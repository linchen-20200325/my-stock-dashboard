"""shared/decision_digest_coverage.py — Decision Digest 的「完整性側車」契約（L0；Issue #1127 P-4 / S8）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
`DecisionDigest`（`shared/decision_digest.py`，Phase 1 凍結）在形成前就把行動截到 `MAX_ACTIONS`，
並把「資料異常整列被排除」「持有但無鍵」等情形吞進內部；讀 Digest 的人（含未來的 One AI Brain）
**看不出少了什麼**。本檔提供**側車（sidecar）**：獨立版本的 coverage 物件，與 Digest 一起裝進
envelope（`src/services/decision_digest_assembly.py::AssembledDigest`），由它攜帶完整性揭露。

═══ 為什麼是側車、而不是改 Digest ═════════════════════════════════════
Digest v1 凍結（`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` §5）：不得改欄位、不得升
`SCHEMA_VERSION`、不得動 `MAX_ACTIONS`、不得新增列舉成員、不得新增 confidence 語意。
升 v2 屬另案（Stage F，須過 High Gate＋獨立 QA）。側車的版本號 `COVERAGE_SCHEMA_VERSION` 與
Digest 的版本**互相獨立**；Digest v2 日後若吸收這些欄位，側車可退役，而不影響 v1 消費者。

═══ 設計鐵則（寫死）══════════════════════════════════════════════════
1. **`is_complete` 是「唯一」的完整性判定**：omitted==0 且 excluded==0 且 unkeyed==0 且 unmatched==0
   且 holdings_without_station_row==0 且 `digest_holdings_available`／`digest_actions_available` 皆 True 且四段證據皆 used。
   ⚠️ 最後兩個旗標是 **v1 限制**，不是「沒完成」：v1 builder 的 holdings／actions 段只有在「至少一項行動事實」時
   才 AVAILABLE，**無法區分「沒事做」與「判不出來」**。所以「零行動」一律 `is_complete=False`（保守 fail-closed）——
   它的意思是「v1 Digest 不能證明沒有遺漏」，**不是**「有東西漏了」。Digest v2 若能區分，這兩個旗標才可放寬。
   物件本身不合法（`validate_coverage` 有違規）→ `is_complete` 為 False（fail-closed）。
2. **未知不是零**：不能評估的計數一律 `None`（不是 0）。None 使 `is_complete` 為 False。
   ⛔ 以 0 表示「沒有」會把「不知道」偽裝成「沒有被省略」——比沒有數字更危險（CLAUDE.md §1）。
3. **不得含 confidence／score／neutral／safe 語意或欄位**；缺資料不以任何形式被描述成「安全」。
   `is_complete` 只回答「有沒有東西沒被讀進 Digest」，**不是**信心、也**不是**「可以放心」。
4. `withheld_reason` 用本檔自有的 str 常數集合（`WITHHELD_*`），**不沿用、不擴充** Digest 的任何列舉
   （`DataStatus`／`MissingReason`…）。
5. `used` 的語意是「該段證據**完整**採用」：被拒用、或只採到一部分（partial）都是 False。
6. 計數用嚴格 `int`（`type(v) is int`）：bool 與 float 一律被 validator 拒絕（`True` 不是 1、`2.0` 不是 2）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 `shared.decision_digest`；零 I/O、零 streamlit、零 `src.*`。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from shared.decision_digest import MAX_ACTIONS

#: 側車自己的版本（與 `shared.decision_digest.SCHEMA_VERSION` 獨立）。
COVERAGE_SCHEMA_VERSION: str = "digest_coverage.v1"

# ── 證據段（固定四段、固定順序）────────────────────────────────────────────
SEGMENT_MARKET: str = "market"
SEGMENT_RISK_CAP: str = "risk_cap"
SEGMENT_HOLDINGS: str = "holdings"
SEGMENT_ACTIONS: str = "actions"
SEGMENTS: tuple = (SEGMENT_MARKET, SEGMENT_RISK_CAP, SEGMENT_HOLDINGS, SEGMENT_ACTIONS)

# ── 證據被拒用／未完整採用的原因（本檔自有常數；⛔ 不是 Digest 的 MissingReason）──────────
WITHHELD_NO_STAMP: str = "no_stamp"            # 沒有證據，或證據沒有日期戳（不得補日期）
WITHHELD_STALE: str = "stale"                  # freshness 判為過期
WITHHELD_FETCH_FAILED: str = "fetch_failed"    # 上游抓取明確失敗（FetchOutcome.FETCH_FAILED）
WITHHELD_UNDETERMINED: str = "undetermined"    # 新鮮度／抓取結果無法判定（保守：不採用）
WITHHELD_PIT_VIOLATION: str = "pit_violation"  # as_of／fetched_at 時序違反（lookahead）
WITHHELD_NOT_LOADED: str = "not_loaded"        # 證據可用，但上游這一段根本沒載入／沒提供
WITHHELD_PARTIAL: str = "partial"              # 證據可用，但只有一部分事實可用（其餘缺／異常）
WITHHELD_REASONS: frozenset = frozenset({
    WITHHELD_NO_STAMP, WITHHELD_STALE, WITHHELD_FETCH_FAILED, WITHHELD_UNDETERMINED,
    WITHHELD_PIT_VIOLATION, WITHHELD_NOT_LOADED, WITHHELD_PARTIAL,
})


@dataclass(frozen=True)
class SegmentEvidence:
    """單一證據段的採用狀況與血緣。

    - `used=True`：該段證據完整採用；必有 `source` 與 `as_of`，且 `withheld_reason` 必為 None。
    - `used=False`：必有 `withheld_reason`（`WITHHELD_REASONS` 之一）；`source`／`as_of` 「若有」才帶
      （例如 stale 的證據仍可追溯它是哪個來源、哪一天的資料；⛔ 沒有就是 None，不補、不用 generated_at 頂替）。
    建構時**不**做檢查（與 `DecisionDigest` 同：由 `validate_coverage` 收口）。
    """
    segment: str
    used: bool
    source: str | None = None
    as_of: date | None = None
    withheld_reason: str | None = None


@dataclass(frozen=True)
class DigestCoverage:
    """Digest 的完整性揭露（側車）。欄位語意：

    - `actions_total_eligible`：全部合格行動候選數（未截斷）；**不能評估 → None**。
    - `actions_shown`：實際進入 Digest 的行動數（永遠已知）。
    - `actions_omitted_count`：`total − shown`；total 為 None 時必為 None。
    - `actions_max`：Digest 的行動上限（必須等於 `shared.decision_digest.MAX_ACTIONS`，不得硬編碼）。
    - `excluded_invalid_rows`：站內持有列因 `_invalid_lights`／`_invalid_inputs`／`_detail.error` 被排除的數；
      不能評估 → None。
    - `unkeyed_held_count`：持有但無 `HoldingKey` 的列數；`holdings_rows` 沒給 → None。
    - `actions_unmatched_dropped`：站內 held、無異常旗標、有行動碼，卻因 ticker 對不上持股鍵（大小寫／空白不符、
      不在 `holdings_rows`、沒有 `HoldingKey`）而被 builder 靜默丟棄的列數；不能評估 → None。
    - `holdings_without_station_row`：held 持股中，站內列沒有同 ticker held 列者（＝沒有任何站內證據）的數量；
      不能評估 → None。
    - `digest_holdings_available`／`digest_actions_available`：Digest 的 holdings／actions 段 availability 是否為
      AVAILABLE（由 digest 推得，`AssembledDigest` 與 digest 交叉驗證）。
    - `segments`：恰為 market／risk_cap／holdings／actions 四段，固定順序。
    """
    actions_total_eligible: int | None
    actions_shown: int
    actions_omitted_count: int | None
    actions_max: int
    excluded_invalid_rows: int | None
    unkeyed_held_count: int | None
    actions_unmatched_dropped: int | None
    holdings_without_station_row: int | None
    digest_holdings_available: bool
    digest_actions_available: bool
    segments: tuple
    schema_version: str = COVERAGE_SCHEMA_VERSION

    @property
    def is_complete(self) -> bool:
        """**唯一**的完整性判定（見模組 docstring 鐵則 1）。不合法的物件一律 False。"""
        if validate_coverage(self):
            return False
        return (self.actions_omitted_count == 0 and self.excluded_invalid_rows == 0
                and self.unkeyed_held_count == 0 and self.actions_unmatched_dropped == 0
                and self.holdings_without_station_row == 0
                and self.digest_holdings_available is True and self.digest_actions_available is True
                and all(s.used is True for s in self.segments))

    def to_dict(self) -> dict:
        """JSON 友善 dict（決定性：欄位順序固定、date 轉 ISO）。先 `assert_coverage_valid`。"""
        assert_coverage_valid(self)
        return {
            "schema_version": self.schema_version,
            "actions_total_eligible": self.actions_total_eligible,
            "actions_shown": self.actions_shown,
            "actions_omitted_count": self.actions_omitted_count,
            "actions_max": self.actions_max,
            "excluded_invalid_rows": self.excluded_invalid_rows,
            "unkeyed_held_count": self.unkeyed_held_count,
            "actions_unmatched_dropped": self.actions_unmatched_dropped,
            "holdings_without_station_row": self.holdings_without_station_row,
            "digest_holdings_available": self.digest_holdings_available,
            "digest_actions_available": self.digest_actions_available,
            "segments": [
                {"segment": s.segment, "used": s.used, "source": s.source,
                 "as_of": s.as_of.isoformat() if s.as_of is not None else None,
                 "withheld_reason": s.withheld_reason}
                for s in self.segments
            ],
            "is_complete": self.is_complete,
        }


# ══════════════════════════════════════════════════════════════════════
# validator（純函式；任何輸入都不 raise）
# ══════════════════════════════════════════════════════════════════════
def _is_strict_int(v: Any) -> bool:
    """嚴格 int：`True`／`2.0`／numpy 整數都不算（bool 是 int 的子類，故用 `type(v) is int`）。"""
    return type(v) is int


def _opt_count(name: str, v: Any, out: list) -> bool:
    """None 或非負嚴格 int。回傳是否為合法 int（None 回 False，違規也回 False）。"""
    if v is None:
        return False
    if not _is_strict_int(v):
        out.append(f"{name}_type: 必須是嚴格 int 或 None（bool／float 一律拒收）：{type(v).__name__} {v!r}")
        return False
    if v < 0:
        out.append(f"{name}_negative: 不得為負：{v!r}")
        return False
    return True


def _check_segment(s: Any, idx: int, out: list) -> None:
    path = f"segments[{idx}]"
    if type(s) is not SegmentEvidence:
        out.append(f"segment_type: {path} 必須是 SegmentEvidence：{type(s).__name__}")
        return
    if type(s.segment) is not str or s.segment not in SEGMENTS:
        out.append(f"segment_name: {path}.segment 必須是 {list(SEGMENTS)} 之一：{s.segment!r}")
    if type(s.used) is not bool:
        out.append(f"used_type: {path}.used 必須是 bool：{type(s.used).__name__} {s.used!r}")
        return
    if s.source is not None and (type(s.source) is not str or not s.source.strip()):
        out.append(f"source_type: {path}.source 必須是非空 str 或 None：{s.source!r}")
    # `date` 的子類 `datetime` 不得冒充
    if s.as_of is not None and type(s.as_of) is not date:
        out.append(f"as_of_type: {path}.as_of 必須恰好是 datetime.date 或 None：{s.as_of!r}")
    if s.used:
        if s.withheld_reason is not None:
            out.append(f"used_with_reason: {path} used=True 時 withheld_reason 必須是 None：{s.withheld_reason!r}")
        if s.source is None:
            out.append(f"used_without_source: {path} used=True 必須有 source（血緣可追溯）")
        if s.as_of is None:
            out.append(f"used_without_as_of: {path} used=True 必須有 as_of（不得以 generated_at 頂替）")
    else:
        if s.withheld_reason is None:
            out.append(f"unused_without_reason: {path} used=False 必須有 withheld_reason")
        elif type(s.withheld_reason) is not str or s.withheld_reason not in WITHHELD_REASONS:
            out.append(f"withheld_reason_unknown: {path}.withheld_reason 必須是 {sorted(WITHHELD_REASONS)} 之一："
                       f"{s.withheld_reason!r}")


def validate_coverage(c: Any) -> tuple:
    """回傳 `DigestCoverage` 的**全部**違規（空 tuple＝合規）。每筆是 `"code: 說明"` 字串。任何輸入都不 raise。"""
    try:
        return tuple(_validate(c))
    except Exception as e:  # noqa: BLE001 —— 刻意：validator 本身不得因髒輸入而 raise（回報成違規）
        return (f"validator_error: {type(e).__name__}",)


def _validate(c: Any) -> list:
    if type(c) is not DigestCoverage:
        return [f"type: 必須是 DigestCoverage：{type(c).__name__}"]
    out: list = []
    if type(c.schema_version) is not str or c.schema_version != COVERAGE_SCHEMA_VERSION:
        out.append(f"schema_version_mismatch: 期望 {COVERAGE_SCHEMA_VERSION!r}，實得 {c.schema_version!r}")

    total_ok = _opt_count("actions_total_eligible", c.actions_total_eligible, out)
    omitted_ok = _opt_count("actions_omitted_count", c.actions_omitted_count, out)
    _opt_count("excluded_invalid_rows", c.excluded_invalid_rows, out)
    _opt_count("unkeyed_held_count", c.unkeyed_held_count, out)
    _opt_count("actions_unmatched_dropped", c.actions_unmatched_dropped, out)
    _opt_count("holdings_without_station_row", c.holdings_without_station_row, out)
    for _flag in ("digest_holdings_available", "digest_actions_available"):
        if type(getattr(c, _flag)) is not bool:
            out.append(f"{_flag}_type: 必須是 bool：{type(getattr(c, _flag)).__name__} {getattr(c, _flag)!r}")

    shown_ok = False
    if c.actions_shown is None or not _is_strict_int(c.actions_shown):
        out.append(f"actions_shown_type: 必須是嚴格 int（永遠已知，不得為 None）：{c.actions_shown!r}")
    elif c.actions_shown < 0:
        out.append(f"actions_shown_negative: 不得為負：{c.actions_shown!r}")
    else:
        shown_ok = True

    max_ok = _is_strict_int(c.actions_max)
    if not max_ok:
        out.append(f"actions_max_type: 必須是嚴格 int：{c.actions_max!r}")
    elif c.actions_max != MAX_ACTIONS:
        out.append(f"actions_max_mismatch: 必須等於 shared.decision_digest.MAX_ACTIONS({MAX_ACTIONS})，"
                   f"實得 {c.actions_max}（不得硬編碼或自訂）")
    if shown_ok and max_ok and c.actions_shown > c.actions_max:
        out.append(f"shown_exceeds_max: shown({c.actions_shown}) > actions_max({c.actions_max})")

    # total／omitted：同時為 None（未知）或同時為 int
    if (c.actions_total_eligible is None) != (c.actions_omitted_count is None):
        out.append("total_omitted_unknown_mismatch: actions_total_eligible 與 actions_omitted_count "
                   "必須同時為 None（未知）或同時為 int")
    if total_ok and omitted_ok and shown_ok:
        if c.actions_total_eligible < c.actions_shown:
            out.append(f"total_below_shown: total({c.actions_total_eligible}) < shown({c.actions_shown})")
        if c.actions_omitted_count != c.actions_total_eligible - c.actions_shown:
            out.append(f"omitted_mismatch: omitted({c.actions_omitted_count}) != total({c.actions_total_eligible})"
                       f" − shown({c.actions_shown})")

    segs = c.segments
    seg_by_name: dict = {}
    if type(segs) is not tuple:
        out.append(f"segments_type: 必須是 tuple：{type(segs).__name__}")
    else:
        for i, s in enumerate(segs):
            _check_segment(s, i, out)
        names = [getattr(s, "segment", None) for s in segs]
        if names != list(SEGMENTS):
            out.append(f"segments_set: 必須恰為 {list(SEGMENTS)}（唯一、固定順序）：{names!r}")
        else:
            seg_by_name = {s.segment: s for s in segs if type(s) is SegmentEvidence}

    # 跨欄位：actions 段完整採用 ⇒ 計數已評估；holdings 段完整採用 ⇒ unkeyed 已知
    act = seg_by_name.get(SEGMENT_ACTIONS)
    _eval_counts = (c.actions_total_eligible, c.actions_omitted_count, c.excluded_invalid_rows,
                    c.actions_unmatched_dropped, c.holdings_without_station_row)
    if act is not None and act.used is True:
        if any(v is None for v in _eval_counts):
            out.append("actions_used_with_unknown_counts: actions 段 used=True 時 total／omitted／excluded／"
                       "unmatched／holdings_without_station_row 必須已評估（不得為 None）")
    elif act is not None and act.used is False:
        if any(v is not None for v in _eval_counts):
            out.append("actions_unused_with_known_counts: actions 段 used=False（證據未採用）時 total／omitted／"
                       "excluded／unmatched／holdings_without_station_row 必須全部是 None"
                       "（未採用的證據之上的計數不可信；未知不是 0）")
    hold = seg_by_name.get(SEGMENT_HOLDINGS)
    if hold is not None and hold.used is True and c.unkeyed_held_count is None:
        out.append("holdings_used_with_unknown_unkeyed: holdings 段 used=True 時 unkeyed_held_count 必須已知（不得為 None）")
    return out


def assert_coverage_valid(c: Any) -> None:
    """有任何違規 → `ValueError`（附全部違規）。"""
    v = validate_coverage(c)
    if v:
        raise ValueError("DigestCoverage 違反契約：\n  " + "\n  ".join(v))


__all__ = [
    "COVERAGE_SCHEMA_VERSION", "SEGMENT_MARKET", "SEGMENT_RISK_CAP", "SEGMENT_HOLDINGS", "SEGMENT_ACTIONS",
    "SEGMENTS", "WITHHELD_NO_STAMP", "WITHHELD_STALE", "WITHHELD_FETCH_FAILED", "WITHHELD_UNDETERMINED",
    "WITHHELD_PIT_VIOLATION", "WITHHELD_NOT_LOADED", "WITHHELD_PARTIAL", "WITHHELD_REASONS",
    "SegmentEvidence", "DigestCoverage", "validate_coverage", "assert_coverage_valid",
]
