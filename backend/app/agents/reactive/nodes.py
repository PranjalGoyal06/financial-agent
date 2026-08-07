from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.agents.reactive.schemas import (
    CARD_MODELS,
    ComparisonCard,
    DataQualityReport,
    ErrorCard,
    EvidenceItem,
    FinalResponse,
    InsufficientDataCard,
    LLMOutput,
    NewsDigestCard,
    PortfolioSnapshotCard,
    RecommendationCard,
    ResearchRunStatusCard,
    RetrievalDisclosure,
    RetrievalPlan,
    model_to_dict,
)
from app.agents.reactive.state import ReactiveState
from app.prompts.manager import render_prompt
from app.db.repositories.audit_repository import (
    DEFAULT_AUDIT_REPOSITORY,
    AuditRepository,
)
from app.db.repositories.holdings_repository import (
    DEFAULT_HOLDINGS_REPOSITORY,
    HoldingsRepository,
)
from app.db.repositories.investment_principles_repository import (
    DEFAULT_INVESTMENT_PRINCIPLES_REPOSITORY,
    InvestmentPrinciplesRepository,
)
from app.db.repositories.recommendations_repository import (
    DEFAULT_RECOMMENDATIONS_REPOSITORY,
    RecommendationRecord,
    RecommendationsRepository,
)
from app.db.repositories.user_profile_repository import (
    DEFAULT_USER_PROFILE_REPOSITORY,
    UserProfileRepository,
)
from app.db.repositories.watchlist_repository import (
    DEFAULT_WATCHLIST_REPOSITORY,
    WatchlistRepository,
)
from app.integrations import chroma_client, yfinance_client
from app.services.market_data_service import (
    DEFAULT_MARKET_DATA_SERVICE,
    MarketDataEnvelope,
    MarketDataService,
)

DEFAULT_USER_ID = "demo-user"
RECENT_CHAT_LIMIT = 6
MAX_MARKET_TICKERS = 5
MAX_ARTIFACTS = 3
MAX_NEWS_CHUNKS = 10
TICKER_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,14}(?:\.(?:NS|BO))?\b")
COMPARE_PATTERN = re.compile(r"\bcompare\b|\bversus\b|\bvs\.?\b", re.IGNORECASE)
NEWS_PATTERN = re.compile(r"\bnews\b|\bheadline|\blatest\b|\bimpact\b", re.IGNORECASE)
RECOMMENDATION_PATTERN = re.compile(
    r"\bshould\s+i\b|\bbuy\b|\bsell\b|\bhold\b|\badd\b|\breduce\b|\brecommend",
    re.IGNORECASE,
)
RISK_PATTERN = re.compile(
    r"\brisk\b|\bconcentration\b|\bexposure\b|\ballocation\b|\bdownside\b",
    re.IGNORECASE,
)
DATA_PATTERN = re.compile(
    r"\bprice\b|\bquote\b|\bweight\b|\bvalue\b|\bdata\b", re.IGNORECASE
)
RESEARCH_RUN_PATTERN = re.compile(
    r"\bdeep research\b|\bresearch run\b|\brun research\b", re.IGNORECASE
)
CHAT_PATTERN = re.compile(
    r"\bwhat is\b|\bexplain\b|\bdefine\b|\bhow does\b|\bhello\b|\bhi\b", re.IGNORECASE
)
TICKER_STOPWORDS = {
    "SHOULD",
    "ADD",
    "BUY",
    "SELL",
    "HOLD",
    "ETF",
    "MVP",
    "USD",
    "INR",
    "NSE",
    "BSE",
    "AI",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return dict(value)


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_for_prompt(value: Any) -> str:
    return json.dumps(value, default=_json_default, indent=2, sort_keys=True)


def _coerce_llm_content(response: Any) -> str:
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else str(content)


def _audit_event(
    state: ReactiveState, event_type: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    return {
        "audit_event_id": str(uuid4()),
        "run_id": state.get("graph_run_id"),
        "session_id": state["session_id"],
        "actor": "system",
        "event_type": event_type,
        "event_timestamp": _utc_now().isoformat(),
        "metadata_json": metadata,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalised = value.strip().upper()
        if not normalised or normalised in seen:
            continue
        seen.add(normalised)
        output.append(normalised)
    return output


def _dedupe_preserve_case(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def _extract_tickers(query: str) -> list[str]:
    return _dedupe(
        [
            match.group(0)
            for match in TICKER_PATTERN.finditer(query.upper())
            if match.group(0) not in TICKER_STOPWORDS
        ]
    )


def _holding_tickers(holdings: list[dict[str, Any]]) -> list[str]:
    tickers: list[str] = []
    for holding in holdings:
        ticker = holding.get("canonical_ticker") or holding.get("raw_ticker")
        if isinstance(ticker, str):
            tickers.append(ticker)
    return _dedupe(tickers)


def _portfolio_holdings(state: ReactiveState) -> list[dict[str, Any]]:
    portfolio = state.get("portfolio", {})
    holdings = portfolio.get("holdings", []) if isinstance(portfolio, dict) else []
    return [holding for holding in holdings if isinstance(holding, dict)]


def _holding_cost(holding: dict[str, Any]) -> float:
    try:
        return float(holding.get("quantity", 0)) * float(
            holding.get("avg_buy_price", 0)
        )
    except (TypeError, ValueError):
        return 0.0


def _allocation_summary(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(_holding_cost(holding) for holding in holdings)
    by_asset: dict[str, float] = {}
    by_ticker: list[dict[str, Any]] = []
    for holding in holdings:
        value = _holding_cost(holding)
        asset_class = str(holding.get("asset_class") or "other")
        by_asset[asset_class] = by_asset.get(asset_class, 0.0) + value
        ticker = str(holding.get("canonical_ticker") or holding.get("raw_ticker") or "")
        if ticker:
            by_ticker.append(
                {
                    "ticker": ticker,
                    "value": value,
                    "weight": (value / total * 100) if total else 0.0,
                }
            )
    allocation = [
        {
            "asset_class": asset_class,
            "value": value,
            "weight": (value / total * 100) if total else 0.0,
        }
        for asset_class, value in by_asset.items()
    ]
    allocation.sort(key=lambda item: item["value"], reverse=True)
    by_ticker.sort(key=lambda item: item["value"], reverse=True)
    return {
        "total_imported_cost": total,
        "asset_allocation": allocation,
        "ticker_weights": by_ticker,
        "top_concentration": by_ticker[:5],
    }


def _baseline_summary(state: ReactiveState) -> dict[str, Any]:
    portfolio = state.get("portfolio", {})
    holdings = portfolio.get("holdings", []) if isinstance(portfolio, dict) else []
    return {
        "user_profile": state.get("user_profile", {}),
        "holding_count": len(holdings),
        "portfolio_allocation": portfolio.get("allocation_summary", {}),
        "watchlist": state.get("watchlist", []),
        "principles": state.get("investment_principles", state.get("principles", [])),
        "recent_chat_context": state.get("recent_chat_context", [])[
            -RECENT_CHAT_LIMIT:
        ],
    }


def _resolve_canonical_ticker(
    ticker: str, holdings: list[dict[str, Any]], watchlist: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    upper = ticker.strip().upper()
    for holding in holdings:
        for key in ("canonical_ticker", "raw_ticker"):
            value = holding.get(key)
            if isinstance(value, str) and value.upper() == upper:
                return str(holding.get("canonical_ticker") or value).upper(), None
    for item in watchlist:
        value = item.get("ticker")
        if isinstance(value, str) and value.upper() == upper:
            exchange = item.get("exchange")
            resolved = yfinance_client.resolve_ticker(
                value, str(exchange) if exchange else None
            )
            if resolved.ok and resolved.resolved_ticker:
                return resolved.resolved_ticker, None
            return (
                None,
                resolved.error.message
                if resolved.error
                else "Ticker could not be resolved.",
            )
    if upper.endswith((".NS", ".BO")):
        return upper, None
    resolved = yfinance_client.resolve_ticker(upper, "NSE")
    if resolved.ok and resolved.resolved_ticker:
        return resolved.resolved_ticker, None
    return (
        None,
        resolved.error.message if resolved.error else "Ticker could not be resolved.",
    )


def _heuristic_plan(query: str) -> RetrievalPlan:
    tickers = _extract_tickers(query)
    if RESEARCH_RUN_PATTERN.search(query):
        intent = "research_run_trigger"
    elif RECOMMENDATION_PATTERN.search(query):
        intent = "recommendation"
    elif COMPARE_PATTERN.search(query):
        intent = "comparison"
    elif NEWS_PATTERN.search(query):
        intent = "news_impact"
    elif RISK_PATTERN.search(query):
        intent = "risk_analysis"
    elif DATA_PATTERN.search(query):
        intent = "data_request"
    elif CHAT_PATTERN.search(query) or not tickers:
        intent = "general_question"
    else:
        intent = "portfolio_explanation"
    return RetrievalPlan(
        intent=intent,  # type: ignore[arg-type]
        relevant_tickers=tickers,
        reason_for_retrieval=f"Classified as {intent} from deterministic query rules.",
    )


def _invoke_groq_structured(
    prompt: str, schema: type[Any], user_query: str
) -> Any | None:
    if not os.environ.get("GROQ_API_KEY") or not os.environ.get("GROQ_MODEL"):
        return None
    try:
        from langchain_groq import ChatGroq

        llm = ChatGroq(model=os.environ["GROQ_MODEL"], temperature=0)
        structured = llm.with_structured_output(schema)
        return structured.invoke([("system", prompt), ("human", user_query)])
    except Exception:
        return None


def _invoke_groq_text(prompt: str, user_query: str) -> str | None:
    if not os.environ.get("GROQ_API_KEY") or not os.environ.get("GROQ_MODEL"):
        return None
    try:
        from langchain_groq import ChatGroq

        llm = ChatGroq(model=os.environ["GROQ_MODEL"], temperature=0)
        return _coerce_llm_content(
            llm.invoke([("system", prompt), ("human", user_query)])
        )
    except Exception:
        return None


def _evidence_id(source_type: str, ticker_or_scope: str | None) -> str:
    scope = (ticker_or_scope or "portfolio").replace(" ", "_")
    return f"{source_type}_{scope}_{int(_utc_now().timestamp())}_{uuid4().hex[:8]}"


def _envelope_to_evidence(
    source_type: str, ticker: str, envelope: MarketDataEnvelope
) -> EvidenceItem:
    if envelope.error is not None or envelope.value is None:
        quality = "unavailable"
        failure_reason = (
            envelope.error.message if envelope.error else "No provider value returned."
        )
    elif envelope.is_stale:
        quality = "stale"
        failure_reason = None
    else:
        quality = "fresh"
        failure_reason = None
    return EvidenceItem(
        evidence_id=_evidence_id(source_type, envelope.resolved_ticker or ticker),
        source_type=source_type,  # type: ignore[arg-type]
        ticker=envelope.resolved_ticker or ticker,
        provider=envelope.source,
        fetched_at=_utc_now(),
        quality_tier=quality,  # type: ignore[arg-type]
        payload=envelope.value or {},
        failure_reason=failure_reason,
    )


def initialise_turn(state: ReactiveState) -> dict[str, Any]:
    graph_run_id = state.get("graph_run_id") or str(uuid4())
    user_id = (
        state.get("user_id")
        or state.get("user_profile", {}).get("user_id")
        or DEFAULT_USER_ID
    )
    initial_state = {
        "graph_run_id": graph_run_id,
        "user_id": user_id,
        "audit_events": [
            {
                "audit_event_id": str(uuid4()),
                "run_id": graph_run_id,
                "session_id": state["session_id"],
                "actor": "system",
                "event_type": "reactive.turn.started",
                "event_timestamp": _utc_now().isoformat(),
                "metadata_json": {"user_id": user_id},
            }
        ],
    }
    return initial_state


def load_baseline_context(
    state: ReactiveState,
    holdings_repository: HoldingsRepository = DEFAULT_HOLDINGS_REPOSITORY,
    watchlist_repository: WatchlistRepository = DEFAULT_WATCHLIST_REPOSITORY,
    user_profile_repository: UserProfileRepository = DEFAULT_USER_PROFILE_REPOSITORY,
    investment_principles_repository: InvestmentPrinciplesRepository = (
        DEFAULT_INVESTMENT_PRINCIPLES_REPOSITORY
    ),
) -> dict[str, Any]:
    user_id = state.get("user_id") or DEFAULT_USER_ID
    holdings = [
        _to_dict(holding) for holding in holdings_repository.list_by_user(user_id)
    ]
    watchlist = [_to_dict(item) for item in watchlist_repository.list_by_user(user_id)]
    user_profile = user_profile_repository.get_by_user(user_id)
    principles = [
        _to_dict(principle)
        for principle in investment_principles_repository.list_active_by_user(user_id)
    ]
    allocation = _allocation_summary(holdings)
    portfolio = {
        "user_id": user_id,
        "holdings": holdings,
        "allocation_summary": allocation,
    }
    return {
        "portfolio": portfolio,
        "watchlist": watchlist,
        "user_profile": _to_dict(user_profile)
        if user_profile
        else {"user_id": user_id},
        "principles": principles,
        "investment_principles": principles,
        "recent_chat_context": state.get("recent_chat_context", [])[
            -RECENT_CHAT_LIMIT:
        ],
        "data_freshness_status": {},
        "audit_events": [
            _audit_event(
                state,
                "reactive.baseline.loaded",
                {
                    "holding_count": len(holdings),
                    "watchlist_count": len(watchlist),
                    "principle_count": len(principles),
                    "has_user_profile": user_profile is not None,
                },
            )
        ],
    }


def plan_retrieval(state: ReactiveState) -> dict[str, Any]:
    prompt = render_prompt(
        "reactive/plan_retrieval.yaml",
        baseline_summary=_json_for_prompt(_baseline_summary(state)),
    )
    plan = _invoke_groq_structured(prompt, RetrievalPlan, state["user_query"])
    if not isinstance(plan, RetrievalPlan):
        plan = _heuristic_plan(state["user_query"])
    return {
        "retrieval_plan": model_to_dict(plan),
        "audit_events": [
            _audit_event(
                state,
                "reactive.retrieval_plan.created",
                {"intent": plan.intent, "relevant_tickers": plan.relevant_tickers},
            )
        ],
    }


def validate_retrieval_plan(state: ReactiveState) -> dict[str, Any]:
    raw_plan = state.get("retrieval_plan", {})
    try:
        plan = RetrievalPlan.model_validate(raw_plan)
    except ValidationError:
        plan = _heuristic_plan(state["user_query"])
        plan.warnings.append(
            "Planner output was invalid; deterministic fallback was used."
        )
    if plan.intent == "unclear":
        plan.intent = "general_question"
        plan.warnings.append("Unclear intent downgraded to general_question.")

    holdings = _portfolio_holdings(state)
    watchlist = state.get("watchlist", [])
    held_or_watch = set(_holding_tickers(holdings))
    held_or_watch.update(
        str(item.get("ticker", "")).upper()
        for item in watchlist
        if isinstance(item, dict)
    )

    resolved_tickers: list[str] = []
    external_tickers: list[str] = []
    warnings = list(plan.warnings)
    for ticker in plan.relevant_tickers:
        resolved, error = _resolve_canonical_ticker(ticker, holdings, watchlist)
        if resolved is None:
            warnings.append(
                f"Could not resolve ticker {ticker}: {error or 'unknown error'}"
            )
            continue
        resolved_tickers.append(resolved)
        if resolved not in held_or_watch:
            external_tickers.append(resolved)

    if plan.intent == "risk_analysis" and not resolved_tickers:
        resolved_tickers = _holding_tickers(holdings)
    if plan.intent == "recommendation" and not resolved_tickers:
        plan.intent = "portfolio_explanation"
        warnings.append(
            "Recommendation intent downgraded because no resolvable ticker was found."
        )

    retrieval_items: list[str] = []
    if plan.intent == "portfolio_explanation":
        retrieval_items.extend(["allocation", "concentration"])
    elif plan.intent == "recommendation":
        retrieval_items.extend(
            ["market_quote", "concentration", "prior_recommendations", "principles"]
        )
    elif plan.intent == "comparison":
        retrieval_items.extend(["market_quote", "fundamental"])
    elif plan.intent == "risk_analysis":
        retrieval_items.extend(["allocation", "concentration", "market_quote"])
    elif plan.intent == "news_impact":
        retrieval_items.append("news")
    elif plan.intent == "research_followup":
        retrieval_items.append("artifact")
    elif plan.intent == "data_request":
        retrieval_items.append("market_quote")

    plan.relevant_tickers = _dedupe(resolved_tickers)[:MAX_MARKET_TICKERS]
    plan.external_tickers = _dedupe(external_tickers)
    plan.retrieval_items = _dedupe_preserve_case(retrieval_items)
    plan.warnings = warnings
    return {
        "retrieval_plan": model_to_dict(plan),
        "relevant_tickers": plan.relevant_tickers,
        "audit_events": [
            _audit_event(
                state,
                "reactive.retrieval_plan.validated",
                {
                    "intent": plan.intent,
                    "retrieval_items": plan.retrieval_items,
                    "warnings": warnings,
                },
            )
        ],
    }


def execute_retrieval(
    state: ReactiveState,
    market_data_service: MarketDataService = DEFAULT_MARKET_DATA_SERVICE,
    recommendations_repository: RecommendationsRepository = (
        DEFAULT_RECOMMENDATIONS_REPOSITORY
    ),
) -> dict[str, Any]:
    plan = RetrievalPlan.model_validate(state.get("retrieval_plan", {}))
    evidence: list[EvidenceItem] = []

    if "allocation" in plan.retrieval_items:
        evidence.append(
            EvidenceItem(
                evidence_id=_evidence_id("allocation", "portfolio"),
                source_type="allocation",
                provider="deterministic_backend",
                fetched_at=_utc_now(),
                quality_tier="fresh",
                payload=state.get("portfolio", {}).get("allocation_summary", {}),
            )
        )
    if "concentration" in plan.retrieval_items:
        evidence.append(
            EvidenceItem(
                evidence_id=_evidence_id("portfolio", "concentration"),
                source_type="portfolio",
                provider="deterministic_backend",
                fetched_at=_utc_now(),
                quality_tier="fresh",
                payload={
                    "top_concentration": state.get("portfolio", {})
                    .get("allocation_summary", {})
                    .get("top_concentration", [])
                },
            )
        )
    if "market_quote" in plan.retrieval_items:
        quotes = market_data_service.get_quotes(plan.relevant_tickers)
        for ticker in plan.relevant_tickers:
            envelope = quotes.get(ticker) or quotes.get(ticker.upper())
            if envelope is None:
                evidence.append(
                    EvidenceItem(
                        evidence_id=_evidence_id("market_quote", ticker),
                        source_type="market_quote",
                        ticker=ticker,
                        provider="yfinance",
                        fetched_at=_utc_now(),
                        quality_tier="unavailable",
                        payload={},
                        failure_reason="No market quote returned.",
                    )
                )
            else:
                evidence.append(_envelope_to_evidence("market_quote", ticker, envelope))
    if "fundamental" in plan.retrieval_items:
        fundamentals = market_data_service.get_fundamentals(plan.relevant_tickers)
        for ticker in plan.relevant_tickers:
            envelope = fundamentals.get(ticker) or fundamentals.get(ticker.upper())
            if envelope is not None:
                evidence.append(_envelope_to_evidence("fundamental", ticker, envelope))
    if "news" in plan.retrieval_items:
        for ticker in plan.relevant_tickers[:MAX_MARKET_TICKERS]:
            documents = chroma_client.query_documents(
                state["user_query"], ticker=ticker
            )[:MAX_NEWS_CHUNKS]
            if not documents:
                evidence.append(
                    EvidenceItem(
                        evidence_id=_evidence_id("news", ticker),
                        source_type="news",
                        ticker=ticker,
                        provider="chroma",
                        fetched_at=_utc_now(),
                        quality_tier="unavailable",
                        payload={},
                        failure_reason="No indexed news matched this query.",
                    )
                )
            for document in documents:
                evidence.append(
                    EvidenceItem(
                        evidence_id=_evidence_id("news", ticker),
                        source_type="news",
                        ticker=ticker,
                        provider=str(document.metadata.get("source", "chroma")),
                        fetched_at=_utc_now(),
                        quality_tier="limited",
                        payload={
                            "document_id": document.document_id,
                            "text": document.text,
                            "metadata": document.metadata,
                        },
                    )
                )
    if "artifact" in plan.retrieval_items:
        documents = chroma_client.query_documents(state["user_query"])[:MAX_ARTIFACTS]
        for document in documents:
            evidence.append(
                EvidenceItem(
                    evidence_id=_evidence_id("artifact", document.document_id),
                    source_type="artifact",
                    provider="chroma",
                    fetched_at=_utc_now(),
                    quality_tier="limited",
                    payload={
                        "document_id": document.document_id,
                        "text": document.text,
                        "metadata": document.metadata,
                    },
                )
            )
    if "prior_recommendations" in plan.retrieval_items:
        for recommendation in recommendations_repository.list_by_tickers(
            state.get("user_id", DEFAULT_USER_ID), plan.relevant_tickers
        ):
            evidence.append(
                EvidenceItem(
                    evidence_id=_evidence_id(
                        "recommendation", recommendation.recommendation_id
                    ),
                    source_type="recommendation",
                    provider="paisa",
                    fetched_at=_utc_now(),
                    quality_tier="fresh",
                    payload=asdict(recommendation),
                )
            )

    return {
        "retrieved_chunks": [model_to_dict(item) for item in evidence],
        "audit_events": [
            _audit_event(
                state,
                "reactive.retrieval.executed",
                {"retrieved_count": len(evidence), "items": plan.retrieval_items},
            )
        ],
    }


def build_evidence_pack(state: ReactiveState) -> dict[str, Any]:
    items = [
        EvidenceItem.model_validate(item) for item in state.get("retrieved_chunks", [])
    ]
    disclosure = RetrievalDisclosure(
        deterministic=[
            "user profile",
            "portfolio holdings",
            "watchlist",
            "investment principles",
        ],
        llm_planned=[
            f"{item.source_type}: {item.ticker or 'portfolio'}"
            for item in items
            if item.quality_tier != "unavailable"
        ],
        unavailable=[
            {
                "item": f"{item.source_type}: {item.ticker or 'portfolio'}",
                "reason": item.failure_reason or "Unavailable.",
            }
            for item in items
            if item.quality_tier == "unavailable"
        ],
    )
    return {
        "evidence_pack": [model_to_dict(item) for item in items],
        "retrieval_disclosure": model_to_dict(disclosure),
        "audit_events": [
            _audit_event(
                state,
                "reactive.evidence_pack.sealed",
                {"evidence_count": len(items)},
            )
        ],
    }


def data_quality_gate(state: ReactiveState) -> dict[str, Any]:
    plan = RetrievalPlan.model_validate(state.get("retrieval_plan", {}))
    holdings = _portfolio_holdings(state)
    evidence = [
        EvidenceItem.model_validate(item) for item in state.get("evidence_pack", [])
    ]
    missing_critical: list[str] = []
    warnings = list(plan.warnings)
    stale_items = [
        item.evidence_id for item in evidence if item.quality_tier == "stale"
    ]

    portfolio_required = plan.intent in {
        "portfolio_explanation",
        "recommendation",
        "risk_analysis",
    }
    if portfolio_required and not holdings:
        missing_critical.append("portfolio holdings")

    if plan.intent == "recommendation" and not state.get("user_profile", {}).get(
        "risk_tolerance"
    ):
        warnings.append("Risk profile is missing; using MVP default risk framing.")

    if plan.intent in {"recommendation", "comparison", "risk_analysis", "data_request"}:
        market_items = [item for item in evidence if item.source_type == "market_quote"]
        if market_items and all(
            item.quality_tier == "unavailable" for item in market_items
        ):
            if plan.intent == "risk_analysis":
                warnings.append(
                    "Market snapshots are unavailable; using holdings-only risk."
                )
            else:
                missing_critical.append("market snapshots for relevant tickers")

    if missing_critical:
        overall = "critical_failure"
    elif stale_items:
        overall = "stale"
    elif any(item.quality_tier == "limited" for item in evidence) or warnings:
        overall = "limited"
    else:
        overall = "good"

    report = DataQualityReport(
        overall=overall,  # type: ignore[arg-type]
        missing_critical=missing_critical,
        stale_items=stale_items,
        warnings=warnings,
    )
    update: dict[str, Any] = {
        "data_quality": model_to_dict(report),
        "data_quality_verdict": report.overall,
        "data_quality_passed": report.overall != "critical_failure",
        "data_quality_flags": missing_critical + stale_items + warnings,
        "audit_events": [
            _audit_event(
                state,
                "reactive.data_quality.completed",
                model_to_dict(report),
            )
        ],
    }
    if report.overall == "critical_failure":
        final = _insufficient_final_response(state, report)
        update["final_response"] = model_to_dict(final)
    return update


def _insufficient_final_response(
    state: ReactiveState, report: DataQualityReport
) -> FinalResponse:
    missing = report.missing_critical or ["required evidence"]
    card = InsufficientDataCard(
        missing=missing,
        warnings=report.warnings,
        next_steps=["Import or refresh portfolio and market data, then ask again."],
    )
    text = (
        "I do not have enough validated data to answer this safely. Missing: "
        + ", ".join(missing)
        + "."
    )
    return FinalResponse(
        response_type="insufficient_data",
        bubble_text=text,
        card_payload=model_to_dict(card),
        confidence_tier="insufficient",
        data_quality=report.overall,
        retrieval_disclosure=state.get("retrieval_disclosure", {}),
        evidence_ids=[],
        assumptions=[],
        principle_conflicts=[],
        graph_run_id=state["graph_run_id"],
    )


def final_reasoning(state: ReactiveState) -> dict[str, Any]:
    plan = RetrievalPlan.model_validate(state.get("retrieval_plan", {}))
    if plan.intent == "research_run_trigger":
        card = ResearchRunStatusCard(
            status="not_started",
            message="Deep Research is a separate user-triggered workflow.",
            next_action="Open the Deep Research page to configure and start a run.",
        )
        output = LLMOutput(
            response_type="research_run_status",
            bubble_text=(
                "Deep Research is available as a separate workflow. Open the "
                "Deep Research page to start a run."
            ),
            card_payload=model_to_dict(card),
            evidence_ids_used=[],
            confidence_tier="medium",
            assumptions=[],
            principle_conflicts=[],
        )
        return {
            "llm_raw_output": output.model_dump_json(),
            "parsed_output": model_to_dict(output),
        }

    prompt = render_prompt(
        "reactive/final_reasoning.yaml",
        baseline_summary=_json_for_prompt(_baseline_summary(state)),
        retrieval_disclosure=_json_for_prompt(state.get("retrieval_disclosure", {})),
        data_quality=_json_for_prompt(state.get("data_quality", {})),
        evidence_pack=_json_for_prompt(state.get("evidence_pack", [])),
    )
    structured = _invoke_groq_structured(prompt, LLMOutput, state["user_query"])
    if isinstance(structured, LLMOutput):
        raw = structured.model_dump_json()
        parsed = structured
    else:
        raw_text = _invoke_groq_text(prompt, state["user_query"])
        parsed = _deterministic_llm_output(state, raw_text)
        raw = raw_text or parsed.model_dump_json()
    return {
        "llm_raw_output": raw,
        "audit_events": [
            _audit_event(
                state,
                "reactive.final_reasoning.completed",
                {"response_type": parsed.response_type, "raw_length": len(raw)},
            )
        ],
    }


def _deterministic_llm_output(
    state: ReactiveState, raw_text: str | None = None
) -> LLMOutput:
    plan = RetrievalPlan.model_validate(state.get("retrieval_plan", {}))
    data_quality = state.get("data_quality", {}).get("overall", "good")
    evidence_ids = [
        item.get("evidence_id")
        for item in state.get("evidence_pack", [])
        if isinstance(item.get("evidence_id"), str)
    ]
    if plan.intent == "recommendation":
        card = RecommendationCard(
            action="insufficient_data"
            if data_quality == "critical_failure"
            else "watch",
            summary=raw_text
            or (
                "Based on the validated evidence available, treat this as an "
                "advisory watch item rather than an execution signal."
            ),
            confidence_tier="low",
            data_quality=data_quality,
            bear_case=(
                "The available evidence is limited, so downside cannot be "
                "fully quantified."
            ),
            key_risks=[
                "Data coverage may be incomplete.",
                "Market conditions may change after the fetched evidence.",
            ],
            no_action_case=(
                "Taking no action remains reasonable until stronger evidence "
                "is available."
            ),
            assumptions=[
                "MVP analysis uses imported holdings and available provider data only."
            ],
            evidence_ids=evidence_ids,
        )
        return LLMOutput(
            response_type="recommendation",
            bubble_text=card.summary,
            card_payload=model_to_dict(card),
            evidence_ids_used=evidence_ids,
            confidence_tier="low",
            assumptions=card.assumptions,
            principle_conflicts=[],
        )
    if plan.intent in {"portfolio_explanation", "risk_analysis"}:
        allocation = state.get("portfolio", {}).get("allocation_summary", {})
        card = PortfolioSnapshotCard(
            total_holdings=len(_portfolio_holdings(state)),
            allocation=allocation.get("asset_allocation", []),
            concentration=allocation.get("top_concentration", []),
            risks=["Review high single-asset or single-ticker concentration."],
            suggested_prompts=[
                "Stress-test my top holding.",
                "Explain my asset-class exposure.",
            ],
            evidence_ids=evidence_ids,
        )
        return LLMOutput(
            response_type="portfolio_snapshot",
            bubble_text=(
                "Here is a portfolio-level view based on your imported holdings."
            ),
            card_payload=model_to_dict(card),
            evidence_ids_used=evidence_ids,
            confidence_tier="medium",
            assumptions=[
                "Current market prices may be unavailable; imported cost is "
                "used where needed."
            ],
            principle_conflicts=[],
        )
    if plan.intent == "comparison":
        card = ComparisonCard(
            tickers=plan.relevant_tickers,
            summary=raw_text
            or "Comparison is based on the validated evidence that could be retrieved.",
            metrics={},
            risk_notes=[
                "Compare valuation and risk only after checking fresh market data."
            ],
            data_quality=data_quality,
            caveats=["Some fundamentals may be unavailable in the MVP provider data."],
            evidence_ids=evidence_ids,
        )
        return LLMOutput(
            response_type="comparison",
            bubble_text=card.summary,
            card_payload=model_to_dict(card),
            evidence_ids_used=evidence_ids,
            confidence_tier="low",
            assumptions=[],
            principle_conflicts=[],
        )
    if plan.intent == "news_impact":
        card = NewsDigestCard(
            tickers=plan.relevant_tickers,
            items=[],
            summary=raw_text
            or (
                "I could not find enough indexed news evidence for a detailed "
                "impact summary."
            ),
            data_quality=data_quality,
            caveats=[
                "News retrieval depends on indexed documents currently "
                "available to PAISA."
            ],
            evidence_ids=evidence_ids,
        )
        return LLMOutput(
            response_type="news_digest",
            bubble_text=card.summary,
            card_payload=model_to_dict(card),
            evidence_ids_used=evidence_ids,
            confidence_tier="low",
            assumptions=[],
            principle_conflicts=[],
        )
    return LLMOutput(
        response_type="plain_chat",
        bubble_text=raw_text or _plain_chat_fallback(state["user_query"]),
        card_payload=None,
        evidence_ids_used=[],
        confidence_tier="medium",
        assumptions=[],
        principle_conflicts=[],
    )


def _plain_chat_fallback(query: str) -> str:
    lower = query.lower()
    if "beta" in lower:
        return (
            "Beta measures how sensitive an asset is to broad market movements. "
            "A beta above 1 usually means the asset moves more than the market; "
            "below 1 means it tends to move less."
        )
    if lower.strip() in {"hi", "hello", "hey"}:
        return (
            "Hi. Ask me about portfolio risk, a holding, a comparison, market "
            "news, or an investing concept."
        )
    return (
        "I can help explain investing concepts, inspect your portfolio context, "
        "compare holdings, or produce advisory analysis when enough validated "
        "evidence is available."
    )


def parse_validate_output(state: ReactiveState) -> dict[str, Any]:
    raw = state.get("llm_raw_output", "")
    validation_errors: list[str] = []
    output: LLMOutput
    try:
        parsed_json = json.loads(raw)
        output = LLMOutput.model_validate(parsed_json)
    except Exception:
        if state.get("parsed_output"):
            try:
                output = LLMOutput.model_validate(state["parsed_output"])
            except Exception as exc:
                validation_errors.append(str(exc))
                output = _error_output("The assistant response could not be parsed.")
        else:
            validation_errors.append("LLM output was not valid JSON.")
            output = _deterministic_llm_output(state, raw if raw.strip() else None)

    valid_ids = {
        item.get("evidence_id")
        for item in state.get("evidence_pack", [])
        if isinstance(item.get("evidence_id"), str)
    }
    invalid_ids = [
        evidence_id
        for evidence_id in output.evidence_ids_used
        if evidence_id not in valid_ids
    ]
    if invalid_ids:
        validation_errors.append(
            f"Invalid evidence IDs stripped: {', '.join(invalid_ids)}"
        )
        output.evidence_ids_used = [
            evidence_id
            for evidence_id in output.evidence_ids_used
            if evidence_id in valid_ids
        ]

    card_model = CARD_MODELS.get(output.response_type)
    if output.card_payload is not None and card_model is not None:
        try:
            output.card_payload = model_to_dict(
                card_model.model_validate(output.card_payload)
            )
        except ValidationError as exc:
            validation_errors.append(str(exc))
            output = LLMOutput(
                response_type="plain_chat",
                bubble_text=output.bubble_text,
                card_payload=None,
                evidence_ids_used=output.evidence_ids_used,
                confidence_tier=output.confidence_tier,
                assumptions=output.assumptions,
                principle_conflicts=output.principle_conflicts,
            )
    elif output.card_payload is not None and output.response_type not in CARD_MODELS:
        validation_errors.append(
            "Unsupported card response type degraded to plain_chat: "
            f"{output.response_type}"
        )
        output = LLMOutput(
            response_type="plain_chat",
            bubble_text=output.bubble_text,
            card_payload=None,
            evidence_ids_used=output.evidence_ids_used,
            confidence_tier=output.confidence_tier,
            assumptions=output.assumptions,
            principle_conflicts=output.principle_conflicts,
        )

    return {
        "parsed_output": model_to_dict(output),
        "validation_errors": validation_errors,
        "audit_events": [
            _audit_event(
                state,
                "reactive.output.validated",
                {
                    "validation_errors": validation_errors,
                    "response_type": output.response_type,
                },
            )
        ],
    }


def _error_output(message: str) -> LLMOutput:
    card = ErrorCard(message=message, recoverable=True)
    return LLMOutput(
        response_type="error",
        bubble_text=message,
        card_payload=model_to_dict(card),
        evidence_ids_used=[],
        confidence_tier="insufficient",
        assumptions=[],
        principle_conflicts=[],
    )


def compliance_check(state: ReactiveState) -> dict[str, Any]:
    output = LLMOutput.model_validate(state.get("parsed_output", {}))
    conflicts = list(output.principle_conflicts)
    principles = state.get("investment_principles") or state.get("principles", [])
    hard_principles = [
        principle
        for principle in principles
        if isinstance(principle, dict) and int(principle.get("priority", 99)) <= 1
    ]
    action = ""
    if isinstance(output.card_payload, dict):
        action = str(output.card_payload.get("action", "")).lower()
    if action in {"buy", "sell", "add", "reduce"}:
        for principle in hard_principles:
            body = str(principle.get("body", "")).lower()
            title = str(principle.get("title", "Hard principle"))
            if "no" in body or "avoid" in body:
                conflicts.append(
                    f"Potential conflict with priority-1 principle: {title}"
                )
    output.principle_conflicts = _dedupe(conflicts)
    return {
        "parsed_output": model_to_dict(output),
        "principle_conflicts": output.principle_conflicts,
        "audit_events": [
            _audit_event(
                state,
                "reactive.compliance.checked",
                {"principle_conflicts": output.principle_conflicts},
            )
        ],
    }


def format_response(state: ReactiveState) -> dict[str, Any]:
    if state.get("final_response"):
        return {}
    output = LLMOutput.model_validate(state.get("parsed_output", {}))
    data_quality = state.get("data_quality", {}).get("overall", "good")
    final = FinalResponse(
        response_type=output.response_type,
        bubble_text=output.bubble_text,
        card_payload=output.card_payload,
        confidence_tier=output.confidence_tier,
        data_quality=data_quality,
        retrieval_disclosure=state.get("retrieval_disclosure", {}),
        evidence_ids=output.evidence_ids_used,
        assumptions=output.assumptions,
        principle_conflicts=output.principle_conflicts,
        graph_run_id=state["graph_run_id"],
    )
    return {
        "final_response": model_to_dict(final),
        "audit_events": [
            _audit_event(
                state,
                "reactive.response.formatted",
                {"response_type": final.response_type},
            )
        ],
    }


def persist_turn(
    state: ReactiveState,
    audit_repository: AuditRepository = DEFAULT_AUDIT_REPOSITORY,
    recommendations_repository: RecommendationsRepository = (
        DEFAULT_RECOMMENDATIONS_REPOSITORY
    ),
) -> dict[str, Any]:
    final_response = FinalResponse.model_validate(state.get("final_response", {}))
    final_hash = hashlib.sha256(
        final_response.model_dump_json().encode("utf-8")
    ).hexdigest()
    events = list(state.get("audit_events", []))
    events.append(
        {
            "audit_event_id": str(uuid4()),
            "run_id": state.get("graph_run_id"),
            "session_id": state["session_id"],
            "actor": "system",
            "event_type": "reactive.turn.completed",
            "event_timestamp": _utc_now().isoformat(),
            "metadata_json": {
                "input_sha256": hashlib.sha256(
                    state["user_query"].encode("utf-8")
                ).hexdigest(),
                "output_sha256": final_hash,
                "response_type": final_response.response_type,
            },
        }
    )
    audit_repository.insert_many(events)
    if (
        final_response.response_type == "recommendation"
        and final_response.card_payload
        and final_response.confidence_tier != "insufficient"
    ):
        recommendations_repository.insert(
            RecommendationRecord(
                user_id=state.get("user_id", DEFAULT_USER_ID),
                source_type="reactive_chat",
                source_id=state.get("graph_run_id", ""),
                action=str(final_response.card_payload.get("action", "unknown")),
                confidence_tier=final_response.confidence_tier,
                data_quality=final_response.data_quality,
                summary=final_response.bubble_text,
                card_payload=final_response.card_payload,
            )
        )
    return {}
