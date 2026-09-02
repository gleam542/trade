import requests

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


class FetchError(RuntimeError):
    """Raised when klines can't be fetched — network failure, rate limiting,
    or a Binance API error — with a message meant to be shown to the user
    directly, instead of a raw requests/HTTP traceback."""


def fetch_klines(symbol: str, interval: str = "1h", limit: int = 500) -> list[tuple]:
    """Fetch OHLCV klines for a symbol from Binance's public REST API.

    Returns a list of (open_time, open, high, low, close, volume, close_time) tuples.
    Raises FetchError on network failure, rate limiting, or an invalid
    symbol/interval — never a raw requests exception.
    """
    try:
        resp = requests.get(
            BINANCE_KLINES_URL,
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise FetchError(f"{symbol}：連不到 Binance API（{e.__class__.__name__}：{e}）") from e

    if resp.status_code == 429:
        raise FetchError(f"{symbol}：被 Binance 限流（429），請稍後再試或降低抓取頻率／根數")
    if resp.status_code == 400:
        try:
            detail = resp.json().get("msg", resp.text)
        except ValueError:
            detail = resp.text
        raise FetchError(f"{symbol}：Binance 回傳 400，交易對或參數可能有誤（{detail}）")
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise FetchError(f"{symbol}：Binance API 回傳錯誤（HTTP {resp.status_code}）") from e

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
