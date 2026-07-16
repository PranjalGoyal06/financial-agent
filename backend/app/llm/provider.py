from __future__ import annotations

from typing import Any, Type, TypeVar
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq

from app.config import settings

T = TypeVar("T", bound=BaseModel)


def get_chat_model(
    temperature: float = 0.1,
    streaming: bool = False,
) -> BaseChatModel:
    """Get the configured LLM chat model client.

    Reads configuration dynamically from settings. Currently defaults to Groq,
    but can be extended to other providers (OpenAI, Anthropic, Ollama) by adding
    a settings.llm_provider key.
    """
    if not settings.groq_api_key or not settings.groq_model:
        raise ValueError(
            "Groq API key or model is not configured. "
            "Set GROQ_API_KEY and GROQ_MODEL in your .env file."
        )

    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=temperature,
        streaming=streaming,
    )


def get_structured_model(
    schema: Type[T],
    temperature: float = 0.0,
) -> Runnable[Any, T]:
    """Get a model configured to output structured objects matching the schema."""
    llm = get_chat_model(temperature=temperature, streaming=False)
    return llm.with_structured_output(schema)
