# Part Three

## Chapter 12 Exception Handling and Recovery 异常处理与恢复

### 是什么

**Exception Handling and Recovery，异常处理与恢复**，指的是：

Agent 在执行任务过程中遇到错误、失败、超时、工具异常、模型输出不合法、检索为空、权限不足等情况时，能够识别异常、记录异常、选择恢复策略，并尽可能继续完成任务或给出清晰失败原因。

普通 Agent 遇到异常可能是：

```text
用户输入
→ Agent 调用工具
→ 工具失败
→ 程序报错 / 直接中断 / 输出不完整答案
```

具备 Exception Handling and Recovery 的 Agent 是：

```text
用户输入
→ Agent 执行任务
→ 检测异常
→ 判断异常类型
→ 选择恢复策略
→ 重试 / 降级 / 换工具 / 重新规划 / 请求补充信息
→ 输出最终结果或清晰失败报告
```

该模式关注的是如何打造高度稳健、富有韧性的智能体，使其在面对各种困难和异常时，仍能维持功能连续性与运行完整性。它强调事前预案与事后响应并重，以确保系统即使遭遇挑战，也能持续运行。这种适应能力，是智能体在复杂、不可预测环境中成功发挥作用的关键，也有助于提升其整体效能与可信度。

它的核心思想是：

```text
Agent 系统不可能永远不出错，真正重要的是出错后能不能稳定恢复。
```

### 为什么重要

Agent 系统比普通聊天应用更容易出错。

因为它不只是生成文本，还会：

```text
1. 调用模型；
2. 调用工具；
3. 读取文件；
4. 查询数据库；
5. 检索知识库；
6. 运行代码；
7. 解析 JSON；
8. 多 Agent 协作；
9. 并行执行任务；
10. 维护记忆和上下文。
```

这些环节每一个都可能失败。

例如：

```text
LLM 请求超时；
模型输出不是合法 JSON；
Router 返回了未知 route；
Planner 生成了不可执行计划；
Tool Call 缺少参数；
文件路径不存在；
Excel sheet 不存在；
RAG 检索为空；
Reflection 修正后引入新错误；
并行 Worker 部分失败；
MCP Server 连接失败；
Memory 检索出过期信息。
```

如果没有异常处理，Agent 会出现：

```text
1. 整个程序崩溃；
2. 用户看不到失败原因；
3. 工具失败后仍然假装成功；
4. 模型根据不存在的工具结果继续编造；
5. 多 Agent 中一个失败导致全局失败；
6. 无法记录 bad case；
7. 后续无法学习和改进；
8. 系统不适合真实工程使用。
```

所以这一节非常重要，它解决的是 Agent 的 **可靠性** 问题。

### Exception Handling 和 Recovery 分别是什么

#### Exception Handling：异常处理

Exception Handling 关注的是：

```text
发现异常、捕获异常、分类异常、记录异常、阻止系统崩溃。
```

例如：

```python
try:
    result = tool(**arguments)
except FileNotFoundError as e:
    return {
        "success": False,
        "error_type": "file_not_found",
        "message": str(e)
    }
```

它的目标不是立刻解决问题，而是先让异常变得可见、可控。

#### Recovery：恢复

Recovery 关注的是：

```text
异常发生后，系统下一步应该怎么做。
```

常见恢复方式：

```text
1. 重试；
2. 修正参数后重试；
3. 换一个工具；
4. 降级为部分结果；
5. 重新规划；
6. 请求用户补充信息；
7. 跳过失败子任务；
8. 返回清晰失败报告；
9. 记录 bad case；
10. 更新记忆或策略。
```

例如：

```text
analyze_excel 失败：sheet_name 不存在
→ Recovery：
先调用 inspect_excel 获取可用 sheet
→ 重新选择 sheet
→ 再调用 analyze_excel
```

一句话：

```text
Exception Handling 是“别崩”；Recovery 是“尽量继续完成任务”。
```

### Agent 中常见异常类型

Agent 的异常可以分很多层。

#### LLM 调用异常

例如：

```text
请求超时；
接口 429 限流；
接口 500 / 502 / 504；
API Key 错误；
模型名错误；
返回内容为空；
返回格式不符合预期。
```

在你的项目中，典型案例就是：

```text
同步请求可以跑；
异步并发请求 qwen 报 504；
后来定位到 httpx.AsyncClient 的 trust_env / 代理 / 连接池问题。
```

这就是非常真实的 LLM 调用异常。

#### 模型输出异常

模型输出不一定稳定。

常见情况：

```text
1. 应该输出 JSON，结果输出自然语言；
2. JSON 少了字段；
3. route 输出了未知值；
4. tool_name 不在工具白名单；
5. arguments 类型错误；
6. Planner 生成了不可执行步骤；
7. Reflection 输出了错误判断；
8. 最终答案违反用户格式要求。
```

例如 Router 要求输出：

```json
{"route": "data_analyst"}
```

但模型输出：

```text
我认为这个问题应该交给数据分析专家处理。
```

这就属于模型输出格式异常。

#### Tool Call 异常

工具调用是 Agent 最容易出错的地方。

常见情况：

```text
工具不存在；
参数缺失；
参数类型错误；
文件路径不存在；
文件格式不支持；
权限不足；
工具执行超时；
工具内部异常；
工具返回结果为空；
工具返回结果过大。
```

例如：

```text
工具：analyze_excel
错误：sheet_name 缺失
恢复：先调用 inspect_excel，再重新调用 analyze_excel
```

#### RAG / Memory 异常

检索相关异常：

```text
检索为空；
召回无关内容；
引用来源不存在；
检索结果过长；
向量库连接失败；
FTS 查询失败；
记忆过期；
记忆冲突；
记忆污染。
```

恢复策略可能是：

```text
改写 query；
扩大 top_k；
改用关键词检索；
使用混合检索；
明确告诉用户没有找到依据；
不基于空检索结果编造答案。
```

#### Planning / Goal 异常

计划和目标相关异常：

```text
计划步骤不可执行；
步骤顺序错误；
遗漏关键子目标；
目标不清晰；
成功标准缺失；
执行过程中目标偏离；
达到最大步数仍未完成；
Replanning 无限循环。
```

恢复策略：

```text
重新提取目标；
重新规划；
减少步骤；
请求用户明确目标；
触发停止条件；
返回部分完成结果。
```

#### Multi-Agent / Parallelization 异常

多 Agent 和并行任务中常见：

```text
某个 Worker 失败；
某个 Agent 无响应；
多个 Agent 结论冲突；
Aggregator 无法合并结果；
并发过高导致请求失败；
一个任务失败影响全局；
部分结果成功、部分失败。
```

恢复策略：

```text
允许 partial success；
失败 Worker 单独记录；
Aggregator 汇总成功结果；
对失败部分说明原因；
必要时降低并发重试；
冲突交给 Reviewer 判断。
```

#### MCP 异常

MCP 相关异常包括：

```text
MCP Server 启动失败；
stdio 输出被日志污染；
initialize 失败；
capability 不支持；
tools/list 失败；
tools/call 参数错误；
resources/read 失败；
连接中断；
权限被拒绝；
高风险工具未确认。
```

尤其 stdio 模式要注意：

```text
stdout 只能输出 MCP JSON-RPC 消息；
普通日志必须写 stderr；
否则 Client 解析会失败。
```

### 异常处理的核心流程

Agent 异常处理可以抽象成：

```text
Detect → Classify → Log → Recover → Report → Learn
```

中文是：

```text
检测异常
→ 分类异常
→ 记录日志
→ 执行恢复策略
→ 向用户报告结果
→ 沉淀为 bad case 或经验
```

#### Detect：检测异常

系统要能发现：

```text
工具返回 failed；
模型输出格式不合法；
JSON 解析失败；
route 不在允许列表；
工具参数校验失败；
文件不存在；
请求超时；
结果为空；
执行超过最大步数。
```

没有检测，就不会有恢复。

#### Classify：异常分类

异常不能只写：

```text
error
```

要分类：

```text
llm_timeout
llm_rate_limit
invalid_json
unknown_route
tool_not_found
missing_argument
file_not_found
permission_denied
retrieval_empty
goal_drift
max_steps_exceeded
mcp_server_error
```

分类的价值是：

```text
不同异常对应不同恢复策略。
```

#### Log：记录日志

异常日志至少要记录：

```text
trace_id；
stage；
agent_name；
tool_name；
input_summary；
error_type；
error_message；
recoverable；
recovery_action；
status；
elapsed_seconds；
timestamp。
```

例如：

```json
{
  "trace_id": "trace_001",
  "stage": "tool_call",
  "agent_name": "data_analyst",
  "tool_name": "analyze_excel",
  "error_type": "sheet_not_found",
  "error_message": "Sheet 86 not found",
  "recoverable": true,
  "recovery_action": "call inspect_excel",
  "status": "recovering"
}
```

异常日志是后续 Learning and Adaptation 的基础。

#### Recover：恢复

根据异常类型选择恢复策略。

例如：

```text
invalid_json
→ 重新要求模型按 JSON 输出
→ 或用 JSON repair
→ 或 fallback 到规则解析

missing_argument
→ 返回缺失字段
→ 让模型补全参数
→ 或调用 inspect 工具获取候选值

file_not_found
→ 检查路径
→ 列出当前目录
→ 请求用户提供正确路径

retrieval_empty
→ 改写 query
→ 扩大 top_k
→ 切换关键词检索
→ 如果仍为空，说明没有找到依据

llm_timeout
→ 重试
→ 降低并发
→ 切换模型
→ 返回部分结果
```

#### Report：报告结果

恢复成功时，要说明：

```text
遇到了什么问题；
如何恢复；
最终结果是什么。
```

恢复失败时，要说明：

```text
失败在哪一步；
原因是什么；
已经尝试了哪些恢复方式；
用户可以怎么继续。
```

不要简单输出：

```text
出错了。
```

更好的输出：

```text
我尝试读取 86 这个 sheet，但文件中没有找到该 sheet。
随后我检查了工作簿，发现可用 sheet 是 85、8011。
因此当前无法按“86 → 85 / 8011”的规则执行覆盖操作。
请确认源 sheet 名称是否应该是其他名称。
```

#### Learn：沉淀经验

异常不是处理完就结束。

应该沉淀为：

```text
bad case；
工具调用日志；
记忆；
回归测试样例；
Prompt / schema 优化依据。
```

例如：

```text
Tool Call 经常缺少 sheet_name
→ 更新工具 schema
→ 在 Planner 中加入 inspect_excel 前置步骤
→ 加入 Tool Call 回归测试
```

这就和第二章 Learning and Adaptation 连起来了。

### Recovery 的常见策略

#### Retry：重试

适合临时性错误：

```text
网络抖动；
LLM timeout；
临时 502 / 504；
数据库连接短暂失败。
```

但重试要有限制：

```python
max_retries = 2
retry_delay = 1.0
```

不能无限重试。

适合使用指数退避：

```text
第 1 次失败 → 等 1 秒；
第 2 次失败 → 等 2 秒；
第 3 次失败 → 停止并报告。
```

#### Parameter Repair：参数修复

适合工具参数错误。

例如：

```text
缺少 sheet_name；
column 参数传了数字但工具要求字母；
路径格式错误；
JSON 字段名不匹配。
```

恢复方式：

```text
返回结构化错误；
让模型重新生成参数；
或调用 inspect 工具获取候选值。
```

示例：

```text
analyze_sheet 缺少 sheet_name
→ inspect_excel 获取 sheet 列表
→ 选择最相关 sheet
→ 重新调用 analyze_sheet
```

#### Fallback：降级

当主策略失败时，使用备用策略。

例如：

```text
向量检索失败 → 使用关键词检索；
异步并发失败 → 降低并发或顺序执行；
MCP Server 不可用 → 使用内部工具函数；
完整分析失败 → 返回部分分析；
模型 A 超时 → 切换模型 B。
```

Fallback 的意义是：

```text
不要因为一个能力失败，就让整个任务失败。
```

#### Replanning：重新规划

适合当前计划无法继续。

例如：

```text
原计划：读取文件 → 分析文件 → 输出总结
异常：文件不存在
恢复：重新规划为 list_files → 找候选文件 → 再读取
```

Replanning 要注意限制次数：

```python
max_replan_times = 2
```

避免无限循环。

#### Partial Success：部分成功

并行、多 Agent、批量任务中很重要。

例如：

```text
三个 Worker：
summary_worker 成功；
questions_worker 成功；
key_terms_worker 失败。
```

不要直接让整个任务失败。

可以输出：

```text
已完成摘要和问题生成；
关键词提取失败，原因是模型请求超时；
以下是已完成部分。
```

这比全局失败更好。

#### Ask for Clarification：请求澄清

当缺少关键信息时，需要用户补充。

例如：

```text
用户要求修改 Excel，但没有提供文件路径；
用户说“那个 demo”，但 Memory 也无法确定是哪一个；
工具需要 API Key，但环境变量不存在；
高风险写操作需要确认。
```

但要注意：

```text
能自动推断和恢复的，不要频繁问用户；
真正缺少关键条件时，才请求澄清。
```

#### Safe Stop：安全停止

当无法恢复或风险过高时，应该停止。

例如：

```text
工具连续失败；
达到最大重试次数；
高风险操作未确认；
目标不清晰；
权限不足；
检测到可能破坏数据。
```

安全停止输出应包括：

```text
已完成什么；
失败在哪里；
为什么停止；
如何继续。
```

### 异常结果应该结构化

无论是工具、Agent，还是整体 Orchestrator，都应该返回结构化异常。

例如：

```json
{
  "success": false,
  "error_type": "sheet_not_found",
  "message": "Sheet '86' does not exist in this workbook.",
  "recoverable": true,
  "recovery_suggestion": "Call inspect_excel to list available sheets.",
  "stage": "tool_call",
  "tool_name": "analyze_excel"
}
```

结构化异常的好处：

```text
1. Planner 能判断是否需要重新规划；
2. Monitor 能判断子目标是否阻塞；
3. Reflection 能检查最终答案是否诚实；
4. Learning 能转成 bad case；
5. 前端能展示清晰错误状态；
6. 用户能理解失败原因。
```

### 和前面章节的关系

#### 和 Tool Use 的关系

Tool Use 让 Agent 能调用工具。

Exception Handling 保证：

```text
工具调用失败时不会直接崩溃；
工具参数错误时可以修复；
工具结果为空时不会编造；
高风险工具会触发确认或停止。
```

#### 和 Planning 的关系

Planning 生成计划。

Recovery 可以在计划失败时触发：

```text
Replanning
```

例如：

```text
步骤 2 失败
→ Monitor 标记 blocked
→ Planner 重新生成替代步骤
```

#### 和 Reflection 的关系

Reflection 可以参与恢复。

例如：

```text
模型输出 JSON 不合法
→ Critic 检查格式问题
→ Reviser 修复 JSON
```

但要注意：

```text
Reflection 不能替代真实工具校验。
```

例如代码是否能运行，还是要靠 `ast.parse`、pytest 或实际工具。

#### 和 Memory 的关系

Memory 可以记录历史异常和恢复经验。

例如：

```text
用户公司的 qwen 异步请求容易受代理影响；
AsyncLLMClient 默认 trust_env=False。
```

下次遇到类似问题可以直接复用经验。

#### 和 Learning and Adaptation 的关系

异常处理产生 bad case。

Learning 根据 bad case 改进：

```text
工具参数频繁错误
→ 优化 schema

Router 经常输出未知 route
→ 加强 route 约束

RAG 经常检索为空
→ 增加 query rewrite
```

#### 和 Goal Monitoring 的关系

Monitoring 负责判断异常是否阻塞目标。

例如：

```text
某个工具失败
→ 当前子目标是否还能完成？
→ 是否需要换工具？
→ 是否需要重新规划？
→ 是否应该停止？
```

#### 和 MCP 的关系

MCP 工具调用也需要完整异常处理。

例如：

```text
MCP Server 启动失败；
tools/list 失败；
tools/call 参数错误；
权限拒绝；
stdio 输出格式错误。
```

MCP Server 返回错误时，Host 不能直接崩溃，而要转换成可恢复的 Agent 状态。

### 在 LocalAgent 中如何应用

你的 LocalAgent 非常需要这一节。

可以设计一个统一异常结果对象：

```python
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentError:
    error_type: str
    message: str
    stage: str
    recoverable: bool
    recovery_suggestion: str | None = None
    details: dict[str, Any] | None = None
```

也可以设计统一工具结果：

```python
@dataclass
class ToolResult:
    success: bool
    data: Any | None = None
    error: AgentError | None = None
    summary: str | None = None
```

这样所有工具都返回统一结构：

```text
成功：success=True + data
失败：success=False + error
```

#### Router 异常

可能异常：

```text
模型输出未知 route；
route 为空；
confidence 太低；
JSON 解析失败。
```

恢复策略：

```text
1. 尝试 normalize_route；
2. 使用规则 fallback；
3. 进入 unclear / fallback handler；
4. 记录 routing_error bad case。
```

#### Planner 异常

可能异常：

```text
计划为空；
步骤不可执行；
工具不存在；
步骤太多；
没有停止条件。
```

恢复策略：

```text
1. 要求重新生成结构化计划；
2. 限制最大步骤数；
3. 删除不可执行步骤；
4. 使用默认模板计划；
5. 失败则返回无法规划原因。
```

#### Tool Executor 异常

可能异常：

```text
工具不存在；
参数不合法；
权限不足；
工具超时；
执行失败。
```

恢复策略：

```text
1. 工具白名单校验；
2. 参数 schema 校验；
3. 参数修复；
4. 重试；
5. 降级；
6. 高风险操作请求确认；
7. 返回结构化错误。
```

#### Data Analyst 异常

可能异常：

```text
Excel 文件不存在；
sheet 不存在；
列不存在；
复合键重复；
写入权限不足；
文件被占用。
```

恢复策略：

```text
1. 先 inspect_excel；
2. 列出可用 sheet 和列名；
3. 对列名做规范化；
4. 写入前备份；
5. 失败时返回可恢复建议。
```

#### Knowledge Expert 异常

可能异常：

```text
检索为空；
检索结果无关；
向量库不可用；
引用缺失；
上下文过长。
```

恢复策略：

```text
1. query rewrite；
2. FTS + vector 混合检索；
3. top_k 扩大；
4. rerank；
5. 找不到依据时明确说明；
6. 不允许编造引用。
```

#### Multi-Agent 异常

可能异常：

```text
某个 Agent 失败；
Agent 输出格式不合法；
多个 Agent 冲突；
Aggregator 汇总失败。
```

恢复策略：

```text
1. 允许部分成功；
2. 失败 Agent 单独标记；
3. Aggregator 只汇总成功结果；
4. 冲突交给 Reviewer；
5. 最终答案说明哪些部分失败。
```

### 和 [[ORCH]] 事件结合

你可以在 LocalAgent 的 `[[ORCH]]` 协议里增加异常事件。

例如：

```json
{
  "type": "exception_detected",
  "trace_id": "trace_001",
  "stage": "tool_call",
  "agent_name": "data_analyst",
  "tool_name": "analyze_excel",
  "error_type": "sheet_not_found",
  "message": "Sheet '86' not found",
  "recoverable": true
}
```

恢复开始：

```json
{
  "type": "recovery_started",
  "trace_id": "trace_001",
  "strategy": "call_inspect_excel",
  "reason": "sheet_not_found"
}
```

恢复成功：

```json
{
  "type": "recovery_succeeded",
  "trace_id": "trace_001",
  "strategy": "call_inspect_excel",
  "summary": "Found available sheets: 85, 8011"
}
```

恢复失败：

```json
{
  "type": "recovery_failed",
  "trace_id": "trace_001",
  "reason": "Required source sheet is missing",
  "safe_stop": true
}
```

接入价值：

```text
1. 前端能展示 Agent 在哪里失败；
2. 用户能看到系统尝试了什么恢复；
3. 调试时可以回放完整链路；
4. 异常可以进入 bad case；
5. 评估平台可以统计 Recovery Success Rate。
```

这会让你的 Agent 系统更像真实工程系统。

### 常见坑

#### 只 try except，不分类

差的写法：

```python
except Exception as e:
    return str(e)
```

问题是：

```text
不知道错误类型；
不知道能不能恢复；
无法自动选择恢复策略；
无法进入 bad case 分类。
```

#### 工具失败后继续编造

这是 Agent 系统大忌。

例如：

```text
RAG 检索为空
→ 模型仍然编造答案
```

正确做法：

```text
明确说明没有找到依据；
尝试改写检索；
仍失败则停止或给出基于现有信息的有限回答。
```

#### 无限重试

重试必须有限制。

```text
max_retries
max_steps
max_replan_times
max_tool_calls
```

否则 Recovery 会变成死循环。

#### 把所有异常都交给模型解决

模型可以帮助修复格式、重新生成参数，但真实异常必须由程序判断。

例如：

```text
文件是否存在；
JSON 是否合法；
代码是否能运行；
工具是否成功；
权限是否允许。
```

这些应该由程序或工具判断，不应只靠模型自评。

#### 不给用户清晰失败原因

失败时不能只说：

```text
我无法完成。
```

应该说：

```text
我在哪一步失败；
失败原因是什么；
我尝试了什么恢复；
还需要用户提供什么；
哪些部分已经完成。
```

### 需要掌握

#### 必须掌握

##### Exception Handling and Recovery 的定义是什么？

见上文 **“第三章第一节：Exception Handling and Recovery 是什么”** 部分。

核心一句话：

```text
Exception Handling and Recovery 的本质是：让 Agent 在出错时不崩溃、不编造，而是能识别异常、选择恢复策略，并清楚说明结果。
```

再压缩一点：

```text
异常处理负责别崩，恢复机制负责尽量继续。
```

##### Exception Handling 和 Recovery 的区别是什么？

见上文 **“Exception Handling 和 Recovery 分别是什么”** 部分。

简要总结：

```text
Exception Handling 关注发现、捕获、分类和记录异常；
Recovery 关注异常发生后如何继续推进任务。
```

对比：

| 能力               | 核心问题               | 典型动作                                               |
| ------------------ | ---------------------- | ------------------------------------------------------ |
| Exception Handling | 哪里出错了，如何不崩溃 | try-except、错误分类、日志记录、结构化错误             |
| Recovery           | 出错后怎么办           | 重试、参数修复、fallback、重新规划、部分成功、安全停止 |

一句话：

```text
Exception Handling 是把异常变得可见、可控；Recovery 是让系统从异常中尽量恢复。
```

#####  Agent 中常见异常类型有哪些？

Agent 的异常可以按执行层级分类。

1. LLM 调用异常

```text
1. 请求超时；
2. 429 限流；
3. 500 / 502 / 504 服务错误；
4. API Key 错误；
5. 模型名错误；
6. 返回内容为空；
7. 返回结构不符合预期；
8. 并发过高导致请求失败。
```

​	你之前遇到的：

```text
同步请求能跑，但异步并发 qwen 请求失败，最后定位到 httpx.AsyncClient 的 trust_env / 代理 / 连接池问题。
```

​	就是典型 LLM 调用异常。

2. 模型输出异常

```text
1. 要求 JSON，模型输出自然语言；
2. JSON 字段缺失；
3. JSON 语法错误；
4. Router 输出未知 route；
5. tool_name 不在工具白名单；
6. arguments 类型错误；
7. Planner 生成不可执行步骤；
8. 输出格式不符合用户要求。
```

​	例如：

```text
期望 route 是 code_expert / data_analyst / knowledge_expert；
模型却输出了 data_helper。
```

​	这就是 `unknown_route`。

3. Tool Call 异常

```text
1. 工具不存在；
2. 参数缺失；
3. 参数类型错误；
4. 文件路径不存在；
5. 文件格式不支持；
6. 权限不足；
7. 工具执行超时；
8. 工具内部报错；
9. 工具返回空结果；
10. 工具返回内容过大。
```

​	例如：

```text
analyze_excel 缺少 sheet_name；
read_file 路径不存在；
run_tests 超时。
```

4. RAG / Memory 异常

```text
1. 检索为空；
2. 检索结果无关；
3. 引用来源不存在；
4. 向量库连接失败；
5. FTS 查询失败；
6. 记忆过期；
7. 记忆冲突；
8. 记忆污染；
9. 检索结果过长，无法注入上下文。
```

​	这类异常最重要的原则是：

```text
检索不到依据时，不要编造。
```

5. Planning / Goal 异常

```text
1. 计划为空；
2. 计划步骤不可执行；
3. 步骤顺序错误；
4. 遗漏关键子目标；
5. 没有停止条件；
6. 达到最大步骤仍未完成；
7. 目标偏离；
8. Replanning 无限循环。
```

6. Multi-Agent / Parallelization 异常

```text
1. 某个 Worker 失败；
2. 某个 Agent 无响应；
3. 某个 Agent 输出格式错误；
4. 多个 Agent 结论冲突；
5. Aggregator 无法汇总；
6. 并发过高导致部分请求失败；
7. 一个 Agent 失败影响整体任务。
```

​	这类任务要特别支持：

```text
Partial Success，部分成功。
```

7. MCP 异常

```text
1. MCP Server 启动失败；
2. stdio 输出被普通日志污染；
3. initialize 失败；
4. capability 不支持；
5. tools/list 失败；
6. tools/call 参数错误；
7. resources/read 失败；
8. Server 连接中断；
9. 权限被拒绝；
10. 高风险工具未确认。
```

​	MCP 的一个重要坑是：

```text
stdio 模式下，stdout 只能输出 MCP JSON-RPC 消息，普通日志要写 stderr。
```

##### Detect → Classify → Log → Recover → Report → Learn 的流程是什么？

见上章节**异常处理的核心流程**

##### Retry / Fallback / Replanning / Partial Success / Safe Stop 的区别是什么？

这几个都是 Recovery 策略，但适用场景不同。

见上章节 **Recovery 的常见策略**

五者对比

| 策略            | 核心动作         | 适用场景             |
| --------------- | ---------------- | -------------------- |
| Retry           | 同样操作再试一次 | 临时错误             |
| Fallback        | 换备用方案       | 主能力不可用         |
| Replanning      | 换执行路线       | 当前计划无法继续     |
| Partial Success | 保留成功部分     | 批量、并行、多 Agent |
| Safe Stop       | 安全停止并报告   | 无法恢复或风险过高   |

##### 为什么异常结果要结构化？

异常结果结构化，是为了让上层 Orchestrator、Monitor、Reviewer 和评估系统都能理解异常。

差的异常返回：

```text
出错了：Sheet not found
```

好的异常返回：

```json
{
  "success": false,
  "error_type": "sheet_not_found",
  "message": "Sheet '86' does not exist in this workbook.",
  "recoverable": true,
  "recovery_suggestion": "Call inspect_excel to list available sheets.",
  "stage": "tool_call",
  "tool_name": "analyze_excel"
}
```

结构化异常的价值：

```text
1. Orchestrator 能判断下一步做什么；
2. Planner 能判断是否需要重新规划；
3. Monitor 能判断目标是否被阻塞；
4. Reviewer 能检查最终答案是否诚实；
5. 前端能展示清晰错误状态；
6. Learning 系统能转成 bad case；
7. 评估平台能统计错误类型和恢复成功率。
```

如果异常只是字符串，上层系统很难自动处理。

一句话：

```text
异常结构化，系统才知道怎么恢复、怎么展示、怎么评估。
```

##### 为什么不能无限重试？

无限重试会让 Recovery 变成新的故障源。

问题包括：

```text
1. 任务卡死；
2. 成本失控；
3. 接口被限流；
4. 工具重复执行；
5. 用户长时间无反馈；
6. 日志被重复错误污染；
7. 多 Agent 系统进入死循环；
8. 高风险工具可能重复造成副作用。
```

例如：

```text
LLM 请求一直 504；
如果无限重试，就会一直消耗时间和 token，还可能加重服务压力。
```

正确做法：

```text
1. 设置 max_retries；
2. 使用指数退避；
3. 区分可重试和不可重试异常；
4. 多次失败后 fallback；
5. fallback 失败后 safe stop；
6. 报告已尝试的恢复动作。
```

示例：

```python
max_retries = 2
max_replan_times = 2
max_tool_calls = 8
max_steps = 10
```

一句话：

```text
重试是恢复手段，不是无限循环的理由。
```

##### 为什么工具失败后不能继续编造？

工具失败后继续编造，是 Agent 系统中非常严重的问题。

例如：

```text
RAG 检索为空；
模型仍然假装找到了文档依据。

Excel 工具读取失败；
模型仍然编造 sheet 内容。

run_tests 失败；
模型仍然说测试全部通过。
```

这样会导致：

```text
1. 用户被误导；
2. 工具结果失去可信度；
3. 最终答案没有事实依据；
4. 后续操作可能基于错误信息；
5. 系统难以调试；
6. 评估和回归测试失真。
```

正确做法是：

```text
1. 明确说明工具失败；
2. 不使用不存在的工具结果；
3. 尝试恢复，例如重试、换工具、改参数；
4. 恢复失败时给出有限结论；
5. 清楚区分“已验证结果”和“推测”。
```

例如：

```text
我没有成功读取该 Excel 文件，因此不能确认 sheet 内容。
我已经尝试检查路径，但文件不存在。
请提供正确文件路径后，我可以继续分析。
```

一句话：

```text
工具失败后，Agent 应该诚实报告和恢复，而不是假装成功。
```

#### 进阶掌握

##### 如何设计统一错误类型？

统一错误类型的目标是：

```text
让所有 Agent、工具、MCP Server、RAG、Memory 都用同一套错误语言。
```

可以按模块设计错误类型。

1. LLM 错误

```text
llm_timeout
llm_rate_limit
llm_server_error
llm_auth_error
llm_empty_response
llm_invalid_response
```

2. 模型输出错误

```text
invalid_json
missing_required_field
unknown_route
invalid_tool_name
invalid_arguments
format_violation
```

3. 工具错误

```text
tool_not_found
tool_permission_denied
tool_timeout
tool_execution_error
missing_argument
invalid_argument_type
```

4. 文件 / Excel 错误

```text
file_not_found
file_permission_denied
unsupported_file_type
sheet_not_found
column_not_found
duplicate_key
file_locked
write_failed
```

5. RAG / Memory 错误

```text
retrieval_empty
retrieval_irrelevant
vector_store_error
memory_conflict
memory_stale
citation_missing
citation_mismatch
```

6. Planning / Goal 错误

```text
plan_empty
plan_not_executable
step_failed
goal_unclear
goal_drift
max_steps_exceeded
max_replan_exceeded
```

7. MCP 错误

```text
mcp_server_start_failed
mcp_initialize_failed
mcp_capability_unsupported
mcp_tool_call_failed
mcp_resource_read_failed
mcp_transport_error
mcp_permission_denied
```

统一错误类型的好处：

```text
1. 恢复策略可以按 error_type 分发；
2. 日志可以统计；
3. bad case 可以分类；
4. 前端可以展示统一状态；
5. 自动评估可以统计各类错误率；
6. 后续 Learning 可以知道优先优化哪里。
```

##### 如何设计 ToolResult / AgentError？

建议所有工具和 Agent 都返回统一结构。

1. AgentError

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentError:
    error_type: str
    message: str
    stage: str
    recoverable: bool
    recovery_suggestion: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
```

​	字段含义：

```text
error_type：
统一错误类型，例如 sheet_not_found。

message：
给用户或上层看的错误说明。

stage：
错误发生阶段，例如 router、planner、tool_call、rag、mcp。

recoverable：
是否可恢复。

recovery_suggestion：
建议恢复策略。

details：
结构化细节，例如 file_path、sheet_name、available_sheets。
```

2. ToolResult

```python
@dataclass
class ToolResult:
    success: bool
    data: Any | None = None
    summary: str | None = None
    error: AgentError | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

​	成功示例：

```python
ToolResult(
    success=True,
    data={"sheets": ["86", "85", "8011"]},
    summary="Workbook contains 3 sheets.",
)
```

​	失败示例：

```python
ToolResult(
    success=False,
    error=AgentError(
        error_type="sheet_not_found",
        message="Sheet '86' not found.",
        stage="tool_call",
        recoverable=True,
        recovery_suggestion="Call inspect_excel to list available sheets.",
        details={"requested_sheet": "86"}
    )
)
```

​	设计原则：

```text
1. 不要让工具直接返回裸字符串；
2. 成功和失败都要结构化；
3. 失败时必须有 error_type；
4. recoverable 决定是否进入恢复流程；
5. summary 用于给模型和用户快速理解；
6. details 用于程序恢复和日志。
```

##### 如何做参数修复？

参数修复适合模型调用工具时参数不完整、不合法或不匹配的情况。

典型错误：

```text
1. 缺少必填参数；
2. 参数类型错误；
3. 字段名错误；
4. sheet_name 不存在；
5. column 写成列名但工具要求列字母；
6. file_path 格式错误。
```

参数修复流程：

```text
参数校验失败
→ 返回结构化错误
→ 判断是否可自动修复
→ 必要时调用 inspect 工具获取候选值
→ 重新生成参数
→ 再次校验
→ 限制最大修复次数
```

例如 Excel 场景：

```text
analyze_sheet 缺少 sheet_name
→ inspect_excel 获取 sheet 列表
→ 模型根据用户意图选择 sheet
→ 重新调用 analyze_sheet
```

伪代码：

```python
def repair_tool_arguments(tool_name, arguments, error, context):
    if error.error_type == "missing_argument":
        return ask_llm_to_fill_missing_arguments(tool_name, arguments, error, context)

    if error.error_type == "sheet_not_found":
        workbook_info = inspect_excel(arguments["file_path"])
        return ask_llm_to_choose_sheet(arguments, workbook_info)

    if error.error_type == "invalid_argument_type":
        return coerce_argument_type(arguments, error.details)

    return None
```

注意：

```text
1. 参数修复要有最大次数；
2. 不确定时不要瞎猜；
3. 高风险写操作参数修复后仍需用户确认；
4. 修复前后都要记录日志；
5. 修复失败要 safe stop。
```

##### 如何做部分成功？

部分成功适用于多步骤、多文件、多 Agent、并行任务。

核心原则：

```text
不要因为一个子任务失败，就丢掉所有已经成功的结果。
```

例如并行任务：

```text
summary_worker：成功
questions_worker：成功
key_terms_worker：失败
```

最终可以输出：

```text
已完成：
1. 摘要生成；
2. 问题生成。

未完成：
1. 关键词提取失败，原因是 LLM timeout。

以下是已完成结果。
```

工程结构：

```json
{
  "overall_success": false,
  "partial_success": true,
  "completed_tasks": [
    {
      "name": "summary_worker",
      "success": true,
      "summary": "..."
    }
  ],
  "failed_tasks": [
    {
      "name": "key_terms_worker",
      "success": false,
      "error_type": "llm_timeout",
      "recoverable": true
    }
  ],
  "final_summary": "部分任务成功，关键词提取失败。"
}
```

部分成功策略适合：

```text
1. 批量文件处理；
2. 多 Worker 并行；
3. 多 Agent 协作；
4. 多工具链路；
5. RAG 多 query 检索；
6. 自动评估批量 runner。
```

设计原则：

```text
1. 成功部分要保留；
2. 失败部分要标明原因；
3. 最终答案要明确说明 partial；
4. 不要把部分成功伪装成完全成功；
5. 可恢复失败可以提供下一步建议。
```

##### 如何将异常事件接入 [[ORCH]]？

可以把异常处理过程变成可观察事件，见上**和[[ORCH]]事件结合**

##### 如何把异常转成 bad case？

异常不是处理完就结束，而是要沉淀为 bad case。

转换流程：

```text
异常日志
→ 判断是否代表系统缺陷
→ 提取 input / expected / actual
→ 分类 error_type
→ 分析 root_cause
→ 生成 fix_suggestion
→ 加入 bad case 库
→ 转成回归测试
```

示例：

```json
{
  "case_id": "case_tool_001",
  "trace_id": "trace_001",
  "module": "tool_executor",
  "error_type": "missing_argument",
  "input": "分析 data.xlsx 的 86 sheet",
  "expected": {
    "tool_name": "analyze_excel",
    "arguments": {
      "file_path": "data.xlsx",
      "sheet_name": "86"
    }
  },
  "actual": {
    "tool_name": "analyze_excel",
    "arguments": {
      "file_path": "data.xlsx"
    }
  },
  "root_cause": "模型生成 Tool Call 时遗漏 sheet_name",
  "fix_suggestion": "优化工具 schema，并在 analyze_excel 前增加 inspect_excel 参数补全流程",
  "status": "open"
}
```

哪些异常适合转 bad case：

```text
1. 高频出现；
2. 影响任务完成；
3. 可通过规则、Prompt、schema 或流程优化；
4. 代表某类系统缺陷；
5. 可以转成测试样例。
```

哪些不一定转：

```text
1. 用户临时输错路径；
2. 外部服务偶发抖动；
3. 用户取消操作；
4. 不可复现的临时问题。
```

##### 如何评估 Recovery Success Rate？

Recovery Success Rate 衡量异常发生后，系统成功恢复的比例。

```text
Recovery Success Rate = 成功恢复的异常次数 / 可恢复异常总次数
```

例如：

```text
本周发生 100 个 recoverable 异常；
其中 72 个通过重试、参数修复、fallback 等方式恢复；
Recovery Success Rate = 72%。
```

可以细分：

```text
Retry Success Rate；
Parameter Repair Success Rate；
Fallback Success Rate；
Replanning Success Rate；
Partial Success Rate；
Safe Stop Correctness。
```

评估字段：

```json
{
  "trace_id": "trace_001",
  "error_type": "sheet_not_found",
  "recoverable": true,
  "recovery_strategy": "call_inspect_excel",
  "recovery_success": true,
  "final_task_success": true,
  "recovery_attempts": 1,
  "elapsed_seconds": 0.8
}
```

还要关注：

```text
1. 恢复后任务是否真的完成；
2. 恢复是否引入新错误；
3. 恢复是否过度调用工具；
4. 恢复是否违反用户约束；
5. 恢复是否导致成本过高。
```

相关指标：

```text
Mean Recovery Attempts：
平均恢复尝试次数。

Recovery Latency：
恢复耗时。

Safe Stop Rate：
安全停止比例。

False Recovery Rate：
看似恢复成功但最终答案错误的比例。

Unrecoverable Error Rate：
不可恢复异常比例。
```

最终目标不是让所有错误都强行恢复，而是：

```text
能恢复的尽量恢复，不能恢复的安全停止并清楚说明原因。
```

##### 如何在 Multi-Agent / MCP / RAG 中做异常恢复？

不同系统模块的恢复方式不同。

1. Multi-Agent 中的异常恢复

​	常见异常：

```text
1. 某个 Agent 失败；
2. 某个 Agent 输出格式错误；
3. Agent 之间结论冲突；
4. Aggregator 汇总失败；
5. Reviewer 发现严重问题。
```

​	恢复策略：

```text
1. 单个 Agent 失败时允许 partial success；
2. 失败 Agent 单独重试；
3. 输出格式错误时要求该 Agent 重新格式化；
4. 多 Agent 冲突时交给 Reviewer / Judge；
5. Aggregator 只汇总成功结果，并说明失败部分。
```

​	示例：

```text
code_expert 成功；
knowledge_expert 检索失败；
data_analyst 不相关。

最终输出：
基于 code_expert 的结果给出代码分析；
说明知识库检索失败，因此没有引用文档依据。
```

2. MCP 中的异常恢复

​	常见异常：

```text
1. MCP Server 启动失败；
2. initialize 失败；
3. capability 不支持；
4. tools/list 失败；
5. tools/call 参数错误；
6. permission denied；
7. stdio 被日志污染；
8. transport 连接中断。
```

​	恢复策略：

```text
1. Server 启动失败 → 检查命令、路径、环境变量；
2. capability 不支持 → 不调用该能力，换 Server 或 fallback；
3. tools/call 参数错误 → 参数修复；
4. permission denied → 请求用户授权；
5. stdio 输出污染 → 日志改 stderr；
6. Server 不可用 → fallback 到内部工具或 safe stop。
```

​	MCP 特别要注意：

```text
Host 不应该因为某个 MCP Server 挂掉而整体崩溃；
每个 Server 的失败要隔离处理。
```

3. RAG 中的异常恢复

​	常见异常：

```text
1. 检索为空；
2. 召回无关内容；
3. 引用缺失；
4. 引用和答案不匹配；
5. 向量库不可用；
6. 上下文过长。
```

​	恢复策略：

```text
1. query rewrite；
2. 扩大 top_k；
3. 切换 FTS 关键词检索；
4. 使用混合检索；
5. rerank；
6. 压缩检索结果；
7. 找不到依据时明确说明；
8. 禁止基于空结果编造答案。
```

​	示例：

```text
用户问 build 模式；
向量检索为空；
系统改用关键词 build / plan / mode 检索；
如果仍为空，就说明知识库中没有找到相关内容，而不是编造。
```

4. 三者共同原则

​	无论 Multi-Agent、MCP 还是 RAG，异常恢复都要遵守：

```text
1. 失败要隔离；
2. 结果要结构化；
3. 能恢复就恢复；
4. 不能恢复就部分成功或安全停止；
5. 不要编造未验证结果；
6. 异常要记录为日志；
7. 高频异常要转 bad case；
8. 恢复能力要进入评估体系。
```

### 面试表达

可以这样说：

```text
Exception Handling and Recovery 是 Agent 系统中的可靠性机制。Agent 在执行过程中会遇到模型超时、输出格式错误、工具参数错误、文件不存在、检索为空、多 Agent 部分失败等问题。工程上不能只用一个 try except 把错误吞掉，而是要对异常进行检测、分类、结构化记录，并根据异常类型选择恢复策略，比如重试、参数修复、fallback、重新规划、部分成功或安全停止。
```

结合工程实践可以这样说：

```text
在实现上，我会设计统一的 AgentError 和 ToolResult，让所有工具和 Agent 都返回结构化状态。比如工具失败时返回 error_type、message、recoverable、recovery_suggestion，而不是直接抛异常给上层。Orchestrator 根据 error_type 决定是否重试、修正参数、换工具、触发 Replanning，还是安全停止。同时把异常事件记录到 trace 日志，并转成 bad case，进入自动评估和回归测试平台。
```

结合你的 LocalAgent 可以这样说：

```text
在 LocalAgent 中，我会把异常处理接入 [[ORCH]] 事件系统。比如 data_analyst 调用 analyze_excel 时发现 sheet 不存在，系统不会直接失败，而是发出 exception_detected 事件，然后触发 recovery_started，自动调用 inspect_excel 获取可用 sheet。如果恢复成功，就继续执行；如果源 sheet 确实不存在，就 safe_stop，并向用户说明失败原因和已尝试的恢复动作。这样的设计可以让 Agent 的执行过程可观察、可恢复、可评估。
```

### 一句话总结

```text
Exception Handling and Recovery 的本质是：让 Agent 在出错时不崩溃、不编造，而是能识别异常、选择恢复策略，并清楚说明结果。
```

再压缩一点：

```text
异常处理负责别崩，恢复机制负责尽量继续。
```

## Chapter 13 Human-in-the-Loop（HITL） 人类在环

### 是什么

**Human-in-the-Loop，人类在环**，指的是：

在 Agent 执行任务的关键节点，让人类参与确认、审批、纠错、选择、补充信息或最终裁决，从而提高系统安全性、可靠性和可控性。

普通全自动 Agent 是：

```text
用户输入
→ Agent 理解任务
→ Agent 调用工具
→ Agent 修改文件 / 发送请求 / 执行命令
→ 输出结果
```

Human-in-the-Loop 的 Agent 是：

```text
用户输入
→ Agent 理解任务
→ Agent 判断是否需要人类介入
→ 低风险任务自动执行
→ 高风险 / 不确定任务请求用户确认
→ 用户批准 / 拒绝 / 修改
→ Agent 继续执行或安全停止
```

它的核心思想是：

```text
Agent 可以自动执行很多任务，但关键决策和高风险操作必须有人类控制权。
```

### 为什么需要 Human-in-the-Loop

Agent 系统不是普通文本生成器，它可能会：

```text
1. 修改文件；
2. 覆盖 Excel；
3. 删除数据；
4. 执行 shell；
5. 查询数据库；
6. 写入记忆；
7. 调用 MCP 工具；
8. 发送邮件；
9. 提交代码；
10. 修改项目配置。
```

这些行为一旦出错，会造成真实影响。

例如：

```text
用户：把 86 的 N 列覆盖到 85 和 8011 的 O 列。

如果 Agent 直接执行：
- 可能选错文件；
- 可能选错 sheet；
- 可能覆盖错列；
- 可能没有备份；
- 可能无法恢复。
```

所以这种任务不能完全自动执行，至少要让用户确认：

```text
即将修改文件：xxx.xlsx
源 sheet：86
目标 sheet：85、8011
匹配键：A、B 列
源列：N
目标列：O
操作：覆盖已有内容
是否确认执行？
```

Human-in-the-Loop 的价值是：

```text
让 Agent 自动化能力不失控。
```

### Human-in-the-Loop 介入哪些环节

人类可以在 Agent 执行链路的多个阶段介入。

#### 任务理解阶段

当用户目标不清晰时，需要人类补充。

例如：

```text
用户：帮我改一下那个文件。
```

Agent 不知道：

```text
哪个文件；
改什么；
是否允许覆盖；
是否需要备份。
```

这时应该询问用户，而不是猜。

#### 目标确认阶段

当任务影响较大时，可以先让用户确认目标。

例如：

```text
我理解你的目标是：
根据 A、B 两列作为复合键，把 86 表 N 列覆盖到 85 和 8011 表 O 列。
这个理解是否正确？
```

这能防止一开始目标就错。

#### 工具调用前

这是最常见的人类在环节点。

尤其是高风险工具：

```text
write_file
delete_file
update_excel
run_shell_command
update_database
send_email
submit_pr
write_memory
```

执行前应该确认。

#### 工具失败后

当 Agent 无法自动恢复时，需要用户参与。

例如：

```text
工具失败：找不到 86 这个 sheet。
当前文件中可用 sheet 是：85、8011、Sheet1。
请确认源 sheet 应该是哪一个？
```

这属于 Exception Recovery 中的人类介入。

#### 多个方案选择时

Agent 有多个可行方案，但无法确定哪个更符合用户意图。

例如：

```text
方案 A：原地修改 Excel，并自动备份。
方案 B：生成一个新文件，不修改原文件。
方案 C：只输出处理脚本，不直接执行。
```

让用户选择更安全。

#### 低置信度决策时

如果 Router、Planner、Tool Call 的置信度低，不应该强行执行。

例如：

```json
{
  "route": "data_analyst",
  "confidence": 0.42
}
```

可以问：

```text
我不确定这是 Excel 数据分析任务还是普通文件总结任务。你是希望我分析表格内容，还是只总结文件说明？
```

#### 最终输出前

对于报告、邮件、代码提交、文件修改等任务，最终输出前可以让用户审阅。

例如：

```text
我已经生成修改方案，但还没有写入文件。
请确认后我再执行写入。
```

### Human-in-the-Loop 的常见形式

#### Confirmation：确认

最常见。

用于：

```text
写文件；
覆盖数据；
删除内容；
发送消息；
执行命令；
提交代码；
更新数据库。
```

示例：

```text
我将执行以下操作：
1. 修改文件：report.xlsx
2. 源 sheet：86
3. 目标 sheet：85、8011
4. 操作：覆盖 O 列已有内容

是否确认继续？
```

#### Approval：审批

比确认更正式，适合高风险操作。

例如：

```text
Agent 生成了数据库更新 SQL；
需要用户审批后才能执行。
```

审批适合：

```text
生产环境数据库；
公司内部系统；
批量文件修改；
发邮件；
发 PR；
执行 shell。
```

#### Correction：纠错

用户纠正 Agent 的理解或结果。

例如：

```text
不是 85 的 N 列，是 86 的 N 列。
不是覆盖 P 列，是覆盖 O 列。
这个任务应该走 data_analyst，不是 general_chat。
```

纠错信息应该进入：

```text
Memory；
Learning and Adaptation；
bad case；
回归测试。
```

#### Selection：选择

当有多个候选项时，让用户选择。

例如：

```text
我找到了三个可能的文件：
1. data_2026.xlsx
2. data_backup.xlsx
3. result.xlsx

你要处理哪一个？
```

#### Feedback：反馈

用户对 Agent 输出进行评价。

例如：

```text
这个答案太泛。
这个结论不对。
这个代码能跑。
这个方案就按这个继续。
```

Feedback 是 Learning and Adaptation 的重要输入。

#### Manual Override：人工接管

当 Agent 无法继续或风险过高时，用户可以接管。

例如：

```text
Agent 多次工具失败；
用户手动指定正确路径；
Agent 继续执行。
```

### 什么时候必须 Human-in-the-Loop

不是所有任务都需要用户确认，否则系统会很烦。

应该按风险等级区分。

#### 可以自动执行的低风险任务

```text
解释概念；
总结文本；
只读检索；
读取文件；
检查 Python 语法；
列出 Excel sheet；
生成代码草稿；
生成建议；
普通问答。
```

这些一般可以自动执行。

#### 建议确认的中风险任务

```text
写入本地文件；
修改 Excel；
写入记忆；
运行测试；
执行本地脚本；
批量处理文件；
调用外部 API。
```

这些通常需要确认，尤其第一次执行时。

#### 必须确认的高风险任务

```text
删除文件；
覆盖原始数据；
更新数据库；
发送邮件；
提交 PR；
执行 shell 命令；
修改系统配置；
调用生产环境接口；
修改公司内部数据。
```

这些必须 Human-in-the-Loop。

#### 必须人工裁决的情况

除了高风险操作，还有一些逻辑上必须人工裁决：

```text
1. 用户目标不清晰；
2. 多个方案都合理；
3. 工具结果冲突；
4. 多 Agent 结论冲突；
5. 记忆和当前输入冲突；
6. 置信度过低；
7. 执行结果不可逆；
8. 涉及安全、隐私、合规。
```

### Human-in-the-Loop 和自动化的平衡

Human-in-the-Loop 不是让用户每一步都点确认。

如果确认太多，用户体验会变差。

错误设计：

```text
读取文件要确认；
总结文本要确认；
生成草稿要确认；
每个模型调用都确认。
```

这样会让 Agent 变成“半自动但很烦”。

正确设计是：

```text
低风险自动；
中风险可配置确认；
高风险强制确认；
不确定时请求用户裁决。
```

可以用风险等级控制：

```json
{
  "tool_name": "inspect_excel",
  "risk_level": "read",
  "require_confirmation": false
}
{
  "tool_name": "copy_column_by_composite_key",
  "risk_level": "write",
  "require_confirmation": true
}
{
  "tool_name": "delete_file",
  "risk_level": "dangerous",
  "require_confirmation": true
}
```

核心原则：

```text
让用户控制风险，而不是让用户参与所有琐事。
```

### Human-in-the-Loop 和 Exception Handling 的关系

上一节讲 Exception Handling and Recovery。

Human-in-the-Loop 是一种重要的 Recovery 策略。

例如：

```text
工具失败：sheet_not_found
自动恢复：inspect_excel
如果仍无法确定：请求用户选择正确 sheet
```

流程：

```text
异常发生
→ 自动恢复
→ 自动恢复失败
→ 人类介入
→ 用户补充信息
→ Agent 继续执行
```

示例：

```text
我没有找到 86 这个 sheet。
当前可用 sheet 是：85、8011、Sheet1。
你希望把哪个 sheet 作为源 sheet？
```

所以 Human-in-the-Loop 可以理解为：

```text
自动恢复无法安全决定时，把控制权交还给用户。
```

### Human-in-the-Loop 和 Goal Monitoring 的关系

Goal Monitoring 负责发现：

```text
目标不清晰；
执行偏离；
约束冲突；
成功标准无法判断；
停止条件触发。
```

这些情况可能需要人类介入。

例如：

```text
用户目标：帮我优化这个项目。
```

这个目标太泛。

Goal Monitor 可以触发 Human-in-the-Loop：

```text
你想优先优化哪一方面？
1. 性能
2. 代码结构
3. 错误处理
4. Agent 架构
5. 测试覆盖
```

也就是说：

```text
Goal Monitoring 发现目标问题；
Human-in-the-Loop 让用户澄清目标。
```

### Human-in-the-Loop 和 Learning and Adaptation 的关系

用户确认、拒绝、纠错、反馈都是学习信号。

例如：

```text
用户拒绝执行某个工具：
说明 Agent 的风险判断可能太激进。

用户纠正 route：
说明 Router 需要优化。

用户修改生成内容：
说明 Prompt 或输出格式需要适应。

用户多次选择“生成新文件，不原地修改”：
说明用户偏好保守写入策略。
```

这些反馈可以进入：

```text
Memory；
bad case；
规则优化；
Prompt 优化；
评估集。
```

所以 Human-in-the-Loop 不只是安全机制，也是学习数据来源。

### Human-in-the-Loop 和 MCP 的关系

MCP 很适合接入外部工具，但也增加风险。

MCP Server 暴露的工具可能包括：

```text
文件系统；
数据库；
GitHub；
邮件；
shell；
公司内部 API；
Excel 写入工具。
```

所以 Host 必须做 Human-in-the-Loop 控制。

尤其是 MCP Tools 应该带上元数据：

```json
{
  "name": "copy_column_by_composite_key",
  "description": "根据复合键覆盖 Excel 列",
  "risk_level": "write",
  "require_confirmation": true,
  "destructive": false,
  "idempotent": false
}
```

调用前 Host 应展示：

```text
工具名称；
作用；
参数；
影响范围；
是否会写入；
是否可回滚；
是否需要备份。
```

MCP 里非常重要的一点是：

```text
Server 暴露能力；
Host 负责用户授权和安全控制。
```

不能让 MCP Server 自己决定所有高风险操作是否执行。

### Human-in-the-Loop 的工程设计

#### 审批对象 ApprovalRequest

可以设计一个结构化审批对象：

```json
{
  "approval_id": "approval_001",
  "trace_id": "trace_001",
  "action_type": "tool_call",
  "risk_level": "write",
  "agent_name": "data_analyst",
  "tool_name": "copy_column_by_composite_key",
  "description": "根据 A、B 复合键将 86 表 N 列覆盖到 85 和 8011 表 O 列",
  "arguments_summary": {
    "file_path": "report.xlsx",
    "source_sheet": "86",
    "target_sheets": ["85", "8011"],
    "key_columns": ["A", "B"],
    "source_column": "N",
    "target_column": "O"
  },
  "side_effects": [
    "会修改 Excel 文件",
    "会覆盖目标 O 列已有内容"
  ],
  "rollback_plan": "执行前创建备份文件 report.backup.xlsx",
  "options": ["approve", "reject", "modify"]
}
```

这样 UI 可以展示审批卡片。

#### 用户响应 HumanResponse

用户可以：

```text
批准；
拒绝；
修改参数；
要求生成新文件；
要求先预览；
取消任务。
```

结构：

```json
{
  "approval_id": "approval_001",
  "decision": "modify",
  "modified_arguments": {
    "target_column": "P"
  },
  "comment": "不要覆盖 O 列，改成写入 P 列"
}
```

Agent 根据用户响应继续执行。

#### 工具风险配置

每个工具都应该有风险元数据：

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    risk_level: str
    require_confirmation: bool
    read_only: bool
    destructive: bool
    idempotent: bool
```

示例：

```python
ToolDefinition(
    name="inspect_excel",
    description="读取 Excel 结构信息",
    risk_level="read",
    require_confirmation=False,
    read_only=True,
    destructive=False,
    idempotent=True,
)
ToolDefinition(
    name="copy_column_by_composite_key",
    description="根据复合键覆盖 Excel 列",
    risk_level="write",
    require_confirmation=True,
    read_only=False,
    destructive=False,
    idempotent=False,
)
```

### 在 LocalAgent 中如何应用

你的 LocalAgent 很适合把 Human-in-the-Loop 接入 `[[ORCH]]` 事件流。

#### 审批事件

当 Agent 准备执行高风险工具时，发出事件：

```json
{
  "type": "approval_required",
  "trace_id": "trace_001",
  "approval_id": "approval_001",
  "tool_name": "copy_column_by_composite_key",
  "risk_level": "write",
  "description": "将 86 表 N 列覆盖到 85 和 8011 表 O 列",
  "arguments_summary": {
    "source_sheet": "86",
    "target_sheets": ["85", "8011"],
    "source_column": "N",
    "target_column": "O"
  },
  "side_effects": [
    "会修改原始 Excel 文件",
    "会覆盖目标列已有内容"
  ],
  "options": ["approve", "reject", "modify"]
}
```

前端收到后展示确认按钮。

#### 用户批准

```json
{
  "type": "approval_granted",
  "trace_id": "trace_001",
  "approval_id": "approval_001",
  "decision": "approve"
}
```

Agent 继续执行工具。

#### 用户拒绝

```json
{
  "type": "approval_rejected",
  "trace_id": "trace_001",
  "approval_id": "approval_001",
  "decision": "reject",
  "reason": "不想覆盖原文件"
}
```

Agent 安全停止或改为生成脚本。

#### 用户修改参数

```json
{
  "type": "approval_modified",
  "trace_id": "trace_001",
  "approval_id": "approval_001",
  "modified_arguments": {
    "target_column": "P"
  },
  "comment": "改为写入 P 列"
}
```

Agent 使用新参数重新校验并继续。

#### 和 Excel 工具结合

对于你的 Excel 原地修改工具，建议流程是：

```text
用户提出修改需求
→ Agent 解析目标
→ inspect_excel 获取 sheet / 列信息
→ 生成操作计划
→ 发出 approval_required
→ 用户确认
→ 自动备份文件
→ 执行写入
→ 返回更新摘要
→ 记录 tool log
```

这样非常工程化。

### 常见坑

#### 什么都问用户

如果每一步都问，Agent 就失去自动化价值。

应该只在：

```text
高风险；
低置信度；
目标不清晰；
不可逆操作；
外部影响；
自动恢复失败。
```

时才问。

#### 高风险操作不确认

这是更严重的问题。

比如：

```text
删除文件；
覆盖 Excel；
执行 shell；
更新数据库；
发送邮件；
提交 PR。
```

这些必须确认。

#### 确认信息不完整

差的确认：

```text
是否执行？
```

好的确认：

```text
即将修改 report.xlsx：
- 源 sheet：86
- 目标 sheet：85、8011
- 匹配键：A、B 列
- 源列：N
- 目标列：O
- 操作：覆盖已有内容
- 备份：将创建 report.backup.xlsx

是否确认？
```

#### 用户修改参数后不重新校验

用户修改参数后，Agent 必须重新校验。

例如用户把目标列改成 P，系统要检查：

```text
P 列是否存在；
是否允许写入；
是否影响原逻辑；
是否仍需要备份。
```

#### 审批状态没有进入日志

所有用户审批都应该记录：

```text
谁审批；
审批了什么；
批准还是拒绝；
是否修改参数；
执行结果如何。
```

这对审计和回放非常重要。

### 需要掌握

#### 必须掌握

##### Human-in-the-Loop 的定义是什么？

见上文 **“Human-in-the-Loop 是什么”** 部分。

核心一句话：

```text
Human-in-the-Loop 的本质是：让 Agent 在关键决策和高风险操作上保留人类控制权。
```

再压缩一点：

```text
低风险自动化，高风险人确认。
```

##### 为什么 Agent 需要人类在环？

Agent 需要人类在环，是因为 Agent 不只是生成文本，它可能会执行真实操作。

例如：

```text
1. 修改文件；
2. 覆盖 Excel；
3. 删除数据；
4. 执行 shell 命令；
5. 更新数据库；
6. 写入记忆；
7. 调用 MCP 工具；
8. 发送邮件；
9. 提交代码；
10. 修改项目配置。
```

这些操作一旦出错，会产生真实副作用。

例如 Excel 覆盖任务：

```text
把 86 表 N 列覆盖到 85 和 8011 表 O 列。
```

如果完全自动执行，可能出现：

```text
1. 选错文件；
2. 选错 sheet；
3. 选错源列或目标列；
4. 覆盖已有重要数据；
5. 没有备份；
6. 执行后无法恢复。
```

所以人类在环的价值是：

```text
1. 防止高风险操作失控；
2. 让用户确认 Agent 是否理解正确；
3. 在低置信度场景中让用户裁决；
4. 在工具失败后让用户补充信息；
5. 让用户保留最终决策权；
6. 为后续 Learning and Adaptation 提供反馈信号。
```

一句话：

```text
Agent 可以提高自动化程度，但不能替代用户对关键风险的控制权。
```

##### 人类可以在哪些阶段介入？

人类可以在 Agent 执行链路的多个阶段介入，见上文 **HITL 介入哪些环节**。

##### Confirmation / Approval / Correction / Selection / Feedback / Manual Override 的区别是什么？

这几个都是人类在环的形式，但作用不同。

| 类型            | 含义                 | 典型场景                       |
| --------------- | -------------------- | ------------------------------ |
| Confirmation    | 确认是否继续         | 写文件、覆盖 Excel 前          |
| Approval        | 审批高风险操作       | 执行 SQL、发送邮件、提交 PR    |
| Correction      | 用户纠正 Agent       | route 错、参数错、理解错       |
| Selection       | 用户从多个选项中选择 | 多个文件、多个方案、多个 sheet |
| Feedback        | 用户评价结果         | 答案不对、太泛、代码能跑       |
| Manual Override | 人工接管或覆盖决策   | Agent 多次失败、风险过高       |

见上文 **HITL 常见形式**

##### 哪些操作必须人类确认？

可以按风险等级区分，见上文 **什么时候必须 HITL**。

一句话：

```text
凡是不可逆、有外部影响、低置信度或涉及用户真实数据的操作，都应该让人确认。
```

##### 如何平衡自动化和人工确认？

Human-in-the-Loop 不是每一步都问用户，见上文 **HITL 和自动化的平衡**。

一句话：

```text
让用户控制风险，而不是让用户参与所有琐事。
```

##### Human-in-the-Loop 和 Exception Recovery / Goal Monitoring / Learning / MCP 的关系是什么？

见上文

##### 为什么高风险工具不能全自动执行？

高风险工具不能全自动执行，因为它们可能产生不可逆或外部影响。

例如：

```text
1. 删除文件后无法恢复；
2. 覆盖 Excel 会破坏原始数据；
3. update_database 会影响真实业务数据；
4. send_email 会影响外部人员；
5. run_shell_command 可能破坏系统；
6. submit_pr 会影响代码仓库；
7. write_memory 可能造成长期错误记忆；
8. 调用生产环境接口可能影响线上系统。
```

模型可能出现：

```text
1. 理解错用户目标；
2. 选错工具；
3. 传错参数；
4. 忽略约束；
5. 被提示注入影响；
6. 基于错误记忆做决策；
7. 对风险判断不足。
```

所以高风险工具必须确认。

执行前至少展示：

```text
1. 工具名称；
2. 操作对象；
3. 参数摘要；
4. 影响范围；
5. 是否会覆盖 / 删除 / 写入；
6. 是否有备份或回滚方案；
7. 用户可选 approve / reject / modify。
```

一句话：

```text
高风险工具不能全自动执行，是因为 Agent 可以辅助决策，但不能替用户承担真实后果。
```

#### 进阶掌握

##### 如何设计 ApprovalRequest？

ApprovalRequest 是 Agent 请求用户确认或审批时的结构化对象。

它应该回答：

```text
Agent 想做什么？
为什么要做？
风险是什么？
会影响什么？
用户可以怎么决定？
```

推荐结构：

```json
{
  "approval_id": "approval_001",
  "trace_id": "trace_001",
  "action_type": "tool_call",
  "risk_level": "write",
  "agent_name": "data_analyst",
  "tool_name": "copy_column_by_composite_key",
  "description": "根据 A、B 复合键将 86 表 N 列覆盖到 85 和 8011 表 O 列",
  "arguments_summary": {
    "file_path": "report.xlsx",
    "source_sheet": "86",
    "target_sheets": ["85", "8011"],
    "key_columns": ["A", "B"],
    "source_column": "N",
    "target_column": "O"
  },
  "side_effects": [
    "会修改 Excel 文件",
    "会覆盖目标 O 列已有内容"
  ],
  "rollback_plan": "执行前创建备份文件 report.backup.xlsx",
  "options": ["approve", "reject", "modify"],
  "expires_at": null
}
```

关键字段：

```text
approval_id：
审批唯一 ID。

trace_id：
关联本次 Agent 执行链路。

action_type：
审批的是工具调用、文件写入、记忆写入还是外部请求。

risk_level：
read / write / dangerous / external。

tool_name：
即将调用的工具。

arguments_summary：
参数摘要，避免展示过长或敏感内容。

side_effects：
可能造成的副作用。

rollback_plan：
备份或回滚方案。

options：
用户可选动作。
```

好的 ApprovalRequest 应该让用户一眼看懂：

```text
即将发生什么；
会影响什么；
风险是什么；
是否可回滚；
我能选择什么。
```

##### 如何设计 HumanResponse？

HumanResponse 是用户对 ApprovalRequest 的回应。

用户不只是 approve / reject，还可能修改参数。

推荐结构：

```json
{
  "approval_id": "approval_001",
  "trace_id": "trace_001",
  "decision": "modify",
  "modified_arguments": {
    "target_column": "P"
  },
  "comment": "不要覆盖 O 列，改成写入 P 列",
  "timestamp": "2026-07-07T10:00:00"
}
```

decision 可以包括：

```text
approve：
批准执行。

reject：
拒绝执行。

modify：
修改参数后执行。

preview：
先预览，不执行写入。

cancel：
取消整个任务。
```

处理原则：

```text
1. approve 后继续执行；
2. reject 后 safe_stop 或提供替代方案；
3. modify 后必须重新校验参数；
4. preview 后只生成预览结果，不做真实写入；
5. cancel 后终止任务并记录原因。
```

特别注意：

```text
用户修改参数后，不能直接执行，必须重新做 schema 校验和风险判断。
```

##### 如何给工具配置 risk_level 和 require_confirmation？

每个工具都应该带风险元数据。

可以设计 ToolDefinition：

```python
from dataclasses import dataclass


@dataclass
class ToolDefinition:
    name: str
    description: str
    risk_level: str
    require_confirmation: bool
    read_only: bool
    destructive: bool
    idempotent: bool
```

字段含义：

```text
risk_level：
read / write / dangerous / external。

require_confirmation：
是否执行前必须用户确认。

read_only：
是否只读。

destructive：
是否可能破坏或删除数据。

idempotent：
重复执行是否安全。
```

示例一：只读工具

```python
ToolDefinition(
    name="inspect_excel",
    description="读取 Excel 的 sheet 和列信息",
    risk_level="read",
    require_confirmation=False,
    read_only=True,
    destructive=False,
    idempotent=True,
)
```

示例二：写操作工具

```python
ToolDefinition(
    name="copy_column_by_composite_key",
    description="根据复合键覆盖 Excel 列",
    risk_level="write",
    require_confirmation=True,
    read_only=False,
    destructive=False,
    idempotent=False,
)
```

示例三：危险工具

```python
ToolDefinition(
    name="delete_file",
    description="删除指定文件",
    risk_level="dangerous",
    require_confirmation=True,
    read_only=False,
    destructive=True,
    idempotent=False,
)
```

工具风险配置原则：

```text
1. 只读工具通常不确认；
2. 写操作默认确认；
3. destructive=True 必须确认；
4. external 类操作必须确认；
5. idempotent=False 的工具要更谨慎；
6. 用户修改参数后重新计算风险；
7. MCP 工具也要映射到同一套风险模型。
```

##### 如何把审批事件接入 [[ORCH]]？

可以把 Human-in-the-Loop 作为 `[[ORCH]]` 事件流的一部分。

建议事件类型：

```text
approval_required
approval_granted
approval_rejected
approval_modified
approval_cancelled
```

审批、批准、拒绝、修改见上文 **在Local Agent 中如何应用**，下面只介绍取消任务

approval_cancelled

```json
{
  "type": "approval_cancelled",
  "trace_id": "trace_001",
  "approval_id": "approval_001",
  "reason": "用户取消任务"
}
```

接入价值：

```text
1. 前端可以展示审批卡片；
2. 用户可以明确批准、拒绝或修改；
3. trace 可以回放整个审批过程；
4. 高风险操作有审计记录；
5. Learning 可以从用户选择中学习偏好；
6. 自动评估可以统计 Human Intervention Rate。
```

##### 如何处理用户拒绝或修改参数？

1. 用户拒绝

​	用户拒绝后，不能继续执行原操作。

​	可选策略：

```text
1. Safe Stop：安全停止；
2. 提供替代方案；
3. 改为只生成脚本；
4. 改为生成新文件；
5. 改为只预览；
6. 记录用户偏好。
```

​	例如：

```text
用户拒绝原地覆盖 Excel。

Agent 可以回应：
好的，我不会修改原文件。可以改为：
1. 生成一个新 Excel 文件；
2. 只输出处理脚本；
3. 只生成操作预览。
```

2. 用户修改参数

​	用户修改参数后，必须重新进入校验流程。

​	流程：

```text
接收 modified_arguments
→ 合并原参数
→ 重新做 schema 校验
→ 重新做风险判断
→ 必要时再次确认
→ 执行工具
```

​	例如用户把目标列从 O 改为 P：

```text
target_column: O → P
```

​	系统要重新检查：

```text
P 列是否存在；
是否允许写入；
是否仍是覆盖操作；
是否需要备份；
是否改变风险等级。
```

3. 用户要求 preview

​	如果用户选择预览：

```text
只计算将要更新的行数；
展示前几条匹配结果；
不写入文件。
```

​	这对 Excel 类工具非常实用。

4. 用户取消

​	用户取消后：

```text
停止当前任务；
记录取消原因；
不要继续调用相关工具；
输出已停止说明。
```

##### 如何记录审批日志？

审批日志是审计和回放的关键。

建议记录：

```text
approval_id；
trace_id；
user_request；
agent_name；
tool_name；
risk_level；
arguments_summary；
side_effects；
decision；
modified_arguments；
user_comment；
timestamp；
execution_result；
operator；
```

示例：

```json
{
  "approval_id": "approval_001",
  "trace_id": "trace_001",
  "user_request": "把 86 的 N 列覆盖到 85 和 8011 的 O 列",
  "agent_name": "data_analyst",
  "tool_name": "copy_column_by_composite_key",
  "risk_level": "write",
  "arguments_summary": {
    "source_sheet": "86",
    "target_sheets": ["85", "8011"],
    "source_column": "N",
    "target_column": "O"
  },
  "side_effects": [
    "modify_excel_file",
    "overwrite_existing_cells"
  ],
  "decision": "approve",
  "modified_arguments": null,
  "user_comment": null,
  "execution_result": "success",
  "timestamp": "2026-07-07T10:00:00"
}
```

日志用途：

```text
1. 审计高风险操作；
2. 回放用户决策；
3. 分析用户偏好；
4. 生成 bad case；
5. 统计人工介入频率；
6. 证明 Agent 没有越权执行。
```

注意：

```text
日志里不要保存 API Key、数据库密码、真实敏感数据；
参数可以保存摘要；
必要时对路径和内容脱敏。
```

##### 如何评估 Human Intervention Rate？

Human Intervention Rate 表示 Agent 执行过程中需要人类介入的比例。

```text
Human Intervention Rate = 需要人类介入的任务数 / 总任务数
```

也可以按工具调用计算：

```text
Tool Intervention Rate = 需要确认的工具调用数 / 总工具调用数
```

还可以细分：

```text
Confirmation Rate：
需要确认的比例。

Approval Reject Rate：
用户拒绝审批的比例。

Modification Rate：
用户修改参数的比例。

Clarification Rate：
需要用户澄清目标的比例。

Manual Override Rate：
用户人工接管的比例。
```

这些指标的意义：

```text
1. 介入率过高：Agent 自动化不足，用户体验差；
2. 介入率过低：可能风险控制不足；
3. 拒绝率高：Agent 风险判断或工具选择可能有问题；
4. 修改率高：Tool Call 参数生成可能不准确；
5. 澄清率高：Goal Setting 或 Memory 可能不足。
```

示例评估记录：

```json
{
  "total_tasks": 100,
  "human_intervention_tasks": 18,
  "human_intervention_rate": 0.18,
  "approval_required": 12,
  "approval_rejected": 3,
  "approval_modified": 4,
  "manual_override": 1
}
```

理想状态不是 0%。

更合理的目标是：

```text
低风险任务尽量少介入；
高风险任务稳定触发确认；
用户拒绝和修改率逐步下降；
Agent 参数生成越来越准确。
```

##### 如何将用户反馈转为 bad case 和长期偏好？

Human-in-the-Loop 产生的用户反馈非常有价值。

1. 转为 bad case

​	当用户纠正 Agent 的错误时，应记录为 bad case。

​	例如用户说：

```text
这个应该走 data_analyst，不是 general_chat。
```

​	可以转成：

```json
{
  "case_id": "router_001",
  "module": "router",
  "input": "根据 86 的 AB 列匹配 85 和 8011",
  "expected": "data_analyst",
  "actual": "general_chat",
  "error_type": "routing_error",
  "root_cause": "Router 没有识别 Excel 列匹配任务",
  "fix_suggestion": "增加 Excel / sheet / 列匹配关键词规则",
  "status": "open"
}
```

2. 转为长期偏好

​	当用户表达长期规则时，应写入 Memory。

​	例如用户说：

```text
以后修改 Excel 时，优先生成新文件，不要原地覆盖。
```

​	可以变成长期偏好：

```json
{
  "memory_type": "user_preference",
  "content": "用户在 Excel 修改任务中偏好生成新文件，而不是原地覆盖。",
  "tags": ["excel", "write_operation", "safety_preference"],
  "status": "active"
}
```

3. 区分 bad case 和长期偏好

| 用户反馈           | 应该如何处理            |
| ------------------ | ----------------------- |
| “这个 route 错了”  | bad case                |
| “这个参数不对”     | tool call bad case      |
| “以后都这样输出”   | 长期偏好                |
| “这次不要执行”     | 当前任务约束            |
| “以后不要原地覆盖” | 长期偏好                |
| “这个答案太泛”     | answer quality bad case |

​	判断标准：

```text
如果反馈指出系统错误，转 bad case；
如果反馈表达未来偏好，写入长期记忆；
如果只影响当前任务，只放在当前上下文。
```

4. 进入 Learning and Adaptation

​	反馈最终应该进入优化闭环：

```text
用户反馈
→ 分类
→ bad case / memory / current constraint
→ 更新 Prompt / 规则 / 工具 schema
→ 加入回归测试
→ 验证指标是否提升
```

​	这样 Human-in-the-Loop 不只是安全机制，也成为 Agent 持续改进的数据来源。

### 面试表达

可以这样说：

```text
Human-in-the-Loop 是 Agent 系统中的人类控制机制。它的核心不是让用户参与每一步，而是在高风险、低置信度、目标不清晰、工具失败或涉及外部副作用时，把关键决策交还给人类确认或裁决。这样可以避免 Agent 在不确定或高风险场景下自动执行错误操作。
```

结合工程实践可以这样说：

```text
工程上我会给每个工具配置 risk_level、read_only、destructive、idempotent 和 require_confirmation 等元数据。低风险只读工具可以自动执行；写文件、覆盖 Excel、更新数据库、执行 shell、发送邮件等高风险工具必须生成 ApprovalRequest，由用户批准、拒绝或修改参数后再执行。所有审批过程都记录到 trace 和 [[ORCH]] 事件里，方便回放、审计和后续评估。
```

结合你的 LocalAgent 可以这样说：

```text
在 LocalAgent 中，Human-in-the-Loop 可以和 Tool Executor、MCP Server 以及 [[ORCH]] 事件系统结合。比如 data_analyst 准备执行 Excel 覆盖操作时，系统会先生成 approval_required 事件，展示源 sheet、目标 sheet、匹配键、源列、目标列、是否覆盖、是否备份等信息。用户批准后才执行；如果用户拒绝，则 safe_stop；如果用户修改参数，则重新校验后继续。这样可以让 LocalAgent 既具备自动化能力，又保留关键操作的人类控制权。
```

### 一句话总结

```text
Human-in-the-Loop 的本质是：让 Agent 在关键决策和高风险操作上保留人类控制权。
```

再压缩一点：

```text
低风险自动化，高风险人确认。
```

## Chapter 14 Knowledge Retrieval（RAG）

