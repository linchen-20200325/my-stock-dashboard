@echo off
chcp 65001 >nul
cd /d E:\01.Github\my-stock-dashboard
echo === 準備 commit v18.455 + v18.456 + v18.457 ===
git add src/data/etf/etf_fetch.py
git add src/data/core/data_loader.py
git add src/compute/health/mj_trend_score.py
git add src/ui/tabs/tab_stock.py
git add src/ui/tabs/stock_sections/section_dragon_alert.py
git add src/data/news/news_fetcher.py
git add STATE.md
git commit -m "fix: t2_inst missing + Reuters RSS dead + dragon capex fix + MJ bootstrap + ETF zh_name

v18.455: fetch_etf_zh_name attempts=1->2, proxy 403 fallback bug fix
v18.456: fetch_financial_statements adds prev_period_data; mj_trend bootstrap
  - 730-day FinMind call already has prev quarter; use it to bootstrap 2nd snapshot
  - Fixes mj_trend always = 0 after Streamlit Cloud restart
v18.457: 4 fixes
  - Task#18: write t2_inst from df2 (外資/投信 cols) before sections render
    Fixes: K-line narrative always shows 外資中性; v4 chip foreign_net always 0
  - Task#19: remove dead Reuters RSS (feeds.reuters.com dead since June 2020)
  - Task#20: dragon alert uses CF capex (quarterly flow) not PP&E stock (BS)
    PP&E for mfg companies >> capital, causing false dragon signals
    _capex2 now saved to t2_data['capex'] and passed to section
  - Task#21: (Fund) APP_VERSION v19.45 -> v19.293 (separate fund commit)"
echo === 推送到 GitHub ===
git push
echo === 完成 ===
pause
