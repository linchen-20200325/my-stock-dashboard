@echo off
chcp 65001 >nul
cd /d E:\01.Github\my-stock-dashboard
echo === 準備 commit v18.458 ===
git add src/ui/tabs/stock_sections/section_financial_leading.py
git add src/ui/tabs/tab_stock.py
git add src/data/news/news_fetcher.py
git add src/ui/tabs/tab_edu.py
git add src/data/core/data_registry.py
git add STATE.md
git commit -m "fix: financial_leading capex label + stale Reuters description strings (v18.458)

1. section_financial_leading.py: use CF capex over PP&E for display
   - Add capex=None kw-only param; prioritize '季資本支出' over '固定資產/資本支出'
   - Fixes same root cause as dragon_alert (v18.457): PP&E != capex
   - tab_stock.py: pass capex=_capex2 to render_financial_leading_section

2. Stale Reuters description strings cleanup (v18.457 removed feed but missed these):
   - news_fetcher.py: docstring still listed 'Reuters Biz' — updated
   - tab_edu.py: description string still listed 'Reuters' — updated
   - data_registry.py: Reuters registry entry commented out (dead since 2020)"
echo === 推送到 GitHub ===
git push
echo === 完成 ===
pause
