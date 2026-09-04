# trade

這個 repo 裝了兩個各自獨立的專案。

## `trade-signal/` — 加密貨幣訊號系統

抓 Binance K 線存進 PostgreSQL，算技術指標、產生多空訊號、回測，並提供 HTTP API 與網頁介面。目前開發中的部分幾乎都在這裡。

詳細說明見 [trade-signal/README.md](trade-signal/README.md)。

## 根目錄 — Aura 電商前端（React + Vite）

一個購物網站的靜態展示（Hero / 商品列表 / 購物車 / 結帳 / Journal），沒有後端，商品資料寫在 `constants.ts` 裡。

```bash
npm install
npm run dev
```

預設跑在 <http://localhost:3000>。
