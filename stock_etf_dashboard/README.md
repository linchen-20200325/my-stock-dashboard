# 📈 Stock & ETF 智慧投資儀表板

獨立、可單獨執行的量化投資儀表板，嚴格遵循 4 層 Clean Architecture 與資料完整性憲法
（Fail Loud, Never Fake）。與主專案 `src/` 物理隔離，不共用程式碼。

## 快速開始

```bash
pip install -r stock_etf_dashboard/requirements.txt
streamlit run stock_etf_dashboard/app.py       # 啟動 UI（記憶體模式即開即用）
python -m pytest stock_etf_dashboard/tests -q   # 43 項單元/邊界測試
```

## 分層架構（依賴單向向下）

```
L3 UI          app.py                    頂部風控列 + 左右雙池 + 側欄行動中心
L2/L3 Services  services/                純運算 + 編排
   ├ stock_scoring_engine.py             PE/PB 河流圖位階 + MA20/60 + MACD + 籌碼同步
   ├ etf_overlap_calc.py                 ETF 成分穿透 + 去重複計數 + >30% 集中度警戒
   ├ exposure_service.py                 讀持股→抓 ETF 成分→穿透（依賴注入,離線可測）
   └ pool_state_service.py               觀察池↔持股 單向狀態機 + 出場訊號
L1 Repositories repositories/            外部資料,出口過 schema + 血緣
   ├ market_repo.py                      yfinance OHLCV / 配息 / 估值序列 / 最新收盤
   ├ etf_repo.py                         ETF 成分兩源：yfinance funds_data → 台灣 Yahoo
   │                                       /holding（優先抓代號對齊；小數→%；全敗 fail-loud）
   ├ chip_repo.py                        TWSE T86 三大法人（股→張）
   └ sheets_repo.py                      Google Sheets（PoolStore 介面 + 記憶體後端）
L0 Infra        core/                     被全層 import,禁依賴上層
   ├ constants.py                        所有門檻 SSOT（§3.3 無 inline magic number）
   ├ schemas.py                          Pandera 出口驗證（壞值回空殼,不放行）
   ├ circuit_breaker.py                  置信度 0~100 + 除權息還原防呆 + Fail Loud
   ├ provenance.py                       血緣（source / fetched_at / as_of）
   └ line_dispatcher.py                  LINE 推播
```

## 存儲：Google Sheets 實體隔離

| worksheet | 用途 | 欄位 |
|---|---|---|
| `stock_watchlist` | 觀察池（純代碼無價） | ticker, name, note, updated_at |
| `stock_portfolio` | 持股庫存 | ticker, name, lots, avg_price, trailing_stop_pct, take_profit_pct, updated_at |
| `stock_ledgers` | 交易帳本（append-only） | ts, ticker, action, lots, price, reason |

`.streamlit/secrets.toml`（部署端才需要，本機記憶體模式免設定）：
```toml
[gsheets]
sheet_id = "你的_spreadsheet_key"
[gsheets.service_account]      # gspread service account JSON 內容
type = "service_account"
# ...
```
LINE 推播需環境變數 `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`。

## 核心設計原則

- **Fail Loud**：缺料/壞假設一律 `raise FailLoudError`，不 `fillna(0)`、不吞例外、不回假資料。
- **置信度鎖定**：資料齊全度×新鮮度×來源可靠度 < 70 → 鎖定，不給操作建議。
- **除權息防呆**：除息開低跳空自動還原參考價，避免誤觸移動停損。
- **穿透去重複計數**：直接持 2330 + 0050 內含 2330 → 合併到同一底層曝險；成分抓不到
  → 標「下限」而非補 0。UI「🔓 從我的持股自動穿透」讀持股組合 → yfinance 抓 ETF 成分
  （`etf_repo.fetch_etf_holdings`）→ 逐檔算市值穿透；無現價的標的跳過並回報,不捏造市值。
- **單向狀態機**：買入只能從觀察池、賣出只能從持股；每次轉移寫帳本。
