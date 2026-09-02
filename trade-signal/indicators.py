"""Pure-Python technical indicator calculations (no extra dependencies)."""


def ema(values: list[float], period: int) -> list[float]:
    """Exponential moving average, seeded with a simple average of the first `period` values.

    Returns a series of length `len(values) - period + 1` (empty if not enough data).
    """
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    ema_values = [sum(values[:period]) / period]
    for price in values[period:]:
        ema_values.append(price * k + ema_values[-1] * (1 - k))
    return ema_values


def rsi(closes: list[float], period: int = 14) -> list[float]:
    """Wilder's RSI. Returns a series aligned to closes[period:] (empty if not enough data)."""
    if len(closes) < period + 1:
        return []

    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi(avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    rsi_values = [_rsi(avg_gain, avg_loss)]
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi_values.append(_rsi(avg_gain, avg_loss))

    return rsi_values


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    """MACD line, signal line, and histogram, all aligned to the same index range.

    Returns three empty lists if there isn't enough data.
    """
    if len(closes) < slow + signal:
        return [], [], []

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)

    # ema_fast starts earlier than ema_slow since fast < slow; trim to align both
    # series to the same starting point in `closes`.
    offset = slow - fast
    macd_line = [f - s for f, s in zip(ema_fast[offset:], ema_slow)]

    signal_line = ema(macd_line, signal)
    macd_aligned = macd_line[signal - 1:]
    histogram = [m - s for m, s in zip(macd_aligned, signal_line)]

    return macd_aligned, signal_line, histogram


def bollinger_bands(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[list[float], list[float], list[float]]:
    """Middle/upper/lower Bollinger Bands, aligned to closes[period - 1:].

    Returns three empty lists if there isn't enough data.
    """
    if len(closes) < period:
        return [], [], []

    middle = []
    upper = []
    lower = []
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        middle.append(mean)
        upper.append(mean + num_std * std)
        lower.append(mean - num_std * std)

    return middle, upper, lower
