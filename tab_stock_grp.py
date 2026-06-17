"""TAB 比較 × 排行（多股比較 / 多因子排行 / 汰弱留強）— 從 app.py 抽出（PR P2-B Phase 5-B）

依賴策略
========
- Top-level: streamlit
- 函式內 late import: 27 個依賴（含 app.py 內部 helper 與外部模組函式），
  避免循環 import（tab_stock_grp.py ← app.py ← tab_stock_grp.py）。

呼叫端
======
- app.py: `with tab_stock_grp: render_stock_grp()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from tab_helpers import (
    final_recommendation,
    format_condition_emoji,
    parse_cash_flow_ratio,
)


def render_stock_grp():
    # ─ Late imports（避免循環 import）─
    import time
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from config import FINMIND_TOKEN  # noqa: F401  (some sub-features may use)
    # 外部模組
    from tech_indicators import (
        calc_rsi, calc_ibs, calc_volume_ratio,
        calc_kd, calc_bollinger, calc_vcp,
    )
    from scoring_helpers import calc_health_score, health_grade
    from ui_widgets import teacher_conclusion
    from financial_health_engine import analyze_financial_health
    from ai_structured_summary import build_structured_summary_prompt
    from etf_fetch import _fetch_news_for
    from daily_checklist import analyze_20d_chips_from_df
    from exit_signals import (
        compute_tech_bearish, judge_news_sentiment_cached, evaluate_exit_signals,
    )
    # app.py 內部 helper
    from app import (
        _get_loader, _load_cache, _save_cache,
        _fetch_stock_news,
        fetch_dividend_data, fetch_financials,
        fetch_quarterly, fetch_quarterly_extra,
        gemini_call, parse_stocks,
    )
    # data_loader 可能也提供 fetch_financial_statements
    try:
        from data_loader import fetch_financial_statements
    except ImportError:
        from app import fetch_financial_statements

    st.markdown("""<div style="padding:6px 0 4px;">
<span style="font-size:20px;font-weight:900;color:#e6edf3;">📊 比較 × 排行</span>
<span style="font-size:11px;color:#484f58;margin-left:10px;">市場狀態 · 多股比較 · 多因子排行 · 汰弱留強 · 最終建議</span>
</div>""", unsafe_allow_html=True)

    # ══ ① 市場狀態快覽 ══════════════════════════════════════════
    # 改為總是渲染 3 張卡，無資料時顯示「未載入」中性 placeholder（不再強制要求先跑總經 Tab）
    _t3_mkt = st.session_state.get('mkt_info', {}) or {}
    _t3_li  = st.session_state.get('li_latest')
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
        # 修正：台股加權指數真實在 cl_data['tw']，而非 mkt_info；舊路徑永遠 None
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
        # 修正：warroom_summary 從未寫入 hold_pct；改讀 mkt_info.exposure_pct ('80%' 字串)
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

    # ══ ② 輸入多檔代碼 ══════════════════════════════════════════
    with st.container(border=True):
        t3c1, t3c2 = st.columns([4, 1])
        with t3c1:
            multi_input = st.text_area(
                '輸入多檔代碼（逗號/空格/換行，最多10檔）',
                value='2330 2454 2317 2382 3017 2308 2303 2376 6669 3661',
                height=68, key='multi_input',
                placeholder='例：2330 2454 2317 2382 3017')
        with t3c2:
            st.markdown('<br>', unsafe_allow_html=True)
            t3_run_btn = st.button('🚀 批次分析', type='primary',
                                   use_container_width=True, key='t3_run_btn')

    stock_list_t3 = parse_stocks(multi_input)[:10]
    if stock_list_t3:
        st.caption(f'待分析：{", ".join(stock_list_t3)}（共{len(stock_list_t3)}檔）')
    elif t3_run_btn:
        st.warning('⚠️ 請先在上方輸入至少一個有效股票代碼，再按「🚀 批次分析」')

    # ══ 批次分析邏輯 ════════════════════════════════════════════
    if t3_run_btn and stock_list_t3:
        loader_t3  = _get_loader()
        results_t3 = []          # 汰弱留強（健康度）結果
        score_t3   = []          # 多因子評分結果

        prog_t3 = st.progress(0, text='批次分析中...')
        from scoring_engine import score_single_stock as _sss
        from stock_names    import get_stock_name as _gsn
        import threading as _threading
        _t3_loader_lock = _threading.Lock()  # FinMind dl 非線程安全，需串行保護

        # ── 並發抓取（ThreadPoolExecutor，最多3個同時）────────
        def _fetch_single_t3(sid4):
            # 先檢查本地緩存（v2 prefix 強制清除舊錯誤 cache）
            _cached = _load_cache('t3v2', sid4, ttl_hours=4)
            if _cached:
                return _cached
            try:
                # get_combined_data 共享 FinMind dl 實例，需加鎖確保線程安全
                with _t3_loader_lock:
                    _df4_raw, _err4, _name4 = loader_t3.get_combined_data(sid4, 360, True)
                df4   = _df4_raw.tail(300).reset_index(drop=True) if _df4_raw is not None and not _df4_raw.empty else None
                # _name4 可能就是 sid4（get_stock_name fallback），需確認是真正的名稱
                name4 = (_name4 if _name4 and _name4 != sid4 else None) or _gsn(sid4) or sid4
                avg_div4, _, _ = fetch_dividend_data(sid4)
                cl4, cx4, _capex4, _cl_src4, _cx_src4, _, _fin_errs4 = fetch_financials(sid4, industry='')
                result4 = {'sid': sid4, 'df': df4, 'name': name4,
                           'avg_div': avg_div4, 'cl': cl4, 'cx': cx4}
                # 空 K 線標記 error 並跳過快取（避免 4hr 內持續空轉）
                if df4 is None or df4.empty:
                    result4['error'] = _err4 or '無 K 線資料（yfinance + FinMind 雙源皆空）'
                else:
                    _save_cache('t3v2', sid4, result4)
                return result4
            except Exception as _e4:
                return {'sid': sid4, 'error': str(_e4)}

        _t3_futures = {}
        with ThreadPoolExecutor(max_workers=3) as _t3_exec:
            for sid4 in stock_list_t3:
                _t3_futures[_t3_exec.submit(_fetch_single_t3, sid4)] = sid4
        _t3_fetched = {}
        for _fut, _sid in _t3_futures.items():
            try:
                _t3_fetched[_sid] = _fut.result()
            except Exception:
                _t3_fetched[_sid] = {'sid': _sid, 'error': 'timeout'}

        for i4, sid4 in enumerate(stock_list_t3):
            prog_t3.progress((i4 + 1) / len(stock_list_t3),
                             text=f'分析 {sid4} ({i4+1}/{len(stock_list_t3)})...')
            try:
                _d4     = _t3_fetched.get(sid4, {})
                df4     = _d4.get('df')
                # 名稱優先: loader返回值 > stock_names靜態字典 > 代碼本身
                _raw_name4 = _d4.get('name', '')
                name4   = (_raw_name4 if _raw_name4 and _raw_name4 != sid4
                           else _gsn(sid4))
                avg_div4= _d4.get('avg_div', 0)
                cl4     = _d4.get('cl')
                cx4     = _d4.get('cx')
                _fin_st4= {}

                price4  = float(df4['close'].iloc[-1]) if df4 is not None and not df4.empty else 0
                ma20_4  = float(df4['MA20'].iloc[-1])  if df4 is not None and 'MA20'  in df4.columns else None
                ma100_4 = float(df4['MA100'].iloc[-1]) if df4 is not None and 'MA100' in df4.columns else None
                rsi4    = calc_rsi(df4)
                ibs4 = calc_ibs(df4)
                vr4     = calc_volume_ratio(df4)
                k4, d4  = calc_kd(df4)
                bb4  = calc_bollinger(df4)
                vcp4    = calc_vcp(df4) if df4 is not None and len(df4) >= 30 else None
                health4, _ = calc_health_score(df4, rsi4, ibs4, vr4, k4, d4, bb4)
                grade4, grade_color4, _, emoji4 = health_grade(health4)

                if ma20_4 and ma100_4 and price4 > ma20_4 > ma100_4:
                    trend4 = '📈多頭'
                elif ma20_4 and ma100_4 and price4 < ma20_4 < ma100_4:
                    trend4 = '📉空頭'
                elif ma100_4 and price4 > ma100_4:
                    trend4 = '📊多箱'
                elif price4 > 0:
                    trend4 = '📊空箱'
                else:
                    trend4 = '⚪無資料'

                val4 = '⚪無股利'
                if avg_div4 > 0 and price4 > 0:
                    ch4, fa4, de4 = avg_div4/0.07, avg_div4/0.05, avg_div4/0.03
                    if price4 <= ch4:
                        val4 = '🟢便宜'
                    elif price4 <= fa4:
                        val4 = '🟡合理'
                    elif price4 <= de4:
                        val4 = '🔴昂貴'
                    else:
                        val4 = '🔴超貴'

                vcp_ok4 = vcp4 and vcp4['contracting']

                # ── 汰弱留強舊評分 ─────────────────────────────
                old_score4 = 0
                if '多頭' in trend4:
                    old_score4 += 2
                if '便宜' in val4:
                    old_score4 += 3
                elif '合理' in val4:
                    old_score4 += 1
                if vcp_ok4:
                    old_score4 += 2
                if cl4 and cl4 > 0:
                    old_score4 += 1
                old_score4 += round(health4 / 50, 0)

                # 出場訊號：技術 + 籌碼兩維（利空新聞第三維由「AI 掃利空」鈕後補）
                _ex_tech4 = compute_tech_bearish(df4, k=k4, d=d4)
                _ex_chip4 = analyze_20d_chips_from_df(df4)
                _ex_chip_sig4 = _ex_chip4.get('signal', '') if isinstance(_ex_chip4, dict) else ''

                results_t3.append({
                    'stock_id': sid4,
                    '代碼': sid4, '名稱': name4 or sid4, '現價': f'{price4:.2f}',
                    '健康度': health4, '評級': f'{emoji4}{grade4}',
                    'RSI':  f'{rsi4}' if rsi4 else '-',
                    '量比': f'{vr4}' if vr4 else '-',
                    'IBS':  f'{ibs4}' if ibs4 is not None else '-',
                    'KD':   f'K{k4}/D{d4}' if k4 else '-',
                    '趨勢': trend4, '357評價': val4,
                    'VCP':  '✅收縮' if vcp_ok4 else '⚪',
                     '合約負債': f'{cl4/1e8:.1f}億' if cl4 and cl4 > 0 else '-',



                    '舊評分': int(old_score4),
                    '_health': health4, '_val': val4, '_trend': trend4,
                    '_ex_tech': _ex_tech4, '_ex_chip_sig': _ex_chip_sig4,
                    # 資料診斷專用欄位（health_inspector 讀取）
                    '_price_date': (str(df4['date'].iloc[-1])[:10]
                                    if df4 is not None and not df4.empty
                                    and 'date' in df4.columns else None),
                    '_cl_ok':      bool(cl4 and cl4 > 0),
                    '_cx_ok':      bool(cx4 and cx4 > 0),
                    '_has_div':    bool(avg_div4 and avg_div4 > 0),
                    '_fetch_err':  _d4.get('error'),
                })

                # ── 操作狀態燈 🔵🟠🟡 ──────────────────────────
                try:
                    _status4 = '⚪'
                    if df4 is not None and not df4.empty:
                        _p4      = float(df4['close'].iloc[-1])
                        _ma20_4  = float(df4['close'].tail(20).mean())
                        _bias4   = (_p4 - _ma20_4) / _ma20_4 * 100 if _ma20_4 else 0
                        _vol4    = float(df4['volume'].iloc[-1])      if 'volume' in df4.columns else 0
                        _avgvol4 = float(df4['volume'].tail(20).mean()) if 'volume' in df4.columns else 1
                        _shrink4 = _avgvol4 > 0 and _vol4 < _avgvol4 * 0.7
                        _near20_4= abs(_bias4) < 3
                        if health4 >= 80 and '多頭' in str(trend4) and _shrink4 and _near20_4:
                            _status4 = '🔵 加碼'
                        elif _bias4 > 25:
                            _status4 = '🟡 警示'
                        elif '昂貴' in str(val4) or '超貴' in str(val4):
                            _status4 = '🟠 減碼'
                    if results_t3:
                        results_t3[-1]['操作狀態'] = _status4
                except Exception:
                    pass

                # ── 多因子評分 ─────────────────────────────────
                if df4 is not None and not df4.empty:
                    try:
                        # 重用第一階段已抓好的 df4（get_combined_data days=360 的 tail(300)），
                        # 不再以 days=300 重打一次 API（原本每檔 get_combined_data 跑兩次純浪費）。
                        _n4_use = name4 or _gsn(sid4)
                        sf = _sss(df4, sid4, _n4_use)
                        score_t3.append(sf)
                    except Exception:
                        pass

            except Exception:
                results_t3.append({
                    'stock_id': sid4, '代碼': sid4, '名稱': '失敗', '現價': '-',
                    '健康度': 0, '評級': '-', 'RSI': '-', '量比': '-',
                    'IBS': '-', 'KD': '-', '趨勢': '-', '357評價': '-',
                    'VCP': '-', '合約負債': '-', '舊評分': 0,
                    '_health': 0, '_val': '-', '_trend': '-',
                })
            time.sleep(0.2)

        prog_t3.empty()

        # ── AI 風控警示 ────────────────────────────────────────
        _t3_mkt = st.session_state.get('mkt_info', {}) or {}  # 從 Tab1 更新後取得
        risk_alerts_t3 = []
        if _t3_mkt.get('regime') == 'bear':
            risk_alerts_t3.append('大盤偏空，建議降低持股至20%以下')
        if _t3_mkt.get('foreign_net', 0) < -5e9:
            risk_alerts_t3.append('外資大量賣超，注意籌碼面壓力')

        st.session_state['t3_data'] = {
            'results':     results_t3,
            'score_t3':    score_t3,
            'risk_alerts': risk_alerts_t3,
        }
        # v18.223：一鍵串接 — 鎖定 batch 當下 codes，下方 MJ + picker 自動跑全程
        st.session_state['t3_batch_codes'] = tuple(stock_list_t3)

    # ══ 顯示結果 ════════════════════════════════════════════════
    t3_data = st.session_state.get('t3_data')
    results_t3 = []  # 確保 results_t3 在 if t3_data 外部也有定義

    if t3_data:
        results_t3  = t3_data['results']
        score_t3    = t3_data['score_t3']
        risk_alerts = t3_data.get('risk_alerts', [])

        # ── 🔰 故事化白話：兩套評分一次搞懂（純疊加，零動計算）──
        with st.expander('🔰 這頁怎麼看？兩套排行 + 多因子一次搞懂'):
            st.markdown('''這頁同時用**兩套評分**幫你比較多檔股票，角度不同、互相參照：

| 排行 | 看什麼 | 白話 |
|---|---|---|
| **③ 多因子評分** | 趨勢＋動能＋籌碼＋量價＋RS 五項合成 | 偏「**現在強不強**」（短中期動能選股） |
| **④ 汰弱留強** | 健康度（均線／RSI／KD／量比／布林） | 偏「**體質好不好**」（淘汰技術面偏弱的） |

**多因子的 5 個分數（0~100，越高越好）：**
- **趨勢**：均線排列是否偏多（站上均線、多頭排列）
- **動能**：近期上漲的力道（漲勢／RSI）
- **籌碼**：法人／主力是否買超
- **量價**：成交量與股價是否同步放大（量價配合）
- **RS 相對強度**：這檔相對大盤是強還是弱，**RS 越高＝跑贏大盤越多**

> 💡 兩套都排前面、且 RS 向上的＝「強上加強」優先觀察；體質好但動能弱的可留意打底。最終仍以最下方「⑤ 最終綜合建議」＋風控警示為準。''')

        # ── 預先計算基本面（③④⑤ 共用）─────────────────────────
        _fund_map = {}
        for _r3 in results_t3:
            _sid3 = _r3.get('stock_id', _r3.get('代碼',''))
            _qtr3 = None
            try:
                _qtr3, _ = fetch_quarterly(_sid3)
            except Exception:
                pass
            _avg3 = None
            try:
                _avg3, _, _ = fetch_dividend_data(_sid3)
            except Exception:
                pass
            _eps3 = _gp3 = None
            if _qtr3 is not None and not _qtr3.empty:
                _ec3 = next((c for c in _qtr3.columns if 'EPS' in str(c).upper() or '每股盈餘' in str(c)), None)
                _gc3 = '毛利率' if '毛利率' in _qtr3.columns else None  # 精確比對，避免命中'毛利率名稱'
                if _ec3:
                    _es3 = pd.to_numeric(_qtr3[_ec3].tail(4), errors='coerce').dropna()
                    if len(_es3) >= 1:
                        _eps3 = round(float(_es3.sum()), 2)
                if _gc3:
                    # 取最後一個非NaN值（避免最新季度尚未公布時取到NaN）
                    _gs3 = pd.to_numeric(_qtr3[_gc3], errors='coerce').dropna()
                    if len(_gs3) >= 1:
                        _gp3 = round(float(_gs3.iloc[-1]), 1)
            # 獲利品質得分 (SQ)
            _sq3 = None
            try:
                from scoring_engine import calc_quality_score as _cqs3
                _sq_r3 = _cqs3(_qtr3)
                if _sq_r3.get('sq') is not None:
                    _sq3 = f"{_sq_r3['sq']:.0f}({_sq_r3['sq_label']})"
            except Exception:
                pass
            # 前瞻動能 FGMS
            _fgms3 = None
            try:
                _qex3 = None
                try:
                    _qex3, _ = fetch_quarterly_extra(_sid3)
                except Exception:
                    pass
                from scoring_engine import calc_forward_momentum_score as _cfgms3
                _is_fin3 = bool(_qtr3['是否金融股'].iloc[0]) if _qtr3 is not None and '是否金融股' in _qtr3.columns else False
                _fg_r3 = _cfgms3(_qtr3, _qex3, is_finance=_is_fin3)
                if _fg_r3.get('fgms') is not None:
                    _fgms3 = f"{_fg_r3['fgms']:.0f}({_fg_r3['fgms_label']})"
            except Exception:
                pass
            _fund_map[_sid3] = {
                '近4季EPS': f'{_eps3:.2f}' if _eps3 is not None else '-',
                '毛利率%':  f'{_gp3:.1f}'  if _gp3  is not None else '-',
                '殖利率%':  f'{_avg3:.1f}' if _avg3  is not None else '-',
                'SQ評分':   _sq3   if _sq3   is not None else '-',
                'FGMS':     _fgms3 if _fgms3 is not None else '-',
            }

        # ── ⑤ 最終綜合建議卡 ──────────────────────────────────
        if results_t3:
            score_map = {s['stock_id']: s for s in score_t3}

            st.markdown('#### ⑤ 最終綜合建議')
            # 動態：計算積極/觀察/等待各有幾支
            _rec_counts = {'積極': 0, '觀察': 0, '等待': 0}
            for _rr in results_t3:
                _rl, _ = final_recommendation(_rr, score_map)
                _rec_counts[_rl.split()[-1]] = _rec_counts.get(_rl.split()[-1], 0) + 1
            _active_n = _rec_counts.get('積極', 0)
            _wait_n = _rec_counts.get('等待', 0)
            if _active_n >= 2:
                _r5c = f'本批 {_active_n} 支達積極布局條件'
                _r5a = '可同步建倉，停損設健康度跌破50'
            elif _active_n == 1:
                _r5c = '僅 1 支達積極條件，其餘觀察或等待'
                _r5a = '單一標的建倉，其餘等訊號確認'
            else:
                _r5c = f'本批無積極訊號（{_wait_n} 支等待），市場擇股難度高'
                _r5a = '空手等待，勿強求進場'
            st.markdown(teacher_conclusion('宏爺', f'健康+多因子+357三重確認，共 {len(results_t3)} 支', _r5c, _r5a), unsafe_allow_html=True)
            rec_cols = st.columns(min(len(results_t3), 5))
            for ci, row in enumerate(results_t3[:5]):
                rec_label, rec_color = final_recommendation(row, score_map)
                mf2 = score_map.get(row['stock_id'], {}).get('total', 0)
                _fd2 = _fund_map.get(row['stock_id'], {})
                with rec_cols[ci]:
                    st.markdown(f"""<div style="background:#0d1117;border:2px solid {rec_color};
border-radius:10px;padding:12px;text-align:center;margin:2px 0;">
<div style="font-size:20px;font-weight:900;color:{rec_color};">{row['代碼']}</div>
<div style="font-size:11px;color:#8b949e;">{row['名稱']}</div>
<div style="font-size:13px;font-weight:700;color:{rec_color};margin:6px 0;">{rec_label}</div>
<div style="font-size:11px;color:#8b949e;">健康:{row.get('健康度',0):.0f} | 多因子:{mf2:.0f}</div>
<div style="font-size:11px;color:#8b949e;">EPS:{_fd2.get('近4季EPS','-')} | 毛利:{_fd2.get('毛利率%','-')}%</div>
</div>""", unsafe_allow_html=True)

        # ── RS 走勢對比 ─────────────────────────────────────────
        if score_t3 and len(score_t3) >= 2:
            st.markdown('---')
            _sdf = pd.DataFrame([{
                '代碼': r['stock_id'], '總分': r.get('total',0),
                '趨勢': r.get('trend',0), '動能': r.get('momentum',0),
                '籌碼': r.get('chip',0), '量價': r.get('volume',0),
                'RS': r.get('rs_score',50),
            } for r in score_t3]).sort_values('總分', ascending=False)
            st.markdown('##### 📈 多因子維度對比')
            # 動態：找出 RS 最高與 RS 向上的股票
            _rs_top = _sdf.iloc[0] if not _sdf.empty else None
            _rs_up_pre = [r['stock_id'] for r in score_t3 if r.get('rs_up')]
            if _rs_top is not None and _rs_up_pre:
                _rs27c = f'RS 最強 {_rs_top["代碼"]}（{_rs_top["RS"]:.0f}分），{len(_rs_up_pre)} 支 RS 向上'
                _rs27a = '優先佈局 RS 向上標的，動能最強'
            elif _rs_top is not None:
                _rs27c = f'RS 最強 {_rs_top["代碼"]}（{_rs_top["RS"]:.0f}分），無 RS 向上訊號'
                _rs27a = '等待突破，趨勢+動能>70再行動'
            else:
                _rs27c = 'RS 資料計算中'
                _rs27a = '等待資料載入後判斷'
            st.markdown(teacher_conclusion('朱家泓', 'RS相對強度對比', _rs27c, _rs27a), unsafe_allow_html=True)
            _score_pivot = _sdf.head(5).set_index('代碼')[['趨勢','動能','籌碼','量價','RS']]
            st.dataframe(_score_pivot, use_container_width=True,
                column_config={c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format='%.0f')
                               for c in ['趨勢','動能','籌碼','量價','RS']})
            _rs_up_list = [r['stock_id'] for r in score_t3 if r.get('rs_up')]
            if _rs_up_list:
                st.success(f"📊 RS曲線向上（強勢動能）：{' / '.join(_rs_up_list)}")

        st.markdown('---')

        # ── ③+④ 雙欄：多因子排行（含EPS/毛利率）vs 汰弱留強 ──
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown('##### ③ 多因子評分排行')
            st.caption('趨勢×0.30 + 動能×0.25 + 籌碼×0.20 + 量價×0.15 + 風險×0.10')
            st.caption('🔰 另三欄基本面白話：SQ品質分＝獲利品質（賺得乾不乾淨）、FGMS前瞻＝前瞻成長動能（未來成長力道），皆 0~100 越高越好；EPS／毛利率／殖利率為對照。')
            # 動態：找出最高分與門檻達標數
            _top_score_r = max(score_t3, key=lambda r: r.get('total', 0)) if score_t3 else None
            _pass70 = [r for r in score_t3 if r.get('total', 0) >= 70]
            if _top_score_r:
                _mf3c = f'最高分 {_top_score_r["stock_id"]} {_top_score_r.get("total",0):.0f}分，{len(_pass70)}/{len(score_t3)} 支≥70分'
                _mf3a = '≥70分方可列入候選，其餘繼續觀察'
            else:
                _mf3c = '多因子資料計算中'
                _mf3a = '等待評分載入'
            st.markdown(teacher_conclusion('孫慶龍', '多因子總分排行', _mf3c, _mf3a), unsafe_allow_html=True)
            if score_t3:
                from scoring_engine import rank_stocks as _rk3
                _ranked3 = _rk3(score_t3)
                _rank_rows = []
                for _ri, _r in enumerate(_ranked3):
                    _sid_r = _r.get('stock_id','')
                    _fd = _fund_map.get(_sid_r, {})
                    _rank_rows.append({
                        '排名': _ri + 1, '代碼': _sid_r,
                        '名稱': (_r.get('stock_name','') or '')[:6],
                        '總分': _r.get('total', 0),
                        '近4季EPS': _fd.get('近4季EPS', '-'),
                        '毛利率%':  _fd.get('毛利率%',  '-'),
                        'SQ評分':   _fd.get('SQ評分',   '-'),
                        'FGMS前瞻': _fd.get('FGMS',     '-'),
                        '殖利率%':  _fd.get('殖利率%',  '-'),
                        '評級': _r.get('grade', '-'),
                    })
                _rank_df = pd.DataFrame(_rank_rows)
                st.dataframe(_rank_df, use_container_width=True, hide_index=True,
                             column_config={
                                 '總分':     st.column_config.ProgressColumn('總分', min_value=0, max_value=100, format='%.1f'),
                                 '近4季EPS': st.column_config.TextColumn('近4Q EPS'),
                                 '毛利率%':  st.column_config.TextColumn('毛利率%'),
                                 'SQ評分':   st.column_config.TextColumn('SQ品質分'),
                                 'FGMS前瞻': st.column_config.TextColumn('FGMS前瞻'),
                                 '殖利率%':  st.column_config.TextColumn('殖利率%'),
                             })
            else:
                st.info('多因子評分資料載入中')

        with col_right:
            st.markdown('##### ④ 汰弱留強明細')
            st.caption('健康度 · 357評價 · VCP · KD · RSI')
            # 動態：計算被淘汰（健康度<50 或 357超貴）的數量
            _elim_n = sum(1 for r in results_t3
                          if r.get('健康度', 100) < 50 or '超貴' in str(r.get('357評價', '')))
            _keep_n = len(results_t3) - _elim_n
            if _elim_n > 0:
                _e4c = f'{_elim_n} 支被淘汰（健康<50 或 357超貴），剩 {_keep_n} 支候選'
                _e4a = '只看留下的 {_keep_n} 支，被淘汰直接跳過'.format(_keep_n=_keep_n)
            else:
                _e4c = f'本批 {len(results_t3)} 支全數通過汰弱篩選'
                _e4a = '品質整齊，可從多因子排行取前2~3支'
            st.markdown(teacher_conclusion('弘爺', f'汰弱留強（共 {len(results_t3)} 支）', _e4c, _e4a), unsafe_allow_html=True)
            # ── 出場警示掃描鈕（利空新聞 LLM 第三維，按需觸發以省額度）──
            if results_t3:
                _scan_c1, _scan_c2 = st.columns([1, 3])
                with _scan_c1:
                    _scan_news = st.button('🤖 AI 掃利空', key='_grp_scan_news',
                                           help='對組合內每檔近期新聞做 Gemini 利空判讀（6h 快取）')
                if _scan_news:
                    _sent_map = {}
                    _prog_n = st.progress(0.0, text='AI 掃描利空新聞中...')
                    for _ni, _r3n in enumerate(results_t3):
                        _sidn = _r3n.get('stock_id', _r3n.get('代碼', ''))
                        _nmn = _r3n.get('名稱', _sidn)
                        _prog_n.progress((_ni + 1) / len(results_t3),
                                         text=f'AI 判讀 {_sidn} 利空... ({_ni+1}/{len(results_t3)})')
                        try:
                            _rawn = _fetch_stock_news(_sidn, _nmn, 8, recency='3m')
                            _titlesn = [n.get('title', '') for n in (_rawn or []) if n.get('title')]
                            _sent_map[_sidn] = (judge_news_sentiment_cached(gemini_call, _sidn, _nmn, _titlesn)
                                                if _titlesn else None)
                        except Exception:
                            _sent_map[_sidn] = None
                    _prog_n.empty()
                    st.session_state['_grp_news_sent'] = _sent_map
                _grp_sent = st.session_state.get('_grp_news_sent', {})
                with _scan_c2:
                    if _grp_sent:
                        _nh = sum(1 for v in _grp_sent.values()
                                  if v and v.get('label') == '利空' and v.get('confidence', 0) >= 50)
                        st.caption(f'✅ 已掃描；偵測 {_nh} 檔利空。出場欄＝三維計分（🔴3／🟠2／🟡1／🟢0）')
                    else:
                        st.caption('出場欄目前為「技術＋籌碼」兩維；按左鈕加入「利空新聞(LLM)」第三維')
                _elim_rows = []
                for _r3 in results_t3:
                    _sid3 = _r3.get('stock_id', _r3.get('代碼',''))
                    _row = {k: v for k, v in _r3.items() if not k.startswith('_') and k != 'stock_id'}
                    _row.update(_fund_map.get(_sid3, {}))
                    _ev3 = evaluate_exit_signals(_r3.get('_ex_tech'),
                                                 _r3.get('_ex_chip_sig', ''),
                                                 _grp_sent.get(_sid3))
                    _row['出場'] = f'{_ev3["icon"]} {_ev3["score"]}/3'
                    _elim_rows.append(_row)
                df_cmp = pd.DataFrame(_elim_rows).sort_values(['舊評分', '健康度'], ascending=[False, False]).reset_index(drop=True)
                # 確保名稱欄位存在
                if '名稱' not in df_cmp.columns and '代碼' in df_cmp.columns:
                    df_cmp.insert(0, '名稱', df_cmp['代碼'])
                _col_order = [c for c in ['名稱','代碼','現價','出場','操作狀態','健康度','評級','舊評分',
                                           'RSI','KD','量比','IBS','趨勢','357評價','VCP',
                                           '合約負債','近4季EPS','毛利率%','殖利率%']
                              if c in df_cmp.columns]
                st.dataframe(df_cmp[_col_order], use_container_width=True,
                             hide_index=True,
                             column_config={
                                 '名稱':     st.column_config.TextColumn('名稱', width='small'),
                                 '代碼':     st.column_config.TextColumn('代碼', width='small'),
                                 '現價':     st.column_config.TextColumn('現價'),
                                 '出場':     st.column_config.TextColumn('出場', width='small', help='三維出場訊號：🔴3=強烈出場 / 🟠2=建議減碼 / 🟡1=留意 / 🟢0=清淡（利空新聞需按「AI 掃利空」）'),
                                 '健康度':   st.column_config.NumberColumn('健康度',  format='%d 🏥'),
                                 '舊評分':   st.column_config.NumberColumn('評分',    format='%d ⭐'),
                                 '近4季EPS': st.column_config.TextColumn('近4Q EPS'),
                                 '毛利率%':  st.column_config.TextColumn('毛利率%'),
                                 '殖利率%':  st.column_config.TextColumn('殖利率%'),
                             })

        st.markdown('---')

        # ── 風控警示 ────────────────────────────────────────────
        if risk_alerts:
            st.markdown('#### ⚠️ 風控警示')
            for alert in risk_alerts:
                st.warning(alert)

    # ══ 批次財報體檢（自動執行）══════════════════════════════════
    if results_t3 and stock_list_t3:
        st.markdown('---')
        st.markdown("""<div style="margin:16px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#d2a8ff18,#0d1117);border-left:4px solid #d2a8ff;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#d2a8ff;">🏥 批次財報體檢（策略2）</span><span style="font-size:11px;color:#8b949e;margin-left:8px;">4力1棒子 · 現金流矩陣 · OPM護城河</span></div>""", unsafe_allow_html=True)
        _fh3_trigger = '_'.join(sorted(r.get('stock_id', r.get('代碼','')) for r in results_t3[:10]))
        if st.session_state.get('_fh_t3_last_key') != _fh3_trigger or not st.session_state.get('_fh_t3_results'):
            _asc = as_completed  # L2: 使用頂層已匯入的 as_completed
            _fk3 = FINMIND_TOKEN    # 使用全域 FINMIND_TOKEN（含 os.environ fallback）
            if not _fk3:
                st.warning('⚠️ 未設定 FINMIND_TOKEN，無法抓取財報資料。請在 Streamlit Secrets 或環境變數中設定 FINMIND_TOKEN。')
            _fh3_new = {}
            _prog3 = st.progress(0, text='財報體檢中（純計算，無 AI 呼叫）...')
            def _fh3_fn(sid):
                _fd3 = fetch_financial_statements(sid, _fk3)
                if not _fd3.get('error'):
                    try:
                        from tw_stock_data_fetcher import fetch_5_years_cash_flow
                        _fd3['b_item_5y'] = fetch_5_years_cash_flow(sid, _fk3)
                    except Exception:
                        pass
                return sid, analyze_financial_health("", sid, _fd3)
            _done3 = 0
            with ThreadPoolExecutor(max_workers=3) as _ex3:
                _fts3 = {_ex3.submit(_fh3_fn, s): s for s in stock_list_t3}
                for _ft3 in _asc(_fts3):
                    _done3 += 1
                    _prog3.progress(_done3 / len(stock_list_t3), text=f'體檢 {_done3}/{len(stock_list_t3)}...')
                    _sid3, _res3 = _ft3.result()
                    _fh3_new[_sid3] = _res3
            _prog3.empty()
            st.session_state['_fh_t3_results'] = _fh3_new
            st.session_state['_fh_t3_last_key'] = _fh3_trigger

    _fh_t3_cached = st.session_state.get('_fh_t3_results', {})

    if _fh_t3_cached:
        # ── 摘要比較表 ────────────────────────────────────────────
        st.markdown('##### 📊 體檢摘要比較表')
        st.caption('🔰 欄位白話（MJ 策略2）：現金水位＝現金佔總資產（>25%佳）；OCF＝營業現金流（須為正，否則「黑字破產」）；'
                   '負債比＝欠錢比例（<60%穩）；企業DNA＝商業模式類型；雷達均分＝五力體質平均（越高越好）。')
        _fh_rows = []
        for _sid_f, _fd_f in _fh_t3_cached.items():
            _scores_f = _fd_f.get('radar_scores', {})
            _avg_f = round(sum(_scores_f.values()) / len(_scores_f), 1) if _scores_f else 0
            _fh_rows.append({
                '代碼':     _sid_f,
                '現金水位':  _fd_f.get('cash_ratio_status', '?') + ' ' + _fd_f.get('cash_ratio_value', ''),
                'OCF':      _fd_f.get('ocf_status', '?') + ' ' + _fd_f.get('ocf_value', ''),
                '負債比':   _fd_f.get('debt_ratio_status', '?') + ' ' + _fd_f.get('debt_ratio_value', ''),
                '企業DNA':  _fd_f.get('business_model_dna', 'N/A'),
                '雷達均分': _avg_f,
                '紅旗':     '⚠️' if (_fd_f.get('red_flags', 'None') not in ('None', '', None)) else '✅',
            })
        _df_fh = pd.DataFrame(_fh_rows).sort_values('雷達均分', ascending=False).reset_index(drop=True)
        st.dataframe(
            _df_fh, use_container_width=True, hide_index=True,
            column_config={
                '代碼':     st.column_config.TextColumn('代碼',   width='small'),
                '現金水位': st.column_config.TextColumn('現金水位'),
                'OCF':      st.column_config.TextColumn('OCF'),
                '負債比':   st.column_config.TextColumn('負債比'),
                '企業DNA':  st.column_config.TextColumn('企業DNA', width='medium'),
                '雷達均分': st.column_config.NumberColumn('雷達均分', format='%.1f ⭐'),
                '紅旗':     st.column_config.TextColumn('紅旗', width='small'),
            }
        )

        # v18.213 L2：多檔模組比較表（鏡像 Fund L1 expander → 合併表 pattern）
        # ── 經營能力多檔比較表 ───────────────────────────────────
        _op_rows = []
        for _sid_o, _fd_o in _fh_t3_cached.items():
            _oper_o = _fd_o.get('operating_module', {}) or {}
            if not _oper_o or _fd_o.get('error'):
                continue
            _op_rows.append({
                '代碼':     _sid_o,
                'DSO 應收': _oper_o.get('DSO', 'N/A'),
                'DIO 存貨': _oper_o.get('DIO', 'N/A'),
                'DPO 應付': _oper_o.get('DPO', 'N/A'),
                '翻桌率':   _oper_o.get('Asset_Turnover', 'N/A'),
                '完整循環': _oper_o.get('Complete_Cycle', 'N/A'),
                '現金缺口': _oper_o.get('Cash_Gap_Days', 'N/A'),
            })
        if _op_rows:
            st.markdown('##### ⚙️ 經營能力多檔比較（MJ DSO/DIO/DPO）')
            _df_op = pd.DataFrame(_op_rows)
            st.dataframe(
                _df_op, use_container_width=True, hide_index=True,
                column_config={
                    '代碼':     st.column_config.TextColumn('代碼', width='small'),
                    'DSO 應收': st.column_config.TextColumn('DSO 應收'),
                    'DIO 存貨': st.column_config.TextColumn('DIO 存貨'),
                    'DPO 應付': st.column_config.TextColumn('DPO 應付'),
                    '翻桌率':   st.column_config.TextColumn('翻桌率'),
                    '完整循環': st.column_config.TextColumn('完整循環'),
                    '現金缺口': st.column_config.TextColumn('現金缺口'),
                }
            )

        # ── 獲利能力多檔比較表 ───────────────────────────────────
        _pf_rows = []
        for _sid_p, _fd_p in _fh_t3_cached.items():
            _prof_p = _fd_p.get('profitability_module', {}) or {}
            if not _prof_p or _fd_p.get('error'):
                continue
            _pf_rows.append({
                '代碼':       _sid_p,
                '毛利率':     _prof_p.get('Gross_Margin', {}).get('Value', 'N/A'),
                '營業利益率': _prof_p.get('Operating_Margin', {}).get('Value', 'N/A'),
                '安全邊際':   _prof_p.get('Margin_Of_Safety', {}).get('Value', 'N/A'),
                '淨利率':     _prof_p.get('Net_Margin', {}).get('Value', 'N/A'),
                'ROE':        _prof_p.get('ROE', {}).get('Value', 'N/A'),
            })
        if _pf_rows:
            st.markdown('##### 💰 獲利能力多檔比較（MJ 5大指標）')
            _df_pf = pd.DataFrame(_pf_rows)
            st.dataframe(
                _df_pf, use_container_width=True, hide_index=True,
                column_config={
                    '代碼':       st.column_config.TextColumn('代碼', width='small'),
                    '毛利率':     st.column_config.TextColumn('毛利率'),
                    '營業利益率': st.column_config.TextColumn('營業利益率', width='medium'),
                    '安全邊際':   st.column_config.TextColumn('安全邊際'),
                    '淨利率':     st.column_config.TextColumn('淨利率'),
                    'ROE':        st.column_config.TextColumn('ROE'),
                }
            )

        # ── 個股詳細展開卡片 ──────────────────────────────────────
        st.markdown('##### 🔍 個股詳細體檢報告')
        for _sid_f, _fd_f in _fh_t3_cached.items():
            _dna_f = _fd_f.get('business_model_dna', '無法判斷')
            _dna_color = (TRAFFIC_GREEN if _dna_f.startswith('A+') else
                          '#2ea043' if _dna_f.startswith('A') else
                          TRAFFIC_YELLOW if _dna_f.startswith('B') else
                          '#f97316' if _dna_f.startswith('C') else
                          TRAFFIC_RED)
            with st.expander(f'🏥 {_sid_f} — DNA: {_dna_f}', expanded=False):
                # 生死燈號
                _gc1, _gc2, _gc3 = st.columns(3)
                _gc1.metric('現金佔總資產', _fd_f.get('cash_ratio_value', 'N/A'),
                            _fd_f.get('cash_ratio_status', '🔴'))
                _gc2.metric('營業活動現金流', _fd_f.get('ocf_value', 'N/A'),
                            _fd_f.get('ocf_status', '🔴'))
                _gc3.metric('負債比率', _fd_f.get('debt_ratio_value', 'N/A'),
                            _fd_f.get('debt_ratio_status', '🔴'))

                # 雷達圖
                _scores_f = _fd_f.get('radar_scores', {})
                if _scores_f:
                    import plotly.graph_objects as go
                    _cats_f = list(_scores_f.keys())
                    _vals_f = list(_scores_f.values()) + [list(_scores_f.values())[0]]
                    _cats_f_closed = _cats_f + [_cats_f[0]]
                    _fig_f = go.Figure(go.Scatterpolar(
                        r=_vals_f, theta=_cats_f_closed,
                        fill='toself', fillcolor='rgba(63,185,80,0.15)',
                        line=dict(color=TRAFFIC_GREEN, width=2),
                        marker=dict(size=6, color=TRAFFIC_GREEN),
                    ))
                    _fig_f.update_layout(
                        polar=dict(
                            radialaxis=dict(range=[0, 100], tickfont=dict(size=9), showticklabels=True),
                            angularaxis=dict(tickfont=dict(size=11)),
                            bgcolor='#0d1117',
                        ),
                        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                        showlegend=False, height=280,
                        margin=dict(l=40, r=40, t=20, b=20),
                    )
                    st.plotly_chart(_fig_f, width='stretch',
                                    key=f'radar_t3_{_sid_f}')

                # DNA + OPM
                st.markdown(
                    f'<div style="display:inline-block;background:{_dna_color}22;'
                    f'border:1px solid {_dna_color}66;border-radius:6px;'
                    f'padding:4px 12px;font-size:13px;color:{_dna_color};font-weight:700;">'
                    f'企業DNA：{_dna_f}</div>',
                    unsafe_allow_html=True
                )
                _opm_f = _fd_f.get('opm_data', {})
                if _opm_f:
                    _pay_f = _opm_f.get('payable_days', 0)
                    _rec_f = _opm_f.get('receivable_days', 0)
                    _adv_f = _opm_f.get('advantage', False)
                    if _adv_f:
                        st.success(f'OPM護城河 ✅ 付款天數({_pay_f}天) > 收款天數({_rec_f}天)，具議價優勢')
                    else:
                        st.warning(f'OPM護城河 ⚠️ 付款天數({_pay_f}天) ≤ 收款天數({_rec_f}天)，議價能力待強化')

                # ── 存活能力精細模組（Survival Module）──────────
                _surv_f = _fd_f.get('survival_module', {})
                if _surv_f and not _fd_f.get('error'):
                    st.markdown('**🏥 存活能力精細診斷（MJ 3大生死指標）**')
                    _s_cols = st.columns(3)
                    _status_color = {'Pass': TRAFFIC_GREEN, 'Acceptable': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED}
                    for _col, (_key, _label) in zip(_s_cols, [
                        ('Cash_Ratio', '💰 氣長不長'),
                        ('DSO_Speed',  '⚡ 收現速度'),
                    ]):
                        _si = _surv_f.get(_key, {})
                        _sc = _status_color.get(_si.get('Status', 'Fail'), TRAFFIC_RED)
                        with _col:
                            st.markdown(
                                f'<div style="background:{_sc}18;border:1px solid {_sc}55;'
                                f'border-radius:8px;padding:10px;text-align:center;">'
                                f'<div style="font-size:11px;color:#8b949e;">{_label}</div>'
                                f'<div style="font-size:18px;font-weight:900;color:{_sc};">{_si.get("Value","N/A")}</div>'
                                f'<div style="font-size:11px;color:{_sc};">{_si.get("Status","?")}</div>'
                                f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_si.get("Insight","")}</div>'
                                f'</div>', unsafe_allow_html=True)
                    _r110 = _surv_f.get('Rule_100_100_10', {})
                    _r110_sc = _status_color.get(_r110.get('Status', 'Fail'), TRAFFIC_RED)
                    # 各分項勾叉（門檻：A>100% / B≥100% / C>10%，與 financial_health_engine:416/423/431 對齊）
                    _a_ok = parse_cash_flow_ratio(_r110.get('Cash_Flow_Ratio',''), 100, strict=True)
                    _b_ok = parse_cash_flow_ratio(_r110.get('Cash_Flow_Adequacy',''), 100, strict=False)
                    _c_ok = parse_cash_flow_ratio(_r110.get('Cash_Reinvestment',''), 10, strict=True)
                    with _s_cols[2]:
                        st.markdown(
                            f'<div style="background:{_r110_sc}18;border:1px solid {_r110_sc}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">🔄 100/100/10</div>'
                            f'<div style="font-size:11px;color:#c9d1d9;">'
                            f'A{format_condition_emoji(_a_ok)}{_r110.get("Cash_Flow_Ratio","N/A")} '
                            f'B{format_condition_emoji(_b_ok)}{_r110.get("Cash_Flow_Adequacy","N/A")} '
                            f'C{format_condition_emoji(_c_ok)}{_r110.get("Cash_Reinvestment","N/A")}</div>'
                            f'<div style="font-size:12px;font-weight:700;color:{_r110_sc};">{_r110.get("Status","?")}</div>'
                            f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_r110.get("Insight","")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _verdict_f = _surv_f.get('Final_Survival_Verdict', '')
                    if _verdict_f:
                        st.caption(f'🎯 {_verdict_f}')

                # ── 經營能力模組（Operating Module）──────────────
                _oper_f = _fd_f.get('operating_module', {})
                if _oper_f and not _fd_f.get('error'):
                    st.markdown('**⚙️ 經營能力診斷（MJ DSO/DIO/DPO）**')
                    _o4c = st.columns(4)
                    with _o4c[0]:
                        st.metric('DSO 應收天數', _oper_f.get('DSO', 'N/A'))
                    with _o4c[1]:
                        st.metric('DIO 存貨天數', _oper_f.get('DIO', 'N/A'))
                    with _o4c[2]:
                        st.metric('DPO 應付天數', _oper_f.get('DPO', 'N/A'))
                    with _o4c[3]:
                        st.metric('總資產翻桌率', _oper_f.get('Asset_Turnover', 'N/A'))
                    _o2c = st.columns(2)
                    with _o2c[0]:
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:#161b22;border-radius:6px;">'
                            f'<div style="font-size:11px;color:#8b949e;">完整循環天數</div>'
                            f'<div style="font-size:18px;font-weight:900;color:#58a6ff;">{_oper_f.get("Complete_Cycle","N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    with _o2c[1]:
                        _ccc_f = str(_oper_f.get('Cash_Gap_Days', '0'))
                        _ccc_num_f = float(''.join(c for c in _ccc_f if c in '0123456789.-') or '0')
                        _ccc_color_f = TRAFFIC_GREEN if _ccc_num_f <= 0 else (TRAFFIC_YELLOW if _ccc_num_f <= 30 else TRAFFIC_RED)
                        _opm_yes_f = _oper_f.get('OPM_Strategy', 'No') == 'Yes'
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:#161b22;border-radius:6px;">'
                            f'<div style="font-size:11px;color:#8b949e;">現金缺口天數 {"🏰 OPM護城河" if _opm_yes_f else ""}</div>'
                            f'<div style="font-size:18px;font-weight:900;color:{_ccc_color_f};">{_ccc_f}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _oper_f.get('Verdict'):
                        st.caption(f'💡 {_oper_f["Verdict"]}')

                # ── 獲利能力模組（Profitability Module）─────────
                _prof_f = _fd_f.get('profitability_module', {})
                if _prof_f and not _fd_f.get('error'):
                    st.markdown('**💰 獲利能力診斷（MJ 5大指標）**')
                    _p5f = st.columns(5)
                    _gm_f = _prof_f.get('Gross_Margin', {})
                    _gm_f_ok = _gm_f.get('Status', '') == 'Good'
                    with _p5f[0]:
                        st.markdown(
                            f'<div style="background:{f"{TRAFFIC_GREEN}18" if _gm_f_ok else f"{TRAFFIC_RED}18"};border:1px solid {f"{TRAFFIC_GREEN}55" if _gm_f_ok else f"{TRAFFIC_RED}55"};'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">毛利率</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{TRAFFIC_GREEN if _gm_f_ok else TRAFFIC_RED};">{_gm_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{TRAFFIC_GREEN if _gm_f_ok else TRAFFIC_RED};">{"好生意" if _gm_f_ok else "辛苦"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _om_f = _prof_f.get('Operating_Margin', {})
                    _om_f_ok = _om_f.get('Core_Business_Profitable', 'No') == 'Yes'
                    with _p5f[1]:
                        st.markdown(
                            f'<div style="background:{f"{TRAFFIC_GREEN}18" if _om_f_ok else f"{TRAFFIC_RED}18"};border:1px solid {f"{TRAFFIC_GREEN}55" if _om_f_ok else f"{TRAFFIC_RED}55"};'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">營業利益率</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{TRAFFIC_GREEN if _om_f_ok else TRAFFIC_RED};">{_om_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{TRAFFIC_GREEN if _om_f_ok else TRAFFIC_RED};">{"本業獲利✅" if _om_f_ok else "本業虧損❌"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _mos_f = _prof_f.get('Margin_Of_Safety', {})
                    _mos_f_ok = _mos_f.get('Status', '') == 'Strong'
                    with _p5f[2]:
                        st.markdown(
                            f'<div style="background:{f"{TRAFFIC_GREEN}18" if _mos_f_ok else f"{TRAFFIC_YELLOW}18"};border:1px solid {f"{TRAFFIC_GREEN}55" if _mos_f_ok else f"{TRAFFIC_YELLOW}55"};'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">安全邊際</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{TRAFFIC_GREEN if _mos_f_ok else TRAFFIC_YELLOW};">{_mos_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{TRAFFIC_GREEN if _mos_f_ok else TRAFFIC_YELLOW};">{"抗震極強" if _mos_f_ok else "費用偏高"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _nm_f = _prof_f.get('Net_Margin', {})
                    _nm_f_s = _nm_f.get('Status', '')
                    _nm_f_c = TRAFFIC_GREEN if _nm_f_s == 'Pass' else (TRAFFIC_YELLOW if _nm_f_s == 'Thin Profit' else TRAFFIC_RED)
                    with _p5f[3]:
                        st.markdown(
                            f'<div style="background:{_nm_f_c}18;border:1px solid {_nm_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">稅後淨利率</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{_nm_f_c};">{_nm_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{_nm_f_c};">{_nm_f_s}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _roe_f = _prof_f.get('ROE', {})
                    _roe_f_warn = _roe_f.get('Leverage_Warning', 'None') != 'None'
                    try:
                        _roe_f_num = float(_roe_f.get('Value', '0').replace('%', '').strip())
                    except (ValueError, AttributeError):
                        _roe_f_num = None
                    _roe_f_positive = _roe_f_num is not None and _roe_f_num > 0
                    _roe_f_c = TRAFFIC_YELLOW if _roe_f_warn else (TRAFFIC_GREEN if _roe_f_positive else TRAFFIC_RED)
                    with _p5f[4]:
                        st.markdown(
                            f'<div style="background:{_roe_f_c}18;border:1px solid {_roe_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">ROE</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{_roe_f_c};">{_roe_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{_roe_f_c};">{"⚠️ 高槓桿" if _roe_f_warn else ("✅ 真實獲利" if _roe_f_positive else "❌ 本業虧損")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _prof_f.get('Final_Insight'):
                        st.caption(f'🎯 {_prof_f["Final_Insight"]}')

                # ── 財務結構模組（Financial Structure Module）────
                _fstr_f = _fd_f.get('financial_structure_module', {})
                if _fstr_f and not _fd_f.get('error'):
                    st.markdown('**🏗️ 財務結構診斷（那根棒子 + 以長支長）**')
                    _fsf2c = st.columns(2)
                    _dr_f = _fstr_f.get('Debt_Ratio', {})
                    _dr_f_s = _dr_f.get('Status', '')
                    _dr_f_c = {'Pass': TRAFFIC_GREEN, 'Warning': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED, 'N/A': '#8b949e'}.get(_dr_f_s, '#8b949e')
                    with _fsf2c[0]:
                        st.markdown(
                            f'<div style="background:{_dr_f_c}18;border:1px solid {_dr_f_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">負債佔資產比率</div>'
                            f'<div style="font-size:20px;font-weight:900;color:{_dr_f_c};">{_dr_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_dr_f_c};">'
                            f'{"✅ 穩健" if _dr_f_s=="Pass" else ("⚠️ 偏高" if _dr_f_s=="Warning" else ("🔴 高危" if _dr_f_s=="Fail" else ("🏦 特許行業" if "金融" in _dr_f.get("Value","") else "⚪ 資料缺漏")))}'
                            f'</div></div>', unsafe_allow_html=True)
                    _ltf_f = _fstr_f.get('Long_Term_Funding_Ratio', {})
                    _ltf_f_s = _ltf_f.get('Status', '')
                    _ltf_f_c = TRAFFIC_GREEN if _ltf_f_s == 'Pass' else ('#8b949e' if _ltf_f_s == 'N/A' else TRAFFIC_RED)
                    _ltf_f_label = ('✅ 資金配置正確' if _ltf_f_s == 'Pass'
                                    else ('⚪ 資料不足' if _ltf_f_s == 'N/A'
                                          else '🔴 短債長投危機'))
                    with _fsf2c[1]:
                        st.markdown(
                            f'<div style="background:{_ltf_f_c}18;border:1px solid {_ltf_f_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">以長支長比率</div>'
                            f'<div style="font-size:20px;font-weight:900;color:{_ltf_f_c};">{_ltf_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_ltf_f_c};">'
                            f'{_ltf_f_label}'
                            f'</div></div>', unsafe_allow_html=True)
                    if _fstr_f.get('Final_Insight'):
                        st.caption(f'🏗️ {_fstr_f["Final_Insight"]}')

                # ── 償債能力模組（Solvency Module）─────────────
                _solv_f = _fd_f.get('solvency_module', {})
                if _solv_f and not _fd_f.get('error'):
                    st.markdown('**🛡️ 短期償債能力（MJ 300/150 嚴格標準）**')
                    _sv_f_v = _solv_f.get('Final_Solvency_Verdict', '')
                    _sv_f_pass = 'Pass' in _sv_f_v
                    _sv_f_exc  = 'Exception' in _sv_f_v
                    _sv_f_bc   = TRAFFIC_GREEN if _sv_f_pass and not _sv_f_exc else (TRAFFIC_YELLOW if _sv_f_exc else TRAFFIC_RED)
                    _sv_f_icon = '✅' if _sv_f_pass and not _sv_f_exc else ('⚡' if _sv_f_exc else '🔴')
                    st.markdown(
                        f'<div style="background:{_sv_f_bc}18;border:1px solid {_sv_f_bc}55;'
                        f'border-radius:8px;padding:6px 12px;margin-bottom:6px;">'
                        f'<span style="font-size:12px;font-weight:700;color:{_sv_f_bc};">'
                        f'{_sv_f_icon} {_sv_f_v}</span></div>', unsafe_allow_html=True)
                    _is_dso_exc_f  = "條件B：天天收現" in _sv_f_v
                    _is_cash_exc_f = "條件A：現金充足" in _sv_f_v
                    _is_any_exc_f  = _is_dso_exc_f or _is_cash_exc_f
                    _cr_thresh_f   = 150 if _is_dso_exc_f else (100 if _is_cash_exc_f else 300)
                    _cr_label_f    = (f'流動比率（保命符放寬 >{_cr_thresh_f}%）'
                                      if _is_any_exc_f else '流動比率 >300%')
                    _svf2c = st.columns(2)
                    for _col_s, (_key_s, _label_s) in zip(_svf2c, [
                        ('Current_Ratio', _cr_label_f),
                        ('Quick_Ratio',   '速動比率 >150%'),
                    ]):
                        _si_f = _solv_f.get(_key_s, {})
                        _si_f_s = _si_f.get('Status', '')
                        if _key_s == 'Current_Ratio' and _is_any_exc_f:
                            try:
                                _cr_f_num = float(_si_f.get('Value', '0').replace('%', '').strip())
                                if _cr_f_num > _cr_thresh_f:
                                    _si_f_c, _si_f_s = TRAFFIC_GREEN, f'Pass（保命符 >{_cr_thresh_f}%）'
                                else:
                                    _si_f_c = TRAFFIC_RED
                            except (ValueError, AttributeError):
                                _si_f_c = TRAFFIC_GREEN if 'Pass' in _si_f_s else TRAFFIC_RED
                        else:
                            _si_f_c = TRAFFIC_GREEN if 'Pass' in _si_f_s else TRAFFIC_RED
                        with _col_s:
                            st.markdown(
                                f'<div style="background:{_si_f_c}18;border:1px solid {_si_f_c}55;'
                                f'border-radius:8px;padding:8px;text-align:center;">'
                                f'<div style="font-size:10px;color:#8b949e;">{_label_s}</div>'
                                f'<div style="font-size:18px;font-weight:900;color:{_si_f_c};">{_si_f.get("Value","N/A")}</div>'
                                f'<div style="font-size:10px;color:{_si_f_c};">{_si_f_s}</div>'
                                f'</div>', unsafe_allow_html=True)
                    if _is_dso_exc_f:
                        st.info('🔍 收現行業保命符（DSO ≤ 15天，流動比率門檻 >150%）')
                    elif _is_cash_exc_f:
                        st.info('💰 現金充足保命符（現金佔總資產 >25%，流動比率門檻 >100%）')
                    if _solv_f.get('Final_Insight'):
                        st.caption(f'🛡️ {_solv_f["Final_Insight"]}')

                # ── 綜合診斷模組（Advanced Diagnostic Module）────
                _adv_f = _fd_f.get('advanced_diagnostic_module', {})
                if _adv_f and not _fd_f.get('error'):
                    st.markdown('**🔬 綜合診斷與避雷（跨表勾稽）**')
                    _adf3c = st.columns(3)
                    # 盈餘品質
                    _eq_f = _adv_f.get('Earnings_Quality', {})
                    _eq_f_s = _eq_f.get('Status', '')
                    _eq_f_c = TRAFFIC_GREEN if _eq_f_s == 'Pass' else (TRAFFIC_RED if _eq_f_s == 'Fail' else '#8b949e')
                    with _adf3c[0]:
                        st.markdown(
                            f'<div style="background:{_eq_f_c}18;border:1px solid {_eq_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">盈餘含金量</div>'
                            f'<div style="font-size:16px;font-weight:900;color:{_eq_f_c};">{_eq_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_eq_f_c};">{"✅ 真金白銀" if _eq_f_s=="Pass" else ("🔴 紙上富貴" if _eq_f_s=="Fail" else "N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 雙高危機
                    _dh_f = _adv_f.get('Double_High_Warning', '')
                    _dh_f_c = TRAFFIC_RED if 'Triggered' in _dh_f else (TRAFFIC_GREEN if 'Clear' in _dh_f else '#8b949e')
                    with _adf3c[1]:
                        st.markdown(
                            f'<div style="background:{_dh_f_c}18;border:1px solid {_dh_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">雙高危機</div>'
                            f'<div style="font-size:13px;font-weight:900;color:{_dh_f_c};">{"🔴 觸發！" if "Triggered" in _dh_f else ("✅ 安全" if "Clear" in _dh_f else "⬜ N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 企業 DNA
                    _dna_f = _adv_f.get('Business_DNA', 'N/A')
                    _dna_f_c = TRAFFIC_GREEN if 'A+' in _dna_f else (TRAFFIC_RED if '瀕死' in _dna_f else '#58a6ff')
                    with _adf3c[2]:
                        st.markdown(
                            f'<div style="background:{_dna_f_c}18;border:1px solid {_dna_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">企業 DNA</div>'
                            f'<div style="font-size:11px;font-weight:900;color:{_dna_f_c};">{_dna_f}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _adv_f.get('Final_Verdict'):
                        st.caption(f'🔬 {_adv_f["Final_Verdict"]}')

                # AI 診斷
                _insight_f = _fd_f.get('ai_insight', '')
                if _insight_f:
                    st.markdown(
                        f'<div style="background:#161b22;border-left:3px solid {TRAFFIC_GREEN};'
                        f'padding:10px 14px;border-radius:0 6px 6px 0;'
                        f'font-size:13px;color:#c9d1d9;margin-top:8px;">'
                        f'🤖 {_insight_f}</div>',
                        unsafe_allow_html=True
                    )

                # 紅旗
                _flags_f = _fd_f.get('red_flags', 'None')
                if _flags_f and _flags_f not in ('None', ''):
                    st.error(f'🚩 紅旗警示：{_flags_f}')
                else:
                    st.success('✅ 未發現財報紅旗異常')

    # ── AI 投資組合綜合判讀 ───────────────────────────────────────
    if results_t3:
        st.markdown('---')
        st.markdown("""<div style="margin:16px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#76e3ea18,#0d1117);border-left:4px solid #76e3ea;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#76e3ea;">🤖 AI 投資組合綜合判讀</span><span style="font-size:11px;color:#8b949e;margin-left:8px;">台股資深基金經理人 · 強弱排序 · 汰弱留強 · 風險診斷</span></div>""", unsafe_allow_html=True)
        _t3ai_key = 't3_port_' + '_'.join(sorted(r.get('stock_id', r.get('代碼','')) for r in results_t3[:10]))
        _t3ai_cached = st.session_state.get(_t3ai_key, '')
        _t3ai_c1, _t3ai_c2 = st.columns([3, 1])
        with _t3ai_c1:
            _t3ai_btn = st.button('🤖 生成 AI 投資組合分析報告', key='t3_ai_gen', type='primary')
        with _t3ai_c2:
            if st.button('🔄 重新生成', key='t3_ai_regen'):
                st.session_state.pop(_t3ai_key, None)
                st.rerun()
        if _t3ai_btn:
            _sc_map3 = {s.get('stock_id'): s for s in score_t3}
            _port_lines = []
            for _rp in results_t3:
                _sid_p = _rp.get('stock_id', _rp.get('代碼',''))
                _nm_p  = _rp.get('stock_name', _rp.get('名稱', _sid_p))
                _ht_p  = _rp.get('_health', 0)
                _sc_p  = _rp.get('total', _rp.get('舊評分', 0))
                _fd_p  = _fund_map.get(_sid_p, {})
                _fhp   = _fh_t3_cached.get(_sid_p, {})
                _dna_p = _fhp.get('business_model_dna', 'N/A') if _fhp else 'N/A'
                _fb_p  = _rp.get('foreign_buy', 0) or 0
                _rsi_p = _rp.get('rsi', 'N/A')
                _ma_p  = '多頭排列' if (_rp.get('ma_above', 0) or 0) >= 2 else '空頭排列'
                _vcp_p = 'VCP突破' if _rp.get('vcp_signal') else '未突破'
                _scf   = _sc_map3.get(_sid_p, {})
                try:
                    _dim_p = (f" 五維(趨{_scf.get('trend',0):.0f}/動{_scf.get('momentum',0):.0f}/籌{_scf.get('chip',0):.0f}"
                              f"/量{_scf.get('volume',0):.0f}/RS{_scf.get('rs_score',50):.0f})") if _scf else ''
                except (TypeError, ValueError):
                    _dim_p = ''
                _rad_p = _fhp.get('radar_scores', {}) if _fhp else {}
                _rad_avg_p = f"{sum(_rad_p.values())/len(_rad_p):.1f}" if _rad_p else '-'
                _port_lines.append(
                    f"[{_sid_p} {_nm_p}] 健康度={_ht_p:.0f} 評分={_sc_p:.0f}{_dim_p} | "
                    f"技術: 均線={_ma_p} RSI={_rsi_p} {_vcp_p} | "
                    f"籌碼: 外資{'買超' if _fb_p>0 else '賣超'}{abs(_fb_p)/1e8:.1f}億 | "
                    f"基本面: EPS={_fd_p.get('近4季EPS','-')} 毛利={_fd_p.get('毛利率%','-')}% "
                    f"殖利率={_fd_p.get('殖利率%','-')} SQ品質={_fd_p.get('SQ評分','-')} FGMS={_fd_p.get('FGMS','-')} | "
                    f"財報體檢: DNA={_dna_p} 現金水位={_fhp.get('cash_ratio_value','-') if _fhp else '-'} "
                    f"OCF={_fhp.get('ocf_value','-') if _fhp else '-'} 負債比={_fhp.get('debt_ratio_value','-') if _fhp else '-'} 雷達均分={_rad_avg_p}"
                )
            _reg_p = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
            _reg_txt_p = '多頭市場（積極操作）' if _reg_p == 'bull' else ('空頭市場（縮減部位）' if _reg_p == 'bear' else '震盪整理（謹慎觀望）')
            _exp_p = st.session_state.get('macro_state', {}).get('exposure_limit_pct', 'N/A')
            # ── 依綜合評分排出強弱順序（重用上方已算好的資料）──────────
            _ranked_t3 = sorted(
                results_t3,
                key=lambda _r: _r.get('total', _r.get('舊評分', 0)) or 0,
                reverse=True,
            )
            _strong_lines = []
            for _ri, _rr in enumerate(_ranked_t3, 1):
                _sid_r = _rr.get('stock_id', _rr.get('代碼', ''))
                _nm_r  = _rr.get('stock_name', _rr.get('名稱', _sid_r))
                _sc_r  = _rr.get('total', _rr.get('舊評分', 0)) or 0
                _ht_r  = _rr.get('_health', 0) or 0
                _ma_r  = '均線多頭排列' if (_rr.get('ma_above', 0) or 0) >= 2 else '均線空頭排列'
                _fb_r  = _rr.get('foreign_buy', 0) or 0
                _strong_lines.append(
                    f"第{_ri}名 [{_sid_r} {_nm_r}] 綜合評分={_sc_r:.0f} 健康度={_ht_r:.0f} | "
                    f"{_ma_r}、外資{'買超' if _fb_r > 0 else '賣超'}{abs(_fb_r)/1e8:.1f}億"
                )
            _strong_str = '\n'.join(_strong_lines) if _strong_lines else '（沒有可排序的股票）'
            # ── 風險診斷字串（大盤格局 + 建議上限 + 系統風控警示）──────
            _risk_str = (
                f"目前大盤格局：{_reg_txt_p}\n"
                f"系統建議的持股上限：{_exp_p}%\n"
                "系統風控警示：\n"
                + ('\n'.join(f'⚠️ {_a}' for _a in risk_alerts) if risk_alerts else '（目前沒有觸發任何風控警示）')
            )
            # ── 時事新聞：抓組合中評分最高的 1~2 檔（重用排序結果）──────
            _news_blocks = []
            for _rn in _ranked_t3[:2]:
                _sid_news = _rn.get('stock_id', _rn.get('代碼', ''))
                _nm_news  = _rn.get('stock_name', _rn.get('名稱', _sid_news))
                if not _sid_news:
                    continue
                _nblk = _fetch_news_for(_sid_news, _nm_news, 3)
                if _nblk:
                    _news_blocks.append(f'【{_sid_news} {_nm_news}】\n{_nblk}')
            _t3_news_str = '\n\n'.join(_news_blocks) if _news_blocks else None
            _t3ai_sections = [
                {'name': '這個組合裡有哪些股票、各檔現在的體質',
                 'data': '\n'.join(_port_lines)},
                {'name': '哪幾檔比較強、哪幾檔在拖後腿',
                 'data': _strong_str},
                {'name': '這個組合有沒有押太集中、現在風險在哪',
                 'data': _risk_str},
            ]
            _t3ai_prompt = build_structured_summary_prompt(
                subject_title='我的個股組合',
                sections=_t3ai_sections,
                news_text=_t3_news_str,
                overall_question='這個組合整體狀況如何、要不要調整、最該注意什麼風險。',
            )
            with st.spinner('AI 基金經理人分析中（約 30 秒）...'):
                _t3ai_result = gemini_call(_t3ai_prompt, max_tokens=2000)
            st.session_state[_t3ai_key] = _t3ai_result
        if _t3ai_cached:
            st.markdown(_t3ai_cached)
        elif not _t3ai_btn:
            st.caption('▲ 點擊上方按鈕，AI 將生成投資組合強弱排序矩陣與汰弱留強建議。')

    # ══ 📊 MJ 趨勢分數（v18.189）+ 🎯 三階段濾網（v19.58）═══════════
    # v18.223 一鍵化：吃 batch 跑完時鎖定的 codes（t3_batch_codes），自動跑 MJ + picker + AI。
    # 不再依賴 stock_list_t3（避免 textarea 改動觸發重跑），改 textarea 後須按「批次分析」才更新。
    _batch_codes = st.session_state.get('t3_batch_codes')
    if _batch_codes:
        _bc_list = list(_batch_codes)
        _render_mj_trend_section(_bc_list, auto_run=True)
        _render_stage_picker_section(_bc_list, auto_run=True)
    elif stock_list_t3:
        st.info('💡 上方按「🚀 批次分析」會自動串跑 MJ 趨勢分數 + 三階段濾網 + AI 三型建議。')


def _render_stage_picker_section(stock_list: list[str], *,
                                  auto_run: bool = False) -> None:
    """v19.58 個股組合內三階段濾網 — 直接拿 stock_list_t3 為 candidates，共用 picker 子函式。

    v18.223：auto_run=True 串接「批次分析」一鍵流程（picker 跳過按鈕直接跑、AI 也自動）。
    與 _render_mj_trend_section 互補：MJ 趨勢分數看「最近 3 月/3 季的進步退步」，
    三階段濾網看「當下是否進場（基本面 9 項 ＋ 籌碼技術 6 項 ＋ AI 三型建議）」。
    共用 data_loader.fetch_financial_statements + financial_health_engine（與 MJ 同源）。
    """
    import pandas as pd
    import streamlit as _st  # noqa: F811

    from app import gemini_call  # late import 沿用 render_stock_grp 同模式避循環
    from tab_stock_picker import render_tab_stock_picker

    _st.markdown('---')
    _st.markdown(
        '<div style="margin:16px 0 8px;padding:8px 16px;'
        'background:linear-gradient(90deg,#3b82f622,#0d1117);'
        'border-left:4px solid #3b82f6;border-radius:0 6px 6px 0;">'
        '<span style="font-size:15px;font-weight:900;color:#3b82f6;">'
        '🎯 三階段濾網（基本面 → 籌碼技術 → AI 建議）</span>'
        '<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        f'直接用上方輸入的 {len(stock_list)} 檔當候選</span></div>',
        unsafe_allow_html=True,
    )

    # 把純代碼 list 轉成 picker 需要的最小 DataFrame
    _df = pd.DataFrame({'代碼': stock_list})
    render_tab_stock_picker(
        gemini_fn=gemini_call,
        candidates=_df,
        source_label='個股組合輸入',
        key_prefix='picker_t3',
        auto_run=auto_run,
    )


def _render_mj_trend_section(stock_list: list[str], *,
                              auto_run: bool = False) -> None:
    """v18.189 個股組合內「MJ 趨勢分數」區塊。

    v18.223：auto_run=True 串接「批次分析」一鍵流程（移除手動按鈕，自動跑全程 + cache）。
    對 stock_list 每檔合議「近 3 月月營收動能」+「近 3 季 MJ 體檢 status delta」
    產出 5 段判定（🚀 強進步 / 📈 進步 / ➖ 中性 / 📉 退步 / 🔻 強退步）。
    月權重 65%（先行）/ 季權重 35%（落後但見品質）。
    """
    import pandas as pd
    from datetime import date

    import streamlit as _st  # noqa: F811 — explicit local alias
    from config import FINMIND_TOKEN as _TOK
    from data_loader import fetch_financial_statements
    from financial_health_engine import analyze_financial_health
    from mj_health_diff import diff_mj_health  # noqa: F401 — used transitively by score
    from mj_snapshot_io import (
        current_finmind_yyyymm,
        list_snapshots,
        load_snapshot,
        save_snapshot,
    )
    from mj_trend_score import compute_trend_score

    _st.markdown('---')
    _st.markdown(
        '<div style="margin:16px 0 8px;padding:8px 16px;'
        'background:linear-gradient(90deg,#22c55e22,#0d1117);'
        'border-left:4px solid #22c55e;border-radius:0 6px 6px 0;">'
        '<span style="font-size:15px;font-weight:900;color:#22c55e;">'
        '📊 MJ 趨勢分數（v18.189）</span>'
        '<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        '月營收動能 × 季財報體檢 · 65/35 雙頻率合議</span></div>',
        unsafe_allow_html=True,
    )
    _st.caption(
        '🔰 **判定規則**：≥+1.5 🚀 強進步 / +0.5~+1.5 📈 進步 / -0.5~+0.5 ➖ 中性 / '
        '-1.5~-0.5 📉 退步 / ≤-1.5 🔻 強退步。'
        '**月權重高**因月營收 10 日公布（先行指標），季財報 45 天遞延（落後但見獲利品質）。'
        '近 3 季 MJ 不足時自動補抓本季快照。'
    )

    # v18.223：auto_run 模式移除手動按鈕；slider 保留以利使用者觀察/調整權重
    _w_mon = _st.slider(
        '月營收權重',
        min_value=0.4, max_value=0.9, value=0.65, step=0.05,
        key='_mj_trend_w_mon',
        help='月營收動能占比，季財報自動 = 1 - 此值。改動後下次按「批次分析」生效。',
    )

    if not auto_run:
        _st.caption('💡 上方按「🚀 批次分析」自動跑 MJ 趨勢分數（首次 ~30-60s）')
        return

    if not _TOK:
        _st.error('🔴 未設定 `FINMIND_TOKEN` → 無法抓財報與月營收')
        return

    yyyymm_curr = current_finmind_yyyymm(date.today())
    # v18.223 cache 防 rerun 重跑（key 含 codes + 權重 + 當前季）
    _mj_cache_key = (
        f'_mj_trend_rows_{hash(tuple(stock_list))}_'
        f'{round(float(_w_mon) * 100)}_{yyyymm_curr}'
    )
    rows = _st.session_state.get(_mj_cache_key)
    if rows is None:
        rows = []
        prog = _st.progress(0.0, text=f'MJ 趨勢分數中 {len(stock_list)} 檔...')
        for i, sid in enumerate(stock_list, 1):
            prog.progress(i / len(stock_list),
                          text=f'[{i}/{len(stock_list)}] {sid} 趨勢計算中...')
            row = _compute_one_stock_trend(
                sid, yyyymm_curr, _TOK, float(_w_mon),
                fetch_financial_statements=fetch_financial_statements,
                analyze_financial_health=analyze_financial_health,
                list_snapshots=list_snapshots,
                load_snapshot=load_snapshot,
                save_snapshot=save_snapshot,
                compute_trend_score=compute_trend_score,
            )
            rows.append(row)
        prog.empty()
        _st.session_state[_mj_cache_key] = rows

    _render_mj_trend_table(rows, pd, _st, yyyymm_curr)


def _compute_one_stock_trend(
    sid: str,
    yyyymm_curr: str,
    token: str,
    w_monthly: float,
    *,
    fetch_financial_statements,
    analyze_financial_health,
    list_snapshots,
    load_snapshot,
    save_snapshot,
    compute_trend_score,
) -> dict:
    """單檔流程：抓月營收 → 補抓 MJ 季財報 → 跑 compute_trend_score。

    例外永遠 graceful — 單檔失敗不阻斷批次。
    """
    row: dict = {
        'sid': sid, 'label': '—', 'label_code': 'error', 'score': 0.0,
        'mon_sub': 0.0, 'mj_sub': 0.0, 'note': '',
        'snap_ym': '', 'snap_stale': None,
    }
    monthly_3m: list[dict] = []
    mj_snaps: list[dict] = []

    # ── 1. 月營收 3 期 ──────────────────────────────────────────
    try:
        from monthly_revenue_screener import compute_yoy_mom, fetch_monthly_revenue
        df_rev = fetch_monthly_revenue(sid, months=15)
        stats = compute_yoy_mom(df_rev) if df_rev is not None and not df_rev.empty else {}
        # compute_yoy_mom 回 {yoy_last3: [M-2, M-1, M], mom_last: float}
        yoy_last3 = (stats or {}).get('yoy_last3') or []
        mom_last = (stats or {}).get('mom_last')
        if isinstance(yoy_last3, list) and yoy_last3:
            for j, yoy in enumerate(yoy_last3):
                if yoy is None:
                    continue
                m_dict = {'yoy_pct': yoy}
                if j == len(yoy_last3) - 1 and mom_last is not None:
                    m_dict['mom_pct'] = mom_last
                monthly_3m.append(m_dict)
    except Exception as e:  # pragma: no cover - defensive
        row['note'] += f'月營收抓取失敗 ({type(e).__name__}); '

    # ── 2. MJ 季財報快照（不足 3 季自動補抓本季）───────────────
    try:
        yms = list_snapshots(sid)
        # 若本季快照缺，自動補抓
        if yyyymm_curr not in yms:
            try:
                fin = fetch_financial_statements(sid, token)
                if fin and not fin.get('error'):
                    mj = analyze_financial_health(token, sid, fin, news_context='')
                    if isinstance(mj, dict):
                        save_snapshot(sid, yyyymm_curr, mj)
                        yms = list_snapshots(sid)  # refresh
            except Exception as e_in:  # pragma: no cover - defensive
                row['note'] += f'本季 MJ 補抓失敗 ({type(e_in).__name__}); '

        # v18.199 ── 記錄實採最新快照季 + 是否落後（快照新鮮度條用）──
        if yms:
            row['snap_ym'] = yms[0]
            row['snap_stale'] = (yms[0] != yyyymm_curr)

        # 取近 3 季（list_snapshots 已降序：新→舊）
        for ym in yms[:3]:
            snap = load_snapshot(sid, ym)
            if isinstance(snap, dict):
                mj_snaps.append(snap)
        # compute_mj_trend_subscore 期望 list[oldest..latest]，反轉之
        mj_snaps.reverse()
    except Exception as e:  # pragma: no cover - defensive
        row['note'] += f'MJ 快照載入失敗 ({type(e).__name__}); '

    # ── 3. 合議 ─────────────────────────────────────────────────
    try:
        out = compute_trend_score(monthly_3m, mj_snaps, w_monthly=w_monthly)
        row['label'] = out['label']
        row['label_code'] = out['label_code']
        row['score'] = out['score']
        row['mon_sub'] = out['monthly_subscore']
        row['mj_sub'] = out['mj_subscore']
        row['mon_detail'] = out['monthly_detail']
        row['mj_detail'] = out['mj_detail']
        if not monthly_3m and not mj_snaps:
            row['note'] += '月+季資料皆缺; '
    except Exception as e:  # pragma: no cover - defensive
        row['note'] += f'合議失敗 ({type(e).__name__}); '
    return row


_TREND_SORT_ORDER = {
    'strong_down': 0, 'down': 1, 'neutral': 2,
    'up': 3, 'strong_up': 4, 'error': 5,
}


def _fmt_quarter(yyyymm: str) -> str:
    """202503 → 2025Q1（季底月份對應季）；格式不符回原字串。"""
    s = str(yyyymm or '').strip()
    if len(s) != 6 or not s.isdigit():
        return s or '—'
    q = {'03': 'Q1', '06': 'Q2', '09': 'Q3', '12': 'Q4'}.get(s[4:6], s[4:6])
    return f'{s[:4]}{q}'


def _render_mj_trend_table(rows: list[dict], pd, st_mod, yyyymm_curr: str = '') -> None:
    """渲染結果表（退步在前）+ 統計 KPI。"""
    if not rows:
        return
    cnt = {k: 0 for k in _TREND_SORT_ORDER}
    for r in rows:
        cnt[r['label_code']] = cnt.get(r['label_code'], 0) + 1
    cols = st_mod.columns(5)
    cols[0].metric('🔻 強退步', cnt.get('strong_down', 0))
    cols[1].metric('📉 退步', cnt.get('down', 0))
    cols[2].metric('➖ 中性', cnt.get('neutral', 0))
    cols[3].metric('📈 進步', cnt.get('up', 0))
    cols[4].metric('🚀 強進步', cnt.get('strong_up', 0))

    # v18.199 ── 📊 快照新鮮度條（MJ 季財報分來自哪季 — 防補抓失敗靜默沿用舊季）──
    _fresh = sum(1 for r in rows if r.get('snap_stale') is False)
    _stale = sum(1 for r in rows if r.get('snap_stale') is True)
    _missing = sum(1 for r in rows if r.get('snap_stale') is None)
    if _stale == 0 and _missing == 0:
        _fc, _ft = TRAFFIC_GREEN, '🟢 全部最新'
    elif _fresh == 0:
        _fc, _ft = TRAFFIC_RED, '🔴 全部落後或缺'
    else:
        _fc, _ft = TRAFFIC_YELLOW, '🟡 部分落後'
    st_mod.markdown(
        f'<div style="margin:8px 0;padding:8px 14px;border-left:4px solid {_fc};'
        f'background:{_fc}14;border-radius:0 6px 6px 0;font-size:13px;">'
        f'<b style="color:{_fc};">📊 MJ 快照新鮮度</b>　'
        f'📅 應有最新季 <b>{_fmt_quarter(yyyymm_curr)}</b>　'
        f'<span style="color:{_fc};">{_ft}</span>　'
        f'<span style="color:#8b949e;">🟢 最新 {_fresh} ／ 🟡 落後 {_stale} ／ ⬜ 無快照 '
        f'{_missing}（共 {len(rows)} 檔）</span></div>',
        unsafe_allow_html=True,
    )

    def _quarter_cell(r: dict) -> str:
        _ym = r.get('snap_ym') or ''
        if not _ym:
            return '⬜ 無'
        _q = _fmt_quarter(_ym)
        return f'🟡 {_q}（舊）' if r.get('snap_stale') else f'🟢 {_q}'

    rows_sorted = sorted(rows, key=lambda r: _TREND_SORT_ORDER.get(r['label_code'], 99))
    df = pd.DataFrame([{
        '代碼': r['sid'],
        '判定': r['label'],
        '綜合分數': round(r['score'], 2),
        '月營收分': round(r['mon_sub'], 2),
        'MJ 季財報分': round(r['mj_sub'], 2),
        '季別': _quarter_cell(r),
        '備註': r['note'].strip().rstrip(';') if r['note'] else '',
    } for r in rows_sorted])
    st_mod.dataframe(df, use_container_width=True, hide_index=True)

    with st_mod.expander('🛠️ 逐檔細節（分子分數推導）', expanded=False):
        for r in rows_sorted:
            st_mod.markdown(f"**{r['sid']}**：{r['label']}（合分 {r['score']:.2f}）")
            st_mod.json({
                'monthly_detail': r.get('mon_detail', {}),
                'mj_detail': r.get('mj_detail', {}),
            })
