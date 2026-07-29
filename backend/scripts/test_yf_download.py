import yfinance as yf
import time

# Create dummy tickers
tickers = [f"{t}.NS" for t in ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"] * 100]

start_time = time.time()
data = yf.download(tickers, period="1y", group_by="ticker", progress=False, auto_adjust=False, ignore_tz=True)
print(f"Downloaded {len(tickers)} tickers in {time.time() - start_time:.2f} seconds")
