from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from typing import Any


@dataclass(slots=True)
class ChromaDocument:
    document_id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any]


CHROMA_COLLECTION: dict[str, ChromaDocument] = {}


def embed_text(text: str, dimensions: int = 32) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = sha256(token.encode("utf-8")).digest()
        index = digest[0] % dimensions
        vector[index] += 1.0
    norm = sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def upsert_documents(documents: list[dict[str, Any]]) -> list[str]:
    document_ids: list[str] = []
    for document in documents:
        document_id = str(document["document_id"])
        text = str(document["text"])
        metadata = dict(document.get("metadata", {}))
        CHROMA_COLLECTION[document_id] = ChromaDocument(
            document_id=document_id,
            text=text,
            embedding=embed_text(text),
            metadata=metadata,
        )
        document_ids.append(document_id)
    return document_ids


def query_documents(query: str, ticker: str | None = None) -> list[ChromaDocument]:
    query_terms = set(query.lower().split())
    matches: list[ChromaDocument] = []
    for document in CHROMA_COLLECTION.values():
        if ticker is not None and document.metadata.get("ticker") != ticker:
            continue
        if query_terms.intersection(document.text.lower().split()):
            matches.append(document)
    return matches

