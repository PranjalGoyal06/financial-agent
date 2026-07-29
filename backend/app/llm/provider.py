from __future__ import annotations

from typing import Any, Type, TypeVar, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


import asyncio

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_LOCAL_LLM_SEMAPHORE = asyncio.Semaphore(2)
_GEMINI_LAST_CALL_LOCK = asyncio.Lock()
_GEMINI_LAST_CALL_TIME: float = 0.0
_GEMINI_CIRCUIT_BROKEN: bool = False


def reset_gemini_circuit_breaker() -> None:
    """Reset the Gemini circuit breaker state for a new research run."""
    global _GEMINI_CIRCUIT_BROKEN
    _GEMINI_CIRCUIT_BROKEN = False
    logger.info("Gemini circuit breaker reset for new run.")


class GeminiCircuitBrokenError(Exception):
    """Raised when Gemini calls are disabled for the remainder of a research run."""
    pass


class ThrottledChatOllama(ChatOllama):
    """ChatOllama wrapper that uses a global semaphore to throttle concurrent local inference."""
    async def _agenerate(self, *args, **kwargs):
        async with _LOCAL_LLM_SEMAPHORE:
            return await super()._agenerate(*args, **kwargs)

    async def _astream(self, *args, **kwargs):
        async with _LOCAL_LLM_SEMAPHORE:
            async for chunk in super()._astream(*args, **kwargs):
                yield chunk


class ThrottledChatGoogleGenerativeAI(ChatGoogleGenerativeAI):
    """ChatGoogleGenerativeAI wrapper that enforces 1 RPM rate limit (60s pacing)
    and a 1-strike circuit breaker per research run."""

    async def _agenerate(self, *args, **kwargs):
        global _GEMINI_LAST_CALL_TIME, _GEMINI_CIRCUIT_BROKEN
        if _GEMINI_CIRCUIT_BROKEN:
            raise GeminiCircuitBrokenError(
                f"Gemini circuit breaker active for current run: skipping request for model '{self.model}'."
            )

        async with _GEMINI_LAST_CALL_LOCK:
            if _GEMINI_CIRCUIT_BROKEN:
                raise GeminiCircuitBrokenError(
                    f"Gemini circuit breaker active for current run: skipping request for model '{self.model}'."
                )

            now = time.monotonic()
            elapsed = now - _GEMINI_LAST_CALL_TIME
            if elapsed < 60.0 and _GEMINI_LAST_CALL_TIME > 0:
                wait_time = 60.0 - elapsed
                logger.info("Pacing Gemini API call (1 RPM limit): Waiting %.1fs...", wait_time)
                await asyncio.sleep(wait_time)
            _GEMINI_LAST_CALL_TIME = time.monotonic()

        try:
            return await super()._agenerate(*args, **kwargs)
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "Quota exceeded" in err_msg or "ResourceExhausted" in err_msg:
                _GEMINI_CIRCUIT_BROKEN = True
                logger.warning("Gemini 429 quota limit hit. Circuit breaker activated for current run.")
                raise GeminiCircuitBrokenError(
                    f"429 Quota Exceeded for model '{self.model}'. Circuit breaker activated for current run."
                ) from exc
            raise exc

    async def _astream(self, *args, **kwargs):
        global _GEMINI_LAST_CALL_TIME, _GEMINI_CIRCUIT_BROKEN
        if _GEMINI_CIRCUIT_BROKEN:
            raise GeminiCircuitBrokenError(
                f"Gemini circuit breaker active for current run: skipping request for model '{self.model}'."
            )

        async with _GEMINI_LAST_CALL_LOCK:
            if _GEMINI_CIRCUIT_BROKEN:
                raise GeminiCircuitBrokenError(
                    f"Gemini circuit breaker active for current run: skipping request for model '{self.model}'."
                )

            now = time.monotonic()
            elapsed = now - _GEMINI_LAST_CALL_TIME
            if elapsed < 60.0 and _GEMINI_LAST_CALL_TIME > 0:
                wait_time = 60.0 - elapsed
                logger.info("Pacing Gemini API call (1 RPM limit): Waiting %.1fs...", wait_time)
                await asyncio.sleep(wait_time)
            _GEMINI_LAST_CALL_TIME = time.monotonic()

        try:
            async for chunk in super()._astream(*args, **kwargs):
                yield chunk
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "Quota exceeded" in err_msg or "ResourceExhausted" in err_msg:
                _GEMINI_CIRCUIT_BROKEN = True
                logger.warning("Gemini 429 quota limit hit. Circuit breaker activated for current run.")
                raise GeminiCircuitBrokenError(
                    f"429 Quota Exceeded for model '{self.model}'. Circuit breaker activated for current run."
                ) from exc
            raise exc


def get_chat_model(
    temperature: float = 0.1,
    streaming: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> BaseChatModel:
    """Get a chat model client for the requested provider."""
    resolved_provider = (provider or settings.llm_provider).lower()

    if resolved_provider == "groq":
        target_model = model or settings.groq_model
        if not settings.groq_api_key or not target_model:
            raise ValueError(
                "Groq API key or model is not configured. "
                "Set GROQ_API_KEY and GROQ_MODEL in your .env file."
            )
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=target_model,
            temperature=temperature,
            streaming=streaming,
        )

    if resolved_provider == "ollama":
        return ThrottledChatOllama(
            base_url=settings.ollama_base_url,
            model=model or settings.ollama_model,
            temperature=temperature,
        )

    if resolved_provider == "gemini":
        target_model = model or settings.gemini_model
        if not settings.gemini_api_key or not target_model:
            raise ValueError(
                "Gemini API key or model is not configured. "
                "Set GEMINI_API_KEY and GEMINI_MODEL in your .env file."
            )
        gemini_kwargs: dict[str, Any] = {}
        if "thinking" in target_model.lower() or "pro" in target_model.lower():
            gemini_kwargs["thinking_budget"] = 0
            gemini_kwargs["include_thoughts"] = False

        return ThrottledChatGoogleGenerativeAI(
            api_key=settings.gemini_api_key,
            model=target_model,
            temperature=temperature,
            streaming=streaming,
            max_retries=1,
            **gemini_kwargs,
        )

    if resolved_provider == "ollama_cloud":
        target_model = model or settings.ollama_cloud_model
        if not settings.ollama_cloud_base_url or not target_model:
            raise ValueError(
                "Ollama Cloud base URL or model is not configured. "
                "Set OLLAMA_CLOUD_BASE_URL and OLLAMA_CLOUD_MODEL in your .env file."
            )
        headers: dict[str, str] = {}
        if settings.ollama_cloud_api_key:
            headers["Authorization"] = f"Bearer {settings.ollama_cloud_api_key}"

        return ChatOllama(
            base_url=settings.ollama_cloud_base_url,
            model=target_model,
            temperature=temperature,
            headers=headers if headers else None,
            max_retries=3,
        )

    raise ValueError(
        f"Unknown LLM provider: {resolved_provider!r}. "
        "Supported values are 'groq', 'ollama', 'gemini', and 'ollama_cloud'."
    )


def get_structured_model(
    schema: Type[T],
    temperature: float = 0.0,
    provider: str | None = None,
    model: str | None = None,
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
    method: Literal["function_calling", "json_mode"] | None = None,
) -> Runnable[Any, T]:
    """Get a model configured to output structured objects matching the schema."""
    resolved_provider = (provider or settings.llm_provider).lower()
    resolved_method = method
    if resolved_method is None:
        resolved_method = "json_mode" if resolved_provider == "gemini" else "function_calling"

    llm = get_chat_model(
        temperature=temperature,
        streaming=False,
        provider=provider,
        model=model,
    )
    runnable = llm.with_structured_output(schema, method=resolved_method)
    
    if fallback_provider:
        fallback_llm = get_chat_model(
            temperature=temperature,
            streaming=False,
            provider=fallback_provider,
            model=fallback_model,
        )
        resolved_fallback_provider = fallback_provider.lower()
        resolved_fallback_method = method or ("json_mode" if resolved_fallback_provider == "gemini" else "function_calling")
        fallback_runnable = fallback_llm.with_structured_output(schema, method=resolved_fallback_method)
        runnable = runnable.with_fallbacks([fallback_runnable])
        
    return runnable
