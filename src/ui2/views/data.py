"""data 頁（🗂 資料）view：只渲染 PageVM ＋「🔌 連線診斷」區塊（GitHub #1110 D-T2）。

DEC-146 第一批：可導航、誠實的「尚未提供／尚未接線」空殼。保留 Data State／Capability 分軸（本頁全為 Capability 軸
`⬜ 尚未提供`）。⛔ 來源健康度欄位／分母／retrieved_at／proxy／刷新時間／真登入／Sheet／API／公式；⛔ 取數與判態。
「連線診斷」只呈現網路連線狀態字（不是資料來源健康度）：完整資料健康度尚未開放；本區僅檢查連線，不代表資料已更新。
探測由殼注入的 callable 在**使用者點擊那次 rerun** 才執行；session_state 只存安全枚舉報告（`ui2_diag_report`），
⛔ 存 callable／URL／例外文字；⛔ 任何時間戳或日期。
"""
from __future__ import annotations

from dataclasses import replace
from html import escape

import streamlit as st

from shared.ui2_contract import diag as D
from shared.ui2_contract.models import PageVM
from shared.ui2_contract.tones import ChipTone
from src.ui2.components.html import chip_html, first_screen_html
from src.ui2.views._page import _md, render_cards, render_sections, render_title

KEY_DIAG_RUN = "ui2_diag_run"          # 「檢查連線」按鈕（widget key）
KEY_DIAG_REPORT = "ui2_diag_report"    # 極小的安全枚舉報告（DiagReport；frozen dataclass of Enum）

_TONE = {
    D.DiagStatus.SUCCESS: ChipTone.POSITIVE,
    D.DiagStatus.FAILED: ChipTone.DANGER,          # 紅色只給「連線失敗」
    D.DiagStatus.AUTH_UNVERIFIED: ChipTone.WARNING,
    D.DiagStatus.NOT_CONFIGURED: ChipTone.NEUTRAL_INFO,
    D.DiagStatus.NOT_CHECKED: ChipTone.NEUTRAL_INFO,
}


def _row(label: str, res: D.ProbeResult | None, *, sub: bool = False) -> str:
    chip = (chip_html(res.status.value, _TONE[res.status], with_symbol=True) if res is not None
            else chip_html(D.TEXT_DIAG_PUBLICATION_VALUE, ChipTone.NEUTRAL_INFO, with_symbol=True))
    cls = "ui2-diag__row ui2-diag__row--sub" if sub else "ui2-diag__row"
    return f'<div class="{cls}"><span class="ui2-diag__label">{escape(label)}</span>{chip}</div>'


def _reasons(rep: D.DiagReport) -> str:
    items = [(D.TEXT_DIAG_LABEL_NAS_RELAY, rep.nas_relay), (D.TEXT_DIAG_LABEL_NAS_PROXY, rep.nas_proxy),
             (D.TEXT_DIAG_LABEL_FINMIND, rep.finmind), (D.TEXT_DIAG_LABEL_YAHOO, rep.yahoo),
             (D.TEXT_DIAG_LABEL_TWSE, rep.twse)]
    lines = [f"{escape(lb)}：{escape(r.reason.value)}" for lb, r in items if r.reason is not D.DiagReason.NONE]
    if rep.notice is not D.DiagNotice.NONE:
        lines.append(escape(rep.notice.value))
    return "".join(f'<div class="ui2-diag__reason">{ln}</div>' for ln in lines)


def _block_html(rep: D.DiagReport) -> str:
    return (f'<div class="ui2-diag" role="group" aria-label="{escape(D.TEXT_DIAG_ARIA)}">'
            f'<div role="heading" aria-level="2" class="ui2-section-title">{escape(D.TEXT_DIAG_TITLE)}</div>'
            f'<div class="ui2-diag__note">{escape(D.TEXT_DIAG_NOTE)}</div>'
            + _row(D.TEXT_DIAG_LABEL_NAS_RELAY, rep.nas_relay)
            + _row(D.TEXT_DIAG_LABEL_NAS_PROXY, rep.nas_proxy)
            + f'<div class="ui2-diag__group">{escape(D.TEXT_DIAG_LABEL_EXTERNAL)}</div>'
            + _row(D.TEXT_DIAG_LABEL_FINMIND, rep.finmind, sub=True)
            + _row(D.TEXT_DIAG_LABEL_YAHOO, rep.yahoo, sub=True)
            + _row(D.TEXT_DIAG_LABEL_TWSE, rep.twse, sub=True)
            + _row(D.TEXT_DIAG_LABEL_PUBLICATION, None) + '</div>')


def _valid_report(rep: object) -> bool:
    """深度驗證：五個探測結果都必須是 `ProbeResult(DiagStatus, DiagReason)`、notice 必須是 `DiagNotice`。
    形狀不對的報告（producer bug／過期 session）不得進 session，否則資料頁每次 rerun 都會崩潰。"""
    if not isinstance(rep, D.DiagReport) or not isinstance(rep.notice, D.DiagNotice):
        return False
    return all(isinstance(p, D.ProbeResult) and isinstance(p.status, D.DiagStatus) and isinstance(p.reason, D.DiagReason)
               for p in (rep.nas_relay, rep.nas_proxy, rep.finmind, rep.yahoo, rep.twse))


def _current_report() -> D.DiagReport:
    rep = st.session_state.get(KEY_DIAG_REPORT)
    return rep if _valid_report(rep) else D.INITIAL_REPORT


def render_diag(diag_check=None) -> None:
    """連線診斷區塊。⛔ 不按不探測：只有 `st.button` 回 True 的那一次 rerun 才呼叫 `diag_check`。
    畫面順序（GPT 定稿）＝狀態列 → 按鈕 → 固定安全原因類別；用 `st.empty()` 佔位，讓點擊結果在同一次 rerun 內回填。"""
    rows_slot = st.empty()
    clicked = st.button(D.TEXT_DIAG_BUTTON, key=KEY_DIAG_RUN, width="stretch", disabled=diag_check is None)
    reasons_slot = st.empty()
    notice = D.DiagNotice.NONE      # 冷卻／忙碌提示只屬於「這次點擊」，不跟著結果存進 session（其後 rerun／換頁再回來不再顯示）
    if clicked and diag_check is not None:
        try:
            result = diag_check()
        except Exception:   # noqa: BLE001 — 不顯示例外原文
            result = None
        if _valid_report(result):
            notice = result.notice
            report = replace(result, notice=D.DiagNotice.NONE)
        else:               # 非 DiagReport／形狀不對 → 與例外同一個固定結果（fail closed；⛔ 原樣存入 session）
            report = D.DiagReport(*(D.ProbeResult(D.DiagStatus.FAILED, D.DiagReason.OTHER),) * 5)
        st.session_state[KEY_DIAG_REPORT] = report
    rep = _current_report()
    rows_slot.markdown(_block_html(rep), unsafe_allow_html=True)
    reasons_slot.markdown(_reasons(replace(rep, notice=notice)), unsafe_allow_html=True)


def render(vm: PageVM, diag_check=None) -> None:
    render_title(vm)
    _md(first_screen_html(vm.context.first_screen))      # 現在狀態／是否需要行動／下一步／主 CTA（disabled 示意）
    render_diag(diag_check)                              # 🔌 連線診斷（第一屏之後、其餘內容之前）
    render_cards(vm)
    render_sections(vm)
