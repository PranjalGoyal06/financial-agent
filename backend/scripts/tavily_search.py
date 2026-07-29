import os
from tavily import TavilyClient

# Ensure TAVILY_API_KEY is in your environment
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

response = client.search(
    query="Indian macroeconomic outlook 2026 inflation interest rates",
    max_results=5,
    search_depth="basic",
    # topic="news",  # Focuses specifically on news articles rather than general web/PDFs
    days=7         # Strictly limits search results to the last 7 days
)

for i, r in enumerate(response.get("results", []), 1):
    print(f"[{i}] {r.get('title')}")
    print(f"    Date: {r.get('published_date')}")
    print(f"    URL:  {r.get('url')}\n")