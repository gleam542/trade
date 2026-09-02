import argparse
import sys
import time

from config import DATABASE_URL, DEFAULT_INTERVAL, DEFAULT_LIMIT, DEFAULT_SYMBOLS
from db import get_connection, upsert_klines
from fetch import FetchError, fetch_futures_klines, fetch_klines, list_futures_perpetual_symbols

# Being polite to Binance's rate limit when --all fires off a few hundred
# requests back-to-back — a small --symbols list never needed this.
ALL_MODE_REQUEST_DELAY_SECONDS = 0.1


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取加密貨幣行情並存入 PostgreSQL")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help=f"改抓現貨這幾個交易對（預設不指定時抓的是全部合約，見 --all）。例：{' '.join(DEFAULT_SYMBOLS)}",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="抓幣安所有 USDT 本位永續合約（fapi.binance.com），存入時 market='futures'。"
        "不指定 --symbols 也不指定 --all 時，這是預設行為",
    )
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, help="K 線週期，如 1h 4h 1d")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="每個交易對抓取的 K 線根數")
    parser.add_argument("--db", default=DATABASE_URL, help="PostgreSQL 連線字串（預設讀環境變數 DATABASE_URL）")
    args = parser.parse_args()

    # Neither flag given -> default to the full futures universe, not the
    # small spot list — --symbols (explicit or not) is the only way to get
    # spot data now.
    if args.symbols is None and not args.all:
        args.all = True

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
