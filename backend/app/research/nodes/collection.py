from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, cast
from datetime import datetime, timezone

from app.evidence.schemas import EvidenceItem, EvidencePack
from app.market_data.provider import (
    ProviderError,
    TickerNotFoundError,
    YFinanceProvider,
)
from app.quant.lib import compute_all_metrics, compute_correlation_matrix
from app.research.state import ResearchState
from app.research.store import search_prior_artifacts
from app.search.client import search as search_tavily
from app.ta.lib import compute_rsi, compute_sma

logger = logging.getLogger(__name__)
_provider = YFinanceProvider()


# ── 1. Macro Collection ────────────────────────────────────────────────────────


async def _collect_macro(run_id: str) -> EvidencePack:
    """Collect macro-level research evidence."""
    query = "India equity market macro outlook this week"
    fetched_at = datetime.now(timezone.utc)
    
    # Live Tavily search
    items = await search_tavily(query, max_results=5)
    
    return EvidencePack(
        pack_id=f"{run_id}_macro",
        target="macro",
        items=items,
        created_at=fetched_at,
    )


# ── 2. Sector Collection ───────────────────────────────────────────────────────


async def _collect_sector(run_id: str, sector: str) -> tuple[str, EvidencePack]:
    """Collect industry/sector level research evidence."""
    query = f"{sector} sector trends India equity market"
    fetched_at = datetime.now(timezone.utc)
    
    # Live Tavily search
    items = await search_tavily(query, max_results=4)
    
    pack = EvidencePack(
        pack_id=f"{run_id}_sector_{sector.lower().replace(' ', '_')}",
        target=sector,
        items=items,
        created_at=fetched_at,
    )
    return sector, pack


# ── 3. Ticker Collection ───────────────────────────────────────────────────────


def _fetch_ticker_yfinance(ticker: str) -> tuple[dict, list, dict | None]:
    """Blocking yfinance scraper methods executed in a background thread."""
    quote = _provider.get_quote(ticker)
    historical = _provider.get_historical(ticker, period="1y", interval="1d")
    try:
        fundamentals = _provider.get_fundamentals(ticker)
    except Exception as exc:
        logger.warning("Failed to retrieve fundamentals for %s: %s", ticker, exc)
        fundamentals = None
    return quote.model_dump(), historical.bars, (fundamentals.model_dump() if fundamentals else None)


async def _collect_ticker(run_id: str, ticker: str) -> tuple[str, EvidencePack, list]:
    """Collect ticker-specific news, quant/TA indicators, and fundamentals."""
    fetched_at = datetime.now(timezone.utc)
    items = []
    bars = []

    # 1. Gather Tavily, yfinance, and Chroma retrieval in parallel
    try:
        tavily_task = search_tavily(f"{ticker} stock news analysis", max_results=4)
        chroma_task = search_prior_artifacts(f"{ticker} investment research analysis", limit=3, target=ticker)
        yf_task = asyncio.to_thread(_fetch_ticker_yfinance, ticker)

        news_items, prior_items, yf_results = await asyncio.gather(tavily_task, chroma_task, yf_task)
        items.extend(news_items)
        items.extend(prior_items)
        
        quote_dict, bars, fund_dict = yf_results
    except (TickerNotFoundError, ProviderError) as exc:
        logger.error("Market data fetch failed for target %s: %s", ticker, exc)
        # Populate empty pack rather than crashing the research workflow
        pack = EvidencePack(pack_id=f"{run_id}_ticker_{ticker}", target=ticker, items=[], created_at=fetched_at)
        return ticker, pack, []

    # 2. Add yfinance quote item
    items.append(
        EvidenceItem(
            id=f"mkt_quote_{ticker.lower().replace('.', '_')}",
            type="market_data",
            source="yfinance",
            fetched_at=fetched_at,
            freshness="same_day",
            summary=(
                f"Current Price: INR {quote_dict.get('price')} | "
                f"Day Change: {quote_dict.get('day_change_pct'):+.2f}% | "
                f"Volume: {quote_dict.get('volume')} | "
                f"52W Range: {quote_dict.get('week52_low')} - {quote_dict.get('week52_high')}"
            ),
        )
    )

    # 3. Add fundamentals item (if available)
    if fund_dict:
        items.append(
            EvidenceItem(
                id=f"mkt_fund_{ticker.lower().replace('.', '_')}",
                type="market_data",
                source="yfinance",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=(
                    f"Valuation: P/E={fund_dict.get('pe_ratio') or 'N/A'}, "
                    f"P/B={fund_dict.get('pb_ratio') or 'N/A'}, "
                    f"P/S={fund_dict.get('ps_ratio') or 'N/A'}, "
                    f"PEG={fund_dict.get('peg_ratio') or 'N/A'} | "
                    f"Per-Share: EPS(ttm)={fund_dict.get('eps_ttm') or 'N/A'}, "
                    f"Book Value={fund_dict.get('book_value_per_share') or 'N/A'} | "
                    f"Margins: Operating={fund_dict.get('operating_margin') or 'N/A'}, "
                    f"Net Profit={fund_dict.get('profit_margin') or 'N/A'} | "
                    f"Returns: ROE={fund_dict.get('return_on_equity') or 'N/A'}, "
                    f"ROA={fund_dict.get('return_on_assets') or 'N/A'} | "
                    f"Growth (yoy): Rev Growth={fund_dict.get('revenue_growth') or 'N/A'}, "
                    f"Earnings Growth={fund_dict.get('earnings_growth') or 'N/A'} | "
                    f"Dividends: Yield={fund_dict.get('dividend_yield') or 'N/A'}, "
                    f"Payout Ratio={fund_dict.get('payout_ratio') or 'N/A'} | "
                    f"Market Cap: INR {fund_dict.get('market_cap') or 'N/A'} | "
                    f"Analyst Target: INR {fund_dict.get('analyst_target_price') or 'N/A'}"
                ),
            )
        )

    # 4. Compute and add quant/TA metrics
    if bars:
        metrics = compute_all_metrics(bars)
        rsi_list = compute_rsi(bars, window=14)
        sma50_list = compute_sma(bars, window=50)

        # Get latest technicals
        latest_rsi = next((v for v in reversed(rsi_list) if v is not None), None)
        latest_sma50 = next((v for v in reversed(sma50_list) if v is not None), None)

        metrics_summary = {
            "total_return_6mo": metrics.get("total_return"),
            "cagr_1y": metrics.get("cagr"),
            "volatility_annualized": metrics.get("volatility_annualized"),
            "max_drawdown": metrics.get("max_drawdown"),
            "sharpe_ratio": metrics.get("sharpe_ratio"),
            "distance_from_52w_high": metrics.get("pct_from_high"),
            "distance_from_52w_low": metrics.get("pct_from_low"),
            "rsi_14": latest_rsi,
            "sma_50": latest_sma50,
        }

        items.append(
            EvidenceItem(
                id=f"comp_{ticker.lower().replace('.', '_')}",
                type="computed_metric",
                source="internal_computation",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=json.dumps(metrics_summary),
            )
        )

    pack = EvidencePack(
        pack_id=f"{run_id}_ticker_{ticker}",
        target=ticker,
        items=items,
        created_at=fetched_at,
    )
    return ticker, pack, bars


# ── 4. Portfolio Collection ────────────────────────────────────────────────────


def _collect_portfolio(
    run_id: str,
    ticker_bars: dict[str, list],
    macro_pack: EvidencePack,
) -> EvidencePack:
    """Build the evidence pack for portfolio level synthesis."""
    fetched_at = datetime.now(timezone.utc)
    items = []

    # 1. Add correlation matrix computed over historical closes
    if ticker_bars:
        matrix = compute_correlation_matrix(ticker_bars)
        items.append(
            EvidenceItem(
                id="comp_portfolio_correlation",
                type="computed_metric",
                source="internal_computation",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=json.dumps({"return_correlation_matrix": matrix}),
            )
        )

    # 2. Extract macro details to populate the portfolio evidence context
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

    return EvidencePack(
        pack_id=f"{run_id}_portfolio",
        target="portfolio",
        items=items,
        created_at=fetched_at,
    )


# ── 5. Main Collection Node ────────────────────────────────────────────────────


async def collect_all_node(state: ResearchState) -> dict:
    """Collection Node: Executes fan-out evidence gathering in parallel.

    Queries Tavily news searches, yfinance prices and ratios, Chroma past
    research, and calculates quantitative/TA stats asynchronously.
    """
    run_id = state.get("run_id") or "test_run"
    tickers = state.get("tickers") or []
    sectors = state.get("sectors") or []
    
    logger.info(
        "Collection Node starting | tickers=%s sectors=%s run_id=%s",
        tickers,
        sectors,
        run_id,
    )

    errors = []

    # Setup parallel operations
    macro_task = _collect_macro(run_id)
    sector_tasks = [_collect_sector(run_id, sec) for sec in sectors]
    ticker_tasks = [_collect_ticker(run_id, tick) for tick in tickers]

    # Execute all
    logger.info("Executing fan-out gather operations...")
    gathered = await asyncio.gather(macro_task, *sector_tasks, *ticker_tasks, return_exceptions=True)

    # Parse gathered results
    idx = 0
    
    # Macro pack
    macro_pack = gathered[idx]
    if isinstance(macro_pack, Exception):
        logger.error("Failed macro collection: %s", macro_pack)
        errors.append(f"Macro collection failed: {macro_pack}")
        macro_pack = EvidencePack(pack_id=f"{run_id}_macro", target="macro", items=[], created_at=datetime.now(timezone.utc))
    else:
        macro_pack = cast(EvidencePack, macro_pack)
    idx += 1

    # Sector packs
    sector_evidence: dict[str, EvidencePack] = {}
    for _ in sectors:
        res = gathered[idx]
        if isinstance(res, Exception):
            logger.error("Failed sector collection: %s", res)
            errors.append(f"Sector collection failed: {res}")
        else:
            sec_name, sec_pack = cast(tuple[str, EvidencePack], res)
            sector_evidence[sec_name] = sec_pack
        idx += 1

    # Ticker packs
    ticker_evidence: dict[str, EvidencePack] = {}
    ticker_bars: dict[str, list] = {}
    for tick in tickers:
        res = gathered[idx]
        if isinstance(res, Exception):
            logger.error("Failed ticker collection for %s: %s", tick, res)
            errors.append(f"Ticker collection failed for {tick}: {res}")
            ticker_evidence[tick] = EvidencePack(pack_id=f"{run_id}_ticker_{tick}", target=tick, items=[], created_at=datetime.now(timezone.utc))
        else:
            ticker, tick_pack, bars = cast(tuple[str, EvidencePack, list], res)
            ticker_evidence[ticker] = tick_pack
            if bars:
                ticker_bars[ticker] = bars
        idx += 1

    # Generate portfolio pack based on macro outline + return correlation matrix
    portfolio_pack = _collect_portfolio(run_id, ticker_bars, macro_pack)

    logger.info(
        "Collection Node complete | macro_items=%d sector_packs=%d ticker_packs=%d",
        len(macro_pack.items),
        len(sector_evidence),
        len(ticker_evidence),
    )

    update = {
        "macro_evidence": macro_pack,
        "sector_evidence": sector_evidence,
        "ticker_evidence": ticker_evidence,
        "portfolio_evidence": portfolio_pack,
    }
    if errors:
        update["errors"] = errors
    return update
