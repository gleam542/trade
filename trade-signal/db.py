import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS klines (
    symbol TEXT NOT NULL,
    open_time INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    close_time INTEGER NOT NULL,
    PRIMARY KEY (symbol, open_time)
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


def upsert_klines(conn: sqlite3.Connection, symbol: str, rows: list[tuple]) -> None:
    conn.executemany(
        """
        INSERT INTO klines (symbol, open_time, open, high, low, close, volume, close_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, open_time) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            close_time=excluded.close_time
        """,
        [(symbol, *row) for row in rows],
    )
    conn.commit()


def latest_open_time(conn: sqlite3.Connection, symbol: str) -> int | None:
    cur = conn.execute(
        "SELECT MAX(open_time) FROM klines WHERE symbol = ?", (symbol,)
    )
    result = cur.fetchone()[0]
    return int(result) if result is not None else None
