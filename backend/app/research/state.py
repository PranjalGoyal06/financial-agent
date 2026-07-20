from __future__ import annotations

from typing import Annotated, TypedDict

from app.evidence.schemas import EvidencePack
from app.research.schemas import (
    MacroSynthesis,
    PortfolioSynthesis,
    SectorSynthesis,
    TickerSynthesis,
)


def merge_dict(left: dict, right: dict) -> dict:
    """Reducer that merges two dictionaries (e.g. dict of sector or ticker outputs)."""
    return {**left, **right}


def append_list(left: list, right: list) -> list:
    """Reducer that appends items to a list (e.g. list of errors)."""
    return left + right


class ResearchState(TypedDict):
    """The state graph state dictionary for the Deep Research workflow.

    Uses TypedDict fields with custom merge annotation handlers to support
    concurrent node updates during the fan-out collection and synthesis stages.
    """

    run_id: str
    user_id: str

    # ── Targets determined by the Planner Node ────────────────────────────────
    tickers: list[str]
    sectors: list[str]
    ticker_to_sector: dict[str, str]

    # ── Collected Evidence Packs ──────────────────────────────────────────────
    macro_evidence: EvidencePack | None
    sector_evidence: Annotated[dict[str, EvidencePack], merge_dict]
    ticker_evidence: Annotated[dict[str, EvidencePack], merge_dict]
    portfolio_evidence: EvidencePack | None

    # ── Generated Syntheses ───────────────────────────────────────────────────
    macro_synthesis: MacroSynthesis | None
    sector_synthesis: Annotated[dict[str, SectorSynthesis], merge_dict]
    ticker_synthesis: Annotated[dict[str, TickerSynthesis], merge_dict]
    portfolio_synthesis: PortfolioSynthesis | None

    # ── Error & Flow Tracking ────────────────────────────────────────────────
    errors: Annotated[list[str], append_list]
