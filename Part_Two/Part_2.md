# Part Two

## Chapter 9 Learning and Adaptation

### 是什么

Agent 在运行过程中，根据用户反馈、历史结果、工具执行情况、bad case、评估指标等信息，不断调整自己的行为策略，让后续任务表现更好。

简单说：

```
Memory Management 让 Agent “记得过去”；
Learning and Adaptation 让 Agent “从过去中变得更好”。
```

普通 Agent 是：

```
用户输入
→ Agent 执行
→ 输出结果
→ 结束
```

带 Learning and Adaptation 的 Agent 是：

```
用户输入
→ Agent 执行
→ 输出结果
→ 收集反馈
→ 分析哪里做得好 / 不好
→ 更新规则、Prompt、工具策略、记忆或评估集
→ 后续任务表现变好
```

它的核心思想是：

```
Agent 不应该每次都从零开始，而应该能从历史反馈和错误中调整自己的行为。
```

### 为什么需要 Learning and Adaptation

Agent 系统上线后，不可能一开始就完美，会有很多问题，如果 Agent 不具备学习和适应的能力，它就会反复犯同样的错误

Learning and Adaptation 的价值就是把一次失败变成后续优化的依据

### Learning and Adaptation 和 Memory Management 的区别

#### Memory Management

Memory Management 解决的是：

```
哪些信息要保存？
如何检索？
如何压缩？
如何注入上下文？
```

它偏向“记忆系统”。

例如：

```
记住用户家里使用 DeepSeek，公司使用 qwen。
记住用户已经实现 AsyncLLMClient。
记住用户希望代码示例更利于学习。
```

#### Learning and Adaptation

Learning and Adaptation 解决的是：

```
Agent 如何根据历史反馈改变后续行为？
```

它偏向“行为改进”。

例如：

```
因为用户已经实现 AsyncLLMClient，所以后续不要再建议重新改造客户端。
因为 Routing 多次错判 Excel 任务，所以优化路由规则。
因为 Tool Call 多次缺少 sheet_name，所以增强工具参数校验和提示。
```

一句话区别：

```
Memory 是保存信息；
Learning 是利用信息改变行为。
```

### 核心流程

一个完整的学习与适应流程可以抽象为：

```
Observe → Evaluate → Diagnose → Adapt → Validate
```

对应中文是：

```
观察结果
→ 评估表现
→ 诊断问题
→ 调整策略
→ 验证是否变好
```

具体来说：

```
1. Observe：记录 Agent 执行过程和用户反馈；
2. Evaluate：判断结果是否成功；
3. Diagnose：分析失败原因；
4. Adapt：调整 Prompt、规则、工具参数、记忆或评估集；
5. Validate：用回归测试验证改动是否有效。
```

### Agent 可以从哪些东西中学习

1. 用户显式反对

   例如用户说：

   ```
   这个回答不对。
   这个应该走 code_expert。
   这里不要再问我，直接按默认路径处理。
   以后代码示例都要用 LLMClient。
   ```

   这些是最直接的反馈。

   系统可以更新：

   ```
   用户偏好
   路由规则
   Prompt 约束
   默认配置
   示例代码模板
   ```

2. 用户隐式反馈

   用户没有明确说错，但行为能反映问题。

   例如：

   ```
   用户反复追问同一个点；
   用户多次要求“再详细一点”；
   用户总是要求“给出下载版”；
   用户每次都把代码复制回来报错。
   ```

   这些说明 Agent 可能：

   ```
   回答不够具体；
   代码可运行性不足；
   没有考虑用户项目环境；
   没有提供足够调试信息。
   ```

3. 工具执行结果

   例如：

   ```
   工具多次返回 FileNotFoundError；
   json.loads 多次解析失败；
   pytest 多次失败在同一类断言；
   httpx 异步请求因代理失败。
   ```

   系统可以学习：

   ```
   调用工具前先检查路径；
   要求模型只输出合法 JSON；
   代码生成后先执行语法检查；
   异步 HTTP 默认 trust_env=False。
   ```

4. Bad Case

   Bad case 是最重要的学习材料之一。

   例如：

   ```
   {
     "module": "router",
     "input": "帮我根据 AB 列匹配两个 sheet",
     "expected": "data_analyst",
     "actual": "general_chat",
     "root_cause": "Router 没有识别 Excel 匹配任务"
   }
   ```

   后续可以针对它：

   ```
   优化规则路由；
   修改 Router Prompt；
   加入测试集；
   做回归测试；
   统计修复率。
   ```

5. 评估指标

   如果有自动评估平台，可以从指标中学习。

   例如：

   ```
   Router Accuracy 从 82% 下降到 75%；
   Tool Call Success Rate 只有 60%；
   RAG Recall@K 不稳定；
   引用命中率低；
   最终回答可用性评分不高。
   ```

   这些指标可以指导优化方向。

### Learning and Adaptation 的几种层级

#### Prompt Adaptation Prompt 适应

根据 bad case 修改 Prompt。

例如原 Router Prompt 没强调 Excel：

```
请判断任务类型。
```

优化后：

```
如果用户提到 xlsx、Excel、sheet、列匹配、单元格覆盖、CSV 等，优先考虑 data_analyst。
```

这是最常见、成本最低的适应方式。

#### Rule Adaptation 规则适应

把高置信度经验固化成规则。

例如：

```python
if any(keyword in user_input.lower() for keyword in ["xlsx", "excel", "sheet", "csv"]):
    return "data_analyst"
```

适合确定性强的场景。

规则适应比 Prompt 更稳定，但灵活性较弱。

#### Memory Adaptation 记忆适应

把长期有效的信息写入记忆，并让后续回答使用。

例如：

```
用户希望后续代码示例都朝着更利于学习理解的方向改造。
```

后续你发示例代码时，Agent 就应该自动：

```
不机械翻译；
改造成适合当前项目的版本；
讲解结构；
回顾知识点。
```

这就是记忆驱动的适应。

#### Tool Strategy Adaptation 工具策略适应

根据历史工具结果调整工具调用方式。

比如：

```
Excel 工具经常 sheet_name 缺失。
```

后续工具调用前先执行：

```
inspect_excel → 获取 sheet 列表 → 再 analyze_sheet
```

#### Evaluation Set Adaptation 评估集适应

把 bad case 加入测试集，防止回归。

例如 Router 错误样例：

```
{
  "input": "根据 86 的 AB 列匹配 85 和 8011，并覆盖 O 列",
  "expected_route": "data_analyst"
}
```

后续每次改 Router，都跑一遍回归测试。

这是工程上非常重要的一类“学习”。

#### 模型微调

感兴趣学，Agent 开发应该不用

### 和第一章模式的关系

Learning and Adaptation 可以增强第一章所有模式。

| 模式            | 如何适应                                 |
| --------------- | ---------------------------------------- |
| Routing         | 根据错分样例优化路由规则和 Router Prompt |
| Planning        | 根据失败任务优化计划模板和最大步数       |
| Tool Use        | 根据工具失败优化参数生成和校验策略       |
| Reflection      | 根据漏检问题优化 Critic Prompt           |
| Parallelization | 根据耗时和失败率调整并发数               |
| Prompt Chaining | 根据中间步骤失败优化链路顺序             |
| Multi-Agent     | 根据各 Agent 表现调整职责边界和工具权限  |

例如：

```
Parallelization 中公司内网 qwen 并发过高容易 504
→ 学习到 qwen 默认并发要保守
→ 配置 PARALLEL_MAX_CONCURRENCY 或 LLM_MAX_CONNECTIONS
```

这就是适应。

### 工程实现

#### 记录执行轨迹

没有日志就无法学习

至少要记录：

```
用户输入；
Router 判断；
Planner 计划；
Tool Call；
工具结果；
Agent 输出；
Reflection 审查；
最终回答；
用户反馈；
失败原因；
耗时；
token 成本。
```

这就是后续分析的基础。

#### 构建 Bad Case Taxonomy

可以分类为：

```
1. routing_error：路由错误；
2. planning_error：计划错误；
3. tool_selection_error：工具选错；
4. tool_argument_error：工具参数错误；
5. tool_execution_error：工具执行失败；
6. retrieval_error：检索不到；
7. citation_error：引用错误；
8. reflection_miss：反思漏检；
9. answer_hallucination：回答幻觉；
10. format_error：输出格式错误；
11. user_preference_miss：没有遵守用户偏好。
```

每个 bad case 应该记录：

```
{
  "case_id": "case_001",
  "module": "router",
  "input": "...",
  "expected": "...",
  "actual": "...",
  "error_type": "routing_error",
  "root_cause": "...",
  "fix_action": "...",
  "status": "open"
}
```

#### 将 Bad Case 转成回归测试

一次 bad case 如果只修一次，很容易以后又犯。

所以要转成测试样例。

#### 更新策略

Adaptation 可以更新不同层：

```
1. 更新规则；
2. 更新 Prompt；
3. 更新工具 schema；
4. 更新默认参数；
5. 更新记忆；
6. 更新 Agent 职责；
7. 更新测试集；
8. 更新文档。
```

但不要每次错误都立刻改系统。

应该先判断：

```
这是偶发问题，还是高频问题？
是模型随机波动，还是设计缺陷？
是用户输入不清楚，还是系统理解失败？
修复会不会影响其他样例？
```

#### 验证改动

每次适应后都要验证。

例如你优化了 Router Prompt，不能只看一个样例对了。

要跑：

```
原来的正确样例；
新加入的 bad case；
边界样例；
无关任务样例。
```

防止出现：

```
修好了 Excel 路由，但把普通文件总结也误判成 data_analyst。
```

所以 Learning and Adaptation 必须和 Evaluation 结合。

### 常见坑

#### 把 Memory 当 Learning

记住一件事，不等于学会改进行为。

例如系统记住：

```
用户喜欢中文回答。
```

但后续还是输出英文。

这说明只有 Memory，没有 Adaptation。

真正的 Adaptation 是：

```
后续回答自动使用中文；
代码注释也优先中文；
学习笔记按中文结构输出。
```

#### 从单个样例过拟合

用户纠正一次，不代表所有情况都要改规则。

例如一次用户说：

```
这个任务不要用工具。
```

不能直接学成：

```
以后类似任务都不用工具。
```

要区分：

```
局部偏好；
当前任务约束；
长期规则；
偶发异常。
```

#### 错误记忆导致错误适应

如果把模型错误结论写入记忆，后续会持续污染。

所以学习前要确认：

```
这个反馈来源可靠吗？
是用户明确确认的吗？
工具结果是否支持？
是否已经验证？
```

#### 只改 Prompt ，不做评估

很多人遇到 bad case 就改 Prompt，但不跑回归。

结果是：

```
修一个坏三个。
```

正确流程是：

```
记录 bad case
→ 分析原因
→ 修改策略
→ 加入测试集
→ 跑回归
→ 确认指标提升
```

#### 适应速度太快

Agent 如果每次都自动修改自己的规则，可能变得不可控。

工程上建议：

```
低风险偏好可以自动记忆；
规则和工具策略变更需要评估；
高风险策略变更需要人工确认。
```

### 需要掌握

#### 必须掌握

```
1. Learning and Adaptation 的定义是什么？

见上文 “第二章第九节：Learning and Adaptation 是什么” 部分。
核心一句话：
Learning and Adaptation 的本质是：把用户反馈、工具结果、bad case 和评估指标转化为 Agent 后续行为策略的改进。
它不是简单保存历史，而是让 Agent 根据历史表现调整后续行为。


2. 它和 Memory Management 的区别是什么？

见上文 “Learning and Adaptation 和 Memory Management 的区别” 部分。
核心区别：
Memory Management 解决“记住什么、怎么取出来用”；
Learning and Adaptation 解决“如何根据过去改变后续行为”。

简单说：
Memory 是保存信息；
Learning 是利用信息改进策略。

例如：
Memory：
记住用户已经实现 AsyncLLMClient。
Learning：
以后异步 demo 默认基于这个 AsyncLLMClient，不再建议用户重新改造客户端。


3. Agent 可以从用户反馈、工具结果、bad case、评估指标中学习吗？

可以，而且这四类是工程 Agent 最主要的学习来源。
3.1 用户反馈
用户反馈包括显式反馈和隐式反馈。
显式反馈：
这个回答不对。
这个应该走 data_analyst。
以后代码示例都要更适合我学习。
不要再重复定义部分。

这些反馈可以更新：
用户偏好；
回答风格；
路由规则；
Prompt 约束；
默认代码模板；
记忆内容。

隐式反馈包括：
用户反复追问同一个点；
用户多次要求“再详细一点”；
用户总是把代码复制回来报错；
用户频繁纠正某类输出。

这说明 Agent 可能在某些方面不够具体、不够可运行，或者没有理解用户项目环境。

3.2 工具结果
工具结果是非常可靠的学习信号。
例如：
json.loads 解析失败；
pytest 测试失败；
read_file 文件不存在；
httpx 请求超时；
Excel 工具提示 sheet_name 不存在。

这些结果可以反向优化 Agent 行为：
JSON 输出前加强格式约束；
代码生成后先做语法检查；
读取文件前先检查路径；
调用 Excel 工具前先 inspect_excel；
异步 HTTP 默认 trust_env=False。

工具结果比模型自我判断更可靠，因为它来自真实执行环境。

3.3 Bad Case
Bad case 是 Agent 失败样例，是最重要的学习材料。
示例：
{
  "module": "router",
  "input": "帮我根据 86 的 AB 列匹配 85 和 8011",
  "expected": "data_analyst",
  "actual": "general_chat",
  "error_type": "routing_error",
  "root_cause": "Router 没有识别 Excel sheet 匹配任务"
}

这种 bad case 可以用于：
优化 Router Prompt；
增加规则路由；
更新工具 schema；
加入回归测试集；
统计错误类型；
验证修复效果。

3.4 评估指标
指标可以告诉我们系统整体哪里弱。
例如：
Router Accuracy 下降；
Tool Call Success Rate 偏低；
RAG Recall@K 不稳定；
Reflection 修复率低；
最终回答可用性评分低。

根据指标可以决定优化方向：
Router Accuracy 低 → 优化路由规则和 Router Prompt；
Tool Call 成功率低 → 优化工具 schema 和参数校验；
RAG Recall@K 低 → 优化 query rewrite、chunk 和 rerank；
Reflection 修复率低 → 优化 Critic Prompt 和检查清单。

总结：
用户反馈告诉 Agent 用户想要什么；
工具结果告诉 Agent 执行是否真实成功；
bad case 告诉 Agent 失败在哪里；
评估指标告诉 Agent 系统整体弱点在哪里。


4. 为什么学习不等于微调模型？

学习不等于微调模型。
在 Agent 工程中，大多数“学习”和“适应”并不是训练模型参数，而是在系统层面优化行为。
常见适应方式包括：
1. 修改 Prompt；
2. 增加规则；
3. 更新记忆；
4. 调整工具调用策略；
5. 优化工具 schema；
6. 更新默认参数；
7. 修改 Agent 职责边界；
8. 增加 bad case 测试集；
9. 调整检索策略；
10. 加强 Reflection 检查清单。

例如：
问题：
Router 多次把 Excel 任务误判成 general_chat。
不需要微调模型，先做：
1. 增加 Excel 关键词规则；
2. 修改 Router Prompt；
3. 加入 Router 测试样例；
4. 跑回归测试。

再例如：
问题：
Tool Call 经常缺少 sheet_name。

不需要微调模型，先做：
1. 修改工具 schema；
2. 调用 analyze_excel 前先 inspect_excel；
3. 参数校验失败时返回结构化错误；
4. 让模型基于错误重新生成参数。

微调模型适合更大规模、更稳定的数据场景，但对当前个人 Agent 项目来说，优先级通常低于
Prompt 优化；
规则优化；
记忆更新；
工具策略优化；
自动评估与回归测试。

所以这一节的重点不是“训练一个新模型”，而是：
让 Agent 系统通过工程机制持续改进。


5. Observe → Evaluate → Diagnose → Adapt → Validate 的基本流程是什么？

Learning and Adaptation 的基本闭环是：
Observe → Evaluate → Diagnose → Adapt → Validate
也就是：
观察 → 评估 → 诊断 → 调整 → 验证

5.1 Observe：观察
记录 Agent 执行过程。
需要记录：
用户输入；
Router 判断；
Planner 计划；
Tool Call 参数；
工具执行结果；
Agent 输出；
Reflection 审查；
最终回答；
用户反馈；
耗时和错误信息。
没有观察记录，就无法知道系统哪里做错了。

5.2 Evaluate：评估
判断这次执行是否成功。
可以评估：
Router 是否选对；
工具是否选对；
参数是否正确；
RAG 是否召回相关内容；
Reflection 是否发现问题；
最终回答是否满足用户需求。

例如：
用户要求分析 Excel；
Router 输出 general_chat；
评估结果：routing_error。

5.3 Diagnose：诊断
分析失败原因。
不是只记录“错了”，还要判断“为什么错”。
例如：
错误类型：routing_error
根因：Router Prompt 没有强调 sheet、xlsx、列匹配等数据分析关键词。
或者：
错误类型：tool_argument_error
根因：工具 schema 没有明确 sheet_name 必填。

5.4 Adapt：调整
根据诊断结果调整系统。
可能的调整包括：
修改 Prompt；
增加规则；
更新工具 schema；
修改默认参数；
更新记忆；
加入 bad case；
调整 Agent 分工；
优化检索策略。

例如：
如果用户输入包含 xlsx、Excel、sheet、列匹配、覆盖列等关键词，优先路由到 data_analyst。

5.5 Validate：验证
调整后必须验证。
不能只看一个 bad case 修好了，还要确认没有破坏其他样例。
验证方式：
跑原有测试集；
跑新增 bad case；
检查边界样例；
统计指标是否提升；
确认没有引入新错误。

完整闭环可以写成：
记录执行轨迹
→ 判断是否失败
→ 标注错误类型
→ 分析根因
→ 修改策略
→ 加入回归测试
→ 验证指标提升

这就是 Agent 真正的持续改进能力。


6. 为什么 bad case 是 Agent 优化的核心材料？

Bad case 是 Agent 优化的核心材料，因为它比抽象感觉更具体。
如果只说：
Router 不太准。
这没有办法直接优化。
但如果有 bad case：
{
  "input": "根据 86 的 AB 列匹配 85 和 8011，并覆盖 O 列",
  "expected_route": "data_analyst",
  "actual_route": "general_chat",
  "error_type": "routing_error"
}

就可以明确知道：
哪个输入错了；
期望是什么；
实际是什么；
哪个模块错了；
错误类型是什么；
应该怎么修。

Bad case 的价值包括：
1. 帮助定位具体失败模块；
2. 帮助分析 root cause；
3. 可以转成测试样例；
4. 可以验证修复是否有效；
5. 可以防止同类问题回归；
6. 可以统计高频错误类型；
7. 可以指导 Prompt、规则、工具 schema 优化。

对于 Agent 工程来说，bad case 相当于传统软件工程中的 bug report。
没有 bad case，就只能凭感觉调 Prompt。
有 bad case，才能形成：
发现问题 → 修复问题 → 加入测试 → 防止回归


7. 为什么适应后必须做回归验证？

适应后必须做回归验证，因为修改一个策略可能修好一个问题，同时破坏其他场景。
例如你为了修复 Excel 路由，增加规则：
if "表" in user_input:
    return "data_analyst"

可能导致：
用户：解释一下表驱动测试
也被错误路由到 data_analyst。

这就是：
修好一个 case，破坏其他 case。
所以每次 Adapt 后都要 Validate。

回归验证需要覆盖：
1. 原来的正确样例；
2. 新加入的 bad case；
3. 边界样例；
4. 无关任务样例；
5. 高频真实用户样例。

例如 Router 优化后要检查：
Excel 任务是否正确进入 data_analyst；
代码任务是否仍然进入 code_expert；
知识库任务是否仍然进入 knowledge_expert；
普通问答是否不会误进工具链；
含糊任务是否进入 fallback。

回归验证的目的不是证明“这次修改有变化”，而是证明：
这次修改整体上让系统变好，而不是局部变好、整体变差。


8. 为什么不能从单个样例过拟合？

不能从单个样例过拟合，是因为一个样例可能只是局部情况，不一定代表长期规律。
例如用户说：
这个任务不要调用工具。
这可能只针对当前任务，而不是所有类似任务。

如果系统直接学成：
以后这类任务都不调用工具。

就可能造成错误适应。
过拟合单个样例会带来：
1. 规则变得过窄；
2. 破坏其他正常场景；
3. 系统行为越来越偏；
4. Prompt 被补丁堆满；
5. 新旧规则互相冲突；
6. Agent 难以维护。

正确做法是先判断反馈类型：
这是当前任务约束？
这是用户长期偏好？
这是高频 bad case？
这是明确工具错误？
这是偶发模型波动？

不同情况处理不同：
当前任务约束 → 只在当前任务生效；
长期偏好 → 写入 Memory；
高频 bad case → 修改规则或 Prompt；
工具真实错误 → 更新工具策略；
偶发波动 → 先记录，不急着改系统。

一句话：
不要因为一个样例就修改全局行为；要看它是否代表稳定规律。
```

#### 进阶掌握

```
1. 如何设计 feedback logging？

Feedback logging 是记录反馈和执行结果的机制。
它的目标是让系统知道：
用户觉得哪里不好；
哪个模块出了问题；
这次执行是否成功；
后续应该怎么优化。

建议记录字段：
{
  "feedback_id": "fb_001",
  "trace_id": "trace_001",
  "timestamp": "2026-07-06T10:00:00",
  "user_input": "帮我分析这个 xlsx 文件",
  "agent_output": "这是一个普通问答任务...",
  "feedback_type": "explicit_negative",
  "feedback_text": "这个应该走 data_analyst，不是普通问答",
  "module": "router",
  "expected_behavior": "route=data_analyst",
  "actual_behavior": "route=general_chat",
  "severity": "medium",
  "status": "open"
}

反馈来源可以分为：
explicit_positive：用户明确认可；
explicit_negative：用户明确否定；
correction：用户给出修正；
implicit_retry：用户反复追问；
tool_failure：工具执行失败；
eval_failure：自动评估失败。

记录 feedback 时要注意：
1. 关联 trace_id，方便回放完整过程；
2. 标注影响模块；
3. 记录 expected 和 actual；
4. 记录用户原话；
5. 标注严重程度；
6. 支持后续转成 bad case；
7. 避免保存敏感内容。

没有 feedback logging，Agent 的学习就没有数据来源。


2. 如何设计 bad case taxonomy？

Bad case taxonomy 是失败样例分类体系。
它的作用是让错误可以被统计、分析和修复。

推荐分类如下：
1. routing_error
路由错误，例如 Excel 任务被分到 general_chat。
2. planning_error
计划错误，例如计划太空、漏步骤、顺序错误。
3. tool_selection_error
工具选择错误，例如应该 inspect_excel，却调用 calculator。
4. tool_argument_error
工具参数错误，例如缺少 sheet_name，参数类型错误。
5. tool_execution_error
工具执行失败，例如文件不存在、权限不足、超时。
6. retrieval_error
检索错误，例如 RAG 没召回相关文档。
7. citation_error
引用错误，例如答案引用了无关片段或不存在的来源。
8. reflection_miss
反思漏检，例如 Critic 没发现边界条件缺失。
9. hallucination
回答编造了工具结果或文档中没有的信息。
10. format_error
输出格式错误，例如 JSON 不合法、Markdown 不符合要求。
11. user_preference_miss
没有遵守用户偏好，例如用户要求不要重复定义，但仍然重复。
12. aggregation_error
汇总错误，例如多个 Agent 结果冲突但没有标注。
13. timeout_or_cost_error
执行时间过长、并发过高、成本不可控。

Bad case 记录结构：
{
  "case_id": "case_001",
  "trace_id": "trace_001",
  "module": "router",
  "error_type": "routing_error",
  "input": "帮我根据 AB 列匹配两个 sheet",
  "expected": {
    "route": "data_analyst"
  },
  "actual": {
    "route": "general_chat"
  },
  "root_cause": "Router 规则未覆盖 Excel 列匹配任务",
  "fix_suggestion": "增加 Excel / sheet / 列匹配关键词规则",
  "status": "open",
  "created_at": "2026-07-06"
}

Taxonomy 的价值是：
把“感觉不好”变成“可分类、可统计、可修复的问题”。


3. 如何把 bad case 转成测试集？

Bad case 不能只记录，还要进入测试集。
转换流程：
bad case
→ 提取输入和期望输出
→ 定义断言规则
→ 加入 JSONL / SQLite 测试集
→ 批量 runner 执行
→ 统计是否修复

例如 Router bad case：
{
  "case_id": "router_001",
  "input": "根据 86 的 AB 列匹配 85 和 8011，并覆盖 O 列",
  "expected_route": "data_analyst",
  "tags": ["excel", "routing", "regression"]
}

Tool Call bad case：
{
  "case_id": "tool_001",
  "input": "分析 data.xlsx 的 86 sheet",
  "expected_tool": "analyze_excel",
  "expected_arguments": {
    "file_path": "data.xlsx",
    "sheet_name": "86"
  },
  "tags": ["tool_call", "excel"]
}

RAG bad case：
{
  "case_id": "rag_001",
  "input": "解释 build 模式和 plan 模式区别",
  "expected_keywords": ["build mode", "plan mode"],
  "expected_recall_docs": ["codex_usage_notes.md"],
  "tags": ["rag", "recall"]
}

每次修改系统后跑测试：
1. 跑新增 bad case；
2. 跑历史回归集；
3. 看指标是否提升；
4. 如果通过，标记 case 为 fixed；
5. 如果失败，继续诊断。

这样 bad case 就从“失败记录”变成了“防回归资产”。


4. 如何根据指标优化 Router / Tool Use / RAG / Reflection？

指标要能对应优化动作。
4.1 Router 指标与优化
常见指标：
Router Accuracy；
Fallback Rate；
Misroute Rate；
Per-route Precision / Recall。

如果 Router Accuracy 低，可以优化：
1. 增加规则路由；
2. 优化 Router Prompt；
3. 减少模糊 route；
4. 增加 route 描述和示例；
5. 加入 bad case 回归集；
6. 输出结构化 route + confidence。

4.2 Tool Use 指标与优化
常见指标：
Tool Selection Accuracy；
Argument Accuracy；
Tool Call Success Rate；
Invalid Tool Call Rate；
Unnecessary Tool Call Rate。

如果 Tool Call 成功率低，可以优化：
1. 工具 schema 写清楚参数；
2. 加强参数校验；
3. 对缺失参数返回结构化错误；
4. 低风险工具允许一次参数修复；
5. 先 inspect 再 analyze；
6. 限制模型只能调用白名单工具。

4.3 RAG 指标与优化
常见指标：
Recall@K；
MRR；
引用命中率；
unsupported claim rate；
answer faithfulness。

如果 Recall@K 低，可以优化：
1. query rewrite；
2. 调整 chunk size；
3. 增加关键词检索；
4. 混合检索：FTS + vector；
5. rerank；
6. 增加 metadata 过滤；
7. 增加同义词和项目术语映射。

如果引用质量差，可以优化：
1. 要求答案只基于检索片段；
2. Reflection 检查 unsupported claims；
3. 增加 citation verifier；
4. 降低无依据内容权重。

4.4 Reflection 指标与优化
常见指标：
Critic Issue Detection Rate；
Revision Success Rate；
False Positive Rate；
New Error Introduction Rate；
Reflection Repair Rate。

如果 Critic 漏检，可以优化：
1. 增加检查清单；
2. 按任务类型设计不同 Critic；
3. 引入工具结果；
4. 多 Reviewer 并行检查；
5. 把漏检样例加入测试集。

如果 Reviser 引入新错误，可以优化：
1. Reviser 输入必须包含原始任务；
2. 限制只修改 Critic 指出的问题；
3. 修正后再次工具校验；
4. 限制最大反思轮数。

总结：
指标不是只用来看分数，而是用来决定下一步优化哪里。


5. 如何区分短期反馈和长期规则？

不是所有反馈都应该变成长期规则。
区分标准如下。

5.1 短期反馈
短期反馈只对当前任务或当前会话有效。
例如：
这次不要调用工具。
这个回答再短一点。
这个示例先不要加异常处理。
这次只关注 86 这个 sheet。
处理方式：
只影响当前任务；
写入当前会话上下文；
不进入全局规则；
不影响未来所有任务。

5.2 长期规则
长期规则对未来类似任务都有效。
例如：
以后我发送示例代码时，你可以朝更利于学习和理解的方向改造。
后续答案中，已经总结过的定义和区别不要重复。
家里环境默认 DeepSeek，公司默认 qwen。
异步 demo 默认使用用户已有 AsyncLLMClient。
处理方式：
写入长期记忆；
更新回答策略；
后续自动应用；
必要时加入规则或模板。

5.3 判断标准
可以问几个问题：
1. 用户是否说了“以后、今后、默认、长期”？
2. 这个反馈是否适用于未来类似任务？
3. 是否已经多次出现？
4. 是否和用户偏好或项目规范有关？
5. 是否可能和其他场景冲突？
6. 是否需要用户确认？

原则：
当前任务约束，不升级为长期规则；
明确长期偏好，写入记忆并改变后续行为；
不确定时先作为 session-level 规则，而不是 global rule。


6. 如何控制自动适应的风险？

自动适应有风险，因为 Agent 如果随意修改自己的规则，可能越来越偏。
常见风险：
1. 从单个样例过拟合；
2. 错误反馈被当成长期规则；
3. 模型错误结论进入记忆；
4. 自动修改工具策略导致新错误；
5. Prompt 越改越复杂；
6. 安全策略被弱化；
7. 高风险操作被自动放行。

控制方式：
1. 分级适应；
2. 高风险改动需要人工确认；
3. 所有策略改动记录日志；
4. 适应后跑回归测试；
5. 保留回滚机制；
6. 区分 session-level 和 global-level；
7. 不自动放宽安全限制；
8. 对敏感信息做过滤。

可以按风险分级：
低风险：
回答风格、输出格式、学习偏好，可以自动适应。
中风险：
Prompt、路由规则、工具参数策略，建议先记录并评估。
高风险：
工具权限、写操作策略、数据库操作、系统命令，必须人工确认。

一个安全原则：
Agent 可以自动学习如何更好地回答，但不能自动学习如何绕过安全限制。


7. 如何评估 Adaptation 是否真的提升系统表现？

评估 Adaptation 是否有效，不能只看单个样例。
需要对比改动前后指标。

7.1 A/B 对比
比较：
改动前版本
vs
改动后版本

观察：
Router Accuracy 是否提升；
Tool Call 成功率是否提升；
RAG Recall@K 是否提升；
Reflection 修复率是否提升；
最终回答可用性是否提升。

7.2 Bad Case 修复率
计算：
Bad Case 修复率 = 已修复 bad case 数 / 总 bad case 数
例如：
20 个 Router bad case；
修复后通过 16 个；
修复率 = 80%。

7.3 回归失败率
同时要看是否破坏旧功能。
Regression Failure Rate = 原本通过但改动后失败的样例数 / 原本通过样例数
如果修复 3 个 bad case，但导致 10 个旧样例失败，说明适应策略不好。

7.4 用户体验指标
也可以看：
用户纠正次数是否减少；
用户重复说明次数是否减少；
用户追问次数是否减少；
用户接受答案比例是否提升。

7.5 质量评估维度
不同模块看不同指标：
Router：路由正确率；
Tool Use：工具选择和参数正确率；
RAG：召回率和引用命中率；
Reflection：问题检出率和修复率；
Planning：计划可执行性和任务完成率；
Multi-Agent：各 Agent 贡献率和冲突处理质量。

结论：
Adaptation 是否有效，要看整体指标是否提升，而不是某一个样例是否变好。
```

### 一句话总结

```
Learning and Adaptation 的本质是：把用户反馈、工具结果、bad case 和评估指标转化为 Agent 后续行为策略的改进。
```

再压缩一点：

```
不只是记住过去，而是从过去中改进未来。
```

## Chapter 10  Model Context Protocol 模型上下文协议

### 是什么

MCP 采用客户端—服务器架构。它规定了数据（resources）、交互模板（本质上就是 prompts）以及可执行函数（tools）应如何由 MCP 服务器暴露，再由 MCP 客户端消费。客户端既可以是 LLM 的宿主应用，也可以是 AI 智能体本身。这种标准化方法大幅降低了 LLM 接入多样化运行环境的复杂度。

它解决的问题是：

```
不同 AI 应用想接入不同工具、数据源、工作流时，不要每次都重新写一套私有集成方式。
```

没有 MCP 时，通常是这样：

```
ChatGPT / Claude / LocalAgent / Cursor / VSCode
分别为：
- 文件系统
- 数据库
- GitHub
- Excel 工具
- RAG 知识库
- 测试工具
- 公司内部 API

各写一套工具接入逻辑。
```

有 MCP 后，可以变成：

```
AI 应用作为 MCP Host / Client
通过统一协议连接多个 MCP Server
每个 MCP Server 暴露自己的 Tools / Resources / Prompts
```

也就是说，MCP 的目标是：

```
让工具、数据源、上下文和 Agent 应用之间有统一连接协议，用来简化 LLM 获取上下文、执行动作以及与各类系统交互的方式。
```

### MCP 和 Tool Use/ Function Calling 的关系

Tool Use 的结构是：

```
模型判断要不要用工具
→ 选择工具
→ 生成参数
→ 程序执行工具
→ 返回工具结果
```

MCP 和它的关系是：

```
Tool Use 是“Agent 要用工具”这个能力；
Function Calling 是“模型告诉程序调用哪个函数”的格式；
MCP 是“工具、资源、Prompt 如何被外部 AI 应用发现和调用”的协议。
```

MCP 与工具函数调用的基本区别如下：

| 特性       | 工具函数调用                                                 | 模型上下文协议（MCP）                                        |
| :--------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
| **标准化** | 通常是专有实现，且因厂商而异；格式和实现方式会随 LLM 提供商不同而变化。 | 属于开放、标准化协议，促进不同 LLM 与工具之间的互操作。      |
| **范围**   | 是 LLM 请求执行某个特定预定义函数的直接机制。                | 是关于 LLM 与外部工具如何发现彼此并进行通信的更广泛框架。    |
| **架构**   | LLM 与应用内部工具处理逻辑之间的一对一交互。                 | 客户端—服务器架构，LLM 驱动的应用（客户端）可连接并使用多个 MCP 服务器。 |
| **发现**   | LLM 需要在特定对话上下文中被明确告知有哪些工具可用。         | 支持动态发现；MCP 客户端可以查询服务器当前提供了哪些能力。   |
| **复用性** | 工具集成通常与具体应用和所用 LLM 紧密耦合。                  | 鼓励构建可复用、独立存在的「MCP 服务器」，供任意合规应用访问。 |

可以这样理解：

```
Function Calling 偏一次调用；
MCP 偏工具生态和连接标准。
```

例如你本地有一个 Excel 分析工具：

```
analyze_excel(file_path: str, sheet_name: str)
```

在普通 Tool Use 里，它只是你项目内部的一个 Python 函数。

但如果你把它做成 MCP Server，它就可以被支持 MCP 的客户端发现、展示、调用。

MCP 规范中，Server 可以向 Client 暴露三类核心能力：

```
Resources：上下文和数据
Prompts：模板化消息和工作流
Tools：模型可以执行的函数
```

官方规范中明确列出，Servers 可以提供 Resources、Prompts、Tools；Clients 也可以提供 Sampling、Roots、Elicitation 等能力。

### MCP 核心架构 Host / Client / Server

#### Host 宿主应用

Host 是真正面向用户的 AI 应用

例如：

```
Claude Desktop
ChatGPT
Cursor
```

Host 负责：

```
1. 管理用户交互；
2. 管理多个 MCP Client；
3. 控制连接权限；
4. 处理用户授权；
5. 聚合上下文；
6. 和 LLM 集成；
7. 做安全策略。
```

官方架构文档中说明，Host 负责创建和管理多个 Client 实例、控制权限和生命周期、执行安全策略和同意要求、处理用户授权决策，并管理跨 Client 的上下文聚合。

#### Client 客户端连接器

Client 不是最终用户看到的聊天界面。

Client 是 Host 里面负责连接某个 MCP Server 的连接实例。

一个 Host 可以有多个 Client。

例如：

```
LocalAgent Host
├─ Client A → 文件系统 MCP Server
├─ Client B → Excel 工具 MCP Server
├─ Client C → 知识库 MCP Server
└─ Client D → Git 工具 MCP Server
```

官方架构文档说明，每个 Client 维护一个到特定 Server 的隔离连接，并负责协议协商、能力交换、双向消息路由、订阅和通知，以及维护不同 Server 之间的安全边界。

重点是：

```
一个 Client 通常对应一个 Server。
```

#### Server 能力提供者

Server 是真正暴露工具、资源和 Prompt 的服务。

例如：

```
filesystem MCP server
database MCP server
github MCP server
excel-analysis MCP server
local-rag MCP server
test-runner MCP server
```

Server 负责：

```
1. 暴露 Resources；
2. 暴露 Tools；
3. 暴露 Prompts；
4. 执行自己负责的能力；
5. 返回结构化结果；
6. 遵守安全约束。
```

官方架构文档中说明，Server 提供特定上下文和能力，可以暴露 resources、tools、prompts，且可以是本地进程或远程服务。

### MCP 的三个核心 Server 能力

MCP Server 最核心的三个能力是：

```
Resources
Tools
Prompts
```

#### Tools 模型可调用的函数

Tools 最接近你前面学的 Function Calling。

例如：

```
calculator
read_file
analyze_excel
query_database
run_tests
search_knowledge_base
```

MCP 的 Tools 让 Server 暴露可由语言模型调用的工具，用来和外部系统交互，例如查询数据库、调用 API 或执行计算；每个工具有唯一名称，并包含描述其 schema 的元数据。

一个工具通常包含：

```
name：工具名
description：工具说明
inputSchema：输入参数 JSON Schema
outputSchema：可选输出结构
```

官方 Tools 规范中，工具定义包含 `name`、可选 `title`、`description`、`inputSchema`，以及可选 `outputSchema` 和 annotations。

例如一个天气工具在 MCP 里大概是：

```json
{
  "name": "get_weather",
  "description": "Get current weather information for a location",
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City name or zip code"
      }
    },
    "required": ["location"]
  }
}
```

对应调用时，Client 会发送类似：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {
      "location": "New York"
    }
  }
}
```

官方 Tools 规范中，Client 通过 `tools/list` 发现工具，通过 `tools/call` 调用工具。

#### Resources 可读取的上下文和数据

Resources 更像“可被 AI 使用的数据”。

例如：

```
file:///project/README.md
file:///logs/error.log
db://test_results/latest
knowledge://agentic-design-patterns/chapter1
excel://data/report.xlsx/sheet/86
```

Resources 的重点不是“执行动作”，而是“提供上下文”。

可以这样区分：

```
Tool：做一个动作
Resource：提供一份数据
```

例如：

```
read_file 作为 Tool：调用后读取文件内容
file:///xxx.py 作为 Resource：这个文件本身是可被读取的上下文
```

对于你的 LocalAgent 来说：

```
项目文档
代码文件
日志文件
知识库片段
Excel 表摘要
历史会话摘要
```

都可以抽象成 Resource。

#### Prompts 可复用的提示词模板和工作流

Prompts 是 Server 暴露给 Client 的模板化 Prompt 或工作流。

例如：

```
code_review_prompt
debug_traceback_prompt
summarize_document_prompt
generate_aw_script_prompt
rag_answer_prompt
```

它的意义是：

```
不只是工具可以标准化，
Prompt 模板和工作流也可以标准化。
```

比如你的 AW 脚本专家可以提供一个 Prompt：

```
generate_aw_script
```

参数：

```
{
  "scenario": "小区删建",
  "loop_count": 5,
  "wait_ms": 2000
}
```

然后 MCP Client 可以获取这个 Prompt 模板，把它交给模型执行。

这对团队协作很有价值，因为它让“经验 Prompt”也成为可复用资产。

### MCP 的通信协议： JSON-RPC 2.0

MCP 底层使用 JSON-RPC 2.0 消息格式。

你可以把它理解成一种标准请求格式。

普通 HTTP API 可能是：

```
POST /api/analyze_excel
```

MCP 更像：

```
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

其中：

```
jsonrpc：协议版本
id：请求 ID，用于匹配响应
method：调用的方法
params：参数
```

官方规范说明，MCP 使用 JSON-RPC 2.0 消息，在 Hosts、Clients、Servers 之间通信。

你需要掌握几个常见方法：

```
initialize：初始化连接和能力协商
tools/list：列出工具
tools/call：调用工具
resources/list：列出资源
resources/read：读取资源
prompts/list：列出 prompts
prompts/get：获取 prompt
notifications/...：通知事件
```

学习阶段你不需要把所有方法背下来，但要理解：

```
MCP 本质上是围绕 JSON-RPC 消息定义的一套工具、资源、Prompt 访问协议。
```

### MCP 的 Transport：stdio 和 Streamable HTTP

MCP 定义了两类标准传输方式：

```
1. stdio
2. Streamable HTTP
```

官方 Transport 文档说明，MCP 使用 JSON-RPC 编码消息，目前定义了两种标准传输机制：stdio，以及 Streamable HTTP；同时 Client 应尽可能支持 stdio。

#### stdio 本地进程通信

stdio 的典型场景是：

```
Host 启动一个本地 MCP Server 子进程
通过 stdin / stdout 交换 JSON-RPC 消息
```

例如：

```
Claude Desktop / LocalAgent
启动：
python excel_mcp_server.py

然后通过标准输入输出通信。
```

stdio 适合：

```
本地文件系统工具
本地代码分析工具
本地 Excel 分析工具
本地 RAG 工具
本地测试执行工具
```

官方文档中说明，stdio transport 下 Client 会把 MCP Server 作为子进程启动，Server 从 stdin 读取 JSON-RPC 消息，并向 stdout 输出消息；Server 不得向 stdout 写入非 MCP 消息。

这个点非常重要：

```
stdout 只能输出协议消息；
日志应该写 stderr。
```

否则 MCP Client 解析会坏。

#### Streamable HTTP 远程服务通信

Streamable HTTP 适合把 MCP Server 做成远程服务。

例如：

```
https://your-company.com/mcp
```

适合：

```
远程数据库工具
公司内部 API
远程知识库
云端工具服务
团队共享 MCP Server
```

官方文档说明，Streamable HTTP 使用 HTTP POST 和 GET 请求，Server 可以选择使用 SSE 流式发送多条 Server 消息，并且必须提供一个同时支持 POST 和 GET 的 MCP endpoint。

你以后完全可以想象：

```
LocalAgent FastAPI 后端
同时提供：
/chat
/mcp
```

`/mcp` 就是一个 MCP endpoint。

### MCP 的连接生命周期

一个 MCP 会话一般包括：

```
1. Client 连接 Server
2. initialize 初始化
3. 能力协商 capability negotiation
4. Client 发现 tools/resources/prompts
5. 模型或 Host 决定调用工具或读取资源
6. Client 发送 JSON-RPC 请求
7. Server 返回结果
8. Host 把结果交给模型生成答案
9. 会话结束或保持
```

官方架构文档说明，MCP 使用能力协商机制，Client 和 Server 在初始化时显式声明支持的功能；Server 可以声明资源订阅、工具支持、Prompt 模板等能力，Client 可以声明 sampling、通知等能力。

你可以把能力协商理解成：

```
Client：你会什么？
Server：我会 tools、resources。
Client：好，那我就只调用你声明过的能力。
```

这比随便调用一个不存在的工具更安全、更规范。

### MCP 和之前的关系

#### MCP 和 Tool Use

MCP 是 Tool Use 的标准化协议层。

```
Tool Use：Agent 要调用工具
MCP：工具如何被发现、描述、调用、返回结果
```

#### MCP 和 Function Calling

Function Calling 通常发生在模型和应用之间。

MCP 通常发生在应用和外部工具 Server 之间。

更准确的链路是：

```
用户
→ Host 里的 LLM
→ LLM 决定需要工具
→ Host / Client 通过 MCP 调用 Server 工具
→ Server 返回结果
→ Host 把结果给 LLM
→ LLM 生成最终回答
```

也就是说：

```
Function Calling 偏模型侧工具决策；
MCP 偏应用侧工具连接协议。
```

#### MCP 和 RAG

RAG 的检索器可以做成 MCP Server。

例如：

```
local_knowledge_mcp_server
暴露：
- search_knowledge_base tool
- read_document_chunk resource
- rag_answer_prompt prompt
```

这样任何支持 MCP 的 AI 应用都可以复用你的本地知识库能力。

#### MCP 和 Memory

Memory 也可以被包装成 MCP Server。

例如：

```
memory_mcp_server
暴露：
- search_memory
- write_memory
- update_memory
- list_recent_tasks
```

但要注意权限：

```
读记忆是低风险；
写记忆是中风险；
删除记忆需要用户确认。
```

#### MCP 和 Multi-Agent

在多 Agent 系统中，MCP Server 可以作为统一工具层。

```
code_expert
data_analyst
knowledge_expert
都不直接操作底层工具
而是通过 MCP Client 调用对应 MCP Server
```

这会让工具权限和协议更清晰。

### MCP 的安全问题

MCP 的安全风险很高，因为它可以让 AI 应用访问外部数据和执行工具

官方规范明确强调，MCP 通过任意数据访问和代码执行路径提供强大能力，因此实现者必须认真处理安全和信任问题；规范中列出用户同意和控制、数据隐私、工具安全、LLM sampling 控制等原则。

以下为安全原则：

#### 用户必须知道暴露了什么工具

用户应该知道：

```
当前 AI 能看到哪些 Server
每个 Server 暴露了哪些工具
工具能访问哪些数据
工具会不会修改系统状态
```

官方 Tools 文档也建议应用提供 UI，清楚显示哪些工具暴露给 AI，并在工具调用时插入清晰提示。

#### 工具调用最好有人类确认

特别是写操作：

```
delete_file
write_file
update_database
send_email
run_shell_command
submit_code
```

这些不能让模型随便执行。

官方 Tools 文档中也强调，从信任、安全角度，应始终有人类在环，能够拒绝工具调用，并建议对操作展示确认提示。

### MCP Server 不能随便看全量对话

MCP 的架构原则之一是 Server 不应该读取完整对话，也不应该看到其他 Server 的内容；完整对话历史保留在 Host，Server 只收到必要上下文。

这点很重要。

正确结构：

```
Host 管理完整上下文
Server 只拿完成工具任务所需的信息
```

错误结构：

```
把全部聊天记录都发给每个 MCP Server
```

#### 本地 HTTP MCP Server 要防 DNS rebinding

如果用 Streamable HTTP 在本地跑 MCP Server，安全要求更高。

官方 Transport 文档要求实现 Streamable HTTP 时验证 Origin header，防止 DNS rebinding；本地运行时建议只绑定 localhost，而不是 0.0.0.0，并实现合适认证。

你以后如果用 FastAPI 做 MCP Server，要特别注意：

```
host="127.0.0.1"
```

不要随便：

```
host="0.0.0.0"
```

尤其在公司内网。

### MCP 和普通内部 Tool Registry 的区别

前面已经学过工具注册表：

```
TOOLS = {
    "read_file": read_file,
    "analyze_excel": analyze_excel,
}
```

这属于内部工具系统。

MCP 则是标准协议。

对比：

| 维度        | 内部 Tool Registry | MCP                       |
| ----------- | ------------------ | ------------------------- |
| 使用范围    | 只在你项目内部     | 可被支持 MCP 的客户端复用 |
| 工具发现    | 代码里写死         | `tools/list` 动态发现     |
| 工具调用    | 直接 Python 函数   | JSON-RPC `tools/call`     |
| 数据资源    | 自己定义           | Resources 标准化          |
| Prompt 模板 | 自己管理           | Prompts 标准化            |
| 客户端兼容  | 弱                 | 强                        |
| 工程复杂度  | 低                 | 中高                      |
| 生态价值    | 低                 | 高                        |

所以学习路径应该是：

```
先会写内部 Tool Registry
再理解 MCP 协议
最后把稳定工具封装成 MCP Server
```

### 重点掌握

#### 第一层 概念层

```
1. MCP 是什么？

见上文 “第二章第十节：MCP 协议是什么” 部分。
核心一句话：
MCP 是一种用于连接 AI 应用和外部工具、数据源、Prompt 工作流的标准协议。
官方规范中，MCP 被定义为一种开放协议，用于让 LLM 应用和外部数据源、工具进行标准化集成，并支持共享上下文、暴露工具能力、构建可组合的集成和工作流。


2. MCP 解决什么问题？

MCP 解决的是：
AI 应用接入外部工具和数据源时缺少统一标准的问题。

没有 MCP 时，每个 Agent 项目都要自己写一套工具接入逻辑：
LocalAgent 自己接文件系统；
Cursor 自己接 GitHub；
Claude Desktop 自己接数据库；
公司内部 Agent 自己接 Excel / RAG / 测试工具。

这样会导致：
1. 工具不能复用；
2. 接口标准不统一；
3. 每个 AI 应用都要重复集成；
4. 工具发现、调用、权限控制都靠私有实现；
5. 工具生态很难沉淀。

MCP 的作用是把这些能力协议化：
AI 应用不直接依赖某个工具的私有实现；
而是通过 MCP Client 连接 MCP Server；
再通过标准协议发现 Tools、Resources 和 Prompts。

对 Agent 工程来说，MCP 的价值是：
把“我项目里的工具函数”升级成“任何兼容 MCP 的 Agent 都能发现和调用的标准工具服务”。


3. Host / Client / Server 是什么？

见上文 “MCP 的核心架构：Host / Client / Server” 部分。
简要总结：
Host 是 AI 应用；
Client 是 Host 内部连接某个 Server 的协议客户端；
Server 是提供工具、资源和 Prompt 的能力服务。

MCP 使用 JSON-RPC 2.0 消息在 Hosts、Clients、Servers 之间通信；官方规范中也明确区分 Host、Client、Server 三类参与者。

一个典型结构是：
LocalAgent Host
├─ MCP Client A → filesystem_mcp_server
├─ MCP Client B → excel_mcp_server
├─ MCP Client C → rag_mcp_server
└─ MCP Client D → memory_mcp_server

注意重点：
一个 Host 可以连接多个 Server；
通常一个 Client 对应一个 Server；
Server 不等于聊天机器人，它只是能力提供方。

官方架构文档也说明，MCP Host 会为每个 MCP Server 创建一个对应的 MCP Client，每个 Client 维护和对应 Server 的专用连接。


4. Tools / Resources / Prompts 是什么？

见上文 “MCP 的三个核心 Server 能力” 部分。
简要总结：
Tools：可执行动作；
Resources：可读取上下文；
Prompts：可复用提示词模板或工作流。

Tools
Tools 是模型可以调用的外部能力，例如查询数据库、调用 API、执行计算等。MCP 工具需要有唯一名称，并带有描述 schema 的元数据。

在 LocalAgent 中对应：
inspect_excel
analyze_sheet
search_knowledge_base
read_file
run_tests
check_python_syntax

Resources
Resources 是 Server 暴露给客户端的上下文数据，例如文件、数据库 schema、应用专用信息等，并通过 URI 唯一标识。

在 LocalAgent 中对应：
项目 README
错误日志
代码文件
知识库片段
Excel sheet 摘要
历史会话摘要

Prompts
Prompts 是可复用的提示词模板或任务工作流。

在 LocalAgent 中对应：
code_review_prompt
debug_traceback_prompt
generate_aw_script_prompt
summarize_file_prompt
rag_answer_prompt

最重要的区分是：
Tool 是做事；
Resource 是给上下文；
Prompt 是提供任务模板。


5. stdio / HTTP 是什么？

见上文 “MCP 的 Transport：stdio 和 Streamable HTTP” 部分。
简要总结：
stdio 适合本地 MCP Server；
Streamable HTTP 适合远程或独立服务型 MCP Server。
MCP 使用 JSON-RPC 编码消息，官方传输层包括 stdio 和 Streamable HTTP。stdio 模式下，Client 把 Server 作为子进程启动，通过 stdin/stdout 交换 JSON-RPC 消息；Server 的 stdout 不能输出非 MCP 消息，日志应写 stderr。

官方文档中，Streamable HTTP 使用 POST/GET 和可选 SSE，Server 需要提供一个同时支持 POST 和 GET 的 MCP endpoint。
```

#### 第二层 协议层

```
1. JSON-RPC 2.0 消息格式是什么？

MCP 底层使用 JSON-RPC 2.0 消息。官方规范说明，MCP 使用 JSON-RPC 2.0 在 Host、Client、Server 之间通信。

一个典型请求是：

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}

字段含义：

jsonrpc：协议版本，固定为 2.0；
id：请求 ID，用于匹配响应；
method：要调用的方法；
params：方法参数。

一个典型响应是：

{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": []
  }
}

一个典型错误响应是：

{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32602,
    "message": "Invalid params"
  }
}

你需要掌握到这个程度：

看到 method 能知道这是在调用 MCP 的哪个能力；
看到 id 能知道请求和响应如何对应；
看到 params 能知道参数传给谁；
看到 result / error 能判断执行成功还是失败。
2. initialize 是什么？

initialize 是 MCP 连接建立后的第一步。

它负责：

1. 协商协议版本；
2. 交换 Client / Server 能力；
3. 交换实现信息；
4. 建立后续通信基础。

官方生命周期文档说明，初始化阶段必须是 Client 和 Server 之间的首次交互，并在这个阶段建立协议版本兼容性、交换和协商能力、共享实现信息。

示例：

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "LocalAgent",
      "version": "0.1.0"
    }
  }
}

你可以把 initialize 理解成：

Client 问 Server：我们用哪个协议版本？你会什么？我会什么？
3. capability negotiation 是什么？

capability negotiation 是能力协商。

它解决的问题是：

Client 和 Server 不能假设对方支持所有 MCP 能力，而要先声明和确认。

例如 Server 声明自己支持：

{
  "capabilities": {
    "tools": {
      "listChanged": true
    },
    "resources": {
      "subscribe": true,
      "listChanged": true
    },
    "prompts": {}
  }
}

Client 看到后才知道：

可以 tools/list；
可以 tools/call；
可以 resources/list；
可以 resources/read；
可以 prompts/list；
可以 prompts/get。

官方生命周期文档把能力协商列为初始化阶段的核心内容之一。

工程意义：

不要硬编码假设某个 Server 一定支持某个功能；
要先看它 initialize 返回的 capabilities。
4. tools/list 是什么？

tools/list 用于列出 Server 暴露的工具。

例如：

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}

返回可能是：

{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "inspect_excel",
        "description": "Inspect workbook sheets and columns",
        "inputSchema": {
          "type": "object",
          "properties": {
            "file_path": {
              "type": "string"
            }
          },
          "required": ["file_path"]
        }
      }
    ]
  }
}

tools/list 的作用是：

让 Host / Client 动态发现 Server 提供了哪些工具。

这和你自己写：

TOOLS = {"inspect_excel": inspect_excel}

不同。

内部 Tool Registry 是代码写死的；MCP 是运行时通过协议发现的。

5. tools/call 是什么？

tools/call 用于调用某个工具。

示例：

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "inspect_excel",
    "arguments": {
      "file_path": "D:/data/report.xlsx"
    }
  }
}

返回：

{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Workbook has sheets: 86, 85, 8011"
      }
    ],
    "isError": false
  }
}

你需要掌握：

tools/list 是发现工具；
tools/call 是执行工具。

在 LocalAgent 中，模型可能先决定：

需要分析 Excel 文件

然后 Host 通过 MCP Client 调用：

excel_mcp_server.tools/call(inspect_excel)

工具返回结果后，再交给模型继续分析。

6. resources/list 是什么？

resources/list 用于列出 Server 提供的资源。

例如：

{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "resources/list",
  "params": {}
}

返回可能是：

{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "resources": [
      {
        "uri": "file:///project/README.md",
        "name": "README.md",
        "description": "Project overview"
      },
      {
        "uri": "knowledge://agentic-design-patterns/chapter1",
        "name": "Chapter 1 Summary",
        "description": "Summary of seven Agent design patterns"
      }
    ]
  }
}

它的作用是：

让 Host 知道这个 Server 有哪些上下文数据可用。

Resources 更偏“读上下文”，不是执行动作。

7. resources/read 是什么？

resources/read 用于读取某个资源。

示例：

{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "resources/read",
  "params": {
    "uri": "file:///project/README.md"
  }
}

返回可能是：

{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "contents": [
      {
        "uri": "file:///project/README.md",
        "mimeType": "text/markdown",
        "text": "# LocalAgent\n..."
      }
    ]
  }
}

你需要区分：

resources/read：读取已有上下文；
tools/call read_file：通过工具执行读取动作。

两者都可能读文件，但抽象不同：

Resource 更像“这个文件是一份上下文”；
Tool 更像“执行一个读取文件的动作”。
8. prompts/list 是什么？

prompts/list 用于列出 Server 提供的 Prompt 模板。

示例：

{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "prompts/list",
  "params": {}
}

返回可能是：

{
  "jsonrpc": "2.0",
  "id": 6,
  "result": {
    "prompts": [
      {
        "name": "code_review",
        "description": "Review Python code for bugs, readability and edge cases",
        "arguments": [
          {
            "name": "code",
            "required": true
          }
        ]
      }
    ]
  }
}

Prompts 的价值是：

把常用任务模板也标准化暴露出来，而不只是暴露工具。
9. prompts/get 是什么？

prompts/get 用于获取具体 Prompt 模板。

示例：

{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "prompts/get",
  "params": {
    "name": "code_review",
    "arguments": {
      "code": "def add(a,b): return a+b"
    }
  }
}

返回可能是：

{
  "jsonrpc": "2.0",
  "id": 7,
  "result": {
    "description": "Review Python code",
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "请审查下面的 Python 代码：\ndef add(a,b): return a+b"
        }
      }
    ]
  }
}

你可以把它理解成：

prompts/list：有哪些模板；
prompts/get：取出某个模板并填充参数。

对你的项目来说，AW 脚本生成、代码审查、RAG 答案生成，都适合沉淀成 Prompt 模板。
```

#### 第三层 工程层

```
1. 如何设计一个本地 MCP Server？

学习阶段可以先设计一个最小本地 Server。

目标：

通过 stdio 启动；
暴露 2-3 个工具；
能被 MCP Client 调用；
返回结构化结果；
有基本错误处理和日志。

建议第一个 demo 做：

excel_mcp_server

因为你已有 Excel 工程场景。

最小能力：

inspect_excel：查看 workbook 有哪些 sheet、每个 sheet 有哪些列；
copy_column_by_composite_key：按复合键复制列；
summarize_sheet：总结指定 sheet 行列信息。

本地启动方式可以理解成：

Host 启动子进程：
python excel_mcp_server.py

然后通过 stdin / stdout 和它通信。

stdio 模式下要注意：

stdout 只能输出 MCP JSON-RPC 消息；
普通日志必须写 stderr；
否则 Client 会解析失败。

这是官方 transport 要求之一：Server 不得向 stdout 写入非 MCP 消息，日志可以写到 stderr。

2. 如何暴露几个工具？

一个 MCP Server 不要一开始暴露太多工具。

建议按能力边界设计：

filesystem_mcp_server：只处理文件；
excel_mcp_server：只处理 Excel；
rag_mcp_server：只处理知识库；
memory_mcp_server：只处理记忆；
test_mcp_server：只处理测试执行。

以 excel_mcp_server 为例，工具可以是：

inspect_excel
analyze_sheet
copy_column_by_composite_key

不要一开始做一个万能工具：

do_excel_task

因为这会导致：

工具描述模糊；
参数 schema 很难设计；
模型容易传错参数；
权限控制困难；
测试和评估困难。

好的工具应该：

职责单一；
名字清楚；
参数明确；
返回稳定；
失败可解释。
3. 如何定义 inputSchema？

inputSchema 是 MCP Tool 的参数说明，本质是 JSON Schema。

例如：

{
  "name": "copy_column_by_composite_key",
  "description": "根据复合键匹配源 sheet 和目标 sheet，并把源列覆盖写入目标列。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "file_path": {
        "type": "string",
        "description": "Excel 文件路径"
      },
      "source_sheet": {
        "type": "string",
        "description": "源工作表名称"
      },
      "target_sheets": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "description": "目标工作表名称列表"
      },
      "key_columns": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "description": "复合键列名或列号，例如 ['A', 'B']"
      },
      "source_column": {
        "type": "string",
        "description": "源列，例如 N"
      },
      "target_column": {
        "type": "string",
        "description": "目标列，例如 O"
      },
      "overwrite": {
        "type": "boolean",
        "description": "是否覆盖目标列已有内容"
      }
    },
    "required": [
      "file_path",
      "source_sheet",
      "target_sheets",
      "key_columns",
      "source_column",
      "target_column"
    ]
  }
}

设计原则：

1. required 字段必须明确；
2. 参数描述要让模型知道怎么填；
3. 枚举值尽量用 enum；
4. 布尔开关要有默认策略；
5. 文件路径要做路径限制；
6. 写操作参数必须特别清楚；
7. 不要让一个参数承担多种含义。
4. 如何返回结构化结果？

工具返回不要只返回一段随意文本，最好结构化。

例如 Excel 覆盖工具返回：

{
  "success": true,
  "operation": "copy_column_by_composite_key",
  "file_path": "D:/data/report.xlsx",
  "source_sheet": "86",
  "target_sheets": ["85", "8011"],
  "matched_rows": {
    "85": 120,
    "8011": 118
  },
  "updated_cells": {
    "85": 120,
    "8011": 118
  },
  "warnings": [],
  "summary": "已根据 A、B 复合键将 86 表 N 列覆盖到 85 和 8011 表 O 列。"
}

返回结构化结果的好处：

1. 模型更容易生成可靠总结；
2. Reviewer 可以检查结果；
3. 日志可以记录关键字段；
4. 自动评估可以断言 matched_rows、updated_cells；
5. 出错时可以定位问题。

如果失败，也要结构化：

{
  "success": false,
  "error_type": "sheet_not_found",
  "message": "目标工作表 8011 不存在。",
  "recoverable": true,
  "suggestion": "请先调用 inspect_excel 查看可用 sheet。"
}
5. 如何处理错误？

MCP Server 必须做好错误处理。

常见错误类型：

invalid_arguments：参数不合法；
file_not_found：文件不存在；
permission_denied：权限不足；
sheet_not_found：sheet 不存在；
column_not_found：列不存在；
duplicate_key：复合键重复；
tool_execution_error：工具执行异常；
timeout：执行超时。

错误处理原则：

1. 不要直接抛 Python 堆栈给模型；
2. 返回可读错误信息；
3. 标明是否可恢复；
4. 给出下一步建议；
5. 日志里保留完整异常；
6. 返回给模型的内容要脱敏。

例如：

{
  "success": false,
  "error_type": "missing_required_argument",
  "message": "缺少必填参数 sheet_name。",
  "recoverable": true,
  "suggestion": "请先调用 inspect_excel 获取可用 sheet，然后重新调用 analyze_sheet。"
}

这样模型可以自动修正下一次调用。

6. 如何记录日志？

MCP tool call 日志至少要记录：

trace_id；
server_name；
tool_name；
arguments_summary；
status；
result_summary；
error_type；
elapsed_seconds；
timestamp；
risk_level；
user_confirmed。

示例：

{
  "trace_id": "trace_001",
  "server_name": "excel_mcp_server",
  "tool_name": "copy_column_by_composite_key",
  "arguments_summary": {
    "source_sheet": "86",
    "target_sheets": ["85", "8011"],
    "key_columns": ["A", "B"],
    "source_column": "N",
    "target_column": "O"
  },
  "status": "success",
  "result_summary": "updated 238 cells",
  "elapsed_seconds": 1.42,
  "risk_level": "write",
  "user_confirmed": true,
  "timestamp": "2026-07-06T10:00:00"
}

注意：

不要把 API Key、数据库密码、公司内网真实地址写入日志；
文件路径必要时可脱敏；
大文件内容不要直接写入日志，只写摘要。
7. 如何控制权限？

权限控制是 MCP 工程实现的核心。

可以按风险分级：

read：只读，例如 inspect_excel、read_file、search_docs；
write：写入，例如 write_file、copy_column_by_composite_key；
execute：执行，例如 run_tests、run_shell_command；
external：外部影响，例如 send_email、submit_pr、update_database。

策略：

1. 只读工具可以默认允许；
2. 写文件工具需要用户确认；
3. 执行命令工具默认关闭；
4. 数据库默认只允许 SELECT；
5. 文件路径限制在 workspace；
6. 所有工具必须在白名单中；
7. 高风险工具需要二次确认。

官方 Tools 文档也强调，工具调用应有人类在环，应用应清楚展示暴露给模型的工具，并在调用工具时给用户明确提示。
```



#### 第四层 安全层

```
1. 为什么需要工具白名单？

工具白名单用于限制模型只能调用被允许的工具。

不要让模型可以通过字符串随便调用任意函数。

错误设计：

func = globals()[tool_name]
func(**arguments)

正确设计：

ALLOWED_TOOLS = {
    "inspect_excel": inspect_excel,
    "analyze_sheet": analyze_sheet,
}

原因：

1. 防止模型调用危险函数；
2. 防止调用内部未公开函数；
3. 防止绕过权限；
4. 方便审计和测试；
5. 方便按 Agent 分配工具权限。
2. 为什么必须参数校验？

模型生成的参数不一定可靠。

可能出现：

缺少必填参数；
参数类型错误；
路径越权；
sheet 名不存在；
列名错误；
传入超大文件；
写操作参数不完整。

所以必须：

1. 用 inputSchema 约束参数；
2. 程序侧再次校验；
3. 对路径做 workspace 限制；
4. 对写操作做风险检查；
5. 参数错误时返回结构化错误。

不能因为模型“看起来填对了”就直接执行。

3. 为什么需要用户确认？

因为 MCP 工具可能执行真实操作。

需要确认的操作包括：

写文件；
覆盖 Excel；
删除文件；
更新数据库；
发送邮件；
运行 shell；
提交代码；
修改配置。

比如用户让你：

把 86 的 N 列覆盖到 85 和 8011 的 O 列

这是写操作，应该明确提示：

即将修改原 Excel 文件；
目标 sheet 是 85 和 8011；
目标列是 O；
会覆盖已有内容；
是否确认执行？

对学习 demo，可以先模拟确认；对真实项目，必须有 UI 或 CLI 确认。

4. 如何区分只读和写操作？

可以按是否改变外部状态区分。

只读工具：

inspect_excel；
read_file；
search_knowledge_base；
list_files；
query_database_select；
check_python_syntax。

写操作：

write_file；
copy_column_by_composite_key；
update_excel_cell；
delete_file；
update_database；
create_draft；
send_email。

执行类工具：

run_tests；
run_python_script；
run_shell_command。

原则：

只读工具默认可执行；
写操作必须确认；
执行类工具要限制范围；
外部影响类工具必须最高风险控制。
5. 为什么本地 Server 要绑定 localhost？

如果使用 Streamable HTTP 在本地跑 MCP Server，应该绑定：

127.0.0.1

而不是：

0.0.0.0

官方 Transport 文档明确建议，本地运行 Streamable HTTP Server 时应只绑定 localhost，并验证 Origin header，以防 DNS rebinding 攻击。

也就是说：

本地 MCP Server 不应该默认暴露给局域网或公网。

尤其在公司内网环境，这一点非常重要。

6. 为什么不要暴露敏感数据？

MCP Server 可能会接触：

本地文件；
项目代码；
日志；
数据库；
API Key；
公司内网接口；
用户记忆；
工具执行结果。

如果不做脱敏和权限控制，模型或外部 Server 可能看到不该看到的内容。

应该避免暴露：

API Key；
数据库密码；
内网真实 IP；
生产环境配置；
客户数据；
公司敏感日志；
未脱敏报错；
用户隐私。

正确做法：

只传工具执行所需的最小数据；
日志中只保存摘要；
敏感字段脱敏；
Server 不拿完整对话；
不同 Server 之间隔离上下文。
7. 为什么不要让 Server 看完整对话？

MCP Server 是能力提供者，不应该默认看到用户完整聊天记录。

原因：

1. 最小权限原则；
2. 降低隐私风险；
3. 避免 Server 获取无关敏感信息；
4. 保持不同 Server 的安全边界；
5. 防止工具服务被提示注入污染。

正确结构：

Host 管理完整上下文；
Client 只把工具调用所需参数发给 Server；
Server 只处理自己的任务。

例如 Excel Server 只需要：

file_path
sheet_name
key_columns
source_column
target_column

它不需要知道：

用户完整对话；
其他 Agent 的内部推理；
API Key；
无关项目背景。
```



#### 第五层 项目层

```
1. LocalAgent 里哪些能力适合做 MCP Server？

适合 MCP 化的能力通常满足：

边界清楚；
可复用；
参数明确；
工具结果可结构化；
未来可能被其他 Agent / Client 使用。

你的 LocalAgent 中适合做 MCP Server 的能力：

1. filesystem_mcp_server
文件浏览、读取、搜索。

2. excel_mcp_server
Excel / CSV 检查、分析、匹配、覆盖。

3. rag_mcp_server
知识库检索、文档片段读取。

4. memory_mcp_server
记忆检索、记忆写入、bad case 查询。

5. test_mcp_server
运行测试、语法检查、pytest 结果解析。

6. code_mcp_server
代码搜索、函数定位、导入关系分析。

7. aw_script_mcp_server
AW 脚本生成、规则校验、模板查询。

优先级建议：

第一优先级：filesystem_mcp_server、excel_mcp_server
第二优先级：rag_mcp_server、test_mcp_server
第三优先级：memory_mcp_server、aw_script_mcp_server

原因：

文件和 Excel 工具边界最清楚，最适合先做 demo；
RAG 和测试工具价值高，但实现复杂一点；
Memory 和 AW 脚本专家更像高级能力，适合后续接入。
2. 哪些能力保持内部函数就够了？

不是所有能力都需要 MCP 化。

可以继续保持内部函数的能力：

1. Router 内部分类逻辑；
2. Planner 内部计划生成；
3. Aggregator 汇总逻辑；
4. Reviewer 审查逻辑；
5. Prompt Chaining 的中间步骤；
6. LLMClient / AsyncLLMClient；
7. UI 状态管理；
8. 当前会话短期上下文管理。

原因：

这些能力更像 Host 内部编排逻辑，
不是外部工具能力，
也不一定需要被其他 MCP Client 复用。

判断标准：

如果它是“Agent 内部怎么思考和编排”，保持内部函数；
如果它是“外部可调用的工具或数据源能力”，适合 MCP 化。

例如：

Routing 不适合先做 MCP Server；
Excel 分析适合做 MCP Server。
3. 哪些工具应该只读？

只读工具是低风险工具，可以默认允许。

LocalAgent 中适合只读的工具：

list_files；
read_file；
search_files；
inspect_excel；
summarize_sheet；
search_knowledge_base；
read_document_chunk；
search_memory；
check_python_syntax；
parse_log；
list_test_cases。

这些工具的特点是：

不修改文件；
不写数据库；
不发送外部请求；
不影响真实系统状态。

但只读不等于无风险。

仍然要注意：

路径限制；
敏感文件过滤；
大文件大小限制；
日志脱敏；
权限检查。
4. 哪些工具需要确认？

需要确认的是会改变外部状态、消耗资源或有安全风险的工具。

LocalAgent 中需要确认的工具：

write_file；
overwrite_excel_column；
copy_column_by_composite_key；
delete_file；
update_memory；
delete_memory；
run_tests；
run_python_script；
run_shell_command；
update_database；
generate_or_modify_aw_script_file。

其中高风险工具：

delete_file；
run_shell_command；
update_database；
覆盖原始 Excel；
修改公司项目文件。

这些必须明确提示用户：

将要执行什么；
影响哪些文件；
是否覆盖已有内容；
能否回滚；
是否已备份；
是否确认继续。

对于你的 Excel 原地修改类工具，建议默认策略是：

先生成备份；
再执行覆盖；
返回更新摘要；
记录 tool call 日志。
5. 如何记录 MCP tool call 日志？

建议把 MCP tool call 日志纳入 LocalAgent 的 [[ORCH]] 或 trace 系统。

字段：

trace_id；
request_id；
server_name；
transport；
tool_name；
arguments_summary；
risk_level；
need_confirmation；
user_confirmed；
status；
result_summary；
error_type；
elapsed_seconds；
timestamp。

示例：

{
  "trace_id": "trace_20260706_001",
  "request_id": "mcp_req_003",
  "server_name": "excel_mcp_server",
  "transport": "stdio",
  "tool_name": "copy_column_by_composite_key",
  "arguments_summary": {
    "source_sheet": "86",
    "target_sheets": ["85", "8011"],
    "key_columns": ["A", "B"],
    "source_column": "N",
    "target_column": "O"
  },
  "risk_level": "write",
  "need_confirmation": true,
  "user_confirmed": true,
  "status": "success",
  "result_summary": "matched 238 rows and updated 238 cells",
  "elapsed_seconds": 1.42,
  "timestamp": "2026-07-06T10:00:00"
}

日志用途：

1. 前端展示 Agent 做了什么；
2. 调试工具调用失败；
3. 评估 Tool Call 正确率；
4. 生成 bad case；
5. 做安全审计；
6. 支持回归测试。
6. 如何纳入自动评估平台？

MCP 可以直接接入你的 Agent 自动评估与回归测试平台。

评估对象可以包括：

1. 工具发现是否正确；
2. 工具选择是否正确；
3. 工具参数是否正确；
4. 工具执行是否成功；
5. 工具结果是否被正确使用；
6. 错误处理是否稳定；
7. 高风险工具是否触发确认；
8. 日志是否完整。

测试样例示例：

{
  "case_id": "mcp_excel_001",
  "input": "根据 86 的 AB 列匹配 85 和 8011，把 86 的 N 列覆盖到目标 O 列",
  "expected_server": "excel_mcp_server",
  "expected_tool": "copy_column_by_composite_key",
  "expected_arguments": {
    "source_sheet": "86",
    "target_sheets": ["85", "8011"],
    "key_columns": ["A", "B"],
    "source_column": "N",
    "target_column": "O"
  },
  "need_confirmation": true
}

指标：

MCP Tool Selection Accuracy；
MCP Argument Accuracy；
MCP Tool Call Success Rate；
MCP Permission Check Pass Rate；
MCP Confirmation Trigger Rate；
MCP Error Handling Quality；
MCP Result Grounding Rate。

评估闭环：

执行 MCP tool call
→ 记录 trace
→ 对比 expected tool / arguments
→ 判断是否成功
→ 生成 bad case
→ 修复 schema / Prompt / 规则
→ 加入回归测试

这样 MCP 不只是“能调工具”，而是进入了工程化评估体系。
```



### 一句话总结

```
MCP 的本质是：用统一协议把 AI 应用和外部工具、数据源、Prompt 工作流连接起来，让 Agent 的上下文和能力可以标准化、可复用、可组合。
```

再压缩一点：

```
Tool Use 是会用工具，MCP 是让工具接入变成标准。
```

对你来说，这一节可以总结成：

```
LocalAgent 未来要从“内部工具调用系统”升级到“标准化工具协议系统”，MCP 就是最值得学习的方向。
```