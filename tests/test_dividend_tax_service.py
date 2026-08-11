"""tests/test_dividend_tax_service.py — 配息稅後試算 L3 service 編排 + §1/§4.6 降級。

monkeypatch L1 取配息 + L2 幣別判定;測「編排 + 海外排除 + 逐筆健保 + 近1年過濾」。
稅務 math 已於 test_dividend_tax 單測,本檔不重測。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

import src.services.dividend_tax_service as svc


def _recent_monthly(n=12, per_share=1.0):
    today = pd.Timestamp(dt.date.today())
    idx = pd.DatetimeIndex([today - pd.Timedelta(days=30 * i) for i in range(n)])
    return pd.Series([per_share] * n, index=idx)


def test_usd_etf_excluded_and_flagged(monkeypatch):
    """§4.6:美元 ETF 排除稅務計算,僅標記於 overseas。"""
    monkeypatch.setattr(svc, "holding_currency", lambda t: "USD" if t == "BND" else "TWD")
    monkeypatch.setattr(svc, "fetch_etf_dividends", lambda t: _recent_monthly())
    v = svc.get_dividend_tax_view(
        [{"ticker": "BND", "shares": 100}, {"ticker": "00980D", "shares": 30000}])
    assert v["overseas"] == ["BND"]
    assert [r["代號"] for r in v["per_etf"]] == ["00980D"]
    assert v["n_tw"] == 1


def test_tw_monthly_nhi_per_payment(monkeypatch):
    """月配、每筆 3 萬(≥2萬)→ 逐筆健保 floor(30000×2.11%)=633,12 筆。"""
    monkeypatch.setattr(svc, "holding_currency", lambda t: "TWD")
    monkeypatch.setattr(svc, "fetch_etf_dividends", lambda t: _recent_monthly(12, 1.0))
    v = svc.get_dividend_tax_view([{"ticker": "00980D", "shares": 30000}],
                                  marginal_rate=0.20)
    assert v["per_etf"][0]["二代健保"] == 633 * 12
    assert v["summary"]["gross"] == 360_000
    assert v["summary"]["nhi_premium"] == 633 * 12
    assert v["summary"]["income_tax"] is not None      # 有選邊際率 → 有綜所稅


def test_tw_small_monthly_below_threshold_no_nhi(monkeypatch):
    """月配、每筆 1.5 萬(<2萬)→ 逐筆免健保(不年度加總比門檻)。"""
    monkeypatch.setattr(svc, "holding_currency", lambda t: "TWD")
    monkeypatch.setattr(svc, "fetch_etf_dividends", lambda t: _recent_monthly(12, 1.0))
    v = svc.get_dividend_tax_view([{"ticker": "A.TW", "shares": 15000}])
    assert v["per_etf"][0]["二代健保"] == 0
    assert v["summary"]["gross"] == 180_000
    assert v["summary"]["income_tax"] is None          # 未選邊際率 → 不算綜所稅


def test_recent_filter_excludes_old_payment(monkeypatch):
    """只計近 1 年;800 天前那筆不計(§2.3 近1年窗)。"""
    monkeypatch.setattr(svc, "holding_currency", lambda t: "TWD")
    today = pd.Timestamp(dt.date.today())
    s = pd.Series([1.0, 1.0], index=pd.DatetimeIndex(
        [today - pd.Timedelta(days=10), today - pd.Timedelta(days=800)]))
    monkeypatch.setattr(svc, "fetch_etf_dividends", lambda t: s)
    v = svc.get_dividend_tax_view([{"ticker": "A.TW", "shares": 30000}])
    assert v["per_etf"][0]["配息筆數"] == 1
    assert v["summary"]["gross"] == 30_000


def test_no_dividends_is_zero(monkeypatch):
    """§1:抓不到配息 → 0,不捏造。"""
    monkeypatch.setattr(svc, "holding_currency", lambda t: "TWD")
    monkeypatch.setattr(svc, "fetch_etf_dividends", lambda t: None)
    v = svc.get_dividend_tax_view([{"ticker": "A.TW", "shares": 1000}], marginal_rate=0.20)
    assert v["summary"]["gross"] == 0
    assert v["per_etf"][0]["配息筆數"] == 0
    assert v["summary"]["net_after_all"] == 0


def test_invalid_holdings_skipped(monkeypatch):
    """空代號 / 股數 ≤0 → 跳過。"""
    monkeypatch.setattr(svc, "holding_currency", lambda t: "TWD")
    monkeypatch.setattr(svc, "fetch_etf_dividends", lambda t: _recent_monthly())
    v = svc.get_dividend_tax_view([{"ticker": "", "shares": 100},
                                   {"ticker": "A.TW", "shares": 0}])
    assert v["per_etf"] == [] and v["overseas"] == []
