当前使用的模型：**GPT-5.6 Sol**。

下面进入 **Stage5-Phase4-WP4：Real E2E Demo + Lightweight Evaluation（真实端到端演示与轻量评测）** 的学习/面试总结。本总结以这次真实完成的工程、实验和最终 Closure Gate（收口门禁）为准，不把尚未实现的能力包装成已完成。

推荐学习文档文件名：

```text
docs/interview/stage5_phase4_wp4_real_e2e_and_quality_evaluation.md
```

# 一、这个 WP 一句话怎么定义

WP4 的核心不是“把 Feature Risk Review 跑起来”，而是：

> **建立一个严格隔离 Ground Truth、真实模型 Prediction、人工 Adjudication 和最终 Quality Evaluation 的一次性评测闭环，并确保失败 Case、低分结果和未评指标都被如实保留。**

最终真实状态：

```text
Dataset Size              = 5
Real Case Count           = 5
Workflow Success          = 4/5
Report Generation         = 4/5

Change Point F1           = 0.800
Component F1              = 0.483
Risk Area F1              = 0.421
Historical Evidence F1    = 0.286
Historical Finding F1     = 0.667
Coverage Gap F1           = 0.197
Risk Level Accuracy       = 0.500
Citation Correctness      = 0.571
```

最终 Closure：

```text
WP4_FINAL_STATUS = COMPLETE_WITH_ACCEPTED_LIMITATIONS
P0 = 0
P1 = 0
P2 = 0
READY_FOR_PHASE5 = YES
```



------

# 二、为什么这个 WP 很有面试价值

如果只是做一个 Demo：

```text
Document
→ Agent
→ Report
```

面试官很容易继续问：

> 你怎么知道结果好不好？

再继续：

> Ground Truth 谁写的？

> Ground Truth 会不会看过模型输出？

> 模型失败了你重跑了吗？

> 失败 Case 是按 0 分，还是直接删掉？

> Citation 能找到来源就算正确吗？

> Risk Level 是怎么调出来的？

> 你是不是看完结果以后才改规则？

WP4 实际解决的就是这些问题。

它把系统从：

```text
“Agent 能运行”
```

推进到了：

```text
“Agent 的真实质量可以被审计”
```

这是 Evaluation Engineering（评测工程）和普通 Demo 最大的区别。

------

# 三、WP4 最核心的架构：四类 Authority 必须分开

这一 WP 最重要的知识点之一，就是**不要让一个对象同时拥有多个角色**。

整个评测链实际上有四类不同 Authority（权威来源）。

## 1. Source Authority

是真实 Kubernetes KEP、Issue、Test Plan 等源数据。

负责回答：

> 原始事实是什么？

------

## 2. Ground Truth Authority

由人工基于 Source 独立标注：

```text
expected_change_points
expected_components
expected_risk_areas
expected_historical_issue_ids
expected_coverage_gaps
expected_risk_level
```

负责回答：

> 我们认为正确答案是什么？

WP4 里 5 个 Case 最终全部：

```text
HUMAN_REVIEWED
GROUND_TRUTH_READY
```

而且在 Prediction 之前冻结。

------

## 3. Prediction Authority

来自真实运行：

```text
DocumentAnalysisAgent
RiskRetrievalAgent
TestReviewAgent
Aggregator
```

负责回答：

> 当前系统实际输出了什么？

Prediction 不能读取 Ground Truth。

------

## 4. Evaluation Authority

由：

```text
Frozen Prediction
+
Frozen Ground Truth
+
Human Adjudication
```

计算 Metric。

Evaluator 不负责“创造答案”，只负责：

```text
比较
计数
聚合
状态传播
```

------

# 四、为什么 Ground Truth 一定要先冻结

这是面试高频问题。

假设：

```text
先跑模型
↓
发现模型把 k8s_541 判 HIGH
↓
人工觉得 HIGH 好像也合理
↓
把 Ground Truth 从 MEDIUM 改成 HIGH
```

那这个评测已经失效了。

因为 Ground Truth 被 Prediction 影响。

这叫：

**Evaluation Leakage（评测泄漏）**。

所以这次采用：

```text
Human Annotation
↓
Validation
↓
GROUND_TRUTH_READY
↓
Manifest Freeze
↓
Prediction
```

而不是：

```text
Prediction
↓
Human Label
```

最终 Frozen Ground Truth digest 也被 Manifest 固定。

------

# 五、为什么还要 Freeze Runtime Manifest

只冻结 Ground Truth 还不够。

如果跑完两个 Case 后发现 Retrieval 不好：

```text
改 top_k
改 boost
改 prompt
↓
继续跑剩下 3 个
```

那么 5 个 Case 已经不是同一个系统版本。

所以 Manifest 还冻结：

```text
Git commit
Dataset digest
Annotation digest
Retrieval corpus digest
Model
Temperature
Structured output mode
Agent authority
Workflow authority
Aggregation policy
Risk policy
Priority policy
Retrieval configuration
```

这保证：

> 五个 Case 评的是同一个系统。

------

# 六、为什么必须 One Primary Run Per Case

本次冻结规则：

```text
ONE_PRIMARY_RUN_PER_CASE = YES
```

这是一个非常好的面试点。

例如：

```text
k8s_1287
```

真实运行中：

```text
DocumentAnalysis = SUCCESS
RiskRetrieval = FAILED
TestReview = FAILED
Workflow = FAILED
```

Risk branch 是 Schema Validation Failure，Test branch 是 invalid JSON。

如果这时候：

```text
重新跑一次
↓
第二次成功
↓
只保存成功结果
```

会产生 Survivorship Bias（幸存者偏差）。

系统实际可靠性被人为抹掉了。

所以：

```text
attempt = 1
```

必须保留。

最终：

```text
Workflow Success = 4 / 5
```

而不是：

```text
5 / 5
```

这比“全部成功”的 Demo 更可信。

------

# 七、Environment Failure 和 Business Failure 为什么一定要分开

这是 Runtime / Evaluation 系统里很重要的工程边界。

## Environment Failure

例如：

```text
DNS failure
API key missing
provider unavailable
connection failure
```

并且发生在**任何业务模型输出之前**。

可以认为：

> 实验没真正开始。

这种情况未来可以人工决定重试。

------

## Business Failure

例如这次：

```text
模型返回非法 JSON
模型输出不符合 Pydantic Schema
Agent branch FAILED
```

说明：

> 系统已经运行，只是系统能力失败了。

所以：

```text
k8s_1287 = BUSINESS_RESULT
```

不能改叫 Environment Failure。

面试中可以总结为：

> **环境失败是实验无法执行，业务失败是实验真实结果。**

------

# 八、为什么 Execution Metric 和 Quality Metric 必须分开

这是 WP4 最重要的设计之一。

例如：

```text
k8s_1287
workflow FAILED
```

它应该影响：

```text
E2E Workflow Success
Report Generation Success
```

所以：

```text
4 / 5
```

但它没有有效 RiskFinding，因此不能把：

```text
RiskLevel = wrong
Citation = wrong
Coverage Gap = wrong
```

强行记成 0。

正确做法是：

```text
risk_level = EXECUTION_FAILED
citation = EXECUTION_FAILED
coverage_gap = EXECUTION_FAILED
```



因此不同 Metric 有不同 denominator。

比如 RiskLevel：

```text
541   HIGH vs MEDIUM → wrong
753   HIGH vs HIGH   → correct
1287  EXECUTION_FAILED
1472  HIGH vs MEDIUM → wrong
1602  HIGH vs HIGH   → correct
```

结果是：

```text
2 / 4 = 0.5
```

而不是：

```text
2 / 5 = 0.4
```

------

# 九、为什么 Component 在 k8s_1287 还能评

这是一个很漂亮的 field-level availability（字段级可用性）案例。

`k8s_1287`：

```text
DocumentAnalysis = SUCCESS
```

所以它已经产生：

```text
affected_components
```

Component Metric 是 deterministic normalized-set matching（确定性归一化集合匹配），不依赖人工 Adjudication。

因此可以继续评。

但：

```text
Change Point
Risk Area
```

采用的是人工 1:1 matching。

1287 没有正常 adjudication，所以保持：

```text
NOT_EVALUATED
```

而不是强行计算。

Codex 最终确认这一语义合法。

------

# 十、文本类指标为什么不用 Embedding 自动 Judge

Change Point、Risk Area、Coverage Gap 都有一个问题：

语义等价不等于字符串完全一致。

比如：

```text
Prediction:
invoke an external binary for credentials
```

和：

```text
GT:
exec-based external credential provider
```

语义明显一样。

但如果用 exact match 会判错。

又不能简单让另一个 LLM 自动判：

```text
MATCH / NO_MATCH
```

因为这样会引入新的：

```text
Judge Bias
Judge Drift
Judge Prompt Dependency
```

所以当前 WP4 采用：

**Human-adjudicated 1:1 matching（人工裁决一对一匹配）**。

------

# 十一、为什么必须 1:1 Matching

假设 Prediction：

```text
P0:
exec provider introduces new configuration
and versioned ExecCredential API
```

它同时覆盖：

```text
GT0
GT1
```

如果允许：

```text
P0 → GT0
P0 → GT1
```

一个泛化 Prediction 就可以拿多个 TP。

Precision/Recall 会被人为抬高。

所以规则冻结为：

```text
一个 Prediction 最多 MATCH 一个 Expected
一个 Expected 最多 MATCH 一个 Prediction
```

本质上是在避免：

**semantic double counting（语义重复计数）**。

------

# 十二、Change Point 为什么表现最好

Aggregate：

```text
TP = 16
FP = 8
FN = 0

Precision = 0.667
Recall = 1.0
F1 = 0.8
```



含义不是：

> Agent 特别精准。

而是：

> **所有人工关键变化都被识别到了，但 Agent 会额外生成一些变化点。**

也就是说：

```text
High Recall
Medium Precision
```

典型问题：

**Over-generation（过度生成）**。

------

# 十三、Risk Area 的结果告诉了我们什么

结果：

```text
TP = 12
FP = 29
FN = 4

Precision ≈ 0.293
Recall = 0.75
F1 ≈ 0.421
```



很典型：

> 大部分真正风险能找到，但模型把很多“相关问题”也扩写成 Risk Area。

所以系统当前不是：

```text
risk blind
```

而是：

```text
risk over-sensitive
```

这种区别面试里非常值得讲。

------

# 十四、为什么 Historical Evidence 和 Historical Finding 要拆成两个指标

这是 WP4 最有技术含量的指标设计之一。

## Historical Evidence @5

评价：

> Retriever（检索器）有没有真的把历史 Issue 放进 top-5？

当前：

```text
TP = 2
FN = 10
Recall = 2 / 12 = 0.167
F1 = 0.286
```

------

## Historical Issue Finding

评价：

> 最终 RiskFinding 有没有识别到正确 historical issue ID？

当前：

```text
TP = 6
FN = 6
Recall = 0.5
F1 = 0.667
```



它们不是同一个阶段。

所以：

```text
Retrieval Recall = 0.167
Finding Recall = 0.5
```

完全可能同时成立。

------

# 十五、为什么 Historical Evidence Precision 是 1.0，但 Retrieval 其实很差

这是一个很适合面试追问的指标陷阱。

最终：

```text
Historical Evidence:
TP = 2
FP = 0
FN = 10

Precision = 1.0
Recall = 0.167
```

为什么 FP=0？

因为冻结 Metric 只把：

```text
github_enhancement_tracking_issue
kubernetes_issue_snapshot
```

作为 Historical Issue Prediction。

KEP section 不属于 Issue，所以不会作为 FP。

实际 top-5 composition：

```text
KEP = 18
Issue Snapshot = 2
```



所以真实问题不是：

> 检索到了很多错误 Issue。

而是：

> **基本没有检索到 Issue。**

因此：

```text
Precision 很高
Recall 极低
```

这就是为什么面试不能只报一个 Precision。

------

# 十六、Self-KEP Dominance 是什么问题

三个 Case：

```text
k8s_541
k8s_753
k8s_1602
```

top-5 全是自身 KEP。

只有：

```text
k8s_1472
```

出现：

```text
3 KEP
2 historical issue snapshot
```



这说明当前 lexical retrieval 更偏向：

```text
query 和 feature source 高词面相似
```

而不是：

```text
历史问题相关性
```

所以 Future Optimization 的方向可以是：

```text
source-aware retrieval
query decomposition
historical issue routing
metadata filtering
reranking
```

但注意：

**这些都不是 WP4 已完成内容。**

只是 Evaluation 暴露出来的未来方向。

------

# 十七、Coverage Gap 为什么是最弱指标之一

结果：

```text
TP = 6
FP = 40
FN = 9

Precision ≈ 0.130
Recall = 0.4
F1 ≈ 0.197
```



这是一个非常真实的大模型问题：

> **模型很擅长“提出测试建议”，但不等于识别真实 Coverage Gap。**

例如 TestReviewAgent 可能生成：

```text
建议补 malformed JSON 测试
建议补 timeout 测试
建议补 metrics 测试
建议补 concurrency 测试
```

这些建议听起来都合理。

但人工 Ground Truth 可能是：

```text
request cancellation propagation 未覆盖
upgrade-downgrade-upgrade 无实际执行证据
specific regression path 未覆盖
```

所以：

```text
reasonable suggestion
≠
grounded coverage gap
```

这句话很适合面试。

------

# 十八、为什么 Coverage Metric 只能用 potential_gaps

TestReviewResult 有：

```text
potential_gaps
recommended_missing_cases
```

如果把 `recommended_missing_cases` 也算 Prediction：

模型可以疯狂生成：

```text
20 个测试建议
```

只要碰巧覆盖 GT，就增加 Recall。

于是冻结规则明确：

```text
Coverage Prediction =
TestReviewResult.potential_gaps only
```

`recommended_missing_cases` 只是 recommendation，不属于已识别 gap。

这是非常典型的：

**Metric Boundary Design（指标边界设计）**。

------

# 十九、Risk Level 为什么只有 50%

当前：

```text
541   expected MEDIUM → predicted HIGH
753   HIGH → HIGH
1472  MEDIUM → HIGH
1602  HIGH → HIGH
```

准确率：

```text
2 / 4 = 0.5
```



从现象看，系统明显偏向：

```text
HIGH
```

也就是 Conservative Bias（保守偏置）。

但这里非常重要：

> WP4 没有根据这 5 个 Case 回头调整 Risk Policy。

所以最终仍然：

```text
RISK_POLICY_CALIBRATED = NO
```

这比把 Accuracy 调到 100% 更可信。

------

# 二十、为什么不能在 WP4 后直接改 Risk Policy

如果：

```text
看到 541 应该 MEDIUM
看到 1472 应该 MEDIUM
↓
修改 Risk Policy
↓
重新跑同样 5 个 Case
```

你得到的是：

**Training on Evaluation Set（在评测集上调参）**。

结果不能再视为独立 Evaluation。

正确流程应该是以后：

```text
Calibration Set
↓
Policy tuning
↓
Frozen Evaluation Set
```

但本 WP 没做 calibration。

所以：

```text
Risk Policy Calibrated = NO
```

必须如实保留。

------

# 二十一、Citation Traceability 和 Citation Correctness 的区别

这是本项目一个非常重要的面试知识点。

## Traceability

回答：

> `[C1]` 能不能找到对应 EvidenceRef？

比如：

```text
evidence_id
source_id
source_path
source_url
section
```

都存在。

说明：

```text
TRACEABLE
```

------

## Correctness

回答：

> 这个 Evidence 的内容真的支持 Finding 吗？

例如：

Finding：

```text
This may cause cluster-wide outage.
```

Evidence 只说：

```text
credential cached until expirationTimestamp
```

Evidence 能找到，但不能完整支持 Claim。

所以只能：

```text
PARTIALLY_SUPPORTED
```

因此：

```text
Traceable ≠ Correct
```

------

# 二十二、Citation Rubric 为什么设计四档

四档：

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

Citation Correctness：

```text
20 / (20 + 11 + 4)
= 20 / 35
≈ 0.571
```



注意：

```text
PARTIALLY_SUPPORTED
```

不是：

```text
0.5 分
```

Primary metric 里只有 `SUPPORTED` 进入 numerator。

这样标准更严格。

------

# 二十三、为什么 UNVERIFIABLE 不进入 denominator

如果 Evidence：

```text
source missing
identity broken
fragment truncated
```

人工无法判断。

这种情况和：

```text
UNSUPPORTED
```

不一样。

UNSUPPORTED 是：

> 我能看，而且它不支持。

UNVERIFIABLE 是：

> 我根本无法可靠判断。

所以单独统计，不进入 correctness denominator。

------

# 二十四、人工 Adjudication 为什么还要做 provenance

我们在最后 Closure Gate 真正遇到的 P1 就是这个问题。

最开始 4 份 adjudication：

```text
note:
confirmed by human
但同时又写
FINAL_HUMAN_CONFIRMATION_REQUIRED
```

并且：

```text
reviewed_at
早于 prediction finished_at
```

所以即使 verdict 本身都合法，也不能证明：

> 人工裁决发生在 Prediction 之后。

于是 Final Gate BLOCKED。

最终修复为：

```text
FINAL_HUMAN_CONFIRMATION_COMPLETED
reviewer = GemHr
reviewed_at = prediction 之后的真实时间
```

之后 provenance PASS。

这说明：

> Evaluation 不只是 Metric，还包括 Auditability（可审计性）。

------

# 二十五、为什么最后还因为两个 Unit Test 被 BLOCK

另一个很好的工程经验。

项目已经从：

```text
Ground Truth = PENDING
No Adjudication
```

推进到：

```text
Ground Truth = HUMAN_REVIEWED
Adjudication = EXISTS
```

但两个 Unit Test 还在断言旧 Phase 状态：

```text
必须全部 PENDING
不能存在 adjudication JSON
```

所以：

```text
2 failed
```

最终采用的是：

**Test-only remediation**。

不是为了让测试绿去改生产代码。

修复后：

```text
128 passed
0 failed
```



这个例子可以用来回答：

> “测试失败时，你怎么判断是实现错了还是测试过期了？”

------

# 二十六、本 WP 最值得记住的几个工程原则

建议你真正记住下面 10 条。

### 1.

```text
Evaluation cannot repair Runtime.
```

评测系统不能为了让 Runtime 成功去重试、修输出。

### 2.

```text
Ground Truth must not observe Prediction.
```

否则标签泄漏。

### 3.

```text
Prediction must not observe Ground Truth.
```

否则答案泄漏。

### 4.

```text
Execution failure != quality failure.
```

失败阶段不同，Metric eligibility 也不同。

### 5.

```text
One primary run means preserving bad cases.
```

不能挑最好的一次。

### 6.

```text
Traceable citation != correct citation.
```

引用可追溯不等于证据支持 Claim。

### 7.

```text
Reasonable recommendation != true coverage gap.
```

大模型特别容易在这里过生成。

### 8.

```text
Precision and Recall must be interpreted together.
```

Historical Retrieval 是非常典型案例。

### 9.

```text
Evaluation set must not become calibration set.
```

否则准确率没有意义。

### 10.

```text
Audit metadata is part of correctness.
```

没有 provenance 的“人工审核”不能称为可靠实验。

------

# 二十七、名词 / 概念速览

按照你的长期学习模板，这一节每个词只用一句话。

### Ground Truth（真值）

人工或权威来源定义的预期正确答案，用于和系统 Prediction 比较。

### Prediction（预测）

被冻结 Runtime 在一次正式执行中实际产生的业务输出。

### Adjudication（裁决）

对无法通过纯确定性规则判断的 Prediction 与 Ground Truth 关系进行人工判定。

### Evaluation Leakage（评测泄漏）

Ground Truth、Prediction 或 Evaluation 之间发生不应有的信息流，导致指标虚高。

### Freeze Manifest（冻结清单）

记录 Dataset、Runtime、Model、Policy 和 Ground Truth 等 Authority 的不可变实验快照。

### Primary Run（主运行）

一个 Case 被正式纳入 Evaluation 的唯一主要执行结果。

### Business Failure（业务失败）

系统已经开始产生业务行为，但 Agent/模型/Schema 等业务路径失败。

### Environment Failure（环境失败）

业务执行开始前因网络、凭据、Provider 等外部条件导致实验无法运行。

### Metric Eligibility（指标适用性）

某个 Case 是否具备计算特定 Metric 所需要的有效阶段输出。

### Precision（精确率）

所有系统预测为正的结果中，有多少是真正正确的。

### Recall（召回率）

所有应该被识别的目标中，有多少被系统成功找到了。

### F1 Score（F1 分数）

Precision 与 Recall 的调和平均，用来平衡两者。

### One-to-One Matching（一对一匹配）

一个 Prediction 最多匹配一个 Ground Truth，反向同样如此。

### Citation Traceability（引用可追踪性）

Citation 是否能稳定定位到对应 Evidence。

### Citation Correctness（引用正确性）

Evidence 内容是否真正支撑当前 Finding 的 Claim。

### SUPPORTED（完全支持）

Evidence 足以支持 Finding 的核心主张。

### PARTIALLY_SUPPORTED（部分支持）

Evidence 支持部分事实，但不足以覆盖 Finding 的完整主张。

### UNSUPPORTED（不支持）

Evidence 可读取，但并不能支持 Finding。

### UNVERIFIABLE（不可验证）

Evidence 本身因缺失、截断或 identity 问题无法可靠判断。

### Provenance（溯源）

记录一个 Artifact 由谁、何时、基于什么输入产生，从而支持独立审计。

### Deterministic Evaluation（确定性评测）

给定完全相同的输入与规则，每次运行都应产生完全相同的结果。

### Calibration（校准）

使用独立数据调整阈值、Risk Policy 等决策规则的过程。

### Over-generation（过度生成）

模型预测了大量合理但不属于目标 Ground Truth 的额外内容。

### Self-KEP Dominance（自身 KEP 占优）

Retriever top-K 被 Feature 本身的 KEP 大量占据，导致 Historical Issue 召回不足。

------

# 二十八、工程构建方法类面试题

下面这些问题比纯定义题更值得准备。

## Q1：为什么不让 LLM 自动 Judge Change Point？

推荐答题思路：

> 因为这样会引入第二个不可控模型，最终指标同时受被评模型和 Judge 模型影响。当前数据集只有 5 个 Case，所以我优先采用人工 1:1 adjudication，保证评测边界可解释。以后数据规模扩大可以引入 LLM Judge，但要先构建人工 gold set 验证 Judge agreement。

------

## Q2：为什么 Ground Truth 要在 Prediction 前冻结？

> 为了避免 label leakage。否则人工看完系统结果后可能无意识调整 expected label，使 Evaluation 变成事后解释。

------

## Q3：为什么 1287 失败不直接算所有指标 0 分？

> 因为执行失败和质量失败是两个维度。没有产生 RiskFinding，就不存在 Citation Correctness 这个观测值，正确状态是 EXECUTION_FAILED；但它仍然进入 E2E Success 的固定 denominator。

------

## Q4：为什么 E2E denominator 固定为 5，但 RiskLevel denominator 是 4？

> E2E 衡量系统处理固定 Evaluation Set 的可靠性，所以所有 Case 都必须算；RiskLevel 是业务质量指标，只能在实际产生有效 RiskLevel Prediction 的 Case 上计算。

------

## Q5：为什么 Historical Evidence Precision=1 不能说 Retriever 很好？

> 因为 Recall 只有 0.167。Retriever 很少返回 Historical Issue，所以没有产生错误 Issue FP，但绝大多数应召回的 Issue 根本没进 top-5。

------

## Q6：为什么 Historical Retrieval 和 Historical Finding 分开评？

> Retrieval 衡量 evidence acquisition，Finding 衡量 downstream reasoning。分开后才能定位问题到底出在“没找到证据”还是“找到后不会推理”。

------

## Q7：为什么 Coverage Gap Precision 很低？

> TestReviewAgent 倾向生成大量合理测试建议，但评测目标是 source-backed coverage gap，不是 brainstorming，所以很多看起来合理的建议最终属于 FP。

------

## Q8：Citation 为什么不用 Citation ID 是否存在作为正确率？

> 因为 ID 存在只能证明 traceability。Claim 可能比 Evidence 表达得更强，所以还需要人工判断 supported / partially supported / unsupported。

------

## Q9：为什么 RiskLevel Accuracy 只有 50% 还允许 WP4 PASS？

> WP4 的目标不是证明系统质量足够高，而是构建可信的 Evaluation Loop。低准确率是 Evaluation 成功暴露出的 Findings，不是 Evaluation Framework 自身失败。

------

## Q10：为什么评完后不立刻调 Risk Policy？

> 因为这 5 个 Case 已经是 Evaluation Set。如果根据它们调 Policy 再重新报告结果，会造成 evaluation-set overfitting。调参应该使用独立 Calibration Set。

------

# 二十九、方案取舍类问题

## “为什么不用 LLM-as-a-Judge？”

当前规模很小，人工裁决成本可接受，而且需要优先建立可信 Ground Truth。

未来扩展可以：

```text
Human Gold Set
↓
LLM Judge
↓
Judge Agreement Evaluation
↓
Human Spot Check
```

但本 WP 没做。

------

## “为什么不用 Embedding similarity 自动匹配文本？”

Embedding 能提供 semantic similarity，但很难确定：

```text
0.72 是 MATCH？
0.78 呢？
```

阈值本身需要 Calibration。

当前没有校准集，所以用 Human 1:1 match 更可信。

------

## “为什么不直接跑 100 个 Case？”

因为当前重点是：

```text
Evaluation contract
data isolation
failure semantics
metric correctness
auditability
```

先把 5 Case 的闭环做对，比快速放大到 100 Case 但评测逻辑不可信更有价值。

同时要诚实说明：

```text
DATASET_SIZE = 5
```

无法做统计泛化。

------

# 三十、本 WP 真实 Bad Case

面试里建议至少记住 4 个。

## Bad Case 1：k8s_1287 模型结构化输出失败

真实性：

**真实执行发现。**

Risk branch：

```text
schema validation failure
```

Test branch：

```text
invalid JSON
```

结果：

```text
workflow FAILED
```

处理：

```text
不重跑
不修 JSON
attempt=1 保留
```

知识点：

```text
one-pass evaluation
business failure
execution-quality separation
```

------

## Bad Case 2：Historical Retrieval 被 Self-KEP 占据

真实性：

**真实 Evaluation 发现。**

结果：

```text
18 KEP
2 Issue Snapshot
```

Historical Evidence Recall：

```text
0.167
```

知识点：

```text
retrieval bias
source distribution
precision/recall interpretation
```

------

## Bad Case 3：Coverage Gap 大量 Over-generation

真实性：

**真实 Evaluation 发现。**

结果：

```text
TP=6
FP=40
F1≈0.197
```

知识点：

```text
reasonable generation != grounded finding
metric boundary
precision failure
```

------

## Bad Case 4：人工审核 metadata 破坏 provenance

真实性：

**真实 Closure Gate 发现。**

问题：

```text
reviewed_at 早于 prediction
final confirmation note 自相矛盾
```

虽然 verdict 本身没问题，仍然：

```text
P1 BLOCKED
```

修复：

只修改：

```text
note
reviewer
reviewed_at
```

没有修改业务 verdict。

知识点：

```text
auditability
artifact provenance
evaluation integrity
```

------

# 三十一、面试中怎么描述“最大的系统问题”

如果问：

> 这一轮评测发现你系统最大的不足是什么？

可以回答：

> 目前最明显的不是 Feature Change 理解，而是 Retrieval 和 Test Coverage Review。Change Point F1 达到 0.8，Recall 是 1.0，说明文档理解能力相对稳定；但 Historical Evidence Recall 只有 0.167，top-5 中 20 条证据有 18 条都是 KEP，说明 lexical retrieval 明显偏向 feature source，而没有有效拉出历史 Issue。另一方面 Coverage Gap F1 只有约 0.197，主要因为 TestReviewAgent 会生成很多合理但不够 source-grounded 的测试建议。这个评测让我能够把问题定位到具体 stage，而不是只说最终报告质量不好。

这个回答非常适合 1～3 年 Agent 工程岗位。

------

# 三十二、如果问“Citation 做得怎么样”

可以回答：

> 我们先实现了 Citation Traceability，保证每个 EvidenceRef 有稳定 identity、source path、URL 和 section。但后面没有把“能追踪”直接当“正确”，而是做了 finding-evidence pair 级人工 adjudication。最终 35 个可验证 Citation pair 中 20 个完全支持、11 个部分支持、4 个不支持，所以严格 Citation Correctness 是 20/35，大约 57%。这个结果说明模型大部分并不是完全 hallucination，而是经常从正确事实进一步扩展出 Evidence 没完全支撑的风险结论。

这是一个很好的面试答案。

------

# 三十三、如果问“你 Evaluation 平台最大的设计思想是什么”

建议回答：

> 我最大的原则是把 Execution、Ground Truth、Prediction 和 Evaluation Authority 分开。Ground Truth 在模型执行前人工冻结；Runtime 通过 Manifest 冻结；每个 Case 只保留一次 Primary Run；环境失败和业务失败分开；失败 Case 仍进入 E2E denominator，但没有可用业务输出的质量指标标 EXECUTION_FAILED，而不是强行算 0。这样最终结果可能不好看，但每个数字都可以追溯到 frozen artifact。

------

# 三十四、本 WP 没有完成什么

这一段必须记牢，避免面试越界。

没有完成：

```text
大规模 Evaluation Dataset
LLM Judge
自动 Semantic Matching
Risk Policy Calibration
Production Risk Threshold
Priority Correctness Evaluation
Citation Completeness Evaluation
Token Usage Evaluation
Cost Evaluation
Statistical Confidence Interval
Online Evaluation
A/B Experiment
Production deployment
```

最终仍明确：

```text
RISK_POLICY_CALIBRATED = NO
PRIORITY_CORRECTNESS = NOT_EVALUATED
CITATION_COMPLETENESS = NOT_EVALUATED
TOKEN_USAGE = NOT_EVALUATED
COST = NOT_EVALUATED
PRODUCTION_CHANGE = NO
```



------

# 三十五、简历上怎么压缩成 2～3 条

以后真正整理简历时可以进一步打磨，目前建议表述方向：

> **构建 Feature Risk Review 离线评测闭环**：基于 5 个真实 Kubernetes Enhancement Case 建立 Human-reviewed Ground Truth、Runtime Manifest Freeze、one-pass real model execution、人工 1:1 adjudication 与 deterministic evaluator，隔离 Ground Truth / Prediction / Runtime authority，并区分 execution failure 与 quality failure。

> **设计多阶段质量指标体系**：覆盖 Change Point、Component、Risk Area、Historical Evidence@5、Historical Issue Finding、Coverage Gap、Risk Level 与 Citation Correctness；真实评测中 Change Point F1=0.80，Historical Evidence Recall=0.167，Coverage Gap F1=0.197，定位 Retrieval self-KEP dominance 与 TestReview over-generation。

> **建立可审计 Evaluation Gate**：保留 1/5 真实模型结构化输出失败 Case，不自动 retry；通过 artifact digest、human adjudication provenance、per-case/aggregate deterministic recomputation 和 independent closure review 保证评测结果可复现、不可事后调参。

数字是真实结果，可以讲。

------

# 三十六、这一 WP 你面试前最少要背下来的内容

如果时间有限，只记下面这 8 个点：

1. **Ground Truth 必须在 Prediction 前冻结。**
2. **Runtime 也通过 Manifest 冻结，保证所有 Case 是同一版本。**
3. **每 Case One Primary Run，Business Failure 不重跑。**
4. **Execution Failure 和 Quality Failure 分开。**
5. **Change Point / Risk Area / Coverage Gap 使用人工 1:1 Matching。**
6. **Historical Retrieval 与 Historical Finding 分 stage 评估。**
7. **Citation Traceability ≠ Citation Correctness。**
8. **Evaluation Set 不能看完结果后直接拿来 Calibration。**

再记三个最关键数字：

```text
Workflow Success          = 4/5
Change Point F1           = 0.80
Historical Recall         = 0.167
Coverage Gap F1           = 0.197
Citation Correctness      = 0.571
```

其实是五个数字，但这五个组合起来就能把整个 WP 的强项和弱项讲清楚。

------

# 三十七、最终学习结论

WP4 真正完成的不是“一个评测脚本”，而是一个小型、但边界完整的 **Evaluation Lifecycle（评测生命周期）**：

```text
Source
→ Human Ground Truth
→ Validation
→ Freeze
→ Real Execution
→ Prediction Artifact
→ Independent Integrity Review
→ Human Adjudication
→ Deterministic Evaluation
→ Independent Aggregate Review
→ Closure Gate
```

它最有价值的地方是：

> **系统没有通过 Evaluation 来证明自己优秀，而是通过 Evaluation 明确知道自己哪里优秀、哪里不足，以及这些结论为什么可信。**

从面试角度看，这已经比“我做过 RAG，然后测了一下 Recall@K”高一个层级，因为你可以讨论：

```text
data leakage
experiment authority
failure semantics
denominator design
human adjudication
citation grounding
retrieval-vs-reasoning stage separation
calibration boundary
artifact provenance
reproducibility
```

这些都是生产级 Agent Evaluation 非常核心的问题。