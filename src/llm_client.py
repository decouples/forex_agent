"""
大模型客户端封装
================
统一封装 Gemini 和 ChatGLM，便于在 LangGraph 节点内通过同一接口调用。
内置内存缓存：相同 prompt 不重复调用 API，节省 token 和延迟。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from functools import lru_cache
from src.config import settings
from src.logging_utils import get_logger

logger = get_logger(__name__)


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类。"""

    @abstractmethod
    def _call(self, prompt: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        return _cached_generate(self.__class__.__name__, prompt, system_prompt or "")


class GeminiClient(BaseLLMClient):
    """Gemini SDK 封装（默认 gemini-2.0-flash-lite，延迟极低）。"""

    def _call(self, prompt: str, system_prompt: str | None = None) -> str:
        from google import genai

        if not settings.GEMINI_API_KEY:
            return "未配置 GEMINI_API_KEY，返回本地占位报告。"

        logger.info("llm_request | provider=gemini | model=%s | prompt_len=%s", settings.GEMINI_MODEL, len(prompt))
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        final_prompt = prompt if not system_prompt else f"{system_prompt}\n\n{prompt}"
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=final_prompt,
            # config={"max_output_tokens": 512},
        )
        text = getattr(response, "text", "") or "Gemini 未返回文本结果。"
        if not text.strip():
            logger.warning("llm_empty_response | provider=gemini | model=%s", settings.GEMINI_MODEL)
            raise ValueError("Gemini 返回空文本。")
        logger.info("llm_response | provider=gemini | model=%s | text_len=%s", settings.GEMINI_MODEL, len(text))
        return text


class ChatGLMClient(BaseLLMClient):
    """ChatGLM (zai-sdk) 封装（默认 glm-4-flash，速度最快）。"""

    def _call(self, prompt: str, system_prompt: str | None = None) -> str:
        from zai import ZhipuAiClient

        if not settings.CHATGLM_API_KEY:
            return "未配置 CHATGLM_API_KEY，返回本地占位报告。"

        logger.info("llm_request | provider=chatglm | model=%s | prompt_len=%s", settings.CHATGLM_MODEL, len(prompt))
        client = ZhipuAiClient(api_key=settings.CHATGLM_API_KEY)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=settings.CHATGLM_MODEL,
            messages=messages,
            temperature=0.4,
            thinking={"type": "disabled"}
            # max_tokens=512
        )
        print(response)
        text = response.choices[0].message.content or ""
        if not text.strip():
            text = response.choices[0].message.reasoning_content or ""
        if not text.strip():
            logger.warning("llm_empty_response | provider=chatglm | model=%s", settings.CHATGLM_MODEL)
            raise ValueError("ChatGLM 返回空文本。")
        logger.info("llm_response | provider=chatglm | model=%s | text_len=%s", settings.CHATGLM_MODEL, len(text))
        return text


# 全局 LLM 实例（惰性初始化，避免每次 import 就构造）
_client_instance: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    """根据配置返回指定的 LLM 客户端（单例）。"""
    global _client_instance
    if _client_instance is None:
        if settings.LLM_PROVIDER == "chatglm":
            _client_instance = ChatGLMClient()
        else:
            _client_instance = GeminiClient()
    return _client_instance


@lru_cache(maxsize=64)
def _cached_generate(client_class: str, prompt: str, system_prompt: str) -> str:
    """缓存 LLM 调用结果：相同 prompt 直接返回，不重复请求 API。"""
    logger.info("llm_cache_miss | client=%s | prompt_len=%s", client_class, len(prompt))
    client = get_llm_client()
    return client._call(prompt, system_prompt or None)
