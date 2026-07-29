from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    poolclass=NullPool,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


from sqlalchemy import text


async def init_db() -> None:
    from app import models  # noqa: F401
    from app.checkpointer import get_checkpointer_context

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        try:
            await connection.execute(
                text("ALTER TABLE research_schedules ADD COLUMN IF NOT EXISTS watchlist_id VARCHAR;")
            )
        except Exception:
            pass
        
    async with get_checkpointer_context() as checkpointer:
        await checkpointer.setup()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
