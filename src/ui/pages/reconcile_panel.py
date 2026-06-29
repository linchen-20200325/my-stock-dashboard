"""src/ui/pages/reconcile_panel.py — §4.3 重算對帳 UI panel(v18.403 #8+#12)。

把 `src/compute/risk/reconcile.py` 三個對帳函式的結果攤在診斷 tab 上:
- US10Y:FRED DGS10 vs Yahoo ^TNX/10
- 月營收 YoY:自算(now/y_ago - 1)vs FinMind 預算欄
- 健康評分:v1 arithmetic vs v2 min_of_factors(Liebig 短板)

§8.2 L5 UI:純讀 session_state + L2 compute,無 I/O。
caller 只需 `from src.ui.pages import render_reconcile_panel`。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from src.compute.risk.reconcile import (
    reconcile_health_score,
    reconcile_monthly_revenue_yoy,
    reconcile_us10y_yield,
)

_C_GREEN  = "#3fb950"
_C_YELLOW = "#d29922"
_C_RED    = "#f85149"
_C_IDLE   = "#666"

_STATUS_COLOR: dict[str, str] = {
    'agree':         _C_GREEN,
    'disagree':      _C_RED,
    'a_missing':     _C_IDLE,
    'b_missing':     _C_IDLE,
    'both_missing':  _C_IDLE,
}

_STATUS_EMOJI: dict[str, str] = {
    'agree':         '🟢',
    'disagree':      '🔴',
    'a_missing':     '⬜',
    'b_missing':     '⬜',
    'both_missing':  '⬜',
}


def _ss(key: str, default: Any = None) -> Any:
    try:
        return st.session_state.get(key, default)
    except Exception:  # noqa: BLE001
        return default


def _get_us10y_pair() -> tuple[float | None, float | None]:
    """從 macro_info 取 FRED DGS10 + Yahoo ^TNX raw quote。

    Returns (fred_dgs10_pct, yahoo_tnx_raw).
    fred_dgs10_pct:百分點(例 4.25 = 4.25%)
    yahoo_tnx_raw:Yahoo 原始 quote(=殖利率 × 10,例 42.5)
    """
    _macro = _ss('macro_info', {}) or {}
    _cl = _ss('cl_data', {}) or {}
    # FRED DGS10 通常在 macro_info 內(待 verify production key);Yahoo ^TNX 在 cl_data.intl
    _fred = (_macro.get('us10y') or {}).get('value')  # 若有
    _intl = _cl.get('intl') or {}
    _tnx_df = _intl.get('10Y公債殖利率')
    _yahoo = None
    if _tnx_df is not None and hasattr(_tnx_df, 'empty') and not _tnx_df.empty:
        _ccol = 'close' if 'close' in _tnx_df.columns else (
            'Close' if 'Close' in _tnx_df.columns else None)
        if _ccol:
            try:
                _yahoo = float(_tnx_df[_ccol].iloc[-1])
            except Exception:
                _yahoo = None
    return _fred, _yahoo


def _get_health_params() -> tuple[float | None, float | None, float | None]:
    """從 session_state 取健康評分對帳所需 3 個輸入:jqavg / score_pct / fnet。"""
    _wr = _ss('warroom_summary', {}) or {}
    _mkt = _ss('mkt_info', {}) or {}
    _cl = _ss('cl_data', {}) or {}

    _jqavg = _wr.get('jingqi_avg')
    if _jqavg is None:
        _jingqi = _ss('jingqi_info', {}) or {}
        _jqavg = _jingqi.get('avg')

    _score = _mkt.get('score')
    # score 折換 0-100:從 macro_helpers.calc_traffic_light 邏輯(score / 4 * 100)
    _score_pct = None
    if _score is not None:
        try:
            _score_pct = float(_score) / 4.0 * 100.0
        except Exception:
            _score_pct = None

    _inst = _cl.get('inst') or {}
    _fk = next((k for k in _inst if '外資' in str(k)), None)
    _fnet = _inst.get(_fk, {}).get('net', 0) if _fk else 0
    try:
        _fnet = float(_fnet)
    except Exception:
        _fnet = 0.0

    return _jqavg, _score_pct, _fnet


def compute_reconcile_rows() -> list[dict[str, Any]]:
    """計算 3 個對帳 row(純函式,易測)。

    Returns list of dict: {name, status, emoji, color, v_a, v_b, source_a, source_b,
                           delta_abs, agree, note}
    """
    rows = []

    # ── US10Y:FRED DGS10 vs Yahoo ^TNX/10 ──────────────
    fred, yahoo = _get_us10y_pair()
    _r = reconcile_us10y_yield(fred, yahoo)
    rows.append({
        'name':     'US10Y 殖利率',
        'status':   _r['status'],
        'emoji':    _STATUS_EMOJI.get(_r['status'], '⬜'),
        'color':    _STATUS_COLOR.get(_r['status'], _C_IDLE),
        'v_a':      _r['value_a'],
        'v_b':      _r['value_b'],
        'source_a': _r['source_a'],
        'source_b': _r['source_b'],
        'delta':    _r['delta_abs'],
        'note':     '雙源差 > 5bp → disagree',
    })

    # ── 月營收 YoY:目前無 production 收集(待 user 觸發個股查詢時動)──
    # 留 placeholder row,寫 'a_missing' 但顯示 ⬜ 已知未觸發
    _t2 = _ss('t2_data', {}) or {}
    self_calc = _t2.get('rev_yoy_self')  # 預留欄位
    finmind = _t2.get('rev_yoy_finmind')  # 預留欄位
    _r2 = reconcile_monthly_revenue_yoy(self_calc, finmind)
    rows.append({
        'name':     '月營收 YoY(待個股觸發)',
        'status':   _r2['status'],
        'emoji':    _STATUS_EMOJI.get(_r2['status'], '⬜'),
        'color':    _STATUS_COLOR.get(_r2['status'], _C_IDLE),
        'v_a':      _r2['value_a'],
        'v_b':      _r2['value_b'],
        'source_a': _r2['source_a'],
        'source_b': _r2['source_b'],
        'delta':    _r2['delta_abs'],
        'note':     '個股 Tab 查股票後填欄;雙源差 > 0.1pp → disagree',
    })

    # ── 健康評分:v1 arithmetic vs v2 min_of_factors ────
    jq, sc, fn = _get_health_params()
    _r3 = reconcile_health_score(jq, sc, fn)
    rows.append({
        'name':     '健康評分(v1 vs v2)',
        'status':   _r3['status'],
        'emoji':    _STATUS_EMOJI.get(_r3['status'], '⬜'),
        'color':    _STATUS_COLOR.get(_r3['status'], _C_IDLE),
        'v_a':      _r3['value_a'],
        'v_b':      _r3['value_b'],
        'source_a': _r3['source_a'],
        'source_b': _r3['source_b'],
        'delta':    _r3['delta_abs'],
        'note':     '差 > 15 分 → arithmetic 掩蓋短板(查 jqavg / score / fnet)',
    })

    return rows


def render_reconcile_panel() -> None:
    """渲染「📐 §4.3 重算對帳 panel」(在 data_registry_panel 之後)。"""
    st.markdown("### 📐 §4.3 重算對帳(雙演算法/雙源 cross-check)")
    st.caption(
        "對齊 CLAUDE.md §4.3 — 關鍵指標雙源對帳,降低單源偏差風險。"
        "🟢 一致 / 🔴 不一致(警示)/ ⬜ 未觸發。"
    )

    rows = compute_reconcile_rows()

    _th = ("font-size:10px;color:#888;font-weight:700;padding:6px 10px;"
           "border-bottom:1px solid #30363d")
    _td = "font-size:11px;padding:6px 10px;line-height:1.4"
    _html = (
        f"<div style='display:grid;grid-template-columns:0.4fr 1.4fr 0.7fr 0.7fr 0.7fr 2.2fr;"
        f"background:#0d1117;border-radius:6px 6px 0 0'>"
        f"<span style='{_th};text-align:center'>狀態</span>"
        f"<span style='{_th}'>指標</span>"
        f"<span style='{_th};text-align:right'>v1</span>"
        f"<span style='{_th};text-align:right'>v2</span>"
        f"<span style='{_th};text-align:right'>差距</span>"
        f"<span style='{_th}'>note</span>"
        f"</div>"
    )
    for r in rows:
        _bg = ("#0a1a0a" if r['emoji'] == "🟢" else
               ("#1a0606" if r['emoji'] == "🔴" else "#0d1117"))
        _va = f"{r['v_a']:.3g}" if r['v_a'] is not None else '—'
        _vb = f"{r['v_b']:.3g}" if r['v_b'] is not None else '—'
        _dl = f"{r['delta']:.3g}" if r['delta'] is not None else '—'
        _html += (
            f"<div style='display:grid;grid-template-columns:0.4fr 1.4fr 0.7fr 0.7fr 0.7fr 2.2fr;"
            f"background:{_bg};border-bottom:1px solid #21262d'>"
            f"<span style='{_td};text-align:center;color:{r['color']};font-size:14px'>{r['emoji']}</span>"
            f"<span style='{_td};color:#e6edf3'>{r['name']}</span>"
            f"<span style='{_td};color:#bbb;text-align:right;font-family:monospace'>{_va}</span>"
            f"<span style='{_td};color:#bbb;text-align:right;font-family:monospace'>{_vb}</span>"
            f"<span style='{_td};color:{r['color']};text-align:right;font-family:monospace'>{_dl}</span>"
            f"<span style='{_td};color:#888;font-size:10px'>{r['note']}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
        f"{_html}</div>", unsafe_allow_html=True,
    )

    # caption:統計 + sources
    _agree = sum(1 for r in rows if r['status'] == 'agree')
    _dis = sum(1 for r in rows if r['status'] == 'disagree')
    _mis = sum(1 for r in rows if 'missing' in r['status'])
    st.caption(
        f"3 個對帳 ｜🟢 一致 {_agree}　🔴 不一致 {_dis}　⬜ 未觸發 {_mis} ｜"
        f"unrolled sources:{rows[0]['source_a']} vs {rows[0]['source_b']} ／"
        f" {rows[2]['source_a']} vs {rows[2]['source_b']}"
    )
