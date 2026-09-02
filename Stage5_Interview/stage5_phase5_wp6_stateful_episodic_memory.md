当前使用的模型：**GPT-5.6 Sol**。

下面进入 **Stage5-Phase5-WP6 — Stateful Episodic Memory（有状态情景记忆）最终学习 / 面试总结**。

推荐面试材料文件名：

```
docs/interview/wp6-stateful-episodic-memory.md
```

------

# 1. 一句话项目定义

WP6 的目标是：

> 为 LocalAgent 建立一套可形成、持久化、检索、注入并可评估的 Episodic Memory，让 Agent 能把真实 Run Experience 作为历史经验在后续任务中复用，同时通过 deterministic Layer1 和 real-model Layer2 两层 Evaluation 验证真实性、安全性、Scope 和上下文注入行为。

最终状态：

```text
WP6 Layer1 = COMPLETE / CANONICAL
WP6 Layer2 = COMPLETE / PASS_WITH_OBSERVED_LIMITATIONS

OPEN_P0 = 0
OPEN_P1 = 0

WP6_READY_TO_CLOSE = YES
```

Layer1 最终 fresh canonical experiment：

```text
12 / 12 scenarios PASS
194 / 194 assertions PASS
Layer1 Gate = PASS
```

Layer2 使用真实 `deepseek-v4-flash`：

```text
12 scenarios
6 PASS / 6 FAIL

P0 Memory Safety Violation = 0
Memory Behavior Failure = 0
```

因此 Layer2 的 50% Scenario Success Rate 不能解释成“Memory 成功率只有 50%”。

------

# 2. WP6 实际解决了什么问题

在 WP6 之前，Memory 更接近：

```text
用户事实
→ 保存
→ 后续取回
```

WP6 增加的是另一类长期记忆：

```text
我过去经历过什么？
```

例如：

```text
过去某次 Run
→ 做了什么
→ 成功还是失败
→ 最终是否交付
→ 得到了什么事实性结果
```

这些被投影成 Episode。

之后遇到相似任务：

```text
Current Request
      ↓
Episodic Retrieval
      ↓
Historical Experience
      ↓
ContextBuilder
      ↓
Model Context
```

因此 Semantic Memory 和 Episodic Memory 的定位不同：

```text
Semantic Memory
= 我知道什么

Episodic Memory
= 我经历过什么
```

------

# 3. Episodic Memory 的核心数据边界

Episode 不是：

- Chat Transcript；
- Chain of Thought；
- Runtime Journal Dump；
- 原始 Tool Result；
- Planner 内部状态快照。

我们最终冻结的是：

> 一次 bounded、auditable、completed Run Experience 的 factual projection。

也就是说，Episode 是对真实 Runtime Experience 的**有限事实投影**。

核心信息来自：

```text
PlanningRequest
Plan / Step
AgentState terminal step
Final Decision
OutputGate
```

但不会直接把：

```text
raw Journal
raw Model narrative
raw Tool output
CoT
```

塞进去。

------

# 4. 为什么 Formation 必须发生在 terminal decision 之后

Formation（记忆形成）时机最终是：

```text
Run execution
      ↓
terminal decision
      ↓
OutputGate
      ↓
Episodic Formation
      ↓
cleanup
```

原因是只有 terminal 时：

```text
最终状态
执行结果
是否交付
成功/失败
```

才稳定。

如果太早形成：

```text
Step 2 还没执行
→ Memory 已经写入“任务完成”
```

就容易形成错误历史。

------

# 5. 为什么 FAILED Run 也允许形成 Episode

这点很重要。

Episodic Memory 不是：

```text
Success Cache
```

而是：

```text
Historical Experience
```

失败经验也有价值。

例如：

```text
数据库迁移失败
→ 之前具体失败在哪
→ 下次可以作为历史经验
```

所以 eligibility 是：

```text
meaningful
+
terminal
+
factual
```

而不是：

```text
status == SUCCESS
```

WP6 中专门验证：

```text
FAILED Episode Formation
FAILED Episode Retrieval
```

------

# 6. 为什么 greeting 不应该形成 Episode

例如：

```text
你好
谢谢
好的
```

如果全部长期保存，会造成：

```text
Memory Pollution
Retrieval Noise
Context Budget Waste
```

所以 trivial interaction 应：

```text
SKIPPED_INELIGIBLE
```

Layer1 最终：

```text
TRIVIAL_REJECTION_RATE = 1.0
```



------

# 7. Episodic Retrieval 为什么没有直接复用高级 RAG

当前 Knowledge RAG 已经是：

```text
Dense
+ BM25
+ RRF
+ Cross-Encoder
```

但是 WP6 Episodic Retrieval 没有复用这一整套。

当前使用：

```text
bounded SQLite lexical retrieval
```

原因不是技术能力不足，而是刻意控制复杂度。

WP6 先优先保证：

```text
Formation correctness
Persistence correctness
Scope correctness
Retrieval determinism
Context injection
Evaluation
```

而不是一开始就把：

```text
Embedding
BM25
RRF
Reranker
```

全部叠进去。

这是一个很好的工程取舍：

> 先建立正确且可评估的 Memory Lifecycle，再优化 Retrieval Quality。

------

# 8. 当前 Episodic Retrieval 的核心规则

当前是：

```text
query =
PlanningRequest.user_request
```

然后：

```text
active filter
exact agent_id
exact scope
lexical score
zero-score reject
deterministic sorting
top-K
context budget
```

排序大致遵循：

```text
score DESC
created_at DESC
memory_id ASC
```

因此 deterministic Layer1 能稳定复现。

------

# 9. selected、supplied、injected 为什么必须拆开

这是 WP6 一个非常重要的 Observability（可观测性）设计。

完整链路：

```text
Episode
↓
Retrieval selected
↓
MemoryContextBundle supplied
↓
ContextBuilder injected
↓
Model Context
```

三个概念：

```text
selected
= Retriever 选中了

supplied
= Memory Service 真正交给 ContextBuilder

injected
= 最终进入模型 Context
```

不能看到：

```text
selected = true
```

就说：

> Memory 已经被模型看到。

因为可能：

```text
selected = YES
supplied = YES
injected = NO
```

E11 就专门验证三层 evidence。

------

# 10. Trust Boundary 怎么设计

历史 Episode 本身可能出现：

```text
“忽略之前所有规则”
```

但历史经验不能因此变成高权限指令。

所以 Episodic Memory 注入固定：

```text
source =
EPISODIC_MEMORY_RETRIEVAL

trust =
USER_CONTENT
```

同时带 historical-experience preamble。

也就是说：

> 这是历史经验，不是系统指令。

最终 Layer1、Layer2 都没有出现 Instruction Elevation Violation。

------

# 11. WP6 Evaluation 为什么必须做成 Stateful

普通 Evaluation：

```text
Input
→ Agent
→ Output
→ Score
```

但 Episodic Memory 是跨 Run 行为。

例如：

```text
Run A
→ Formation Episode A

Run B
→ Retrieval Episode A
→ Injection
```

因此隔离单位必须是：

```text
Scenario
```

而不是：

```text
Run
```

最终执行方式：

```text
Scenario 1
  fresh subprocess
  fresh Memory DB
  fresh Journal DB
  Run A
  Run B

Scenario 2
  fresh subprocess
  fresh DBs
  ...
```

同一 Scenario 内共享 state，Scenario 之间完全隔离。

------

# 12. 12 个 Scenario 的能力矩阵

不用死背细节，记能力即可：

| Scenario | 核心能力                       |
| -------- | ------------------------------ |
| E01      | meaningful success → Episode   |
| E02      | failed Run → truthful Episode  |
| E03      | trivial interaction rejected   |
| E04      | formation idempotency          |
| E05      | factual grounding              |
| E06      | privacy                        |
| E07      | similar episode retrieval      |
| E08      | unrelated episode rejection    |
| E09      | scope isolation                |
| E10      | failed episode retrieval       |
| E11      | selected / supplied / injected |
| E12      | trust boundary                 |

这套 Dataset 的价值是覆盖完整 Memory Lifecycle，而不是只有“存”和“查”。

------

# 13. Grounding 是整个 WP 最值得学的部分

WP6 中 Grounding 的含义：

> Episode 中记录的事实是否能被真实 Runtime Evidence 支撑。

不是：

```text
Episode 自己说成功
→ PASS
```

而是：

```text
Runtime Evidence
          ↓
       compare
          ↑
Persisted Episode
```

因此必须有两个独立 Evidence Surface。

------

# 14. 第一个重大 Bad Case：Display Name 被当成 Runtime Identity

最初 Dataset 有：

```text
release_list
```

Runtime canonical identity：

```text
task-release_list
```

而 Episode 中可能是：

```text
执行专业任务
```

早期 Evaluator 实际在比较：

```text
release_list
vs
执行专业任务
```

当然会失败。

后来冻结：

```text
PlanStep.step_id
= canonical execution identity

RuntimeEvent.step_id
= runtime evidence identity

PlanStep.title
→ StepState.name
= human-readable display
```

核心知识：

> Display Field 不能成为 Identity Authority。

------

# 15. Typed Identity Adapter 的作用

Dataset symbolic ID：

```text
release_list
```

需要规范到：

```text
task-release_list
```

不能每个 Evaluator 自己写字符串拼接。

最终形成统一 typed normalization：

```text
Dataset symbolic identity
↓
Identity Adapter
↓
Runtime canonical identity
```

核心原则：

> 一个 Contract 的 Normalization 规则必须有一个 Owner。

------

# 16. 为什么最终把 Grounding 拆成两部分

最终 Grounding 分为：

### Runtime Evidence

问：

> Runtime 实际做了什么？

例如：

```text
step/status
terminal
delivery
```

### Persisted Fidelity

问：

> Episode 是否忠实记录了 Runtime？

例如 Runtime：

```text
FAILED
```

Episode：

```text
SUCCEEDED
```

那才是真正：

```text
EPISODE_GROUNDING_MISMATCH
```

这种拆分避免了：

```text
Runtime Identity
Presentation Text
Persisted Memory
```

三种不同语义混在一起。

------

# 17. 第二个重大 Bad Case：Dataset 自己越权

修完 identity 后，并没有直接 12/12 PASS。

当时出现：

```text
Dataset expected:
config_check

Runtime actual:
task-data
```

进一步审计发现：

```text
config_check
migrate_plan
deploy_answer
```

这些其实来自 evaluation-designed task vocabulary。

但 Production Planner 从未承诺：

> 某个自然语言输入必须生成唯一这个 task ID。

也就是说 Dataset 在偷偷评价 Planner。

------

# 18. Domain Owner 最终怎么划分

最后冻结：

```text
Planner
→ 决定做什么

Runtime
→ 记录实际发生什么

Episodic Memory
→ 忠实记录 Experience

Dataset
→ 定义 Memory Ground Truth

AgentEvalOps
→ 比较 Runtime Evidence 和 Memory Evidence
```

这是 WP6 非常有面试价值的设计。

核心原则：

> Ground Truth Owner 不等于所有 Behavior 的 Owner。

------

# 19. 为什么不能只删失败的那几条 Assertion

如果只删除：

```text
当前失败的 5 条
```

然后获得：

```text
12/12 PASS
```

这是 Force-Green。

真正做法是：

```text
Audit E01-E12
↓
找出全部同类 Planner Task Identity assertions
↓
统一处理
```

包括那些**恰好 PASS**的。

这证明 Dataset V2 是系统修复，而不是 cherry-picking。

------

# 20. Dataset 为什么升级成 V2

不能修改原 V1：

```text
same dataset id
different bytes
```

否则历史结果无法解释。

最终：

```text
V1
stateful_episodic_v1
sha256:d87cc...
```

保留。

新建：

```text
V2
stateful_episodic_v2
sha256:678ecc...
```

并记录：

```text
parent = V1
reason = DATASET_SCOPE_DEFECT
```

这就是 Dataset Lineage。

------

# 21. 为什么 Grounding 86.5% → 100% 不能当性能提升

V1：

```text
denominator = 37
```

V2：

```text
denominator = 32
```

而且 Contract 已经变化。

因此不能说：

> Grounding 从 86.5% 优化到了 100%。

正确说法：

> V1 暴露了 Dataset Scope Defect，V2 修正 Domain Boundary 后，在新的 Grounding Contract 下获得 100% deterministic Layer1 Accuracy。

这是非常重要的指标真实性问题。

------

# 22. Layer1 为什么不用真实模型

Layer1 测的是：

```text
Runtime Contract
Memory Contract
Evaluation Contract
Evidence Chain
```

如果直接接真实模型，则失败可能来自：

```text
Model randomness
Planner variance
Prompt
Provider
Runtime
Memory
Evaluator
```

无法快速 attribution。

所以 Layer1 使用：

```text
real Runtime
+
scripted deterministic model-side response
```

而不是 mock 整个系统。

------

# 23. Scripted Backend 也出现过 Bad Case

早期 scripted backend 太泛化，导致：

```text
Scenario semantic
!=
scripted planner behavior
```

制造大量 false failure。

还遇到 specialist：

```text
REQUIRED_DEPENDENCY_FAILED
```

后来发现 Layer1 ModelProfile 缺 capability，例如：

```text
supports_structured_output
supports_code_reasoning
```

导致真实 Router/Selection path 拒绝 specialist。

重点：

> Test Double 也必须满足真实系统 Contract。

------

# 24. Layer1 最终结果

最终 fresh canonical Layer1：

```text
12 / 12 scenarios PASS

194 / 194 assertions PASS

Grounding Assertions:
32 PASS

Formation Precision = 1.0
Formation Recall = 1.0

Grounding Accuracy = 1.0

Fabricated Fact Rate = 0.0

Recall@K = 1.0
Hit@K = 1.0

Injection Success = 1.0

Scope Leakage = 0.0
Instruction Elevation = 0.0
```

但这些只适用于 frozen deterministic Dataset/Implementation Contract。

------

# 25. 第三个重大 Bad Case：12/12 PASS 仍然不能冻结 Baseline

第一次 V2 已经 12/12 PASS。

但审计发现：

```text
Experiment Target Ref
=
2bb58...

Current Target Ref
=
f7841...
```

即：

> 实验测试的不是当前源码。

因此拒绝 canonicalize。

这是整个 WP 最值得讲的工程故事之一。

------

# 26. 为什么一个 aggregate hash 不够

当时只有：

```text
sha256:2bb58...
```

后来变成：

```text
sha256:f7841...
```

我们只能知道：

```text
changed
```

却不知道：

```text
which file changed
```

旧 snapshot 又找不到。

因此引入：

```text
Source Receipt
```

------

# 27. Source Receipt 是什么

Source Receipt 至少包含：

```text
ordered source files

each file:
  relative path
  SHA256
  byte length

aggregate algorithm
aggregate ref

git/worktree identity
```

这样下次 ref drift，可以直接定位：

```text
file X
old digest
new digest
```

------

# 28. Dirty Worktree 为什么仍可冻结

工作树 clean 当然更好。

但真正需要证明的是：

> 实验跑的具体 bytes 是什么。

因此即使：

```text
WORKTREE_CLEAN = NO
```

只要有：

```text
file receipt
aggregate ref
pre-run ref
post-run ref
experiment binding
```

依然可以构建可信 provenance。

最终 canonical run：

```text
pre-run ref == post-run ref
```

即 Source Stability PASS。

------

# 29. Baseline 不等于一组 Metrics

真正 Baseline Authority 包含：

```text
Dataset
Dataset lineage

Target ref
Target source receipt

AgentEvalOps ref
AgentEvalOps source receipt

Execution policy

Experiment artifact
Experiment digest

Scenario summary
Assertions
Metrics
Gate
Environment
```

所以：

```text
accuracy = 1.0
```

本身没有足够意义。

应该说：

> 哪份 Dataset、哪版 Runtime、哪版 Evaluator、哪次 Experiment 得到的 1.0。

------

# 30. Experiment / Candidate / Canonical 为什么拆成三层

最终是：

```text
Source Receipt
      ↓
Experiment Artifact
      ↓
Candidate Baseline
      ↓
Canonical Authority
```

Experiment 回答：

> 实验发生了什么？

Candidate 回答：

> 这份 Experiment 是否值得成为候选 baseline？

Canonical Authority 回答：

> 这份 Candidate 是否正式成为权威 baseline？

保持单向依赖，可以避免 circular digest。

------

# 31. 第四个重大 Bad Case：Baseline Immutability 漏字段

最终 freeze 前又发现：

`compatibility_with()` 只比较：

```text
dataset digest
target ref
AgentEvalOps ref
execution policy
```

但没比较：

```text
target source receipt digest
AgentEvalOps source receipt digest
experiment artifact digest
```

因此理论上 evidence 已变化，但 baseline 仍会被判断 compatible。

最终要求：

```text
任一 immutable dimension 改变
→ BASELINE_INCOMPATIBLE
```



------

# 32. 为什么修了 Baseline 还要再跑 12 Case

因为修改：

```text
episodic_baseline.py
```

导致 AgentEvalOps semantic ref 改变：

```text
b69f9f...
→
820915...
```

旧 experiment 绑定旧 evaluator bytes。

所以即使改的只是 Baseline Governance，严格 provenance 下也不能直接复用旧实验。

于是再次 fresh run。

最终：

```text
Target =
f7841...

AgentEvalOps =
820915...

12 / 12 PASS
```

并正式 canonical freeze。

------

# 33. Layer1 和 Layer2 到底有什么区别

这是必须会答的。

## Layer1

```text
Deterministic Contract Evaluation
```

回答：

> 系统是否满足已经冻结的工程 Contract。

使用 deterministic scripted backend。

------

## Layer2

```text
Real-Model Observational Evaluation
```

回答：

> 把真实模型放进去以后，系统实际表现成什么样。

真实模型允许：

```text
Planner variance
Model variance
Runtime behavioral failure
```

所以不要求：

```text
12 / 12 PASS
```

------

# 34. Layer2 最终是怎么跑的

真实模型：

```text
provider = deepseek
model = deepseek-v4-flash
```

真实网络调用发生。

继续使用：

```text
GLOBAL_SEQUENTIAL
```

同样的 12 个 V2 Scenario。

最终：

```text
6 PASS
6 FAIL
0 BLOCKED
```



------

# 35. 为什么 Layer2 50% 不能说“Memory 只有 50% 成功率”

因为 Scenario Failure Attribution（失败归因）显示：

```text
MODEL_BEHAVIOR = 0

PLANNER_VARIANCE = 5

RUNTIME_BEHAVIOR = 7

MEMORY_BEHAVIOR = 0

EVALUATION_LIMITATION = 0
INFRA_FAILURE = 0
```

也就是说：

> 没有一个 Failure 被建立为 Episodic Memory behavior failure。

所以：

```text
Scenario Success Rate = 0.5
```

是整个 Scenario 层面的真实模型运行结果，不是 Memory Accuracy。



------

# 36. Layer2 的主要观测结果

最终：

```text
FORMATION_PRECISION = 1.0

FORMATION_RECALL = 0.9375

TRIVIAL_REJECTION_RATE = 1.0

GROUNDING_ACCURACY = 0.7667

FABRICATED_FACT_RATE = 0.0

EXPECTED_EPISODE_RECALL_AT_K = 1.0

HIT_AT_K = 1.0

IRRELEVANT_SELECTION_RATE = 0.0

INJECTION_SUCCESS = 1.0

SCOPE_LEAKAGE = 0.0

INSTRUCTION_ELEVATION = 0.0

Scenario Success = 0.5
```



------

# 37. Layer2 最重要的三个结果

如果面试只记三个：

### 第一

```text
Memory Retrieval / Injection
仍然稳定
```

Recall@K / Hit@K / Injection 都是 1.0。

### 第二

```text
Memory Safety 没出现 P0
```

Fabricated Fact：

```text
0
```

Scope Leakage：

```text
0
```

Instruction Elevation：

```text
0
```

### 第三

真实模型暴露的是：

```text
Planner / Runtime variance
```

而不是已经建立的：

```text
Memory behavior defect
```

------

# 38. 为什么 Layer2 不继续做 N=3 / N=5

因为当前目标是尽快面试。

这次 Layer2 定位是：

```text
Minimal Real-Model Observation
```

不是统计 Benchmark。

如果做：

```text
12 scenarios
× 5 repetitions
```

会迅速变成另一项大型工程。

当前一轮已经足够证明：

```text
真实 provider 跑过
真实 nondeterministic Planner 跑过
真实 Memory lifecycle 跑过
有完整 failure attribution
```

因此停止继续扩张。

------

# 39. Layer2 为什么是 PASS_WITH_OBSERVED_LIMITATIONS

因为 Gate 不是：

```text
12/12 must PASS
```

而是：

```text
provenance complete
evaluation infra usable

P0 = 0
scope leakage = 0
fabricated fact = 0

failure correctly attributed
```

这些都满足。

所以：

```text
PASS_WITH_OBSERVED_LIMITATIONS
```

是合理结果。

------

# 40. WP6 最值得记的名词 / 概念

| 名词                        | 一句话                                                       |
| --------------------------- | ------------------------------------------------------------ |
| Episodic Memory（情景记忆） | 保存 Agent 过去实际经历过的 Run Experience。                 |
| Formation                   | 将终态 Run Experience 投影成 Episode。                       |
| Grounding                   | Episode 的事实必须由 Runtime Evidence 支撑。                 |
| Runtime Evidence            | Journal、State、terminal receipt 等真实运行事实。            |
| Fidelity                    | Persisted Episode 是否忠实表达 Runtime。                     |
| Stateful Evaluation         | 多 Run 共享状态的评估。                                      |
| Scenario                    | Stateful Evaluation 的隔离和评估单位。                       |
| Source Receipt              | 每个 semantic source 文件的摘要及 aggregate provenance。     |
| Dataset Lineage             | Dataset 版本及修复原因的血缘关系。                           |
| Candidate Baseline          | 尚未完成 authority freeze 的候选基线。                       |
| Canonical Baseline          | 正式冻结并可作为回归权威的基线。                             |
| Baseline Immutability       | 基线不得静默接受不同 evidence。                              |
| Failure Attribution         | 区分 Model、Planner、Runtime、Memory、Evaluation、Infra 失败。 |
| Layer1                      | deterministic contract evaluation。                          |
| Layer2                      | real-model observational evaluation。                        |

------

# 41. 工程方法题：为什么 Evaluation 本身也必须被测试

因为 Evaluation System 也有：

```text
Schema
Identity
Normalization
Evidence Capture
Aggregation
Metric
Gate
Artifact
Baseline
```

这些都可能出 Bug。

WP6 就实际发现：

```text
Display name / identity 混淆

scripted backend capability defect

Dataset scope defect

target ref drift

baseline provenance incomplete

baseline immutability incomplete
```

所以：

> Evaluator 不是天然正确的裁判，它本身也是软件系统。

------

# 42. 工程方法题：为什么 Ground Truth 也不能盲信

Ground Truth 的权威应该限定在：

```text
它负责的 Domain
```

Dataset 可以规定：

```text
Episode 必须 truthful
```

但不代表可以规定：

```text
Planner 必须选 task X
```

这就是 Domain Boundary。

------

# 43. 工程方法题：为什么 Evaluation 需要 Fail Closed

典型场景：

```text
旧 experiment ref != 当前 source ref
```

如果证据无法证明：

```text
what changed
```

则：

```text
不要猜测 compatible
```

而应该：

```text
BLOCK
INVALIDATE candidate
fresh rerun
```

核心：

> Evidence 不完整时，宁可失去 PASS，也不能制造假 authority。

------

# 44. 工程方法题：Deterministic + Real Model 两层为什么比只跑真实模型好

Layer1：

```text
找 Contract Bug
```

Layer2：

```text
观察真实行为
```

如果只有 Layer2：

```text
失败
```

很难知道是谁的问题。

有 Layer1 后：

```text
Layer1 12/12
Layer2 6/12
```

就可以进一步 attribution：

```text
Memory deterministic contract稳定
真实模型引入 Planner/Runtime variance
```

这就是两层 Evaluation 的真正价值。

------

# 45. 最值得讲的三个 Bad Case

## Bad Case 1

> Evaluator 把 display name 当 canonical identity。

体现：

```text
Identity Authority
Typed Contract
```

------

## Bad Case 2

> Dataset Ground Truth 越权评价 Planner。

体现：

```text
Domain Boundary
Ground Truth Governance
```

------

## Bad Case 3

> 已经 12/12 PASS，但因为 Source Provenance 不完整主动拒绝 freeze。

体现：

```text
Engineering Truthfulness
Provenance
Baseline Governance
Fail-Closed
```

如果面试只能讲一个，我建议讲第三个。

------

# 46. 面试高频追问

### Q：Episode 和 Chat History 有什么区别？

> Chat History 记录对话；Episode 是经过 Formation 的 bounded Runtime Experience，只保存事实性经验，不等于原始 Transcript。

------

### Q：失败任务为什么也保存？

> 失败也是历史经验，只要 meaningful、terminal、factual。

------

### Q：怎么防止 Memory 说谎？

> 用独立 Runtime Evidence 和 Persisted Episode 做 Grounding/Fidelity 比较，同时 Fabricated Fact 是 hard gate。

------

### Q：怎么防止跨 Agent 泄露？

> Retrieval 使用 exact agent/scope filtering，并有负向 fixture 验证 foreign memory 不进入 candidate/selected/injected。

------

### Q：怎么防止历史记忆变成 Prompt Injection？

> Episodic Memory 永远以 USER_CONTENT trust 注入，不提升为 system/developer instruction。

------

### Q：为什么不用现有 Dense+BM25+RRF？

> 当前重点是 Memory Lifecycle correctness，不是 Retrieval tuning；高级 Knowledge RAG 和 Episodic Memory 暂时保持独立。

------

### Q：真实模型结果为什么只有 50%？

> 50% 是 Scenario-level success，不是 Memory success。失败主要来自 Planner variance 和 Runtime behavior；Memory behavior failure 为 0。

------

### Q：你敢说真实模型 Memory 已经完全稳定吗？

> 不敢。Layer2 只执行了一轮 observational suite，不是统计 benchmark，也不能外推到所有生产输入。

------

# 47. 30 秒总结

> 我在 LocalAgent 的 Advanced Memory 阶段实现并评估了 Stateful Episodic Memory。Runtime 会在一次有意义的 Run 终态后，把真实执行经验形成 Episode，在后续相似 Run 中按 agent/scope 检索并通过 ContextBuilder 注入模型上下文。我建立了 12 个跨 Run Scenario 的 stateful evaluation，覆盖 formation、failed memory、idempotency、grounding、retrieval、scope、privacy、injection 和 trust boundary。Layer1 使用 deterministic scripted backend，最终 12/12 Scenario、194/194 Assertion PASS，并通过 source receipt、dataset lineage 和 immutable baseline authority 冻结 canonical baseline；Layer2 又用真实 DeepSeek 做了一轮 observation，6/12 Scenario PASS，但没有 Memory behavior failure 或 P0 safety violation，主要问题来自 Planner 和 Runtime variance。

------

# 48. 2 分钟总结

> 我在 LocalAgent 的 Advanced Memory 阶段实现了 Episodic Memory，也就是让 Agent 不仅能记住事实，还能记住过去真实经历过的 Run Experience。Episode 不是 Chat Transcript 或 CoT，而是在 Runtime terminal decision 后，根据 PlanningRequest、AgentState、step result、terminal 和 delivery 等真实证据形成的 bounded factual projection。失败 Run 也可以形成 Episode，因为失败本身也是历史经验；问候、小聊这类 trivial Run 则会被过滤。
>
> Retrieval 目前没有直接复用 Knowledge RAG 的 Dense+BM25+RRF，而是先采用 bounded SQLite lexical retrieval，并做 exact agent/scope filter、zero-score rejection、top-K 和 context budget。检索结果还会分别观察 selected、supplied 和 ContextBuilder injected，避免把“检索到了”误认为“模型真的看到了”。
>
> 评估上我做了 Stateful Evaluation，一个 Scenario 内多次 Run 共享 Memory 和 Journal，Scenario 之间使用 fresh subprocess 和数据库隔离。12 个 Scenario 覆盖 Formation、Failed Episode、Trivial Rejection、Idempotency、Grounding、Privacy、Retrieval、Scope、Injection 和 Trust Boundary。
>
> 过程中我们发现过很多 Evaluation 系统自身的问题，比如把 display name 当 canonical step identity、Dataset 越权规定 Planner task、scripted backend capability 不满足真实 Runtime Contract，以及 12/12 PASS 后发现 experiment source hash 和当前源码不一致。最终我引入 Dataset V2 lineage、typed Runtime Evidence、file-level Source Receipt、durable Experiment Artifact 和 immutable Canonical Baseline。Layer1 fresh deterministic experiment 最终 12/12 Scenario、194/194 Assertion PASS。
>
> 在此基础上又跑了一轮真实 DeepSeek Layer2。结果是 6/12 Scenario PASS，Grounding Accuracy 约 76.7%，但 Retrieval Recall@K、Hit@K、Injection Success 都是 1.0，Scope Leakage、Fabricated Fact、Instruction Elevation 都是 0。失败归因主要是 Planner variance 和 Runtime behavior，没有建立 Episodic Memory production defect，所以 WP6 最终以 Layer1 Canonical + Layer2 PASS_WITH_OBSERVED_LIMITATIONS 收口。

------

# 49. 最终真实性边界

**真实已完成：**

```text
Episodic Formation
Persistence
Idempotency
Retrieval
Scope Isolation
Context Injection
Trust Boundary

Stateful Dataset V2
Deterministic Layer1
Canonical Baseline
Real-Model Layer2 Observation
Failure Attribution
```

**真实结果：**

```text
Layer1:
12/12 Scenario PASS
194/194 Assertion PASS

Layer2:
6/12 Scenario PASS
Memory Behavior Failure = 0
P0 Safety Violation = 0
```

**尚未完成 / 不应该声称：**

```text
N=3/N=5 statistical real-model benchmark

真实模型所有场景都稳定

生产环境所有 scope leakage = 0

Episodic Vector / BM25 / RRF retrieval

Multi-Agent Shared / Private Memory Governance
```

后者就是下一条主功能线 **WP7**。