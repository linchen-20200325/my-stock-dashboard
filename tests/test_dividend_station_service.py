"""💰 存股戰情室 L3：build_station_rows 組表（依賴注入,離線）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared import dividend_station_thresholds as T
from src.services import dividend_station_service as svc


def _wk(n=60, lo=80, hi=120):
    idx = pd.date_range("2022-01-07", periods=n, freq="W-FRI")
    return pd.Series(np.linspace(lo, hi, n), index=idx)


def _good_metrics(ticker):
    return {"weekly_close": _wk(), "premium_pct": 0.3, "sharpe": 1.1,
            "total_return_1y_pct": 15, "annual_yield_pct": 6, "inception_years": 8,
            "ann_return_3y_pct": 10, "cum_return_3y_pct": None,
            "peer_ranks": {m: 0.2 for m in T.PEER_WINDOWS_MONTHS}}


def test_build_rows_shape_and_pass():
    holdings = [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE}]
    rows = svc.build_station_rows(holdings, vix=18, metrics_fn=_good_metrics)
    assert len(rows) == 1
    r = rows[0]
    assert r["代號"] == "0056" and "核心" in r["類別"]
    for col in ("健檢", "235 燈號", "3-3-3", "建議動作", "_detail"):
        assert col in r
    assert r["3-3-3"].startswith("✅")


def test_build_rows_per_ticker_failure_is_isolated():
    def _bad(ticker):
        raise RuntimeError("no data")
    holdings = [{"ticker": "9999", "name": "壞檔", "asset_class": T.ASSET_SATELLITE}]
    rows = svc.build_station_rows(holdings, vix=None, metrics_fn=_bad)
    assert len(rows) == 1
    assert "資料不足/抓取失敗" in rows[0]["建議動作"]      # §1 誠實標記,不炸整表


def test_build_rows_mixed_good_and_bad():
    calls = {"n": 0}
    def _mixed(ticker):
        calls["n"] += 1
        if ticker == "BAD":
            raise ValueError("x")
        return _good_metrics(ticker)
    holdings = [{"ticker": "0056", "name": "A", "asset_class": T.ASSET_CORE},
                {"ticker": "BAD", "name": "B", "asset_class": T.ASSET_CORE}]
    rows = svc.build_station_rows(holdings, vix=18, metrics_fn=_mixed)
    assert len(rows) == 2
    assert rows[0]["3-3-3"].startswith("✅")
    assert "抓取失敗" in rows[1]["建議動作"]


def test_build_rows_skips_blank_ticker():
    rows = svc.build_station_rows([{"ticker": "  ", "name": ""}], vix=18, metrics_fn=_good_metrics)
    assert rows == []


def test_row_detail_has_health_and_235():
    holdings = [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE}]
    r = svc.build_station_rows(holdings, vix=18, metrics_fn=_good_metrics)[0]
    d = r["_detail"]
    for k in ("健檢A", "健檢B", "健檢C", "健檢D", "235觸發", "3-3-3明細"):
        assert k in d
