from __future__ import annotations

import json

from app.evidence.schemas import EvidencePack
from app.research.prompts import format_evidence_pack

SYSTEM_PROMPT = """You are a chief investment officer (CIO) managing an equity portfolio.
Your task is to synthesize the macro environment, sector reviews, and individual ticker syntheses, and recommend portfolio-level adjustments.

CRITICAL INSTRUCTIONS:
1. Every recommended adjustment, pick, risk assessment, and analysis narrative must cite relevant evidence using the stable citation ID in square brackets (e.g., [news_a1b2c3d4], [mkt_f1e2d3c4]).
2. Leverage the correlation matrix and individual ticker recommendations to optimize risk concentration and factor exposures.
3. Output MUST conform strictly to the required JSON schema.
"""

USER_TEMPLATE = """Macro Outlook Summary:
Outlook: {macro_outlook}
Drivers: {macro_drivers}

Sector Outlines:
{sector_outlines}

Individual Stock Recommendations:
{ticker_recommendations}

Correlation Matrix of Returns (computed over historical bars):
{correlation_matrix}

Portfolio Evidence Pack (Macro and general context):
{formatted_evidence}

Generate a comprehensive PortfolioSynthesis JSON object based on the inputs above.
Ensure that rationales for adjustments and analysis narratives contain explicit citations to the evidence IDs.
"""


def get_portfolio_messages(
    macro_outlook: str,
    macro_drivers: list[str],
    sector_outlines: dict[str, dict[str, str]],
    ticker_recs: dict[str, dict],
    correlation_matrix: dict[str, dict[str, float | None]],
    pack: EvidencePack,
) -> list[dict[str, str]]:
    """Return the system and user messages for the Portfolio Synthesis node."""
    formatted_evidence = format_evidence_pack(pack)
    
    # Format sub-structures for readability in prompt
    sector_outlines_str = "\n".join(
        f"- Sector: {sec}\n  Outlook: {data.get('outlook')}\n  Analysis: {data.get('analysis_markdown')}"
        for sec, data in sector_outlines.items()
    )
    
    ticker_recs_str = "\n".join(
        f"- Ticker: {tick}\n  Recommendation: {data.get('recommendation')}\n  Confidence: {data.get('confidence_score')}/100\n  Rationale: {data.get('rationale')}"
        for tick, data in ticker_recs.items()
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                macro_outlook=macro_outlook,
                macro_drivers=str(macro_drivers),
                sector_outlines=sector_outlines_str,
                ticker_recommendations=ticker_recs_str,
                correlation_matrix=json.dumps(correlation_matrix, indent=2),
                formatted_evidence=formatted_evidence,
            ),
        },
    ]
