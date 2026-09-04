# trade-signal

抓取加密貨幣行情數據存入 PostgreSQL，計算技術指標、產生多空訊號、跑回測，並提供 HTTP API 與網頁介面。

![Signal Console](docs/console.png)

網頁介面（`frontend/console.html`，由 `api.py` 掛在根路徑）：左邊是最新判斷與各項指標讀數，圖表疊上布林通道、EMA100 趨勢線、費波那契回撤位，三角形標出每一根 K 線當下會發出的訊號；往下還有 RSI、KD、MACD 三張子圖與逐根數值的原始資料表。

<details>
<summary>API 文件（<code>/docs</code>，FastAPI 自動產生）</summary>

![API docs](docs/api-docs.png)

</details>

> 截圖裡的埠號是產生截圖時的臨時實例，照下面說明啟動的話是 `8000`。

## 資料來源

預設抓 Binance USDT 本位永續合約公開 REST API（`fapi.binance.com`），不需要 API key。也可以改抓 Binance 現貨（`/api/v3/klines`）——見下方 `--symbols`。

## 安裝

```bash
pip install -r requirements.txt
```

需要一個可連線的 PostgreSQL（本機安裝、`docker compose up db`，或雲端代管的都可以）。連線字串透過環境變數 `DATABASE_URL` 設定（例如 `postgresql://user:password@host:5432/trade_signal`），沒設的話預設連 `postgresql://postgres:postgres@localhost:5432/trade_signal`；每支 CLI 腳本也都有 `--db` 參數可以覆蓋，用途一樣。資料表（`klines`）會在第一次連線時自動建立（`CREATE TABLE IF NOT EXISTS`），不用手動建表。

## 使用方式

```bash
python main.py
```

參數：
- 不加任何參數：抓幣安**所有**目前在交易中的 USDT 本位永續合約（等同 `--all`，見下）——這是預設行為
- `--symbols`：改抓**現貨**這幾個交易對，例如 `--symbols BTCUSDT ETHUSDT`（跟 `--all` 互斥，兩者只能擇一；不指定 `--symbols` 也不指定 `--all` 時，等同指定了 `--all`）
- `--all`：明確指定抓全部 USDT 本位永續合約（`fapi.binance.com/fapi/v1/exchangeInfo` 篩出 `contractType=PERPETUAL`、`quoteAsset=USDT`、`status=TRADING`，約三、四百個），存入時 `market` 欄位會是 `futures`。因為一次要打幾百次 API，這個模式下每個交易對之間會停頓 0.1 秒才發下一個請求，避免觸發 Binance 限流；一輪跑下來大約數十秒
- `--interval`：K 線週期（`1m` `5m` `1h` `4h` `1d` 等），預設 `1h`
- `--limit`：每個交易對抓取的根數（最大 1000），預設 `500`
- `--db`：PostgreSQL 連線字串，預設讀環境變數 `DATABASE_URL`（見上方「安裝」）

資料會存到 `klines` 資料表，以 `(market, symbol, open_time)` 為主鍵，重複執行會更新既有資料而不會產生重複列（`INSERT ... ON CONFLICT DO UPDATE`）——`market` 讓現貨（`spot`，`--symbols`）跟合約（`futures`，預設或 `--all`）的同名交易對（例如現貨 BTCUSDT 跟合約 BTCUSDT）分開存放，不會互相覆蓋。

**注意這裡有兩個不同的「預設」，容易搞混**：`main.py`**抓資料**時不加參數預設抓合約（上面說的）；但 `read_ohlc()`／`read_closes()` 的 `market` 參數、`analyze.py`／`backtest.py` CLI 版、`api.py` 的 `/api/symbols`／`/api/signal`／`/api/chart`／`/api/backtest` 這幾個單一交易對端點，**分析時**預設看的都還是現貨（`market='spot'`）——如果你只跑過預設的 `python main.py`（合約），資料庫裡會沒有現貨資料，這些分析端點會查不到東西（`analyze.py`／`backtest.py` 會印出「無此交易對資料」，API 端點會回 404）。API 端點都接受 `market=futures` 查詢參數可以指定看合約（前端「交易對」分頁旁邊的市場別選單就是用這個切換）；`/api/advise`（策略試算）比較特別，固定會同時掃描現貨＋合約兩個市場，不受 `market` 參數（它本來就不接受這個參數）或前端選單影響。

單一交易對抓取失敗（連不到 Binance、被限流、交易對打錯字等）不會中斷整批：`main.py` 會印出那個交易對的錯誤原因、跳過它，繼續抓其餘交易對；跑完後如果有任何交易對失敗，會印出失敗清單並以非 0 狀態碼結束（方便 cron 或監控腳本偵測），已成功抓到的交易對照樣會存進資料庫。

## 資料表結構

| 欄位 | 說明 |
|---|---|
| market | 市場別，`spot`（現貨，預設）或 `futures`（USDT 本位永續合約） |
| symbol | 交易對，如 BTCUSDT |
| open_time | K 線開盤時間（毫秒時間戳） |
| open / high / low / close | 開高低收價 |
| volume | 成交量 |
| close_time | K 線收盤時間（毫秒時間戳） |

## 排程抓取

用 Docker 的話不用自己設 cron——`docker-compose.yml` 內建一個 `scheduler` 服務，`docker compose up` 就會自動每 15 分鐘跑一次 `python main.py`（見下方「Docker」一節）。以下是不用 Docker、自己在主機上跑時的作法。

可以搭配 cron 定期執行，例如每 15 分鐘存一次庫（不加參數，預設抓全部合約）：

```
*/15 * * * * cd /path/to/trade-signal && DATABASE_URL=postgresql://user:password@host:5432/trade_signal python main.py >> fetch.log 2>&1
```

只想抓現貨那幾個交易對的話，cron 那行加上 `--symbols`（例如 `python main.py --symbols BTCUSDT ETHUSDT`）即可——這樣每輪只打個位數次 API，遠比抓全部合約輕量。

cron 執行環境不會自動帶入你互動式 shell 的環境變數，所以 `DATABASE_URL` 通常要像上面這樣直接寫在 crontab 那一行裡（或寫進一個 cron 會讀到的 env 檔）。

### macOS：用 launchd 取代 cron

macOS 上比 cron 順手的做法是 launchd。在 `~/Library/LaunchAgents/` 放一個 plist，登入時自動載入：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>com.trade-signal.fetch</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/sh</string>
		<string>-c</string>
		<string>cd /path/to/trade-signal &amp;&amp; ./.venv/bin/python main.py --symbols BTCUSDT ETHUSDT; ./.venv/bin/python main.py --all</string>
	</array>
	<key>EnvironmentVariables</key>
	<dict>
		<key>DATABASE_URL</key>
		<string>postgresql://user@localhost:5432/trade_signal</string>
	</dict>
	<key>StartInterval</key>
	<integer>900</integer>
	<key>RunAtLoad</key>
	<true/>
	<key>StandardOutPath</key>
	<string>/path/to/trade-signal/fetch.log</string>
	<key>StandardErrorPath</key>
	<string>/path/to/trade-signal/fetch.log</string>
</dict>
</plist>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.trade-signal.fetch.plist
launchctl kickstart -k gui/$(id -u)/com.trade-signal.fetch   # 立刻跑一輪
launchctl bootout gui/$(id -u)/com.trade-signal.fetch        # 停用
```

跟 cron 一樣要注意環境變數不會自動帶入，所以 `DATABASE_URL` 寫在 `EnvironmentVariables` 裡。上面範例一輪跑兩批（現貨 + 合約），因為 `main.py` 一次只能抓一種市場——只跑 `--all` 的話現貨資料會停在最後一次手動抓取的時間點不再更新（`docker-compose.yml` 的 `scheduler` 就只跑合約，同樣要注意）。

**改了 plist 內容之後，`kickstart` 是沒用的**——這點很容易踩到而且完全不會報錯。launchd 是在 `bootstrap` 時把 plist 讀進記憶體的，`kickstart -k` 只把行程殺掉重開，用的還是舊設定。所以改了環境變數（例如加密碼）、路徑或間隔之後，行程看起來是新的、卻完全沒吃到新設定，會誤以為是自己填錯：

```bash
# 改了 plist 內容 → 必須完整卸載再載入
launchctl bootout gui/$(id -u)/com.trade-signal.api
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.trade-signal.api.plist

# 只改了 .py 程式碼、plist 沒動 → kickstart 就夠（原地重啟，比較快）
launchctl kickstart -k gui/$(id -u)/com.trade-signal.api
```

`bootout` 之後緊接著 `bootstrap` 有機會撞到 `Bootstrap failed: 5: Input/output error`——那是前一個還在卸載中的競態，不是 plist 有問題，等一兩秒再 `bootstrap` 就好。

API 也可以照這個模式寫一個 plist（把 `StartInterval` 換成 `KeepAlive`），指令是 `./.venv/bin/python -m uvicorn api:app --port 8000`。前端不用另外開服務——`api.py` 已經把 `frontend/` 掛在同一個 port 上了（見下方「API + 前端」）。要放密碼的話記得 plist 是明文檔，`chmod 600` 一下；用 `plutil` 寫入比手改 XML 不容易出錯：

```bash
plutil -replace EnvironmentVariables.API_PASSWORD -string '你的密碼' \
  ~/Library/LaunchAgents/com.trade-signal.api.plist
```

**專案放在 `~/Desktop`／`~/Documents`／`~/Downloads` 底下的話會撞到 macOS TCC 隱私權限**——launchd 啟動的行程沒有這些目錄的存取權，而且症狀會因為執行檔而異，不容易看出是權限問題：

- `/usr/bin/python3`（系統 Python）跑 `http.server` 會回 404 `No permission to list directory`
- `.venv/bin/uvicorn` 這種 venv 產生的 wrapper script 會噴 `PermissionError: ... pyvenv.cfg`
- 但 `.venv/bin/python` 本身可以正常存取——所以上面所有範例都統一走 `./.venv/bin/python -m <module>`，而不是直接呼叫 `uvicorn` 指令
- plist 裡設 `WorkingDirectory` 會在每次執行時印出 `getcwd: cannot access parent directories` 警告（功能不受影響，純噪音），改成在 `sh -c` 裡 `cd` 就沒有

最乾淨的解法是把專案放在這些受保護目錄之外（例如 `~/dev/`），就完全不用處理上面這些。不然就是去「系統設定 → 隱私權與安全性 → 完全磁碟取用權」加入 `/bin/sh`。

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
- **趨勢過濾**（`trend_period`，預設 100 期 EMA）：上面五項全是均值回歸指標——超買就看空、超賣就看多——在單邊趨勢裡會一路逆勢進場、一路被停損。所以最後再過一道：收盤價在長期 EMA **之上**時擋掉做空、**之下**時擋掉做多，只留順勢的那一邊，被擋下的一律變成觀望。`trend_period=0` 可關閉過濾、取回原始的均值回歸訊號；EMA 還沒暖機完的前 99 根不過濾（沒有趨勢讀數可比）

被趨勢過濾擋下時，`score` 與 `reason` 都會保留原本的內容、只有 `signal` 變成 `neutral`，並在 `reason` 末尾附上被擋的原因——所以你看得到「本來要發什麼訊號、為什麼沒發」，而不是憑空變成觀望。輸出多一個 `trend_ema` 欄位（過濾關閉或還沒暖機時為 `None`）。實測 10 支合約各約 500 根 1h K 線，開啟過濾後平均總報酬由 **−2.49% 轉為 +5.23%**、平均勝率 53.6% → 60.8%、交易筆數降到約三分之一（擋掉的都是逆勢單）。**但兩種設定都沒有贏過單純買入持有**（那段期間所有幣都在漲，buy & hold 有 12~41%）——過濾解決的是「逆勢虧錢」，不是讓這套策略變得比持有更好。個別交易對也可能變差（例如 SSVUSDT 總報酬 12.84% → 8.28%），要看具體標的請自己跑 `backtest.py` 對照 `--trend-period 0` 與預設值。

這只是簡單的規則式判斷，不是投資建議，門檻值和週期都可以在呼叫 `generate_signal()` 時調整。KD 和費波那契回撤跟 ATR 止損一樣，需要額外傳入 `highs`/`lows` 才會計算並參與計分；沒傳就只回傳 `kd_k`/`kd_d`/`fib_level` 等欄位皆為 `None`，不影響其餘三項判斷。費波那契回撤位的抓法是簡化版（只挑近期波段高低點與單一 61.8% 位階，不分辨多重波段或畫出完整的 0/23.6/38.2/50/61.8/100% 網格），實務上這個位階常和其他訊號一起看，這裡把它當成跟 RSI/KD 同等級的單一 ±1 因子。

有做多/做空判斷時，還會算一個 ATR（Average True Range，14 期，Wilder 平滑）為基礎的止損價位：做多是「現價 − 2×ATR」，做空是「現價 + 2×ATR」——止損幅度會跟著這個交易對當下的實際波動大小走，而不是固定百分比。`generate_signal()` 需要額外傳入 `highs`/`lows`（跟 `closes`等長）才會算這個；沒傳就只回傳 `atr`/`stop_loss` 皆為 `None`，不影響原本的多空判斷。目前這個止損價位只是「算出來顯示」，`backtest.py` 的回測還沒有模擬止損觸發後提前出場的情境（見下方「下一步」）。

同樣在有方向時，另外算兩個同屬 ATR 算術的數字（觀望時三個都是 `None`）：

| 欄位 | 算法 | 意思 |
|---|---|---|
| `entry_low` / `entry_high` | 收盤 ± `atr_entry_band`×ATR（預設 0.5） | 「這支標的目前的波動下，跟訊號價差不多的範圍」 |
| `take_profit` | 收盤 ± `target_risk_reward`×（止損距離）（預設 2.0） | 讓風報比等於設定值的價位 |

**進場區間刻意涵蓋收盤價本身**，不是「等回調到某個價位再進場」。這是為了跟回測對得起來：`backtest.py` 一筆交易的定義就是「訊號當根收盤進場、下一根收盤出場」，所有勝率與平均報酬的前提都是以收盤價進場。如果改成等回撤的限價進場，回測必須一起改成模擬限價單（沒成交就不算），否則顯示的勝率會與實際做法脫節。

`take_profit` 則是純粹的比例換算——把止損距離乘上風報比，**不代表價格會走到那裡**，回測也完全沒有模擬到價出場。

價格欄位一律四捨五入到 **6 位有效數字**而非固定小數位。幣價跨了好幾個數量級（BTCUSDT 是 80889.7，CTRUSDT 是 0.010041），原本統一 `round(x, 4)` 會把後者壓成 `0.01`，誤差 0.8%，止損與風報比跟著算歪。

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
- `GET /api/symbols?market=spot|futures` — 資料庫裡有資料的交易對清單，`market` 預設 `spot`
- `GET /api/signal/{symbol}?market=` — 該交易對目前的 `generate_signal()` 結果
- `GET /api/chart/{symbol}?limit=300&market=` — 逐根 K 線的 OHLC + 指標（含 `kdK`/`kdD`/`fibLevel`/`fibSwingHigh`/`fibSwingLow`/`fibUptrend`）+ 當下（不含未來）訊號 + 止損價位，給畫圖用
- `GET /api/backtest/{symbol}?market=...` — 呼叫 `backtest()`，查詢參數對應 `--rsi-period`、`--kd-k-period`、`--fib-lookback` 等 CLI 參數
- `GET /api/advise?capital=&profit_pct=&hours=` — 跨交易對掃描：**同時掃描現貨與合約兩個市場**（同一個代號在兩邊各自算一個獨立候選，例如現貨 BTCUSDT 跟合約 BTCUSDT 可能訊號方向不同，會分開列出），本金、目標盈利 %、預計花費小時數換算成每小時所需報酬率（`requiredHourlyPct`），排序時先分兩層——「歷史上該方向的平均每小時報酬（來自 `backtest()` 的 `by_direction` 細分）有沒有達到這個目標」排前面，同樣有達到／同樣沒達到的再比訊號分數的信心度（`|score| / 5`，五項指標同向觸發的比例），最後比勝率。也就是說輸入的本金／目標盈利／小時數改變時，`requiredHourlyPct` 跟著變，兩層排序的結果也可能跟著換人——不是固定訊號分數排序、只是換個數字顯示而已。附上該方向的歷史勝率／平均報酬、以及 ATR 止損價位做參考，回傳的每個候選跟最終 `pick` 都附帶 `market` 欄位。跑過 `python main.py --all` 之後這裡可能要掃三、四百個合約交易對，一次掃描可能要幾秒鐘——見下方效能說明

啟動後可以打開 `http://localhost:8000/docs` 看自動產生的 API 文件。CORS 預設全開（`allow_origins=["*"]`），方便本機開發時用不同 port 或直接開檔案存取；正式對外提供服務前要收窄。

打開前端最簡單的方式是**直接開 <http://localhost:8000/>** ——`api.py` 會把 `frontend/` 掛在根路徑，同一個 port 同時提供 API 與頁面（根路徑會轉到 `/console.html`）。這樣前端跟 API 同源，不必依賴那個全開的 CORS，對外開隧道時也只需要一個網址。

也可以直接用瀏覽器開啟 `frontend/console.html` 檔案（或另起一個靜態伺服器），畫面上方的欄位可以改 API 位址。頁面是透過 `http(s)://` 載入時，這個欄位會自動填成當下的 origin；用 `file://` 直接開啟時則保留預設的 `http://localhost:8000`。

**但設了 `API_PASSWORD` 之後就只能走 <http://localhost:8000/>**，`file://` 那條路會卡在 `API 回應 401`。原因是頁面用 `fetch()` 取資料，而 **`fetch()` 收到 401 不會讓瀏覽器跳出登入框**——只有直接導航到那個網址才會。所以從 `file://` 開的頁面永遠拿不到憑證、也沒有地方可以輸入。從 `http://localhost:8000/` 進去則是先跳登入框、通過之後同源的 `fetch` 自動帶著憑證，一切正常。這個頁面會即時 fetch 這幾個端點，跟前面章節的腳本是同一套邏輯、同一個資料庫，不是另外寫死的展示資料。

### 對外連線（隧道）

想在外網看的話，因為 API 與頁面已經合併在同一個 port，用 `cloudflared` 開一條臨時隧道就夠：

```bash
cloudflared tunnel --url http://localhost:8000
```

它會印出一個 `https://<隨機字串>.trycloudflare.com` 網址，開那個網址就等同開本機的 `localhost:8000`（頁面與 API 都在裡面）。手機開這個網址就能用，加到主畫面後跟 app 差不多。

幾個實務上的注意事項：

- **那個行程就是隧道本身**。關掉終端機視窗、`Ctrl+C`、或電腦睡眠，網址立刻失效——它不是背景服務。要長時間開著就讓那個視窗留著，或自己包一個 launchd agent。
- **每次啟動都是不同的隨機網址**。這種不需登入的 quick tunnel 沒辦法指定名稱。想要固定網址得註冊 Cloudflare 帳號、建一條 [named tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)（免費，但要綁一個自己的域名）。
- **API 綁在 `127.0.0.1` 不影響隧道**。`cloudflared` 是從這台機器自己連 `localhost:8000`，所以不必為了對外而改成 `--host 0.0.0.0`。反過來說，如果你想要的只是「同一個 Wi-Fi 下用手機看」，那才需要改綁定並用內網 IP，而且那樣做等於把服務開放給整個區網。
- 驗證真的通了、而且防護有效：`curl -s -o /dev/null -w '%{http_code}\n' https://<你的網址>/api/symbols` 應該回 **401**（有帶 `www-authenticate` 標頭，手機瀏覽器才會跳登入框）。回 200 表示認證沒生效，別留著它對外。

**開之前先設密碼**。`api.py` 有兩道防護，都預設關閉（本機使用不用設定任何東西）：

```bash
API_PASSWORD='你自己想一個密碼' ./.venv/bin/python -m uvicorn api:app --port 8000
```

- `API_PASSWORD`：設了就對**所有**請求啟用 HTTP Basic 認證，帳號預設 `trade`（可用 `API_USER` 改）。沒設 = 完全不認證，跟以前一樣。瀏覽器開啟時會跳出登入框。
- `CORS_ORIGINS`：逗號分隔，覆蓋預設的 localhost 允許清單（預設 `http://localhost:8000,http://127.0.0.1:8000,null`，其中 `null` 是用 `file://` 開頁面時的 Origin）。前端現在同源，所以只有從 `file://` 或另一個 port 開頁面時才需要動它。

認證是寫成 middleware 而不是 FastAPI 的 app 層級 dependency——**dependency 不會套用到 `app.mount()` 掛上的 sub-application**，靜態前端會整個沒被擋（API 回 401，但頁面本身照樣 HTTP 200 吐出來）。middleware 在所有請求之前跑，`/`、`/console.html`、`/docs`、`/api/*` 都一起擋。

沒設密碼就把網址對外開的話：拿到網址的人就能讀你資料庫裡的所有交易對與訊號。存放的都是 Binance 公開行情、不含個人資料，但它畢竟是跑在你自己機器上的服務。

**Basic Auth 只是最低標**：它擋得住隨機掃描，但沒有速率限制——攻擊者可以無限次嘗試猜密碼，所以密碼的長度與隨機性就是唯一的防線（別用電話、生日、姓名這類個人資訊）。長期公開或要給別人用，把驗證交給 Cloudflare Access 這類前置服務會穩得多。

交易對分頁旁邊有個「市場別」下拉選單（現貨／合約）。現貨交易對數量少，維持原本的分頁介面；切到合約會改成一個**可輸入搜尋的交易對欄位**——因為 `python main.py --all` 抓回來的合約可能有三、四百個，全部做成分頁會直接把版面撐爆，做成下拉選單也得整串捲。這個欄位用的是原生 `<datalist>`，打幾個字就會篩出符合的代號（不分大小寫），選到清單裡不存在的代號時不會送出請求，會還原成目前圖表顯示的那個。頁面開啟時預設顯示 `BTCUSDT`（資料庫裡沒有的話才退回清單第一個——照字母序的第一個往往是 `0GUSDT` 這種冷門幣）。這個選單只影響「交易對」分頁跟下面的圖表要顯示現貨還是合約資料；**策略試算的掃描範圍不受這個選單影響**，永遠現貨＋合約都掃（見上面 `/api/advise` 的說明），下方圖表會依照建議結果本身的 `market` 自動切換，不是跟著選單走。

### 效能：為什麼要一次算完整個序列

`generate_signal()` 只回傳「最新一根」的判斷；`backtest.py` 的回測、`/api/chart` 的逐根圖表資料都需要「每一根」的判斷，走的是 `generate_signal_series()`——一次把整段序列的 RSI／MACD／布林／KD 都算好，再逐根讀值，而不是對每一根都重新從頭算一次指標。原本後者是 O(n²)（序列長度的平方），資料只有 5 個交易對時感覺不出來，但 `--all` 抓回三、四百個合約、`/api/advise` 又要對每個候選都跑一次回測時就會很明顯——例如 500 根 K 線、105 個交易對，優化前要 80 秒以上，優化後約 2 秒。前端「策略試算」的輸入框（本金／盈利／小時數）也因此改成 400ms 防抖動（debounce），不會每打一個字就送一次全市場掃描的請求。

畫面上有兩塊容易搞混、但範圍不同的區塊：
- **最新判斷**（摘要條，在交易對分頁下方）：只反映你**目前選取的分頁**（例如點 BTCUSDT 就顯示 BTCUSDT 自己的 `generate_signal()` 結果，含止損價位），切換分頁就會跟著換。
- **策略試算／建議商品**（頁面最下方）：呼叫 `/api/advise`，永遠掃描**全部**追蹤中的交易對，跟你目前點開哪個分頁無關——它可能推薦一個你根本沒在看的交易對，下面還有一張「各交易對每小時報酬率比較」圖表，把每個候選（不只是最後選中的那個）都畫出來跟目標比。

所以兩者顯示不同交易對、甚至方向相反都是正常的，不是同一件事互相矛盾。

> 這跟你可能在對話裡看到的 Claude Artifact 版「Signal Console」是兩個東西：Artifact 版本裡的資料是寫死內嵌的示範資料，而且託管在 Claude 的網頁沙盒環境裡，基於安全限制連不到你本機的 API；`frontend/console.html` 才是真正串接這支 API 的版本，但只能在你本機（或你部署 API 的地方）打開才會有資料。

## Docker

也可以用 Docker 跑 API＋資料庫，不用自己裝 Python 或 PostgreSQL。

```bash
docker compose up --build
```

`docker-compose.yml` 有三個服務：
- `db`：官方 `postgres:16-alpine`，資料存在具名 volume（`db-data`），容器重建或重啟資料不會不見；也對外開了 `5432` port，本機工具（例如 `psql`）要直接連也可以
- `api`：這個專案的 FastAPI 服務，`DATABASE_URL` 環境變數已經指向 `db` 服務（`postgresql://trade:trade@db:5432/trade_signal`），`depends_on` 設定會等 `db` 通過健康檢查（`pg_isready`）才啟動
- `scheduler`：跟 `api` 同一個 image，不開 port，啟動後就跑 `while true; do python main.py; sleep 900; done`——等同內建每 15 分鐘一次的 cron，不用另外在主機上設定排程。單次 `main.py` 失敗（連不上 Binance、限流等）不會讓這個迴圈停下來，下一輪還是會照跑；不加參數預設抓**全部合約**（約三、四百個，每輪跑下來大約數十秒），跟 README 前面「排程抓取」章節的 cron 範例做一樣的事。只想抓現貨那幾個交易對的話，把 `docker-compose.yml` 裡 `scheduler` 的 `command` 改成 `python main.py --symbols BTCUSDT ETHUSDT` 之類即可

啟動後 API 就在 `http://localhost:8000`。之後打開 `frontend/console.html` 一樣把 API 位址指向 `http://localhost:8000` 即可，前端本身不跑在容器裡，還是直接用瀏覽器開檔案。

不想要自動排程抓取（例如只是想手動測試），可以只啟動 `db` 跟 `api`：`docker compose up --build db api`。

抓資料／跑分析／回測這些一次性指令用同一個 image 執行即可，例如：

```bash
docker compose run --rm api python main.py --symbols BTCUSDT ETHUSDT
docker compose run --rm api python main.py --all
docker compose run --rm api python analyze.py BTCUSDT
docker compose run --rm api python backtest.py BTCUSDT
```

`Dockerfile` 只是標準的 `python:3.12-slim` + `pip install -r requirements.txt` + `uvicorn` 起服務，沒有特殊技巧；`.dockerignore` 排除了 `.git/`、`frontend/`（不需要在容器裡）等。

只想跑資料庫、Python 直接在本機執行（不透過 Docker 跑 API）也可以，只啟動 `db` 這個服務即可：

```bash
docker compose up -d db
DATABASE_URL=postgresql://trade:trade@localhost:5432/trade_signal python main.py
```

## 下一步（尚未實作）

- 更完整的持倉邏輯（訊號翻轉才換邊，而非每根重新進出場），並讓 `backtest.py` 真正模擬「觸發止損價位就提前出場」，而不是只顯示止損價位
- 交易成本／滑價模擬
- 均線交叉等更多指標
