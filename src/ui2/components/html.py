"""元件 HTML builder（純函式、無 streamlit；所有動態字串一律 escape）。

語意色調四族（Positive／Warning／Danger／Neutral-Info）→ CSS modifier；
⛔ 不用警告族承載中性資訊（類型／產業／計數／估值口徑／資料來源 → Neutral/Info）。
⛔ 輸出為單行 HTML（避免 st.markdown 把縮排當 code block）。
"""
from __future__ import annotations

from html import escape

from shared.ui2_contract.models import (
    CapabilityState, CardVM, CtaVM, FieldState, FieldVM, FirstScreenVM, FreshnessInfo, JudgementState,
)
from shared.ui2_contract.text import TEXT_ASOF_MISSING
from shared.ui2_contract.tones import TONE_SYMBOL, ChipTone

#: 資料語意五態＋判定結果 → chip 色調。Missing／Not evaluated／無法判定＝灰（Neutral）；Stale＝琥珀；
#: Unavailable＝紅（系統真錯誤）。⛔ 無法判定給 Positive（綠＝safe 誤讀；DEC-124）。
STATE_TONE: dict[FieldState | JudgementState, ChipTone] = {
    FieldState.OK: ChipTone.NEUTRAL_INFO,
    FieldState.MISSING: ChipTone.NEUTRAL_INFO,
    FieldState.STALE: ChipTone.WARNING,
    FieldState.UNAVAILABLE: ChipTone.DANGER,
    FieldState.NOT_EVALUATED: ChipTone.NEUTRAL_INFO,
    JudgementState.UNDETERMINABLE: ChipTone.NEUTRAL_INFO,
}

#: Capability marker（Preview-only；與資料語意正交）→ 灰。
CAPABILITY_TONE: dict[CapabilityState, ChipTone] = {
    CapabilityState.NOT_PROVIDED: ChipTone.NEUTRAL_INFO,
}


def tone_for(field: FieldVM) -> ChipTone:
    if field.capability is CapabilityState.NOT_PROVIDED:
        return CAPABILITY_TONE[field.capability]
    return STATE_TONE[field.state]


_TONE_CLASS: dict[ChipTone, str] = {
    ChipTone.POSITIVE: "ui2-chip--positive",
    ChipTone.WARNING: "ui2-chip--warning",
    ChipTone.DANGER: "ui2-chip--danger",
    ChipTone.NEUTRAL_INFO: "ui2-chip--neutral",
}


def tone_class(tone: ChipTone) -> str:
    return _TONE_CLASS[tone]


def chip_html(text: str, tone: ChipTone, *, with_symbol: bool = False) -> str:
    sym = f"{TONE_SYMBOL[tone]} " if with_symbol else ""
    return f'<span class="ui2-chip {tone_class(tone)}">{escape(sym + text)}</span>'


def neutral_chip_html(text: str) -> str:
    """類型／產業／計數／估值口徑／資料來源專用（Neutral/Info；⛔ 不用警告族）。"""
    return chip_html(text, ChipTone.NEUTRAL_INFO)


def status_chip_html(field: FieldVM) -> str:
    """欄位狀態字樣 chip（OK 態無）。紅色只給 Unavailable（系統真錯誤）；未載入＝灰。"""
    if field.state is FieldState.OK or not field.status_text:
        return ""
    return chip_html(field.status_text, tone_for(field))


def freshness_html(fresh: FreshnessInfo) -> str:
    """field-level freshness micro-tag：資料日＋來源。缺 as_of → `⬜ 資料日未提供`（⛔ 補推估日期）。"""
    asof = escape(fresh.as_of) if fresh.as_of else escape(TEXT_ASOF_MISSING)
    parts = [f'<span class="ui2-fresh">資料日 {asof}</span>' if fresh.as_of
             else f'<span class="ui2-fresh ui2-fresh--missing">{asof}</span>']
    if fresh.source:
        parts.append(neutral_chip_html(f"來源 {fresh.source}"))
    return '<span class="ui2-freshrow">' + "".join(parts) + "</span>"


def metric_card_html(card: CardVM) -> str:
    f = card.field
    value = (f'<div class="ui2-card__value">{escape(f.value_text)}</div>'
             if f.value_text is not None else '<div class="ui2-card__value ui2-card__value--blank">—</div>')
    detail = f'<div class="ui2-card__detail">{escape(f.detail)}</div>' if f.detail else ""
    chips = "".join(chip_html(c.text, c.tone) for c in card.chips)
    return (f'<div class="ui2-card" data-card-id="{escape(card.card_id)}">'
            f'<div class="ui2-card__title">{escape(card.title)}</div>{value}'
            f'<div class="ui2-card__chips">{status_chip_html(f)}{chips}</div>{detail}'
            f'{freshness_html(f.freshness)}</div>')


def field_row_html(field: FieldVM) -> str:
    value = escape(field.value_text) if field.value_text is not None else ""
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if field.detail else ""
    return (f'<div class="ui2-row"><div class="ui2-row__label">{escape(field.label)}</div>'
            f'<div class="ui2-row__body"><span class="ui2-row__value">{value}</span>'
            f'{status_chip_html(field)}</div>{detail}</div>')


def cta_html(cta: CtaVM) -> str:
    reason = f'<div class="ui2-cta__reason">{escape(cta.disabled_reason)}</div>' if cta.disabled_reason else ""
    state = "" if cta.enabled else " ui2-cta--disabled"
    return (f'<div class="ui2-ctawrap"><span class="ui2-cta{state}" aria-disabled="{str(not cta.enabled).lower()}">'
            f'{escape(cta.label)}</span>{reason}</div>')


def banner_html(text: str, note: str) -> str:
    return (f'<div class="ui2-banner" role="note"><strong>{escape(text)}</strong>'
            f'<span class="ui2-banner__note">{escape(note)}</span></div>')


def qa_row_html(question: str | None, field: FieldVM) -> str:
    """第一屏一列：（選配）問題編號＋欄位 label／value／狀態 chip／原因。緊湊單列，手機優先。"""
    q = f'<span class="ui2-q">{escape(question)}</span>' if question else ""
    value = f'<span class="ui2-row__value">{escape(field.value_text)}</span>' if field.value_text is not None else ""
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if field.detail else ""
    return (f'<div class="ui2-qrow">{q}<span class="ui2-row__label">{escape(field.label)}</span> '
            f'{value}{status_chip_html(field)}{detail}</div>')


def first_screen_html(fs: FirstScreenVM) -> str:
    """第一屏四問（客戶 (5)-9）：① 現在狀態 ② 是否需要行動 ③ 下一步 ④ 主 CTA（單一緊湊區塊）。"""
    rows = [qa_row_html("① 現在狀態", fs.current_state)]
    rows += [qa_row_html(None, r) for r in fs.context_rows]
    rows += [qa_row_html("② 是否需要行動", fs.action_needed),
             qa_row_html("③ 下一步", fs.next_step)]
    return ('<div class="ui2-qa">' + "".join(rows)
            + '<span class="ui2-q">④ 主 CTA</span>' + cta_html(fs.primary_cta) + "</div>")
