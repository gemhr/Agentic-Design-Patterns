#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Part_One/C5_Tool_Use/demo2.py

import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# ============================================================
# 处理项目内模块导入
# ============================================================
# 当前文件路径：
# Part_One/C5_Tool_Use/demo2.py
#
# parents[2] 对应项目根目录：
# Agentic-Design-Patterns/
#
# 这样就可以正常导入 common.llm_client
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from common.llm_client import AsyncLLMClient


# ============================================================
# 数据结构：工具调用请求与工具执行结果
# ============================================================


@dataclass
class ToolCallRequest:
    """
    模型生成的工具调用请求。

    字段说明：
    - action: 动作类型，tool_call 或 final_answer
    - tool_name: 工具名称
    - arguments: 工具参数
    - final_answer: 如果模型认为不需要工具，可以直接给最终答案
    """

    action: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    final_answer: str | None = None


@dataclass
class ToolResult:
    """
    工具执行结果。

    字段说明：
    - tool_name: 工具名称
    - success: 是否执行成功
    - result: 工具返回结果
    - error: 错误信息
    - elapsed_seconds: 工具执行耗时
    """

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    elapsed_seconds: float = 0.0


# ============================================================
# 工具定义：模拟 search_information 工具
# ============================================================
# 注意：
# 这个工具不访问公网，只使用本地字典模拟搜索结果。
# 这样符合公司内网数据不得出网的学习环境。
# ============================================================


def search_information(query: str) -> str:
    """
    模拟信息搜索工具。

    适用场景：
    - 查询简单事实；
    - 查询天气、首都、人口、常识类问题；
    - 演示 Tool Use / Function Calling 流程。

    参数：
    - query: 查询关键词。
    """

    print(f"\n--- 工具被调用：search_information(query={query!r}) ---")

    simulated_results = {
        "weather in london": "The weather in London is currently cloudy with a temperature of 15°C.",
        "capital of france": "The capital of France is Paris.",
        "population of earth": "The estimated population of Earth is around 8 billion people.",
        "tallest mountain": "Mount Everest is the tallest mountain above sea level.",
        "dogs": "Dogs are domesticated mammals known for loyalty, social behavior, and strong cooperation with humans.",
        "default": f"Simulated search result for {query!r}: No specific information found, but the topic seems interesting.",
    }

    normalized_query = query.strip().lower()

    # 做一点简单归一化，让模型传入自然语言时也更容易命中
    if "capital" in normalized_query and "france" in normalized_query:
        key = "capital of france"
    elif "weather" in normalized_query and "london" in normalized_query:
        key = "weather in london"
    elif "population" in normalized_query and "earth" in normalized_query:
        key = "population of earth"
    elif "tallest" in normalized_query and "mountain" in normalized_query:
        key = "tallest mountain"
    elif "dog" in normalized_query or "dogs" in normalized_query:
        key = "dogs"
    else:
        key = normalized_query

    result = simulated_results.get(key, simulated_results["default"])

    print(f"--- 工具返回结果：{result} ---")

    return result


# ============================================================
# 工具注册表
# ============================================================
# Tool Use 的关键工程结构之一就是工具注册表。
#
# 模型不能随便调用任意函数。
# 程序只允许调用 TOOLS 中注册过的工具。
# ============================================================


ToolFunction = Callable[..., Any]


TOOLS: dict[str, ToolFunction] = {
    "search_information": search_information,
}


TOOL_DESCRIPTIONS = """
当前系统可用工具如下：

1. search_information
用途：
- 查询简单事实信息；
- 查询天气、国家首都、人口、常识类信息；
- 当用户问“法国首都是哪里”“伦敦天气怎么样”“告诉我一些关于狗的信息”等问题时，可以使用。

参数：
{
  "query": "string，查询关键词或查询问题"
}
"""


# ============================================================
# 工具调用 JSON 解析
# ============================================================


def extract_json_object(text: str) -> dict[str, Any]:
    """
    从模型输出中提取 JSON 对象。

    为什么需要这个函数？
    因为模型有时会输出：

    ```json
    {...}
    ```

    或者在 JSON 前后加解释文字。
    这里做一个简单清洗，尽量提高 demo 的健壮性。
    """

    cleaned = text.strip()

    # 去掉 Markdown JSON 代码块
    code_block_pattern = r"```(?:json)?\s*(.*?)```"
    match = re.search(code_block_pattern, cleaned, flags=re.DOTALL | re.IGNORECASE)

    if match:
        cleaned = match.group(1).strip()

    # 如果还有多余文本，尝试截取第一个 JSON 对象
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型输出不是合法 JSON，原始输出为：{text}") from exc


def parse_tool_call(raw_text: str) -> ToolCallRequest:
    """
    将模型输出解析为 ToolCallRequest。
    """

    data = extract_json_object(raw_text)

    action = data.get("action")

    if action == "tool_call":
        return ToolCallRequest(
            action="tool_call",
            tool_name=data.get("tool_name"),
            arguments=data.get("arguments") or {},
            final_answer=None,
        )

    if action == "final_answer":
        return ToolCallRequest(
            action="final_answer",
            tool_name=None,
            arguments=None,
            final_answer=data.get("final_answer", ""),
        )

    raise ValueError(f"未知 action：{action}，完整输出为：{data}")


# ============================================================
# Tool Planner：让模型决定是否需要调用工具
# ============================================================


async def plan_tool_call(llm: AsyncLLMClient, user_query: str) -> ToolCallRequest:
    """
    Tool Planner 阶段。

    让模型判断：
    1. 是否需要工具；
    2. 如果需要，调用哪个工具；
    3. 工具参数是什么。

    注意：
    模型只负责“提出工具调用请求”，不会真的执行工具。
    """

    system_prompt = f"""
你是一个 Agent 系统中的 Tool Planner。

你的职责：
1. 判断用户问题是否需要调用工具；
2. 如果需要工具，输出工具调用 JSON；
3. 如果不需要工具，输出最终答案 JSON。

重要限制：
1. 只能使用系统提供的工具；
2. 不能编造不存在的工具；
3. 不能自己假装已经调用工具；
4. 必须严格输出 JSON；
5. 不要输出 Markdown；
6. 不要输出额外解释。

{TOOL_DESCRIPTIONS}

如果需要调用工具，请输出：

{{
  "action": "tool_call",
  "tool_name": "search_information",
  "arguments": {{
    "query": "查询内容"
  }}
}}

如果不需要调用工具，请输出：

{{
  "action": "final_answer",
  "final_answer": "你的回答"
}}
"""

    user_prompt = f"""
用户问题：
{user_query}

请判断是否需要调用工具，并严格输出 JSON。
"""

    raw_response = await llm.chat(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.0,
        max_tokens=512,
    )

    print("\n--- Tool Planner 原始输出 ---")
    print(raw_response)

    return parse_tool_call(raw_response)


# ============================================================
# Tool Executor：程序侧真正执行工具
# ============================================================


def validate_tool_call(tool_call: ToolCallRequest) -> None:
    """
    校验工具调用是否合法。

    这里体现 Tool Use 的工程安全点：
    模型输出不能直接相信，必须由程序侧校验。
    """

    if tool_call.action != "tool_call":
        raise ValueError(f"当前不是工具调用 action：{tool_call.action}")

    if not tool_call.tool_name:
        raise ValueError("tool_name 不能为空")

    if tool_call.tool_name not in TOOLS:
        raise ValueError(f"未知工具：{tool_call.tool_name}")

    if tool_call.arguments is None:
        raise ValueError("arguments 不能为空")

    if tool_call.tool_name == "search_information":
        query = tool_call.arguments.get("query")

        if not isinstance(query, str) or not query.strip():
            raise ValueError("search_information 工具需要非空字符串参数 query")


async def execute_tool(tool_call: ToolCallRequest) -> ToolResult:
    """
    执行工具调用。

    注意：
    当前 search_information 是同步函数。
    为了兼容未来可能存在的耗时工具，这里用 asyncio.to_thread 包一层。
    """

    start_time = time.perf_counter()

    try:
        validate_tool_call(tool_call)

        assert tool_call.tool_name is not None
        assert tool_call.arguments is not None

        tool_func = TOOLS[tool_call.tool_name]

        result = await asyncio.to_thread(tool_func, **tool_call.arguments)

        elapsed = time.perf_counter() - start_time

        return ToolResult(
            tool_name=tool_call.tool_name,
            success=True,
            result=result,
            error=None,
            elapsed_seconds=elapsed,
        )

    except Exception as exc:
        elapsed = time.perf_counter() - start_time

        return ToolResult(
            tool_name=tool_call.tool_name or "unknown",
            success=False,
            result=None,
            error=str(exc),
            elapsed_seconds=elapsed,
        )


# ============================================================
# Final Answer：让模型基于工具结果生成最终回答
# ============================================================


async def generate_final_answer(
    llm: AsyncLLMClient,
    user_query: str,
    tool_call: ToolCallRequest,
    tool_result: ToolResult,
) -> str:
    """
    根据工具执行结果生成最终回答。

    注意：
    这里模型不能编造工具结果之外的信息。
    """

    system_prompt = """
你是一个严谨的中文助手。

你会收到：
1. 用户原始问题；
2. 工具调用请求；
3. 工具执行结果。

你的任务：
1. 根据工具结果回答用户问题；
2. 如果工具执行失败，要解释失败原因；
3. 不要编造工具结果中没有的信息；
4. 回答要简洁清楚。
"""

    user_prompt = f"""
用户原始问题：
{user_query}

工具调用请求：
{json.dumps(tool_call.__dict__, ensure_ascii=False, indent=2)}

工具执行结果：
{json.dumps(tool_result.__dict__, ensure_ascii=False, indent=2)}

请基于工具结果生成最终回答。
"""

    return await llm.chat(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.2,
        max_tokens=800,
    )


# ============================================================
# Agent 主流程
# ============================================================


async def run_agent_with_tool(llm: AsyncLLMClient, user_query: str) -> str:
    """
    执行一次 Tool Use Agent 流程。

    完整流程：
    1. 用户输入；
    2. Tool Planner 判断是否需要工具；
    3. 如果不需要工具，直接返回 final_answer；
    4. 如果需要工具，程序侧校验并执行工具；
    5. 模型基于工具结果生成最终回答。
    """

    print("\n" + "=" * 80)
    print(f"用户问题：{user_query}")

    try:
        tool_call = await plan_tool_call(llm, user_query)

        print("\n--- 解析后的 ToolCallRequest ---")
        print(tool_call)

        if tool_call.action == "final_answer":
            return tool_call.final_answer or ""

        tool_result = await execute_tool(tool_call)

        print("\n--- ToolResult ---")
        print(tool_result)

        final_answer = await generate_final_answer(
            llm=llm,
            user_query=user_query,
            tool_call=tool_call,
            tool_result=tool_result,
        )

        return final_answer

    except Exception as exc:
        return f"Agent 执行失败：{exc}"


# ============================================================
# 并发运行多个用户问题
# ============================================================


async def main() -> None:
    """
    并发执行多个 Tool Use 示例。

    这里复用了 AsyncLLMClient 的异步上下文管理。
    你的 AsyncLLMClient 会复用底层 httpx.AsyncClient，避免每次请求都重新建连接。
    """

    queries = [
        "What is the capital of France?",
        "What's the weather like in London?",
        "Tell me something about dogs.",
    ]

    async with AsyncLLMClient() as llm:
        tasks = [
            run_agent_with_tool(llm, query)
            for query in queries
        ]

        results = await asyncio.gather(*tasks)

    print("\n" + "=" * 80)
    print("最终结果汇总")

    for query, result in zip(queries, results):
        print("\n--- Query ---")
        print(query)
        print("--- Final Answer ---")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())