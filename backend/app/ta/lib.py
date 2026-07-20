from __future__ import annotations

"""Technical analysis library — Layer 2 (computation).

All functions are pure Python (no TA-Lib, no pandas), synchronous, and
side-effect free.  Input type is always ``list[HistoricalBar]``.

Outputs are ``list[float | None]`` aligned 1-to-1 with the input bar list.
None values pad the head of the series for the warm-up period (e.g. the
first ``window - 1`` values of SMA are None).
"""

import math

from app.market_data.schemas import HistoricalBar


def _closes(bars: list[HistoricalBar]) -> list[float]:
    return [b.close for b in bars]


def _is_valid(v: float) -> bool:
    """True when a close price is a usable finite positive number."""
    return v > 0 and not math.isnan(v) and not math.isinf(v)


def _nan_to_none(values: list[float | None]) -> list[float | None]:
    """Replace any NaN or Inf float in the list with None.

    Called at the output boundary of every TA function so callers always
    receive a clean list[float | None] with no unexpected NaN propagation.
    (yfinance occasionally returns nan for the latest partially-formed bar.)
    """
    return [
        None if (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v
        for v in values
    ]


def compute_sma(bars: list[HistoricalBar], window: int) -> list[float | None]:
    """Simple Moving Average.

    Returns a list of length ``len(bars)``.  The first ``window - 1`` values
    are None (warm-up period).  Any bar with a NaN or invalid close is also
    returned as None.
    """
    closes = _closes(bars)
    result: list[float | None] = []
    for i in range(len(closes)):
        if i < window - 1:
            result.append(None)
        elif not all(_is_valid(closes[j]) for j in range(i - window + 1, i + 1)):
            result.append(None)  # window contains invalid price
        else:
            result.append(sum(closes[i - window + 1 : i + 1]) / window)
    return _nan_to_none(result)


def compute_ema(bars: list[HistoricalBar], window: int) -> list[float | None]:
    """Exponential Moving Average (Wilder / standard EMA).

    Multiplier k = 2 / (window + 1).
    Seeded from the SMA of the first ``window`` valid closes.
    The first ``window - 1`` values are None (warm-up period).
    NaN or invalid closes produce None at that position.
    """
    closes = _closes(bars)
    if len(closes) < window:
        return [None] * len(closes)

    k = 2.0 / (window + 1)
    result: list[float | None] = [None] * (window - 1)

    # Seed: need window valid closes to form the initial SMA
    seed_closes = closes[:window]
    if not all(_is_valid(c) for c in seed_closes):
        # Cannot seed; propagate None through the whole series
        return [None] * len(closes)

    seed_sma = sum(seed_closes) / window
    result.append(seed_sma)

    for c in closes[window:]:
        prev_ema = result[-1]
        if prev_ema is None or not _is_valid(c):
            result.append(None)
        else:
            result.append(c * k + prev_ema * (1.0 - k))

    return _nan_to_none(result)


def compute_rsi(bars: list[HistoricalBar], window: int = 14) -> list[float | None]:
    """Relative Strength Index (Wilder's smoothing method).

    Returns a list of length ``len(bars)``.  The first ``window`` values are
    None (one extra for the initial delta computation).

    RSI is in the range [0, 100].  RSI = 100 when there are no losing periods.
    NaN or invalid closes (e.g. from partially-formed latest bars) are emitted
    as None rather than propagating NaN into downstream computations.
    """
    closes = _closes(bars)
    if len(closes) < window + 1:
        return [None] * len(closes)

    # Compute deltas, treating invalid closes as no-change (0.0) to avoid NaN
    # propagation through Wilder smoothing while keeping the list aligned.
    deltas: list[float] = []
    for i in range(1, len(closes)):
        prev, curr = closes[i - 1], closes[i]
        if _is_valid(prev) and _is_valid(curr):
            deltas.append(curr - prev)
        else:
            deltas.append(0.0)  # treat invalid bar as no-change

    gains = [max(d, 0.0) for d in deltas]
    losses = [abs(min(d, 0.0)) for d in deltas]

    # Seed averages over first window
    avg_gain = sum(gains[:window]) / window
    avg_loss = sum(losses[:window]) / window

    def _rsi_from_avgs(ag: float, al: float) -> float:
        if al == 0.0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    # The first `window` bars produce no RSI value
    result: list[float | None] = [None] * window
    result.append(_rsi_from_avgs(avg_gain, avg_loss))

    # Wilder smoothing for the rest
    for i in range(window, len(deltas)):
        avg_gain = (avg_gain * (window - 1) + gains[i]) / window
        avg_loss = (avg_loss * (window - 1) + losses[i]) / window
        # If the bar itself is invalid (e.g. NaN close), emit None
        if not _is_valid(closes[i + 1]):
            result.append(None)
        else:
            result.append(_rsi_from_avgs(avg_gain, avg_loss))

    return _nan_to_none(result)
