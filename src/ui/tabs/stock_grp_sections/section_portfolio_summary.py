"""src/ui/tabs/stock_grp_sections/section_portfolio_summary.py — 顯示結果區
(v18.415 Batch 7-3).

從 tab_stock_grp.py:105-446 抽出。包含 5 個子塊:
- 📊 投資組合綜合總結 banner(5 KPI metric)
- 🔰 兩套評分故事化 expander
- 預先計算基本面 _fund_map(EPS / 毛利 / 殖利率 / SQ / FGMS / P/B)
- ⑤ 最終綜合建議卡(每檔最多 5 張)
- 📈 RS 走勢對比 + 多因子維度對比表
- ③ 多因子評分排行(左欄)
- ④ 汰弱留強明細(右欄)+ AI 掃利空(LLM 第三維)
- ⚠️ 風控警示

§8.2 layer:L5 UI Tab section helper(🟡 中風險:約 290 LOC,
跨 L1 fetcher / L2 calc / L3 service)。

對外 API:
- render_portfolio_summary_section(*, gemini_call_fn) -> dict
  回傳 {results_t3, score_t3, risk_alerts, fund_map};
  上游(批次財報體檢 / AI 投資組合)接此 dict 為輸入。
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
# I1:「多因子總分能不能算」的唯一判定(L0,H1)。本檔用它把「排行是空的」三態分開:
# 計算中 / 總經未評估(不會自己算完)/ 真的沒有可評分的檔。
from shared.scoring_regime_gate import resolve_scoring_regime
from shared.signal_thresholds import (
    GRP_NEWS_BEARISH_CONFIDENCE_MIN,
    MULTIFACTOR_ENTRY_MIN,
)
from shared.stock_buckets import classify_pb_level, get_pb_bands
from src.compute.screener.scorability import CandidateStats, summarize_candidates
from src.compute.scoring import (
    evaluate_exit_signals,
    judge_news_sentiment_cached,
)
from src.config import WEIGHT_TABLES
from src.data.news import fetch_stock_news as _fetch_stock_news
from src.data.stock.app_stock_fetchers import (
    fetch_dividend_data,
    fetch_quarterly,
    fetch_quarterly_extra,
)
from src.services.allocation_service import get_macro_regime
from src.services.stock_grp_service import (
    get_industry_category as fetch_industry_category,
)
from src.ui.render import (  # v19.174 去識別化：改吃策略代號常數 + 新函式名
    STRATEGY_TECHNICAL,
    STRATEGY_VALUATION,
    strategy_conclusion,
)
from src.ui.tabs.tab_helpers import final_recommendation


def render_portfolio_summary_section(
    *,
    gemini_call_fn: Callable[..., str],
) -> dict[str, Any]:
    """渲染 KPI banner + ⑤ + RS + ③④ + 風控警示。

    回傳 dict 給下游 section 用:
      - results_t3: list[dict] — 批次抓取結果
      - score_t3: list[dict] — 多因子評分
      - risk_alerts: list[str] — AI 風控警示
      - fund_map: dict[str, dict] — 基本面預計算結果(EPS / 毛利 / SQ / FGMS / P/B)

    若 session_state 無 t3_data → 回傳空 dict({})。
    """
    t3_data = st.session_state.get('t3_data')
    if not t3_data:
        return {}

    results_t3  = t3_data['results']
    score_t3    = t3_data['score_t3']
    risk_alerts = t3_data.get('risk_alerts', [])

    # ── 📊 投資組合綜合總結 banner(v18.327 PR-B 頂部 KPI 摘要)──
    # B5-b(2026-08):候選數改吃**單一來源** summarize_candidates(§2.1 SSOT)。
    # 舊版分子取自 score_t3、分母取自 results_t3 —— 兩個 list 長度不保證相等
    # (section_batch_fetcher 只在 K 線非空時才 append score_t3),於是同頁「≥70」
    # 出現兩個不同分母,再加上汰弱那處的第三種定義,三個數字互相否定。
    _stats = summarize_candidates(results_t3, score_t3)
    _total_n = _stats.n_total
    # 健康度平均只算「真的有健康度讀數」的檔(§1:缺讀數不以 0 充數拉低平均)
    _health_vals = [_h for _h in
                    ((_r.get('健康度') if isinstance(_r, dict) else None) for _r in results_t3)
                    if isinstance(_h, (int, float)) and not isinstance(_h, bool)]
    _avg_health = sum(_health_vals) / len(_health_vals) if _health_vals else None
    _score_map_kpi = {s.get('stock_id'): s for s in score_t3 if isinstance(s, dict)}
    _top_pick = max((_score_map_kpi[i] for i in _stats.scored_ids if i in _score_map_kpi),
                    key=lambda _s: _s.get('total', 0) or 0, default=None)
    _top_pick_str = (f"{_top_pick.get('stock_id', '—')} "
                     f"({_top_pick.get('total', 0):.0f}分)"
                     if _top_pick else '—')
    _risk_n = len(risk_alerts)
    _bk_c1, _bk_c2, _bk_c3, _bk_c4, _bk_c5 = st.columns(5)
    _bk_c1.metric('組合檔數', f'{_total_n} 檔',
                  delta=(f'⚪ {_stats.n_unscored} 檔無法評分'
                         if _stats.n_unscored else None),
                  delta_color='off',
                  help='本次批次分析涵蓋的股票數量;「無法評分」= 抓不到 K 線 / 評分失敗,'
                       '下方各表以「⚪ 無法評分」標示,不給假分數參與排序(§1)')
    if _avg_health is None:
        _bk_c2.metric('平均健康度', '—', delta='⚪ 無讀數', delta_color='off',
                      help='本批沒有任何一檔取得健康度讀數(§1:不以 0 充數)')
    else:
        _avg_health_color = ('🟢' if _avg_health >= HEALTH_GRADE_A_MIN
                             else '🟡' if _avg_health >= HEALTH_GRADE_B_MIN
                             else '🔴')
        _bk_c2.metric('平均健康度', f'{_avg_health:.0f}',
                      delta=_avg_health_color,
                      help=f'組合平均健康度(0-100);A 級≥{HEALTH_GRADE_A_MIN} / '
                           f'B 級≥{HEALTH_GRADE_B_MIN}。'
                           f'只平均「有讀數」的 {len(_health_vals)} 檔')
    _bk_c3.metric(f'多因子 ≥{MULTIFACTOR_ENTRY_MIN:.0f} 候選',
                  f'{_stats.n_entry_pass}/{_stats.n_scored}',
                  delta=(f'⚪ {_stats.n_unscored} 檔未列入'
                         if _stats.n_unscored else None),
                  delta_color='off',
                  help=f'多因子總分達 {MULTIFACTOR_ENTRY_MIN:.0f} 分以上的檔數(積極布局候選)。'
                       f'**分母 = 可評分檔數**(與下方「③ 多因子評分排行」表列數同一母體);'
                       f'抓不到 K 線的檔不列入分子也不列入分母')
    _bk_c4.metric('最強檔', _top_pick_str,
                  help='多因子總分最高的代碼(只在可評分檔中取)')
    _bk_c5.metric('風控警示', f'{_risk_n} 項',
                  delta=('🔴 注意' if _risk_n > 0 else '🟢 清淡'),
                  delta_color='inverse',
                  help='系統觸發的風控警示數量(下方有詳情)')

    # ── 🔰 故事化白話:一張總表怎麼看(v19.164 合併版)──
    with st.expander('🔰 這頁怎麼看?一張「組合排行總表」搞懂'):
        st.markdown('''下方**「🏆 組合排行總表」一檔一列**,把原本散落的最終建議、多因子排行、汰弱留強
合成一張,依「綜合建議 → 多因子」排序,**開頁 3 秒**看出哪幾檔積極、哪幾檔該汰:

| 欄位 | 看什麼 |
|---|---|
| **綜合建議** | 健康＋多因子＋357 三重確認 → 積極／觀察／等待 |
| **多因子**(0~100) | 趨勢＋動能＋籌碼＋量價＋風險＋基本面 六因子加權(權重 SSOT `config.WEIGHT_TABLES`),偏「**現在強不強**」;抓不到 K 線 → 「⚪ 無法評分」不給假分 |
| **健康度** | 均線／RSI／KD／量比／布林,偏「**體質好不好**」 |
| **出場** | 技術＋籌碼(＋AI 利空)三維出場訊號 X/3 |
| **型態／風報比** | K 線型態學等幅滿足的目標與風報比(完整見「🎯 型態目標價」) |
| **EPS／毛利／殖利／P/B** | 基本面對照(各只出現這一次) |

- **多因子子維度**(趨勢／動能／籌碼／量價／風險 個別分數)在下方「📈 多因子維度拆解」展開。
- **逐檔技術明細**(RSI／KD／量比／357／VCP／合約負債…)在「🩹 逐檔技術明細」展開。
- **財報體質(趨勢×轉機、找體質差→變好)**在更下方「📊 財報趨勢×轉機」區塊。

> 💡 多因子＋健康度都排前面＝「強上加強」優先觀察;體質好但動能弱的可留意打底。''')

    # ── 預先計算基本面(③④⑤ 共用)─────────────────────────
    _fund_map = _precompute_fund_map(results_t3)

    # ── 🏆 組合排行總表(v19.164 合併 ③④⑤,一檔一列,每個 headline 欄只出現一次)──
    _render_master_table(results_t3, score_t3, _fund_map, _stats)

    # ── 🎯 型態目標價(全組合,共用批次來源;逐檔看圖下鑽,非第二輸入)──
    _render_pattern_batch(results_t3, score_t3)

    # ── 明細 drill-down(需要才展開,不佔首屏)──────────────────────
    if score_t3 and len(score_t3) >= 2:
        with st.expander('📈 多因子維度拆解（趨勢／動能／籌碼／量價／風險）— 上表「多因子」欄的拆解',
                         expanded=False):
            _render_multifactor_dims(score_t3)
    with st.expander('📋 多因子評分排行 + 基本面明細（EPS／毛利／SQ品質／FGMS前瞻／殖利／P/B）',
                     expanded=False):
        _render_multifactor_ranking(score_t3, _fund_map, _stats)
    with st.expander('🩹 逐檔技術明細（RSI／KD／量比／IBS／VCP／357／合約負債／操作狀態）＋ 🤖 AI 掃利空',
                     expanded=False):
        _render_elimination_detail(
            results_t3, _fund_map, _stats, gemini_call_fn=gemini_call_fn)

    st.markdown('---')

    # ── 風控警示 ────────────────────────────────────────────
    if risk_alerts:
        st.markdown('#### ⚠️ 風控警示')
        for alert in risk_alerts:
            st.warning(alert)

    return {
        'results_t3': results_t3,
        'score_t3': score_t3,
        'risk_alerts': risk_alerts,
        'fund_map': _fund_map,
    }


def _precompute_fund_map(results_t3: list[dict]) -> dict[str, dict]:
    """逐檔抓季報 + 股利 + SQ + FGMS + P/B → 拼成 6 欄基本面 dict。

    供 ⑤ 最終建議 + ③ 排行表 + ④ 汰弱明細 + AI 投資組合 4 處共用。
    """
    _fund_map: dict[str, dict] = {}
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
            _gc3 = '毛利率' if '毛利率' in _qtr3.columns else None  # 精確比對,避免命中'毛利率名稱'
            if _ec3:
                _es3 = pd.to_numeric(_qtr3[_ec3].tail(4), errors='coerce').dropna()
                if len(_es3) >= 1:
                    _eps3 = round(float(_es3.sum()), 2)
            if _gc3:
                _gs3 = pd.to_numeric(_qtr3[_gc3], errors='coerce').dropna()
                if len(_gs3) >= 1:
                    _gp3 = round(float(_gs3.iloc[-1]), 1)
        # 獲利品質得分 (SQ)
        _sq3 = None
        try:
            from src.compute.scoring import calc_quality_score as _cqs3
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
            from src.compute.scoring import calc_forward_momentum_score as _cfgms3
            _is_fin3 = bool(_qtr3['是否金融股'].iloc[0]) if _qtr3 is not None and '是否金融股' in _qtr3.columns else False
            _fg_r3 = _cfgms3(_qtr3, _qex3, is_finance=_is_fin3)
            if _fg_r3.get('fgms') is not None:
                _fgms3 = f"{_fg_r3['fgms']:.0f}({_fg_r3['fgms_label']})"
        except Exception:
            pass
        # P/B 估值分級(SSOT: shared.stock_buckets + data_loader)
        _pb_eval3 = '-'
        try:
            _price_num3 = float(str(_r3.get('現價', '0')).replace(',', ''))
            if _price_num3 > 0:
                # C4(v19.197):P/B 改走 SSOT get_pb_ratio(TWSE 官方 PBratio T1 → FinMind BS T2),
                # 與單檔頁同源;原本只用 FinMind fetch_bps(T2)→ 同股跨頁 P/B 帶可能不一致(§2.1)。
                from src.data.stock.yield_pe_fetcher import get_pb_ratio
                _pb_raw3 = get_pb_ratio(_sid3, _price_num3).get('pb')
                if _pb_raw3 and _pb_raw3 > 0:
                    _ind3 = fetch_industry_category(_sid3)
                    _bands3 = get_pb_bands(_ind3)
                    _pb_eval3 = f'{_pb_raw3:.2f} {classify_pb_level(_pb_raw3, _bands3)}'
        except Exception:
            pass
        # §4.1(2026-08 稽核)殖利率單位修正:_avg3 = 年均現金股利(**元**,fetch_dividend_data
        # 首元素),原本直接印成「殖利率%」→ 台積電印 13.7「%」其實是 13.7 元(真殖利率
        # 0.58%,差 ~23×)。改算真殖利率 = 年均股利 ÷ 現價 × 100(現價已在 _r3)。
        _price_yld3 = None
        try:
            _price_yld3 = float(str(_r3.get('現價', '0')).replace(',', ''))
        except (TypeError, ValueError):
            _price_yld3 = None
        _yield3 = (round(_avg3 / _price_yld3 * 100, 2)
                   if (_avg3 and _price_yld3 and _price_yld3 > 0) else None)
        _fund_map[_sid3] = {
            '近4季EPS': f'{_eps3:.2f}' if _eps3 is not None else '-',
            '毛利率%':  f'{_gp3:.1f}'  if _gp3  is not None else '-',
            '殖利率%':  f'{_yield3:.2f}' if _yield3 is not None else '-',
            'SQ評分':   _sq3   if _sq3   is not None else '-',
            'FGMS':     _fgms3 if _fgms3 is not None else '-',
            'P/B評價':  _pb_eval3,
        }
    return _fund_map


def _render_master_table(
    results_t3: list[dict],
    score_t3: list[dict],
    fund_map: dict[str, dict],
    stats: CandidateStats,
) -> None:
    """🏆 組合排行總表(v19.164 合併 ③④⑤)— 一檔一列,依綜合建議 → 多因子排序。

    每個 headline 欄只出現一次(去重 EPS/毛利/殖利/健康度/評級/多因子);技術明細、
    多因子子維度、型態完整欄改由下方 expander 展開。§1:型態風報比缺 → 「—」不腦補。

    B5-b(2026-08)§1:抓不到 K 線 → 多因子欄留白、綜合建議標「⚪ 無法評分」。
    舊版走 `score_map.get(sid, {}).get('total', 0)` → 缺分當 0 分,再餵給
    `final_recommendation` 算出「🔴 等待」—— 那是「評過了,很差」,不是「沒得評」。
    """
    if not results_t3:
        return
    score_map = {s['stock_id']: s for s in score_t3 if isinstance(s, dict) and 'stock_id' in s}
    _prio = {'積極': 0, '觀察': 1, '等待': 2}
    rows = []
    for r in results_t3:
        sid = r.get('stock_id', r.get('代碼', ''))
        _scored = stats.is_scored(str(sid))
        if _scored:
            rec_label, _ = final_recommendation(r, score_map)
            rec_word = rec_label.split()[-1] if rec_label else ''
            mf = float(score_map.get(sid, {}).get('total', 0) or 0)
            _mf_cell = round(mf, 0)
            _prio_v = _prio.get(rec_word, 3)
        else:
            # NaN(非 None):讓「多因子」欄維持 float dtype → sort_values 不會拿
            # None 跟 float 比較而 TypeError;ProgressColumn 對 NaN 一律留白。
            rec_label, _mf_cell, _prio_v = '⚪ 無法評分', float('nan'), 9
        cs = r.get('_pattern') or {}   # v19.174 去識別化:欄名原帶人名羅馬拼音
        rr = cs.get('rr')
        ev = evaluate_exit_signals(r.get('_ex_tech'), r.get('_ex_chip_sig', ''), None)
        fd = fund_map.get(sid, {})
        _health_raw = r.get('健康度')
        _health_ok = isinstance(_health_raw, (int, float)) and not isinstance(_health_raw, bool)
        rows.append({
            '代碼': sid, '名稱': r.get('名稱', sid) or sid, '現價': r.get('現價', '-'),
            '綜合建議': rec_label,
            '多因子': _mf_cell,
            '評級': r.get('評級', '-'),
            '健康度': float(_health_raw) if _health_ok else float('nan'),
            '出場': f'{ev["icon"]} {ev["score"]}/3',
            '型態': cs.get('pattern') or '—',
            '風報比': f'{rr:.2f}' if isinstance(rr, (int, float)) else '—',
            # ── T4(2026-08)錨點型價位:三欄都**因股而異**,才有比較價值 ──
            # 刻意**不放**停利價與固定盈虧比:tab_stock.py:648-677(v19.179 B1-b)
            # 已證明 RR=(P×1.05−P)/(P−P×0.92)=0.625,P 完全約掉 ⇒ 20 列會印同一個數。
            '絕對停損': _fmt_abs_stop(r),
            '停損RR': (f'{r["_rr_anchor"]:.2f}'
                       if isinstance(r.get('_rr_anchor'), (int, float)) else '—'),
            '距支撐': (f'{r["_sr_dist_sup"]:+.1f}%'
                       if isinstance(r.get('_sr_dist_sup'), (int, float)) else '—'),
            'EPS(4Q)': fd.get('近4季EPS', '-'),
            '毛利%': fd.get('毛利率%', '-'),
            '殖利%': fd.get('殖利率%', '-'),
            'P/B': fd.get('P/B評價', '-'),
            '_p': _prio_v,
        })
    df = (pd.DataFrame(rows)
          .sort_values(['_p', '多因子'], ascending=[True, False], na_position='last')
          .drop(columns=['_p']).reset_index(drop=True))
    st.markdown('#### 🏆 組合排行總表')
    st.caption('一檔一列,3 秒看出「哪幾檔積極、哪幾檔該汰」:綜合建議 → 多因子 → 健康度 → 出場 → '
               '型態/風報比 → 基本面。每個欄位只出現一次(明細見下方展開區)。'
               '「⚪ 無法評分」= 抓不到 K 線 / 評分失敗,多因子欄留白排最後,'
               '**不以 0 分冒充「很弱」**(§1)。')
    if stats.n_unscored:
        st.caption(f'⚪ 本批 {stats.n_unscored} 檔無法評分:'
                   f'{"、".join(c for c in stats.unscored_ids if c)}'
                   f'(這些檔不列入上方「多因子 ≥{stats.entry_min:.0f} 候選」的分子與分母)')
    st.dataframe(df, use_container_width=True, hide_index=True, column_config={
        '多因子': st.column_config.ProgressColumn('多因子', min_value=0, max_value=100, format='%.0f'),
        '健康度': st.column_config.NumberColumn('健康度', format='%d 🏥'),
        '出場': st.column_config.TextColumn('出場', help='技術+籌碼二維;利空新聞第三維在下方「逐檔技術明細」按「AI 掃利空」'),
        '型態': st.column_config.TextColumn('型態'),
        '風報比': st.column_config.TextColumn(
            '風報比',
            help='**型態**等幅滿足推算;型態未明→「—」不給假高值。'
                 '與右方「停損RR」錨點不同 —— 這個看型態目標,那個看紅K低點。'),
        # ── T4(2026-08)三個錨點型欄位 ──────────────────────────
        '絕對停損': st.column_config.TextColumn(
            '絕對停損',
            help='近 20 根紅K中**最大量**那根的低點再往下 0.5%,括號為距現價%。\n\n'
                 '這是各股自己的價量結構位置,不是「現價 −8%」那種固定倍數。\n\n'
                 '找不到大量紅K → 「—」。§1:**不**退回固定 −8% 冒充錨點。'),
        '停損RR': st.column_config.TextColumn(
            '停損RR',
            help='(停利目標1 − 現價) ÷ (現價 − 絕對停損)。\n\n'
                 '⚠️ 與「風報比」是**兩個不同的東西**:本欄分母是**紅K低點**,'
                 '故因股而異;個股頁另有一個「固定方案盈虧比」恆為 0.625'
                 '(現價在分子分母約掉),那個放進比較表沒有意義,故本表不列。\n\n'
                 '現價已跌破紅K低點 → 「—」(分母為負,舊版會噴出數千倍假數字)。'),
        '距支撐': st.column_config.TextColumn(
            '距支撐',
            help='現價距**近 20 個交易日**最低點的百分比。正值 = 支撐在下方。\n\n'
                 '⚠️ 這裡的「20」與「絕對停損」欄的「20」意思不同:'
                 '本欄是最後 20 根 **K 線**,那欄是最後 20 根 **紅 K**(可能橫跨數月)。'),
        'P/B': st.column_config.TextColumn('P/B 估值'),
    })


def _fmt_abs_stop(row: dict) -> str:
    """T4：絕對停損價 + 距現價% 合成一格（`89.55 (-10.4%)`）。

    §1：`_abs_stop` 為 None（近 20 根紅K無有效成交量）→ 回「—」，
    **不可**退回固定 −8% —— 那是現價的固定倍數，會讓這一欄退化成
    「每檔都一樣」的假錨點（v19.179 B1-b 就是在修這個）。

    距離為負代表現價已跌破停損線，是**有意義的狀態**（該出場了），
    照樣顯示，不當成錯誤。

    2026-08 稽核修：距離為負(現價已跌破紅K低點錨,停損價反在現價之上)時,原本只印
    `314.69 (-17.2%)`,讀起來像「停損價高於現價」的壞資料。改前綴 `🚨已跌破` 明示
    這是「早該出場」狀態(對齊個股單檔頁 section_health_score 的 🚨已跌破 三態)。
    """
    _stop = row.get('_abs_stop')
    if not isinstance(_stop, (int, float)):
        return '—'
    _dist = row.get('_stop_dist_pct')
    if not isinstance(_dist, (int, float)):
        return f'{_stop:.2f}'
    if _dist < 0:
        # 現價已跌破紅K低點錨 → 停損價在現價之上 = 早該出場,明示不誤讀為壞資料
        return f'🚨已跌破 {_stop:.2f} ({_dist:+.1f}%)'
    return f'{_stop:.2f} ({_dist:+.1f}%)'


_MF_DIMS = (('趨勢', 'trend'), ('動能', 'momentum'), ('籌碼', 'chip'),
            ('量價', 'volume'), ('風險', 'risk'))
"""多因子子維度顯示欄 → `score_single_stock()` 實際回傳的 key(§2.1 SSOT,禁止亂猜 key)。

B5-b(2026-08)刪掉的舊欄:`'RS': r.get('rs_score', 50)` —— `score_single_stock`
**從來沒有**回傳 `rs_score`/`rs_up`,所以那一欄恆為捏造的 50(還畫成進度條),
而「📊 RS 曲線向上」提示是永不觸發的死碼。多因子總分本來就不含 RS
(見 `scoring_engine.stock_score`:趨勢/動能/籌碼/量價/風險/基本面 六因子)。
基本面因子(月營收 YoY)目前未被 `score_single_stock` 回傳個別分數 → 不列(不捏造)。
"""


def _batch_scoring_regime(score_t3: list[dict]) -> tuple[str | None, str]:
    """本批分數**實際使用**的 regime → `(regime, 說不出來的原因)`。

    I1 2026-08-10。來源 = `score_single_stock()` 回傳 dict 上的 `'regime'` 欄
    —— 評分當下就蓋上去的戳記(§2.2 provenance)。

    **刻意不在渲染時重讀一次總經**:那描述的是「現在的市場」,不是「螢幕上這些
    數字是用什麼算出來的」。使用者跑完批次再去開 🌍 總經頁,兩者立刻分岔,
    caption 就會再一次宣稱一組不是真的用過的權重 —— 正是本次要修的那個病。
    (現在與當下總經的落差另外揭露,見 `_render_multifactor_ranking`。)

    Returns:
        `(regime, '')` 可宣告;`(None, 原因)` 不可宣告 —— 此時 caller **不得**
        退回任何一組權重當展示值(§1)。
    """
    _rows = [s for s in (score_t3 or []) if isinstance(s, dict) and 'error' not in s]
    if not _rows:
        return None, '本批沒有任何多因子評分結果'
    _regs = {str(s.get('regime') or '').strip().lower() for s in _rows}
    _regs.discard('')
    if not _regs:
        return None, ('評分結果未帶 regime 標記'
                      '(score_single_stock 的輸出契約變了?)')
    if len(_regs) > 1:
        # 同一批本來就只取一次 regime(section_batch_fetcher 全批共用一個判定),
        # 出現多個代表接線壞掉 —— 這種時候更不能挑一個印出來。
        return None, f'同一批出現多個 regime:{" / ".join(sorted(_regs))}(不該發生)'
    _r = _regs.pop()
    if _r not in WEIGHT_TABLES:
        return None, f'regime={_r!r} 在 config.WEIGHT_TABLES 找不到對應權重表'
    return _r, ''


def _no_multifactor_reason(stats: CandidateStats) -> tuple[str, str]:
    """「多因子排行是空的」的三態歸因 → `(結論句, 行動句)`。

    I1 2026-08-10:原文案固定是「多因子資料計算中 / 等待評分載入」。H1 之後
    **「總經未評估」也會讓 `score_t3` 為空**(§1 拒絕評分),那時「計算中」是錯的
    措辭 —— 它不會自己算完,使用者會一直等一件永遠不會發生的事,而真正該做的動作
    (去開 🌍 總經頁)完全沒被提到。
    """
    if stats.n_total == 0:
        return ('尚未執行批次分析(本頁目前沒有任何標的)',
                '在上方輸入股票代碼並執行批次分析')
    _dec = resolve_scoring_regime(get_macro_regime())
    if not _dec.usable:
        return (f'本批 {stats.n_total} 檔都沒有多因子總分 —— 目前總經狀態:{_dec.reason}',
                '按「🚀 一鍵更新全部數據」,或先開 🌍 總經頁讓紅綠燈算出結論後重跑批次'
                '(§1:總經沒有結論時任選一組權重都等於替你做大盤判斷,寧可不給)')
    return (f'本批 {stats.n_total} 檔全部無法評分'
            f'({stats.n_unscored} 檔抓不到 K 線 / 評分失敗)',
            '先確認 K 線來源(yfinance / FinMind)是否可用 —— 這**不會**自己算完')


def _render_multifactor_dims(score_t3: list[dict]) -> None:
    """📈 多因子維度拆解 — 主表「多因子」欄的子分數(唯一棲身)。"""
    _rows = [r for r in (score_t3 or [])
             if isinstance(r, dict) and 'error' not in r and r.get('stock_id')]
    if not _rows:
        # I1:原文案「多因子維度資料載入中」—— 能走到這裡代表 score_t3 有東西
        # (caller 已 `len(score_t3) >= 2`)但每一列不是帶 error 就是沒有代碼,
        # 也就是**已經算完而且失敗了**,不是還在載入。
        st.info('本批的多因子評分結果全部帶錯誤或缺代碼,沒有子維度可拆解'
                '(不是還在計算)')
        return
    _sdf = pd.DataFrame([
        {'代碼': r['stock_id'], '總分': r.get('total', 0),
         **{_label: r.get(_key) for _label, _key in _MF_DIMS}}
        for r in _rows
    ]).sort_values('總分', ascending=False)
    _cols = [_label for _label, _ in _MF_DIMS]
    _pivot = _sdf.set_index('代碼')[_cols]
    st.dataframe(_pivot, use_container_width=True, column_config={
        c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format='%.0f')
        for c in _cols})
    st.caption('五欄為 `score_single_stock()` 實際回傳的子分數;'
               '多因子總分另含「基本面(月營收 YoY)」因子,該因子未回傳個別分數故不列'
               '(§1:不補一個看起來合理的數字)。加權權重見下方「③ 多因子評分排行」。')


def _fmt_pattern(x, fmt: str = '%.2f') -> str:
    """數值 → 字串;None/非數 → 「—」(§1 不腦補)。v19.174 去識別化:原函式名帶人名羅馬拼音。"""
    return (fmt % x) if isinstance(x, (int, float)) else '—'


def _render_pattern_batch(
    results_t3: list[dict],
    score_t3: list[dict],
) -> None:
    """🎯 型態目標價(全組合)— v19.164 批次化,共用上方批次的 K 線來源。

    每檔在 run_batch_fetch 內已用 df4 就地算好(存 `_pattern`),此處只渲染。
    §1 誠實:擺動點不足 / 型態未明 → 標「—」不腦補;下鑽線圖共用批次 df(同源同數)。
    """
    if not results_t3:
        return
    st.markdown('#### 🎯 型態目標價（全組合）')
    st.caption('共用上方批次的 10 檔 K 線自動算,**無需再選標的**。§1:擺動點不足 / 型態未明 → '
               '「—」不給假目標;距甜蜜價% 負=待突破、正=已突破。')
    rows = []
    for r in results_t3:
        sid = r.get('stock_id', r.get('代碼', ''))
        cs = r.get('_pattern') or {}   # v19.174 去識別化:欄名原帶人名羅馬拼音
        _dist = cs.get('dist_pct')
        if _dist is None:
            _dist_s = '—'
        else:
            _dist_s = f'{_dist:+.1f}% ' + ('已突破' if _dist >= 0 else '待突破')
        rows.append({
            '代碼': sid, '名稱': r.get('名稱', sid) or sid,
            '型態': cs.get('pattern') or '—',
            '甜蜜價': _fmt_pattern(cs.get('sweet')),
            '距甜蜜價%': _dist_s,
            '止損': _fmt_pattern(cs.get('stop')),
            '目標①': _fmt_pattern(cs.get('target1')),
            '風報比': _fmt_pattern(cs.get('rr'), '%.2f'),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── 逐檔看圖下鑽(選一檔看 K 線 + 手動微調;非第二輸入,標的仍是上方 10 檔)──
    _ordered = [s['stock_id'] for s in sorted(
        score_t3, key=lambda x: x.get('total', 0) or 0, reverse=True)]
    _codes = _ordered + [r.get('stock_id', r.get('代碼', ''))
                         for r in results_t3
                         if r.get('stock_id', r.get('代碼', '')) not in _ordered]
    _codes = [c for c in _codes if c]
    if not _codes:
        return
    with st.expander('🔎 看某一檔的型態線圖 + 手動微調關鍵點（從上方 10 檔挑一檔看圖）',
                     expanded=False):
        _sel = st.selectbox('看哪一檔的型態線圖', _codes, key='_csgrp_drill')
        _pre_df = None
        try:
            from shared.app_cache import _load_cache
            _cache = _load_cache('t3v2', _sel, ttl_hours=4)
            _pre_df = (_cache or {}).get('df')
        except Exception:
            _pre_df = None
        from src.ui.tabs.pattern_targets_ui import render_pattern_targets_for_ticker
        render_pattern_targets_for_ticker(_sel, key_prefix='cs_grp', preloaded_df=_pre_df)

        # ── T4-2(2026-08)VCP + 布林:**複用同一個 selectbox**,不另開選擇器 ──
        # 單筆頁的 `render_vcp_bollinger_section` 直接吃 (sid, vcp, bb) 三個值,
        # 而 vcp / bb 在 run_batch_fetch:158-159 就已算好並存進 `_vcp` / `_bb`
        # ⇒ 這裡零計算、零抓取,純渲染(同 `_pattern` 的 v19.164 範式)。
        #
        # 為什麼掛在型態下鑽底下而不是自成一區:使用者已經在這裡選好標的了,
        # 再給第二個「看哪一檔的 VCP」選擇器 = 同一件事問兩次
        # (user 2026-08 明確要求「簡化選項與功能」)。
        _sel_row = next((r for r in results_t3
                         if str(r.get('stock_id', r.get('代碼', ''))) == str(_sel)), None)
        if _sel_row is not None:
            _vcp_d, _bb_d = _sel_row.get('_vcp'), _sel_row.get('_bb')
            if _vcp_d or _bb_d:
                st.markdown('---')
                from src.ui.tabs.stock_sections import render_vcp_bollinger_section
                render_vcp_bollinger_section(_sel, _vcp_d, _bb_d)
            else:
                # §1:算不出來要說,不可留白讓人以為「這檔沒型態問題」
                st.caption(f'⚪ {_sel} 的 VCP / 布林未計算'
                           '（K 線不足 30 根，或該檔抓取失敗）。')


def _render_multifactor_ranking(
    score_t3: list[dict],
    fund_map: dict[str, dict],
    stats: CandidateStats,
) -> None:
    """③ 多因子評分排行(左欄)。

    B5-b(2026-08):結論句的「N/M 支≥70分」改吃 `stats`(與頂部 KPI 同一份),
    舊版自己重算一次且分母用 `len(score_t3)`,與 KPI 的 `len(results_t3)` 打架。
    """
    st.markdown('##### ③ 多因子評分排行')
    # ── I1 §1:權重 caption 必須是**這批分數真的用過**的那一組 ──────────────
    # 原碼 `_w = WEIGHT_TABLES['neutral']` + 字串寫死「(neutral 權重)」:
    # regime=bull 時畫面上的分數確實是用 bull 權重算的,caption 卻宣稱中性
    # —— 說明文字與數字來自兩個不同的 regime,而使用者只看得到說明文字。
    _reg, _reg_why = _batch_scoring_regime(score_t3)
    if _reg:
        _w = WEIGHT_TABLES[_reg]
        st.caption(
            f"趨勢×{_w['trend']:.2f} + 動能×{_w['momentum']:.2f} + 籌碼×{_w['chip']:.2f} + "
            f"量價×{_w['volume']:.2f} + 風險×{_w['risk']:.2f} + 基本面×{_w['fundamental']:.2f}"
            f"({_reg} 權重 — 本批評分**當下實際採用**的那一組,SSOT 來自 config.WEIGHT_TABLES)"
        )
    else:
        st.caption(f'⬜ 本批沒有可宣告的加權權重:{_reg_why}。'
                   '(§1:多因子權重是總經 regime 的函數,不知道實際用了哪一組時,'
                   '寧可不寫,也不挑一組數字給你看)')
    # 批次跑完之後總經才變 → 螢幕上的排名是舊 regime 算的。不講,使用者會拿它跟
    # 頁面其他地方(建議持股 / 紅綠燈)的新 regime 對照,得到一個同頁互相矛盾的畫面。
    if _reg:
        _cur = resolve_scoring_regime(get_macro_regime())
        if _cur.usable and _cur.regime != _reg:
            st.warning(f'⚠️ 這份排行是用「{_reg}」權重算的,但目前總經 regime 已經是'
                       f'「{_cur.regime}」—— 權重表不同,名次可能已經換人。'
                       f'請重跑一次批次分析再據此決策。')
    st.caption('🔰 另三欄基本面白話:SQ品質分＝獲利品質(賺得乾不乾淨)、FGMS前瞻＝前瞻成長動能(未來成長力道),皆 0~100 越高越好;EPS／毛利率／殖利率為對照。')
    from src.compute.scoring import rank_stocks as _rk3
    _ranked3 = _rk3(score_t3 or [])       # 與 stats.n_scored 同一條篩選規則(丟掉 error 列)
    _top_score_r = _ranked3[0] if _ranked3 else None
    _entry_txt = f'{stats.entry_min:.0f}'
    if _top_score_r:
        _mf3c = (f'最高分 {_top_score_r["stock_id"]} {_top_score_r.get("total", 0):.0f}分,'
                 f'{stats.n_entry_pass}/{stats.n_scored} 支≥{_entry_txt}分')
        if stats.n_unscored:
            _mf3c += f'(另 {stats.n_unscored} 檔無法評分,未列入)'
        _mf3a = f'≥{_entry_txt}分方可列入候選,其餘繼續觀察'
    else:
        # I1:三態歸因(尚未執行 / 總經未評估 / 真的沒有可評分的檔),取代原本
        # 一律「多因子資料計算中 + 等待評分載入」的錯誤措辭。
        _mf3c, _mf3a = _no_multifactor_reason(stats)
    st.markdown(strategy_conclusion(STRATEGY_VALUATION, '多因子總分排行', _mf3c, _mf3a), unsafe_allow_html=True)
    if _ranked3:
        _rank_rows = []
        for _ri, _r in enumerate(_ranked3):
            _sid_r = _r.get('stock_id','')
            _fd = fund_map.get(_sid_r, {})
            _rank_rows.append({
                '排名': _ri + 1, '代碼': _sid_r,
                '名稱': (_r.get('stock_name','') or '')[:6],
                '總分': _r.get('total', 0),
                '近4季EPS': _fd.get('近4季EPS', '-'),
                '毛利率%':  _fd.get('毛利率%',  '-'),
                'SQ評分':   _fd.get('SQ評分',   '-'),
                'FGMS前瞻': _fd.get('FGMS',     '-'),
                '殖利率%':  _fd.get('殖利率%',  '-'),
                'P/B評價':  _fd.get('P/B評價',  '-'),
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
                         'P/B評價':  st.column_config.TextColumn('P/B 估值(產業帶狀)'),
                     })
    else:
        # I1:同上三態 —— 這裡與上方結論句是**同一個** `_ranked3` 為空的分支
        # (`_top_score_r = _ranked3[0] if _ranked3 else None`),直接沿用同一份文字,
        # 不重算一次(也避免兩處各自去讀一次總經而講出不同的話)。
        # 原文案「多因子評分資料載入中」在「總經未評估」時是假的:沒有任何背景工作會把它算完。
        st.info(f'{_mf3c}。{_mf3a}')


def _render_elimination_detail(
    results_t3: list[dict],
    fund_map: dict[str, dict],
    stats: CandidateStats,
    *,
    gemini_call_fn: Callable[..., str],
) -> None:
    """④ 汰弱留強明細(右欄)+ AI 掃利空。

    B5-b(2026-08)§1:淘汰/保留改吃 `stats`(單一來源)。舊版:
      `_elim_n = sum(1 for r in results_t3 if r.get('健康度', 100) < HEALTH_GRADE_B_MIN ...)`
    —— 健康度缺讀數時預設**滿分 100** → 直接判「保留」,而同檔 KPI/總表對同一欄
    卻預設 0。一個欄位、同一頁、兩個方向相反的預設值,是「假綠燈」的引信。
    現在缺讀數 = 既不 kept 也不 eliminated,明講「N 檔健康度無讀數,未判定」。
    """
    st.markdown('##### ④ 汰弱留強明細')
    st.caption('健康度 · 357評價 · VCP · KD · RSI')
    _elim_n, _keep_n = stats.n_eliminated, stats.n_kept
    _unknown_n = stats.n_health_unknown
    _thr_txt = f'{stats.health_min:.0f}'
    if _elim_n > 0:
        _e4c = f'{_elim_n} 支被淘汰(健康<{_thr_txt} 或 357超貴),剩 {_keep_n} 支候選'
        _e4a = f'只看留下的 {_keep_n} 支,被淘汰直接跳過'
    elif _keep_n > 0:
        _e4c = f'有讀數的 {_keep_n} 支全數通過汰弱篩選'
        _e4a = '品質整齊,可從多因子排行取前2~3支'
    else:
        _e4c = '本批沒有任何一支取得健康度讀數 → 無法判定汰弱'
        _e4a = '先確認 K 線/財報來源是否可用,不要當成「全數通過」'
    if _unknown_n:
        _e4c += f';另 {_unknown_n} 支健康度無讀數,未判定'
    st.markdown(strategy_conclusion(STRATEGY_TECHNICAL, f'汰弱留強(共 {stats.n_total} 支)', _e4c, _e4a), unsafe_allow_html=True)
    # ── 出場警示掃描鈕(利空新聞 LLM 第三維,按需觸發以省額度)──
    if not results_t3:
        return
    _scan_c1, _scan_c2 = st.columns([1, 3])
    with _scan_c1:
        _scan_news = st.button('🤖 AI 掃利空', key='_grp_scan_news',
                               help='對組合內每檔近期新聞做 Gemini 利空判讀(6h 快取)')
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
                _sent_map[_sidn] = (judge_news_sentiment_cached(gemini_call_fn, _sidn, _nmn, _titlesn)
                                    if _titlesn else None)
            except Exception:
                _sent_map[_sidn] = None
        _prog_n.empty()
        st.session_state['_grp_news_sent'] = _sent_map
    _grp_sent = st.session_state.get('_grp_news_sent', {})
    with _scan_c2:
        if _grp_sent:
            _nh = sum(1 for v in _grp_sent.values()
                      if v and v.get('label') == '利空' and v.get('confidence', 0) >= GRP_NEWS_BEARISH_CONFIDENCE_MIN)
            st.caption(f'✅ 已掃描;偵測 {_nh} 檔利空。出場欄＝三維計分(🔴3／🟠2／🟡1／🟢0)')
        else:
            st.caption('出場欄目前為「技術＋籌碼」兩維;按左鈕加入「利空新聞(LLM)」第三維')
    _elim_rows = []
    for _r3 in results_t3:
        _sid3 = _r3.get('stock_id', _r3.get('代碼',''))
        _row = {k: v for k, v in _r3.items() if not k.startswith('_') and k != 'stock_id'}
        _row.update(fund_map.get(_sid3, {}))
        _ev3 = evaluate_exit_signals(_r3.get('_ex_tech'),
                                     _r3.get('_ex_chip_sig', ''),
                                     _grp_sent.get(_sid3))
        _row['出場'] = f'{_ev3["icon"]} {_ev3["score"]}/3'
        _elim_rows.append(_row)
    # v18.322 Option A:舊評分退役 → ④ 汰弱留強改以「純健康度」排序(對齊頁面說明)
    # v19.164:身分/健康/出場/EPS/毛利/殖利 已在上方「組合排行總表」,此明細只留技術欄(去重)
    df_cmp = pd.DataFrame(_elim_rows).sort_values('健康度', ascending=False).reset_index(drop=True)
    if '名稱' not in df_cmp.columns and '代碼' in df_cmp.columns:
        df_cmp.insert(0, '名稱', df_cmp['代碼'])
    _col_order = [c for c in ['名稱','代碼','出場','操作狀態',
                               'RSI','KD','量比','IBS','趨勢','357評價','VCP','合約負債']
                  if c in df_cmp.columns]
    st.caption('身分/健康度/評級/EPS/毛利/殖利 已在上方組合排行總表,此處只列技術與籌碼明細(去重)。')
    st.dataframe(df_cmp[_col_order], use_container_width=True,
                 hide_index=True,
                 column_config={
                     '名稱':     st.column_config.TextColumn('名稱', width='small'),
                     '代碼':     st.column_config.TextColumn('代碼', width='small'),
                     '出場':     st.column_config.TextColumn('出場', width='small', help='三維出場訊號:🔴3=強烈出場 / 🟠2=建議減碼 / 🟡1=留意 / 🟢0=清淡(利空新聞需按「AI 掃利空」)'),
                 })
