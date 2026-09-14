# 1. 名词 / 概念速览

**部署（Deployment）**：Kubernetes 管理长期运行 Pod 副本、更新和故障重建的控制器。

**服务（Service）**：为一组 Pod 提供稳定网络地址；当前 API 使用 ClusterIP。

**任务（Job）**：执行完成后退出的工作负载；当前 Migration 和 Kafka Topic Provisioning 都使用 Job。

**配置映射（ConfigMap）**：保存非敏感运行配置。

**Secret**：保存数据库 DSN、API Key、JWT Key 等敏感配置引用。

**存活探针（Liveness Probe）**：判断进程是否需要被重启。

**就绪探针（Readiness Probe）**：判断 Pod 当前是否应该接收流量或承担工作。

**滚动更新（RollingUpdate）**：旧、新 Pod 短时间并存完成升级。

**重建策略（Recreate）**：先停止旧 Pod，再启动新 Pod，不允许版本重叠。

**安全上下文（SecurityContext）**：限制 Pod 用户、权限、Capabilities、文件系统等运行权限。

**资源请求 / 限额（Requests / Limits）**：向调度器声明基础资源需求并限制资源上界。

**优雅终止（Graceful Termination）**：Pod 被终止时给予应用时间执行 shutdown。

------

# 2. 当前 WP 真实实现

当前 Kubernetes Base 管理：

```text
API Deployment
Outbox Publisher Deployment
Evaluation Worker Deployment

Migration Job
Kafka Init Job

API ClusterIP Service
```

Canonical Base 没有把 PostgreSQL、Redis、Kafka 伪装成生产 Kubernetes 集群，而是把它们定义为外部基础设施；本地 Overlay 才额外提供单节点 PostgreSQL、Redis、Kafka 做集成测试。

真实 Docker Desktop Kubernetes 已验证：

```text
Migration Job          Complete
Kafka Init Job         Complete

API                    Available
Publisher              Available
Worker                 Available

/health                200
/readyz                200
/metrics               200
```

同时真实完成 API / Worker Pod 删除重建、Publisher / Worker Rollout、Worker `1 → 2 → 1` 和 Kafka 故障恢复。

------

# 3. 架构与调用链

当前 Kubernetes 并没有改变应用架构：

```text
Client
  ↓
Kubernetes Service
  ↓
API Pod
  ↓
PostgreSQL Job + Outbox
  ↓
Publisher Pod
  ↓
Kafka
  ↓
Worker Pod
  ↓
PostgreSQL Result
```

部署层负责的是：

```text
Scheduling
Restart
Rollout
Probe
Resource Governance
Configuration
```

业务正确性仍然来自：

```text
PostgreSQL Authority
Kafka Consumer Group
Lease / Fencing
Consumer Dedup
Unique Result
Runtime Owner
```

Final Review 明确确认：**Kubernetes 不是第二套 Correctness Authority。**

------

# 4. 为什么 API 固定单副本

当前 API：

```yaml
replicas: 1
strategy:
  type: Recreate
```

原因不是 Kubernetes 做不到多副本，而是当前 Agent Runtime 仍然存在 Process-local Owner。

如果使用普通 RollingUpdate：

```text
old API Pod
+
new API Pod
```

会短时间同时 Active。

这可能破坏当前：

```text
Run ownership
Approval ownership
Runtime lifecycle
```

边界。

所以当前选择：

```text
正确性
>
零停机
```

最终明确：

```ini
API_REPLICAS = 1
API_ROLLOUT_OVERLAP = NO
API_HORIZONTAL_SCALE_SUPPORTED = NO
```



这是 WP8 最有价值的架构点之一：

> Kubernetes 能创建多个 Pod，但不代表应用天然支持分布式多副本。

------

# 5. 为什么 Worker 可以横向扩展

Worker 与 API 不一样。

Worker 已经有：

```text
Kafka Consumer Group
PostgreSQL Worker Lease
Fresh Claim Token
Fencing
Consumer Dedup
Unique Result
```

因此多个 Worker 同时运行时，正确性有分布式机制保护。

WP8 真实验证：

```text
Worker 1
→ 2 Ready
→ 1
```

成功。

因此可以说：

> Worker 的横向扩展基础已经真实验证。

但不能说：

```text
无限扩容
HPA ready
capacity benchmark complete
```

------

# 6. 为什么 Publisher 可以 RollingUpdate

Publisher 发生旧、新 Pod 短时间重叠时，仍然依赖：

```text
PostgreSQL Outbox Claim
Lease
Fresh Claim Token
Fencing
```

所以两个 Publisher 并存，不代表同一 Outbox 可以无限重复产生 Durable Effect。

因此 Publisher 可以使用：

```text
RollingUpdate
maxUnavailable=0
maxSurge=1
```

而 API 不能直接套同样策略。

核心原则：

> Rollout Strategy 必须由应用自己的并发正确性决定，而不是所有 Deployment 都统一使用 RollingUpdate。

------

# 7. Migration 为什么还是独立 Job

当前只有：

```text
localagent-migrate
```

负责：

```text
alembic upgrade head
```

没有：

```text
API initContainer migration
Publisher initContainer migration
Worker initContainer migration
```



这样 Migration Owner 仍然唯一。

部署顺序：

```text
Infrastructure Ready
↓
Migration Job Complete
↓
Kafka Init Job Complete
↓
Application Deployments
```

而不是每个 Pod 启动时自己修改数据库 Schema。

------

# 8. 为什么 Kafka Topic 也由独立 Job 管理

Topic：

```text
evaluation.jobs.v1
evaluation.jobs.v1.dlq
```

由：

```text
localagent-kafka-init
```

独立 Job 显式创建。

Kafka Auto-create 仍然关闭。

这样能避免：

```text
topic 名拼错
→ Kafka 自动创建错误 topic
→ 系统表面继续运行
```

Topic Provisioning 也是 Deployment Authority 的一部分。

------

# 9. Liveness 和 Readiness 在 Kubernetes 中怎么使用

API：

```text
Liveness / Startup
→ /health

Readiness
→ /readyz
```

Publisher / Worker：

```text
Readiness
→ WP6 healthcheck CLI
```

但是 Publisher / Worker **没有**把 dependency-aware readiness 当成 liveness。

为什么？

例如 Kafka 挂了：

```text
Worker process still alive
Kafka unavailable
```

正确结果：

```text
Worker Not Ready
```

而不是：

```text
Liveness failed
→ Kubernetes restart
→ Kafka still down
→ restart loop
```

------

# 10. Kafka Down 为什么 API 仍 Ready

真实 Kubernetes 故障验证：

```text
Kafka replicas = 0
```

结果：

```text
API                Ready
Publisher          Not Ready
Worker             Not Ready
```

Kafka 恢复后：

```text
Kafka Init
→ Topics confirmed
→ Publisher Ready
→ Worker Ready
```



原因仍然来自 Transactional Outbox：

```text
API
↓
PostgreSQL Job + Outbox
↓
commit
```

Kafka 不在 API 同步 Durable Admission 链路。

------

# 11. Kubernetes SecurityContext 做了什么

当前 Application Pod / Job：

```text
runAsNonRoot = true
runAsUser = 10001
runAsGroup = 10001

allowPrivilegeEscalation = false

capabilities:
  drop:
    - ALL

seccompProfile:
  RuntimeDefault

readOnlyRootFilesystem = true
```

同时：

```text
/tmp
temporary Chroma
```

通过 `emptyDir` 提供合法可写目录。

更重要的是这些不是单纯 YAML：

真实 Pod 已验证：

```text
uid=10001
gid=10001
read-only root
application Ready
```

------

# 12. 为什么关闭 ServiceAccount Token 自动挂载

当前：

```yaml
automountServiceAccountToken: false
```

并且没有：

```text
Role
ClusterRole
RoleBinding
ClusterRoleBinding
```



原因是应用根本不需要访问 Kubernetes API。

如果默认挂 Token，就相当于给应用一个没必要的 Cluster Credential。

原则：

> 应用不需要 Kubernetes API，就不要给 Kubernetes API 身份。

------

# 13. ConfigMap 和 Secret 如何分工

ConfigMap：

```text
Kafka address
Redis address
Topic name
Runtime flags
Observability config
```

Secret：

```text
Database DSN
Remote API Key
JWT Key Material
Kafka Credential（如启用）
```

真实 Secret 不进入 Repository。

`secret.example.yaml` 只有 Placeholder，而且不进入 Production Kustomization。

------

# 14. Kubernetes 为什么不能保证部署顺序

Kubernetes：

```text
kubectl apply A
kubectl apply B
kubectl apply C
```

不代表：

```text
A 完成
再执行 B
再执行 C
```

所以项目使用 PowerShell Deployment Script 显式控制：

```text
Context Check
↓
Config / Service
↓
Local Infrastructure
↓
Wait
↓
Secret Validation
↓
Migration
↓
Wait Complete
↓
Kafka Init
↓
Wait Complete
↓
Application Deployments
↓
Rollout Wait
```



这其实比“会写 Deployment YAML”更有工程价值。

------

# 15. Context Safety 为什么重要

Final Review 实际发现了一个 Blocking P1。

原来的判断使用类似：

```text
context name contains "test" / "dev" / "local"
```

这种逻辑会让：

```text
contest-prod
latest-production
device-prod
```

意外通过。

最后改成：

```text
docker-desktop
minikube
kind
kind-*

或有明确分隔符的：
local
test
dev
```

其他 Context：

```text
必须显式 -AllowNonLocalContext
```

这属于典型的：

> Deployment Safety Guardrail。

------

# 16. Resource Requests / Limits 是什么

当前：

```text
API
Publisher
Worker
Migration
Kafka Init
```

都设置了：

```text
requests
limits
```

Worker Baseline 高于 Publisher。

但这些值目前只是：

```text
initial baseline
```

不是：

```text
production capacity benchmark
```

不能因为 YAML 里写了 CPU/Memory 就说完成容量规划。

------

# 17. Graceful Termination 当前边界

当前：

```text
API        45s
Publisher  45s
Worker     75s
```



但是：

```text
active long Evaluation
```

不保证一定在 75 秒内完成。

如果 Worker 被终止：

```text
Kafka Redelivery
+
PG Lease Expiry
+
Fencing
+
Dedup
```

负责恢复。

这比强行：

```text
terminationGracePeriodSeconds = 3600
```

更合理。

------

# 18. 工程构建方法类问答

### Kubernetes 上了以后，为什么 API 还不能多副本？

因为应用的 Runtime Ownership 仍有 Process-local 状态，Kubernetes 只负责调度，不会自动解决分布式 Ownership。

### 为什么 Worker 可以扩容？

因为 Worker 已经有 Kafka Consumer Group、PostgreSQL Lease/Fencing、Dedup 和 Unique Result 等分布式正确性机制。

### 为什么 API 用 Recreate，而 Worker 用 RollingUpdate？

API 不允许两个 Active Runtime Pod 重叠；Worker 已具备多实例并发正确性。

### 为什么 Migration 不用 initContainer？

否则每个应用 Pod 都可能执行 Migration，Migration Owner 会再次分散。

### 为什么 Readiness 不能直接作为 Liveness？

外部依赖故障会触发无意义 Pod Restart，形成 Restart Storm。

### 为什么 Kafka Down 不影响 API Ready？

因为 API 通过 PostgreSQL Job + Transactional Outbox Durable Accept 请求，Kafka 属于后台异步链路。

### Kubernetes 会自动解决 Exactly-once 吗？

不会。当前仍然是 At-Least-Once + Dedup / Fencing / Idempotency。

------

# 19. 30 秒面试回答

我把 Agent 后端进一步部署到了真实 Kubernetes。这里我没有简单把所有组件都做成 Deployment，而是按照 Runtime Contract 映射。

API 当前还有 Process-local Owner，所以固定单副本并使用 Recreate，避免升级时两个 Runtime 同时 Active；Publisher 和 Worker 因为已经有 PostgreSQL Lease/Fencing、Kafka Consumer Group 和 Dedup，所以可以 RollingUpdate，Worker 也真实验证了 `1→2→1` 扩缩容。

Migration 和 Kafka Topic Provisioning 都用独立 Job，Probe 直接复用已有 `/health`、`/readyz` 和 Worker Healthcheck。真实 Kubernetes 上还验证了 Pod 重建、Rollout、SecurityContext，以及 Kafka Down 时 API 仍 Ready、Publisher/Worker Not Ready 的故障语义。

------

# 20. 2 分钟面试回答

Kubernetes 这部分我主要关注的是部署层不能破坏应用自己的 Authority 和 Correctness。

API Runtime 当前还有 Process-local Run/Approval 等 Owner，所以我没有因为用了 Kubernetes 就直接做多副本，而是固定 `replicas=1`，Rollout 使用 Recreate，接受升级时短暂不可用，避免 old/new Runtime 同时 Active。

Publisher 和 Worker 不一样。Publisher 已经有 PostgreSQL Outbox Lease/Fencing，Worker 有 Kafka Consumer Group、PostgreSQL Worker Lease/Fencing、Consumer Dedup 和唯一 Result，所以它们允许 RollingUpdate，Worker 还在真实 Docker Desktop Kubernetes 上验证了 `1→2→1` 的扩缩容。

数据库 Migration 和 Kafka Topic Provisioning 都拆成独立 Job，由部署脚本显式等待完成后再启动应用。Probe 直接复用应用已有 Contract，API `/health` 做 Liveness、`/readyz` 做 Readiness，Publisher/Worker 只把依赖检查用于 Readiness，避免 Kafka 故障导致 Restart Storm。

安全方面 Pod 使用 Non-root、Read-only Root Filesystem、Drop ALL Capabilities，并关闭 ServiceAccount Token 自动挂载。最终还做了真实 Kafka Failure Smoke：Kafka Down 时 API 继续 Ready，而 Publisher 和 Worker Not Ready，恢复后自动回到 Ready。

------

# 21. 高频追问 + 简答

**Kubernetes 能自动解决多副本一致性吗？**
不能，它只管理 Pod；业务多副本安全仍然依赖应用自己的分布式协议。

**为什么 API 不做 HPA？**
因为当前 API 多副本本身还不安全，HPA 只会自动放大这个问题。

**为什么 Worker 可以未来做 HPA？**
它已经具备横向扩展基础，但目前没有容量 Benchmark，所以 WP8 没实现 HPA。

**为什么不做 Ingress？**
WP8 目标是验证 Deployment Runtime，ClusterIP + Port-forward 已足够。

**为什么不做 Helm？**
当前规模 Plain YAML / Kustomize 足够，额外引入 Helm 没有明显收益。

**为什么不用 Kubernetes 管生产 PostgreSQL/Kafka？**
当前 Stage6 不建设 Stateful HA Platform，Canonical Base 将其视为外部基础设施。

------

# 22. Bad Case / Failure Scenario

### Bad Case：API 使用普通 RollingUpdate

```text
old API
+
new API
```

两个 Process-local Runtime Owner 同时 Active，可能破坏 Ownership。

------

### Bad Case：所有 Pod 都执行 Migration

```text
API
Publisher
Worker
↓
alembic upgrade
```

会重新制造 Migration Race。

------

### Bad Case：Kafka Readiness 被当成 Worker Liveness

```text
Kafka down
→ Worker liveness fail
→ Kubernetes restart
→ Kafka still down
→ restart loop
```

------

### Bad Case：默认 ServiceAccount Token

应用本来不访问 Kubernetes API，却自动获得 Cluster Credential，扩大攻击面。

------

### Bad Case：凭名字包含 `test` 就允许部署

```text
contest-prod
```

也包含 `test`，可能错误部署生产环境。这个 Bad Case 本轮真实发现并修复。

------

# 23. Truth Boundary

当前真实实现：

```text
✅ Real Docker Desktop Kubernetes
✅ Deployment / Service / Job
✅ ConfigMap / Secret Reference
✅ ServiceAccount
✅ Non-root
✅ Read-only Root Filesystem
✅ Drop ALL capabilities

✅ API replicas=1
✅ API Recreate rollout

✅ Publisher RollingUpdate
✅ Worker RollingUpdate

✅ Worker 1→2→1 real scale smoke

✅ Migration Job
✅ Kafka Init Job

✅ API /health real probe
✅ API /readyz real probe
✅ Publisher / Worker readiness

✅ API Pod recreation
✅ Worker Pod recreation

✅ Kafka outage / recovery smoke
✅ HTTP health/readiness/metrics

✅ Context deployment guardrail
```



------

# 24. Completion Boundary

最终：

```ini
WP8_REVIEW_STATUS = PASS

REAL_KUBERNETES_EVIDENCE_CONFIRMED = YES

API_REPLICAS = 1
API_ROLLOUT_OVERLAP = NO
API_HORIZONTAL_SCALE_SUPPORTED = NO

WORKER_SCALE_TO_TWO_CONFIRMED = YES

MIGRATION_OWNER_CONFIRMED = ONE_KUBERNETES_JOB
KAFKA_TOPIC_OWNER_CONFIRMED = ONE_KUBERNETES_JOB

KAFKA_NOT_API_READINESS_DEPENDENCY = YES

NON_ROOT_CONFIRMED = YES
READ_ONLY_ROOT_FILESYSTEM_CONFIRMED = YES
PRIVILEGE_ESCALATION_BLOCKED = YES

SERVICE_ACCOUNT_TOKEN_AUTOMOUNT = NO

KAFKA_FAILURE_SEMANTICS_CONFIRMED = YES

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0

ARCHITECTURE_REOPEN_REQUIRED = NO

CAN_CLOSE_WP8 = YES
CAN_ENTER_WP9 = YES
```



------

# 25. Known Limitation / ACCEPTED_P1

目前仍然没有：

```text
API multi-replica
Zero-downtime API rollout

HPA
Ingress
PDB
NetworkPolicy
Helm

Production Secret Manager

PostgreSQL HA
Redis HA
Kafka HA

Kafka TLS / SASL production wiring

Shared production RAG index

Capacity benchmark
Real model E2E
```

同时长时间 Evaluation 不保证一定在 Termination Grace 内完整 Drain。

这些都不是当前 Blocking。

------

# 26. 面试关键词

```text
Kubernetes
Deployment
Service
Job

ConfigMap
Secret

ServiceAccount
RBAC

SecurityContext
runAsNonRoot
Capabilities
readOnlyRootFilesystem

Liveness Probe
Readiness Probe
Startup Probe

RollingUpdate
Recreate

Requests / Limits

Graceful Termination

Horizontal Scaling

Replica Safety

Migration Job
Topic Provisioning

ClusterIP

Kustomize

Deployment Guardrail

Application Authority
Distributed Ownership
```

------

# 27. WP7 → WP8 最大的区别

WP7：

```text
Docker Compose
→ 单机多服务运行
```

WP8：

```text
Kubernetes
→ 调度、重建、升级、扩缩容
```

但最关键的一点是：

> **从 Compose 到 Kubernetes，应用本身的分布式正确性不会自动升级。**

所以：

```text
API
仍然只能 1 Replica

Worker
因为已有分布式正确性机制
才可以 2 Replica
```

这是 WP8 最核心的工程认知。

------

# 28. 最值得记住的 8 个问题

```text
1. 为什么 Kubernetes 并不能自动让应用支持多副本？

2. 为什么 API 使用 Recreate，而 Worker 可以 RollingUpdate？

3. 为什么 Worker 能横向扩容，API 暂时不能？

4. 为什么 Migration / Kafka Init 必须独立 Job？

5. Liveness 和 Readiness 在 Kubernetes 中各自应该检查什么？

6. 为什么 Kafka Down 不应该触发 API Not Ready？

7. 为什么应用不需要 Kubernetes API 时应该关闭 ServiceAccount Token？

8. 为什么 Kubernetes Deployment Safety 还需要 Context Guardrail？
```

一句话总结整个 WP8：

> **Kubernetes 负责调度、重启和发布，不能替代应用自己的分布式正确性；只有已经具备 Lease、Fencing、Dedup 等多实例机制的组件才应该安全扩容，而仍有 Process-local Owner 的 Agent Runtime 必须明确限制副本数。**

------

WP8 学习完成。按照当前 Stage6 路线，下一步就是最后一个 **WP9 — Distributed Backend Final Gate**。