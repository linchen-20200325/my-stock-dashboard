"""tests/test_c4a_month_contract.py — DEC-151 Batch A:月營收『月份資料契約』(producer 端,additive)。

守衛的事(⚠️ ④『本批不改 C4 分數』只描述 Batch A;Batch B〔tests/test_c4b_revenue_scoring.py〕已依 DEC-151 改 C4 計分,④ 現只保證 C1–C3 與 tier 邏輯不受契約鍵影響):
  ① 舊欄位 parity:`compute_yoy_mom` 的舊 5 個欄位與修前逐值相同(20000 組固定種子對照修前凍結複本);
  ② 契約行為:連續/缺中間/缺末/缺首/跳月/缺基期/日期無法驗證/重複/錯亂/單月/OpenAPI 單月/上游失敗/
     未到公告時點/as_of 回溯/真 0 YoY/舊 caller UNDETERMINED;
  ③ 三個真突變(改寫被測碼 → 檢查轉紅):缺月被壓縮、未公告月被使用、無日期默認連續;
  ④ 本批不改 C4 分數(shortage_screener 對有/無契約鍵的輸入結果逐值相同)。
本檔不釘任何檔案 sha(被改的 monthly_revenue_calc／shortage_screener_service／shortage_cli 查無被釘測試)。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import math
import random
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.compute.health import monthly_revenue_month_contract as REAL  # noqa: E402
from src.compute.health.monthly_revenue_calc import compute_yoy_mom  # noqa: E402

A = dt.date


# ───────────────────────── 輔助 ─────────────────────────
def mk(months, *, ym=True, base=100.0, step=3.0, rev=None):
    """months: ['2025-01', ...];revenue = base + 位置*step(可用 rev dict 覆寫)。"""
    rows = []
    for i, m in enumerate(months):
        y, mo = int(m[:4]), int(m[5:])
        r = (rev or {}).get(m, base + i * step)
        row = {"date": pd.Timestamp(y, mo, 1), "revenue": r}
        if ym:
            row.update(revenue_year=y, revenue_month=mo)
        rows.append(row)
    return pd.DataFrame(rows)


def span(a, b):
    return [str(p) for p in pd.period_range(a, b, freq="M")]


# ───────────────────────── 檢查函式(對 module 參數化 → 同時供正測與突變用) ─────────────────────────
def check_contiguous_all_valid(M):
    c = M.compute_month_contract(mk(span("2025-01", "2026-09")), as_of=A(2026, 10, 15))
    assert c["contract_status"] == "OK"
    assert c["yoy_target_months"] == ["2026-07", "2026-08", "2026-09"]
    assert c["yoy_months"] == ["2026-07", "2026-08", "2026-09"]
    assert c["yoy_months_contiguous"] is True
    assert c["target_observed"] == [True] * 3 and c["target_base_valid"] == [True] * 3
    assert c["target_yoy_computable"] == [True] * 3 and c["target_date_eligible"] == [True] * 3
    assert c["yoy_missing_reasons"] == [None] * 3
    assert c["date_eligibility"] == M.ELIG_VERIFIED and c["yoy_last3_matches_target"] is True


def check_gap_not_compressed(M):
    """2026-07/09/10(缺 8 月)不得當三連續;缺月位置保留、不補造數值。"""
    months = [m for m in span("2025-01", "2026-10") if m != "2026-08"]
    c = M.compute_month_contract(mk(months), as_of=A(2026, 11, 15))
    assert c["yoy_target_months"] == ["2026-08", "2026-09", "2026-10"]
    assert c["yoy_months"] == ["2026-07", "2026-09", "2026-10"]
    assert c["yoy_months_contiguous"] is False
    assert c["target_observed"] == [False, True, True]
    assert c["yoy_target3"][0] is None and c["yoy_target3"][1] is not None
    assert c["yoy_missing_reasons"][0] == M.MONTH_REASON_NO_OBSERVATION
    assert c["yoy_last3_matches_target"] is False


def check_unpublished_month_excluded(M):
    """as_of=2026-10-05:9 月營收 SSOT 公告時點(10/11)未到 → 即使表內已有 9 月列也不入目標。"""
    c = M.compute_month_contract(mk(span("2025-01", "2026-09")), as_of=A(2026, 10, 5))
    assert c["yoy_target_months"] == ["2026-06", "2026-07", "2026-08"]
    assert c["excluded_not_yet_due_months"] == ["2026-09"]
    assert c["yoy_last3_matches_target"] is False
    assert "2026-09" not in c["yoy_target_months"]


def check_legacy_not_contiguous(M):
    """舊 caller 只給舊欄位 → UNDETERMINED(None),不得默認 contiguous=True。"""
    for obj in ({"revenue_yoy_last3": [10.0, 20.0, 30.0]}, {}, None,
                {"yoy_last3": [1.0, 2.0, 3.0]}):
        c = M.resolve_month_contract(obj)
        assert c["contract_status"] == M.STATUS_UNDETERMINED
        assert c["yoy_months_contiguous"] is None
        assert c["date_eligibility"] == M.ELIG_NOT_VERIFIED
    c2 = M.compute_month_contract(None)
    assert c2["yoy_months_contiguous"] is None and c2["contract_status"] == M.STATUS_UNDETERMINED


CHECKS = [check_contiguous_all_valid, check_gap_not_compressed,
          check_unpublished_month_excluded, check_legacy_not_contiguous]


@pytest.mark.parametrize("fn", CHECKS, ids=lambda f: f.__name__)
def test_real_module_passes_checks(fn):
    fn(REAL)


# ───────────────────────── 突變(改寫被測碼,檢查必須轉紅) ─────────────────────────
def _load_mutant(old: str, new: str):
    src = (REPO / "src/compute/health/monthly_revenue_month_contract.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變錨點必須在原檔恰出現 1 次:{old!r}(實得 {src.count(old)})"
    mod = types.ModuleType("_c4a_mutant")
    mod.__file__ = "<mutant>"
    sys.modules["_c4a_mutant"] = mod
    exec(compile(src.replace(old, new), "<mutant>", "exec"), mod.__dict__)
    return mod


MUTANTS = {
    # 缺月被壓縮:把『3 列月份是否相鄰』改成『只要 3 列都有月份就算連續』→ 07/09/10 被當三連續
    "gap_compressed": ("_contig = (_yoy_idx[1] - _yoy_idx[0] == 1) and (_yoy_idx[2] - _yoy_idx[1] == 1)",
                       "_contig = True", check_gap_not_compressed),
    # 未公告月被使用:不看 SSOT 公告時點,改用『目前月份 − 1』當已發布(= 用目前日期推斷某月已發布)
    "unpublished_used": ("_end = _expected_end_idx(asof)\n        _tgt_idx = [_end - 2, _end - 1, _end]",
                         "_end = _month_idx(asof.year, asof.month) - 1\n        _tgt_idx = [_end - 2, _end - 1, _end]",
                         check_unpublished_month_excluded),
    # 無日期默認連續:空契約的連續性預設成 True
    "default_contiguous": ('"yoy_months_contiguous": None,\n        "yoy_target_months"',
                           '"yoy_months_contiguous": True,\n        "yoy_target_months"',
                           check_legacy_not_contiguous),
}


@pytest.mark.parametrize("name", list(MUTANTS))
def test_mutant_is_killed(name):
    old, new, chk = MUTANTS[name]
    mut = _load_mutant(old, new)
    chk(REAL)                                   # 原碼綠
    with pytest.raises(AssertionError):         # 突變碼紅
        chk(mut)


# ───────────────────────── 契約行為 ─────────────────────────
def test_missing_last_month():
    c = REAL.compute_month_contract(mk(span("2025-01", "2026-08")), as_of=A(2026, 10, 15))
    assert c["yoy_target_months"] == ["2026-07", "2026-08", "2026-09"]
    assert c["target_observed"] == [True, True, False]
    assert c["yoy_missing_reasons"] == [None, None, REAL.MONTH_REASON_NO_OBSERVATION]
    assert c["yoy_target3"][2] is None
    assert c["yoy_last3_matches_target"] is False


def test_missing_first_month():
    months = [m for m in span("2025-01", "2026-09") if m != "2026-07"]
    c = REAL.compute_month_contract(mk(months), as_of=A(2026, 10, 15))
    assert c["target_observed"] == [False, True, True]
    assert c["yoy_missing_reasons"][0] == REAL.MONTH_REASON_NO_OBSERVATION
    assert c["yoy_months"] == ["2026-06", "2026-08", "2026-09"] and c["yoy_months_contiguous"] is False


def test_missing_middle_keeps_position_and_reason():
    months = [m for m in span("2025-01", "2026-09") if m != "2026-08"]
    c = REAL.compute_month_contract(mk(months), as_of=A(2026, 10, 15))
    assert c["target_observed"] == [True, False, True]
    assert c["yoy_missing_reasons"] == [None, REAL.MONTH_REASON_NO_OBSERVATION, None]
    assert c["yoy_target3"][1] is None and None not in (c["yoy_target3"][0], c["yoy_target3"][2])


def test_missing_base_month():
    months = [m for m in span("2025-01", "2026-09") if m != "2025-08"]   # 缺去年 8 月基期
    c = REAL.compute_month_contract(mk(months), as_of=A(2026, 10, 15))
    assert c["target_observed"] == [True, True, True]
    assert c["target_base_valid"] == [True, False, True]
    assert c["target_yoy_computable"] == [True, False, True]
    assert c["yoy_missing_reasons"] == [None, REAL.MONTH_REASON_MISSING_BASE, None]


def test_zero_base_is_not_computable_but_true_zero_yoy_is_valid():
    rev = {"2025-09": 0.0}                                  # 基期 0 → 不可算
    c = REAL.compute_month_contract(mk(span("2025-01", "2026-09"), rev=rev), as_of=A(2026, 10, 15))
    assert c["target_base_valid"][2] is False and c["target_yoy_computable"][2] is False
    assert c["yoy_missing_reasons"][2] == REAL.MONTH_REASON_YOY_NOT_COMPUTABLE
    # 合法真 0% YoY:本月 == 去年同月 → 0.0,不是 missing
    rev2 = {"2025-09": 150.0, "2026-09": 150.0}
    c2 = REAL.compute_month_contract(mk(span("2025-01", "2026-09"), rev=rev2), as_of=A(2026, 10, 15))
    assert c2["yoy_target3"][2] == 0.0 and c2["target_yoy_computable"][2] is True
    assert c2["yoy_missing_reasons"][2] is None


def test_date_only_is_not_verified():
    c = REAL.compute_month_contract(mk(span("2025-01", "2026-09"), ym=False), as_of=A(2026, 10, 15))
    assert c["contract_status"] == "OK" and c["month_key_source"] == REAL.SRC_DATE
    assert c["month_key_verified"] is False
    assert c["date_eligibility"] == REAL.ELIG_NOT_VERIFIED
    assert c["target_date_eligible"] == [None] * 3          # 不是 True、也不是 False:NOT VERIFIED
    assert c["yoy_months_contiguous"] is True                # 連續性是相對判斷,不受月份語意影響


def test_as_of_missing_is_not_verified_and_no_clock():
    c = REAL.compute_month_contract(mk(span("2025-01", "2026-09")))
    assert c["yoy_target_months"] == [None] * 3 and c["date_eligibility"] == REAL.ELIG_NOT_VERIFIED
    assert c["yoy_missing_reasons"] == [REAL.MONTH_REASON_AS_OF_MISSING] * 3
    assert c["as_of"] is None and c["yoy_months_contiguous"] is True   # 列層面的連續性仍可判
    c2 = REAL.compute_month_contract(mk(span("2025-01", "2026-09")), as_of="not-a-date")
    assert c2["as_of"] is None and c2["date_eligibility"] == REAL.ELIG_NOT_VERIFIED


@pytest.mark.parametrize("mutate,reason", [
    (lambda d: pd.concat([d, d.iloc[[5]]], ignore_index=True).sort_values("date", kind="stable")
     .reset_index(drop=True), REAL.FAIL_DUPLICATE_MONTH),                       # 月份重複
    (lambda d: d.iloc[::-1].reset_index(drop=True), REAL.FAIL_MONTH_ORDER),      # 月序錯亂
])
def test_duplicate_and_disorder_fail_closed(mutate, reason):
    df = mutate(mk(span("2025-01", "2026-09")))
    c = REAL.compute_month_contract(df, as_of=A(2026, 10, 15))
    assert c["contract_status"] == REAL.STATUS_FAIL_CLOSED and reason in c["contract_fail_reasons"]
    assert c["yoy_target3"] == [None] * 3 and c["target_date_eligible"] == [None] * 3
    assert c["yoy_months_contiguous"] is None and c["date_eligibility"] == REAL.ELIG_NOT_VERIFIED


def test_unparseable_month_and_key_conflict_fail_closed():
    df = mk(span("2025-01", "2026-09"))
    bad = df.copy()
    bad.loc[3, "date"] = pd.NaT
    c = REAL.compute_month_contract(bad, as_of=A(2026, 10, 15))
    assert c["contract_status"] == REAL.STATUS_FAIL_CLOSED and REAL.FAIL_MONTH_UNPARSEABLE in c["contract_fail_reasons"]
    only_date = mk(span("2025-01", "2026-09"), ym=False)
    only_date.loc[3, "date"] = pd.NaT       # 只有 date 且有列無法解析:不得退回位置推月份
    c1 = REAL.compute_month_contract(only_date, as_of=A(2026, 10, 15))
    assert c1["contract_status"] == REAL.STATUS_FAIL_CLOSED
    # DEC-152 C4-D(有意識的預期變化,不是放寬):date 與 revenue_year/month 不一致**不再**直接 FAIL_CLOSED(客戶指出
    # date 與營收月份本來就可能不同);以 revenue_year/month 為月份鍵。單列被改成別的月 → 該月與既有月重複 → 仍 FAIL_CLOSED。
    conflict = df.copy()
    conflict["revenue_month"] = conflict["revenue_month"].where(conflict.index != 4, 12)  # 與 date 不一致,且與 2025-12 重複
    c2 = REAL.compute_month_contract(conflict, as_of=A(2026, 10, 15))
    assert c2["contract_status"] == REAL.STATUS_FAIL_CLOSED
    assert REAL.FAIL_DUPLICATE_MONTH in c2["contract_fail_reasons"] or REAL.FAIL_MONTH_ORDER in c2["contract_fail_reasons"]
    assert c2["target_date_eligible"] == [None] * 3
    # date 與 ym 系統性差一個月(FinMind 若以公布月為 date 就會是這種)→ 以 ym 為月份鍵、不 FAIL、但『未驗證』(不默默修正、不冒充已驗證)
    shifted = df.copy()
    shifted["date"] = shifted["date"] + pd.offsets.MonthBegin(1)
    c3 = REAL.compute_month_contract(shifted, as_of=A(2026, 10, 15))
    assert c3["contract_status"] == REAL.STATUS_OK and c3["month_key_source"] == REAL.SRC_REVENUE_YM
    assert c3["month_key_verified"] is False and c3["target_date_eligible"] == [None] * 3
    assert c3["yoy_target_months"] == ["2026-07", "2026-08", "2026-09"] and c3["yoy_months"][-1] == "2026-09"


def test_single_valid_month_and_openapi_single_month_not_three():
    one = mk(["2026-09"])
    c = REAL.compute_month_contract(one, as_of=A(2026, 10, 15))
    assert c["target_observed"] == [False, False, True]
    assert c["yoy_months_contiguous"] is False
    assert c["target_yoy_computable"] == [False, False, False]
    assert c["yoy_months"] == [None, None, "2026-09"]
    # OpenAPI 單月快照(date 取自『資料年月』,附 revenue_year/month):不得冒充三個月
    snap = mk(["2026-09"])
    snap.attrs["source"] = "TWSE-OpenAPI:t187ap05_L+TPEx:mopsfin_t187ap05_O(keyless fallback,單月快照)"
    cs = REAL.compute_month_contract(snap, as_of=A(2026, 10, 15))
    assert cs["yoy_months_contiguous"] is False and cs["target_observed"].count(True) == 1
    assert cs["yoy_target3"] == [None, None, None]          # 單月快照算不出 YoY(缺基期),不補造


def test_upstream_failure_not_presumed_success():
    full = mk(span("2025-01", "2026-09"))
    c = REAL.compute_month_contract(full, as_of=A(2026, 10, 15), upstream_failed=True)
    assert c["contract_status"] == REAL.STATUS_FAIL_CLOSED and REAL.FAIL_UPSTREAM in c["contract_fail_reasons"]
    assert c["yoy_target3"] == [None] * 3 and c["yoy_months_contiguous"] is None
    # 既有契約被標失敗後同樣 fail-closed
    ok = REAL.compute_month_contract(full, as_of=A(2026, 10, 15))
    failed = REAL.mark_upstream_failed(ok)
    assert failed["contract_status"] == REAL.STATUS_FAIL_CLOSED and failed["yoy_months_contiguous"] is None
    assert REAL.mark_upstream_failed(None)["contract_status"] == REAL.STATUS_FAIL_CLOSED
    # compute_yoy_mom 的舊欄位不受影響
    st = compute_yoy_mom(full, as_of=A(2026, 10, 15), upstream_failed=True)
    assert st["yoy_last3"] == compute_yoy_mom(full)["yoy_last3"]


def test_as_of_backtest_cannot_see_future():
    full = mk(span("2025-01", "2026-09"))
    past = A(2026, 3, 15)
    c_full = REAL.compute_month_contract(full, as_of=past)
    truncated = full[full["date"] <= pd.Timestamp(2026, 2, 1)].reset_index(drop=True)
    c_trunc = REAL.compute_month_contract(truncated, as_of=past)
    assert c_full["yoy_target_months"] == ["2025-12", "2026-01", "2026-02"]
    assert c_full["yoy_target3"] == c_trunc["yoy_target3"]               # 未來列不影響任何目標月
    assert c_full["target_observed"] == c_trunc["target_observed"]
    assert c_full["excluded_not_yet_due_months"][0] == "2026-03" and "2026-09" in c_full["excluded_not_yet_due_months"]
    assert c_trunc["excluded_not_yet_due_months"] == []


def test_ssot_boundary_publication_day():
    """邊界取 SSOT:9 月營收 due = 10/01 + tw_monthly_revenue(10) = 10/11。"""
    full = mk(span("2025-01", "2026-09"))
    assert REAL.compute_month_contract(full, as_of=A(2026, 10, 10))["yoy_target_months"][-1] == "2026-08"
    assert REAL.compute_month_contract(full, as_of=A(2026, 10, 11))["yoy_target_months"][-1] == "2026-09"
    from shared.staleness import MACRO_PUBLICATION_LAG_DAYS
    assert MACRO_PUBLICATION_LAG_DAYS[REAL.REVENUE_INDICATOR] == 10    # 契約只引 SSOT,未另訂規則


def test_year_boundary_targets():
    c = REAL.compute_month_contract(mk(span("2024-06", "2026-01")), as_of=A(2026, 2, 20))
    assert c["yoy_target_months"] == ["2025-11", "2025-12", "2026-01"]
    assert c["yoy_months_contiguous"] is True and c["target_base_valid"] == [True] * 3


def test_nan_revenue_row_is_not_an_observation_and_not_zero():
    rev = {"2026-08": float("nan")}
    c = REAL.compute_month_contract(mk(span("2025-01", "2026-09"), rev=rev), as_of=A(2026, 10, 15))
    assert c["target_observed"] == [True, False, True]
    assert c["yoy_missing_reasons"][1] == REAL.MONTH_REASON_NO_OBSERVATION and c["yoy_target3"][1] is None


def test_contract_exception_is_loud_fail_closed(capsys):
    orig = REAL._compute
    REAL._compute = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        c = REAL.compute_month_contract(mk(span("2025-01", "2026-09")), as_of=A(2026, 10, 15))
    finally:
        REAL._compute = orig
    assert c["contract_status"] == REAL.STATUS_FAIL_CLOSED
    assert any(r.startswith(REAL.FAIL_CONTRACT_EXCEPTION) for r in c["contract_fail_reasons"])
    assert "契約計算例外" in capsys.readouterr().out


def test_compute_yoy_mom_merges_contract_additively():
    full = mk(span("2025-01", "2026-09"))
    s = compute_yoy_mom(full, as_of=A(2026, 10, 15))
    for k in ("last_date", "last_revenue", "yoy_last3", "mom_last", "months_available"):
        assert k in s
    assert s["yoy_last3"] == s["yoy_target3"]                  # 連續完整時兩者一致
    legacy = compute_yoy_mom(full)                             # 舊呼叫方式:契約欄位在、但 NOT VERIFIED
    assert legacy["yoy_last3"] == s["yoy_last3"]
    assert legacy["date_eligibility"] == REAL.ELIG_NOT_VERIFIED
    e = compute_yoy_mom(pd.DataFrame(), as_of=A(2026, 10, 15))
    assert e["yoy_last3"] == [] and e["months_available"] == 0 and e["contract_status"] == REAL.STATUS_UNDETERMINED


# ───────────────────────── 舊欄位 parity(20000 組固定種子 vs 修前凍結複本) ─────────────────────────
def _load_legacy():
    p = Path(__file__).parent / "_legacy_monthly_revenue_calc_snapshot.py"
    spec = importlib.util.spec_from_file_location("_legacy_mrc", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _random_frame(rng: random.Random) -> pd.DataFrame:
    n_all = rng.randint(0, 30)
    start = rng.randint(0, 12)
    idxs = sorted(rng.sample(range(start, start + 40), min(n_all, 40))) if n_all else []
    if rng.random() < 0.7 and idxs:               # 70% 近似連續
        lo = idxs[0]
        idxs = [lo + i for i in range(len(idxs))]
        if rng.random() < 0.4 and len(idxs) > 3:   # 再隨機挖洞
            for _ in range(rng.randint(1, 3)):
                idxs.pop(rng.randrange(len(idxs)))
    rows = []
    for k in idxs:
        y, m = 2024 + k // 12, k % 12 + 1
        r = rng.choice([rng.uniform(0, 1e6), rng.uniform(0, 1e6), float("nan"), None, 0.0, 1.0])
        rows.append({"date": pd.Timestamp(y, m, rng.choice([1, 1, 1, 10, 28])), "revenue": r,
                     "revenue_year": y, "revenue_month": m})
    df = pd.DataFrame(rows, columns=["date", "revenue", "revenue_year", "revenue_month"])
    roll = rng.random()
    if roll < 0.08 and len(df):
        df.loc[rng.randrange(len(df)), "date"] = pd.NaT
    elif roll < 0.14 and len(df) > 1:
        df = pd.concat([df, df.iloc[[rng.randrange(len(df))]]], ignore_index=True)
    elif roll < 0.2 and len(df) > 1:
        df = df.sample(frac=1.0, random_state=rng.randint(0, 10**6)).reset_index(drop=True)
    elif roll < 0.26:
        df = df[["date", "revenue"]]
    elif roll < 0.3:
        df = df[["revenue"]]
    return df


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if a is pd.NaT or b is pd.NaT:
        return a is b
    if isinstance(a, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or a == b
    try:
        return bool(a == b)
    except Exception:  # noqa: BLE001
        return a is b


def test_legacy_fields_parity_20000_seeded():
    legacy = _load_legacy()
    rng = random.Random(20000)
    legacy_keys = ("last_date", "last_revenue", "yoy_last3", "mom_last", "months_available")
    n_exc = 0
    for i in range(20000):
        df = _random_frame(rng)
        as_of = rng.choice([None, A(2026, 10, 15), A(2026, 3, 9), "2026-11-30"])
        try:
            old = legacy.compute_yoy_mom(df.copy())
        except Exception as e:  # noqa: BLE001 — 修前就會拋的輸入,新版必須拋同型例外(行為不變)
            n_exc += 1
            with pytest.raises(type(e)):
                compute_yoy_mom(df.copy(), as_of=as_of)
            continue
        new = compute_yoy_mom(df.copy(), as_of=as_of)
        for k in legacy_keys:
            assert _same(old[k], new[k]), (i, k, old[k], new[k])
        assert "contract_status" in new and len(new["yoy_months"]) == len(new["yoy_last3"])
        assert new["yoy_months_contiguous"] is not True or new["month_key_source"] != REAL.SRC_NONE
    assert n_exc < 20000


# ───────────────────────── Batch B 後:契約鍵不影響 C1–C3、透傳接線 ─────────────────────────
def test_c1_c3_unchanged_with_or_without_contract():
    """(原 test_c4_score_unchanged_with_or_without_contract;Batch B 起 C4 依契約評分,故只守 C1–C3 不變。)

    語意變更理由:Batch A 時 shortage_screener 不讀契約,『有/無契約鍵結果逐值相同』成立;Batch B 依 DEC-151
    讓 C4 讀契約(缺契約=UNDETERMINED 不得逐月加速),C4 分數本來就會因契約而不同 → 該斷言對 C4 失效。
    C1–C3 仍須與契約鍵無關。
    """
    from src.compute.screener.shortage_screener import score_shortage
    q = [{"label": f"2026Q{i}", "revenue": 1000, "gross_profit": 300, "cogs": 700,
          "contract_liab": 100 + i, "inventory": 200 - i} for i in range(1, 6)]
    for yoy in ([20.0, 30.0, 40.0], [20.0, None, 40.0], [20.0, 30.0, None], [None, 30.0, 40.0], []):
        base = {"stock_id": "9999", "name": "t", "is_finance": False, "quarters": q, "revenue_yoy_last3": yoy}
        c = REAL.compute_month_contract(mk(span("2025-01", "2026-09")), as_of=A(2026, 10, 15))
        with_c = {**base, REAL.MONTH_CONTRACT_KEY: c}
        a, b = score_shortage(base), score_shortage(with_c)
        assert (a.c1_contract_liab, a.c2_gross_margin, a.c3_inventory_days) == \
            (b.c1_contract_liab, b.c2_gross_margin, b.c3_inventory_days)


def test_candidate_pool_passes_contract_and_selection_unchanged():
    from src.services import shortage_screener_service as SVC
    rows = []
    for sid, mult in (("1101", 1.5), ("1102", 1.3), ("1103", 0.8)):
        for i, m in enumerate(span("2025-01", "2026-09")):
            y, mo = int(m[:4]), int(m[5:])
            rows.append({"stock_id": sid, "date": pd.Timestamp(y, mo, 1),
                         "revenue": 100.0 * (mult if y == 2026 else 1.0)})
    pool = SVC._candidate_pool(pd.DataFrame(rows), max_n=10)
    assert [c["stock_id"] for c in pool] == ["1101", "1102"]       # 1103 動能向下被濾掉:選股/排序不變
    for c in pool:
        con = c[REAL.MONTH_CONTRACT_KEY]
        assert con["contract_status"] == "OK" and con["month_key_source"] == REAL.SRC_DATE
        assert con["date_eligibility"] == REAL.ELIG_NOT_VERIFIED       # batch 路徑只有 date 欄 → NOT VERIFIED


def test_score_and_diagnose_threads_contract_into_ranker(monkeypatch):
    from src.services import shortage_screener_service as SVC
    seen = []
    monkeypatch.setattr(SVC, "fetch_quarterly_shortage_frame", lambda sid: [])
    monkeypatch.setattr(SVC, "rank_shortage", lambda stocks, include_na=True: seen.extend(stocks) or [])
    full = mk(span("2025-01", "2026-09"))
    monkeypatch.setattr(SVC, "fetch_monthly_revenue", lambda sid, months=18: full)
    monkeypatch.setattr(SVC, "_as_of_today", lambda: A(2026, 10, 15))
    SVC._score_and_diagnose([("1101", None), ("1102", [1.0, 2.0, 3.0]),
                             ("1103", [1.0, 2.0, 3.0], {"contract_status": "OK", "marker": 1})])
    by = {s["stock_id"]: s for s in seen}
    assert by["1101"][REAL.MONTH_CONTRACT_KEY]["yoy_target_months"] == ["2026-07", "2026-08", "2026-09"]
    assert by["1101"]["revenue_yoy_last3"] == compute_yoy_mom(full)["yoy_last3"]
    assert REAL.MONTH_CONTRACT_KEY not in by["1102"]                      # 舊輸入(2-tuple)不憑空附契約
    assert by["1103"][REAL.MONTH_CONTRACT_KEY]["marker"] == 1


def test_score_and_diagnose_single_fetch_failure_marks_fail_closed(monkeypatch):
    from src.services import shortage_screener_service as SVC
    seen = []
    monkeypatch.setattr(SVC, "fetch_quarterly_shortage_frame", lambda sid: [])
    monkeypatch.setattr(SVC, "rank_shortage", lambda stocks, include_na=True: seen.extend(stocks) or [])
    monkeypatch.setattr(SVC, "_with_status",
                        lambda fn, *a, **k: (fn(*a, **k), True) if fn is SVC.fetch_monthly_revenue else (fn(*a, **k), False))
    monkeypatch.setattr(SVC, "fetch_monthly_revenue", lambda sid, months=18: mk(span("2025-01", "2026-09")))
    monkeypatch.setattr(SVC, "_as_of_today", lambda: A(2026, 10, 15))
    SVC._score_and_diagnose([("1101", None)], failed=[])
    assert seen[0][REAL.MONTH_CONTRACT_KEY]["contract_status"] == REAL.STATUS_FAIL_CLOSED


def test_cli_build_stock_input_carries_contract(monkeypatch):
    spec = importlib.util.spec_from_file_location("_c4a_cli", REPO / "scripts/shortage_cli.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    full = mk(span("2025-01", "2026-09"))
    monkeypatch.setattr(cli, "fetch_quarterly_shortage_frame", lambda sid: [])
    monkeypatch.setattr(cli, "fetch_monthly_revenue", lambda sid, months=18: full)
    out = cli.build_stock_input("2330")
    assert out["revenue_yoy_last3"] == compute_yoy_mom(full)["yoy_last3"]
    assert out[cli.MONTH_CONTRACT_KEY]["contract_status"] == "OK"
    assert out[cli.MONTH_CONTRACT_KEY]["as_of"] is not None
    fin = cli.build_stock_input("2880")
    assert cli.MONTH_CONTRACT_KEY not in fin                                # 金融股提前返回,輸入形狀不變
