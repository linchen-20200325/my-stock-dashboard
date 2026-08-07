"""v18.204 I4：個股 ↔ 總經 regime 跨 Tab 聯動（鏡像 Fund v19.64 I1）。

在個股分析 Tab 顯示大盤總經 regime 背景（多空 + 建議持股 + 市場廣度），
讓 user 看個股時不忘系統性風險背景 —「大盤空頭時，再強的個股也難完全抗
系統性風險」。

讀總經 Tab 已算好的 session_state（個股 Tab 未載入總經 → 容錯提示）：
  - mkt_info：market_strategy.get_market_assessment 結果
    {regime:'bull'/'neutral'/'bear', label, score,
     index_below_ma5, foreign_net, ...}
    ⚠️ v19.170 P0-1：**持股% 不從這裡取**，一律走
    `allocation_service.get_allocation()`（全站唯一持股 SSOT）。
  - jingqi_info：**旌旗指數** regime {regime, label, color, source, ...}（optional）
    ⚠️ P0-C 定名：舊註解寫「市場廣度 regime」——「市場廣度」是家族統稱
    （含 上漲佔比 / 旌旗指數 / AD 值 / 騰落指標 ADL 四個量），不是這一個
    數字的名字。旌旗指數 = 上漲佔比的 5 日均，定義見
    `src/ui/render/ui_widgets.py` BREADTH_TERMS。
零新 IO（純 reuse 總經 Tab 結果），屬「跨 Tab 訊號聯動」系列。
"""
from __future__ import annotations

import streamlit as st


def render_macro_stock_backdrop(session_state) -> None:
    """渲染大盤總經背景 banner（純顯示，零副作用，零新 IO）。"""
    # ── D1 v19.185（C1 接線 · §1 Fail Loud）────────────────────────────────
    # 原碼直讀 `mkt_info['regime']`（趨勢面**輸入**）並補 default `'neutral'`。
    # 兩個後果：
    #  (a) 健康分跌破防禦門檻的那天，總經頁燈號卡印 🔴 空頭防禦，這條 banner 仍照
    #      raw regime 印「🟢 大盤多頭 → 順勢操作環境較友善」—— 同一天兩個相反結論；
    #  (b) 未評估時 default 'neutral' 讓 banner 直接宣告「震盪」。
    # 改吃全站唯一仲裁點 get_macro_regime()（與燈號卡、置底常駐條同一次判定）。
    from src.services.allocation_service import get_macro_regime
    _reg = get_macro_regime()
    if not _reg.get("is_loaded"):
        st.caption("🧭 載入「總經」Tab 後，這裡會顯示大盤 regime 背景（多空 / 建議持股）")
        return

    _mkt = session_state.get("mkt_info") or {}
    if not isinstance(_mkt, dict):
        _mkt = {}
    _regime = str(_reg.get("regime") or "unknown")
    # label 優先用燈號卡的中文 label（同一次仲裁的產物）；沒有才退回 mkt_info 的
    # 趨勢面 label —— 但那是**輸入**的敘述，故加註來源避免被讀成結論。
    _label = str(_reg.get("traffic_light") or "").strip()
    if not _label:
        _raw_label = str(_mkt.get("label", "") or "").strip()
        _label = f"{_raw_label}（趨勢面）" if _raw_label else _regime
    # v19.170 P0-1:建議持股改讀全站唯一 SSOT(get_allocation),不再讀
    # mkt_info['exposure_pct'](market_strategy 自算的 80/50/20,與
    # 🎚️ 建議持股油門 打架)。§1 Fail Loud:未評估時 range_text='--' → 不顯示。
    from src.services.allocation_service import get_allocation
    _alloc = get_allocation()
    _exp = _alloc.range_text if _alloc.is_loaded else ""
    _below5 = _mkt.get("index_below_ma5")
    # v18.210 K4：走 shared/colors SSOT（traffic-light hex 散落 15 檔 110 處統一收納）
    from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED
    # D1 v19.185：補 'caution'（canonical 五態之一，原本落到藍色 "#58a6ff"，
    # 看起來像「有另一種狀態」而不是「保守」）。
    _border = {"bull": TRAFFIC_GREEN, "neutral": TRAFFIC_YELLOW,
               "caution": TRAFFIC_RED, "bear": TRAFFIC_RED}.get(_regime, "#58a6ff")

    _head = f"🧭 <b>大盤總經背景</b>（來自「總經」Tab）：<b>{_label}</b>"
    if _exp:
        _head += f"　·　建議持股 <b style='color:#c9d1d9'>{_exp}</b>"
    if _below5 is True:
        _head += "　·　指數 &lt; MA5"
    elif _below5 is False:
        _head += "　·　指數 &gt; MA5"

    # ── P0-C 定名（2026-08-05）─────────────────────────────────────
    # 原本印「市場廣度：{label}」，但 label 來自 `jingqi_info` —— 也就是拿
    # **家族統稱**當標籤去印**單一成員**的值。同一時間名詞表說「市場廣度＝
    # 騰落指標 ADL」，讀者跨 tab 對照必然打結。
    # 定名後：「市場廣度」只當家族/章節統稱，單一數值一律用正式名（旌旗指數）。
    # 名詞定義單一出處：ui_widgets.BREADTH_JINGQI。
    from src.ui.render.ui_widgets import BREADTH_JINGQI

    _jq = session_state.get("jingqi_info") or {}
    _jq_line = ""
    if isinstance(_jq, dict) and _jq.get("label"):
        # §1：備援 / 代理來源要看得見（'ADL' 為主源；'大盤估算' / 'TWSE即時' 為代理）
        _jq_src = str(_jq.get("source") or "")
        _jq_note = f"（{_jq_src} 代理）" if _jq_src and _jq_src != "ADL" else ""
        _jq_line = (f"<br/><span style='color:#888'>"
                    f"{BREADTH_JINGQI.canonical}：{_jq.get('label')}{_jq_note}</span>")

    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
        f"color:#8b949e;line-height:1.7'>{_head}{_jq_line}</div>",
        unsafe_allow_html=True,
    )

    if _regime in ("bear", "caution"):
        st.caption(
            "🔴 大盤空頭 → 個股操作宜保守 / 減碼，即使基本面強的股也難完全"
            "抗系統性風險（建議降持股比例）"
        )
    elif _regime == "bull":
        st.caption("🟢 大盤多頭 → 順勢操作環境較友善，仍須個股基本面把關")
