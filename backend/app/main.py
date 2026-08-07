from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.artifacts import router as artifacts_router
from app.api.v1.chat import router as chat_router
from app.api.v1.portfolio import router as portfolio_router
from app.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(artifacts_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=settings.api_v1_prefix)
app.include_router(portfolio_router, prefix=settings.api_v1_prefix)
