"""src/ui/tabs/yield_screener.py — 7% 高殖利率防禦網（漏斗篩選器 / Screener Mode）

資料來源：
  ① 全市場本益比 + 殖利率 + 股價淨值比：TWSE OpenAPI BWIBBU_d（單次抓全市場）
  ② 單檔配息歷史：yfinance Ticker.dividends（僅在用戶選定後觸發）

架構：
  • 全部走既有 proxy_helper.fetch_url() → NAS Squid Proxy（自動降級直連）
  • @st.cache_data(ttl=TTL_1DAY) 一日快取，減少對 NAS 中繼站的負擔
  • Slider 動態篩選：最低殖利率(%) + 最高本益比
  • max_retries / timeout / 防迴圈：fetch_url 內建 3 次重試 + 20s timeout + Storm Shield 快取
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.ttls import TTL_1DAY

TWSE_BWIBBU_URL = 'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d'


# ══════════════════════════════════════════════════════════════════════════════
# ① 全市場 — TWSE BWIBBU_d 單次抓取
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_twse_yield_pe() -> pd.DataFrame:
    """從 TWSE OpenAPI 一次取得全市場本益比 / 殖利率 / 股價淨值比。

    Returns:
        DataFrame with columns: 代碼 / 名稱 / 本益比 / 殖利率(%) / 股價淨值比
        失敗回傳空 DataFrame（呼叫端用 .empty 檢查）
    """
    # v18.406 R5:L3 wrapper(EX-PASSTHRU-1 Group A 升級)
    from src.services.yield_screener_service import proxy_fetch_url
    try:
        _resp = proxy_fetch_url(TWSE_BWIBBU_URL, timeout=15)
        if _resp is None or getattr(_resp, 'status_code', 0) != 200:
            print('[yield_screener] TWSE BWIBBU 回傳非 200 或 None')
            return pd.DataFrame()
        _data = _resp.json()
        if not isinstance(_data, list) or not _data:
            print('[yield_screener] TWSE BWIBBU 回傳格式異常')
            return pd.DataFrame()
        _df = pd.DataFrame(_data).rename(columns={
            'Code':          '代碼',
            'Name':          '名稱',
            'PEratio':       '本益比',
            'DividendYield': '殖利率(%)',
            'PBratio':       '股價淨值比',
        })
        for _c in ['本益比', '殖利率(%)', '股價淨值比']:
            if _c in _df.columns:
                _df[_c] = pd.to_numeric(_df[_c], errors='coerce')
        _result = _df.dropna(subset=['殖利率(%)']).reset_index(drop=True)
        # v18.356 PR-Q5b S-PROV-1 phase 19:DataFrame 走 attrs
        try:
            _result.attrs.setdefault('source', 'TWSE:OpenAPI:BWIBBU_d')
            _result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _result
    except Exception as _e:
        print(f'[yield_screener] TWSE BWIBBU 解析失敗：{_e}')
        return pd.DataFrame()


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
