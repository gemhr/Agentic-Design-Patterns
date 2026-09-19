# Stage8 — Agentic Test Engineering Workflow

## 一、先记住 Stage8 到底做了什么

Stage8 不是重新实现测试平台。

真实业务中已经有：

```text
Case Generation Platform
Environment Management Platform
Test Execution Platform
Ticket / Issue Platform
```

Stage8 做的是这些系统上面的：

```text
Feature 理解
→ 风险分析
→ 测试计划
→ 人工 Review
→ Case 生成编排
→ 环境选择
→ 测试启动
→ 长任务状态管理
→ 结果观察
→ 日志确定性解析
→ Failure Triage
→ Tool Approval
→ Ticket Continuation
```

核心思想可以压成一句：

> **Agent 负责模糊理解、分析和建议；Application / Runtime 负责身份、状态、版本绑定、审批、并发、幂等和外部副作用。**

Stage8 最终 PRODUCT 主链已经闭环。

------

# 二、Stage8 最终状态

Final Gate：

```ini
STAGE8_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

CORE_BUSINESS_LOOP = CLOSED_FOR_PRODUCT_PATH_WITH_MOCK_EXTERNAL_PLATFORMS

PLANNING_LOOP = CLOSED
CASE_LOOP = CLOSED
EXECUTION_LOOP = CLOSED
SUCCESS_LOOP = CLOSED
FAILURE_TRIAGE_LOOP = CLOSED
PRODUCT_TICKET_LOOP = CLOSED

TEST_DATA_LOOP = PARTIAL
CI_LOOP = PARTIAL

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 7
P2 = 4

INTERVIEW_READY = YES
DEMO_READY = YES
PRODUCTION_READY = NO
```

Stage8 回归：

```text
89 passed
```

Migration 唯一 head：

```text
0016_stage8_wp10_ticket
```

------

# 三、WP0～WP10 一张图

```text
WP0
Mission / Application Foundation
↓
建立 FeatureTestMission、BusinessReview、MissionRunReference

WP1
Evidence-driven Specialist Agents
↓
Feature Understanding / Risk / Test Planning

WP2
Mock Business Platforms & Governed Actions
↓
建立外部平台 typed Port + Tool Runtime Adapter

WP3
Async Execution & Failure Triage
↓
ExternalExecutionJob + FailureEvidencePackage + Triage

WP4
CI Guardian
↓
CI clustering / history / change correlation / hypothesis

WP5
Minimal Web Demo
↓
用真实 canonical API 串主流程

WP6
Workflow / Production Readiness Audit
↓
发现 Case / Env / Result / Ticket 等关键业务缺口

WP7
Generated Case Platform Bridge
↓
TestPlan → Case Platform → GeneratedCaseArtifact

WP8
Environment-aware Execution Bridge
↓
环境选择 → XLS → Test Platform → async Job

WP9
Execution Result Observation
↓
Provider Observation → Parser → SUCCESS / FAILED

WP10
Durable Ticket Continuation
↓
PRODUCT → Approval → Continuation → Ticket Platform
```

Final Gate 又把这些 WP 组合起来重新验证，不是简单把每个 WP 的 PASS 相加。

------

# 四、完整业务链必须能背下来

最终 canonical 主链：

```text
FeatureContext
↓
Feature Understanding Agent
↓
Risk Analysis Agent
↓
Test Planning Agent
↓
durable TestPlan
↓
Business Review
↓
Case Generation Tool
↓
GeneratedCaseArtifact
↓
Environment Requirements
↓
Environment Search
↓
Environment Recheck
↓
execution-list.xls
↓
PENDING ExternalExecutionJob
↓
Test Execution Tool
↓
RUNNING ExternalExecutionJob
↓
Provider Observation
↓
ExecutionResultParser
↓
SUCCESS / FAILED
```

成功：

```text
SUCCESS
→ Mission COMPLETED
```

失败：

```text
FAILED
→ FailureEvidencePackage
→ Failure Triage
```

产品问题：

```text
PRODUCT
→ TicketDraft
→ Tool Approval
→ TicketContinuation
→ resume approved ToolInvocation
→ Ticket Platform
→ ticket_id / ticket_url
```

------

# 五、WP0 — Mission 为什么要和 Agent Run 分开

这是整个 Stage8 第一个重要概念。

## Agent Run

通常：

```text
几十秒
几分钟
```

有：

```text
deadline
budget
cancellation
terminal state
```

## FeatureTestMission

可能持续：

```text
数小时
数天
```

因为中间可能：

```text
等人工 Review
等环境
等测试执行
等 Approval
等 Ticket continuation
```

所以：

```text
Mission ≠ Agent Run
```

Mission 是业务生命周期。

Run 是一次模型执行生命周期。

Final Gate 确认当前没有 canonical 路径让一个 Agent Run 挂几个小时等待测试结束。

### 面试一句话

> 我没有把长业务流程直接塞进 Agent Run，Mission 负责跨请求、跨人工等待和外部任务，Agent Run 只负责一次 bounded reasoning。

------

# 六、WP1 — Specialist Agent 到底负责什么

主要 Specialist：

```text
Feature Understanding Agent
Risk Analysis Agent
Test Planning Agent
Failure Triage Agent
CI Guardian Agent
```

它们不是业务 Truth Owner。

Agent 负责：

```text
理解
分析
推断
规划
归因
建议
```

后端负责：

```text
schema validation
evidence ID validation
state transition
version binding
approval
side effect
```

这是 Stage8 最重要的设计边界之一：

> **LLM 可以提出事实解释，但不能创造系统事实。**

------

# 七、Evidence-bound 是什么意思

Agent 不能随便说：

```text
execution_id = xxx
case_path = xxx
environment = xxx
```

系统先准备：

```text
authoritative evidence IDs
```

Agent 输出只能引用这些 evidence。

之后后端还会重新校验。

例如 Failure Triage：

```text
ExecutionResult
Case
Environment
TestPlan
Log
```

由后端组成：

```text
FailureEvidencePackage
```

然后 Agent 做：

```text
classification
hypothesis
recommendation
```

Agent 不拥有 Execution identity。

------

# 八、WP1 — TestPlan 为什么必须有 version + digest

TestPlan 是后续整个测试流程的业务依据。

不能：

```text
Review Plan A
→ Plan 修改成 B
→ 继续用 A 的 Review
```

所以 Review 精确绑定：

```text
subject_id
version
digest
```

而且：

```text
environment_requirements
```

也进入完整 TestPlan digest。

否则会出现：

```text
Review approves:
4G + hardware A

Plan later changes:
5G + hardware B

旧 Review 仍然有效
```

这是错误的。

Final Gate 已确认 environment requirements 被包含在 canonical TestPlan digest 内。

------

# 九、Business Review 和 Tool Approval 不是一回事

这点面试非常容易问。

## Business Review

回答：

> 这份 TestPlan 在业务上能不能继续？

绑定：

```text
subject
version
digest
```

## Tool Approval

回答：

> 是否允许执行这一次具体 ToolInvocation？

绑定：

```text
tool_invocation_id
invocation_binding_digest
```

所以：

```text
Business Review
≠
Tool Approval
```

一个批业务方案。

一个批真实外部副作用。

------

# 十、WP2 — 为什么已有平台还要统一 Tool Runtime

外部平台虽然业务不同：

```text
Case Platform
Environment Platform
Execution Platform
Ticket Platform
```

但进入 AgentCore 以后统一走：

```text
Stage8 Application
→ GovernedToolInvoker
→ ToolRegistry
→ ToolGovernance
→ ToolExecutionService
→ Platform Adapter
→ External Platform
```

这样就不会出现：

```text
Case 有安全检查
Execution 没安全检查
Ticket 自己直接调 API
```

------

# 十一、为什么 MCP Tool 也不能特殊处理

Stage8 延续整个 AgentCore 的原则：

```text
Built-in Tool
MCP Tool
Business Platform Tool
```

Provider 可以不同。

Execution Authority 不能不同。

因此：

```text
Model
→ ToolInvocation
→ Validation
→ Governance
→ Approval if needed
→ Claim
→ ToolExecutionService
→ Provider
```

而不是：

```text
Model
→ MCP Client
→ tools/call
```

------

# 十二、WP7 — Case Generation 的正确边界

真实业务已有：

```text
自然语言
→ 自动生成测试 Case
```

平台。

所以 AgentCore 不负责：

```text
自己写完整 Case 脚本
```

AgentCore 负责：

```text
TestScenario
→ Case Platform request
```

Platform 负责：

```text
provider_case_id
case_path
```

后端保存：

```text
GeneratedCaseArtifact
```

------

# 十三、为什么 case_path 不能让 caller 直接传

错误设计：

```json
{
  "case_path": "\\server\\random\\case"
}
```

会产生：

```text
arbitrary path
绕过 Case Generation
绕过 Review binding
执行未批准 Case
```

所以现在 Execution API 只接：

```text
generated_case_artifact_id
```

后端自己解析：

```text
provider_case_id
case_path
TestPlan binding
```

Final Gate 已确认 Web Demo 也切换到了这个新 canonical API。

------

# 十四、GeneratedCaseArtifact 为什么重要

它不是简单缓存一个 path。

它表示：

```text
这个 Case
是哪个 Mission 的
来自哪个 TestPlan
哪个 version
哪个 digest
哪个 scenario
哪个 Provider
```

因此它是：

> **Case Authority。**

Final Gate 最终冻结：

```text
CASE_AUTHORITY = GENERATED_CASE_ARTIFACT
```

------

# 十五、Case Generation 为什么也要幂等

假设：

```text
AgentCore
→ Case Platform
→ Case 已生成

网络 response 丢了
```

如果直接 retry：

```text
可能再生成一个 Case
```

所以 WP7 使用稳定 business identity / provider idempotency key。

同时数据库有 artifact uniqueness。

目标不是绝对 once。

目标是：

```text
同一个业务请求
→ 尽量复用同一个 Case generation operation
```

------

# 十六、WP8 — Agent 为什么不能直接选 Environment

Agent 可以说：

```text
需要：
5G
某硬件
某 feature flag
某 capability
```

这是：

```text
EnvironmentRequirements
```

但 Agent 不能说：

```text
ENV-001 当前 FREE
IP 是 10.x.x.x
```

这些是外部事实。

Owner 是：

```text
Environment Platform
```

Final Gate：

```text
ENVIRONMENT_STATUS_AUTHORITY = ENVIRONMENT_PLATFORM
```

------

# 十七、Environment Selection 为什么用 deterministic code

当前：

```text
requirements
→ hard filter
→ FREE
→ stable sort
```

不需要 LLM。

因为：

```text
FREE / BUSY
版本
能力
feature flag
```

全部是结构化条件。

这里让 LLM 参与只会：

```text
增加随机性
降低可测试性
```

------

# 十八、为什么查询到 FREE 后还要再检查一次

因为：

```text
T1: Environment = FREE
T2: 另一个用户占用
T3: AgentCore 启动测试
```

所以真正 start 前还要：

```text
get_environment()
→ recheck
```

如果 BUSY：

```text
try next candidate
```

全部无资源：

```text
WAITING_FOR_RESOURCE
```

不会强行运行。

------

# 十九、为什么不自己用 Redis 锁环境

因为 AgentCore 不是环境最终 Owner。

假设自己：

```text
SETNX env:001
```

但公司原 Environment Platform 不认识这个锁。

其他用户还是可以占用环境。

这是假安全。

所以正确做法：

> 使用 Environment Platform 自身的 reserve / lease 能力。

当前平台没有提供。

所以诚实接受：

```text
recheck → start
```

之间仍有 race。

Final Gate 把它列为 Accepted P1。

------

# 二十、为什么没有资源要 WAIT，而不是降级

例如要求：

```text
5G environment
```

没有 5G FREE。

不能：

```text
自动找 4G
```

因为这会改变 TestPlan 语义。

正确：

```text
WAITING_FOR_RESOURCE
```

后续资源可用再继续。

------

# 二十一、为什么 execution-list.xls 不让 LLM 写

Excel 内容本质是结构化 execution contract。

LLM 直接操作单元格：

```text
容易格式错误
容易漏字段
不可稳定复现
```

所以：

```text
GeneratedCaseArtifact
Environment
Parameters
↓
ExecutionListBuilder
↓
execution-list.xls
```

普通代码生成。

Final Gate 确认文件输出路径也由 AgentCore 控制。

------

# 二十二、WP8 — 为什么 External Job 必须先 PENDING 再调用外部平台

错误：

```text
先启动外部测试
→ 再写数据库
```

如果：

```text
外部已启动
进程 crash
```

数据库完全不知道这次执行存在。

正确：

```text
persist ExternalExecutionJob PENDING
commit
↓
external start
```

这样至少留下：

```text
case
environment
IP
xls
parameters
business identity
```

的恢复锚点。

------

# 二十三、为什么长测试不能让 Agent Run 等

测试可能：

```text
30 min
2 hours
8 hours
```

Agent Run 有：

```text
deadline
token budget
runtime resources
```

不应该挂着。

因此：

```text
start execution
→ external_execution_id
→ ExternalExecutionJob RUNNING
→ current Agent Run ends
```

之后由另外的 observation 操作继续。

------

# 二十四、Execution Replay Identity 是什么

同一个 Case 不代表同一次执行。

例如：

```text
Case A
param = X
```

和：

```text
Case A
param = Y
```

是不同执行。

所以 request digest 至少包含：

```text
mission
artifact
parameters
```

Final Gate 已确认：

```text
same request → replay
different parameters → no false replay
```

------

# 二十五、WP9 — 谁决定测试成功还是失败

不能是 caller。

不能是 LLM。

当前 Authority：

```text
TestExecutionPlatform
→ terminal readiness

ExecutionResultParser
→ SUCCESS / FAILED
```

Final Gate：

```text
EXECUTION_RESULT_AUTHORITY =
PROVIDER_RESULT_PLUS_DETERMINISTIC_PARSER
```

------

# 二十六、为什么 Provider status 不直接决定 SUCCESS / FAILED

设计上把两个问题分开：

```text
Platform status:
任务还在跑吗？
结果 ready 了吗？
Result log:
最终 SUCCESS 还是 FAILED？
```

所以 Provider status 只有：

```text
readiness authority
```

没有：

```text
business result authority
```

这样不会出现两个 Truth Owner。

------

# 二十七、为什么 SUCCESS / FAILED 不交给 LLM

因为日志是固定格式。

例如：

```text
STATUS=FAILED
ERROR_CODE=...
ERROR_MESSAGE=...
FAILED_STEP=...
```

普通 Parser：

```text
准确
稳定
低成本
可测试
```

LLM：

```text
更适合分析为什么失败
```

所以：

> Parser 判断 What happened；Triage 分析 Why。

------

# 二十八、大日志最重要的设计点

不能：

```text
log[:16KB]
→ parser
```

因为：

```text
STATUS=FAILED
```

可能在日志结尾。

所以当前设计：

```text
Parse Boundary
≠
Persist Boundary
```

Provider Adapter 可以扫描完整 deterministic log 获取决定字段。

数据库只保存：

```text
bounded head/tail excerpt
normalized fields
result_location
```

最多：

```text
16 KiB excerpt
```

Final Gate 已确认大日志 tail marker 路径通过。

------

# 二十九、Caller 为什么不能 self-report result

旧 WP3 曾经允许：

```text
POST FAILED
```

这只能用于早期 Mock。

现在 canonical：

```text
POST observe(job_id)
```

用户只能说：

> 帮我查这个 Job。

不能说：

> 这个 Job FAILED。

Legacy callback 仍存在，但只允许：

```text
SERVICE principal
+
narrow callback scope
```

普通 Human / Web 不允许。

------

# 三十、WP3 / WP9 — Terminal First-wins

假设：

```text
observe #1
→ SUCCESS
```

后来：

```text
observe #2
→ FAILED
```

不能：

```text
SUCCEEDED → FAILED
```

第一次 accepted terminal result 成为 durable truth。

依赖：

```text
PostgreSQL row lock
+
terminal first-wins
```

------

# 三十一、两个 FAILED observation 同时来怎么办

最终：

```text
one terminal result
one Triage claim
```

机制：

```text
execution row FOR UPDATE
+
conditional triage claim
```

所以不会：

```text
Triage twice
TicketDraft twice
Approval twice
```

------

# 三十二、WP3 — FailureEvidencePackage 为什么必须由后端构建

如果让 Triage Agent 自己说：

```text
我分析的 Case 是 X
环境是 Y
执行是 Z
```

它可能产生 hallucination。

所以系统根据 durable data 重建：

```text
Plan
Case
Environment
Execution
Result
Log
```

Agent 只能消费。

------

# 三十三、Failure Classification

当前分类：

```text
PRODUCT
TEST_DATA
ENVIRONMENT
TOOL_CHAIN
INFRASTRUCTURE
UNKNOWN
```

这个分类可以用 Agent。

因为：

```text
日志事实已经确定
```

但：

```text
失败根因通常是概率性推断
```

正好属于 Agent 擅长范围。

------

# 三十四、TEST_DATA 为什么没有强行做自动修复

用户的新 Feature 可能第一次出现。

如果失败是：

```text
test data semantic mismatch
```

系统可能根本不知道“正确数据”是什么。

所以 Stage8 没有虚构：

```text
self-healing
```

当前只做到：

```text
TEST_DATA classification
→ recommendation
→ candidate repair
```

机械且能证明正确的未来可以 deterministic repair。

语义性问题：

```text
human
```

------

# 三十五、WP4 — CI Guardian 的正确定位

CI Guardian 当前有：

```text
manual CI ingest
failure clustering
history comparison
change correlation
LLM hypothesis
recommendation
```

普通代码负责：

```text
哪些失败聚成一类
历史上有没有出现
最近有哪些 change
```

LLM 负责：

```text
哪一个更可能有关
原因假设
建议排查路径
```

Change correlation 只是候选关系。

不是：

```text
确定根因
```

------

# 三十六、WP10 — 为什么 PRODUCT 不直接创建 Ticket

因为 create_ticket 是：

```text
HIGH RISK
NON_IDEMPOTENT
external mutation
```

所以：

```text
Triage PRODUCT
→ TicketDraft
→ Tool Approval
```

必须由人授权。

------

# 三十七、TicketDraft、Approval、Ticket 是三种事实

必须区分：

```text
TicketDraft
= 准备提什么内容

Approval APPROVED
= 允许执行

External Ticket
= Provider 已经真正创建
```

所以：

```text
APPROVED ≠ Ticket Created
```

Final Gate 明确把三者分开。

------

# 三十八、为什么 Approval 后还需要 TicketContinuation

Approval 只回答：

```text
允许 / 拒绝
```

它不负责：

```text
什么时候执行
哪个 Worker 执行
执行到哪
provider timeout 怎么办
ticket_id 怎么回写
```

所以需要 durable：

```text
TicketContinuation
```

跨：

```text
HTTP request
process restart
worker invocation
```

保存业务状态。

------

# 三十九、Approval A 如何防止执行 Draft B

Continuation 创建时冻结：

```text
request_snapshot
request_digest
approval_id
tool_invocation_id
invocation_binding_digest
```

执行前重新验证：

```text
current Approval
request digest
durable invocation identity
binding digest
```

不一致：

```text
FAIL CLOSED
```

Final Gate：

```text
Approval A cannot authorize Draft B
```

------

# 四十、Business Claim 和 Tool Claim 为什么需要两层

## Business Claim

```text
TicketContinuation
READY → PROCESSING
```

回答：

> 哪个 Worker 负责这个业务任务？

## Tool Execution Claim

```text
DurableApprovalService.claim_execution()
```

回答：

> 谁真正拥有这次外部副作用执行权？

这是两个不同层级。

即使 Stage8 业务层重复：

```text
Tool Runtime
```

仍然是最终 Side Effect Authority。

------

# 四十一、两个 Continuation Worker 同时执行怎么办

依靠：

```text
READY → PROCESSING CAS
```

只有一个 winner。

然后 Tool Runtime 再做一次 execution claim。

因此：

```text
one business winner
one external execution
```

Final Gate 已回归。

------

# 四十二、为什么 Ticket timeout 不能自动重试

最典型：

```text
create_ticket
→ Provider 已创建
→ response lost
```

AgentCore 看起来只是 timeout。

如果 retry：

```text
Ticket #1
Ticket #2
```

所以：

```text
UNKNOWN
→ NO BLIND RETRY
```

这是 NON_IDEMPOTENT Tool 最关键的生产意识。

------

# 四十三、到底有没有 Exactly-once

不能说通用 exactly-once。

准确说：

内部用了：

```text
stable idempotency key
unique constraint
row lock
CAS
business claim
tool execution claim
first-wins
```

尽量做到：

```text
exactly-once-like safety
```

但外部 Provider 如果：

```text
执行成功
response 丢失
又不支持 idempotency/reconciliation
```

就只能：

```text
UNKNOWN
```

Final Gate 也明确禁止宣称 generic external exactly-once。

------

# 四十四、Kafka 为什么没有硬塞进 Stage8

当前 TicketContinuation：

```text
PostgreSQL durable row
+
process_ready_once()
```

已经保证：

```text
原 HTTP 结束以后任务不会消失
```

Kafka 未来的价值：

```text
automatic wakeup
event delivery
worker decoupling
```

Kafka 不应该成为：

```text
Approval Truth
Mission Truth
Ticket State Truth
```

Final Gate：

```text
KAFKA = NOT_REQUIRED_FOR_BUSINESS_CORRECTNESS
```

------

# 四十五、为什么当前没有 Temporal

当前状态主要是：

```text
PostgreSQL durable state
+
row lock
+
CAS
+
explicit application transitions
```

复杂度仍可控。

如果以后大量增加：

```text
Timer
Signal
Cross-day retry
Lease recovery
Compensation
复杂 continuation
```

再评估 Temporal。

正确表达：

> 当前没有试图自己造通用 Workflow Engine。

------

# 四十六、Stage8 State Machine

Final Gate 当前状态：

```text
CREATED
→ CONTEXT_READY
→ AWAITING_REVIEW

AWAITING_REVIEW
→ READY_FOR_EXECUTION
→ CONTEXT_READY
→ CANCELLED

READY_FOR_EXECUTION
→ WAITING_FOR_RESOURCE
→ EXECUTING
→ CANCELLED

WAITING_FOR_RESOURCE
→ READY_FOR_EXECUTION
→ CANCELLED

EXECUTING
→ COMPLETED
→ TRIAGING
→ FAILED
→ CANCELLED

TRIAGING
→ EXECUTING
→ COMPLETED
→ FAILED
→ CANCELLED
```

Terminal：

```text
COMPLETED
FAILED
CANCELLED
```

Final Gate 未发现 canonical main path 的 dead state。

------

# 四十七、整个 Stage8 的 Owner / Truth 必须会背

| 对象               | Truth / Owner                         |
| ------------------ | ------------------------------------- |
| Mission            | Stage8 MissionService + PostgreSQL    |
| Agent Run          | RunCoordinator / Runtime              |
| TestPlan           | Stage8 Planning + PostgreSQL          |
| Business Review    | BusinessReviewService                 |
| Case               | GeneratedCaseArtifact + Case Platform |
| Environment 状态   | Environment Platform                  |
| Execution Job      | Stage8ExecutionService                |
| SUCCESS / FAILED   | Provider result + Parser              |
| Failure Evidence   | Backend reconstruction                |
| Triage             | claim winner + Specialist             |
| Tool Approval      | DurableApprovalService                |
| TicketContinuation | TicketContinuationService             |
| ticket_id / URL    | Ticket Platform                       |

------

# 四十八、你在面试中可以把 Stage8 分成四层

## 第一层：Agent Reasoning

```text
Feature Understanding
Risk Analysis
Test Planning
Failure Triage
CI Guardian
```

------

## 第二层：Application Workflow

```text
Mission
Review
Case binding
Environment selection
External job
Ticket continuation
```

------

## 第三层：Runtime Safety

```text
Typed Validation
Tool Governance
HITL
Claim
CAS
Side Effect State
UNKNOWN
```

------

## 第四层：Existing Business Platforms

```text
Case Platform
Environment Platform
Execution Platform
Ticket Platform
```

这个分层特别适合回答：

> 你这个项目的架构是什么？

------

# 四十九、Stage8 最典型的真实 Bad Case

## Bad Case 1 — Review A 执行 Plan B

通过：

```text
subject/version/digest
```

阻断。

------

## Bad Case 2 — caller 自己传 case_path

已经删除 canonical path。

只允许：

```text
generated_case_artifact_id
```

------

## Bad Case 3 — Environment 查询 FREE，但 start 时 BUSY

增加 pre-start recheck。

仍存在无 reserve 的 race，明确接受。

------

## Bad Case 4 — external start 成功，本地 response 丢失

进入：

```text
UNKNOWN
```

不重新选环境启动。

------

## Bad Case 5 — 用户自己 POST FAILED

canonical route 已移除。

正式结果由 provider observation + parser 决定。

------

## Bad Case 6 — 只解析日志前 16 KiB

可能漏掉末尾 FAILED。

修成：

```text
parse enough data
persist bounded excerpt
```

------

## Bad Case 7 — 两个 FAILED observation

最终：

```text
one terminal result
one triage
```

------

## Bad Case 8 — Approval A 执行 Draft B

通过：

```text
snapshot
digest
invocation binding
```

fail closed。

------

## Bad Case 9 — Approved Tool 永远执行不了

WP10 真实发现：

```text
PREPARED durable invocation
execution_claim_id = NULL
```

后续绑定 claim 被 immutable identity 拒绝。

修成同一 APPROVED binding 在 PREPARED 状态允许一次 claim binding。

------

## Bad Case 10 — Approval 已建，但 Continuation 落库失败

Final Gate 真正发现：

```text
retry
→ random runtime identity
→ Approval B
```

最后把：

```text
run_id
invocation_id
approval_id
```

稳定绑定到 execution identity。

同 Draft 重放复用 Approval A。

不同 Draft：

```text
binding mismatch
→ fail closed
```

------

# 五十、Stage Final Gate 为什么有价值

如果只看每个 WP：

```text
WP0 PASS
WP1 PASS
...
WP10 PASS
```

仍然不能证明整个系统能跑。

Final Gate 真正发现了三个组合问题：

```text
1. Web Demo 还是旧 WP3 DTO
2. Stage8 Approval 与通用 Approval HTTP ownership 不兼容
3. PRODUCT replay 可能产生 Approval B
```

说明：

> **局部正确 ≠ 组合正确。**

这是 Stage8 很值得讲的工程经验。

------

# 五十一、当前 7 个 Accepted P1

这七个一定要记住。

## 1. Orphan Case

Case Platform 已生成。

但 provider 返回以后：

```text
Plan changed
```

AgentCore 不保存 stale artifact。

外部平台可能留下 orphan Case。

------

## 2. Environment race

没有 reserve API。

```text
recheck
→ start
```

之间存在 race。

------

## 3. UNKNOWN reconciliation

External execution 结果不确定以后：

```text
没有自动 reconciliation
```

------

## 4. Automatic Result Observation

现在：

```text
observe_once()
```

需要外部 trigger。

没有常驻 worker。

------

## 5. TicketContinuation PROCESSING recovery

```text
READY → PROCESSING
→ worker crash
```

没有 lease/reaper。

------

## 6. Post-COMMITTED writeback repair

```text
Ticket created
Tool COMMITTED
→ process crash
→ business writeback missing
```

目前不能自动修复。

------

## 7. Stage8 Object-level RBAC

当前有认证。

但 Mission / Review / Continuation 没有完整企业级对象权限。

------

# 五十二、P2

当前四个 P2：

```text
execution-list retention / cleanup

Feature Understanding / Risk
没有独立历史版本表

malformed terminal log
没有独立 parse-error terminal state

Web Demo
不会自动跑 observer / continuation worker
```

------

# 五十三、为什么不是 Production Ready

主要缺：

```text
真实企业 connector + auth

Stage8 object-level RBAC

Environment reserve

automatic observer worker

UNKNOWN reconciliation

Continuation lease/reaper

post-COMMITTED repair

capacity/load test

SLA/SLO

retention cleanup

HA worker

企业日志 parser
```

所以：

```text
Interview Ready = YES
Demo Ready = YES
Production Ready = NO
```

这个口径不要改。

------

# 五十四、外部平台当前应该怎么描述

正确：

> **Real contract design + deterministic mock adapter。**

错误：

> “我们已经接入了公司真实测试平台。”

Stage8 当前验证的是：

```text
Contract
Authority
Failure semantics
Integration architecture
```

不是企业真实生产网络联调。

------

# 五十五、30 秒项目回答

> Stage8 是我在 AgentCore Runtime 上做的一条通信测试工程 Workflow。Feature 先经过理解、风险分析和 TestPlan，再通过 version/digest 做人工 Review；之后统一走 Tool Runtime 调 Case、环境和测试执行平台，后端持久化长任务 Job，再从 Provider 观察结果并用普通 Parser 判断成功失败。失败后重建证据交给 Triage Agent，PRODUCT 问题才进入 Tool Approval，批准后通过 PostgreSQL durable continuation 恢复同一个 ToolInvocation 去创建 Ticket。Agent 主要做模糊理解和归因，状态、版本、审批和外部副作用都由后端控制。

------

# 五十六、2 分钟项目回答

> Stage8 的业务背景是通信测试工程。实际公司里 Case Generation、环境管理、测试执行和 Ticket 系统本来就已经存在，所以我没有重新做这些系统，而是在 AgentCore Runtime 上加了一层 Agentic workflow，把这些平台串起来。
>
> 入口是 FeatureTestMission，它和一次 Agent Run 是分开的。Mission 可能持续几小时甚至几天，但 Feature Understanding、Risk Analysis、Test Planning 等 Agent Run 都是 bounded 的。TestPlan 做 canonical digest，环境要求也在 digest 里，然后 Business Review 精确绑定 subject、version 和 digest，避免批准了旧计划却执行新计划。
>
> Review 之后通过统一 Tool Runtime 调 Case Platform，返回的 Case ID 和 Path 保存为 GeneratedCaseArtifact，后续执行只能引用 artifact，caller 不能自己传路径。环境方面 Agent 只表达 requirements，FREE/BUSY 和 IP 必须来自 Environment Platform，后端 deterministic filter，start 前再 recheck，没有资源就 WAITING。
>
> 外部测试可能跑几个小时，所以先持久化 PENDING ExternalExecutionJob 再调用 Test Platform，拿到 execution ID 以后当前 Run 就结束。之后 observe_once 查询平台，SUCCESS/FAILED 用普通 Parser 解析固定日志，不交给 LLM。
>
> 失败时后端从 Job、Plan、Case、Environment 和 Log 重建 FailureEvidencePackage，再让 Triage Agent 判断 PRODUCT、TEST_DATA、ENVIRONMENT 等类型。PRODUCT 不直接提单，而是生成 TicketDraft 和 Tool Approval。批准后由 PostgreSQL TicketContinuation 独立续跑，先拿 business claim，再走原 Tool Runtime 的 execution claim，恢复同一个 approved ToolInvocation 创建 Ticket。
>
> 对 create_ticket 这种非幂等操作，如果外部可能成功但 response 丢失，我会记录 UNKNOWN，不自动 retry，避免重复提单。Stage8 的 PRODUCT 主闭环已经通过 Final Gate 和 89 个 Stage8 测试，但外部平台目前还是 contract + deterministic mock，真实 connector、RBAC、自动 worker、reconciliation 和 HA recovery 还是生产缺口。

------

# 五十七、高频工程问题

## 1. 为什么不用一个 Agent Run 跑到底？

长任务会跨人工等待和外部执行，不应该绑 Run deadline。

------

## 2. 为什么需要 Mission？

提供长生命周期业务状态。

------

## 3. 为什么 Review 要绑定 digest？

防止旧审批执行新计划。

------

## 4. 为什么 environment_requirements 也进 digest？

因为环境要求属于 TestPlan 业务内容。

------

## 5. 为什么 Agent 不直接选机器？

机器当前状态属于外部平台事实。

------

## 6. 为什么没有环境不自动降级？

会改变 TestPlan 语义。

------

## 7. 为什么不 Redis lock 环境？

AgentCore 不是 Environment Authority。

------

## 8. 为什么不能传 case_path？

会绕过 Case artifact / Review / path safety。

------

## 9. 为什么先写 PENDING Job？

防止外部已启动但本地没有记录。

------

## 10. 为什么长任务不用 Agent Run 等？

Run 与业务任务生命周期不同。

------

## 11. 为什么结果不是 callback body 的 SUCCESS？

用户不能自己拥有执行结果 Truth。

------

## 12. 为什么固定日志不用 LLM？

确定性代码更准确、稳定。

------

## 13. 为什么 Triage 又需要 LLM？

失败根因分类包含模糊推断。

------

## 14. 为什么大日志只存一部分？

完整日志属于原始平台；AgentCore只保存分析所需 evidence。

------

## 15. 为什么 parse 不能也只看 16KiB？

可能截掉末尾终态。

------

## 16. 为什么 Ticket 要 Approval？

创建 Issue 是真实外部副作用。

------

## 17. Approval 以后为什么不直接执行？

Approval 和业务执行生命周期应该解耦。

------

## 18. 为什么需要 Continuation？

跨请求保存后续动作状态。

------

## 19. 两个 Worker 怎么办？

Business CAS + Tool execution claim。

------

## 20. Ticket timeout 为什么不能 retry？

可能已经创建。

------

## 21. Exactly-once 做到了吗？

没有 generic guarantee，只做 exactly-once-like safety。

------

## 22. Kafka 为什么没加？

当前 correctness 不需要 Kafka。

------

## 23. Temporal 为什么没加？

当前状态复杂度 PostgreSQL/CAS 足够。

------

## 24. TEST_DATA 为什么没自动修？

新 Feature 的正确语义数据未必可推导。

------

## 25. CI Guardian 是不是会自动判断哪个 Commit 有问题？

不会，只生成候选 correlation 和 hypothesis。

------

# 五十八、最尖锐问题

## “你不就是调用几个已有平台 API 吗？”

> API 调用本身确实不难。真正复杂的是 TestPlan 版本绑定、Case Authority、资源竞争、长任务状态、人工审批、重复请求、外部 timeout 和 crash 后如何避免重复副作用。Stage8 主要解决的是这些跨平台 correctness 问题。

------

## “为什么不直接 LangGraph？”

> Agent graph 只能解决部分 reasoning 编排。Review binding、PostgreSQL Truth、Tool claim、UNKNOWN、长任务 Job 和外部副作用不能交给 graph framework 自动解决。

------

## “你是不是自己造了低配 Temporal？”

> 当前只是少量明确业务状态和 CAS，没有做通用 timer、signal、retry、compensation engine。如果跨日 timer、lease recovery 和复杂 continuation 大量增加，我会重新评估 Temporal。

------

## “没有接真实企业平台，怎么叫真实项目？”

> 我会明确说当前是 production-oriented contract 和 failure semantics，用 deterministic mock 做可重复验证，不会说已经线上接入企业系统。项目真实的部分是 Runtime、业务状态、Authority、审批和失败模型。

------

## “100 人能不能扛？”

> 没做 load test，所以我不会给 QPS 或 SLA 承诺。目前有 PostgreSQL durable state、CAS、bounded concurrency 和 stateless API 的扩展基础，但容量需要实测。

------

## “为什么 Kafka 都没用？”

> 因为 PostgreSQL 已经负责 durable truth。Kafka 如果现在只是为了展示技术栈，会引入第二套状态来源。后续它更适合做 wakeup 和 worker decoupling。

------

## “没有 Agent，系统还剩什么？”

> Mission、Review、Case Authority、环境选择、External Job、Parser、Approval、Claim、Continuation 都还成立。Agent 主要提升 Feature 理解、风险分析、TestPlan 和 Failure Triage 这些模糊认知环节。

------

# 五十九、Stage8 的面试重点，不是功能数量

真正有价值的是这些工程决策：

```text
Mission != Run

Proposal != Truth

Review != Approval

Approval != Execution Claim

Agent requirement != Provider status

TicketDraft != Ticket

Provider terminal != Business result

Parse boundary != Persist boundary

Business Claim != Tool Claim

Timeout != Failure

UNKNOWN != Retry

Local state != External truth
```

这几组对比几乎能覆盖 Stage8 大部分追问。

------

# 六十、Stage8 最应该记住的十句话

1. **Mission 管长业务生命周期，Agent Run 只管一次 bounded reasoning。**
2. **Agent 可以提出 TestPlan，但 Review、版本和状态必须由后端持有。**
3. **批准的是精确的 subject/version/digest，不是“差不多这份计划”。**
4. **Case、环境状态、执行结果和 Ticket ID 都属于外部平台事实，LLM 不能创造。**
5. **能用确定性代码判断的事情，就不要让 LLM 判断。**
6. **外部副作用前先持久化本地意图，否则 crash 后系统可能连自己做过什么都不知道。**
7. **Approval 只是授权，Execution Claim 才是一次真实执行权。**
8. **Business Claim 控制谁处理流程，Tool Claim 控制谁真正产生副作用。**
9. **对于非幂等外部动作，结果不确定时宁可 UNKNOWN，也不能盲目重试。**
10. **Stage8 的核心不是调用几个 API，而是把 Agent reasoning 和确定性的业务 Authority、安全执行、长任务恢复边界分开。**

------

# 六十一、最终 Truth / Owner / Completion Boundary

## 已真实实现

```text
FeatureTestMission

Mission / Agent Run separation

Feature Understanding
Risk Analysis
Test Planning

typed / evidence-bound Specialist

TestPlan persistence
version / digest Review binding

GeneratedCaseArtifact

environment-aware deterministic selection

WAITING_FOR_RESOURCE

backend-controlled execution-list.xls

durable ExternalExecutionJob

async external start

Provider Observation

deterministic result parser

bounded log persistence

FailureEvidencePackage

Failure Triage

PRODUCT TicketDraft

Tool Approval

durable TicketContinuation

Business Claim

Tool Execution Claim

Ticket result writeback

CI clustering/history/change candidate correlation

Web Demo canonical flow
```

------

## 外部系统目前是 Mock / Contract

```text
Case Platform

Environment Platform

Test Execution Platform

Ticket Platform
```

准确说法：

```text
typed contract
+
deterministic mock adapter
```

------

## Partial

```text
TEST_DATA remediation

CI automation
```

------

## 尚未生产完成

```text
真实企业 connectors/auth

Stage8 object-level RBAC

Environment reservation

automatic observation worker

UNKNOWN reconciliation

PROCESSING lease/reaper

post-COMMITTED writeback repair

HA worker

load test

SLA/SLO

retention cleanup

企业日志 parser
```

------

# 六十二、Stage8 最终面试定义

> **Stage8 是运行在 AgentCore 统一 Runtime 上的一条 PostgreSQL-backed Agentic Test Engineering Workflow。它把 Feature 理解、风险分析、TestPlan、业务 Review、Case 生成、环境决策、外部执行、结果观察、Failure Triage 和 PRODUCT Ticket continuation 串成完整业务链；LLM 负责提议和归因，Application / Runtime 负责 durable identity、Authority、版本绑定、状态、Approval、Claim、Idempotency 和不确定副作用。**

完成边界：

```text
Interview-ready
Deterministic mock demo-ready
PRODUCT main loop closed
Not enterprise production-ready
```