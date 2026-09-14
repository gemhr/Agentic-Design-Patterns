当前是 **GPT-5.6 Sol**。

下面进入 **Stage6-Supplement-WP12 — Sandbox / Isolated Tool Execution** 的学习 / 面试总结。推荐文件名：

```
docs/interview/stage6_wp12_sandbox_isolated_tool_execution.md
```

本总结以 WP12 Final Review 为最终事实来源。当前状态是 `PASS_WITH_EXPLICIT_LIMITATIONS`，`P0=0 / Blocking P1=0 / Accepted P1=NONE`，可以正式关闭。

# 1. 名词 / 概念速览

**沙箱（Sandbox）**：把不完全可信的执行放进受限制环境，让它即使出错也只能影响有限范围。

**执行隔离（Execution Isolation）**：从进程、文件系统、网络、资源等维度限制执行能力。

**执行收敛（Execution Containment）**：强调“即使允许执行，最大影响范围也被限制”。

**可信进程内执行（Trusted In-Process Execution）**：Tool 直接在 Agent Runtime 进程里执行，不属于 Sandbox。

**隔离执行（Isolated Execution）**：本项目中特指显式进入 Docker 容器执行的 Tool。

**治理（Governance）**：决定一个 Tool Invocation 是否允许执行。

**沙箱执行策略（SandboxExecutionPolicy）**：决定已经获准执行的 Tool 使用什么执行模式、网络和资源限制。

**默认拒绝网络（Default Deny Network）**：隔离 Tool 默认使用 Docker `network none`，除非代码侧策略明确允许。

**故障关闭（Fail Closed）**：Sandbox 不可用时直接执行失败，而不是偷偷降级为进程内执行。

**资源限制（Resource Limits）**：限制 CPU、内存、进程数和执行时间。

**能力削减（Capability Dropping）**：通过 `cap-drop ALL` 等方式减少容器内进程拥有的 Linux Capability。

------

# 2. 当前 WP 真实实现

WP12 最终新增了：

```text
SandboxExecutionPolicy

ToolExecutionBackend

TrustedInProcessExecutionBackend

DockerIsolatedExecutionBackend

sandbox_execution_demo
```

但是没有新建第二套 Tool Runtime、Governance、Approval、Retry、Idempotency、Cancellation 或 Tool Result Contract。

现有 Tool 默认继续走：

```text
TrustedInProcessExecutionBackend
```

只有明确由代码侧声明为隔离执行的 Tool 才进入：

```text
DockerIsolatedExecutionBackend
```

而且 Trusted In-Process 明确**不叫 Sandbox**。

Docker 隔离真实实现了：

```text
固定镜像
固定 Worker
无 shell=True

read-only rootfs
non-root
cap-drop ALL
no-new-privileges

CPU limit
Memory limit
PIDs limit

NO_NETWORK by default

只读 input mount
独立可写 output mount

不继承 Agent Runtime 环境变量

bounded stdout/stderr

timeout/cancel 后强制删除容器
```



------

# 3. 架构与调用链

最终链路是：

```text
Model Tool Intent
        ↓
ToolAdapter.build_invocation()
        ↓
Typed Validation
        ↓
ToolGovernanceService
        ↓
ALLOW / APPROVAL_REQUIRED
        ↓
HITL（如果需要）
        ↓
Approval Claim
仅 APPROVAL_REQUIRED 路径
        ↓
ResourceAuthorization
如果适用
        ↓
ToolExecutionService
        ↓
ToolAttemptExecutor
        ↓
ToolExecutionBackendResolver
        ↓
┌───────────────────────────────┐
│ TrustedInProcessBackend       │
│ 或                            │
│ DockerIsolatedBackend         │
└───────────────────────────────┘
        ↓
ToolAdapterResponse
        ↓
build_tool_output()
        ↓
ToolExecutionResult
```



最关键的 Owner 边界：

```text
Governance
→ 决定能不能执行

SandboxExecutionPolicy
→ 决定怎么执行

Backend
→ 执行并强制隔离

ToolExecutionService
→ 仍拥有 Retry / Idempotency / Result
```

------

# 4. 为什么这样设计

## Governance 和 Sandbox 为什么不能合并

这是 WP12 最核心的面试问题。

假设用户请求：

> 删除一个文件。

Governance 回答：

> 这个动作有没有权限执行？

Sandbox 回答：

> 即使允许执行，这个代码最多能访问哪里？

所以：

```text
Governance = Authorization

Sandbox = Containment
```

如果把两者混起来，会出现第二套安全 Authority。

------

## 为什么 Approval 不能替代 Sandbox

用户批准一个高风险操作：

```text
APPROVED
```

只代表：

> 这个动作经过授权。

不代表：

> 这个 Tool 可以访问整台机器。

例如用户批准某个数据处理 Tool，不应该因此获得：

```text
C:\
整个 repo
数据库 Secret
Agent API Key
任意网络
```

所以：

```text
Approval
+
Sandbox

=
Authorization + Containment
```

------

## 为什么 TrustedInProcess 不能叫 Sandbox

因为它仍然和 Agent Runtime 共用：

```text
Process
Environment
Filesystem permissions
Network
Memory space
```

虽然有：

```text
Path check
Timeout
Typed Validation
```

这些都是 Application Guard，不是 OS / Container Isolation。

Final Review 特别把 Trusted 模式的网络状态从错误的 `NO_NETWORK` 改成：

```text
NOT_APPLICABLE
```

避免产生虚假的安全证据。

------

# 5. 可选方案与 Trade-off

## 方案一：全部 Tool 都 Docker 化

优点：

```text
隔离统一
安全边界简单
```

问题：

已有 Tool 的业务语义不同。

例如：

```text
get_system_status
```

如果放容器里，看到的是容器状态，不再是 Host 状态。

MCP 又是长生命周期 Provider，不是一次 Invocation 一个 Container。

所以 WP12 没有为了架构整齐强行迁移所有 Tool。

------

## 方案二：Windows 原生 Subprocess Sandbox

理论上可以做：

```text
Job Object
Restricted Token
ACL
Process Group
```

但当前项目没有相关基础设施，网络隔离也不好做。

因此没有选它作为当前主要 Sandbox Backend。

------

## 方案三：Docker

当前选择。

优势：

```text
真实可运行
Windows Docker Desktop 可验证
Filesystem Mount Boundary
Network none
CPU / Memory / PIDs
Container lifecycle
```

代价：

```text
Docker Engine dependency
启动成本
生产 Control Plane 更复杂
```

------

## 方案四：Kubernetes Job per Tool

没有做。

因为会带来：

```text
Pod startup latency
RBAC
NetworkPolicy
TTL
Image lifecycle
Cluster dependency
```

对于当前面试型工程项目收益太低。

------

## 方案五：独立 Sandbox Executor Service

这是更合理的未来生产方向：

```text
Agent API / Worker
        ↓
Sandbox Executor
        ↓
Container Runtime
```

而不是：

```text
Agent API
→ 挂 Docker socket
```

但 WP12 没有继续扩建这个服务。

------

# 6. 工程构建方法类问答

### 为什么 Sandbox 要放在 ToolExecutionService 下面？

因为 Sandbox 只负责执行环境，而 ToolExecutionService 已经拥有 Retry、Idempotency、Result 和 Attempt Lifecycle。

如果 Sandbox 放到 ToolAdapter：

> 每个业务 Tool 都会开始管理 Docker 生命周期。

这样会导致基础设施职责扩散。

------

### 为什么 Sandbox Mode 不能让模型选择？

因为模型本身可能被 Prompt Injection。

所以：

```text
model argument:
sandbox=false
```

绝不能关闭隔离。

Sandbox Mode 必须来自：

```text
code/operator-owned
ToolExecutionSpec.sandbox_policy
```



------

### Docker 不可用怎么办？

对于：

```text
mode=ISOLATED
```

必须：

```text
typed fail closed
```

不能：

```text
Docker unavailable
→ fallback in-process
```

否则最危险的时候反而失去安全边界。

------

### 为什么不继承 os.environ？

Agent Runtime Environment 可能存在：

```text
LLM API Key
DB URL
Redis
Kafka
JWT
MCP credentials
```

Sandbox 默认拿到这些，就失去 Secret Isolation 的意义。

所以当前只允许固定 Runtime Env + Code-owned Explicit Values。

------

### Sandbox 自己能 Retry 吗？

不能。

Backend：

```text
execute()
=
one attempt
```

Retry 仍由 ToolExecutionService 判断。

否则：

```text
Sandbox Backend失败
→ 自己重跑
```

可能导致 Non-idempotent Side Effect 重复执行。



------

# 7. 30 秒面试回答

我在 Tool Runtime 里把 Governance 和 Sandbox 分成两层。Governance 决定 Tool Invocation 能不能执行，Sandbox 只负责已经授权后的执行隔离。

具体实现上，我在 ToolAttemptExecutor 下面增加统一 Execution Backend，现有可信 Tool 继续走进程内执行，显式声明为 isolated 的 Tool 才进入 Docker。Docker 默认只读根文件系统、非 root、禁用 Linux Capability、禁止网络，只挂只读输入和独立输出目录，同时限制 CPU、内存、进程数和执行时间。

如果 Sandbox 不可用会直接 typed fail，不会降级成进程内执行。Retry、Idempotency 和 Tool Result 仍由原 Tool Runtime 管理，没有再造第二套 Runtime。

------

# 8. 2 分钟面试回答

我做 Sandbox 的时候，先明确了它不能替代 Tool Governance。

现有 Tool Runtime 已经有 Typed Validation、Risk Classification、HITL、Approval 和 Execution Service，所以 Sandbox 应该解决的是“一个已经获准执行的 Tool 最多能影响到哪里”。

架构上我在 `ToolAttemptExecutor` 下面增加统一 Execution Backend。默认 Built-in Tool 继续使用 `TrustedInProcessExecutionBackend`，这个模式明确不叫 Sandbox。只有代码侧 `ToolExecutionSpec` 声明为 isolated 的 Tool 才进入 Docker Backend，模型、用户参数和 MCP Provider 都不能改变这个选择。

Docker 隔离使用固定镜像和固定 Worker，不支持任意 Shell 或代码执行。容器使用只读 RootFS、Non-root 用户、Drop All Capabilities，只挂只读 Input 和独立 Output，默认 `network none`，同时设置 CPU、Memory 和 PIDs Limit。Sandbox 也不继承 Agent Runtime 的 Environment，所以 LLM Key、数据库配置等不会自动进入容器。

Timeout 和 Cancellation 仍由原来的 RunContext 和 ToolAttemptExecutor 管理，Backend 只负责收到终止信号以后执行 `docker rm -f` 并验证容器消失。Backend 本身不会 Retry，避免非幂等 Tool 被偷偷重复执行。

最后，生产环境没有把 Docker Socket 挂给 API / Worker；当前 Docker Backend 是真实可运行的本地隔离能力，未来如果生产化，会更适合演进成独立 Sandbox Executor。

------

# 9. 高频追问 + 简答

**Q：Docker Sandbox 是不是绝对安全？**
不是。它提供明显强于进程内执行的容器隔离，但当前没有实现完整生产 Sandbox Control Plane。

**Q：为什么不能直接用 subprocess？**
Subprocess 只提供地址空间分离，文件系统、环境和网络仍可能和父进程高度共享。

**Q：为什么默认断网？**
多数 Tool 不需要网络，默认关闭能减少数据外传面。

**Q：用户批准 Data Egress 后是不是就自动联网？**
不是。Approval 和 Network Policy 是两层独立控制。

**Q：Sandbox 是否负责权限判断？**
不负责，仍然是 ToolGovernanceService。

**Q：Sandbox 是否负责 Retry？**
不负责，Retry 属于 ToolExecutionService。

**Q：为什么要固定 Worker？**
防止 Sandbox 变成任意代码 / Shell Execution Service。

**Q：MCP Tool 现在 Sandbox 了吗？**
没有。当前 MCP Process Separation 不等于 WP12 Sandbox。

------

# 10. Bad Case / Failure Scenario

## Bad Case 1：Docker 挂了就退回进程内

错误：

```text
Docker unavailable
→ execute locally
```

这等于在隔离最需要的时候失去隔离。

正确：

```text
Docker unavailable
→ typed execution failure
```

------

## Bad Case 2：模型控制 Network Policy

错误：

```text
tool arguments:
{
  "network": true
}
```

然后 Sandbox 开网。

这等于允许攻击 Prompt 修改执行边界。

正确：

```text
SandboxExecutionPolicy
→ code-owned
```

------

## Bad Case 3：把 Docker Socket 挂给生产 API

```text
/var/run/docker.sock
→ API container
```

通常意味着 API 可以控制宿主 Docker Engine。

因此当前生产 Compose/K8s 明确没有这么做。

------

## Bad Case 4：Sandbox 自己 Retry

```text
container start
→ uncertain failure
→ backend recreate container
→ execute again
```

对于 Non-idempotent Tool 可能造成双执行。

所以 Backend 一次 execute 就是一次 Attempt。

------

## Bad Case 5：Timeout Future 被取消就声称进程死了

```text
future.cancel()
→ worker_terminated=true
```

这是错误的。

Final Review 专门修复为：

```text
docker rm -f
→ docker inspect
→ confirmed absent
→ worker_terminated=true
```

无法验证就不能声称已经终止。

------

## Bad Case 6：只限制最终 Tool Result

如果：

```text
Tool产生1GB stdout
→ 全读进内存
→ 最后截成4KB
```

已经太晚了。

当前是 bounded streaming capture，达到 Limit 就提前失败。

------

# 11. Truth Boundary

当前**真实完成**：

```text
✅ Execution Backend abstraction

✅ Trusted In-Process backend
   但明确不是 Sandbox

✅ Real Docker isolated backend

✅ Operator/code-owned Sandbox Policy

✅ Model不能选择 Sandbox Mode

✅ MCP Provider不能选择 Sandbox Mode

✅ Isolated fail closed

✅ No isolated → in-process fallback

✅ Read-only rootfs

✅ Non-root

✅ Capabilities dropped

✅ no-new-privileges

✅ read-only input mount

✅ dedicated writable output mount

✅ default NO_NETWORK

✅ no Agent env inheritance

✅ synthetic secret isolation verified

✅ CPU limit runtime applied

✅ Memory limit runtime applied

✅ PIDs limit runtime applied

✅ Wall-clock timeout

✅ Bounded stdout/stderr

✅ Container termination verification

✅ Backend local retry = NO

✅ Existing Tool Result Contract reused

✅ Governance / Approval / Resource Auth preserved

✅ Real Docker smoke

✅ Generic Shell Tool = NO
```



------

# 12. Completion Boundary

最终结果：

```ini
WP12_REVIEW_STATUS = PASS_WITH_EXPLICIT_LIMITATIONS

SANDBOX_BACKEND_ABSTRACTION_CONFIRMED = YES
TOOL_EXECUTION_OWNER_PRESERVED = YES

TRUSTED_IN_PROCESS_LABELLED_SANDBOX = NO

DOCKER_ISOLATED_BACKEND_CONFIRMED = YES
FIXED_WORKLOAD_ONLY = YES
GENERIC_SHELL_TOOL = NO

SANDBOX_SELECTION_OPERATOR_OWNED = YES
MODEL_CANNOT_SELECT_SANDBOX_MODE = YES
MCP_PROVIDER_CANNOT_SELECT_SANDBOX_MODE = YES

ISOLATED_FAIL_CLOSED = YES
ISOLATED_TO_IN_PROCESS_FALLBACK = NO

FILESYSTEM_MOUNT_BOUNDARY_CONFIRMED = YES
READ_ONLY_ROOTFS_CONFIRMED = YES
NON_ROOT_CONFIRMED = YES
CAPABILITIES_DROPPED_CONFIRMED = YES

NETWORK_DEFAULT_DENY_CONFIRMED = YES_FOR_ISOLATED

AGENT_ENV_INHERITANCE = NO
SYNTHETIC_SECRET_ISOLATION_CONFIRMED = YES

CPU_LIMIT_STATUS = CONFIGURED_AND_RUNTIME_APPLIED
MEMORY_LIMIT_STATUS = CONFIGURED_AND_RUNTIME_APPLIED
PIDS_LIMIT_STATUS = CONFIGURED_AND_RUNTIME_APPLIED

WALL_CLOCK_LIMIT_CONFIRMED = YES
OUTPUT_CAPTURE_BOUNDED_CONFIRMED = YES

CONTAINER_TERMINATION_CONFIRMED =
YES_FOR_TESTED_TIMEOUT_CANCEL_AND_NORMAL_PATHS

DESCENDANT_TREE_TIMEOUT_PROOF =
NO_EXPLICIT_LIMITATION

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = NONE

ARCHITECTURE_REOPEN_REQUIRED = NO
CAN_CLOSE_WP12 = YES
```



------

# 13. Known Limitation / ACCEPTED_P1

当前明确**没有**：

```text
Hard Disk Quota

Domain / IP Network Allowlist

DNS Filter

Egress Proxy

MCP Sandbox

全部 Built-in Tool Sandbox

Descendant Timeout 独立验证

ALLOW_NETWORK 正向外网 Smoke

Production Dedicated Sandbox Executor

Resource Exhaustion Stress Test

完整 Resource-limit Exit Classification

Per-attempt Cleanup / Resource-limit Trace
```



尤其注意：

### CPU / Memory / PIDs

可以说：

> Docker Runtime 已真实配置并应用 CPU、Memory 和 PIDs Limit。

不能说：

> 我完整验证了 CPU / Memory / Fork Bomb 资源耗尽行为。

Final Review 明确没有做这类不稳定 Stress Test。

### Process Tree

可以说：

> Timeout 后会强制移除 Container，并真实验证 Container 已不存在。

不能说：

> 已独立验证任意 Grandchild Process 在超时后绝不存活。

该项明确：

```text
DESCENDANT_TREE_TIMEOUT_PROOF = NO
```



当前：

```text
ACCEPTED_P1 = NONE
```

这些都是 Scope 外显式限制，不是未关闭缺陷。

------

# 14. 面试关键词

建议重点记住这一组，不需要全部塞进简历：

- Sandbox
- Execution Isolation
- Execution Containment
- Tool Governance
- Authorization vs Containment
- Trusted In-Process Execution
- Isolated Execution
- Fail Closed
- Read-only RootFS
- Non-root
- Capability Dropping
- No-new-privileges
- Mount Isolation
- Network Default Deny
- Environment Isolation
- Secret Isolation
- CPU / Memory / PIDs Limits
- Wall-clock Timeout
- Bounded Output
- Container Cleanup
- Retry Authority
- Idempotency
- Side-effect Uncertainty
- Fixed Workload
- Docker Socket Security
- Defense in Depth

最后一句可以作为 WP12 的核心记忆：

> **Tool Governance 解决“这个动作有没有权执行”，Sandbox 解决“即使这个动作被允许，它最多能影响到哪里”；所以 Sandbox 必须位于 Governance 之后，并且不能拥有第二套权限、Retry 或业务结果 Authority。**

至此，**WP10 Agent Security、WP11 Context Engineering、WP12 Sandbox** 三个面试补强项全部完成。下一阶段最值得做的已经不是继续加功能，而是把 **Stage5 + Stage6 整体项目叙事、简历表述和高频面试题**正式收口。