当前使用的模型：**GPT-5.6 Sol**。

下面正式做 **Stage5-Phase5-WP5：Stateful Memory Evaluation（有状态记忆评估）** 的学习 / 面试总结。本次总结只基于已经真实完成并通过 Final Closure Gate 的工程结果，不把后续优化或尚未解决的 LocalAgent 行为问题描述成已完成能力。

推荐保存文件名：

```
docs/interview/stage5_phase5_wp5_stateful_memory_evaluation.md
```

------

# 一、WP5 一句话定义

WP5 的核心不是“把 Memory 场景跑绿”，而是建立一套能够让**真实 LocalAgent 在连续多轮状态变化下运行，并用 Dataset Ground Truth（数据集真值）、Runtime Evidence（运行时证据）、最终 SQLite 状态和分层指标判断记忆形成、生命周期、检索、注入、隔离与泄漏行为**的 Stateful Memory Evaluation 系统。

最终结果：

```text
WP5_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS
OPEN_P0 = 0
OPEN_P1 = 0

BASELINE_V2_STATUS = CANONICAL
WP5_ENGINEERING_COMPLETE = YES
PHASE5_INTERVIEW_READY = YES
```

20 个真实 Scenario 全部执行，最终行为结果是：

```text
PASS    = 6
FAIL    = 4
BLOCKED = 10

EVALUABLE = 10
Quality Success Rate = 6 / 10 = 60%
Overall Pass Fraction = 6 / 20 = 30%
```

这套 Baseline（基线）故意保留 FAIL / BLOCKED，而不是追求 20/20 全绿。

------

# 二、先理解 WP5 到底解决了什么问题

WP1～WP4 已经解决了 Memory 本身：

```text
WP1  Domain / Persistence
WP2  Formation
WP3  Lifecycle
WP4  Retrieval / Ranking / Context Injection
```

但“代码实现了”和“这个 Memory 系统真的可信”完全是两件事。

WP5 要回答的是：

```text
用户说：
项目数据库使用 SQLite

        ↓

Memory Formation
到底记没记？

        ↓

Predicate
是不是 project.database？

        ↓

Lifecycle
后来说 PostgreSQL 后，
是否真的 SUPERSEDE？

        ↓

Retrieval
后续问题有没有找到当前正确 Memory？

        ↓

Context Injection
Memory 有没有真正进入模型上下文？

        ↓

Isolation / Leakage
旧的、遗忘的、其它 Scope 的 Memory
有没有错误泄漏？

        ↓

最终 SQLite
到底是什么状态？
```

而且这些不能只测单次函数调用。

真正的 Memory 是**有状态的**：

```text
Step 1: Remember SQLite
Step 2: Correct to PostgreSQL
Step 3: Ask current database
```

Step 3 的正确性取决于 Step 1、Step 2 已经真实改变了系统状态。

这就是 Stateful Evaluation 与普通单轮 Evaluation 最大的区别。

------

# 三、真实性与完成边界

这是面试中必须主动讲清楚的一部分。

## 已真实实现

WP5 已真实实现：

- Stateful Dataset V2；
- Scenario / Step 顺序执行；
- 每个 Step 对应独立 ExecutionAttempt；
- Scenario 内状态连续；
- Scenario 间环境隔离；
- Formation / Predicate / Lifecycle / Final State / Retrieval / Injection / Leakage / Invariant 等 Evaluator；
- Layer 1 deterministic evaluation；
- Layer 2 real-model evaluation；
- SQLite final-state projection；
- Journal evidence collection；
- Baseline artifact；
- Evaluation Implementation Ref；
- Runtime / Evaluation Infra / Expected Evidence Limitation 分离；
- Canonical Baseline V2。

Final Closure Gate 已确认 Evaluation System 达到 Engineering Complete。

## 已真实测试

真实 E1-v2 Attempt-2：

```text
20 scenarios
28 steps
28 primary execution attempts

20 scenarios with real model invocation

Authoritative MODEL_STARTED = 80
Physical MODEL_STARTED = 83
```

之所以 Physical 是 83，是因为 authoritative suite 建立前曾有一次 FrozenDict serialization aborted run，实际产生额外 3 个模型调用，但不属于正式 Baseline lineage。

## 真实已知限制

当前 Layer 2 production journal 为 content-minimized，因此无法证明具体 selected / excluded Memory identity。

所以：

```text
Expected Memory Recall@K = NOT_EVALUABLE

Forgotten Leakage = NOT_EVALUABLE
Scope Leakage = NOT_EVALUABLE
Superseded Leakage = NOT_EVALUABLE
```

不能写成 `0`，也不能写成 `PASS`。

## 尚未完成

没有完成：

```text
Layer2 identity-level Retrieval observability
完美的 Memory Formation 稳定性
所有 real-model scenario 20/20 PASS
Windows temp file cleanup 完全稳健
```

这些均不是 WP5 Completion 的必要条件。

------

# 四、WP5 的核心架构

可以把整个系统记成五层。

```text
                 Dataset Ground Truth
                         │
                         ▼
                Stateful Scenario Runner
                         │
                         ▼
                  Real LocalAgent
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       Journal        SQLite State    HTTP Result
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                   Typed Assertions
                         │
                         ▼
                      Metrics
                         │
                         ▼
                    Hard Gate
                         │
                         ▼
                  Baseline Artifact
```

其中三个 Authority（权威）边界尤其重要：

```text
LocalAgent
= Runtime Owner

AgentEvalOps
= Evaluation Owner

Dataset
= Ground Truth Owner
```

AgentEvalOps **不能为了评估方便修改真实 Memory 状态**。

这是 WP5 最重要的设计原则之一。

------

# 五、为什么一个 Scenario 要包含多个 Step

例如：

```text
database_correction

Step 1
“项目数据库使用 SQLite”
→ INSERT SQLite

Step 2
“项目数据库改成 PostgreSQL”
→ SUPERSEDE SQLite
→ ACTIVE PostgreSQL

Step 3
“当前数据库是什么？”
→ Retrieval / Injection
```

如果三个 Step 分别启动三个独立 Memory DB：

那 Step 3 根本不是 Stateful Evaluation。

因此我们冻结：

```text
同 Scenario：
state continuity

不同 Scenario：
fresh isolated environment
```

每 Scenario 都是：

```text
fresh LocalAgent subprocess
fresh port
fresh Memory DB
fresh Journal DB
fresh environment token
fresh work directory
```

这样既能测试状态演进，又避免不同 Scenario 相互污染。

------

# 六、为什么 Final SQLite State 比 Event 更权威

这是非常好的系统设计面试点。

Event 能告诉我们：

```text
曾经发生过什么
```

而 Final State 告诉我们：

```text
系统最后真正处于什么状态
```

例如：

```text
INSERT SQLite
SUPERSEDE SQLite
INSERT PostgreSQL
```

Event 看起来可能都正确。

但如果最终 DB 里：

```text
SQLite ACTIVE
PostgreSQL ACTIVE
```

那么系统仍然违反 keyed ACTIVE invariant（键控激活不变量）。

所以我们冻结：

```text
Journal
= observational evidence

Final SQLite projection
= final-state authority
```

最终真实实验中：

```text
Final State Accuracy = 15 / 16 = 93.75%
Invariant Pass Rate = 44 / 44 = 100%

keyed ACTIVE violation = 0
scope isolation violation = 0
```



------

# 七、为什么设计 Layer 1 和 Layer 2

这是整个 WP5 最值得面试展开的设计之一。

## Layer 1 — Deterministic Contract Verification（确定性合同验证）

目标：

> 验证 Evaluation Contract 本身是否严格正确。

例如检索必须满足：

```text
ACTIVE → 可以选

SUPERSEDED → 不允许选

FORGOTTEN → 不允许选

foreign scope → 不允许选

unrelated lexical memory → 不允许选
```

Layer 1 使用 deterministic harness，因此要求严格：

```text
7 retrieval scenarios
7 PASS
0 FAIL
0 BLOCKED
```

Layer 1 是：

> Contract correctness gate。

------

## Layer 2 — Real Model Evaluation（真实模型评估）

目标：

> 观察真实 LocalAgent + 真实模型的实际行为。

这里模型有随机性：

```text
Formation 可能少记
Formation 可能多记
Planner 可能失败
Runtime subsystem 可能 failure
```

所以 Layer 2 不能要求：

```text
100% PASS
```

Layer 2 是：

> Behavioral baseline。

这就是为什么最终：

```text
LAYER2_GATE = FAIL
```

同时仍然：

```text
BASELINE_V2 = CANONICAL
WP5_ENGINEERING_COMPLETE = YES
```

两者并不矛盾。

------

# 八、PASS / FAIL / BLOCKED 为什么必须分开

这是另一个高频面试点。

## PASS

证据足够，而且行为符合 Ground Truth。

## FAIL

证据足够，而且证明行为不符合 Ground Truth。

例如：

```text
expected IGNORE
actual formed memory
→ FAIL
```

## BLOCKED

Ground Truth 存在，但因为上游失败或证据不足，**无法公平判断**。

例如：

```text
Formation runtime failure
        ↓
根本没有 lifecycle event
        ↓
Lifecycle assertion
不能 PASS
也不能 FAIL
        ↓
BLOCKED
```

如果把 BLOCKED 当 FAIL：

会把“没法评价”和“证明确实错误”混在一起。

如果把 BLOCKED 当 PASS：

更严重，会制造虚假正确性。

因此最终：

```text
PASS = 6
FAIL = 4
BLOCKED = 10
```

而质量成功率只使用：

```text
PASS + FAIL
```

作为 denominator。

------

# 九、为什么 Success Rate 是 60%，但 Overall Pass 只有 30%

这是以后面试很容易被追问的地方。

真实结果：

```text
PASS = 6
FAIL = 4
BLOCKED = 10
```

所以：

```text
Quality Success Rate
= PASS / (PASS + FAIL)
= 6 / 10
= 60%
```

但：

```text
Overall Pass Fraction
= PASS / TOTAL
= 6 / 20
= 30%
```

两者表达完全不同。

你面试不能简单说：

> “成功率 60%。”

应该说：

> “20 个 Scenario 中 6 PASS、4 FAIL、10 BLOCKED；对 10 个真正可评 Scenario 计算的 quality success rate 是 60%，总体直接 PASS 比例是 30%。”

Final Gate 专门验证了这个口径。

------

# 十、Expected Evidence Limitation 为什么是一个独立概念

Layer 2 当前 Production Journal 不输出具体 Memory IDs。

所以对于：

```text
expected selected = db
expected excluded = db_old
```

Evaluation 实际不知道：

```text
到底选中了哪个 memory_id
```

这不是：

```text
FAIL
```

因为没有证据证明选错。

也不是：

```text
PASS
```

因为没有证据证明选对。

因此设计：

```text
BLOCKED

blocked_by =
NOT_SUPPORTED_BY_CURRENT_EVIDENCE

evidence_gap_classification =
EXPECTED_EVIDENCE_LIMITATION
```

最终真实 Baseline 中共有：

```text
12 expected-evidence-limitation blocked assertions
```



这是一个非常好的 Evaluation Engineering（评估工程）思想：

> **知道自己无法证明什么，本身也是评估系统可信度的一部分。**

------

# 十一、为什么 Retrieval Identity 不可评，但 Count 仍然可以评

这是 WP5 一个非常细的设计。

假设 runtime 只告诉 Evaluation：

```text
selected_count = 1
context_record_count = 1
```

但没告诉：

```text
selected_memory_id
```

那么：

### 不能判断

```text
selected 的是不是 db
```

因此：

```text
Recall@K → BLOCKED
```

### 但仍然可以判断

```text
有没有检索到 Memory
有没有注入 Context
```

例如：

```text
selected_count = 0
```

这就是明确的：

```text
RETRIEVAL_MISS
```

不能因为 identity evidence unavailable 就把整个 Retrieval Evaluator BLOCKED。

这就是：

> **Identity assertions 与 Count-level assertions 解耦。**

------

# 十二、为什么 Leakage 不能写成 0

当前 Layer2：

```text
Forgotten Leakage Rate = None
Superseded Leakage Rate = None
Scope Leakage Rate = None
Irrelevant Injection Rate = None
```

因为没有 identity evidence。

假设你只知道：

```text
selected_count = 1
```

你不知道这个 1 是：

```text
正确 ACTIVE memory
```

还是：

```text
FORGOTTEN memory
```

所以不能说：

```text
Leakage = 0
```

必须：

```text
NOT_EVALUABLE
```

这就是典型的：

> Absence of evidence is not evidence of absence.

------

# 十三、为什么 Leakage Rate 与普通 Accuracy 的方向不同

普通指标：

```text
Accuracy
Recall
Hit@K
Rejection Rate
```

通常：

```text
1 = best
```

而 Leakage：

```text
0 = best
```

因此最终冻结：

```text
Leakage Rate
= failed / evaluable
```

而普通 Accuracy：

```text
= passed / evaluable
```

这个问题 WP5 中真实抓到过一次 evaluator bug：

原先 leakage 也错误使用：

```text
passed / evaluable
```

结果：

```text
没有 leakage
→ value = 1.0
```

虽然数值数学没错，但指标语义完全反了。

最后修正为：

```text
0 = no leakage
1 = all leaked
```

这属于非常典型的 Evaluation Metric Semantics（评估指标语义）问题。

------

# 十四、Evaluation Implementation Ref 是什么

只保存 Git commit 不够。

因为实验期间可能存在：

```text
同一个 HEAD
+
dirty worktree
```

而 Evaluation semantics 已经改变。

所以 WP5 使用：

```text
evaluation_implementation_ref

=
Git HEAD
+
semantic source content digest
```

最终真实 Baseline：

```text
cc2ac10559047eca813bf0b9b202a7ffc13c599f:
sha256:5f536e282abbf67319be38227621cfd50a70f446c818559cd5ddcbdf816ec8a9
```



它覆盖：

```text
Dataset
Evaluator
Metrics
Gate
Journal
Projection
Runner
Provisioner
Execution Transport
...
```

这样同一个 Git HEAD 下，只要关键 Evaluation semantics 改过：

```text
implementation_ref
```

就变化。

这是 Baseline 可复现性的关键。

------

# 十五、为什么 V1 Baseline 不能直接和 V2 做数值对比

V1 与 V2：

```text
Dataset 不同
Ground Truth contract 有变化
Evaluation implementation ref 不同
```

因此：

```text
BASELINE_V1_V2_COMPATIBILITY =
INCOMPATIBLE
```

不能写：

> “V2 比 V1 成功率提高了 XX%。”

这属于典型的 apples-to-oranges comparison（不可比实验比较）。

V1 最终保留为：

```text
OBSERVATIONAL_ONLY
```

V2 才是：

```text
CANONICAL
```



------

# 十六、真实实验最终指标怎么理解

最终真实结果中最值得记的几项：

| 维度                         | 结果           | 怎么解释                           |
| ---------------------------- | -------------- | ---------------------------------- |
| Formation REMEMBER Precision | 11/12 ≈ 91.7%  | 记下来的事实大多数应该被记         |
| Formation REMEMBER Recall    | 11/13 ≈ 84.6%  | 应该记的事实仍有漏记               |
| IGNORE Precision             | 2/4 = 50%      | 模型对“不该记”的判断仍不稳定       |
| IGNORE Recall                | 2/3 ≈ 66.7%    | 仍存在不应形成 Memory 却形成的情况 |
| Predicate Class Accuracy     | 10/10          | REGISTERED / OPEN 分类稳定         |
| Predicate ID Accuracy        | 10/10          | 注册 Predicate identity 稳定       |
| Lifecycle Accuracy           | 13/14 ≈ 92.9%  | 生命周期整体稳定                   |
| Final State Accuracy         | 15/16 = 93.75% | 最终持久化状态整体可靠             |
| Invariant Pass Rate          | 44/44          | 核心状态不变量没有破坏             |
| Injection Success            | 2/3            | 有一个真实 Context Injection Miss  |



最明显的短板是：

> Formation 判断仍然受真实模型随机性影响。

而不是：

> Persistence / Predicate / Core Lifecycle 整体失控。

------

# 十七、WP5 中最值得记住的 Bad Cases

## Bad Case 1：Deterministic Harness 自己制造假失败

最初：

```text
ScriptedMemoryTarget("*")
```

只按：

```text
ACTIVE + agent + scope
```

选择。

所以：

```text
db
北京天气
```

两个 ACTIVE direct Memory 都被选中。

导致：

```text
retrieval_unrelated_rejection FAIL
```

但真实 LocalAgent lexical overlap 明明是：

```text
db > 0
weather = 0
```

根因：

> Evaluation Harness 与 Runtime Contract 不一致。

修复：

只在 test-only deterministic harness 中增加最小 lexical mirror，而不是实现第二套 Production Retrieval。

知识点：

> **测试替身如果不具备足够 fidelity（保真度），测试本身可以制造错误结论。**

------

## Bad Case 2：Leakage Metric 方向反了

原实现：

```text
value = passed / evaluable
```

结果：

```text
0 leakage
→ 1.0
```

但指标名叫：

```text
Leakage Rate
```

最终修为：

```text
failed / evaluable
```

知识点：

> 指标不仅要数学正确，还必须语义方向正确。

------

## Bad Case 3：Loopback 请求被系统 Proxy 拦截

真实 E1-v2 Attempt-1：

```text
AgentEvalOps
→ 127.0.0.1 LocalAgent /health
→ system proxy 127.0.0.1:7892
→ HTTP 502
```

修复：

```text
AgentEvalOps loopback client
→ trust_env=False
```

但 LocalAgent：

```text
→ DeepSeek external API
```

仍保留自己的 provider 网络环境。

知识点：

> Control-plane local traffic 与 external data/model traffic 要做网络策略隔离。

------

## Bad Case 4：Provisioning 失败但 stdout/stderr 被 DEVNULL 丢弃

真实 Canary 出现：

```text
process exit code = 3
```

但：

```text
stdout = DEVNULL
stderr = DEVNULL
```

无法判断原因。

最终增加：

```text
bounded startup diagnostics
redaction
typed failure phase
```

知识点：

> Fail-fast 如果没有 failure evidence，只是“更快地不知道为什么失败”。

------

## Bad Case 5：真实 Runtime terminal 导致下游 Assertion BLOCKED

例如：

```text
Formation FAIL
↓
Lifecycle 没发生
↓
Lifecycle assertion BLOCKED
```

这不能简单：

```text
全部 FAIL
```

也不能：

```text
全部 PASS
```

知识点：

> Evaluation 要区分 root failure 与 downstream non-evaluable consequences。

------

# 十八、名词 / 概念速览

按照你的固定模板，每个只用一句话。

**Stateful Evaluation（有状态评估）**：多个 Step 在共享状态下顺序执行，用于验证状态随时间演进后的系统行为。

**Scenario（场景）**：一个完整的业务评估单元，可包含多个有顺序依赖的 Step。

**ExecutionAttempt（执行尝试）**：一次具体 Step 对真实 Runtime 的执行记录。

**Ground Truth（真值）**：Dataset 中描述预期行为的权威事实，Evaluator 不能自行修改。

**Evaluation Owner（评估所有者）**：负责执行评估、收集证据和计算结果，但不能拥有被测系统状态。

**Runtime Owner（运行时所有者）**：真正执行并修改业务状态的系统，本项目中是 LocalAgent。

**Final State Authority（最终状态权威）**：判断最终 Memory 状态时以只读 SQLite projection 为最终事实来源。

**Evidence Capture（证据采集）**：从 Journal、SQLite、HTTP Result 等渠道收集可用于判断 Ground Truth 的证据。

**PASS**：证据充分且实际行为满足 Ground Truth。

**FAIL**：证据充分且实际行为违反 Ground Truth。

**BLOCKED**：Ground Truth 存在，但由于缺少必要证据或前置行为失败而无法完成判断。

**Expected Evidence Limitation（预期证据限制）**：系统设计已知无法提供某类证据，因此保持 BLOCKED，但不视为 Evaluation Infra defect。

**Invariant（不变量）**：无论模型行为如何都必须始终成立的系统状态约束。

**Layer 1 Deterministic Evaluation（第一层确定性评估）**：用可控环境严格验证 Contract correctness。

**Layer 2 Real-Model Evaluation（第二层真实模型评估）**：用真实 Runtime 与真实模型建立 behavioral baseline。

**Behavioral Baseline（行为基线）**：记录真实系统当前行为，包括 PASS、FAIL 和 BLOCKED，而不是只保存成功结果。

**Canonical Baseline（规范基线）**：Dataset、Evaluation implementation、Target 和 Model provenance 均被冻结、可复核的正式基线。

**Evaluation Implementation Ref（评估实现引用）**：Git HEAD 加关键 Evaluation semantic source digest，用于准确标识实验使用的评估实现。

**Provenance（来源追踪）**：记录 Dataset、代码、Runtime、模型、解释器和实验 lineage，使结果可复核。

**Leakage Rate（泄漏率）**：不应出现的 Memory 被错误检索或注入的比例，0 最好。

**Quality Denominator（质量分母）**：只使用真正可评价的 PASS + FAIL，不把 BLOCKED 强行计入。

**Systemic Infra Failure（系统性基础设施失败）**：会让整个 Suite 无法可靠执行的 Provisioning / Transport / Artifact 等公共基础设施问题。

------

# 十九、工程构建方法类问题

这一部分是你要求固定加入的“模糊工程题”，重点不是背项目代码，而是理解通用设计。

## Q1：为什么 Memory Evaluation 不能只做单轮输入输出测试？

因为 Memory 的核心价值是状态演进；单轮只能验证当前回答，无法验证 Remember → Supersede → Forget → Retrieve 的跨轮生命周期。

------

## Q2：Stateful Evaluation 最大的工程难点是什么？

不是写 Evaluator，而是同时保证：

```text
Scenario 内状态连续
Scenario 间状态隔离
Evidence 可追踪
Final State 有唯一 Authority
失败不能污染后续场景
```

------

## Q3：为什么不用 Event 直接作为 Final State？

Event 是“发生过什么”，DB State 是“最后是什么”；Event 可能完整但持久化最终结果仍然错误。

------

## Q4：为什么 BLOCKED 不能直接算 FAIL？

因为 FAIL 表示“已经证明行为错误”，BLOCKED 表示“没有足够条件完成判断”，两者统计含义不同。

------

## Q5：为什么 Layer 1 要 100% 严格，而 Layer 2 不需要？

Layer 1 测的是我们自己定义的 deterministic contract，失败说明 Evaluation / Contract 有问题；Layer 2 测真实模型，随机性和真实 runtime failure 本身就是要记录的行为。

------

## Q6：为什么不能为了减少 BLOCKED 而让 Evaluator 去查询更多内部状态？

因为会破坏 Evaluation 与 Runtime 的 Authority Boundary；Evaluator 只能读取合法证据，不能通过越权访问或修改内部状态制造“可评”。

------

## Q7：为什么 identity evidence 不足时 Count 仍然要评？

因为“有没有检索到任何 Memory”和“检索到的是不是正确 Memory”是两个不同问题，Evidence 能力也不同。

------

## Q8：为什么 Baseline 里应该保存 FAIL？

因为 Baseline 是当前系统行为的事实快照，不是 KPI 展示；如果只保留成功结果，就失去 regression detection 价值。

------

## Q9：为什么 Dataset 版本变化后不能直接比较指标？

因为 Ground Truth 发生变化后 denominator 和问题难度都可能变化；没有 comparability contract 的指标差异不代表系统 regression/improvement。

------

## Q10：为什么 Git SHA 不足以标识 Evaluation Implementation？

因为 dirty worktree 下同一个 HEAD 可以对应不同 evaluator semantics，所以还需要 semantic source content digest。

------

## Q11：为什么测试 Harness 不能过度模拟 Production Runtime？

因为一旦复制出第二套完整 Retrieval Engine，就会出现两套逻辑漂移；Harness 只应实现完成 Contract Verification 所需的最小 deterministic semantics。

------

## Q12：为什么网络 Proxy 问题也算 Evaluation Engineering？

因为 Evaluation 不只是 metric 函数；Provisioning、Execution Transport、Isolation、Evidence Collection 都属于 Evaluation System 的可信执行链。

------

# 二十、面试高频追问与答案

## 1. 你这个评估平台和普通 LLM Eval 有什么区别？

普通 LLM Eval 更多是一问一答；我的 Stateful Memory Eval 会让同一个 Scenario 中的多个 Step 共享真实 Memory 状态，例如先记 SQLite、再改 PostgreSQL、最后询问当前数据库，同时验证 Formation、Lifecycle、Retrieval、Injection 和最终 SQLite State。

------

## 2. 你怎么保证不同测试案例之间不互相污染？

每个 Scenario 使用 fresh LocalAgent subprocess、独立端口、Memory DB、Journal DB、environment token 和 work directory；只在同一个 Scenario 内保持状态连续。

------

## 3. 你怎么判断 Memory 最后是否正确？

最终状态不依赖回答文本，也不只看事件，而是对 Scenario 独立 SQLite 做只读 projection，将其作为 Final State Authority。

------

## 4. 为什么你真实实验只有 6 个 PASS，还说项目完成？

因为 WP5 的目标是建设可信 Evaluation System，而不是把真实模型行为调成 20/20。Final Gate 验证 Dataset、Evaluator、Evidence、Metrics、Invariant 和 Baseline Authority 都可信，真实 FAIL / BLOCKED 被准确保留，所以 Evaluation Engineering 已经完成。

------

## 5. LAYER2_GATE=FAIL 为什么还能 Canonical？

因为这个 Gate FAIL 表达真实 Runtime/model terminal、localized evidence gap 和 downstream prerequisite BLOCKED，而不是 Evaluation core correctness failure；Canonical Baseline 可以包含失败，只要这些失败被准确记录。

------

## 6. 你是怎么处理证据不足的？

用 BLOCKED，不把缺证据伪造为 PASS 或 FAIL；如果是架构已知缺证据，再用 typed `EXPECTED_EVIDENCE_LIMITATION` 单独分类。

------

## 7. Retrieval Recall@K 为什么最后是 None？

真实 production journal 当前没有 selected Memory identity，所以无法知道“选中的是不是 expected memory”；因此 denominator 为 0，结果是 NOT_EVALUABLE，而不是 0。

------

## 8. 那你怎么知道 Retrieval 本身没坏？

Layer 1 deterministic contract 已经用 identity-level evidence 严格验证 Retrieval，包括 ACTIVE hit、SUPERSEDED / FORGOTTEN exclusion、scope isolation 和 unrelated rejection；Layer 2 主要验证真实 Runtime behavior。

------

## 9. 你怎么测试 Memory leakage？

有 identity evidence 时直接验证 FORGOTTEN、SUPERSEDED、foreign scope、irrelevant Memory 是否进入 selected/injected IDs；没有 identity evidence时明确 NOT_EVALUABLE。

------

## 10. 这个项目里最典型的 Evaluation Bug 是什么？

一个是 Harness wildcard 没模拟 lexical relevance，导致测试自己制造 irrelevant retrieval；另一个是 Leakage Rate 错用了 success-rate formula，导致“没有泄漏”显示成 1.0。

------

## 11. 你怎么保证 Baseline 可复现？

Baseline 绑定 Dataset schema/id/version/digest、Evaluation implementation ref、AgentEvalOps HEAD、LocalAgent HEAD、解释器、Provider / Model profile、timestamp 和 experiment lineage。

------

## 12. 你的 Baseline V1 和 V2 为什么不能比较？

因为 Dataset Ground Truth 和 Evaluation implementation 都发生了 contract-level 变化，所以标记 `BASELINE_INCOMPATIBLE`，禁止做数值 delta。

------

# 二十一、30 秒面试总结

> 我在 LocalAgent 的 Advanced Memory 上建设了一套 Stateful Memory Evaluation 系统，不只测单轮问答，而是让多个 Step 在真实共享 Memory 状态下执行，覆盖 Formation、Predicate、Lifecycle、Retrieval、Context Injection、Scope Isolation 和 Final State。评估系统将 LocalAgent 作为 Runtime Owner、AgentEvalOps 作为 Evaluation Owner、Dataset 作为 Ground Truth Owner，并用 Journal 和只读 SQLite 做证据。最终跑了 20 个真实 Scenario、28 个 Step，正式 Baseline 有 80 次模型调用，Predicate Accuracy 10/10、Lifecycle 13/14、Final State 15/16、Invariant 44/44。最终形成 Canonical Baseline V2，并保留真实 FAIL、BLOCKED 和 Evidence Limitation，而不是为了指标追绿。

------

# 二十二、2 分钟面试总结

> 我在完成 LocalAgent 的 Memory Formation、Lifecycle 和 Retrieval 后，继续建设了 Stateful Memory Evaluation。传统单轮 Eval 很难验证 Memory，因为 Memory 的正确性依赖跨轮状态，例如先记 SQLite、后面改 PostgreSQL、再问当前数据库，需要验证旧 Memory 是否被 Supersede、当前 Memory 是否能被 Retrieve 和 Inject，以及最终 SQLite 状态是否正确。
>
> 我把 Authority 拆成三层：LocalAgent 是 Runtime Owner，AgentEvalOps 只负责 Evaluation，Dataset 是 Ground Truth Owner。每个 Scenario 可以包含多个有依赖的 Step，Scenario 内共享状态，不同 Scenario 使用独立 LocalAgent subprocess、端口、Memory DB 和 Journal DB。Evaluator 不只看模型回答，而是结合 Journal Evidence 和只读 SQLite Final State。
>
> 同时我设计了两层评估。Layer 1 用 deterministic harness 严格验证 Contract，例如 ACTIVE 才能被选中、FORGOTTEN 和跨 Scope Memory 必须被排除；Layer 2 使用真实 LocalAgent 和 DeepSeek 建 Behavioral Baseline，不要求 100% PASS，而是准确保留模型随机性和 Runtime failure。
>
> 过程中真实发现过一些 Evaluation Bad Case，例如 Harness 本身没有模拟 lexical relevance，导致 unrelated memory 被错误选中；还有 Leakage Rate 方向反了，以及本机 Proxy 把 `127.0.0.1` 的 LocalAgent health request 转发到代理导致整套实验阻塞。这些都通过 Contract Gate 和 Infrastructure remediation 修复。
>
> 最终真实执行了 20 个 Scenario、28 个 Step，Canonical Suite 有 80 个 `MODEL_STARTED`。Predicate Class 和 Predicate ID 都是 10/10，Lifecycle 13/14，Final State 15/16，Invariant 44/44。真实结果是 6 PASS、4 FAIL、10 BLOCKED，我没有重跑追绿，而是把这些结果连同 Evidence Limitation 一起冻结成 `WP5_STATEFUL_MEMORY_BASELINE_V2`。最终 Codex Final Gate 判定 `PASS_WITH_ACCEPTED_LIMITATIONS`，Baseline V2 升级为 Canonical，WP5 Engineering Complete。

------

# 二十三、你现在最应该真正掌握的 8 个点

1. **Stateful Eval 为什么和单轮 Eval 不一样。**
2. **Runtime Owner / Evaluation Owner / Ground Truth Owner 为什么必须分离。**
3. **PASS / FAIL / BLOCKED 三态为什么不能混。**
4. **Journal Evidence 与 Final SQLite Authority 为什么不是一回事。**
5. **Layer 1 deterministic contract 与 Layer 2 real behavioral baseline 为什么要分层。**
6. **Identity evidence 不足时为什么 Count 仍然可以评。**
7. **Canonical Baseline 为什么可以包含 FAIL / BLOCKED。**
8. **Evaluation 本身也可能有 Bug，所以 Harness、Metrics、Infra、Provenance 同样需要被评估。**

如果这 8 个点能够脱离项目代码自己讲清楚，WP5 对面试的核心价值基本就掌握了。