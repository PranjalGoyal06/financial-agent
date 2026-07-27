import asyncio
import json
import logging
from typing import Any, cast
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from app.evidence.schemas import EvidenceItem, EvidencePack
from app.llm.provider import get_structured_model
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
from app.research.logger import get_run_logger

logger = logging.getLogger(__name__)
_provider = YFinanceProvider()


class SearchQueries(BaseModel):
    queries: list[str] = Field(
        description="List of specific search queries to run against a search engine."
    )


async def _generate_queries(prompt_text: str, max_queries: int = 3) -> list[str]:
    """Generates specific search queries using a local LLM."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"You are a research analyst. Generate up to {max_queries} highly specific search engine queries to gather evidence for the following topic. Return ONLY the JSON array."),
        ("user", "{topic}")
    ])
    
    model = get_structured_model(SearchQueries, temperature=0.1, provider="ollama", fallback_provider="ollama_cloud")
    chain = prompt | model
    
    try:
        result: SearchQueries = await chain.ainvoke({"topic": prompt_text})
        return result.queries[:max_queries]
    except Exception as e:
        logger.warning(f"Query generation failed: {e}")
        return [prompt_text]  # Fallback to the raw prompt


async def _search_with_delay(query: str, max_results: int) -> list[EvidenceItem]:
    """Wraps Tavily search with a small delay to avoid rate limits."""
    await asyncio.sleep(0.5)
    return await search_tavily(query, max_results=max_results)


async def _collect_macro(run_id: str) -> EvidencePack:
    """Collect macro-level research evidence."""
    fetched_at = datetime.now(timezone.utc)
    queries = await _generate_queries("India equity market macroeconomic outlook, interest rates, and systemic risks this week", max_queries=3)
    
    items = []
    for q in queries:
        res = await _search_with_delay(q, max_results=3)
        items.extend(res)
    
    return EvidencePack(
        pack_id=f"{run_id}_macro",
        target="macro",
        items=items,
        created_at=fetched_at,
    )


async def _collect_sector(run_id: str, sector: str) -> tuple[str, EvidencePack]:
    """Collect industry/sector level research evidence."""
    fetched_at = datetime.now(timezone.utc)
    queries = await _generate_queries(f"Current trends, headwinds, and tailwinds for the {sector} sector in the Indian equity market", max_queries=3)
    
    items = []
    for q in queries:
        res = await _search_with_delay(q, max_results=3)
        items.extend(res)
    
    pack = EvidencePack(
        pack_id=f"{run_id}_sector_{sector.lower().replace(' ', '_')}",
        target=sector,
        items=items,
        created_at=fetched_at,
    )
    return sector, pack


async def collect_macro_sector(state: ResearchState) -> dict:
    """Node 2: Collects Macro and Sector evidence."""
    sectors = state.get("sectors", [])
    run_id = state.get("run_id")
    run_logger = get_run_logger(run_id)
    run_logger.log_event("collect_macro_sector", "node_start", f"Collect Macro/Sector Node starting | run_id={run_id}")

    logger.info("Collect Macro/Sector Node starting | run_id=%s sectors=%s", run_id, sectors)
    errors = []

    macro_task = _collect_macro(run_id)
    sector_tasks = [_collect_sector(run_id, sec) for sec in sectors]

    gathered = await asyncio.gather(macro_task, *sector_tasks, return_exceptions=True)

    idx = 0
    macro_pack = gathered[idx]
    if isinstance(macro_pack, Exception):
        errors.append(f"Macro collection failed: {macro_pack}")
        macro_pack = EvidencePack(pack_id=f"{run_id}_macro", target="macro", items=[], created_at=datetime.now(timezone.utc))
    else:
        macro_pack = cast(EvidencePack, macro_pack)
    idx += 1

    sector_results = []
    for _ in sectors:
        res = gathered[idx]
        if isinstance(res, Exception):
            errors.append(f"Sector collection failed: {res}")
        else:
            sector_results.append(cast(tuple[str, EvidencePack], res))
        idx += 1
        
    # Build structures
    sector_evidence = {sector: pack for sector, pack in sector_results}

    logger.info("Collect Macro/Sector complete | %d sectors processed", len(sector_evidence))
    run_logger.log_event("collect_macro_sector", "node_complete", f"Collect Macro/Sector complete. Processed {len(sector_evidence)} sectors.")

    update = {
        "macro_evidence": macro_pack,
        "sector_evidence": sector_evidence,
    }
    if errors:
        update["errors"] = errors
    return update


# ── Ticker Collection (Round 1) ────────────────────────────────────────────────

def _fetch_ticker_yfinance(ticker: str) -> tuple[dict, list, dict | None]:
    quote = _provider.get_quote(ticker)
    historical = _provider.get_historical(ticker, period="1y", interval="1d")
    try:
        fundamentals = _provider.get_fundamentals(ticker)
    except Exception as exc:
        logger.warning("Failed to retrieve fundamentals for %s: %s", ticker, exc)
        fundamentals = None
    return quote.model_dump(), historical.bars, (fundamentals.model_dump() if fundamentals else None)


async def _collect_ticker_r1(run_id: str, ticker: str) -> tuple[str, EvidencePack, list]:
    fetched_at = datetime.now(timezone.utc)
    items = []
    bars = []

    queries = await _generate_queries(f"{ticker} stock news, recent earnings, and analyst ratings", max_queries=3)
    
    try:
        tavily_tasks = [_search_with_delay(q, max_results=2) for q in queries]
        chroma_task = search_prior_artifacts(f"{ticker} investment research analysis", limit=3, target=ticker)
        yf_task = asyncio.to_thread(_fetch_ticker_yfinance, ticker)

        results = await asyncio.gather(*tavily_tasks, chroma_task, yf_task)
        
        # Unpack results
        for t_res in results[:-2]:
            items.extend(t_res)
        items.extend(results[-2])  # Chroma
        quote_dict, bars, fund_dict = results[-1]  # YFinance
        
    except (TickerNotFoundError, ProviderError) as exc:
        logger.error("Market data fetch failed for target %s: %s", ticker, exc)
        pack = EvidencePack(pack_id=f"{run_id}_ticker_{ticker}_r1", target=ticker, items=[], created_at=fetched_at)
        return ticker, pack, []

    # Add yfinance quote item
    items.append(
        EvidenceItem(
            id=f"mkt_quote_{ticker.lower().replace('.', '_')}",
            type="market_data",
            source="yfinance",
            fetched_at=fetched_at,
            freshness="same_day",
            summary=(
                f"Current Price: INR {quote_dict.get('price')} | "
                f"Day Change: {quote_dict.get('day_change_pct'):+.2f}%"
            ),
        )
    )

    if fund_dict:
        items.append(
            EvidenceItem(
                id=f"mkt_fund_{ticker.lower().replace('.', '_')}",
                type="market_data",
                source="yfinance",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=f"Valuation: P/E={fund_dict.get('pe_ratio')}, Market Cap: INR {fund_dict.get('market_cap')}",
            )
        )

    if bars:
        metrics = compute_all_metrics(bars)
        items.append(
            EvidenceItem(
                id=f"comp_{ticker.lower().replace('.', '_')}",
                type="computed_metric",
                source="internal_computation",
                fetched_at=fetched_at,
                freshness="same_day",
                summary=json.dumps({"total_return": metrics.get("total_return")}),
            )
        )

    pack = EvidencePack(
        pack_id=f"{run_id}_ticker_{ticker}",
        target=ticker,
        items=items,
        created_at=fetched_at,
    )
    return ticker, pack, bars


async def collect_tickers_round1(state: ResearchState) -> dict:
    tickers = state.get("tickers", [])
    run_id = state.get("run_id")
    run_logger = get_run_logger(run_id)
    run_logger.log_event("collect_tickers_round1", "node_start", f"Collect Tickers Round 1 Node starting | run_id={run_id}")

    logger.info("Collect Tickers Round 1 Node starting | run_id=%s tickers=%s", run_id, tickers)
    errors = []

    ticker_tasks = [_collect_ticker_r1(run_id, tick) for tick in tickers]
    gathered = await asyncio.gather(*ticker_tasks, return_exceptions=True)

    ticker_evidence: dict[str, EvidencePack] = {}
    
    for tick, res in zip(tickers, gathered):
        if isinstance(res, Exception):
            errors.append(f"Ticker R1 collection failed for {tick}: {res}")
            ticker_evidence[tick] = EvidencePack(pack_id=f"{run_id}_ticker_{tick}", target=tick, items=[], created_at=datetime.now(timezone.utc))
        else:
            ticker, tick_pack, _ = cast(tuple[str, EvidencePack, list], res)
            ticker_evidence[ticker] = tick_pack

    logger.info("Collect Tickers Round 1 complete")
    run_logger.log_event("collect_tickers_round1", "node_complete", f"Collect Tickers Round 1 complete. Processed {len(tickers)} tickers.")

    update = {"ticker_evidence": ticker_evidence}
    if errors:
        update["errors"] = errors
    return update


# ── Ticker Collection (Round 2) ────────────────────────────────────────────────

async def collect_tickers_round2(state: ResearchState) -> dict:
    """Executes follow-up queries generated by evidence_triage."""
    # Only execute follow-ups if requested by triage
    follow_up_queries = state.get("follow_up_queries", {})
    run_id = state.get("run_id")
    run_logger = get_run_logger(run_id)
    run_logger.log_event("collect_tickers_round2", "node_start", f"Collect Tickers Round 2 Node starting | run_id={run_id}")
    
    if not follow_up_queries:
        logger.info("Collect Tickers Round 2 Node skipping (no queries)")
        run_logger.log_event("collect_tickers_round2", "node_complete", "Collect Tickers Round 2 skipping (no follow-up queries)")
        return {}
    
    ticker_evidence = dict(state.get("ticker_evidence", {}))
    
    logger.info("Collect Tickers Round 2 Node starting")
    
    for ticker, queries in follow_up_queries.items():
        pack = ticker_evidence.get(ticker)
        if not pack:
            continue
            
        items = []
        for q in queries:
            try:
                res = await _search_with_delay(q, max_results=3)
                items.extend(res)
            except Exception as e:
                logger.warning(f"R2 Search failed for {ticker}: {e}")
                
        # Merge into existing packs
        ticker_evidence[ticker].items.extend(items)
        ticker_evidence[ticker].metadata["r2_queries"] = queries

    logger.info("Collect Tickers Round 2 complete | processed %d follow-ups", len(follow_up_queries))
    run_logger.log_event("collect_tickers_round2", "node_complete", f"Collect Tickers Round 2 complete. Processed {len(follow_up_queries)} follow-ups.")

    return {
        "ticker_evidence": ticker_evidence,
    }
