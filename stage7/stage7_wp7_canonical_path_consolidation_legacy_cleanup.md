# Stage7-WP7 — Canonical Path Consolidation & Legacy Compatibility Debt Cleanup

## 一、本 WP 到底解决了什么问题

WP7 不是新增功能，而是在 Stage7 Final Gate 之后做一次：

> **Canonical Path Consolidation + Legacy Compatibility Debt Cleanup**

也就是把 Stage1～Stage7 历史上为了：

```text
兼容旧 Runtime
兼容旧 Constructor
兼容旧 API
兼容旧 Provider
兼容旧 Persistence
兼容旧 Tests
```

而留下来的：

```text
双线实现
fallback
compatibility seam
optional service
旧 authority
旧 API
旧 tests
dead code
```

重新审计。

核心目标不是：

> “尽量兼容旧系统。”

而是：

> **当前 Canonical Production Path 必须只有一条；已经退出当前 Architecture 的旧 Contract 可以直接破坏性删除。**

最终确认了 37 项 Compatibility Debt，其中 24 条直接删除、13 条通过迁移调用者后重写；删除 19 个 legacy-only test files、约 116 个 legacy test nodes，并迁移 53 个 caller。

------

# 二、最终完成状态

最终：

```ini
WP7_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

STAGE7_CANONICAL_PATH_CONSOLIDATED = PASS

P0_COUNT = 0
BLOCKING_P1_COUNT = 0
ACCEPTED_P1_COUNT = 0
P2_COUNT = 2

BREAKING_CHANGE = YES

FORWARD_COMPATIBILITY_WITH_LEGACY = NOT_REQUIRED
LEGACY_COMPATIBILITY_REQUIRED = NO

ARCHITECTURE_REOPEN_REQUIRED = NO
```

所以 WP7 的结果不是：

```text
“新旧两套都能跑”
```

而是：

```text
“当前 Production Canonical Path 收敛成一套”
```

------

# 三、名词 / 概念速览

### Canonical Path

当前唯一被正式支持、测试、部署和维护的生产执行路径。

### Legacy Path

已经被当前架构替代，但历史上为了兼容而继续保留的旧执行路径。

### Compatibility Debt

为了兼容历史版本而引入，并持续增加维护成本、旁路风险或测试成本的技术债。

### Breaking Change

主动破坏旧接口、旧行为、旧配置或旧测试，不再保证旧调用方继续工作。

### Forward Compatibility with Legacy

继续让旧版本或旧调用方式在新系统里工作；WP7 明确不再要求。

### Compatibility Shim

为了让旧接口继续工作而保留的一层翻译 / 适配 / fallback。

### Dual-path Architecture

新旧两套路径同时存在，例如 Durable Runtime 和旧 Process-local Runtime 同时可达。

### Production Reachability

某段代码是否真的能从正式生产入口走到，而不是只存在于 Unit Test。

### Authority

哪个组件拥有某类最终事实的决定权，例如 PostgreSQL Durable Run Control 是 Run ownership authority。

### Duplicate Authority

同一种 Truth 同时由两套系统决定，比如 PostgreSQL 和 Process Memory 都能决定 Approval。

### Fail Closed

旧依赖缺失或状态不满足时拒绝继续执行，而不是退回旧行为。

### Test-only Seam

只服务测试，不参与生产的构造方式或辅助接口。

### Current Contract

虽然名字可能带 Legacy / Compatibility，但当前生产仍真实依赖的正式 Contract。

### Dead Code

没有当前 Production Value、没有当前 Canonical Caller，只因为历史遗留而存在的代码。

------

# 四、为什么“兼容旧版本”会变成架构问题

兼容本身不是坏事。

问题在于旧系统里常出现：

```text
if new_service is available:
    new_path()
else:
    old_path()
```

短期看很方便。

长期就变成：

```text
Canonical Path
+
Legacy Path
```

两个 Runtime Truth 同时存在。

比如 Durable Run 已经成为正式 Authority，但某个旧入口还能：

```text
绕过 DurableRunControlService
→ 走 Process-local execution
```

那所谓 Durable Runtime 就并不是真正的系统 Authority。

WP7 的核心原则因此是：

> 如果旧行为已经退出 Current Production Contract，那么继续兼容它本身就是风险。

------

# 五、为什么旧测试也应该删除

以前很容易出现：

```text
生产已经迁移到新 Contract
↓
旧 test 失败
↓
为了让旧 test 继续绿
↓
production 保留 compatibility branch
```

结果测试反过来阻止架构收敛。

WP7 改成：

```text
如果 Test 只保护已经废弃的 Contract
→ Delete Test
```

而不是：

```text
修改 Production 重新兼容 Test
```

最终 LocalAgent 删除 14 个 legacy-only test files，AgentEvalOps 删除 5 个，总计约 116 个旧 test nodes。

这里一个很重要的思想是：

> **Test 不是天然正确的；Test 只是某个 Contract 的 executable specification。Contract 废弃以后，保护它的 Test 也应该退出。**

------

# 六、为什么 Test Count 下降不一定是 Regression

例如：

```text
原来有 1000 tests
删掉 116 个 Legacy tests
现在只有 884
```

不能机械认为：

> Coverage 下降了。

如果删除的是：

```text
旧 Runtime
旧 API
旧 Persistence
旧 Provider
```

对应的行为测试，

那么这代表：

```text
系统支持面变小
Canonical Boundary 更清晰
```

而不是功能退化。

真正重要的是：

```text
Current Canonical Contract
是否有充分测试
```

WP7 最终 Canonical Regression 为 PASS。

------

# 七、WP7 是怎么分类 Legacy Debt 的

实际 Cleanup 并不是：

```text
grep legacy
→ delete
```

而是先区分：

```text
当前 Production Contract
历史 Legacy Debt
Test-only obsolete seam
当前真实 limitation
```

Final Gate 里确认了 37 项 Compatibility Debt，同时还确认了 9 项虽然名字带 Compatibility / Legacy，但仍属于 Current Contract，因此保留。

这点非常重要：

> **Legacy 是语义，不是变量名。**

------

# 八、Runtime 双线清理了什么

WP7 直接删除了：

```text
core/runtime/agent_loop.py
core/runtime/runtime_mode.py
CHAT_RUNTIME_MODE
ChatService legacy execution branch
AgentRouter legacy orchestration
legacy blocking executor
旧 RunHandle constructor
server module-level compatibility handles
```

生产现在只剩：

```text
FastAPI / ChatService
→ CoordinatedRuntimeFactory
→ durable Run lease / fencing
→ canonical Runtime
```

这意味着：

> “Legacy Runtime 已经不可 Production Reachable。”

而不仅是：

> “默认不开 Legacy。”

------

# 九、为什么“配置禁用 Legacy”还不够

两种状态区别很大。

## 方案 A

```text
Legacy code 还完整存在
只是 config 默认不用
```

意味着未来：

```text
某个配置
某个 test helper
某个 DI seam
```

仍可能重新进入旧链路。

## 方案 B

```text
Legacy production path deleted
Canonical caller migrated
```

旧路径从结构上不存在。

WP7 选择的是 B。

------

# 十、Optional Durable Service 为什么危险

典型历史代码：

```python
if durable_service is not None:
    use_durable()
else:
    use_old_process_local()
```

这样 `Optional` 本身就在表达：

> Durable Authority 不是强制 Contract。

WP7 将 Production 需要的：

```text
Run
Approval
Tool side-effect
```

Durable Service 收紧成 Required。

特别是 Cancel / Approval HTTP 不再从：

```text
ChatService
Local Registry
Process-local Controller
```

获取跨实例 Truth。

------

# 十一、Required Dependency 是一种 Architecture Enforcement

很多人会把：

```text
Optional[DurableService]
→ DurableService
```

看成类型层面的“小改动”。

实际上它表达的是：

> 当前 Architecture 不再允许没有 Durable Authority 的 Production Runtime 存在。

也就是把：

```text
Architecture Rule
```

直接编码进 Constructor / Composition Root。

这是很实用的工程方法。

------

# 十二、Tool Runtime 清理了什么

WP7 删除了旧：

```text
direct Tool execution
legacy executor seam
Complex Workflow string compatibility wrapper
```

而当前 Canonical Tool Chain 保持：

```text
ToolRegistry
→ ToolAdapter
→ Typed Validation
→ ToolInvocation
→ Governance
→ Approval / Claim
→ ToolExecutionService
→ Durable Side-effect Ledger
```

所以任何 Tool 都不能通过历史 helper 绕开：

```text
Validation
Governance
HITL
Side-effect Safety
```

------

# 十三、为什么 `LegacyStringToolAdapter` 没删

它名字里有：

```text
Legacy
```

但它仍然适配三个当前正在使用的 String Tool 进入：

```text
Typed / Governed Tool Runtime
```

它不是安全旁路。

所以 WP7 保留了它。

这就是一个很好的面试例子：

> **是否 Legacy 不能看类名，要看 Production Role。**

------

# 十四、Approval / HITL 清理了什么

历史代码还存在：

```text
Cancel / Approve / Reject
→ local fallback
```

WP7 将这些删掉。

现在：

```text
HTTP Approval / Cancel
→ Required Durable Service
```

Local Controller / Registry 只允许：

```text
wake-up acceleration
local projection
```

不能成为跨实例 Truth。

------

# 十五、为什么 Local Cache 还能保留

“删 Legacy”并不意味着：

```text
Process-local state 全删
```

例如：

```text
Local waiter
Local registry
cache
```

仍可以存在。

关键区别是：

```text
Cache Miss
!=
Business Truth
```

也就是说它们可以帮助：

```text
性能
唤醒
投影
```

但不能决定：

```text
Run 是否存在
Approval 是否批准
Tool 是否已执行
```

------

# 十六、Provider 层清理了什么

Remote Provider 删除：

```text
requests.Session injection
requests.post compatibility
requests exception classifier
old non-stream JSON generate path
old native JSON path
```

当前 Production Provider 只保留：

```text
application-scoped httpx.AsyncClient
+
async typed delta
```

这把 WP4 已经建立的 Async Streaming Contract 从：

```text
“Canonical path”
```

进一步收紧成：

```text
“唯一 production provider path”
```

------

# 十七、为什么 Sync Facade 还保留

WP7 没有机械把所有同步 API 删除。

因为当前 blocking Runtime / AgentRouter 仍然真实调用：

```text
generate()
```

所以这个 Sync Facade 属于：

```text
Current Production Contract
```

而不是 Legacy Debt。

这也是 Cleanup 的一个核心原则：

> 不为了“代码看起来纯”而重构当前正常 Contract。

------

# 十八、这轮 Provider Cleanup 还发现了什么真实问题

清理时发现：

```text
sync model
→ async Runtime
```

适配过程中，把 async Delta Callback 错误直接交给 Thread 内 Sync Adapter，

导致：

```text
PLANNING_MODEL_FAILED
```

最后改成：

```text
Sync model 在线程完成
→ 回 Event Loop
→ Runtime acceptance
```

从而继续保持：

```text
pre-accept fallback
post-accept fail-stop
```

这说明 Legacy Cleanup 也可能暴露隐藏的 Current Contract Bug。

------

# 十九、MCP 清理了什么

WP7 删除了：

```text
McpIntegrationComponent.wait_for_available
```

这个未使用 Compatibility Helper。

但没有重写当前 Phase9/WP6 的 MCP 架构。

生产仍只有：

```text
McpIntegrationComponent
→ validated Session Generation
→ frozen Registry / Governance
→ Adapter Resolver
```

并确认没有：

```text
direct StdioMcpClient production path
adapter-owned session
old reconnect prototype
```

------

# 二十、Persistence 清理是为什么最关键的一类 Cleanup

WP7 删除：

```text
Runtime SQLite Snapshot Store
SQLite EventConsumption Checkpoint Store
旧 persistence CLI
Journal v1 reader / digest
PlanSnapshot v1
legacy_fingerprint
```

当前 Runtime Durable Authority 不再同时保留：

```text
PostgreSQL
+
SQLite fallback
```

这类 Cleanup 比普通 Dead Code 更重要，因为它直接消除了：

```text
Duplicate Persistence Authority
```

------

# 二十一、为什么 Memory SQLite 没删

因为：

```text
Memory SQLite
```

属于当前 Memory 数据 Contract，

而不是：

```text
Runtime Run / Approval / Tool Side-effect Authority
```

所以虽然同样叫 SQLite：

```text
用途不同
Truth Domain 不同
```

不能因为“我们现在都用 PostgreSQL”就机械删除。

------

# 二十二、API Cleanup 做了什么

LocalAgent 删除：

```text
/api/runtime/evaluation-execute/v1
```

保留当前：

```text
evaluation-v2 / v3 / v4
```

AgentEvalOps 同时删除：

```text
generic /api/runtime/execute target
evaluation-v1 parser / target
anonymous bearer fallback
synthetic-default release-gate seam
```

Bearer Token 改为：

```text
Required + non-empty
```

------

# 二十三、为什么旧 API 可以直接删

因为当前项目没有要求：

```text
保持所有历史外部 Client
```

而且旧 Evaluation API 已经有明确 Canonical Replacement。

所以与其：

```text
v1
→ translate
→ v2
```

长期保留，

不如：

```text
删除 v1
迁移仓内 caller
```

这能减少：

```text
parser
auth
schema
test
security
```

多套 Contract。

------

# 二十四、Compatibility Cleanup 也是 Security Hardening

WP7 实际发现一个重要问题：

```text
evaluation v3/v4
```

会先被一个更宽泛的 Evaluation Middleware Rule 匹配。

这使：

```text
SERVICE + scope
```

可能绕过：

```text
ADMIN-only
```

要求。

最终通过调整 Route Priority 关闭。

所以：

> 历史 Compatibility Rule 往往不是单纯维护成本，也可能形成 Security Bypass。

------

# 二十五、为什么 Production Reachability 是判断 Legacy 的核心

一段代码可能：

```text
名字很旧
```

但仍是 Production Current Contract。

另一段代码可能：

```text
名字看起来正常
```

但实际上只为旧测试存在。

所以判断时应该问：

```text
Production入口能不能走到它？
当前Composition Root是否装配它？
当前Docs是否声明支持？
当前Canonical Tests是否依赖？
```

而不是看：

```text
class name
文件创建时间
代码风格
```

------

# 二十六、37 项 Compatibility Debt 最终如何处理

最终统计：

```text
Compatibility Debt Found = 37

Legacy Paths Deleted = 24

Legacy Paths Rewritten = 13

Legacy Configs Removed = 2

Legacy APIs Removed = 3

Legacy Test Files Deleted = 19

Legacy Test Nodes Deleted = 116

Dead Code Items Deleted = 13

Canonical Callers Migrated = 53
```

这说明 WP7 不是：

```text
简单 grep + delete
```

而是：

```text
audit
→ classify
→ migrate
→ delete
→ regression
```

------

# 二十七、哪些 Compatibility 被故意保留

最终保留 9 类。

比较重要的包括：

```text
Model sync facade
LegacyStringToolAdapter
ChatStreamCompatibilityAdapter
Memory SQLite v1 migration
Current Snapshot/Event schema compatibility
MCP protocol version compatibility
Trace compatibility fields
纯测试 helper
Desktop/w crawler等独立 requests.Session
```

这些之所以保留，是因为它们：

```text
仍属于 Current Contract
```

而不是因为：

```text
“怕删”
```

------

# 二十八、为什么“保留 Current Compatibility”并不和 WP7 冲突

WP7 目标不是：

```text
ZERO compatibility code
```

而是：

```text
ZERO obsolete compatibility path
```

例如 MCP Protocol Version Compatibility 是：

```text
外部协议兼容
```

这属于当前功能。

而 `requests.Session` Remote Provider seam 是：

```text
已被 httpx async transport 取代
```

所以删除。

关键判断是：

> **兼容的是当前支持对象，还是历史废弃对象。**

------

# 二十九、工程方法类问答

## Q1：为什么不推荐长期维护新旧两套 Runtime？

因为两套 Runtime 最终会产生：

```text
两套 Owner
两套测试
两套错误恢复
两套安全边界
```

而且 Bug 修复很容易只修新链路。

------

## Q2：Breaking Change 为什么有时比 Compatibility 更好？

如果当前没有必须维持旧 Contract 的外部要求：

Breaking Change 可以快速：

```text
收窄支持面
减少状态空间
减少旁路
减少测试
```

让系统更容易推理。

------

## Q3：删除测试是不是很危险？

删除当前 Contract 的测试危险。

删除已经废弃 Contract 的测试是合理的。

关键先判断：

```text
Test 保护的是当前行为
还是 Legacy 行为
```

------

## Q4：为什么 Optional Dependency 容易成为兼容债？

因为 Optional 往往意味着：

```text
有它走新路
没它走旧路
```

如果新 Service 已经是 Canonical Authority，就应该 Required。

------

## Q5：为什么 Process-local cache 可以保留？

因为 Cache 可以是：

```text
Performance Optimization
```

只要：

```text
Cache Miss != Business Truth
```

就不会形成 Duplicate Authority。

------

## Q6：为什么 Sync Facade 不删？

因为它现在仍有 Production Caller。

删除它需要 Runtime 进一步 Async 化，那属于新 Scope，不是 Legacy Cleanup。

------

## Q7：为什么 Memory SQLite 不删？

因为它属于不同 Truth Domain。

不能因为 Runtime Durable State 用 PostgreSQL，就把所有 SQLite 都定义为 Legacy。

------

## Q8：怎么判断某个兼容代码是否应该删？

主要看：

```text
production reachability
current contract
canonical replacement
authority impact
security impact
```

------

## Q9：为什么旧 API 不保留 deprecated shim？

因为本项目当前没有 Forward Compatibility Requirement，而且仓内 Caller 都可以直接迁移。

继续保留只会增加 Auth/Parser/Test Contract。

------

## Q10：Legacy Cleanup 为什么会发现新 Bug？

因为迁移 Caller 和删除 fallback 后，原来被 Compatibility Layer 掩盖的：

```text
错误回调
错误依赖
错误路由
```

会直接暴露。

------

# 三十、30 秒面试总结

Stage7 完成后我又做了一轮 Legacy Compatibility Debt Cleanup。因为项目早期为了持续演进，保留了不少旧 Runtime、旧 constructor、fallback、SQLite authority、Provider requests seam 和旧 Evaluation API。

我先从 Production Reachability 和 Authority 出发，把 Current Contract 和 Legacy Contract 分开。最终清掉 37 项兼容债，包括 24 条直接删除、13 条迁移重写，同时删掉 19 个只保护旧 Contract 的测试文件和 116 个 Legacy Test Node。

最终 Production 只剩 Coordinated Runtime、Required Durable Services、async httpx Provider、当前 MCP Lifecycle 和 authenticated evaluation-v2 target，不再为了旧测试保留 Production Bypass。

------

# 三十一、2 分钟面试总结

Stage7 Final Gate 做完以后，我又补了一轮 Canonical Path Consolidation。

原因是项目从早期单进程 Runtime 一路演进到 Durable Run、HITL、Tool Governance、Streaming、MCP 和 Side-effect Reconciliation，中间为了不破坏旧版本，留下了一些 Legacy branch、Optional service、Fallback 和旧测试。

这类代码最大的问题不是代码量，而是它会让新的 Authority 不彻底。比如明明 PostgreSQL 已经是 Approval 或 Run 的 durable authority，但如果某个旧入口还能回退到 Local Registry，那系统就依然存在第二套 Truth。

所以我重新审计了 Stage1～Stage7 的历史 Handoff、Composition Root、Runtime、Tool、Provider、Persistence、API 和 Tests。判断标准不是代码名字，而是 Production Reachability 和 Current Contract。

最后确认了 37 项 Compatibility Debt，24 条直接删掉，13 条迁移 Caller 后重写；删掉 19 个 Legacy Test Files、约 116 个旧 Contract Test Nodes，并迁移 53 个 Caller。

比较重要的变化包括：Production 只剩 Coordinated Runtime；Durable Run、Approval、Tool Invocation Service 变成 Required；Remote Provider 删除 requests 和旧非流式路径；Runtime SQLite Snapshot/Checkpoint Authority 删除；Evaluation v1、generic target 和 anonymous auth fallback 删除。

但我没有机械删除所有 Compatibility，例如当前 Runtime 还真实需要 Model Sync Facade，Memory SQLite 也属于独立 Current Contract，所以这些保留。

最终目标不是“零旧代码”，而是“一个 Production Canonical Path、一个 Authority”。

------

# 三十二、高频追问

## 1. 为什么要专门做 Legacy Cleanup？

因为长期兼容很容易形成：

```text
新 Authority
+
旧 fallback Authority
```

最后架构只在文档上是单一的。

------

## 2. 你删掉了多少？

```text
37 项 Compatibility Debt

24 条删除
13 条重写

19 个 Legacy Test Files
约 116 个 Test Nodes

13 组 Dead Code
53 个 Caller Migration
```

------

## 3. 为什么删除 116 个测试不是风险？

因为它们保护的是已经废弃的 Contract。

当前 Canonical Regression 仍然 PASS。

------

## 4. 你们现在完全不做 Compatibility 了吗？

不是。

Current External / Production Contract 的 Compatibility 仍保留。

不再维护的是：

```text
Obsolete Legacy Compatibility
```

------

## 5. 为什么 LegacyStringToolAdapter 还在？

虽然名字旧，但当前三个 Tool 仍通过它进入 Typed/Governed Runtime。

它不是安全旁路。

------

## 6. 为什么 Model Sync Facade 还在？

当前 Blocking Runtime 仍真实调用。

删除它需要新一轮 Async Runtime 重构，不属于 Legacy Cleanup。

------

## 7. 为什么 Runtime SQLite 删了，Memory SQLite 没删？

因为两者属于不同 Truth Domain。

Runtime Durable Authority 已经是 PostgreSQL；Memory SQLite 仍是当前 Memory Contract。

------

## 8. Cleanup 过程中发现过什么问题？

包括：

```text
Evaluation middleware route 权限绕过

Cancel/Approval endpoint 仍可能取 local truth

Sync Model → Async Runtime callback 错配

cancelled OUTPUT_DELTA coroutine cleanup

Provider docs 漂移
```

全部已关闭。

------

# 三十三、Bad Case

## Bad Case 1：为了旧测试保留旧 Runtime

```text
Production 已经不需要
但 Test 还在
→ 保留 Compatibility Branch
```

这是 Test 驱动架构倒退。

------

## Bad Case 2：Durable Service 仍 Optional

```text
有 PostgreSQL
→ Durable

没有
→ Process-local
```

等于 Durable Authority 并不真正强制。

------

## Bad Case 3：只在 Config 中禁用 Legacy

代码仍完整可达，只是默认关闭。

未来很容易再次开启。

------

## Bad Case 4：看到 Legacy 字样就删除

可能误删当前：

```text
LegacyStringToolAdapter
```

这种仍有 Production Value 的组件。

------

## Bad Case 5：所有 SQLite 都删

会误伤：

```text
Memory SQLite
```

这种独立 Current Contract。

------

## Bad Case 6：为了旧 Client 保留所有 API 版本

导致：

```text
Auth
Schema
Parser
Tests
```

永久多套。

------

## Bad Case 7：Delete Production Code，但旧 Caller 不迁移

结果只是把 Legacy Debt 变成 Runtime Bug。

------

## Bad Case 8：Compatibility Layer 可以绕过 Security

例如 broad Evaluation middleware 导致权限要求被更宽规则覆盖。

------

# 三十四、本 WP 最重要的三个知识点

## 第一：Canonical Path 比 Forward Compatibility 更重要

在没有明确兼容要求时：

```text
单一路径
>
新旧双线
```

尤其对 Agent Runtime 的 Safety Authority。

------

## 第二：Test 保护的是 Contract，不是历史

Contract 废弃：

```text
Test 也可以废弃。
```

不能为了 Test Green 继续保留旧行为。

------

## 第三：判断 Legacy 要看 Production Role

不是看：

```text
名字
年份
风格
```

而是看：

```text
Production Reachability
Current Contract
Authority
Canonical Replacement
```

------

# 三十五、Truth / Completion Boundary

## 已真实完成

### Canonical Runtime Single Path

Production 只装配 Coordinated Runtime。

### Legacy Runtime Removal

旧 AgentLoop / Runtime Mode / Legacy Chat / Legacy executor 已删除。

### Required Durable Services

当前 Production Run / Approval / Tool Side-effect 不再依赖 Optional compatibility fallback。

### Tool Runtime Consolidation

不存在 Legacy direct execution bypass。

### HITL Consolidation

Approval / Cancel 不再使用 process-local truth fallback。

### Provider Consolidation

Remote Provider 删除 requests / non-stream legacy path。

### MCP Consolidation

不存在第二条旧 MCP lifecycle / direct client production path。

### Runtime Persistence Consolidation

旧 SQLite Runtime Snapshot/Checkpoint Authority 删除。

### Evaluation Consolidation

只保留 authenticated current evaluation target。

### Legacy Test Removal

19 个 test files、约 116 个 nodes 删除。

### Dead Code Removal

确认删除 13 组 Dead Code。

### Canonical Caller Migration

共迁移 53 个 Caller。

### Canonical Regression

最终：

```ini
CANONICAL_PRODUCTION_PATH_SINGLE = PASS

LEGACY_RUNTIME_BYPASS = NONE
LEGACY_TOOL_EXECUTION_BYPASS = NONE
LEGACY_APPROVAL_BYPASS = NONE
LEGACY_SIDE_EFFECT_BYPASS = NONE
LEGACY_MCP_PATH = NONE
LEGACY_EVALUATION_BYPASS = NONE
DUPLICATE_AUTHORITY = NONE
OBSOLETE_COMPATIBILITY_FALLBACK = NONE

CANONICAL_REGRESSION = PASS
```

------

# 三十六、刻意保留的 Current Compatibility

保留并不代表 Cleanup 不彻底。

仍保留：

```text
Model Sync Facade
LegacyStringToolAdapter
Desktop Chat Compatibility Adapter
Memory SQLite v1 Data Compatibility
Current Snapshot/Event Schema Compatibility
MCP Protocol Version Compatibility
Trace Compatibility Contract
Test-only helper
其它独立 requests users
```

因为它们当前仍有真实价值。

------

# 三十七、没有在 WP7 做的事情

以下不是 Legacy Debt，因此没有借 Cleanup 扩 Scope：

```text
MCP HTTP Transport

Dynamic Tool Hot Reload

Multi-provider HA

Streaming Resume

Remote Cancellation Guarantee

Generic External Exactly-once

Saga / Compensation / 2PC

Evaluation Token Online Refresh

Real DeepSeek CI

Native-tool Initial-selection Streaming Buffer
```

------

# 三十八、还剩下的两个 P2

WP7 没有新增新的 P2。

继续保留：

```text
1. WP4 native-tool initial-selection buffering

2. AgentEvalOps workflow checkout floating LocalAgent main
```

这两个不是 Legacy Compatibility Debt，因此本 WP 刻意没有处理。

------

# 三十九、面试中不能夸大的地方

不要说：

> “所有 Legacy Code 都删完了。”

应该说：

> “所有已确认会形成 Production Compatibility Debt 或 Authority Bypass 的历史路径已经清理；仍属于 Current Contract 的 Compatibility 被保留。”

不要说：

> “现在完全没有任何同步代码。”

应该说：

> “Remote Provider Canonical Transport 已是 Async HTTP；Model Sync Facade 因当前 Runtime 调用仍有真实用途，所以保留。”

不要说：

> “所有 SQLite 都删除了。”

应该说：

> “Runtime Durable Authority 的 SQLite fallback 已删除；Memory SQLite 属于独立 Current Contract，仍然保留。”

不要说：

> “测试越少越好。”

应该说：

> “删除的是已经退出 Current Contract 的 Legacy Tests，同时 Canonical Regression 必须继续通过。”

------

# 四十、一句话总结

> WP7 的本质不是“大扫除”，而是把多年演进过程中为了兼容旧版本留下的 **Dual Path、Fallback、Optional Authority、旧 API 和 Legacy Tests** 清出 Production Boundary，让当前 Architecture 从“默认走新链路”真正变成“只存在一条 Canonical Production Path”。