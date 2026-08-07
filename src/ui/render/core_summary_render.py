"""src/ui/render/core_summary_render.py — 核心總表渲染(L4 Render,E1 v19.185)。

職責一句話
----------
吃一個 `shared.core_summary.CoreSummary` → 吐畫面。**零 I/O、零 session_state
讀取、零判定邏輯**。

為什麼這一層一個說明字串都不准自己寫
------------------------------------
`shared/allocation_decision.py:82-96` 記錄的事故:同一個檔案裡 `range_text` 有
「lo == hi 就只印一個數字」的收斂邏輯,`build_allocation_decision` 組 drivers 時
卻另用 raw f-string 拼區間 → 線上印出「→ 20–20%」。
**只要有第二個地方組同一句話,兩邊遲早會不一致。**

因此本檔的規則是:每一格的燈號 / 數字 / 說明,全部取自 `KpiCell`
(`cell.light` / `cell.value_text` / `cell.display_text` / `cell.explain`),
UI 端只負責排版與跳脫。本檔唯一自己寫的文字是**與資料無關的靜態圖例**
(「⬜ = 未評估 ≠ 沒問題」那一行)。

分層(§8.2)
-----------
L4 Render:import `shared.*`(L0)+ streamlit。**不** import 任何 L1 fetcher、
不 import L5、不讀 session_state(資料一律由 caller 傳入)。
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

from shared.colors import TRAFFIC_NEUTRAL, TRAFFIC_ORANGE, emoji_to_hex
from shared.core_summary import CoreSummary, KpiCell, STATUS_FAILED, STATUS_UNKNOWN

# ❌(取數失敗)不在 traffic-light 四色表內,另給一色;其餘一律走 shared.colors SSOT。
_FAILED_HEX: str = '#f778ba'


def _hex(cell: KpiCell) -> str:
    """cell → 邊框/文字色。失敗態獨立色,避免與「未評估」的灰混淆。"""
    if cell.status == STATUS_FAILED:
        return _FAILED_HEX
    if cell.light == '🟠':
        # `position_throttle` 的「轉守」用 🟠，不在 traffic-light 四色表內。
        # 不補這條的話它會被 emoji_to_hex 退成灰 → 畫面上與「⬜ 未評估」同色，
        # 使用者分不出「已判定為轉守」和「還沒算」（§1 三態必須可辨識）。
        return TRAFFIC_ORANGE
    return emoji_to_hex(cell.light)


def _esc(text) -> str:
    """最小化 HTML 逸出(對齊 `data_freshness.staleness_badge_html` 的做法)。

    `explain` 內可能含上游 fetcher 的錯誤原文 / cap reason,直接塞進 HTML
    會破版甚至注入。
    """
    return (str(text).replace('&', '&amp;')
                     .replace('<', '&lt;')
                     .replace('>', '&gt;'))


def render_core_summary(summary: Optional[CoreSummary]) -> None:
    """渲染核心總表(頁面最頂端的最高階概況)。

    Args:
        summary: `core_summary_service.get_core_summary()` 的輸出。
            None → 顯示誠實的「無法組裝」訊息,**不**畫空表假裝正常。

    Note:
        §1:本函式不會把任何一格「補」成好看的樣子。⬜ 未評估與 ❌ 取數失敗
        都照實印,且用不同顏色與不同 emoji 讓使用者一眼分得出來。
    """
    st.markdown('#### 🧭 核心總表')

    if summary is None or not getattr(summary, 'cells', ()):
        st.info('⬜ 核心總表尚未組裝完成 —— 未評估 ≠ 沒問題，'
                '請按「🚀 一鍵更新全部數據」後再看。')
        return

    _cells = tuple(summary.cells)

    # ── 頂部一行狀態(有結論 / 未評估 / 失敗 各幾項)──────────────────────
    # 文字出自 CoreSummary.headline(),本層不自算計數。
    _bar_color = (_FAILED_HEX if summary.n_failed
                  else (TRAFFIC_NEUTRAL if summary.n_unknown else emoji_to_hex('🟢')))
    st.markdown(
        f'<div style="background:#0d1117;border:1px solid {_bar_color};'
        f'border-radius:8px;padding:6px 12px;margin:2px 0 8px;'
        f'font-size:12px;color:{_bar_color};font-weight:700;">'
        f'{_esc(summary.headline())}</div>',
        unsafe_allow_html=True)

    # ── KPI 格子(每格:名稱 + 燈號數字)────────────────────────────────
    _tiles = ''.join(
        f'<div style="background:#161b22;border:1px solid #30363d;'
        f'border-left:3px solid {_hex(_c)};border-radius:6px;'
        f'padding:8px 10px;">'
        f'<div style="font-size:10px;color:#8b949e;line-height:1.4;">'
        f'{_esc(_c.label)}</div>'
        f'<div style="font-size:14px;font-weight:800;color:{_hex(_c)};'
        f'line-height:1.5;word-break:break-all;">{_esc(_c.display_text)}</div>'
        f'</div>'
        for _c in _cells)
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,'
        f'minmax(190px,1fr));gap:6px;margin-bottom:6px;">{_tiles}</div>',
        unsafe_allow_html=True)

    # ── 靜態圖例（本檔唯一自己寫的文字：它與任何一筆資料都無關）──────────
    st.caption('🟢🟡🔴 = 已評估且有結論　｜　⬜ = **未評估**（不是「沒問題」，'
               '缺什麼與怎麼補見下方明細）　｜　❌ = 取數失敗（會印出例外型別）')

    # ── 明細：逐格印 producer 給的 explain，UI 端不加工 ────────────────────
    with st.expander('📖 每個數字怎麼來的？（缺資料時也會說缺什麼、怎麼補）',
                     expanded=False):
        for _c in _cells:
            st.markdown(f'**{_esc(_c.label)}**')
            for _line in (_c.explain or ()):
                st.markdown(f'- {_line}')
            if not _c.explain:
                # 契約上不該發生（三支 formatter 都會塞第一行）；真發生要看得見。
                st.markdown('- ⚠️ 本格未附推導說明（producer 契約異常）')
            st.markdown('')

    # ── 未評估 / 失敗的收斂引導（用的是 cell 自己的 label，不自寫結論）──────
    _pending = [c.label for c in _cells if c.status == STATUS_UNKNOWN]
    _broken = [c.label for c in _cells if c.status == STATUS_FAILED]
    if _broken:
        st.error('❌ 取數失敗：' + '、'.join(_esc(x) for x in _broken)
                 + ' —— 展開上方明細看例外型別與原文。')
    if _pending:
        st.caption('⬜ 尚未評估：' + '、'.join(_esc(x) for x in _pending)
                   + ' —— 展開上方明細看各自缺什麼、怎麼補。')
