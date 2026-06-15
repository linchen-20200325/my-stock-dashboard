"""v18.204 I4：個股 ↔ 總經 regime 跨 Tab 聯動（鏡像 Fund v19.64 I1）。

在個股分析 Tab 顯示大盤總經 regime 背景（多空 + 建議持股 + 市場廣度），
讓 user 看個股時不忘系統性風險背景 —「大盤空頭時，再強的個股也難完全抗
系統性風險」。

讀總經 Tab 已算好的 session_state（個股 Tab 未載入總經 → 容錯提示）：
  - mkt_info：market_strategy.get_market_assessment 結果
    {regime:'bull'/'neutral'/'bear', label, score, exposure_pct,
     index_below_ma5, foreign_net, ...}
  - jingqi_info：市場廣度 regime {regime, label, color, ...}（optional）
零新 IO（純 reuse 總經 Tab 結果），屬「跨 Tab 訊號聯動」系列。
"""
from __future__ import annotations

import streamlit as st


def render_macro_stock_backdrop(session_state) -> None:
    """渲染大盤總經背景 banner（純顯示，零副作用，零新 IO）。"""
    _mkt = session_state.get("mkt_info") or {}
    if not isinstance(_mkt, dict) or not _mkt.get("regime"):
        st.caption("🧭 載入「總經」Tab 後，這裡會顯示大盤 regime 背景（多空 / 建議持股）")
        return

    _regime = str(_mkt.get("regime", "neutral"))
    _label = str(_mkt.get("label", "") or _regime)
    _exp = str(_mkt.get("exposure_pct", "") or "")
    _below5 = _mkt.get("index_below_ma5")
    # v18.210 K4：走 shared/colors SSOT（traffic-light hex 散落 15 檔 110 處統一收納）
    from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED
    _border = {"bull": TRAFFIC_GREEN, "neutral": TRAFFIC_YELLOW,
               "bear": TRAFFIC_RED}.get(_regime, "#58a6ff")

    _head = f"🧭 <b>大盤總經背景</b>（來自「總經」Tab）：<b>{_label}</b>"
    if _exp:
        _head += f"　·　建議持股 <b style='color:#c9d1d9'>{_exp}</b>"
    if _below5 is True:
        _head += "　·　指數 &lt; MA5"
    elif _below5 is False:
        _head += "　·　指數 &gt; MA5"

    _jq = session_state.get("jingqi_info") or {}
    _jq_line = ""
    if isinstance(_jq, dict) and _jq.get("label"):
        _jq_line = f"<br/><span style='color:#888'>市場廣度：{_jq.get('label')}</span>"

    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
        f"color:#8b949e;line-height:1.7'>{_head}{_jq_line}</div>",
        unsafe_allow_html=True,
    )

    if _regime == "bear":
        st.caption(
            "🔴 大盤空頭 → 個股操作宜保守 / 減碼，即使基本面強的股也難完全"
            "抗系統性風險（建議降持股比例）"
        )
    elif _regime == "bull":
        st.caption("🟢 大盤多頭 → 順勢操作環境較友善，仍須個股基本面把關")
