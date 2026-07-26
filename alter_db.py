import asyncio
from backend.app.db import engine
from sqlalchemy import text

async def alter():
    async with engine.begin() as conn:
        await conn.execute(text('ALTER TABLE market_snapshots ALTER COLUMN payload_json TYPE JSONB USING payload_json::jsonb'))
        await conn.execute(text('ALTER TABLE artifacts ALTER COLUMN metadata_json TYPE JSONB USING metadata_json::jsonb'))

asyncio.run(alter())
