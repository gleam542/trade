"""Combine RSI + MACD + Bollinger Bands into a simple long/short/neutral signal.

This is a rule-based heuristic, not a trading recommendation:
- RSI oversold/overbought flags mean-reversion extremes.
- A MACD crossover flags a shift in momentum.
- A close outside the Bollinger Bands flags a stretched, likely-to-revert price.
Each contributes +1/-1 to a score; the sign of the total score decides the call.
"""

from indicators import atr, bollinger_bands, macd, rsi


def _decide(
    latest_rsi: float,
    macd_now: float,
    macd_prev: float,
    signal_now: float,
    signal_prev: float,
    latest_close: float,
    upper_band: float,
    lower_band: float,
    rsi_oversold: float,
    rsi_overbought: float,
) -> tuple[str, int, list[str]]:
    """Pure scoring rule, isolated so it can be unit-tested without real price data."""
    bullish_cross = macd_prev <= signal_prev and macd_now > signal_now
    bearish_cross = macd_prev >= signal_prev and macd_now < signal_now

    score = 0
    reasons = []

    if latest_rsi < rsi_oversold:
        score += 1
        reasons.append(f"RSI {latest_rsi:.1f} 進入超賣區（<{rsi_oversold}）")
    elif latest_rsi > rsi_overbought:
        score -= 1
        reasons.append(f"RSI {latest_rsi:.1f} 進入超買區（>{rsi_overbought}）")

    if bullish_cross:
        score += 1
        reasons.append("MACD 黃金交叉（MACD 上穿訊號線）")
    elif bearish_cross:
        score -= 1
        reasons.append("MACD 死亡交叉（MACD 下穿訊號線）")

    if latest_close <= lower_band:
        score += 1
        reasons.append("收盤價跌破布林下軌（超賣）")
    elif latest_close >= upper_band:
        score -= 1
        reasons.append("收盤價突破布林上軌（超買）")

    if score > 0:
        decision = "long"
    elif score < 0:
        decision = "short"
    else:
        decision = "neutral"
        if not reasons:
            reasons.append("RSI、MACD、布林通道皆未觸發訊號")

    return decision, score, reasons


def generate_signal(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bb_period: int = 20,
    bb_std: float = 2.0,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
    atr_period: int = 14,
    atr_stop_multiplier: float = 2.0,
) -> dict:
    """`highs`/`lows` are optional (same length as `closes`) — pass them to
    also get an ATR-based stop-loss price back. Without them, `atr` and
    `stop_loss` are just None.
    """
    rsi_values = rsi(closes, rsi_period)
    macd_line, signal_line, _ = macd(closes, macd_fast, macd_slow, macd_signal)
    bb_middle, bb_upper, bb_lower = bollinger_bands(closes, bb_period, bb_std)

    if (
        len(rsi_values) < 1
        or len(macd_line) < 2
        or len(signal_line) < 2
        or len(bb_upper) < 1
    ):
        return {
            "signal": "neutral",
            "score": 0,
            "reason": "資料不足，無法計算指標",
            "rsi": None,
            "macd": None,
            "macd_signal": None,
            "bb_upper": None,
            "bb_lower": None,
            "atr": None,
            "stop_loss": None,
        }

    latest_rsi = rsi_values[-1]
    macd_now, macd_prev = macd_line[-1], macd_line[-2]
    signal_now, signal_prev = signal_line[-1], signal_line[-2]
    latest_close = closes[-1]
    upper_band, lower_band = bb_upper[-1], bb_lower[-1]

    decision, score, reasons = _decide(
        latest_rsi,
        macd_now,
        macd_prev,
        signal_now,
        signal_prev,
        latest_close,
        upper_band,
        lower_band,
        rsi_oversold,
        rsi_overbought,
    )

    atr_value = None
    stop_loss = None
    if highs is not None and lows is not None:
        atr_values = atr(highs, lows, closes, atr_period)
        if atr_values:
            atr_value = atr_values[-1]
            if decision == "long":
                stop_loss = latest_close - atr_stop_multiplier * atr_value
            elif decision == "short":
                stop_loss = latest_close + atr_stop_multiplier * atr_value

    return {
        "signal": decision,
        "score": score,
        "reason": "；".join(reasons),
        "rsi": round(latest_rsi, 2),
        "macd": round(macd_now, 6),
        "macd_signal": round(signal_now, 6),
        "bb_upper": round(upper_band, 4),
        "bb_lower": round(lower_band, 4),
        "atr": round(atr_value, 4) if atr_value is not None else None,
        "stop_loss": round(stop_loss, 4) if stop_loss is not None else None,
    }
