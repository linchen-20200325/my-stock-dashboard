"""v18.236 快取 TTL SSOT — `@st.cache_data(ttl=N)` 秒數常數集中地。

63 處 `ttl=N` 散落 20 檔，集中為 7 個語意常數（依時間長度命名）。
data_config.py 的 `TTL_CONFIG` dict 改成 import 重組，確保單一來源。

設計：純常數模組，零 import 依賴；caller 用
`from shared.ttls import TTL_30MIN, TTL_1HOUR, TTL_1DAY`。

對外 API：
- TTL_10MIN   = 600       台股總經月頻指標(tw_macro 7 處 fetcher;v18.402 D3 新增)
- TTL_15MIN   = 900       盤中重算（etf_calc 風險指標 / 折溢價）
- TTL_30MIN   = 1800      法人/融資/PCR/期貨 OI（leading_indicators 主流）
- TTL_1HOUR   = 3600      行情/財報/基本面（app / etf_fetch / data_loader 主流）
- TTL_2HOUR   = 7200      NAV 歷史（etf_fetch）
- TTL_6HOUR   = 21600     月營收篩選（monthly_revenue_screener / exit_signals）
- TTL_1DAY    = 86400     靜態日頻（持股 / 評等 / 績效 / 配息歷史）
- TTL_3DAY    = 259200    台股月營收原始抓取（tw_stock_data_fetcher）
- TTL_7DAY    = 604800    超靜態（經理人 / 中文名稱）

來源：v18.230 P0 audit 列為 SSOT #1 違規；data_config.py:17-23 已有 partial dict
但僅 daily_checklist 2 處引用，其餘 60+ 處仍 hardcode 數字。
"""
from __future__ import annotations

TTL_10MIN: int = 600      # 10 分鐘 — tw_macro 7 處 fetcher(v18.402 D3 新增 SSOT)
TTL_15MIN: int = 900      # 15 分鐘 — 盤中高頻重算
TTL_30MIN: int = 1800     # 30 分鐘 — 法人/融資/期貨/PCR
TTL_1HOUR: int = 3600     # 1 小時 — 行情/財報/基本面主流
TTL_2HOUR: int = 7200     # 2 小時 — NAV 歷史
TTL_6HOUR: int = 21600    # 6 小時 — 月營收篩選
TTL_1DAY: int = 86400     # 1 天 — 靜態日頻資料
TTL_3DAY: int = 86400 * 3  # 3 天 — 台股月營收原始抓取
TTL_7DAY: int = 86400 * 7  # 7 天 — 超靜態元資料
