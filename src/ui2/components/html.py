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


#: 三個語意軸的**樣式**區分（DEC-124；Freeze §4.1「顏色不是唯一載體」）：
#: 資料語意＝實線框、判定結果＝雙線框、capability＝虛線框；另帶 `data-axis` 屬性供測試／無障礙工具讀取。
#: 三軸字樣本身已互斥（`shared/ui2_contract/text.py` 三張表），樣式只是第二載體，⛔ 取代字樣。
AXIS_CLASS: dict[str, str] = {
    "data": "ui2-chip--axis-data",
    "judgement": "ui2-chip--axis-judgement",
    "capability": "ui2-chip--axis-capability",
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


def chip_html(text: str, tone: ChipTone, *, with_symbol: bool = False, axis: str | None = None,
              state: str | None = None) -> str:
    sym = f"{TONE_SYMBOL[tone]} " if with_symbol else ""
    ax = f" {AXIS_CLASS[axis]}" if axis else ""
    attrs = (f' data-axis="{escape(axis)}"' if axis else "") + (f' data-state="{escape(state)}"' if state else "")
    return f'<span class="ui2-chip {tone_class(tone)}{ax}"{attrs}>{escape(sym + text)}</span>'


def neutral_chip_html(text: str) -> str:
    """類型／產業／計數／估值口徑／資料來源專用（Neutral/Info；⛔ 不用警告族）。"""
    return chip_html(text, ChipTone.NEUTRAL_INFO)


def status_chip_html(field: FieldVM) -> str:
    """欄位狀態字樣 chip（OK 態無）。紅色只給 Unavailable（系統真錯誤）；未載入＝灰。"""
    if field.state is FieldState.OK or not field.status_text:
        return ""
    state = field.capability.value if field.layer == "capability" else field.state.value
    return chip_html(field.status_text, tone_for(field), axis=field.layer, state=state)


def freshness_html(fresh: FreshnessInfo) -> str:
    """field-level freshness micro-tag：資料日＋來源。缺 as_of → `⬜ 資料日未提供`（⛔ 補推估日期）。"""
    asof = escape(fresh.as_of) if fresh.as_of else escape(TEXT_ASOF_MISSING)
    parts = [f'<span class="ui2-fresh">資料日 {asof}</span>' if fresh.as_of
             else f'<span class="ui2-fresh ui2-fresh--missing">{asof}</span>']
    if fresh.source:
        parts.append(neutral_chip_html(f"來源 {fresh.source}"))
    return '<span class="ui2-freshrow">' + "".join(parts) + "</span>"


def _state_attr(field: FieldVM) -> str:
    return field.capability.value if field.layer == "capability" else field.state.value


def metric_card_html(card: CardVM) -> str:
    """資料卡：title／value／狀態 chip／detail／field-level freshness（Freeze §9-1）。無值 → blank 樣式（⛔ 補 0）。"""
    f = card.field
    value = (f'<div class="ui2-card__value">{escape(f.value_text)}</div>'
             if f.value_text is not None else '<div class="ui2-card__value ui2-card__value--blank">—</div>')
    detail = f'<div class="ui2-card__detail">{escape(f.detail)}</div>' if f.detail else ""
    chips = "".join(chip_html(c.text, c.tone) for c in card.chips)
    return (f'<div class="ui2-card" data-card-id="{escape(card.card_id)}" data-axis="{f.layer}" '
            f'data-state="{_state_attr(f)}">'
            f'<div class="ui2-card__title">{escape(card.title)}</div>{value}'
            f'<div class="ui2-card__chips">{status_chip_html(f)}{chips}</div>{detail}'
            f'{freshness_html(f.freshness)}</div>')


def empty_state_html(field: FieldVM) -> str:
    """空／冷／未提供狀態的區塊呈現（取代空白）：chip（三軸各自樣式）＋原因一句。⛔ 空白、⛔ 補 0、⛔ 紅色（除 Unavailable）。"""
    reason = f'<div class="ui2-empty__reason">{escape(field.detail)}</div>' if field.detail else ""
    return (f'<div class="ui2-empty" data-axis="{field.layer}" data-state="{_state_attr(field)}">'
            f'<span class="ui2-row__label">{escape(field.label)}</span> {status_chip_html(field)}{reason}</div>')


def field_row_html(field: FieldVM) -> str:
    value = escape(field.value_text) if field.value_text is not None else ""
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if field.detail else ""
    return (f'<div class="ui2-row" data-axis="{field.layer}" data-state="{_state_attr(field)}">'
            f'<div class="ui2-row__label">{escape(field.label)}</div>'
            f'<div class="ui2-row__body"><span class="ui2-row__value">{value}</span>'
            f'{status_chip_html(field)}</div>{detail}</div>')


def cta_html(cta: CtaVM) -> str:
    """主 CTA。Preview 期 enabled=False：虛線框＋`aria-disabled="true"`＋原因文字（⛔ 看起來可按；⛔ 觸發任何動作）。"""
    reason = f'<div class="ui2-cta__reason">{escape(cta.disabled_reason)}</div>' if cta.disabled_reason else ""
    state = "" if cta.enabled else " ui2-cta--disabled"
    return (f'<div class="ui2-ctawrap"><span class="ui2-cta{state}" role="button" '
            f'aria-disabled="{str(not cta.enabled).lower()}">{escape(cta.label)}</span>{reason}</div>')


def banner_html(text: str, note: str) -> str:
    return (f'<div class="ui2-banner" role="note"><strong>{escape(text)}</strong>'
            f'<span class="ui2-banner__note">{escape(note)}</span></div>')


def qa_row_html(question: str | None, field: FieldVM, *, qid: str = "ctx") -> str:
    """第一屏一列：（選配）問題編號＋欄位 label／value／狀態 chip／原因。緊湊單列，手機優先。

    `data-ui2-q`＝量測錨點（`q1`～`q3`／`ctx`；④ 見 `first_screen_html`），不影響呈現。
    """
    q = f'<span class="ui2-q">{escape(question)}</span>' if question else ""
    value = f'<span class="ui2-row__value">{escape(field.value_text)}</span>' if field.value_text is not None else ""
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if field.detail else ""
    return (f'<div class="ui2-qrow" data-ui2-q="{qid}" data-axis="{field.layer}" data-state="{_state_attr(field)}">'
            f'{q}<span class="ui2-row__label">{escape(field.label)}</span> '
            f'{value}{status_chip_html(field)}{detail}</div>')


def first_screen_html(fs: FirstScreenVM) -> str:
    """第一屏四問（客戶 (5)-9）：① 現在狀態 ② 是否需要行動 ③ 下一步 ④ 主 CTA（單一緊湊區塊）。"""
    rows = [qa_row_html("① 現在狀態", fs.current_state, qid="q1")]
    rows += [qa_row_html(None, r, qid="ctx") for r in fs.context_rows]
    rows += [qa_row_html("② 是否需要行動", fs.action_needed, qid="q2"),
             qa_row_html("③ 下一步", fs.next_step, qid="q3")]
    return ('<div class="ui2-qa">' + "".join(rows)
            + '<div class="ui2-qrow ui2-qrow--cta" data-ui2-q="q4"><span class="ui2-q">④ 主 CTA</span>'
            + cta_html(fs.primary_cta) + "</div></div>")
