@echo off
chcp 65001 >nul
cd /d E:\01.Github\my-stock-dashboard
echo === 準備 commit v18.455 + v18.456 ===
git add src/data/etf/etf_fetch.py src/data/core/data_loader.py src/compute/health/mj_trend_score.py STATE.md
git commit -m "fix(mj): bootstrap 上季快照 + fix(etf): fetch_etf_zh_name attempts=1->2

v18.455: fetch_etf_zh_name attempts=1->2 修正 proxy 403 不降級直連 bug
v18.456: fetch_financial_statements 加 prev_period_data, mj_trend bootstrap
  - fetch_financial_statements 回傳 prev_period_data (730天資料已含上季)
  - compute_one_stock_trend 保存本季後自動 bootstrap 上季快照
  - Streamlit Cloud 重啟後仍能湊足 2 季 delta，mj_trend 不再恆為 0"
echo === 推送到 GitHub ===
git push
echo === 完成 ===
pause
