"""💰 存股戰情室 L2 純函式：健檢 ABCD / 235燈 / 3-3-3 / 週K。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from src.compute.etf import dividend_station as ds


def _daily(closes, start="2023-01-02"):
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.Series(closes, index=idx, dtype=float)


def _weekly(n, val=100.0, start="2022-01-07"):
    idx = pd.date_range(start, periods=n, freq="W-FRI")
    return pd.Series([val] * n, index=idx, dtype=float)


# ── 週K resample ────────────────────────────────────────────────────────
def test_weekly_closes_uses_friday_last():
    s = _daily(list(range(1, 21)))          # 20 交易日 ≈ 4 週
    wk = ds.weekly_closes(s)
    assert isinstance(wk.index, pd.DatetimeIndex)
    assert (wk.index.weekday == 4).all(), "週標籤應為週五(W-FRI)"


def test_weekly_closes_drops_incomplete_current_week():
    # 造到週三收尾 → 當週未收完應被丟棄
    idx = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])  # 一~三
    s = pd.Series([10, 11, 12], index=idx, dtype=float)
    wk = ds.weekly_closes(s)
    assert len(wk) == 0, "未到週五的當週不可納入（防 lookahead）"


def test_weekly_closes_empty_raises():
    with pytest.raises(ValueError):
        ds.weekly_closes(pd.Series([], dtype=float))


def test_weekly_closes_descending_input_not_dropping_complete_week():
    """稽核 M2：台股常新→舊排序;不排序會誤刪整週。升冪/降冪結果須一致。"""
    s = _daily(list(range(1, 41)))          # 到週五收尾
    asc = ds.weekly_closes(s)
    desc = ds.weekly_closes(s.iloc[::-1])   # 反轉成降冪
    assert len(asc) == len(desc) and asc.index[-1] == desc.index[-1]


def test_bollinger_z_nan_last_returns_none():
    """稽核 L5：最新值 NaN → 回 None（不可回 NaN 被 235 誤當「全清」）。"""
    idx = pd.date_range("2022-01-07", periods=21, freq="W-FRI")
    vals = list(np.linspace(100, 120, 20)) + [np.nan]
    assert ds.bollinger_z(pd.Series(vals, index=idx)) is None


# ── 布林 / 均線 ─────────────────────────────────────────────────────────
def test_bollinger_z_insufficient_returns_none():
    assert ds.bollinger_z(_weekly(10)) is None


def test_bollinger_z_flat_series_returns_none():
    assert ds.bollinger_z(_weekly(25, 100.0)) is None       # 無波動 std=0


def test_bollinger_z_negative_when_below_mean():
    wk = _weekly(19, 100.0)
    wk = pd.concat([wk, pd.Series([80.0], index=[wk.index[-1] + pd.Timedelta(weeks=1)])])
    z = ds.bollinger_z(wk)
    assert z is not None and z < 0


def test_week_ma_slope_down():
    idx = pd.date_range("2022-01-07", periods=15, freq="W-FRI")
    wk = pd.Series(np.linspace(120, 100, 15), index=idx)     # 下降
    assert ds.week_ma_slope(wk, T.MA_QUARTER_WEEKS) < 0


# ── 報酬 / 配息 / 夏普 helper ────────────────────────────────────────────
def test_annual_yield_pct():
    assert ds.annual_yield_pct(6.0, 100.0) == 6.0
    assert ds.annual_yield_pct(None, 100.0) is None
    assert ds.annual_yield_pct(6.0, 0.0) is None


def test_total_and_annualized_return():
    assert ds.total_return_pct(100.0, 121.0) == pytest.approx(21.0)
    assert ds.annualized_return_pct(100.0, 121.0, 2.0) == pytest.approx(10.0, abs=1e-6)
    assert ds.total_return_pct(0.0, 121.0) is None
    assert ds.annualized_return_pct(100.0, 121.0, 0.0) is None


def test_sharpe_weekly_positive_and_insufficient():
    idx = pd.date_range("2022-01-07", periods=30, freq="W-FRI")
    up = pd.Series(np.linspace(100, 130, 30), index=idx)
    assert ds.sharpe_weekly(up) > 0
    assert ds.sharpe_weekly(_weekly(5)) is None          # 不足
    assert ds.sharpe_weekly(_weekly(30, 100.0)) is None  # 無波動


def test_inception_years():
    first = pd.Timestamp("2015-01-01")
    assert ds.inception_years(first, pd.Timestamp("2025-01-01")) == pytest.approx(10.0, abs=0.1)
    assert ds.inception_years(None, pd.Timestamp("2025-01-01")) is None


# ── 健檢 ────────────────────────────────────────────────────────────────
def test_health_a_eats_principal():
    assert ds.health_a(3.0, 6.0).level == "🔴"              # 報酬 < 配息 → 吃本金
    assert ds.health_a(8.0, 6.0).level == "🟢"
    assert ds.health_a(None, 6.0).level == "⚪"


def test_health_b_negative_sharpe():
    assert ds.health_b(-0.3).level == "🔴"
    assert ds.health_b(0.5).level == "🟢"
    assert ds.health_b(None).level == "⚪"


def test_health_c_trend_weak():
    idx = pd.date_range("2022-01-07", periods=20, freq="W-FRI")
    wk = pd.Series(np.linspace(130, 100, 20), index=idx)     # 收在季線下且下彎
    assert ds.health_c(wk).level == "🟡"


def test_health_d_premium():
    assert ds.health_d(2.0).level == "🟡"
    assert ds.health_d(0.5).level == "🟢"
    assert ds.health_d(None).level == "⚪"


# ── 235 三取一 Max ──────────────────────────────────────────────────────
def test_235_cruise():
    r = ds.light_235(vix=15, weekly_close=110, ma4w=105, ma13w=100, ma52w=95, z=0.5)
    assert r.light == T.LIGHT_CRUISE


def test_235_light1_small_dip():
    r = ds.light_235(vix=22, weekly_close=110, ma4w=105, ma13w=100, ma52w=95, z=0.5)
    assert r.light == T.LIGHT_1 and r.deploy_pct == T.DEPLOY_LIGHT1_PCT


def test_235_takes_max_severity():
    # VIX 22(燈一) + 週收<季線(燈二) + z<-3(燈三) → 取最嚴重燈三
    r = ds.light_235(vix=22, weekly_close=80, ma4w=95, ma13w=90, ma52w=100, z=-3.5)
    assert r.light == T.LIGHT_3
    assert any("布林<-3σ" in x for x in r.reasons)


def test_235_light3_vix_crash():
    r = ds.light_235(vix=35, weekly_close=110, ma4w=105, ma13w=100, ma52w=95, z=0.0)
    assert r.light == T.LIGHT_3 and any("VIX" in x for x in r.reasons)


def test_235_take_profit_force():
    r = ds.light_235(vix=15, weekly_close=140, ma4w=120, ma13w=110, ma52w=100, z=3.5)
    assert r.light == T.LIGHT_TAKE_PROFIT and r.take_profit == "force"


def test_235_deepwater_wait_confirmation():
    # 週收破年線但布林未達 -2σ → 深水防守：等共伴確認
    r = ds.light_235(vix=15, weekly_close=94, ma4w=96, ma13w=97, ma52w=100, z=-1.5)
    assert r.deepwater_note and "共伴確認" in r.deepwater_note


def test_235_deepwater_recovery():
    # 破年線但站回季線 → 落底回升留意
    r = ds.light_235(vix=15, weekly_close=98, ma4w=96, ma13w=97, ma52w=100, z=-0.5)
    assert r.deepwater_note and "落底回升" in r.deepwater_note


def test_235_missing_all_inputs_is_cruise():
    r = ds.light_235(vix=None, weekly_close=None, ma4w=None, ma13w=None, ma52w=None, z=None)
    assert r.light == T.LIGHT_CRUISE          # 缺值不觸發任何條件（§1）


# ── 3-3-3 ───────────────────────────────────────────────────────────────
def _peers(v):
    return {m: v for m in T.PEER_WINDOWS_MONTHS}


def test_333_all_pass():
    r = ds.screen_333(inception_years=5, ann_return_3y_pct=9, cum_return_3y_pct=None,
                      peer_ranks=_peers(0.2))
    assert r.passed is True


def test_333_new_fund_fails_inception():
    r = ds.screen_333(inception_years=1.5, ann_return_3y_pct=9, cum_return_3y_pct=None,
                      peer_ranks=_peers(0.2))
    assert r.passed is False and r.inception_ok is False


def test_333_cum_return_alternative_passes():
    r = ds.screen_333(inception_years=4, ann_return_3y_pct=None, cum_return_3y_pct=25,
                      peer_ranks=_peers(0.1))
    assert r.return_ok is True and r.passed is True


def test_333_peer_not_top_third_fails():
    r = ds.screen_333(inception_years=4, ann_return_3y_pct=9, cum_return_3y_pct=None,
                      peer_ranks=_peers(0.5))      # 後段班
    assert r.peer_ok is False and r.passed is False


def test_333_missing_peer_is_undecided_not_pass():
    r = ds.screen_333(inception_years=4, ann_return_3y_pct=9, cum_return_3y_pct=None,
                      peer_ranks=None)
    assert r.peer_ok is None and r.passed is False   # 不可判定不放行（§1）


# ── 彙總 ────────────────────────────────────────────────────────────────
def test_assess_holding_integration():
    idx = pd.date_range("2022-01-07", periods=60, freq="W-FRI")
    wk = pd.Series(np.linspace(80, 120, 60), index=idx)     # 上升
    a = ds.assess_holding(
        ticker="0056", name="高股息", asset_class=T.ASSET_CORE, weekly_close=wk,
        vix=18, premium_pct=0.3, sharpe=1.2, total_return_1y_pct=15, annual_yield_pct=6,
        inception_years=8, ann_return_3y_pct=10, cum_return_3y_pct=None,
        peer_ranks=_peers(0.2))
    assert a.ticker == "0056"
    assert a.worst_health in ("🟢", "🟡", "🔴", "⚪")
    assert a.screen.passed is True


def _assess(**kw):
    idx = pd.date_range("2022-01-07", periods=60, freq="W-FRI")
    base = dict(ticker="X", name="", asset_class=T.ASSET_CORE,
                weekly_close=pd.Series(np.linspace(80, 120, 60), index=idx),
                vix=15, premium_pct=0.3, sharpe=1.0, total_return_1y_pct=15,
                annual_yield_pct=6, inception_years=8, ann_return_3y_pct=10,
                cum_return_3y_pct=None, peer_ranks=_peers(0.2))
    base.update(kw)
    return ds.assess_holding(**base)


def test_suggest_action_cull_on_principal_eat():
    a = _assess(total_return_1y_pct=2, annual_yield_pct=6)   # 吃本金
    assert ds.suggest_action(a).startswith("🔴 汰弱")


def test_suggest_action_trend_weak_pauses_add():
    # 造 235 亮燈(VIX高) 但季線轉弱 → 暫停加碼
    idx = pd.date_range("2022-01-07", periods=60, freq="W-FRI")
    wk = pd.Series(np.linspace(130, 100, 60), index=idx)     # 下彎、收季線下
    a = _assess(weekly_close=wk, vix=22, sharpe=1.0, total_return_1y_pct=15, annual_yield_pct=6)
    assert "暫停加碼" in ds.suggest_action(a)


def test_suggest_action_cruise():
    a = _assess()
    assert ds.suggest_action(a).startswith("⚪ 巡航")


def test_assess_holding_stock_kind_skips_d_and_333():
    """個股：D折溢價、3-3-3 不適用（即使給值也不判）；A/B/C/235 照跑。"""
    idx = pd.date_range("2022-01-07", periods=60, freq="W-FRI")
    wk = pd.Series(np.linspace(80, 120, 60), index=idx)
    a = ds.assess_holding(
        ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
        asset_kind=T.KIND_STOCK, weekly_close=wk, vix=18,
        premium_pct=1.9, sharpe=1.0, total_return_1y_pct=20, annual_yield_pct=2,
        inception_years=10, ann_return_3y_pct=15, cum_return_3y_pct=None,
        peer_ranks={m: 0.1 for m in T.PEER_WINDOWS_MONTHS})
    assert a.asset_kind == T.KIND_STOCK
    assert a.health_d.level == "⚪" and "個股不適用" in a.health_d.msg   # premium 1.9 不判 🟡
    assert a.screen.passed is False and "個股不適用" in a.screen.detail  # peer 0.1 不判 ✅
    assert a.health_b.level == "🟢"                                     # B/C/235 仍照跑


def test_assess_holding_empty_raises():
    with pytest.raises(ValueError):
        ds.assess_holding(
            ticker="X", name="", asset_class=T.ASSET_CORE, weekly_close=pd.Series([], dtype=float),
            vix=18, premium_pct=None, sharpe=None, total_return_1y_pct=None, annual_yield_pct=None,
            inception_years=None, ann_return_3y_pct=None, cum_return_3y_pct=None, peer_ranks=None)
