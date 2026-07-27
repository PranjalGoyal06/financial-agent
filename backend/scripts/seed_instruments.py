import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

import yfinance as yf
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure app is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.db import Base, AsyncSessionLocal
from app.models import InstrumentModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def recreate_table():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        logger.info("Dropping instruments table...")
        await conn.run_sync(InstrumentModel.__table__.drop, checkfirst=True)
        logger.info("Creating instruments table...")
        await conn.run_sync(InstrumentModel.__table__.create)
    await engine.dispose()


def _fetch_yf_metadata(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        market_cap = info.get("marketCap")
        market_cap_bucket = None
        if market_cap:
            if market_cap > 200_000_000_000:
                market_cap_bucket = "Large Cap"
            elif market_cap >= 50_000_000_000:
                market_cap_bucket = "Mid Cap"
            else:
                market_cap_bucket = "Small Cap"

        return {
            "display_name": info.get("shortName"),
            "company_name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": market_cap,
            "market_cap_bucket": market_cap_bucket,
            "country": info.get("country"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "quote_type": info.get("quoteType"),
            "website": info.get("website"),
            "summary": info.get("longBusinessSummary"),
            "full_time_employees": info.get("fullTimeEmployees"),
            "raw_yfinance_info": info,
        }
    except Exception as exc:
        logger.warning(f"yfinance fetch failed for {ticker}: {exc}")
        return {}


async def seed_data():
    await recreate_table()

    stocks_json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        "app", "search", "data", "stocks.json"
    )
    
    with open(stocks_json_path, "r", encoding="utf-8") as f:
        stocks = json.load(f)

    logger.info(f"Loaded {len(stocks)} stocks from JSON.")

    async with AsyncSessionLocal() as session:
        for idx, stock in enumerate(stocks):
            symbol = stock["symbol"]
            canonical_ticker = symbol
            ticker = f"{symbol}.NS"
            isin = stock.get("isin")
            series = stock.get("series")

            logger.info(f"[{idx+1}/{len(stocks)}] Fetching {ticker}...")
            
            metadata = await asyncio.to_thread(_fetch_yf_metadata, ticker)
            
            inst = InstrumentModel(
                ticker=ticker,
                canonical_ticker=canonical_ticker,
                display_name=metadata.get("display_name") or stock.get("name") or symbol,
                company_name=metadata.get("company_name") or stock.get("name") or symbol,
                sector=metadata.get("sector"),
                industry=metadata.get("industry"),
                market_cap=metadata.get("market_cap"),
                market_cap_bucket=metadata.get("market_cap_bucket"),
                country=metadata.get("country"),
                currency=metadata.get("currency"),
                exchange=metadata.get("exchange") or stock.get("exchange") or "NSE",
                quote_type=metadata.get("quote_type"),
                website=metadata.get("website"),
                summary=metadata.get("summary"),
                full_time_employees=metadata.get("full_time_employees"),
                isin=isin,
                series=series,
                raw_yfinance_info=metadata.get("raw_yfinance_info"),
                last_synced_at=datetime.now(timezone.utc)
            )
            
            session.add(inst)
            
            # Commit in batches of 50
            if (idx + 1) % 50 == 0:
                await session.commit()
                logger.info(f"Committed batch up to index {idx+1}")
                # Sleep a bit to avoid hitting rate limits too hard
                await asyncio.sleep(2)
            else:
                # Small sleep between requests
                await asyncio.sleep(0.1)

        # Final commit
        await session.commit()
        logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed_data())
