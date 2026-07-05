"""全台股基本面初篩 L3 service 測試(編排 L1 loader + L2 prescreen + 快取)。

用 monkeypatch 注入假快照,避免依賴真實 parquet;另附真實資料 smoke。
"""
import numpy as np
import pandas as pd
import pytest

import src.services.fundamental_screener_service as svc


def _fake_snapshot():
    def _mk(ids, gp, op, net):
        return pd.DataFrame({
            "stock_id": ids, "revenue": [1000.0] * len(ids),
            "gross_profit": gp, "op_income": op, "net_income": net,
            "eps": [2.0] * len(ids), "total_assets": [1000.0] * len(ids),
            "total_liab": [400.0] * len(ids), "current_assets": [600.0] * len(ids),
        })
    current = _mk(["2330", "9999"], [400.0, 400.0], [300.0, 300.0], [200.0, 200.0])
    # 2330 去年三率全較低 → 三率三升成立;9999 去年毛利率較高 → 三率三升不過
    prev = _mk(["2330", "9999"], [300.0, 500.0], [200.0, 200.0], [100.0, 100.0])
    meta = {"roc_year": 115, "season": 1, "prev_roc_year": 114}
    return current, prev, meta


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(svc, "load_fundamentals_snapshot", lambda: _fake_snapshot())
    svc._clear(svc._prescreen_cached)     # 清掉可能的舊快取
    yield
    svc._clear(svc._prescreen_cached)


def test_get_prescreen_returns_df_and_meta(patched):
    df, meta = svc.get_fundamental_prescreen(refresh=True)
    assert set(df["stock_id"]) == {"2330", "9999"}
    assert "survivor" in df.columns
    assert meta["roc_year"] == 115


def test_get_survivors_only_all_pass(patched):
    surv, _ = svc.get_fundamental_survivors(refresh=True)
    assert surv["survivor"].all()
    assert list(surv["stock_id"]) == ["2330"]     # 9999 三率三升不過被剔


def test_get_survivor_ids(patched):
    ids = svc.get_survivor_ids(refresh=True)
    assert ids == ["2330"]
    assert all(isinstance(x, str) for x in ids)


def test_survivor_ids_empty_when_none_pass(monkeypatch):
    # 全部 EPS 負 → 無存活 → 回空 list(不炸)
    def _bad():
        cur = pd.DataFrame({
            "stock_id": ["1111"], "revenue": [1000.0], "gross_profit": [400.0],
            "op_income": [300.0], "net_income": [200.0], "eps": [-1.0],
            "total_assets": [1000.0], "total_liab": [400.0], "current_assets": [600.0],
        })
        return cur, pd.DataFrame(), {"roc_year": 115, "season": 1, "prev_roc_year": None}
    monkeypatch.setattr(svc, "load_fundamentals_snapshot", _bad)
    svc._clear(svc._prescreen_cached)
    assert svc.get_survivor_ids(refresh=True) == []
    svc._clear(svc._prescreen_cached)


def test_real_service_smoke():
    from src.data.stock.fundamentals_snapshot_loader import FUNDAMENTALS_CACHE_DIR
    if not (FUNDAMENTALS_CACHE_DIR / "latest.json").exists():
        pytest.skip("無快照資料")
    svc._clear(svc._prescreen_cached)
    ids = svc.get_survivor_ids(refresh=True)
    assert len(ids) > 50                    # 全市場四項全過應有數百檔
    assert "2330" in ids                    # 台積電為存活股(sanity)
    svc._clear(svc._prescreen_cached)
