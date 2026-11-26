"""market 頁 view：只渲染 PageVM。

版面（Wireframes §2／Freeze §0.1.6／§16.1-M；P2 起依客戶 2026-11-04 (19)／DEC-133）：
標題 → [今日結論 → 市場目前狀態 → Risk Cap → 是否需要行動 → 下一步 → 主 CTA] → **緊接**「今日主要風險」（L1，⛔ 被插隊）
→ 🇹🇼 台股日 K 主圖／**誠實空槽**＋一行 SPEC →〔Real 日 K 才有：圖外原生 `st.radio`「期間」20／60 日〕→（B-UI2-DELTA-BELOW）今日變化（唯讀、恆不可比較）→ 核心指標卡 → 🤖 OneBrain Outlook（內容不變，只改位置）→ 其餘區塊。
（Issue #1108 方向 B 起 OneBrain 移到指標卡之後；DEC-133 G-3 的舊順序「OneBrain → Primary → 指標卡」被 DEC-157 有意識取代，見 docs/DECISIONS.md。）
（Active Contract §3.1：📊 整頁不承載完整 evidence 摺疊——P3 起 L2／L3 evidence 區塊不渲染，VM 完整保留。）
桌機（≥769px）由 CSS 把 狀態／Risk Cap／今日主要風險 排成三 tile（見 shell/css.py）；手機堆疊。

P2 實作形態（線框 F-5 (ii)）：OneBrain 取 VM 既有 L1 section 原樣渲染（`section_l1_html`），只是畫的位置前移；
`render_sections(skip={"onebrain"})` 仍被呼叫（其餘區塊與 L2／L3 呈現政策不變，`test_render_policy_guard_has_teeth` 保有牙）。
空槽與 SPEC 全在 view 內以既有字樣／TWII 卡 freshness 組成；VM／canonical／scenarios 0 變更。

期間切換（2026-11-26；#1199 留言 7186846291／7186895108 客戶 R16 具名授權）：VM 帶日 K 事實（＝Real-data Preview）時，圖（含圖例、圖內附註、
資料日）之後、「今日變化」之前，加一組**圖外**原生 `st.radio`（horizontal，列標籤「期間」，選項「20 日／60 日」，預設 20；R20 客戶取代前版：120 日另案）。
本檔只畫 widget、不讀資料；所選值由殼（`shell/app.py`）讀 session 後傳給 feed（`read_real_snapshot(days=)`）。
FAKE（VM 無日 K 事實＝誠實空槽）與其他頁不渲染本 widget。⛔ 252／縮放／捲動／降採樣；⛔ 圖 SVG／HTML 內任何控制項。
"""
from __future__ import annotations

from html import escape

import streamlit as st

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import delta_below_html, kbar_chart_html, market_l1_html, primary_slot_html
from src.ui2.views._page import _md, render_cards, render_sections, render_title, section_l1_html

ONEBRAIN_SECTION_ID = "onebrain"
TWII_CARD_ID = "twii"

#: 📊 日 K「期間」radio（純 UI 狀態；`ui2_` 前綴＋模組頂層字串常數，G9）。殼（`shell/app.py`）以同值常數讀取所選值（測試釘相等）。
KEY_KBAR_DAYS = "ui2_kbar_days"
KEY_KBAR_DAYS_BOX = "ui2_kbar_days_box"     # container key（CSS／量測錨點 `.st-key-ui2_kbar_days_box`；非 session_state）
#: 核准選項（客戶 R20 具名授權 #1199 留言 7191058929：全裝置 20／60 日；⛔ 120 另案、⛔ 252）；第一個＝預設。與 feed／canonical 各一份，測試釘相等。
KBAR_DAY_OPTIONS: tuple[int, ...] = (20, 60)
KBAR_DAYS_DEFAULT = KBAR_DAY_OPTIONS[0]
KBAR_DAYS_LABEL = "期間"


def kbar_days_label(days: int) -> str:
    """選項標籤（只有核准字串「20 日」「60 日」）。"""
    return f"{days} 日"


def _kbar_period_picker() -> None:
    """圖外原生 radio（horizontal；原生 radiogroup／checked＝選中態語意、方向鍵切換、Tab 進出）。value＝int 天數。"""
    with st.container(key=KEY_KBAR_DAYS_BOX):
        st.radio(KBAR_DAYS_LABEL, KBAR_DAY_OPTIONS, key=KEY_KBAR_DAYS, horizontal=True, format_func=kbar_days_label)


def render(vm: PageVM) -> None:
    render_title(vm)
    _md(market_l1_html(vm.context.first_screen, vm.context.main_risk))
    # Issue #1108（方向 B）：台股 Primary（日 K 主圖／誠實空槽）→ 核心指標卡 → 🤖 OneBrain Outlook（內容不變，只動位置）。
    # 台股 Primary 誠實空槽＋一行 SPEC（來源／資料日＝TWII 卡 freshness）。
    # Issue #1099 PR-2（DEC-156）：VM 帶日 K 事實（Real-data Preview）時，同一位置改畫日 K 主圖（含灰／紅誠實狀態）；
    # 沒有日 K 事實（FAKE 示意軸）→ 照舊誠實空槽（⛔ FAKE K 棒）。
    twii = next((c for c in vm.context.cards if c.card_id == TWII_CARD_ID), None)
    _md(kbar_chart_html(vm.context.kbar) if vm.context.kbar is not None else primary_slot_html(twii))
    if vm.context.kbar is not None:       # 期間切換：只在日 K 事實存在時（Real；含紅／灰態——整窗錯誤時仍可切）；FAKE／空槽沒有
        _kbar_period_picker()
    # B-UI2-DELTA-BELOW（D1＝BELOW）：「今日變化」（唯讀、恆不可比較）在 Primary 之後、核心指標卡之前；位置在量測錨點之下，不影響 L1／Primary 的首屏餘裕。
    if vm.context.delta is not None:
        _md(delta_below_html(vm.context.delta))
    render_cards(vm)
    onebrain = next((s for s in vm.context.sections if s.section_id == ONEBRAIN_SECTION_ID and s.level == "L1"), None)
    if onebrain is not None:
        _md(f'<div class="ui2-m-onebrain" data-ui2-l1="onebrain">{section_l1_html(onebrain)}</div>')
    render_sections(vm, skip={ONEBRAIN_SECTION_ID} if onebrain is not None else frozenset())
