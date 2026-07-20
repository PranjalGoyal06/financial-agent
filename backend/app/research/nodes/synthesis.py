from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

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
    model = get_structured_model(MacroSynthesis, temperature=0.1)
    
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
    model = get_structured_model(SectorSynthesis, temperature=0.1)

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


# ── 3. Ticker Synthesis Node ───────────────────────────────────────────────────


async def _run_ticker_synthesis(ticker: str, state: ResearchState) -> tuple[str, TickerSynthesis | None]:
    """Execute LLM call for a single ticker."""
    pack = state.get("ticker_evidence", {}).get(ticker)
    if not pack or not pack.items:
        logger.warning("No evidence for ticker %r. Skipping synthesis.", ticker)
        return ticker, None

    # Get sector context for prompt
    sector = state.get("ticker_to_sector", {}).get(ticker)
    sector_summary = ""
    if sector:
        sec_synth = state.get("sector_synthesis", {}).get(sector)
        if sec_synth:
            sector_summary = sec_synth.analysis_markdown

    logger.info("Executing Ticker Synthesis for: %s", ticker)
    messages = get_ticker_messages(ticker, sector or "Unknown", sector_summary, pack)
    model = get_structured_model(TickerSynthesis, temperature=0.1)

    try:
        res = await model.ainvoke(messages)
        # Validate citations
        citation_text = (
            res.analysis_markdown + " " +
            " ".join(res.rationale) + " " +
            " ".join(res.risk_factors) + " " +
            res.bear_case
        )
        val = validate_citations(citation_text, pack)
        if not val.is_valid:
            logger.warning("Ticker %s synthesis contained invalid citations: %s", ticker, val.invalid_citations)
        return ticker, res
    except Exception as exc:
        logger.error("Ticker synthesis failed for %s: %s", ticker, exc)
        return ticker, None


async def ticker_synthesis_node(state: ResearchState) -> dict:
    """Synthesize ticker-level evidence for all watchlisted tickers in parallel."""
    tickers = state.get("tickers") or []
    if not tickers:
        return {}

    tasks = [_run_ticker_synthesis(tick, state) for tick in tickers]
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


# ── 4. Portfolio Synthesis Node ────────────────────────────────────────────────


async def portfolio_synthesis_node(state: ResearchState) -> dict:
    """CIO Node: Synthesize macro, sector, ticker outputs, and correlation matrices."""
    pack = state.get("portfolio_evidence")
    if not pack or not pack.items:
        logger.warning("Portfolio evidence pack is empty. Skipping portfolio synthesis.")
        return {}

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
        }
        for tick, data in state.get("ticker_synthesis", {}).items()
    }

    # Extract correlation matrix from computed metric (if present)
    correlation_matrix = {}
    corr_item = next((it for it in pack.items if it.id == "comp_portfolio_correlation"), None)
    if corr_item:
        try:
            data = json.loads(corr_item.summary)
            correlation_matrix = data.get("return_correlation_matrix", {})
        except Exception:
            pass

    logger.info("Executing Portfolio Synthesis...")
    messages = get_portfolio_messages(
        macro_outlook=macro_outlook,
        macro_drivers=macro_drivers,
        sector_outlines=sector_outlines,
        ticker_recs=ticker_recs,
        correlation_matrix=correlation_matrix,
        pack=pack,
    )
    model = get_structured_model(PortfolioSynthesis, temperature=0.1)

    try:
        res = await model.ainvoke(messages)
        # Validate citations
        val = validate_citations(
            res.analysis_markdown + " " + " ".join(res.allocation_adjustments),
            pack,
        )
        if not val.is_valid:
            logger.warning("Portfolio synthesis contained invalid citations: %s", val.invalid_citations)
        return {"portfolio_synthesis": res}
    except Exception as exc:
        logger.error("Portfolio synthesis node failed: %s", exc)
        return {"errors": [f"Portfolio synthesis failed: {exc}"]}
