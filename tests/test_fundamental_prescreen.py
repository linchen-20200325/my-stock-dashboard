"""全台股基本面初篩 L2 純函式測試(向量化,4 項全過才 survivor)。

涵蓋:乾淨存活股、逐項失敗、金融股缺營收、無去年同季、除零 guard、缺欄 raise、
空輸入、真實 parquet smoke。
"""
import numpy as np
import pandas as pd
import pytest

from shared.fundamental_prescreen_thresholds import DEBT_RATIO_MAX, PRESCREEN_REQUIRED_PASSES
from src.compute.screener.fundamental_prescreen import (
    REQUIRED_COLS,
    run_fundamental_prescreen,
    survivors_only,
)


def _row(stock_id, *, revenue=1000.0, gross_profit=400.0, op_income=300.0,
         net_income=200.0, eps=2.0, total_assets=1000.0, total_liab=400.0,
         current_assets=600.0):
    return {
        "stock_id": stock_id, "revenue": revenue, "gross_profit": gross_profit,
        "op_income": op_income, "net_income": net_income, "eps": eps,
        "total_assets": total_assets, "total_liab": total_liab,
        "current_assets": current_assets,
    }


def _df(rows):
    return pd.DataFrame(rows)


# 去年同季:比本季差(三率較低)→ 本季三率三升成立
def _prev_worse(stock_id):
    return _row(stock_id, gross_profit=300.0, op_income=200.0, net_income=100.0)


def test_clean_survivor_passes_all_four():
    cur = _df([_row("2330")])
    prev = _df([_prev_worse("2330")])
    out = run_fundamental_prescreen(cur, prev)
    r = out.iloc[0]
    assert bool(r["pass_debt"])          # 400/1000=0.4 < 0.5
    assert bool(r["pass_three_rise"])    # 三率皆升
    assert bool(r["pass_net_current"])   # 600 > 400
    assert bool(r["pass_eps_positive"])  # 2.0 > 0
    assert r["pass_count"] == 4
    assert bool(r["survivor"])


def test_debt_ratio_fail():
    # 負債 600 / 資產 1000 = 0.6 ≥ 0.5 → pass_debt False → 非 survivor
    cur = _df([_row("1111", total_liab=600.0)])
    out = run_fundamental_prescreen(cur, _df([_prev_worse("1111")]))
    r = out.iloc[0]
    assert not bool(r["pass_debt"])
    assert not bool(r["survivor"])


def test_three_rise_fail_when_margin_flat_or_down():
    # 去年三率 = 本季(未上升)→ 嚴格 > 不成立
    cur = _df([_row("2222")])
    prev = _df([_row("2222")])          # 同值
    out = run_fundamental_prescreen(cur, prev)
    assert not bool(out.iloc[0]["pass_three_rise"])


def test_net_current_fail():
    # 流動資產 300 < 總負債 400 → 淨流動值 <0
    cur = _df([_row("3333", current_assets=300.0)])
    out = run_fundamental_prescreen(cur, _df([_prev_worse("3333")]))
    assert not bool(out.iloc[0]["pass_net_current"])


def test_eps_not_positive_fail():
    cur = _df([_row("4444", eps=-0.5)])
    out = run_fundamental_prescreen(cur, _df([_prev_worse("4444")]))
    assert not bool(out.iloc[0]["pass_eps_positive"])
    assert not bool(out.iloc[0]["survivor"])


def test_financial_stock_no_revenue_excluded():
    # 金融股:無營收/毛利(NaN)→ 三率算不出 → 三率三升 False → 非 survivor(誠實排除)
    cur = _df([_row("2891", revenue=np.nan, gross_profit=np.nan)])
    prev = _df([_prev_worse("2891")])
    r = run_fundamental_prescreen(cur, prev).iloc[0]
    assert not bool(r["pass_three_rise"])
    assert pd.isna(r["gross_margin"])
    assert not bool(r["survivor"])


def test_no_prev_year_three_rise_all_fail():
    # 無去年同季 → 無法 YoY → 三率三升一律不過(不猜)
    cur = _df([_row("5555")])
    for prev in (None, pd.DataFrame()):
        out = run_fundamental_prescreen(cur, prev)
        assert not bool(out.iloc[0]["pass_three_rise"])
        assert not bool(out.iloc[0]["survivor"])


def test_zero_total_assets_guarded():
    # 資產總計 0 → 負債比 NaN(不 inf、不 silent 0)→ pass_debt False
    cur = _df([_row("6666", total_assets=0.0)])
    r = run_fundamental_prescreen(cur, _df([_prev_worse("6666")])).iloc[0]
    assert pd.isna(r["debt_ratio"])
    assert not bool(r["pass_debt"])


def test_zero_revenue_guarded():
    # 營收 0 → 三率 NaN(不 inf)→ 三率三升 False
    cur = _df([_row("7777", revenue=0.0)])
    r = run_fundamental_prescreen(cur, _df([_prev_worse("7777")])).iloc[0]
    assert pd.isna(r["gross_margin"])
    assert not bool(r["pass_three_rise"])


def test_missing_column_raises():
    bad = _df([_row("8888")]).drop(columns=["total_liab"])
    with pytest.raises(ValueError):
        run_fundamental_prescreen(bad, None)


def test_empty_current_returns_empty_with_columns():
    out = run_fundamental_prescreen(pd.DataFrame(), pd.DataFrame())
    assert out.empty
    for c in ("stock_id", "survivor", "pass_count"):
        assert c in out.columns


def test_dedup_stock_id_keep_first():
    cur = _df([_row("9999", eps=1.0), _row("9999", eps=9.0)])
    out = run_fundamental_prescreen(cur, None)
    assert (out["stock_id"] == "9999").sum() == 1
    assert out.iloc[0]["eps"] == 1.0        # keep first


def test_survivors_only_helper():
    cur = _df([_row("1001"), _row("1002", eps=-1.0)])  # 1002 EPS 負 → 淘汰
    prev = _df([_prev_worse("1001"), _prev_worse("1002")])
    out = run_fundamental_prescreen(cur, prev)
    surv = survivors_only(out)
    assert list(surv["stock_id"]) == ["1001"]


def test_property_pass_count_matches_bool_sum():
    # property:pass_count 永遠 = 四個布林欄之和,survivor ⟺ pass_count==4
    rng = np.random.default_rng(42)
    rows = [_row(str(6000 + i),
                 total_liab=float(rng.integers(100, 900)),
                 eps=float(rng.integers(-3, 5)),
                 current_assets=float(rng.integers(100, 900)),
                 gross_profit=float(rng.integers(100, 500))) for i in range(50)]
    cur = _df(rows)
    prev = _df([_prev_worse(str(6000 + i)) for i in range(50)])
    out = run_fundamental_prescreen(cur, prev)
    bool_sum = out[["pass_debt", "pass_three_rise", "pass_net_current",
                    "pass_eps_positive"]].sum(axis=1)
    assert (out["pass_count"] == bool_sum).all()
    assert (out["survivor"] == (out["pass_count"] == PRESCREEN_REQUIRED_PASSES)).all()


def test_debt_ratio_threshold_is_ssot():
    # golden:門檻恰為 DEBT_RATIO_MAX;剛好等於 → 不過(嚴格 <)
    exactly = DEBT_RATIO_MAX * 1000.0
    cur = _df([_row("1234", total_assets=1000.0, total_liab=exactly)])
    r = run_fundamental_prescreen(cur, _df([_prev_worse("1234")])).iloc[0]
    assert not bool(r["pass_debt"])         # 0.5 < 0.5 為 False


def test_real_snapshot_smoke():
    # 真實 parquet:能跑通、survivor 是全市場子集、金融股不在 survivor
    import pathlib
    base = pathlib.Path("data_cache/fundamentals")
    if not (base / "latest.json").exists():
        pytest.skip("無快照資料")
    cur = pd.concat([pd.read_parquet(base / f"{m}_115Q1.parquet") for m in ("sii", "otc")])
    prev = pd.concat([pd.read_parquet(base / f"{m}_114Q1.parquet") for m in ("sii", "otc")])
    out = run_fundamental_prescreen(cur, prev)
    assert len(out) > 1500                      # 全市場 ~1969
    surv = survivors_only(out)
    assert 0 < len(surv) < len(out)             # 有存活但非全部
    assert surv["survivor"].all()
    assert (surv["eps"] > 0).all()              # 存活股 EPS 必為正
    assert surv["debt_ratio"].max() < DEBT_RATIO_MAX
