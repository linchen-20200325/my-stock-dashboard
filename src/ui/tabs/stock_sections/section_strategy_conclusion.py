"""src/ui/tabs/stock_sections/section_strategy_conclusion.py — 策略 1 結論 + MJ 趨勢分數 section(v18.408 U4 Phase 3-S1).

從 tab_stock.py:1342-1509 抽出。
- 策略 1 結論 expander:月營收 / 毛利率 / SQ 獲利品質 / FGMS 前瞻動能 4 指標
- MJ 趨勢分數合議(月 + 季雙頻率 65/35)

§8.2 layer:L5 UI Tab section helper(中風險:依賴 5 locals + 7 helpers,
無下游 state 寫回)。

對外 API:
- render_strategy_conclusion_section(sid2, rev2, qtr2, qtr_extra2, finmind_token,
                                       fetch_financial_statements,
                                       analyze_financial_health) -> None
"""
from __future__ import annotations

from datetime import date as _date_mj

import pandas as pd
import streamlit as st

from shared.colors import (
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from src.ui.render.tab_sections import border_left_banner  # R-UI-1 v18.412
from shared.signal_thresholds import (
    FGMS_LABEL_T1,
    FGMS_LABEL_T2,
    FGMS_LABEL_T3,
    SQ_GOOD_MIN,
    SQ_STABLE_MIN,
)


def render_strategy_conclusion_section(
    sid2: str, rev2, qtr2, qtr_extra2,
    finmind_token: str,
    fetch_financial_statements,
    analyze_financial_health,
) -> None:
    """策略 1 結論 + MJ 趨勢分數合議。

    Args:
        sid2: 股票代碼
        rev2: 月營收 DataFrame
        qtr2: 季財報 DataFrame
        qtr_extra2: 季 BS/CF DataFrame
        finmind_token: FinMind API token(供 MJ trend 補抓本季快照)
        fetch_financial_statements: callback(token, sid)→ dict
        analyze_financial_health: callback(token, sid, fin, news_context)→ dict
    """
    with st.expander('📖 策略1 結論', expanded=True):
        if rev2 is not None and not rev2.empty and 'yoy' in rev2.columns:
            _yoy_last3 = rev2['yoy'].dropna().tail(3).tolist()
            if len(_yoy_last3) >= 2:
                _yoy_trend = all(_yoy_last3[i] > _yoy_last3[i - 1] for i in range(1, len(_yoy_last3)))
                _yoy_latest = _yoy_last3[-1]
                _rev_signal = ('✅ 月營收YoY連續加速' if _yoy_trend and _yoy_latest > 0
                               else ('⚠️ 月營收成長趨緩' if _yoy_latest > 0 else '🔴 月營收年減'))
                st.markdown(f'<div style="color:#c9d1d9;font-size:13px;padding:3px 0;">• {_rev_signal}（最近YoY: {_yoy_latest:+.1f}%）</div>',
                            unsafe_allow_html=True)
        # 月營收結論(移入 if 內,避免 _rev_signal 未定義)
        if rev2 is not None and not rev2.empty and 'yoy' in rev2.columns:
            _yoy_s2 = rev2['yoy'].dropna().tail(3).tolist()
            if _yoy_s2:
                _rv_latest = _yoy_s2[-1]
                _rv_trend = len(_yoy_s2) >= 2 and all(_yoy_s2[i] > _yoy_s2[i - 1] for i in range(1, len(_yoy_s2)))
                _rv_sig = ('✅ 月營收YoY連續加速' if _rv_trend and _rv_latest > 0
                           else ('⚠️ 月營收成長趨緩' if _rv_latest > 0 else '🔴 月營收年減'))
                _rv_c = TRAFFIC_GREEN if '✅' in _rv_sig else (TRAFFIC_RED if '🔴' in _rv_sig else TRAFFIC_YELLOW)
                st.markdown(border_left_banner(
                    _rv_c,
                    f'<span style="font-size:11px;color:#8b949e;">🎓 策略1 · 月營收</span>　'
                    f'<span style="font-weight:700;">{_rv_sig}（YoY:{_rv_latest:+.1f}%）</span>',
                    padding_y=7, font_size=13,
                ), unsafe_allow_html=True)
            else:
                st.caption('月營收資料不足，無法判斷趨勢')
        else:
            st.caption('⚠️ 月營收資料缺失（請確認 FinMind Token）')
        # 毛利率結論 + 獲利品質得分 (SQ)
        if qtr2 is not None and not qtr2.empty:
            _gp_col = '毛利率' if '毛利率' in qtr2.columns else None  # 精確比對,避免命中'毛利率名稱'
            if _gp_col:
                _gp_series = pd.to_numeric(qtr2[_gp_col].tail(4), errors='coerce').dropna()
                if len(_gp_series) >= 2:
                    _gp_now = float(_gp_series.iloc[-1])
                    _gp_trend = float(_gp_series.iloc[-1]) - float(_gp_series.iloc[-2])
                    _gp_c = TRAFFIC_GREEN if _gp_now >= 30 and _gp_trend >= 0 else (TRAFFIC_YELLOW if _gp_now >= 20 else TRAFFIC_RED)
                    _gp_msg = (f'✅ {_gp_now:.1f}%（高毛利≥30%，護城河寬）' if _gp_now >= 30
                               else f'⚠️ {_gp_now:.1f}%（中等毛利20~30%）' if _gp_now >= 20
                               else f'🔴 {_gp_now:.1f}%（低毛利<20%）')
                    st.markdown(border_left_banner(
                        _gp_c,
                        f'<span style="font-size:11px;color:#8b949e;">🎓 陳重銘 · 毛利率</span>　'
                        f'<span style="font-weight:700;">{_gp_msg}</span>',
                        padding_y=7, font_size=13,
                    ), unsafe_allow_html=True)
            # 獲利品質得分 (SQ)
            try:
                from src.compute.scoring import calc_quality_score as _cqs
                _sq_res = _cqs(qtr2)
                if _sq_res.get('sq') is not None:
                    _sq_v = _sq_res['sq']
                    _sq_lbl = _sq_res['sq_label']
                    _sq_gm = _sq_res['gm_trend']
                    _sq_rv = _sq_res['rev_trend']
                    _sq_c = TRAFFIC_GREEN if _sq_v >= SQ_GOOD_MIN else (TRAFFIC_YELLOW if _sq_v >= SQ_STABLE_MIN else TRAFFIC_RED)
                    st.markdown(border_left_banner(
                        _sq_c,
                        f'<span style="font-size:11px;color:#8b949e;">🎓 獲利品質 SQ</span>　'
                        f'<span style="font-weight:700;">SQ {_sq_v:.0f}分 · {_sq_lbl}</span>'
                        f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">毛利{_sq_gm} 營收{_sq_rv}</span>',
                        padding_y=7, font_size=13,
                    ), unsafe_allow_html=True)
            except Exception:
                pass
            # 前瞻成長動能分數 (FGMS)
            try:
                from src.compute.scoring import calc_forward_momentum_score as _cfgms
                _is_fin2 = bool(qtr2.get('是否金融股', pd.Series([False])).iloc[0]) if qtr2 is not None and '是否金融股' in qtr2.columns else False
                print(f'[FGMS_UI] qtr2={qtr2 is not None and not qtr2.empty}, qtr_extra2={qtr_extra2 is not None and not qtr_extra2.empty}')
                _fgms_r = _cfgms(qtr2, qtr_extra2, is_finance=_is_fin2)
                print(f'[FGMS_UI] fgms={_fgms_r.get("fgms")}, three_rate={_fgms_r.get("three_rate")}')
                if _fgms_r.get('fgms') is not None:
                    _fv = _fgms_r['fgms']
                    _fl = _fgms_r['fgms_label']
                    _fc = TRAFFIC_GREEN if _fv >= FGMS_LABEL_T2 else (TRAFFIC_YELLOW if _fv >= FGMS_LABEL_T3 else TRAFFIC_RED)
                    _ = FGMS_LABEL_T1  # 保留 import 不被 lint 移除(原 inline 引用)
                    # 子維度摘要(得分)
                    _fd_parts = []
                    if _fgms_r['cl_momentum'] is not None:
                        _fd_parts.append(f"合約負債:{_fgms_r['cl_momentum']:.0f}")
                    if _fgms_r['inv_divergence'] is not None:
                        _fd_parts.append(f"存貨背離:{_fgms_r['inv_divergence']:.0f}")
                    if _fgms_r['three_rate'] is not None:
                        _fd_parts.append(f"三率:{_fgms_r['three_rate']:.0f}")
                    if _fgms_r['capex_intensity'] is not None:
                        _fd_parts.append(f"資本支出:{_fgms_r['capex_intensity']:.0f}")
                    _fd_str = '  '.join(_fd_parts)
                    # 三率實際數值(最新季)
                    _rate_parts = []
                    if qtr2 is not None and not qtr2.empty:
                        def _last_rate(col):
                            if col in qtr2.columns:
                                _s = pd.to_numeric(qtr2[col], errors='coerce').dropna()
                                return f"{_s.iloc[-1]:.1f}%" if len(_s) else None
                            return None
                        _gm_v = _last_rate('毛利率')
                        _oi_v = _last_rate('營業利益率')
                        _ni_v = _last_rate('淨利率')
                        if _gm_v:
                            _rate_parts.append(f"毛利率{_gm_v}")
                        if _oi_v:
                            _rate_parts.append(f"營業利益率{_oi_v}")
                        if _ni_v:
                            _rate_parts.append(f"淨利率{_ni_v}")
                    _rate_str = '  '.join(_rate_parts)
                    _rate_line = (f'<div style="font-size:11px;color:#8b949e;margin-top:3px;">📊 三率實值：{_rate_str}</div>'
                                  if _rate_str else '')
                    st.markdown(border_left_banner(
                        _fc,
                        f'<span style="font-size:11px;color:#8b949e;">🔭 前瞻動能 FGMS</span>　'
                        f'<span style="font-weight:700;">FGMS {_fv:.0f}分 · {_fl}</span>'
                        f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">{_fd_str}</span>'
                        f'{_rate_line}',
                        padding_y=7, font_size=13,
                    ), unsafe_allow_html=True
                    )
            except Exception as _efgms2:
                import traceback as _tb2
                print(f'[FGMS_UI] 顯示錯誤: {_efgms2}')
                _tb2.print_exc()

    # ── 📊 MJ 趨勢分數合議(月+季雙頻率,單檔模式)──
    # SSOT:呼叫 mj_trend_score.compute_one_stock_trend(),與組合 Tab 同一函式
    try:
        from src.compute.health import (
            current_finmind_yyyymm as _cfymm,
            list_snapshots as _ls_snap,
            load_snapshot as _ld_snap,
            save_snapshot as _sv_snap,
        )
        from src.compute.health import compute_one_stock_trend as _cost
        _ymm_curr = _cfymm(_date_mj.today())
        _mj_row = _cost(
            sid=sid2, yyyymm_curr=_ymm_curr, token=finmind_token, w_monthly=0.65,
            fetch_financial_statements=fetch_financial_statements,
            analyze_financial_health=analyze_financial_health,
            list_snapshots=_ls_snap, load_snapshot=_ld_snap, save_snapshot=_sv_snap,
        )
        _mj_score = float(_mj_row.get('score', 0.0))
        _mj_label = _mj_row.get('label', '—')
        _mj_code = _mj_row.get('label_code', 'error')
        _mj_color = {
            'strong_up': TRAFFIC_GREEN, 'up': TRAFFIC_GREEN,
            'neutral': TRAFFIC_NEUTRAL,
            'down': TRAFFIC_YELLOW, 'strong_down': TRAFFIC_RED,
            'error': TRAFFIC_NEUTRAL,
        }.get(_mj_code, TRAFFIC_NEUTRAL)
        _mon_sub = float(_mj_row.get('mon_sub', 0.0))
        _mj_sub = float(_mj_row.get('mj_sub', 0.0))
        _snap_ym = _mj_row.get('snap_ym') or '—'
        _snap_stale = _mj_row.get('snap_stale')
        _fresh_tag = ('🟢 最新' if _snap_stale is False
                      else ('🟡 落後' if _snap_stale is True else '⬜ 無快照'))
        _mj_note = (_mj_row.get('note') or '').strip().rstrip(';')
        _note_line = (f'<div style="font-size:11px;color:#8b949e;margin-top:3px;">⚠️ {_mj_note}</div>'
                      if _mj_note else '')
        st.markdown(
            f'<div style="background:#0d1117;border-left:3px solid {_mj_color};'
            f'padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
            f'<span style="font-size:11px;color:#8b949e;">📊 MJ 趨勢分數合議（月+季 65/35）</span>　'
            f'<span style="font-size:13px;font-weight:700;color:{_mj_color};">{_mj_label}（合分 {_mj_score:+.2f}）</span>'
            f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">月分 {_mon_sub:+.2f} · 季分 {_mj_sub:+.2f} · 快照 {_snap_ym} {_fresh_tag}</span>'
            f'{_note_line}'
            f'</div>', unsafe_allow_html=True
        )
    except Exception as _emj:
        print(f'[MJ_TREND_UI] 顯示錯誤: {_emj}')
