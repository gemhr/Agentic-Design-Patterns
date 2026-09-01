当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase5-WP1 学习 / 面试总结

## Advanced Memory Domain & Persistence Foundation

WP1 解决的不是“让 Agent 开始记忆”，而是先建立一个真正可以承载长期记忆的 **Domain Model（领域模型）+ Persistence Foundation（持久化基础）**。

一句话概括：

> **把原本的 Conversation History（对话历史）与真正的 Long-term Memory（长期记忆）彻底分域，并建立稳定 identity、lifecycle-capable status、provenance、SQLite Source of Truth、原子写入和显式 migration，为后面的 Formation、Conflict、Forget、Retrieval 提供可靠基础。**

WP1 最终已经通过 Final Gate：`PASS_WITH_ACCEPTED_LIMITATIONS`，`OPEN_P0=0`、`OPEN_P1=0`、`REMEDIATED_P1=1`，并允许进入 WP2。

------

# 1. 一句话定义

**WP1 为 Advanced Memory 建立了独立于 Conversation History 的长期记忆领域与 SQLite 持久化合同，使每条 Memory 都拥有稳定 identity、明确 type/status、provenance 和可演进 lifecycle foundation。**

面试里可以压缩成：

> 我先把长期 Memory 从聊天记录里拆成独立 Domain，而不是直接给 messages 表加几个字段；然后建立稳定 memory_id、状态生命周期、provenance、原子持久化和 schema migration，为后面的 Formation、Conflict 和 Retrieval 做基础。

------

# 2. 为什么要做

如果跳过 WP1，直接开始做：

```text
LLM
→ 提取一个事实
→ INSERT 数据库
```

很快会碰到四类问题。

## 2.1 Conversation History 和 Memory 被混为一谈

History 表示：

> “发生过什么对话。”

Memory 表示：

> “经过 Memory Policy 接受后，哪些信息应该长期影响未来行为。”

两者生命周期完全不同。

History 通常是：

```text
user message
assistant message
summary
```

而 Long-term Memory 后面需要：

```text
ACTIVE
SUPERSEDED
FORGOTTEN
```

以及：

- logical fact identity；
- conflict；
- provenance；
- retrieval suppression。

所以 WP1 正式冻结并实现：

```text
Conversation History != Long-term Memory
```

现有 `messages`、`message_exchanges`、`conversation_summaries`、`messages_fts` 不承担 Advanced Memory 语义。

------

## 2.2 没有稳定 identity，就无法做生命周期

比如：

```text
database = SQLite
```

后来变成：

```text
database = PostgreSQL
```

如果 Memory identity 就是：

```text
hash(content)
```

那么内容一变 identity 也变。

这会导致旧 Memory 很难被稳定引用。

因此 WP1 规定：

> `memory_id` 与 content 解耦，是 opaque、stable、immutable identity。

这样未来才可以：

```text
memory_A.status = SUPERSEDED
memory_A.superseded_by = memory_B
```

而不会因为正文变化导致“这个 Memory 到底是谁”都不确定。

------

## 2.3 如果 Vector Index 是 Source of Truth，Forget 会很难做

如果：

```text
Vector DB
= Memory Source of Truth
```

那么以后：

```text
SUPERSEDED
FORGOTTEN
```

的语义就容易与 index 中残留向量脱节。

WP1 因此冻结：

```text
SQLite canonical Memory record
= Source of Truth

Vector / lexical index
= Derived Projection
```

以后即便 Index 有 stale entry，也必须由 canonical status 兜底过滤。

------

## 2.4 Schema 不提前考虑 lifecycle，后面一定返工

如果 WP1 只设计：

```text
id
text
embedding
```

到了 WP3 才发现需要：

- status；
- provenance；
- superseded relation；
- forget tombstone；

就得再次做 destructive migration。

所以 WP1 选择：

> 现在冻结 lifecycle-capable persistence，暂时不实现 lifecycle behavior。

这就是：

**Capability Foundation（能力基础）** 和 **Behavior Implementation（行为实现）** 的区别。

------

# 3. 真实架构

WP1 实现后的关系可以理解为：

```text
SQLite Memory DB
│
├─ Conversation Domain
│  ├─ messages
│  ├─ message_exchanges
│  ├─ conversation_summaries
│  └─ messages_fts
│
└─ Advanced Memory Domain
   └─ long_term_memory
```

物理上：

> 同一个 SQLite file。

业务上：

> 两个独立 Domain。

这是很重要的区分：

```text
Shared Storage
!=
Shared Domain
```



------

## Advanced Memory Domain

核心实现位于：

```
core/advanced_memory.py
```

主要包含：

- `MemoryType`
- `MemoryStatus`
- `MemoryOrigin`
- `SemanticMemoryRecord`
- `MemoryDomainError`
- `AdvancedMemoryStore`

WP1 v1 的 type 只允许：

```text
SEMANTIC
```

没有提前加入：

```text
EPISODIC
PROCEDURAL
```

避免“enum 里存在 = 功能已经支持”的伪能力。

------

# 4. Owner / Contract

## 4.1 Domain Owner

继续继承 WP0：

```text
LocalAgent
= Advanced Memory Runtime Owner
```

WP1 没有引入第二个 Memory Owner。

------

## 4.2 Schema Owner

```
core/memory_manager.py
```

仍然拥有：

- schema version；
- physical signature；
- initialization；
- preflight；
- migration。

而：

```
AdvancedMemoryStore
```

只负责：

```text
create
get
list
```

它**没有**自行：

- CREATE TABLE；
- ALTER TABLE；
- 修改 `PRAGMA user_version`。

这防止出现：

**Schema Authority Split-brain（Schema 双权威）**。

------

## 4.3 Persistence API Boundary

方向是：

```text
Memory Domain
→ narrow persistence boundary
→ SQLite
```

而不是：

```text
Agent
→ sqlite3
```

同时又没有过度引入：

- Generic Repository；
- Repository Factory；
- ORM Framework；
- Unit of Work Framework。

这是一个很好的工程取舍：

> 有 Boundary，但不 Framework 化。

------

# 5. 方案取舍

## 5.1 `memory_id`：内容 hash vs stable opaque ID

### 内容 hash

优点：

- 自动 dedup；
- 实现简单。

问题：

一旦事实内容变：

```text
SQLite
→ PostgreSQL
```

ID 也跟着变。

它不能稳定表达：

> “这是旧 Memory 的新版本。”

因此拒绝。

------

## 5.2 `logical_key` 是否代替 memory_id

例如：

```text
project_database
```

看起来似乎可以当 identity。

但问题是：

同一个 logical fact 可能存在多个版本：

```text
Memory A
logical_key=project_database
SQLite

Memory B
logical_key=project_database
PostgreSQL
```

因此：

```text
memory_id
= record identity

logical_key
= optional logical fact slot
```

两者职责不同。

------

## 5.3 是否所有 Semantic Memory 都强制 logical_key

拒绝。

因为自然语言长期事实不一定都能可靠结构化。

WP1 最终采用：

```text
optional logical_key
```

只在可以确定结构化事实槽时使用。

------

## 5.4 Profile 单独建系统吗

没有。

例如：

```text
profile.preferred_language
profile.response_style
```

仍然作为普通 atomic Semantic Memory。

优点：

- 一套 persistence；
- 一套 lifecycle；
- 一套 retrieval；
- 一套 evaluator。

避免 Profile System 和 Memory Collection 双基础设施。

------

# 6. 核心执行链

WP1 当前真正可以执行的是：

```text
SemanticMemoryRecord
        ↓
validation
        ↓
AdvancedMemoryStore.create()
        ↓
SQLite transaction
        ↓
long_term_memory
```

读取：

```text
memory_id
   ↓
get_by_memory_id()
   ↓
SemanticMemoryRecord
```

或者：

```text
agent_id
+ memory_scope
   ↓
list_by_agent()
   ↓
ACTIVE records by default
```

注意：

这里还没有：

```text
User Conversation
→ Candidate
→ SemanticMemoryRecord
```

因为 Formation 是 WP2。

------

# 7. Memory-specific 生命周期

这是 WP1 最重要的设计之一。

目前状态 vocabulary 已实现：

```text
ACTIVE
SUPERSEDED
FORGOTTEN
```



------

## ACTIVE

含义：

> 当前有效的长期事实。

未来默认 Retrieval 应只检索 ACTIVE。

目前已经实现的基础 read：

```text
list_by_agent(active_only=True)
```

默认只返回 ACTIVE。

------

## SUPERSEDED

含义：

> 曾经有效，但已经被更新事实替代。

例如：

```text
A:
database = SQLite
status = SUPERSEDED

B:
database = PostgreSQL
status = ACTIVE
```

WP1：

**只会表示这个状态。**

还不会真正执行：

```text
ACTIVE → SUPERSEDED
```

这是 WP3。

------

## FORGOTTEN

含义：

> 已经进入逻辑遗忘状态，不能再参与默认检索。

但 WP1 还没有：

```text
forget_memory()
```

只预留 persistence contract。

------

# 8. Evaluation 设计

WP1 还没有 AgentEvalOps Bridge，但它已经做了一件很重要的事：

> 让未来 evaluator 不需要依赖 SQLite incidental details。

未来稳定可以引用：

- `memory_id`
- `memory_type`
- `status`
- `agent_id`
- `memory_scope`
- `logical_key`
- origin run
- origin exchange
- provenance
- timestamps
- supersede relation

而不能依赖：

- row number；
- insertion order；
- table internal id；
- SQL column position。

这就是：

**Evaluation-aware Domain Design（面向评测的领域设计）**。

------

# 9. 真实指标 / 测试结果

WP1 没有真实模型实验。

所以：

```text
REAL_EXPERIMENT_EXECUTED = NO
```

不能说已经验证：

- Formation Precision；
- Retrieval Recall；
- Conflict Accuracy；
- Forget Success。

------

## 真实 deterministic tests

Final Gate 后：

### Advanced Memory

```text
46 passed
```

### Focused Regression

```text
435 passed
1 failed
1 deselected
```

唯一失败属于独立确认的 pre-existing failure。

### Full Repository

```text
2738 passed
4 failed
13 deselected
42 subtests passed
```

并且：

```text
PRE_EXISTING_FAILURES_CONFIRMED = YES
```

4 个失败在没有 WP1 Diff 的 baseline 同样存在。

另外：

```text
compileall = PASS
git diff --check = PASS
```

------

# 10. Bad Case

## Bad Case 1：直接把 messages 当 Semantic Memory

### Trigger

给 `messages` 增加：

```text
memory_type
status
embedding
```

然后称其为 Advanced Memory。

### Risk

Conversation 与 Long-term Memory lifecycle 混淆。

### Root Cause

把：

> “聊天发生过”

错误等同于：

> “应该长期记住”。

### Fix

独立 `long_term_memory` Domain。

------

# Bad Case 2：content hash 作为 memory_id

### Trigger

```text
memory_id = sha256(content)
```

### Risk

正文变化导致 identity 变化。

### Root Cause

Content Identity 与 Entity Identity 混淆。

### Fix

opaque stable `memory_id`。

------

# Bad Case 3：logical_key 建 UNIQUE

### Trigger

数据库加：

```text
UNIQUE(agent_id, logical_key)
```

### Risk

会把 Conflict Resolution 塞进 DB constraint。

比如：

```text
SQLite
PostgreSQL
```

第二条事实插入时直接 DB error。

数据库根本不知道：

> 这是冲突、更新，还是暂时并存。

### Fix

`logical_key` 非唯一。

Conflict 交给 WP3 Domain Policy。

------

# Bad Case 4：Vector DB 作为事实源

### Trigger

Embedding 入库后只在 Chroma 中保留 Memory。

### Risk

未来 Forget 时可能：

```text
SQLite says FORGOTTEN
but vector index still returns result
```

或者反过来：

根本没有 canonical status。

### Fix

SQLite 为 lifecycle Source of Truth。

Index 只做 derived projection。

------

# Bad Case 5：constructor 自动 migration

### Trigger

`MemoryManager()` 初始化时发现缺表：

```text
CREATE TABLE
ALTER TABLE
set user_version
```

### Risk

启动一个 Runtime 实例就可能偷偷修改生产数据结构。

不利于：

- rollback；
- deployment；
- version control；
- observability。

### Fix

WP1 正式做到：

```text
preflight
→ migration required
→ explicit migration
```

constructor 对 existing DB 不负责升级。

------

# Bad Case 6：幂等比较漏掉 lifecycle 字段

这是本 WP 真实发现并修复的问题。

原实现把：

```text
same memory_id
```

的幂等 equality 判定做得不完整。

漏掉了：

- `created_at`
- `updated_at`
- `superseded_by_memory_id`

还允许：

```text
ACTIVE
+
superseded_by_memory_id
```

这种不一致 record。

### Risk

同一个 Memory ID 可以携带不同 lifecycle facts，却被误判为“相同请求”。

### Root Cause

把幂等理解成：

> “正文差不多一样”。

实际上 Memory record 的 lifecycle metadata 也是 Business State。

### Fix

完整 canonical equality。

Final Gate 后：

```text
same ID + identical complete record
→ idempotent

same ID + any different business field
→ conflict reject
```

这个 Bad Case 很有面试价值。

------

# 11. Known Limitations

## 11.1 没有 durable user identity

当前只有：

```text
agent_id
memory_scope
```

长期 partition 基础。

不能声称支持：

- user-level memory；
- multi-user isolation。

------

## 11.2 没有 conversation / thread identity

因此：

不能做真正的 THREAD Memory。

------

## 11.3 没有 durable shared scope

当前 Multi-Agent 的 Run 内共享：

不等于：

Long-term Shared Memory。

------

## 11.4 Supersede relation 没有 FK

当前：

```
superseded_by_memory_id
```

可以持久化。

但还没有数据库级保证：

> target 一定存在。

这是 WP3 在真正实现 Supersede mutation 时再解决。

------

## 11.5 Forget policy 没实现

目前只确定：

FORGOTTEN 可以用 tombstone representation。

还没有：

- authorization；
- redaction；
- retention；
- physical purge。

------

## 11.6 Episodic 尚未加入 contract

```
MemoryType
```

只有：

```text
SEMANTIC
```

这是有意的 focused scope。

------

# 12. 没有完成什么

WP1 没有完成：

- Semantic Memory Formation
- Candidate Extraction
- Should Remember
- Conflict Resolution
- Supersede mutation
- Explicit Forget
- Retrieval
- BM25 Memory retrieval
- Embedding
- Vector retrieval
- Ranking
- Context Injection
- Memory token budget
- Episodic Memory
- Multi-Agent private/shared governance
- Stateful AgentEvalOps Evaluation
  -真实跨 Run行为验证

所以当前准确描述是：

> **Advanced Memory Foundation 已完成。**

而不是：

> **Advanced Memory System 已完成。**

------

# 13. 名词 / 概念速览

### Domain Model（领域模型）

用明确的业务实体、状态和约束表达系统中的核心业务概念。

### Persistence Foundation（持久化基础）

为业务实体提供可靠存储、读取、原子性、迁移与版本管理能力。

### Stable Identity（稳定身份）

实体内容变化后仍然保持不变的唯一标识。

### Opaque ID（不透明标识）

调用方只把 ID 当标识使用，不依赖其内部生成方式。

### Logical Key（逻辑键）

表示“这些记录属于同一个业务事实槽”的辅助标识，不等于 record identity。

### Atomic Fact（原子事实）

可以独立被更新、替代、遗忘和检索的最小长期事实。

### Lifecycle Vocabulary（生命周期状态词汇）

系统正式允许表达的状态集合，例如 ACTIVE / SUPERSEDED / FORGOTTEN。

### Tombstone（墓碑记录）

删除或遗忘正文后仍保留最小 identity / status / lifecycle evidence 的记录。

### Source of Truth（事实源）

拥有最终业务事实权威的数据来源。

### Derived Projection（派生投影）

从 Source of Truth 构建、可以重建且不拥有业务权威的数据结构。

### Idempotency（幂等性）

同一个业务操作重复执行不会产生额外副作用。

### Atomicity（原子性）

一个操作要么完整成功，要么完整失败，不留下部分状态。

### Explicit Migration（显式迁移）

由明确迁移流程改变 schema，而不是业务进程初始化时偷偷升级数据库。

### Fail Closed（失败关闭）

当版本或结构不确定时拒绝继续，而不是猜测后自动修改。

------

# 14. 工程构建类面试题

## Q1：为什么 Semantic Memory 不直接放 messages 表？

核心回答：

> Conversation History 表示发生过的对话，而 Semantic Memory 表示经过策略接受、会长期影响未来行为的事实，两者 identity、生命周期、查询和删除语义不同。因此物理上可以共用 SQLite，但业务 Domain 必须分离。

------

## Q2：为什么 memory_id 不能用 content hash？

核心：

> content 是可变化的业务数据，而 identity 应稳定。以后 supersede、audit 和 evaluation 都需要稳定引用旧 Memory，所以 memory_id 必须与正文解耦。

------

## Q3：memory_id 和 logical_key 有什么区别？

推荐答：

> memory_id 唯一标识一条具体 Memory Record；logical_key 表示多个 record 可能属于同一个事实槽，比如 `project_database`。SQLite 和 PostgreSQL 两个版本可以有不同 memory_id，但相同 logical_key。

------

## Q4：为什么 logical_key 不设 UNIQUE？

因为：

> 数据库无法判断新值是冲突、更新还是合法并存。Conflict Resolution 应属于 Domain Policy，而不是 Unique Constraint。

------

## Q5：为什么现在就有 SUPERSEDED/FORGOTTEN 状态，却没实现功能？

这是：

**Schema Forward Compatibility（Schema 前向能力准备）**

但不要这样泛泛回答，最好说：

> 我们提前让 persistence 可以表达未来生命周期，避免 WP3 为核心状态再做破坏性 migration；但生产 mutation API 没有提前暴露，所以能力边界仍然清晰。

------

## Q6：为什么 vector index 不能当 Source of Truth？

因为它擅长：

> retrieval。

不擅长：

> authoritative lifecycle。

尤其：

- supersede；
- forget；
- audit；
- provenance；
- atomic update。

所以 canonical record 在 SQLite。

Vector index 可以重建。

------

## Q7：为什么 constructor 不能自动 migration？

回答重点：

> Schema migration 是运维行为，不应由普通业务对象初始化隐式触发。显式 preflight + migration 可以做到 fail closed、rollback、版本可观测，并防止应用启动时偷偷修改 durable state。

------

## Q8：为什么 WP1 不直接加 Episodic？

因为：

> Episodic 的 payload、provenance 和 retrieval 需求还没真正冻结。提前加 enum 只会制造“contract 支持了但功能没实现”的假象，所以先聚焦真正落地的 SEMANTIC。

------

## Q9：幂等为什么必须比较 lifecycle 字段？

这是一个很好的进阶题。

因为：

```text
same memory_id
```

代表：

> 同一个业务实体。

如果：

```text
status
timestamps
superseded relation
```

不同，却仍被认为“相同”，就会把真实业务状态差异吞掉。

所以 idempotency equality 必须基于完整 canonical business record。

------

# 15. 推荐面试答案

## 面试题：你们长期 Memory 的数据模型是怎么设计的？

推荐回答：

> 我没有直接把 Conversation History 当成 Long-term Memory，而是在同一个 SQLite backend 中建立了独立 Memory Domain。History 记录发生过的消息，Advanced Memory 记录经过长期记忆策略接受的业务事实，两者共用物理数据库但 lifecycle 和 identity 完全独立。
>
> 每条 Memory 有一个稳定 opaque `memory_id`，不能由正文 hash 或 SQLite row id 推导；另外支持 optional `logical_key`，用于表达多个 Memory Record 属于同一个逻辑事实槽，比如 `project_database`，但 logical key 本身不唯一，因为真正的 Conflict Resolution 不能交给数据库 Unique Constraint。
>
> 生命周期层提前支持 ACTIVE、SUPERSEDED 和 FORGOTTEN 三种状态，但 WP1 只允许生产路径创建 ACTIVE，Supersede 和 Forget 的 mutation 留在后续 lifecycle WP。这样 schema 能承载未来行为，又不会提前暴露没有实现的业务能力。
>
> 持久化上 SQLite 是唯一 Source of Truth，未来 vector 或 lexical index 只作为 derived projection，所以即使 index 出现 stale entry，也不能绕过 canonical lifecycle。Schema migration 也是显式 v1→v2，而不是 constructor 自动改库，支持 preflight、rollback 和 fail-closed。
>
> Final Gate 里我们还发现了一次真实幂等问题：原实现没有把 timestamps 和 supersede relation 纳入 canonical equality，可能让相同 memory_id 携带不同 lifecycle state 还被当成幂等请求。最后把 equality 修成完整 business record comparison，并补了回归测试。

这段已经很适合面试深挖。

------

# 16. 简历表述

现在 WP1 单独仍不建议占一整条简历 bullet，但已经可以成为最终 Advanced Memory 项目的技术支撑。

未来完成 WP5 后，可以合并成类似：

> 设计并实现独立 Long-term Memory Domain，基于 SQLite 构建稳定 Memory Identity、Lifecycle Status、Provenance、原子写入与显式 Schema Migration，将 canonical Memory Record 与向量检索索引解耦，支持后续 Conflict/Supersede/Forget 与 Stateful Evaluation。

当前需要注意：

这句话里的：

> “支持后续 Conflict/Supersede/Forget”

是**架构可支持**。

不是已经完成这些行为。

如果当前单独描述 WP1，应写：

> 实现 Advanced Memory Domain 与 SQLite Persistence Foundation，建立稳定 memory_id、Semantic Memory 类型合同、ACTIVE/SUPERSEDED/FORGOTTEN 生命周期表示、provenance、原子幂等写入及 v1→v2 显式 migration。

这句与当前真实完成状态一致。

------

# 17. 推荐学习文档文件名

按照现有规范：

```text
docs/interview/stage5_phase5_wp1_memory_domain_persistence.md
```

推荐文档标题：

> **Stage5-Phase5-WP1 — Advanced Memory Domain, Identity and Persistence Foundation**

------

# WP1 最值得记住的 7 句话

如果面试前只复习几分钟，优先记这七句：

1. **Conversation History 记录发生过什么，Long-term Memory 记录什么应该长期影响未来行为，两者不能混为一个 Domain。**
2. **`memory_id` 是稳定 record identity，`logical_key` 是可选事实槽，两者不是一回事。**
3. **Logical key 不应该用 UNIQUE Constraint 实现 Conflict Resolution。**
4. **SQLite canonical record 是 Source of Truth，向量和 lexical index 只能是可重建的 Derived Projection。**
5. **WP1 提前支持 ACTIVE / SUPERSEDED / FORGOTTEN 的持久化表达，但生产路径只允许创建 ACTIVE，生命周期 mutation 属于后续 WP。**
6. **Schema migration 必须显式执行，existing DB 的 constructor 不能偷偷升级 durable state。**
7. **Memory idempotency 要比较完整 business record，生命周期字段不同不能被当成同一个幂等请求。**

WP1 的核心学习点不是“SQLite 怎么建表”，而是：

> **如何把一个 Demo 级“存一段文本”提升成真正可以承载生命周期、冲突、遗忘、检索和评测的业务 Domain。**