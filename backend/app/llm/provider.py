from __future__ import annotations

from typing import Any, Type, TypeVar
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from app.config import settings

T = TypeVar("T", bound=BaseModel)


def get_chat_model(
    temperature: float = 0.1,
    streaming: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> BaseChatModel:
    """Get a chat model client for the requested provider.

    Provider and model are resolved in this priority order:
      1. Explicit arguments passed to this function (per-request overrides).
      2. ``settings.llm_provider`` / provider-specific model settings (env / .env).

    Supported providers:
      - ``"groq"``   — Cloud inference via the Groq API (requires GROQ_API_KEY).
      - ``"ollama"`` — Local inference via an Ollama server (no API key needed).

    Args:
        temperature: Sampling temperature.
        streaming: Whether to enable token streaming.
        provider: Provider name override. Defaults to ``settings.llm_provider``.
        model: Model name override. Defaults to the provider's default model
            from settings (``groq_model`` or ``ollama_model``).

    Returns:
        A ``BaseChatModel`` instance for the resolved provider.

    Raises:
        ValueError: If a required configuration is missing or an unknown
            provider is specified.
    """
    resolved_provider = (provider or settings.llm_provider).lower()

    if resolved_provider == "groq":
        if not settings.groq_api_key or not settings.groq_model:
            raise ValueError(
                "Groq API key or model is not configured. "
                "Set GROQ_API_KEY and GROQ_MODEL in your .env file."
            )
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=model or settings.groq_model,
            temperature=temperature,
            streaming=streaming,
        )

    if resolved_provider == "ollama":
        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=model or settings.ollama_model,
            temperature=temperature,
        )

    raise ValueError(
        f"Unknown LLM provider: {resolved_provider!r}. "
        "Supported values are 'groq' and 'ollama'."
    )


def get_structured_model(
    schema: Type[T],
    temperature: float = 0.0,
    provider: str | None = None,
    model: str | None = None,
) -> Runnable[Any, T]:
    """Get a model configured to output structured objects matching the schema."""
    llm = get_chat_model(
        temperature=temperature,
        streaming=False,
        provider=provider,
        model=model,
    )
    return llm.with_structured_output(schema)
