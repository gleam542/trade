# trade

加密貨幣訊號系統：抓 Binance K 線存進 PostgreSQL，算技術指標、產生多空訊號、回測，並提供 HTTP API 與網頁介面。

程式與說明都在 **[`trade-signal/`](trade-signal/)** —— 見 [trade-signal/README.md](trade-signal/README.md)。

```bash
cd trade-signal
pip install -r requirements.txt
python main.py                                  # 抓資料
python -m uvicorn api:app --port 8000           # API + 網頁介面
```

然後開 <http://localhost:8000/>。
