"""ETF AI 首席顧問 TAB — 對齊「總經 AI」風格的 Markdown 戰情報告

依賴策略
========
- Top-level: streamlit
- 函式內 late import：
  * etf_dashboard.py 內部 helper: _fetch_news_for, macro_allocation_banner
  * v19.170 P0-1：配置數字改吃建議持股 SSOT
    `src.services.allocation_service.get_allocation / get_allocation_sleeves`，
    **不再引用 DEPRECATED 的 `etf_render.MACRO_ALLOC`**。

呼叫端
======
- app.py 經 etf_dashboard re-export 取用
"""
from __future__ import annotations

import streamlit as st


def render_etf_ai(gemini_fn=None):
    # v19.170 P0-1:移除 MACRO_ALLOC 引用 —— 該靜態表與 🎚️ 建議持股油門 脫鉤
    # (bull 一律股票 70%),餵給 AI 會產出與畫面矛盾的配置文字給使用者看。
    from src.ui.etf import _fetch_news_for, macro_allocation_banner

    mkt_info = st.session_state.get('mkt_info', {})
    regime   = mkt_info.get('regime', 'neutral')
    macro_allocation_banner(regime)

    st.markdown('### 🤖 ETF AI 首席策略師')
    st.caption('依組合配置 + 健康燈號 + 回測 + 總經 + 新聞，生成結構化戰情報告。'
               '個股的 AI 評斷請至「🔬 個股」Tab，本區聚焦 ETF 組合層級決策。')

    # ── 讀取資料（不再讀 etf_single_data，個股有自己的 AI）──────
    port_d     = st.session_state.get('etf_portfolio_data')
    backtest_d = st.session_state.get('etf_backtest_data')

    if not port_d:
        st.info(
            '📋 尚未載入組合資料\n\n'
            '請先到上方「📋 輸入持股組合」區塊輸入持股並點「計算組合」，'
            'AI 首席策略師會根據你的真實持股 + 健康燈號 + 總經狀態給出組合層級建議。'
        )
        # 自由提問仍開放（無持股也能問通用問題）
        _render_free_qa(gemini_fn)
        return

    # ── 顯示生成按鈕（不再有 dataframe 摘要表，避免雜訊）──────
    st.markdown(
        f'<div style="background:#0d1117;border-left:3px solid #76e3ea;padding:10px 14px;'
        f'border-radius:0 6px 6px 0;margin:8px 0;font-size:12px;color:#c9d1d9;">'
        f'📊 將分析 <b>{len(port_d.get("rows", []))} 檔持股</b> '
        f'｜總現值 <b>{port_d.get("total_value", 0):,.0f} 元</b>'
        f'｜總經狀態 <b>{regime}</b>'
        + (f'｜回測 CAGR <b>{backtest_d["cagr"]:.1f}%</b> / Sharpe <b>{backtest_d["sharpe"]:.2f}</b>'
           if backtest_d else '')
        + '</div>', unsafe_allow_html=True)

    if st.button('🤖 生成 ETF 組合戰情研判報告', key='etf_ai_comp_btn',
                 use_container_width=True, type='primary'):
        if not gemini_fn:
            st.warning('⚠️ 請設定 GEMINI_API_KEY 才能使用 AI 功能')
        else:
            _generate_report(gemini_fn, port_d, backtest_d, regime,
                             _fetch_news_for, mkt_info)

    # ── 顯示已生成報告 ────────────────────────────────────────
    saved = st.session_state.get('etf_ai_comp_result')
    if saved:
        st.markdown('---')
        st.markdown(
            '<div style="margin:14px 0 8px;padding:8px 16px;'
            'background:linear-gradient(90deg,#76e3ea18,#0d1117);'
            'border-left:4px solid #76e3ea;border-radius:0 6px 6px 0;">'
            '<span style="font-size:15px;font-weight:900;color:#76e3ea;">'
            '📊 AI 組合戰情研判報告</span></div>',
            unsafe_allow_html=True)
        st.markdown(saved)
        if st.button('🔄 清除結果', key='etf_ai_comp_clear'):
            st.session_state.pop('etf_ai_comp_result', None)
            st.rerun()

    _render_free_qa(gemini_fn)


def _generate_report(gemini_fn, port_d, backtest_d, regime,
                     fetch_news_fn, mkt_info):
    """組裝 Markdown prompt 並呼叫 Gemini 生成結構化戰情報告。

    v19.170 P0-1：簽章移除 `MACRO_ALLOC` 參數。prompt 內的配置百分比一律
    來自 `get_allocation_sleeves()`；總經未評估(回 None)時 prompt **完全不出現
    任何配置百分比**，並明令 AI 不得自行給數字(§1 Fail Loud)。
    """
    rows     = port_d.get('rows', [])
    war_rows = port_d.get('war_rows', [])
    rebal    = port_d.get('rebal_actions', [])

    # ── 持股明細（含資本利得、配息、role）─────────────────────
    _hold_lines = []
    for r in rows:
        _hold_lines.append(
            f'  - {r["ticker"]} ({r.get("role","—")})：'
            f'持有 {int(r.get("shares",0)):,} 股｜均價 {r.get("avg_price",0):.2f}｜'
            f'現價 {r.get("current_price",0):.2f}｜'
            f'資本利得 {r.get("capital_gain_pct",0):+.2f}%（{r.get("capital_gain",0):+,.0f}元）｜'
            f'近1年已領配息 {r.get("dividend_received",0):,.0f}元｜'
            f'希望比例 {r.get("target_pct",0):.1f}% / 實際 {r.get("actual_pct",0):.1f}%'
            f'（偏離 {r.get("deviation",0):+.1f}pp）'
        )
    _hold_str = '\n'.join(_hold_lines) if _hold_lines else '（無持股）'

    # ── 健康燈號 + 動作建議（來自 _compute_etf_warroom_row）────
    _war_lines = []
    for w in war_rows:
        _war_lines.append(
            f'  - {w.get("代號","?")}：健康燈號 {w.get("健康燈號","—")}｜'
            f'σ位階 {w.get("σ位階","—")}｜'
            f'距MA20 {w.get("距月線%","—")}%｜距MA60 {w.get("距季線%","—")}%｜'
            f'折溢價 {w.get("折溢價%","—")}%｜年化配息率 {w.get("年化配息率%","—")}%｜'
            f'1年含息報酬 {w.get("1年含息報酬%","—")}%｜'
            f'動作建議：{w.get("動作建議","—")}'
        )
    _war_str = '\n'.join(_war_lines) if _war_lines else '（無健檢資料）'

    # ── 再平衡指令 ────────────────────────────────────────────
    _rebal_str = '；'.join(
        f'{a["動作"]} {a["ETF"]} {a["金額(元)"]:,.0f}元（偏離 {a["偏離度%"]:+.1f}%）'
        for a in rebal) if rebal else '無需再平衡'

    # ── 回測（可選）──────────────────────────────────────────
    _bt_str = '（尚未執行回測）'
    if backtest_d:
        _w_txt = ', '.join(f'{t}:{w*100:.0f}%' for t, w in backtest_d['weights'].items())
        _bt_str = (
            f'期間 {backtest_d["period"]}｜權重 {_w_txt}｜'
            f'CAGR {backtest_d["cagr"]:.2f}%｜Sharpe {backtest_d["sharpe"]:.2f}｜'
            f'MDD {backtest_d["mdd"]:.2f}%｜年化波動率 {backtest_d["vol"]:.2f}%'
        )

    # ── 總經數據快照 ─────────────────────────────────────────
    # v19.170 P0-1:原本餵 DEPRECATED 的 MACRO_ALLOC(bull 固定股票 70%),
    # 與 🎚️ 建議持股油門 脫鉤 → AI 會寫出跟畫面互相矛盾的配置給使用者看。
    # 改為唯一取數入口:區間文字取 get_allocation().range_text,
    # 三桶百分比取 get_allocation_sleeves()(由最終建議持股中值推導)。
    from src.services.allocation_service import (
        get_allocation,
        get_allocation_sleeves,
    )

    _alloc_dec = get_allocation()
    _sleeves = get_allocation_sleeves()
    _macro_lines = [f'• 大盤狀態：{regime}']
    if _sleeves is not None:
        _macro_lines.append(f'• 系統最終建議持股（唯一真相）：{_alloc_dec.range_text}')
        _macro_lines.append(
            f'• 對應三桶配置：股票型 {_sleeves.get("股票型ETF", 0)}% / '
            f'債券型 {_sleeves.get("債券型ETF", 0)}% / 現金 {_sleeves.get("貨幣/現金", 0)}%'
        )
    else:
        # §1 Fail Loud:總經未評估 → prompt 內**不得出現任何配置百分比**
        _macro_lines.append('• 建議配置：總經尚未評估，系統沒有任何配置數字可提供')
    for _k, _v in mkt_info.items():
        if _k in ('regime', 'exposure_pct'):
            continue
        if isinstance(_v, (int, float)):
            _macro_lines.append(f'• {_k}: {_v}')
    _macro_str = '\n'.join(_macro_lines)

    # ── 為每檔 ETF 抓近期新聞（最多前 4 檔，各 2 則）────────
    _news_lines = []
    for r in rows[:4]:
        _tk = r.get('ticker', '')
        _nn = fetch_news_fn(_tk, _tk, 2)
        if _nn and _nn != '（暫無相關新聞）':
            _news_lines.append(f'[{_tk}]\n{_nn}')
    _news_str = '\n\n'.join(_news_lines) if _news_lines else '（暫無相關新聞）'
    _overlap_str = st.session_state.get('etf_overlap_summary', '（未計算 — 請先在「組合配置」頁檢視持股重疊）')
    _weak_str = st.session_state.get('etf_weakness_summary', '（未計算 — 請先在「組合配置」頁跑主動 ETF 弱勢度檢測）')

    # ── 改用共用「白話結構化摘要」元件組 prompt ──────────────
    from src.services import build_structured_summary_prompt

    # v19.178 §3.3:「美股大跌 20%」原為 prompt 內寫死,而 `loss_pct` 的計算情境
    # 走 SSOT PORTFOLIO_STRESS_TEST_DROP_PCT(-20.0)。改情境時數字會動、送給 AI 的
    # 說明不會動 → AI 會用錯誤的情境描述解讀正確的虧損值。改為插值。
    from shared.signal_thresholds import PORTFOLIO_STRESS_TEST_DROP_PCT
    _hold_data = (
        f'這個組合一共 {len(rows)} 檔｜目前總現值 {port_d.get("total_value",0):,.0f} 元'
        f'｜壓力測試（假設美股大跌 {abs(PORTFOLIO_STRESS_TEST_DROP_PCT):g}% 時，'
        f'整個組合大概會跌多少）約 {port_d.get("loss_pct",0):.1f}%\n'
        f'下面是每一檔的持有狀況（希望比例＝你原本想配多少%、實際＝現在實際占多少%、'
        f'偏離＝差了幾個百分點 pp）：\n{_hold_str}\n\n'
        f'持股重疊（兩檔 ETF 裝的成分股很像，等於同一筆錢押兩次、風險更集中）：\n{_overlap_str}'
    )

    _health_data = (
        '燈號意思：🟢 體質健康｜🟡 趨勢轉弱（價格跌破季線、走勢變差）｜'
        '🔴 該處理（核心檔：賺到的配息還補不回本金虧損；衛星檔：漲太多該停利了）。\n'
        'σ位階（現在價格偏離平常均價的程度，負越多代表越便宜、正越多代表越貴）｜'
        '距MA20、MA60（離月線、季線還差幾%，看短中期趨勢）｜'
        '折溢價（你買的價格比這檔實際淨值貴或便宜幾%，溢價太高＝買貴了）｜'
        '年化配息率（一年大概能領回幾%現金）｜1年含息報酬（含領到的配息，一年總共賺賠幾%）。\n'
        f'{_war_str}\n\n'
        f'主動型 ETF 弱勢度 / 換股訊號（基金經理人選股有沒有變差、要不要換掉）：\n{_weak_str}'
    )

    _rebal_data = (
        '再平衡＝把漲太多、跌太多而跑掉的比例，買賣調回你原本設定的目標比例。\n'
        f'系統算出來的調整動作：{_rebal_str}'
    )

    _bt_data = (
        '回測＝拿這個組合的歷史資料，模擬「過去如果這樣配，會賺賠多少、抖不抖」。\n'
        f'{_bt_str}\n'
        '名詞白話：CAGR（過去平均一年賺幾%）｜Sharpe（每承受一分風險換到多少報酬，越高越划算，>1 算不錯）｜'
        'MDD 最大回檔（過去最慘從高點往下跌掉幾%，數字越大代表你曾經要忍受越大的帳面虧損）｜'
        '年化波動率（價格平常上下震盪有多劇烈，越大代表越會心驚膽跳）。'
    )

    # v19.170 P0-1:配置護欄 —— 明令 AI 只能沿用 SSOT 的數字,
    # 避免它自行生出第 N 套與 🎚️ 建議持股油門 矛盾的股債比。
    if _sleeves is not None:
        _macro_guard = (
            f'⚠️ 配置護欄（必須遵守）：系統最終建議持股為 {_alloc_dec.range_text}，'
            '上面的股/債/現金三桶百分比就是由這個區間推導出來的（與畫面上的'
            '「🎚️ 建議持股油門」是同一個數字來源）。你的配置建議必須與此一致，'
            '不得自行給出不同的百分比，也不得引用任何其他來源的股債比。'
            '可以做的是：拿這組百分比去對照使用者目前實際配置，指出哪邊超標、哪邊不足。'
        )
    else:
        _macro_guard = (
            '⚠️ 配置護欄（必須遵守）：總經尚未評估，請勿在報告中給出具體持股或配置百分比。'
            '這一節只能說明「總經還沒評估，要先按『🚀 一鍵更新全部數據』才會有建議配置」，'
            '不准自行推估、不准引用一般常見的股債比數字。'
        )

    _macro_data = (
        '這段看的是現在整體大環境順不順，以及系統建議的股債現金比例。\n'
        f'{_macro_str}\n'
        f'{_macro_guard}'
    )

    sections = [
        {'name': '這個 ETF 組合現在長怎樣（持股、配置比例、有沒有重複押注）',
         'data': _hold_data},
        {'name': '每檔 ETF 健不健康、有沒有要處理的',
         'data': _health_data},
        {'name': '要不要重新分配比例（再平衡）',
         'data': _rebal_data},
        {'name': '過去績效如何、波動大不大（回測）',
         'data': _bt_data},
        {'name': '現在大環境順不順（大盤狀態與建議配置）',
         'data': _macro_data},
    ]

    prompt = build_structured_summary_prompt(
        '我的 ETF 組合', sections, news_text=_news_str,
        overall_question='這個 ETF 組合整體狀況如何、要不要調整、最該注意什麼。')

    with st.spinner('AI 首席策略師生成戰情報告中（約 8-12 秒）...'):
        result = gemini_fn(prompt, max_tokens=2200)
    if result and not result.startswith('⚠️'):
        st.session_state['etf_ai_comp_result'] = result
        st.rerun()
    else:
        st.error(result or 'AI 回傳為空，請確認 GEMINI_API_KEY')


def _render_free_qa(gemini_fn):
    """ETF 自由提問區（不需先載入組合資料）"""
    st.markdown('---')
    st.markdown('#### 💬 ETF 自由提問')
    st.caption('不需先載入組合，直接輸入任何 ETF 相關問題（適合策略諮詢、新標的研究）。')
    question = st.text_area(
        '輸入問題', height=80, key='etf_ai_question',
        placeholder='例如：台灣高股息 ETF 和美國債券 ETF 如何搭配？升息循環尾聲該加碼長債嗎？')
    if st.button('💬 提問', key='etf_ai_ask_btn', use_container_width=True):
        if not question.strip():
            st.warning('請輸入問題')
        elif not gemini_fn:
            st.warning('⚠️ 請設定 GEMINI_API_KEY')
        else:
            q_prompt = (
                # v19.174 去識別化：prompt 內原列 3 位人名，改為純方法論描述（會進 LLM 輸出）。
                # ⚠️ 措辭刻意避開「現金」二字：`tests/test_no_hardcoded_position_pct.py`
                #    會抓「持股語意關鍵詞 + 12 字內百分比」，寫成「…現金流、7%…」會誤觸守門。
                f'你是 ETF 投資教育顧問，以 VCP 波幅收縮、以息養股、7% 殖利率估值三套框架回答，'
                f'不超過 300 字，嚴禁捏造數據：\n\n問題：{question}\n'
                f'⚠️ 僅供學術研究，非投資建議'
            )
            with st.spinner('AI 回答中...'):
                answer = gemini_fn(q_prompt, max_tokens=600)
            if answer and not answer.startswith('⚠️'):
                st.markdown(answer)
            else:
                st.warning(answer or 'AI 回傳為空')
