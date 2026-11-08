"""tests/test_c4b_revenue_scoring.py — DEC-151 Batch B:C4(月營收 YoY 逐月加速)依『月份資料契約』評分。

客戶 2026-11-08 裁示(DEC-151):C4 採最近三個完整且到公告時點的日曆月、可信月份鍵、保留缺值位置;
不連續不得判逐月加速,可依既有部分達標規則評分但不得虛構證據。
修前 bug:`valid=[非 None]` 壓縮缺值 → `[20,None,40]` 被當連續兩月而給『逐月加速』20 分。

守衛的事(逐條對應客戶要求):
  ① 缺中間/首/末月、缺基期、跳月(差 2 個月)→ 不得 STRONG/STEADY,依既有 PARTIAL/動能不足/資料不足,不補值不當 0;
  ② 跨年(12→01→02)連續判定正確;單月 fallback;真 0% / 負 YoY 與 missing(None)可區分;
  ③ 日期資格 None(NOT VERIFIED)/False → 禁 STRONG(其餘照既有規則);上游失敗 / FAIL_CLOSED → 資料不足且 c4_ok False;
     舊輸入無契約 → 禁 STRONG;
  ④ 正向:契約 OK + 3 月連續 + 皆 eligible + 嚴格遞增 → STRONG;STEADY / PARTIAL / 動能不足各一;
  ⑤ c4_ok 與 n_signals_ok / miss_reason 一致;C1–C3 不變;四項全缺仍 TIER_INSUFFICIENT;
  ⑥ 4 個真突變(改寫被測碼 → 檢查轉紅):壓縮 None / 忽略日期資格 / 缺月仍給 STEADY / 忽略 FAIL_CLOSED。
本檔不釘任何檔案 sha。全部合成資料,零網路。
"""
from __future__ import annotations

import datetime as dt
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shared.shortage_screen_thresholds import (  # noqa: E402
    SHORTAGE_REV_PARTIAL_SCORE,
    SHORTAGE_REV_STEADY_SCORE,
    SHORTAGE_REV_STRONG_SCORE,
    SHORTAGE_REVENUE_YOY_MIN_PCT,
    TIER_INSUFFICIENT,
    TIER_STRONG,
)
from src.compute.health import monthly_revenue_month_contract as MC  # noqa: E402
from src.compute.health.monthly_revenue_calc import compute_yoy_mom  # noqa: E402
from src.compute.screener import shortage_screener as REAL  # noqa: E402
from tests.test_shortage_screener import _strong_quarters, _verified_contract  # noqa: E402

A = dt.date
STRONG, STEADY, PARTIAL = SHORTAGE_REV_STRONG_SCORE, SHORTAGE_REV_STEADY_SCORE, SHORTAGE_REV_PARTIAL_SCORE
_MIN = SHORTAGE_REVENUE_YOY_MIN_PCT
ASOF = A(2026, 10, 15)          # 目標月 = 2026-07 / 08 / 09(Batch A:月後 +10 天公告)


# ───────────────────────── 輔助 ─────────────────────────
def producer_df(yoys, *, drop_cur=(), drop_base=(), ym=True, end_year=2026, cur_months=(7, 8, 9)):
    """2025-01..(end_year, cur_months 末月) 的月營收表;基期(去年同月)=100,目標月 = 100*(1+yoy/100)。

    yoys[i] 為 None → 該目標月不放列(缺月)。drop_cur/drop_base:額外移除的 'YYYY-MM'。
    """
    rows = []
    tgt = {(end_year, m): y for m, y in zip(cur_months, yoys)}
    last = (end_year, cur_months[-1])
    for p in pd.period_range("2025-01", f"{last[0]}-{last[1]:02d}", freq="M"):
        key = (p.year, p.month)
        lab = str(p)
        if lab in drop_cur or lab in drop_base:
            continue
        if key in tgt:
            if tgt[key] is None:
                continue
            rev = 100.0 * (1.0 + tgt[key] / 100.0)
        else:
            rev = 100.0
        row = {"date": pd.Timestamp(p.year, p.month, 1), "revenue": rev}
        if ym:
            row.update(revenue_year=p.year, revenue_month=p.month)
        rows.append(row)
    return pd.DataFrame(rows)


def real_inputs(df, as_of=ASOF, **kw):
    """月營收表 → (legacy yoy_last3, 契約) —— 與 L3 service 一樣走 compute_yoy_mom + extract_month_contract。"""
    stats = compute_yoy_mom(df, as_of=as_of, **kw)
    return stats["yoy_last3"], MC.extract_month_contract(stats)


def stock(yoy3, contract=None, *, quarters=None, sid="2330"):
    s = {"stock_id": sid, "name": "t", "is_finance": False,
         "quarters": quarters if quarters is not None else _strong_quarters(), "revenue_yoy_last3": yoy3}
    if contract is not None:
        s[MC.MONTH_CONTRACT_KEY] = contract
    return s


def c4(M, yoy3, contract=None):
    r = M.score_shortage(stock(yoy3, contract))
    return r


def c4_from_df(M, df, **kw):
    y3, con = real_inputs(df, **kw)
    return M.score_shortage(stock(y3, con))


def hand(yoy3, **kw):
    """手建契約(OK、3 目標月連續、資格已驗證),可覆寫欄位。"""
    c = _verified_contract(yoy3)
    c.update(kw)
    return c


# ───────────────────────── 檢查函式(對 module 參數化 → 同時供正測與突變用) ─────────────────────────
def check_gap_middle_not_strong_or_steady(M):
    """[20,None,40]:缺中間月(契約確認 2026-08 無列)→ 不得 STRONG/STEADY;只有 2 個有效月且 >門檻 → 既有 PARTIAL。"""
    r = c4_from_df(M, producer_df([20.0, None, 40.0]))
    assert r.metrics["rev_yoy_scored"][1] is None, "缺值位置必須保留為 None,不得壓縮"
    assert r.c4_revenue_yoy == PARTIAL, r.reasons
    assert r.c4_ok is True
    assert all("逐月加速" not in x for x in r.reasons)
    assert "缺" in r.reason_text


def check_date_eligibility_blocks_strong(M):
    """日期資格 None(NOT VERIFIED,date-only 月份鍵)→ 禁 STRONG;DEC-153 起連 STEADY 也禁,最高既有 PARTIAL(5)。
    資格 False(未到公告時點)→ 該月值視為缺值(見 check_not_yet_due_is_missing)。"""
    y = [16.0, 18.0, 22.0]
    for elig in ([None, None, None], [True, None, True]):
        r = c4(M, y, hand(y, target_date_eligible=elig))
        assert r.c4_revenue_yoy == PARTIAL and r.c4_revenue_yoy not in (STRONG, STEADY), (elig, r.reasons)
        assert all("逐月加速" not in x for x in r.reasons)
    check_not_yet_due_is_missing(M)


def check_not_yet_due_is_missing(M):
    """target_date_eligible=False 的月:值比照 observed=False 視為缺值,不計入 YoY、走缺月分支(不得 STEADY/STRONG)。"""
    y = [20.0, 30.0, 40.0]
    r = c4(M, y, hand(y, target_date_eligible=[True, True, False]))
    assert r.metrics["rev_yoy_scored"] == [20.0, 30.0, None], r.metrics["rev_yoy_scored"]
    assert r.metrics["rev_missing_reasons"][2] == MC.MONTH_REASON_NOT_YET_DUE
    assert r.c4_revenue_yoy == PARTIAL and r.c4_ok is True, r.reasons
    assert "缺" in r.reason_text
    r2 = c4(M, y, hand(y, target_date_eligible=[False, False, True]))     # 只剩 1 個有效月 → 資料不足
    assert r2.c4_ok is False and r2.c4_revenue_yoy == 0.0
    r3 = c4(M, y, hand(y, target_date_eligible=[False, False, False]))
    assert r3.c4_ok is False and r3.c4_revenue_yoy == 0.0


def check_gap_never_steady(M):
    """缺月、其餘兩月皆>門檻 → 只能 PARTIAL(5),不得 STEADY(12)。"""
    r = c4(M, [None, 30.0, 40.0], hand([None, 30.0, 40.0]))
    assert r.c4_revenue_yoy == PARTIAL, r.reasons


def check_fail_closed_is_insufficient(M):
    """契約 FAIL_CLOSED → 即使舊欄位有漂亮的值也 0 分且 c4_ok False(不是真 0 分)。"""
    con = MC.mark_upstream_failed(hand([20.0, 30.0, 40.0]))
    r = c4(M, [20.0, 30.0, 40.0], con)
    assert r.c4_revenue_yoy == 0.0 and r.c4_ok is False
    assert "FAIL_CLOSED" in r.miss_reason


def check_flag_none_not_observed(M):
    y = [16.0, 18.0, 22.0]
    for flag in ("target_observed", "target_base_valid", "target_yoy_computable"):
        r = c4(M, y, hand(y, **{flag: [None, True, True]}))
        assert r.metrics["rev_yoy_scored"][0] is None and r.c4_revenue_yoy == PARTIAL


def check_legacy_contiguity_none(M):
    assert c4(M, [16.0, 18.0, 22.0]).metrics["rev_contiguous"] is None
    assert c4(M, [16.0, 18.0, 22.0]).c4_revenue_yoy == PARTIAL


def check_future_row_not_blocking(M):
    y3, con = real_inputs(_with_future_jump_row([16.0, 18.0, 22.0]))
    assert M.score_shortage(stock(y3, con)).c4_revenue_yoy == STRONG


# ───────────────────────── 缺月 / 不連續 ─────────────────────────
@pytest.mark.parametrize("yoys,exp_missing", [
    ([20.0, None, 40.0], 1),      # 缺中間
    ([None, 30.0, 40.0], 0),      # 缺首月
    ([20.0, 30.0, None], 2),      # 缺末月
])
def test_missing_target_month_never_strong_or_steady(yoys, exp_missing):
    r = c4_from_df(REAL, producer_df(yoys))
    assert r.c4_revenue_yoy == PARTIAL
    assert r.c4_ok is True and r.c4_revenue_yoy not in (STRONG, STEADY)
    assert r.metrics["rev_yoy_scored"][exp_missing] is None
    assert r.metrics["rev_missing_reasons"][exp_missing] == MC.MONTH_REASON_NO_OBSERVATION
    assert all("逐月加速" not in x for x in r.reasons)
    # 缺月位置須出現在理由裡(不得沉默)
    assert r.metrics["rev_target_months"][exp_missing] in r.reason_text


def test_gap_middle_and_checks_on_real():
    check_gap_middle_not_strong_or_steady(REAL)
    check_gap_never_steady(REAL)


def test_missing_base_month_is_missing_not_zero():
    """缺基期(2025-08):該月 YoY 不可算 → None(原因 missing_base),不是 0%,且不得 STEADY/STRONG。"""
    r = c4_from_df(REAL, producer_df([20.0, 30.0, 40.0], drop_base={"2025-08"}))
    assert r.metrics["rev_yoy_scored"] == [pytest.approx(20.0), None, pytest.approx(40.0)]
    assert r.metrics["rev_missing_reasons"][1] == MC.MONTH_REASON_MISSING_BASE
    assert r.c4_revenue_yoy == PARTIAL and r.c4_ok is True


def test_two_yoy_present_but_two_months_apart():
    """只有 07 與 09 有 YoY(08 無列):兩個值『一前一後』但月份差 2 個月 → 不是連續,不可 STEADY/STRONG。

    舊欄位 yoy_last3 取最後 3 列 = [06,07,09] 三個值(修前會被當連續三月)——契約須證明它不連續。
    """
    df = producer_df([20.0, None, 40.0])
    y3, con = real_inputs(df)
    assert all(v is not None for v in y3), "舊 yoy_last3 在此情境三個位置都有值(壓縮後長得像連續三月)"
    assert con["yoy_months_contiguous"] is False
    r = REAL.score_shortage(stock(y3, con))
    assert r.c4_revenue_yoy not in (STRONG, STEADY)
    assert r.c4_revenue_yoy == PARTIAL


def test_cross_year_contiguous_is_strong():
    """as_of 2027-02-15 → 目標月 2026-11 / 12 / 2027-01(跨年):連續 + 驗證 + 遞增 → STRONG。"""
    rows = []
    tgt = {"2026-11": 16.0, "2026-12": 18.0, "2027-01": 22.0}
    for p in pd.period_range("2025-01", "2027-01", freq="M"):
        rev = 100.0 * (1 + tgt[str(p)] / 100) if str(p) in tgt else 100.0
        rows.append({"date": pd.Timestamp(p.year, p.month, 1), "revenue": rev,
                     "revenue_year": p.year, "revenue_month": p.month})
    df = pd.DataFrame(rows)
    y3, con = real_inputs(df, as_of=A(2027, 2, 15))
    assert con["yoy_target_months"] == ["2026-11", "2026-12", "2027-01"]
    r = REAL.score_shortage(stock(y3, con))
    assert r.c4_revenue_yoy == STRONG and r.c4_ok is True


def test_cross_year_gap_is_not_contiguous():
    """跨年缺 2026-12:不得因為『12→01 數字相差不大』而當連續。"""
    rows = []
    tgt = {"2026-11": 16.0, "2027-01": 22.0}
    for p in pd.period_range("2025-01", "2027-01", freq="M"):
        if str(p) == "2026-12":
            continue
        rev = 100.0 * (1 + tgt[str(p)] / 100) if str(p) in tgt else 100.0
        rows.append({"date": pd.Timestamp(p.year, p.month, 1), "revenue": rev,
                     "revenue_year": p.year, "revenue_month": p.month})
    r = c4_from_df(REAL, pd.DataFrame(rows), as_of=A(2027, 2, 15))
    assert r.c4_revenue_yoy == PARTIAL and r.metrics["rev_yoy_scored"][1] is None


def test_single_month_fallback_is_insufficient_not_zero():
    """單月(例 OpenAPI 只有當月一列)→ 有效月 <2 → 資料不足,c4_ok False,不是 0 分的『動能不足』。"""
    df = pd.DataFrame([{"date": pd.Timestamp(2026, 9, 1), "revenue": 120.0,
                        "revenue_year": 2026, "revenue_month": 9}])
    r = c4_from_df(REAL, df)
    assert r.c4_revenue_yoy == 0.0 and r.c4_ok is False
    assert "④" in r.miss_reason
    assert all("動能不足" not in x for x in r.reasons)


# ───────────────────────── 真 0% / 負 YoY vs missing ─────────────────────────
def test_true_zero_percent_differs_from_missing():
    """三月皆真 0%:有效值 → c4_ok True、『動能不足』(合法的真 0 分);三月皆缺:資料不足 c4_ok False。"""
    zero = c4_from_df(REAL, producer_df([0.0, 0.0, 0.0]))
    miss = c4_from_df(REAL, producer_df([None, None, None]))
    assert zero.metrics["rev_yoy_scored"] == [0.0, 0.0, 0.0]
    assert zero.c4_ok is True and zero.c4_revenue_yoy == 0.0 and any("動能不足" in x for x in zero.reasons)
    assert miss.c4_ok is False and miss.c4_revenue_yoy == 0.0 and any("資料不足" in x for x in miss.reasons)


def test_zero_with_one_missing_is_not_treated_as_two_missing():
    """[0.0, None, 20.0]:0% 是有效值(2 個有效月)→ 有 >門檻者 → PARTIAL;[None,None,20.0] 才是資料不足。"""
    a = c4_from_df(REAL, producer_df([0.0, None, 20.0]))
    b = c4_from_df(REAL, producer_df([None, None, 20.0]))
    assert a.c4_ok is True and a.c4_revenue_yoy == PARTIAL
    assert b.c4_ok is False and b.c4_revenue_yoy == 0.0


def test_negative_yoy_is_valid_value_and_weak():
    r = c4_from_df(REAL, producer_df([-5.0, -3.0, -8.0]))
    assert r.c4_ok is True and r.c4_revenue_yoy == 0.0
    assert any("動能不足" in x for x in r.reasons)
    r2 = c4_from_df(REAL, producer_df([-5.0, None, -8.0]))      # 缺月 + 皆≤門檻 → 動能不足(有效月 2)
    assert r2.c4_ok is True and r2.c4_revenue_yoy == 0.0 and any("動能不足" in x for x in r2.reasons)


# ───────────────────────── 日期資格 / 上游失敗 / 舊輸入 ─────────────────────────
def test_date_eligibility_none_and_false_block_strong():
    check_date_eligibility_blocks_strong(REAL)


def test_date_only_month_key_blocks_strong_end_to_end():
    """全市場路徑(batch 只有 date 欄,月份語意 NOT VERIFIED)→ eligible 全 None → 即使遞增也只 PARTIAL(DEC-153)。"""
    r = c4_from_df(REAL, producer_df([16.0, 18.0, 22.0], ym=False))
    assert r.metrics["rev_date_eligible"] == [None, None, None]
    assert r.c4_revenue_yoy == PARTIAL and r.c4_ok is True
    assert "NOT VERIFIED" in r.reason_text
    assert "rev_strong_blocked_by" in r.metrics and r.metrics["rev_strong_blocked_by"]


def test_upstream_failure_is_insufficient_and_c4_not_ok():
    df = producer_df([20.0, 30.0, 40.0])
    stats = compute_yoy_mom(df, as_of=ASOF, upstream_failed=True)
    con = MC.extract_month_contract(stats)
    assert con["contract_status"] == MC.STATUS_FAIL_CLOSED
    r = REAL.score_shortage(stock([20.0, 30.0, 40.0], con))           # 舊欄位即使是好看的值
    assert r.c4_revenue_yoy == 0.0 and r.c4_ok is False and "FAIL_CLOSED" in r.miss_reason
    check_fail_closed_is_insufficient(REAL)


@pytest.mark.parametrize("mk_df", [
    lambda: pd.concat([producer_df([20.0, 30.0, 40.0]), producer_df([20.0, 30.0, 40.0]).iloc[[-1]]],
                      ignore_index=True),                               # 重複月
    lambda: producer_df([20.0, 30.0, 40.0]).iloc[::-1].reset_index(drop=True),   # 月序錯亂
])
def test_contract_fail_closed_inputs_give_insufficient(mk_df):
    y3, con = real_inputs(mk_df())
    assert con["contract_status"] == MC.STATUS_FAIL_CLOSED
    r = REAL.score_shortage(stock(y3, con))
    assert r.c4_revenue_yoy == 0.0 and r.c4_ok is False


def test_legacy_input_without_contract_never_strong():
    """舊輸入(只有 revenue_yoy_last3)= UNDETERMINED:[16,18,22] 修前 STRONG,現在最多 PARTIAL(連續性未驗證)。

    QA 修正(DEC-151 不得虛構證據):連續性未驗證 → 不得給 STEADY(三值也可能是跳月拼成)。
    """
    r = c4(REAL, [16.0, 18.0, 22.0])
    assert r.c4_revenue_yoy == PARTIAL and r.c4_ok is True
    assert all("逐月加速" not in x for x in r.reasons)
    assert "連續性未驗證" in r.reason_text
    assert r.metrics["rev_contiguous"] is None                 # UNDETERMINED 如實呈現 None,不得顯示 True
    assert c4(REAL, [30.0, 20.0, 25.0]).c4_revenue_yoy == PARTIAL      # 不遞增也一樣不給 STEADY
    w = c4(REAL, [5.0, 3.0, 1.0])
    assert w.c4_revenue_yoy == 0.0 and w.c4_ok is True and any("動能不足" in x for x in w.reasons)
    # 舊輸入有缺值位置:不壓縮
    r2 = c4(REAL, [20.0, None, 40.0])
    assert r2.c4_revenue_yoy == PARTIAL
    r3 = c4(REAL, [None, None, 20.0])
    assert r3.c4_ok is False and "④月營收有效月數<2" in r3.miss_reason     # 舊文案保留(無契約路徑)


def test_legacy_undetermined_contract_object_never_strong():
    r = c4(REAL, [16.0, 18.0, 22.0], MC.legacy_undetermined_contract())
    assert r.c4_revenue_yoy == PARTIAL and r.metrics["rev_contiguous"] is None
    assert "連續性未驗證" in r.reason_text


def test_contract_ok_but_as_of_missing_blocks_strong():
    """as_of 缺 → 目標月無法決定,公告時點 NOT VERIFIED → 不得 STRONG。"""
    df = producer_df([16.0, 18.0, 22.0])
    y3, con = real_inputs(df, as_of=None)
    assert con["yoy_target_months"] == [None] * 3
    r = REAL.score_shortage(stock(y3, con))
    assert r.c4_revenue_yoy == PARTIAL and "目標月未定" in r.reason_text


def test_value_present_but_flag_false_is_not_used():
    """契約自相矛盾(YoY 有值但 target_yoy_computable=False)→ fail-closed 不採用該值。"""
    y = [20.0, 30.0, 40.0]
    con = hand(y, target_yoy_computable=[True, False, True])
    r = c4(REAL, y, con)
    assert r.metrics["rev_yoy_scored"][1] is None
    assert r.c4_revenue_yoy == PARTIAL


# ───────────────────────── 正向:STRONG / STEADY / PARTIAL / 動能不足 ─────────────────────────
def test_positive_strong_end_to_end_with_real_producer():
    r = c4_from_df(REAL, producer_df([16.0, 18.0, 22.0]))
    assert r.c4_revenue_yoy == STRONG and r.c4_ok is True
    assert any("逐月加速" in x for x in r.reasons)
    assert r.metrics["rev_c4_basis"] == "target3" and r.metrics["rev_strong_blocked_by"] == []


def test_positive_strong_hand_built_all_flags():
    r = c4(REAL, [16.0, 18.0, 22.0], hand([16.0, 18.0, 22.0]))
    assert r.c4_revenue_yoy == STRONG


def test_steady_when_all_above_but_not_increasing():
    r = c4(REAL, [30.0, 20.0, 25.0], hand([30.0, 20.0, 25.0]))
    assert r.c4_revenue_yoy == STEADY and r.c4_ok is True
    assert r.metrics["rev_strong_blocked_by"] == []


def test_partial_when_some_above():
    r = c4(REAL, [20.0, 10.0, 5.0], hand([20.0, 10.0, 5.0]))
    assert r.c4_revenue_yoy == PARTIAL and r.c4_ok is True


def test_weak_when_none_above():
    r = c4(REAL, [5.0, 3.0, 1.0], hand([5.0, 3.0, 1.0]))
    assert r.c4_revenue_yoy == 0.0 and r.c4_ok is True and any("動能不足" in x for x in r.reasons)


def test_strictly_increasing_required_for_strong():
    r = c4(REAL, [18.0, 18.0, 22.0], hand([18.0, 18.0, 22.0]))
    assert r.c4_revenue_yoy == STEADY


def test_threshold_boundary_is_strict_greater():
    y = [_MIN, _MIN + 1, _MIN + 2]          # 第一個 == 門檻 → 非 >,不是皆 >
    r = c4(REAL, y, hand(y))
    assert r.c4_revenue_yoy == PARTIAL


# ───────────────────────── c4_ok 與 n_signals_ok / miss_reason 一致 ─────────────────────────
_CASES = [
    ([16.0, 18.0, 22.0], hand([16.0, 18.0, 22.0])),
    ([20.0, None, 40.0], hand([20.0, None, 40.0])),
    ([None, None, 20.0], hand([None, None, 20.0])),
    ([None, None, None], hand([None, None, None])),
    ([16.0, 18.0, 22.0], None),
    ([None, None, 20.0], None),
    ([20.0, 30.0, 40.0], MC.mark_upstream_failed(hand([20.0, 30.0, 40.0]))),
    ([16.0, 18.0, 22.0], hand([16.0, 18.0, 22.0], target_date_eligible=[None] * 3)),
    ([-5.0, -3.0, -8.0], hand([-5.0, -3.0, -8.0])),
    ([], None),
]


@pytest.mark.parametrize("y3,con", _CASES)
def test_c4_ok_consistent_with_flags_and_miss_reason(y3, con):
    r = c4(REAL, y3, con)
    flags = (r.c1_ok, r.c2_ok, r.c3_ok, r.c4_ok)
    assert r.n_signals_ok == sum(1 for f in flags if f)
    assert (r.c4_ok is False) == ("④" in r.miss_reason)
    # c4_ok False ⇔ C4 走資料不足分支 ⇔ 分數 0 且理由寫『資料不足』
    c4_reason = next(x for x in r.reasons if "月營收" in x)
    assert (r.c4_ok is False) == ("資料不足" in c4_reason)
    if r.c4_ok is False:
        assert r.c4_revenue_yoy == 0.0
    # 逐月加速只允許在契約 OK 且資格全 True
    if r.c4_revenue_yoy == STRONG:
        assert con is not None and con["contract_status"] == "OK" and all(e is True for e in con["target_date_eligible"])


def test_gap_miss_reason_is_honest_vs_legacy_text():
    r_gap = c4(REAL, [None, None, 20.0], hand([None, None, 20.0]))
    r_legacy = c4(REAL, [None, None, 20.0])
    assert "缺月/不連續" in r_gap.miss_reason and "有效月數<2" not in r_gap.miss_reason
    assert "有效月數<2" in r_legacy.miss_reason and "缺月" not in r_legacy.miss_reason


def test_metrics_additive_and_legacy_key_kept():
    r = c4(REAL, [20.0, None, 40.0], hand([20.0, None, 40.0]))
    assert r.metrics["rev_yoy_last3"] == [20.0, None, 40.0]            # 舊 key 保留(CLI 讀它)
    for k in ("rev_c4_contract_status", "rev_c4_basis", "rev_yoy_scored", "rev_target_months",
              "rev_missing_reasons", "rev_contiguous", "rev_date_eligible", "rev_strong_blocked_by"):
        assert k in r.metrics


# ───────────────────────── 回歸:C1–C3 / tier / 四項全缺 ─────────────────────────
def test_c1_c3_unchanged_by_contract():
    base = c4(REAL, [16.0, 18.0, 22.0], hand([16.0, 18.0, 22.0]))
    assert (base.c1_contract_liab, base.c2_gross_margin, base.c3_inventory_days) == (35.0, 25.0, 20.0)
    for y3, con in _CASES:
        r = c4(REAL, y3, con)
        assert (r.c1_contract_liab, r.c2_gross_margin, r.c3_inventory_days) == (35.0, 25.0, 20.0)
        assert r.total == r.c1_contract_liab + r.c2_gross_margin + r.c3_inventory_days + r.c4_revenue_yoy


def test_four_all_missing_still_insufficient():
    qs = _strong_quarters()
    for q in qs:
        q["contract_liab"] = q["gross_profit"] = q["inventory"] = None
    for y3, con in (([None] * 3, hand([None] * 3)), ([20.0, 30.0, 40.0], MC.mark_upstream_failed(hand([1.0] * 3))),
                    ([], None), ([None, None, 20.0], hand([None, None, 20.0]))):
        r = REAL.score_shortage(stock(y3, con, quarters=qs))
        assert r.n_signals_ok == 0 and r.tier == TIER_INSUFFICIENT, (y3, con and con["contract_status"])
    # 反例:C4 有效 → 不是四項全缺 → 仍在榜
    r = REAL.score_shortage(stock([20.0, 30.0, 40.0], hand([20.0, 30.0, 40.0]), quarters=qs))
    assert r.n_signals_ok == 1 and r.tier != TIER_INSUFFICIENT


def test_golden_full_strong_still_strong_tier():
    r = c4(REAL, [16.0, 18.0, 22.0], hand([16.0, 18.0, 22.0]))
    assert r.total == 100.0 and r.tier == TIER_STRONG


def test_ranking_gap_stock_below_full_evidence_stock():
    a = stock([16.0, 18.0, 22.0], hand([16.0, 18.0, 22.0]), sid="1111")
    b = stock([16.0, None, 22.0], hand([16.0, None, 22.0]), sid="2222")
    ranked = REAL.rank_shortage([b, a])
    assert [x.stock_id for x in ranked] == ["1111", "2222"]
    assert ranked[0].total > ranked[1].total


def test_service_candidate_pool_market_path_cannot_reach_strong():
    """全市場路徑只有 date → eligible 全 None;即使營收逐月加速也不可能 STRONG(最多 STEADY)。"""
    from src.services import shortage_screener_service as SVC
    rows = []
    yoys = {7: 16.0, 8: 18.0, 9: 22.0}
    for p in pd.period_range("2025-01", "2026-09", freq="M"):
        rev = 100.0 * (1 + yoys[p.month] / 100) if (p.year == 2026 and p.month in yoys) else 100.0
        rows.append({"stock_id": "1101", "date": pd.Timestamp(p.year, p.month, 1), "revenue": rev})
    pool = SVC._candidate_pool(pd.DataFrame(rows), max_n=5)
    if not pool:                                    # classify_trend 未納入時不影響本測試主旨
        pytest.skip("候選池篩選未納入合成股")
    c = pool[0]
    r = REAL.score_shortage(stock(c["revenue_yoy_last3"], c[MC.MONTH_CONTRACT_KEY]))
    assert r.c4_revenue_yoy != STRONG


def test_malformed_contract_does_not_raise_and_never_strong():
    for bad in ({"contract_status": "OK"}, {"contract_status": "OK", "yoy_target_months": ["x", "y", "z"],
                                           "yoy_target3": "oops"}, {"contract_status": None}, "garbage", 5):
        r = c4(REAL, [16.0, 18.0, 22.0], bad)
        assert r.c4_revenue_yoy != STRONG


# ───────────────────────── QA 追加(非作者 QA 有條件通過後的修正) ─────────────────────────
def test_not_yet_due_month_is_missing_not_scored():
    check_not_yet_due_is_missing(REAL)


@pytest.mark.parametrize("flag", ["target_observed", "target_base_valid", "target_yoy_computable"])
def test_value_with_unverified_flag_is_not_observed(flag):
    """(M6)值存在但 observed/base_valid/computable 為 None(NOT VERIFIED)或 False → 不得被當作有效觀測。"""
    y = [16.0, 18.0, 22.0]
    for bad in (None, False):
        flags = [bad, True, True]
        r = c4(REAL, y, hand(y, **{flag: flags}))
        assert r.metrics["rev_yoy_scored"] == [None, 18.0, 22.0], (flag, bad)
        assert r.c4_revenue_yoy == PARTIAL, (flag, bad, r.reasons)      # 缺月分支,不得 STEADY/STRONG


def test_legacy_contiguity_is_reported_as_undetermined_none():
    """(M11)無契約 / UNDETERMINED 契約:rev_contiguous 必須如實為 None(不得顯示 True 或 False)。"""
    assert c4(REAL, [16.0, 18.0, 22.0]).metrics["rev_contiguous"] is None
    assert c4(REAL, [16.0, 18.0, 22.0], MC.legacy_undetermined_contract()).metrics["rev_contiguous"] is None
    und = dict(MC.legacy_undetermined_contract(), contract_fail_reasons=[MC.UND_NO_MONTH_INFO])
    assert c4(REAL, [16.0, 18.0, 22.0], und).metrics["rev_contiguous"] is None


def _with_future_jump_row(yoys, *, ym=True, drop=(), future_rev=999.0):
    """目標月(07-09)完整後再接一列『未到公告時點』的 2026-12(跳月未來列):舊 yoy_last3 取最後 3 列會含它。"""
    df = producer_df(yoys, drop_cur=drop, ym=ym)
    row = {"date": pd.Timestamp(2026, 12, 1), "revenue": future_rev}
    if ym:
        row.update(revenue_year=2026, revenue_month=12)
    return pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def test_target_contiguity_not_blocked_by_future_jump_row():
    """(M15)目標三月完整連續、資格已驗證,只因表尾有未到期的跳月未來列(舊 yoy_months_contiguous=False)
    → 仍應 STRONG(連續性看目標月自身);未來列的值不得影響評分。"""
    y3, con = real_inputs(_with_future_jump_row([16.0, 18.0, 22.0]))
    assert con["yoy_months_contiguous"] is False and con["excluded_not_yet_due_months"] == ["2026-12"]
    assert con["yoy_target_months"] == ["2026-07", "2026-08", "2026-09"]
    r = REAL.score_shortage(stock(y3, con))
    assert r.c4_revenue_yoy == STRONG and r.metrics["rev_contiguous"] is True
    r2 = REAL.score_shortage(stock(real_inputs(_with_future_jump_row([16.0, 18.0, 22.0], future_rev=1.0))[0],
                                   real_inputs(_with_future_jump_row([16.0, 18.0, 22.0], future_rev=1.0))[1]))
    assert r2.metrics["rev_yoy_scored"] == r.metrics["rev_yoy_scored"]       # 未來列值不同,評分輸入不變


def test_future_jump_row_does_not_launder_unverified_months():
    """反例:放寬連續性判斷不得放行未驗證/缺月/不連續的目標月。"""
    # (i) 目標月缺 08 + 未來跳月列 → 缺月分支(PARTIAL),不得 STRONG/STEADY
    r = c4_from_df(REAL, _with_future_jump_row([16.0, None, 22.0]))
    assert r.c4_revenue_yoy == PARTIAL
    # (ii) 月份鍵未驗證(date-only)+ 未來跳月列 → 資格 None,不得 STRONG
    r = c4_from_df(REAL, _with_future_jump_row([16.0, 18.0, 22.0], ym=False))
    assert r.c4_revenue_yoy == PARTIAL
    # (iii) 手建:目標月標籤不連續(即使舊欄位 contiguous=True 也不得放行)→ 缺位置語意不成立,不得 STRONG/STEADY
    y = [16.0, 18.0, 22.0]
    r = c4(REAL, y, hand(y, yoy_target_months=["2026-07", "2026-09", "2026-10"], yoy_months_contiguous=True))
    assert r.c4_revenue_yoy not in (STRONG, STEADY)
    # (iv) 手建:舊 yoy_months_contiguous=True、但某月資格 None → 仍不得 STRONG
    r = c4(REAL, y, hand(y, target_date_eligible=[True, None, True], yoy_months_contiguous=True))
    assert r.c4_revenue_yoy == PARTIAL


def test_cli_prints_scored_target3_with_missing_not_zero():
    import importlib.util as _iu
    spec = _iu.spec_from_file_location("_c4b_cli", REPO / "scripts/shortage_cli.py")
    cli = _iu.module_from_spec(spec)
    spec.loader.exec_module(cli)
    r = REAL.score_shortage(stock([16.0, 18.0, 22.0], hand([20.0, None, 40.0])))   # legacy 與 target3 故意不同
    txt = cli.format_score_report(r)
    assert "2026-07:+20.0%" in txt and "2026-08:缺" in txt and "2026-09:+40.0%" in txt
    assert "+16.0%" not in txt and "18.0" not in txt                       # 不印未被評分使用的舊 3 值
    assert "2026-08:+0.0%" not in txt and "2026-08:0" not in txt           # 缺值不得顯示成 0
    # 舊 ShortageScore(無 rev_yoy_scored)仍可印(退回舊欄位)
    legacy = r.__class__(**{**r.__dict__, "metrics": {"rev_yoy_last3": [16.0, None, 22.0]}})
    assert "缺" in cli.format_score_report(legacy)


# ───────────────────────── 突變(改寫被測碼,檢查必須轉紅) ─────────────────────────
def _load_mutant(old: str, new: str):
    src = (REPO / "src/compute/screener/shortage_screener.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變錨點必須在原檔恰出現 1 次:{old!r}(實得 {src.count(old)})"
    mod = types.ModuleType("_c4b_mutant")
    mod.__file__ = "<mutant>"
    sys.modules["_c4b_mutant"] = mod
    exec(compile(src.replace(old, new), "<mutant>", "exec"), mod.__dict__)
    return mod


MUTANTS = {
    # (a) 把 None 壓縮回去:缺月不再擋 3 位置分支(valid 變成只含非 None 的 2 個值)
    "compress_none": ("if n_missing == 0 and contiguous is True and not key_unverified:",
                      "if contiguous is True and not key_unverified:", check_gap_middle_not_strong_or_steady),
    # (b) 忽略 date_eligible:公告時點資格不再阻擋 STRONG
    "ignore_date_eligible": ("        if not all(e is True for e in elig):\n            key_unverified.append(",
                             "        if False:\n            key_unverified.append(",
                             check_date_eligibility_blocks_strong),
    # (c) 缺月仍給 STEADY:缺月分支改回傳 STEADY 分
    "gap_gets_steady": ("return _c4_result(SHORTAGE_REV_PARTIAL_SCORE,\n                          f\"🟡月營收 YoY 部分達標（{len(valid)}",
                        "return _c4_result(SHORTAGE_REV_STEADY_SCORE,\n                          f\"🟡月營收 YoY 部分達標（{len(valid)}",
                        check_gap_never_steady),
    # (e) 未到公告時點(資格 False)的月仍計入評分
    "not_yet_due_scored": ("elig[i] is not False) else None", "True) else None", check_not_yet_due_is_missing),
    # (f) 旗標 None 也當作觀測到(M6)
    "flag_none_as_observed": ("vals = [raw3[i] if (all(f[i] is True for f in flags)",
                              "vals = [raw3[i] if (all(f[i] is not False for f in flags)", check_flag_none_not_observed),
    # (g) legacy 路徑連續性顯示 True(M11)
    "legacy_contiguous_true": ("contiguous = c.get(\"yoy_months_contiguous\") if status == STATUS_OK else None",
                               "contiguous = c.get(\"yoy_months_contiguous\") if status == STATUS_OK else True",
                               check_legacy_contiguity_none),
    # (h) 回退到舊的『整表 yoy_months_contiguous』連續性判斷(M15)
    "strong_uses_legacy_contiguity": ("if contiguous is not True:      #", "if c.get(\"yoy_months_contiguous\") is not True:      #",
                                      check_future_row_not_blocking),
    # (d) 忽略 FAIL_CLOSED:契約失敗不再走資料不足
    "ignore_fail_closed": ("if status == STATUS_FAIL_CLOSED:", "if False:", check_fail_closed_is_insufficient),
}


@pytest.mark.parametrize("name", list(MUTANTS))
def test_mutant_is_killed(name):
    old, new, chk = MUTANTS[name]
    mut = _load_mutant(old, new)
    chk(REAL)                                   # 原碼綠
    with pytest.raises(AssertionError):         # 突變碼紅
        chk(mut)
