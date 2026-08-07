from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import json


T = TypeVar("T")


@dataclass(slots=True)
class ProviderError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderResult(Generic[T]):
    ticker: str
    resolved_ticker: str | None
    ok: bool
    value: T | None = None
    error: ProviderError | None = None
    fetched_at: str | None = None
    source: str = "yfinance"


_EXCHANGE_SUFFIXES = {
    "NSE": ".NS",
    "BSE": ".BO",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_known_suffix(ticker: str) -> str:
    for suffix in _EXCHANGE_SUFFIXES.values():
        if ticker.upper().endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


def resolve_ticker(ticker: str, exchange: str | None = None) -> ProviderResult[dict[str, str]]:
    raw_ticker = ticker.strip().upper()
    if not raw_ticker:
        return ProviderResult(
            ticker=ticker,
            resolved_ticker=None,
            ok=False,
            error=ProviderError(code="invalid_ticker", message="Ticker cannot be empty."),
        )

    if any(raw_ticker.endswith(suffix) for suffix in _EXCHANGE_SUFFIXES.values()):
        return ProviderResult(
            ticker=ticker,
            resolved_ticker=raw_ticker,
            ok=True,
            value={"raw_ticker": _strip_known_suffix(raw_ticker), "canonical_ticker": raw_ticker, "exchange": exchange or ""},
            fetched_at=_utc_now(),
        )

    if exchange is None:
        return ProviderResult(
            ticker=ticker,
            resolved_ticker=None,
            ok=False,
            error=ProviderError(
                code="unresolvable_ticker",
                message="Exchange is required to resolve this ticker.",
                details={"ticker": ticker},
            ),
        )

    suffix = _EXCHANGE_SUFFIXES.get(exchange.strip().upper())
    if suffix is None:
        return ProviderResult(
            ticker=ticker,
            resolved_ticker=None,
            ok=False,
            error=ProviderError(
                code="unsupported_exchange",
                message=f"Unsupported exchange '{exchange}'.",
                details={"ticker": ticker, "exchange": exchange},
            ),
        )

    canonical_ticker = f"{raw_ticker}{suffix}"
    return ProviderResult(
        ticker=ticker,
        resolved_ticker=canonical_ticker,
        ok=True,
        value={"raw_ticker": raw_ticker, "canonical_ticker": canonical_ticker, "exchange": exchange.strip().upper()},
        fetched_at=_utc_now(),
    )


def _request_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _batch_request(urls: list[tuple[str, str]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for key, url in urls:
        try:
            results[key] = _request_json(url)
        except Exception as exc:  # noqa: BLE001
            results[key] = ProviderError(
                code="fetch_failed",
                message=str(exc),
                details={"url": url},
            )
    return results


def _canonical_or_error(ticker: str, exchange: str | None = None) -> tuple[str | None, ProviderError | None]:
    resolved = resolve_ticker(ticker, exchange)
    if not resolved.ok or not resolved.resolved_ticker:
        return None, resolved.error
    return resolved.resolved_ticker, None


def _quote_payload(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    quote = payload.get("quoteResponse", {}).get("result", [])
    if not quote:
        raise ValueError("Quote response was empty.")
    data = quote[0]
    return {
        "ticker": symbol,
        "provider_ticker": data.get("symbol", symbol),
        "price": data.get("regularMarketPrice"),
        "currency": data.get("currency"),
        "market_state": data.get("marketState"),
        "exchange": data.get("fullExchangeName") or data.get("exchange"),
        "change": data.get("regularMarketChange"),
        "change_percent": data.get("regularMarketChangePercent"),
        "day_high": data.get("regularMarketDayHigh"),
        "day_low": data.get("regularMarketDayLow"),
        "fifty_two_week_high": data.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": data.get("fiftyTwoWeekLow"),
        "timestamp": data.get("regularMarketTime"),
        "short_name": data.get("shortName"),
        "long_name": data.get("longName"),
    }


def get_quotes(tickers: list[str], exchanges: dict[str, str] | None = None) -> dict[str, ProviderResult[dict[str, Any]]]:
    resolved: dict[str, ProviderResult[dict[str, str]]] = {}
    request_urls: list[tuple[str, str]] = []
    for ticker in tickers:
        exchange = (exchanges or {}).get(ticker)
        resolved_result = resolve_ticker(ticker, exchange)
        resolved[ticker] = resolved_result
        if resolved_result.ok and resolved_result.resolved_ticker:
            request_urls.append(
                (
                    resolved_result.resolved_ticker,
                    "https://query1.finance.yahoo.com/v7/finance/quote?symbols="
                    + quote_plus(resolved_result.resolved_ticker),
                )
            )

    payloads = _batch_request(request_urls)
    results: dict[str, ProviderResult[dict[str, Any]]] = {}
    for ticker in tickers:
        resolved_result = resolved[ticker]
        if not resolved_result.ok or not resolved_result.resolved_ticker:
            results[ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=None,
                ok=False,
                error=resolved_result.error,
            )
            continue

        payload = payloads.get(resolved_result.resolved_ticker)
        if isinstance(payload, ProviderError):
            results[resolved_result.resolved_ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=resolved_result.resolved_ticker,
                ok=False,
                error=payload,
            )
            continue

        try:
            results[resolved_result.resolved_ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=resolved_result.resolved_ticker,
                ok=True,
                value=_quote_payload(resolved_result.resolved_ticker, payload),
                fetched_at=_utc_now(),
            )
        except Exception as exc:  # noqa: BLE001
            results[resolved_result.resolved_ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=resolved_result.resolved_ticker,
                ok=False,
                error=ProviderError(
                    code="parse_failed",
                    message=str(exc),
                    details={"ticker": resolved_result.resolved_ticker},
                ),
            )
    return results


def get_quote(ticker: str, exchange: str | None = None) -> ProviderResult[dict[str, Any]]:
    results = get_quotes([ticker], {ticker: exchange} if exchange is not None else None)
    return results.get(ticker) or results.get(ticker.upper()) or next(iter(results.values()))


def _fundamentals_payload(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("quoteSummary", {}).get("result", [])
    if not summary:
        raise ValueError("Fundamentals response was empty.")
    data = summary[0]
    return {
        "ticker": symbol,
        "price": (data.get("price") or {}),
        "summary_detail": (data.get("summaryDetail") or {}),
        "default_key_statistics": (data.get("defaultKeyStatistics") or {}),
        "financial_data": (data.get("financialData") or {}),
        "asset_profile": (data.get("assetProfile") or {}),
    }


def get_fundamentals(tickers: list[str], exchanges: dict[str, str] | None = None) -> dict[str, ProviderResult[dict[str, Any]]]:
    results: dict[str, ProviderResult[dict[str, Any]]] = {}
    for ticker in tickers:
        exchange = (exchanges or {}).get(ticker)
        resolved_ticker, error = _canonical_or_error(ticker, exchange)
        if error is not None or resolved_ticker is None:
            results[ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=None,
                ok=False,
                error=error,
            )
            continue

        try:
            url = (
                "https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
                + quote_plus(resolved_ticker)
                + "?modules=assetProfile,summaryDetail,defaultKeyStatistics,price,financialData"
            )
            payload = _request_json(url)
            results[resolved_ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=resolved_ticker,
                ok=True,
                value=_fundamentals_payload(resolved_ticker, payload),
                fetched_at=_utc_now(),
            )
        except Exception as exc:  # noqa: BLE001
            results[resolved_ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=resolved_ticker,
                ok=False,
                error=ProviderError(
                    code="fetch_failed",
                    message=str(exc),
                    details={"ticker": resolved_ticker},
                ),
            )
    return results


def get_fundamentals_for_ticker(ticker: str, exchange: str | None = None) -> ProviderResult[dict[str, Any]]:
    results = get_fundamentals([ticker], {ticker: exchange} if exchange is not None else None)
    return results.get(ticker) or results.get(ticker.upper()) or next(iter(results.values()))


def _news_payload(symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
    news_items = payload.get("news") or payload.get("newses") or []
    articles: list[dict[str, Any]] = []
    for item in news_items:
        articles.append(
            {
                "document_id": item.get("uuid") or item.get("content") or item.get("title"),
                "ticker": symbol,
                "title": item.get("title"),
                "body": item.get("summary") or item.get("content") or "",
                "published_at": (
                    datetime.fromtimestamp(item["providerPublishTime"], tz=timezone.utc).isoformat()
                    if item.get("providerPublishTime")
                    else None
                ),
                "source": item.get("publisher") or "yfinance",
                "url": item.get("link"),
            }
        )
    return {"ticker": symbol, "articles": articles}


def get_news(tickers: list[str] | str, exchanges: dict[str, str] | None = None) -> dict[str, ProviderResult[dict[str, Any]]] | ProviderResult[dict[str, Any]]:
    if isinstance(tickers, str):
        batch = get_news([tickers], exchanges)
        return batch.get(tickers) or batch.get(tickers.upper()) or next(iter(batch.values()))

    results: dict[str, ProviderResult[dict[str, Any]]] = {}
    for ticker in tickers:
        exchange = (exchanges or {}).get(ticker)
        resolved_ticker, error = _canonical_or_error(ticker, exchange)
        if error is not None or resolved_ticker is None:
            results[ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=None,
                ok=False,
                error=error,
            )
            continue

        try:
            search_query = quote_plus(_strip_known_suffix(resolved_ticker))
            url = (
                "https://query1.finance.yahoo.com/v1/finance/search?q="
                + search_query
                + "&quotesCount=0&newsCount=20"
            )
            payload = _request_json(url)
            results[resolved_ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=resolved_ticker,
                ok=True,
                value=_news_payload(resolved_ticker, payload),
                fetched_at=_utc_now(),
            )
        except Exception as exc:  # noqa: BLE001
            results[resolved_ticker] = ProviderResult(
                ticker=ticker,
                resolved_ticker=resolved_ticker,
                ok=False,
                error=ProviderError(
                    code="fetch_failed",
                    message=str(exc),
                    details={"ticker": resolved_ticker},
                ),
            )
    return results
