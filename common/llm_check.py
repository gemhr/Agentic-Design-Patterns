# common/llm_check.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.llm_client import LLMClient

def main() -> None:
    """
    测试当前环境变量配置下的模型是否可用。
    """

    llm = LLMClient()

    result = llm.chat(
        user_prompt="请用一句话说明 Prompt Chaining 是什么。",
        system_prompt="你是一个严谨、简洁的中文 AI 助手。",
    )

    print("\n========== 当前模型输出 ==========")
    print(result)


if __name__ == "__main__":
    main()