# common/llm_client.py
import json
import os
from typing import Any, Literal

import httpx
import requests
from requests import Response


LLMProvider = Literal["qwen", "deepseek"]


class BaseLLMConfig:
    """
    LLM 通用配置基类。

    作用：
    1. 统一读取环境变量；
    2. 统一构造请求地址；
    3. 统一构造请求头和请求体；
    4. 同步客户端和异步客户端都复用这套配置。
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

    def _build_headers(self) -> dict[str, str]:
        """
        构造 HTTP 请求头。

        DeepSeek 官方 API 需要 Authorization。
        公司内网千问当前不需要 API Key，所以 LLM_API_KEY 为空时不加 Authorization。
        """

        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _build_body(
        self,
        user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """
        构造 Chat Completions 请求体。

        注意：
        - qwen：公司内网千问支持 chat_template_kwargs.enable_thinking；
        - deepseek：这里保持 OpenAI-compatible 标准参数，不额外传 thinking 字段，避免官方接口不识别。
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
            body["chat_template_kwargs"] = {
                "enable_thinking": self.enable_thinking,
            }

        return body

    def _get_provider(self, provider: LLMProvider | None) -> LLMProvider:
        """
        获取模型提供方。

        支持：
        - qwen：公司内网千问
        - deepseek：家里 DeepSeek 官方 API
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
        获取模型接口地址。

        强烈建议通过环境变量 LLM_BASE_URL 配置。
        """

        env_base_url = os.getenv("LLM_BASE_URL")
        if env_base_url:
            return env_base_url

        if self.provider == "qwen":
            # 公司内网地址不要提交真实值，建议通过环境变量配置
            return "http://xxx.x.x.x:8001/v1/chat/completions"

        if self.provider == "deepseek":
            return "https://api.deepseek.com"

        raise ValueError(f"未知 provider：{self.provider}")

    def _get_model(self) -> str:
        """
        获取模型名。

        强烈建议通过环境变量 LLM_MODEL 配置。
        """

        env_model = os.getenv("LLM_MODEL")
        if env_model:
            return env_model

        if self.provider == "qwen":
            return "Qwen3.5-27B"

        if self.provider == "deepseek":
            return "deepseek-v4-pro"

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


class AsyncLLMClient(BaseLLMConfig):
    """
    异步 LLM 客户端。

    适用于：
    - Parallelization demo
    - 多 Worker 并发调用模型
    - 多 Agent 并发执行
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
        max_connections: int | None = None,
        max_keepalive_connections: int | None = None,
        trust_env: bool | None = None,
        http2: bool | None = None,
    ) -> None:
        super().__init__(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout=timeout,
            verify_ssl=verify_ssl,
            enable_thinking=enable_thinking,
        )

        self.max_connections = max_connections or int(os.getenv("LLM_MAX_CONNECTIONS", "3"))
        self.max_keepalive_connections = (
            max_keepalive_connections
            if max_keepalive_connections is not None
            else int(os.getenv("LLM_MAX_KEEPALIVE_CONNECTIONS", "0"))
        )

        # 公司内网模型强烈建议默认 False，避免走系统代理
        self.trust_env = (
            trust_env
            if trust_env is not None
            else self._get_bool_env("LLM_TRUST_ENV", False)
        )

        self.http2 = (
            http2
            if http2 is not None
            else self._get_bool_env("LLM_HTTP2", False)
        )

        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """
        懒加载 AsyncClient，保证多个并发请求复用同一个客户端。
        """

        if self._client is not None and not self._client.is_closed:
            return self._client

        timeout = httpx.Timeout(
            connect=10.0,
            read=float(self.timeout),
            write=30.0,
            pool=30.0,
        )

        limits = httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
        )

        self._client = httpx.AsyncClient(
            timeout=timeout,
            verify=self.verify_ssl,
            limits=limits,
            trust_env=self.trust_env,
            http2=self.http2,
        )

        return self._client

    async def aclose(self) -> None:
        """
        关闭底层 HTTP 客户端。
        """

        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncLLMClient":
        self._get_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def chat(
        self,
        user_prompt: str,
        system_prompt: str = "你是一个严谨、简洁的中文 AI 助手。",
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        body = self._build_body(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response_data = await self._post(body)

        return self._extract_content(response_data)

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        client = self._get_client()

        try:
            response = await client.post(
                self.chat_url,
                headers=self._build_headers(),
                json=body,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"异步请求模型失败：provider={self.provider}, "
                    f"url={self.chat_url}, "
                    f"status_code={response.status_code}, "
                    f"response_body={response.text[:1000]}"
                )

            try:
                return response.json()
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"模型返回内容不是合法 JSON，原始响应该为：{response.text[:1000]}"
                ) from exc

        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"异步请求模型超时：provider={self.provider}, "
                f"url={self.chat_url}, "
                f"timeout={self.timeout}, "
                f"error={repr(exc)}"
            ) from exc

        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"异步请求模型 HTTP 异常：provider={self.provider}, "
                f"url={self.chat_url}, "
                f"error={repr(exc)}"
            ) from exc

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        try:
            return data["choices"][0]["message"]["content"]
        except KeyError as exc:
            raise RuntimeError(f"无法从模型响应中解析 content，原始响应为：{data}") from exc
