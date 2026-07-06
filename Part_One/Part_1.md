# Part One

## Chapter 3 Parallelization

### 是什么

并行化模式：把一个任务拆成多个可以同时执行的子任务，让多个模型调用、多个工具调用、多个 Agent 或多个处理流程并行运行，最后再把结果汇总。

核心思想：如果多个步骤之间没有强依赖关系，就不要顺序执行，而是并行执行，提高效率或提升结果质量。

![image-20260630224058849](C:\Users\GemHr\AppData\Roaming\Typora\typora-user-images\image-20260630224058849.png)

### 为什么需要 Parallelization

Agent 系统中，很多任务天然可以拆分为多个互不依赖的子任务

eg. 审查一段代码，可以并行从多个角度检查：

```
安全问题检查
性能问题检查
可读性检查
边界条件检查
```

这些检查之间没有严格先后关系，所以可以同时执行。

如果顺序执行：

```
安全检查 → 性能检查 → 可读性检查 → 边界条件检查 → 汇总
```

耗时会更长。

如果并行执行：

```
安全检查     ┐
性能检查     ├→ 汇总
可读性检查   ┤
边界条件检查 ┘
```

效率更高，也更容易做多角度分析。

这么做的核心在于识别工作流中那些不依赖其他步骤即时输出的环节，并将它们并行执行。当任务涉及 API、数据库等本身就有往返延迟的外部服务时，这种做法尤为有效：可以一次性并发发起多条请求。

### Parallelization 解决什么问题

1. 降低总耗时
   如果过一个任务需要多个独立步骤，顺序执行会累加耗时。

   例如每个模型调用 3 秒，4 个步骤顺序执行就是：

   ```
   3 + 3 + 3 + 3 = 12 秒
   ```

   并行执行可能接近：

   ```
   max(3, 3, 3, 3) = 3 秒
   ```

   实际还会有调度和汇总开销，但整体通常明显更快。

2. 提升结果质量

   例如同一个问题可以让多个 Agent 分别分析：

   ```
   代码专家：关注实现逻辑
   测试专家：关注边界用例
   架构专家：关注模块设计
   安全专家：关注风险点
   ```

   最后由一个汇总器整合结果。

   这种做法比单个 Prompt 一次性分析更全面。

### 典型流程

一个标准并行流程通常是：

```
用户输入
→ 拆分为多个独立子任务
→ 并行执行多个 Worker
→ 收集每个 Worker 的结果
→ 汇总、去重、冲突处理
→ 输出最终答案
```

可以抽象成：

```
Input
→ Worker A
→ Worker B
→ Worker C
→ Aggregator
→ Output
```

其中：

```
Worker：负责执行单个子任务
Aggregator：负责汇总多个结果
```

### 和提示链与路由的区别

| 模式            | 解决的问题                 | 流程特点       |
| --------------- | -------------------------- | -------------- |
| Prompt Chaining | 一个复杂任务如何分步骤完成 | 顺序执行       |
| Routing         | 一个任务应该走哪条路径     | 条件分支       |
| Parallelization | 多个独立任务如何同时完成   | 并行执行后汇总 |

可以这样理解：

```
Prompt Chaining：先做 A，再做 B
Routing：判断做 A 还是 B
Parallelization：A、B、C 一起做
```

三者经常组合使用：

```
用户输入
→ Routing 判断任务类型
→ 进入某条 Chain
→ Chain 中某些步骤并行执行
→ Aggregator 汇总结果
→ 输出最终答案
```

### Parallelization 的两种常见形式

1. Sectioning 任务切片并行

   把一个大输入切成多个部分，每个部分并行处理。

   例如：

   ```
   长文档
   → 第 1 段摘要
   → 第 2 段摘要
   → 第 3 段摘要
   → 第 4 段摘要
   → 汇总成总摘要
   ```

   适合：

   ```
   长文档总结
   多文件分析
   多日志分析
   多表格处理
   多测试用例分析
   ```

2. Voting / Multiple Perspective 多视角并行

   让多个 Worker 从不同角度处理同一个输入。

   例如代码审查：

   ```
   Worker A：检查 bug
   Worker B：检查性能
   Worker C：检查安全
   Worker D：检查可维护性
   → 汇总
   ```

   适合：

   ```
   代码审查
   方案评估
   论文审稿
   复杂问题分析
   Agent 自检
   多专家协作
   ```

   这类并行不一定是为了切分输入，而是为了得到不同角度的结果。

### 核心组成

1. Task Splitter 任务拆分器

   负责判断任务能不能拆，以及怎么拆。

   例如：

   ```
   按文档段落拆
   按文件拆
   按问题维度拆
   按专家角色拆
   按数据范围拆
   ```

   不是所有任务都适合并行。只有子任务之间没有强依赖关系时，才适合并行。

2. Worker 并行执行单元

   Worker 可以是：

   ```
   一个 Prompt
   一个模型调用
   一个工具调用
   一个 Agent
   一个代码函数
   一个数据处理任务
   ```

   每个 Worker 应该有明确职责。

   例如：

   ```
   security_review_worker
   performance_review_worker
   readability_review_worker
   ```

3. Aggregator 结果汇总器

   Aggregator 是 Parallelization 的关键。

   因为并行执行后，结果可能会：

   ```
   重复
   冲突
   遗漏
   粒度不一致
   格式不一致
   重要性不同
   ```

   Aggregator 要负责：

   ```
   1. 合并多个结果；
   2. 去重；
   3. 处理冲突；
   4. 排序；
   5. 生成最终答案；
   6. 必要时标注不确定性。
   ```

   没有 Aggregator，并行结果只是“多段输出”，不是一个完整 Agent 结果。

4. Concurrency Controller 并发控制器

   工程上还要控制并发数量。

   如果一次发起太多模型请求，可能导致：

   ```
   接口限流
   响应变慢
   资源占用过高
   日志混乱
   失败率升高
   ```

   所以要设计：

   ```
   最大并发数
   超时时间
   失败重试
   部分失败是否允许继续
   结果顺序如何保持
   ```

### 适合场景

适合用的场景：

```
1. 子任务之间没有强依赖关系；
2. 任务可以自然拆分；
3. 多个角度分析会提升质量；
4. 顺序执行耗时太长；
5. 允许最后统一汇总；
6. 单个模型一次性处理容易漏项。
```

例如：

```
多文件代码审查
多个 Excel sheet 分析
长文档分段总结
论文多维度审稿
Agent 多专家评估
RAG 多路检索
多个候选答案投票
```

### 什么时候不用

不适合用的场景：

```
1. 后一步强依赖前一步结果；
2. 任务非常简单；
3. 并行成本高于收益；
4. 结果之间很难合并；
5. 工具或模型接口不支持高并发；
6. 需要严格顺序执行。
```

例如：

```
先登录再查询再下载
先解析字段再生成 SQL
先读取配置再执行任务
```

这种更适合 Prompt Chaining，而不是 Parallelization。

### Python 中如何实现并行

1. concurrent.futures

   适合普通同步函数并行。

   ```python
   from concurrent.futures import ThreadPoolExecutor
   
   
   with ThreadPoolExecutor(max_workers=3) as executor:
       futures = [
           executor.submit(worker_a, user_input),
           executor.submit(worker_b, user_input),
           executor.submit(worker_c, user_input),
       ]
   
       results = [future.result() for future in futures]
   ```

   对于 HTTP 模型请求来说，很多时候是 I/O 密集型，线程池就够用。

2. asyncio

   适合异步 HTTP 客户端，比如 `httpx.AsyncClient`。

   ```python
   results = await asyncio.gather(
       worker_a(user_input),
       worker_b(user_input),
       worker_c(user_input),
   )
   ```

3. 多进程
   适合CPU密集型任务，比如大规模本地数据处理、复杂计算，但是模型HTTP调用一般不需要多进程

### 常见坑

1. 误把有依赖的任务并行

2. 并行结果不好汇总

   多个 Worker 输出格式不一致，Aggregator 会很难处理。

   所以每个 Worker 最好使用统一格式

3. 没有处理部分失败
   并行中，可能某个 Worker 失败，但其他 Worker 成功。

   你需要决定：

   ```
   一个失败就整体失败？
   允许部分成功？
   失败结果如何展示？
   是否重试失败 Worker？
   ```

4. 并发过高

   应该设置：

   ```
   max_workers
   timeout
   retry
   rate limit
   ```

5. 重复信息太多
   多个 Worker 可能说同一件事，所以 Aggregator 要负责去重和排序，避免答案啰嗦

### 需要掌握

1. 必须掌握

```
1.Parallelization的定义是什么
它的核心含义是：把一个任务拆分成多个互不强依赖的子任务，让这些子任务同时执行，最后再把多个结果汇总成最终答案。


2.Parallelization是如何解决耗时和多视角分析问题的

3.Worker和 Aggregator 的关系是什么
Worker：执行具体子任务，是并行执行单元； Aggregator：汇总多个 Worker 的结果，是结果汇总器。
Worker 负责“分别看”；
Aggregator 负责“统一说”。

流程是：

用户输入
→ 多个 Worker 并行分析
→ Aggregator 收集结果
→ Aggregator 汇总为最终答案

如果没有 Aggregator，Parallelization 只是得到一堆零散输出，不是完整 Agent 结果。

4.哪些任务适合并行
子任务之间没有强依赖关系。
如 多文件分析，多sheet excel分析，长文档分段总结，多角度代码审查，多路RAG检索，Agent自动评估


5.不适合并行的任务
后一步强依赖前一步结果，如
强顺序依赖任务（登录，获取token，调用接口，下载结果），Prompt Chaining型任务，数据依赖明显型任务，任务很简单，汇总困难的任务，高风险工具调用，


6.并行结果为什么要统一格式
并行结果需要统一格式，是因为 Aggregator 要稳定读取、合并和比较多个 Worker 的输出。
统一格式的好处包括：

1. 方便程序解析；
2. 方便结果合并；
3. 方便去重；
4. 方便排序；
5. 方便冲突检测；
6. 方便保存日志；
7. 方便后续评估；
8. 方便失败时定位是哪一个 Worker 的问题。

推荐 Worker 输出包含：

1. worker_name：Worker 名称；
2. status：success 或 failed；
3. findings：发现的问题列表；
4. summary：简短总结；
5. confidence：置信度；
6. error：失败原因；
7. metadata：额外信息。


7.部分失败和并发数量如何处理
并行任务中，部分失败是常见情况。

例如 4 个 Worker 并行执行：

Worker A：成功
Worker B：成功
Worker C：失败
Worker D：成功

这时系统需要决定：

1. 是否整体失败？
2. 是否保留成功结果？
3. 是否重试失败 Worker？
4. 是否在最终结果中说明失败情况？
7.1 部分失败如何处理？

常见策略有三种。

策略一：全部成功才算成功

适合强一致性场景。

例如：

所有数据校验任务都必须成功

只要一个失败，整体失败。

优点是结果可靠，缺点是容错性差。

策略二：允许部分成功

适合分析类任务。

例如：

4 个代码审查 Worker 中 1 个失败，仍然可以汇总其他 3 个结果

最终答案中说明：

安全检查成功；
性能检查成功；
可维护性检查成功；
测试覆盖检查失败。

这种方式更适合 Agent 分析场景。

策略三：失败 Worker 重试

如果失败是临时网络问题、模型超时，可以重试。

例如：

最多重试 2 次；
重试仍失败则记录 error；
最终结果允许部分成功。
7.2 并发数量如何控制？

并发数量不是越大越好。

如果一次发起太多模型请求，可能导致：

1. API 限流；
2. 请求超时；
3. 服务压力过大；
4. 日志混乱；
5. 失败率升高；
6. token 消耗过快。

所以需要设置最大并发数。

例如：

max_workers = 3

含义是最多同时跑 3 个 Worker。

7.3 工程建议

并行执行时建议设计这些参数：

1. max_workers：最大并发数；
2. timeout：单个 Worker 超时时间；
3. retry_times：失败重试次数；
4. allow_partial_success：是否允许部分成功；
5. fail_fast：是否一个失败就立即停止；
6. rate_limit：限速；
7. log_result：是否记录每个 Worker 结果。

总结原则：

分析类任务允许部分成功；
关键任务要求全部成功；
失败要记录；
必要时重试；
并发数量要保守控制。
```

2. 进阶掌握

   ```
   1. Sectioning 和多视角并行的区别是什么？
   Parallelization 常见有两种形式：
   
   1. Sectioning：切片并行；
   2. Multiple Perspectives：多视角并行。
   1.1 Sectioning：切片并行
   
   Sectioning 是把一个大输入切成多个小块，每个 Worker 处理其中一块。
   
   例如长文档总结：
   
   长文档
   → 第 1 段摘要
   → 第 2 段摘要
   → 第 3 段摘要
   → 汇总为总摘要
   
   这里每个 Worker 处理的是不同输入片段。
   
   适合：
   
   1. 长文档；
   2. 多文件；
   3. 多日志；
   4. 多 Excel Sheet；
   5. 大批量测试用例；
   6. 大数据分块处理。
   
   核心目标是：
   
   把大任务切成小任务，提高处理速度，并绕开单次上下文过长的问题。
   1.2 多视角并行
   
   多视角并行是让多个 Worker 处理同一个输入，但每个 Worker 关注不同角度。
   
   例如代码审查：
   
   同一段代码
   → Bug 角度分析
   → 性能角度分析
   → 安全角度分析
   → 可维护性角度分析
   → 汇总
   
   这里每个 Worker 看到的是同一个输入，但分析目标不同。
   
   适合：
   
   1. 代码审查；
   2. 方案评估；
   3. 论文审稿；
   4. 风险分析；
   5. 多专家协作；
   6. Agent 输出自检。
   
   核心目标是：
   
   从多个维度提升结果质量和覆盖率。
   1.3 对比
   对比项	Sectioning	多视角并行
   输入	不同输入片段	同一个输入
   Worker 差异	处理对象不同	分析角度不同
   主要目标	提高速度、处理长输入	提升质量、覆盖更多维度
   典型例子	长文档分段总结	多专家代码审查
   Aggregator 重点	合并分片结果	去重、冲突处理、综合判断
   
   简单总结：
   
   Sectioning 是“切开处理”；
   多视角并行是“多人看同一件事”。
   
   
   2. 如何用 ThreadPoolExecutor 实现同步并行？
   
   ThreadPoolExecutor 是 Python 标准库里的线程池工具，适合执行 I/O 密集型任务。
   
   模型 HTTP 请求通常是 I/O 密集型，所以可以用线程池并行发起多个模型调用。
   
   基本示例：
   
   from concurrent.futures import ThreadPoolExecutor, as_completed
   
   
   def worker(name: str, user_input: str) -> str:
       return f"{name} 分析结果：{user_input}"
   
   
   def run_parallel(user_input: str) -> list[str]:
       tasks = [
           ("bug_checker", user_input),
           ("performance_checker", user_input),
           ("security_checker", user_input),
       ]
   
       results = []
   
       with ThreadPoolExecutor(max_workers=3) as executor:
           future_to_name = {
               executor.submit(worker, name, text): name
               for name, text in tasks
           }
   
           for future in as_completed(future_to_name):
               name = future_to_name[future]
   
               try:
                   result = future.result()
                   results.append(result)
               except Exception as exc:
                   results.append(f"{name} 执行失败：{exc}")
   
       return results
   
   核心点：
   
   1. ThreadPoolExecutor 创建线程池；
   2. submit 提交任务；
   3. as_completed 按完成顺序获取结果；
   4. future.result() 获取返回值；
   5. try/except 处理单个 Worker 失败。
   
   在模型调用场景中，每个 Worker 可以内部调用：
   
   llm.chat(...)
   
   注意：如果多个线程共用同一个 LLMClient，一般 HTTP 调用问题不大；但更稳妥的做法是每个 Worker 内部单独创建或传入线程安全的客户端配置。
   
   
   3. 如何用 asyncio 实现异步并行？
   
   asyncio 是 Python 的异步并发方案，适合大量 I/O 请求。
   
   如果你的模型客户端支持异步 HTTP，比如使用 httpx.AsyncClient，就可以用 asyncio.gather() 同时执行多个异步 Worker。
   
   示例结构：
   
   import asyncio
   
   
   async def worker(name: str, user_input: str) -> str:
       await asyncio.sleep(1)
       return f"{name} 分析结果：{user_input}"
   
   
   async def run_parallel(user_input: str) -> list[str]:
       results = await asyncio.gather(
           worker("bug_checker", user_input),
           worker("performance_checker", user_input),
           worker("security_checker", user_input),
           return_exceptions=True,
       )
   
       final_results = []
   
       for result in results:
           if isinstance(result, Exception):
               final_results.append(f"某个 Worker 执行失败：{result}")
           else:
               final_results.append(result)
   
       return final_results
   
   
   if __name__ == "__main__":
       output = asyncio.run(run_parallel("请审查这段代码"))
       print(output)
   
   核心点：
   
   1. async def 定义异步函数；
   2. await 等待异步操作；
   3. asyncio.gather 并发执行多个任务；
   4. return_exceptions=True 可以避免一个任务失败导致整体直接抛异常；
   5. asyncio.run 启动异步入口。
   
   
   4. 如何设计 Aggregator Prompt？
   
   Aggregator Prompt 的目标不是重新分析原始问题，而是汇总多个 Worker 的结果。
   
   一个好的 Aggregator Prompt 应该告诉模型：
   
   1. 原始任务是什么；
   2. 每个 Worker 的结果是什么；
   3. 需要合并哪些内容；
   4. 需要去重；
   5. 需要处理冲突；
   6. 需要输出什么格式；
   7. 不要编造 Worker 没有提到的信息。
   
   示例：
   
   你是一个结果汇总器。
   
   下面是多个 Worker 对同一个任务的分析结果。
   你的任务是对这些结果进行整合。
   
   要求：
   1. 合并重复观点；
   2. 保留重要发现；
   3. 如果多个 Worker 结论冲突，请明确指出；
   4. 不要编造 Worker 没有提到的信息；
   5. 按重要程度排序；
   6. 最终输出中文报告。
   
   原始任务：
   {user_input}
   
   Worker 结果：
   {worker_results}
   
   请输出：
   1. 总体结论
   2. 关键发现
   3. 风险点
   4. 冲突或不确定项
   5. 建议
   
   如果 Worker 输出是 JSON，可以让 Aggregator 输出更结构化：
   
   {
     "overall_summary": "...",
     "key_findings": [],
     "risks": [],
     "conflicts": [],
     "recommendations": []
   }
   
   Aggregator Prompt 的关键原则是：
   
   1. 只汇总已有结果；
   2. 不重新发挥；
   3. 不隐瞒冲突；
   4. 不制造不存在的结论；
   5. 输出结构要稳定。
   
   
   5. 如何处理结果冲突？
   
   并行 Worker 可能会产生冲突结论。
   
   例如：
   
   Worker A：这个方案风险较低。
   Worker B：这个方案存在较高安全风险。
   
   冲突不能直接忽略。
   
   常见处理方式有几种。
   
   5.1 显式标注冲突
   
   在最终结果中写明：
   
   存在冲突：
   - Worker A 认为风险较低；
   - Worker B 认为存在高安全风险；
   - 需要进一步确认输入校验和权限控制逻辑。
   
   这是最稳妥的做法。
   
   5.2 按专业 Worker 优先级处理
   
   如果不同 Worker 有不同专业领域，可以设定优先级。
   
   例如安全问题：
   
   security_checker 的安全风险判断优先级高于 general_checker。
   
   这样当通用 Worker 和安全 Worker 冲突时，优先采纳安全 Worker。
   
   5.3 按置信度处理
   
   如果 Worker 输出包含 confidence，可以优先采纳高置信度结论。
   
   例如：
   
   {
     "worker": "security_checker",
     "confidence": 0.91,
     "finding": "存在越权风险"
   }
   
   优先级高于：
   
   {
     "worker": "general_checker",
     "confidence": 0.55,
     "finding": "没有明显风险"
   }
   5.4 增加裁判步骤
   
   对于重要冲突，可以再调用一个 Judge / Critic Worker 进行裁决。
   
   流程：
   
   Worker A 结果
   Worker B 结果
   → Judge 判断哪个更合理
   → Aggregator 汇总
   
   这会增加一次模型调用，但可以提升复杂任务的可靠性。
   
   5.5 保守处理
   
   对于安全、数据删除、线上变更、代码执行等高风险任务，如果结果冲突，应该保守处理。
   
   例如：
   
   只要有一个 Worker 提到高风险，就在最终结果中保留该风险。
   
   总结原则：
   
   冲突不要隐藏；
   高风险冲突要保守；
   能标注不确定性就标注；
   必要时增加 Judge。
   
   
   6. 如何做并发限流和失败重试？
   
   并发限流和失败重试是 Parallelization 工程落地的关键。
   
   6.1 为什么需要并发限流？
   
   如果并发太高，会出现：
   
   1. API 限流；
   2. 请求超时；
   3. 服务压力过大；
   4. 失败率升高；
   5. token 消耗过快；
   6. 日志难以排查。
   
   所以要设置最大并发数。
   
   同步线程池中：
   
   ThreadPoolExecutor(max_workers=3)
   
   异步场景中可以用信号量：
   
   semaphore = asyncio.Semaphore(3)
   
   表示最多同时执行 3 个任务。
   
   6.2 如何设计失败重试？
   
   重试适合处理临时错误，例如：
   
   1. 网络抖动；
   2. 接口超时；
   3. 连接中断；
   4. 429 限流；
   5. 5xx 服务端错误。
   
   不适合无限重试。
   
   推荐策略：
   
   1. 最多重试 2 到 3 次；
   2. 每次重试前等待一小段时间；
   3. 可以使用指数退避；
   4. 最终失败要记录 error；
   5. 不要吞掉异常。
   
   简单同步重试示例：
   
   import time
   
   
   def run_with_retry(func, max_retries: int = 2, sleep_seconds: float = 1.0):
       last_error = None
   
       for attempt in range(max_retries + 1):
           try:
               return func()
           except Exception as exc:
               last_error = exc
   
               if attempt < max_retries:
                   time.sleep(sleep_seconds)
   
       raise RuntimeError(f"重试后仍然失败：{last_error}")
   6.3 工程建议
   
   推荐配置：
   
   max_workers = 3
   timeout = 60
   max_retries = 2
   allow_partial_success = True
   
   对于你当前学习 demo：
   
   max_workers 设为 3 就够；
   失败时记录错误；
   允许部分成功；
   Aggregator 汇总成功结果，并说明失败 Worker。
   
   对于真实业务：
   
   1. 高风险任务不要自动并行执行写操作。
   2. 失败样本加入 bad case；
   3. 日志中记录每个 Worker 的耗时和失败原因；
   
   
   7. 如何将 Parallelization 接入多 Agent 系统？
   
   Parallelization 很适合接入多 Agent 系统，因为每个 Worker 都可以是一个独立 Agent。
   
   例如：
   
   用户输入一段代码
   → bug_agent 并行分析 bug
   → security_agent 并行分析安全风险
   → performance_agent 并行分析性能
   → test_agent 并行分析测试覆盖
   → aggregator_agent 汇总最终报告
   
   这就是多 Agent 并行协作。
   
   7.1 多 Agent 并行架构
   
   可以抽象成：
   
   User Input
   → Coordinator
      → Agent A
      → Agent B
      → Agent C
      → Agent D
   → Aggregator Agent
   → Final Answer
   
   其中：
   
   Coordinator：负责发起并行任务；
   Worker Agents：负责不同子任务；
   Aggregator Agent：负责汇总结果。
   
   7.2 多 Agent 并行要注意什么？
   
   需要注意：
   
   1. 每个 Agent 职责要清楚；
   2. 每个 Agent 输出格式要统一；
   3. Coordinator 不要承担具体分析任务；
   4. Aggregator 要能处理重复和冲突；
   5. 并发数量要受控；
   6. 部分失败要可记录；
   7. 重要任务要保留中间结果，方便回放。
   
   总结来说：
   
   Parallelization 接入多 Agent 系统时，每个 Worker 可以升级为一个专家 Agent，Coordinator 负责任务分发，Aggregator 负责结果融合。
   ```

### 一句话总结

```
Parallelization 的本质是：把互不依赖的多个子任务同时执行，再由 Aggregator 汇总结果。
```

和前两节合起来看：

```
Prompt Chaining：按顺序做多个步骤
Routing：选择应该走哪条路径
Parallelization：多个独立步骤同时做
```

这三种模式是 Agent 编排的基础组合。



## Chapter 6 Planning

### 是什么

智能行为往往不只是对当前输入做出反应，还需要前瞻性：把复杂任务拆成更小、可管理的步骤，并规划如何达成目标。这正是规划（Planning）模式的作用所在。其核心在于，智能体或多智能体系统能够制定一系列行动，从初始状态走向目标状态。

Planning，规划模式，就是让 Agent 在真正执行任务前，先生成一个清晰的执行计划，然后按照计划逐步完成任务。

普通模型调用是：

```
用户输入 → 模型直接回答
```

Planning 模式是：

```
用户输入
→ 理解任务
→ 制定执行计划
→ 按步骤执行
→ 根据执行结果调整计划
→ 输出最终答案
```

它的核心思想是：

```
复杂任务不要直接开干，先想清楚要做哪些步骤、每一步依赖什么、是否需要工具、最后如何汇总。
```

可以把规划智能体看作一位能承接复杂目标的专家。当你让它「组织一次团队外出活动」时，你给出的是目标及其约束，而不是具体做法。智能体的核心任务，是自主`规划`**通往目标的路径**：先厘清`初始状态`（如预算、人数、意向日期）与`目标状态`（活动成功预订），再找出连接两者的`最优行动序列`。计划不是预先写死的，而是根据请求动态生成的。

这一过程的关键特征是适应性：初始计划只是起点，不是僵化剧本。智能体真正的能力，在于吸纳新信息并绕开障碍继续推进。例如，若首选场地不可用或所选餐饮已订满，一个有能力的智能体不会直接失败，而会记录新约束、重新评估选项，并给出新的计划，例如更换场地或调整日期。

但也必须看到`灵活性`与`可预测性`之间的**权衡**。可随情境调整的规划是专门手段，并非万能解。

- 当问题的解法已经`清楚`且`可重复`时，把智能体约束在预定的`固定工作流`中往往更有效：这样能减少不确定性和失控风险，从而得到更可靠、更一致的结果。
- 因此，究竟该用规划智能体还是简单任务执行智能体，归根结底取决于一个问题：「怎么做」`仍需探索`，还是`已经明确`？

### 为什么需要 Planning

前面几节已经学了：

```
Prompt Chaining：按固定步骤执行
Routing：选择处理路径
Parallelization：并行执行多个任务
Reflection：检查并修正结果
Tool Use：调用真实工具
```

但是这些模式都有一个前提：

```
系统已经知道下一步该做什么。
```

Planning 解决的是更高一层的问题：

```
面对一个复杂任务，Agent 应该如何自己拆解步骤？
```

例如用户说：

```
帮我分析这个项目的代码结构，找出潜在问题，并给出优化建议。
```

这个任务不能直接一次回答。Agent 需要先规划：

```
1. 读取项目目录结构
2. 识别核心模块
3. 分析入口文件
4. 分析依赖关系
5. 检查潜在问题
6. 汇总优化建议
```

这就是 Planning。

### 解决什么问题

Planning 主要解决复杂任务中的几个问题：

```
1. 任务太大，模型不知道从哪开始；
2. 多步骤任务容易遗漏；
3. 工具调用顺序不清晰；
4. 执行过程中无法追踪进度；
5. 任务失败后不知道回到哪一步；
6. 用户很难理解 Agent 正在做什么；
7. 后续无法做评估和日志回放。
```

没有 Planning 的 Agent 往往是：

```
想到哪做到哪。
```

有 Planning 的 Agent 是：

```
先拆任务，再执行，再检查。
```

这让 Agent 更像一个真正的工程执行系统。

### 核心流程

一个典型 Planning 流程是：

```
用户输入
→ Planner 生成计划
→ Executor 执行计划
→ Observer 记录执行结果
→ Replanner 必要时调整计划
→ Finalizer 汇总最终答案
```

可以简化为：

```
Task
→ Plan
→ Execute
→ Observe
→ Replan
→ Final Answer
```

其中几个角色很重要：

```
Planner：负责制定计划
Executor：负责执行步骤
Observer：负责观察执行结果
Replanner：负责根据失败或新信息调整计划
Finalizer：负责输出最终答案
```

### Planning 和  Prompt Chaining 的区别

Prompt Chaining 是提前设计好的固定流程，无论用户输入什么，都大致按这个固定链路走。

Planning 是 Agent 根据当前任务动态生成步骤。

例如用户问代码，就生成代码分析计划；用户问 Excel，就生成表格处理计划；用户问 RAG，就生成检索计划。

对比：

| 对比项   | Prompt Chaining | Planning         |
| -------- | --------------- | ---------------- |
| 步骤来源 | 开发者提前写死  | Agent 动态生成   |
| 适合任务 | 流程固定的任务  | 复杂、开放任务   |
| 灵活性   | 中等            | 高               |
| 可控性   | 高              | 需要约束         |
| 重点     | 按步骤执行      | 先决定做哪些步骤 |

可以简单理解：

```
Prompt Chaining：我已经知道步骤，让模型按步骤做。
Planning：我还不知道步骤，让模型先规划步骤。
```

### 常见形式

1. 一次性计划
   先生成完整计划，然后按照计划执行

   流程：

   ```
   用户任务
   → 生成完整计划
   → 按计划执行
   → 输出最终答案
   ```

   优点：

   ```
   简单
   容易实现
   适合学习 demo
   日志清晰
   ```

   缺点：

   ```
   计划一旦错了，后面可能都错
   执行中无法灵活调整
   ```

   适合：

   ```
   代码生成
   报告写作
   文档总结
   简单工具调用任务
   ```

2. ReAct 风格 Planning

   ReAct 可以理解为：

   ```
   Reason + Act
   ```

   也就是边想边做。

   流程：

   ```
   Thought：我下一步应该做什么
   Action：调用工具
   Observation：观察工具结果
   Thought：根据结果决定下一步
   Action：继续执行
   ...
   Final Answer：最终回答
   ```

   这种方式适合工具调用场景。

   例如：

   ```
   Thought：我需要先读取文件
   Action：read_file
   Observation：文件内容是...
   Thought：现在需要分析关键字段
   Action：analyze_columns
   Observation：字段包括...
   Final Answer：分析结果如下...
   ```

   这类模式非常接近真实 Agent。

3. Plan-and-Execute

   这是工程里很常见的形式：

   ```
   Planner 先生成计划
   Executor 再逐步执行
   ```

   Planner 和 Executor 可以是同一个模型，也可以是不同模块。

   结构：

   ```
   User Task
   → Planner
   → Plan
   → Executor
   → Step Results
   → Final Answer
   ```

   适合：

   ```
   多步骤工具调用
   复杂代码分析
   数据处理任务
   项目级分析
   ```

4. Replanning

   执行过程中如果发现计划不合适，就重新规划。

   例如：

   ```
   原计划：读取 data.xlsx
   执行结果：文件不存在
   重新规划：列出当前目录文件，寻找可用 Excel 文件
   ```

   流程：

   ```
   Plan
   → Execute Step
   → Observe Failure
   → Update Plan
   → Continue
   ```

   这对于真实 Agent 很重要，因为工具调用经常失败。

### 核心组成





## Part One 总结

Agent 不是一个单纯的聊天模型，而是一套“任务理解、路径选择、工具执行、结果检查、多角色协作”的工程系统。

### 模式总览

| 章节 | 模式                        | 核心问题                 | 一句话理解                       |
| ---- | --------------------------- | ------------------------ | -------------------------------- |
| 1    | Prompt Chaining             | 复杂任务如何分步骤完成   | 把大任务拆成多个连续小步骤       |
| 2    | Routing                     | 不同任务应该走哪条路径   | 先判断任务类型，再交给合适处理器 |
| 3    | Parallelization             | 多个独立任务如何同时执行 | 多个 Worker 并行做，最后汇总     |
| 4    | Reflection                  | 输出结果如何检查和修正   | 先生成，再审查，再修改           |
| 5    | Tool Use / Function Calling | Agent 如何调用真实能力   | 模型决策，程序执行工具           |
| 6    | Planning                    | 复杂任务执行前如何规划   | 先生成计划，再按计划执行         |
| 7    | Multi-Agent Collaboration   | 多个 Agent 如何协作      | 多个专家 Agent 分工合作          |

### 每一节的核心

1. Prompt Chaining 分步骤做
2. Routing 选择路径
3. Parallelization 并行执行，多个互不依赖的子任务可以同时执行，然后由 Aggregator 汇总
4. Reflection 检查与修正，解决第一次结果不够可靠怎么办
5. Tool Use/Function Calling 调用真实工具，模型负责判断要用什么工具，程序负责安全执行工具
6. Planning 先规划再执行，解决复杂任务应该怎么安排步骤
7. Mult-Agent Collaboration 多Agent 分工协作，解决多个 Agent 谁负责什么，以及如何协作 

### 七个模式之间的关系

这七个模式可以串成一个完整 Agent 工作流：

```
用户输入
→ Routing：判断任务类型
→ Planning：制定执行计划
→ Tool Use：调用真实工具
→ Prompt Chaining：组织多步骤流程
→ Parallelization：并行执行独立任务
→ Multi-Agent：分配给不同专家 Agent
→ Reflection：检查和修正最终结果
→ 输出答案
```

更具体一点：

```
Routing 负责选方向；
Planning 负责任务拆解；
Tool Use 负责真实执行；
Prompt Chaining 负责顺序编排；
Parallelization 负责并发加速；
Multi-Agent 负责角色分工；
Reflection 负责质量控制。
```

如果压缩成一句话：

```
Routing 选路，Planning 定步骤，Tool Use 做事，Prompt Chaining 串流程，Parallelization 提效率，Multi-Agent 做分工，Reflection 保质量。
```

### 对 Agent 工程的认识

1. Agent 不是一个大 Prompt
2. 模型不是执行者，程序才是
3. 复杂任务必须可观察
4. Agent 工程的核心不是更聪明，而是更可控























