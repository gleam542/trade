import argparse

from config import DB_PATH, DEFAULT_SYMBOLS
from db import get_connection, read_ohlc
from signals import generate_signal

SIGNAL_LABELS = {"long": "做多", "short": "做空", "neutral": "觀望"}


def main() -> None:
    parser = argparse.ArgumentParser(description="根據資料庫中的 K 線資料，用 RSI + MACD 判斷多空訊號")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="要分析的交易對")
    parser.add_argument("--db", default=DB_PATH, help="SQLite 資料庫檔案路徑")
    args = parser.parse_args()

    conn = get_connection(args.db)
    try:
        for symbol in args.symbols:
            highs, lows, closes = read_ohlc(conn, symbol)
            result = generate_signal(closes, highs=highs, lows=lows)
            label = SIGNAL_LABELS[result["signal"]]
            print(
                f"{symbol}: {label}  (RSI={result['rsi']}, MACD={result['macd']}, "
                f"訊號線={result['macd_signal']}, 布林上軌={result['bb_upper']}, 布林下軌={result['bb_lower']})"
            )
            print(f"  理由：{result['reason']}")
            if result["kd_k"] is not None:
                print(f"  KD：%K={result['kd_k']}, %D={result['kd_d']}")
            if result["fib_level"] is not None:
                trend = "上升段" if result["fib_uptrend"] else "下跌段"
                print(
                    f"  費波那契：{trend} 61.8% 回撤位={result['fib_level']}"
                    f"（高={result['fib_swing_high']}, 低={result['fib_swing_low']}）"
                )
            if result["stop_loss"] is not None:
                print(f"  止損價位：{result['stop_loss']}（2倍 ATR={result['atr']}）")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
