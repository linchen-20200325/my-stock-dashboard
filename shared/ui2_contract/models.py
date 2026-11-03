"""View Model 型別（frozen dataclass）—— New UI2 Presentation Contract。

規則（Architecture Gate §4.2／§4.3；Freeze §5／§9／§13；DEC-124）：
- 純資料：⛔ I/O、⛔ streamlit、⛔ 計算投資語意。
- 缺值 ≠ 0：`value_text` 只在 OK／STALE 態可有值；其餘態必為 None（建構時強制）。
- 每個欄位帶 field-level `FreshnessInfo(as_of, source)`；⛔ 共用全域更新時間。
- `PageVM.context`（全量）與 `PageVM.slice`（呈現切片）分離；slice 只能由 context 截取。

═══ 三個互不混層的語意軸（客戶 2026-11-02 Semantic Correction Gate；DEC-124）═══
1. `FieldState`＝**正式資料語意**，只有五個：OK／Missing／Stale／Unavailable／Not Evaluated。
   Not Evaluated＝「這項規則／計算尚未執行或不在本次評估範圍」。
2. `JudgementState`＝**判定結果**（不是資料語意）：`UNDETERMINABLE`＝Unable to Determine
   ＝「有進入判定流程，但因必要輸入 Missing／Unavailable／Invalid／insufficient，無法得到正式結果」。
   ⛔ 與 Not Evaluated 合併；⛔ 推導 safe／neutral／no action／無需調整／可加碼；⛔ 帶 value。
3. `CapabilityState`＝**Capability／Implementation Availability State**（與 1、2 正交；Preview-only）：
   `NOT_PROVIDED`（`⬜ 尚未提供`）＝功能尚未實作／尚未接線。**不是** objective data quality state，
   **不是**「第 6 個正式資料語意態」。`NOT_PROVIDED` 欄位的 `state` 必為 None（資料語意不適用）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared.ui2_contract.text import (
    ALLOWED_STATUS_PREFIXES, CAPABILITY_STATUS_PREFIXES, JUDGEMENT_STATUS_PREFIXES,
)
from shared.ui2_contract.tones import ChipTone


class FieldState(str, Enum):
    """正式資料語意（DEC-124：只有這五個，含 OK）。⛔ 在此加入 capability marker 或判定結果。"""

    OK = "ok"
    MISSING = "missing"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    NOT_EVALUATED = "not_evaluated"   # 規則／計算尚未執行或不在本次評估範圍


class JudgementState(str, Enum):
    """判定結果（非資料語意；DEC-124）。≠ `FieldState.NOT_EVALUATED`，兩者禁止合併。"""

    UNDETERMINABLE = "undeterminable"   # 已進入判定流程，但必要輸入不足／不可得／無效 → 無正式結果


class CapabilityState(str, Enum):
    """Capability／Implementation Availability（與資料語意正交；DEC-124）。

    `NOT_PROVIDED`＝Preview-only implementation marker（例：System Action Aggregator／OneBrain 尚未實作、
    某 Preview 功能尚未接線）。只允許 Preview 期 producer 使用（守衛：tests/test_ui2_guards.py）。
    """

    PROVIDED = "provided"
    NOT_PROVIDED = "not_provided"


#: 正式資料語意五態（DEC-124）；守衛釘死「恰為這五個」。
DATA_SEMANTIC_STATES = frozenset(FieldState)

#: 這些態「有值可顯示」；其餘態 value_text 必為 None（missing ≠ 0；unavailable ≠ safe；無法判定 ≠ safe）。
VALUE_BEARING_STATES = frozenset({FieldState.OK, FieldState.STALE})


def status_prefixes_for(state: FieldState | JudgementState | CapabilityState) -> tuple[str, ...]:
    """各軸各自的允許字樣表（三張表互斥；⛔ 混查）。"""
    if isinstance(state, FieldState):
        return ALLOWED_STATUS_PREFIXES[state.value]
    if isinstance(state, JudgementState):
        return JUDGEMENT_STATUS_PREFIXES[state.value]
    if isinstance(state, CapabilityState):
        return CAPABILITY_STATUS_PREFIXES[state.value]
    raise TypeError(f"未知語意軸：{state!r}")


@dataclass(frozen=True)
class FreshnessInfo:
    """field-level 新鮮度。缺 → None（呈現層顯示 `⬜ 資料日未提供`），⛔ 補推估日期。"""

    as_of: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class FieldVM:
    """單一欄位：label／value／state／status_text／freshness／capability。

    - `capability=PROVIDED`（預設）：`state` 必為 `FieldState`（資料語意）或 `JudgementState`（判定結果）。
    - `capability=NOT_PROVIDED`：`state` 必為 None、`value_text` 必為 None、字樣屬 `⬜ 尚未提供` 家族。
    """

    label: str
    state: FieldState | JudgementState | None
    value_text: str | None = None
    status_text: str | None = None      # L1 外露狀態字樣（OK 態可為 None）
    detail: str | None = None           # 例：Unavailable 的一句原因
    freshness: FreshnessInfo = FreshnessInfo()
    capability: CapabilityState = CapabilityState.PROVIDED

    def __post_init__(self) -> None:
        if not isinstance(self.capability, CapabilityState):
            raise TypeError(f"{self.label}: capability 必須是 CapabilityState，收到 {self.capability!r}")
        if self.capability is CapabilityState.NOT_PROVIDED:
            if self.state is not None:
                raise ValueError(f"{self.label}: capability marker 與資料語意正交，NOT_PROVIDED 不得帶 state")
            if self.value_text is not None:
                raise ValueError(f"{self.label}: NOT_PROVIDED 不得帶 value_text")
            allowed = CAPABILITY_STATUS_PREFIXES[self.capability.value]
            if self.status_text is None or not self.status_text.startswith(allowed):
                raise ValueError(f"{self.label}: status_text={self.status_text!r} 不屬於 {allowed}")
            return
        if not isinstance(self.state, (FieldState, JudgementState)):
            raise TypeError(f"{self.label}: state 必須是 FieldState／JudgementState，收到 {self.state!r}")
        if self.state not in VALUE_BEARING_STATES and self.value_text is not None:
            raise ValueError(
                f"{self.label}: state={self.state.value} 不得帶 value_text（missing ≠ 0；無法判定 ≠ safe）")
        if self.state in VALUE_BEARING_STATES and self.value_text is None:
            raise ValueError(f"{self.label}: state={self.state.value} 必須有 value_text")
        allowed = status_prefixes_for(self.state)
        if self.state is FieldState.OK:
            if self.status_text is not None:
                raise ValueError(f"{self.label}: OK 態不外露狀態字樣")
        else:
            if self.status_text is None or not self.status_text.startswith(allowed):
                raise ValueError(
                    f"{self.label}: status_text={self.status_text!r} 不屬於 "
                    f"{self.state.value} 態的允許字樣 {allowed}")

    @property
    def layer(self) -> str:
        """語意軸：`data`／`judgement`／`capability`。"""
        if self.capability is CapabilityState.NOT_PROVIDED:
            return "capability"
        return "judgement" if isinstance(self.state, JudgementState) else "data"

    def allowed_status_prefixes(self) -> tuple[str, ...]:
        return status_prefixes_for(
            self.capability if self.capability is CapabilityState.NOT_PROVIDED else self.state)


@dataclass(frozen=True)
class ChipVM:
    text: str
    tone: ChipTone


@dataclass(frozen=True)
class CardVM:
    """資料卡：value／short state／as_of／source（Freeze §9-1）。"""

    card_id: str
    title: str
    field: FieldVM
    chips: tuple[ChipVM, ...] = ()


@dataclass(frozen=True)
class CtaVM:
    """主 CTA 描述。Preview 期 enabled=False（⛔ 觸發任何更新／寫入）。"""

    label: str
    enabled: bool = False
    disabled_reason: str | None = None


@dataclass(frozen=True)
class FirstScreenVM:
    """每頁第一屏四問（客戶 (5)-9）：現在狀態／是否需要行動／下一步／主 CTA。

    `conclusion`（📊 市場頁專用；Batch 3）＝今日結論一行（DEC-081 Q2-1：各判斷獨立並列、缺值明寫）。
    VM **原樣帶出** canonical 提供的句子，⛔ 由位階／指標推導多空、⛔ 新增動作。
    """

    current_state: FieldVM
    action_needed: FieldVM
    next_step: FieldVM
    primary_cta: CtaVM
    context_rows: tuple[FieldVM, ...] = ()   # 例：Risk Cap 一行
    conclusion: FieldVM | None = None


@dataclass(frozen=True)
class SectionVM:
    """L2／L3 摺疊區塊。`mode`＝所屬模式（🎯 標的頁雙模式；None＝與模式無關）。"""

    section_id: str
    title: str
    level: str                      # "L1" | "L2" | "L3"
    fields: tuple[FieldVM, ...] = ()
    mode: str | None = None


@dataclass(frozen=True)
class SearchBoxVM:
    """🎯 標的頁搜尋框（Preview 期為 disabled 示意；⛔ 真查詢／真資料 fetch）。"""

    placeholder: str
    name_search: FieldVM            # 名稱搜尋尚未提供（capability；FUI-NAME-SEARCH）
    cta: CtaVM


@dataclass(frozen=True)
class LookupResultVM:
    """🎯 即時查一檔的 FAKE 結果（Ad-hoc、session-only；⛔ 寫入持股／觀察／候選池／Sheet）。

    `snapshot`＝6 維 Snapshot（state＋短句）；`add_watch_cta`＝加入觀察，Preview 恆 disabled。
    """

    ticker_text: str
    name_text: str
    chips: tuple[ChipVM, ...]
    summary: FieldVM                # 查詢摘要（查一檔模式的 ①）
    snapshot: tuple[FieldVM, ...]
    add_watch_cta: CtaVM
    isolation_note: str
    sections: tuple[SectionVM, ...] = ()
    #: False＝尚未查詢（cold）：只畫灰色說明，⛔ 結果頭／Snapshot／加入觀察（Wireframes §6）。
    queried: bool = True


@dataclass(frozen=True)
class ModeOptionVM:
    mode_id: str
    label: str


@dataclass(frozen=True)
class TargetVM:
    """🎯 標的頁：雙模式（市場精選／即時查一檔）＋搜尋框＋查一檔 FAKE 結果。

    兩個模式的內容**都在 context**（完整 Decision Context 不因呈現切換而減少）；
    哪一個展開只由 `PresentationSlice.active_mode` 決定（Presentation Slice ≠ Decision Context）。
    """

    modes: tuple[ModeOptionVM, ...]
    default_mode: str
    search: SearchBoxVM
    lookup: LookupResultVM


@dataclass(frozen=True)
class AccountVM:
    """👤 我的頁帳戶／登入切換 skeleton（FAKE；⛔ 真 Google OAuth／Sheet 讀寫）。

    `account_state`＝`signed_out`／`signed_in`／`unavailable`（連線事實，fake 場景維度；
    **不是**資料語意態、capability 或判定結果）。`actions`＝管理動作（Preview 恆 disabled）。
    """

    account_state: str
    actions: tuple[CtaVM, ...]


@dataclass(frozen=True)
class PageContext:
    """全量 Decision Context —— 與任何 UI 切片（Top-N／收合／tab）無關。"""

    first_screen: FirstScreenVM
    cards: tuple[CardVM, ...] = ()
    sections: tuple[SectionVM, ...] = ()
    #: 📊 市場頁「今日主要風險」：L1，緊接第一屏之後、⛔ 被 L2／L3 插隊（Freeze §0.1.6-3）。
    main_risk: FieldVM | None = None
    target: TargetVM | None = None          # 🎯 標的頁專用
    account: AccountVM | None = None        # 👤 我的頁專用


@dataclass(frozen=True)
class PresentationSlice:
    """呈現切片：只能由 context 截取（⛔ 反向影響 context）。"""

    top_n: int | None
    visible_card_ids: tuple[str, ...]
    #: 🎯 標的頁目前展開的模式（其餘模式收合；⛔ 同時完整展開）。其他頁 None。
    active_mode: str | None = None


@dataclass(frozen=True)
class PageVM:
    page_id: str            # `shared.ia_nav4` 的 P4_* id
    title: str
    scenario_id: str
    is_fake: bool
    context: PageContext
    slice: PresentationSlice
    banner_text: str | None = None
