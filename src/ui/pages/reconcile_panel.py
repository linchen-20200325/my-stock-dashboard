"""src/ui/pages/reconcile_panel.py — §4.3 重算對帳 UI panel(v18.403 #8+#12)。

把 `src/compute/risk/reconcile.py` 三個對帳函式的結果攤在診斷 tab 上:
- US10Y:FRED DGS10 vs Yahoo ^TNX(**刻度自動偵測**,v19.177 起不再寫死 ÷10)
- 月營收 YoY:自算(now/y_ago - 1)vs FinMind 預算欄
- 健康評分:v1 arithmetic vs v2 min_of_factors(Liebig 短板)

§8.2 L5 UI:純讀 session_state + L2 compute,無 I/O。
caller 只需 `from src.ui.pages import render_reconcile_panel`。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

# v19.181 D3:色票改引 L0 SSOT。原本這裡 inline 一組舊 GitHub 調色盤
# (#3fb950/#d29922/#f85149/#6e7681),全站已於 v19.68 遷 Tailwind
# (shared/colors.py 的 docstring 就記著這次遷移)⇒ 工具箱裡的 🟡 有兩種黃:
# 本面板一個、data_registry_panel 一個、其餘全站第三個。
from shared.colors import (
    TRAFFIC_GREEN as _C_GREEN,
    TRAFFIC_NEUTRAL as _C_IDLE,
    TRAFFIC_RED as _C_RED,
)
from src.compute.risk.reconcile import (
    reconcile_health_score,
    reconcile_monthly_revenue_yoy,
    reconcile_us10y_yield,
)

#: market_regime 未回報 max_score 時的分母。**必須**與
#: `macro_helpers.calc_traffic_light` 健康段的 `float(_mkt.get('max_score') or 4.0)`
#: 同值 —— 這是對帳面板,分母跟 production 不一樣就等於在對一個假的帳。
_MAX_SCORE_FALLBACK = 4.0

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

    # ── v19.181 D3:score 折換 0-100 的分母改吃 `mkt_info['max_score']` ─────────
    # 【原本錯在哪】舊碼寫死 `score / 4.0 * 100`,註解還說是「從 macro_helpers
    # .calc_traffic_light 邏輯」。但 v19.102 起 macro_helpers 早就改成
    #     _max_score = float(_mkt.get('max_score') or 4.0)
    #     _score_pct = min(_score / _max_score * 100, 100)
    # (macro_helpers.py 健康段;SSOT 說明見 signal_thresholds.HEALTH_WEIGHT_SCORE)。
    # `market_regime` 的真滿分是 **4 / 5 / 6**:固定 4 項一定會評,
    # ad_ratio 有傳 +1、m1b_m2_gap 有傳 +1(market_strategy.py `_max` 計算)。
    # ⇒ max_score=6 時舊碼把 score_pct 算成 1.5 倍(score=3 → 75 而非 50),
    #   對帳面板拿一個**高估 50%** 的輸入去跟 production 對帳,差值本身就是假的。
    # 【為何連 clamp 也要抄】`min(..., 100)` 不是防呆而是語意:score 可能因
    # M1B-M2 的 +0.5 分出現非整數,分母又是動態的,不夾住就可能 >100。
    # 【為何連 `or` 的 falsy 行為也要抄】production 寫的是
    # `float(_mkt.get('max_score') or 4.0)` —— `max_score` 為 **0** 時也會退 4.0
    # (0 是 falsy)。本面板刻意用同一個 `or`,而**不是**寫成
    # `if max_score is None`:對帳面板的職責是把 production 算過的那筆帳再算一次,
    # 不是在這裡「順手修好」production 的邊界處理。真要改 0 的語意,要改的是
    # `macro_helpers`,兩邊一起改;面板單方面「變聰明」= 對到一筆別人沒算過的帳。
    # 唯一額外的守衛是**負分母**:market_regime 的 `_max` 是 4.0 + 0/1 + 0/1,
    # 結構上不可能為負,出現即代表 session 被汙染 → §1 誠實回 None(面板顯示 ⬜),
    # 不讓一個負的 score_pct 悄悄流進對帳差值。
    _score = _mkt.get('score')
    _score_pct = None
    if _score is not None:
        try:
            _max_score = float(_mkt.get('max_score') or _MAX_SCORE_FALLBACK)
        except (TypeError, ValueError):
            print(f"[reconcile_panel] ⚠️ mkt_info['max_score'] 無法轉 float: "
                  f"{_mkt.get('max_score')!r} → score_pct 視為未取得(§1)")
            _max_score = None
        if _max_score is not None and _max_score < 0:
            print(f"[reconcile_panel] ⚠️ mkt_info['max_score'] 為負: {_max_score!r} "
                  f"→ score_pct 視為未取得(§1,不硬算出一個負百分比)")
            _max_score = None
        if _max_score is not None:
            try:
                _score_pct = min(float(_score) / _max_score * 100.0, 100.0)
            except (TypeError, ValueError, ZeroDivisionError):
                print(f"[reconcile_panel] ⚠️ score 無法轉 float: {_score!r} "
                      f"→ 視為未取得(§1)")
                _score_pct = None

    # ── v19.177 P1-B:`_fnet` 缺值改 None,不再捏 0(§1)──────────────────────
    # 舊碼三處都寫死 0。看似無害(v1 的 HEALTH_FNET_BONUS 已校準歸零),但
    # **v2 有實質影響**:`compute_health_score_min_of_factors` 在 `fnet <= 0`
    # 時會把 40 分壓制項加進 min 候選(reconcile.py:229-230)⇒ 「三大法人沒載入」
    # 被當成「外資淨賣」,v2 被硬壓到 ≤40 → 與 v1 拉開差距 → 該列**假紅**。
    # 改回 None 後,reconcile_health_score 內兩個 compute_* 都會回 None,
    # 面板誠實顯示 ⬜(both_missing)而不是紅燈。
    _inst = _cl.get('inst') or {}
    _fk = next((k for k in _inst if '外資' in str(k)), None)
    _fnet_raw = _inst.get(_fk, {}).get('net') if _fk else None
    try:
        _fnet = float(_fnet_raw) if _fnet_raw is not None else None
    except (TypeError, ValueError):
        print(f"[reconcile_panel] ⚠️ 外資 net 無法轉 float: {_fnet_raw!r} → 視為未取得(§1)")
        _fnet = None

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
        # v19.177 P1-B ③:^TNX 刻度改由 reconcile.normalize_tnx_quote 偵測
        # (4.63 直接% / 46.3 ×10 慣例 / 越界回 ⬜ 不猜)。偵測結果印在 source 欄,
        # 故 note 提醒讀者「v1/v2 都已是百分點」,避免又被誤讀成沒換算。
        'note':     '雙源差 > 5bp → disagree；^TNX 刻度自動偵測（見 source 欄），'
                    '兩欄皆為百分點',
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


def reconcile_caption(rows: list[dict[str, Any]]) -> str:
    """對帳表下方的統計 caption(純函式,易測)。

    v19.181 D3:原本 caption 開頭寫死字串「3 個對帳」,與 `len(rows)` 脫鉤 ——
    `compute_reconcile_rows()` 加一列或少一列,畫面照樣說 3 個。同一段還寫死
    `rows[0]` / `rows[2]` 取 source,列數一變就 IndexError 或指到別人的來源。
    改為全部由 rows 推導,並抽成純函式讓測試能直接對「說的 == 算的」。
    """
    _agree = sum(1 for r in rows if r.get('status') == 'agree')
    _dis = sum(1 for r in rows if r.get('status') == 'disagree')
    _mis = sum(1 for r in rows if 'missing' in str(r.get('status', '')))
    _srcs = ' ／ '.join(
        f"{r.get('source_a', '?')} vs {r.get('source_b', '?')}"
        for r in rows
        # 兩源都缺(從未觸發)的列不列 source —— 印出來只是雜訊
        if r.get('status') != 'both_missing'
    )
    _head = (f"{len(rows)} 個對帳 ｜🟢 一致 {_agree}　🔴 不一致 {_dis}　"
             f"⬜ 未觸發 {_mis}")
    return f"{_head} ｜ 對帳來源:{_srcs}" if _srcs else _head


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

    # caption:統計 + sources(全部由 rows 推導,見 `reconcile_caption` docstring)
    st.caption(reconcile_caption(rows))
