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


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float]:
    """Wilder's Average True Range. Returns a series aligned to closes[period:]
    (same alignment as `rsi`), empty if not enough data.
    """
    if len(closes) < period + 1:
        return []

    true_ranges = []
    for i in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    avg = sum(true_ranges[:period]) / period
    atr_values = [avg]
    for i in range(period, len(true_ranges)):
        avg = (avg * (period - 1) + true_ranges[i]) / period
        atr_values.append(avg)

    return atr_values


def stochastic_kd(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    k_period: int = 14,
    smooth_k: int = 3,
    d_period: int = 3,
) -> tuple[list[float], list[float]]:
    """Stochastic oscillator (%K, %D), both 0-100, aligned to the same index range.

    Raw %K = (close - lowest low over k_period) / (highest high - lowest low) * 100.
    The returned %K is a `smooth_k`-period SMA of raw %K (the commonly quoted
    "slow %K"); %D is a `d_period`-period SMA of that %K. Returns two empty
    lists if there isn't enough data. A zero-range window (highest == lowest)
    reports 50.0 (neither overbought nor oversold) instead of dividing by zero.
    """
    if len(closes) < k_period + smooth_k + d_period - 2:
        return [], []

    raw_k = []
    for i in range(k_period - 1, len(closes)):
        window_high = max(highs[i - k_period + 1: i + 1])
        window_low = min(lows[i - k_period + 1: i + 1])
        span = window_high - window_low
        raw_k.append(50.0 if span == 0 else (closes[i] - window_low) / span * 100)

    def _sma(values: list[float], period: int) -> list[float]:
        return [sum(values[i - period + 1: i + 1]) / period for i in range(period - 1, len(values))]

    k_values = _sma(raw_k, smooth_k)
    d_values = _sma(k_values, d_period)
    k_aligned = k_values[d_period - 1:]

    return k_aligned, d_values


def fibonacci_retracement(
    highs: list[float],
    lows: list[float],
    lookback: int = 55,
) -> tuple[float, float, bool] | None:
    """Find the swing high/low over the last `lookback` bars and report
    which came first — the basis for a Fibonacci retracement read.

    Returns (swing_high, swing_low, uptrend): `uptrend` is True when the
    swing low occurred before the swing high (the most recent leg ran up,
    so a pullback toward the low retraces *into* an uptrend), False when
    the high came first (the leg ran down). Returns None if there isn't
    enough data, or the window is flat (swing_high <= swing_low).
    """
    if len(highs) < lookback or len(lows) < lookback:
        return None

    window_highs = highs[-lookback:]
    window_lows = lows[-lookback:]

    idx_high = max(range(lookback), key=lambda i: window_highs[i])
    idx_low = min(range(lookback), key=lambda i: window_lows[i])

    swing_high = window_highs[idx_high]
    swing_low = window_lows[idx_low]
    if swing_high <= swing_low:
        return None

    return swing_high, swing_low, idx_low < idx_high


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
