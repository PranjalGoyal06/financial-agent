from __future__ import annotations

from app.evidence.schemas import EvidencePack
from app.research.prompts import format_evidence_pack

SYSTEM_PROMPT = """You are an equity research sector analyst analyzing the {sector_name} sector in India.
Your task is to synthesize sector-specific news, industry data, and trends, and output a structured JSON analysis.

CRITICAL INSTRUCTIONS:
1. Every claim, driver, and analysis narrative must cite relevant evidence using the stable citation ID in square brackets (e.g., [news_a1b2c3d4], [mkt_f1e2d3c4]). Do not invent citation IDs.
2. Address sector-specific headwinds, tailwinds, and government policies affecting {sector_name} in India.
3. Output MUST conform strictly to the required JSON schema.
"""

USER_TEMPLATE = """Here is the collected evidence for the {sector_name} sector:

{formatted_evidence}

Based on the evidence above, generate the SectorSynthesis structure for the "{sector_name}" sector. Ensure every key driver and section in the analysis narrative contains explicit citations to the evidence IDs.
"""


def get_sector_messages(sector_name: str, pack: EvidencePack) -> list[dict[str, str]]:
    """Return the system and user messages for the Sector Synthesis node."""
    formatted_evidence = format_evidence_pack(pack)
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(sector_name=sector_name)},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                sector_name=sector_name, formatted_evidence=formatted_evidence
            ),
        },
    ]
