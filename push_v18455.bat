@echo off
chcp 65001 >nul
cd /d E:\01.Github\my-stock-dashboard
echo === 準備 commit v18.455 ===
git add src/data/etf/etf_fetch.py STATE.md
git commit -m "fix(etf): fetch_etf_zh_name attempts=1->2 修正 proxy 403 不降級直連 bug"
echo === 推送到 GitHub ===
git push
echo === 完成 ===
pause
