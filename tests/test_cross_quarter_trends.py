"""tests/test_cross_quarter_trends.py — 全台股跨季趨勢因子(v19.139 A-1）。

驗趨勢斜率方向 + YoY + favorable_count + §1 誠實邊界(季數不足/缺去年同季/除零)。
含一個對 repo 內真實 5 季 parquet 的 smoke test（資料在 repo，可離線跑）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compute.screener.cross_quarter_trends import compute_cross_quarter_trends


def _q(sid, roc, season, *, rev, gp, op, ta, tl):
    return {"stock_id": sid, "roc_year": roc, "season": season,
            "revenue": rev, "gross_profit": gp, "op_income": op,
            "total_assets": ta, "total_liab": tl}


def _rising_stock(sid="AAA"):
    """毛利率/營益率逐季升、負債比逐季降、營收 YoY 正 → 四項全佳。"""
    rows = []
    for i, roc_season in enumerate([(114, 1), (114, 2), (114, 3), (114, 4), (115, 1)]):
        roc, s = roc_season
        rev = 1000 + i * 100                      # 營收成長(115Q1=1400 vs 114Q1=1000 → YoY +40%)
        gp = rev * (0.20 + i * 0.02)              # 毛利率 20%→28% 升
        op = rev * (0.10 + i * 0.02)              # 營益率 10%→18% 升
        tl = 600 - i * 50                         # 負債 600→400
        rows.append(_q(sid, roc, s, rev=rev, gp=gp, op=op, ta=1000, tl=tl))
    return rows


# ── 方向正確性 ────────────────────────────────────────────────
def test_rising_stock_all_favorable():
    df = compute_cross_quarter_trends(pd.DataFrame(_rising_stock()))
    r = df.iloc[0]
    assert r["gross_margin_slope"] > 0
    assert r["op_margin_slope"] > 0
    assert r["debt_ratio_slope"] < 0
    assert r["revenue_yoy"] == pytest.approx(0.4, abs=1e-6)   # 1400/1000-1
    assert r["favorable_count"] == 4 and r["favorable_of"] == 4


def test_deteriorating_stock_zero_favorable():
    # 反向:毛利/營益率降、負債升、營收縮 → 0 佳
    rows = []
    for i, (roc, s) in enumerate([(114, 1), (114, 2), (114, 3), (114, 4), (115, 1)]):
        rev = 1000 - i * 100
        rows.append(_q("BBB", roc, s, rev=rev, gp=rev * (0.30 - i * 0.03),
                       op=rev * (0.20 - i * 0.03), ta=1000, tl=400 + i * 50))
    df = compute_cross_quarter_trends(pd.DataFrame(rows))
    r = df.iloc[0]
    assert r["gross_margin_slope"] < 0 and r["op_margin_slope"] < 0
    assert r["debt_ratio_slope"] > 0 and r["revenue_yoy"] < 0
    assert r["favorable_count"] == 0 and r["favorable_of"] == 4


def test_sorted_by_favorable_desc():
    df = compute_cross_quarter_trends(pd.DataFrame(_rising_stock("GOOD") + [
        _q("BAD", 114, 1, rev=1000, gp=200, op=100, ta=1000, tl=900),
        _q("BAD", 114, 2, rev=900, gp=150, op=50, ta=1000, tl=950),
        _q("BAD", 114, 3, rev=800, gp=100, op=20, ta=1000, tl=980),
    ]))
    assert list(df["stock_id"])[0] == "GOOD"   # 四項全佳排最前


# ── §1 誠實邊界 ──────────────────────────────────────────────
def test_insufficient_quarters_slope_nan():
    # 只有 2 季 < MIN(3) → 斜率 NaN(不硬配)
    rows = [_q("CCC", 114, 1, rev=1000, gp=200, op=100, ta=1000, tl=500),
            _q("CCC", 114, 2, rev=1100, gp=240, op=120, ta=1000, tl=480)]
    r = compute_cross_quarter_trends(pd.DataFrame(rows)).iloc[0]
    assert np.isnan(r["gross_margin_slope"]) and np.isnan(r["op_margin_slope"])
    assert r["n_quarters"] == 2


def test_no_prior_year_quarter_yoy_nan():
    # 只有 114Q1~Q4(無 115、也無 113)→ 最新 114Q4 的去年同季 113Q4 不存在 → yoy NaN
    rows = [_q("DDD", 114, s, rev=1000 + s, gp=200, op=100, ta=1000, tl=500)
            for s in (1, 2, 3, 4)]
    r = compute_cross_quarter_trends(pd.DataFrame(rows)).iloc[0]
    assert np.isnan(r["revenue_yoy"])
    assert r["favorable_of"] == 3    # 3 個斜率有、yoy 無


def test_zero_revenue_margin_nan_not_zero():
    # revenue=0 → 毛利率 NaN(不 silent 0);金融業無營收自然無三率
    rows = [_q("EEE", 114, s, rev=0, gp=0, op=0, ta=1000, tl=500) for s in (1, 2, 3)]
    r = compute_cross_quarter_trends(pd.DataFrame(rows)).iloc[0]
    assert np.isnan(r["gross_margin_slope"]) and np.isnan(r["op_margin_slope"])


def test_empty_and_missing_cols():
    assert compute_cross_quarter_trends(pd.DataFrame()).empty
    with pytest.raises(ValueError, match="缺必備欄"):
        compute_cross_quarter_trends(pd.DataFrame({"stock_id": ["X"]}))


def test_duplicate_same_quarter_kept_last():
    # 同檔同季兩筆(補抓)→ 去重 keep last,不重複計季
    rows = [_q("FFF", 114, 1, rev=1000, gp=200, op=100, ta=1000, tl=500),
            _q("FFF", 114, 1, rev=1200, gp=300, op=150, ta=1000, tl=450),  # 補抓覆蓋
            _q("FFF", 114, 2, rev=1300, gp=340, op=170, ta=1000, tl=440),
            _q("FFF", 114, 3, rev=1400, gp=380, op=190, ta=1000, tl=430)]
    r = compute_cross_quarter_trends(pd.DataFrame(rows)).iloc[0]
    assert r["n_quarters"] == 3   # 3 個不同季(非 4)


# ── 真實資料 smoke(repo 內 5 季 parquet,離線)──────────────────
def test_real_snapshot_smoke():
    from src.data.stock.fundamentals_snapshot_loader import load_all_fundamentals_quarters
    try:
        _all = load_all_fundamentals_quarters()
    except FileNotFoundError:
        pytest.skip("repo 無 fundamentals 快照(CI 精簡環境)")
    _all.attrs.clear()  # 避 cache 汙染
    out = compute_cross_quarter_trends(_all)
    assert not out.empty
    assert set(["stock_id", "favorable_count", "revenue_yoy"]).issubset(out.columns)
    # favorable_count ∈ [0,4]、favorable_of ∈ [0,4] 且 count ≤ of
    assert out["favorable_count"].between(0, 4).all()
    assert (out["favorable_count"] <= out["favorable_of"]).all()
    # 全市場約 2000 檔(上市+上櫃),至少上百檔
    assert len(out) > 100
