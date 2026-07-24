from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.research.nodes.collection import (
    collect_macro_sector,
    collect_tickers_round1,
    collect_tickers_round2,
)
from app.research.nodes.discovery import discover_screen
from app.research.nodes.persist import persist_node
from app.research.nodes.planner import plan_macro_sector, plan_tickers
from app.research.nodes.reconciliation import reconcile_with_prior
from app.research.nodes.synthesis import (
    macro_synthesis_node,
    portfolio_synthesis_node,
    sector_synthesis_node,
    ticker_synthesis_node,
)
from app.research.nodes.triage import evidence_triage
from app.research.state import ResearchState


def build_research_graph() -> StateGraph:
    """Build and compile the Deep Research StateGraph."""
    workflow = StateGraph(ResearchState)

    # 1. Add all nodes
    workflow.add_node("plan_macro_sector", plan_macro_sector)
    workflow.add_node("collect_macro_sector", collect_macro_sector)
    workflow.add_node("discover_screen", discover_screen)
    workflow.add_node("plan_tickers", plan_tickers)
    workflow.add_node("collect_tickers_round1", collect_tickers_round1)
    workflow.add_node("evidence_triage", evidence_triage)
    workflow.add_node("collect_tickers_round2", collect_tickers_round2)
    workflow.add_node("macro_synthesis", macro_synthesis_node)
    workflow.add_node("sector_synthesis", sector_synthesis_node)
    workflow.add_node("ticker_synthesis", ticker_synthesis_node)
    workflow.add_node("reconcile_with_prior", reconcile_with_prior)
    workflow.add_node("portfolio_synthesis", portfolio_synthesis_node)
    workflow.add_node("persist", persist_node)

    # 2. Add edges (linear chain layout for single-execution guarantees)
    workflow.add_edge(START, "plan_macro_sector")
    workflow.add_edge("plan_macro_sector", "collect_macro_sector")
    
    # discover_screen runs here specifically because spillover extraction needs
    # macro/sector evidence; screener/competitor vectors have no such dependency 
    # and could theoretically run earlier if this ever needs to be parallelized.
    workflow.add_edge("collect_macro_sector", "discover_screen")
    
    workflow.add_edge("discover_screen", "plan_tickers")
    workflow.add_edge("plan_tickers", "collect_tickers_round1")
    workflow.add_edge("collect_tickers_round1", "evidence_triage")
    workflow.add_edge("evidence_triage", "collect_tickers_round2")
    workflow.add_edge("collect_tickers_round2", "macro_synthesis")
    workflow.add_edge("macro_synthesis", "sector_synthesis")
    workflow.add_edge("sector_synthesis", "ticker_synthesis")
    workflow.add_edge("ticker_synthesis", "reconcile_with_prior")
    workflow.add_edge("reconcile_with_prior", "portfolio_synthesis")
    workflow.add_edge("portfolio_synthesis", "persist")
    workflow.add_edge("persist", END)

    return workflow
