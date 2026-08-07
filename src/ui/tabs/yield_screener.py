"""src/ui/tabs/yield_screener.py — 7% 高殖利率防禦網（漏斗篩選器 / Screener Mode）

資料來源：
  ① 全市場本益比 + 殖利率 + 股價淨值比：TWSE OpenAPI BWIBBU_d ＋ TPEX peratio_analysis
     → **已下沉 L1**：`src/data/stock/yield_pe_fetcher.py`（E2,2026-08）
  ② 單檔配息歷史：yfinance Ticker.dividends（僅在用戶選定後觸發）

架構：
  • 全部走既有 proxy_helper.fetch_url() → NAS Squid Proxy（自動降級直連）
  • @st.cache_data(ttl=TTL_1DAY) 一日快取，減少對 NAS 中繼站的負擔（在 L1 模組內）
  • max_retries / timeout / 防迴圈：fetch_url 內建 3 次重試 + 20s timeout + Storm Shield 快取

本檔現況：估值 fetcher 下沉 L1 後，只剩 re-export ＋ `_proxy_status_badge()` HTML 徽章。
"""
from __future__ import annotations
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

# ══════════════════════════════════════════════════════════════════════════════
# ① / ①-b 全市場估值 fetcher — E2(2026-08)已整組下沉 L1,此處僅 re-export
# ══════════════════════════════════════════════════════════════════════════════
# 搬遷理由(解 C3-d):這三個函式是 L1 fetcher,卻住在 L5 UI Tab,而本檔 module-level
# 無條件 `import streamlit as st` —— 兩支 headless cron
# (scripts/push_daily_signals.py、scripts/update_forward_test_freeze.py)走這條
# import 會把整個 streamlit UI 鏈拉進 cron。後者是每月凍結**前進式驗證**的那支,
# import 鏈一斷紀錄就靜默停止更新(§1)。實作 + 完整 docstring 見 L1 模組。
#
# §8.2.A EX-PASSTHRU-1:本檔(L5)直 import L1 fetcher —— pass-through 取數,
# 無多源 fallback / 無跨 fetcher TTL 統一 / 無結果後處理,且 L1 內已自帶
# @st.cache_data(EX-CACHE-1)集中緩存,加 L3 wrapper 只是 §8.1 step 6 的
# 「用不到的抽象」。已登記於 tests/test_c3_layering_guard.py `_WHITELIST`。
#
# ⚠️ 測試請 patch **L1 模組**(`src.data.stock.yield_pe_fetcher.*`)。
#    patch 本檔的 re-export 只改別名綁定,打不到 `fetch_pe_name_maps` 的內部呼叫。
from src.data.stock.yield_pe_fetcher import (  # noqa: F401
    TPEX_PERATIO_URL,
    TWSE_BWIBBU_URL,
    fetch_pe_name_maps,
    fetch_tpex_yield_pe,
    fetch_twse_yield_pe,
)


# ══════════════════════════════════════════════════════════════════════════════
# ② 單檔配息歷史 — yfinance Ticker.dividends（透過 NAS proxy）
# ══════════════════════════════════════════════════════════════════════════════
# P1-1b v18.375:fetch_dividend_history 整檔搬至 src/data/stock/dividend_fetcher.py(L1)
# 此處改 backward-compat re-export(走 lazy import,caller 介面不變)
# v18.406 R5:走 L3 wrapper
from src.services.yield_screener_service import get_annual_dividends as fetch_dividend_history  # noqa: F401


# ══════════════════════════════════════════════════════════════════════════════
# ③ 連線狀態檢查 — 顯示 NAS Proxy 是否啟用
# ══════════════════════════════════════════════════════════════════════════════
def _proxy_status_badge() -> str:
    """回傳 HTML badge 顯示 NAS 中繼站狀態（不實際發送請求，僅看 secrets）。"""
    try:
        # v18.406 R5:走 L3 wrapper
        from src.services.yield_screener_service import get_proxy_status_config
        _p = get_proxy_status_config()
        if _p:
            return (f'<span style="background:#0a2818;color:{TRAFFIC_GREEN};padding:3px 10px;'
                    'border-radius:6px;font-size:11px;font-weight:700;">'
                    '🟢 NAS 中繼站 已啟用</span>')
        return (f'<span style="background:#1f0d0d;color:{TRAFFIC_RED};padding:3px 10px;'
                'border-radius:6px;font-size:11px;font-weight:700;">'
                '🔴 NAS 中繼站 未設定（直連模式）</span>')
    except Exception:
        return (f'<span style="background:#2a1f00;color:{TRAFFIC_YELLOW};padding:3px 10px;'
                'border-radius:6px;font-size:11px;font-weight:700;">'
                '🟡 Proxy 狀態未知</span>')


# ══════════════════════════════════════════════════════════════════════════════
# ④ 主畫面渲染
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# ⑤ 殖利率確認 — 倒序選股流程第二步（S1/S2 通過後呼叫）
# ══════════════════════════════════════════════════════════════════════════════
