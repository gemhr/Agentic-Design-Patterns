# Stage5-Phase8-WP1 — Tool Discovery / Selection / Native Function Calling 学习与面试总结

## 1. 本 WP 解决什么问题

### 1.1 原始真实问题

这是一个：

```text
USER_REPRODUCED_BAD_CASE
```

Phase7 完成 Tool Governance（工具治理）和 HITL（Human-in-the-Loop，人类在环）后，真实 Desktop 测试发现：

用户为了稳定触发高风险 Tool，几乎必须自己输入：

```text
complex_workflow_simulator
NON_IDEMPOTENT_SIMULATION
operation_id
resource_key
items
processing_options
完整 JSON
```

系统虽然已经具备：

```text
Tool Registry
Tool Governance
Approval
Execution Claim
HITL
ToolExecutionService
Journal
```

但用户体验依然接近：

```text
User
↓
自己知道 Tool name
↓
自己选择 Tool
↓
自己理解 execution_mode
↓
自己构造 wire JSON
↓
Agent 负责执行
```

这意味着：

> Runtime Safety 已经比较完整，但 Agent Tool Use 本身还没有真正成立。

我们希望形成：

```text
User
自然语言业务意图
        ↓
Agent / Model
Tool Discovery
Tool Selection
Argument Construction
        ↓
Runtime
Validation
Governance
HITL
Execution
```

核心原则：

> **不要让 User 充当 Tool Router。**

同时还有另一条更重要的安全原则：

> **不要为了让 Model 更聪明，把 Runtime Safety 交给 Model。**

------

# 2. 源码审计发现的真正根因

Codex Source Audit 证明：

问题不在 Registry、Governance、HITL 或 Execution。

它们原本就是可工作的。

真正问题位于：

```text
User
↓
Model
↓
ToolInvocation
```

这一段。

原实现中模型最终只能看到：

```text
ToolDescriptor(
    name,
    description
)
```

Planner Prompt 近似：

```text
- tool_name: description
```

而 Tool 调用协议只是：

```text
CALL: tool_name(argument_text)
```

模型看不到：

```text
字段业务含义
required / optional
defaults
examples
什么时候使用
什么时候不要使用
哪些字段应该由系统生成
```

与此同时：

```text
_tool_intent_likely()
```

还通过硬编码关键词决定：

```text
是否值得进入 Tool Planner
```

因此存在两个问题：

```text
问题 A：
用户语义没命中关键词
→ Planner 根本看不到 Tool

问题 B：
即使进入 Planner
→ Model 只有 name + description
→ 必须猜 Runtime wire JSON
```

`complex_workflow_simulator` 的问题尤其严重，因为它的 DTO 同时包含：

```text
业务参数
+
operation identity
+
idempotency identity
+
failure injection
+
processing control
+
timeout
```

这实际上把：

```text
Runtime Wire Contract
```

错误暴露成了：

```text
User Intent Contract
```

------

# 3. WP1 第一阶段：LLM-facing Tool Contract

## 3.1 为什么不重构 Tool Registry

当时的候选方案：

```text
A. ToolRegistryV2
B. 新建 LLM Tool Catalog
C. 新建 Agent Tool Framework
D. 扩展现有 ToolDescriptor
```

最终选择：

```text
D. 扩展现有 ToolDescriptor
```

因为现有：

```text
ToolRegistry
ToolRegistration
ToolAdapter
ToolInvocation
ToolGovernanceService
ToolExecutionService
```

Owner 都是正确的。

真正缺少的只是：

```text
LLM-facing Tool Metadata
```

也就是：

> 模型应该如何理解这个 Tool。

因此只增强现有 ToolDescriptor，而没有制造：

```text
ToolRegistryV2
ToolFrameworkV2
ParallelToolCatalog
```

### 面试表达

> 我们先确认问题是 Tool 的 Model-facing surface 不够，而不是 Runtime Registry 架构有问题，所以没有为了“工具调用不好用”重写整套 Tool Framework，只扩展现有 Descriptor。

------

# 4. LLM-facing Metadata 与 Governance Metadata

这是整个 WP1 最重要的设计边界之一。

## LLM-facing Metadata

告诉 Model：

```text
这个 Tool 是做什么的
什么时候应该调用
什么时候不应该调用
每个业务参数是什么意思
哪些参数可以默认
```

例如：

```text
resource_key
items
action
quantity
execution intent
```

------

## Governance Metadata

告诉 Runtime：

```text
Risk
Side Effect
Idempotency
Authorization
Approval Threshold
Execution Policy
```

两者必须分开。

因为如果让 Model 输出：

```text
risk = LOW
approved = true
approval_required = false
```

然后 Runtime 信任模型：

安全边界就完全失效。

所以 LocalAgent 最终保持：

```text
Model
↓
选择 Tool
↓
构造业务参数
↓
ToolAdapter
↓
spec_for()
↓
Runtime 派生 side-effect / idempotency
↓
ToolGovernanceService
↓
Risk / Approval
```

一句话：

> **Model 描述意图，Runtime 判定事实。**

------

# 5. Argument Construction 的责任划分

审计后对 `complex_workflow_simulator` 输入进行了重新分类。

## Agent / User 业务语义

```text
resource_key
items
item_id
action
quantity
execution intent
```

这些应该来自：

```text
用户自然语言
→ Agent 推断
```

------

## System Generated

例如：

```text
operation_id
idempotency_key
```

这些属于 Runtime 技术 identity。

普通用户不应该知道。

------

## Defaultable

例如：

```text
priority
attributes
processing_options
```

如果用户没有特殊要求：

使用系统默认值。

------

## Test-only / Hidden

例如：

```text
failure_injection
failure_stage
failure_item_id
```

它们属于 deterministic fault testing 能力。

普通业务 Tool surface 不应该展示。

------

## Runtime Derived

例如：

```text
requested_timeout_seconds
```

不应要求 Model 或 User 填。

------

# 6. 为什么 System 生成 operation_id

`operation_id` 是：

```text
technical invocation identity
```

不是：

```text
business intent
```

用户真正关心：

```text
对哪个 resource
执行什么 action
quantity 是多少
```

而不是 UUID 怎么生成。

所以最终：

```text
operation_id
→ Adapter / System generated
```

------

# 7. Idempotency Key 的真实完成边界

`IDEMPOTENT_COMMIT` 下：

```text
idempotency_key
```

也可以系统生成。

但当前合同只保证：

```text
一个最终 ToolInvocation
+
该 invocation Runtime retry
```

使用同一个 key。

它不保证：

```text
跨重新规划
跨 Run
跨用户重新提交
跨进程重启
```

依然保持同一 logical idempotency identity。

这属于：

```text
ACCEPTED_LIMITATION
```

### 面试追问

**问：那你这个幂等是不是不完整？**

答：

> 当前实现解决的是单 invocation 的执行重试幂等，不是跨 Run 的业务级 exactly-once。跨 Run 需要持久化 idempotency contract，是另一个层级的问题。

------

# 8. Tool Intent Gate 的第一次演进

原实现：

```text
关键词没命中
→ Tool Planner 不执行
```

导致自然语言召回率太低。

ZCode 第一版为了修复它，直接改成：

```text
所有非空请求
→ Tool Planner
```

这个方案表面解决 recall：

```text
召回率 ↑
```

但 Codex Review 发现新的真实问题：

```text
你好
解释一下幂等
Python decorator 是什么
```

所有普通聊天都增加一次：

```text
self.llm.generate()
```

也就是说：

```text
普通回答本来 1 次 LLM

变成：

Tool Planner
+
Final Model

= 2 次
```

影响：

```text
Latency
Token Cost
Monetary Cost
Observability
Budget semantics
```

最终改成：

```text
Cheap deterministic prefilter
↓
疑似业务动作
↓
Tool Planner
```

Model 仍然负责最终语义 Tool Selection。

这个 Bad Case 非常适合面试：

> **不能为了 Tool Recall 直接把所有请求都送进昂贵的 Semantic Planner。**

------

# 9. Prompt-based Tool Calling

WP1 第一版完成后实际结构：

```text
Tool Registry
↓
render_for_planner()
↓
Prompt
↓
LLM
↓
CALL: tool_name(json)
↓
Parser
↓
ToolAdapter
↓
Governance
```

这里叫：

```text
Prompt-based Structured Tool Calling
```

因为模型本质上还是在输出：

```text
普通字符串
```

只是 Runtime 约定：

```text
CALL: xxx(...)
```

代表 Tool Call。

------

# 10. Bounded Validation Repair

Prompt-based Tool Calling 最大的问题之一：

Model 仍然可能产生：

```text
错误 JSON
错误 enum
缺少 required field
错误字段类型
```

所以增加：

```text
Bounded Repair
```

流程：

```text
Model Arguments
↓
ToolAdapter.build_invocation()
↓
Validation FAIL
↓
一次 Repair
↓
重新 Validation
↓
PASS / FAIL
```

严格：

```text
MAX_REPAIR = 1
```

为什么不能无限？

因为无限 Repair 会：

```text
成本不可预测
延迟不可预测
模型循环
参数语义漂移
```

而且必须发生在 Governance 之前：

```text
arguments
↓
validation
↓
repair
↓
final valid invocation
↓
Governance
```

------

# 11. 为什么 Validation 必须早于 Governance

这是 WP1 / WP1N 中一个非常重要的工程知识点。

正确：

```text
Untrusted Model Arguments
↓
Typed Validation
↓
Immutable ToolInvocation
↓
Governance
```

不能：

```text
Invalid Arguments
↓
Governance
↓
再 Validation
```

因为 Governance 做的是：

```text
Authorization
Risk
Side-effect
Idempotency
Approval
```

它必须评估：

> **Runtime 真正认可的、最终准备执行的 invocation。**

否则会出现：

```text
Governance 判断的是 A
最终执行的是 B
```

即使当前不执行，也会污染：

```text
Audit
Policy Events
Approval Preparation
Quota
Cache
未来副作用
```

------

# 12. 为什么后来决定升级 Native Function Calling

完成 Prompt-based WP1 后，又进行一次 Codex Feasibility Audit。

前提改变为：

> LocalAgent 当前明确只需要支持 DeepSeek。

审计发现：

当前 DeepSeek Chat Completions Provider 实际支持：

```text
tools
tool_choice
assistant.tool_calls[]
tool_call.id
function.name
function.arguments
```

并且做了真实官方 API capability probe：

```text
HTTP 200
finish_reason = tool_calls
tool_call_count = 1
```

同时当前：

```text
Thinking = OFF
```

所以升级 Native Function Calling 的真实复杂度被评估为：

```text
CHANGE_SIZE = MEDIUM
TASK_RISK = M
ARCHITECTURE_REOPEN_REQUIRED = NO
```

这时继续保留 `CALL:` parser 的收益已经不高。

------

# 13. Prompt-based vs Provider-native

Prompt-based：

```text
Model
↓
普通文本
↓
CALL: xxx(...)
↓
自己 Parse
```

Native：

```text
DeepSeek
↓
assistant.tool_calls[]
↓
function.name
function.arguments
tool_call.id
```

最大的变化只是：

```text
Model Protocol Layer
```

后面的：

```text
ToolAdapter
Governance
HITL
ToolExecutionService
```

全部继续复用。

------

# 14. Native Function Calling 最终架构

最终 DeepSeek Native 路径：

```text
User
↓
Model Capability Check
↓
DeepSeek Chat Completion
tools=[...]
tool_choice=auto
↓
0 Tool Call
OR
1 Native Tool Call
↓
NativeToolCall normalization
↓
ToolAdapter.build_invocation()
↓
Typed Validation
↓
Optional one same-tool repair
↓
Immutable ToolInvocation
↓
authorize_tool
↓
spec_for()
↓
ToolGovernanceService
↓
ALLOW / DENY / APPROVAL_REQUIRED
↓
ToolApprovalController
↓
ToolExecutionService
↓
assistant(tool_calls)
+
role=tool / tool_call_id
↓
DeepSeek Final Continuation
```

这就是最终真实主链。

------

# 15. 为什么 Native Function Calling 仍要 Typed Validation

Provider native schema 并不是 Runtime Security Contract。

DeepSeek 仍可能产生：

```text
错误 JSON
错误业务值
不存在的字段
非法 enum
逻辑不合理参数
```

所以：

```text
Provider Tool Call
```

只能认为：

```text
Model Intent Surface
```

不能认为：

```text
Validated ToolInvocation
```

依然必须：

```text
function.arguments
↓
ToolAdapter.build_invocation()
↓
Typed Validation
```

------

# 16. Native Schema 怎么设计

这里没有建设：

```text
ToolDefinitionV2
SchemaRegistryV2
```

而是：

```text
Existing ToolAdapter / DTO Contract
↓
Native Function Schema Projection
```

例如 simulator Native Schema 只暴露：

```text
resource_key
execution_mode
items
```

不会暴露：

```text
operation_id
idempotency_key
failure_injection
failure_stage
timeout
metadata
risk
approval
```

这样 Native Function Schema 仍然只是：

```text
LLM-facing projection
```

真正的 Runtime validation Source of Truth 仍在 Adapter / DTO。

------

# 17. DeepSeek tool_call.id 为什么不能当 Runtime ID

DeepSeek 返回：

```text
tool_call.id
```

但最终明确：

```text
provider_tool_call_id
=
TRACE_ONLY_AND_CONTINUATION_CORRELATION
```

它只能用于：

```text
assistant tool_calls
↔
role=tool
```

之间做 Provider message correlation。

不能成为：

```text
operation_id
idempotency_key
ToolInvocation ID
approval binding
execution claim
```

原因：

> Provider identity 和 Runtime security identity 属于两个不同信任域。

------

# 18. Native Tool Result Continuation

Native Function Calling 不是只解析一次 Tool Call。

完整协议：

```text
User
↓
Assistant:
tool_calls=[...]
↓
Runtime executes Tool
↓
Tool message:
role=tool
tool_call_id=...
content=...
↓
DeepSeek
↓
Final Assistant Answer
```

所以 Tool result 不能再仅仅：

```text
拼成普通 Context 文本
```

而需要真正保持：

```text
assistant(tool_calls)
+
tool(role, tool_call_id)
```

消息协议。

------

# 19. Duplicate Execution Safety

Native Function Calling 引入了新的风险：

```text
Tool 已执行成功
↓
Final continuation LLM 调用失败
```

错误做法：

```text
重新开始 selection
↓
再次执行 Tool
```

可能造成：

```text
Duplicate Side Effect
```

最终明确拆成：

```text
Phase A
Model Tool Selection

Phase B
Tool Execution

Phase C
Final Model Continuation
```

Tool 一旦执行成功：

```text
Phase C retry
```

只能：

```text
重试 Final Continuation
```

不能：

```text
返回 Phase A
```

所以：

```text
Tool execution count = exactly 1
```

------

# 20. Native Bounded Repair

Native Function Calling 后 Repair 不再使用：

```text
CALL: xxx(...)
```

而是：

```text
Native Tool Call
↓
Validation FAIL
↓
一次 Native Correction
↓
same Tool
↓
Native Tool Call
↓
Revalidate
```

必须：

```text
same Tool
MAX_REPAIR=1
```

如果 repair：

```text
返回 content
换 Tool
返回多个 Tool
第二次仍 invalid
```

全部：

```text
FAIL CLOSED
zero Governance
zero Approval
zero Execution
```

------

# 21. Real Bad Case — Repair Failure 进入 Governance

这是：

```text
CODEX_REVIEW_DISCOVERY
```

第一版 Native Repair 存在：

```text
Validation FAIL
↓
Repair FAIL
↓
validated_invocation=None
↓
_prepare_answer_messages()
↓
authorize_tool()
↓
再次 Validation FAIL
```

虽然：

```text
Approval = 0
Execution = 0
```

但仍违反：

```text
Validation-before-Governance
```

最终 fix：

```text
Repair FAIL
↓
直接 Tool validation failure
↓
END
```

并增加 spy：

```text
Governance = 0
Approval = 0
Execution = 0
```

------

# 22. Real Bad Case — Native Capability Boundary

这是整个 WP1 最值得讲的一个 Review Bad Case。

第一版 Native Integration 做了：

```text
Unified Invocation
↓
无条件 tools/tool_choice
```

默认：

```text
所有 Model Engine
```

都支持 Native Function Calling。

但真实系统还有：

```text
LocalLLMEngine
```

并不支持。

------

## 情况 A：直接崩溃

Local Engine：

```text
generate()
```

不接受：

```text
tools
tool_choice
```

于是：

```text
TypeError
↓
RUNTIME_EXECUTION_FAILED
```

------

## 情况 B：更危险的 Silent Failure

有的 Fake Engine：

```python
generate(**kwargs)
```

所以不会 TypeError。

但是它实际上：

```text
不支持 Native Tool Calling
```

于是：

```text
tools 被静默忽略
↓
native_tool_call=None
↓
模型普通回答
```

结果原来应该：

```text
Permission / Approval / Resource Gate
↓
DENY
```

的场景可能变成：

```text
Model normal answer
```

虽然没有发生越权执行，但破坏了：

```text
Governance denial before final answer
```

的既有合同。

------

# 23. Capability-aware Routing

最终修复：

```text
supports_native_tool_calling()
```

能力声明。

而不是：

```text
if provider == "deepseek"
```

最终：

```text
Selected Model Profile
↓
Model Adapter
↓
Capability Check
        ↓
       / \
      /   \
 Native   Non-native
   |          |
tools      existing Tool path
```

为什么不用 Provider 名称判断？

因为：

```text
Provider Identity
≠
Runtime Capability
```

未来同一个 Provider：

```text
不同模型
不同 endpoint
不同模式
```

支持能力也可能不同。

------

# 24. Capability Fail-closed

还有一个很好的设计：

即使某个 Engine：

```python
generate(**kwargs)
```

可以吞掉任意参数，

如果：

```text
supports_native_tool_calling = false
```

Adapter 也会：

```text
NATIVE_TOOL_CALLING_UNSUPPORTED
```

fail closed。

这样避免：

```text
未知参数被静默忽略
```

这种非常隐蔽的错误。

------

# 25. 最终 Owner Map

| Responsibility                | Owner                               |
| ----------------------------- | ----------------------------------- |
| Tool Registry                 | `ToolRegistry`                      |
| Tool Native Schema Projection | ToolRegistration / ToolAdapter 附近 |
| Native Capability             | Model Adapter / Engine              |
| Provider Wire Normalization   | `RemoteLLMEngine`                   |
| Semantic Tool Selection       | DeepSeek Native Tool Calling        |
| Argument Construction         | Model + system/default              |
| Typed Validation              | `ToolAdapter.build_invocation()`    |
| Invocation Spec               | `adapter.spec_for()`                |
| Governance                    | `ToolGovernanceService`             |
| Approval                      | `ToolApprovalController`            |
| Execution                     | `ToolExecutionService`              |
| Runtime Identity              | Local Runtime                       |
| Provider Correlation ID       | DeepSeek `tool_call.id`             |
| Final Continuation            | Model invocation layer              |

最关键的一句话：

> **Provider 负责表达调用，Runtime 负责接受、治理和执行调用。**

------

# 26. 真实性与完成边界

## 已真实实现

```text
LLM-facing Tool Metadata
Natural-language Tool Selection
System-generated operation identity
Bounded Validation Repair
DeepSeek Native Function Calling
Native Tool schema
Native ToolCall normalization
Native Tool-result continuation
Capability-aware routing
Non-native fallback
Multiple Tool call fail-closed
Validation-before-Governance
Continuation retry isolation
```

------

## 已真实测试

最终 Codex Gate：

```text
214 passed + 12 subtests
```

相关测试。

全量：

```text
3178 passed
12 failed
```

其中：

```text
12 failed
```

均为 HEAD 已存在 baseline。

WP1N：

```text
新增失败 = 0
```

------

## 已真实 DeepSeek API 验证

```text
SELECTION_TOOL_CALL = PASS
PROVIDER_ID_PRESERVED = PASS
TOOL_RESULT_CONTINUATION = PASS
```

使用真实 DeepSeek 官方 endpoint。

------

## 未实现 / Accepted Limitation

```text
DeepSeek only
Thinking Tool Calling disabled
Native Tool Streaming disabled
0/1 Tool Call only
No multi-provider abstraction
No parallel Tool Calling
No Tool RAG
No MCP yet
```

------

# 27. 名词 / 概念速览

### Tool Discovery（工具发现）

让适合当前请求的 Tool 成为 Model 可选择的候选。

### Tool Selection（工具选择）

Model 根据用户语义决定真正调用哪个 Tool。

### Argument Construction（参数构造）

把自然语言业务意图转换为结构化 Tool 参数。

### LLM-facing Metadata（面向模型元数据）

帮助 Model 理解 Tool 用途和输入方式的信息。

### Governance Metadata（治理元数据）

Runtime 用来判断 Risk、Authorization 和 Approval 的权威事实。

### Native Function Calling（原生函数调用）

通过 Provider API 的 `tools/tool_calls` 协议表达 Tool 调用。

### Prompt-based Tool Calling（基于提示词的工具调用）

让 Model 输出约定文本，再由 Runtime 自己解析。

### Capability Detection（能力检测）

运行时判断当前 Model/Adapter 是否真正支持某项能力。

### Fail Closed（失败关闭）

出现未知、非法或无法验证状态时拒绝继续，而不是默认允许。

### Typed Validation（强类型校验）

把模型参数验证并转换成 Runtime 可接受的 typed invocation。

### Bounded Repair（有界修复）

参数错误后只允许有限次数让 Model 修复。

### ToolInvocation（工具调用实例）

Runtime 已经接受的结构化、不可变 Tool 调用。

### Provider Correlation ID（Provider 关联 ID）

Provider 用于关联 Tool Call 和 Tool Result 的消息级 identity。

### Idempotency Key（幂等键）

用于识别可重试逻辑操作、防止重复副作用的 identity。

### Capability-aware Routing（能力感知路由）

根据 Model 实际能力选择 Native 或非 Native 调用路径。

### Validation-before-Governance

Governance 只能处理 Runtime 已验证的 ToolInvocation。

------

# 28. 工程构建方法类问答

## Q1：为什么先做 Prompt-based，后来又改 Native？

最初目标是快速证明：

```text
Natural Language
→ Tool Selection
→ Valid Invocation
```

当确认只用 DeepSeek 后，Native Function Calling 改造被审计为 M 级，收益已经高于继续维护文本协议，所以再迁移。

------

## Q2：Native Function Calling 后 Tool Registry 还有用吗？

有。

Provider `tools` 只是 Registry 的 Model-facing projection。

真正 Tool identity / Adapter binding 仍然由 Registry 管理。

------

## Q3：Native Function Calling 能代替 Governance 吗？

不能。

它只解决：

```text
Model 怎么表达 Tool Call
```

不解决：

```text
这个 Tool 能不能执行
风险是多少
是否要审批
```

------

## Q4：为什么 Native schema 不能作为最终校验？

因为 Provider schema 只约束 Model 输出格式，不能代替业务验证和安全规则。

------

## Q5：为什么 tool_call.id 不直接作为 invocation_id？

因为 Provider identity 不属于 Runtime trust domain。

Provider ID 只用于消息关联。

------

## Q6：为什么 Repair 后必须重新 Governance？

因为参数变化意味着 side-effect / idempotency / risk 都可能变化。

------

## Q7：为什么 multiple tool calls 直接 fail closed？

当前 Runtime 的 Stop Condition 是单 Tool Invocation。

为了快速闭环，不在 Phase8 引入 Parallel / Multi-tool orchestration。

------

## Q8：为什么用 capability 判断而不是 `provider == deepseek`？

Capability 是真实执行能力；Provider 名称只是身份。

同一个 Provider 的不同模型或 endpoint 能力可能不同。

------

## Q9：为什么还保留 non-native 路径？

因为 Runtime 真实还存在 Local / 非 Native Engine。

Native 是 capability enhancement，不应该破坏原有 Engine。

------

## Q10：为什么不顺手做 multi-provider？

因为真实需求是 DeepSeek-only。

为了“以后也许支持”提前做 Provider Framework 会扩大 Scope。

------

# 29. 高频面试追问 + 简单回答

## 1. 你们 Tool Selection 谁负责？

DeepSeek Native Function Calling 负责语义选择，Runtime 负责验证和执行。

------

## 2. Tool schema 从哪来？

从已有 ToolAdapter / DTO contract 做 LLM-facing projection，不维护独立 ToolDefinitionV2。

------

## 3. 模型能决定 risk 吗？

不能。risk 由 Adapter spec 和 Governance deterministic 计算。

------

## 4. 模型说“已经批准”有效吗？

无效。Approval Authority 在 `ToolApprovalController`。

------

## 5. Function Calling 还会参数错吗？

会，所以仍然需要 typed validation。

------

## 6. 参数错了怎么办？

最多一次 same-tool native repair，再失败就 fail closed。

------

## 7. 为什么只修一次？

控制延迟、成本和语义漂移。

------

## 8. Repair 换 Tool 怎么办？

直接失败，不能允许模型在 repair 阶段重新选择 Tool。

------

## 9. 多 Tool Call 怎么处理？

当前只支持 0/1，多个直接 fail closed。

------

## 10. 为什么不是 silently pick first？

因为可能丢掉 Model 的部分操作意图，也可能导致不可预测副作用。

------

## 11. Tool 已执行后 Final LLM 失败怎么办？

只重试 final continuation，不重新选择或执行 Tool。

------

## 12. 怎么避免重复执行？

执行阶段和 final continuation 阶段分离，并保持 execution claim / invocation identity。

------

## 13. Provider tool_call.id 有什么用？

只关联 assistant tool call 和 `role=tool` result。

------

## 14. idempotency_key 谁生成？

当前由 Runtime / Adapter 为需要的 invocation 生成。

------

## 15. idempotency_key 能跨 Run 吗？

当前不能保证，合同只覆盖最终 invocation 的 Runtime retry。

------

## 16. Native Function Calling 最大收益是什么？

结构化 Tool Call 更可靠，并且可以删除额外 Planner 调用和脆弱的 `CALL:` parser。

------

## 17. 为什么还需要 Tool description？

Native Function Calling 只规范输出格式，Model 仍然需要语义描述决定何时调用哪个 Tool。

------

## 18. 为什么你们不用 strict schema？

DeepSeek strict 当前属于 Beta，而且 Runtime typed validation 已经是 authoritative，所以当前不是必要条件。

------

## 19. Thinking Mode 为什么没做？

当前生产配置关闭 Thinking；开启后需要正确保存并回传 `reasoning_content`，会扩大 message contract。

------

## 20. Streaming Tool Call 为什么没做？

当前 Tool selection 本身是 non-streaming，Phase8 没有真实需求处理 tool-call delta。

------

## 21. Capability Detection 为什么重要？

因为不能假设所有 Model Engine 都支持 `tools`；否则会出现 TypeError 或静默吞参数。

------

## 22. 静默吞 tools 为什么危险？

Runtime 可能以为模型在执行 Native Tool Selection，但实际模型只返回普通文本，从而破坏已有 Governance 时序。

------

## 23. 为什么 Capability 应由 Adapter 报告？

Adapter 最接近实际 Engine 能力，可以避免 Router 硬编码 Provider 细节。

------

## 24. Local Engine 不支持 Native 怎么办？

继续走已有 Tool Planner / Governance 路径，不破坏原有合同。

------

## 25. Native 请求失败会 fallback 到 CALL parser 吗？

Native coordinated path 不会自动 fallback；失败必须 fail closed。

------

## 26. 为什么 Validation 要在 Governance 前？

Governance 必须只评估 Runtime 已经接受的最终 immutable invocation。

------

## 27. 如果 Governance 在 Validation 前有什么风险？

可能产生错误审计、错误 policy decision，甚至未来产生错误审批或配额副作用。

------

## 28. 这个 WP 最重要的工程 Trade-off 是什么？

智能性、成本和安全三者平衡：Model 负责语义理解，但所有安全决定留给 deterministic Runtime。

------

## 29. 为什么没做 Tool RAG？

目前只有几个 Tool，没有检索规模问题，直接把小型 Tool catalog 给模型更简单可靠。

------

## 30. 接下来为什么适合做 MCP？

因为 Local Tool 的：

```text
Discovery
Selection
Arguments
Validation
Governance
Execution
```

已经跑通。

MCP 下一步只需要作为新的 Tool Provider 接入，而不是边接 MCP 边修 Tool Use 基础问题。

------

# 30. 30 秒面试总结

> 我们在完成 Tool Governance 和 HITL 后发现，用户实际使用 Tool 时仍然需要自己知道 Tool 名称和完整 JSON，相当于用户在充当 Tool Router。源码审计发现模型当时只能看到 name 和 description，并通过文本 `CALL:` 协议调用 Tool。我们先增强了 LLM-facing metadata、系统默认参数和 bounded repair；后来确认生产只使用 DeepSeek 后，又升级为 Provider-native Function Calling。现在 DeepSeek 通过 `tools/tool_calls` 负责语义 Tool Selection，但参数仍必须经过 ToolAdapter typed validation，Risk、Idempotency、Approval 和 Execution 都继续由 deterministic Runtime 控制。另外我们增加了 native capability detection，只有真正支持 Tool Calling 的模型才走 native path。最终 Codex Gate PASS，相关回归没有新增失败。

------

# 31. 2 分钟面试总结

> Phase7 完成 HITL 后，我们发现一个真实问题：为了稳定调用高风险 `complex_workflow_simulator`，用户必须自己写 Tool name、execution mode 和完整 JSON。这意味着 Runtime Safety 已经完成，但 Tool Discovery、Selection 和 Argument Construction 还没有真正交给 Agent。
>
> Codex 审计发现 Registry、Governance、Execution Owner 都没问题，真正问题是模型只看到 Tool 的 name 和 description，而且前面还有一个硬编码 intent gate。所以第一步我们没有重构 Tool Framework，只扩展现有 ToolDescriptor 的 LLM-facing metadata，把 Tool 的业务用途、when-to-use 和业务参数语义暴露给 Model，同时隐藏 operation_id、fault injection 等内部字段；operation identity 和 idempotency identity 改由 Runtime 生成。参数 validation 失败允许一次 bounded repair，而且必须在 Governance 前完成。
>
> 第一版为了提高召回率曾经让所有请求都进入 Tool Planner，Codex Review 发现这会让普通聊天多一次 LLM 调用，所以后来改成低成本 prefilter。
>
> 接着我们确认当前生产只使用 DeepSeek。Codex 可行性审计和真实 API probe 证明 DeepSeek 原生支持 tools/tool_calls，而且当前 Thinking 关闭，因此 Native Function Calling 改造只属于 M 级。我们把文本 `CALL:` 协议替换成了 DeepSeek Native Tool Call，但是后面的 ToolAdapter、Governance、HITL 和 Execution 完全保留。
>
> Native 迁移过程中还有两个比较典型的真实 Review Bad Case。第一个是 repair 失败后错误进入 Governance，后来改为 validation failure 直接 fail closed；第二个是 Native 路径一开始默认所有 Engine 都支持 tools，导致 Local Engine TypeError，甚至宽松 stub 静默吞 tools、破坏 denial 时序，所以后来增加了 capability-aware routing，只有 Adapter 明确声明支持 Native Tool Calling 才发送 tools。
>
> 最终架构变成 Model 负责表达调用，ToolAdapter 负责验证，Governance 负责安全，ApprovalController 负责审批，ToolExecutionService 负责执行。DeepSeek 的 tool_call.id 只做 provider continuation correlation，不参与本地 invocation 或 approval identity。Final continuation 失败也只重试 Model continuation，不重新执行 Tool。最终 Codex Gate PASS，全量回归没有新增失败。

------

# 32. 推荐学习文档文件名

```text
docs/interview/stage5_phase8_wp1_tool_selection_native_function_calling.md
```

------

# 33. 最值得背住的五句话

### 1

> **User 不应该充当 Tool Router。**

### 2

> **Model 负责语义，Runtime 负责安全。**

### 3

> **Provider-native Function Calling 只替换 Tool Call 的表达协议，不替代 Runtime Validation 和 Governance。**

### 4

> **Governance 只能接受已经 Validation 成功的 immutable ToolInvocation。**

### 5

> **Model capability 应按能力声明路由，而不是按 Provider 名称硬编码。**