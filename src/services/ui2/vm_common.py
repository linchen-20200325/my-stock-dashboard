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
    AccountVM, CandleVM, CapabilityState, CardVM, ChipVM, CtaVM, FieldState, FieldVM, FirstScreenVM,
    FreshnessInfo, JudgementState, KbarChartVM, LookupResultVM, ModeOptionVM, PageContext, PageVM,
    PresentationSlice, SearchBoxVM, SectionVM, TargetVM,
)
from shared.ui2_contract.pages import (
    ACCOUNT_IDS, MODE_CURATED, MODE_IDS, P4_ME, P4_MARKET, P4_TARGET, SCENARIO_IDS, SCENARIO_REAL,
)
from shared.ui2_contract.tones import ChipTone
from shared.ui2_contract.text import (
    PREVIEW_BANNER_TEXT, REAL_PREVIEW_BANNER_TEXT, TEXT_MISSING_NOT_FETCHED, TEXT_MISSING_NOT_READY,
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
                     fields=tuple(field_from_spec(f) for f in spec.get("fields", ())),
                     mode=spec.get("mode"))


def cta_from_spec(spec: Spec, default_reason: str) -> CtaVM:
    """CTA 一律 disabled（Preview：⛔ 觸發任何更新／寫入／OAuth／查詢）。"""
    return CtaVM(label=str(spec["label"]), enabled=False,
                 disabled_reason=str(spec.get("disabled_reason", default_reason)))


def target_from_canonical(spec: Spec) -> TargetVM:
    """🎯 標的頁 canonical → TargetVM。模式內容全量保留；⛔ 依模式裁掉 context。"""
    modes = tuple(ModeOptionVM(str(m["id"]), str(m["label"])) for m in spec["modes"])
    if tuple(m.mode_id for m in modes) != MODE_IDS:
        raise ValueError(f"標的頁模式須恰為 {MODE_IDS}，收到 {[m.mode_id for m in modes]}")
    srch = spec["search"]
    lk = spec["lookup"]
    add = lk["add_watch"]
    return TargetVM(
        modes=modes, default_mode=str(spec.get("default_mode", MODE_CURATED)),
        search=SearchBoxVM(
            placeholder=str(srch["placeholder"]),
            name_search=field_from_spec(srch["name_search"]),
            cta=cta_from_spec(srch["cta"], "尚未開放查詢")),
        lookup=LookupResultVM(
            ticker_text=str(lk["ticker"]), name_text=str(lk["name"]),
            chips=tuple(ChipVM(str(t), ChipTone.NEUTRAL_INFO) for t in lk["chips"]),
            summary=field_from_spec(lk["summary"]),
            snapshot=tuple(field_from_spec(f) for f in lk["snapshot"]),
            add_watch_cta=CtaVM(label=str(add["label"]), enabled=False,
                                disabled_reason=str(add["disabled_reason"])),
            isolation_note=str(lk["isolation_note"]),
            sections=tuple(section_from_spec(x) for x in lk.get("sections", ())),
            queried=bool(lk.get("queried", True))))


def account_from_canonical(spec: Spec) -> AccountVM:
    st_ = str(spec["account_state"])
    if st_ not in ACCOUNT_IDS:
        raise ValueError(f"未知帳戶狀態 {st_!r}（允許 {ACCOUNT_IDS}）")
    return AccountVM(account_state=st_, actions=tuple(
        cta_from_spec(a, "登入與 Sheet 操作尚未開放") for a in spec["actions"]))


def kbar_from_spec(spec: Spec) -> KbarChartVM:
    """📊 台股日 K canonical spec → `KbarChartVM`（Issue #1099 PR-2）。原樣搬運（⛔ 補棒、⛔ 排序／去重修補——
    不合法交給 `CandleVM`／`KbarChartVM` 建構時 raise）。"""
    return KbarChartVM(
        field=field_from_spec(spec["field"]),
        candles=tuple(CandleVM(date=str(c["date"]), open=c["open"], high=c["high"], low=c["low"], close=c["close"])
                      for c in spec.get("candles", ())),
        target_n=int(spec["target_n"]),
        notes=tuple(str(n) for n in spec.get("notes", ())))


def aggregator_pending_field(label: str) -> FieldVM:
    """動作欄：Aggregator 未實作 → `⬜ 尚未提供（待 System Action Aggregator）`（僅 Preview 期；Gate §4.6.5）。

    capability marker（DEC-124）：⛔ 帶資料語意、⛔ 讀成「今日無需調整」或「無法判定」。
    """
    return FieldVM(label, None, None, TEXT_NOT_PROVIDED_AGGREGATOR,
                   "動作判斷功能尚未開放", FreshnessInfo(),
                   capability=CapabilityState.NOT_PROVIDED)


def _banner_for(canonical: Spec) -> str | None:
    """頁首標示：FAKE 場景 → `PREVIEW_BANNER_TEXT`；Real-data Preview（`scenario`＝`real`）→
    `REAL_PREVIEW_BANNER_TEXT`（NUI2-REAL-FEED）。兩軸 ⛔ 混用：FAKE 不得標 real、real 不得用 FAKE 場景 id。"""
    is_fake = bool(canonical.get("is_fake", False))
    scenario = canonical.get("scenario")
    if is_fake and scenario == SCENARIO_REAL:
        raise ValueError("FAKE canonical 不得使用 real 場景 id（Real／Fake feed 必須可區分）")
    if not is_fake and scenario in SCENARIO_IDS:
        raise ValueError(f"非 FAKE canonical 不得使用 FAKE 場景 id {scenario!r}（Real／Fake feed 必須可區分）")
    if is_fake:
        return PREVIEW_BANNER_TEXT
    return REAL_PREVIEW_BANNER_TEXT if scenario == SCENARIO_REAL else None


def build_page_vm(canonical: Spec, *, top_n: int | None = None, mode: str | None = None) -> PageVM:
    """canonical → PageVM。`top_n`／`mode` 只影響 `slice`，⛔ 影響 `context`（Gate §4.2-6／G3）。"""
    page = str(canonical["page"])
    banner = _banner_for(canonical)
    for key, only in (("conclusion", P4_MARKET), ("main_risk", P4_MARKET), ("kbar", P4_MARKET),
                      ("target", P4_TARGET), ("account", P4_ME)):
        if canonical.get(key) is not None and page != only:
            raise ValueError(f"{page}: canonical 不得提供 {key}（僅 {only} 頁）")
    if mode is not None and mode not in MODE_IDS:
        raise ValueError(f"未知模式 {mode!r}（允許 {MODE_IDS}）")
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
                          disabled_reason=str(cta_spec.get("disabled_reason", "此功能尚未開放"))),
        context_rows=tuple(field_from_spec(s) for s in canonical.get("context_rows", ())),
        conclusion=(field_from_spec(canonical["conclusion"])
                    if canonical.get("conclusion") is not None else None),
    )
    cards = tuple(card_from_spec(s) for s in canonical.get("cards", ()))
    sections = tuple(section_from_spec(s) for s in canonical.get("sections", ()))
    target = (target_from_canonical(canonical["target"])
              if canonical.get("target") is not None else None)
    account = (account_from_canonical(canonical["account"])
               if canonical.get("account") is not None else None)
    ids = tuple(c.card_id for c in cards)
    visible = ids if top_n is None else ids[: max(int(top_n), 0)]
    active_mode = None
    if target is not None:
        active_mode = mode or target.default_mode
        if active_mode != MODE_CURATED:
            visible = ()            # 查一檔模式：精選收合（呈現切片；context.cards 不變）
    return PageVM(
        page_id=page, title=str(canonical["title"]), scenario_id=str(canonical["scenario"]),
        is_fake=bool(canonical.get("is_fake", False)),
        context=PageContext(
            first_screen=first, cards=cards, sections=sections,
            main_risk=(field_from_spec(canonical["main_risk"])
                       if canonical.get("main_risk") is not None else None),
            target=target, account=account,
            kbar=(kbar_from_spec(canonical["kbar"]) if canonical.get("kbar") is not None else None)),
        slice=PresentationSlice(top_n=top_n, visible_card_ids=visible, active_mode=active_mode),
        banner_text=banner,
    )


def spec_list(items: Sequence[Spec]) -> list[dict]:
    return [dict(i) for i in items]
