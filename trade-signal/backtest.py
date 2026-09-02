"""Walk-forward backtest for the RSI+MACD+Bollinger signal.

At each bar, the signal is generated using only closes up to and including
that bar (no lookahead), then scored against the next bar's return: a "long"
signal earns that return, "short" earns its inverse, "neutral" earns nothing
(flat/cash). This measures whether the rule has one-bar-ahead predictive edge —
it is not a realistic PnL simulation (no fees, slippage, or position sizing
beyond "one full unit per signal bar").
"""

import argparse

from config import DB_PATH, DEFAULT_SYMBOLS
from db import get_connection, read_ohlc
from signals import generate_signal_series

DEFAULT_MIN_BARS = 60


def _empty_result() -> dict:
    empty_direction = {"trades": 0, "win_rate": None, "avg_return": None}
    return {
        "bars_tested": 0,
        "trades": 0,
        "win_rate": None,
        "total_return": 0.0,
        "final_equity": 1.0,
        "buy_hold_return": 0.0,
        "by_direction": {"long": dict(empty_direction), "short": dict(empty_direction)},
    }


def backtest(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    min_bars: int = DEFAULT_MIN_BARS,
    **signal_kwargs,
) -> dict:
    """`highs`/`lows` are optional (same length as `closes`) — pass them so
    the KD and Fibonacci-retracement factors (and the ATR stop-loss) also
    participate in each bar's signal, same as `generate_signal()` itself.
    Without them those factors just sit out, as before.
    """
    if len(closes) < min_bars + 2:
        return _empty_result()

    equity = 1.0
    total_return = 0.0
    wins = 0
    trades = 0
    bars_tested = 0
    direction_stats = {
        "long": {"trades": 0, "wins": 0, "sum_return": 0.0},
        "short": {"trades": 0, "wins": 0, "sum_return": 0.0},
    }

    # One O(n) pass over the whole series instead of recomputing every
    # indicator from scratch at each bar (generate_signal() in a loop here
    # would be O(n²) — noticeable once a symbol universe runs into the
    # hundreds, as `python main.py --all` does).
    series = generate_signal_series(closes, highs, lows, **signal_kwargs)

    for i in range(min_bars, len(closes) - 1):
        result = series[i]
        next_return = (closes[i + 1] - closes[i]) / closes[i]

        if result["signal"] == "long":
            bar_return = next_return
        elif result["signal"] == "short":
            bar_return = -next_return
        else:
            bar_return = 0.0

        if result["signal"] in direction_stats:
            bucket = direction_stats[result["signal"]]
            bucket["trades"] += 1
            bucket["sum_return"] += bar_return
            if bar_return > 0:
                bucket["wins"] += 1
            trades += 1
            if bar_return > 0:
                wins += 1

        total_return += bar_return
        equity *= 1 + bar_return
        bars_tested += 1

    buy_hold_return = (closes[-1] - closes[min_bars]) / closes[min_bars]

    by_direction = {}
    for direction, bucket in direction_stats.items():
        by_direction[direction] = {
            "trades": bucket["trades"],
            "win_rate": (bucket["wins"] / bucket["trades"]) if bucket["trades"] else None,
            "avg_return": (bucket["sum_return"] / bucket["trades"]) if bucket["trades"] else None,
        }

    return {
        "bars_tested": bars_tested,
        "trades": trades,
        "win_rate": (wins / trades) if trades else None,
        "total_return": total_return,
        "final_equity": equity,
        "buy_hold_return": buy_hold_return,
        "by_direction": by_direction,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="對資料庫中的歷史 K 線回測 RSI+MACD+布林 訊號")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="要回測的交易對")
    parser.add_argument("--db", default=DB_PATH, help="SQLite 資料庫檔案路徑")
    parser.add_argument("--min-bars", type=int, default=DEFAULT_MIN_BARS, help="開始產生訊號前所需的最少根數（暖機期）")
    parser.add_argument("--rsi-period", type=int, default=14, help="RSI 週期")
    parser.add_argument("--rsi-oversold", type=float, default=30.0, help="RSI 超賣門檻")
    parser.add_argument("--rsi-overbought", type=float, default=70.0, help="RSI 超買門檻")
    parser.add_argument("--macd-fast", type=int, default=12, help="MACD 快線 EMA 週期")
    parser.add_argument("--macd-slow", type=int, default=26, help="MACD 慢線 EMA 週期")
    parser.add_argument("--macd-signal", type=int, default=9, help="MACD 訊號線 EMA 週期")
    parser.add_argument("--bb-period", type=int, default=20, help="布林通道週期")
    parser.add_argument("--bb-std", type=float, default=2.0, help="布林通道標準差倍數")
    parser.add_argument("--kd-k-period", type=int, default=14, help="KD %%K 週期")
    parser.add_argument("--kd-smooth-k", type=int, default=3, help="KD %%K 平滑週期")
    parser.add_argument("--kd-d-period", type=int, default=3, help="KD %%D 週期")
    parser.add_argument("--kd-oversold", type=float, default=20.0, help="KD 超賣門檻")
    parser.add_argument("--kd-overbought", type=float, default=80.0, help="KD 超買門檻")
    parser.add_argument("--fib-lookback", type=int, default=55, help="費波那契回撤取樣根數")
    parser.add_argument("--fib-tolerance-pct", type=float, default=0.05, help="費波那契回撤位容忍範圍（佔波段幅度比例）")
    args = parser.parse_args()

    signal_kwargs = dict(
        rsi_period=args.rsi_period,
        rsi_oversold=args.rsi_oversold,
        rsi_overbought=args.rsi_overbought,
        macd_fast=args.macd_fast,
        macd_slow=args.macd_slow,
        macd_signal=args.macd_signal,
        bb_period=args.bb_period,
        bb_std=args.bb_std,
        kd_k_period=args.kd_k_period,
        kd_smooth_k=args.kd_smooth_k,
        kd_d_period=args.kd_d_period,
        kd_oversold=args.kd_oversold,
        kd_overbought=args.kd_overbought,
        fib_lookback=args.fib_lookback,
        fib_tolerance_pct=args.fib_tolerance_pct,
    )

    conn = get_connection(args.db)
    try:
        for symbol in args.symbols:
            highs, lows, closes = read_ohlc(conn, symbol)
            result = backtest(closes, highs=highs, lows=lows, min_bars=args.min_bars, **signal_kwargs)
            if result["bars_tested"] == 0:
                print(f"{symbol}: 資料不足，無法回測（需要至少 {args.min_bars + 2} 根 K 線）")
                continue
            win_rate_str = f"{result['win_rate']:.1%}" if result["win_rate"] is not None else "N/A"
            print(
                f"{symbol}: 測試 {result['bars_tested']} 根 K 線，"
                f"{result['trades']} 次進場，勝率 {win_rate_str}，"
                f"策略累積報酬 {result['total_return']:.2%}，"
                f"複利終值 {result['final_equity']:.4f}，"
                f"買入持有報酬 {result['buy_hold_return']:.2%}"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
