import asyncio
import logging

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.evidence.lib import compute_evidence_sufficiency_score
from app.llm.provider import get_structured_model
from app.research.state import ResearchState

logger = logging.getLogger(__name__)


class FollowUpQueries(BaseModel):
    queries: list[str] = Field(
        description="List of 1 to 3 targeted follow-up queries."
    )


async def _generate_follow_up(ticker: str, pack_summary: str) -> list[str]:
    """Generates targeted follow-up queries using a local LLM."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a research analyst reviewing an initial evidence pack for a stock. Generate 1 to 3 highly targeted search queries to fill any critical gaps (e.g. recent management commentary, specific risk factors). Return ONLY the JSON array."),
        ("user", f"Ticker: {ticker}\n\nCurrent Evidence Summary:\n{pack_summary}")
    ])
    
    model = get_structured_model(FollowUpQueries, temperature=0.1, provider="ollama", fallback_provider="ollama_cloud")
    chain = prompt | model
    
    try:
        result: FollowUpQueries = await chain.ainvoke({})
        return result.queries[:3]
    except Exception as e:
        logger.warning(f"Follow-up query generation failed for {ticker}: {e}")
        return []


from app.research.logger import get_run_logger

async def evidence_triage(state: ResearchState) -> dict:
    """Triage Node: Enforces sufficiency gating and plans follow-up queries."""
    run_id = state.get("run_id") or "test_run"
    run_logger = get_run_logger(run_id)
    run_logger.log_event("evidence_triage", "node_start", "Evidence Triage Node starting")
    logger.info("Evidence Triage Node starting")
    
    ticker_evidence = state.get("ticker_evidence", {})
    follow_up_queries = {}
    
    tasks = []
    tickers = []
    
    for ticker, pack in ticker_evidence.items():
        result = compute_evidence_sufficiency_score(pack)
        run_logger.log_event(
            "evidence_triage", 
            "triage_gate", 
            f"Sufficiency check for {ticker}: score={result.score}, sufficient={result.is_sufficient}",
            {"score": result.score, "is_sufficient": result.is_sufficient, "item_count": result.item_count}
        )
        
        if not result.is_sufficient:
            logger.warning(f"Triage: {ticker} failed sufficiency check (score {result.score}). Skipping R2.")
            continue
            
        logger.info(f"Triage: {ticker} passed (score {result.score}). Planning follow-ups.")
        
        summaries = [f"[{i.source}] {i.summary[:200]}" for i in pack.items[:5]]
        pack_summary = "\n".join(summaries)
        
        tickers.append(ticker)
        tasks.append(_generate_follow_up(ticker, pack_summary))
        
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ticker, queries in zip(tickers, results):
            if isinstance(queries, Exception):
                run_logger.log_exception("evidence_triage", queries, f"Follow-up generation failed for {ticker}")
                logger.error(f"Follow-up generation failed for {ticker}: {queries}")
            elif queries:
                follow_up_queries[ticker] = queries
                run_logger.log_event("evidence_triage", "llm_call", f"Follow-up queries generated for {ticker}", {"queries": queries})
                
    run_logger.log_event("evidence_triage", "node_complete", f"Evidence Triage complete. Scheduled follow-ups for {len(follow_up_queries)} tickers.", {"follow_up_queries": follow_up_queries})
    logger.info(f"Evidence Triage complete. Scheduled follow-ups for {len(follow_up_queries)} tickers.")
    
    return {"follow_up_queries": follow_up_queries}
