from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.integrations import chroma_client
from app.integrations import yfinance_client
from app.services import audit_service


def _chunk_text(text: str, chunk_size_tokens: int = 300) -> list[str]:
    tokens = text.split()
    if not tokens:
        return []
    return [
        " ".join(tokens[index : index + chunk_size_tokens])
        for index in range(0, len(tokens), chunk_size_tokens)
    ]


def ingest_news_for_tickers(tickers: list[str]) -> dict[str, list[Any]]:
    ingested: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for ticker in tickers:
        result = yfinance_client.get_news(ticker)
        if isinstance(result, dict):
            result = result.get(ticker) or result.get(ticker.upper()) or next(iter(result.values()))

        if not result.ok or result.value is None:
            audit_service.log_event(
                "news_ingest_skipped",
                "Skipping ticker because yfinance news fetch failed",
                {"ticker": ticker, "error": result.error.message if result.error else "unknown"},
            )
            failed.append({"ticker": ticker, "reason": result.error.message if result.error else "fetch_failed"})
            continue

        articles = result.value.get("articles", [])
        for article in articles:
            body = str(article.get("body") or "").strip()
            chunks = _chunk_text(body)
            if not chunks:
                continue

            fetched_at = result.fetched_at or datetime.now(timezone.utc).isoformat()
            published_at = article.get("published_at")
            document_id = str(article.get("document_id") or uuid4())
            chunk_documents = []
            for index, chunk in enumerate(chunks):
                chunk_documents.append(
                    {
                        "document_id": f"{document_id}:{index}",
                        "text": chunk,
                        "metadata": {
                            "document_id": document_id,
                            "ticker": result.resolved_ticker or ticker,
                            "source": "yfinance_news",
                            "document_type": "news",
                            "fetched_at": fetched_at,
                            "published_at": published_at,
                        },
                    }
                )

            chroma_client.upsert_documents(chunk_documents)
            ingested.append(
                {
                    "ticker": result.resolved_ticker or ticker,
                    "document_id": document_id,
                    "chunk_count": len(chunk_documents),
                }
            )

    return {"ingested": ingested, "failed": failed}
