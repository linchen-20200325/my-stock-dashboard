# -*- coding: utf-8 -*-
"""批 D2 — DL-f1-s61：季校準腳本外資缺值不再以 0 代入（`fb = 0 if pd.isna(...)`，等於 fillna(0)）。

三個最容易出錯的輸入（§6）：
1. foreign_buy 為 NaN → 傳給 market_regime 的是 None（缺席），不是 0（「買賣相抵」）
2. foreign_buy 有值 → 原值照傳
3. None 與 0 在 market_regime 的計分相同（皆 0 分）→ 校準分數不受影響，只是不再捏造觀測值
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

import scripts.calibrate_macro_traffic as cmt


def _feat(fb):
    return cmt._Features(
        date=pd.Timestamp("2026-09-01"), close=100.0, ma60=95.0, ma120=90.0,
        ma60_above_3d=True, ma60_below_3d=False, ma120_above_3d=True, ma120_below_3d=False,
        ma120_rising=True, ma120_falling=False, ma60_prev=94.0, vol_today=1.0, avg_vol_20=1.0,
        foreign_buy=fb)


def _spy(monkeypatch):
    # patch 真正持有者 market_strategy（src.services 是 PEP 562 轉發，不 patch 套件層）
    import src.services.market_strategy as svc
    seen = []
    real = svc.market_regime

    def _mr(*a, **k):
        seen.append(k.get("foreign_buy"))
        return real(*a, **k)
    monkeypatch.setattr(svc, "market_regime", _mr)
    return seen


@pytest.mark.parametrize("fb,want", [(float("nan"), None), (12.5, 12.5)])
def test_traffic_light_passes_none_for_missing(monkeypatch, fb, want):
    seen = _spy(monkeypatch)
    cmt._features_to_traffic_light(_feat(fb))
    assert seen == [want]


def test_backtest_cache_passes_none_for_missing(monkeypatch):
    seen = _spy(monkeypatch)
    f = _feat(float("nan"))
    monkeypatch.setattr(cmt, "_build_features_at", lambda df, t: f)
    df = pd.DataFrame({"Close": [100.0] * 150})
    out = cmt._backtest_with_inputs_cache(df)
    assert out and all(v is None for v in seen)
    assert all(row["cl_data"] is None for row in out)


def test_none_and_zero_score_identically():
    from src.services import market_regime
    kw = dict(index_close=100.0, ma60=95.0, ma120=90.0, ma60_above_3d=True, ma120_above_3d=True)
    a = market_regime(foreign_buy=None, **kw)
    b = market_regime(foreign_buy=0, **kw)
    sa = a.get("score") if isinstance(a, dict) else a[0]
    sb = b.get("score") if isinstance(b, dict) else b[0]
    assert math.isclose(float(sa), float(sb))
