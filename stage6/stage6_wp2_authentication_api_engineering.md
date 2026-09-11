# Stage6-WP2 — Authentication & API Engineering

## 身份认证与 API 工程学习 / 面试总结

------

# 1. 名词 / 概念速览

**身份认证（Authentication, AuthN）**：回答“你是谁”，本项目通过 EdDSA JWT + PostgreSQL User 完成。

**授权（Authorization, AuthZ）**：回答“你能做什么”，本项目通过 RBAC 与对象级 Ownership 判断。

**JWT（JSON Web Token）**：携带身份 Claims 并由签名保证完整性的访问令牌。

**EdDSA**：WP2 固定使用的 JWT 非对称签名算法，API 只需要公钥验证 Token。

**主体（Principal）**：JWT 验证完成后，由服务端建立的可信身份对象。

**身份权威（Identity Authority）**：判断用户身份真假的最终 Authority，本项目是“Server Verified JWT + PostgreSQL User”。

**RBAC（Role-Based Access Control）**：基于角色进行权限控制，本项目固定 USER、OPERATOR、ADMIN。

**对象级授权（Object-level Authorization）**：不仅判断角色，还判断某个具体 Run / Conversation 是否属于当前用户。

**对象归属（Object Ownership）**：服务端持久化 `(object_type, object_id) -> owner_user_id` 的绑定关系。

**权限提升（Privilege Escalation）**：普通用户通过伪造身份或权限字段获得更高权限的安全问题。

**隐藏 404（Hidden 404）**：无权访问他人对象时返回 404，而不是暴露“对象存在但你没权限”。

**Request ID**：单次 HTTP Request 的诊断 Identity，用来关联响应、日志和错误，不等同于 Run ID 或 Trace ID。

**401 Unauthorized**：实际上表示“未通过身份认证”。

**403 Forbidden**：已经认证成功，但权限不足。

**可信边界（Trust Boundary）**：系统明确哪些信息来自可信服务端，哪些来自不可直接信任的客户端输入。

------

# 2. 当前 WP 真实实现

WP2 最终建立了真实 HTTP 身份链：

```text
Authorization: Bearer <JWT>
        ↓
AuthService
        ↓
EdDSA Signature / Claims Validation
        ↓
PostgreSQL User / Role
        ↓
Frozen Principal
        ↓
Authorization Service
        ↓
RBAC + Object Ownership
        ↓
FastAPI Business Route
```

JWT 必须验证：

```text
alg
iss
aud
sub
roles
jti
iat
nbf
exp
```

Token 中的 Role 不能单独作为最终权限 Authority。

系统还会读取 PostgreSQL 当前 Role Assignment，JWT 中的 Role 必须是数据库 Role 的子集。

因此即使 Caller 能构造一个：

```text
roles = ["ADMIN"]
```

也不能在数据库没有 ADMIN Assignment 的情况下升级权限。

------

# 3. 当前 Auth 架构与调用链

认证链：

```text
HTTP Request
    ↓
Authorization Header
    ↓
JWT
    ↓
AuthService
    ↓
EdDSA Verification
    ↓
Validate Claims
    ↓
PostgreSQL users / roles
    ↓
Principal
```

授权链：

```text
Principal
    ↓
Role Check
    ↓
Object Ownership Check
    ↓
ALLOW / DENY
    ↓
Route / Runtime
```

对象 Ownership：

```text
object_ownership
(
    object_type,
    object_id,
    owner_user_id
)
```

目前支持：

```text
RUN
CONVERSATION
```

该表只表达：

> “这个对象属于谁。”

它不负责：

```text
RunRegistry
AgentState
Approval State
Execution Claim
Journal
Snapshot
```

所以这里一个非常重要的边界是：

```text
Ownership Authority
≠
Runtime State Authority
```

------

# 4. Authentication 和 Authorization 有什么区别

这是后端面试非常高频的问题。

Authentication：

```text
Who are you?
```

例如：

```text
JWT signature valid?
Token expired?
User exists?
User disabled?
```

Authorization：

```text
What are you allowed to do?
```

例如：

```text
你是不是 ADMIN？

这个 Run 是不是你的？

你能不能 approve 这个 Run？
```

所以：

```text
JWT valid
```

不代表：

```text
可以访问所有 API
```

正确链路：

```text
Authentication
      ↓
Principal
      ↓
Authorization
```

------

# 5. 为什么客户端的 actor_id 不能作为身份

旧设计可能收到：

```json
{
  "actor_id": "admin"
}
```

如果服务端直接：

```text
actor_id
→ Runtime Actor
```

客户端就可以：

```text
普通用户
→ 修改 body
→ actor_id = admin
```

形成权限提升。

WP2 后：

```text
Runtime Actor
=
Principal.user_id
```

Payload 中的：

```text
actor_id
```

最多只是兼容字段，不能成为身份 Authority。

所以需要记住一句：

> 身份必须来自服务端验证后的 Principal，而不是客户端声明的 Identity Field。

------

# 6. Principal 为什么需要单独存在

可以直接在每个 Route：

```text
decode JWT
→ user_id
```

但长期会导致：

```text
Route A 这样校验
Route B 少校验一个 claim
Route C 直接相信 roles
```

因此 WP2 建立统一：

```text
AuthService
→ Principal
```

Principal 是：

```text
frozen=True
slots=True
```

的不可变身份对象。

后面的业务层只需要信任：

```text
Principal
```

而不需要再次处理 Raw JWT。

这样形成：

```text
Untrusted HTTP Input
        ↓
Authentication Boundary
        ↓
Trusted Principal
```

------

# 7. 为什么 JWT Role 还需要查数据库

假设 Token：

```text
roles = ["ADMIN"]
```

如果 API 只信 JWT：

> Token 有效期内，即使管理员已经撤销这个用户的 ADMIN 权限，它仍然可能继续使用旧权限。

当前实现采用：

```text
JWT roles
∩
PostgreSQL current roles
```

的严格关系。

更准确地说：

```text
token roles
必须是
DB current role assignment 的子集
```

所以：

```text
Token ADMIN
DB USER
```

不能以 ADMIN 执行。

这让 PostgreSQL 保持：

```text
Current Identity / Role Authority
```

而 JWT 只是：

```text
Signed Credential Snapshot
```

------

# 8. 为什么使用非对称 EdDSA

WP2 固定：

```text
EdDSA
```

API Server：

```text
只持有 Public Key
```

Token Issuer：

```text
持有 Private Key
```

因此即使 API Verification Server 被读取配置：

理论上也无法仅凭 Public Key：

```text
签发新的 ADMIN Token
```

这比：

```text
HS256
```

这类对称签名更适合：

```text
Issuer
和
Resource Server
```

职责分离的架构。

本项目当前不建设完整 OAuth Authorization Server，只提供 Local/Test Token Issuer。

生产 API 只负责：

```text
Verify
```

不负责：

```text
Issue
```

------

# 9. JWT 为什么必须固定算法

一个典型错误：

```python
jwt.decode(token, key)
```

然后根据 Token Header 自己决定：

```text
alg
```

攻击者可能试图利用：

```text
alg = none
```

或者算法混淆。

当前 AuthService：

```text
先明确检查 JWT header alg
+
PyJWT algorithms=["EdDSA"]
```

因此只有：

```text
EdDSA
```

可以进入验证流程。

`none` 和其它算法均 Fail Closed。

------

# 10. 常见 JWT Claims 在本项目中的作用

## iss — Issuer

谁签发的 Token。

防止：

```text
别的系统签发的合法 JWT
```

被 LocalAgent 接受。

------

## aud — Audience

这个 Token 是签给谁用的。

防止：

```text
原本给 Service A 的 Token
```

拿到 LocalAgent 使用。

------

## sub — Subject

用户身份。

本项目最终映射：

```text
PostgreSQL User UUID
```

------

## exp — Expiration

Token 到什么时候失效。

------

## nbf — Not Before

Token 在什么时间之前不能使用。

------

## iat — Issued At

Token 签发时间。

------

## jti — JWT ID

Token 自身唯一 Identity。

------

## roles

访问权限快照。

但不是数据库 Role Authority 的替代品。

------

# 11. RBAC 是怎么设计的

本项目固定：

```text
USER
OPERATOR
ADMIN
```

USER：

```text
访问自己的业务对象
```

OPERATOR：

```text
平台运维类操作
```

ADMIN：

```text
平台级管理与特权操作
```

Role Check 集中到：

```text
require_role()
```

Object Check 集中到：

```text
AuthorizationService
require_owned()
```

而不是让每个 Route 都自己写：

```python
if "ADMIN" in principal.roles:
```

Codex Review 没发现第二套互相冲突的 Authorization Owner。

------

# 12. RBAC 为什么还不够

假设：

```text
USER A
USER B
```

两个人角色都是：

```text
USER
```

仅 RBAC 可以判断：

```text
USER 可以访问 Run API
```

但无法判断：

```text
Run R1 是 A 的
还是 B 的
```

所以还需要：

```text
Object-level Authorization
```

最终：

```text
Role
+
Ownership
```

共同决定权限。

例如：

```text
USER
+
owns Run R1
→ ALLOW
USER
+
does not own R1
→ DENY
```

------

# 13. Object Ownership 为什么必须服务端持久化

错误方案：

```text
request.user_id
=
object owner
```

或者：

```text
agent_id
=
principal.user_id
```

本质上都容易把：

```text
Business Identifier
```

误认为：

```text
Security Identity
```

WP2 后建立：

```text
object_ownership
```

持久化：

```text
RUN R1 → USER A
CONVERSATION C1 → USER A
```

权限检查以数据库 Binding 为准。

Conversation / Memory 已不再使用 `agent_id` 作为 Principal 身份来源。

------

# 14. Run Ownership 是怎么绑定的

Run 通过认证 HTTP 创建时：

```text
Request
  ↓
Principal.user_id
  ↓
Persist Run Ownership
  ↓
Runtime Admission
```

Caller 不允许传：

```text
owner_user_id
```

决定 Ownership。

由于现有 RunRegistry 还是 Process-local，Ownership Binding 和 Runtime Admission 目前不能处于同一个数据库事务。

因此存在：

```text
Owner Binding COMMIT
        ↓
Runtime Admission Failure
        ↓
Orphan Ownership Binding
```

但不会出现：

```text
Active Run
without Owner
```

当前选择宁可：

```text
存在一条无 Active Run 的孤儿 Binding
```

也不能：

```text
产生一个真实运行但没有 Ownership 的 Run
```

这属于 Fail Closed 的安全取舍。

------

# 15. 为什么历史 Unknown Owner 默认拒绝 USER

历史数据可能没有：

```text
owner_user_id
```

错误做法是：

```text
当前第一个访问的人
→ 自动成为 Owner
```

或者：

```text
agent_id 相等
→ 猜 Owner
```

这会制造越权。

WP2 决定：

```text
Unknown Owner
```

对于：

```text
USER
OPERATOR
```

返回：

```text
hidden 404
```

ADMIN：

```text
按 Policy 访问
```

所以原则是：

> 不知道对象属于谁时，不能猜；安全边界应该 Fail Closed。

------

# 16. 为什么无权访问时有时返回 404，而不是 403

假设攻击者尝试：

```text
GET /runs/R123
```

如果返回：

```text
403
```

它可以确认：

```text
R123 真实存在
```

然后批量枚举：

```text
R124
R125
R126
```

因此 Object-level Authorization 可以：

```text
不存在
和
存在但不属于你
```

统一返回：

```text
404
```

避免 Object Enumeration。

这就是：

```text
Hidden 404
```

------

# 17. Request ID 为什么有用

每个 HTTP Request 都有：

```text
X-Request-ID
```

同时错误 Body：

```text
error.request_id
```

例如用户反馈：

```text
请求失败
request_id=abc123
```

服务端可以直接搜索：

```text
structured logs
```

找到对应请求。

它和：

```text
Run ID
Trace ID
```

不同。

可以简单理解：

```text
Request ID
= 一次 HTTP Request

Run ID
= 一次 Agent Runtime Execution

Trace ID
= 一条跨组件调用链
```

WP2 已确认 401 和 Hidden 404 都会返回 Request ID。

------

# 18. 为什么 /health 和 /readyz 不需要 JWT

如果 Kubernetes 或 Load Balancer：

```text
readiness probe
```

每次都需要：

```text
Bearer JWT
```

会让基础设施健康检查变复杂。

因此：

```text
/health
/readyz
```

是 Public。

业务：

```text
/api/*
```

默认 Protected。

Codex Review 已确认所有当前业务 Route 都位于 `/api/*` 并统一要求 Principal。

------

# 19. Review 中发现的第一个真实安全 Bug

Final Review 发现：

```text
v3/v4 TEST_ONLY evaluation controls
```

虽然已经要求：

```text
Authenticated
```

但没有要求：

```text
ADMIN
```

这些接口可以：

```text
安装 fixture
触发私有 Memory 治理
使用 caller-supplied agent identity
```

所以：

```text
Authenticated USER
```

仍然权限过大。

最终增加：

```text
ADMIN Role Gate
```

并补 403 + Request ID 测试。

这个案例非常适合面试：

> “Authenticated” 只代表知道你是谁，不代表你有权执行高风险管理操作。

------

# 20. Review 中发现的第二个问题

Identity ORM / Migration 出现 Schema Drift。

具体是：

```text
users.version
```

默认值：

```text
代码 / Migration = 0
```

而 WP0 Contract：

```text
DEFAULT = 1
```

同时：

```text
RoleRow metadata
```

缺少 Migration 已有的 Role CHECK。

最终：

```text
Model
Migration
Frozen Contract
```

全部统一。

这说明 Migration 和 ORM Model 必须保持一致，不能只测试：

```text
代码能跑
```

而忽略：

```text
Schema Contract
```

------

# 21. 工程方法类问答

## Q1：Authentication 和 Authorization 有什么区别？

Authentication 判断身份，Authorization 判断这个身份是否有权执行具体操作。

------

## Q2：JWT 验证通过为什么还要查询数据库？

因为 JWT 是有时效的 Credential Snapshot，数据库才是当前 User / Role Authority，可以撤销用户或权限。

------

## Q3：为什么不能信客户端 actor_id？

客户端输入属于 Untrusted Boundary，可以任意篡改；Runtime Actor 必须来自 Server Verified Principal。

------

## Q4：为什么有 RBAC 还需要 Object Ownership？

RBAC 只能判断“USER 能做什么类型操作”，不能判断“这个具体对象是不是 USER 的”。

------

## Q5：为什么 Unauthorized Object 返回 404？

避免暴露对象是否真实存在，降低 Object Enumeration 风险。

------

## Q6：为什么 Principal 做成 Immutable？

身份一旦通过 Authentication Boundary 建立，后续业务代码不应该偷偷修改用户 ID 或 Role。

------

## Q7：为什么 API 只保存公钥？

因为 API 只负责验证 Token，不负责生产签发；私钥和资源服务器分离可以缩小 Secret 暴露范围。

------

## Q8：为什么不在本项目里直接做 Password Login？

当前目标是 Resource Server Authentication / Authorization，不是建设完整 IAM 或 OAuth Authorization Server。

------

## Q9：OPERATOR 和 ADMIN 有什么区别？

OPERATOR 面向平台运维，不应天然获得所有业务敏感数据权限；ADMIN 才是平台级高权限身份。

------

## Q10：Object Ownership 为什么不能放 RunRegistry？

RunRegistry 是 Process-local Runtime State Owner，而 Ownership 是需要跨请求持久化的 Security Fact，二者生命周期和 Authority 不一样。

------

# 22. 30 秒面试回答

我给 LocalAgent 补了一套完整的 HTTP 身份和权限边界。认证使用 EdDSA JWT，API 只持有公钥，AuthService 会验证 Signature、Issuer、Audience、时间 Claims 和 Subject，然后再查询 PostgreSQL 的用户和角色，最终生成不可变 Principal。

授权上不仅做了 USER、OPERATOR、ADMIN 的 RBAC，还增加了服务端持久化 Object Ownership，Run、Conversation、Memory 和 Approval 都不能再相信客户端传入的 actor_id 或 agent_id。普通用户访问他人对象会返回隐藏 404，避免对象枚举。所有业务 `/api/*` 默认需要认证，health/readiness 保持公开，同时统一加入 Request ID 和安全错误投影。

------

# 23. 2 分钟面试回答

LocalAgent 原来更多是一个本地 Agent Runtime，HTTP 层没有完整可信的 Human Identity，所以我在 Stage6 给它补了一套 Authentication 和 Authorization 体系。

认证使用 EdDSA JWT。AuthService 不只是 decode Token，而是固定算法并验证 Signature、Issuer、Audience、sub、jti、iat、nbf、exp 等 Claims，然后再读取 PostgreSQL 当前 User 和 Role。JWT 中的 Role 只能是数据库当前 Role Assignment 的子集，因此 Token 本身不能绕过数据库把自己升级成 ADMIN。验证完成后生成 Frozen Principal，后续业务代码只信 Principal，不再信 Request Body 里的 actor_id、user_id 等字段。

授权分成两层。第一层是 USER、OPERATOR、ADMIN 的 RBAC，第二层是 Object Ownership。PostgreSQL 中持久化 Run 和 Conversation 的 Owner，Memory 跟随 Conversation Ownership，Approval 则在执行前检查对应 Run Owner。普通用户访问别人的对象会返回隐藏 404，避免泄露对象是否存在。

这里我还特别区分了 Ownership Authority 和 Runtime State Authority。Ownership 表只回答“对象属于谁”，RunRegistry、AgentState、Approval Controller 和 Execution Claim 仍由原 Runtime 管理，没有为了权限系统再创建第二套 Runtime Authority。

Final Review 还发现一个真实权限问题：部分 TEST_ONLY Evaluation API 原来只要求 Authenticated，普通 USER 仍然可以进入高权限控制面，后来直接收紧成 ADMIN-only，并补了 403 和 Request ID 回归测试。

------

# 24. 高频追问 + 简答

### JWT 有签名是不是就可以完全信任里面所有内容？

不能。签名证明 Token 没被篡改，还必须检查 Issuer、Audience、Expiry 等 Claims，并结合当前数据库权限。

### 为什么不用 HS256？

不是不能用；本项目使用 EdDSA 是为了让 Issuer 持有私钥，而 API 只持有公钥，实现签发和验证职责分离。

### Token 被撤权怎么办？

数据库仍保存当前 Role Assignment，旧 Token 中已经失效的 Role 不会被接受。

### JWT 过期为什么不直接返回底层异常？

底层异常属于内部实现，HTTP 只应该返回稳定 Typed Error，避免泄露验证细节。

### USER 为什么不能操作别人的 Approval？

Approval 是 Run 的派生操作，必须先判断 Principal 是否拥有对应 Run 或具有明确的高权限 Role。

### Object Ownership 是不是新的 Runtime State？

不是。它只是持久化 Security Binding，不接管 AgentState、Run 生命周期或 Execution Claim。

### 为什么历史对象不自动归当前用户？

没有可靠 Ownership Evidence 时自动赋权可能导致越权，所以默认 Fail Closed。

### Request ID 能代替 Trace ID 吗？

不能。Request ID 标识单次 HTTP 请求，Trace ID 用于跨组件调用链。

------

# 25. Bad Case / Failure Scenario

## Bad Case 1：直接信 actor_id

```text
USER Token
+
actor_id = admin
```

如果 Runtime 信 Body：

```text
Privilege Escalation
```

正确：

```text
actor = Principal.user_id
```

------

## Bad Case 2：只做 JWT，不做对象授权

```text
USER A JWT valid
```

然后：

```text
GET /runs/B_RUN
```

如果只判断：

```text
authenticated = true
```

USER A 就能读取 USER B 的对象。

正确：

```text
AuthN
+
RBAC
+
Object Ownership
```

------

## Bad Case 3：只信 JWT roles

用户过去是：

```text
ADMIN
```

Token 有效期 15 分钟。

数据库已经撤销 ADMIN。

如果 API 只信 Token：

```text
旧权限继续有效
```

当前：

```text
JWT Role
必须匹配 DB current assignment
```

------

## Bad Case 4：历史 Run 没 Owner 就归当前用户

攻击者请求一个旧 Run。

服务端：

```text
no owner
→ bind current user
```

攻击者就可能抢占历史对象。

正确：

```text
Unknown owner
→ USER deny
```

------

## Bad Case 5：所有认证用户都能访问管理 API

```text
Authenticated
≠
Authorized
```

WP2 Final Review 实际发现过这一问题，并将高风险 Evaluation Controls 改成 ADMIN-only。

------

# 26. Truth Boundary

当前真实完成：

```text
✅ EdDSA JWT Authentication
✅ Signature Validation
✅ Algorithm Whitelist
✅ Issuer Validation
✅ Audience Validation
✅ Time Claims Validation

✅ PostgreSQL users
✅ PostgreSQL roles
✅ PostgreSQL user_roles

✅ Frozen Principal
✅ USER / OPERATOR / ADMIN

✅ Object Ownership
✅ Run Ownership
✅ Conversation Ownership
✅ Memory Ownership
✅ Approval Ownership

✅ Caller actor_id 不可信
✅ Anonymous Private API 禁止

✅ Hidden 404
✅ Request ID
✅ Typed Auth Errors

✅ Real PostgreSQL Identity Tests
✅ Real HTTP Authorization Chain

✅ Final Security Review
```

Final Review 明确确认这些核心 Auth / Ownership Contract 均成立。

尚未实现：

```text
❌ Password Login
❌ Refresh Token
❌ OAuth Authorization Server
❌ Tenant Model
❌ IAM Admin UI
❌ Redis Rate Limiter
```

Redis 属于 WP3。

------

# 27. Completion Boundary

WP2 最终：

```text
WP2_REVIEW_STATUS = PASS

P0 = 0
BLOCKING_P1 = 0

JWT_AUTHENTICATION_CONFIRMED = YES
PRINCIPAL_AUTHORITY_CONFIRMED = YES
IDENTITY_POSTGRESQL_CONFIRMED = YES

OBJECT_OWNERSHIP_CONFIRMED = YES

CALLER_IDENTITY_SPOOFING_BLOCKED = YES
ANONYMOUS_PRIVATE_ACCESS_BLOCKED = YES

REAL_HTTP_AUTHORIZATION_CHAIN_CONFIRMED = YES

ARCHITECTURE_REOPEN_REQUIRED = NO

CAN_CLOSE_WP2 = YES
CAN_ENTER_WP3 = YES
```

Review：

```text
BUGS_FOUND = 2
BUGS_FIXED = 2
```

再次证明当前工程流程：

```text
Review
→ Find Bug
→ Fix
→ Targeted Test
→ PASS
```

不需要：

```text
Review → FAIL → 新整改任务 → 再 Review
```

------

# 28. Known Limitation / ACCEPTED_P1

当前最主要的 Accepted Limitation：

```text
Conversation
仍沿用 agent-scoped identity
```

即同一个：

```text
agent_id
```

目前只能绑定一个 Owner。

所以：

```text
USER A
USER B
```

暂时不能自然复用完全相同的逻辑 `agent_id` 并各自获得独立 Conversation Namespace。

但当前行为：

```text
fail closed
```

不会导致：

```text
跨用户读取
```

因此不阻断 WP2。

另一个已明确边界是：

```text
Run Ownership Binding
和
Process-local Runtime Admission
```

不是同一个事务，可能产生没有 Active Run 的 Orphan Binding，但不会产生 Active Run Without Owner。

------

# 29. 面试关键词

优先掌握：

```text
Authentication
Authorization

JWT
EdDSA
Public Key
Private Key

Issuer
Audience
Subject
Expiration
JTI
Algorithm Confusion

Principal
Identity Authority

RBAC
USER
OPERATOR
ADMIN

Object-level Authorization
Object Ownership

Privilege Escalation
Identity Spoofing
Fail Closed
Hidden 404
Object Enumeration

PostgreSQL Identity
Role Assignment

Request ID
HTTP 401
HTTP 403
HTTP 404

Security Boundary
Trust Boundary
```

------

# 30. 本 WP 最值得掌握的 7 个问题

如果面试准备时间有限，优先掌握：

```text
1. Authentication 和 Authorization 到底有什么区别？

2. JWT 验证通过后，为什么还要查 PostgreSQL User / Role？

3. 为什么不能信客户端传入的 actor_id / user_id？

4. RBAC 为什么无法替代 Object-level Authorization？

5. 为什么无权访问别人的资源有时返回 Hidden 404？

6. Ownership Authority 为什么不能和 Runtime State Authority 混在一起？

7. EdDSA 公私钥分离相比对称 JWT 签名有什么工程意义？
```

其中最核心的一句话可以记成：

> **客户端只能提供 Credential，不能声明可信 Identity；身份由服务端认证产生，权限再由 Role 和 Object Ownership 决定。**