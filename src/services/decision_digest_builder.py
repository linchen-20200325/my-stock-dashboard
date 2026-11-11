"""L3 Service — Decision Digest Builder（AB-1）：把既有規則層輸出**搬運**成 `DecisionDigest`。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
DEC-092 後 D2.5 計畫的 AB-1（`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5；設計草案
`docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §4／§11）。一支**純函式**
`build_decision_digest`：不取數、不讀檔、不碰 streamlit／session、不接 AI、不接 UI。
它只**搬運**呼叫端傳進來的既有服務輸出（`get_macro_state`／`get_allocation`／
`dividend_station_service` 的列／`holdings_service` 的列），不重算、不改寫任何一個。

═══ 核心原則：builder 不發明日期、不發明鍵 ═════════════════════════════
- 五個服務輸出**都不回傳** `as_of`／`fetched_at`。日期只能由呼叫端以 `SourceStamp`
  明確傳入（`source` 必須是資料來源名稱，不得是 AI）；沒有 stamp → 該筆事實是
  `MISSING`＋`NO_INPUT`（絕不以「現在」或今天的日期代替）。
- 唯一既有的日期是 Risk Cap 快照的 `risk_cap_disclosure.snapshot_ts`（台北時間字串
  `%Y-%m-%d %H:%M:%S`），以 Asia/Taipei 解讀、取日期部分；缺或解析失敗 → 上限事實 MISSING。
- `portfolio_id` **沒有來源**（AB-4r 才決定）。有鍵的持股只來自呼叫端傳入的
  `holding_keys`（ticker → HoldingKey）；builder **絕不**從 `portfolio_name` 或任何東西推導鍵。
  held 但無鍵的列只計入 `unkeyed_count`。

═══ 各段搬運規則 ════════════════════════════════════════════════════════
market    只搬 `regime`（文字）／`light`（文字）／`health`（有限數值），逐字、不重算。
          `OK` 只在有 `macro_stamp` 且 macro_state 已載入時成立。`is_loaded` 不為 True、regime
          為 'unknown'、light 為 '⬜'、health 為 None → 該事實 `MISSING`＋`NO_INPUT`（最接近的既有
          MissingReason：上游「未評估」＝沒有輸入可判，非抓取失敗）；health 非有限數值 → `INVALID`
          （AB-0 D11：有值但不合法，值丟棄）。unknown／⬜ 絕不被映成中性值。
risk_cap  `cap_pct` 取 `macro_state['exposure_limit_pct']`（⛔ 不是 `AllocationDecision.cap_pct`
          ——那是多條 cap 的最小值）。`exposure_lo/hi_pct` 取 `allocation.final_lo/final_hi`，
          **僅在** `allocation.is_loaded` 且有 `macro_stamp`（allocation 由 macro_state 推得，
          其日期用 macro 的 stamp；沒有 stamp 就不宣稱日期）時為 OK。
          `cap_valid` 是**代理判斷**：`exposure_limit_pct` 為 0..100 的有限實數 且 揭露內有
          可解析的 `snapshot_ts`。服務不回傳直接旗標；builder 不呼叫
          `is_valid_risk_cap_snapshot`、不重讀檔。真實的 0 是 ok／0，None 是 missing。
          rule＝`RuleRef('risk_cap', RISK_CAP_RULESET_VERSION)`。不推導 STALE（無輸入可判）。
tw_trend／intl_trend／industry／valuation
          永遠是 AB-0 固定的定義狀態段（NOT_DEFINED ×3、valuation RESEARCH_ONLY），不填。
          ⚠️ 產業集中度（`compute_industry_concentration`）與選股排名（`get_ranked_picks`）
          **不搬**：契約沒有對應的段（C §11 第 4／14 列），故不接受為參數。
holdings  `holdings_rows is None` → UNAVAILABLE＋NO_INPUT、`unkeyed_count=0`（未知，不是零）。
          策略一律 `未分類`（`strategy_source=None`，AB-0 對未分類的唯一合法形式）。
          ⚠️ 契約的 holdings 可得性由 entries 的 facts 推導；v1 的 entry facts 只有「行動事實」，
          所以**沒有任何行動事實時 holdings 為 UNAVAILABLE**（即使有鍵的持股存在）。
actions   只搬 `dividend_station_service` 持有列上 `_action` ∈ {cut, take_profit_force,
          take_profit_partial, pause_add, add} 者（premium／cruise／未知碼一律不搬），
          須無 `_detail.error`、held、有鍵（且鍵在 holdings 內）、有 `station_stamp`。
          `text` 逐字取 `row['建議動作']`。依 Q4 序（見 `shared.decision_digest_rules`）排序，
          `priority_rank`＝1..n，**截斷至 MAX_ACTIONS(3)**（上游仍有完整清單，這裡只是 Digest 的上限）。
          個股汰換字串（`assess_stock`）與 `flag_take_profit`（衛星≥15%）沒有 Q4 位階 → v1 不搬。
          契約規定 actions 為 AVAILABLE 需 holdings 非 UNAVAILABLE，故 v1 builder 只在「至少一項
          行動」時 AVAILABLE；否則 UNAVAILABLE＋NO_INPUT（「沒有要做的事」與「判不出來」在 v1
          無法區分——見 AB-1 報告）。
ai_participation  一律 RULE_ONLY。

輸入型別：`macro_state` 須為 Mapping 或 None；`allocation` 須為 None 或帶 `is_loaded`／`final_lo`／`final_hi`
的物件；`*_rows` 須為 list／tuple 或 None；`holding_keys` 須為 Mapping 或 None；`*_stamp` 須為
`SourceStamp` 或 None —— 型別不對 → `TypeError`（Fail Loud，不默默當成「沒給」）。
帶 `_invalid_lights`／`_invalid_inputs`（非空）的站內列整列不搬行動（Digest 內不揭露：AB-0 無對應欄位；
排除數與被 `MAX_ACTIONS` 截掉的候選數，改由 `plan_action_selection` 供**側車** coverage 揭露，見
`src/services/decision_digest_assembly.py`／`shared/decision_digest_coverage.py`，Issue #1127）。
`held` 非 bool／None、`is_loaded` 非 bool／None → `TypeError`。上游 L4 缺口（cap 與 final_hi 交叉、health 範圍、
舊 snapshot_ts 不推 STALE）屬規格明言／上游責任，本檔不補。
可搬運的行動列若 `建議動作` 不是非空 str → `ValueError`（分支碼在、文字不在＝規則層契約漂移，
不得默默丟掉一個可能是汰弱的行動）。

回傳前一律 `assert_strict`（AB-0 `validate` ＋ rule_id 允許名單 ＋ 行動排序）；違規即 `ValueError`。

分層（CLAUDE.md §8.2）：L3 —— 只 import 標準函式庫與 L0（`shared.*`）。
"""
from __future__ import annotations

import math
import numbers
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from shared.decision_digest import (
    MAX_ACTIONS, PLACEHOLDER_TEXTS, ActionOrigin, ActionRef, ActionsSection, AiParticipation, Availability,
    DataStatus, DecisionDigest, DefinitionSection, DefinitionState, Fact, FactSection, HoldingEntry,
    HoldingKey, HoldingsSection, MissingReason, Provenance, RiskCapSection, RuleRef, StrategyType,
    derive_availability,
)
from shared.decision_digest_rules import (
    ACTION_RULE_IDS, ACTION_RULE_VERSION, assert_strict, q4_sort_index,
)
from shared.regime_arbiter import REGIME_LIGHT, UNLOADED_VERDICT
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION
from shared.station_specs import KEY_INVALID_INPUTS, KEY_INVALID_LIGHTS

#: Risk Cap 快照 `timestamp` 的格式（= `macro_state_locker._TIMESTAMP_FMT`；L3 之間不互相 import，故複本）。
_SNAPSHOT_TS_FMT = "%Y-%m-%d %H:%M:%S"

#: 缺值事實的來源標籤（Provenance.source 必填；這是「本該來自哪支服務輸出」的名稱，不是資料來源宣稱）。
_SRC_MACRO = "macro_state"
_SRC_ALLOCATION = "allocation"
_SRC_RISK_CAP = "risk_cap_snapshot"

#: 上游「未評估」佔位值（SSOT：`shared.regime_arbiter.UNLOADED_VERDICT`）；見 `_text_or_none`（大小寫變體由 AB-0 佔位字判定接住）。
_UNEVALUATED_REGIME = frozenset({UNLOADED_VERDICT.regime})
_UNEVALUATED_LIGHT = frozenset({UNLOADED_VERDICT.light})

#: `market.regime`／`market.light` 的合法詞彙（Issue #1144 A2；SSOT＝`shared.regime_arbiter.REGIME_LIGHT`，
#: 推導而來、不另存第六份手寫真相源）。比對用 `strip().lower()`；名單外的非空值 → INVALID（佔位字／未載入／無 stamp 仍 MISSING）。
_VALID_REGIMES = frozenset(set(REGIME_LIGHT) - {UNLOADED_VERDICT.regime})
_VALID_LIGHTS = frozenset(REGIME_LIGHT[r] for r in _VALID_REGIMES)

_RISK_CAP_RULE = RuleRef("risk_cap", RISK_CAP_RULESET_VERSION)


@dataclass(frozen=True)
class SourceStamp:
    """呼叫端明確提供的資料日戳（builder 不自己產生日期）。

    `source`：資料來源名稱（例："FRED"／"macro_state.json"），不得是 AI（Provenance 會拒收）；
    `as_of`：資料歸屬日（台股業務日）；`fetched_at`：tz-aware 抓取時間或 None。
    """
    source: str
    as_of: date
    fetched_at: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.source) is not str or not self.source.strip():
            raise ValueError(f"SourceStamp.source 必須是非空 str：{self.source!r}")
        if type(self.as_of) is not date:
            raise ValueError(f"SourceStamp.as_of 必須恰好是 datetime.date（不得是 datetime/str）：{self.as_of!r}")
        if self.fetched_at is not None and not (
                type(self.fetched_at) is datetime and self.fetched_at.utcoffset() is not None):
            raise ValueError(f"SourceStamp.fetched_at 必須是 tz-aware datetime 或 None：{self.fetched_at!r}")


# ── 小工具 ───────────────────────────────────────────────────────────────
def _finite_number(v: Any) -> bool:
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        return False
    try:
        return math.isfinite(v)
    except (OverflowError, TypeError, ValueError):
        return False


def _prov_missing(source: str) -> Provenance:
    return Provenance(source=source)


def _prov_from(stamp: SourceStamp) -> Provenance:
    return Provenance(source=stamp.source, as_of=stamp.as_of, fetched_at=stamp.fetched_at)


def _missing(fid: str, source: str, *, rule: RuleRef | None = None, unit: str | None = None,
             reason: MissingReason = MissingReason.NO_INPUT) -> Fact:
    return Fact(fact_id=fid, status=DataStatus.MISSING, provenance=_prov_missing(source),
                missing_reason=reason, rule=rule, unit=unit)


def _invalid(fid: str, source: str, *, rule: RuleRef | None = None, unit: str | None = None) -> Fact:
    return Fact(fact_id=fid, status=DataStatus.INVALID, provenance=_prov_missing(source),
                rule=rule, unit=unit)


def _get(mapping: Any, key: str) -> Any:
    return mapping.get(key) if isinstance(mapping, Mapping) else None


# ── market ───────────────────────────────────────────────────────────────
#: 與 AB-0 `_is_placeholder` 同形的「零值樣式」（0、0.0、0%…）；SSOT 是 AB-0，本複本由測試用 `Fact` 當 oracle 釘住。
_ZERO_LIKE_RE = re.compile(r"[0.]+%?")


def _is_placeholder_text(v: str) -> bool:
    """AB-0 缺值佔位字（`PLACEHOLDER_TEXTS`＋零值樣式）；NFKC → 去 Cc/Cf → casefold → 去空白後比對。"""
    n = "".join(ch for ch in unicodedata.normalize("NFKC", v)
                if unicodedata.category(ch) not in ("Cc", "Cf")).casefold()
    n = "".join(n.split())
    return n in PLACEHOLDER_TEXTS or bool(_ZERO_LIKE_RE.fullmatch(n))


def _text_or_none(v: Any, banned: frozenset) -> str | None:
    """逐字回傳；blank／上游「未評估」佔位值／AB-0 缺值佔位字（比對時去空白＋casefold）→ None（降級為缺值，
    不映成值、也不讓整份 Digest 因上游吐了 'N/A' 而崩潰）。"""
    if type(v) is not str or not v.strip() or v.strip() in banned or _is_placeholder_text(v):
        return None
    return v


def _flag(v: Any, name: str) -> bool:
    """bool 旗標：Python `bool` 或 None（＝未給，視為 False）；其餘型別 → TypeError（不默默當 False）。"""
    if v is None or type(v) is bool:
        return v is True
    raise TypeError(f"{name} 必須是 bool 或 None：{type(v).__name__} {v!r}")


def _market_section(macro_state: Mapping | None, stamp: SourceStamp | None) -> FactSection:
    loaded = _flag(_get(macro_state, "is_loaded"), "macro_state['is_loaded']")
    usable = loaded and stamp is not None
    src = stamp.source if stamp is not None else _SRC_MACRO

    def text_fact(fid: str, raw: Any, banned: frozenset, valid: Any) -> Fact:
        t = _text_or_none(raw, banned) if loaded else None
        if t is None or not usable:
            return _missing(fid, src)                       # MISSING 優先於 INVALID
        if t.strip().lower() not in valid:                  # 名單外的非空值：有值但不合法（值丟棄）
            return _invalid(fid, src)
        return Fact(fact_id=fid, status=DataStatus.OK, provenance=_prov_from(stamp), text=t)

    regime = text_fact("market.regime", _get(macro_state, "regime"), _UNEVALUATED_REGIME, _VALID_REGIMES)
    light = text_fact("market.light", _get(macro_state, "light"), _UNEVALUATED_LIGHT, _VALID_LIGHTS)

    h = _get(macro_state, "health") if loaded else None
    if h is None:
        health = _missing("market.health", src)
    elif not _finite_number(h):
        health = _invalid("market.health", src)
    elif not usable:
        health = _missing("market.health", src)
    else:
        health = Fact(fact_id="market.health", status=DataStatus.OK, provenance=_prov_from(stamp),
                      value=float(h))
    facts = (regime, light, health)
    av = derive_availability(facts)
    return FactSection(availability=av, facts=facts,
                       missing_reason=MissingReason.NO_INPUT if av is Availability.UNAVAILABLE else None)


# ── risk cap ─────────────────────────────────────────────────────────────
def _snapshot_date(disclosure: Any) -> date | None:
    """`RiskCapDisclosure.snapshot_ts`（台北時間字串）→ 台北日期；缺／解析失敗 → None（不猜）。"""
    ts = getattr(disclosure, "snapshot_ts", None)
    if ts is None and isinstance(disclosure, Mapping):
        ts = disclosure.get("snapshot_ts")
    if type(ts) is not str or not ts.strip():
        return None
    try:
        # 字串本身就是台北時間：取日期部分即可，⛔ 不做任何時區換算（換成 UTC 會在 00:00–08:00 差一天）。
        return datetime.strptime(ts.strip(), _SNAPSHOT_TS_FMT).date()
    except ValueError:
        return None


def _pct_fact(fid: str, raw: Any, *, as_of_prov: Provenance | None, src: str) -> Fact:
    """0..100 的有限實數 → OK（需有日期）；None → MISSING；不合法 → INVALID。0 是真的 0。"""
    if raw is None:
        return _missing(fid, src, rule=_RISK_CAP_RULE, unit="%")
    if not _finite_number(raw) or not (0 <= raw <= 100):
        return _invalid(fid, src, rule=_RISK_CAP_RULE, unit="%")
    if as_of_prov is None:
        return _missing(fid, src, rule=_RISK_CAP_RULE, unit="%")
    return Fact(fact_id=fid, status=DataStatus.OK, provenance=as_of_prov, value=float(raw),
                unit="%", rule=_RISK_CAP_RULE)


def _risk_cap_section(macro_state: Mapping | None, allocation: Any,
                      macro_stamp: SourceStamp | None) -> RiskCapSection:
    # 只讀 macro_state 的揭露（A.3）；不退而讀 allocation.risk_cap_disclosure（那是另一條取數路徑）。
    disclosure = _get(macro_state, "risk_cap_disclosure")
    snap_date = _snapshot_date(disclosure)
    cap_prov = (Provenance(source=_SRC_RISK_CAP, as_of=snap_date) if snap_date is not None else None)
    raw_cap = _get(macro_state, "exposure_limit_pct")
    cap = _pct_fact("risk_cap.cap_pct", raw_cap, as_of_prov=cap_prov, src=_SRC_RISK_CAP)
    cap_valid = cap.status is DataStatus.OK

    alloc_loaded = _flag(getattr(allocation, "is_loaded", None), "allocation.is_loaded")
    lo_prov = _prov_from(macro_stamp) if (alloc_loaded and macro_stamp is not None) else None
    lo_raw = getattr(allocation, "final_lo", None) if alloc_loaded else None
    hi_raw = getattr(allocation, "final_hi", None) if alloc_loaded else None
    lo = _pct_fact("risk_cap.exposure_lo_pct", lo_raw, as_of_prov=lo_prov, src=_SRC_ALLOCATION)
    hi = _pct_fact("risk_cap.exposure_hi_pct", hi_raw, as_of_prov=lo_prov, src=_SRC_ALLOCATION)
    av = derive_availability((cap, lo, hi))
    return RiskCapSection(cap_valid=cap_valid, cap_pct=cap, exposure_lo_pct=lo, exposure_hi_pct=hi,
                          availability=av,
                          missing_reason=MissingReason.NO_INPUT if av is Availability.UNAVAILABLE else None)


# ── holdings & actions ───────────────────────────────────────────────────
def _is_held(row: Mapping) -> bool:
    """`held` 須是 Python `bool` 或缺／None（＝非持有）；其餘型別（np.bool_、'True'、1…）→ TypeError。
    ⛔ 不默默當非持有 —— 那會吞掉一個可能是汰弱的行動。"""
    return _flag(row.get("held"), "row['held']")


def _ticker_of(row: Mapping) -> str | None:
    t = row.get("ticker")
    if t is None:
        t = row.get("代號")
    return t if type(t) is str and t.strip() else None


def _key_for(ticker: str | None, holding_keys: Mapping | None) -> HoldingKey | None:
    if ticker is None or holding_keys is None:
        return None
    k = holding_keys.get(ticker)
    if k is None:
        return None
    if type(k) is not HoldingKey:
        raise TypeError(f"holding_keys[{ticker!r}] 必須恰好是 HoldingKey：{type(k).__name__}")
    if k.symbol != ticker:
        raise ValueError(f"holding_keys[{ticker!r}].symbol={k.symbol!r} 與 ticker 不一致（builder 不改鍵）")
    return k


#: 站內列「合法且已知」的**非行動**碼（`dividend_station.ACTION_PREMIUM`／`ACTION_CRUISE` 的複本；L3 不得 import
#: `src.compute`，故以字串複本登記，由測試 pin 住與 `dividend_station.ACTION_*` 的一致）。用 tuple 而非 frozenset：
#: 站內列的 `_action` 可能是任何東西（含不可 hash 者），`in tuple` 只用 `==`，不會 raise。
_NON_ACTION_CODES: tuple = ("premium", "cruise")


@dataclass(frozen=True)
class _ScanResult:
    """站內列掃描結果：**每一列**恰好歸入下列互斥且窮盡的分類之一（分割恆等式，由測試守住）：

        rows_total == len(candidates) + non_action + not_held + excluded_invalid
                      + unrecognized + unmatched + non_mapping

    (a) `candidates`：成為行動候選。
    (b) 合法且已知的排除：`not_held`（held 缺／False）、`non_action`（合法非行動碼 premium／cruise，且 ticker
        對得上 held 持股）、`excluded_invalid`（held 且帶 `_invalid_lights`／`_invalid_inputs`／`_detail.error`）。
    (c) 「未能讀入」：`non_mapping`（非 Mapping 的項）、`unrecognized`（held、無異常，但 `_action` 缺／None／未知碼，
        例如 'Add'、'zzz'）、`unmatched`（held、無異常、碼合法，但 ticker 對不上持股：行動碼要求對得上有鍵的 held
        持股，非行動碼要求 ticker 在 held 持股內）。
    另有一個**正交的疊加計數** `duplicate_rows`（不屬於分割）：held 的站內列中，ticker（非空）出現在 ≥2 個 held 列的
    **所有**列數。同 ticker 多列代表站內證據彼此可能衝突；builder 既有選取行為不變，但任何一列都不得被默默選用而
    不揭露。
    """
    candidates: list
    rows_total: int = 0
    non_mapping: int = 0
    not_held: int = 0
    excluded_invalid: int = 0
    non_action: int = 0
    unrecognized: int = 0
    unmatched: int = 0
    duplicate_rows: int = 0


def _scan_action_rows(station_rows: Sequence[Mapping] | None, station_stamp: SourceStamp | None,
                      keyed: frozenset, holding_keys: Mapping | None,
                      held_tickers: frozenset = frozenset()) -> _ScanResult:
    """單一掃描迴圈：把**每一列**歸入 `_ScanResult` 的互斥窮盡分類（見該類 docstring）。

    ⚠️ 這是 `_action_candidates`（`build_decision_digest` 的路徑）與 `plan_action_selection`
    （Issue #1127 S8 的省略揭露）**共用的唯一判定**——兩者不得各自重寫一份（會漂移）。
    分支順序與 builder 原本逐一相同（非 Mapping → held → 異常旗標 → `_detail.error` → 行動碼 → 鍵 → 文字），
    只是在原本 `continue` 的地方多記一筆分類計數；候選與例外行為不變。
    `held_tickers`：held 持股的 ticker 集合，只用來判定「非行動碼的列 ticker 是否對得上持股」（不影響候選）。
    `station_rows`／`station_stamp` 為 None 時不掃描 → 全 0（呼叫端以 `evaluated` 區分「未知」與「0」）。
    """
    if station_rows is None or station_stamp is None:
        return _ScanResult(candidates=[])
    out: list = []
    n_total = n_nonmap = n_nothel = n_invalid = n_nonact = n_unrec = n_unm = 0
    ticker_count: dict = {}
    for row in station_rows:
        n_total += 1
        if not isinstance(row, Mapping):
            n_nonmap += 1
            continue
        if not _is_held(row):
            n_nothel += 1
            continue
        tk = _ticker_of(row)
        if tk is not None:
            ticker_count[tk] = ticker_count.get(tk, 0) + 1
        # 帶資料異常標記（非空）的列整列不搬：不用壞資料給建議（fail-safe）。Digest 內沒有「列被排除」的欄位可揭露，
        # 排除數由 `plan_action_selection` 以側車 coverage 揭露；空 list／空 dict 視為無異常。
        if row.get(KEY_INVALID_LIGHTS) or row.get(KEY_INVALID_INPUTS):
            n_invalid += 1
            continue
        detail = row.get("_detail")
        if isinstance(detail, Mapping) and detail.get("error"):
            n_invalid += 1
            continue
        code = row.get("_action")
        if code not in ACTION_RULE_IDS:
            if code in _NON_ACTION_CODES:
                if tk is not None and tk in held_tickers:
                    n_nonact += 1
                else:
                    n_unm += 1
            else:
                n_unrec += 1
            continue
        key = _key_for(tk, holding_keys)
        if key is None or key not in keyed:
            n_unm += 1
            continue
        text = row.get("建議動作")
        if type(text) is not str or not text.strip():
            raise ValueError(f"站內列 {key.symbol!r} 的 _action={code!r} 但 建議動作 不是非空 str：{text!r}"
                             "（規則層契約漂移；不得默默丟掉行動）")
        out.append((key, code, text))
    return _ScanResult(candidates=out, rows_total=n_total, non_mapping=n_nonmap, not_held=n_nothel,
                       excluded_invalid=n_invalid, non_action=n_nonact, unrecognized=n_unrec, unmatched=n_unm,
                       duplicate_rows=sum(n for n in ticker_count.values() if n >= 2))


def _action_candidates(station_rows: Sequence[Mapping] | None, station_stamp: SourceStamp | None,
                       keyed: frozenset, holding_keys: Mapping | None) -> list:
    """合格行動候選：(HoldingKey, branch_code, 原樣文字)，保持輸入順序。"""
    return _scan_action_rows(station_rows, station_stamp, keyed, holding_keys).candidates


def _order_candidates(cands: list) -> list:
    """Q4 序（stable）。`build_decision_digest` 與 `plan_action_selection` 共用。"""
    return sorted(cands, key=lambda c: q4_sort_index(c[1]))


def _keyed_holdings(holdings_rows: Sequence[Mapping], holding_keys: Mapping | None) -> tuple:
    """持有列 → (有鍵的 HoldingKey 依輸入順序（保留重複）, 無鍵持有列數)。"""
    keys_in_order: list = []   # 保留重複，讓契約檢查（duplicate_holding_key）看得到，不默默去重
    unkeyed = 0
    for row in holdings_rows:
        if not isinstance(row, Mapping) or not _is_held(row):
            continue
        key = _key_for(_ticker_of(row), holding_keys)
        if key is None:
            unkeyed += 1
        else:
            keys_in_order.append(key)
    return keys_in_order, unkeyed


def _holdings_and_actions(holdings_rows: Sequence[Mapping] | None, holding_keys: Mapping | None,
                          station_rows: Sequence[Mapping] | None,
                          station_stamp: SourceStamp | None) -> tuple:
    if holdings_rows is None:
        return (HoldingsSection(availability=Availability.UNAVAILABLE, entries=(),
                                missing_reason=MissingReason.NO_INPUT, unkeyed_count=0),
                ActionsSection(availability=Availability.UNAVAILABLE, items=(),
                               missing_reason=MissingReason.NO_INPUT))
    keys_in_order, unkeyed = _keyed_holdings(holdings_rows, holding_keys)
    keyed = frozenset(keys_in_order)

    cands = _action_candidates(station_rows, station_stamp, keyed, holding_keys)
    ordered = _order_candidates(cands)  # stable
    chosen = ordered[:MAX_ACTIONS]

    facts_by_key: dict = {}
    items: list = []
    for rank, (key, code, text) in enumerate(chosen, start=1):
        fid = f"action_fact:{key.portfolio_id}:{key.symbol}"
        rule = RuleRef(code, ACTION_RULE_VERSION)
        facts_by_key[key] = Fact(fact_id=fid, status=DataStatus.OK, provenance=_prov_from(station_stamp),
                                 text=text, rule=rule)
        items.append(ActionRef(action_id=f"action:{key.portfolio_id}:{key.symbol}", text=text,
                               origin=ActionOrigin.RULE_LAYER, rule=rule, evidence_refs=(fid,),
                               target=key, priority_rank=rank))

    entries = tuple(
        HoldingEntry(key=k, strategy=StrategyType.UNCLASSIFIED, strategy_source=None,
                     facts=((facts_by_key[k],) if k in facts_by_key else ()))
        for k in keys_in_order)
    derived = derive_availability(tuple(f for e in entries for f in e.facts)) if entries else Availability.UNAVAILABLE
    if derived is Availability.AVAILABLE and unkeyed > 0:
        derived = Availability.PARTIAL
    holdings = HoldingsSection(
        availability=derived, entries=entries,
        missing_reason=MissingReason.NO_INPUT if derived is Availability.UNAVAILABLE else None,
        unkeyed_count=unkeyed)

    # items 非空 ⇒ 至少一個 entry 帶行動事實 ⇒ holdings 不會是 UNAVAILABLE（結構保證；
    # 契約的 actions_available_without_holdings 仍由 assert_strict 兜底）。
    if items:
        actions = ActionsSection(availability=Availability.AVAILABLE, items=tuple(items))
    else:
        actions = ActionsSection(availability=Availability.UNAVAILABLE, items=(),
                                 missing_reason=MissingReason.NO_INPUT)
    return holdings, actions


# ── 輸入型別驗證（型別不對 → TypeError，不默默當成「沒給」）──────────────────
def _require(name: str, v: Any, ok: bool, expect: str) -> None:
    if not ok:
        raise TypeError(f"{name} 必須是 {expect}：{type(v).__name__}")


def _validate_inputs(macro_state: Any, macro_stamp: Any, allocation: Any, station_rows: Any,
                     station_stamp: Any, holdings_rows: Any, holding_keys: Any) -> None:
    _require("macro_state", macro_state, macro_state is None or isinstance(macro_state, Mapping),
             "Mapping 或 None")
    _require("macro_stamp", macro_stamp, macro_stamp is None or type(macro_stamp) is SourceStamp,
             "SourceStamp 或 None")
    _require("station_stamp", station_stamp, station_stamp is None or type(station_stamp) is SourceStamp,
             "SourceStamp 或 None")
    _require("allocation", allocation,
             allocation is None or all(hasattr(allocation, a) for a in ("is_loaded", "final_lo", "final_hi")),
             "None 或帶 is_loaded／final_lo／final_hi 的物件")
    _require("station_rows", station_rows, station_rows is None or type(station_rows) in (list, tuple),
             "list／tuple 或 None")
    _require("holdings_rows", holdings_rows, holdings_rows is None or type(holdings_rows) in (list, tuple),
             "list／tuple 或 None")
    _require("holding_keys", holding_keys, holding_keys is None or isinstance(holding_keys, Mapping),
             "Mapping 或 None")


# ── 行動選取計畫（Issue #1127 S8：省略揭露的資料來源；純加性，不改 build_decision_digest 輸出）──────────
@dataclass(frozen=True)
class ActionSelectionPlan:
    """`build_decision_digest` 在行動段做的選取，攤開來看（不改任何輸出，只讓「被省略／沒被讀進來」可被數出來）。

    **原則**：掃描時每一列都必須被歸入互斥且窮盡的分類之一（見 `_ScanResult`），不得有任何一列被靜默略過。
    不能評估的欄位一律 None（**未知不是 0**）。

    ── 能否評估與行動選取 ──
    - `evaluated`：`holdings_rows`／`station_rows`／`station_stamp` 任一為 None → False（builder 此時行動段 UNAVAILABLE）。
    - `ordered`：**全部**合格候選 (HoldingKey, branch_code, 原樣文字)，Q4 序（stable）；未評估 → ()。
    - `chosen`：`ordered[:MAX_ACTIONS]`，與 `build_decision_digest` 實際搬進 Digest 的行動逐一相同（parity 由測試守住）。

    ── 站內列分割（未評估 → 全 None）：rows_total == len(ordered) + station_non_action_rows + station_not_held_rows
         + excluded_invalid_rows + unrecognized_action_code_rows + unmatched_station_rows + station_non_mapping_rows ──
    - `station_rows_total`：掃描到的站內列總數。
    - 合法且已知的排除（不算遺漏）：`station_not_held_rows`、`station_non_action_rows`（premium／cruise 且 ticker 對得上
      held 持股）、`excluded_invalid_rows`（資料異常：`_invalid_lights`／`_invalid_inputs`／`_detail.error`；
      這個**算**未讀入，coverage 仍要求其為 0）。
    - 未能讀入：`station_non_mapping_rows`、`unrecognized_action_code_rows`（`_action` 缺／None／未知碼，含 'Add'、'zzz'）、
      `unmatched_station_rows`（held、無異常、碼合法，但 ticker 對不上持股／鍵；大小寫或空白不符、不在 `holdings_rows`、
      沒有 `HoldingKey`、非行動碼的 ticker 不在 held 持股）。
    - `duplicate_station_ticker_rows`：**正交疊加**（不在分割內）：同 ticker 出現在 ≥2 個 held 站內列者的所有列數。
    - `holdings_without_station_row`：held 持股中，站內列沒有同 ticker held 列者（＝沒有任何站內證據）的數量。
      比對一律精確字串（與鍵查找相同，不做大小寫或空白正規化）。

    ── 持有列分割（`holdings_rows` 為 None → 全 None）：holdings_rows_total == holdings_non_mapping_rows
         + holdings_not_held_rows + holdings_held_keyed_rows + unkeyed_held_count ──
    - `holdings_non_mapping_rows`：非 Mapping 的持有項（原本被靜默略過）。
    - `unkeyed_held_count`：held 但無鍵的持有列數（與 `HoldingsSection.unkeyed_count` 同判定；`holdings_rows is None` → None，
      builder 對此情形的 `unkeyed_count=0` 是「未知」，不是零）。
    """
    evaluated: bool
    ordered: tuple
    chosen: tuple
    excluded_invalid_rows: int | None
    unkeyed_held_count: int | None
    unmatched_station_rows: int | None = None
    holdings_without_station_row: int | None = None
    station_rows_total: int | None = None
    station_non_mapping_rows: int | None = None
    station_not_held_rows: int | None = None
    station_non_action_rows: int | None = None
    unrecognized_action_code_rows: int | None = None
    duplicate_station_ticker_rows: int | None = None
    holdings_rows_total: int | None = None
    holdings_non_mapping_rows: int | None = None
    holdings_not_held_rows: int | None = None
    holdings_held_keyed_rows: int | None = None

    @property
    def total_eligible(self) -> int | None:
        return len(self.ordered) if self.evaluated else None

    @property
    def omitted_count(self) -> int | None:
        return len(self.ordered) - len(self.chosen) if self.evaluated else None


def plan_action_selection(*, station_rows: Sequence[Mapping] | None = None,
                          station_stamp: SourceStamp | None = None,
                          holdings_rows: Sequence[Mapping] | None = None,
                          holding_keys: Mapping[str, HoldingKey] | None = None) -> ActionSelectionPlan:
    """純函式：重用 `build_decision_digest` 同一套判定（`_keyed_holdings`／`_scan_action_rows`／
    `_order_candidates`），回傳完整候選、實際選取與各種「沒被讀進 Digest」的計數。
    輸入型別驗證與 builder 相同（型別不對 → TypeError）。"""
    _require("station_stamp", station_stamp, station_stamp is None or type(station_stamp) is SourceStamp,
             "SourceStamp 或 None")
    _require("station_rows", station_rows, station_rows is None or type(station_rows) in (list, tuple),
             "list／tuple 或 None")
    _require("holdings_rows", holdings_rows, holdings_rows is None or type(holdings_rows) in (list, tuple),
             "list／tuple 或 None")
    _require("holding_keys", holding_keys, holding_keys is None or isinstance(holding_keys, Mapping),
             "Mapping 或 None")
    if holdings_rows is None:
        return ActionSelectionPlan(evaluated=False, ordered=(), chosen=(), excluded_invalid_rows=None,
                                   unkeyed_held_count=None)
    keys_in_order, unkeyed = _keyed_holdings(holdings_rows, holding_keys)
    h_total = len(holdings_rows)
    h_nonmap = sum(1 for r in holdings_rows if not isinstance(r, Mapping))
    h_nothel = sum(1 for r in holdings_rows if isinstance(r, Mapping) and not _is_held(r))
    holdings_side = dict(unkeyed_held_count=unkeyed, holdings_rows_total=h_total, holdings_non_mapping_rows=h_nonmap,
                         holdings_not_held_rows=h_nothel, holdings_held_keyed_rows=len(keys_in_order))
    if station_rows is None or station_stamp is None:
        return ActionSelectionPlan(evaluated=False, ordered=(), chosen=(), excluded_invalid_rows=None,
                                   **holdings_side)
    held_tickers = frozenset(t for t in (_ticker_of(r) for r in holdings_rows
                                         if isinstance(r, Mapping) and _is_held(r)) if t is not None)
    sc = _scan_action_rows(station_rows, station_stamp, frozenset(keys_in_order), holding_keys, held_tickers)
    ordered = tuple(_order_candidates(sc.candidates))
    return ActionSelectionPlan(
        evaluated=True, ordered=ordered, chosen=ordered[:MAX_ACTIONS], excluded_invalid_rows=sc.excluded_invalid,
        unmatched_station_rows=sc.unmatched,
        holdings_without_station_row=_count_holdings_without_station_row(holdings_rows, station_rows),
        station_rows_total=sc.rows_total, station_non_mapping_rows=sc.non_mapping, station_not_held_rows=sc.not_held,
        station_non_action_rows=sc.non_action, unrecognized_action_code_rows=sc.unrecognized,
        duplicate_station_ticker_rows=sc.duplicate_rows, **holdings_side)


def _count_holdings_without_station_row(holdings_rows: Sequence[Mapping], station_rows: Sequence[Mapping]) -> int:
    """held 持有列中，站內列裡沒有同 ticker（精確比對）held 列者的數量。"""
    covered = {t for t in (_ticker_of(r) for r in station_rows if isinstance(r, Mapping) and _is_held(r))
               if t is not None}
    n = 0
    for row in holdings_rows:
        if not isinstance(row, Mapping) or not _is_held(row):
            continue
        t = _ticker_of(row)
        if t is None or t not in covered:
            n += 1
    return n


# ── 入口 ─────────────────────────────────────────────────────────────────
def build_decision_digest(*, generated_at: datetime,
                          macro_state: Mapping | None = None,
                          macro_stamp: SourceStamp | None = None,
                          allocation: Any = None,
                          station_rows: Sequence[Mapping] | None = None,
                          station_stamp: SourceStamp | None = None,
                          holdings_rows: Sequence[Mapping] | None = None,
                          holding_keys: Mapping[str, HoldingKey] | None = None) -> DecisionDigest:
    """純函式：搬運既有輸出成 `DecisionDigest`（規則見模組 docstring）。違反契約 → `ValueError`。"""
    _validate_inputs(macro_state, macro_stamp, allocation, station_rows, station_stamp, holdings_rows,
                     holding_keys)
    holdings, actions = _holdings_and_actions(holdings_rows, holding_keys, station_rows, station_stamp)
    digest = DecisionDigest(
        generated_at=generated_at,
        market=_market_section(macro_state, macro_stamp),
        tw_trend=DefinitionSection(definition=DefinitionState.NOT_DEFINED),
        intl_trend=DefinitionSection(definition=DefinitionState.NOT_DEFINED),
        valuation=DefinitionSection(definition=DefinitionState.RESEARCH_ONLY),
        industry=DefinitionSection(definition=DefinitionState.NOT_DEFINED),
        holdings=holdings,
        risk_cap=_risk_cap_section(macro_state, allocation, macro_stamp),
        actions=actions,
        ai_participation=AiParticipation.RULE_ONLY,
    )
    assert_strict(digest)
    return digest


__all__ = ["SourceStamp", "build_decision_digest", "ActionSelectionPlan", "plan_action_selection"]
