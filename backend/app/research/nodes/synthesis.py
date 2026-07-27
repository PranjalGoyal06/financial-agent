from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.evidence.lib import validate_citations
from app.llm.provider import get_structured_model
from app.research.prompts.macro import get_macro_messages
from app.research.prompts.portfolio import get_portfolio_messages
from app.research.prompts.sector import get_sector_messages
from app.research.prompts.ticker import get_ticker_messages
from app.research.schemas import (
    MacroSynthesis,
    PortfolioSynthesis,
    SectorSynthesis,
    TickerSynthesis,
)
from app.research.state import ResearchState

logger = logging.getLogger(__name__)


# ── 1. Macro Synthesis Node ────────────────────────────────────────────────────


async def macro_synthesis_node(state: ResearchState) -> dict:
    """Synthesize market-wide macro evidence into a MacroSynthesis model."""
    pack = state.get("macro_evidence")
    if not pack or not pack.items:
        logger.warning("Macro evidence pack is empty. Skipping macro synthesis.")
        return {}

    logger.info("Executing Macro Synthesis...")
    messages = get_macro_messages(pack)
    model = get_structured_model(MacroSynthesis, temperature=0.1, provider="ollama_cloud", fallback_provider="ollama")
    
    try:
        res = await model.ainvoke(messages)
        # Validate citations
        val = validate_citations(res.analysis_markdown + " ".join(res.key_drivers), pack)
        if not val.is_valid:
            logger.warning("Macro synthesis contained invalid citations: %s", val.invalid_citations)
        return {"macro_synthesis": res}
    except Exception as exc:
        logger.error("Macro synthesis node failed: %s", exc)
        return {"errors": [f"Macro synthesis failed: {exc}"]}


# ── 2. Sector Synthesis Node ───────────────────────────────────────────────────


async def _run_sector_synthesis(sector: str, state: ResearchState) -> tuple[str, SectorSynthesis | None]:
    """Execute LLM call for a single sector."""
    pack = state.get("sector_evidence", {}).get(sector)
    if not pack or not pack.items:
        logger.warning("No evidence for sector %r. Skipping synthesis.", sector)
        return sector, None

    logger.info("Executing Sector Synthesis for: %s", sector)
    messages = get_sector_messages(sector, pack)
    model = get_structured_model(SectorSynthesis, temperature=0.1, provider="ollama_cloud", fallback_provider="ollama")

    try:
        res = await model.ainvoke(messages)
        # Validate citations
        val = validate_citations(res.analysis_markdown + " ".join(res.key_drivers), pack)
        if not val.is_valid:
            logger.warning("Sector %s synthesis contained invalid citations: %s", sector, val.invalid_citations)
        return sector, res
    except Exception as exc:
        logger.error("Sector synthesis failed for %s: %s", sector, exc)
        return sector, None


async def sector_synthesis_node(state: ResearchState) -> dict:
    """Synthesize sector-level evidence for all active sectors in parallel."""
    sectors = state.get("sectors") or []
    if not sectors:
        return {}

    tasks = [_run_sector_synthesis(sec, state) for sec in sectors]
    results = await asyncio.gather(*tasks)

    updates: dict = {}
    errors: list[str] = []
    for sector, res in results:
        if res:
            updates[sector] = res
        else:
            errors.append(f"Sector synthesis failed for {sector}")

    result: dict[str, Any] = {"sector_synthesis": updates}
    if errors:
        result["errors"] = errors
    return result


from langchain_core.prompts import ChatPromptTemplate
from app.research.schemas import FrontierTickerSynthesis

class _DraftCritique(BaseModel):
    weaknesses: list[str] = Field(description="List of weak points in the draft thesis.")
    
async def _run_ticker_synthesis(ticker: str, state: ResearchState) -> tuple[str, TickerSynthesis | None]:
    """Execute 5-step LLM call for a single ticker."""
    pack = state.get("ticker_evidence", {}).get(ticker)
    if not pack or not pack.items:
        logger.warning("No evidence for ticker %r. Skipping synthesis.", ticker)
        return ticker, None
        
    sector = state.get("ticker_to_sector", {}).get(ticker)
    sector_summary = "DEGRADED_MACRO_ONLY: Sector context not available for discovered ticker."
    if sector:
        sec_synth = state.get("sector_synthesis", {}).get(sector)
        if sec_synth:
            sector_summary = sec_synth.analysis_markdown

    from app.db import AsyncSessionLocal
    from app.models import InstrumentModel
    from sqlalchemy import select

    metadata_text = "Metadata not available."
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(InstrumentModel).where(InstrumentModel.ticker == ticker)
            res = await session.execute(stmt)
            inst = res.scalar_one_or_none()
            if inst:
                metadata_text = f"Company: {inst.company_name or inst.display_name or ticker}\n"
                metadata_text += f"Industry: {inst.industry or 'Unknown'}\n"
                metadata_text += f"Market Cap: {inst.market_cap_bucket or 'Unknown'}\n"
                metadata_text += f"Summary: {inst.summary or 'No summary available.'}"
    except Exception as e:
        logger.warning("Failed to fetch instrument metadata for %s: %s", ticker, e)

    logger.info("Executing Ticker Synthesis for: %s", ticker)
    
    # Pre-render evidence
    evidence_text = "\n".join(f"[{item.id}] {item.summary}" for item in pack.items)

    # 3a. Draft Thesis (Bear-case first - Tier 2 Nemotron)
    draft_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an equity analyst. Draft a comprehensive thesis. Crucially, start with the BEAR CASE and KILL THE COMPANY risk before any bull case. Return the TickerSynthesis JSON."),
        ("user", "Ticker: {ticker}\n\nCompany Metadata:\n{metadata}\n\nSector Context: {sector_summary}\n\nEvidence:\n{evidence}")
    ])
    draft_model = get_structured_model(TickerSynthesis, temperature=0.1, provider="ollama_cloud", fallback_provider="ollama")
    
    try:
        draft: TickerSynthesis = await (draft_prompt | draft_model).ainvoke({
            "ticker": ticker,
            "metadata": metadata_text,
            "sector_summary": sector_summary,
            "evidence": evidence_text
        })
    except Exception as exc:
        logger.error("Ticker %s draft synthesis failed: %s", ticker, exc)
        return ticker, None

    # 3b. Adversarial Critique (Tier 2 Nemotron)
    critique_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a red-team analyst. Critique this draft thesis. Identify logical leaps, missing risks, or unwarranted optimism. Extract weaknesses as a list of strings."),
        ("user", "Draft Thesis:\n{draft}\n\nEvidence:\n{evidence}")
    ])
    critique_model = get_structured_model(_DraftCritique, temperature=0.2, provider="ollama_cloud", fallback_provider="ollama")
    
    try:
        critique_res: _DraftCritique = await (critique_prompt | critique_model).ainvoke({
            "draft": draft.model_dump_json(),
            "evidence": evidence_text
        })
        critiques = critique_res.weaknesses
    except Exception as exc:
        logger.warning("Ticker %s critique failed: %s", ticker, exc)
        critiques = []

    # 3c. Revised Thesis (Tier 2 Nemotron)
    revise_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are the original equity analyst. Revise your draft thesis to address the red-team critiques. Defend your stance or adjust your recommendation/confidence. Return the TickerSynthesis JSON."),
        ("user", "Draft Thesis:\n{draft}\n\nCritiques:\n{critiques}\n\nEvidence:\n{evidence}")
    ])
    revise_model = get_structured_model(TickerSynthesis, temperature=0.1, provider="ollama_cloud", fallback_provider="ollama")
    
    try:
        revised: TickerSynthesis = await (revise_prompt | revise_model).ainvoke({
            "draft": draft.model_dump_json(),
            "critiques": "\n".join(critiques),
            "evidence": evidence_text
        })
    except Exception as exc:
        logger.error("Ticker %s revise synthesis failed: %s", ticker, exc)
        return ticker, None

    # 3d. Frontier Judgment (CIO - Tier 3 Gemini)
    cio_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are the Chief Investment Officer. Review the analyst's revised thesis. You hold final veto power. Adjust the recommendation or confidence if the evidence doesn't support the analyst's conviction. Explicitly state what changed and why. Return the FrontierTickerSynthesis JSON."),
        ("user", "Revised Thesis:\n{revised}\n\nEvidence:\n{evidence}")
    ])
    cio_model = get_structured_model(
        FrontierTickerSynthesis, 
        temperature=0.1, 
        provider="gemini",
        fallback_provider="ollama_cloud"
    )
    
    final_output: TickerSynthesis = revised
    try:
        cio_judgment: FrontierTickerSynthesis = await (cio_prompt | cio_model).ainvoke({
            "revised": revised.model_dump_json(),
            "evidence": evidence_text
        })
        # Merge frontier changes into final output
        final_output.recommendation = cio_judgment.recommendation
        final_output.confidence_score = cio_judgment.confidence_score
        final_output.target_price = cio_judgment.target_price
        # Add the frontier reasoning to the rationale
        final_output.rationale.insert(0, f"CIO Judgment: {cio_judgment.what_changed_and_why}")
    except Exception as exc:
        logger.warning("Ticker %s CIO Judgment failed (all retries/fallbacks exhausted). Falling back to Analyst Revised Thesis: %s", ticker, exc)
        final_output.frontier_judgment_unavailable = True

    # Assign provenance fields based on state
    discovered_tickers = state.get("discovered_tickers", [])
    if ticker in discovered_tickers:
        final_output.source = "discovered"
        # We could lookup the exact vector/reason from discovery node if we stored it,
        # but for now we just mark it discovered.
        final_output.discovery_reason = "Surfaced via automated discovery scanning."

    # Validate citations on the final output
    citation_text = (
        final_output.analysis_markdown + " " +
        " ".join(final_output.rationale) + " " +
        " ".join(final_output.risk_factors) + " " +
        final_output.bear_case
    )
    val = validate_citations(citation_text, pack)
    if not val.is_valid:
        logger.warning("Ticker %s synthesis contained invalid citations: %s", ticker, val.invalid_citations)
        
    return ticker, final_output


async def ticker_synthesis_node(state: ResearchState) -> dict:
    """Synthesize ticker-level evidence using a 5-step pipeline."""
    tickers = state.get("tickers") or []
    if not tickers:
        return {}

    sem = asyncio.Semaphore(2)

    async def _paced_synthesis(ticker_symbol: str):
        async with sem:
            res = await _run_ticker_synthesis(ticker_symbol, state)
            await asyncio.sleep(1.0)
            return res

    tasks = [_paced_synthesis(tick) for tick in tickers]
    results = await asyncio.gather(*tasks)

    updates: dict = {}
    errors: list[str] = []
    for ticker, res in results:
        if res:
            updates[ticker] = res
        else:
            errors.append(f"Ticker synthesis failed for {ticker}")

    result: dict[str, Any] = {"ticker_synthesis": updates}
    if errors:
        result["errors"] = errors
    return result


from app.evidence.schemas import EvidencePack, EvidenceItem
from datetime import datetime, timezone
import yfinance as yf
from app.quant.lib import compute_correlation_matrix

async def portfolio_synthesis_node(state: ResearchState) -> dict:
    """CIO Node: Synthesize macro, sector, ticker outputs, and correlation matrices."""
    run_id = state.get("run_id") or "test_run"
    logger.info("Executing Portfolio Synthesis...")

    # Extract inputs from state
    macro_outlook = "neutral"
    macro_drivers: list[str] = []
    macro_synthesis = state.get("macro_synthesis")
    if macro_synthesis:
        macro_outlook = macro_synthesis.outlook
        macro_drivers = macro_synthesis.key_drivers

    sector_outlines = {
        sec: {
            "outlook": data.outlook,
            "analysis_markdown": data.analysis_markdown,
        }
        for sec, data in state.get("sector_synthesis", {}).items()
    }

    ticker_recs = {
        tick: {
            "recommendation": data.recommendation,
            "confidence_score": data.confidence_score,
            "rationale": "; ".join(data.rationale),
            "source": getattr(data, "source", "watchlist"),
        }
        for tick, data in state.get("ticker_synthesis", {}).items()
    }

    # Fetch 90 days of data for the correlation matrix on the fly for all synthesized tickers
    fetched_at = datetime.now(timezone.utc)
    correlation_matrix = {}
    valid_tickers = list(ticker_recs.keys())
    
    if len(valid_tickers) > 1:
        try:
            data = await asyncio.to_thread(yf.download, valid_tickers, period="3mo", progress=False)
            if not data.empty and 'Close' in data:
                closes = data['Close']
                # compute_correlation_matrix expects dict[str, list[float]]
                ticker_bars = {}
                for tick in valid_tickers:
                    if tick in closes:
                        ticker_bars[tick] = closes[tick].dropna().values.tolist()
                
                if ticker_bars:
                    correlation_matrix = compute_correlation_matrix(ticker_bars)
        except Exception as e:
            logger.warning("Failed to compute portfolio correlation matrix: %s", e)

    # Build portfolio evidence pack
    items = []
    if correlation_matrix:
        items.append(
            EvidenceItem(
                id="comp_portfolio_correlation",
                type="computed_metric",
                source="internal_computation",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=json.dumps({"return_correlation_matrix": correlation_matrix}),
            )
        )
        
    macro_pack = state.get("macro_evidence")
    if macro_pack and macro_pack.items:
        macro_summaries = [it.summary for it in macro_pack.items[:2]]
        items.append(
            EvidenceItem(
                id="macro_portfolio_context",
                type="prior_artifact",
                source="internal_computation",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=f"Top Macro context lines: {' | '.join(macro_summaries)}",
            )
        )
        
    # Inject drift reports into evidence if any exist
    drift_reports = state.get("drift_reports", {})
    if drift_reports:
        items.append(
            EvidenceItem(
                id="reconciliation_drift_reports",
                type="computed_metric",
                source="reconciliation_node",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=json.dumps({"drift_reports": drift_reports}),
            )
        )

    pack = EvidencePack(
        pack_id=f"{run_id}_portfolio",
        target="portfolio",
        items=items,
        created_at=fetched_at,
    )

    messages = get_portfolio_messages(
        macro_outlook=macro_outlook,
        macro_drivers=macro_drivers,
        sector_outlines=sector_outlines,
        ticker_recs=ticker_recs,
        correlation_matrix=correlation_matrix,
        pack=pack,
    )
    model = get_structured_model(PortfolioSynthesis, temperature=0.1, provider="gemini", fallback_provider="ollama_cloud")

    try:
        res = await model.ainvoke(messages)
        # Validate citations
        val = validate_citations(
            res.analysis_markdown + " " + " ".join(res.allocation_adjustments),
            pack,
        )
        if not val.is_valid:
            logger.warning("Portfolio synthesis contained invalid citations: %s", val.invalid_citations)
        return {
            "portfolio_synthesis": res,
            "portfolio_evidence": pack  # Pass to state for persist_node
        }
    except Exception as exc:
        logger.error("Portfolio synthesis node failed: %s", exc)
        return {"errors": [f"Portfolio synthesis failed: {exc}"]}
