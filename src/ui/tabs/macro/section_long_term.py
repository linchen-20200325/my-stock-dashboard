"""src/ui/tabs/macro/section_long_term.py — 長期 regime + 雷達 slow_verdict 準備(P3-D10 v18.392 抽出)。

原 tab_macro.py:178-241 inline。

雙重職責(輕量,集中在一處):
1. 雙視角總經 — 長期 12M classify_long_term_regime 計算 `_lt`(v18.171/190 後 UI 已移,
   保留 _lt 供下方雷達雙速合議)
2. 全球風險雷達資料準備 — 從 _lt 映射 `_slow_v`(v18.172/173),render 已下移至
   「短線急殺」桶之後的 🌍 全球風險桶(由 _render_global_risk_bucket 呼叫)

closure params:無(讀 st.session_state.macro_info via load_section_inputs)

回傳 tuple:
- _lt: dict | None    長期 regime classify 結果(score/regime/color/detail/suggest_pct)
- _rr_fred_key: str   FRED_API_KEY(雷達 fetcher 用)
- _slow_v: dict | None  slow_verdict(level/score/color/icon/action)— 給 _render_global_risk_bucket
"""
from __future__ import annotations

import os
from typing import Any

import streamlit as st


def prepare_long_term_radar() -> tuple[Any, str, Any]:
    """計算長期 regime + 派生 slow_verdict(雷達桶用)。

    Returns:
        (_lt, _rr_fred_key, _slow_v)
        - _lt: classify_long_term_regime 結果 dict(或 None)
        - _rr_fred_key: FRED_API_KEY(雷達 fetcher 用)
        - _slow_v: slow_verdict dict(或 None)
    """
    # ── v18.171 長期 vs 短期 雙視角總經面板 ─────
    # 長期 (12M):景氣大循環位階;短期 (1Q):對齊台股財報季偏向
    # 純函式集中於 macro_helpers.classify_long_term_regime / classify_short_term_regime
    # v18.173:_lt hoist 到 try 外,供下方雙速合議使用
    _lt = None
    try:
        from src.compute.macro import (
            classify_long_term_regime as _cls_lt,
            detect_mk_golden_inflection as _det_mk2,
        )
        # C1-E v18.291:雙視角 macro_info 走 section_inputs SSOT。
        from src.services import load_section_inputs as _load_si_lt
        _lt_inp = _load_si_lt(st.session_state)
        _mi_d = _lt_inp.macro_info or {}
        _cpi_d = _mi_d.get('us_core_cpi') or {}
        _fed_d = _mi_d.get('fed_funds') or {}
        _ndc_d = _mi_d.get('ndc_signal') or {}
        _pmi_d = _mi_d.get('ism_pmi') or {}

        _mk_for_lt = _det_mk2(
            cpi_yoy=_cpi_d.get('yoy'),
            cpi_prev_yoy=_cpi_d.get('prev_yoy'),
            fed_rate=_fed_d.get('current'),
            fed_prev_rate=_fed_d.get('prev'),
        )
        _lt = _cls_lt(
            cpi_yoy=_cpi_d.get('yoy'),
            fed_rate=_fed_d.get('current'),
            fed_prev_rate=_fed_d.get('prev'),
            ndc_score=_ndc_d.get('score'),
            pmi=_pmi_d.get('value') or _pmi_d.get('current') or _pmi_d.get('pmi'),
            mk_signal=_mk_for_lt,
        )
        # v18.190:雙視角 UI 區塊移除(與「拐點偵測 6 面向 + MK」功能重疊,
        # 雙視角為純加權打分、未經 backtest;保留 _lt 計算供下方雷達雙速合議使用)
    except Exception as _e_lts:
        print(f'[tab_macro/長短期雙視角] {type(_e_lts).__name__}: {_e_lts}')

    # ── v18.172/v18.173 全球風險雷達資料準備(render 已下移)──────────────
    # v18.317:10 燈雷達 render 從總覽頂部下移至「短線急殺」桶之後的 🌍 全球風險桶
    # (見下方 _render_global_risk_bucket 呼叫)。此處僅備妥 _rr_fred_key / _slow_v,
    # 並 pre-init 以保證下移後的呼叫點變數必定存在(即使本 try 中途 raise)。
    _rr_fred_key = ''
    _slow_v = None
    try:
        _rr_fred_key = (os.environ.get('FRED_API_KEY') or
                        (st.secrets.get('FRED_API_KEY')
                         if hasattr(st, 'secrets') else None) or '')
        # v18.173:把 v18.171 dual-view 算出的長期 regime _lt 映射成 slow_verdict
        # 校準:_cls_lt score 範圍 ~[-2,+2],乘 5 對齊 fund synth 期望的 ~[-10,+10]
        if _lt and isinstance(_lt, dict) and _lt.get('regime'):
            _reg = str(_lt['regime'])
            _icon = _reg.split()[0] if _reg.split() else '⚪'
            _slow_v = {
                'level':  _reg,
                'score':  float(_lt.get('score') or 0.0) * 5.0,
                'color':  _lt.get('color') or '#888',
                'icon':   _icon,
                'action': f"{_lt.get('detail','')}；建議持股 {_lt.get('suggest_pct','--')}",
            }
    except Exception as _e_rr:
        print(f'[tab_macro/risk_radar] {type(_e_rr).__name__}: {_e_rr}')

    return _lt, _rr_fred_key, _slow_v
