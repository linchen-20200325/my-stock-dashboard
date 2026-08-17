"""L2 ETF 穿透：去重複計數、>30% 警戒、覆蓋率熔斷。"""
import pytest

from stock_etf_dashboard.core import constants as C
from stock_etf_dashboard.core.circuit_breaker import FailLoudError, isclose
from stock_etf_dashboard.services import etf_overlap_calc as ov


def test_de_double_count_direct_plus_etf():
    # 直接持 2330 市值 30 萬 + 0050(70萬) 內含 2330 47%
    direct = [{"ticker": "2330", "market_value": 300000}]
    etfs = [{"ticker": "0050", "market_value": 700000,
             "holdings": {"2330": 47.0, "2317": 4.5, "2454": 3.0}}]
    rep = ov.compute_penetrated_exposure(direct, etfs)
    row = next(r for r in rep.rows if r.name == "2330")
    # 300000 + 700000*0.47 = 629000；佔總市值 1,000,000 → 62.9%
    assert isclose(row.via_direct, 300000.0)
    assert isclose(row.via_etf, 329000.0)
    assert isclose(row.market_value, 629000.0)
    assert isclose(row.exposure_pct, 62.9)


def test_single_name_over_30pct_breaches():
    direct = [{"ticker": "2330", "market_value": 400000}]
    etfs = [{"ticker": "0050", "market_value": 600000,
             "holdings": {"2330": 50.0, "2317": 50.0}}]
    rep = ov.compute_penetrated_exposure(direct, etfs)
    assert "2330" in rep.alerts
    row = next(r for r in rep.rows if r.name == "2330")
    assert row.exposure_pct > C.SINGLE_NAME_EXPOSURE_ALERT_PCT
    assert row.breach is True


def test_diversified_no_breach():
    direct = []
    etfs = [{"ticker": "0050", "market_value": 1000000,
             "holdings": {f"S{i}": 10.0 for i in range(10)}}]
    rep = ov.compute_penetrated_exposure(direct, etfs)
    assert rep.alerts == []
    assert rep.is_complete is True   # 權重加總 100% → 覆蓋率 100%


def test_incomplete_etf_triggers_circuit_breaker():
    # 成分抓不到 (holdings=None) → 不完整,曝險為下限
    direct = [{"ticker": "2330", "market_value": 500000}]
    etfs = [{"ticker": "00878", "market_value": 500000, "holdings": None}]
    rep = ov.compute_penetrated_exposure(direct, etfs)
    assert rep.is_complete is False
    assert "00878" in rep.incomplete_etfs
    assert "下限" in rep.note


def test_partial_topn_lowers_coverage():
    # ETF 只揭露 top 權重 60% → 覆蓋率 < 門檻 → 不完整
    etfs = [{"ticker": "0050", "market_value": 1000000,
             "holdings": {"2330": 40.0, "2317": 20.0}}]
    rep = ov.compute_penetrated_exposure([], etfs)
    assert rep.coverage_pct < C.OVERLAP_MIN_COVERAGE_PCT
    assert rep.is_complete is False


def test_zero_total_value_raises():
    with pytest.raises(FailLoudError):
        ov.compute_penetrated_exposure([], [])


def test_negative_market_value_raises():
    with pytest.raises(FailLoudError):
        ov.compute_penetrated_exposure([{"ticker": "X", "market_value": -1}], [])


def test_duplicate_direct_same_ticker_accumulates():
    # 同一代碼分兩筆直接持股 → 應累加,不可覆蓋
    direct = [{"ticker": "2330", "market_value": 100000},
              {"ticker": "2330", "market_value": 50000}]
    etfs = [{"ticker": "0050", "market_value": 100000, "holdings": {"2330": 50.0}}]
    rep = ov.compute_penetrated_exposure(direct, etfs)
    row = next(r for r in rep.rows if r.name == "2330")
    assert isclose(row.via_direct, 150000.0)
    assert isclose(row.via_etf, 50000.0)


def test_alias_map_merges_cross_naming():
    # 直接持「台積電」中文 + ETF 成分用代碼 2330 → alias 對齊後合併
    direct = [{"ticker": "台積電", "market_value": 100000}]
    etfs = [{"ticker": "0050", "market_value": 100000, "holdings": {"2330": 50.0}}]
    rep = ov.compute_penetrated_exposure(direct, etfs, alias_map={"台積電": "2330"})
    names = {r.name for r in rep.rows}
    assert "2330" in names and "台積電" not in names
    row = next(r for r in rep.rows if r.name == "2330")
    assert isclose(row.market_value, 150000.0)   # 10萬直接 + 5萬穿透
