"""src/services/sector_flow_fact_service.py — 板塊事實(唯讀 L3;Issue #1140 §B／G-3／G-10).

回答一個問題:**「資料日(最新交易日)各板塊三大法人合計淨額是多少(億元)」**,只輸出事實。

口徑(G-10;常數 `SECTOR_FLOW_BASIS`)
    三大法人合計 = 外資 + 投信 + 自營商;依個股「張數 × 1000 股 × 收盤價」彙總至板塊,單位億元;
    視窗 = 最新交易日(**不是** bubble 的近 5 交易日累計 `x_yi`)。
    ⛔ 這**不是**「僅外資」(`外資淨買賣超(僅外資)` 另有口徑,本檔不碰、不重用)。

資料流(L1 → L2 → 本層;純讀,不 fetch、不寫檔、不快取、不新增來源)
    L1 `reader.read_sector_flow_cache(strict=True)` ── 板塊集合(N)／觀測日／is_stale／tpex_complete／n_absent_cells
    L1 `reader.read_sector_daily_net_latest()`      ── daily_net.parquet 最新日原始列
    L1 `reader.read_sector_flow_cron_coverage()`    ── metadata.coverage 診斷計數(上一次 cron 所抓天數)
    L2 `canonicalize_sector_daily`                  ── 原始標籤 → 標準板塊(ETF 家族等別名合併;重複列 raise)
    ⛔ 不呼叫 `get_sector_flow_view`(它帶 quadrant／y_yi／size_yi／highlight／持股);⛔ 不碰
       holdings_service／gsheet;⛔ 不 import streamlit／UI。

§1 Fail Loud:缺值 ≠ 0。最新日「無列」的板塊 = 未觀測(sign="unobserved"),**絕不**補 0、**不**計入合計與
    正/負/持平;NaN/inf → 整份 UNAVAILABLE(不 fillna)。重複列 → 不靜默相加。對帳不過 → UNAVAILABLE。
G-3 方案 A 衍生聚合(`derived`;`is_derived=True`,與 `rows` 分離標示):資料日、涵蓋板塊數、合計淨額、
    淨額為正／負／持平板塊數。**只對「完整且通過對帳」的資料計算**;partial/unknown → `derived=None`(rows 照給)。
    ⛔ 不做依淨額排序的 Top/Bottom／排名(rows 固定依板塊名排序,不隱含 Top-N);⛔ 沒有任何「全市場」欄位。
⚠️ 完整性 ≠ 覆蓋度(F1,契約):`completeness='complete'` **只代表來源旗標完整**
    (最新日 twse_ok／tpex_ok／industry_ok 皆 True 且視窗 `tpex_complete is True`),
    **不代表板塊全覆蓋**。覆蓋度以 `coverage.n_observed`／`n_universe`／`n_unobserved`
    (`derived` 亦同帶 `n_observed`)為準 —— 最新日只有 1/N 板塊有列時仍可能是 complete。本層不設最低覆蓋率門檻。
⚠️ `derived` 自帶 `as_of`／`is_stale`(轉述 fact),消費端單拿 derived 也不會漏看資料日與過期。
⚠️ `coverage.n_excluded_foreign_ccy`／`n_unclassified_stock_days`／`cron_coverage_n_days` 來自
    metadata.coverage = **上一次 cron 抓取天數**的診斷計數,**非綁定 data_date**,也不是整個視窗。
⚠️ 對帳備註(M7):步驟 9「原始合計 vs 標準化後合計」與後段「Σrows vs 原始合計」在 universe 檢查通過後
    數學上等價(rows 的觀測列即標準化列);步驟 9 保留為冗餘縱深防禦(可在建 rows 前就擋下 L2 輸出異常,
    並附帶檢查標準化列非空、有限),**不是**獨立的第二個對帳來源。
本層**不產出任何使用者可見文案**:只回 reason／caveat 碼與數值(文案屬後續 UI Gate)。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from shared.sector_flow_fact_thresholds import (
    SECTOR_NET_FLAT_EPS_YI,
    SECTOR_NET_RECONCILE_ABS_TOL_YI,
    SECTOR_NET_RECONCILE_REL_TOL,
)
from shared.ui2_contract.models import FieldState
from src.compute.sector_flow import canonicalize_sector_daily
from src.data.sector_flow import reader as _reader

# ── 描述性常數(非使用者文案)────────────────────────────────────────────
SOURCE: str = "data_cache/sector_flow:bubble_latest.json+metadata.json+daily_net.parquet"


@dataclass(frozen=True)
class SectorFlowBasis:
    """口徑(G-10)。純描述性常數,不含使用者文案。"""

    institutions: tuple = ("foreign", "trust", "dealer")   # 三大法人合計 = 外資 + 投信 + 自營商
    aggregation: str = "lots_x_1000_shares_x_close_to_sector"
    window: str = "latest_trading_day"
    unit: str = "yi_twd"                                    # 億元


SECTOR_FLOW_BASIS = SectorFlowBasis()

# sign(中性詞;⛔ 不用流入/流出)
SIGN_POSITIVE, SIGN_NEGATIVE, SIGN_FLAT, SIGN_UNOBSERVED = "positive", "negative", "flat", "unobserved"
_SIGNS = frozenset({SIGN_POSITIVE, SIGN_NEGATIVE, SIGN_FLAT, SIGN_UNOBSERVED})

COMPLETE, PARTIAL, UNKNOWN = "complete", "partial", "unknown"
_COMPLETENESS = frozenset({COMPLETE, PARTIAL, UNKNOWN})

# caveat 碼(⛔ 碼內不得出現全市場語意;`scope_*` 揭露合計含 ETF/ETN 等標籤)
CAVEAT_SCOPE_INCLUDES_NON_COMMON_LABELS = "scope_includes_etf_etn_and_receipt_labels"
CAVEAT_TPEX_WINDOW_INCOMPLETE = "tpex_window_incomplete"
CAVEAT_TPEX_WINDOW_FLAG_MISSING = "tpex_window_flag_missing"
CAVEAT_DAY_FLAG_NOT_TRUE = "data_date_flag_not_true"
CAVEAT_FLAG_COLUMNS_ABSENT = "flag_columns_absent"
#: 來源 = metadata.coverage = 上一次 cron 抓取天數的診斷計數,**非綁定 data_date**(碼名即敘述範圍)。
CAVEAT_FOREIGN_CCY_EXCLUDED = "foreign_ccy_etf_excluded_last_cron_run_scope"
CAVEAT_SECTORS_UNOBSERVED = "sectors_unobserved_on_data_date"
CAVEAT_ABSENT_CELLS = "absent_cells_in_window"
CAVEAT_UNCLASSIFIED_STOCK_DAYS = "unclassified_stock_days_present_last_cron_run_scope"
CAVEAT_N_STOCKS_INVALID = "n_stocks_invalid"   # 原始 n_stocks 非整數 / 負 / 非有限 / bool → 該板塊 n_stocks=None
CAVEAT_CRON_COVERAGE_UNAVAILABLE = "cron_coverage_unavailable"

#: reason → state 的**唯一**對映(集中單一 dict;`SectorFlowFact.__post_init__` 強制一致,測試窮舉)。
REASON_STATE: dict = {
    "ok": FieldState.OK,
    "stale": FieldState.STALE,
    "bubble_not_produced": FieldState.MISSING,
    "daily_net_unreadable": FieldState.MISSING,        # 缺檔 / 空檔 / 缺必要欄
    "observation_date_unknown": FieldState.MISSING,
    "date_disagreement": FieldState.MISSING,
    "reader_exception": FieldState.UNAVAILABLE,
    "daily_net_corrupt": FieldState.UNAVAILABLE,       # 壞檔 ≠ 缺檔
    "compute_exception": FieldState.UNAVAILABLE,
    "integrity_duplicate_rows": FieldState.UNAVAILABLE,
    "integrity_nonfinite": FieldState.UNAVAILABLE,
    "integrity_component_mismatch": FieldState.UNAVAILABLE,
    "integrity_reconcile": FieldState.UNAVAILABLE,
    "integrity_universe_mismatch": FieldState.UNAVAILABLE,
    "integrity_count_identity": FieldState.UNAVAILABLE,
}
_VALUE_STATES = frozenset({FieldState.OK, FieldState.STALE})
_AMT_COLS = ("net_amt_yi", "foreign_yi", "trust_yi", "dealer_yi")
_FLAG_COLS = ("twse_ok", "tpex_ok", "industry_ok")


# ── 契約 ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SectorNetRow:
    """一個標準板塊在資料日的淨額事實。`net_yi=None` ⇔ sign="unobserved"(最新日無列;**不是** 0)。"""

    sector: str
    net_yi: float | None
    n_stocks: int | None
    members: tuple
    sign: str
    is_derived: bool = False

    def __post_init__(self):
        if self.sign not in _SIGNS:
            raise ValueError(f"SectorNetRow.sign 非法: {self.sign!r}")
        if (self.net_yi is None) != (self.sign == SIGN_UNOBSERVED):
            raise ValueError("SectorNetRow: net_yi=None 必須且僅當 sign='unobserved'")
        if self.net_yi is not None and not math.isfinite(self.net_yi):
            raise ValueError("SectorNetRow.net_yi 必須有限")
        if self.is_derived is not False:
            raise ValueError("SectorNetRow 是原始列,is_derived 必須為 False")


@dataclass(frozen=True)
class SectorFlowCoverage:
    n_universe: int
    n_observed: int
    n_unobserved: int
    unobserved_sectors: tuple
    tpex_complete_window: bool | None
    tpex_ok_on_data_date: bool | None
    n_absent_cells_window: int | None
    n_excluded_foreign_ccy: int | None      # 來自 metadata.coverage(上一次 cron 抓取天數的診斷計數;非綁定 data_date、非整個視窗)
    n_unclassified_stock_days: int | None   # 同上
    cron_coverage_n_days: int | None = None  # metadata.coverage.n_days(上述兩計數涵蓋的天數;缺 → None,供稽核)


@dataclass(frozen=True)
class SectorFlowDerived:
    """G-3 方案 A 衍生聚合。⚠️ 是本系統對各板塊淨額再做的聚合,**不是來源直接提供的數字**。"""

    is_derived: bool
    total_net_yi: float
    n_positive: int
    n_negative: int
    n_flat: int
    n_unobserved: int
    n_universe: int
    reconciled: bool
    raw_total_yi: float
    n_observed: int = 0                     # 恆等式:n_observed == 正+負+持平;n_observed + n_unobserved == n_universe
    as_of: str = ""                         # 資料日 YYYY-MM-DD(轉述 fact.data_date,消費端單拿 derived 不致漏看)
    is_stale: bool = False                  # 轉述 fact.is_stale

    def __post_init__(self):
        if self.is_derived is not True:
            raise ValueError("SectorFlowDerived.is_derived 必須為 True")
        if not (isinstance(self.as_of, str) and self.as_of):
            raise ValueError("SectorFlowDerived.as_of 必須為非空資料日字串")
        if not isinstance(self.is_stale, bool):
            raise ValueError("SectorFlowDerived.is_stale 必須為 bool")
        if (self.n_positive + self.n_negative + self.n_flat != self.n_observed
                or self.n_observed + self.n_unobserved != self.n_universe):
            raise ValueError("SectorFlowDerived 計數恆等式不成立")


@dataclass(frozen=True)
class SectorFlowFact:
    """板塊事實。`completeness='complete'` 只代表**來源旗標完整**,**不代表板塊全覆蓋**;
    覆蓋度以 `coverage.n_observed`／`n_universe`／`n_unobserved` 為準(F1)。"""

    state: FieldState
    reason: str
    data_date: str | None                   # YYYY-MM-DD(可信觀測日)
    is_stale: bool
    stale_reason: str | None                # reader 的診斷文字(非 UI 文案)
    source: str
    basis: SectorFlowBasis
    completeness: str
    caveats: tuple
    coverage: SectorFlowCoverage | None
    rows: tuple
    derived: SectorFlowDerived | None
    diagnostic: str | None = None           # 技術診斷(例外型別等);⛔ 非使用者文案

    def __post_init__(self):
        if REASON_STATE.get(self.reason) is not self.state:
            raise ValueError(f"reason={self.reason!r} 與 state={self.state!r} 不一致(見 REASON_STATE)")
        if self.completeness not in _COMPLETENESS:
            raise ValueError(f"completeness 非法: {self.completeness!r}")
        if self.state not in _VALUE_STATES:
            if self.rows or self.derived is not None or self.coverage is not None:
                raise ValueError("非 OK/STALE 態不得帶 rows / derived / coverage(缺值 ≠ 0)")
        if self.derived is not None and self.completeness != COMPLETE:
            raise ValueError("partial/unknown 不得給 derived(合計與計數)")


# ── 內部 ───────────────────────────────────────────────────────────────
def _fail(reason: str, *, data_date: str | None = None, is_stale: bool = False,
          stale_reason: str | None = None, diagnostic: str | None = None) -> SectorFlowFact:
    return SectorFlowFact(
        state=REASON_STATE[reason], reason=reason, data_date=data_date, is_stale=is_stale,
        stale_reason=stale_reason, source=SOURCE, basis=SECTOR_FLOW_BASIS, completeness=UNKNOWN,
        caveats=(), coverage=None, rows=(), derived=None, diagnostic=diagnostic)


def _as_count(v) -> int | None:
    """JSON/metadata 計數 → int;bool / 負數 / 非整數 / 缺 → None(不當 0)。"""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, np.integer)):
        return int(v) if v >= 0 else None
    if isinstance(v, float) and math.isfinite(v) and v >= 0 and float(v).is_integer():
        return int(v)
    return None


def _is_true(v) -> bool:
    return isinstance(v, (bool, np.bool_)) and bool(v)


def _is_false(v) -> bool:
    return isinstance(v, (bool, np.bool_)) and not bool(v)


def _sign_of(net: float | None) -> str:
    """正/負/持平(具名常數 ε;⛔ 不用 `== 0`,-0.0 與 ±ε 內皆持平;None → 未觀測)。"""
    if net is None:
        return SIGN_UNOBSERVED
    if abs(net) <= SECTOR_NET_FLAT_EPS_YI:
        return SIGN_FLAT
    return SIGN_POSITIVE if net > 0 else SIGN_NEGATIVE


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=SECTOR_NET_RECONCILE_REL_TOL,
                        abs_tol=SECTOR_NET_RECONCILE_ABS_TOL_YI)


def _parse_universe(view: dict) -> list:
    """bubble.sectors → [(標準板塊名, members tuple)];形狀不符 → raise(由呼叫端歸 reader_exception)。"""
    out = []
    for i, s in enumerate(view["sectors"]):
        if not isinstance(s, dict):
            raise ValueError(f"bubble.sectors[{i}] 不是 dict")
        name = s.get("sector")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"bubble.sectors[{i}].sector 缺或非字串")
        mem = s.get("members")
        members = (tuple(sorted(str(m) for m in mem)) if isinstance(mem, (list, tuple)) else ())
        out.append((name.strip(), members))
    return out


def _sum_n_stocks(raw: pd.DataFrame, raw_to_canon: dict) -> tuple:
    """原始 n_stocks → ({標準板塊: 成員加總 int | 不在表內=None}, 是否出現「無效」值)。

    缺(NA / 無此欄)→ 該板塊 None(不 caveat);無效(非整數浮點如 3.7、負數、非有限、bool、不可解析)→ None 並回報 invalid。
    """
    if "n_stocks" not in raw.columns:
        return {}, False
    totals: dict = {}
    bad: set = set()
    invalid_seen = False
    for lab, v in zip(raw["sector"], raw["n_stocks"]):
        name = raw_to_canon.get(str(lab).strip())
        if name is None:
            continue
        if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
            bad.add(name)                                      # 缺:該板塊 None,不當 0
            continue
        n = _as_count(v)
        if n is None:
            bad.add(name)
            invalid_seen = True
            continue
        totals[name] = totals.get(name, 0) + n
    return {k: (None if k in bad else v) for k, v in totals.items() if k not in bad}, invalid_seen


def _flag_evidence(raw: pd.DataFrame) -> tuple:
    """最新日旗標 → (any_non_true, columns_absent, tpex_ok_on_data_date)。NA / 缺 ≠ True。"""
    present = [c for c in _FLAG_COLS if c in raw.columns]
    absent = len(present) < len(_FLAG_COLS)
    non_true = any(not _is_true(v) for c in present for v in raw[c])
    tpex_ok = None
    if "tpex_ok" in raw.columns:
        vals = list(raw["tpex_ok"])
        if vals and all(_is_true(v) for v in vals):
            tpex_ok = True
        elif any(_is_false(v) for v in vals):
            tpex_ok = False
    return non_true, absent, tpex_ok


# ── 主入口 ─────────────────────────────────────────────────────────────
def get_sector_flow_fact(*, today: date | None = None) -> SectorFlowFact:
    """唯讀組出「最新交易日各板塊三大法人合計淨額」事實。判定順序見模組 docstring／`REASON_STATE`。

    不對 caller 拋例外:任何未預期錯誤 ⇒ UNAVAILABLE `compute_exception`(§1:明示不可用,不假裝有資料)。

    Args:
        today: 新鮮度基準日(台北日期;測試注入;None → reader 的台北今日)。
    """
    try:
        return _compute(today)
    except Exception as e:  # noqa: BLE001
        return _fail("compute_exception", diagnostic=f"{type(e).__name__}: {e}")


def _compute(today: date | None) -> SectorFlowFact:
    # 1 strict reader:壞 bubble 檔 ≠ 尚未產生
    try:
        view = _reader.read_sector_flow_cache(strict=True, today=today)
        universe_rows = _parse_universe(view) if view.get("ok") is True else []
    except Exception as e:  # noqa: BLE001 — 轉成 UNAVAILABLE 事實,不炸 caller
        return _fail("reader_exception", diagnostic=f"{type(e).__name__}: {e}")
    # 2
    if view.get("ok") is not True:
        return _fail("bubble_not_produced")
    is_stale = bool(view.get("is_stale"))
    stale_reason = view.get("stale_reason")

    # 3 daily_net:缺檔/空檔/缺欄 → MISSING;壞檔 → UNAVAILABLE
    try:
        daily = _reader.read_sector_daily_net_latest()
    except Exception as e:  # noqa: BLE001
        return _fail("reader_exception", diagnostic=f"{type(e).__name__}: {e}")
    _st = daily.get("status")
    if _st == "corrupt":
        return _fail("daily_net_corrupt", is_stale=is_stale, stale_reason=stale_reason,
                     diagnostic=daily.get("reason"))
    if _st != "ok":
        return _fail("daily_net_unreadable", is_stale=is_stale, stale_reason=stale_reason,
                     diagnostic=f"{_st}: {daily.get('reason')}")

    # 4 觀測日未知(含:缺 / 無法解析 / 晚於今日 / 與 updated_at 矛盾 — reader 已一律回 None)
    obs_raw = view.get("observation_date")
    obs = None
    if isinstance(obs_raw, str):
        try:
            obs = date.fromisoformat(obs_raw)
        except ValueError:
            obs = None
    if obs is None:
        return _fail("observation_date_unknown", is_stale=True, stale_reason=stale_reason)
    obs_iso = obs.isoformat()
    # 5 daily_net 最大日必須等於 bubble 觀測日(否則兩份快取不同步,不擇一硬用)
    if daily["data_date"] != obs:
        return _fail("date_disagreement", is_stale=is_stale, stale_reason=stale_reason,
                     diagnostic=f"daily_net={daily['data_date'].isoformat()} observation_date={obs_iso}")

    raw: pd.DataFrame = daily["rows"]
    # 6 (date, 原始 sector) 重複 → 重用 L2 canonicalize 的 raise(不靜默相加、不 drop_duplicates)
    try:
        # n_stocks 由本層自行加總(見 _sum_n_stocks):不交給 L2 的 `int(round())`(會把 3.7 靜默四捨五入、inf 直接炸)
        canon, canon_meta = canonicalize_sector_daily(raw.drop(columns=["n_stocks"], errors="ignore"))
    except ValueError as e:
        return _fail("integrity_duplicate_rows", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason, diagnostic=str(e))
    except Exception as e:  # noqa: BLE001
        return _fail("compute_exception", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason, diagnostic=f"{type(e).__name__}: {e}")

    # 7 最新日任一金額欄非有限(NaN / inf / 不可解析)→ 整份不可用(⛔ 不 fillna、不當 0)
    amt = raw[list(_AMT_COLS)].apply(pd.to_numeric, errors="coerce").astype("float64")
    if not np.isfinite(amt.to_numpy()).all():
        return _fail("integrity_nonfinite", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason)
    # 8 逐列口徑恆等式:net == foreign + trust + dealer
    comp = amt["foreign_yi"] + amt["trust_yi"] + amt["dealer_yi"]
    if not np.isclose(amt["net_amt_yi"].to_numpy(), comp.to_numpy(),
                      rtol=SECTOR_NET_RECONCILE_REL_TOL, atol=SECTOR_NET_RECONCILE_ABS_TOL_YI).all():
        return _fail("integrity_component_mismatch", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason)
    # 9 對帳:原始合計 == 標準化後合計(標準化只重新分組,不得改變總額)
    raw_total = math.fsum(amt["net_amt_yi"].tolist())
    canon_net = pd.to_numeric(canon["net_amt_yi"], errors="coerce").astype("float64")
    if len(canon) == 0 or not np.isfinite(canon_net.to_numpy()).all() \
            or not _isclose(raw_total, math.fsum(canon_net.tolist())):
        return _fail("integrity_reconcile", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason)
    # 10 最新日的標準板塊必須都在 bubble 板塊集合內(集合本身不得重複)
    universe_names = [n for n, _m in universe_rows]
    universe_set = set(universe_names)
    canon_names = [str(s) for s in canon["sector"]]
    if (len(universe_set) != len(universe_names) or not universe_set
            or any(n not in universe_set for n in canon_names)
            or len(set(canon_names)) != len(canon_names)):
        return _fail("integrity_universe_mismatch", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason)

    # ── rows:固定依板塊名排序(⛔ 不依金額;不隱含 Top-N/排名)──────────────
    # n_stocks:不信任 L2 的 `int(round())`(3.7 會被靜默四捨五入)—— 由原始列自行加總,
    # 任一成員缺 / 無效(非整數、負、非有限、bool)→ 該板塊 n_stocks=None;無效(非「缺」)另加 caveat。
    raw_to_canon = {lab: canon_name for canon_name, labs in canon_meta.get("members", {}).items()
                    for lab in labs}
    n_stocks_by, n_stocks_invalid = _sum_n_stocks(raw, raw_to_canon)
    canon_by = {}
    for i, name in enumerate(canon_names):
        canon_by[name] = (float(canon_net.iloc[i]), n_stocks_by.get(name))
    members_by = dict(universe_rows)
    rows = []
    for name in sorted(universe_set):
        obs_row = canon_by.get(name)
        net = obs_row[0] if obs_row is not None else None
        members = members_by.get(name) or tuple(canon_meta.get("members", {}).get(name, ()))
        rows.append(SectorNetRow(sector=name, net_yi=net,
                                 n_stocks=(obs_row[1] if obs_row is not None else None),
                                 members=tuple(members), sign=_sign_of(net)))
    rows = tuple(rows)

    n_universe = len(universe_set)
    n_pos = sum(1 for r in rows if r.sign == SIGN_POSITIVE)
    n_neg = sum(1 for r in rows if r.sign == SIGN_NEGATIVE)
    n_flat = sum(1 for r in rows if r.sign == SIGN_FLAT)
    n_unobs = sum(1 for r in rows if r.sign == SIGN_UNOBSERVED)
    n_obs = n_universe - n_unobs
    total = math.fsum(r.net_yi for r in rows if r.net_yi is not None)
    # 計數恆等式 + 對帳 (3):正+負+持平+未觀測 == N;觀測數 == 標準化列數;Σ列 == 原始合計
    if (n_pos + n_neg + n_flat + n_unobs != n_universe or len(rows) != n_universe
            or n_obs != len(canon_names)):
        return _fail("integrity_count_identity", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason)
    if not _isclose(total, raw_total):
        return _fail("integrity_reconcile", data_date=obs_iso, is_stale=is_stale,
                     stale_reason=stale_reason)

    # ── 完整性(derived 的閘門)────────────────────────────────────────
    tpex_window = view.get("tpex_complete")
    day_non_true, flags_absent, tpex_day = _flag_evidence(raw)
    n_absent_cells = _as_count(view.get("n_absent_cells"))
    cron_cov = _reader.read_sector_flow_cron_coverage()
    n_excl = _as_count((cron_cov or {}).get("n_excluded_foreign_ccy_stock_days"))
    n_uncls = _as_count((cron_cov or {}).get("n_unclassified_stock_days"))

    caveats = []
    if n_stocks_invalid:
        caveats.append(CAVEAT_N_STOCKS_INVALID)
    if tpex_window is False:
        caveats.append(CAVEAT_TPEX_WINDOW_INCOMPLETE)
    elif tpex_window is not True:
        caveats.append(CAVEAT_TPEX_WINDOW_FLAG_MISSING)
    if day_non_true:
        caveats.append(CAVEAT_DAY_FLAG_NOT_TRUE)
    if flags_absent:
        caveats.append(CAVEAT_FLAG_COLUMNS_ABSENT)
    # 非完整性條件:永遠只揭露、不阻擋(n_absent_cells 健康資料下也 > 0)
    if n_excl:
        caveats.append(CAVEAT_FOREIGN_CCY_EXCLUDED)
    if n_unobs > 0:
        caveats.append(CAVEAT_SECTORS_UNOBSERVED)
    if n_absent_cells:
        caveats.append(CAVEAT_ABSENT_CELLS)
    if n_uncls:
        caveats.append(CAVEAT_UNCLASSIFIED_STOCK_DAYS)
    if cron_cov is None:
        caveats.append(CAVEAT_CRON_COVERAGE_UNAVAILABLE)
    caveats.append(CAVEAT_SCOPE_INCLUDES_NON_COMMON_LABELS)

    # partial:有旗標值非 True(含 NA)或視窗 tpex_complete is not True(含 None);
    # unknown:旗標欄缺。兩者一律不給 derived(rows 照給)。
    if day_non_true or tpex_window is not True:
        completeness = PARTIAL
    elif flags_absent:
        completeness = UNKNOWN
    else:
        completeness = COMPLETE

    coverage = SectorFlowCoverage(
        n_universe=n_universe, n_observed=n_obs, n_unobserved=n_unobs,
        unobserved_sectors=tuple(r.sector for r in rows if r.sign == SIGN_UNOBSERVED),
        tpex_complete_window=tpex_window if isinstance(tpex_window, bool) else None,
        tpex_ok_on_data_date=tpex_day, n_absent_cells_window=n_absent_cells,
        n_excluded_foreign_ccy=n_excl, n_unclassified_stock_days=n_uncls,
        cron_coverage_n_days=_as_count((cron_cov or {}).get("n_days")))
    derived = None
    if completeness == COMPLETE:
        derived = SectorFlowDerived(
            is_derived=True, total_net_yi=total, n_positive=n_pos, n_negative=n_neg, n_flat=n_flat,
            n_unobserved=n_unobs, n_universe=n_universe, reconciled=True, raw_total_yi=raw_total,
            n_observed=n_obs, as_of=obs_iso, is_stale=is_stale)

    reason = "stale" if is_stale else "ok"
    return SectorFlowFact(
        state=REASON_STATE[reason], reason=reason, data_date=obs_iso, is_stale=is_stale,
        stale_reason=stale_reason, source=SOURCE, basis=SECTOR_FLOW_BASIS, completeness=completeness,
        caveats=tuple(caveats), coverage=coverage, rows=rows, derived=derived)
