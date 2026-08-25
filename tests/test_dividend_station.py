"""💰 存股戰情室 L2 純函式：健檢 ABCD / 235燈 / 3-3-3 / 週K。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
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


# ── 個股汰換：assess_stock（財報為主·KD為輔,§ user 2026-08）─────────────────
def _kd(label="無", cross=None, high=False, low=False, bear=False, bull=False,
        k=50.0, d=50.0):
    return {"k": k, "d": d, "label": label, "cross": cross,
            "high_passivation": high, "low_passivation": low,
            "bearish_divergence": bear, "bullish_divergence": bull}


def test_assess_stock_grade_f_bearish_kd_swap_out():
    """財報 F + KD 死亡交叉 → 🔴 換出（賣點確認）。"""
    sa = ds.assess_stock(ticker="1111", name="爛股", asset_class=T.ASSET_SATELLITE,
                         mj_grade="F", mj_score_pct=15, mj_headline="🔴 高危",
                         mj_fail_items=["負債比率", "流動比率", "現金"],
                         kd=_kd(label="死亡交叉", cross="death"))
    assert sa.swap_level == "🔴"
    assert "換出" in sa.swap_action and "賣點確認" in sa.swap_action


def test_assess_stock_grade_c_bullish_kd_batch():
    """財報 C（汰弱）但 KD 轉強（黃金交叉）→ 🟡 分批換/觀察（不急砍）。"""
    sa = ds.assess_stock(ticker="2222", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="C", mj_score_pct=40, mj_headline="🟡",
                         mj_fail_items=["毛利率"], kd=_kd(label="黃金交叉", cross="golden"))
    assert sa.swap_level == "🟡"
    assert "分批換" in sa.swap_action or "觀察" in sa.swap_action


def test_assess_stock_grade_c_neutral_kd_swap_out():
    """財報 C + KD 無明顯訊號 → 仍 🔴 換出（基本面主導）。"""
    sa = ds.assess_stock(ticker="3333", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="C", mj_score_pct=45, mj_headline="🟡",
                         mj_fail_items=["負債比率"], kd=_kd(label="無"))
    assert sa.swap_level == "🔴" and "換出" in sa.swap_action


def test_assess_stock_grade_a_high_passivation_strong_hold():
    """財報 A + KD 高檔鈍化 → 🟢 強勢續抱。"""
    sa = ds.assess_stock(ticker="4444", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="A", mj_score_pct=85, mj_headline="🟢",
                         mj_fail_items=[], kd=_kd(label="高檔鈍化", high=True, k=92, d=90))
    assert sa.swap_level == "🟢" and "強勢續抱" in sa.swap_action


def test_assess_stock_grade_a_bearish_kd_watch():
    """財報 A（佳）但 KD 短線轉弱（頂背離）→ 🟡 留意、暫不加碼（不換出）。"""
    sa = ds.assess_stock(ticker="5555", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="A", mj_score_pct=80, mj_headline="🟢",
                         mj_fail_items=[], kd=_kd(label="頂背離", bear=True))
    assert sa.swap_level == "🟡"
    assert "留意" in sa.swap_action and "換出" not in sa.swap_action


def test_assess_stock_grade_b_neutral_hold():
    """財報 B（非汰弱門檻）+ KD 中性 → 🟢 續抱。"""
    sa = ds.assess_stock(ticker="6666", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="B", mj_score_pct=65, mj_headline="🔵",
                         mj_fail_items=[], kd=_kd(label="無"))
    assert sa.swap_level == "🟢" and "續抱" in sa.swap_action


def test_assess_stock_no_financials_data_insufficient():
    """財報資料不足（grade=None）→ ⚪ 只供 KD 參考,不猜、不捏 grade（§1）。"""
    sa = ds.assess_stock(ticker="7777", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade=None, mj_score_pct=None, mj_headline="",
                         mj_fail_items=None, kd=_kd(label="低檔鈍化", low=True))
    assert sa.swap_level == "⚪" and "資料不足" in sa.swap_action
    assert sa.mj_grade is None


def test_assess_stock_no_kd_still_fundamentals_only():
    """KD 資料不足（kd=None）→ 仍用財報判:F → 🔴 換出;kd_label 標資料不足。"""
    sa = ds.assess_stock(ticker="8888", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="F", mj_score_pct=10, mj_headline="🔴",
                         mj_fail_items=["現金"], kd=None)
    assert sa.swap_level == "🔴" and "換出" in sa.swap_action
    assert sa.kd_label == "資料不足"


def test_assess_stock_unknown_grade_treated_as_insufficient():
    """上游 grade 非已知分級（契約漂移/髒值）→ ⚪ 不判定,不誤判續抱（§1）。

    ⚠️ 2026-08-25 更新斷言：原本要求動作文字含「資料不足」，但那**正是要修的問題** ——
    「沒抓到」跟「上游給了一個不在分級表裡的值」是兩件事：前者重跑就好，後者是
    上下游契約破了（程式要修），畫成「資料不足」等於保證沒有人會去修它。
    **判燈結果不變**（仍是 ⚪、仍只供 KD 參考），只是原因說對。
    """
    sa = ds.assess_stock(ticker="9999", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="ZZZ", mj_score_pct=50, mj_headline="?",
                         mj_fail_items=[], kd=_kd(label="無"))
    assert sa.swap_level == "⚪"                       # 判燈不變
    assert sa.miss_reason == SS.MISS_CONTRACT_DRIFT    # 但原因是「契約漂移」不是「缺資料」
    assert "ZZZ" in sa.swap_action, "要指出是哪個值不認得,否則沒人查得到"


def test_assess_stock_missing_grade_is_not_contract_drift():
    """對照組：真的沒抓到 → 同樣 ⚪,但原因是「沒抓到」(可重跑),文案維持原樣。"""
    sa = ds.assess_stock(ticker="9999", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade=None, mj_score_pct=None, mj_headline="",
                         mj_fail_items=[], kd=_kd(label="無"))
    assert sa.swap_level == "⚪" and "資料不足" in sa.swap_action
    assert sa.miss_reason == SS.MISS_NO_INPUT


def test_sharpe_weekly_rf_lowers_sharpe():
    """B2:rf>0 → 超額報酬下降 → sharpe 較 rf=0 低(health_b「無超額報酬」名副其實)。"""
    idx = pd.date_range("2022-01-07", periods=30, freq="W-FRI")
    up = pd.Series(np.linspace(100, 130, 30), index=idx)
    s0 = ds.sharpe_weekly(up, rf_pct=0.0)
    s5 = ds.sharpe_weekly(up, rf_pct=5.33)
    assert s0 is not None and s5 is not None and s5 < s0


def test_assess_stock_breakdown_early_warning():
    """B3:財報 grade OK(B)但盈轉虧/逐季惡化 → 提前 🟡 減碼(不再 🟢 續抱)。"""
    sa = ds.assess_stock(ticker="2330", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="B", mj_score_pct=60, mj_headline="", mj_fail_items=[],
                         kd=_kd(label="無"), trend={"is_breakdown": True})
    assert sa.swap_level == "🟡" and "盈轉虧" in sa.swap_action


def test_assess_stock_ok_no_breakdown_still_hold():
    """B3:grade OK 且無惡化 → 維持 🟢 續抱(不誤觸發)。"""
    sa = ds.assess_stock(ticker="2330", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade="B", mj_score_pct=60, mj_headline="", mj_fail_items=[],
                         kd=_kd(label="無"), trend={"is_breakdown": False})
    assert sa.swap_level == "🟢"
