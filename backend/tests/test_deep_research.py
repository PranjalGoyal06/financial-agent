import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from app.research.graph import build_research_graph
from app.research.nodes.synthesis import macro_synthesis_node
from app.research.state import ResearchState
from app.evidence.schemas import EvidencePack, EvidenceItem

def test_build_research_graph_compiles() -> None:
    """Verify that the deep research StateGraph compiles and all edges are valid."""
    graph = build_research_graph()
    compiled = graph.compile()
    assert compiled is not None
    assert "planner" in compiled.nodes
    assert "collection" in compiled.nodes
    assert "macro_synthesis" in compiled.nodes
    assert "portfolio_synthesis" in compiled.nodes

@pytest.mark.asyncio
async def test_macro_synthesis_node_empty_evidence() -> None:
    """Verify macro_synthesis_node returns empty dict when evidence is missing."""
    state = {"macro_evidence": None} # type: ignore
    result = await macro_synthesis_node(state)
    assert result == {}

@pytest.mark.asyncio
async def test_macro_synthesis_node_with_evidence() -> None:
    """Verify macro_synthesis_node processes evidence correctly."""
    pack = EvidencePack(
        pack_id="test_pack",
        target="macro",
        created_at=datetime.now(timezone.utc),
        items=[
            EvidenceItem(
                id="item_1",
                type="news",
                source="tavily",
                fetched_at=datetime.now(timezone.utc),
                freshness="same_day",
                summary="Market is bullish."
            )
        ]
    )
    state = {"macro_evidence": pack} # type: ignore
    
    mock_res = AsyncMock()
    mock_res.analysis_markdown = "Test Analysis [item_1]"
    mock_res.key_drivers = ["driver1"]
    
    mock_model = AsyncMock()
    mock_model.ainvoke.return_value = mock_res
    
    with patch("app.research.nodes.synthesis.get_structured_model", return_value=mock_model):
        with patch("app.research.nodes.synthesis.validate_citations") as mock_val:
            mock_val.return_value.is_valid = True
            result = await macro_synthesis_node(state)
            
            assert "macro_synthesis" in result
            assert result["macro_synthesis"] == mock_res
