# Stage5-Phase4-WP2 学习 / 面试总结

## Three-Agent Risk Review Workflow（多智能体风险审查工作流）

WP2 是 Phase4 目前最重要的一个工程节点。WP1 解决的是**数据、Contract 和 Evaluation Boundary（评测边界）**，WP2 则第一次把这些东西真正组合成了一个：

> **有依赖、有并发、有检索、有真实 LLM、有失败语义、有证据约束的 Multi-Agent（多智能体）业务 Workflow。**

而且最终不仅 Fake Test 跑通，还完成了真实 `deepseek/deepseek-chat` 三 Agent Smoke：三个 Agent 全部获得 validated structured output，Workflow 最终 `SUCCESS`。80_real_model_smoke_retry2.mdMD

------

# 1. WP2 最终解决了什么问题

最终业务链路是：

```
FeatureDocument
      ↓
DocumentAnalysisAgent
      ↓
DocumentAnalysisResult
      ↓
┌───────────────────────────────┐
│                               │
↓                               ↓
RiskRetrievalAgent         TestReviewAgent
│                               │
├─ Historical Retrieval         ├─ TestPlan Provider
├─ HistoricalIssue Provider     ├─ TestCase Provider
├─ EvidenceRef                  ├─ Coverage Analysis
└─ LLM Risk Inference           └─ LLM Recommendation
│                               │
└───────────────┬───────────────┘
                ↓
        async parallel join
                ↓
 FeatureRiskReviewWorkflowResult
```

最终真实实现：

- `DocumentAnalysisAgent`
- `RiskRetrievalAgent`
- `TestReviewAgent`
- `FeatureRiskReviewWorkflow`
- Data Provider
- Historical Knowledge Retriever
- Model Port
- Structured Output Validation
- Parallel Execution
- Partial Result
- Evidence identity filtering
- DeepSeek provider compatibility
- Real Model Smoke

30_zcode_execution(3).mdMD

------

# 2. 最终真实性状态

这一部分面试前一定要记牢。

```
THREE_AGENT_WORKFLOW = IMPLEMENTED

REAL_PARALLEL_EXECUTION = IMPLEMENTED
PARTIAL_RESULT_HANDLING = IMPLEMENTED

REAL_KUBERNETES_DATA_PROVIDER = YES

HISTORICAL_RETRIEVAL_CORPUS_BUILT = YES
LOCAL_LEXICAL_INDEX = YES
VECTOR_INDEX = NO

REAL_MODEL_EXECUTION = YES
REAL_THREE_AGENT_SMOKE = YES
REAL_RETRIEVAL_EXECUTION = YES
REAL_TEST_REVIEW_EXECUTION = YES

GROUND_TRUTH = PENDING

CITATION_TRACEABILITY = IMPLEMENTED
CITATION_CORRECTNESS = NOT_EVALUATED

FINAL_RISK_AGGREGATION = NOT_IMPLEMENTED

PRODUCTION_CHANGE = NO
LOCALAGENT_WRITE = NONE
```

真实 Smoke 使用：

```
Case  = k8s_541
Model = deepseek/deepseek-chat
```

最终：

```
WORKFLOW_STATUS = SUCCESS

DOCUMENT_ANALYSIS_STATUS = SUCCESS
RISK_RETRIEVAL_STATUS = SUCCESS
TEST_REVIEW_STATUS = SUCCESS
```

80_real_model_smoke_retry2.mdMD

------

# 3. 名词 / 概念速览

| 名词                                     | 一句话理解                                                   |
| ---------------------------------------- | ------------------------------------------------------------ |
| Workflow Owner（工作流所有者）           | 决定谁负责整个业务执行顺序、依赖和失败语义。                 |
| Agent Port（智能体端口）                 | Agent 依赖的抽象能力接口，例如模型调用或数据查询，而不是具体 Provider。 |
| Adapter（适配器）                        | 把外部模型、数据源或检索实现适配到内部稳定 Port。            |
| Dependency（依赖）                       | 下游任务必须等待上游结果才能执行。                           |
| Parallel Branch（并行分支）              | 多个彼此独立的任务在依赖满足后同时执行。                     |
| Join（汇合）                             | 等待并行分支结束后组合各分支结果。                           |
| Partial Result（部分结果）               | 一个分支失败时仍保留其他成功分支的结果。                     |
| Fail-fast（快速失败）                    | 一个子任务失败后立即取消其他任务的并发语义。                 |
| Sibling Preservation（兄弟任务结果保留） | 一个并行分支失败时，不取消另一个成功或仍在执行的分支。       |
| Source Fact（来源事实）                  | 直接来自外部数据源的事实，例如 Issue、TestPlan。             |
| Inference（推断）                        | LLM 基于 Source Fact 产生的风险判断或建议。                  |
| Evidence Identity（证据身份）            | 某条 Evidence 的稳定 ID，由系统而不是 LLM 创建。             |
| Hallucination Boundary（幻觉边界）       | 限制 LLM 可以推理什么，但不能虚构哪些系统事实。              |
| Coverage State（覆盖状态）               | 表示测试证据完整程度，例如 `PLAN_ONLY`。                     |
| Structured Output（结构化输出）          | 要求模型输出能够验证的 JSON / typed result，而不是自由文本。 |
| Provider Capability（模型供应商能力）    | 不同模型 API 对 `json_schema`、tool call 等特性的支持差异。  |
| Compatibility Adapter（兼容适配器）      | 在不改变业务 Contract 的情况下吸收 Provider 差异。           |
| Lexical Retrieval（词法检索）            | 根据词项重叠等文本特征做检索，而不是向量相似度。             |
| Citation Traceability（引用可追溯）      | Finding 可以追溯回真实 Evidence。                            |
| Citation Correctness（引用正确性）       | 判断 Evidence 是否真的支持 Claim；WP2 未评估。               |

------

# 4. WP2 最重要的设计决策：Workflow Owner 应该是谁

Codex 最终冻结：

```
WORKFLOW_OWNER =
AgentEvalOps FeatureRiskReviewWorkflow
```

而没有复用 AgentEvalOps 的 `ExecutionTarget`，也没有把整个业务丢给 LocalAgent production Runtime。20_codex_decision(1).mdMD

这个决策特别值得面试讲。

## 为什么不用现有 ExecutionTarget

因为已有 ExecutionTarget 的核心语义是：

```
Evaluation Run
→ Attempt
→ timeout
→ artifact
→ terminal outcome
```

而本 WP 的业务语义是：

```
DocumentAnalysis
→ parallel branches
→ partial failure
→ join
```

二者解决的不是同一个问题。

这叫：

**Abstraction Mismatch（抽象不匹配）。**

不是“现有抽象能套就一定套”。

------

# 5. 为什么也没有直接复用 LocalAgent Multi-Agent Runtime

LocalAgent 已经有成熟的：

- Runtime；
- Agent Registry；
- Scheduler；
- Parallel Execution；
- Budget；
- Cancellation；
- Recovery；
- Retrieval execution。

20_codex_decision(1).mdMD

第一反应可能是：

> “既然有 Runtime，为什么不直接复用？”

因为为了这个 Feature Review Demo 接进去，需要引入：

```
Agent registry modification
Plan configuration
Kubernetes corpus configuration
production lifecycle semantics
Runtime ownership changes
```

会让 Phase4 从：

> “业务 Demo”

变成：

> “LocalAgent Runtime Integration Project”。

所以最终保持：

```
LOCALAGENT_WRITE = NONE
```

这体现一个非常重要的工程原则：

> **Reuse（复用）的前提是 ownership 和 lifecycle 匹配，而不是代码已经存在。**

------

# 6. 为什么没有建设通用 Workflow Engine

本次实际只需要：

```
FeatureRiskReviewWorkflow.run(case)
```

所以没有建设：

```
DAG DSL
Node Registry
Edge Registry
Scheduler
Plugin Runtime
Workflow Persistence
Distributed Executor
```

30_zcode_execution(3).mdMD

这是一道非常典型的系统设计题：

> “为什么不用 LangGraph / DAG Engine？”

回答思路：

> 当前业务图只有一个固定 prerequisite 和两个并行 branch，拓扑稳定，变化频率低。如果为了三个节点建立通用 DAG DSL，会额外引入状态管理、节点注册和生命周期复杂度，但没有解决实际需求。所以采用业务专用 orchestrator；未来只有在 workflow 数量、动态拓扑或持久化需求明显增加时再抽象。

------

# 7. 三个 Agent 的职责为什么必须严格分开

## DocumentAnalysisAgent

负责：

> “这个 Feature 到底改了什么？”

输入：

```
FeatureDocument
```

输出：

```
feature_summary
change_points
affected_components
potential_risk_areas
uncertainty
```

它不允许：

- 查 Historical Issues；
- 查 TestPlan；
- 看 Ground Truth；
- 给最终 HIGH / MEDIUM / LOW。

30_zcode_execution(3).mdMD

------

## RiskRetrievalAgent

负责：

> “这些变化能找到哪些历史 Evidence，并基于这些 Evidence 推断哪些风险？”

执行：

```
Change Points
      ↓
Query
      ↓
Historical Retriever
+
HistoricalIssue Provider
      ↓
Source Facts
      ↓
LLM
      ↓
Risk Findings
```

------

## TestReviewAgent

负责：

> “已有测试证据覆盖到什么程度，还可能缺什么？”

执行：

```
Change Points
      ↓
TestPlan / TestCase Provider
      ↓
Source Facts
      ↓
LLM
      ↓
Coverage Analysis
+
Missing Test Recommendation
```

------

# 8. 最重要的真实性设计：FACT 和 INFERENCE 必须分开

这是 WP2 最值得记住的设计之一。

Risk Agent 的结构不是：

```
LLM
→ HistoricalIssue
→ Risk
```

而是：

```
Provider
→ HistoricalIssue        FACT

Retriever
→ EvidenceRef            FACT

LLM
→ RiskFinding            INFERENCE
```

最终结果也明确分：

```
retrieved_historical_issues
retrieved_evidence

agent_inferred_risk_findings
```

30_zcode_execution(3).mdMD

这样可以避免一种很危险的错误：

> LLM 自己说“历史上 Kubernetes Issue #12345 曾经出现这个问题”，系统随后把这句话当真实历史数据。

------

# 9. EvidenceRef 为什么不能让 LLM 创建

最终冻结：

```
EVIDENCE_OWNER =
DataProvider / HistoricalKnowledgeRetriever
```

LLM 只能：

```
consume
select
reference
```

不能创建：

```
source_url
evidence_id
issue_id
HistoricalIssue
```

Codex Final Review 也实际确认：

```
LLM_CAN_CREATE_EVIDENCE_IDENTITY = NO
UNKNOWN_EVIDENCE_FILTER = PASS
```

40_codex_review(2).mdMD

真实 Smoke 中：

```
UNKNOWN_EVIDENCE_REFERENCES = 0
FILTERED_INVALID_FINDINGS = 0
```

80_real_model_smoke_retry2.mdMD

------

# 10. 一个非常重要的防幻觉模式

模型可能输出：

```
{
  "risk": "...",
  "evidence_ids": ["fake-evidence-123"]
}
```

系统不能因为 JSON Schema 合法就接受。

因为：

> Schema Validity（结构合法）≠ Referential Integrity（引用完整性）。

所以 WP2 又做了一层：

```
Model Finding
      ↓
evidence ID exists?
issue ID exists?
      ↓
YES → accepted finding
NO  → filtered_invalid_findings
```

这其实和数据库中的：

**Foreign Key（外键）**

思想非常接近。

面试可以说：

> 对 LLM Structured Output，我不只做 schema validation，还做 reference validation。因为模型完全可能生成结构合法但事实身份不存在的 ID，所以 EvidenceRef 和 Issue ID 需要再和 provider 返回集合做 referential integrity 校验。

这是非常好的 Agent 工程回答。

------

# 11. TestReview 中最大的语义陷阱：没有 TestCase ≠ 没有覆盖

当前 Kubernetes Dataset：

```
TestPlan = REAL
TestCase[] = []
```

所以最终定义：

```
NO_TEST_DATA
PLAN_ONLY
PARTIAL_COVERAGE
COVERED
```

其中：

```
NO_TEST_DATA
=
TestPlan[] empty
AND
TestCase[] empty
```

而：

```
PLAN_ONLY
=
TestPlan[] non-empty
AND
TestCase[] empty
```

20_codex_decision(1).mdMD

因此：

```
TestCase[] = []
```

不能推导：

```
NO_COVERAGE
```

因为真实情况只是：

> 我们有 Test Plan，但是还没有映射到具体 test function。

------

# 12. 真实模型是否守住了 PLAN_ONLY

是。

真实 DeepSeek 执行中：

```
TEST_PLAN_COUNT = 1
TEST_CASE_COUNT = 0
COVERAGE_STATE = PLAN_ONLY
```

而且模型没有说：

> “没有任何测试覆盖。”

相反，它识别到已有 Test Plan，只是在此基础上提出 potential gaps 和 recommended missing cases。80_real_model_smoke_retry2.mdMD

这很重要，因为 Fake Test 只能证明代码逻辑。

真实 Smoke 才证明：

> 模型实际运行时也没有把这个数据不完整状态误解成零覆盖。

------

# 13. 为什么 `recommended_missing_cases` 可以由 LLM 创建

因为这个字段的语义明确是：

```
RECOMMENDATION
```

不是：

```
EXISTING TEST FACT
```

所以：

```
Existing TestPlan
Existing TestCase
```

必须来自 Provider。

而：

```
Recommended Missing Case
```

可以由 LLM 推断。

这就是：

> **事实字段和建议字段要有不同的 Authority。**

------

# 14. 并行为什么用 asyncio.gather，而不是 TaskGroup

Codex 冻结：

```
asyncio.gather(..., return_exceptions=True)
```

20_codex_decision(1).mdMD

这是一个很好的 Python 异步面试题。

## TaskGroup 默认更偏 fail-fast

一个 child 失败：

```
→ sibling cancellation
```

但业务要求：

```
RiskRetrieval FAILED
      ↓
TestReview 仍应继续
      ↓
保留 TestReview result
```

所以：

```
asyncio.gather(..., return_exceptions=True)
```

更符合业务语义。

关键不是：

> “哪个 API 更新？”

而是：

> **哪个 primitive 的 failure semantics 更符合业务。**

------

# 15. 如何证明它真的并行，而不是看起来并行

ZCode 没采用：

```
耗时 < 2 秒
```

这种脆弱测试。

而是使用两个：

```
asyncio.Event
```

构造同步 barrier。

Risk branch：

```
我启动了
↓
等 Test branch 也启动
```

Test branch：

```
我启动了
↓
等 Risk branch 也启动
```

如果是串行：

```
Risk 启动
↓
一直等 Test
↓
但 Test 永远启动不了
```

测试就失败。

Codex Final Review 确认该测试真实验证了 overlap。40_codex_review(2).mdMD

### 面试答法

> 并发测试我没有依赖 wall-clock threshold，因为 CI 机器负载会造成 flaky test。我通过 asyncio.Event 让两个 branch 互相等待对方进入，从逻辑上证明它们存在执行重叠；串行实现一定无法通过这个 barrier。

------

# 16. Failure Semantics 为什么要提前冻结

最终状态：

```
BranchStatus:
SUCCESS
FAILED
NOT_STARTED

WorkflowStatus:
SUCCESS
PARTIAL
FAILED
```

20_codex_decision(1).mdMD

具体：

### DocumentAnalysis 失败

```
Workflow = FAILED
Risk = NOT_STARTED
Test = NOT_STARTED
```

因为两个 branch 都依赖它。

------

### Risk 失败、Test 成功

```
Workflow = PARTIAL
Risk = FAILED
Test = SUCCESS
```

成功结果必须保留。

------

### Test 失败、Risk 成功

```
Workflow = PARTIAL
Risk = SUCCESS
Test = FAILED
```

------

### 两个下游都失败

```
Workflow = FAILED
```

但 DocumentAnalysis 结果仍然保留。

------

# 17. 为什么“两下游都失败”不是 PARTIAL

因为：

```
DocumentAnalysis
```

只是 prerequisite。

用户真正请求的是：

> Feature Risk Review。

如果：

```
Risk Analysis FAILED
Test Review FAILED
```

那么仅有：

```
Feature Summary
```

并没有交付业务核心价值。

因此：

```
FAILED
```

更符合业务语义。

但是：

```
DocumentAnalysisResult
```

仍保留用于 debug 和 evidence traceability。

这是：

> **Result Preservation（结果保留）和 Success Semantics（成功语义）是两件不同的事情。**

------

# 18. Partial Result 为什么很重要

很多简单 Agent Workflow：

```
await asyncio.gather(...)
```

只要一个异常：

```
整次执行失败
```

这意味着：

> 已经花成本得到的另一条高价值结果也被扔掉。

WP2 则明确：

```
one branch fails
→ preserve sibling result
→ workflow PARTIAL
```

对于真实 AI Workflow 非常重要，因为模型、Tool、Retrieval 都比普通纯函数更容易发生局部失败。

------

# 19. BranchFailure 为什么不能保存完整 traceback

业务 DTO 只保留：

```
branch
error_type
message
recoverable
```

而不是：

```
traceback
raw prompt
raw response
credential
```

40_codex_review(2).mdMD

因为业务结果和诊断日志不是同一层。

> 业务 Result 应该表达“发生了什么”；Debug Log 才表达“内部怎么炸的”。

否则：

- 泄漏 Prompt；
- 泄漏模型输出；
- 泄漏环境信息；
- DTO 越来越重。

------

# 20. Retrieval 最开始为什么需要补数据

原始 WP0 corpus 只有：

- 5 个 KEP；
- 5 个 enhancement tracking issue。

ZCode 做 retrieval spike 后：

```
meaningful evidence = 1 / 5
```

所以按照之前冻结的停止条件，进行了非常小范围 enrichment：

```
10 real kubernetes/kubernetes issue snapshots
2 per case
```

之后启发式 spike：

```
5 / 5
```

30_zcode_execution(3).mdMD

这不是自动造数据，而是真实 Kubernetes Issue snapshot。

------

# 21. 为什么补 10 条 Issue 不算 Ground Truth Leakage

Codex 专门审核了这一点。

最终所有：

```
111 chunks
```

进入一个共享 corpus。

没有：

```
case_id == k8s_541
→ only search 541 issues
```

这种 query-time filtering。

所有 Case 都可以检索整个共享 corpus。40_codex_review(2).mdMD

所以：

```
case → fixed correct evidence
```

没有被硬编码。

这延续了 Phase3 一个非常重要的 Authority 原则：

> **Ground Truth 不能控制 Retrieval Population。**

------

# 22. Retrieval 为什么最后没有用 Vector RAG

最终实际实现：

```
SourcePreservingLexicalRetriever
```

使用：

```
lexical overlap
+
small source boost
```

而不是：

```
embedding
vector DB
BM25/RRF
Cross-Encoder
```

30_zcode_execution(3).mdMD

这不是“RAG 做得差”。

这是一个刻意控制 Phase4 范围的工程选择。

因为 Phase3 已经专门完成 Retrieval Evaluation。

Phase4 的目的不是：

> 再做一次 retrieval research。

而是：

> 把 retrieval 真正装进一个业务 Agent Workflow。

------

# 23. 这里应该怎么在面试描述 RAG

不要说：

> “WP2 使用向量数据库构建高级 RAG。”

实际上：

```
VECTOR_INDEX = NO
LOCAL_LEXICAL_INDEX = YES
```

40_codex_review(2).mdMD

正确描述：

> Phase4 的业务 Demo 使用 source-preserving lexical retrieval，从真实 Kubernetes historical corpus 检索 Evidence；此前 Phase3 已独立评估 BM25、Dense、RRF、Cross-Encoder 等 candidate，但 Phase4 没有为了 Demo 强行启用全部候选方案。

------

# 24. 实际真实 Smoke 发现的 Retrieval 观察

真实 `k8s_541` Risk Query 的 top-5：

全部是：

```
k8s_541 自身 KEP sections
```

例如：

- Provider input format；
- Provider configuration；
- Provider output format；
- Proposal。

10 条 enrichment bug snapshot 没进 top-5。80_real_model_smoke_retry2.mdMD

这个结果很重要。

但当前不能说：

```
Retriever 不好
```

也不能说：

```
Retriever 很好
```

因为还没有 Ground Truth。

因此正确状态：

```
OBSERVATION =
REAL_RISK_RETRIEVAL_TOP5_SELF_KEP_DOMINATED
```

留到 WP4 Evaluation。

------

# 25. 为什么不能看到这个现象就立刻调 K / Boost

因为那会变成：

```
看真实结果
↓
觉得不好
↓
调 scoring
↓
再跑
↓
直到满意
```

这会造成 Evaluation Contamination（评测污染）。

所以 WP2 坚持：

```
record observation
do not tune
```

这个纪律非常值得面试讲。

------

# 26. WP2 最大的真实 Bad Case：DeepSeek Structured Output

第一次真实 Smoke：

```
deepseek/deepseek-chat
```

请求真的到达 Provider。

但是 DeepSeek 拒绝：

```
response_format.type = json_schema
```

错误：

> ```
> This response_format type is unavailable now
> ```

所以：

```
DocumentAnalysis = FAILED
Risk = NOT_STARTED
Test = NOT_STARTED
```

50_real_model_smoke.mdMD

------

# 27. 这个 Bad Case 的真正根因是什么

不是：

```
DeepSeek质量差
Prompt写错
Agent架构失败
```

而是：

```
MODEL_PROVIDER_STRUCTURED_OUTPUT_CAPABILITY_MISMATCH
```

也就是：

> Model Adapter 隐式假设所有 LiteLLM Provider 都支持 OpenAI-style JSON Schema。

真实世界中，不同 Provider 能力不同。

这是非常典型的：

**External Capability Mismatch（外部能力不匹配）。**

------

# 28. 为什么不直接换模型

最简单确实是：

```
DeepSeek不支持
↓
换Gemini/OpenAI
```

但是这样会留下一个问题：

> 业务层依赖某个 Provider 的特殊能力。

所以最终选择：

```
Port 保持不变
Adapter 吸收 Provider 差异
```

这是标准的：

**Ports and Adapters（端口与适配器）**

思想。

------

# 29. DeepSeek compatibility 最终怎么做

最终：

```
FeatureRiskReviewModelPort
        ↓
Provider capability decision
        ↓
┌─────────────────────────────┐
│                             │
↓                             ↓
DeepSeek                 Native Provider
json_text                json_schema
│                             │
└─────────────┬───────────────┘
              ↓
parse_structured_model_output
              ↓
Pydantic strict validation
              ↓
typed result
```

60_zcode_model_compat_fix.mdMD

------

# 30. 最关键的原则：降 Transport，不降 Contract

DeepSeek 路径不再发送：

```
response_format=json_schema
```

但仍要求：

```
Return only valid JSON
```

然后：

```
json.loads
↓
Pydantic model_validate
```

因此：

```
Provider Constraint ↓
Business Contract 不变
```

这是整个修复最值得学习的一句话：

> **兼容外部 Provider 时，可以降低 transport-level guarantees，但不能因此降低 application-level validation。**

------

# 31. 为什么不做自动 fallback retry

没有写：

```
try:
    call(json_schema)
except:
    call(json_text)
```

最终 Codex 确认：

```
AUTOMATIC_RUNTIME_FALLBACK_RETRY = NO
PROVIDER_REQUESTS_PER_AGENT_INVOCATION = 1
```

70_codex_model_compat_review.mdMD

原因：

如果所有异常都 fallback：

```
401
429
timeout
provider 500
schema unsupported
```

都会被误认为“json_schema 不支持”。

而且一次 Agent invocation 可能偷偷发两次模型请求。

这会破坏：

- Cost semantics；
- Latency；
- Observability；
- Failure semantics。

------

# 32. Provider Capability 应该在哪一层处理

不能写进：

```
DocumentAnalysisAgent
RiskRetrievalAgent
TestReviewAgent
```

而应该：

```
Agent
↓
FeatureRiskReviewModelPort
↓
LiteLLM Adapter
↓
Provider-specific handling
```

这就是经典的：

> **业务逻辑不知道外部 Provider 差异。**

------

# 33. 为什么 DeepSeek JSON 模式还要传 Schema

DeepSeek native `json_schema` 不支持。

但 Prompt 中需要知道目标 JSON shape。

最终没有手写第二套 Schema。

而是：

```
response_schema.model_json_schema()
```

生成 Schema instruction。60_zcode_model_compat_fix.mdMD

因此：

```
SCHEMA_AUTHORITY = PYDANTIC_MODEL
```

70_codex_model_compat_review.mdMD

避免：

```
Pydantic字段更新
↓
Prompt里手写schema忘了更新
↓
Contract drift
```

------

# 34. Structured Output 为什么不能只靠 JSON Schema

即便 Provider 支持：

```
response_format=json_schema
```

应用层仍然应该：

```
parse
+
validate
```

因为：

> 外部服务约束不应该成为内部 Contract 的唯一保护层。

所以 WP2 最终两种 Provider path 都统一经过：

```
parse_structured_model_output
↓
Pydantic validation
```

------

# 35. Real Smoke #2 真正证明了什么

第二次 Smoke：

```
DeepSeek json_text
↓
real model
↓
valid JSON
↓
production parser
↓
Pydantic
```

三个 Agent 全通过。80_real_model_smoke_retry2.mdMD

所以现在可以说：

> Structured Output compatibility 不是只有 unit test 证明，而是被真实 DeepSeek execution 验证。

这是 Bad Case 闭环。

------

# 36. 但 Real Smoke 成功不等于 Evaluation 成功

这是一定要注意的。

当前：

```
REAL_THREE_AGENT_SMOKE = YES
```

只能证明：

> 系统真实能执行。

不能证明：

```
风险识别正确
Historical Issue Recall 很高
Coverage Gap 正确
Citation 正确
```

因为：

```
GROUND_TRUTH = PENDING
QUALITY_EVALUATION = NOT_RUN
```

80_real_model_smoke_retry2.mdMD

这就是：

> **Execution Correctness（执行正确性）≠ Task Quality（任务质量）。**

------

# 37. 高频面试问题

## Q1：你的 Multi-Agent Workflow 是怎么编排的？

可以回答：

> 我实现的是一个固定业务拓扑，而不是通用 DAG Engine。DocumentAnalysisAgent 先分析 Feature，产出 change points、affected components 和 risk areas；然后 RiskRetrievalAgent 和 TestReviewAgent 并行执行，前者查历史知识和 Issue，后者检查 Test Plan / Test Case，最后由 workflow join typed results。两个下游使用 `asyncio.gather(return_exceptions=True)`，这样一个分支失败时不会取消另一个分支，可以保留 partial result。

------

# 38. Q2：为什么不用 TaskGroup？

> 这个场景不是 fail-fast。RiskRetrieval 失败时，我仍希望 TestReview 完成并返回结果。TaskGroup 默认会在 child exception 后取消 sibling，而 `gather(return_exceptions=True)` 更贴合 sibling-result-preservation 的业务语义，所以我是根据 failure semantics 选 primitive，不是根据 API 新旧选。

------

# 39. Q3：怎么证明是真的并发？

> 我没有用耗时阈值，因为那在 CI 中很不稳定。我用两个 `asyncio.Event` 做 barrier，让两个 downstream branch 在执行时等待对方进入；如果实现是串行的，第一个分支就永远等不到第二个，因此测试会失败。这样证明的是逻辑上的 overlap。

------

# 40. Q4：Agent 怎么避免伪造历史 Issue？

> HistoricalIssue 和 EvidenceRef 都由 DataProvider / Retriever 创建，模型只能引用已有 identity。Structured Output 后除了 Pydantic schema validation，我还会校验模型返回的 issue_id 和 evidence_id 是否存在于本次 retrieval/provider result 中。结构合法但引用不存在的 finding 会进入 filtered_invalid_findings，而不是业务结果。

------

# 41. Q5：为什么不用 LLM 自己检索和生成 citation？

> 因为 citation identity 属于系统事实，而不是模型推断。如果允许模型自己生成 source_url 或 issue_id，会把 hallucination 混入事实层。我把检索到的 Evidence identity 交给模型，模型只能选择和引用，而不能创造。

------

# 42. Q6：测试用例为空时怎么处理？

> 当前 Kubernetes 数据有真实 Test Plan，但没有可靠的 test-function mapping。因此我没有把 `TestCase=[]` 当成 no coverage，而是定义 `PLAN_ONLY` 状态。只有 TestPlan 和 TestCase 都为空才是 `NO_TEST_DATA`。这样 Contract 能表达真实数据的不完整，而不是为了 Demo 强行造测试用例。

------

# 43. Q7：为什么 Phase4 不直接上向量 RAG？

> Phase3 已经单独评估过 Dense、BM25、RRF 和 Cross-Encoder。Phase4 的目标是验证业务 workflow，不是重复做 retrieval research，所以采用最小 source-preserving lexical retriever，把真实 Kubernetes Evidence 接进 Agent。后续 retrieval quality 是否足够，再由正式 Evaluation 判断，而不是凭一次 Demo 调参。

------

# 44. Q8：你遇到过模型 Provider 不兼容吗？

这个 WP 现在有一个非常好的真实回答：

> 有。第一次真实三 Agent Smoke 使用 DeepSeek 时，请求已经到 Provider，但 DeepSeek 当时不支持我们使用的 OpenAI-style `response_format=json_schema`，所以 DocumentAnalysis 第一跳就失败。根因不是 Prompt 或模型质量，而是 Provider capability mismatch。我没有直接换模型，而是在 Adapter 层增加 DeepSeek `json_text` 兼容路径，业务 Port 和 Typed Contract 不变，最后仍统一经过 JSON parse 和 Pydantic strict validation。修复后同一个 Case、同一个 DeepSeek、同一业务 Prompt重新执行，三个 Agent 全部成功。

这是这整个 WP 最强的真实 Bad Case。

------

# 45. Q9：为什么不用失败后自动 fallback？

> 我没有做 `json_schema` 请求失败后再自动发一次 `json_text` 请求，因为这会把一次 Agent invocation 变成两次 Provider 调用，而且 auth、429、timeout 等异常也可能被误分类为 capability issue。我是在请求前根据 Provider identity 选择 transport mode，因此一次 invocation 始终对应一次 Provider 请求。

------

# 46. Q10：为什么 Smoke SUCCESS 还不能说系统质量好？

> Smoke 只验证 execution reality，也就是三个 Agent、retrieval、parallel workflow 和 structured output 能真实跑通。它没有 Ground Truth，因此不能计算 risk accuracy、coverage gap accuracy 或 citation correctness。Execution success 和 task quality 是两层问题。

------

# 47. 工程构建方法类问题

## “什么时候应该抽象成通用 Workflow Engine？”

考虑四类信号：

```
1. 多个 Workflow 重复相同 orchestration pattern
2. 拓扑运行时动态变化
3. 需要持久化 / resume
4. 需要统一 retry / timeout / observability
```

当前都没有达到必须抽象的程度。

所以：

```
specific orchestrator
```

更合适。

------

# 48. “Multi-Agent 应该怎么划职责？”

比较好的原则：

> 按信息权限和业务责任划分，而不是按 Prompt 数量划分。

本 WP：

```
Document Agent
= Feature understanding

Risk Agent
= historical evidence + risk inference

Test Agent
= test evidence + coverage inference
```

不是为了“显得 Multi-Agent”硬拆三个模型调用。

------

# 49. “什么时候并行，什么时候串行？”

判断是否存在：

**Data Dependency（数据依赖）。**

这里：

```
Risk Agent
Test Agent
```

都依赖：

```
DocumentAnalysisResult
```

所以不能和 Document Agent 并行。

而二者之间互不依赖：

```
Risk || Test
```

才适合并行。

------

# 50. “Agent 输出应该全是自由文本还是全结构化？”

都不是。

推荐：

```
Machine boundary
→ structured

Human-facing narrative
→ natural language
```

WP2 中 Agent 之间交换：

```
DocumentAnalysisResult
RiskRetrievalResult
TestReviewResult
```

而最终 WP3 Report 才面向人类可读表达。

------

# 51. “Provider Compatibility 应该做成能力注册中心吗？”

Phase4 不需要。

现在真实问题只有：

```
DeepSeek json_schema unsupported
```

一个小显式 compatibility rule 足够。

只有当模型 Provider 数量很多、能力矩阵经常变化时，再考虑：

```
Capability Registry
Feature Detection
Negotiation
```

当前建会过度工程。

------

# 52. Trade-off 总结

| 决策                     | 备选                 | 最终选择                       | 原因                      |
| ------------------------ | -------------------- | ------------------------------ | ------------------------- |
| Workflow                 | 通用 DAG             | 具体 orchestrator              | 拓扑固定                  |
| Runtime                  | LocalAgent Runtime   | AgentEvalOps workflow          | Owner 不匹配              |
| 并发                     | TaskGroup            | gather(return_exceptions=True) | 需要 sibling preservation |
| Evidence                 | LLM 创建             | Provider 创建                  | 防幻觉                    |
| TestCase 缺失            | 当无覆盖             | PLAN_ONLY                      | 保持真实性                |
| RAG                      | Vector/Hybrid        | Lexical                        | Phase4 控制范围           |
| DeepSeek incompatibility | 换模型               | Adapter compatibility          | 保持业务模型独立          |
| Compatibility            | error fallback retry | pre-call mode decision         | 单请求、失败语义清晰      |
| Schema                   | Prompt 手写          | Pydantic model_json_schema     | 单一 Authority            |
| Smoke 后 retrieval       | 立即调参             | 记录 observation               | 防评测污染                |

------

# 53. 真实 Bad Case 档案

## Bad Case 1：Provider 不支持 Structured Output

**真实性：真实发生。**

触发：

```
deepseek/deepseek-chat
+
response_format.type=json_schema
```

结果：

```
BadRequestError
"This response_format type is unavailable now"
```

风险：

> Agent 在业务逻辑执行前直接失败。

根因：

> Adapter 把 OpenAI-style capability 当成所有 Provider 的共同能力。

修复：

```
DeepSeek
→ json_text mode
→ generated schema instruction
→ strict parser
→ Pydantic validation
```

回归：

- DeepSeek 不发送 `json_schema`
- Native Provider 保留 `json_schema`
- invalid JSON rejected
- schema violation rejected
- one request per invocation

真实复验：

```
k8s_541
+
same DeepSeek
→ three agents SUCCESS
```

70_codex_model_compat_review.mdMD 80_real_model_smoke_retry2.mdMD

------

# 54. Bad Case 2：Historical corpus 初始检索价值不足

**真实性：实施中真实发现。**

初始：

```
meaningful_evidence_cases = 1/5
```

采取：

> 小范围补 10 条真实 Kubernetes Issue snapshot。

最终 heuristic spike：

```
5/5
```

但真实 Smoke 又发现：

```
top5 = self KEP dominated
```

所以：

> “Spike 5/5”不能被宣传为“真实历史 Bug 检索质量很好”。

这是一个特别好的 Evaluation Literacy（评测素养）案例。

------

# 55. Bad Case 3：TestCase 缺失可能被误判成无覆盖

**真实性：这是架构设计时预防的风险，真实 Smoke 没触发。**

风险：

```
TestCase=[]
→ Model says no tests exist
```

设计：

```
PLAN_ONLY
```

真实 Smoke：

> 模型正确识别已有 Test Plan。

因此：

```
PREVENTED / NOT OBSERVED IN REAL SMOKE
```

不要把它说成“真实发生过”。

------

# 56. Truthful Implementation Boundary

## 可以说已经实现

```
✓ Three-Agent Workflow
✓ Dependency-aware orchestration
✓ Real parallel branches
✓ Partial Result semantics
✓ Real Kubernetes Data Provider
✓ Historical lexical retrieval
✓ EvidenceRef propagation
✓ Evidence identity validation
✓ Source Fact / Inference separation
✓ PLAN_ONLY coverage semantics
✓ Structured model outputs
✓ DeepSeek compatibility adapter
✓ Real DeepSeek three-agent smoke
```

------

## 还不能说

```
✗ Feature Risk Review Final Report
✗ Final HIGH/MEDIUM/LOW Risk Level
✗ Priority
✗ Ground Truth completed
✗ Citation Correctness evaluated
✗ Retrieval ranking quality evaluated
✗ Risk Accuracy evaluated
✗ Coverage Gap Accuracy evaluated
✗ Production Workflow deployed
```

------

# 57. 面试时最容易夸大的地方

不要说：

> “我们构建了向量 RAG。”

没有。

当前：

```
LOCAL_LEXICAL_INDEX = YES
VECTOR_INDEX = NO
```

------

不要说：

> “Risk Agent 检索到了历史 Kubernetes Bug。”

真实 Smoke 的 top-5 并没有命中 enrichment bug snapshot。80_real_model_smoke_retry2.mdMD

------

不要说：

> “Citation 已验证正确。”

现在只是：

```
CITATION_TRACEABILITY = IMPLEMENTED
CITATION_CORRECTNESS = NOT_EVALUATED
```

------

不要说：

> “Test Coverage Accuracy 已验证。”

当前没有 Ground Truth。

------

# 58. 简历最终可以怎么写

WP2 单独可以形成一个很不错的技术 Bullet：

> 设计并实现 Feature Risk Review 三智能体工作流，将特性解析、历史风险检索与测试覆盖审查拆分为 Typed Agent，通过 `asyncio.gather` 实现下游并行与 Partial Result 保留；对 LLM 输出增加 Evidence identity 校验，限制模型只能引用真实 Provider/Retriever 证据，并完成真实 DeepSeek 三 Agent 执行闭环。

第二条可以写 Provider Bad Case：

> 解决 DeepSeek 不支持 OpenAI-style JSON Schema Structured Output 的真实兼容问题，将 Provider 差异收敛在 Model Adapter，通过 JSON-text transport + Pydantic strict validation 保持业务 Contract 不变，并确保单次 Agent invocation 仅产生一次模型请求。

这两条都是真实经历。

------

# 59. 如果面试官问“这个项目最有价值的工程点是什么”

我建议不要回答：

> “用了三个 Agent。”

而是：

> 我觉得最有价值的是把 LLM 推断和系统事实分开。历史 Issue、Test Plan 和 Evidence identity 都由系统 Provider 拥有，模型只能基于这些事实做推断，不能自己创造 citation；同时 Multi-Agent Workflow 对并发、partial failure 和 provider capability 都有明确 Contract。这样这个 Demo 不只是多个 Prompt 串起来，而是有可信执行边界的 Agent Workflow。

这个回答明显比“用了 RAG + Multi-Agent”更高级。

------

# 60. WP2 最值得记住的 8 句话

如果面试前只复习这一节，就记下面八句：

1. **Multi-Agent 的价值不在 Agent 数量，而在职责、数据权限和失败边界。**
2. **Workflow abstraction 要匹配业务 Owner，已有 Runtime 不代表必须复用。**
3. **并发 primitive 应按 failure semantics 选择；本场景需要 sibling preservation，所以用 `gather(return_exceptions=True)`。**
4. **HistoricalIssue / TestPlan / EvidenceRef 是 Source Fact，RiskFinding / Coverage Gap 是 LLM Inference。**
5. **Structured Output 仅通过 Schema 校验还不够，还需要 Evidence ID 的 Referential Integrity 校验。**
6. **TestCase 为空不等于没有测试，当前真实状态是 `PLAN_ONLY`。**
7. **Provider 兼容应该由 Adapter 吸收；可以降低 transport constraint，但不能降低 business validation。**
8. **Real Smoke SUCCESS 只证明系统真实能跑，不证明任务质量已经通过 Evaluation。**

------

# 61. 推荐学习文档文件名

按照我们最新约定，统一使用小写路径：

```
docs/interview/stage5_phase4_wp2_three_agent_risk_review_workflow.md
```

这个命名方式后续 WP 都保持一致。

------

# 62. WP2 学习阶段最终状态

```
WP2_IMPLEMENTATION = COMPLETE
WP2_FINAL_REVIEW = PASS
WP2_REAL_MODEL_SMOKE = PASS

WP2_READY_FOR_WP3 = YES
```

保留进入后续阶段的观察：

```
REAL_RISK_RETRIEVAL_TOP5_SELF_KEP_DOMINATED
GROUND_TRUTH_PENDING
TEST_CASE_MAPPING_PARTIAL
CITATION_CORRECTNESS_NOT_EVALUATED
```

这些不是 WP2 未完成，而是后续 WP3 / WP4 需要继续解决或评估的问题。

WP2 的学习/面试总结到这里正式收口。