# Stage8-WP9 — Execution Result Observation & Log Normalization

## 1. 名词 / 概念速览

**Execution Observation**
测试启动以后，根据已经持久化的 `ExternalExecutionJob` 主动查询外部执行平台真实状态，而不是等待用户告诉系统成功还是失败。

**Result Authority**
谁有资格决定一次执行最终是什么结果；WP9 中 Authority 是执行平台提供的状态和结果日志，而不是 caller 或 LLM。

**ExecutionResultParser**
确定性日志解析器，根据固定格式解析 `SUCCESS / FAILED`、错误码、错误信息和失败步骤。

**Provider-owned Result Location**
结果日志位置由 TestExecutionPlatform 返回，AgentCore 把它视为 opaque reference，而不是让 caller 自己指定文件路径。

**observe_once()**
执行一次状态观察的可重入操作；调用一次只查一次，不在 HTTP 请求中循环等待几个小时。

**Terminal First-wins**
一次执行第一次被接受的终态结果成为最终事实，后续冲突结果不能覆盖它。

**Bounded Log Excerpt**
AgentCore 不持久化完整大日志，只保存受限的日志片段和归一化错误字段。

------

# 2. 本 WP 解决什么业务问题

WP8 已经完成：

```text
GeneratedCaseArtifact
→ 选择环境
→ execution-list.xls
→ Test Execution Platform
→ external_execution_id
→ ExternalExecutionJob RUNNING
```

但这里还存在一个明显断点：

> 测试真正跑完以后，AgentCore 怎么知道它成功还是失败？

过去 WP3 有一条测试用 callback：

```text
caller
→ POST SUCCESS / FAILED
```

这种方式不适合作为正式业务 Truth，因为用户完全可以自己声明：

```text
“这个任务失败了”
```

甚至自己提交错误信息。

WP9 把 canonical 路径改成：

```text
ExternalExecutionJob
→ stored external_execution_id
→ 查询 TestExecutionPlatform
→ 取得 provider-owned result/log
→ 普通代码解析结果
→ existing ingest_result()
```

caller 现在只能说：

```text
“观察一下这个 Job”
```

不能决定结果。

------

# 3. 工程构建方法问答

## 为什么不能让 caller 直接提交 SUCCESS / FAILED？

因为这属于执行事实。

例如真实测试平台实际上是：

```text
FAILED
```

但 caller 提交：

```text
SUCCESS
```

如果系统直接相信，就会导致：

```text
Mission COMPLETED
```

从而把真实失败吞掉。

所以现在：

```text
CALLER_SELF_REPORTED_RESULT = NON_CANONICAL
```

正式结果只能由 Provider Observation 得到。

------

## 为什么 observe API 只接受 job_id？

因为 AgentCore 自己拥有：

```text
ExternalExecutionJob
```

里面已经保存了：

```text
external_execution_id
environment
execution-list
```

所以 caller 只需要表达：

> 我想观察 AgentCore 里的这个 Job。

然后后端自己解析：

```text
job_id
→ external_execution_id
```

caller 不需要、也不应该传外部执行 ID。

------

## 为什么 Platform status 不直接决定 SUCCESS / FAILED？

因为当前设计把两个职责拆开了。

Platform status 回答：

```text
“这个任务还在跑吗？”
“已经结束了吗？”
```

固定日志回答：

```text
“最终到底是成功还是失败？”
```

所以：

```text
Provider Status
→ terminal readiness

ExecutionResultParser
→ SUCCESS / FAILED
```

这样不会出现两个地方同时拥有最终结果 Authority。

------

## 为什么不用 LLM 看日志判断成功还是失败？

因为日志格式是固定的。

例如：

```text
STATUS=FAILED
ERROR_CODE=XXX
ERROR_MESSAGE=...
FAILED_STEP=...
```

这种事情普通代码可以精确解析。

让 LLM 去判断：

```text
“我觉得这应该算失败”
```

反而会引入不稳定性。

所以：

```text
Parser：
发生了什么？

Triage Agent：
为什么可能发生？
```

------

## Parser 和 Failure Triage 的边界是什么？

Parser 负责：

```text
SUCCESS / FAILED
error_code
error_message
failed_step
```

Triage 负责：

```text
PRODUCT
TEST_DATA
ENVIRONMENT
TOOL_CHAIN
INFRASTRUCTURE
UNKNOWN
```

以及：

```text
可能的原因
下一步建议
```

也就是：

> **确定性事实用代码，模糊归因用 Agent。**

------

## 如果日志格式解析失败怎么办？

不能默认：

```text
SUCCESS
```

也不能默认：

```text
FAILED
```

当前做法是：

```text
malformed
→ 不 ingest
→ 不 Triage
→ 保持可恢复状态
```

以后日志正常了，再 observe 一次还能继续处理。

------

## 如果执行平台说已经结束，但日志还没写好怎么办？

这种情况真实系统里很常见：

```text
Execution process finished
↓
log flush / aggregation still in progress
```

所以：

```text
remote terminal
+
result ready=false
```

不能立即猜结果。

当前行为：

```text
不 ingest
不 Triage
等待下一次 observation
```

------

## 为什么不用 HTTP 一直轮询直到测试结束？

因为测试可能：

```text
几十分钟
几小时
```

如果一个 HTTP request：

```text
query
sleep
query
sleep
```

一直挂着，

就把：

```text
业务任务生命周期
```

错误绑定到了：

```text
HTTP 请求生命周期
```

WP9 只实现：

```text
observe_once()
```

以后无论：

```text
Web polling
Scheduler
Kafka Worker
```

都只需要反复调用它。

------

## 为什么 Observation 也走 Tool Runtime？

因为 Environment / Test Platform 都是外部 Provider。

即使 observation 是 read-only：

```text
stage8_get_execution_status
stage8_get_execution_result
```

也继续走：

```text
ToolRegistry
→ Governance
→ ToolExecutionService
→ Adapter
→ TestExecutionPlatform
```

这样外部平台访问不会出现第二条旁路。

------

## Read-only 为什么不需要审批？

因为：

```text
query status
read result
```

没有外部写副作用。

所以可以经过 Governance，但不需要 HITL。

------

## 为什么 Result Observation 不自己改 Job 状态？

因为 WP3 已经有成熟的：

```text
ingest_result()
```

负责：

```text
row lock
terminal first-wins
Mission transition
FailureEvidencePackage
Triage claim
```

如果 WP9 自己再写：

```text
if success:
    job.status = ...
```

就会出现第二套状态机。

所以 WP9 只做：

```text
Provider Observation
→ NormalizedExecutionResult
→ ingest_result()
```

------

## 为什么 Terminal First-wins 很重要？

假设：

```text
第一次 observe
→ SUCCESS
→ Job SUCCEEDED
```

后来 Provider 因为延迟或数据异常又返回：

```text
FAILED
```

如果允许覆盖：

```text
SUCCEEDED → FAILED
```

整个业务状态就不稳定。

所以第一次接受的 terminal result 是 durable truth。

后续 observation 直接返回已有 terminal Job。

------

## 两个 observe 同时看到 FAILED 怎么办？

两个请求都可能：

```text
Provider → FAILED
```

但最后都会进入已有：

```text
ingest_result()
```

内部通过：

```text
PostgreSQL row lock
+
triage claim
```

保证：

```text
一个 terminal result
一个 Triage
```

不会生成两份 TicketDraft 或两次 Approval。

------

## 为什么不保存完整日志？

因为日志可能非常大。

如果直接：

```text
完整日志
→ PostgreSQL JSONB
→ Prompt
```

会带来：

```text
数据库膨胀
Prompt token 膨胀
延迟
成本
```

所以当前只保存：

```text
result_location
normalized fields
bounded log excerpt
```

完整日志仍然留在原始执行平台。

------

## 16 KiB 限制为什么容易踩坑？

如果简单做：

```text
log[:16KB]
→ parser
```

而真正：

```text
STATUS=FAILED
```

写在文件末尾，

结果就永远解析不到。

Sol 最后修成：

```text
Provider Adapter
→ 扫描完整 deterministic log 找决定性字段

然后：
→ 只保留受限 head/tail excerpt
```

所以：

```text
解析边界
!=
持久化边界
```

------

## 为什么要区分 Parse Boundary 和 Persist Boundary？

因为：

> “我需要读取多少，才能知道发生了什么”

和：

> “我需要保存多少，才能供后续分析”

不是一回事。

正确设计：

```text
完整/足够扫描
→ 得到 status / error fields

持久化
→ 只存 bounded excerpt
```

这样兼顾结果准确性和存储成本。

------

## result_location 为什么不能直接当成本地文件路径打开？

因为它属于：

```text
Provider-owned opaque reference
```

可能是：

```text
远端路径
对象存储地址
平台内部 ID
```

AgentCore 不应该：

```text
Path(result_location).read_text()
```

否则会重新引入 Arbitrary Filesystem Access。

当前只把它作为元数据保存，由 Adapter 负责访问。

------

## 日志内容是不是可信的？

不是。

即使来自公司内部平台，它依然属于外部数据。

例如日志里出现：

```text
Ignore previous instructions
```

这只是日志内容。

不能成为系统 Prompt 指令。

当前 Triage 只把 bounded excerpt 当 Evidence Data。

------

## 为什么还保留 WP3 的 callback？

主要是：

```text
provider/test compatibility
```

以及旧 focused tests。

但是已经不允许普通用户调用。

现在必须：

```text
SERVICE principal
+
localagent:stage8:result-callback
```

Web Demo 也已经切到：

```text
observe API
```

所以 callback 不再是 canonical 用户路径。

------

## 如果未来真实测试平台支持 Webhook 呢？

那条 callback 可以重新成为：

```text
Provider Callback Adapter
```

但前提是：

```text
认证
来源绑定
execution identity 验证
```

而不是普通用户直接 POST 一个结果。

------

# 4. 30 秒项目回答

> 测试启动以后我没有让用户自己上报成功失败，而是根据 durable ExternalExecutionJob 去查询已有测试平台的执行状态和固定结果日志。平台状态只负责告诉我任务有没有结束，真正的 SUCCESS/FAILED 由普通代码解析固定格式日志。解析完成后我不重新写一套状态机，而是继续调用原来的 ingest_result，复用 terminal first-wins、FailureEvidencePackage 和一次性 Triage。完整日志不落库，只保存受限 excerpt，避免大日志把 PostgreSQL 和 Prompt 撑大。

------

# 5. 2 分钟项目回答

> 测试执行平台启动任务以后会返回 external_execution_id，但真实测试可能跑几个小时，所以 Agent Run 不会一直等待。
>
> WP9 做的是一个可重入的 observe_once。调用方只能给 AgentCore 自己的 job_id，后端从 ExternalExecutionJob 里拿 external_execution_id，通过 Tool Runtime 查询 TestExecutionPlatform。普通 caller 不能自己提交 SUCCESS、FAILED 或日志路径。
>
> Platform status 只负责告诉系统任务还在运行还是已经结束，真正的成功失败由固定格式日志决定。日志里的 STATUS、ERROR_CODE、ERROR_MESSAGE 和 FAILED_STEP 用普通 parser 解析，LLM 不参与这一步。
>
> 如果结果日志还没准备好或者格式无法解析，就不猜成功失败，也不触发 Triage，下一次 observation 还能恢复。真正得到 terminal result 后，再转成现有 ExecutionResult，继续调用 WP3 的 ingest_result，所以 row lock、terminal first-wins、Mission 状态迁移和 Triage claim 都只有一套实现。
>
> 大日志方面也做了边界。Provider Adapter 可以扫描完整日志获取决定性字段，但 PostgreSQL 和 Prompt 只保存 16 KiB 的 head/tail excerpt 以及归一化错误字段。所以解析正确性和存储限制是分开的。
>
> 另外之前的 self-report callback 还保留用于 Provider/Test Service，但普通用户已经不能调用，Web Demo 现在只走 observe API。

------

# 6. 高频追问 + 简答

## 测试结束以后是谁通知 AgentCore？

当前 WP9 没有自动 scheduler。

是：

```text
外部触发
→ observe_once(job_id)
```

后续可以由 Web polling、Scheduler 或 Kafka Worker 调用。

------

## 那现在算自动化吗？

业务操作已经自动化，但触发仍需要外部调度。

所以不能说：

> 已实现全自动后台持续轮询。

------

## 为什么不现在做 scheduler？

因为先把：

```text
observe_once()
```

做成正确、幂等的业务操作更重要。

Scheduler 只是“什么时候调用它”。

------

## 为什么不用 Kafka？

Kafka 可以以后负责：

```text
ObservationRequested
TerminalObserved
```

但它不能替代结果 Parser、Job 状态和 ingest_result。

所以当前没必要为了用了 Kafka 而加 Kafka。

------

## 如果日志超大怎么办？

完整日志留在执行平台。

AgentCore：

```text
扫描需要的信息
+
保存 bounded excerpt
```

------

## 16 KiB 会不会导致结果判断错误？

不会。

最终实现不是只解析前 16 KiB。

Provider Adapter 会扫描完整 deterministic log 找决定性字段，再生成最多 16 KiB excerpt。

------

## 如果日志最后才有 FAILED 呢？

仍然可以识别。

Final Gate 专门验证了 marker 在 16 KiB 和 1000 行以后仍可观察。

------

## 如果两次 observation 得到不同结果呢？

第一次被接受的 terminal result 为准。

后续不会覆盖。

------

## 为什么？

因为业务事实必须稳定。

否则：

```text
COMPLETED
→ FAILED
→ COMPLETED
```

不断翻转，后续 Ticket、报告都会失去一致性。

------

## 如果结果解析错了怎么办？

这是 Parser Contract / Log Format 的问题。

当前 Mock format 是 deterministic 的。

真实接公司平台时要针对真实日志格式实现对应 Adapter/Parser，而不能直接宣称当前 Parser 已支持真实生产日志。

------

## 为什么 error_message 也要限长？

因为一个固定字段也可能非常大。

如果只限制 log excerpt，却允许：

```text
ERROR_MESSAGE = 5MB
```

仍然会把 DB 和 Prompt 撑大。

所以 normalized fields 也需要独立 bound。

------

## 旧 callback 现在还能用吗？

能，但只给：

```text
SERVICE principal
+
narrow scope
```

使用。

普通用户不能再自己提交执行结果。

------

## UNKNOWN 怎么处理？

当前：

```text
UNKNOWN / lost-result reconciliation
```

还没实现。

这是明确 Accepted Limitation。

------

# 7. Bad Case

## Real Bad Case 1 — 用户自己点击 FAILED

以前 Web Demo 可以：

```text
用户
→ POST FAILED
→ ingest_result
→ Triage
```

这意味着人可以制造一个假的失败事实。

WP9 后：

```text
Web caller
→ observe(job_id)
```

真正结果由 Provider Observation 决定。

Legacy callback 只允许受限 SERVICE principal。

------

## Real Bad Case 2 — 只截前 16 KiB 再解析

错误路线：

```text
完整日志 100KB
→ 只拿前 16KB
→ Parser
```

如果：

```text
STATUS=FAILED
```

在文件末尾，

系统会误判 malformed。

最终修成：

```text
扫描完整日志决定字段
→ bounded head/tail excerpt 持久化
```

------

## Real Bad Case 3 — Observation 自己实现状态迁移

错误：

```text
observe
→ job.status = FAILED
→ triage()
```

这会产生第二套状态机。

最终：

```text
observe
→ ExecutionResult
→ existing ingest_result()
```

继续复用 WP3。

------

## Real Bad Case 4 — Duplicate Observe 产生两次 Triage

两个并发请求：

```text
observe
observe
```

同时得到 FAILED。

如果没有 row lock / claim：

```text
Triage A
Triage B
TicketDraft A
TicketDraft B
```

最终依靠已有：

```text
row lock
+
conditional triage claim
```

只执行一次。

------

## Real Bad Case 5 — Provider 返回 result_location 后本地直接打开

错误：

```text
Path(provider_result_location).read_text()
```

如果 Provider / caller 能控制这个字符串，就重新产生目录穿越和 Arbitrary Filesystem Access。

当前：

```text
result_location = opaque metadata
```

只由 Adapter 负责访问。

------

## Real Bad Case 6 — Malformed Log 默认成功

错误：

```python
if "FAILED" not in log:
    success = True
```

这会把所有未知格式都当成功。

现在：

```text
无法严格解析
→ no result
→ no ingest
```

------

# 8. Truth / Owner / Completion Boundary

## Job Identity

Owner：

```text
AgentCore ExternalExecutionJob
```

caller 只给内部 `job_id`。

------

## External Execution Identity

Owner：

```text
TestExecutionPlatform
```

存储在 Job 中。

caller 不提交。

------

## Provider Execution Status

Owner：

```text
TestExecutionPlatform
```

用于判断：

```text
still running / terminal ready
```

------

## SUCCESS / FAILED

Owner：

```text
ExecutionResultParser
+
Provider result/log
```

不是 LLM，也不是 caller。

------

## error_code / error_message / failed_step

Owner：

```text
fixed-format provider result
```

Parser 负责提取。

------

## Failure Root Cause

Owner：

```text
Failure Triage Agent
```

它使用已经确定的 FailureEvidencePackage 做归因。

------

## Job Terminal State

Owner：

```text
existing Stage8ExecutionService.ingest_result()
```

Observation Service 不拥有。

------

## Triage Execution

Owner：

```text
existing triage claim
```

一次失败只能正式触发一次。

------

## Log Location

Owner：

```text
TestExecutionPlatform
```

AgentCore 视为 opaque reference。

------

## Full Log

Owner：

```text
原始测试/日志平台
```

AgentCore 不持久化完整内容。

------

## WP9 已完成

当前真实完成：

```text
ExternalExecutionJob
→ canonical observe API
→ governed Platform status query
→ governed result query
→ deterministic parser
→ bounded evidence
→ existing ingest_result
→ SUCCESS or one Failure Triage
```

------

## WP9 尚未完成

当前没有：

```text
真实企业 TestExecutionPlatform transport/auth

真实企业日志格式

background scheduler

Kafka observation worker

cancellation

UNKNOWN reconciliation

lost-result recovery

object storage

完整 Stage8 object-level RBAC
```

------

# 9. 当前 Stage8 主链

做到 WP9 后，当前业务主链已经可以描述为：

```text
Feature
→ Feature Understanding
→ Risk Analysis
→ TestPlan
→ Human Review

→ Case Generation Platform
→ GeneratedCaseArtifact

→ Environment Platform
→ 找满足条件的 FREE 环境
→ pre-execution recheck

→ execution-list.xls
→ Test Execution Platform
→ ExternalExecutionJob

→ Provider Observation
→ fixed-format log parsing

SUCCESS
→ Mission COMPLETED

FAILED
→ FailureEvidencePackage
→ Failure Triage
```

这时候真正还没有闭上的主要业务链已经不是“测试怎么跑”，而是：

```text
PRODUCT
→ TicketDraft
→ Approval
→ ?
```

下一 WP 就是补这个问号。

------

# 10. 本 WP 最应该记住的五句话

第一句：

> **执行结果属于外部测试平台事实，普通用户不能自己声明 SUCCESS 或 FAILED。**

第二句：

> **固定格式能确定的 SUCCESS、FAILED 和错误字段用普通代码解析，不交给 LLM。**

第三句：

> **Observation 只负责获取事实，真正的终态状态迁移继续复用原来的 ingest_result。**

第四句：

> **日志解析需要多少内容和数据库最终保存多少内容，是两个不同的边界。**

第五句：

> **一次 observe 应该是幂等、可重入的业务操作，至于以后由 Web、Scheduler 还是 Kafka 触发，是另一层问题。**