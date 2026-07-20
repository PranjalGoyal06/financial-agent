from __future__ import annotations

"""Quantitative metrics library — Layer 2 (computation).

All functions are:
  - Pure Python (no external TA libraries, no pandas)
  - Synchronous
  - Side-effect free — no I/O, no LLM
  - Deterministic given the same input

Input type is always ``list[HistoricalBar]`` from ``market_data.schemas``.
Outputs are plain Python scalars or dicts — never Pydantic models — so they
can be directly serialised into EvidenceItem.summary strings.

The LLM narrates metrics; it never computes them.  Every metric that appears
in a research prompt must flow through this module.
"""

import math
from datetime import date
from typing import Literal

from app.market_data.schemas import HistoricalBar

# ── Helpers ────────────────────────────────────────────────────────────────────


def _closes(bars: list[HistoricalBar]) -> list[float]:
    """Raw close sequence — may include zeros from split artefacts."""
    return [b.close for b in bars]


def _valid_closes(bars: list[HistoricalBar]) -> list[float]:
    """Close prices with zero / NaN entries removed.

    Used by all aggregate quant functions.  TA functions keep using ``_closes``
    because their outputs must stay 1-to-1 aligned with the input bar list.
    """
    return [
        b.close
        for b in bars
        if b.close and b.close > 0 and not math.isnan(b.close)
    ]


def _log_returns(closes: list[float]) -> list[float]:
    """Daily log returns, skipping any pair where either price is non-positive."""
    result = []
    for i in range(1, len(closes)):
        prev, curr = closes[i - 1], closes[i]
        if prev > 0 and curr > 0:
            result.append(math.log(curr / prev))
    return result


def _pearson(x: list[float], y: list[float]) -> float | None:
    """Pearson correlation coefficient.  Returns None if denominator is zero."""
    n = len(x)
    if n < 2:
        return None
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denom_sq = sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)
    if denom_sq == 0:
        return None
    return num / math.sqrt(denom_sq)


# ── Public API ─────────────────────────────────────────────────────────────────


def compute_returns(
    bars: list[HistoricalBar],
    method: Literal["simple", "log", "cagr"] = "simple",
) -> float | list[float]:
    """Compute period return(s) for a price series.

    simple — single total return (close[-1] / close[0] - 1)
    log    — list of daily log returns ln(p_t / p_{t-1}), length = len(bars)-1
    cagr   — single annualised compound return (252 trading days/year)
    """
    closes = _valid_closes(bars)
    if len(closes) < 2:
        return 0.0

    if method == "simple":
        return (closes[-1] - closes[0]) / closes[0]

    if method == "log":
        return _log_returns(closes)

    if method == "cagr":
        n_days = len(closes) - 1
        if n_days <= 0 or closes[0] <= 0:
            return 0.0
        years = n_days / 252.0
        return (closes[-1] / closes[0]) ** (1.0 / years) - 1.0

    raise ValueError(f"Unknown method: {method!r}. Expected 'simple', 'log', or 'cagr'.")


def compute_volatility(
    bars: list[HistoricalBar],
    window: int | None = None,
) -> float:
    """Annualised historical volatility (std dev of daily log returns × √252).

    window — if set, use only the last N bars.  None = all bars.
    Returns 0.0 when fewer than 2 data points are available.
    """
    closes = _valid_closes(bars)
    if window is not None:
        closes = closes[-window:]
    if len(closes) < 2:
        return 0.0

    rets = _log_returns(closes)
    n = len(rets)
    mean = sum(rets) / n
    variance = sum((r - mean) ** 2 for r in rets) / (n - 1)
    return math.sqrt(variance) * math.sqrt(252)


def compute_max_drawdown(
    bars: list[HistoricalBar],
) -> tuple[float, date, date]:
    """Maximum peak-to-trough drawdown.

    Uses each bar's high as the potential peak and each bar's low as the
    potential trough, giving a conservative (worst-case) measure.

    Returns:
        drawdown_pct  — negative float, e.g. -0.35 = 35 % drawdown
        peak_date     — date of the rolling high before the worst trough
        trough_date   — date of the worst trough
    """
    if not bars:
        return (0.0, date.today(), date.today())

    # Filter out bars with zero or NaN prices (yfinance split artefacts)
    valid = [b for b in bars if b.high > 0 and b.low > 0 and not math.isnan(b.high) and not math.isnan(b.low)]
    if not valid:
        return (0.0, date.today(), date.today())

    peak_price = valid[0].high
    peak_date = valid[0].date
    max_dd = 0.0
    dd_peak_date = valid[0].date
    dd_trough_date = valid[0].date

    for bar in valid:
        if bar.high > peak_price:
            peak_price = bar.high
            peak_date = bar.date

        if peak_price > 0:
            dd = (bar.low - peak_price) / peak_price
            if dd < max_dd:
                max_dd = dd
                dd_peak_date = peak_date
                dd_trough_date = bar.date

    return (max_dd, dd_peak_date, dd_trough_date)


def compute_52w_distance(bars: list[HistoricalBar]) -> dict:
    """Current price distance from the 52-week high and low.

    Uses the last 252 bars (or all bars if fewer than 252 are available).

    Returns dict with keys:
        pct_from_high — negative float, e.g. -0.12 = 12 % below the high
        pct_from_low  — positive float, e.g. +0.35 = 35 % above the low
        high_52w      — float
        low_52w       — float

    All values are None when bars is empty.
    """
    # Filter to valid prices only
    valid = [
        b for b in bars[-252:]
        if b.close > 0 and b.high > 0 and b.low > 0
        and not math.isnan(b.close) and not math.isnan(b.high) and not math.isnan(b.low)
    ]
    if not valid:
        return {
            "pct_from_high": None,
            "pct_from_low": None,
            "high_52w": None,
            "low_52w": None,
        }

    high_52w = max(b.high for b in valid)
    low_52w = min(b.low for b in valid)
    current = valid[-1].close

    pct_from_high = (current - high_52w) / high_52w if high_52w else None
    pct_from_low = (current - low_52w) / low_52w if low_52w else None

    return {
        "pct_from_high": pct_from_high,
        "pct_from_low": pct_from_low,
        "high_52w": high_52w,
        "low_52w": low_52w,
    }


def compute_sharpe_ratio(
    bars: list[HistoricalBar],
    risk_free_rate: float = 0.065,
) -> float:
    """Annualised Sharpe ratio.

    risk_free_rate — annual decimal rate.  Default 6.5 % (approx. India 10Y
                     G-Sec yield as of mid-2025).  Override per-run if needed.

    Returns 0.0 if volatility is zero or fewer than 2 bars are available.
    """
    vol = compute_volatility(bars)
    if vol == 0.0 or len(bars) < 2:
        return 0.0

    closes = _valid_closes(bars)
    if len(closes) < 2:
        return 0.0
    rets = _log_returns(closes)
    if not rets:
        return 0.0
    mean_daily = sum(rets) / len(rets)
    annualised_return = mean_daily * 252
    return (annualised_return - risk_free_rate) / vol


def compute_correlation_matrix(
    bars_dict: dict[str, list[HistoricalBar]],
) -> dict[str, dict[str, float | None]]:
    """Pairwise Pearson correlation of daily log returns.

    Args:
        bars_dict — {ticker: bars}

    Returns:
        {ticker_a: {ticker_b: corr}} for all pairs including self (1.0).
        Correlation is None when fewer than 10 overlapping trading dates exist.
    """
    tickers = list(bars_dict.keys())

    # Build {ticker: {date: log_return}} maps
    ret_map: dict[str, dict[date, float]] = {}
    for ticker, bars in bars_dict.items():
        closes = _valid_closes(bars)
        if len(closes) < 2:
            ret_map[ticker] = {}
            continue
        # Re-pair with bar dates, filtering to valid-close positions
        valid_bars = [b for b in bars if b.close and b.close > 0 and not math.isnan(b.close)]
        ret_map[ticker] = {
            valid_bars[i].date: math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes))
        }

    matrix: dict[str, dict[str, float | None]] = {t: {} for t in tickers}
    for i, ta in enumerate(tickers):
        matrix[ta][ta] = 1.0
        for tb in tickers[i + 1:]:
            common = sorted(set(ret_map[ta]) & set(ret_map[tb]))
            if len(common) < 10:
                corr: float | None = None
            else:
                ra = [ret_map[ta][d] for d in common]
                rb = [ret_map[tb][d] for d in common]
                corr = _pearson(ra, rb)
            matrix[ta][tb] = corr
            matrix[tb][ta] = corr

    return matrix


def compute_all_metrics(bars: list[HistoricalBar]) -> dict:
    """Convenience wrapper: all P0 metrics from one bar series.

    Called by the deep research collection node to build the
    ``computed_metric`` EvidenceItems for each ticker in a single call.
    Returns a flat dict of serialisable scalars (no date objects — converted
    to strings) so the result can be embedded directly into EvidenceItem.summary.

    All values are None when bars is empty.
    """
    if not bars:
        return {
            "total_return": None,
            "cagr": None,
            "volatility_annualized": None,
            "max_drawdown": None,
            "max_drawdown_peak_date": None,
            "max_drawdown_trough_date": None,
            "sharpe_ratio": None,
            "pct_from_high": None,
            "pct_from_low": None,
            "high_52w": None,
            "low_52w": None,
            "bars_count": 0,
        }

    dd, dd_peak, dd_trough = compute_max_drawdown(bars)
    dist = compute_52w_distance(bars)

    return {
        "total_return": compute_returns(bars, method="simple"),
        "cagr": compute_returns(bars, method="cagr"),
        "volatility_annualized": compute_volatility(bars),
        "max_drawdown": dd,
        "max_drawdown_peak_date": str(dd_peak),
        "max_drawdown_trough_date": str(dd_trough),
        "sharpe_ratio": compute_sharpe_ratio(bars),
        "pct_from_high": dist["pct_from_high"],
        "pct_from_low": dist["pct_from_low"],
        "high_52w": dist["high_52w"],
        "low_52w": dist["low_52w"],
        "bars_count": len(bars),
    }
