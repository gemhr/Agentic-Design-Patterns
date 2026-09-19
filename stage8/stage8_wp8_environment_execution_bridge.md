# Stage8-WP8 — Environment-aware Execution Bridge & Existing Test Platform Adapter

## 1. 名词 / 概念速览

**GeneratedCaseArtifact**
WP7 已经生成并持久化的正式 Case 引用，WP8 只能从它拿 `case_path`，不能让调用方自己填写。

**EnvironmentRequirements**
TestPlan 中保存的环境要求，例如版本、网络类型、硬件类型、能力和 Feature Flag。

**Environment Platform**
真实业务里的环境管理平台，负责告诉 AgentCore 哪些环境满足条件，以及当前是 `FREE` 还是 `BUSY`。

**ExecutionListBuilder**
普通后端代码，根据正式 Case 生成已有测试平台需要的 `execution-list.xls`，不是 LLM 在改 Excel。

**ExternalExecutionJob**
一次外部测试任务的持久化记录，保存“跑哪个 Case、在哪个环境、用什么执行列表、外部 execution_id 是什么”。

**PENDING Before Side Effect**
先把准备执行的任务记录下来，再真正调用外部测试平台，避免“测试已经启动，但 AgentCore 完全没记录”。

**Pre-execution Recheck**
环境第一次查询为空闲后，在真正提交执行前再查一次，降低环境被其他人抢占的风险。

------

# 2. 本 WP 解决什么业务问题

WP7 已经可以做到：

```text
TestPlan
→ Review
→ Case Platform
→ GeneratedCaseArtifact
```

但真正开始测试以前，过去还是需要人自己提供：

```text
Case
环境
执行机
参数
```

这和真实业务里的工作方式还差一段。

WP8 把这一段补成：

```text
GeneratedCaseArtifact
→ 从当前 TestPlan 读取环境要求
→ 查询环境管理平台
→ 找符合要求且 FREE 的环境
→ 执行前再次确认
→ 生成现有 execution-list.xls
→ 调现有测试执行平台
→ 得到 external_execution_id
→ ExternalExecutionJob = RUNNING
```

现在 caller 已经不能自己传 Case Path、Environment ID、IP 或 Executor。

------

# 3. 工程构建方法问答

## 为什么执行入口只接受 generated_case_artifact_id？

因为 WP7 已经建立了：

```text
Approved TestPlan
→ TestScenario
→ Case Platform
→ GeneratedCaseArtifact
```

如果到了执行阶段又允许：

```text
case_path="/xxx/anything"
```

那 caller 可以直接绕过 WP7。

所以现在唯一可信来源是：

```text
generated_case_artifact_id
→ backend load artifact
→ backend resolve case_path
```

最终：

```text
EXECUTION_CASE_AUTHORITY = GeneratedCaseArtifact
ARBITRARY_CASE_PATH_ALLOWED = NO
```

------

## 为什么执行前还要检查 Case 属不属于当前 TestPlan？

因为 Case 可能是旧 Plan 生成的。

例如：

```text
Plan v1
→ CASE-A

后来：
Plan v2
```

如果只判断：

```text
CASE-A belongs to this Mission
```

就可能拿旧 Case 跑新计划。

所以执行前仍然重新比较：

```text
subject
version
digest
```

必须和当前已批准 TestPlan 完全一致。

------

## 为什么 environment_requirements 要进入 TestPlan digest？

因为环境要求本身也是 Review 内容的一部分。

假设人工批准的是：

```text
27B + 5G + capability A
```

如果后来悄悄改成：

```text
27A + capability B
```

但 digest 不变化，那么旧 Review 就还能授权新环境要求。

所以 WP8 已确认：

```text
ENVIRONMENT_REQUIREMENTS_IN_TESTPLAN_DIGEST = YES
```

------

## Agent 到底负责选什么？

Agent 在 TestPlan 阶段可以说：

> 我需要什么环境。

例如：

```text
version = 27B
network = 5G
required_capabilities = [...]
```

但 Agent 不能说：

> ENV-001 现在是空闲的。

真实状态必须查询 Environment Platform。

因此：

```text
Agent
→ 提出 Requirement

Environment Platform
→ 提供真实环境状态

普通代码
→ 做确定性过滤
```

------

## 为什么环境选择不用新的 Agent？

因为这里不需要开放式推理。

当前规则只是：

```text
满足硬条件
+
FREE
+
稳定排序
```

这用普通代码更可靠。

最终策略：

```text
HARD_FILTER
→ FREE
→ environment_id ASC
```

------

## 为什么缺少环境要求时直接不执行？

通信测试环境通常不能随便找一台机器跑。

如果 TestPlan 没说清楚：

```text
版本
网络类型
硬件要求
能力要求
```

系统并不知道“任意空闲环境”是不是安全。

所以当前选择：

```text
environment_requirements missing
→ fail closed
```

而不是随便找一台 FREE 环境。

------

## 找不到环境怎么办？

不降级，不硬跑。

当前：

```text
没有满足条件且 FREE 的环境
→ WAITING_FOR_RESOURCE
→ 不启动测试
```

因此：

```text
NO_RESOURCE_BEHAVIOR =
NO_EXTERNAL_EXECUTION_AND_WAITING_FOR_RESOURCE
```

------

## 为什么查询到 FREE 后还要再查一次？

因为第一次查询以后，环境可能被别人占用。

例如：

```text
10:00:00 ENV-01 FREE
10:00:01 其他测试占用
10:00:02 AgentCore 提交执行
```

所以正式执行前会重新调用 Environment Platform。

如果变成 BUSY：

```text
跳到下一个候选
```

而不是继续执行。

------

## 这样就完全没有竞态了吗？

没有。

仍然存在：

```text
recheck FREE
↓
极短时间窗口
↓
外部提交
```

期间别人仍可能抢占环境。

当前没有 reserve API，所以这个竞态被明确保留为 Accepted Limitation。

没有为了它自己造 Redis 分布式锁，因为 AgentCore 不是环境资源的最终 Owner。

------

## 为什么不用 AgentCore 自己锁环境？

因为真实环境状态属于 Environment Platform。

AgentCore 自己加一把锁只能约束：

```text
AgentCore 自己
```

却约束不了：

```text
其他测试平台
其他业务人员
其他系统
```

所以最正确的解决方式最终应该是环境平台提供：

```text
reserve / claim
```

而不是 AgentCore 建一个“看起来有锁”的旁路状态。

------

## execution-list.xls 是谁生成的？

普通 Python 代码。

流程：

```text
GeneratedCaseArtifact.case_path
→ ExecutionListBuilder
→ execution-list.xls
```

里面：

```text
Case Path = 平台生成的正式路径
Selected = TRUE
```

caller 不提供输出路径，也不能替换 Case Path。

------

## 为什么不用 LLM 填 Excel？

因为填固定格式 Excel 是确定性工作。

让模型做：

```text
单元格位置
格式
TRUE/FALSE
路径写入
```

只会增加不稳定性。

所以：

```text
LLM
负责决定测什么

普通代码
负责把这些决定转成执行平台需要的文件格式
```

------

## 为什么测试执行还要走 Tool Runtime？

因为“启动测试”是真实外部副作用。

不能：

```text
ExecutionService
→ TestExecutionPlatform.start()
```

直接调用。

仍然走：

```text
GovernedToolInvoker
→ ToolExecutionService
→ Stage8PlatformToolAdapter
→ TestExecutionPlatform
```

------

## 为什么一定要先写 PENDING Job 再启动外部测试？

最危险的顺序是：

```text
外部测试启动成功
→ AgentCore 进程崩了
→ 还没创建 Job
```

这时测试正在真实执行，但 AgentCore 完全不知道它存在。

所以现在：

```text
选择 Case / Environment / Execution List
→ 写 PENDING Job
→ commit
→ 调外部平台
→ 得到 execution_id
→ RUNNING
```

------

## PENDING Job 里为什么要保存选中的环境？

因为网络重试的时候不能重新选环境。

错误：

```text
第一次：
选择 ENV-01
→ 外部已启动
→ response lost

retry：
重新查询
→ ENV-02
→ 再启动一次
```

这样就会重复测试。

所以 PENDING 已经绑定：

```text
Generated Case
Environment
Environment IP
Execution List
Requirements
Parameters
```

重试优先恢复原来的执行意图。

------

## 相同 Case 重试是不是一定复用旧 Job？

不是。

现在不是简单按：

```text
Mission + Case
```

判断。

还会计算稳定的 request digest。

所以：

```text
同 Case + 同执行参数
→ replay

同 Case + 不同执行配置
→ 新的执行语义
```

最终：

```text
SAME_REQUEST_REPLAY = PASS
DIFFERENT_CONFIG_REPLAY = NO_FALSE_REPLAY
```

------

## 为什么 Mission 不能在创建 PENDING 时就变 EXECUTING？

因为 PENDING 只说明：

> 我准备启动。

并不代表外部平台真的接受了测试。

所以只有：

```text
provider returns execution_id
```

以后：

```text
Job = RUNNING
Mission = EXECUTING
```

------

## 为什么 HTTP 不等测试跑完？

真实测试可能运行：

```text
几十分钟
几小时
```

HTTP/Agent Run 不应该一直挂着。

所以：

```text
start accepted
→ execution_id
→ Job RUNNING
→ 当前请求返回
```

后续结果由新的流程观察。

这延续了 WP3 的：

> 长任务不是长 Agent Run。

------

# 4. 30 秒项目回答

> 测试计划通过 Review 并生成正式 Case 后，我把执行入口收紧成只接受 generated_case_artifact_id。系统从当前 TestPlan 读取结构化环境要求，去环境平台查询满足条件且空闲的环境，并在真正启动前再确认一次。然后普通代码生成现有测试平台需要的 execution-list.xls，再通过统一 Tool Runtime 调已有执行平台。启动前会先持久化 PENDING Job，平台真正返回 execution_id 后才把 Job 和 Mission 标成运行中，所以 Agent 不需要一直等几个小时的测试结束。

------

# 5. 2 分钟项目回答

> WP8 解决的是从“已经有正式 Case”到“真正开始一次测试”的过程。
>
> 之前执行接口需要 caller 自己传 Case、环境和 Executor，这其实绕开了前面已经建立的 Case 和环境 Authority。所以这一阶段把 canonical input 收紧成 generated_case_artifact_id。后端先确认这份 Artifact 确实属于当前已批准的 TestPlan，再从 Artifact 拿平台生成的 case_path。
>
> 环境要求由 Test Planning 阶段生成结构化字段，并且进入 TestPlan digest，所以人工批准的其实也包含环境要求。执行时 AgentCore 去环境管理平台查询真实环境，按硬条件过滤，只保留 FREE 的候选，再做稳定排序。真正提交测试前还会再查询一次，如果环境已经变 BUSY，就尝试下一个；如果没有可用环境，任务进入 WAITING_FOR_RESOURCE，不会强行执行。
>
> 接下来由普通 Python 代码生成公司现有执行平台需要的 execution-list.xls，Case Path 只能来自 GeneratedCaseArtifact，caller 不能自己指定。
>
> 真正启动测试仍然经过统一 Tool Runtime。这里还保留了 WP3 的异步设计：先持久化 PENDING ExternalExecutionJob，把 Case、环境、执行列表和参数都固定下来，然后才调用外部平台。平台返回 execution_id 后，Job 才进入 RUNNING，Mission 才进入 EXECUTING，当前 HTTP 请求立即结束。
>
> 为了避免网络重试重复启动，执行身份不只看 Mission 和 Case，还绑定执行参数；相同请求复用已有 Job，不同配置不会错误复用。
>
> 当前外部环境平台和执行平台仍是 Mock，下一步再补执行结果观察和固定日志解析。

------

# 6. 高频追问 + 简答

## 你们怎么选测试环境？

TestPlan 给出环境要求，环境平台提供真实状态，然后普通代码过滤：

```text
满足硬条件
+
FREE
```

最后稳定选一个。

------

## Agent 会不会自己猜一个环境？

不会。

Agent 只说：

> 我需要什么。

不能说：

> ENV-01 现在空闲。

------

## 为什么不直接让用户指定 IP？

因为 canonical 自动流程的目标就是接管人工选环境。

如果以后需要手工指定环境，应设计成明确的 audited override，而不是默认入口。

------

## 如果没有环境怎么办？

进入：

```text
WAITING_FOR_RESOURCE
```

不执行。

------

## 如果环境刚查完就被别人抢了怎么办？

执行前再查一次。

仍然存在极短竞态，彻底解决需要环境平台提供 reserve/claim。当前没有自行实现伪分布式锁。

------

## 为什么不用 Redis 锁环境？

因为 Redis 锁只能约束 AgentCore，看不到公司其他系统对环境的使用，不能成为真实资源 Authority。

------

## 为什么还要生成 xls？

因为这是现有成熟测试执行平台的输入 Contract。

我们的目标是复用它，而不是重新写 Executor。

------

## 为什么不改现有执行平台，让它直接吃 JSON？

现实工程里没必要为了 Agent 项目重写已经成熟的业务系统。

Adapter 把 AgentCore 的结构化请求转换成现有平台能接受的格式就行。

------

## 执行列表是不是模型生成的？

不是。

普通确定性代码生成。

------

## 为什么启动执行需要幂等？

因为网络超时可能导致：

```text
平台已经启动
AgentCore 没收到 response
```

重试不能再启动第二次。

------

## 怎么判断是不是同一次执行？

现在使用稳定 request digest，里面绑定：

```text
Mission
Generated Case
Execution Parameters
```

而 PENDING Job 再固定具体选中的 Environment 和 Execution List。

------

## 为什么重试不能重新选环境？

因为第一次可能实际上已经在 ENV-01 启动了。

重新选 ENV-02 会造成一次业务请求启动两个真实测试。

------

## 为什么 Agent Run 不等测试结束？

测试可能持续几个小时。

Agent Run 只负责：

```text
准备
启动
记录 external job
```

测试结果回来后再由新的处理阶段继续。

------

# 7. Bad Case

## Real Bad Case 1 — Caller 继续传 case_path

如果执行 API 仍允许：

```text
case_path="/random/path"
```

那么 WP7 的 Case Generation 全部可以被绕开。

最终彻底移除旧入口：

```text
generated_case_artifact_id only
```

------

## Real Bad Case 2 — 旧 Case 通过已有 RUNNING Job 绕过 Plan Gate

初版 Replay 如果只看到：

```text
这个 Mission 已经有 RUNNING Job
```

就直接返回，

可能发生：

```text
Case 基于 Plan v1
当前 Plan 已经变成 v2
→ replay old job
```

Sol 最终修成：

```text
replay 前仍然重新校验
Artifact ↔ current approved Plan
```

------

## Real Bad Case 3 — Environment Requirement 不进入 Plan digest

如果 Review 批准：

```text
5G / 27B
```

然后环境要求被修改：

```text
4G / 27A
```

而 digest 不变化，

旧 Review 仍能授权新执行条件。

最终 environment requirements 已进入 canonical TestPlan digest。

------

## Real Bad Case 4 — same Mission + Case 被错误当成同一次执行

错误 Replay：

```text
Mission-A + Case-A
→ 永远返回同一个 Job
```

但可能：

```text
第一次 parameters A
第二次 parameters B
```

本来应该是不同执行。

现在增加稳定 request digest：

```text
same request → replay
different config → no false replay
```

------

## Real Bad Case 5 — External Side Effect 发生后才建 Job

错误：

```text
start external test
→ process crash
→ Job never created
```

最终修成：

```text
persist PENDING
→ commit
→ external start
```

------

## Real Bad Case 6 — 没环境还强行执行

现在明确：

```text
no matching FREE environment
→ WAITING_FOR_RESOURCE
→ NO external execution
```

------

## Accepted Bad Case — Recheck 后仍然被抢

当前还有：

```text
recheck FREE
→ 提交前被别人占用
```

因为环境平台没有 reserve API。

这是已知限制，不是假装解决。

------

# 8. Truth / Owner / Completion Boundary

## Case Truth

Owner：

```text
GeneratedCaseArtifact
```

路径最终来自 Case Platform。

caller 不拥有。

------

## Environment Requirement

Owner：

```text
Current validated TestPlan
```

Agent 可以提出要求，但进入 TestPlan 后才成为当前执行要求。

------

## Environment Status / IP

Owner：

```text
Environment Platform
```

AgentCore 只能查询。

------

## Environment Selection

Owner：

```text
Stage8 deterministic application logic
```

当前不是 LLM 决策。

------

## execution-list.xls

Owner：

```text
ExecutionListBuilder
```

它根据可信 Case Artifact 构造已有平台输入。

------

## External Test Execution

Owner：

```text
TestExecutionPlatform
```

AgentCore 负责请求和记录，不负责真正运行测试进程。

------

## ExternalExecutionJob

Owner：

```text
Stage8ExecutionService + PostgreSQL
```

它记录：

```text
跑什么 Case
在哪个环境
用什么执行列表
外部 execution_id
当前执行状态
```

------

## Mission EXECUTING

只有：

```text
Provider accepted
+
execution_id returned
```

以后才成立。

------

## WP8 已完成

真实完成：

```text
GeneratedCaseArtifact
→ Current Plan validation
→ Environment Requirement
→ Environment Platform query
→ FREE candidate selection
→ Pre-execution recheck
→ Execution List generation
→ Tool Runtime
→ Test Execution Platform
→ PENDING
→ external execution_id
→ RUNNING
→ asynchronous return
```

------

## WP8 没完成

当前没有：

```text
真实公司 Environment Platform transport/auth
真实 Test Execution Platform transport/auth

Environment reserve

结果 polling

固定日志解析

test cancellation

自动负载均衡

manual environment override

execution-list cleanup
```

其中：

```text
结果观察
固定日志目录
SUCCESS / FAILED
错误信息解析
```

属于下一阶段 WP9。

------

# 9. 本 WP 最应该记住的五句话

第一句：

> **Agent 可以决定需要什么环境，但不能决定哪个环境现在是空闲的。**

第二句：

> **执行只能引用 GeneratedCaseArtifact，不能重新开放任意 Case Path。**

第三句：

> **先持久化 PENDING，再启动外部测试，是为了保证外部动作发生以后系统至少还有可恢复的本地记录。**

第四句：

> **网络重试必须复用已经固定的执行意图，不能重新选环境再启动一次。**

第五句：

> **已有测试平台继续负责真正执行，AgentCore 的价值是把 Case、环境选择、执行请求和异步状态可靠地串起来。**