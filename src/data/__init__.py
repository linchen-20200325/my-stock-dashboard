"""src/data/ — L1 資料層聚合(v18.360 Phase 2 F-6.2)。

7 個子目錄按職責分類:
  core/       data_loader, data_registry      (核心 fetcher)
  macro/      macro_core, tw_macro, leading_indicators, macro_alert
  stock/      tw_stock_data_fetcher            (TW 個股)
  etf/        etf_fetch                        (ETF)
  daily/      daily_data_fetchers              (日間快照)
  portfolio/  gsheet_portfolio                 (Google Sheets)
  proxy/      proxy_helper, nas_server, yf_proxy  (代理層)

本 __init__.py 故意留空,避免循環 import。caller 從子目錄取數:
  from src.data.core import StockDataLoader
  from src.data.macro import fetch_fred
"""
