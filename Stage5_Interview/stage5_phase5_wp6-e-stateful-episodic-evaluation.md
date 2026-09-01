当前使用的模型：**GPT-5.6 Sol**。

下面进入 **Stage5-Phase5-WP6-E — Stateful Episodic Evaluation（有状态情景记忆评估）** 的学习 / 面试总结。推荐面试材料文件名：

```
docs/interview/wp6-e-stateful-episodic-evaluation.md
```

这次 WP 很适合作为面试重点，因为最后真正有价值的并不是“12/12 测试通过”，而是我们围绕 **Evaluation Contract（评估合同）、Ground Truth（真值）、Runtime Evidence（运行时证据）、Provenance（来源证明）和 Baseline（基线）** 连续发现并修掉了一整串评估系统自身的错误。

------

# 1. 一句话定义这个 WP

WP6-E 的目标是：

> **为 LocalAgent 的 Episodic Memory（情景记忆）建立一个 deterministic、stateful、可审计的 Layer1 Evaluation，用真实 Runtime evidence 验证 Episode Formation、Grounding、Retrieval、Scope、Injection 和 Trust Boundary，并最终冻结一个可复现、带完整 provenance 的 canonical baseline。**

最终：

```text
WP6_E_LAYER1_STATUS = COMPLETE
BASELINE_STATUS = CANONICAL

OPEN_P0 = 0
OPEN_P1 = 0

12 / 12 scenarios PASS
194 / 194 assertions PASS

Layer1 Gate = PASS
```

最终 canonical authority 是针对：

```text
Dataset:
stateful_episodic_v2

LocalAgent Target:
sha256:f7841bd8...

AgentEvalOps:
sha256:820915cc...

Execution:
GLOBAL_SEQUENTIAL

Baseline:
WP6_STATEFUL_EPISODIC_BASELINE_V2_R3
```

冻结的。

------

# 2. 这个 WP 到底在评价什么

先理解一个非常重要的边界。

WP6-E 不是在评价：

> “LLM 回答好不好？”

而是在评价：

> “一次 Run 结束后形成的 Episode，是否真实、正确、隔离、安全地表达了实际 Runtime Experience，并能在后续 Run 中正确被检索和注入。”

因此整个链路是：

```text
Run A
│
├─ Planner / Runtime executes
│
├─ AgentState / Journal records facts
│
├─ terminal decision
│
└─ Episodic Formation
       ↓
   Episode persisted
       ↓
Run B
       ↓
MemoryRetrievalService
       ↓
selected
       ↓
supplied
       ↓
ContextBuilder injected
       ↓
model-visible historical context
```

WP6-E 要在这条链的多个位置同时取证。

这也是为什么它必须是 **stateful evaluation**，而不是一个简单的：

```text
input → output → compare
```

测试。

------

# 3. 为什么叫 Stateful Evaluation

普通 Evaluation 可能是：

```text
Question
↓
Agent
↓
Answer
↓
Evaluator
```

一个 Case 相互独立。

而 Episodic Memory 天然依赖历史状态。

例如 E07：

```text
Run A
→ 产生 Episode A

Run B
→ 必须能检索 Episode A
```

因此正确隔离单位不是：

```text
每个 Run fresh DB
```

而是：

```text
每个 Scenario fresh environment

Scenario 内：
Run A / Run B
共享 Memory DB
共享 Journal DB
共享 Runtime subprocess
```

Scenario 与 Scenario 之间则必须隔离。

最终我们冻结的是：

```text
GLOBAL_SEQUENTIAL

Scenario 1
  fresh subprocess
  fresh DB
  Run A
  Run B

Scenario 2
  completely fresh environment
```

这样既保留同 Scenario 的 memory state，又避免跨 Scenario 污染。

------

# 4. WP6-E 的 12 个 Scenario 到底测什么

这 12 个 Scenario 不建议死背 Case 内容，而应该记住覆盖矩阵：

| Scenario | 核心能力                                       |
| -------- | ---------------------------------------------- |
| E01      | meaningful successful Run 能形成 Episode       |
| E02      | failed Run 也能形成 truthful Episode           |
| E03      | greeting / trivial Run 不应形成 Episode        |
| E04      | 同 origin Run replay 必须幂等                  |
| E05      | Episode factual grounding                      |
| E06      | privacy / sensitive content 不应泄露           |
| E07      | 相似历史 Episode 能被后续 Run 检索             |
| E08      | 无关 Episode 应 zero-score reject              |
| E09      | agent / scope isolation                        |
| E10      | FAILED Episode 仍可作为真实历史被检索          |
| E11      | selected / supplied / injected 三层证据        |
| E12      | historical content 只能保持 USER_CONTENT trust |

这里尤其要记住 E11。

我们后来明确冻结：

```text
selected != supplied != injected
```

因为：

```text
selected
= Retrieval Service选中了什么

supplied
= MemoryContextBundle真正提供了什么

injected
= ContextBuilder最终真正塞进model context什么
```

如果只看到 `selected=YES` 就声称“记忆成功注入模型”，这是典型的 evaluation false positive。

------

# 5. 名词 / 概念速览

这一节是面试前快速复习用的。

| 名词                                  | 一句话理解                                                   |
| ------------------------------------- | ------------------------------------------------------------ |
| Episodic Memory（情景记忆）           | 保存 Agent 过去实际经历过的、带边界的 Run experience。       |
| Stateful Evaluation（有状态评估）     | 多个执行步骤共享状态，后续行为依赖此前状态的评估方式。       |
| Ground Truth（真值）                  | Dataset 声明的预期行为，但它必须受到真实 Domain Owner 边界约束。 |
| Runtime Evidence（运行时证据）        | Journal、receipt、AgentState 等能够证明 Runtime 实际发生了什么的事实。 |
| Grounding（事实对齐）                 | 验证持久化 Episode 中的事实是否由真实 Runtime evidence 支撑。 |
| Canonical Identity（规范身份）        | Runtime 中用于唯一标识某个实体的正式 identity，例如 `PlanStep.step_id`。 |
| Display Name（展示名称）              | 给人看的描述，例如 `执行专业任务`，不能替代 canonical identity。 |
| Provenance（来源证明）                | 证明某个实验究竟基于哪份 Dataset、哪版 Target、哪版 Evaluator。 |
| Source Receipt（源码收据）            | 保存 semantic manifest 中每个文件的 digest 和最终 aggregate ref。 |
| Baseline（基线）                      | 在固定 Dataset、代码版本、执行策略下冻结的一组权威 Evaluation 结果。 |
| Canonical Baseline（权威基线）        | 通过 provenance、immutability 和 Gate 审计后正式冻结的 baseline。 |
| Candidate Baseline（候选基线）        | 已有实验结果，但还未满足 canonical authority 的 baseline。   |
| Baseline Immutability（基线不可变性） | 同一个 baseline 不允许静默接受不同 Dataset、代码或 experiment evidence。 |
| Fail Closed（失败关闭）               | 证据不充分时宁可 BLOCK / FAIL，也不能猜测为 PASS。           |
| Layer1                                | deterministic scripted backend，用于验证 Evaluation / Runtime contract。 |
| Layer2                                | real-model observational evaluation，用真实模型观察效果，目前未运行。 |

------

# 6. 最值得理解的第一个问题：Grounding 到底是谁和谁比较

我们最早犯过一个非常典型的错误：

Dataset：

```text
release_list
```

Runtime canonical step：

```text
task-release_list
```

而 Episode 中的人类可读 observation：

```text
执行专业任务
```

Evaluator 最初做的是：

```text
release_list
vs
执行专业任务
```

于是全部失败。

问题不是 Runtime，也不是 Memory。

问题是：

> **把 presentation identity 当成 canonical identity。**

后来 Codex 审计明确：

```text
PlanStep.step_id
= canonical Runtime identity

StepState.step_id
= 同一 canonical identity

RuntimeEvent.step_id
= Journal canonical identity

PlanStep.title
→ StepState.name
= human-readable display name
```

所以：

```text
task-release_list
```

和：

```text
执行专业任务
```

根本不是同一个语义维度。

------

# 7. 为什么最后必须把 Grounding 拆成两种

这是本 WP 最重要的设计点之一。

最终我们把 Grounding 拆成：

```text
Runtime Identity / Fact Grounding
```

以及：

```text
Persisted Observation Fidelity
```

第一类问：

> Dataset 声明的 Runtime fact 在实际 Runtime 中是否真的发生？

例如：

```text
expected:
release_list SUCCEEDED

normalize:
task-release_list

Journal:
task-release_list SUCCEEDED
```

PASS。

第二类问：

> Episode 是否如实描述实际发生的 Runtime experience？

例如 Runtime：

```text
step status = FAILED
terminal = FAILED
delivery = NOT_DELIVERED
```

Episode：

```text
FAILED
NOT_DELIVERED
```

PASS。

如果 Episode 写：

```text
SUCCEEDED
DELIVERED
```

才是 Memory Grounding Failure。

这两个判断不能混在一起。

------

# 8. Typed Identity Adapter 为什么比字符串拼接好

Evaluator 不能到处写：

```python
"task-" + expected
```

因为 `"task-"` 本身也是一个 Contract。

最终我们增加统一的 typed adapter：

```text
Dataset symbolic identity
release_list

↓ normalize

canonical Runtime identity
task-release_list
```

由一个 owner 负责。

核心原则：

> **Normalization 规则只能有一个 Owner。**

否则以后可能出现：

```text
Evaluator A: task-{id}
Evaluator B: specialist-{id}
Runtime: task-{id}
```

测试各自都能跑，但系统 Contract 已经分叉。

这其实是非常典型的生产级 Evaluation Engineering 问题。

------

# 9. 第二个大坑：Dataset 也可能是错的

修完 identity evaluator 后，Layer1 仍然只有：

```text
8 / 12 PASS
```

当时出现：

```text
Dataset expected:
config_check

Runtime actual:
task-data
```

一开始很容易认为：

> Planner 错了。

但进一步审计发现：

```text
task-data
```

是 LocalAgent 当前 deterministic planner 的合法行为。

而：

```text
config_check
migrate_plan
backup_review
deploy_answer
```

实际上来自：

```text
DESIGNED_GROUND_TRUTH
evaluation-script task vocabulary
```

并不是 production Planner 的 frozen contract。

也就是说 Dataset 在偷偷规定：

> “Planner 必须选择我设计的 task。”

但这个 WP 的目标明明是：

> 评价 Episodic Memory。

于是 Dataset 跨越了 Domain Boundary（领域边界）。

------

# 10. Planner 和 Episodic Memory 的 Owner 边界

最后冻结成：

```text
Planner
→ 决定做什么

Runtime
→ 记录实际做了什么

Episodic Memory
→ 忠实记住实际发生了什么

AgentEvalOps
→ 比较 Runtime evidence 和 persisted Episode evidence
```

所以：

```text
Planner实际选择 task-data
```

只要这是合法 Plan，而 Episode 也忠实记录：

```text
task-data 对应的真实执行结果
```

那 Episodic Memory 就没有错。

不能因为 Dataset 原先想要：

```text
config_check
```

就判 Memory FAIL。

这个设计原则非常适合面试：

> **一个 Evaluator 不应该隐式评价另一个 Domain Owner 所负责的决策。**

------

# 11. 为什么不能只把那 5 条失败 Assertion 删除

发现 Dataset Scope Defect 后，最危险的修法是：

```text
E04 failed → 删除
E05 failed → 删除
E07 failed → 删除
E08 failed → 删除
```

然后：

```text
12 / 12 PASS
```

这叫 force-green。

我们最终要求对 E01-E12 **全部 Planner identity assertions** 做审计。

结果发现 V1 里一共 16 个 grounding run 都存在类似预定义 Planner vocabulary，只不过其中部分恰好和当前 Planner 匹配，所以之前 PASS。

于是 V2 对它们全部执行同一个规则。

这一步非常重要，因为它证明 V2 的 12/12 并不是 cherry-picking。

------

# 12. Dataset V1 为什么不能原地修改

V1 已经参与过历史实验。

如果直接修改：

```text
stateful_episodic_v1
```

然后继续叫：

```text
stateful_episodic_v1
```

历史结果就失去可解释性。

所以最终保留：

```text
V1
sha256:d87cc...
```

新建：

```text
stateful_episodic_v2
stateful-episodic-scenario.v2

sha256:678ecc...
```

并记录：

```text
parent = V1
reason = DATASET_SCOPE_DEFECT
```

这就是 Dataset Lineage（数据集血缘）。

------

# 13. 为什么 V1 86.5% → V2 100% 不能说“性能提升”

V1：

```text
Grounding denominator = 37
```

V2：

```text
Grounding denominator = 32
```

而且 Grounding Contract 本身发生变化。

所以：

```text
86.49%
→
100%
```

不是同一个指标定义下的提升。

正确表述是：

> V1 暴露了 Dataset Scope Defect；V2 修正 Grounding Contract 后，在新的合法 Domain Scope 下获得 100% deterministic Layer1 Grounding。

不应该说：

> “我们把 Grounding Accuracy 从 86.5% 优化到了 100%。”

这是面试真实性非常重要的一点。

------

# 14. 第三个大坑：Evaluation Backend 自己会制造假失败

WP6-E 早期有一个 generic scripted backend。

它会生成：

```text
DIRECT_ANSWER
执行专业任务
```

但 Dataset 有更具体的 task semantics。

于是 Grounding 大面积失败。

进一步审计甚至发现 specialist step 最开始出现：

```text
REQUIRED_DEPENDENCY_FAILED
```

最终根因并不是 production planner，而是 Layer1 scripted `ModelProfile` 缺：

```text
supports_code_reasoning
supports_structured_output
```

因此 specialist model selection 失败。

修复后：

```text
MultiAgentDriver
AgentRouter
Model Invocation
StepResult
Scheduler
RunCoordinator
```

仍然是真 Runtime。

我们只是替换：

```text
model-side nondeterministic output
```

为 deterministic scripted response。

这是一个非常好的测试替身设计原则：

> **Mock 不应该绕过被测 Runtime；它只应该替换不可控依赖。**

------

# 15. 为什么 Layer1 禁止真实模型

Layer1 的目标不是测模型能力。

而是验证：

```text
Memory contract
Runtime contract
Evaluation contract
Evidence chain
```

如果放进真实模型：

```text
同一个 input
Run 1 plan A
Run 2 plan B
```

你很难判断失败来自：

```text
Evaluator
Runtime
Memory
Model randomness
Prompt
Provider
```

因此 Layer1 使用：

```text
target-owned
bounded
deterministic
zero-network
scripted backend
```

这样才能建立稳定 baseline。

------

# 16. Layer2 和 Layer1 有什么区别

这个面试几乎必问。

Layer1：

```text
deterministic contract evaluation
```

回答：

> 系统实现是否满足我们定义好的工程合同？

Layer2：

```text
real-model observational evaluation
```

回答：

> 真实模型进入后，真实模型决策和语义变化下系统实际表现如何？

现在状态是：

```text
Layer1 = COMPLETE
Layer2 = NOT_RUN
Layer2 allowed = YES
```



千万不要说：

> “我们的真实模型 Episodic Memory 已经 100%。”

没有这回事。

------

# 17. 第四个大坑：实验通过 ≠ Baseline 可以冻结

V2 第一次已经：

```text
12 / 12 PASS
```

但 Codex 拒绝 canonicalize baseline。

因为发现：

```text
experiment Target ref =
2bb58e...

current Target ref =
f7841b...
```

也就是说：

> 实验测试的代码，不是现在工作区这份代码。

即便全部 PASS，也不能用它证明当前系统。

这就是 Provenance。

------

# 18. 为什么 aggregate hash 还不够

最初我们只有：

```text
TARGET_IMPLEMENTATION_REF =
sha256:2bb58...
```

后来 source drift 发生后却无法回答：

> 究竟哪个文件发生了变化？

因为：

```text
aggregate hash
```

只能告诉你：

```text
changed
```

不能告诉你：

```text
what changed
```

而旧源码 snapshot 又已经不存在。

最后只能将旧 baseline candidate 作废。

这就是我们后来引入 Source Receipt 的原因。

------

# 19. Source Receipt 怎么设计

最终 Target 和 AgentEvalOps 都有类似：

```text
semantic manifest

file A
  path
  sha256
  byte length

file B
  path
  sha256
  byte length

...

aggregate algorithm
aggregate ref

git/worktree identity
```

这样下次 ref：

```text
ABC
→
DEF
```

可以直接回答：

```text
file X changed
old digest
new digest
```

而不是重新考古 Git history。

------

# 20. Dirty Worktree 为什么仍可以 Certification

一个很容易被问的问题：

> 工作区不是 clean Git commit，还能做 baseline 吗？

答案：

可以。

关键不是：

```text
git clean
```

而是：

```text
你能否精确证明实验使用的 bytes。
```

我们最终就是：

```text
CURRENT_TARGET_WORKTREE_CLEAN = NO
```

但仍然通过：

```text
file-level receipt
aggregate digest
pre-run ref
post-run ref
experiment binding
```

完成 certification。

面试可以说：

> Git commit 是很方便的 provenance anchor，但并不是唯一形式；对于 dirty working tree，我使用 semantic source receipt 直接绑定实际 bytes。

------

# 21. 为什么旧 12/12 PASS 最后被作废

注意不是说：

> 旧实验错了。

旧实验依然是真实：

```text
HISTORICAL_CANDIDATE_EVIDENCE
```

只是不能回答：

> 当前代码是不是也 PASS？

因为无法恢复旧 `2bb58...` 对应源码。

最终做法：

```text
旧 candidate
→ INVALIDATED_CANDIDATE

当前 source bytes
→ new provenance root
→ fresh experiment
```

这是非常正确的治理方式。

------

# 22. Baseline Provenance 必须包含什么

最终一个 baseline authority 至少冻结：

```text
Dataset
├─ schema
├─ id
├─ version
└─ digest

Dataset lineage

Target
├─ implementation ref
└─ source receipt digest

AgentEvalOps
├─ implementation ref
└─ source receipt digest

Execution
└─ GLOBAL_SEQUENTIAL

Experiment
├─ artifact ref
└─ artifact digest

Results
├─ scenarios
├─ assertions
├─ metrics
└─ Layer1 gate

Environment provenance
```

所以 Baseline 不是：

```json
{"accuracy": 1.0}
```

而是一份**带环境和源码身份的实验权威记录**。

------

# 23. 为什么 experiment artifact 和 baseline artifact 要分开

最终设计：

```text
Experiment Artifact
↓
记录客观实验结果

Baseline Candidate
↓
引用 Experiment Artifact

Canonical Freeze Authority
↓
引用 Candidate
```

而不是：

```text
Experiment
↔
Baseline
```

互相引用。

否则产生：

```text
A digest依赖B
B digest又依赖A
```

出现 circular digest dependency。

因此最终是单向 DAG：

```text
Source Receipts
       ↓
Experiment Artifact
       ↓
Candidate Baseline
       ↓
Canonical Freeze Authority
```

------

# 24. 第五个大坑：Baseline compatibility 少比较 3 个字段

最后只剩一个 P1 时，所有 12 个 Case、194 assertions 已经 PASS。

但是 Codex 又阻止 freeze。

原因：

`compatibility_with()` 当时只比较：

```text
dataset_digest
target_ref
agentevalops_ref
execution_policy
```

却没有：

```text
target_source_receipt_digest
agentevalops_source_receipt_digest
experiment_artifact_digest
```

这意味着可能：

```text
ref相同
但绑定 evidence 已变化
```

却还被判断 compatible。

所以必须：

```text
different immutable evidence
→ BASELINE_INCOMPATIBLE
```



------

# 25. 为什么修 Baseline compatibility 后又必须重跑一次 12 Case

因为：

```text
episodic_baseline.py
```

本身属于：

```text
EPISODIC_SEMANTIC_SOURCE_FILES
```

修完以后 AgentEvalOps ref：

```text
b69f9f...
→
820915...
```

于是旧 experiment：

```text
绑定 b69f9f...
```

不能证明：

```text
820915...
```

哪怕改动只是 baseline governance。

最终我们还是重新跑了一遍。

这就是 strict provenance 的代价。

也是它的价值。

------

# 26. 最终 immutable chain

最终 canonical chain 大致可以脑补成：

```text
Dataset V2
678ecc...
      │
      ├───────────────┐
      │               │
Target Receipt    AgentEvalOps Receipt
f784...           820915...
      │               │
      └──────┬────────┘
             ↓
      Fresh Experiment
      12 / 12 PASS
             ↓
       Candidate R3
             ↓
    Canonical Authority
```

Canonical authority：

```text
canonical_baseline_authority.v2_r3_...
```

digest：

```text
sha256:f0d582f3...
```



------

# 27. 这整个 WP 最值得记住的 Bad Case

如果面试只能讲一个 Bad Case，我建议讲：

> **“12/12 PASS 但我拒绝冻结 Baseline。”**

故事非常完整：

最初：

```text
12/12 PASS
```

正常开发者可能直接宣布：

> evaluation done。

但进一步审计发现：

```text
experiment Target hash != current Target hash
```

而且只有 aggregate hash，没有 file-level receipt。

旧 snapshot 也无法恢复。

所以我们：

```text
没有降低 provenance gate
没有手工把 current hash改成old
没有重新描述旧实验为current evidence
```

而是：

```text
invalidated candidate
→ source receipt
→ fresh provenance lineage
→ fresh experiment
→ immutable baseline
```

这比“我把 Recall@K 做到 100%”更有面试区分度。

------

# 28. 工程构建方法类问题

## 问题一：为什么不能只测最终 Episode 内容？

因为最终内容只能证明 persistence 结果，无法判断错误发生在：

```text
Formation
Retrieval
Selection
Supply
Context Injection
```

正确做法是多阶段 evidence capture。

------

## 问题二：为什么 Evaluation Dataset 也必须受 Domain Boundary 约束？

因为 Dataset 是 Ground Truth Owner，不代表它拥有所有系统行为的决策权。

例如：

```text
Planner task selection
```

属于 Planner Domain。

Memory Dataset 如果规定唯一 Planner task，就已经跨 Domain。

------

## 问题三：怎么防止修 Dataset 时“为了过测试删难 Case”？

三个办法：

```text
完整 Scenario inventory
同类 assertion 全量审计
Negative regression
```

我们没有只删 5 个 FAIL，而是统一处理全部 Planner identity assertions。

------

## 问题四：为什么 Runtime Evidence 和 Persisted Evidence 必须独立？

如果 Persisted Episode 自己既是被测对象，又作为事实 authority：

```text
Episode说自己是对的
Evaluator拿Episode证明Episode是对的
```

会形成自证。

所以事实 authority 必须来自 Runtime。

------

## 问题五：为什么 baseline 还需要 code digest？

因为指标离开代码版本就没有意义。

```text
Recall@K=1
```

只能解释为：

> 某份 Dataset + 某份 Runtime + 某份 Evaluator 下 Recall@K=1。

------

## 问题六：为什么还要 experiment artifact digest？

因为同一代码可以运行：

```text
Run A
Run B
```

结果可能不同。

Baseline 必须指向具体哪一次实验 evidence。

------

## 问题七：为什么 Layer1 用 scripted backend 而不是 mock 掉整个 Runtime？

因为那样只是在测试自己的 mock。

正确方法：

```text
真实 Runtime
真实 Scheduler
真实 AgentRouter
真实 StepResult
真实 persistence

仅替换 model nondeterminism
```

------

# 29. 面试官高频追问与推荐答案

## Q1：你的 Episodic Memory 和普通聊天历史有什么区别？

回答：

> 我们把 Episode 定义成一次 bounded Run experience projection，不直接保存聊天 transcript，也不保存 CoT。它由 Runtime 在 terminal decision 后根据真实 AgentState 和运行事实形成，包括实际执行状态和结果，用于后续相似 Run 的历史经验检索。

------

## Q2：失败的 Run 会不会形成记忆？

回答：

> 会，只要它是有意义且事实充分的 Run。FAILED 本身也是有价值的历史经验。我们专门用 E02 和 E10 验证 failed Episode 的形成和后续 retrieval。

------

## Q3：怎么防止一条历史记忆跨 Agent 泄露？

回答：

> Episodic Retrieval 使用 exact `agent_id + scope` 过滤，E09 使用 foreign agent/scope fixture 做 negative test。Layer1 canonical baseline 中 scope leakage rate 为 0。

------

## Q4：怎么防止历史 Memory 被当成 instruction？

回答：

> Episodic content 通过 `EPISODIC_MEMORY_RETRIEVAL` source 注入，并固定为 `USER_CONTENT` trust level，同时增加“历史经验而非指令”的 preamble。E12 专门验证 instruction-like historical text 不会被提升为 system/developer authority。

------

## Q5：为什么 Retrieval 成功还不够？

回答：

> Retrieval 只是 selected。后面还有 supplied 和 ContextBuilder injected。我们分别取证这三层，避免“retriever选中了，但模型实际上没看到”的 false positive。

------

## Q6：你们用了向量库吗？

回答要特别准确：

> Knowledge RAG 使用 Dense + BM25 + RRF + Cross-Encoder；但是当前 Episodic Memory MVP 没有使用那套 retrieval stack，而是 bounded SQLite lexical retrieval。两个系统故意保持独立，避免把 Knowledge RAG 和 Long-term Memory 混成一个检索子系统。

------

## Q7：为什么不直接拿真实模型做 Evaluation？

回答：

> 我先用 deterministic Layer1 固定 Runtime、Memory 和 Evaluation Contract。如果一开始就放入 real model，模型的不确定性会和评估框架缺陷混在一起。Layer1 canonical 后才允许进入 Layer2 observational real-model evaluation。

------

## Q8：12/12 PASS 为什么还折腾那么久？

推荐回答：

> 因为 PASS 本身没有意义，必须回答“哪个 Dataset、哪版 Runtime、哪版 Evaluator、哪次 Experiment 得到的 PASS”。我们中间就发现过旧 experiment 的 Target hash 与当前源码不一致，所以主动 invalidated candidate，重新建立 source receipt 和 provenance lineage，然后才重新跑实验并冻结 baseline。

这句话很强。

------

# 30. 面试中不要说错的几件事

不要说：

```text
真实模型测试 100% 通过
```

真实情况：

```text
Layer1 deterministic = PASS
Layer2 real model = NOT_RUN
```

不要说：

```text
Grounding 从 86.5% 优化到 100%
```

因为 V1/V2 contract 和 denominator 不同。

不要说：

```text
Planner task-data 是我们修出来的
```

它本来就是合法 Planner 行为。

不要说：

```text
scope leakage 在任何生产环境都是 0
```

这里只能说当前 deterministic Layer1 Dataset 下为 0。

不要说：

```text
full suite 完全绿色
```

真实情况是：

```text
1903 passed
1 pre-existing failed
```



------

# 31. 30 秒面试总结

> 我在 LocalAgent 的 Advanced Memory 阶段为 Episodic Memory 建了一套 stateful evaluation。它不是简单比较最终输出，而是按 Scenario 共享 Memory 和 Journal 状态，分别验证 Episode formation、grounding、retrieval、scope、context injection 和 trust boundary。过程中我们发现过 evaluator identity authority 错误、Dataset 跨 Domain 规定 Planner task、以及 experiment source hash 与当前代码不一致等问题。最终通过 typed runtime evidence、Dataset V2 lineage、file-level source receipts 和 immutable baseline authority，把 12 个 deterministic scenarios、194 个 assertions 全部跑通，并冻结了 canonical Layer1 baseline；真实模型 Layer2 目前还没有执行。

------

# 32. 2 分钟面试总结

> 我们的 LocalAgent 在 Advanced Memory 阶段增加了 Episodic Memory，也就是把一次真实 Run 的有边界历史经验形成结构化 Episode，在后续相似请求中重新检索并注入模型上下文。
>
> 为了验证它，我没有用普通 input-output benchmark，而是做了 stateful scenario evaluation。一个 Scenario 内的多次 Run 共享 Runtime、Memory DB 和 Journal，Scenario 之间完全隔离。12 个场景分别覆盖成功和失败 Episode formation、trivial rejection、idempotency、factual grounding、privacy、similar retrieval、zero-score rejection、scope isolation、failed Episode retrieval、context injection 和 trust boundary。
>
> 实现过程中比较有价值的是，我们多次发现 Evaluation 系统自身的问题。比如一开始 Dataset 的 `release_list` 被拿去和 Episode 的 `执行专业任务` 做字符串比较，后来我们明确了 `PlanStep.step_id` 才是 canonical Runtime identity，而 display name 只是 presentation field，所以把 Runtime identity grounding 和 persisted observation fidelity 分开。
>
> 后来 identity 修好以后仍然只有 8/12 PASS，我们进一步发现 Dataset 预先指定了 `config_check`、`migrate_plan` 之类 Planner task，但这些只是 designed ground truth，并不是 production Planner contract。Memory evaluator 实际跨 Domain 在评价 Planner。于是我们创建 Dataset V2，把 Grounding 改成真实 Runtime facts 对 persisted Episode facts，同时保留 fabricated fact、status mismatch 等 negative gate。
>
> V2 后已经 12/12 PASS，但我们仍然没有直接冻结 baseline，因为 experiment 绑定的 Target hash 和当前源码不一致，而且历史上只保存 aggregate hash，无法解释 drift。最后我们 invalidated 旧 candidate，引入 per-file source receipt，对当前 Target 和 AgentEvalOps 重新建立 provenance，重新跑完整实验，再建立 experiment artifact、candidate baseline 和独立 canonical authority。最终 deterministic Layer1 canonical baseline 是 12/12 scenarios、194/194 assertions PASS，P0/P1 都为 0。真实模型 Layer2 目前仍然没有执行。

------

# 33. 这个 WP 对 1～3 年 Agent 开发岗位最大的面试价值

真正有区分度的不是：

```text
Memory
SQLite
Recall@K
```

这些很多候选人都能讲。

你的核心亮点应该放在：

```text
Evaluation 不是测试脚本，
而是一套有 Ground Truth Owner、
Evidence Authority、
Domain Boundary、
Implementation Provenance、
Dataset Lineage、
Baseline Lifecycle
的工程系统。
```

尤其是这三个故事最值得讲：

**第一，Evaluator 自己也会错。**

所以需要对 Evaluation Framework 本身做 contract 和 regression。

**第二，Ground Truth 也可能越权。**

Dataset 不能因为叫 Ground Truth 就规定其它 Domain Owner 的行为。

**第三，12/12 PASS 也可能不可信。**

如果无法证明测试到底跑在哪份源码上，就不能 canonicalize baseline。

这三个点基本已经从“会写 Agent 功能”提升到了“会构建可信 Agent Evaluation System”的层次。

------

# 34. 本 WP 最终真实性边界

最终可以确认的是真实完成：

```text
Stateful Episodic Dataset V2
12 Scenario deterministic Layer1
Runtime evidence capture
Identity grounding
Persisted fidelity
Retrieval / injection / trust evaluation
Dataset lineage
Source receipts
Durable experiment artifact
Immutable baseline authority
Canonical baseline freeze
```

最终测试：

```text
12 / 12 scenarios PASS
194 / 194 assertions PASS

Layer1 Gate PASS

full unit:
1903 passed
1 confirmed pre-existing failure
```



尚未完成：

```text
Real-model Layer2 observational experiment
```

所以当前准确状态就是：

```text
WP6-E Layer1 = COMPLETE
Layer2 = NOT_RUN
```

------

WP6-E 的学习/面试总结到这里完成。

**下一步你可以选择：直接进入下一步，或者继续对这个 WP 做一轮“模拟面试追问”，我按大厂 1～3 年 Agent 开发岗位连续追问你。**

当前使用的模型：**GPT-5.6 Sol**。

下面我按真正面试里的“**一个问题答完，面试官顺着你的答案继续往下挖**”来组织，而不是彼此独立的八股题。答案都基于这次 WP6-E 的真实实现和最终 Canonical Baseline（权威基线）结果；最终 deterministic Layer1 是 12/12 Scenario、194/194 Assertion PASS，Layer2 真实模型实验仍未执行。

# 第一轮：先确认你到底做了什么

### Q1：先简单介绍一下你在 Episodic Memory 评估这块做了什么？

**参考答案：**

我给 LocalAgent 的 Episodic Memory 做了一套 Stateful Evaluation（有状态评估）。

它不是传统的一次请求对应一次输出，而是以 Scenario 为隔离单位。一个 Scenario 内可以有 Run A、Run B，多次 Run 共享同一个 Memory DB 和 Journal DB，这样可以验证“Run A 形成历史经验，Run B 能不能正确检索和使用”。

最终 Dataset V2 有 12 个场景，覆盖 Episode formation、失败 Run 记忆、trivial rejection、幂等、grounding、privacy、retrieval、scope isolation、context injection 和 trust boundary。

Layer1 使用 deterministic scripted backend，不调用真实模型。最终 12/12 Scenario、194/194 Assertion PASS，并冻结成 canonical baseline。

------

### Q2：为什么 Memory Evaluation 一定要做成 Stateful？普通 case-by-case 不行吗？

**参考答案：**

不够。

普通 Evaluation 假设：

```text
input
→ system
→ output
→ evaluation
```

每个 Case 相互独立。

但 Episodic Memory 的核心能力本身就是跨 Run 的：

```text
Run A
→ 形成 Episode

Run B
→ 检索 Run A 的 Episode
→ 注入后续上下文
```

如果每个 Run 都 fresh DB，Run B 根本不存在历史状态，也就测不到 Episodic Memory。

所以我的隔离粒度是：

```text
Scenario 与 Scenario 之间完全隔离

Scenario 内多个 Run 共享：
- subprocess
- Memory DB
- Journal DB
```

这样既能测试 stateful behavior，又不会发生跨测试污染。

------

### Q3：为什么 Scenario 之间还要重新启动 subprocess？清数据库不就够了吗？

**参考答案：**

只清数据库不能覆盖所有 Runtime state。

除了 Memory DB、Journal DB，还有可能存在：

- process-level singleton；
- in-memory cache；
- registry state；
- runtime configuration；
- environment binding；
- ContextVar；
- connection/client state。

所以最终我们使用 `GLOBAL_SEQUENTIAL`，每个 Scenario 都 fresh subprocess、port、Memory DB、Journal DB、workdir 和 environment token。

这样 Scenario isolation 不依赖“我认为已经清干净”，而是直接通过 process boundary 保证。最终 canonical experiment 就是按这个执行策略冻结的。

------

# 第二轮：面试官开始问 Dataset 怎么设计

### Q4：你的 12 个 Scenario 具体覆盖哪些能力？

**参考答案：**

我更习惯按能力矩阵记，而不是死背 Case：

- E01：正常成功 Run 能形成 Episode；
- E02：失败 Run 也可以形成 truthful Episode；
- E03：问候、小聊这类 trivial Run 不应该形成；
- E04：同一个 `origin_run_id` replay 必须幂等；
- E05：Episode 必须 grounded in actual Runtime；
- E06：隐私和敏感信息；
- E07：相似历史经验的跨 Run retrieval；
- E08：无关历史必须 zero-score reject；
- E09：agent/scope isolation；
- E10：FAILED Episode 仍可以被后续检索；
- E11：selected、supplied、injected 三阶段证据；
- E12：历史内容保持 USER_CONTENT trust，不能变成 instruction authority。

这个设计比只测试“能不能存、能不能查”更接近完整的 Memory lifecycle。

------

### Q5：为什么失败的 Run 还要形成 Episode？失败了不是应该丢掉吗？

**参考答案：**

失败本身也是 Experience。

比如以前执行某个部署任务失败过，下一次再遇到类似任务，失败经历可能非常有价值。

所以我们的原则不是：

```text
SUCCESS 才能形成 Episode
```

而是：

```text
meaningful + factual terminal Run
```

就可能形成 Episode。

但失败 Episode 必须真实，比如：

```text
terminal = FAILED
delivery = NOT_DELIVERED
```

不能在记忆里变成成功。

E02 测失败 Episode formation，E10 测失败 Episode 后续仍然能够被 retrieval。

------

### Q6：那 trivial greeting 为什么不能也存？多存一点不是更好吗？

**参考答案：**

Memory 不是日志仓库。

如果：

```text
你好
谢谢
好的
```

这种交互也不断形成 Episode，会导致长期 Memory：

- 数量膨胀；
- retrieval noise 增大；
- 有价值 Episode 被稀释；
- context budget 被无意义历史占用。

所以 formation 有 eligibility。

E03 就专门验证 trivial Run：

```text
formation = SKIPPED_INELIGIBLE
memory count delta = 0
```

最终 canonical Layer1 的 trivial rejection rate 是 1.0。

------

# 第三轮：开始进入 Grounding

### Q7：你一直说 Grounding，这里的 Grounding 到底是什么？

**参考答案：**

在这个 WP 里，Grounding 不是传统 RAG 里的“回答是否基于文档”。

它指：

> Episode 中保存的历史事实，是否能被实际 Runtime evidence 证明。

所以必须存在两个独立 evidence surface：

```text
Actual Runtime Evidence
vs
Persisted Episode Evidence
```

比如 Runtime 实际：

```text
FAILED
NOT_DELIVERED
```

但 Episode 写：

```text
SUCCEEDED
DELIVERED
```

那就是 Grounding Failure。

------

### Q8：Runtime Evidence 具体从哪里来？为什么不能直接拿 Episode 自己比较？

**参考答案：**

不能让被测对象证明自己正确。

如果：

```text
Episode
→ 说自己执行成功
```

Evaluator 再读取同一个 Episode：

```text
Episode says SUCCESS
→ PASS
```

那就是 circular validation。

所以 Runtime truth 来自独立的：

- Journal Runtime events；
- Runtime receipt；
- terminal state；
- AgentState projection。

Episode 是被评价对象。

原则就是：

> **Runtime 是发生事实的 authority，Episode 是历史事实的 projection。**

------

### Q9：你们中间不是出现过 Grounding 全失败吗？是什么问题？

**参考答案：**

有，而且这是这个 WP 一个很典型的 Evaluation Bug。

Dataset 里写的是：

```text
release_list
```

Runtime canonical identity 是：

```text
task-release_list
```

但 persisted Episode 的 human-readable observation 是：

```text
执行专业任务
```

最初 Evaluator 直接拿：

```text
release_list
vs
执行专业任务
```

做 literal comparison。

所以会大规模误报。

后来我们重新审计 identity authority，发现：

```text
PlanStep.step_id
RuntimeEvent.step_id
```

才是 canonical Runtime identity。

而：

```text
PlanStep.title
→ StepState.name
```

只是 display name。

所以这是 Evaluator 把 presentation field 当 identity authority 了。

------

### Q10：那你最后怎么修的？

**参考答案：**

我们把 Grounding 拆成两部分。

第一部分：

```text
Runtime Identity / Fact Grounding
```

验证实际 Runtime 是否存在预期的 canonical fact。

第二部分：

```text
Persisted Observation Fidelity
```

验证 Episode 是否忠实描述真实 Runtime outcome。

然后引入 typed identity adapter，把 Dataset symbolic identity：

```text
release_list
```

统一 normalize 到：

```text
task-release_list
```

再与 `RuntimeEvent.step_id` 比较。

而 Episode 的：

```text
执行专业任务
```

继续保持 human-readable observation，不强行改成内部 Runtime ID。

------

### Q11：为什么不直接让 Episode 也保存 `task-release_list`？不是更容易比较吗？

**参考答案：**

因为不能为了 Evaluation 方便污染 production Memory Contract。

Episode 的 production contract 当时冻结的是：

> human-readable factual observation。

而 Episode 最终会经过：

```text
canonical_text
→ Memory retrieval
→ ContextBuilder
→ model-visible context
```

如果只是为了 Evaluator，把：

```text
task-release_list
```

这种 Runtime internal identity 塞进 Episode，就会改变：

- persistence schema；
- renderer；
- retrieval text；
- 最终 model-visible context。

这是典型的“为了让测试过而改生产设计”。

所以最后选择修 Evaluator identity authority，而不是改 Production Memory。

------

# 第四轮：面试官继续追 Dataset，最重要的一组

### Q12：修完 identity 之后是不是就 12/12 PASS 了？

**参考答案：**

没有。

修完以后大概是：

```text
8 / 12 PASS
```

但这次失败已经不是 Evaluator Bug，而暴露了 Dataset 自己的问题。

例如 Dataset 期待：

```text
config_check
```

但 Runtime 实际 Planner 合法选择：

```text
task-data
```

进一步审计发现 `config_check`、`migrate_plan`、`deploy_answer` 这些值其实是 human-designed / scripted task vocabulary，并不是 production Planner 冻结合同里的唯一合法输出。

------

### Q13：Dataset 不就是 Ground Truth 吗？为什么 Ground Truth 还能错？

**参考答案：**

这是我在这个 WP 里一个很重要的认识：

> **Ground Truth Owner 不等于所有 Domain 的 Behavior Owner。**

Dataset 可以定义 Episodic Memory 应该满足什么条件。

但是：

```text
Planner 应该选择哪个 task
```

这个决策属于 Planner。

如果 Memory Dataset 自己规定：

```text
这个请求必须选 config_check
```

那它实际上已经开始评价 Planner，而不是评价 Episodic Memory。

所以 Ground Truth 本身也需要 Domain Boundary。

------

### Q14：你最后是怎么划分 Owner 的？

**参考答案：**

最终冻结的是：

```text
Planner
→ 决定做什么

Runtime
→ 记录实际做了什么

Episodic Memory
→ 忠实持久化实际发生的 Experience

AgentEvalOps
→ 只读比较 Runtime evidence 和 Episode evidence
```

这条 Owner Boundary 很重要。

比如 Planner 合法选择：

```text
task-data
```

那么 Memory 正确行为应该是：

```text
忠实记录 task-data 对应的真实结果
```

而不是为了迎合 Dataset 假装 Planner 执行了：

```text
config_check
```

------

### Q15：那你是不是把那几个失败 assertion 删除掉，测试就绿了？

**参考答案：**

没有。

如果只删：

```text
E04/E05/E07/E08
```

当前失败的 assertion，那就是 cherry-picking / force-green。

我们做的是：

> 对 E01-E12 中所有同类型的 Planner identity assertion 做统一 Scope Audit。

包括那些当时碰巧 PASS 的，也全部审计。

结果发现 V1 中这类 assertion 是系统性的。

所以 V2 对所有 Scenario 采用统一规则，不再把 predefined Planner task selection 作为 Episodic Layer1 required Gate。

这个是我认为 V2 结果可信的重要原因之一。

------

### Q16：把 Planner identity 删了，会不会导致 Runtime 做什么都能 PASS？

**参考答案：**

不会。

V2 仍然要求两个独立 surface。

第一：

```text
require_runtime_step_facts = true
```

必须确实存在真实 Runtime completed step/status evidence。

第二：

```text
persisted fidelity
```

Episode 里的 observation status、terminal、delivery、result 必须被 Runtime 支撑。

此外 negative tests 继续覆盖：

```text
Runtime FAILED
Episode SUCCEEDED
→ FAIL

Episode fabricated nonexistent fact
→ P0

missing runtime evidence
→ BLOCKED
```

所以只是移除了 Planner domain overconstraint，并没有弱化 Memory Grounding。

------

# 第五轮：Dataset Versioning

### Q17：既然 V1 有问题，为什么不直接修改 V1 Dataset？

**参考答案：**

因为 V1 已经参与了历史实验。

如果原地修改：

```text
stateful_episodic_v1
```

那同一个 Dataset ID 就会对应两套不同 Ground Truth。

历史：

```text
8/12
```

和新：

```text
12/12
```

会失去可解释性。

所以我们保留 V1 bytes 和 digest，新建：

```text
stateful_episodic_v2
stateful-episodic-scenario.v2
```

并记录 lineage：

```text
parent = V1
reason = DATASET_SCOPE_DEFECT
```

这样历史 evidence 不会被重写。

------

### Q18：那为什么不能说 Grounding Accuracy 从 86.5% 提升到了 100%？

**参考答案：**

因为 metric semantic 已经变化。

V1 Grounding denominator：

```text
37
```

V2：

```text
32
```

V1 里面包含跨 Domain Planner identity assertions。

V2 则改成 actual-runtime-evidence + persisted-fidelity。

所以两个 1.0/0.8649 不是同一个测量定义。

正确表达是：

> V1 暴露 Dataset Scope Defect；V2 修正合同后，在新的合法 Episodic Domain Scope 下 Grounding Accuracy 为 1.0。

不能把它包装成普通性能优化。

------

# 第六轮：测试框架设计

### Q19：Layer1 为什么用 scripted backend？直接 mock Runtime 不更快吗？

**参考答案：**

如果把整个 Runtime mock 掉，测到的是：

```text
mock
→ mock
```

而不是生产执行链。

我们的 Layer1 保留真实的：

- Planner/PlanCompiler path；
- Scheduler；
- MultiAgentDriver；
- AgentRouter；
- Model invocation contract；
- StepResult；
- RunCoordinator；
- Journal；
- Memory formation/retrieval。

只把：

```text
model nondeterministic response
```

替换成 deterministic scripted model output。

所以它验证的仍然是实际 Runtime contract。

------

### Q20：为什么不用真实模型直接测？

**参考答案：**

因为当前阶段要先区分：

```text
system contract failure
```

和：

```text
model nondeterminism
```

如果一开始接真实模型，失败时可能来自：

- Planner randomness；
- prompt；
- provider；
- model output；
- Runtime；
- Memory；
- Evaluator。

定位成本会很高。

所以：

```text
Layer1
= deterministic contract evaluation

Layer2
= real-model observational evaluation
```

当前 Layer1 已 canonical，Layer2 是 `ALLOWED`，但仍然 `NOT_RUN`。

------

### Q21：你们 scripted backend 中间有没有出过问题？

**参考答案：**

有。

早期 generic scripted backend 太通用了，会产生不符合 Scenario request semantics 的 plan，制造大量假 Grounding Failure。

还遇到过 specialist step：

```text
REQUIRED_DEPENDENCY_FAILED
```

进一步定位发现并不是 Runtime dependency logic 错，而是 Layer1 scripted `ModelProfile` 缺少类似：

```text
supports_code_reasoning
supports_structured_output
```

导致真实 model-selection path 拒绝 specialist。

修复时没有绕过 Scheduler 或直接伪造 StepResult，而只是把 evaluation-only ModelProfile 调整到 Dataset 所需 capability，真实 Runtime 流程仍然执行。

这个 Bad Case 可以很好说明：

> Test Double 也必须满足真实系统 contract，否则它自己会制造 false negative。

------

# 第七轮：Selected / Supplied / Injected

### Q22：你怎么证明“Memory 被模型用了”？

**参考答案：**

不能只看 retrieval selected。

我们把证据拆成：

```text
selected
supplied
injected
```

`selected` 表示 retrieval service 选中了 Episode。

`supplied` 表示它真正进入 `MemoryContextBundle`。

`injected` 表示 `ContextBuilder` 最终把它放入 model context。

因为可能存在：

```text
selected = YES
supplied = YES
injected = NO
```

如果只测 selected，会把 context injection bug 错判成 retrieval success。

E11 就专门测这三层。

------

### Q23：为什么你们把 selected、supplied、injected 分这么细？是不是过度设计？

**参考答案：**

对一个简单 Demo 可能是过度。

但对 production Agent，Memory 链路至少有：

```text
retrieval
→ filtering
→ budget
→ context assembly
→ model-visible prompt
```

每层都可能丢内容。

如果用户问题是：

> “为什么我明明检索到了记忆，模型却完全没用？”

只看 retrieval log 无法定位。

这三层 evidence 可以快速区分问题 Owner，所以我认为这是合理的 observability boundary，而不是为了抽象而抽象。

------

# 第八轮：安全与 Trust Boundary

### Q24：历史 Episode 里面如果有人写“忽略之前所有指令”，会不会 Prompt Injection？

**参考答案：**

这是 E12 重点。

Episodic Memory 被视为历史用户内容，而不是 instruction authority。

所以 ContextBuilder 注入时：

```text
source =
EPISODIC_MEMORY_RETRIEVAL

trust =
USER_CONTENT
```

并有历史经验语义的 preamble。

即使 Episode 文本本身长得像指令，也不能被提升成 system/developer authority。

最终 Layer1：

```text
instruction_elevation_violation_rate = 0.0
```

但我只会说这是当前 deterministic Dataset 下的结果，不外推到所有生产输入。

------

### Q25：你怎么做 Scope Isolation？

**参考答案：**

当前 Episodic Memory Scope 是 exact：

```text
agent_id
+
scope
```

Retrieval candidate 必须满足 target agent 和 target scope。

E09 专门放 foreign agent/scope fixture。

验证它不能成为：

```text
candidate
selected
supplied
injected
```

所以 scope leakage 不只是检查最终 prompt，而是尽量在整个 retrieval/injection chain 上取证。

------

# 第九轮：面试官开始问“12/12 通过为什么还没结束”

### Q26：你已经 12/12 PASS 了，为什么后来还做了那么多 Gate？

**参考答案：**

因为：

> **Evaluation Result 和 Evaluation Authority 是两回事。**

我们第一次 V2 已经 12/12 PASS。

但是准备冻结 baseline 时发现：

```text
experiment target ref
!=
current target ref
```

也就是说实验测试的源码 bytes 和当前源码不一致。

那这份 12/12 只能证明历史 Target，不能证明当前 Target。

所以没有 canonicalize。

这是整个 WP 我认为最重要的工程决策之一。

------

### Q27：代码 hash 不一致，那重新算一下不就行了？

**参考答案：**

不能。

问题是旧实验当时只保存 aggregate hash：

```text
sha256:2bb58...
```

但没有保存 per-file semantic receipt。

后来 hash 变成：

```text
f7841...
```

我们知道“变了”，却不能可靠证明：

> 究竟哪些文件变了、是否只是 evaluation-only change、有没有 production semantic drift。

而旧 source snapshot 也拿不到。

所以不能通过猜测解释 provenance。

------

### Q28：最后怎么解决的？

**参考答案：**

没有继续强行考古旧 hash。

而是：

```text
old experiment
→ HISTORICAL_CANDIDATE_EVIDENCE

old baseline candidate
→ INVALIDATED_CANDIDATE
```

然后从当前实际 bytes 建新的 provenance root。

引入 Source Receipt：

```text
semantic file path
per-file sha256
byte length
ordered manifest
aggregate algorithm
aggregate ref
worktree identity
```

之后重新跑完整 V2 experiment。

这样未来再 drift，就可以知道具体哪个 semantic file 发生变化。

------

# 第十轮：Dirty Worktree 压力题

### Q29：工作区是 dirty 的，为什么你还敢冻结 baseline？

**参考答案：**

因为真正需要冻结的是：

> **实验实际使用的 bytes**

而不是一定要求：

> Git working tree clean。

Git commit 是很好的 provenance anchor，但不是唯一方式。

对于 dirty worktree，我们通过：

```text
per-file Source Receipt
+
aggregate implementation ref
+
pre-run ref
+
post-run ref
+
experiment artifact binding
```

证明实验期间 semantic source 没变化。

最终 canonical run 的 Target 和 AgentEvalOps 都满足：

```text
pre-run ref == post-run ref
```

所以 source stability PASS。

------

### Q30：那你不觉得 Git commit hash 更简单？

**参考答案：**

更简单，所以在正常生产 CI/CD 中我仍然优先建议 commit SHA / build artifact digest。

但这次开发阶段存在 dirty worktree，而且我们又需要精确冻结当前实验源码。

所以 Source Receipt 是：

> 对真实 bytes 的补充 provenance mechanism。

它不是说 Git 不重要，而是避免“只有 commit 才能做实验”的不必要限制。

------

# 第十一轮：Baseline 设计

### Q31：Baseline 在你的系统里到底是什么？不就是一组指标吗？

**参考答案：**

不是。

一组：

```text
accuracy=1.0
recall=1.0
```

不能构成完整 baseline。

我们的 Baseline Authority 绑定：

```text
Dataset
+ Dataset lineage
+ Target implementation
+ Target source receipt
+ AgentEvalOps implementation
+ AgentEvalOps source receipt
+ execution policy
+ experiment artifact
+ scenario outcomes
+ assertions
+ metrics
+ Layer1 gate
+ environment provenance
```

所以 baseline 本质上是：

> 一个带完整实验身份和源码身份的权威结果快照。

------

### Q32：Candidate Baseline 和 Canonical Baseline 有什么区别？

**参考答案：**

Candidate 表示：

> 实验已经产生，但还没有通过完整 authority / provenance / immutability Gate。

Canonical 表示：

> Dataset、源码、experiment、结果、compatibility contract 全部完成审计并被冻结。

而且我们最终不是直接修改 candidate：

```text
CANDIDATE
→ 修改原文件为 CANONICAL
```

而是保持 candidate immutable，再创建独立 canonical authority。

这样历史 evidence chain 不被改写。

------

### Q33：为什么 experiment artifact 和 baseline artifact 要拆开？

**参考答案：**

因为职责不同。

Experiment Artifact 回答：

> 这次实验客观发生了什么？

Baseline Authority 回答：

> 这次实验是否被选为某个版本的权威参考？

如果两边互相包含 digest：

```text
Experiment digest depends Baseline
Baseline digest depends Experiment
```

会产生 circular digest dependency。

所以最后是：

```text
Source Receipt
↓
Experiment Artifact
↓
Candidate Baseline
↓
Canonical Authority
```

单向依赖。

------

# 第十二轮：最后一个 Baseline Bad Case

### Q34：你们最终 Freeze 前还有什么问题？

**参考答案：**

最后一个 P1 是 Baseline Immutability Contract 不完整。

当时：

```text
compatibility_with()
```

只比较：

```text
dataset digest
target ref
agentevalops ref
execution policy
```

但漏掉：

```text
target source receipt digest
agentevalops source receipt digest
experiment artifact digest
```

所以理论上 evidence 已经变化，baseline 仍可能返回 compatible。

最终把这三个 immutable dimensions 加入 compatibility contract。任一变化都返回：

```text
BASELINE_INCOMPATIBLE
```

同时 `INVALIDATED_CANDIDATE` 不允许重新 canonicalize。

------

### Q35：修这么一个 baseline compatibility 函数，为什么又要重新跑 12 个 Scenario？

**参考答案：**

这是 strict provenance 带来的结果。

因为：

```text
episodic_baseline.py
```

本身属于 `EPISODIC_SEMANTIC_SOURCE_FILES`。

修改以后 AgentEvalOps implementation ref 从：

```text
b69f9f...
```

变成：

```text
820915...
```

旧 12/12 experiment 绑定的是旧 evaluator/governance bytes。

如果直接拿旧 experiment 冻结新版本，就违反我们刚刚建立的 provenance contract。

所以重新做了 fresh current-ref V2 experiment，最终还是 12/12 PASS，再 canonical freeze。

------

# 第十三轮：指标压力题

### Q36：你最终 12/12 全过，是不是说明 Episodic Memory 已经没有 Bug 了？

**参考答案：**

不能这样说。

只能说：

> 在 `stateful_episodic_v2`、当前 certified LocalAgent Target、当前 AgentEvalOps implementation 和 `GLOBAL_SEQUENTIAL` deterministic Layer1 contract 下，12/12 required scenarios PASS。

它不能证明：

- 所有自然语言输入；
- 所有真实模型决策；
- 所有生产并发情况；
- 所有 Memory 长期演化；
- 所有攻击场景；

都没有问题。

所以这叫 canonical baseline，而不是 correctness proof。

------

### Q37：那这些 1.0 指标到底有什么价值？

**参考答案：**

价值主要是 regression baseline。

以后如果：

```text
formation recall: 1.0 → 0.92
scope leakage: 0 → >0
injection success: 1.0 → 0.8
```

我们知道某个 frozen contract 回归了。

它的作用不是证明系统完美，而是：

> 建立稳定、可复现、可比较的工程行为基线。

------

### Q38：Fabricated Fact Rate=0，是不是代表模型不会幻觉？

**参考答案：**

不是。

这里的 fabricated fact 指的是：

> Episodic Formation 是否记录了 Runtime 实际没有发生的 step/tool/recovery/result。

不是通用 LLM hallucination metric。

所以不能把：

```text
FABRICATED_FACT_RATE = 0
```

解释成：

> 模型幻觉率 0。

这是完全不同的指标语义。

------

# 第十四轮：RAG / Memory 交叉追问

### Q39：你的 Episodic Retrieval 用的是向量库 + BM25 + RRF 吗？

**参考答案：**

不是。

要严格区分 Knowledge RAG 和 Long-term Memory。

Knowledge RAG 当前是：

```text
Dense
+ BM25
+ RRF
+ Cross-Encoder
```

而 Episodic Memory 当前 MVP 是：

```text
bounded SQLite lexical retrieval
```

使用 canonical text 和确定性的 lexical tokenization/ranking。

这是有意分开的，不把知识检索和历史经验检索强行合成同一套 Retrieval Stack。

------

### Q40：那为什么 Episodic Memory 不直接复用现成高级 RAG？

**参考答案：**

当前优先级是：

> Contract 可解释、状态正确、Scope 正确、可评估。

Episodic Memory Dataset 规模和当前 MVP 需求并不要求复杂 hybrid retrieval。

如果一开始就叠加：

```text
embedding
BM25
RRF
reranker
```

会把：

```text
Memory correctness
```

和：

```text
retrieval tuning
```

混在一起。

现在先把 Memory lifecycle 和 Evaluation contract 打稳，将来如果 Episode 规模和 recall 需求真的出现瓶颈，再升级 retrieval architecture。

------

# 第十五轮：系统设计追问

### Q41：如果以后数据量大了，你会怎么升级 Episodic Retrieval？

**参考答案：**

我会保持 Retrieval Interface 不变，逐步替换底层 candidate generation。

可能演进为：

```text
Metadata hard filter
  agent_id / scope / active

↓
Lexical + Dense candidate retrieval

↓
Hybrid fusion

↓
Optional reranking

↓
top-K / context budget
```

但我不会直接复制 Knowledge RAG。

因为 Episodic Memory 还要考虑：

- recency；
- run outcome；
- failed/success experience；
- agent/scope；
- temporal relevance；
- duplicate/similar experience；
- memory lifecycle。

未来 scoring contract应该单独设计。

------

### Q42：如果引入向量 retrieval，Evaluation 需要怎么变化？

**参考答案：**

需要新增 ranking-oriented metrics，但不会删除现有 behavioral assertions。

比如增加：

```text
Recall@K
MRR
NDCG
```

或者针对 expected Episode：

```text
expected episode rank
```

但这些不能替代：

```text
scope leakage
injection
trust boundary
fabricated fact
formation
```

因为“检索排名好”不等于“Memory 系统正确”。

------

# 第十六轮：最后几个很容易把人问崩的题

### Q43：你这套 Evaluation 最大的问题是什么？

**参考答案：**

目前最大的真实性边界是：

> Layer1 是 deterministic evaluation，不是真实模型 observation。

所以虽然 contract 已经非常稳定，但它还没有回答：

```text
真实 DeepSeek / 其它模型
在非确定性 Planning 下
Episodic Memory 实际效果如何
```

这就是 Layer2 的任务。

另外当前 full unit 仍有一个已经确认 pre-existing 的：

```text
test_security_dataset::
test_v2_dataset_rejects_unsupported_schema_version
```

最终 canonical run 是：

```text
1903 passed
1 pre-existing failed
```

不能说 full suite 全绿。

------

### Q44：如果让你重做一次，这个 WP 最想提前做什么？

**参考答案：**

我会更早冻结三个东西：

第一，**Domain Owner Matrix**。

一开始明确 Planner、Runtime、Memory、Dataset、Evaluator 各自拥有的行为，能更早避免 Dataset Scope Defect。

第二，**Evidence Authority Matrix**。

明确：

```text
step identity → Journal
terminal → Runtime receipt
persisted memory → Memory store
injection → ContextBuilder
```

避免 display field 和 canonical field 混用。

第三，**file-level Source Receipt**。

如果最开始实验就保存 per-file semantic receipt，就不会发生后来旧 aggregate hash 无法解释的问题。

------

### Q45：这个项目里你认为最有价值的一个 Bad Case 是什么？

**参考答案：**

我会选：

> “12/12 PASS 但我主动拒绝冻结 baseline。”

当时实验已经全通过，但 experiment 绑定的 Target ref 和当前源码 ref 不一致，而且旧实验只有 aggregate source hash，没有 file-level receipt，已经无法可靠解释 source drift。

我没有：

- 手工把 hash 改成一致；
- 认为只是小改动就忽略；
- 把历史 12/12 当当前结果。

而是 invalidated old candidate，引入 per-file Source Receipt，重新认证当前源码、重新执行完整 V2 experiment，最后才冻结 canonical baseline。

这个案例可以同时体现：

```text
evaluation governance
provenance
fail-closed
baseline lifecycle
engineering truthfulness
```

我认为它比单纯讲“实现了一个 Memory API”更有区分度。

------

# 第十七轮：面试官让你做最终总结

### Q46：两分钟总结一下，你这个 WP 最终解决了什么？

**参考答案：**

我为 LocalAgent 的 Episodic Memory 建了一套 stateful deterministic evaluation。

它以 Scenario 为隔离单位，Scenario 内多个 Run 共享 Memory 和 Journal，因此能够真正测试“上一轮形成 Episode、下一轮检索并注入”的跨 Run 行为。12 个 Scenario 覆盖 formation、failed memory、trivial rejection、idempotency、grounding、privacy、retrieval、scope、injection 和 trust boundary。

在开发过程中，我发现 Evaluation 系统本身也会产生错误。比如最开始把 human-readable step name 当 canonical identity，后来拆分 Runtime Identity Grounding 和 Persisted Observation Fidelity；之后又发现 Dataset 用 designed Planner task vocabulary 约束 production Planner，跨越了 Episodic Memory 的 Domain Boundary，因此建立 Dataset V2，并保留 V1 lineage。

V2 第一次已经 12/12 PASS，但我没有直接冻结 baseline，因为 experiment source ref 和当前源码不一致。最后我们引入 file-level Source Receipt、durable experiment artifact、candidate baseline 和独立 canonical authority，并补齐 baseline compatibility contract。最终针对当前 certified LocalAgent、当前 AgentEvalOps、Dataset V2 和 `GLOBAL_SEQUENTIAL` policy，fresh experiment 得到 12/12 Scenario、194/194 Assertion PASS，并冻结了 canonical Layer1 baseline。

目前 deterministic Layer1 已完成，但 real-model observational Layer2 仍未执行。

------

## 最后给你一个面试记忆主线

如果实际面试时紧张，不需要背上面 46 题。

你只要抓住下面这条因果链：

```text
为什么做 Stateful
↓
因为 Episodic Memory 跨 Run

怎么证明真实
↓
Runtime Evidence vs Persisted Episode

Evaluator 为什么曾经错
↓
Display Name ≠ Canonical Identity

为什么 Dataset 也错
↓
Memory Dataset 越权评价 Planner

怎么修 Dataset
↓
V1 immutable → V2 lineage

为什么 12/12 还不够
↓
Experiment source != current source

怎么解决 provenance
↓
Source Receipt + fresh rerun

Baseline 为什么还卡过
↓
immutability dimensions 不完整

最终怎么冻结
↓
Experiment → Candidate → Canonical Authority

现在到哪
↓
Layer1 COMPLETE
Layer2 NOT_RUN
```

这条主线掌握以后，大部分追问你都能从“**Owner → Evidence → Contract → Provenance**”四个词往回推，而不需要硬背答案。最终 canonical Layer1 的完整 evidence chain、12/12 场景和 194/194 assertion 均已冻结；真实模型 Layer2 仍明确为未执行。

下一轮如果你愿意，我们可以直接进入**不附答案的真实模拟面试**：我一次只问一题，根据你的回答继续追问，并在最后统一打分。