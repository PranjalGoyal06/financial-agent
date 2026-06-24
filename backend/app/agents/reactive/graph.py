from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.agents.reactive.nodes import (
    build_evidence_pack,
    compliance_check,
    data_quality_gate,
    execute_retrieval,
    final_reasoning,
    format_response,
    initialise_turn,
    load_baseline_context,
    parse_validate_output,
    persist_turn,
    plan_retrieval,
    validate_retrieval_plan,
)
from app.agents.reactive.state import ReactiveState

INITIALISE_TURN = "initialise_turn"
LOAD_BASELINE_CONTEXT = "load_baseline_context"
PLAN_RETRIEVAL = "plan_retrieval"
VALIDATE_RETRIEVAL_PLAN = "validate_retrieval_plan"
EXECUTE_RETRIEVAL = "execute_retrieval"
BUILD_EVIDENCE_PACK = "build_evidence_pack"
DATA_QUALITY_GATE = "data_quality_gate"
FINAL_REASONING = "final_reasoning"
PARSE_VALIDATE_OUTPUT = "parse_validate_output"
COMPLIANCE_CHECK = "compliance_check"
FORMAT_RESPONSE = "format_response"
PERSIST_TURN = "persist_turn"

NODE_ORDER = (
    INITIALISE_TURN,
    LOAD_BASELINE_CONTEXT,
    PLAN_RETRIEVAL,
    VALIDATE_RETRIEVAL_PLAN,
    EXECUTE_RETRIEVAL,
    BUILD_EVIDENCE_PACK,
    DATA_QUALITY_GATE,
    FINAL_REASONING,
    PARSE_VALIDATE_OUTPUT,
    COMPLIANCE_CHECK,
    FORMAT_RESPONSE,
    PERSIST_TURN,
)

NODE_FUNCTIONS: dict[str, Callable[[ReactiveState], dict[str, Any] | ReactiveState]] = {
    INITIALISE_TURN: initialise_turn,
    LOAD_BASELINE_CONTEXT: load_baseline_context,
    PLAN_RETRIEVAL: plan_retrieval,
    VALIDATE_RETRIEVAL_PLAN: validate_retrieval_plan,
    EXECUTE_RETRIEVAL: execute_retrieval,
    BUILD_EVIDENCE_PACK: build_evidence_pack,
    DATA_QUALITY_GATE: data_quality_gate,
    FINAL_REASONING: final_reasoning,
    PARSE_VALIDATE_OUTPUT: parse_validate_output,
    COMPLIANCE_CHECK: compliance_check,
    FORMAT_RESPONSE: format_response,
    PERSIST_TURN: persist_turn,
}


def route_after_plan_validation(state: ReactiveState) -> str:
    plan = state.get("retrieval_plan", {})
    if isinstance(plan, dict) and plan.get("intent") == "research_run_trigger":
        return FINAL_REASONING
    return EXECUTE_RETRIEVAL


def route_after_data_quality(state: ReactiveState) -> str:
    if state.get("data_quality_verdict") == "critical_failure":
        return PERSIST_TURN
    return FINAL_REASONING


def build_reactive_graph():
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise ImportError(
            "LangGraph is required to build the reactive graph. "
            "Install langgraph before calling build_reactive_graph()."
        ) from exc

    graph = StateGraph(ReactiveState)
    for node_name, node_fn in NODE_FUNCTIONS.items():
        graph.add_node(node_name, node_fn)

    graph.set_entry_point(INITIALISE_TURN)
    graph.add_edge(INITIALISE_TURN, LOAD_BASELINE_CONTEXT)
    graph.add_edge(LOAD_BASELINE_CONTEXT, PLAN_RETRIEVAL)
    graph.add_edge(PLAN_RETRIEVAL, VALIDATE_RETRIEVAL_PLAN)
    graph.add_conditional_edges(
        VALIDATE_RETRIEVAL_PLAN,
        route_after_plan_validation,
        {
            EXECUTE_RETRIEVAL: EXECUTE_RETRIEVAL,
            FINAL_REASONING: FINAL_REASONING,
        },
    )
    graph.add_edge(EXECUTE_RETRIEVAL, BUILD_EVIDENCE_PACK)
    graph.add_edge(BUILD_EVIDENCE_PACK, DATA_QUALITY_GATE)
    graph.add_conditional_edges(
        DATA_QUALITY_GATE,
        route_after_data_quality,
        {
            FINAL_REASONING: FINAL_REASONING,
            PERSIST_TURN: PERSIST_TURN,
        },
    )
    graph.add_edge(FINAL_REASONING, PARSE_VALIDATE_OUTPUT)
    graph.add_edge(PARSE_VALIDATE_OUTPUT, COMPLIANCE_CHECK)
    graph.add_edge(COMPLIANCE_CHECK, FORMAT_RESPONSE)
    graph.add_edge(FORMAT_RESPONSE, PERSIST_TURN)
    graph.add_edge(PERSIST_TURN, END)
    return graph.compile()


build_graph = build_reactive_graph
