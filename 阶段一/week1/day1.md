# 第一天：Event Loop、Coroutine、Task、`await` 与 `create_task()`

今天先建立一个核心心智模型：

> `async def` 定义可暂停的执行流程；调用后得到协程对象；Task 把协程交给事件循环调度；`await` 决定当前执行流什么时候等待、什么时候可能把控制权交还事件循环。

---

## 一、Event Loop（事件循环）

### 1. 为什么需要

普通同步程序执行到网络请求、磁盘读取、模型 API 调用时，当前线程会一直等待。

Agent 系统中常见的耗时操作包括：

- 调用大模型接口；
- 调用多个工具；
- 查询数据库；
- RAG（检索增强生成）召回；
- 向客户端发送流式事件。

这些操作大部分时间不是在使用 CPU，而是在等待外部资源。事件循环允许当前任务等待时，先运行其他可以推进的任务。

---

### 2. 核心概念

事件循环可以暂时理解为一个不断执行以下步骤的调度器：

1. 找到当前可以运行的任务；
2. 让其中一个任务继续运行；
3. 任务运行到需要等待的地方；
4. 挂起该任务；
5. 执行其他任务或等待 I/O 就绪；
6. 等待条件满足后，把原任务放回可运行队列。

事件循环是 `asyncio` 应用的核心，负责运行 Task、执行回调、处理网络 I/O 等操作。通常应用层使用 `asyncio.run()` 管理事件循环，而不是手动创建和关闭它。citeturn221278view1

---

### 3. 内部执行流程

执行：

```python
asyncio.run(main())
```

可以先简化理解为：

```text
创建事件循环
    ↓
将 main() 包装为主 Task
    ↓
事件循环开始调度主 Task
    ↓
主 Task 遇到需要等待的 await
    ↓
主 Task 挂起，事件循环运行其他 Task
    ↓
main() 执行结束
    ↓
清理资源并关闭事件循环
```

在一个事件循环线程中，同一时刻通常只有一个 Task 正在执行 Python 代码。它依赖 Cooperative Scheduling（协作式调度）：任务主动运行到可挂起的等待点，事件循环才能调度其他任务。citeturn221278view0turn221278view3

因此：

> 异步并发不是多个 Task 同时执行 Python 指令，而是多个 Task 在等待期间交替推进。

---

### 4. 最小示例

```python
import asyncio


async def main() -> None:
    loop = asyncio.get_running_loop()
    print(f"事件循环：{loop!r}")
    print("main 开始")

    await asyncio.sleep(0.1)

    print("main 恢复")
    print("main 结束")


if __name__ == "__main__":
    asyncio.run(main())
```

`get_running_loop()` 只能在已经运行的事件循环中调用；没有运行中的事件循环时会抛出 `RuntimeError`。citeturn221278view1

---

### 5. 常见错误

#### 错误一：把异步理解成多线程

默认情况下，一个事件循环通常运行在一个线程中。

```text
异步并发 ≠ 多线程并行
```

异步适合大量 I/O 等待，不会自动让 CPU 密集型代码并行。

#### 错误二：认为事件循环会随时抢占任务

事件循环不是操作系统那种强制抢占调度。

以下代码在循环执行结束前不会主动让出控制权：

```python
async def bad_task() -> None:
    for _ in range(100_000_000):
        pass
```

即使函数使用了 `async def`，内部没有真正的等待点，仍然可能长期占用事件循环。

#### 错误三：在已有事件循环中再次调用 `asyncio.run()`

FastAPI、Jupyter 和部分 GUI 环境已经存在事件循环，内部再次调用 `asyncio.run()` 通常会报错：

```text
RuntimeError: asyncio.run() cannot be called from a running event loop
```

---

### 6. 设计权衡

事件循环的优势：

- 单线程可以管理大量 I/O 操作；
- Task 切换成本通常低于线程切换；
- 适合模型调用、数据库访问和网络流式传输。

代价：

- 一个阻塞操作可能拖住整个事件循环；
- Task 生命周期、异常和取消需要明确管理；
- 调试执行顺序比同步程序更复杂。

---

### 7. 在 LocalAgent 中如何使用

在 FastAPI 后端中，可以把一次请求粗略理解为一个正在事件循环中执行的 Task：

```text
请求 Task
 ├─ await Router
 ├─ await Planner
 ├─ await 模型调用
 ├─ await 工具执行
 └─ await SSE 输出
```

Router（路由器）结果是 Planner（规划器）的输入时，它们存在依赖关系，应当顺序 `await`。

两个互不依赖的模型分析任务，才可能创建为两个独立 Task 并发执行。

---

### 8. 面试关注点

面试时需要明确：

- 事件循环通常运行在一个线程中；
- Task 使用协作式调度；
- `async def` 不代表代码自动并发；
- 只有任务运行到实际挂起点，其他 Task 才有运行机会；
- 异步主要提高 I/O 等待期间的资源利用率。

---

## 二、Coroutine（协程）与协程对象

### 1. 为什么需要

普通函数只能持续执行到返回或抛出异常。

协程则可以：

```text
开始执行 → 暂停 → 保存状态 → 恢复执行 → 返回结果
```

这让一个函数可以在等待网络、数据库或定时器时暂停，而不阻塞整个线程。

---

### 2. 核心概念

使用 `async def` 定义的是 Coroutine Function（协程函数）：

```python
async def fetch_data() -> str:
    return "result"
```

调用它：

```python
coro = fetch_data()
```

得到的是 Coroutine Object（协程对象），而不是字符串 `"result"`。

Python 官方数据模型明确区分：

- 协程函数：使用 `async def` 定义；
- 协程对象：调用协程函数后产生的对象。citeturn221278view2turn221278view0

---

### 3. 内部执行流程

执行：

```python
coro = fetch_data()
```

大致发生的是：

```text
创建协程对象
保存：
    - 要执行的函数
    - 局部变量状态
    - 当前执行位置
但不执行函数体
```

只有以下操作之一发生，协程才会被推进：

```python
await coro
```

或者：

```python
asyncio.create_task(coro)
```

单纯调用协程函数不会执行函数体，还可能产生“coroutine was never awaited”警告。citeturn221278view0

---

### 4. 最小示例

```python
import asyncio
import inspect


async def model_call() -> str:
    print("model_call 开始执行")
    await asyncio.sleep(0.1)
    print("model_call 执行结束")
    return "模型结果"


async def main() -> None:
    coroutine_object = model_call()

    print(f"对象类型：{type(coroutine_object)}")
    print(f"是否为协程对象：{inspect.iscoroutine(coroutine_object)}")
    print("此时 model_call 的函数体还没有执行")

    result = await coroutine_object
    print(f"结果：{result}")


if __name__ == "__main__":
    asyncio.run(main())
```

预期顺序：

```text
对象类型：...
是否为协程对象：True
此时 model_call 的函数体还没有执行
model_call 开始执行
model_call 执行结束
结果：模型结果
```

---

### 5. 常见错误

#### 错误一：忘记 `await`

```python
async def main() -> None:
    result = model_call()
    print(result)
```

这里的 `result` 是协程对象，不是模型结果。

#### 错误二：重复等待同一个协程对象

```python
coro = model_call()

result1 = await coro
result2 = await coro  # 错误
```

协程对象通常只能完整执行一次。第二次等待会出现类似错误：

```text
RuntimeError: cannot reuse already awaited coroutine
```

需要再次执行时，应重新调用协程函数：

```python
result1 = await model_call()
result2 = await model_call()
```

#### 错误三：把协程对象长期保存，却没有明确执行者

```python
self.pending_call = model_call()
```

此时只是保存了一个还没运行的协程对象。更合理的设计通常是：

- 保存调用参数；
- 在需要时调用协程函数；
- 或明确创建并保存 Task。

---

### 6. 设计权衡

协程对象很轻量，但它本身不负责：

- 调度；
- 生命周期管理；
- 取消；
- 记录执行状态；
- 并发运行。

这些职责通常由 Task 承担。

---

### 7. 在 LocalAgent 中如何使用

例如模型客户端：

```python
async def chat(self, prompt: str) -> str:
    ...
```

调用：

```python
coro = client.chat(prompt)
```

只生成了调用计划。

执行：

```python
result = await client.chat(prompt)
```

才真正发起请求。

因此在排查“为什么模型接口没有被调用”时，需要先确认代码是不是只创建了协程对象，却没有 `await` 或创建 Task。

---

### 8. 面试关注点

常见追问：

> 调用一个 `async def` 函数后，函数体是否立即运行？

不会。调用只产生协程对象。

> 协程对象和 Task 有什么区别？

协程对象描述一段可暂停的执行流程；Task 把协程包装成可以被事件循环独立调度、等待、取消和获取结果的对象。

---

## 三、`await`

### 1. 为什么需要

`await` 有两个核心作用：

1. 等待一个 Awaitable（可等待对象）的结果；
2. 当等待对象尚未完成时，允许当前 Task 挂起。

常见可等待对象包括：

- 协程对象；
- Task；
- Future（未来对象）。

---

### 2. 核心概念

很多人会把 `await` 简化成：

> `await` 就是让出事件循环。

这个说法不够准确。

更准确的是：

> `await` 请求推进一个可等待对象；只有这个对象当前无法立即完成时，当前 Task 才会真正挂起。

例如：

```python
async def immediate() -> int:
    return 1
```

执行：

```python
value = await immediate()
```

可能直接完成，中间没有明显调度其他 Task 的机会。

而：

```python
await asyncio.sleep(1)
```

当前 Task 会等待定时器，事件循环可以运行其他 Task。

---

### 3. 直接 `await` 协程的内部流程

```python
result = await child()
```

不是创建一个新的 Task。

可以近似理解为：

```text
当前 Task 执行 main()
    ↓
进入 child() 协程
    ↓
child() 在当前 Task 的调用链中运行
    ↓
child() 遇到未完成的等待对象
    ↓
当前 Task 整体挂起
    ↓
等待完成后恢复 child()
    ↓
child() 返回
    ↓
main() 继续
```

因此：

```python
await task_a()
await task_b()
```

通常是串行关系：

```text
task_a 完整结束
    ↓
task_b 才开始
```

但需要注意：`task_a` 等待 I/O 时，事件循环仍然可以运行此前已经存在的其他 Task。

---

### 4. 最小示例：直接 `await` 是串行的

```python
import asyncio
import logging
import time


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def simulated_model_call(name: str, delay: float) -> str:
    logger.info("%s：开始", name)
    await asyncio.sleep(delay)
    logger.info("%s：恢复并结束", name)
    return f"{name}-result"


async def main() -> None:
    started_at = time.perf_counter()

    result_a = await simulated_model_call("model-a", 1.0)
    result_b = await simulated_model_call("model-b", 1.0)

    elapsed = time.perf_counter() - started_at

    logger.info("结果：%s, %s", result_a, result_b)
    logger.info("总耗时：%.2f 秒", elapsed)


if __name__ == "__main__":
    asyncio.run(main())
```

总耗时约为两次等待时间之和：

```text
约 2 秒
```

---

### 5. 常见错误

#### 错误一：以为连续 `await` 会自动并发

```python
result_a = await call_a()
result_b = await call_b()
```

这通常是串行执行。

#### 错误二：看到 `await` 就认为一定切换了 Task

如果等待对象已经完成，或者协程在返回前没有遇到实际挂起点，可能不会发生事件循环切换。

#### 错误三：为了“异步”而给所有函数加 `async`

以下函数没有异步等待，没有必要使用 `async def`：

```python
async def add(a: int, b: int) -> int:
    return a + b
```

这会让调用端必须额外 `await`，但没有获得异步收益。

---

### 6. 设计权衡

直接 `await` 的优点：

- 控制流清晰；
- 异常直接向调用者传播；
- 生命周期明确；
- 不容易遗漏结果。

缺点：

- 对互不依赖的慢操作使用连续 `await`，会导致不必要的串行等待。

---

### 7. 在 LocalAgent 中如何使用

适合直接 `await` 的场景：

```text
Router 结果 → 决定 Planner 输入
Planner 结果 → 决定工具参数
工具结果 → 决定最终回答
```

这些步骤存在数据依赖，不应盲目并发。

例如：

```python
route = await router.route(user_message)
plan = await planner.create_plan(route)
tool_result = await tool_executor.execute(plan)
```

这是正确的串行链路，不应该为了追求并发全部改成 Task。

---

### 8. 面试关注点

重点回答：

> `await` 是否一定会让出事件循环？

不一定。只有等待对象没有立即完成、当前 Task 需要挂起时，事件循环才有机会调度其他任务。

> `await coroutine()` 是否会创建新 Task？

不会。协程通常在当前 Task 的调用链中执行。

---

## 四、Task（任务）与 `asyncio.create_task()`

### 1. 为什么需要

直接 `await` 一个协程时，当前执行流要等它完成后才能继续。

当两个操作互不依赖时：

```text
模型 A 分析代码质量
模型 B 分析安全风险
```

可以把它们包装成两个独立 Task，让事件循环交替推进。

---

### 2. 核心概念

Task 是对协程的包装，它会：

- 把协程注册到事件循环；
- 保存运行状态；
- 保存返回结果；
- 保存抛出的异常；
- 支持等待和取消；
- 允许协程作为独立调度单元运行。

`asyncio.create_task()` 会包装协程并将其安排到事件循环中运行，然后立即返回 Task 对象。citeturn221278view0turn221278view4

Task 常见状态可以简化为：

```text
PENDING
   ↓
RUNNING
   ↓
等待 I/O，再次 PENDING
   ↓
RUNNING
   ↓
FINISHED / CANCELLED
```

---

### 3. Task 什么时候开始运行

以你当前 Python 3.12 默认 Task Factory（任务工厂）为准：

```python
task = asyncio.create_task(worker())
```

会立即创建并调度 Task，但通常不会在 `create_task()` 调用内部直接执行完整的 `worker()`。

当前 Task 会继续运行，直到：

- 遇到真正挂起的 `await`；
- 当前协程返回；
- 显式让出执行机会。

例如：

```python
task = asyncio.create_task(worker())

print("create_task 之后")
await asyncio.sleep(0)
```

通常输出顺序为：

```text
create_task 之后
worker 开始
```

因为 `await asyncio.sleep(0)` 提供了一次显式调度机会。

Python 新版本支持 Eager Task（急切任务）相关机制，可能改变“创建时是否立即执行到首次阻塞”的行为；第一天先以默认任务工厂为准。Python 3.14 的接口已经明确提供了相关的 `eager_start` 控制。citeturn221278view0

---

### 4. 最小示例：创建 Task 后并发执行

```python
import asyncio
import logging
import time


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def simulated_model_call(name: str, delay: float) -> str:
    current_task = asyncio.current_task()
    task_name = current_task.get_name() if current_task else "unknown"

    logger.info("%s：开始，所在 Task=%s", name, task_name)

    try:
        logger.info("%s：准备等待 I/O", name)
        await asyncio.sleep(delay)
        logger.info("%s：I/O 完成，恢复执行", name)
        return f"{name}-result"
    except asyncio.CancelledError:
        logger.warning("%s：任务被取消", name)
        raise
    finally:
        logger.info("%s：执行 finally", name)


async def run_concurrently() -> None:
    started_at = time.perf_counter()

    task_a: asyncio.Task[str] = asyncio.create_task(
        simulated_model_call("model-a", 1.0),
        name="model-a-task",
    )
    task_b: asyncio.Task[str] = asyncio.create_task(
        simulated_model_call("model-b", 1.0),
        name="model-b-task",
    )

    logger.info("两个 Task 已创建")
    logger.info("task_a.done()=%s", task_a.done())
    logger.info("task_b.done()=%s", task_b.done())

    # 此处还不使用 gather，保持第一天范围。
    result_a = await task_a
    result_b = await task_b

    elapsed = time.perf_counter() - started_at

    logger.info("结果：%s, %s", result_a, result_b)
    logger.info("总耗时：%.2f 秒", elapsed)


if __name__ == "__main__":
    asyncio.run(run_concurrently())
```

虽然代码先写：

```python
result_a = await task_a
```

但 `task_b` 已经被创建并调度。当 `task_a` 等待时，`task_b` 也可以继续推进。

总耗时通常接近：

```text
max(1 秒, 1 秒) ≈ 1 秒
```

而不是两者之和。

---

### 5. `await coroutine` 与 `create_task` 的本质区别

#### 直接等待协程

```python
result = await worker()
```

结构：

```text
当前 Task
  └─ worker 协程
```

没有新 Task。

#### 创建 Task

```python
task = asyncio.create_task(worker())
result = await task
```

结构：

```text
当前 Task
另一个 worker Task
```

worker 获得独立的 Task 状态和调度身份。

---

### 6. 一个容易写出的无效模式

```python
result = await asyncio.create_task(worker())
```

这不是错误，但多数简单场景没有价值。

你创建了一个独立 Task，却马上等待它：

```text
创建 Task
    ↓
当前 Task 立刻等待
    ↓
没有安排其他独立工作
```

除非需要：

- 显式的 Task 身份；
- 单独取消；
- 任务命名和追踪；
- 与已经存在的其他 Task 形成调度边界；

否则直接写：

```python
result = await worker()
```

通常更清楚。

---

### 7. Task 引用丢失问题

不要随意写真正的 Fire-and-Forget（触发后不等待）：

```python
asyncio.create_task(background_job())
```

事件循环只保留 Task 的弱引用；如果程序其他位置没有保存 Task，它可能在完成前被垃圾回收。因此官方建议保存强引用。citeturn221278view0turn221278view4

可以维护一个后台任务集合：

```python
import asyncio
from collections.abc import Coroutine
from typing import Any


background_tasks: set[asyncio.Task[Any]] = set()


def start_background_task(
    coroutine: Coroutine[Any, Any, Any],
) -> asyncio.Task[Any]:
    task = asyncio.create_task(coroutine)
    background_tasks.add(task)

    task.add_done_callback(background_tasks.discard)
    return task
```

但注意：

> 保存引用只解决 Task 生命周期问题，不等于已经正确处理 Task 异常。

如果后台 Task 抛出异常，却没有人 `await` 或读取异常，可能出现：

```text
Task exception was never retrieved
```

生产代码还需要统一记录后台任务异常。

---

### 8. 常见错误

#### 错误一：创建了 Task，但主协程立即结束

```python
async def main() -> None:
    asyncio.create_task(long_running_job())
```

`main()` 很快结束，`asyncio.run()` 开始关闭事件循环，后台 Task 通常没有机会正常完成。

#### 错误二：创建 Task 后不保存、不等待、不处理异常

```python
asyncio.create_task(model_call())
```

这会让任务所有权不清晰。

#### 错误三：创建 Task 后仍然串行

```python
task_a = asyncio.create_task(call_a())
result_a = await task_a

task_b = asyncio.create_task(call_b())
result_b = await task_b
```

`task_b` 在 `task_a` 完成后才创建，仍然接近串行。

正确思路是先创建全部独立任务：

```python
task_a = asyncio.create_task(call_a())
task_b = asyncio.create_task(call_b())

result_a = await task_a
result_b = await task_b
```

#### 错误四：把存在依赖的任务强行并发

```python
route_task = asyncio.create_task(router.route(message))
plan_task = asyncio.create_task(planner.plan(route))
```

此时 `route` 还不存在，说明两个任务不独立，不能直接并发。

---

### 9. 设计权衡

| 方式                | 适用场景           | 优点             | 风险                         |
| ------------------- | ------------------ | ---------------- | ---------------------------- |
| `await coroutine()` | 有顺序依赖         | 简单、异常链清晰 | 独立 I/O 会被串行化          |
| `create_task()`     | 任务相互独立       | 可以并发推进     | 需要管理生命周期、异常和取消 |
| 创建后立即 `await`  | 需要独立 Task 身份 | 可命名、可取消   | 很多场景只是增加复杂度       |
| 后台 Task           | 独立长期任务       | 不阻塞主流程     | 容易丢失异常和生命周期       |

---

### 10. 在 LocalAgent 中如何使用

#### 适合直接 `await`

```python
route = await router.route(message)
plan = await planner.plan(route)
```

因为 Planner 依赖 Router。

#### 适合创建 Task

```python
code_review_task = asyncio.create_task(
    code_agent.review(code),
    name="code-review",
)

security_review_task = asyncio.create_task(
    security_agent.review(code),
    name="security-review",
)

code_result = await code_review_task
security_result = await security_review_task
```

两项分析相互独立，可以并发。

不过生产级 LocalAgent 不应该到处散落裸 `create_task()`。第三天学习 Structured Concurrency（结构化并发）后，会使用更清晰的 TaskGroup（任务组）管理任务归属。

---

## 五、今天必须形成的执行模型

观察下面代码：

```python
async def worker(name: str) -> None:
    print(name, "start")
    await asyncio.sleep(1)
    print(name, "end")


async def main() -> None:
    print("main-1")

    task = asyncio.create_task(worker("A"))

    print("main-2")

    await asyncio.sleep(0)

    print("main-3")

    await task

    print("main-4")
```

在默认调度模式下，应当理解为：

```text
事件循环运行 main Task
    ↓
打印 main-1
    ↓
创建 A Task，将 A 加入待运行队列
    ↓
main Task 继续执行
    ↓
打印 main-2
    ↓
main 遇到 sleep(0)，让出控制权
    ↓
事件循环运行 A Task
    ↓
A 打印 start
    ↓
A 等待 sleep(1)，被挂起
    ↓
事件循环恢复 main
    ↓
打印 main-3
    ↓
main 等待 A Task
    ↓
约 1 秒后 A 恢复
    ↓
打印 A end，A 完成
    ↓
main 被重新调度
    ↓
打印 main-4
```

这比死记 `create_task()` API 更重要。

---

# 当天最小实践任务

## 实验目录

```text
asyncio_week1/
└─ day01_event_loop_task/
   ├─ demo.py
   ├─ observations.md
   └─ test_demo.py
```

今天不修改 LocalAgent。

---

## 任务一：实现统一模拟函数

编写：

```python
async def simulated_io(name: str, delay: float) -> str:
    ...
```

必须记录：

- Task 名称；
- 开始时间；
- 进入等待前；
- 等待恢复后；
- 函数结束；
- `finally` 执行。

---

## 任务二：实现三组对比实验

### 实验 A：只创建协程对象

```python
coro = simulated_io("A", 0.5)
```

验证函数体没有执行。

实验结束时需要正确关闭未执行的协程对象：

```python
coro.close()
```

否则会产生未等待协程警告。

### 实验 B：连续直接 `await`

```python
result_a = await simulated_io("A", 0.5)
result_b = await simulated_io("B", 0.5)
```

记录总耗时，预期接近 1 秒。

### 实验 C：先创建两个 Task，再分别等待

```python
task_a = asyncio.create_task(...)
task_b = asyncio.create_task(...)

result_a = await task_a
result_b = await task_b
```

记录总耗时，预期接近 0.5 秒。

今天禁止使用 `gather()`，确保你真正理解 Task 是如何产生并发的。

---

## 任务三：观察 Task 什么时候开始

依次打印：

```python
print("before create_task")
task = asyncio.create_task(...)
print("after create_task")

await asyncio.sleep(0)

print("after yield")
await task
```

在 `observations.md` 中回答：

1. `create_task()` 返回时，子 Task 是否已经完成？
2. 子 Task 第一次执行发生在什么位置之后？
3. 删除 `await asyncio.sleep(0)` 后，执行顺序是否变化？
4. 把 `await task` 放到创建后第一行，执行顺序如何变化？

---

## 任务四：验证连续 `await` 不等于并发

至少使用 `time.perf_counter()` 记录：

```text
直接 await 总耗时
create_task 总耗时
```

不要只看日志顺序，要用耗时证明。

测试断言不要写得过于严格，避免机器调度波动：

```python
assert serial_elapsed >= 0.9
assert concurrent_elapsed < 0.8
```

建议每个模拟等待设为 `0.5` 秒。

---

# 当天知识总结

1. `async def` 定义协程函数，调用后只产生协程对象。
2. 协程对象不会自动执行，必须被 `await` 或包装为 Task。
3. 事件循环负责调度 Task 和处理异步 I/O。
4. 一个事件循环线程中，同一时刻通常只有一个 Task 执行 Python 代码。
5. `await coroutine()` 不会创建新 Task。
6. 连续直接 `await` 通常形成串行依赖。
7. `create_task()` 将协程包装成独立调度的 Task。
8. Task 被创建后只是进入调度状态，默认情况下当前 Task 要先让出控制权，子 Task 才能执行。
9. 并发任务应当先全部创建，再分别等待。
10. Task 必须有人保存、等待、取消或处理异常。

---

# 面试题

### 1. 调用 `async def` 函数时，函数体会立即执行吗？

不会。调用只会创建协程对象；只有被等待或调度后，函数体才开始执行。

### 2. `await func_a(); await func_b()` 是否并发？

通常不是。`func_b` 会在 `func_a` 返回后才开始。要并发，需要先把独立协程调度为不同 Task。

### 3. `await` 是否一定会切换到其他 Task？

不一定。等待对象可以立即完成时，当前 Task 可能继续执行；只有当前 Task 真正挂起时，事件循环才会运行其他任务。

### 4. `asyncio.create_task()` 调用后，Task 是否立刻执行？

它会立即创建并调度 Task，但在默认非急切执行模式下，当前 Task 通常会继续运行，直到它让出事件循环后，新 Task 才获得执行机会。

### 5. Coroutine 和 Task 的区别是什么？

Coroutine 是一段可暂停的执行流程；Task 是协程在事件循环中的独立调度和状态管理对象，能够保存结果、异常以及取消状态。

---

# 验收清单

- [ ] 能解释事件循环为什么适合 I/O 密集型任务。
- [ ] 能区分协程函数、协程对象和 Task。
- [ ] 能解释调用 `async def` 为什么不会立即执行函数体。
- [ ] 能解释直接 `await` 为什么通常是串行。
- [ ] 能解释 Task 在什么时候获得执行机会。
- [ ] 能通过日志还原任务开始、暂停、恢复和结束过程。
- [ ] 能通过耗时证明串行与并发的区别。
- [ ] 没有出现 `coroutine was never awaited`。
- [ ] 没有出现 `Task exception was never retrieved`。
- [ ] 代码具备类型标注、结构化日志和明确的 Task 名称。

---

# 第二天预告

第二天进入 `asyncio.gather()`：

- 如何一次等待多个并发任务；
- 为什么结果顺序不等于完成顺序；
- 一个任务失败后其他任务到底会怎样；
- `return_exceptions=True` 为什么容易被误用；
- 如何表示“部分成功、部分失败”。