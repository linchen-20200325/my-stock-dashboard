"""tests/test_c4e_unverified_key_cap.py — DEC-153:月份鍵未驗證時 C4 不得取得 STEADY／STRONG。

客戶 2026-11-08 正式裁示(DEC-153):「未驗證 C4 年月鍵選 B:C4 不得取得 STEADY／STRONG,
僅在符合既有 PARTIAL 條件時最高 5 分。」

『未驗證』= 契約 month_key_verified 不為 True、或 target_date_eligible 非全 True、或 legacy／UNDETERMINED、
或 as_of 缺(目標月未定)。此時只可走既有分支:
  有效值≥2 且任一 > SHORTAGE_REVENUE_YOY_MIN_PCT → 既有 PARTIAL(5);有效值皆≤門檻 → 既有『動能不足』0;
  有效值<2 → 既有『資料不足』0 且 c4_ok=False(不得硬給 5 分);FAIL_CLOSED → 資料不足。
verified=True 且全部條件成立 → 行為不變(STEADY／STRONG 仍可)。

不是:所有缺值一律 5／一律 0、排除資料不完整股票、新百分位、分數重配、改 Risk Cap/PIT、改任何門檻或 C1–C3。

下游 before/after:用合成 fixture(⚠️ 不代表真實市場)量化 C4 分數轉移矩陣、tier、排名位移、前 50 名變動;
『before』= 同一份原始碼把 key_unverified 清空的突變體(= DEC-153 前行為,逐字等價於 c5846b7 的 C4 分支)。
本檔不釘任何檔案 sha;全部合成資料,零網路。
"""
from __future__ import annotations

import datetime as dt
import sys
import types
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shared.shortage_screen_thresholds import (  # noqa: E402
    SHORTAGE_REV_PARTIAL_SCORE as PARTIAL,
    SHORTAGE_REV_STEADY_SCORE as STEADY,
    SHORTAGE_REV_STRONG_SCORE as STRONG,
    SHORTAGE_REVENUE_YOY_MIN_PCT as MINP,
    TIER_INSUFFICIENT,
)
from src.compute.health import monthly_revenue_month_contract as MC  # noqa: E402
from src.compute.health.monthly_revenue_calc import compute_yoy_mom  # noqa: E402
from src.compute.screener import shortage_screener as REAL  # noqa: E402
from tests.test_shortage_screener import _q, _strong_quarters, _verified_contract  # noqa: E402

ASOF = dt.date(2026, 10, 15)           # 目標月 2026-07/08/09


# ───────────────────────── 輔助 ─────────────────────────
def mk_df(yoys, *, ym=True, date_shift=0, drop=(), drop_base=(), only=None):
    """2025-01..2026-09;基期 100,目標月 7/8/9 = 100*(1+yoy/100);yoy None → 該月不放列。
    only='year'/'month' → 只留單一明示欄(另一欄不存在)。"""
    tgt = {(2026, 7 + i): y for i, y in enumerate(yoys)}
    rows = []
    for p in pd.period_range("2025-01", "2026-09", freq="M"):
        lab = str(p)
        if lab in drop or lab in drop_base or ((p.year, p.month) in tgt and tgt[(p.year, p.month)] is None):
            continue
        rev = 100.0 * (1.0 + tgt[(p.year, p.month)] / 100.0) if (p.year, p.month) in tgt else 100.0
        row = {"date": pd.Timestamp(p.year, p.month, 1) + pd.DateOffset(months=date_shift), "revenue": rev}
        if ym and only in (None, "year"):
            row["revenue_year"] = p.year
        if ym and only in (None, "month"):
            row["revenue_month"] = p.month
        rows.append(row)
    return pd.DataFrame(rows)


def inputs(df, *, as_of=ASOF, **kw):
    st = compute_yoy_mom(df, as_of=as_of, **kw)
    return st["yoy_last3"], MC.extract_month_contract(st)


def stock(yoy3, contract=None, *, quarters=None, sid="2330"):
    s = {"stock_id": sid, "name": "t", "is_finance": False,
         "quarters": quarters if quarters is not None else _strong_quarters(), "revenue_yoy_last3": yoy3}
    if contract is not None:
        s[MC.MONTH_CONTRACT_KEY] = contract
    return s


def run(M, yoy3, contract=None, **kw):
    return M.score_shortage(stock(yoy3, contract, **kw))


def run_df(M, df, **kw):
    y3, con = inputs(df, **kw)
    return M.score_shortage(stock(y3, con))


def hand(yoy3, **kw):
    c = _verified_contract(yoy3)
    c.update(kw)
    return c


INC = [16.0, 18.0, 22.0]       # 嚴格遞增、皆 > 15
FLAT = [30.0, 20.0, 25.0]      # 皆 > 15 但非遞增 → 已驗證時 STEADY
LOW = [5.0, 3.0, 1.0]          # 皆 ≤ 15
MIX = [5.0, 30.0, 8.0]         # 任一 > 15


# ───────────────────────── 檢查函式(對 module 參數化 → 同時供正測與突變) ─────────────────────────
def check_verified_unchanged(M):
    """verified=True 連續完整:行為不變。"""
    assert run_df(M, mk_df(INC)).c4_revenue_yoy == STRONG
    assert run_df(M, mk_df(FLAT)).c4_revenue_yoy == STEADY
    assert run_df(M, mk_df(MIX)).c4_revenue_yoy == PARTIAL
    assert run_df(M, mk_df(LOW)).c4_revenue_yoy == 0.0
    for y in (INC, FLAT):
        r = run(M, y, hand(y))
        assert r.c4_revenue_yoy in (STRONG, STEADY) and r.metrics["rev_c4_key_unverified"] == []


def check_unverified_capped_at_partial(M):
    """未驗證 + 數字完整遞增/平穩 → 只可 PARTIAL(5),絕非 12/20;理由不得寫逐月加速/皆>x%。"""
    cases = []
    cases.append(run_df(M, mk_df(INC), source_month_key_verified=False))        # 全市場批次路徑
    cases.append(run_df(M, mk_df(FLAT), source_month_key_verified=False))
    cases.append(run_df(M, mk_df(INC, ym=False)))                               # date-only
    cases.append(run_df(M, mk_df(INC, date_shift=1)))                           # date≠ym(單股,FinMind 真實形狀)
    cases.append(run_df(M, mk_df(INC), as_of=None))                             # as_of 缺 → 目標月未定
    for r in cases:
        assert r.c4_revenue_yoy == PARTIAL and r.c4_ok is True, r.reasons
        assert r.c4_revenue_yoy not in (STEADY, STRONG)
        txt = r.reason_text
        assert "逐月加速" not in txt and "皆>" not in txt, txt
        assert "月份鍵未驗證" in txt or "目標月未定" in txt or "連續性未驗證" in txt, txt
        assert r.metrics["rev_c4_key_unverified"], "未驗證原因必須進 metrics"
        assert r.metrics["rev_strong_blocked_by"], "rev_strong_blocked_by 必須非空"


def check_hand_flag_unverified(M):
    """契約 month_key_verified=False(其餘欄位皆合格、資格全 True)→ 仍不得 STEADY/STRONG(單看 month_key_verified)。"""
    for y in (INC, FLAT):
        r = run(M, y, hand(y, month_key_verified=False))
        assert r.c4_revenue_yoy == PARTIAL, r.reasons
    # 資格 None / 部分 None / 部分 False(後者該月視為缺值)
    for elig in ([None, None, None], [True, None, True], [True, True, None]):
        r = run(M, INC, hand(INC, target_date_eligible=elig))
        assert r.c4_revenue_yoy == PARTIAL, (elig, r.reasons)


def check_unverified_low_is_momentum_zero(M):
    """未驗證 + 有效值皆≤門檻 → 既有『動能不足』0 分,c4_ok=True(不得被抬到 5)。"""
    for r in (run_df(M, mk_df(LOW), source_month_key_verified=False), run_df(M, mk_df(LOW, ym=False)),
              run(M, LOW, hand(LOW, month_key_verified=False))):
        assert r.c4_revenue_yoy == 0.0 and r.c4_ok is True, r.reasons
        assert any("動能不足" in x for x in r.reasons)


def check_unverified_insufficient_not_five(M):
    """未驗證 + 有效值<2 → 既有『資料不足』0 分且 c4_ok=False,不得硬給 5 分。"""
    for y in ([None, None, 20.0], [40.0, None, None], [None, None, None]):
        df = mk_df(y)
        for r in (run_df(M, df, source_month_key_verified=False), run_df(M, mk_df(y, ym=False))):
            assert r.c4_revenue_yoy == 0.0 and r.c4_ok is False, (y, r.reasons)
            assert "資料不足" in r.reason_text and "④" in r.miss_reason


# ───────────────────────── 正測 ─────────────────────────
def test_verified_continuous_complete_unchanged():
    check_verified_unchanged(REAL)


def test_unverified_numerically_complete_increasing_capped_at_5():
    check_unverified_capped_at_partial(REAL)


def test_hand_built_unverified_flags():
    check_hand_flag_unverified(REAL)


def test_unverified_all_below_threshold_is_zero_momentum():
    check_unverified_low_is_momentum_zero(REAL)


def test_unverified_insufficient_stays_insufficient():
    check_unverified_insufficient_not_five(REAL)


def test_date_ne_ym_single_path_capped():
    st = compute_yoy_mom(mk_df(INC, date_shift=1), as_of=ASOF)
    con = MC.extract_month_contract(st)
    assert con["contract_status"] == "OK" and con["month_key_verified"] is False
    assert REAL.score_shortage(stock(st["yoy_last3"], con)).c4_revenue_yoy == PARTIAL


@pytest.mark.parametrize("only", ["year", "month"])
def test_only_one_explicit_column_is_date_only_unverified(only):
    """只有 revenue_year 或只有 revenue_month 單欄 → 不算明示年月鍵(退回 date-only)→ 未驗證,最高 5。"""
    r = run_df(REAL, mk_df(INC, only=only))
    assert r.c4_revenue_yoy == PARTIAL and r.metrics["rev_c4_key_unverified"]


def test_missing_month_missing_base_existing_behaviour():
    # 缺月:已驗證 → 既有缺月 PARTIAL;未驗證 → 一樣最高 PARTIAL(且理由註明未驗證)
    r = run_df(REAL, mk_df([20.0, None, 40.0]))
    assert r.c4_revenue_yoy == PARTIAL and r.metrics["rev_c4_key_unverified"] == []
    r = run_df(REAL, mk_df([20.0, None, 40.0]), source_month_key_verified=False)
    assert r.c4_revenue_yoy == PARTIAL and "月份鍵未驗證" in r.reason_text and "缺" in r.reason_text
    # 缺基期:2025-08 不存在 → 2026-08 不可算
    r = run_df(REAL, mk_df(INC, drop_base=("2025-08",)))
    assert r.metrics["rev_yoy_scored"][1] is None and r.c4_revenue_yoy == PARTIAL
    r = run_df(REAL, mk_df(INC, drop_base=("2025-08",)), source_month_key_verified=False)
    assert r.metrics["rev_yoy_scored"][1] is None and r.c4_revenue_yoy == PARTIAL
    # 缺月造成有效<2 → 資料不足
    r = run_df(REAL, mk_df([None, None, 40.0]), source_month_key_verified=False)
    assert r.c4_ok is False and r.c4_revenue_yoy == 0.0


def test_true_zero_and_negative_are_valid_values_not_missing():
    for src_ok in (True, False):
        kw = {} if src_ok else {"source_month_key_verified": False}
        # 真 0%、負 YoY 皆為有效值:有效數 3 → 不是資料不足;皆 ≤ 門檻 → 動能不足 0、c4_ok=True
        r = run_df(REAL, mk_df([0.0, -10.0, 0.0]), **kw)
        assert r.metrics["rev_yoy_scored"][0] == 0.0 and r.metrics["rev_yoy_scored"][1] == pytest.approx(-10.0)
        assert r.c4_ok is True and r.c4_revenue_yoy == 0.0 and any("動能不足" in x for x in r.reasons)
        # 有一個 > 門檻 → 既有 PARTIAL
        r = run_df(REAL, mk_df([0.0, -10.0, 30.0]), **kw)
        assert r.c4_ok is True and r.c4_revenue_yoy == PARTIAL


def test_legacy_without_contract_and_undetermined_and_eligible_none():
    assert run(REAL, INC).c4_revenue_yoy == PARTIAL                                  # 無契約
    assert run(REAL, INC, MC.legacy_undetermined_contract()).c4_revenue_yoy == PARTIAL
    assert run(REAL, LOW).c4_revenue_yoy == 0.0 and run(REAL, LOW).c4_ok is True
    assert run(REAL, [None, None, 20.0]).c4_ok is False                              # 舊文案/資料不足不變
    r = run(REAL, INC, hand(INC, target_date_eligible=[None, None, None]))          # 公告時點未知
    assert r.c4_revenue_yoy == PARTIAL
    # legacy basis 但契約 status=OK、連續性 True(as_of 缺)→ 也不得 STEADY
    y3, con = inputs(mk_df(INC), as_of=None)
    assert con["contract_status"] == "OK" and con["yoy_months_contiguous"] is True
    assert REAL.score_shortage(stock(y3, con)).c4_revenue_yoy == PARTIAL


def test_upstream_failure_fail_closed_is_insufficient():
    st = compute_yoy_mom(mk_df(INC), as_of=ASOF, upstream_failed=True)
    con = MC.extract_month_contract(st)
    r = REAL.score_shortage(stock(INC, con))
    assert r.c4_revenue_yoy == 0.0 and r.c4_ok is False and "FAIL_CLOSED" in r.miss_reason


def test_existing_legitimate_partial_unchanged():
    """既有合法 PARTIAL(已驗證 + 一個 >門檻)分數/理由結構不變,且不帶未驗證字樣。"""
    r = run(REAL, MIX, hand(MIX))
    assert r.c4_revenue_yoy == PARTIAL and "未驗證" not in r.reason_text and "部分達標" in r.reason_text
    assert r.metrics["rev_c4_key_unverified"] == []


def test_c4_scores_only_existing_constants():
    allowed = {0.0, PARTIAL, STEADY, STRONG}
    for y in (INC, FLAT, LOW, MIX, [None, 20.0, 30.0], [None, None, 20.0]):
        for con in (None, hand(y), hand(y, month_key_verified=False), MC.legacy_undetermined_contract()):
            assert run(REAL, y, con).c4_revenue_yoy in allowed


def test_signal_flags_consistent_with_cap():
    """c4_ok／n_signals_ok／miss_reason 與分數一致:未驗證 5 分=ok;資料不足=not ok 且 miss_reason 有④。"""
    r5 = run(REAL, INC)
    assert r5.c4_ok is True and r5.n_signals_ok == 4 and "④" not in r5.miss_reason
    rd = run(REAL, [None, None, 20.0])
    assert rd.c4_ok is False and rd.n_signals_ok == 3 and "④" in rd.miss_reason


def test_c1_c3_unchanged_and_four_missing_exclusion_unchanged():
    base = run(REAL, INC)
    ref = run(REAL, INC, hand(INC))                      # 已驗證
    assert (base.c1_contract_liab, base.c2_gross_margin, base.c3_inventory_days) == \
           (ref.c1_contract_liab, ref.c2_gross_margin, ref.c3_inventory_days)
    qs = [dict(q, contract_liab=None, gross_profit=None, inventory=None) for q in _strong_quarters()]
    r = run(REAL, [None, None, None], quarters=qs)
    assert r.n_signals_ok == 0 and r.tier == TIER_INSUFFICIENT and r.total == 0.0
    assert REAL.rank_shortage([stock([None, None, None], quarters=qs)]) == []


def test_no_new_threshold_constants_in_source():
    """DEC-153 不新增分數/門檻:C4 區段只引用既有 SHORTAGE_REV_*/SHORTAGE_REVENUE_YOY_MIN_PCT。"""
    src = (REPO / "src/compute/screener/shortage_screener.py").read_text(encoding="utf-8")
    seg = src[src.index("DEC-153(客戶"):src.index("# 有效旗標（DEC-149")]
    assert "SHORTAGE_REV_" in seg
    import re
    assert not re.findall(r"(?<![\w.\[])\d+\.\d+(?![\w])", seg.split("key_unverified: list[str] = []")[1]
                          .split("increasing =")[0]), "未驗證判定區不得出現數字常數"


# ───────────────────────── 突變(≥4,必須轉紅;原碼綠) ─────────────────────────
_SEQ = [0]


def _load_mutant(old: str, new: str):
    src = (REPO / "src/compute/screener/shortage_screener.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變錨點必須在原檔恰出現 1 次:{old!r}(實得 {src.count(old)})"
    _SEQ[0] += 1
    mod = types.ModuleType(f"_c4e_mutant_{_SEQ[0]}")
    mod.__file__ = "<mutant>"
    sys.modules[mod.__name__] = mod
    exec(compile(src.replace(old, new), "<mutant>", "exec"), mod.__dict__)
    return mod


_GATE = "if n_missing == 0 and contiguous is True and not key_unverified:"
MUTANTS = {
    # (a) 恢復 verified=False 也可 STEADY/STRONG(拿掉未驗證閘門)
    "restore_unverified_steady": (_GATE, "if n_missing == 0 and contiguous is True:", check_unverified_capped_at_partial),
    # (b) 動能不足改給 5(把未驗證/缺月的動能不足抬到 PARTIAL)
    "momentum_zero_to_five": (
        "return _c4_result(0.0, f\"🔴月營收 YoY 動能不足（{len(valid)}/{TARGET_MONTHS}月有值",
        "return _c4_result(SHORTAGE_REV_PARTIAL_SCORE, f\"🔴月營收 YoY 動能不足（{len(valid)}/{TARGET_MONTHS}月有值",
        check_unverified_low_is_momentum_zero),
    # (c) 資料不足硬給 5 分
    "insufficient_forced_five": (
        "return _c4_result(0.0, f\"⚪月營收 YoY：資料不足{_tail}\", metrics, ok=False, miss=_miss)",
        "return _c4_result(SHORTAGE_REV_PARTIAL_SCORE, f\"⚪月營收 YoY：資料不足{_tail}\", metrics, ok=False, miss=_miss)",
        check_unverified_insufficient_not_five),
    # (d) 無視 target_date_eligible(資格 None/False 不再算未驗證)
    "ignore_eligible": (
        "        if not all(e is True for e in elig):\n            key_unverified.append(",
        "        if False:\n            key_unverified.append(",
        check_hand_flag_unverified),
    # (e) 無視契約 month_key_verified
    "ignore_month_key_verified": (
        "if c.get(\"month_key_verified\") is not True:", "if False:", check_hand_flag_unverified),
}


@pytest.mark.parametrize("name", list(MUTANTS))
def test_mutant_is_killed(name):
    old, new, chk = MUTANTS[name]
    mut = _load_mutant(old, new)
    chk(REAL)                                   # 原碼綠
    with pytest.raises(AssertionError):         # 突變碼紅
        chk(mut)


# ───────────────────────── 下游 before/after(合成 fixture,不代表真實市場) ─────────────────────────
def _variant_quarters():
    """四種 C1–C3 底分(strong=80、hi=55、lo=32、weak=22;55／32 讓 C4 的 +12 與 +5 落在不同 tier 門檻兩側)。"""
    def edit(base, **by_idx):
        out = [dict(q) for q in base]
        for idx, kv in by_idx.items():
            out[int(idx[1:])].update(kv)
        return out
    strong = _strong_quarters()
    # 底分 55:C1 20(合約負債 YoY 20% 級)+ C2 25 + C3 10(存貨僅單降) → +12=67(強) / +5=60(中)
    hi = edit(strong, q0={"contract_liab": 180}, q4={"inventory": 250})
    # 底分 32:C1 0 + C2 12(毛利率僅單升)+ C3 20 → +12=44(中) / +5=37(弱)
    lo = edit(strong, q0={"contract_liab": 170}, q4={"gross_profit": 620})
    weak = edit(strong, q0={"contract_liab": 170}, q4={"gross_profit": 620, "inventory": 250})
    return {"strong": strong, "hi55": hi, "lo32": lo, "weak": weak}


def _scenarios():
    """(名稱, yoy3, contract)。含 verified/unverified 三路(單股已驗證、單股未驗證/date≠ym、全市場批次、legacy)。"""
    out = []
    for k, off in enumerate((0.0, 0.5, 1.0, 1.5, 2.0, 2.5)):       # 同型態微擾 → 排名有並列也有差異
        inc = [a + off for a in INC]
        flat = [a + off for a in FLAT]
        low = [a + off for a in LOW]
        mix = [a + off for a in MIX]
        for tag, y in (("inc", inc), ("flat", flat), ("low", low), ("mix", mix)):
            df = mk_df(y)
            out.append((f"single_verified_{tag}_{k}", *inputs(df)))
            out.append((f"batch_{tag}_{k}", *inputs(df, source_month_key_verified=False)))
            out.append((f"date_ne_ym_{tag}_{k}", *inputs(mk_df(y, date_shift=1))))
            out.append((f"legacy_{tag}_{k}", y, None))
        out.append((f"batch_gap_{k}", *inputs(mk_df([20.0 + off, None, 40.0]), source_month_key_verified=False)))
        out.append((f"batch_one_valid_{k}", *inputs(mk_df([None, None, 30.0 + off]), source_month_key_verified=False)))
    return out


def _build_stocks():
    stocks, meta = [], {}
    n = 0
    for vname, qs in _variant_quarters().items():
        for sname, y3, con in _scenarios():
            sid = f"{1000 + n}"
            n += 1
            stocks.append(stock(y3, con, quarters=qs, sid=sid))
            meta[sid] = (vname, sname)
    return stocks, meta


@pytest.fixture(scope="module")
def baseline_module():
    """DEC-153 前行為:把未驗證判定清空(其餘一字不動)。"""
    return _load_mutant('    metrics["rev_c4_key_unverified"] = list(key_unverified)',
                        '    key_unverified = []\n    metrics["rev_c4_key_unverified"] = list(key_unverified)')


def test_downstream_before_after_quantified(baseline_module):
    stocks, meta = _build_stocks()
    old = {s.stock_id: s for s in baseline_module.rank_shortage(stocks, include_na=True)}
    new = {s.stock_id: s for s in REAL.rank_shortage(stocks, include_na=True)}
    assert len(old) == len(new) == len(stocks) >= 200

    # (1) C1–C3 / c*_ok / n_signals_ok / miss_reason 全程不變;只有 C4 分數(與連動 total/tier/理由)可變
    for sid in old:
        a, b = old[sid], new[sid]
        assert (a.c1_contract_liab, a.c2_gross_margin, a.c3_inventory_days) == \
               (b.c1_contract_liab, b.c2_gross_margin, b.c3_inventory_days), sid
        assert (a.c1_ok, a.c2_ok, a.c3_ok, a.c4_ok, a.n_signals_ok, a.miss_reason) == \
               (b.c1_ok, b.c2_ok, b.c3_ok, b.c4_ok, b.n_signals_ok, b.miss_reason), sid
        assert b.c4_revenue_yoy <= a.c4_revenue_yoy, "DEC-153 只可降分,不可升分"
        assert abs((a.total - b.total) - (a.c4_revenue_yoy - b.c4_revenue_yoy)) < 1e-9

    # (2) C4 轉移矩陣
    trans = Counter((old[s].c4_revenue_yoy, new[s].c4_revenue_yoy) for s in old)
    allowed_new = {0.0, PARTIAL, STEADY, STRONG}
    assert all(n in allowed_new for _, n in trans)
    # 未驗證路徑(batch/date_ne_ym/legacy)新 C4 ≤ 5;已驗證單股路徑完全不變
    for sid, (_v, sname) in meta.items():
        if sname.startswith("single_verified_"):
            assert old[sid].c4_revenue_yoy == new[sid].c4_revenue_yoy, sname
        else:
            assert new[sid].c4_revenue_yoy <= PARTIAL, sname
    # 被降分的只可能是原 12/20 → 5(原 5/0 不動;不會有 →0 的新降分)
    assert {k for k in trans if k[0] != k[1]} <= {(STRONG, PARTIAL), (STEADY, PARTIAL), (STRONG, 0.0), (STEADY, 0.0)}
    assert (STRONG, 0.0) not in trans and (STEADY, 0.0) not in trans, "有 >門檻的有效值者不得被降到 0"
    # 註:修前未驗證路徑的資格為 None → STRONG 本就被擋,實際降分是 STEADY→5;(STRONG→5)只在手建『資格全 True 但
    # month_key_verified=False』的契約出現(見 test_hand_built_unverified_flags),producer 不會產生。
    assert trans[(STEADY, PARTIAL)] > 0, "fixture 必須真的覆蓋到降分"

    # (3) tier 變動:只降不升
    order = {"弱訊號": 0, "中度": 1, "強缺貨": 2}
    tier_moves = Counter((old[s].tier, new[s].tier) for s in old if old[s].tier != new[s].tier)
    for (a, b), n in tier_moves.items():
        assert order.get(b, -1) < order.get(a, -1) and n > 0, (a, b)
    assert tier_moves, "fixture 必須有 tier 變動才有量化意義"

    # (4) 排名位移 + 前 50 名變動(用真實 rank_shortage 排序;可評分者)
    ro = [s.stock_id for s in baseline_module.rank_shortage(stocks)]
    rn = [s.stock_id for s in REAL.rank_shortage(stocks)]
    assert len(ro) == len(rn) == len(stocks)        # DEC-153 不排除任何股票(僅降分,四項全缺外無股被移出榜)
    top_old, top_new = set(ro[:50]), set(rn[:50])
    n_top_changed = len(top_old - top_new)
    pos_o = {s: i for i, s in enumerate(ro)}
    pos_n = {s: i for i, s in enumerate(rn)}
    shifts = [pos_n[s] - pos_o[s] for s in ro]
    # 已驗證單股 STRONG 仍在最前面群組:新榜前 N 名(N=已驗證 strong 變體 × 單股 inc)全為已驗證單股
    ver_strong = [s for s, (v, n) in meta.items() if v == "strong" and n.startswith("single_verified_inc")]
    assert set(rn[:len(ver_strong)]) == set(ver_strong)
    # 量化數字(合成資料,deterministic):印出供報告;並釘上下界避免靜默漂移
    print(f"[DEC-153 before/after] n={len(stocks)} 轉移={dict(trans)} tier_moves={dict(tier_moves)} "
          f"top50_out={n_top_changed} max_rank_drop={max(shifts)} moved={sum(1 for x in shifts if x)}")
    assert n_top_changed > 0 and max(shifts) > 0 and sum(1 for x in shifts if x) > 0


def test_service_paths_batch_and_single_use_real_ranking(monkeypatch):
    """L3 真實路徑:全市場批次(source 未驗證)最高 5;單股逐檔(source 可信)STRONG 維持。"""
    from src.services import shortage_screener_service as SVC
    frame = _strong_quarters()
    monkeypatch.setattr(SVC, "fetch_quarterly_shortage_frame", lambda sid: frame)
    monkeypatch.setattr(SVC, "_as_of_today", lambda: ASOF)

    # 全市場批次:30 檔同型 INC(date==ym,但批次來源標記未驗證)
    frames = []
    for i in range(30):
        d = mk_df(INC)
        d.insert(0, "stock_id", f"{1100 + i}")
        frames.append(d)
    pool = SVC._candidate_pool(pd.concat(frames, ignore_index=True), max_n=1000)
    assert len(pool) == 30
    pairs = [(c["stock_id"], c["revenue_yoy_last3"], c[MC.MONTH_CONTRACT_KEY]) for c in pool]
    rows, _note = SVC._score_and_diagnose(pairs)
    assert rows and all(r["④月營收"] <= PARTIAL for r in rows), [r["④月營收"] for r in rows][:5]

    # 單股逐檔(存活池路徑,pair 無 yoy3 → 單抓月營收;date==ym、source 可信)→ 仍可 STRONG
    monkeypatch.setattr(SVC, "fetch_monthly_revenue", lambda sid, months=18: mk_df(INC))
    rows1, _ = SVC._score_and_diagnose([("2330", None)])
    assert rows1 and rows1[0]["④月營收"] == STRONG
    # 單股 date≠ym → 最高 5
    monkeypatch.setattr(SVC, "fetch_monthly_revenue", lambda sid, months=18: mk_df(INC, date_shift=1))
    rows2, _ = SVC._score_and_diagnose([("2330", None)])
    assert rows2 and rows2[0]["④月營收"] == PARTIAL


def test_downstream_consumers_schema_unchanged():
    """消費者契約:to_row 鍵集合不變(forward_test 凍結讀『缺貨分數』欄/通知讀『_tier』);C4 只多 metrics 鍵(additive)。"""
    row = REAL.score_shortage(stock(INC)).to_row()
    assert set(row) == {"代碼", "名稱", "缺貨分數", "訊號強度", "①合約負債", "②毛利率", "③存貨天數", "④月營收", "理由",
                        "_tier", "有效訊號數", "缺值原因", "_n_signals_ok", "_c1_ok", "_c2_ok", "_c3_ok", "_c4_ok"}
    m = REAL.score_shortage(stock(INC)).metrics
    assert "rev_yoy_last3" in m and "rev_c4_ok" in m and "rev_c4_key_unverified" in m   # 舊 key 保留
