from __future__ import annotations

import asyncio
from collections.abc import Generator
from uuid import uuid4

import pytest
from app.config import settings
from app.db import AsyncSessionLocal, init_db
from app.main import app
from app.models import MarketSnapshotModel, UserModel
from fastapi.testclient import TestClient
from sqlalchemy import delete


async def _clean_database(user_id: str) -> None:
    """Clean up user-related records and market snapshots."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Deleting the user cascades to portfolios, imports, and holdings
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.execute(delete(MarketSnapshotModel))


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Provide a TestClient with database initialization and user isolation."""
    user_id = f"test-user-{uuid4()}"
    monkeypatch.setattr(settings, "default_user_id", user_id)

    # Initialize tables and clean database
    asyncio.run(init_db())
    asyncio.run(_clean_database(user_id))

    with TestClient(app) as test_client:
        yield test_client

    # Teardown
    asyncio.run(_clean_database(user_id))
