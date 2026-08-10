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
# v19.178 AI-SSOT:餵給 LLM 的門檻一律引 SSOT,不在 prompt 內寫死(§3.3)。
# 五桶危險門檻 SSOT = shared/macro_buckets.BUCKET_DANGER_SPECS(畫面燈號同源),
# 由 L3 共用 prompt 元件 ai_structured_summary 轉成判讀句(個股 Tab 共用同一份)。
from shared.signal_thresholds import PCR_PERCENT_SCALE_MIN as _PCR_PCT_SCALE_MIN
# v19.180 B2-b §4.1:PCR 百分比↔比值刻度換算的唯一實作(L0)。取值端換算一次,
# 規則引擎(calculate_system_state)與 AI prompt 共用同一個比值刻度變數。
from shared.pcr_scale import normalize_pcr_to_ratio as _normalize_pcr
from src.config import (  # noqa: F401
    FINMIND_TOKEN,
    LEEK_ALERT_HIGH_PCT,
    LEEK_ALERT_LOW_PCT,
    LEEK_PIVOT_HIGH_PCT,
)
from src.services.ai_structured_summary import (
    danger_rule_text as _danger_rule_text,
    macro_stale_legend as _macro_stale_legend,
    macro_stale_prefix as _macro_stale_prefix,
    pcr_rule_text as _pcr_rule_text,
)
from src.ui.render.macro_ui_components import section_header
from src.ui.tabs.macro.helpers import render_macro_bucket_summary_bar  # noqa: F401
# v19.175 P0:`cl_data['inst']` 型別收斂 SSOT(L5 → L2,合法下行依賴)
# I2(2026-08-10):BIAS240 估算揭露 SSOT 同樣在 L2(說明見 macro_helpers 的 I2 區塊)。
from src.compute.macro import (
    bias_estimated_prompt_prefix as _bias_est_prefix,
    coerce_inst_dict,
    macro_estimated_legend as _macro_est_legend,
)
from src.services.macro_state_locker import (
    MACRO_VETO_FUTURES_NET_SHORT_LOTS,
    MACRO_VETO_FUTURES_EXPOSURE_CAP_PCT,
    MacroStateLocker, calculate_system_state, load_macro_state,
)


# ══════════════════════════════════════════════════════════════════════
# v19.178 AI-SSOT — 餵給 LLM 的「怎麼判讀」門檻一律由 SSOT 產生
#
# 【修的是什麼】本檔 `_ctx` 區塊組裝送進 Gemini 的總經 context,每行都附一句
# 「怎麼判讀」。2026-08-06 稽核發現其中 6 條的門檻是 prompt 內寫死的裸數字,
# 且**與畫面燈號用的 shared/macro_buckets.BUCKET_DANGER_SPECS 不一致**:
#     外資期貨  prompt <-35000 強烈空頭   vs  SSOT 黃 -10000 / 紅 -20000
#     VIX       prompt >28 / >35          vs  SSOT 黃 22 / 紅 30
#     BIAS240   prompt >15 / <-10         vs  SSOT 黃 10 / 紅 20
#     ADL 廣度  prompt >70 / <30          vs  SSOT 黃 50 / 紅 35
#     PMI       prompt <48 製造業衰退      vs  SSOT 黃 50 / 紅 46
#     CPI       prompt >3% 升息壓力        vs  SSOT 黃 3.5 / 紅 4.0
# 後果:系統畫面已亮 🔴,AI 卻依較寬的門檻說「還在安全區」。使用者會以為兩者
# 看的是同一套規則 —— 這是 §1「錯誤的數字比沒有數字更危險」的變形:
# **錯誤的門檻比沒有門檻更危險**。
#
# 【處置】不再手寫門檻,一律由 `src.services.ai_structured_summary.danger_rule_text`
# 生成(值/單位/小數位/方向全取自 DangerSpec)。該 helper 刻意放在 L3 共用 prompt
# 元件,因為**個股 Tab 的 AI prompt 也犯同款**(tab_stock `_macro_lines2` 另寫了
# VIX >20 / PMI <45 / US10Y >4 一套),兩處必須共用同一份真相才不會再分岔(§2.1)。
# ══════════════════════════════════════════════════════════════════════
_danger_rule = _danger_rule_text     # 本檔沿用短名（呼叫點密集，維持可讀性）
_pcr_alert_rule = _pcr_rule_text

# ══════════════════════════════════════════════════════════════════════
# G1(2026-08-07)— 月頻總經數字必須帶 as_of 日期 + 過期標記
#
# 【修的是什麼】本檔 `_ctx` 的 4 條月頻指標(NDC / PMI / 台灣出口 / 美核心 CPI)
# 原本**一個日期都沒有**,而它們的天然發布延遲是 1~27 天、資料歸屬月又是「上個月」
# ⇒ 送進 Gemini 時,一份 6 月的 CPI 與昨天的 VIX 在 prompt 裡長得一模一樣。
# LLM 只能當成「現在」講,使用者則以為 AI 講的是當下。
# `shared/staleness.stale_tag` 這個防護早就寫好了,但它唯一的消費者
# (`app_ai_service.build_llm_context`)0 caller —— 做好了卻從來沒接上。
#
# 【怎麼接】只借用 SSOT,**不**改吃 `build_llm_context`:後者是本區塊的**子集**
# (少了法人/融資/PCR/ADL/期貨/韭菜,且沒有 v19.178 的 `danger_rule_text` 門檻),
# 改吃它等於用資訊量更少的版本覆蓋掉現況(§2.1 收斂的方向要往資訊多的那邊收)。
# 門檻走 L0 `shared.staleness.monthly_stale_threshold`(每個指標依自己的發布
# 週期算,不是一律 40 天 —— 見該處註解:40 天會讓當期 CPI 每天都被誤標過期)。
# ══════════════════════════════════════════════════════════════════════
def _stale(_key: str, _d: dict) -> str:
    """月頻指標行首時效標記。`_d` 為 `macro_info[_key]`;無 date → 標「日期不明」。"""
    return _macro_stale_prefix(_key, (_d or {}).get('date'))


def _asof(_d: dict) -> str:
    """資料歸屬日註記。§1:抓不到日期要照實講,不留白讓 LLM 以為是今天。"""
    _v = str((_d or {}).get('date') or '').strip()
    return f'資料月份 {_v}' if _v else '資料月份不明'


def render_section_news_ai(_macro_info: dict, _tl_eff_reg: str) -> None:
    """渲染§十一 News AI 總裁決區(原 tab_macro line 4227-4521)。"""
    # F2(2026-08):原 `from app import gemini_call` —— 舊註解寫「lazy import,避
    # L5→L6 違憲於 module load 時 trigger」,但 late import **不會**讓上行 import
    # 變合憲,只是把它藏進函式體(§8.2.A.0 規則 5 的理由倒置)。真正的修法是換方向:
    # gemini_call 已下沉 L3。保留 late import 純粹是為了不在 module load 期拉依賴鏈。
    from src.services.app_ai_service import gemini_call  # noqa: F401
    # v18.398 P5-B3-β R8:news fetcher 已抽至 src/data/news
    from src.data.news import fetch_macro_news as _fetch_macro_news
    # ══════════════════════════════════════════════════════════════
    # SECTION 十一: 🤖 AI 總裁決（實體狀態鎖架構）
    # 前端唯讀 macro_state.json；LLM 運算由觸發按鈕在背景執行並寫檔
    # ══════════════════════════════════════════════════════════════
    # v19.168:§九 從「AI 綜合」桶群移出後(它是純規則引擎),本 section(真 Gemini AI 裁決)
    # 改為自行 emit 'ai' 桶群 banner(原由 §九 共用 emit)。
    from shared.macro_buckets import bucket_group_banner_html as _bgb
    st.markdown(_bgb('ai', 6), unsafe_allow_html=True)
    st.markdown(section_header('十一', '📰 新聞 ｜🤖 AI 總裁決', '🤖'), unsafe_allow_html=True)
    render_macro_bucket_summary_bar('news')  # v18.314 桶輕量總結 bar(新聞系統性風險)
    
    with st.expander('🤖 AI 總裁決 — 實體狀態鎖架構（唯讀）', expanded=True):
        _verdict_hdr_c1, _verdict_hdr_c2, _verdict_hdr_c3, _verdict_hdr_c4 = \
            st.columns([2.6, 1.2, 1.1, 1])
        with _verdict_hdr_c1:
            st.markdown(
                '<div style="font-size:12px;color:#8b949e;padding:4px 0;">'
                '整合即時國際財經新聞（RSS）與當前量化總經數據，'
                '由 Gemini AI 生成 Markdown 戰情報告。'
                '曝險上限由 Python 規則引擎計算，AI 負責解讀。'
                '<br><span style="color:#484f58;">「📰 掃描新聞」只抓新聞（免金鑰）；'
                '「🔒 執行 AI 裁決」需 Streamlit Secrets：'
                '<code>GEMINI_API_KEY = "AIza..."</code></span></div>',
                unsafe_allow_html=True)
        with _verdict_hdr_c2:
            # v19.73：獨立「掃描新聞」鈕——只抓 RSS、不需 Gemini 金鑰、不跑 AI。
            # 修使用者回報「新聞沒有讀取按鈕」（原本新聞只能靠 AI 裁決鈕順便抓）。
            _do_scan_news = st.button(
                '📰 掃描新聞', key='btn_scan_news', use_container_width=True,
                help='只抓即時財經新聞 RSS（不需 Gemini 金鑰、不跑 AI）；'
                     '掃完上方「新聞整體狀態」燈號會更新。')
        with _verdict_hdr_c3:
            _do_verdict = st.button('🔒 執行 AI 裁決', key='btn_run_verdict',
                                    use_container_width=True, type='primary')
        with _verdict_hdr_c4:
            if st.button('🗑️ 清除報告', key='btn_clear_verdict', use_container_width=True):
                st.session_state.pop('_macro_ai_report', None)
                st.session_state.pop('_macro_ai_ts', None)
                st.rerun()

        # ── 觸發：只掃新聞（免 AI 金鑰）→ 更新「新聞整體狀態」燈號 ──
        if _do_scan_news:
            with st.spinner('📡 抓取即時財經新聞 RSS…'):
                _scanned = _fetch_macro_news(5)
                st.session_state['_macro_news_items'] = _scanned
            st.success(f'✅ 已掃描 {len(_scanned)} 則新聞（上方燈號已更新）')
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
                # v19.173 正名:原註「MK 拐點」→ CPI×Fed 雙頂回落(MK ≠ Mann-Kendall)
                _fed_d  = _macro_info.get('fed_funds') or {}  # CPI×Fed 雙頂回落配對
                _mi_d   = st.session_state.get('m1b_m2_info') or {}
                _bi_d   = st.session_state.get('bias_info') or {}
                _li_d   = st.session_state.get('li_latest')
                # `選PCR` 欄位是 leading_indicators 寫入時已 ×100 的**百分比刻度**
                # （50~200）。`_pcr_v` 保留原始值僅供顯示 / 對帳，**不可**直接送任何
                # 吃「標準比值刻度」的消費端（規則引擎 / MACRO_ALERT_RULES）。
                _pcr_v  = None
                if _li_d is not None and not _li_d.empty and '選PCR' in _li_d.columns:
                    _pcr_raw = str(_li_d.iloc[-1].get('選PCR', ''))
                    if _pcr_raw not in ('', '-', 'nan', 'None'):
                        try:
                            _pcr_v = float(_pcr_raw)
                        except ValueError:
                            pass
                # v19.180 B2-b §4.1：換算**上移到取值端做一次**，規則引擎與 AI prompt
                # 共用同一個比值刻度變數。修的 bug：v19.178 只在 prompt 那行 inline
                # 換算，`_macro_numbers['PCR']` 仍送百分比刻度 → `pcr > 1.5` 對 126.80
                # 恆真 → 曝險分數系統性 −10 → 曝險上限恆低 10 個百分點。
                # 刻度不明（≤0 / >500 / NaN）→ None，§1 不猜、不回填中性預設。
                _pcr_ratio, _pcr_scale_src = _normalize_pcr(_pcr_v)
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
                    # v19.180 B2-b：送**標準比值刻度**（引擎契約，見
                    # `calculate_system_state` docstring）。原本送 `_pcr_v`
                    # （百分比刻度）是 100× 量綱錯。
                    'PCR':                 _pcr_ratio,
                    'Futures_Net_Short':   _fut_net_v,
                    'Index_Below_MA5':     _below_ma5,
                    'Sahm_Rule_Triggered': False,  # 尚無薩姆規則資料來源，預設 False
                }
                _system_state = calculate_system_state(_macro_numbers)
                # ── 組裝量化原始數據字串供新版 AI 提示語使用 ──────
                _cl_d_v = st.session_state.get('cl_data', {})
                # v19.175 P0:`.get('inst', {})` 的預設值只在 key 不存在時生效;
                # key 在、值為 None(上游三大法人全敗)時會讓下面 3 行 genexpr 拋
                # `TypeError: 'NoneType' object is not iterable` 炸掉總經分頁。
                # 收斂 + log 走 L2 SSOT(§1:缺失時三行量化脈絡直接不列給 LLM,
                # 不塞 0 讓它腦補「外資買賣超 0 億」)。
                _inst_v = coerce_inst_dict(_cl_d_v, where='section_news_ai')
                _fk_v   = next((k for k in _inst_v if '外資' in str(k)), None)
                _tk_v   = next((k for k in _inst_v if '投信' in str(k)), None)
                _dk_v   = next((k for k in _inst_v if '自營' in str(k)), None)
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
                    # v19.178:原「>15%偏貴、<-10%低估」為 prompt 內寫死,與五桶 SSOT
                    # (黃 10 / 紅 20,high_bad 單向)不符。負乖離側 SSOT **刻意不設門檻**
                    # (spec.note:「負乖離為超賣機會,非危險」),故如實告知而非另編一個 -10。
                    # I2(2026-08-10):TWII 歷史不足 240 天時,`bias_240` 的分母其實是
                    # MA<N>(見 macro_snapshot.compute_twii_bias)。這條**只送數字**時
                    # LLM 沒有任何依據能分辨,只能當實測年線寫進建議 —— 與 G1 的
                    # `[STALE:Nd]` 同一類問題,故沿用同一套行首標記 + 圖例。
                    _ctx.append(
                        f'• {_bias_est_prefix(_bi_d)}大盤年線乖離率 BIAS240：'
                        f'{_bi_d["bias_240"]:+.1f}%'
                        f'（{_danger_rule("bias_240")}；'
                        f'負乖離＝低於年線,系統視為超賣機會而非危險,不設危險門檻）')
                if _mi_d.get('m1b_yoy') is not None:
                    _gap_v = round(float(_mi_d['m1b_yoy']) - float(_mi_d.get('m2_yoy') or 0), 2)
                    _ctx.append(
                        f'• M1B={_mi_d["m1b_yoy"]:.1f}%  M2={_mi_d.get("m2_yoy",0):.1f}%  '
                        f'差額={_gap_v:+.2f}%（正=資金行情啟動；{_danger_rule("m1b_m2_gap")}）')
                if _fnet_v is not None:
                    _ctx.append(f'• 外資現貨買賣超：{_fnet_v:+.1f}億（{_danger_rule("foreign_net")}）')
                if _tnet_v is not None:
                    # 投信 / 自營商在五桶 SSOT 內**沒有**對應 DangerSpec → 誠實不給門檻,
                    # 不自行腦補一組(§1:沒有門檻好過錯誤的門檻)。
                    _ctx.append(f'• 投信買賣超：{_tnet_v:+.1f}億（系統未對此項設危險門檻）')
                if _dnet_v is not None:
                    _ctx.append(f'• 自營商買賣超：{_dnet_v:+.1f}億（系統未對此項設危險門檻）')
                if _margin_v is not None:
                    _ctx.append(f'• 融資餘額：{_margin_v:.0f}億（{_danger_rule("margin")}）')
                if _leek_v2 is not None:
                    # v19.177 §1:原文案寫「>80散戶過熱、<20散戶恐慌」—— 那是**另一個**
                    # 同名指標的尺度(融資餘額 5Y 標準化指數,值域 [0,100]、中位 50)。
                    # 本欄實際餵進來的 `韭菜指數` 是「小台法人空多比」
                    # (leading_indicators:(法人空方MTX OI − 法人多方MTX OI)/小台全體OI×100),
                    # **值域 ±100%、中位 0%**。兩者差一個量綱(§4.1)。
                    # 後果:實測 +34.7%(三套門檻都判過熱)會被 LLM 讀成「離 80 還很遠 →
                    # 情緒平穩」⇒ **AI 總經敘事系統性低估散戶過熱**。這是餵給模型的
                    # 錯誤事實,比畫面上寫錯更難察覺(§1「錯誤的數字比沒有數字更危險」)。
                    # 門檻一律引 SSOT(src/config/config.py:105-120),不在 prompt 內寫死。
                    _ctx.append(
                        f'• 韭菜指數（小台法人空多比）：{_leek_v2:+.1f}%'
                        f'（值域 ±100%、中性 0%；'
                        f'>{LEEK_PIVOT_HIGH_PCT:+.0f}% 散戶偏熱、'
                        f'>{LEEK_ALERT_HIGH_PCT:+.0f}% 極端過熱（頂部訊號）；'
                        f'<{LEEK_ALERT_LOW_PCT:+.0f}% 極端悲觀（軋空動能）)'
                    )
                if _pcr_ratio is not None:
                    # v19.180 B2-b:換算已上移至取值端(`_pcr_ratio`,SSOT
                    # `shared.pcr_scale.normalize_pcr_to_ratio`),此處只負責敘述,
                    # 不再自行 inline 換算 —— 那正是 v19.178 只修一半的根因:
                    # prompt 換算了、`_macro_numbers['PCR']` 沒換,同一份值兩種刻度。
                    # 判別線仍如實告訴 LLM,讓它知道畫面顯示的百分比與此處比值同源。
                    _ctx.append(
                        f'• 選擇權 PCR（Put/Call 比值）：{_pcr_ratio:.2f}'
                        f'（原始欄位值 {_pcr_v:.1f}；系統以 >{_PCR_PCT_SCALE_MIN:.0f} '
                        f'判定為百分比刻度並 ÷100 換回標準比值，'
                        f'本次判定：{_pcr_scale_src}；{_pcr_alert_rule()}）')
                if _adl_ratio_v is not None:
                    # v19.178 正名:原寫「ADR 廣度指標」—— ADR 在金融是 American
                    # Depositary Receipt(美國存託憑證),與本欄毫無關係,會誤導 LLM。
                    # 本欄實為 ADL 漲跌家數比(上漲家數佔比 %),與五桶 `adl` 同源同欄位。
                    _ctx.append(
                        f'• ADL 漲跌家數比（上漲家數佔全市場 %）：{_adl_ratio_v:.0f}%'
                        f'（{_danger_rule("adl")}）')
                if _fut_net_v is not None:
                    # v19.178 §4.1 量綱:本欄 = TX **當量口**(大台淨口 + 0.25×小台淨口),
                    # 非原始口數加總(evidence: leading_indicators.py:1267-1281)。原 prompt
                    # 只寫「口」且門檻 -35000 與畫面燈號(-10000/-20000)差 1.75 倍。
                    # 兩條門檻**都是真的但用途不同**,故兩條並列並各自標明來源。
                    _ctx.append(
                        f'• 外資期貨淨口數：{_fut_net_v:+.0f} 口'
                        f'（單位為 TX 當量口＝大台淨口＋0.25×小台淨口，非原始口數加總；'
                        f'負=淨空單；{_danger_rule("fut_net")}；'
                        f'另有系統硬否決線：淨口 <{MACRO_VETO_FUTURES_NET_SHORT_LOTS:+.0f} 口'
                        f'「且」指數同時跌破 MA5 → 強制曝險上限 '
                        f'{MACRO_VETO_FUTURES_EXPOSURE_CAP_PCT}%，此線比燈號嚴屬設計）')
                if _vix_d.get('current'):
                    _ctx.append(f'• VIX 恐慌指數：{_vix_d["current"]}（{_danger_rule("vix")}）')
                # v19.178 §1:原寫 `locals().get('_m8_ndc')` —— `_m8_ndc` 從未在本函式
                # 內賦值(它隨 §八 被抽到 section_mid 的 local),故此條 **永遠不會進 prompt**,
                # 是 dead context。NDC 實際就在本函式的 `_macro_info` 參數裡,直接取用。
                _ndc_v = _macro_info.get('ndc_signal') or {}
                if _ndc_v.get('score') is not None:
                    # G1:以下 4 條為**月頻**指標 —— 一律帶 as_of 月份 + 過期標記。
                    _ctx.append(
                        f'• {_stale("ndc_signal", _ndc_v)}NDC 景氣對策信號：'
                        f'{float(_ndc_v["score"]):.0f}分'
                        f'（{_asof(_ndc_v)}；國發會 9 項指標合成，分數越高景氣越熱；'
                        f'{_danger_rule("ndc_signal")}）')
                if _pmi_cur is not None:
                    _ctx.append(f'• {_stale("ism_pmi", _pmi_d)}'
                                f'台灣 PMI（製造業採購經理人指數）：{_pmi_cur}'
                                f'（{_asof(_pmi_d)}；{_danger_rule("ism_pmi")}；'
                                f'黃線即榮枯分界，低於代表製造業收縮）')
                if _exp_d.get('yoy') is not None:
                    # v19.178 正名:`tw_export` = 財政部海關**出口**年增率,不是經濟部
                    # 外銷訂單(v19.85 已於畫面正名,此處為漏網的第二份)。
                    _ctx.append(f'• {_stale("tw_export", _exp_d)}'
                                f'台灣出口 YoY（財政部海關出口金額年增率）：'
                                f'{_exp_d["yoy"]:+.1f}%'
                                f'（{_asof(_exp_d)}；{_danger_rule("tw_export")}）')
                if _cpi_d.get('yoy') is not None:
                    _ctx.append(f'• {_stale("us_core_cpi", _cpi_d)}'
                                f'美國核心 CPI YoY：{_cpi_d["yoy"]:+.1f}%'
                                f'（{_asof(_cpi_d)}；{_danger_rule("us_core_cpi")}；'
                                f'通膨高→升息壓力→壓抑高本益比成長股估值）')
                # v19.178 §1:`_ai_sox` / `_ai_nvda` 同樣從未在本函式賦值(它們是
                # section_cross_ai 的 local),故美股科技動能這條也是 dead context。
                # 修法需把 `tech_s` 一路傳進本 section(跨 section 參數改動,§8.4 屬
                # 分開提案),本版**不擴大改動面**,改為明確標注待接線,不再假裝有值。
                # (原碼 `locals().get(...) or 0` 會讓 if 恆為 False,靜默吞掉整條)
                _v_macro_ctx = '\n'.join(_ctx) if _ctx else '（數據尚未載入，請先按「🚀 一鍵更新全部數據」）'
                # G1:有任何一行被標過期 → 把圖例放在最前面。不解釋 `[STALE:Nd]`
                # 等於沒標(LLM 不會自己知道那是什麼);全部當期時不加,免製造雜訊。
                # I2:`[ESTIMATED:MA<N>/240]` 同理,各自獨立判斷、各自獨立附圖例。
                _ctx_legends = [
                    _lg for _lg in (_macro_stale_legend(_v_macro_ctx),
                                    _macro_est_legend(_v_macro_ctx)) if _lg
                ]
                if _ctx_legends:
                    _v_macro_ctx = '{}\n\n{}'.format('\n'.join(_ctx_legends),
                                                     _v_macro_ctx)
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
    
        # ── 唯讀渲染：市場體制/系統風險仍讀 macro_state.json ────────────
        _ms = load_macro_state()
        _srl = _ms.get('systemic_risk_level', '危險')
        _regime = _ms.get('market_regime', '系統異常')
        _ms_ts = _ms.get('timestamp', '')
        # v19.170 SSOT 修正:建議持股改讀 allocation_service,不再自行由
        # `_ms['exposure_limit_pct']` 算。原因:repo 中 macro_state.json 常不存在,
        # load_macro_state() 會回 _DEFAULT_STATE(exposure_limit_pct=0),
        # 而本 expander 預設 expanded=True → 會用 48px 巨字印「曝險 0%／現金 100%」,
        # 與 🎚️ 建議持股油門(如 20%)當場打架。
        # 函式內延遲 import:避免 module-level L5(ui)→L3(services) 循環匯入。
        from src.services.allocation_service import (
            get_allocation as _get_alloc,
            get_allocation_sleeves as _get_sleeves,
        )
        _alloc = _get_alloc()
        _sleeves = _get_sleeves()
    
        _srl_clr = {'安全': TRAFFIC_GREEN, '警告': TRAFFIC_YELLOW, '危險': TRAFFIC_RED}.get(_srl, '#8b949e')
        _reg_clr = {'多頭': TRAFFIC_GREEN, '震盪': TRAFFIC_YELLOW, '空頭': TRAFFIC_RED}.get(_regime, '#8b949e')

        # v19.170 §1 Fail Loud:總經未評估 → 本區塊「不得印出任何持股/現金數字」,
        # 只顯示未評估提示;禁止回填 0% / 100% 之類的預設值。
        if _alloc.is_loaded:
            _cash_disp = f"{_sleeves['貨幣/現金']}%" if _sleeves else '--'
            _alloc_block_html = (
                f'<div style="font-size:10px;color:#484f58;">'
                f'建議持股（同步自 🎚️ 建議持股油門）</div>'
                f'<div style="font-size:48px;font-weight:900;color:{_srl_clr};">'
                f'{_alloc.final_mid}<span style="font-size:18px;">%</span></div>'
                f'<div style="font-size:11px;color:#8b949e;">'
                f'區間 {_alloc.range_text}｜貨幣/現金 {_cash_disp}</div>'
            )
        else:
            _alloc_block_html = (
                '<div style="font-size:10px;color:#484f58;">'
                '建議持股（同步自 🎚️ 建議持股油門）</div>'
                '<div style="font-size:22px;font-weight:900;color:#8b949e;">'
                '⬜ 總經未評估</div>'
                '<div style="font-size:11px;color:#8b949e;">'
                '請先按「🚀 一鍵更新全部數據」</div>'
            )
    
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
            f'{_alloc_block_html}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True)
    
        # 快照時效檢查：與即時紅綠燈比對，不一致則提醒重新裁決（避免依過期判斷操作）
        # C1 v19.182:`_tl_eff_reg` 現為 canonical 結論(`calc_traffic_light` 的
        # `effective_regime`,與燈色同源),不再是由 icon 反推的值。
        # 未評估('unknown' / None)→ 對照不到中文 → `_live_reg_zh` 為空字串 →
        # 下方 gate 直接跳過提醒(§1:沒有即時判斷就不宣稱快照「不一致」)。
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
