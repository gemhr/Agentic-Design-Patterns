# Part Four

我建议按这个顺序学：

````
1. Evaluation and Monitoring
2. Guardrails Safety Patterns
3. Inter Agent Communication
4. Resource Aware Optimization
5. Reasoning Techniques
6. Prioritization
7. Exploration and Discovery
## 第一梯队：必须重点掌握

### 1. Evaluation and Monitoring（评估与监控）

这是第四章最重要的一节。

原因很简单：面试官会非常关心你是不是只会做 Demo（演示项目），还是知道怎么把 Agent 做成可评估、可迭代的工程系统。

你自己的 LocalAgent（本地智能体项目）里已经有这个方向：

```
Router 正确率；
Tool Call 正确率；
RAG Recall@K；
Citation Accuracy；
Answer Usefulness；
Bad Case 分类；
回归测试平台。
```

这一节和你的项目高度重合，必须重点学。

面试价值：**极高。**

------

### 2. Guardrails Safety Patterns（护栏安全模式）

这节也很重要。

原因是 Agent 一旦能调用工具，就会涉及风险：

```
写文件；
删文件；
执行 shell；
更新数据库；
发送请求；
读取敏感信息；
越权调用工具。
```

这和第三章的 Human-in-the-Loop（人类在环）、Exception Handling and Recovery（异常处理与恢复）关系很强。

面试里如果你能说清楚：

```
工具白名单；
参数校验；
权限控制；
高风险操作确认；
输出过滤；
Prompt Injection 防护；
数据脱敏；
审计日志；
Safe Stop。
```

会非常加分。

面试价值：**高。**

------

### 3. Inter Agent Communication（智能体间通信）

你前面已经学过 Multi-Agent Collaboration（多智能体协作），但多智能体真正难的不是“有多个 Agent”，而是：

```
Agent 之间传什么；
用什么格式传；
谁负责调度；
失败怎么回传；
冲突怎么处理；
状态怎么同步；
结果怎么聚合。
```

这节对你的 LocalAgent 也很重要，因为你有：

```
core_router；
code_expert；
data_analyst；
knowledge_expert；
aw_script_expert；
Aggregator；
Reviewer。
```

面试里讲多 Agent 时，如果只说“多个专家分工”，会显得浅；如果能讲通信协议、状态结构、消息格式、错误传播，就明显更工程化。

面试价值：**高。**

------

## 第二梯队：需要掌握，但不用过度深入

### 4. Resource Aware Optimization（资源感知优化）

这节很实用。

Agent 系统会消耗很多资源：

```
token；
模型调用次数；
工具调用次数；
检索耗时；
并发连接；
上下文长度；
本地 embedding 内存；
向量库检索时间。
```

你之前也遇到过本地 embedding（向量化模型）占用 4G 内存、并发请求、连接池等问题，所以这节对你有实际价值。

但面试里一般不会单独深问，更多是在系统设计里体现：

```
为什么要限制 max_steps；
为什么要控制 top_k；
为什么要做 context compression；
为什么要选择小模型 / 大模型分层；
为什么要限制并发；
为什么要做缓存。
```

面试价值：**中高。**

------

### 5. Reasoning Techniques（推理技术）

这节要学，但要注意分寸。

面试里如果你只讲 Chain-of-Thought（思维链）、Tree-of-Thought（思维树）这些名词，可能价值不大，甚至容易显得“偏 Prompt 技巧”。

真正有用的是从工程角度理解：

```
任务分解；
逐步验证；
Self-Consistency；
先计划后执行；
先生成再检查；
复杂问题拆成子问题；
让模型输出结构化推理结果而不是裸答案。
```

也就是说，这节应该和 Planning（规划）、Reflection（反思）、Goal Monitoring（目标监控）结合起来学。

面试价值：**中高。**

------

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

