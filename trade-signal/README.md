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

單一交易對抓取失敗（連不到 Binance、被限流、交易對打錯字等）不會中斷整批：`main.py` 會印出那個交易對的錯誤原因、跳過它，繼續抓其餘交易對；跑完後如果有任何交易對失敗，會印出失敗清單並以非 0 狀態碼結束（方便 cron 或監控腳本偵測），已成功抓到的交易對照樣會存進資料庫。

## 資料表結構

| 欄位 | 說明 |
|---|---|
| symbol | 交易對，如 BTCUSDT |
| open_time | K 線開盤時間（毫秒時間戳） |
| open / high / low / close | 開高低收價 |
| volume | 成交量 |
| close_time | K 線收盤時間（毫秒時間戳） |

## 排程抓取

可以搭配 cron 定期執行，例如每 15 分鐘存一次庫：

```
*/15 * * * * cd /path/to/trade-signal && python main.py >> fetch.log 2>&1
```

「多久存一次」（cron 排程頻率）跟「每根 K 線代表多長時間」（`--interval`）是兩件獨立的事：上面這行預設還是抓 `--interval 1h` 的 1 小時 K 線，只是每 15 分鐘重新抓一次最新資料——由於 `(symbol, open_time)` 是主鍵，還沒收盤的當前這根 K 線會被同一列覆蓋更新，不會重複。如果要讓存進去的 K 線本身就是 15 分鐘一根，改成 `python main.py --interval 15m` 即可，兩者可以獨立選擇也可以搭配著用。

## 多空訊號分析（RSI + MACD + 布林通道 + KD + 費波那契回撤）

先用 `main.py` 把資料抓進資料庫，再跑：

```bash
python analyze.py --symbols BTCUSDT ETHUSDT
```

輸出範例：

```
BTCUSDT: 做多  (RSI=28.4, MACD=12.3, 訊號線=8.1, 布林上軌=27500.0, 布林下軌=25800.0)
  理由：RSI 28.4 進入超賣區（<30）；MACD 黃金交叉（MACD 上穿訊號線）；KD %K 15.2 進入超賣區（<20）
  KD：%K=15.2, %D=18.4
  費波那契：上升段 61.8% 回撤位=26800.0（高=28500.0, 低=24200.0）
  止損價位：25800.0（2倍 ATR=850.0）
```

判斷邏輯（`signals.py`），五項各 ±1 分後加總：
- RSI（14 期，Wilder 平滑）< 30 視為超賣（+1），> 70 視為超買（-1）
- MACD（12/26/9 EMA）出現黃金交叉（MACD 上穿訊號線，+1）或死亡交叉（-1）
- 收盤價跌破布林通道下軌（20 期均線 ± 2 個標準差，+1）或突破上軌（-1）
- KD 隨機指標（%K 14 期、平滑 3 期，%D 再 3 期均線）< 20 視為超賣（+1），> 80 視為超買（-1）——概念上跟 RSI 類似（抓超買超賣），但用高低價的相對位置算，不是只看收盤價
- 收盤價貼近近 55 根 K 線波段高低點的 61.8% 費波那契回撤位（容忍範圍為波段幅度的 5%）：波段是上升段（低點先出現）且價格拉回到回撤位視為支撐（+1）；波段是下跌段（高點先出現）且價格反彈到回撤位視為壓力（-1）
- 分數 > 0 → 做多，< 0 → 做空，= 0 → 觀望

這只是簡單的規則式判斷，不是投資建議，門檻值和週期都可以在呼叫 `generate_signal()` 時調整。KD 和費波那契回撤跟 ATR 止損一樣，需要額外傳入 `highs`/`lows` 才會計算並參與計分；沒傳就只回傳 `kd_k`/`kd_d`/`fib_level` 等欄位皆為 `None`，不影響其餘三項判斷。費波那契回撤位的抓法是簡化版（只挑近期波段高低點與單一 61.8% 位階，不分辨多重波段或畫出完整的 0/23.6/38.2/50/61.8/100% 網格），實務上這個位階常和其他訊號一起看，這裡把它當成跟 RSI/KD 同等級的單一 ±1 因子。

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

回測方式：從第 `--min-bars`（預設 60）根開始，每一根只用當下（含）以前的收盤價（以及高低價，若有提供）產生訊號，用下一根的漲跌幅評分——「做多」賺下一根漲幅、「做空」賺其反向、「觀望」不動作（持有現金）。這是驗證訊號本身有沒有一步預測力的簡化評估，不是計入手續費、滑價、部位管理的真實策略模擬，也沒有「持有到訊號翻轉才出場」的邏輯。`backtest()` 也可以額外傳入 `highs`/`lows`，讓 KD 和費波那契回撤（以及 ATR 止損）在回測時跟即時判斷一樣參與計分；CLI 版（`backtest.py`）預設會用 `read_ohlc()` 抓好高低價，並提供 `--kd-k-period`、`--kd-oversold`、`--fib-lookback` 等對應參數可調。

## API + 前端

`api.py` 用 FastAPI 把上面幾支腳本包成 HTTP 介面，`frontend/console.html` 是一個會呼叫這個 API 的靜態網頁。

啟動 API：

```bash
uvicorn api:app --reload --port 8000
```

端點：
- `GET /api/symbols` — 資料庫裡有資料的交易對清單
- `GET /api/signal/{symbol}` — 該交易對目前的 `generate_signal()` 結果
- `GET /api/chart/{symbol}?limit=300` — 逐根 K 線的 OHLC + 指標（含 `kdK`/`kdD`/`fibLevel`/`fibSwingHigh`/`fibSwingLow`/`fibUptrend`）+ 當下（不含未來）訊號 + 止損價位，給畫圖用
- `GET /api/backtest/{symbol}?...` — 呼叫 `backtest()`，查詢參數對應 `--rsi-period`、`--kd-k-period`、`--fib-lookback` 等 CLI 參數
- `GET /api/advise?capital=&profit_pct=&hours=` — 跨交易對掃描：本金、目標盈利 %、預計花費小時數，換算成每小時所需報酬率（`requiredHourlyPct`），排序時先分兩層——「歷史上該方向的平均每小時報酬（來自 `backtest()` 的 `by_direction` 細分）有沒有達到這個目標」排前面，同樣有達到／同樣沒達到的再比訊號分數的信心度（`|score| / 5`，五項指標同向觸發的比例），最後比勝率。也就是說輸入的本金／目標盈利／小時數改變時，`requiredHourlyPct` 跟著變，兩層排序的結果也可能跟著換人——不是固定訊號分數排序、只是換個數字顯示而已。附上該方向的歷史勝率／平均報酬、以及 ATR 止損價位做參考

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
