"""src/ui/tabs/stock_grp_sections/section_ai_portfolio.py — AI 投資組合綜合判讀
(v18.417 Batch 7-5).

從 tab_stock_grp.py:89-199 抽出。Tab 三層化下層 AI 判讀。

聚合 5 個資料源:
- results_t3(批次抓取結果:健康度 / RSI / VCP / 外資 / ma_above)
- score_t3(多因子評分:總分 / 五維 / RS)
- _fund_map(基本面:EPS / 毛利 / 殖利率 / SQ / FGMS / P/B)
- _fh_t3_cached(財報體檢:DNA / 現金水位 / OCF / 負債比 / 雷達)
- session_state(mkt_info.regime + macro_state.exposure_limit_pct + risk_alerts)

→ build_structured_summary_prompt → Gemini → 顯示 / 快取至
st.session_state[_t3ai_key] 防 rerun 重打。

§8.2 layer:L5 UI Tab section helper(🔴 高風險:約 130 LOC,
依賴前 3 批 section 輸出 + AI 服務 + news fetcher)。

對外 API:
- render_ai_portfolio_section(*, results_t3, score_t3, risk_alerts,
                              fund_map, fh_cached, gemini_call_fn,
                              fetch_news_fn, build_prompt_fn) -> None
"""
from __future__ import annotations

from typing import Any, Callable

import streamlit as st


def render_ai_portfolio_section(
    *,
    results_t3: list[dict],
    score_t3: list[dict],
    risk_alerts: list[str],
    fund_map: dict[str, dict],
    fh_cached: dict[str, dict],
    gemini_call_fn: Callable[..., str],
    fetch_news_fn: Callable[..., Any],
    build_prompt_fn: Callable[..., str],
) -> None:
    """渲染 AI 投資組合綜合判讀(Tab 最下層 — 看完 raw data 才看 AI)。

    button 觸發 → 建 prompt → Gemini call → 寫 session_state cache(避免 rerun 重打)。
    若 cache 有,直接顯示;若無且 user 沒點,顯示 hint。
    """
    if not results_t3:
        return

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
        _t3ai_prompt = _build_portfolio_prompt(
            results_t3=results_t3,
            score_t3=score_t3,
            risk_alerts=risk_alerts,
            fund_map=fund_map,
            fh_cached=fh_cached,
            fetch_news_fn=fetch_news_fn,
            build_prompt_fn=build_prompt_fn,
        )
        with st.spinner('AI 基金經理人分析中(約 30 秒)...'):
            _t3ai_result = gemini_call_fn(_t3ai_prompt, max_tokens=2000)
        st.session_state[_t3ai_key] = _t3ai_result
    if _t3ai_cached:
        st.markdown(_t3ai_cached)
    elif not _t3ai_btn:
        st.caption('▲ 點擊上方按鈕,AI 將生成投資組合強弱排序矩陣與汰弱留強建議。')


def _build_portfolio_prompt(
    *,
    results_t3: list[dict],
    score_t3: list[dict],
    risk_alerts: list[str],
    fund_map: dict[str, dict],
    fh_cached: dict[str, dict],
    fetch_news_fn: Callable[..., Any],
    build_prompt_fn: Callable[..., str],
) -> str:
    """聚合 5 dict 為 3 段 prompt sections + news block,呼 build_structured_summary_prompt。"""
    _sc_map3 = {s.get('stock_id'): s for s in score_t3}
    _port_lines = []
    for _rp in results_t3:
        _sid_p = _rp.get('stock_id', _rp.get('代碼',''))
        _nm_p  = _rp.get('stock_name', _rp.get('名稱', _sid_p))
        _ht_p  = _rp.get('_health', 0)
        _sc_p  = _rp.get('total', _rp.get('健康度', 0))
        _fd_p  = fund_map.get(_sid_p, {})
        _fhp   = fh_cached.get(_sid_p, {})
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
        # v18.349 PR-O1:單位「張」(SSOT data_loader.py:286 /1000 後),原 /1e8「億」是錯誤假設元的舊 bug
        _port_lines.append(
            f"[{_sid_p} {_nm_p}] 健康度={_ht_p:.0f} 評分={_sc_p:.0f}{_dim_p} | "
            f"技術: 均線={_ma_p} RSI={_rsi_p} {_vcp_p} | "
            f"籌碼: 外資近20日{'買超' if _fb_p>0 else '賣超'}{abs(_fb_p):,.0f}張 | "
            f"基本面: EPS={_fd_p.get('近4季EPS','-')} 毛利={_fd_p.get('毛利率%','-')}% "
            f"殖利率={_fd_p.get('殖利率%','-')} SQ品質={_fd_p.get('SQ評分','-')} "
            f"FGMS={_fd_p.get('FGMS','-')} P/B={_fd_p.get('P/B評價','-')} | "
            f"財報體檢: DNA={_dna_p} 現金水位={_fhp.get('cash_ratio_value','-') if _fhp else '-'} "
            f"OCF={_fhp.get('ocf_value','-') if _fhp else '-'} 負債比={_fhp.get('debt_ratio_value','-') if _fhp else '-'} 雷達均分={_rad_avg_p}"
        )
    _reg_p = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
    _reg_txt_p = '多頭市場(積極操作)' if _reg_p == 'bull' else ('空頭市場(縮減部位)' if _reg_p == 'bear' else '震盪整理(謹慎觀望)')
    _exp_p = st.session_state.get('macro_state', {}).get('exposure_limit_pct', 'N/A')
    # ── 依綜合評分排出強弱順序(重用上方已算好的資料)──────────
    _ranked_t3 = sorted(
        results_t3,
        key=lambda _r: _r.get('total', _r.get('健康度', 0)) or 0,
        reverse=True,
    )
    _strong_lines = []
    for _ri, _rr in enumerate(_ranked_t3, 1):
        _sid_r = _rr.get('stock_id', _rr.get('代碼', ''))
        _nm_r  = _rr.get('stock_name', _rr.get('名稱', _sid_r))
        _sc_r  = _rr.get('total', _rr.get('健康度', 0)) or 0
        _ht_r  = _rr.get('_health', 0) or 0
        _ma_r  = '均線多頭排列' if (_rr.get('ma_above', 0) or 0) >= 2 else '均線空頭排列'
        _fb_r  = _rr.get('foreign_buy', 0) or 0
        # v18.349 PR-O1:單位「張」(同上),原 /1e8「億」是錯誤假設元的舊 bug
        _strong_lines.append(
            f"第{_ri}名 [{_sid_r} {_nm_r}] 綜合評分={_sc_r:.0f} 健康度={_ht_r:.0f} | "
            f"{_ma_r}、外資近20日{'買超' if _fb_r > 0 else '賣超'}{abs(_fb_r):,.0f}張"
        )
    _strong_str = '\n'.join(_strong_lines) if _strong_lines else '(沒有可排序的股票)'
    # ── 風險診斷字串(大盤格局 + 建議上限 + 系統風控警示)──────
    _risk_str = (
        f"目前大盤格局:{_reg_txt_p}\n"
        f"系統建議的持股上限:{_exp_p}%\n"
        "系統風控警示:\n"
        + ('\n'.join(f'⚠️ {_a}' for _a in risk_alerts) if risk_alerts else '(目前沒有觸發任何風控警示)')
    )
    # ── 時事新聞:抓組合中評分最高的 1~2 檔(重用排序結果)──────
    _news_blocks = []
    for _rn in _ranked_t3[:2]:
        _sid_news = _rn.get('stock_id', _rn.get('代碼', ''))
        _nm_news  = _rn.get('stock_name', _rn.get('名稱', _sid_news))
        if not _sid_news:
            continue
        _nblk = fetch_news_fn(_sid_news, _nm_news, 3)
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
    return build_prompt_fn(
        subject_title='我的個股組合',
        sections=_t3ai_sections,
        news_text=_t3_news_str,
        overall_question='這個組合整體狀況如何、要不要調整、最該注意什麼風險。',
    )
