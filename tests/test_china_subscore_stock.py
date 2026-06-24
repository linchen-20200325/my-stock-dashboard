"""test_china_subscore_stock.py — v18.272 China 副盤(Stock 端)

對稱 Fund v19.114 同名測試,演算法 100% 一致:
1. 5 因子各自打分(CLI/PMI/CPI/M2/USDCNY)邊界正確
2. subscore 等權平均 + 缺項重分配(不偽 50)
3. regime 4 級 + USDCNY > 7.4 flag 獨立判讀
4. snapshot 對 raw dict[series_id, DataFrame] 萃取正確
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_helpers import (
    _score_china_cli,
    _score_china_cpi,
    _score_china_m2,
    _score_china_pmi,
    _score_china_usdcny,
    china_macro_snapshot,
    classify_china_regime,
    compute_china_subscore,
)


# ══════════════════════════════════════════════════════════════
# 1. 各因子打分邊界
# ══════════════════════════════════════════════════════════════

@pytest.mark.parametrize("v,expected", [
    (101.0, 100.0),
    (99.5,  50.0),
    (98.5,  25.0),
    (97.0,  0.0),
    (None,  None),
])
def test_score_cli(v, expected):
    assert _score_china_cli(v) == expected


def test_score_pmi_mirrors_cli():
    for v in (101.0, 99.5, 98.5, 97.0):
        assert _score_china_pmi(v) == _score_china_cli(v)


@pytest.mark.parametrize("v,expected", [
    (2.0,  100.0),
    (1.5,  100.0),
    (0.5,  50.0),
    (3.5,  50.0),
    (5.0,  0.0),
    (-1.0, 0.0),
    (None, None),
])
def test_score_cpi(v, expected):
    assert _score_china_cpi(v) == expected


@pytest.mark.parametrize("v,expected", [
    (10.0, 100.0),
    (9.0,  100.0),
    (7.0,  50.0),
    (4.0,  0.0),
    (None, None),
])
def test_score_m2(v, expected):
    assert _score_china_m2(v) == expected


@pytest.mark.parametrize("v,expected", [
    (6.5, 100.0),
    (7.1, 50.0),
    (7.3, 25.0),
    (7.5, 0.0),
    (None, None),
])
def test_score_usdcny(v, expected):
    assert _score_china_usdcny(v) == expected


def test_score_handles_nan():
    nan = float("nan")
    assert _score_china_cli(nan) is None
    assert _score_china_cpi(nan) is None
    assert _score_china_usdcny(nan) is None


# ══════════════════════════════════════════════════════════════
# 2. snapshot — 從 raw dict[series_id, DataFrame] 萃取
# ══════════════════════════════════════════════════════════════

def _make_df(value: float, date: str = "2025-12-01") -> pd.DataFrame:
    return pd.DataFrame({
        "date": [pd.Timestamp(date)],
        "value": [value],
        "source": ["FRED:test"],
        "fetched_at": ["2026-06-24T10:00:00Z"],
    })


def test_snapshot_empty():
    out = china_macro_snapshot({})
    assert set(out.keys()) == {"cli", "pmi", "cpi_yoy", "m2_yoy", "usdcny",
                               "credit_impulse_proxy"}
    for k in ("cli", "pmi", "cpi_yoy", "m2_yoy", "usdcny"):
        assert out[k]["value"] is None
        assert out[k]["zone"] == "⬜ 無資料"


def test_snapshot_cli_green():
    from shared.fred_series import FRED_CHN_OECD_CLI
    out = china_macro_snapshot({FRED_CHN_OECD_CLI: _make_df(100.5)})
    assert out["cli"]["value"] == 100.5
    assert "🟢" in out["cli"]["zone"]


def test_snapshot_usdcny_red():
    from shared.fred_series import FRED_USDCNY
    out = china_macro_snapshot({FRED_USDCNY: _make_df(7.45)})
    assert "🔴" in out["usdcny"]["zone"]


def test_snapshot_m3_level_to_yoy_green():
    """v18.273 校正:M3 level series 漲 10% YoY → 🟢 綠(寬鬆)"""
    from shared.fred_series import FRED_CHN_M2
    dates = pd.date_range('2025-01-01', periods=13, freq='ME')
    levels = [250 * (1 + 0.10 * i / 12) for i in range(13)]
    df = pd.DataFrame({
        "date": dates, "value": levels,
        "source": ["FRED:test"] * 13, "fetched_at": ["2026-06-24"] * 13,
    })
    out = china_macro_snapshot({FRED_CHN_M2: df})
    assert "🟢" in out["m2_yoy"]["zone"]
    assert 9.0 <= out["m2_yoy"]["value"] <= 11.0


def test_snapshot_m3_level_to_yoy_red_tight():
    """v18.273:M3 level 12 月只漲 4% → YoY 4% → 🔴(緊縮)"""
    from shared.fred_series import FRED_CHN_M2
    dates = pd.date_range('2025-01-01', periods=13, freq='ME')
    levels = [250 + i * (10/12) for i in range(13)]  # 漲 10 兆 = 4%
    df = pd.DataFrame({
        "date": dates, "value": levels,
        "source": ["FRED:test"] * 13, "fetched_at": ["2026-06-24"] * 13,
    })
    out = china_macro_snapshot({FRED_CHN_M2: df})
    assert "🔴" in out["m2_yoy"]["zone"]


def test_snapshot_m3_short_series_no_yoy():
    """v18.273:M3 level 不足 13 筆 → YoY 不可算 → ⬜ 無資料(§1 fail loud)"""
    from shared.fred_series import FRED_CHN_M2
    out = china_macro_snapshot({FRED_CHN_M2: _make_df(280.0)})
    assert out["m2_yoy"]["zone"] == "⬜ 無資料"
    assert out["m2_yoy"]["value"] is None


# ══════════════════════════════════════════════════════════════
# 3. compute_china_subscore
# ══════════════════════════════════════════════════════════════

def _snap(cli=None, pmi=None, cpi=None, m2=None, usdcny=None) -> dict:
    def _e(v):
        return {"value": v, "date": None, "zone": "", "source": None}
    return {
        "cli":     _e(cli),
        "pmi":     _e(pmi),
        "cpi_yoy": _e(cpi),
        "m2_yoy":  _e(m2),
        "usdcny":  _e(usdcny),
    }


def test_subscore_empty():
    assert compute_china_subscore({}) is None
    assert compute_china_subscore(_snap()) is None


def test_subscore_all_green():
    out = compute_china_subscore(_snap(cli=101, pmi=101, cpi=2.0, m2=10.0, usdcny=6.8))
    assert out["score"] == 100.0
    assert out["n_available"] == 5


def test_subscore_all_red():
    out = compute_china_subscore(_snap(cli=97, pmi=97, cpi=5.5, m2=4.0, usdcny=7.5))
    assert out["score"] == 0.0


def test_subscore_mixed():
    """3 綠 + 2 紅 → 60"""
    out = compute_china_subscore(_snap(cli=101, pmi=101, cpi=2.0, m2=4.0, usdcny=7.5))
    assert out["score"] == 60.0


def test_subscore_partial_missing_redistributes():
    """只有 2 個資料 → 平均 2 項"""
    out = compute_china_subscore(_snap(cpi=2.0, usdcny=6.8))
    assert out["score"] == 100.0
    assert out["n_available"] == 2


# ══════════════════════════════════════════════════════════════
# 4. classify_china_regime
# ══════════════════════════════════════════════════════════════

def test_regime_empty():
    out = classify_china_regime({})
    assert out["regime"] == "⬜ 資料不足"
    assert out["fx_alert"] is False


def test_regime_cli_pmi_both_missing():
    out = classify_china_regime(_snap(m2=10.0, cpi=2.0, usdcny=6.8))
    assert out["regime"] == "⬜ 資料不足"


def test_regime_green_expansion():
    out = classify_china_regime(_snap(cli=101, pmi=101, m2=10.0, cpi=2.0))
    assert out["regime"] == "🟢 擴張"


def test_regime_red_recession():
    out = classify_china_regime(_snap(cli=97, pmi=97, m2=8.0))
    assert out["regime"] == "🔴 衰退/緊縮"


def test_regime_red_via_m2_tight():
    out = classify_china_regime(_snap(cli=101, pmi=101, m2=4.0))
    assert out["regime"] == "🔴 衰退/緊縮"


def test_regime_yellow_slowdown():
    out = classify_china_regime(_snap(cli=98.5, pmi=99.5, m2=8.0))
    assert out["regime"] == "🟡 減速"


def test_regime_neutral():
    out = classify_china_regime(_snap(cli=99.5, pmi=99.5, m2=8.0))
    assert out["regime"] == "⚪ 中性"


def test_regime_fx_alert_independent():
    out = classify_china_regime(_snap(cli=101, pmi=101, m2=10.0, usdcny=7.5))
    assert out["regime"] == "🟢 擴張"
    assert out["fx_alert"] is True


def test_regime_fx_alert_boundary():
    out = classify_china_regime(_snap(cli=101, pmi=101, usdcny=7.4))
    assert out["fx_alert"] is False  # strictly >


def test_regime_fx_alert_when_data_short():
    out = classify_china_regime(_snap(usdcny=7.5))
    assert out["regime"] == "⬜ 資料不足"
    assert out["fx_alert"] is True
