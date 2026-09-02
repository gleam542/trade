import argparse
import sys

from config import DB_PATH, DEFAULT_INTERVAL, DEFAULT_LIMIT, DEFAULT_SYMBOLS
from db import get_connection, upsert_klines
from fetch import FetchError, fetch_klines


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取加密貨幣行情並存入 SQLite")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="交易對，如 BTCUSDT ETHUSDT")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="K 線週期，如 1h 4h 1d")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="每個交易對抓取的 K 線根數")
    parser.add_argument("--db", default=DB_PATH, help="SQLite 資料庫檔案路徑")
    args = parser.parse_args()

    failed = []
    conn = get_connection(args.db)
    try:
        for symbol in args.symbols:
            # One symbol's failure (network hiccup, rate limit, bad symbol)
            # shouldn't abort the whole batch — record it and keep going so
            # every other symbol still gets fetched and stored this run.
            try:
                rows = fetch_klines(symbol, args.interval, args.limit)
            except FetchError as e:
                print(f"{symbol}: 抓取失敗 — {e}")
                failed.append(symbol)
                continue
            upsert_klines(conn, symbol, rows)
            print(f"{symbol}: 存入 {len(rows)} 筆 {args.interval} K 線資料")
    finally:
        conn.close()

    if failed:
        print(f"\n共 {len(failed)} 個交易對抓取失敗：{', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
