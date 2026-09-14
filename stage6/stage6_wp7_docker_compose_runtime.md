# 1. 名词 / 概念速览

**单镜像多进程角色（One Image / Multiple Process Roles）**：API、Publisher、Worker 复用同一应用镜像，通过不同 Command 运行不同职责。

**一次性服务（One-shot Service）**：执行完任务后正常退出的容器角色，例如数据库 Migration 和 Kafka Topic Provisioning。

**迁移所有者（Migration Owner）**：唯一负责 `alembic upgrade head` 的组件，避免多个长期进程并发执行 Schema Migration。

**KRaft**：Kafka 不依赖 ZooKeeper 的元数据管理模式；本项目 Compose 使用单节点 KRaft。

**命名卷（Named Volume）**：由 Docker 管理的持久化存储，本项目用于 PostgreSQL、Kafka 和 Chroma。

**容器就绪（Container Readiness）**：判断服务是否具备承担职责所需依赖，不等同于“进程还活着”。

**优雅退出（Graceful Shutdown）**：容器收到终止信号后，让应用有时间正常关闭连接和执行生命周期。

**Compose DNS**：容器通过 `postgres`、`redis`、`kafka` 等 Service Name 访问依赖，而不是用 `localhost`。

**非 root 运行（Non-root Runtime）**：应用容器使用普通 UID/GID 运行，降低容器逃逸或误操作时的权限范围。

**冻结依赖（Frozen Dependency Install）**：使用 `pyproject.toml + uv.lock` 确定镜像内依赖，避免构建结果漂移。

------

# 2. 当前 WP 真实实现

当前 Compose 拓扑已经真实存在：

```text
postgres
redis
kafka

migrate
kafka-init

api
publisher
worker
```

三个长期应用进程使用同一个 Python 3.12 Application Image，仅启动命令不同；`migrate` 和 `kafka-init` 则是独立的一次性服务。

实际运行边界是：

```text
API
→ uvicorn server:app

Publisher
→ python -m scripts.run_outbox_publisher

Worker
→ python -m scripts.run_evaluation_worker
```

Publisher 使用真实 Kafka Sink，Worker 使用真实 `RuntimeEvaluationExecutor`，没有把 Test Recording Sink 或 Fake Executor 带进 Compose。

------

# 3. 为什么推荐 One Image / Multiple Commands

如果 API、Publisher、Worker 分别做三套镜像，会出现：

```text
三套 Dockerfile
三套依赖
三套版本
三套安全补丁
```

然后很容易发生：

```text
API image = 新代码
Worker image = 老代码
Publisher image = 另一个依赖版本
```

当前项目改成：

```text
same image
+
different command
```

所以三个进程共享：

```text
相同源码
相同 Python
相同 uv.lock
相同 Runtime Dependency
```

这能减少 Deployment Drift。

当前镜像使用固定 Digest 的 Astral `uv + Python 3.12 bookworm-slim`，依赖来自 `pyproject.toml + uv.lock`，采用 frozen install。

------

# 4. 为什么 Migration 必须是 One-shot Owner

错误方式：

```text
API startup
→ alembic upgrade head

Publisher startup
→ alembic upgrade head

Worker startup
→ alembic upgrade head
```

三个进程同时启动就可能：

```text
并发执行 migration
争抢 DDL
产生启动时竞态
```

当前正确方式：

```text
PostgreSQL healthy
↓
migrate
→ alembic upgrade head
↓
exit 0
↓
API / Publisher / Worker 才启动
```

实际验证中 Migration 多次执行都能成功到 `0006_wp6_observability`，而首次 Migration 失败时，三个长期进程确实不会启动。

面试里可以总结为：

> Schema Migration 是部署阶段的单一 Owner，不应该由每个业务进程各自抢着执行。

------

# 5. Kafka Topic 为什么也要显式 Provision

当前 Kafka：

```text
KAFKA_AUTO_CREATE_TOPICS_ENABLE=false
```

Topic 不依赖“第一次 Producer 发消息时顺便创建”。

而是：

```text
Kafka healthy
↓
kafka-init
↓
ensure evaluation.jobs.v1
ensure evaluation.jobs.v1.dlq
↓
exit 0
```

Topic Provisioning 是幂等的，多次重跑仍然成功。两个 Topic 都为 2 Partitions、Replication Factor 1。

为什么这么做？

因为自动建 Topic 会把：

```text
拼错 Topic 名
配置错误
部署遗漏
```

悄悄变成一个新的 Topic。

显式 Provision 的好处是：

```text
Topic 是部署资产
而不是运行时副作用
```

------

# 6. 为什么 API 不依赖 Kafka

这是 WP7 非常重要的面试点。

当前 API 依赖：

```text
PostgreSQL
Migration
Redis
```

但明确：

```text
API_DEPENDS_ON_KAFKA = NO
```



原因来自前面 WP4/WP5 的架构：

```text
HTTP Submission
↓
PostgreSQL Job
+
Transactional Outbox
↓
COMMIT
```

API 已经完成 Durable Admission。

Kafka 后续由 Publisher 异步发送。

因此：

```text
Kafka Down
```

不代表：

```text
API 不能接受 Job
```

真实故障 Smoke 也证明：

```text
Kafka down
→ API ready = 200
→ Publisher/Worker not ready
```



这一点很适合面试讲：

> Transactional Outbox 不只是解决双写一致性，也解耦了 API Availability 和 Kafka Availability。

------

# 7. Publisher / Worker 为什么依赖 Kafka

Publisher 的职责就是：

```text
Outbox
→ Kafka
```

Worker 的职责就是：

```text
Kafka
→ Evaluation
```

因此 Kafka 是这两个进程的 Required Dependency。

当前：

```text
Publisher
→ PostgreSQL + Kafka + kafka-init

Worker
→ PostgreSQL + Kafka + kafka-init
```

Worker 不依赖 Redis。

这说明 Compose Dependency 不是：

> “所有服务都依赖所有基础设施”。

而应该根据真实 Process Responsibility 建模。

------

# 8. 为什么容器里不能用 localhost 访问基础设施

在 Docker Container 中：

```text
localhost
```

指的是：

```text
当前容器自己
```

不是宿主，也不是其他 Container。

所以当前 Compose 内：

```text
postgres:5432
redis:6379
kafka:9092
```

通过 Compose DNS 访问。

没有用 `localhost` 指向基础设施。

这是一道非常常见的 Docker 面试基础题。

------

# 9. 为什么默认不暴露 PostgreSQL / Redis / Kafka 端口

当前默认 Host 只暴露 API：

```text
127.0.0.1:<api-port>
```

PostgreSQL：

```text
no host port
```

Redis：

```text
no host port
```

Kafka：

```text
no host port
```

Publisher / Worker Metrics 也只在 Compose Network 内可访问。

好处有两个。

第一，避免宿主冲突。你的机器已经有别的 Redis / PostgreSQL / AgentEvalOps Service。

第二，减少攻击面。

```text
Database / Redis / Kafka
```

通常只是：

```text
Backend Internal Dependency
```

没必要默认暴露到 Host。

------

# 10. 为什么 API 只绑定 loopback

Canonical Compose：

```text
127.0.0.1:8000
```

只允许本机访问。

真实验证时 8000 已被 AgentEvalOps 使用，所以通过：

```text
LOCAL_AGENT_API_PORT=18000
```

覆盖 Host Port，仍保持 loopback-only。

这个设计表达的是：

> 本地 Compose 是 Production-like Runtime，不是直接暴露公网的 Deployment。

WP8 Kubernetes 再处理正式 Service / Networking。

------

# 11. 为什么要 Non-root

当前 Application Container：

```text
uid=10001
gid=10001
```

实际三个应用进程均验证为 Non-root。

如果应用被攻击或出现代码漏洞：

root Container 拥有更大的：

```text
filesystem
process
device
container capability
```

破坏空间。

Non-root 属于：

```text
least privilege
```

的基础容器安全措施。

同时当前没有：

```text
privileged
Docker socket
host network
```

进一步缩小权限边界。

------

# 12. 为什么 Secret 不能 Bake 进镜像

错误：

```dockerfile
ENV API_KEY=xxxx
```

或者：

```dockerfile
COPY .env /app/.env
```

因为 Image Layer 是持久的。

即使后续删除：

```text
.env
```

历史 Layer 里仍可能存在。

当前：

```text
PostgreSQL password
Remote API Key
JWT Public Key
Kafka SASL credential
```

只通过环境注入，Dockerfile 不保存；`.dockerignore` 也排除了真实 `.env`。

------

# 13. 为什么 .dockerignore 很重要

没有 `.dockerignore` 时：

```text
docker build .
```

可能把：

```text
.git
.venv
database
logs
model
.env
```

全部发给 Docker Daemon。

这既导致：

```text
Build Context 巨大
```

也会产生 Secret 风险。

当前第一次 Build Context 约：

```text
32.94 MB
```

没有包含宿主 `.venv`、模型、数据库、日志或 `.env`。

------

# 14. Windows Dependency 为什么会阻塞 Linux Docker Build

这是 WP7 一个非常真实的工程坑。

项目之前有：

```text
llama-cpp-python
PyQt6
```

这些主要用于 Windows / Desktop。

但 Docker Backend：

```text
Linux
```

使用 frozen lock 安装时也会尝试解析这些依赖，从而阻塞 Build。

最终使用：

```text
sys_platform == 'win32'
```

Platform Marker。

因此：

```text
Windows uv sync
→ 仍然安装这些依赖
```

而：

```text
Linux Docker backend
→ 不安装
```



这是典型：

> Application Dependency 与 Deployment Target Dependency 要有清晰 Platform Boundary。

------

# 15. 为什么 `uv run` 作为全局 ENTRYPOINT 出问题

原始方案里：

```text
uv run ...
```

作为统一 Container Entrypoint。

但 Non-root Container 中 `uv` 尝试写：

```text
.uv-cache
```

导致 One-shot Service 出错。

最终改成：

```text
/opt/venv/bin/python
/opt/venv/bin/uvicorn
/opt/venv/bin/alembic
```

直接运行已经构建好的 Virtual Environment。

这个经验很好：

> Build Tool 不一定应该成为 Production Runtime Launcher。

------

# 16. 为什么 `python -m scripts.xxx` 比 `python scripts/xxx.py` 稳定

原先：

```text
python scripts/foo.py
```

出现 Import Root 问题。

因为 Python 直接执行文件时：

```text
sys.path
```

和模块执行方式可能不同。

最终改为：

```text
python -m scripts.foo
```

使项目模块解析基于 Package Root。



------

# 17. Chroma 为什么需要 Volume

当前：

```text
chroma_data
→ /app/chroma_db
```

是 Named Volume。

Docker Image 不复制宿主的：

```text
index
embedding model
```

所以未 Seed 时：

```text
RAG = degraded
```

而不是假装 RAG 正常。

这是正确的 Truth Boundary：

> 容器化了应用，不等于自动拥有宿主原来的知识索引。

------

# 18. Persistence 和 Container Lifecycle 的关系

Container 是可销毁的。

Durable State 不应该依赖：

```text
Container writable layer
```

当前：

```text
PostgreSQL
→ postgres_data

Kafka
→ kafka_data

Chroma
→ chroma_data
```

均使用 Named Volume。

执行：

```text
docker compose down
```

后这些 Volume 仍然存在。

但：

```text
docker compose down -v
```

会删除 Volume。

所以两者不能随便混用。

------

# 19. Health 与 Readiness 如何被 Docker 复用

WP6 已经实现真实 Readiness Contract。

WP7 没有再写第二套：

```text
Docker-specific health logic
```

而是直接复用：

```text
API
→ /readyz

Publisher
→ scripts.healthcheck

Worker
→ scripts.healthcheck
```



这是非常好的工程原则：

> Deployment Probe 应消费 Application Health Contract，而不是复制业务判断逻辑。

------

# 20. Redis Down 的真实行为

实际 Smoke：

```text
Redis stop
```

结果：

```text
API /readyz = 503
API /health = 200
```

恢复 Redis：

```text
/readyz = 200
```



为什么？

因为：

```text
Process alive
```

所以 Liveness 仍然成功。

但：

```text
Redis Limiter
```

是 API Required Capability，因此 Readiness 失败。

这正好验证了 WP6 的设计不是纸面上的。

------

# 21. Kafka Down 的真实行为

实际：

```text
Kafka stop
```

得到：

```text
API ready = 200

Publisher ready = false
Worker ready = false
```

恢复 Kafka：

```text
Publisher / Worker ready again
```



这就是：

```text
Capability-aware Readiness
```

真正运行在 Docker Runtime 里的结果。

------

# 22. PostgreSQL Down 的真实行为

PostgreSQL：

```text
stop
```

以后：

```text
API not ready
Publisher not ready
Worker not ready
```

因为 PostgreSQL 是三个角色共有的 Durable Authority。

恢复后：

```text
all ready
```

同时：

```text
Alembic Head
Kafka Topics
```

仍然保留。

------

# 23. Restart Recovery 验证了什么

真实验证：

```text
docker compose restart api
```

然后：

```text
/readyz = 200
```

以及：

```text
docker compose restart worker
```

后：

```text
worker ready
```



这证明：

```text
Container restart
```

不会让进程依赖某些不可恢复的本地内存初始化状态。

------

# 24. Graceful Shutdown 验证了什么

真实：

```text
docker compose stop
```

过程中应用在 Grace Period 内正常退出。

API 日志明确出现：

```text
Application shutdown complete
```



但必须注意 Truth Boundary：

当前只验证：

```text
idle / message-boundary graceful shutdown
```

没有证明：

```text
正在执行一个长时间 Evaluation
一定会完整 drain 完再退出
```

强制中断后的恢复仍依赖：

```text
PG Lease/Fencing
Kafka Redelivery
```



------

# 25. PID 1 / Signal 为什么重要

Container 中最终进程往往是 PID 1。

如果：

```text
shell wrapper
```

没有正确转发 SIGTERM：

Docker Stop 发出的信号可能到不了 Python Process。

当前镜像直接运行：

```text
uvicorn
python
alembic
```

没有使用吞 Signal 的 Shell Wrapper。

这样才能让已有的：

```text
FastAPI lifespan
Worker shutdown
Publisher shutdown
```

真正执行。

------

# 26. 工程构建方法类问答

### 为什么 API / Worker / Publisher 使用同一镜像？

减少版本漂移和重复构建，同时通过不同 Command 保持 Process Responsibility 分离。

### 为什么 Migration 独立成 One-shot Service？

避免多个长期业务进程并发执行 Schema Migration，明确 Migration Owner。

### 为什么 Kafka Topic 不依赖 Auto-create？

防止配置错误和 Topic 拼写错误静默创建新 Topic，同时把 Topic 变成显式部署资产。

### 为什么 API 不依赖 Kafka Ready？

因为 Transactional Outbox 已经允许 API 在 PostgreSQL 中 Durable Accept Job，Kafka 是异步发送依赖。

### 为什么不把 PostgreSQL / Redis / Kafka 默认暴露宿主端口？

它们属于内部依赖，暴露会增加冲突和攻击面。

### 为什么要 Non-root？

遵循最小权限原则，降低容器漏洞或误操作的影响范围。

### 为什么 `docker compose down` 不默认加 `-v`？

因为 `-v` 会删除 Durable Volume，普通停止环境不应该顺手删除数据库状态。

### Docker Healthcheck 为什么复用应用 `/readyz`？

避免 Deployment 层重新实现一套与应用语义可能不一致的健康逻辑。

------

# 27. 30 秒面试回答

我把 Agent 后端做成了 One Image / Multiple Process Roles 的 Docker Compose 架构，API、Outbox Publisher 和 Kafka Worker 使用同一个 Python 3.12 镜像，通过不同 Command 运行。

数据库 Migration 和 Kafka Topic Provisioning 都是独立 One-shot Service，避免多个业务进程并发做 DDL 或依赖 Topic Auto-create。Compose 默认只暴露 loopback API，PostgreSQL、Redis、Kafka 都只走内部 Network，应用使用 Non-root 用户运行。

Healthcheck 直接复用应用已有 Readiness Contract，所以 Kafka Down 时 API 仍然 Ready，但 Publisher 和 Worker Not Ready；Redis Down 时 Liveness 仍然正常但 API Readiness 失败。PostgreSQL 和 Kafka 使用 Named Volume，容器重建后状态仍可恢复。

------

# 28. 2 分钟面试回答

我在容器化这块没有简单把 FastAPI 塞进 Docker，而是按照进程职责做了完整 Runtime Topology。

API、Outbox Publisher 和 Evaluation Worker 使用同一个 Python 3.12 Application Image，这样三者的代码和依赖版本一致，但通过不同启动命令保持职责分离。Database Migration 和 Kafka Topic Provisioning 则拆成独立 One-shot Service，Migration 只在 PostgreSQL Healthy 后执行，成功后业务进程才启动；Kafka Topic 关闭 Auto-create，通过 kafka-init 幂等 Provision。

网络方面，Compose 内通过 service DNS 访问 `postgres`、`redis`、`kafka`，默认宿主只暴露 loopback API，不暴露数据库、Redis 或 Kafka；应用容器使用 Non-root UID，Secret 只通过环境注入，不写进 Image Layer。

Healthcheck 直接消费 WP6 已有的 Readiness Contract，而不是另写 Docker 判断。例如 Kafka Down 不影响 API Ready，因为 Job Submission 只依赖 PostgreSQL Job + Transactional Outbox，但 Publisher 和 Worker 会 Not Ready。Redis Down 时 API `/health` 仍是 200，但 `/readyz` 是 503。

持久状态放在 PostgreSQL、Kafka、Chroma Named Volume，普通 `docker compose down` 不删除 Volume。Graceful Shutdown 与 Restart 也做了真实验证，强制异常恢复则继续依赖之前的 Lease/Fencing 和 Kafka Redelivery。

------

# 29. 高频追问 + 简答

### Docker 和虚拟机最大区别是什么？

Docker 共享宿主内核，通过 Namespace/Cgroup 隔离；VM 通常拥有独立 Guest OS。

### 为什么一个镜像可以运行三个服务？

镜像只是 Filesystem + Runtime 环境，真正执行什么由 Container Command 决定。

### `localhost` 在 Container 里指谁？

当前 Container 自己，不是宿主，也不是另一个 Service。

### `depends_on` 能完全保证应用依赖可用吗？

不能只靠启动顺序；还应该配合 Healthcheck / Readiness。当前 Migration、Kafka Init 和长期进程均有实际依赖状态判断。

### Named Volume 和 Bind Mount 有什么区别？

Named Volume 由 Docker 管理生命周期；Bind Mount 映射宿主具体路径，更依赖 Host 环境。

### 为什么 Kafka / PG 用 Volume，Redis 不一定要？

PG/Kafka 持有当前架构需要保留的 Durable State；Redis 在本项目主要是 Cache / Limiter，不是业务 Durable Authority。

------

# 30. Bad Case / Failure Scenario

**Bad Case：三个进程都跑 Migration**

```text
API ─┐
Publisher ├→ alembic upgrade
Worker ─┘
```

造成 DDL Race。正确方式是 One-shot Migration Owner。

**Bad Case：API depends_on Kafka**

```text
Kafka down
→ API refuses start
```

这破坏 Transactional Outbox 解耦后的 Availability Contract。

**Bad Case：容器配置 localhost PostgreSQL**

```text
postgresql://localhost:5432
```

API Container 实际连接的是它自己。

**Bad Case：把 Secret 写 Dockerfile**

Secret 会进入 Image Layer，后续删除文件也不能保证消失。

**Bad Case：默认暴露 5432/6379/9092**

会增加宿主端口冲突和攻击面。

**Bad Case：`docker compose down -v` 当普通停止命令**

会把数据库和 Kafka Volume 一起删除。

------

# 31. Truth Boundary

当前真实实现包括：

```text
✅ Dockerfile
✅ Python 3.12
✅ uv frozen install
✅ Non-root user
✅ .dockerignore

✅ One Image / Multiple Processes

✅ PostgreSQL container
✅ Redis container
✅ Kafka 4.3.1 KRaft

✅ Migration One-shot
✅ Kafka Init One-shot

✅ Topic Auto-create disabled

✅ API / Publisher / Worker containers

✅ API does not depend on Kafka

✅ Real health/readiness

✅ Named PostgreSQL volume
✅ Named Kafka volume
✅ Named Chroma volume

✅ Internal Compose networking

✅ Host exposes API only

✅ Secret not baked into image

✅ Restart recovery
✅ Graceful shutdown smoke

✅ Redis failure smoke
✅ Kafka failure smoke
✅ PostgreSQL failure smoke
```



------

# 32. Completion Boundary

最终：

```text
WP7_IMPLEMENTATION_STATUS = PASS

DOCKERFILE_IMPLEMENTED = YES
UV_FROZEN_INSTALL = YES
NON_ROOT_RUNTIME = YES

ONE_IMAGE_MULTI_PROCESS = YES

COMPOSE_IMPLEMENTED = YES

MIGRATION_SERVICE = YES_ONE_SHOT
KAFKA_INIT_SERVICE = YES_ONE_SHOT_IDEMPOTENT

TOPIC_AUTO_CREATE = NO

API_SERVICE = PASS
PUBLISHER_SERVICE = PASS_REAL_KAFKA_SINK
WORKER_SERVICE = PASS_RUNTIME_EVALUATION_EXECUTOR

API_DEPENDS_ON_KAFKA = NO

API_HEALTHCHECK = PASS
PUBLISHER_HEALTHCHECK = PASS
WORKER_HEALTHCHECK = PASS

SECRET_BAKED = NO

GRACEFUL_SHUTDOWN_TESTED = PASS
RESTART_RECOVERY_TESTED = PASS

REDIS_FAILURE_SMOKE = PASS
KAFKA_FAILURE_SMOKE = PASS
POSTGRESQL_FAILURE_SMOKE = PASS

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0

ARCHITECTURE_REOPEN_REQUIRED = NO

WP7_FINAL_REVIEW = PASS
```



------

# 33. Known Limitation / ACCEPTED_P1

当前明确没有：

```text
HA PostgreSQL
HA Redis
HA Kafka

TLS / SASL
Load Balancer
Autoscaling

Production Secret Manager

Grafana / Collector

Active long-job drain proof
Real model E2E
```

并且 Application Image 因当前 Torch / CUDA / Chroma 依赖约：

```text
6.09 GB
```

容器中也没有预 Seed Embedding Model / Chroma Index，因此 RAG 默认是 documented degraded mode。

这些都不是当前 WP 的 Blocking。

------

# 34. 这轮最值得讲的 7 个真实工程问题

本轮真正遇到并解决了：

```text
Windows-only dependency
阻塞 Linux frozen build

Kafka init / image 配置不正确

缺少 restart / init / grace / Chroma volume

Tool allowed roots
只接受 Windows Path

Non-root + uv run
产生 cache 写权限问题

python scripts/x.py
模块导入根错误

Publisher / Worker Metrics
只监听 loopback
```

最终均已修复。

这些比“我写了 Dockerfile”更适合面试展开，因为它们体现的是：

> 真正把一个 Windows 开发项目迁入 Linux Container Runtime 时，构建、路径、权限、网络、生命周期和配置边界会一起暴露出来。

------

# 35. 面试关键词

建议重点掌握：

```text
Docker Image
Container

Dockerfile
Multi-stage Build

Docker Compose

One Image / Multiple Commands

Non-root User

Docker Layer

Build Context
.dockerignore

Compose Network
Service DNS

Named Volume
Bind Mount

Healthcheck
Liveness
Readiness

Graceful Shutdown
SIGTERM
PID 1

One-shot Job

Database Migration

Kafka Topic Provisioning

Idempotent Provisioning

Environment Injection
Secret Baking

Platform Marker

Dependency Reproducibility
uv.lock

Persistent State
Ephemeral Container

Failure Recovery
```

------

# 36. WP6 → WP7 怎么串起来讲

WP6 做的是：

```text
应用知道自己：
活不活
Ready 不 Ready
哪里出错
Trace 怎么串
```

WP7 做的是：

```text
Docker / Compose
真正消费这些 Runtime Contract
```

例如：

```text
WP6:
/readyz 正确定义

WP7:
Docker healthcheck
直接调用 /readyz
```

又比如：

```text
WP6:
Kafka 不属于 API readiness

WP7:
API Compose dependency
也不依赖 Kafka
```

这说明 Deployment Architecture 没有和 Application Architecture 打架。

------

# 37. 本 WP 最值得掌握的 10 个问题

优先掌握：

```text
1. 为什么 API / Publisher / Worker 用一个镜像而不是三个？

2. 为什么 Migration 要独立 One-shot Owner？

3. 为什么 Kafka Topic 不依赖 Auto-create？

4. 为什么 API 不应该依赖 Kafka Ready？

5. Container 里为什么不能用 localhost 访问其他 Service？

6. 为什么 PostgreSQL / Redis / Kafka 默认不暴露宿主端口？

7. 为什么 Production Container 要 Non-root？

8. 为什么 Secret 不能 Bake 进 Docker Image？

9. Named Volume 解决了什么问题？

10. Docker Healthcheck 为什么应该复用应用 Readiness，而不是另写一套判断？
```

最值得记住的一句话：

> **容器化不是把程序“塞进 Docker”就结束，而是要把应用已有的 Process Owner、依赖关系、Migration、Readiness、Secret、持久状态和 Shutdown Contract 原样映射到 Deployment Runtime；部署层不能重新发明一套和应用架构冲突的事实。**