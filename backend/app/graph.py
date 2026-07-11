from __future__ import annotations

from typing import Any, Optional, Union

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langgraph.prebuilt import ToolNode, create_react_agent
from langgraph.store.base import BaseStore
from pydantic import BaseModel

from app.config import settings
from app.market_data.tools import MARKET_DATA_TOOLS

# ── System prompt ──────────────────────────────────────────────────────────────
#
# {portfolio_context} is a runtime placeholder — it is injected into the first
# SystemMessage at invocation time, not baked into the compiled graph. This means
# the graph singleton stays valid across users/requests even though each user has
# a different portfolio.

_SYSTEM_PROMPT_TEMPLATE = """\
You are PAISA — Portfolio Advisor and Investment Strategist Agent.
You have access to real-time and historical Indian equity market data tools.

GROUND RULES:
- Never fabricate prices, returns, or financial figures. Always call the
  appropriate tool to fetch live data before citing any number.
- When you cite a price, always include the fetched_at timestamp so the user
  knows how fresh the data is.
- For ambiguous company names, resolve the ticker first. Prefer NSE (.NS) over
  BSE (.BO) unless the user specifies otherwise.
- Keep answers concise and grounded. Use markdown formatting.

USER'S PORTFOLIO:
{portfolio_context}
"""


class SequentialToolNode(ToolNode):
    """A custom ToolNode that executes tool calls sequentially rather than in parallel.
    This resolves race conditions and off-by-one rendering issues in the streaming UI.
    """
    def _func(
        self,
        input: Union[
            list[AnyMessage],
            dict[str, Any],
            BaseModel,
        ],
        config: RunnableConfig,
        *,
        store: Optional[BaseStore],
    ) -> Any:
        tool_calls, input_type = self._parse_input(input, store)
        outputs = []
        for call in tool_calls:
            outputs.append(self._run_one(call, input_type, config))
        return self._combine_tool_outputs(outputs, input_type)

    async def _afunc(
        self,
        input: Union[
            list[AnyMessage],
            dict[str, Any],
            BaseModel,
        ],
        config: RunnableConfig,
        *,
        store: Optional[BaseStore],
    ) -> Any:
        tool_calls, input_type = self._parse_input(input, store)
        outputs = []
        for call in tool_calls:
            outputs.append(await self._arun_one(call, input_type, config))
        return self._combine_tool_outputs(outputs, input_type)


# ── Agent factory ──────────────────────────────────────────────────────────────


def get_agent(portfolio_context: str) -> Any:
    """Build and return a compiled LangGraph ReAct agent.

    A new agent is constructed per-request so the system prompt always reflects
    the current portfolio state. The LLM client and tool list are lightweight to
    instantiate — no network calls happen until the graph is invoked.

    Args:
        portfolio_context: Markdown table of the user's holdings, or a
            'No portfolio data available.' fallback string.

    Returns:
        A compiled LangGraph graph that accepts ``{"messages": [...]}`` as input
        and supports ``astream_events(version="v2")``.
    """
    if not settings.groq_api_key or not settings.groq_model:
        raise ValueError(
            "Groq API key or model is not configured. "
            "Set GROQ_API_KEY and GROQ_MODEL in your .env file."
        )

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.1,
        streaming=True,
    )

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        portfolio_context=portfolio_context
    )

    return create_react_agent(
        llm,
        tools=SequentialToolNode(MARKET_DATA_TOOLS),
        prompt=SystemMessage(content=system_prompt),
        version="v1",
    )
