# trade-signal

抓取加密貨幣行情數據並存入 SQLite 資料庫，之後可以基於這些數據做多空分析。

目前階段：只做資料收集（K 線 OHLCV），分析邏輯之後再加。

## 資料來源

Binance 公開 REST API（`/api/v3/klines`），不需要 API key。

## 安裝

```bash
pip install -r requirements.txt
```

## 使用方式

```bash
python main.py --symbols BTCUSDT ETHUSDT --interval 1h --limit 500
```

參數：
- `--symbols`：要抓的交易對，預設 `BTCUSDT ETHUSDT BNBUSDT SOLUSDT XRPUSDT`
- `--interval`：K 線週期（`1m` `5m` `1h` `4h` `1d` 等），預設 `1h`
- `--limit`：每個交易對抓取的根數（最大 1000），預設 `500`
- `--db`：SQLite 檔案路徑，預設 `data/trade_signal.db`

資料會存到 `klines` 資料表，以 `(symbol, open_time)` 為主鍵，重複執行會更新既有資料而不會產生重複列。

## 資料表結構

| 欄位 | 說明 |
|---|---|
| symbol | 交易對，如 BTCUSDT |
| open_time | K 線開盤時間（毫秒時間戳） |
| open / high / low / close | 開高低收價 |
| volume | 成交量 |
| close_time | K 線收盤時間（毫秒時間戳） |

## 排程抓取

可以搭配 cron 定期執行，例如每小時抓一次：

```
0 * * * * cd /path/to/trade-signal && python main.py
```

## 多空訊號分析（RSI + MACD）

先用 `main.py` 把資料抓進資料庫，再跑：

```bash
python analyze.py --symbols BTCUSDT ETHUSDT
```

輸出範例：

```
BTCUSDT: 做多  (RSI=28.4, MACD=12.3, 訊號線=8.1)
  理由：RSI 28.4 進入超賣區（<30）；MACD 黃金交叉（MACD 上穿訊號線）
```

判斷邏輯（`signals.py`）：
- RSI（14 期，Wilder 平滑）< 30 視為超賣（偏多 +1 分），> 70 視為超買（偏空 -1 分）
- MACD（12/26/9 EMA）出現黃金交叉（MACD 上穿訊號線，偏多 +1 分）或死亡交叉（偏空 -1 分）
- 兩項加總：分數 > 0 → 做多，< 0 → 做空，= 0 → 觀望

這只是簡單的規則式判斷，不是投資建議，門檻值（30/70、12/26/9）都可以在呼叫 `generate_signal()` 時調整。

## 下一步（尚未實作）

- 回測（驗證這套規則過去的勝率/報酬）
- 更多指標（布林通道、均線交叉等）與更完整的評分機制
