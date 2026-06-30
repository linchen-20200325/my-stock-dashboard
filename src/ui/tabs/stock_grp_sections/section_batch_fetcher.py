"""src/ui/tabs/stock_grp_sections/section_batch_fetcher.py — 批次分析 fetcher
(v18.414 Batch 7-2).

從 tab_stock_grp.py:110-308 抽出。
- ThreadPoolExecutor + cache lock(FinMind dl 非線程安全)
- 並發抓取 K 線 + 股利 + 財報
- 計算技術指標(RSI/IBS/KD/Bollinger/VCP)+ 健康度評分
- 多因子評分(score_single_stock)
- 操作狀態燈分類
- AI 風控警示
- 結果寫入 st.session_state['t3_data'] + ['t3_batch_codes']

§8.2 layer:L5 UI Tab section helper(🟡 中風險:199 LOC,涉及 L1 fetcher + L2 計算)。

對外 API:
- run_batch_fetch(stock_list: list[str]) -> None
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st

from shared.app_cache import _load_cache, _save_cache
from shared.calc_helpers import calc_bias_pct
from shared.thresholds import YIELD_HIGH_DEC, YIELD_LOW_DEC, YIELD_MID_DEC
from src.compute.scoring import (
    calc_health_score,
    compute_tech_bearish,
    health_grade,
    score_single_stock,
)
from src.compute.strategy import (
    calc_bollinger,
    calc_ibs,
    calc_kd,
    calc_rsi,
    calc_vcp,
    calc_volume_ratio,
)
from src.config import get_stock_name
from src.data.stock.app_stock_fetchers import (
    _get_loader,
    fetch_dividend_data,
    fetch_financials,
)
from src.services import analyze_20d_chips_from_df
from src.ui.tabs.tab_helpers import (
    classify_stock_status_lamp,
    classify_trend_4tier,
)


def run_batch_fetch(stock_list: list[str]) -> None:
    """批次抓取 + 計算 + 寫入 session_state(t3_data, t3_batch_codes)。

    並發抓 K 線 / 股利 / 財報 → 算指標 → 算健康度 → 算多因子 → 算狀態燈 → 風控警示。
    """
    loader = _get_loader()
    results_t3 = []          # 汰弱留強(健康度)結果
    score_t3   = []          # 多因子評分結果

    prog_t3 = st.progress(0, text='批次分析中...')
    _t3_loader_lock = threading.Lock()  # FinMind dl 非線程安全,需串行保護

    # ── 並發抓取(ThreadPoolExecutor,最多 3 個同時)────────
    def _fetch_single_t3(sid4):
        _cached = _load_cache('t3v2', sid4, ttl_hours=4)
        if _cached:
            return _cached
        try:
            with _t3_loader_lock:
                _df4_raw, _err4, _name4 = loader.get_combined_data(sid4, 360, True)
            df4   = _df4_raw.tail(300).reset_index(drop=True) if _df4_raw is not None and not _df4_raw.empty else None
            name4 = (_name4 if _name4 and _name4 != sid4 else None) or get_stock_name(sid4) or sid4
            avg_div4, _, _ = fetch_dividend_data(sid4)
            cl4, cx4, _capex4, _cl_src4, _cx_src4, _, _fin_errs4 = fetch_financials(sid4, industry='')
            result4 = {'sid': sid4, 'df': df4, 'name': name4,
                       'avg_div': avg_div4, 'cl': cl4, 'cx': cx4}
            if df4 is None or df4.empty:
                result4['error'] = _err4 or '無 K 線資料(yfinance + FinMind 雙源皆空)'
            else:
                _save_cache('t3v2', sid4, result4)
            return result4
        except Exception as _e4:
            return {'sid': sid4, 'error': str(_e4)}

    _t3_futures = {}
    with ThreadPoolExecutor(max_workers=3) as _t3_exec:
        for sid4 in stock_list:
            _t3_futures[_t3_exec.submit(_fetch_single_t3, sid4)] = sid4
    _t3_fetched = {}
    for _fut, _sid in _t3_futures.items():
        try:
            _t3_fetched[_sid] = _fut.result()
        except Exception:
            _t3_fetched[_sid] = {'sid': _sid, 'error': 'timeout'}

    for i4, sid4 in enumerate(stock_list):
        prog_t3.progress((i4 + 1) / len(stock_list),
                         text=f'分析 {sid4} ({i4+1}/{len(stock_list)})...')
        try:
            _d4     = _t3_fetched.get(sid4, {})
            df4     = _d4.get('df')
            _raw_name4 = _d4.get('name', '')
            name4   = (_raw_name4 if _raw_name4 and _raw_name4 != sid4
                       else get_stock_name(sid4))
            avg_div4= _d4.get('avg_div', 0)
            cl4     = _d4.get('cl')
            cx4     = _d4.get('cx')

            price4  = float(df4['close'].iloc[-1]) if df4 is not None and not df4.empty else 0
            ma20_4  = float(df4['MA20'].iloc[-1])  if df4 is not None and 'MA20'  in df4.columns else None
            ma100_4 = float(df4['MA100'].iloc[-1]) if df4 is not None and 'MA100' in df4.columns else None
            rsi4    = calc_rsi(df4)
            ibs4    = calc_ibs(df4)
            vr4     = calc_volume_ratio(df4)
            k4, d4  = calc_kd(df4)
            bb4     = calc_bollinger(df4)
            vcp4    = calc_vcp(df4) if df4 is not None and len(df4) >= 30 else None
            health4, _ = calc_health_score(df4, rsi4, ibs4, vr4, k4, d4, bb4)
            grade4, grade_color4, _, emoji4 = health_grade(health4)

            # v18.328 PR-C P1:4 段趨勢判定走 SSOT(個股 Tab K 線註解共用同函式)
            trend4, _ = classify_trend_4tier(price4, ma20_4, ma100_4)

            val4 = '⚪無股利'
            if avg_div4 > 0 and price4 > 0:
                ch4, fa4, de4 = avg_div4/YIELD_HIGH_DEC, avg_div4/YIELD_MID_DEC, avg_div4/YIELD_LOW_DEC
                if price4 <= ch4:
                    val4 = '🟢便宜'
                elif price4 <= fa4:
                    val4 = '🟡合理'
                elif price4 <= de4:
                    val4 = '🔴昂貴'
                else:
                    val4 = '🔴超貴'

            vcp_ok4 = vcp4 and vcp4['contracting']

            # 出場訊號:技術 + 籌碼兩維(利空新聞第三維由「AI 掃利空」鈕後補)
            _ex_tech4 = compute_tech_bearish(df4, k=k4, d=d4)
            _ex_chip4 = analyze_20d_chips_from_df(df4)
            _ex_chip_sig4 = _ex_chip4.get('signal', '') if isinstance(_ex_chip4, dict) else ''

            # v18.349 PR-O1:foreign_buy 真 bug 修(SSOT 對齊 data_loader L286 /1000)
            _fb4 = 0.0
            try:
                if df4 is not None and not df4.empty and '外資' in df4.columns:
                    _fb4 = float(pd.to_numeric(
                        df4['外資'].tail(20), errors='coerce').fillna(0).sum())
            except Exception as _e_fb:
                print(f'[section_batch_fetcher foreign_buy] {sid4} {type(_e_fb).__name__}: {_e_fb}')

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
                '_health': health4, '_val': val4, '_trend': trend4,
                'foreign_buy': _fb4,
                '_ex_tech': _ex_tech4, '_ex_chip_sig': _ex_chip_sig4,
                '_price_date': (str(df4['date'].iloc[-1])[:10]
                                if df4 is not None and not df4.empty
                                and 'date' in df4.columns else None),
                '_cl_ok':      bool(cl4 and cl4 > 0),
                '_cx_ok':      bool(cx4 and cx4 > 0),
                '_has_div':    bool(avg_div4 and avg_div4 > 0),
                '_fetch_err':  _d4.get('error'),
            })

            # ── 操作狀態燈 🔵🟠🟡(v18.336 PR-H4:抽至 classify_stock_status_lamp SSOT)
            try:
                _status4 = '⚪'
                if df4 is not None and not df4.empty:
                    _p4      = float(df4['close'].iloc[-1])
                    _ma20_4  = float(df4['close'].tail(20).mean())
                    _bias4   = calc_bias_pct(_p4, _ma20_4) or 0
                    _vol4    = float(df4['volume'].iloc[-1])      if 'volume' in df4.columns else 0
                    _avgvol4 = float(df4['volume'].tail(20).mean()) if 'volume' in df4.columns else 1
                    _vol_ratio4 = _vol4 / _avgvol4 if _avgvol4 > 0 else None
                    _status4 = classify_stock_status_lamp(
                        health_score=health4, trend_label=trend4,
                        bias_pct=_bias4, vol_ratio=_vol_ratio4,
                        valuation_label=val4)
                if results_t3:
                    results_t3[-1]['操作狀態'] = _status4
            except Exception as _e_lamp:
                print(f'[section_batch_fetcher 狀態燈] {sid4} {type(_e_lamp).__name__}: {_e_lamp}')

            # ── 多因子評分 ─────────────────────────────────
            if df4 is not None and not df4.empty:
                try:
                    _n4_use = name4 or get_stock_name(sid4)
                    sf = score_single_stock(df4, sid4, _n4_use)
                    score_t3.append(sf)
                except Exception:
                    pass

        except Exception:
            results_t3.append({
                'stock_id': sid4, '代碼': sid4, '名稱': '失敗', '現價': '-',
                '健康度': 0, '評級': '-', 'RSI': '-', '量比': '-',
                'IBS': '-', 'KD': '-', '趨勢': '-', '357評價': '-',
                'VCP': '-', '合約負債': '-',
                '_health': 0, '_val': '-', '_trend': '-',
            })
        time.sleep(0.2)

    prog_t3.empty()

    # ── AI 風控警示 ────────────────────────────────────────
    _t3_mkt = st.session_state.get('mkt_info', {}) or {}
    risk_alerts_t3 = []
    if _t3_mkt.get('regime') == 'bear':
        risk_alerts_t3.append('大盤偏空,建議降低持股至20%以下')
    if _t3_mkt.get('foreign_net', 0) < -5e9:
        risk_alerts_t3.append('外資大量賣超,注意籌碼面壓力')

    st.session_state['t3_data'] = {
        'results':     results_t3,
        'score_t3':    score_t3,
        'risk_alerts': risk_alerts_t3,
    }
    # v18.223:一鍵串接 — 鎖定 batch 當下 codes,下方 MJ + picker 自動跑全程
    st.session_state['t3_batch_codes'] = tuple(stock_list)
