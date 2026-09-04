"""趨勢過濾的最小檢查：`python test_signals.py`，不需要任何測試框架或資料庫。

只測 `_decide()` 的過濾分支——它是純函式，不碰價格資料。過濾邏輯壞掉
（方向反了、忘記關閉開關、暖機期誤判）這裡就會 fail。
"""

from signals import _decide, generate_signal, generate_signal_series

# 五項指標的中性值：RSI 50、MACD 無交叉、收盤在布林通道內、KD 50、無費波。
# 各測試只覆寫自己要觸發的那一項，其餘保持不觸發，避免分數被別的因子干擾。
NEUTRAL = dict(
    latest_rsi=50.0,
    macd_now=0.0, macd_prev=0.0, signal_now=0.0, signal_prev=0.0,
    latest_close=100.0, upper_band=110.0, lower_band=90.0,
    rsi_oversold=30.0, rsi_overbought=70.0,
    latest_k=50.0,
)

OVERBOUGHT = {**NEUTRAL, "latest_rsi": 80.0}   # -> score -1 -> short
OVERSOLD = {**NEUTRAL, "latest_rsi": 20.0}     # -> score +1 -> long


def test_no_filter_keeps_raw_signal():
    assert _decide(**OVERBOUGHT)[0] == "short"
    assert _decide(**OVERSOLD)[0] == "long"


def test_filter_disabled_by_zero_period():
    # trend_ema=None 代表沒有趨勢讀數（trend_period=0，或 EMA 還沒暖機完）
    assert _decide(**OVERBOUGHT, trend_ema=None, trend_period=0)[0] == "short"
    assert _decide(**OVERSOLD, trend_ema=None, trend_period=0)[0] == "long"


def test_uptrend_blocks_short():
    # 收盤 100 在 EMA 90 之上 = 上升趨勢，不逆勢做空
    decision, score, reasons = _decide(**OVERBOUGHT, trend_ema=90.0, trend_period=100)
    assert decision == "neutral", decision
    assert score == -1, f"score 應保留原值以便顯示「本來要發什麼」，得到 {score}"
    assert any("趨勢過濾" in r for r in reasons), reasons


def test_downtrend_blocks_long():
    decision, score, reasons = _decide(**OVERSOLD, trend_ema=110.0, trend_period=100)
    assert decision == "neutral", decision
    assert score == 1, score
    assert any("趨勢過濾" in r for r in reasons), reasons


def test_with_trend_signals_pass_through():
    # 順勢的那一邊不該被動到
    assert _decide(**OVERBOUGHT, trend_ema=110.0, trend_period=100)[0] == "short"
    assert _decide(**OVERSOLD, trend_ema=90.0, trend_period=100)[0] == "long"


# --- 端到端：合成價格走一遍完整的 generate_signal 路徑 ---
# 光測 _decide() 抓不到參數沒接通這類錯（trend_period 忘了加進
# generate_signal() 的簽名，_decide 的測試照樣全綠，但 API 一呼叫就 NameError）。

def _synthetic_uptrend(n=200):
    """穩定上升但有鋸齒的價格——會反覆觸發超買，正好給趨勢過濾擋。"""
    closes = [100 + i * 0.5 + (3 if i % 7 == 0 else 0) for i in range(n)]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]
    return closes, highs, lows


def test_generate_signal_end_to_end():
    closes, highs, lows = _synthetic_uptrend()
    result = generate_signal(closes, highs=highs, lows=lows)
    assert result["trend_ema"] is not None, "EMA 應已暖機完並回報"
    assert result["signal"] in ("long", "short", "neutral")


def test_series_uptrend_emits_no_short_after_warmup():
    closes, highs, lows = _synthetic_uptrend()
    series = generate_signal_series(closes, highs=highs, lows=lows, trend_period=100)
    warm = [b for b in series if b["trend_ema"] is not None]
    assert warm, "暖機後應該要有資料"
    assert not [b for b in warm if b["signal"] == "short"], "持續上升趨勢中不該發做空訊號"


def test_series_disabled_filter_does_emit_shorts():
    # 對照組：關掉過濾，同一份上升資料就會出現逆勢做空——證明上面那條
    # 是過濾擋掉的，不是這份合成資料本來就不會觸發做空。
    closes, highs, lows = _synthetic_uptrend()
    series = generate_signal_series(closes, highs=highs, lows=lows, trend_period=0)
    assert [b for b in series if b["signal"] == "short"], "關閉過濾後應該看得到做空訊號"


# --- 進場區間 / 目標價 / 價格精度 ---

def _uptrend_with_signal(n=200):
    """上升趨勢 + 尾端急拉，讓最後一根觸發訊號（才會有進出場價位）。"""
    closes = [100 + i * 0.5 for i in range(n - 5)] + [140, 150, 165, 180, 200]
    highs = [c * 1.02 for c in closes]
    lows = [c * 0.98 for c in closes]
    return closes, highs, lows


def test_entry_zone_brackets_the_close():
    closes, highs, lows = _uptrend_with_signal()
    r = generate_signal(closes, highs=highs, lows=lows)
    if r["signal"] == "neutral":
        return  # 這份合成資料沒觸發訊號，本測試不適用
    c = closes[-1]
    assert r["entry_low"] < c < r["entry_high"], (r["entry_low"], c, r["entry_high"])


def test_risk_reward_matches_setting():
    closes, highs, lows = _uptrend_with_signal()
    r = generate_signal(closes, highs=highs, lows=lows, target_risk_reward=3.0)
    if r["signal"] == "neutral":
        return
    c = closes[-1]
    risk = abs(c - r["stop_loss"])
    reward = abs(r["take_profit"] - c)
    assert abs(reward / risk - 3.0) < 0.01, f"風報比應為 1:3，得到 1:{reward/risk:.2f}"


def test_neutral_has_no_entry_or_target():
    # 觀望時不該給進出場價位——沒有方向就沒有「進場」可言
    flat = [100.0] * 200
    r = generate_signal(flat, highs=[100.0] * 200, lows=[100.0] * 200)
    assert r["signal"] == "neutral"
    assert r["entry_low"] is None and r["take_profit"] is None


def test_small_price_keeps_precision():
    """幣價 0.01 級時，固定 4 位小數會把 0.010041 壓成 0.01（誤差 0.8%），
    止損與風報比就全歪了。這裡確認改用有效位數之後小數點後還留得住東西。"""
    scale = 0.0001
    closes = [(100 + i * 0.5) * scale for i in range(195)] + [
        x * scale for x in (140, 150, 165, 180, 200)
    ]
    highs = [c * 1.02 for c in closes]
    lows = [c * 0.98 for c in closes]
    r = generate_signal(closes, highs=highs, lows=lows)
    if r["signal"] == "neutral":
        return
    c = closes[-1]
    risk = abs(c - r["stop_loss"])
    reward = abs(r["take_profit"] - c)
    assert risk > 0, "止損被四捨五入成與收盤價相同，精度已流失"
    assert abs(reward / risk - 2.0) < 0.01, f"小價格下風報比失真：1:{reward/risk:.2f}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✓ {name}")
    print("\n全部通過")
