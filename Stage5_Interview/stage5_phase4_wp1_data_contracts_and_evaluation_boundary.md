# Stage5-Phase4-WP1 学习 / 面试总结

## 1. 这个 WP 到底完成了什么

WP1 的核心不是“定义几个 Pydantic Model”，而是给后面的 Multi-Agent Feature Risk Review 建立一套**可信的数据语言和数据边界**。

现在的数据链路可以概括为：

```
真实 Kubernetes 开源资料
        ↓
WP0 Frozen Raw Source
        ↓
WP1 Normalized Business Projection
        ↓
Typed Contracts
        ↓
后续 Three-Agent Workflow

同时：

Evaluation Annotation
        ↓
独立 Evaluation Path
        ×
不能进入 Runtime Agent Input
```

最终已经真实实现：

- `FeatureDocument`
- `FeatureChangePoint`
- `EvidenceRef`
- `HistoricalIssue`
- `TestPlan`
- 可为空的 `TestCase`
- `RiskFinding`
- `FeatureRiskReviewReport`
- `EvaluationAnnotation`
- `AnnotationStatus`
- `FeatureRiskReviewCase`

5 个真实 Kubernetes KEP Case 均可加载。30_zcode_execution(2).mdMD

Final Gate 还实际验证了最重要的一条边界：

> Runtime loader 不读取 `annotations/`，Runtime object 中也没有 `expected_*` 或 annotation；Evaluation Annotation 必须通过独立入口加载。40_codex_review(1).mdMD

所以这个 WP 真正解决的是：

> **业务数据、外部事实和评测答案之间应该如何建立清晰边界。**

------

# 2. 关键术语速览

| 术语                                  | 一句话理解                                                   |
| ------------------------------------- | ------------------------------------------------------------ |
| Contract（契约）                      | 明确定义模块或 Agent 之间交换什么数据以及字段语义。          |
| Typed Contract（强类型契约）          | 用明确的数据类型约束 Agent 输入输出，而不是任意 `dict` 或自由文本。 |
| Raw Source（原始来源）                | 从 Kubernetes 冻结下来的原始 KEP、Issue、Test Plan 等外部事实。 |
| Normalized Projection（归一化投影）   | 把不同外部数据转换成 AgentEvalOps 内部统一业务结构。         |
| Ground Truth（标准答案）              | Evaluation 用来判断 Agent 输出正确与否的参考答案。           |
| Annotation（标注）                    | 人工对 Case 添加的预期 Change Point、Risk、Risk Level 等评测信息。 |
| Evaluation Leakage（评测泄漏）        | 被评测系统在执行时直接或间接获得了 Ground Truth。            |
| EvidenceRef（证据引用）               | 将业务 Finding 追溯到具体原始资料的轻量引用结构。            |
| Citation Traceability（引用可追溯性） | 能证明某个 Finding 来源于哪条 Evidence。                     |
| Citation Correctness（引用正确性）    | 判断 Citation 是否真的支持对应 Claim；WP1 **没有评估这个指标**。 |
| Source Authority（来源权威）          | 判断一条数据到底来自真实外部来源、人工标注还是模型生成。     |
| Projection Builder（投影构建器）      | 从冻结 Raw Source 确定性地产生 Normalized Dataset 的工具。   |
| Runtime Path（运行路径）              | 后续真实 Agent 执行时能够访问的数据路径。                    |
| Evaluation Path（评测路径）           | Evaluator 才能访问 Annotation / Expected Result 的独立路径。 |

------

# 3. 为什么不能直接拿 Kubernetes JSON / Markdown 给 Agent

一个常见错误思路是：

```
KEP Markdown
GitHub Issue JSON
Test Plan Markdown
        ↓
Agent 自己解析
```

小 Demo 可以这样做，但很快会出现三个问题。

### 第一，不同数据源结构不同

KEP 是 Markdown。

GitHub Issue 是 JSON。

Test Plan 又可能只是 KEP 中的一段文本。

如果三个 Agent 都分别理解这些原始结构：

```
DocumentAnalysisAgent → 自己解析 KEP
RiskRetrievalAgent    → 自己解析 Issue
TestReviewAgent       → 自己解析 Test Plan
```

业务语义就散落到 Agent Prompt 和 Parser 中。

WP1 改成：

```
External Source
      ↓
Normalization
      ↓
Typed Business Contract
      ↓
Agent
```

后续 Agent 只需要理解：

```
FeatureDocument
HistoricalIssue
TestPlan
EvidenceRef
```

而不用理解 Kubernetes 数据内部所有细节。

------

# 4. 为什么 Raw / Normalized / Annotation 必须分三层

这是 WP1 最值得面试讲的设计。

## Raw Source

代表：

> **外部世界实际是什么。**

例如：

```
Kubernetes KEP README
GitHub Enhancement Tracking Issue
KEP Test Plan
```

它不能因为我们的业务需要就被改写。

------

## Normalized Business Data

代表：

> **AgentEvalOps 怎么理解这些外部事实。**

例如：

```
GitHub Issue JSON
        ↓
HistoricalIssue
```

或者：

```
KEP Test Plan
        ↓
TestPlan
```

这是一个 Projection，而不是新的 Authority。

------

## Evaluation Annotation

代表：

> **我们希望 Agent 在这个 Case 上识别出什么。**

例如：

```
expected_change_points
expected_components
expected_risk_areas
expected_coverage_gaps
expected_risk_level
```

它属于 Evaluation。

因此：

```
Raw Source
   ≠
Normalized Business Data
   ≠
Evaluation Ground Truth
```

这三个概念混在一起，就非常容易发生 Evaluation Leakage。

------

# 5. WP1 最重要的 Bad Case：Ground Truth Leakage

假设为了编码方便，设计：

```
class FeatureRiskReviewCase:
    feature: FeatureDocument
    issues: list[HistoricalIssue]
    tests: list[TestPlan]
    expected_risk_level: RiskLevel
    expected_change_points: list[str]
```

然后 Runtime：

```
case = load_case("k8s_541")
agent.run(case)
```

即使 Prompt 没有显式告诉模型：

```
expected_risk_level
```

这个设计依然危险。

因为：

> Runtime object 本身已经拥有 Evaluation Truth。

以后一个 serializer、debug helper、`model_dump()`、Prompt builder 或日志处理稍有变化，就可能把答案带进去。

所以 WP1 最终采用的是：

```
load_feature_risk_review_cases()
        ↓
Runtime Business Data

load_evaluation_annotations()
        ↓
Evaluation Truth
```

Final Gate 已经实际沿调用链确认这两个入口隔离。40_codex_review(1).mdMD

### 面试时一句话

> 我没有只靠“Prompt 约定不要使用 Ground Truth”防止数据泄漏，而是在 Dataset Loader 层把 Runtime Data 和 Evaluation Annotation 分成两个独立入口，使被评测 Agent 的正常执行对象本身不持有标准答案。

这个回答质量很高。

------

# 6. 为什么 Ground Truth 现在还是 PENDING

当前：

```
GROUND_TRUTH = PENDING
```

这不是没做完。

WP1 要解决的是：

```
Ground Truth 应该长什么样
+
应该放在哪里
+
谁能访问
```

而不是：

> 让 LLM 把 5 个 Case 的答案自动填出来。

目前 annotation 已经定义最小字段：

```
expected_change_points
expected_components
expected_risk_areas
expected_historical_issue_ids
expected_coverage_gaps
expected_risk_level
```

但需要人工审核。

Final Gate 明确认为：

```
HUMAN_ANNOTATION_CHECKPOINT_REQUIRED = YES
```

并且这个 Checkpoint 只要求在 **WP4 Real E2E Evaluation 前**完成。40_codex_review(1).mdMD

这是一种很重要的工程思想：

> **Schema Ready 不等于 Annotation Ready。**

------

# 7. 为什么不能让 LLM 自己生成 Ground Truth

因为我们最终要评估的本身就是 Agent / LLM。

如果：

```
LLM
 ↓
生成 expected risks

同类 LLM
 ↓
预测 risks

Evaluator
 ↓
比较两者
```

很容易形成：

> 模型自己的偏好成为“正确答案”。

尤其 Risk Level 这种东西本来就带判断性质。

我们可以让 LLM：

```
辅助产生 annotation candidate
```

但最终 Authority 应该是：

```
真实 KEP
+
Risks / Mitigations
+
Test Plan
+
Historical Evidence
+
人工审核
```

因此 WP1 保持 `PENDING` 反而比自动填满更可信。

------

# 8. EvidenceRef 为什么重要

后面的 Agent 最危险的一种输出是：

> “这个 Feature 可能导致某个历史故障。”

但没有任何证据。

所以 Phase4 不应该只返回：

```
{
  "risk": "可能出现兼容性问题"
}
```

而应该接近：

```
RiskFinding
├── description
├── affected_components
├── historical_issue_refs
├── evidence_refs
└── uncertainty
```

最终形成：

```
Risk Finding
     ↓
EvidenceRef
     ↓
HistoricalIssue / TestPlan
     ↓
Frozen Kubernetes Source
```

这就是：

**Evidence Traceability（证据可追溯性）。**

------

# 9. Traceability 和 Correctness 千万不要混

这是后续面试非常容易被追问的点。

现在实现的是：

```
Finding
   ↓
EvidenceRef
   ↓
Source
```

因此我们可以说：

> 这个 Finding 的证据来源可以追溯。

但不能说：

> 这个 Evidence 一定正确支持这个 Finding。

后者需要：

**Citation Correctness。**

Phase3 Final Handoff 本身也已经冻结：

```
CITATION_CORRECTNESS = NOT_EVALUATED
CITATION_COMPLETENESS = NOT_EVALUATED
```

STAGE5_PHASE3_FINAL_HANDOFF.mdMD

因此 Phase4 的 truthful wording 是：

> 实现了 evidence-level Citation Traceability。

而不是：

> 实现了 Citation Correctness Evaluation。

------

# 10. 为什么 HistoricalIssue 没有强行补 severity

WP0 当前 5 条 historical evidence 实际是 Kubernetes enhancement tracking issue，而不是经过确认的 production incident。10_codex_execution.mdMD

原始数据没有官方 severity。

最危险的实现是：

```
这个 Issue 看起来很严重
        ↓
severity = HIGH
```

然后系统以后把：

```
HIGH
```

当成 Kubernetes 官方事实。

WP1 正确做法是：

```
source severity = null
```

如果未来我们人工判断：

```
curated_severity = HIGH
annotation_source = human_curated
```

于是：

```
Source Fact
```

和：

```
Our Annotation
```

仍然是两件事情。

### 面试可以提炼成

> 外部 Source Field 和内部 Curated Field 必须区分，否则经过 normalization 后很容易发生 provenance laundering——人工推断最后看起来像原始数据本身提供的事实。

------

# 11. TestCase 为什么允许为空

当前真实情况：

```
REAL TestPlan = YES
REAL TestCase Mapping = PARTIAL
TestCase[] = []
```

40_codex_review(1).mdMD

如果为了让 Demo 好看，我们编一些：

```
test_scheduler_failure_001
test_storage_recovery_002
```

然后称之为 Kubernetes Existing Tests，就会破坏真实性。

所以 Contract 应该能够表达：

```
TestPlan exists
TestCase[] = []
```

这是非常值得学习的一个原则：

> **Contract 应该能够表达现实中的“不完整”，而不是逼迫数据伪装成完整。**

这也是为什么 Optional / Empty Collection 在生产系统里非常重要。

------

# 12. Codex Final Gate 发现的真实 Bad Case

Codex 找到了一个很好的 P1。

原来的 Projection Builder：

```
rebuild
 ↓
重新创建 PENDING annotation
```

问题在于未来：

```
人工审核
 ↓
HUMAN_REVIEWED
 ↓
再次 rebuild dataset
 ↓
被覆盖成 PENDING
```

这意味着：

> Projection Builder 意外拥有了 Annotation 生命周期。

最终修复为：

```
annotation file 不存在
        ↓
创建 PENDING template

annotation file 已存在
        ↓
保留
```

并增加测试：

> `HUMAN_REVIEWED` annotation 在 rebuild 后仍然保留。40_codex_review(1).mdMD

------

# 13. 这里其实涉及一个很重要的 Owner 问题

谁拥有 Annotation？

错误：

```
Projection Builder
    ↓
每次都生成 Annotation
```

正确：

```
Projection Builder
    ↓
首次 bootstrap annotation template

Human / Evaluation Process
    ↓
拥有 annotation 后续生命周期
```

因此这个 Bug 的根因并不只是：

> 文件被覆盖。

更深层是：

> **Owner Boundary（所有权边界）错误。**

这类问题特别适合 Agent Platform / System Design 面试。

------

# 14. 为什么 WP1 不需要 Schema Registry

我们现在只有：

```
FeatureDocument
HistoricalIssue
TestPlan
RiskFinding
...
```

完全可以通过：

```
Python typed model
+
versioned dataset
+
tests
```

管理。

如果现在建设：

```
Schema Registry
Dynamic Contract Registry
Contract Plugin
Version Negotiation
```

确实“更像平台”。

但没有实际问题需要它解决。

这就是 Phase4 的核心取舍：

> **Contract 要强，但 Contract Infrastructure 不需要重。**

------

# 15. 为什么使用 Typed Contract 而不是自由 JSON

自由 JSON 最大优势是快。

但 Multi-Agent 系统很容易出现：

```
Agent A:
{
  "components": [...]
}

Agent B expected:
{
  "affected_components": [...]
}
```

或者：

```
risk_level = "high"
```

另一边：

```
risk_level = "HIGH"
```

Typed Contract 可以把这种问题提前到边界处理。

它还让后续 WP2 更容易做到：

```
DocumentAnalysisAgent
        ↓
FeatureChangePoint[]
        ↓
RiskRetrievalAgent
TestReviewAgent
```

而不是两个 Agent 再解析第一个 Agent 写的一段 Markdown。

------

# 16. 高频面试问题

## Q1：为什么要给 Agent 输出设计结构化 Contract？

可以回答：

> Multi-Agent 场景下，一个 Agent 的输出通常是另一个 Agent 的输入。如果全部依赖自然语言，不仅解析不稳定，而且字段语义、缺失值和失败状态很难统一。我在 Feature Risk Review 中把 FeatureChangePoint、HistoricalIssue、RiskFinding、EvidenceRef 等定义成 Typed Contract，让 Agent 之间交换的是明确业务对象。自然语言仍用于 reasoning 和最终报告，但系统边界使用结构化数据。

------

## Q2：为什么不直接把 Kubernetes 原始数据传给 Agent？

> 原始数据属于外部 Source Schema，而 Agent Workflow 需要的是内部业务语义。我保留 Raw Source 不变，然后通过 deterministic projection 转成 Normalized Business Contract。这样既保留 source traceability，也避免每个 Agent 分别理解 GitHub Issue、KEP Markdown 等不同外部格式。

------

## Q3：怎么避免 Evaluation Data Leakage？

> 我不是只在 Prompt 中告诉 Agent“不要看答案”，而是把 runtime dataset 和 evaluation annotation 分成两个 loader。正常 workflow 加载的 FeatureRiskReviewCase 本身不包含 expected fields，只有 evaluator 能通过独立入口加载 annotation。Final Review 还专门沿实际 loader 调用链检查过这个边界。

------

## Q4：为什么 Ground Truth 不让 LLM 自动生成？

> LLM 可以辅助生成 annotation candidate，但如果直接把模型生成结果作为 Ground Truth，就容易形成 self-evaluation bias。我的数据来自真实 Kubernetes KEP、Issue 和 Test Plan，最终 expected change points、risk areas、risk level 等需要人工审核后才能从 PENDING 升级为 HUMAN_REVIEWED。

------

## Q5：EvidenceRef 和 Citation Correctness 有什么区别？

> EvidenceRef 解决 traceability，也就是一个 Finding 能不能回到具体 source；Citation Correctness 则进一步判断 source 是否真的支持这个 claim。当前 Phase4 只实现前者，没有把它夸大成 citation correctness evaluation。

------

## Q6：为什么 TestCase 可以为空？

> 因为真实 Dataset 当前能可靠获得 KEP Test Plan，但还没有可靠映射到具体 Kubernetes test function。与其生成假的 TestCase，我让 Contract 明确支持空列表。这保证系统能够表达真实数据的不完整状态。

------

# 17. 更模糊、更容易拉开差距的追问

### “Typed Contract 会不会限制 Agent 灵活性？”

核心思路：

> Reasoning 可以灵活，系统边界应该稳定。

可以解释：

```
LLM internal reasoning
        → flexible

Agent output boundary
        → typed

Final human report
        → readable
```

不是所有内容都结构化，而是**机器之间需要可靠交换的部分结构化**。

------

### “如果 Kubernetes KEP Schema 变了怎么办？”

不需要立刻谈 Schema Registry。

应该回答：

> Raw Source 和 Normalized Projection 已经分离，因此外部 Schema 变化主要由 projection adapter 消化，而不会直接传播到 Agent Contract。当前 Dataset 又冻结在明确 commit，所以 Evaluation 本身不会随着 upstream master 漂移。如果未来要持续同步上游，再考虑正式的 schema/version migration。

------

### “为什么 Annotation 不放进同一个 Case Object，调用方便很多？”

因为：

> Convenience 和 Evaluation Integrity 冲突时，应该优先后者。

同一个 object 会增加 accidental leakage 风险。

------

### “人工 Ground Truth 会不会主观？”

会。

因此更成熟的回答不是说“人工一定正确”，而是：

> Risk Level 本身具有判断性。当前小型 Demo 使用 human-reviewed annotation 足够；如果生产化，可以增加 annotation guideline、多 reviewer agreement、disagreement resolution，但 Phase4 没有为了 5 个 Case 建完整 annotation platform。

------

# 18. 这个 WP 的核心 Trade-off

| 选择                        | 收益           | 代价              | WP1选择 |
| --------------------------- | -------------- | ----------------- | ------- |
| Raw Source 直接给 Agent     | 实现最快       | 强耦合外部格式    | ❌       |
| Normalized Contract         | 边界稳定       | 多一层 projection | ✅       |
| Runtime + Annotation 同对象 | 调用方便       | Leakage 风险      | ❌       |
| 独立 Evaluation Annotation  | 更可信         | Loader 稍多       | ✅       |
| 自动 LLM Ground Truth       | 快             | 自评偏差          | ❌       |
| Human-reviewed Ground Truth | 更可信         | 有人工成本        | ✅       |
| 强制 TestCase 非空          | 数据看起来完整 | 会逼迫造假        | ❌       |
| TestCase 可为空             | Truthful       | Demo 数据不完整   | ✅       |
| Schema Registry             | 可扩展         | 过度工程          | ❌       |
| Typed Models + Tests        | 足够可靠       | 泛化能力有限      | ✅       |

------

# 19. Truthful Implementation Boundary

现在可以说：

```
IMPLEMENTED

✓ 真实 Kubernetes Feature Source
✓ Feature Risk Review Typed Contracts
✓ Normalized Dataset Projection
✓ EvidenceRef
✓ Citation Traceability
✓ Runtime / Evaluation Annotation Isolation
✓ PENDING / HUMAN_REVIEWED Annotation Contract
✓ 5 个 Kubernetes Case 可加载
✓ Projection rebuild 不覆盖人工 Annotation
```

已经验证：

```
EVALUATED / TESTED

✓ 8 focused tests PASS
✓ Ruff PASS
✓ Dataset Validator PASS
✓ git diff --check PASS
✓ Loader leakage boundary reviewed
```

40_codex_review(1).mdMD

还不能说：

```
NOT IMPLEMENTED / NOT EVALUATED

✗ Ground Truth 已完成
✗ Three-Agent Workflow
✗ Real Agent Execution
✗ RAG Index
✗ Risk Aggregation
✗ Real E2E Evaluation
✗ Citation Correctness
✗ Citation Completeness
✗ Production Integration
```

------

# 20. 简历现在能写什么

WP1 **单独不值得占一整条简历 Bullet**。

它更适合作为 Phase4 最终业务项目的一部分。

未来 Phase4 完成后，可以把这部分浓缩成类似：

> 基于真实 Kubernetes KEP、Enhancement Issue 与 Test Plan 构建 Feature Risk Review 数据集，通过 Typed Contract 统一 Feature、历史问题、测试计划与 Evidence 数据模型，并隔离 Runtime Data 与 Evaluation Ground Truth，避免评测数据泄漏。

这里的：

**“真实 Kubernetes”**

和：

**“Evaluation Ground Truth 隔离”**

都很有价值。

------

# 21. 绝对不能夸大的内容

不要说：

> “使用真实 Kubernetes 生产事故数据。”

现在不是。

真实情况是：

> Kubernetes enhancement tracking issues。

不要说：

> “构建了真实 Kubernetes Test Case 数据集。”

目前只有：

> Real Test Plan，真实 test-function mapping 尚未建立。

不要说：

> “完成了人工标注的高质量 Benchmark。”

现在：

```
GROUND_TRUTH = PENDING
```

不要说：

> “实现 Citation Correctness。”

现在只有：

```
CITATION_TRACEABILITY = IMPLEMENTED
```

不要说：

> “已经完成 Feature Risk Review Multi-Agent 系统。”

WP2 尚未开始。

------

# 22. 这个 WP 最值得记住的 5 句话

面试前如果没时间复习整篇，记这五条：

1. **Raw Source、Normalized Business Data 和 Evaluation Annotation 是三种不同 Authority，不能混在一起。**
2. **防止 Evaluation Leakage 最好依赖数据和 Loader 边界，而不是依赖 Prompt 约定。**
3. **Typed Contract 的目的不是让架构更漂亮，而是稳定 Multi-Agent 之间的数据交换。**
4. **Contract 应该能表达真实世界的不完整状态，因此 TestCase 可以为空，缺失 severity 保持 null。**
5. **Evidence Traceability 只证明 Finding 能回到 Source，不等于 Citation Correctness。**

