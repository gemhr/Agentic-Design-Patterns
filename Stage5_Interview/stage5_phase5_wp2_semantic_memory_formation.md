当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase5-WP2 学习 / 面试总结

## Semantic Memory Formation

WP2 是 Phase5 里第一个真正把 **Long-term Memory（长期记忆）** 从“能存”推进到“会形成”的 WP。

一句话概括：

> **在 canonical Coordinated Runtime 中，把一次已经成功交付并完成 Conversation commit 的 Run，转化为受策略约束的 Semantic Memory Candidate，再由 LocalAgent 做最终 Should Remember 决策并持久化为 `ACTIVE SEMANTIC` Memory。**

WP2 已经完成三层验证：

```text
Architecture Decision = PASS_WITH_ACCEPTED_LIMITATIONS
Implementation = IMPLEMENTED / TESTED
Real Formation Smoke Experiment = PASS
```

Codex Final Gate 也确认：

```text
ARCHITECTURE_COMPLIANCE = FULL
OPEN_P0 = 0
OPEN_P1 = 0
REMEDIATED_P1 = 2
WP3_SCOPE_LEAK = NONE
```



------

# 1. 一句话项目定义

**WP2 在 Output 已成功交付、Conversation Exchange 已持久化之后，引入独立 Semantic Memory Formation 流程，通过 deterministic eligibility + LLM candidate extraction + code-owned validation，把明确、稳定、长期有效的用户事实形成 `ACTIVE SEMANTIC` Memory。**

面试时可以压缩成：

> 我不是让 LLM 直接写 Memory，而是在 delivered exchange 后增加独立 Formation pipeline：先做 deterministic eligibility，再让 LLM 提 candidate，最后由代码做 grounding、policy 和 authoritative record preparation，只有通过验证的事实才能进入长期 Memory。

------

# 2. 为什么需要 WP2

WP1 已经解决：

```text
Memory 怎么存
Memory ID 是什么
Status 怎么表示
Schema 怎么迁移
```

但还没有解决：

> **什么时候应该记？**

如果没有 WP2，最容易出现三种错误。

------

## 2.1 所有用户输入都保存

例如：

```text
今天先临时用 pip 装一下。
```

如果直接保存，就会让未来 Agent 错误认为：

> “这个项目长期使用 pip。”

这叫：

**Memory Pollution（记忆污染）**。

------

## 2.2 Assistant 自己说的话被固化

例如用户只问：

```text
你猜这个项目可能用什么数据库？
```

Assistant 猜：

```text
可能是 PostgreSQL。
```

如果系统把 final answer 当事实源，就会形成：

```text
database = PostgreSQL
```

这相当于：

> Assistant hallucination 被永久固化。

因此 WP2 冻结：

```text
Original User Explicit Assertion
= 第一版唯一事实 Authority
```



------

## 2.3 Model 直接拥有写 Memory 的权力

最危险的 Demo 设计是：

```text
LLM:
{
  "remember": true,
  "memory_id": "...",
  "status": "ACTIVE"
}
→ DB
```

这样 Model 实际成为了：

**Mutation Authority（修改权威）**。

WP2 正式把它改成：

```text
LLM = Candidate Producer
LocalAgent = Mutation Authority
```

这是 WP2 最核心的工程边界之一。

------

# 3. 当前真实架构

WP2 最终真实链路：

```text
User Query
    ↓
Canonical Coordinated Runtime
    ↓
Planning / Execution / Synthesis
    ↓
OutputGate
    ↓
DELIVERED
    ↓
RunFinalMemoryWriter
    ↓
Conversation Exchange COMMITTED
    ↓
CommittedExchangeReceipt
    ↓
SemanticMemoryFormation
    ↓
Deterministic Eligibility
    ↓
LLM Candidate Proposal
    ↓
Strict Parser
    ↓
Source Grounding
    ↓
Code-owned Should Remember Policy
    ↓
Semantic Normalization
    ↓
SemanticMemoryRecord
    ↓
AdvancedMemoryStore.create()
    ↓
SQLite long_term_memory
```



这条链最重要的两个先后关系：

```text
DELIVERED
必须早于
FORMATION
```

以及：

```text
Conversation COMMIT
必须早于
FORMATION
```

------

# 4. Owner / Contract

## 4.1 OutputGate

仍然只负责：

> final output 是否成功交付。

它不调用 LLM 做 Memory，也不写 Long-term Memory。

------

## 4.2 RunFinalMemoryWriter

仍然只负责：

**Conversation Persistence（对话持久化）**。

WP2 只让它返回：

```
CommittedExchangeReceipt
```

里面只有必要 identity：

- `run_id`
- `exchange_id`
- `entry_agent_id`
- `memory_scope`

没有把 query / answer / Tool / RAG 全塞进去。

------

## 4.3 SemanticMemoryFormation

WP2 新增的核心 Owner。

负责：

```text
eligibility
candidate extraction
strict parsing
grounding
policy validation
normalization
record preparation
persistence orchestration
observation
```

------

## 4.4 AdvancedMemoryStore

继续只负责：

```text
create
get
list
```

不拥有：

- Should Remember；
- LLM Prompt；
- conflict；
- supersede。

------

# 5. 为什么 Formation 必须在 DELIVERED 之后

假设在 Synthesis 之前就形成 Memory：

```text
specialist output
→ Memory
```

可能保存的是：

- 中间猜测；
- 未采用方案；
- tool raw result；
- 最终没交付的信息。

因此 WP2 冻结：

```text
OutputGate = DELIVERED
→ Conversation committed
→ Formation
```

只有真正交付给用户的 Run 才有资格进入 Formation lifecycle。

------

# 6. 为什么 Conversation Commit 还必须先于 Formation

这点很容易被忽略。

不能：

```text
Memory 写成功
→ Conversation commit 失败
```

否则会出现：

> 长期 Memory 说某次交流发生过，但 canonical Conversation 根本没有提交成功。

因此真实顺序：

```text
Conversation Exchange
COMMIT SUCCESS
        ↓
拿到 origin_exchange_id
        ↓
Formation
```

这样 provenance 才可信。

------

# 7. Formation 为什么不用一个事务全包

没有做：

```text
Conversation INSERT
+
LLM Formation
+
Long-term Memory INSERT
=
一个 SQLite transaction
```

因为 LLM 可能耗时几秒甚至更久。

如果放在 SQLite transaction 中：

- 锁时间变长；
- failure coupling 增强；
- delivered result 会被 Memory failure 污染。

所以最终设计是：

```text
Transaction 1
Conversation Exchange

Transaction 2
Memory A

Transaction 3
Memory B
```

各自独立。

------

# 8. Execution Model 的取舍

WP2 没有采用：

- fire-and-forget；
- background worker；
- Kafka；
- MQ；
- outbox。

第一版采用：

**Isolated Bounded Awaited Post-delivery Execution（隔离、有界、等待完成的交付后执行）**。

意味着：

```text
answer 已经 delivery
↓
request 尾部继续 Formation
↓
Formation 收口
↓
Run 完整结束
```

好处：

- 不会 detached task；
- shutdown 有 owner；
  -实现成本低；
- failure 易观察。

代价：

> Formation latency 会增加 request tail time。

但不会增加：

`OutputGate delivery latency`。

------

# 9. Should Remember 的核心设计

最终不是纯规则，也不是纯 LLM。

而是：

```text
Deterministic Eligibility
        ↓
LLM Proposal
        ↓
Strict Parser
        ↓
Code-owned Validation
        ↓
ACCEPT / IGNORE
```

这是典型：

**Hybrid Policy（混合策略）**。



------

## 为什么不用纯 deterministic

自然语言里：

```text
以后统一使用 uv。
```

和：

```text
今天临时用 uv。
```

很难全部靠正则可靠判断。

------

## 为什么不用纯 LLM

因为：

```text
LLM says REMEMBER
```

不应该直接等于：

```text
DB INSERT
```

否则 Model 就变成最终政策 Owner。

------

# 10. 哪些内容可以记

WP2 第一版 allowlist：

### Stable User Preference（稳定用户偏好）

例如：

```text
以后回答都尽量简洁。
```

### Project Stable Fact（稳定项目事实）

例如：

```text
这个项目数据库使用 PostgreSQL。
```

### Engineering Constraint（工程约束）

例如：

```text
这个项目不能使用公网 API。
```

### Explicit Long-term Decision（明确长期决策）

例如：

```text
以后统一使用 uv 管理依赖。
```

### User Correction（用户明确修正）

例如：

```text
数据库已经改成 PostgreSQL。
```



------

# 11. 哪些必须 Ignore

至少包括：

- 临时行为；
- one-off operation；
- small talk；
- uncertain / speculative statement；
- assistant-only inference；
- assistant recommendation；
- Tool-only fact；
- RAG-only fact；
- third-party quote；
- malformed candidate；
- ungrounded candidate。

------

# 12. Source Authority 是怎么控制的

当前第一版明确：

```text
Original User Query
= Fact Authority
```

Delivered Final Answer：

```text
= Normalization Context Only
```

Tool / RAG：

```text
= NOT TRUSTED AS DIRECT SEMANTIC SOURCE
```

这是一个非常重要的安全设计。

例如：

RAG 文档中写：

```text
系统使用 Oracle。
```

并不代表：

> 用户自己的项目使用 Oracle。

所以不能因为它进入 Model Context 就自动成为 Memory。

------

# 13. Source Grounding 怎么实现

真实 Final Gate 已验证：

candidate 中的：

```
source_excerpt
```

必须经过：

- whitespace normalization；
- case normalization；

然后成为：

> original user query 的连续 substring。

空字符串、过短或无法匹配：

```text
fail closed
```



这不是：

**Semantic Entailment（语义蕴含）**。

它只能证明：

> 这个 candidate 至少绑定到了用户真实说过的一段文本。

不能证明：

> candidate 对那段话的语义理解一定正确。

所以仍有 semantic misclassification limitation。

------

# 14. Candidate Contract

Model 只能产生类似概念：

```text
REMEMBER / IGNORE
category
canonical_text proposal
logical_key proposal
value
source_excerpt
reason
```

Model 不允许决定：

```text
memory_id
MemoryType
MemoryStatus
scope
origin
timestamps
formation_method
supersede
forget
SQL
```

Strict Parser（严格解析器）对 unknown / forbidden field：

```text
fail closed
```



------

# 15. Semantic Normalization

最终 record 不是保存整段用户话。

而是拆成 atomic fact。

例如：

```text
这个项目以后统一使用 uv 管理依赖。
```

可能形成：

```text
logical_key:
project.package_manager

payload:
{"value": "uv"}

canonical_text:
The project's package manager is uv.
```

核心是：

**Atomic Memory（原子记忆）**。

每条 Memory 应能被：

- 单独更新；
- 单独 supersede；
- 单独 forget；
- 单独 retrieve。

------

# 16. 为什么 payload 只允许 scalar

WP2 第一版规定：

```text
{"value": scalar}
```

scalar：

- string
- number
- boolean

暂时不允许：

- list
- arbitrary nested object；
  -复杂 Profile Schema。

目的不是表达能力最大化，而是：

> 先让 Memory lifecycle 简单、可测、可解释。

------

# 17. Formation Method

当前正式 vocabulary：

```text
HYBRID
```

含义：

```text
LLM proposes
+
LocalAgent validates
```

没有提前加入：

```text
MANUAL
DETERMINISTIC
IMPORT
TOOL
```

因为这些路径并没有真实存在。

------

# 18. Memory Identity 谁生成

`memory_id`：

由 LocalAgent authoritative Formation boundary 生成。

不是：

- Model；
- content hash；
- logical key；
- SQLite auto increment。

这延续了 WP1 的 stable identity Contract。

------

# 19. Idempotency 的真实边界

这是 WP2 很重要的知识点。

WP2 只保证：

**Same-execution Persistence Retry Idempotency（同一次 Formation 执行内持久化重试幂等）**。

流程：

```text
LLM extraction once
↓
validation once
↓
prepare complete immutable record once
↓
persist
↓
遇到可重试 persistence uncertainty
↓
retry SAME record
```

重试不能：

```text
重新 LLM
重新生成 ID
重新 timestamps
```



------

# 20. WP2 故意没有做 Cross-run Dedup

例如两个 Run：

```text
Run A:
database = PostgreSQL

Run B:
database = PostgreSQL
```

WP2 当前允许：

```text
Memory A ACTIVE
Memory B ACTIVE
```

这是 deliberate limitation。

因为：

```text
这是同一个事实吗？
应该 NO_CHANGE 吗？
应该 merge 吗？
```

已经是 Consolidation / Conflict Resolution 问题。

Owner：

**WP3**。

------

# 21. Correction 为什么旧事实仍然 ACTIVE

真实实验 F3：

Setup：

```text
SQLite ACTIVE
```

Correction：

```text
数据库已经改成 PostgreSQL。
```

WP2 正确结果：

```text
SQLite      ACTIVE
PostgreSQL  ACTIVE
```

不是 bug。

因为 WP2 只负责：

> 新事实 Formation。

WP3 才负责：

```text
SQLite
ACTIVE → SUPERSEDED

PostgreSQL
ACTIVE
```

------

# 22. Multi-candidate Formation

一个用户输入可以拆多条。

例如：

```text
数据库改 PostgreSQL，以后依赖都用 uv。
```

可形成：

```text
Memory 1:
project.database = PostgreSQL

Memory 2:
project.package_manager = uv
```

当前最大：

```text
8 candidates
```

每条独立 transaction。

一条失败不会 rollback 已成功的其他 Memory。

------

# 23. Formation Result

不是简单：

```text
success = true
```

而是 typed outcome：

```text
SUCCEEDED
PARTIAL
FAILED
CANCELLED
TIMED_OUT
```

并记录：

- proposed count
- accepted count
- ignored count
- persisted count
- reused count
- failed count

所以：

```text
accepted=0
```

可以完全是：

```text
SUCCEEDED
```

因为：

> “没有值得记的信息”是正常业务结果。

------

# 24. Failure Isolation

这是 WP2 最重要的 Runtime Contract 之一。

如果：

```text
Answer 已经 DELIVERED
```

随后：

```text
Formation FAILED
```

不能：

```text
Run → FAILED
```

也不能：

- 重发 answer；
- 撤销 answer；
- 修改 Step succeeded；
  -改变 terminal。

Final Gate 对这个行为进行了真实源码级验证。

------

# 25. CancelledError Bad Case

Final Gate 真实发现：

某些非 production/custom Formation runner 直接抛：

```python
asyncio.CancelledError
```

可能掉进现有 Runtime cancellation path。

风险：

```text
已经 DELIVERED
↓
Formation runner cancelled
↓
整个 Run 被误判 cancellation/failure
```

修复：

把它转换为独立：

```text
FormationStatus = CANCELLED
FORMATION_CANCELLED
```

而不改变 final terminal。

这是一个非常适合面试的真实 Bad Case。

------

# 26. Small-talk / Transient Gate Bad Case

Final Gate 还发现：

原 implementation 对一些：

- small talk；
- transient；
- uncertain；
- tool-only；

仍然过度依赖 LLM。

这意味着：

```text
LLM 误判 REMEMBER
```

可能增加 false positive。

修复后变为：

```text
Pre-model narrow deterministic gate
+
Post-model code policy
```



这也是一个非常真实的：

**LLM 不应该拥有最终策略权** 的例子。

------

# 27. Observation 设计

WP2 新增：

```
MEMORY_FORMATION_COMPLETED
```

但它不是业务 Source of Truth。

业务 Authority：

```text
SemanticMemoryRecord
```

Observation 只记录：

- run/exchange identity
- status
- counts
- safe reason
- memory_id
- latency

不记录：

- query
- final answer
- canonical text
- payload
- source excerpt
- prompt
- CoT
- raw exception



------

# 28. 为什么 Observation 不能参与事务

如果：

```text
Memory persisted
Event emit failed
```

应该：

```text
Memory = SUCCESS
Observation = MISSING
```

而不是：

```text
rollback Memory
```

这体现：

```text
Business Authority
!=
Observability
```

------

# 29. Formation Latency

记录三类：

```text
formation_total_duration
model_extraction_duration
persistence_duration
```

但没有制定：

- SLO；
- benchmark；
- P95；
  -吞吐量目标。

当前只是：

**Instrumentation（仪表化）**。

------

# 30. Timeout 的真实语义

当前 Formation：

```text
30s orchestration timeout
```

但不是：

> 所有 blocking operation 物理上 30 秒立刻杀死。

如果线程里的：

- Model call；
- SQLite operation；

还需要完成安全收口，wall time 可以超过 30 秒。

Final Gate 明确把这个保留为 limitation。

------

# 31. 真实实验

WP2 已经完成了真实 Formation Smoke。

Frozen Cases：

### F1 Stable

```text
这个项目以后统一使用 uv 管理依赖。
```

结果：

```text
1 ACTIVE SEMANTIC
PASS
```

------

### F2 Transient

```text
今天先临时用 pip 装一下。
```

结果：

```text
0 Memory
PASS
```

------

### F3 Correction

Setup：

```text
SQLite ACTIVE
```

Correction：

```text
数据库已经改成 PostgreSQL。
```

结果：

```text
SQLite ACTIVE
PostgreSQL ACTIVE
PASS
```

符合 WP2 boundary。

------

### F4 Assistant-only

用户只要求 Assistant 猜测数据库。

结果：

```text
0 Memory
PASS
```

因此：

```text
WP2_REAL_FORMATION_SMOKE = PASS
```

但不要表述：

```text
Formation Precision = 100%
```

四个 case 只是 smoke，不是正式 dataset。

------

# 32. Planning Token 真实问题

真实实验中还暴露过一个与 Formation 独立的 Runtime reliability 问题：

```text
REMOTE_OUTPUT_TRUNCATED
→ PLANNING_FAILED
```

最终确认根因：

```text
Planning output token budget = 512
```

太小，Planner structured output 有概率被截断。

提高 Planning token budget 后问题已修复。

这个问题很有面试价值，因为它体现了：

> LLM Runtime 的 token budget 不只是成本配置，同时是 correctness contract 的一部分。

------

## 为什么同样输入有时成功有时失败

因为模型每次输出长度不是完全固定。

同一个任务可能一次：

```text
450 tokens
```

成功。

另一次：

```text
>512 tokens
```

被截断。

于是出现：

```text
same input
→ sometimes success
→ sometimes REMOTE_OUTPUT_TRUNCATED
```

不是业务逻辑随机。

而是 output length 与固定 token ceiling 的交互。

------

## 这个 Bad Case 的关键根因

不是：

- Planning timeout；
- Formation；
- SQLite；
- Network disconnect。

而是：

**Output Budget Under-provisioning（输出预算不足）**。

------

# 33. 为什么这是 Runtime 问题而不是 Prompt 问题

当然可以让 Planner Prompt 更短。

但真正通用的问题是：

> Runtime 给 structured output 留的 budget 是否足够承载 contract。

如果一个 Plan contract 合法情况下可能超过 512 token，那 512 本身就是错误配置。

因此修复应该从：

```text
合理 output budget
```

入手，而不是：

```text
遇到 truncation 猜着补 JSON
```

后者非常危险。

------

# 34. 真实测试结果

Codex Final Gate：

```text
Direct WP2
69 passed

Runtime
98 passed

Model + Advanced Memory
66 passed + 12 subtests

Observability / Trace
248 passed

Stage3 injection E2E
2 passed
```

Full repo：

```text
2807 passed
4 failed
13 deselected
42 subtests passed
```

4 个失败为已确认 pre-existing baseline。

------

# 35. Known Limitations

当前仍存在：

### Crash durability

```text
Conversation committed
↓
process hard crash
↓
Formation 可能未发生
```

无 outbox / durable replay。

------

### Cross-process Formation idempotency

没有。

Restart 后人工重放可能重新形成 Memory。

------

### Cross-run duplicate

没有。

属于 WP3。

------

### Tool / RAG attestation

当前直接拒绝。

以后若支持 Tool-grounded Memory，需要额外 Source Attestation（来源证明）设计。

------

### Semantic grounding

当前 substring grounding 只证明 textual provenance。

不能形式化证明语义正确。

------

### Identity

没有：

- user
- thread
- project
- shared durable identity。

------

# 36. WP2 没有完成什么

必须明确：

```text
Semantic NO_CHANGE = NOT_IMPLEMENTED
Conflict Resolution = NOT_IMPLEMENTED
Supersede = NOT_IMPLEMENTED
Explicit Forget = NOT_IMPLEMENTED
```

以及：

```text
Memory Retrieval = NOT_IMPLEMENTED
Ranking = NOT_IMPLEMENTED
Context Injection = NOT_IMPLEMENTED
```

还有：

```text
Formal Stateful Evaluation = NOT_IMPLEMENTED
```

真实 Smoke 已完成，但正式指标仍属于 WP5。

------

# 37. 名词 / 概念速览

### Memory Formation（记忆形成）

从一次真实交互中识别并生成长期记忆候选的过程。

### Semantic Memory（语义记忆）

保存稳定事实、偏好、约束和长期决策的长期记忆类型。

### Candidate（候选）

Model 提出的“建议记住的信息”，尚未拥有业务权威。

### Mutation Authority（修改权威）

最终有权创建或改变长期 Memory 的组件。

### Should Remember Policy（是否应记忆策略）

判断一个 candidate 是否值得进入长期 Memory 的规则。

### Source Authority（来源权威）

规定哪些信息来源有资格被认定为长期事实。

### Grounding（溯源绑定）

验证 candidate 是否真正基于允许的原始输入。

### Memory Pollution（记忆污染）

把临时、错误、推测或不可信信息持久化为长期 Memory。

### Hybrid Formation（混合式记忆形成）

LLM 提候选，代码拥有最终验证和持久化决定权。

### Atomic Fact（原子事实）

可单独生命周期管理的最小事实单位。

### Formation Idempotency（形成幂等）

同一次 Formation 的持久化重试不会重复产生 Memory。

### Observation Artifact（观测产物）

用于监控和评测 Formation 的安全、非权威数据。

### Output Budget（输出预算）

允许模型生成的最大输出 token 数，是结构化 LLM contract 的 correctness 参数之一。

------

# 38. 工程构建类面试题

## Q1：为什么不让 LLM 直接判断 remember=true 后写数据库？

推荐答：

> LLM 输出不能直接拥有 mutation authority，因为它有 hallucination、prompt injection 和 schema escape 风险。我的实现把 LLM 限制为 candidate producer，最终 source validation、category policy、identity、status 和 persistence 都由代码控制。

------

## Q2：为什么只信 original user query？

> 第一版先把 source authority 收窄到用户明确陈述。Assistant、RAG、Tool 或第三方内容都可能是推断或外部事实，不能自动升级为“用户长期事实”。后续如果要支持 Tool-confirmed Memory，需要额外 attestation contract。

------

## Q3：为什么 Formation 必须在 OutputGate DELIVERED 后？

> 防止把中间 step、未交付 synthesis 或失败 Run 内容永久化。只有 final output 真正 delivered，且 canonical exchange commit 成功后，Formation 才开始。

------

## Q4：为什么 Formation failure 不能把 Run 改成失败？

> Final output 已经交付成功，Long-term Memory 属于 post-delivery enhancement。Formation failure 如果反向改变 terminal，就会出现“用户已经收到答案但系统 Run 又失败”的语义冲突，所以 Formation outcome 必须独立。

------

## Q5：为什么不把 conversation 和 Memory 放一个 transaction？

> Formation 包含 LLM 调用，事务时间太长；而且会把 Long-term Memory policy failure 与 conversation durability耦合。Conversation 先独立 commit，Memory 再 per-record transaction，更符合 failure isolation。

------

## Q6：为什么不在 WP2 做 duplicate suppression？

> Duplicate、NO_CHANGE 和 conflict 都要求读取已有 Memory 并判断新旧事实关系，这已经属于 Consolidation 和 Lifecycle Policy，所以我故意把它冻结到 WP3，避免 Formation 和 Conflict Resolution 混在一个阶段。

------

## Q7：为什么 payload 设计得那么简单？

> v1 只保存 `{"value": scalar}`，是为了让事实保持 atomic、容易比较和生命周期管理。过早支持任意 nested schema 会让 conflict、ranking 和 evaluator复杂度快速增加。

------

## Q8：substring grounding 有什么局限？

> 它能保证 candidate 的 evidence 确实出现在 original user input 中，但不能证明语义蕴含完全正确，所以它属于 provenance gate，不是 semantic verifier。真实实验仍然需要验证 false positive / false negative。

------

## Q9：为什么真实实验只做四个 Case？

> WP2 目标是验证 production chain 和关键 policy 是否真实可达，所以先做 frozen smoke cases。正式 Formation Precision、Recall 和更多边界 case 留给 WP5 AgentEvalOps dataset，避免把人工 smoke 伪装成统计指标。

------

## Q10：Planning 为什么会随机 `REMOTE_OUTPUT_TRUNCATED`？

推荐答：

> Planner 的 output token budget 当时只有 512。相同输入每次生成长度存在波动，当 structured Plan 恰好超过 512 token 时就被 provider 截断，所以表现成概率失败。把 Planning output budget 调整到合理范围后解决。这个案例说明 token budget 也是 Runtime correctness contract，不只是成本参数。

------

# 39. 推荐完整面试回答

如果面试官问：

> 你的 Memory Formation 是怎么设计的？

可以这样答：

> 我先把 Formation 放在 canonical Run 的 post-delivery lifecycle 里，只有 OutputGate 已经确认 DELIVERED，并且 Conversation Exchange 成功 commit 后才触发，这样不会把中间结果或失败请求写成长期记忆。
>
> Formation 本身采用 hybrid 模式。代码先做 deterministic eligibility，然后通过统一 Model Invocation 让 LLM 输出严格结构化的候选，但 LLM 没有 mutation authority，它不能指定 memory_id、status、scope 或 lifecycle。LocalAgent 再做 parser、source grounding、category 和 Should Remember policy，只有明确来自 original user query 的稳定 preference、project fact、engineering constraint 或 long-term decision 才能落库。
>
> accepted candidate 会规范成 atomic Semantic Memory，由 LocalAgent 生成稳定 ID、provenance、ACTIVE 状态和 HYBRID formation method，再通过 AdvancedMemoryStore 做单 record transaction。Formation failure 和 cancellation 都与已经 delivered 的 final output 隔离，不会反向修改 Run terminal。
>
> 真实测试时我们冻结了四个 case：长期 uv 决策能形成 Memory、临时 pip 操作被忽略、SQLite→PostgreSQL correction 只新增 ACTIVE 而不提前 supersede、Assistant 自己推断的数据库不会被写入。四个 smoke case 全部符合预期。
>
> 另外真实实验中还发现 Planner 的 output token budget 只有 512，structured plan 有概率被截断成 `REMOTE_OUTPUT_TRUNCATED`。后来确认是输出 budget 不足并调整，这也是一次 Runtime reliability 的真实问题。

这段已经足够支撑连续追问。

------

# 40. 简历表述

当前 WP2 已经可以进入最终 Advanced Memory 项目 bullet。

推荐：

> 设计并实现 Semantic Memory Formation Pipeline，在 Coordinated Runtime 的 delivered-exchange 后执行 deterministic eligibility、LLM candidate extraction、source grounding 与 code-owned Should Remember Policy，将稳定用户偏好、项目事实和工程约束持久化为可追溯的 ACTIVE Semantic Memory；通过真实 smoke experiment 验证稳定事实形成、临时信息抑制、用户修正与 Assistant-only memory pollution 防护。

如果需要更偏工程：

> 实现 post-delivery Semantic Memory Formation，采用 LLM Candidate + deterministic policy 的 Hybrid 架构，限制 Model mutation authority，支持 source grounding、atomic multi-fact formation、same-execution idempotency、failure isolation 与 content-minimized observability，并完成真实模型链路验证。

------

# 41. 推荐面试材料文件名

按照你的规范：

```text
docs/interview/stage5_phase5_wp2_semantic_memory_formation.md
```

推荐标题：

> **Stage5-Phase5-WP2 — Semantic Memory Formation, Source Authority and Failure Isolation**

------

# WP2 最值得背下来的 10 句话

1. **Formation 只能发生在 Output 已 DELIVERED 且 Conversation Exchange 已 COMMITTED 之后。**
2. **LLM 只是 Candidate Producer，LocalAgent 才是 Memory Mutation Authority。**
3. **第一版只把 original user explicit assertion 当作 Semantic Memory 的事实来源。**
4. **Assistant、Tool、RAG 和第三方内容不能因为进入 Context 就自动升级成长期事实。**
5. **Should Remember 使用 deterministic eligibility + LLM proposal + code validation 的 Hybrid 策略。**
6. **Grounding 证明 candidate 来自用户真实输入，但 substring grounding 并不等于语义完全正确。**
7. **Formation failure 不能反向改变已经 delivered 的 final output 和 Run terminal。**
8. **同一次 execution 的 retry 必须复用 prepared record；cross-Run duplicate 和 NO_CHANGE 属于 WP3。**
9. **真实 F1～F4 smoke 验证了稳定事实形成、transient suppression、correction formation 和 assistant-only pollution suppression。**
10. **Planning output token 过小会直接造成 structured output correctness failure；512 token 导致过真实 `REMOTE_OUTPUT_TRUNCATED`，说明 token budget 是 Runtime contract 的一部分。**

WP2 真正值得学的并不是“怎么再调一次 LLM”，而是：

> **如何把一个概率型模型限制在 Candidate 层，用确定性的 Runtime Contract、Source Authority、Grounding、Failure Isolation 和 Persistence Boundary，把不可靠模型输出转化成可控、可追溯、可评测的长期 Memory。**