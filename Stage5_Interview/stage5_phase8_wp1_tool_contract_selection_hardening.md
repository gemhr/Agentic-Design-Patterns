# Stage5-Phase8-WP1 — Tool Contract & Selection Hardening 学习 / 面试总结

## 1. 本 WP 解决什么问题

### 1.1 原始真实问题

这是一个：

```text
USER_REPRODUCED_BAD_CASE
```

在 Phase7 HITL 已经完成后，真实 Desktop 测试暴露出一个问题：

用户为了稳定触发高风险 Tool，几乎必须自己写：

```text
调用 complex_workflow_simulator

execution_mode = NON_IDEMPOTENT_SIMULATION

operation_id = ...

resource_key = ...

items = [...]

processing_options = ...
```

也就是说系统虽然已经有：

```text
Tool Registry
Governance
HITL
Execution
```

但用户体验仍然接近：

```text
User
→ 自己知道 Tool 名
→ 自己选择 Tool
→ 自己理解底层 enum
→ 自己构造 wire JSON
→ Agent 只是执行
```

这违背了 Agent Tool Use（智能体工具使用）的基本职责划分。

正确目标应该是：

```text
User
自然语言表达业务意图
        ↓
Agent / Model
Tool Selection
Argument Construction
        ↓
Runtime
Validation
Governance
HITL
Execution
```

------

### 1.2 源码审计找到的真正根因

Codex Source Audit 发现，问题**不是 Tool Registry 坏了，也不是 HITL / Governance 不完整**。

真正的问题位于 Runtime Safety 主链之前。

原来的 Model 实际只看到：

```text
ToolDescriptor(
    name,
    description
)
```

Planner Prompt 最终类似：

```text
- tool_name: description
```

模型看不到：

```text
字段含义
required / optional
defaults
业务示例
什么时候该用
什么时候不该用
```

而 Tool 调用协议又只是：

```text
CALL: tool_name(argument_text)
```

因此模型必须自己猜完整 JSON。

同时 `_tool_intent_likely()` 还通过关键词决定：

```text
要不要进入 Tool Planner
```

如果自然语言没有命中关键词，甚至连 Tool Selection 都不会发生。

------

## 2. 真实架构 / 数据流 / 状态流

WP1 完成后的核心链路是：

```text
User Natural Language
        ↓
AgentRouter
Tool Intent Prefilter
        ↓
Tool Planner
        ↓
LLM-facing Tool Metadata
        ↓
Tool Selection
        ↓
Argument Construction
        ↓
ToolAdapter.build_invocation()
        ↓
Typed Validation
        ↓
[失败时最多一次 Repair]
        ↓
Final Valid ToolInvocation
        ↓
adapter.spec_for()
        ↓
ToolGovernanceService
        ↓
ALLOW / DENY / APPROVAL_REQUIRED
        ↓
Phase7 HITL / ToolExecutionService
```

其中非常重要的是 Owner（所有权）没有发生迁移。

| Responsibility                     | Owner                                   |
| ---------------------------------- | --------------------------------------- |
| Tool Registry                      | `ToolRegistry`                          |
| Candidate exposure / orchestration | `AgentRouter`                           |
| Semantic Tool Selection            | Planner Model                           |
| Argument Construction              | Planner Model + system/default handling |
| Argument Validation                | `ToolAdapter` / Typed DTO               |
| Side-effect / Idempotency facts    | `adapter.spec_for()`                    |
| Governance                         | `ToolGovernanceService`                 |
| Approval                           | `ToolApprovalController`                |
| Execution                          | `ToolExecutionService`                  |
| State                              | `AgentStateMachine` / Runtime           |
| Journal                            | Runtime journal-first path              |

一句话记忆：

> **Model 负责“想调用什么、业务参数是什么”，Runtime 负责“能不能调用、风险是什么、是否需要审批、最终怎么执行”。**

------

## 3. 核心设计选择

### 3.1 为什么扩展现有 `ToolDescriptor`，而不是新建 Tool Framework V2？

候选方案：

```text
A. ToolRegistryV2 / ToolDefinitionV2

B. 独立 LLM Tool Catalog

C. 扩展现有 ToolDescriptor

D. 接 OpenAI / LangChain / AutoGen Tool Framework
```

最终选择：

```text
C. 扩展现有 ToolDescriptor
```

原因：

现有：

```text
ToolRegistry
ToolRegistration
ToolAdapter
ToolExecutionService
Governance
```

架构本身是正确的。

缺的只是：

```text
LLM-facing presentation
```

所以应该增强现有：

```text
ToolDescriptor
```

而不是复制整套 Tool 系统。

### 面试表达

> 我们没有因为模型看不懂 Tool 就重写 Runtime，而是在现有 Registry 上增加 LLM-facing metadata，这样可以保持 Tool 的单一事实来源，并避免产生 ToolRegistryV2 这种平行架构。

------

### 3.2 为什么 LLM Metadata 和 Governance Metadata 必须分开？

LLM-facing Metadata（面向模型元数据）负责：

```text
Tool 是做什么的
什么时候使用
业务参数怎么表达
有什么默认行为
```

Governance Metadata（治理元数据）负责：

```text
risk
side effect
idempotency
authorization
approval
```

如果把两者混在一起，Model 可能生成：

```text
risk = LOW
approved = true
approval_required = false
```

然后 Runtime 错误相信模型。

WP1 保持：

```text
Model
选择 execution_mode
        ↓
Adapter
根据 invocation 派生 side effect / idempotency
        ↓
Governance
计算真实 risk / approval
```

所以：

> **Model 可以描述意图，但不能声明安全事实。**

------

### 3.3 为什么没有直接做 Native Function Calling？

候选：

```text
A. Prompt-based Tool Calling
B. Provider-native Function Calling
```

当前 LocalAgent 的 Model Adapter Contract 基本是：

```text
messages
max_tokens
```

没有统一：

```text
tools=[]
function definitions
tool call delta
provider-native schema
```

如果 WP1 强行做 Native Function Calling，会立即扩大到：

```text
ModelAdapter redesign
DeepSeek / Qwen / OpenAI provider compatibility
streaming tool-call parsing
Tool call normalization
```

这已经超出 Phase8 的目标。

因此当前明确接受：

```text
ACCEPTED_P1
Prompt-based Structured Tool Calling
```

但要求它在真实 E2E 中足够稳定。

------

### 3.4 为什么 Validation Repair 只能有限次数？

现在流程：

```text
Model Arguments
↓
Typed Validation
↓
失败
↓
Repair once
↓
重新 Validation
↓
成功 / 确定失败
```

不能无限 Retry，因为无限修复会造成：

```text
成本不可控
延迟不可控
行为不确定
可能反复修改业务语义
```

所以本项目采用：

> **Bounded Repair（有界修复）**

本 WP 实际限制为最多一次 repair。

而且必须发生在 Governance 之前。

------

### 3.5 为什么 `operation_id` 不让 User 填？

因为它属于：

```text
technical identity
```

而不是业务意图。

用户真正要表达的是：

```text
对哪个 resource
对哪个 item
执行什么 action
quantity 是多少
是否要真实修改
```

所以：

```text
operation_id
→ System Generated
```

同理，在 `IDEMPOTENT_COMMIT` 模式下：

```text
idempotency_key
→ System Generated
```

但这里有一个重要完成边界：

当前 idempotency key 只保证：

```text
一个最终 ToolInvocation
+
该 invocation 的 Runtime retry
```

使用相同 key。

它**不保证**：

```text
跨重新规划
跨重新提交
跨 Run
跨进程重启
```

的逻辑去重。

这是当前明确的：

```text
ACCEPTED_LIMITATION
```

------

## 4. 真实性与完成边界

### 已真实实现

```text
ToolDescriptor LLM-facing metadata
业务型 Tool instructions
Tool intent prefilter 改进
natural-language Tool Selection
system-generated operation_id
system-generated idempotency_key
bounded validation repair
test-only fields 从普通 planner surface 隐藏
```

### 已真实测试

Codex Final Review：

```text
181 passed
0 failed
0 skipped
```

并通过：

```text
compileall
git diff --check
```

测试已经证明：

```text
自然语言
→ simulator
→ valid typed invocation
→ HIGH
→ APPROVAL_REQUIRED
```

同时：

```text
普通问答
→ NO_TOOL / 不执行 Tool
```

### 尚未完成

```text
真实远程 LLM E2E
Desktop HITL 自然语言完整 E2E
Restricted Demo Workspace
Workspace read/write Tool
MCP
Native Function Calling
```

其中前两项将在 WP2 验证。

------

## 5. Real Bad Cases

### Bad Case 1 — User 被迫充当 Tool Router

**真实性**

```text
USER_REPRODUCED_BAD_CASE
```

**Trigger**

用户希望执行一次有副作用的模拟业务操作。

**Symptom**

必须自己写：

```text
complex_workflow_simulator
NON_IDEMPOTENT_SIMULATION
完整 JSON
```

才能稳定调用。

**Risk**

Agent 系统退化为：

```text
User routes Tool
Agent executes Tool
```

Tool Selection 根本没有真实价值。

**Root Cause**

Model 只获得：

```text
name + description
```

没有足够参数语义和 Tool 使用指导。

**Fix**

新增 LLM-facing metadata，隐藏技术字段，由 Agent 构造业务参数，System 生成 identity。

**Regression**

自然语言 simulator 测试：

```text
Tool selected = complex_workflow_simulator
Typed validation = PASS
Governance = HIGH / APPROVAL_REQUIRED
```

**Knowledge Point**

```text
Tool Usability
LLM-facing Contract
Separation of Intent and Runtime Contract
```

------

### Bad Case 2 — Keyword Gate 阻止自然语言 Tool Use

**真实性**

```text
SOURCE_AUDIT_DISCOVERY
```

**Trigger**

用户表达 Tool 业务意图，但文字没有命中 `_tool_intent_likely()` 的关键词。

**Symptom**

```text
User
↓
keyword miss
↓
Tool Planner 根本不执行
```

**Risk**

即使 Tool Metadata 再好，Model 都看不到 Tool。

**Root Cause**

Tool Discovery 被硬编码 keyword gate 控制。

**Fix**

放宽成更广义的业务动作预筛选。

**Regression**

自然语言 simulator / status Tool 能进入 planner。

**Knowledge Point**

> Tool Discovery 的入口过滤不能比 Tool Selection 本身更脆弱。

------

### Bad Case 3 — ZCode 初版让所有消息都调用 Planner

**真实性**

```text
CODEX_REVIEW_DISCOVERY
```

这是本 WP 很适合面试讲的真实工程 Review Bad Case。

**Trigger**

ZCode 为了解决 keyword miss，将：

```text
_tool_intent_likely()
```

修改为：

```text
所有非空 request
→ true
```

**Symptom**

于是：

```text
你好
什么是幂等性
解释 decorator
```

都会先额外调用一次 Tool Planner。

而这个 planner 目前直接：

```text
self.llm.generate
```

**Risk**

造成：

```text
额外延迟
额外 Token
额外模型成本
double model invocation
budget / observability 路径放大
```

**Root Cause**

修复 false negative 时走到了另一个极端：

```text
没有 Tool Intent Gate
```

**Fix**

Codex Fix-forward：

```text
广义业务动作预筛选
+
planner 仍保留 NO_TOOL
```

**Regression**

普通概念问答不再触发 planner；自然语言 Tool Intent 仍能进入 planner。

**Knowledge Point**

```text
Precision / Recall Trade-off
Cost-aware Routing
Cheap Prefilter + Expensive Semantic Selection
```

这是一个很好的面试故事：

> 我们先解决召回率不足，但 Review 时发现把 recall 拉满会导致每个请求增加一次模型调用，于是最终采用便宜的 deterministic prefilter 控制成本，真正的语义选择仍交给模型。

------

## 6. 名词 / 概念速览

| Term                                              | 一句话理解                                                   |
| ------------------------------------------------- | ------------------------------------------------------------ |
| Tool Discovery（工具发现）                        | 从当前可用工具中确定哪些 Tool 有可能处理这个请求。           |
| Tool Selection（工具选择）                        | 从候选 Tool 中根据用户语义选择真正要调用的 Tool。            |
| Argument Construction（参数构造）                 | 将用户自然语言转换成 Tool 所要求的结构化业务参数。           |
| LLM-facing Metadata（面向模型元数据）             | 用来帮助模型理解 Tool 用途和输入方式的信息。                 |
| Governance Metadata（治理元数据）                 | Runtime 用于风险、授权、审批等安全判断的权威信息。           |
| Tool Registry（工具注册表）                       | 保存可用 Tool 定义及 Adapter 绑定的 canonical catalog。      |
| ToolAdapter（工具适配器）                         | 将模型构造的参数转换为 Runtime 可验证、可执行的 ToolInvocation。 |
| ToolInvocation（工具调用对象）                    | 一次已经完成结构化和验证的 Tool 调用实例。                   |
| Bounded Repair（有界修复）                        | 参数验证失败后只允许有限次数重新构造，避免无限重试。         |
| Idempotency（幂等性）                             | 同一个逻辑操作重复执行时不会重复产生额外副作用。             |
| Idempotency Key（幂等键）                         | Runtime 用于识别同一个幂等操作的 identity。                  |
| Prefilter（预筛选）                               | 在昂贵的 Model Tool Selection 前，用低成本规则判断是否值得进入 planner。 |
| Prompt-based Tool Calling（基于提示词的工具调用） | 模型通过文本协议产生 Tool call，而不是 Provider 原生 function calling。 |
| Native Function Calling（原生函数调用）           | 模型 Provider 原生支持 Tool Schema 和结构化 Tool Call。      |

------

## 7. 工程构建方法类问答

### Q1：为什么 Tool Metadata 不能只写一个 description？

因为 description 往往只能说明“Tool 是什么”，无法稳定告诉模型：

```text
什么时候调用
什么时候不调用
字段是什么意思
哪些字段可默认
```

模型自然语言到 Tool 参数的映射会非常脆弱。

------

### Q2：为什么不直接把完整 JSON Schema 全塞给模型？

因为完整 Runtime Schema 里可能包含：

```text
内部 identity
failure injection
timeout
metadata
治理相关技术字段
```

模型真正需要的是 **LLM-facing business contract**，而不是整个 Runtime wire contract。

------

### Q3：Tool Selection 为什么可以交给 LLM，但 Governance 不行？

Tool Selection 是语义问题：

```text
用户想做什么？
哪个 Tool 最合适？
```

LLM 擅长。

Governance 是安全和确定性规则：

```text
能不能做？
风险是多少？
要不要审批？
```

必须 deterministic。

------

### Q4：为什么 Tool Selection 不放在 Planner 主计划里直接决定？

当前 Planner 只负责较粗的：

```text
requires_tools
```

而实际 Tool 选择依赖当次 Tool catalog 和业务语义。

因此当前保持专门 Tool Planner 更符合现有架构，也避免扩大 Planner Contract。

------

### Q5：为什么要保留 `_tool_intent_likely()`？

主要为了：

```text
Cost
Latency
```

因为当前 Tool Planner 本身也是一次 LLM 调用。

如果所有普通消息都进入 Tool Planner，会产生双模型调用。

所以采用：

```text
cheap prefilter
→ expensive semantic selection
```

------

### Q6：为什么 prefilter 不能决定具体 Tool？

因为 deterministic keyword 很难准确理解业务语义。

Prefilter 只回答：

```text
“这个请求像不像需要 Tool？”
```

具体：

```text
“应该用哪个 Tool？”
```

仍由 Model 决定。

------

### Q7：为什么参数 Repair 必须在 Governance 前？

因为 Governance 必须根据**最终真实执行的参数**判断：

```text
side effect
idempotency
risk
```

如果 Governance 后再修改参数：

```text
审批的是 A
执行的是 B
```

会破坏安全 Contract。

------

### Q8：为什么 Repair 不能无限重试？

无限 retry 会导致：

```text
成本不可预测
延迟不可预测
语义漂移
模型循环
```

所以用 bounded repair。

------

### Q9：为什么 `operation_id` 由系统生成？

它是运行时技术 identity，不属于用户业务语义。

让 User 填只会增加认知负担和错误率。

------

### Q10：为什么这次没有顺手把 MCP 也做了？

因为 Phase8 首先验证：

```text
Local Tool
自然语言 → Tool → arguments
```

如果这一层有问题，接入 MCP 只会把问题复制过去。

先把 Local Tool Use 做正确，再让 MCP 作为新 Provider 接入。

------

## 8. 高频面试追问 + 简单回答

### 1. 你们 Tool Selection 是谁负责的？

**答：**

语义选择由 Tool Planner Model 负责；`AgentRouter` 负责 candidate exposure、prefilter 和调用协调，Runtime 不参与语义选择。

------

### 2. 你们 Tool Registry 里放了什么？

**答：**

Registry 保存 Tool identity、description / LLM-facing presentation 和对应 Adapter 绑定；Governance Policy 是独立权威来源。

------

### 3. 为什么 Governance Metadata 不直接放进 Prompt？

**答：**

可以给模型解释性提示，但 risk、approval、authorization 不能由模型控制，否则模型可能通过生成低风险字段绕过安全机制。

------

### 4. 用户不提供 operation_id，怎么生成？

**答：**

在 Adapter 构造最终 invocation 时系统生成，用户只负责业务参数。

------

### 5. idempotency key 每次都是随机的吗？

**答：**

独立 invocation 会生成不同 key；同一个最终 invocation 在 Runtime retry 中复用同一个 key。目前不保证跨 Run 或重新规划后的逻辑去重。

------

### 6. 为什么 idempotency key 不做跨进程？

**答：**

那需要更强的持久化 idempotency contract，已经超出本阶段目标；当前合同只保证 invocation 内 retry。

------

### 7. 参数错了怎么办？

**答：**

先走 typed validation；失败后允许一次 bounded repair，再重新 validation，失败就确定性停止，不进入执行。

------

### 8. 为什么最多只修一次？

**答：**

防止无限模型调用、延迟失控和参数语义不断漂移。

------

### 9. Repair 后为什么要重新跑 Governance？

**答：**

因为 risk 必须基于最终真实参数计算，不能审批旧参数后执行新参数。

------

### 10. 普通聊天会不会也调用 Tool Planner？

**答：**

不会全部调用。我们有一个低成本 intent prefilter，只把疑似业务动作送到 planner，planner 本身仍可以返回 `NO_TOOL`。

------

### 11. 为什么不直接把所有请求都给 planner？

**答：**

因为当前 planner 本身是一轮额外 LLM 调用，会增加延迟、Token 和成本。

------

### 12. prefilter 会不会漏召回？

**答：**

会有少量可能，这是当前 P2 limitation。所以它只做广义过滤，不能承担最终 Tool Selection。

------

### 13. 当前 Tool Calling 是 Function Calling 吗？

**答：**

不是，目前还是 prompt-based structured `CALL` protocol；provider-native Function Calling 是后续演进方向。

------

### 14. 为什么不用原生 Function Calling？

**答：**

当前 Model Adapter 没有统一 tools schema contract，强做会牵涉多 Provider、streaming 和 ModelInvocationRouter 重构，不符合当前快速闭环目标。

------

### 15. Prompt Tool Calling 靠谱吗？

**答：**

可靠性低于 native function calling，所以我们增加了明确 Tool metadata、typed validation 和 bounded repair，并通过 deterministic integration tests 做保护。

------

### 16. 模型能不能自己说“这个操作已经批准了”？

**答：**

不能。模型文本没有审批 authority，最终必须经过 `ToolGovernanceService` 和 `ToolApprovalController`。

------

### 17. execution_mode 是模型选择的，那模型岂不是能控制风险？

**答：**

模型只是表达执行意图；Runtime 会根据最终 typed invocation 通过 `spec_for()` 派生 side-effect/idempotency，再由 Governance 决定真实风险。

------

### 18. 怎么防止模型把 HIGH 风险说成 LOW？

**答：**

Runtime 根本不读取模型生成的 risk 值，risk authority 不在 LLM-facing contract 里。

------

### 19. 为什么要隐藏 failure injection？

**答：**

它是 deterministic test 能力，不是普通用户业务字段，暴露给模型只会增加 Schema 复杂度和误调用风险。

------

### 20. Tool 数量只有几个，为什么还叫 Tool Discovery？

**答：**

这里的 Discovery 主要是候选可达性和模型可见性，不是向量检索。当前工具规模很小，不需要 Tool RAG。

------

### 21. Tool 多到几百个怎么办？

**答：**

那时才值得考虑 capability filtering、Tool Retrieval 或 embedding search；当前阶段没有这个真实需求。

------

### 22. Tool Selection 和 Agent Router 有什么区别？

**答：**

Agent Router 决定哪个 Agent 承担任务；Tool Selection 决定该 Agent 具体调用哪个 Tool，两者粒度不同。

------

### 23. 你们最大的真实 Bug 是什么？

**答：**

一个是用户被迫自己点名 Tool 和写完整 JSON；另一个是初版修复后所有非空请求都触发 Tool Planner，导致普通聊天额外产生一次模型调用，后来在 Codex Review 中修掉。

------

### 24. 这个 WP 最大的 Trade-off 是什么？

**答：**

在 Tool 召回率和模型调用成本之间取平衡：不能用过窄 keyword gate，也不能所有请求都调用 Tool Planner。

------

### 25. 如果现在让你继续优化，你最先做什么？

**答：**

先做 WP2 的真实远程模型和 Desktop HITL E2E，证明自然语言 Tool Use 在真实链路稳定，再进入 MCP，而不是继续抽象 Tool Framework。

------

## 9. 30 秒面试总结

> 我们在完成 Tool Governance 和 HITL 后发现，用户实际调用高风险 Tool 时仍然需要自己知道 Tool 名称、execution mode 和完整 JSON，相当于用户在充当 Tool Router。源码审计发现模型实际只看到 Tool 的 name 和 description，而且前面还有一个脆弱的 keyword gate。我们没有重构 Runtime，而是在现有 ToolDescriptor 上增加 LLM-facing metadata，让模型理解 Tool 的业务用途和参数，同时把 operation_id 等技术字段改为系统生成，并增加一次 bounded validation repair。安全上仍保持 Adapter → spec_for → Governance → HITL 的 deterministic 主链。最终 181 个相关测试通过，Codex Gate PASS。

------

## 10. 2 分钟面试总结

> Phase7 完成后，我们已经有比较完整的 Tool Governance、HITL、CAS execution claim 和 ToolExecutionService，但真实 Desktop Demo 暴露了另一个问题：用户为了稳定调用 `complex_workflow_simulator`，必须明确写 Tool 名称、`NON_IDEMPOTENT_SIMULATION` 和完整 JSON。这说明 Runtime Safety 做好了，但 Tool Discovery、Selection 和 Argument Construction 实际还没有真正交给 Agent。
>
> 我们先做源码审计，发现 Registry 本身没有问题，真正问题是模型最终只看到 `ToolDescriptor(name, description)`，没有字段语义、默认值和使用场景；同时 `_tool_intent_likely()` 还会通过硬编码关键词决定是否进入 planner。
>
> 所以 WP1 没有做 ToolRegistryV2，也没有引入 LangChain 或 Native Function Calling，而是在现有 ToolDescriptor 上增加 LLM-facing metadata，把业务用途、when-to-use、参数语义给模型，同时继续把 risk、side effect、idempotency 和 approval 留在 Runtime Governance。
>
> 参数方面，用户只需要表达 resource、item、action、quantity 和是否真实执行，`operation_id`、idempotency key 由系统生成，processing options 使用默认值，failure injection 等测试字段不暴露给普通模型。参数 validation 失败时允许最多一次 repair，并且一定发生在 Governance 前。
>
> 实施中还有一个真实 Review Bad Case：最初为了避免 keyword gate 漏召回，把所有非空请求都送进 Tool Planner，结果普通聊天也会增加一次 `llm.generate`，带来延迟和成本放大。Codex Review 后改成了低成本业务动作 prefilter，再由 Model 做真正语义 Tool Selection。
>
> 最终相关测试 181 passed，Governance、HITL 和 Execution Owner 都没有改变。当前仍是 prompt-based Tool Calling，没有做 provider-native Function Calling，这是明确接受的限制，下一步会通过真实远程模型和 HITL E2E 验证，再进入 MCP。

------

## 11. 推荐学习文档文件名

```text
docs/interview/stage5_phase8_wp1_tool_contract_selection_hardening.md
```