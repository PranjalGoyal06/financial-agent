from __future__ import annotations

from typing import Any, Optional, Union

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode, create_react_agent
from langgraph.store.base import BaseStore
from pydantic import BaseModel

from app.llm.provider import get_chat_model
from app.market_data.tools import MARKET_DATA_TOOLS
from app.portfolio.tools import get_ticker_recommendation_tool
from app.quant.tools import (
    compute_52w_distance_tool,
    compute_max_drawdown_tool,
    compute_returns_tool,
    compute_sharpe_ratio_tool,
    compute_volatility_tool,
)
from app.search.tools import web_search_tool
from app.ta.tools import (
    compute_ema_tool,
    compute_rsi_tool,
    compute_sma_tool,
)

# Unified toolset for the ReAct agent
AGENT_TOOLS = [
    *MARKET_DATA_TOOLS,
    web_search_tool,
    compute_returns_tool,
    compute_volatility_tool,
    compute_max_drawdown_tool,
    compute_sharpe_ratio_tool,
    compute_52w_distance_tool,
    compute_sma_tool,
    compute_ema_tool,
    compute_rsi_tool,
    get_ticker_recommendation_tool,
]

# Set handle_tool_error = True on all of them
for t in AGENT_TOOLS:
    t.handle_tool_error = True


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


def get_agent(
    portfolio_context: str,
    provider: str | None = None,
    model: str | None = None,
) -> Any:
    """Build and return a compiled LangGraph ReAct agent.

    A new agent is constructed per-request so the system prompt always reflects
    the current portfolio state. The LLM client and tool list are lightweight to
    instantiate — no network calls happen until the graph is invoked.

    Args:
        portfolio_context: Markdown table of the user's holdings, or a
            'No portfolio data available.' fallback string.
        provider: LLM provider override ('groq' or 'ollama'). Defaults to the
            server-level ``settings.llm_provider``.
        model: Model name override. Defaults to the provider's default model
            from settings.

    Returns:
        A compiled LangGraph graph that accepts ``{"messages": [...]}`` as input
        and supports ``astream_events(version="v2")``.
    """
    llm = get_chat_model(temperature=0.1, streaming=True, provider=provider, model=model)

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        portfolio_context=portfolio_context
    )

    return create_react_agent(
        llm,
        tools=SequentialToolNode(AGENT_TOOLS),
        prompt=SystemMessage(content=system_prompt),
        version="v1",
    )
