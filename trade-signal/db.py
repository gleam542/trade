import psycopg

SCHEMA = """
CREATE TABLE IF NOT EXISTS klines (
    market TEXT NOT NULL DEFAULT 'spot',
    symbol TEXT NOT NULL,
    open_time BIGINT NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    close_time BIGINT NOT NULL,
    PRIMARY KEY (market, symbol, open_time)
);
"""


def get_connection(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url)
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()
    return conn


def upsert_klines(conn: psycopg.Connection, symbol: str, rows: list[tuple], market: str = "spot") -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO klines (market, symbol, open_time, open, high, low, close, volume, close_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (market, symbol, open_time) DO UPDATE SET
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


def latest_open_time(conn: psycopg.Connection, symbol: str, market: str = "spot") -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(open_time) FROM klines WHERE market = %s AND symbol = %s", (market, symbol)
        )
        result = cur.fetchone()[0]
    return int(result) if result is not None else None


def read_closes(
    conn: psycopg.Connection, symbol: str, limit: int | None = None, market: str = "spot"
) -> list[float]:
    """Return closing prices for a symbol in ascending open_time order.

    With `limit`, returns the most recent `limit` closes (still ascending).
    """
    with conn.cursor() as cur:
        if limit is None:
            cur.execute(
                "SELECT close FROM klines WHERE market = %s AND symbol = %s ORDER BY open_time ASC",
                (market, symbol),
            )
        else:
            cur.execute(
                """
                SELECT close FROM (
                    SELECT close, open_time FROM klines
                    WHERE market = %s AND symbol = %s
                    ORDER BY open_time DESC
                    LIMIT %s
                ) AS recent ORDER BY open_time ASC
                """,
                (market, symbol, limit),
            )
        rows = cur.fetchall()
    return [row[0] for row in rows]


def read_ohlc(
    conn: psycopg.Connection, symbol: str, limit: int | None = None, market: str = "spot"
) -> tuple[list[float], list[float], list[float]]:
    """Return (highs, lows, closes) for a symbol in ascending open_time order.

    With `limit`, returns the most recent `limit` bars (still ascending).
    """
    with conn.cursor() as cur:
        if limit is None:
            cur.execute(
                "SELECT high, low, close FROM klines WHERE market = %s AND symbol = %s ORDER BY open_time ASC",
                (market, symbol),
            )
        else:
            cur.execute(
                """
                SELECT high, low, close FROM (
                    SELECT high, low, close, open_time FROM klines
                    WHERE market = %s AND symbol = %s
                    ORDER BY open_time DESC
                    LIMIT %s
                ) AS recent ORDER BY open_time ASC
                """,
                (market, symbol, limit),
            )
        rows = cur.fetchall()
    highs = [row[0] for row in rows]
    lows = [row[1] for row in rows]
    closes = [row[2] for row in rows]
    return highs, lows, closes
