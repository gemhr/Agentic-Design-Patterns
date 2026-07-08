# Part_One/C2_Routing/demo2.py
import sys
from pathlib import Path


# ============================================================
# 处理项目内模块导入
# ============================================================
# 当前文件路径：
# Part_One/C2_Routing/demo2.py
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
# 模拟不同的子 Agent / Handler
# ============================================================
# 在真实 Agent 系统中，这些 Handler 可以替换成：
# 1. 订票 Agent
# 2. 信息查询 Agent
# 3. 代码专家 Agent
# 4. 数据分析 Agent
# 5. 知识库 Agent
#
# 当前示例只模拟 Routing 的核心思想：
# Router 负责判断任务类型，Handler 负责真正处理任务。
# ============================================================


def booking_handler(request: str) -> str:
    """
    模拟订票处理器。

    适合处理：
    - 订机票
    - 订酒店
    - 行程预订
    """

    print("\n--- 路由到 Booking Handler：订票处理器 ---")
    return f"Booking Handler 已处理请求：{request!r}。结果：模拟完成预订操作。"


def info_handler(request: str) -> str:
    """
    模拟信息查询处理器。

    适合处理：
    - 常识问题
    - 地理问题
    - 概念解释
    - 普通信息查询
    """

    print("\n--- 路由到 Info Handler：信息查询处理器 ---")
    return f"Info Handler 已处理请求：{request!r}。结果：模拟完成信息查询。"


def unclear_handler(request: str) -> str:
    """
    模拟兜底处理器。

    当 Router 无法判断用户请求属于哪一类时，进入这里。
    """

    print("\n--- 路由到 Unclear Handler：兜底处理器 ---")
    return f"Coordinator 无法明确分发请求：{request!r}。请用户补充说明。"


# ============================================================
# Router：使用 LLM 判断应该走哪条路由
# ============================================================


def normalize_route(raw_route: str) -> str:
    """
    规范化模型输出。

    为什么需要这个函数？
    因为 LLM 可能不会完全按要求只输出一个词，例如：
    - booker
    - booker.
    - 'booker'
    - 结果是：booker

    所以这里做一次清洗，提高代码健壮性。
    """

    route = raw_route.strip().lower()

    # 去掉常见多余符号
    route = route.replace("'", "").replace('"', "")
    route = route.replace(".", "").replace("。", "")
    route = route.replace("`", "")

    # 如果模型输出了包含解释的句子，尝试从中提取合法 route
    allowed_routes = ["booker", "info", "unclear"]

    for allowed_route in allowed_routes:
        if allowed_route in route:
            return allowed_route

    return "unclear"


def route_request(llm: LLMClient, request: str) -> str:
    """
    使用 LLM Router 判断用户请求应该交给哪个 Handler。

    输出只能是：
    - booker
    - info
    - unclear
    """

    system_prompt = """
你是一个 Agent 系统中的任务路由器。

你的职责不是回答用户问题，而是判断用户请求应该交给哪个处理器。

可选路由如下：

1. booker
适用于订机票、订酒店、预订旅行相关请求。

2. info
适用于普通信息查询、概念解释、常识问题、知识性问题。

3. unclear
适用于用户请求含糊、不完整，或者无法判断应该交给哪个处理器的情况。

请严格遵守以下要求：
1. 只能输出一个单词；
2. 只能从 booker、info、unclear 中选择一个；
3. 不要输出解释；
4. 不要输出 JSON；
5. 不要输出 Markdown。
"""

    user_prompt = f"""
请判断下面用户请求应该路由到哪一个处理器。

用户请求：
{request}
"""

    raw_decision = llm.chat(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.0,
        max_tokens=20,
    )

    decision = normalize_route(raw_decision)

    print("\n--- Router 原始输出 ---")
    print(raw_decision)

    print("\n--- Router 规范化结果 ---")
    print(decision)

    return decision


# ============================================================
# Delegation：根据 Router 结果分发到不同 Handler
# ============================================================


def coordinator_agent(request: str) -> str:
    """
    协调器 Agent。

    执行流程：
    1. 接收用户请求；
    2. 调用 Router 判断 route；
    3. 根据 route 分发给对应 Handler；
    4. 返回 Handler 的处理结果。
    """

    llm = LLMClient()

    decision = route_request(llm, request)

    handlers = {
        "booker": booking_handler,
        "info": info_handler,
        "unclear": unclear_handler,
    }

    # 如果模型输出了未知 route，则使用 unclear_handler 兜底
    handler = handlers.get(decision, unclear_handler)

    result = handler(request)

    return result


# ============================================================
# 示例运行
# ============================================================


def main() -> None:
    """
    运行 Routing 示例。
    """

    print("\n========== 示例 A：订票请求 ==========")
    request_a = "Book me a flight to London."
    result_a = coordinator_agent(request_a)
    print(f"\nFinal Result A: {result_a}")

    print("\n========== 示例 B：信息查询请求 ==========")
    request_b = "What is the capital of Italy?"
    result_b = coordinator_agent(request_b)
    print(f"\nFinal Result B: {result_b}")

    print("\n========== 示例 C：含糊请求 ==========")
    # 注意：
    # 原书示例里用了 "Tell me about quantum physics."
    # 但这个请求其实属于普通知识查询，更应该被路由到 info，而不是 unclear。
    # 所以这里换成一个更含糊的请求，方便观察 unclear 分支。
    request_c = "Can you help me with that thing?"
    result_c = coordinator_agent(request_c)
    print(f"\nFinal Result C: {result_c}")


if __name__ == "__main__":
    main()