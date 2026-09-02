import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS klines (
    market TEXT NOT NULL DEFAULT 'spot',
    symbol TEXT NOT NULL,
    open_time INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    close_time INTEGER NOT NULL,
    PRIMARY KEY (market, symbol, open_time)
);
"""


def _migrate_legacy_schema(conn: sqlite3.Connection) -> None:
    """Pre-market-column databases have `klines` keyed on (symbol, open_time)
    only — every row in them came from the spot API, so rebuild the table
    under the new (market, symbol, open_time) key with market='spot',
    preserving the data instead of losing it to a silent CREATE TABLE IF
    NOT EXISTS no-op."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(klines)").fetchall()]
    if not cols or "market" in cols:
        return
    conn.execute("ALTER TABLE klines RENAME TO klines_legacy")
    conn.execute(SCHEMA)
    conn.execute(
        """
        INSERT INTO klines (market, symbol, open_time, open, high, low, close, volume, close_time)
        SELECT 'spot', symbol, open_time, open, high, low, close, volume, close_time FROM klines_legacy
        """
    )
    conn.execute("DROP TABLE klines_legacy")
    conn.commit()


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    _migrate_legacy_schema(conn)
    return conn


def upsert_klines(conn: sqlite3.Connection, symbol: str, rows: list[tuple], market: str = "spot") -> None:
    conn.executemany(
        """
        INSERT INTO klines (market, symbol, open_time, open, high, low, close, volume, close_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(market, symbol, open_time) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            close_time=excluded.close_time
        """,
        [(market, symbol, *row) for row in rows],
    )
    conn.commit()


def latest_open_time(conn: sqlite3.Connection, symbol: str, market: str = "spot") -> int | None:
    cur = conn.execute(
        "SELECT MAX(open_time) FROM klines WHERE market = ? AND symbol = ?", (market, symbol)
    )
    result = cur.fetchone()[0]
    return int(result) if result is not None else None


def read_closes(
    conn: sqlite3.Connection, symbol: str, limit: int | None = None, market: str = "spot"
) -> list[float]:
    """Return closing prices for a symbol in ascending open_time order.

    With `limit`, returns the most recent `limit` closes (still ascending).
    """
    if limit is None:
        cur = conn.execute(
            "SELECT close FROM klines WHERE market = ? AND symbol = ? ORDER BY open_time ASC",
            (market, symbol),
        )
    else:
        cur = conn.execute(
            """
            SELECT close FROM (
                SELECT close, open_time FROM klines
                WHERE market = ? AND symbol = ?
                ORDER BY open_time DESC
                LIMIT ?
            ) ORDER BY open_time ASC
            """,
            (market, symbol, limit),
        )
    return [row[0] for row in cur.fetchall()]


def read_ohlc(
    conn: sqlite3.Connection, symbol: str, limit: int | None = None, market: str = "spot"
) -> tuple[list[float], list[float], list[float]]:
    """Return (highs, lows, closes) for a symbol in ascending open_time order.

    With `limit`, returns the most recent `limit` bars (still ascending).
    """
    if limit is None:
        cur = conn.execute(
            "SELECT high, low, close FROM klines WHERE market = ? AND symbol = ? ORDER BY open_time ASC",
            (market, symbol),
        )
    else:
        cur = conn.execute(
            """
            SELECT high, low, close FROM (
                SELECT high, low, close, open_time FROM klines
                WHERE market = ? AND symbol = ?
                ORDER BY open_time DESC
                LIMIT ?
            ) ORDER BY open_time ASC
            """,
            (market, symbol, limit),
        )
    rows = cur.fetchall()
    highs = [row[0] for row in rows]
    lows = [row[1] for row in rows]
    closes = [row[2] for row in rows]
    return highs, lows, closes
