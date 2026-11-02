"""View Model 型別（frozen dataclass）—— New UI2 Presentation Contract。

規則（Architecture Gate §4.2／§4.3；Freeze §5／§9／§13）：
- 純資料：⛔ I/O、⛔ streamlit、⛔ 計算投資語意。
- 缺值 ≠ 0：`value_text` 只在 OK／STALE 態可有值；其餘態必為 None（建構時強制）。
- 每個欄位帶 field-level `FreshnessInfo(as_of, source)`；⛔ 共用全域更新時間。
- `PageVM.context`（全量）與 `PageVM.slice`（呈現切片）分離；slice 只能由 context 截取。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from shared.ui2_contract.text import ALLOWED_STATUS_PREFIXES
from shared.ui2_contract.tones import ChipTone


class FieldState(str, Enum):
    """語意態：OK＋四態（Freeze §5）＋功能尚未提供（四態之外，Freeze §5.3）。"""

    OK = "ok"
    MISSING = "missing"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    NOT_EVALUATED = "not_evaluated"
    NOT_PROVIDED = "not_provided"   # 功能尚未提供（≠ Unavailable）


#: 這些態「有值可顯示」；其餘態 value_text 必為 None（missing ≠ 0；unavailable ≠ safe）。
VALUE_BEARING_STATES = frozenset({FieldState.OK, FieldState.STALE})


@dataclass(frozen=True)
class FreshnessInfo:
    """field-level 新鮮度。缺 → None（呈現層顯示 `⬜ 資料日未提供`），⛔ 補推估日期。"""

    as_of: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class FieldVM:
    """單一欄位：label／value／state／status_text／freshness。"""

    label: str
    state: FieldState
    value_text: str | None = None
    status_text: str | None = None      # L1 外露狀態字樣（OK 態可為 None）
    detail: str | None = None           # 例：Unavailable 的一句原因
    freshness: FreshnessInfo = FreshnessInfo()

    def __post_init__(self) -> None:
        if self.state not in VALUE_BEARING_STATES and self.value_text is not None:
            raise ValueError(
                f"{self.label}: state={self.state.value} 不得帶 value_text（missing ≠ 0）")
        if self.state in VALUE_BEARING_STATES and self.value_text is None:
            raise ValueError(f"{self.label}: state={self.state.value} 必須有 value_text")
        allowed = ALLOWED_STATUS_PREFIXES[self.state.value]
        if self.state is FieldState.OK:
            if self.status_text is not None:
                raise ValueError(f"{self.label}: OK 態不外露狀態字樣")
        else:
            if self.status_text is None or not self.status_text.startswith(allowed):
                raise ValueError(
                    f"{self.label}: status_text={self.status_text!r} 不屬於 "
                    f"{self.state.value} 態的允許字樣 {allowed}")


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
    """每頁第一屏四問（客戶 (5)-9）：現在狀態／是否需要行動／下一步／主 CTA。"""

    current_state: FieldVM
    action_needed: FieldVM
    next_step: FieldVM
    primary_cta: CtaVM
    context_rows: tuple[FieldVM, ...] = ()   # 例：Risk Cap 一行


@dataclass(frozen=True)
class SectionVM:
    """L2／L3 摺疊區塊。"""

    section_id: str
    title: str
    level: str                      # "L2" | "L3"
    fields: tuple[FieldVM, ...] = ()


@dataclass(frozen=True)
class PageContext:
    """全量 Decision Context —— 與任何 UI 切片（Top-N／收合／tab）無關。"""

    first_screen: FirstScreenVM
    cards: tuple[CardVM, ...] = ()
    sections: tuple[SectionVM, ...] = ()


@dataclass(frozen=True)
class PresentationSlice:
    """呈現切片：只能由 context 截取（⛔ 反向影響 context）。"""

    top_n: int | None
    visible_card_ids: tuple[str, ...]


@dataclass(frozen=True)
class PageVM:
    page_id: str            # `shared.ia_nav4` 的 P4_* id
    title: str
    scenario_id: str
    is_fake: bool
    context: PageContext
    slice: PresentationSlice
    banner_text: str | None = None
