import argparse

from config import DB_PATH, DEFAULT_INTERVAL, DEFAULT_LIMIT, DEFAULT_SYMBOLS
from db import get_connection, upsert_klines
from fetch import fetch_klines


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取加密貨幣行情並存入 SQLite")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, help="交易對，如 BTCUSDT ETHUSDT")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="K 線週期，如 1h 4h 1d")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="每個交易對抓取的 K 線根數")
    parser.add_argument("--db", default=DB_PATH, help="SQLite 資料庫檔案路徑")
    args = parser.parse_args()

    conn = get_connection(args.db)
    try:
        for symbol in args.symbols:
            rows = fetch_klines(symbol, args.interval, args.limit)
            upsert_klines(conn, symbol, rows)
            print(f"{symbol}: 存入 {len(rows)} 筆 {args.interval} K 線資料")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
