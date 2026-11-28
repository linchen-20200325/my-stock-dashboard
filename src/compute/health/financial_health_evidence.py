"""src/compute/health/financial_health_evidence.py — 財報「證據 pack」（L2 純函式，離線）。

單一財報期間的**具名原值 + 少數可逐一對上既有定義的比率**，每個數字都帶
期間 / 來源 / 單位 / 口徑 / 發布可得日 / 缺值原因。**不是評分、不是標籤、不是任何操作語意**。

§8.2 layer：L2 —— 零 I/O、零時鐘、零 streamlit、不 import `src.data` / `src.services`，
也**不** import `financial_health_engine`（避免拖入其 import 鏈）。本模組不改既有引擎、
取數層、門檻、Schema、caller。

════════════════════════════════════════════════════════════════════
為什麼不吃 legacy `fin_data` 字典
════════════════════════════════════════════════════════════════════
legacy 取數層（`financial_statements_fetcher._v()`）查無時回 ``0.0``、各比率分母為 0 時也回 ``0``，
缺值與真 0 無法區分。本模組改吃**型別化輸入** ``FinancialPeriodInput``：缺值＝``None``，
真 0 是觀測值並照實保留（例：總負債真的是 0 → ``debt_ratio_pct == 0.0``）。

════════════════════════════════════════════════════════════════════
可輸出的比率（與既有定義逐一對照；對照測試見 tests/test_financial_health_evidence.py）
════════════════════════════════════════════════════════════════════
- gross_margin_pct      = 毛利 / 營收 × 100            （取數層 ``gp / rev * 100``）
- operating_margin_pct  = 營業利益 / 營收 × 100        （引擎 ``_no_ai_profitability``）
- net_margin_pct        = 稅後淨利 / 營收 × 100        （同上）
- cash_ratio_pct        = 現金 / 總資產 × 100          （取數層 ``cash / assets * 100``）
- debt_ratio_pct        = 總負債 / 總資產 × 100        （取數層 ``liab / assets * 100``）
- current_ratio  (倍)   = 流動資產 / 流動負債          （引擎以 % 表示，本包換成倍數 = 引擎值 / 100）
- quick_ratio    (倍)   = (流動資產 − 存貨) / 流動負債  （同上；存貨欄必須存在，**不**把缺存貨當 0）
- ocf_to_net_income (倍)= 營業現金流 / 稅後淨利        （引擎 ``Earnings_Quality`` 以 % 表示；換算同上）

單位：``*_pct`` 為 ×100 的 float；倍數無單位；金額需同幣別同單位（本模組不驗證，只在 limitations 聲明）。
輸出一律 ``round(x, ROUND_DIGITS)``（引擎自身只取 1 位小數，對照時以其捨入誤差為容差）。

與引擎**刻意不同**之處（不是 bug）：引擎因 legacy 輸入缺值為 0，把「讀到 0」一律當缺漏；
本包輸入是型別化的，真 0 是有效觀測（例：現金 0 → 現金比 0.0%），缺值才是 ``None``。

════════════════════════════════════════════════════════════════════
明確**不輸出**（原因：口徑 / 公告日 / 公式未驗證，或屬聚合判定）
════════════════════════════════════════════════════════════════════
DSO / DPO / DIO（天數口徑與單季或累計未驗）、年化 ROE（引擎以單季 ×4 年化，口徑未驗）、
100-100-10 與現金流矩陣 / DNA、一切分數 / 標籤 / 分級、趨勢分數（缺口徑與公告日）。
此清單同時寫入每份輸出的 ``limitations``。

════════════════════════════════════════════════════════════════════
§1 Fail Loud / missing ≠ 0
════════════════════════════════════════════════════════════════════
- 結構性壞輸入 raise ``FinancialEvidenceInputError``（含 bool 值、未知科目名、naive fetched_at …）。
- 科目值為 NaN / ±inf **不 raise**：視為缺值（metric ``non_finite_input``），``items`` 內以 ``None`` 呈現，
  並記入 ``input_issues``；絕不變成 0。
- 分母 0 / 負 → ``unknown``，不是 0、不是 inf。
- 適用性：只有 ``company_type == "general"`` 才計算；金融股 / ETF → ``not_applicable``；
  ``unknown`` → ``unknown``。**沒有預設值**，必須顯式傳。新上市等適用性本模組無從判斷，
  亦不做任何「年數不足」的失敗判定。
- ``published_at`` 為 None → ``pit_status = "unknown_publication_date"``；有值只代表「來源有宣告日期」
  （``published_at_declared``），**永不宣稱時點正確性已被驗證**。
"""

from __future__ import annotations

import datetime as _dt
import math
import numbers
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Literal, Mapping

# ── 常數 ─────────────────────────────────────────────────────────────

#: 輸出比率的小數位數（單一來源；引擎只取 1 位，本包保留較多位避免二次捨入）。
ROUND_DIGITS = 4
#: 判定「分母為 0」的絕對容差（§4.3 浮點不用 ==）。
_ZERO_TOL = 1e-12

ITEM_NAMES: tuple[str, ...] = (
    "revenue", "cogs", "gross_profit", "operating_income", "net_income",
    "total_assets", "current_assets", "current_liabilities", "total_liabilities",
    "equity", "cash", "inventory", "ocf", "capex", "dividends",
)
COMPANY_TYPES: tuple[str, ...] = ("general", "financial", "etf", "unknown")
BASIS_VALUES: tuple[str, ...] = ("single_quarter", "cumulative")

STATUS_OK = "ok"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUSES: tuple[str, ...] = (STATUS_OK, STATUS_UNKNOWN, STATUS_NOT_APPLICABLE)

REASON_MISSING_INPUT = "missing_input"
REASON_ZERO_DENOMINATOR = "zero_denominator"
REASON_NON_POSITIVE_DENOMINATOR = "non_positive_denominator"
REASON_NON_FINITE_INPUT = "non_finite_input"
REASON_NON_FINITE_RESULT = "non_finite_result"
REASON_BASIS_UNKNOWN = "basis_unknown"
REASON_NOT_APPLICABLE_COMPANY_TYPE = "not_applicable_company_type"
REASON_UNKNOWN_COMPANY_TYPE = "unknown_company_type"
REASON_INVALID_NEGATIVE_INPUT = "invalid_negative_input"
REASON_INCONSISTENT_INPUT = "inconsistent_input"
REASON_CODES: tuple[str, ...] = (
    REASON_MISSING_INPUT, REASON_ZERO_DENOMINATOR, REASON_NON_POSITIVE_DENOMINATOR,
    REASON_NON_FINITE_INPUT, REASON_NON_FINITE_RESULT, REASON_BASIS_UNKNOWN,
    REASON_NOT_APPLICABLE_COMPANY_TYPE, REASON_UNKNOWN_COMPANY_TYPE,
    REASON_INVALID_NEGATIVE_INPUT, REASON_INCONSISTENT_INPUT,
)

PIT_UNKNOWN = "unknown_publication_date"
PIT_DECLARED = "published_at_declared"

#: 這些資產負債表科目不可能為負；負值視為荒謬輸入（unknown，不輸出）。
_NON_NEGATIVE_ITEMS = frozenset({"cash", "current_assets", "inventory", "total_liabilities"})

LIMITATION_BASIS = "財報口徑（單季或累計）由來源提供，未驗證時相關比率不輸出。"
LIMITATION_PIT = "未取得發布可得日時不聲稱時點正確，亦不可用於歷史判斷。"
LIMITATION_EXCLUDED = ("本包不輸出 DSO／DPO／DIO、年化 ROE、100-100-10、現金流矩陣與 DNA、"
                       "任何分數或標籤、趨勢分數；原因為口徑、公告日或公式未驗證。")
LIMITATION_UNITS = "金額欄位需為同一幣別與單位，本模組不驗證；比率不受單位影響。"
LIMITATION_NOT_APPLICABLE = "金融股與 ETF 的財報科目意義不同，一般公司比率不適用，一律不輸出。"
LIMITATION_UNKNOWN_TYPE = "公司類型未指明，適用性未證，比率一律不輸出。"
LIMITATION_BASIS_UNKNOWN = "此期口徑未知，損益與現金流量類比率不輸出。"
LIMITATION_NON_FINITE = "部分科目值為 NaN 或 inf，已視為缺值，不以 0 代替。"
LIMITATION_PIT_DECLARED = "發布日為來源所宣告，本模組未驗證其正確性。"


class FinancialEvidenceInputError(ValueError):
    """輸入結構性錯誤（§1 Fail Loud）。訊息說明哪個欄位 / 條件違規。"""


# ── 資料結構 ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FinancialPeriodInput:
    """單一財報期間的型別化輸入。缺值＝None；真 0 保留為 0。"""

    period_end: _dt.date
    source: str
    fetched_at: _dt.datetime
    unit: str
    basis: Literal["single_quarter", "cumulative"] | None
    published_at: _dt.date | None
    items: Mapping[str, float | None]


@dataclass(frozen=True)
class EvidenceMetric:
    """一個比率的證據。value 只有 status == 'ok' 才非 None。"""

    name: str
    value: float | None
    status: str
    reason_code: str | None
    formula_id: str
    inputs: tuple[str, ...]
    unit_label: str

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise FinancialEvidenceInputError(f"metric.status 不合法：{self.status!r}")
        if self.status == STATUS_OK:
            if (self.value is None or self.reason_code is not None
                    or not math.isfinite(self.value)):
                raise FinancialEvidenceInputError("status=ok 必須有有限 value 且無 reason_code")
        else:
            if self.value is not None or self.reason_code not in REASON_CODES:
                raise FinancialEvidenceInputError("非 ok 的 metric 必須 value=None 且帶合法 reason_code")


@dataclass(frozen=True)
class FinancialEvidence:
    """單期財報證據。無任何分數、標籤或操作語意欄位。"""

    period_end: _dt.date
    source: str
    fetched_at: _dt.datetime
    unit: str
    basis: str | None
    published_at: _dt.date | None
    pit_status: str
    company_type: str
    items: Mapping[str, float | None]
    metrics: Mapping[str, EvidenceMetric]
    limitations: tuple[str, ...]
    input_issues: tuple[str, ...]


# ── 比率規格（單一來源）──────────────────────────────────────────────

@dataclass(frozen=True)
class _Spec:
    name: str
    formula_id: str
    inputs: tuple[str, ...]
    numerator: Callable[[Mapping[str, float]], float]
    denominator: str
    scale: float
    unit_label: str
    flow: bool                      # True＝涉及損益 / 現金流量科目，受 basis 影響
    zero_means_non_positive: bool   # True＝分母 ≤ 0 一律回 non_positive_denominator
    numerator_must_be_non_negative: bool = False


_SPECS: tuple[_Spec, ...] = (
    _Spec("gross_margin_pct", "gross_profit/revenue*100", ("gross_profit", "revenue"),
          lambda v: v["gross_profit"], "revenue", 100.0, "%", True, False),
    _Spec("operating_margin_pct", "operating_income/revenue*100", ("operating_income", "revenue"),
          lambda v: v["operating_income"], "revenue", 100.0, "%", True, False),
    _Spec("net_margin_pct", "net_income/revenue*100", ("net_income", "revenue"),
          lambda v: v["net_income"], "revenue", 100.0, "%", True, False),
    _Spec("cash_ratio_pct", "cash/total_assets*100", ("cash", "total_assets"),
          lambda v: v["cash"], "total_assets", 100.0, "%", False, False),
    _Spec("debt_ratio_pct", "total_liabilities/total_assets*100",
          ("total_liabilities", "total_assets"),
          lambda v: v["total_liabilities"], "total_assets", 100.0, "%", False, False),
    _Spec("current_ratio", "current_assets/current_liabilities",
          ("current_assets", "current_liabilities"),
          lambda v: v["current_assets"], "current_liabilities", 1.0, "倍", False, False),
    _Spec("quick_ratio", "(current_assets-inventory)/current_liabilities",
          ("current_assets", "inventory", "current_liabilities"),
          lambda v: v["current_assets"] - v["inventory"], "current_liabilities", 1.0, "倍",
          False, False, numerator_must_be_non_negative=True),
    _Spec("ocf_to_net_income", "ocf/net_income", ("ocf", "net_income"),
          lambda v: v["ocf"], "net_income", 1.0, "倍", True, True),
)
METRIC_NAMES: tuple[str, ...] = tuple(s.name for s in _SPECS)


# ── 輸入驗證 / 正規化 ────────────────────────────────────────────────

def _validate_period(p: FinancialPeriodInput) -> None:
    if not isinstance(p, FinancialPeriodInput):
        raise FinancialEvidenceInputError(
            f"period 必須是 FinancialPeriodInput，收到 {type(p).__name__}")
    if isinstance(p.period_end, _dt.datetime) or not isinstance(p.period_end, _dt.date):
        raise FinancialEvidenceInputError("period_end 必須是 datetime.date（不接受 datetime）")
    if not isinstance(p.source, str) or not p.source.strip():
        raise FinancialEvidenceInputError("source 必須是非空字串")
    if not isinstance(p.unit, str) or not p.unit.strip():
        raise FinancialEvidenceInputError("unit 必須是非空字串")
    if (not isinstance(p.fetched_at, _dt.datetime) or p.fetched_at.tzinfo is None
            or p.fetched_at.utcoffset() is None):
        raise FinancialEvidenceInputError("fetched_at 必須是 tz-aware datetime")
    if p.basis is not None and p.basis not in BASIS_VALUES:
        raise FinancialEvidenceInputError(f"basis 不合法：{p.basis!r}（允許 {BASIS_VALUES} 或 None）")
    if p.published_at is not None:
        if isinstance(p.published_at, _dt.datetime) or not isinstance(p.published_at, _dt.date):
            raise FinancialEvidenceInputError("published_at 必須是 date 或 None（不接受 datetime）")
        if p.published_at < p.period_end:
            raise FinancialEvidenceInputError(
                f"published_at {p.published_at} 早於 period_end {p.period_end}（不可能）")
    if not isinstance(p.items, Mapping):
        raise FinancialEvidenceInputError("items 必須是 Mapping")


def _normalize_items(items: Mapping[str, object]) -> tuple[dict[str, float | None], set[str]]:
    """驗證科目名與值型別 → (完整 15 科目的 float|None 字典, 非有限值科目集合)。

    缺鍵＝None；NaN / ±inf 一律轉 None 並記入 nonfinite（**絕不轉 0**）；真 0 原樣保留。
    不改傳入映射。
    """
    unknown = sorted(str(k) for k in items if k not in ITEM_NAMES)
    if unknown:
        raise FinancialEvidenceInputError(f"items 含未知科目名：{unknown}（允許 {list(ITEM_NAMES)}）")
    out: dict[str, float | None] = {}
    nonfinite: set[str] = set()
    for name in ITEM_NAMES:
        raw = items.get(name)
        if raw is None:
            out[name] = None
            continue
        if isinstance(raw, bool) or not isinstance(raw, numbers.Real):
            raise FinancialEvidenceInputError(
                f"科目 {name} 值型別不合法：{type(raw).__name__}（只收 int / float / None，不收 bool）")
        try:
            val = float(raw)
        except OverflowError as exc:
            raise FinancialEvidenceInputError(f"科目 {name} 數值過大無法轉 float") from exc
        if math.isfinite(val):
            out[name] = _pos_zero(val)
        else:
            out[name] = None
            nonfinite.add(name)
    return out, nonfinite


# ── 閘門與運算 ───────────────────────────────────────────────────────

def _company_gate(company_type: str) -> tuple[str, str] | None:
    """回傳 (status, reason_code) 表示整份不計算；None 表示可計算。"""
    if company_type == "general":
        return None
    if company_type == "unknown":
        return STATUS_UNKNOWN, REASON_UNKNOWN_COMPANY_TYPE
    return STATUS_NOT_APPLICABLE, REASON_NOT_APPLICABLE_COMPANY_TYPE


def _basis_gate(spec: _Spec, basis: str | None) -> str | None:
    """損益 / 現金流量類比率在口徑未知時不輸出。回傳 reason_code 或 None。"""
    if spec.flow and basis is None:
        return REASON_BASIS_UNKNOWN
    return None


def _denominator_reason(d: float, non_positive_only: bool) -> str | None:
    """分母不可用 → reason_code；可用 → None。"""
    if non_positive_only:
        return REASON_NON_POSITIVE_DENOMINATOR if d <= _ZERO_TOL else None
    if math.isclose(d, 0.0, abs_tol=_ZERO_TOL):
        return REASON_ZERO_DENOMINATOR
    if d < 0:
        return REASON_NON_POSITIVE_DENOMINATOR
    return None


def _pos_zero(x: float) -> float:
    """負零正規化：-0.0 + 0.0 == +0.0，其餘值不變（輸出不得出現 -0.0）。"""
    return x + 0.0


def _unknown(spec: _Spec, reason: str, status: str = STATUS_UNKNOWN) -> EvidenceMetric:
    return EvidenceMetric(spec.name, None, status, reason, spec.formula_id,
                          spec.inputs, spec.unit_label)


def _evaluate(spec: _Spec, vals: Mapping[str, float | None], nonfinite: set[str],
              basis: str | None) -> EvidenceMetric:
    reason = _basis_gate(spec, basis)
    if reason is not None:
        return _unknown(spec, reason)
    if any(n in nonfinite for n in spec.inputs):
        return _unknown(spec, REASON_NON_FINITE_INPUT)
    if any(vals[n] is None for n in spec.inputs):
        return _unknown(spec, REASON_MISSING_INPUT)
    got = {n: float(vals[n]) for n in spec.inputs}  # type: ignore[arg-type]
    if any(n in _NON_NEGATIVE_ITEMS and got[n] < 0 for n in spec.inputs):
        return _unknown(spec, REASON_INVALID_NEGATIVE_INPUT)
    reason = _denominator_reason(got[spec.denominator], spec.zero_means_non_positive)
    if reason is not None:
        return _unknown(spec, reason)
    num = spec.numerator(got)
    if spec.numerator_must_be_non_negative and num < 0:
        return _unknown(spec, REASON_INCONSISTENT_INPUT)
    val = num / got[spec.denominator] * spec.scale
    if not math.isfinite(val):
        return _unknown(spec, REASON_NON_FINITE_RESULT)
    return EvidenceMetric(spec.name, _pos_zero(round(val, ROUND_DIGITS)), STATUS_OK, None,
                          spec.formula_id, spec.inputs, spec.unit_label)


# ── 主函式 ───────────────────────────────────────────────────────────

def build_financial_evidence(period: FinancialPeriodInput, *,
                             company_type: str) -> FinancialEvidence:
    """由單期型別化輸入建立 ``FinancialEvidence``。純函式、不改輸入、不讀時鐘。

    ``company_type`` 為 keyword-only 且**無預設值**：必須顯式指定
    ``"general" | "financial" | "etf" | "unknown"``。

    Raises:
        FinancialEvidenceInputError: 輸入結構性錯誤。
    """
    _validate_period(period)
    if not isinstance(company_type, str) or company_type not in COMPANY_TYPES:
        raise FinancialEvidenceInputError(
            f"company_type 不合法：{company_type!r}（允許 {COMPANY_TYPES}）")
    vals, nonfinite = _normalize_items(period.items)

    gate = _company_gate(company_type)
    metrics: dict[str, EvidenceMetric] = {}
    for spec in _SPECS:
        if gate is not None:
            metrics[spec.name] = _unknown(spec, gate[1], gate[0])
        else:
            metrics[spec.name] = _evaluate(spec, vals, nonfinite, period.basis)

    issues = tuple(f"non_finite_item:{n}" for n in ITEM_NAMES if n in nonfinite)
    limitations = [LIMITATION_BASIS, LIMITATION_PIT, LIMITATION_EXCLUDED, LIMITATION_UNITS]
    if company_type in ("financial", "etf"):
        limitations.append(LIMITATION_NOT_APPLICABLE)
    elif company_type == "unknown":
        limitations.append(LIMITATION_UNKNOWN_TYPE)
    if period.basis is None:
        limitations.append(LIMITATION_BASIS_UNKNOWN)
    if period.published_at is not None:
        limitations.append(LIMITATION_PIT_DECLARED)
    if nonfinite:
        limitations.append(LIMITATION_NON_FINITE)

    return FinancialEvidence(
        period_end=period.period_end,
        source=period.source,
        fetched_at=period.fetched_at,
        unit=period.unit,
        basis=period.basis,
        published_at=period.published_at,
        pit_status=PIT_UNKNOWN if period.published_at is None else PIT_DECLARED,
        company_type=company_type,
        items=MappingProxyType(dict(vals)),
        metrics=MappingProxyType(metrics),
        limitations=tuple(limitations),
        input_issues=issues,
    )
