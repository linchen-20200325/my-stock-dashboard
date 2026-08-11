"""tests/test_watchlist_health_service.py — 組合體檢 L3 service 編排 + §1 降級。

monkeypatch L1 取價 + L2 指標(math 已於 test_asset_lag / etf_calc 各自單測),
本檔專測「編排 + 誠實降級」:基準對映、非台股不判、缺價/樣本不足/例外逐檔隔離、去重。
classify_lag_verdict 保留真實 → 驗證指標→燈號整合。
"""
from __future__ import annotations

import pandas as pd
import pytest

import src.services.watchlist_health_service as svc


def _price_df(n=200, start="2025-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    return pd.DataFrame({"Close": [100.0 + i for i in range(n)]}, index=idx)


def _patch(monkeypatch, *, price=None, metrics=None, vb=None, raise_fetch=False):
    def _fetch(t, *a, **k):
        if raise_fetch:
            raise RuntimeError("boom")
        return price if price is not None else _price_df()
    monkeypatch.setattr(svc, "fetch_etf_price", _fetch)
    if metrics is not None:
        monkeypatch.setattr(svc, "calc_weakness_metrics", lambda *a, **k: dict(metrics))
    if vb is not None:
        monkeypatch.setattr(svc, "compute_portfolio_vs_benchmark", lambda *a, **k: vb)


_GOOD_VB = {"benchmark_ok": True,
            "final": {"portfolio": 0.05, "benchmark": 0.20, "per_asset": {}}}


def test_etf_maps_to_0050_and_flags_streak(monkeypatch):
    _patch(monkeypatch,
           metrics={"quarter_lose_streak": 3, "down_ratio": 70, "up_ratio": 70, "sample": 200},
           vb=_GOOD_VB)
    row = svc.evaluate_one("00980A.TW")
    assert row["類型"] == "ETF"
    assert row["基準"] == "0050.TW"
    assert row["連敗季數"] == 3
    assert row["相對基準%"] == -15.0            # (0.05-0.20)*100
    assert row["燈號"] == "🚨 連續3季輸盤"


def test_stock_maps_to_twii(monkeypatch):
    _patch(monkeypatch,
           metrics={"quarter_lose_streak": 0, "down_ratio": 10, "up_ratio": 10, "sample": 200},
           vb=_GOOD_VB)
    row = svc.evaluate_one("2330.TW")
    assert row["類型"] == "個股"
    assert row["基準"] == "^TWII"
    assert row["燈號"] == "🟢 體質正常"


def test_non_tw_ticker_not_judged_and_no_fetch(monkeypatch):
    """§4.6:非台股代號 → 不硬選基準、不抓價。"""
    calls = {"n": 0}
    def _fetch(t, *a, **k):
        calls["n"] += 1
        return _price_df()
    monkeypatch.setattr(svc, "fetch_etf_price", _fetch)
    row = svc.evaluate_one("^TWII")
    assert row["燈號"] == "⚪ 無法判定（非台股代號）"
    assert calls["n"] == 0                       # 沒判定就不該打 API


def test_empty_price_is_insufficient(monkeypatch):
    _patch(monkeypatch, price=pd.DataFrame({"Close": []}))
    row = svc.evaluate_one("00980A.TW")
    assert row["燈號"] == "⚪ 價格資料不足"


def test_insufficient_sample_honest(monkeypatch):
    """§1:calc_weakness_metrics 回 _err(新上市<30天)→ 樣本不足,不外推。"""
    _patch(monkeypatch, metrics={"_err": "insufficient_data", "sample": 12}, vb=_GOOD_VB)
    row = svc.evaluate_one("00980A.TW")
    assert row["燈號"] == "⚪ 樣本不足 (n=12)"
    assert row["連敗季數"] is None               # 指標不填


def test_fetch_exception_isolated(monkeypatch):
    _patch(monkeypatch, raise_fetch=True)
    row = svc.evaluate_one("2330.TW")
    assert row["燈號"].startswith("⚪ 抓取失敗")


def test_benchmark_not_ok_relative_pct_none(monkeypatch):
    """基準對不上共同日 → 相對% 為 None(不畫假),但其餘指標仍給。"""
    _patch(monkeypatch,
           metrics={"quarter_lose_streak": 0, "down_ratio": 10, "up_ratio": 10, "sample": 200},
           vb={"benchmark_ok": False, "final": {"portfolio": None, "benchmark": None, "per_asset": {}}})
    row = svc.evaluate_one("2330.TW")
    assert row["相對基準%"] is None
    assert row["燈號"] == "🟢 體質正常"


def test_otc_two_fallback_user_holding(monkeypatch):
    """DEFECT 1 回歸:00980D 是上櫃(.TWO)ETF —— .TW 抓不到應 fallback .TWO,
    不得誤標「價格資料不足」(否則使用者的實際持股會顯示無資料)。"""
    def _fetch(t, *a, **k):
        if t.endswith(".TWO") or t in ("0050.TW", "^TWII"):
            return _price_df()
        return pd.DataFrame({"Close": []})       # .TW 一律空
    monkeypatch.setattr(svc, "fetch_etf_price", _fetch)
    monkeypatch.setattr(svc, "calc_weakness_metrics",
                        lambda *a, **k: {"quarter_lose_streak": 0, "down_ratio": 10,
                                         "up_ratio": 10, "sample": 200})
    monkeypatch.setattr(svc, "compute_portfolio_vs_benchmark", lambda *a, **k: _GOOD_VB)
    row = svc.evaluate_one("00980D")             # 裸碼上櫃 ETF
    assert row["代號"] == "00980D.TWO"           # 用 .TWO 抓到,顯示 .TWO
    assert row["基準"] == "0050.TW"
    assert row["燈號"] == "🟢 體質正常"           # 有資料 → 正常判定,非「資料不足」


def test_otc_two_fallback_stock(monkeypatch):
    """上櫃個股(裸碼)同樣 .TW→.TWO fallback。"""
    def _fetch(t, *a, **k):
        return _price_df() if (t.endswith(".TWO") or t == "^TWII") else pd.DataFrame({"Close": []})
    monkeypatch.setattr(svc, "fetch_etf_price", _fetch)
    monkeypatch.setattr(svc, "calc_weakness_metrics",
                        lambda *a, **k: {"quarter_lose_streak": 0, "down_ratio": 10,
                                         "up_ratio": 10, "sample": 200})
    monkeypatch.setattr(svc, "compute_portfolio_vs_benchmark", lambda *a, **k: _GOOD_VB)
    row = svc.evaluate_one("6488")
    assert row["代號"] == "6488.TWO"
    assert row["基準"] == "^TWII"


def test_get_rows_dedup_bare_vs_suffix(monkeypatch):
    """DEFECT 2 回歸:'2330' 與 '2330.TW' 視為同檔,去重成一列(不重複抓價)。"""
    _patch(monkeypatch,
           metrics={"quarter_lose_streak": 0, "down_ratio": 10, "up_ratio": 10, "sample": 200},
           vb=_GOOD_VB)
    rows = svc.get_watchlist_health_rows(["2330", "2330.TW", "00980A.TW"])
    assert len(rows) == 2                        # 2330/2330.TW 合一 + 00980A
    assert [r["代號"] for r in rows] == ["2330.TW", "00980A.TW"]


def test_get_rows_dedup_and_order(monkeypatch):
    _patch(monkeypatch,
           metrics={"quarter_lose_streak": 0, "down_ratio": 10, "up_ratio": 10, "sample": 200},
           vb=_GOOD_VB)
    rows = svc.get_watchlist_health_rows(["2330.TW", "2330.tw", " 2330.TW ", "00980A.TW"])
    assert [r["代號"] for r in rows] == ["2330.TW", "00980A.TW"]


def test_summarize_laggards(monkeypatch):
    rows = [
        {"代號": "A", "燈號": "🚨 連續3季輸盤"},
        {"代號": "B", "燈號": "🟢 體質正常"},
        {"代號": "C", "燈號": "🔴 雙向弱勢"},
        {"代號": "D", "燈號": "⚪ 樣本不足 (n=5)"},
    ]
    assert [r["代號"] for r in svc.summarize_laggards(rows)] == ["A", "C"]
