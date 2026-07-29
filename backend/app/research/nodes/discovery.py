import asyncio
import logging
from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.llm.provider import get_structured_model
from app.research.state import ResearchState
from app.research.utils import run_concurrently

logger = logging.getLogger(__name__)

from pathlib import Path

# Load Nifty 500 constituents from local CSV
_csv_path = Path(__file__).parent.parent.parent.parent.parent / "sample_imports" / "ind_nifty500list.csv"
try:
    _df = pd.read_csv(_csv_path)
    SCREENER_UNIVERSE = [f"{sym}.NS" for sym in _df["Symbol"].dropna().tolist()]
except Exception as e:
    logger.error(f"Failed to load Nifty 500 universe: {e}")
    SCREENER_UNIVERSE = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]


class SpilloverExtraction(BaseModel):
    """Tickers extracted from macro/sector synthesis."""
    tickers: list[str] = Field(
        description="List of canonical ticker symbols (e.g. INFY.NS) mentioned as having significant momentum or tailwinds."
    )


class CandidateGrading(BaseModel):
    """Grading for a discovered candidate."""
    score: int = Field(ge=1, le=10, description="Idiosyncratic catalyst score (1-10)")
    reasoning: str = Field(description="Why this ticker is interesting right now based on the news.")


def _run_local_screener(exclude_tickers: set[str]) -> list[dict[str, Any]]:
    """Runs a quick batched yfinance download to find 1-day/3-day movers."""
    targets = [t for t in SCREENER_UNIVERSE if t not in exclude_tickers]
    if not targets:
        return []

    try:
        # Download last 5 days of data
        data = yf.download(targets, period="5d", group_by="ticker", progress=False, auto_adjust=False, ignore_tz=True)
    except Exception as e:
        logger.warning(f"yfinance screener download failed: {e}")
        return []

    candidates = []
    
    # Handle single ticker edge case in yf.download
    if len(targets) == 1:
        ticker = targets[0]
        if not data.empty and len(data) >= 2:
            closes = data['Close'].dropna().values
            if len(closes) >= 2:
                pct_change = (closes[-1] / closes[-2]) - 1
                candidates.append({
                    "ticker": ticker,
                    "vector": "screener",
                    "reason": f"Screener: 1-day move of {pct_change:.2%}",
                    "metric": abs(pct_change)
                })
        return candidates

    for ticker in targets:
        try:
            if ticker not in data.columns.levels[0]:
                continue
            df = data[ticker].dropna()
            if len(df) < 2:
                continue
            closes = df['Close'].values
            pct_change = (closes[-1] / closes[-2]) - 1
            
            # Keep interesting moves (> 3% up or down)
            if abs(pct_change) > 0.03:
                candidates.append({
                    "ticker": ticker,
                    "vector": "screener",
                    "reason": f"Screener: 1-day move of {pct_change:.2%}",
                    "metric": abs(pct_change)
                })
        except Exception:
            continue
            
    # Sort by absolute move and take top 5
    candidates.sort(key=lambda x: x["metric"], reverse=True)
    return candidates[:5]


async def _extract_spillover(state: ResearchState, exclude_tickers: set[str]) -> list[dict[str, Any]]:
    """Uses a local LLM to extract mentioned tickers from macro/sector synthesis."""
    run_id = state.get("run_id") or "test_run"
    run_logger = get_run_logger(run_id)
    
    texts = []
    if state.get("macro_synthesis"):
        texts.append(state["macro_synthesis"].analysis_markdown)
    if state.get("sector_synthesis"):
        for sec in state["sector_synthesis"].values():
            texts.append(sec.analysis_markdown)
            
    if not texts:
        run_logger.log_debug("discover_screen", "No macro/sector synthesis text found for spillover extraction")
        return []
        
    combined_text = "\n\n".join(texts)
    run_logger.log_debug("discover_screen", f"Extracting spillover tickers from {len(combined_text)} chars of synthesis text")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a financial analyst. Extract canonical stock tickers (e.g. INFY.NS) mentioned in the text that show strong momentum, tailwinds, or catalysts. Return ONLY the JSON schema."),
        ("user", "{text}")
    ])
    
    model = get_structured_model(SpilloverExtraction, temperature=0.1, provider="ollama_cloud", fallback_provider="ollama")
    chain = prompt | model
    
    try:
        # Assuming run is relatively fast for a local model
        result: SpilloverExtraction = await chain.ainvoke({"text": combined_text[:8000]})
        
        candidates = []
        for t in result.tickers:
            t = t.upper()
            if t not in exclude_tickers:
                candidates.append({
                    "ticker": t,
                    "vector": "spillover",
                    "reason": "Spillover: Mentioned in macro/sector research as having strong tailwinds."
                })
        run_logger.log_debug("discover_screen", f"Spillover extraction surfaced {len(candidates)} candidates", {"candidates": candidates})
        return candidates[:5]
    except Exception as e:
        logger.warning(f"Spillover extraction failed: {e}")
        run_logger.log_debug("discover_screen", f"Spillover extraction failed: {e}")
        return []


async def _grade_candidate(candidate: dict, model_callable, run_logger) -> dict | None:
    """Grades a single candidate based on recent news (mocked for MVP without Tavily here)."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Chief Investment Officer grading research candidates. Score this candidate (1-10) based on how interesting its catalyst or price action is. Score >=7 means it's worth a deep dive."),
        ("user", "Ticker: {ticker}\nReason for discovery: {reason}")
    ])
    
    chain = prompt | model_callable
    
    try:
        result: CandidateGrading = await chain.ainvoke({
            "ticker": candidate["ticker"],
            "reason": candidate["reason"]
        })
        
        graded = {
            **candidate,
            "score": result.score,
            "reasoning": result.reasoning
        }
        run_logger.log_debug("discover_screen", f"Graded candidate {candidate['ticker']}: score={result.score}", {"candidate": graded})
        return graded
    except Exception as e:
        logger.warning(f"Candidate grading failed for {candidate['ticker']}: {e}")
        run_logger.log_debug("discover_screen", f"Candidate grading failed for {candidate['ticker']}: {e}")
        return None


from app.research.logger import get_run_logger

async def discover_screen(state: ResearchState) -> dict:
    """Discovery Node: Identifies promising off-watchlist candidates."""
    run_id = state.get("run_id") or "test_run"
    run_logger = get_run_logger(run_id)
    run_logger.log_event("discover_screen", "node_start", "Discover Screen Node starting")
    run_logger.log_debug("discover_screen", f"Starting discovery screening against screener universe ({len(SCREENER_UNIVERSE)} stocks)")
    logger.info("Discover Screen Node starting")
    
    watchlist_tickers = set(state.get("tickers", []))
    
    # 1. Run vectors concurrently
    screener_task = asyncio.to_thread(_run_local_screener, watchlist_tickers)
    spillover_task = _extract_spillover(state, watchlist_tickers)
    
    screener_cands, spillover_cands = await run_concurrently([screener_task, spillover_task], execute_async=state.get("async_execution", True))
    
    run_logger.log_api_traffic("discover_screen", "yfinance_screener", f"Evaluated {len(SCREENER_UNIVERSE)} stocks", len(screener_cands))
    run_logger.log_event("discover_screen", "llm_call", f"Spillover extraction surfaced {len(spillover_cands)} candidates", {"candidates": [c["ticker"] for c in spillover_cands]})
    run_logger.log_debug("discover_screen", f"Screener candidates: {len(screener_cands)}, Spillover candidates: {len(spillover_cands)}", {
        "screener_candidates": screener_cands,
        "spillover_candidates": spillover_cands
    })

    # Combine and dedupe
    seen = set(watchlist_tickers)
    all_candidates = []
    
    for c in screener_cands + spillover_cands:
        if c["ticker"] not in seen:
            seen.add(c["ticker"])
            all_candidates.append(c)
            
    if not all_candidates:
        run_logger.log_debug("discover_screen", "No candidates found during discovery vectors")
        run_logger.log_event("discover_screen", "node_complete", "Discover Screen: No candidates found", {"discovered_tickers": []})
        logger.info("Discover Screen: No candidates found.")
        return {"discovered_tickers": []}
        
    logger.info(f"Discover Screen: Found {len(all_candidates)} raw candidates. Grading...")
    run_logger.log_debug("discover_screen", f"Grading {len(all_candidates)} combined raw candidates", {"all_candidates": all_candidates})
    
    # 2. Grade candidates (using local LLM)
    grade_model = get_structured_model(CandidateGrading, temperature=0.2, provider="ollama_cloud", fallback_provider="ollama")
    grade_tasks = [_grade_candidate(c, grade_model, run_logger) for c in all_candidates]
    graded_results = await run_concurrently(grade_tasks, execute_async=state.get("async_execution", True))
    
    # 3. Filter and promote top 5
    valid_results = [r for r in graded_results if r is not None and r["score"] >= 7]
    valid_results.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = valid_results[:5]
    
    discovered_tickers = [c["ticker"] for c in top_candidates]
    run_logger.log_debug("discover_screen", f"Filtered top {len(top_candidates)} candidates with score >= 7", {
        "valid_results": valid_results,
        "top_candidates": top_candidates,
        "discovered_tickers": discovered_tickers
    })
    run_logger.log_event("discover_screen", "node_complete", f"Promoted {len(discovered_tickers)} candidates", {"discovered_tickers": discovered_tickers, "top_candidates": top_candidates})
    logger.info(f"Discover Screen: Promoted {len(discovered_tickers)} candidates: {discovered_tickers}")
    
    return {"discovered_tickers": discovered_tickers}
