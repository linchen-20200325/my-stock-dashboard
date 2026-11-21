"""shared/system_action_contract.py — System Action Aggregator 的 L0 契約型別（M-A2；Architecture Gate §4.6）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
`docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` §4.6（客戶 Q2=A〔修正分類〕；M-A1 客戶核准）凍結的
「System Action State／action-facing canonical contract」之**型別與枚舉**。組裝邏輯在 L3
`src/services/system_action_aggregator.py`；本檔只放：
- 枚舉常數（`action_class` 五類、`group` 四組、`day_status` 三態、Risk Cap 三態、`exposure_gate`）；
- 既有規則識別字的**字串複本**（L0 不得 import `src.*`，也不得 import Digest 家族；與來源相等由
  `tests/test_system_action_aggregator_contract.py` pin 住，漂移即紅燈）；
- frozen dataclass（建構時驗證；未知枚舉值一律 raise，⛔ 靜默補值）。

═══ 語意（DEC-124；寫死） ══════════════════════════════════════════════
- `not_evaluated`＝規則／計算尚未執行或不在本次評估範圍。
- `undeterminable`＝已進入判定，但必要輸入 Missing／Unavailable／Invalid／insufficient。
- 兩類**計數分列、⛔ 合併**（`ActionCounts.not_evaluated_n`／`undeterminable_n`）。
- `unavailable`＝該檔整批抓取失敗（`_detail.error`）。
- 任一 `not_evaluated`／`undeterminable`／`unavailable` 存在時 `day_status` ⛔ `no_adjustment_today`
  （由 `SystemActionState.__post_init__` 再守一次，縱深）。

═══ 本檔**沒有**的東西（§4.6.4 禁止） ══════════════════════════════════
⛔ 新投資規則／新門檻／新比例／AI action／改寫既有結果／覆寫 Risk Cap／「減碼 1/2」「全出」／寫入。
`ExposureGate` 只接受 `undeterminable`（`FUI-RC-NUMERIC-GATE` 啟用前；Q1=A）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 `shared.*`；零 I/O、零 streamlit、零 `src.*`。
"""
from __future__ import annotations

import numbers
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from shared.holdings_data_short import SHORT_FX, SHORT_PRICE, SHORT_UNJUDGED

#: 契約版本（AI 總管／M-A2 內部命名；改欄位＝契約變更，須升版並經獨立 QA，§4.6.7）。
CONTRACT_VERSION: str = "system_action.v1"

# ── action_class（§4.6.6 O1；客戶 Q2 四類＋DEC-124 第五類） ─────────────────
ACTION_CLASS_ACTIONABLE: str = "actionable"
ACTION_CLASS_NON_ACTIONABLE: str = "non_actionable"
ACTION_CLASS_UNAVAILABLE: str = "unavailable"
ACTION_CLASS_NOT_EVALUATED: str = "not_evaluated"
ACTION_CLASS_UNDETERMINABLE: str = "undeterminable"
ACTION_CLASSES: tuple = (ACTION_CLASS_ACTIONABLE, ACTION_CLASS_NON_ACTIONABLE, ACTION_CLASS_UNAVAILABLE,
                         ACTION_CLASS_NOT_EVALUATED, ACTION_CLASS_UNDETERMINABLE)
#: 有分組（加／留／換／減）的 class；其餘 class 的 `group` 必為空字串。
GROUPED_CLASSES: frozenset = frozenset({ACTION_CLASS_ACTIONABLE, ACTION_CLASS_NON_ACTIONABLE})

# ── group（W-5 客戶核准；只是排版） ────────────────────────────────────────
GROUP_ADD: str = "加"
GROUP_HOLD: str = "留"
GROUP_SWAP: str = "換"
GROUP_REDUCE: str = "減"
GROUP_NONE: str = ""
GROUPS: tuple = (GROUP_ADD, GROUP_HOLD, GROUP_SWAP, GROUP_REDUCE)

# ── day_status（§4.6.6 O3） ─────────────────────────────────────────────────
DAY_NEEDS_ACTION: str = "needs_action"
DAY_NO_ADJUSTMENT_TODAY: str = "no_adjustment_today"
DAY_UNDETERMINABLE: str = "undeterminable"
DAY_STATUSES: tuple = (DAY_NEEDS_ACTION, DAY_NO_ADJUSTMENT_TODAY, DAY_UNDETERMINABLE)

# ── 規則來源（I1／I2） ─────────────────────────────────────────────────────
#: ETF 軌：`dividend_station.action_branch` 分支碼（版本標籤沿用 `shared.decision_digest_rules`）。
SOURCE_KIND_ACTION_BRANCH: str = "action_branch.v1"
#: 個股軌：`StockAssessment.swap_level`。
SOURCE_KIND_SWAP_LEVEL: str = "swap_level"
SOURCE_KINDS: tuple = (SOURCE_KIND_ACTION_BRANCH, SOURCE_KIND_SWAP_LEVEL)

#: `dividend_station.ACTION_*` 七分支的字串複本（測試 pin 住與 `dividend_station.ACTION_*` 相等）。
#: ⚠️ 刻意**不** import `shared.decision_digest_rules`：該檔屬 Decision Digest 家族，Stage F production
#:    caller Gate（Issue #1138、DEC-159／DEC-160；`tests/test_decision_digest_invariants_guard.py`）未開前
#:    不得有 production importer。故允許名單同樣以複本登記，測試 pin 住與 `RULE_ID_ALLOWLIST` 一致。
BRANCH_CUT: str = "cut"
BRANCH_TAKE_PROFIT_FORCE: str = "take_profit_force"
BRANCH_TAKE_PROFIT_PARTIAL: str = "take_profit_partial"
BRANCH_PAUSE_ADD: str = "pause_add"
BRANCH_ADD: str = "add"
BRANCH_PREMIUM: str = "premium"
BRANCH_CRUISE: str = "cruise"
ETF_BRANCHES: tuple = (BRANCH_CUT, BRANCH_TAKE_PROFIT_FORCE, BRANCH_TAKE_PROFIT_PARTIAL,
                       BRANCH_PAUSE_ADD, BRANCH_ADD, BRANCH_PREMIUM, BRANCH_CRUISE)
#: `shared.decision_digest_rules.RULE_ID_ALLOWLIST` 的鍵（rule_id）複本；`rule_id` 只能取自此集合或空字串。
#: （`premium`／`cruise` 刻意不在內，同 DEC-094；測試 pin 住與來源相等。）
RULE_ID_ALLOWLIST_KEYS: frozenset = frozenset({"risk_cap", BRANCH_CUT, BRANCH_TAKE_PROFIT_FORCE,
                                               BRANCH_TAKE_PROFIT_PARTIAL, BRANCH_PAUSE_ADD, BRANCH_ADD})

#: `swap_level` 四級（`assess_stock` 的 `level`；🔴換出／🟡留意／🟢續抱／⚪資料不足）。
SWAP_OUT: str = "🔴"
SWAP_WATCH: str = "🟡"
SWAP_KEEP: str = "🟢"
SWAP_INSUFFICIENT: str = "⚪"
SWAP_LEVELS: tuple = (SWAP_OUT, SWAP_WATCH, SWAP_KEEP, SWAP_INSUFFICIENT)

#: `dividend_station.LEVEL_UNJUDGED` 的字串複本（燈格「從未判過等級」；測試 pin 住）。
LEVEL_UNJUDGED: str = ""

# ── data_short_kind（I7；`holdings_data_short.row_short_kind` 原樣） ────────────
DATA_SHORT_KINDS: tuple = (SHORT_UNJUDGED, SHORT_PRICE, SHORT_FX)

# ── Risk Cap（I4／O4a／O4b） ───────────────────────────────────────────────
#: `shared.allocation_decision.build_allocation_decision` 為曝險上限建的 `Cap.name` 字面複本
#: （與 L5 `src/ui/views/risk_cap_gate.SYSTEM_RISK_CAP_NAME` 同一字面；測試以真的
#: `build_allocation_decision` 輸出 pin 住）。
SYSTEM_RISK_CAP_NAME: str = "系統風險上限"
RISK_CAP_VALID: str = "valid"        # 有效的「系統風險上限」那條 Cap 在 caps 內
RISK_CAP_INVALID: str = "invalid"    # 取 Risk Cap 時出錯（讀壞／例外；error 原樣帶）
RISK_CAP_MISSING: str = "missing"    # 沒有那條 Cap（未計算／算不出／過期／未評估）
RISK_CAP_STATUSES: tuple = (RISK_CAP_VALID, RISK_CAP_INVALID, RISK_CAP_MISSING)
#: O4b：曝險超限判定。數值 Gate（`FUI-RC-NUMERIC-GATE`）啟用前**恆**為此值（Q1=A）。
EXPOSURE_GATE_UNDETERMINABLE: str = "undeterminable"
#: 加碼類 item 的 `risk_cap_tag`（Gate §4.6.6 O4b 逐字）。
RISK_CAP_TAG_UNDETERMINABLE: str = "Risk Cap 無法判定"
RISK_CAP_TAG_NONE: str = ""
RISK_CAP_TAGS: tuple = (RISK_CAP_TAG_UNDETERMINABLE, RISK_CAP_TAG_NONE)


def _req_str(name: str, v: Any, *, allow_empty: bool = True) -> None:
    if type(v) is not str:
        raise TypeError(f"{name} 必須是 str：{type(v).__name__}")
    if not allow_empty and not v:
        raise ValueError(f"{name} 不得為空字串")


def _req_enum(name: str, v: Any, allowed: tuple) -> None:
    if type(v) is not str or v not in allowed:
        raise ValueError(f"{name} 不是已知值：{v!r}（允許 {allowed}）")


def _req_count(name: str, v: Any) -> None:
    if isinstance(v, bool) or not isinstance(v, numbers.Integral) or v < 0:
        raise ValueError(f"{name} 必須是非負整數：{v!r}")


@dataclass(frozen=True)
class ActionSourceStamp:
    """一項輸入的 as_of／source（I5）。缺 → None（⛔ 補今天、⛔ 空字串冒充）。"""

    as_of: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        for _n in ("as_of", "source"):
            _v = getattr(self, _n)
            if _v is not None:
                _req_str(_n, _v, allow_empty=False)


@dataclass(frozen=True)
class RiskCapState:
    """I4／O4a：Risk Cap state。Aggregator **原樣傳遞**（⛔ 改寫、⛔ 補值、⛔ 自算曝險）。

    - `valid`：`system_cap_pct` 為那條 Cap 的 `pct`（原樣），`error` 空；
    - `missing`：`system_cap_pct` 為 None、`error` 空；
    - `invalid`：`system_cap_pct` 為 None、`error` 非空（原樣帶出錯訊息）。
    """

    status: str
    system_cap_pct: int | None = None
    system_cap_reason: str = ""
    error: str = ""
    stamp: ActionSourceStamp = ActionSourceStamp()

    def __post_init__(self) -> None:
        _req_enum("RiskCapState.status", self.status, RISK_CAP_STATUSES)
        _req_str("RiskCapState.system_cap_reason", self.system_cap_reason)
        _req_str("RiskCapState.error", self.error)
        if type(self.stamp) is not ActionSourceStamp:
            raise TypeError(f"RiskCapState.stamp 必須是 ActionSourceStamp：{type(self.stamp).__name__}")
        _pct = self.system_cap_pct
        if self.status == RISK_CAP_VALID:
            if isinstance(_pct, bool) or not isinstance(_pct, numbers.Integral):
                raise ValueError(f"RiskCapState(valid) 必須帶 Cap.pct 原值（int）：{_pct!r}")
            if self.error:
                raise ValueError("RiskCapState(valid) 不得帶 error")
        else:
            if _pct is not None:
                raise ValueError(f"RiskCapState({self.status}) 不得帶 system_cap_pct：{_pct!r}")
            if self.system_cap_reason:
                raise ValueError(f"RiskCapState({self.status}) 不得帶 system_cap_reason")
            if self.status == RISK_CAP_INVALID and not self.error:
                raise ValueError("RiskCapState(invalid) 必須帶 error（原樣出錯訊息）")
            if self.status == RISK_CAP_MISSING and self.error:
                raise ValueError("RiskCapState(missing) 不得帶 error（有錯請用 invalid）")


@dataclass(frozen=True)
class ExposureGate:
    """O4b：曝險超限判定。數值 Gate 前恆 `undeterminable`（⛔ 自行計算曝險、分母、現金、總資產）。"""

    status: str = EXPOSURE_GATE_UNDETERMINABLE

    def __post_init__(self) -> None:
        if self.status != EXPOSURE_GATE_UNDETERMINABLE:
            raise ValueError(f"ExposureGate 在 FUI-RC-NUMERIC-GATE 啟用前只能是 undeterminable：{self.status!r}")


@dataclass(frozen=True)
class ActionItem:
    """O1：一檔的 action-facing 結果。`formal_label` 為來源字樣**逐字**（⛔ 改寫）。"""

    ticker: str
    name: str
    held: bool
    source_kind: str
    source_rule: str              # ETF 分支碼／swap_level；整批抓取失敗列為空字串
    formal_label: str
    action_class: str
    group: str
    counts_toward_today: bool
    risk_cap_tag: str
    rule_id: str
    data_short_kind: str
    stamp: ActionSourceStamp

    def __post_init__(self) -> None:
        _req_str("ActionItem.ticker", self.ticker, allow_empty=False)
        _req_str("ActionItem.name", self.name)
        _req_str("ActionItem.formal_label", self.formal_label, allow_empty=False)
        if type(self.held) is not bool:
            raise TypeError(f"ActionItem.held 必須是 bool：{self.held!r}")
        if type(self.counts_toward_today) is not bool:
            raise TypeError(f"ActionItem.counts_toward_today 必須是 bool：{self.counts_toward_today!r}")
        _req_enum("ActionItem.source_kind", self.source_kind, SOURCE_KINDS)
        _rules = ETF_BRANCHES if self.source_kind == SOURCE_KIND_ACTION_BRANCH else SWAP_LEVELS
        if self.source_rule != "":
            _req_enum("ActionItem.source_rule", self.source_rule, _rules)
        _req_enum("ActionItem.action_class", self.action_class, ACTION_CLASSES)
        if self.action_class in GROUPED_CLASSES:
            _req_enum("ActionItem.group", self.group, GROUPS)
        elif self.group != GROUP_NONE:
            raise ValueError(f"ActionItem({self.action_class}) 不得有 group：{self.group!r}")
        if self.counts_toward_today and self.action_class != ACTION_CLASS_ACTIONABLE:
            raise ValueError(f"只有 actionable 可計入今日需處理：{self.action_class}")
        if self.action_class == ACTION_CLASS_UNAVAILABLE and self.source_rule:
            raise ValueError("unavailable（整批抓取失敗）列沒有規則結果，source_rule 必為空")
        if self.action_class in GROUPED_CLASSES and not self.source_rule:
            raise ValueError(f"ActionItem({self.action_class}) 必須帶既有規則結果 source_rule")
        _req_enum("ActionItem.risk_cap_tag", self.risk_cap_tag, RISK_CAP_TAGS)
        if self.risk_cap_tag and not (self.source_kind == SOURCE_KIND_ACTION_BRANCH
                                      and self.source_rule == BRANCH_ADD
                                      and self.action_class == ACTION_CLASS_ACTIONABLE):
            raise ValueError("risk_cap_tag 只標在加碼類（action_branch=add 且 actionable）item")
        if self.rule_id != "" and self.rule_id not in RULE_ID_ALLOWLIST_KEYS:
            raise ValueError(f"ActionItem.rule_id 不在 RULE_ID_ALLOWLIST：{self.rule_id!r}")
        if self.data_short_kind != "":
            _req_enum("ActionItem.data_short_kind", self.data_short_kind, DATA_SHORT_KINDS)
        if type(self.stamp) is not ActionSourceStamp:
            raise TypeError(f"ActionItem.stamp 必須是 ActionSourceStamp：{type(self.stamp).__name__}")


@dataclass(frozen=True)
class ActionCounts:
    """O2：統一計數。`by_group` 為各組 item 數（含不計入今日的「留」）。兩類判不出**分列**。"""

    today_n: int
    by_group: Mapping[str, int]
    not_evaluated_n: int
    undeterminable_n: int
    unavailable_n: int
    incomplete_rows_n: int

    def __post_init__(self) -> None:
        for _n in ("today_n", "not_evaluated_n", "undeterminable_n", "unavailable_n", "incomplete_rows_n"):
            _req_count(f"ActionCounts.{_n}", getattr(self, _n))
        if not isinstance(self.by_group, Mapping) or tuple(self.by_group) != GROUPS:
            raise ValueError(f"ActionCounts.by_group 的鍵必須恰為 {GROUPS}（依序）：{self.by_group!r}")
        for _g in GROUPS:
            _req_count(f"ActionCounts.by_group[{_g}]", self.by_group[_g])
        object.__setattr__(self, "by_group", MappingProxyType(dict(self.by_group)))


@dataclass(frozen=True)
class DayBasis:
    """O3 的依據（只沿用 I6／I7 既有函式的結果；M-A2 為 A-T8 parity 可觀測而揭露，消費端 ⛔ 重算）。"""

    judged_lights: int
    total_lights: int
    tally: Mapping[str, int]
    all_rows_judged: bool
    cruise_gate_open: bool       # `cruise_or_gap(...)` 回巡航句
    digest_data_short: bool      # `holdings_data_short.digest_data_short(digest)`

    def __post_init__(self) -> None:
        _req_count("DayBasis.judged_lights", self.judged_lights)
        _req_count("DayBasis.total_lights", self.total_lights)
        for _n in ("all_rows_judged", "cruise_gate_open", "digest_data_short"):
            if type(getattr(self, _n)) is not bool:
                raise TypeError(f"DayBasis.{_n} 必須是 bool")
        if not isinstance(self.tally, Mapping):
            raise TypeError("DayBasis.tally 必須是 Mapping")
        object.__setattr__(self, "tally", MappingProxyType(dict(self.tally)))


@dataclass(frozen=True)
class ActionProvenance:
    """O5：輸入 as_of／source 彙總＋`contract_version`。"""

    inputs: tuple            # ((輸入名, ActionSourceStamp), ...)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"contract_version 不符：{self.contract_version!r}")
        if type(self.inputs) is not tuple:
            raise TypeError("ActionProvenance.inputs 必須是 tuple")
        for _e in self.inputs:
            if (type(_e) is not tuple or len(_e) != 2 or type(_e[0]) is not str
                    or type(_e[1]) is not ActionSourceStamp):
                raise TypeError(f"ActionProvenance.inputs 元素必須是 (str, ActionSourceStamp)：{_e!r}")


@dataclass(frozen=True)
class SystemActionState:
    """System Action State／action-facing canonical contract（O1～O5）。"""

    items: tuple
    counts: ActionCounts
    day_status: str
    day_basis: DayBasis
    risk_cap_state: RiskCapState
    exposure_gate: ExposureGate
    provenance: ActionProvenance

    def __post_init__(self) -> None:
        if type(self.items) is not tuple or any(type(_i) is not ActionItem for _i in self.items):
            raise TypeError("SystemActionState.items 必須是 tuple[ActionItem]")
        for _n, _t in (("counts", ActionCounts), ("day_basis", DayBasis), ("risk_cap_state", RiskCapState),
                       ("exposure_gate", ExposureGate), ("provenance", ActionProvenance)):
            if type(getattr(self, _n)) is not _t:
                raise TypeError(f"SystemActionState.{_n} 必須是 {_t.__name__}")
        _req_enum("SystemActionState.day_status", self.day_status, DAY_STATUSES)
        _c = self.counts
        # 縱深：有任何判不出／不可得時 ⛔「今日無需調整」（A-T4；DEC-124 兩類分列）。
        if self.day_status == DAY_NO_ADJUSTMENT_TODAY and (
                _c.today_n or _c.not_evaluated_n or _c.undeterminable_n or _c.unavailable_n
                or _c.incomplete_rows_n):
            raise ValueError("有需處理／未評估／無法判定／不可得／未判全列時，day_status 不得為 no_adjustment_today")
        if (self.day_status == DAY_NEEDS_ACTION) != (_c.today_n > 0):
            raise ValueError("day_status=needs_action 若且唯若 today_n > 0")


__all__ = [
    "CONTRACT_VERSION",
    "ACTION_CLASS_ACTIONABLE", "ACTION_CLASS_NON_ACTIONABLE", "ACTION_CLASS_UNAVAILABLE",
    "ACTION_CLASS_NOT_EVALUATED", "ACTION_CLASS_UNDETERMINABLE", "ACTION_CLASSES", "GROUPED_CLASSES",
    "GROUP_ADD", "GROUP_HOLD", "GROUP_SWAP", "GROUP_REDUCE", "GROUP_NONE", "GROUPS",
    "DAY_NEEDS_ACTION", "DAY_NO_ADJUSTMENT_TODAY", "DAY_UNDETERMINABLE", "DAY_STATUSES",
    "SOURCE_KIND_ACTION_BRANCH", "SOURCE_KIND_SWAP_LEVEL", "SOURCE_KINDS",
    "BRANCH_CUT", "BRANCH_TAKE_PROFIT_FORCE", "BRANCH_TAKE_PROFIT_PARTIAL", "BRANCH_PAUSE_ADD",
    "BRANCH_ADD", "BRANCH_PREMIUM", "BRANCH_CRUISE", "ETF_BRANCHES",
    "SWAP_OUT", "SWAP_WATCH", "SWAP_KEEP", "SWAP_INSUFFICIENT", "SWAP_LEVELS",
    "RULE_ID_ALLOWLIST_KEYS", "LEVEL_UNJUDGED", "DATA_SHORT_KINDS",
    "SYSTEM_RISK_CAP_NAME", "RISK_CAP_VALID", "RISK_CAP_INVALID", "RISK_CAP_MISSING", "RISK_CAP_STATUSES",
    "EXPOSURE_GATE_UNDETERMINABLE", "RISK_CAP_TAG_UNDETERMINABLE", "RISK_CAP_TAG_NONE", "RISK_CAP_TAGS",
    "ActionSourceStamp", "RiskCapState", "ExposureGate", "ActionItem", "ActionCounts", "DayBasis",
    "ActionProvenance", "SystemActionState",
]
