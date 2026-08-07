"""TAB 教學：策略邏輯說明書（靜態 Markdown）— 從 app.py 抽出（PR P2-B Phase 5-A）

依賴極簡：streamlit + L0 shared 常數 + L4 `ui_widgets`（策略代號 / 標題 SSOT）；
內部所需 data_registry / shared.macro_card / pandas 皆在函式內 late import，
避免循環 import 與啟動成本。

呼叫端
======
- app.py: `with tab_edu: render_tab_edu()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.financial_health_thresholds import (  # 策略2 章節門檻 SSOT（§3.3）
    FH_ASSET_TURNOVER_MIN,
    FH_CASH_RATIO_SAFE_PCT,
    FH_CASH_RATIO_WATCH_PCT,
    FH_CASH_REINVEST_MIN_PCT,
    FH_CASHFLOW_ADEQUACY_MIN_PCT,
    FH_CASHFLOW_RATIO_MIN_PCT,
    FH_CURRENT_RATIO_MIN_PCT,
    FH_DEBT_RATIO_EXCELLENT_PCT,
    FH_DEBT_RATIO_PASS_PCT,
    FH_DEBT_RATIO_WARN_PCT,
    FH_DSO_FAST_DAYS,
    FH_DSO_SLOW_DAYS,
    FH_DUPONT_LEVERAGE_DEBT_PCT,
    FH_EARNINGS_QUALITY_MIN_PCT,
    FH_GROSS_MARGIN_GOOD_PCT,
    FH_LONG_TERM_FUNDING_MIN_PCT,
    FH_MOS_STRONG_PCT,
    FH_NET_MARGIN_PASS_PCT,
    FH_OPERATING_MARGIN_EXCELLENT_PCT,
    FH_QUICK_RATIO_MIN_PCT,
    FH_ROE_LEVERAGE_CHECK_PCT,
    FH_ROE_TOP_PCT,
)
from shared.fred_series import FRED_NAPM
from shared.signal_thresholds import (  # B6-a v19.181:VCP 章風控數字改吃 SSOT
    ATR_STOP_MULTIPLIER,
    RR_DEFAULT_TARGET_GAIN,
    RR_MIN,
    STOP_LOSS_DEFAULT_PCT,
    VCP_ATR_CONTRACTION_RATIO,
)
from shared.ttls import TTL_1DAY
from src.ui.render.ui_widgets import (  # v19.175：章節標題改吃策略代號 SSOT
    STRATEGY_FINANCIAL,
    STRATEGY_TECHNICAL,
    STRATEGY_VALUATION,
    strategy_label,
)


# #U7：單值總經指標若 identifier 為 FRED series id → 可抓歷史序列畫 sparkline
#
# ⚠️ B6-a v19.181 移除 `FRED_NAPM: 'lin'`（§1 反捏造）：
#   下方 `_single` 把 `FRED_NAPM` 這個 key 對到 `macro_info['ism_pmi']`，
#   而該 key 的**內容其實是台灣 PMI**（`macro_snapshot.fetch_tw_pmi_block:649-659`
#   明講「session_state key 仍為 'ism_pmi' 維持向後相容，內容是台灣 PMI」）。
#   一旦掛上 FRED `NAPM`（**美國** ISM）序列，就會拿台灣的當期值去跟美國的
#   歷史分布算 Z-Score（`:471 calc_z_score(_series, _val)`）—— 那個 Z 是假的，
#   閾值線也是美規的。寧可沒有趨勢圖，也不要一個跨國混算的 Z。
#   要恢復 sparkline，得先接上**台灣** PMI 的歷史序列（`tw_macro.fetch_pmi_history`）。
_FRED_EDU_UNITS = {'CPILFESL': 'pc1', 'XTEXVA01TWM664S': 'pc1'}


# ════════════════════════════════════════════════════════════════
# B6-a v19.181 — 教學文案的「活數字」佔位符（§3.3 反捏造 / SSOT）
# ────────────────────────────────────────────────────────────────
# 【為什麼要有這一層】
# 這份說明書被 user 當**學習材料**在讀。全面對帳後發現：凡是門檻 / 係數 /
# 來源清單用**手打字串**寫進教學段落的地方，最後全都跟實作漂開了 ——
#   - PMI 多源「賽跑 10 個源(…MacroMicro…FinMind…)」→ 實際 8 源，
#     MacroMicro v19.113 拔除、FinMind v19.85 拔除（同一頁 :161 已是新版，
#     原理教室那段沒跟著改 ⇒ 同一份文件自己打自己）
#   - 衰退機率 logit 手寫 `0.5 + 0.55 × spread` → 實作是 −0.8 / −1.5
#   - 外資期貨「系統實際 logic」手寫 −50000 + MA240 → 全站不存在這條規則
#
# 【對策】可被 code 證實或證偽的數字**一律不手寫**，寫成 `§§TOKEN§§`，
# 由 `_resolve_edu_tokens()` 在 render 期從 SSOT 取值替換。
# 之後改常數，文案自動跟著動；漏掉的 token 會**原樣印在畫面上**（不是靜默
# 消失），等於自己會喊的 §1 fail-loud。
#
# 用 `§§…§§` 而不是 `str.format` 的 `{}`：教學段落裡有大量 markdown 表格與
# code fence，套 `.format()` 會被 `{` 誤炸；token 取代是純字串替換，零風險。
# ════════════════════════════════════════════════════════════════

def _edu_tokens() -> dict[str, str]:
    """教學文案 token → SSOT 實值。**每次 render 現算**，不做 module-level 快取。

    L1 的 `PMI_SOURCE_REGISTRY` 走函式內 late import（§8.2.A EX-PASSTHRU-1：
    L5 → L1 pass-through 讀取，模組載入期不拉整條 macro 依賴鏈）。
    """
    import math as _m
    import sys as _sys

    from shared.signal_thresholds import (
        BREADTH_BULL_PCT,
        BREADTH_NEUTRAL_PCT,
        FOREIGN_5D_NET_THRESHOLD_YI,
        FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD,
        FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
        FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
        MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
        MARGIN_BALANCE_WARN_THRESHOLD_YI,
        RECESSION_LOGIT_COEF_INTERCEPT,
        RECESSION_LOGIT_COEF_SPREAD,
        TWII_20D_DROP_THRESHOLD_PCT,
        VIX_HIGH_RISK_THRESHOLD,
        VIX_MEDIUM_RISK_THRESHOLD,
    )
    from src.config import LEEK_ALERT_HIGH_PCT, LEEK_ALERT_LOW_PCT

    def _recession_p(spread: float) -> float:
        """複刻 `macro_core.recession_probability` 的算式（同一組 SSOT 係數）。"""
        _logit = RECESSION_LOGIT_COEF_SPREAD * spread + RECESSION_LOGIT_COEF_INTERCEPT
        return round(1 / (1 + _m.exp(-_logit)) * 100, 1)

    # PMI 多源賽跑順序 —— 名單與筆數皆取 registry，不手抄
    try:
        from src.data.macro.macro_core import PMI_SOURCE_REGISTRY
        _pmi_names = [_n for _n, _fn in PMI_SOURCE_REGISTRY]
    except Exception as _e_pmi:  # noqa: BLE001 — 教學頁不因 macro 依賴失敗而整頁炸
        print(f'[tab_edu] PMI_SOURCE_REGISTRY 讀取失敗:'
              f'{type(_e_pmi).__name__}: {_e_pmi} → 來源清單顯示「暫無法讀取」',
              file=_sys.stderr)
        _pmi_names = []

    return {
        '§§PMI_SOURCES§§': (' → '.join(_pmi_names) if _pmi_names
                            else '（暫無法讀取 PMI_SOURCE_REGISTRY）'),
        '§§PMI_SOURCE_COUNT§§': str(len(_pmi_names)) if _pmi_names else '—',
        '§§RECESSION_COEF_SPREAD§§': f'{RECESSION_LOGIT_COEF_SPREAD:g}',
        '§§RECESSION_COEF_INTERCEPT§§': f'{RECESSION_LOGIT_COEF_INTERCEPT:g}',
        '§§RECESSION_P_AT_0§§': f'{_recession_p(0.0):.0f}',
        '§§RECESSION_P_AT_M1§§': f'{_recession_p(-1.0):.0f}',
        '§§RECESSION_P_AT_M2§§': f'{_recession_p(-2.0):.0f}',
        '§§FUT_DEFENSE_LOTS§§': f'{FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD:,}',
        '§§FUT_V4_RED_LOTS§§': f'{FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS:,}',
        '§§FUT_V4_YELLOW_LOTS§§': f'{FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS:,}',
        '§§VIX_V4_RED§§': f'{VIX_HIGH_RISK_THRESHOLD:g}',
        '§§VIX_V4_YELLOW§§': f'{VIX_MEDIUM_RISK_THRESHOLD:g}',
        '§§FOREIGN_5D_YI§§': f'{FOREIGN_5D_NET_THRESHOLD_YI:,.0f}',
        '§§TWII_20D_PCT§§': f'{TWII_20D_DROP_THRESHOLD_PCT:g}',
        '§§MARGIN_WARN_YI§§': f'{MARGIN_BALANCE_WARN_THRESHOLD_YI:,.0f}',
        '§§MARGIN_OVERHEAT_YI§§': f'{MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:,.0f}',
        '§§LEEK_ALERT_HIGH§§': f'{LEEK_ALERT_HIGH_PCT:+g}',
        '§§LEEK_ALERT_LOW§§': f'{LEEK_ALERT_LOW_PCT:+g}',
        '§§BREADTH_BULL§§': f'{BREADTH_BULL_PCT:g}',
        '§§BREADTH_NEUTRAL§§': f'{BREADTH_NEUTRAL_PCT:g}',
    }


def _resolve_edu_tokens(text: str, tokens: dict[str, str] | None = None) -> str:
    """把教學文字裡的 `§§TOKEN§§` 換成 SSOT 實值。

    `tokens` 省略時現算一份（單一段落用）；批次渲染多段時請先呼叫
    `_edu_tokens()` 取一份重複傳入，避免每段都重跑 late import。
    未登記的 token **保持原樣**印在畫面上 —— 這是刻意的：
    漏改的佔位符要看得見（§1 降級不靜默），不可悄悄消失成空字串。
    """
    if tokens is None:
        tokens = _edu_tokens()
    for _k, _v in tokens.items():
        text = text.replace(_k, _v)
    return text


# ════════════════════════════════════════════════════════════════
# v19.175 — 說明書策略章節標題（import 期組好，錯了立刻 ValueError）
#
# 背景：v19.174 去識別化後，說明書 4 個策略章節的標題是**手打字串**
# 「📐 策略3（技術 / 動能）— …」。實機 DOM 掃描抓到兩件事：
#   (1) 「策略2」+「🏥」全站 0 次；
#   (2) 三章都掛「策略3」，但其中兩章括號寫「（技術 / 動能）」、
#       一章寫「（資金面）」—— 同一代號兩種括號說明。
#
# 判定（查 v19.174 刪掉的 `_STRATEGY_MAP` 原始分組後的結論，不是猜）：
#   - 型態學 / VCP / 資金動能 三章原本就同屬「策略3：技術 / 動能 / 資金面」
#     那一組，**三章都叫策略3 是對的**，不是遷移時把策略2 錯標成策略3。
#   - 真正的兩個缺陷是：
#       a. 說明書從來沒有 **策略2（財報體檢）** 這一章
#          → `STRATEGY_FINANCIAL` 全站 0 個 caller，🏥 永遠不出現。
#          本次補章，門檻一律 import `shared/financial_health_thresholds`，
#          與 🔬 個股 / 🏆 個股組合 的財報體檢同一份 SSOT。
#       b. 括號是各 caller 手打 → 同代號兩種說明。
#          本次改由 `ui_widgets.strategy_label()` 統一產出（該函式已移除
#          scope 覆寫參數，一個代號只有一種括號），章節之間的差異一律寫在
#          破折號後面的**主題**。
# ════════════════════════════════════════════════════════════════
_EDU_STRATEGY_TITLES: dict[str, str] = {
    # key → 章節 emoji + 「策略N（範疇）」(SSOT) + 「— 主題」(本章專屬)
    'valuation_leading': (
        f'📊 {strategy_label(STRATEGY_VALUATION)}'
        f' — 財報領先指標與盈餘成長選股'),
    'financial_health': (
        f'🏥 {strategy_label(STRATEGY_FINANCIAL)}'
        f' — 四關體檢：存活 × 財務結構 × 償債 × 獲利'),
    'pattern': (
        f'📐 {strategy_label(STRATEGY_TECHNICAL)}'
        f' — 型態學：破底翻 × 頭肩底 × 頸線突破'),
    'vcp': (
        f'🌀 {strategy_label(STRATEGY_TECHNICAL)}'
        f' — VCP 波幅收縮與爆量突破'),
    'liquidity': (
        # v19.179 §1:標題原寫「均線多頭家數」—— 但本章內文（:672-690）v19.178 已改成
        # 誠實版,明講「本系統**沒有**站上年線家數比這個數據,全站沒有任何一行程式在算
        # 它」。標題卻還在宣傳該指標 ⇒ 同一章自我打臉,且標題比內文先被看到,誤導性更強。
        # 改用本系統真正在算的量:旌旗指數 ＝ 上漲佔比（單日）的 5 日移動平均
        # （evidence: src/services/jingqi_calc.py 的 ad_ratio 5 日均）。
        f'💰 {strategy_label(STRATEGY_TECHNICAL)}'
        f' — 資金動能 M1B-M2 × 旌旗指數（市場廣度）× 外資期貨防守'),
}


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _fetch_fred_series_edu(series_id: str, units: str = 'lin', months: int = 24):
    """抓 FRED 指標近 N 月歷史序列（教學 tab sparkline 用）；units=pc1 取 YoY%。失敗回 None。"""
    try:
        import os as _o
        import pandas as _pd
        from src.data.proxy import fetch_url as _fu
        _key = (_o.environ.get('FRED_API_KEY')
                or (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else '') or '')
        if not _key:
            return None
        _r = _fu('https://api.stlouisfed.org/fred/series/observations',
                 params={'series_id': series_id, 'api_key': _key, 'file_type': 'json',
                         'units': units, 'sort_order': 'desc', 'limit': months},
                 timeout=12, attempts=1)
        if _r is None or getattr(_r, 'status_code', 0) != 200:
            return None
        _pairs = [(_ob['date'], float(_ob['value']))
                  for _ob in _r.json().get('observations', [])
                  if _ob.get('value') not in ('.', '', None)]
        if len(_pairs) < 3:
            return None
        _pairs.sort(key=lambda x: x[0])
        _result = _pd.Series([v for _, v in _pairs],
                             index=_pd.to_datetime([d for d, _ in _pairs]))
        # v18.357 PR-Q5c S-PROV-1 phase 19:Series attrs
        try:
            _result.attrs.setdefault('source', f'FRED:{series_id}:units={units}:months={months}')
            _result.attrs.setdefault('fetched_at', _pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _result
    except Exception:
        return None


def render_tab_edu():
    st.markdown('## 📖 系統說明書 — 公式、策略與資料來源完整說明')
    # v19.174 去識別化：原文的稱謂已改為中性表述
    st.caption('整理自公開教學資源，僅供學術研究。投資涉及風險，本系統不構成買賣建議，盈虧自負。'
               '｜v18.281 合併原理教室 + 資料來源地圖,單一說明書集中查閱。')

    # ════════════════════════════════════════════════════════════
    # v18.281 — ⓪ 資料來源完整地圖(學 Fund tab6 Section ⓪)
    # 每筆資料 → 用在哪個 Tab → 來源 endpoint → refresh → fallback
    # ════════════════════════════════════════════════════════════
    with st.expander('⓪ 📊 資料來源完整地圖（每筆資料→Tab→endpoint→refresh→fallback）',
                     expanded=False):
        st.caption('本系統各 Tab 用到的所有資料來源,對照 CLAUDE.md §2.1 SSOT 5-Tier 權威分級。'
                   '**任一筆失敗會在 🔎 資料診斷 Tab 用紅燈標出**。')
        _dm = [
            ('📈 美國總經指標', '🌍 總經',
             'FRED API（NAPM / DGS10 / DGS2 / DGS3MO / BAMLH0A0HYM2 / M2SL / WALCL / CPIAUCSL / FEDFUNDS / UNRATE / PPIACO）',
             'FRED 30min / 月後 ~13 天（CPI/NFP 有修正）',
             'FRED → DBnomics → ISM 官網 → MacroMicro'),
            ('📊 VIX / DXY / 銅', '🌍 總經',
             'Yahoo Chart（^VIX / DX-Y.NYB / HG=F）',
             'Yahoo 1hr / EOD 翌日 04:00 TW',
             'Yahoo → CBOE CDN（VIX）'),
            ('🇹🇼 TW PMI', '🌍 總經',
             '8 源賽跑：CIER-EN → data.gov.tw → NDC → CIER首頁 → StockFeel → Cnyes → CIER-cid8 → MoneyDJ（v19.113）',
             '月後第 1 營業日',
             'PMI_SOURCE_REGISTRY 順序賽跑,取第一命中（禁止平均）'),
            ('🏦 CBC M1B / M2', '🌍 總經',
             'CBC ms1.json（央行）',
             '月後 ~5-7 天,90 天 cache',
             'CBC（TWD）→ IMF（USD,僅 fallback,禁跨幣別平均）'),
            ('🇨🇳 中國拖累 modifier', '🌍 總經',
             'FRED（CNCPIALLMINMEI / IRLTCT01CNM156N / MYAGM3CNM189N / XTEXVA01CNM664S）',
             '月頻,90 天 cache',
             '全敗 → modifier = 1.0 中性'),
            # B6-a v19.181:Tab 名對齊 app.py:476/568/584/809/870 的真實 label。
            # 原寫「📈 個股」「💰 籌碼」—— 前者 emoji 錯(真名 🔬 個股),
            # 後者根本不是 Tab(籌碼是 🌍 總經 底下的 §三 區塊),照著找找不到。
            ('💹 個股 OHLCV', '🔬 個股',
             'TWSE OpenAPI / TPEX OpenAPI / FinMind / Yahoo',
             '同日盤後 14:30 TW,30min cache',
             'TWSE → FinMind → Yahoo'),
            ('💰 三大法人 / 融資', '🔬 個股 / 🌍 總經§籌碼',
             'TWSE 三大法人表 / TWSE 融資餘額',
             '同日盤後,30min cache',
             'TWSE → HiStock → Wearn（融資）'),
            ('📐 期貨 / 選擇權 PCR', '🌍 總經§籌碼',
             'TAIFEX（外資 TX 期貨 / Put-Call Ratio）',
             '同日盤後 14:00 TW',
             'TAIFEX 主源,無備援'),
            ('📅 月營收', '🔬 個股',
             'FinMind / MOPS / Goodinfo',
             '月後 ~10 天,3 天 cache',
             'FinMind → MOPS → Goodinfo'),
            ('🏦 ETF NAV / 持股', '🏦 ETF',
             'etf_fetch（TWSE / 投信官網）',
             '2hr cache',
             'fallback chain 內部處理'),
            ('📰 新聞 RSS', '🌍 總經',
             'Google News / Bloomberg / CNBC / Yahoo Finance',  # v18.458: Reuters removed (dead since 2020)
             '即時',
             '個別失敗 → 其他源繼續'),
            # B6-a v19.181:原寫「EX-AI-1 例外,回 str」—— EX-AI-1 這條例外
            # 已於 v18.399 P5-DEAD-δ 隨 `ai_engine.py` 整檔刪除而**正式退役**
            # (CLAUDE.md §0 步驟 4 + §8.2.A 該列已標「已退役」)。
            # 現行 AI 走 `app.py:gemini_call` → `ai_fetcher.post_gemini`,
            # prompt 由 `ai_structured_summary.build_structured_summary_prompt` 組。
            ('🤖 AI 摘要', '🌍 總經 / 🔬 個股',
             'Google Gemini API（ai_fetcher.post_gemini）',
             'On-demand 無 cache',
             'GEMINI_KEY 未設 → AI 區塊跳過（不擋畫面）'),
        ]
        _th = ('font-size:10px;color:#888;font-weight:700;padding:8px 10px;'
               'border-bottom:1px solid #30363d')
        _td = 'font-size:11px;padding:8px 10px;line-height:1.4'
        _html = (
            f"<div style='display:grid;grid-template-columns:1.4fr 1.1fr 2.6fr 1.5fr 2.2fr;"
            f"background:#0d1117;border-radius:6px 6px 0 0'>"
            f"<span style='{_th}'>資料項目</span>"
            f"<span style='{_th}'>用在 Tab</span>"
            f"<span style='{_th}'>來源 / endpoint</span>"
            f"<span style='{_th}'>Refresh / 延遲</span>"
            f"<span style='{_th}'>Fallback chain</span></div>"
        )
        for _item, _tab, _src, _ref, _fb in _dm:
            _html += (
                f"<div style='display:grid;grid-template-columns:1.4fr 1.1fr 2.6fr 1.5fr 2.2fr;"
                f"background:#0d1117;border-bottom:1px solid #21262d'>"
                f"<span style='{_td};color:#e6edf3;font-weight:600'>{_item}</span>"
                f"<span style='{_td};color:#79c0ff'>{_tab}</span>"
                f"<span style='{_td};color:#bbb;font-family:monospace;font-size:10px'>{_src}</span>"
                f"<span style='{_td};color:#888'>{_ref}</span>"
                f"<span style='{_td};color:#a5d6ff;font-size:10px'>{_fb}</span></div>"
            )
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_html}</div>", unsafe_allow_html=True)
        st.caption('**📖 對應憲法**：CLAUDE.md §2.1 SSOT（5-Tier）、§2.3 PIT（發布延遲）、'
                   '§2.4 Freshness（TTL）、§4.6 領域邊界。任一筆紅燈 → 🔎 資料診斷 Tab 找對應 fetcher 修。')

    # ── 📖 指標解讀手冊（從 data_registry 自動生成）──────────────
    # v17: 新增「即時數值 + 24M 趨勢圖」chip + sparkline，使用 shared/macro_card 共用模組
    with st.expander('📖 指標解讀手冊 — 數字 + 趨勢 + 完整教學', expanded=True):
        try:
            from src.data.core import (
                get_categories, get_by_category, get_edu, get_edu_count,
                render_edu_card_html,
            )
            from shared.macro_card import calc_z_score, make_sparkline
            import pandas as _pd_edu

            # ─── identifier → (current_value, pd.Series|None, t_warn, t_crit, high_is_bad) ───
            def _get_indicator_data(identifier: str):
                """從 session_state 取出指標的即時值 + 24M series + 警戒/危險閾值。

                覆蓋範圍：
                  ✓ 有 series：^VIX / ^TNX / ^SOX / DX-Y.NYB（cl_data.intl 有 90D OHLC）
                  ✓ 僅單值：CPILFESL / NAPM / XTEXVA01TWM664S / NDC_signal /
                            ms1.json / MI_MARGN / BFI82U（macro_info / m1b_m2_info / cl_data）
                  ✗ 無資料：BWIBBU_d（TWSE 大盤散點資料，無單一聚合值，請至個股 Tab 看）
                """
                _macro = st.session_state.get('macro_info') or {}
                _cl    = st.session_state.get('cl_data') or {}
                _intl  = _cl.get('intl') or {}
                _m1b   = st.session_state.get('m1b_m2_info') or {}
                _bias  = st.session_state.get('bias_info') or {}

                # ─ 國際金融（有完整 OHLC DataFrame）─
                _intl_map = {
                    '^TNX':      ('10Y公債殖利率', 4,    5,   True),
                    '^SOX':      ('費城半導體 SOX', None, None, False),
                    'DX-Y.NYB':  ('美元指數 DXY',   105,  110, True),
                }
                if identifier in _intl_map:
                    _name, _tw, _tc, _hib = _intl_map[identifier]
                    _df = _intl.get(_name)
                    if _df is not None and not _df.empty:
                        _ccol = 'Close' if 'Close' in _df.columns else (
                            'close' if 'close' in _df.columns else None)
                        if _ccol:
                            _s = _df[_ccol].dropna()
                            if len(_s) >= 2:
                                return float(_s.iloc[-1]), _s, _tw, _tc, _hib
                    return None, None, _tw, _tc, _hib

                # ─ ^VIX：macro_info.vix 已有 60 天 series ─
                if identifier == '^VIX':
                    _v = _macro.get('vix') or {}
                    if _v.get('values') and _v.get('dates'):
                        try:
                            _s = _pd_edu.Series(_v['values'],
                                                index=_pd_edu.to_datetime(_v['dates']))
                            return _v.get('current'), _s, 22, 30, True
                        except Exception:
                            pass
                    return _v.get('current'), None, 22, 30, True

                # ─ 單值類（無 series，但顯示當前值 + 閾值線）─
                _single = {
                    'CPILFESL':       ((_macro.get('us_core_cpi') or {}).get('yoy'),         2.5,  4,    True),
                    FRED_NAPM:        ((_macro.get('ism_pmi')     or {}).get('value') or
                                       (_macro.get('ism_pmi')     or {}).get('current'),     50,   45,   False),
                    'XTEXVA01TWM664S':  ((_macro.get('tw_export')   or {}).get('yoy'),         0,    -5,   False),
                    'NDC_signal':     ((_macro.get('ndc_signal')  or {}).get('score') or
                                       (_macro.get('ndc_signal')  or {}).get('value'),       32,   22,   None),
                    'ms1.json':       ((_m1b.get('m1b_yoy')      or 0) -
                                       (_m1b.get('m2_yoy')        or 0)
                                       if (_m1b.get('m1b_yoy') is not None
                                           and _m1b.get('m2_yoy') is not None)
                                       else None,                                            0,    -2,   False),
                }
                # ─ BFI82U：三大法人現貨買賣超（取外資 net，億）─
                if identifier == 'BFI82U':
                    _inst = _cl.get('inst') or {}
                    _foreign_key = next((k for k in _inst if '外資' in str(k)), None)
                    if _foreign_key:
                        _net = _inst.get(_foreign_key, {}).get('net')
                        if _net is not None:
                            _val = float(_net) / 1e8 if abs(float(_net)) > 1e6 else float(_net)
                            return _val, None, 0, -100, False
                    return None, None, 0, -100, False

                if identifier in _single:
                    _v, _tw, _tc, _hib = _single[identifier]
                    _funits = _FRED_EDU_UNITS.get(identifier)
                    if _funits is not None:
                        _ser = _fetch_fred_series_edu(identifier, _funits)
                        if _ser is not None and len(_ser) >= 3:
                            return ((_v if _v is not None else float(_ser.iloc[-1])),
                                    _ser, _tw, _tc, _hib)
                    return _v, None, _tw, _tc, _hib

                # ─ 其他（暫無資料，後續 PR 處理）─
                return None, None, None, None, None

            # ── B6-a v19.181:「已撰寫 N 個」改數**真的會渲染出來的**卡片 ──────
            # 原本寫 `get_edu_count()` = `len(EDU_GUIDE)`,但下方渲染迴圈只印
            # 「EDU key 能對上 DATA_REGISTRY.identifier」的卡（:462-463 的 join）。
            # 兩個 EDU key 對不上任何 identifier（`NAPM`、`NDC_signal` —— registry
            # 用的是 `cier-pmi` / `TaiwanBusinessIndicator` 等），所以宣稱數字比
            # 畫面上看得到的多 2 張，使用者會一直找那兩張找不到的卡。
            # 改成先把要渲染的清單算出來再報數 → 「說的」與「畫的」同一份資料。
            _cat_pairs: list[tuple[str, list]] = []
            for _cat in get_categories():
                _pairs = [(e, get_edu(e.get('identifier')))
                          for e in get_by_category(_cat)]
                _pairs = [(e, ed) for e, ed in _pairs if ed is not None]
                if _pairs:
                    _cat_pairs.append((_cat, _pairs))
            _edu_total = sum(len(_p) for _, _p in _cat_pairs)
            _edu_written = get_edu_count()
            # 掛不上任何 identifier 的教學文稿數 —— 有就誠實講,沒有就不提(§1)
            _edu_orphans = max(_edu_written - _edu_total, 0)
            _edu_orphan_note = (
                f'　⚠️ 另有 **{_edu_orphans} 篇**教學文稿已寫好但**掛不上任何指標**'
                f'（EDU key 對不到 `DATA_REGISTRY` 的 identifier），因此不會顯示 —— '
                f'這是待修的接線問題，不是你漏看。'
            ) if _edu_orphans else ''
            st.markdown(
                f"""
**新人最大的痛點**：指標一堆，但每個是什麼？要怎麼看？要搭配什麼一起看？
本手冊把每個核心指標拆解成 **6 個問題** + **24 個月趨勢圖**：

| 問題 | 內容 |
|------|------|
| 💡 **是什麼** | 用一句白話解釋這個指標在量什麼 |
| 📐 **怎麼判讀** | 數字到了哪個門檻代表什麼訊號 |
| 🔗 **搭配看什麼** | 不能只看單一指標，要對照哪些指標 |
| 📊 **歷史錨點** | 歷史上的關鍵數字（讓你有比例尺） |
| ⬆️ **上游因** | 誰會影響這指標（找根源） |
| ⬇️ **下游果** | 這指標會影響誰（找連動效應） |
| 📈 **即時值 + 24M 趨勢** | 當前值 + Z-Score + 趨勢圖（含警戒/危險閾值線） |

📌 本頁下方會列出 **{_edu_total} 張** 核心指標教學卡（持續擴充中）。
未列出的指標請見「🔎 資料診斷」Tab → 各類別展開查看完整資料目錄。
{_edu_orphan_note}
""")
            st.markdown('---')
            for _cat, _edu_pairs in _cat_pairs:
                st.markdown(f'### {_cat}')
                for _e, _edu in _edu_pairs:
                    _id = _e.get('identifier', '')
                    _val, _series, _tw, _tc, _hib = _get_indicator_data(_id)
                    # ─ 即時值 + Z-Score chip ─
                    _z = (calc_z_score(_series, _val)
                          if _series is not None and len(_series) >= 10 else None)
                    if _val is not None or _series is not None:
                        _val_str = (f"{_val:.2f}" if isinstance(_val, (int, float))
                                    else "—")
                        _z_str   = f"  Z={_z:+.2f}" if _z is not None else ""
                        _z_color = (MATERIAL_RED if _z is not None and abs(_z) >= 2 and
                                    ((_hib and _z > 0) or (_hib is False and _z < 0))
                                    else (MATERIAL_GREEN if _z is not None and abs(_z) >= 2
                                          else (MATERIAL_ORANGE if _z is not None and abs(_z) >= 1.5
                                                else "#79c0ff")))
                        st.markdown(
                            f"<div style='display:flex;gap:14px;align-items:baseline;"
                            f"margin:14px 0 0;padding:8px 14px;background:#161b22;"
                            f"border:1px solid #30363d;border-radius:8px 8px 0 0;"
                            f"border-bottom:none'>"
                            f"<span style='color:#8b949e;font-size:11px;font-weight:600;"
                            f"letter-spacing:1px'>📈 即時值與趨勢</span>"
                            f"<span style='color:#e6edf3;font-size:18px;font-weight:700'>"
                            f"{_val_str}</span>"
                            f"<span style='color:{_z_color};font-size:12px'>{_z_str}</span>"
                            f"</div>",
                            unsafe_allow_html=True)
                        # ─ Sparkline（有 series 才畫）─
                        if _series is not None and len(_series) >= 2:
                            # v18.440 修:make_sparkline 簽章為
                            # (values, dates, height, line_color, threshold_warn, threshold_crit)
                            # 原呼叫傳了不存在的 high_is_bad / lookback → TypeError
                            # (教學分頁原本未綁定渲染,故此 latent bug 一直沒被觸發)。
                            # lookback=60 改 slice 最後 60 點;轉 list 確保 make_sparkline 內
                            # values[-1] 不踩 pandas label-index。high_is_bad 上方 Z 卡已用,sparkline 不需。
                            _fig = make_sparkline(
                                list(_series)[-60:],
                                threshold_warn=_tw, threshold_crit=_tc,
                                height=70,
                            )
                            if _fig is not None:
                                st.plotly_chart(
                                    _fig, use_container_width=True,
                                    config={'displayModeBar': False},
                                    key=f'spark_{_id}_{_cat}')
                        else:
                            st.caption("⚠️ 此指標目前僅有單一最新值，趨勢圖待後續 PR 補齊（需擴充 macro fetcher）")
                    # ─ 既有 EDU HTML 卡（白話/判讀/搭配/上下游/歷史）─
                    st.markdown(render_edu_card_html(_e, _edu),
                                unsafe_allow_html=True)
        except ImportError as _ie:
            st.error(f'❌ 無法載入 data_registry：{_ie}')

    # ── 策略章節導讀（v19.175：解「三章都叫策略3」的閱讀困惑）────────
    st.markdown('---')
    st.markdown('### 🧭 三大策略分類導讀')
    # 括號範疇一律取 `strategy_label()`（SSOT），此處**不重寫**；破折號後的
    # 「例：…」是舉例用的指標名稱，不是範疇定義，改動不會造成代號↔括號不一致。
    st.caption(
        '本說明書把選股邏輯收斂為三類（括號內範疇是全站唯一說法）：'
        f'**{strategy_label(STRATEGY_VALUATION)}** 例：殖利率、357 區間、年線位階；'
        f'**{strategy_label(STRATEGY_FINANCIAL)}** 例：現金、負債、毛利、盈餘品質；'
        f'**{strategy_label(STRATEGY_TECHNICAL)}** 例：型態、VCP、均線、M1B-M2、法人籌碼。'
        f'　⚠️ {STRATEGY_TECHNICAL} 涵蓋面最廣，底下有「型態學 / VCP / 資金動能」**三章**，'
        '三章的代號與括號完全相同，差異寫在破折號後的主題 —— '
        '這是分類本來就寬，不是章節編號重複。')

    # ── 策略1（估值 / 存股）v19.174 去識別化；v19.175 標題改吃 SSOT ────
    with st.expander(_EDU_STRATEGY_TITLES['valuation_leading'], expanded=True):
        st.markdown("""
### 核心邏輯：在「業績加速成長」前提早佈局

本策略強調，股價長期反映的是企業「未來盈餘的折現值」。
市場往往落後財報數字，懂得讀「領先財報」的人就能在機構法人之前看見機會。

---

#### 🔑 財報領先指標一：合約負債（Contract Liabilities）

> **白話定義**：客戶已付錢但公司尚未交貨 → 代表「口袋裡的訂單」

| 門檻 | 訊號 | 意義 |
|------|------|------|
| 合約負債 **> 股本 50%** | 🟢 龍多信號 | 訂單爆滿，未來 1–2 季業績有保證 |
| 合約負債 **> 股本 100%** | 🔥 超強信號 | 產能供不應求，定價權在手 |
| 合約負債持續季增 | 🔼 加分項 | 訂單持續進來，成長趨勢確認 |

**篩選口訣**：合約負債高 → 代表「客戶先給錢」，這樣的公司最不怕景氣波動。

---

#### 🔑 財報領先指標二：資本支出（CapEx）

> **白話定義**：公司在大買機器、蓋廠房 → 代表對未來「投票」

| 門檻 | 訊號 | 意義 |
|------|------|------|
| 資本支出 **> 股本 80%** | 🟢 擴張信號 | 大膽押注未來需求，對訂單有把握才會花這麼多 |
| 資本支出連續 2 季增加 | 🔼 加分項 | 不是一次性，是持續擴產 |

---

#### 🔑 盈餘成長率：EPS 加速是關鍵

- **近 4 季 EPS 年增率加速**（從 +5% → +10% → +20%）= 最強選股信號
- 毛利率 ≥ 30% 且維持 or 提升 → 高護城河企業
- 營業利益率提升 → 靠本業賺錢，非業外收益

#### ✅ 龍多股完整篩選框架

```
合約負債 > 股本 50%  ✓
資本支出 > 股本 80%  ✓
近 4 季 EPS 加速成長  ✓
月營收 YoY 加速 (3個月均線上彎)  ✓
→ 龍多股確認，大型法人機構尚未追入前的黃金買點
```
""")

    # ── 策略2（財報體檢）v19.175 補章 ─────────────────────────────
    # 門檻**全部** import 自 shared/financial_health_thresholds.py（§3.3 反捏造），
    # 與 🔬 個股「AI 財報體檢」/ 🏆 個股組合「批次財報體檢」同一份 SSOT。
    with st.expander(_EDU_STRATEGY_TITLES['financial_health'], expanded=True):
        st.markdown(f"""
### 核心邏輯：先確認「這門生意活得下去」，再談會不會漲

{STRATEGY_VALUATION} 看便宜、{STRATEGY_TECHNICAL} 看時機，本策略只問一件事：
**這家公司的財報體質撐不撐得住？** 順序是「存活 → 財務結構 → 償債 → 獲利」，
前一關沒過，後面數字再漂亮都不看。

> 📍 **在系統哪裡看**：🔬 個股 →「AI 財報體檢」區塊（單檔完整版）；
> 🏆 個股組合 →「批次財報體檢」區塊（多檔並排）。
> 以下門檻與那兩處**同一份常數**（`shared/financial_health_thresholds.py`），
> 不會出現說明書寫一套、畫面算另一套。

---

#### 🔑 第一關：存活關（氣長 + 收現 + 現金流自給）

| 指標 | 白話 | 門檻 |
|------|------|------|
| 氣長（現金 ÷ 總資產） | 手上還有多少現金可以撐 | ≥ **{FH_CASH_RATIO_SAFE_PCT:.0f}%** 🟢／{FH_CASH_RATIO_WATCH_PCT:.0f}–{FH_CASH_RATIO_SAFE_PCT:.0f}% 🟡／< {FH_CASH_RATIO_WATCH_PCT:.0f}% 🔴 |
| 收現天數 DSO | 賣出去多久才收到錢 | < **{FH_DSO_FAST_DAYS:.0f} 天** 🟢（天天收現金）／{FH_DSO_FAST_DAYS:.0f}–{FH_DSO_SLOW_DAYS:.0f} 天 🟡／> {FH_DSO_SLOW_DAYS:.0f} 天 🔴 |
| 現金流量比率（OCF ÷ 流動負債） | 本業現金夠不夠還短債 | > **{FH_CASHFLOW_RATIO_MIN_PCT:.0f}%** |
| 現金流量允當比率（5 年 OCF ÷ 5 年 資本支出+存貨增+現金股利） | 擴張與配息是不是自己賺來的 | ≥ **{FH_CASHFLOW_ADEQUACY_MIN_PCT:.0f}%** |
| 現金再投資比率 | 賺的錢有沒有再投回長期資產 | > **{FH_CASH_REINVEST_MIN_PCT:.0f}%** |

**口訣**：現金流量比率 {FH_CASHFLOW_RATIO_MIN_PCT:.0f}％ ×
允當比率 {FH_CASHFLOW_ADEQUACY_MIN_PCT:.0f}％ ×
再投資比率 {FH_CASH_REINVEST_MIN_PCT:.0f}％ → 三個都過＝現金流自給自足。

---

#### 🔑 第二關：財務結構關（借多少 + 借得對不對）

| 指標 | 門檻 | 意義 |
|------|------|------|
| 負債佔資產比率 | < **{FH_DEBT_RATIO_EXCELLENT_PCT:.0f}%** 🟢優秀／< {FH_DEBT_RATIO_PASS_PCT:.0f}% 🟡正常／{FH_DEBT_RATIO_PASS_PCT:.0f}–{FH_DEBT_RATIO_WARN_PCT:.0f}% ⚠️警戒／> {FH_DEBT_RATIO_WARN_PCT:.0f}% 🔴 | 突發性倒閉風險的第一道防線 |
| 以長支長（(股東權益+非流動負債) ÷ 固定資產） | > **{FH_LONG_TERM_FUNDING_MIN_PCT:.0f}%** | < {FH_LONG_TERM_FUNDING_MIN_PCT:.0f}% ＝ 短債長投，景氣一轉就周轉不靈 |

⚠️ **例外**：金融 / 租賃業負債天生高，須以產業旗標豁免，不可直接套用上表。

---

#### 🔑 第三關：償債關（極嚴標準）

| 指標 | 門檻 |
|------|------|
| 流動比率（流動資產 ÷ 流動負債） | > **{FH_CURRENT_RATIO_MIN_PCT:.0f}%** |
| 速動比率（(流動資產−存貨) ÷ 流動負債） | > **{FH_QUICK_RATIO_MIN_PCT:.0f}%** |

沒過不是直接判死，而是進入**交叉驗證**（例如 DSO < {FH_DSO_FAST_DAYS:.0f} 天的收現型行業可豁免）。

---

#### 🔑 第四關：獲利關（三率三升 + 槓桿防呆）

| 指標 | 門檻 | 意義 |
|------|------|------|
| 營業毛利率 | ≥ **{FH_GROSS_MARGIN_GOOD_PCT:.0f}%** | 高毛利才有護城河 |
| 營業利益率 | > **{FH_OPERATING_MARGIN_EXCELLENT_PCT:.0f}%** | < 0% ＝ 本業虧損，直接淘汰 |
| 經營安全邊際（營益 ÷ 毛利） | ≥ **{FH_MOS_STRONG_PCT:.0f}%** | 毛利衰退 {100 - FH_MOS_STRONG_PCT:.0f}% 本業仍不虧 |
| 稅後淨利率 | > **{FH_NET_MARGIN_PASS_PCT:.0f}%** | 最後真正落袋的比例 |
| ROE | > **{FH_ROE_TOP_PCT:.0f}%** 頂標 | 但要看是「本業賺」還是「借來的」 |
| 杜邦槓桿防呆 | ROE > {FH_ROE_LEVERAGE_CHECK_PCT:.0f}% 且 負債比 > **{FH_DUPONT_LEVERAGE_DEBT_PCT:.0f}%** → 🚨 | 高 ROE 若來自高槓桿＝假優等生 |

---

#### 🔑 綜合診斷：經營能力與盈餘品質

| 指標 | 門檻 | 白話 |
|------|------|------|
| 總資產翻桌率（營收 ÷ 總資產） | > **{FH_ASSET_TURNOVER_MIN:.1f} 趟** | 同一份資產一年做幾趟生意 |
| 盈餘品質（OCF ÷ 稅後淨利） | ≥ **{FH_EARNINGS_QUALITY_MIN_PCT:.0f}%** | < {FH_EARNINGS_QUALITY_MIN_PCT:.0f}% ＝ 帳上有賺、現金沒進來（紙上富貴） |

> **{STRATEGY_FINANCIAL} 心法**：「先看會不會倒，再看賺不賺錢。
> 帳上獲利是意見，現金流才是事實。」
""")

    # ── 策略3 章節 1/3：型態學 — v19.174 去識別化；v19.175 標題改吃 SSOT ──
    # （章節主題寫在破折號後；括號範疇一律由 strategy_label() 產出，勿在此重寫）
    with st.expander(_EDU_STRATEGY_TITLES['pattern'], expanded=True):
        st.markdown(r"""
### 核心邏輯：用「型態」讀懂主力換手完畢的訊號

本策略認為，K線型態是「資金博弈的足跡」。主力洗盤完畢後，往往留下可辨識的底部型態。

> 📍 **在系統哪裡看**：🔬 個股 / 🏆 個股組合 的「型態目標價」區塊
> （`compute/strategy/pattern_targets.py`）。
> ⚠️ 該模組**只判三種型態**：`破底翻` / `N字整理` / `型態未明`。
> 以下「頭肩底」一節屬**通用型態學教材**，系統**沒有**頭肩底偵測器 ——
> 別在畫面上找它，找不到不是你的問題。

---

#### 🔑 型態一：破底翻（Fake Breakdown Reversal）

> 股價跌破前低 → 但**又站回**前低之上 → 散戶停損被洗出後主力拉抬

**系統實際判定式**（`pattern_targets.derive_pattern_levels`，純價格、不看量）：

```
破底翻 = (最低擺動低 < 前低/支撐)  AND  (現價 > 前低/支撐)
```

| 教材上的加分條件 | 系統有沒有在判 |
|------|---------|
| ① 量縮跌破前低（散戶恐慌賣壓，非主力出貨） | ❌ 不判，要自己看圖 |
| ② 大量紅K收盤站回前低之上 | ❌ 不判，要自己看圖 |
| ③ 連續 2 根紅K，第 2 根突破近期高點 | ❌ 不判，要自己看圖 |

> ⚠️ 舊版本章把上面三條寫成「判斷標準」，讀起來像系統在檢查它們 —— 並沒有。
> 系統給的是**價格關鍵位**（頸線 / 止損 / 等幅目標），量價確認由你自己補。

**停損設定**：系統取 `破底低 × (1 − buffer)`；教材口訣「跌破破底翻 K 棒低點即出場」同義。

---

#### 🔑 型態二：頭肩底（Inverse Head & Shoulders）— ⚠️ 通用教材，系統未實作

```
         左肩          右肩
          /\            /\
         /  \    頭    /  \
        /    \  /  \  /    \
───────/──────\/────\/──────────  ← 頸線（Neckline）
                底部（最低點）
```

| 要素 | 判斷標準 |
|------|---------|
| 左肩 | 下跌後反彈，成交量萎縮 |
| 頭部 | 跌破左肩低點，量更小（洗盤） |
| 右肩 | 反彈至接近左肩高點，**量比頭部大** |
| 突破頸線 | 收盤站上頸線 + 成交量爆增 ≥ 均量 1.5 倍 → 買點 |

---

#### 🔑 操作細節：頸線突破買點

1. **等收盤確認**：不追日內突破，等收盤穩站頸線之上
2. **拉回不破**：突破後若拉回測試頸線不跌破 → 加碼機會
   （這裡的「回測」是**價格回來測試頸線**，不是歷史績效模擬的那個回測）
3. **目標價**：頸線 + 型態高度（等幅量測）
4. **停損**：跌破型態低點即出場

> 系統的等幅量測用的是：`target = 頸線 + (第一波高 − 箱底)`、
> `target2 = 頸線 + 2 ×(同一段幅)`（`pattern_targets.compute_pattern_targets`）。
""")

    # ── 策略3 章節 2/3：VCP 波幅收縮 — v19.174 去識別化；v19.175 標題吃 SSOT ──
    with st.expander(_EDU_STRATEGY_TITLES['vcp'], expanded=True):
        st.markdown(rf"""
### 核心邏輯：波幅每次比上次小 → 籌碼鎖定完成 → 等爆量突破

VCP（Volatility Contraction Pattern）找的是「橫盤整理中能量不斷蓄積」的股票，
波幅每次比前次更小，量能不斷萎縮，直到爆量突破才確認方向。

---

#### 🔑 VCP 四大關鍵條件（通用教材版）

| 條件 | 標準 | 說明 |
|------|------|------|
| ① **多次波幅收縮** | ≥ 3 次 | 每次高低振幅比前次縮小 |
| ② **整理期間量能萎縮** | 量能遞減 | 籌碼鎖定，浮額洗盡 |
| ③ **不跌破關鍵均線** | 站上均線 | 型態不能在均線下方整理 |
| ④ **突破需有爆量** | 突破日放量 | 收盤突破整理高點 + 巨量 = 有效突破 |

---

#### 🔑 本系統實際判定式（與上表**不完全一樣**，看畫面請以這裡為準）

> ⚠️ **v19.181 更正**：舊版把 ②寫成「量比 < 0.8」、③寫成「站上 MA20」、
> ④寫成「量比 ≥ 2.0」。這三個數字**都不是**系統在用的值 ——
> `0.8` 在程式裡是 **ATR 波動收縮比**（`VCP_ATR_CONTRACTION_RATIO`），
> 跟成交量無關；量比 2.0 全站不存在。實際有兩支不同的實作：

**個股（`scoring_engine.check_vcp_atr_filter`）** — 只有一條，純波動：
```
VCP 收縮確認 = ATR5 < ATR20 × {VCP_ATR_CONTRACTION_RATIO:g}   (SSOT: VCP_ATR_CONTRACTION_RATIO)
資料 < 25 根 → 回「資料不足」，不硬判
```

**ETF（`etf_calc.check_vcp_signal`）** — 四條全成立才亮訊號：
```
① 收盤 > MA50            ② 收盤 > MA200
③ 近 2 週均振幅 < 前 2 週均振幅 × 0.6      ← 波幅收縮
④ 當日量 > 50 日均量                       ← **放量**，不是萎縮
資料 < 210 個交易日 (ETF_VCP_MIN_DAYS) → 不判
```

> 📌 兩點特別容易看錯：
> (a) 用的是 **MA50 / MA200**，不是教材講的 MA20；
> (b) ④是「**放量**才算數」——「量能萎縮」講的是**整理期間**，
> 突破當下反而要**放量**。舊版把兩個階段的量能寫成同一條，方向剛好相反。

---

#### 🔑 VCP 示意圖

```
價格
│    /\        /\      /\
│   /  \      /  \    /  \  ← 波幅一次比一次小
│  /    \    /    \  /    \___________  突破!▲▲▲ (爆量)
│ /      \  /      \/
│/        \/
└─────────────────────────────── 時間
        收縮①  收縮②  收縮③   Pivot Point(突破點)
```

---

#### 🔑 進出場規則

| 動作 | 標準 |
|------|------|
| **進場** | 突破 Pivot Point（整理高點）+ 當日收盤接近最高 |
| **加碼** | 突破後拉回測試 Pivot 不破，再加碼 |
| **停損** | 跌破進場 K 棒低點；系統預設固定停損 **−{STOP_LOSS_DEFAULT_PCT:.0f}%**（`STOP_LOSS_DEFAULT_PCT`），ATR 模式為 `Entry − {ATR_STOP_MULTIPLIER:g}×ATR14` |
| **停利** | 系統的盈虧比通過門檻是 **≥ {RR_MIN:g}**（`RR_MIN`，低於此不顯示），預設目標漲幅 **+{RR_DEFAULT_TARGET_GAIN * 100:.0f}%**（`RR_DEFAULT_TARGET_GAIN`） |

> ⚠️ **v19.181 更正**：舊版手寫的盈虧比目標比系統實際門檻（{RR_MIN:g}）高，
> 停損寫成一個區間、加碼倍數也是全站不存在的規則。
> 上表數字現已全部改由 `shared/signal_thresholds.py` 常數代入。

> **{STRATEGY_TECHNICAL} 心法**：「量縮到極點就是爆發前夕。等的不是上漲，等的是籌碼。」
""")

    # ── 策略3 章節 3/3：資金動能 — v19.174 去識別化；v19.175 標題改吃 SSOT ──
    # B6-a v19.181:本章的廣度門檻改走 §§TOKEN§§ → `_resolve_edu_tokens`（SSOT），
    # 不再手寫 60 / 40（`BREADTH_BULL_PCT` / `BREADTH_NEUTRAL_PCT`）。
    with st.expander(_EDU_STRATEGY_TITLES['liquidity'], expanded=True):
        st.markdown(_resolve_edu_tokens("""
### 核心邏輯：用「總體資金」判斷大盤體質，而非個股

本策略認為，股票市場是資金推動的遊戲。M1B-M2 利差是最領先的資金指標，
比任何技術指標都早 6–9 個月看到轉折。

---

#### 🔑 指標一：M1B – M2 利差（資金寬鬆度）

> **白話**：M1B 是活錢（活存），M2 是定存 + 活存。
> 活錢比例上升 → 錢從定存搬出來 → 準備進股市

*（教學示意，實際持股以 🎚️ 建議持股油門為準）*

| 利差 | 訊號 | 建議倉位 |
|------|------|---------|
| M1B YoY **> M2 YoY** 且擴大 | 🟢 資金寬鬆，多頭啟動 | **持股 70–100%** |
| M1B YoY **= M2 YoY**（利差收斂） | 🟡 轉折警戒，注意方向 | **持股 50%** |
| M1B YoY **< M2 YoY**（利差翻負） | 🔴 資金緊縮，熊市風險 | **持股 0–30%** |

---

#### 🔑 指標二：市場廣度（本系統用「旌旗指數」）

> ⚠️ **本系統沒有「站上年線家數比」這個數據**（§1 反捏造）。
> 原教材這一段寫的是「台股 1800 支股票中有幾支站在年線之上」，
> 但全站**沒有任何一行程式在算它**，畫面上也找不到這個數字 ——
> 照著找只會白費力氣，故改為說明系統**實際**提供的廣度指標。

> **本系統實際算的**：**旌旗指數 ＝ 上漲佔比的 5 日移動平均**
> （上漲佔比 ＝ 上漲家數 ÷（上漲家數＋下跌家數）× 100；再取 5 日均）。
> 它衡量的是「最近一週有多少比例的股票在漲」，同樣屬於**市場廣度**家族，
> 但**不是**均線類指標。位置：🌍 總經 → 🧩 籌碼桶「旌旗指數」。

| 旌旗指數 | 市場意義 |
|---------|---------|
| ≥ **§§BREADTH_BULL§§%** | 🟢 多頭格局強健，可積極持股 |
| **§§BREADTH_NEUTRAL§§–§§BREADTH_BULL§§%** | 🟡 多空拉鋸，選股不選市 |
| < **§§BREADTH_NEUTRAL§§%** | 🔴 熊市格局，嚴控倉位 |

（門檻 SSOT：`BREADTH_BULL_PCT` / `BREADTH_NEUTRAL_PCT`，由常數即時代入；
判定用 `>=`，所以恰好等於門檻時算**上面那一格**。）

搭配「大盤 vs 個股」強弱：
- 指數創高但廣度不創高 → 警訊（領頭羊撐盤，底層崩潰）
- 廣度先反彈 → 領先大盤底部的信號

---

#### 🔑 指標三：外資期貨空單防守線

*（教學示意，實際持股以 🎚️ 建議持股油門為準；系統真正的期貨門檻見下方）*

| 外資期貨淨部位 | 訊號 | 操作建議 |
|--------------|------|---------|
| 淨**多單** > 0 且擴大 | 🟢 外資看多台股 | 可積極作多 |
| 淨多單縮減中 | 🟡 外資降低多頭暴露 | 適度降低倉位 |
| 淨**空單** > 0 | 🔴 外資對沖台股風險 | 大盤需謹慎 |
| 淨空單急速擴大 | 🚨 系統性風險信號 | 大幅降低曝險 |

> 📌 **系統實際門檻**（SSOT，非教材示意）：v4 引擎風險燈
> 🟡 期貨淨部位 < §§FUT_V4_YELLOW_LOTS§§ 口 ／ 🔴 < §§FUT_V4_RED_LOTS§§ 口；
> 紅綠燈「空頭防禦」旗標另用 |淨部位| > §§FUT_DEFENSE_LOTS§§ 口（且市場分數 < 2）。
> 三者用途不同、刻意不統一，詳見「📐 外資籌碼」章。

---

#### ✅ 完整多空判斷矩陣

*（教學示意，實際持股以 🎚️ 建議持股油門為準）*

| M1B-M2 | 旌旗指數（廣度） | 外資期貨 | 建議倉位 |
|--------|---------|---------|---------|
| ✅ 寬鬆 | ✅ ≥§§BREADTH_BULL§§% | ✅ 多單 | **滿倉 80–100%** |
| ✅ 寬鬆 | ✅ ≥§§BREADTH_BULL§§% | ❌ 空單 | **七成 70%** |
| ✅ 寬鬆 | ❌ <§§BREADTH_NEUTRAL§§% | 任何 | **五成 50%，選股不選市** |
| ❌ 緊縮 | 任何 | 任何 | **防守 0–30%，保留現金** |

> **記憶口訣**：「M1B-M2 翻正是起跑槍，廣度過半是加速器，外資空單是急剎車。」

---

#### 📌 股匯四象限快查表（連動操作）

*（教學示意，實際持股以 🎚️ 建議持股油門為準）*

| 象限 | 台股 | 台幣 | 外資行為 | 持股建議 |
|------|------|------|---------|---------|
| 🟢 股匯雙漲 | ↑ | 升值 | 匯入真實資金 | **80–100%** |
| ⚠️ 股漲匯貶 | ↑ | 貶值 | 疑似拉高出貨 | **50%，不追高** |
| 🔴 股匯雙殺 | ↓ | 貶值 | 大舉提款撤出 | **0–30%，嚴格防守** |
| 🟡 股跌匯升 | ↓ | 升值 | 資金停泊台灣 | **50–70%，找錯殺股** |
"""))

    # ── v18.281 原理教室(從 macro_classroom 移入,合併成單一說明書)──
    render_principle_classroom()

    st.markdown("""---
<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;
padding:10px 14px;font-size:11px;color:#8b949e;margin-top:8px;text-align:center;">
⚠️ 本教學整理自公開教學資源，僅供學術研究與教育用途。<br>
投資涉及風險，任何操作均應自行判斷，盈虧自負。本系統非投資顧問，不構成買賣建議。
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# v18.281 — 總經原理教室(從 macro_classroom.py 移入,合併成單一說明書)
# 內容已對權威來源查證(CIER/國發會/TWSE/FRED/ISM/CBOE,見 v18.279)
# ════════════════════════════════════════════════════════════════
_PRINCIPLE_CHAPTERS: list[tuple[str, str]] = [
    (
        "🌀 景氣循環四階段(復甦 → 擴張 → 高峰 → 衰退)",
        """
經濟不是直線成長,而是循環:**復甦 → 擴張 → 高峰 → 衰退**,平均一個完整循環約 5-10 年。

- **復甦**:谷底翻揚,失業率高但 PMI 反轉、央行寬鬆,股市最佳買點
- **擴張**:GDP 穩步成長,通膨溫和,股市持續上行
- **高峰**:景氣過熱,通膨升溫迫使央行升息,股市見頂
- **衰退**:企業獲利衰退,失業率上升,股市熊市

**TW 在地補充**:台股景氣高度同步美股(R² ≈ 0.7),但加掛「外資資金流」因子 —
外資撤退時即使美股漲,台股也可能 K 線轉弱。判讀位階時要兩面看。

📐 **數學定義(NBER 衰退判定 / TW 國發會景氣燈號)**

**NBER 美國版**:無單一公式,看 6 大月度指標(實質個人所得 / 非農就業 / 個人消費 /
製造批發銷售 / 家戶就業 / 工業生產)。GDP 連 ≥ 2 季 QoQ < 0 → 技術性衰退。

**TW 國發會景氣燈號**:綜合 9 項指標(M1B / 股價 / 工業生產 / 海關出口 / 機械設備 /
製造業銷售值 / 批發零售餐飲 / 非農就業 / PMI)→ 紅(熱絡)/ 黃紅(轉熱)/ 綠(穩定)/
黃藍(轉弱)/ 藍(低迷)5 燈號。

📜 **歷史案例(TWII 反應)**

| 年份 | 全球事件 | TWII 高點→低點 | 持續 | 國發會燈號 |
|---|---|---|---|---|
| 2000-2001 | dot-com + 911 | 10393 → 3411(-67%) | 19 月 | 連 **15** 月藍燈(2000/12–2002/2,**史上最長**) |
| 2008 | 金融海嘯 | 9859 → 3955(-60%) | 12 月 | 連 **9** 月藍燈(2008/9–2009/5,史上第三長) |
| 2015 | 中國股災 | 10014 → 7203(-28%) | 7 月 | 景氣低迷黃藍燈為主 |
| **2020** | **COVID-19** | **12197 → 8523(-30%)** | **2 月**(史上最短) | 黃藍 → 紅燈 |
| 2022 | Fed 升息 | 18619 → 12629(-32%) | 10 月 | 紅 → 黃藍 |

> 國發會藍燈紀錄排名:① 網路泡沫 15 月(2000/12–2002/2)> ② 歐債 10 月(2011/11–2012/8)> ③ 金融海嘯 9 月(2008/9–2009/5)。
        """.strip(),
    ),
    (
        "📊 PMI 為何 50 是分水嶺?",
        """
PMI(Purchasing Managers Index, 採購經理人指數)向採購經理調查 5 個面向(新訂單 / 生產 /
雇用 / 供應商交貨 / 存貨)。每面向「比上月好/差/持平」三選一,再合成擴散指數(diffusion index)。

- PMI > 50:**多數企業比上月好** → 經濟擴張
- PMI < 50:**多數企業比上月差** → 經濟收縮
- PMI = 50:**好壞均衡** → 經濟停滯

**領先性**:PMI 領先實質 GDP / 工業生產 約 1-3 個月,因為採購決定先於生產。

**TW 在地來源**:本系統按優先序賽跑 **§§PMI_SOURCE_COUNT§§ 個源**
(§§PMI_SOURCES§§),取**第一個命中**即停,**禁止平均**(混合不同方法論 = 雜訊)。
順序 SSOT:`macro_core.PMI_SOURCE_REGISTRY`(上面這串名單由該 registry 即時產生,
不是手打的,所以拔源 / 加源時這段會自動跟著改)。
台灣官方製造業 PMI 由中華經濟研究院(CIER)**2012/7 才創編**,故 2008-09 金融海嘯**無台灣官方 PMI**,僅能參照美國 ISM。

📐 **數學定義**

```
單一面向擴散指數 = (回答「好」的%) + 0.5 × (回答「持平」的%)      → 落 0~100

  等價寫法:50 + (好% − 差%) ÷ 2
  ⚠️ 常見誤寫:「好% − 差% + 50」——  少除以 2,好60/持平20/差20 會算成 90(真值 70)

PMI = 5 個面向擴散指數的**等權**平均(各 20%)
```

**⚠️ 權重的歷史沿革**:ISM 曾用 30/25/20/15/10 的加權(新訂單最重),
但**自 2008 年 1 月起已改為 5 項等權(各 20%)**;台灣中經院 PMI 建置時即採等權版本。
若你在舊教材看到 30% 新訂單那組數字,那是 2008 年前的舊制。

**注意**:本系統**不自行計算 PMI**,只抓各來源**已公布**的 PMI 數值。
上面的定義是給你看懂這個數字怎麼來的,不是系統內的運算式。

📜 **歷史案例(製造業 PMI vs TWII)**

| 月份 | 美 ISM | 台灣 PMI(中經院)| TWII 同期 | 市場狀態 |
|---|---|---|---|---|
| 2008/12 | 32.4(26 年新低)| —(2012/7 才創編)| 4591(底部區) | 後 12 月 +78%(8188)|
| 2009/3 | 36.3(反轉)| — | 5210 | 復甦起點 |
| 2020/4 | 41.5 | 47.6 | 9978 | 後 6 月 +26%(12552 / 2020/10)|
| **2022/12** | **48.4** | **43.7** | 14138 | 谷底區 |
| 2024/9 | 47.2 | 49.2(緊縮)| 22260 | 與景氣脫鉤(指數創高)|

> ⚠️ 台灣官方 PMI(中經院 CIER)2012/7 才創編,2008-09 兩列僅有美國 ISM;先前誤填的 2008-09 台灣 PMI 為不存在數據,已移除(§1 反捏造)。
        """.strip(),
    ),
    (
        "🚨 薩姆規則(Sahm Rule)— 衰退鎖定指標",
        """
2019 年聯準會經濟學家 **Claudia Sahm** 提出:
**美國失業率 3 個月滾動平均** - **過去 12 個月最低點** ≥ 0.5 百分點 → 衰退鎖定。

歷史回測:**1949 年以來 100% 命中**(11 次衰退全部觸發,無假警報)。

**為何 0.5?** 失業率單月雜訊大,**3M 平均**過濾噪音;**12M 低點**抓「動能轉折」;
0.5pp 是統計顯著閾值。

**啟示**:薩姆觸發 = 衰退**已開始**,不是預警 → 立刻降低風險。
台股無法忽視美股拖累,薩姆觸發後 TW 大盤平均 6 個月回檔 -15%。

📐 **數學定義**

```
Sahm = MA(美失業率, 3M) - min(美失業率[-12M : now])

if Sahm ≥ 0.5 → 衰退鎖定
```

**為何用 3M 平均?** 月度勞動數據雜訊 ±0.1-0.2pp,3M 滑動平均降噪 √3 倍。
**為何用 12M 低點?** 抓「最近一次景氣谷底後升的幅度」,直接捕捉動能反轉。

📜 **歷史案例(衰退起點後 TWII 反應)**

| 美衰退起點(NBER) | 約略 Sahm | 後 6 月 TWII | 後 12 月 TWII |
|---|---|---|---|
| 1990/7 | 0.5 | -57%(海灣戰爭崩盤)| -38% |
| 2001/3 | 0.6 | -32% | -7% |
| **2008/2** | **0.5** | **-22%** | **-46%** |
| 2020/4 | 2.4(史上最高)| +30%(QE 異常) | +57% |
| 2024/8 | 0.5 | +5%(進行中) | TBD |

> ⚠️ 表中日期為 **NBER 衰退起始月**。薩姆規則屬即時指標,實際跨 0.5 觸發點通常**落在衰退起點後 0-3 月**(2020/4、2024/8 為薩姆實際觸發月,其餘為衰退起點對照)。

**規則**:衰退起點後 TWII 平均 6 月回檔 -15%(2020 為政策例外)。
        """.strip(),
    ),
    (
        "📉 殖利率曲線倒掛 — 50 年最準衰退預警",
        """
正常:**長天期公債殖利率 > 短天期**(借錢越久利率越高,合理)。
**倒掛**:10 年期 < 2 年期 / 3 個月,即 10Y-2Y 或 10Y-3M < 0。

**為何能預測衰退?** 倒掛代表市場預期:
- **未來會降息**(經濟轉壞 → Fed 降息 → 長債殖利率先下)
- **企業借短貸長利潤萎縮** → 銀行不願放貸 → 信用收縮
- **投資人爭搶長債避險** → 長債價格上漲、殖利率下跌

**歷史**:1969 以來每次衰退前 10Y-3M 都倒掛,**平均提前 12 個月**(6-24 範圍)。
**台股應對**:倒掛後 12 個月內,TW 50 通常先見頂、後修正,可降低個股 β 暴露。

📐 **數學定義**

```
Spread_10Y2Y = Yield_10Y - Yield_2Y
Spread_10Y3M = Yield_10Y - Yield_3M

if Spread < 0 → 倒掛
if Spread < 0 持續 ≥ 3 月 → 高機率衰退
```

**本系統的 logistic 衰退機率(`macro_core.recession_probability`)**:
```
logit = §§RECESSION_COEF_SPREAD§§ × Spread_10Y3M + (§§RECESSION_COEF_INTERCEPT§§)
P(recession) = 1 / (1 + exp(−logit)) × 100%
```
係數 SSOT:`shared/signal_thresholds.RECESSION_LOGIT_COEF_SPREAD / _INTERCEPT`
(上面的數字由該常數即時代入,不是手打)。代幾個值感受一下:
Spread = 0% → P ≈ **§§RECESSION_P_AT_0§§%**;
Spread = −1% → P ≈ **§§RECESSION_P_AT_M1§§%**;
Spread = −2% → P ≈ **§§RECESSION_P_AT_M2§§%**。

> ⚠️ 這組係數是本系統自用的簡化式(輸入為**當期**利差),**不是** Fed NY 官方
> 那條「12 個月移動平均利差」模型 —— 兩者係數與輸入都不同,數字不可互相對照。
> 本段舊版手寫了另一組係數與對照百分比,既不符實作、算術上也跟它自己的式子
> 對不起來;v19.181 起全數改由 SSOT 常數即時代入,不再手打。

📜 **歷史案例(倒掛 → TWII 反應)**

| 倒掛日 | 倒掛深度 | 美衰退起點 | 提前期 | TWII 高峰→谷底 |
|---|---|---|---|---|
| 2000/2 | -0.5% | 2001/3 | 13 月 | 10393 → 3411(-67%) |
| 2006/7 | -0.2% | 2007/12 | 17 月 | 9859 → 3955(-60%) |
| 2019/3* | -0.3% | 2020/2 | 11 月 | 12197 → 8523(-30%) |
| **2022/7** | **-1.08%**(2023/7,**1981 年來最深**) | TBD | 已 24+ 月 | 進行中(2024/7 24416 是否頂?)|

> *2019/3 先倒掛的是 10Y-3M;10Y-2Y 主倒掛在 2019/8。
> 倒掛深度:-1.08%(2023/7/3)是 **1981 年來最深**;真史上最深為 1980-81 Volcker 期(< -2%)。

**2022 異常**:1981 年來最深倒掛但衰退遲未到,可能 AI 資本支出 + 寬鬆財政對沖。
        """.strip(),
    ),
    (
        "📐 外資籌碼 — TW 股市定價最重要的單一指標",
        """
TW 股市外資持股比 ~40%(2024 年),日均成交量占比 25-30%,**外資動向是定價核心**。

本系統三大外資觀察:
- **外資現貨買賣超**:當日 net buy/sell(億 TWD)。單日數字系統**不設門檻**,
  真正會亮燈的是**5 日累積** ≤ §§FOREIGN_5D_YI§§ 億(見下方③)
- **外資期貨淨部位**:多空淨未平倉(口數)。系統有**兩組**門檻:
  防禦旗標用 |淨部位| > §§FUT_DEFENSE_LOTS§§ 口、v4 風險燈用
  §§FUT_V4_YELLOW_LOTS§§ / §§FUT_V4_RED_LOTS§§ 口(見下方①②)
- **三大法人**:外資 + 投信 + 自營商合計動向

**外資撤退的早期訊號**(觀念,非系統判定式):
1. 連續多個交易日淨賣超,且 5 日累積達警戒量級
2. 期貨大空單建立 + 現貨同時賣超
3. 押注大跌:put/call 比飆高

📐 **數學定義(系統實際 logic)**

> ⚠️ **v19.181 更正**:本段舊版寫「期貨 net < −50000 AND TWII < MA240 → 防禦模式」,
> 以及「30000 口對應 ~6 億 TWD、歷史回測 6 月 −8%」—— **全站沒有任何一行程式**
> 跑那條 −50000 + 年線的規則,那組回測數字也沒有任何出處(§1 反捏造)。
> 下面是三條**真的存在**的判定,門檻一律由 SSOT 常數即時代入。

```
外資現貨買賣超 (億 TWD) = TWSE 三大法人表「外資及陸資」買進 − 賣出
外資期貨淨部位 (口)      = TAIFEX「外資」TX 期貨未平倉淨額(多 − 空)

① 紅綠燈「空頭防禦」旗標  (macro_helpers.calc_traffic_light)
   市場分數 < 2  AND  |期貨淨部位| > §§FUT_DEFENSE_LOTS§§ 口  AND  期貨淨部位 < 0
   ※ 期貨資料**沒抓到**時既不觸發也不抑制 —— 缺資料 ≠ 沒有大空單

② v4 引擎風險燈  (v4_strategy_engine.macro_risk_signal)
   🔴 VIX > §§VIX_V4_RED§§    或  期貨淨部位 < §§FUT_V4_RED_LOTS§§ 口
   🟡 VIX > §§VIX_V4_YELLOW§§ 或  期貨淨部位 < §§FUT_V4_YELLOW_LOTS§§ 口

③ 外資現貨賣超紅旗  (macro_signal_lookback_tw.DEFAULT_TW_SIGNALS)
   外資 5 日累積買賣超 ≤ §§FOREIGN_5D_YI§§ 億  (搭配 TWII 20 日跌幅 ≤ §§TWII_20D_PCT§§% 同時亮)
```

**為什麼同一個「外資期貨」有三個不同門檻?** 因為它們**用途不同**:①是健康評分裡的
單一防禦觸發、②是分級紅黃燈、③看的是現貨不是期貨。刻意各自具名、**不合併**
(合併 = 行為變更);細節見 `shared/signal_thresholds.py` 各常數 docstring。

📜 **歷史案例**

| 期間 | 外資累計淨賣 | TWII 反應 | 觸發強度 |
|---|---|---|---|
| 2008 全年 | 約 -4,600 億 + 期空 -8 萬口 | 8506 → 4591(全年 -46%)| 極端 |
| 2015/8 中國股災 | 8 月單月大賣(全年實為**淨買超 +422 億**)| 10014 → 7203(-28%)| 強 |
| 2020/3 COVID | -3100 億(1 月內) | 12197 → 8523(-30%)| 極端 |
| **2022 Fed 升息** | **-1.23 兆**(全年!) | **18619 → 12629(-32%)** | **史上最大單年** |
| 2024/8 套利平倉 | 約 -2,800 億(3 日) | 24416 → 19830(8/5 收盤,-19%)| 快速 |

> 金額為概略量級,精確值以 TWSE 三大法人統計為準。**注意 2015 全年外資是淨買超**(+422 億),僅 8 月股災單月賣超,勿與全年混淆。
        """.strip(),
    ),
    (
        "💸 散戶情緒反指標 — 融資餘額 × 韭菜指數(兩個不同的量,別搞混)",
        """
> ⚠️ **v19.181 更正 —— 先講清楚,不然你會對著畫面看不懂**
> 本系統裡有**兩個都叫「韭菜指數」但單位完全不同**的東西
> (定名 SSOT:`src/config/config.py`「韭菜指數門檻 SSOT」)。
> 本章舊版只講了 (A),但**畫面上實際顯示的是 (B)** ——
> 讀者拿 (A) 的門檻去看 (B) 的數字,必然誤判。

| | (A) 融資 5Y 標準化指數 | (B) 小台法人空多比 ← **畫面顯示的是這個** |
|---|---|---|
| 值域 | 0 ~ 100,中位 **50** | 約 −100 ~ +100,中位 **0** |
| 定義 | (融資餘額 − μ_5Y) ÷ σ_5Y 標準化後映到 0-100 | (法人空方 MTX 未平倉 − 法人多方 MTX 未平倉) ÷ 小台全體未平倉 × 100 |
| 系統有沒有在算 | ❌ **沒有**。全 repo 無任何一行程式產生此數列(無融資 Z-score fetcher),門檻 `LEEK_HIGH/LOW_THRESHOLD` 目前 **0 consumer** | ✅ 有,`leading_indicators.py` 每日產出 |
| 正負讀法 | 越高 = 散戶越樂觀 | **正值** = 散戶被迫站多方(危險);**負值** = 散戶淨空(機會) |

**(B) 的實際門檻**(`config.LEEK_ALERT_*`,由 SSOT 即時代入):
法人空多比 > **§§LEEK_ALERT_HIGH§§%** → 🔴 散戶過度樂觀(頂部訊號);
< **§§LEEK_ALERT_LOW§§%** → 🟢 軋空動能極強(機會)。
另有兩組較敏感的門檻(籌碼綜合評分 / 拐點偵測)用途不同、刻意不統一,見 config 該段。

---

**融資餘額**(億 TWD)本身是**另一個獨立指標**,系統確實有抓,門檻也真的在用:
> **🟡 警戒 > §§MARGIN_WARN_YI§§ 億** ／ **🔴 過熱 > §§MARGIN_OVERHEAT_YI§§ 億**
> (SSOT:`MARGIN_BALANCE_WARN_THRESHOLD_YI` / `MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI`)

**為何是反指標?** 散戶資訊不對稱、追高殺低 → 集體借錢買進時往往接近頂、
集體斷頭時接近底。用法是「逆向確認」:多頭訊號 + 散戶不熱 = 高勝率;
多頭訊號 + 融資飆高 = 警覺。

📐 **數學定義**

```
融資餘額 = TWSE + TPEX 每日融資餘額總和(億 TWD)   ← 系統實際使用,絕對金額比門檻

法人空多比(畫面「韭菜指數」)
  = (法人空方 MTX 未平倉 − 法人多方 MTX 未平倉) ÷ 小台全體未平倉 × 100   (%)

── 以下僅為「教材概念」,系統目前未實作 ──────────────────
標準化情緒指數 = ((融資 − μ_5Y) ÷ σ_5Y + 2) ÷ 4 × 100,clip 到 [0, 100]
  對應 Z:100 → Z ≈ +2(極端樂觀) / 50 → Z ≈ 0 / 0 → Z ≈ −2(極端悲觀)
  想法:融資結構隨市場規模變化,絕對金額跨年代不可比,標準化才有意義。
  ⚠️ 下表的歷史「韭菜值」是這個**未實作**指標的回推示意,
     **不可**拿去對照畫面上那個 ±% 的法人空多比。
```

📜 **歷史案例(融資頂峰 vs TWII 修正)**

| 融資高峰日 | 融資餘額 | 標準化指數(未實作,示意)| TWII | 後 12 月 TWII |
|---|---|---|---|---|
| 2000/4(融資天花板)| **5,956 億**(史上最高)| 48 | 9855 | -50% |
| 2007/10(海嘯前) | 約 3,200 億 | 42 | 9809 | -60% |
| 2018/1 | 1,840 億 | 38 | 11103 | -16% |
| **2021/11** | 約 2,540 億 | 45 | 17840 | **-29%** |
| 2024/7 | 約 2,500 億 | 35 | 24416 | 警戒中 |

> 註 1:「標準化指數」欄是上面那個**系統未實作**的 (A) 指標之回推示意,
> 放在這裡只為說明「絕對金額」與「相對位階」會給出不同結論 ——
> **不要**拿它去對照畫面上的法人空多比(±%),兩者尺度不同。
> 註 2:融資**絕對**金額史上最高在 2000/4(5,956 億);2021 這輪絕對峰在 4 月
> (約 2,600 億),11 月是相對位階的高點。
> 註 3:對照現行門檻 —— 2021/11 與 2024/7 的約 2,5xx 億都已越過
> §§MARGIN_WARN_YI§§ 億黃線,但未達 §§MARGIN_OVERHEAT_YI§§ 億紅線。

**底部反例**:2009/3 融資極度萎縮(標準化位階 ≈ 8)→ TWII 後 12 月 +97%。
極端低位 = 散戶絕望 = 反向買點。
        """.strip(),
    ),
    (
        "😱 VIX 30 — 恐慌指數歷史標竿",
        """
**VIX**:CBOE 用 SPX 選擇權隱含波動率計算的「市場預期未來 30 天波動」。

- VIX < 15:**極平靜**(常見牛市末期,警覺自滿)
- VIX 15-20:**正常**
- VIX 20-30:**警戒**(出現賣壓)
- VIX ≥ 30:**恐慌**(2008/2020/2018Q4 都觸發)
- VIX ≥ 40:**極度恐慌**,歷史上多為**最佳逆向買點**

**TW 對應**:無等價 TW VIX(TAIFEX 有 VIX 指數但流動性低)。本系統用美股 VIX
作為「全球風險偏好」proxy:VIX 飆 → 外資撤新興市場 → 台股賣壓。

📐 **數學定義**

```
VIX² = (2/T) Σ [(ΔK_i / K_i²) × e^(rT) × Q(K_i)] - (1/T) × (F/K_0 - 1)²

化簡:VIX = SPX 30 天 ATM 選擇權隱含 σ × 100

T   = 30 天 / 365
K_i = 第 i 個 OTM 履約價
Q   = 該選擇權買賣中價
```

**標準差換算**:VIX 30 = 年化 σ 30% → 1 月 σ = 30/√12 ≈ 8.7%
所以 VIX 30 = 「68% 機率 SPX 1 月內變動 ±8.7%」。

📜 **歷史案例(VIX 高峰 vs TWII 反應)**

| 日期 | VIX 峰值 | 觸發事件 | TWII 同期(% 變化) |
|---|---|---|---|
| 2008/10/24 | **89.5**(盤中史上最高;收盤 79)| 雷曼倒閉 | -34%(4 月內) |
| 2010/5 | 46(5/20 餘波) | Flash Crash | -8%(快速恢復) |
| 2018/2/5 | 50(盤中;收盤 37) | volmageddon | -10% |
| **2020/3/16** | **82.7**(收盤史上最高) | COVID | -30%(2 月內) |
| 2022/9 | 33 | Fed 鷹派 | -7% |
| 2024/8/5 | 65(盤中) | 套利平倉 | -19% 同日大跌 |

> VIX 紀錄:**盤中史上最高 89.53(2008/10/24)**;**收盤史上最高 82.69(2020/3/16)**,兩者不同口徑。

**規則**:VIX > 40 後 6 月 TWII 平均 +18%(6 次中 5 次正報酬),但須承受續跌 -10% 風險。
        """.strip(),
    ),
    (
        "🕐 美林時鐘 — 景氣 × 通膨 二維配置框架",
        """
2004 年美林證券提出,用 **GDP 動能(↑↓)** × **通膨方向(↑↓)** 切 4 象限:

| 階段 | GDP | 通膨 | 最佳資產 |
|---|---|---|---|
| **復甦** | ↑ | ↓ | **股票**(成長 + 寬鬆) |
| **擴張** | ↑ | ↑ | **商品**(原物料定價) |
| **高峰** | ↓ | ↑ | **現金**(避險 + 等高息) |
| **衰退** | ↓ | ↓ | **債券**(降息 + 避險) |

**台股對應策略**:
- 復甦/擴張:增加成長股、半導體、原物料
- 高峰:轉防禦股(電信、公用)、現金、海外債
- 衰退:長期公債、防禦股、避開高 β 個股

📐 **數學定義(階段判斷)**

```
GDP 動能 = sign(GDP_QoQ_annualized 趨勢 over 6M)
通膨方向 = sign(CPI YoY 趨勢 over 6M)

→ 復甦  if GDP↑ & CPI↓
→ 擴張  if GDP↑ & CPI↑
→ 高峰  if GDP↓ & CPI↑
→ 衰退  if GDP↓ & CPI↓
```

**美林原版回測(1973-2004)4 階段年化報酬**(原報告階段名 Reflation/Recovery/Overheat/Stagflation)

| 階段(原文) | 股票 | 債券 | 商品 | 現金 |
|---|---|---|---|---|
| 復甦 Recovery | **+19%** | +7% | -7% | +2% |
| 擴張 Overheat | +6% | 0% | **+19%** | +1% |
| 高峰 Stagflation | -11% | -1% | **+28%** | 0% |
| 衰退 Reflation | +6% | **+9%** | -11% | +3% |

> 數據引自美林 2004《The Investment Clock》原始報告,各方引用略有出入(整數 vs 小數、Stagflation 商品 +28%/+29% 兩版)。
> 上方白話的「高峰→現金」是**風險定位**口訣;原報告**實證**1973-2004 滯脹期反而**商品最強**(石油危機),兩者出發點不同(防守口訣 vs 歷史回測),不矛盾。

📜 **歷史案例(TWII 年報酬 vs 階段)**

| 年份 | 階段 | TWII 年報酬 | 重點 |
|---|---|---|---|
| 2009 | 復甦 | **+78%** | 4591 → 8188(從谷底反彈)|
| 2017 | 擴張 | +15% | 9253 → 10643(半導體領軍)|
| 2018 | 高峰 | -8% | 10643 → 9727 |
| 2008 | 衰退 | -46% | 8506 → 4591 |
| **2020** | **復甦** | **+22%** | 11997 → 14732(疫情後反彈) |
| 2022 | 高峰→衰退 | -22% | 18219 → 14137(Fed 升息) |
| 2023 | 復甦 | +27% | 14137 → 17930 |
| 2024 | 復甦/擴張 | +28% | 17930 → 23035(AI 行情)|
        """.strip(),
    ),
    (
        "💰 M1B-M2 黃金交叉 — TW 在地動能信號",
        """
- **M1B**:活期 + 支存(高流動性,即時可用)
- **M2**:M1B + 定存 + 外幣存款(全部準貨幣)

**M1B/M2 比率**上升 = 錢從定存轉活存,**等著進股市** → 多頭動能。
**M1B/M2 比率**下降 = 錢回流定存,股市籌碼乾涸 → 空頭風險。

**經典訊號**:M1B YoY > M2 YoY 持續 ≥ 3 個月 → **黃金交叉**,台股歷史上 6-12 月平均
報酬 +20%(2009 / 2017 / 2020 都觸發)。**死亡交叉**反之。

**資料源**:央行 CBC ms1.json 月公布,本系統 90 天 cache fallback。

📐 **數學定義**

```
M1B = 通貨 + 支票存款 + 活期存款 + 活期儲蓄存款
M2  = M1B + 定存 + 定儲 + 外幣存款 + 郵儲

M1B YoY (%) = (M1B_now - M1B_12M_ago) / M1B_12M_ago × 100
M2  YoY (%) = (M2_now  - M2_12M_ago)  / M2_12M_ago  × 100

Spread = M1B YoY - M2 YoY

黃金交叉 = Spread 由負轉正 且持續 ≥ 3 月
死亡交叉 = Spread 由正轉負 且持續 ≥ 3 月
```

**為何 M1B/M2 比率有解釋力?** 該比率反映「**準備買股的錢** / **總準貨幣**」,
比率上升即「資金正從定存搬到活存準備進場」,屬於 TW 在地獨家動能。

📜 **歷史案例(M1B-M2 交叉 vs TWII)**

| 黃金交叉日 | Spread 由負轉正 | TWII 起點 | 後 12 月 TWII |
|---|---|---|---|
| 2009/2 | -3% → +4% | 4591 | **+78%**(8188)|
| 2012/9 | -2% → +1% | 7715 | +12% |
| 2017/3 | -1% → +3% | 9811 | +13% |
| **2020/6** | **+5% → +13%**(最大 spread) | **11621** | **+30%**(15125)|
| 2023/9 | -1% → +2% | 16480 | +30%(21450)|

**死亡交叉反例**:2007/12 Spread 由正轉負 → 2008 大跌 -46%。
2022/3 Spread 由正轉負 → 12 月內 -22%。
        """.strip(),
    ),
    (
        "📏 Z-Score / σ band — 統計極端值如何用於進出場",
        """
**Z-Score**:某指標**現值** vs **歷史平均** 差幾個標準差(σ):

```
Z = (現值 - μ) / σ
```

- Z = 0:正常區
- |Z| > 1:偏離(機率 ~32%)
- |Z| > 2:極端(機率 ~5%)
- |Z| > 3:罕見(機率 ~0.3%)

**應用**(本系統 σ band 進出場):
- **z=+2** 過熱 → 賣出訊號(年高 + 2σ 對應的價格)
- **z=-2** 過冷 → 買進訊號(年低 - 2σ 對應的價格)
- **z=+3 / z=-3** 極端 → 加倍訊號

**為何 ±1.5σ / ±2σ 是常用 cut-off?** 統計上 ±2σ 約 5%,**極罕見必反應**;
±1.5σ 約 13%,**夠少見值得反應**。

📐 **數學定義**

```
μ (mean)    = Σ x_i / n
σ (std dev) = √(Σ (x_i - μ)² / (n-1))
Z = (x_current - μ) / σ

常態分布累積機率(經驗法則 68-95-99.7):
  P(|Z| < 1) ≈ 68.27%
  P(|Z| < 2) ≈ 95.45%
  P(|Z| < 3) ≈ 99.73%
  P(|Z| > 2) ≈ 4.55% → 「20 次出現 1 次」
```

**Lookback 選擇(本系統實際)**:

> ⚠️ **v19.181 更正**:本段舊版寫「個股 vol / 韭菜指數 → 252 / 1250 交易日、
> 殖利率 / VIX → 252 交易日、M1B-M2 spread → 60 月」—— 全 repo grep
> `1250` 與 5 年月頻 z-score **一個都不存在**,韭菜指數更是連 z-score 都沒算
> (見「散戶情緒反指標」章)。實際上系統只有**一處**在算 Z-Score:

- **指標解讀手冊的即時值卡**(本頁上方,`shared.macro_card.calc_z_score`):
  拿該指標**手上有的整段序列**當母體,不另設固定視窗 ——
  `^VIX` ≈ 60 個交易日、`^TNX` / `^SOX` / `DXY` ≈ 90 個交易日、
  FRED 系列(核心 CPI / 出口 YoY / PMI)≈ 24 個月。
  少於 10 點就不顯示 Z(寧可不給,不給一個樣本數不足的假 Z)。
- 趨勢圖(sparkline)另外只取**最後 60 點**,那是視覺裁切,**不是** Z 的母體。

> 📌 `TRADING_DAYS_PER_YEAR = 252`(`shared/signal_thresholds.py`)確實存在,
> 但它的用途是**年化換算**(IRR / 年化波動率 / Sharpe),不是 Z-Score 視窗 ——
> 兩件事不要混為一談。

📜 **歷史案例(TW 在地 Z-Score 應用)**

| 指標 | 日期 | 現值 | μ / σ | Z | 後續(6-12M)|
|---|---|---|---|---|---|
| VIX | 2020/3 | 82.7(收盤)| 19/8 | **+8.0** | TWII +35% |
| 外資期貨 net | 2008/10 | -8.5 萬口 | -1/3 萬 | **-2.5** | TWII -22%(續跌)/ -34%(底)|
| 融資餘額 | 2021/11 | 2540 億 | 1600/450 | **+2.1** | TWII -29% |
| TWII RSI | 2009/3 | 25 | 50/15 | -1.7 | +78%(極端低反彈)|
| 美 ISM | 2008/12 | 32.4 | 52/5 | **-4.0** | TWII 後 12 月 +78%(谷底反彈)|

**逆向操作經驗值**:Z > +3 或 Z < -3 的指標後 6-12 月,均值回歸機率 > 75%。
        """.strip(),
    ),
]


def render_principle_classroom() -> None:
    """📚 總經原理小教室 — 永久 expander,初學者隨時可查的書本式解釋。

    10 段核心概念,每段 200-400 字,適合「學一次 → 看其他指標都通」。
    對齊 Fund 版本但加 TW 在地補充(外資/韭菜/M1B-M2 等台股獨家章節)。
    """
    st.divider()
    with st.expander(
        "📚 總經原理小教室 — 看不懂的指標?點這裡學一次,終身受用",
        expanded=False,
    ):
        st.caption(
            "為初學者整理的 10 個核心總經概念,**含 TW 股市在地補充**。"
            "每段都解釋「是什麼 / 為何重要 / 怎麼判讀」。"
            "建議按順序讀完,之後看其他指標就會通。"
        )
        # B6-a v19.181:章節內文的門檻 / 係數 / 來源清單一律走 `§§TOKEN§§`,
        # 由 SSOT 即時代入(見 `_edu_tokens`)。token 表**取一次**重複用,
        # 避免每章都重跑 PMI_SOURCE_REGISTRY 的 late import。
        _tokens = _edu_tokens()
        for _i, (_title, _body) in enumerate(_PRINCIPLE_CHAPTERS, 1):
            st.markdown(f"### {_i}. {_resolve_edu_tokens(_title, _tokens)}")
            st.markdown(_resolve_edu_tokens(_body, _tokens))
            st.markdown("---")
