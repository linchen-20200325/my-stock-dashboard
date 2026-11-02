"""VM 共用純函式：canonical spec → L0 VM 型別。

輸入 spec（dict）鍵：label／value／as_of／source／state／stale_days／reason／sub_reason／missing_kind。
規則（Freeze §5；DEC-124）：value 為 None 且無明示態 → MISSING（⛔ 補 0／中性／續抱／safe）；
明示 unavailable／not_evaluated／undeterminable／not_provided 時**丟棄** value（unavailable ≠ safe；
無法判定 ≠ safe）。`state` 提示只收 `SPEC_STATE_HINTS`，其餘 → raise（⛔ 未知態默默落成 OK）。
- `not_evaluated`（資料語意）＝規則／計算尚未執行或不在本次評估範圍。
- `undeterminable`（判定結果）＝已進入判定、必要輸入不足／不可得／無效；⛔ 映射成 not_evaluated。
- `not_provided`（capability marker，Preview-only）＝功能尚未實作／接線；`state` 為 None。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from shared.ui2_contract.models import (
    CapabilityState, CardVM, CtaVM, FieldState, FieldVM, FirstScreenVM, FreshnessInfo,
    JudgementState, PageContext, PageVM, PresentationSlice, SectionVM,
)
from shared.ui2_contract.text import (
    PREVIEW_BANNER_TEXT, TEXT_MISSING_NOT_FETCHED, TEXT_MISSING_NOT_READY,
    TEXT_NOT_EVALUATED, TEXT_NOT_PROVIDED, TEXT_NOT_PROVIDED_AGGREGATOR,
    TEXT_RISK_CAP_UNDETERMINABLE, TEXT_UNAVAILABLE, stale_text,
)

Spec = Mapping[str, Any]

#: canonical spec 的 `state` 提示白名單（None＝依 value 判 OK／MISSING）。
SPEC_STATE_HINTS = frozenset({None, "stale", "unavailable", "not_evaluated", "undeterminable",
                              "not_provided"})

#: 這些頁的 `action_needed` 不得由 canonical 提供（Aggregator 未實作；VM ⛔ 創造動作）。
PAGES_ACTION_FROM_AGGREGATOR_ONLY = frozenset({"p4_market", "p4_hold"})


def field_from_spec(spec: Spec) -> FieldVM:
    label = str(spec["label"])
    fresh = FreshnessInfo(as_of=spec.get("as_of"), source=spec.get("source"))
    hint = spec.get("state")
    value = spec.get("value")
    detail = spec.get("reason")
    if hint not in SPEC_STATE_HINTS:
        raise ValueError(f"{label}: 未知 state 提示 {hint!r}（允許 {sorted(map(str, SPEC_STATE_HINTS))}）")
    if hint == "unavailable":
        return FieldVM(label, FieldState.UNAVAILABLE, None, TEXT_UNAVAILABLE, detail, fresh)
    if hint == "not_evaluated":
        return FieldVM(label, FieldState.NOT_EVALUATED, None,
                       spec.get("sub_reason") or TEXT_NOT_EVALUATED, detail, fresh)
    if hint == "undeterminable":
        return FieldVM(label, JudgementState.UNDETERMINABLE, None,
                       spec.get("sub_reason") or TEXT_RISK_CAP_UNDETERMINABLE, detail, fresh)
    if hint == "not_provided":
        return FieldVM(label, None, None, spec.get("sub_reason") or TEXT_NOT_PROVIDED, detail, fresh,
                       capability=CapabilityState.NOT_PROVIDED)
    if value is None:
        status = (TEXT_MISSING_NOT_READY if spec.get("missing_kind") == "not_ready"
                  else TEXT_MISSING_NOT_FETCHED)
        return FieldVM(label, FieldState.MISSING, None, status, detail, fresh)
    if hint == "stale":
        return FieldVM(label, FieldState.STALE, str(value),
                       stale_text(spec.get("stale_days")), detail, fresh)
    return FieldVM(label, FieldState.OK, str(value), None, detail, fresh)


def card_from_spec(spec: Spec) -> CardVM:
    return CardVM(card_id=str(spec["key"]), title=str(spec["label"]),
                  field=field_from_spec(spec))


def section_from_spec(spec: Spec) -> SectionVM:
    return SectionVM(section_id=str(spec["key"]), title=str(spec["title"]),
                     level=str(spec["level"]),
                     fields=tuple(field_from_spec(f) for f in spec.get("fields", ())))


def aggregator_pending_field(label: str) -> FieldVM:
    """動作欄：Aggregator 未實作 → `⬜ 尚未提供（待 System Action Aggregator）`（僅 Preview 期；Gate §4.6.5）。

    capability marker（DEC-124）：⛔ 帶資料語意、⛔ 讀成「今日無需調整」或「無法判定」。
    """
    return FieldVM(label, None, None, TEXT_NOT_PROVIDED_AGGREGATOR,
                   "動作權威尚未實作（Preview）", FreshnessInfo(),
                   capability=CapabilityState.NOT_PROVIDED)


def build_page_vm(canonical: Spec, *, top_n: int | None = None) -> PageVM:
    """canonical → PageVM。`top_n` 只影響 `slice`，⛔ 影響 `context`（Gate §4.2-6／G3）。"""
    page = str(canonical["page"])
    if page in PAGES_ACTION_FROM_AGGREGATOR_ONLY:
        if canonical.get("action_needed") is not None:
            raise ValueError(f"{page}: canonical 不得提供 action_needed（VM 不創造動作；待 Aggregator）")
        action = aggregator_pending_field("是否需要行動")
    else:
        spec = canonical.get("action_needed")
        action = field_from_spec(spec) if spec is not None else aggregator_pending_field("是否需要行動")
    nxt = canonical.get("next_step")
    next_step = field_from_spec(nxt) if nxt is not None else aggregator_pending_field("下一步")
    cta_spec = canonical["cta"]
    first = FirstScreenVM(
        current_state=field_from_spec(canonical["current_state"]),
        action_needed=action,
        next_step=next_step,
        primary_cta=CtaVM(label=str(cta_spec["label"]), enabled=False,
                          disabled_reason=str(cta_spec.get("disabled_reason", "Preview：不觸發任何動作"))),
        context_rows=tuple(field_from_spec(s) for s in canonical.get("context_rows", ())),
    )
    cards = tuple(card_from_spec(s) for s in canonical.get("cards", ()))
    sections = tuple(section_from_spec(s) for s in canonical.get("sections", ()))
    ids = tuple(c.card_id for c in cards)
    visible = ids if top_n is None else ids[: max(int(top_n), 0)]
    return PageVM(
        page_id=page, title=str(canonical["title"]), scenario_id=str(canonical["scenario"]),
        is_fake=bool(canonical.get("is_fake", False)),
        context=PageContext(first_screen=first, cards=cards, sections=sections),
        slice=PresentationSlice(top_n=top_n, visible_card_ids=visible),
        banner_text=PREVIEW_BANNER_TEXT if canonical.get("is_fake") else None,
    )


def spec_list(items: Sequence[Spec]) -> list[dict]:
    return [dict(i) for i in items]
