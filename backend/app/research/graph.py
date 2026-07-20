from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.research.nodes.collection import collect_all_node
from app.research.nodes.persist import persist_node
from app.research.nodes.planner import plan_node
from app.research.nodes.synthesis import (
    macro_synthesis_node,
    portfolio_synthesis_node,
    sector_synthesis_node,
    ticker_synthesis_node,
)
from app.research.state import ResearchState


def build_research_graph() -> StateGraph:
    """Build and compile the Deep Research StateGraph.

    Flow:
              START
                │
                ▼
            [ planner ]
                │
                ▼
          [ collection ]
           /          \
          ▼            ▼
     [ macro ]      [ sector ]
          │            │
          │            ▼
          │        [ ticker ]
          \            /
           ▼          ▼
         [ portfolio ]
                │
                ▼
           [ persist ]
                │
                ▼
               END
    """
    workflow = StateGraph(ResearchState)

    # 1. Add all nodes
    workflow.add_node("planner", plan_node)
    workflow.add_node("collection", collect_all_node)
    workflow.add_node("macro_synthesis", macro_synthesis_node)
    workflow.add_node("sector_synthesis", sector_synthesis_node)
    workflow.add_node("ticker_synthesis", ticker_synthesis_node)
    workflow.add_node("portfolio_synthesis", portfolio_synthesis_node)
    workflow.add_node("persist", persist_node)

    # 2. Add edges (linear chain layout for single-execution guarantees)
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "collection")
    workflow.add_edge("collection", "macro_synthesis")
    workflow.add_edge("macro_synthesis", "sector_synthesis")
    workflow.add_edge("sector_synthesis", "ticker_synthesis")
    workflow.add_edge("ticker_synthesis", "portfolio_synthesis")
    workflow.add_edge("portfolio_synthesis", "persist")
    workflow.add_edge("persist", END)

    return workflow
