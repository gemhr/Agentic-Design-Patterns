# LocalAgent Stage 2.5 — Multi-Agent Runtime 学习 / 面试总结

**推荐文件名：**

```text
stage2_5_multi_agent_runtime_interview_notes.md
```

------

# 1. 这一阶段到底解决了什么问题

Stage 2.5 不是“给项目加几个 Agent”。

它真正解决的问题是：

> Stage 2 的 Coordinated Runtime 已经成为默认执行入口，但旧版多 Agent 编排没有完整迁移，导致系统虽然叫 Multi-Agent，真实请求却可能一直由 `core_router` 自己回答。

因此 Stage 2.5 的目标是把：

```text
用户请求
-> core_router
-> 偶尔委派
```

升级为真正受 Runtime 管理的：

```text
用户请求
-> PlanResolver
-> PlanCompiler
-> Frozen Plan
-> Scheduler
-> Specialist Agent
-> StepResultStore
-> Synthesis
-> OutputGate
-> Atomic Memory
-> Trace / Journal / Frontend
-> Run terminal
```

最终 Stage 2.5 已通过正式 RC Gate：

```text
P0 = 0
P1 = 0
P2 = 1

Required RC scenarios = 54/54 PASS
Full repository = 1412 passed + 42 subtests
Stability = 20/20 PASS
RC Gate = PASS
```

唯一接受的 P2 是 Planning 与 specialist 共用 bounded executor 时的容量饥饿风险。

------

# 2. 名词 / 概念速览

## Coordinated Runtime（协调式运行时）

由 Runtime 统一管理 Planning、调度、并发、状态、错误、交付和生命周期，而不是让 Agent 自己随意调用其他 Agent。

## PlanResolver（计划解析器）

决定一次请求采用 direct answer、单 specialist 还是 multi-agent execution，并输出合法的执行计划。

## PlanCompiler（计划编译器）

把 Planner 返回的不可信 typed decision 编译成 Runtime 允许执行的有限图结构。

## Frozen Plan（冻结计划）

Plan 一旦进入执行阶段不可修改，避免执行过程中 Planner 或 Agent 动态改变图结构。

## AgentRegistry（智能体注册表）

保存 Agent 身份、能力、入口权限、委派权限和 execution adapter identity，是 Agent capability authority。

## InvocationRole（调用角色）

区分：

```text
ENTRY
DELEGATED
SYNTHESIS
```

并进一步决定 HistoryPolicy。

## HistoryPolicy（历史读取策略）

```text
AGENT_SCOPE
NONE
```

ENTRY 可以读取原有 direct conversation history；delegated specialist 和 synthesis 禁止读取旧 Agent Memory。

## Scheduler（调度器）

决定哪个 Step 已满足依赖并获得执行 claim。

## StepClaim（步骤执行授权）

Runtime 中真正允许执行一个 Step 的凭证；Driver 不能自行扫描 Plan 然后执行。

## StepResult（步骤结果）

专业 Agent 输出的 typed Runtime object，而不是随意传递的字符串。

## StepResultStore（步骤结果存储）

Run-scoped 内存 Store，负责：

```text
PREPARED
-> READABLE
```

以及 once-write、dependency ACL、容量限制等。

## Synthesis Agent（综合智能体）

专门负责聚合多个 specialist 的结果，不能直接被用户选择。

## OutputGate（输出闸门）

整个 Run 唯一拥有最终正文发布权的组件。

状态：

```text
NOT_STARTED
-> PUBLISHING
-> PUBLISHED | FAILED | OUTCOME_UNKNOWN
```

## DeliveryStatus（交付状态）

```text
NOT_APPLICABLE
DELIVERED
FAILED
OUTCOME_UNKNOWN
```

它与 Agent Step 是否成功是两个不同维度。

## Journal-first（先日志后发送）

Runtime Event 先写 Journal，再进入 EventChannel：

```text
journal append
-> enqueue
```

这样即便发送阶段失败，也能保留已经发生过什么的事实。

## Trace Contract v1（追踪合同）

Stage 2.5 正式冻结了六类 Span：

```text
runtime.run
runtime.planning
runtime.step
runtime.synthesis
runtime.output_delivery
runtime.final_memory_commit
```

## Recovery Validation（恢复验证）

当前 Recovery 只判断历史 Run 是否安全、是否需要人工 reconciliation，不真正恢复执行。

------

# 3. 最重要的架构思想：Runtime 才是 Owner

Stage 2.5 最核心的一条学习不是“怎么调用多个 Agent”，而是：

> Multi-Agent 系统最难的不是 Agent，而是 Ownership。

------

## 3.1 RunCoordinator 是 Run 生命周期 Owner

不能让：

- Agent；
- Scheduler；
- Driver；
- OutputGate；
- ChatService；

任何一个模块自己决定 Run 最终结果。

最终设计：

```text
RunCoordinator
    owns
Planning
Execution batches
Delivery decision
Run terminal
Cleanup
```

这样能够避免：

```text
Agent认为成功
Delivery认为失败
Coordinator又认为成功
```

这样的多事实源冲突。

------

## 3.2 AgentState 是运行状态 Single Source of Truth

一个非常典型的 Bad Case 是：

```text
PlanStep.status = RUNNING
AgentState.step_status = SUCCEEDED
```

这会产生状态双写。

最终原则：

```text
Plan
= 静态执行合同

AgentState
= 动态运行状态
```

Plan 不记录：

- status；
- start time；
- completion time；
- runtime retry state。

这是 Single Source of Truth（单一事实来源）的典型工程实践。

------

# 4. 为什么 Planner 不能直接生成执行图

看起来最自然的实现是：

> 让大模型直接生成 DAG，然后 Runtime 执行。

Stage 2.5 明确否决了这个方案。

因为 Planner 是不可信输入源。

如果 Planner 可以生成：

```text
agent
dependencies
callable
output_policy
runtime_state
retry_policy
```

那么实际上：

> LLM 已经变成 Runtime Authority。

这是危险的。

最终架构是：

```text
Planner
-> typed decision

Compiler
-> validate Registry
-> validate capability
-> compile one of legal shapes
```

只支持：

```text
Shape 0
core_router -> final

Shape 1
specialist -> final

Shape 2
specialist -> synthesis

Shape 3
N specialists -> synthesis
```

Planner 没有权创造第五种拓扑。

------

# 5. 为什么要把 instruction 从 Plan 中拿出去

早期一个容易出现的设计是：

```python
PlanStep(
    instruction="分析 D:\\xxx\\secret.csv ..."
)
```

然后 Plan 进入：

- Snapshot；
- fingerprint；
- Trace；
- Journal；
- Debug log。

这会产生数据泄漏。

最终：

```text
Plan
= safe execution metadata

StepInvocationBindings
= raw instruction
```

Bindings：

- run-scoped；
- memory-only；
- read-only；
- no persistence；
- no recovery；
- Run结束立即clear。

这是非常典型的：

> Control Plane metadata 与 Data Plane content 分离。

------

# 6. Multi-Agent 真正是如何并行的

Stage 2.5 不是：

```python
for agent in agents:
    agent.run()
```

Scheduler 会同时 claim independent steps。

Shape 3：

```text
knowledge_expert ──┐
                   ├─> synthesis
code_expert ───────┤
                   │
data_analyst ──────┘
```

测试没有只看：

```text
总时间变短了
```

而是使用：

- `threading.Barrier`
- active counter
- enter/exit ordering

证明两个 specialist 的真实执行区间发生重叠。

这是面试里很好的一点：

> 并发测试不要依赖 wall-clock timing，应该使用 deterministic synchronization primitive。

------

# 7. StepResultStore 为什么不能只是 dict

一个简单方案：

```python
results[step_id] = result
```

实际上远远不够。

最终 Store 支持：

```text
Entry:
PREPARED -> READABLE

Store:
OPEN -> SEALED -> CLEARED
```

并且：

- once-write；
- producer identity validation；
- result size limit；
- run total size limit；
- dependency ACL；
- Store lifecycle；
- late write rejection；
- no get_all。

其中最关键的是：

> Synthesis 不能看到整个 Store。

例如：

```text
Synthesis depends_on:
A
B
```

那么只能读：

```text
A
B
```

不能读取：

```text
C
D
```

即使 C、D 已经执行完成。

这其实是在 Agent Runtime 内实现了一层最小的：

> Information Flow Control（信息流控制）。

------

# 8. 为什么 Synthesis 不允许 partial result fallback

假设两个专家：

```text
knowledge_expert -> success
code_expert -> failed
```

最简单的产品体验可能是：

> 用 knowledge 的结果先回答。

Stage 2.5 没这么做。

因为 dependencies 当前都是 required。

因此：

```text
required dependency failed
-> synthesis BLOCKED
-> synthesis model call = 0
-> no partial final
```

原因：

1. 用户以为这是完整回答；
2. Synthesis 缺失信息时可能 hallucinate；
3. Runtime 很难判断某个依赖是否“可选”。

所以 optional edge 和 graceful degradation 被明确留到未来，而不是偷偷实现。

------

# 9. HistoryPolicy 修复是一个非常好的 Bad Case

WP3 最开始已经设置：

```text
persist=False
```

大家很容易以为：

> specialist 已经不会碰 Memory。

但源码审计发现：

```text
persist=False
```

只控制：

> 写 Memory。

并没有控制：

> 读 Memory。

因此 delegated specialist 仍可能读取：

```text
以前 Run 的 agent history
rolling summary
```

这会产生隐藏上下文污染。

最终拆成两个正交维度：

```text
HistoryPolicy
= 是否读取历史

persist
= 是否写入历史
```

调用关系：

```text
ENTRY
-> AGENT_SCOPE
-> persist=False

DELEGATED
-> NONE
-> persist=False

SYNTHESIS
-> NONE
-> persist=False
```

这体现一个非常重要的工程思想：

> Read policy 和 Write policy 不应该通过一个 bool 隐式表达。

------

# 10. Final Output 是 Stage 2.5 最值得讲的设计之一

多 Agent 系统最大的风险之一是：

```text
specialist A 输出
specialist B 输出
synthesis 又输出
```

导致用户看到多个“final”。

因此最终引入：

# OutputGate

它是 Run-level singleton owner。

状态：

```text
NOT_STARTED
    |
    v
PUBLISHING
    |
    +--> PUBLISHED
    |
    +--> FAILED
    |
    +--> OUTCOME_UNKNOWN
```

只有唯一 final Step 才能使用。

任何状态一旦离开 `NOT_STARTED`：

> 永远不能第二次 publish。

包括 `FAILED`。

原因是设计保证的是：

```text
at-most-once publish attempt
```

而不是：

```text
retry until success
```

------

# 11. 为什么 FAILED 和 OUTCOME_UNKNOWN 必须区分

EventChannel 是：

```text
Journal
-> Channel
```

情况一：

```text
Journal append失败
```

可以确定：

```text
正文没有进入持久事实
```

所以：

```text
Delivery = FAILED
```

情况二：

```text
Journal append成功
Channel enqueue失败
```

只能确定：

```text
OUTPUT已经发生过持久记录
```

但无法确定消费者是否已经看见。

所以：

```text
Delivery = OUTCOME_UNKNOWN
```

不能自动 retry。

这是分布式系统非常经典的：

> Uncertain Outcome（结果不确定性）。

------

# 12. 为什么 Final Step 成功不代表 Run 成功

例如：

```text
Synthesis model success
StepResult valid
Store READABLE
```

说明：

```text
Final Step = SUCCEEDED
```

然后：

```text
Output delivery失败
```

最终必须是：

```text
Final Step = SUCCEEDED
Delivery = FAILED
Run = FAILED
```

而不是：

```text
Final Step = FAILED
```

否则就无法回答：

> 到底是模型执行失败，还是用户交付失败？

同样：

```text
Final Step = SUCCEEDED
Delivery = DELIVERED
Memory = FAILED
Run = FAILED
```

表示：

> 用户回答已经成功生成并发送，只是 Memory 保存失败。

这就是 Execution / Delivery / Persistence 三层事实分离。

------

# 13. Journal-first 的 sequence Bad Case

有一个很典型的问题：

```text
OUTPUT step_sequence=2
Journal成功
enqueue失败
```

如果本地 Emitter 只在 enqueue 成功后：

```python
sequence += 1
```

那么接下来：

```text
STEP_COMPLETED
```

也会使用：

```text
sequence=2
```

Journal 里就出现两个相同 sequence。

最终规则：

```text
如果 partially_persisted=True
即使 publish抛异常
也要消费 local sequence
```

最终：

```text
STEP_STARTED  = 1
OUTPUT        = 2  # journaled
STEP_COMPLETED= 3
```

这是一个很典型的：

> 本地状态必须与 durable fact 对齐，而不是只与 API return value 对齐。

------

# 14. Memory 为什么必须原子提交

WP4 初版：

```text
write(user)
write(assistant)
```

如果：

```text
user成功
assistant失败
```

历史里会留下：

```text
只有user，没有assistant
```

下一轮模型读取 Memory 后会以为上一轮用户的问题没有被回答。

WP5 最终新增：

```text
append_exchange_atomic
```

把：

```text
user
assistant
```

放在一个 SQLite transaction。

同时增加：

```text
exchange_id
run_id
```

实现幂等约束。

结果：

```text
两条都成功
OR
两条都不存在
```

历史读取只读取：

```text
legacy message
或
COMMITTED exchange
```

这是标准的 Atomicity（原子性）设计。

------

# 15. Trace Contract 为什么值得讲

Stage 2.5 没有简单地“加日志”。

而是冻结了一套可供未来 AgentEvalOps 消费的 Trace schema：

```text
runtime.run
runtime.planning
runtime.step
runtime.synthesis
runtime.output_delivery
runtime.final_memory_commit
```

Shape 3：

```text
Run
├── Specialist A
├── Specialist B
├── Specialist C
└── Synthesis
      └── Output Delivery
          └── Final Memory Commit
```

几个 specialist 是 sibling，而不是：

```text
A
└── B
    └── C
```

因为它们是真实并行，不存在调用父子关系。

Trace 只能记录：

```text
status
duration
agent_id
execution_kind
result_length
delivery_status
error_code
version metadata
```

不能记录：

```text
Prompt
instruction
result正文
final正文
exception raw
private path
```

这体现：

> Observability 不能因为“便于排查”而破坏数据安全边界。

------

# 16. Recovery 为什么故意不做自动 Resume

这是一个很容易被面试官追问的问题：

> 你都有 Snapshot / Journal 了，为什么不直接恢复执行？

答案是：

因为以下数据没有持久化：

```text
StepInvocationBindings
StepResultStore
OutputGate
raw final
```

那么恢复一个运行中的 multi-agent Run 会存在严重的不确定性。

尤其：

```text
OUTPUT已经journaled
但没有terminal
```

不能判断：

> 用户是否看见。

因此 Recovery 做的是：

```text
Validation
```

而不是：

```text
Replay / Resume
```

结果：

```text
TERMINAL
UNSUPPORTED
REQUIRES_RECONCILIATION
CORRUPTED
...
```

而且 RecoveryValidator 根本没有：

```text
send_output()
write_memory()
```

这种能力。

这是一个很好的 Principle of Least Authority（最小权限原则）设计。

------

# 17. Planning Starvation 是怎样发现的

WP6 做压力测试时发现：

```text
blocking executor被占满
-> Planning尝试submit
-> submit admission同步等待
-> asyncio event loop被阻塞
-> cancel/disconnect无法执行
```

这个问题最开始已经接近 P1：

> cancellation无法收敛。

最终最小修复：

```python
await asyncio.to_thread(executor.submit, ...)
```

重点不是 `to_thread` 本身。

重点是：

> 把可能等待的同步 admission 从 event loop 挪走。

同时没有：

- 增加 worker；
- 增大 timeout；
- 创建第二业务executor。

修复后：

- cancellation收敛；
- deadline分类正确；
- pending有界；
  -释放资源后恢复。

剩下的是容量性能风险，所以降为：

```text
ACCEPTED_P2
```

------

# 18. 工程构建方法类高频面试题

## Q1：为什么 Multi-Agent 不能直接让 Agent 相互调用？

因为这样调用拓扑、状态、timeout、budget、cancellation 和 side effect owner 会分散到各 Agent 中，很难形成统一 Runtime Contract。

我的项目中采用：

```text
Planner
-> Compiler
-> Scheduler
-> Driver
```

Agent 本身只是执行节点。

------

## Q2：为什么需要 PlanCompiler？

Planner 是模型输出，不能被直接视为可信执行合同。

Compiler承担：

- Agent Registry校验；
- capability校验；
- dependency校验；
- graph shape校验；
- output policy生成。

属于 Trust Boundary（信任边界）。

------

## Q3：为什么 Plan 不保存运行状态？

因为 Plan 是 immutable execution definition。

运行状态由 AgentState管理。

否则 Plan和AgentState会双写形成状态冲突。

------

## Q4：为什么 specialist结果要先进Store？

因为需要：

- once-write；
- lifecycle；
- size limit；
- ACL；
- dependency readiness；
- synthesis input控制。

直接 `dict[agent] = output` 无法满足这些Runtime约束。

------

## Q5：为什么不能 partial synthesis？

当前 dependency contract全部是required。

如果缺一个结果仍然synthesis，就无法区分：

```text
真正完整结果
vs
降级结果
```

因此当前 fail closed。

未来若支持optional edge，需要在Plan Contract中显式表达。

------

## Q6：为什么 Final Output 要单独一个Gate？

因为 multi-agent中多个Step可能成功。

Step success不应该自动意味着：

> 可以向用户输出。

OutputGate负责唯一final source和at-most-once publish attempt。

------

## Q7：为什么delivery unknown不重试？

因为journal-first情况下：

```text
Journal成功
enqueue失败
```

只能知道系统已经产生过output事实，无法知道用户有没有收到。

重试可能产生重复回答。

------

## Q8：为什么Memory要在DELIVERED后写？

如果模型生成成功但output没有成功交付，却先写Memory：

下一轮模型会认为：

> 用户已经收到那个回答。

这会造成conversation history与真实UX不一致。

因此：

```text
Delivery
-> Memory
```

------

## Q9：为什么Recovery不自动恢复？

因为无法恢复：

```text
Bindings
StepResult
OutputGate state
```

而且无法确定已journaled output是否被用户看到。

自动恢复反而可能造成重复side effect和重复output。

------

## Q10：为什么不用一个巨型 RuntimeContext 保存所有东西？

因为不同对象有不同生命周期和权限：

```text
RunContext
AgentState
Plan
Bindings
Store
OutputGate
```

如果全部塞在一个Context，会导致任何组件都能访问所有数据和状态，Ownership失控。

------

# 19. 高频追问：如何证明是真的多 Agent

不能只说：

> 有四个Agent类。

应该回答：

> Planner可以编译出多个独立 specialist Step，Scheduler同时claim它们，ParallelExecutor以bounded concurrency执行，结果分别写入StepResultStore，Synthesis只有在全部required dependency READABLE后才执行。

测试方面：

> 我没有用总耗时判断并行，而用了threading.Barrier、active worker counter和事件先后关系证明执行区间真实重叠。

这个回答的工程可信度会高很多。

------

# 20. 高频追问：你这个系统是不是 exactly-once？

不能回答“是”。

正确回答：

> 不是。Stage 2.5明确只保证Runtime内final output的at-most-once publish attempt。

因为：

```text
Journal成功
enqueue失败
```

会产生：

```text
OUTCOME_UNKNOWN
```

无法证明consumer究竟有没有看到正文。

因此系统不会自动重试。

------

# 21. 高频追问：你的 Multi-Agent 能无限扩Agent吗

不能说“任意多 Agent”。

当前真实边界：

- Registry固定；
- Compiler限制图形；
  -资源限制；
- concurrency budget；
  -当前只支持Shape 0～3；
  -required dependencies。

正确表达：

> Runtime架构支持N个独立specialist fan-out，但实际N受Registry、Compiler和资源策略限制，不是无界动态Agent网络。

------

# 22. 高频追问：你们做 Durable Execution 了吗

没有。

可以回答：

> 我实现了Snapshot、Journal和Recovery Validation，但没有宣称完整Durable Resume。

因为：

```text
Bindings
Store
Gate
```

都不是durable state。

Recovery采取fail-closed和reconciliation策略。

这个回答比硬说“支持断点恢复”更真实。

------

# 23. Stage 2.5 真实 Bad Cases

## Bad Case 1：Plan 与 AgentState双写状态

风险：

```text
Plan says RUNNING
AgentState says SUCCEEDED
```

修复：

> Plan静态，AgentState唯一动态状态源。

------

## Bad Case 2：Planner直接控制执行图

风险：

> LLM变成Runtime Authority。

修复：

```text
Planner typed decision
-> Compiler legal shape
```

------

## Bad Case 3：persist=False 但仍读取旧Memory

这是实际源码审计发现的问题。

根因：

> persist只控制写。

修复：

```text
HistoryPolicy.NONE
+
persist=False
```

------

## Bad Case 4：Store默认resource key导致假并行

WP3实施中出现过：

两个 specialist虽然调度并发，但被相同 resource key 的 limit=1 串行化。

修复后：

> typed Step使用独立resource key，同时保留Run级max concurrency。

------

## Bad Case 5：Journal成功但Emitter sequence未消费

结果：

> 两个事件可能使用相同step sequence。

修复：

> partially_persisted异常同样消费sequence。

------

## Bad Case 6：Memory user成功、assistant失败

风险：

> 半条conversation history。

修复：

```text
append_exchange_atomic
```

------

## Bad Case 7：Planning等待executor阻塞event loop

WP6真实测试发现。

风险：

> cancel无法传播，Run可能长期无法收敛。

修复：

> admission wait放到`asyncio.to_thread`。

------

## Bad Case 8：CSV请求出现 INVALID_CAPABILITY

Stage 2.5冻结之后真实复现：

```text
查数据库，mock_test_results.csv这个表的第四列的表头是什么
```

Planner model执行成功，但之后：

```text
INVALID_CAPABILITY
PLANNING_FAILED
```

没有：

```text
PLAN_CREATED
STEP_STARTED
```

当前只能确认：

> capability validation失败。

尚未确认Planner实际输出的capability，因此具体根因没有完全验证。

曾讨论：

- CSV deterministic route；
- capability白名单；
- ResourceKind / OperationKind / Capability分离；

但这些 **尚未实现**。

这是进入Stage 3时可以关注的真实Production Gap，但不能当作Stage 2.5已完成能力。

------

# 24. 30秒面试总结

> 我在LocalAgent里完成了一次从单Agent Runtime到生产级多Agent Runtime的升级。核心不是简单增加多个Agent，而是把Planning、Plan编译、Scheduler、Agent Registry、并行specialist、StepResultStore、Synthesis和Final Output全部纳入统一Runtime管理。我通过OutputGate保证一次Run只有一个最终输出，并把Agent执行成功、消息交付和Memory持久化拆成独立状态；同时建立了Journal-first事件、Trace Contract、原子Memory和fail-closed Recovery。最终做了54个RC场景和故障注入验收，全仓1412个测试通过。

------

# 25. 2分钟面试总结

> Stage 2.5主要解决的是我们把默认入口迁移到Coordinated Runtime之后，多Agent能力反而退化的问题。我的处理方式不是让core router继续手工delegate，而是在Runtime层建立正式的Planning和Execution Contract。
>
> 请求首先进入PlanResolver，Planner只返回typed decision，PlanCompiler会根据AgentRegistry把它限制成四种合法执行图，然后freeze。Scheduler拥有唯一的Step claim权，多个独立specialist可以真实并行执行。我用了barrier和active counter测试来证明它们的执行区间确实重叠。
>
> Specialist结果不会直接输出，而是进入run-scoped StepResultStore。Store有PREPARED/READABLE状态、once-write、容量限制和dependency ACL，Synthesis只能读取自己的显式依赖。
>
> 最终输出又单独设计了Run级OutputGate，因为Step执行成功并不等于消息成功送到用户。Gate只保证at-most-once publish attempt，并且把DELIVERED、FAILED和OUTCOME_UNKNOWN分开。比如Journal成功但channel enqueue失败时，我不会自动重试，因为无法确定用户是否已经看见回答。
>
> Memory也是在确认DELIVERED后才保存，而且user和assistant用同一个SQLite事务原子提交。
>
> 可观测方面冻结了Trace Contract v1，区分run、planning、step、synthesis、delivery和memory span，同时Journal不保存raw output。Recovery采取read-only fail-closed设计，不自动重发final或重写Memory。
>
> 最终做了54个RC场景、30个必选故障点和完整安全矩阵，全仓1412个测试通过，RC Gate通过。唯一保留的P2是Planning和specialist共享bounded executor产生的容量饥饿风险。

------

# 26. Truth / Completion Boundary

面试时可以明确说“已经实现”的：

- Dynamic Multi-Agent Planning；
- Registry + Compiler；
- Frozen Plan；
  -真实并行 specialist；
- StepResultStore；
- dependency ACL；
- Synthesis；
- History isolation；
- OutputGate；
- at-most-once publish attempt；
- DeliveryStatus；
- atomic final Memory；
- Trace Contract v1；
- Journal safe projection；
- Frontend runtime status；
- Recovery no-redelivery/no-recommit；
- Fault Injection；
- RC Gate。

不能声称：

- distributed exactly-once；
- arbitrary DAG；
- unlimited multi-agent；
- optional dependencies；
- partial result degradation；
- full durable execution resume；
- dynamic Agent registration；
- recursive Agent delegation；
- all fault scenarios have production injection seams；
- AgentEvalOps已经正式接入；
- `INVALID_CAPABILITY` CSV问题已经修复。

------

# 27. Stage 2.5 最值得继续深入学习的关键词

如果准备面试，我建议优先继续深入：

```text
Single Source of Truth
Ownership
State Machine
Immutable Plan
Capability-based Routing
Scheduler / Claim
Fan-out / Fan-in
Structured Concurrency
Dependency DAG
Information Flow Control
Idempotency
At-most-once
Exactly-once impossibility
Uncertain Outcome
Journal-first / Write-ahead semantics
Atomic Transaction
Recovery Reconciliation
Fail Closed
Backpressure
Bounded Executor
Starvation
Cancellation Propagation
Trace Context
Span Topology
High-cardinality Metrics
Control Plane vs Data Plane
```

其中最值得优先掌握的是：

```text
1. Ownership / Single Source of Truth
2. At-most-once 与 uncertain outcome
3. 并发 + cancellation + backpressure
4. Journal / Event / Recovery
5. Synthesis 与 dependency isolation
6. Runtime 与 Agent职责边界
```

这些已经不只是“Agent八股”，而是典型的 Runtime、分布式系统和生产工程问题。

------

# 28. 整个 Stage 2.5 最核心的学习结论

如果只记住一句话：

> 多 Agent 的核心难点不是“怎么让多个模型互相调用”，而是如何让一个 Runtime 在并发、不确定性、失败、重试、状态持久化和数据安全条件下，仍然只有一个明确的 Owner 和一套一致的事实。

Stage 2.5 真正做出来的就是这件事。