# common/llm_client.py
import json
import os
from typing import Any, Literal

import requests
from requests import Response


LLMProvider = Literal["qwen", "deepseek"]


class LLMClient:
    """
    通用 LLM 客户端。

    支持两种环境：
    1. 公司内网环境：调用部门本地部署的千问；
    2. 家里环境：调用 DeepSeek 官方 API。

    所有敏感信息都通过环境变量传入，不写死在代码里。
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
        verify_ssl: bool | None = None,
        enable_thinking: bool | None = None,
    ) -> None:
        """
        初始化客户端。

        优先级：
        1. 显式传入的参数；
        2. 环境变量；
        3. 默认值。
        """

        self.provider: LLMProvider = self._get_provider(provider)
        self.base_url = base_url or self._get_base_url()
        self.model = model or self._get_model()
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")

        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", "60"))
        self.verify_ssl = (
            verify_ssl
            if verify_ssl is not None
            else self._get_bool_env("LLM_VERIFY_SSL", self.provider == "deepseek")
        )

        self.enable_thinking = (
            enable_thinking
            if enable_thinking is not None
            else self._get_bool_env("LLM_ENABLE_THINKING", False)
        )

        self.chat_url = self._build_chat_url(self.base_url)

    def chat(
        self,
        user_prompt: str,
        system_prompt: str = "你是一个严谨、简洁的中文 AI 助手。",
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """
        普通对话接口。

        后续所有章节示例都建议只调用这个方法。
        """

        body = self._build_body(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = self._post(body)
        data = self._parse_response(response)

        try:
            return data["choices"][0]["message"]["content"]
        except KeyError as exc:
            raise RuntimeError(f"无法从模型响应中解析 content，原始响应为：{data}") from exc

    def _build_body(
        self,
        user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """
        根据不同 provider 构造请求体。
        """

        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        if self.provider == "qwen":
            # 公司内网千问接口使用这个字段关闭 thinking 模式
            body["chat_template_kwargs"] = {
                "enable_thinking": self.enable_thinking,
            }

        elif self.provider == "deepseek":
            # DeepSeek 官方 API 当前支持 thinking 开关。
            # 这里默认关闭，方便章节 demo 稳定输出。
            body["thinking"] = {
                "type": "enabled" if self.enable_thinking else "disabled",
            }

        return body

    def _post(self, body: dict[str, Any]) -> Response:
        """
        发送 HTTP 请求。
        """

        headers = {
            "Content-Type": "application/json",
        }

        # DeepSeek 官方 API 需要 Bearer Token。
        # 公司内网千问当前不需要 API Key，所以 api_key 为空时不添加 Authorization。
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(
                self.chat_url,
                headers=headers,
                json=body,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            raise RuntimeError(
                f"请求模型失败：provider={self.provider}, url={self.chat_url}, error={exc}"
            ) from exc

    @staticmethod
    def _parse_response(response: Response) -> dict[str, Any]:
        """
        解析模型返回 JSON。
        """

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"模型返回内容不是合法 JSON：{response.text}") from exc

    def _get_provider(self, provider: LLMProvider | None) -> LLMProvider:
        """
        获取当前模型提供方。
        """

        raw_provider = provider or os.getenv("LLM_PROVIDER", "qwen")
        raw_provider = raw_provider.strip().lower()

        if raw_provider not in {"qwen", "deepseek"}:
            raise ValueError(
                "LLM_PROVIDER 只支持 qwen 或 deepseek，"
                f"当前值为：{raw_provider}"
            )

        return raw_provider  # type: ignore[return-value]

    def _get_base_url(self) -> str:
        """
        根据 provider 获取默认模型地址。

        注意：
        - 公司千问地址建议通过环境变量传入；
        - DeepSeek 官方 API 默认 base_url 是 https://api.deepseek.com。
        """

        env_base_url = os.getenv("LLM_BASE_URL")
        if env_base_url:
            return env_base_url

        if self.provider == "qwen":
            return "http://xxx.x.x.x:8001/v1/chat/completions"

        if self.provider == "deepseek":
            return "https://api.deepseek.com"

        raise ValueError(f"未知 provider：{self.provider}")

    def _get_model(self) -> str:
        """
        根据 provider 获取默认模型名。
        """

        env_model = os.getenv("LLM_MODEL")
        if env_model:
            return env_model

        if self.provider == "qwen":
            return "Qwen3.5-27B"

        if self.provider == "deepseek":
            return "deepseek-v4-flash"

        raise ValueError(f"未知 provider：{self.provider}")

    @staticmethod
    def _build_chat_url(base_url: str) -> str:
        """
        兼容两种写法：

        1. 直接传完整接口：
           http://xxx.x.x.x:8001/v1/chat/completions

        2. 只传 base_url：
           https://api.deepseek.com

        如果没有以 /chat/completions 结尾，则自动补上。
        """

        url = base_url.rstrip("/")

        if url.endswith("/chat/completions"):
            return url

        return f"{url}/chat/completions"

    @staticmethod
    def _get_bool_env(name: str, default: bool) -> bool:
        """
        从环境变量读取 bool 值。
        """

        value = os.getenv(name)
        if value is None:
            return default

        return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# 兼容之前第一章第一节 demo 里的写法。
# 后续建议逐步改成 LLMClient。
QwenLLMClient = LLMClient
