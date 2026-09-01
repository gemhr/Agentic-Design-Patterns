当前模型：GPT-5.6 Sol。

WP8 已通过，可以进入学习阶段。

状态确认：

```text
CROSS_REPOSITORY_SECURITY_E2E = PASS
```

WP8 完成了 Stage5-Phase2 最后一块工程闭环：将：

```text
Dataset
 ↓
Security Run Planning
 ↓
LocalAgent HTTP Execution
 ↓
FinalAnswer Evidence
 ↓
Security Evaluator
 ↓
Persistence
 ↓
Regression Comparison
 ↓
Security Release Gate
 ↓
CI Exit
```

串成真实跨仓 E2E。

但学习时需要重点注意一个非常重要的工程发现：

本 WP **不是简单验证“25/25 安全通过”**，反而发现了真实边界：

- 25 个 Case 中：
  - 15 个 `USER_INPUT` 可以真实执行；
  - 10 个 `NOT_MAPPED` 仍然属于 Coverage Debt。
- 真实 Dataset 下：
  - `sec-role-confusion-002`
  - `sec-tool-injection-001`

由于依赖 Tool Evidence，而当前 Contract 不支持，因此稳定产生：

```text
INCONCLUSIVE
```

导致完整 Dataset ALLOW 路径实际：

```text
ReleaseDecision = FAIL
reason = security_evaluation_inconclusive
```

这不是 Bug，而是正确暴露 Evaluation Contract Gap。

同时已经验证：

- Attack Regression → BLOCK
- Benign Over-refusal Regression → BLOCK
- Evaluation INCONCLUSIVE → BLOCK
- 可决定性 Coverage 下 ALLOW → PASS → CI exit 0



------

# Stage5-Phase2-WP8 学习文档

## 一、本 WP 涉及名词与概念速览

### Cross-Repository E2E（跨仓端到端测试）

验证多个独立仓库之间真实调用链是否符合 Contract。

------

### Integration Validation（集成验证）

验证已有模块组合是否正确，而不是开发新的核心能力。

------

### Test Double（测试替身）

用于替代真实外部依赖的可控实现，例如 deterministic judge。

------

### Deterministic Runtime Behavior（确定性运行行为）

固定输入输出的运行环境，用于验证系统逻辑，而不是验证模型能力。

------

### Evidence Capture（证据捕获）

保存 Agent 执行过程中可验证的事实，例如最终回答。

------

### FinalAnswerEvidenceV1

当前系统定义的最终回答证据结构，用于后续 Evaluation。

------

### Known Coverage Debt（已知覆盖债务）

当前系统明确知道但尚未支持验证的范围。

例如：

```text
RAG injection
Tool output injection
Agent message injection
```

------

### NOT_MAPPED

测试 Case 没有对应 Execution Target 映射。

不是失败，而是当前能力边界。

------

### INCONCLUSIVE（无法判定）

Evaluator 无法可靠判断 PASS/FAIL。

区别：

```text
FAIL = 行为确定错误

INCONCLUSIVE = 证据不足
```

------

### Release Gate（发布门禁）

根据 Evaluation 结果决定是否允许发布。

------

### Regression Attribution（回归归因）

判断 Candidate 相比 Baseline 是否产生退化。

------

### Frozen Gap（冻结缺口）

已经认可存在，并且不会导致当前 Gate 误判的已知缺口。

------

### Truthfulness Boundary（真实性边界）

工程声明中必须明确：

“已经证明什么”和“没有证明什么”。

------

# 二、本 WP 核心工程问题

## 问题1：为什么需要 Cross-Repository E2E，而不是单仓测试？

回答：

单模块测试只能证明：

```text
模块内部逻辑正确
```

但是 Agent 系统真实链路包含：

```text
Evaluation Platform
Runtime
Evidence
Evaluator
Persistence
Release
CI
```

任何一个 Contract 不一致都会导致：

例如：

- Run 成功，但 Evidence 丢失；
- EvaluationResult 存在，但 attempt_id 错绑；
- Release Gate 使用错误字段；
- CI exit 与 ReleaseDecision 不一致。

所以需要跨仓 E2E 验证：

> 从评估平台发起真实请求，到 Agent 返回结果，再到安全决策和 CI 出口的完整生命周期。

------

# 三、本 WP 架构理解

完整链路：

```
Security Dataset
        |
        v
SecurityRegressionService
        |
        v
SecurityRunPlan
        |
        v
LocalAgentHttpExecutionTarget
        |
        v
LocalAgent FastAPI
        |
        v
FinalAnswerEvidence
        |
        v
SecurityEvaluator
        |
        v
EvaluationResult
        |
        v
SecurityRunSummary
        |
        v
Comparison
        |
        v
SecurityReleasePolicy
        |
        v
ReleaseDecision
        |
        v
CI Exit Code
```

面试表达：

> 我没有把 Security Evaluation 做成独立系统，而是复用了已有 Evaluation Runtime 和 Release Pipeline，通过 Cross Repository E2E 验证 Dataset、Execution、Evidence、Evaluation、Regression、Release 的完整闭环。

------

# 四、为什么使用 deterministic runtime，而不是直接调用真实大模型？

这是本 WP 最重要面试点。

问题：

为什么不用真实 LLM 测试 Prompt Injection？

回答：

真实 LLM 测试存在：

1. 输出随机性；
2. 模型版本变化；
3. Prompt 漂移；
4. Judge 不稳定。

如果目标是验证：

```text
Evaluation Pipeline 是否正确
```

应该隔离变量。

所以：

使用：

```text
真实 LocalAgent HTTP
+
真实 Evidence Capture
+
真实 Persistence
+
deterministic runtime behavior
```

替换：

```text
模型行为
```

这样可以证明：

> Pipeline 能正确识别安全退化。

但不能证明：

> 生产模型一定安全。

------

# 五、为什么不直接 Mock LocalAgent？

这是高级追问。

错误方案：

```
AgentEvalOps
 |
Mock Response
 |
Evaluator
```

问题：

跳过：

- HTTP Contract
- Runtime Adapter
- Evidence Capture
- Execution Identity

无法发现跨仓问题。

所以采用：

```
AgentEvalOps
 |
真实 HTTP
 |
真实 LocalAgent FastAPI
 |
替换 chat_service
```

即：

测试真实系统边界，但控制不可预测因素。

------

# 六、为什么 25 个 Case 没有全部执行？

这是非常适合面试讲的 Bad Case。

初始预期：

```
25 cases
↓
25 executions
↓
Security Gate
```

实际：

```
25 cases

15 USER_INPUT
↓
真实执行

10 NOT_MAPPED
↓
Coverage Debt
```

原因：

当前 LocalAgent Runtime 只支持：

```text
USER_INPUT
```

但是：

```text
RAG Context
Tool Output
Agent Message
Reference Data
```

没有对应 Evidence Producer。

如果强行补：

会导致：

- 虚假覆盖；
- 假装验证未实现能力。

所以保留：

```text
Known Coverage Debt
```

------

# 七、为什么 INCONCLUSIVE 不能当 PASS？

这是 Security Evaluation 高频问题。

错误：

```
INCONCLUSIVE
↓
没有失败
↓
PASS
```

原因：

Security 场景：

```
无法确认安全
```

不等于：

```
确认安全
```

例如：

Tool Injection：

系统无法知道：

Agent 是否真的执行了危险动作。

所以：

```
Evidence 不足
=
Release 阻断
```

------

# 八、为什么完整 Dataset ALLOW 反而失败？

这是本 WP 最有价值的工程发现。

表面：

```
25 case
全部跑完
```

应该 PASS。

实际：

```
2 个 case
INCONCLUSIVE
```

导致：

```
Release FAIL
```

原因：

Release Gate 不是判断：

```
有没有明显错误
```

而是：

```
是否有足够证据证明可以发布
```

所以：

```
Evidence insufficient
=
不能自动放行
```

------

# 九、为什么需要 Known Coverage Debt？

如果没有：

```
NOT_MAPPED
=
FAIL
```

那么系统永远无法发布。

如果：

```
NOT_MAPPED
=
PASS
```

又会隐藏风险。

所以设计：

```
Frozen Known Gap
```

规则：

已有：

```
允许存在
```

新增：

```
阻断
```

即：

> 已知债务可以管理，但不能继续扩大。

------

# 十、工程构建方法类问题

## Q1：为什么安全评估系统不能只看最终回答？

回答：

最终回答只是一个输出。

完整 Agent 行为可能包括：

```
Tool Call
Retrieval
Memory
Planning
Agent Message
```

只看最终回答无法判断：

- 是否泄露信息；
- 是否执行危险动作；
- 是否违反权限边界。

因此需要：

```
Evidence Model
```

记录行为事实。

------

## Q2：为什么 Evaluation Pipeline 要和 Release Gate 分离？

回答：

Evaluator：

回答：

> 这个行为是否满足评价标准？

Release Gate：

回答：

> 当前版本是否允许发布？

两个职责不同。

否则：

Evaluator 一旦修改，会直接改变发布策略。

工程上应该：

```
Evaluation Result
        |
        v
Release Policy
```

解耦。

------

## Q3：为什么不用一个总分决定安全？

例如：

```
Security Score = 95%
```

问题：

安全不是平均指标。

一个：

```
Critical Failure
```

不能被：

```
99 个 PASS
```

抵消。

所以采用：

```
Blocking Condition
```

而不是：

```
Weighted Score
```

------

## Q4：为什么 E2E 需要测试失败路径？

因为生产系统最危险的是：

```
失败但是错误放行
```

所以必须验证：

- Attack Regression → BLOCK
- Over-refusal → BLOCK
- Evaluation Failure → BLOCK

不仅验证：

```
PASS
```

------

# 十一、30 秒面试版本

> 我在 AgentEvalOps 中实现了一套 Prompt Injection Security Cross Repository E2E 流程，把 Security Dataset、LocalAgent HTTP Execution、Evidence Capture、Security Evaluator、Regression Comparison、Release Gate 和 CI Exit 串起来。测试过程中没有直接 Mock Agent 返回，而是保持真实 HTTP 和 Evidence 链路，通过 deterministic runtime 控制模型行为，从而验证 Evaluation Pipeline 的正确性。最终发现当前系统真实支持 15/25 个 Security Case，另外 10 个属于未映射 Trust Boundary，并通过 Known Coverage Debt 管理，而不是伪造覆盖。

------

# 十二、2 分钟面试版本

> 在完成 Security Release Gate 后，我继续建设 Cross Repository Security E2E，目标不是增加新的 Security Framework，而是验证已有 Evaluation Pipeline 在真实跨仓环境下是否闭环。
>
> 首先我复用了已有 Prompt Injection Dataset、Security Regression Runner、LocalAgent HTTP Adapter、Evidence Capture、Security Evaluator 和 Release Policy。测试链路从 AgentEvalOps 发起，通过真实 HTTP 调用 LocalAgent Evaluation Endpoint，再经过 FinalAnswerEvidence 捕获、Evaluation Result 持久化、Baseline/Candidate Comparison，最终进入 ReleaseDecision 和 CI Exit。
>
> 实现过程中我没有直接 Mock LocalAgent 响应，因为这样无法验证 HTTP Contract、Execution Identity 和 Evidence Wiring。因此采用真实 LocalAgent 服务，但是替换 deterministic runtime behavior，让测试关注 Evaluation Pipeline，而不是生产模型随机性。
>
> 测试过程中发现一个重要边界：原计划 25 个 Case 全覆盖，但实际只有 15 个 USER_INPUT Case 可以执行，另外 10 个属于 RAG、Tool Output、Agent Message 等 Trust Boundary，没有对应 Execution Mapping。如果强行让它们通过，会形成虚假安全证明。因此保留为 Known Coverage Debt。
>
> 另外发现两个 Tool Evidence 相关 Case 在当前 Evaluator Contract 下只能得到 INCONCLUSIVE，而不是 PASS。最终 Release Gate 正确阻断，并区分了 Evaluation Evidence 不足和 Agent 行为失败。
>
> 这个过程证明了整个 Security Regression Pipeline 的工程可靠性，同时明确了当前系统安全能力边界。

------

# 十三、高频追问与回答

## 1. 为什么不用真实大模型测试？

答：

真实模型适合做能力评估，但不适合验证 Pipeline 正确性，因为存在随机性和版本漂移。E2E 阶段重点验证系统 Contract，因此使用 deterministic runtime。

------

## 2. deterministic runtime 是否降低真实性？

答：

降低的是模型行为真实性，不降低系统链路真实性。

HTTP、Runtime、Evidence、Persistence、Evaluation、Release 都是真实链路。

------

## 3. 为什么发现 Coverage Debt 不补？

答：

因为补 Coverage Debt 需要新增对应 Evidence Producer。

例如 Tool Output Injection，需要 Runtime 提供 Tool Execution Evidence。

如果当前没有 Contract，直接补测试属于伪覆盖。

------

## 4. INCONCLUSIVE 为什么阻断？

答：

Security 发布要求证明安全。

无法证明安全时不能自动放行。

------

## 5. 为什么 NOT_MAPPED 不直接 FAIL？

答：

因为当前系统明确知道这些能力未支持。

如果每次都 FAIL，会导致系统无法演进。

所以采用：

```
已有 Gap 冻结管理
新增 Gap 阻断
```

------

## 6. 为什么不用 Security Score？

答：

安全问题不能平均化。

一个 Critical Regression 不能被大量普通 PASS 抵消。

------

## 7. 这套系统现在能证明 LocalAgent 安全吗？

答：

不能。

它证明的是：

> Security Evaluation / Regression / Release Pipeline 正确运行。

生产 LLM Prompt Injection Resistance 仍需要真实模型测试和人工校准。

------

# 十四、本 WP 推荐面试材料文件名

建议：

```text
docs/interview/stage5_phase2_wp8_cross_repository_security_e2e.md
```

------

WP8 学习完成。
按照当前阶段流程，下一步不是继续开发，而是：

**进入 Stage5-Phase2 Final Gate。**