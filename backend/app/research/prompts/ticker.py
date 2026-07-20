from __future__ import annotations

from app.evidence.schemas import EvidencePack
from app.research.prompts import format_evidence_pack

SYSTEM_PROMPT = """You are a senior buy-side equity research analyst performing deep fundamental research on {ticker}.
Your task is to synthesize the company-specific news, quantitative metrics, technical indicators, and fundamentals into a structured JSON recommendation.

CRITICAL INSTRUCTIONS ON OUTPUT FIELDS:
1. CITATIONS: Every claim, investment rationale, risk factor, bear case, and analysis narrative must cite relevant evidence using the stable citation ID in square brackets (e.g., [news_a1b2c3d4], [mkt_f1e2d3c4]).
2. BEAR CASE: Provide a detailed, numbers-driven downside scenario analysis based on the evidence. Generic hand-waving is not allowed.
3. KILL THE COMPANY: Identify a plausible, structural, or catastrophic risk that could destroy the business model (e.g., clean energy shift destroying refining margins for oil companies, severe regulatory bans, disruption by AI tools, key personnel risk). Generic risks like 'increased competition' or 'economic slowdown' are strictly unacceptable.
4. CONFIDENCE SCORE: A value from 0 to 100. Lower it if evidence is sparse, stale, or conflicting.
5. RECOMMENDATION: Must select exactly one of: "buy", "add", "hold", "reduce", "watch", "no_action", "insufficient_data".
"""

USER_TEMPLATE = """Research Target: {ticker}
Sector Context: {sector_name}
Sector Analysis Summary:
{sector_analysis_markdown}

Collected Evidence Pack (Price, Technicals, Fundamentals, News, and Prior Research):
{formatted_evidence}

Generate a comprehensive TickerSynthesis JSON object for "{ticker}".
Ensure that:
- Rationale, risk factors, and bear cases cite specific evidence IDs.
- 'kill_the_company' is highly specific to {ticker}'s industry and business model.
"""


def get_ticker_messages(
    ticker: str,
    sector_name: str,
    sector_analysis_markdown: str,
    pack: EvidencePack,
) -> list[dict[str, str]]:
    """Return the system and user messages for the Ticker Synthesis node."""
    formatted_evidence = format_evidence_pack(pack)
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(ticker=ticker)},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                ticker=ticker,
                sector_name=sector_name,
                sector_analysis_markdown=sector_analysis_markdown,
                formatted_evidence=formatted_evidence,
            ),
        },
    ]
