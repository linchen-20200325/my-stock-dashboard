"""L1 etf_repo：Yahoo TW 第二源解析 + 兩源 fallback 鏈。"""
import pytest

from stock_etf_dashboard.core.circuit_breaker import FailLoudError
from stock_etf_dashboard.repositories import etf_repo as E


# ── Yahoo TW 頁解析 ─────────────────────────────────────────────────────
def test_yahoo_tw_prefers_symbol_code():
    html = ('x{"symbol":"2330.TW","symbolName":"台積電","weighting":"47.12"}y'
            '{"symbol":"2317.TW","symbolName":"鴻海","weighting":"4.5"}z')
    assert E._parse_yahoo_tw_holdings(html) == {"2330": 47.12, "2317": 4.5}


def test_yahoo_tw_name_fallback_and_fraction_scaling():
    # 無 symbol 欄 → 退名稱；小數權重整組 ×100
    html = ('{"holdingName":"台積電","holdingPercent":0.4712}'
            '{"holdingName":"鴻海","holdingPercent":0.045}')
    assert E._parse_yahoo_tw_holdings(html) == {"台積電": 47.12, "鴻海": 4.5}


def test_yahoo_tw_empty_page_raises():
    with pytest.raises(FailLoudError):
        E._parse_yahoo_tw_holdings("")


def test_yahoo_tw_no_holdings_raises():
    with pytest.raises(FailLoudError):
        E._parse_yahoo_tw_holdings("<html>no holdings here</html>")


# ── 單位轉換 ────────────────────────────────────────────────────────────
def test_scale_fraction_to_percent():
    assert E._scale_to_percent({"2330": 0.47, "2317": 0.045}) == {"2330": 47.0, "2317": 4.5}


def test_scale_percent_unchanged():
    assert E._scale_to_percent({"2330": 47.0}) == {"2330": 47.0}


def test_scale_drops_out_of_range_noise():
    # 999 超出 (0,100] → 濾掉；剩合理值
    assert E._scale_to_percent({"2330": 47.0, "JUNK": 999.0}) == {"2330": 47.0}


def test_scale_all_invalid_raises():
    with pytest.raises(FailLoudError):
        E._scale_to_percent({"A": 999.0, "B": 500.0})


# ── 兩源 fallback 鏈 ────────────────────────────────────────────────────
def test_chain_falls_back_to_yahoo_when_yfinance_fails(monkeypatch):
    def yf_fail(t):
        raise FailLoudError("yfinance 台股常無 funds_data")
    monkeypatch.setattr(E, "_from_yfinance", yf_fail)
    monkeypatch.setattr(E, "_from_yahoo_tw", lambda t: {"2330": 47.0, "2317": 4.5})
    assert E.fetch_etf_holdings("0050.TW") == {"2330": 47.0, "2317": 4.5}


def test_chain_uses_yfinance_first_when_available(monkeypatch):
    monkeypatch.setattr(E, "_from_yfinance", lambda t: {"2330": 50.0})
    # yahoo 不該被呼叫；設成拋錯以佐證未被用到
    monkeypatch.setattr(E, "_from_yahoo_tw",
                        lambda t: (_ for _ in ()).throw(AssertionError("不該呼叫 yahoo")))
    assert E.fetch_etf_holdings("0050.TW") == {"2330": 50.0}


def test_chain_all_sources_fail_raises(monkeypatch):
    monkeypatch.setattr(E, "_from_yfinance",
                        lambda t: (_ for _ in ()).throw(FailLoudError("yf 敗")))
    monkeypatch.setattr(E, "_from_yahoo_tw",
                        lambda t: (_ for _ in ()).throw(FailLoudError("yahoo 敗")))
    with pytest.raises(FailLoudError, match="兩源皆敗"):
        E.fetch_etf_holdings("0050.TW")


def test_chain_empty_result_falls_through(monkeypatch):
    # yfinance 回空 dict（非例外）→ 應續走 yahoo
    monkeypatch.setattr(E, "_from_yfinance", lambda t: {})
    monkeypatch.setattr(E, "_from_yahoo_tw", lambda t: {"2330": 47.0})
    assert E.fetch_etf_holdings("0050.TW") == {"2330": 47.0}
