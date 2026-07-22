"""tests/test_portfolio_limits.py — 投組層級集中度守門(v19.151)。

驗 check_portfolio_limits:市值權重 → 單股 ≤10% / 持股 ≤10 檔 上限檢查。純函式離線可測。
接活 RiskController 早定義卻空轉的投組上限(個股組合風險貢獻區塊用)。
"""
from __future__ import annotations

from src.compute.risk.risk_control import check_portfolio_limits


def test_ok_ten_equal_at_threshold():
    # 10 檔各 10% —— 剛好等於上限(strict >,不算超標)、n=10 不超檔數 → OK
    w = {f"{2300 + i}": 100.0 for i in range(10)}
    r = check_portfolio_limits(w)
    assert r["n_positions"] == 10
    assert r["over_concentration"] == []          # 10.0% 不 > 10%
    assert r["too_many_positions"] is False
    assert r["ok"] is True
    assert r["max_weight_pct"] == 10.0


def test_over_concentration_flagged():
    r = check_portfolio_limits({"2330": 50, "2317": 30, "1101": 20})  # 50/30/20%
    codes = [c for c, _ in r["over_concentration"]]
    assert codes == ["2330", "2317", "1101"]      # 全 >10%,依權重降冪
    assert r["over_concentration"][0] == ("2330", 50.0)
    assert r["max_weight_pct"] == 50.0
    assert r["ok"] is False


def test_too_many_positions_flagged():
    # 11 檔等權 = 9.09% 各(未超單股),但 n=11 > 10 → 檔數超標
    w = {f"{2300 + i}": 1.0 for i in range(11)}
    r = check_portfolio_limits(w)
    assert r["n_positions"] == 11
    assert r["over_concentration"] == []          # 9.09% 未超 10%
    assert r["too_many_positions"] is True
    assert r["ok"] is False


def test_single_stock_is_over_concentrated():
    r = check_portfolio_limits({"2330": 1000.0})   # 1 檔 = 100%
    assert r["over_concentration"] == [("2330", 100.0)]
    assert r["ok"] is False                        # 全押一檔 = 過度集中(正確)


def test_empty_is_ok():
    r = check_portfolio_limits({})
    assert r["n_positions"] == 0 and r["ok"] is True
    assert r["max_weight_pct"] is None


def test_filters_invalid_weights():
    # 0 / 負 / None / NaN → 視為未持有,不計入
    r = check_portfolio_limits({
        "2330": 100.0, "2317": 0, "1101": -5, "2454": None, "3008": float("nan"),
    })
    assert r["n_positions"] == 1                    # 僅 2330 有效
    assert r["over_concentration"] == [("2330", 100.0)]


def test_scale_free_market_values():
    # 傳入的是市值(張數×1000×價),函式內部正規化為 % → 50/50
    r = check_portfolio_limits({"2330": 5_000_000.0, "2317": 5_000_000.0})
    assert {c: p for c, p in r["weights_pct"].items()} == {"2330": 50.0, "2317": 50.0}
    assert r["too_many_positions"] is False        # 2 檔 ≤ 10


def test_custom_thresholds():
    r = check_portfolio_limits({"a": 6, "b": 4}, single_max_pct=0.5, max_positions=1)
    assert r["over_concentration"] == [("a", 60.0)]   # 60% > 50%
    assert r["too_many_positions"] is True            # 2 檔 > 1
