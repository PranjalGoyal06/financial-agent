from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketSnapshotModel


def make_params_hash(ticker: str, snapshot_type: str, **kwargs: str) -> str:
    """Deterministic SHA-256 over the full set of fetch parameters.

    kwargs are sorted so that key ordering never affects the hash.
    Example: make_params_hash("INFY.NS", "historical", range="6mo", interval="1d")
    """
    parts = [f"ticker={ticker}", f"type={snapshot_type}"]
    parts += [f"{k}={v}" for k, v in sorted(kwargs.items())]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def get_cached(
    session: AsyncSession,
    snapshot_type: str,
    params_hash: str,
) -> dict | None:
    """Return the deserialized payload if a fresh snapshot exists, else None.

    Freshness is determined by fresh_until > now(UTC). Expired rows are left in
    place and overwritten on the next successful fetch (put_cache upsert).
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(MarketSnapshotModel).where(
            MarketSnapshotModel.params_hash == params_hash,
            MarketSnapshotModel.snapshot_type == snapshot_type,
            MarketSnapshotModel.fresh_until > now,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        return None
    return json.loads(snapshot.payload_json)


async def put_cache(
    session: AsyncSession,
    *,
    snapshot_type: str,
    params_hash: str,
    ticker: str,
    payload: dict,
    provider: str,
    fresh_until: datetime,
) -> None:
    """Upsert a snapshot row.

    On conflict (same params_hash), updates payload, fetched_at, and fresh_until.
    The caller is responsible for wrapping this in an explicit transaction
    (async with session.begin()).
    """
    now = datetime.now(timezone.utc)
    payload_str = json.dumps(payload, default=str)
    stmt = (
        pg_insert(MarketSnapshotModel)
        .values(
            ticker=ticker,
            snapshot_type=snapshot_type,
            params_hash=params_hash,
            payload_json=payload_str,
            provider=provider,
            fetched_at=now,
            fresh_until=fresh_until,
        )
        .on_conflict_do_update(
            index_elements=["params_hash"],
            set_={
                "payload_json": payload_str,
                "fetched_at": now,
                "fresh_until": fresh_until,
            },
        )
    )
    await session.execute(stmt)
