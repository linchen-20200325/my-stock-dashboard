"""src/compute/health/financial_period_adapter.py — 財報「來源原值 → 證據 pack」轉接層（L2 純函式，離線）。

流程：**來源原值（具名科目觀測）→ ``FinancialPeriodInput`` → 既有 ``FinancialEvidence``**。
本層只吃呼叫端**已提供**的具名原始科目觀測，每筆觀測附明確的證據種類（``evidence``）、
來源科目原名；期間層附來源 / 期間 / 單位 / 幣別 / 發布可得日 / 取得時間 / 口徑 / 公司類型。
不讀 legacy 字典、不猜、不推。

§8.2 layer：L2 —— 零 I/O、零網路、零時鐘、零 streamlit；只 import 標準庫與
``src.compute.health.financial_health_evidence``（不 import 引擎、``src.data``、``src.services``）。
不改既有引擎 / 取數層 / pack / caller / UI / 門檻 / Schema；不另造比率或金融公式。

════════════════════════════════════════════════════════════════════
(a) 為什麼不吃 legacy ``fin_data`` 字典與 ``_v()``
════════════════════════════════════════════════════════════════════
legacy 取數層把「查無」「值為 0」「被重置」全部壓成同一個 ``0.0``，轉接層從輸出端
無法反推當初是哪一種。因此本層**不接受**任何已被 legacy 壓平的字典；輸入必須在科目層級
就帶著「這個值是怎麼來的」的證據標記。

════════════════════════════════════════════════════════════════════
(b) legacy 三個陷阱，各自由 ``evidence`` 欄位如何表達
════════════════════════════════════════════════════════════════════
1. 缺值預設 0.0（``financial_statements_fetcher._v()`` 查無科目回 0.0；其比對還取
   max|val|，同鍵多筆時以絕對值最大者勝出）
   → 呼叫端必須標 ``legacy_default``：本層一律輸出 ``None`` + 缺口
   ``legacy_default_zero``，**即使 value 是 0.0 也不當真 0**。
2. 單位異常值被靜默重置為 0（同檔約 288–295 行：``rev > 0`` 且 ``abs(營業利益或淨利) > rev × 1.2``
   時 print 後改成 0）
   → 呼叫端必須標 ``legacy_reset``：本層輸出 ``None`` + 缺口 ``legacy_anomaly_reset``，
   **不補 0、不還原臆測值**。
3. ``quarterly_financials_fetcher._first_hit`` 對 ``v != 0`` 才算命中，丟掉真正的 0
   → 若來源明示該科目為 0 而呼叫端據此標 ``source_reported``，本層**原值保留 0.0**；
   若呼叫端只能得到「_first_hit 沒命中」，那是缺值，不得標 ``source_reported``
   （應不提供該觀測，缺口為 ``not_observed``，或標 ``source_absent``）。

════════════════════════════════════════════════════════════════════
(c) 誰負責判斷 evidence
════════════════════════════════════════════════════════════════════
**本層不判斷。** 呼叫端（日後合法的來源 reader）必須握有證據才能標 ``source_reported``。
「有證據的真 0」的判準屬來源層，本層不替它決定；本層只保證：標了 ``source_reported`` 且為有限數
就原值進 pack（含 0.0，``-0.0`` 正規化為 ``0.0``），不會把任何 0 一律改成缺值。
本層**不會**因為 value 是 0 就懷疑它，也**不會**因為 value 是 0 就相信它。

════════════════════════════════════════════════════════════════════
(d) 不處理幣別換算與單位換算
════════════════════════════════════════════════════════════════════
``currency`` 與 ``unit`` 只做「一致性檢查」：觀測若自帶 ``period_end`` / ``unit`` / ``currency``，
必須與所屬期間**完全相同**（逐字比對，大小寫與前後空白皆敏感：``"twd"`` 不等於 ``"TWD"``，
這是刻意偏嚴，寧可 raise 也不靜默正規化），否則整份 raise（混單位、跨期、混幣別在本層不可表示）。
期間的 ``source`` / ``unit`` 原樣透傳，不 strip、不改大小寫。
不換算、不補單位、不由金額大小推斷單位。
**幣別不得丟失**：既有 ``FinancialPeriodInput`` / ``FinancialEvidence`` 沒有幣別欄位，**證據本身不帶幣別**，
因此 ``build_evidence_from_raw`` 回傳 ``AdaptedEvidence(evidence, gaps, currency)``，三者必須成對保存與傳遞。
``evidence`` 與 ``gaps`` 也必須成對傳遞：只拿 period 去呼叫 ``build_financial_evidence``，
pack 裡的 ``None`` 只會顯示 ``missing_input``，看不出是缺值、legacy 假值、衝突還是非有限值。
來源明示的異常值（例：營業利益 2500 / 營收 1000，``source_reported``）**原樣**進 pack，
由 pack 既有的單位異常防線標 unknown；本層不在此判定。

════════════════════════════════════════════════════════════════════
公司類型、口徑、發布日：必須顯式，絕不推定
════════════════════════════════════════════════════════════════════
- ``company_type`` 無預設值，且**不得**由股票代號前綴（例如 28 / 58 開頭）或任何啟發式推斷：
  代號前綴規則會隨市場制度變動，且遇到特例時會把一般公司誤判成金融股（或相反），
  錯誤適用性比「未知」更危險。呼叫端不知道就傳 ``"unknown"``，pack 會輸出 unknown。
- ``basis`` / ``published_at`` 原樣透傳，None 就是 None：不由 ``period_end`` 加天數、不由
  ``fetched_at``、不由法定公告截止日推定；不推定單季或累計。

════════════════════════════════════════════════════════════════════
缺口（``AdapterGap``）與 fail loud
════════════════════════════════════════════════════════════════════
每個沒有取得有效值的科目恰有一筆缺口，依 ``ITEM_NAMES`` 順序，決定性。多筆觀測同科目：
全部結論一致才合併；任一不一致（值不同、或來源回報與缺值 / legacy 混雜）→ ``None`` +
``conflicting_observations``，**不得** max / abs / 平均 / 後者覆蓋前者來消除衝突。
結構性壞輸入一律 raise ``FinancialPeriodAdapterError``（型別錯、空字串、naive 時間、
不在允許集的取值、未知科目、bool / Decimal / str / complex 值、單位 / 幣別 / 期間不符 ……）。
數值型別與 pack 的 ``_normalize_items`` 一致：排除 bool，其餘接受 ``numbers.Real``
（含 numpy 的 int / float 純量，一律轉 float）；``numpy.bool_`` 不是 ``numbers.Real``，同樣拒絕。
通過 ``numbers.Real`` 但無法 ``float()`` 的型別（例：``numpy.timedelta64``，含 NaT）與超大 int 一律
raise ``FinancialPeriodAdapterError``，訊息只含型別名、不回顯值。
**精確值語意**：「是不是 0」「兩筆觀測是否相同」「標記與值是否矛盾」一律以**精確值**
（``fractions.Fraction``：int / numpy 整數 → 精確整數；Fraction → 自身；float / numpy 浮點 →
``as_integer_ratio()``）判定，不看轉成 float 之後的結果，也不用容差。float 只用於最後輸出到
``items``。因此：極小非零的 ``Fraction``（如 ``1/10**400``）若轉 float 下溢為 ``0.0``，**不會**被當成
真 0，而是輸出 ``None`` + 缺口 ``unrepresentable_value``；``2**53`` 與 ``2**53 + 1`` 轉 float 後相同，
但精確值不同，視為 ``conflicting_observations``；``0.1``（float）與 ``Fraction(1, 10)`` 精確值不同，
同樣衝突；``0.5`` 與 ``Fraction(1, 2)``、``0`` / ``-0.0`` / ``Fraction(0)`` 精確值相等，可合併。
無法取得精確值的 ``numbers.Real`` 型別（沒有 ``as_integer_ratio`` 者）一律 fail closed：
raise ``FinancialPeriodAdapterError``。病態自訂型別（``denominator == 0``、``as_integer_ratio()``
回傳非數、``__float__`` 丟 ``RuntimeError`` ……）造成的任何 ``Exception`` 也一律收斂成同一個例外
（不捕捉 ``BaseException``），訊息只含科目名與型別名。
**次正規區**：``source_reported`` 的精確值轉 float 後落在次正規區（絕對值小於最小正規 double）
且被捨入成**不同的**值，與下溢同樣輸出 ``None`` + ``unrepresentable_value``（次正規區相對誤差可達 100%，
故 fail closed）；本身就是 double 的次正規值（如 ``5e-324``、``1e-310``）精確等於其 float，照常輸出。
正常範圍內的 0.5-ulp 捨入（如 ``Fraction(1, 3)``、``2**53 + 1``）屬可接受的有損輸出；
衝突比較仍用精確值，不受影響。
證據種類與值互相矛盾者也 raise：``source_absent`` 要帶「無值」——``None`` 或非有限值，
帶有限值（含 ``0.0``、``-0.0``、``numpy.int64(0)``）整份 raise；``legacy_default`` /
``legacy_reset`` 帶了**有限的非 0** 值（legacy 這兩種情境輸出的只會是 0.0；帶別的值代表標記貼錯）。
這三種標記搭配 NaN / ±inf 時**不 raise**，與 ``None`` 同路徑：值 ``None`` + 該 evidence 對應的缺口。
``source_label`` 會原樣回顯到 ``gap.detail``，呼叫端須維持為來源科目原名（不放敏感或自由文字）。
結果「與觀測順序無關」僅對 ``items``、gap 的 ``item`` 與 ``reason_code`` 成立；
``gap.detail`` 內來源科目原名的排列依觀測出現順序。

════════════════════════════════════════════════════════════════════
(e) 範圍聲明
════════════════════════════════════════════════════════════════════
財報來源權利、時點正確性（PIT）、口徑仍未解除；本層**零 production caller**，
不代表任何財報功能完成。
"""

from __future__ import annotations

import datetime as _dt
import math
import numbers
from collections.abc import Mapping as _AbcMapping
from collections.abc import Sequence as _AbcSequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Literal, Sequence

from src.compute.health.financial_health_evidence import (
    BASIS_VALUES,
    COMPANY_TYPES,
    ITEM_NAMES,
    FinancialEvidence,
    FinancialPeriodInput,
    build_financial_evidence,
)

# ── 常數 ─────────────────────────────────────────────────────────────

EVIDENCE_SOURCE_REPORTED = "source_reported"
EVIDENCE_SOURCE_ABSENT = "source_absent"
EVIDENCE_LEGACY_DEFAULT = "legacy_default"
EVIDENCE_LEGACY_RESET = "legacy_reset"
EVIDENCE_KINDS: tuple[str, ...] = (
    EVIDENCE_SOURCE_REPORTED, EVIDENCE_SOURCE_ABSENT,
    EVIDENCE_LEGACY_DEFAULT, EVIDENCE_LEGACY_RESET,
)

GAP_NOT_OBSERVED = "not_observed"
GAP_SOURCE_ABSENT = "source_absent"
GAP_LEGACY_DEFAULT_ZERO = "legacy_default_zero"
GAP_LEGACY_ANOMALY_RESET = "legacy_anomaly_reset"
GAP_NON_FINITE_VALUE = "non_finite_value"
GAP_CONFLICTING_OBSERVATIONS = "conflicting_observations"
GAP_VALUE_MISSING_FOR_REPORTED = "value_missing_for_reported"
GAP_UNREPRESENTABLE_VALUE = "unrepresentable_value"
GAP_REASON_CODES: tuple[str, ...] = (
    GAP_NOT_OBSERVED, GAP_SOURCE_ABSENT, GAP_LEGACY_DEFAULT_ZERO, GAP_LEGACY_ANOMALY_RESET,
    GAP_NON_FINITE_VALUE, GAP_CONFLICTING_OBSERVATIONS, GAP_VALUE_MISSING_FOR_REPORTED,
    GAP_UNREPRESENTABLE_VALUE,
)

#: 缺口說明模板（固定文字；{item} 為科目名，{labels} 為呼叫端提供的來源科目原名）。
_DETAIL_TEMPLATES: dict[str, str] = {
    GAP_NOT_OBSERVED: "{item}：呼叫端未提供此科目觀測",
    GAP_SOURCE_ABSENT: "{item}：來源明示無此科目（{labels}）",
    GAP_LEGACY_DEFAULT_ZERO: "{item}：legacy 缺值預設 0.0，不是觀測值（{labels}）",
    GAP_LEGACY_ANOMALY_RESET: "{item}：legacy 把單位異常值重置為 0，原值未保留（{labels}）",
    GAP_NON_FINITE_VALUE: "{item}：來源值為 NaN 或 inf（{labels}）",
    GAP_CONFLICTING_OBSERVATIONS: "{item}：多筆觀測互相衝突，未擇一（{labels}）",
    GAP_VALUE_MISSING_FOR_REPORTED: "{item}：標為來源回報但未帶值（{labels}）",
    GAP_UNREPRESENTABLE_VALUE: "{item}：來源值非零，但無法以 float 表示（下溢或超出範圍）（{labels}）",
}

#: 觀測結論 → 缺口原因（reported 且有限數者不在此表，直接是值）。
_EVIDENCE_TO_GAP: dict[str, str] = {
    EVIDENCE_SOURCE_ABSENT: GAP_SOURCE_ABSENT,
    EVIDENCE_LEGACY_DEFAULT: GAP_LEGACY_DEFAULT_ZERO,
    EVIDENCE_LEGACY_RESET: GAP_LEGACY_ANOMALY_RESET,
}


#: 最小正規 double（= ``sys.float_info.min``，測試以 sys 對照；此處不 import sys 以維持白名單）。
_FLOAT_MIN_NORMAL = 2.0 ** -1022


class FinancialPeriodAdapterError(ValueError):
    """轉接層輸入結構性錯誤（§1 Fail Loud）。訊息說明哪個欄位 / 條件違規。"""


# ── 資料結構 ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RawObservation:
    """單一具名科目的來源觀測。

    ``evidence`` 由呼叫端依來源證據標記（本層不判斷）；``source_label`` 為來源科目原名（追溯用）。
    ``period_end`` / ``unit`` / ``currency`` 為可選自帶標記，若提供必須與所屬期間完全一致。
    """

    item: str
    value: float | None
    evidence: Literal["source_reported", "source_absent", "legacy_default", "legacy_reset"]
    source_label: str
    period_end: _dt.date | None = None
    unit: str | None = None
    currency: str | None = None


@dataclass(frozen=True)
class RawFinancialPeriod:
    """單一財報期間的來源原值包。``company_type`` 無預設值，必須顯式（不得推斷）。"""

    period_end: _dt.date
    source: str
    fetched_at: _dt.datetime
    unit: str
    currency: str
    basis: Literal["single_quarter", "cumulative"] | None
    published_at: _dt.date | None
    company_type: Literal["general", "financial", "etf", "unknown"]
    observations: Sequence[RawObservation]


@dataclass(frozen=True)
class AdapterGap:
    """一個沒有取得有效值的科目與原因。``detail`` 為簡短中性說明。"""

    item: str
    reason_code: str
    detail: str

    def __post_init__(self) -> None:
        if self.item not in ITEM_NAMES:
            raise FinancialPeriodAdapterError(f"gap.item 不合法：{self.item!r}")
        if self.reason_code not in GAP_REASON_CODES:
            raise FinancialPeriodAdapterError(f"gap.reason_code 不合法：{self.reason_code!r}")


@dataclass(frozen=True)
class AdaptedEvidence:
    """``build_evidence_from_raw`` 的結果：證據、缺口、幣別三者成對，不可拆開保存。

    證據本身不帶幣別；缺口說明各 ``None`` 為什麼是 ``None``（pack 只會顯示 missing_input）。
    """

    evidence: FinancialEvidence
    gaps: tuple[AdapterGap, ...]
    currency: str


@dataclass(frozen=True)
class AdaptedPeriod:
    """轉接結果：可直接交給既有引擎的期間輸入 + 公司類型 + 幣別 + 缺口。"""

    period: FinancialPeriodInput
    company_type: str
    currency: str
    gaps: tuple[AdapterGap, ...]


# ── 驗證 ─────────────────────────────────────────────────────────────

def _fail(msg: str) -> None:
    raise FinancialPeriodAdapterError(msg)


def _is_plain_date(x: object) -> bool:
    return isinstance(x, _dt.date) and not isinstance(x, _dt.datetime)


def _non_empty_str(x: object) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _fail_exact(item: str, v: object) -> None:
    """訊息只含科目名與型別名，不回顯值。"""
    _fail(f"科目 {item} 值無法取得精確表示（型別 {type(v).__name__}）")


def _to_float(item: str, v: object) -> float:
    """float() 的統一包裝：任何 Exception（含病態自訂型別丟的 RuntimeError 等）→ 適配層例外。

    只捕捉 Exception，不捕捉 BaseException（KeyboardInterrupt 等照常往上傳）。訊息不回顯值。
    """
    try:
        return float(v)  # type: ignore[arg-type]
    except Exception:                                      # noqa: BLE001 — 一律 fail closed
        pass                                               # 在 except 外 raise，避免串接原例外
    _fail(f"科目 {item} 值無法轉為 float（型別 {type(v).__name__}）")
    raise AssertionError("unreachable")                    # _fail 一定 raise


def _exact_unsafe(item: str, v: object) -> Fraction | None:
    """_exact 的本體；可能丟出任何例外，由 ``_exact`` 統一收斂。"""
    if isinstance(v, numbers.Rational):                  # int / Fraction / numpy 整數
        return Fraction(int(v.numerator), int(v.denominator))
    ratio = getattr(v, "as_integer_ratio", None)         # float / numpy 浮點
    if ratio is None:
        _fail_exact(item, v)
    try:
        n, d = ratio()
    except (ValueError, OverflowError):                   # NaN / ±inf 的正常路徑
        try:
            nonfinite = not math.isfinite(float(v))       # type: ignore[arg-type]
        except Exception:                                 # noqa: BLE001
            nonfinite = False
        if nonfinite:
            return None
        _fail_exact(item, v)
    return Fraction(int(n), int(d))


def _exact(item: str, v: object) -> Fraction | None:
    """原值的精確表示。有限值 → Fraction；NaN / ±inf → None（非有限）；無法精確表示 → raise。

    只在 ``numbers.Real`` 且非 bool 的值上呼叫。不經 float，故不受下溢 / 大整數碰撞影響。
    病態型別（``denominator == 0``、``as_integer_ratio()`` 回傳非數、方法本身丟例外 ……）造成的任何
    ``Exception``（ZeroDivisionError / ValueError / TypeError / RuntimeError / OverflowError ……）
    一律收斂成 ``FinancialPeriodAdapterError``；不捕捉 BaseException。NaN / ±inf 回 None 是正常路徑，
    不會變成 raise。
    """
    try:
        return _exact_unsafe(item, v)
    except FinancialPeriodAdapterError:
        raise
    except Exception:                                      # noqa: BLE001 — 一律 fail closed
        raise FinancialPeriodAdapterError(
            f"科目 {item} 值無法取得精確表示（型別 {type(v).__name__}）") from None


def _validate_value(obs: RawObservation) -> None:
    """值型別（與 pack 一致：排除 bool、接受 numbers.Real）與「證據種類 ↔ 值」是否矛盾。

    source_absent / legacy_default / legacy_reset 搭配 NaN 或 ±inf 視同 None，不 raise；
    搭配**精確有限值**：source_absent 任何有限值、legacy_* 的精確非 0 值皆為標記貼錯，raise
    （以精確值判定，極小非零值轉 float 下溢為 0.0 也算非 0）。
    """
    v = obs.value
    if v is None:
        return
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        _fail(f"科目 {obs.item} 值型別不合法：{type(v).__name__}（排除 bool，只收 numbers.Real 或 None）")
    # 例：超大 int（OverflowError）、numpy.timedelta64（通過 numbers.Real 但 float() 丟 TypeError）、
    # 病態自訂型別（任何 Exception）。訊息只含型別名，不回顯值。
    _to_float(obs.item, v)
    exact = _exact(obs.item, v)
    if exact is None:
        return          # 非有限值：reported → non_finite_value 缺口；其他標記 → 與 None 同路徑
    if obs.evidence == EVIDENCE_SOURCE_ABSENT:
        _fail(f"科目 {obs.item} 標為 source_absent 卻帶了值（證據自相矛盾）")
    if obs.evidence in (EVIDENCE_LEGACY_DEFAULT, EVIDENCE_LEGACY_RESET) and exact != 0:
        _fail(f"科目 {obs.item} 標為 {obs.evidence} 卻帶了非 0 值（legacy 只會輸出 0.0；標記貼錯）")


def _check_observation_consistency(raw: RawFinancialPeriod, obs: RawObservation) -> None:
    """觀測自帶的期間 / 單位 / 幣別若提供，必須與所屬期間完全一致（混單位、跨期不可表示）。"""
    if obs.period_end is not None:
        if not _is_plain_date(obs.period_end):
            _fail(f"科目 {obs.item} 的 period_end 必須是 date 或 None")
        if obs.period_end != raw.period_end:
            _fail(f"科目 {obs.item} 的 period_end {obs.period_end} 與期間 {raw.period_end} 不符（跨期）")
    if obs.unit is not None and obs.unit != raw.unit:
        _fail(f"科目 {obs.item} 的 unit {obs.unit!r} 與期間 {raw.unit!r} 不符（混單位）")
    if obs.currency is not None and obs.currency != raw.currency:
        _fail(f"科目 {obs.item} 的 currency {obs.currency!r} 與期間 {raw.currency!r} 不符（混幣別）")


def _validate_observation(obs: object) -> None:
    if not isinstance(obs, RawObservation):
        _fail(f"observations 的元素必須是 RawObservation，收到 {type(obs).__name__}")
    if not isinstance(obs.item, str) or obs.item not in ITEM_NAMES:
        _fail(f"科目名不在 ITEM_NAMES：{obs.item!r}（允許 {list(ITEM_NAMES)}）")
    if not isinstance(obs.evidence, str) or obs.evidence not in EVIDENCE_KINDS:
        _fail(f"科目 {obs.item} 的 evidence 不合法：{obs.evidence!r}（允許 {EVIDENCE_KINDS}）")
    if not _non_empty_str(obs.source_label):
        _fail(f"科目 {obs.item} 的 source_label 必須是非空字串")
    for fname in ("unit", "currency"):
        fv = getattr(obs, fname)
        if fv is not None and not isinstance(fv, str):
            _fail(f"科目 {obs.item} 的 {fname} 必須是字串或 None")
    _validate_value(obs)


def _validate_raw(raw: object) -> None:
    if not isinstance(raw, RawFinancialPeriod):
        _fail(f"raw 必須是 RawFinancialPeriod，收到 {type(raw).__name__}")
    if not _is_plain_date(raw.period_end):
        _fail("period_end 必須是 datetime.date（不接受 datetime）")
    for fname in ("source", "unit", "currency"):
        if not _non_empty_str(getattr(raw, fname)):
            _fail(f"{fname} 必須是非空字串")
    if (not isinstance(raw.fetched_at, _dt.datetime) or raw.fetched_at.tzinfo is None
            or raw.fetched_at.utcoffset() is None):
        _fail("fetched_at 必須是 tz-aware datetime")
    if raw.basis is not None and (not isinstance(raw.basis, str) or raw.basis not in BASIS_VALUES):
        _fail(f"basis 不合法：{raw.basis!r}（允許 {BASIS_VALUES} 或 None）")
    if raw.published_at is not None:
        if not _is_plain_date(raw.published_at):
            _fail("published_at 必須是 date 或 None（不接受 datetime）")
        if raw.published_at < raw.period_end:
            _fail(f"published_at {raw.published_at} 早於 period_end {raw.period_end}（不可能）")
    if not isinstance(raw.company_type, str) or raw.company_type not in COMPANY_TYPES:
        _fail(f"company_type 不合法：{raw.company_type!r}（允許 {COMPANY_TYPES}；必須顯式，不推斷）")
    obs_seq = raw.observations
    if (isinstance(obs_seq, (str, bytes, _AbcMapping)) or not isinstance(obs_seq, _AbcSequence)):
        _fail("observations 必須是序列（list / tuple）")
    for obs in obs_seq:
        _validate_observation(obs)
        _check_observation_consistency(raw, obs)


# ── 單科目解析 ───────────────────────────────────────────────────────

def _outcome(obs: RawObservation) -> tuple[str | None, float | None, Fraction | None]:
    """單筆觀測 → (缺口原因 | None, 輸出值 | None, 精確值 | None)。

    輸出值只在「有證據、精確值為有限且可表示」時非 None。精確值只用於比較（真 0 判定與衝突偵測），
    不輸出。本層不替呼叫端判斷 evidence；這裡只是把四種證據種類逐一對映成結論。
    """
    if obs.evidence == EVIDENCE_SOURCE_REPORTED:
        if obs.value is None:
            return GAP_VALUE_MISSING_FOR_REPORTED, None, None
        exact = _exact(obs.item, obs.value)
        if exact is None:
            return GAP_NON_FINITE_VALUE, None, None
        if exact == 0:
            return None, 0.0, exact                      # 精確值為 0：真 0（-0.0 一律正規化為 0.0）
        val = _to_float(obs.item, obs.value)
        if not math.isfinite(val) or not abs(val) > 0.0:
            return GAP_UNREPRESENTABLE_VALUE, None, exact  # 非零卻下溢 / 溢位：不得當真 0
        if abs(val) < _FLOAT_MIN_NORMAL and exact != Fraction(val):
            return GAP_UNREPRESENTABLE_VALUE, None, exact  # 次正規區被捨入成不同的值：fail closed
        return None, val, exact
    # source_absent / legacy_default / legacy_reset：值一律不採（驗證階段已確保不矛盾）
    return _EVIDENCE_TO_GAP[obs.evidence], None, None


def _merge_outcomes(outcomes: Sequence[tuple[str | None, float | None, Fraction | None]]
                    ) -> tuple[str | None, float | None]:
    """多筆結論全部一致才合併；任一不一致 → 衝突缺口。不取 max / abs / 平均 / 後者覆蓋。

    「一致」以（缺口原因、精確值）判定：精確值逐位相同才算相同，任何差異（含 1e-9、
    float 碰撞的大整數）都屬衝突，不容差、不看轉 float 後是否相等。
    """
    first = outcomes[0]
    if all(o[0] == first[0] and o[2] == first[2] for o in outcomes[1:]):
        return first[0], first[1]
    return GAP_CONFLICTING_OBSERVATIONS, None


def _labels(obs_list: Sequence[RawObservation]) -> str:
    seen: list[str] = []
    for o in obs_list:
        if o.source_label not in seen:
            seen.append(o.source_label)
    return "、".join(seen)


def _resolve_item(name: str, obs_list: Sequence[RawObservation]
                  ) -> tuple[float | None, AdapterGap | None]:
    if not obs_list:
        reason: str | None = GAP_NOT_OBSERVED
        value: float | None = None
    else:
        reason, value = _merge_outcomes([_outcome(o) for o in obs_list])
    if reason is None:
        return value, None
    detail = _DETAIL_TEMPLATES[reason].format(item=name, labels=_labels(obs_list))
    return None, AdapterGap(item=name, reason_code=reason, detail=detail)


# ── 主函式 ───────────────────────────────────────────────────────────

def _to_period_input(raw: RawFinancialPeriod, items: dict[str, float | None]) -> FinancialPeriodInput:
    """欄位原樣透傳（basis / published_at 不推定）；items 轉唯讀。"""
    return FinancialPeriodInput(
        period_end=raw.period_end,
        source=raw.source,
        fetched_at=raw.fetched_at,
        unit=raw.unit,
        basis=raw.basis,
        published_at=raw.published_at,
        items=MappingProxyType(dict(items)),
    )


def adapt_financial_period(raw: RawFinancialPeriod) -> AdaptedPeriod:
    """來源原值 → ``AdaptedPeriod``。純函式、不改輸入、不讀時鐘。

    Raises:
        FinancialPeriodAdapterError: 輸入結構性錯誤（見模組 docstring）。
    """
    _validate_raw(raw)
    by_item: dict[str, list[RawObservation]] = {n: [] for n in ITEM_NAMES}
    for obs in raw.observations:
        by_item[obs.item].append(obs)
    items: dict[str, float | None] = {}
    gaps: list[AdapterGap] = []
    for name in ITEM_NAMES:
        value, gap = _resolve_item(name, by_item[name])
        items[name] = value
        if gap is not None:
            gaps.append(gap)
    return AdaptedPeriod(
        period=_to_period_input(raw, items),
        company_type=raw.company_type,
        currency=raw.currency,
        gaps=tuple(gaps),
    )


def build_evidence_from_raw(raw: RawFinancialPeriod) -> AdaptedEvidence:
    """``adapt_financial_period`` 後交給既有 ``build_financial_evidence``。

    回傳 ``AdaptedEvidence(evidence, gaps, currency)``：證據內容原樣不改；證據本身不帶幣別，
    幣別必須與證據成對保存；evidence 與 gaps 必須成對傳遞。
    """
    adapted = adapt_financial_period(raw)
    evidence = build_financial_evidence(adapted.period, company_type=adapted.company_type)
    return AdaptedEvidence(evidence=evidence, gaps=adapted.gaps, currency=adapted.currency)
