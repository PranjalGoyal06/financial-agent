from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import settings

_sync_url = settings.database_url.replace("+asyncpg", "")

def get_checkpointer_context():
    return AsyncPostgresSaver.from_conn_string(_sync_url)
