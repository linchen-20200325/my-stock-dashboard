"""四頁共用的 PageVM 渲染骨架（第一屏四問 → 核心卡 → 各區塊）。

標示（FAKE 示意資料／Real-data Preview 單行 banner）由殼在導覽**之前**統一渲染（頁面頂部），本檔不重複渲染。
開發專用的 Preview 控制只在 `?ui2_dev=1` 由殼畫出，本檔不涉及。

**呈現政策（Active Contract §8；P3，客戶 2026-11-03 (17) A2）**：`PageVM.context.sections` 是 VM 全量（**不是** Decision
Context，也不是畫面清單）；本檔只決定「哪些區塊在畫面上怎麼畫」，**不改 VM 內容**——L1 直接畫；L2／L3 **預設不渲染**
（四個主要投資頁不承載完整 L2／L3 evidence expander；evidence 仍完整留在 VM／canonical／Digest 輸入），
只有 `SHOWN_FOLDS` 白名單內的「使用者功能／已核准稽核入口」才以預設收合的 expander 呈現。新增 L2／L3 區塊
**預設隱藏**（fail closed：不會因為新增 evidence 而意外長出 expander）。
Batch 3：標題／本文拆成可重用片段，供 📊 市場（今日結論＋今日主要風險）、🎯 標的（雙模式）、
👤 我的（帳戶 skeleton）三頁各自組版；所有頁仍只吃 PageVM（⛔ 取數／判態／聚合動作）。
"""
from __future__ import annotations

from html import escape

import streamlit as st

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import field_row_html, first_screen_html, metric_card_html


def _md(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def render_title(vm: PageVM, **attrs: str) -> None:
    # data-ui2-page／-scenario＝量測與測試錨點（tests/ui2_viewport），不影響呈現。
    extra = "".join(f' data-ui2-{k}="{escape(v)}"' for k, v in attrs.items())
    _md(f'<div class="ui2-pagetitle" data-ui2-page="{escape(vm.page_id)}" '
        f'data-ui2-scenario="{escape(vm.scenario_id)}"{extra}>{escape(vm.title)}</div>')


def render_cards(vm: PageVM, *, content_mode: str | None = None) -> None:
    visible = set(vm.slice.visible_card_ids)
    cards = [c for c in vm.context.cards if c.card_id in visible]
    if cards:
        attr = f' data-ui2-mode-content="{escape(content_mode)}"' if content_mode else ""
        _md(f'<div class="ui2-grid"{attr}>' + "".join(metric_card_html(c) for c in cards) + "</div>")


def _label_repeats_title(sec, f) -> bool:
    """區塊只有一個欄位、且欄位 label 已是區塊標題的一部分（如標題「🤖 OneBrain Outlook」＋列「OneBrain Outlook」）
    → 列的 label 不再重複畫（P1 重複標籤合併；欄位資料與 `data-*` 不變）。"""
    return len(sec.fields) == 1 and bool(f.label.strip()) and f.label.strip() in sec.title


#: 允許以「預設收合 expander」呈現的 L2／L3 區塊（page_id, section_id）。分兩類（純 presentation 分類，不改 VM）：
#:   * 使用者功能（DEC-121 Q2=B／DEC-130 (b)）：🎯 精選的「選股條件」（精簡、人類可讀）；
#:   * 已核准的次層稽核入口（Active Contract §3.4／DEC-130 (b)）：👤 的 Decision Digest Viewer、Rule Registry（預設收合）。
#: 其餘 L2／L3（為什麼／指標明細／原始資料表／完整 6 欄表／明細／原始明細／查一檔的基本面·估值·研究解釋／
#: 👤 的 Data Freshness·System Information〔→ P6 資料健康度〕）＝evidence：**VM 完整保留、Human UI 不渲染**。
SHOWN_FOLDS: frozenset[tuple[str, str]] = frozenset({
    ("p4_target", "conditions"),
    ("p4_me", "digest"),
    ("p4_me", "registry"),
})


def is_shown_fold(page_id: str, section_id: str) -> bool:
    return (page_id, section_id) in SHOWN_FOLDS


def section_l1_html(sec) -> str:
    """一個 L1 區塊的 HTML（標題＋各欄位列）。供 `render_sections` 與需要自行安排位置的頁（📊 的 OneBrain）共用，內容一致。"""
    rows = "".join(field_row_html(f, hide_label=_label_repeats_title(sec, f)) for f in sec.fields)
    return f'<div class="ui2-section-title">{escape(sec.title)}</div>' + rows


def render_sections(vm: PageVM, *, mode: str | None = None, extra=(), skip: frozenset[str] | set[str] = frozenset()) -> None:
    """L1 區塊直接畫；L2／L3 只畫 `SHOWN_FOLDS` 白名單內者（預設收合），其餘 evidence 不渲染（VM 不動，見檔頭）。
    `mode` 給定時只畫該模式（或與模式無關）的區塊（⛔ 同時完整展開）。
    `skip`：呼叫端已自行安排位置畫過的 section_id（P2：📊 的 `onebrain` 上移）；只影響「在哪畫」，不影響 VM。"""
    for sec in (*vm.context.sections, *extra):
        if sec.section_id in skip:
            continue
        if mode is not None and sec.mode not in (None, mode):
            continue
        if sec.level == "L1":
            _md(section_l1_html(sec))
        elif is_shown_fold(vm.page_id, sec.section_id):
            rows = "".join(field_row_html(f, hide_label=_label_repeats_title(sec, f)) for f in sec.fields)
            with st.expander(sec.title, expanded=False):   # Streamlit 自帶展開箭頭；不再加文字「▸」（雙箭頭）
                _md(rows)
        # 其餘 L2／L3＝evidence：不渲染（P3）；資料仍在 PageVM.context.sections／lookup.sections


def render_page(vm: PageVM) -> None:
    render_title(vm)
    _md(first_screen_html(vm.context.first_screen))      # 第一屏四問（主 CTA：disabled 示意）
    render_cards(vm)
    render_sections(vm)
