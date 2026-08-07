"""v18.277 — Stock 端總經原理小教室 + 紅綠燈判讀說明。

設計:對齊 Fund v19.124 macro_beginner_view.py 的「📚 原理小教室」,
針對 TW 股市專案調整(在地補充 TWSE/外資/PMI 國際源等)。

不做 Fund 的三層 toggle — Stock 架構末段才算 tl_final,不支援 early return。
改為:
  - 既有紅綠燈儀表板 → 附「📖 為何這個顏色?」expander 講判讀規則
  - 頁底永久 expander → 「📚 總經原理小教室」教 10 段核心概念

被 tab_macro.py 在 2 處呼叫:
  render_traffic_light_explainer(tl)  — 紅綠燈附近
  render_principle_classroom()        — 頁底

§3.3 SSOT
  - 引入 macro_helpers HEALTH_DEFENSE_THRESHOLD / BULL_MIN_SCORE
  - 文字教室為 user-facing 教學內容,無 metric magic number

§8 架構
  - L4 Render 級(本檔放 root,與 ui_widgets.py 同層)
  - 純 streamlit UI 渲染,無 I/O,無重邏輯
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

# v19.173 §3.3:健康評分權重一律從 SSOT 換算,**禁止**教室頁自己寫死百分比。
# 教訓來源:本檔原本寫死「景氣(40%) + 市場結構(40%) + 外資資金(20%)」,
# v19.102 校準把 SSOT 改成 0.6/0.4/0 之後教學頁沒跟著改 → 文件與程式漂移。
# 改成 derive,權重再校準時教室頁自動同步,不會再說謊。
from shared.signal_thresholds import (
    HEALTH_FNET_BONUS,
    HEALTH_WEIGHT_JQ,
    HEALTH_WEIGHT_SCORE,
)
# 從 SSOT 取門檻,讓教室講解「為何 35 / 4 是切點」時對得上 production 行為
from src.compute.macro import BULL_MIN_SCORE, HEALTH_DEFENSE_THRESHOLD

_JQ_PCT = round(HEALTH_WEIGHT_JQ * 100)      # 旌旗指數(廣度)佔比 → 60
_SC_PCT = round(HEALTH_WEIGHT_SCORE * 100)   # 大盤評分佔比 → 40
_FNET_BONUS = HEALTH_FNET_BONUS              # 外資加分「分數」(不是佔比) → 0

# ── 校準 provenance(說明文字用,非門檻;來源 MACRO_HEALTH_WEIGHT_PROPOSAL.md）──
# 教室頁要說服讀者「0 不是 bug」就必須把證據強度講出來,故一併具名常數化,
# 避免下次有人只改敘述、忘了證據對不對得上。
_CAL_N = 4748                 # v19.102 校準樣本數(2006~2026 交易日)
_CAL_AUC = 0.753              # 驗證集 AUC(overfit_flag=False)
_FNET_BONUS_LEGACY = 20       # v19.102 校準**前**的外資加分,歸零前的舊值


# ════════════════════════════════════════════════════════════════
# 紅綠燈判讀說明 — 解釋當前顏色為何是這樣
# ════════════════════════════════════════════════════════════════

def render_traffic_light_explainer(tl: Optional[dict]) -> None:
    """在紅綠燈儀表板附近渲染「📖 為何這個顏色?」expander。

    讀現場 tl dict(已含 color/health/score/defense/regime 等),
    回推目前燈號被哪一條 rule 觸發,白話解釋給新手。
    """
    if not tl:
        return

    _color = tl.get('color', '')
    _label = tl.get('label', '—')
    _health = tl.get('health', 0)
    _score = tl.get('score', 0)
    # ── C1 三欄位契約（v19.183 D2 修正本檔的誤用）──────────────────────────────
    # 舊碼只取 `tl.get('regime', 'neutral')`，然後拿它去**解釋燈號為什麼是這個顏色**。
    # 那是拿「輸入」去解釋「結論」，兩者可以完全相反：
    #   決策樹分支 1/2（外資期貨大空單 / 健康分跌破門檻）會**直接覆蓋**趨勢面 regime，
    #   於是「趨勢 bull、燈號 🔴 空頭防禦」的日子，本 expander 會印
    #   「市場 regime: bull」，讀者只會更困惑（這正是 C1 稽核點名最刺眼的一處）。
    # 現在分開顯示：`regime` = 趨勢面**輸入**；`effective_regime` = 燈號的**結論**。
    # 另外 `.get(..., 'neutral')` 的預設值本身也違反 §1（把「沒有」偽裝成「震盪」），
    # 一併改為 None → 顯示「— 未取得」。
    _trend_regime = tl.get('regime')
    _eff_regime = tl.get('effective_regime')
    _regime_source = tl.get('regime_source')
    _defense = tl.get('defense', False)
    # ⚠️ v19.177 P1-B:`fut_net` 現在可能是 **None**(先行指標未載入)。
    # 舊碼 `tl.get('fut_net', 0)` 的預設**只在 key 不存在時生效** —— key 在、
    # 值為 None 時原樣拿到 None,下方 `{_fut_net:+,.0f}` 立刻拋 TypeError,
    # 而 caller(`section_state.py:501`)包了 try/except → 整個「📖 為何這個顏色」
    # expander **靜默消失**。§1:降級要看得見,不可靜默,更不可回頭捏 0(那等於
    # 宣告「外資期貨淨部位是 0」)。
    _fut_net = tl.get('fut_net')
    _conf = tl.get('conf', 0)

    with st.expander("📖 為何紅綠燈是現在這個顏色?(展開看判讀規則 + 推導)", expanded=False):
        st.markdown("#### 🧮 目前數據")
        st.markdown(
            f"- 健康評分:**{_health}** / 100"
            f"  *(切點:{HEALTH_DEFENSE_THRESHOLD} → 防禦級)*"
        )
        st.markdown(
            f"- 市場分數:**{_score}** / 6"
            f"  *(切點:多頭需 ≥ {BULL_MIN_SCORE})*"
        )
        st.markdown(
            f"- 趨勢面 regime(**輸入**,來自 `market_regime()` 的均線判定):"
            f"**{_trend_regime or '— 未取得'}**"
        )
        st.markdown(
            f"- 生效 regime(**結論**,燈號就是由它決定):"
            f"**{_eff_regime or '— 未取得'}**"
        )
        if _trend_regime and _eff_regime and str(_trend_regime).lower() != _eff_regime:
            st.caption(
                f"⚖️ 這兩個值**不一樣是正常的**:趨勢面說「{_trend_regime}」,"
                f"但下面第 1/2 條(總經惡化)優先命中並覆蓋了它 → 最終「{_eff_regime}」。"
                "§2.1「衝突時上層贏」——不平均、不折衷。"
            )
        st.markdown(
            f"- 外資期貨淨部位:**{_fut_net:+,.0f}** 口" if _fut_net is not None
            else "- 外資期貨淨部位:**— 未取得**（先行指標未載入；"
                 "此時防禦判定的期貨條件視為「無法判斷」，不會觸發也不會抑制）"
        )
        st.markdown(f"- 資料信心度:**{_conf}%**")

        st.markdown("")
        st.markdown("#### 🎯 判讀規則(由上而下檢查,先觸發者勝)")

        # 動態解釋目前是哪一條觸發
        # B6-a v19.181:「3 萬口」原為手打 —— 改吃 SSOT
        # `FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD`(= macro_helpers._defense 真正用的
        # 那一個常數),常數調整時本行自動跟著動,不會再變成過期文案(§3.3)。
        from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
        # ── v19.183 D2：改讀 `regime_source`，不再自己把決策樹重寫一次 ────────────
        # 【原缺陷】舊碼在這裡**重新實作**了一次判定（`_regime == 'bull' and
        #   _score >= BULL_MIN_SCORE` 等），拿 raw 趨勢 regime 去推「哪一條觸發」。
        #   兩個問題：
        #     ① 第二套實作 = 必然漂移。arbiter 的分支順序 / 門檻一改，這裡不會跟。
        #     ② 它用的輸入本來就錯（raw regime 是輸入不是結論，見上方註解），
        #        「總經惡化覆蓋技術面多頭」那天會標錯行。
        # 【修法】`calc_traffic_light` 已經把「哪一條分支生效」寫成
        #   `regime_source`（`shared.regime_arbiter.SOURCE_*`）——直接查表比對即可，
        #   判定與解釋從此保證同源（§2.1）。
        #   舊 session 的 tl dict 沒有這個 key → 退回原本的推導，並明講是推測值。
        from shared import regime_arbiter as _RA_cls
        _rules = [
            (
                _RA_cls.SOURCE_DEFENSE_FUTURES,
                "🔴 **空頭防禦**（外資期貨）",
                f"市場分數 < {_RA_cls.DEFENSE_MAX_MARKET_SCORE}"
                f" 且外資期貨淨空單 > {FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD:,} 口",
                _defense,
            ),
            (
                _RA_cls.SOURCE_DEFENSE_HEALTH,
                "🔴 **空頭防禦**（健康分）",
                f"健康評分 < {HEALTH_DEFENSE_THRESHOLD}",
                (not _defense) and _health < HEALTH_DEFENSE_THRESHOLD,
            ),
            (
                _RA_cls.SOURCE_BULL_SCORE,
                "🟢 **多頭積極**",
                f"趨勢 regime = bull AND 市場分數 ≥ {BULL_MIN_SCORE}",
                str(_trend_regime).lower() == 'bull' and _score >= BULL_MIN_SCORE,
            ),
            (
                _RA_cls.SOURCE_BEAR_TREND,
                "🔴 **保守防禦**",
                "趨勢 regime ∈ (caution, bear)",
                str(_trend_regime).lower() in ('caution', 'bear'),
            ),
            (
                _RA_cls.SOURCE_NEUTRAL_FALLTHROUGH,
                "🟡 **震盪整理**",
                "其他全部情境(預設)",
                True,
            ),
        ]
        _fallback_idx = None
        for _i, (_src, _lbl, _cond, _guess) in enumerate(_rules):
            if _guess and _fallback_idx is None:
                _fallback_idx = _i
        _hit_idx = None
        if _regime_source:
            _hit_idx = next((_i for _i, _r in enumerate(_rules)
                             if _r[0] == _regime_source), None)
        _is_guess = _hit_idx is None
        if _is_guess:
            _hit_idx = _fallback_idx
        for _i, (_src, _lbl, _cond, _guess) in enumerate(_rules):
            _mark = "👈 **目前觸發**" if _i == _hit_idx else ""
            st.markdown(f"{_i+1}. {_lbl} — `{_cond}` {_mark}")
        if _is_guess:
            st.caption(
                "ℹ️ 這次的「目前觸發」是由現場數值**回推**的（本輪燈號沒帶 "
                "`regime_source`，多半是舊的 session 快取）。按一次"
                "「🚀 一鍵更新全部數據」後就會改讀決策樹自己回報的生效分支。"
            )

        st.markdown("")
        st.markdown("#### 🎓 背後原理")
        # v19.173 誠實化：原文寫「景氣(40%) + 市場結構(40%) + 外資資金(20%)」是
        # v19.102 校準**前**的舊權重，且把 jqavg 誤稱為「景氣」。現行 SSOT
        # (shared/signal_thresholds.py) 為 HEALTH_WEIGHT_JQ=0.6 /
        # HEALTH_WEIGHT_SCORE=0.4 / HEALTH_FNET_BONUS=0，公式見
        # macro_helpers.compute_macro_health:102-106。
        # 同批修正另兩處漂移：①「市場分數(0-6)」的來源不是 daily checklist 而是
        # market_regime()，分母基本 4、ad_ratio/m1b_m2_gap 有傳才升 5-6
        # (market_strategy.py:151-155)；② regime 只會回 bull/neutral/bear
        # 三態，且由 MA120 連三日 + 斜率單獨決定（ADL/漲跌家數是進 score，不進
        # regime）—— 'caution' 是 calc_traffic_light:144 的死分支，永不觸發。
        # ── P0-C 定名 + 反捏造（2026-08-05）──────────────────────────
        # 原文「旌旗指數(站上 20MA 家數比＝市場廣度)」兩個錯：
        #   ① **捏造**（§1）：全站沒有任何一行在算「站上 20MA 的家數比」。
        #      grep `站上|above_ma|pct_above`：tab_stock.py:563-565 的 _above_ma20
        #      是單檔個股比自己的均線；daily_data_fetchers.py:445 的 adl_ma20 是
        #      「ADL 累積線的 MA20」。兩者都不是「站上均線的股票家數比例」。
        #      真值：jingqi_calc.py:43 = ad_ratio.tail(5).mean()，即
        #      **上漲佔比的 5 日均**。
        #   ② **撞名**：「市場廣度」是家族統稱（上漲佔比 / 旌旗 / AD 值 / ADL），
        #      同時名詞表又寫「騰落指標＝市場廣度」→ 跨 tab 對照必然打結。
        # 文案不在本檔手寫，取 ui_widgets.BREADTH_JINGQI（名詞定義單一出處）。
        from src.ui.render.ui_widgets import BREADTH_FAMILY_NAME, BREADTH_JINGQI
        st.markdown(
            "TW 股市紅綠燈用**三大支柱**綜合判讀:\n"
            f"- **健康評分**(0-100):{BREADTH_JINGQI.canonical}"
            f"({BREADTH_JINGQI.formula}；屬**{BREADTH_FAMILY_NAME}**類,"
            f"不是景氣指標){_JQ_PCT}% + 大盤評分 {_SC_PCT}%"
            f",外資資金加分項 **+{_FNET_BONUS} 分**(校準後歸零,見下一段),"
            f"低於 {HEALTH_DEFENSE_THRESHOLD} = 系統性風險浮現,優先保護資金\n"
            "- **市場分數**:由 `market_regime()` 對均線/外資/廣度/資金活水打分,"
            "滿分隨資料齊全度浮動(基本 4;ADL、M1B-M2 有值才升 5-6),"
            f"≥ {BULL_MIN_SCORE} 才允許多頭策略\n"
            "- **regime 分類**:只看 MA120 連三日站上/跌破 + 均線斜率 → "
            "bull / neutral / bear 三態(廣度、漲跌家數是進「市場分數」,不進 regime)\n\n"
            "**為何優先看防禦?** 在熊市買進的代價遠大於在牛市少賺。"
            "系統設計成「**寧可錯過,不可錯買**」的保守風控。"
        )

        st.markdown("")
        st.markdown("#### 🧪 為什麼「外資資金」那一項被校準成 0 分?")
        st.markdown(
            f"這不是漏寫的 bug,是**校準後的明示歸零**。v19.102 拿 2006–2026 共 "
            f"{_CAL_N:,} 個交易日的真實資料,去擬合「哪些因子預測得到未來 20 日回撤 "
            f"≥8%」,驗證集 AUC = {_CAL_AUC}(overfit_flag=False)。結果:\n"
            f"- 旌旗指數 vs 大盤評分的相對重要性 ≈ 60:40 → 權重定為 "
            f"{_JQ_PCT}% / {_SC_PCT}%\n"
            f"- 外資淨買超的擬合權重 ≈ +0.0006/億,方向甚至微偏反 —— 也就是"
            f"「知道外資買了多少」對預測回撤幾乎**沒有增益** → 原本無條件 "
            f"+{_FNET_BONUS_LEGACY} 分(占滿分五分之一)的加分項歸零為 "
            f"+{_FNET_BONUS} 分\n\n"
            "**這裡可以學到的事**:一個指標「聽起來很重要」跟「真的能預測」是兩回事。"
            f"外資動向天天上新聞,但把它加進這條公式只是讓分數整體虛高 "
            f"{_FNET_BONUS_LEGACY} 分、拉不開好壞天的差距。常數與公式形狀刻意保留"
            "(沒有把該項刪掉),未來若重跑校準發現它有用,改一個數字就能接回來。\n\n"
            "⚠️ 想看外資怎麼動,請看**籌碼桶**的外資現貨/期貨燈號 —— "
            "那裡是單獨判讀,不會被這條公式吃掉。"
        )
# ════════════════════════════════════════════════════════════════
# v18.281 — 原理教室(_PRINCIPLE_CHAPTERS + render_principle_classroom)
# 已移至 tab_edu.py(合併成單一「系統說明書」)。
# 本檔現僅保留 render_traffic_light_explainer(總經 Tab 即時診斷 widget)。
# 向後相容:若有 caller 仍 import render_principle_classroom,從 tab_edu re-export。
# ════════════════════════════════════════════════════════════════
def render_principle_classroom() -> None:  # noqa: D401 — 向後相容 shim
    """已搬至 tab_edu(系統說明書)。保留 shim 避免舊 caller 壞掉。"""
    from src.ui.tabs import render_principle_classroom as _rpc
    _rpc()
