from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.config import settings


class ChatState(TypedDict, total=False):
    user_id: str
    message: str
    response: str
    tokens: list[str]
    model: str
    used_local_response: bool


def split_tokens(text: str) -> list[str]:
    return re.findall(r"\S+\s*", text)


def local_response(message: str) -> str:
    cleaned = " ".join(message.strip().split())
    return (
        "SCALE Finance Agent is connected. "
        f"I received your message as {settings.default_user_id}: {cleaned}. "
        "The chat runtime is online and ready for the next layer of portfolio data."
    )


def call_llm(message: str) -> tuple[str, str, bool]:
    if not settings.groq_api_key or not settings.groq_model:
        return local_response(message), "local-response", True

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_groq import ChatGroq

    model = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.2,
    )
    try:
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are SCALE Finance Agent. Answer plainly and keep the "
                        "response focused on the user's message. Do not use tools, "
                        "market data, portfolio data, or recommendations yet."
                    )
                ),
                HumanMessage(content=message),
            ]
        )
    except Exception:
        return local_response(message), "local-response", True

    content = (
        response.content if isinstance(response.content, str) else str(response.content)
    )
    return content, settings.groq_model, False


def raw_llm_node(state: ChatState) -> dict[str, Any]:
    response, model_name, used_local_response = call_llm(state["message"])
    return {
        "response": response,
        "tokens": split_tokens(response),
        "model": model_name,
        "used_local_response": used_local_response,
    }


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("raw_llm_call", raw_llm_node)
    graph.set_entry_point("raw_llm_call")
    graph.add_edge("raw_llm_call", END)
    return graph.compile()


chat_graph = build_chat_graph()
