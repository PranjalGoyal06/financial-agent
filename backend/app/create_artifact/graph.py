from langgraph.graph import StateGraph, START, END
from app.create_artifact.state import CreateArtifactState
from app.create_artifact.nodes import (
    interpret_request_node,
    gather_evidence_node,
    generate_content_node,
    validate_citations_node,
    persist_file_node,
    render_card_node
)

def should_gather_evidence(state: CreateArtifactState):
    intent = state.get("intent")
    if intent and intent.needs_fresh_grounding:
        return "gather_evidence"
    return "generate_content"

# Build the graph
builder = StateGraph(CreateArtifactState)

# Add nodes
builder.add_node("interpret_request", interpret_request_node)
builder.add_node("gather_evidence", gather_evidence_node)
builder.add_node("generate_content", generate_content_node)
builder.add_node("validate_citations", validate_citations_node)
builder.add_node("persist_file", persist_file_node)
builder.add_node("render_card", render_card_node)

# Add edges
builder.add_edge(START, "interpret_request")
builder.add_conditional_edges(
    "interpret_request",
    should_gather_evidence,
    {
        "gather_evidence": "gather_evidence",
        "generate_content": "generate_content"
    }
)
builder.add_edge("gather_evidence", "generate_content")
builder.add_edge("generate_content", "validate_citations")
builder.add_edge("validate_citations", "persist_file")
builder.add_edge("persist_file", "render_card")
builder.add_edge("render_card", END)

create_artifact_graph = builder.compile()
