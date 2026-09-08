# LocalAgent + AgentEvalOps 全项目面试叙事

推荐文件名：

```text
docs/interview/localagent_agentevalops_project_narrative.md
```

------

# 一、先用一句话定义整个项目

> **我做的是一套面向复杂知识与工具执行场景的 Agent 工程系统：LocalAgent 负责真实 Agent Runtime、RAG、Memory、Tool、HITL 和 MCP 执行，AgentEvalOps 负责对这些能力产生的真实 Execution Evidence 做 Dataset、Evaluation、Regression 和 Release Gate；整个项目的演进核心不是不断堆 Agent Feature，而是逐步解决 Runtime Ownership、Side-effect Safety、Production Boundary 和 Evaluation-Driven Optimization。**

如果进一步压缩：

```text
LocalAgent
= 怎么可靠地运行 Agent

AgentEvalOps
= 怎么证明 Agent 的改动到底变好了还是变差了
```

最终两个系统之间形成：

```text
Runtime
→ Evidence
→ Evaluation
→ Regression
→ Release Decision
→ 再优化 Runtime
```

这是整个项目最核心的闭环。

------

# 二、项目背景怎么讲

LocalAgent 最初是一个面向复杂知识查询、数据分析和工具执行场景的 Agent 工程原型。

原始能力已经包括一些典型 AI 应用组件，例如：

```text
LLM
RAG
Memory
Tool
Router
Planner
Multi-Agent
FastAPI
```

但随着能力增加，我发现真正困难的问题已经不是：

> 怎么调用一次 LLM？

而变成：

```text
一次 Agent Run 到底谁拥有状态？

多个 Agent 谁能执行、谁能输出？

Tool 执行一半网络断了，到底有没有产生副作用？

Timeout 和 Cancellation 谁负责？

模型能不能自己决定 Tool Risk？

Memory 谁能读？

RAG 优化后到底是真的变好，还是只在几个 Case 上感觉更好？

线上失败怎么转成 Regression Case？

MCP Server 接进来以后，是否能绕开原来的 Tool Governance？
```

所以项目后面的演进逐渐从：

```text
AI Application
```

转向：

```text
Agent Runtime Engineering
+
Evaluation Engineering
+
AI Safety / Governance
+
Production Awareness
```

------

# 三、整个项目的演进主线

可以把整个项目记成六次升级。

```text
原型期
“Agent 能跑”
        ↓

Stage2
“Agent 能被一个明确 Runtime 可靠地管理”
        ↓

Stage2.5
“真正的 Multi-Agent 也进入统一 Runtime”
        ↓

Stage3 / 3.5
“Runtime 具备最小生产运行边界，并冻结核心 Contract”
        ↓

Stage4
“建立独立 Evaluation / Regression / Release Gate 平台”
        ↓

Stage5
“用 Evaluation 反过来驱动 RAG、Memory、Security、Tool、HITL、MCP 演进”
```

这就是面试最应该讲的主故事。

------

# 四、第一阶段故事：从“能调用 Agent”到“有 Agent Runtime”

## Stage2 — Agent Runtime

Stage2 最重要的变化不是增加 Agent 数量，而是：

> **把原来职责混杂的 Agent 调用链重构成一个有明确 Owner、状态机、失败语义、资源生命周期和可恢复边界的协调式运行时(Coordinated Runtime)。**

Stage2 最终形成：

```text
RunContext
AgentState
AgentStateMachine
Plan
Scheduler
RunCoordinator

Budget
Deadline
Cancellation

Model Retry
Model Fallback
Circuit Breaker

Tool Runtime
Retrieval Runtime

RuntimeEvent
Journal
Trace
Snapshot
Recovery Validation
Graceful Shutdown
Fault Injection
```

Stage2 的核心定义就是：Agent Runtime 不是调用 LLM，而是管理一次 Agent Execution 从开始到结束的状态、资源、副作用和事实边界。

------

# 五、Stage2 最重要的系统设计思想：一个事实只能有一个 Owner

这是整个项目后来反复出现的思想。

例如：

```text
Runtime Mutable State
→ AgentState

Run Terminal
→ RunCoordinator

Model Retry
→ RetryExecutor

Candidate Fallback
→ ModelInvocationRouter

Tool Side-effect Truth
→ AttemptSideEffectTracker

Recovery Decision
→ RecoveryValidator
```

为什么一定要这样？

因为如果两个组件都能写同一个 Fact：

```text
Plan says RUNNING
AgentState says SUCCEEDED
```

那后面的：

```text
Retry
Recovery
Trace
Shutdown
```

都会出现不同答案。

所以：

> **复杂系统设计的第一步不是拆 Service，而是先确定 Authority 和 Truth Owner。**

Stage2 正式把这套 Owner 思维建立起来。

------

# 六、Stage2 第二个核心：副作用不能被“猜”

Tool Runtime 让我第一次真正碰到分布式系统里的不确定结果问题。

例如：

```text
发送 create_issue 请求
        ↓
远端已经收到
        ↓
连接断开
        ↓
本地没有成功 Response
```

这时候不能说：

```text
NOT_STARTED
```

因为 Provider 可能已经执行。

只能说：

```text
UNKNOWN
```

所以 Tool Side Effect 被显式建模：

```text
NOT_STARTED
STARTED
COMMITTED
UNKNOWN
COMPENSATED
```

核心原则：

> **UNKNOWN ≠ NOT_STARTED。**

对于非幂等操作，如果状态已经是：

```text
COMMITTED
或
UNKNOWN
```

就不能简单自动 Retry。

Stage2 也因此没有宣称系统级 Exactly-once。

------

# 七、为什么 Journal-first 是整个 Runtime 的重要基础

最终事件链：

```text
Runtime Event
     ↓
Journal
     ↓
Observability
     ↓
Channel
     ↓
Client
```

而不是：

```text
先推给 Client
→ 再记录
```

这样可以区分：

```text
业务事实已经发生
```

和：

```text
用户是否成功看到
```

例如：

```text
Tool 已执行
Journal 已持久化
Client Channel 失败
```

不能因为 Client 没收到，就重新执行 Tool。

这其实建立了整个项目后来非常常见的一条原则：

> **业务事实(Execution Truth)与交付事实(Delivery Truth)必须分开。**

------

# 八、Recovery 为什么没有直接做自动 Resume

这也是面试很值得讲的地方。

项目已经有：

```text
Snapshot
Journal
```

但没有因此说：

> “已经支持 Durable Execution。”

因为真实执行中还有：

```text
Tool Side Effect
StepResult
Invocation Binding
Output Delivery
```

不是全部 Durable。

所以当前：

```text
Recovery
= Validation Only
```

RecoveryValidator 可以回答：

```text
Snapshot 是否有效？
Journal 是否连续？
是否存在 side-effect gap？
是否需要 reconciliation？
```

但不能：

```text
重新调用 Model
重新执行 Tool
重新发送 Final Answer
自动 Resume
```

这个选择体现的是：

> **不知道怎样安全恢复时，Fail Closed 比伪装成支持 Durable Resume 更正确。**

------

# 九、第二次升级：真正把 Multi-Agent 纳入 Runtime

## Stage2.5 — Multi-Agent Runtime

Stage2 做完后出现了一个真实架构问题：

> Coordinated Runtime 已经成为默认入口，但原来的 Multi-Agent 编排没有完整迁移，导致系统虽然有很多 Agent，真实请求仍可能一直是 `core_router` 自己执行。

所以 Stage2.5 不是：

```text
再增加几个 Agent Class
```

而是建立：

```text
User Request
     ↓
PlanResolver
     ↓
PlanCompiler
     ↓
Frozen Plan
     ↓
Scheduler
     ↓
Specialist Agents
     ↓
StepResultStore
     ↓
Synthesis
     ↓
OutputGate
     ↓
Final Output
```

Stage2.5 最终 54/54 必选 RC 场景通过。

------

# 十、Planner 为什么不能直接生成一个随便执行的 DAG

如果让 LLM Planner 输出：

```text
Agent
Dependencies
Retry Policy
Runtime State
Callable
Output Policy
```

然后 Runtime 直接执行，那么实际上：

> **LLM 已经变成 Runtime Authority。**

所以最终变成：

```text
Planner
→ Typed Decision

PlanCompiler
→ Validate AgentRegistry
→ Validate Capability
→ Compile Legal Shape
```

当前只允许有限拓扑。

Planner 负责：

```text
“我认为应该怎么做”
```

Runtime Compiler 负责：

```text
“系统允许怎么做”
```

这就是：

> **模型决策(Model Decision)和执行权威(Runtime Authority)分离。**

------

# 十一、Multi-Agent 的难点其实不是并行，而是信息流

多个 Specialist 的结果没有直接字符串拼接：

```text
Agent A Output
Agent B Output
Agent C Output
```

而是：

```text
Specialist
→ Typed StepResult
→ StepResultStore
→ Dependency-scoped View
→ Synthesis
```

`StepResultStore` 不只是 `dict`。

它具备：

```text
once-write
producer validation
size limit
lifecycle
dependency ACL
late-write rejection
```

如果 Synthesis 只依赖 A、B：

```text
A
B
```

它就不能顺便读取 C、D。

这相当于在 Agent Runtime 中做了一层最小：

> **信息流控制(Information Flow Control)。**

------

# 十二、Multi-Agent 为什么需要 OutputGate

多个 Specialist 都可能成功：

```text
knowledge_expert
code_expert
data_analyst
synthesis
```

但：

```text
Step Success
≠
可以向用户发送 Final Answer
```

所以引入：

```text
OutputGate
```

成为 Run 级唯一 Final Publication Owner。

```text
NOT_STARTED
    ↓
PUBLISHING
    ↓
PUBLISHED
FAILED
OUTCOME_UNKNOWN
```

只允许一次 Publish Attempt。

这样避免：

```text
Specialist A 发一次
Specialist B 发一次
Synthesis 又发一次
```

最终只有唯一 Final Source。

------

# 十三、一个很好的真实问题：HistoryPolicy

当时已经设置：

```text
persist=False
```

大家一开始容易以为 Specialist 已经不会访问旧 Memory。

但源码审计发现：

```text
persist=False
```

只控制：

```text
写历史
```

并不控制：

```text
读历史
```

所以 delegated Specialist 仍可能读到旧 Run 的 Agent History。

最终拆成：

```text
HistoryPolicy
= 是否读取

persist
= 是否写入
```

这给我的一个很重要的工程认识是：

> **两个正交的权限维度，不应该偷懒塞进一个 Boolean。**

这是 Stage2.5 非常典型的源码审计 Bad Case。

------

# 十四、第三次升级：从 Runtime Correctness 到最小生产化

## Stage3 — 最小必要生产化(Minimal Necessary Productionization)

Stage2/2.5 已经解决：

```text
Runtime 是否正确执行
```

Stage3 开始解决：

```text
这个 Runtime 能不能被正确启动？
配置错误能不能提前发现？
Tool 权限谁拥有？
安全边界在哪？
Trace 能不能输出到外部系统？
外部监控挂了会不会拖垮主 Runtime？
系统能不能有界关闭？
```

Stage3 最终定义非常准确：

> 从“功能正确的工程原型”，推进到“具备最小生产运行边界的系统”。

不是：

```text
完整企业生产平台
```

Stage3 最终 Gate 为 PASS，但明确：

```text
Production proven = NO
```

------

# 十五、Stage3 第一条主线：Composition Root 和生命周期

Stage3 把：

```text
Settings
Validation
Persistence Preflight
Runtime Services
Shutdown
```

收进唯一生产 Composition Root：

```text
server.py::lifespan()
```

启动过程变成：

```text
Process Start
    ↓
Load Settings
    ↓
Validate Config
    ↓
Persistence Preflight
    ↓
Construct Services
    ↓
READY
```

非法配置：

```text
→ FAIL CLOSED
→ never READY
```

核心思想：

> **能在 Startup 阶段确定的错误，不应该拖到真实用户 Request 中才爆炸。**

------

# 十六、Stage3 第二条主线：Tool Platformization

原来的危险方向：

```text
Model
→ Tool
→ Execute
```

Stage3 将它拆成：

```text
Model proposes
      ↓
ToolRegistry
      ↓
ToolGovernanceService
      ↓
ResourceAuthorizationService
      ↓
ToolExecutionService
```

几个 Owner 明确分开：

```text
ToolRegistry
= identity / discovery

ToolGovernanceService
= risk / permission / approval policy

ResourceAuthorizationService
= path / resource authorization

ToolExecutionService
= actual execution
```

模型不能因为生成：

```json
{"approved": true}
```

就自动获得安全授权。

这为后面的 HITL 和 MCP 奠定了核心 Safety Boundary。

------

# 十七、Prompt Injection 的处理为什么值得讲

Stage3 没有宣称：

```text
“我彻底解决了 Prompt Injection”
```

而是先解决一个更工程化的问题：

> **即使模型受到恶意文本影响，不可信数据也不能因此获得确定性的 Runtime Authority。**

所以：

```text
RAG Content
Tool Result
Memory
History
```

可以影响模型理解，

但不能直接决定：

```text
Tool Permission
Approval
Resource Authorization
```

因此 Prompt Injection 的准确能力一直是：

```text
PARTIALLY_SUPPORTED
```

而不是 Fully Solved。

------

# 十八、Stage3 第三条主线：真实跨系统可观测链路

Stage3 把：

```text
Local Runtime Trace
```

真正导出到：

```text
LocalAgent
→ TraceExportEnvelope
→ PycURL
→ AgentEvalOps
→ PostgreSQL
```

并验证：

```text
首次写入
→ 201 PERSISTED

完全相同 Replay
→ 200 DUPLICATE_ACCEPTED

相同 Identity + 不同语义
→ 409 CONFLICT
```

但 Trace Delivery 仍是：

```text
BEST_EFFORT
+
AT_MOST_ONE_TRANSPORT_ATTEMPT
```

不是 Exactly-once。

Stage3 最终完成真实双系统 E2E，但仍明确不宣称 Production Proven。

------

# 十九、Stage3.5：为什么开发到这里要冻结 Contract

Stage3 做完以后继续开发 RAG、Memory、Tool、Evaluation 时，会面临一个问题：

> 后续每加一个 Feature，会不会重新破坏 Runtime Owner？

所以 Stage3.5 没继续堆功能，而是把已经证明成立的核心语义冻结成：

```text
FROZEN_BASELINE_V1
```

包括：

```text
RunContext
AgentState
Plan
RunCoordinator

ToolRegistry
ToolGovernance
ResourceAuthorization
ToolExecutionService

Journal-first
Recovery Validation-only
OutputGate
DELIVERED-only Final Memory

Trace Contract
Trace Delivery Semantics
```

后面 Stage4、Stage5 的改动都应该在这些 Owner Boundary 上继续演进，而不是重新发明第二套 Runtime。

这一步对我的项目很重要，因为它把：

```text
“当前实现方式”
```

和：

```text
“后续不能随意破坏的 Contract”
```

分开。

------

# 二十、第四次升级：从 Observability 到真正的 Evaluation Platform

## Stage4 — AgentEvalOps

Stage3 已经把 LocalAgent Trace 发给 AgentEvalOps。

但：

```text
有 Trace
≠
有 Evaluation
```

PandaProbe 原本更偏：

```text
Trace
Score
Monitoring
Analytics
```

Stage4 真正做的是：

> **把 Trace 从 Evaluation Truth 中解耦，建立一个独立 Evaluation Domain。**

最终主链：

```text
Trace / Span
    ↓
Online Normalization
    ↓
TraceEvidenceCandidate
    ↓
Explicit Feedback
    ↓
DatasetVersion / TestCaseVersion
    ↓
EvaluationRun
    ↓
ExecutionAttempt
    ↓
EvaluationResult
    ↓
Baseline / Candidate
    ↓
RegressionReport
    ↓
ReleaseDecision
    ↓
CI Adapter
```

Stage4 最终完整冻结在推荐最小范围内。

------

# 二十一、Stage4 最核心的一句话

> **Trace ≠ EvaluationResult。**

Trace 回答：

```text
真实 Runtime 发生了什么？
```

EvaluationResult 回答：

```text
在特定 Dataset、
Case Version、
Evaluator Version、
Candidate Version
下，
这个行为质量怎么样？
```

所以：

```text
Trace
= Observation / Evidence

EvaluationResult
= Evaluation Truth
```

这也是整个 AgentEvalOps 最重要的 Owner Boundary。

------

# 二十二、Evaluation Runtime 为什么也需要 Run / Attempt / Result

Evaluation 看似只是：

```text
for case in dataset:
    score(case)
```

但真实系统需要处理：

```text
Retry
Worker Crash
Concurrency
Timeout
Stale Worker
Result Finalization
```

所以 Stage4 建立：

```text
EvaluationRun
ExecutionAttempt
EvaluationResult
```

其中：

```text
Run
= 一次评估批次

Attempt
= 一个 Case 的一次执行事实

Result
= 最终 Evaluation Fact
```

Result 采用：

```text
Append-only
```

Retry 不 Reset 原 Attempt，而是：

```text
Attempt B
retry_of = Attempt A
```

这样历史才可信。

------

# 二十三、CAS 和 Fencing 是 Stage4 最值得讲的后端能力

多个 Worker 可能同时看到：

```text
Attempt = PENDING
```

最终由数据库 CAS：

```text
UPDATE ...
WHERE status = PENDING
```

决定唯一 Claim Winner。

但 CAS 只解决：

```text
谁先获得执行权
```

还需要 Fencing Token 解决：

```text
Worker A 获得 Claim
→ A 卡死
→ Worker B 接管
→ A 后来恢复
```

A 必须不能继续写 Result。

所以每次写入必须验证：

```text
caller_claim_token
==
current_claim_token
```

这就是：

> **CAS 解决竞争，Fencing 解决 stale owner。**

------

# 二十四、为什么 Production Trace 不能自动变 TestCase

假设一条线上 Trace 因为模型回答错误而进入 Failure Analysis。

如果系统自动：

```text
actual output
→ expected output
```

那就变成：

```text
错误答案
→ Golden Answer
```

所以 Stage4 明确加入 Feedback Boundary：

```text
Failing Trace
→ Evidence Candidate
→ Explicit Feedback
→ TestCaseVersion
→ New DatasetVersion
```

而：

```text
Sanitization
Expected Output
Criticality
Version
```

都需要明确 Authority。

这也是：

> **Observation 不能自动升级成 Ground Truth。**

------

# 二十五、Stage4 最终形成 Release Gate

单次 Evaluation 回答：

```text
Candidate 表现如何？
```

Regression 回答：

```text
Candidate 相比 Baseline 如何？
```

基本分类：

```text
PASS → FAIL
= REGRESSION

FAIL → PASS
= IMPROVEMENT

same
= UNCHANGED

missing / ERROR / INCONCLUSIVE
= NOT_COMPARABLE
```

尤其：

```text
NOT_COMPARABLE
≠
FAIL
```

因为：

> 没有足够证据不能自动转换成负面事实。

最后：

```text
Critical REGRESSION
→ BLOCK

Critical NOT_COMPARABLE
→ BLOCK
```

最终由 `RegressionReportService` 产生：

```text
ReleaseDecision
```

CI 只做 Adapter，不重新计算 Policy。

------

# 二十六、第五次升级：Evaluation 开始反向驱动 Agent 能力

## Stage5 — Evaluation-Driven Optimization

Stage4 结束时，Evaluation Platform 已经有了：

```text
Dataset
TestCase
Run
Attempt
Result
Regression
ReleaseDecision
```

但当时还缺：

```text
真实 LocalAgent ExecutionTarget
具体 RAG Evaluator
Memory Evaluation
Security Evaluation
真实 Agent Feature Optimization
```

Stage5 真正开始回答：

> **有了 Evaluation Platform 以后，怎么用它来指导真实 Agent 迭代？**

最终 Stage5 Source Audit 确认：

```text
AgentEvalOps
→ owns Dataset / GroundTruth / Evaluation / Regression

LocalAgent
→ owns Runtime / Retrieval / Memory / Tool / HITL / MCP
```

HTTP Response 和 Evaluation Artifact 只是跨系统 Evidence Boundary，不会把 Runtime State Owner 转给 AgentEvalOps。

------

# 二十七、Stage5 第一步：把真实 LocalAgent 接进 Evaluation

以前 AgentEvalOps 的 ExecutionTarget 主要是 Fixture。

Stage5 Phase0 增加：

```text
AgentEvalOps
→ LocalAgentHttpExecutionTarget
→ /api/runtime/execute
→ Coordinated Runtime
```

这里我没有直接复用：

```text
/api/chat
```

因为 Chat API 是面向 User Streaming 的。

Evaluation 需要：

```text
SUCCEEDED
FAILED
CANCELLED
TIMEOUT
```

这样的 Machine Terminal Fact。

所以：

> **面向人的 Streaming Protocol 和面向机器的 Execution Protocol 可以共享同一个 Runtime，但不应该强行共享同一个 Wire Contract。**

------

# 二十八、HTTP Ambiguous Outcome 再次成为关键设计

比如：

```text
HTTP request 可能已经被 LocalAgent 接收
→ Response 连接断开
```

AgentEvalOps 不知道：

```text
远端是否执行
```

所以：

```text
OUTCOME_UNKNOWN
```

并：

```text
NO AUTOMATIC RETRY
```

这个设计其实和 Stage2 Tool Side-effect UNKNOWN 是同一套工程思想：

> **系统不能把不知道伪装成没有发生。**

这说明整个项目从 Runtime 到跨系统 Evaluation，Failure Semantics 是一致的。

------

# 二十九、Stage5 RAG 的故事不能讲成“我加了 BM25 和 RRF”

真正的故事是：

> **我建立了一套 Evaluation-Driven RAG Optimization 方法。**

路线：

```text
Dense Baseline
    ↓
BM25
    ↓
Dense + BM25
    ↓
RRF
    ↓
Cross-Encoder
    ↓
No-Answer Threshold
    ↓
Context Selection
```

但每一步都要：

```text
Freeze Baseline
→ Change One Variable
→ Benchmark
→ Compare
→ Keep / Reject
```

不是：

```text
技术看起来高级
→ 就上线
```

------

# 三十、为什么 Dense + BM25 有价值

稠密检索(Dense Retrieval)擅长：

```text
语义
同义表达
自然语言
```

稀疏检索(Sparse Retrieval / BM25)擅长：

```text
错误码
类名
函数名
ID
精确术语
```

所以 Hybrid 的理由是：

> **检索互补性(Retrieval Complementarity)。**

而不是：

> Hybrid 比 Dense 听起来高级。

------

# 三十一、为什么使用 RRF

Dense 和 BM25 Score 不同量纲。

不能直接：

```text
DenseScore + BM25Score
```

所以使用倒数排名融合(RRF, Reciprocal Rank Fusion)：

```text
score(d)
=
Σ 1 / (k + rank_i(d))
```

融合 Rank，而不是直接融合异构 Score。

但实验结果也很重要：

```text
部分 Metric ↑
部分 Metric ↓
```

所以当时没有宣称：

```text
RRF 全面击败 Dense
```

------

# 三十二、Cross-Encoder 为什么有提升也没有上线

交叉编码器(Cross-Encoder)可以：

```text
Query + Document
→ Joint Encoding
→ Relevance Score
```

排序通常更准确。

真实实验中：

```text
Public Benchmark Ranking
→ improved
```

但：

```text
Domain Hard Guardrail
→ regressed
```

所以：

```text
Capability Proven
Candidate Rejected
```

这句话非常适合面试：

> **证明一个技术有效，不等于证明当前 Candidate 值得上线。**

------

# 三十三、一个 Negative Result 为什么反而很有价值

No-Answer Threshold 做了大量配置搜索。

最终：

```text
FEASIBLE_CONFIG_COUNT = 0
```

系统没有：

```text
删除 Hard Case
降低要求
偷改 Dataset
```

而是直接：

```text
REJECT_NO_FEASIBLE_POLICY
```

这体现了 Stage5 很重要的实验原则：

> **实验不是为了证明我的方案有效，而是为了判断它到底有没有效。**

------

# 三十四、RAG Productionization 最后的真实结果

Stage6 后：

```text
HYBRID_RRF
```

已经真正进入 LocalAgent Runtime，成为显式可配置的 Production-Reachable Strategy。

但最终：

```text
CURRENT_RAG_PRODUCTION_DEFAULT
= BASELINE

HYBRID_RRF_PRODUCTION_REACHABLE
= YES

HYBRID_RRF_DEFAULT
= NO

CROSS_ENCODER_PRODUCTION_REACHABLE
= NO
```

原因之一就是 Hybrid 虽然 Aggregate Metric 提升，但 Per-case Regression Gate 没满足。

所以不能把平均提升掩盖个别已有用户场景退化。

------

# 三十五、Stage5 Memory 的核心不是“加一个向量库”

Advanced Memory 最终做的是：

```text
Semantic Memory
Episodic Memory

RUN Episode
STEP Episode

Private Memory
Project Memory

Owner
Visibility
Scope
Requester
Authorization
Grant
Promotion
Lifecycle
Provenance
```

语义记忆(Semantic Memory)保存：

```text
事实
```

情景记忆(Episodic Memory)保存：

```text
经历
```

更重要的是：

> **Memory 成为了 Runtime Domain，而不是一个 Store。**

------

# 三十六、Memory 最重要的权限问题

一句必须背：

> **任务委派(Task Delegation)不等于记忆权限委派(Memory Permission Delegation)。**

比如：

```text
Entry Agent
→ delegate
→ Database Specialist
```

只说明：

```text
Specialist 可以执行这个 Step
```

不意味着：

```text
Specialist 可以读 Entry Agent 所有 Private Memory
```

所以：

```text
Owner
Visibility
Scope
Requester
```

必须分开。

最终源码审计仍确认这些边界成立。

------

# 三十七、Memory 为什么不能成为 Authorization Authority

如果 Memory 写：

```text
“Agent B 是管理员”
```

Runtime 不能因此给 B 权限。

否则：

```text
Untrusted Data
→ Authorization
```

就是权限提升。

因此：

```text
Memory
= Data

Trusted Runtime Grant
= Authorization Fact
```

这和 Prompt Injection、Tool、MCP 的 Safety Philosophy 是统一的。

------

# 三十八、Stage5 Security 的故事

Prompt Injection 最终不只停在：

```text
“写一个 Prompt 防攻击”
```

而是形成：

```text
Attack Dataset
→ Real Execution
→ Security Evidence
→ Deterministic Evaluator
→ LLM Judge
→ Regression
→ Security Release Gate
```

并区分：

### 直接提示词注入(direct prompt injection)

恶意指令直接来自 User。

### 间接提示词注入(indirect prompt injection)

恶意指令通过：

```text
RAG
Tool Result
External Document
Memory
```

进入上下文。

核心观点：

> **低信任数据不能因为进入 Context 就获得高权限 Instruction Authority。**

------

# 三十九、为什么安全不能只看 Final Answer

如果 Agent 最后说：

```text
“我拒绝执行。”
```

但中间已经：

```text
调用危险 Tool
删除文件
修改资源
```

最终答案看起来安全也没有意义。

所以 Security Evaluation 必须看：

```text
Tool Call
Runtime Event
Side Effect Evidence
Final Answer
```

而不仅是最后文本。

这也是 Agent Safety 和普通 Chatbot Safety 很重要的区别。

------

# 四十、Stage5 HITL：模型做错决定时，如何阻止副作用发生

高风险 Tool 最终进入：

```text
ToolInvocation
      ↓
ToolGovernanceService
      ↓
APPROVAL_REQUIRED
      ↓
ToolApprovalController
      ↓
WAITING_FOR_APPROVAL
      ↓
Human
   ┌──┴──┐
Approve Reject
   ↓      ↓
Claim   zero execution
   ↓
ToolExecutionService
```

这里一个特别重要的设计：

```text
APPROVED
≠
EXECUTION_CLAIMED
```

Approve 是：

```text
业务授权
```

Claim 是：

```text
Runtime 唯一执行资格
```

这样重复 Approve 才不会造成重复执行。

------

# 四十一、HITL 的 Exactly-once 要怎么说才准确

不能说：

> “我实现了分布式 Exactly-once。”

当前真实能力是：

```text
single-process
active Run
at-most-once execution claim
```

由：

```text
Approval Binding
CAS
Execution Claim
```

保证。

没有：

```text
distributed consensus
durable execution lease
restart recovery
multi-node claim
```

最终 Source Audit 对这个边界明确重新确认。

------

# 四十二、Stage5 Tool Runtime：用户不再自己做 Tool Router

早期 Tool 使用体验可能是：

```text
用户知道 Tool 名
用户知道 JSON Schema
用户知道参数 Enum
```

Stage8 最终变成：

```text
Natural-language Intent
        ↓
Model
        ↓
Tool Selection
        ↓
Argument Proposal
        ↓
ToolRegistry
        ↓
ToolAdapter.build_invocation()
        ↓
Typed Validation
        ↓
Immutable ToolInvocation
        ↓
ToolAdapter.spec_for()
        ↓
ToolGovernanceService
        ↓
ALLOW / DENY / APPROVAL_REQUIRED
        ↓
Claim
        ↓
ToolExecutionService
        ↓
Tool Result
        ↓
role=tool
        ↓
Final Answer
```

最终 Source Audit 确认这条生产链仍成立。

------

# 四十三、Function Calling 在我的系统里到底负责什么

DeepSeek Native Function Calling 负责：

```text
语义工具选择
+
参数提议
```

它不负责：

```text
Typed Validation
Risk
Authorization
Idempotency
Approval
Execution
```

所以：

> **函数调用(Function Calling)是意图表达协议(Intent Protocol)，不是安全协议(Security Protocol)。**

Model 可以提出 Action。

Runtime 决定 Action 能不能真正发生。

------

# 四十四、最后一步：MCP 为什么不是第二套 Tool Runtime

Phase9 最核心的 Architecture Decision：

> **模型上下文协议(MCP)只是外部工具提供协议(External Tool Provider Protocol)，不能重新制造第二套 Runtime。**

架构：

```text
External MCP Server
        ↓
MCP Client
        ↓
MCP-backed ToolAdapter
        ↓
Existing ToolRegistry
        ↓
Existing Validation
        ↓
Existing Governance
        ↓
Existing HITL
        ↓
Existing Claim
        ↓
Existing ToolExecutionService
```

最终当前源码仍保持这个结构。

------

# 四十五、为什么 MCP 是一个防腐层(Anti-Corruption Layer)问题

MCP 世界有：

```text
MCP Tool Name
MCP Schema
MCP annotations
CallToolResult
```

LocalAgent 世界有：

```text
ToolInvocation
ToolExecutionSpec
ToolPolicy
ToolOutput
```

所以 `McpBackedToolAdapter` 的职责就是：

```text
External Protocol Model
→
Internal Runtime Contract
```

而不是让 Runtime Core 到处出现 MCP 特判。

------

# 四十六、MCP Metadata 为什么不能决定安全

Provider 可以声明：

```text
readOnlyHint=true
idempotentHint=true
```

但它只是：

> **提供方声明(Provider Claim)。**

不能直接成为：

```text
Runtime Fact
```

真正 Risk / Approval Authority：

```text
Local ToolPolicy
+
ToolGovernanceService
```

因此：

> **Provider 可以描述能力，但 Provider 不能给自己授权。**

------

# 四十七、MCP Retry 为什么仍然属于 Runtime

假设：

```text
issue_write
→ timeout
```

MCP Client 不知道：

```text
GitHub 是否已经创建 Issue
```

如果 Client：

```text
reconnect
→ replay
```

可能造成：

```text
duplicate mutation
```

所以：

```text
MCP Client
→ no automatic replay

Runtime
→ owns Retry Policy
```

这再次回到 Stage2 就已经建立的：

> **UNKNOWN 不能降级成 NOT_STARTED。**

整个项目的 Failure Semantics 是贯通的。

------

# 四十八、整个项目最终的系统图

```text
                         User
                          │
                          ▼
                    LocalAgent API
                          │
                          ▼
                  Coordinated Runtime
                          │
             ┌────────────┼─────────────┐
             │            │             │
             ▼            ▼             ▼
          Planning       Memory         RAG
             │                          │
             ▼                          ▼
          Scheduler                 Retrieval
             │                          │
      ┌──────┼──────┐                   │
      ▼      ▼      ▼                   ▼
 Specialist Agents                 ContextBuilder
      │                                  │
      └──────────┐                       │
                 ▼                       │
             Synthesis                   │
                 │                       │
                 └──────────┬────────────┘
                            ▼
                           Model
                            │
                            ▼
                      Tool Selection
                            │
                            ▼
                       ToolRegistry
                            │
                            ▼
                        Validation
                            │
                            ▼
                        Governance
                            │
                    ┌───────┴───────┐
                    │               │
                  ALLOW           HITL
                    │               │
                    │          Approval/Claim
                    │               │
                    └───────┬───────┘
                            ▼
                   ToolExecutionService
                            │
               ┌────────────┴────────────┐
               │                         │
          Built-in Tool              MCP Adapter
                                         │
                                         ▼
                                    MCP Provider

                            │
                            ▼
                       OutputGate
                            │
                            ▼
                        Delivery
                            │
                    DELIVERED only
                            │
                            ▼
                         Memory


同时：

LocalAgent Runtime
       │
       ├── Journal
       ├── Trace
       ├── Retrieval Evidence
       ├── HITL Evidence
       │
       ▼
    AgentEvalOps
       │
       ▼
Dataset / GroundTruth
       │
       ▼
EvaluationRun / Attempt / Result
       │
       ▼
Baseline / Candidate
       │
       ▼
RegressionReport
       │
       ▼
ReleaseDecision
```

------

# 四十九、如果面试官问：“你这个项目最大的特点是什么？”

推荐回答：

> 我觉得最大的特点不是我用了多少 Agent Framework，而是整个项目后期一直围绕“谁拥有事实和执行权”设计。比如 Plan 是静态定义，AgentState 是动态状态 Owner；Model 可以选择 Tool，但 ToolGovernance 才决定 Risk；Human 可以 Approve，但 Runtime Claim 才能真正执行；Trace 是 Evidence，不是 Evaluation Truth；Evaluation 可以评价 Runtime，但不能修改 Runtime Terminal。
>
> 所以随着功能增加，我没有继续靠大量隐式 Callback 拼装，而是逐步把 Owner、Contract、Side-effect State 和 Evaluation Evidence 显式化。

------

# 五十、如果面试官问：“为什么自己做 Runtime，不直接全部用 LangChain？”

推荐回答：

> 我的目的不是重新做一个通用 Agent Framework，而是为了学习和解决项目里比较关键的 Runtime 问题，比如状态唯一事实源、Cancellation、Deadline、Tool Side-effect UNKNOWN、Journal-first、Multi-Agent dependency isolation、HITL Claim 和 Recovery Boundary。
>
> 这些问题即使使用 LangChain、LangGraph 之类的框架仍然存在，只是部分由框架内部实现。我的项目希望把这些 Runtime Contract 显式掌握。业务层当然可以使用框架，但我不会把框架本身当作系统设计答案。

------

# 五十一、如果面试官问：“为什么还单独做 AgentEvalOps？”

推荐回答：

> 因为 Runtime 可观测性和 Evaluation 是两个不同问题。Trace 只能告诉我发生了什么，但不能告诉我这个结果在一个固定 Dataset、Ground Truth 和 Evaluator 下到底好不好。
>
> 所以 AgentEvalOps 把 Trace 当 Evidence Source，独立拥有 Dataset、TestCase、Evaluation Run/Attempt/Result，再做 Baseline/Candidate Regression 和 Release Gate。后来 Stage5 又把 LocalAgent 真正接成 ExecutionTarget，这样每次 RAG、Memory 或 Tool 改动都可以用真实 Execution Evidence 做 Candidate Evaluation。

------

# 五十二、如果面试官问：“RAG 做了哪些高级优化？”

不要只回答：

```text
BM25
RRF
Cross-Encoder
```

推荐：

> 我把 RAG 优化分成 retrieval、ranking、abstention 和 context selection 四层。先固定 Dense Baseline，再增加 BM25 验证 sparse/dense 互补性，用 RRF 做 rank fusion；之后用 Cross-Encoder 做二阶段 reranking；再尝试 No-Answer Threshold 和 Top-K Context Selection。
>
> 但项目重点其实是 Evaluation-Driven Optimization。Cross-Encoder 在公开 Benchmark 上变好但业务 Guardrail 回退，因此没有生产化；No-Answer 也没有找到可行 Policy。Hybrid RRF 后来真正接进 Runtime，但逐 Case Regression 超过 Gate，所以当前 Production Default 仍是 Baseline。

最终 Source Audit 明确确认当前默认仍为 `BASELINE`。

------

# 五十三、如果面试官问：“Memory 做到什么程度？”

推荐：

> 我的 Memory 不只是把历史消息存进数据库。后面把它分成 Semantic Memory 和 Episodic Memory，还进一步区分 private/project scope、Owner、Requester、Visibility 和 Authorization。
>
> 多 Agent 场景下我尤其强调 Task Delegation 不等于 Memory Permission Delegation；Project Shared Memory 也不是全局共享，而是通过 typed Project Grant 控制 READ、WRITE、FORGET、PROMOTE。Memory 内容本身永远不能成为 Authorization Authority。

------

# 五十四、如果面试官问：“MCP 怎么接的？”

推荐：

> 我没有把 MCP 做成第二套 Tool Runtime，而是把 MCP Server 当 External Tool Provider。启动时通过 stdio 做 initialize 和 tools/list，把远端 Tool 经过 Local Mapping 包装成 MCP-backed ToolAdapter，再注册进原来的 ToolRegistry。
>
> 所以 MCP Tool 和 Built-in Tool 从进入 Runtime 以后走的是同一条 Validation、Governance、HITL、Claim 和 ToolExecutionService。MCP annotations 只作为 Provider Claim，不能降低本地 Risk；MCP Client 也不拥有 mutation retry authority。

------

# 五十五、全项目最值得准备的 12 个 Bad Cases

这些比“做了多少类”更适合面试。

## 1. Plan / AgentState 双写

问题：

```text
Plan says RUNNING
AgentState says SUCCEEDED
```

解决：

```text
Plan = static
AgentState = dynamic truth
```

关键词：

```text
Single Source of Truth
```

------

## 2. Tool UNKNOWN 被当 NOT_STARTED

问题：

```text
请求已发
连接断开
→ 自动 Retry
```

风险：

```text
Duplicate Side Effect
```

解决：

```text
UNKNOWN
→ no automatic retry
```

------

## 3. `persist=False` 仍然读取旧 Memory

真实源码审计问题。

解决：

```text
HistoryPolicy
+
persist
```

分别控制读写。

------

## 4. Journal 已持久化但 Channel 失败

问题：

```text
Output durable
但发送状态不确定
```

解决：

```text
OUTCOME_UNKNOWN
```

不重发。

------

## 5. Planning executor 阻塞 Event Loop

真实压力测试发现同步 admission wait 导致 Cancellation 无法传播。

修复：

```text
asyncio.to_thread(...)
```

把可能阻塞的同步等待移出 Event Loop。

------

## 6. Trace 数值精度问题

大型整数经过浮点存储会：

```text
9007199254740993
→
9007199254740992
```

最后将权威数值语义放到正确数据 Owner 上，而不是修改全局 JSON Codec。

------

## 7. 文档/CLI 暴露数据库密码

Stage4 Demo Gate 曾发现 README / Makefile / CLI Help 中存在明文 DSN Password。

修复配置来源并 Re-Gate。

这个案例说明：

> **Documentation Surface 也是 Security Surface。**

------

## 8. Dataset 和 Corpus 血缘错位

Metric 计算没错，但 Ground Truth 对应另一份 Corpus。

说明：

> **Evaluation 正确不仅取决于公式，也取决于 Data Lineage。**

------

## 9. Retrieval EMPTY 被错误提升成 FAILED

```text
EMPTY
```

本来只是：

```text
没有找到 Evidence
```

却被上层变成：

```text
Run Failed
```

修复后保持 Typed Status。

------

## 10. Approval TOCTOU

用户批准：

```text
Args=A
```

不能执行：

```text
Args=B
```

最终通过：

```text
Immutable Invocation
Binding Digest
Execution Claim
```

绑定。

------

## 11. DeepSeek Tool Call `content=None`

真实 Provider Wire 允许：

```python
content = None
```

内部 Token Estimator 一度假设必须是字符串。

结果 Tool 已经执行成功，Continuation 前却 TypeError。

说明：

> Provider Contract 的 Nullability 必须贯穿所有辅助组件。

最终 Source Audit 仍确认对应 Regression 证据存在。

------

## 12. MCP EmbeddedResource Compatibility

原实现只支持：

```text
TextContent
```

外部 MCP 可能返回：

```text
EmbeddedResource(TextResourceContents)
```

正确修法不是 GitHub 特判，而是：

```text
扩标准 MCP Result Normalization
```

同时没有顺手把完整 Resources Primitive 都做掉。

------

# 五十六、全项目反复出现的一个统一设计思想

仔细看会发现，从 Stage2 到 Stage5，很多看似不同的问题其实是同一个问题。

### Stage2

```text
UNKNOWN Side Effect
≠
NOT_STARTED
```

### Stage2.5

```text
Execution Success
≠
Delivery Success
```

### Stage3

```text
Model Proposal
≠
Security Authority
```

### Stage4

```text
Trace
≠
Evaluation Truth
```

### Stage5

```text
Provider Claim
≠
Runtime Fact
```

它们背后的统一思想就是：

> **不要把一个层面的事实偷偷升级成另一个层面的 Authority。**

这是整个项目最有价值的系统设计认知之一。

------

# 五十七、整个项目最终可以抽象成四个词

## 1. 真值(Truth)

什么是真正可信的事实？

例如：

```text
Trace
≠ EvaluationResult

MCP annotation
≠ Runtime Risk Fact
```

------

## 2. 所有权(Owner)

谁有资格产生或修改这个 Fact？

例如：

```text
Run terminal
→ RunCoordinator

Tool execution
→ ToolExecutionService

ReleaseDecision
→ RegressionReportService
```

------

## 3. 持久化(Persistence)

这个事实要不要 Durable？

例如：

```text
Journal
EvaluationResult
→ durable

RegressionReport
→ 当前可 derived
```

------

## 4. 适配边界(Adapter Boundary)

怎么让两个 Domain 交互而不复制 Business Logic？

例如：

```text
LocalAgent Runtime
→ HTTP Execution Adapter
→ AgentEvalOps

MCP Provider
→ MCP-backed ToolAdapter
→ Tool Runtime
```

这四个词基本可以解释整个项目后期所有 Architecture Decision。

------

# 五十八、30 秒项目介绍

> 我做了两个配套项目：LocalAgent 和 AgentEvalOps。LocalAgent 是一个自研 Agent Runtime，主要完成 RunContext、状态机、Planning、Multi-Agent 并行、Tool/RAG/Memory、Journal、Recovery Validation 和 Graceful Shutdown，后面又补了 Tool Governance、HITL、Native Function Calling 和 MCP。AgentEvalOps 则把 Runtime Trace 和 Execution Evidence 接出来，建立 Dataset、Evaluation Run/Attempt/Result、Baseline/Candidate Regression 和 Release Gate。Stage5 最后用这套 Evaluation 体系实际做了 Hybrid RAG、Prompt Injection、安全、Memory、Tool 和 MCP 的迭代，所以整个项目重点是 Agent Runtime Engineering 加 Evaluation-Driven Optimization，而不是简单做一个聊天机器人。

------

# 五十九、2 分钟项目介绍

> 这个项目其实分成两个系统。LocalAgent 负责真实 Agent Runtime，AgentEvalOps 负责 Evaluation 和 Regression。
>
> LocalAgent 最开始已经能做 RAG、Memory 和 Tool，但我后来发现功能越多，状态、失败和副作用越难管理，所以 Stage2 开始重构 Runtime。建立了 RunContext、AgentState、Scheduler、Budget、Timeout、Cancellation、Tool Side-effect State、Journal-first、Trace、Snapshot 和 Recovery Validation。后面 Stage2.5 再把 Multi-Agent 真正迁进 Runtime，通过 Planner、PlanCompiler、Scheduler、StepResultStore、Synthesis 和 OutputGate 做真实并行和唯一最终输出。
>
> Stage3 做最小生产化，把 Settings、startup validation、ToolRegistry、Governance、ResourceAuthorization、ToolExecutionService、安全边界和 Graceful Shutdown 收进明确 Composition Root，并且把 Trace 真正导出到 AgentEvalOps。Stage3.5 再冻结这些核心 Owner 和 Contract。
>
> Stage4 开始改 AgentEvalOps。核心是把 Trace 从 Evaluation Truth 中拆开，建立 Dataset/TestCase、Run/Attempt/Result，通过 PostgreSQL CAS 和 Fencing 管理 Evaluation 并发，再做 Baseline/Candidate Regression、Critical Case Release Gate 和 Trace-to-Dataset Feedback。
>
> Stage5 最后把两边真正串起来：AgentEvalOps 通过 HTTP ExecutionTarget 运行真实 LocalAgent，再用 Retrieval Evidence、Recall/MRR/NDCG、LLM Judge 和 Security Evaluator评价改动。我实际做了 BM25、RRF、Cross-Encoder 等 RAG 实验，但没有为了项目好看全部上线；最后 Production Default 仍然是 Baseline，Hybrid RRF 只是 production-reachable。后面又做了 Advanced Memory、Tool HITL、Natural-language Tool Calling 和 MCP Integration。MCP 只是外部 Tool Provider，最后仍然走原来的 Local Governance、Claim 和 ToolExecutionService。

------

# 六十、5 分钟项目介绍

> 项目最开始是一个面向复杂知识查询和工具执行场景的 Agent 原型，有 RAG、Memory、Tool 和多个 Agent。但是随着能力越来越多，我发现真正困难的已经不是 Prompt 或调用模型，而是 Runtime 怎么管理状态、并发、副作用、失败和生命周期。
>
> 所以 Stage2 我首先做 Agent Runtime 重构。把一次执行抽象成 RunContext 和 AgentState，Plan 只负责静态执行定义，AgentState 才是动态状态唯一事实源。Scheduler 用 StepClaim 控制什么时候可以执行，Model 层把 Retry 和 Candidate Fallback 分开，Tool 又显式记录 Side-effect State。这里最重要的一个原则是 UNKNOWN 不能当 NOT_STARTED，因为网络断开时外部 Tool 可能已经发生副作用。
>
> Event 又采用 Journal-first，也就是先持久化事实再向外 Streaming。这样 Tool 已经执行但客户端发送失败时，Runtime 不会因为用户没收到结果就重新执行 Tool。Snapshot 和 Journal 后面用于 Recovery Validation，但我没有做自动 Resume，因为缺少完整 Durable Executor 和 Side-effect Recovery。
>
> Stage2.5 解决真实 Multi-Agent。Planner 不直接创建任意 DAG，只输出 Typed Decision，再由 PlanCompiler 编译成 Runtime 允许的执行图。多个 Specialist 由 Scheduler 真正并行执行，结果进 StepResultStore；Synthesis 只能读自己的 dependency，不允许读全量 Store。最后由 OutputGate 成为唯一 Final Answer Owner。这一步还发现了一个很典型的问题：`persist=False` 只能控制 Memory 写，不能阻止 Specialist 读取旧 History，所以最后把 HistoryPolicy 和 persist 拆成两个正交权限。
>
> Stage3 做最小生产化。我把 Config Validation、Persistence Preflight、Readiness 和 Shutdown 收进唯一 Composition Root。Tool 则正式拆成 ToolRegistry、ToolGovernance、ResourceAuthorization 和 ToolExecutionService。模型只负责提出 Tool，不能自己批准权限。Prompt Injection 我也没有说完全解决，而是先保护 deterministic authority：RAG、Tool Result、Memory 这些低信任数据即使影响模型，也不能直接改变 Tool Permission。Observability 方面还做了 Trace Contract 并真实导出到 AgentEvalOps。
>
> 到 Stage4 开始做 AgentEvalOps。这里最核心的设计是 Trace 不是 Evaluation Result。Trace 只是 Observation 和 Evidence，Evaluation 独立拥有 Dataset、TestCase、ExecutionTarget、Run、Attempt 和 Result。EvaluationAttempt 使用 PostgreSQL CAS Claim，Fencing Token 防 stale worker 回写；Retry 创建新 Attempt，Result append-only。然后 Baseline 和 Candidate 按 Case/Evaluator Version 对齐生成 Regression，再由业务 Criticality 做 Release Gate。线上 Trace 也不能自动进入 Dataset，必须经过 Explicit Feedback，因为 actual output 不能直接当 expected answer。
>
> Stage5 最后真正做 Evaluation-Driven Optimization。先把 AgentEvalOps 的 ExecutionTarget 接到真实 LocalAgent，然后 Runtime 原始 Retrieval 会生成 retrieved/ranked/selected Evidence。RAG 方面我固定 Dense Baseline，再做 BM25、RRF、Cross-Encoder、No-Answer 和 Context Selection。比较有意思的是，Cross-Encoder 在公开 Benchmark 确实更好，但业务 Guardrail 下降，所以没有 production enable；No-Answer 最后甚至没有找到一个满足约束的 Threshold，也直接 Reject。Hybrid RRF 后来真正接进 Runtime，但由于 Per-case Regression Gate 没满足，现在 Default 仍然是 Baseline。
>
> 后面又把 Memory 从普通 History 扩展成 Semantic/Episodic/Project Memory，并做 Owner、Requester 和 Grant；Tool 增加 HITL，高风险 Operation 先 Approval，再 CAS Claim 才执行；Native Function Calling 只负责模型 Tool Selection，Runtime 仍然负责 Validation 和 Governance。最后接 MCP 时，我也没有重做 Tool Runtime，而是把 MCP Server 作为 External Tool Provider，通过 Adapter 注册进原来的 ToolRegistry，所以 Built-in Tool 和 MCP Tool 最后都共享同一个 Governance、HITL、Retry 和 Side-effect Truth。
>
> 所以我觉得整个项目最重要的工程收获是：复杂 Agent 系统最难的不是让模型更智能，而是明确 Truth、Owner、Persistence 和 Adapter Boundary，让模型的概率性决策始终被放在一个确定性的 Runtime 和 Evaluation 控制面里。

------

# 六十一、10 分钟深挖时怎么展开

不要从 Stage2 一直背到 Stage5。

先讲 2 分钟总故事。

然后让面试官选择深挖。

推荐形成五条分支：

```text
A. Agent Runtime
B. Multi-Agent
C. Evaluation / Regression
D. RAG / Memory
E. Tool / HITL / MCP
```

------

## A. Runtime 分支

重点准备：

```text
RunContext
AgentState
Single Source of Truth
Cancellation
Deadline
Retry / Fallback
Side-effect UNKNOWN
Journal-first
Recovery Validation
Graceful Shutdown
```

------

## B. Multi-Agent 分支

重点：

```text
Planner vs Compiler
Frozen Plan
Scheduler / StepClaim
Parallel Specialist
StepResultStore
Dependency ACL
Synthesis
OutputGate
History Isolation
```

------

## C. Evaluation 分支

重点：

```text
Trace ≠ EvaluationResult
Dataset / GroundTruth
Run / Attempt / Result
CAS
Fencing Token
Retry Lineage
Append-only Result
Baseline / Candidate
Criticality
Release Gate
Trace Feedback
```

------

## D. RAG / Memory 分支

重点：

```text
Dense
BM25
Hybrid
RRF
Cross-Encoder
Recall / MRR / NDCG
No-Answer
Context Selection
Data Lineage

Semantic Memory
Episodic Memory
Private / Project
Owner / Requester
Memory Authorization
```

------

## E. Tool / HITL / MCP 分支

重点：

```text
ToolRegistry
ToolAdapter
Typed ToolInvocation
Governance
Approval
CAS
Execution Claim
Side-effect Truth
Function Calling
MCP Adapter
Provider Claim
Retry Authority
```

------

# 六十二、高频快问快答

## Q：你的项目是 Agent Framework 吗？

不是通用 Framework。

它是一个围绕真实 Agent Runtime、Evaluation 和能力优化构建的工程项目。

------

## Q：为什么不用 LangGraph？

可以用，但我的学习目标是显式掌握 Runtime Ownership、Side Effect、Cancellation、Recovery、HITL 等底层语义。

------

## Q：真正的 Runtime Owner 是谁？

Run 生命周期和 Terminal：

```text
RunCoordinator
```

Runtime 动态状态：

```text
AgentState
```

------

## Q：Plan 和 AgentState 为什么分开？

Plan 是静态执行定义。

AgentState 是动态执行事实。

避免双写。

------

## Q：为什么 Tool Timeout 不能直接 Retry？

因为远端 Side Effect 可能已经发生。

------

## Q：你保证 Exactly-once 吗？

不做系统级 Distributed Exactly-once 声明。

目前部分链路实现 single-process at-most-once claim/publish semantics。

------

## Q：为什么 Trace 不是 Evaluation？

Trace 描述发生了什么。

Evaluation 描述这个行为质量如何。

------

## Q：Evaluation 为什么需要 Attempt？

为了表示 Retry、Worker Failure、Claim 和 Execution Lineage。

------

## Q：CAS 和 Fencing 区别？

CAS 防两个 Worker 同时 Claim。

Fencing 防旧 Worker 恢复后继续写。

------

## Q：RAG 当前默认是 Hybrid 吗？

不是。

```text
Default = BASELINE
```

Hybrid RRF production-reachable，但不是默认。

------

## Q：Cross-Encoder 上线了吗？

没有。

当前仍属于 Evaluation / Experimental 能力。

------

## Q：为什么不直接把更多 Chunk 给 LLM？

更多 Context 会增加 Noise 和 Token Cost，不保证 Support Coverage 提升。

------

## Q：Semantic Memory 和 Episodic Memory 区别？

Semantic：

```text
我知道什么
```

Episodic：

```text
我经历过什么
```

------

## Q：Delegation 会继承 Memory 权限吗？

不会。

Task Delegation != Memory Permission Delegation。

------

## Q：Function Calling 谁负责安全？

Function Calling 负责 Tool Selection 和 Arguments Proposal。

Local Runtime 负责安全。

------

## Q：MCP 和 Function Calling 什么关系？

Function Calling：

```text
Model → Tool Call Intent
```

MCP：

```text
Host ↔ External Tool Provider
```

二者是不同层。

------

## Q：MCP annotations 可以决定 Tool Risk 吗？

不可以。

Provider Metadata 只是 Provider Claim。

Local Policy 才是 Authority。

------

# 六十三、整个项目最不能说错的 Truth Boundary

## 不能说：

```text
整个系统已经 Production Proven
```

正确：

> 完成了大量真实源码、Regression、Cross-system E2E 和最小生产化验证，但不是企业级 Production Certification。

------

## 不能说：

```text
实现 Distributed Exactly-once
```

没有。

------

## 不能说：

```text
支持自动 Durable Recovery
```

当前：

```text
Recovery = VALIDATION_ONLY
```

------

## 不能说：

```text
完整解决 Prompt Injection
```

正确：

```text
Prompt Injection
= PARTIALLY_SUPPORTED
```

重点保护 deterministic authority boundary。

------

## 不能说：

```text
RAG 默认已经升级 Hybrid RRF
```

最终：

```text
Default = BASELINE
Hybrid RRF = production-reachable optional
```

------

## 不能说：

```text
Cross-Encoder 已 Production
```

没有。

------

## 不能说：

```text
HITL = distributed exactly-once
```

当前：

```text
single-process active-Run at-most-once claim
```

------

## 不能说：

```text
实现完整 MCP Resources
```

当前只支持：

```text
TextContent
EmbeddedResource(TextResourceContents)
isError
```

没有完整 Resources Primitive。

------

## GitHub MCP 也要注意

Phase9 历史学习材料记录过官方 GitHub MCP E2E。

但最终 Stage5 Source Audit 没有重新恢复出足够强的当前成功证据，所以最终总叙事最好说：

```text
GitHub MCP compatibility
= source-confirmed

current external mutation success
= final audit unable to re-verify
```

不要把 Final Audit 描述成重新证明 GitHub mutation PASS。

------

# 六十四、最后真正应该形成的项目认知

如果学完整个项目以后还把它理解成：

```text
我做了 RAG
我做了 Multi-Agent
我做了 MCP
```

其实还没有抓住重点。

真正应该形成的是下面这套认知：

```text
模型负责概率性推理
Runtime 负责确定性执行

Planner 可以提出 Plan
Compiler 决定合法执行图

Model 可以提出 Tool
Runtime 决定能否执行

Provider 可以声明 Metadata
Local Policy 决定 Security Fact

Human 可以批准
Runtime Claim 决定唯一执行资格

Trace 可以提供 Evidence
Evaluation 决定 Quality Truth

Average Metric 可以变好
Regression Gate 决定是否接受 Candidate
```

也就是：

> **Agent 工程的核心不是让模型拥有更多 Authority，而是在模型能力越来越强时，仍然保持明确的 Runtime Authority、Evidence Boundary 和 Evaluation Control Plane。**

------

# 六十五、全项目最终一句话

> **我把一个最初以 RAG、Memory 和 Multi-Agent 为主的 Agent 原型，逐步演进成了一个有明确 Runtime Owner、并发与副作用语义、最小生产运行边界、独立 Evaluation / Regression 平台以及 Tool/HITL/MCP 安全执行链的完整 Agent 工程系统；并且后期所有 RAG、Memory 和 Tool 能力都不再靠“感觉优化”，而是通过真实 Execution Evidence 和 AgentEvalOps 做 Evaluation-Driven Optimization。**

------

# 六十六、面试前最后背这 12 句话

1. **Agent Runtime 的核心不是调用 LLM，而是管理状态、资源、副作用和生命周期。**
2. **一个事实只能有一个 Owner。**
3. **Plan 是静态定义，AgentState 是动态事实。**
4. **UNKNOWN 不能伪装成 NOT_STARTED。**
5. **业务执行成功、用户交付成功和持久化成功是不同事实。**
6. **Planner / Model 可以提出决策，但不能成为 Runtime Authority。**
7. **Trace 是 Observation / Evidence，不是 Evaluation Truth。**
8. **CAS 解决竞争，Fencing 解决 stale owner。**
9. **Optimization without Evaluation is Guessing。**
10. **Capability Proven 不等于 Candidate Accepted。**
11. **Task Delegation 不等于 Memory Permission Delegation。**
12. **MCP 是 External Tool Provider Protocol，不是第二套 Tool Runtime。**

------

# 六十七、项目学习结束后的最终知识框架

```text
                    ┌────────────────────┐
                    │     LLM / Agent    │
                    │ Probability Layer  │
                    └─────────┬──────────┘
                              │ Proposal
                              ▼
                    ┌────────────────────┐
                    │   Agent Runtime    │
                    │ Deterministic Ctrl │
                    │                    │
                    │ State / Policy     │
                    │ Scheduler / Claim  │
                    │ Side Effect        │
                    │ HITL / Lifecycle   │
                    └─────────┬──────────┘
                              │ Evidence
                              ▼
                    ┌────────────────────┐
                    │    AgentEvalOps    │
                    │ Evaluation Control │
                    │                    │
                    │ Dataset / GT       │
                    │ Metrics / Judge    │
                    │ Regression / Gate  │
                    └─────────┬──────────┘
                              │ Decision
                              ▼
                    ┌────────────────────┐
                    │  Optimize Runtime  │
                    │ RAG / Memory / Tool│
                    │ Security / MCP     │
                    └─────────┬──────────┘
                              │
                              └─────→ 下一轮 Evaluation
```

这就是整个项目最终应该记在脑子里的那张图。