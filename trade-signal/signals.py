"""Combine RSI + MACD + Bollinger Bands + KD + Fibonacci retracement into a
simple long/short/neutral signal.

This is a rule-based heuristic, not a trading recommendation:
- RSI oversold/overbought flags mean-reversion extremes.
- A MACD crossover flags a shift in momentum.
- A close outside the Bollinger Bands flags a stretched, likely-to-revert price.
- KD (stochastic %K) oversold/overbought flags the same kind of extreme as
  RSI, computed differently (from the high/low range rather than closes).
- A close landing near the 61.8% Fibonacci retracement of the latest swing
  flags a level traders commonly watch for a bounce (in an up-leg) or a
  rejection (in a down-leg).
Each contributes +1/-1 to a score; the sign of the total score decides the call.
"""

from indicators import atr, bollinger_bands, ema, fibonacci_retracement, macd, rsi, stochastic_kd


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
    latest_k: float | None = None,
    kd_oversold: float = 20.0,
    kd_overbought: float = 80.0,
    fib_levels: tuple[float, float, bool] | None = None,
    fib_tolerance_pct: float = 0.05,
    trend_ema: float | None = None,
    trend_period: int = 0,
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

    if latest_k is not None:
        if latest_k < kd_oversold:
            score += 1
            reasons.append(f"KD %K {latest_k:.1f} 進入超賣區（<{kd_oversold}）")
        elif latest_k > kd_overbought:
            score -= 1
            reasons.append(f"KD %K {latest_k:.1f} 進入超買區（>{kd_overbought}）")

    if fib_levels is not None:
        swing_high, swing_low, uptrend = fib_levels
        span = swing_high - swing_low
        tolerance = span * fib_tolerance_pct
        if uptrend:
            level = swing_high - 0.618 * span
            if abs(latest_close - level) <= tolerance:
                score += 1
                reasons.append(f"價格貼近上升段 61.8% 費波那契回撤支撐（{level:.4g}）")
        else:
            level = swing_low + 0.618 * span
            if abs(latest_close - level) <= tolerance:
                score -= 1
                reasons.append(f"價格貼近下跌段 61.8% 費波那契回撤壓力（{level:.4g}）")

    if score > 0:
        decision = "long"
    elif score < 0:
        decision = "short"
    else:
        decision = "neutral"
        if not reasons:
            reasons.append("RSI、MACD、布林通道、KD、費波那契回撤皆未觸發訊號")

    # 趨勢過濾：上面五項全是均值回歸指標（超買就看空、超賣就看多），在單邊
    # 趨勢裡會一路逆勢進場、一路被停損。價格在長期 EMA 之上時擋掉做空、在
    # 之下時擋掉做多，只留順勢的那一邊。
    #
    # score 與 reasons 都保留原值不動,只改 decision——這樣前端／回測仍看得到
    # 「本來要發什麼訊號、為什麼被擋」，而不是憑空變成 neutral。
    if trend_ema is not None:
        if decision == "short" and latest_close > trend_ema:
            decision = "neutral"
            reasons.append(
                f"做空訊號被趨勢過濾擋下：收盤 {latest_close:.4g} 在 EMA{trend_period} {trend_ema:.4g} 之上（上升趨勢不逆勢做空）"
            )
        elif decision == "long" and latest_close < trend_ema:
            decision = "neutral"
            reasons.append(
                f"做多訊號被趨勢過濾擋下：收盤 {latest_close:.4g} 在 EMA{trend_period} {trend_ema:.4g} 之下（下降趨勢不逆勢做多）"
            )

    return decision, score, reasons


def _price(v: float | None) -> float | None:
    """價格四捨五入到 6 位有效數字，而不是固定 6 位小數。

    幣價跨了好幾個數量級：BTCUSDT 是 80889.7，CTRUSDT 是 0.010041。原本
    統一用 `round(x, 4)`，前者沒事，後者直接變成 0.01——誤差 0.8%，止損
    與風報比全部算歪。有效位數對兩端都準。
    """
    return None if v is None else float(f"{v:.6g}")


_EMPTY_RESULT = {
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
    "kd_k": None,
    "kd_d": None,
    "fib_swing_high": None,
    "fib_swing_low": None,
    "fib_level": None,
    "fib_uptrend": None,
    "trend_ema": None,
    "entry_low": None,
    "entry_high": None,
    "take_profit": None,
}


def generate_signal_series(
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
    kd_k_period: int = 14,
    kd_smooth_k: int = 3,
    kd_d_period: int = 3,
    kd_oversold: float = 20.0,
    kd_overbought: float = 80.0,
    fib_lookback: int = 55,
    fib_tolerance_pct: float = 0.05,
    trend_period: int = 100,
    atr_entry_band: float = 0.5,
    target_risk_reward: float = 2.0,
) -> list[dict]:
    """The result `generate_signal(closes[: i + 1], highs[: i + 1], lows[: i + 1])`
    would give at every bar `i`, computed for the whole series in one pass
    instead of one call per bar.

    Every indicator here is causal (Wilder's RSI/ATR, EMA-based MACD, a
    rolling Bollinger/stochastic window, a fixed-lookback Fibonacci swing —
    none of them look past the bar they're evaluated at), so computing each
    one once over the full array and reading bar `i` back off it gives the
    exact same value as recomputing it from scratch on `closes[: i + 1]`.
    That means callers who need every bar's signal — the walk-forward
    backtest, the per-bar chart endpoint — can get it in O(n) here instead
    of the O(n²) that calling `generate_signal()` in a loop costs (each
    call there redoes every indicator over an ever-growing prefix).
    `generate_signal()` itself is just `generate_signal_series(...)[-1]`.

    `trend_period` is the long EMA used to filter out counter-trend calls
    (see `_decide`); pass 0 to disable the filter and get the raw
    mean-reversion signal. Bars before the EMA has warmed up are simply
    unfiltered — there's no trend reading to filter against yet.
    """
    n = len(closes)
    rsi_values = rsi(closes, rsi_period)
    macd_line, signal_line, _ = macd(closes, macd_fast, macd_slow, macd_signal)
    bb_middle, bb_upper, bb_lower = bollinger_bands(closes, bb_period, bb_std)
    trend_values = ema(closes, trend_period) if trend_period > 0 else []

    rsi_offset = n - len(rsi_values)
    macd_offset = n - len(macd_line)
    bb_offset = n - len(bb_upper)
    trend_offset = n - len(trend_values)

    have_hl = highs is not None and lows is not None
    kd_k_values, kd_d_values = ([], [])
    atr_values: list[float] = []
    if have_hl:
        kd_k_values, kd_d_values = stochastic_kd(highs, lows, closes, kd_k_period, kd_smooth_k, kd_d_period)
        atr_values = atr(highs, lows, closes, atr_period)
    kd_offset = n - len(kd_k_values)
    atr_offset = n - len(atr_values)

    results: list[dict] = []
    for i in range(n):
        # Mirrors generate_signal()'s own insufficient-data guard, translated
        # from "len(rsi_values from closes[:i+1]) < 1" etc. into full-series
        # offsets: rsi needs >=1 value, macd/signal need >=2 (a "now" and a
        # "prev" for crossover detection), bollinger needs >=1.
        if i < rsi_offset or i < macd_offset + 1 or i < bb_offset:
            results.append(dict(_EMPTY_RESULT))
            continue

        latest_rsi = rsi_values[i - rsi_offset]
        macd_now, macd_prev = macd_line[i - macd_offset], macd_line[i - 1 - macd_offset]
        signal_now, signal_prev = signal_line[i - macd_offset], signal_line[i - 1 - macd_offset]
        latest_close = closes[i]
        upper_band, lower_band = bb_upper[i - bb_offset], bb_lower[i - bb_offset]

        # 沒暖機完（i < trend_offset）就是 None，代表這根不過濾——此時還沒有
        # 趨勢讀數可比。trend_period=0 時 trend_values 為空、offset 為 n，
        # 這個條件永遠不成立，等於整個過濾關閉。
        trend_now = trend_values[i - trend_offset] if i >= trend_offset else None

        latest_k = None
        latest_d = None
        fib_levels = None
        if have_hl:
            if i >= kd_offset:
                latest_k = kd_k_values[i - kd_offset]
                latest_d = kd_d_values[i - kd_offset]
            if i + 1 >= fib_lookback:
                fib_levels = fibonacci_retracement(
                    highs[i + 1 - fib_lookback: i + 1], lows[i + 1 - fib_lookback: i + 1], fib_lookback
                )

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
            latest_k,
            kd_oversold,
            kd_overbought,
            fib_levels,
            fib_tolerance_pct,
            trend_now,
            trend_period,
        )

        atr_value = None
        stop_loss = None
        entry_low = entry_high = take_profit = None
        if have_hl and i >= atr_offset:
            atr_value = atr_values[i - atr_offset]
            if decision in ("long", "short"):
                # 進場區間：以訊號當根收盤為中心、上下各半個 ATR。表達的是
                # 「這支標的目前的波動下，跟訊號價差不多的範圍」，不是預測
                # 會回到哪裡——回測是以收盤價進場的，所以這個區間刻意涵蓋
                # 收盤價本身，數字才對得上。
                entry_low = latest_close - atr_entry_band * atr_value
                entry_high = latest_close + atr_entry_band * atr_value
                risk = atr_stop_multiplier * atr_value
                if decision == "long":
                    stop_loss = latest_close - risk
                    take_profit = latest_close + risk * target_risk_reward
                else:
                    stop_loss = latest_close + risk
                    take_profit = latest_close - risk * target_risk_reward

        fib_swing_high, fib_swing_low, fib_level, fib_uptrend = None, None, None, None
        if fib_levels is not None:
            swing_high, swing_low, uptrend = fib_levels
            span = swing_high - swing_low
            fib_swing_high = swing_high
            fib_swing_low = swing_low
            fib_uptrend = uptrend
            fib_level = swing_high - 0.618 * span if uptrend else swing_low + 0.618 * span

        results.append(
            {
                "signal": decision,
                "score": score,
                "reason": "；".join(reasons),
                "rsi": round(latest_rsi, 2),
                "macd": round(macd_now, 6),
                "macd_signal": round(signal_now, 6),
                "bb_upper": _price(upper_band),
                "bb_lower": _price(lower_band),
                "atr": _price(atr_value),
                "stop_loss": _price(stop_loss),
                "kd_k": round(latest_k, 2) if latest_k is not None else None,
                "kd_d": round(latest_d, 2) if latest_d is not None else None,
                "fib_swing_high": _price(fib_swing_high),
                "fib_swing_low": _price(fib_swing_low),
                "fib_level": _price(fib_level),
                "fib_uptrend": fib_uptrend,
                "trend_ema": _price(trend_now),
                "entry_low": _price(entry_low),
                "entry_high": _price(entry_high),
                "take_profit": _price(take_profit),
            }
        )

    return results


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
    kd_k_period: int = 14,
    kd_smooth_k: int = 3,
    kd_d_period: int = 3,
    kd_oversold: float = 20.0,
    kd_overbought: float = 80.0,
    fib_lookback: int = 55,
    fib_tolerance_pct: float = 0.05,
    trend_period: int = 100,
    atr_entry_band: float = 0.5,
    target_risk_reward: float = 2.0,
) -> dict:
    """`highs`/`lows` are optional (same length as `closes`) — pass them to
    also get an ATR-based stop-loss price, the KD (stochastic) oscillator,
    and a Fibonacci retracement read back. Without them, those all come
    back as None and don't participate in the score.

    Just the latest bar of `generate_signal_series()` — use that directly
    if you need every bar's signal (a backtest, a chart), since calling
    this in a loop redoes every indicator from scratch each time.
    """
    if not closes:
        return dict(_EMPTY_RESULT)
    return generate_signal_series(
        closes,
        highs,
        lows,
        rsi_period,
        macd_fast,
        macd_slow,
        macd_signal,
        bb_period,
        bb_std,
        rsi_oversold,
        rsi_overbought,
        atr_period,
        atr_stop_multiplier,
        kd_k_period,
        kd_smooth_k,
        kd_d_period,
        kd_oversold,
        kd_overbought,
        fib_lookback,
        fib_tolerance_pct,
        trend_period,
        atr_entry_band,
        target_risk_reward,
    )[-1]
