"""src/compute/health/monthly_revenue_month_contract.py — 月營收「月份資料契約」(DEC-151 Batch A,L2 純函式).

為什麼需要(2026-11-08 DEC-150 Batch B1 調查):`compute_yoy_mom` 的 `yoy_last3` 取 df『最後 3 列』
(不是最後 3 個日曆月)、輸出只有 3 個浮點、沒有月份鍵;L1 fetcher 對缺月/NaN 列 `dropna` 直接丟掉。
→ `[20,30,40]` 與「缺 2025-08」的 `[20,30,40]` 長得一模一樣,『位置即月份』不成立,
C4(月營收 YoY 逐月加速)無法分辨「連續三個月」與「跳月」。

本模組只做 **producer 端**資料契約(additive、向後相容),**不改任何分數、不改 tier**:
Batch B 才會讓 C4 使用這些欄位。舊欄位(`yoy_last3` 等)由 `compute_yoy_mom` 原樣保留。

契約欄位(全部由 `compute_month_contract` 產生,compute_yoy_mom 以 additive 方式併入回傳 dict):
  contract_version            int       契約版本
  contract_status             str       OK / FAIL_CLOSED / UNDETERMINED(見下)
  contract_fail_reasons       list[str] FAIL_CLOSED/UNDETERMINED 的原因(不默默修正)
  as_of                       str|None  回溯基準日(ISO);None = 呼叫端沒給
  month_key_source            str       revenue_year_month / date_column / none
  month_key_verified          bool      月份鍵是否來自『明示的 revenue_year+revenue_month 欄、date 與之逐列一致、且呼叫端
                                         未標記該來源『尚未經真實資料驗證』(`source_month_key_verified`,DEC-152)』
  month_key_source_fields     list[str] 月份鍵實際取自哪些欄位(['revenue_year','revenue_month'] / ['date'] / [])
  month_key_date_agrees       bool|None 有 revenue_year/month 與 date 兩者時,逐列年月是否全部一致;不適用 → None
                                         (False ＝ date 與營收月份不同,**不**視為衝突:DEC-152 客戶指出兩者本來就可能不同)
  yoy_months                  list      與舊 `yoy_last3` 一對一對應的年月鍵 'YYYY-MM'(列位置的月份,None = 無此列/無法判定)
  yoy_months_contiguous       bool|None 舊 `yoy_last3` 那 3 列是否為 3 個連續日曆月;None = UNDETERMINED
  yoy_target_months           list[3]   固定 3 個目標日曆月(最近 3 個『已達 SSOT 公告時點』的月,舊→新);None = as_of 缺
  yoy_target3                 list[3]   目標月的 YoY%,缺值保留位置(None)——不補造數值
  yoy_missing_reasons         list[3]   各目標月缺值原因(MONTH_REASON_*;有值則 None)
  target_observed             list[3]   (1)該月有真實營收觀測
  target_base_valid           list[3]   (2)去年同月基期存在且 ≠ 0
  target_yoy_computable       list[3]   (3)YoY 可合法計算(含合法真 0%)
  target_date_eligible        list[3]   (4)公告時點資格:True = 月份鍵已驗證且 SSOT 公告時點 ≤ as_of;
                                         None = NOT VERIFIED;False = 未到公告時點
  date_eligibility            str       VERIFIED_BY_SSOT_LAG / NOT_VERIFIED(整體;不得補造日期)
  date_eligibility_reasons    list[str] NOT_VERIFIED 的原因
  excluded_not_yet_due_months list     表內有列、但尚未到 SSOT 公告時點而被排除的月(不入目標)
  yoy_last3_matches_target    bool|None 舊 yoy_last3 的 3 列是否剛好就是目標 3 個月(否則舊欄位含非目標月)
連續性(yoy_months_contiguous)/觀測/基期/可算/公告時點 = 五項獨立欄位,**刻意不濃縮成單一布林**。

公告時點的『可信』判準只用 repo 既有 SSOT:`shared.staleness.MACRO_PUBLICATION_LAG_DAYS['tw_monthly_revenue']`
與 `monthly_publication_due`(due = 次月 1 日 + 發布延遲)。⚠️ 來源(FinMind/OpenAPI)沒有逐筆『實際公告日』欄位,
本契約只能保證『已過 SSOT 公告時點』,**不能**證明某公司某月在某日確實已公告;不得用 fetched_at 當公告日、
不得從列表位置推月份、不得用目前日期推斷『某月已發布』——只在呼叫端明確給 as_of(可注入)時比對 SSOT 公告時點。
月份鍵只認明示欄位(DEC-152 C4-D 起):
  · 有 revenue_year+revenue_month → **以它們為月份鍵**(來源宣稱的營收所屬月);date 只用來交叉核對:
      - 逐列一致且呼叫端未標記『來源未驗證』→ 已驗證(month_key_verified=True,與修前相同);
      - date 與營收月份**不同**(例:date 是公布月)→ **不 FAIL_CLOSED**(修前會),但 month_key_verified=False,
        公告時點資格 NOT VERIFIED(原因 date_differs_from_revenue_ym);
      - 呼叫端傳 `source_month_key_verified=False`(全市場批次路徑,SSOT
        `shared.monthly_revenue_month_key.BATCH_SOURCE_MONTH_KEY_VERIFIED`)→ 一律 month_key_verified=False:
        來源欄位宣稱的月份在**真實資料驗證前**不得使公告時點資格變 True(護欄,不是評分規則)。
  · 只有 date → 月份語意『NOT VERIFIED』(FinMind 的 date 可能是營收月或公布月,本沙箱連不到 FinMind 無法核實),
    公告時點資格一律 NOT VERIFIED,依賴它的強連續訊號由 Batch B 阻擋;
  · 重複月 / 月序錯亂 / 月份鍵無法解析(含 revenue_year/month 缺值、date 存在卻有解析不了的列)→ FAIL_CLOSED
    (標原因,不默默修正)。**不從 date 推導 revenue_year/month 補缺**:缺值就是缺值。

§8.2:L2 純函式,不碰 I/O、不讀時鐘(as_of 由呼叫端注入)。
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any

import pandas as pd

from shared.staleness import MACRO_PUBLICATION_LAG_DAYS, expected_latest_data_month, monthly_publication_due

CONTRACT_VERSION = 1
#: 月營收發布延遲 SSOT 的 indicator 名稱(shared/staleness.py;CLAUDE.md §2.3『月後 ~10 天』)。
REVENUE_INDICATOR = "tw_monthly_revenue"
TARGET_MONTHS = 3          # C4 看『最近 3 個月』(既有行為,非新增閾值)

# contract_status
STATUS_OK = "OK"
STATUS_FAIL_CLOSED = "FAIL_CLOSED"
STATUS_UNDETERMINED = "UNDETERMINED"
# month_key_source
SRC_REVENUE_YM = "revenue_year_month"
SRC_DATE = "date_column"
SRC_NONE = "none"
# date_eligibility
ELIG_VERIFIED = "VERIFIED_BY_SSOT_LAG"
ELIG_NOT_VERIFIED = "NOT_VERIFIED"

# 各月缺值原因
MONTH_REASON_NO_OBSERVATION = "no_observation"          # 無該月觀測
MONTH_REASON_MISSING_BASE = "missing_base"              # 缺去年同月基期
MONTH_REASON_YOY_NOT_COMPUTABLE = "yoy_not_computable"  # YoY 不可算(基期為 0)
MONTH_REASON_NOT_YET_DUE = "not_yet_due"                # 未到公告時點
MONTH_REASON_DATE_UNPARSEABLE = "date_unparseable"      # 日期/年月無法解析
MONTH_REASON_AS_OF_MISSING = "as_of_missing"            # 呼叫端沒給 as_of → 目標月無法定
MONTH_REASON_FAIL_CLOSED = "contract_fail_closed"       # 整體 fail-closed

# 整體 fail-closed / UNDETERMINED 原因
FAIL_DUPLICATE_MONTH = "duplicate_month"
FAIL_MONTH_ORDER = "month_order_disorder"
FAIL_MONTH_UNPARSEABLE = "month_unparseable"
FAIL_UPSTREAM = "upstream_fetch_failed"
FAIL_CONTRACT_EXCEPTION = "contract_exception"
UND_NO_DATA = "no_data"
UND_NO_MONTH_INFO = "no_month_info"
UND_LEGACY_INPUT = "legacy_input_no_month_contract"
# date_eligibility_reasons 的資訊性原因(非 FAIL)
ELIG_REASON_DATE_DIFFERS = "date_differs_from_revenue_ym"        # date 與來源宣稱營收月份不同(DEC-152:合法,但無法自我驗證)
ELIG_REASON_SOURCE_UNVERIFIED = "source_month_key_unverified_pending_real_data"   # 護欄:來源欄位未經真實資料驗證

#: 注入到 L3 輸入 dict 的鍵(shortage_screener 的 stock['revenue_month_contract'])。
MONTH_CONTRACT_KEY = "revenue_month_contract"

#: `extract_month_contract` 要從 compute_yoy_mom 結果複製的契約欄位(舊欄位不在內)。
CONTRACT_FIELDS: tuple[str, ...] = (
    "contract_version", "contract_status", "contract_fail_reasons", "as_of",
    "month_key_source", "month_key_verified", "month_key_source_fields", "month_key_date_agrees", "yoy_months", "yoy_months_contiguous",
    "yoy_target_months", "yoy_target3", "yoy_missing_reasons",
    "target_observed", "target_base_valid", "target_yoy_computable", "target_date_eligible",
    "date_eligibility", "date_eligibility_reasons", "excluded_not_yet_due_months",
    "yoy_last3_matches_target",
)


def _label(idx: int | None) -> str | None:
    """月序(y*12+m-1)→ 'YYYY-MM'。"""
    if idx is None:
        return None
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _month_idx(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _parse_as_of(as_of: Any) -> _dt.date | None:
    """as_of → date;None / 無法解析 → None(不猜、不退回今天)。"""
    if as_of is None:
        return None
    if isinstance(as_of, pd.Timestamp):
        return None if pd.isna(as_of) else as_of.date()
    if isinstance(as_of, _dt.datetime):
        return as_of.date()
    if isinstance(as_of, _dt.date):
        return as_of
    try:
        _t = pd.to_datetime(as_of, errors="coerce")
    except (ValueError, TypeError):
        return None
    return None if _t is pd.NaT or pd.isna(_t) else _t.date()


def _finite_float(v: Any) -> float | None:
    """營收值 → 有限 float;缺/NaN/inf/非數 → None(不當成 0)。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _empty_contract(status: str, reasons: list[str], *, as_of: _dt.date | None = None,
                    n_yoy: int = 0, source: str = SRC_NONE) -> dict[str, Any]:
    """沒有可判斷內容時的契約(全部『未知』,不預設連續、不預設合格)。"""
    _r = list(reasons)
    return {
        "contract_version": CONTRACT_VERSION,
        "contract_status": status,
        "contract_fail_reasons": _r,
        "as_of": as_of.isoformat() if as_of else None,
        "month_key_source": source,
        "month_key_verified": False,
        "month_key_source_fields": [],
        "month_key_date_agrees": None,
        "yoy_months": [None] * n_yoy,
        "yoy_months_contiguous": None,
        "yoy_target_months": [None] * TARGET_MONTHS,
        "yoy_target3": [None] * TARGET_MONTHS,
        "yoy_missing_reasons": [MONTH_REASON_FAIL_CLOSED if status == STATUS_FAIL_CLOSED
                                else MONTH_REASON_NO_OBSERVATION] * TARGET_MONTHS,
        "target_observed": [None] * TARGET_MONTHS,
        "target_base_valid": [None] * TARGET_MONTHS,
        "target_yoy_computable": [None] * TARGET_MONTHS,
        "target_date_eligible": [None] * TARGET_MONTHS,
        "date_eligibility": ELIG_NOT_VERIFIED,
        "date_eligibility_reasons": list(_r),
        "excluded_not_yet_due_months": [],
        "yoy_last3_matches_target": None,
    }


def legacy_undetermined_contract() -> dict[str, Any]:
    """舊 caller 只給舊欄位(沒有月份契約)時的明確預設:連續性 UNDETERMINED(None),**不得**預設 contiguous=True。"""
    return _empty_contract(STATUS_UNDETERMINED, [UND_LEGACY_INPUT])


def resolve_month_contract(obj: Any) -> dict[str, Any]:
    """從 compute_yoy_mom 結果或 L3 輸入 dict 取月份契約;沒有 → `legacy_undetermined_contract()`。

    供 Batch B 的 C4 使用:舊輸入(只有 `revenue_yoy_last3`)得到 UNDETERMINED,而不是預設連續。
    """
    if isinstance(obj, dict):
        _c = obj.get(MONTH_CONTRACT_KEY)
        if isinstance(_c, dict) and "contract_status" in _c:
            return _c
        if "contract_status" in obj and "yoy_months_contiguous" in obj:
            return {k: obj[k] for k in CONTRACT_FIELDS if k in obj}
    return legacy_undetermined_contract()


def extract_month_contract(stats: dict[str, Any] | None) -> dict[str, Any]:
    """compute_yoy_mom 結果 → 只含契約欄位的 dict(給 L3 塞進輸入;不含舊欄位)。"""
    if not isinstance(stats, dict) or "contract_status" not in stats:
        return legacy_undetermined_contract()
    return {k: stats[k] for k in CONTRACT_FIELDS if k in stats}


def mark_upstream_failed(contract: dict[str, Any] | None) -> dict[str, Any]:
    """上游抓取確定失敗時,把契約改成 FAIL_CLOSED(上游失敗不得推定成功;不補造任何月份)。"""
    _c = dict(contract) if isinstance(contract, dict) and "contract_status" in contract \
        else legacy_undetermined_contract()
    _reasons = [r for r in _c.get("contract_fail_reasons", []) if r != UND_LEGACY_INPUT]
    if FAIL_UPSTREAM not in _reasons:
        _reasons.append(FAIL_UPSTREAM)
    _out = _empty_contract(STATUS_FAIL_CLOSED, _reasons, n_yoy=len(_c.get("yoy_months") or []),
                           source=_c.get("month_key_source", SRC_NONE))
    _out["as_of"] = _c.get("as_of")
    return _out


def _row_keys(df: pd.DataFrame):
    """逐列月份鍵(原始列序,不排序)。回 (keys, source, self_consistent, fail_reasons, date_agrees)。

    keys[i] = 月序 int 或 None(該列無法解析)。只認明示欄位,不從列位置推月份,**不從 date 推導 revenue_year/month**。
    self_consistent = 月份鍵全可解析且(有 date 時)date 逐列與之同月(尚未計入呼叫端的『來源未驗證』標記)。
    date_agrees = 兩組欄位都在時 date 與 revenue_year/month 是否逐列一致;其餘 None。date≠營收月份不是 FAIL(DEC-152)。
    """
    _n = len(df)
    _has_ym = "revenue_year" in df.columns and "revenue_month" in df.columns
    _has_date = "date" in df.columns
    _fails: list[str] = []

    _date_keys: list[int | None] = [None] * _n
    if _has_date:
        try:
            _dts = pd.to_datetime(df["date"], errors="coerce")
        except (ValueError, TypeError):
            _dts = pd.Series([pd.NaT] * _n)
        for i, t in enumerate(_dts.tolist()):
            if t is not pd.NaT and not pd.isna(t):
                _date_keys[i] = _month_idx(int(t.year), int(t.month))

    _ym_keys: list[int | None] = [None] * _n
    if _has_ym:
        _ys = pd.to_numeric(df["revenue_year"], errors="coerce").tolist()
        _ms = pd.to_numeric(df["revenue_month"], errors="coerce").tolist()
        for i, (y, m) in enumerate(zip(_ys, _ms)):
            if y is None or m is None or pd.isna(y) or pd.isna(m):
                continue
            if float(y) != int(y) or float(m) != int(m):
                continue
            y, m = int(y), int(m)
            if 1900 <= y <= 2200 and 1 <= m <= 12:
                _ym_keys[i] = _month_idx(y, m)

    if _has_ym:
        _keys = _ym_keys
        _src = SRC_REVENUE_YM
        if any(k is None for k in _keys):
            _fails.append(FAIL_MONTH_UNPARSEABLE)
        if _has_date and any(d is None for d in _date_keys):
            _fails.append(FAIL_MONTH_UNPARSEABLE)   # date 欄存在卻有解析不了的列 → 跨欄無法對照
        # DEC-152:date 與營收月份不同不再是 FAIL(客戶指出本來就可能不同,例:date=公布月);只記錄,且不得因此算『已驗證』
        _agrees = (all(d is not None and k is not None and d == k for d, k in zip(_date_keys, _ym_keys))
                   if _has_date else None)
        _verified = not _fails and _agrees is not False
        return _keys, _src, _verified, sorted(set(_fails)), _agrees
    elif _has_date:
        _keys = _date_keys
        _src = SRC_DATE
        if any(k is None for k in _keys):
            _fails.append(FAIL_MONTH_UNPARSEABLE)
        _verified = False
    else:
        return [None] * _n, SRC_NONE, False, [], None
    return _keys, _src, _verified, sorted(set(_fails)), None


def compute_month_contract(
    df_stock: pd.DataFrame | None,
    *,
    as_of: Any = None,
    upstream_failed: bool = False,
    source_month_key_verified: bool = True,
) -> dict[str, Any]:
    """對單股月營收序列產生月份資料契約(欄位定義見模組 docstring)。

    Args:
        df_stock: [date, revenue(, revenue_year, revenue_month)];**原始列序**即判定月序是否錯亂的依據。
        as_of: 回溯基準日(date/datetime/'YYYY-MM-DD');None → 目標月無法決定,公告時點 NOT VERIFIED。
               呼叫端注入(L2 不讀時鐘);回溯時未到 SSOT 公告時點的月不入。
        upstream_failed: L1 判定上游確定抓取失敗 → FAIL_CLOSED(不推定成功)。
        source_month_key_verified: 呼叫端對『revenue_year/revenue_month 欄來源』的信任標記(DEC-152 護欄)。
            預設 True ＝ 修前行為(明示欄位且 date 逐列一致 → month_key_verified);
            False ＝ 來源宣稱的月份**尚未經真實資料驗證**(全市場批次路徑傳 SSOT
            `BATCH_SOURCE_MONTH_KEY_VERIFIED`),month_key_verified 與公告時點資格一律 NOT VERIFIED。
            此旗標只收緊、不放寬;不影響 FAIL_CLOSED 判定、缺值位置或任何分數規則。
    """
    _asof = _parse_as_of(as_of)
    if upstream_failed:
        return _empty_contract(STATUS_FAIL_CLOSED, [FAIL_UPSTREAM], as_of=_asof)
    if df_stock is None or not isinstance(df_stock, pd.DataFrame) or df_stock.empty \
            or "revenue" not in df_stock.columns:
        return _empty_contract(STATUS_UNDETERMINED, [UND_NO_DATA], as_of=_asof)
    try:
        return _compute(df_stock, _asof, source_trusted=bool(source_month_key_verified))
    except Exception as _e:  # noqa: BLE001 — 契約算不出來 = fail-closed 並 loud,絕不讓它拖垮舊欄位或偽裝成功
        print(f"[month-contract] 契約計算例外 → FAIL_CLOSED: {type(_e).__name__}: {_e}")
        return _empty_contract(STATUS_FAIL_CLOSED, [f"{FAIL_CONTRACT_EXCEPTION}:{type(_e).__name__}"], as_of=_asof)


def _compute(df: pd.DataFrame, asof: _dt.date | None, *, source_trusted: bool = True) -> dict[str, Any]:
    _n = len(df)
    _keys, _src, _verified, _fails, _agrees = _row_keys(df)
    _fields = {SRC_REVENUE_YM: ["revenue_year", "revenue_month"], SRC_DATE: ["date"]}.get(_src, [])
    if _src == SRC_NONE:
        return _empty_contract(STATUS_UNDETERMINED, [UND_NO_MONTH_INFO], as_of=asof, n_yoy=3)

    # 月序 / 重複 檢查(原始列序;只看解析得出的列)
    _valid = [k for k in _keys if k is not None]
    if len(set(_valid)) != len(_valid):
        _fails.append(FAIL_DUPLICATE_MONTH)
    if any(b < a for a, b in zip(_valid, _valid[1:])):
        _fails.append(FAIL_MONTH_ORDER)
    _fails = sorted(set(_fails))
    # 舊 yoy_last3 恆為 3 元素(n>=1);yoy_months 與之一對一
    _n_yoy = 3
    if _fails:
        _c = _empty_contract(STATUS_FAIL_CLOSED, _fails, as_of=asof, n_yoy=_n_yoy, source=_src)
        _c["month_key_source_fields"] = list(_fields)
        _c["yoy_target_months"] = [None] * TARGET_MONTHS
        if asof is not None:   # 目標月是日曆事實(只依 as_of 與 SSOT),不受資料列影響
            _c["yoy_target_months"] = _target_labels(asof)
        return _c

    _revs = [_finite_float(v) for v in pd.to_numeric(df["revenue"], errors="coerce").tolist()]
    _rev_by: dict[int, float] = {k: r for k, r in zip(_keys, _revs) if k is not None and r is not None}
    _present: set[int] = {k for k in _keys if k is not None}

    # ── 與舊 yoy_last3 一對一的年月鍵(最後 3 列) ─────────────────────
    _yoy_idx: list[int | None] = []
    for _off in (2, 1, 0):
        _i = _n - 1 - _off
        _yoy_idx.append(_keys[_i] if _i >= 0 else None)
    _contig: bool | None
    if any(k is None for k in _yoy_idx):
        _contig = False      # 不足 3 列:不可能是 3 個連續月(已知,不是 UNDETERMINED)
    else:
        _contig = (_yoy_idx[1] - _yoy_idx[0] == 1) and (_yoy_idx[2] - _yoy_idx[1] == 1)

    _elig_reasons: list[str] = []
    if asof is None:
        _elig_reasons.append(MONTH_REASON_AS_OF_MISSING)
    if _src == SRC_DATE:
        _elig_reasons.append("month_key_unverified_date_only")
    if _src == SRC_REVENUE_YM and _agrees is False:
        _elig_reasons.append(ELIG_REASON_DATE_DIFFERS)
    if _src == SRC_REVENUE_YM and _verified and not source_trusted:
        _elig_reasons.append(ELIG_REASON_SOURCE_UNVERIFIED)
    # 護欄(DEC-152):來源宣稱的月份在真實資料驗證前,不得使 month_key_verified / 公告時點資格變 True
    _verified = _verified and source_trusted

    # ── 固定 3 個目標月 ───────────────────────────────────────────────
    if asof is None:
        _tgt_idx: list[int | None] = [None] * TARGET_MONTHS
    else:
        _end = _expected_end_idx(asof)
        _tgt_idx = [_end - 2, _end - 1, _end]

    _obs: list[bool | None] = []
    _basev: list[bool | None] = []
    _comp: list[bool | None] = []
    _elig: list[bool | None] = []
    _yoy: list[float | None] = []
    _why: list[str | None] = []
    for t in _tgt_idx:
        if t is None:
            _obs.append(None); _basev.append(None); _comp.append(None); _elig.append(None)
            _yoy.append(None); _why.append(MONTH_REASON_AS_OF_MISSING)
            continue
        _due = monthly_publication_due(_label(t), indicator=REVENUE_INDICATOR)
        _due_ok = _due is not None and _due <= asof
        _elig.append((True if _verified else None) if _due_ok else False)
        _cur = _rev_by.get(t)
        _base = _rev_by.get(t - 12)
        _o = _cur is not None
        _bv = _base is not None and _base != 0.0
        _obs.append(_o)
        _basev.append(_bv)
        _comp.append(_o and _bv)
        if _o and _bv:
            _yoy.append((_cur / _base - 1.0) * 100.0)
            _why.append(None)
        else:
            _yoy.append(None)
            if not _o:
                _why.append(MONTH_REASON_NO_OBSERVATION)
            elif _base is None:
                _why.append(MONTH_REASON_MISSING_BASE)
            else:
                _why.append(MONTH_REASON_YOY_NOT_COMPUTABLE)

    # 表內有列、但尚未到 SSOT 公告時點 → 排除(回溯不得看到未來資料 / 未公告月不入)
    _excluded: list[str] = []
    if asof is not None:
        _end = _tgt_idx[-1]
        _excluded = [_label(k) for k in sorted(_present) if k > _end]

    _ok = asof is not None and _verified
    return {
        "contract_version": CONTRACT_VERSION,
        "contract_status": STATUS_OK,
        "contract_fail_reasons": [],
        "as_of": asof.isoformat() if asof else None,
        "month_key_source": _src,
        "month_key_verified": _verified,
        "month_key_source_fields": list(_fields),
        "month_key_date_agrees": _agrees,
        "yoy_months": [_label(k) for k in _yoy_idx],
        "yoy_months_contiguous": _contig,
        "yoy_target_months": [_label(t) for t in _tgt_idx],
        "yoy_target3": _yoy,
        "yoy_missing_reasons": _why,
        "target_observed": _obs,
        "target_base_valid": _basev,
        "target_yoy_computable": _comp,
        "target_date_eligible": _elig,
        "date_eligibility": ELIG_VERIFIED if _ok else ELIG_NOT_VERIFIED,
        "date_eligibility_reasons": [] if _ok else _elig_reasons,
        "excluded_not_yet_due_months": _excluded,
        "yoy_last3_matches_target": (None if asof is None else _yoy_idx == _tgt_idx),
    }


def _expected_end_idx(asof: _dt.date) -> int:
    """最近一個『已達 SSOT 公告時點』的日曆月(月序):重用 shared.staleness,grace=0,不另訂規則。"""
    _m = expected_latest_data_month(lag_days=MACRO_PUBLICATION_LAG_DAYS[REVENUE_INDICATOR],
                                    today=asof, grace_days=0)
    return _month_idx(_m.year, _m.month)


def _target_labels(asof: _dt.date) -> list[str]:
    _end = _expected_end_idx(asof)
    return [_label(_end - 2), _label(_end - 1), _label(_end)]
