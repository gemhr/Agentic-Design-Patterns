# Stage8-WP4 — CI Guardian & Change Correlation

## 1. 名词 / 概念速览

**CI 守护分析（CI Guardian）**
面向一批 CI 结果做聚类、历史对比和变更关联的分析能力，不是单次执行失败分析。

**失败聚类（Failure Clustering）**
按照稳定的 failure signature 把一批失败执行归成少量问题簇。

**历史对比（Historical Comparison）**
把当前 CI cluster 与同 suite 上一次 terminal run 进行数量和状态比较。

**回归信号（Regression Signal）**
用确定性规则判断当前失败是否相对历史出现退化，但不等于已经找到根因。

**变更时间线（Change Timeline）**
按时间组织代码、Feature、Case、环境、配置、Tool、Executor 等近期变更。

**变更候选（Change Candidate）**
根据时间窗口和组件重叠筛出来的“值得怀疑的变化”，不是已确认根因。

**相关性（Correlation）**
两个事件在时间、组件或业务范围上相关。

**因果关系（Causation）**
一个变化被证明导致了一个结果；WP4 没有自动建立这个结论。

**权威 ID 集（Authoritative ID Set）**
由系统生成的 cluster、evidence、change ID 集合，模型只能从中引用。

**幂等分析（Idempotent Analysis）**
同一个 CI Run 重复触发 analyze 时返回同一个 canonical analysis，而不是重复生成。

------

# 2. 本 WP 解决什么业务问题

WP3 解决的是：

```text
一个 execution 为什么失败？
```

也就是单执行 Failure Triage。

但真实 nightly CI 的问题通常是：

```text
昨天 1000 个 case 都正常
今天突然 35 个失败

这些失败是不是同一种问题？
以前有没有？
是不是最近某个版本改动引起的？
影响范围有多大？
下一步先查什么？
```

所以 WP4 把分析层级从：

```text
single execution
```

提升到：

```text
CI batch / cluster / history / change timeline
```

最终链路：

```text
CI Run
→ deterministic failure clustering
→ historical comparison
→ deterministic change candidate selection
→ CI Guardian
→ hypothesis / recommendation
```

最重要的工程原则是：

> 能确定性计算的事实先由代码计算，LLM 只负责解释、归因假设和建议。

Final Gate 已确认 cluster、count、history、change candidate 全部在模型调用前完成。

------

# 3. 工程构建方法问答

## 为什么 Failure Triage 和 CI Guardian 要分开？

因为问题粒度不同。

Failure Triage：

```text
EXEC-001 为什么失败？
```

它需要：

```text
case
expected
actual
environment
logs
feature
```

CI Guardian：

```text
为什么今天这一批 CI 同时出现 20 个 RRC_SETUP_TIMEOUT？
```

它需要：

```text
multiple executions
failure clusters
previous CI
recent changes
```

所以：

```text
Failure Triage = single-run diagnosis
CI Guardian = batch-level regression analysis
```

如果硬塞成一个 Agent，Prompt、Evidence Scope 和结果 Contract 都会越来越混乱。

------

## 为什么要先聚类，再调用 LLM？

假设 CI 有：

```text
100 个失败
```

如果每个失败调用一次模型：

```text
100 failures
→ 100 LLM calls
```

成本高，而且同一类问题可能得到几十种不同解释。

WP4 先做：

```text
100 failures
→ deterministic clustering
→ 3 clusters
→ 1 Guardian analysis
```

这样减少：

```text
Token Cost
Latency
Output Variance
```

而且聚类本身本来就是确定性数据问题，不需要 LLM。

Final Gate 当前是一整个 Run Analysis 只调用一次 Guardian，额外最多一次 repair。

------

## Failure Signature 为什么不能由模型生成？

因为自由文本不稳定。

比如同一个问题模型可能分别写：

```text
RRC setup timeout
RRC connection setup timed out
RRC establishment timeout
```

如果用这些文本聚类，就会把同一个问题拆开。

所以当前优先使用：

```text
CIExecutionResult.failure_signature
```

缺失时再做 deterministic fallback。

Final Gate 还专门修了：

```text
None
""
"   "
大小写差异
```

导致 cluster 不稳定的问题。

------

## 为什么只 cluster FAILED？

因为：

```text
SUCCEEDED
RUNNING
CANCELLED
ERROR
```

未必都属于同一种“测试失败”语义。

Sol 审计发现 Luna 初版把 `ERROR` 和 `FAILED` 混进了同一个 failure analysis boundary，最后收紧成：

```text
FAILED only
```

这说明：

> 状态名看起来都“不正常”，不代表业务语义相同。

------

## 历史基线为什么不能简单取数据库上一条记录？

因为数据库插入顺序不等于业务时间顺序。

例如：

```text
CI-001 completed 10:00
CI-003 completed 12:00
CI-002 补录 completed 11:00
```

如果按自增 ID 或 created_at：

```text
previous run
```

可能选错。

所以当前真实规则：

```text
same suite
+
terminal
+
completed_at < current.completed_at
+
order by completed_at DESC
```

并用 `ci_run_id` 做稳定 tie-break。

------

## 为什么不同 suite 不能互相比？

因为：

```text
smoke suite
full regression suite
performance suite
```

用例规模和失败基线不同。

所以 previous run 必须：

```text
same suite_id
```

否则：

```text
10 / 1000 failures
```

和：

```text
1 / 20 failures
```

根本不能直接比较。

------

## Regression Candidate 是什么意思？

当前它是确定性信号。

例如：

```text
previous_count = 0
current_count = 12
```

可以标记：

```text
new regression candidate
```

或者：

```text
previous_count = 2
current_count = 20
delta = +18
```

说明问题明显扩大。

但它只回答：

> 相比历史是不是出现退化。

不回答：

> 是谁导致的。

Final Gate 明确把这两个边界分开了。

------

## Change Correlation 是怎么做的？

当前没有复杂因果模型。

先做两个 deterministic 条件。

第一层是时间窗口：

```text
previous.completed_at
<
change.occurred_at
<=
current.completed_at
```

如果是第一次 CI：

```text
current.started_at
<
change.occurred_at
<=
current.completed_at
```

第二层是：

```text
cluster affected components
∩
change affected components
!= ∅
```

满足才进入 candidate set。

------

## 为什么还需要模型？规则不是已经找出 Change 了吗？

规则只筛候选。

例如：

```text
Failure Cluster = RRC_SETUP_TIMEOUT
```

最近有：

```text
CHANGE-001 RRC retry logic
CHANGE-002 RRC logging
CHANGE-003 RRC timer adjustment
```

三者时间和组件都匹配。

系统可以确定：

> 这三个值得分析。

但哪个最可疑、为什么、应该先查什么，需要语义推理。

所以：

```text
deterministic code
→ candidate generation

LLM
→ hypothesis and recommendation
```

------

## 为什么 correlation 不能直接当 causation？

因为：

```text
Change A happened
然后 Failure B happened
```

并不证明：

```text
A caused B
```

可能还有：

```text
环境变化
TestData 变化
并发故障
其他隐藏提交
```

所以结果 Contract 使用：

```text
suspected_change_ids
root_cause_hypothesis
```

而没有：

```text
confirmed_cause
```

------

## Change ID 为什么也要有 Authority？

模型可能生成：

```text
CHANGE-999
```

但系统根本没有这个 Change。

因此：

```text
suspected_change_ids
⊆
deterministic candidate IDs
```

否则触发 shared repair。

第二次仍非法就 fail closed。

------

## Cluster ID 也需要校验吗？

需要。

Sol 审计实际发现：

> Luna 初版只校验 Evidence ID 和 Change ID，没有校验 Cluster ID。

模型如果返回：

```text
CLUSTER-999
```

分析就失去绑定。

最后 Cluster ID 也纳入同一个 semantic validator。

------

## 为什么所有 semantic error 共用一次 repair budget？

比如一次模型结果同时存在：

```text
fake evidence
fake change ID
bad confidence
```

不能分别：

```text
evidence repair 1 次
change repair 1 次
confidence repair 1 次
```

否则所谓“最多一次 repair”实际上会无限放大。

所以当前：

```text
Initial
+
at most one total repair
```

JSON、confidence、Evidence、Change、Cluster 都共享这一个预算。

------

## 为什么 CI Guardian 不直接自动创建 Ticket？

因为 WP4 负责的是：

```text
analysis
```

不是：

```text
execution authority
```

Guardian 可以建议：

```text
OPEN_TICKET
```

但如果真的执行，仍然应该回到 WP2：

```text
stage8_create_ticket
→ Governance
→ HITL
→ Claim
```

当前 WP4 明确没有自动 Ticket、rerun、rollback、release block。

------

## 为什么 CI Guardian 不能直接当 Release Gate？

因为：

```text
分析建议
```

和：

```text
是否允许发布
```

是两个不同 Authority。

如果以后做 Release Gate，需要独立定义：

```text
Policy
Threshold
Override
Approval
Audit
```

当前 Guardian 只做分析。

------

## 为什么历史 CI 不放 Memory？

因为：

```text
昨天是否失败了 20 个 case
```

是业务事实。

必须来自：

```text
PostgreSQL / CI Platform
```

而不是 Memory。

Memory 可以保存经验：

```text
RRC_SETUP_TIMEOUT 常见原因是什么
```

但不能成为 CI Truth。

------

## 为什么当前不用 RAG 做历史失败检索？

因为当前 WP4 只比较：

```text
current CI
vs
previous CI
```

这是结构化数据。

SQL 比 embedding 更直接。

RAG 更适合以后：

```text
在半年历史问题中找相似 failure
```

当前不需要为了“AI 感”硬加。

------

# 4. 30 秒项目回答

> 在 CI Guardian 这一层，我没有让模型直接读一堆 CI 结果自己判断，而是先用确定性代码做 failure signature 聚类、上一条同 suite CI 对比以及 Change Timeline 候选筛选。比如某类失败从上一轮 0 个变成当前 12 个，会先被系统标成 regression candidate；再根据前后 CI 的时间窗口和 affected component overlap 筛出近期变更。最后才让 CI Guardian Agent 基于这些结构化事实生成根因假设和建议。模型只能引用系统提供的 cluster、evidence 和 change ID，所以它不能自造证据，而且我们明确把 correlation 和 causation 分开。

------

# 5. 2 分钟项目回答

> Stage8 前面已经能对单次失败做 Failure Triage，但真实 nightly CI 更常见的问题是，一晚上可能同时失败几十个 Case，需要先判断是不是同一种问题、是不是新回归、以及和最近哪些变化相关。
>
> 所以 WP4 我做了一层 CI Guardian。第一步不是调用 LLM，而是先用确定性逻辑处理 CI 数据。FAILED execution 按稳定的 failure signature 聚类，signature 缺失时使用 canonical fallback。然后针对每个 cluster，找同 suite、严格早于当前 CI 的最近一条 terminal run，计算 previous count、current count、delta、is_new 和 regression candidate。
>
> 变更关联也是系统先筛。Change Timeline 包括 Code Commit、Feature Merge、Tool Release、Case、Environment、Config、Executor 变化。系统只选择前一轮 CI 到当前 CI 之间的 change，再要求 affected component 和 failure cluster 有交集，得到候选集合。
>
> 最后 CI Guardian 才进入现有 Specialist Runtime。模型只负责解释这些已经计算好的 facts，输出 suspected change、root-cause hypothesis 和 recommendation。Evidence ID、Change ID、Cluster ID 都必须属于系统提供的集合，否则最多 repair 一次，再错就 fail closed。
>
> 另外我们没有把相关性当成因果，也没有让 Guardian 自动提 Ticket、rerun 或阻断发布。它当前只是 Analysis Authority。如果以后要执行这些动作，仍然回到已有 Tool Governance 和 HITL。
>
> 持久化上每个 CI Run 只有一个 canonical analysis，重复 analyze 直接返回原结果，并发请求通过 row lock 和 unique constraint 保证不会生成两个 version 1。

------

# 6. 高频追问 + 简答

## CI Guardian 和普通监控告警有什么区别？

监控通常回答：

```text
失败数量超过阈值了吗？
```

CI Guardian还会结合：

```text
failure cluster
history
recent changes
```

给出：

```text
suspected cause
impact
next action
```

但最终仍然是分析，不是执行 Authority。

------

## 为什么不直接把所有 CI 日志丢给大模型？

三个问题：

```text
成本高
结果不稳定
无法保证统计事实正确
```

Count、Cluster、Time Window 本来就是代码更擅长的事情。

------

## Failure Clustering 为什么不用 Embedding？

当前已有稳定：

```text
failure_signature
```

这是强业务信号。

如果它已经足够区分问题，再上 embedding clustering 只会增加：

```text
复杂度
阈值问题
不可解释性
```

------

## 如果两个 Failure Signature 文本不同但实际是同一问题怎么办？

这是当前简单 clustering 的限制。

未来可以：

```text
signature normalization
+
rule mapping
+
embedding similarity
```

增强。

当前 Completion Boundary 明确只是 simple signature clustering。

------

## CI Guardian 是每个 cluster 调一次模型吗？

当前不是。

当前：

```text
one CI run analysis
→ one Guardian invocation
```

模型一次看到系统构建好的 cluster / comparison / candidate 集合。

只有失败校验时最多再 repair 一次。

------

## Previous Run 怎么定义？

```text
same suite
terminal
completed_at < current.completed_at
nearest completed_at
```

不能按数据库插入顺序。

------

## Current CI 是第一次运行怎么办？

没有 previous run：

```text
previous_count = 0
```

当前出现的 failure cluster 会视为 new regression candidate。

Change window 则使用：

```text
current.started_at
<
change.time
<=
current.completed_at
```

------

## 一个 Change 为什么可能关联多个 Cluster？

因为同一个代码修改可能影响多个 Case / Component。

Correlation 是：

```text
cluster ↔ candidate changes
```

不是一对一绑定。

------

## Confidence 是概率吗？

不是严格统计概率。

当前只是模型对自己 hypothesis 的置信元数据，范围限制：

```text
0..1
```

不能说：

> 0.9 就代表 90% 真实概率。

------

## Guardian 为什么不能自己创造 Change？

因为 Change Timeline 是外部系统事实。

模型没有 Authority 声明：

```text
“最近肯定有一个 RRC patch”
```

如果没有对应 ChangeEvent，它不能作为证据。

------

## 同一个 CI Run 重复 analyze 怎么办？

当前 Contract 是：

```text
one analysis per run
version = 1
```

再次 analyze：

```text
return existing snapshot
```

不会再次调用模型。

------

## 两个请求同时 analyze 呢？

当前：

```text
CI run row lock
+
analysis.ci_run_id UNIQUE
```

双保险。

最终只能产生一个 canonical analysis。

------

## 为什么还需要 digest？

分析结果是 durable artifact。

通过：

```text
canonical JSON
→ UTF-8
→ SHA-256
```

可以稳定标识这个 snapshot。

以后 UI、Review 或外部引用可以绑定具体分析内容。

------

# 7. Bad Case

## Real Bad Case 1 — Agent 注册了，但生产 Adapter 没注册

Luna 已经：

```text
DEFAULT_AGENT_REGISTRY
→ ci_guardian
```

看起来完成。

但生产：

```text
AgentAdapterFactory
```

没有对应：

```text
ci_guardian_adapter
```

结果真实 Runtime Factory 会构造失败。

Sol 最终补上同源 `AgentRouterSingleAgentAdapter`。

这是典型的：

> Registry existence != production reachability。

------

## Real Bad Case 2 — Cluster ID 没做 Authority 校验

初版已经验证：

```text
Evidence ID
Change ID
```

但漏了：

```text
Cluster ID
```

模型仍然可以返回：

```text
CLUSTER-999
```

最后 Cluster ID 也纳入同一个 semantic validator 和 repair budget。

------

## Real Bad Case 3 — 空白 Signature 导致聚类不稳定

这些：

```text
None
""
"   "
```

如果不规范化，可能被视为三个不同 cluster。

再加上：

```text
RRC
rrc
" RRC "
```

也可能拆开。

最后统一 canonicalize signature 和 component。

------

## Real Bad Case 4 — 把 ERROR 和 FAILED 混在一起

初版 cluster 把两者都认为是 Failure。

但：

```text
FAILED
```

可以是 Case 执行失败；

```text
ERROR
```

可能是基础设施或执行框架异常。

业务语义不同。

最终 WP4 clustering 只处理 `FAILED`。

------

## Real Bad Case 5 — Previous Run 选择了 unfinished run

如果：

```text
CI-001 COMPLETED
CI-002 RUNNING
CI-003 current
```

错误逻辑可能拿：

```text
CI-002
```

做 historical baseline。

它还没有完整结果，comparison 会失真。

最终只选择：

```text
terminal + strictly earlier
```

的 run。

------

## Real Bad Case 6 — Duplicate Analyze 产生两个 version=1

Luna 初版：

```text
Analyze CI-001
→ version 1

Analyze CI-001 again
→ another version 1
```

这说明：

```text
version
```

只是字段，没有真正语义。

最终改成：

```text
one CI run
→ one canonical version 1
```

重复请求直接返回已有 snapshot，并发用 row lock + unique constraint 收敛。

------

## Hypothetical Bad Case — Correlation 被升级成 Causation

假设：

```text
02:00 commit RRC code
03:00 CI RRC cases failed
```

系统如果直接输出：

```text
RRC commit caused CI failure
```

这是过度结论。

正确只能是：

```text
RRC commit is a suspected correlated change
```

还需要：

```text
reproduction
rollback comparison
additional evidence
```

才能进一步确认因果。

------

# 8. Truth / Owner / Completion Boundary

## CI Run Truth

External CI / Mock CI 持有原始执行事实。

Stage8：

```text
stage8_ci_runs
```

保存 immutable snapshot。

重复同 `ci_run_id` 不允许覆盖。

------

## Failure Cluster Truth

Owner：

```text
deterministic cluster_failures()
```

模型不是 Cluster Authority。

------

## Historical Comparison Truth

Owner：

```text
deterministic compare_history()
```

负责：

```text
current_count
previous_count
delta
is_new
regression_candidate
```

模型只解释。

------

## Change Candidate Truth

Owner：

```text
deterministic correlate_changes()
```

负责：

```text
time window
component overlap
candidate set
```

模型不能添加不存在的 Change。

------

## CI Guardian Truth

CI Guardian 输出的是：

```text
analysis
hypothesis
recommendation
```

而不是：

```text
confirmed fact
```

------

## Evidence Truth

Evidence ID 由系统构造。

当前包括：

```text
CI run
execution
cluster
change timeline
```

模型只引用。

------

## Analysis Truth

Owner：

```text
CIGuardianApplicationService
stage8_ci_analysis
```

Contract：

```text
one analysis per CI run
version = 1
canonical digest
```

------

## Transaction Owner

继续是：

```text
CIGuardianApplicationService
```

Repository 只使用传入 session。

没有 Repository 自己 commit。

------

## Migration Truth

当前 head：

```text
0014_stage8_wp4
```

并且：

```text
down_revision = 0013_stage8_wp3
```

------

## WP4 真正完成

已经真实实现：

```text
CI Run durable snapshot

FAILED-only deterministic clustering

stable failure signature normalization

same-suite previous terminal run selection

historical comparison

deterministic regression signal

Change Timeline

bounded time-window correlation

normalized component overlap

system-owned Evidence IDs

system-owned Change IDs

system-owned Cluster IDs

ci_guardian Specialist

existing Runtime reuse

strict JSON / Pydantic

shared one-repair budget

correlation / causation boundary

durable CI analysis

canonical digest

duplicate analyze idempotency

concurrent analyze safety

thin HTTP APIs
```

Final Gate 均确认通过。

------

## WP4 没完成

明确没有：

```text
真实 Jenkins / GitLab CI / GitHub Actions

cron scheduler

Kafka / HA worker

多历史 Run 趋势分析

ML / Embedding clustering

长期 CI RAG

automatic ticket

automatic rerun

automatic rollback

release gate

Web UI
```

这些属于当前 Completion Boundary，不是遗留 Bug。

------

# 9. 本 WP 最应该记住的五句话

第一句：

> **能确定性计算的 CI Facts 不交给 LLM，模型只负责解释和假设。**

第二句：

> **先 Cluster，再调用 Agent；不要为每条失败单独做一次大模型分析。**

第三句：

> **Regression Signal 说明发生了退化，Change Correlation 说明值得怀疑，但二者都不等于已经证明因果。**

第四句：

> **Evidence ID、Change ID、Cluster ID 都属于系统 Authority，模型只能引用，不能创造。**

第五句：

> **CI Guardian 当前只有 Analysis Authority，没有 Ticket、Rollback、Release Gate 等 Execution Authority。**