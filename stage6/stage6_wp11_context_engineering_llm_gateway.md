当前是 **GPT-5.6 Sol**。

下面进入 **Stage6-Supplement-WP11 — Context Engineering / LLM Gateway** 的学习 / 面试总结。推荐文件名：

```
docs/interview/stage6_wp11_context_engineering_llm_gateway.md
```

本总结以 WP11 Final Review 为准；最终状态是 `PASS_WITH_REVIEW_FIXES`，`P0=0 / Blocking P1=0 / Accepted P1=0`，可以正式关闭 WP11。

# 1. 名词 / 概念速览

**上下文工程（Context Engineering）**：决定一次模型调用到底放哪些信息、顺序如何、谁必须保留、预算如何分配、超长时如何降级。

**提示词工程（Prompt Engineering）**：主要关注 System Prompt / Instruction 本身“怎么写”。

**上下文预算（Context Budget）**：模型 Context Window 中分配给输入消息的 Token 空间。

**最终 Provider 消息门禁（Final Provider Message Budget Gate）**：真正调用模型前，对最终实际 Wire Messages 再做一次统一预算检查。

**确定性降级（Deterministic Degradation）**：超预算时按固定规则丢弃低优先级上下文，而不是随机截断。

**提示词身份（Prompt Identity）**：用 `prompt_id + prompt_version + prompt_digest` 标识某次调用使用的代码侧 Prompt Policy。

**结构化输出（Structured Output）**：要求模型输出满足明确 JSON / Schema Contract 的结果。

**有界修复（Bounded Repair）**：结构化结果解析失败后，只允许固定次数修复，本项目最多一次。

**能力路由（Capability Routing）**：根据模型是否支持 Tool、Native Function Calling、Structured Output 等能力选择模型。

**协议原子性（Protocol Atomicity）**：Native Tool 的 `assistant(tool_calls)` 和对应 `tool(tool_call_id)` 必须作为完整交换保留，不能只留下其中一半。

------

# 2. 当前 WP 真实实现

WP11 最终做了三组核心能力，没有新造一个 `LLMGatewayService`，而是在现有 `ContextBuilder + AgentRouter + ModelInvocationRouter` 上增强。

第一组是最终 Context Budget。现在每次真正调用 Provider 之前，都要经过统一 Gate：

```text
Context Sources
→ ContextBuilder
→ Security Instruction
→ Message Assembly
→ Model Selection
→ selected model context_window
→ Final Provider Message Budget Gate
→ Provider
```

最终 Gate 会把完整 Wire Message 一起估算，包括 Native Tool 的 `tool_calls`、arguments、call id、`tool_call_id`，而不是只统计 `content`。选中具体模型后，还会按照该模型自己的 `context_window` 再检查一次。

第二组是 Context Selection。History 改成保留最近对话并从最旧完整 Turn 开始丢弃；RAG 按整个 Chunk keep/drop；Memory 按整个 Record keep/drop；Native Tool Exchange 不拆。

第三组是模型调用合同。增加 Prompt Identity、模型能力语义区分和 Structured Output 的“一次修复后失败即 typed fail”。

------

# 3. 架构与调用链

当前主链可以理解为：

```text
User Request
      ↓
AgentRouter
      ↓
History / Memory / RAG / Tool Result
      ↓
ContextBuilder
      ├─ Trust / Role
      ├─ Mandatory / Priority
      ├─ Budget
      └─ Deterministic Selection
      ↓
Final Wire Messages
      ↓
ModelSelectionPolicy
      ↓
ModelRoutingPolicy
      ↓
selected ModelProfile
      ↓
Provider-specific Final Budget Gate
      ↓
ModelInvocationRouter
      ├─ Timeout
      ├─ Retry
      ├─ Fallback
      ├─ Circuit Breaker
      └─ Invocation Evidence
      ↓
Provider
      ↓
Domain Parser
      ↓
Valid
或
一次 Repair
      ↓
Domain Parser
      ↓
Valid / Typed Fail
```

Owner 没有漂移：ContextBuilder 仍拥有 Context selection/budget；ModelInvocationRouter 仍拥有 transport retry/fallback；Planner / Formation / Forget 各自的 Parser 仍然拥有 Schema Validation。

这点很重要：

> **Context Engineering 没有变成第二个 Retrieval、Memory 或 Model Runtime。**

------

# 4. 为什么这样设计

## Prompt Engineering 和 Context Engineering 为什么要分开

Prompt Engineering 回答：

> “System Prompt 应该怎么写？”

Context Engineering 回答：

> “这次模型调用到底应该看什么？”

例如一次 Agent 调用可能同时有：

```text
System
Security Policy
Current User Request
Recent History
Summary
Long-term Memory
RAG
Tool Result
Multi-Agent Result
```

真正困难的是 Context Window 不够时：

> 谁必须留下，谁可以丢？

这就是 Context Engineering。

------

## 为什么还要 Final Provider Budget Gate

因为前面 `ContextBuilder` 算过 Budget，并不代表最终消息一定还是那些内容。

例如后面可能增加：

```text
Security Instruction
assistant.tool_calls
tool result
repair prompt
```

如果只在最开始算一次：

```text
Build 阶段 120k tokens
→ 后面 append 10k
→ 模型实际窗口 128k
→ 请求超限
```

所以最终必须对**真正发送给模型的 Wire Message**检查。

Final Review 还发现 Luna 第一版用的是所有 Profile 中最大的窗口，而不是实际被选中的 Provider Window，这已经修复。

------

## 为什么 System / Security / Current Request 不能被裁掉

这些是一次 Invocation 最核心的语义。

当前规则是：

```text
System Instruction
Canonical Security Instruction
Current User Request

→ mandatory
→ complete
→ 放不下就 typed fail
```

而不是：

```text
为了成功调用模型
→ 把 System Prompt 截掉一半
```

Final Review 已确认这些 Mandatory 内容不能静默 drop/truncate。

------

## 为什么 History 要 recent-first

原来有一个很真实的 Bug：

```text
ORDER BY ASC
LIMIT N
```

结果拿到的是最早 N 条历史，不是最近 N 条。

长对话里反而会出现：

```text
模型看到开场白
却看不到刚刚说过什么
```

现在变成：

```text
query latest N
→ restore chronological order
→ model
```

超预算时，再从最老的完整 Turn 开始删除。

------

## 为什么不能逐条删除 History

假设：

```text
user: 北京天气怎么样？
assistant: 20°C

user: 那上海呢？
assistant: 22°C
```

如果只删掉第一条 user，但保留 assistant：

```text
assistant: 20°C
```

语义就失去来源。

所以使用完整 Conversation Turn / Group 做原子选择。

------

## 为什么 Retrieval Top-K 不等于 Context Budget

Retriever 的职责：

```text
谁相关？
排序是什么？
```

Context Builder 的职责：

```text
这一次模型能装多少？
```

例如：

```text
Retriever → 10 chunks
Context Budget → 只能容纳 4 chunks
```

不应该因此让 ContextBuilder 再做一次 Retrieval Ranking。

所以现在：

```text
Retriever rank
→ ContextBuilder 按 rank whole-chunk keep/drop
```

Retriever Authority 不变。

这句话非常适合面试：

> **Retrieval Budget 决定召回多少候选，Context Budget 决定本次模型调用实际放多少，两者不是同一层。**

------

## 为什么 Tool JSON 不能随便截断

原来的路径可能出现：

```text
Tool Contract
→ valid JSON
→ AgentRouter 截到 1600 chars
→ invalid JSON
```

这相当于上游保证了结构正确，下游又把结构破坏掉。

现在：

```text
JSON / structured result
→ 整体保留

Plain Text
→ 才允许 bounded truncation
```

并且仍受原 Tool Contract 大小限制。

------

# 5. 可选方案与 Trade-off

**方案一：统一把所有来源都 Summary。** 优点是省 Token，但会产生信息损失和额外 Model Call，而且 Summary 自身可能失真；当前没有采用。

**方案二：只截最老 History。** 简单，但无法处理 RAG / Memory / Tool Result 一起爆 Context 的情况；当前采用的是多来源确定性降级。

**方案三：精确 Provider Tokenizer。** 准确，但不同 Provider / Model tokenizer 维护成本高；当前使用 deterministic estimator，所以结果稳定但不是精确 Token Count。

**方案四：新建独立 LLM Gateway Service。** 架构看起来更“高级”，但会产生第二个 Invocation / Retry / Fallback Owner，所以没有做。

**方案五：结构化输出失败无限 Repair。** 成功率可能提高，但容易产生无限循环和成本失控；当前最多 Repair 一次。

------

# 6. 工程构建方法类问答

### Context Window 不够时你怎么处理？

先区分 Mandatory 和 Optional。System、安全指令和当前用户请求必须完整保留；History 保留最近完整 Turn；RAG 和 Memory 按上游已有排序整块降级；Native Tool Exchange 不允许拆分。如果 Mandatory Context 本身放不下，就直接 typed fail。

### 为什么不简单从 Prompt 最后截断？

因为最后可能正好是 Tool Result、最新对话或关键用户请求，而且截断结构化 JSON 和 Tool Protocol 会直接破坏语义。

### ContextBuilder 会不会重新排序 RAG？

不会。Retriever 决定 relevance/ranking，ContextBuilder 只决定本次 Invocation 是否能容纳该 Chunk。

### 为什么还需要 Prompt Version？

模型效果变化时，需要回答：

> “是模型换了，还是 Prompt Policy 变了？”

所以使用：

```text
prompt_id
prompt_version
prompt_digest
```

进行可追溯归因。

### 为什么没有真的做一个 LLM Gateway？

因为现有 ModelInvocationRouter 已经拥有模型调用、Retry、Fallback、Circuit Breaker 等职责，再建一个 Gateway 会制造第二 Authority。

### Structured Output 为什么不由 ModelInvocationRouter 校验？

Router 不了解 Planning / Memory / Forget 的业务 Schema。

因此：

```text
Router
→ transport

Domain Parser
→ schema / semantics
```

两层责任分离。

### Structured Repair 为什么最多一次？

避免无限 Self-repair Loop，也保证失败语义有界和可预测。

------

# 7. 30 秒面试回答

我在 Agent Runtime 里把 Context Engineering 独立成了明确的调用层。System、安全指令和当前用户请求是 mandatory，History 按最近完整 Turn 保留，RAG 和 Memory 保留各自的 Retrieval Ranking，只在 Context 层按完整 Chunk / Record 做预算降级。

真正调用模型前还会按照最终选中模型的 Context Window 对完整 Wire Messages 再做一次 Gate，包括 Native Tool Call 的协议字段。

另外我给 Prompt 增加了版本和 Digest，并把 Structured Output 做成严格 Parser 加最多一次 Repair，第二次仍失败就 typed fail。整个过程复用已有 ModelInvocationRouter，没有再造一套 LLM Gateway。

------

# 8. 2 分钟面试回答

我把 Context Engineering 和 Prompt Engineering 分开处理。Prompt Engineering 解决 Instruction 怎么写，而 Context Engineering 负责一次模型调用到底应该放哪些信息。

Runtime 中会同时存在 System、用户请求、History、Memory、RAG、Tool Result 和 Multi-Agent Result。我给这些来源保留不同的 Trust、Priority 和 Mandatory 属性。System、安全指令和当前请求必须完整保留；History 取最近 N 条并按完整 Turn 从最老开始降级；RAG 和 Memory 不在 Context 层重新做相关性排序，只沿用 Retriever 和 Memory Retrieval 的既有排名，按整个 Chunk 或 Record keep/drop。

另外我发现只在 Context 构建阶段算 Token 不够，因为后面可能追加 Security Instruction 和 Native Tool Result。所以现在每次真正调用 Provider 之前都会再做 Final Budget Gate，而且按照最终选中的 Model Profile 的 Context Window 检查，Native Tool 的 `tool_calls`、arguments 和 `tool_call_id` 也会计入预算。

结构化输出方面，Planner、Memory Formation 和 Forget 都继续由各自严格 Parser 校验。模型第一次输出不符合 Schema 时最多进行一次 bounded repair，然后再次使用同一个 Parser；第二次失败直接 typed fail，Transport Fallback 不能绕过 Schema。

这样 Context、Routing、Retry、Schema 和 Tool Validation 的 Owner 都保持清晰。

------

# 9. 高频追问 + 简答

**Q：为什么不用更大的 Context Window 直接解决？**
Context 越大成本和延迟越高，而且无关信息可能降低模型质量，不能替代 Context Selection。

**Q：为什么不全部做 Summary？**
Summary 本身有信息损失，而且会引入额外模型调用和新的失真面。

**Q：RAG Top-K 和 Context Budget 区别是什么？**
Top-K 是 Retrieval Candidate Selection；Context Budget 是 Invocation-time Selection。

**Q：为什么 History 保留最近的？**
通常最近 Turn 对当前意图依赖最强，同时旧历史已有 Summary 兜底。

**Q：Prompt Digest 包含用户 Prompt 吗？**
不包含。它只描述 code-owned Prompt Policy。

**Q：Fallback 到另一模型后还要重新校验 Schema 吗？**
必须。Fallback 改的是 Provider，不改变业务 Contract。

**Q：模型支持 Tool 是否等于支持 Native Function Calling？**
不等于，这两个 Capability 已明确分开。

**Q：你支持 Provider-native Structured Output 吗？**
当前 Remote Engine 没发送 `response_format/json_schema`，因此没有声称支持；当前是 Plain-text JSON + Strict Domain Parser。

------

# 10. Bad Case / Failure Scenario

### Bad Case：预算按最大 Model Window 算

```text
Profile A: 128k
Profile B: 32k

Context = 50k

先按最大窗口检查：
PASS

最终选 B：
Provider failure
```

Final Review 已修成根据 selected profile 再做 Provider-specific Gate。

### Bad Case：History 取最早 N 条

长会话中模型只看到旧话题，看不到最新上下文。

WP11 已修复。

### Bad Case：拆 Native Tool Protocol

```text
assistant(tool_calls=id-1)
```

被保留，而：

```text
tool(tool_call_id=id-1)
```

被裁掉。

Provider Protocol 就不完整。

当前 Final Gate 只允许整组通过或 typed fail。

### Bad Case：ContextBuilder 二次重排 Memory

Memory Retrieval 已经排好：

```text
A > B > C
```

ContextBuilder 再按 opaque ID：

```text
C > A > B
```

就越权成为第二 Ranking Authority。

Final Review 已修复这个问题。

### Bad Case：Schema 失败就继续换模型

```text
Model A malformed
→ Model B malformed
→ Model C malformed
→ ...
```

这会把业务校验失败误当 Transport Failure。

当前 Schema Invalid 不属于 Router 的 transient failure；只允许一次 domain-level repair。

------

# 11. Truth Boundary

当前真实完成的能力包括：

```text
Final Provider Message Budget Gate

Security Instruction included in budget

Current User Request mandatory

History recent-first

Oldest whole-turn degradation

RAG whole-chunk selection

Memory whole-record selection

Native Tool Protocol atomicity

Structured Tool Result preservation

ContextSelectionRecord

Prompt ID / Version / Digest

Content-free Context Observability

Provider / Model safe identity evidence

Explicit Native Tool Capability

Explicit Provider Structured Output Capability

Strict Domain Parser

One-shot Structured Repair

Second failure = Typed Fail

Fallback cannot bypass Schema

No new LLMGatewayService

WP10 Security Boundary preserved
```



------

# 12. Completion Boundary

最终：

```ini
WP11_REVIEW_STATUS = PASS_WITH_REVIEW_FIXES

FINAL_PROVIDER_MESSAGE_BUDGET_GATE_CONFIRMED = YES
SECURITY_INSTRUCTION_BUDGETED_CONFIRMED = YES
CURRENT_USER_REQUEST_MANDATORY_CONFIRMED = YES

HISTORY_RECENT_FIRST_CONFIRMED = YES
HISTORY_WHOLE_TURN_DEGRADATION_CONFIRMED = YES

NATIVE_TOOL_PROTOCOL_ATOMIC_CONFIRMED = YES
STRUCTURED_TOOL_RESULT_PRESERVED = YES

RAG_WHOLE_CHUNK_SELECTION_CONFIRMED = YES
MEMORY_WHOLE_RECORD_SELECTION_CONFIRMED = YES

PROMPT_IDENTITY_CONFIRMED = YES

MODEL_CAPABILITY_SEMANTICS_CONFIRMED = YES
PROVIDER_STRUCTURED_OUTPUT_OVERCLAIM = NO

STRUCTURED_REPAIR_MAX_ATTEMPTS = 1
STRUCTURED_SECOND_FAILURE_TYPED = YES
FALLBACK_SCHEMA_BYPASS = NO

WP10_SECURITY_BOUNDARY_PRESERVED = YES

NEW_LLM_GATEWAY_SERVICE = NO

P0 = 0
BLOCKING_P1 = 0
ACCEPTED_P1 = 0

ARCHITECTURE_REOPEN_REQUIRED = NO
CAN_CLOSE_WP11 = YES
```



有一个文档层小问题需要记住：Review Conclusion 写“发现 7 个缺陷”，但正文实际上列出 F1～F8 共 **8 项**；这是报告计数不一致，不影响代码 Gate。

------

# 13. Known Limitation / ACCEPTED_P1

当前 Token Count 仍是确定性近似估算，不是 Provider 精确 Tokenizer；Provider Actual Usage 仍没有完整接线。

Provider Tool Schema 本身不属于 Message DTO，因此 WP11 没有给它单独做 Token Budget。

Project Memory 仍然只是读取 Active Records，没有 Query Relevance / Top-K；WP11 明确没有顺手重构它。

此外 `_ConnectedRequest` 的 lifespan isolated failure 被确认是既有 Test Fixture 问题，不是 WP11 改动导致。

这些都不属于 Accepted P1：

```text
ACCEPTED_P1 = 0
```



------

# 14. 面试关键词

唯一建议重点记住这一组：

- 上下文工程（Context Engineering）
- Token Budget
- Context Window
- Mandatory Context
- Deterministic Degradation
- Recent-first History
- Whole-turn Trimming
- RAG Chunk Selection
- Memory Record Selection
- Retrieval Authority
- Protocol Atomicity
- Prompt Identity
- Prompt Version
- Prompt Digest
- Capability Routing
- Structured Output
- Schema Validation
- Bounded Repair
- Typed Failure
- Retry vs Fallback
- Provider-specific Context Gate
- Context Provenance
- Low-cardinality Observability

一句话总结 WP11：

> **Context Engineering 不是简单拼 Prompt，而是在保持 Retrieval、Memory、Tool 和安全 Authority 不变的前提下，决定一次模型调用哪些信息应该进入、哪些必须保留、超预算如何确定性降级，并保证最终真正发送给 Provider 的消息满足当前模型的 Context Contract。**

WP11 学习完成。下一步就是最后一个补强项：**WP12 — Sandbox / Isolated Tool Execution**。