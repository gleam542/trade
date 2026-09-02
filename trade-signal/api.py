"""HTTP API exposing signals/backtest over the stored klines.

Run locally with:
    uvicorn api:app --reload --port 8000

CORS is wide open (allow_origins=["*"]) because this is meant to be called
from a static frontend file opened straight from disk or a different local
port during development — lock it down before exposing this beyond your own
machine.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backtest import backtest as run_backtest
from config import DB_PATH, DEFAULT_SYMBOLS
from db import get_connection, read_ohlc
from signals import generate_signal

app = FastAPI(title="trade-signal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _known_symbols(db_path: str) -> list[str]:
    # Scoped to spot data only, so a DB that also holds `python main.py --all`'s
    # futures universe doesn't flood every endpoint (and the frontend's tab
    # list) with a few hundred extra symbols nothing else here is built for.
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM klines WHERE market = 'spot' ORDER BY symbol"
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows] or list(DEFAULT_SYMBOLS)


def _ohlc_or_404(symbol: str, db_path: str) -> tuple[list[float], list[float], list[float]]:
    conn = get_connection(db_path)
    try:
        highs, lows, closes = read_ohlc(conn, symbol)
    finally:
        conn.close()
    if not closes:
        raise HTTPException(status_code=404, detail=f"no stored klines for {symbol}")
    return highs, lows, closes


@app.get("/api/symbols")
def list_symbols(db: str = Query(default=DB_PATH)):
    return {"symbols": _known_symbols(db)}


@app.get("/api/signal/{symbol}")
def get_signal(symbol: str, db: str = Query(default=DB_PATH)):
    highs, lows, closes = _ohlc_or_404(symbol, db)
    return generate_signal(closes, highs=highs, lows=lows)


@app.get("/api/chart/{symbol}")
def get_chart(symbol: str, limit: int = Query(default=300, ge=2, le=2000), db: str = Query(default=DB_PATH)):
    """Per-bar OHLC + indicators + the signal that would have fired at that
    bar, using only data up to and including it (no lookahead) — same shape
    the walk-forward backtest consumes, useful for charting."""
    conn = get_connection(db)
    try:
        rows = conn.execute(
            """
            SELECT open_time, open, high, low, close FROM (
                SELECT open_time, open, high, low, close FROM klines
                WHERE symbol = ? ORDER BY open_time DESC LIMIT ?
            ) ORDER BY open_time ASC
            """,
            (symbol, limit),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"no stored klines for {symbol}")

    highs = [row[2] for row in rows]
    lows = [row[3] for row in rows]
    closes = [row[4] for row in rows]
    bars = []
    for i, (open_time, o, h, l, c) in enumerate(rows):
        entry = {"t": open_time, "o": o, "h": h, "l": l, "c": c}
        result = generate_signal(closes[: i + 1], highs=highs[: i + 1], lows=lows[: i + 1])
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
            )
        bars.append(entry)
    return {"symbol": symbol, "bars": bars}


@app.get("/api/backtest/{symbol}")
def get_backtest(
    symbol: str,
    db: str = Query(default=DB_PATH),
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
):
    highs, lows, closes = _ohlc_or_404(symbol, db)
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
    )


@app.get("/api/advise")
def advise(
    capital: float = Query(gt=0),
    profit_pct: float = Query(gt=0),
    hours: float = Query(gt=0),
    db: str = Query(default=DB_PATH),
):
    """Cross-symbol screener: among tracked symbols with a non-neutral
    signal, rank candidates that historically clear the requested pace
    (from backtest()'s by_direction breakdown) ahead of ones that don't,
    then by confidence (|score| / 5) within each tier — so the pick
    actually responds to capital/profit_pct/hours instead of only
    annotating a fixed, target-independent ranking. Still not a
    guarantee: it's "which of these signals historically kept up with
    this pace," not a forecast."""
    required_hourly_pct = ((1 + profit_pct / 100) ** (1 / hours) - 1) * 100

    candidates = []
    for symbol in _known_symbols(db):
        conn = get_connection(db)
        try:
            highs, lows, closes = read_ohlc(conn, symbol)
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
                "direction": latest["signal"],
                "score": latest["score"],
                "confidence": abs(latest["score"]) / 5 * 100,
                "reason": latest["reason"],
                "atr": latest["atr"],
                "stopLoss": latest["stop_loss"],
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

    candidates.sort(
        key=lambda c: (meets_pace(c), c["confidence"], c["stats"]["winRate"] or -1),
        reverse=True,
    )

    return {
        "requiredHourlyPct": required_hourly_pct,
        "expectedProfitUsdt": capital * profit_pct / 100,
        "pick": candidates[0] if candidates else None,
        "candidates": candidates,
    }
