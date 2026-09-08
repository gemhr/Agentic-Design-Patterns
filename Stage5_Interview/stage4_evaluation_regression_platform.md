# AgentEvalOps Stage 4 整体学习总结

Stage 4 最终已经完成并冻结。独立 Closeout 的正式结论是：

```text
STAGE4_PROJECT_GATE: PASS
PHASE0 ~ PHASE5_MINIMAL_RECOMMENDED_SCOPE: COMPLETE
OPEN_P0: 0
OPEN_P1: 0

INTERVIEW_READY: YES
APPLICATION_PRIORITY: APPLY_NOW

STAGE4_FREEZE: YES
NO_MORE_STAGE4_FEATURE_EXPANSION: YES

Production Ready: PARTIAL
```

因此，学习 Stage4 时最重要的不是记住“做了多少功能”，而是理解它如何从一个以 **Trace / Score / Monitoring** 为中心的 PandaProbe，逐步演进成一个具有独立 **Evaluation / Regression / Release Gate** 能力的 AgentEvalOps 平台。

------

# 1. Stage 4 一句话定义

> **Stage 4 的核心工作，是把 Trace 从 Evaluation Truth 中解耦出来，建立独立的 Evaluation Domain，并最终形成 Production Trace → Feedback → Dataset/TestCase → Evaluation → Regression → Release Gate 的完整评估闭环。**

最终主链：

```text
Trace / Span
    ↓
Generic Online Normalization
    ↓
Failure Detection / Metrics
    ↓
TraceEvidenceCandidate
    ↓
Trace Feedback
    ↓
DatasetVersion / TestCaseVersion
    ↓
EvaluationRun
    ↓
ExecutionAttempt
    ↓
EvaluationResult
    ↓
Baseline / Candidate Comparison
    ↓
RegressionReport
    ↓
ReleaseDecision
    ↓
Demo / CI Adapter
```

这条链是整个 Stage4 最值得背下来的内容。

------

# 2. Stage 4 六个阶段分别解决什么

| Phase  | 核心问题                              | 最终结果                       |
| ------ | ------------------------------------- | ------------------------------ |
| Phase0 | Trace 和 Evaluation 到底谁拥有 Truth  | Architecture / Owner Freeze    |
| Phase1 | 不同 Runtime 的 Trace 怎么统一分析    | Generic Online Core            |
| Phase2 | Evaluation 怎么真实执行、并发、持久化 | Run / Attempt / Result Runtime |
| Phase3 | Baseline 和 Candidate 怎么比较        | Regression + Release Gate      |
| Phase4 | 生产失败怎么回流测试集                | Trace-to-Dataset Feedback      |
| Phase5 | 核心能力怎么真正跑给人看、给 CI 用    | Closed-loop Demo + CI Adapter  |

最重要的是：

> **Phase0～Phase5 不是六堆功能，而是一条依赖链。**

------

# 3. Phase0：Stage4 最重要的架构决策

整个 Stage4 的第一原则：

```text
Trace ≠ EvaluationResult
```

Trace 表示：

> 系统真实运行时“发生了什么”。

EvaluationResult 表示：

> 某个明确版本的 TestCase、Evaluator、ExecutionTarget，在某次 Run / Attempt 下得到的评估事实。

因此：

```text
Trace
= Observation / Evidence Source

Evaluation
= Evaluation Truth
```

如果不拆开，就会出现：

```text
Trace Score
→ 被当成 Evaluation Score

生产实际输出
→ 被当成 expected answer

线上失败
→ 被直接当成 regression case
```

这些在语义上都是错误的。

所以 Stage4 最核心的系统设计思想可以概括为：

> **先冻结 Truth Owner，再实现业务流程。**

最终 Closeout 没发现 Dual Owner，Owner consistency 为 PASS。

------

# 4. Phase1：Generic Online Core

Phase1 解决的是 Runtime-neutral（运行时中立）问题。

原系统可能面对：

```text
Legacy Trace
LocalAgent Trace
未来其它 Agent Runtime
```

不能给每个 Runtime 写一套 Evaluation。

所以先统一映射：

```text
Runtime-specific Trace
        ↓
Generic Trace / Span
```

核心统一字段包括：

```text
normalized_source_kind
normalized_outcome
normalized_operation
normalized_component
normalized_error_code
normalized_duration_ms
normalized_attributes
```

这样 Evaluation 平台后续不需要依赖 LocalAgent-specific DTO。

------

# 5. Outcome / Failure Semantics

Phase1 一个非常重要的知识点：

```text
SUCCESS
FAILURE
CANCELLED
TIMEOUT
UNKNOWN
```

真正属于 failure：

```text
FAILURE
CANCELLED
TIMEOUT
```

而：

```text
UNKNOWN
```

**不等于 FAILURE。**

为什么？

因为 UNKNOWN 只是：

> 没有足够证据判断。

如果把 UNKNOWN 计入 failure：

```text
不确定数据
→ failure_count 增长
→ 在线质量指标失真
```

这体现一个通用工程原则：

> **缺少证据不能自动转换成负面事实。**

历史 normalized NULL 也没有被系统伪造回填。

------

# 6. TraceEvidenceCandidate 是什么

发现一条 failing Trace 后，并没有直接：

```text
Trace
→ TestCase
```

而是：

```text
Trace
→ TraceEvidenceCandidate
```

Candidate 只代表：

> 这条 Trace 值得被考虑加入 Evaluation 数据。

它还不是：

- Golden TestCase；
- Critical Case；
- Expected Answer；
  -正式 Dataset Version。

这层设计很重要，因为：

```text
“发现线上问题”
≠
“批准它成为评估资产”
```

------

# 7. Phase2：Evaluation Domain Foundation

Phase2 建立了 Stage4 真正的 Offline Evaluation Core。

核心对象：

```text
DatasetVersion
TestCaseVersion
EvaluationSuiteVersion

EvaluatorSpec
ExecutionTargetRef

EvaluationRun
ExecutionAttempt
EvaluationResult
```

其中最核心的是：

```text
Run
Attempt
Result
```

------

# 8. Run / Attempt / Result 怎么理解

## EvaluationRun

表示：

> 一次完整 Evaluation 执行。

例如：

```text
Dataset v3
+
Suite v2
+
Candidate v5
```

跑一轮，就是一个 Run。

------

## ExecutionAttempt

表示：

> 某一个 Case 的某一次具体执行尝试。

因为可能：

```text
Attempt 1
→ TIMEOUT

Attempt 2
→ SUCCESS
```

因此 Attempt 是执行过程事实。

------

## EvaluationResult

表示：

> 已经最终确定的 Evaluation Fact。

所以记住：

```text
Run
= 一次评估批次

Attempt
= 某个 Case 的一次执行尝试

Result
= 最终不可随意修改的评估事实
```

------

# 9. 为什么 Run / Attempt / Result 不能合并

如果只有一个“Evaluation 表”，很难正确处理：

- Retry；
- Worker Crash；
- Concurrent Claim；
- Timeout；
- stale worker；
  -最终结果唯一性；
  -历史追踪。

分层以后：

```text
Run
→ 管批次

Attempt
→ 管执行生命周期

Result
→ 管最终事实
```

Owner 很清楚。

------

# 10. Atomic Claim CAS

多个 Worker 可能同时看到：

```text
Attempt=PENDING
```

如果只是 Python：

```python
if status == "PENDING":
    status = "RUNNING"
```

不能保证并发安全。

因此 Stage4 使用 CAS（Compare-And-Set，比较并设置）思想，让数据库做竞争：

```text
UPDATE attempt
SET claimed...
WHERE
    attempt_id = ?
    AND status = PENDING
```

只有一个 Worker 成功更新。

所以：

> **并发 ownership 最终必须在共享 Truth Store 解决，而不是靠进程内 if。**

------

# 11. Claim Token Fencing

CAS 只解决“谁先抢到”。

还存在另一种 Bad Case：

```text
Worker A claim
    ↓
A 卡死

lease/recovery
    ↓
Worker B 获得执行权

A 突然恢复
```

如果只看：

```text
status == RUNNING
```

A 仍可能继续写 Result。

所以还要：

```text
claim_token
```

后续写入必须满足：

```text
caller_claim_token
==
current_claim_token
```

这就是 Fencing Token（栅栏令牌）。

它解决：

> **旧 owner 恢复后不能继续污染当前执行事实。**

这是 Stage4 最值得面试深入讲的并发设计之一。

------

# 12. Retry 为什么要创建新 Attempt

错误设计：

```text
Attempt A FAILED
→ reset A to PENDING
```

这会覆盖历史。

最终采用：

```text
Attempt A FAILED
    ↓
Attempt B
retry_of=A
```

即：

> **Retry 是一个新的事实，而不是修改旧事实。**

这样可以保留：

-第一次为什么失败；
-重试了几次；
-哪一次成功；
-完整 execution lineage。

------

# 13. EvaluationResult 为什么 Append-only

如果：

```text
Result FAIL
```

后续能改成：

```text
Result PASS
```

那 Regression 历史就不可信。

因此 Stage4 使用：

```text
Append-only Result
+
Logical Uniqueness
```

Result 一旦 finalized，就作为历史事实保留。

所以：

> **Regression 平台首先必须保证 Evaluation Result 本身可信。**

------

# 14. Phase2 已经证明什么

已经证明：

```text
LOCAL_POSTGRESQL_PROVEN
DOMAIN_CONCURRENCY_CORRECTNESS_PROVEN
```

包括：

- Run/Attempt persistence；
- Atomic Claim；
- Fencing；
- Retry lineage；
- stale reconciliation；
- append-only Result；
- logical uniqueness。

但没有证明：

```text
PRODUCTION_MULTI_WORKER_PROVEN
```

因为没有真实生产 Worker 集群、Crash/Restart、Load 环境的完整验证。

这个边界必须记住。

------

# 15. Phase3：为什么需要 Regression Domain

单次 Evaluation 只能回答：

> Candidate 自己表现怎么样？

但实际发布需要问：

> Candidate 相比 Baseline 变好了还是变差了？

所以 Phase3 增加：

```text
Baseline Run
Candidate Run
      ↓
Comparison
```

对齐键不是只有 `test_case_id`，而是：

```text
(
  case_id,
  case_version,
  evaluator_id,
  evaluator_version
)
```

这一点非常重要。

否则两个不同版本 Case 或 Evaluator 的 Result 可能被错误比较。

------

# 16. Regression Classification

当前核心分类：

```text
PASS → FAIL
= REGRESSION

FAIL → PASS
= IMPROVEMENT

same
= UNCHANGED

missing / ERROR / INCONCLUSIVE
= NOT_COMPARABLE
```

注意：

```text
NOT_COMPARABLE
≠
FAIL
```

它表达：

> 当前无法做可信版本比较。

这和 Phase1：

```text
UNKNOWN ≠ FAILURE
```

是同一种工程思想。

------

# 17. Criticality 为什么不能自动判断

系统可以判断：

```text
Case A = REGRESSION
```

但不能知道：

```text
Case A 是否属于核心业务
```

所以：

```text
Criticality Owner = caller
```

不能由：

- Evaluator；
- Comparison Service；
- CI；
  -名字或 tag 自动推断。

因为 Criticality 是业务 Policy。

------

# 18. Release Gate

最终最小 Release Policy：

```text
Critical REGRESSION
→ BLOCK

Critical NOT_COMPARABLE
→ BLOCK

Non-critical REGRESSION
→ report only

Non-critical NOT_COMPARABLE
→ report only
```

最终：

```text
ReleaseDecision.PASS
ReleaseDecision.FAIL
```

Owner 是：

```text
RegressionReportService
```

这点非常重要：

> **CI 不是 ReleaseDecision Owner。**

------

# 19. Phase4：Trace Feedback

Phase4 完成：

```text
Failing Trace
    ↓
TraceEvidenceCandidate
    ↓
Explicit Feedback
    ↓
TestCaseVersion
    ↓
DatasetVersion
```

这里最大的设计原则是：

```text
Production Trace
≠
Automatically trusted Test Case
```

------

# 20. 为什么生产 Trace 不能直接写进 Dataset

因为还缺几个权威事实：

```text
输入是否脱敏？
expected answer 是什么？
是否 Critical？
Case Version 是多少？
Dataset Version 是多少？
```

AgentEvalOps 没有权力自动回答。

所以最终：

```text
Sanitization
= CALLER_SUPPLIED

Expected Output
= CALLER_SUPPLIED / OPTIONAL

Criticality
= CALLER_SUPPLIED

Version
= CALLER_SUPPLIED
```

------

# 21. 为什么 Production Actual Output 不能当 Expected Output

比如线上 Trace 是因为模型：

```text
答错
```

才进入 failure analysis。

如果自动：

```text
actual output
→ expected output
```

就等于：

```text
错误答案
→ Golden Answer
```

所以这一步必须显式治理。

------

# 22. Dataset 为什么 NEW_VERSION

如果已有：

```text
Dataset V1
```

加入一个新 Case 后不能修改 V1。

而应该：

```text
Dataset V1
    ↓
Dataset V2
```

因为历史 Run 可能绑定 V1。

如果原地修改：

> 过去 Evaluation 的输入集合就变了，历史结果无法解释。

所以：

> **Evaluation Dataset 也属于 Versioned Fact。**

------

# 23. Phase4 的真实边界

完成的是：

```text
MINIMAL PRODUCTION FEEDBACK LOOP
```

没有：

```text
Durable Dataset Catalog
Feedback HTTP API
Automatic Evaluation
Human Review
Alert
Judge/Human Agreement
```

因此不能称为：

> 完整 Production Feedback Platform。



------

# 24. Phase5-WP1：为什么还需要 Demo

做到 Phase4 后，理论上的核心模块已经全了：

```text
Feedback
Evaluation
Comparison
Report
Gate
```

但：

```text
Service 全存在
≠
完整工作流真的能跑
```

所以 WP1 做 Closed-loop Demo。

真实调用：

```text
TraceFeedbackService
→ EvaluationPersistenceService
→ EvaluationLoopService
→ EvaluationComparisonService
→ RegressionReportService
```

并使用真实 PostgreSQL。

这证明的是：

> **Composition Correctness（组合正确性）。**

------

# 25. Demo 为什么不用真实 LLM

Demo 的目标：

> 验证 AgentEvalOps Workflow。

不是：

> 验证 DeepSeek/OpenAI API。

真实模型会引入：

-网络；
-费用；
-密钥；
-随机性；
-版本变化。

所以使用 deterministic Fixture：

```text
REAL PostgreSQL
+
SYNTHETIC deterministic evaluation
```

这样 Demo 稳定可重复。

------

# 26. WP1 的真实安全 Bad Case

第一次 Final Gate 并没有通过。

发现：

```text
README
Makefile
CLI --help
```

存在明文 PostgreSQL DSN password。

因此：

```text
H-4 = FAIL
```

之后修成：

```text
explicit --dsn
→ environment
→ project config
```

重新 Final Gate：

```text
PASS
```

这个 Bad Case 很适合面试。

因为说明：

> **Onboarding / Documentation Surface 也是 Security Surface。**

最终 Closeout 记录这个 P1 已关闭，而不是抹掉历史。

------

# 27. Phase5-WP2：CI Gate

WP1 Demo 中：

```text
ReleaseDecision.FAIL
→ Demo exit 0
```

这是正确的。

因为：

> Demo 成功地演示出了 FAIL。

但 CI 需要：

```text
PASS
→ process success

Gate FAIL
→ process failure

Technical Error
→ process failure
```

最终冻结：

```text
PASS          → exit 0
Gate FAIL     → exit 2
Technical Err → exit 1
```

------

# 28. 为什么 Gate FAIL 和 Technical Error 要分开

如果统一：

```text
everything bad → exit 1
```

那 CI 无法区分：

### 情况 A

```text
Evaluation 正常完成
但 Candidate 质量不达标
```

### 情况 B

```text
数据库挂了
配置错误
Evaluation 根本没执行完
```

它们的运维含义完全不同。

所以：

```text
Business Failure
!=
Technical Failure
```

这是非常重要的后端/平台设计思想。

------

# 29. CI 为什么不能重新计算 ReleaseDecision

错误：

```python
if regression_count > 0:
    exit(2)
```

这会创造第二个 Release Policy Owner。

正确：

```text
RegressionReportService
→ ReleaseDecision
→ CLI Adapter
→ Exit Code
```

因此：

```text
CLI
= Adapter

CLI
≠ Decision Engine
```

------

# 30. FAIL 时为什么一定要生成 Artifact

CI 变红只能告诉开发者：

> Release Gate 没过。

还需要知道：

- 哪个 Case？
- REGRESSION 还是 NOT_COMPARABLE？
  -哪个 Critical blocker？
  -Baseline / Candidate 是什么？

所以必须：

```text
write artifact
    ↓
exit 2
```

Workflow 再：

```text
if: always()
```

上传 artifact。

------

# 31. 为什么没有直接接 production release.yml

因为当前 Gate 使用：

```text
synthetic baseline/candidate
```

如果直接挂进 production release：

> 会制造“AgentEvalOps 已保护真实生产发布”的错误事实。

所以最终只证明：

```text
STATIC_WORKFLOW_PROVEN
```

而不是：

```text
REMOTE_GITHUB_ACTIONS_PROVEN
PRODUCTION_RELEASE_GATE_PROVEN
```

Remote GitHub Actions 最终也是：

```text
NOT_EXECUTED
```



------

# 32. Stage4 最重要的 Owner Matrix

| Truth / Operation            | Owner                        |
| ---------------------------- | ---------------------------- |
| Trace Observation            | Trace ingestion / repository |
| Normalized Online Projection | Online Core                  |
| Failure Semantics            | Generic Online Core          |
| TraceEvidenceCandidate       | TraceService                 |
| Trace Feedback               | TraceFeedbackService         |
| Dataset/TestCase facts       | Evaluation Catalog Domain    |
| Run lifecycle                | EvaluationPersistenceService |
| Attempt execution            | EvaluationLoop + Persistence |
| Result truth                 | Evaluation Result Repository |
| Regression Classification    | EvaluationComparisonService  |
| Criticality                  | Caller                       |
| RegressionReport             | RegressionReportService      |
| ReleaseDecision              | RegressionReportService      |
| Demo                         | Orchestration only           |
| Exit Mapping                 | CI Adapter                   |
| CI Job Result                | GitHub Actions               |

整套系统设计的核心就是：

> **一件事情只能有一个 Truth Owner。**

------

# 33. Stage4 最重要的 Persistence Matrix

| Fact                           | 当前形态                         |
| ------------------------------ | -------------------------------- |
| Trace                          | PostgreSQL Durable               |
| Span                           | PostgreSQL Durable               |
| Normalized Projection          | PostgreSQL                       |
| EvaluationRun                  | PostgreSQL Durable               |
| ExecutionAttempt               | PostgreSQL Durable               |
| EvaluationResult               | PostgreSQL Durable / append-only |
| TraceEvidenceCandidate         | Derived / In-memory              |
| Feedback Result                | In-memory                        |
| DatasetVersion/TestCaseVersion | 当前 In-memory                   |
| RegressionComparison           | Derived                          |
| RegressionReport               | Derived                          |
| ReleaseDecision                | Derived                          |
| CI JSON                        | File Artifact                    |



所以一定要区分：

```text
object exists
≠
object persisted
```

------

# 34. Stage4 最值得掌握的 12 个专业名词

| 名词             | 一句话理解                                        |
| ---------------- | ------------------------------------------------- |
| Observation      | 系统运行时发生的事实                              |
| Evidence         | 可用于 Evaluation 的证据引用                      |
| Evaluation Truth | 经过明确评估上下文产生的结果                      |
| Projection       | 把 Runtime-specific 数据映射成 Generic read model |
| CAS              | 用条件更新解决并发 ownership                      |
| Fencing Token    | 防止 stale owner 继续写                           |
| Retry Lineage    | 用新 Attempt 保留重试关系                         |
| Append-only      | 最终事实只能新增不能覆盖                          |
| Alignment Key    | Baseline/Candidate Result 对齐依据                |
| Critical Case    | 会影响 Release Gate 的业务关键 Case               |
| Fail Closed      | 未知状态默认不放行                                |
| Adapter          | 只转换协议，不重新拥有业务逻辑                    |

------

# 35. Stage4 的核心 Bad Cases

最值得准备的几个：

### 1. Trace 和 Evaluation 双 Owner

修复：

```text
Trace = Evidence
EvaluationResult = Evaluation truth
```

### 2. UNKNOWN 被当 Failure

修复：

```text
UNKNOWN != FAILURE
```

### 3. 两个 Worker 同时 Claim

修复：

```text
Atomic CAS
```

### 4. stale Worker 恢复后写 Result

修复：

```text
Claim Token Fencing
```

### 5. Retry Reset 旧 Attempt

修复：

```text
New Retry Child
```

### 6. Result 可覆盖

修复：

```text
Append-only
```

### 7. Trace 自动变 TestCase

修复：

```text
Explicit Feedback Boundary
```

### 8. Production Output 自动变 Expected Answer

禁止自动推断。

### 9. Regression 自动变 Critical

Criticality 改为 caller-owned。

### 10. CLI 重算 Gate

改为只消费 `ReleaseDecision`。

### 11. Gate FAIL 和 Technical Error 混在一起

改为：

```text
2 / 1
```

### 12. README/CLI Help 泄露 DSN Password

实际 H-4 P1，修复后 rerun PASS。

------

# 36. 整体工程方法论

整个 Stage4 可以总结为四个问题。

## Truth

> 哪个数据才是权威事实？

例如：

```text
Trace ≠ EvaluationResult
```

------

## Owner

> 谁有资格修改或生成这个事实？

例如：

```text
ReleaseDecision
→ RegressionReportService
```

------

## Persistence

> 这个事实是否需要 Durable？

例如：

```text
EvaluationResult
→ YES

RegressionReport
→ 当前 NO
```

------

## Adapter

> 怎么把一个 Domain 的结果交给另一个系统，而不复制业务逻辑？

例如：

```text
ReleaseDecision
→ CLI Exit
→ GitHub Actions
```

如果面试官问：

> “你做这个项目最大的系统设计收获是什么？”

我推荐回答：

> **我后来越来越重视 Truth、Owner、Persistence 和 Adapter Boundary，而不是单纯堆 Service。一个复杂 Agent 系统很多问题本质上都是这些边界没有定义清楚。**

------

# 37. Stage4 测试证据

最终 Closeout 当前 HEAD：

```text
Cross-phase PostgreSQL:
53 passed

Full Unit:
580 passed

Ruff:
PASS

uv lock:
PASS

compileall:
PASS

Alembic:
single head
```



历史各 Phase 还有独立 PostgreSQL / Unit Gate。

面试不要说：

> “累计跑了几千测试。”

更准确说：

> 每个 WP 都有独立 Gate，Stage4 Final Closeout 又在最终 HEAD 上重新跑了 53 个跨阶段 PostgreSQL integration regression 和 580 个 unit tests。

------

# 38. Stage4 的真实性等级

现在可以安全说：

```text
LOCAL_POSTGRESQL_PROVEN
DOMAIN_CONCURRENCY_CORRECTNESS_PROVEN
SYNTHETIC_DEMO_PROVEN
STATIC_WORKFLOW_PROVEN
```

不能说：

```text
PRODUCTION_MULTI_WORKER_PROVEN
REMOTE_GITHUB_ACTIONS_PROVEN
PRODUCTION_RELEASE_GATE_PROVEN
PRODUCTION_EXECUTION_TARGET_PROVEN
```

Final Closeout 专门冻结了这些边界。

------

# 39. 当前 Known Limitations

不用背几十条，记住七类。

| 类别                 | 当前缺口                                                |
| -------------------- | ------------------------------------------------------- |
| Production Execution | 没有 production ExecutionTarget                         |
| Concurrency          | 没有 production multi-worker wiring proof               |
| Persistence          | Durable Dataset Catalog、Report/Decision persistence 无 |
| Automation           | automatic baseline / candidate discovery 无             |
| RAG / Memory         | concrete evaluators / targets / datasets 尚无           |
| Human Workflow       | Human Review / Judge Agreement 无                       |
| CI/CD                | Remote GitHub Action、production release integration 无 |

因此：

```text
INTERVIEW_READY = YES
Production Ready = PARTIAL
```



------

# 40. 30 秒面试总结

> AgentEvalOps 是我基于 PandaProbe 改造成的 Agent Evaluation 和 Regression 平台。核心改造是先把 Trace 从 Evaluation Truth 中解耦，Trace 只作为 Observation 和 Evidence，然后建立独立的 Dataset/TestCase、ExecutionTarget、Run/Attempt/Result Runtime。
>
> Evaluation 执行层使用 PostgreSQL 做 Atomic Claim CAS、Claim Token Fencing、Retry Lineage 和 Append-only Result，在此基础上做 Baseline/Candidate Regression、Critical Case Release Gate，再把线上 failing Trace 通过显式 Feedback 转成新的 TestCase/Dataset Version。
>
> 最后我做了真实 PostgreSQL 的 deterministic closed-loop Demo 和 CI Adapter，把 PASS、业务 Gate FAIL 和技术异常分别映射为 exit 0、2、1。

------

# 41. 2 分钟面试总结

> PandaProbe 原来更偏 Trace、Score 和 Monitoring，我改造时首先解决 Observation 和 Evaluation 的 Owner 边界。我把 Trace 定义成线上观测事实和 Evidence Source，Evaluation 则独立拥有 Dataset、TestCase、ExecutionTarget、Run、Attempt、Result、Regression 和 Release Gate。
>
> Online 侧先做 Generic Trace/Span Normalization，把不同 Runtime 的数据统一成 runtime-neutral 模型，并明确 FAILURE、CANCELLED、TIMEOUT 才算 failure，UNKNOWN 不算 failure。
>
> Offline Evaluation 是工程上最复杂的一层。我用 PostgreSQL 实现 Run / Attempt / Result 生命周期，通过 Atomic Claim CAS 防止并发重复 claim，通过 Claim Token Fencing 防止 stale worker 恢复后写脏数据，Retry 新建 child Attempt 而不是修改旧事实，EvaluationResult 使用 append-only 模型。
>
> 在稳定 Result 上再做 Baseline/Candidate Comparison，按照 case/version/evaluator 对齐，得到 regression、improvement、unchanged 和 not-comparable。Criticality 由 caller 提供，RegressionReportService 最终生成 ReleaseDecision。
>
> Production Feedback 中，我没有把 Trace 自动当 TestCase，而是要求 caller 显式提供 sanitized input、expected output、criticality 和版本，再生成新的 DatasetVersion/TestCaseVersion。
>
> 最后做 closed-loop Demo 和 CI Adapter。CI 不重新判断 regression，只消费 ReleaseDecision；PASS 返回 0、业务 Gate FAIL 返回 2、Technical Error 返回 1。Stage4 最终 P0/P1 为 0，53 个跨阶段 PostgreSQL regression 和 580 个 unit 通过，但 production CI、多 Worker、Production Target 等仍诚实标为 Deferred。

------

# 42. 高频追问速答

| 问题                             | 核心答案                                                |
| -------------------------------- | ------------------------------------------------------- |
| Trace 为什么不是 Result？        | Observation provenance 和 Evaluation provenance 不同    |
| 为什么 UNKNOWN 不算 failure？    | 没有证据不能等价为失败                                  |
| 为什么 Run/Attempt 分开？        | Retry、并发、生命周期需要独立 execution fact            |
| CAS 解决什么？                   | 多 worker 同时 claim                                    |
| Fencing 解决什么？               | stale owner 恢复后继续写                                |
| Retry 为什么新建 Attempt？       | 保留执行历史                                            |
| Result 为什么 append-only？      | Regression 必须建立在稳定事实上                         |
| Criticality 谁拥有？             | Caller                                                  |
| Trace 为什么不自动进入 Dataset？ | sanitization / expected output / version authority 缺失 |
| Gate FAIL 为什么 exit 2？        | 区分业务失败和技术异常                                  |
| CLI 会判断 regression 吗？       | 不会，只消费 ReleaseDecision                            |
| GitHub Action 真跑过吗？         | 没有，当前仅 static workflow proven                     |
| Production Ready 吗？            | Partial                                                 |

------

# 43. 最容易答错的地方

必须避免这些说法：

```text
“Stage4 已 Production Ready”
```

错，应该是：

```text
Production Ready = PARTIAL
```

------

```text
“已经 Production Multi-worker exactly-once”
```

错。

已证明的是：

```text
Domain Concurrency Correctness
```

------

```text
“GitHub CI 已真实上线阻断生产发布”
```

错。

真实：

```text
Remote GitHub Actions = NOT_EXECUTED
production release integration = NO
```

------

```text
“Dataset 和 RegressionReport 都持久化”
```

错。

当前 Dataset Catalog / Report / Decision 仍未 durable。

------

# 44. 简历可以安全写什么

可以安全写：

> 基于 PandaProbe 改造 Agent Evaluation & Regression 平台，构建 Generic Trace Normalization、Trace Feedback、版本化 Evaluation Domain、Run/Attempt/Result 执行模型以及 Baseline/Candidate Regression 和 Critical Case Release Gate。

> 基于 PostgreSQL 实现 Evaluation Attempt 的 Atomic Claim CAS、Claim Token Fencing、Retry Lineage 和 append-only Result，保证并发执行下 ownership 和最终评估事实收敛。

> 构建 failing Trace → Dataset/TestCase → Evaluation → Regression → ReleaseDecision 的 deterministic closed-loop Demo，并实现 CI Adapter，将 PASS / Gate FAIL / Technical Error 映射为 0 / 2 / 1。

这些与 Final Closeout 的真实证据一致。

------

# 45. Stage4 最终知识框架

把所有内容压缩成四层即可：

```text
┌─────────────────────────────┐
│ Observation                 │
│ Trace / Span                │
│ Normalization / Metrics     │
└─────────────┬───────────────┘
              │ Evidence
              ▼
┌─────────────────────────────┐
│ Feedback Boundary           │
│ Sanitization                │
│ Expected Output             │
│ Dataset Versioning          │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ Evaluation Runtime          │
│ Dataset / TestCase          │
│ Run / Attempt / Result      │
│ CAS / Fencing / Retry       │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ Regression & Delivery       │
│ Baseline / Candidate        │
│ Report / ReleaseDecision    │
│ Demo / CI Adapter           │
└─────────────────────────────┘
```

这张图理解以后，Stage4 就基本掌握了。

------

# 46. 最终必须背住的 10 句话

> **1. Trace 是 Observation / Evidence，不是 Evaluation Truth。**

> **2. EvidenceCandidate 不等于 TestCase，中间必须存在显式 Feedback Boundary。**

> **3. Evaluation 的可信 provenance 来自版本化 Case + Run + Attempt + Result。**

> **4. CAS 解决并发 claim，Fencing 解决 stale owner 回写。**

> **5. Retry 是新 Attempt，不应该 reset 旧 Attempt。**

> **6. EvaluationResult 是 append-only fact，Regression 才有可信历史基础。**

> **7. Classification、Criticality、ReleaseDecision 必须分别有唯一 Owner。**

> **8. Production Trace 不能自动推导 sanitization、expected output、criticality 和 Dataset version。**

> **9. ReleaseDecision 是业务事实，Exit Code 是 Process Contract；业务 Gate FAIL 和 Technical Error 必须区分。**

> **10. Stage4 已经 Interview Ready，但只有 Partial Production Ready；准确描述证据边界比继续堆功能更重要。**

最终 Stage4 的正式状态可以压缩为：

```text
Stage4:
COMPLETE_AND_FROZEN

Core Evaluation / Regression:
TESTED

Open P0/P1:
0 / 0

Current HEAD:
580 unit
53 cross-phase PostgreSQL integration

Interview Ready:
YES

Production Ready:
PARTIAL

Recommended direction:
APPLY_FIRST
```