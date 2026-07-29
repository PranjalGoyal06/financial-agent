import asyncio
import logging

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.llm.provider import get_structured_model
from app.research.state import ResearchState
from app.research.store import search_prior_artifacts
from app.research.utils import run_concurrently

logger = logging.getLogger(__name__)


class DriftReport(BaseModel):
    drift_report: str = Field(
        description="A concise markdown string highlighting flipped recommendations or massive confidence shifts vs the prior."
    )


async def _reconcile_ticker(ticker: str, current_synthesis: str) -> tuple[str, str | None]:
    """Compares current synthesis against the most recent prior artifact."""
    priors = await search_prior_artifacts(
        f"{ticker} investment research analysis", 
        limit=1, 
        artifact_type="ticker", 
        target=ticker
    )
    
    if not priors:
        return ticker, None
        
    prior_text = priors[0].summary
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an audit analyst. Compare the current research output against the prior research. Produce a concise 'Drift Report' highlighting only significant changes (e.g., flipped recommendation from BUY to SELL, massive confidence shift, or new critical risk). Keep it under 2 sentences. If there's no major drift, just say 'No significant drift.'"),
        ("user", "Prior Research:\n{prior}\n\nCurrent Research:\n{current}")
    ])
    
    model = get_structured_model(DriftReport, temperature=0.1, provider="ollama_cloud", fallback_provider="ollama")
    
    try:
        res: DriftReport = await (prompt | model).ainvoke({
            "prior": prior_text,
            "current": current_synthesis
        })
        return ticker, res.drift_report
    except Exception as e:
        logger.warning("Failed to generate drift report for %s: %s", ticker, e)
        return ticker, None


from app.research.logger import get_run_logger

async def reconcile_with_prior(state: ResearchState) -> dict:
    """Reconciliation Node: Compares current outputs with prior Chroma artifacts."""
    run_id = state.get("run_id") or "test_run"
    run_logger = get_run_logger(run_id)
    run_logger.log_event("reconcile_with_prior", "node_start", "Reconciliation Node starting")
    logger.info("Reconciliation Node starting")
    
    ticker_synthesis = state.get("ticker_synthesis", {})
    if not ticker_synthesis:
        run_logger.log_event("reconcile_with_prior", "node_skipped", "Reconcile Node skipped (no ticker synthesis results)")
        return {}
        
    tasks = []
    for ticker, data in ticker_synthesis.items():
        current_str = data.model_dump_json()
        tasks.append(_reconcile_ticker(ticker, current_str))
        
    results = await run_concurrently(tasks, execute_async=state.get("async_execution", True), return_exceptions=True)
    
    drift_reports = {}
    for res in results:
        if isinstance(res, Exception):
            run_logger.log_exception("reconcile_with_prior", res, "Reconciliation task failed")
            logger.error("Reconciliation task failed: %s", res)
            continue
            
        ticker, report = res
        if report:
            drift_reports[ticker] = report
            run_logger.log_debug("reconcile_with_prior", f"Drift report generated for {ticker}", {"ticker": ticker, "report": report})
            run_logger.log_event("reconcile_with_prior", "drift_report", f"Drift report for {ticker}: {report}", {"ticker": ticker, "report": report})
            
    if not drift_reports:
        run_logger.log_event("reconcile_with_prior", "node_skipped", "Reconciliation skipped (no prior state found to reconcile against)")
    else:
        run_logger.log_event("reconcile_with_prior", "node_complete", f"Reconciliation complete. Generated {len(drift_reports)} drift reports.", {"drift_reports": drift_reports})
    logger.info("Reconciliation complete. Generated %d drift reports.", len(drift_reports))
    return {"drift_reports": drift_reports}
