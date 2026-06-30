"""src/ui/tabs/stock_grp_sections/section_market_status.py — ① 市場狀態快覽
(v18.413 Batch 7-1).

從 tab_stock_grp.py:85-141 抽出。
- 🚦 大盤燈號(warroom_summary['traffic_light'])
- 📈 台股大盤(cl_data.tw.台股加權指數 → daily 漲跌幅)
- 💼 建議持股(mkt_info.exposure_pct)

§8.2 layer:L5 UI Tab section helper(🟢 低風險:57 LOC,純展示 + 3 KPI 卡)。

對外 API:
- render_market_status_section() -> None
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW


def render_market_status_section() -> None:
    """① 市場狀態快覽 — 3 KPI 卡(大盤燈號 / 台股大盤 / 建議持股)。

    改為總是渲染 3 張卡,無資料時顯示「未載入」中性 placeholder
    (不再強制要求先跑總經 Tab)。
    """
    _t3_mkt = st.session_state.get('mkt_info', {}) or {}
    _t3_tl  = st.session_state.get('warroom_summary', {}) or {}

    _t3c1, _t3c2, _t3c3 = st.columns(3)
    with _t3c1:
        _tl_label = _t3_tl.get('traffic_light') or '未載入'
        _tl_color = (TRAFFIC_GREEN if '綠' in _tl_label else
                     TRAFFIC_YELLOW if '黃' in _tl_label else
                     TRAFFIC_RED if '紅' in _tl_label else '#484f58')
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid {_tl_color}33;border-radius:8px;'
            f'padding:10px 14px;text-align:center;">'
            f'<div style="font-size:11px;color:#8b949e;">🚦 大盤燈號</div>'
            f'<div style="font-size:16px;font-weight:900;color:{_tl_color};">{_tl_label}</div>'
            f'</div>', unsafe_allow_html=True)
    with _t3c2:
        # 修正:台股加權指數真實在 cl_data['tw'],而非 mkt_info;舊路徑永遠 None
        _t3_cl = st.session_state.get('cl_data', {}) or {}
        _twii_df = (_t3_cl.get('tw', {}) or {}).get('台股加權指數')
        _twii_pct = None
        if _twii_df is not None and hasattr(_twii_df, 'empty') and not _twii_df.empty:
            _close_col = 'close' if 'close' in _twii_df.columns else (
                'Close' if 'Close' in _twii_df.columns else None)
            if _close_col and len(_twii_df) >= 2:
                try:
                    _c_now  = float(_twii_df[_close_col].iloc[-1])
                    _c_prev = float(_twii_df[_close_col].iloc[-2])
                    if _c_prev > 0:
                        _twii_pct = (_c_now / _c_prev - 1.0) * 100.0
                except (ValueError, TypeError):
                    pass
        if _twii_pct is not None:
            _twii_c = '#da3633' if _twii_pct > 0 else '#2ea043'
            _twii_val = f'{_twii_pct:+.2f}%'
        else:
            _twii_c, _twii_val = '#484f58', '未載入'
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
            f'padding:10px 14px;text-align:center;">'
            f'<div style="font-size:11px;color:#8b949e;">📈 台股大盤</div>'
            f'<div style="font-size:16px;font-weight:900;color:{_twii_c};">{_twii_val}</div>'
            f'</div>', unsafe_allow_html=True)
    with _t3c3:
        # 修正:warroom_summary 從未寫入 hold_pct;改讀 mkt_info.exposure_pct ('80%' 字串)
        _t3_hold = _t3_mkt.get('exposure_pct') if _t3_mkt else None
        _hold_val = str(_t3_hold) if _t3_hold not in (None, '', '--') else '未載入'
        _hold_c = '#58a6ff' if _t3_hold not in (None, '', '--') else '#484f58'
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
            f'padding:10px 14px;text-align:center;">'
            f'<div style="font-size:11px;color:#8b949e;">💼 建議持股</div>'
            f'<div style="font-size:16px;font-weight:900;color:{_hold_c};">{_hold_val}</div>'
            f'</div>', unsafe_allow_html=True)
    st.markdown('')
