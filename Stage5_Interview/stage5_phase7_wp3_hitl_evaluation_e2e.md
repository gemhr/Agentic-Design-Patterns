当前使用的模型：**GPT-5.6 Sol**。

# Stage5-Phase7-WP3 学习 / 面试总结

## HITL Evaluation / E2E（HITL 评估 / 端到端验证）

WP3 最终状态：

```text
WP3_FINAL_GATE = PASS_WITH_ACCEPTED_LIMITATIONS

HITL_EVALUATOR = PASS
EVIDENCE_COMPLETENESS_BOUNDARY = PASS
CORRELATION_BOUNDARY = PASS
BAD_CASE_DETECTION = PASS
REAL_LOCALAGENT_EVIDENCE_E2E = PASS
ARTIFACT_TRUTH = PASS
AGENTEVALOPS_AUTHORITY_BOUNDARY = PASS

BLOCKING_P0 = 0
BLOCKING_P1 = 0
ARCHITECTURE_REOPEN_REQUIRED = NO
```

WP3 的核心不是“给 HITL 再加几个测试”，而是把 **LocalAgent Runtime 产生的真实审批证据，变成 AgentEvalOps 可以可信判定 PASS / FAIL / BLOCKED 的 Evaluation Contract（评估合同）**。

------

# 1. 本 WP 解决什么问题

## 1.1 WP1、WP2 已经能跑，为什么还需要 WP3

WP1 已经解决：

```text
高风险 Tool
→ WAITING_FOR_APPROVAL
→ APPROVE / REJECT
→ execution claim
```

WP2 又解决：

```text
Runtime
→ Streaming
→ Human
→ HTTP approve/reject
→ Runtime
```

但到这里仍只能回答：

> “代码看起来支持 HITL。”

还不能系统回答：

> “如何证明审批真的发生在 Tool 副作用之前？”

比如真正危险的问题是：

```text
Tool 是否可能先执行，后补 APPROVED？

REJECT 后是否可能仍然启动 Tool？

重复 APPROVE 是否可能执行两次？

Cancel / Timeout 后是否可能 late approve 再执行？

证据不完整时，系统会不会因为没看到 TOOL_STARTED 就误判安全？
```

WP3 就是把这些问题转化成：

> **Evidence-driven Safety Assertions（证据驱动的安全断言）**

并交给 AgentEvalOps 统一评价。

------

# 2. 真实架构 / 数据流 / 状态流

最终 Owner Boundary（所有权边界）非常明确：

```text
LocalAgent
= Runtime Fact Producer
= Run / Approval / Tool / Side Effect / Journal Owner

AgentEvalOps
= Fact Consumer
= Evaluation Owner
```

AgentEvalOps 不做：

```text
approve
reject
修改 AgentState
恢复 pending
继续执行 Tool
```

它只做：

```text
读取 evidence
→ validate
→ correlate
→ assert
→ PASS / FAIL / BLOCKED
```



完整数据流：

```text
LocalAgent Runtime
      ↓
Journal-first Runtime Events
      ↓
Safe Journal Projection
      ↓
HitlToolApprovalEvidenceV1
      ↓
Correlation
      ↓
Assertions A-F
      ↓
Aggregate
      ↓
PASS / FAIL / BLOCKED
      ↓
Evaluation Artifact
```

这就是 WP3 最关键的架构：

> **Runtime 负责产生事实，Evaluation 系统负责解释事实，但 Evaluation 不能反过来成为 Runtime 状态 Owner。**

------

# 3. 核心设计选择 / 候选方案 / 取舍

## 3.1 为什么不让 AgentEvalOps 直接实时控制 HITL

理论上可以让 AgentEvalOps：

```text
启动 LocalAgent
→ 等待 approval
→ 自动 approve/reject
→ 驱动整个 workflow
```

也就是扩展一个 Interactive ExecutionTarget（交互式执行目标）。

但当前 `ExecutionTarget` 更偏：

```text
request
→ terminal result
```

如果强行加入 interactive lifecycle，就会扩大到：

```text
live session
callback
command routing
pending state
interactive orchestration
```

所以 WP3 选择更轻的路线：

```text
LocalAgent 自己执行真实 HITL
        ↓
产生 Journal evidence
        ↓
AgentEvalOps 离线评价
```

这很好地保持了：

```text
Evaluation
!= Runtime orchestration
```

而 interactive AgentEvalOps HITL driver 被明确放到 Future。

------

## 3.2 为什么不用字符串 grep 日志

错误实现：

```python
if "APPROVED" in logs:
    passed = True
```

这种方法的问题很多：

```text
字符串可能来自错误信息
字段格式改变就失效
无法可靠关联同一个 approval
无法判断 sequence
无法区分多个 Run
无法识别证据是否完整
```

所以 WP3 正式 evaluator 只消费：

> **Typed Evidence（强类型证据）**

包括：

```text
HitlToolApprovalEvidenceV1
HitlRuntimeEventV1
```

并使用 Pydantic strict validation：

```text
extra = forbid
digest format validation
single run_id validation
sequence strictly increasing
```



------

## 3.3 为什么没有复制一套 Approval 状态机到 AgentEvalOps

这是一个很容易犯的架构错误。

比如 AgentEvalOps 再维护：

```text
PENDING
APPROVED
REJECTED
INVALIDATED
```

然后自己重演 Runtime。

这样会形成：

```text
LocalAgent Runtime State Machine

+

AgentEvalOps Evaluation State Machine
```

两套“真相”。

WP3 实际采用的是：

```text
ordered evidence
→ assertions
```

而不是：

```text
replay Runtime state machine
```

这是更好的 Evaluation Architecture。

------

# 4. HITL Evidence Contract（HITL 证据合同）

新增的核心 evidence schema：

```text
HitlToolApprovalEvidenceV1
HitlRuntimeEventV1
```

关键字段包括：

```text
run_id
event sequence
event type

approval_id
invocation_binding_digest
invocation_identity_digest
decision_status

trace_complete
provenance
terminal status
```

证据必须满足：

```text
single run
strictly increasing sequence
typed payload
validated digest
```

否则就不能被当成可信 evaluation evidence。

------

# 5. Correlation（关联）为什么是核心难点

Evaluator 不能只判断：

```text
有没有 APPROVED
有没有 TOOL_STARTED
```

而必须证明：

> 这个 `TOOL_STARTED` 属于这个 Approval。

Approval lifecycle 的主要 correlation：

```text
run_id
+
approval_id
+
invocation_binding_digest
```

但这里有一个真实困难：

```text
TOOL_STARTED
```

目前并不携带：

```text
invocation_binding_digest
```

所以执行事件需要依赖：

```text
invocation_identity_digest
```

来关联。

------

## 5.1 为什么这是一个 Evidence Gap，而不是简单字段问题

Approval binding digest 表示的是更完整的：

```text
invocation
+
args
+
idempotency
+
resource
+
risk
```

而 identity digest 更接近：

```text
invocation identity
```

所以二者能力不同。

WP3 没有为了 evaluator 去修改 LocalAgent Runtime Event Contract，而是在当前证据条件下：

```text
run-scoped identity correlation
```

并且对 Ambiguous Correlation（歧义关联）：

```text
FAIL / fail closed
```

而不是“随便选一个”。

这是非常重要的取舍。

------

# 6. Cross-run Isolation（跨 Run 隔离）

例如：

```text
Run A:
APPROVAL_REQUESTED

Run B:
TOOL_STARTED
```

即使某些 digest 恰好一样：

Run B 的 Tool event 也绝不能证明 Run A 执行了。

所以 evidence envelope 强制：

```text
所有 event.run_id
==
envelope.run_id
```

Foreign Run（其他 Run）event 会直接被拒绝。

这防止了：

> Evaluation False Positive（评估假阳性）。

------

# 7. Cross-approval Isolation（跨审批隔离）

同一个 Run 内也可能有：

```text
Approval A
Approval B
```

Evaluator 不能：

```text
Approval A 的 APPROVED
+
Approval B 的 TOOL_STARTED
=
A PASS
```

所以 WP3 增加了：

```text
HITL_MULTI_APPROVAL_ISOLATION
```

用于验证生命周期隔离。

如果：

```text
一个 invocation_identity_digest
对应多个 approval lifecycle
```

则会记录：

```text
ambiguous_identity_digests
```

并让 correlation assertion FAIL，而不是 first-match。

------

# 8. Assertions A-F

这是 WP3 最核心的知识。

------

## Assertion A — Approval Requested

高风险 scenario 应该观察到：

```text
TOOL_APPROVAL_REQUESTED
```

如果完整 trace 中没有：

```text
FAIL
```

如果 trace 自己都不完整：

```text
BLOCKED
```

核心思想：

> 证据缺失和行为失败是两个不同的问题。

------

## Assertion B — Approval Before Execution

最核心安全不变量：

```text
REQUESTED
<
DECIDED(APPROVED)
<
TOOL_STARTED
```

如果：

```text
TOOL_STARTED sequence = 10
APPROVED sequence = 15
```

则：

```text
FAIL
```

而且 evaluator 会给出类似：

```text
TOOL_STARTED sequence 10 occurred before
TOOL_APPROVAL_DECIDED(APPROVED) sequence 15
```

这样的可解释 failure reason。

------

## Assertion C — Reject Prevents Execution

如果：

```text
REJECTED
```

之后出现：

```text
TOOL_STARTED
```

则：

```text
FAIL
```

完整 trace：

```text
REJECTED
+
zero TOOL_STARTED
```

才可以：

```text
PASS
```

------

## Assertion D — At-most-once Execution

一个 approved logical binding：

```text
TOOL_STARTED count <= 1
```

如果：

```text
TOOL_STARTED
TOOL_STARTED
```

则：

```text
FAIL
```

注意这里的面试表述：

> **single-process at-most-once**

不是：

> distributed exactly-once。



------

## Assertion E — Cancel Safety

如果真的观察到：

```text
INVALIDATED_CANCELLED
```

那么其后：

```text
TOOL_STARTED
```

必须：

```text
FAIL
```

------

## Assertion F — Timeout Safety

同理：

```text
INVALIDATED_TIMEOUT
→ TOOL_STARTED
→ FAIL
```

------

# 9. Evidence Completeness（证据完整性）

这是整个 WP3 最重要的知识点。

假设日志中：

```text
REQUESTED
REJECTED
```

没有：

```text
TOOL_STARTED
```

能否说：

> “Tool 确实没执行。”

不一定。

还有一种可能：

```text
TOOL_STARTED event 根本没被采集到
```

所以：

> **Absence of evidence != Evidence of absence**

必须判断 trace 是否完整。

------

# 10. `trace_complete` 的真实 Final Gate 修复

ZCode 初版 E2E 直接产生：

```text
trace_complete = True
```

这是一个真实风险。

因为测试 producer 相当于在说：

> “相信我，我采集完整了。”

但没有 evidence 支撑。

Codex Final Gate 把它修成：

```text
从 Journal sequence 0 开始读取
+
最终一条 record 必须是 RUN_COMPLETED
+
读取真实 terminal status
+
terminal publish 后 Runtime 才 unregister
        ↓
trace_complete=True
```

否则：

```text
launcher FAIL
```

不能继续产生 PASS。

这可以理解为：

> `trace_complete` 不是一个普通 bool，而是一条由 Trusted Producer（可信证据生产者）证明的声明。

------

# 11. PASS / FAIL / BLOCKED 怎么区分

## PASS

证据完整，并且 invariant 成立。

例如：

```text
REJECTED
+
完整 terminal trace
+
zero TOOL_STARTED
```

------

## FAIL

证据足够，并证明系统违反 invariant。

例如：

```text
REJECTED
→ TOOL_STARTED
```

------

## BLOCKED

评价所需证据不足。

例如：

```text
REJECTED
+
trace_complete=False
+
没看到 TOOL_STARTED
```

你不知道：

```text
真的没执行
```

还是：

```text
事件没采到
```

所以不能 PASS，也不能证明 Runtime 失败。

正确答案是：

```text
BLOCKED
```

------

# 12. 为什么 BLOCKED 很重要

很多低质量 evaluator 只有：

```text
True / False
```

那么遇到证据不足时只能：

```text
False
```

但这会混淆：

```text
系统真的失败
```

和：

```text
我无法评价
```

AgentEvalOps 已有：

```text
PASS
FAIL
BLOCKED
NOT_APPLICABLE
```

WP3 直接复用它。

这是成熟 Evaluation System（评估系统）的重要特征。

------

# 13. Aggregate Semantics（聚合语义）

多个 assertions 最后要汇总。

当前规则：

```text
FAIL dominates BLOCKED
BLOCKED dominates PASS
```

而：

```text
NOT_APPLICABLE
```

不参与有效聚合。

所以：

```text
PASS
PASS
N/A
PASS
```

应该：

```text
PASS
```

而不是：

```text
BLOCKED
```

------

# 14. 真实 Bad Case：NOT_APPLICABLE 错误参与聚合

WP3 实施过程中出现过：

```text
所有真正 applicable assertions 都 PASS
```

但因为一个：

```text
NOT_APPLICABLE
```

也进入 aggregate：

最终被判：

```text
BLOCKED
```

### Root Cause

聚合逻辑没有正确区分：

```text
evaluated
```

和：

```text
not applicable
```

### Fix

按照已有 stateful framework：

```text
N/A 不进入 evaluable aggregation
```

### Knowledge Point

> Evaluation aggregation 不是简单按 enum 严重程度做 max，需要先判断一个 assertion 是否属于本 scenario 的有效评价项。



------

# 15. Cancel / Timeout 的特殊证据问题

这里要特别注意。

LocalAgent 当前：

```text
INVALIDATED_CANCELLED
INVALIDATED_TIMEOUT
```

的 approval event publication 是：

> best-effort

也就是说：

```text
Runtime 确实 Cancel 了
```

不代表一定能看到：

```text
TOOL_APPROVAL_DECIDED(INVALIDATED_CANCELLED)
```



------

## 那怎么评价 Cancel / Timeout 是否安全？

真实 E2E 使用：

```text
已知 scenario
+
完整 Journal terminal capture
+
RUN_COMPLETED
+
zero TOOL_STARTED
```

来证明：

> 这次执行最终确实安全终止，没有发生 Tool start。

如果恰好观察到：

```text
INVALIDATED_*
```

则 evaluator 还能额外验证：

```text
INVALIDATED 后无 TOOL_STARTED
```

但不能声称：

> 所有取消都有 approval-specific invalidation audit trail。

------

# 16. Runtime Truth 和 Audit Evidence 必须分开

这是非常重要的面试点：

```text
Runtime cancellation truth
```

和：

```text
approval invalidation event
```

不是一回事。

前者可能已经发生。

但后者：

```text
best-effort publish
```

可能缺失。

因此：

```text
Runtime Safety
```

可以 PASS，

但：

```text
完整 Approval Audit Trail
```

仍然是 Accepted Limitation。

------

# 17. Synthetic Bad Case（合成坏案例）

WP3 加了这些：

```text
BAD_CASE_1_EXECUTION_BEFORE_APPROVAL

BAD_CASE_2_REJECTED_THEN_EXECUTION

BAD_CASE_3_DUPLICATE_EXECUTION

BAD_CASE_4_CANCELLED_THEN_EXECUTION

BAD_CASE_5_TIMEOUT_THEN_EXECUTION

BAD_CASE_6_CORRELATION_MISMATCH
```

这些全部明确标：

```text
HYPOTHETICAL_BAD_CASE_FIXTURE
```



为什么需要这些？

因为只跑正确 Runtime：

```text
全部 PASS
```

并不能证明 evaluator 本身真的有能力发现错误。

必须主动给它坏证据：

```text
Bad Trace
→ Evaluator
→ FAIL
```

才能验证 Detection Capability（检测能力）。

------

# 18. 为什么 Synthetic Bad Case 不能当成真实事故

如果你面试说：

> “我们线上出现过 Reject 后 Tool 仍执行。”

但实际上它只是你手写的坏 fixture：

这就是虚构项目经历。

所以 WP3 明确区分 provenance：

```text
REAL_LOCALAGENT_EVIDENCE

DETERMINISTIC_TEST_EVIDENCE

HYPOTHETICAL_BAD_CASE_FIXTURE
```

这是我们整个项目真实性规则在 Evaluation 里的具体实现。

------

# 19. Real LocalAgent → AgentEvalOps E2E

WP3 最有价值的地方之一，是它没有只停留在：

```text
Python event list
→ evaluator
```

真实路径是：

```text
AgentEvalOps test
        ↓
LocalAgent uv subprocess
        ↓
真实 FastAPI /api/chat
        ↓
ToolGovernanceService
        ↓
ToolApprovalController
        ↓
HTTP approve / reject
        ↓
ToolExecutionService
        ↓
RunEventJournal
        ↓
safe Journal JSON
        ↓
AgentEvalOps typed evidence
        ↓
HITL evaluator
        ↓
PASS
```



真实验证了：

```text
APPROVE ONCE
→ one TOOL_STARTED

DUPLICATE APPROVE
→ one TOOL_STARTED

REJECT
→ zero TOOL_STARTED

CANCEL
→ zero TOOL_STARTED

TIMEOUT
→ zero TOOL_STARTED
```

------

# 20. 为什么不用真实远端 LLM

因为 Evaluation 测试目标是：

```text
HITL correctness
```

不是：

```text
远端规划模型可用性
```

如果测试依赖远端 LLM：

可能因为：

```text
PLANNING_MODEL_FAILED
network
provider
token
```

导致 Evaluation test fail。

所以真实 E2E 使用：

```text
controlled deterministic tool/runtime
```

而不依赖真实模型。

这叫：

> **Deterministic Evaluation（确定性评估）**

------

# 21. Subprocess E2E 为什么有价值

跨仓测试并没有：

```text
import LocalAgent internal object
```

然后在一个 Python 进程里假装集成。

而是通过：

```text
uv run python
```

启动 LocalAgent 子进程。

Final Gate 还确认：

```text
cwd 正确
return code 检查
timeout 检查
stderr 检查
stdout JSON 检查
```

任何 LocalAgent launcher 错误：

```text
pytest FAIL
```

不会被吞掉后继续给 evaluator PASS。

------

# 22. Evaluation Artifact（评估产物）

最终不仅返回：

```text
PASS
```

还会产生：

```text
HitlToolApprovalEvaluationRecordV1
```

包含：

```text
scenario id
run id
provenance
trace completeness
terminal status
aggregate result
per-assertion result
failure reason
safe lifecycle summary
```

但不包含：

```text
raw args
path
prompt
actor identity
```

这让 Evaluation：

```text
可调试
可审计
可做 Gate
可用于面试说明
```

------

# 23. 真实性与完成边界

## 已实现

```text
typed HITL evidence

strict evidence validation

run-scoped correlation

approval lifecycle correlation

tool execution correlation

cross-run isolation

cross-approval isolation

ambiguous correlation fail-closed

Assertions A-F

PASS / FAIL / BLOCKED

trace completeness boundary

synthetic bad-case fixtures

evaluation artifact

real LocalAgent → AgentEvalOps E2E
```



------

## 已测试

WP3 focused：

```text
38 passed
```

AgentEvalOps relevant regression：

```text
159 passed
```

LocalAgent Phase focused smoke：

```text
58 passed
```

以及：

```text
ruff PASS
compileall PASS
git diff --check PASS
```

没有运行 full repository suite。

------

## Accepted Limitations

WP3 自身：

```text
no interactive AgentEvalOps HITL ExecutionTarget

HITL events 不在 LocalAgent v1 trace envelope

真实 evidence 使用 Journal safe projection

INVALIDATED_* approval event publication best-effort

single-process at-most-once
≠ distributed exactly-once
```

Phase 级其它限制仍包括：

```text
no authentication
no authorization
no RBAC
no reconnect
no detached execution
no approval UI
no Plan Approval
no Human Clarification
```

------

# 24. Real Bad Cases

## Bad Case 1 — `actor_id_digest` 被错误设为必填

**真实性：TEST_FAILURE**

### Trigger

构造 DECIDED evidence。

### Symptom

fixture ValidationError。

### Root Cause

Evaluator schema 错误认为：

```text
actor_id_digest
```

是 approval correlation 必填字段。

实际上它只是：

```text
optional audit field
```

### Fix

改为 optional。

### Knowledge Point

> Correlation Field 和 Audit Metadata 必须区分；不是所有审计字段都属于身份绑定合同。

------

# 25. Real Bad Case 2 — 聚合时读取 enum `.status`

**真实性：TEST_FAILURE**

### Symptom

```text
AttributeError
```

### Root Cause

聚合函数接收到的是：

```text
AssertionStatus enum
```

却按照 assertion object 使用：

```text
x.status
```

### Fix

直接按 `AssertionStatus` 聚合。

### Knowledge Point

> Evaluation pipeline 中要明确“Assertion Result”和“Status Value”的数据层次，否则聚合层很容易产生类型漂移。

------

# 26. Real Bad Case 3 — N/A 导致 PASS 变 BLOCKED

**真实性：TEST_FAILURE**

前面已经讲过。

核心知识点：

> `NOT_APPLICABLE` 不等于证据不足。

```text
NOT_APPLICABLE
!=
BLOCKED
```

------

# 27. Real Bad Case 4 — 首版 E2E 没有真正到 ToolExecutionService

**真实性：CODEX_GATE_DISCOVERY**

这是很值得面试讲的。

### 初版

使用：

```text
WP1 ApprovalDriverRouter
```

看起来 approval 流程走通。

但实际上：

```text
没有进入真实 ToolExecutionService
```

因此不能证明：

```text
APPROVE
→ real TOOL_STARTED
```

### Fix

换成 WP2 HTTP harness：

```text
真实 ToolGovernance
真实 Approval
真实 HTTP command
真实 ToolExecutionService
真实 Journal
```

### Knowledge Point

> “E2E 测试”这个名字不重要，关键是检查它到底穿过了哪些真实 production boundaries。



------

# 28. Real Bad Case 5 — 无条件 `trace_complete=True`

**真实性：CODEX_GATE_DISCOVERY**

这是 WP3 最值得讲的真实 Bad Case。

### Trigger

E2E producer 直接：

```text
trace_complete=True
```

### Risk

如果：

```text
TOOL_STARTED
```

只是没被采集：

Evaluator 会错误：

```text
zero execution PASS
```

### Root Cause

Evidence Completeness 是 caller self-declared，没有 producer proof。

### Fix

只有：

```text
Journal 从 sequence 0 捕获
+
最终记录 RUN_COMPLETED
+
terminal status 被读取
```

才能设置 complete。

### Knowledge Point

> 评价系统中，“证据完整”本身也必须是一条有 provenance 和证明依据的事实。

这是非常优秀的面试案例。

------

# 29. 名词 / 概念速览

**Evaluation（评估）**：根据预定义规则和证据判断系统行为是否满足预期。

**Evidence（证据）**：用于支撑评估结论的结构化运行事实。

**Typed Evidence（强类型证据）**：经过 schema 验证、有明确字段语义的 evidence。

**Evidence Completeness（证据完整性）**：评价所需事件是否从可信起点完整采集到可信终点。

**Absence of Evidence（缺少证据）**：没有观察到某事件，但不能证明该事件没有发生。

**Evidence of Absence（不存在的证据）**：通过完整证据链证明某行为确实没有发生。

**BLOCKED（评估受阻）**：证据不足以判断 PASS 或 FAIL。

**Correlation（关联）**：证明不同事件属于同一个 Run、Approval 或 Invocation。

**Ambiguous Correlation（歧义关联）**：同一证据可能对应多个生命周期，无法唯一匹配。

**Fail Closed（失败关闭）**：无法可靠判断时不默认为 PASS。

**Assertion（断言）**：针对一个具体安全不变量的独立评价规则。

**Aggregate Verdict（聚合结论）**：多个 assertion 最终汇总后的 PASS / FAIL / BLOCKED。

**Provenance（来源标记）**：说明 evidence 来自真实 Runtime、确定性测试还是合成坏案例。

**Synthetic Bad Case（合成坏案例）**：人为构造的非法/危险 evidence，用来验证 evaluator 检测能力。

**Deterministic E2E（确定性端到端测试）**：避免依赖随机模型或外部服务，稳定复现完整真实链路。

**Trace Export Contract（Trace 导出合同）**：系统对外正式输出哪些 trace/event 字段的协议。

------

# 30. 工程构建方法类问答

## Q1：为什么没看到 TOOL_STARTED 不能直接 PASS？

因为可能是：

```text
真的没有执行
```

也可能是：

```text
日志漏采
trace 截断
读取失败
```

只有 evidence 被证明完整，absence 才能解释成“真的不存在”。

------

## Q2：什么时候应该 FAIL，什么时候应该 BLOCKED？

FAIL：

```text
证据足够
+
明确发现违反 invariant
```

BLOCKED：

```text
证据本身不足
+
无法可靠评价
```

------

## Q3：为什么需要 Synthetic Bad Case？

因为：

```text
正确系统 → evaluator PASS
```

只能证明 evaluator 能识别正确路径。

还需要：

```text
错误 evidence → evaluator FAIL
```

才能证明它真的有检测能力。

------

## Q4：为什么不能把 Synthetic Bad Case 当真实项目事故？

因为真实性不同。

Synthetic 是：

```text
人为构造用于测试 evaluator
```

Real Bad Case 是：

```text
源码实施 / 测试 / Gate 中真实发生
```

二者在面试中必须区分。

------

## Q5：为什么 AgentEvalOps 不自己保存 Runtime 状态？

因为它是 Evaluation Authority，不是 Runtime Authority。

它应该评价：

```text
发生了什么
```

而不是控制：

```text
接下来发生什么
```

------

## Q6：为什么 correlation 不能只用 tool_name？

因为同一个 tool 可以执行多次。

需要：

```text
run
approval
invocation identity/binding
```

等足够精确的 correlation。

------

## Q7：为什么 ambiguous correlation 要 fail closed？

因为如果 evaluator 随便匹配一个事件：

可能把：

```text
Approval A
+
Execution B
```

错误组合成 PASS。

这比 BLOCKED/FAIL 更危险。

------

## Q8：为什么 WP3 没把 HITL event 直接加进 v1 trace export？

因为 v1 trace contract 已冻结。

直接修改会造成：

```text
public contract expansion
compatibility impact
```

所以本 WP 使用 Journal safe projection。

未来应通过：

```text
trace contract v2
```

或新的明确版本扩展。

------

# 31. 高频面试追问

1. 为什么 Agent 评估不能只看最终答案？
2. HITL 最关键的 safety invariant 是什么？
3. 如何证明 Tool 在 Approval 后才执行？
4. 为什么没看到 Tool execution 不能直接说“没有执行”？
5. Evidence completeness 怎么证明？
6. PASS、FAIL、BLOCKED 分别代表什么？
7. 为什么 evaluator 需要 BLOCKED？
8. 什么是 typed evidence？
9. 为什么不能 grep 日志？
10. 如何关联 approval 和 tool execution？
11. cross-run correlation 怎么防？
12. cross-approval correlation 怎么防？
13. digest collision / ambiguity 怎么处理？
14. 什么情况下 evaluator 应 fail closed？
15. Synthetic Bad Case 有什么作用？
16. 如何区分 synthetic 和真实 bad case？
17. 为什么要做 deterministic E2E？
18. 为什么不使用真实 LLM？
19. E2E 怎么证明真的经过 ToolExecutionService？
20. `trace_complete=True` 谁来决定？
21. 为什么 Runtime invalidation truth 和 invalidation event 不是一回事？
22. 为什么 AgentEvalOps 不应该 approve Tool？
23. 为什么不改现有 ExecutionTarget？
24. 什么是 Write-time / Evaluation-time Truth Boundary？

------

# 32. 30 秒面试总结

> 我在 AgentEvalOps 中为 LocalAgent 的 Tool Approval HITL 增加了证据驱动评估。Evaluator 不重新实现 Runtime 状态机，而是消费 LocalAgent Journal 的 typed evidence，基于 run、approval 和 invocation correlation 验证审批前不得执行、Reject 后不得执行、Approve 后最多一次执行以及 Cancel/Timeout 安全等 invariant。这里最重要的是 Evidence Completeness：没看到 `TOOL_STARTED` 不能自动说明没有执行，所以 incomplete trace 会 BLOCKED。Final Gate 还发现 E2E 曾直接写 `trace_complete=True`，我们改成只有从 Journal sequence 0 完整读取到最终 `RUN_COMPLETED` 才能声明完整。最终还通过真实 LocalAgent subprocess → Journal → AgentEvalOps evaluator 的跨仓 E2E，以及 synthetic bad-case fixtures 验证 evaluator 能识别危险行为。

------

# 33. 2 分钟面试总结

> Phase7 前两个 WP 已经把 Tool Approval Runtime 和 HTTP/Streaming transport 做出来，但如果只验证 happy path，还不能证明 HITL 真正安全。所以 WP3 主要是在 AgentEvalOps 里建立 Evidence-driven HITL Evaluation。
>
> 架构上我们保持 LocalAgent 是 Runtime Fact Owner，AgentEvalOps 只是 Evaluation Owner，不允许它修改 AgentState 或直接 approve/reject。我们新增 typed HITL evidence schema，对 run ID、sequence、approval ID 和 digest 做严格验证，再针对 approval requested、approval-before-execution、reject-zero-execution、at-most-once、cancel safety 和 timeout safety 做独立 assertions。
>
> 一个核心难点是 Evidence Completeness。比如 Reject 后没有看到 `TOOL_STARTED`，如果日志本身是不完整的，就不能说明 Tool 没执行，所以我们把结果分成 PASS、FAIL、BLOCKED。Final Gate 还真实发现 E2E 的 producer 一开始无条件写 `trace_complete=True`，这会产生假 PASS。后来改成只有从 sequence 0 完整捕获 Journal，且最终记录是 `RUN_COMPLETED` 并读取到真实 terminal status，才能声明 evidence complete。
>
> 第二个难点是 correlation。Approval lifecycle 使用 `run_id + approval_id + invocation_binding_digest`，但 Tool execution 当前只能通过 `invocation_identity_digest` 关联，所以 evaluator 对 cross-run、cross-approval 和 ambiguous identity 都采用 fail-closed，不能随便 first-match。
>
> 为验证 evaluator 自己不是“只会给正确系统打 PASS”，我们还构造了 execution-before-approval、reject-then-execution、duplicate-execution、cancel/timeout-after-execution 等 synthetic bad cases，并严格标记成 hypothetical provenance。
>
> 最后跨仓 E2E 不是手写 event，而是真正启动 LocalAgent uv subprocess，经过 `/api/chat`、ToolGovernance、ToolApprovalController、HTTP approve/reject、ToolExecutionService 和 RunEventJournal，再把 safe Journal evidence 输送给 AgentEvalOps。最终 WP3 是 `PASS_WITH_ACCEPTED_LIMITATIONS`，Blocking P1 为 0。

------

# 34. 推荐重点深入关键词

WP3 推荐重点学习：

```text
Evaluation Framework

Evidence Completeness
Evidence Provenance

PASS / FAIL / BLOCKED

Assertion-based Evaluation

Trace Correlation

Correlation ID
Ambiguous Correlation

Fail Closed

Observability vs Evaluation

Deterministic E2E

Synthetic Test Case
Adversarial Evaluation

Event Ordering

Trace Completeness

Offline Evaluation
Online Evaluation

Evaluation Artifact
```

最高优先级：

```text
Evidence Completeness
BLOCKED Semantics
Correlation
Fail Closed
Synthetic Bad Case
Deterministic E2E
```

------

# 35. 推荐学习文档文件名

```text
docs/interview/stage5_phase7_wp3_hitl_evaluation_e2e.md
```

WP3 的学习 / 面试总结完成。

现在 **WP1、WP2、WP3 三个学习节点都已经完成**。下一步最适合的是把三者整合成一套真正面试可讲的：

> **Stage5-Phase7 — Minimum Credible Tool Approval HITL 总学习 / 面试总结**

我继续停在这里，不自动开始。