"""
大模型客户端封装（异步版）
========================
统一封装 Gemini / ChatGLM / DeepSeek / vLLM，便于在 LangGraph 节点内通过同一接口调用。
内置内存缓存：相同 prompt 不重复调用 API，节省 token 和延迟。

支持的 LLM_PROVIDER：
  - gemini    : Google Gemini（google-genai SDK）
  - chatglm   : 智谱 ChatGLM（zai-sdk）
  - deepseek  : DeepSeek 官方 API（兼容 OpenAI 协议，通过 httpx 异步直连）
  - vllm      : 本地 vLLM 推理服务（兼容 OpenAI /v1/chat/completions 协议）
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import httpx

from src.config import settings
from src.logging_utils import get_logger

logger = get_logger(__name__)

_llm_cache: dict[tuple[str, str, str], str] = {}


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类。"""

    @abstractmethod
    async def _acall(self, prompt: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError

    async def agenerate(self, prompt: str, system_prompt: str | None = None) -> str:
        return await _cached_agenerate(self.__class__.__name__, prompt, system_prompt or "", self)


# ================================================================
#  Gemini
# ================================================================

class GeminiClient(BaseLLMClient):
    """Gemini SDK 封装（SDK 本身是同步的，放在线程池中执行避免阻塞事件循环）。"""

    async def _acall(self, prompt: str, system_prompt: str | None = None) -> str:
        from google import genai

        if not settings.GEMINI_API_KEY:
            return "未配置 GEMINI_API_KEY，返回本地占位报告。"

        logger.info("llm_request | provider=gemini | model=%s | prompt_len=%s", settings.GEMINI_MODEL, len(prompt))
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        final_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.GEMINI_MODEL,
            contents=final_prompt,
        )
        text = getattr(response, "text", "") or ""
        if not text.strip():
            logger.warning("llm_empty_response | provider=gemini | model=%s", settings.GEMINI_MODEL)
            raise ValueError("Gemini 返回空文本。")
        logger.info("llm_response | provider=gemini | model=%s | text_len=%s", settings.GEMINI_MODEL, len(text))
        return text


# ================================================================
#  ChatGLM / ZhipuAI
# ================================================================

class ChatGLMClient(BaseLLMClient):
    """ChatGLM (zai-sdk) 封装（SDK 同步，放入线程池）。"""

    async def _acall(self, prompt: str, system_prompt: str | None = None) -> str:
        from zai import ZhipuAiClient

        if not settings.CHATGLM_API_KEY:
            return "未配置 CHATGLM_API_KEY，返回本地占位报告。"

        logger.info("llm_request | provider=chatglm | model=%s | prompt_len=%s", settings.CHATGLM_MODEL, len(prompt))
        client = ZhipuAiClient(api_key=settings.CHATGLM_API_KEY)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=settings.CHATGLM_MODEL,
            messages=messages,
            temperature=0.4,
            thinking={"type": "disabled"},
        )
        text = response.choices[0].message.content or ""
        if not text.strip():
            text = response.choices[0].message.reasoning_content or ""
        if not text.strip():
            logger.warning("llm_empty_response | provider=chatglm | model=%s", settings.CHATGLM_MODEL)
            raise ValueError("ChatGLM 返回空文本。")
        logger.info("llm_response | provider=chatglm | model=%s | text_len=%s", settings.CHATGLM_MODEL, len(text))
        return text


# ================================================================
#  DeepSeek（兼容 OpenAI 协议，httpx 异步直连）
# ================================================================

class DeepSeekClient(BaseLLMClient):
    """DeepSeek 官方 API 封装（httpx 异步）。"""

    async def _acall(self, prompt: str, system_prompt: str | None = None) -> str:
        if not settings.DEEPSEEK_API_KEY:
            return "未配置 DEEPSEEK_API_KEY，返回本地占位报告。"

        logger.info(
            "llm_request | provider=deepseek | model=%s | base_url=%s | prompt_len=%s",
            settings.DEEPSEEK_MODEL, settings.DEEPSEEK_BASE_URL, len(prompt),
        )
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.DEEPSEEK_BASE_URL.rstrip('/')}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1024,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text.strip():
            logger.warning("llm_empty_response | provider=deepseek | model=%s", settings.DEEPSEEK_MODEL)
            raise ValueError("DeepSeek 返回空文本。")
        logger.info("llm_response | provider=deepseek | model=%s | text_len=%s", settings.DEEPSEEK_MODEL, len(text))
        return text


# ================================================================
#  vLLM 本地推理（兼容 OpenAI /v1/chat/completions 协议）
# ================================================================

class VLLMClient(BaseLLMClient):
    """vLLM 本地推理服务封装（httpx 异步）。"""

    async def _acall(self, prompt: str, system_prompt: str | None = None) -> str:
        logger.info(
            "llm_request | provider=vllm | model=%s | base_url=%s | prompt_len=%s",
            settings.VLLM_MODEL, settings.VLLM_BASE_URL, len(prompt),
        )
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.VLLM_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.VLLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.VLLM_MODEL,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1024,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not text.strip():
            logger.warning("llm_empty_response | provider=vllm | model=%s", settings.VLLM_MODEL)
            raise ValueError("vLLM 返回空文本。")
        logger.info("llm_response | provider=vllm | model=%s | text_len=%s", settings.VLLM_MODEL, len(text))
        return text


# ================================================================
#  单例路由
# ================================================================

_client_instance: BaseLLMClient | None = None

_PROVIDER_MAP: dict[str, type[BaseLLMClient]] = {
    "gemini": GeminiClient,
    "chatglm": ChatGLMClient,
    "deepseek": DeepSeekClient,
    "vllm": VLLMClient,
}


def get_llm_client() -> BaseLLMClient:
    """根据 LLM_PROVIDER 配置返回对应客户端（单例）。"""
    global _client_instance
    if _client_instance is None:
        cls = _PROVIDER_MAP.get(settings.LLM_PROVIDER)
        if cls is None:
            supported = ", ".join(sorted(_PROVIDER_MAP.keys()))
            raise ValueError(
                f"未知的 LLM_PROVIDER: '{settings.LLM_PROVIDER}'，支持的值：{supported}"
            )
        _client_instance = cls()
        logger.info("llm_client_init | provider=%s | class=%s", settings.LLM_PROVIDER, cls.__name__)
    return _client_instance


async def _cached_agenerate(client_class: str, prompt: str, system_prompt: str, client: BaseLLMClient) -> str:
    """异步安全的内存缓存：相同 prompt 直接返回，不重复请求 API。"""
    key = (client_class, prompt, system_prompt)
    if key in _llm_cache:
        logger.info("llm_cache_hit | client=%s | prompt_len=%s", client_class, len(prompt))
        return _llm_cache[key]
    logger.info("llm_cache_miss | client=%s | prompt_len=%s", client_class, len(prompt))
    result = await client._acall(prompt, system_prompt or None)
    _llm_cache[key] = result
    return result
