"""src/ui/views/page_target.py — 新版（預設模式）「🎯 標的」單一頁（L5 UI；UI-T，2026-10-29）。

單一職責（客戶 A 規格 §4.2 原文）::

    目前市場裡有哪些值得研究的股票？

先看哪些產業有資金動能，再看候選公司，最後點進單一股票 —— 同一頁，不另設「查一檔」。

規格出處：客戶 2026-10-29 已核准的線框 `docs/vnext/NEWUI_D25_UIT_WIREFRAME_2026-10-29.md`（裁示 1A 2A 3A 4A 5A）
＋ `docs/vnext/d25_wireframes/target.html`（DEC-092）＋ DEC-099（合併 🔍 找標的＋🔬 查一檔，並移除 NAV-1 過渡切換）。

整頁順序（桌面與手機同序）::

    🎯 標的 ─ 問句
    ① ⬜ 資料狀態：尚未彙總
    ② 搜尋：[代碼] [🔍 載入完整分析]   ▸ 進階選項（判型・期間・均線）
    ③ 🤖 AI 投資總結：⬜ 尚未提供
    ④ 第一區 產業機會（矩陣；[🗺️ 載入板塊地圖]；熱力圖／泡泡圖降為展開區）
    ⑤ 第二區 候選標的（選股條件 → 候選表 → 選一檔＋🔍 查看此檔）
    ⑥ 第三區 單一股票（個股七區塊／ETF 版型／判不出型別灰卡）
    ⑦ ▸ 進階分析（多檔比較・仍未覆蓋的功能）

═══ 這個檔**不是**什麼 ═══════════════════════════════════════════════
- **不是新的計算或取數**：所有區塊呼叫 `page_find` / `page_inspect` 既有的 loader／builder（見 `_target_blocks`）。
- **不放「⚡ 需要處理」**（客戶 3A）：標的頁沒有既有規則來源，也不放假佔位。
- **不改 `page_find.py` / `page_inspect.py` / `ia_nav.PAGE_LABELS`**：legacy 模式（D2 側欄）仍獨立渲染舊兩頁；
  `app.py::_ia_view_find()` 依 session 旗標分流到本頁。

操作隔離：各區獨立 gate（單檔 form／選股 form／載入板塊地圖鈕／批次 form／查看此檔鈕），結果記在 session 到使用者下一次要求，
按其他區的鈕不會重呼叫本區的 L3；冷啟動零取數。各區以 `guard()` 逐區隔離（一區例外不吞掉其他區）。
"""
from __future__ import annotations

import streamlit as st

from src.ui.views import _target_blocks as B


def render_page_target() -> None:
    """🎯 標的（單一頁）。"""
    _session = st.session_state
    B.inject_css()   # 兩族 v2 卡面的樣式表每輪恰一次
    st.markdown(f"## {B.PAGE_TITLE}")
    st.caption(B.PAGE_SUBTITLE)
    st.caption(B.HEALTH_CHIP)
    B.guard("搜尋", lambda: B.render_search_form(_session))
    st.caption(B.AI_PLACEHOLDER)
    B.guard(B.ZONE1_TITLE, lambda: B.render_zone_industry(_session))
    B.guard(B.ZONE2_TITLE, lambda: B.render_zone_candidates(_session))
    # 第三區「為什麼值得看」讀第二區已記住的候選列（只讀、不取數；第二區沒跑成就是 None）。
    B.guard(B.ZONE3_TITLE, lambda: B.render_zone_single(_session, B.peek_screen_bundle(_session)))
    B.guard(B.ADVANCED_EXPANDER, lambda: B.render_advanced(_session))
