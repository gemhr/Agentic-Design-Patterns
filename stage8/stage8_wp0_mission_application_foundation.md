当前对话使用 **GPT-5.6 Sol**。

下面进入 **Stage8-WP0 — Mission & Application Foundation** 的学习 / 面试总结。推荐学习文档文件名：

```text
docs/interview/stage8_wp0_mission_application_foundation.md
```

WP0 最终已经通过 Gate：`WP0_FINAL_GATE = PASS`，`P0=0`、`BLOCKING_P1=0`，并且没有重开既有 Runtime 架构。

------

# 1. 名词 / 概念速览

**业务任务（Mission）**
跨多个 Agent Run、人工审核和外部任务存在的长生命周期业务对象，例如一次 Feature 的完整测试过程。

**运行（Run）**
AgentCore 中一次短生命周期智能执行，有明确 Deadline、Budget 和 Terminal State。

**应用层（Application Layer）**
负责组织业务用例、事务和状态推进，不负责底层模型推理或 Tool 执行。

**领域对象（Domain Object）**
表达真实业务概念及规则的对象，例如 `FeatureTestMission`、`BusinessReview`。

**仓储（Repository）**
负责数据库读写，不拥有业务状态转换规则。

**事务所有者（Transaction Owner）**
决定一次业务操作中哪些数据库修改必须原子提交；WP0 中由 Application Service 持有。

**乐观并发控制（Optimistic Concurrency Control, OCC）**
通过版本号等条件检测并发修改冲突，而不是提前加全局锁。

**比较并交换（Compare-and-Swap, CAS）**
只有数据库当前值仍符合预期时才允许更新，例如 `version = expected_version`。

**首次决策生效（First-wins）**
多个并发审批请求中，第一个成功提交的决定成为最终事实。

**幂等（Idempotency）**
重复执行同一个已经成功的决定，不会产生新的副作用或改变最终状态。

**业务审核（Business Review）**
审核 Test Plan、Case、Expected Result 等业务内容，与 Runtime Tool Approval 属于不同 Domain。

**工具审批（Tool Approval）**
Agent 执行高风险 Tool 前的 Runtime 安全控制，绑定具体 Tool Invocation。

**主题绑定（Subject Binding）**
审批必须绑定被审核内容的具体 version / digest，避免批准旧内容后作用到新内容。

**组合根（Composition Root）**
负责创建并连接应用级依赖的地方，本项目主要由 `server.py::lifespan()` 承担。

------

# 2. 这个 WP 解决了什么业务问题

Stage8 后续要完成这样一条链：

```text
Feature
→ Risk Analysis
→ Test Planning
→ Human Review
→ Execution
→ Failure Triage
→ CI Guardian
```

这里有一个很现实的问题：

**整个 Feature 测试流程可能持续几小时甚至几天，但 AgentCore Run 本身不应该持续这么久。**

比如：

```text
Feature F123

上午：
Risk Agent Run

下午：
Test Planning Agent Run

晚上：
测试人员审核 Test Plan

第二天：
启动远程测试

几个小时后：
Execution callback

然后：
Failure Triage Agent Run
```

如果直接让一个 Agent Run 表示整个过程：

```text
Run
├─ Risk
├─ 等人审批 6 小时
├─ Test Plan
├─ 等执行机 3 小时
└─ Failure Triage
```

就会破坏原 Runtime 的语义：

- Deadline 怎么定义？
- Budget 怎么管理？
- Run 一直占资源怎么办？
- Runtime Recovery 要不要负责业务等待？
- 一个几天的 Feature 为什么要塞进一次模型执行？

所以 WP0 引入了：

```text
FeatureTestMission
```

正确关系变成：

```text
FeatureTestMission F123
│
├─ Run A: Risk Analysis
├─ Business Review
├─ Run B: Test Planning
├─ External Execution
└─ Run C: Failure Triage
```

Mission 是业务生命周期。

Run 是一次有界智能计算。

最终实现也明确保持了这个边界：Mission 只保存 Run 引用，不创建、不恢复、不修改 Runtime Run。

------

# 3. 工程构建方法问答

## 为什么不能直接扩展 AgentStateMachine？

因为它们描述的是两个完全不同层级的状态。

`AgentStateMachine` 管的是：

```text
一次 Agent Run
```

例如：

```text
RUNNING
CANCELLED
FAILED
COMPLETED
```

而 Mission 管的是：

```text
一次 Feature Testing Process
```

例如：

```text
CONTEXT_READY
AWAITING_REVIEW
READY_FOR_EXECUTION
EXECUTING
TRIAGING
COMPLETED
```

如果混到一起，Runtime 就会开始理解：

- 什么叫 Test Plan；
- 什么叫 Remote Execution；
- 什么叫 Case Review；
- 什么叫 CI。

这样 Runtime 从通用执行底座变成通信测试业务系统。

所以我们选择：

```text
FeatureTestMission != AgentStateMachine
```

这是 WP0 最重要的 Architecture Boundary。

------

## 为什么 Mission 不能直接等远程执行几个小时？

因为 Agent Run 是有界执行。

Run 有：

```text
Deadline
Budget
Cancellation
Terminal State
```

远程 PC 执行可能：

```text
1 小时
3 小时
10 小时
```

正确模式是：

```text
Agent Run
→ 决定怎么执行
→ start_execution
→ 返回 execution_id
→ Run terminal
```

然后：

```text
Mission = EXECUTING
```

未来由：

```text
callback / worker
```

得到结果后，再启动新的 Triage Run。

这样等待是**业务等待**，而不是**模型执行等待**。

------

## 为什么 Application Service 是 Transaction Owner？

因为 Repository 只应该回答：

> 怎么读写数据？

而 Application Service 才知道：

> 这次业务操作需要哪些修改一起成功？

例如推进 Mission：

```text
validate transition
→ CAS update Mission
→ commit
```

或者未来：

```text
create external execution
+
update Mission status
+
write outbox
```

这些属于一个业务 Use Case。

所以：

```text
Application Service
    ↓ transaction
Repository
```

而不是：

```text
Repository
→ 自己决定 transaction
```

最终实现中 Mission / Business Review 的事务确实由对应 Application Service 持有。

------

## 为什么需要 CAS，而不是先查 version 再 update？

错误方式：

```python
mission = get(id)

if mission.version == expected_version:
    update(mission)
```

问题是两个请求可以同时：

```text
Request A reads version=3
Request B reads version=3
```

然后：

```text
A → version 4
B → version 4
```

B 会覆盖 A。

正确做法是让数据库承担最后判断：

```sql
UPDATE mission
SET ...
WHERE mission_id = ?
AND version = 3;
```

两个请求即使同时看到 version 3：

```text
A update → 1 row
B update → 0 rows
```

所以 stale writer 能被发现。

WP0 的真实实现已经使用 `mission_id + expected_version` 条件更新。

------

## 为什么不用分布式锁？

因为这里的业务需求只是：

> 避免两个请求同时修改同一个数据库对象。

PostgreSQL CAS / row lock 已经够用。

如果再引入：

```text
Redis distributed lock
ZooKeeper
etcd
```

会增加：

- lease；
- lock timeout；
- lock loss；
- 双写；
- 运维复杂度。

对当前 200 人左右的内部系统没有收益。

------

## 为什么 Business Review 不能复用 Tool Approval？

两者看起来都有：

```text
approve / reject
```

但它们批准的东西完全不同。

Tool Approval 批准的是：

```text
具体 ToolInvocation
```

例如：

```text
create_ticket(
    severity="critical",
    feature="F123"
)
```

它关心：

```text
risk
invocation binding
execution claim
run binding
side effect
```

而 Business Review 批准的是：

```text
Test Plan Version 4
```

它可能：

- 跨多个 Run；
- 等几个小时；
- 审核一份业务文档；
- 本身并没有 ToolInvocation。

所以：

```text
Business Review
!=
Tool Approval
```

最终 WP0 也创建了独立的 `stage8_business_reviews` Truth，而没有复用 `ToolApprovalController` 或 `DurableApprovalRow`。

------

## 那为什么 Business Review 又借鉴 Tool Approval？

因为一些并发模式是通用工程问题：

```text
first-wins
CAS
idempotency
digest binding
```

我们复用的是**设计思想**，不是复用 Domain Model。

例如：

```text
Reviewer A → APPROVE
Reviewer B → REJECT
```

不能最终由请求顺序随机覆盖。

所以必须：

```text
PENDING
→ APPROVED
```

之后：

```text
REJECT
```

失败。

WP0 通过数据库 row lock + `status = PENDING` 条件保证并发相反决定最多一个成功。

------

## 为什么同一个 approve 再 approve 要允许？

因为 HTTP 请求可能：

```text
Client
→ APPROVE
→ Server commit

网络断了

Client 不知道成功没有
→ 再次 APPROVE
```

如果第二次直接报错，客户端很难区分：

```text
第一次没执行
```

还是：

```text
第一次成功，只是响应丢了
```

所以：

```text
APPROVE → APPROVE
```

可以幂等返回。

但：

```text
APPROVE → REJECT
```

必须冲突。

------

## Subject Version / Digest 是干什么的？

这是 WP0 实际发现过的 Bad Case。

比如审核的是：

```text
Test Plan v3
digest = abc
```

Reviewer 点了批准。

但在审批前，内容已经更新成：

```text
Test Plan v4
digest = xyz
```

如果 Review 只绑定：

```text
mission_id
```

那就可能发生：

> 人审核的是 v3，最终系统却把这个批准应用到 v4。

所以 Review 保存：

```text
subject_version
subject_digest
```

并要求第一次决定必须匹配。

------

# 4. 30 秒项目回答

> Stage8 里我没有直接拿一次 Agent Run 表示整个 Feature 测试流程，因为实际测试流程会跨人工审批、远程执行，生命周期可能是几小时甚至几天，而 Runtime Run 本身是有 Deadline 和 Budget 的短生命周期执行。所以我在业务层增加了 `FeatureTestMission`，由它管理业务生命周期，一个 Mission 可以关联多个短 Run。人工审核也没有复用 Tool Approval，而是做了独立的 Business Review，因为一个审核的是业务版本，一个审核的是具体高风险 Tool Invocation。Mission 状态推进和 Review decision 都落 PostgreSQL，用 version CAS 和 first-wins 防并发冲突。

------

# 5. 2 分钟项目回答

> Stage8 开始做真实测试工程业务闭环以后，我首先处理的是业务生命周期和 Runtime 生命周期的边界。
>
> 原来的 AgentCore Run 是一次有 Deadline、Budget 和 Terminal State 的短生命周期智能执行，但 Feature 测试不是这样。一个 Feature 从风险分析、Test Plan、人工审核，到远程测试和 Failure Triage，可能跨几天。如果直接扩 `AgentStateMachine`，Runtime 就会开始承担测试业务状态，而且为了等人审批或者远程执行，一个 Run 可能挂几个小时。
>
> 所以我增加了一个业务级的 `FeatureTestMission`。Mission 由 Stage8 Application Service 和 PostgreSQL 持有，一个 Mission 可以关联多个 Run，但只保存 `run_id` 引用，不控制 Run lifecycle。比如 Risk Analysis 是一个 Run，Test Planning 是另一个 Run，远程执行结束以后再触发新的 Triage Run。
>
> 第二个边界是 Business Review。原系统已经有 Durable HITL，但它是 Tool Approval，批准的是一个具体的 ToolInvocation，涉及风险、Invocation Binding 和 Side-effect Execution Claim。Test Plan Review 不是这个语义，所以我没有强行复用，而是增加独立的 Business Review Domain。
>
> 两者会共享一些工程方法，比如 CAS、first-wins、幂等 decision 和 digest binding。Mission transition 用 `mission_id + expected_version` 做数据库条件更新，Review 对并发 decision 使用 row lock 和 `PENDING` 条件，保证两个冲突决定只能有一个成功。
>
> Review 还绑定 `subject_version` 和 `subject_digest`，避免用户审核旧版 Test Plan，却把审批结果应用到了新版内容。这个地方审计时实际上发现了一个 Bug：原实现调用方不传 binding 时能绕过检查，后来已经修掉，并补了 PostgreSQL 并发测试和最小认证 HTTP E2E。

这个回答里面最后那个 Bug 非常值得讲，因为它是真实工程过程中发现并修复的，而不是为了面试虚构。该缺口和修复均被 Final Gate 明确记录。

------

# 6. 高频追问 + 简答

## Mission 和 Workflow 有什么区别？

Mission 是**业务事实和生命周期对象**。

Workflow 更偏：

```text
怎么执行步骤
```

Mission 表示：

```text
这个 Feature Testing Process 当前实际处于什么状态
```

我们当前没有引入通用 Workflow Engine。

------

## Mission 和 Job 有什么区别？

Job 通常表示：

```text
某个需要执行的后台任务
```

Mission 是更高层：

```text
Mission
├─ Agent Run
├─ Human Review
├─ Execution Job
├─ Agent Run
└─ CI analysis
```

一个 Mission 可以包含多个 Job。

------

## 为什么不用 EvaluationJob 直接实现 Mission？

现有 EvaluationJob 的 Domain 是：

```text
Evaluation
```

状态和 payload 都围绕 Evaluation 定义。

虽然它证明 PostgreSQL Job + Worker 模式已经存在，但不应该为了省几个类把测试业务硬塞进 Evaluation Domain。

复用的是模式，不是 Domain。

------

## Mission Run Reference 为什么不直接 FK 到 Runtime Run 表？

核心要求是：

> Mission 只依赖稳定的 Run Identity，而不是控制 Runtime 生命周期。

是否使用数据库 FK 是 persistence design 问题，最重要的是不能让 Stage8 变成 Runtime Run Owner。

WP0 真实边界就是只保存引用。

------

## 为什么用乐观锁，不用悲观锁？

Mission 修改不是超高冲突业务。

大部分请求：

```text
读 → 判断 → 修改
```

冲突概率低。

用 version CAS：

- 实现简单；
- 无长期锁；
- 易于 HTTP 暴露 stale conflict；
- 足够解决 lost update。

Review decision 因为 first-wins 语义更直接，所以采用 row lock + status condition 也合理。

------

## first-wins 是否等于 exactly-once？

不是。

First-wins 是：

> 多个竞争 decision 中只有第一个成为最终事实。

Exactly-once 更关注：

> 一个操作在故障、重试等情况下不能重复产生业务副作用。

WP0 Business Review 主要是 first-wins + idempotent decision。

------

## 为什么 Runtime Event Journal 不能存 Mission？

因为 Journal 的 Truth 是：

```text
Runtime Run execution evidence
```

例如：

```text
step started
tool called
run terminal
```

Mission 的 Truth 是：

```text
Test Plan reviewed
remote execution pending
failure triage completed
```

虽然都叫状态/事件，但 Domain 完全不同。

------

## 为什么 RAG / Memory 不能保存 Mission state？

因为 RAG 和 Memory 是上下文系统，不是业务 Authority。

它们可以告诉 Agent：

```text
历史上 F123 类似 Feature 容易出什么问题
```

但不能决定：

```text
Mission 当前是不是 APPROVED
```

------

## 为什么 Review 要同时有 version 和 digest？

Version 更适合业务并发控制：

```text
v3 → v4
```

Digest 更适合绑定具体内容：

```text
SHA(...)
```

两者一起能表达：

> 我批准的是这个版本里的这份具体内容。

------

## 如果 approve 请求重复了怎么办？

相同决定：

```text
APPROVE → APPROVE
```

幂等。

冲突决定：

```text
APPROVE → REJECT
```

拒绝。

------

## Review 是不是 HITL？

广义上当然属于人类在环（Human-in-the-Loop, HITL）。

但工程 Domain 要区分：

```text
Runtime Tool HITL
```

和：

```text
Business Workflow Review
```

不能因为都有人点按钮，就共享同一套状态模型。

------

# 7. Bad Case

## Real Bad Case 1 — Stale Review Binding Bypass

这是本 WP 的真实 Bug。

最初 Review 已经保存：

```text
subject_version = 3
subject_digest = abc
```

但 `_decide()` 的逻辑只在调用者主动提交 binding 时才检查。

于是可能：

```text
Review:
    v3 / abc

Client:
    approve(
        review_id=R1
        // 不提交 version
        // 不提交 digest
    )
```

绕过绑定校验。

危险在于未来：

```text
Test Plan v3
→ 创建 Review

Test Plan 更新到 v4

调用者不传 subject binding
→ APPROVE
```

这就破坏了：

```text
Human reviewed content
==
Actually approved content
```

Sol 审计后修成：

> PENDING Review 只要已经保存 binding，第一次 approve/reject 必须提交完全一致的 `(subject_version, subject_digest)`。

缺失也算冲突。

这个 Bad Case 面试价值很高。

------

## Real Bad Case 2 — Concurrent Conflicting Review

场景：

```text
Reviewer A → APPROVE
Reviewer B → REJECT
```

同时请求。

如果只是：

```python
review = get_review()

if review.status == PENDING:
    review.status = decision
```

两个请求可能都读取：

```text
PENDING
```

最终后提交的覆盖前提交的。

WP0 使用：

```text
row lock
+
UPDATE requires status=PENDING
```

确保：

```text
exactly one winner
```

并且真实 PostgreSQL 双事务测试已经验证该核心语义。

------

## Hypothetical Bad Case — Mission 与 Run 混为一体

假设把：

```text
Mission = Agent Run
```

则 Remote Execution 开始后：

```text
Run → 等 4 小时
```

期间：

- Deadline 可能超时；
- Runtime resource 一直占着；
- Approval 生命周期复杂；
- Recovery 必须理解业务状态；
- Worker restart 后很难判断是在“执行 Agent”还是“等外部测试”。

这也是为什么 Mission 必须位于 Runtime 上层。

这是设计推演，没有在 WP0 中真实触发，属于 **Hypothetical**。

------

# 8. Truth / Owner / Completion Boundary

这是面试最需要讲清楚的一部分。

## Mission Truth

```text
stage8_feature_test_missions
```

Owner：

```text
Stage8 Application Service
```

负责：

```text
Feature Testing business lifecycle
Mission transition
Mission version
```

真实 Final Gate 已确认 Mission lifecycle truth 由 Stage8 Application Service 事务推进。

------

## Run Truth

仍然属于：

```text
AgentCore Runtime
RunCoordinator
AgentStateMachine
```

Stage8：

```text
只保存 run_id reference
```

不负责：

```text
Run start
Run terminal
Run state recovery
Runtime Journal
```

------

## Business Review Truth

```text
stage8_business_reviews
```

Owner：

```text
BusinessReviewService
```

负责：

```text
PENDING
APPROVED
REJECTED

subject binding
decision actor
first-wins
idempotency
```

------

## Tool Approval Truth

仍然属于：

```text
ToolApprovalController
DurableApprovalService
```

WP0 没修改。

Business Review：

```text
!= Tool Approval
```

------

## Transaction Truth

```text
Application Service
```

拥有 transaction。

Repository 只接受已有 session 并完成 persistence operation。

------

## PostgreSQL

真实实现：

```text
stage8_feature_test_missions
stage8_mission_run_refs
stage8_business_reviews
```

Migration：

```text
0011_stage8_mission
```

且已经在测试 PostgreSQL 的空 schema 上实际执行 `alembic upgrade head` 成功。

------

## WP0 真正完成了什么

已真实实现：

```text
FeatureTestMission
Mission State Transition
Mission version CAS
Mission ↔ Run Reference

BusinessReview
Review first-wins
Review idempotency
Subject version/digest binding

PostgreSQL persistence
Alembic migration

Typed Stage8 HTTP API
Existing Auth / Rate Limit reuse
Existing Composition Root reuse
```

测试：

```text
5 passed
```

包括最小真实 PostgreSQL 并发决定测试和认证 ASGI E2E。

------

## WP0 没完成什么

没有：

```text
Risk Analysis
Test Planning
Case Engineering
Remote Execution
Failure Triage
CI Guardian
Web UI
```

这不是缺陷，而是明确的 Completion Boundary。

另外当前 Business Review 虽然已经保存并严格匹配 `subject_version / digest`，但 Test Plan / Case 等真正 Subject Aggregate 还没实现，所以现在不会反查这些尚不存在的 Repository。这是明确的后续范围。

------

## 本 WP 最应该记住的三句话

第一句：

> **Mission 管业务生命周期，Run 管一次有界智能执行。**

第二句：

> **Business Review 和 Tool Approval 都有人类确认，但批准的对象和 Authority 不同，所以不能共用一个 Domain。**

第三句：

> **并发正确性尽量交给数据库做：Mission 用 version CAS，Review 用 first-wins + subject binding，而不是依赖应用层“先查再改”。**

这三个点基本就是 WP0 面试价值的核心。