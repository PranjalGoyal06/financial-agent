from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.recommend.state import RecommendState
from app.recommend.nodes import (
    parse_input_node,
    fetch_data_node,
    generate_card_node,
    audit_persist_node,
)

def build_recommend_graph() -> StateGraph:
    """Build and compile the /recommend StateGraph."""
    workflow = StateGraph(RecommendState)

    workflow.add_node("parse_input", parse_input_node)
    workflow.add_node("fetch_data", fetch_data_node)
    workflow.add_node("generate_card", generate_card_node)
    workflow.add_node("audit_persist", audit_persist_node)

    # Standard flow
    workflow.add_edge(START, "parse_input")
    
    # Conditional edge out of parse_input
    def check_error(state: RecommendState) -> str:
        if state.get("error"):
            return END
        return "fetch_data"

    workflow.add_conditional_edges("parse_input", check_error)
    
    # Conditional edge out of fetch_data
    def check_fetch_error(state: RecommendState) -> str:
        if state.get("error"):
            return END
        return "generate_card"
        
    workflow.add_conditional_edges("fetch_data", check_fetch_error)
    
    # Conditional edge out of generate
    def check_gen_error(state: RecommendState) -> str:
        if state.get("error"):
            return END
        return "audit_persist"
        
    workflow.add_conditional_edges("generate_card", check_gen_error)
    
    workflow.add_edge("audit_persist", END)

    return workflow.compile()

# Provide a singleton instance since the graph itself is stateless (state is passed per run)
recommend_agent = build_recommend_graph()
