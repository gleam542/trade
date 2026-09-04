"""HTTP API exposing signals/backtest over the stored klines.

Run locally with:
    uvicorn api:app --reload --port 8000

This also serves `frontend/` at the root, so one port covers both the API
and the page (see the mount at the bottom of this file).

Two guards, both off by default so local use needs no configuration:

- `API_PASSWORD` (optional, with `API_USER` defaulting to "trade") turns on
  HTTP Basic auth for every request. Unset = no auth, as before.
- `CORS_ORIGINS` (optional, comma-separated) replaces the default localhost
  allowlist. The frontend is same-origin now, so CORS only matters when the
  page is opened from `file://` or a separate port.

Set both before putting this behind a public tunnel — see README.
"""

import base64
import os
import secrets
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backtest import backtest as run_backtest
from config import DATABASE_URL, DEFAULT_SYMBOLS
from db import get_connection, read_ohlc
from signals import generate_signal, generate_signal_series

Market = Literal["spot", "futures"]

# "null" 是用 file:// 直接開啟頁面時瀏覽器送出的 Origin。
_DEFAULT_CORS = "http://localhost:8000,http://127.0.0.1:8000,null"
_CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", _DEFAULT_CORS).split(",") if o.strip()]

_AUTH_PASSWORD = os.environ.get("API_PASSWORD")
_AUTH_USER = os.environ.get("API_USER", "trade")

app = FastAPI(title="trade-signal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _credentials_ok(header: str | None) -> bool:
    """驗 `Authorization: Basic base64(user:pass)`。

    比對用 compare_digest 而不是 ==：後者逐字元比對、遇到不同就提早回傳，
    回應時間會洩漏猜對了幾個字元（時序攻擊）。
    """
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
        user, _, password = decoded.partition(":")
    except (ValueError, UnicodeDecodeError):
        return False
    return secrets.compare_digest(user, _AUTH_USER) and secrets.compare_digest(password, _AUTH_PASSWORD)


# 認證寫成 middleware 而不是 app 層級的 dependency：dependency 不會套用到
# 底下用 app.mount() 掛上的 sub-application，靜態前端會整個沒被擋（HTTP 200
# 直接吐出頁面）。middleware 在所有請求之前跑，mount 的路徑也包含在內。
@app.middleware("http")
async def _basic_auth(request: Request, call_next):
    if _AUTH_PASSWORD and not _credentials_ok(request.headers.get("authorization")):
        return JSONResponse(
            {"detail": "需要帳號密碼"},
            status_code=status.HTTP_401_UNAUTHORIZED,
            # 少了這個標頭瀏覽器不會跳出登入框，只會顯示一頁 401。
            headers={"WWW-Authenticate": 'Basic realm="trade-signal"'},
        )
    return await call_next(request)


def _known_symbols(market: Market = "spot") -> list[str]:
    # Scoped to a single market at a time, so a DB that also holds
    # `python main.py --all`'s few-hundred-symbol futures universe doesn't
    # flood an endpoint built around a small spot list unless asked for.
    conn = get_connection(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT symbol FROM klines WHERE market = %s ORDER BY symbol", (market,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    symbols = [r[0] for r in rows]
    if not symbols and market == "spot":
        symbols = list(DEFAULT_SYMBOLS)
    return symbols


def _ohlc_or_404(symbol: str, market: Market = "spot") -> tuple[list[float], list[float], list[float]]:
    conn = get_connection(DATABASE_URL)
    try:
        highs, lows, closes = read_ohlc(conn, symbol, market=market)
    finally:
        conn.close()
    if not closes:
        raise HTTPException(status_code=404, detail=f"no stored {market} klines for {symbol}")
    return highs, lows, closes


@app.get("/api/symbols")
def list_symbols(market: Market = "spot"):
    return {"symbols": _known_symbols(market)}


@app.get("/api/signal/{symbol}")
def get_signal(symbol: str, market: Market = "spot"):
    highs, lows, closes = _ohlc_or_404(symbol, market)
    return generate_signal(closes, highs=highs, lows=lows)


@app.get("/api/chart/{symbol}")
def get_chart(
    symbol: str,
    limit: int = Query(default=300, ge=2, le=2000),
    market: Market = "spot",
):
    """Per-bar OHLC + indicators + the signal that would have fired at that
    bar, using only data up to and including it (no lookahead) — same shape
    the walk-forward backtest consumes, useful for charting."""
    conn = get_connection(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT open_time, open, high, low, close FROM (
                    SELECT open_time, open, high, low, close FROM klines
                    WHERE market = %s AND symbol = %s ORDER BY open_time DESC LIMIT %s
                ) AS recent ORDER BY open_time ASC
                """,
                (market, symbol, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"no stored {market} klines for {symbol}")

    highs = [row[2] for row in rows]
    lows = [row[3] for row in rows]
    closes = [row[4] for row in rows]
    # One O(n) pass instead of recomputing every indicator from scratch at
    # each bar (see generate_signal_series()'s docstring).
    series = generate_signal_series(closes, highs=highs, lows=lows)
    bars = []
    for i, (open_time, o, h, l, c) in enumerate(rows):
        entry = {"t": open_time, "o": o, "h": h, "l": l, "c": c}
        result = series[i]
        if result["rsi"] is not None:
            entry.update(
                rsi=result["rsi"],
                macd=result["macd"],
                macdSignal=result["macd_signal"],
                bbUpper=result["bb_upper"],
                bbLower=result["bb_lower"],
                signal=result["signal"],
                score=result["score"],
                reason=result["reason"],
                atr=result["atr"],
                stopLoss=result["stop_loss"],
                kdK=result["kd_k"],
                kdD=result["kd_d"],
                fibSwingHigh=result["fib_swing_high"],
                fibSwingLow=result["fib_swing_low"],
                fibLevel=result["fib_level"],
                fibUptrend=result["fib_uptrend"],
                trendEma=result["trend_ema"],
                entryLow=result["entry_low"],
                entryHigh=result["entry_high"],
                takeProfit=result["take_profit"],
            )
        bars.append(entry)
    return {"symbol": symbol, "bars": bars}


@app.get("/api/backtest/{symbol}")
def get_backtest(
    symbol: str,
    market: Market = "spot",
    min_bars: int = Query(default=60, ge=1),
    rsi_period: int = 14,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    bb_period: int = 20,
    bb_std: float = 2.0,
    kd_k_period: int = 14,
    kd_smooth_k: int = 3,
    kd_d_period: int = 3,
    kd_oversold: float = 20.0,
    kd_overbought: float = 80.0,
    fib_lookback: int = 55,
    fib_tolerance_pct: float = 0.05,
    trend_period: int = 100,
):
    highs, lows, closes = _ohlc_or_404(symbol, market)
    return run_backtest(
        closes,
        highs=highs,
        lows=lows,
        min_bars=min_bars,
        rsi_period=rsi_period,
        rsi_oversold=rsi_oversold,
        rsi_overbought=rsi_overbought,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        bb_period=bb_period,
        bb_std=bb_std,
        kd_k_period=kd_k_period,
        kd_smooth_k=kd_smooth_k,
        kd_d_period=kd_d_period,
        kd_oversold=kd_oversold,
        kd_overbought=kd_overbought,
        fib_lookback=fib_lookback,
        fib_tolerance_pct=fib_tolerance_pct,
        trend_period=trend_period,
    )


@app.get("/api/advise")
def advise(
    capital: float = Query(gt=0),
    profit_pct: float = Query(gt=0),
    hours: float = Query(gt=0),
    min_trades: int = Query(default=30, ge=0),
):
    """Cross-symbol screener: among tracked symbols with a non-neutral
    signal — spot AND futures both, so a symbol tracked in both markets
    (e.g. spot BTCUSDT and futures BTCUSDT) shows up as two independent
    candidates — rank by confidence (|score| / 5) first, then by whether
    the direction historically cleared the requested pace, then win rate.

    Two guards against picking noise, both learned the hard way (see the
    README section on this endpoint):

    - `min_trades` drops candidates whose direction has too few historical
      trades to mean anything. Screening ~500 symbols and taking the best
      number is a multiple-comparisons trap: at 25 trades, a 60% win rate
      happens by pure chance 21% of the time, so across dozens of
      candidates you are *guaranteed* a great-looking one even if every
      signal is noise. Pass 0 to disable.
    - Confidence leads the sort. It used to be pace-first, which let a
      1-of-5-indicator signal outrank a 4-of-5 one purely because its
      small historical sample happened to look good.

    Still not a guarantee, and not advice: it's "which of these signals
    has the most indicators agreeing, among those with enough history to
    say anything at all," not a forecast."""
    required_hourly_pct = ((1 + profit_pct / 100) ** (1 / hours) - 1) * 100

    candidates = []
    for market in ("spot", "futures"):
        for symbol in _known_symbols(market):
            conn = get_connection(DATABASE_URL)
            try:
                highs, lows, closes = read_ohlc(conn, symbol, market=market)
            finally:
                conn.close()
            if not closes:
                continue

            latest = generate_signal(closes, highs=highs, lows=lows)
            if latest["signal"] not in ("long", "short"):
                continue

            bt = run_backtest(closes, highs=highs, lows=lows)
            direction_stats = bt["by_direction"][latest["signal"]]

            candidates.append(
                {
                    "symbol": symbol,
                    "market": market,
                    "direction": latest["signal"],
                    "score": latest["score"],
                    "confidence": abs(latest["score"]) / 5 * 100,
                    "reason": latest["reason"],
                    "atr": latest["atr"],
                    "stopLoss": latest["stop_loss"],
                    "entryLow": latest["entry_low"],
                    "entryHigh": latest["entry_high"],
                    "takeProfit": latest["take_profit"],
                    "stats": {
                        "trades": direction_stats["trades"],
                        "winRate": direction_stats["win_rate"],
                        "avgReturnPct": (
                            direction_stats["avg_return"] * 100
                            if direction_stats["avg_return"] is not None
                            else None
                        ),
                    },
                }
            )

    def meets_pace(c: dict) -> bool:
        avg = c["stats"]["avgReturnPct"]
        return avg is not None and avg >= required_hourly_pct

    # 樣本太少的直接不列入排名。留著它們只會讓「掃越多、越保證挑到運氣好的
    # 那個」這件事更嚴重——被排除的數量單獨回報，讓使用者知道篩掉了多少，
    # 而不是安靜地消失。
    ranked = [c for c in candidates if c["stats"]["trades"] >= min_trades]
    excluded = len(candidates) - len(ranked)

    def positive_history(c: dict) -> bool:
        avg = c["stats"]["avgReturnPct"]
        return avg is not None and avg > 0

    # 排序四層，由粗到細：
    #
    # 1. 歷史平均報酬為正——最低門檻。純看信心會讓「指標很一致但歷史上一直
    #    做錯」的標的登頂（實測出現過信心 60%、勝率 40.6%、平均 -0.444%/h
    #    的第一名）。這種沉到最後但不刪除，矛盾的案例本身有參考價值。
    # 2. 信心——指標同向的比例，是「現在這根 K 線」的直接證據；歷史平均是
    #    小樣本估計、雜訊大得多，所以證據強度優先於歷史數字。
    # 3. 是否跟得上目標節奏。
    # 4. 勝率。
    ranked.sort(
        key=lambda c: (
            positive_history(c),
            c["confidence"],
            meets_pace(c),
            c["stats"]["winRate"] or -1,
        ),
        reverse=True,
    )

    return {
        "requiredHourlyPct": required_hourly_pct,
        "expectedProfitUsdt": capital * profit_pct / 100,
        "minTrades": min_trades,
        "excludedLowSample": excluded,
        "pick": ranked[0] if ranked else None,
        "candidates": ranked,
    }


# 把 frontend/ 掛在根路徑，讓同一個 port 同時吃 API 與頁面。透過隧道
# （cloudflared 等）對外時只需要一個網址，前端也變成同源、不必依賴上面
# 那個全開的 CORS。
#
# 必須放在檔案最後：mount("/") 會接走所有還沒被比對到的路徑，寫在前面
# 會把後面註冊的 /api/* 全部蓋掉。
_FRONTEND_DIR = Path(__file__).parent / "frontend"
if _FRONTEND_DIR.is_dir():
    # frontend/ 裡沒有 index.html（頁面叫 console.html，README 各處也都這樣
    # 寫），所以根路徑自己轉過去，省得複製一份或改檔名。這條要註冊在下面的
    # mount 之前才會生效。
    @app.get("/", include_in_schema=False)
    def _frontend_index():
        return RedirectResponse("/console.html")

    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
