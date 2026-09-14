# Stage7-WP3 — Authenticated Cross-repo Evaluation Candidate Gate

## 一、本 WP 解决了什么问题

WP3 解决的不是“给项目加一套 Evaluation”，因为 AgentEvalOps 本来已经拥有完整的评测域能力。

真正的问题是：

> 如何让 AgentEvalOps 通过真实认证调用 LocalAgent production Runtime，拿到真实运行证据，再把 baseline / candidate 比较结果变成能阻断 CI 和 Release 的真实 Candidate Gate。

WP3 最终形成的真实闭环是：

```text
AgentEvalOps
→ dedicated SERVICE principal
→ short-lived scoped Bearer JWT
→ LocalAgent production HTTP
→ AuthService / ownership / scope
→ Coordinated Runtime
→ Final Answer / Artifact Evidence
→ AgentEvalOps ExecutionAttempt / EvaluationResult
→ Baseline / Candidate
→ Comparability Validation
→ RegressionReport
→ ReleaseDecision
→ Candidate Gate
→ CI / Release blocking
```

而不是：

```text
synthetic JSON
→ 假造一个 PASS / FAIL
```

最终：

```ini
WP3_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS
P0_COUNT = 0
BLOCKING_P1_COUNT = 0
ACCEPTED_P1_COUNT = 1
ARCHITECTURE_REOPEN_REQUIRED = NO
```

------

# 二、名词 / 概念速览

### 跨仓评测（Cross-repo Evaluation）

AgentEvalOps 和 LocalAgent 分属两个仓库，但共同完成一次真实 Runtime Evaluation。

### 评测权威（Evaluation Authority）

决定 Dataset、Evaluator、Baseline/Candidate、RegressionReport、ReleaseDecision 的唯一权威。

WP3 中：

```text
AgentEvalOps = Evaluation Authority
```

LocalAgent 不拥有第二套 Evaluation Domain。

### Runtime Truth

LocalAgent 负责真实执行结果、终态、Artifact、Final Answer 和 Runtime provenance。

### 服务主体（Service Principal）

代表 AgentEvalOps 这个服务本身访问 LocalAgent 的机器身份，而不是模拟普通用户。

### 短期 Bearer JWT（Short-lived Bearer JWT）

AgentEvalOps 调用 LocalAgent 时携带的短期签名凭证。

### 服务权限范围（Service Scope）

限制 Service Principal 只能调用明确允许的接口，例如：

```text
localagent:evaluation:execute
```

### 资源所有权（Resource Ownership）

即使有合法 SERVICE token，也只能操作自己创建/拥有的 Run。

### ExecutionTarget

AgentEvalOps 中负责实际调用被测系统的抽象；本 WP 的 production target 是 `LocalAgentHttpExecutionTarget`。

### Baseline

作为比较基准的已知版本 / 配置 / 运行结果。

### Candidate

待评估、准备发布的新版本 / 新配置。

### 可比性（Comparability）

在计算 regression 前，先确认 baseline 和 candidate 属于同一个可比较实验条件。

### 回归报告（RegressionReport）

汇总 candidate 相对 baseline 的指标退化、critical regression 等信息。

### 发布决策（ReleaseDecision）

最终输出 Candidate 是否允许进入下一步发布。

### Candidate Gate

根据真实 Evaluation 结果决定 CI 是否通过的自动化门禁。

### Known-good Candidate

预期不会产生 regression 的 candidate，用于证明 Gate 能正常 PASS。

### Known-bad Candidate

在保持 comparability 的前提下故意制造质量退化，用于证明 Gate 能真正 FAIL。

------

# 三、为什么 WP3 不能在 LocalAgent 再做一套 Evaluation

现有架构已经明确：

```text
AgentEvalOps owns:
Dataset
Ground Truth
EvaluationRun
ExecutionAttempt
EvaluationResult
Evaluator
Baseline
Candidate
RegressionReport
ReleaseDecision
Candidate Gate
```

LocalAgent 只拥有：

```text
Runtime execution
terminal truth
Artifact / Final Answer evidence
runtime provenance
authentication
runtime resource authorization
```

如果 LocalAgent 再自己实现：

```text
Recall@K
MRR
RegressionReport
ReleaseDecision
```

就会出现两个 Evaluation Authority。

以后很容易发生：

```text
AgentEvalOps: FAIL
LocalAgent: PASS
```

然后没人知道谁才是真正 Release Gate。

所以 WP3 的正确方向不是：

> “补齐 LocalAgent Evaluation”。

而是：

> “让 AgentEvalOps 真正消费 LocalAgent production evidence”。

------

# 四、为什么一定要 Dedicated Service Principal

错误方案：

```text
AgentEvalOps
→ 冒充某个用户 JWT
```

或者：

```text
AgentEvalOps
→ ADMIN token
```

都不合理。

因为服务调用和用户调用是不同的安全主体。

所以 WP3 使用：

```text
dedicated enabled SERVICE principal
+
short-lived signed Bearer JWT
+
database-registered scope
```

LocalAgent 最终验证：

```text
signature
issuer
audience
iat
nbf
exp
jti
database principal
disabled status
principal kind
scope
```

并要求：

```text
localagent:evaluation:execute
```

这意味着：

> AgentEvalOps 是一个独立、可禁用、可最小授权的机器身份。

------

# 五、为什么不能直接给 ADMIN Token

这次 Sol Gate 实际发现过这个问题的变体：

原实现存在：

```text
HUMAN / ADMIN
```

绕过 evaluation service scope 的路径。

同时 SERVICE principal 还能访问普通 LocalAgent API。

最后都被修掉：

```text
evaluation endpoint
→ SERVICE only

SERVICE
→ 只允许 evaluation endpoint
   + owned-run cancel

普通 chat/API
→ 403
```

这体现一个典型安全原则：

> Service-to-service Auth 不只是“认证成功”，还必须做最小权限授权。

------

# 六、Authentication 和 Authorization 的区别

WP3 中这两个概念分得很清楚。

## Authentication

回答：

> 你是谁？

例如：

```text
SERVICE principal = agentevalops-ci
```

验证：

```text
JWT signature
issuer
audience
exp
database principal
disabled status
```

## Authorization

回答：

> 你能做什么？

例如：

```text
localagent:evaluation:execute
```

以及：

```text
只能 cancel 自己拥有的 Run
```

所以：

```text
Missing Bearer
→ 401

Valid identity but missing scope
→ 403
```

这是非常典型、面试常问的边界。

------

# 七、为什么 Cancel 还需要 Ownership

即使 AgentEvalOps 有：

```text
localagent:evaluation:execute
```

也不能变成：

```text
“能取消整个 LocalAgent 的所有 Run”
```

真实 Gate 验证：

```text
service principal 取消自己创建的 Run
→ accepted

另一个 service principal 取消该 Run
→ fail closed
```

所以：

```text
Scope
```

解决：

> 这个身份是否有某类操作权限？

```text
Ownership
```

解决：

> 它是否能对这个具体资源执行操作？

两者不能混为一谈。

------

# 八、为什么 Credential 由 Composition 注入，而不是 Target 自己读环境变量

错误设计：

```python
class LocalAgentHttpExecutionTarget:
    token = os.environ["TOKEN"]
```

这会让：

```text
Domain / Adapter
```

直接依赖全局环境。

问题包括：

```text
测试困难
credential ownership 模糊
多个 target 无法隔离
隐藏配置依赖
secret 更容易泄漏
```

WP3 的链路是：

```text
Settings
→ Resolver / Composition
→ LocalAgentHttpExecutionTarget
```

并使用：

```text
SecretStr
```

保存 service credential。

execute 和 cancel 复用同一个 Bearer contract。

这属于典型的：

> Configuration belongs to Composition Root, not business adapter internals.

------

# 九、为什么之前的 E2E 不能算 Production E2E

WP3 审计发现旧集成方式用了：

```text
lifespan="off"
没有 production AuthService
```

这种测试最多只能证明：

> HTTP 协议大概通了。

它不能证明：

```text
真实 lifespan
真实 DB
真实 Redis
真实 Auth middleware
真实 Service Principal
真实 Coordinated Runtime
```

都能组合工作。

最终 WP3 的生产 E2E 实际启动：

```text
AgentEvalOps EvaluationLoop
→ LocalAgentSubprocessProvisioner
→ uvicorn server:app
→ production lifespan
→ AuthService
→ PostgreSQL identity
→ Redis
→ evaluation-execute
→ Coordinated Runtime
```

------

# 十、为什么可以使用 Deterministic Provider

Production E2E 并不等于：

```text
必须调用真实 DeepSeek
```

WP3 测的是：

```text
Cross-repo
Auth
Runtime Composition
Persistence
Evaluation
Candidate Gate
```

不是测试模型本身。

所以最终使用：

```text
bounded local OpenAI-compatible deterministic provider
```

只替代外部模型调用。

其余：

```text
LocalAgent server
FastAPI
middleware
AuthService
PostgreSQL
Redis
RuntimeFactory
HTTP adapter
```

都是真实 production path。

这是一种很典型的测试设计：

> Fake nondeterministic dependency, keep system integration real.

------

# 十一、EvaluationAttempt 为什么必须持久化

如果 Evaluation 只是：

```text
发 HTTP
→ 拿 response
→ 算个 score
```

那无法审计：

```text
当时执行的是谁？
哪个 Run？
什么 outcome？
是否超时？
Artifact 来自哪里？
```

WP3 的真实链路先：

```text
create Attempt
→ claim
→ start
→ execute LocalAgent
→ record outcome
→ finalize
```

最终重新读取 Attempt，确认：

```text
status = TERMINAL
execution_outcome_kind = SUCCESS
run_id preserved
artifact = localagent-run://...
```

因此 Evaluation 结果是有执行 provenance 的，而不是一个孤立分数。

------

# 十二、为什么 Baseline / Candidate 必须先做 Comparability

这是 WP3 最重要的 Evaluation 知识点之一。

假设：

```text
Baseline:
Dataset A
Index v1

Candidate:
Dataset B
Index v2
```

即使 Candidate 分数下降，也不能直接说：

> Candidate 回归了。

因为变量已经变了。

所以 comparison 前必须检查：

```text
dataset identity
suite identity
source/index identity
execution profile
evaluator identity
```

WP3 的真实测试还验证了：

```text
source_manifest_sha256 mismatch
→ WP3IdentityMismatch
→ fail closed
```

原则是：

> Regression only makes sense after comparability is proven.

------

# 十三、Known-bad Candidate 为什么特别重要

很多 Evaluation 系统只证明：

```text
good candidate → PASS
```

但这无法证明 Gate 真能抓住回归。

所以必须做：

```text
known-bad candidate → FAIL
```

而且这个 known-bad 不能作弊。

Sol 实际否掉过 Luna 的错误方案：

> 修改 candidate `expected_output` 来制造 FAIL。

因为这样改变了 Ground Truth，不再是同一个实验条件。

最后正确实现是：

```text
同一个 Dataset
同一个 Case
同一个 expected_output
同一个 evaluator
同一个 target/profile

baseline output correct
good candidate output correct
bad candidate output degraded
```

最后分数：

```text
baseline = 1.0
good = 1.0
bad = 0.0
```

这才是真正的：

> Candidate quality regression.

------

# 十四、RegressionReport 和 ReleaseDecision 的关系

WP3 并没有自己手写：

```text
if score < xxx:
    fail
```

而是复用现有 AgentEvalOps Authority：

```text
persisted baseline result
+
persisted candidate result
→ EvaluationComparisonService
→ RegressionReportService
→ ReleaseDecision
```

Known-bad 最终：

```text
regression_count = 1
critical regression
→ ReleaseDecision.FAIL
```

Known-good：

```text
regression_count = 0
→ ReleaseDecision.PASS
```

这样：

```text
CI
```

并不自己解释 Evaluation Domain。

它只消费：

```text
ReleaseDecision
```

------

# 十五、为什么 CLI 不能成为第二 Authority

Candidate Gate CLI：

```text
release_gate.py
```

不应该自己重新实现一遍 regression 算法。

最终 canonical mode 的作用只是：

```text
读取 persisted run IDs
→ 调已有 comparison service
→ 调 RegressionReportService
→ 映射 ReleaseDecision 到 exit code
```

例如：

```text
PASS → 0
business FAIL → 2
technical failure → 1
```

所以 CLI 是：

```text
delivery adapter
```

不是：

```text
evaluation authority
```

------

# 十六、为什么 Synthetic Gate 不够

原来的 CI：

```text
release_gate --synthetic --scenario ...
```

只能证明：

> 如果输入一个 synthetic FAIL，CLI 会返回失败。

但不能证明：

```text
真实 LocalAgent candidate
→ 真正 Evaluation regression
→ CI FAIL
```

所以最终 canonical workflow 被改成：

```text
启动 PostgreSQL / Redis
→ 启动 LocalAgent production composition
→ 创建 ephemeral SERVICE identity
→ 生成短期 token
→ 跑真实 baseline/candidate
→ persisted results
→ canonical release_gate
```

Synthetic path 仍保留：

```text
unit / developer smoke
```

但不再是 Release Authority。

------

# 十七、为什么 CI 必须同时测 Good 和 Bad

只测：

```text
good → PASS
```

只能证明系统能成功。

只测：

```text
bad → FAIL
```

也可能说明系统坏了。

所以 WP3 最终验证：

```text
real good candidate
→ exit 0

real bad candidate
→ exit 2
```

并且 JSON evidence：

```text
synthetic=false
authority=RegressionReportService
```

这相当于验证了 Gate 的：

```text
positive path
+
negative path
```

------

# 十八、为什么 Release Workflow 要显式依赖 Candidate Gate

如果 Candidate Gate 跑了，但 Release：

```text
不依赖它
```

那么它只是一个 dashboard。

真正 Gate 必须：

```text
candidate-gate
↓
PASS
↓
build / push
```

Final WP3 中：

```text
release.yml
```

新增了：

```text
candidate-gate
```

而 Docker build：

```text
needs: candidate-gate
```

所以 Candidate regression 会在 build/push 前阻断 release。

------

# 十九、为什么不把 LLM Judge 放进普通 CI

LLM Judge 存在：

```text
non-determinism
latency
cost
model drift
prompt drift
API availability
```

如果把它放进普通 hard gate：

```text
PR 今天 PASS
明天可能 FAIL
```

而且 CI 成本和稳定性都会变差。

所以 WP3 选择：

```text
deterministic evaluator
→ hard gate
```

LLM Judge / large benchmark：

```text
manual
scheduled
report-only
```

这是非常合理的 Production Evaluation 分层。

------

# 二十、工程方法类问答

## Q1：为什么 Evaluation Authority 放 AgentEvalOps，而不是 LocalAgent？

因为 Evaluation 是独立领域：

```text
Dataset
Evaluator
Baseline/Candidate
Regression
ReleaseDecision
```

不应该和 Agent Runtime execution truth 混在一起。

LocalAgent 只提供真实执行 evidence。

------

## Q2：为什么跨仓调用需要 Dedicated Service Principal？

因为服务到服务调用不应该冒充用户。

独立 Service Principal 可以：

```text
最小权限
单独禁用
单独审计
单独轮换 credential
```

------

## Q3：为什么 service token 不能给 ADMIN？

因为 AgentEvalOps 实际只需要：

```text
evaluation execute
owned-run cancel
```

ADMIN 会违反 least privilege。

------

## Q4：为什么使用短期 JWT 而不是长期 API Key？

短期 JWT：

```text
有过期时间
可验证 issuer/audience
可携带 scope
可绑定 service identity
```

长期 static key 一旦泄漏，风险窗口更大。

当前第一版没有在线 refresh，但仍是 short-lived token + controlled rotation。

------

## Q5：为什么 Production E2E 不调用真实大模型？

因为 WP3 的测试目标是系统集成，而不是模型质量。

模型是最不确定、最昂贵的 dependency，所以替换成 deterministic provider，同时保留其他 production components。

------

## Q6：为什么 baseline/candidate 比较前必须做 comparability？

因为如果 Dataset、Evaluator、Index 或 execution profile 不一致，分数变化不能归因于 candidate 本身。

------

## Q7：为什么 known-bad candidate 不能改 Ground Truth？

因为那样测试变量变了。

真正 regression 必须：

```text
same Ground Truth
same evaluation conditions
only candidate output quality degrades
```

------

## Q8：Candidate Gate 为什么复用 RegressionReportService？

因为 CI 不应该再次定义“什么叫 regression”。

Domain Authority 只应该有一个。

------

## Q9：Synthetic Gate 有什么价值？

适合：

```text
unit test
CLI exit-code smoke
developer local test
```

但不能替代 production-target Release Gate。

------

## Q10：为什么 Release workflow 还要显式 needs candidate gate？

因为如果 workflow 没有 dependency，即使 candidate gate FAIL，Release 仍可能继续。

这就不是真正的 Gate。

------

# 二十一、30 秒面试总结

我们项目里 Evaluation 是独立仓 AgentEvalOps 负责的，LocalAgent 只提供 Runtime Truth。之前两边虽然有 HTTP adapter，但 production LocalAgent 已经要求 JWT，AgentEvalOps 没有真实 service identity，而且 CI 的 Candidate Gate 主要还是 synthetic fixture。

我后来补了 dedicated SERVICE principal、短期 scoped Bearer JWT 和 owned-run authorization，让 AgentEvalOps 可以通过真实 production HTTP 调 LocalAgent，再把 Runtime Artifact 和 Final Answer 持久化成 EvaluationAttempt/Result。

然后我们用同一 Dataset、同一 Ground Truth 和同一 evaluator 跑真实 baseline、good candidate 和 known-bad candidate，只有 bad candidate 的真实输出退化，最终通过现有 RegressionReportService 得到 ReleaseDecision.FAIL。这个结果再进入 canonical CLI 和 CI，Release build 显式依赖 Candidate Gate，所以真实回归会直接阻断发布。

------

# 二十二、2 分钟面试总结

我们 Evaluation 的架构是跨仓的。AgentEvalOps 是 Evaluation Authority，拥有 Dataset、Evaluator、Baseline/Candidate、RegressionReport 和 ReleaseDecision；LocalAgent 只负责真实 Runtime execution 和 Artifact evidence。

之前最大的问题是这个闭环没有真正 production 化。LocalAgent 已经有 JWT Auth，但 AgentEvalOps 的 HTTP target 没有 service credential，旧 E2E 还会关掉 production lifespan 和 Auth，所以实际上不能证明跨仓生产链可用。

我先给 AgentEvalOps 建了 dedicated SERVICE principal，使用 short-lived signed Bearer JWT，并限制 scope 只能调用 evaluation execute 和取消自己拥有的 Run。Credential 由 Settings 和 composition 注入 ExecutionTarget，不让 adapter 自己读环境变量。

之后把 E2E 改成真正启动 LocalAgent production FastAPI/lifespan、PostgreSQL、Redis 和 AuthService，只把外部模型替换成 deterministic provider。AgentEvalOps 通过真实 HTTP 调用后，把结果持久化成 ExecutionAttempt 和 EvaluationResult。

最后做了真实 baseline/candidate gate。Baseline、good candidate 和 bad candidate 使用完全相同的 Dataset、Ground Truth、ExecutionTarget 和 evaluator。Bad candidate 只让真实 model output 退化，所以属于真正可比较的 regression。EvaluationComparisonService 和 RegressionReportService 最终产生 ReleaseDecision.FAIL，canonical CLI 返回 exit 2。

CI workflow 也不再用 synthetic fixture，而是自己启动真实 test stack、生成 persisted runs，再执行 canonical gate。Release workflow 的 build 显式依赖 candidate gate，所以 Evaluation regression 会真正阻断发布。

------

# 二十三、高频追问

## 1. 为什么不把 AgentEvalOps 合并进 LocalAgent？

因为 Runtime 和 Evaluation 是不同领域。

拆仓可以独立演进，也能避免 Runtime 同时拥有“自己执行、自己评分、自己决定能不能发布”的过强 Authority。

------

## 2. 如果 Service Token 泄漏怎么办？

第一版 token 是短期的，并绑定独立 service principal。

可以：

```text
disable principal
rotate credential
wait token expiration
```

当前还没有自动在线 refresh。

------

## 3. 为什么 foreign Run cancel 返回 404，而不是 403？

这是 fail-closed / non-disclosure 的资源访问语义之一。

避免暴露：

```text
“这个 run 存在，只是你无权访问”
```

真实实现采用当前 ownership contract。

------

## 4. 如果 Candidate 和 Baseline provenance 不同怎么办？

不比较。

直接进入：

```text
NOT_COMPARABLE / fail closed
```

而不是把差异误判成 regression。

------

## 5. 为什么 Gate CLI exit code 还区分 1 和 2？

因为：

```text
1
= technical error

2
= business release rejection
```

这样 CI 和诊断工具能区分：

> 系统坏了

和：

> Candidate 真回归了

------

## 6. 为什么 known-bad candidate 这么重要？

因为它验证 Gate 真能检测回归，而不是只能证明 happy path。

------

## 7. 为什么不直接比较 final score？

因为 Regression 需要：

```text
comparability
critical cases
metric semantics
threshold
```

所以必须经过已有 Evaluation Domain Service，而不是 CLI 直接比较两个数字。

------

# 二十四、Bad Case

## Bad Case 1：AgentEvalOps 使用 ADMIN Token

简单，但权限过宽。

一旦 token 泄漏，可以访问无关 Runtime API。

------

## Bad Case 2：关闭 Auth 跑 E2E

```text
lifespan=off
auth disabled
```

这种 E2E 不能证明 production composition。

------

## Bad Case 3：Candidate Gate 只吃 Synthetic JSON

能证明 CLI 判断逻辑，但不能证明：

```text
真实 Agent regression
→ 真正阻断 Release
```

------

## Bad Case 4：Known-bad 通过修改 Ground Truth

```text
baseline expected=A
candidate expected=B
```

这不是 Candidate regression，只是测试条件变化。

Sol 实际拒绝过这个实现。

------

## Bad Case 5：Baseline / Candidate Provenance 不同还强行比较

可能把：

```text
Dataset change
Index change
Evaluator change
```

误判成 candidate quality regression。

------

## Bad Case 6：CI Gate 跑了，但 Release 不依赖它

```text
candidate-gate FAIL
build still runs
```

这种只能叫检查，不叫 Gate。

------

## Bad Case 7：CLI 自己实现一套 regression 规则

这样会出现：

```text
Domain says PASS
CLI says FAIL
```

形成第二 Evaluation Authority。

------

# 二十五、这一 WP 最重要的三个知识点

## 第一：Runtime Truth 和 Evaluation Authority 必须分离

```text
LocalAgent
= “发生了什么”

AgentEvalOps
= “这次结果好不好”
```

------

## 第二：Regression 前必须先证明 Comparability

```text
Comparable
→ 才能讨论 Regression

Not Comparable
→ Fail Closed
```

------

## 第三：Evaluation 只有进入 CI / Release dependency 才是真 Gate

```text
Evaluation Report
```

本身不是 Gate。

真正 Gate 是：

```text
ReleaseDecision.FAIL
→ CI non-zero
→ Release build 不运行
```

------

# 二十六、Truth / Completion Boundary

## 已真实完成

### Evaluation Authority Preserved

AgentEvalOps 保持唯一 Evaluation/Candidate Gate Authority。

### Dedicated Service Principal

LocalAgent 支持独立 SERVICE principal。

### Short-lived Bearer JWT

AgentEvalOps 使用短期 signed JWT 调 LocalAgent。

### Evaluation Scope

Service principal 使用：

```text
localagent:evaluation:execute
```

### Owned Run Cancel

只能取消自己拥有的 evaluation Run。

### Credential Injection

Settings → Resolver → ExecutionTarget。

### Real Cross-repo HTTP

真实 AgentEvalOps → LocalAgent production HTTP 已验证。

### LocalAgent Production Composition

真实：

```text
FastAPI
lifespan
AuthService
PostgreSQL
Redis
Coordinated Runtime
```

均进入 E2E。

### EvaluationAttempt Persistence

真实 Runtime outcome 被持久化。

### Baseline / Candidate Execution

baseline、good candidate、bad candidate 都经 production target 执行。

### Comparability Validation

same Dataset / Suite / Target / Evaluator / Ground Truth。

### RegressionReport

Bad candidate 产生真实 regression。

### ReleaseDecision

Good → PASS。

Bad → FAIL。

### Canonical Candidate Gate

真实 persisted run IDs 输入 canonical CLI。

### CI Enforcement

Good：

```text
exit 0
```

Bad：

```text
exit 2
```

### Release Blocking

release build：

```text
needs: candidate-gate
```

------

# 二十七、尚未完成

## Online Service Token Refresh

未实现。

当前是：

```text
short-lived pre-issued token
+
deployment secret injection
+
controlled rotation/restart
```

### LLM Judge Hard Gate

未实现，也刻意不进入 ordinary CI。

### Large Benchmark CI

未进入普通 CI。

### Real DeepSeek/OpenAI CI

未使用。

### Remote GitHub Actions Execution Evidence

本 WP 没有真的提交一次远端 workflow run，而是用：

```text
workflow static assertion
YAML parse
local canonical CLI integration
```

验证 CI contract。

------

# 二十八、面试不能夸大的地方

不要说：

> “我们的 CI 每次都跑真实 DeepSeek。”

应该说：

> “普通 Candidate Gate 使用 deterministic provider 保证 repeatability，真实 LLM Judge 和大型 benchmark 放在非 hard-gate 路径。”

不要说：

> “LocalAgent 自己做 Evaluation。”

应该说：

> “LocalAgent 提供 Runtime evidence，AgentEvalOps 是 Evaluation Authority。”

不要说：

> “任何两个 evaluation run 都可以直接比较。”

应该说：

> “只有通过 identity/provenance comparability validation 的 baseline/candidate 才允许生成 regression。”

不要说：

> “我们实现了完整 OAuth service auth。”

应该说：

> “第一版采用 dedicated service principal + short-lived signed Bearer JWT，没有实现在线 token refresh。”

------

# 二十九、一句话总结

> WP3 的本质不是“把 Evaluation 接上 HTTP”，而是把 **Service Authentication + Production Runtime Evidence + Comparable Baseline/Candidate + Regression Authority + ReleaseDecision + CI Dependency** 串成一个真正能阻断发布的跨仓质量闭环。