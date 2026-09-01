# Stage5-Phase4-WP3 学习 / 面试总结

## Risk Aggregation + Citation Report（风险聚合与引用报告）

WP3 解决的是一个和 WP2 完全不同的问题。

WP2 已经证明：

> 三个 Agent 能基于真实 Kubernetes 数据、真实 DeepSeek、真实 Retrieval/TestReview 完成 typed workflow。

WP3 则进一步回答：

> **多个 Agent 已经产生事实和推断之后，最终面向用户的风险等级、处理优先级、引用、完整性和 Markdown 报告，到底应该由谁决定？**

最终选择没有增加第四个 LLM Agent，而是建立：

```text
FeatureRiskReviewWorkflowResult
        ↓
FeatureRiskReviewAggregator
        ↓
FeatureRiskReviewReport
        ↓
render_feature_risk_review_markdown()
        ↓
Markdown Artifact
```

其中 Aggregator（聚合器）是确定性业务 Policy Owner（策略所有者），Markdown Renderer（渲染器）只是展示层。这个设计经过 Architecture Decision、实现、Final Review、真实 artifact smoke、Independent Result Review，以及一次真实 Windows newline serialization Bad Case 修复后最终收口。

------

# 1. WP3 最终真实完成状态

最终可以准确表述为：

```text
WP3_STATUS = COMPLETE

RISK_AGGREGATION_IMPLEMENTED = YES
FINAL_RISK_LEVEL_IMPLEMENTED = YES
PRIORITY_IMPLEMENTED = YES

TYPED_FEATURE_RISK_REVIEW_REPORT = YES
MARKDOWN_RENDERER = YES
PARTIAL_REPORT_SUPPORTED = YES

REAL_REPORT_ARTIFACT_GENERATED = YES

CITATION_TRACEABILITY = IMPLEMENTED
CITATION_CORRECTNESS = NOT_EVALUATED
CITATION_COMPLETENESS = NOT_EVALUATED

RISK_POLICY_CALIBRATED = NO
GROUND_TRUTH = PENDING
QUALITY_EVALUATION = NOT_RUN

REAL_MODEL_EXECUTION_IN_WP3 = NO
RETRIEVAL_EXECUTION_IN_WP3 = NO

PRODUCTION_CHANGE = NO
LOCALAGENT_WRITE = NONE
```

最终真实 `k8s_541` Report Smoke 得到：

```text
COMPLETENESS = FULL
RISK_LEVEL = HIGH
PRIORITY = ACT_NOW
COVERAGE_STATE = PLAN_ONLY

RISK_FINDINGS = 6
HISTORICAL_ISSUES = 1
TEST_PLANS = 1
TEST_CASES = 0
RECOMMENDED_MISSING_CASES = 10

EVIDENCE_COUNT = 7
```

但 `HIGH / ACT_NOW` 只是当前 deterministic heuristic（确定性启发式）对真实输入的输出，**不是 Ground Truth，也不是已经验证正确的风险评级**。

------

# 2. 名词 / 概念速览

| 名词                                  | 一句话理解                                                   |
| ------------------------------------- | ------------------------------------------------------------ |
| Aggregation（聚合）                   | 把多个 Agent 的 typed result 按固定业务规则组合成最终业务结果。 |
| Aggregator（聚合器）                  | WP3 中负责 RiskLevel、Priority、Completeness 等确定性决策的业务组件。 |
| Deterministic Policy（确定性策略）    | 相同输入必然产生相同结果，不依赖 LLM 随机生成。              |
| Heuristic（启发式规则）               | 人工设计、可解释但尚未经过统计校准的业务判断规则。           |
| Calibration（校准）                   | 用真实标注数据验证、调整 threshold 或 policy，使输出和真实目标对齐。 |
| RiskLevel（风险等级）                 | 表示当前已观察到的风险程度，本 WP 为 LOW / MEDIUM / HIGH。   |
| Priority（处理优先级）                | 表示下一步应该怎样处理，不等价于 RiskLevel。                 |
| ReportCompleteness（报告完整性）      | 表示 Risk/Test 分支是否都可用，例如 FULL 或部分分支不可用。  |
| Policy Owner（策略所有者）            | 唯一负责某个业务结论生成规则的组件。                         |
| Evidence Identity（证据身份）         | `EvidenceRef` 的稳定身份，由 Provider/Retriever 创建。       |
| Citation Traceability（引用可追溯性） | 报告中的引用可以解析回真实 EvidenceRef。                     |
| Citation Correctness（引用正确性）    | 判断引用证据是否真的支持该 Claim，WP3 未评测。               |
| Renderer（渲染器）                    | 把 typed report 转为 Markdown，不应该重新做业务决策。        |
| Source Preservation（来源保真）       | WP3 不改写 WP2 已有事实，只做聚合、排序和展示。              |
| Fail Closed（失败关闭）               | 数据完整性冲突时直接失败，而不是猜测、覆盖或修复。           |
| Artifact Provenance（产物溯源）       | 能追踪某个最终 Artifact 来源于哪个上游真实 Artifact。        |
| Round-trip Equality（往返等价）       | 输出写入磁盘再读取后必须与原始输出完全一致。                 |

------

# 3. WP3 最核心的架构决策：为什么没有第四个 Agent

最直观的方案其实是：

```text
DocumentAgent
RiskAgent
TestAgent
        ↓
ReportAgent
        ↓
Final Report
```

但 Codex 最终明确否决了这个方案，选择：

```text
AGGREGATION_OWNER =
FeatureRiskReviewAggregator
```

并冻结：

```text
FOURTH_LLM_AGENT = NO
```



原因非常重要。

前三个 Agent 已经完成了真正需要 LLM reasoning（推理）的部分：

- Feature understanding；
- Risk inference；
- Coverage reasoning。

最终 Risk Level、Priority、Citation assembly 属于：

> **业务 Policy，而不是新的开放式语言推理。**

如果再交给 ReportAgent：

```text
已有 Findings
        ↓
LLM
        ↓
“我觉得整体 HIGH”
```

就会出现几个问题：

- 同样输入可能生成不同结果；
- Final RiskLevel 很难回归测试；
- LLM 可能重新创造 Citation；
- Agent inference 和 Business Policy 混在一起；
- 未来 Evaluation 很难定位到底是谁造成错误。

所以 WP3 采用：

> **LLM 负责生成不确定性和推断，确定性代码负责最终业务决策。**

------

# 4. 这是一个非常重要的 Agent 工程分层

最终系统可以分成三层：

## 第一层：Source Fact（来源事实）

例如：

```text
HistoricalIssue
EvidenceRef
TestPlan
TestCase
retrieved evidence
```

它们来自 Provider / Retriever。

------

## 第二层：Agent Inference（Agent 推断）

例如：

```text
Feature Summary
Change Points
RiskFinding
coverage_assessment
potential_gaps
recommended_missing_cases
uncertainty
```

由三个 Agent 基于 Source Fact 产生。

------

## 第三层：Aggregation Policy Output（聚合策略输出）

例如：

```text
RiskLevel
Priority
ReportCompleteness
scenario ordering
uncertainty summary
```

由 deterministic Aggregator 产生。

这三个 Authority（权威来源）不能互相越权。

------

# 5. 面试中如何解释这个三层设计

可以直接回答：

> 我把系统事实、LLM 推断和最终业务 Policy 分开。HistoricalIssue、EvidenceRef、TestPlan 这些是 Provider 的事实；RiskFinding 和 Coverage Gap 是 LLM inference；最终 RiskLevel 和 Priority 不让 LLM 再自由生成，而由 deterministic Aggregator 根据 typed result 计算。这样可以知道每个结论到底由谁负责，也便于回归和 Evaluation。

这比简单说“用了 Structured Output”更有工程含量。

------

# 6. Risk Policy 为什么不能让 LLM 直接判断 HIGH / MEDIUM / LOW

因为当前 Ground Truth 还没有完成：

```text
GROUND_TRUTH = PENDING
```

如果直接让 LLM 生成：

```json
{
  "risk_level": "HIGH"
}
```

你很难回答：

> 为什么 HIGH？

而当前 Aggregator 可以明确解释：

```text
6 accepted risk findings
+
historical issue reference
+
potential gaps
+
PLAN_ONLY
→ 根据 Rule 3
→ HIGH
```

这叫：

**Explainable Policy（可解释策略）。**

------

# 7. Risk Policy 的最终规则

Codex Architecture Decision 冻结了一套非常谨慎的离散规则。

## Rule 1：Risk branch 缺失

```text
Risk branch unavailable
→ risk_level = None
```

绝不能：

```text
没有检索到风险
→ LOW
```

尤其当 Risk Agent 根本没执行时。

------

# 8. Rule 2：Test branch 缺失

Risk Agent 成功但 TestReview 失败时：

```text
risk_level ∈ {HIGH, MEDIUM}
```

绝不能 LOW。

实际实现具体化为：

```text
>= 2 accepted findings
+
historical issue reference
→ HIGH

otherwise
→ MEDIUM
```

Codex Final Review 专门审查了这项 concretization（具体化），最终：

```text
RULE2_CONCRETIZATION = ACCEPTED
```



------

# 9. Rule 3：HIGH

两个 downstream 都成功时：

```text
accepted findings >= 2
AND
(
    historical issue reference exists
    OR coverage_state == NO_TEST_DATA
    OR potential_gaps non-empty
)
→ HIGH
```

注意：

不是：

```text
finding >= 2
→ HIGH
```

还要求额外风险信号。

------

# 10. Rule 4：MEDIUM

只要存在任一：

```text
accepted finding
potential gap
NO_TEST_DATA
PLAN_ONLY
document uncertainty
risk uncertainty
test uncertainty
```

就至少：

```text
MEDIUM
```

这体现的是：

> **存在未解决信息或风险信号时，不能轻易给 LOW。**

------

# 11. Rule 5：LOW 为什么非常严格

只有全部满足：

```text
Risk SUCCESS
Test SUCCESS

findings == 0
potential_gaps == []

coverage_state == COVERED

document uncertainty empty
risk uncertainty empty
test uncertainty empty
```

才允许：

```text
LOW
```

也就是说：

> LOW 不是“没发现东西”，而是“当前证据比较完整，并且没有发现风险”。

这对应一个非常重要的工程原则：

> **Absence of evidence（缺少证据）不等于 evidence of absence（证明不存在）。**

------

# 12. Rule 6：后来为什么有一个保守兜底

实现过程中 ZCode 增加：

```text
PARTIAL_COVERAGE
+
no findings
+
no gap
+
no uncertainty
→ MEDIUM
```

Architecture Decision 没明确列这条。

所以 Codex Final Review 特别做了审核。

最终：

```text
RULE6_CONFORMANCE =
ACCEPTED_CONSERVATIVE_DEFAULT
```



原因是如果不处理：

```text
PARTIAL_COVERAGE
```

会进入一个没有明确 RiskLevel 的状态。

默认 LOW 又违反：

> explicit uncertainty > confident LOW

所以 MEDIUM 是一个保守的 deterministic fallback。

------

# 13. Risk Policy 为什么不是“模型”

当前必须明确：

```text
RISK_POLICY_TYPE =
deterministic transparent heuristic

RISK_POLICY_CALIBRATED =
NO
```



不要在面试说：

> “我构建了一个风险评分模型。”

没有。

现在只是：

> **一套透明、离散、可测试的 Demo Policy。**

------

# 14. 为什么没有做 risk_score = 0.73

很容易有人想设计：

```text
RiskScore =
0.4 * findings
+ 0.3 * historical
+ 0.2 * coverage
+ 0.1 * uncertainty
```

但这些权重没有真实数据来源。

如果只有五个 Case，就人为创造：

```text
0.37
0.21
0.18
```

会形成：

**False Precision（伪精确）。**

所以当前选择：

```text
少量可解释 if/else rule
```

反而更可信。

------

# 15. Priority 为什么不能等于 RiskLevel

这是 WP3 第二个很重要的设计。

Risk Level 回答：

> “风险有多高？”

Priority 回答：

> “接下来应该怎么处理？”

因此 Priority 最终不是：

```text
HIGH → P0
MEDIUM → P1
LOW → P2
```

而是：

```text
COMPLETE_REVIEW
ACT_NOW
SCHEDULE_REVIEW
MONITOR
```



------

# 16. Priority Policy

## Partial Report

任何可交付的 Partial Report：

```text
priority =
COMPLETE_REVIEW
```

即使现有 Risk Agent 输出已经 HIGH。

这是非常重要的设计。

因为：

> 审查都没有完成，就不应该把不完整信息包装成最终操作结论。

------

## Full + HIGH + Coverage Gap

```text
FULL
+
HIGH
+
(NO_TEST_DATA or potential_gaps)
→ ACT_NOW
```

------

## 其他 HIGH / MEDIUM

```text
→ SCHEDULE_REVIEW
```

------

## LOW

```text
→ MONITOR
```

所以：

> Priority 与 Risk Level 相关，但不是一对一映射。

------

# 17. 为什么 Partial HIGH 不是 ACT_NOW

假设：

```text
Risk Agent = HIGH
Test Agent = FAILED
```

如果输出：

```text
ACT_NOW
```

用户可能理解：

> “系统已经完成评审并确认必须立即处理。”

但实际上：

> Test Coverage 根本没分析完。

因此：

```text
COMPLETE_REVIEW
```

更诚实。

------

# 18. ReportCompleteness 为什么是独立字段

最终新增：

```text
FULL
PARTIAL_RISK_UNAVAILABLE
PARTIAL_TEST_UNAVAILABLE
```



这个字段表达：

> 报告业务输入是否完整。

而不是：

> 报告质量好不好。

所以：

```text
FULL
```

只意味着：

> 三个 WP2 branch 都成功。

不能解释成：

```text
Evaluation complete
Citation verified
Production ready
```

------

# 19. FAILED Workflow 为什么不能生成一个全 None Report

一种很常见的错误设计：

```json
{
  "risk_level": null,
  "historical_issues": [],
  "coverage": [],
  "priority": null
}
```

然后还是把它叫：

```text
FeatureRiskReviewReport
```

这样用户无法知道：

> “是真的什么都没有？”

还是：

> “系统失败了？”

所以 WP3 对 FAILED input 返回：

```text
FeatureRiskReviewAggregationFailure
```

而不是 Completed Report。

这叫：

> **Failure State 和 Empty Business Result 必须区分。**

------

# 20. Partial Result 又为什么允许生成 Report

例如：

```text
Risk failed
Test succeeded
```

此时仍然有业务价值：

```text
Feature Summary
Existing Test Plan
Coverage Assessment
Missing Recommendations
```

所以可以生成：

```text
PARTIAL_RISK_UNAVAILABLE
```

但 Risk section 必须明确：

```text
Unavailable
```

不能留一个空数组，让人误解为：

```text
No risk found
```

Codex Final Review 已确认这条语义 PASS。

------

# 21. Citation 在 WP3 中到底做了什么

WP2 已经解决：

> Evidence identity 从哪里来？

WP3 只解决：

> 如何聚合并展示这些已有 Evidence。

冻结：

```text
CITATION_OWNER =
FeatureRiskReviewDataProvider /
HistoricalKnowledgeRetriever

AGGREGATOR_CITATION_ROLE =
consume + deduplicate + group + render
```



Aggregator 不能创建：

```text
evidence_id
source_url
source_id
issue_id
```

------

# 22. Citation 去重为什么按 evidence_id

多个 Finding 可能引用同一个 Evidence：

```text
Finding A → Evidence X
Finding B → Evidence X
HistoricalIssue → Evidence X
```

最终 Report 不需要重复保存三份 X。

所以：

```text
dedup key = evidence_id
```

------

# 23. 同一个 evidence_id 对应不同对象怎么办

不能：

```text
first wins
last wins
merge
```

因为这意味着 Evidence Identity 已经发生冲突。

所以最终：

```text
same evidence_id
+
different EvidenceRef
→ aggregation failure
```

Codex 确认：

```text
CITATION_CONFLICT_BEHAVIOR = FAIL_CLOSED
```



------

# 24. 这个设计像什么

很像数据库：

```text
PRIMARY KEY = evidence_id
```

如果同一个 PK 对应两份完全不同的数据：

> 这是数据完整性错误。

系统不应该“聪明地挑一个”。

------

# 25. Markdown Citation Label 为什么不是 Evidence Identity

最终 Markdown：

```text
[C1]
[C2]
...
[C7]
```

只是展示标签。

真实 Authority 仍然：

```text
EvidenceRef.evidence_id
```

因此：

```text
[C3]
```

可以因为排序变化变成：

```text
[C4]
```

但 Evidence identity 不应该变化。

------

# 26. 最终真实 Report 有多少 Citation

真实 smoke：

```text
REPORT_EVIDENCE_COUNT = 7
MARKDOWN_UNIQUE_CITATION_LABEL_COUNT = 7
CITATION_LABEL_RESOLUTION = PASS
```

修复后的 Narrow Re-review 再次确认这一点。

------

# 27. 为什么 Citation Resolution PASS 仍然不是 Citation Correctness

现在只证明：

```text
RiskFinding
→ [C3]
→ EvidenceRef X
```

是真实可追溯链路。

但是还没有证明：

> Evidence X 的内容真的支持这个 Risk Finding。

因此继续：

```text
CITATION_TRACEABILITY = IMPLEMENTED
CITATION_CORRECTNESS = NOT_EVALUATED
CITATION_COMPLETENESS = NOT_EVALUATED
```



------

# 28. Structured Report 为什么必须比 Markdown 更权威

最终：

```text
FeatureRiskReviewReport
```

才是 Authority。

Markdown 是：

```text
render(report)
```

如果以后：

- API；
- Evaluation；
- Dashboard；
- Export；

需要结果，都应该使用 typed report。

而不是反向解析 Markdown。

------

# 29. 为什么 Markdown 不应该由 LLM“润色”

如果：

```text
Typed Report
→ LLM rewrite
→ Markdown
```

模型可能：

- 修改 RiskLevel；
- 合并 Finding；
- 漏掉 uncertainty；
- 增加不存在的 Citation；
- 把 recommendation 变成事实。

所以 WP3 使用：

```text
pure deterministic renderer
```



------

# 30. Renderer 应该做什么，不应该做什么

应该：

```text
格式化
section ordering
citation label mapping
human-readable wording
```

不应该：

```text
业务推理
Risk Level 修改
Priority 修改
Evidence 创建
Risk Finding 改写
```

这是：

> **Presentation Layer（展示层）不拥有 Business Semantics（业务语义）。**

------

# 31. Report Contract 做了哪些最小扩展

Architecture Decision 没创建 `ReportV2`。

而是在现有 `FeatureRiskReviewReport` 上做 minimal extension：

```text
case_id
priority
completeness

existing_test_cases
coverage_state
coverage_assessment
potential_gaps

unavailable_sections
uncertainties
```

同时保留原来的：

```text
feature_summary
change_points
high_risk_scenarios
historical_issues
existing_coverage
missing_cases
risk_level
evidence_refs
uncertainty
```



------

# 32. 为什么不创建 ReportV2

因为当前 contract 尚未进入复杂版本兼容阶段。

如果只是少数必需字段：

```text
FeatureRiskReviewReport
+ fields
```

比：

```text
FeatureRiskReviewReportV2
ReportEnvelopeV2
SectionRegistry
```

更简单。

这是典型：

> **Minimum Necessary Contract Evolution（最小必要合同演进）。**

------

# 33. CoverageState 为什么从 agents.py 移到 contracts.py

原来：

```text
CoverageState
```

定义在 `agents.py`。

WP3 Aggregator 又需要使用它。

如果直接：

```text
aggregation.py
→ agents.py
```

就会让业务 Contract 依赖 Agent implementation module。

所以最终移动到：

```text
contracts.py
```

然后：

```text
agents.py
aggregation.py
```

共同 import。

Codex Final Review：

```text
COVERAGE_STATE_MOVE = PASS
```



------

# 34. 这是哪个通用设计原则

> **Shared domain vocabulary 应放在 shared contract/domain 层，而不是某个 consumer 的实现模块里。**

例如：

```text
OrderStatus
PaymentState
WorkflowState
CoverageState
```

这些通常不应该归某个具体 Service class 所有。

------

# 35. Uncertainty 为什么必须进入最终 Report

三个 Agent 都可能有：

```text
uncertainty
```

如果最终 Aggregator 只输出：

```text
HIGH
ACT_NOW
```

却把 uncertainty 丢了，那么 deterministic policy 会制造出一种：

> “系统非常确定”

的假象。

所以最终保留：

```text
ReportUncertainty[]
```

并且来源带标签：

```text
document_analysis
risk_retrieval
test_review
workflow
```



------

# 36. Risk Policy 如何使用 Uncertainty

只要任一 branch uncertainty 非空：

```text
→ 至少 MEDIUM
```

从而阻止 confident LOW。

但 WP3 没有设计：

```text
confidence = 0.63
```

因为没有真实校准依据。

------

# 37. Real Artifact 为什么可以直接复用 WP2 输出

WP2 已经有：

```text
wp2_real_model_smoke_retry2_k8s_541.json
```

它保存了真实 DeepSeek 三 Agent typed result。

WP3 Aggregator 又是确定性的。

所以完全没有必要：

```text
再次调用 DeepSeek
```

最终真实链路：

```text
WP2 real artifact
        ↓
Pydantic validate
        ↓
Aggregator
        ↓
Renderer
        ↓
WP3 artifacts
```

Codex 确认：

```text
FROZEN_ARTIFACT_AGGREGATION_REQUIRES_MODEL = NO
```



------

# 38. 这个设计为什么对 Evaluation 特别重要

因为以后如果最终 RiskLevel 错了，可以拆开判断：

```text
是 WP2 Agent Finding 错？
        ↓
还是 Retrieval 错？
        ↓
还是 WP3 deterministic policy 错？
```

而不是：

```text
ReportAgent 输出 HIGH
```

然后不知道到底哪里有问题。

这叫：

> **Fault Attribution（错误归因）。**

------

# 39. Ground Truth 为什么仍然不能进入 WP3

WP3 Runtime 只允许输入：

```text
FeatureRiskReviewWorkflowResult
```

不允许：

```text
EvaluationAnnotation
expected_risk_level
expected_risk_areas
expected_coverage_gaps
```

Codex Final Review 和 Report Review 均确认：

```text
RUNTIME_EVALUATION_LEAKAGE = PASS
```



------

# 40. 为什么 Ground Truth 不能参与制定当前结果

假设标注说：

```text
expected_risk_level = HIGH
```

然后你看到当前 Policy 输出：

```text
MEDIUM
```

于是把 threshold 调成：

```text
finding >= 2 → HIGH
```

那这个 Case 已经参与了 Policy calibration。

之后再拿这个 Case 评测：

```text
Risk Accuracy = 100%
```

就没有意义。

因此 WP3 明确：

```text
RISK_POLICY_USES_GROUND_TRUTH = NO
FROZEN_ARTIFACT_USED_FOR_CALIBRATION = NO
```



------

# 41. 真实 `k8s_541` 为什么得到 HIGH

真实输入中：

```text
accepted findings = 6
historical issue reference exists
potential_gaps = 10
coverage_state = PLAN_ONLY
```

满足 HIGH Rule。

所以：

```text
RiskLevel.HIGH
```

这是：

> **Policy Execution Correctness（策略执行正确）。**

不是：

> **Domain Correctness（业务事实正确）。**

Codex Independent Review 已明确区分这两者。

------

# 42. 为什么又得到 ACT_NOW

当前 Report：

```text
FULL
+
HIGH
+
potential_gaps non-empty
```

满足：

```text
Priority.ACT_NOW
```

同样只能说：

```text
PRIORITY_POLICY_EXECUTION = PASS
```

不能说：

> “这个 Kubernetes KEP 真应该立刻处理。”



------

# 43. 这是面试里非常重要的 Evaluation 思维

一定记住：

```text
代码按规则执行正确
≠
规则本身业务正确
```

例如：

```text
if temperature > 20:
    danger = HIGH
```

程序完全实现正确。

但阈值 20 是否合理：

> 是另一层 Evaluation 问题。

------

# 44. WP3 最重要的真实 Bad Case：Windows Markdown Serialization

第一次 Real Report Smoke：

```text
Renderer output
```

语义完全正确。

JSON 也完全正确。

Citation 也正确。

但 Independent Result Review 发现：

```text
MARKDOWN_RENDERER_AUTHORITY = FAIL
```



------

# 45. 问题怎么发生的

Source `HistoricalIssue.description` 本身包含：

```text
\r\n
```

Renderer 原样保留。

旧 runner：

```python
Path.write_text(markdown, encoding="utf-8")
```

在 Windows 默认 text mode 下会进行 newline translation。

已有：

```text
\r\n
```

中的：

```text
\n
```

又被翻译成：

```text
\r\n
```

于是落盘：

```text
\r\r\n
```



------

# 46. 为什么读回来变成多一个空行

Universal newline read：

```text
\r\r\n
```

会形成：

```text
\n\n
```

于是 Historical Issue description 每个原换行后多一个空行。

非常典型的 Windows text serialization bug。

------

# 47. 为什么这个 Bug 很难发现

最有意思的是：

> 两个字符串长度都是 11073。

Codex 比较后却发现：

```text
text != text
```



所以：

```text
len(output) == len(saved)
```

完全不能证明 Artifact fidelity。

------

# 48. 最终怎么修

只修 runner：

```python
write_text(
    markdown,
    encoding="utf-8",
    newline=""
)
```

关闭 newline translation。

没有修改：

```text
Renderer
Aggregator
Policy
Source text
```



------

# 49. 为什么不能用 replace("\r\n", "\n") 修

因为这样是在：

```text
修改业务输出
```

而不是：

```text
修序列化层
```

Source 中原本的 CRLF 是真实内容。

Renderer 的职责也是保持内容。

正确方案应该：

> **让 storage fidelity 服从 renderer output，而不是反过来修改 renderer output 适应 storage。**

------

# 50. 最终增加了什么回归保护

现在 runner 会：

```text
renderer output
        ↓
write
        ↓
read bytes
        ↓
UTF-8 decode
        ↓
compare
```

必须：

```text
saved_markdown == renderer_output
```

同时：

```text
saved_bytes ==
renderer_output.encode("utf-8")
```

最终 Narrow Review：

```text
ROUND_TRIP_EQUALITY_GUARD = PRESENT
MARKDOWN_BYTE_PRESERVATION = PASS
MARKDOWN_RENDERER_AUTHORITY = PASS
```



------

# 51. 这个 Bad Case 最重要的工程知识

> **Artifact generation pipeline 不止包含业务逻辑和 Renderer，filesystem serialization 本身也是 correctness boundary。**

可以抽象为：

```text
Business Object
↓
Serialization
↓
Encoding
↓
Filesystem
↓
Read-back
```

任何一层都可能破坏结果。

------

# 52. JSON 为什么也加入 Round-trip Check

ZCode 同时加了：

```text
JSON artifact read
↓
json.loads
↓
report
==
FeatureRiskReviewReport.model_dump(mode="json")
```



这也是很合理的 Artifact Integrity（产物完整性）检查。

------

# 53. 高频面试问题：为什么最终报告不用 LLM 生成

推荐回答：

> 前三个 Agent 已经完成非确定性的分析和推断，最终 RiskLevel、Priority 和 Citation assembly 属于业务 Policy。如果再用第四个 LLM Agent，会重新引入随机性和 Citation hallucination，也难以测试。我最后用了 deterministic Aggregator，再用纯 Markdown renderer 展示，这样相同 typed result 一定得到相同 final report。

------

# 54. 面试题：你的风险等级是怎么定的？

回答：

> 当前不是模型预测，也不是经过统计校准的 Risk Score，而是一套透明 heuristic。只有 Risk/Test 两个下游都成功、没有 finding/gap、coverage 明确是 COVERED、且没有 uncertainty 时才允许 LOW；存在 finding、PLAN_ONLY、gap 或 uncertainty 至少 MEDIUM；多个 source-referenced finding 再叠加历史引用或 coverage gap 才升级 HIGH。Ground Truth 还没有进入 policy，所以我会明确说它是 uncalibrated demo policy。

------

# 55. 面试题：为什么 LOW 的条件这么严格？

> 因为 Retrieval 没命中或者 TestCase 数据缺失不能被解释成安全。“没有证据”不等于“证明没有风险”。尤其当前 TestCase mapping 还不完整，所以我采用 conservative policy，只有 coverage 完整且没有 finding 和 uncertainty 才允许 LOW。

------

# 56. 面试题：Priority 和 RiskLevel 为什么分开？

> RiskLevel 表示风险本身的程度，Priority 表示下一步处理动作。比如 Risk Agent 已经判断 HIGH，但如果 TestReview 分支失败，最终 report 是 partial，我会给 COMPLETE_REVIEW，而不是 ACT_NOW，因为审查还没有完成。这避免把不完整信息包装成最终动作建议。

------

# 57. 面试题：Citation 怎么防止被模型造出来？

> Citation identity 在 WP2 已经归 Provider/Retriever 所有。WP3 Aggregator 只能消费这些 EvidenceRef，并按 evidence_id 去重。如果相同 evidence_id 对应不同内容，我会 fail closed，而不是挑一个覆盖。Markdown 的 `[C1]` 只是展示标签，真实 identity 仍然是 EvidenceRef。

------

# 58. 面试题：Citation Resolution 通过是不是说明引用正确？

> 不是。Resolution 只证明 `[C1]` 能追溯到真实 EvidenceRef，也就是 traceability。Evidence 是否真正支持 Finding，需要 claim-level citation correctness evaluation，目前 WP3 还没有做，所以我明确保留 `CITATION_CORRECTNESS = NOT_EVALUATED`。

------

# 59. 面试题：Partial Result 怎么生成最终报告？

> 我允许 partial report，但必须显式标记 completeness。如果 Risk branch 失败，Historical Issues 和 High-Risk Scenarios 会标记 unavailable，RiskLevel 是 None；如果 Test branch 失败，可以保留已有 Risk inference，但 RiskLevel 不允许 LOW。FAILED workflow 不生成 completed report，而返回 typed aggregation failure。

------

# 60. 面试题：怎么避免 Evaluation Leakage？

> Runtime Aggregator 的输入只允许 typed workflow result，不 import annotation loader，也不读取 expected fields。我没有用 k8s_541 的 expected risk level 调当前规则。最终真实 artifact 只是验证 deterministic policy 能执行，不拿它反向调整 threshold。

------

# 61. 面试题：怎么保证生成文件没有被序列化破坏？

这里现在有非常好的真实回答：

> 我们真实遇到过一次。Renderer 本身返回正确 Markdown，但 Windows `Path.write_text()` 的默认 newline translation 把 source 中已有的 CRLF 再转换，导致落盘 Markdown 多空行。这个问题甚至长度比较发现不了，因为两份字符串长度相同。最后我关闭 newline translation，并增加 byte/text round-trip equality：renderer output 写盘后再以 UTF-8 bytes 读回，必须和原字符串、原编码字节完全一致。

------

# 62. 工程构建问题：何时用 deterministic code，何时用 LLM

一个通用判断方法：

## LLM 更适合

```text
语义理解
开放式推理
归纳总结
语言表达
未知模式发现
```

## Deterministic Code 更适合

```text
Policy enforcement
状态转换
权限
排序规则
Risk threshold
Citation identity
数据完整性
结构化 aggregation
```

WP3 就是把这两个区域主动切开。

------

# 63. 工程构建问题：什么时候 heuristic 规则可以接受

当：

- 数据量很小；
- Ground Truth 不足；
- 规则能清晰解释；
- 业务主要目的是 Demo / MVP；
- 规则之后可以被 Evaluation 替换或校准；

那么：

```text
transparent heuristic
```

比：

```text
fake ML score
```

更合理。

------

# 64. 什么时候应该升级成 calibrated policy

未来只有当：

```text
有足够人工 Ground Truth
+
Risk Level 有明确业务定义
+
有稳定 Evaluation Dataset
+
能够做 calibration / holdout validation
```

才值得：

- 调 threshold；
- 调 rule；
- 做统计模型；
- 做 classification model。

目前还没到这一步。

------

# 65. 一个特别容易混淆的概念：Policy Accuracy vs Execution Correctness

## Execution Correctness

输入满足 Rule 3：

```text
代码确实输出 HIGH
```

这个 WP3 已验证。

## Policy Accuracy

真实专家判断：

```text
这个 Case 到底应该 HIGH 还是 MEDIUM？
```

这个还没评估。

二者不能混。

------

# 66. Report Artifact 的真实 Provenance

现在最终 Demo 已经形成清晰的 Evidence Chain：

```text
Real Kubernetes Feature Data
        ↓
WP2 real DeepSeek three-agent execution
        ↓
wp2_real_model_smoke_retry2_k8s_541.json
        ↓
Pydantic validation
        ↓
FeatureRiskReviewAggregator
        ↓
FeatureRiskReviewReport
        ↓
Markdown renderer
        ↓
wp3_real_report_smoke_k8s_541.json
wp3_real_report_smoke_k8s_541.md
```

Independent Review 已验证 Source Fact Preservation 和 Provenance 都成立。

------

# 67. WP3 的真实 Bad Case 档案

## Bad Case 1：Markdown newline serialization mismatch

**真实性：真实发生。**

触发：

```text
Windows
+
source description contains CRLF
+
Path.write_text newline translation
```

风险：

> Renderer 正确，但最终 Artifact 被修改。

根因：

> 文件系统文本序列化再次转换已有换行。

修复：

```text
newline=""
+
byte/text round-trip equality
```

回归：

```text
renderer_output == saved_bytes.decode("utf-8")

renderer_output.encode("utf-8") == saved_bytes
```

最终 Review：

```text
MARKDOWN_RENDERER_AUTHORITY = PASS
```



------

# 68. Bad Case 2：不完整结果可能被包装成完整业务结论

**真实性：设计阶段预防，测试覆盖，真实 FULL smoke 未触发。**

风险：

```text
Risk HIGH
+
Test FAILED
→ ACT_NOW
```

可能让用户误以为评审完整。

设计：

```text
PARTIAL
→ COMPLETE_REVIEW
```

真实性表述应该是：

> 这是架构设计预防的错误，不是当前真实 Smoke 发生过的线上故障。

------

# 69. Bad Case 3：Citation ID 冲突

**真实性：防御性场景，测试覆盖，真实 Smoke 未触发。**

触发：

```text
same evidence_id
+
different EvidenceRef
```

处理：

```text
FAIL_CLOSED
```

不要说这是实际数据里发生过的问题。

------

# 70. Bad Case 4：没有风险命中就默认 LOW

**真实性：设计阶段预防。**

当前 Policy 明确防止：

```text
no retrieval hit
→ LOW
```

特别是 Risk branch missing 时：

```text
risk_level = None
```

不是 LOW。

------

# 71. WP3 最值得讲的架构演进

面试可以按这个顺序：

```text
最初问题：
三个 Agent 的输出如何形成最终决策？

方案 A：
再加一个 ReportAgent
问题：
随机、Citation hallucination、不可回归。

方案 B：
Workflow 自己做 Aggregation
问题：
Orchestration Owner 和 Business Policy 混淆。

最终：
单独 FeatureRiskReviewAggregator
+
typed FeatureRiskReviewReport
+
pure Markdown Renderer
```

这是一条非常完整的架构决策故事。

------

# 72. 为什么 Aggregator 不直接放 Workflow

WP2 Workflow 负责：

```text
dependency
parallelism
branch status
partial failure
```

WP3 Aggregator 负责：

```text
RiskLevel
Priority
Citation grouping
Report completeness
```

如果混在一起：

> orchestration logic 与 business policy 会耦合。

以后修改 Risk Policy 还可能影响 Workflow。

所以两个 Owner 分开。

------

# 73. 对系统设计面试有什么价值

WP3 实际涉及：

- Domain Service；
- Policy Owner；
- Contract Evolution；
- Failure Semantics；
- Partial Result；
- Source-of-Truth；
- Structured Output；
- Citation Integrity；
- Evaluation Leakage；
- Artifact Provenance；
- Serialization；
- Cross-platform newline；
- Deterministic Testing。

已经明显不是“Prompt Engineering”。

------

# 74. 简历 Bullet 可以怎么写

可以写：

> 设计确定性 Feature Risk Aggregation 层，将多 Agent 的 typed 推断结果收敛为 RiskLevel、Priority、Coverage、Citation 和 Uncertainty 报告；将 LLM inference 与业务 Policy 解耦，支持 Partial Report、Citation identity fail-closed 校验及可追溯 Markdown 输出。

另一个真实工程 Bullet：

> 修复 Windows 文本换行转换导致 Markdown Report 与 Renderer 输出不一致的问题，通过关闭 newline translation 并增加 UTF-8 byte/text round-trip equality guard，保证最终 Artifact 与 typed report 的 deterministic renderer 严格一致。

------

# 75. 如果面试官问“WP3 最有价值的设计是什么”

推荐回答：

> 不是 RiskLevel 规则本身，而是我把“模型推断”和“最终业务 Policy”拆开。三个 Agent 可以有不确定性，但最终系统需要一个可解释、可复现、可测试的决策层。我让 Aggregator 成为 RiskLevel / Priority 的唯一 Owner，Ground Truth 又与 Runtime 隔离，这样后续 Evaluation 可以明确判断是 Agent 错、Retrieval 错还是 Policy 错。

------

# 76. 如果问“这个 Risk Policy 能上线吗”

不能说能。

正确回答：

> 目前不能作为 production calibrated policy。我现在只有 deterministic demo heuristic，Ground Truth 还在 Pending，RiskLevel 和 Priority correctness 尚未评估。这个阶段主要目的是先建立可信的 policy boundary 和 evaluation-ready contract，WP4 再用人工标注数据评测。

------

# 77. 如果问“为什么还值得实现这个 heuristic”

> 因为最终业务系统必须先有一个明确 Policy Owner，否则 RiskLevel 会散落在 Prompt 或多个 Agent 中，之后甚至没法评测。先建立简单透明规则，再通过 Evaluation 判断哪些规则需要调整，比一开始做一个不可解释的复杂评分模型更可靠。

------

# 78. WP3 不能夸大的地方

不要说：

> “RiskLevel Accuracy 已经验证。”

没有。

------

不要说：

> “HIGH 是正确标签。”

没有 Ground Truth。

------

不要说：

> “Citation Accuracy 100%。”

现在只有 identity resolution。

------

不要说：

> “Historical bug recall 很好。”

WP2 实际 Retrieval top-5 还是 self-KEP dominated。

------

不要说：

> “这是生产 Risk Model。”

目前：

```text
RISK_POLICY_CALIBRATED = NO
```

------

# 79. 最终面试八句话

如果只复习下面八句：

1. **前三个 Agent 负责推理，最终 RiskLevel / Priority 由 deterministic Aggregator 负责。**
2. **Source Fact、Agent Inference、Business Policy 是三个不同 Authority。**
3. **Risk Policy 是透明 heuristic，不是 calibrated model，更没有读取 Ground Truth。**
4. **LOW 的条件必须非常严格，因为 absence of evidence 不等于 evidence of absence。**
5. **RiskLevel 和 Priority 不等价；Partial Report 即使已有 HIGH，也优先 COMPLETE_REVIEW。**
6. **Citation identity 属于 Provider/Retriever，Aggregator 只能消费和渲染，冲突时 fail closed。**
7. **Typed Report 是 Authority，Markdown 只是 deterministic presentation。**
8. **Renderer 正确不代表最终 Artifact 正确，filesystem serialization 也是 correctness boundary。**

------

# 80. 推荐学习文档文件名

按照当前统一命名规则：

```
docs/interview/stage5_phase4_wp3_risk_aggregation_and_citation_report.md
```

------

# 81. WP3 最终学习收口状态

```text
WP3_IMPLEMENTATION = COMPLETE
WP3_FINAL_REVIEW = PASS
WP3_REAL_REPORT_SMOKE = PASS
WP3_RESULT_REVIEW = PASS
WP3_SERIALIZATION_FIX = PASS

WP3_READY_FOR_WP4 = YES
```

当前必须带入 WP4 的 Known Limitations（已知限制）：

```text
GROUND_TRUTH = PENDING
RISK_POLICY_CALIBRATED = NO

RISK_LEVEL_CORRECTNESS = NOT_EVALUATED
PRIORITY_CORRECTNESS = NOT_EVALUATED

CITATION_CORRECTNESS = NOT_EVALUATED
CITATION_COMPLETENESS = NOT_EVALUATED

RETRIEVAL_QUALITY = NOT_EVALUATED
TEST_CASE_MAPPING = PARTIAL

REAL_RISK_RETRIEVAL_TOP5_SELF_KEP_DOMINATED
```

这些正是 **WP4 — Real E2E Demo + Lightweight Evaluation（真实端到端 Demo + 轻量评测）** 接下来应该解决或正式测量的内容，而不是回头继续修改 WP3。