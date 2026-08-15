"""src/ui/tabs/macro/section_state.py — Section 2 拐點偵測 + 市場狀態卡(F-7.1 B-S2 抽出)。

📊 整合六大面向 + CPI×Fed 雙頂回落(v18.169;v19.173 正名,原「MK 黃金拐點」——
「MK」= Mann-Kendall 的通用縮寫,但那條規則只是兩點差分,見 macro_helpers 註解);
結論寫入 st.session_state['regime_data'] 供其他 tab 共用。

closure params(4 explicit pass):
- _mkt_info: dict | None  market_regime() 結果(從 S1 算出)
- _mkt_placeholder, _tl_placeholder: streamlit placeholder(S1 預留)
- cd: dict  cl_data alias
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.calc_helpers import calc_bias_pct  # R-CALC-3 v18.412
from shared.colors import (  # noqa: F401
    TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
)
from src.config import FINMIND_TOKEN  # noqa: F401
# v19.176 P0-D:韭菜指數拐點門檻走 L0 SSOT(§3.3);與另外兩組同名不同義的
# 門檻分別命名,詳見 src/config/config.py「韭菜指數門檻 SSOT」區塊。
from src.config import LEEK_PIVOT_HIGH_PCT, LEEK_PIVOT_LOW_PCT
# v19.183 D2 §3.3:拐點面板乖離門檻 ±10 / ±8 原為 inline magic number,抽至 L0 SSOT。
from shared.signal_thresholds import PIVOT_BIAS_20_PCT, PIVOT_BIAS_240_PCT
# v19.183 D2:M1B/M2 是否為「^TWII 動能代理」的判定 SSOT(原用從未被寫入的 is_proxy 鍵)。
from shared.macro_provenance import is_m1b_m2_proxy
from src.compute.macro import calc_traffic_light  # noqa: F401
from src.ui.tabs.macro.handlers import _render_traffic_light  # noqa: F401


def render_section_state(_mkt_info, _mkt_placeholder, _tl_placeholder, cd,
                         show_market_data: bool = True) -> None:
    """渲染 §二 拐點偵測 + 市場狀態(原 tab_macro line 2186-2565)。

    Args:
        _mkt_info: `market_regime()` 結果(從 S1 算出)。
        _mkt_placeholder / _tl_placeholder: S1 預留的 st.empty 佔位符。
        cd: `cl_data` alias。
        show_market_data: 快取是否新鮮(≤30 分且非刷新中)——**與
            `section_traffic_light.render_traffic_light_top()` 回傳的第二個值同源**。
            False 時本函式**不重算也不回填**紅綠燈卡,讓頁頂維持「⏳ 燈號等待中」,
            避免用過期快取蓋掉新鮮度警告(§2.4;詳見函式尾端註解)。
            預設 True 是為了不破壞既有 positional caller(tab_macro 已改為顯式傳值)。
    """
    # ══════════════════════════════════════════════════════════════
    # 拐點偵測系統（整合六大面向 + CPI×Fed 雙頂回落，v18.169；v19.173 正名）
    # ══════════════════════════════════════════════════════════════
    if _mkt_info:
        _mi2    = _mkt_info
        _ma60   = _mi2.get('ma60', 0)
        _ma120  = _mi2.get('ma120', 0)
        _ma200  = _mi2.get('ma200', 0)
        _idx2   = _mi2.get('index_price', 0)
        _sigs2  = _mi2.get('signals', [])
        # v19.183 D2:原本這裡有 `_regime2 = _mi2.get('regime','neutral')`。
        # 兩個問題,故整行移除:
        #   ① **死變數** —— 全檔零 reference(2026-08-07 複驗),只是 C1 之前的殘留。
        #   ② 它直讀 raw `mkt_info['regime']`(趨勢面**輸入**)並在缺值時捏 'neutral',
        #      正是 C1 `shared/regime_arbiter.py` 要消滅的第 3 個 producer(P3)。
        #      留著等於留一顆地雷:下一個人看到現成變數就會拿去當「大盤 regime」用。
        # 本 section 若日後真的需要 regime,一律取 `calc_traffic_light` 的
        # `effective_regime`(canonical 結論),不得再讀 raw。
        _m1b2   = st.session_state.get('m1b_m2_info', {})
        _bias2  = st.session_state.get('bias_info', {})
        _li2    = st.session_state.get('li_latest')
        _cd2    = st.session_state.get('cl_data', {})
        _tw2    = _cd2.get('tw', {})
        _twd_df = _tw2.get('新台幣匯率')
    
        # ── 計算各項拐點訊號 ─────────────────────────────────────
        pivot_signals = []  # (label, icon, color, detail)
        # v19.173：訊號「群」的可評估名單（§資訊單調性，比照
        #   allocation_service._derive_intrinsic_caps 的「未知 ≠ 不利」原則）。
        #   每個 fetch/資料 gate 成功就登記對應 family key；沒登記的群 →
        #   下方 aggregate_pivot_families() 會標「未評估」並**從分母剔除**，
        #   既不當成偏空、也不當成不偏空。這樣「多抓到一個來源」只會改變
        #   分母與該群的方向，不會像舊的絕對計數那樣讓結論整個反轉。
        _fam_ok: set = set()
    
        # 1. 技術面：均線方向（MA60/MA120 彎折）
        if _ma60 and _ma120 and _idx2:
            _fam_ok.add('trend')   # v19.173：均線資料到位 → 趨勢群可評估
            _turn_up   = any('向上彎折' in s for s in _sigs2)
            _turn_down = any('向下' in s and 'MA' in s for s in _sigs2)
            _above60   = _idx2 > _ma60
            _above120  = _idx2 > _ma120
            _above200  = _idx2 > _ma200 if _ma200 else None
            # R-CALC-3 v18.412:乖離率公式 SSOT(calc_bias_pct)
            _d60  = calc_bias_pct(_idx2, _ma60)  or 0.0
            _d120 = calc_bias_pct(_idx2, _ma120) or 0.0
    
            if _turn_up and _above60 and _above120:
                pivot_signals.append(('均線多頭確認','🟢',TRAFFIC_GREEN,
                    f'站上MA60(+{_d60:.1f}%) & MA120(+{_d120:.1f}%) + 均線向上彎折 → 中長線起漲點'))
            elif _turn_up and _above60:
                pivot_signals.append(('均線初步翻多','🟡',TRAFFIC_YELLOW,
                    f'站上MA60(+{_d60:.1f}%) + 向上彎折，待突破MA120({_ma120:,.0f})確認'))
            elif not _above60 and _turn_down:
                pivot_signals.append(('均線空頭確認','🔴',TRAFFIC_RED,
                    f'跌破MA60({_d60:.1f}%) + 均線向下 → 中期起跌訊號'))
            elif _above60 and not _above120:
                # v19.183 D2:'#8b949e' → TRAFFIC_NEUTRAL(語意相同的灰,行為不變:
                # 兩者都不等於 TRAFFIC_RED/GREEN → aggregate_pivot_families 判 neutral)。
                # 收成具名常數是為了讓「拐點色碼只能用 traffic SSOT」這條不變量
                # 可以被 tests/test_d2_macro_sections.py 的 AST 守衛精確驗證 ——
                # 只要清單裡還留一個 hex 字面值,守衛就得放寬,下一個寫死的
                # '#da3633' 就又會混進來(那正是本次修掉的月線乖離 bug)。
                pivot_signals.append(('整理區間','⚪',TRAFFIC_NEUTRAL,
                    '站上MA60但未過MA120 → 等待方向確認'))
    
        # 2. 乖離率（與台股體質 ±7~10% 門檻）
        if _bias2:
            _fam_ok.add('level')   # v19.173：乖離率資料到位 → 位階群可評估
            _b240 = _bias2.get('bias_240', 0)
            _b60  = _bias2.get('bias_60', _bias2.get('bias_20', 0))
            _b20  = _bias2.get('bias_20', 0)
            if _b240 > PIVOT_BIAS_240_PCT:
                pivot_signals.append(('年線乖離過大','⚠️',TRAFFIC_RED,
                    f'年線乖離 +{_b240:.1f}% > {PIVOT_BIAS_240_PCT:.0f}% → 頂部拐點區間，考慮減碼'))
            elif _b240 < -PIVOT_BIAS_240_PCT:
                pivot_signals.append(('年線深度低估','💡',TRAFFIC_GREEN,
                    f'年線乖離 {_b240:.1f}% < -{PIVOT_BIAS_240_PCT:.0f}% → 底部拐點區間，考慮布局'))
            if abs(_b20) > PIVOT_BIAS_20_PCT:
                _bl20 = '過熱' if _b20 > 0 else '超賣'
                # ── v19.183 D2 §2.1:色碼改吃 traffic SSOT（原 '#da3633' / '#2ea043'）──
                # 【為什麼這是 bug 而不是配色偏好】下游
                # `macro_helpers.aggregate_pivot_families` 判「這一群偏多還偏空」是
                # **嚴格比對** `color == TRAFFIC_RED` / `TRAFFIC_GREEN`
                # （= '#ef4444' / '#22c55e'，見 shared/colors.py）。
                # '#da3633' / '#2ea043' 是 v19.68 換色前的舊 GitHub 色票，兩者都
                # **永遠不相等** → 這兩盞燈落進 `setdefault(..., 'neutral')`，
                # 「位階（乖離率）」群在只有月線訊號的日子恆判「中性」。
                # 實際後果：畫面小卡印紅色「⚠️ 月線過熱」，同一頁上方的分群明細
                # 卻寫「位階（乖離率）：中性」，而且該群不進 n_bear 分子 →
                # 綜合拐點結論被系統性拉向「訊號分歧」。
                # macro_helpers 的 docstring 已把這條列為「已知落差、待 section_state
                # 端單獨修」，此即該修正。
                pivot_signals.append((f'月線{_bl20}',
                    '⚠️' if _b20 > 0 else '💡',
                    TRAFFIC_RED if _b20 > 0 else TRAFFIC_GREEN,
                    f'月線乖離 {_b20:+.1f}% → 短線{_bl20}修正機率高'))
    
        # 3. M1B-M2（資金面黃金/死亡交叉）
        # ── v19.183 D2 §3.3 幽靈 key：`_m1b2.get('is_proxy')` 從未被寫入 ──────────
        # `m1b_m2_info` 由 `macro_snapshot.fetch_m1b_m2_block()` 產生，回傳鍵只有
        # {m1b_yoy, m2_yoy, gap, source} —— 沒有 `is_proxy`。真正的旗標是更上游
        # `tw_macro.fetch_cbc_m1b_m2()` 的 `is_proxy_tier`，被重新打包時丟掉了。
        # 於是這道守門「代理值不得產生黃金/死亡交叉訊號」**一次都沒擋到過**：
        # CBC 兩層全敗、退到 ^TWII 20/60 日動量硬湊出來的假 M1B/M2，照樣被寫成
        # 「M1B>M2 黃金交叉 → 資金由定存轉入股市，長線起漲徵兆」。
        # 判定改走 L0 SSOT `shared.macro_provenance.is_m1b_m2_proxy()`（同時吃
        # 布林旗標與 source 標籤，精確比對不做 substring 嗅探）。
        if _m1b2 and not is_m1b_m2_proxy(_m1b2):
            _fam_ok.add('liquidity')   # v19.173：M1B/M2 到位 → 資金群可評估
            _m1b_y = _m1b2.get('m1b_yoy', 0)
            _m2_y  = _m1b2.get('m2_yoy', 0)
            _diff  = _m1b_y - _m2_y
            if _diff > 0:
                pivot_signals.append(('M1B>M2 黃金交叉','✅',TRAFFIC_GREEN,
                    f'M1B({_m1b_y:.1f}%) > M2({_m2_y:.1f}%) → 資金由定存轉入股市，長線起漲徵兆'))
            elif _diff < -1:
                pivot_signals.append(('M1B<M2 死亡交叉','❌',TRAFFIC_RED,
                    f'M1B({_m1b_y:.1f}%) < M2({_m2_y:.1f}%) → 資金撤離股市，長線起跌警示'))
    
        # 4. 台幣匯率（貶轉升=外資流入，升轉貶=外資撤退）
        if _twd_df is not None and not _twd_df.empty:
            _twd_col = 'close' if 'close' in _twd_df.columns else 'Close'
            if _twd_col in _twd_df.columns and len(_twd_df) >= 10:
                _fam_ok.add('liquidity')   # v19.173：台幣序列到位 → 資金群可評估
                _twd_now   = float(_twd_df[_twd_col].iloc[-1])
                _twd_prev5 = float(_twd_df[_twd_col].iloc[-5])
                _twd_chg   = (_twd_now - _twd_prev5) / _twd_prev5 * 100
                # 注意：TWD=X 是 USD/TWD，數字越小=台幣越升值
                if _twd_chg < -0.5:  # 台幣升值 (匯率數字下降)
                    pivot_signals.append(('台幣升值','✅',TRAFFIC_GREEN,
                        f'台幣近5日升值 {abs(_twd_chg):.1f}% → 外資熱錢流入，指數底部反彈訊號'))
                elif _twd_chg > 0.5:  # 台幣貶值 (匯率數字上升)
                    pivot_signals.append(('台幣貶值','⚠️',TRAFFIC_YELLOW,
                        f'台幣近5日貶值 {_twd_chg:.1f}% → 外資撤退觀察，留意資金流出風險'))
    
        # 5. 外資期貨 + 散戶比（先行指標）
        if _li2 is not None and not _li2.empty:
            _fam_ok.add('chips')   # v19.173：先行指標到位 → 籌碼群可評估
            _last_li = _li2.iloc[-1]
            _fut_net = _last_li.get('外資大小')
            _leek    = _last_li.get('韭菜指數')
            _pcr     = _last_li.get('選PCR')
            if _fut_net is not None:
                _fut_net_v = float(_fut_net)
                if _fut_net_v < -30000:
                    pivot_signals.append(('外資期貨大量空單','🔴',TRAFFIC_RED,
                        f'外資期貨淨空 {abs(_fut_net_v):,.0f}口 > 3萬口 → 頂部起跌訊號'))
                elif _fut_net_v < 0 and abs(_fut_net_v) < 10000:
                    pivot_signals.append(('外資空單縮減','🟡',TRAFFIC_YELLOW,
                        f'外資期貨淨空 {abs(_fut_net_v):,.0f}口（補回中）→ 底部拐點觀察'))
                elif _fut_net_v > 10000:
                    pivot_signals.append(('外資期貨多方','✅',TRAFFIC_GREEN,
                        f'外資期貨淨多 {_fut_net_v:,.0f}口 → 多頭強勢確認'))
            # v19.176 P0-D §3.3：門檻 ±20 原為 inline magic number，抽至 L0 SSOT
            # `config.LEEK_PIVOT_*`。拐點用途 → 敏感度取中、且左右對稱
            # （偵測轉折不預設方向偏好）。**刻意不與** section_chips 的
            # 進階警示（±30）／綜合評分（+10/-5）合併：三者用途不同，
            # 合併是行為變更。⚠️ 亦與 config.LEEK_HIGH_THRESHOLD(35) 那組
            # 「融資餘額 0~100 指數」不同量綱，不可互換（§4.1）。
            if _leek is not None:
                _leek_v = float(_leek)
                if _leek_v > LEEK_PIVOT_HIGH_PCT:
                    pivot_signals.append(('散戶極度看多（危險）','⚠️',TRAFFIC_RED,
                        f'韭菜指數 {_leek_v:+.1f}% > {LEEK_PIVOT_HIGH_PCT:+.0f}%'
                        ' → 散戶過熱，頂部拐點警示（反向指標）'))
                elif _leek_v < LEEK_PIVOT_LOW_PCT:
                    pivot_signals.append(('散戶極度悲觀（機會）','💡',TRAFFIC_GREEN,
                        f'韭菜指數 {_leek_v:+.1f}% < {LEEK_PIVOT_LOW_PCT:+.0f}%'
                        ' → 散戶極度看空，底部拐點機會（反向指標）'))
    
        # ── 6. 台灣領先指標拐點（景氣對策 / 領先指標 / 外資連續日數）─────
        try:
            from src.data.macro import (
                fetch_ndc_signal_history as _f_ndc_h,
                fetch_ndc_leading_index as _f_ndc_li,
                fetch_foreign_consecutive_days as _f_fi_streak,
            )
            _FMD_TK = st.secrets.get('FINMIND_TOKEN', '') \
                if hasattr(st, 'secrets') else ''
            _ndc_h = st.session_state.get('_ndc_hist_cache')
            if _ndc_h is None:
                _ndc_h = _f_ndc_h(months_back=12, token=_FMD_TK or '')
                st.session_state['_ndc_hist_cache'] = _ndc_h
            _ndc_li = st.session_state.get('_ndc_li_cache')
            if _ndc_li is None:
                _ndc_li = _f_ndc_li(months_back=18, token=_FMD_TK or '')
                st.session_state['_ndc_li_cache'] = _ndc_li
            _fi_st = st.session_state.get('_fi_streak_cache')
            if _fi_st is None:
                _fi_st = _f_fi_streak(days_back=30, token=_FMD_TK or '')
                st.session_state['_fi_streak_cache'] = _fi_st
    
            # v19.173：登記可評估群。景氣對策(6-A) 與 領先指標(6-B) 同屬國發會
            #   **同一份資料集**（領先指標本身就是景氣對策信號的構成項），
            #   故合併為一個 'cycle' 群 —— 兩者同號幾乎必然，不該當成兩份證據。
            #   6-C 外資連續日數屬籌碼面，併入 'chips'（與外資期貨同一齣戲）。
            if _ndc_h or _ndc_li:
                _fam_ok.add('cycle')
            if _fi_st:
                _fam_ok.add('chips')

            # 6-A 景氣對策信號拐點
            _inf = (_ndc_h or {}).get('inflection', '')
            _sc, _spv = (_ndc_h or {}).get('score_latest'), (_ndc_h or {}).get('score_prev')
            if '翻多' in _inf:
                pivot_signals.append(('景氣對策連2月翻多','🚀',TRAFFIC_GREEN,
                    f'分數 {_spv}→{_sc} 由跌轉升 → 景氣領先翻揚拐點'))
            elif '翻空' in _inf:
                pivot_signals.append(('景氣對策連2月翻空','⚠️',TRAFFIC_RED,
                    f'分數 {_spv}→{_sc} 由升轉跌 → 景氣動能衰退拐點'))
            elif '連3月上升' in _inf:
                pivot_signals.append(('景氣對策連3月上升','✅',TRAFFIC_GREEN,
                    f'分數穩步上升至 {_sc}/45 → 景氣擴張持續'))
            elif '連3月下降' in _inf:
                pivot_signals.append(('景氣對策連3月下降','❌',TRAFFIC_RED,
                    f'分數連續下滑至 {_sc}/45 → 景氣收縮持續'))
    
            # 6-B 領先指標 6M smoothed change
            _li_inf = (_ndc_li or {}).get('inflection', '')
            _s6m = (_ndc_li or {}).get('smooth6m')
            _ps6m = (_ndc_li or {}).get('prev_s6m')
            if '由負轉正' in _li_inf and _s6m is not None and _ps6m is not None:
                pivot_signals.append(('領先指標 6M 由負轉正','🚀',TRAFFIC_GREEN,
                    f'6M smoothed change：{_ps6m:+.2f}%→{_s6m:+.2f}% → 景氣翻揚黃金拐點'))
            elif '由正轉負' in _li_inf and _s6m is not None and _ps6m is not None:
                pivot_signals.append(('領先指標 6M 由正轉負','⚠️',TRAFFIC_RED,
                    f'6M smoothed change：{_ps6m:+.2f}%→{_s6m:+.2f}% → 景氣轉折下行'))
            elif '持續擴張' in _li_inf and _s6m is not None:
                pivot_signals.append(('領先指標持續擴張','✅',TRAFFIC_GREEN,
                    f'6M smoothed change {_s6m:+.2f}% 維持正值 → 景氣擴張'))
            elif '持續收縮' in _li_inf and _s6m is not None:
                pivot_signals.append(('領先指標持續收縮','❌',TRAFFIC_RED,
                    f'6M smoothed change {_s6m:+.2f}% 維持負值 → 景氣收縮'))
    
            # 6-C 外資連續日數反轉
            _fi_inf = (_fi_st or {}).get('inflection', '')
            _cd = (_fi_st or {}).get('consec_days')
            _ps = (_fi_st or {}).get('prev_streak')
            if '賣→買' in _fi_inf:
                pivot_signals.append(('外資由連賣轉買','🚀',TRAFFIC_GREEN,
                    f'外資連 {-_ps if _ps else 0} 賣後首日翻買 → 籌碼面拐點'))
            elif '買→賣' in _fi_inf:
                pivot_signals.append(('外資由連買轉賣','⚠️',TRAFFIC_RED,
                    f'外資連 {_ps if _ps else 0} 買後首日翻賣 → 籌碼動能減弱'))
            elif '連' in _fi_inf and '買超' in _fi_inf and _cd is not None:
                pivot_signals.append(('外資連續買超','✅',TRAFFIC_GREEN,
                    f'外資已連 {_cd} 日買超 → 籌碼穩健'))
            elif '連' in _fi_inf and '賣超' in _fi_inf and _cd is not None:
                pivot_signals.append(('外資連續賣超','❌',TRAFFIC_RED,
                    f'外資已連 {abs(_cd)} 日賣超 → 籌碼流出警示'))
        except Exception as _e_tp6:
            print(f'[tab_macro/拐點面板6] {type(_e_tp6).__name__}: {_e_tp6}')
    
        # ── 7. CPI×Fed 雙頂回落（CPI YoY × Fed Funds Rate 同步回落）───────
        # v18.169：鏡像 fund services/macro_service.py::_detect_inflection
        # 規則：CPI 月降 + Fed Funds 月降/持平 → ⭐ 強訊號（多頭最佳買點）
        # 邏輯純函式集中於 macro_helpers.detect_cpi_fed_double_top（可單測）
        #
        # v19.173 正名：原名「MK 黃金拐點」/ detect_mk_golden_inflection。
        #   「MK」是 Mann-Kendall 的通用縮寫，但這條規則只是「本月 vs 上月」
        #   兩點差分 + 固定 ppt 門檻 —— 沒有 S 統計量 / Var(S) / Z / p-value /
        #   tie 修正（全 repo `grep -i mann` = 0 hit）。掛 MK 之名等於借了一個
        #   它沒有的統計背書。真正的 Mann-Kendall 見 `shared/mk_test.py`。
        #   ⚠️ 判定邏輯**零變更**，只換名字與 label。
        #
        # v19.173 未做（並列 MK 佐證）：原規劃在此同時顯示 CPI / Fed 的真
        #   Mann-Kendall 統計量（Z / p / Sen's β / n）。**做不了**，因為手上
        #   根本沒有序列 —— `macro_snapshot.fetch_cpi_block()` 只回
        #   {yoy, prev_yoy, date, source}，`fetch_fed_funds_block()` 只回
        #   {current, prev, date, source}，兩者都是**純量**，session_state
        #   的 macro_info 也只存這些。要並列就得新增「回整條月頻序列」的
        #   fetcher，而那屬新資料流（CLAUDE.md §7 需先對齊 endpoint / 單位 /
        #   發布延遲 / PIT 對齊鍵），不在本輪授權範圍。
        #   §1：寧可不顯示，也不拿兩個點硬算一個沒有檢定力的 Z（n=2 時
        #   `mann_kendall()` 直接回 None，這是刻意的）。
        try:
            from src.compute.macro import detect_cpi_fed_double_top as _det_cf
            _mi_mk = st.session_state.get('macro_info') or {}
            _cpi_mk = _mi_mk.get('us_core_cpi') or {}
            _fed_mk = _mi_mk.get('fed_funds') or {}
            # v19.173：四個輸入齊全才算「通膨利率群可評估」；
            #   缺任一個 → 該群不進分母（不是「不偏空」，是「沒判斷」）。
            if all(_v is not None for _v in (
                    _cpi_mk.get('yoy'), _cpi_mk.get('prev_yoy'),
                    _fed_mk.get('current'), _fed_mk.get('prev'))):
                _fam_ok.add('inflation')
            _mk_sig = _det_cf(
                cpi_yoy=_cpi_mk.get('yoy'),
                cpi_prev_yoy=_cpi_mk.get('prev_yoy'),
                fed_rate=_fed_mk.get('current'),
                fed_prev_rate=_fed_mk.get('prev'),
            )
            if _mk_sig is not None:
                pivot_signals.append((
                    _mk_sig['label'], _mk_sig['icon'],
                    _mk_sig['color'], _mk_sig['detail'],
                ))
        except Exception as _e_tp7:
            print(f'[tab_macro/拐點面板7-CPIxFed] {type(_e_tp7).__name__}: {_e_tp7}')
    
        # v1.2 暫存供 AI 首席總經分析師讀（章節：拐點訊號摘要）
        st.session_state['_pivot_signals'] = list(pivot_signals)
    
        # ── 綜合評分 & 顯示 ──────────────────────────────────────
        # v19.173：從「數紅燈個數」改成「數偏空的**群**數 + 顯示分母」。
        #
        # 【為什麼不能直接數訊號個數 —— 共線性】
        # 舊寫法 `sum(1 for ... if c == TRAFFIC_RED)` 隱含假設每盞紅燈都是一份
        # **獨立**證據。實際上這些訊號彼此高度相關：
        #   - 「年線乖離過大 / 外資期貨大量空單 / 散戶極度看多」是同一個
        #     「多頭末端擁擠度」因子的三種量測；
        #   - 「景氣對策連 2 月翻空 / 領先指標 6M 由正轉負」出自國發會同一份
        #     資料集（領先指標是景氣對策信號的構成項），幾乎必然同號。
        # 等相關（equicorrelated）近似下的有效獨立訊號數為
        #
        #       n_eff = n / ( 1 + (n − 1) · ρ̄ )
        #
        # 代 n = 4、ρ̄ = 0.7 → n_eff = 4 / (1 + 3×0.7) = 4/3.1 ≈ 1.29，
        # 也就是「4 個空頭訊號」實際只值約 1.3 個獨立訊號 —— 確信度誇大約 3 倍。
        # （ρ̄ = 0.7 是量級假設而非本專案實測，故**不印到畫面**，只用來解釋
        #   為何要分群；§3.3 反捏造。）
        #
        # 【為什麼要有分母 —— 資訊單調性】
        # 舊門檻 `_bear_pts >= 2` 是絕對計數，面向 6 需 FinMind token、面向 7 需
        # CPI+Fed，任一 fetch 失敗就少幾盞燈 → 同一個市場可能從「🔴 4 個空頭」
        # 掉成「⚪ 訊號分歧」。這與 allocation_service.py:178-212（v19.170 已修的
        # 三環第一環）是同一類 bug：多知道 / 少知道一個事實，結論反而反轉。
        # 現在改成：拿不到資料的群 → 標「未評估」、**排除於分母外**，
        # 既不當「不偏空」也不當「偏空」，且分母一定寫給使用者看。
        #
        # 分群 / 門檻 / 判定式的 SSOT 在 macro_helpers（L2 純函式，可單測）。
        from src.compute.macro import aggregate_pivot_families as _agg_pv
        _pv_agg = _agg_pv(pivot_signals, evaluable=_fam_ok)
    
        # 新舊門檻等價性（詳見 macro_helpers.PIVOT_MIN_SIDE_FAMILIES 註解）：
        #   舊 `>= 2` 的單位是「訊號」，新 `>= 2` 的單位是「群」，常數值不動。
        #   兩訊號分屬不同群 → 新舊完全等價；兩訊號擠在同一群 → 舊成立、新不成立，
        #   而那正是共線性誤判（同一因子的兩種量測不是兩份獨立證據）。
        _pivot_overall = _pv_agg['headline']
        _pivot_color   = _pv_agg['color']
    
        # v18.321：🔮 拐點群組 banner（與其他桶一致的分隔條，分組化收尾）
        from shared.macro_buckets import bucket_group_banner_html as _bgb_pv
        st.markdown(_bgb_pv('pivot', 0), unsafe_allow_html=True)
    
        st.markdown(f'<div style="background:#161b22;border-left:4px solid {_pivot_color};'
                    f'border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;'
                    f'font-size:13px;font-weight:600;color:{_pivot_color};">'
                    f'{_pivot_overall}</div>', unsafe_allow_html=True)
        # v19.173：分群明細 + 未評估揭露（§1 誠實揭露資料完整度）。
        #   把「哪幾群偏空、哪幾群根本沒資料」攤開，使用者才知道那句結論
        #   是建立在幾份**互相獨立**的證據上，而不是同一件事被數了好幾次。
        _pv_side_txt = {'bull': '偏多', 'bear': '偏空',
                        'neutral': '中性', 'unevaluated': '未評估'}
        st.caption('　'.join(
            f"{_f['name']}：{_pv_side_txt.get(_f['side'], _f['side'])}"
            for _f in _pv_agg['families'].values()))
        st.caption(
            '💡 同一群內的訊號（例：外資期貨大空單＋散戶極度看多）源自同一個潛在'
            '因子，**群內取最壞、不累加** —— 避免把同一件事數成多份獨立證據而'
            '誇大確信度。'
        )
        if _pv_agg['note']:
            st.caption(_pv_agg['note'])
        if _pv_agg['unknown_labels']:
            # 不靜默吞：label 與 macro_helpers.PIVOT_FAMILY_OF 對不上時要看得見，
            # 否則新增訊號時會悄悄從分子分母同時消失（§1 Fail Loud）。
            print('[tab_macro/拐點分群] 未歸群的訊號 label='
                  f"{_pv_agg['unknown_labels']}")
    
        # v18.319：六大面向 → verdict 小卡格（比照桶卡片，常駐可見），
        #          完整訊號敘述 + 判斷參考收進 Raw expander（要看才打開）。
        # v19.173 正名：原「六大面向 + MK 黃金拐點」（MK ≠ Mann-Kendall）
        st.markdown('##### 📊 拐點詳細分析 — 六大面向 + CPI×Fed 雙頂回落')
        if pivot_signals:
            _pv_cols = st.columns(3)
            for _pi, (_label, _icon, _color, _detail) in enumerate(pivot_signals):
                with _pv_cols[_pi % 3]:
                    st.markdown(
                        f"<div style='background:#0d1117;border:1px solid #21262d;"
                        f"border-top:3px solid {_color};border-radius:8px;"
                        f"padding:8px 10px;margin:3px 0;min-height:54px;"
                        f"display:flex;align-items:center;'>"
                        f"<span style='color:{_color};font-weight:700;font-size:13px;'>"
                        f"{_icon} {_label}</span></div>", unsafe_allow_html=True)
            with st.expander('🔍 拐點六大面向 — 完整訊號明細 + 判斷參考', expanded=False):
                for _label, _icon, _color, _detail in pivot_signals:
                    st.markdown(
                        f'<div style="background:#0d1117;border-left:3px solid {_color};'
                        f'border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;">'
                        f'<span style="color:{_color};font-weight:600;">{_icon} {_label}</span>'
                        f'<br><span style="color:#8b949e;font-size:12px;">{_detail}</span>'
                        f'</div>', unsafe_allow_html=True)
                # 拐點參考表 → 已移至 Tab5 策略手冊
                st.caption('📖 拐點判斷參考表 → 詳見「策略手冊」Tab')
        else:
            st.info('尚無足夠資料計算拐點，請點擊「🚀 一鍵更新全部數據」')
    
        # ── 熱錢深度監測（三角交叉：外資 × 匯率 × 背離偵測）─────────────
        # 拉到 expander 同層 sibling — Streamlit 禁止 expander 巢狀（原 #101 為 bug）
        # ── v1.2 倒掛翻正後 ^TWII 6/12/18M 表現歷史回測 ────────────────
        import os as _os_tw_bt
        try:  # v19.81:無 secrets.toml 時 st.secrets.get 會 raise(CI/裸跑)→ 降級 env-only
            _sec_fred_tw_bt = (st.secrets.get('FRED_API_KEY')
                               if hasattr(st, 'secrets') else None)
        except Exception:
            _sec_fred_tw_bt = None
        _fred_key_tw_bt = (_os_tw_bt.environ.get('FRED_API_KEY') or _sec_fred_tw_bt or '')
        with st.expander(
            '📊 歷史回測：美債倒掛翻正後 ^TWII 6/12/18M 表現',
            expanded=False,
        ):
            try:
                from src.compute.strategy import backtest_twii_turning_points as _bt_twii
                _bt = _bt_twii(_fred_key_tw_bt)
            except Exception as _bt_e:
                _bt = {"source_ok": False, "note": str(_bt_e)[:120],
                       "events": [], "summary": {"n_events": 0},
                       "twii_series": None, "t10y2y_series": None}
            if not _bt.get('source_ok'):
                st.info(f"⚠️ FRED 或 ^TWII 抓取失敗，回測暫不可用。{_bt.get('note','')}")
            elif _bt['summary']['n_events'] == 0:
                st.info(f"近 30 年無符合條件之倒掛翻正事件（{_bt.get('note','')}）")
            else:
                _sm = _bt['summary']
                _bk1, _bk2, _bk3, _bk4, _bk5 = st.columns(5)
                _bk1.metric('事件數', f"{_sm['n_events']}",
                             help=f"完整 18M 窗口：{_sm['n_complete_18m']}")
                _bk2.metric('+6M 中位數',
                             f"{_sm['median_6m']:+.1f}%" if _sm['median_6m'] is not None else '—',
                             delta=f"勝率 {_sm['win_rate_6m']:.0f}%"
                                    if _sm['win_rate_6m'] is not None else None)
                _bk3.metric('+12M 中位數',
                             f"{_sm['median_12m']:+.1f}%" if _sm['median_12m'] is not None else '—',
                             delta=f"勝率 {_sm['win_rate_12m']:.0f}%"
                                    if _sm['win_rate_12m'] is not None else None)
                _bk4.metric('+18M 中位數',
                             f"{_sm['median_18m']:+.1f}%" if _sm['median_18m'] is not None else '—',
                             delta=f"勝率 {_sm['win_rate_18m']:.0f}%"
                                    if _sm['win_rate_18m'] is not None else None)
                _bk5.metric('資料涵蓋',
                             f"{len(_bt['twii_series']):,} 日"
                             if _bt['twii_series'] is not None else '—')
                # 事件清單表
                _ev_df = pd.DataFrame(_bt['events'])
                if not _ev_df.empty:
                    _ev_df['翻正日'] = pd.to_datetime(_ev_df['date']).dt.date
                    # v19.183 D2（§2.3）：翻正日 ≠ 可執行進場日。把兩個日期同時
                    # 攤在表上，使用者才看得出這條績效是「哪一天買」算出來的。
                    _bt_cols = ['翻正日']
                    if 'entry_date' in _ev_df.columns:
                        _ev_df['可進場日'] = pd.to_datetime(
                            _ev_df['entry_date'], errors='coerce').dt.date
                        _bt_cols.append('可進場日')
                    _ev_df_disp = _ev_df[_bt_cols + ['t10y2y_min_pre',
                                            'ret_6m', 'ret_12m', 'ret_18m']].rename(
                        columns={'t10y2y_min_pre': '倒掛最深(%)',
                                 'ret_6m':  '+6M (%)',
                                 'ret_12m': '+12M (%)',
                                 'ret_18m': '+18M (%)'})
                    st.dataframe(_ev_df_disp, use_container_width=True,
                                  hide_index=True, height=240)
                # FIX(§3.3 反捏造): 原文含「但台股與美股相關性 ~0.6」——
                #   全 repo 沒有任何一行 code 在計算台股與美股的相關係數，該數字是憑空寫死的。
                #   而**本檔 L367-368 自己才剛立下紀律**：「ρ̄ = 0.7 是量級假設而非本專案實測，
                #   故不印到畫面；§3.3 反捏造」—— 同一個檔案上下自打臉。
                #   移除該數字，保留「需搭配 NDC 雙重確認」這個有效建議（它不依賴任何未實測的量）。
                st.caption(
                    '💡 **解讀**：美債 10Y-2Y 倒掛翻正後 6~18 個月內，'
                    '^TWII 歷史中位數正報酬率 = 底部累積期布局訊號；'
                    '但台股走勢並非完全跟隨美股，需搭配 NDC 景氣燈號雙重確認。'
                )
                # ── v19.183 D2（CLAUDE.md §2.3 防 lookahead）誠實揭露 ────────────
                # 事件判定需要「翻正後連 5 日不再翻負」才成立 → 站在翻正日當天
                # 沒有人知道這件事。且 T10Y2Y 是 FRED 日頻，D 日的值要等 D 日
                # 美股收盤後才發布（≈ D+1 04:00 台北），台股當天早已收盤。
                # 因此報酬一律從「確認日之後第一根 TWII K 棒」起算 ——
                # 這也是為什麼上表會有兩個日期欄。
                st.caption(
                    '🔒 **這條績效沒有偷看未來**：事件要「翻正後連 5 日不再翻負」才算數，'
                    '而這件事在翻正日當天無從得知；加上 FRED 的 T10Y2Y 當日值要等'
                    '美股收盤後才發布（台股早已收盤）。故 +6M/+12M/+18M 一律以'
                    '**「可進場日」＝ 確認日之後第一根加權指數 K 棒**的收盤價當進場價，'
                    '而非翻正日收盤。'
                )
    
        if _twd_df is not None and not _twd_df.empty:
            # v18.321：💵 現金流向群組 banner（與其他桶一致的分隔條，分組化收尾）
            from shared.macro_buckets import bucket_group_banner_html as _bgb_cf
            st.markdown(_bgb_cf('cashflow', 0), unsafe_allow_html=True)
            # v18.319：現金流向 Raw（三角交叉 + sliders）預設收合（要看才打開），
            #          比照基金面板「Raw data 縮起來」；互動內容不動。
            with st.expander("💵 熱錢深度監測 — 三角交叉（外資 × 匯率 × 背離）",
                             expanded=False):
                st.caption(
                    "上方「台幣升貶」訊號的深化版：把**外資買賣超**與**台幣匯率**"
                    "做交叉分析，找出「背離」時刻——例如台幣升值但外資沒買，"
                    "代表熱錢可能停泊匯市觀望，往往是行情前奏。"
                )
                try:
                    from src.ui.tabs import render_hot_money_section
                    render_hot_money_section(
                        _twd_df, FINMIND_TOKEN, key_prefix="tab_macro_hm")
                except Exception as _hme:
                    st.error(f"熱錢監測渲染失敗：[{type(_hme).__name__}] {_hme}")
    
    elif not cd:
        with _mkt_placeholder.container():
            st.info('📡 請點擊「🚀 一鍵更新全部數據」載入大盤數據')
    # ── ③ 資料到位後，回填紅綠燈佔位符（修復「未審先判」Bug）────
    # C1-E v18.291:走 section_inputs SSOT(對齊 C1-D 紅綠燈初次計算路徑)
    #
    # ⚠️ v19.183 D2:本段整包加上 `show_market_data` 閘門。修的是兩個問題 ——
    #
    # 【① 30 分鐘新鮮度閘門被架空(§2.4)】
    #   `section_traffic_light.render_traffic_light_top()` 刻意在快取超過 30 分鐘
    #   或刷新中時**不算燈號**,改在 placeholder 印「⏳ 燈號等待中（上次更新 45
    #   分鐘前，已過期）」。但本段原本**無條件**重算一次 `calc_traffic_light`
    #   並 `_render_traffic_light(_tl_placeholder, ...)` —— 用的是同一份過期
    #   session 資料,卻直接把那句警告蓋掉、換成一張自信滿滿的燈號卡。
    #   結果:那道閘門在「已載入過但快取過期」的每一次 rerun 都等於不存在。
    #   (do_refresh 路徑不受影響:tab_macro 在該路徑最後 `st.rerun()`,本函式
    #    根本跑不到;故加閘門後「資料到位後回填」的原始用途完全不受損。)
    #
    # 【② warroom 的 health 與 regime 來自不同次計算(§2.1)】
    #   本段的 `_wr_sum.update({...})` 只寫 primitives,**不寫**
    #   `effective_regime` / `light` / `regime_source`。而 `get_macro_state()`
    #   的快路徑優先讀 `effective_regime`(由 render_traffic_light_top 寫入)。
    #   兩次計算若輸入不同(例如跨 rerun 之間 jingqi_info 才補到),就會湊出
    #   「health_score 是新的、effective_regime 是舊的」這種混血 warroom。
    #   修法:本段真的要寫時,把同一次仲裁的三個 regime 欄位一併寫回,
    #   讓 warroom 內部恆為「同一次 calc_traffic_light 的完整快照」。
    if not show_market_data:
        # 燈號卡維持 render_traffic_light_top 印的等待訊息(§1:不拿過期資料
        # 冒充當日結論);同理不渲染建議持股油門與「為何這個顏色」——
        # 那兩者都是對「當前燈號」的說明,燈號都還沒亮就先解釋等於憑空捏造。
        return
    from src.services import load_section_inputs as _load_si_tl2
    _tl2_inp = _load_si_tl2(st.session_state)
    _tl2_mkt = _tl2_inp.mkt_info or {}
    _tl_final = calc_traffic_light(
        _tl2_mkt,
        _tl2_inp.jingqi_info or {},
        _tl2_inp.cl_data or {},
        _tl2_inp.li_latest,
    )
    _render_traffic_light(_tl_placeholder, _tl_final, _tl2_mkt)
    # v19.62 — 建議持股油門(姿態非開關):總經健康分 → 建議持股區間
    try:
        from src.ui.tabs.macro.section_traffic_light import render_position_throttle
        render_position_throttle(_tl_final)
    except Exception as _e_thr:
        print(f"[position_throttle] {type(_e_thr).__name__}: {_e_thr}")
    # v18.277 — 為何這個顏色?(展開講判讀規則 + 推導,for 新手)
    try:
        from src.ui.tabs import render_traffic_light_explainer
        render_traffic_light_explainer(_tl_final)
    except Exception as _e_exp:
        print(f"[macro_classroom/explainer] {type(_e_exp).__name__}: {_e_exp}")
    if _tl_final:
        # v19.170 P0-1 修 SSOT 破口:原本 `st.session_state['warroom_summary'] = {...}`
        # 整包覆寫,把 section_traffic_light 先寫入的 'throttle' key 抹掉 —— 下游
        # (頁頂常駐條 / 今日作戰室)讀不到 throttle 就 fallback 回粗略 80/50/20,
        # 正是稽核「同畫面 6 套持股建議」的成因之一。改為就地 update 保留既有 key。
        _wr_sum = st.session_state.get('warroom_summary')
        if not isinstance(_wr_sum, dict):
            _wr_sum = {}
        _wr_sum.update({
            'traffic_light': _tl_final['label'],
            'health_score':  _tl_final['health'],
            # ── C1 regime 三欄位契約(v19.183 D2 補齊)────────────────────────
            # `regime` 維持舊語意 = 趨勢面**輸入** raw `mkt_info['regime']`,
            # 供畫面揭露「被壓制的反向訊號」。⚠️ 它**不是**結論。
            # `effective_regime` / `light` / `regime_source` 才是本次仲裁的結論,
            # 三者與上面的 health_score 出自**同一次** `calc_traffic_light`,
            # 不會再出現「新 health 配舊 regime」的混血 warroom(§2.1)。
            # 缺值時退回 raw 而非捏 'neutral':`.get('regime')` 為 None 時
            # `get_macro_state()` 會走 arbiter 重算路徑,那是正確的降級。
            'regime': _tl2_mkt.get('regime'),
            'effective_regime': _tl_final.get('effective_regime'),
            'light':            _tl_final.get('light'),
            'regime_source':    _tl_final.get('regime_source'),
            'market_score':  _tl_final['score'],
            'jingqi_avg':    _tl_final['jqavg'],
            'leek_index':    _tl_final['leek'],
            'foreign_net_bn':_tl_final['fnet'],
            'futures_net':   _tl_final['fut_net'],
            'confidence_pct':_tl_final['conf'],
        })
        st.session_state['warroom_summary'] = _wr_sum
    
