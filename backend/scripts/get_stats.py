import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.abspath('.'), 'backend'))
from app.db import AsyncSessionLocal
from app.models import InstrumentModel
from sqlalchemy import select, func

async def main():
    async with AsyncSessionLocal() as session:
        total = await session.scalar(select(func.count(InstrumentModel.ticker)))
        print(f"Total Instruments: {total}")
        
        print("\n--- Market Cap Buckets ---")
        res = await session.execute(select(InstrumentModel.market_cap_bucket, func.count()).group_by(InstrumentModel.market_cap_bucket))
        for row in res:
            print(f"{row[0] or 'Unknown/None'}: {row[1]}")
            
        print("\n--- Top 5 Sectors ---")
        res = await session.execute(select(InstrumentModel.sector, func.count()).group_by(InstrumentModel.sector).order_by(func.count().desc()).limit(5))
        for row in res:
            print(f"{row[0]}: {row[1]}")
            
        print("\n--- Top 5 Industries ---")
        res = await session.execute(select(InstrumentModel.industry, func.count()).group_by(InstrumentModel.industry).order_by(func.count().desc()).limit(5))
        for row in res:
            print(f"{row[0]}: {row[1]}")
            
        null_mc = await session.scalar(select(func.count(InstrumentModel.ticker)).where(InstrumentModel.market_cap.is_(None)))
        print(f"\nMissing Market Cap Data (NULL): {null_mc}")

asyncio.run(main())
