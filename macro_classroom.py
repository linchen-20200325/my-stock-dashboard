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

# 從 SSOT 取門檻,讓教室講解「為何 35 / 4 是切點」時對得上 production 行為
from macro_helpers import BULL_MIN_SCORE, HEALTH_DEFENSE_THRESHOLD


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
    _regime = tl.get('regime', 'neutral')
    _defense = tl.get('defense', False)
    _fut_net = tl.get('fut_net', 0)
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
        st.markdown(f"- 市場 regime:**{_regime}**")
        st.markdown(f"- 外資期貨淨部位:**{_fut_net:+,.0f}** 口")
        st.markdown(f"- 資料信心度:**{_conf}%**")

        st.markdown("")
        st.markdown("#### 🎯 判讀規則(由上而下檢查,先觸發者勝)")

        # 動態解釋目前是哪一條觸發
        _matched_idx = None
        _rules = [
            (
                "🔴 **空頭防禦**",
                f"健康評分 < {HEALTH_DEFENSE_THRESHOLD} OR(市場分數 < 2 且外資期貨大空單 > 3 萬口)",
                _defense or _health < HEALTH_DEFENSE_THRESHOLD,
            ),
            (
                "🟢 **多頭積極**",
                f"regime = bull AND 市場分數 ≥ {BULL_MIN_SCORE}",
                _regime == 'bull' and _score >= BULL_MIN_SCORE,
            ),
            (
                "🔴 **保守防禦**",
                "regime ∈ (caution, bear)",
                _regime in ('caution', 'bear'),
            ),
            (
                "🟡 **震盪整理**",
                "其他全部情境(預設)",
                True,
            ),
        ]
        for _i, (_lbl, _cond, _matched) in enumerate(_rules):
            _mark = "👈 **目前觸發**" if (_matched and _matched_idx is None) else ""
            if _matched and _matched_idx is None:
                _matched_idx = _i
            st.markdown(f"{_i+1}. {_lbl} — `{_cond}` {_mark}")

        st.markdown("")
        st.markdown("#### 🎓 背後原理")
        st.markdown(
            "TW 股市紅綠燈用**三大支柱**綜合判讀:\n"
            "- **健康評分**(0-100):景氣(40%)+ 市場結構(40%)+ 外資資金(20%),"
            "低於 35 = 系統性風險浮現,優先保護資金\n"
            "- **市場分數**(0-6):由 6 個 daily checklist 指標投票,≥ 4 才允許多頭策略\n"
            "- **regime 分類**:結合大盤走勢 + ADL + 漲跌家數 → bull/neutral/caution/bear\n\n"
            "**為何優先看防禦?** 在熊市買進的代價遠大於在牛市少賺。"
            "系統設計成「**寧可錯過,不可錯買**」的保守風控。"
        )
# ════════════════════════════════════════════════════════════════
# v18.281 — 原理教室(_PRINCIPLE_CHAPTERS + render_principle_classroom)
# 已移至 tab_edu.py(合併成單一「系統說明書」)。
# 本檔現僅保留 render_traffic_light_explainer(總經 Tab 即時診斷 widget)。
# 向後相容:若有 caller 仍 import render_principle_classroom,從 tab_edu re-export。
# ════════════════════════════════════════════════════════════════
def render_principle_classroom() -> None:  # noqa: D401 — 向後相容 shim
    """已搬至 tab_edu(系統說明書)。保留 shim 避免舊 caller 壞掉。"""
    from tab_edu import render_principle_classroom as _rpc
    _rpc()
