from __future__ import annotations

"""Evidence & Compliance validation library — Layer 2 / deterministic rules.

Includes:
  - Data freshness & staleness auditing
  - Citation validation against an EvidencePack
  - Evidence sufficiency score calculation (0–100)
  - Scenario expected value calculation & stress testing price shocks
  - Compliance audit logging using python's `logging` module (`paisa.compliance.audit`)
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.evidence.schemas import EvidencePack

audit_logger = logging.getLogger("paisa.compliance.audit")


class CitationValidationResult(BaseModel):
    is_valid: bool
    total_citations: int
    valid_citations: list[str]
    invalid_citations: list[str]
    hallucinated_ids: list[str]


class SufficiencyResult(BaseModel):
    score: int = Field(ge=0, le=100)
    item_count: int
    news_count: int
    market_data_count: int
    computed_metric_count: int
    has_stale_items: bool
    is_sufficient: bool  # score >= threshold


class PriceShockResult(BaseModel):
    ticker: str
    base_price: float
    shocked_price: float
    shock_pct: float
    scenario_name: str


class ScenarioEVResult(BaseModel):
    base_case_target: float
    base_case_prob: float
    bull_case_target: float
    bull_case_prob: float
    bear_case_target: float
    bear_case_prob: float
    expected_value: float
    expected_return_pct: float


# ── 1. Freshness Audit & Logging ─────────────────────────────────────────────

def check_data_freshness(pack: EvidencePack) -> dict[str, int]:
    """Check count of items in each freshness tier and log compliance status."""
    counts = {"same_day": 0, "this_week": 0, "stale": 0}
    stale_items = []
    
    for item in pack.items:
        counts[item.freshness] += 1
        if item.freshness == "stale":
            stale_items.append(item.id)
            
    audit_logger.info(
        "Compliance Audit - Freshness Check | pack_id=%s target=%s counts=%s stale_items=%s",
        pack.pack_id,
        pack.target,
        counts,
        stale_items,
    )
    return counts


def log_compliance_event(
    event_type: str,
    target: str,
    details: dict,
    status: Literal["PASSED", "WARNING", "FAILED"] = "PASSED",
) -> None:
    """Log a compliance audit event in a structured format."""
    audit_logger.info(
        "Compliance Event | event_type=%s target=%s status=%s details=%s",
        event_type,
        target,
        status,
        details,
    )


# ── 2. Citation Validation ───────────────────────────────────────────────────

def validate_citations(
    text: str,
    pack: EvidencePack,
) -> CitationValidationResult:
    """Extract citations (e.g., [news_001], [mkt_002]) from text and validate against pack."""
    pattern = r"\[([a-zA-Z0-9_-]+)\]"
    found = re.findall(pattern, text)
    unique_citations = list(dict.fromkeys(found))
    
    valid_ids = pack.item_ids
    valid_citations = []
    invalid_citations = []
    
    for cid in unique_citations:
        if cid in valid_ids:
            valid_citations.append(cid)
        else:
            invalid_citations.append(cid)
            
    is_valid = len(invalid_citations) == 0
    
    log_compliance_event(
        event_type="CITATION_VALIDATION",
        target=pack.target,
        details={
            "total": len(unique_citations),
            "valid_count": len(valid_citations),
            "invalid_count": len(invalid_citations),
            "invalid_ids": invalid_citations,
        },
        status="PASSED" if is_valid else "WARNING",
    )
    
    return CitationValidationResult(
        is_valid=is_valid,
        total_citations=len(unique_citations),
        valid_citations=valid_citations,
        invalid_citations=invalid_citations,
        hallucinated_ids=invalid_citations,
    )


# ── 3. Evidence Sufficiency Score ────────────────────────────────────────────

def compute_evidence_sufficiency_score(
    pack: EvidencePack,
    min_items: int = 3,
    min_news: int = 1,
    min_market_data: int = 1,
) -> SufficiencyResult:
    """Compute a score (0-100) reflecting how complete the evidence pack is."""
    item_count = len(pack.items)
    news_count = sum(1 for i in pack.items if i.type == "news")
    market_data_count = sum(1 for i in pack.items if i.type == "market_data")
    computed_count = sum(1 for i in pack.items if i.type == "computed_metric")
    has_stale = any(i.freshness == "stale" for i in pack.items)
    
    score = 0
    # Quantity score (up to 40 pts)
    score += min(40, item_count * 10)
    
    # Diversity score (up to 40 pts)
    if news_count >= min_news:
        score += 15
    if market_data_count >= min_market_data:
        score += 15
    if computed_count >= 1:
        score += 10
        
    # Freshness penalty / bonus (up to 20 pts)
    if not has_stale and item_count > 0:
        score += 20
    elif has_stale:
        score = max(0, score - 15)
        
    score = min(100, max(0, score))
    is_sufficient = (
        score >= 50 and
        item_count >= min_items and
        news_count >= min_news and
        market_data_count >= min_market_data
    )
    
    log_compliance_event(
        event_type="SUFFICIENCY_CHECK",
        target=pack.target,
        details={
            "score": score,
            "is_sufficient": is_sufficient,
            "item_count": item_count,
            "news_count": news_count,
            "market_data_count": market_data_count,
            "has_stale": has_stale,
        },
        status="PASSED" if is_sufficient else "WARNING",
    )
    
    return SufficiencyResult(
        score=score,
        item_count=item_count,
        news_count=news_count,
        market_data_count=market_data_count,
        computed_metric_count=computed_count,
        has_stale_items=has_stale,
        is_sufficient=is_sufficient,
    )


# ── 4. Scenario EV & Price Shock Helpers ─────────────────────────────────────

def apply_price_shock(
    ticker: str,
    base_price: float,
    shock_pct: float,
    scenario_name: str = "custom_shock",
) -> PriceShockResult:
    """Apply a price shock (e.g. -0.10 for -10%) to a base price."""
    shocked_price = round(base_price * (1.0 + shock_pct), 2)
    return PriceShockResult(
        ticker=ticker,
        base_price=base_price,
        shocked_price=shocked_price,
        shock_pct=shock_pct,
        scenario_name=scenario_name,
    )


def compute_scenario_ev(
    current_price: float,
    base_target: float,
    base_prob: float,
    bull_target: float,
    bull_prob: float,
    bear_target: float,
    bear_prob: float,
) -> ScenarioEVResult:
    """Calculate expected price and expected return % across 3 scenarios."""
    prob_sum = base_prob + bull_prob + bear_prob
    if abs(prob_sum - 1.0) > 1e-4:
        # Normalize probabilities if they don't sum strictly to 1.0
        base_prob = base_prob / prob_sum
        bull_prob = bull_prob / prob_sum
        bear_prob = bear_prob / prob_sum

    ev = (base_target * base_prob) + (bull_target * bull_prob) + (bear_target * bear_prob)
    expected_return_pct = round(((ev - current_price) / current_price) * 100.0, 2) if current_price > 0 else 0.0

    return ScenarioEVResult(
        base_case_target=base_target,
        base_case_prob=base_prob,
        bull_case_target=bull_target,
        bull_case_prob=bull_prob,
        bear_case_target=bear_target,
        bear_case_prob=bear_prob,
        expected_value=round(ev, 2),
        expected_return_pct=expected_return_pct,
    )
