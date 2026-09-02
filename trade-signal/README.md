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

## 多空訊號分析（RSI + MACD + 布林通道）

先用 `main.py` 把資料抓進資料庫，再跑：

```bash
python analyze.py --symbols BTCUSDT ETHUSDT
```

輸出範例：

```
BTCUSDT: 做多  (RSI=28.4, MACD=12.3, 訊號線=8.1, 布林上軌=27500.0, 布林下軌=25800.0)
  理由：RSI 28.4 進入超賣區（<30）；MACD 黃金交叉（MACD 上穿訊號線）
  止損價位：25800.0（2倍 ATR=850.0）
```

判斷邏輯（`signals.py`），三項各 ±1 分後加總：
- RSI（14 期，Wilder 平滑）< 30 視為超賣（+1），> 70 視為超買（-1）
- MACD（12/26/9 EMA）出現黃金交叉（MACD 上穿訊號線，+1）或死亡交叉（-1）
- 收盤價跌破布林通道下軌（20 期均線 ± 2 個標準差，+1）或突破上軌（-1）
- 分數 > 0 → 做多，< 0 → 做空，= 0 → 觀望

這只是簡單的規則式判斷，不是投資建議，門檻值和週期都可以在呼叫 `generate_signal()` 時調整。

有做多/做空判斷時，還會算一個 ATR（Average True Range，14 期，Wilder 平滑）為基礎的止損價位：做多是「現價 − 2×ATR」，做空是「現價 + 2×ATR」——止損幅度會跟著這個交易對當下的實際波動大小走，而不是固定百分比。`generate_signal()` 需要額外傳入 `highs`/`lows`（跟 `closes`等長）才會算這個；沒傳就只回傳 `atr`/`stop_loss` 皆為 `None`，不影響原本的多空判斷。目前這個止損價位只是「算出來顯示」，`backtest.py` 的回測還沒有模擬止損觸發後提前出場的情境（見下方「下一步」）。

## 回測

驗證這套規則在歷史資料上的表現：

```bash
python backtest.py --symbols BTCUSDT ETHUSDT
```

輸出範例：

```
BTCUSDT: 測試 440 根 K 線，132 次進場，勝率 54.5%，策略累積報酬 8.32%，複利終值 1.0891，買入持有報酬 15.20%
```

回測方式：從第 `--min-bars`（預設 60）根開始，每一根只用當下（含）以前的收盤價產生訊號，用下一根的漲跌幅評分——「做多」賺下一根漲幅、「做空」賺其反向、「觀望」不動作（持有現金）。這是驗證訊號本身有沒有一步預測力的簡化評估，不是計入手續費、滑價、部位管理的真實策略模擬，也沒有「持有到訊號翻轉才出場」的邏輯。

## API + 前端

`api.py` 用 FastAPI 把上面幾支腳本包成 HTTP 介面，`frontend/console.html` 是一個會呼叫這個 API 的靜態網頁。

啟動 API：

```bash
uvicorn api:app --reload --port 8000
```

端點：
- `GET /api/symbols` — 資料庫裡有資料的交易對清單
- `GET /api/signal/{symbol}` — 該交易對目前的 `generate_signal()` 結果
- `GET /api/chart/{symbol}?limit=300` — 逐根 K 線的 OHLC + 指標 + 當下（不含未來）訊號 + 止損價位，給畫圖用
- `GET /api/backtest/{symbol}?...` — 呼叫 `backtest()`，查詢參數對應 `--rsi-period` 等 CLI 參數
- `GET /api/advise?capital=&profit_pct=&hours=` — 跨交易對掃描：本金、目標盈利 %、預計花費小時數，換算成每小時所需報酬率，挑出目前訊號分數最高的交易對，並附上該方向在 `backtest()` 回測中的歷史勝率／平均報酬、以及 ATR 止損價位做參考（`backtest()` 現在會額外回傳 `by_direction: {long, short}` 的細分統計）

啟動後可以打開 `http://localhost:8000/docs` 看自動產生的 API 文件。CORS 預設全開（`allow_origins=["*"]`），方便本機開發時用不同 port 或直接開檔案存取；正式對外提供服務前要收窄。

打開前端：先確定 API 正在跑（見上），再直接用瀏覽器開啟 `frontend/console.html`（或用任何靜態伺服器），畫面上方的欄位可以改 API 位址（預設 `http://localhost:8000`）。這個檔案會即時 fetch 這幾個端點，跟前面章節的腳本是同一套邏輯、同一個資料庫，不是另外寫死的展示資料。

畫面上有兩塊容易搞混、但範圍不同的區塊：
- **最新判斷**（摘要條，在交易對分頁下方）：只反映你**目前選取的分頁**（例如點 BTCUSDT 就顯示 BTCUSDT 自己的 `generate_signal()` 結果，含止損價位），切換分頁就會跟著換。
- **策略試算／建議商品**（頁面最下方）：呼叫 `/api/advise`，永遠掃描**全部**追蹤中的交易對，跟你目前點開哪個分頁無關——它可能推薦一個你根本沒在看的交易對，下面還有一張「各交易對每小時報酬率比較」圖表，把每個候選（不只是最後選中的那個）都畫出來跟目標比。

所以兩者顯示不同交易對、甚至方向相反都是正常的，不是同一件事互相矛盾。

> 這跟你可能在對話裡看到的 Claude Artifact 版「Signal Console」是兩個東西：Artifact 版本裡的資料是寫死內嵌的示範資料，而且託管在 Claude 的網頁沙盒環境裡，基於安全限制連不到你本機的 API；`frontend/console.html` 才是真正串接這支 API 的版本，但只能在你本機（或你部署 API 的地方）打開才會有資料。

## 下一步（尚未實作）

- 更完整的持倉邏輯（訊號翻轉才換邊，而非每根重新進出場），並讓 `backtest.py` 真正模擬「觸發止損價位就提前出場」，而不是只顯示止損價位
- 交易成本／滑價模擬
- 均線交叉等更多指標
