# Part_One/C3_Parallelization/demo.py
import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path


# ============================================================
# 处理项目内模块导入
# ============================================================
# 当前文件路径：
# Part_One/C3_Parallelization/demo.py
#
# parents[2] 对应项目根目录：
# Agentic-Design-Patterns/
#
# 这样就可以正常导入 common.llm_client
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from common.llm_client import LLMClient


# ============================================================
# WorkerResult：统一每个并发 Worker 的输出格式
# ============================================================
# 并行化模式中，不同 Worker 最好输出统一结构。
# 这样 Aggregator 汇总时会更稳定，也方便后续记录日志、测试和排查问题。
# ============================================================


@dataclass
class WorkerResult:
    """
    单个 Worker 的执行结果。

    字段说明：
    - worker_name: Worker 名称
    - title: Worker 负责的任务标题
    - content: Worker 输出内容
    - success: 是否执行成功
    - elapsed_seconds: 执行耗时
    - error: 失败原因
    """

    worker_name: str
    title: str
    content: str
    success: bool
    elapsed_seconds: float
    error: str | None = None


# ============================================================
# 通用 Worker 执行函数
# ============================================================
# 当前 common.llm_client.LLMClient 是同步 requests 调用。
# 为了在 asyncio 中并发执行同步函数，这里使用 asyncio.to_thread。
#
# asyncio.to_thread 的作用：
# 把一个同步阻塞函数丢到线程中运行，避免阻塞整个事件循环。
# ============================================================


async def run_llm_worker(
    llm: LLMClient,
    worker_name: str,
    title: str,
    system_prompt: str,
    user_prompt: str,
) -> WorkerResult:
    """
    执行一个 LLM Worker。

    这个函数会调用一次模型，并把结果包装成 WorkerResult。
    """

    start_time = time.perf_counter()

    try:
        # llm.chat 是同步函数，所以用 asyncio.to_thread 包一层
        content = await asyncio.to_thread(
            llm.chat,
            user_prompt,
            system_prompt,
            0.2,   # temperature
            1024,  # max_tokens
        )

        elapsed = time.perf_counter() - start_time

        return WorkerResult(
            worker_name=worker_name,
            title=title,
            content=content,
            success=True,
            elapsed_seconds=elapsed,
            error=None,
        )

    except Exception as exc:
        elapsed = time.perf_counter() - start_time

        return WorkerResult(
            worker_name=worker_name,
            title=title,
            content="",
            success=False,
            elapsed_seconds=elapsed,
            error=str(exc),
        )


# ============================================================
# 三个可以并行执行的 Worker
# ============================================================
# 这三个任务之间没有强依赖关系：
#
# 1. 总结主题
# 2. 生成相关问题
# 3. 提取关键词
#
# 它们都只依赖同一个 topic，所以可以同时执行。
# ============================================================


async def summarize_worker(llm: LLMClient, topic: str) -> WorkerResult:
    """
    Worker 1：总结主题。
    """

    system_prompt = """
你是一个简洁的知识总结助手。
你的任务是对用户给出的主题进行简明总结。

要求：
1. 使用中文；
2. 控制在 150 字以内；
3. 只输出总结内容，不要输出额外解释。
"""

    user_prompt = f"""
请简要总结下面这个主题：

{topic}
"""

    return await run_llm_worker(
        llm=llm,
        worker_name="summarize_worker",
        title="主题总结",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


async def questions_worker(llm: LLMClient, topic: str) -> WorkerResult:
    """
    Worker 2：生成相关问题。
    """

    system_prompt = """
你是一个学习问题生成助手。
你的任务是围绕用户给出的主题，生成有助于深入学习的问题。

要求：
1. 使用中文；
2. 生成 3 个问题；
3. 每个问题要具体、有启发性；
4. 不要回答问题，只输出问题列表。
"""

    user_prompt = f"""
请围绕下面这个主题生成 3 个值得思考的问题：

{topic}
"""

    return await run_llm_worker(
        llm=llm,
        worker_name="questions_worker",
        title="相关问题",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


async def key_terms_worker(llm: LLMClient, topic: str) -> WorkerResult:
    """
    Worker 3：提取关键词。
    """

    system_prompt = """
你是一个关键词提取助手。
你的任务是从用户给出的主题中提取关键术语。

要求：
1. 使用中文；
2. 提取 5 到 10 个关键词；
3. 用逗号分隔；
4. 不要输出额外解释。
"""

    user_prompt = f"""
请从下面这个主题中提取关键术语：

{topic}
"""

    return await run_llm_worker(
        llm=llm,
        worker_name="key_terms_worker",
        title="关键术语",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


# ============================================================
# Aggregator：汇总多个并发 Worker 的结果
# ============================================================
# Aggregator 的职责：
# 1. 收集多个 Worker 输出；
# 2. 合并信息；
# 3. 去除重复；
# 4. 整理成最终答案；
# 5. 不编造 Worker 没有提供的信息。
# ============================================================


def format_worker_results(results: list[WorkerResult]) -> str:
    """
    将 WorkerResult 列表格式化为可传给 Aggregator 的文本。
    """

    blocks: list[str] = []

    for result in results:
        if result.success:
            blocks.append(
                f"""
【{result.title}】
Worker: {result.worker_name}
耗时: {result.elapsed_seconds:.2f} 秒
内容:
{result.content}
""".strip()
            )
        else:
            blocks.append(
                f"""
【{result.title}】
Worker: {result.worker_name}
耗时: {result.elapsed_seconds:.2f} 秒
状态: 执行失败
错误:
{result.error}
""".strip()
            )

    return "\n\n".join(blocks)


async def aggregate_results(
    llm: LLMClient,
    topic: str,
    results: list[WorkerResult],
) -> str:
    """
    使用 Aggregator 汇总多个 Worker 的结果。
    """

    success_results = [result for result in results if result.success]
    failed_results = [result for result in results if not result.success]

    if not success_results:
        return "所有并发 Worker 都执行失败，无法生成最终汇总。"

    worker_results_text = format_worker_results(results)

    system_prompt = """
你是一个并行任务结果汇总器 Aggregator。

下面会给你多个 Worker 对同一个主题的并行处理结果。
你的任务是整合这些结果，生成一个完整、清晰的中文回答。

要求：
1. 合并重复内容；
2. 保留每个 Worker 的关键信息；
3. 如果有 Worker 执行失败，要在最后简要说明；
4. 不要编造 Worker 没有提供的信息；
5. 输出结构清晰，适合学习笔记。
"""

    user_prompt = f"""
原始主题：
{topic}

并行 Worker 结果：
{worker_results_text}

请输出以下结构：

## 1. 主题概述

## 2. 关键术语

## 3. 值得继续思考的问题

## 4. 汇总说明
"""

    final_answer = await asyncio.to_thread(
        llm.chat,
        user_prompt,
        system_prompt,
        0.2,   # temperature
        1500,  # max_tokens
    )

    if failed_results:
        failed_names = ", ".join(result.worker_name for result in failed_results)
        final_answer += f"\n\n注意：以下 Worker 执行失败，汇总结果可能不完整：{failed_names}"

    return final_answer


# ============================================================
# 主流程：并行执行多个 Worker，然后汇总
# ============================================================


async def run_parallel_example(topic: str) -> None:
    """
    执行 Parallelization 示例。

    流程：
    1. 创建 LLMClient；
    2. 并发执行三个 Worker；
    3. 打印每个 Worker 的中间结果；
    4. 调用 Aggregator 汇总；
    5. 打印最终结果。
    """

    llm = LLMClient()

    print(f"\n========== Parallelization 示例 ==========")
    print(f"主题：{topic}")

    start_time = time.perf_counter()

    # 并发执行多个相互独立的 Worker
    results = await asyncio.gather(
        summarize_worker(llm, topic),
        questions_worker(llm, topic),
        key_terms_worker(llm, topic),
    )

    parallel_elapsed = time.perf_counter() - start_time

    print("\n========== 并行 Worker 执行结果 ==========")

    for result in results:
        print(f"\n--- {result.title} / {result.worker_name} ---")
        print(f"成功: {result.success}")
        print(f"耗时: {result.elapsed_seconds:.2f} 秒")

        if result.success:
            print(result.content)
        else:
            print(f"错误: {result.error}")

    print(f"\n并行阶段总耗时: {parallel_elapsed:.2f} 秒")

    print("\n========== Aggregator 汇总结果 ==========")

    final_answer = await aggregate_results(
        llm=llm,
        topic=topic,
        results=results,
    )

    total_elapsed = time.perf_counter() - start_time

    print(final_answer)

    print(f"\n总耗时: {total_elapsed:.2f} 秒")


if __name__ == "__main__":
    test_topic = "The history of space exploration"

    asyncio.run(run_parallel_example(test_topic))
