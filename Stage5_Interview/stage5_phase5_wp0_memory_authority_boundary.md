当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase5-WP0 学习 / 面试总结

## Coordinated Memory Authority & Evaluation Boundary Freeze

WP0 本身没有实现 Advanced Memory（高级记忆）功能，它解决的是一个更基础、也更容易在真实工程中出错的问题：

> **在真正开始写 Memory 代码之前，先冻结“谁有权决定 Memory、什么时候可以写 Memory、Memory 如何进入 Context、Evaluation 可以看到什么但不能控制什么”。**

这正是后面 WP1～WP7 不发生架构漂移的基础。以下内容严格基于本次 WP0 handoff 和实际验证结果整理。

------

# 1. 一句话定义

**WP0 通过冻结 Memory Runtime Owner（记忆运行时所有者）、Mutation Authority（修改权威）、Formation Lifecycle（记忆形成生命周期）、Context Assembly Authority（上下文组装权威）和 Evaluation Boundary（评测边界），为后续 Advanced Memory 建立单一且不可分裂的架构责任边界。**

面试时可以更自然地说：

> 我没有一开始就直接做向量库或者 Memory Retrieval，而是先把 Memory 的 Owner 和生命周期冻结下来，避免 Agent、Runtime、Evaluator 各自都能修改长期记忆，形成多写入权威和状态不一致。

------

# 2. 为什么要做 WP0

很多 Demo 级 Agent Memory 的设计非常简单：

```text
Agent
→ 发现重要内容
→ 写数据库
```

或者：

```text
LLM
→ 生成 Memory
→ 直接插入 Vector DB
```

这样做在 Demo 中能跑，但进入多 Agent Runtime 后很容易出现几个严重问题。

## 2.1 谁都可以写 Memory

比如：

- `code_expert` 可以写；
- `knowledge_expert` 可以写；
- orchestrator 也可以写；
- evaluator 为了测试方便还能直接写。

最终形成：

**Split-brain Authority（双权威 / 多权威）**

同一个长期事实可能有多个系统在决定它的最终状态。

------

## 2.2 未完成任务也可能被永久记住

如果 Memory Formation（记忆形成）发生在：

- Model generation 中；
- Step 执行中；
- Final Output 前；

那么后续流程失败时：

```text
Memory 已经写入
↓
Run 最终失败
↓
用户其实从来没有收到这个结果
```

Memory state 与用户真正看到的业务事实就不一致了。

因此 WP0 最重要的一项决定是：

> **Formation 只能从 canonical delivered outcome 开始。**

------

## 2.3 Evaluation 可能污染被测系统

如果 AgentEvalOps 可以：

```text
Ground Truth
→ 直接修改 LocalAgent Memory
→ 再评价 LocalAgent
```

那 Evaluation 实际上已经参与制造结果。

这种分数没有意义。

所以必须明确：

> AgentEvalOps 只评，不写。

------

## 2.4 Memory 很容易绕过 Context 安全边界

最简单的方法是：

```text
memory_text = ...
system_prompt += memory_text
```

但这会绕过：

- token budget；
- provenance；
- trust classification；
- dedup；
- source ordering；
- context truncation。

所以 WP0 冻结：

```text
Memory Retrieval
→ typed Context
→ ContextBuilder
→ Model Context
```

而不是任意字符串拼 Prompt。

------

# 3. 真实架构

## 3.1 当前 canonical Runtime

当前实际生产路径已经验证为：

```text
POST /api/chat
    ↓
create_run_scope
    ↓
PlanResolver
    ↓
RunCoordinator
    ↓
MultiAgentDriver
    ↓
StepResultCommitter
    ↓
OutputGate
    ↓
RunFinalMemoryWriter
    ↓
MemoryManager.append_exchange_atomic
```

这条路径同时服务：

- dynamic single-step plan；
- dynamic multi-step plan。

因此不能因为类名叫 `MultiAgentDriver`，就错误认为单 Agent 请求走的是另一套 Runtime。

------

## 3.2 当前 Memory 能力

现在真实存在的是：

```text
Short-term Context
├─ conversation messages
└─ Rolling Summary
```

以及 final delivered exchange persistence。

当前还不存在：

```text
Long-term Memory
├─ Semantic Memory
├─ Episodic Memory
├─ Conflict Resolution
├─ Supersede
├─ Forget
└─ Memory Retrieval
```

因此：

> WP0 是 Architecture Freeze（架构冻结），不是 Advanced Memory Implementation。

------

# 4. Owner / Contract

这是 WP0 最重要的知识点。

------

## 4.1 Advanced Memory Runtime Owner

正式冻结：

```text
LocalAgent = Advanced Memory Runtime Owner
```

意思不是某一个 class 是 Owner。

而是：

> Advanced Memory 属于 LocalAgent 的业务 Runtime Domain。

LocalAgent 负责：

- formation policy；
- lifecycle；
- persistence；
- retrieval semantics；
- scope interpretation；
- conflict；
- supersede；
- forget；
- provenance。

------

## 4.2 AgentEvalOps Owner

正式冻结：

```text
AgentEvalOps = Memory Evaluation Owner
```

它负责：

- Dataset；
- Ground Truth；
- Scenario；
- evaluator；
- artifact；
- report。

但不能：

```text
AgentEvalOps
→ mutate LocalAgent Memory
```

这是两个不同的 Owner。

------

## 4.3 Agent 的角色

Agent 不是 Memory Owner。

Agent 最多是：

**Candidate Producer（候选生产者）**

例如 Agent 可以输出：

> “用户刚才明确说明该项目数据库已经切换 PostgreSQL，这可能值得长期记忆。”

但是否：

- INSERT；
- UPDATE；
- NO_CHANGE；
- SUPERSEDE；
- FORGET；

必须由统一 Memory Domain 决定。

因此：

```text
Agent
      ↓
Memory Candidate
      ↓
Memory Domain Policy
      ↓
Authoritative Mutation
```

而不是：

```text
Agent
↓
DB
```

------

# 5. 方案取舍

## 5.1 Formation 放 Agent 内部

### 优点

简单。

Agent 自己最了解当前对话。

### 问题

每个 Agent 都可能形成独立写入口：

```text
Agent A → DB
Agent B → DB
Agent C → DB
```

导致：

- lifecycle 不一致；
- conflict policy 不一致；
- provenance 不一致；
- mutation split-brain。

### 结论

拒绝。

Agent 只能产生 candidate。

------

# 5.2 Generation 中途写 Memory

例如：

```text
LLM Stream
→ 检测到事实
→ 写 Memory
→ 后续生成失败
```

### 问题

Memory 已经写入，但用户没有收到成功结果。

它会破坏：

**Delivered-only semantics（仅已交付结果才能形成长期状态）**

### 结论

拒绝。

------

# 5.3 Final Output 生成完成但尚未 Delivery 时写

依然存在：

```text
Final generated
↓
Memory persisted
↓
Output delivery failed
```

所以：

生成完成 ≠ Delivered。

### 结论

拒绝。

------

# 5.4 Post-delivery Formation

最终选择：

```text
OutputGate
↓
DELIVERED
↓
Memory Formation
```

这是目前最合理的 lifecycle boundary。

优点：

- 用户确实收到结果；
- 不污染 retry；
- 不污染 failed Run；
- 与现有 final memory writer 边界一致；
- Formation failure 可以与 delivery failure 隔离。

------

# 6. 核心执行链

未来 Advanced Memory 的方向已经被冻结为：

```text
Canonical Coordinated Run
        ↓
OutputGate
        ↓
DELIVERED
        ↓
Memory Candidate Formation
        ↓
Memory Domain
        ↓
Mutation Decision
        ↓
Persistence
```

下一次 Run：

```text
Current Query
      ↓
Memory Retrieval
      ↓
Typed Memory Context
      ↓
ContextBuilder
      ↓
Model Context
      ↓
Agent Response
```

Evaluation：

```text
AgentEvalOps
     ↓
HTTP Execute LocalAgent
     ↓
Read-only Evidence
     ↓
Evaluator
     ↓
Evaluation Artifact
```

三条链之间职责非常明确。

------

# 7. Memory-specific 生命周期

WP0 还没有真正实现生命周期状态，但已经冻结了：

> 生命周期 mutation 必须只有一个最终 Authority。

未来可能出现：

```text
Candidate
    ↓
Memory Domain
    ├─ CREATE
    ├─ UPDATE
    ├─ NO_CHANGE
    ├─ SUPERSEDE
    └─ FORGET
```

关键点是：

这些不能由五套代码分别直接改库。

------

## Candidate 与 Mutation 的区别

这是一个很适合面试追问的点。

### Candidate

表示：

> “也许应该发生某项 Memory 变化。”

例如：

```text
database = PostgreSQL
```

### Mutation

表示：

> “经过 Domain 校验以后，正式修改长期 Memory 状态。”

例如：

```text
SQLite → SUPERSEDED
PostgreSQL → ACTIVE
```

Candidate 可以来自模型。

Mutation authority 必须由代码控制的 Runtime Domain 掌握。

------

# 8. Evaluation 设计

WP0 没有实现 Memory evaluator，但冻结了最终架构。

------

## 8.1 Black-box Execution（黑盒执行）

AgentEvalOps 未来通过：

```text
HTTP
→ LocalAgent
```

调用真正 canonical Runtime。

它不应该调用一条 evaluation-only shortcut。

------

## 8.2 White-box Read-only Evidence（白盒只读证据）

只靠 final answer 不够。

例如最终回答错了：

> “项目还在使用 SQLite。”

可能有五种原因：

1. 新 PostgreSQL Memory 根本没形成；
2. formation 成功，但旧 SQLite 没 supersede；
3. lifecycle 正确，但 retrieval 没找到 PostgreSQL；
4. retrieval 找到了，但 Context 没注入；
5. Context 正确，Model 最终还是回答错。

所以 AgentEvalOps 还需要 read-only evidence：

```text
memory_id
status
scope
formation decision
retrieval top-K
injected memory IDs
latency
```

这样 Evaluation 才具有：

**Failure Attribution（失败归因）**

能力。

------

# 9. 真实指标

WP0 没有执行 Advanced Memory 真实实验。

因此：

```text
REAL_MEMORY_EXPERIMENT = NO
```

不能提供：

- Formation Precision；
- Recall@K；
- Conflict Accuracy；
- Forget Success；
- Retrieval Latency。

本 WP 唯一真实测试结果是：

```text
35 passed in 6.25s
```

覆盖的是现有 canonical Runtime / final memory / context / retrieval contract 的轻量回归。

同时：

```text
git diff --check = PASS
```

没有：

- production code change；
- database change；
- test change；
- AgentEvalOps change。

------

# 10. Bad Case

## Bad Case 1：每个 Agent 自己写长期 Memory

### Trigger

```text
code_expert → memory DB
knowledge_expert → memory DB
router → memory DB
```

### Risk

形成多个 mutation authority。

### Root Cause

Candidate Producer 与 Mutation Authority 混淆。

### Fix

统一：

```text
Agent → Candidate
Memory Domain → Mutation
```

### 面试知识点

Single Writer Authority（单写入权威）。

------

# Bad Case 2：模型生成途中写 Memory

### Trigger

模型已经提取：

```text
database = PostgreSQL
```

立即落库。

之后 Run 失败。

### Risk

Memory 中保存了一个用户实际没有成功完成的业务过程。

### Root Cause

Formation lifecycle 太早。

### Fix

只允许：

```text
OutputGate = DELIVERED
```

之后进入 Formation。

------

# Bad Case 3：AgentEvalOps 为了构造 Scenario 直接改 Memory DB

### Trigger

Evaluator：

```text
INSERT INTO memories ...
```

然后执行 query。

### Risk

测试系统参与制造被测状态。

### Root Cause

Evaluation Owner 与 Runtime Owner 混淆。

### Fix

Stateful Scenario 必须通过真实 Run 形成 Memory。

Evaluator 最多：

read-only inspection。

------

# Bad Case 4：Memory 直接追加到 System Prompt

### Trigger

```text
system_prompt += memory_text
```

### Risk

Memory 可能：

- 绕过 token budget；
- 绕过 ContextBuilder；
- 获得 trusted instruction 权限；
- 绕过 provenance；
- 注入恶意内容。

### Fix

```text
MemoryContextRecord
→ ContextItem
→ ContextBuilder
```

Memory 保持：

**Data Role（数据角色）**

而不是：

**Instruction Role（指令角色）**。

------

# Bad Case 5：用 `run_id` 冒充 conversation identity

### Trigger

为了快速实现 THREAD scope：

```text
conversation_id = run_id
```

### Risk

每次 Run 都产生新 ID。

Memory 无法跨 Run 正确共享。

### Root Cause

为了设计完整而发明不存在的 identity semantics。

### Fix

WP0 明确规定：

```text
run_id != conversation_id
```

没有可信 identity 就标：

```
NOT_CONFIRMED
```

而不是伪造。

------

# 11. Known Limitations

本次接受的限制都是真实且合理的。

## 11.1 `session_id` 不能做 durable scope

当前：

```
session_id
```

存在于 Runtime。

但：

- 未进入 Memory persistence；
- 当前有 compatibility/default 属性。

因此只能用于：

Transient Correlation。

不能声称：

> 已经实现 THREAD Memory。

------

## 11.2 没有 `user_id`

因此当前不能声称：

> 已经实现 user-level persistent memory isolation。

------

## 11.3 没有 `project_id`

因此不能直接实现：

```text
PROJECT
```

Scope。

------

## 11.4 Durable shared scope 未冻结

当前存在的是：

**Run-local sharing**

例如多个 step 在同一个 Run 内通过 Step Result 共享信息。

这不等于：

**Long-term Shared Memory**。

这个区别非常重要。

------

## 11.5 Formation Execution Model 尚未决定

目前只决定：

```text
DELIVERED
↓
Formation
```

还没有决定：

- synchronous；
- async；
- isolated task；
- outbox-like；
- transaction coupling。

这是后续 WP 应解决的问题，不是 WP0 缺陷。

------

# 12. 没有完成什么

面试时一定要主动讲清边界。

WP0 没有完成：

- Semantic Memory；
- Episodic Memory；
- Memory Candidate Extraction；
- Memory Persistence Schema；
- Memory Conflict Resolution；
- Supersede；
- Forget；
- vector retrieval；
- hybrid retrieval；
- Memory Ranking；
- Context Injection production wiring；
- multi-agent shared Memory；
- AGENT_PRIVATE governance；
- Stateful Scenario Runner；
- Memory-specific evaluator；
  -真实 Memory quality metrics。

所以 WP0 是：

> **Architecture Foundation**

而不是：

> Advanced Memory Feature Delivery。

------

# 13. 名词 / 概念速览

### Advanced Memory System（高级记忆系统）

不仅保存历史，还具有形成、更新、冲突、遗忘、检索和作用于后续行为的完整生命周期。

### Runtime Owner（运行时所有者）

对某类生产业务状态具有最终业务责任的组件或 Domain。

### Mutation Authority（修改权威）

拥有最终 create/update/supersede/forget 决策与提交权的一方。

### Candidate Producer（候选生产者）

只能提出“可能需要修改 Memory”的建议，不能直接改变长期事实。

### Formation Lifecycle（记忆形成生命周期）

决定 Memory 在一次 Agent Run 的哪个阶段允许被创建。

### Post-delivery（交付后）

只有 `OutputGate` 确认结果已向用户交付之后，才进入后续阶段。

### Split-brain Authority（双权威）

多个组件都认为自己拥有同一份业务状态的最终修改权。

### Context Assembly（上下文组装）

将 System、History、RAG、Memory 等 ContextItem 按规则构造成最终模型输入。

### Typed Context（类型化上下文）

不是裸字符串，而是携带 source、provenance、trust 等结构信息的 Context 数据。

### Provenance（来源追踪）

记录一条 Memory 来自哪个 Run、Exchange 或其他可信来源。

### Durable Identity（持久身份）

能够跨进程、跨 Run 稳定识别实体的 ID。

### Transient Correlation（瞬时关联）

只用于当前 Runtime 流程关联，不能被当作长期业务身份。

### Evaluation Projection（评测投影）

从生产业务事实派生的只读评测视图，不拥有业务修改权。

### Stateful Evaluation（有状态评测）

一个 Case 由多个有顺序、会改变系统状态的真实 Run 组成。

------

# 14. 工程构建类面试题

下面这些问题非常适合从 WP0 延伸。

------

## Q1：为什么不让每个 Agent 自己维护自己的 Memory？

核心考点：

**Owner / Authority。**

应该回答：

即使不同 Agent 最终可以拥有 Private Memory，访问范围和 mutation authority 仍是两个问题。

如果每个 Agent 可以直接：

```text
insert
update
delete
```

那么 conflict policy、provenance、幂等、forget 和生命周期会分裂。

因此 Agent 只产生 Memory Candidate，统一 Memory Domain 决定最终 mutation。

------

## Q2：Memory Formation 为什么放在 post-delivery？

考察：

Runtime lifecycle。

关键点：

- generation success 不代表 delivery success；
- step success 不代表 run success；
- intermediate result 不一定成为用户看到的结果；
- post-delivery 可以避免 failed / retried Run 污染长期状态。

------

## Q3：为什么 Formation failure 不应该让用户请求失败？

因为：

OutputGate 已经确定：

```text
DELIVERED
```

如果此时 Memory Formation 失败导致重新改变 final result，就会破坏 terminal / delivery semantics。

正确做法是：

> Formation 是 delivery 后的独立业务动作，其 failure 应单独观测和处理。

至于未来是否需要重试，要由后续 WP 决定。

------

## Q4：为什么 Memory 和 Knowledge RAG 不应该直接用同一个 Domain？

因为两者 lifecycle 不同。

Knowledge RAG 更关注：

```text
document
→ chunk
→ index
→ retrieve
```

Memory 更关注：

```text
formation
→ identity
→ update
→ conflict
→ supersede
→ forget
→ scope
```

可以复用 retrieval primitives，但不能复用业务语义。

------

## Q5：为什么不能用 `run_id` 当 conversation ID？

因为：

```
run_id
```

表达一次运行。

Conversation：

通常跨多个 Run。

如果：

```text
conversation_id = run_id
```

那么每次 Run 都是一个新的 conversation。

会直接破坏跨 Run Memory。

------

## Q6：ContextBuilder 为什么应该保持唯一 Context Authority？

因为它负责：

- source；
- trust；
- token budget；
- ordering；
- truncation；
- role binding。

如果 Memory Retrieval 绕过 ContextBuilder 自己拼 Prompt，会出现第二套 Context Policy。

------

## Q7：为什么 Evaluation 需要 White-box Evidence？

因为只评价 final answer 无法定位失败阶段。

比如答案错：

```text
Formation?
Lifecycle?
Retrieval?
Injection?
Generation?
```

需要稳定 evidence 才能做 stage-level diagnosis。

------

## Q8：为什么 Evaluation Projection 不能成为 Business Contract？

这里不是说它完全不能稳定，而是：

> 评测需要的观测字段不能反向定义整个 Runtime Domain。

否则为了测试方便会：

- 暴露过多内部信息；
- 扩大敏感内容 surface；
- 让 evaluator 与内部实现强耦合。

应采用：

Business truth first
→ minimal read-only projection。

------

# 15. 推荐面试答案

## 面试题：你们的 Agent Memory 是怎么设计的？

现在只能回答 WP0 层面，不要提前冒充 WP1～WP5 已完成。

推荐：

> 我们原来只有 Conversation History 和 Rolling Summary，所以做 Advanced Memory 时我没有直接接一个向量数据库，而是先把 Memory 的 Owner 和生命周期冻结下来。
>
> LocalAgent 是唯一的 Memory Runtime Owner，单个 Agent 只能产生 Memory Candidate，不能直接修改 Long-term Memory。这样 create、update、supersede、forget 后续都可以通过统一 Domain 管理，避免多个 Agent 各自写库形成 split-brain。
>
> Formation 的入口放在 canonical Coordinated Runtime 的 `OutputGate = DELIVERED` 之后，因为生成完成不代表最终成功交付。这样失败或中间结果不会进入长期记忆，而且 Formation failure 不能反过来修改已经交付的 final output。
>
> Context 侧则复用现有 typed Context pipeline，Memory Retrieval 未来必须转成 typed Memory Context，再经过 `ContextBuilder` 进入模型，而不是直接拼到 System Prompt。
>
> Evaluation 也做了 Owner 隔离：LocalAgent 负责 Memory 行为，AgentEvalOps 只通过真实 HTTP Run 和 read-only evidence 做 Stateful Evaluation，不能根据 Ground Truth 修改生产 Memory。

这段已经能够体现：

- Runtime 思维；
- Owner；
- lifecycle；
- Context Engineering；
- Evaluation validity。

但如果面试官追问：

> Conflict 具体怎么解决？

当前阶段要诚实说：

> WP0 只完成了 Authority 和 Contract Freeze，具体 lifecycle implementation 在后续 WP 实现。

------

# 16. 简历表述

WP0 **不适合单独作为简历 bullet**。

因为它没有交付用户可见 Feature。

应该等 WP5 完成以后，把 WP0 的架构价值融合进完整 Advanced Memory 描述。

例如未来可以写成：

> 基于 Coordinated Runtime 重构长期 Memory 权威边界，采用 delivered-only Memory Formation、统一 mutation authority 和 typed Context injection，避免多 Agent 独立写入导致的状态分裂，并通过 AgentEvalOps Stateful Evaluation 验证跨 Run Memory 生命周期。

但目前：

**不要把这句话当成已完成 WP5 后的最终简历材料。**

WP0 目前真实完成的只是前半部分架构冻结。

------

# 17. 推荐学习文档文件名

按照当前统一规范：

```text
docs/interview/stage5_phase5_wp0_memory_authority_boundary.md
```

推荐标题：

> **Stage5-Phase5-WP0 — Memory Authority, Runtime Lifecycle and Evaluation Boundary**

------

# 本 WP 最值得真正记住的 5 句话

如果时间有限，WP0 最重要的是把下面五句话背熟：

1. **Agent 可以发现 Memory Candidate，但不能成为 Long-term Memory mutation authority。**
2. **Memory Formation 从 `OutputGate = DELIVERED` 后开始，因为 generation success 不等于 business delivery success。**
3. **Memory 和 Knowledge RAG 可以复用 retrieval primitive，但 lifecycle、conflict、scope 和 forget 必须属于独立 Memory Domain。**
4. **Memory 通过 typed Context → `ContextBuilder` 进入模型，不能随意拼接 System Prompt。**
5. **LocalAgent 负责生产 Memory，AgentEvalOps 负责证明 Memory 是否有效；Evaluator 永远不能为了让 Case 通过反向修改生产 Memory。**

这五点基本就是 WP0 的核心工程价值。

**WP0 学习完成后，下一步就是 Stage5-Phase5-WP1 — Advanced Memory Domain & Persistence Foundation。**