"""src/ui/tabs/macro/section_news_ai.py — Section 十一 News AI 總裁決(F-7.1 B-3 抽出,P2 v18.389 rename)。

🤖 News AI 總裁決(實體狀態鎖架構):
- 前端唯讀 macro_state.json
- LLM 運算由觸發按鈕在背景執行並寫檔
- 結尾含「教室搬至說明書」指引註解

closure params(explicit pass):
- _macro_info: dict  總經數值 dict(從前面 section 計算)
- _tl_eff_reg: str   有效 traffic light regime(從 §一 計算)
"""
from __future__ import annotations

import datetime
import json

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW  # noqa: F401
from src.config import FINMIND_TOKEN  # noqa: F401
from src.ui.render.macro_ui_components import section_header
from src.ui.tabs.macro.helpers import render_macro_bucket_summary_bar  # noqa: F401
from src.services.macro_state_locker import (
    MacroStateLocker, calculate_system_state, load_macro_state,
)


def render_section_news_ai(_macro_info: dict, _tl_eff_reg: str) -> None:
    """渲染§十一 News AI 總裁決區(原 tab_macro line 4227-4521)。"""
    # app.py 內部 helper(lazy import,避 L5→L6 違憲於 module load 時 trigger)
    from app import gemini_call  # noqa: F401
    # v18.398 P5-B3-β R8:news fetcher 已抽至 src/data/news
    from src.data.news import fetch_macro_news as _fetch_macro_news
    # ══════════════════════════════════════════════════════════════
    # SECTION 十一: 🤖 AI 總裁決（實體狀態鎖架構）
    # 前端唯讀 macro_state.json；LLM 運算由觸發按鈕在背景執行並寫檔
    # ══════════════════════════════════════════════════════════════
    st.markdown(section_header('十一', '📰 新聞 ｜🤖 AI 總裁決', '🤖'), unsafe_allow_html=True)
    render_macro_bucket_summary_bar('news')  # v18.314 桶輕量總結 bar(新聞系統性風險)
    
    with st.expander('🤖 AI 總裁決 — 實體狀態鎖架構（唯讀）', expanded=True):
        _verdict_hdr_c1, _verdict_hdr_c2, _verdict_hdr_c3 = st.columns([4, 1, 1])
        with _verdict_hdr_c1:
            st.markdown(
                '<div style="font-size:12px;color:#8b949e;padding:4px 0;">'
                '整合即時國際財經新聞（RSS）與當前量化總經數據，'
                '由 Gemini AI 生成 Markdown 戰情報告。'
                '曝險上限由 Python 規則引擎計算，AI 負責解讀。'
                '<br><span style="color:#484f58;">需設定 Streamlit Secrets：'
                '<code>GEMINI_API_KEY = "AIza..."</code></span></div>',
                unsafe_allow_html=True)
        with _verdict_hdr_c2:
            _do_verdict = st.button('🔒 執行 AI 裁決', key='btn_run_verdict',
                                    use_container_width=True, type='primary')
        with _verdict_hdr_c3:
            if st.button('🗑️ 清除報告', key='btn_clear_verdict', use_container_width=True):
                st.session_state.pop('_macro_ai_report', None)
                st.session_state.pop('_macro_ai_ts', None)
                st.rerun()
    
        # ── 觸發：呼叫 MacroStateLocker 寫入 macro_state.json ──
        if _do_verdict:
            with st.spinner('📡 正在抓取財經新聞 + 呼叫 Gemini AI（約 15~30 秒）…'):
                _v_news = _fetch_macro_news(5)
                # v18.284：stash 供頂部「五桶·新聞」燈號讀取（系統性風險命中數 → 紅/黃/綠）
                st.session_state['_macro_news_items'] = _v_news
                _v_news_titles = [_n['title'] for _n in _v_news]
                # 組裝量化數據快照供 AI 判讀
                _vix_d  = _macro_info.get('vix') or {}
                _exp_d  = _macro_info.get('tw_export') or {}
                _pmi_d  = _macro_info.get('ism_pmi') or {}
                _cpi_d  = _macro_info.get('us_core_cpi') or {}
                _fed_d  = _macro_info.get('fed_funds') or {}  # v18.169 MK 拐點
                _mi_d   = st.session_state.get('m1b_m2_info') or {}
                _bi_d   = st.session_state.get('bias_info') or {}
                _li_d   = st.session_state.get('li_latest')
                _pcr_v  = None
                if _li_d is not None and not _li_d.empty and '選PCR' in _li_d.columns:
                    _pcr_raw = str(_li_d.iloc[-1].get('選PCR', ''))
                    if _pcr_raw not in ('', '-', 'nan', 'None'):
                        try:
                            _pcr_v = float(_pcr_raw)
                        except ValueError:
                            pass
                # 外資期貨淨口數（負值=淨空單）
                _fut_net_v = None
                if _li_d is not None and not _li_d.empty and '外資大小' in _li_d.columns:
                    try:
                        _fut_net_v = float(_li_d.iloc[-1].get('外資大小', 0))
                    except (ValueError, TypeError):
                        pass
                # 指數是否跌破 MA5（從 mkt_info 取得）
                _mkt_d = st.session_state.get('mkt_info') or {}
                _below_ma5 = bool(_mkt_d.get('index_below_ma5', False))
                # PMI 連兩月追蹤：本次觸發時記錄當前值，下次觸發時作為「前月」
                _pmi_cur = _pmi_d.get('value')
                _pmi_prev_v = st.session_state.get('_s10_prev_pmi_value')
                if _pmi_cur is not None:
                    st.session_state['_s10_prev_pmi_value'] = _pmi_cur
                _macro_numbers = {
                    'VIX_Index':           _vix_d.get('current'),
                    'M1B_YoY_pct':         _mi_d.get('m1b_yoy'),
                    'M2_YoY_pct':          _mi_d.get('m2_yoy'),
                    'TW_Export_YoY_pct':   _exp_d.get('yoy'),
                    'ISM_PMI_or_OECD_CLI': _pmi_cur,
                    'PMI_Prev_Month':       _pmi_prev_v,
                    'US_Core_CPI_YoY_pct': _cpi_d.get('yoy'),
                    'US_Core_CPI_PrevMonth_YoY_pct': _cpi_d.get('prev_yoy'),  # v18.169
                    'US_FedFunds_Rate_pct': _fed_d.get('current'),             # v18.169
                    'US_FedFunds_PrevMonth_pct': _fed_d.get('prev'),           # v18.169
                    'BIAS240_pct':         _bi_d.get('bias_240'),
                    'PCR':                 _pcr_v,
                    'Futures_Net_Short':   _fut_net_v,
                    'Index_Below_MA5':     _below_ma5,
                    'Sahm_Rule_Triggered': False,  # 尚無薩姆規則資料來源，預設 False
                }
                _system_state = calculate_system_state(_macro_numbers)
                # ── 組裝量化原始數據字串供新版 AI 提示語使用 ──────
                _cl_d_v = st.session_state.get('cl_data', {})
                _inst_v = _cl_d_v.get('inst', {})
                _fk_v   = next((k for k in _inst_v if '外資' in k), None)
                _tk_v   = next((k for k in _inst_v if '投信' in k), None)
                _dk_v   = next((k for k in _inst_v if '自營' in k), None)
                _fnet_v = _inst_v.get(_fk_v, {}).get('net') if _fk_v else None
                _tnet_v = _inst_v.get(_tk_v, {}).get('net') if _tk_v else None
                _dnet_v = _inst_v.get(_dk_v, {}).get('net') if _dk_v else None
                _margin_v = _cl_d_v.get('margin')
                _adl_v   = _cl_d_v.get('adl')
                _adl_ratio_v = None
                if _adl_v is not None and not _adl_v.empty and 'ad_ratio' in _adl_v.columns:
                    try:
                        _adl_ratio_v = float(_adl_v['ad_ratio'].iloc[-1])
                    except (ValueError, TypeError):
                        pass
                _leek_v2 = None
                if _li_d is not None and not _li_d.empty and '韭菜指數' in _li_d.columns:
                    try:
                        _leek_v2 = float(_li_d.iloc[-1].get('韭菜指數', None))
                    except (ValueError, TypeError):
                        pass
                _ctx = []
                if _bi_d.get('bias_240') is not None:
                    _ctx.append(f'• 大盤年線乖離率 BIAS240：{_bi_d["bias_240"]:+.1f}%（>15%偏貴、<-10%低估）')
                if _mi_d.get('m1b_yoy') is not None:
                    _gap_v = round(float(_mi_d['m1b_yoy']) - float(_mi_d.get('m2_yoy') or 0), 2)
                    _ctx.append(f'• M1B={_mi_d["m1b_yoy"]:.1f}%  M2={_mi_d.get("m2_yoy",0):.1f}%  差額={_gap_v:+.2f}%（正=資金行情啟動）')
                if _fnet_v is not None:
                    _ctx.append(f'• 外資現貨買賣超：{_fnet_v:+.1f}億')
                if _tnet_v is not None:
                    _ctx.append(f'• 投信買賣超：{_tnet_v:+.1f}億')
                if _dnet_v is not None:
                    _ctx.append(f'• 自營商買賣超：{_dnet_v:+.1f}億')
                if _margin_v is not None:
                    _ctx.append(f'• 融資餘額：{_margin_v:.0f}億（>3400億危險、>2500億警戒）')
                if _leek_v2 is not None:
                    _ctx.append(f'• 韭菜指數（小台散戶多空比）：{_leek_v2:.0f}（>80散戶過熱、<20散戶恐慌）')
                if _pcr_v is not None:
                    _ctx.append(f'• 選擇權 PCR：{_pcr_v:.2f}（>1.3市場恐慌偏多訊號、<0.7過度樂觀偏空）')
                if _adl_ratio_v is not None:
                    _ctx.append(f'• ADR 廣度指標：{_adl_ratio_v:.0f}%（>70市場健康、<30廣度不足）')
                if _fut_net_v is not None:
                    _ctx.append(f'• 外資期貨淨口數：{_fut_net_v:+.0f}口（負=淨空單、<-35000強烈空頭信號）')
                if _vix_d.get('current'):
                    _ctx.append(f'• VIX 恐慌指數：{_vix_d["current"]}（>28警戒、>35極度恐慌）')
                _ndc_v = locals().get('_m8_ndc')
                if _ndc_v and _ndc_v.get('score') is not None:
                    _ctx.append(f'• NDC 景氣對策信號：{float(_ndc_v["score"]):.0f}分（9-16藍燈衰退 / 23-31綠燈穩定 / 38-45紅燈過熱）')
                if _pmi_cur is not None:
                    _ctx.append(f'• 台灣 PMI / 景氣領先：{_pmi_cur}（>50擴張、<50收縮、<48製造業衰退）')
                if _exp_d.get('yoy') is not None:
                    _ctx.append(f'• 台灣外銷訂單 YoY：{_exp_d["yoy"]:+.1f}%（科技出口景氣領先）')
                if _cpi_d.get('yoy') is not None:
                    _ctx.append(f'• 美國核心 CPI YoY：{_cpi_d["yoy"]:+.1f}%（>3% 升息壓力、壓抑高 PE 成長股估值）')
                _sox_v = locals().get('_ai_sox') or 0
                _nvda_v = locals().get('_ai_nvda') or 0
                if _sox_v or _nvda_v:
                    _ctx.append(f'• 美股科技動能：費半 SOX={_sox_v:+.1f}% / NVDA={_nvda_v:+.1f}%（領先台股科技權值股 2-4 週）')
                _v_macro_ctx = '\n'.join(_ctx) if _ctx else '（數據尚未載入，請先按「🚀 一鍵更新全部數據」）'
                _locker = MacroStateLocker()
                _locker.lock_system_state_only(_system_state)
                # 組裝 Markdown 提示語（不依賴 JSON 解析，與 Tab 2 AI 首席顧問同風格）
                _v_state_json = json.dumps(_system_state, ensure_ascii=False, indent=2)
                # 將新聞標題與摘要一併傳給 AI（提升黑天鵝偵測準確度）
                _v_news_lines = []
                for _n_item in _v_news:
                    _t_n = _n_item.get('title', '').strip()
                    _s_n = _n_item.get('summary', '').strip()
                    _src_n = _n_item.get('source', '')
                    if _t_n:
                        _line = f'- [{_src_n}] {_t_n}'
                        if _s_n:
                            _line += f'｜{_s_n[:120]}'
                        _v_news_lines.append(_line)
                _v_news_str = '\n'.join(_v_news_lines) if _v_news_lines else '（無法取得新聞）'
    
                # v1.2 新增章節（一）：熱錢動向（三角交叉）
                _v_hot_money_ctx = '（無熱錢資料）'
                try:
                    # _twd_df 在 _mkt_info 區塊已抓；fallback 從 session_state
                    _twd_df_ai = locals().get('_twd_df')
                    if _twd_df_ai is None:
                        _cl_ss = st.session_state.get('cl_data', {}) or {}
                        _twd_df_ai = (_cl_ss.get('tw', {}) or {}).get('新台幣匯率')
                    if _twd_df_ai is not None and not _twd_df_ai.empty:
                        from src.ui.tabs import get_latest_hot_money_state
                        _hm = get_latest_hot_money_state(
                            _twd_df_ai, FINMIND_TOKEN or '')
                        if _hm:
                            _v_hot_money_ctx = (
                                f'- 最新判讀（{_hm["date"]}）：**{_hm["state"]}**\n'
                                f'- 解讀：{_hm["interpretation"][:120]}\n'
                                f'- 最新外資買賣超：{_hm["foreign_net_yi"]:+.1f} 億\n'
                                f'- 近5日累計外資：{_hm["roll_flow"]:+.0f} 億\n'
                                f'- 最新 USD/TWD：{_hm["usdtwd"]:.3f}\n'
                                f'- 近5日台幣升貶：{_hm["roll_apprec"]:+.2f}%（正=升值=熱錢流入）'
                            )
                except Exception as _hm_ai_e:
                    print(f'[AI/hot_money] {type(_hm_ai_e).__name__}: {_hm_ai_e}')
    
                # v1.2 新增章節（二）：拐點訊號摘要（六大面向綜合）
                _v_pivot_ctx = '（拐點訊號尚未計算，請先載入總經拼圖）'
                _pivot_sigs_ai = st.session_state.get('_pivot_signals') or []
                if _pivot_sigs_ai:
                    _pivot_lines = []
                    _bull_n = _bear_n = _warn_n = 0
                    for _lab, _ic, _co, _det in _pivot_sigs_ai:
                        if _co == TRAFFIC_GREEN:
                            _bull_n += 1
                            _kind = '🟢 多頭'
                        elif _co == TRAFFIC_RED:
                            _bear_n += 1
                            _kind = '🔴 空頭'
                        else:
                            _warn_n += 1
                            _kind = '🟡 觀察'
                        _pivot_lines.append(f'- [{_kind}] {_lab}：{_det[:80]}')
                    _v_pivot_ctx = (
                        f'綜合：多頭 {_bull_n} 條 / 空頭 {_bear_n} 條 / 觀察 {_warn_n} 條\n'
                        + '\n'.join(_pivot_lines)
                    )
    
                from src.services import build_structured_summary_prompt
                _sections_macro = [
                    {'name': '現在市場是偏多還偏空（系統幫你下的判斷）',
                     'data': _v_state_json},
                    {'name': '景氣、資金、利率這些關鍵數字現在長怎樣',
                     'data': _v_macro_ctx},
                    {'name': '熱錢動向（三角交叉：外資 × 台幣匯率 × 背離）',
                     'data': _v_hot_money_ctx},
                    {'name': '拐點訊號（六大面向綜合判斷，偵測景氣反轉）',
                     'data': _v_pivot_ctx},
                ]
                _macro_ai_prompt = build_structured_summary_prompt(
                    '台股大盤現在的狀況', _sections_macro, news_text=_v_news_str,
                    overall_question='現在大盤整體偏多還偏空、適不適合進場、最該留意什麼。')
                _ai_rpt = gemini_call(_macro_ai_prompt, max_tokens=2400)
                _tz8 = datetime.timezone(datetime.timedelta(hours=8))
                st.session_state['_macro_ai_report'] = _ai_rpt
                st.session_state['_macro_ai_ts'] = datetime.datetime.now(_tz8).strftime('%Y-%m-%d %H:%M:%S')
            st.rerun()
    
        # ── 唯讀渲染：從 macro_state.json 讀取曝險數據 ────────────
        _ms = load_macro_state()
        _srl = _ms.get('systemic_risk_level', '危險')
        _regime = _ms.get('market_regime', '系統異常')
        _exp_pct = int(_ms.get('exposure_limit_pct', 0))
        _cash_pct = 100 - _exp_pct
        _ms_ts = _ms.get('timestamp', '')
    
        _srl_clr = {'安全': TRAFFIC_GREEN, '警告': TRAFFIC_YELLOW, '危險': TRAFFIC_RED}.get(_srl, '#8b949e')
        _reg_clr = {'多頭': TRAFFIC_GREEN, '震盪': TRAFFIC_YELLOW, '空頭': TRAFFIC_RED}.get(_regime, '#8b949e')
    
        st.markdown(
            f'<div style="background:#0d1117;border:2px solid {_srl_clr};'
            f'border-radius:12px;padding:18px 20px;margin:10px 0;">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'flex-wrap:wrap;gap:8px;margin-bottom:10px;">'
            f'<div>'
            f'<span style="font-size:11px;color:#484f58;">市場體制</span><br>'
            f'<span style="font-size:22px;font-weight:900;color:{_reg_clr};">{_regime}</span>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<span style="background:{_srl_clr}22;border:1px solid {_srl_clr};'
            f'border-radius:20px;padding:4px 14px;font-size:12px;'
            f'font-weight:700;color:{_srl_clr};">系統風險：{_srl}</span>'
            f'<div style="font-size:10px;color:#484f58;margin-top:4px;">'
            f'裁決時間：{_ms_ts if _ms_ts else "尚未執行"}</div>'
            f'</div>'
            f'</div>'
            f'<div style="text-align:center;padding:8px 0;">'
            f'<div style="font-size:10px;color:#484f58;">建議股票型基金曝險</div>'
            f'<div style="font-size:48px;font-weight:900;color:{_srl_clr};">'
            f'{_exp_pct}<span style="font-size:18px;">%</span></div>'
            f'<div style="font-size:11px;color:#8b949e;">現金/防禦型資產 {_cash_pct}%</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True)
    
        # 快照時效檢查：與即時紅綠燈比對，不一致則提醒重新裁決（避免依過期判斷操作）
        _live_reg_zh = {'bull': '多頭', 'neutral': '震盪', 'bear': '空頭'}.get(_tl_eff_reg, '')
        if _ms_ts and _live_reg_zh and _regime in ('多頭', '震盪', '空頭') and _regime != _live_reg_zh:
            st.warning(
                f'⚠️ 此為 {_ms_ts} 的鎖定快照（市場體制：{_regime}），'
                f'與目前即時紅綠燈（{_live_reg_zh}）不一致 —— '
                f'請重按上方「執行 AI 裁決」更新，以免依過期判斷操作。')
    
        # ── Markdown AI 戰情報告（與 Tab 2 AI 首席顧問同風格）────
        _macro_ai_rpt = st.session_state.get('_macro_ai_report', '')
        _macro_ai_ts  = st.session_state.get('_macro_ai_ts', '')
        if _macro_ai_rpt:
            st.markdown(
                f'<div style="margin:14px 0 8px;padding:8px 16px;'
                f'background:linear-gradient(90deg,#76e3ea18,#0d1117);'
                f'border-left:4px solid #76e3ea;border-radius:0 6px 6px 0;">'
                f'<span style="font-size:15px;font-weight:900;color:#76e3ea;">🤖 AI 首席總經分析師報告</span>'
                f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
                f'分析時間：{_macro_ai_ts}</span></div>',
                unsafe_allow_html=True)
            st.markdown(_macro_ai_rpt)
        elif not _ms_ts:
            st.info('尚未執行 AI 裁決。點擊上方「執行 AI 裁決」按鈕以生成首次分析。')
        else:
            st.caption('▲ 點擊上方「執行 AI 裁決」，AI 將綜合量化數據與即時新聞生成完整戰情報告。')
    
    
    
    # v18.281 — 📚 總經原理教室已搬至「📖 系統說明書」Tab(合併成單一說明書)。
    # 此處留指引,不再於總經 Tab 重複渲染。
