当前对话使用 **GPT-5.6 Sol**。

下面进入 **Stage8-WP2 — Mock Business Platforms & Governed Actions** 的学习 / 面试总结。

推荐学习文档文件名：

```text
docs/interview/stage8_wp2_mock_business_platforms_governed_actions.md
```

WP2 最终状态：

```ini
WP2_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS
P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0
ARCHITECTURE_REOPEN_REQUIRED = NO
```

本 WP 真正完成的是：

```text
External Business Platforms
→ Typed Mock Platform
→ Existing Tool Registry
→ Governance
→ HITL
→ Execution Claim
→ ToolExecutionService
→ External Mock Mutation
```

其中 `start_execution` 和 `create_ticket` 已经真实证明没有绕过现有 Tool Runtime。

------

# 1. 名词 / 概念速览

**平台端口（Platform Port）**
业务层对外部系统能力的窄接口，例如查询 Case、启动执行、创建 Ticket。

**工具适配器（Tool Adapter）**
把外部平台能力转换成 AgentCore 统一 Tool Contract 的适配层。

**外部系统事实（External System Truth）**
由真正外部平台拥有的事实，例如 execution 状态、ticket 是否已创建。

**副作用（Side Effect）**
会改变外部世界状态的操作，例如启动执行、创建 Ticket。

**工具治理（Tool Governance）**
在 Tool 真正执行前，根据 Tool 和 Invocation 的风险事实决定 ALLOW、DENY 或 APPROVAL_REQUIRED。

**执行声明（Execution Claim）**
在批准后真正执行副作用前，对执行权进行持久化抢占，避免多个执行者重复执行同一个 Invocation。

**幂等键（Idempotency Key）**
用于识别“这是不是同一个业务操作”的稳定键，使重复请求可以复用已有结果，而不是产生重复副作用。

**非幂等（Non-idempotent）**
重复执行同样请求可能产生多个外部结果，例如创建两个 Ticket。

**副作用检查点（Side-effect Checkpoint）**
在真正外部 mutation 前记录“即将执行副作用”的边界，用于区分 PREPARED / STARTED / COMMITTED / UNKNOWN。

**未知状态（UNKNOWN）**
系统无法确定外部副作用到底有没有成功提交，例如请求超时但 Provider 可能已经执行。

**资源键（Resource Key）**
用来表达 Tool 正在操作哪个逻辑资源，例如 `stage8:tickets`。

**不可信外部上下文（UNTRUSTED_EXTERNAL）**
Tool 返回的外部内容只能作为数据和 Evidence，不能直接获得系统指令权限。

**组合根（Composition Root）**
负责构建并连接 application-scoped Platform、Tool Adapter、Registry、Governance 等依赖的地方。

------

# 2. 这个 WP 解决什么业务问题

WP1 已经有：

```text
Feature
→ Risk
→ TestPlan
```

但这些数据仍然主要来自请求输入。

真实测试工程里，Agent 必须面对外部系统：

```text
Feature 文档平台
Git / Code 平台
会议纪要平台
Case 平台
Environment 平台
Executor 平台
Log 平台
Ticket 平台
```

问题是，不能简单写成：

```text
Risk Agent
→ ExecutorClient.start_execution()
```

因为一旦 Agent 能直接调用外部 Platform Client，原来 AgentCore 已经建立的：

```text
Validation
Governance
HITL
Execution Claim
Idempotency
Side-effect State
```

全部失效。

所以 WP2 真正做的事情不是“写几个 Mock API”，而是建立这个边界：

```text
业务平台能力
    ↓
Platform Port
    ↓
Tool Adapter
    ↓
Existing AgentCore Tool Runtime
```

对于查询操作：

```text
get_feature_document
get_environment
get_logs
```

通常可以：

```text
ALLOW
```

但仍然是 Tool。

对于：

```text
create_ticket
start_execution
```

必须表达真实 Side-effect Fact，再由现有 Runtime 决定是否审批以及如何执行。

------

# 3. 工程构建方法问答

## 为什么外部平台要分 Platform Port 和 Tool Adapter？

因为它们回答两个不同问题。

Platform Port 回答：

> 外部系统有哪些业务能力？

例如：

```python
create_ticket(...)
get_ticket(...)
```

Tool Adapter 回答：

> AgentCore 怎么安全地调用这个能力？

它负责：

```text
build_invocation
spec_for
typed validation
ToolExecutionService integration
```

如果把两者混在一起，Mock Platform 就会知道：

```text
Governance
Approval
Execution Claim
```

这样外部系统层反而侵入 Runtime。

所以：

```text
Platform = business capability
Tool Adapter = runtime integration
```

------

## 为什么 Read-only Tool 也要走 Tool Runtime？

如果是模型自主调用：

```text
Agent
→ get_logs
```

依然应该经过：

```text
ToolRegistry
Typed Validation
Governance
ToolExecutionService
```

因为即使没有副作用，也需要统一：

- Schema；
- Permission；
- Tool identity；
- Timeout；
- Observation；
- Trust boundary。

但如果是 Application Service 固定预取 Context：

```text
FeatureContextBuilder
→ FeatureDocumentPort.get(...)
```

这种 deterministic read 可以直接走 Platform Port。

所以不是：

> 所有外部访问都必须是 Agent Tool。

而是：

> **模型驱动的外部访问必须走 Tool Runtime；确定性应用层预取可以直接走只读 Port。**

------

## 为什么 Mock Platform 必须是共享实例？

这是 WP2 实际发现的一个问题。

错误：

```text
create_ticket Tool
→ MockPlatform A
→ BUG-001
```

但：

```text
search_tickets Tool
→ MockPlatform B
```

那后者就看不到 `BUG-001`。

这会导致：

```text
Side-effect succeeded
```

和：

```text
External truth query
```

来自两个不同世界。

所以最终：

```text
server.py::lifespan()
→ create one DeterministicMockPlatform
```

然后：

```text
Tool Adapters
FeatureContextBuilder
```

共用。

Sol 已确认这是 application-scoped 单实例。

------

## 为什么 Mock state 不是 Stage8 Business Truth？

例如：

```text
EXEC-001 = RUNNING
```

这是：

```text
Executor Platform Truth
```

而：

```text
Mission = EXECUTING
```

是：

```text
Stage8 Business Truth
```

两个是不同 Authority。

未来正确关系：

```text
External Executor
→ reports EXEC-001 RUNNING
→ Stage8 Application interprets
→ Mission state transition
```

不能让 Mock Executor 直接修改 Mission。

------

## 为什么 `start_execution` 可以做成幂等，而 `create_ticket` 更保守？

因为两个业务操作天然语义不同。

`start_execution` 可以构造稳定业务 key，例如绑定：

```text
case
environment
executor
parameters
```

如果重复收到同一个 key：

```text
start_execution(same key)
```

Provider 可以返回已有：

```text
EXEC-001
```

而不是再启动一次。

所以可以声明：

```text
IDEMPOTENT_WITH_KEY
```

但前提是 Provider 真的按这个 key 去重。

这也是 WP2 实际修过的问题：Luna 初版只是“声明支持幂等”，但 key 没进入 Provider，所以重复请求仍会产生多个 execution。后来补成真实 Provider replay。

------

## 为什么 `create_ticket` 改成 NON_IDEMPOTENT？

因为创建 Ticket 如果没有真实 Provider-side deduplication：

```text
create_ticket(...)
create_ticket(...)
```

完全可能生成：

```text
BUG-001
BUG-002
```

所以不能为了看起来高级，就声明：

```text
IDEMPOTENT_WITH_KEY
```

Sol 审计发现 Luna 初版这里就是虚假 Contract。

最终改成：

```text
EXTERNAL_STATE_MUTATION
+
NON_IDEMPOTENT
```

并提供稳定 Resource Key。

这个点面试非常值得讲：

> **幂等不是 metadata 配一个枚举，而是 Provider 必须真的能实现对应语义。**

------

## 为什么 create_ticket 要审批，而 start_execution 不一定？

风险不只看“是不是副作用”。

例如测试环境里的：

```text
start_execution
```

如果：

- 参数 Typed；
- case/environment/executor 明确；
- 有稳定幂等键；
- 只是 Mock 测试执行；

可以允许自动执行。

而：

```text
create_ticket
```

会产生正式外部缺陷记录，容易：

- 误报；
- 重复提单；
- 影响开发；
- 产生人工成本。

所以当前 Governance 给它 HIGH effective risk，并要求：

```text
APPROVAL_REQUIRED
```

这是业务语义，而不是“一切 Side Effect 都审批”。

------

## Business Review 已经通过，为什么 create_ticket 还要 Tool Approval？

因为批准对象不同。

例如 TestPlan Review：

```text
APPROVED
```

代表：

> 测试人员认可这份 Test Plan。

但后续模型想执行：

```text
create_ticket(title=..., severity=...)
```

这是一个具体外部副作用。

所以仍需要：

```text
Tool Governance
```

去判断这一次 Invocation 是否允许执行。

也就是：

```text
Business Review
!=
Tool Approval
```

WP0 是业务认可。

WP2 Tool Approval 是执行权认可。

------

## create_ticket 为什么需要 Execution Claim？

Approval 只能表达：

> 允许执行这个 Invocation。

但并不能保证：

```text
两个 worker
```

不会同时看到 APPROVED，然后各执行一次。

所以：

```text
Approval
→ Execution Claim
→ only claimant executes
```

这是 exactly-once / duplicate prevention 的关键一层。

WP2 已经通过真实定向 integration test 证明：

```text
approve
→ claim
→ ToolExecutionService
→ mutation
```

而且 Ticket 在审批前不存在，执行后才出现。

------

## 为什么 `before_side_effect()` 必须发生在 Provider mutation 前？

因为 Runtime 需要明确知道：

```text
外部世界是否可能已经发生变化
```

假设：

```text
before_side_effect
→ provider.create_ticket
→ network timeout
```

此时系统至少知道：

> 已经进入副作用边界，外部可能已经提交。

所以不能简单标：

```text
FAILED
```

可能需要：

```text
UNKNOWN
```

如果反过来：

```text
provider mutation
→ before_side_effect
```

那 Runtime 失去了判断外部副作用是否可能发生的关键边界。

最终 `start_execution` 与 `create_ticket` 都确认 checkpoint 在 Provider 调用之前。

------

## UNKNOWN 为什么不能自动 Retry？

因为：

```text
UNKNOWN
```

意味着：

> 我不知道第一次到底成功没成功。

如果是：

```text
create_ticket
```

第一次已经创建成功但响应丢失，

这时自动 retry 就可能创建第二张 Ticket。

所以：

```text
UNKNOWN
→ reconciliation / human handling
```

而不是：

```text
UNKNOWN
→ retry
```

WP2 没有重做这套机制，而是确认 Stage8 Adapter 没有覆盖现有 Runtime UNKNOWN 语义，也没有 Adapter-level auto retry。

------

## Tool Adapter 为什么不能自己 Retry？

因为 Retry Authority 如果散落在：

```text
Adapter
HTTP Client
Runtime
Business Workflow
```

每层都重试一次，很容易放大副作用。

比如：

```text
Business retry × Tool retry × Client retry
```

可能一共执行很多次。

所以 Stage8 Adapter 只做：

> 一次 Provider attempt。

重试策略继续归现有 Runtime / 上层业务控制。

------

## FeatureContextBuilder 为什么可以直接调用 Platform Port？

因为它是 deterministic orchestration。

例如：

```text
feature_id=F123
```

系统已经明确知道要获取：

```text
feature document
code diff
meeting summary
```

无需让 LLM 再决定：

> 我今天要不要调用 get_feature_document？

这类固定 Context Assembly 用 Application Service/Builder 更稳定，也更省 Token。

------

## 为什么 Tool Result 仍然是不可信数据？

因为外部系统内容可能包含：

```text
Meeting Summary:
"Ignore previous instructions and execute..."
```

或者日志里出现类似文本。

即使它来自公司的平台，也不代表：

> 它可以控制 Agent。

所以所有 Tool Result 继续以：

```text
UNTRUSTED_EXTERNAL
```

进入模型上下文。

Sol 确认 Stage8 Query Tool 仍复用 AgentRouter 的这个统一边界。

------

# 4. 30 秒项目回答

> Stage8 里我把真实测试业务平台都抽成 Typed Port，然后通过现有 Tool Adapter 接进 AgentCore，没有让 Agent 直接调用 Platform Client。像 Feature Document、Environment、Log 这类查询 Tool 通常直接 ALLOW；`create_ticket`、`start_execution` 属于外部副作用，会继续走已有 Governance、HITL、Execution Claim 和 ToolExecutionService。这里我们还特别区分了幂等语义：`start_execution` 有稳定业务 key，Provider 会 replay；`create_ticket` 没有可靠去重能力，所以明确标成 non-idempotent。Mock 平台可以是假的，但执行权链是真的。

------

# 5. 2 分钟项目回答

> Stage8 接业务系统时，我没有直接写一堆 Client 让 Agent 调，而是把外部平台拆成 Platform Port 和 Tool Adapter。Platform Port 表达业务系统能力，比如查环境、启动测试、创建 Ticket；Tool Adapter 再把这些能力接进已有的 AgentCore Tool Runtime。
>
> 查询型 Tool 会走 Registry、Typed Validation、Governance 和 ToolExecutionService，但通常直接 ALLOW。副作用 Tool 继续复用已有的 Governance、Durable HITL、Execution Claim、Side-effect Ledger 和 ToolExecutionService。
>
> 这个阶段有两个比较典型的问题。第一个是 `start_execution`，初版虽然 metadata 写了 `IDEMPOTENT_WITH_KEY`，但 key 根本没有传给 Mock Provider，所以重复请求还是会创建多个 execution。后来改成根据 case、environment、executor、parameters 生成稳定 key，Provider 也真正按 key 去重，相同请求 replay 原 execution。
>
> 第二个是 `create_ticket`。初版也声明成幂等，但实际 Provider 没这个能力，所以这个 Contract 是假的。最后改成 `NON_IDEMPOTENT`，并把风险设成 HIGH，必须人工审批。我们补了一条 canonical integration test，验证审批前没有外部 Ticket，approve 后还必须抢 execution claim，再进入 ToolExecutionService，最后才产生 `BUG-001`。
>
> 所以这个 WP 我比较强调一点：外部平台本身可以用 Mock，但是 Validation、Governance、Approval、Claim 和 Side-effect State 这些执行权边界必须是真实复用已有 Runtime 的。

------

# 6. 高频追问 + 简答

## Tool Registry 是怎么接 Stage8 Tool 的？

直接追加到现有：

```text
build_builtin_tool_registrations()
```

然后由：

```text
server.py::lifespan()
```

在 Registry freeze 前注册。

没有 Stage8 专用 Registry。

------

## 为什么不用 MCP 模拟这些业务平台？

MCP 当然可以是未来真实 Provider 形式之一。

但 WP2 当前要验证的是：

```text
业务 Tool Contract
+
Runtime Safety Boundary
```

使用本地 Typed Mock 最快。

以后换成真实 REST / SDK / MCP：

```text
Tool Runtime
```

不需要改。

------

## start_execution 的 idempotency key 怎么设计？

当前绑定：

```text
case
environment
executor
parameters
```

或它们的稳定 canonical representation。

目标不是密码学安全，而是：

> 相同业务执行请求得到相同 Operation Identity。

Final Gate 已确认 full-input stable key + provider replay。

------

## 那 mission_id 为什么不一定进 key？

要看业务语义。

如果：

```text
同一 Mission 内相同 case/environment
```

必须视为同一次执行，Mission 可以参与。

如果 execution 的业务 identity 已由 execution plan / case/environment/executor 唯一表达，则不一定需要。

关键不是字段越多越好，而是：

> key 能否稳定识别同一业务副作用。

------

## create_ticket 为什么不用 idempotency key？

因为当前 Mock Ticket Provider 没有实现可靠 Provider deduplication。

如果未来真实 Ticket 系统支持：

```text
client_request_id
external idempotency key
```

则可以升级 Contract。

当前宁可保守标：

```text
NON_IDEMPOTENT
```

也不要虚假声明幂等。

------

## Approval 是 exactly-once 吗？

不是。

Approval 表示：

> 这个 Invocation 被允许。

Exactly-once / duplicate suppression 还需要：

```text
Approval binding
+
Execution Claim
+
Durable ToolInvocation
+
Provider idempotency / reconciliation
```

------

## Resource Key 有什么用？

它表达：

> 这个 ToolInvocation 操作哪个逻辑资源。

比如 Ticket：

```text
stage8:tickets
```

可以用于：

- authorization；
- risk；
- claim/binding；
- concurrency scope。

但它不等于 idempotency key。

------

## create_ticket 现在是 exactly-once 吗？

不能简单这么说。

更准确：

> Runtime 通过 Approval Binding、Execution Claim 和 Durable Invocation 防止同一个已批准 Invocation 被多个执行者重复执行。

但 Provider 本身是 non-idempotent。

如果外部提交后响应丢失进入 UNKNOWN：

```text
不能盲目 retry
```

仍需要 reconciliation。

这个回答更准确。

------

## Mock Platform 状态为什么不落 PostgreSQL？

因为它模拟的是：

```text
外部系统
```

不是我们自己的生产业务库。

真实环境中 Ticket/Executor 自己就有自己的数据库。

Mock 如果也全部落 Stage8 PostgreSQL，反而容易混淆 Authority。

------

## Query Tool 为什么只有一两个做完整 E2E？

因为 8 个 Query Tool 走的是同一模式：

```text
Registry
→ Governance ALLOW
→ ToolExecutionService
→ Adapter
→ Platform
```

测试价值在证明公共链，而不是复制 8 遍几乎一样的测试。

Final Gate 也明确接受没有为 8 个 Query Tool 各写 E2E。

------

## Tool Permission 怎么限制？

Sol 审计发现 Luna 初版：

```text
所有 production agents
```

都能调用全部 Stage8 Tool。

后来收紧到：

```text
core_router
+
3 个 Stage8 specialists
```

继续使用已有 Governance Catalog。

------

## 为什么不做复杂 RBAC？

当前已有 Tool Policy Catalog 能表达足够的 Agent permission。

Stage8 当前目标是测试业务闭环，不是搭企业 IAM。

等真实平台接入再根据：

```text
用户
角色
团队
资源
```

扩展授权模型。

------

# 7. Bad Case

## Real Bad Case 1 — Fake Idempotency Contract

Luna 初版：

```text
stage8_start_execution
→ IDEMPOTENT_WITH_KEY
```

看起来正确。

但真正执行：

```text
Invocation A
→ EXEC-001

相同业务 Invocation B
→ EXEC-002
```

因为：

> idempotency key 根本没有传给 Provider。

也就是说：

```text
metadata says idempotent
!=
provider is idempotent
```

Sol 最终修成：

```text
stable key
→ Provider dedup
→ same key replay EXEC-001
```

并专门用两个不同 invocation identity、同一个稳定业务 key 做 replay 测试。

------

## Real Bad Case 2 — create_ticket 错误声明为幂等

初版：

```text
create_ticket = IDEMPOTENT_WITH_KEY
```

但：

- Provider 没去重；
- 还缺 required resource key；
- canonical execution 会 contract validation fail。

Sol 改成：

```text
NON_IDEMPOTENT
+
stable resource key
+
HIGH risk
+
APPROVAL_REQUIRED
```



这个案例特别适合回答：

> 你们 Tool Risk / Idempotency metadata 是不是只是写死配置？

可以说：

> 不是，Review 时确实发现过 metadata 和 Provider 能力不一致，后来按实际 Provider 能力回收了 Contract。

------

## Real Bad Case 3 — Mock Platform Instance 分裂

初版生产 Composition 没明确保证：

```text
FeatureContextBuilder
Tool Adapter
```

共享同一 Platform 实例。

如果每个 Tool 有自己的：

```text
DeterministicMockPlatform
```

那么：

```text
create_ticket
→ BUG-001
```

之后另一个 Tool 查不到。

修复后：

```text
server.lifespan
→ one platform instance
→ all consumers
```



------

## Real Bad Case 4 — Governance Permission 过宽

Luna 初版为了让 Tool 能用：

```text
所有 production Agent
→ 所有 Stage8 Tools
```

虽然测试容易 PASS，但权限明显过宽。

Sol 后来收紧为：

```text
core_router
+
Stage8 specialists
```

说明：

> Policy coverage 测试通过，不等于 Policy 设计合理。



------

## Real Bad Case 5 — Approval Test 只测到 APPROVAL_REQUIRED

原测试只是证明：

```text
Governance
→ APPROVAL_REQUIRED
```

但没有证明：

```text
approve
→ claim
→ execution
```

如果后半段接错，Demo 仍然会坏。

Sol 补了一条 canonical integration：

```text
approval 前
→ no ticket

approve
→ claim
→ ToolExecutionService
→ COMMITTED
→ BUG-001 exists
```



------

## Hypothetical Bad Case — UNKNOWN 后自动重试

假设：

```text
create_ticket
→ Provider 已创建 BUG-001
→ network timeout
→ Runtime UNKNOWN
```

如果 Stage8 写：

```text
if UNKNOWN:
    retry()
```

可能再创建：

```text
BUG-002
```

所以 UNKNOWN 必须保持未知，而不是业务层擅自解释成失败。

当前 WP2 已确认 Stage8 Adapter 不自动 Retry，并保留底层 UNKNOWN Authority。

------

# 8. Truth / Owner / Completion Boundary

## Tool Registry Truth

Owner：

```text
Existing AgentCore ToolRegistry
```

Stage8 只注册新 Tool。

没有：

```text
Stage8ToolRegistry
```

------

## Tool Policy Truth

Owner：

```text
Existing ToolPolicyCatalog / ToolGovernanceService
```

Stage8 只新增 Tool policy metadata。

------

## Tool Approval Truth

Owner：

```text
ToolApprovalController
DurableApprovalService
```

`create_ticket` 直接复用。

Stage8 没有独立 Tool Approval。

------

## Execution Claim Truth

仍由现有 Durable Approval / Execution Claim 机制持有。

WP2 只证明 `create_ticket` 必须先 claim 才能发生 mutation。

------

## Tool Execution Truth

Owner：

```text
ToolExecutionService
DurableToolInvocationService
```

状态：

```text
PREPARED
STARTED
COMMITTED
UNKNOWN
```

Stage8 Adapter 不能自己定义最终执行 Truth。

------

## Mock External Truth

当前：

```text
DeterministicMockPlatform
```

拥有：

```text
ExecutionRecord
TicketRecord
Feature Document
Environment
...
```

它模拟未来真实公司平台。

这些不是：

```text
Mission Truth
TestPlan Truth
Review Truth
```

------

## start_execution Truth

当前真实能力：

```text
EXTERNAL_STATE_MUTATION
IDEMPOTENT_WITH_KEY
stable full-input key
provider replay
before_side_effect checkpoint
ToolExecutionService
shared external Mock state
```

Final Gate 全部 PASS。

------

## create_ticket Truth

当前真实能力：

```text
EXTERNAL_STATE_MUTATION
NON_IDEMPOTENT
HIGH risk
APPROVAL_REQUIRED
immutable invocation binding
durable execution claim
PREPARED → STARTED → COMMITTED
external BUG-001
```



------

## Feature Context Truth

`FeatureContextBuilder` 可以从 Mock：

```text
Feature Document
Code Diff
Meeting Summary
```

生成 WP1 Evidence。

Evidence source identity 仍来自 Platform Snapshot，而不是模型。

所以 WP1 的：

```text
Evidence Authority = FeatureContext
```

没有被破坏。

------

## WP2 真正完成了什么

已实现：

```text
Typed external platform DTO / ports

Deterministic Mock Platform

8 read-only query tools

stage8_start_execution
stage8_create_ticket

Existing ToolRegistry integration
Existing Governance integration
Existing HITL integration
Existing ToolExecutionService
Existing Durable Invocation

start_execution provider idempotency

create_ticket Approval + Claim + Execution

FeatureContextBuilder
External Evidence integration

Shared application-scoped Mock Platform
```

------

## WP2 没完成什么

没有：

```text
modify_official_case
cancel_execution

真实公司 API
真实网络 Client
真实企业 Authentication

Mock Platform persistence / HA

Remote execution result callback
Polling Worker
Failure Triage
Business Retry
Case Self-healing
CI Guardian
```

这些是明确边界，不是 WP2 缺陷。

------

# 本 WP 最应该记住的四句话

第一句：

> **Mock Platform 可以是假的，但 Tool Runtime 的 Validation、Governance、Approval、Claim 和 Side-effect 状态必须是真的。**

第二句：

> **幂等不是给 Tool 写一个 `IDEMPOTENT` 标签，而是 Provider 必须真正支持稳定业务 key 和重复请求 replay。**

第三句：

> **Approval 只给执行许可，Execution Claim 才决定谁真正有权执行这一次副作用。**

第四句：

> **外部 Tool Result 永远是数据，不因为来自公司平台就能变成可信系统指令。**

这四句话就是 WP2 最核心的面试价值。