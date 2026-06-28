"""src/ui/tabs/macro/handlers.py — tab_macro 4 個 inner def(F-7.1 B-1 抽出)。

無 closure 依賴(全部用 st.session_state + 顯式參數):
- _macro_session_reset:scoped session_state pop
- _on_refresh_click / _on_force_clear_click:streamlit button on_click handler
- _render_traffic_light(placeholder, tl, mkt_info):紅綠燈卡 placeholder 回填
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_RED, TRAFFIC_YELLOW


def _macro_session_reset():
    """pop 總經相關 session_state keys（scoped）。

    v18.329：**只清總經自己的 session_state**，不碰其他 tab 的 @st.cache_data
    快取。正常更新走此路徑＝吃既有 TTL 暖快取，秒級且不拖累個股 / ETF / 健診頁。
    """
    for _k in ('cl_data', 'cl_ts', 'mkt_info', 'jingqi_info', 'li_latest',
               'warroom_summary', '_last_inst', '_last_inst_date',
               '_last_margin', 'futures_net', 'adl_debug_msg'):
        st.session_state.pop(_k, None)
    st.session_state['_is_refreshing'] = True


def _on_refresh_click():
    """正常更新 on_click：只清總經 session_state，吃既有 @st.cache_data TTL 暖快取。

    v18.329：移除原本的全站 `st.cache_data.clear()`（會炸掉個股 / ETF / 健診的
    快取，導致每次更新總經後全站都要冷啟重抓 → 又慢又奇怪）。要零殘留改用下方
    『🆕 強制重抓』。對齊 Fund `clear_tab1_macro_caches` 的 scoped 行為。
    """
    _macro_session_reset()


def _on_force_clear_click():
    """強制重抓 on_click：全清 pkl + st.cache_data + proxy URL cache + 總經 session_state。"""
    try:
        from src.services import _pkl_clear_all
        _pkl_clear_all()
    except Exception as _e_clr:
        print(f'[Cache] pkl clear failed: {_e_clr}')
    try:
        st.cache_data.clear()
        print('[Cache] 🗑️ st.cache_data cleared (force)')
    except Exception as _e_sc:
        print(f'[Cache] st.cache_data clear failed: {_e_sc}')
    try:
        from src.data.proxy import proxy_helper as _ph_clr
        _ph_clr._URL_CACHE.clear()
        _ph_clr.reset_proxy_cache()
        print('[Cache] 🗑️ proxy URL cache + config cache cleared (force)')
    except Exception as _e_ph:
        print(f'[Cache] proxy clear failed: {_e_ph}')
    _macro_session_reset()
    print('[Cache] 🗑️ 強制重抓：全快取清除完成')


def _render_traffic_light(placeholder, tl, mkt_info=None):
    """將計算結果回填到 placeholder（或顯示等待狀態）。
    mkt_info: 選填，來自 market_regime() 的原始 dict，用以合併顯示市場評分與信號。
    以較保守信號為主（traffic light 已含 defense/health 降級邏輯）。

    信心門檻：conf < 70% 時不顯示燈號，改列出缺失資料避免誤導決策。
    """
    if tl is None:
        placeholder.info(
            '⏳ **系統正在深度解析大盤與籌碼數據，請稍候...**\n\n'
            '首次使用請點擊「🚀 一鍵更新全部數據」載入資料。',
            icon='📡'
        )
        return

    # ── 信心門檻 gating：conf<70% 直接擋燈號，逐項列出缺失資料 ──
    if tl.get('conf', 0) < 70:
        _missing = tl.get('missing_sources', []) or []
        _missing_lines = ''.join(
            f'<li style="margin:4px 0;color:{TRAFFIC_RED};">❌ {m}</li>' for m in _missing
        ) if _missing else '<li style="color:#8b949e;">（無法判斷）</li>'
        with placeholder.container():
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#2a1d00,#1a1208);'
                f'border:2px solid {TRAFFIC_YELLOW};border-radius:14px;padding:18px 22px;margin-bottom:12px;">'
                f'<div style="font-size:22px;font-weight:900;color:{TRAFFIC_YELLOW};">⏸️ 資料不足，無法判斷市場狀態</div>'
                f'<div style="font-size:13px;color:#c9d1d9;margin-top:8px;">'
                f'目前數據信心 <b style="color:{TRAFFIC_RED};">{tl["conf"]}%</b>'
                f'（門檻 70%，避免新舊資料混雜誤導決策）</div>'
                f'<div style="font-size:12px;color:#8b949e;margin-top:10px;">缺少以下資料來源：</div>'
                f'<ul style="font-size:13px;margin:6px 0 0 4px;padding-left:20px;">{_missing_lines}</ul>'
                f'<div style="font-size:12px;color:#58a6ff;margin-top:12px;">'
                f'👉 請點上方「🚀 一鍵更新全部數據」載入完整資料後，燈號才會顯示。'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        return

    # ── 整合 market_regime() 的輔助資訊 ──────────────────────
    _mi      = mkt_info or {}
    _mi_score  = _mi.get('score')
    _mi_mx     = _mi.get('max_score', 4)
    _mi_idx    = _mi.get('index_price', 0)
    _mi_exp    = _mi.get('exposure_pct', '--')
    _mi_sigs   = _mi.get('signals', [])
    _mi_upd    = st.session_state.get('cl_ts', '')

    _sigs_html = ''.join(
        f'<span style="background:#21262d;border-radius:5px;padding:2px 7px;'
        f'font-size:11px;color:#c9d1d9;margin-right:4px;">{s}</span>'
        for s in _mi_sigs
    )
    _meta_line = ''
    if _mi_score is not None:
        _meta_line = (
            f'<div style="display:flex;flex-wrap:wrap;gap:14px;margin-top:8px;">'
            f'<span style="font-size:12px;color:#8b949e;">評分 '
            f'<b style="color:{tl["color"]};">{_mi_score}/{_mi_mx}</b></span>'
            f'<span style="font-size:12px;color:#8b949e;">加權指數 '
            f'<b style="color:#e6edf3;">{_mi_idx:,.0f}</b></span>'
            f'<span style="font-size:12px;color:#8b949e;">建議持股 '
            f'<b style="color:{tl["color"]};">{_mi_exp}</b></span>'
            + (f'<span style="font-size:11px;color:#484f58;">更新 {_mi_upd}</span>'
               if _mi_upd else '')
            + '</div>'
        )

    with placeholder.container():
        # ── 合併看板主體 ────────────────────────────────────
        st.markdown(f'''<div style="background:linear-gradient(135deg,#0a1628,#0d1f3c);
border:3px solid {tl["color"]};border-radius:16px;padding:20px 24px;margin-bottom:12px;">
<div style="display:flex;align-items:flex-start;gap:16px;">
  <div style="font-size:56px;line-height:1;flex-shrink:0;">{tl["icon"]}</div>
  <div style="flex:1;min-width:0;">
<div style="font-size:24px;font-weight:900;color:{tl["color"]};">{tl["label"]}</div>
<div style="font-size:15px;color:#c9d1d9;margin-top:4px;">{tl["action"]}</div>
<div style="font-size:12px;color:#8b949e;margin-top:2px;">{tl["sub"]}</div>
{f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;">{_sigs_html}</div>' if _sigs_html else ''}
{_meta_line}
  </div>
  <div style="text-align:right;flex-shrink:0;">
<div style="font-size:12px;color:#484f58;">綜合健康度</div>
<div style="font-size:36px;font-weight:900;color:{tl["color"]};">{tl["health"]:.0f}</div>
<div style="font-size:11px;color:#484f58;">/ 100分｜信心{tl["conf"]}%</div>
<div style="font-size:10px;color:#6e7681;margin-top:3px;max-width:170px;line-height:1.3;">📊 台股籌碼 / 技術面<br>（全球美股面看下方各桶）</div>
  </div>
</div></div>''', unsafe_allow_html=True)

        # ── 數據信心提示 ────────────────────────────────────
        if tl['conf'] < 80:
            st.warning(f'⚠️ 數據信心指數 {tl["conf"]}%，部分資料缺失，建議更新後再操作')


