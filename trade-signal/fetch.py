import requests

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


def fetch_klines(symbol: str, interval: str = "1h", limit: int = 500) -> list[tuple]:
    """Fetch OHLCV klines for a symbol from Binance's public REST API.

    Returns a list of (open_time, open, high, low, close, volume, close_time) tuples.
    """
    resp = requests.get(
        BINANCE_KLINES_URL,
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    raw = resp.json()
    return [
        (
            int(row[0]),
            float(row[1]),
            float(row[2]),
            float(row[3]),
            float(row[4]),
            float(row[5]),
            int(row[6]),
        )
        for row in raw
    ]
