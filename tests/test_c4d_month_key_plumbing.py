"""tests/test_c4d_month_key_plumbing.py — DEC-152 C4-D:revenue_year／revenue_month 月份鍵 plumbing(additive、回溯相容)。

客戶 2026-11-08 裁示(DEC-152):FinMind TaiwanStockMonthRevenue 已提供 revenue_year／revenue_month,date 與營收所屬月份
可能不同,不要直接信任 date;優先傳遞來源提供的月份鍵、最小 schema 擴充、不憑空補月份;**真實資料驗證前不得宣稱全市場
STRONG 已恢復**;不新增權重／門檻／封頂／排名例外。

守衛的事:
  ① L1 `_batch_finmind`:來源有 revenue_year/month → 多帶這兩欄(原值,不被 date 覆寫);來源沒有 → 不帶(不由 date 推導);
     只有單欄 → 不帶;NaN 不丟列;舊快取形狀(無兩欄)下游行為不變;
  ② 契約:以 revenue_year/month 為月份鍵;date≠營收月份(系統性差月)**不** FAIL_CLOSED;但缺月位置保留、重複/亂序/
     不可解析/上游失敗仍 FAIL_CLOSED;真 0% 與缺值可區分;
  ③ 護欄:全市場批次路徑(`source_month_key_verified=False`)公告時點資格維持 NOT VERIFIED(None)→ STRONG 恆 0;
     單股路徑(date 逐列與 ym 一致)行為不退步;
  ④ 真突變(改寫被測碼 → 檢查轉紅):由 date 推導補欄 / 護欄移除 / date≠ym 一律 FAIL_CLOSED / L3 不傳護欄旗標。
全部合成資料,零網路。本檔不釘檔案 sha。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shared import monthly_revenue_month_key as SSOT  # noqa: E402
from shared.shortage_screen_thresholds import SHORTAGE_REV_STRONG_SCORE  # noqa: E402
from src.compute.health import monthly_revenue_month_contract as MC  # noqa: E402
from src.compute.health.monthly_revenue_calc import compute_yoy_mom  # noqa: E402
from src.compute.screener import shortage_screener as SS  # noqa: E402
from src.data.stock import monthly_revenue_fetcher as MR  # noqa: E402
from src.services import shortage_screener_service as SVC  # noqa: E402

A = dt.date
ASOF = A(2026, 10, 15)          # 目標月 2026-07/08/09
STRONG = SHORTAGE_REV_STRONG_SCORE


# ───────────────────────── 輔助 ─────────────────────────
def _load(src: str, name: str, file: str) -> types.ModuleType:
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = file
    sys.modules[name] = m
    try:
        exec(compile(src, file, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _mutant(mod, old: str, new: str, tag: str):
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"替換點不唯一或已不存在:{old!r}"
    return _load(src.replace(old, new), f"_c4d_mut_{tag}", mod.__file__)


def span(a, b):
    return [str(p) for p in pd.period_range(a, b, freq="M")]


def stock_df(yoys=(20.0, 30.0, 40.0), *, drop=(), date_shift=0, ym=True, drop_base=()):
    """單股 2025-01..2026-09;基期=100,目標月 7/8/9 = 100*(1+yoy)。date = 營收月 1 日 + date_shift 個月(模擬公布月)。"""
    rows = []
    tgt = {(2026, 7 + i): y for i, y in enumerate(yoys)}
    for p in pd.period_range("2025-01", "2026-09", freq="M"):
        lab = str(p)
        if lab in drop or lab in drop_base:
            continue
        rev = 100.0 * (1.0 + tgt[(p.year, p.month)] / 100.0) if (p.year, p.month) in tgt else 100.0
        d = pd.Timestamp(p.year, p.month, 1) + pd.DateOffset(months=date_shift)
        row = {"date": d, "revenue": rev}
        if ym:
            row.update(revenue_year=p.year, revenue_month=p.month)
        rows.append(row)
    return pd.DataFrame(rows)


def batch_table(n=30, *, ym=True, date_shift=0, yoys=(20.0, 30.0, 40.0)):
    frames = []
    for i in range(n):
        d = stock_df(yoys, date_shift=date_shift, ym=ym)
        d.insert(0, "stock_id", f"{1100 + i}")
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def fm_raw(sids=("1101", "1102"), *, with_ym=True, shift=0, drop_cols=(), nan_ym_at=None):
    """模擬 FinMind 全市場原始回應(date 為字串;date 可比營收月晚 shift 個月)。"""
    frames = []
    for sid in sids:
        n = 19
        months = pd.period_range("2025-02", periods=n, freq="M")
        f = pd.DataFrame({
            "date": [(pd.Timestamp(p.year, p.month, 1) + pd.DateOffset(months=shift)).strftime("%Y-%m-%d") for p in months],
            "stock_id": sid,
            "revenue": [float(1000 + i * 50) for i in range(n)],
        })
        if with_ym:
            f["revenue_year"] = [p.year for p in months]
            f["revenue_month"] = [p.month for p in months]
        frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    for c in drop_cols:
        df = df.drop(columns=[c])
    if nan_ym_at is not None:
        df.loc[nan_ym_at, "revenue_month"] = float("nan")
    return df


def run_batch_finmind(mod, raw):
    """以假 finmind_get 跑 `_batch_finmind`(不動網路)。"""
    mod._get_token = lambda: "tok"
    mod.finmind_get = lambda *a, **k: raw.copy()
    return mod._batch_finmind(18)


# ───────────────────────── 檢查函式(參數化 module → 同時供正測與突變用) ─────────────────────────
def check_l1_carries_source_ym(M):
    out = run_batch_finmind(M, fm_raw(shift=1))      # date 比營收月晚 1 個月(公布月)
    assert list(out.columns) == ["stock_id", "date", "revenue", "revenue_year", "revenue_month"]
    first = out[out["stock_id"] == "1101"].iloc[0]
    assert (int(first["revenue_year"]), int(first["revenue_month"])) == (2025, 2)
    assert first["date"] == pd.Timestamp("2025-03-01"), "date 保持來源值,不被營收月覆寫"


def check_l1_does_not_fabricate_ym(M):
    out = run_batch_finmind(M, fm_raw(with_ym=False))
    assert list(out.columns) == ["stock_id", "date", "revenue"], "來源沒有月份鍵 → 不得由 date 推導出 revenue_year/month"
    assert "revenue_year" not in out.columns and "revenue_month" not in out.columns


def check_single_column_not_carried(M):
    out = run_batch_finmind(M, fm_raw(drop_cols=("revenue_month",)))
    assert list(out.columns) == ["stock_id", "date", "revenue"], "只有單欄無法構成月份鍵 → 不帶、不補"


def contract_ok_unverified_when_date_differs(M):
    c = M.compute_month_contract(stock_df(date_shift=1), as_of=ASOF)
    assert c["contract_status"] == "OK" and c["month_key_source"] == "revenue_year_month"
    assert c["month_key_source_fields"] == ["revenue_year", "revenue_month"] and c["month_key_date_agrees"] is False
    assert c["yoy_target_months"] == ["2026-07", "2026-08", "2026-09"] and c["yoy_months"] == c["yoy_target_months"]
    assert c["month_key_verified"] is False and c["target_date_eligible"] == [None] * 3
    assert M.ELIG_REASON_DATE_DIFFERS in c["date_eligibility_reasons"]
    assert [round(v) for v in c["yoy_target3"]] == [20, 30, 40]


def guard_blocks_eligibility(M):
    c = M.compute_month_contract(stock_df(), as_of=ASOF, source_month_key_verified=False)
    assert c["contract_status"] == "OK" and c["month_key_date_agrees"] is True
    assert c["month_key_verified"] is False and c["target_date_eligible"] == [None] * 3
    assert c["date_eligibility"] == M.ELIG_NOT_VERIFIED and M.ELIG_REASON_SOURCE_UNVERIFIED in c["date_eligibility_reasons"]
    c2 = M.compute_month_contract(stock_df(), as_of=ASOF)       # 單股預設路徑:修前行為
    assert c2["month_key_verified"] is True and c2["target_date_eligible"] == [True] * 3


# ───────────────────────── ① L1 ─────────────────────────
def test_l1_carries_source_ym():
    check_l1_carries_source_ym(MR)


def test_l1_no_fabrication_when_source_lacks_ym():
    check_l1_does_not_fabricate_ym(MR)
    check_single_column_not_carried(MR)


def test_l1_nan_ym_keeps_row_and_is_not_filled():
    out = run_batch_finmind(MR, fm_raw(nan_ym_at=3))
    assert len(out) == 38 and out["revenue_month"].isna().sum() == 1, "NaN 月份鍵不丟列、不補值"
    assert out["revenue_year"].notna().all()


def test_old_cache_shape_without_ym_still_works_downstream():
    """舊快取(無 revenue_year/month 的 stock_id/date/revenue)→ 候選池照舊產生契約(date-only,NOT VERIFIED)。"""
    old = batch_table(5, ym=False)
    assert list(old.columns) == ["stock_id", "date", "revenue"]
    SVC_asof = SVC._as_of_today
    SVC._as_of_today = lambda: ASOF
    try:
        pool = SVC._candidate_pool(old, max_n=10)
    finally:
        SVC._as_of_today = SVC_asof
    assert pool, "舊形狀仍有候選池"
    for c in pool:
        mc = c[MC.MONTH_CONTRACT_KEY]
        assert mc["month_key_source"] == "date_column" and mc["month_key_source_fields"] == ["date"]
        assert mc["month_key_verified"] is False and mc["target_date_eligible"] == [None] * 3


# ───────────────────────── ② 契約 ─────────────────────────
def test_date_differs_from_ym_is_not_fail_closed():
    contract_ok_unverified_when_date_differs(MC)


def partial_disagreement_not_verified(M):
    df = stock_df()                                            # date 與 ym 逐列一致
    df.loc[df.index[5], "date"] = df.loc[df.index[5], "date"] + pd.DateOffset(months=1)   # 只有 1 列不一致
    c = M.compute_month_contract(df, as_of=ASOF)
    assert c["contract_status"] == "OK" and c["month_key_date_agrees"] is False
    assert c["month_key_verified"] is False and c["target_date_eligible"] == [None] * 3


def test_partial_row_disagreement_is_not_agree_nor_verified():
    partial_disagreement_not_verified(MC)


def test_mutation_agrees_all_to_any_turns_red():
    """M8:逐列『全部一致』被改成『任一列一致』→ 部分列不一致會被誤判已驗證。"""
    src = pathlib.Path(MC.__file__).read_text(encoding="utf-8")
    old = "_agrees = (all(d is not None and k is not None and d == k"
    assert src.count(old) == 1
    mut = _load(src.replace(old, "_agrees = (any(d is not None and k is not None and d == k"), "_c4d_mut_m8", MC.__file__)
    with pytest.raises(AssertionError):
        partial_disagreement_not_verified(mut)


def test_irregular_date_vs_ym_offsets_still_use_ym_key():
    df = stock_df(date_shift=1)
    df.loc[df.index[-1], "date"] = pd.Timestamp("2026-10-10")        # 公布日落在不同日,仍同為『公布月』序
    c = MC.compute_month_contract(df, as_of=ASOF)
    assert c["contract_status"] == "OK" and c["yoy_months"][-1] == "2026-09"


def test_missing_month_keeps_position_with_source_ym():
    c = MC.compute_month_contract(stock_df(drop=("2026-08",), date_shift=1), as_of=ASOF)
    assert c["contract_status"] == "OK"
    assert c["yoy_target3"][1] is None and c["yoy_missing_reasons"][1] == MC.MONTH_REASON_NO_OBSERVATION
    assert c["target_observed"] == [True, False, True] and c["yoy_target3"][0] is not None
    assert c["yoy_months_contiguous"] is False     # 舊 yoy_last3 那 3 列是 7、9 與更早的 6 月 → 不連續


def test_missing_base_and_true_zero_distinguished():
    c = MC.compute_month_contract(stock_df(yoys=(0.0, 30.0, 40.0), drop_base=("2025-09",)), as_of=ASOF)
    assert c["yoy_target3"][0] == 0.0 and c["target_yoy_computable"][0] is True       # 真 0% 是有效值
    assert c["yoy_target3"][2] is None and c["yoy_missing_reasons"][2] == MC.MONTH_REASON_MISSING_BASE


@pytest.mark.parametrize("mutate,reason", [
    (lambda d: pd.concat([d, d.iloc[[5]]], ignore_index=True), MC.FAIL_DUPLICATE_MONTH),
    (lambda d: d.iloc[::-1].reset_index(drop=True), MC.FAIL_MONTH_ORDER),
    (lambda d: d.assign(revenue_month=d["revenue_month"].where(d.index != 3, float("nan"))), MC.FAIL_MONTH_UNPARSEABLE),
    (lambda d: d.assign(revenue_month=d["revenue_month"].where(d.index != 3, 13)), MC.FAIL_MONTH_UNPARSEABLE),
    (lambda d: d.assign(date=d["date"].where(d.index != 3, pd.NaT)), MC.FAIL_MONTH_UNPARSEABLE),
])
def test_bad_keys_still_fail_closed_even_with_shifted_date(mutate, reason):
    c = MC.compute_month_contract(mutate(stock_df(date_shift=1)), as_of=ASOF)
    assert c["contract_status"] == MC.STATUS_FAIL_CLOSED and reason in c["contract_fail_reasons"]
    assert c["yoy_target3"] == [None] * 3 and c["target_date_eligible"] == [None] * 3


def test_upstream_failure_fail_closed_regardless_of_key_columns():
    c = MC.compute_month_contract(stock_df(), as_of=ASOF, upstream_failed=True, source_month_key_verified=False)
    assert c["contract_status"] == MC.STATUS_FAIL_CLOSED and MC.FAIL_UPSTREAM in c["contract_fail_reasons"]
    m = MC.mark_upstream_failed(MC.compute_month_contract(stock_df(), as_of=ASOF))
    assert m["contract_status"] == MC.STATUS_FAIL_CLOSED and m["target_date_eligible"] == [None] * 3


def test_date_only_never_gets_ym_fields():
    c = MC.compute_month_contract(stock_df(ym=False), as_of=ASOF)
    assert c["month_key_source"] == "date_column" and c["month_key_source_fields"] == ["date"]
    assert c["month_key_date_agrees"] is None and c["target_date_eligible"] == [None] * 3


def test_legacy_fields_unchanged_by_ym_columns():
    """舊欄位(yoy_last3 等)與是否帶 revenue_year/month 無關。"""
    a = compute_yoy_mom(stock_df(ym=False, date_shift=1), as_of=ASOF)
    b = compute_yoy_mom(stock_df(ym=True, date_shift=1), as_of=ASOF)
    for k in ("last_date", "last_revenue", "yoy_last3", "mom_last", "months_available"):
        assert a[k] == b[k], k


# ───────────────────────── ③ 護欄:全市場 STRONG 維持 0;單股不退步 ─────────────────────────
def _pool(table, mod=SVC):
    old = mod._as_of_today
    mod._as_of_today = lambda: ASOF
    try:
        return mod._candidate_pool(table, max_n=1000)
    finally:
        mod._as_of_today = old


def _c4_score(pool_item):
    return SS._score_revenue_yoy(pool_item["revenue_yoy_last3"], pool_item[MC.MONTH_CONTRACT_KEY])[0]


def check_market_path_has_no_strong(mod=SVC):
    for shift in (0, 1):       # date == 營收月 與 date = 公布月 兩種來源形狀
        pool = _pool(batch_table(40, ym=True, date_shift=shift), mod)
        assert len(pool) == 40, "非空池(避免空洞通過)"
        scores = [_c4_score(c) for c in pool]
        assert STRONG not in scores, f"全市場路徑不得在未驗證下出現 STRONG(shift={shift})"
        for c in pool:
            mc = c[MC.MONTH_CONTRACT_KEY]
            assert mc["month_key_verified"] is False and mc["target_date_eligible"] == [None] * 3


def test_market_path_strong_stays_zero():
    check_market_path_has_no_strong()


def test_single_path_control_still_reaches_strong():
    """對照組:同一份資料走單股預設路徑(date 逐列與 ym 一致)仍可 STRONG —— 證明上面的 0 是護欄造成、單股不退步。"""
    st = compute_yoy_mom(stock_df(), as_of=ASOF)
    c = MC.extract_month_contract(st)
    assert c["month_key_verified"] is True and c["target_date_eligible"] == [True] * 3
    assert SS._score_revenue_yoy(st["yoy_last3"], c)[0] == STRONG


def test_single_path_shifted_date_no_longer_fail_closed_but_not_strong():
    """單股路徑若 date≠營收月(FinMind 真實形狀):修前 FAIL_CLOSED(資料不足);現在以 ym 為鍵、仍不 STRONG(未驗證)。"""
    st = compute_yoy_mom(stock_df(date_shift=1), as_of=ASOF)
    score = SS._score_revenue_yoy(st["yoy_last3"], MC.extract_month_contract(st))[0]
    assert st["contract_status"] == "OK" and score != STRONG


def test_ssot_flag_is_false_and_service_wires_it():
    assert SSOT.BATCH_SOURCE_MONTH_KEY_VERIFIED is False
    src = pathlib.Path(SVC.__file__).read_text(encoding="utf-8")
    assert "source_month_key_verified=BATCH_SOURCE_MONTH_KEY_VERIFIED" in src


def test_no_new_scoring_surface():
    """不新增權重/門檻/封頂:C4 分數只可能是既有常數集合。"""
    from shared import shortage_screen_thresholds as T
    allowed = {0.0, T.SHORTAGE_REV_PARTIAL_SCORE, T.SHORTAGE_REV_STEADY_SCORE, T.SHORTAGE_REV_STRONG_SCORE}
    for shift in (0, 1):
        for c in _pool(batch_table(10, date_shift=shift)):
            assert _c4_score(c) in allowed


# ───────────────────────── ④ 真突變 ─────────────────────────
def test_mutation_l1_fabricates_ym_from_date_turns_red():
    mut = _mutant(MR, '        _result_b = _df[_cols_b].sort_values(',
                  '        if "revenue_year" not in _df.columns:\n'
                  '            _df["revenue_year"] = _df["date"].dt.year\n'
                  '            _df["revenue_month"] = _df["date"].dt.month\n'
                  '            _cols_b += ["revenue_year", "revenue_month"]\n'
                  '        _result_b = _df[_cols_b].sort_values(', "fab")
    with pytest.raises(AssertionError):
        check_l1_does_not_fabricate_ym(mut)
    check_l1_carries_source_ym(mut)        # 該突變不破壞正向行為 → 只有『不憑空補月份』這條偵測得到它


def test_mutation_guard_removed_turns_red():
    mut = _mutant(MC, "    _verified = _verified and source_trusted\n", "    pass\n", "noguard")
    with pytest.raises(AssertionError):
        guard_blocks_eligibility(mut)


def test_mutation_date_ne_ym_always_fail_closed_turns_red():
    mut = _mutant(MC, "        _verified = not _fails and _agrees is not False\n",
                  "        if _agrees is False:\n            _fails.append('date_vs_revenue_ym_conflict')\n"
                  "        _verified = not _fails and _agrees is not False\n", "conflict")
    with pytest.raises(AssertionError):
        contract_ok_unverified_when_date_differs(mut)


def test_mutation_service_drops_guard_flag_turns_red():
    mut = _mutant(SVC, "source_month_key_verified=BATCH_SOURCE_MONTH_KEY_VERIFIED", "source_month_key_verified=True", "svc")
    with pytest.raises(AssertionError):
        check_market_path_has_no_strong(mut)


def test_mutation_ssot_flag_true_turns_red():
    mut = _mutant(SVC, "source_month_key_verified=BATCH_SOURCE_MONTH_KEY_VERIFIED",
                  "source_month_key_verified=not BATCH_SOURCE_MONTH_KEY_VERIFIED", "ssot")
    with pytest.raises(AssertionError):
        check_market_path_has_no_strong(mut)
