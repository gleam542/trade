import requests

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
FUTURES_KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
FUTURES_EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"


class FetchError(RuntimeError):
    """Raised when klines can't be fetched — network failure, rate limiting,
    or a Binance API error — with a message meant to be shown to the user
    directly, instead of a raw requests/HTTP traceback."""


def _get_klines(url: str, symbol: str, interval: str, limit: int) -> list[tuple]:
    try:
        resp = requests.get(
            url,
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


def fetch_klines(symbol: str, interval: str = "1h", limit: int = 500) -> list[tuple]:
    """Fetch OHLCV klines for a symbol from Binance's spot public REST API.

    Returns a list of (open_time, open, high, low, close, volume, close_time) tuples.
    Raises FetchError on network failure, rate limiting, or an invalid
    symbol/interval — never a raw requests exception.
    """
    return _get_klines(BINANCE_KLINES_URL, symbol, interval, limit)


def fetch_futures_klines(symbol: str, interval: str = "1h", limit: int = 500) -> list[tuple]:
    """Same as fetch_klines(), but from Binance's USDⓈ-M futures REST API
    (fapi.binance.com) instead of spot — a different market with its own
    price series, even for a symbol name shared with the spot pair."""
    return _get_klines(FUTURES_KLINES_URL, symbol, interval, limit)


def list_futures_perpetual_symbols() -> list[str]:
    """All USDT-margined perpetual contracts currently trading on Binance
    Futures, e.g. ["BTCUSDT", "ETHUSDT", ...] — sorted, no duplicates.

    Filters fapi.binance.com's exchangeInfo down to contractType ==
    "PERPETUAL", quoteAsset == "USDT", and status == "TRADING" (excludes
    delivery/quarterly contracts and symbols that are delisted or in a
    pre-launch/break state). Raises FetchError on network failure or a
    non-2xx response, same as the kline fetchers.
    """
    try:
        resp = requests.get(FUTURES_EXCHANGE_INFO_URL, timeout=10)
    except requests.exceptions.RequestException as e:
        raise FetchError(f"抓取 Binance 合約交易對清單失敗（{e.__class__.__name__}：{e}）") from e

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise FetchError(f"抓取 Binance 合約交易對清單失敗（HTTP {resp.status_code}）") from e

    symbols = [
        s["symbol"]
        for s in resp.json().get("symbols", [])
        if s.get("contractType") == "PERPETUAL"
        and s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING"
    ]
    return sorted(set(symbols))
