当前使用 GPT-5.6 Sol。

# Stage9-WP1 学习 / 面试总结

## Object Authorization + API v1 Foundation

WP1 解决的核心问题可以压成一句话：

> **把“用户已经登录”进一步收紧成“这个用户是否有权操作这个具体对象”，并把 Tenant、Owner、Action 收敛到统一的 ObjectAuthorizationService 中。**

这一步之后，AgentCore 才真正有了比较完整的对象级授权（Object-level Authorization）边界，而不只是认证（Authentication）和简单的 User ID Ownership。WP1 Final Gate 已经确认 Tenant、Owner、ADMIN、SERVICE、Legacy、Migration、第二 Authority 等阻断项全部关闭。

------

# 1. 这一个 WP 最终构建了什么

最终主链是：

```text
JWT
↓
Principal
↓
ObjectAuthorizationService
↓
Canonical Ownership
↓
Existing Domain Authority
```

其中 Principal 的 `tenant_id` 不是相信客户端，而是从 PostgreSQL 用户记录取得；如果 JWT 也带 `tenant_id`，必须和数据库完全一致。

这里最重要的不是新增了一个 Service，而是把以前散落的：

```text
user_id comparison
ADMIN bypass
SERVICE scope
EvaluationJob.owner_user_id
Run ownership
Stage8 Mission ownership
```

统一成了一个对象授权入口。

现在对象授权只回答：

> **这个 Principal 能不能对这个 Object 执行这个 Action？**

它不负责修改业务状态。

所以现在边界是：

```text
Authorization
≠ Run Lease
≠ Approval CAS
≠ Continuation Claim
≠ Tool Execution Claim
```

这几个 Owner 仍然独立。

------

# 2. 为什么“认证成功”还远远不够

认证（Authentication）回答的是：

> 你是谁？

比如：

```text
user_id = U100
tenant_id = T1
role = HUMAN
```

但对象授权（Object Authorization）回答的是：

> 你能不能操作 `mission_id=M200`？

这两个问题完全不同。

以前一个已经通过 JWT 的用户，如果知道别人的 `mission_id`、`continuation_id` 或 `execution_id`，某些 Stage8 API 仍可能继续执行业务操作。

这就是典型的不安全直接对象引用（Insecure Direct Object Reference, IDOR）问题。

WP1 之后：

```text
User A
↓
mission_id of User B
↓
ObjectAuthorizationService
↓
tenant / owner / action check
↓
404
```

而不是简单：

```text
JWT valid
→ allow
```

Legacy Stage8 的 Mission Planning、Provider Callback、Failure Triage、Tool Approval、TicketContinuation、Evaluation Job、Run Cancel 等路径现在都已经在 Mutation 之前进行授权。

------

# 3. Tenant 和 Owner 为什么要同时存在

这两个概念要分开。

## Tenant

租户（Tenant）是安全隔离边界：

```text
tenant_id = T1
```

意味着：

> T1 的对象原则上不能被 T2 的 Principal 访问。

## Owner

对象所有者（Object Owner）是 Tenant 内部的用户归属：

```text
owner_user_id = U1
```

所以授权通常先判断：

```text
Principal.tenant_id
==
Object.tenant_id
```

再判断：

```text
Principal.user_id
==
Object.owner_user_id
```

或者是否具有 Tenant 内的管理权限。

因此：

```text
Tenant
= hard security partition

Owner
= object-level user ownership
```

这就是为什么仅有：

```text
owner_user_id
```

仍然不够。

假设两个 Tenant 都有：

```text
user_id = 100
```

或者 ADMIN 可以绕过 Owner，缺 Tenant Boundary 就会产生跨租户访问问题。

WP1 最终还通过数据库组合外键保证：

```text
object_ownership(owner_user_id, tenant_id)
```

必须对应：

```text
users(id, tenant_id)
```

不能持久化成：

```text
owner = Tenant A User
tenant_id = Tenant B
```

这样的漂移状态。

------

# 4. 为什么 ADMIN 也不能直接放行

这是这次 Sol Review 抓出来的一个很典型的问题。

之前存在类似语义：

```text
if ADMIN:
    allow
```

甚至：

```text
ownership row 不存在
+
ADMIN
→ allow
```

这个逻辑在单用户或者小系统里可能觉得方便，但放进多租户系统就很危险。

正确顺序应该是：

```text
先解析 Object
↓
得到 Object tenant
↓
Principal tenant == Object tenant
↓
再判断 ADMIN
```

所以现在的 ADMIN 是：

> **租户内管理员（Tenant-local Administrator）**

可以：

```text
Tenant A ADMIN
→ 管理 Tenant A 内其他用户对象
```

不能：

```text
Tenant A ADMIN
→ Tenant B
```

而且：

```text
missing ownership
```

也不能因为 ADMIN 就放行。

这一点现在已经修正。

------

# 5. SERVICE Principal 为什么比 HUMAN 更容易做错

HUMAN 通常可以按：

```text
tenant
+
owner / admin
+
action
```

判断。

但服务身份（Service Principal）不同。

例如 Evaluation Worker、Provider Callback、后台 Processor，它们通常不是业务对象的 `owner_user_id`。

因此不能要求：

```text
SERVICE.user_id == owner_user_id
```

否则后台任务根本做不了。

但也不能变成：

```text
SERVICE
→ allow all
```

所以 WP1 最终冻结的是：

```text
same tenant
+
exact required scope
+
allowed action
+
endpoint policy
```

例如 Provider Result Callback：

```text
SERVICE
↓
same tenant
↓
PROCESS
↓
STAGE8_RESULT_CALLBACK_SCOPE
↓
Job → Mission authorization
↓
ingest_result
```

这就叫：

> **Scope 不能代替 Object Authorization，Object Authorization 也不能代替 Scope。**

两者是并列约束。

WP1 修复后 SERVICE 不再依赖“是不是 Owner”，但必须满足 Tenant + Scope + Action。

------

# 6. Action 为什么要显式建模

WP1 定义了：

```text
READ
MUTATE
CANCEL
APPROVE
PROCESS
RESUME
SUBSCRIBE
```

这是很重要的设计。

不能只判断：

```text
can_access(object)
```

因为：

```text
能 READ
≠ 能 CANCEL

能 READ
≠ 能 APPROVE

能 PROCESS
≠ 能 SUBSCRIBE
```

例如 Run：

```text
ObjectAuthorizationService
CANCEL
↓
DurableRunControlService.request_cancel()
```

而 Tool Approval：

```text
ObjectAuthorizationService
APPROVE
↓
DurableApprovalService
↓
Approval CAS
```

这里 Authorization 只决定：

> 你能不能发出这个业务动作。

真正：

```text
PENDING → APPROVED
```

是不是合法，仍然由 Approval State Machine 决定。

这就是：

> **Action Authorization 和 Domain Invariant 是两层控制。**

------

# 7. Authorization 为什么必须发生在 Mutation 之前

这也是本 WP 非常值得面试讲的一点。

错误：

```text
load object
↓
transition()
↓
write DB
↓
authorize()
```

即使最后返回 403，副作用已经发生了。

正确：

```text
Authenticate
↓
Resolve Object
↓
Authorize
↓
Domain Mutation
```

这次 Sol 找出的 Mission Planning 就是典型 Bad Case。

之前 Planning Route 会直接：

```text
读取 Mission
↓
调用 Specialist / Model
↓
创建 TestPlan
↓
创建 Review
↓
改变 Mission
```

但没有先授权。

修复后必须先：

```text
Mission MUTATE Authorization
```

之后才能进入 Model 或 Domain Service。

------

# 8. Child Object 为什么不一定都需要 tenant_id

WP1 没有机械给：

```text
Review
TestPlan
GeneratedCaseArtifact
ExternalExecutionJob
TicketContinuation
```

每张表都加：

```text
tenant_id
owner_user_id
```

这是一个合理取舍。

因为这些对象都有：

```text
Child
↓
Mission FK
↓
MISSION canonical ownership
```

所以只要：

```text
Child → Mission
```

是强数据库外键，并且查询时一定沿这个关系做授权，那么 Mission 作为聚合根（Aggregate Root）就已经提供 Ownership Truth。

例如：

```text
Review ID
↓
Review.mission_id
↓
Mission
↓
object_ownership
```

这比每张表复制 Owner 更简单，也避免：

```text
Mission tenant = A
Review tenant = B
```

这种冗余字段漂移。

但异步 Worker、独立热路径或者无法稳定 Join 的对象，可以考虑冗余。

判断原则不是：

> “所有表必须有 tenant_id。”

而是：

> **Ownership 是否可以无歧义、不可绕过地解析。**

------

# 9. Evaluation Job 为什么曾经构成第二 Authority

之前 Evaluation Job 自己有：

```text
EvaluationJobRow.owner_user_id
```

HTTP Endpoint 会直接：

```text
job.owner_user_id
→ require_owner_id()
```

但其他对象走：

```text
object_ownership
→ ObjectAuthorizationService
```

这就形成：

```text
Authority A = object_ownership
Authority B = EvaluationJob.owner_user_id
```

以后两个状态一旦不一致：

> 到底谁是真相？

所以 Sol 把它定义成第二对象 Authority。

WP1 修复后：

```text
EVALUATION_JOB
```

也加入 canonical ownership。

业务表里的 `owner_user_id` 可以继续作为业务字段，但：

> **不能继续作为 HTTP Authorization Authority。**

这是 Owner / Truth 设计里一个很典型的原则：

> **数据可以重复，Authority 不能重复。**

------

# 10. Migration 为什么也是安全设计的一部分

这次 WP1 的第一版最大的坑之一，实际上出在数据库迁移（Database Migration）。

代码 ORM 已经允许：

```text
MISSION
```

进入 `object_ownership`。

但是旧数据库实际存在：

```sql
CHECK object_type IN ('RUN', 'CONVERSATION')
```

如果 Migration 没修改这个数据库 Constraint：

```text
代码认为 MISSION 可写
数据库认为 MISSION 不可写
```

结果就是新 Mission 已经创建了，但 Ownership 写失败。

这进一步暴露出第二个问题：

原来：

```text
commit Mission
↓
bind ownership
```

是两个事务。

于是会留下：

```text
Mission exists
ownership missing
```

对于授权系统，这种状态非常危险。

现在变成：

```text
BEGIN

insert Mission
insert canonical ownership

COMMIT
```

Ownership 写失败：

```text
ROLLBACK Mission
```

这就是：

> **安全不变量（Security Invariant）必须和业务对象在同一事务建立。**



------

# 11. 为什么 API v1 现在值得做，但不能重写所有 Legacy API

Stage9 以后新增：

```text
Event Feed
Resume
Continuation
Tool Snapshot
```

如果继续全部挂在历史：

```text
/api/...
```

下面，后续很难再建立稳定兼容边界。

所以现在正式冻结：

```text
/api/v1
```

作为 Stage9 后新的公共 API Boundary。

WP1 只迁了最小几个：

```text
/api/v1/principal
/api/v1/missions/{mission_id}
/api/v1/runs/{run_id}/cancel
```

不是全量搬家。

这是因为这阶段的目标是：

> 建立版本化 Contract。

而不是：

> 重写整个 Server。

旧 `/api/...` 继续存在，但是 Legacy。

同时安全修复不能因为 Legacy 就不做：

```text
Legacy route
```

仍然必须走同一套 ObjectAuthorizationService。

------

# 12. 本 WP 的 Owner / Truth / Authority

这个需要面试时非常清楚。

| 问题                         | Owner / Truth                        |
| ---------------------------- | ------------------------------------ |
| 用户属于哪个 Tenant          | PostgreSQL Principal / User          |
| Object 属于哪个 Tenant/User  | Canonical Object Ownership           |
| 某 Principal 能否操作 Object | ObjectAuthorizationService           |
| Run 当前由哪个 Worker 执行   | DurableRunControlService / Run Lease |
| Approval 是否批准            | DurableApprovalService               |
| Tool 是否可以产生副作用      | Tool Governance + Execution Claim    |
| TicketContinuation 谁处理    | Continuation Claim                   |
| Domain 状态能不能 transition | 对应 Domain Service / State Machine  |

核心原则：

> **授权决定能不能进入命令，Domain Owner 决定命令本身是否合法。**

------

# 13. 名词 / 概念速览

| 概念                                                  | 一句话                                                |
| ----------------------------------------------------- | ----------------------------------------------------- |
| 认证（Authentication）                                | 确认调用者是谁。                                      |
| 授权（Authorization）                                 | 判断调用者可以做什么。                                |
| 对象级授权（Object-level Authorization）              | 针对具体 Object ID 判断调用者是否有操作权限。         |
| 租户（Tenant）                                        | 系统中的硬隔离安全边界。                              |
| 对象所有权（Object Ownership）                        | Tenant 内某个对象属于哪个业务用户。                   |
| 基于角色的访问控制（Role-Based Access Control, RBAC） | 根据角色授予权限。                                    |
| Scope                                                 | Service Token 被允许使用的一组窄能力。                |
| IDOR                                                  | 用户知道其他对象 ID 后绕过授权访问对象。              |
| 聚合根（Aggregate Root）                              | 子对象可以通过它继承一致的 Ownership 和业务生命周期。 |
| Canonical Authority                                   | 某一事实最终唯一可信的决定来源。                      |
| API 版本化（API Versioning）                          | 为公开接口建立稳定兼容边界。                          |
| Fail Closed                                           | 无法证明允许时默认拒绝。                              |

------

# 14. 真实 Bad Case

## REAL：Mission Planning IDOR

第一版 WP1 实现后：

```text
POST mission planning
↓
没有 ObjectAuthorizationService
↓
直接读 Mission
↓
Model / Specialist
↓
TestPlan / Review
↓
Mission transition
```

只要知道别人的：

```text
mission_id
```

就可能修改别人的 Mission。

Sol Review 把它定为 P0。

修复：

```text
mission_id
↓
Mission ownership
↓
MUTATE authorization
↓
planning
```

现在 foreign owner 请求会在模型调用和任何业务 Mutation 之前拒绝。

------

# 15. 一个面试常见故障场景

## HYPOTHETICAL：Tenant A 的 ADMIN 获取 Tenant B 的 Run ID

错误设计：

```python
if principal.is_admin:
    return allow
```

于是：

```text
Tenant A ADMIN
→ Tenant B Run
→ Cancel
```

正确设计：

```text
Resolve Run Ownership
↓
Object.tenant_id == Principal.tenant_id ?
↓ NO
404
```

只有 Tenant 一致以后：

```text
owner
or
tenant-local ADMIN
```

才继续判断。

------

# 16. 本 WP 高频面试题与直接回答

## Q1：Authentication 和 Authorization 有什么区别？

我会回答：

> Authentication 解决“你是谁”，Authorization 解决“你能对这个对象做什么”。我项目里 JWT 和数据库 Principal 负责认证，但一个已经登录的用户如果知道其他用户的 Mission ID，仍然不能直接操作。所以我又加了一层 ObjectAuthorizationService，根据 tenant、owner 和 action 判断 READ、MUTATE、APPROVE、CANCEL 等权限。认证成功不代表对象授权成功。

------

## Q2：为什么不能只靠 user_id 做 Ownership？

> 因为 user_id 只解决对象属于哪个用户，没有硬隔离不同租户。我们最终把 tenant_id 作为第一层 Security Partition，owner_user_id 作为 Tenant 内的对象归属。授权先检查 Tenant，再检查 Owner、ADMIN、SERVICE Scope。这样即使 ADMIN 也不能跨 Tenant。

------

## Q3：ADMIN 为什么不能直接 bypass？

> 因为 ADMIN 本身也必须有作用域。我这里定义的是 tenant-local ADMIN，它只能管理当前 Tenant 的对象。必须先解析 Object Ownership 并确认 Tenant 一致，然后 ADMIN 才能绕过 Owner 检查。如果 Ownership 缺失，我会 fail closed，而不是因为 ADMIN 就默认允许。

------

## Q4：SERVICE 不属于 Object Owner，怎么授权？

> SERVICE 不按 HUMAN Owner 规则判断。我要求它同时满足 same tenant、明确的 endpoint scope 和 action policy。比如 Provider Result Callback 必须属于同一个 Tenant，同时具备 callback scope 和 PROCESS 权限，之后才能更新对应 Job。Scope 不能代替 Object Authorization。

------

## Q5：为什么 Authorization 不能直接放进 Domain Service？

> Domain Service 负责业务状态是否合法，比如 Approval 能不能从 PENDING 变成 APPROVED；Authorization 负责调用者有没有资格发出这个命令。我把这两层分开。HTTP 或 Application 层先通过 ObjectAuthorizationService，然后仍然调用原来的 Domain Owner，不让授权层成为第二套状态机。

------

## Q6：为什么 Child Object 不都加 tenant_id？

> 我优先让 Child 通过强 FK 继承 Aggregate Root 的 Ownership。比如 Review、TestPlan、ExecutionJob 都能通过 Mission 找到 canonical ownership。如果每张表都复制 tenant 和 owner，反而要维护多份一致性。只有独立异步热路径或者无法稳定 Join 时，我才考虑冗余字段。

------

## Q7：为什么数据库也要做 Tenant Consistency Constraint？

> 不能只相信应用层。否则完全可能写出 owner 属于 Tenant A，但 ownership row 标成 Tenant B 的状态。我们最后给 users(id, tenant_id) 建 candidate key，再让 object_ownership(owner_user_id, tenant_id) 做组合外键，从数据库层禁止这种漂移。

------

## Q8：Authorization 应该在什么时候执行？

> 必须在任何 Domain Mutation 和外部副作用之前。比如 Mission Planning 之前有过一个漏洞，知道别人的 mission_id 就可能直接进入 Planning。后来改成先解析 Ownership、做 MUTATE Authorization，通过以后才允许 Model、TestPlan、Review 和 Mission transition 执行。

------

## Q9：为什么 Evaluation Job 的 owner_user_id 不能直接拿来授权？

> 因为系统已经有 canonical object ownership。如果 Evaluation Job 又自己拿业务表 owner_user_id 做 HTTP 授权，就产生两套 Authority。两个字段将来一旦漂移就不知道相信谁。所以业务字段可以保留，但 Object Authorization 必须统一走 canonical ownership。

------

## Q10：为什么现在才加 `/api/v1`？

> 前期快速开发时我们允许 Breaking Change，接口主要为了内部迭代。到 Stage9 开始做 Resume、Multi-Tenant、Continuation 以后，Public Contract 会越来越重要，所以我从这一阶段开始冻结 `/api/v1`。没有一次性迁移所有 Legacy API，只保证新的平台能力全部从 v1 开始。

------

# 17. 这次阿里面试，如果再次问到

这是 Stage9 学习阶段最值得保留的一部分。

## 问：多个业务、不同用户调用 Tool，权限怎么控制？

### WP1 之前

你只能回答：

> 我有 JWT、Role、Scope，还有 Tool Governance，部分对象会校验 Owner。

问题是：

> 还没有完整 Object-level Authorization。

### WP1 之后

可以回答：

> “我现在把认证和对象授权完全拆开。JWT 认证以后会从 PostgreSQL 构造 Principal，其中 tenant_id 是数据库绑定的。之后所有 object-bound command 都统一经过 ObjectAuthorizationService，先做 tenant boundary，再判断 owner、tenant-local ADMIN 或 SERVICE 的 scope/action。比如 Run Cancel、Tool Approval、Stage8 Mission、Execution Job 都必须先完成对象授权，之后才进入原来的 Run Control、Approval CAS 或 Domain Service。授权层没有执行 Authority，只负责决定 caller 能不能进入命令。”

这已经是很完整的平台型回答。

------

## 问：多租户是怎么做的？

现在可以直接回答：

> “我目前做的是最小多租户隔离，不是完整企业 IAM。Principal 有 tenant_id，durable object 通过 canonical ownership 绑定 tenant_id 和 owner_user_id。数据库还用 composite FK 保证 owner 和 tenant 一致。ADMIN 只能在当前 tenant 内管理，SERVICE 必须同时满足 same tenant、scope 和 action。Workspace、组织树、跨 tenant super-admin 目前没做。”

这个回答非常适合你当前项目事实。

------

## 问：如何防止一个用户知道别人 object ID 后直接调用接口？

可以回答：

> “我们所有 object-bound API 都不能只靠 Authenticated。请求先解析 canonical object ownership，再走 ObjectAuthorizationService。不存在和 unauthorized 对 Public API 都映射成 404，避免 ID Enumeration。真正的 domain mutation 只能发生在 authorization 之后。”

------

# 18. 当前 Known Limitations

WP1 完成后仍然没有：

```text
Workspace / Organization hierarchy
Super Admin
Full IAM
Resumable Streaming
Tool Discovery
Generic Durable Continuation
```

这些不是 WP1 Failure，而是明确的 Stage9 后续范围。

特别要注意：

> **现在可以说“实现了最小 Tenant/Object Authorization”，不能说“已经有完整企业级 Multi-Tenancy / IAM 平台”。**

------

# 19. 这一 WP 最应该记住的 5 句话

1. **Authentication 证明你是谁，Object Authorization 决定你能对哪个对象做什么。**
2. **Tenant 是硬隔离边界，Owner 是 Tenant 内对象归属。**
3. **ADMIN 也必须先经过 Tenant Boundary。**
4. **Authorization 只决定能否进入命令，不能接管 Run、Approval 或 Tool 的执行 Authority。**
5. **安全不变量不仅要写在代码里，还要用数据库约束和事务保证。**

推荐学习文档文件名：

```text
stage9_wp1_object_authorization_api_v1_learning.md
```

按照流程，WP1 学习到这里暂停。下一步是 **Stage9-WP2 — Durable Client Event Feed + Resumable Streaming**，它会直接解决你那场阿里面试里被连续追问的“断线、重连、跨实例、流式恢复”问题。