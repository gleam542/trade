import argparse
import sys
import time

from config import DB_PATH, DEFAULT_INTERVAL, DEFAULT_LIMIT, DEFAULT_SYMBOLS
from db import get_connection, upsert_klines
from fetch import FetchError, fetch_futures_klines, fetch_klines, list_futures_perpetual_symbols

# Being polite to Binance's rate limit when --all fires off a few hundred
# requests back-to-back — the small default symbol list never needed this.
ALL_MODE_REQUEST_DELAY_SECONDS = 0.1


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取加密貨幣行情並存入 SQLite")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="交易對，如 BTCUSDT ETHUSDT")
    group.add_argument(
        "--all",
        action="store_true",
        help="改抓幣安所有 USDT 本位永續合約（fapi.binance.com），忽略 --symbols，存入時 market='futures'",
    )
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="K 線週期，如 1h 4h 1d")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="每個交易對抓取的 K 線根數")
    parser.add_argument("--db", default=DB_PATH, help="SQLite 資料庫檔案路徑")
    args = parser.parse_args()

    if args.all:
        try:
            symbols = list_futures_perpetual_symbols()
        except FetchError as e:
            print(f"抓取合約交易對清單失敗 — {e}")
            sys.exit(1)
        print(f"共 {len(symbols)} 個 USDT 本位永續合約")
        fetch = fetch_futures_klines
        market = "futures"
        delay = ALL_MODE_REQUEST_DELAY_SECONDS
    else:
        symbols = args.symbols
        fetch = fetch_klines
        market = "spot"
        delay = 0.0

    failed = []
    conn = get_connection(args.db)
    try:
        for i, symbol in enumerate(symbols):
            # One symbol's failure (network hiccup, rate limit, bad symbol)
            # shouldn't abort the whole batch — record it and keep going so
            # every other symbol still gets fetched and stored this run.
            try:
                rows = fetch(symbol, args.interval, args.limit)
            except FetchError as e:
                print(f"{symbol}: 抓取失敗 — {e}")
                failed.append(symbol)
                continue
            upsert_klines(conn, symbol, rows, market=market)
            print(f"{symbol}: 存入 {len(rows)} 筆 {args.interval} K 線資料")
            if delay and i < len(symbols) - 1:
                time.sleep(delay)
    finally:
        conn.close()

    if failed:
        print(f"\n共 {len(failed)} 個交易對抓取失敗：{', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
