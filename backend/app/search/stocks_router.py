import json
import os
from typing import List, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()

# In-memory cache for the stocks data
_STOCKS_CACHE: List[Dict[str, str]] = []

class StockResponse(BaseModel):
    symbol: str
    name: str
    isin: Optional[str] = None
    series: Optional[str] = None
    exchange: Optional[str] = "NSE"

def load_stocks_data():
    global _STOCKS_CACHE
    if _STOCKS_CACHE:
        return
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "data", "stocks.json")
    
    if not os.path.exists(json_path):
        print(f"Warning: Stock JSON data file not found at {json_path}")
        return
        
    try:
        with open(json_path, mode="r", encoding="utf-8") as f:
            _STOCKS_CACHE = json.load(f)
    except Exception as e:
        print(f"Error loading stock data: {e}")

@router.on_event("startup")
async def startup_event():
    load_stocks_data()

@router.get("/stocks", response_model=List[StockResponse])
async def search_stocks(q: str = Query("")):
    """Search stocks by symbol or name. Returns top 10 results."""
    query = q.lower().strip()
    if not query:
        return []
        
    # Lazy load just in case startup event didn't fire (e.g. testing)
    if not _STOCKS_CACHE:
        load_stocks_data()
        
    results = []
    # Simple linear search - fast enough for ~2300 items
    for stock in _STOCKS_CACHE:
        if query in stock["symbol"].lower() or query in stock["name"].lower():
            results.append(stock)
            if len(results) >= 10:
                break
                
    return results
