import asyncio
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import settings
from app.db import AsyncSessionLocal, init_db
from app.main import app
from app.models import MarketSnapshotModel, UserModel

async def _setup_database(user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = UserModel(id=user_id)
            session.add(user)

async def _clean_database(user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.execute(delete(MarketSnapshotModel))

@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """Provide a TestClient with database initialization and user isolation."""
    # Ensure tables exist
    asyncio.run(init_db())
    
    # Generate unique test user ID and inject it
    user_id = f"test-user-{uuid4()}"
    monkeypatch.setattr(settings, "default_user_id", user_id)

    # Clean any remnants and set up user
    asyncio.run(_clean_database(user_id))
    asyncio.run(_setup_database(user_id))

    with TestClient(app) as test_client:
        yield test_client

    # Teardown
    asyncio.run(_clean_database(user_id))
