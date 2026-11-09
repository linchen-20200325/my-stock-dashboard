"""元件 HTML builder（純函式、無 streamlit；所有動態字串一律 escape）。

語意色調四族（Positive／Warning／Danger／Neutral-Info）→ CSS modifier；
⛔ 不用警告族承載中性資訊（類型／產業／計數／估值口徑／資料來源 → Neutral/Info）。
⛔ 輸出為單行 HTML（避免 st.markdown 把縮排當 code block）。
"""
from __future__ import annotations

import math
from html import escape

from shared.ui2_contract.models import (
    AccountVM, CapabilityState, CardVM, CtaVM, FieldState, FieldVM, FirstScreenVM, FreshnessInfo,
    JudgementState, KbarChartVM, LookupResultVM, SearchBoxVM,
)
from shared.ui2_contract import text as _T
from shared.ui2_contract.text import TEXT_ASOF_MISSING, TEXT_NOT_PROVIDED, is_dev_only_text, is_known_l0_explain
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


def shown(detail: str | None) -> bool:
    """該段 `detail` 是否畫在 Human UI：有字、且不是只給開發面／資料健康度讀的治理參照句（見 `is_dev_only_text`）。
    ⛔ 這只是呈現政策：被略過的句子仍完整留在 `FieldVM.detail`（Active Contract §8）。"""
    if not detail:
        return False
    if is_dev_only_text(detail):
        if not is_known_l0_explain(detail):      # 不沉默：不是已知 L0 常數卻命中治理參照 → 有人把工程句寫進 detail
            print(f"[ui2.html] WARNING 含治理參照的 detail 未顯示（不是已知 L0 說明常數）：{detail[:80]!r}")
        return False
    return True


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
    detail = f'<div class="ui2-card__detail">{escape(f.detail)}</div>' if shown(f.detail) else ""
    chips = "".join(chip_html(c.text, c.tone) for c in card.chips)
    return (f'<div class="ui2-card" data-card-id="{escape(card.card_id)}" data-axis="{f.layer}" '
            f'data-state="{_state_attr(f)}">'
            f'<div class="ui2-card__title">{escape(card.title)}</div>{value}'
            f'<div class="ui2-card__chips">{status_chip_html(f)}{chips}</div>{detail}'
            f'{freshness_html(f.freshness)}</div>')


def empty_state_html(field: FieldVM) -> str:
    """空／冷／未提供狀態的區塊呈現（取代空白）：chip（三軸各自樣式）＋原因一句。⛔ 空白、⛔ 補 0、⛔ 紅色（除 Unavailable）。"""
    reason = f'<div class="ui2-empty__reason">{escape(field.detail)}</div>' if shown(field.detail) else ""
    return (f'<div class="ui2-empty" data-axis="{field.layer}" data-state="{_state_attr(field)}">'
            f'<span class="ui2-row__label">{escape(field.label)}</span> {status_chip_html(field)}{reason}</div>')


def field_row_html(field: FieldVM, *, hide_label: bool = False) -> str:
    """一列欄位。`hide_label=True`：區塊標題已是同一個名稱時不重複顯示 label（P1 重複標籤合併；欄位資料不變）。"""
    value = escape(field.value_text) if field.value_text is not None else ""
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if shown(field.detail) else ""
    label = "" if hide_label else f'<div class="ui2-row__label">{escape(field.label)}</div>'
    return (f'<div class="ui2-row" data-axis="{field.layer}" data-state="{_state_attr(field)}">'
            f'{label}'
            f'<div class="ui2-row__body"><span class="ui2-row__value">{value}</span>'
            f'{status_chip_html(field)}</div>{detail}</div>')


def cta_html(cta: CtaVM, *, with_reason: bool = True) -> str:
    """主 CTA。Preview 期 enabled=False：虛線框＋`aria-disabled="true"`＋原因文字（⛔ 看起來可按；⛔ 觸發任何動作）。

    `with_reason=False`（一列多顆按鈕時）：原因改放 `title`，並由呼叫端另列一句共用原因（⛔ 吞掉原因）。
    """
    reason = (f'<div class="ui2-cta__reason">{escape(cta.disabled_reason)}</div>'
              if cta.disabled_reason and with_reason else "")
    state = "" if cta.enabled else " ui2-cta--disabled"
    tip = (f' title="{escape(cta.disabled_reason)}"' if cta.disabled_reason and not with_reason else "")
    return (f'<div class="ui2-ctawrap"><span class="ui2-cta{state}" role="button" '
            f'aria-disabled="{str(not cta.enabled).lower()}"{tip}>{escape(cta.label)}</span>{reason}</div>')


def banner_html(text: str, note: str, *, note_hidden_on_mobile: bool = False) -> str:
    """頂部單行標示。`note_hidden_on_mobile=True`：手機窄螢幕不顯示補充說明（避免折成兩行；主標示文字不變）。"""
    cls = "ui2-banner__note ui2-banner__note--wide" if note_hidden_on_mobile else "ui2-banner__note"
    tail = f'<span class="{cls}">{escape(note)}</span>' if note else ""
    return f'<div class="ui2-banner" role="note"><strong>{escape(text)}</strong>{tail}</div>'


def qa_row_html(question: str | None, field: FieldVM, *, qid: str = "ctx") -> str:
    """第一屏一列：欄位 label／value／狀態 chip／原因。緊湊單列，手機優先。

    `data-ui2-q`＝量測錨點（`q1`～`q3`／`ctx`；④ 見 `first_screen_html`），不影響呈現。
    `question`＝該列回答的第一屏問題名（無題號）：只寫成 `data-ui2-qname` 屬性（測試／無障礙工具用），
    **不渲染成可見文字**（P1：題號「①②③④」是線框的草稿註記，不是 UI 文案）。
    """
    q = ""
    qname = f' data-ui2-qname="{escape(question)}"' if question else ""
    value = f'<span class="ui2-row__value">{escape(field.value_text)}</span>' if field.value_text is not None else ""
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if shown(field.detail) else ""
    return (f'<div class="ui2-qrow" data-ui2-q="{qid}"{qname} data-axis="{field.layer}" data-state="{_state_attr(field)}">'
            f'{q}<span class="ui2-row__label">{escape(field.label)}</span> '
            f'{value}{status_chip_html(field)}{detail}</div>')


def first_screen_html(fs: FirstScreenVM, *, cta_first: bool = False) -> str:
    """第一屏四問（客戶 (5)-9）：現在狀態／是否需要行動／下一步／主 CTA（單一緊湊區塊；題號不外露，錨點 `data-ui2-q`）。

    `cta_first=True`（📊 市場頁；Wireframes §2.1／§2.2、DEC-117 Q5：頁首→更新 CTA→今日結論→…）：主 CTA 排在
    **最前**（今日結論之前）。四問是**資訊需求**，不代表 DOM 固定按 ①→④ 排列（客戶 2026-11-03 裁示）；
    只調順序與排版，⛔ 不改任何 VM 欄位／字樣。此模式 CTA 與原因同列（`ui2-qrow--cta-top`），不另顯示「④」編號標籤。
    """
    rows = [] if cta_first else ([conclusion_row_html(fs.conclusion)] if fs.conclusion is not None else [])
    if cta_first:
        rows.append('<div class="ui2-qrow ui2-qrow--cta ui2-qrow--cta-top" data-ui2-q="q4">'
                    + cta_html(fs.primary_cta) + "</div>")
        if fs.conclusion is not None:
            rows.append(conclusion_row_html(fs.conclusion))
    rows += [qa_row_html("現在狀態", fs.current_state, qid="q1")]
    rows += [qa_row_html(None, r, qid="ctx") for r in fs.context_rows]
    rows += [qa_row_html("是否需要行動", fs.action_needed, qid="q2"),
             qa_row_html("下一步", fs.next_step, qid="q3")]
    tail = ("" if cta_first else
            '<div class="ui2-qrow ui2-qrow--cta" data-ui2-q="q4" data-ui2-qname="主 CTA">'
            + cta_html(fs.primary_cta) + "</div>")
    return '<div class="ui2-qa">' + "".join(rows) + tail + "</div>"


def page_title_html(page_id: str, scenario_id: str, title: str) -> str:
    """頁標題 div（與 `src/ui2/views/_page.py::render_title` 逐字相同；供需要把標題與第一屏放進同一個容器的頁使用）。"""
    return (f'<div class="ui2-pagetitle" data-ui2-page="{escape(page_id)}" '
            f'data-ui2-scenario="{escape(scenario_id)}">{escape(title)}</div>')


def hold_l1_html(title_html: str, fs: FirstScreenVM) -> str:
    """💼 持股頁：標題＋第一屏同一容器（`ui2-h-l1`）。手機＝與原本逐像素相同（堆疊）；桌機（≥769px）由 CSS 依
    Wireframes §4.2／W-11（客戶 Q3 核准）排成：header 列＝標題＋主 CTA、其下三 tile（Risk Cap／目前曝險／組合狀態）、
    再其下今日需處理／下一步各一列。⛔ 不增刪任何欄位／元件／字樣，DOM 內容與 `data-ui2-q` 錨點全保留。"""
    return '<div class="ui2-h-l1">' + title_html + first_screen_html(fs) + "</div>"


# ════════════════════════════════════════════════════════════════════
# 💼 持股 W-11 批 1（DEC-141；客戶 2026-11-05 Q1~Q8）：僅版面／欄位結構／空槽——⛔ 資料接線、計算、新來源
# ════════════════════════════════════════════════════════════════════
def _hold_slot_chip() -> str:
    return chip_html(TEXT_NOT_PROVIDED, ChipTone.NEUTRAL_INFO, axis="capability", state="not_provided")


def hold_status_html(fs: FirstScreenVM) -> str:
    """組合狀態行（Wireframes §4.1 ①／§4.2 header 列）：`組合：<既有欄位> · 資料日 <> · 判得出 <>`。

    * 組合名稱／檔數＝**只取** VM 既有 `current_state` 欄位（有值顯示值、無值顯示其狀態字樣）；⛔ 另行取數／推算。
    * 資料日（Q4）＝固定 `⬜ 資料日未提供`：未授權新增組合層日期定義或來源，⛔ 最舊一檔／今日／抓取時間頂替。
    * 判得出 M／N（Q4/draft）＝固定 `⬜ 尚未提供`：⛔ 計算、⛔ 寫成可信度／機率。
    """
    cs = fs.current_state
    name = cs.value_text if cs.value_text is not None else (cs.status_text or TEXT_NOT_PROVIDED)
    return ('<div class="ui2-h-status" data-ui2-l1="hold_status">'
            f'<span class="ui2-h-status__seg" data-seg="portfolio">{escape(_T.HOLD_STATUS_PORTFOLIO_LABEL)}：{escape(name)}</span>'
            f'<span class="ui2-h-status__seg" data-seg="asof">{escape(_T.HOLD_STATUS_ASOF_LABEL)} {escape(TEXT_ASOF_MISSING)}</span>'
            f'<span class="ui2-h-status__seg" data-seg="judged">{escape(_T.HOLD_STATUS_JUDGED_LABEL)} {escape(TEXT_NOT_PROVIDED)}</span>'
            "</div>")


def hold_action_row_html(field: FieldVM | None) -> str:
    """今日需處理**單行**（Q6）：取代「是否需要行動／下一步」兩列的**畫面**（VM 兩欄位原樣保留，只是不再各占一列）。
    內容＝VM 既有動作欄的 Capability 空槽字樣（Aggregator 前 `⬜ 尚未提供（待系統動作整合）`）；
    ⛔ 計算動作、⛔ 「今日無需調整」、⛔ 把缺動作當全部續抱。保留錨點 `data-ui2-q="q2"`。"""
    if field is None:
        axis, state, chip = "capability", "not_provided", _hold_slot_chip()
    else:
        axis, state, chip = field.layer, _state_attr(field), status_chip_html(field)
    return (f'<div class="ui2-qrow" data-ui2-q="q2" data-ui2-qname="是否需要行動" data-axis="{axis}" '
            f'data-state="{state}"><span class="ui2-row__label">{escape(_T.HOLD_ACTION_LABEL)}</span> {chip}</div>')


def hold_first_screen_html(fs: FirstScreenVM) -> str:
    """💼 第一屏：現在狀態／context（Risk Cap・目前曝險）／**今日需處理單行**／主 CTA。與 `first_screen_html` 相比只少「下一步」一列（合併，Q6）。"""
    rows = [qa_row_html("現在狀態", fs.current_state, qid="q1")]
    rows += [qa_row_html(None, r, qid="ctx") for r in fs.context_rows]
    rows.append(hold_action_row_html(fs.action_needed))
    tail = ('<div class="ui2-qrow ui2-qrow--cta" data-ui2-q="q4" data-ui2-qname="主 CTA">'
            + cta_html(fs.primary_cta) + "</div>")
    return '<div class="ui2-qa">' + "".join(rows) + tail + "</div>"


def hold_l1_v2_html(title_html: str, fs: FirstScreenVM) -> str:
    """標題 → 組合狀態行 → 第一屏（`hold_l1_html` 的 W-11 批 1 版；容器 class 不變，桌機規則沿用）。"""
    return '<div class="ui2-h-l1">' + title_html + hold_status_html(fs) + hold_first_screen_html(fs) + "</div>"


def hold_table_html() -> str:
    """持股表（Q7）：桌機八欄表頭＋手機四欄（其餘四欄收進每列展開，CSS 控制）＋原因句；⛔ 假列／假成本／假報酬／「0 檔」。"""
    ths = "".join(
        '<th scope="col"' + ("" if mobile else ' class="ui2-ht__x"') + f">{escape(name)}</th>"
        for name, mobile in _T.HOLD_TABLE_COLS)
    return ('<div class="ui2-h-table" data-ui2-l1="hold_table" data-axis="capability" data-state="not_provided">'
            f'<div class="ui2-section-title">{escape(_T.HOLD_TABLE_TITLE)}</div>'
            f'<table class="ui2-ht" data-ui2-cols="{len(_T.HOLD_TABLE_COLS)}"><thead><tr>{ths}</tr></thead></table>'
            f'<div class="ui2-ht__more">{escape(_T.HOLD_TABLE_EXPAND_HINT)}</div>'
            f'<div class="ui2-ht__empty">{_hold_slot_chip()}'
            f'<span class="ui2-primary-slot__reason">{escape(_T.HOLD_TABLE_REASON)}</span></div></div>')


def hold_body_html(onebrain_html: str = "") -> str:
    """第一屏之後（DOM＝手機順序：建議持股水位 → OneBrain → Primary 空槽 → 持股表；桌機由 CSS grid 排成
    OneBrain／〔Primary｜建議持股水位〕／持股表，Q1=A：Primary 與建議持股水位在上、持股表在下）。

    * Primary（Q2/Q3）：產業曝險／集中度；桌機維持預定高度、手機收成一行（標題＋`⬜ 尚未提供`）；⛔ 圖形元素、假橫條、0。
    * 建議持股水位（Q5）：僅空槽；⛔ 讀 Risk Cap、⛔ 區間數字、⛔ 暗示已有上限。
    """
    cap = ('<div class="ui2-primary-slot ui2-h-cap" data-ui2-l1="hold_cap_slot" data-axis="capability" data-state="not_provided">'
           f'<div class="ui2-section-title">{escape(_T.HOLD_CAP_TITLE)}</div>'
           f'<div class="ui2-primary-slot__body">{_hold_slot_chip()}'
           f'<span class="ui2-primary-slot__reason">{escape(_T.HOLD_CAP_REASON)}</span></div></div>')
    ob = f'<div class="ui2-m-onebrain ui2-h-ob" data-ui2-l1="onebrain">{onebrain_html}</div>' if onebrain_html else ""
    primary = ('<div class="ui2-primary-slot ui2-h-primary" data-ui2-l1="hold_primary_slot" data-axis="capability" data-state="not_provided">'
               f'<div class="ui2-section-title">{escape(_T.HOLD_PRIMARY_TITLE)}</div>'
               f'<div class="ui2-primary-slot__body">{_hold_slot_chip()}'
               f'<span class="ui2-primary-slot__reason">{escape(_T.HOLD_PRIMARY_REASON)}</span></div>'
               f'<div class="ui2-primary-slot__spec" data-ui2-spec="1">{escape(_T.HOLD_PRIMARY_SPEC)}</div></div>')
    return '<div class="ui2-h-body">' + cap + ob + primary + hold_table_html() + "</div>"


# ════════════════════════════════════════════════════════════════════
# Batch 3：📊 今日結論／今日主要風險、🎯 雙模式＋搜尋＋查一檔、👤 帳戶 skeleton
# ════════════════════════════════════════════════════════════════════
def conclusion_row_html(field: FieldVM) -> str:
    """今日結論（📊 市場第一屏首列；DEC-081 Q2-1）：句子原樣顯示，⛔ 由 UI 加工／推導。

    無值（冷啟動）→ 以狀態 chip＋原因取代句子（⛔ 空白、⛔ 紅色）。
    """
    text = (f'<span class="ui2-concl__text">{escape(field.value_text)}</span>'
            if field.value_text is not None else status_chip_html(field))
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if shown(field.detail) else ""
    return (f'<div class="ui2-qrow ui2-qrow--concl" data-ui2-q="concl" data-axis="{field.layer}" '
            f'data-state="{_state_attr(field)}"><span class="ui2-q">今日結論</span>{text}{detail}</div>')


def main_risk_html(field: FieldVM) -> str:
    """今日主要風險（L1；緊接第一屏之後）。退化／護欄句（DEC-117 Q6）逐字外露：狀態字樣 chip＋原因句。

    ⛔ 不產生風險項、⛔ 寫「無風險」「安全」。冷啟動＝灰色說明（⛔ 紅），真錯誤＝紅（Unavailable）。
    """
    detail = f'<div class="ui2-row__detail">{escape(field.detail)}</div>' if shown(field.detail) else ""
    value = f'<span class="ui2-row__value">{escape(field.value_text)}</span>' if field.value_text else ""
    return (f'<div class="ui2-risk" data-ui2-l1="main_risk" data-axis="{field.layer}" '
            f'data-state="{_state_attr(field)}"><span class="ui2-q">{escape(field.label)}</span>'
            f'{value}{status_chip_html(field)}{detail}</div>')


def market_l1_html(fs: FirstScreenVM, main_risk: FieldVM | None) -> str:
    """市場頁 L1 區：（更新 CTA→今日結論→）第一屏四問區塊 ＋ **緊接**其後的今日主要風險（同一個容器，桌機排成三 tile，手機堆疊）。"""
    return ('<div class="ui2-m-l1">' + first_screen_html(fs, cta_first=True)
            + (main_risk_html(main_risk) if main_risk is not None else "") + "</div>")


def neutral_status_chip_html(field: FieldVM) -> str:
    """狀態 chip，但色調固定 Neutral/Info（W-4：市場 context 不以 Warning／Danger 主導）。

    狀態由**文字**（⚠／🔴 字樣＋軸別樣式 `data-axis`／`data-state`）承載，不靠色調；OK 態無 chip。
    """
    if field.state is FieldState.OK or not field.status_text:
        return ""
    state = field.capability.value if field.layer == "capability" else field.state.value
    return chip_html(field.status_text, ChipTone.NEUTRAL_INFO, axis=field.layer, state=state)


def _ctx_chip(field: FieldVM) -> str:
    """W-4 輕量 context chip：一律 Neutral/Info 外觀（⛔ Warning／Danger／綠）；非 OK 態以文字標示狀態。"""
    if field.value_text is not None and field.state is FieldState.OK:
        return neutral_chip_html(field.value_text)
    if field.value_text is not None:                      # Stale：值照顯示，狀態文字附上
        return neutral_chip_html(field.value_text) + neutral_status_chip_html(field)
    return neutral_status_chip_html(field)


def ctxline_html(rows: tuple[FieldVM, ...]) -> str:
    """🎯 標的頁 W-4：市場位階＋Risk Cap 一行（小字級、置於查詢摘要之下；不搶查一檔／基本面／valuation）。"""
    items = "".join(f'<span class="ui2-ctxline__item"><span class="ui2-row__label">{escape(r.label)}</span> '
                    f'{_ctx_chip(r)}</span>' for r in rows)
    return f'<div class="ui2-qrow ui2-ctxline" data-ui2-q="ctx">{items}</div>'


def search_html(search: SearchBoxVM) -> str:
    """搜尋框＋搜尋 CTA（Preview：disabled 示意；⛔ 真查詢）。同時是標的頁的主 CTA 錨點（q4）。"""
    box = (f'<span class="ui2-searchbox" role="searchbox" aria-disabled="true" '
           f'aria-label="{escape(search.placeholder)}">🔍 {escape(search.placeholder)}</span>')
    reason = (f'<div class="ui2-cta__reason">{escape(search.cta.disabled_reason)}</div>'
              if search.cta.disabled_reason else "")
    hint = (f'<div class="ui2-search__hint">{status_chip_html(search.name_search)} '
            f'<span class="ui2-row__detail">{escape(search.name_search.detail or "")}</span></div>')
    return (f'<div class="ui2-search" data-ui2-q="q4" data-ui2-l1="search">{box}'
            f'{cta_html(search.cta, with_reason=False)}</div>{reason}{hint}')


def target_first_screen_html(fs: FirstScreenVM, summary: FieldVM) -> str:
    """🎯 標的頁第一屏（搜尋列在模式切換之下；本函式只含 ① 摘要、W-4 context 行、② ③）。"""
    return ('<div class="ui2-qa">' + qa_row_html("現在狀態（查詢摘要）", summary, qid="q1")
            + ctxline_html(fs.context_rows)
            + qa_row_html("是否需要行動", fs.action_needed, qid="q2")
            + qa_row_html("下一步", fs.next_step, qid="q3") + "</div>")


def snapshot_html(fields: tuple[FieldVM, ...]) -> str:
    """6 維 Snapshot（state＋短句；3×2 小格）。每格 field-level 狀態；⛔ 大段 prose。"""
    cells = "".join(
        f'<div class="ui2-dim" data-dim="{escape(f.label)}" data-axis="{f.layer}" data-state="{_state_attr(f)}">'
        f'<span class="ui2-row__label">{escape(f.label)}</span> '
        + (f'<span class="ui2-row__value">{escape(f.value_text)}</span>' if f.value_text is not None else "")
        + (neutral_status_chip_html(f) if f.label == "市場環境" else status_chip_html(f)) + "</div>"
        for f in fields)
    return f'<div class="ui2-snapshot">{cells}</div>'


def lookup_idle_html(lk: LookupResultVM) -> str:
    """尚未查詢（cold）：只有灰色說明（Wireframes §6；⛔ 畫結果頭／Snapshot／加入觀察、⛔ 紅色）。"""
    return (f'<div class="ui2-lookup ui2-lookup--idle" data-ui2-mode-content="lookup" data-ui2-queried="false">'
            f'{empty_state_html(lk.summary)}</div>')


def lookup_result_html(lk: LookupResultVM) -> str:
    """即時查一檔 FAKE 結果：Header（Neutral chip）→ 6 維 Snapshot → 加入觀察（disabled）→ session 隔離說明。"""
    if not lk.queried:
        return lookup_idle_html(lk)
    chips = "".join(neutral_chip_html(c.text) for c in lk.chips)
    return (f'<div class="ui2-lookup" data-ui2-mode-content="lookup" data-ui2-queried="true">'
            f'<div class="ui2-lookup__head"><strong>{escape(lk.ticker_text)} {escape(lk.name_text)}</strong> '
            f'{chips}</div>{snapshot_html(lk.snapshot)}'
            f'<div class="ui2-lookup__add">{cta_html(lk.add_watch_cta)}</div>'
            f'<div class="ui2-row__detail">{escape(lk.isolation_note)}</div></div>')


#: 帳戶示意態的人話標示（FAKE 場景；⛔ 不是登入證據，真實 auth 狀態另案 `NUI2-AUTH-CONTRACT-GATE`）。
_ACCOUNT_STATE_LABEL = {"signed_out": "尚未登入", "signed_in": "已登入", "unavailable": "Sheet 讀取失敗"}


def account_actions_html(account: AccountVM) -> str:
    """👤 帳戶／登入切換 skeleton：管理動作列（disabled）＋帳戶狀態標示（FAKE）。⛔ 真 OAuth／Sheet。"""
    btns = "".join(cta_html(a, with_reason=False) for a in account.actions)
    reasons = sorted({a.disabled_reason for a in account.actions if a.disabled_reason})
    note = f'<div class="ui2-cta__reason">{escape("；".join(reasons))}</div>' if reasons else ""
    return (f'<div class="ui2-account" data-ui2-l1="account_actions" '
            f'data-ui2-account="{escape(account.account_state)}">'
            f'<span class="ui2-q">帳戶管理（示意狀態：{escape(_ACCOUNT_STATE_LABEL.get(account.account_state, account.account_state))}）</span>'
            f'<div class="ui2-account__btns">{btns}</div>{note}</div>')


# ════════════════════════════════════════════════════════════════════
# P2（客戶 2026-11-04 (19)／DEC-133）：📊 台股 Primary 誠實空槽＋一行 SPEC
# ════════════════════════════════════════════════════════════════════
#: 空槽標題（客戶 DEC-117 Q4 原詞「🇹🇼 台股趨勢」；「Primary」是內部詞，不上畫面）。
PRIMARY_SLOT_TITLE = "🇹🇼 台股趨勢"
#: 空槽原因句（既有字樣家族「此項目尚未開放」，同 `real_canonical._R_PORT`；不新造字樣）。
PRIMARY_SLOT_REASON = "此項目尚未開放"
#: SPEC 行誠實性標示（客戶 (19)）：SPEC 引用的是 TWII 卡的「最新收盤」來源／資料日，不是歷史序列。
SPEC_REFERENCE_LABEL = "最新收盤參考"
#: 缺值政策字樣（政策字樣，非資料值；與 §1 Fail Loud 同向）。
SPEC_MISSING_POLICY = "缺值不補"
SPEC_PREFIX = "SPEC"


def spec_line_text(fresh: FreshnessInfo | None) -> str:
    """一行 SPEC：`SPEC｜最新收盤參考｜<來源>｜資料日 <as_of>｜缺值不補`（客戶 (19) G-2=B：省略頻率欄）。

    來源與資料日**只取 TWII 卡既有 freshness**（與卡逐字同值）：來源缺值→省略來源欄；as_of 缺→`TEXT_ASOF_MISSING`
    （⛔ 補推估日期、⛔ 寫死來源、⛔ 手寫「日頻」）。as_of 原樣（ISO），不轉換格式。
    """
    fresh = fresh or FreshnessInfo()
    parts = [SPEC_PREFIX, SPEC_REFERENCE_LABEL]
    if fresh.source:
        parts.append(fresh.source)
    parts.append(f"資料日 {fresh.as_of}" if fresh.as_of else TEXT_ASOF_MISSING)
    parts.append(SPEC_MISSING_POLICY)
    return "｜".join(parts)


def primary_slot_html(twii_card: CardVM | None) -> str:
    """台股 Primary 主圖**誠實空槽**（無正式歷史序列→不畫圖）：標題＋Capability 字樣 `⬜ 尚未提供`＋原因句（灰底，⛔ 紅）＋
    SPEC 行。依內容高度（客戶 (19) G-1=A，不預留 220px）。⛔ svg／polyline／canvas／img／假走勢／MA。

    空槽是 **Capability**（`capability` 軸），與卡的 Data State 正交：卡 Unavailable／Missing 不會把槽改紅。
    """
    fresh = twii_card.field.freshness if twii_card is not None else None
    chip = chip_html(TEXT_NOT_PROVIDED, ChipTone.NEUTRAL_INFO, axis="capability", state="not_provided")
    return ('<div class="ui2-primary-slot" data-ui2-l1="primary_slot" data-axis="capability" data-state="not_provided">'
            f'<div class="ui2-section-title">{escape(PRIMARY_SLOT_TITLE)}</div>'
            f'<div class="ui2-primary-slot__body">{chip}'
            f'<span class="ui2-primary-slot__reason">{escape(PRIMARY_SLOT_REASON)}</span></div>'
            f'<div class="ui2-primary-slot__spec" data-ui2-spec="1">{escape(spec_line_text(fresh))}</div></div>')


# ════════════════════════════════════════════════════════════════════
# Issue #1099 PR-2（DEC-156 A／B／A）：📊 台股加權指數日 K 主圖（取代誠實空槽，**只在** VM 帶日 K 事實時）
# ════════════════════════════════════════════════════════════════════
#: K 棒顏色（DEC-156 A：當日收盤 vs 當日開盤；色值沿用已核准視覺稿 NEWUI2_TWII_CANDLESTICK_VISUAL_PREVIEW 的 --red／--green／--muted）。
KBAR_COLOR: dict[str, str] = {"up": "#ef5564", "down": "#25be87", "flat": "#9aaec0"}
#: 文字圖例（顏色不是唯一載體；DEC-156 A 逐字語意：紅＝收盤＞開盤、綠＝收盤＜開盤、灰＝收盤＝開盤）。
KBAR_LEGEND: tuple[tuple[str, str], ...] = (("up", "紅｜收盤＞開盤"), ("down", "綠｜收盤＜開盤"), ("flat", "灰｜收盤＝開盤"))
KBAR_LEGEND_SEP = "　"
KBAR_SUBTITLE = "加權指數日 K｜單位：指數點｜顏色只比較當日開盤與收盤，不是相對前一日漲跌"
#: 圖高（DEC-156 B「約 220px」）：以 svg 的 height 屬性給在**圖本身**（有 K 棒才出現）；誠實空槽仍依內容高度（DEC-133 G-1=A）。
KBAR_PLOT_H = 220
_KB_TOP, _KB_BOTTOM_PAD = 8, 24          # 繪圖區上緣；底部留給起訖日期列
_KB_Y_AXIS_W = 52                        # 左側 y 軸刻度欄寬（px）
_KB_TICKS = 5
_KB_BODY_FRAC = 0.55                     # K 棒實體寬＝每根格寬的比例
_KB_MIN_BODY_H = 1.5                     # 開收同價（或極近）時實體最小可見高度（灰十字線的橫線）


def kbar_direction(open_: float, close: float) -> str:
    """DEC-156 A：`close>open` 紅（up）、`close<open` 綠（down）、`close==open` 灰十字（flat）。
    `==` 以極小容差判定（CLAUDE.md §4.3 浮點比較；只吸收浮點表示誤差，0.01 點的差仍分紅綠）。"""
    if math.isclose(close, open_, rel_tol=1e-12, abs_tol=1e-9):
        return "flat"
    return "up" if close > open_ else "down"


def kbar_legend_text() -> str:
    return KBAR_LEGEND_SEP.join(t for _, t in KBAR_LEGEND)


def _f(v: float) -> str:
    return f"{v:.2f}"


def _kbar_svg(kbar: KbarChartVM) -> str:
    """K 棒 svg：左欄 y 軸刻度（px 定寬）＋右欄 K 棒（x 用 %、y 用 px ⇒ 寬度自適應、文字不變形、無水平溢出）。
    ⛔ 成交量、均線、按鈕、拖曳／縮放（DEC-156 未核准）。"""
    cs = kbar.candles
    n = len(cs)
    lo, hi = min(c.low for c in cs), max(c.high for c in cs)
    span = hi - lo
    pad = span * 0.06 if span > 0 else max(abs(hi) * 0.001, 1.0)
    lo_p, hi_p = lo - pad, hi + pad
    h = KBAR_PLOT_H
    y0, y1 = _KB_TOP, h - _KB_BOTTOM_PAD

    def yt(v: float) -> float:
        return y0 + (hi_p - v) / (hi_p - lo_p) * (y1 - y0)

    ticks = [hi_p - i * (hi_p - lo_p) / (_KB_TICKS - 1) for i in range(_KB_TICKS)]
    yaxis = "".join(
        f'<text x="{_KB_Y_AXIS_W - 6}" y="{_f(yt(t) + 3.5)}" text-anchor="end" font-size="10" fill="currentColor" '
        f'fill-opacity="0.75">{escape(f"{t:,.0f}")}</text>' for t in ticks)
    grid = "".join(f'<line x1="0" x2="100%" y1="{_f(yt(t))}" y2="{_f(yt(t))}" stroke="currentColor" '
                   f'stroke-opacity="0.18" stroke-width="1"/>' for t in ticks)
    slot = 100.0 / n
    bw = slot * _KB_BODY_FRAC
    bars = []
    for i, c in enumerate(cs):
        d = kbar_direction(c.open, c.close)
        col = KBAR_COLOR[d]
        cx = (i + 0.5) * slot
        top = yt(max(c.open, c.close))
        bh = max(_KB_MIN_BODY_H, abs(yt(c.open) - yt(c.close)))
        bars.append(
            f'<g class="ui2-kbar__c ui2-kbar__c--{d}" data-kbar-dir="{d}" data-kbar-date="{escape(c.date)}">'
            f'<line x1="{_f(cx)}%" x2="{_f(cx)}%" y1="{_f(yt(c.high))}" y2="{_f(yt(c.low))}" stroke="{col}" stroke-width="1.5"/>'
            f'<rect x="{_f(cx - bw / 2)}%" y="{_f(top)}" width="{_f(bw)}%" height="{_f(bh)}" fill="{col}"/></g>')
    first, last = cs[0].date, cs[-1].date
    dates = ((f'<text x="0" y="{h - 6}" text-anchor="start" font-size="10" fill="currentColor" fill-opacity="0.75">'
              f'{escape(first)}</text>') if n > 1 else "") + (
        f'<text x="100%" y="{h - 6}" text-anchor="end" font-size="10" fill="currentColor" fill-opacity="0.75">'
        f'{escape(last)}</text>')
    label = (f"台股加權指數日 K，{first} 至 {last} 共 {n} 根；紅＝收盤高於開盤，綠＝收盤低於開盤，灰＝收盤等於開盤"
             if n > 1 else f"台股加權指數日 K，{last} 共 1 根；紅＝收盤高於開盤，綠＝收盤低於開盤，灰＝收盤等於開盤")
    return (f'<div class="ui2-kbar__plot" data-ui2-kbar-plot="1">'
            f'<svg class="ui2-kbar__yaxis" width="{_KB_Y_AXIS_W}" height="{h}" aria-hidden="true">{yaxis}</svg>'
            f'<svg class="ui2-kbar__svg" width="100%" height="{h}" role="img" aria-label="{escape(label)}">'
            f'{grid}{"".join(bars)}{dates}</svg></div>')


def kbar_meta_text(fresh: FreshnessInfo) -> str:
    """圖下一行：資料日（缺→`⬜ 資料日未提供`，⛔ 補推估日期）｜來源（缺→省略）｜缺值不補。"""
    parts = [f"資料日 {fresh.as_of}" if fresh.as_of else TEXT_ASOF_MISSING]
    if fresh.source:
        parts.append(fresh.source)
    parts.append(SPEC_MISSING_POLICY)
    return "｜".join(parts)


def kbar_chart_html(kbar: KbarChartVM) -> str:
    """📊 台股日 K 主圖（Issue #1099 PR-2）。放在原誠實空槽的位置（同一個 markdown 區塊），版面其餘不動。

    - OK／Stale：K 棒＋y 軸刻度＋起訖日期＋文字圖例＋資料日／來源；Stale 另有與 TWII 卡相同的 `⚠` 字樣（照畫，資料是真歷史但舊）。
    - 不足 20 根：照實少畫＋「僅 N 根（不足 20）」（⛔ 補棒）。
    - Missing／無法判定（灰）、Unavailable（紅，系統真錯誤）：0 個圖形、狀態字樣＋一句人話原因（CLAUDE.md §1.A 第 4 點灰紅分離）。
    """
    f = kbar.field
    has_bars = bool(kbar.candles)
    reason = f'<span class="ui2-kbar__reason">{escape(f.detail)}</span>' if shown(f.detail) else ""
    chip = status_chip_html(f)
    status = f'<div class="ui2-kbar__status" data-ui2-kbar-status="1">{chip}{reason}</div>' if (chip or reason) else ""
    body = ""
    if has_bars:
        legend = "".join(
            (KBAR_LEGEND_SEP if i else "")
            + f'<span class="ui2-kbar__sw ui2-kbar__sw--{d}" data-kbar-sw="{d}"></span>{escape(t)}'
            for i, (d, t) in enumerate(KBAR_LEGEND))
        notes = "".join(f'<div class="ui2-kbar__note" data-ui2-kbar-note="1">{escape(n)}</div>' for n in kbar.notes)
        body = (_kbar_svg(kbar) + f'<div class="ui2-kbar__legend" data-ui2-kbar-legend="1">{legend}</div>' + notes)
    sub = f'<div class="ui2-kbar__sub">{escape(KBAR_SUBTITLE)}</div>' if has_bars else ""
    return (f'<div class="ui2-kbar" data-ui2-l1="primary_chart" data-axis="{f.layer}" data-state="{_state_attr(f)}">'
            f'<div class="ui2-section-title">{escape(PRIMARY_SLOT_TITLE)}</div>{sub}{status}{body}'
            f'<div class="ui2-kbar__meta" data-ui2-kbar-meta="1">{escape(kbar_meta_text(f.freshness))}</div></div>')


# ════════════════════════════════════════════════════════════════════
# DEC-146：頂部導覽第一列（Active Sheet 狀態＋帳號入口狀態；固定占位）
# ════════════════════════════════════════════════════════════════════
TOP_SHEET_LABEL = "Active Sheet"
TOP_ACCOUNT_LABEL = "帳號"


def top_status_row_html(banner_text: str | None = None, banner_note: str = "", *, note_hidden_on_mobile: bool = False) -> str:
    """頂部第一列：Active Sheet 狀態｜資料模式標示（FAKE 示意資料／Real-data Preview；DEC-146 方案 A 併入）｜帳號入口狀態。

    Active Sheet／帳號：**零輸入、固定占位**（⛔ 讀 `ui2_account`／`ui2_dev`／query／session；⛔ 宣稱已登入／未登入／已選 Sheet）。
    `⬜ 尚未提供` 屬 **Capability 軸**（DEC-124／DEC-130；功能尚未接線）；不是按鈕、不可聚焦、不可觸發（正式 Auth／Sheet 契約之前）。
    模式標示＝既有 `banner_html`（文字契約 `PREVIEW_BANNER_*`／`REAL_PREVIEW_BANNER_*` 不變；`role=note`），只是位置從頁首獨立一行
    併入本列（省下一個容器與其間距）。桌機（≥769px）本列單行（Sheet｜標示｜帳號）；手機本列固定分兩行
    （標示一行、Sheet／帳號一行；CSS 以固定高度讓位），⛔ 截斷或隱藏標示文字。"""
    chip = chip_html(TEXT_NOT_PROVIDED, ChipTone.NEUTRAL_INFO, axis="capability", state="not_provided")
    mode = (f'<span class="ui2-top1__mode" data-ui2-top-item="mode">'
            f'{banner_html(banner_text, banner_note, note_hidden_on_mobile=note_hidden_on_mobile)}</span>') if banner_text else ""
    return ('<div class="ui2-top1" data-ui2-top="status" data-axis="capability" data-state="not_provided">'
            f'<span class="ui2-top1__item" data-ui2-top-item="sheet">{escape(TOP_SHEET_LABEL)} {chip}</span>'
            f'{mode}'
            f'<span class="ui2-top1__item" data-ui2-top-item="account">{escape(TOP_ACCOUNT_LABEL)} {chip}</span></div>')
