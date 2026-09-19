# Stage8-WP5 — Minimal Web Demo & Agent Toolbox

## 1. 名词 / 概念速览

**展示层（Presentation Layer）**
负责触发后端能力、读取结果和展示状态，不拥有业务 Truth。

**智能体工具箱（Agent Toolbox）**
用于独立调用 Feature Understanding、Risk Analysis、Test Planning、Failure Triage、CI Guardian 等 Specialist 的演示入口。

**契约审计（Contract Audit）**
逐条核对前端 fetch 的 URL、Method、Payload、Response 与 FastAPI/Pydantic Contract 是否一致。

**权威边界（Authority Boundary）**
规定 Mission、Review、Evidence、Triage、CI Analysis 等事实到底由哪个后端组件持有。

**薄 UI（Thin UI）**
前端只 trigger / read / render，不复制后端 Domain Logic。

**安全渲染（Safe Rendering）**
外部或模型文本通过 `textContent` 等方式写入 DOM，避免不可信内容被解释为 HTML。

**Tool Approval Pending**
表示危险 Tool 已生成持久化审批请求，但真实外部 Side Effect 尚未发生。

**Business Review**
业务人员对 TestPlan 等业务 Artifact 的认可，与 Tool Approval 是不同 Authority。

------

# 2. 本 WP 解决什么业务问题

WP0~WP4 已经有完整后端能力：

```text
Feature
→ Risk
→ TestPlan
→ Business Review
→ Execution
→ Callback
→ Failure Triage
→ CI Guardian
```

但如果只有 API 和测试，面试现场很难在几分钟内把整个系统讲清楚。

所以 WP5 的目标不是“开发一个正式前端产品”，而是：

> 做一个最小 Web Demo，把已有真实后端能力可视化出来。

最终页面覆盖：

```text
Mission Workflow
Agent Toolbox
CI Guardian
```

并且全部走真实 Stage8 API，没有另外造一套 Demo Backend。

------

# 3. 工程构建方法问答

## 为什么不用 React / Vue？

因为当前目标是面试 Demo，不是正式前端产品。

真正需要的是：

```text
能打开
能点
能调用真实后端
能展示状态
```

而不是：

```text
大型组件体系
复杂状态管理
前端构建链
```

所以最终采用：

```text
FastAPI
+
Static HTML
+
Vanilla JS fetch
+
CSS
```

这让前端本身几乎不增加新的工程维护面。

------

## 为什么 UI 不能自己推进 Mission 状态？

因为 Mission Truth 的 Owner 仍然是：

```text
MissionService
```

错误：

```javascript
mission.status = "COMPLETED"
```

正确：

```text
UI
→ backend mutation API
→ MissionService
→ response
→ UI render
```

如果前端能自己改 Mission 状态，就相当于绕过：

```text
CAS
Transition Rule
Persistence
```

前面 WP0 做的 Authority 全失效。

------

## 为什么前端不能自己计算 Regression / Risk / Correlation？

这些都是业务 Truth 或分析结果。

例如：

```text
current_count > previous_count
```

前端当然可以算，但不能因此成为：

```text
regression_candidate Authority
```

正确：

```text
Backend calculates
→ API returns
→ UI displays
```

同理：

```text
Risk
Triage classification
Change correlation
```

都不能在 JS 重新实现。

Final Gate 已确认前端没有推进 Mission，也没有自己计算 Risk / Regression / Correlation / Root Cause。

------

## 为什么 Agent Toolbox 不能直接调 Provider？

Toolbox 的目的是展示：

> Specialist 可以独立调用。

但“独立调用”不等于：

```text
Browser
→ Provider API
```

正确仍然是：

```text
Browser
→ Specialist API
→ SpecialistAgentApplicationService
→ CoordinatedRuntimeFactory
→ Agent Adapter
→ AgentRouter
→ ModelInvocationRouter
```

Final Gate 已确认：

```text
TOOLBOX_DIRECT_PROVIDER = NO
```

------

## 为什么 CI Guardian 的独立 API 被删除？

这是 WP5 最有价值的真实 Bad Case。

Luna 初版新增：

```text
POST /api/stage8/agents/ci-guardian/run
```

并允许 caller 直接传：

```text
clusters
comparisons
change candidates
evidence IDs
```

这意味着 caller 重新获得了 WP4 已经收回的：

```text
Cluster Authority
Change Authority
Evidence Authority
```

等于破坏：

```text
CI Run
→ deterministic clustering
→ history compare
→ change candidate selection
→ Guardian
```

最终删除这个 raw route。

现在 Toolbox 只传：

```text
ci_run_id
```

然后进入：

```text
CIGuardianApplicationService.analyze(ci_run_id)
```

由后端重新构建全部 Authority。

------

## 这和 WP3 Failure Triage 的问题有什么相似？

WP3 也出现过：

```text
Independent Failure Triage API
→ caller submits arbitrary evidence
```

后来修成：

```text
caller submits execution_id
→ backend reconstructs FailureEvidencePackage
```

WP5 的 CI Guardian 是同一个原则：

> **独立调用入口不能等于把 Evidence Authority 交给 caller。**

------

## 为什么 Failure Triage Toolbox 只接受 execution_id？

因为：

```text
execution_id
```

是 durable business reference。

后端可以据此重建：

```text
ExecutionResult
Case
Environment
Logs
TestPlan
```

如果浏览器直接提交任意 Evidence JSON，用户就可以构造不存在的日志和 Case。

最终 WP5 仍保持 Failure Triage 只接受真实 `execution_id`。

------

## 为什么 Business Review 和 Tool Approval 必须在 UI 上分开显示？

两者批准对象不同。

### Business Review

批准：

```text
TestPlan
```

表示：

> 这份测试方案可以进入执行阶段。

### Tool Approval

批准：

```text
create_ticket Invocation
```

表示：

> 允许这一次外部 Side Effect。

如果 UI 都显示成：

```text
Approved
```

用户很容易误以为：

> TestPlan 批准以后所有外部动作都能执行。

所以 WP5 明确显示：

```text
Business Review
Tool Approval Pending
```

------

## 为什么 `APPROVAL_REQUIRED` 时不能显示 Ticket Created？

因为：

```text
TicketDraft
```

已经存在，

但：

```text
External Ticket
```

还没有创建。

当前真实状态是：

```text
create_ticket
→ Governance
→ APPROVAL_REQUIRED
→ durable approval_id
```

所以页面显示：

```text
Tool Approval Pending
```

而不是：

```text
BUG-001 created
```

Final Gate 明确验证了这一 Truth Boundary。

------

## 为什么 callback 后不让前端再调一次 Failure Triage？

Luna 初版前端在 FAILED callback 后，又主动调用了一次 Triage API。

但 WP3 callback 本身已经：

```text
persist result
→ trigger Triage
```

前端再调一次会造成：

```text
duplicate triage
```

严重时还可能再次进入 non-idempotent Ticket 流程。

最终修成：

```text
callback
→ backend performs triage
→ callback returns latest job
→ UI renders job.triage
```

------

## 为什么 PRODUCT / TEST_DATA 按钮要写 “Like Failure”？

因为前端只能构造一种类似：

```text
product-like logs/result
```

但最终分类 Authority 是 Failure Triage Agent。

不能因为用户点：

```text
Submit PRODUCT Failure
```

就让 UI 假装结果一定是 PRODUCT。

所以改成：

```text
Product-like Failure
Test-data-like Failure
```

然后展示真实后端分类。

------

## 为什么 UI 需要处理 JWT？

因为现有：

```text
/api/*
```

已经要求 Bearer JWT。

如果：

```text
GET /stage8
```

能打开，

但所有 fetch 都不带 Authorization：

```text
所有按钮 → 401
```

页面实际上不可用。

WP5 没有为了 Demo 去关闭 Auth，而是增加一个 Token 输入，由统一 fetch helper 添加：

```text
Authorization: Bearer ...
```

Token 只留在页面内存，不持久化。

------

## 为什么不能为了 Demo 绕过 Auth？

因为：

```text
Demo convenience
```

不能成为降低 Production Boundary 的理由。

错误：

```text
if path == /stage8:
    skip auth
```

正确：

```text
UI
→ follows existing authentication contract
```

这体现：

> Presentation Layer 必须适配现有安全边界，而不是让安全边界适配 Demo。

------

## 为什么 Token 不存 localStorage？

当前只是内部 Demo。

Token 只需要在当前页面使用。

存 localStorage 会扩大：

```text
XSS
persistent credential exposure
```

风险。

所以：

```text
memory only
refresh → re-enter
```

足够。

------

## 为什么一定要检查 `innerHTML`？

因为页面展示大量不可信内容：

```text
Feature
Logs
LLM Result
Commit Summary
TicketDraft
```

如果：

```javascript
element.innerHTML = modelResult
```

那么外部内容可能直接变成 DOM。

最终页面全部使用：

```javascript
textContent
```

并确认没有：

```text
innerHTML
outerHTML
insertAdjacentHTML
document.write
```

等危险 sink。

------

## Prompt Injection 和 HTML Injection 有什么区别？

Prompt Injection：

```text
恶意文本影响 LLM 行为
```

HTML Injection / XSS：

```text
恶意文本影响浏览器 DOM / JS
```

例如日志：

```text
Ignore previous instructions
```

主要属于 Prompt Injection 风险。

日志：

```html
<script>alert(1)</script>
```

如果被 innerHTML 渲染，则变成前端安全问题。

两者需要分别防守。

------

## 为什么静态目录不能依赖当前工作目录？

错误：

```python
Path("static/stage8")
```

假设进程一定从 repo root 启动。

如果服务从其他 working directory 启动，就找不到资源。

最终使用：

```python
Path(__file__).resolve().parent / "static" / "stage8"
```

因此与 CWD 无关。

------

## 为什么 CI Demo 不能固定 ci_run_id？

WP4 已冻结：

```text
ci_run_id immutable
duplicate ingest rejected
```

如果 UI 每次都创建：

```text
CI-DEMO-PREV
CI-DEMO-CURRENT
```

第一次演示成功，第二次就冲突。

所以 WP5 每次生成 suffix：

```text
CI-DEMO-xxxx-PREV
CI-DEMO-xxxx-CURRENT
```

既保持 Backend immutability，又保证 Demo 可重复运行。

------

## 为什么不修改后端允许重复覆盖 CI Run？

因为：

> UI Convenience 不能改变 Domain Contract。

正确是前端适配 immutable CI Run。

而不是为了 Demo：

```text
PUT existing CI Run
overwrite snapshot
```

破坏 WP4 的 provenance。

------

# 4. 30 秒项目回答

> Stage8 最后我补了一个最小 Web Demo，不是重新做测试管理平台，而是用 FastAPI 静态页面和 Vanilla JS 把已有的 Mission、Specialist Agent、Execution、Failure Triage 和 CI Guardian 串起来。前端只负责 trigger、read 和 render，Mission 状态、Risk、Triage、Regression 等 Truth 全部还是后端持有。这里还修过一个比较典型的问题：最开始为了 Agent Toolbox 给 CI Guardian 开了一个 raw API，caller 可以自己传 cluster、change 和 evidence，实际上绕过了 WP4 的 Authority，最后删掉改成只传 ci_run_id，由后端重新构建所有分析输入。另外页面严格区分 Business Review 和 Tool Approval，对模型和日志输出全部用 textContent 安全渲染。

------

# 5. 2 分钟项目回答

> Stage8 前面已经完成完整后端链路，但是只有 API 和测试不太适合面试现场展示，所以最后做了一个 Minimal Web Demo。
>
> 技术上我刻意没有上 React 或 Vue，而是 FastAPI 静态 HTML、Vanilla JS 和 CSS，因为目标不是前端工程，而是让已有 AgentCore 后端能力可操作、可观察。
>
> 页面主要分三块。第一块是 Mission Workflow，可以创建 Feature Mission，运行 Feature Understanding、Risk Analysis、Test Planning，做 Business Review，再启动 External Execution、提交 Mock callback，并观察 Failure Triage。第二块是 Agent Toolbox，用来独立调用各个 Specialist。第三块是 CI Guardian，可以导入一组 previous/current CI，再展示 Cluster、Historical Comparison、Change Candidate 和 Guardian Finding。
>
> 这个阶段我比较重视 Presentation Layer 不要破坏 Backend Authority。比如 Luna 初版为了 Toolbox 新增了一个 CI Guardian raw endpoint，调用方可以直接传 clusters、change candidates 和 evidence IDs，这实际上绕过了前一阶段确定性聚类和 Evidence Authority，所以 Review 时把这个 route 删除了，Toolbox 只接受 ci_run_id，再走 `CIGuardianApplicationService.analyze()`。
>
> 另外 Failure Triage 也只接受 execution_id，不允许前端自造 Evidence。页面只展示 Backend 返回的 Mission、Triage、Regression 结果，不自己推导业务 Truth。
>
> 安全方面，现有 API 需要 Bearer JWT，所以 Demo 也遵守同一认证边界，没有为了展示去 bypass auth。外部日志和 LLM 输出统一通过 `textContent` 渲染，避免把不可信内容变成 HTML。
>
> 所以这个 WP 的定位就是：UI 可以很薄，但 Authority、Security 和 Backend Contract 不能因为是 Demo 就打折。

------

# 6. 高频追问 + 简答

## 你们前端为什么这么简单？

因为核心价值在 Agent Runtime 和测试业务闭环。

前端只需要：

```text
trigger
read
render
```

引入复杂 SPA 不增加当前面试价值。

------

## Agent Toolbox 和 Workflow 有什么区别？

Workflow：

```text
多个 Agent / Business Step 按真实 Mission 流程组合
```

Toolbox：

```text
单个 Specialist 独立调用
```

两者底层共用同一个 Specialist Runtime。

------

## UI 有没有自己的 Workflow？

没有。

最终：

```text
SECOND_WORKFLOW_IMPLEMENTATION = NO
```

完整业务流程仍然由后端 Stage8 Service 提供。

------

## UI 会直接访问 Mock Platform 吗？

不会。

最终：

```text
MOCK_PLATFORM_BYPASS = NO
```

Execution 等副作用仍然必须经过真实后端 Tool Runtime。

------

## CI Guardian 为什么不能像普通 Chat 一样输入一段 Prompt？

因为 CI Guardian 的输入不是自由聊天上下文。

它依赖：

```text
CI Run
Cluster
History
Change Candidates
Evidence
```

这些都有 Authority。

如果允许任意 prompt，就失去了可验证的分析边界。

------

## UI 里能看到 Ticket 吗？

当前能看到：

```text
TicketDraft
Tool Approval Pending
approval_id
```

但没有完整 Tool Approval UI。

所以不能说 Ticket 已经创建。

------

## 为什么没有做 Tool Approval 页面？

因为 WP5 目标是展示完整 Stage8 主链，不是建设完整 Approval Console。

现有后端 HITL 已在前面的 WP 中验证。

当前把 pending approval 正确展示出来已经够面试使用。

------

## 为什么没有 WebSocket？

当前：

```text
manual interaction + callback demo
```

已经足够。

WebSocket 会增加：

```text
connection lifecycle
reconnect
auth
state sync
```

当前没有必要。

------

## 页面刷新后状态能完全恢复吗？

不能。

当前明确：

```text
无完整 refresh recovery
```

这是 Accepted Limitation。

Backend Truth 还在，但 Browser UI 没有做完整 Dashboard Read Model。

------

## 为什么没有 Browser E2E？

当前 WP Gate 重点是：

```text
Contract Audit
ASGI targeted tests
Source Audit
```

没有引入 Playwright/Selenium。

这是明确 Completion Boundary，不代表正式生产 UI 已完成浏览器兼容性验证。

------

## 你们测试前端主要测什么？

重点不是像素级 UI。

而是：

```text
route reachable
static asset path
JS/FastAPI contract
authority boundary
safe rendering
backend targeted smoke
```

最终还针对 WP3 Triage 和 WP4 CI Guardian 跑了最相关节点。

------

# 7. Bad Case

## Real Bad Case 1 — CI Guardian Toolbox 绕过 Authority

初版：

```text
POST /api/stage8/agents/ci-guardian/run
```

caller 可以提交：

```text
clusters
comparisons
change candidates
evidence IDs
```

这等于：

```text
Browser
→ defines analysis truth
→ LLM
```

绕过 WP4 的：

```text
deterministic clustering
historical comparison
change candidate selection
```

最终直接删除 raw route，改为：

```text
ci_run_id
→ CIGuardianApplicationService.analyze()
```

------

## Real Bad Case 2 — 前端重复触发 Failure Triage

初版：

```text
callback FAILED
→ backend already triages

JS
→ calls Failure Triage API again
```

会导致重复推理。

更严重时可能：

```text
PRODUCT
→ create_ticket approval twice
```

最终 callback 返回最新 Job，UI 直接读取后端 `job.triage`。

------

## Real Bad Case 3 — 页面能打开，但所有 API 401

现有 middleware：

```text
/api/*
→ Bearer JWT required
```

如果静态页面 fetch 不带 Token：

```text
GET /stage8 → 200
所有按钮 → 401
```

这属于典型“页面测试通过但 Demo 实际不可用”。

最终增加内存态 Token 输入和统一 Authorization Header。

------

## Real Bad Case 4 — PRODUCT 按钮变成分类 Authority

如果页面按钮写：

```text
Submit PRODUCT Failure
```

再直接显示：

```text
PRODUCT
```

就相当于前端跳过 Failure Triage。

最终改成：

```text
Product-like Failure
```

真实分类以后端 Triage 为准。

------

## Real Bad Case 5 — Pending Approval 被显示成 Ticket Created

后端真实状态：

```text
create_ticket
→ APPROVAL_REQUIRED
```

如果 UI 显示：

```text
Ticket created successfully
```

就是 Presentation Layer 在篡改 Truth。

最终显示：

```text
Tool Approval Pending
approval_id
```

------

## Real Bad Case 6 — 固定 CI Demo ID 第二次演示失败

因为 WP4 中：

```text
ci_run_id immutable
```

固定 Demo ID 第二次运行会发生冲突。

正确修复不是放松 Backend Contract，而是：

```text
UI generates new demo suffix
```

------

## Hypothetical Bad Case — innerHTML 渲染日志

假设外部日志包含：

```html
<img src=x onerror=alert(1)>
```

如果：

```javascript
result.innerHTML = log
```

浏览器会解释 HTML。

当前统一：

```javascript
result.textContent = log
```

因此不可信文本只作为文本显示。

------

# 8. Truth / Owner / Completion Boundary

## Mission Truth

Owner：

```text
MissionService
```

UI 只展示。

------

## Business Review Truth

Owner：

```text
BusinessReview / Stage8 Application Service
```

UI 只发 approve / reject 请求。

------

## Agent Output Truth

Owner：

```text
SpecialistAgentApplicationService
+
existing AgentCore Runtime
```

Toolbox 不是 Model Owner。

------

## External Execution Truth

Owner：

```text
ExternalExecutionJob
Stage8ExecutionService
External Platform
```

UI 只展示 execution/job 状态。

------

## Failure Triage Truth

Owner：

```text
FailureTriage Specialist
+
authoritative execution-bound evidence
```

UI 不能指定 classification。

------

## CI Analysis Truth

Owner：

```text
CIGuardianApplicationService
stage8_ci_analysis
```

UI 只传 `ci_run_id`。

------

## Business Review vs Tool Approval

Business Review：

```text
批准 TestPlan
```

Tool Approval：

```text
批准具体危险 ToolInvocation
```

UI 已明确分开。

------

## Frontend Truth

Frontend 没有业务 Truth。

最终矩阵明确：

```text
FRONTEND_BUSINESS_AUTHORITY = NO
SECOND_WORKFLOW_IMPLEMENTATION = NO
MOCK_PLATFORM_BYPASS = NO
```

------

## Security Boundary

当前真实完成：

```text
Bearer JWT compatible

no hardcoded secret

Token memory-only

textContent safe rendering

no unsafe HTML sink
```

------

## WP5 真正完成

已实现：

```text
GET /stage8

Static HTML / JS / CSS

Mission Workflow Demo

Feature Understanding view
Risk Analysis view
TestPlan view

Business Review controls

Start Execution

Execution Job view

Mock Result Callback

Failure Triage display

Agent Toolbox

CI Guardian Demo

JWT-compatible fetch

safe rendering

repeatable Mission / CI demo

CWD-independent static path
```

并且：

```text
real existing APIs reused
no direct Provider
no MockPlatform bypass
no frontend business logic
```

Final Gate 全部确认通过。

------

## WP5 没完成

明确没有：

```text
React / Vue

frontend build system

WebSocket

browser E2E

full refresh recovery

complete Tool Approval operation UI

persistent browser session

dashboard charts

full production console
```

这些属于 Presentation Completion Boundary，不是 Backend 能力缺陷。

------

# 9. 本 WP 最应该记住的五句话

第一句：

> **Demo UI 可以薄，但不能因为是 Demo 就绕过 Backend Authority。**

第二句：

> **Agent Toolbox 可以提供独立入口，但不能把 Evidence / Change / Cluster Authority 重新交给 caller。**

第三句：

> **Business Review 和 Tool Approval 批准的是不同对象，UI 必须把两者明确区分。**

第四句：

> **前端只负责 trigger、read、render，Mission、Risk、Triage、Regression 等业务 Truth 都属于后端。**

第五句：

> **不可信 LLM / Log / External Data 既是 Prompt Injection 风险，也是浏览器 HTML Injection 风险，两个边界都要处理。**