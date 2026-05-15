"""ETF AI 教練 TAB — 從 etf_dashboard.py 抽出（PR P2-B Phase 6-D，收官）

依賴策略
========
- Top-level: streamlit
- 函式內 late import 5 個依賴：
  * stdlib: pandas
  * etf_dashboard.py 內部 helper (3):
    MACRO_ALLOC（常數）/ _fetch_news_for / macro_allocation_banner

呼叫端
======
- app.py 經 etf_dashboard re-export 取用
"""
from __future__ import annotations

import streamlit as st


def render_etf_ai(gemini_fn=None):
    # ─ Late imports（避免循環 import）─
    import pandas as pd
    from etf_dashboard import MACRO_ALLOC, _fetch_news_for, macro_allocation_banner

    mkt_info = st.session_state.get('mkt_info', {})
    regime   = mkt_info.get('regime', 'neutral')
    macro_allocation_banner(regime)

    st.markdown('### 🤖 ETF AI 綜合評斷')
    st.caption('整合 Tab ⑥⑦⑧ 分析結果，生成跨模組綜合建議。請先在各分頁執行分析。')

    # 讀取各 Tab 存入的資料
    single_d  = st.session_state.get('etf_single_data')
    port_d    = st.session_state.get('etf_portfolio_data')
    backtest_d= st.session_state.get('etf_backtest_data')

    has_data  = any([single_d, port_d, backtest_d])

    # ── 已有資料：顯示摘要 ───────────────────────────────────
    if has_data:
        st.markdown('#### 📊 已載入分析摘要')
        summary_rows = []
        if single_d:
            summary_rows.append({
                '來源': 'Tab⑥ 單支診斷',
                '內容': f'{single_d["ticker"]} | 殖利率:{single_d["cur_yield"]:.1f}% | 總報酬:{single_d["total_ret"]:.1f}% | VCP:{single_d["vcp"]["signal"]}',
            })
        if port_d:
            summary_rows.append({
                '來源': 'Tab⑦ 組合配置',
                '內容': f'總資產:{port_d["total_value"]:,.0f}元 | 壓力測試損失:{port_d["loss_pct"]:.1f}% | 再平衡:{len(port_d["rebal_actions"])}筆',
            })
        if backtest_d:
            summary_rows.append({
                '來源': 'Tab⑧ 回測',
                '內容': f'CAGR:{backtest_d["cagr"]:.1f}% | Sharpe:{backtest_d["sharpe"]:.2f} | MDD:{backtest_d["mdd"]:.1f}% | 期間:{backtest_d["period"]}',
            })
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        # 建立綜合 prompt
        sections = [
            "你是頂尖ETF投資策略師，整合以下多維度資料，給出綜合評斷。",
            "每個評斷項目不超過300字，條列式，嚴禁捏造未提供的數據。",
            f"\n當前總經市場狀態：{regime}",
            f"建議配置：{MACRO_ALLOC.get(regime, {})}",
        ]
        if single_d:
            sections.append(
                f"\n【Tab⑥ 單支ETF診斷】{single_d['ticker']} ({single_d['name']})\n"
                f"  含息總報酬={single_d['total_ret']:.1f}% | 殖利率={single_d['cur_yield']:.1f}% | "
                f"5年均殖利率={single_d['avg_yield']:.1f}% | VCP信號={single_d['vcp']['signal']} | "
                f"折溢價={single_d['premium']['premium_pct']}% | 追蹤誤差={single_d['te']}%"
            )
        if port_d:
            acts = ', '.join(f'{a["動作"]}{a["ETF"]}' for a in port_d['rebal_actions'])
            sections.append(
                f"\n【Tab⑦ 組合配置】{len(port_d['rows'])}檔ETF | 總資產={port_d['total_value']:,.0f}元\n"
                f"  壓力測試預估損失={port_d['loss_pct']:.1f}% | 再平衡指令：{acts or '無需調整'}"
            )
        if backtest_d:
            w_txt = ' | '.join(f'{t}:{w*100:.0f}%' for t, w in backtest_d['weights'].items())
            sections.append(
                f"\n【Tab⑧ 回測績效】{backtest_d['period']} 期間 | 組合：{w_txt}\n"
                f"  CAGR={backtest_d['cagr']:.1f}% | 夏普值={backtest_d['sharpe']:.2f} | "
                f"最大回撤={backtest_d['mdd']:.1f}% | 年化波動率={backtest_d['vol']:.1f}%"
            )
        sections += [
            "\n請輸出：",
            "1.【整體ETF組合評級】A+/A/B/C（綜合以上所有數據）",
            "2.【最大機會點】目前最值得加碼的方向（附理由）",
            "3.【最大風險點】需要立即處理的警示",
            "4.【行動清單】依優先序列出3項具體行動",
            f"5.【總經連動建議】在{regime}市場下，ETF佈局應如何因應",
            "⚠️ 僅供學術研究與教育用途，非投資建議，盈虧自負",
        ]
        _base_prompt = '\n'.join(sections)

        if st.button('🤖 生成 ETF 綜合 AI 評斷', key='etf_ai_comp_btn', use_container_width=True):
            if not gemini_fn:
                st.warning('⚠️ 請設定 GEMINI_API_KEY 才能使用 AI 功能')
            else:
                # 收集本頁所有 ETF ticker，抓取各自新聞
                _comp_tickers = []
                if single_d:
                    _comp_tickers.append((single_d['ticker'], single_d.get('name', '')))
                if port_d:
                    for _rr in port_d.get('rows', [])[:3]:
                        _tk = _rr.get('ticker', '')
                        if _tk and (_tk, '') not in _comp_tickers:
                            _comp_tickers.append((_tk, ''))
                if backtest_d:
                    for _tk in list(backtest_d.get('weights', {}).keys())[:3]:
                        if (_tk, '') not in _comp_tickers:
                            _comp_tickers.append((_tk, ''))
                _comp_news_lines = []
                for _tk, _nm in _comp_tickers[:4]:
                    _nn = _fetch_news_for(_tk, _nm, 2)
                    if _nn and _nn != '（暫無相關新聞）':
                        _comp_news_lines.append(f'[{_tk}]\n{_nn}')
                _comp_news_str = '\n'.join(_comp_news_lines) if _comp_news_lines else '（暫無相關新聞）'
                full_prompt = _base_prompt + f'\n\n【近期各ETF相關新聞】\n{_comp_news_str}'
                with st.spinner('AI 整合分析中...'):
                    result = gemini_fn(full_prompt, max_tokens=1500)
                if result and not result.startswith('⚠️'):
                    st.session_state['etf_ai_comp_result'] = result
                    st.rerun()
                else:
                    st.error(result or 'AI 回傳為空，請確認 API Key')

        saved_result = st.session_state.get('etf_ai_comp_result')
        if saved_result:
            st.markdown('---')
            st.markdown(saved_result)
            if st.button('🔄 清除結果', key='etf_ai_comp_clear'):
                st.session_state.pop('etf_ai_comp_result', None)
                st.rerun()
    else:
        st.info(
            '📋 尚未有分析資料\n\n'
            '請先到以下頁面執行分析：\n'
            '- **Tab ⑥** 單一 ETF 深度診斷\n'
            '- **Tab ⑦** ETF 組合配置\n'
            '- **Tab ⑧** ETF 歷史回測\n\n'
            '分析完成後回到此頁，即可生成跨模組綜合評斷。'
        )

    # ── 自由提問區 ────────────────────────────────────────────
    st.markdown('---')
    st.markdown('#### 💬 ETF 自由提問')
    st.caption('不需要先執行分析，直接輸入任何ETF相關問題')
    question = st.text_area('輸入問題', height=80, key='etf_ai_question',
                             placeholder='例如：台灣高股息ETF和美國債券ETF如何搭配？')
    if st.button('💬 提問', key='etf_ai_ask_btn', use_container_width=True):
        if not question.strip():
            st.warning('請輸入問題')
        elif not gemini_fn:
            st.warning('⚠️ 請設定 GEMINI_API_KEY')
        else:
            q_prompt = (
                f"你是ETF投資教育顧問，以春哥VCP、郭俊宏以息養股、孫慶龍7%估值框架回答，"
                f"不超過300字，嚴禁捏造數據：\n\n問題：{question}\n"
                f"⚠️ 僅供學術研究，非投資建議"
            )
            with st.spinner('AI 回答中...'):
                answer = gemini_fn(q_prompt, max_tokens=600)
            if answer and not answer.startswith('⚠️'):
                st.markdown(answer)
            else:
                st.warning(answer or 'AI 回傳為空')
