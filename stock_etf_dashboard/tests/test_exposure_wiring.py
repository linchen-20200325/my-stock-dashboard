"""L1+L3：真實 fetch_etf_holdings 解析 + 從持股自動穿透（依賴注入，離線）。"""
import pandas as pd
import pytest

from stock_etf_dashboard.core import constants as C
from stock_etf_dashboard.core.circuit_breaker import FailLoudError, isclose
from stock_etf_dashboard.repositories import etf_repo
from stock_etf_dashboard.repositories.sheets_repo import InMemoryStore
from stock_etf_dashboard.services import exposure_service as exs


# ── L1 成分解析 ─────────────────────────────────────────────────────────
def _yf_holdings(pairs):
    """模擬 yfinance top_holdings：Symbol 索引 + Name + Holding Percent。"""
    idx = pd.Index([s for s, _ in pairs], name="Symbol")
    return pd.DataFrame({"Name": ["-"] * len(pairs),
                         "Holding Percent": [w for _, w in pairs]}, index=idx)


def test_normalize_fraction_to_percent_and_strip_suffix():
    raw = _yf_holdings([("2330.TW", 0.47), ("2317.TW", 0.045)])
    h = etf_repo._normalize_holdings(raw)
    assert h == {"2330": 47.0, "2317": 4.5}


def test_normalize_already_percent_unchanged():
    raw = _yf_holdings([("2330.TW", 40.0), ("2317.TW", 20.0)])
    h = etf_repo._normalize_holdings(raw)
    assert h == {"2330": 40.0, "2317": 20.0}


def test_normalize_empty_raises():
    with pytest.raises(FailLoudError):
        etf_repo._normalize_holdings(pd.DataFrame())


def test_normalize_skips_nan_weight():
    raw = _yf_holdings([("2330.TW", 0.5), ("XXXX.TW", float("nan"))])
    h = etf_repo._normalize_holdings(raw)
    assert "2330" in h and "XXXX" not in h


def test_yahoo_symbol_suffix():
    assert etf_repo._yahoo_symbol("0050") == "0050.TW"
    assert etf_repo._yahoo_symbol("0050.TW") == "0050.TW"
    assert etf_repo._yahoo_symbol("SPY") == "SPY"


# ── ETF 判定 ────────────────────────────────────────────────────────────
def test_is_tw_etf():
    assert exs.is_tw_etf("0050.TW") is True
    assert exs.is_tw_etf("00878") is True
    assert exs.is_tw_etf("2330.TW") is False


# ── L3 自動穿透（注入假 price/holdings）─────────────────────────────────
def _store_with(holdings):
    s = InMemoryStore()
    for h in holdings:
        s.upsert_holding(h)
    return s


def test_build_exposure_de_double_count_and_incomplete():
    store = _store_with([
        {"ticker": "2330.TW", "lots": 2, "avg_price": 900},   # 直接
        {"ticker": "0050.TW", "lots": 5, "avg_price": 140},   # ETF 含 2330
        {"ticker": "00878.TW", "lots": 3, "avg_price": 21},   # ETF 成分抓不到
    ])
    prices = {"2330": 900.0, "0050": 140.0, "00878": 21.0}

    def price_fn(code):
        return prices[code.split(".")[0]]

    def holdings_fn(code):
        if code.split(".")[0] == "0050":
            return {"2330": 47.0, "2317": 4.5}
        raise FailLoudError(f"{code} 成分抓不到")

    res = exs.build_portfolio_exposure(store, price_fn=price_fn, holdings_fn=holdings_fn)
    rep = res.report
    # 市值：2330直=2*900*1000=1.8M；0050=0.7M；00878=63k；total=2.563M
    assert isclose(rep.total_value, 2_563_000.0)
    row2330 = next(r for r in rep.rows if r.name == "2330")
    assert isclose(row2330.via_direct, 1_800_000.0)
    assert isclose(row2330.via_etf, 329_000.0)      # 0.7M*0.47
    assert row2330.breach is True                    # 83% > 30%
    assert "2330" in rep.alerts
    assert rep.is_complete is False                  # 00878 成分未知
    assert "00878" in rep.incomplete_etfs
    assert res.etf_tickers == ["0050", "00878"]


def test_build_exposure_skips_no_price_not_fabricated():
    store = _store_with([
        {"ticker": "2330.TW", "lots": 2, "avg_price": 900},
        {"ticker": "9999.TW", "lots": 1, "avg_price": 10},    # 無現價
    ])

    def price_fn(code):
        if code.split(".")[0] == "9999":
            raise FailLoudError("9999 無現價")
        return 900.0

    res = exs.build_portfolio_exposure(store, price_fn=price_fn,
                                       holdings_fn=lambda c: None)
    assert [x["ticker"] for x in res.skipped_no_price] == ["9999.TW"]
    assert "2330" in res.priced and "9999" not in res.priced
    # 只有 2330 有現價 → 曝險 100%
    row = next(r for r in res.report.rows if r.name == "2330")
    assert isclose(row.exposure_pct, 100.0)


def test_build_exposure_empty_portfolio_raises():
    with pytest.raises(FailLoudError):
        exs.build_portfolio_exposure(InMemoryStore(),
                                     price_fn=lambda c: 1.0,
                                     holdings_fn=lambda c: None)


def test_shares_per_lot_is_ssot():
    # 市值換算用 SSOT 常數（§3.3）
    store = _store_with([{"ticker": "2330.TW", "lots": 1, "avg_price": 900}])
    res = exs.build_portfolio_exposure(store, price_fn=lambda c: 500.0,
                                       holdings_fn=lambda c: None)
    assert isclose(res.report.total_value, 500.0 * C.SHARES_PER_LOT)
