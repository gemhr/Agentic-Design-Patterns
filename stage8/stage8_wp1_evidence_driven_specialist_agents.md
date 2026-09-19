当前对话使用 **GPT-5.6 Sol**。

下面进入 **Stage8-WP1 — Evidence-driven Specialist Agents** 的学习 / 面试总结。

推荐学习文档文件名：

```text
docs/interview/stage8_wp1_evidence_driven_specialist_agents.md
```

WP1 最终状态：

```ini
WP1_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 3
KNOWN_BUGS = 0
ARCHITECTURE_REOPEN_REQUIRED = NO
```

本 WP 已经真正完成：

```text
Feature Context
→ Feature Understanding
→ Evidence-bound Risk Analysis
→ Risk-driven Test Planning
→ Durable TestPlan
→ Business Review
```

而且独立 Agent API 与 Mission Workflow 共用同一套 `SpecialistAgentApplicationService`。

------

# 1. 名词 / 概念速览

**专业化智能体（Specialist Agent）**
只负责一个明确业务能力的 Agent，例如 Risk Analysis，而不是一个 Agent 承担整条工作流。

**类型化输入 / 输出（Typed Input / Typed Output）**
Agent 的输入输出受明确 Schema 约束，而不是任意自然语言字符串。

**结构化输出（Structured Output）**
要求模型生成符合指定数据结构的结果，本项目采用 JSON + Pydantic 本地校验。

**有界修复（Bounded Repair）**
模型结构化输出失败后只允许有限次数重新生成；WP1 是初始调用后最多再 repair 一次。

**证据引用（Evidence Reference）**
Risk 等推理结果指向具体输入材料的引用，使结论可以追溯。

**证据权威（Evidence Authority）**
决定哪些 Evidence 真实存在的组件；WP1 中由 `FeatureContext` 而不是 LLM 持有。

**风险驱动测试（Risk-driven Testing）**
先识别风险，再针对 Risk 生成 Test Scenario，而不是直接从 Feature 批量生成 Case。

**覆盖绑定（Risk Coverage Binding）**
`TestScenario.covered_risk_ids` 必须引用真实存在的 Risk ID。

**规范化 JSON（Canonical JSON）**
通过稳定的 key 排序和序列化规则，使相同业务内容得到稳定表示。

**内容摘要（Digest）**
对规范化后的 TestPlan 计算 SHA-256，用于 Business Review 精确绑定被审核内容。

**持久化主题（Durable Subject）**
Business Review 所审核的对象必须是数据库中的稳定业务对象，而不是瞬时内存结果。

**智能体注册表（Agent Registry）**
AgentCore 中保存稳定 Agent identity 与 adapter binding 的统一注册机制。

**应用层门面（Application Service Facade）**
在现有 Runtime 上增加业务 Typed Contract，而不是重做底层 Agent Framework。

------

# 2. 这个 WP 解决什么业务问题

WP0 解决的是：

> 一次 Feature Testing Process 怎么长期存在。

WP1 开始解决：

> **Agent 到底如何真正参与测试分析，而且它的输出怎么做到可验证、可解释、可以进入后续业务流程。**

最简单的错误路线是：

```text
Feature 文档
→ LLM
→ “这里有一些风险”
→ LLM
→ “建议测试以下内容”
```

这种方案有三个严重问题。

第一，输出没有稳定 Contract。

今天模型可能输出：

```text
风险：建链失败
```

明天可能输出：

```text
{
  "possible_issue": ...
}
```

后续程序没办法可靠消费。

第二，“Evidence”可能是假的。

如果只是让 LLM 自己输出：

```json
{
  "risk": "Cell Setup Failure",
  "evidence": "code_diff_123"
}
```

系统却从来没有检查 `code_diff_123` 是否真实存在，那么所谓“证据驱动”只是模型自己给自己的结论编了一个引用。

第三，Test Plan 可能和 Risk 没有关系。

错误链路：

```text
Feature → Risk
Feature → TestPlan
```

虽然页面上同时展示了 Risk 和 TestPlan，但后者可能根本没有根据前者规划。

WP1 最终把它改造成：

```text
FeatureContext
    ↓
Feature Understanding
    ↓
RiskAnalysisResult
    ├─ risk_id
    ├─ failure_mode
    ├─ confidence
    └─ evidence_id[]
    ↓
TestPlanResult
    └─ TestScenario.covered_risk_ids[]
    ↓
PostgreSQL TestPlan
    ├─ version
    └─ digest
    ↓
Business Review
```

因此这不是单纯“让 LLM 输出 JSON”，而是把 AI 推理结果真正变成了一个可以进入业务系统的 **Typed Business Artifact**。

------

# 3. 工程构建方法问答

## 为什么 Specialist Agent 不直接调用模型 Provider？

因为 Model Invocation 的 Owner 已经在 AgentCore。

当前正确链路是：

```text
SpecialistAgentApplicationService
→ CoordinatedRuntimeFactory.create_static_run_scope()
→ existing Agent Adapter
→ AgentRouter
→ ModelInvocationRouter
→ Provider
```

而不是：

```text
RiskAnalysisService
→ DeepSeek API
```

Sol 已经确认 Feature Understanding、Risk Analysis、Test Planning 都注册到了既有 Agent Registry，并走现有 Runtime，没有新增第二套 Runtime、Registry 或 Provider path。

面试可以直接说：

> 业务层只负责 Risk/TestPlan 的业务 Contract，模型调用、deadline、runtime lifecycle 还是归统一 Harness 管。

------

## 为什么 Typed Output 不直接依赖 Provider Structured Output？

因为项目当前 Provider profile 不能假定稳定提供原生 Structured Output。

所以采用：

```text
Model Text
→ JSON Extraction
→ Pydantic Validation
```

如果失败：

```text
→ Repair once
→ Validation again
```

如果再次失败：

```text
→ Fail
```

而不是构造默认结果假装成功。

最终实现已经收紧成 strict JSON + Pydantic，而且 schema、Evidence、feature binding、risk ID、coverage 等语义错误都共享同一个 repair budget。

------

## 为什么 Repair 只能一次？

因为 Repair 本质仍然是一次模型调用。

如果：

```text
JSON parse error → retry
Evidence error → retry
Risk ID error → retry
Coverage error → retry
```

每类错误各重试一次，很容易变成一个隐式 Agent Loop。

所以 WP1 的原则是：

```text
Initial
+
at most one repair
```

无论什么 Validation Error，都消耗同一个 Repair Budget。

面试关键词：

**有界重试（Bounded Retry）**、**预算控制（Budget Control）**、**确定性失败边界（Deterministic Failure Boundary）**。

------

## 为什么 Evidence 不能完全让模型自己生成？

因为模型是推理者，不是事实 Authority。

假设 Context 中真实只有：

```text
DOC-1
DIFF-1
MEETING-1
```

模型却返回：

```text
TICKET-9381
```

如果系统直接接受，模型实际上完成了：

```text
生成结论
+
生成支持自己结论的证据
```

这在测试风险分析里没有可信度。

所以 WP1 修复后：

```text
FeatureContext
→ authoritative evidence map
```

模型只能返回：

```text
evidence_id
+
interpretation
```

然后系统重新从 Evidence Map 中恢复：

```text
source_type
source_ref
真实 source identity
```

这次 Sol 审计真实发现 Luna 初版允许模型自造 Evidence，并进行了修复。未知 Evidence ID 现在会进入一次 repair，再错则明确失败。

------

## 为什么模型可以生成 interpretation，却不能生成 source identity？

因为两者的 Truth 层级不同。

例如真实 Evidence：

```text
DIFF-001
source_ref = commit abc/file.py
```

模型可以解释：

> 这里修改了重试逻辑，可能导致 recovery 场景状态不一致。

这是：

```text
Inference
```

但模型不能说：

> 证据来自 ticket 9381。

除非 `ticket 9381` 真的在 Context 里。

因此：

```text
Source identity
→ Context Authority

Interpretation
→ Model
```

这个边界非常适合面试追问。

------

## 为什么 RiskItem 至少必须有一个 Evidence？

因为 Stage8 Risk Agent 的业务目标不是：

> 帮我脑暴一些风险。

而是：

> 根据当前 Feature 资料分析风险。

所以：

```text
Risk
without Evidence
```

在本项目中就是无效业务输出。

这里通过 Schema / semantic validation 强制，而不是只写在 Prompt 里。

------

## 为什么 risk_id 必须唯一？

因为后面的 TestPlan 使用：

```text
covered_risk_ids
```

引用 Risk。

如果：

```text
RISK-001
RISK-001
```

对应两个不同风险，那么：

```text
covered_risk_ids=["RISK-001"]
```

到底覆盖哪个？

无法判断。

因此 WP1 最终增加了重复 `risk_id` 拒绝逻辑。

------

## 为什么 Test Planning 必须显式绑定 Risk ID？

因为这才能证明：

```text
Feature
→ Risk
→ Test Scenario
```

是真链路。

否则可能只是：

```text
Risk Agent 输出一份结果

Test Planning Agent 完全不看它
→ 根据 Feature 再生成另一份结果
```

UI 看起来 Agent 很多，但实际上多个 Agent 之间没有业务数据依赖。

最终实现要求：

```text
TestScenario.covered_risk_ids
```

只能引用当前 `RiskAnalysisResult` 中真实存在的 Risk。

------

## 为什么不强制每一个 Risk 都必须被 TestPlan 覆盖？

因为：

```text
Risk detected
```

不一定代表：

```text
must automatically create a test
```

例如某些 Risk：

- 当前环境无法验证；
- 需要专项设备；
- 需要人工判断；
- 当前版本明确不支持。

所以当前只保证：

> Scenario 不能引用不存在的 Risk。

而不是造一个复杂的自动 Coverage Policy Engine。

------

## 为什么 TestPlan 必须持久化，而 Risk 暂时可以不持久化历史？

因为当前真正需要进入人工 Review 的 Subject 是：

```text
TestPlan
```

Review 必须稳定回答：

> 人到底批准的是哪一版 TestPlan？

所以至少 TestPlan 需要：

```text
subject_id
version
payload
digest
```

而 Feature Understanding / Risk Analysis 当前主要作为生成 TestPlan 的中间推理结果。

因此本阶段允许：

```text
Feature Understanding history = not durable
Risk history = not durable
```

这是当前明确接受的 P1。

------

## 为什么 Digest 不能直接 hash `str(dict)`？

因为：

```python
str({"a": 1, "b": 2})
```

这种表示不是一个应该依赖的稳定业务序列化 Contract。

同样的结构，如果序列化顺序等变化，就可能产生不同结果。

因此先：

```text
Canonical JSON
```

例如稳定 key 顺序、compact separators、UTF-8，

然后：

```text
SHA-256
```

最终 WP1 就是这样实现的。

这里不要在面试时称为什么“高级密码学不可变绑定”。

就说：

> 用规范化 JSON 算内容摘要，确保 Review 绑定的是具体 TestPlan 内容。

足够。

------

## 为什么 Review Binding 要使用数据库返回的 TestPlan，而不是刚生成的内存对象？

因为数据库中的对象才是 Durable Truth。

错误：

```text
LLM generates TestPlan
→ memory version=1/digest=x
→ create Review
→ database save
```

如果 persistence 对数据进行了变化，或者 save 失败，就可能出现：

```text
Review binding
!=
Durable TestPlan
```

WP1 修复后是：

```text
persist TestPlan
→ read/use persisted row version + digest
→ create Business Review
```

最终 PostgreSQL 集成测试也重新计算了 digest，并验证 DB TestPlan 与 PENDING Review 完全匹配。

------

## 独立 Agent API 和 Workflow 为什么必须共用实现？

因为业务上既希望：

```text
测试人员单独调用 Risk Analysis
```

也希望：

```text
Mission
→ Feature Understanding
→ Risk
→ Test Planning
```

如果分别实现：

```text
/api/risk
→ implementation A
```

和：

```text
workflow
→ implementation B
```

以后 Prompt、Schema、Repair、Evidence Validation 很快就会分叉。

所以都是：

```text
HTTP / Workflow
        ↓
SpecialistAgentApplicationService
```

Sol 已确认独立 HTTP API 与 Mission planning workflow 共用同一个 Application Service、Prompt、Parser、Validator 和 Repair 实现。

------

# 4. 30 秒项目回答

> 在测试业务里我没有直接让 LLM 自由输出 Risk 和 Test Plan，而是在现有 AgentCore Runtime 上增加了一层 Typed Specialist Agent。Feature Understanding、Risk Analysis 和 Test Planning 都走统一 Runtime，但输出经过严格 JSON 和 Pydantic 校验，失败最多 repair 一次。Risk 必须引用 FeatureContext 中真实存在的 Evidence，模型只能解释证据，不能自己创造 source identity。然后 Test Scenario 再通过 `covered_risk_ids` 绑定真实 Risk。最终 TestPlan 持久化到 PostgreSQL，计算稳定 version 和 digest，再复用上一阶段的 Business Review 做人工审核。

------

# 5. 2 分钟项目回答

> Stage8 的第二步是把 LLM 推理真正变成可进入测试业务流程的结构化结果。
>
> 我做了三个 Specialist Agent：Feature Understanding、Risk Analysis 和 Test Planning，但是没有重做 Agent Framework，它们都注册到原来的 Agent Registry，然后通过 `CoordinatedRuntimeFactory`、AgentRouter 和 ModelInvocationRouter 执行，业务层只是增加 Typed Contract 和 Result Validation。
>
> 模型输出不能依赖 Provider 原生 Structured Output，所以采用 JSON 加 Pydantic 的本地严格校验。如果第一次输出结构或者业务语义不合法，只允许 repair 一次，第二次再失败就直接返回错误，避免形成无限 Agent Loop。
>
> Risk Analysis 这里我重点做了 Evidence Boundary。最开始实现里其实存在一个问题：模型可以自己返回任意 Evidence source，也就是说它能自己生成结论，再自己编一个证据来支持这个结论。Review 时把这个问题发现了，所以后来改成由 FeatureContext 建立 authoritative evidence map，模型只允许返回已有的 evidence ID 和自己的 interpretation，source identity 最终由系统重新恢复。这样 Evidence 的事实来自 Context，模型只负责推理。
>
> 然后 Test Planning 不是重新基于 Feature 自由生成，而是必须消费 RiskAnalysisResult，每个 Scenario 的 `covered_risk_ids` 只能引用真实 Risk，从结构上保证 Feature → Risk → Scenario 这条链成立。
>
> 最后 TestPlan 会作为 durable subject 存进 PostgreSQL，通过 canonical JSON 计算 SHA-256 digest。Business Review 使用数据库中真实 TestPlan 的 version 和 digest 做绑定，所以测试人员审核的是一份明确版本的 Test Plan，而不是一段临时模型输出。

------

# 6. 高频追问 + 简答

## 你们用了真正的 Multi-Agent 吗？

用了现有 Agent Runtime 和 Registry 中的多个 Specialist Agent，但这一阶段没有为了展示 Multi-Agent 强行让 Agent 相互自由 delegation。

当前更多是：

```text
Application Workflow
→ Feature Agent Run
→ Risk Agent Run
→ Planning Agent Run
```

这么做更可控，也更符合测试业务固定流程。

------

## Specialist Agent 和普通 Agent 有什么区别？

底层 Runtime 没区别。

区别在业务层：

```text
stable capability
+
Typed Request
+
Typed Result
+
business validator
```

例如 Risk Agent 不能只返回任意文本。

------

## 为什么不直接 Function Calling 返回 RiskResult？

Function Calling 更适合：

```text
模型选择并调用 Tool
```

这里 RiskResult 是：

```text
模型最终业务推理结果
```

虽然理论上也可以通过 structured generation/tool-like schema 实现，但当前 Provider 不统一支持，所以采用 JSON + Pydantic 更简单。

------

## JSON 格式正确是不是就代表结果正确？

不是。

我们有两层：

```text
Syntactic Validation
```

例如：

```text
字段存在
类型正确
confidence 是 float
```

以及：

```text
Semantic Validation
```

例如：

```text
Evidence ID 是否真实存在
risk_id 是否重复
covered_risk_ids 是否引用真实 Risk
feature binding 是否一致
```

这是 WP1 一个重要点。

------

## Pydantic 能校验 Evidence 是不是真的存在吗？

Pydantic 可以做部分本地 validator。

但：

```text
Evidence 是否属于本次 FeatureContext
```

需要拿当前请求 Context 中建立的 Evidence Map 做语义校验。

所以不能只靠 Schema。

------

## Evidence 和 RAG Citation 是一回事吗？

不是完全相同。

RAG Citation 是 Evidence 的一种来源。

Evidence 还可能来自：

```text
Feature Document
Code Diff
Meeting Summary
Developer Note
```

WP1 统一用业务 `EvidenceRef` 表达。

------

## RAG 为什么这一阶段还没完全接进去？

因为现在的核心目标是先证明：

```text
Evidence Authority
+
Risk-driven flow
```

RAG evidence 当前可以通过 request 注入。

真实历史 Ticket / CI Failure ingestion 属于后续业务数据接入，不值得阻塞 WP1。这是明确的 Accepted P1。

------

## TestPlan 为什么用 JSONB？

当前目标是：

```text
bounded structured business artifact
```

不是建设通用 Test Management Platform。

Scenario、Coverage 等结构未来还可能变化。

使用 JSONB：

- 开发快；
- 保持完整 Typed Payload；
- 减少当前阶段大量子表；
- 足够支持 version/digest/review。

------

## TestPlan Version 现在怎么管理？

当前新 TestPlan Subject 从：

```text
version = 1
```

开始。

WP1 还没有做复杂 TestPlan 修改历史。

当前主要目的是让 Review 有一个稳定可绑定的 Subject。

------

## Mission 怎么知道这几个 Agent Run 属于自己？

WP0 已经有：

```text
MissionRunReference
```

WP1 最开始 Luna 以为拿不到 Runtime run_id。

Sol 后来发现已有公开：

```text
scope.run_id
```

所以现在 production Runtime 会自动记录 Mission ↔ Specialist Run Reference，而且没有修改 Runtime Owner Contract。

------

## 为什么 Feature Understanding 和 Risk 没有持久化？

这是当前范围取舍。

它们目前是生成 TestPlan 的中间推理结果，而真正需要人工审核和跨阶段稳定引用的是：

```text
TestPlan
```

如果后面需要：

```text
审计 Risk 历史
对比 Risk 版本
质量评测
```

再增加 durable history。

当前不为了完整提前建表。

------

## 这种多步 Workflow 中间失败怎么办？

当前每一步是 bounded Run。

如果 Risk 失败：

```text
不进入 Test Planning
```

如果 TestPlan 失败：

```text
不创建 Review
```

当前 TestPlan Save、Review Create、Mission transition 之间还不是一个整体原子事务，这是当前 Accepted P1。

------

## 为什么不立刻修跨事务一致性？

因为当前是内部 Demo / 面试闭环。

最坏情况下可能出现：

```text
TestPlan saved
Review not created
```

它是可检测、可修复的中间状态。

如果现在为了这个问题引入：

```text
Saga
Workflow Engine
Distributed Transaction
复杂 Compensation Framework
```

成本明显大于收益。

------

# 7. Bad Case

## Real Bad Case 1 — Fake Evidence

这是 WP1 最重要的真实 Bad Case。

Luna 初版允许模型直接返回：

```json
{
  "evidence": [
    {
      "source_type": "HISTORICAL_TICKET",
      "source_ref": "BUG-9381"
    }
  ]
}
```

但系统没有确认：

```text
BUG-9381
```

真的存在于当前 FeatureContext。

这意味着：

```text
LLM generates risk
+
LLM generates evidence supporting risk
```

“Evidence-driven”实际上名存实亡。

Sol 修复后：

```text
FeatureContext
→ Evidence Map
```

例如：

```text
E1 → Feature Document
E2 → Code Diff
E3 → Meeting Summary
```

模型只能输出：

```text
E2
```

系统再从 Map 恢复真实 source identity。

不存在：

```text
E999
```

则：

```text
Repair once
→ still invalid
→ fail
```

这是非常好的面试真实案例。

------

## Real Bad Case 2 — Specialist Agent ID 实际没注册

Luna 初版看起来已经有：

```text
feature-understanding
risk-analysis
test-planning
```

但实际 Specialist ID 使用方式不符合现有 Registry 约束，而且没有正确注册。

结果生产调用会在 `AgentRouter` 中退回：

```text
core_router
```

也就是说：

> API 名字看起来调用的是 Risk Agent，但实际 Runtime identity 不是 Risk Agent。

Sol 最终修改稳定 ID 并补齐 Registry / Adapter Factory registration。

这是另一个非常好的面试 Bad Case：

> **“代码存在”和“production reachable”不是一回事。**

------

## Real Bad Case 3 — HTTP Projection 把 Typed Result 变成 `{}`

实现 Typed Agent 后，内部 Pydantic Result 是正确的。

但 HTTP smoke 发现：

```text
_stage8_projection()
```

在投影部分 Pydantic 字段时，结果会变成：

```json
{}
```

所以：

```text
Domain correct
!=
Transport correct
```

最后补了 primitive / dict / model projection 逻辑。

这个案例适合回答：

> 为什么有 Unit Test 还需要最小 HTTP E2E？

------

## Hypothetical Bad Case — 无限 Structured Repair

假设：

```text
parse fail
→ retry
evidence fail
→ retry
coverage fail
→ retry
feature mismatch
→ retry
...
```

那么一次 Risk Analysis 请求就可能产生大量模型调用。

所以 Repair Budget 必须统一，而不是每个 Validator 自己重试一次。

当前真实实现是：

```text
Initial + at most one repair
```

这是设计边界，不是本阶段真实线上事故。

------

# 8. Truth / Owner / Completion Boundary

## Model Invocation Truth

Owner 仍然是：

```text
AgentCore Runtime
→ AgentRouter
→ ModelInvocationRouter
```

Stage8 Specialist 不直接调用 Provider。

Sol Final Gate 已确认这一点。

------

## Specialist Business Contract Owner

```text
Stage8 SpecialistAgentApplicationService
```

拥有：

```text
Typed request
Prompt selection
Structured parsing
Business semantic validation
Bounded repair
Typed result
```

它不是模型底座 Owner。

------

## Evidence Truth

真实 source identity Owner：

```text
FeatureContext / request-injected context
```

LLM 只拥有：

```text
interpretation
risk hypothesis
confidence
```

不拥有：

```text
evidence existence
source_ref truth
```

Final Gate 明确记录：

```ini
EVIDENCE_AUTHORITY = FEATURE_CONTEXT_OWNED
FAKE_EVIDENCE_REJECTION = YES
```



------

## Risk Truth

这里要稍微准确表达。

Risk 本身并不是客观外部事实，而是：

```text
AI-generated business analysis
```

系统 Authority 只保证：

```text
这个 RiskResult 是系统真实生成和验证过的结果
```

并不代表：

> 这个 Risk 一定会发生。

`confidence` 也是推理元数据，不是生产 Safety Authority。

------

## TestPlan Truth

持久化：

```text
stage8_test_plans
```

当前关键属性：

```text
mission_id
subject_id
version
payload
digest
```

Final Gate 明确确认：

```ini
TEST_PLAN_PERSISTENCE = POSTGRESQL_JSONB
TEST_PLAN_VERSION = NEW_SUBJECT_STARTS_AT_1
TEST_PLAN_DIGEST = CANONICAL_JSON_SHA256
TEST_PLAN_MISSION_BINDING = YES
```



------

## Business Review Truth

继续由 WP0：

```text
BusinessReviewService
stage8_business_reviews
```

持有。

WP1 只负责：

```text
产生 durable TestPlan
→ 提供 version/digest
→ 创建 Review
```

没有增加第二套 TestPlan Approval。

------

## Mission Truth

继续由：

```text
FeatureTestMission
MissionService
```

持有。

WP1 现在可以：

```text
attach Specialist Run Reference
```

并推进：

```text
CREATED
→ CONTEXT_READY
→ AWAITING_REVIEW
```

但 Specialist Run 仍然不属于 Mission Service 管理生命周期。

------

## RAG Truth

当前：

```text
RAG_BOUNDARY = REQUEST_INJECTED_EVIDENCE_ONLY
```

还没有：

```text
Stage8 historical ticket ingestion
Stage8 CI indexing
live business RAG
```



所以面试不能说：

> Stage8 已经自动从所有历史 Ticket 中检索风险。

现在可以说：

> 底层 Hybrid RAG 已存在，WP1 已经把 RAG Evidence Contract 接进业务层，但真实 Stage8 业务数据 ingestion 暂未完成。

------

## WP1 真正完成

已真实实现：

```text
Feature Understanding Specialist

Risk Analysis Specialist
→ Evidence required
→ Evidence authority validation
→ confidence validation
→ duplicate risk ID rejection

Test Planning Specialist
→ real Risk input
→ covered_risk_ids validation

Strict JSON + Pydantic
Initial + at most one repair

Existing Runtime / Registry integration

3 independent typed Agent APIs
1 Mission planning workflow

Mission ↔ Specialist Run reference

PostgreSQL TestPlan
version
canonical digest

Business Review binding
```

Final Gate 中对应全部 PASS。

------

## WP1 没有完成

当前明确没有：

```text
Feature Understanding durable history
Risk Analysis durable history

真实 Stage8 RAG ingestion

真实 Code Platform
Meeting Platform
Case Platform
Executor Platform

Case Engineering
Remote Execution
Failure Triage
CI Guardian
```

另外当前：

```text
TestPlan save
BusinessReview create
Mission transition
```

仍是多个事务。

极端 DB Failure 下可能出现：

```text
TestPlan 已保存
但 Review 没创建
```

这是当前 3 个 Accepted P1 中最有工程讨论价值的一个。

------

# WP1 最应该记住的四句话

第一句：

> **LLM 可以负责推理，但不能自己成为 Evidence Authority。**

第二句：

> **Risk-driven Testing 不是 Prompt 里写“根据风险生成测试”，而是通过 Risk ID 和 Scenario Coverage 在 Contract 上建立真实数据依赖。**

第三句：

> **Structured Output 不只是 JSON Parse，还需要业务语义校验，并且 Repair 必须有明确预算。**

第四句：

> **Specialist Agent 是现有 AgentCore Runtime 上的 Typed Business Facade，不是另一套 Agent Framework。**

这四句话基本覆盖了 WP1 最有面试价值的内容。