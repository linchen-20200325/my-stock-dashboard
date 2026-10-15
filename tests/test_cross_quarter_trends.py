"""tests/test_cross_quarter_trends.py — 全台股跨季趨勢因子(v19.139 A-1;AUD-C4 單季化 2026-10-15)。

驗趨勢斜率方向 + YoY + favorable_count + §1 誠實邊界(季數不足/缺去年同季/除零),
以及 AUD-C4:損益流量欄由「年初至今累計」拆單季後才算毛利率/營益率斜率。
含對 repo 內真實季快照 parquet 的驗算 / smoke / golden(資料在 repo,可離線跑)。

⚠️ fixture 有意識的修改(2026-10-15,AUD-C4,不是漏改):原 fixture 把 revenue /
gross_profit / op_income 寫成**單季**形狀的數字,但真實資料(MOPS t163sb04)是
**年初至今累計** —— 原 fixture 與真實資料不符,正是它沒抓到「把累計當逐季」這個 bug 的原因。
現行:fixture 先以「單季意圖」寫出,再經 `_ytd()` 依同一 roc_year 累加成累計形狀餵進去。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.compute.screener.cross_quarter_trends import (
    compute_cross_quarter_trends,
    ytd_to_single_quarter,
)

_FUND_DIR = Path(__file__).resolve().parents[1] / "data_cache" / "fundamentals"
_FLOW = ("revenue", "gross_profit", "op_income")


def _q(sid, roc, season, *, rev, gp, op, ta, tl):
    return {"stock_id": sid, "roc_year": roc, "season": season,
            "revenue": rev, "gross_profit": gp, "op_income": op,
            "total_assets": ta, "total_liab": tl}


def _ytd(rows):
    """單季意圖的 rows → 年初至今累計形狀(同 stock_id、同 roc_year 依 season 累加;存量欄不動)。"""
    df = pd.DataFrame(rows).sort_values(["stock_id", "roc_year", "season"]).reset_index(drop=True)
    for c in _FLOW:
        df[c] = df.groupby(["stock_id", "roc_year"])[c].cumsum()
    return df


def _rising_stock(sid="AAA"):
    """(單季意圖)毛利率/營益率逐季升、負債比逐季降、營收 YoY 正 → 四項全佳。"""
    rows = []
    for i, roc_season in enumerate([(114, 1), (114, 2), (114, 3), (114, 4), (115, 1)]):
        roc, s = roc_season
        rev = 1000 + i * 100                      # 單季營收成長(115Q1=1400 vs 114Q1=1000 → YoY +40%)
        gp = rev * (0.20 + i * 0.02)              # 單季毛利率 20%→28% 升
        op = rev * (0.10 + i * 0.02)              # 單季營益率 10%→18% 升
        tl = 600 - i * 50                         # 負債 600→400(存量)
        rows.append(_q(sid, roc, s, rev=rev, gp=gp, op=op, ta=1000, tl=tl))
    return rows


# ── 方向正確性 ────────────────────────────────────────────────
def test_rising_stock_all_favorable():
    df = compute_cross_quarter_trends(_ytd(_rising_stock()))
    r = df.iloc[0]
    assert r["gross_margin_slope"] == pytest.approx(0.02, abs=1e-9)   # 單季毛利率每季 +2pp
    assert r["op_margin_slope"] == pytest.approx(0.02, abs=1e-9)
    assert r["debt_ratio_slope"] < 0
    # Q1 累計 = 單季 → 1400/1000-1(累計對累計,AUD-C4 不改 yoy 定義)
    assert r["revenue_yoy"] == pytest.approx(0.4, abs=1e-6)
    assert r["favorable_count"] == 4 and r["favorable_of"] == 4
    assert r["single_quarter_breaks"] == 0


def test_deteriorating_stock_zero_favorable():
    # 反向(單季意圖):毛利/營益率降、負債升、營收縮 → 0 佳
    rows = []
    for i, (roc, s) in enumerate([(114, 1), (114, 2), (114, 3), (114, 4), (115, 1)]):
        rev = 1000 - i * 100
        rows.append(_q("BBB", roc, s, rev=rev, gp=rev * (0.30 - i * 0.03),
                       op=rev * (0.20 - i * 0.03), ta=1000, tl=400 + i * 50))
    df = compute_cross_quarter_trends(_ytd(rows))
    r = df.iloc[0]
    assert r["gross_margin_slope"] == pytest.approx(-0.03, abs=1e-9)
    assert r["op_margin_slope"] == pytest.approx(-0.03, abs=1e-9)
    assert r["debt_ratio_slope"] > 0 and r["revenue_yoy"] < 0
    assert r["favorable_count"] == 0 and r["favorable_of"] == 4


def test_sorted_by_favorable_desc():
    df = compute_cross_quarter_trends(_ytd(_rising_stock("GOOD") + [
        _q("BAD", 114, 1, rev=1000, gp=200, op=100, ta=1000, tl=900),
        _q("BAD", 114, 2, rev=900, gp=150, op=50, ta=1000, tl=950),
        _q("BAD", 114, 3, rev=800, gp=100, op=20, ta=1000, tl=980),
    ]))
    assert list(df["stock_id"])[0] == "GOOD"   # 四項全佳排最前


def test_single_quarter_slope_differs_from_cumulative_slope():
    """核心修法:斜率吃單季比率,不吃累計比率。

    單季毛利率 114: 50%,10%,10%,10%;115Q1: 50%(營收各 1000)。
    單季斜率 = polyfit([0..4],[.5,.1,.1,.1,.5]);累計比率則為 .5,.3,.233,.2,.5 —— 兩者斜率不同。
    """
    gms = [0.5, 0.1, 0.1, 0.1, 0.5]
    rows = [_q("SQ", roc, s, rev=1000, gp=1000 * g, op=100, ta=1000, tl=500)
            for (roc, s), g in zip([(114, 1), (114, 2), (114, 3), (114, 4), (115, 1)], gms)]
    r = compute_cross_quarter_trends(_ytd(rows)).iloc[0]
    _expect = np.polyfit(np.arange(5.0), np.array(gms), 1)[0]
    _cum_ratio = [0.5, 0.6 / 2, 0.7 / 3, 0.8 / 4, 0.5]
    _cum_slope = np.polyfit(np.arange(5.0), np.array(_cum_ratio), 1)[0]
    assert r["gross_margin_slope"] == pytest.approx(_expect, abs=1e-12)
    assert abs(_expect - _cum_slope) > 1e-3        # 確認這個 fixture 真的分得出兩種算法


# ── §1 誠實邊界 ──────────────────────────────────────────────
def test_insufficient_quarters_slope_nan():
    # 只有 2 季 < MIN(3) → 斜率 NaN(不硬配)
    rows = [_q("CCC", 114, 1, rev=1000, gp=200, op=100, ta=1000, tl=500),
            _q("CCC", 114, 2, rev=1100, gp=240, op=120, ta=1000, tl=480)]
    r = compute_cross_quarter_trends(_ytd(rows)).iloc[0]
    assert np.isnan(r["gross_margin_slope"]) and np.isnan(r["op_margin_slope"])
    assert r["n_quarters"] == 2


def test_no_prior_year_quarter_yoy_nan():
    # 只有 114Q1~Q4(無 115、也無 113)→ 最新 114Q4 的去年同季 113Q4 不存在 → yoy NaN
    rows = [_q("DDD", 114, s, rev=1000 + s, gp=200, op=100, ta=1000, tl=500)
            for s in (1, 2, 3, 4)]
    r = compute_cross_quarter_trends(_ytd(rows)).iloc[0]
    assert np.isnan(r["revenue_yoy"])
    assert r["favorable_of"] == 3    # 3 個斜率有、yoy 無


def test_zero_revenue_margin_nan_not_zero():
    # revenue=0 → 毛利率 NaN(不 silent 0);金融業無營收自然無三率
    rows = [_q("EEE", 114, s, rev=0, gp=0, op=0, ta=1000, tl=500) for s in (1, 2, 3)]
    r = compute_cross_quarter_trends(_ytd(rows)).iloc[0]
    assert np.isnan(r["gross_margin_slope"]) and np.isnan(r["op_margin_slope"])


def test_empty_and_missing_cols():
    assert compute_cross_quarter_trends(pd.DataFrame()).empty
    with pytest.raises(ValueError, match="缺必備欄"):
        compute_cross_quarter_trends(pd.DataFrame({"stock_id": ["X"]}))


def test_duplicate_same_quarter_kept_last():
    # 同檔同季兩筆(補抓)→ 去重 keep last,不重複計季(累計形狀直接寫出)
    rows = [_q("FFF", 114, 1, rev=1000, gp=200, op=100, ta=1000, tl=500),
            _q("FFF", 114, 1, rev=1200, gp=300, op=150, ta=1000, tl=450),  # 補抓覆蓋
            _q("FFF", 114, 2, rev=2500, gp=640, op=320, ta=1000, tl=440),
            _q("FFF", 114, 3, rev=3900, gp=1020, op=510, ta=1000, tl=430)]
    r = compute_cross_quarter_trends(pd.DataFrame(rows)).iloc[0]
    assert r["n_quarters"] == 3   # 3 個不同季(非 4)
    # keep last:114Q2 單季 = 2500 − 1200(不是 − 1000)→ 毛利率 340/1300
    sq = ytd_to_single_quarter(pd.DataFrame(rows[1:]))
    assert sq.loc[sq["season"] == 2, "sq_revenue"].item() == 1300


# ── AUD-C4 單季化(ytd_to_single_quarter)────────────────────────
def _sq_frame(rows):
    return ytd_to_single_quarter(pd.DataFrame(rows))


def test_ytd_q1_is_cumulative_and_q2_is_difference():
    out = _sq_frame([_q("A", 114, 1, rev=100, gp=40, op=20, ta=1, tl=1),
                     _q("A", 114, 2, rev=250, gp=90, op=50, ta=1, tl=1)])
    q1 = out[out["season"] == 1].iloc[0]
    q2 = out[out["season"] == 2].iloc[0]
    assert (q1["sq_revenue"], q1["sq_gross_profit"], q1["sq_op_income"]) == (100, 40, 20)
    assert (q2["sq_revenue"], q2["sq_gross_profit"], q2["sq_op_income"]) == (150, 50, 30)
    # 原累計欄保留(yoy 要用)
    assert list(out["revenue"]) == [100, 250]


def test_ytd_does_not_subtract_across_years():
    """(b) 跨年不相減:115Q1 單季 = 115Q1 累計(不得減 114Q4)。"""
    out = _sq_frame([_q("A", 114, 4, rev=1000, gp=400, op=200, ta=1, tl=1),
                     _q("A", 115, 1, rev=300, gp=120, op=60, ta=1, tl=1)])
    r = out[(out["roc_year"] == 115)].iloc[0]
    assert (r["sq_revenue"], r["sq_gross_profit"], r["sq_op_income"]) == (300, 120, 60)
    assert not r["sq_break"]
    # 114Q4 前季(114Q3)不存在 → NaN(也證明沒有拿別年的列去減)
    r4 = out[(out["roc_year"] == 114)].iloc[0]
    assert np.isnan(r4["sq_revenue"])


def test_ytd_missing_prev_quarter_is_nan():
    """(c) 前季那列不存在 → 三欄單季全 NaN(不補 0、不前值填補)。"""
    out = _sq_frame([_q("A", 114, 1, rev=100, gp=40, op=20, ta=1, tl=1),
                     _q("A", 114, 3, rev=400, gp=160, op=80, ta=1, tl=1)])   # 缺 Q2
    r = out[out["season"] == 3].iloc[0]
    assert np.isnan(r["sq_revenue"]) and np.isnan(r["sq_gross_profit"]) and np.isnan(r["sq_op_income"])
    assert not r["sq_break"]     # 缺前季 ≠ 口徑斷層


def test_ytd_nan_at_either_end_is_nan():
    """(d) 任一端該欄 NaN → 該欄單季 NaN(逐欄;其他欄照算)。"""
    out = _sq_frame([_q("A", 114, 1, rev=100, gp=np.nan, op=20, ta=1, tl=1),     # 前端 gp NaN
                     _q("A", 114, 2, rev=250, gp=90, op=np.nan, ta=1, tl=1),     # 當端 op NaN
                     _q("A", 114, 3, rev=np.nan, gp=150, op=90, ta=1, tl=1)])    # 當端 rev NaN
    q2 = out[out["season"] == 2].iloc[0]
    assert np.isnan(q2["sq_gross_profit"]) and np.isnan(q2["sq_op_income"])
    assert q2["sq_revenue"] == 150
    q3 = out[out["season"] == 3].iloc[0]
    assert np.isnan(q3["sq_revenue"]) and np.isnan(q3["sq_op_income"])   # op 前端 NaN
    assert q3["sq_gross_profit"] == 60
    assert not out["sq_break"].any()


def test_ytd_negative_single_revenue_is_break_all_nan_and_counted():
    """(e) 相減後單季營收 < 0(口徑斷層)→ 三欄 NaN + sq_break + 輸出計數可見。"""
    rows = [_q("BRK", 114, 1, rev=1000, gp=300, op=100, ta=1000, tl=500),
            _q("BRK", 114, 2, rev=800, gp=350, op=150, ta=1000, tl=500),    # 單季 −200
            _q("BRK", 114, 3, rev=1800, gp=650, op=250, ta=1000, tl=500),
            _q("BRK", 114, 4, rev=2800, gp=950, op=350, ta=1000, tl=500)]
    out = _sq_frame(rows)
    q2 = out[out["season"] == 2].iloc[0]
    assert bool(q2["sq_break"]) is True
    assert np.isnan(q2["sq_revenue"]) and np.isnan(q2["sq_gross_profit"]) and np.isnan(q2["sq_op_income"])
    assert out["sq_break"].sum() == 1
    r = compute_cross_quarter_trends(pd.DataFrame(rows)).iloc[0]
    assert r["single_quarter_breaks"] == 1
    # 斷層季不計入有效點:Q1/Q3/Q4 三點 → 斜率仍算得出
    assert not np.isnan(r["gross_margin_slope"])


def test_single_revenue_zero_ratio_nan():
    """(f) 單季營收 = 0(累計持平)→ 比率 NaN(不 silent 0、不 inf);不算斷層。"""
    rows = [_q("Z", 114, 1, rev=1000, gp=300, op=100, ta=1000, tl=500),
            _q("Z", 114, 2, rev=1000, gp=300, op=100, ta=1000, tl=500),   # 單季 0
            _q("Z", 114, 3, rev=2000, gp=600, op=200, ta=1000, tl=500)]
    out = _sq_frame(rows)
    assert out.loc[out["season"] == 2, "sq_revenue"].item() == 0
    assert not out["sq_break"].any()
    r = compute_cross_quarter_trends(pd.DataFrame(rows)).iloc[0]
    assert np.isnan(r["gross_margin_slope"])        # 有效點只剩 2 < 3
    assert r["single_quarter_breaks"] == 0


def test_ytd_never_turns_missing_into_zero_synthetic():
    """(g) 不補 0:缺值(缺前季 / 任一端 NaN)一律 NaN,結果中沒有由缺值變成的 0。"""
    out = _sq_frame([_q("A", 114, 2, rev=100, gp=np.nan, op=0, ta=1, tl=1),     # 缺 Q1
                     _q("A", 114, 3, rev=np.nan, gp=50, op=np.nan, ta=1, tl=1)])
    for c in _FLOW:
        assert out["sq_" + c].isna().all(), c


def test_ytd_rejects_duplicate_keys_and_bad_season():
    with pytest.raises(ValueError, match="重複"):
        _sq_frame([_q("A", 114, 1, rev=1, gp=1, op=1, ta=1, tl=1)] * 2)
    with pytest.raises(ValueError, match="season"):
        _sq_frame([_q("A", 114, 5, rev=1, gp=1, op=1, ta=1, tl=1)])
    with pytest.raises(ValueError, match="roc_year"):
        _sq_frame([_q("A", np.nan, 1, rev=1, gp=1, op=1, ta=1, tl=1),
                   _q("A", np.nan, 2, rev=2, gp=1, op=1, ta=1, tl=1)])


# ── 真實資料(repo 內季快照 parquet,離線)──────────────────────
def _real_all():
    from src.data.stock.fundamentals_snapshot_loader import _load_all_quarters_impl
    try:
        _all = _load_all_quarters_impl(_FUND_DIR)
    except FileNotFoundError:
        pytest.skip("repo 無 fundamentals 快照(CI 精簡環境)")
    _all = _all.copy()
    _all["stock_id"] = _all["stock_id"].astype(str).str.strip()
    return _all


def _read_quarter(name):
    p = _FUND_DIR / name
    if not p.exists():
        pytest.skip(f"repo 無 {name}")
    df = pd.read_parquet(p)
    df["stock_id"] = df["stock_id"].astype(str).str.strip()
    return df


def test_real_2330_114q4_single_quarter():
    """(a) 真實快照驗算:2330 114Q4 單季營收 = 114Q4 累計 − 114Q3 累計。"""
    q3 = _read_quarter("sii_114Q3.parquet")
    q4 = _read_quarter("sii_114Q4.parquet")
    c3 = q3.loc[q3["stock_id"] == "2330", "revenue"].item()
    c4 = q4.loc[q4["stock_id"] == "2330", "revenue"].item()
    assert c4 == 3_809_054_272 and c3 == 2_762_963_851      # 快照確為年初累計
    out = ytd_to_single_quarter(pd.concat([q3, q4], ignore_index=True))
    sq = out.loc[(out["stock_id"] == "2330") & (out["season"] == 4), "sq_revenue"].item()
    assert sq == 3_809_054_272 - 2_762_963_851


def test_real_2330_115q1_not_cross_year():
    """(b) 真實資料:2330 115Q1 單季 = 115Q1 累計(不減 114Q4)。"""
    q4 = _read_quarter("sii_114Q4.parquet")
    q1 = _read_quarter("sii_115Q1.parquet")
    out = ytd_to_single_quarter(pd.concat([q4, q1], ignore_index=True))
    r = out[(out["stock_id"] == "2330") & (out["roc_year"] == 115)].iloc[0]
    for c in _FLOW:
        assert r["sq_" + c] == r[c]


def test_real_2330_margin_slope_matches_hand_computed_single_quarter():
    """2330 毛利率/營益率斜率 = 手算單季比率的 polyfit(防單季化被拔掉)。"""
    _all = _real_all()
    g = _all[_all["stock_id"] == "2330"].sort_values(["roc_year", "season"])
    gm, om, t = [], [], []
    for roc, gg in g.groupby("roc_year"):
        gg = gg.sort_values("season")
        prev = None
        for _, row in gg.iterrows():
            if row["season"] == 1:
                rv, gp, op = row["revenue"], row["gross_profit"], row["op_income"]
            elif prev is not None and prev["season"] == row["season"] - 1:
                rv = row["revenue"] - prev["revenue"]
                gp = row["gross_profit"] - prev["gross_profit"]
                op = row["op_income"] - prev["op_income"]
            else:
                rv = gp = op = np.nan
            prev = row
            t.append(roc * 4 + row["season"] - 1)
            gm.append(gp / rv if rv > 0 else np.nan)
            om.append(op / rv if rv > 0 else np.nan)
    t = np.array(t, dtype=float) - min(t)
    r = compute_cross_quarter_trends(_all[_all["stock_id"] == "2330"]).iloc[0]
    _m = ~np.isnan(gm)
    assert r["gross_margin_slope"] == pytest.approx(
        np.polyfit(t[_m], np.array(gm)[_m], 1)[0], rel=1e-12)
    _m = ~np.isnan(om)
    assert r["op_margin_slope"] == pytest.approx(
        np.polyfit(t[_m], np.array(om)[_m], 1)[0], rel=1e-12)


def test_real_never_turns_missing_into_zero():
    """(g) 全市場:凡單季為 0 者,當季與前季累計皆非 NaN(0 是算出來的,不是缺值補的)。"""
    _all = _real_all().drop_duplicates(subset=["stock_id", "roc_year", "season"], keep="last")
    out = ytd_to_single_quarter(_all)
    key = ["stock_id", "roc_year", "season"]
    prev = out[key + list(_FLOW)].copy()
    prev["season"] = prev["season"] + 1
    m = out.merge(prev, on=key, how="left", suffixes=("", "_prev"))
    for c in _FLOW:
        zero = m["sq_" + c] == 0
        assert m.loc[zero, c].notna().all()
        nq1 = zero & (m["season"] != 1)
        assert m.loc[nq1, c + "_prev"].notna().all()
        # 反向:當季累計 NaN → 單季必 NaN
        assert m.loc[m[c].isna(), "sq_" + c].isna().all()


# ── golden:revenue_yoy / 負債比斜率 與修前算法逐值相同 ──────────────
def _ref_pre_fix(all_quarters: pd.DataFrame) -> pd.DataFrame:
    """修前(AUD-C4 之前)版本的 revenue_yoy 與 debt_ratio_slope 參考實作(逐字搬自修前邏輯)。

    兩者都不吃單季化結果:yoy 是累計對累計、負債比是存量 —— AUD-C4 規格要求數值不變。
    """
    from shared.cross_quarter_thresholds import CROSS_QUARTER_MIN_POINTS as _MIN
    df = all_quarters.copy()
    df["stock_id"] = df["stock_id"].astype(str).str.strip()
    for c in ("revenue", "total_assets", "total_liab", "roc_year", "season"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["roc_year", "season"])
    df["_qord"] = (df["roc_year"] * 4 + (df["season"] - 1)).astype(int)
    df = df.drop_duplicates(subset=["stock_id", "_qord"], keep="last")
    df["_debt"] = df["total_liab"] / df["total_assets"].where(df["total_assets"] > 0)
    rows = {}
    for sid, g in df.groupby("stock_id", sort=False):
        g = g.sort_values("_qord")
        q = g["_qord"].to_numpy()
        t = (q - q.min()).astype(float)
        y = g["_debt"].to_numpy(dtype=float)
        mk = ~np.isnan(y)
        ds = float(np.polyfit(t[mk], y[mk], 1)[0]) if int(mk.sum()) >= _MIN else float("nan")
        by_q = {int(a): float(b) for a, b in zip(q, g["revenue"].to_numpy()) if b == b}
        yoy = float("nan")
        if by_q:
            lt = max(by_q)
            cur, prv = by_q.get(lt), by_q.get(lt - 4)
            if cur is not None and prv is not None and prv > 0:
                yoy = cur / prv - 1.0
        rows[sid] = (ds, yoy)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["debt_ratio_slope", "revenue_yoy"])


def _same_or_both_nan(a: pd.Series, b: pd.Series) -> bool:
    return bool(((a == b) | (a.isna() & b.isna())).all())


def test_real_revenue_yoy_and_debt_slope_golden_unchanged():
    """(h)(i) 全市場:revenue_yoy 與 debt_ratio_slope 與修前算法逐值相同(位元相等)。"""
    _all = _real_all()
    post = compute_cross_quarter_trends(_all).set_index("stock_id")
    ref = _ref_pre_fix(_all)
    assert set(post.index) == set(ref.index)
    post = post.loc[ref.index]
    assert _same_or_both_nan(post["revenue_yoy"], ref["revenue_yoy"])
    assert _same_or_both_nan(post["debt_ratio_slope"], ref["debt_ratio_slope"])


def test_real_snapshot_smoke():
    from src.data.stock.fundamentals_snapshot_loader import load_all_fundamentals_quarters
    try:
        _all = load_all_fundamentals_quarters()
    except FileNotFoundError:
        pytest.skip("repo 無 fundamentals 快照(CI 精簡環境)")
    _all.attrs.clear()  # 避 cache 汙染
    out = compute_cross_quarter_trends(_all)
    assert not out.empty
    assert set(["stock_id", "favorable_count", "revenue_yoy",
                "single_quarter_breaks"]).issubset(out.columns)
    # favorable_count ∈ [0,4]、favorable_of ∈ [0,4] 且 count ≤ of
    assert out["favorable_count"].between(0, 4).all()
    assert (out["favorable_count"] <= out["favorable_of"]).all()
    assert (out["single_quarter_breaks"] >= 0).all()
    # 全市場約 2000 檔(上市+上櫃),至少上百檔
    assert len(out) > 100
