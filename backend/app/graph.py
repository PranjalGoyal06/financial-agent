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
from app.watchlist.tools import WATCHLIST_TOOLS

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
    *WATCHLIST_TOOLS,
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


from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import START, END, StateGraph
from app.compare.graph import compare_agent
from app.create_artifact.graph import create_artifact_graph
from app.recommend.graph import recommend_agent


class MasterState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    request_id: str
    llm_provider: str
    llm_model: str
    
    # compare
    tickers: list[str]
    focus: str | None
    market_data: dict | None
    
    # recommend
    ticker: str | None
    prior_research: dict | None
    
    # artifact
    intent: dict | None
    evidence_pack: dict | None
    markdown_content: str | None
    
    # outputs
    envelope: Any | None
    error: str | None


def get_state_modifier(portfolio_context: str):
    def state_modifier(state: dict) -> list[AnyMessage]:
        system_prompt = SystemMessage(content=_SYSTEM_PROMPT_TEMPLATE.format(portfolio_context=portfolio_context))
        
        trimmed = trim_messages(
            state["messages"],
            max_tokens=8000,
            strategy="last",
            token_counter=count_tokens_approximately,
            include_system=True,
            start_on="human",
        )
        return [system_prompt] + trimmed
        
    return state_modifier


def get_agent(
    portfolio_context: str,
    checkpointer: BaseCheckpointSaver,
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

    paisa_agent = create_react_agent(
        llm,
        tools=SequentialToolNode(AGENT_TOOLS),
        prompt=get_state_modifier(portfolio_context),
        version="v1",
    )
    
    workflow = StateGraph(MasterState)
    
    workflow.add_node("paisa_agent", paisa_agent)
    workflow.add_node("compare_agent", compare_agent)
    workflow.add_node("create_artifact_agent", create_artifact_graph)
    workflow.add_node("recommend_agent", recommend_agent)
    
    def route_request(state: MasterState) -> str:
        messages = state.get("messages", [])
        if not messages:
            return "paisa_agent"
            
        last_msg = messages[-1].content.strip()
        if last_msg.startswith("/compare"):
            return "compare_agent"
        elif last_msg.startswith("/create-artifact"):
            return "create_artifact_agent"
        elif last_msg.startswith("/recommend"):
            return "recommend_agent"
        else:
            return "paisa_agent"
            
    workflow.add_conditional_edges(START, route_request)
    
    workflow.add_edge("paisa_agent", END)
    workflow.add_edge("compare_agent", END)
    workflow.add_edge("create_artifact_agent", END)
    workflow.add_edge("recommend_agent", END)
    
    return workflow.compile(checkpointer=checkpointer)

