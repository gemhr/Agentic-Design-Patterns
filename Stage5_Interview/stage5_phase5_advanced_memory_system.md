当前使用的模型：**GPT-5.6 Sol**。

下面开始 **Stage5-Phase5 — Advanced Memory System（高级记忆系统）最终学习 / 面试总结**。

推荐面试材料文件名：

```
docs/interview/phase5-advanced-memory-system.md
```

这一版不再按 WP5、WP6、WP7 分散讲，而是把整个 Phase5 串成一条完整的**架构演进故事**：

> 从“Agent 有一份简单长期记忆”，逐步演进为“有类型、有 Owner、有 Scope、有生命周期、有多 Agent 权限治理、可被独立 Evaluation 验证的 Advanced Memory Runtime”。

Phase5 最终已经完成工程 Final Gate：

```text
PHASE5_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

OPEN_PHASE5_P0 = 0
OPEN_PHASE5_P1 = 0

PHASE5_INTRODUCED_REGRESSIONS = NONE

WP7_BASELINE_STATUS = CANONICAL

PHASE5_ENGINEERING_COMPLETE = YES
PHASE5_INTERVIEW_READY = YES
```

AgentEvalOps 最终 2331 个 nodeid 全量执行到 terminal state，2315 passed、15 个已确认既有失败、1 skipped，没有漏测；WP7 V2 Governance Baseline 已冻结为 canonical。

------

# 一、Phase5 到底解决了什么问题

最开始的 Memory 很容易被理解成：

```text
user query
   ↓
SQLite / Vector DB
   ↓
找到几条历史内容
   ↓
拼进 Prompt
```

这种东西可以叫“有记忆”，但它解决不了生产级 Agent 的几个核心问题：

```text
这条 Memory 到底是什么类型？

谁拥有它？

什么时候形成？

谁能读取？

谁能修改 / 删除？

多个 Agent 之间能不能共享？

delegation 后权限是否自动继承？

Memory 自己能不能声明权限？

一条旧 Memory 被新事实替代后怎么办？

怎么证明这些规则真的成立？
```

所以 Phase5 的本质并不是：

> 给 LocalAgent 再加一个 Memory Store。

而是：

> **把 Memory 从“数据存储能力”提升成 Runtime 中一个有完整 Domain Contract（领域合同）的子系统。**

------

# 二、最终架构全景

最后形成的核心结构可以简化成：

```text
                         ┌─────────────────┐
                         │   User Request  │
                         └────────┬────────┘
                                  ↓
                         Coordinated Runtime
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
          Memory Formation                  Memory Retrieval
                 │                                 │
        ┌────────┴────────┐            ┌───────────┼────────────┐
        │                 │            │           │            │
   Semantic           Episodic      PRIVATE      PROJECT      Episodic
   Memory             Memory        Semantic     Semantic
        │                 │            │           │            │
        │         ┌───────┴───────┐    └───────────┴────────────┘
        │         │               │                 │
        │       RUN             STEP         ContextBuilder
        │       Entry           Specialist          │
        │                                          ↓
        └──────────────────────────────→ USER_CONTENT
```

外围还有 Governance：

```text
Memory Owner
Memory Visibility
Memory Scope
Requester
Authorization
Project Grant
Promotion
Lifecycle
Provenance
```

再外围是 Evaluation：

```text
LocalAgent
= Runtime Fact Owner

AgentEvalOps
= Evaluation Owner

Dataset
= Ground Truth Owner
```

这三层 Owner 是 Phase5 非常关键的设计。

------

# 三、Phase5 的第一条主线：Semantic Memory

## 1. Semantic Memory 是什么

Semantic Memory（语义记忆）回答：

> **“我知道什么？”**

例如：

```text
用户项目数据库 = PostgreSQL
用户偏好的部署方式 = Docker
某项目当前技术栈 = FastAPI + PostgreSQL
```

它记录的是相对稳定的事实，而不是一次完整经历。

------

# 四、为什么 Semantic Memory 不能只是 append-only

最简单的实现可能是：

```text
记住：
database = SQLite

后来再记：
database = PostgreSQL
```

如果两条都 ACTIVE，就会出现冲突：

```text
SQLite
PostgreSQL
```

模型根本不知道哪个才是当前事实。

因此 Phase5 建立了 Lifecycle（生命周期）：

```text
remember
no-change
supersede
forget
```

典型状态演进：

```text
database = SQLite
        ↓ supersede
database = PostgreSQL
```

旧事实不是简单 delete，而是保留历史生命周期语义。

这使 Memory 不再只是：

```text
CRUD
```

而是：

```text
Domain Lifecycle
```

------

# 五、为什么有 NO_CHANGE

例如系统已经有：

```text
database = PostgreSQL
```

本轮又形成：

```text
database = PostgreSQL
```

不应该生成第二条重复 Memory。

所以：

```text
same logical key
+
same typed value
=
NO_CHANGE
```

这解决的是：

> Memory Formation 的幂等性和重复污染。

------

# 六、为什么 Memory Formation 必须挂在 Runtime 生命周期上

最危险的方案是：

```text
模型说：
“我已经记住了”
↓
立刻持久化
```

问题是：

```text
Run 最终可能失败
OutputGate 可能拒绝
答案可能没真正交付
```

因此我们最终要求形成发生在：

```text
runtime completed
+
terminal decision known
+
OutputGate delivered
```

之后。

核心原则：

> **Memory 应该描述已经发生的业务事实，而不是描述模型打算发生的事情。**

------

# 七、Phase5 第二条主线：Episodic Memory

Semantic Memory 解决：

```text
我知道什么？
```

但无法表达：

```text
我以前经历过什么？
```

例如：

> 之前执行 Kubernetes 升级时，因为 API version 不兼容导致 deployment 创建失败，最后通过修改 manifest 恢复。

把这个压成：

```text
kubernetes.version = xxx
```

会丢失大量有价值信息。

所以引入 Episodic Memory（情景记忆）。

------

# 八、Semantic 和 Episodic 的核心区别

可以用一句话记：

```text
Semantic
= Fact

Episodic
= Experience
```

或者：

```text
Semantic:
我知道 PostgreSQL 是当前数据库。

Episodic:
我之前做数据库迁移时，
从 SQLite 切到 PostgreSQL，
中间遇到了 schema migration 问题，
最后成功完成。
```

面试时这是最先要讲清楚的。

------

# 九、为什么 Episode 不是聊天记录

我们明确没有把：

```text
整个对话
整个 Journal
完整 Prompt
模型 CoT
工具原始输出
```

作为 Episode。

Episode 是：

> **一个 bounded、auditable completed experience projection。**

即从真实 Runtime facts 中抽取：

```text
做了什么
谁做的
结果怎样
状态是什么
属于哪个 Run / Step
```

而不是保存整个原始运行过程。

好处：

```text
更小
更稳定
更容易审计
更安全
更适合检索
```

------

# 十、为什么 Episode 不保存 CoT

这是一个很好的面试点。

因为 CoT：

```text
不是业务事实
不稳定
可能包含内部推理
可能包含敏感信息
很难形成稳定 Contract
```

Episode 应保存的是：

```text
Action
Outcome
Status
Provenance
```

而不是模型脑内过程。

------

# 十一、Entry RUN Episode

最开始 WP6 建立的是：

```text
EpisodeKind.RUN
```

它描述整个 Run 的经验。

Owner：

```text
Entry Agent
```

Identity：

```text
origin_run_id
```

意味着：

```text
一个 origin_run_id
→ 一个 RUN Episode
```

重复 formation：

```text
REUSED
```

而不是重复生成。

------

# 十二、为什么后来还要 STEP Episode

进入 Multi-Agent 后出现新问题。

例如：

```text
Entry Agent
    ↓ delegate
Database Specialist
    ↓ actually executes
```

如果最终 Episode 仍全部属于 Entry Agent：

```text
owner = Entry Agent
```

那么真实 performer 的身份被抹掉了。

所以 WP7-C 增加：

```text
EpisodeKind.STEP
```

------

# 十三、STEP Episode 的 Identity

最终定义：

```text
(
    origin_run_id,
    origin_step_id,
    owner_agent_id
)
```

这是一个非常典型的 Domain Identity 设计。

因为同一个：

```text
run_id
```

里面可能有多个 Step；

同一个 Step：

理论上也不能只靠显示名称判断 performer。

------

# 十四、谁才是 Specialist STEP Episode 的 Owner

不是：

```text
Planner 说是谁
```

也不是：

```text
模型文本说是谁
```

更不是：

```text
display_name
```

必须通过：

```text
PlanStep
Binding
StepClaim
Registry
StepResult.producer_agent_id
```

互相一致后得到：

```text
verified actual performer
```

最终：

```text
Episode owner
=
verified performer
```

这背后的原则是：

> **Ownership 必须来自 committed runtime evidence，而不是 declarative intent。**

------

# 十五、为什么失败 Step 不一定形成 Episode

如果只有：

```text
step failed
```

但没有足够的 committed typed evidence 证明：

```text
谁实际执行
执行到了什么程度
真实结果是什么
```

那么不能为了“多记点东西”硬生成 Episode。

因此：

```text
evidence insufficient
→ SKIP
```

这是典型的：

```text
宁可少记
不要编造
```

------

# 十六、Phase5 第三条主线：Multi-Agent Memory Governance

到了 WP7，问题已经不再是：

> 能不能存 Memory？

而是：

> **多个 Agent 存在时，谁能看到谁的 Memory？**

这就是 Governance（治理）。

------

# 十七、四个概念必须分开

WP7-A 冻结了：

```text
MemoryOwner
MemoryVisibility
MemoryScope
Lifecycle
```

这是非常重要的架构拆分。

它们不能混成一个：

```text
agent_id
```

------

# 十八、Owner 是什么

Owner 表示：

> 谁拥有这条 Memory 的治理权。

当前：

```text
PRIVATE record
→ Agent owns

PROJECT record
→ Project / Workspace owns
```

------

# 十九、Visibility 是什么

Visibility 表示：

> 谁可以看到。

当前：

```text
PRIVATE
PROJECT
```

注意：

```text
Owner != Visibility
```

Project Memory 可以由 Project 拥有，并对多个获授权 Agent 可见。

------

# 二十、Scope 是什么

Scope 表示：

> 这条 Memory 位于哪个逻辑分区。

比如：

```text
Agent A private namespace

Project P namespace
```

Scope 本身不等于 Authorization。

这是一个重要区别：

```text
知道 Project P
!=
有权读取 Project P
```

------

# 二十一、Requester 为什么必须和 Owner 分开

旧设计经常把：

```text
agent_id
```

同时理解为：

```text
owner
requester
scope
```

那么：

```text
Agent B 请求 Agent A 的 Memory
```

根本无法清晰表达。

所以 WP7-B 引入：

```text
MemoryAccessPrincipal
```

显式表示：

```text
谁正在请求
```

然后独立指定：

```text
target owner
```

Authorization 才能判断：

```text
requester == owner ?
```

------

# 二十二、Private Memory 的权限模型

当前 Private 规则非常简单：

```text
Owner
→ ALLOW

Foreign Agent
→ DENY
```

覆盖：

```text
read
update
forget
```

并且授权发生在：

```text
Store query BEFORE
```

而不是读取之后再过滤。

------

# 二十三、为什么必须在 Query 前 Authorization

假设：

```text
SQL query
→ 找到 Agent A Memory
→ Python filter
→ 不返回给 Agent B
```

表面上没泄漏。

但实际上：

```text
unauthorized data 已经被访问
```

还可能产生：

```text
timing side channel
log leakage
metric leakage
debug leakage
```

所以必须：

```text
Authorization
↓
Store Query
```

而不是反过来。

------

# 二十四、Delegation != Permission Delegation

这是整个 WP7 最值得记住的一句话：

> **Task delegation is not Memory permission delegation.**

例如：

```text
Entry Agent
→ 把 Step 委派给 Database Specialist
```

只意味着：

```text
你可以执行这个 Step
```

不意味着：

```text
你可以读 Entry Agent 的所有 Private Memory
```

所以：

```text
Delegation
!=
Durable Memory Grant
```

------

# 二十五、dependency result 和 Memory 的区别

Specialist 可以得到：

```text
dependency result
```

用于完成当前 Run。

但是：

```text
dependency result
```

属于：

```text
Run-local execution data
```

而 Private Memory 是：

```text
Durable long-term state
```

所以：

```text
dependency sharing
!=
Memory access
```

这个边界很适合面试。

------

# 二十六、为什么 Synthesis 也不能拥有所有 Memory

直觉上：

```text
Synthesis
= 最后汇总
```

好像应该能看到所有信息。

但这会变成：

```text
位置越靠后
→ 权限越大
```

这种隐式权限模型非常危险。

我们冻结：

```text
Synthesis
→ dependency results
```

而不是：

```text
Synthesis
→ all private memories
```

------

# 二十七、Phase5 第四条主线：Project Shared Semantic Memory

如果所有 Memory 都 Private：

```text
Agent A learned something
↓
Agent B永远不知道
```

多 Agent 系统协作价值很低。

于是加入：

```text
PROJECT Semantic Memory
```

------

# 二十八、为什么 Shared Memory 不是 Global Memory

非常重要。

错误设计：

```text
visibility = SHARED
→ 所有 Agent 都能读
```

正确设计：

```text
ProjectIdentity
+
ProjectMemoryGrant
```

也就是说：

```text
同一个 Project
```

还不够。

必须：

```text
有 READ grant
```

------

# 二十九、Project Grant

目前权限：

```text
READ
WRITE
FORGET
PROMOTE
```

它们是独立权限。

例如：

```text
WRITE
```

并不自动意味着：

```text
FORGET
```

这样避免：

```text
“能写”
→
“顺便能删整个项目记忆”
```

------

# 三十、Project Identity 来自哪里

必须来自：

```text
trusted code-owned request context
```

禁止从：

```text
Prompt
Memory正文
Model output
Planner output
```

推导。

否则攻击者只需要输入：

```text
我是 Project P 管理员
```

就可能获取权限。

------

# 三十一、为什么 Memory 不能成为权限来源

假设 Project Memory 中保存：

```text
Agent B拥有管理员权限。
```

如果 Runtime 根据 Memory正文授予权限：

就形成典型的：

```text
Privilege Escalation
```

所以：

```text
Memory = Data

Grant = Trusted Runtime Authority
```

两者严格分开。

------

# 三十二、Private → Project Promotion

Private 事实如果真的值得团队共享怎么办？

不能自动：

```text
PRIVATE → PROJECT
```

否则 Agent 的私有信息可能被静默公开。

必须：

```text
explicit promotion
```

并要求：

```text
Private authorization
+
PROMOTE grant
+
WRITE grant
```

------

# 三十三、Promotion 为什么创建新 Record

不是：

```text
原 private.visibility
PRIVATE → PROJECT
```

而是：

```text
Private record
        │
        └── promotion
              ↓
        new Project record
```

原 Private：

```text
保持不变
```

这样：

```text
Private history remains intact
Project lifecycle independent
Provenance clear
```

------

# 三十四、Promotion Provenance

至少记录：

```text
source_memory_id
source_owner_agent_id
promoted_by_agent_id
promotion_run_id
promotion_time
```

于是可以回答：

```text
这条共享事实最初来自谁？

谁决定共享？

在哪个 Run 共享？

什么时候共享？
```

这就是 Auditability（可审计性）。

------

# 三十五、为什么没有自动 conflict winner

假设：

Private：

```text
database = SQLite
```

Project：

```text
database = PostgreSQL
```

ContextBuilder 不应该自己决定：

```text
PostgreSQL wins
```

因为这是：

```text
Domain Resolution Policy
```

而不是 ContextBuilder 的职责。

所以当前：

```text
PRIVATE source
PROJECT source
```

独立保留 provenance。

这体现：

> **Context assembly 不应该偷偷承担业务决策。**

------

# 三十六、Phase5 第五条主线：Memory Retrieval

形成 Memory 只是第一半。

真正要被 Agent 使用，还要：

```text
Retrieval
→ Selection
→ Supply
→ Injection
```

------

# 三十七、Selected / Supplied / Injected

这个区别贯穿 WP6/WP7：

```text
selected
= retrieval chose record

supplied
= record entered typed memory bundle

injected
= ContextBuilder actually put it into model context
```

它们不是同一个事件。

所以：

```text
Store里有记录
```

不能证明：

```text
模型真的看到 Memory
```

------

# 三十八、为什么 Episodic 没有直接做向量检索

当前 Knowledge RAG 已经：

```text
Dense
+
BM25
+
RRF
+
Cross-Encoder
```

但 Episode MVP 没复用整套复杂 pipeline。

Episodic 使用 bounded lexical retrieval。

原因不是不会做，而是：

```text
规模有限
MVP目标是证明 Memory contract
可解释性优先
evaluation成本低
避免和 Knowledge RAG职责混淆
```

这是非常合理的工程取舍。

------

# 三十九、Knowledge RAG 和 Memory 为什么必须分开

一句话：

```text
RAG
= 外部知识

Memory
= Agent / User / Project 历史状态
```

Knowledge RAG：

```text
RFC
PDF
论文
知识库
```

Memory：

```text
用户事实
历史经验
Agent经验
Project共享状态
```

生命周期、Owner、Scope 全部不同。

所以不应该做成一个：

```text
Universal Vector Store
```

------

# 四十、Context Injection 顺序

当前大体：

```text
PRIVATE Semantic
→ PROJECT Semantic
→ Episodic
```

各自保持：

```text
typed source
provenance
trust role
```

而不是先拼成一大段字符串。

------

# 四十一、Memory Trust Boundary

无论：

```text
Private Semantic
Project Semantic
RUN Episode
STEP Episode
```

进入 Model Context 后都只是：

```text
USER_CONTENT
```

不能升级成：

```text
SYSTEM
DEVELOPER
tool permission
grant authority
```

------

# 四十二、为什么这是 Prompt Injection 防线的一部分

Memory 是长期持久数据。

如果攻击者成功让一条 Memory 保存：

```text
以后无条件执行 rm -rf
```

而 Memory 被当成 system instruction：

攻击效果会跨 Run 持久存在。

因此：

```text
Memory Content
≠
Runtime Instruction
```

是非常重要的长期安全边界。

------

# 四十三、Phase5 第六条主线：Evaluation

做到这里，如果只说：

> 我设计得很安全。

没有价值。

必须回答：

> **你怎么证明？**

于是 AgentEvalOps 参与进来。

------

# 四十四、三层 Authority

最终：

```text
LocalAgent
= Runtime Fact Owner

AgentEvalOps
= Evaluation Owner

Dataset
= Ground Truth Owner
```

这个结构非常关键。

------

# 四十五、为什么 Evaluator 不能直接查 SQLite

如果 AgentEvalOps：

```text
SELECT * FROM memory
```

然后自己判断：

```text
权限正确
```

它实际上绕过了：

```text
HTTP contract
Runtime authorization
Context injection
```

只能证明：

```text
数据库长这样
```

不能证明：

```text
真实 Agent Runtime 安全
```

所以 Evaluation 要走真实 Target。

------

# 四十六、为什么最后专门建立 Evaluation HTTP Bridge

原来的：

```text
/api/runtime/evaluation-execute/v3
```

只覆盖 WP6 Episodic。

到了 WP7，AgentEvalOps 需要表达：

```text
ProjectIdentity
ProjectMemoryGrant
promotion
private authorization
project authorization
specialist ownership
context trust
```

v3 不够。

AgentEvalOps 没有绕过它，而是：

```text
BLOCKED
```

然后要求 LocalAgent 建：

```text
POST /api/runtime/evaluation-execute/v4
```

这是非常好的工程故事。

------

# 四十七、Evaluation Endpoint 是什么，不是什么

它是：

```text
TEST_ONLY
typed
deterministic
safe evidence bridge
```

不是：

```text
新 production Memory API
```

AgentEvalOps 可以：

```text
控制实验条件
```

但不能：

```text
决定 Runtime事实
```

------

# 四十八、Phase5 最经典 Bad Case：V1 表面 PASS

WP7-E 第一次跑完后，artifact 看起来 PASS。

但审计发现：

### G04

只做了：

```text
Project WRITE
```

却声称：

```text
Cross-Agent Recall PASS
```

没有 Agent B retrieval。

------

### G05

fresh DB 本来没有 Project P。

然后 Project Q：

```text
retrieval = 0
```

就说：

```text
Scope Isolation PASS
```

毫无意义。

------

### G06

Project P根本不存在。

无 READ grant：

```text
retrieval = 0
```

也不能证明 Grant Enforcement。

------

### G12

没有真实 instruction-like Memory injection。

因此无法证明：

```text
USER_CONTENT trust
```

------

# 四十九、最重要的 Evaluation 原则

从这个 Bad Case 得到：

> **Negative Test 必须先证明被保护的目标真实存在。**

标准结构：

```text
Target Exists
        ↓
Unauthorized Action
        ↓
Authorization DENY
        ↓
Zero Retrieval / Mutation
```

否则：

```text
nothing happened
```

不能证明：

```text
security worked
```

------

# 五十、为什么不能偷偷修改 V1

因为 V1 已经被执行。

如果原地改：

```text
昨天：
8/12

今天：
12/12
```

无法判断：

```text
Runtime improved
还是
Dataset changed
```

所以：

```text
V1 preserved
```

创建：

```text
multi_agent_memory_governance_v2
```

并建立 lineage：

```text
STATEFUL_EVIDENCE_DEFECT
```

------

# 五十一、V2 真正做对了什么

核心不是：

```text
把数字变成 12/12
```

而是：

```text
Run A
→ establish durable state

Run B
→ consume / attack that state
```

例如：

```text
Run A:
Project P database=PostgreSQL

Run B:
Agent B + Project P READ
→ actual recall
```

这才是真正的 Stateful Evaluation（有状态评估）。

------

# 五十二、为什么 Target 自己的 gate 不能作为权威

如果 LocalAgent返回：

```text
passed = true
```

然后 AgentEvalOps：

```text
if response.passed:
    PASS
```

那就是：

> 被测系统自己给自己打分。

所以正式 V2：

```text
Target
→ actual facts only

Evaluator
→ verdict

Dataset
→ expectation
```

------

# 五十三、Typed Observation

v4 返回很多 evidence：

```text
authorization
retrieval
mutation
promotion
specialist
trust
```

AgentEvalOps 不直接到处解析 dict。

先：

```text
HTTP response
↓
Typed Observation
↓
Evaluator
```

这使 schema drift 和 field semantics 更可控。

------

# 五十四、Per-Surface Evaluator

不是一个：

```text
evaluate_everything()
```

而是语义上拆：

```text
Authorization
Retrieval
Mutation
Promotion
Specialist Ownership
Delegation Boundary
Context Trust
```

这样失败才能精确归因。

------

# 五十五、P0 Governance Violation

以下不是普通 fail：

```text
Foreign Private Memory leakage

Cross-project leakage

Unauthorized mutation success

Instruction elevation
```

属于：

```text
P0
```

一个真实发生：

```text
Layer1 Gate = FAIL
```

不能靠平均分盖过去。

------

# 五十六、WP7 V2 最终 Evaluation

正式结果：

```text
Dataset =
multi_agent_memory_governance_v2

12 / 12 Scenarios PASS

0 BLOCKED

P0_MEMORY_GOVERNANCE_VIOLATIONS = 0
```



------

# 五十七、为什么还要 Canonical Baseline

一次：

```text
12/12 PASS
```

还不够。

如果过两天源码变了：

那这次实验已经不能代表当前代码。

所以最终绑定：

```text
Dataset digest

Target implementation ref
Target source receipt

AgentEvalOps implementation ref
AgentEvalOps source receipt

Experiment artifact digest
```

形成 Baseline。

------

# 五十八、Candidate 和 Canonical 为什么分开

先：

```text
Experiment Artifact
```

然后：

```text
Candidate Baseline
```

最后独立 authority：

```text
freeze_decision = CANONICAL
```

而不是修改历史 artifact：

```text
candidate → canonical
```

这样可以保持 evidence immutability。

------

# 五十九、Final Gate 最后一个 Bad Case

第一次 Phase5 Final Gate：

```text
BLOCKED
```

不是因为 Memory失败，而是：

```text
AgentEvalOps full pytest
没有 terminal result
```

当时只看到：

```text
2331 tests collected
```

pytest zero CPU。

我们没有：

```text
“应该没问题”
→ PASS
```

而是继续诊断。

------

# 六十、最终发现根本不是死锁

第一个 integration test：

```text
test_full_beir_scifact_baseline_real_execution
```

因为：

```text
BEIR_SCIFACT_PREBUILT_DIR
```

没有设置，触发 cold build。

后来正确使用已有 cache 后：

```text
test本身完成
```

进一步发现：

```text
Redis localhost:6380
```

没有启动。

最终 Docker Desktop 恢复：

```text
redis-test
```

启动完成。

------

# 六十一、最终 full regression

AgentEvalOps：

```text
2331 collected
2331 executed

2315 passed
15 failed
1 skipped
```

15 failures 全部完成 attribution，没有：

```text
UNKNOWN
```

也没有 Phase5 introduced regression。

因此：

```text
PHASE5_FINAL_GATE =
PASS_WITH_ACCEPTED_LIMITATIONS
```

------

# 六十二、Phase5 真实最终能力

可以真实说已经实现：

```text
Semantic Memory
✅

Entry RUN Episodic Memory
✅

Specialist STEP Episodic Memory
✅

Private Agent Memory
✅

Project Shared Semantic Memory
✅

Cross-Agent Project Recall
✅

READ / WRITE / FORGET / PROMOTE
✅

Private → Project explicit promotion
✅

Delegation permission isolation
✅

Synthesis private isolation
✅

Context USER_CONTENT trust
✅

Stateful governance evaluation
✅

Canonical evaluation baseline
✅
```



------

# 六十三、真实 Accepted Limitations

不能说已经实现：

```text
External durable Project IAM
❌

Shared Episodic
❌

Specialist Semantic formation
❌

Specialist self-private retrieval
❌

Vector / Hybrid Episodic retrieval
❌

Memory Graph
❌

Procedural Memory
❌

TTL / Decay
❌

CRDT
❌

Distributed Memory
❌

WP7 real-model statistical benchmark
❌
```

这些已经正式作为 limitation/future work，不阻塞 Phase5。

------

# 六十四、名词 / 概念速览

| 名词                    | 一句话理解                                                 |
| ----------------------- | ---------------------------------------------------------- |
| Semantic Memory         | 保存“我知道什么”的长期事实。                               |
| Episodic Memory         | 保存“我以前经历过什么”的历史经验。                         |
| RUN Episode             | 以整个 Run 为单位形成的 Entry Agent 经验。                 |
| STEP Episode            | 以具体 delegated Step 为单位形成的 Specialist 经验。       |
| Formation               | 将 Runtime 已完成事实投影成长期 Memory 的过程。            |
| Retrieval               | 根据当前请求找到相关 Memory。                              |
| Memory Owner            | 对某条 Memory 拥有治理权的逻辑主体。                       |
| Requester               | 当前正在申请访问 Memory 的主体。                           |
| Visibility              | Memory 能被哪些范围的主体看到。                            |
| Scope                   | Memory 所属的逻辑 namespace。                              |
| Lifecycle               | remember / no-change / supersede / forget 等状态演进。     |
| Authorization           | 判断 requester 是否有权限执行 Memory 操作。                |
| ProjectIdentity         | 当前 Run 被可信绑定到哪个 Project。                        |
| ProjectMemoryGrant      | 某 Agent 对 Project Memory 拥有的显式权限。                |
| Promotion               | 将 Private Semantic 显式复制/投影为新的 Project Semantic。 |
| Provenance              | 记录 Memory 来自哪里、谁产生或 promotion。                 |
| Idempotency             | 同一个业务事件重复执行不会产生重复持久状态。               |
| ContextBuilder          | 将 typed Memory evidence转换成模型上下文的边界。           |
| USER_CONTENT            | Memory在模型上下文中的可信等级，仅作为数据而非指令。       |
| Stateful Evaluation     | Scenario 中多个 Run 共享真实 Durable State 的评估方式。    |
| Ground Truth            | Dataset 定义的期望业务行为。                               |
| Runtime Evidence        | 被测系统真实执行后产生的事实。                             |
| Source Receipt          | 对构成实验语义的源文件逐个做可审计内容证明。               |
| Canonical Baseline      | 与 Dataset、源码和 artifact绑定的正式回归基准。            |
| Fail Closed             | 身份、权限或证据不明确时默认拒绝。                         |
| P0 Governance Violation | Private泄漏、越权 mutation、scope leakage等严重治理错误。  |

------

# 六十五、最重要的工程设计原则

建议你真正背住下面十条。

### 1.

```text
Memory != Chat History
```

Memory 是经过 Formation 的长期业务状态。

### 2.

```text
Fact != Experience
```

Semantic 和 Episodic 分开。

### 3.

```text
Intent != Runtime Fact
```

Memory Formation 根据 committed runtime evidence。

### 4.

```text
Task Delegation != Permission Delegation
```

委派执行任务不代表继承长期记忆权限。

### 5.

```text
Project Identity != Project Grant
```

属于哪个 Project 不代表能读取 Project Memory。

### 6.

```text
Memory Content != Authorization
```

Memory正文不能自己声明权限。

### 7.

```text
Retrieval != Injection
```

Store 中存在也不代表模型真正看到了。

### 8.

```text
Negative Result != Security Proof
```

必须先证明 target exists。

### 9.

```text
Target Facts != Evaluator Verdict
```

被测系统不能给自己打分。

### 10.

```text
Experiment PASS != Canonical Baseline
```

还必须绑定 Dataset + Source + Artifact。

------

# 六十六、工程方法类问题：为什么不是直接用向量数据库做全部 Memory

因为 Memory 不只是 retrieval 问题。

向量数据库主要回答：

```text
哪个内容相似？
```

但生产 Memory 还需要：

```text
Owner
Authorization
Lifecycle
Identity
Promotion
Provenance
Formation timing
Trust
Evaluation
```

所以：

> Vector Store 只是 Memory Retrieval Backend 的一种可能实现，不等于 Memory System。

------

# 六十七、为什么不用 LangGraph / Mem0 直接解决

面试不要说：

> 它们不好。

正确说：

> 通用框架可以快速提供 storage、namespace、retrieval 等能力，但我这个项目的学习目标是把 Runtime Owner、Formation、multi-agent ownership、authorization 和 evaluation contract 做清楚，因此核心治理逻辑由 LocalAgent 自己拥有。未来底层 Store 或 Retrieval 完全可以替换成框架能力，但 Domain Contract 不应该由第三方存储实现决定。

------

# 六十八、为什么 Private 和 Project 不做两个完全独立系统

因为它们共享很多：

```text
Semantic lifecycle
canonical rendering
persistence patterns
context representation
evaluation semantics
```

完全分裂会重复实现。

但 Governance 必须独立：

```text
Private owner = Agent
Project owner = Project
```

所以是：

> 共享基础设施，分离权限合同。

------

# 六十九、为什么没有做自动 Private → Project 共享

因为系统很难可靠推断：

```text
“这条私人事实可以共享”
```

这涉及隐私和治理。

所以 MVP：

```text
Explicit Promotion
```

是风险最低、最容易审计的选择。

------

# 七十、为什么没有 Shared Episodic

Shared Episodic 比 Shared Semantic 复杂得多。

需要考虑：

```text
谁拥有跨 Agent experience？

一次多 Agent Run 是一条 Episode还是多条？

谁能 forget？

redaction怎么办？

不同 Agent对同一事件观察冲突怎么办？

如何处理 partial visibility？
```

为了 Phase5 面试价值和可信闭环，选择：

```text
Private Episodic
+
Project Shared Semantic
```

比盲目扩展更合理。

------

# 七十一、为什么没有 Procedural Memory

Procedural Memory（程序性记忆）通常保存：

```text
“以后应该怎么做”
```

它和：

```text
Prompt
Policy
Skill
Instruction
```

边界很近。

如果设计不好，Memory 就开始直接影响 Agent行为规则。

因此它需要更强的：

```text
trust
versioning
policy authority
rollback
evaluation
```

Phase5 没有为了凑三种 Memory 而硬上。

------

# 七十二、为什么不用 LLM 自己决定所有 Memory 更新

因为模型适合：

```text
candidate extraction
semantic interpretation
```

但不应该拥有：

```text
Owner
Permission
Run identity
actual tool result
terminal state
scope
```

所以：

```text
Model may propose
Runtime must verify
```

是更稳妥的设计。

------

# 七十三、为什么 Provenance 很重要

如果没有 provenance，一条 Memory：

```text
database=PostgreSQL
```

只能回答：

```text
是什么
```

不能回答：

```text
谁形成的？
哪个 Run？
来自 Private还是Project？
谁 promotion？
是否由 Specialist产生？
```

在 Multi-Agent 系统里，没有 provenance 很快就无法审计。

------

# 七十四、为什么 canonical text 和 payload 要分开

可以理解成：

```text
payload
= machine-readable truth

canonical text
= retrieval / context-readable projection
```

避免直接让：

```text
自然语言正文
```

成为唯一事实来源。

------

# 七十五、为什么 Evaluation 比再加一个 Memory 类型更重要

因为已经拥有：

```text
Semantic
Episodic
Private
Shared
```

之后再加：

```text
Procedural
Graph
Temporal
```

带来的面试边际收益变小。

但能证明：

```text
Private没有泄漏
Cross-agent sharing真实工作
Unauthorized mutation=0
Dataset没有自证
Baseline可重现
```

更能体现真实工程能力。

------

# 七十六、Phase5 最值得讲的 6 个 Bad Case

## Bad Case 1：Plan / Model 声称 performer

风险：

```text
Memory ownership错误
```

修复：

```text
verified committed runtime performer
```

------

## Bad Case 2：Delegation 自动继承 Memory

风险：

```text
Agent-private data leakage
```

修复：

```text
task delegation
!=
memory grant
```

------

## Bad Case 3：Project identity 自动等于授权

风险：

```text
same project = unrestricted access
```

修复：

```text
ProjectIdentity + explicit Grant
```

------

## Bad Case 4：Evaluator 没合同就直接查库

风险：

```text
Evaluator越过 Runtime Authority
```

真实处理：

```text
BLOCKED
→ LocalAgent v4 Evaluation Bridge
```

------

## Bad Case 5：空数据库 negative test 被判 PASS

风险：

```text
false security confidence
```

真实处理：

```text
reject V1 authority
→ immutable V2
→ Run A establish state
→ Run B attack
```

------

## Bad Case 6：Final Gate 因 pytest无输出就猜通过

真实处理：

```text
BLOCKED
→ diagnose first test
→ BEIR cold build
→ Redis test prerequisite
→ Docker recovery
→ 2331/2331 complete execution
```

这六个 Bad Case 足够支撑大量面试追问。

------

# 七十七、高频面试追问与答案

## Q1：你们的 Memory 系统和普通聊天历史有什么区别？

> 聊天历史只是历史消息，而我们的 Memory 是由 Runtime 在确定业务事实后形成的长期状态。它有明确的 Semantic/Episodic 类型、Owner、Scope、Lifecycle、Authorization、Provenance 和 Evaluation，不是简单把历史对话重新塞进 Prompt。

------

## Q2：Semantic 和 Episodic 怎么区分？

> Semantic 保存稳定事实，回答“我知道什么”；Episodic 保存已完成经历，回答“我以前经历过什么”。比如“项目数据库是 PostgreSQL”属于 Semantic，而“上次数据库迁移遇到 schema 问题并最终恢复”属于 Episodic。

------

## Q3：为什么 Episode 不能直接存整段运行日志？

> 原始日志包含噪声、内部执行细节、模型文本甚至敏感信息，而且不稳定。我把 Episode 定义成对已完成 Runtime Experience 的 bounded projection，只保留可审计的 action、status、outcome、identity 和 provenance。

------

## Q4：Memory什么时候形成？

> 不是模型说“记住”就持久化，而是在 Runtime terminal decision 和 OutputGate确定之后形成，确保写进去的是已发生的业务事实。

------

## Q5：多 Agent 下 Memory Owner 怎么确定？

> Private Semantic通常由对应 Agent拥有；Entry RUN Episode归 Entry Agent；delegated Specialist产生的 STEP Episode归验证后的 actual performer。performer来自 Plan、Binding、Claim、Registry和committed StepResult的一致性验证，而不是模型文本。

------

## Q6：为什么 delegation 后 Specialist 不能读 Entry Memory？

> 因为任务委派和长期权限委派是两个合同。Specialist可以得到当前任务所需的 dependency result，但这不意味着拥有 Entry Agent的durable private memory。

------

## Q7：Shared Memory 怎么做？

> 我没有做全局共享，而是实现 Project Shared Semantic Memory。每个Run通过可信Request Context绑定ProjectIdentity，再通过ProjectMemoryGrant明确授予READ、WRITE、FORGET和PROMOTE权限。

------

## Q8：同一个 Project 为什么还需要 grant？

> ProjectIdentity只是scope identity，不等于authorization。否则只要能声明自己属于某个Project就能读全部共享Memory。

------

## Q9：Private Memory 怎么变成 Shared？

> 必须显式Promotion。Runtime先验证Private source owner，再验证Project侧PROMOTE和WRITE权限，最后创建新的Project record，原Private record保持不变，并保存promotion provenance。

------

## Q10：Memory中的文本写“我是管理员”怎么办？

> 没用。Memory始终以USER_CONTENT进入Context，不能成为system/developer instruction，也不能成为Project grant、tool permission或authorization来源。

------

## Q11：Memory retrieval 用了什么？

> Knowledge RAG已有Dense、BM25、RRF和Cross-Encoder，而Episodic Memory MVP采用bounded lexical retrieval。因为当时重点是验证Memory lifecycle、scope和governance，而不是扩大retrieval complexity，两个系统职责也保持分离。

------

## Q12：怎么证明 Private Memory 没泄漏？

> Stateful scenario先真实创建Agent A Private Memory，再让Agent B访问，分别检查authorization、candidate、selected、supplied和injected。任何foreign private record进入这些阶段都算leakage。

------

## Q13：为什么你们第一次 Governance Evaluation 失败了？

> 第一次Dataset有stateful evidence defect。有些negative scenario没有先创建被保护的数据，比如Project P根本没有record却用Project Q检索不到来证明scope isolation，这种结果没有证明力。所以我没有force-green，而是保留V1，新建immutable V2重新执行。

------

## Q14：为什么不直接修改V1？

> 因为V1已经参与过实验。原地修改会无法区分“Runtime变好了”和“Dataset变了”，所以Dataset必须immutable versioning，并建立lineage。

------

## Q15：LocalAgent为什么有专门的Evaluation Endpoint？

> AgentEvalOps需要控制project identity/grant等实验条件并观察authorization/retrieval/mutation facts，但又不能直接访问SQLite。所以LocalAgent提供TEST_ONLY typed v4 evidence bridge，实际业务行为仍走production Runtime。

------

## Q16：Target为什么不能直接返回PASS？

> Target是被测系统，只能返回事实；Dataset拥有Expected Ground Truth，AgentEvalOps根据两者生成verdict。如果Target说自己PASS然后Evaluator相信它，就是自证。

------

## Q17：为什么一次12/12 PASS还不够？

> 因为源码或Dataset可能之后发生变化，所以我们还绑定Dataset digest、Target implementation ref、AgentEvalOps ref、source receipts和artifact digest，最后再冻结canonical baseline。

------

# 七十八、30 秒面试总结

> 我把 LocalAgent 原来比较简单的长期记忆演进成了一套有类型和治理能力的 Advanced Memory System。Semantic Memory负责长期事实，支持 remember、supersede和forget；Episodic Memory记录已完成的Run或delegated Step经验，并根据真实Runtime performer确定owner。在多Agent场景下，我进一步区分Private和Project Shared Memory，显式拆分requester、owner、scope和visibility，Project共享需要typed identity和READ/WRITE/FORGET/PROMOTE grant，task delegation不会自动继承private memory权限。最后通过独立AgentEvalOps做stateful governance evaluation，验证跨Agent recall、private leakage、scope isolation、unauthorized mutation、promotion和context trust，并冻结了canonical baseline。Phase5最终以`PASS_WITH_ACCEPTED_LIMITATIONS`收口。

------

# 七十九、2 分钟面试总结

> Phase5主要解决的是Agent长期记忆从“简单存储”走向生产级Runtime contract的问题。
>
> 第一阶段我先做Semantic Memory，用typed lifecycle表达remember、no-change、supersede和forget，并把formation放到Runtime terminal/output边界之后，避免模型意图直接污染持久状态。
>
> 第二阶段做Episodic Memory，把长期事实和历史经历分开。Entry Agent形成RUN Episode，delegated Specialist形成STEP Episode。Specialist owner不是由Planner或模型文本决定，而是根据Plan、Binding、StepClaim、Registry和committed StepResult验证actual performer。
>
> 第三阶段进入Multi-Agent Governance。我把requester、owner、visibility和scope拆开，Private Memory只能owner自己访问；delegation只表示任务执行权，不表示durable memory permission。为了支持跨Agent协作，又加入Project Shared Semantic Memory，通过可信ProjectIdentity和显式READ、WRITE、FORGET、PROMOTE grant控制访问。Private到Project也不能自动共享，而是显式promotion并保存provenance。
>
> 安全上所有Memory进入模型都只是USER_CONTENT，不能作为system instruction或权限来源。
>
> 最后我没有只靠unit test证明它，而是用AgentEvalOps建立stateful evaluation。过程中第一次Dataset虽然表面PASS，但审计发现negative scenario没有先建立真实target state，所以我保留V1，新建immutable V2，用Run A建立durable state、Run B再做跨Agent或越权验证。V2最终12/12 scenario PASS，P0 governance violation为0，并通过Dataset digest、双端implementation ref、source receipt和artifact digest冻结canonical baseline。最后两仓full regression完成，Phase5以PASS_WITH_ACCEPTED_LIMITATIONS正式结束。

------

# 八十、如果面试官问“这个设计最大的亮点是什么？”

不建议回答：

> 我用了 Semantic + Episodic。

这个太普通。

更好的回答是：

> **我把 Memory 做成了 Runtime Governance Domain，而不是一个 Vector Store。**

展开：

```text
类型
+
生命周期
+
Owner
+
Scope
+
Authorization
+
Multi-Agent sharing
+
Trust
+
Evaluation
```

这是整个 Phase5 最核心的工程价值。

------

# 八十一、如果面试官问“最大的工程教训是什么？”

推荐回答：

> **最容易产生假安全感的不是功能没实现，而是评估证据不成立。**

可以接 V1 Bad Case：

> 我们第一次做Project scope isolation时fresh DB里根本没有目标record，所以“检索不到”并不能证明隔离。后来我把negative scenario改成先真实建立被保护状态，再进行越权访问，并重新版本化Dataset。这个问题让我意识到安全测试必须验证precondition、action、decision和side effect完整证据链，而不能只看最终结果。

这个答案非常有区分度。

------

# 八十二、如果只背 8 句话

最后给你压成八句：

1. **Semantic 是事实，Episodic 是经历。**
2. **Memory Formation 由 Runtime facts 驱动，不由模型声明驱动。**
3. **RUN Episode 属于 Entry，STEP Episode 属于 verified performer。**
4. **Requester、Owner、Scope、Visibility 必须分开。**
5. **Task delegation 不等于 Memory permission delegation。**
6. **Project identity 不等于 Project grant。**
7. **Memory 永远只是 USER_CONTENT，不能成为权限来源。**
8. **Evaluation 必须证明真实 state 和 evidence chain，而不是让 Target 自证 PASS。**

把这八条真正理解以后，Phase5 大部分系统设计追问都能顺着回答。

------

# 八十三、Phase5 学习最终结论

你现在不需要继续给 Memory 堆新能力。

从面试角度，Phase5 已经形成一个完整故事：

```text
简单长期记忆
↓
Typed Semantic lifecycle
↓
Episodic experience
↓
RUN / STEP ownership
↓
Private authorization
↓
Project shared memory
↓
Explicit promotion
↓
Multi-agent governance
↓
Stateful evaluation
↓
Canonical baseline
```

而且不是“设计过”，而是已经经过实现、测试、真实 Bad Case 修正和最终 Gate 收口。Phase5 最终工程状态为 `PASS_WITH_ACCEPTED_LIMITATIONS`，WP7 Governance baseline 已正式 canonical freeze。

**Stage5-Phase5 Advanced Memory System 的学习与工程主线到这里可以正式结束。**