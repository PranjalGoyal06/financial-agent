import asyncio
import logging
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete
from app.db import AsyncSessionLocal
from app.models import Artifact
from app.research.store import _client, COLLECTION_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clear_all_artifacts():
    # 1. Delete all artifacts from PostgreSQL
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(delete(Artifact))
            deleted_count = result.rowcount
            logger.info("Deleted %d artifacts from PostgreSQL database.", deleted_count)

    # 2. Reset/Clear Chroma DB collection
    try:
        _client.delete_collection(COLLECTION_NAME)
        logger.info("Deleted Chroma collection '%s'.", COLLECTION_NAME)
    except Exception as e:
        logger.warning("Chroma collection deletion note: %s", e)

if __name__ == "__main__":
    asyncio.run(clear_all_artifacts())
