当前使用的模型：**GPT-5.6 Sol**。

是的，**整个 Stage5-Phase4 已经正式结束**。最终 Narrow Closure Gate（窄范围收口门禁）为：

```text
WP4_NARROW_CLOSURE_REVIEW_STATUS = PASS_WITH_ACCEPTED_LIMITATIONS
P0_COUNT = 0
P1_COUNT = 0
P2_COUNT = 0

WP4_READY_TO_CLOSE = YES
WP4_FINAL_STATUS = COMPLETE_WITH_ACCEPTED_LIMITATIONS
READY_FOR_PHASE5 = YES
```

因此这里可以把 **Stage5-Phase4：Feature Risk Review（特性风险评审）** 整体冻结为完成状态；`READY_FOR_PHASE5=YES` 只是说明允许进入下一 Phase，不代表 Phase5 已经实施。

这次建议整份 Phase 学习材料保存为：

```text
docs/interview/stage5_phase4_feature_risk_review_and_evaluation.md
```

------

# 一、Phase4 到底做了什么

Phase4 的完整目标不是简单做一个“文档分析 Agent”。

真正目标是构建这样一条闭环：

```text
真实 Feature Document
        ↓
Document Analysis
        ↓
Historical Risk Retrieval
       ╱       ╲
Historical Issue   Existing Test Coverage
       ╲       ╱
 Multi-Agent Risk Analysis
        ↓
Deterministic Aggregation
        ↓
Citation-bearing Risk Review Report
        ↓
Human Ground Truth
        ↓
Frozen Real Execution
        ↓
Human Adjudication
        ↓
Quality Evaluation
```

最终完成的是：

> **一个面向新功能设计文档的多 Agent 风险评审工作流，以及与之配套的、可冻结、可审计、可复现的真实 Evaluation Loop（评测闭环）。**

这比单纯“调用几个 Agent 生成风险报告”多解决了两个关键问题：

```text
1. 报告从哪里来？
2. 怎么证明报告质量怎么样？
```

------

# 二、整个 Phase4 的 WP 划分

最终可以整理成：

```text
Stage5-Phase4 — Feature Risk Review

├─ WP0 — Data Source Bootstrap
│  └─ 真实 Kubernetes Feature / Issue / Test Plan 数据准备
│
├─ WP1 — Dataset + Contracts
│  ├─ Feature Risk Review typed contracts
│  ├─ Runtime Dataset
│  └─ Evaluation Annotation Boundary
│
├─ WP2 — Three-Agent Risk Review Workflow
│  ├─ DocumentAnalysisAgent
│  ├─ RiskRetrievalAgent
│  ├─ TestReviewAgent
│  └─ Parallel Workflow
│
├─ WP3 — Risk Aggregation + Citation Report
│  ├─ Deterministic Aggregator
│  ├─ Risk / Priority Policy
│  ├─ Partial Failure Semantics
│  └─ Citation-bearing Report
│
└─ WP4 — Real E2E + Quality Evaluation
   ├─ Human Ground Truth
   ├─ Runtime Freeze
   ├─ Real DeepSeek Execution
   ├─ Human Adjudication
   └─ Deterministic Evaluation
```

这五个 WP 实际上对应了完整的：

```text
Data
→ Contract
→ Runtime
→ Product Output
→ Evaluation
```

工程生命周期。

------

# 三、WP0：为什么一定要先准备真实数据

Phase4 一开始最容易犯的错误就是：

> 为了快速演示，自己编几个 Feature Document。

我们最终没有这样做。

WP0 使用了真实 Kubernetes Enhancement Proposal（Kubernetes 增强提案）作为 Feature Source。

冻结 Case：

```text
k8s_541   External credential providers
k8s_753   Sidecar Containers
k8s_1287  In-place Update of Pod Resources
k8s_1472  Storage Capacity Constraints
k8s_1602  Structured Logging
```

同时准备：

```text
KEP
Enhancement Tracking Issue
Historical Kubernetes Issue Snapshot
Test Plan
Evaluation Reference
Metadata / Manifest
```

所以后续风险报告不是在 synthetic（合成）文档上证明“Agent 好像能工作”，而是在真实开源工程材料上运行。

## WP0 最重要的工程思想

### Source Authenticity（源真实性）

先保证：

```text
input is real
```

再谈：

```text
evaluation is meaningful
```

否则一个完全 synthetic dataset 上的 90% Accuracy 很难说明工程价值。

------

# 四、WP1：为什么先定义 Contract，而不是直接写 Agent

WP1 做了整个 Phase4 的 Typed Contract（类型化合同）。

核心对象包括：

```text
FeatureDocument
FeatureChangePoint
EvidenceRef
HistoricalIssue
TestPlan
TestCase
RiskFinding
FeatureRiskReviewReport
EvaluationAnnotation
FeatureRiskReviewCase
```

这一步的意义不是“多写几个 Pydantic Model”。

真正解决的是：

> Runtime、数据、评测和报告之间到底通过什么对象通信？

------

# 五、WP1 最重要的边界：Runtime Data 和 Ground Truth 分离

这是整个 Phase4 后面能够可信评测的基础。

最终数据被分成：

```text
Runtime / Business Data
        ↓
normalized/cases.v1.json
```

和：

```text
Evaluation-only Data
        ↓
annotations/annotations.v1.json
```

也就是说：

```text
Runtime Loader
不能自动加载
EvaluationAnnotation
```

这是非常重要的防泄漏设计。

否则：

```text
expected_risk_level
expected_issue_ids
```

一旦意外进入 Agent Prompt，后面的 Evaluation 全部失去意义。

------

# 六、WP1 还学到了一个很重要的问题：Dataset Builder 不能覆盖人工标签

项目中真实出现过一个 P1：

> Dataset rebuild 可能把已经人工审核过的 annotation 覆盖回初始状态。

后来修正为：

```text
HUMAN_REVIEWED annotation
在 projection rebuild 时必须保留
```

这是很典型的 Dataset Engineering（数据集工程）问题。

它说明：

> 构建脚本不仅要保证“能生成数据”，还要保护高价值的人工作业结果。

------

# 七、WP2：三 Agent 为什么这样拆

最终 Agent：

```text
DocumentAnalysisAgent
RiskRetrievalAgent
TestReviewAgent
```

没有做一个：

```text
FeatureRiskSuperAgent
```

原因是三个 Agent 分别对应三个不同信息源和职责。

------

# 八、DocumentAnalysisAgent 的职责

它只看：

```text
Feature Document
```

负责：

```text
Feature Summary
Change Points
Affected Components
Potential Risk Areas
```

它回答的是：

> “这个 Feature 本身发生了什么变化？”

而不是：

> “历史上发生过什么事故？”

这就是职责边界。

------

# 九、RiskRetrievalAgent 的职责

它负责：

```text
Historical Knowledge Retrieval
Historical Issue Retrieval
Risk Finding
EvidenceRef
```

这里最重要的设计是：

### Provider / Retriever 拥有事实身份

例如：

```text
issue_id
source_id
evidence_id
source_path
```

不能由 LLM 自己生成。

LLM 只能基于已经检索到的事实：

```text
infer RiskFinding
```

不能：

```text
invent historical_issue_id
```

------

# 十、TestReviewAgent 的职责

它读取：

```text
TestPlan
TestCase
```

生成：

```text
coverage_assessment
potential_gaps
recommended_missing_cases
```

它回答：

> 现有测试覆盖到了什么，还有什么风险没有真正覆盖？

这里特别重要的是：

```text
Existing Coverage
```

和：

```text
Recommended Missing Cases
```

不能混。

一个 AI 建议：

> 应该增加 XX 测试

并不代表：

> 当前系统真的存在这个 Coverage Gap。

这个区别后来在 WP4 的低 Coverage Precision 上被真实验证出来。

------

# 十一、为什么 RiskRetrieval 和 TestReview 并行

流程冻结为：

```text
DocumentAnalysis
        ↓
    ┌───┴────┐
    ↓        ↓
Risk      TestReview
Retrieval
    └───┬────┘
        ↓
Aggregation
```

因为：

```text
Historical Issue Retrieval
```

与：

```text
Test Coverage Review
```

在 Document Analysis 完成以后没有数据依赖。

所以用了：

```text
asyncio.gather(..., return_exceptions=True)
```

而不是串行执行。

------

# 十二、为什么 `return_exceptions=True` 很关键

如果：

```text
RiskRetrieval FAIL
```

但：

```text
TestReview SUCCESS
```

我们不希望整个 Workflow 直接抛异常，把 TestReview 的成功结果一起丢掉。

所以设计了：

```text
BranchStatus:
SUCCESS
FAILED
NOT_STARTED
```

以及：

```text
WorkflowStatus:
SUCCESS
PARTIAL
FAILED
```

这就是 Partial Result Preservation（部分结果保留）。

------

# 十三、Phase4 的 Failure State Machine

冻结语义：

### Document Analysis 失败

```text
Document = FAILED
Risk = NOT_STARTED
Test = NOT_STARTED

Workflow = FAILED
```

因为下游没有输入。

------

### Risk 失败，Test 成功

```text
Document = SUCCESS
Risk = FAILED
Test = SUCCESS

Workflow = PARTIAL
```

保留 Test 信息。

------

### Risk 成功，Test 失败

```text
Workflow = PARTIAL
```

同理。

------

### 两个 downstream 都失败

```text
Workflow = FAILED
```

这后来真实发生在：

```text
k8s_1287
```



------

# 十四、WP2 的一个关键架构决策：没有复用 Evaluation ExecutionTarget

当时考虑过：

> Phase4 Agent 执行是不是应该复用已有 Evaluation ExecutionTarget？

最后否决。

原因是：

```text
ExecutionTarget
```

的 Owner 是：

```text
Evaluation Attempt Execution
```

而 Feature Risk Review Workflow 是：

```text
业务 Workflow
```

二者生命周期、状态和责任不同。

这是典型的：

### Ownership Boundary（所有权边界）

不要因为“代码看起来能复用”就把 Owner 不同的两个系统强耦合。

------

# 十五、为什么 Phase4 没有改 LocalAgent Runtime

当时也考虑过直接把：

```text
DocumentAnalysisAgent
RiskRetrievalAgent
TestReviewAgent
```

注册进 LocalAgent Runtime。

最终：

```text
LOCALAGENT_WRITE = NONE
```

原因是这样会导致：

```text
Agent Registry
Planner
Corpus
Lifecycle
Runtime Contract
```

一起被迫修改。

对于一个面试导向、时间有限的 Evaluation Feature，这个代价明显超过收益。

所以 AgentEvalOps 自己拥有：

```text
FeatureRiskReviewWorkflow
```

LocalAgent 保持只读。

------

# 十六、真实模型执行遇到的第一个生产问题：Structured Output

WP2 第一次 DeepSeek Real Smoke 失败。

原因不是 Agent Workflow，而是：

```text
response_format.type = json_schema
```

Provider 不兼容。

根因冻结为：

```text
MODEL_PROVIDER_STRUCTURED_OUTPUT_CAPABILITY_MISMATCH
```

后来 adapter 区分：

```text
DeepSeek
→ json_text

Others
→ native json_schema
```

但 Parser 和 Pydantic Validation 不变。

------

# 十七、这个 Structured Output 修复为什么是好的设计

没有：

```text
try native schema
↓ fail
retry json mode
```

而是在请求之前：

```text
根据 Provider Identity
决定兼容模式
```

所以一次 Agent Invocation 仍然只做：

```text
ONE MODEL REQUEST
```

这避免了隐藏 retry。

这个设计后来对 WP4 One-pass Evaluation 非常重要。

------

# 十八、WP3：为什么 Aggregator 不应该是第四个 LLM Agent

这是 Phase4 最重要的架构取舍之一。

可以有两种方案：

### 方案 A

```text
三个 Agent
→ Final Synthesis Agent
```

### 方案 B

```text
三个 Agent
→ Deterministic Aggregator
```

最终选 B。

------

# 十九、为什么选 Deterministic Aggregator

最终汇总涉及：

```text
RiskLevel
Priority
Evidence identity
Coverage State
Partial Failure
Section availability
```

这些都属于：

> 系统 Policy，而不是开放式推理。

如果交给 LLM：

```text
相同输入
→ 可能 HIGH
→ 可能 MEDIUM
```

会造成 Evaluation 无法稳定复现。

所以最终：

```text
AGGREGATION_OWNER =
FeatureRiskReviewAggregator
```

而不是第四 Agent。

------

# 二十、Phase4 学到的一个非常重要原则

可以概括为：

> **LLM 负责推理，Application Policy 负责裁决。**

例如：

LLM 可以说：

```text
这个 Change 可能导致 stale credential
```

但：

```text
RiskLevel = HIGH
Priority = ACT_NOW
```

最终由 deterministic policy 决定。

------

# 二十一、Risk Level Policy

WP3 冻结了一个启发式规则。

例如：

```text
coverage gaps exist
+
historical issue reference
+
multiple findings
```

可能推到：

```text
HIGH
```

而：

```text
LOW
```

只有在非常严格条件下才能出现。

后来 Evaluation 证明：

系统明显偏：

```text
HIGH
```

RiskLevel Accuracy 最终只有：

```text
2 / 4 = 0.5
```



这正说明：

> Deterministic 不代表 Policy 已经正确校准。

所以最后明确：

```text
RISK_POLICY_CALIBRATED = NO
```

------

# 二十二、Risk Level 和 Priority 为什么分开

这是一个容易混淆的面试问题。

### Risk Level

表示：

> 风险严重程度。

例如：

```text
HIGH
MEDIUM
LOW
```

### Priority

表示：

> 接下来应该采取什么行动。

例如：

```text
ACT_NOW
SCHEDULE_REVIEW
MONITOR
COMPLETE_REVIEW
```

如果 Workflow PARTIAL：

即使已有 finding 很严重，也可能：

```text
Priority = COMPLETE_REVIEW
```

因为现在最优先的是：

> 把缺失分支补完整。

所以：

```text
Risk != Action Priority
```

------

# 二十三、Citation 系统是怎么设计的

Phase4 没有让 LLM 自己写：

```text
[C1]
[C2]
```

然后相信它。

实际 authority：

```text
Provider / Retriever
→ EvidenceRef
→ Aggregator
→ Stable Citation Label
```

EvidenceRef 包含：

```text
evidence_id
source_type
source_id
source_path
source_url
section
```

Aggregator 只是消费，不负责创造 Evidence identity。

------

# 二十四、为什么 Evidence ID 冲突要 fail closed

如果两个来源声明：

```text
evidence_id = E123
```

但内容不同。

不能：

```text
last write wins
```

否则报告的 Citation Identity 已经不可相信。

所以：

```text
same ID + conflicting identity
→ fail closed
```

这是 Source Provenance（来源溯源）的核心原则。

------

# 二十五、WP3 还遇到了一个非常有意思的 Bad Case：换行符

WP3 Report Renderer 输出是：

```text
\n
```

但 Windows `write_text()` 默认 newline translation 导致：

```text
\r\n
```

甚至某个阶段出现：

```text
\r\r\n
```

这样：

```text
renderer output
!=
saved artifact
```

虽然人眼打开 Markdown 几乎看不出来。

但从 Evaluation Artifact Authority 看，这是 correctness bug。

最后修复：

```text
write_text(..., newline="")
```

并验证：

```text
rendered_string == read_bytes().decode("utf-8")
```

------

# 二十六、这个换行 Bug 为什么很值得面试讲

因为它说明：

> Artifact Correctness 不止是业务内容正确。

还包括：

```text
serialization
encoding
filesystem behavior
```

最终原则：

> **Filesystem serialization is part of the correctness boundary.**

------

# 二十七、WP4：真正进入 Evaluation Engineering

WP0～WP3 解决：

```text
怎么生成报告
```

WP4 解决：

```text
怎么知道报告好不好
```

这一步把系统从 Agent Workflow 推到了 Evaluation Lifecycle。

------

# 二十八、Ground Truth 如何构建

5 个 Case 的 Ground Truth 不是 Agent 自动标注。

全部由人工基于 Frozen Source 标注：

```text
expected_change_points
expected_components
expected_risk_areas
expected_historical_issue_ids
expected_coverage_gaps
expected_risk_level
```

最终：

```text
5 / 5 HUMAN_REVIEWED
GROUND_TRUTH_READY
```



------

# 二十九、为什么 Ground Truth 不能看 Prediction

因为这样会产生：

### Label Leakage（标签泄漏）

例如：

```text
模型预测 HIGH
↓
人工觉得 HIGH 也挺合理
↓
把 GT 改成 HIGH
```

此时评测已经失效。

所以真实流程：

```text
Human Label
↓
GROUND_TRUTH_READY
↓
Freeze
↓
Prediction
```

------

# 三十、Manifest Freeze 冻结了什么

不只是 Ground Truth。

还冻结：

```text
Git commit
Dataset digest
Annotation digest
Retrieval corpus digest
Model
Temperature
Structured output mode
Agent code authority
Workflow
Aggregator
Renderer
Risk policy
Priority policy
Retrieval scoring
top_k
```

保证 5 个 Case 评的是：

> **同一个系统版本。**

------

# 三十一、为什么每个 Case 只能一个 Primary Run

冻结：

```text
ONE_PRIMARY_RUN_PER_CASE = YES
```

如果一个 Case：

```text
第一次失败
第二次成功
```

然后只保存第二次结果，

真实 Failure Rate 就被洗掉了。

所以：

```text
第一次 business result
就是正式 result
```

------

# 三十二、k8s_1287 是 Phase4 最有价值的真实 Bad Case

真实执行：

```text
DocumentAnalysis = SUCCESS

RiskRetrieval =
FAILED
Schema Validation Error

TestReview =
FAILED
Invalid JSON

Workflow =
FAILED
```

没有 Retry。



最终：

```text
Workflow Success = 4 / 5
```

而不是做成：

```text
5 / 5 Demo
```

------

# 三十三、Environment Failure 和 Business Failure

### Environment Failure

例如：

```text
DNS
credential
connection
provider down
```

且发生在业务输出之前。

这种相当于：

> 实验还没真正开始。

### Business Failure

例如：

```text
invalid JSON
schema validation error
agent branch failed
```

说明：

> 系统已经真实执行，只是能力失败。

所以 `k8s_1287` 必须算：

```text
BUSINESS_RESULT
```

而不是 Environment Failure。

------

# 三十四、为什么失败 Case 不能所有指标算 0

这是 Phase4 最核心的 Metric Design（指标设计）。

`k8s_1287` 没生成 RiskFinding。

那就不存在：

```text
Citation Correctness = 0
```

正确状态应该是：

```text
Citation Correctness =
EXECUTION_FAILED
```

同样：

```text
RiskLevel =
EXECUTION_FAILED
```

而不是：

```text
wrong
```

所以：

```text
Execution Quality
```

和：

```text
Output Quality
```

必须分开。

------

# 三十五、为什么 E2E denominator 是 5，RiskLevel 是 4

E2E 衡量：

> 系统处理固定评测集的能力。

所以：

```text
denominator = 5
```

结果：

```text
4/5 = 0.8
```

RiskLevel 衡量：

> 实际生成有效 RiskLevel 的结果里有多少正确。

`k8s_1287` 根本没产生这个结果。

所以：

```text
2/4 = 0.5
```

而不是：

```text
2/5
```

------

# 三十六、文本指标为什么需要 Human Adjudication

Change Point / Risk Area / Coverage Gap 都不是 exact string match。

例如：

```text
invoke an external executable
```

和：

```text
exec-based credential provider
```

语义一致。

不能直接 string equality。

但 Phase4 也没使用 LLM-as-a-Judge。

因为只有 5 个 Case，人工成本可以接受，而且 Judge 本身还没被验证。

所以采用：

```text
Human 1:1 Matching
```

------

# 三十七、为什么一定是一对一

规则：

```text
一个 Prediction
最多匹配一个 Expected

一个 Expected
最多匹配一个 Prediction
```

防止一个泛化 Prediction：

```text
P0
```

同时匹配：

```text
GT0
GT1
GT2
```

然后凭一个预测拿三个 TP。

本质是避免：

### Double Counting（重复计数）

------

# 三十八、最终 Evaluation 指标

Phase4 的最终真实结果：

| Metric                    | Result    |
| ------------------------- | --------- |
| E2E Workflow Success      | **0.800** |
| Report Generation Success | **0.800** |
| Change Point F1           | **0.800** |
| Component F1              | **0.483** |
| Risk Area F1              | **0.421** |
| Historical Evidence@5 F1  | **0.286** |
| Historical Finding F1     | **0.667** |
| Coverage Gap F1           | **0.197** |
| Risk Level Accuracy       | **0.500** |
| Citation Correctness      | **0.571** |



这些是 Phase4 最需要记住的一组数字。

------

# 三十九、如何解读 Change Point F1 = 0.8

Aggregate：

```text
TP = 16
FP = 8
FN = 0

Precision = 0.667
Recall = 1.0
F1 = 0.8
```

说明：

> 所有人工定义的重要 Change Point 都被找到，但模型会额外生成一些变化点。

所以：

```text
Feature Understanding Recall 强
Precision 一般
```

核心问题：

### Over-generation（过度生成）

------

# 四十、Component 为什么只有 0.483

结果：

```text
Precision = 0.4
Recall ≈ 0.609
```

说明 Agent 往往把：

```text
API
library
subsystem
conceptual module
```

都列成 component。

而人工 GT 更强调：

```text
canonical engineering component
```

所以出现 Component Granularity（组件粒度）不一致。

------

# 四十一、Risk Area F1 = 0.421 怎么理解

```text
Precision ≈ 0.293
Recall = 0.75
```

这说明：

> 真正的核心风险大部分能覆盖，但模型会推导出大量额外风险。

所以当前不是：

```text
risk blind
```

而是：

```text
risk over-sensitive
```

这是非常典型的大模型风险分析行为。

------

# 四十二、Historical Retrieval 是 Phase4 的主要短板

结果：

```text
Historical Evidence Recall =
0.167
```

top-5 composition：

```text
KEP = 18
Issue Snapshot = 2
```



三个 Case：

```text
541
753
1602
```

top-5 全是 KEP。

说明 Lexical Retriever（词法检索器）更偏向：

```text
Feature itself
```

而不是：

```text
Historical Issues
```

我们把这个现象命名为：

### Self-KEP Dominance（自身 KEP 占优）

------

# 四十三、为什么 Historical Evidence Precision = 1 仍然很差

结果：

```text
TP=2
FP=0
FN=10

Precision=1.0
Recall=0.167
```

原因：

KEP 不属于 Historical Issue prediction，所以不会算 FP。

因此系统不是：

> 找了很多错误 Issue。

而是：

> **根本没找到大部分 Issue。**

所以看 Retrieval 时：

```text
Precision only
```

会严重误导。

------

# 四十四、为什么 Historical Finding F1 比 Retrieval 高很多

Finding：

```text
F1 = 0.667
Recall = 0.5
```

Retrieval：

```text
Recall = 0.167
```

说明：

```text
Evidence Acquisition
```

和：

```text
Risk Reasoning
```

是不同阶段。

因此一定要拆：

```text
Historical Evidence Metric
Historical Finding Metric
```

否则只能知道：

> 最终结果不好。

却不知道：

> 到底是 Retrieval 失败还是 Reasoning 失败。

------

# 四十五、Coverage Gap 是整个 Phase 最弱能力之一

结果：

```text
TP = 6
FP = 40
FN = 9

Precision ≈ 0.130
Recall = 0.4
F1 ≈ 0.197
```



最核心发现：

> **LLM 会生成大量合理测试建议，但合理建议不等于真实 Coverage Gap。**

例如：

```text
建议补 concurrency test
建议补 malformed JSON test
建议补 metric test
```

这些可能工程上都合理。

但 GT 要的是：

```text
某个历史 Bug 的 regression coverage
某个明确 upgrade gap
某个 source-backed failure path
```

所以很多 Prediction 最终是 FP。

------

# 四十六、为什么 Coverage 只能看 `potential_gaps`

TestReviewAgent 同时生成：

```text
potential_gaps
recommended_missing_cases
```

冻结 Metric 只评：

```text
potential_gaps
```

因为：

```text
recommended_missing_cases
```

属于 brainstorming / recommendation。

如果把它也拿来算预测：

模型生成越多建议，越可能撞中 GT，Recall 会被人为抬高。

------

# 四十七、RiskLevel 为什么只有 50%

成功 Case：

```text
541:
HIGH vs MEDIUM  ×

753:
HIGH vs HIGH    ✓

1472:
HIGH vs MEDIUM  ×

1602:
HIGH vs HIGH    ✓
```

结果：

```text
2 / 4 = 0.5
```

说明当前 deterministic risk policy 明显偏：

### Conservative / HIGH Bias（保守高风险偏置）

但是 Phase4 没有根据这些结果调 Policy。

所以：

```text
RISK_POLICY_CALIBRATED = NO
```

这是正确做法。

------

# 四十八、为什么不能看完这 5 个 Case 就调 Policy

如果：

```text
Evaluation Set
↓
看到答案
↓
调规则
↓
再评 Evaluation Set
```

Evaluation Set 已经变成：

```text
Training / Calibration Set
```

后面的 Accuracy 就失去独立性。

所以未来如果要校准：

```text
Calibration Set
→ Tune Policy
→ Independent Eval Set
```

这是正确流程。

------

# 四十九、Citation 系统最终评了什么

Phase3 已经保证：

```text
Citation Traceability
```

WP4 进一步评价：

```text
Citation Correctness
```

人工逐个判断：

```text
RiskFinding
↔
EvidenceRef
```

不是整篇报告整体判断。

------

# 五十、四级 Citation Rubric

```text
SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
UNVERIFIABLE
```

最终：

```text
SUPPORTED = 20
PARTIALLY_SUPPORTED = 11
UNSUPPORTED = 4
UNVERIFIABLE = 0
```

Primary Correctness：

```text
20 / (20 + 11 + 4)
= 20 / 35
≈ 0.571
```



------

# 五十一、为什么 `PARTIALLY_SUPPORTED` 不算 0.5

因为当前指标定义的是严格 Citation Correctness：

> Evidence 是否足够支持完整 Claim。

所以只有：

```text
SUPPORTED
```

算 numerator。

如果把 partial 算 0.5，需要重新定义另一种 weighted metric。

Phase4 没有这么做。

------

# 五十二、Citation Traceability ≠ Citation Correctness

例如：

```text
[C1]
```

能跳到真实 KEP section。

只说明：

```text
TRACEABLE
```

但 Finding 可能说：

```text
可能导致 cluster-wide outage
```

Evidence 只说：

```text
credential is cached
```

这只能：

```text
PARTIALLY_SUPPORTED
```

甚至：

```text
UNSUPPORTED
```

所以：

> 有 Citation 不等于 Citation 是对的。

------

# 五十三、人工 Adjudication 为什么也要做 Provenance

Phase4 最后真的因为这个被 BLOCK 一次。

最初 Artifact：

```text
confirmed by human
```

却同时又写：

```text
FINAL_HUMAN_CONFIRMATION_REQUIRED
```

而且：

```text
reviewed_at
```

早于 Prediction。

所以 Codex 判断：

```text
MANUAL_ADJUDICATION_INTEGRITY = FAIL
P1
```



------

# 五十四、最后怎么修复 Human Provenance

只允许修改：

```text
note
reviewer
reviewed_at
```

最终：

```text
FINAL_HUMAN_CONFIRMATION_COMPLETED

reviewer = GemHr

reviewed_at =
真实 Prediction 之后的时间
```

没有修改任何 verdict。

最终：

```text
MANUAL_ADJUDICATION_PROVENANCE = PASS
```



这里学到：

> **Audit Metadata is part of correctness.**

------

# 五十五、为什么最后还修了两个测试

两个旧测试仍然认为：

```text
Ground Truth = PENDING
No Adjudication exists
```

但真实 Phase 已经推进到：

```text
HUMAN_REVIEWED
Adjudication exists
```

导致：

```text
2 failed
```

最终判断：

```text
production implementation 没错
test assertion stale
```

只做 test-only remediation。

结果：

```text
128 passed
0 failed
```



------

# 五十六、这是一个非常好的工程面试案例

面试官问：

> 测试失败时，怎么判断应该改代码还是改测试？

可以说：

> 我先确认失败 assertion 对应的是 contract 还是某个历史 phase state。这个 Case 里 production validator 已经明确支持 HUMAN_REVIEWED 和正式 adjudication，失败测试还硬编码 PENDING/no-adjudication，所以属于 stale phase-state assertion。我只更新测试 expectation，没有为了让测试通过去修改 production contract。

------

# 五十七、整个 Phase4 最重要的架构思想

如果只能记一个：

> **把事实、推理、策略、评测四种 Authority 分开。**

具体：

```text
Source
→ Fact Authority

Agent
→ Reasoning Authority

Aggregator
→ Policy Authority

Ground Truth + Evaluator
→ Evaluation Authority
```

不要让任何一个 Owner 兼任全部角色。

------

# 五十八、第二个核心思想：阶段化评测

不要只评：

```text
Final Report Correct?
```

而是拆：

```text
Document Understanding
↓
Retrieval
↓
Risk Finding
↓
Test Coverage Review
↓
Risk Aggregation
↓
Citation Grounding
```

然后每阶段都有 Metric。

这样出现低分时才能定位。

------

# 五十九、第三个核心思想：Failure 是正式数据

Phase4 没有把：

```text
k8s_1287
```

从 Dataset 删除。

也没有：

```text
retry until success
```

失败本身就是：

```text
Evaluation Evidence
```

所以最终：

```text
Workflow Success = 80%
```

比虚构：

```text
100%
```

更有工程价值。

------

# 六十、第四个核心思想：Quality 不等于 Reliability

两个维度：

### Reliability

```text
Workflow Success
Report Generation
Schema Stability
```

### Quality

```text
Recall
Precision
F1
Citation Correctness
RiskLevel Accuracy
```

一个系统可以：

```text
100% 都跑成功
```

但内容全错。

也可以：

```text
质量不错
```

但 20% 调用失败。

这两个维度必须同时评。

------

# 六十一、第五个核心思想：Evaluation 本身也要被 Evaluation

Phase4 不只是：

```text
Evaluator 算完
→ 相信结果
```

而是：

```text
Evaluator
↓
Independent Aggregate Recompute
↓
Summary JSON consistency
↓
Markdown renderer consistency
↓
Codex Closure Gate
```

最终所有 Aggregate 都被独立复算。



这是：

### Evaluation-of-Evaluation（评测系统自审）

------

# 六十二、名词 / 概念速览

按照你的固定学习模板，每个只用一句话。

### Feature Risk Review（特性风险评审）

基于新功能文档、历史问题和现有测试覆盖，对潜在工程风险进行结构化分析。

### DocumentAnalysisAgent（文档分析智能体）

负责从 Feature Document 中提取 Feature Summary、Change Point、Component 和初步 Risk Area。

### RiskRetrievalAgent（风险检索智能体）

负责检索历史知识/问题，并基于真实 Evidence 推理 Risk Finding。

### TestReviewAgent（测试审核智能体）

负责分析已有 Test Plan / Test Case 并识别 Coverage Gap。

### FeatureRiskReviewWorkflow（特性风险评审工作流）

拥有三个 Agent 的编排、并行执行、分支状态和失败语义。

### Deterministic Aggregator（确定性聚合器）

根据固定 Policy 汇总 Agent Result，而不是再调用 LLM 进行最终裁决。

### EvidenceRef（证据引用）

用于稳定标识来源、路径、Section 和 Citation identity 的类型化证据对象。

### Partial Workflow（部分成功工作流）

部分 Agent 成功、部分 Agent 失败，但成功结果仍然保留。

### Ground Truth（真值）

人工基于权威 Source 冻结的期望结果。

### Freeze Manifest（冻结清单）

保存 Runtime、Dataset、Model、Policy 和 Ground Truth 等实验 Authority。

### One Primary Run（单次主运行）

每个 Evaluation Case 只保留第一次真实 Business Result。

### Business Failure（业务失败）

业务链路已经执行，但模型、Schema 或 Agent 输出失败。

### Environment Failure（环境失败）

业务输出产生之前因 Provider、网络、凭据等环境问题导致无法执行。

### Human Adjudication（人工裁决）

人工判断语义匹配或 Citation 支持关系。

### Metric Eligibility（指标适用性）

根据某个 Case 是否产生该阶段有效输出决定是否可以计算对应 Metric。

### Self-KEP Dominance（自身 KEP 占优）

Retrieval top-K 被 Feature 自身文档占据，导致 Historical Issue 召回不足。

### Over-generation（过度生成）

模型生成大量合理但不属于人工 Ground Truth 的额外内容。

### Citation Traceability（引用可追踪性）

Citation 能否稳定找到对应真实 Evidence。

### Citation Correctness（引用正确性）

当前 Evidence 是否真正支持该 RiskFinding。

### Provenance（溯源）

证明 Artifact 的来源、时间、Reviewer 和依赖关系。

### Calibration（校准）

使用独立数据调整 Risk Policy 或阈值，而不是直接在 Evaluation Set 上调参。

------

# 六十三、整个 Phase4 最值得准备的工程构建问题

## Q1：为什么三个 Agent，而不是一个？

回答重点：

> 文档理解、历史问题检索和测试覆盖属于不同知识源与职责，拆分后可以独立失败、独立观测、独立评测，也允许后两个分支并行。

------

## Q2：为什么不使用第四个 LLM Agent 生成最终报告？

> 最终 RiskLevel、Priority、Citation identity 和 Partial Failure 都属于系统 Policy，需要确定性和可复现性，因此用 deterministic aggregator，而不是让 LLM 再做一次开放式判断。

------

## Q3：为什么 Retrieval 和 TestReview 可以并行？

> 它们都依赖 DocumentAnalysis 输出，但彼此没有依赖，因此属于天然 fan-out / fan-in。

------

## Q4：为什么不直接接 LocalAgent Runtime？

> 会扩大到 Registry、Planner、Corpus 和 Runtime Contract 改造，而 Phase4 的业务 Owner 可以由 AgentEvalOps 自己承担；为了控制改造边界，保持 LocalAgent read-only。

------

## Q5：为什么 Ground Truth 和 Runtime Dataset 分文件？

> 为了从数据结构上阻断 Evaluation Label 进入 Runtime，提高 leakage resistance。

------

## Q6：为什么 RiskLevel 由 Aggregator 而不是 LLM 决定？

> RiskLevel 属于产品级决策 Policy，必须可解释、可回归、可校准。

------

## Q7：为什么 RiskLevel Accuracy 低还不修改 Policy？

> 因为当前 5 个 Case 已经是 Evaluation Set，直接调规则会造成 evaluation-set overfitting。

------

## Q8：为什么 Citation 要人工评？

> Stable Evidence ID 只能证明 traceability，不能证明 Claim 被 Evidence 支持，所以还需要 finding-evidence pair 级 correctness adjudication。

------

## Q9：为什么失败 Case 不重跑？

> Evaluation 的目标是观察真实系统可靠性；自动重跑会产生 survivorship bias。

------

## Q10：为什么 1287 不算 RiskLevel 错误？

> 因为根本没有生成 RiskLevel，应该记 execution failure，而不是 output-quality failure。

------

# 六十四、Phase4 的真实 Bad Cases

建议以后面试重点记这 6 个。

## 1. DeepSeek native structured output 不兼容

真实性：

**真实执行。**

根因：

```text
provider capability mismatch
```

修复：

```text
DeepSeek → json_text
```

------

## 2. k8s_1287 两个 downstream 同时模型输出失败

真实性：

**真实正式 Evaluation。**

Risk：

```text
Schema validation failure
```

Test：

```text
Invalid JSON
```

处理：

```text
不 Retry
保存 Business Failure
```

------

## 3. Self-KEP Dominance

真实性：

**真实 Evaluation 结果。**

```text
18 KEP
2 Issue
```

Historical Recall：

```text
0.167
```

------

## 4. Coverage Over-generation

真实性：

**真实 Evaluation。**

```text
TP=6
FP=40
F1≈0.197
```

------

## 5. Windows newline Artifact Bug

真实性：

**真实 WP3 Closure Review。**

Renderer string 和文件 bytes 不一致。

修复：

```text
newline=""
```

------

## 6. Human Adjudication Provenance 不合法

真实性：

**真实 WP4 Closure Gate。**

问题：

```text
reviewed_at before prediction
note contradictory
```

最终只修 Audit Metadata，不改 verdict。

------

# 六十五、Phase4 的最终系统强弱项

## 强项

### Change Point Understanding

```text
Recall = 1.0
F1 = 0.8
```

主要变化点覆盖很好。

------

### Workflow Architecture

```text
parallel branches
partial failure
typed contract
deterministic aggregation
```

架构边界较完整。

------

### Evaluation Integrity

```text
freeze
one-pass
human GT
human adjudication
independent recompute
```

可信度高。

------

# 六十六、中等能力

### Component

```text
F1 ≈ 0.483
```

粒度还不稳定。

### Risk Area

```text
F1 ≈ 0.421
```

Recall 尚可，但 FP 多。

### Historical Finding

```text
F1 ≈ 0.667
```

比 Retrieval 明显好。

### Citation

```text
Correctness ≈ 0.571
```

有实际 grounding，但 Claim 经常比 Evidence 更强。

------

# 六十七、明显弱项

### Historical Retrieval

```text
Recall ≈ 0.167
```

最大问题之一。

### Coverage Gap

```text
F1 ≈ 0.197
```

当前最明显的 over-generation 环节。

### RiskLevel

```text
Accuracy = 0.5
```

Policy 偏 HIGH，没有校准。

------

# 六十八、整个 Phase4 没有完成什么

这部分面试中一定要诚实。

没有完成：

```text
大规模 Dataset
Production deployment
Online Evaluation
LLM Judge
Semantic Auto Adjudication
Risk Policy Calibration
Risk Threshold Calibration
Priority Correctness
Citation Completeness
Token Usage Evaluation
Cost Evaluation
Statistical Confidence Interval
A/B Testing
Production Incident integration
真实企业 Test Case API
MCP
Semantic Memory
```

最终正式边界仍然：

```text
DATASET_SIZE = 5
PRODUCTION_CHANGE = NO
LOCALAGENT_WRITE = NONE
RISK_POLICY_CALIBRATED = NO
```



------

# 六十九、如果面试官让你 2 分钟介绍整个 Phase4

可以这样组织：

> 我在 AgentEvalOps 里实现过一个 Feature Risk Review 工作流，输入是真实 Kubernetes KEP。首先由 DocumentAnalysisAgent 提取功能变化，再并行执行 RiskRetrievalAgent 和 TestReviewAgent，分别检索历史问题和检查已有测试覆盖，最后不用第四个 LLM，而是用 deterministic aggregator 根据固定 Risk/priority policy 生成带 Citation 的风险报告。
>
> 我后面重点做了 Evaluation。5 个真实 Case 全部人工构建 Ground Truth，并在模型执行前冻结 Dataset、annotation、retrieval corpus、model config 和 policy。每个 Case 只允许一次 primary run，所以其中一个 Case 的真实 schema/JSON 输出失败被保留下来，最终 workflow success 是 4/5，而不是通过 retry 做成 100%。
>
> 质量上我分 stage 评估：Change Point F1 是 0.8；Historical Evidence recall 只有 0.167，暴露出 Retrieval 被自身 KEP 占据的问题；Coverage Gap F1 只有 0.197，说明 TestReviewAgent 会生成很多合理但不够 source-grounded 的建议；RiskLevel accuracy 是 0.5；Citation 通过人工 finding-evidence pair adjudication 后，strict correctness 大约 57%。
>
> 这部分我最看重的不是这些数字高不高，而是把 Source、Prediction、Policy、Ground Truth 和 Evaluation Authority 分开，并且保留失败 Case、固定 denominator 和 artifact provenance，让评测结果可以独立审计和复现。

这段基本就是 Phase4 的核心项目故事。

------

# 七十、如果面试官问：你觉得 Phase4 最大的工程价值是什么？

推荐答案：

> 最大价值不是多写了三个 Agent，而是第一次把多 Agent 输出做成了一个真正可评测、可审计的业务 Workflow。我可以明确知道问题出在 Document Understanding、Retrieval、Risk Reasoning、Test Coverage 还是 Citation，而不是只靠人工感觉报告“看起来不错”。同时冻结 Ground Truth 和 Runtime、保留 one-pass failure，让结果不会因为事后调参或 Retry 被美化。

------

# 七十一、如果面试官问：最大的不足是什么？

> 目前最大的问题是 Historical Retrieval 和 Coverage Gap Review。Retrieval top-5 中 20 条只有 2 条历史 Issue，Historical Evidence Recall 只有 0.167，说明 lexical retrieval 偏向 Feature 自身文档；Coverage Gap F1 只有约 0.197，主要是 TestReviewAgent 会过度生成很多合理建议。RiskLevel 也明显偏 HIGH，Accuracy 只有 0.5，而且还没有独立 Calibration Set，所以我没有在 Evaluation Set 上直接调 Policy。

------

# 七十二、Phase4 最值得背下来的真实数字

不用全部背小数。

推荐只记：

```text
Dataset              = 5 real cases

Workflow Success     = 4/5 = 80%

Change Point
F1                   = 0.80

Historical Retrieval
Recall                ≈ 0.17

Historical Finding
F1                   ≈ 0.67

Coverage Gap
F1                   ≈ 0.20

RiskLevel
Accuracy             = 50%

Citation Correctness ≈ 57%
```

这几个数字已经能完整讲出：

```text
哪里好
哪里差
为什么差
以后该往哪里优化
```

------

# 七十三、Phase4 最终知识体系图

建议你脑子里记成：

```text
                Feature Document
                       │
                       ▼
              Document Analysis
                       │
              ┌────────┴────────┐
              ▼                 ▼
      Historical Retrieval   Test Review
              │                 │
              └────────┬────────┘
                       ▼
              Risk Findings
                       │
                       ▼
          Deterministic Aggregator
                       │
                       ▼
             Citation Report
                       │
              ─────────────────
               Evaluation Layer
              ─────────────────
                       │
       Human Ground Truth / Freeze
                       │
                       ▼
               Real Prediction
                       │
                       ▼
             Human Adjudication
                       │
                       ▼
           Deterministic Metrics
                       │
                       ▼
          Independent Closure Gate
```

这基本就是整个 **Stage5-Phase4** 的完整工程图。

------

# 七十四、Phase4 最终结论

整个 Phase4 真正完成的是三层能力。

第一层是：

```text
Multi-Agent Feature Risk Review
```

能够基于真实 Feature Document，把：

```text
Change
Historical Risk
Existing Tests
Coverage Gap
```

组合成结构化报告。

第二层是：

```text
Evidence-grounded Reporting
```

RiskFinding 不只是自然语言，而是通过稳定 EvidenceRef 和 Citation 链接回真实来源。

第三层、也是含金量最高的一层是：

```text
Evaluation-Driven Engineering
```

我们没有用漂亮 Demo 证明系统“很好”，而是构建了可信实验以后发现：

```text
Change understanding strong
Risk generation over-sensitive
Historical retrieval weak
Coverage review over-generative
Risk policy uncalibrated
Citation grounding mixed
```

而且这些结论全部来自：

```text
Frozen source
Frozen GT
Frozen runtime
One-pass execution
Human adjudication
Deterministic evaluator
Independent review
```

所以整个 Phase4 最应该记住的一句话是：

> **我不仅实现了一个多 Agent 风险评审 Workflow，更建立了一套能真实发现该 Workflow 在 Retrieval、Risk Reasoning、Test Coverage 和 Citation Grounding 上质量问题的可审计 Evaluation Loop。**

这就是整个 Stage5-Phase4 最核心的项目价值。