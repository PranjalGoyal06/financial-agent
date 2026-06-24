from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.integrations import cache
from app.integrations import yfinance_client
from app.services import audit_service


DEFAULT_TTL_SECONDS = 900


@dataclass(slots=True)
class MarketDataEnvelope:
    ticker: str
    resolved_ticker: str | None
    value: dict[str, Any] | None
    is_stale: bool
    source: str
    error: yfinance_client.ProviderError | None = None


class MarketDataService:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds

    def _cache_key(self, kind: str, ticker: str) -> str:
        return f"{kind}:{ticker}"

    def _fetch_with_cache(
        self,
        kind: str,
        tickers: list[str],
        exchanges: dict[str, str] | None,
        fetcher,
    ) -> dict[str, MarketDataEnvelope]:
        results: dict[str, MarketDataEnvelope] = {}
        for ticker in tickers:
            exchange = (exchanges or {}).get(ticker)
            resolution = yfinance_client.resolve_ticker(ticker, exchange)
            if not resolution.ok or not resolution.resolved_ticker:
                results[ticker] = MarketDataEnvelope(
                    ticker=ticker,
                    resolved_ticker=None,
                    value=None,
                    is_stale=True,
                    source="yfinance",
                    error=resolution.error,
                )
                continue

            cache_key = self._cache_key(kind, resolution.resolved_ticker)
            cached_value, cached_is_stale = cache.get(cache_key)
            if cached_value is not None and not cached_is_stale:
                results[ticker] = MarketDataEnvelope(
                    ticker=ticker,
                    resolved_ticker=resolution.resolved_ticker,
                    value=cached_value,
                    is_stale=False,
                    source="cache",
                )
                continue

            if cached_value is None:
                audit_service.log_event(
                    "cache_miss",
                    f"Cache miss for {kind}",
                    {"ticker": resolution.resolved_ticker, "kind": kind},
                )
            fetch_result = fetcher([resolution.resolved_ticker], None).get(resolution.resolved_ticker)
            if fetch_result and fetch_result.ok and fetch_result.value is not None:
                cache.set(cache_key, fetch_result.value, ttl_seconds=self.ttl_seconds)
                results[ticker] = MarketDataEnvelope(
                    ticker=ticker,
                    resolved_ticker=resolution.resolved_ticker,
                    value=fetch_result.value,
                    is_stale=False,
                    source="yfinance",
                )
                continue

            if cached_value is not None:
                audit_service.log_event(
                    "stale_fallback",
                    f"Using stale cached {kind} data",
                    {"ticker": resolution.resolved_ticker, "kind": kind},
                )
                results[ticker] = MarketDataEnvelope(
                    ticker=ticker,
                    resolved_ticker=resolution.resolved_ticker,
                    value=cached_value,
                    is_stale=True,
                    source="cache",
                    error=fetch_result.error if fetch_result else None,
                )
                continue

            results[ticker] = MarketDataEnvelope(
                ticker=ticker,
                resolved_ticker=resolution.resolved_ticker,
                value=None,
                is_stale=True,
                source="yfinance",
                error=fetch_result.error if fetch_result else yfinance_client.ProviderError(
                    code="fetch_failed",
                    message="No provider result returned.",
                ),
            )
        return results

    def get_quotes(self, tickers: list[str], exchanges: dict[str, str] | None = None) -> dict[str, MarketDataEnvelope]:
        return self._fetch_with_cache("quote", tickers, exchanges, yfinance_client.get_quotes)

    def get_fundamentals(self, tickers: list[str], exchanges: dict[str, str] | None = None) -> dict[str, MarketDataEnvelope]:
        return self._fetch_with_cache("fundamentals", tickers, exchanges, yfinance_client.get_fundamentals)


DEFAULT_MARKET_DATA_SERVICE = MarketDataService()


def get_quotes(tickers: list[str], exchanges: dict[str, str] | None = None) -> dict[str, MarketDataEnvelope]:
    return DEFAULT_MARKET_DATA_SERVICE.get_quotes(tickers, exchanges)


def get_fundamentals(tickers: list[str], exchanges: dict[str, str] | None = None) -> dict[str, MarketDataEnvelope]:
    return DEFAULT_MARKET_DATA_SERVICE.get_fundamentals(tickers, exchanges)
