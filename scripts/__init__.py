"""scripts/ — v18.359 Phase 2 F-2 / F-6 維運與 CLI 腳本聚合。

本 __init__.py 為 package marker,讓 tests/ 可用 `from scripts.X import Y`
取得各 CLI module 公開 API。

成員:
  calibrate_macro_traffic — 巨觀信號歷史校準(GitHub Actions cron)
  update_macro_history    — 歷史總經資料補填(GitHub Actions cron)
  update_etf_managers     — ETF 經理人清單一次性更新
  final_check             — 部署前驗證
  debug_financials        — 財務資料除錯
  test_fetch / test_fetchers / test_registry — 離線 print-CLI 驗證(非 pytest)
"""
