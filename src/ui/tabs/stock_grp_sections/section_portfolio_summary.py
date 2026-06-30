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
from shared.signal_thresholds import (
    GRP_NEWS_BEARISH_CONFIDENCE_MIN,
    MULTIFACTOR_ENTRY_MIN,
)
from shared.stock_buckets import classify_pb_level, get_pb_bands
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
from src.services.stock_grp_service import (
    get_bps as fetch_bps,
    get_industry_category as fetch_industry_category,
)
from src.ui.render import teacher_conclusion
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
    _total_n = len(results_t3)
    _health_vals = [_r.get('健康度', 0) or 0 for _r in results_t3]
    _avg_health = sum(_health_vals) / _total_n if _total_n else 0
    _entry_pass_n = sum(1 for _s in score_t3
                        if (_s.get('total', 0) or 0) >= MULTIFACTOR_ENTRY_MIN)
    _top_pick = max(score_t3, key=lambda _s: _s.get('total', 0) or 0) if score_t3 else None
    _top_pick_str = (f"{_top_pick.get('stock_id', '—')} "
                     f"({_top_pick.get('total', 0):.0f}分)"
                     if _top_pick else '—')
    _risk_n = len(risk_alerts)
    _bk_c1, _bk_c2, _bk_c3, _bk_c4, _bk_c5 = st.columns(5)
    _bk_c1.metric('組合檔數', f'{_total_n} 檔',
                  help='本次批次分析涵蓋的股票數量')
    _avg_health_color = ('🟢' if _avg_health >= HEALTH_GRADE_A_MIN
                         else '🟡' if _avg_health >= HEALTH_GRADE_B_MIN
                         else '🔴')
    _bk_c2.metric('平均健康度', f'{_avg_health:.0f}',
                  delta=_avg_health_color,
                  help=f'組合平均健康度(0-100);A 級≥{HEALTH_GRADE_A_MIN} / '
                       f'B 級≥{HEALTH_GRADE_B_MIN}')
    _bk_c3.metric(f'多因子 ≥{MULTIFACTOR_ENTRY_MIN:.0f} 候選',
                  f'{_entry_pass_n}/{_total_n}',
                  help=f'多因子總分達 {MULTIFACTOR_ENTRY_MIN:.0f} 分以上的檔數(積極布局候選)')
    _bk_c4.metric('最強檔', _top_pick_str,
                  help='多因子總分最高的代碼')
    _bk_c5.metric('風控警示', f'{_risk_n} 項',
                  delta=('🔴 注意' if _risk_n > 0 else '🟢 清淡'),
                  delta_color='inverse',
                  help='系統觸發的風控警示數量(下方有詳情)')

    # ── 🔰 故事化白話:兩套評分一次搞懂(純疊加,零動計算)──
    with st.expander('🔰 這頁怎麼看?兩套排行 + 多因子一次搞懂'):
        st.markdown('''這頁同時用**兩套評分**幫你比較多檔股票,角度不同、互相參照:

| 排行 | 看什麼 | 白話 |
|---|---|---|
| **③ 多因子評分** | 趨勢＋動能＋籌碼＋量價＋RS 五項合成 | 偏「**現在強不強**」(短中期動能選股) |
| **④ 汰弱留強** | 健康度(均線／RSI／KD／量比／布林) | 偏「**體質好不好**」(淘汰技術面偏弱的) |

**多因子的 5 個分數(0~100,越高越好):**
- **趨勢**:均線排列是否偏多(站上均線、多頭排列)
- **動能**:近期上漲的力道(漲勢／RSI)
- **籌碼**:法人／主力是否買超
- **量價**:成交量與股價是否同步放大(量價配合)
- **RS 相對強度**:這檔相對大盤是強還是弱,**RS 越高＝跑贏大盤越多**

> 💡 兩套都排前面、且 RS 向上的＝「強上加強」優先觀察;體質好但動能弱的可留意打底。最終仍以最下方「⑤ 最終綜合建議」＋風控警示為準。''')

    # ── 預先計算基本面(③④⑤ 共用)─────────────────────────
    _fund_map = _precompute_fund_map(results_t3)

    # ── ⑤ 最終綜合建議卡 ──────────────────────────────────
    if results_t3:
        score_map = {s['stock_id']: s for s in score_t3}

        st.markdown('#### ⑤ 最終綜合建議')
        _rec_counts = {'積極': 0, '觀察': 0, '等待': 0}
        for _rr in results_t3:
            _rl, _ = final_recommendation(_rr, score_map)
            _rec_counts[_rl.split()[-1]] = _rec_counts.get(_rl.split()[-1], 0) + 1
        _active_n = _rec_counts.get('積極', 0)
        _wait_n = _rec_counts.get('等待', 0)
        if _active_n >= 2:
            _r5c = f'本批 {_active_n} 支達積極布局條件'
            _r5a = '可同步建倉,停損設健康度跌破50'
        elif _active_n == 1:
            _r5c = '僅 1 支達積極條件,其餘觀察或等待'
            _r5a = '單一標的建倉,其餘等訊號確認'
        else:
            _r5c = f'本批無積極訊號({_wait_n} 支等待),市場擇股難度高'
            _r5a = '空手等待,勿強求進場'
        st.markdown(teacher_conclusion('宏爺', f'健康+多因子+357三重確認,共 {len(results_t3)} 支', _r5c, _r5a), unsafe_allow_html=True)
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
        _rs_top = _sdf.iloc[0] if not _sdf.empty else None
        _rs_up_pre = [r['stock_id'] for r in score_t3 if r.get('rs_up')]
        if _rs_top is not None and _rs_up_pre:
            _rs27c = f'RS 最強 {_rs_top["代碼"]}({_rs_top["RS"]:.0f}分),{len(_rs_up_pre)} 支 RS 向上'
            _rs27a = '優先佈局 RS 向上標的,動能最強'
        elif _rs_top is not None:
            _rs27c = f'RS 最強 {_rs_top["代碼"]}({_rs_top["RS"]:.0f}分),無 RS 向上訊號'
            _rs27a = '等待突破,趨勢+動能>70再行動'
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
            st.success(f"📊 RS曲線向上(強勢動能):{' / '.join(_rs_up_list)}")

    st.markdown('---')

    # ── ③+④ 雙欄:多因子排行(含EPS/毛利率)vs 汰弱留強 ──
    col_left, col_right = st.columns([1, 1])

    with col_left:
        _render_multifactor_ranking(score_t3, _fund_map)

    with col_right:
        _render_elimination_detail(
            results_t3, _fund_map, gemini_call_fn=gemini_call_fn)

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
                _bps_v3 = fetch_bps(_sid3)
                if _bps_v3 > 0:
                    _pb_raw3 = _price_num3 / _bps_v3
                    _ind3 = fetch_industry_category(_sid3)
                    _bands3 = get_pb_bands(_ind3)
                    _pb_eval3 = f'{_pb_raw3:.2f} {classify_pb_level(_pb_raw3, _bands3)}'
        except Exception:
            pass
        _fund_map[_sid3] = {
            '近4季EPS': f'{_eps3:.2f}' if _eps3 is not None else '-',
            '毛利率%':  f'{_gp3:.1f}'  if _gp3  is not None else '-',
            '殖利率%':  f'{_avg3:.1f}' if _avg3  is not None else '-',
            'SQ評分':   _sq3   if _sq3   is not None else '-',
            'FGMS':     _fgms3 if _fgms3 is not None else '-',
            'P/B評價':  _pb_eval3,
        }
    return _fund_map


def _render_multifactor_ranking(
    score_t3: list[dict],
    fund_map: dict[str, dict],
) -> None:
    """③ 多因子評分排行(左欄)。"""
    st.markdown('##### ③ 多因子評分排行')
    _w = WEIGHT_TABLES['neutral']
    st.caption(
        f"趨勢×{_w['trend']:.2f} + 動能×{_w['momentum']:.2f} + 籌碼×{_w['chip']:.2f} + "
        f"量價×{_w['volume']:.2f} + 風險×{_w['risk']:.2f} + 基本面×{_w['fundamental']:.2f}"
        f"(neutral 權重,SSOT 來自 config.WEIGHT_TABLES)"
    )
    st.caption('🔰 另三欄基本面白話:SQ品質分＝獲利品質(賺得乾不乾淨)、FGMS前瞻＝前瞻成長動能(未來成長力道),皆 0~100 越高越好;EPS／毛利率／殖利率為對照。')
    _top_score_r = max(score_t3, key=lambda r: r.get('total', 0)) if score_t3 else None
    _pass70 = [r for r in score_t3 if r.get('total', 0) >= MULTIFACTOR_ENTRY_MIN]
    if _top_score_r:
        _mf3c = f'最高分 {_top_score_r["stock_id"]} {_top_score_r.get("total",0):.0f}分,{len(_pass70)}/{len(score_t3)} 支≥70分'
        _mf3a = '≥70分方可列入候選,其餘繼續觀察'
    else:
        _mf3c = '多因子資料計算中'
        _mf3a = '等待評分載入'
    st.markdown(teacher_conclusion('孫慶龍', '多因子總分排行', _mf3c, _mf3a), unsafe_allow_html=True)
    if score_t3:
        from src.compute.scoring import rank_stocks as _rk3
        _ranked3 = _rk3(score_t3)
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
        st.info('多因子評分資料載入中')


def _render_elimination_detail(
    results_t3: list[dict],
    fund_map: dict[str, dict],
    *,
    gemini_call_fn: Callable[..., str],
) -> None:
    """④ 汰弱留強明細(右欄)+ AI 掃利空。"""
    st.markdown('##### ④ 汰弱留強明細')
    st.caption('健康度 · 357評價 · VCP · KD · RSI')
    _elim_n = sum(1 for r in results_t3
                  if r.get('健康度', 100) < HEALTH_GRADE_B_MIN or '超貴' in str(r.get('357評價', '')))
    _keep_n = len(results_t3) - _elim_n
    if _elim_n > 0:
        _e4c = f'{_elim_n} 支被淘汰(健康<50 或 357超貴),剩 {_keep_n} 支候選'
        _e4a = '只看留下的 {_keep_n} 支,被淘汰直接跳過'.format(_keep_n=_keep_n)
    else:
        _e4c = f'本批 {len(results_t3)} 支全數通過汰弱篩選'
        _e4a = '品質整齊,可從多因子排行取前2~3支'
    st.markdown(teacher_conclusion('弘爺', f'汰弱留強(共 {len(results_t3)} 支)', _e4c, _e4a), unsafe_allow_html=True)
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
    df_cmp = pd.DataFrame(_elim_rows).sort_values('健康度', ascending=False).reset_index(drop=True)
    if '名稱' not in df_cmp.columns and '代碼' in df_cmp.columns:
        df_cmp.insert(0, '名稱', df_cmp['代碼'])
    _col_order = [c for c in ['名稱','代碼','現價','出場','操作狀態','健康度','評級',
                               'RSI','KD','量比','IBS','趨勢','357評價','VCP',
                               '合約負債','近4季EPS','毛利率%','殖利率%']
                  if c in df_cmp.columns]
    st.dataframe(df_cmp[_col_order], use_container_width=True,
                 hide_index=True,
                 column_config={
                     '名稱':     st.column_config.TextColumn('名稱', width='small'),
                     '代碼':     st.column_config.TextColumn('代碼', width='small'),
                     '現價':     st.column_config.TextColumn('現價'),
                     '出場':     st.column_config.TextColumn('出場', width='small', help='三維出場訊號:🔴3=強烈出場 / 🟠2=建議減碼 / 🟡1=留意 / 🟢0=清淡(利空新聞需按「AI 掃利空」)'),
                     '健康度':   st.column_config.NumberColumn('健康度',  format='%d 🏥'),
                     '近4季EPS': st.column_config.TextColumn('近4Q EPS'),
                     '毛利率%':  st.column_config.TextColumn('毛利率%'),
                     '殖利率%':  st.column_config.TextColumn('殖利率%'),
                 })
