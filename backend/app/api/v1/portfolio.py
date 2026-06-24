from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.db.repositories.holdings_repository import DEFAULT_HOLDINGS_REPOSITORY
from app.services.portfolio_service import DEFAULT_PORTFOLIO_SERVICE

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/imports", status_code=status.HTTP_201_CREATED)
async def import_portfolio(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portfolio CSV must be UTF-8 encoded.",
        ) from exc

    return DEFAULT_PORTFOLIO_SERVICE.ingest_csv(content, source_filename=file.filename)


@router.get("/holdings")
def list_holdings() -> dict[str, Any]:
    holdings = DEFAULT_HOLDINGS_REPOSITORY.list_by_user("demo-user")
    return {"holdings": [asdict(holding) for holding in holdings]}


@router.get("/valuation")
def portfolio_valuation() -> dict[str, Any]:
    return DEFAULT_PORTFOLIO_SERVICE.portfolio_valuation()
