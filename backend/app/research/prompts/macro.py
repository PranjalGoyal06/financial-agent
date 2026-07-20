from __future__ import annotations

from app.evidence.schemas import EvidencePack
from app.research.prompts import format_evidence_pack

SYSTEM_PROMPT = """You are a senior macroeconomist and investment strategist analyzing the Indian equity market.
Your task is to synthesize market-wide macro evidence and output a structured JSON analysis.

CRITICAL INSTRUCTIONS:
1. Every claim, driver, and analysis narrative must cite relevant evidence using the stable citation ID in square brackets (e.g., [news_a1b2c3d4], [mkt_f1e2d3c4]). Do not invent citation IDs.
2. The analysis must be professional, objective, and dense with concrete data points from the evidence.
3. Output MUST conform strictly to the required JSON schema.
"""

USER_TEMPLATE = """Here is the collected macro evidence for the Indian equity market:

{formatted_evidence}

Based on the evidence above, generate the MacroSynthesis structure. Ensure every key driver and section in the analysis narrative contains explicit citations to the evidence IDs.
"""


def get_macro_messages(pack: EvidencePack) -> list[dict[str, str]]:
    """Return the system and user messages for the Macro Synthesis node."""
    formatted_evidence = format_evidence_pack(pack)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(formatted_evidence=formatted_evidence),
        },
    ]
