from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.schemas import (
    ActionCard,
    ActionDeskData,
    Breadth,
    BriefingResponse,
    ClimateData,
    GreetingData,
    Metric,
    NewsItem,
    NoActionData,
    PortfolioNetPnl,
    VixMetric,
)
from app.market_data.provider import YFinanceProvider
from app.models import HoldingModel, PortfolioModel, Artifact

logger = logging.getLogger(__name__)
_provider = YFinanceProvider()


def _get_relative_time_string(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt

    if delta.total_seconds() < 60:
        return "just now"
    elif delta.total_seconds() < 3600:
        mins = int(delta.total_seconds() / 60)
        return f"{mins} min ago"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(delta.total_seconds() / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


def _get_market_closed_time() -> tuple[str, str]:
    """Returns market_status (open/closed) and relative_time_str."""
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    is_weekend = now_ist.weekday() >= 5
    
    # NSE Trading Hours: Mon-Fri 09:15 to 15:30
    dt_0915 = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    dt_1530 = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)

    if not is_weekend and dt_0915 <= now_ist <= dt_1530:
        return "open", ""
    
    # Calculate last close time
    last_close = dt_1530
    if is_weekend:
        days_to_subtract = now_ist.weekday() - 4
        last_close = last_close - timedelta(days=days_to_subtract)
    elif now_ist < dt_0915:
        last_close = last_close - timedelta(days=1)
        if last_close.weekday() >= 5: # If yesterday was weekend
            days_to_subtract = last_close.weekday() - 4
            last_close = last_close - timedelta(days=days_to_subtract)

    return "closed", _get_relative_time_string(last_close)


def _get_vix_tier(value: float) -> str:
    if value < 15:
        return "low"
    elif value < 20:
        return "moderate"
    elif value < 30:
        return "elevated"
    else:
        return "high"


async def _fetch_climate_data(session: AsyncSession, user_id: str) -> ClimateData:
    # 1. Fetch Nifty and VIX
    async def _safe_quote(ticker: str):
        try:
            quote = await asyncio.to_thread(_provider.get_quote, ticker)
            return quote
        except Exception as e:
            logger.warning("Failed to fetch quote for %s: %s", ticker, e)
            return None

    nifty_task = _safe_quote("^NSEI")
    vix_task = _safe_quote("^INDIAVIX")
    nifty, vix = await asyncio.gather(nifty_task, vix_task)

    nifty_metric = Metric(
        price=nifty.price if nifty else None,
        day_change_pct=nifty.day_change_pct if nifty else None
    )
    vix_metric = VixMetric(
        value=vix.price if vix else None,
        tier=_get_vix_tier(vix.price) if vix and vix.price else "unknown"
    )

    # 2. Fetch Holdings and compute Breadth & Net P&L
    stmt = (
        select(HoldingModel)
        .join(PortfolioModel, HoldingModel.portfolio_id == PortfolioModel.id)
        .where(PortfolioModel.user_id == user_id)
    )
    res = await session.execute(stmt)
    holdings = res.scalars().all()

    advancers = 0
    decliners = 0
    unchanged = 0
    total_invested = 0.0
    total_current_value = 0.0

    if holdings:
        tickers = list(set([h.canonical_ticker for h in holdings]))
        quotes = await asyncio.gather(*[_safe_quote(t) for t in tickers])
        quote_map = {t: q for t, q in zip(tickers, quotes) if q}

        for h in holdings:
            q = quote_map.get(h.canonical_ticker)
            if q:
                if q.day_change_pct and q.day_change_pct > 0:
                    advancers += 1
                elif q.day_change_pct and q.day_change_pct < 0:
                    decliners += 1
                else:
                    unchanged += 1
                
                invested = float(h.avg_cost) * float(h.quantity)
                current = q.price * float(h.quantity) if q.price else invested
                total_invested += invested
                total_current_value += current

    net_pnl_amt = total_current_value - total_invested
    net_pnl_pct = (net_pnl_amt / total_invested * 100) if total_invested > 0 else 0.0

    return ClimateData(
        nifty50=nifty_metric,
        india_vix=vix_metric,
        holdings_breadth=Breadth(advancers=advancers, decliners=decliners, unchanged=unchanged),
        portfolio_net_pnl=PortfolioNetPnl(amount=net_pnl_amt, pct=net_pnl_pct),
        fetched_at=datetime.now(timezone.utc).isoformat()
    )


async def get_briefing_data(session: AsyncSession, user_id: str) -> BriefingResponse:
    # 1. Determine Market Status & Time
    market_status, closed_time = _get_market_closed_time()
    greeting_word = "Good evening"
    now_ist_hour = datetime.now(timezone(timedelta(hours=5, minutes=30))).hour
    if now_ist_hour < 12:
        greeting_word = "Good morning"
    elif now_ist_hour < 17:
        greeting_word = "Good afternoon"

    # 2. Get latest research run artifacts
    stmt_latest = select(Artifact.source_ref_id, Artifact.created_at).where(Artifact.source_type == "research").order_by(Artifact.created_at.desc()).limit(1)
    res_latest = await session.execute(stmt_latest)
    latest_run = res_latest.first()

    tickers_analyzed = 0
    run_relative_time = "no runs yet"
    action_cards = []
    total_qualifying = 0
    top_news = []
    total_reviewed = 0
    no_action_count = 0
    has_overflow = False

    if latest_run:
        latest_run_id = latest_run[0]
        run_created_at = latest_run[1]
        run_relative_time = _get_relative_time_string(run_created_at)

        # 3. Analyze Tickers for Action Desk and extract news
        stmt_artifacts = select(Artifact).where(Artifact.source_ref_id == latest_run_id)
        res_artifacts = await session.execute(stmt_artifacts)
        artifacts = res_artifacts.scalars().all()

        for a in artifacts:
            try:
                a._meta = json.loads(a.metadata_json)
            except Exception:
                a._meta = {}

        ticker_artifacts = [a for a in artifacts if a._meta.get("artifact_type") == "ticker" and a._meta.get("target")]
        tickers_analyzed = len(ticker_artifacts)
        
        # We need to compute total reviewed based on holdings actually reviewed
        stmt_holdings = (
            select(HoldingModel.canonical_ticker)
            .join(PortfolioModel, HoldingModel.portfolio_id == PortfolioModel.id)
            .where(PortfolioModel.user_id == user_id)
        )
        res_holdings = await session.execute(stmt_holdings)
        holdings_tickers = {row[0] for row in res_holdings.all() if row[0]}

        reviewed_holdings = [a for a in ticker_artifacts if a._meta.get("target") in holdings_tickers]
        total_reviewed = len(reviewed_holdings)

        # Get prior artifacts to detect shifts
        prior_run_stmt = select(Artifact.source_ref_id).where(Artifact.source_type == "research", Artifact.source_ref_id != latest_run_id).order_by(Artifact.created_at.desc()).limit(1)
        res_prior = await session.execute(prior_run_stmt)
        prior_run_row = res_prior.first()
        prior_artifacts_map = {}
        if prior_run_row:
            prior_run_id = prior_run_row[0]
            stmt_prior = select(Artifact).where(Artifact.source_ref_id == prior_run_id, Artifact.tags.like('%"type:ticker"%'))
            res_prior_artifacts = await session.execute(stmt_prior)
            for a in res_prior_artifacts.scalars().all():
                try:
                    meta = json.loads(a.metadata_json)
                    if meta.get("target"):
                        prior_artifacts_map[meta["target"]] = meta
                except Exception:
                    pass

        action_desk_candidates = []
        all_news = []

        for a in ticker_artifacts:
            current_conf = a._meta.get("confidence_score", 0)
            current_rec = a._meta.get("recommendation", "unknown")
            target = a._meta.get("target", "")
            
            # Action desk conditions
            is_high_conf = current_conf >= 80
            significant_shift = False
            change_context = None
            
            prior = prior_artifacts_map.get(target)
            if prior:
                prior_conf = prior.get("confidence_score", 0)
                prior_rec = prior.get("recommendation", "unknown")
                if abs(current_conf - prior_conf) >= 10:
                    significant_shift = True
                    diff = current_conf - prior_conf
                    change_context = f"confidence {'jumped' if diff > 0 else 'dropped'} {abs(diff)} pts"
                if current_rec != prior_rec:
                    significant_shift = True
                    change_context = f"{'upgraded' if current_rec in ('buy', 'add') else 'downgraded'} from {prior_rec}"

            if is_high_conf or significant_shift:
                if target in holdings_tickers:
                    try:
                        lines = [line.strip() for line in a.content_markdown.split('\n') if line.strip()]
                        # Grab the first line as a headline, strip hashes
                        headline = lines[0].lstrip('#').strip() if lines else f"Analysis for {target}"
                        
                        bear_case_snippet = ""
                        for idx, line in enumerate(lines):
                            if "Bear Case" in line or "Risks" in line:
                                bear_case_snippet = " ".join(lines[idx+1:idx+3])[:120] + "..."
                                break
                        if not bear_case_snippet:
                            bear_case_snippet = "No critical bear cases identified."

                        action_desk_candidates.append(
                            ActionCard(
                                ticker=target,
                                recommendation=current_rec,
                                confidence_score=current_conf,
                                confidence_tier="high" if current_conf >= 80 else ("moderate" if current_conf >= 60 else "low"),
                                headline=headline[:100],
                                bear_case_snippet=bear_case_snippet,
                                change_context=change_context,
                                run_id=latest_run_id
                            )
                        )
                    except Exception as e:
                        logger.error("Error parsing artifact for action card %s: %s", target, e)
            
            # Extract News
            try:
                ep_raw = a._meta.get("evidence_pack_json", "{}")
                ep = json.loads(ep_raw) if isinstance(ep_raw, str) else ep_raw
                for item in ep.get("items", []):
                    if item.get("type") == "news":
                        # Add a target if missing
                        if not item.get("target"):
                            item["target"] = target
                        all_news.append(item)
            except Exception:
                pass

        # Also extract news from macro artifact
        macro_artifacts = [a for a in artifacts if a._meta.get("artifact_type") == "macro"]
        for a in macro_artifacts:
            try:
                ep_raw = a._meta.get("evidence_pack_json", "{}")
                ep = json.loads(ep_raw) if isinstance(ep_raw, str) else ep_raw
                for item in ep.get("items", []):
                    if item.get("type") == "news":
                        if not item.get("target"):
                            item["target"] = "MACRO"
                        all_news.append(item)
            except Exception:
                pass

        # Sort action cards
        action_desk_candidates.sort(key=lambda x: x.confidence_score, reverse=True)
        total_qualifying = len(action_desk_candidates)
        action_cards = action_desk_candidates[:5]
        has_overflow = total_qualifying > 5
        no_action_count = total_reviewed - total_qualifying if total_reviewed > total_qualifying else 0

        # Process News: deduplicate, sort by published/fetched, take top 5
        unique_urls = set()
        deduped_news = []
        for n in all_news:
            url = n.get("url")
            if url and url not in unique_urls:
                unique_urls.add(url)
                deduped_news.append(n)
        
        def _get_sort_date(n: dict) -> str:
            return n.get("published_at") or n.get("fetched_at") or ""
            
        deduped_news.sort(key=_get_sort_date, reverse=True)
        top_news_raw = deduped_news[:5]

        for n in top_news_raw:
            dt_str = n.get("published_at") or n.get("fetched_at")
            rel_time = ""
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    rel_time = _get_relative_time_string(dt)
                except ValueError:
                    rel_time = dt_str

            top_news.append(NewsItem(
                id=n.get("id", ""),
                title=n.get("title", "")[:100],
                url=n.get("url", "#"),
                source=n.get("source", "Source"),
                published_at=rel_time,
                target=n.get("target", "General"),
                summary=n.get("summary", "")[:120]
            ))

    greeting = GreetingData(
        greeting=greeting_word,
        market_status=market_status,
        market_closed_relative_time=closed_time,
        research_run_relative_time=run_relative_time,
        tickers_analyzed=tickers_analyzed
    )

    climate = await _fetch_climate_data(session, user_id)

    action_desk = ActionDeskData(
        cards=action_cards,
        total_qualifying=total_qualifying,
        has_overflow=has_overflow
    )
    
    no_action = NoActionData(
        count=no_action_count,
        total_reviewed=total_reviewed
    )

    return BriefingResponse(
        greeting=greeting,
        climate=climate,
        action_desk=action_desk,
        no_action=no_action,
        top_news=top_news
    )
