from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GROQ_TESTS") != "1",
    reason="Set RUN_LIVE_GROQ_TESTS=1 to run live Groq connectivity tests.",
)


def test_groq_chat_completion_reachable() -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    model = os.environ.get("GROQ_MODEL")
    if not api_key or not model:
        pytest.skip("GROQ_API_KEY and GROQ_MODEL are required for live Groq tests.")

    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        pytest.fail(f"langchain_groq is not installed: {exc}")

    llm = ChatGroq(model=model, api_key=api_key, temperature=0, max_tokens=8)
    try:
        response = llm.invoke("Reply with exactly: ok")
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Groq chat completion request failed: {type(exc).__name__}: {exc}")

    content = str(getattr(response, "content", response)).strip().lower()
    assert content, "Groq returned an empty response body."
    assert "ok" in content