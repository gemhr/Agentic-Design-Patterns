# Part Four

我建议按这个顺序学：

````
6. Prioritization
7. Exploration and Discovery
## 第三梯队：理解即可，不必花太多时间

### 6. Prioritization（优先级排序）

这节有用，但通常不是面试核心。

它主要解决：

```
多个任务先做哪个；
多个工具先调用哪个；
多个错误先修哪个；
多个检索结果先看哪个；
多个目标冲突时怎么取舍。
```

在 Agent 系统里它确实存在，但你可以把它并入：

```
Planning；
Goal Setting；
Resource Aware Optimization；
Evaluation。
```

不需要单独花太多篇幅。

面试价值：**中。**

------

### 7. Exploration and Discovery（探索与发现）

这节偏进阶。

它讲的是 Agent 在不知道路径时，如何主动探索：

```
发现可用工具；
探索文件结构；
查找相关文档；
尝试不同 query；
发现任务入口；
探索代码依赖。
```

它对复杂 Agent 很有用，但面试中不是最高频。你可以理解它，但不必先深挖。

它可以和 RAG（检索增强生成）、Tool Use（工具使用）、Planning（规划）结合起来讲。

面试价值：**中低到中。**
````

## Chapter 15 Evaluation and Monitoring 评估与监控

这一节是第四章第一梯队里最重要的一节。它解决的问题不是“Agent能不能跑”，而是：

```text
Agent 跑得好不好？
哪里错了？
错因是什么？
改完有没有变好？
上线后是否稳定？
```

OpenAI Evals（OpenAI 评估框架）把 evals（评估）定位为用于测试 LLM 或基于 LLM 构建系统的框架；LangSmith（LangChain 监控评估平台）也把 evaluation（评估）、tracing（链路追踪）、monitoring（监控）和 feedback loop（反馈闭环）作为把 Agent 从 prototype（原型）推向 production（生产）的关键能力。([GitHub](https://github.com/openai/evals?utm_source=chatgpt.com))

### 是什么

**Evaluation and Monitoring（评估与监控）**，指的是：

```text
用一套指标、测试集、日志、追踪和反馈机制，持续判断 Agent 系统的效果、稳定性、成本、安全性和用户体验。
```

它分成两部分：

```text
Evaluation：
评估。通常发生在开发、测试、回归阶段，用来判断系统改动前后效果有没有提升。

Monitoring：
监控。通常发生在线上运行阶段，用来观察真实用户请求中的质量、错误、成本、延迟和风险。
```

一句话：

```text
Evaluation 负责“上线前测得准不准”，Monitoring 负责“上线后看稳不稳”。
```

再压缩一点：

```text
Evaluation 看质量，Monitoring 看运行。
```

### Evaluation 和 Monitoring 的区别

#### Evaluation：评估

Evaluation（评估）通常是离线的。

它回答：

```text
这次系统改动有没有让效果变好？
```

典型场景：

```text
修改 Router prompt 后，Router Accuracy 是否提升；
增加 hybrid retrieval 后，RAG Recall@K 是否提升；
优化 Tool schema 后，Tool Call Accuracy 是否提升；
增加 Reflection 后，Unsupported Claim Rate 是否下降。
```

Evaluation 的核心对象是：

```text
测试集；
预期答案；
指标；
自动 runner；
评估报告。
```

#### Monitoring：监控

Monitoring（监控）通常是线上的。

它回答：

```text
真实用户使用时，系统是否稳定、是否变差、是否有风险？
```

典型场景：

```text
最近 1 小时 LLM timeout 是否变多；
RAG retrieval_empty 是否异常升高；
工具调用失败率是否上升；
平均延迟是否超过阈值；
用户纠错率是否升高；
高风险工具是否都触发了审批。
```

Monitoring 的核心对象是：

```text
日志；
trace；
metrics；
alerts；
dashboard；
线上反馈。
```

OpenTelemetry（开源可观测框架）强调使用 metrics（指标）、logs（日志）和 traces（追踪）来分析软件性能和行为；这套可观测性思想同样适合 Agent 系统，只是 Agent 还要额外追踪 prompt、模型响应、token、工具调用和检索结果等信息。([OpenTelemetry](https://opentelemetry.io/?utm_source=chatgpt.com))

#### 二者对比

| 对比项 | Evaluation（评估）         | Monitoring（监控）                 |
| ------ | -------------------------- | ---------------------------------- |
| 阶段   | 上线前、改动后、回归时     | 上线后、真实运行中                 |
| 目标   | 判断效果好不好             | 判断系统稳不稳                     |
| 数据   | 测试集、标注样例、bad case | 真实请求、trace、日志、用户反馈    |
| 输出   | 分数、报告、失败样例       | dashboard、告警、趋势、异常        |
| 关注点 | 准确率、召回率、可用性     | 延迟、成本、错误率、风险、质量漂移 |

一句话：

```text
Evaluation 用来决定“能不能发版”，Monitoring 用来发现“上线后有没有变坏”。
```

### Agent 系统到底评估什么

Agent 不像普通分类模型，只评估一个 accuracy（准确率）不够。

因为 Agent 是多模块系统。

一个 Agent 请求可能经过：

```text
Router
→ Goal Extractor
→ Planner
→ RAG
→ Tool Use
→ Reflection
→ Human-in-the-Loop
→ Final Answer
```

所以评估也要分层。

#### 第一层：Router 评估

Router（路由器）负责判断用户任务应该走哪条路径。

例如：

```text
普通知识解释 → general_chat
代码审查 → code_expert
Excel 分析 → data_analyst
项目知识问答 → knowledge_expert
AW 脚本生成 → aw_script_expert
```

核心指标

```text
Router Accuracy：
路由正确率。

Unknown Route Rate：
未知路由比例。

Low Confidence Rate：
低置信度比例。

Misroute Rate：
错路由比例。
```

测试样例

```json
{
  "case_id": "router_001",
  "input": "帮我审查这段 Python 代码有没有并发问题",
  "expected_route": "code_expert"
}
```

面试表达

```text
Router 不能只靠肉眼试，我会准备一批带 expected_route 的测试集，统计 Router Accuracy，并把 routing_error 记录成 bad case。每次修改 Router prompt 或规则后，都跑回归测试，确认新版本没有破坏旧样例。
```

#### 第二层：Planner 评估

Planner（规划器）负责把任务拆成可执行步骤。

Planner 评估不是看它写得漂不漂亮，而是看：

```text
计划是否可执行；
步骤是否完整；
是否包含无关步骤；
是否遗漏关键步骤；
是否违反用户约束；
是否有停止条件。
```

核心指标

```text
Plan Executability：
计划可执行性。

Step Completeness：
步骤完整性。

Constraint Compliance：
约束遵守率。

Over-planning Rate：
过度规划率。

Missing Step Rate：
关键步骤遗漏率。
```

示例

用户请求：

```text
根据 86 的 A、B 列匹配 85 和 8011，把 86 的 N 列覆盖到目标表 O 列。
```

好的 Planner 输出应该包含：

```text
1. 检查文件是否存在；
2. inspect_excel 查看 sheet 和列；
3. 确认源 sheet、目标 sheet、key columns、source column、target column；
4. 生成写入计划；
5. 触发 Human-in-the-Loop 审批；
6. 备份文件；
7. 执行覆盖；
8. 返回匹配行数、更新行数和失败行。
```

如果 Planner 直接跳到“执行覆盖”，就遗漏了确认和备份。

#### 第三层：Tool Use 评估

Tool Use（工具使用）评估非常关键，因为 Agent 真正产生外部影响，通常都发生在工具层。

要评估什么

```text
工具是否选对；
参数是否正确；
是否触发权限检查；
是否正确处理工具失败；
是否遵守高风险审批；
工具结果是否被正确使用。
```

核心指标

```text
Tool Selection Accuracy：
工具选择正确率。

Tool Argument Accuracy：
工具参数正确率。

Tool Execution Success Rate：
工具执行成功率。

Permission Check Pass Rate：
权限检查通过率。

Approval Trigger Rate：
审批触发率。

Tool Error Recovery Rate：
工具异常恢复率。
```

示例

```json
{
  "case_id": "tool_001",
  "input": "把 86 的 N 列按 AB 键覆盖到 85 的 O 列",
  "expected_tool": "copy_column_by_composite_key",
  "expected_arguments": {
    "source_sheet": "86",
    "target_sheet": "85",
    "key_columns": ["A", "B"],
    "source_column": "N",
    "target_column": "O"
  },
  "requires_approval": true
}
```

这里不只是看工具是否调用成功，还要看：

```text
工具名对不对；
sheet 对不对；
列对不对；
是否需要审批；
是否有备份或回滚策略。
```

#### 第四层：RAG 评估

RAG（检索增强生成）评估是你的项目里最值得重点做的部分之一。

Ragas（RAG 评估框架）提供了面向 RAG 应用和 Agentic workflow（智能体工作流）的指标；其文档中列出了 faithfulness（忠实度）、answer relevancy（答案相关性）、context precision（上下文精确率）、context recall（上下文召回率）等常用评估维度。([docs.ragas.io](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/?utm_source=chatgpt.com))

RAG 分层评估

RAG 至少要分三层：

```text
检索评估；
生成评估；
引用评估。
```

##### 检索评估

关注：

```text
有没有找对资料。
```

核心指标：

```text
Recall@K：
正确文档是否出现在 top_k 检索结果中。

Precision@K：
top_k 结果中有多少是相关的。

Hit Rate：
是否至少命中一个正确文档。

MRR：
正确结果出现得是否靠前。
```

对你的 LocalAgent 最重要的是：

```text
Recall@K
```

因为正确文档没召回，后面生成一定不可靠。

##### 生成评估

关注：

```text
答案是否忠实、完整、有用。
```

核心指标：

```text
Faithfulness：
答案是否忠实于检索内容。

Answer Completeness：
答案是否覆盖关键点。

Unsupported Claim Rate：
无依据结论比例。

Answer Usefulness：
答案对用户是否有实际帮助。
```

##### 引用评估

关注：

```text
引用是否正确支持答案。
```

核心指标：

```text
Citation Accuracy：
引用准确率。

Citation Hit Rate：
关键结论是否有引用。

Citation Mismatch Rate：
引用错配率。
```

##### RAG bad case 分类

```text
retrieval_empty：检索为空；
retrieval_miss：没召回正确文档；
retrieval_noise：召回无关内容太多；
query_rewrite_error：查询改写错；
metadata_filter_error：过滤条件错；
chunk_boundary_error：chunk 切坏；
citation_mismatch：引用错配；
unsupported_claim：答案无依据；
stale_context：检索到过期内容；
permission_leak：权限泄漏。
```

这套分类非常适合放进你的自动评估平台。

#### 第五层：Reflection 评估

Reflection（反思）不是用了就一定有效。

要评估：

```text
它有没有发现错误；
有没有修正错误；
有没有误伤正确答案；
有没有引入新错误。
```

核心指标

```text
Reflection Detection Rate：
反思发现问题的比例。

Reflection Repair Rate：
反思成功修复问题的比例。

False Positive Rate：
把正确答案误判为错误的比例。

Regression Rate：
修复后引入新错误的比例。
```

示例

如果原答案有 unsupported claim（无依据结论），Reflection 应该能发现并要求删除或标注为推断。

#### 第六层：Goal 评估

Goal Setting and Monitoring（目标设定与监控）也要评估。

它关注：

```text
Agent 是否理解了用户目标；
是否完成关键子目标；
是否遵守约束；
是否在该停止时停止。
```

核心指标

```text
Goal Completion Rate：
目标完成率。

Sub-goal Completion Ratio：
子目标完成比例。

Constraint Violation Rate：
约束违反率。

Goal Drift Rate：
目标偏离率。

Stop Accuracy：
停止判断准确率。

Over-execution Rate：
过度执行率。
```

示例

用户要求：

```text
只基于上传论文内容给审稿意见，不要编造文中没有的数据。
```

评估时就要检查：

```text
是否只基于论文；
是否指出“文中未提供”；
是否编造了实验数据；
是否完成所有审稿维度。
```

#### 第七层：Exception Recovery 评估

Exception Handling and Recovery（异常处理与恢复）也必须可评估。

核心指标

```text
Recovery Success Rate：
恢复成功率。

Safe Stop Correctness：
安全停止是否正确。

Retry Success Rate：
重试成功率。

Fallback Success Rate：
降级成功率。

Parameter Repair Success Rate：
参数修复成功率。

Unhandled Exception Rate：
未处理异常比例。
```

示例

如果 `sheet_not_found` 发生，系统应该：

```text
1. 捕获异常；
2. 标记 recoverable=true；
3. 自动调用 inspect_excel；
4. 如果仍无法确定，触发 Human-in-the-Loop；
5. 最终恢复或 safe stop。
```

评估时就看这条链路有没有完整执行。

#### 第八层：Human-in-the-Loop 评估

Human-in-the-Loop（人类在环）不是触发越多越好，而是要触发得合理。

核心指标

```text
Human Intervention Rate：
人工介入率。

Approval Trigger Accuracy：
审批触发准确率。

Approval Reject Rate：
审批拒绝率。

Modification Rate：
用户修改参数比例。

Manual Override Rate：
人工接管率。

Missed Approval Rate：
应该审批但没审批的比例。
```

最严重的是：

```text
Missed Approval Rate
```

比如删除文件、覆盖数据、执行 shell 却没有触发审批，这是安全事故。

#### 第九层：端到端答案评估

最终用户看到的是答案，所以还要评估 Final Answer（最终答案）。

核心指标

```text
Answer Correctness：
答案正确性。

Answer Completeness：
答案完整性。

Answer Helpfulness：
答案有用性。

Format Compliance：
格式遵守率。

Instruction Following：
指令遵守率。

Hallucination Rate：
幻觉率。

User Satisfaction：
用户满意度。
```

示例

用户要求：

```text
给出可直接放入 notes.md 的答案。
```

那评估时要检查：

```text
是否完整；
是否结构清楚；
是否能直接复制；
是否没有重复前文已讲定义；
是否符合用户偏好的英文专属名词翻译约束。
```

#### 第十层：系统运行监控

除了质量，还要监控运行状态。

核心指标

```text
Latency：
延迟。

Token Usage：
token 使用量。

Cost：
成本。

LLM Error Rate：
模型请求错误率。

Tool Error Rate：
工具错误率。

Timeout Rate：
超时率。

Concurrency：
并发数。

Queue Length：
队列长度。

Memory Usage：
内存使用。

Embedding Latency：
向量化耗时。

Retrieval Latency：
检索耗时。
```

这些指标决定系统能不能长期运行。

### 离线评估怎么做

离线评估的核心是测试集。

#### 测试集结构

你可以设计统一测试样例：

```json
{
  "case_id": "case_001",
  "task_type": "rag_qa",
  "input": "AsyncLLMClient 为什么默认 trust_env=False？",
  "expected_route": "knowledge_expert",
  "expected_tools": ["search_knowledge_base"],
  "expected_docs": ["async_qwen_proxy_issue.md"],
  "expected_answer_points": [
    "避免公司内网请求走系统代理",
    "异步请求更稳定",
    "连接池参数可配置"
  ],
  "constraints": [
    "必须基于项目笔记",
    "不能编造"
  ]
}
```

#### Runner 流程

```text
读取测试集
→ 调用 Agent
→ 记录 trace
→ 评估 route
→ 评估 plan
→ 评估 tool call
→ 评估 retrieval
→ 评估 final answer
→ 输出报告
```

#### 报告示例

```json
{
  "run_id": "eval_20260708_001",
  "total_cases": 100,
  "router_accuracy": 0.91,
  "tool_call_accuracy": 0.86,
  "rag_recall_at_5": 0.82,
  "citation_accuracy": 0.78,
  "goal_completion_rate": 0.84,
  "recovery_success_rate": 0.72,
  "failed_cases": [
    {
      "case_id": "rag_017",
      "error_type": "retrieval_miss",
      "root_cause": "query rewrite missing project keyword"
    }
  ]
}
```

### 线上监控怎么做

线上监控的核心是 trace + metrics + alert。

#### Trace

Trace（链路追踪）记录一次用户请求完整经过。

例如：

```text
request_id
→ router_result
→ goal
→ plan
→ tool_calls
→ rag_results
→ exceptions
→ approvals
→ final_answer
→ feedback
```

#### Metrics

Metrics（指标）记录可聚合的数值。

例如：

```text
平均延迟；
错误率；
工具失败率；
RAG 检索为空率；
审批触发率；
用户纠错率；
token 成本。
```

#### Alert

Alert（告警）在异常升高时通知。

例如：

```text
LLM timeout rate > 10%；
tool_error_rate > 5%；
retrieval_empty_rate > 20%；
missed_approval_rate > 0；
average_latency > 10s。
```

#### Feedback Loop

Feedback Loop（反馈闭环）把线上失败转成离线测试样例。

流程：

```text
线上失败
→ 记录 trace
→ 分类 bad case
→ 加入测试集
→ 修复系统
→ 跑回归
→ 再上线
```

这也是 LangSmith 文档里强调的评估工作流思路：配置线上 evaluator（评估器）、实时监控，并建立反馈闭环。([Docs by LangChain](https://docs.langchain.com/langsmith/evaluation?utm_source=chatgpt.com))

### Bad Case Taxonomy

Bad Case Taxonomy（坏例分类体系）是 Evaluation and Monitoring 的核心资产。

你可以沿用这套：

```text
routing_error：
路由错误。

planning_error：
规划错误。

tool_selection_error：
工具选择错误。

tool_argument_error：
工具参数错误。

tool_execution_error：
工具执行错误。

retrieval_empty：
检索为空。

retrieval_miss：
检索漏召回。

retrieval_noise：
检索噪声。

citation_mismatch：
引用错配。

unsupported_claim：
无依据结论。

goal_drift：
目标偏离。

constraint_violation：
约束违反。

approval_missing：
缺少审批。

recovery_failed：
恢复失败。

format_error：
格式错误。

answer_hallucination：
答案幻觉。
```

每个 bad case 都应该记录：

```text
输入是什么；
期望是什么；
实际是什么；
错误模块；
错误类型；
根因；
修复建议；
是否已加入回归测试。
```

### 这一节面试怎么讲

可以这样说：

```text
Evaluation and Monitoring 是我理解中 Agent 工程化最关键的能力之一。因为 Agent 不是单一模型调用，而是由 Router、Planner、RAG、Tool Use、Reflection、Human-in-the-Loop 等多个模块组成，所以不能只靠人工体验判断效果，而要分模块建立评估体系。
```

继续说：

```text
在离线 Evaluation 阶段，我会构建测试集和 bad case 集，分别评估 Router Accuracy、Tool Call Accuracy、RAG Recall@K、Citation Accuracy、Goal Completion Rate、Recovery Success Rate 等指标。每次修改 prompt、工具 schema、检索策略或路由规则后，都通过 runner 批量回归，比较改动前后的指标。
```

再补线上：

```text
在在线 Monitoring 阶段，我会记录完整 trace，包括用户输入、路由结果、目标、计划、工具调用、RAG 检索结果、异常恢复、审批事件和最终答案，同时监控 latency、token cost、LLM error rate、tool error rate、retrieval_empty_rate、approval_missing_rate 等指标。线上失败样例会进入 bad case taxonomy，再转成离线回归测试，形成持续优化闭环。
```

结合 LocalAgent：

```text
在 LocalAgent 中，我会把 Evaluation and Monitoring 作为自动评估与回归测试平台的核心。底层用 SQLite / JSONL 管理测试集、运行结果和 bad case；runner 批量执行 Agent 请求；评估器分别计算 Router、Tool、RAG、Citation、Goal、Recovery 和 HITL 指标；最后生成报告，告诉我哪类错误下降了，哪类错误变多了。这样 LocalAgent 就不是一个只能演示的 Agent，而是一个可以持续迭代的工程系统。
```

### 必须掌握

#### 基础知识

##### 为什么 Agent不能只靠人工体验评估？

Agent 不能只靠人工体验评估，因为人工体验有很强的主观性、偶然性和不可复现性。

如果只是手动问几个问题，然后觉得“效果还可以”，会有几个问题。

1. 覆盖范围太小

​	人工体验通常只能测试少量样例。

​	比如你手动测了：

```text
1. 一个普通问答；
2. 一个代码审查；
3. 一个 Excel 分析；
4. 一个 RAG 问答。
```

​	这些样例通过了，不代表系统整体可靠。

​	真实用户可能问：

```text
1. 模糊任务；
2. 多轮任务；
3. 带约束任务；
4. 工具参数复杂的任务；
5. RAG 检索不到的任务；
6. 高风险写操作；
7. 多 Agent 协作任务；
8. 异常恢复任务。
```

​	人工体验很难覆盖这些边界情况。

2. 无法稳定复现

​	同一个 Agent，在不同时间、不同模型状态、不同上下文下，输出可能不同。

​	如果没有固定测试集，就很难判断：

```text
这次变好是因为真的优化了；
还是因为模型这次刚好运气好。
```

​	所以必须有固定的 eval set（评估集），用同一批样例反复测试。

3. 无法量化改进

​	人工体验只能说：

```text
感觉更好了。
感觉没以前稳定。
这个回答还行。
```

​	但工程上需要知道：

```text
Router Accuracy 提升了多少；
Tool Call Accuracy 下降了多少；
RAG Recall@K 有没有提高；
Citation Accuracy 有没有改善；
Unsupported Claim Rate 有没有降低；
Latency 有没有变长；
Cost 有没有增加。
```

​	没有指标，就无法判断一次改动到底是收益还是副作用。

4. 容易忽略隐藏错误

​	Agent 的错误有时不会体现在最终答案里。

​	例如：

```text
Router 路由错了，但最终答案勉强答对；
RAG 检索错了，但模型凭记忆答对；
工具参数错了，但没有真正执行写操作；
Reflection 没有发现 unsupported claim；
Human-in-the-Loop 没有触发，但这次刚好没造成事故。
```

​	只看人工体验，很容易漏掉这些系统内部问题。

5. 无法做回归测试

​	Agent 系统每次修改 prompt（提示词）、schema（结构约束）、retrieval（检索）、router（路由器）、tool（工具）后，都可能引入新问题。

​	比如：

```text
优化了 RAG 检索；
结果 Router 路由变差了。

优化了 Tool Call 参数；
结果生成答案格式不稳定了。

减少了 token 消耗；
结果答案完整性下降了。
```

​	如果没有自动评估，就无法发现这种回归。

6. 面试表达

```text
Agent 不能只靠人工体验评估，因为人工测试覆盖有限、主观性强、不可复现，也无法量化改动前后的效果。真实 Agent 系统由 Router、Planner、RAG、Tool Use、Reflection、Human-in-the-Loop 等多个模块组成，只看最终体验很容易漏掉内部错误。工程上应该建立固定测试集、bad case 集、指标体系和批量 runner，每次修改 prompt、schema、retrieval 或 router 后都做回归测试，用指标判断系统是否真的变好。
```

一句话：

```text
人工体验适合发现问题，自动评估适合稳定衡量问题。
```

##### 为什么 Agent 要分模块评估，而不是只评估最终答案？

Agent 要分模块评估，是因为最终答案只是结果，不能告诉你错误发生在哪个环节。

一个完整 Agent 请求可能经过：

```text
用户输入
→ Router
→ Goal Extractor
→ Planner
→ RAG
→ Tool Use
→ Reflection
→ Human-in-the-Loop
→ Final Answer
```

如果最终答案错了，可能原因很多。

1. 只看最终答案，无法定位问题

​	例如用户问：

```text
AsyncLLMClient 为什么默认 trust_env=False？
```

​	最终答案错了，可能是：

```text
Router 把问题路由到了 general_chat，而不是 knowledge_expert；
Query Rewrite 没有补充 trust_env、proxy、qwen 等关键词；
RAG 没召回正确文档；
Context Builder 塞入了无关内容；
Generator 自己编造；
Citation Verifier 没发现引用错配；
Reflection 没有修正 unsupported claim。
```

​	只评估最终答案，只知道“错了”，不知道“为什么错”。

2. 分模块评估可以定位责任

​	每个模块有自己的指标。

```text
Router：
看 Router Accuracy。

Planner：
看计划是否完整、可执行、遵守约束。

Tool Use：
看工具是否选对、参数是否正确、是否触发审批。

RAG：
看 Recall@K、Faithfulness、Citation Accuracy。

Reflection：
看是否发现并修正错误。

Human-in-the-Loop：
看高风险操作是否正确触发审批。

Final Answer：
看答案是否正确、完整、有用、符合格式。
```

​	这样就能判断问题到底出在哪一层。

3. 分模块评估可以指导优化方向

​	不同错误对应不同修复方式。

```text
Router 错：
优化路由规则或 Router prompt。

Tool 参数错：
优化工具 schema、参数校验和参数修复。

RAG 没召回：
优化 chunk、metadata、query rewrite、hybrid retrieval。

答案无依据：
优化生成 prompt、citation verification、Reflection。

高风险没确认：
优化 tool risk_level 和 approval policy。
```

​	如果只看最终答案，就不知道该改哪里。

4. 分模块评估可以避免“修一个坏一个”

​	Agent 系统是链式结构，一个模块优化可能影响另一个模块。

​	例如：

```text
把 RAG top_k 从 5 调到 20：
Recall@K 可能提高；
但 context 噪声增加；
答案 Faithfulness 可能下降；
Latency 和 Cost 也可能上升。
```

​	所以必须同时看多个模块指标，而不是只看最终答案。

5. 面试表达

```text
Agent 不能只评估最终答案，因为最终答案只能说明结果对不对，不能说明错误来自哪里。一个 Agent 请求通常会经过 Router、Planner、RAG、Tool Use、Reflection、Human-in-the-Loop 等多个模块。最终答案错误可能是路由错、计划错、检索错、工具参数错、引用错配，也可能是生成阶段幻觉。工程上我会分模块评估，每层都有独立指标，例如 Router Accuracy、Tool Call Accuracy、RAG Recall@K、Citation Accuracy、Goal Completion Rate、Recovery Success Rate 等。这样才能定位问题、指导优化，并避免系统改动后产生隐藏回归。
```

一句话：

```text
最终答案评估告诉你“错没错”，分模块评估告诉你“错在哪”。
```

#### 进阶掌握

##### 如何设计统一测试集格式？

统一测试集格式的目标是：

```text
让不同类型的 Agent 任务都能用同一套结构管理、运行和评估。
```

一个测试样例不应该只包含 input，还应该包含任务类型、预期路由、预期工具、预期文档、预期答案点、约束和评估方式。

推荐格式：

```json
{
  "case_id": "case_001",
  "task_type": "rag_qa",
  "input": "AsyncLLMClient 为什么默认 trust_env=False？",
  "expected_route": "knowledge_expert",
  "expected_tools": [
    "search_knowledge_base"
  ],
  "expected_docs": [
    "async_qwen_proxy_issue.md",
    "llm_client_notes.md"
  ],
  "expected_keywords": [
    "AsyncLLMClient",
    "httpx.AsyncClient",
    "trust_env",
    "proxy",
    "qwen"
  ],
  "expected_answer_points": [
    "避免公司内网请求走系统代理",
    "异步请求更稳定",
    "连接池参数可配置"
  ],
  "constraints": [
    "必须基于项目笔记",
    "不能编造没有依据的内容"
  ],
  "evaluation": {
    "check_router": true,
    "check_tools": true,
    "check_retrieval": true,
    "check_answer": true,
    "check_citation": true
  },
  "tags": [
    "rag",
    "llm_client",
    "async"
  ]
}
```

1. 字段说明

```text
case_id：
测试样例唯一 ID。

task_type：
任务类型，例如 rag_qa、code_review、excel_tool、general_chat、tool_call。

input：
用户原始输入。

expected_route：
期望 Router 输出。

expected_tools：
期望调用哪些工具。

expected_arguments：
期望工具参数。

expected_docs：
RAG 期望召回哪些文档。

expected_answer_points：
最终答案应该覆盖的关键点。

constraints：
用户约束，例如不要联网、只基于文件、不要原地修改。

evaluation：
本样例需要检查哪些模块。

tags：
用于分类、筛选、统计。
```

2. 不同任务的测试样例

​	Tool Call 测试：

```json
{
  "case_id": "tool_001",
  "task_type": "excel_tool",
  "input": "根据 86 的 AB 列，把 N 列覆盖到 85 的 O 列",
  "expected_route": "data_analyst",
  "expected_tools": [
    "copy_column_by_composite_key"
  ],
  "expected_arguments": {
    "source_sheet": "86",
    "target_sheet": "85",
    "key_columns": ["A", "B"],
    "source_column": "N",
    "target_column": "O"
  },
  "requires_approval": true
}
```

​	Router 测试：

```json
{
  "case_id": "router_001",
  "task_type": "routing",
  "input": "帮我审查这段 Python 代码有没有并发问题",
  "expected_route": "code_expert"
}
```

​	RAG 测试：

```json
{
  "case_id": "rag_001",
  "task_type": "rag_qa",
  "input": "MCP 和 Tool Use 有什么区别？",
  "expected_route": "knowledge_expert",
  "expected_docs": [
    "mcp_notes.md",
    "tool_use_notes.md"
  ],
  "expected_answer_points": [
    "Tool Use 是会用工具",
    "MCP 是工具接入标准化",
    "MCP 包含 Host、Client、Server"
  ]
}
```

3. 设计原则

```text
1. 一个 case 只测试一个主要问题；
2. expected 字段尽量结构化；
3. 支持多模块评估；
4. 支持 tags 分类；
5. 支持 bad case 回归；
6. 支持后续扩展新指标。
```

##### 如何记录 trace？

Trace 是一次 Agent 请求的完整链路记录。

它的目标是：

```text
让每次请求都可以回放、诊断、评估和转 bad case。
```

一个完整 trace 应该记录：

```text
用户输入；
路由结果；
目标；
计划；
工具调用；
RAG 检索结果；
模型调用；
异常；
审批；
最终答案；
用户反馈。
```

1. 推荐 trace 结构

```json
{
  "trace_id": "trace_001",
  "request_id": "req_001",
  "user_input": "AsyncLLMClient 为什么默认 trust_env=False？",
  "started_at": "2026-07-08T10:00:00",
  "ended_at": "2026-07-08T10:00:05",
  "route": {
    "actual": "knowledge_expert",
    "confidence": 0.91
  },
  "goal": {
    "main_goal": "解释 AsyncLLMClient 默认 trust_env=False 的原因",
    "constraints": [
      "基于项目笔记回答"
    ]
  },
  "plan": [
    "检索 AsyncLLMClient 相关笔记",
    "检索 trust_env / proxy 相关记录",
    "基于检索结果生成答案"
  ],
  "tool_calls": [
    {
      "tool_name": "search_knowledge_base",
      "arguments": {
        "query": "AsyncLLMClient trust_env proxy qwen timeout"
      },
      "success": true,
      "elapsed_ms": 120
    }
  ],
  "rag": {
    "queries": [
      "AsyncLLMClient trust_env proxy qwen timeout"
    ],
    "retrieved_chunks": [
      {
        "chunk_id": "chunk_001",
        "source": "async_qwen_proxy_issue.md",
        "score": 0.89
      }
    ]
  },
  "exceptions": [],
  "approvals": [],
  "final_answer": "……",
  "metrics": {
    "latency_ms": 5000,
    "input_tokens": 1200,
    "output_tokens": 600,
    "tool_call_count": 1
  }
}
```

2. trace 需要服务哪些用途

```text
调试：
看 Agent 哪一步出错。

评估：
和 expected_route、expected_docs、expected_tools 对比。

监控：
统计延迟、成本、错误率。

回归：
把失败 trace 转成测试样例。

审计：
检查高风险工具是否审批。

学习：
把用户反馈和 bad case 沉淀下来。
```

3. 记录原则

```text
1. 每次用户请求都有 trace_id；
2. 每个工具调用都有输入、输出、耗时、状态；
3. RAG 结果要记录 query、chunk_id、source、score；
4. 异常要记录 error_type 和 recovery_action；
5. 审批要记录 approval_id 和 decision；
6. 敏感信息要脱敏；
7. trace 不能只存最终答案。
```

##### 如何把线上失败转成 bad case？

​	线上失败转 bad case，是 Evaluation and Monitoring 的核心闭环。

​	流程是：

```text
线上失败
→ 捕获 trace
→ 人工或自动判断失败原因
→ 分类 error_type
→ 提取 expected 和 actual
→ 写入 bad case 库
→ 加入回归测试集
→ 修复后重复验证
```

1. 什么线上失败值得转 bad case？

​	值得转的情况：

```text
1. 用户明确纠正；
2. 用户重新提问说明上次没答好；
3. 工具调用失败；
4. RAG 检索为空或检索错；
5. 高风险操作没有触发审批；
6. 最终答案出现 unsupported claim；
7. Router 路由错误；
8. 同类错误重复出现。
```

​	不一定转的情况：

```text
1. 用户临时输入错误；
2. 外部服务偶发不可用；
3. 用户取消任务；
4. 无法复现的短暂网络问题。
```

2. bad case 结构

```json
{
  "case_id": "badcase_001",
  "source_trace_id": "trace_001",
  "module": "rag",
  "error_type": "retrieval_miss",
  "user_input": "AsyncLLMClient 为什么默认 trust_env=False？",
  "expected": {
    "expected_docs": [
      "async_qwen_proxy_issue.md"
    ],
    "expected_answer_points": [
      "避免公司内网请求走系统代理",
      "异步请求更稳定"
    ]
  },
  "actual": {
    "retrieved_docs": [
      "routing_notes.md"
    ],
    "answer": "……"
  },
  "root_cause": "query rewrite 没有加入 trust_env、proxy、qwen 等关键词",
  "fix_suggestion": "优化 query rewrite，并加入 FTS5 关键词检索",
  "status": "open",
  "tags": [
    "rag",
    "retrieval_miss",
    "llm_client"
  ]
}
```

3. bad case 分类

```text
routing_error：
路由错误。

planning_error：
规划错误。

tool_selection_error：
工具选择错误。

tool_argument_error：
工具参数错误。

retrieval_empty：
检索为空。

retrieval_miss：
检索漏召回。

retrieval_noise：
检索噪声。

citation_mismatch：
引用错配。

unsupported_claim：
无依据结论。

approval_missing：
缺少审批。

recovery_failed：
恢复失败。

format_error：
格式错误。
```

4. 面试表达

```text
线上失败不能只看完就结束。我会把线上失败对应的 trace 提取出来，分析是 Router、Planner、Tool、RAG、Citation、Goal 还是 HITL 的问题，然后转成 bad case，记录 input、expected、actual、error_type、root_cause 和 fix_suggestion。修复后把它加入回归测试集，防止同类问题再次出现。
```

##### 如何做回归测试？

Regression Test 是回归测试，目标是确认系统改动没有破坏已有能力。

Agent 系统中，每次改动这些内容都应该跑回归：

```text
Router prompt；
Planner prompt；
Tool schema；
RAG chunk 策略；
query rewrite；
rerank 规则；
Reflection prompt；
Human-in-the-Loop 策略；
异常恢复策略。
```

1. 回归测试流程

```text
选择测试集
→ 运行当前版本 Agent
→ 记录结果和 trace
→ 计算指标
→ 和 baseline 对比
→ 输出失败 case
→ 判断是否允许合入
```

2. baseline 的作用

Baseline 是基线版本。

比如上一版系统的指标是：

```text
Router Accuracy = 0.90
Tool Call Accuracy = 0.84
RAG Recall@5 = 0.80
Citation Accuracy = 0.76
Average Latency = 5.2s
```

新版本跑完后：

```text
Router Accuracy = 0.92
Tool Call Accuracy = 0.82
RAG Recall@5 = 0.86
Citation Accuracy = 0.78
Average Latency = 7.8s
```

这说明：

```text
Router 和 RAG 变好了；
Tool Call 变差了；
延迟明显增加了。
```

不能只看一个指标提升。

3. 回归测试报告

```json
{
  "run_id": "regression_001",
  "baseline_run_id": "regression_000",
  "total_cases": 100,
  "metrics": {
    "router_accuracy": {
      "old": 0.90,
      "new": 0.92,
      "delta": 0.02
    },
    "tool_call_accuracy": {
      "old": 0.84,
      "new": 0.82,
      "delta": -0.02
    },
    "rag_recall_at_5": {
      "old": 0.80,
      "new": 0.86,
      "delta": 0.06
    },
    "avg_latency_ms": {
      "old": 5200,
      "new": 7800,
      "delta": 2600
    }
  },
  "failed_cases": [
    {
      "case_id": "tool_014",
      "error_type": "tool_argument_error"
    }
  ]
}
```

4. 通过标准

​	可以设置门槛：

```text
Router Accuracy 不得下降超过 2%；
RAG Recall@5 不得下降；
Citation Accuracy 不得下降；
Tool Call Accuracy 不得下降超过 1%；
Missed Approval Rate 必须为 0；
平均延迟不得增加超过 30%。
```

##### 如何比较两个版本的 Agent 效果？

比较两个版本不能只看“哪个回答看起来更好”，而要基于同一批测试集和同一套指标。

两个版本可以是：

```text
旧 prompt vs 新 prompt；
旧 router vs 新 router；
纯向量检索 vs hybrid retrieval；
无 rerank vs 有 rerank；
无 Reflection vs 有 Reflection；
小模型 vs 大模型。
```

1. 对比流程

```text
固定测试集
→ 固定运行环境
→ 分别运行版本 A 和版本 B
→ 记录 trace
→ 计算相同指标
→ 比较差异
→ 分析失败样例
→ 判断是否采用新版本
```

2. 对比维度

```text
质量：
答案正确率、完整性、有用性。

模块：
Router Accuracy、Tool Call Accuracy、RAG Recall@K。

可靠性：
Recovery Success Rate、Unhandled Exception Rate。

安全：
Approval Trigger Accuracy、Missed Approval Rate。

性能：
Latency、Token Usage、Cost。

稳定性：
多次运行波动。
```

3. A/B 对比报告

```json
{
  "experiment_id": "exp_hybrid_retrieval_001",
  "version_a": "vector_only",
  "version_b": "hybrid_retrieval",
  "total_cases": 80,
  "metrics": {
    "rag_recall_at_5": {
      "a": 0.72,
      "b": 0.84,
      "delta": 0.12
    },
    "citation_accuracy": {
      "a": 0.70,
      "b": 0.78,
      "delta": 0.08
    },
    "avg_latency_ms": {
      "a": 1800,
      "b": 2600,
      "delta": 800
    }
  },
  "decision": "accept_with_latency_monitoring"
}
```

4. 判断原则

```text
1. 不能只看平均分，要看失败 case；
2. 不能只看质量，也要看成本和延迟；
3. 不能只看整体指标，也要看不同 task_type；
4. 安全指标优先级高于体验指标；
5. 新版本不能让关键 bad case 回归。
```

##### 如何评估 RAG faithfulness 和 citation accuracy？

RAG faithfulness 是忠实度，关注答案是否忠实于检索内容。

Citation Accuracy 是引用准确率，关注引用是否真的支持对应结论。

1. Faithfulness 评估

​	Faithfulness 的问题是：

```text
答案中的每个关键结论，是否都能从 context 中找到依据？
```

​	评估流程：

```text
抽取答案中的 claims
→ 对每个 claim 查找 context 支持
→ 判断 supported / unsupported
→ 计算 unsupported claim 比例
```

示例：

```json
{
  "answer": "AsyncLLMClient 默认 trust_env=False 是为了避免公司内网请求走系统代理。",
  "claims": [
    {
      "claim": "AsyncLLMClient 默认 trust_env=False",
      "supported": true,
      "source": "chunk_001"
    },
    {
      "claim": "这样可以避免公司内网请求走系统代理",
      "supported": true,
      "source": "chunk_001"
    }
  ],
  "faithfulness": 1.0
}
```

​	如果答案说：

```text
这个设计还能提升模型推理能力。
```

​	但 context 没有这个内容，就属于 unsupported claim。

2. Citation Accuracy 评估

​	Citation Accuracy 的问题是：

```text
答案引用的 source 是否真的支持对应句子？
```

​	错误例子：

```text
答案说：RAG 使用 FTS5 和 Chroma 混合检索。
引用却指向了只讲 Memory 的 chunk。
```

​	这就是 citation mismatch。

​	评估流程：

```text
抽取答案中的引用；
找到引用对应 chunk；
判断 chunk 是否支持引用前的结论；
统计正确引用比例。
```

3. 两者区别

```text
Faithfulness：
答案有没有忠实于检索内容。

Citation Accuracy：
答案引用有没有指向正确依据。
```

​	可能出现：

```text
答案是忠实的，但引用错了；
答案引用格式正确，但内容没有依据；
答案部分有依据，部分是模型补充。
```

​	所以两个指标都要看。

##### 如何监控成本、延迟和错误率？

线上 Monitoring 必须监控成本、延迟和错误率，因为 Agent 系统很容易“效果还行，但跑不动、太贵、不稳定”。

1. 成本监控

​	成本主要来自：

```text
LLM 调用；
embedding 调用；
rerank 调用；
工具调用；
上下文长度；
重试次数；
多 Agent 并行。
```

​	关键指标：

```text
Total Token Usage：
总 token 使用量。

Input Tokens：
输入 token。

Output Tokens：
输出 token。

Cost per Request：
单次请求成本。

Cost per Task Type：
不同任务类型成本。

Tool Call Count：
工具调用次数。

RAG Retrieval Count：
检索次数。

Reflection Rounds：
反思轮数。
```

​	需要关注：

```text
某类任务成本是否异常升高；
某次改动是否导致 token 增加；
RAG top_k 调大后成本是否明显上升；
Reflection 是否带来过多额外调用。
```

2. 延迟监控

​	延迟主要来自：

```text
模型请求；
RAG 检索；
embedding；
rerank；
工具执行；
并行等待；
Human-in-the-Loop 审批等待。
```

​	关键指标：

```text
End-to-End Latency：
端到端延迟。

LLM Latency：
模型调用耗时。

Retrieval Latency：
检索耗时。

Tool Latency：
工具耗时。

Time to First Token：
首 token 时间。

Queue Time：
排队时间。

P95 / P99 Latency：
95 分位和 99 分位延迟。
```

​	平均值不够，要看 P95 和 P99，因为用户最容易感知长尾延迟。

3. 错误率监控

​	错误来源包括：

```text
LLM timeout；
LLM 5xx；
JSON parse error；
tool error；
retrieval_empty；
permission denied；
approval_missing；
recovery_failed；
unhandled exception。
```

​	关键指标：

```text
LLM Error Rate；
Tool Error Rate；
Timeout Rate；
Unhandled Exception Rate；
Retrieval Empty Rate；
Recovery Failed Rate；
Approval Missing Rate。
```

​	其中 `approval_missing` 这类安全错误应该零容忍。

4. trace 和 metrics 的关系

```text
trace 用于定位单次请求发生了什么；
metrics 用于观察整体趋势。
```

​	例如：

```text
metrics 发现 retrieval_empty_rate 最近升高；
再通过 trace 查看哪些 query 检索为空；
最后转成 bad case 修复。
```

##### 如何用评估结果指导 prompt、schema、retrieval、router 的优化？

评估的价值不是生成分数，而是指导怎么改系统。

不同指标异常，对应不同优化方向。

1. 指导 prompt 优化

​	如果出现：

```text
答案太泛；
格式不稳定；
遗漏关键点；
不遵守用户约束；
unsupported claim 太多。
```

​	优先优化 prompt。

​	优化方向：

```text
明确输出格式；
加入 success criteria；
要求只基于 context；
要求资料不足时说明；
加入反例；
加入检查清单。
```

​	示例：

```text
Unsupported Claim Rate 高
→ 在生成 prompt 中加入：
“如果检索资料没有支持某个结论，不要写入最终答案。”
```

2. 指导 schema 优化

​	如果出现：

```text
工具参数缺失；
字段名错误；
参数类型错误；
高风险工具没有审批；
工具结果结构不稳定。
```

​	优先优化 schema。

​	优化方向：

```text
增加 required 字段；
给字段加 description；
限制 enum；
增加参数校验；
把风险元数据加入 tool definition；
统一 ToolResult 和 AgentError。
```

​	示例：

```text
Tool Argument Accuracy 低
→ 优化工具 input schema；
→ 明确 source_sheet、target_sheet、key_columns、source_column、target_column；
→ 对 column 字段加示例。
```

3. 指导 retrieval 优化

​	如果出现：

```text
Recall@K 低；
retrieval_empty 高；
retrieval_noise 高；
citation_mismatch 高；
检索到过期文档。
```

​	优先优化 retrieval。

​	优化方向：

```text
优化 query rewrite；
加入关键词检索；
做 hybrid retrieval；
调整 chunk_size；
补充 metadata；
增加 rerank；
过滤 stale documents；
提高或降低 top_k。
```

​	示例：

```text
用户问 AsyncLLMClient，但 RAG 没召回 trust_env 相关笔记
→ query rewrite 增加 trust_env、proxy、qwen；
→ FTS5 加入关键词检索；
→ metadata 加 tags: llm_client、async。
```

4. 指导 router 优化

​	如果出现：

```text
Router Accuracy 低；
unknown_route 多；
低置信度多；
Excel 任务被路由到 general_chat；
代码审查任务被路由到 knowledge_expert。
```

​	优先优化 router。

​	优化方向：

```text
增加 route definition；
增加 few-shot examples；
加入规则 fallback；
限制 route enum；
输出 confidence；
低置信度触发澄清或默认安全路径。
```

​	示例：

```text
Excel 列匹配任务经常路由错
→ 在 Router prompt 中增加：
“涉及 sheet、列、单元格、xlsx、AB 列匹配、覆盖列的任务，优先路由到 data_analyst。”
```

5. 指标到优化动作映射表

| 指标异常                  | 可能原因         | 优化方向                                        |
| ------------------------- | ---------------- | ----------------------------------------------- |
| Router Accuracy 低        | 路由规则不清     | 优化 router prompt、增加规则 fallback           |
| Tool Argument Accuracy 低 | schema 不清      | 优化 tool schema、加参数校验                    |
| Recall@K 低               | 检索召回差       | query rewrite、hybrid retrieval、metadata       |
| Retrieval Noise 高        | 结果太杂         | rerank、metadata filter、相似度阈值             |
| Faithfulness 低           | 模型编造         | 强化生成 prompt、citation verification          |
| Citation Accuracy 低      | 引用错配         | claim-source 检查、引用格式约束                 |
| Recovery Success Rate 低  | 恢复策略不足     | 增加 fallback、参数修复、safe stop              |
| Approval Missing Rate 高  | 安全策略缺失     | 工具 risk_level、强制审批                       |
| Latency 高                | 调用链太长       | 缓存、减少 top_k、减少反思轮数                  |
| Cost 高                   | token 或调用过多 | context compression、小模型分层、限制 max_steps |

6. 最终闭环

​	完整优化闭环是：

```text
评估指标异常
→ 定位失败模块
→ 查看 trace
→ 生成 bad case
→ 分析 root cause
→ 修改 prompt / schema / retrieval / router
→ 跑回归测试
→ 对比新旧版本
→ 上线监控
```

一句话：

```text
评估不是为了打分，而是为了告诉你下一步该改哪里。
```

### 一句话总结

```text
Evaluation and Monitoring 的本质是：让 Agent 的质量、错误、成本、风险和改进效果都变得可观测、可量化、可回归。
```

再压缩一点：

```text
没有 Evaluation，就不知道改动有没有变好；
没有 Monitoring，就不知道上线后有没有变坏。
```

对你来说，这一节可以浓缩成：

```text
LocalAgent 要从 Demo 变成工程项目，Evaluation and Monitoring 是最关键的升级点。
```

## Chapter 17 Inter-Agent Communication（A2A）智能体间通信

这一节是对第一章 **Multi-Agent Collaboration（多智能体协作）** 的深化。

前面学 Multi-Agent Collaboration（多智能体协作）时，重点是：

```text
多个 Agent 按角色分工协作。
```

现在学 **Inter Agent Communication（智能体间通信）**，重点变成：

```text
多个 Agent 之间到底怎么传递任务、上下文、状态、结果和错误。
```

一句话：

```text
Multi-Agent Collaboration 解决“谁和谁协作”；
Inter Agent Communication 解决“它们怎么协作”。
```

再压缩一点：

```text
多 Agent 不是堆角色，关键是通信协议和状态管理。
```

### Inter Agent Communication 是什么

**Inter Agent Communication（智能体间通信）**，指的是：

```text
在多 Agent 系统中，不同 Agent 之间通过结构化消息、共享状态、事件流或协议机制交换任务、上下文、执行结果、错误信息和决策信号。
```

它关注的不是单个 Agent 怎么回答，而是多个 Agent 如何协同完成复杂任务。

例如你的 LocalAgent（本地智能体项目）里可能有：

```text
core_router；
planner；
data_analyst；
code_expert；
knowledge_expert；
aw_script_expert；
reviewer；
aggregator。
```

这些 Agent 之间必须通信。

否则系统就会变成：

```text
每个 Agent 各说各话；
任务状态不一致；
错误没人接；
结果没人汇总；
冲突没人裁决；
上下文重复传递；
最终答案不可控。
```

### 为什么这一节面试价值高

因为面试里讲多 Agent 时，很多人只能说：

```text
我设计了多个专家 Agent：
代码专家、数据专家、知识库专家、总结专家。
```

这还比较浅。

更工程化的回答应该是：

```text
我不仅设计了多个 Agent 角色，还设计了它们之间的消息结构、上下文传递方式、状态同步方式、错误传播机制、结果聚合机制和冲突裁决机制。
```

这就明显上升到系统设计层面。

面试官可能会追问：

```text
多个 Agent 怎么通信？
上下文怎么传？
谁负责调度？
一个 Agent 失败怎么办？
多个 Agent 结论冲突怎么办？
如何避免上下文爆炸？
如何记录多 Agent 执行链路？
```

所以这一节的面试价值很高。

### Agent 之间需要传什么

多 Agent 通信不是简单把一句自然语言扔给另一个 Agent。

通常需要传这些内容。

#### Task：任务

告诉目标 Agent 要做什么。

例如：

```text
请审查这段 Python 代码的并发问题。
```

或者：

```text
请检索 LocalAgent 中和 RAG 评估相关的笔记。
```

任务要尽量清楚，包括：

```text
目标；
输入；
约束；
期望输出；
截止条件。
```

#### Context：上下文

告诉目标 Agent 已知信息。

例如：

```text
用户当前在学习 Agentic Design Patterns；
本节是 Evaluation and Monitoring；
用户偏好英文专属名词首次出现带中文翻译；
回答要适合放入 notes.md。
```

没有上下文，目标 Agent 可能答偏。

但上下文不能无脑全传，否则会造成：

```text
token 过大；
无关信息干扰；
隐私泄露；
推理效率下降。
```

所以多 Agent 通信要考虑 **Context Passing（上下文传递）** 和 **Context Compression（上下文压缩）**。

#### State：状态

状态表示当前任务执行到了哪一步。

例如：

```text
route 已完成；
plan 已生成；
RAG 已检索；
tool_call 失败；
需要 human approval；
final answer 待 review。
```

状态对 Orchestrator（编排器）特别重要。

它要知道：

```text
哪个 Agent 完成了；
哪个 Agent 失败了；
哪个 Agent 还在等待；
是否可以进入下一步；
是否需要 recovery；
是否需要 safe stop。
```

#### Result：结果

每个 Agent 输出的结果应该结构化。

不要只返回一段自然语言。

例如 knowledge_expert 返回：

```text
summary；
sources；
confidence；
missing_info；
unsupported_claims；
recommended_next_step。
```

data_analyst 返回：

```text
matched_rows；
updated_rows；
failed_rows；
preview；
warnings；
requires_approval。
```

这样 Aggregator（聚合器）才能稳定汇总。

#### Error：错误

Agent 失败时也要结构化返回。

例如：

```text
error_type；
message；
stage；
recoverable；
recovery_suggestion；
partial_result。
```

不要只返回：

```text
我失败了。
```

因为 Orchestrator 需要根据 error_type 决定：

```text
retry；
fallback；
replan；
human-in-the-loop；
partial success；
safe stop。
```

#### Confidence：置信度

Agent 可以返回自己结果的置信度。

例如：

```text
confidence = 0.92
```

或者：

```text
high / medium / low
```

置信度可以帮助系统决定：

```text
是否需要 reviewer；
是否需要继续检索；
是否需要用户确认；
是否需要多 Agent 投票；
是否可以直接输出。
```

### 通信方式有哪些

Inter Agent Communication（智能体间通信）常见有四种模式。

#### Direct Message：直接消息

一个 Agent 直接把任务发给另一个 Agent。

例如：

```text
planner → code_expert
```

适合简单链路。

优点：

```text
简单；
容易实现；
延迟低。
```

缺点：

```text
耦合高；
难以扩展；
复杂任务容易混乱。
```

#### Orchestrator-Mediated Communication：编排器中介通信

所有 Agent 之间不直接互相调用，而是通过 Orchestrator（编排器）通信。

例如：

```text
user
→ orchestrator
→ router
→ planner
→ knowledge_expert
→ reviewer
→ aggregator
→ final answer
```

优点：

```text
控制集中；
状态清楚；
方便记录 trace；
方便做权限控制；
方便做异常恢复；
方便接入 guardrails。
```

缺点：

```text
Orchestrator 复杂度更高；
需要设计清楚状态机和消息格式。
```

对工程项目来说，这种方式最稳。

#### Blackboard Pattern：黑板模式

所有 Agent 共享一个公共状态区，叫 **Blackboard（黑板）**。

每个 Agent 可以读取黑板上的信息，也可以写入自己的结果。

例如：

```text
blackboard:
- user_goal
- plan
- retrieved_docs
- code_review_result
- data_analysis_result
- tool_errors
- final_draft
```

适合复杂协作任务。

优点：

```text
共享状态清楚；
多个 Agent 可以异步协作；
适合多轮迭代。
```

缺点：

```text
状态污染风险；
并发写入冲突；
需要权限和版本控制；
需要记录谁写了什么。
```

#### Event-Driven Communication：事件驱动通信

Agent 不直接互相调用，而是发布和订阅事件。

例如：

```text
route_completed；
plan_created；
tool_call_failed；
rag_retrieval_done；
approval_required；
review_completed。
```

你的 `[[ORCH]]` 事件就很适合这个模式。

优点：

```text
解耦；
可观测；
适合前端流式展示；
适合异步任务；
适合监控和回放。
```

缺点：

```text
实现复杂；
需要事件规范；
需要处理事件顺序和状态一致性。
```

#### 最推荐的工程组合

对于 LocalAgent，最推荐的不是单一模式，而是组合：

```text
Orchestrator-Mediated Communication
+ Structured Message
+ Shared State
+ Event Stream
```

也就是：

```text
Orchestrator 负责调度；
Structured Message 负责传参；
Shared State 负责保存任务上下文；
Event Stream 负责可观测和前端展示。
```

可以理解为：

```text
控制流走 Orchestrator；
数据流走 State；
观察流走 Event。
```

这句话很适合面试：

```text
在多 Agent 系统中，我会把控制流、数据流和观察流分开设计。
```

### 通信消息应该如何设计

Agent 之间通信最好使用 **Structured Message（结构化消息）**。

不要只传自然语言。

推荐消息结构：

```text
message_id；
trace_id；
from_agent；
to_agent；
message_type；
task；
context；
constraints；
expected_output；
payload；
status；
error；
metadata。
```

一个逻辑示例：

```text
message_id: msg_001
trace_id: trace_001
from_agent: orchestrator
to_agent: knowledge_expert
message_type: task_request
task: 检索 Evaluation and Monitoring 相关笔记
context: 用户正在学习第四章第一梯队
constraints: 英文专属名词首次出现加中文翻译
expected_output: 返回关键概念、来源、置信度
```

消息结构化的好处：

```text
方便调试；
方便回放；
方便评估；
方便监控；
方便权限控制；
方便异常恢复。
```

### 常见 message_type

可以设计这些消息类型。

```text
task_request：
任务请求。

task_result：
任务结果。

state_update：
状态更新。

tool_request：
工具调用请求。

tool_result：
工具结果。

error_report：
错误报告。

approval_request：
审批请求。

approval_response：
审批响应。

review_request：
审查请求。

review_result：
审查结果。

conflict_report：
冲突报告。

final_answer_draft：
最终答案草稿。
```

这些消息类型能覆盖大多数多 Agent 协作场景。

### Agent 通信中的状态管理

通信不能只看消息，还要看状态。

每个 Agent 执行任务时可以有状态：

```text
pending；
running；
succeeded；
failed；
blocked；
waiting_for_approval；
cancelled；
skipped。
```

例如 Excel 写入任务：

```text
data_analyst: running
guardrail: waiting_for_approval
tool_executor: blocked
orchestrator: waiting
```

状态管理可以帮助系统判断：

```text
是否继续；
是否等待用户；
是否重试；
是否跳过；
是否安全停止；
是否汇总 partial result。
```

### Agent 通信中的上下文管理

多 Agent 通信最容易出问题的是上下文。

#### 上下文过少

如果传得太少，目标 Agent 不知道背景。

例如：

```text
请回答这个问题。
```

但没有告诉它：

```text
用户在学哪一章；
之前学过什么；
输出要不要 notes.md 格式；
是否需要结合 LocalAgent。
```

结果就容易偏。

#### 上下文过多

如果传得太多，会造成：

```text
token 浪费；
模型注意力分散；
隐私风险增加；
旧信息干扰新任务；
不同 Agent 看到不该看的内容。
```

#### 推荐做法

传上下文时按角色裁剪。

例如：

```text
code_expert：
只给代码、报错、运行环境、用户目标。

knowledge_expert：
只给用户问题、检索范围、已知学习进度。

data_analyst：
只给文件路径、sheet、列、操作目标、约束。

reviewer：
只给最终草稿、任务目标、关键约束、引用来源。
```

原则：

```text
只传完成任务所需的最小上下文。
```

这就是 **Least Context Principle（最小上下文原则）**。

它和安全里的 **Least Privilege Principle（最小权限原则）** 很像。

### Agent 通信中的错误传播

多 Agent 系统中，错误不能丢。

如果某个 Agent 失败，它应该返回：

```text
error_type；
stage；
recoverable；
partial_result；
recovery_suggestion。
```

例如：

```text
knowledge_expert 检索失败：
error_type = retrieval_empty
recoverable = true
recovery_suggestion = 尝试 query rewrite 或扩大检索范围
```

Orchestrator 收到后可以：

```text
重写 query；
切换关键词检索；
要求用户补充；
继续使用 partial result；
safe stop。
```

错误传播的核心是：

```text
失败也要结构化。
```

否则系统只能“整体失败”。

### Agent 通信中的冲突处理

多个 Agent 可能给出冲突结论。

例如：

```text
code_expert 说这段代码并发安全；
reviewer 说存在竞态风险。
```

或者：

```text
knowledge_expert 检索到旧文档；
memory_agent 记忆里有新结论。
```

冲突处理策略：

```text
1. 优先可信来源；
2. 优先最新信息；
3. 要求 Reviewer 仲裁；
4. 要求继续检索；
5. 标注不确定性；
6. 让用户裁决。
```

可以设计一个 **Conflict Resolution（冲突解决）** 模块。

它判断：

```text
冲突是什么；
哪些来源支持各自结论；
哪个来源更可信；
是否需要补充信息；
是否能自动裁决；
是否需要 Human-in-the-Loop。
```

### Agent 通信中的结果聚合

多个 Agent 输出后，需要 Aggregator（聚合器）汇总。

Aggregator 不是简单拼接。

它要做：

```text
去重；
排序；
合并相同结论；
保留分歧；
过滤低置信度内容；
补充引用；
统一格式；
生成最终答案。
```

例如用户问：

```text
分析这个项目哪里还能优化。
```

可能有三个 Agent 输出：

```text
code_expert：代码结构问题；
knowledge_expert：项目文档和历史设计；
evaluation_agent：测试覆盖和 bad case 体系。
```

Aggregator 要合成一个整体回答，而不是直接把三段贴出来。

### Agent 通信和 `[[ORCH]]` 事件

你的 LocalAgent 很适合把通信过程映射成 `[[ORCH]]` 事件。

可以有这些事件：

```text
agent_message_sent；
agent_message_received；
agent_started；
agent_completed；
agent_failed；
agent_blocked；
agent_result_aggregated；
agent_conflict_detected；
agent_review_requested；
agent_review_completed。
```

例如：

```text
[[ORCH]] agent_started: knowledge_expert
[[ORCH]] agent_completed: knowledge_expert
[[ORCH]] agent_started: reviewer
[[ORCH]] agent_review_completed
[[ORCH]] final_answer_ready
```

这样前端和日志都能看懂 Agent 协作过程。

### 常见坑

#### 多个 Agent 只是 prompt 名字不同

例如：

```text
你是代码专家；
你是数据专家；
你是总结专家。
```

但没有通信结构、状态管理、错误传播、聚合逻辑。

这只是“角色扮演”，不是工程化多 Agent。

### Agent 互相传整段对话

这样会造成：

```text
token 浪费；
隐私泄露；
上下文污染；
旧信息干扰；
成本上升。
```

应该传最小必要上下文。

#### 结果只用自然语言传递

自然语言难以稳定解析。

应该结构化：

```text
summary；
data；
confidence；
sources；
error；
next_action。
```

#### 没有错误协议

Agent 失败时只返回“我失败了”，Orchestrator 无法恢复。

必须返回 error_type 和 recovery_suggestion。

#### 没有冲突解决

多个 Agent 结论冲突时，系统直接拼接输出，会让用户困惑。

应该有 Reviewer（审查器）或 Conflict Resolver（冲突解决器）。

### 和前面章节的关系

#### 和 Routing 的关系

Routing（路由）决定任务交给谁。

Inter Agent Communication（智能体间通信）决定交给之后怎么协作。

```text
Routing 负责选 Agent；
Communication 负责 Agent 之间传递信息。
```

#### 和 Planning 的关系

Planning（规划）决定任务步骤。

Inter Agent Communication（智能体间通信）负责把步骤分发给对应 Agent。

#### 和 Tool Use 的关系

有些 Agent 会调用工具。

通信时要把工具调用请求和结果结构化传回 Orchestrator。

#### 和 Evaluation and Monitoring 的关系

通信过程必须可追踪。

否则很难评估：

```text
哪个 Agent 出错；
哪个消息丢失；
哪个阶段耗时高；
哪个结果被 aggregator 错误使用。
```

#### 和 Guardrails 的关系

Agent 通信必须经过安全边界。

例如：

```text
某个 Agent 不能把敏感上下文传给无权限 Agent；
某个 Agent 不能让另一个 Agent 越权调用工具；
RAG 文档内容不能作为跨 Agent 指令传播。
```

### 面试表达

可以这样说：

```text
Inter Agent Communication 是多 Agent 系统工程化的关键。多 Agent 不是简单定义几个角色，而是要设计它们之间如何传递任务、上下文、状态、结果和错误。否则多个 Agent 很容易各说各话，出现状态不一致、结果冲突、错误丢失和上下文膨胀。
```

继续说：

```text
工程上我更倾向于 Orchestrator-Mediated Communication，也就是所有 Agent 通过 Orchestrator 通信。Orchestrator 负责任务分发、状态维护、上下文裁剪、错误恢复、审批触发、结果聚合和 trace 记录。Agent 之间传递的不是纯自然语言，而是 Structured Message，包括 trace_id、from_agent、to_agent、task、context、constraints、expected_output、result、confidence、error 等字段。
```

结合 LocalAgent 可以这样说：

```text
在 LocalAgent 中，我会让 core_router 先判断任务类型，planner 生成步骤，再由 Orchestrator 分发给 code_expert、data_analyst、knowledge_expert 或 aw_script_expert。每个 Agent 返回统一结构，包括 success、summary、data、confidence、sources、warnings、error 和 next_action。所有通信过程都写入 trace，并通过 [[ORCH]] 事件流展示，例如 agent_started、agent_completed、agent_failed、agent_conflict_detected 和 agent_result_aggregated。这样多 Agent 协作就不是简单 prompt 角色扮演，而是有通信协议、状态管理和可观测性的工程系统。
```

### 必须掌握

#### 如何设计 AgentMessage？

AgentMessage 用于描述一次 Agent 之间的通信。

它不应该只是一段自然语言，而应该是一个结构化对象，明确表示：

```text
谁发送；
发送给谁；
要完成什么任务；
需要哪些上下文；
有哪些约束；
期望返回什么；
当前属于哪一次执行链路。
```

**推荐字段**

```python
MessageType = Literal[
    "task_request",
    "task_result",
    "state_update",
    "error_report",
    "review_request",
    "review_result",
    "conflict_report",
]


@dataclass
class AgentMessage:
    message_id: str
    trace_id: str
    parent_message_id: str | None

    from_agent: str
    to_agent: str
    message_type: MessageType

    task: str
    context: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    expected_output: dict[str, Any] = field(default_factory=dict)

    priority: int = 5
    timeout_seconds: int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
```

**字段含义**

```text
message_id：
当前消息的唯一标识。

trace_id：
关联整次用户请求。

parent_message_id：
当前消息由哪条消息派生而来。

from_agent：
发送方 Agent。

to_agent：
接收方 Agent。

message_type：
消息类型。

task：
当前 Agent 要完成的任务。

context：
完成任务所需的最小上下文。

constraints：
必须遵守的限制条件。

expected_output：
期望返回的结果结构。

priority：
任务优先级。

timeout_seconds：
允许的最大执行时间。

metadata：
模型、版本、时间、项目等附加信息。
```

**示例**

```json
{
  "message_id": "msg_001",
  "trace_id": "trace_001",
  "parent_message_id": null,
  "from_agent": "orchestrator",
  "to_agent": "knowledge_expert",
  "message_type": "task_request",
  "task": "检索 LocalAgent 中和 RAG 评估有关的资料",
  "context": {
    "project": "LocalAgent",
    "user_question": "如何评估 RAG 的检索和引用质量？"
  },
  "constraints": [
    "只基于项目知识库",
    "资料不足时明确说明",
    "不得编造来源"
  ],
  "expected_output": {
    "summary": "string",
    "sources": "list",
    "confidence": "float",
    "missing_info": "list"
  },
  "priority": 5,
  "timeout_seconds": 30
}
```

**设计原则**

```text
1. 不要把完整历史对话全部传给目标 Agent；
2. task 和 constraints 必须分开；
3. expected_output 要明确；
4. 所有消息都必须带 trace_id；
5. 子任务消息要保留 parent_message_id；
6. message_type 应使用固定枚举；
7. 敏感信息应在发送前裁剪或脱敏。
```

一句话：

```text
AgentMessage 负责把一次自然语言委派，转换成可追踪、可验证、可执行的结构化任务。
```

#### 如何设计 AgentResult？

AgentResult 用于描述 Agent 完成任务后的结构化返回。

它必须同时支持：

```text
成功结果；
部分成功；
失败结果；
置信度；
来源；
警告；
后续建议。
```

**推荐结构**

```python
ResultStatus = Literal[
    "succeeded",
    "partial_success",
    "failed",
    "blocked",
    "cancelled",
]


@dataclass
class AgentError:
    error_type: str
    message: str
    stage: str
    recoverable: bool
    recovery_suggestion: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    message_id: str
    trace_id: str
    agent_name: str

    status: ResultStatus
    summary: str

    data: Any | None = None
    confidence: float | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    error: AgentError | None = None
    next_action: str | None = None

    metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

**为什么不能只返回 success 和 text？**

如果 Agent 只返回：

```json
{
  "success": true,
  "text": "任务完成"
}
```

Orchestrator（编排器）无法判断：

```text
完成了哪些部分；
结果是否有依据；
结果可信度如何；
有没有警告；
是否需要继续调用其他 Agent；
是否只是部分成功；
下一步应该做什么。
```

**成功结果示例**

```json
{
  "message_id": "msg_002",
  "trace_id": "trace_001",
  "agent_name": "knowledge_expert",
  "status": "succeeded",
  "summary": "找到 3 个与 RAG 评估相关的资料片段。",
  "data": {
    "evaluation_metrics": [
      "Recall@K",
      "Faithfulness",
      "Citation Accuracy"
    ]
  },
  "confidence": 0.92,
  "sources": [
    {
      "chunk_id": "chunk_001",
      "source": "rag_notes.md"
    }
  ],
  "warnings": [],
  "error": null,
  "next_action": "send_to_aggregator"
}
```

**部分成功示例**

```json
{
  "message_id": "msg_003",
  "trace_id": "trace_001",
  "agent_name": "data_analyst",
  "status": "partial_success",
  "summary": "已完成 85 表处理，但 8011 表不存在。",
  "data": {
    "completed_sheets": ["85"],
    "failed_sheets": ["8011"]
  },
  "confidence": 0.85,
  "warnings": [
    "工作簿中未找到 8011 工作表"
  ],
  "error": {
    "error_type": "sheet_not_found",
    "message": "Sheet 8011 does not exist.",
    "stage": "excel_update",
    "recoverable": true,
    "recovery_suggestion": "调用 inspect_excel 获取实际工作表名称"
  },
  "next_action": "request_recovery"
}
```

**设计原则**

```text
1. 成功和失败使用同一结构；
2. 支持 partial_success；
3. summary 给人看，data 给程序处理；
4. error 必须结构化；
5. sources 和 confidence 不应只存在于自然语言中；
6. next_action 只表示建议，最终控制权仍归 Orchestrator；
7. metrics 用于记录耗时、token 和工具调用次数。
```

一句话：

```text
AgentResult 不是一段回答，而是一份可供 Orchestrator 判断下一步动作的执行报告。
```

#### 如何设计 shared state（共享状态）？

shared state 用于保存一次复杂任务的全局状态。

它解决的问题是：

```text
多个 Agent 如何知道当前任务执行到了哪里；
哪些结果已经完成；
哪些任务仍在运行；
哪些错误尚未恢复；
哪些操作正在等待审批。
```

推荐结构

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SubtaskState:
    task_id: str
    agent_name: str
    status: str
    dependencies: list[str] = field(default_factory=list)
    result: Any | None = None
    error: dict[str, Any] | None = None


@dataclass
class SharedState:
    trace_id: str
    user_input: str

    goal: dict[str, Any]
    constraints: list[str]
    plan: list[dict[str, Any]]

    subtasks: dict[str, SubtaskState] = field(default_factory=dict)

    agent_results: dict[str, Any] = field(default_factory=dict)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    rag_results: list[dict[str, Any]] = field(default_factory=list)

    exceptions: list[dict[str, Any]] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)

    final_draft: str | None = None
    final_answer: str | None = None

    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
```

**shared state 应保存什么？**

建议保存：

```text
用户原始目标；
用户约束；
当前计划；
子任务依赖关系；
各 Agent 状态；
工具调用结果；
RAG 检索结果；
错误和恢复记录；
审批状态；
最终草稿和答案。
```

不建议直接保存：

```text
每个 Agent 的全部内部提示词；
所有模型原始输出；
无关历史对话；
不必要的敏感信息；
重复的大段文档内容。
```

**状态更新原则**

多个 Agent 并行工作时，不能随意覆盖 shared state。

推荐：

```text
1. 每个 Agent 只更新自己的命名空间；
2. Orchestrator 负责合并公共状态；
3. 状态更新带 version；
4. 冲突时使用乐观锁或事务；
5. 每次状态修改都记录事件；
6. 原始执行记录尽量追加，不直接覆盖。
```

例如：

```text
agent_results.code_expert
agent_results.knowledge_expert
agent_results.data_analyst
```

而不是让所有 Agent 都写：

```text
state.result
```

**短任务和长任务如何存储？**

短任务：

```text
可以放在进程内存中；
执行完成后写入 trace。
```

长任务或可恢复任务：

```text
写入 SQLite；
保存状态版本；
支持进程重启后恢复；
记录任务依赖和审批状态。
```

一句话：

```text
shared state 是多 Agent 系统的任务事实源，但不应该成为没有边界的公共垃圾桶。
```

#### 如何处理多个 Agent 的并行结果？

并行结果处理的关键不是同时运行，而是：

```text
什么时候汇总；
失败一个是否继续；
如何处理超时；
如何保留部分成功；
如何避免重复结果。
```

**并行执行前先判断依赖**

只有互相独立的任务才能并行。

例如：

```text
代码审查；
文档检索；
测试覆盖分析。
```

可以并行。

但下面不能直接并行：

```text
先解析文件；
再根据解析结果修改文件。
```

因为第二步依赖第一步。

可以把计划表示成 DAG（有向无环图）：

```text
task_a ─┐
task_b ─┼→ aggregate
task_c ─┘
```

**并行结果状态**

每个子任务应有独立状态：

```text
pending；
running；
succeeded；
partial_success；
failed；
timeout；
cancelled。
```

Aggregator（聚合器）不能只等一个布尔值，而要收集所有子任务状态。

**汇总策略**

常见策略有四种。

**All Required（全部必需）**

所有 Agent 成功才继续。

适合：

```text
多个结果缺一不可的任务。
```

**Best Effort（尽力而为）**

保留成功结果，失败部分明确说明。

适合：

```text
多角度分析；
并行检索；
多文件处理。
```

**Quorum（法定数量）**

达到一定成功数量即可继续。

例如：

```text
三个 Reviewer 中两个结论一致。
```

**First Valid Result（首个有效结果）**

第一个满足质量条件的结果返回后，就取消剩余任务。

适合：

```text
多个备用检索源；
多个等价工具。
```

**示例流程**

```text
启动 code_expert、knowledge_expert、evaluation_agent
→ 分别等待结果
→ 单个 Agent 超时不立即终止其他 Agent
→ 收集 succeeded / failed / timeout
→ 保存 partial result
→ 根据聚合策略判断是否继续
→ Aggregator 去重、排序和合并
```

**聚合时要做什么？**

```text
1. 按 agent_name 保留来源；
2. 合并重复结论；
3. 过滤明显无关结果；
4. 标记失败和超时；
5. 保留警告；
6. 计算整体置信度；
7. 不能把部分成功描述成全部成功。
```

一句话：

```text
并行执行追求的是缩短独立任务耗时，而不是让多个 Agent 无条件同时运行。
```

#### 如何处理 Agent 之间的冲突？

Agent 冲突是指不同 Agent 对同一个问题给出不一致结果。

例如：

```text
code_expert 认为代码线程安全；
reviewer 认为存在竞态条件。
```

冲突不能直接通过“谁说得更长”决定。

**先结构化描述冲突**

可以设计 ConflictReport（冲突报告）：

```json
{
  "conflict_id": "conflict_001",
  "trace_id": "trace_001",
  "topic": "代码是否存在竞态条件",
  "claims": [
    {
      "agent_name": "code_expert",
      "claim": "不存在竞态条件",
      "confidence": 0.72,
      "evidence": ["code.py:20-35"]
    },
    {
      "agent_name": "reviewer",
      "claim": "共享变量缺少锁保护",
      "confidence": 0.88,
      "evidence": ["code.py:28"]
    }
  ],
  "resolution_status": "pending"
}
```

**冲突解决顺序**

推荐按以下顺序处理：

```text
第一步：比较证据，而不是比较 Agent 身份；
第二步：比较来源可靠性和更新时间；
第三步：调用工具验证；
第四步：让 Reviewer 重新审查；
第五步：补充检索或执行测试；
第六步：无法裁决时保留分歧；
第七步：高风险场景交给 Human-in-the-Loop。
```

**常见冲突解决策略**

**Evidence-Based Resolution（基于证据裁决）**

优先选择有代码、文档、测试或工具结果支持的结论。

**Source Priority（来源优先级）**

例如：

```text
实际工具结果 > 官方文档 > 项目当前代码 > 历史记忆 > 模型推测。
```

**Freshness Priority（新鲜度优先）**

新版本代码和当前文档优先于旧记录。

**Reviewer Arbitration（审查器仲裁）**

让独立 Reviewer 根据双方证据裁决。

**Voting（投票）**

适合多个同质 Reviewer，但不适合事实来源明确的问题。

**Human Arbitration（人工裁决）**

涉及高风险、业务规则或证据不足时，由用户决定。



**不要隐藏冲突**

如果系统无法可靠解决，应输出：

```text
当前存在两个不同结论；
各自依据是什么；
系统无法自动确认哪一个正确；
建议补充测试或由用户裁决。
```

一句话：

```text
冲突处理的核心不是强行统一答案，而是找到证据、说明分歧，并在必要时把控制权交给人类。
```

#### 如何避免上下文爆炸？

Context Explosion（上下文爆炸）指多 Agent 系统不断转发完整对话、文档和中间结果，导致上下文越来越大。

它会带来：

```text
token 成本上升；
延迟增加；
模型注意力分散；
旧信息干扰；
隐私泄漏风险；
不同 Agent 之间信息污染。
```

**使用最小上下文原则**

每个 Agent 只获取完成当前任务需要的信息。

例如：

```text
code_expert：
代码、报错、运行环境、审查目标。

knowledge_expert：
用户问题、检索范围、必要项目背景。

data_analyst：
文件信息、sheet、列、处理规则。

reviewer：
用户目标、关键约束、草稿和证据。
```

**使用结构化摘要**

不要不断转发所有历史内容。

可以把历史压缩成：

```text
当前目标；
已完成步骤；
关键事实；
未解决问题；
用户约束；
下一步任务。
```

**传引用，不传全文**

例如，不要在 shared state 中反复保存整篇文档。

只保存：

```text
chunk_id；
source；
summary；
score；
必要引用片段。
```

目标 Agent 需要时再读取完整 chunk。

**分离不同类型上下文**

可以分成：

```text
task_context：
当前任务必要信息。

user_context：
用户偏好和约束。

knowledge_context：
RAG 检索内容。

execution_context：
工具结果和错误。

audit_context：
审批和安全记录。
```

Agent 按需读取，而不是全部注入。

**设置上下文预算**

为不同 Agent 设置：

```text
max_context_tokens；
max_chunks；
max_history_messages；
max_tool_results；
max_agent_results。
```

超过预算时：

```text
摘要；
裁剪；
去重；
按相关性排序；
只保留最近和最重要内容。
```

**处理重复信息**

多个 Agent 可能返回相同内容。

Aggregator 应按以下信息去重：

```text
claim；
source；
chunk_id；
text hash；
semantic similarity。
```

**推荐流程**

```text
完整任务状态
→ 按目标 Agent 角色过滤
→ 提取相关字段
→ 压缩历史
→ 限制 token
→ 脱敏
→ 生成最小 AgentMessage
```

一句话：

```text
避免上下文爆炸的关键不是更大的上下文窗口，而是更精确的上下文选择。
```

#### 如何记录多 Agent trace（链路追踪）？

多 Agent trace 要能回答：

```text
任务经过了哪些 Agent；
每个 Agent 收到了什么；
返回了什么；
耗时多少；
哪里失败；
如何恢复；
谁参与了最终答案。
```

**Trace 层级**

可以采用三层结构。

```text
Trace：
一次完整用户请求。

Span：
某个 Agent、工具或检索步骤。

Event：
Span 内部发生的状态变化。
```

示例：

```text
Trace: 用户请求
├─ Span: Router
├─ Span: Planner
├─ Span: knowledge_expert
│  ├─ Event: rag_search_started
│  └─ Event: rag_search_completed
├─ Span: code_expert
├─ Span: Reviewer
└─ Span: Aggregator
```

推荐字段

```json
{
  "trace_id": "trace_001",
  "parent_span_id": null,
  "span_id": "span_knowledge_001",
  "span_type": "agent",
  "agent_name": "knowledge_expert",
  "message_id": "msg_001",
  "status": "succeeded",
  "started_at": "2026-07-11T10:00:00",
  "ended_at": "2026-07-11T10:00:02",
  "latency_ms": 2000,
  "input_summary": "检索 RAG 评估资料",
  "output_summary": "返回 3 个相关文档片段",
  "token_usage": {
    "input_tokens": 600,
    "output_tokens": 250
  },
  "tool_calls": [
    "search_knowledge_base"
  ],
  "error": null
}
```

**要记录哪些内容？**

```text
route 结果；
plan；
AgentMessage；
AgentResult；
子任务状态；
工具调用；
RAG 查询和召回结果；
异常和恢复动作；
审批事件；
冲突和裁决；
最终聚合来源；
耗时、token 和成本。
```

**隐私和成本控制**

Trace 不应无脑记录所有原始内容。

建议：

```text
大段内容保存摘要和引用 ID；
敏感信息脱敏；
API Key 和密码禁止写入；
超长工具结果保存外部引用；
日志设置保留周期；
区分调试日志和生产审计日志。
```

一句话：

```text
多 Agent trace 的目标不是记录得最多，而是让每次协作过程都能被还原和诊断。
```

#### 如何评估 Inter Agent Communication 是否有效？

Inter Agent Communication 的评估不能只看最终答案。

需要同时评估：

```text
消息是否正确；
任务是否正确委派；
状态是否同步；
上下文是否合适；
错误是否正确传播；
结果是否正确聚合。
```

**通信正确性指标**

Message Delivery Success Rate（消息投递成功率）

```text
成功送达目标 Agent 的消息数 / 总消息数
```

Message Schema Validity Rate（消息结构合法率）

```text
符合 AgentMessage schema 的消息数 / 总消息数
```

Task Assignment Accuracy（任务分配正确率）

```text
任务是否被分配给正确 Agent。
```

Context Relevance Rate（上下文相关率）

```text
传给 Agent 的上下文中，有多少真正与任务相关。
```

**状态管理指标**

```text
State Consistency Rate：
不同 Agent 看到的关键状态是否一致。

Stale State Rate：
使用过期状态的比例。

State Conflict Rate：
并发更新产生冲突的比例。

Task Status Accuracy：
任务状态是否真实反映执行结果。
```

**错误传播指标**

```text
Error Propagation Success Rate：
Agent 错误是否正确传到 Orchestrator。

Recovery Trigger Accuracy：
可恢复错误是否触发正确恢复。

Lost Error Rate：
错误是否在通信过程中丢失。

Partial Result Preservation Rate：
失败时是否保留了可用结果。
```

**并行与聚合指标**

```text
Parallel Speedup：
并行执行相比串行节省了多少时间。

Aggregation Accuracy：
Aggregator 是否正确使用各 Agent 结果。

Duplicate Result Rate：
结果重复率。

Conflict Detection Rate：
冲突是否被正确识别。

Conflict Resolution Success Rate：
冲突是否被正确解决。
```

**上下文指标**

```text
Average Context Tokens per Agent：
每个 Agent 平均上下文 token。

Context Compression Ratio：
压缩前后上下文比例。

Irrelevant Context Rate：
无关上下文比例。

Missing Context Rate：
因上下文不足导致失败的比例。

Sensitive Context Leak Rate：
敏感上下文泄露比例。
```

**端到端指标**

```text
Multi-Agent Task Success Rate：
多 Agent 任务成功率。

Coordination Failure Rate：
因通信或协调失败导致的失败率。

Average Agent Handoff Count：
平均 Agent 交接次数。

End-to-End Latency：
端到端延迟。

Token and Cost per Task：
单任务 token 和成本。

User Correction Rate：
用户纠错率。
```

测试样例

```json
{
  "case_id": "communication_001",
  "input": "分析 LocalAgent 的代码结构、知识库和评估体系",
  "expected_agents": [
    "code_expert",
    "knowledge_expert",
    "evaluation_agent"
  ],
  "expected_communication": {
    "parallel": true,
    "aggregator_required": true,
    "reviewer_required": true
  },
  "expected_constraints": [
    "各 Agent 只接收必要上下文",
    "失败结果不得被描述成成功",
    "最终答案需要整合而不是简单拼接"
  ]
}
```

典型 bad case

```text
wrong_agent_assignment：
任务分配给错误 Agent。

message_schema_error：
消息结构不合法。

context_missing：
必要上下文缺失。

context_overflow：
传递上下文过多。

state_conflict：
共享状态冲突。

error_lost：
错误传播丢失。

aggregation_error：
结果聚合错误。

conflict_not_detected：
未发现 Agent 结论冲突。

unauthorized_context_share：
向无权限 Agent 发送敏感上下文。
```

完整改进闭环

```text
收集多 Agent trace
→ 计算通信指标
→ 定位失败消息或状态
→ 分类 communication bad case
→ 优化 AgentMessage / AgentResult / shared state
→ 跑回归测试
→ 对比任务成功率、延迟和成本
```

一句话：

```text
Inter Agent Communication 是否有效，要看任务是否正确传递、状态是否一致、错误是否可恢复、结果是否正确聚合，而不只是看最终答案是否勉强可用。
```

#### 总结

这部分最重要的是建立五个统一对象：

```text
AgentMessage：
统一任务通信。

AgentResult：
统一执行结果。

SharedState：
统一任务状态。

Trace：
统一执行链路。

ConflictReport：
统一冲突描述。
```

它们之间的关系是：

```text
Orchestrator 通过 AgentMessage 分发任务
→ Agent 返回 AgentResult
→ 结果写入 SharedState
→ 全过程记录到 Trace
→ 发现冲突时生成 ConflictReport
→ Reviewer 或 Human-in-the-Loop 完成裁决
→ Aggregator 生成最终答案
```

面试时可以这样总结：

```text
在多 Agent 系统中，我不会让 Agent 直接通过自由文本互相调用，而是统一设计 AgentMessage、AgentResult 和 SharedState。Orchestrator 负责任务分发、上下文裁剪、状态维护、并行调度、错误恢复和结果聚合；所有交互都通过 trace 和 [[ORCH]] 事件记录。对于并行结果，我会根据任务依赖采用全部成功、尽力而为、法定数量或首个有效结果等策略；对于冲突，则优先比较证据、来源和新鲜度，必要时交给 Reviewer 或 Human-in-the-Loop。这样多 Agent 协作才能做到可控、可观测、可评估和可恢复。
```

### 一句话总结

```text
Inter Agent Communication 的本质是：让多个 Agent 通过结构化消息、共享状态和事件机制协同工作，而不是各自独立生成一段文本。
```

再压缩一点：

```text
多 Agent 的难点不是“分几个角色”，而是“怎么通信、怎么同步、怎么聚合、怎么恢复”。
```

对你来说，这一节可以浓缩成：

```text
LocalAgent 如果要从单 Agent 编排升级成多 Agent 工程系统，就必须设计清楚 AgentMessage、AgentResult、shared state、[[ORCH]] 事件和 Orchestrator 调度机制。
```

## Chapter 18 Resource Aware Optimization（资源感知优化）

Resource Aware Optimization 关注的是：

```text
Agent 在完成任务时，如何根据时间、成本、算力、内存、上下文和并发限制，选择更合适的执行方式。
```

一句话：

```text
不是让 Agent 一味追求最强效果，而是在效果、速度、成本和稳定性之间做平衡。
```

它主要解决：

```text
这个任务值得调用大模型吗？
需要调用几次模型？
是否需要完整 RAG 检索？
多个任务能否并行？
上下文应该放多少？
什么时候应该停止继续推理？
```

### 为什么 Agent 特别需要资源优化

普通 LLM（大语言模型）应用可能只调用一次模型，但 Agent（智能体）经常包含：

```text
Routing（路由）；
Planning（规划）；
RAG（检索增强生成）；
Tool Use（工具使用）；
Reflection（反思）；
Multi-Agent Collaboration（多智能体协作）。
```

一个用户请求可能触发：

```text
多次模型调用；
多次知识库检索；
多个工具执行；
多个 Agent 并行；
多轮反思和重新规划。
```

如果不控制，可能出现：

```text
简单问题也执行完整工作流；
一个任务调用十几次模型；
上下文不断膨胀；
RAG 返回大量无关片段；
Reflection 无限修改；
多个 Agent 重复完成相同任务；
延迟和成本越来越高。
```

因此，资源感知优化的本质是：

```text
把“任务复杂度”和“资源投入”匹配起来。
```

### Agent 系统主要有哪些资源

#### Token（词元）

Token 是模型输入和输出的基本计量单位。

Token 消耗主要来自：

```text
系统提示词；
历史对话；
RAG 检索片段；
工具结果；
多 Agent 消息；
模型最终输出；
Reflection 产生的额外调用。
```

Token 过多会造成：

```text
调用成本增加；
延迟上升；
上下文噪声增加；
重要信息被淹没。
```

#### Latency（延迟）

延迟指从用户发出请求到获得结果的时间。

Agent 的延迟可能来自：

```text
模型推理；
RAG 检索；
Embedding（向量嵌入）；
工具执行；
网络请求；
多个 Agent 等待；
人工审批。
```

需要区分：

```text
端到端延迟；
首个输出时间；
模型调用耗时；
工具耗时；
检索耗时。
```

#### Cost（成本）

成本可能包括：

```text
模型 API 调用费用；
Embedding 调用费用；
Reranker（重排模型）费用；
数据库和向量库资源；
本地模型内存与显存；
网络和存储成本。
```

本地模型虽然没有按 Token 计费，但仍然占用：

```text
内存；
显存；
CPU；
GPU；
电力；
响应时间。
```

#### Context Window（上下文窗口）

上下文窗口决定一次模型调用能够接收多少内容。

内容可能包括：

```text
历史对话；
用户偏好；
任务计划；
工具结果；
RAG 资料；
Agent 执行结果。
```

问题不只是“能不能放下”，还包括：

```text
放进去的内容是否都相关。
```

上下文越长不一定越好。过多无关信息可能降低回答质量。

#### Compute and Memory（算力与内存）

本地 Agent 特别需要考虑：

```text
LLM 模型内存；
Embedding 模型内存；
向量数据库内存；
并发请求数；
文件解析资源；
Excel 大文件处理内存。
```

#### Concurrency（并发）

并发可以提升效率，但过高也会带来：

```text
API 限流；
连接池耗尽；
内存占用上升；
模型服务 504；
工具资源冲突；
文件同时写入冲突。
```

所以并发数不能只追求越大越好。

### 核心优化原则

#### 按任务复杂度分级

不是所有任务都走完整 Agent 工作流。

可以分成：

```text
简单任务：
直接调用模型。

中等任务：
Router + 单个专业 Agent + 必要工具。

复杂任务：
Planner + RAG + 多工具 + Reflection。

高风险任务：
完整流程 + Guardrails + Human-in-the-Loop。
```

例如：

```text
“解释什么是 RAG”
→ 不需要 Planner 和多 Agent。

“分析整个 LocalAgent 架构并提出优化方案”
→ 需要规划、检索和多个分析模块。
```

核心原则：

```text
简单任务走短路径，复杂任务才走深路径。
```

#### Model Routing（模型路由）

不同任务使用不同能力和成本的模型。

例如：

```text
分类、路由、格式转换：
使用小模型或规则。

复杂规划、代码审查：
使用能力更强的模型。

简单总结：
使用快速模型。

最终审查：
只在高价值任务中使用强模型。
```

可以理解为：

```text
小模型处理高频简单任务；
大模型处理低频复杂任务。
```

你的 LocalAgent 可以结合 Profile（执行档位）：

```text
fast：
少步骤、少检索、不反思。

balanced：
正常检索和工具调用。

deep：
完整规划、并行分析、反思和验证。
```

#### 控制 Agent 最大执行步数

复杂 Agent 容易不断：

```text
重新规划；
继续检索；
再次调用工具；
重新反思。
```

因此要设置：

```text
max_steps；
max_tool_calls；
max_retries；
max_replan_times；
max_reflection_rounds。
```

达到上限后：

```text
输出当前可用结果；
说明未完成部分；
或者安全停止。
```

不能无限执行。

#### 控制上下文大小

推荐做法：

```text
只保留最近必要对话；
历史内容使用滚动摘要；
工具结果保存摘要而不是全文；
RAG 只注入最相关片段；
多个 Agent 只接收角色所需上下文。
```

例如工具返回一个几万行表格，不应该全部送给模型。

应该转换成：

```text
文件结构；
列名；
关键统计；
异常行；
少量示例数据。
```

#### 优化 RAG 检索资源

RAG 容易产生不必要消耗。

可以控制：

```text
top_k；
相似度阈值；
检索次数；
Query Rewrite（查询改写）次数；
Rerank 候选数量；
最终上下文片段数量。
```

例如：

```text
初始召回 20 个候选；
重排后只保留 5 个；
最终只注入真正相关内容。
```

还可以先判断：

```text
这个问题是否真的需要 RAG。
```

像普通数学计算、代码语法检查，可能不需要知识库检索。

#### Cache（缓存）

缓存可以减少重复计算。

适合缓存：

```text
相同问题的检索结果；
文档 Embedding；
文件解析结果；
模型固定分类结果；
工具只读结果；
不经常变化的知识摘要。
```

但不适合直接缓存：

```text
实时数据；
会变化的文件内容；
用户权限相关结果；
高风险工具执行结果；
包含敏感信息的结果。
```

缓存需要考虑：

```text
缓存键；
有效时间；
版本；
权限；
失效策略。
```

#### Parallelization（并行化）

独立任务可以并行执行。

例如：

```text
代码结构分析；
RAG 文档检索；
测试覆盖分析。
```

可以同时进行。

但有依赖的任务必须串行：

```text
先读取 Excel；
再根据读取结果修改 Excel。
```

并行优化必须考虑：

```text
任务是否独立；
服务是否支持并发；
并发上限；
单个任务失败是否影响整体；
文件是否存在写冲突。
```

#### Batch Processing（批处理）

多个相似任务可以批量处理。

例如：

```text
批量计算 Embedding；
批量评估测试集；
批量读取多个文档；
批量执行 RAG 测试。
```

批处理通常比逐条调用更节省：

```text
网络开销；
初始化开销；
数据库交互次数。
```

但单批不能过大，否则会增加内存和失败影响范围。

#### Early Stop（提前停止）

当已经获得足够可靠的答案时，应停止继续执行。

可以根据以下条件停止：

```text
目标已经完成；
检索证据已经足够；
工具调用已经成功；
答案通过 Reviewer 检查；
达到置信度阈值；
继续执行收益很低。
```

例如 RAG 已经召回直接回答问题的官方文档，就不必继续进行多轮扩展检索。

### 资源优化不是单纯降低成本

资源感知优化需要平衡多个目标：

```text
质量；
延迟；
成本；
稳定性；
安全性。
```

常见冲突包括：

```text
增加 top_k：
可能提高召回率，但增加噪声和 Token。

增加 Reflection：
可能提高质量，但增加延迟和成本。

增加 Agent 数量：
可能增加分析角度，但增加通信和聚合成本。

使用更强模型：
可能提高准确率，但降低响应速度。

提高并发：
可能减少总耗时，但增加服务压力。
```

因此不能单看某一个指标。

更合理的是：

```text
在满足最低质量和安全要求的前提下，尽量降低成本与延迟。
```

注意：

```text
安全不能为了成本被牺牲。
```

例如高风险工具审批不能因为“节省一次交互”就删除。

### 资源预算如何设计

可以为一次 Agent 请求设置 Budget（预算）。

例如：

```text
最大模型调用次数；
最大工具调用次数；
最大检索次数；
最大 Token；
最大执行时间；
最大并发数；
最大 Reflection 轮数。
```

不同任务可以有不同预算。

```text
简单问答：
模型调用 1 次，不调用工具。

普通 RAG 问答：
检索 1 次，模型调用 1～2 次。

复杂分析：
允许规划、并行 Agent 和一次 Reflection。

高风险任务：
允许更多校验步骤，但工具执行必须审批。
```

预算不是一定要全部用完，而是限制上限。

### 如何评估资源优化是否有效

核心指标包括：

```text
平均端到端延迟；
P95 延迟；
单任务 Token；
平均模型调用次数；
平均工具调用次数；
任务成功率；
成本；
内存使用；
并发失败率。
```

不能只看资源下降，还要同时看质量。

例如：

```text
Token 降低 30%；
但任务成功率下降 20%。
```

这不是有效优化。

更理想的是：

```text
Token 降低 25%；
延迟降低 20%；
任务成功率基本不变；
关键安全指标不下降。
```

### 常见坑

#### 所有任务都使用最强模型

会导致成本和延迟过高。

应使用模型路由。

#### 为了省资源不做必要验证

例如取消高风险审批、引用检查或结果校验。

这是错误优化。

```text
资源优化不能突破安全底线和质量底线。
```

#### 盲目增加并发

并发过高可能导致：

```text
连接池耗尽；
服务限流；
504；
内存上涨；
工具写冲突。
```

#### 上下文全部保留

完整历史、所有工具结果、所有 RAG 文档都塞进模型，会造成上下文爆炸。

应做：

```text
摘要；
裁剪；
过滤；
按需读取。
```

#### 只看平均延迟

平均延迟可能掩盖长尾问题。

还需要关注：

```text
P95；
P99；
超时率。
```

### 和前面章节的关系

#### 和 Routing（路由）的关系

Routing 决定：

```text
走哪条执行路径；
选择哪个 Agent；
使用哪个模型；
采用哪种执行档位。
```

#### 和 Planning（规划）的关系

Planner（规划器）生成计划时要考虑：

```text
步骤是否必要；
哪些步骤可以并行；
哪些工具成本高；
什么时候应该停止。
```

#### 和 Evaluation and Monitoring（评估与监控）的关系

资源优化必须通过评估验证。

需要同时观察：

```text
质量；
延迟；
成本；
错误率；
任务成功率。
```

#### 和 Guardrails（护栏）的关系

Guardrails 可以限制：

```text
最大执行步数；
最大工具调用数；
最大成本；
最大运行时间；
最大并发数。
```

但安全检查本身不能为了优化而被绕过。

#### 和 Inter Agent Communication（智能体间通信）的关系

多 Agent 通信会消耗大量上下文和 Token。

因此要：

```text
传递最小必要上下文；
避免重复结果；
减少不必要的 Agent 交接；
只在复杂任务中启用多 Agent。
```

### 面试表达

可以这样回答：

```text
Resource Aware Optimization 是 Agent 工程中根据任务复杂度和系统资源限制，动态控制模型、工具、检索、并发和上下文使用的优化方法。它关注的不只是降低成本，而是在质量、延迟、成本、稳定性和安全性之间做平衡。
```

结合工程实践：

```text
我不会让所有任务都走完整的 Agent 工作流。简单问题直接调用模型，中等任务调用单个专业 Agent，复杂任务才启用 Planning、RAG、多 Agent 和 Reflection。同时会设置 max_steps、max_tool_calls、max_retries、max_context_tokens 和 max_concurrency 等运行限制，并记录每次请求的 Token、模型调用次数、工具调用次数和各阶段耗时。
```

结合 LocalAgent：

```text
在 LocalAgent 中，我会使用 fast、balanced、deep 三种 Profile。Router 除了判断任务类型，还会判断任务复杂度、是否需要 RAG、工具、规划和 Reflection。公司内网 Qwen 服务采用较低并发，家庭 DeepSeek 环境允许更高并发；工具结果和历史对话会先做摘要和裁剪，再传给模型。最终通过任务成功率、P95 延迟、Token 使用量、错误率和并发失败率评估优化是否有效。
```

### 需要掌握

#### 为什么简单任务不应该走完整工作流？

简单任务不应该走完整工作流，因为完整 Agent 链路会引入不必要的模型调用、工具调用、检索、通信和等待成本。

一个完整流程可能包括：

```text
Routing
→ Planning
→ RAG
→ Tool Use
→ Multi-Agent
→ Reflection
→ Final Answer
```

但很多任务并不需要这么复杂。

例如：

```text
解释什么是 RAG；
改写一句话；
检查简单语法错误；
把一段文字缩短。
```

这类任务通常一次模型调用就能完成。

如果仍然走完整流程，可能产生以下问题。

**增加延迟**

每增加一个阶段，都可能增加一次模型调用或工具调用。

例如：

```text
Router 调用一次模型；
Planner 调用一次模型；
专业 Agent 再调用一次模型；
Reflection 再调用一次模型。
```

原本一次调用能完成的任务，可能变成四次调用。

用户最终只看到一个简单答案，却需要等待更长时间。

**增加成本**

完整流程会增加：

```text
输入 Token；
输出 Token；
模型调用次数；
RAG 检索次数；
工具调用次数；
多 Agent 通信成本。
```

如果简单问题也启用 RAG（检索增强生成）和 Reflection（反思），会产生大量无价值消耗。

**增加失败点**

流程越长，可能失败的环节越多。

例如：

```text
Router 路由错；
Planner 生成多余步骤；
RAG 召回无关内容；
工具调用失败；
Reflection 把正确答案改坏。
```

简单任务原本不需要这些环节，却因为复杂流程引入了额外风险。

**容易过度处理**

Agent 可能把简单问题复杂化。

例如用户只是问：

```text
什么是向量数据库？
```

Planner 却生成：

```text
1. 检索向量数据库资料；
2. 对比多种数据库；
3. 调用多个 Agent 分析；
4. 生成架构建议；
5. 进行反思检查。
```

这属于 Over-planning（过度规划）。

**影响用户体验**

简单任务通常追求：

```text
快；
直接；
清楚；
低等待。
```

而复杂任务才需要：

```text
深度；
验证；
多角度；
完整过程。
```

所以执行深度应该和任务复杂度匹配。

**推荐分级**

```text
简单任务：
直接模型调用。

中等任务：
Router + 单个专业 Agent。

复杂任务：
Planner + RAG + Tool Use。

高价值复杂任务：
多 Agent + Reflection + Verification。

高风险任务：
完整流程 + Guardrails + Human-in-the-Loop。
```

一句话：

```text
简单任务走短路径，复杂任务才走深流程。
```

**面试表达**

```text
简单任务不应该走完整 Agent 工作流，因为完整链路会增加模型调用、Token、延迟、成本和失败点。工程上我会先判断任务复杂度，简单解释、格式转换和轻量总结直接调用模型；只有复杂任务才启用 Planning、RAG、工具调用、多 Agent 和 Reflection。这样可以避免过度规划，让资源投入和任务价值匹配。
```

#### 如何通过模型路由、执行档位和预算控制资源？

资源控制可以分成三层：

```text
模型路由：
决定使用哪个模型。

执行档位：
决定走多深的流程。

预算控制：
限制最多可以消耗多少资源。
```

**Model Routing（模型路由）**

模型路由根据任务复杂度选择不同模型。

例如：

```text
分类、路由、关键词提取：
使用小模型或规则。

普通知识解释：
使用快速通用模型。

复杂规划、代码审查：
使用能力更强的模型。

关键结果审查：
必要时使用高能力模型。
```

核心思想：

```text
小模型处理高频简单任务；
强模型处理低频复杂任务。
```

模型路由可以考虑：

```text
任务复杂度；
上下文长度；
是否需要代码能力；
是否需要结构化输出；
响应速度要求；
成本限制；
模型可用状态。
```

例如：

```text
task_complexity = low
→ fast_model

task_complexity = high
→ strong_model
```

**Profile（执行档位）**

执行档位决定 Agent 使用哪些模块。

你的 LocalAgent 可以使用：

```text
fast；
balanced；
deep。
```

**fast**

适合：

```text
简单解释；
格式转换；
短文本总结；
简单问答。
```

策略：

```text
不生成复杂计划；
通常不启用 RAG；
不使用多 Agent；
不进行 Reflection；
限制输出长度。
```

**balanced**

适合：

```text
普通项目问答；
单工具任务；
一般代码分析；
常规 RAG 问答。
```

策略：

```text
必要时 Planning；
正常 RAG；
单个专业 Agent；
有限重试；
必要时一次 Reflection。
```

**deep**

适合：

```text
架构分析；
复杂代码审查；
多文档研究；
复杂项目优化；
多步骤决策。
```

策略：

```text
完整 Planning；
多 Agent；
并行任务；
多轮检索；
Reflection；
引用和结果验证。
```

执行档位可以由：

```text
用户手动选择；
Router 自动推荐；
系统根据任务风险自动提升。
```

**Budget**

预算用于限制一次任务最多可以使用多少资源。

可以设置：

```text
max_model_calls；
max_tool_calls；
max_retrieval_calls；
max_steps；
max_retries；
max_replan_times；
max_reflection_rounds；
max_context_tokens；
max_execution_seconds；
max_cost。
```

不同档位使用不同预算。

例如：

```text
fast：
max_model_calls = 1
max_tool_calls = 0
max_retrieval_calls = 0
max_reflection_rounds = 0

balanced：
max_model_calls = 3
max_tool_calls = 3
max_retrieval_calls = 2
max_reflection_rounds = 1

deep：
max_model_calls = 8
max_tool_calls = 8
max_retrieval_calls = 4
max_reflection_rounds = 2
```

预算不是要求 Agent 必须用完，而是规定上限。

**三者关系**

```text
Model Routing 决定“用什么模型”；
Profile 决定“走多深的流程”；
Budget 决定“最多花多少资源”。
```

完整流程可以是：

```text
用户请求
→ Router 判断任务类型和复杂度
→ 推荐 Profile
→ 选择模型
→ 创建资源预算
→ Orchestrator 执行
→ 达到预算后提前停止或降级。
```

一句话：

```text
模型路由控制单次调用成本，执行档位控制流程复杂度，预算控制整体资源上限。
```

#### 如何控制 Token、上下文、检索、并发和执行步数？

资源控制不能只盯着某一个参数，而要对整个执行链设置上限。

**Token（词元）控制**

Token 消耗主要来自：

```text
系统提示词；
历史对话；
RAG 片段；
工具结果；
Agent 通信；
模型输出。
```

控制方法：

```text
限制 max_input_tokens；
限制 max_output_tokens；
压缩历史对话；
删除重复内容；
工具结果只返回摘要；
RAG 只注入高相关片段；
不同 Agent 只接收必要上下文。
```

还可以设置预警：

```text
如果预计 Token 超过预算：
先压缩；
再裁剪；
必要时降低执行档位。
```

**上下文控制**

Context Window（上下文窗口）大，不代表应该全部用满。

上下文控制原则：

```text
相关性优先于数量；
结构化摘要优先于完整历史；
引用 ID 优先于重复全文；
当前任务优先于旧信息。
```

可以保留：

```text
当前目标；
关键约束；
最近必要对话；
任务计划；
相关 RAG 片段；
必要工具结果。
```

可以删除或压缩：

```text
无关历史；
重复说明；
完整日志；
超长表格；
已经完成的中间推理。
```

**检索控制**

RAG 检索需要控制：

```text
top_k；
相似度阈值；
query rewrite 次数；
检索轮数；
rerank 候选数；
最终 context chunk 数。
```

推荐流程：

```text
初步检索 top_20；
rerank；
最终只保留 top_5。
```

如果首轮检索已经有高质量直接证据，就不必继续扩展查询。

如果检索结果质量低，可以：

```text
改写 query；
切换 Hybrid Retrieval（混合检索）；
扩大范围；
但不能无限检索。
```

**并发控制**

Concurrency（并发）要根据模型服务和任务类型设置。

需要控制：

```text
最大并发 Agent 数；
最大并发模型请求数；
最大并发工具调用数；
连接池大小；
文件写入锁。
```

例如：

```text
公司内网 Qwen 服务：
并发较低，避免 504。

家庭 DeepSeek 服务：
根据接口能力适当提高并发。
```

同时要区分：

```text
只读任务可以适当并发；
同一文件写操作不能并发；
有依赖的任务不能并发；
高内存任务要限制并发。
```

**执行步数控制**

Agent 容易发生循环：

```text
检索
→ 反思
→ 重新检索
→ 重新规划
→ 再调用工具
```

因此要设置：

```text
max_steps；
max_tool_calls；
max_retries；
max_replan_times；
max_reflection_rounds。
```

达到限制后可以：

```text
返回当前部分结果；
说明未完成内容；
请求用户补充；
切换降级方案；
Safe Stop（安全停止）。
```

**统一资源管理**

推荐定义 RequestBudget（请求预算）：

```text
max_input_tokens；
max_output_tokens；
max_context_tokens；
max_steps；
max_model_calls；
max_tool_calls；
max_retrieval_calls；
max_concurrency；
max_execution_seconds。
```

每执行一步都扣减预算。

例如：

```text
调用一次模型：
model_calls + 1

调用一次工具：
tool_calls + 1

执行一次检索：
retrieval_calls + 1
```

达到上限后由 Orchestrator 决定：

```text
继续；
降级；
提前结束；
安全停止。
```

一句话：

```text
Token、上下文、检索、并发和步数都必须有程序级预算，而不能只靠 prompt 提醒 Agent 节省资源。
```

#### 缓存、批处理、并行和提前停止分别适合什么场景？

这四种优化方式解决的问题不同。

**Cache（缓存）**

缓存适合：

```text
输入相同或高度重复；
结果短期内不会变化；
计算成本较高；
可以安全复用。
```

典型场景：

```text
文档解析结果；
文档 Embedding；
固定知识库检索结果；
只读工具结果；
模型分类结果；
静态配置摘要。
```

不适合：

```text
实时数据；
频繁变化的文件；
不同用户权限下的结果；
高风险工具执行结果；
包含敏感信息的内容。
```

缓存必须考虑：

```text
缓存键；
数据版本；
用户权限；
过期时间；
失效策略。
```

一句话：

```text
缓存适合避免重复计算。
```

**Batch Processing（批处理）**

批处理适合大量结构相似、可统一处理的任务。

典型场景：

```text
批量生成 Embedding；
批量评估测试集；
批量解析文档；
批量执行分类；
批量写入数据库；
批量处理 Excel 文件。
```

优势：

```text
减少网络调用次数；
减少模型或服务初始化次数；
提高数据库写入效率；
提高 GPU 或 CPU 利用率。
```

注意：

```text
批次不能过大；
单条失败不能拖垮整批；
要保留每条任务的结果和错误；
要控制内存峰值。
```

一句话：

```text
批处理适合把大量相似任务集中完成。
```

**Parallelization（并行化）**

并行适合彼此独立、没有前后依赖的任务。

典型场景：

```text
代码结构分析；
文档检索；
测试覆盖分析；
多个知识源检索；
多个文件只读解析。
```

不适合：

```text
先读取结果，再根据结果修改；
多个 Agent 同时写同一文件；
多个任务共享不可并发资源；
模型服务承载能力不足。
```

并行需要考虑：

```text
任务依赖；
并发上限；
超时；
部分失败；
结果聚合；
资源冲突。
```

一句话：

```text
并行适合缩短独立任务的总耗时。
```

**Early Stop（提前停止）**

提前停止适合系统已经获得足够信息，继续执行收益很低的场景。

典型条件：

```text
目标已经完成；
关键证据已经找到；
工具已经成功执行；
答案已经通过 Reviewer；
达到置信度阈值；
继续检索不会明显提高质量；
资源预算即将耗尽。
```

例如：

```text
RAG 已经召回直接回答问题的项目文档；
就不必再做三轮扩展检索。
```

或者：

```text
两个 Agent 已经给出一致且有证据的结论；
就不必再调用第三个 Agent。
```

一句话：

```text
提前停止适合在结果已经足够可靠时避免继续浪费资源。
```

**四者区别**

| 方法             | 主要目标       | 适合场景           |
| ---------------- | -------------- | ------------------ |
| Cache            | 避免重复计算   | 相同输入、稳定结果 |
| Batch Processing | 提高批量吞吐   | 大量相似任务       |
| Parallelization  | 缩短总耗时     | 相互独立任务       |
| Early Stop       | 避免无收益执行 | 已获得足够结果     |

可以记成：

```text
缓存解决“重复做”；
批处理解决“一个个做”；
并行解决“排队做”；
提前停止解决“做过头”。
```

#### 为什么资源优化必须同时关注质量、成本、延迟和安全？

资源优化是多目标权衡，不能只优化一个指标。

如果只关注成本，可能牺牲质量。

如果只关注质量，可能导致系统太慢、太贵，无法使用。

如果只关注延迟，可能跳过必要检查。

如果忽略安全，可能产生真实风险。

**只关注质量的问题**

为了追求最高质量，系统可能：

```text
总是调用最强模型；
启用多个 Agent；
进行多轮 RAG；
进行多轮 Reflection；
传入大量上下文。
```

结果可能是：

```text
响应时间过长；
成本过高；
资源占用过大；
线上无法承载。
```

高质量但无法使用，也不是好的工程方案。

**只关注成本的问题**

为了降低成本，可能：

```text
只用小模型；
减少检索；
取消 Reflection；
缩短上下文；
减少验证步骤。
```

结果可能是：

```text
答案质量下降；
工具参数错误增加；
RAG 召回不足；
幻觉率上升。
```

**只关注延迟的问题**

为了快速返回，可能跳过：

```text
引用验证；
工具结果校验；
高风险审批；
异常恢复；
输出检查。
```

这样虽然更快，但会增加错误和安全风险。

**安全不能被资源优化牺牲**

以下步骤即使增加延迟和成本，也不能随意删除：

```text
高风险操作审批；
权限检查；
工具参数校验；
敏感信息检查；
文件备份；
执行结果验证。
```

例如：

```text
为了少一次用户交互，取消 Excel 覆盖前审批。
```

这不是资源优化，而是破坏安全边界。

**正确的优化目标**

更合理的目标是：

```text
在满足质量底线和安全底线的前提下，尽量降低成本和延迟。
```

可以设置：

```text
质量约束；
安全约束；
成本目标；
延迟目标。
```

例如：

```text
任务成功率不得下降；
Missed Approval Rate 必须为 0；
平均 Token 降低 20%；
P95 延迟降低 15%。
```

**典型权衡**

增加 RAG top_k：

```text
可能提高 Recall@K；
但会增加上下文、噪声、延迟和 Token。
```

增加 Reflection：

```text
可能提高答案质量；
但会增加模型调用和响应时间。
```

增加并发：

```text
可能降低总耗时；
但会提高服务压力和错误率。
```

使用小模型：

```text
可能降低成本；
但复杂任务准确率可能下降。
```

所以每次优化都应该同时比较：

```text
任务成功率；
答案质量；
Token；
成本；
P95 延迟；
错误率；
安全指标。
```

**面试表达**

```text
资源优化不能只看成本或延迟，因为 Agent 系统需要同时满足质量、稳定性和安全要求。比如减少 RAG 检索可以降低 Token 和延迟，但可能降低 Recall@K；取消 Reflection 可以节省一次模型调用，但可能增加 unsupported claim；提高并发可以缩短总时间，但可能造成 504 和连接池耗尽。工程上我会先定义质量和安全底线，再在这些约束下优化成本和延迟，并通过 Evaluation and Monitoring 比较任务成功率、P95 延迟、Token、错误率和安全指标。
```

一句话：

```text
资源优化不是用最少资源完成任务，而是用刚好足够的资源，可靠地完成任务。
```

#### 总结

这部分可以浓缩为：

```text
简单任务走短路径；
复杂任务才走深流程。

模型路由决定用哪个模型；
执行档位决定走多深；
预算决定最多消耗多少资源。

缓存避免重复计算；
批处理提高吞吐；
并行缩短独立任务耗时；
提前停止避免无收益执行。

资源优化必须在质量和安全底线之上，再优化成本与延迟。
```

结合 LocalAgent 可以这样说：

```text
在 LocalAgent 中，我会让 Router 同时判断任务类型和复杂度，并推荐 fast、balanced 或 deep Profile。Orchestrator 根据 Profile 配置模型、RAG、工具、多 Agent 和 Reflection，同时加载 max_steps、max_tool_calls、max_context_tokens、max_concurrency 和 timeout 等预算。通过 trace 记录 Token、延迟、调用次数和错误率，再使用 Evaluation and Monitoring 验证优化后质量是否保持稳定。
```

### 一句话总结

```text
Resource Aware Optimization 的本质是：根据任务价值和复杂度，投入刚好足够的模型、上下文、工具和计算资源。
```

再压缩一点：

```text
简单任务走短路径，复杂任务才用深流程。
```

对你的 LocalAgent 来说，可以浓缩成：

```text
通过 Profile 分级、模型路由、上下文裁剪、并发限制、执行预算和资源指标监控，让 LocalAgent 在保证质量和安全的前提下更快、更稳、更省资源。
```

## Chapter 19 Reasoning Techniques 推理技术

Reasoning Techniques（推理技术）关注的是：

```text
如何让 Agent 在复杂任务中更合理地拆解问题、选择步骤、使用证据、调用工具、检查结果，并最终得到可靠答案。
```

一句话：

```text
不是让模型“想得越多越好”，而是让它采用适合当前任务的推理流程。
```

这一节和前面的 Planning（规划）、Tool Use（工具使用）、Reflection（反思）、RAG（检索增强生成）关系非常紧密。

### 为什么 Agent 需要推理技术

简单问题通常可以直接回答：

```text
什么是 RAG？
Python 中 list 和 tuple 有什么区别？
```

但复杂任务可能包含：

```text
多个子问题；
多个约束；
前后依赖；
工具调用；
外部证据；
不确定信息；
多个可选方案。
```

例如：

```text
分析 LocalAgent 的架构问题，并给出按优先级排序的优化方案。
```

这个任务不能只靠一次自由生成完成，而需要：

```text
1. 理解用户目标；
2. 拆分分析维度；
3. 检索已有项目资料；
4. 分析架构、性能、安全和评估；
5. 比较不同方案；
6. 检查建议是否符合现有约束；
7. 汇总最终结论。
```

因此，推理技术的作用是：

```text
把复杂任务转成可执行、可检查、可纠正的过程。
```

### 主要推理技术

推理技术不等于输出完整思维过程

这里需要特别注意。

工程上希望 Agent（智能体）具备更好的推理能力，但不代表一定要向用户暴露完整内部思维过程。

更推荐输出：

```text
任务计划；
关键判断；
证据来源；
工具调用结果；
结论摘要；
不确定性；
验证结果。
```

而不是要求模型展示所有内部推理细节。

可以理解为：

```text
内部可以进行复杂推理；
外部输出结构化、可验证的依据和结论。
```

这对系统也更安全，因为日志真正需要的是：

```text
做了什么；
为什么选择这个步骤；
用了什么证据；
结果是否通过验证。
```

而不是保存大量不可控的自由文本推理。

#### Direct Answer：直接回答

Direct Answer（直接回答）是最简单的方式。

流程：

```text
用户问题
→ 模型直接生成答案
```

适合：

```text
简单事实解释；
简单格式转换；
短文本改写；
明确的语法问题；
低风险任务。
```

优点：

```text
速度快；
成本低；
实现简单。
```

缺点：

```text
不适合复杂多步骤问题；
容易遗漏约束；
难以验证中间过程。
```

例如：

```text
用户：Python 中字典是什么？

直接回答即可，不需要规划、检索和多 Agent。
```

#### Problem Decomposition：问题分解

Problem Decomposition（问题分解）是把复杂问题拆成多个较小问题。

例如：

```text
分析一个 Agent 项目是否适合上线。
```

可以拆成：

```text
1. 架构是否清晰；
2. 工具调用是否安全；
3. RAG 是否可靠；
4. 是否有异常恢复；
5. 是否有评估体系；
6. 性能和成本是否可控。
```

问题分解的价值：

```text
降低单步任务复杂度；
减少遗漏；
便于并行执行；
便于分模块评估；
便于定位错误。
```

这和 Planning 的区别是：

```text
Problem Decomposition 关注把问题拆成哪些子问题；
Planning 关注这些子问题按什么顺序执行。
```

#### Chain-of-Thought：思维链

Chain-of-Thought（思维链）指的是让模型通过多个中间步骤处理复杂问题，而不是直接给最终答案。

它适合：

```text
数学推理；
逻辑判断；
多约束问题；
复杂分析；
需要逐步验证的任务。
```

但在工程中，不应该简单理解成：

```text
让模型输出越长的推理越好。
```

更好的使用方式是要求结构化中间结果，例如：

```text
已知条件；
待解决问题；
执行步骤；
证据；
结论；
风险。
```

例如代码审查可以输出：

```text
问题位置；
触发条件；
影响；
修复建议；
验证方法。
```

而不是输出一大段散乱的“思考过程”。

#### Least-to-Most Prompting：由简到繁提示

Least-to-Most Prompting（由简到繁提示）是先解决简单子问题，再逐步解决复杂问题。

例如：

```text
目标：判断一段并发代码是否安全。
```

可以先处理：

```text
1. 找出共享资源；
2. 找出并发执行位置；
3. 检查是否有锁；
4. 检查共享状态更新；
5. 判断是否可能出现竞态条件。
```

适合：

```text
复杂问题依赖多个基础判断；
后一步需要使用前一步结果；
任务可以自然分层。
```

它和普通问题分解相比，更强调：

```text
子问题从简单到复杂逐步推进。
```

#### ReAct：推理与行动

ReAct（推理与行动）把推理和工具执行结合起来。

基本模式是：

```text
观察当前状态
→ 决定下一步动作
→ 调用工具
→ 获取结果
→ 更新判断
→ 决定是否继续
```

例如：

```text
用户：分析这个 Excel 文件为什么匹配失败。

Agent：
→ 先检查文件和 sheet；
→ 调用 inspect_excel；
→ 发现列名不一致；
→ 再读取表头；
→ 根据结果生成分析。
```

ReAct 的价值是：

```text
模型不需要凭空猜测；
可以根据真实工具结果逐步调整行动。
```

这和 Tool Use 的区别是：

```text
Tool Use 关注模型能调用工具；
ReAct 关注模型如何根据工具结果持续决定下一步。
```

适合：

```text
文件分析；
代码调试；
RAG 检索；
网页或数据库查询；
需要多轮工具调用的任务。
```

#### Self-Consistency：自洽性

Self-Consistency（自洽性）是让模型生成多个候选推理或答案，再选择一致性最高的结论。

例如：

```text
候选 A：问题来自连接池不足；
候选 B：问题来自系统代理；
候选 C：问题来自系统代理。
```

系统可能优先考虑 B 和 C 的共同结论。

适合：

```text
存在不确定性的推理任务；
答案可以通过多个独立路径得到；
重要任务需要降低偶然性。
```

缺点：

```text
模型调用次数增加；
成本和延迟上升；
多个错误答案也可能一致。
```

所以它不能只看投票，还要结合证据验证。

正确理解是：

```text
一致性可以提高稳定性，但不能代替事实依据。
```

#### Tree of Thoughts：思维树

Tree of Thoughts（思维树）是同时探索多个可能方案，再比较和筛选。

例如优化 LocalAgent 时，可以探索：

```text
方案 A：优先优化 RAG；
方案 B：优先优化 Tool Use；
方案 C：优先优化评估平台；
方案 D：先做 MCP 工具中心。
```

然后从这些维度比较：

```text
开发成本；
现有基础；
风险；
收益；
依赖关系。
```

最终选择更合适的路径。

适合：

```text
有多个可行方案；
需要比较取舍；
单一路径容易过早做出错误决定；
规划和探索类任务。
```

缺点：

```text
分支数量容易膨胀；
消耗大量 Token；
执行时间长；
需要设置最大深度和分支数。
```

因此要限制：

```text
max_branches；
max_depth；
max_candidates；
stop_condition。
```

#### Reflection：反思

Reflection（反思）是让模型或 Reviewer（审查器）检查已有结果并进行修正。

流程：

```text
生成初稿
→ 检查错误和遗漏
→ 给出修改建议
→ 生成修正版
```

检查内容可以包括：

```text
是否回答用户问题；
是否遗漏约束；
是否有无依据结论；
工具结果是否使用正确；
引用是否匹配；
格式是否符合要求。
```

适合：

```text
高价值答案；
代码审查；
架构设计；
RAG 答案；
需要严格格式的内容。
```

不适合所有简单任务，否则会增加不必要延迟。

#### Verifier：验证器

Verifier（验证器）负责独立检查结果是否正确。

它和 Reflection 的区别是：

```text
Reflection 更像“检查并修改自己的答案”；
Verifier 更像“根据规则、证据或工具独立验证答案”。
```

Verifier 可以检查：

```text
计算结果是否正确；
代码是否能运行；
工具是否真的成功；
引用是否支持结论；
JSON 是否符合 schema；
输出是否违反约束。
```

验证方式包括：

```text
规则校验；
程序运行；
单元测试；
Schema Validation（结构校验）；
RAG 引用检查；
独立模型审查。
```

工程上，Verifier 通常比单纯让模型“再想一遍”更可靠。

#### Program-Aided Reasoning：程序辅助推理

Program-Aided Reasoning（程序辅助推理）指的是把适合计算或验证的部分交给程序，而不是让模型自己算。

适合：

```text
数学计算；
数据统计；
表格处理；
日期计算；
代码执行；
复杂规则判断。
```

例如：

```text
不要让模型自己计算 10 万行 Excel 的统计结果；
应该让 Python 或数据工具计算，再让模型解释结果。
```

核心原则：

```text
模型负责理解和决策；
程序负责精确计算。
```

这样可以减少：

```text
算术错误；
统计错误；
数据编造；
重复计算。
```

#### Tool-Augmented Reasoning：工具增强推理

Tool-Augmented Reasoning（工具增强推理）比程序辅助推理范围更广。

它可以调用：

```text
搜索工具；
RAG；
数据库；
代码执行器；
文件工具；
监控接口；
外部 API。
```

流程：

```text
判断缺少什么信息
→ 选择工具
→ 调用工具
→ 根据结果继续推理
```

例如：

```text
用户问项目中 AsyncLLMClient 为什么设置 trust_env=False。

Agent 不应该凭记忆回答：
→ 先检索项目笔记；
→ 获取相关代码和问题记录；
→ 基于资料回答。
```

#### Structured Reasoning：结构化推理

Structured Reasoning（结构化推理）是工程中非常推荐的方法。

它要求模型按照固定结构返回中间决策。

例如 Router（路由器）输出：

```text
route；
confidence；
reason_summary；
requires_tool；
requires_rag。
```

Planner 输出：

```text
goal；
steps；
dependencies；
risk_level；
stop_condition。
```

Reviewer 输出：

```text
passed；
issues；
unsupported_claims；
revision_required。
```

它的优点：

```text
便于程序解析；
便于评估；
便于监控；
便于错误恢复；
减少自由文本不稳定。
```

对工程系统来说：

```text
结构化推理通常比要求模型输出长篇自由思考更有价值。
```

#### 不同推理技术如何选择

| 技术                                    | 适合场景               | 主要价值         |
| --------------------------------------- | ---------------------- | ---------------- |
| Direct Answer（直接回答）               | 简单低风险任务         | 快、便宜         |
| Problem Decomposition（问题分解）       | 复杂多维任务           | 降低复杂度       |
| Least-to-Most Prompting（由简到繁提示） | 有前后依赖的复杂问题   | 逐层推进         |
| ReAct（推理与行动）                     | 多轮工具任务           | 根据真实结果行动 |
| Self-Consistency（自洽性）              | 高不确定性问题         | 提高稳定性       |
| Tree of Thoughts（思维树）              | 多方案探索             | 比较不同路径     |
| Reflection（反思）                      | 高价值输出             | 发现并修正问题   |
| Verifier（验证器）                      | 可规则或工具验证的任务 | 独立确认正确性   |
| Program-Aided Reasoning（程序辅助推理） | 计算、统计、执行任务   | 提高精确度       |
| Structured Reasoning（结构化推理）      | 工程系统               | 可解析、可评估   |

### 推荐的 Agent 推理流程

真实工程中，不需要只选一种，而是组合使用。

推荐流程：

```text
用户输入
→ 判断任务复杂度
→ 简单任务直接回答
→ 复杂任务进行问题分解
→ Planner 生成步骤
→ 需要信息时调用 RAG 或工具
→ 根据工具结果继续执行
→ Verifier 检查事实和结果
→ 高价值任务进行 Reflection
→ 输出最终答案
```

可以压缩为：

```text
分解 → 行动 → 验证 → 修正。
```

### Reasoning 和 Planning 的区别

Planning 关注：

```text
下一步要做什么；
步骤顺序是什么；
哪些步骤有依赖；
什么时候结束。
```

Reasoning 关注：

```text
为什么选择这个步骤；
当前证据支持什么；
哪个方案更合理；
结果是否可信。
```

可以理解为：

```text
Planning 设计行动路线；
Reasoning 支撑路线中的判断。
```

### Reasoning 和 Reflection 的区别

Reasoning 发生在解决问题的过程中。

Reflection 通常发生在初步结果生成之后。

```text
Reasoning：
如何得到答案。

Reflection：
答案得到后是否需要修正。
```

但在复杂 Agent 中，两者可以交替出现：

```text
推理
→ 行动
→ 检查
→ 修正
→ 继续推理。
```

### Reasoning 和 RAG 的关系

RAG 提供外部资料。

Reasoning 决定：

```text
要检索什么；
哪些资料更可信；
资料之间是否冲突；
证据是否足够；
能得出什么结论。
```

所以：

```text
RAG 负责找证据；
Reasoning 负责使用证据。
```

没有 RAG，模型可能缺少项目事实。

没有合理推理，即使检索到正确文档，也可能得出错误结论。

### Reasoning 和 Tool Use 的关系

Tool Use 提供执行能力。

Reasoning 决定：

```text
是否需要工具；
选择哪个工具；
参数应该是什么；
工具结果说明了什么；
下一步是否继续。
```

一句话：

```text
工具负责做事，推理负责决定做什么和如何使用结果。
```

### Resource Aware Optimization 和推理技术的关系

推理越复杂，资源消耗通常越高。

例如：

```text
Self-Consistency 需要多次生成；
Tree of Thoughts 需要探索多个分支；
Reflection 需要额外模型调用；
多轮 ReAct 需要多次工具和模型交互。
```

所以要根据任务价值选择推理深度。

可以映射到执行档位：

```text
fast：
Direct Answer。

balanced：
Problem Decomposition + Tool Use + 必要验证。

deep：
Planning + ReAct + 多方案分析 + Reflection + Verifier。
```

核心原则：

```text
推理深度必须和任务复杂度匹配。
```

### 推荐结构化对象

为了避免自由推理失控，可以让各模块输出结构化结果。

Router：

```text
route；
confidence；
task_complexity；
recommended_profile。
```

Planner：

```text
goal；
steps；
dependencies；
required_tools；
stop_condition。
```

Agent：

```text
summary；
evidence；
confidence；
warnings；
next_action。
```

Verifier：

```text
passed；
issues；
evidence_check；
revision_required。
```

这样能做到：

```text
可执行；
可评估；
可追踪；
可恢复。
```

### 常见坑

#### 所有任务都要求复杂推理

会增加：

```text
Token；
延迟；
成本；
错误机会。
```

简单任务直接回答即可。

#### 把输出变长当成推理更强

长答案不等于正确答案。

真正重要的是：

```text
步骤合理；
证据可靠；
结论可验证；
约束被遵守。
```

#### 只依赖模型自我检查

模型可能重复自己的错误。

因此重要结论应该使用：

```text
工具验证；
代码执行；
规则检查；
RAG 证据；
独立 Verifier。
```

#### 探索分支无限增长

Tree of Thoughts 和多方案分析必须设置：

```text
最大分支；
最大深度；
停止条件；
资源预算。
```

#### 记录大量自由推理文本

这会造成：

```text
日志膨胀；
敏感信息风险；
难以结构化评估；
上下文爆炸。
```

更适合记录：

```text
计划；
动作；
证据；
结果；
错误；
决策摘要。
```

### 如何评估推理技术是否有效

可以关注：

```text
Task Success Rate：
任务成功率。

Reasoning Step Accuracy：
关键步骤正确率。

Plan Executability：
计划可执行性。

Tool Decision Accuracy：
工具选择正确率。

Evidence Support Rate：
结论证据支持率。

Verifier Pass Rate：
验证通过率。

Reflection Repair Rate：
反思修复率。

Over-reasoning Rate：
过度推理率。

Average Reasoning Cost：
平均推理成本。

End-to-End Latency：
端到端延迟。
```

评估不能只看质量，还要看：

```text
使用复杂推理后，质量提升是否值得增加的成本和延迟。
```

例如：

```text
增加 Reflection 后：
答案正确率提升 2%；
平均延迟增加 80%。
```

对简单任务可能不值得。

### 面试表达

可以这样回答：

```text
Reasoning Techniques 是让 Agent 在复杂任务中更合理地分解问题、选择行动、使用证据和验证结果的方法。工程上我不会要求所有任务都使用复杂推理，而是根据任务复杂度选择不同策略。简单任务直接回答；中等任务使用问题分解、工具调用和结果验证；复杂任务才启用 Planning、ReAct、多方案探索、Verifier 和 Reflection。
```

结合工程实现：

```text
我更关注结构化推理，而不是让模型输出大段自由思考。比如 Router 返回 route、confidence 和 task_complexity，Planner 返回 steps、dependencies 和 stop_condition，专业 Agent 返回 evidence、confidence 和 warnings，Verifier 返回 passed、issues 和 revision_required。这样推理过程可以被程序解析、监控和评估。
```

结合 LocalAgent：

```text
在 LocalAgent 中，我会把推理深度和 fast、balanced、deep 三种 Profile 绑定。fast 直接回答；balanced 使用问题分解、单 Agent、RAG 或工具和结果校验；deep 才使用完整 Planning、多 Agent、并行分析、Verifier 和 Reflection。同时设置 max_steps、max_tool_calls、max_reflection_rounds 和资源预算，避免过度推理。
```

### 需要掌握

#### 如何防止过度推理和资源浪费？

过度推理是指 Agent（智能体）在任务已经足够简单或已经获得可靠结果后，仍然继续规划、检索、调用工具、探索分支或进行多轮 Reflection（反思）。

常见表现包括：

```text
简单问题也生成复杂计划；
已经找到直接证据，仍继续多轮检索；
同一个工具被重复调用；
多个 Agent 重复分析相同内容；
答案已经通过验证，仍继续反思；
不断重新规划但没有产生新信息；
为了提高很小的质量收益，消耗大量 Token 和时间。
```

防止过度推理的核心原则是：

```text
推理深度要与任务复杂度匹配；
继续执行必须能带来新的有效信息。
```

**先判断任务复杂度**

不是所有任务都需要完整推理链路。

可以把任务分成：

```text
简单任务：
直接回答。

中等任务：
问题分解 + 必要的 RAG 或工具调用。

复杂任务：
Planning + 多步骤执行 + Verifier。

高价值复杂任务：
多 Agent + Reflection + 完整验证。
```

例如：

```text
“什么是向量数据库？”
→ 直接回答。

“分析 LocalAgent 的整体架构并提出优化方案”
→ 需要规划、检索、分模块分析和验证。
```

一句话：

```text
简单任务走短路径，复杂任务才走深流程。
```

**使用 Profile（执行档位）限制推理深度**

可以使用不同执行档位。

fast（快速档）

```text
单次模型调用；
不生成复杂计划；
通常不调用 RAG；
不使用多 Agent；
不进行 Reflection。
```

balanced（平衡档）

```text
允许简单问题分解；
允许必要的 RAG 和工具调用；
有限重试；
必要时进行一次验证。
```

deep（深度档）

```text
允许完整规划；
允许多 Agent 和并行；
允许多轮工具调用；
允许 Verifier 和 Reflection；
但仍然必须受预算和停止条件限制。
```

这样可以避免简单请求默认进入最复杂的执行链。

**设置程序级 Budget（预算）**

不能只在 prompt 中提醒模型“不要想太多”，而要由 Orchestrator（编排器）设置明确上限。

建议限制：

```text
max_steps；
max_model_calls；
max_tool_calls；
max_retrieval_calls；
max_retries；
max_replan_times；
max_reflection_rounds；
max_branches；
max_context_tokens；
max_execution_seconds。
```

例如：

```text
fast：
最多 1 次模型调用；
不允许重新规划和反思。

balanced：
最多 3 次模型调用；
最多 2 次检索；
最多 1 次反思。

deep：
允许更多步骤；
但仍有明确的最大调用次数和执行时间。
```

达到预算后，系统应：

```text
返回当前可用结果；
说明未完成部分；
采用降级方案；
或者 Safe Stop（安全停止）。
```

不能无限继续执行。

**为任务设置明确的停止条件**

Planner（规划器）生成计划时，不仅要说明做什么，还要说明什么时候停止。

常见停止条件：

```text
用户目标已经完成；
关键问题已经回答；
工具执行成功并通过校验；
已经获得足够的检索证据；
答案已经通过 Verifier；
达到目标置信度；
继续执行不能提供新的有效信息；
达到资源预算上限。
```

例如：

```text
RAG 已经召回直接回答问题的当前项目文档；
引用和答案都已通过验证；
此时不应继续扩大检索范围。
```

**使用 Early Stop（提前停止）**

Early Stop 用于在结果已经足够可靠时结束推理。

可以设计以下判断：

```text
goal_completed = true；
evidence_sufficient = true；
verification_passed = true；
new_information_gain 低于阈值；
remaining_budget 不足。
```

例如多个 Agent 分析时：

```text
code_expert 和 reviewer 已经基于代码证据得出一致结论；
不必再调用第三个 Agent 重复分析。
```

或者：

```text
工具已经准确计算出统计结果；
不必让模型再次自行计算。
```

**检查每一步是否带来新信息**

每次准备继续执行前，可以判断：

```text
这一步会获得什么新信息？
它会解决哪个未完成子目标？
它是否只是重复已有结果？
预期收益是否值得新增成本？
```

如果下一步只是重复之前的检索、分析或验证，就应该停止。

可以记录：

```text
information_gain：
本步骤新增信息量。

expected_value：
本步骤对完成目标的预期价值。

estimated_cost：
预计 Token、延迟和工具成本。
```

只有预期收益明显高于成本时才继续。

**限制重复检索和重复工具调用**

RAG（检索增强生成）和 Tool Use（工具使用）很容易被重复调用。

可以通过以下方式避免：

```text
缓存已经执行过的 query；
记录已经读取过的 chunk；
相同参数的只读工具结果复用；
相同 query 不重复检索；
工具失败后根据 error_type 调整参数，而不是原样无限重试。
```

例如：

```text
第一次检索：
AsyncLLMClient trust_env proxy

第二次如果仍使用完全相同 query 和过滤条件，
通常不会产生新结果，不应直接重复。
```

需要重新检索时，应明确改变：

```text
query；
metadata filter；
检索方式；
知识库范围；
top_k。
```

**限制 Reflection 和重新规划次数**

Reflection 不是越多越好。

多轮 Reflection 可能出现：

```text
把正确答案改坏；
反复修改措辞但不提高事实质量；
增加大量模型调用；
输出越来越复杂。
```

推荐：

```text
普通任务：
不进行 Reflection。

重要任务：
最多一次 Reflection。

高价值复杂任务：
最多一到两次，并且每次必须解决明确问题。
```

Replanning（重新规划）也一样。

只有在以下情况才重新规划：

```text
当前计划不可执行；
关键工具失败；
前置假设被证明错误；
用户目标发生变化；
出现新的关键约束。
```

不能因为输出不够完美就无限重新规划。

**优先使用 Verifier（验证器），而不是反复“再想一次”**

对于可以程序验证的问题，应该使用确定性验证，而不是继续让模型推理。

例如：

```text
数学结果：
使用计算器验证。

Python 代码：
运行语法检查或单元测试。

JSON 输出：
使用 schema 校验。

Excel 修改：
重新读取目标单元格验证。

RAG 答案：
检查 claim 是否被引用片段支持。
```

核心原则：

```text
能用程序验证的，不要依赖模型反复自我反思。
```

**控制 Tree of Thoughts 等探索分支**

Tree of Thoughts（思维树）或多方案探索容易导致分支膨胀。

必须限制：

```text
max_branches；
max_depth；
max_candidates；
max_total_steps。
```

还要提前定义筛选标准：

```text
是否满足用户目标；
是否符合约束；
是否有证据支持；
实现成本是否合理；
风险是否可接受。
```

低质量分支应尽早剪枝，而不是全部执行到底。

**压缩上下文和中间结果**

过度推理常伴随上下文不断膨胀。

应该：

```text
历史对话使用滚动摘要；
工具结果只保留关键字段；
RAG 只注入高相关 chunk；
多个 Agent 只接收最小必要上下文；
已经完成的步骤保留结论，不重复保留全部过程。
```

这样既减少 Token，也能降低无关信息对后续判断的干扰。

**通过 Evaluation and Monitoring（评估与监控）识别过度推理**

可以监控以下指标：

```text
Average Model Calls：
平均模型调用次数。

Average Tool Calls：
平均工具调用次数。

Average Reasoning Steps：
平均推理步数。

Reflection Rounds：
反思轮数。

Replanning Rate：
重新规划率。

Duplicate Tool Call Rate：
重复工具调用率。

Over-reasoning Rate：
过度推理率。

Token per Successful Task：
每个成功任务的 Token 消耗。

Marginal Quality Gain：
新增推理步骤带来的边际质量收益。
```

例如：

```text
加入第二轮 Reflection 后：
答案正确率只提升 1%；
但 Token 增加 40%，延迟增加 60%。
```

那么第二轮 Reflection 对大多数任务就不值得启用

**面试表达**

```text
防止过度推理的关键是让推理深度和任务复杂度匹配。工程上我会先通过 Router 判断任务复杂度，并选择 fast、balanced 或 deep Profile，再由 Orchestrator 加载 max_steps、max_model_calls、max_tool_calls、max_retrieval_calls、max_reflection_rounds 和 timeout 等资源预算。

同时，Planner 必须提供明确的 stop_condition。每次继续检索、工具调用或 Reflection 前，都要判断这一步是否能解决未完成目标、是否能带来新信息，以及预期收益是否值得增加的成本。如果目标已经完成、证据已经充足或验证已经通过，就触发 Early Stop。对于可程序验证的结果，优先使用 Verifier，而不是让模型反复自我思考。
```

**最终总结**

```text
防止过度推理不能只靠 prompt 提醒，而要通过任务分级、执行档位、资源预算、停止条件、提前停止、结果复用和程序验证共同实现。
```

再压缩一点：

```text
该直接答时直接答；
该调用工具时调用工具；
结果足够可靠时立即停止。
```

结合 LocalAgent：

```text
Router 决定推理深度，Profile 决定执行流程，Budget 限制资源上限，Verifier 判断结果是否完成，Orchestrator 负责提前停止。
```

这部分也可以直接用于回答面试中的“如何避免 Agent 无限循环、过度规划和成本失控”。

### 一句话总结

```text
Reasoning Techniques 的本质是：让 Agent 按照适合任务复杂度的方式，完成问题分解、证据获取、行动选择、结果验证和错误修正。
```

再压缩一点：

```text
简单任务直接答，复杂任务分解、行动、验证、修正。
```

结合 LocalAgent：

```text
LocalAgent 不需要让所有请求都进行复杂推理，而应该通过 Profile 和任务复杂度，动态选择直接回答、问题分解、工具增强、验证和反思。
```

# 第四章第三梯队：Prioritization（优先级排序）

这一节只需要掌握概念和基本工程思路，不必单独设计复杂模块。

Prioritization（优先级排序）关注的是：

```text
当 Agent 同时面对多个目标、子任务、工具、错误或候选方案时，应该优先处理哪一个。
```

一句话：

```text
Prioritization 的本质是：有限资源下，先做最重要、最紧急、最有价值的事情。
```

------

## 1. 为什么 Agent 需要优先级排序

Agent（智能体）执行复杂任务时，可能同时面对：

```text
多个用户目标；
多个子任务；
多个待调用工具；
多个异常；
多个检索结果；
多个可选方案；
有限的时间和资源预算。
```

例如用户要求：

```text
分析 LocalAgent 的架构问题、性能问题、安全问题和评估体系。
```

Agent 不一定要同时投入相同资源，而可以优先处理：

```text
1. 可能导致数据损坏的安全问题；
2. 影响系统运行的严重故障；
3. 用户明确要求的核心问题；
4. 普通性能优化；
5. 可选的体验改进。
```

如果没有优先级，Agent 可能出现：

```text
先做低价值任务；
忽略关键约束；
资源用完后核心目标还没完成；
同时执行太多不重要任务；
在次要问题上过度推理。
```

------

## 2. 常见优先级判断维度

Agent 可以从几个维度判断任务优先级。

### 2.1 重要性

这个任务对最终目标有多大影响。

例如：

```text
修复工具调用错误
通常比优化输出措辞更重要。
```

### 2.2 紧急性

是否有明确时间限制，或者问题是否正在影响系统运行。

例如：

```text
线上工具持续报错
优先于长期架构优化。
```

### 2.3 风险

不处理是否会导致数据、安全或业务风险。

一般优先级：

```text
安全问题
> 数据损坏问题
> 系统不可用问题
> 功能错误
> 性能问题
> 体验优化。
```

### 2.4 依赖关系

某个任务是否是其他任务的前置条件。

例如：

```text
必须先读取 Excel 结构，
才能确定后续修改方案。
```

即使读取动作价值不高，也必须优先执行。

### 2.5 收益与成本

完成任务能带来多大收益，需要消耗多少资源。

例如：

```text
花一次检索就能解决关键问题
优先于需要五次模型调用、但收益很小的分析。
```

### 2.6 用户明确要求

用户明确指定的重点应优先于 Agent 自己推测的次要目标。

例如用户说：

```text
先不要修改代码，只分析架构。
```

那 Agent 就不能优先生成代码。

------

## 3. 一个简单优先级顺序

可以使用以下基本顺序：

```text
安全和权限
→ 用户明确约束
→ 阻塞性问题
→ 核心目标
→ 前置依赖
→ 高收益任务
→ 普通优化
→ 可选任务。
```

例如在 Excel 修改任务中：

```text
1. 检查文件和工作表是否存在；
2. 确认用户目标和覆盖范围；
3. 判断是否需要审批和备份；
4. 执行核心匹配逻辑；
5. 校验结果；
6. 最后再优化输出格式。
```

------

## 4. Prioritization 和 Planning 的区别

Planning（规划）关注：

```text
任务要拆成哪些步骤；
这些步骤按什么顺序执行。
```

Prioritization 关注：

```text
多个步骤或目标中，哪个更重要；
资源不足时优先保留哪个。
```

一句话：

```text
Planning 负责排流程；
Prioritization 负责排轻重。
```

例如 Planner 生成了十个任务，但资源只能完成五个，就需要优先级排序决定保留哪些任务。

------

## 5. 和其他模式的关系

### 和 Goal Setting and Monitoring（目标设定与监控）

目标决定什么最重要，优先级排序决定先处理哪个目标。

```text
Goal 决定方向；
Prioritization 决定先后。
```

### 和 Resource Aware Optimization（资源感知优化）

资源有限时，优先级排序决定资源投入到哪里。

例如：

```text
优先给核心任务使用强模型；
次要任务使用小模型或直接跳过。
```

### 和 Guardrails（护栏）

安全规则通常拥有最高优先级。

例如：

```text
即使用户急着执行，
高风险工具仍然必须先完成权限检查和人工审批。
```

### 和 Exception Handling and Recovery（异常处理与恢复）

多个异常同时发生时，要优先处理：

```text
安全异常；
阻塞主流程的异常；
可恢复且收益较高的异常；
非关键警告。
```

------

## 6. 常见实现方法

第三梯队只需理解几种简单方式。

### 6.1 固定规则

例如：

```text
危险任务优先级最高；
阻塞任务高于非阻塞任务；
核心目标高于可选目标。
```

优点是简单、稳定、容易解释。

### 6.2 优先级分数

可以根据多个因素计算一个分数：

```text
优先级 = 重要性 + 紧急性 + 风险 + 依赖权重 - 执行成本。
```

不必真的依赖非常复杂的数学模型，重点是统一判断标准。

### 6.3 优先队列

Orchestrator（编排器）可以把任务放进优先队列，根据优先级依次执行。

任务状态可以包含：

```text
task_id；
priority；
risk_level；
dependencies；
estimated_cost；
status。
```

### 6.4 动态调整

优先级不一定固定。

例如：

```text
某工具失败后，异常恢复任务优先级上升；
用户补充新要求后，原计划优先级重新调整；
资源即将耗尽时，非核心任务优先级下降。
```

------

## 7. LocalAgent 中的简单应用

在 LocalAgent（本地智能体项目）中，可以由 Router（路由器）或 Planner 给子任务设置：

```text
priority；
risk_level；
required；
dependencies；
estimated_cost。
```

Orchestrator 再根据这些字段决定执行顺序。

例如：

```text
任务 A：检查文件是否存在
priority = high
required = true

任务 B：分析 Excel 数据
priority = high
depends_on = A

任务 C：生成可视化报告
priority = medium
depends_on = B

任务 D：优化报告措辞
priority = low
```

资源不足时，可以跳过 D，但不能跳过 A 和 B。

对于多个异常：

```text
permission_denied：
最高优先级，立即停止相关操作。

file_not_found：
高优先级，阻塞当前任务。

format_warning：
低优先级，可继续执行。
```

------

## 8. 常见问题

### 问题一：只按任务出现顺序执行

先出现不等于更重要。

应该考虑风险、依赖和目标价值。

### 问题二：让模型自由决定全部优先级

模型可以提供建议，但安全、权限和核心业务优先级最好由程序规则控制。

### 问题三：高优先级任务过多

如果所有任务都是最高优先级，就等于没有优先级。

### 问题四：优先级不动态更新

任务状态、异常和用户目标发生变化后，优先级也应该重新计算。

------

## 9. 面试表达

可以这样回答：

```text
Prioritization 是 Agent 在多个目标、子任务和有限资源之间确定执行先后顺序的机制。它通常会综合考虑重要性、紧急性、风险、任务依赖、用户约束以及收益成本。工程上我会让 Planner 为子任务生成 priority、required、dependencies 和 estimated_cost 等字段，再由 Orchestrator 根据规则或优先队列调度。安全检查、用户明确约束和阻塞性任务优先级最高，资源不足时可以跳过低价值可选任务，但不能跳过核心目标和安全步骤。
```

结合 LocalAgent 可以说：

```text
在 LocalAgent 中，我会优先处理权限和安全检查，其次处理阻塞主流程的任务和用户核心目标，再执行普通分析和可选优化。例如 Excel 修改任务中，文件检查、参数确认、审批和备份必须优先于实际写入，报告美化则属于低优先级任务。当资源预算不足时，Orchestrator 可以跳过低优先级步骤，并返回核心结果。
```

------

## 10. 这一节只需掌握什么

```text
1. Prioritization 的定义；
2. 为什么多目标 Agent 需要优先级；
3. 重要性、紧急性、风险、依赖和成本是主要判断维度；
4. Planning 排流程，Prioritization 排轻重；
5. 安全、用户约束和阻塞任务通常优先；
6. 可以使用固定规则、评分或优先队列实现；
7. 优先级需要根据任务状态动态调整。
```

最核心一句：

```text
Prioritization 的本质是：有限资源下，先保证安全和核心目标，再处理普通优化和可选任务。
```
