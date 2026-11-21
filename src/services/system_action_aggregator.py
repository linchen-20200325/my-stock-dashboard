"""src/services/system_action_aggregator.py — System Action Aggregator（L3 純函式；M-A2；Architecture Gate §4.6）。

═══ 定位（客戶 Q2，逐字見 Gate §4.6.2） ══════════════════════════════════
    Existing Formal Rules + Risk Cap → System Action Aggregator → System Action State
「不是第二套規則引擎。」本模組只做 §4.6.3 允許的 7 件事：收集既有正式結果、收集 Risk Cap state、
區分 actionable／non_actionable／unavailable／not_evaluated（＋DEC-124 undeterminable）、
加／留／換／減分組（W-5；只是排版）、統一計數、區分「今日無需調整」與「無法判定」、
提供共用 canonical view。⛔ 新規則／新門檻／新比例／AI action／改寫既有結果／覆寫 Risk Cap／
「減碼 1/2」「全出」／portfolio 或 Sheet 寫入（§4.6.4）。

═══ 輸入（全部以參數傳入；本模組零 I/O、零時鐘、零 session、零寫入） ════════
- `station_rows`：L3 `dividend_station_service.get_station_rows()` 的列（I1 ETF `_action`＝
  `action_branch` 七分支碼＋`建議動作` 原字樣；I2 個股 `健檢`＝`swap_level`＋`建議動作`；
  I6 `_lights` 燈格；I7 `holdings_data_short` 判定所需鍵）。
- `station_digest`：L3 `build_station_digest()` 的 digest（I7 `digest_data_short` 的唯一原料）。
- `risk_cap`：`RiskCapState`（I4；可由 `risk_cap_state_from_allocation()` 從 `get_allocation(...)` 的結果建）。
- `station_stamp`：I5 戰情表的 as_of／source（缺 → None，照實標缺）。

═══ PORT（Gate §5.1 第 2 點：新位置另建＋parity，Old UI 原檔一字不改） ═════════
`_in_judged_denominator`／`judged_count`／`is_fully_judged`／`aggregate_judged`／`tally_states`／
`cruise_or_gap`／`CRUISE_TEXT` 逐字移植自 L4 `src/ui/render/station_cards.py`（該檔 import streamlit，
L3 不得 import）；`has_system_risk_cap` 移植自 L5 `src/ui/views/risk_cap_gate.py`。
兩處以 `tests/test_system_action_aggregator_parity.py` 釘同輸出；⛔ 在此改任何分子／分母／例外。

分層（CLAUDE.md §8.2）：L3 —— 只 import 標準函式庫與 L0 `shared.*`（刻意不 import L2
`src.compute.etf.dividend_station`：其套件 `__init__` 會連帶載入 streamlit／`src.data`；分支碼與
`LEVEL_UNJUDGED` 以 L0 複本＋測試 pin 住，同 `decision_digest_rules` 慣例）。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping, Sequence

from shared import station_specs as SS
from shared import system_action_contract as C
from shared.holdings_data_short import SHORT_UNJUDGED, digest_data_short, row_short_kind

# ══════════════════════════════════════════════════════════════════════
# 一、PORT：判得出幾盞燈／巡航 gate（逐字移植自 L4 station_cards；parity 測試釘住）
# ══════════════════════════════════════════════════════════════════════

#: 巡航句（station_cards.CRUISE_TEXT 逐字複本；parity 測試 pin 住）。
CRUISE_TEXT = "⚪ 巡航：今天沒有需要動作的部位"


def _in_judged_denominator(cell) -> bool:
    """同 station_cards._in_judged_denominator：結構上不適用、或規格表 emits_level=False 的燈不進分母；
    規格表查不到的 key 算進分母（寧可分數偏低，§1）。"""
    if cell.miss_reason == SS.MISS_NOT_APPLICABLE:
        return False
    _spec = SS.SPECS_BY_KEY.get(cell.key)
    return _spec is None or _spec.emits_level


def judged_count(cells) -> tuple[int, int]:
    """同 station_cards.judged_count：分子＝分母內 state ∈ {live, degraded}（白名單）且 level 非空。"""
    _cs = tuple(c for c in (cells or ()) if _in_judged_denominator(c))
    _num = sum(1 for c in _cs
               if c.state in (SS.STATE_LIVE, SS.STATE_DEGRADED)
               and c.level != C.LEVEL_UNJUDGED)
    return _num, len(_cs)


def is_fully_judged(cells) -> bool:
    """同 station_cards.is_fully_judged：空列回 False（「什麼都沒有」不是「全部都好」）。"""
    _n, _m = judged_count(cells)
    return _m > 0 and _n == _m


def aggregate_judged(cells_per_row) -> tuple[int, int]:
    """同 station_cards.aggregate_judged：逐列 judged_count 相加。"""
    _n = _m = 0
    for _cells in (cells_per_row or ()):
        _a, _b = judged_count(_cells)
        _n += _a
        _m += _b
    return _n, _m


def tally_states(cells_per_row) -> dict[str, int]:
    """同 station_cards.tally_states：四態各幾格（分母口徑同 judged_count；沒出現的填 0）。"""
    _out = {_s: 0 for _s in (SS.STATE_LIVE, SS.STATE_DEGRADED,
                             SS.STATE_MISSING, SS.STATE_UNWIRED)}
    for _cells in (cells_per_row or ()):
        for _c in (_cells or ()):
            if not _in_judged_denominator(_c):
                continue
            if _c.state in _out:
                _out[_c.state] += 1
    return _out


def cruise_or_gap(judged: int, total: int, *, all_rows_judged: bool) -> str:
    """同 station_cards.cruise_or_gap（逐字）：每列每盞適用燈都判得出才回巡航句。"""
    if all_rows_judged and total > 0 and judged == total:
        return CRUISE_TEXT
    return (f"{judged}/{total} 個依據可用 —— "
            f"**不是都沒事,是沒東西可以判**")


def has_system_risk_cap(caps: Any) -> bool:
    """同 risk_cap_gate.has_system_risk_cap：caps 裡有沒有那條「系統風險上限」。"""
    return any(getattr(c, "name", None) == C.SYSTEM_RISK_CAP_NAME for c in (caps or ()))


# ══════════════════════════════════════════════════════════════════════
# 二、既有正式結果 → action_class／group（W-5 客戶核准分組；⛔ 新增任何分支或條件）
# ══════════════════════════════════════════════════════════════════════
# 值：(action_class, group, 是否屬「今日需處理」類, rule_id)。
# ⚠️ 本表**只是把既有分支碼／等級對到呈現分組**（Gate §4.6.6「計入規則」與「分組」兩段）：
#    今日需處理＝加、換、減、暫停加碼；巡航／續抱／高溢價／🟡 留意只做分布（不計入）。
_ETF_MAP: Mapping = MappingProxyType({
    C.BRANCH_CUT: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_REDUCE, True, C.BRANCH_CUT),
    C.BRANCH_TAKE_PROFIT_FORCE: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_REDUCE, True, C.BRANCH_TAKE_PROFIT_FORCE),
    C.BRANCH_TAKE_PROFIT_PARTIAL: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_REDUCE, True,
                                   C.BRANCH_TAKE_PROFIT_PARTIAL),
    C.BRANCH_PAUSE_ADD: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_HOLD, True, C.BRANCH_PAUSE_ADD),
    C.BRANCH_ADD: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_ADD, True, C.BRANCH_ADD),
    C.BRANCH_PREMIUM: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, ""),
    C.BRANCH_CRUISE: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, ""),
})
_SWAP_MAP: Mapping = MappingProxyType({
    C.SWAP_OUT: (C.ACTION_CLASS_ACTIONABLE, C.GROUP_SWAP, True, ""),        # 無 allowlist rule id
    C.SWAP_WATCH: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, ""),  # 🟡 留意：無正式 action code
    C.SWAP_KEEP: (C.ACTION_CLASS_NON_ACTIONABLE, C.GROUP_HOLD, False, ""),
    C.SWAP_INSUFFICIENT: (C.ACTION_CLASS_UNDETERMINABLE, C.GROUP_NONE, False, ""),
})
_KIND_STOCK_TEXT = "個股"     # row["種類"] 的個股字樣（L3 `stock_row_from_assessment`／`_error_row` 既有值）
_KIND_ETF_TEXT = "ETF"


def risk_cap_state_from_allocation(allocation: Any, *, error: str = "",
                                   stamp: C.ActionSourceStamp | None = None) -> C.RiskCapState:
    """`get_allocation(require_valid_risk_cap=True)` 的結果 → `RiskCapState`（I4；只讀 caps，⛔ 自算）。

    - `error` 非空（取 Risk Cap 時的例外／file_error，原樣）→ `invalid`（此時 `allocation` 必為 None）；
    - `allocation` 為 None → `missing`；
    - caps 內恰有一條「系統風險上限」→ `valid`（pct／reason 原樣）；沒有 → `missing`；多於一條 → raise。
    """
    _stamp = C.ActionSourceStamp() if stamp is None else stamp
    if type(error) is not str:
        raise TypeError(f"error 必須是 str：{type(error).__name__}")
    if error:
        if allocation is not None:
            raise ValueError("risk_cap_state_from_allocation：同時給 allocation 與 error，無法判定哪個為準")
        return C.RiskCapState(status=C.RISK_CAP_INVALID, error=error, stamp=_stamp)
    if allocation is None:
        return C.RiskCapState(status=C.RISK_CAP_MISSING, stamp=_stamp)
    _caps = getattr(allocation, "caps", None)
    if not has_system_risk_cap(_caps):
        return C.RiskCapState(status=C.RISK_CAP_MISSING, stamp=_stamp)
    _sys = [c for c in _caps if getattr(c, "name", None) == C.SYSTEM_RISK_CAP_NAME]
    if len(_sys) != 1:
        raise ValueError(f"caps 內「{C.SYSTEM_RISK_CAP_NAME}」不只一條（{len(_sys)}），⛔ 自行挑選")
    return C.RiskCapState(status=C.RISK_CAP_VALID, system_cap_pct=_sys[0].pct,
                          system_cap_reason=str(getattr(_sys[0], "reason", "") or ""), stamp=_stamp)


def _classify_row(row: Any, stamp: C.ActionSourceStamp) -> C.ActionItem:
    """一列既有結果 → ActionItem。未知枚舉值／缺必要鍵一律 raise（⛔ 靜默補值）。"""
    if not isinstance(row, Mapping):
        raise TypeError(f"station_rows 的元素必須是 Mapping：{type(row).__name__}")
    _r = dict(row)        # `holdings_data_short` 只認 dict（同 page_hold `row_data_short(dict(_r))`）
    for _k in ("代號", "名稱", "建議動作", "held"):
        if _k not in _r:
            raise ValueError(f"station row 缺必要鍵 {_k!r}：{_r.get('代號')!r}")
    _ticker, _name, _label, _held = _r["代號"], _r["名稱"], _r["建議動作"], _r["held"]
    if type(_held) is not bool:
        raise TypeError(f"station row held 必須是 bool：{_ticker!r} → {_held!r}")
    _detail = _r.get("_detail") or {}
    if not isinstance(_detail, Mapping):
        raise TypeError(f"station row _detail 必須是 Mapping：{_ticker!r}")
    _is_error = bool(_detail.get("error"))
    _kind_txt = _r.get("種類")

    if "_action" in _r:
        if _is_error:
            raise ValueError(f"station row 同時有 _action 與 _detail.error（契約漂移）：{_ticker!r}")
        _src_kind, _rule = C.SOURCE_KIND_ACTION_BRANCH, _r["_action"]
        if _rule not in _ETF_MAP:
            raise ValueError(f"未知 action_branch 分支碼：{_ticker!r} → {_rule!r}")
        _base = _ETF_MAP[_rule]
    elif _is_error:
        if _kind_txt == _KIND_STOCK_TEXT:
            _src_kind = C.SOURCE_KIND_SWAP_LEVEL
        elif _kind_txt == _KIND_ETF_TEXT:
            _src_kind = C.SOURCE_KIND_ACTION_BRANCH
        else:
            raise ValueError(f"整批抓取失敗列的 種類 不是已知值：{_ticker!r} → {_kind_txt!r}")
        return C.ActionItem(
            ticker=_ticker, name=_name, held=_held, source_kind=_src_kind, source_rule="",
            formal_label=_label, action_class=C.ACTION_CLASS_UNAVAILABLE, group=C.GROUP_NONE,
            counts_toward_today=False, risk_cap_tag=C.RISK_CAP_TAG_NONE, rule_id="",
            data_short_kind="", stamp=stamp)
    elif _kind_txt == _KIND_STOCK_TEXT:
        _src_kind, _rule = C.SOURCE_KIND_SWAP_LEVEL, _r.get("健檢")
        if _rule not in _SWAP_MAP:
            raise ValueError(f"未知 swap_level：{_ticker!r} → {_rule!r}")
        _base = _SWAP_MAP[_rule]
    else:
        raise ValueError(f"station row 既無 _action、也不是個股列或抓取失敗列（契約漂移）：{_ticker!r}")

    _short = row_short_kind(_r) or ""
    if _short == SHORT_UNJUDGED:
        # Gate §4.6.6 對映表：unjudged → undeterminable（DEC-124），⛔ 計入、⛔ 分組。
        _cls, _grp, _today, _rid = C.ACTION_CLASS_UNDETERMINABLE, C.GROUP_NONE, False, ""
    else:
        _cls, _grp, _today, _rid = _base
        if _cls != C.ACTION_CLASS_ACTIONABLE:
            _rid = ""
    _tag = (C.RISK_CAP_TAG_UNDETERMINABLE
            if (_src_kind == C.SOURCE_KIND_ACTION_BRANCH and _rule == C.BRANCH_ADD
                and _cls == C.ACTION_CLASS_ACTIONABLE)
            else C.RISK_CAP_TAG_NONE)
    return C.ActionItem(
        ticker=_ticker, name=_name, held=_held, source_kind=_src_kind, source_rule=_rule,
        formal_label=_label, action_class=_cls, group=_grp,
        # ⚠️ 觀察清單（held=False）不是 portfolio action（同 digest「watch_adds 不計入今日要動作」）。
        counts_toward_today=bool(_today and _held),
        risk_cap_tag=_tag, rule_id=_rid, data_short_kind=_short, stamp=stamp)


def aggregate_system_actions(*, station_rows: Sequence[Mapping[str, Any]],
                             station_digest: Mapping[str, Any],
                             risk_cap: C.RiskCapState,
                             station_stamp: C.ActionSourceStamp) -> C.SystemActionState:
    """既有正式結果＋Risk Cap state → `SystemActionState`。純函式、deterministic、headless。

    ⛔ 截斷／排序／top_n／收合：items 與輸入列一一對應、保持輸入順序（Presentation Slice 屬 consumer）。
    公開輸出嚴格＝凍結 O1～O5；`day_status` 的依據（`DayBasis`）只留在內部 `_aggregate_with_basis`。
    """
    return _aggregate_with_basis(station_rows=station_rows, station_digest=station_digest,
                                 risk_cap=risk_cap, station_stamp=station_stamp)[0]


def _aggregate_with_basis(*, station_rows: Sequence[Mapping[str, Any]],
                          station_digest: Mapping[str, Any],
                          risk_cap: C.RiskCapState,
                          station_stamp: C.ActionSourceStamp) -> tuple[C.SystemActionState, C.DayBasis]:
    """**內部**：同一份計算同時產出公開 `SystemActionState` 與 `day_status` 的依據 `DayBasis`。

    只供 `aggregate_system_actions`（取 [0]）與 A-T8 parity／對照測試使用；⛔ consumer 呼叫。
    `day_status` 只在此判定一次（⛔ 第二套判定）。
    """
    if isinstance(station_rows, (str, bytes)) or not isinstance(station_rows, (list, tuple)):
        raise TypeError(f"station_rows 必須是 list／tuple：{type(station_rows).__name__}")
    if not isinstance(station_digest, Mapping):
        raise TypeError(f"station_digest 必須是 Mapping：{type(station_digest).__name__}")
    if type(risk_cap) is not C.RiskCapState:
        raise TypeError(f"risk_cap 必須是 RiskCapState：{type(risk_cap).__name__}")
    if type(station_stamp) is not C.ActionSourceStamp:
        raise TypeError(f"station_stamp 必須是 ActionSourceStamp：{type(station_stamp).__name__}")

    _items = tuple(_classify_row(_row, station_stamp) for _row in station_rows)

    # I6／I7：「沒事 vs 判不出」gate 的原料（口徑同 page_hold.load_station 的 _unjudged／_all_judged）。
    _cells = [(dict(_row).get("_lights") or ()) for _row in station_rows]
    _judged, _total = aggregate_judged(_cells)
    _row_short = [row_short_kind(dict(_row)) is not None for _row in station_rows]
    _incomplete = sum(1 for _c, _sh in zip(_cells, _row_short) if _sh or not is_fully_judged(_c))
    _all_judged = bool(_cells) and _incomplete == 0
    _tally = tally_states(_cells)
    _cruise_open = cruise_or_gap(_judged, _total, all_rows_judged=_all_judged) == CRUISE_TEXT
    _digest_short = bool(digest_data_short(station_digest))

    def _n(cls: str) -> int:
        return sum(1 for _i in _items if _i.action_class == cls)

    _counts = C.ActionCounts(
        today_n=sum(1 for _i in _items if _i.counts_toward_today),
        by_group={_g: sum(1 for _i in _items if _i.group == _g) for _g in C.GROUPS},
        not_evaluated_n=_n(C.ACTION_CLASS_NOT_EVALUATED),
        undeterminable_n=_n(C.ACTION_CLASS_UNDETERMINABLE),
        unavailable_n=_n(C.ACTION_CLASS_UNAVAILABLE),
        incomplete_rows_n=int(_incomplete))

    if _counts.today_n > 0:
        _day = C.DAY_NEEDS_ACTION
    elif (_cruise_open and not _digest_short and _counts.not_evaluated_n == 0
          and _counts.undeterminable_n == 0 and _counts.unavailable_n == 0):
        _day = C.DAY_NO_ADJUSTMENT_TODAY
    else:
        _day = C.DAY_UNDETERMINABLE

    _state = C.SystemActionState(
        items=_items, counts=_counts, day_status=_day,
        risk_cap_state=risk_cap,                      # O4a：原樣傳遞（同一物件）
        exposure_gate=C.ExposureGate(),               # O4b：恆 undeterminable
        provenance=C.ActionProvenance(inputs=(("station", station_stamp), ("risk_cap", risk_cap.stamp))))
    _basis = C.DayBasis(judged_lights=int(_judged), total_lights=int(_total), tally=_tally,
                        all_rows_judged=_all_judged, cruise_gate_open=_cruise_open,
                        digest_data_short=_digest_short)
    return _state, _basis


__all__ = [
    "CRUISE_TEXT", "judged_count", "is_fully_judged", "aggregate_judged", "tally_states",
    "cruise_or_gap", "has_system_risk_cap", "risk_cap_state_from_allocation", "aggregate_system_actions",
]
