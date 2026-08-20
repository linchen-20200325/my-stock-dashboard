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
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st

from shared.app_cache import _load_cache, _save_cache
from shared.calc_helpers import calc_bias_pct
# H1:「多因子總分能不能算」的唯一判定(L0 純函式)。原碼在此捏造 regime='neutral',
# 見該模組 docstring 的完整病史與「拒絕評分 vs 挑保守權重」的設計決定。
from shared.scoring_regime_gate import resolve_scoring_regime
# T4(2026-08)：停利目標 1 的百分比 —— 算「實際盈虧比」的分子用。
from shared.signal_thresholds import STOP_PROFIT_T1_PCT
from shared.thresholds import YIELD_HIGH_DEC, YIELD_LOW_DEC, YIELD_MID_DEC
# T4(2026-08)：與個股頁**共用**的紅K錨點 / 壓力支撐純函式（§2.1 SSOT）。
# 這兩支抽自 tab_stock.py 行內邏輯，內含三個踩過坑的防呆
# （S4 v19.78 pandas NaN 版本差異、v19.179 B1-b 兩條）——
# 在這裡重寫一份必然漏掉其中一兩條，故走同一支。
from src.compute.strategy.entry_stop_levels import (
    compute_entry_stop_levels,
    compute_support_resistance,
)
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
    summarize_pattern,  # v19.164:型態批次化(df4 已在手,零額外抓取)。v19.174 去識別化改名
)
from src.config import get_stock_name
from src.data.stock.app_stock_fetchers import (
    fetch_dividend_data,
    fetch_financials,
)
# C2(v19.197):多檔補股本分母 → 重用單檔龍頭 gate,修「合約負債有值就當高」假陽性。
from src.data.stock.share_capital_fetcher import fetch_share_capital
from src.ui.tabs.stock_sections.section_financial_leading import evaluate_leading_gates
from src.services import analyze_20d_chips_from_df
from src.ui.tabs.tab_helpers import (
    classify_stock_status_lamp,
    classify_trend_4tier,
)

# A-2 v19.77(review 效能項,user 核准):thread-local loader — 每 worker 執行緒
# 各持一個 StockDataLoader 實例。原以全域 Lock 串行保護「FinMind dl 非線程安全」,
# 代價是 K 線抓取實質退化為序列;實例隔離後無共享可變狀態 → 免鎖真平行。
# @st.cache_data 的 (stock_id, days) 快取鍵仍跨實例共享(_self 底線略過雜湊),
# 快取效益不變;max_workers=3 維持(FinMind 限流禮貌上限)。
_tls_batch = threading.local()


def _get_worker_loader():
    """本執行緒專屬 StockDataLoader(首次呼叫時建立;3 worker ≤ 3 次 login)。"""
    if not hasattr(_tls_batch, 'loader'):
        from src.data.core import StockDataLoader
        _tls_batch.loader = StockDataLoader()
    return _tls_batch.loader


def run_batch_fetch(stock_list: list[str]) -> None:
    """批次抓取 + 計算 + 寫入 session_state(t3_data, t3_batch_codes)。

    並發抓 K 線 / 股利 / 財報 → 算指標 → 算健康度 → 算多因子 → 算狀態燈 → 風控警示。
    """
    results_t3 = []          # 汰弱留強(健康度)結果
    score_t3   = []          # 多因子評分結果

    # ── 總經 regime:全批取一次,由唯一仲裁點供給(C1 v19.182 → H1)──────────
    # 每檔各讀一次 session 沒有意義(同一次 rerun 內不會變),而且一旦分檔讀就有
    # 「同一批股票用了兩種權重」的空間。此處取一次、全批共用。
    from src.services.allocation_service import get_macro_regime
    _regime_dec = resolve_scoring_regime(get_macro_regime())
    if not _regime_dec.usable:
        # §1 降級不靜默:log 一行,畫面另由 risk_alerts_t3 揭露(見本函式結尾)。
        print(f'[section_batch_fetcher regime] {_regime_dec.reason} '
              f'→ 本批不計算多因子總分')

    prog_t3 = st.progress(0, text='批次分析中...')

    # ── 並發抓取(ThreadPoolExecutor,最多 3 個同時)────────
    # A-2 v19.77:免鎖 — 每 worker 各持 loader 實例(見 _get_worker_loader),
    # 原 Lock 讓抓取實質序列化(3 worker 名存實亡)
    def _fetch_single_t3(sid4):
        _cached = _load_cache('t3v2', sid4, ttl_hours=4)
        if _cached:
            return _cached
        try:
            _df4_raw, _err4, _name4 = _get_worker_loader().get_combined_data(sid4, 360, True)
            df4   = _df4_raw.tail(300).reset_index(drop=True) if _df4_raw is not None and not _df4_raw.empty else None
            name4 = (_name4 if _name4 and _name4 != sid4 else None) or get_stock_name(sid4) or sid4
            avg_div4, _, _ = fetch_dividend_data(sid4)
            cl4, cx4, _capex4, _cl_src4, _cx_src4, _, _fin_errs4 = fetch_financials(sid4, industry='')
            _cap4 = fetch_share_capital(sid4)   # C2:股本分母(龍頭 gate 用);失敗回 0
            result4 = {'sid': sid4, 'df': df4, 'name': name4,
                       'avg_div': avg_div4, 'cl': cl4, 'cx': cx4, 'capital': _cap4}
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
            capital4 = _d4.get('capital')
            # C2(v19.197):合約負債/資本支出「佔股本比」龍頭 gate(重用單檔 SSOT 純函式)。
            # 缺股本(舊快取無 capital / 抓取失敗)→ ratio_known=False、*_lead=False(未評估,不假綠)。
            _gates4 = evaluate_leading_gates(cl4, cx4, capital4)

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

            # ── 型態目標價(批次,v19.164)──────────────────────────────
            # df4 已在手(上方 ThreadPool 抓),型態 L2 為純函式 → 零額外抓取、純 CPU。
            # summarize_pattern 內含 §1 誠實 gate:型態未明封鎖假高 rr、擺動點不足回 None。
            _pattern4 = None
            try:
                if (df4 is not None and not df4.empty
                        and 'high' in df4.columns and 'low' in df4.columns and price4 > 0):
                    _pattern4 = summarize_pattern(df4['high'], df4['low'], price4)
            except Exception as _e_cs4:
                print(f'[section_batch_fetcher pattern] {sid4} '
                      f'{type(_e_cs4).__name__}: {_e_cs4}')

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

            # ── T4(2026-08)大量紅K錨點 + 近N日壓力支撐 ────────────────
            # 零額外抓取:直接吃迴圈內已有的 df4(同 v19.164 `_pattern4` 範式 ——
            # 批次算一次 → 總表加欄 + 下鑽 seed 共用)。
            #
            # ⚠️ 為什麼**不**放停利價 / 固定盈虧比:tab_stock.py:648-677 的
            #   v19.179 B1-b 已證明 RR=(P×1.05−P)/(P−P×0.92)=0.625,**P 完全約掉**
            #   ⇒ 那組數字對每一檔都一樣,放進 20 檔比較表等於印 20 列相同值。
            #   此處只放「以紅K低點為錨」的版本 —— 錨點來自各股自己的價量結構,
            #   才具備比較價值(該處畫面亦已正名為「實際盈虧比(紅K低點停損)」)。
            _tp1_4 = price4 * (1 + STOP_PROFIT_T1_PCT / 100.0) if price4 else None
            _esl4 = compute_entry_stop_levels(
                df4, current_price=price4 or None, take_profit_price=_tp1_4)
            _sr4 = compute_support_resistance(df4, current_price=price4 or None)

            results_t3.append({
                'stock_id': sid4,
                '代碼': sid4, '名稱': name4 or sid4, '現價': f'{price4:.2f}',
                # T4:錨點型價位(因股而異,可比)。None 一律留白,§1 不填 0。
                '_abs_stop':      _esl4.abs_stop,
                '_stop_dist_pct': _esl4.stop_distance_pct,
                '_rr_anchor':     _esl4.risk_reward,
                '_rr_why':        _esl4.unavailable_reason,
                '_entry_half':    _esl4.entry_half,
                '_sr_support':    _sr4.support,
                '_sr_resistance': _sr4.resistance,
                '_sr_dist_sup':   _sr4.distance_to_support_pct,
                '_sr_dist_res':   _sr4.distance_to_resistance_pct,
                '_sr_window':     _sr4.window_bars,
                # T4-2:VCP / 布林**完整 dict**(非只有徽章字串),供下鑽卡片渲染。
                # 兩者在 :158-159 本就算好,這裡只是留住它們 —— 零額外計算、零額外抓取。
                # 都是小 dict(非 DataFrame),20 檔的記憶體成本可忽略。
                '_vcp':           vcp4,
                '_bb':            bb4,
                '健康度': health4, '評級': f'{emoji4}{grade4}',
                'RSI':  f'{rsi4}' if rsi4 else '-',
                '量比': f'{vr4}' if vr4 else '-',
                'IBS':  f'{ibs4}' if ibs4 is not None else '-',
                'KD':   f'K{k4}/D{d4}' if k4 else '-',
                '趨勢': trend4, '357評價': val4,
                'VCP':  '✅收縮' if vcp_ok4 else '⚪',
                # C2:raw 億值 + 佔股本比龍頭 badge(達門檻才亮,取代「有值就當高」)。
                '合約負債': ((f'{cl4/1e8:.1f}億'
                             + (f' 🔴龍頭({_gates4["cl_pct"]:.0f}%股本)'
                                if _gates4['cl_lead'] and _gates4['cl_pct'] is not None else ''))
                            if cl4 and cl4 > 0 else '-'),
                '_health': health4, '_val': val4, '_trend': trend4,
                'foreign_buy': _fb4,
                '_ex_tech': _ex_tech4, '_ex_chip_sig': _ex_chip_sig4,
                '_price_date': (str(df4['date'].iloc[-1])[:10]
                                if df4 is not None and not df4.empty
                                and 'date' in df4.columns else None),
                '_cl_ok':      bool(cl4 and cl4 > 0),   # has-value(health_inspector probe 用,勿改語意)
                '_cx_ok':      bool(cx4 and cx4 > 0),
                # C2:佔股本比龍頭 gate 真判定(cl_lead/cx_lead)+ 比例,供下游/測試釘住
                '_cl_lead':    _gates4['cl_lead'], '_cx_lead': _gates4['cx_lead'],
                '_cl_pct':     _gates4['cl_pct'],  '_cx_pct':  _gates4['cx_pct'],
                '_has_div':    bool(avg_div4 and avg_div4 > 0),
                '_fetch_err':  _d4.get('error'),
                '_pattern':    _pattern4,  # v19.164:型態批次摘要(供總表型態欄 + 下鑽 seed)
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
            # v19.148 ① 接線:6 因子評分依總經 regime 切 WEIGHT_TABLES
            # (bull 重趨勢/動能、bear 重風控/基本面)。
            #
            # H1 修:原碼 `(session_state.get('macro_state', {}) or {}).get('regime')
            # or 'neutral'` —— 舊註解寫「未評估 → neutral(誠實不誤判多空)」,但
            # **neutral 不是「不判斷」,它是「判斷為震盪」的那一組權重**。冷啟動
            # (沒開過 🌍 總經頁)時 `macro_state` 這個 key 根本不存在 → 全批股票
            # 被震盪權重評分,而畫面印出一組看起來完全正常的分數與排名。
            # 現改走唯一仲裁點 `get_macro_regime()` + L0 gate:未評估一律**不評分**,
            # 走下游既有的「⚪ 無法評分」三態(scorability.CandidateStats),
            # 並在 risk_alerts 揭露原因。完整理由見 shared/scoring_regime_gate.py。
            if df4 is not None and not df4.empty and _regime_dec.usable:
                try:
                    _n4_use = name4 or get_stock_name(sid4)
                    sf = score_single_stock(df4, sid4, _n4_use,
                                            regime=_regime_dec.regime)
                    score_t3.append(sf)
                except Exception as _e_sc4:
                    # §1:原碼 `except Exception: pass` —— 評分整檔消失且零 log,
                    # 與「總經未評估」在畫面上長得一模一樣,無從分辨。
                    print(f'[section_batch_fetcher score] {sid4} '
                          f'{type(_e_sc4).__name__}: {_e_sc4}')

        except Exception:
            results_t3.append({
                'stock_id': sid4, '代碼': sid4, '名稱': '失敗', '現價': '-',
                '健康度': 0, '評級': '-', 'RSI': '-', '量比': '-',
                'IBS': '-', 'KD': '-', '趨勢': '-', '357評價': '-',
                'VCP': '-', '合約負債': '-',
                '_health': 0, '_val': '-', '_trend': '-',
            })
        # A-2 v19.77:原迴圈尾 0.2 秒 sleep 已移除 — 本迴圈為純本地計算(I/O 已在
        # 上方 ThreadPool 完成),固定延遲純耗 0.2×N 秒且無任何限流意義(review 點名)

    prog_t3.empty()

    # ── AI 風控警示 ────────────────────────────────────────
    _t3_mkt = st.session_state.get('mkt_info', {}) or {}
    risk_alerts_t3 = []

    # H1 §1:總經未評估 → 多因子總分被擋掉這件事必須讓使用者看見。
    # 這條放**第一位**:下方「⚠️ 風控警示」是本頁唯一會逐條印出的自由文字區,
    # 而總表的「⚪ 無法評分」標記同時服務「抓不到 K 線」與「總經未評估」兩種原因,
    # 不在這裡點名,使用者會誤以為是網路/資料源問題而去重抓。
    if not _regime_dec.usable:
        risk_alerts_t3.append(_regime_dec.notice())

    # H1:原碼讀 `mkt_info['regime']` —— 那是**趨勢面輸入**(價格 vs MA60/MA120 +
    # 外資現貨),不是總經紅綠燈的結論。後果與 C1 v19.182 修掉的其他 7 處同型:
    # 健康分跌破防禦門檻 / 外資期貨大額淨空的那天,總經頁印 🔴 而這條警示**不出現**
    # (因為趨勢面還是 bull);反之趨勢轉弱但總經燈仍 🟢 時它又會喊偏空。
    # 改吃與上方評分權重**同一次**仲裁結果 → 同頁不可能再出現兩種多空結論。
    if _regime_dec.regime == 'bear':
        # v19.170 P0-1:移除硬編碼持股%,持股水位一律由建議持股 SSOT 決定
        risk_alerts_t3.append('大盤偏空,建議降低持股比重 → 實際持股見 🎚️ 建議持股油門')
    if _t3_mkt.get('foreign_net', 0) < -5e9:
        risk_alerts_t3.append('外資大量賣超,注意籌碼面壓力')

    st.session_state['t3_data'] = {
        'results':     results_t3,
        'score_t3':    score_t3,
        'risk_alerts': risk_alerts_t3,
    }
    # v18.223:一鍵串接 — 鎖定 batch 當下 codes,下方財報趨勢 + picker 自動跑全程
    st.session_state['t3_batch_codes'] = tuple(stock_list)
