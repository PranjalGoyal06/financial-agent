from __future__ import annotations

import logging

from app.db import AsyncSessionLocal
from app.research.state import ResearchState
from app.research.store import save_research_artifact

logger = logging.getLogger(__name__)


from app.research.logger import get_run_logger

async def persist_node(state: ResearchState) -> dict:
    """Persist Node: Writes all synthesis products and collected evidence to PG & Chroma."""
    run_id = state.get("run_id") or "test_run"
    run_logger = get_run_logger(run_id)
    run_logger.log_event("persist", "node_start", f"Persist Node starting | run_id={run_id}")
    logger.info("Persist Node starting | run_id=%s", run_id)
    
    saved_counts = {"macro": 0, "sector": 0, "ticker": 0, "portfolio": 0}

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # ── 1. Persist Macro Synthesis ────────────────────────────────────
            macro = state.get("macro_synthesis")
            macro_pack = state.get("macro_evidence")
            if macro and macro_pack:
                await save_research_artifact(
                    session,
                    run_id=run_id,
                    artifact_type="macro",
                    target=None,
                    content_markdown=macro.analysis_markdown,
                    evidence_pack_json=macro_pack.model_dump_json(),
                )
                saved_counts["macro"] += 1

            # ── 2. Persist Sector Syntheses ───────────────────────────────────
            sector_dict = state.get("sector_synthesis") or {}
            sector_packs = state.get("sector_evidence") or {}
            for sector, sector_data in sector_dict.items():
                pack = sector_packs.get(sector)
                if pack:
                    await save_research_artifact(
                        session,
                        run_id=run_id,
                        artifact_type="sector",
                        target=sector,
                        content_markdown=sector_data.analysis_markdown,
                        evidence_pack_json=pack.model_dump_json(),
                    )
                    saved_counts["sector"] += 1

            # ── 3. Persist Ticker Syntheses ───────────────────────────────────
            ticker_dict = state.get("ticker_synthesis") or {}
            ticker_packs = state.get("ticker_evidence") or {}
            for ticker, ticker_data in ticker_dict.items():
                pack = ticker_packs.get(ticker)
                if pack:
                    await save_research_artifact(
                        session,
                        run_id=run_id,
                        artifact_type="ticker",
                        target=ticker,
                        content_markdown=ticker_data.analysis_markdown,
                        evidence_pack_json=pack.model_dump_json(),
                        recommendation=ticker_data.recommendation,
                        confidence_score=ticker_data.confidence_score,
                    )
                    saved_counts["ticker"] += 1

            # ── 4. Persist Portfolio Synthesis ────────────────────────────────
            portfolio = state.get("portfolio_synthesis")
            portfolio_pack = state.get("portfolio_evidence")
            if portfolio and portfolio_pack:
                await save_research_artifact(
                    session,
                    run_id=run_id,
                    artifact_type="portfolio",
                    target=None,
                    content_markdown=portfolio.analysis_markdown,
                    evidence_pack_json=portfolio_pack.model_dump_json(),
                )
                saved_counts["portfolio"] += 1

    run_logger.log_event("persist", "node_complete", f"Persist Node complete | saved_counts={saved_counts}", {"saved_counts": saved_counts})
    logger.info("Persist Node complete | Successfully saved all artifacts for run_id=%s", run_id)
    return {}
