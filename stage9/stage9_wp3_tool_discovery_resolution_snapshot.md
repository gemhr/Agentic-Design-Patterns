当前使用 GPT-5.6 Sol。

# Stage9-WP3 学习 / 面试总结

## Tool Discovery + Run-Level Tool Resolution Snapshot

WP3 解决的核心问题一句话可以概括为：

> **Tool 数量增长以后，既要控制模型看到的候选 Tool 数量，又要保证一个已经开始的 Run 在暂停、恢复、跨进程时看到的 Tool Contract 不会悄悄漂移。**

最终实现不是简单的“Top-K Tool 搜索”，而是：

```text
ToolRegistry
↓
Deterministic Discovery
↓
Top-K Candidate Set
↓
PostgreSQL Durable ToolResolutionSnapshot
↓
RunContext Hydration
↓
Planner / Native Tool Calling
↓
Snapshot-bound Tool Resolution
↓
Validation / Governance / Approval / Claim / Execution
```

当前 WP3 Final Gate 已经是 `P0=0 / P1=0 / P2=0`。

------

# 1. 这一 WP 最终构建了什么

最终有两层能力。

第一层是工具发现（Tool Discovery）：

```text
大 Tool Catalog
↓
可见性过滤
↓
metadata keyword matching
↓
deterministic ranking
↓
Top-K
```

第二层是运行级工具解析快照（Run-level Tool Resolution Snapshot）：

```text
Run R
↓
Discovery Result
↓
PostgreSQL create-once Snapshot
↓
后续 Planner / Tool Calling / Execution
都只能使用这个 Snapshot
```

这样解决了两个完全不同的问题：

```text
Discovery
→ 控制候选集规模

Snapshot
→ 保证 Run 内 Tool Contract 稳定
```

WP3 最终已经把 Snapshot 从 Luna 最初的 `RunContext` 内存对象补成了 PostgreSQL Durable Snapshot，并提供 `load / validate / hydrate` 恢复接口。

------

# 2. 为什么 Tool 多了以后不能全部塞给模型

假设系统有：

```text
100 个 Tool
```

如果每次都把所有：

```text
name
description
JSON schema
```

传给模型，会产生几个问题：

第一是上下文成本增加。

第二是模型选择空间变大，错误 Tool Recall 概率可能上升。

第三是很多 Tool 当前用户根本不可见，没必要进入 Prompt。

所以加入：

```text
Tool Discovery
```

先做候选筛选。

但是这里很重要：

> **Discovery 只是 Candidate Selection，不是 Authorization。**

即使 Tool 被 Discovery 选中，真正调用时仍然必须走：

```text
Typed Validation
↓
Current Governance
↓
Approval
↓
Execution Claim
↓
ToolExecutionService
```

这个 Authority Boundary 在 WP3 修复后保持不变。

------

# 3. 为什么 Tool Discovery 不能等于 Tool Authorization

这两个问题完全不同。

Discovery 问：

> 这次应该让模型看到哪些 Tool？

Authorization / Governance 问：

> 当前这一次具体 Invocation 是否允许执行？

比如：

```text
Tool = delete_file
```

可能在 Catalog 里，也可能因为当前任务和文件相关而进入 Top-K。

但真正执行时还要看：

```text
当前用户权限
实际 path
risk
side effect
是否需要 Approval
```

所以：

```text
Discovery Filter
≠ Final Authorization
```

这是本 WP 很值得面试讲的一点。

------

# 4. 为什么必须有 Run-level Snapshot

假设 Run 开始时：

```text
Tool A
schema = v1
```

模型做完前半段以后 Run 暂停。

这时部署了新版本：

```text
Tool A
schema = v2
```

如果恢复时直接重新读当前 Registry：

```text
旧 Run 前半段
→ Tool A v1

恢复以后
→ Tool A v2
```

同一个 Run 内 Contract 就变了。

这会产生：

- 参数不兼容；
- Approval Binding 不一致；
- Provider Identity 漂移；
- 执行不可复现；
- 审计无法解释。

所以创建 Run 时必须冻结：

```text
ToolResolutionSnapshot
```

------

# 5. Snapshot 最终保存什么

当前 PostgreSQL 表：

```text
tool_resolution_snapshots
```

以：

```text
run_id
```

作为主绑定。

核心字段包括：

```text
snapshot_digest
registry_digest
selection_algorithm_version
snapshot_schema_version
selection_query_digest
created_at
tool_items
```

每个 Tool Item 至少记录：

```text
tool_name / canonical_tool_id
provider_kind
provider_identity
remote_tool_id
schema_digest
descriptor_digest
```

这些 Digest 使用 canonical JSON + SHA-256 生成。

------

# 6. Snapshot 保存的是 Contract，不是 Runtime Object

不能把：

```text
Python callable
Adapter instance
MCP session object
```

直接持久化。

正确方式：

```text
Snapshot
保存 Tool identity + contract digest

恢复时：
Snapshot
↓
当前 ToolRegistry
↓
重新解析当前 registration
↓
验证 identity/schema/provider
↓
hydrate RunContext
```

所以 Snapshot 是：

> **持久化 Contract Evidence。**

而不是：

> 把 Python 对象序列化进数据库。

------

# 7. Snapshot 为什么必须 Durable

Luna 第一版其实已经有：

```text
RunContext.tool_resolution_snapshot
```

同一进程里运行是没问题的。

但进程重启以后：

```text
RunContext
```

没了。

如果只能：

```text
重新 Discovery
```

就不能保证：

> 恢复后还是原来那组 Tool。

所以 WP3 的真正 Gate 是：

```text
Run
↓
PostgreSQL Snapshot
↓
Process Restart
↓
load by run_id
↓
validate
↓
hydrate
```

Sol 正是在这一点上发现 P1，并补成 Durable Snapshot。

------

# 8. 为什么不能恢复时重新 Discovery

因为 Discovery 的输入环境可能已经变化。

例如：

```text
Run start:
Catalog = {A, B, C}

Resume:
Catalog = {A, B, C, D}
```

如果重新 Discovery：

旧 Run 可能突然获得：

```text
Tool D
```

这意味着：

> Run 的执行 Contract 被静默扩大。

当前策略：

```text
new Tool added
→ old Run invisible
```

同样，如果旧 Tool 消失：

```text
Tool removed
→ blocked
```

而不是：

```text
自动找一个差不多的替代 Tool
```

当前 Drift Policy 已经明确冻结。

------

# 9. Schema Drift 怎么处理

例如 Snapshot：

```text
Tool A
schema_digest = abc
```

恢复以后当前 Registry：

```text
Tool A
schema_digest = xyz
```

不能：

```text
继续执行
```

因为参数 Contract 已经变化。

现在会：

```text
TOOL_SNAPSHOT_SCHEMA_DRIFT
→ fail closed
```

Provider Identity 改变也是一样：

```text
TOOL_SNAPSHOT_PROVIDER_DRIFT
```

不会悄悄切换 Provider。

------

# 10. Registry Digest 是干什么的

单个 Tool Digest 只能说明某个 Tool。

但 Snapshot 还要表达：

> 当时这个 Tool Set 来自哪个 Catalog Contract。

所以增加：

```text
registry_digest
```

它是内容导出的稳定 Identity。

不能使用：

```text
id(registry)
memory address
startup counter
registration incidental order
```

因为这些跨进程都不稳定。

------

# 11. Descriptor Digest 和 Schema Digest 为什么分开

这两个变化语义不同。

## Schema Digest

表示：

```text
Invocation Contract
```

比如：

```text
arguments
types
required fields
```

变化意味着执行接口变化。

------

## Descriptor Digest

还可能覆盖：

```text
description
tags
selection metadata
provider metadata
```

变化可能影响 Discovery。

当前策略比较保守：

```text
descriptor drift
→ blocked
```

保证旧 Run 恢复时不会悄悄面对不同的 Tool 描述/选择语义。

------

# 12. Discovery 怎么做到 Deterministic

第一版没有做 Embedding Search。

现在采用：

```text
metadata keyword matching
+
stable ranking
+
stable name tie-break
```

输入相同时：

```text
query
catalog
visibility
algorithm version
Top-K
```

输出顺序必须一致。

不能依赖：

```text
random
hash()
set iteration
process object order
```

这很重要，因为 Snapshot 本身是需要可解释和可复现的。

------

# 13. 为什么暂时不用 Embedding 做 Tool Search

不是不能做。

而是当前 Tool Discovery 最重要的工程问题首先是：

```text
candidate boundary
determinism
snapshot
resume stability
authority
```

而不是召回率极限优化。

所以第一版选择：

```text
Keyword / Metadata
```

优点：

- 实现简单；
- 排序确定；
- 可审计；
- 不增加 Embedding 基础设施；
- 容易测试。

当前明确 Non-goal 仍然包括 Embedding Tool Search 和 Learned Ranker。

------

# 14. Empty Result 为什么不能 fallback 全量 Tool

假设 Discovery 没找到 Tool。

错误做法：

```text
result = []
↓
fallback all registry tools
```

这样会让 Discovery 完全失去边界意义。

现在正确行为：

```text
[]
↓
Model runs without tools
```

也就是说：

> 没找到合适 Tool 是正常状态，不是系统错误。

WP3 已明确禁止 silent full-registry fallback。

------

# 15. Tool Snapshot 如何限制 Execution

只限制 Planner 看到哪些 Tool 还不够。

否则 Model 完全可能输出：

```text
tool_name = X
```

然后 Runtime：

```text
ToolRegistry.get(X)
```

如果 X 不在 Snapshot，但 Registry 里有，就绕过了 Discovery。

所以现在执行链是：

```text
Model Tool Proposal
↓
Run Snapshot Resolution
↓
Typed Validation
↓
Governance
...
```

Snapshot 外 Tool：

```text
reject
```

这才意味着 Snapshot 真正成为：

> **Run Tool Contract Boundary。**



------

# 16. Snapshot 为什么仍然不是 Authorization

比如旧 Snapshot 里有：

```text
Tool A
```

之后管理员撤销了该用户权限。

如果 Snapshot 是永久授权：

```text
snapshot contains A
→ allow
```

就会产生安全漏洞。

正确：

```text
Snapshot
→ Tool A 可被这个 Run 解析

Current Governance
→ 当前到底还能不能执行
```

所以：

```text
permission revoked
→ execution denied
```

反过来，如果后来权限扩大：

```text
new permission
```

旧 Run 也不能自动获得新的 Tool。

当前策略：

```text
permission expanded
→ no new Tool in old snapshot
```



------

# 17. MCP Tool 怎么进入这套体系

MCP 没有单独一套 Discovery。

当前：

```text
MCP Server
↓
MCP Adapter
↓
ToolRegistry
↓
ToolCatalog
↓
Discovery
↓
Snapshot
```

这是正确方向。

否则就会变成：

```text
Local Tool Discovery
+
MCP Tool Discovery
```

两套逻辑。

------

# 18. MCP 的 Durable Identity 是什么

不能用：

```text
session_generation
```

作为 Durable Identity。

因为：

```text
process restart
```

以后 generation 可以重新开始。

现在 MCP Snapshot 使用：

```text
configured server_id
+
remote_name
+
local canonical tool_name
+
schema digest
```

这些才是持久化兼容性证据。

`session_generation` 只算：

```text
runtime evidence
```

不进入 Snapshot Identity。

------

# 19. MCP Reconnect 怎么判断还能不能继续

场景：

```text
Run snapshot
↓
MCP reconnect
```

如果只是：

```text
session_generation changed
```

但：

```text
server identity same
remote tool identity same
schema same
descriptor same
```

允许继续。

如果：

```text
schema changed
provider identity changed
descriptor changed
```

阻塞。

不能：

```text
reconnect
→ rediscover
→ 自动换 Tool
```

------

# 20. WP3 给 WP4 留了什么

这是 WP3 和后面 WP4 最重要的接口。

WP4 不需要重新设计 Tool Resume。

它可以直接调用：

```text
load_tool_resolution_snapshot(run_id)
↓
hydrate_tool_snapshot()
↓
validate current Registry / Provider
↓
RunContext
```

如果 Snapshot 缺失：

```text
fail
```

如果 Drift：

```text
fail
```

不能重新 Discovery。

所以：

> **WP3 冻结 Tool Contract，WP4 恢复 Execution Context。**

------

# 21. Owner / Truth / Authority

这个表面试建议记住。

| 问题                                  | Owner                              |
| ------------------------------------- | ---------------------------------- |
| 当前系统有哪些 Tool                   | ToolRegistry                       |
| 本次 Run 应看到哪些候选 Tool          | ToolDiscovery                      |
| 本次 Run 最终冻结了哪些 Tool          | PostgreSQL ToolResolutionSnapshot  |
| 当前 Tool Schema 是否与 Snapshot 一致 | Snapshot Hydration / Validator     |
| 当前用户现在能不能调用这个 Tool       | Current Governance / Authorization |
| 高风险 Tool 是否批准                  | DurableApprovalService             |
| 谁获得真正执行权                      | Execution Claim                    |
| 谁真正调用 Provider                   | ToolExecutionService               |

核心：

> **Discovery、Snapshot、Authorization、Execution 是四个不同层次。**

------

# 22. 名词 / 概念速览

| 名词                                     | 一句话                                                       |
| ---------------------------------------- | ------------------------------------------------------------ |
| 工具注册表（Tool Registry）              | 当前进程可用 Tool Contract 的统一来源。                      |
| 工具发现（Tool Discovery）               | 从完整 Catalog 中筛选与当前任务相关的候选 Tool。             |
| Top-K                                    | 限制暴露给模型的 Tool 数量上限。                             |
| 工具解析快照（Tool Resolution Snapshot） | 冻结一个 Run 所看到的 Tool Contract。                        |
| Schema Digest                            | Tool 输入接口的内容摘要。                                    |
| Descriptor Digest                        | Tool 描述及选择相关元数据摘要。                              |
| Registry Digest                          | 整个 Catalog Contract 的内容型 Identity。                    |
| Drift                                    | Snapshot 和当前 Registry / Provider 出现不兼容变化。         |
| Hydration                                | 根据 Durable Snapshot 在当前进程重新解析可执行 Registration。 |
| Fail Closed                              | 无法证明兼容时拒绝继续，而不是自动换 Tool。                  |
| Deterministic Ranking                    | 同样输入得到同样候选顺序。                                   |

------

# 23. 真实 Bad Case 1：In-memory Snapshot

### REAL

Luna 第一版：

```text
RunContext
→ ToolResolutionSnapshot
```

同一进程：

没问题。

进程重启：

```text
Snapshot lost
```

只能重新 Discovery。

Sol 定义为 P1，因为这不满足 Stage9 的恢复目标。

最终修复：

```text
PostgreSQL create-once snapshot
```

再通过：

```text
load by run_id
```

恢复。

------

# 24. 真实 Bad Case 2：Planner 用 Snapshot，Execution 又查全局 Registry

### REAL

第一版存在类似：

```text
Planner
→ Snapshot

Execution
→ fallback ToolRegistry
```

这样 Model 如果输出一个 Snapshot 外 Tool：

仍可能被执行。

最终修成：

```text
Model proposal
↓
Snapshot Resolution
↓
Validation
```

Snapshot 外 Tool 直接拒绝。

------

# 25. Hypothetical Bad Case：运行中 Tool 升级

```text
Run start
Tool X schema v1

↓

Run pauses

↓

deploy Tool X schema v2

↓

Run resumes
```

错误：

```text
current registry X v2
→ continue
```

正确：

```text
Snapshot expects v1
Current registry = v2

→ schema drift
→ blocked
```

------

# 26. Hypothetical Bad Case：权限撤销

```text
Run start
Tool A allowed

↓

Snapshot includes A

↓

ADMIN revokes A

↓

Run resumes
```

正确：

```text
Snapshot resolution PASS

Governance recheck FAIL

→ no execution
```

因为：

```text
Snapshot
≠ Authorization Grant
```

------

# 27. 面试高频题

## Q1：100 个 Tool 怎么处理？

可以回答：

> Tool 数量大以后我不会把所有 Schema 都直接交给模型。我先做 Tool Discovery，根据当前 query、metadata 和 visibility 做 deterministic Top-K，然后把这组 Tool 在 Run 级别生成 Durable Snapshot。模型只能看到和解析 Snapshot 内的 Tool，但真正执行仍然会重新经过 Validation、Governance、Approval 和 Execution Claim。

------

## Q2：为什么 Discovery 以后还需要 Snapshot？

> Discovery 解决的是候选集规模，Snapshot 解决的是运行稳定性。一个 Run 可能暂停或跨进程恢复，如果恢复时重新 Discovery，Catalog 或 Schema 已经变化，就可能让同一个 Run 前后使用不同 Tool Contract。所以我把选中的 Tool identity、provider 和 schema digest 持久化到 PostgreSQL，恢复时加载原 Snapshot 并做兼容校验。

------

## Q3：为什么不能恢复时再跑一遍 Discovery？

> 因为那会导致 silent drift。比如新 Tool 加入、Tool Schema 更新、MCP Provider 变化，旧 Run 会看到不同的候选集。我的策略是旧 Run 只认原 Snapshot，新 Tool 对旧 Run 不可见，Tool 缺失或者 Schema/Provider 漂移就 fail closed。

------

## Q4：Snapshot 是不是 Tool 权限？

> 不是。Snapshot 只说明这个 Run 当时解析到哪些 Tool Contract。权限可能在 Run 执行期间发生变化，所以真正调用时仍然重新走当前 Governance。如果权限被撤销，Snapshot 里即使还有这个 Tool，也会拒绝执行。

------

## Q5：Snapshot 外 Tool 为什么要在 Validation 前拒绝？

> 因为 Snapshot 是这个 Run 的 Tool Resolution Boundary。先确认 Tool 属于当前 Run，然后才有意义验证它的参数。如果直接去全局 Registry 查，就等于绕过 Snapshot，Discovery 只剩 Prompt 优化作用。

------

## Q6：Tool Discovery 为什么不用向量检索？

> 第一版我优先解决确定性、权限边界和恢复一致性，所以用了 metadata keyword matching 和稳定排序。Embedding 或 learned ranking 可以以后优化召回质量，但它不影响 Runtime Contract，本阶段没有为了排名效果增加新的检索基础设施。

------

## Q7：MCP Tool 怎么处理？

> MCP Tool 和本地 Tool 进入同一个 ToolRegistry，所以 Discovery 和 Snapshot 不分两套。Snapshot 会保存 MCP provider/server identity、remote tool identity 和 schema digest。Reconnect 如果只是 session generation 变化而 identity/schema 不变可以继续，identity 或 schema 漂移就阻塞。

------

## Q8：为什么 MCP generation 不能作为版本号？

> 它是进程内 session 的代次，进程重启后可能重新从 1 开始，所以不能当 durable identity。我用 provider/server identity、remote tool identity 和 schema digest 做跨进程兼容判断。

------

## Q9：Tool Registry 和 Tool Snapshot 谁是真相？

> ToolRegistry 是“当前系统现在有哪些 Tool”的来源；Snapshot 是“某个 Run 当时冻结了哪些 Tool Contract”的 durable truth。它们回答的是不同问题，不是两个相互竞争的 Tool Truth。

------

## Q10：如果一个 Snapshot Tool 被删除怎么办？

> 不自动找替代品，也不重新 Discovery。恢复时 hydrate 找不到对应 Tool，就进入 incompatible/blocked 状态。继续执行必须明确处理，而不是静默改变原 Run Contract。

------

# 28. 如果真实面试再次问到

## 问：Tool 太多，怎么避免全部塞进上下文？

### WP3 完成前

只能回答设计：

> 我计划增加 Tool Discovery 做 Top-K。

但还没有工程闭环。

### WP3 完成后

现在可以回答：

> “我现在实际做了两层。第一层是 Tool Discovery，完整 Registry 先经过 visibility filter 和 deterministic metadata ranking，只把 Top-K Tool 给 Planner 和 native tool calling。第二层是 Run-level ToolResolutionSnapshot，因为只做 Top-K 还不够，一个 Run 暂停恢复以后 Registry 可能已经变化。所以我会把 selected Tool、provider identity、schema digest、descriptor digest 和 algorithm version 持久化到 PostgreSQL。恢复时只加载原 Snapshot，不重新 Discovery；如果 Tool 缺失或者 Schema/Provider 漂移就 fail closed。真正调用 Tool 时仍重新走当前 Governance，所以 Snapshot 也不是永久授权。”

这个回答现在已经有真实源码支撑。

------

# 29. 如果被追问“你的 Tool Discovery 做得高级吗？”

不要回答：

> 做了智能 Tool Retriever。

准确回答：

> “目前 Discovery 是确定性的 metadata keyword matching + Top-K，不是 Embedding Search。因为这个阶段我主要解决的是 Catalog 规模、Run Contract 和 Resume Drift，先保证结果可复现和可审计。Embedding 和 learned ranking 目前明确没做。”

这和当前 Known Limitations 一致。

------

# 30. 这一 WP 最该记住的 6 句话

1. **Discovery 解决候选集规模，Snapshot 解决 Run Contract 稳定性。**
2. **Snapshot 必须 Durable，否则进程重启后只能重新 Discovery。**
3. **旧 Run 不能因为 Registry 增加新 Tool 就自动获得新 Tool。**
4. **Tool 在 Snapshot 中不等于现在仍然有权限执行。**
5. **Snapshot 外 Tool 必须在执行链最前面被拒绝。**
6. **MCP session generation 只是运行期证据，不是 Durable Identity。**

推荐学习文件名：

```text
stage9_wp3_tool_discovery_resolution_snapshot_learning.md
```

WP3 学习到这里结束。下一步进入 **Stage9-WP4 — Generic Durable Continuation + Lease / Reaper / Recovery**。这个 WP 会把现在已经存在的 Run Lease、Approval、Tool Snapshot 和 Stage8 TicketContinuation 串成真正的跨 Worker 恢复闭环。