"""src/ui/tabs/macro/section_traffic_light.py — 紅綠燈決策儀表板(P3-D9 v18.391 抽出)。

原 tab_macro.py:170-235 inline(【模組一】紅綠燈卡 + warroom_summary write)。

跨 page state(critical):本檔寫 `st.session_state['warroom_summary']` 8 keys,
被 tab_stock_grp / section_inputs / macro_helpers / macro/helpers / section_state
5 個檔案讀取。

placeholder lifecycle:`_tl_placeholder = st.empty()` 物件由 caller 沿用 ——
後續 `_tl_placeholder.empty()` (refresh 時清空)+ `render_section_state(...,
_tl_placeholder, ...)` (B-S2)都需要。跨 def 傳 placeholder 已在 B-S2 證實
可行,不是反模式。

closure params:無(全部從 st.session_state 讀)

回傳 tuple (3 件):
- placeholder: st.empty 物件(caller 後續 .empty()/.markdown 用)
- show_market_data: bool(下游所有 section gate)
- tl_eff_reg: str | None('bull'/'neutral'/'bear';§九 / 戰情 / 作戰 共用)
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

import streamlit as st

from shared.position_throttle import compute_position_throttle
from src.compute.macro import calc_traffic_light
from src.ui.tabs.macro.handlers import _render_traffic_light

# 油門帶顏色(對齊姿態 icon)
_THROTTLE_COLORS = {'🟢': '#26a641', '🟡': '#d29922', '🟠': '#db6d28', '🔴': '#da3633'}


def render_position_throttle(tl) -> None:
    """總經『建議持股油門』儀表(v19.62)——姿態油門,非進出開關。

    tl: calc_traffic_light / compute_macro_health 輸出(含 health/regime/defense)。
    無 health → 靜默略過(不炸)。
    """
    if not isinstance(tl, dict) or tl.get('health') is None:
        return
    _health = float(tl.get('health'))
    _thr = compute_position_throttle(
        _health, regime=tl.get('regime'), defense=bool(tl.get('defense')))
    _c = _THROTTLE_COLORS.get(_thr['icon'], '#8b949e')
    _lo, _hi, _mid = _thr['lo_pct'], _thr['hi_pct'], _thr['mid_pct']
    _veto = ('&nbsp;<span style="color:#da3633;">（⚠️ 總經否決：無視技術面多頭，'
             '強制壓低上界）</span>' if _thr['regime_capped'] else '')
    st.markdown(
        f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
        f'padding:10px 14px;margin:6px 0 2px;">'
        f'<b>🎚️ 建議持股油門</b>&nbsp; {_thr["icon"]} <b>{_thr["posture"]}</b>'
        f'&nbsp;→ 建議持股 <b>{_lo}–{_hi}%</b>（中值 {_mid}%）{_veto}'
        f'<div style="position:relative;height:14px;background:#21262d;border-radius:7px;'
        f'margin:8px 0 4px;">'
        f'<div style="position:absolute;left:{_lo}%;width:{max(_hi - _lo, 1)}%;height:100%;'
        f'background:{_c};border-radius:7px;"></div>'
        f'<div style="position:absolute;left:calc({_mid}% - 1px);top:-3px;width:2px;'
        f'height:20px;background:#f0f6fc;"></div></div>'
        f'<span style="font-size:11px;color:#8b949e;">0%（全現金） ← 總經健康分 '
        f'{_health:.0f} → 100%（滿倉）</span></div>',
        unsafe_allow_html=True,
    )
    st.caption('💡 這是「**姿態油門**」：總經只決定你**該持股幾成**（積極↔防守），'
               '不是「全進全出」開關。總經惡化時上界會被壓低，但個別強勢股仍可各自判斷。')


def render_traffic_light_top() -> tuple[Any, bool, str | None]:
    """渲染紅綠燈卡 + 寫 warroom_summary。

    Returns:
        (placeholder, show_market_data, tl_eff_reg)
        - placeholder: st.empty 物件
        - show_market_data: 快取新鮮 (≤30 min) 且非 refresh 中
        - tl_eff_reg: 有效 traffic light regime(bull/neutral/bear;None 表無資料)
    """
    # ════════════════════════════════════════════════════════
    # 【模組一】紅綠燈決策儀表板(st.empty 佔位符修復版)
    # 修復:先挖洞(placeholder)→ 資料到位後回填,杜絕未審先判
    # 紅綠燈計算邏輯已抽至 macro_helpers.calc_traffic_light(Phase 7A-Ext)
    # _render_traffic_light 在 macro/handlers.py(F-7.1 B-1)
    # ════════════════════════════════════════════════════════

    # ── ① 最頂端先建立佔位符(關鍵:必須在任何計算前建立)───
    _tl_placeholder = st.empty()

    # ── ② 讀取快取(快取新鮮才顯示燈號,否則顯示等待,避免誤導)──
    # 設計原則:燈號必須反映「當前資料」而非「過期快取」
    # 30 分鐘內的快取視為有效;超過則要求重新更新
    _cl_ts_str = st.session_state.get('cl_ts', '')
    _cache_fresh = False
    _age_min: float = 0.0
    if _cl_ts_str:
        try:
            _cl_ts_dt = _dt.datetime.strptime(_cl_ts_str[:16], '%Y-%m-%d %H:%M')
            _age_min = (_dt.datetime.now() - _cl_ts_dt).total_seconds() / 60
            _cache_fresh = _age_min < 30   # 30 分鐘內視為新鮮
        except Exception:
            _cache_fresh = False

    # 刷新進行中時隱藏舊資料(避免更新期間顯示過期結論)
    _is_refreshing = st.session_state.get('_is_refreshing', False)
    _show_market_data = _cache_fresh and not _is_refreshing

    _tl_init = None
    _tm_mkt_init: dict = {}
    if _cache_fresh and not _is_refreshing:
        # 快取新鮮 → 立即計算燈號(含資料新鮮度標記)
        # C1-D v18.290:走 section_inputs SSOT(對齊 5 桶 + 戰情概覽 + 今日作戰室)
        from src.services import load_section_inputs as _load_si_tl
        _tl_inp = _load_si_tl(st.session_state)
        _tm_mkt_init = _tl_inp.mkt_info or {}
        _tm_jq_init = _tl_inp.jingqi_info or {}
        _tm_cd_init = _tl_inp.cl_data or {}
        _tm_li_init = _tl_inp.li_latest
        _tl_init = calc_traffic_light(_tm_mkt_init, _tm_jq_init, _tm_cd_init, _tm_li_init)
        _render_traffic_light(_tl_placeholder, _tl_init, _tm_mkt_init)
    else:
        # 無快取 or 快取過期 → 顯示等待狀態,不顯示誤導性燈號
        age_note = (f'（上次更新 {_age_min:.0f} 分鐘前，已過期）'
                    if _cl_ts_str and not _cache_fresh else '（尚無資料）')
        _tl_placeholder.warning(
            f'⏳ **燈號等待中 {age_note}**\n\n'
            '燈號將在「🚀 一鍵更新全部數據」完成後自動亮起。\n'
            '確保資料是今日最新，再做投資判斷。',
        )

    # 統一有效市場 regime(確保交通燈與下方卡片結論一致)
    # 🔴 對應 bear,🟢 對應 bull,🟡 對應 neutral
    _tl_eff_reg = {'🔴': 'bear', '🟢': 'bull', '🟡': 'neutral'}.get(
        (_tl_init or {}).get('icon', ''), None,
    )

    # ── 同步寫入 session_state(其他頁面需要的值)────────────
    if _tl_init:
        st.session_state['warroom_summary'] = {
            'traffic_light': _tl_init['label'],
            'health_score':  _tl_init['health'],
            'regime': _tm_mkt_init.get('regime', 'neutral'),
            'market_score':  _tl_init['score'],
            'jingqi_avg':    _tl_init['jqavg'],
            'leek_index':    _tl_init['leek'],
            'foreign_net_bn': _tl_init['fnet'],
            'futures_net':   _tl_init['fut_net'],
            'confidence_pct': _tl_init['conf'],
        }

    return _tl_placeholder, _show_market_data, _tl_eff_reg
