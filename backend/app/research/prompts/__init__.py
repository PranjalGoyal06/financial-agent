from __future__ import annotations

from app.evidence.schemas import EvidencePack


def format_evidence_pack(pack: EvidencePack | None) -> str:
    """Format an EvidencePack into a structured, readable string for the LLM.

    Each item is prefixed with its stable citation ID (e.g. [news_a1b2c3d4] or
    [mkt_f1e2d3c4]) so the LLM can reference it directly in its structured output.
    """
    if not pack or not pack.items:
        return "No evidence collected."

    lines = []
    for item in pack.items:
        lines.append(f"[{item.id}] Type: {item.type} | Source: {item.source} ({item.freshness})")
        if item.title:
            lines.append(f"Title: {item.title}")
        if item.url:
            lines.append(f"URL: {item.url}")
        lines.append(f"Summary: {item.summary.strip()}")
        lines.append("-" * 40)

    return "\n".join(lines)
