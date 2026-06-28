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

import math

from macro_helpers import (
    CHINA_MODIFIER_FLOOR,
    CHINA_MODIFIER_RANGE,
    _score_china_cli,
    _score_china_cpi,
    _score_china_m2,
    _score_china_pmi,
    _score_china_usdcny,
    apply_china_modifier,
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


# ══════════════════════════════════════════════════════════════
# 4. apply_china_modifier — v18.275 dict 回傳(audit-friendly)
#    composite = main × (0.7 + 0.3 × china/100),只懲罰不加成
#    對稱 Fund v19.117(services.macro_service.apply_china_modifier)
# ══════════════════════════════════════════════════════════════

def test_modifier_constants_match_design():
    """SSOT 守衛:floor=0.70(30% 最大懲罰)+ range=0.30(China 100→1.0×)"""
    assert math.isclose(CHINA_MODIFIER_FLOOR, 0.70, abs_tol=1e-12)
    assert math.isclose(CHINA_MODIFIER_RANGE, 0.30, abs_tol=1e-12)
    # 不變量:floor + range = 1.0(China=100 時 multiplier=1.0,不加成)
    assert math.isclose(
        CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE, 1.0, abs_tol=1e-12,
    )


def test_modifier_returns_dict_with_required_keys():
    """v18.275 回 dict 而非 float,4 欄位齊全(audit-friendly)"""
    out = apply_china_modifier(60.0, 50.0)
    assert isinstance(out, dict)
    assert set(out.keys()) == {"composite", "main", "china", "multiplier"}


@pytest.mark.parametrize("china,expected_composite,expected_mult", [
    (100.0, 60.00, 1.0000),    # multiplier=1.00 → main 原值
    (50.0,  51.00, 0.8500),    # multiplier=0.85 → 60×0.85
    (0.0,   42.00, 0.7000),    # multiplier=0.70 → 60×0.70(最大懲罰)
    (75.0,  55.50, 0.9250),    # multiplier=0.925 → 60×0.925
    (25.0,  46.50, 0.7750),    # multiplier=0.775 → 60×0.775
])
def test_modifier_main_60(china, expected_composite, expected_mult):
    """main=60 各 china 值對應的 composite + multiplier(浮點容差)"""
    out = apply_china_modifier(60.0, china)
    assert math.isclose(out["composite"], expected_composite, abs_tol=1e-9)
    assert math.isclose(out["multiplier"], expected_mult, abs_tol=1e-9)
    assert out["main"] == 60.0
    assert out["china"] == china


def test_modifier_china_none_failsafe():
    """§1 Fail-safe:無中國資料 → composite=main, multiplier=1.0, china=None"""
    out = apply_china_modifier(75.0, None)
    assert out["composite"] == 75.0
    assert out["main"] == 75.0
    assert out["china"] is None
    assert out["multiplier"] == 1.0


def test_modifier_china_none_boundary_main():
    """Fail-safe 邊界 main"""
    assert apply_china_modifier(0.0, None)["composite"] == 0.0
    assert apply_china_modifier(100.0, None)["composite"] == 100.0


def test_modifier_main_none_returns_none():
    """無主分 → None(無從乘起,連 dict 都不回)"""
    assert apply_china_modifier(None, 50.0) is None
    assert apply_china_modifier(None, None) is None


def test_modifier_china_clipped_to_valid_range():
    """china 越界 → clip 到邊界,multiplier 對應 clip 後值"""
    out = apply_china_modifier(60.0, -10.0)
    assert math.isclose(out["composite"], 42.0, abs_tol=1e-9)
    assert out["china"] == 0.0
    assert math.isclose(out["multiplier"], 0.70, abs_tol=1e-9)
    out = apply_china_modifier(60.0, 150.0)
    assert math.isclose(out["composite"], 60.0, abs_tol=1e-9)
    assert out["china"] == 100.0
    assert math.isclose(out["multiplier"], 1.0, abs_tol=1e-9)


def test_modifier_composite_clipped_to_0_100():
    """composite 落在 [0, 100],main 欄位也 clip"""
    out = apply_china_modifier(200.0, 100.0)
    assert out["composite"] == 100.0
    assert out["main"] == 100.0
    out = apply_china_modifier(-50.0, 50.0)
    assert out["composite"] == 0.0
    assert out["main"] == 0.0


def test_modifier_invalid_types_return_none():
    """非數值輸入 → None(不靜默回 dict,不 raise)"""
    assert apply_china_modifier("abc", 50.0) is None
    assert apply_china_modifier(60.0, "xyz") is None


def test_modifier_no_boost_property():
    """Property:對任何 (main, china) ∈ [0,100]²,composite ≤ main(只懲罰不加成)"""
    for main in (0, 25, 50, 75, 100):
        for china in (0, 25, 50, 75, 100):
            out = apply_china_modifier(float(main), float(china))
            assert out["composite"] <= main + 1e-9, (
                f"main={main} china={china} composite={out['composite']} > main"
            )


def test_modifier_monotonic_in_china():
    """Property:固定 main,composite 對 china 單調遞增(china 越好懲罰越輕)"""
    main = 80.0
    prev = -1.0
    for china in (0, 10, 30, 50, 70, 90, 100):
        out = apply_china_modifier(main, float(china))
        assert out["composite"] >= prev, (
            f"china={china} composite={out['composite']} < prev={prev}"
        )
        prev = out["composite"]


def test_modifier_symmetric_with_fund():
    """跨專案對稱守衛:Stock 與 Fund 算同結果(常數 + 公式 + dict 介面 100% 一致)"""
    samples = [
        # (main, china, expected_composite, expected_multiplier)
        (60.0, 100.0, 60.00, 1.0000),
        (60.0, 50.0,  51.00, 0.8500),
        (60.0, 0.0,   42.00, 0.7000),
        (80.0, 50.0,  68.00, 0.8500),
        (100.0, 0.0,  70.00, 0.7000),
    ]
    for main, china, expected_composite, expected_mult in samples:
        out = apply_china_modifier(main, china)
        assert math.isclose(out["composite"], expected_composite, abs_tol=1e-9), (
            f"Stock composite {out['composite']} 偏離 Fund 對稱值 {expected_composite}"
        )
        assert math.isclose(out["multiplier"], expected_mult, abs_tol=1e-9), (
            f"Stock multiplier {out['multiplier']} 偏離 Fund 對稱值 {expected_mult}"
        )


# v18.275 §6 自審「3 個最容易出錯的輸入」:
#   1. china=None (Fail-safe:multiplier=1.0, china=None 明示)
#      ✅ test_modifier_china_none_failsafe + boundary_main
#   2. china 越界 < 0 或 > 100 (clip + multiplier 對應 clip 後值)
#      ✅ test_modifier_china_clipped_to_valid_range
#   3. main 越界 / 非數值 (clip / 回 None)
#      ✅ test_modifier_composite_clipped + invalid_types


# ══════════════════════════════════════════════════════════════
# 5. get_china_snapshot — v18.276 L2 thin wrapper(對稱 Fund v19.118)
#    避免 L5 UI 直呼 L1 tw_macro.fetch_china_macro,§8.2 分層守衛
# ══════════════════════════════════════════════════════════════

def test_get_china_snapshot_empty_key_returns_empty_dict():
    """fail-safe:fred_api_key 空/短 → 空 dict,不呼叫 L1 fetcher(AppTest 守衛)"""
    from macro_helpers import get_china_snapshot
    assert get_china_snapshot("") == {}
    assert get_china_snapshot(None) == {}  # type: ignore[arg-type]
    # <30 字元被視為 AppTest fake key(對齊 _render_global_risk_radar 守衛)
    assert get_china_snapshot("short-fake") == {}


def test_get_china_snapshot_delegates_to_l1_then_l2(monkeypatch):
    """wrapper 串接:tw_macro.fetch_china_macro → macro_helpers.china_macro_snapshot"""
    import macro_helpers as _mh

    _called = {"fetch": 0}

    def _fake_fetch(api_key):
        _called["fetch"] += 1
        # 確認 wrapper 傳遞了正確 key 給 L1
        assert len(api_key) >= 30
        return {}  # 空 dict 模擬「FRED 全失敗」

    monkeypatch.setattr("src.data.macro.tw_macro.fetch_china_macro", _fake_fetch)
    out = _mh.get_china_snapshot("fake-key-with-enough-length-for-truthy-30+")
    assert _called["fetch"] == 1
    # china_macro_snapshot({}) 應回 5 key + credit_impulse_proxy(每個 value=None)
    assert set(out.keys()) >= {"cli", "pmi", "cpi_yoy", "m2_yoy", "usdcny"}
    for k in ("cli", "pmi", "cpi_yoy", "m2_yoy", "usdcny"):
        assert out[k]["value"] is None  # §1 fail loud:不偽造數值


def test_get_china_snapshot_with_real_data_passthrough(monkeypatch):
    """wrapper 對非空 L1 結果做正確 pass-through(不丟欄位、不改值)"""
    import macro_helpers as _mh
    from shared.fred_series import FRED_CHN_OECD_CLI

    _df = pd.DataFrame({
        "date": pd.to_datetime(["2026-04-01", "2026-05-01"]),
        "value": [99.5, 100.2],
        "source": [f"FRED:{FRED_CHN_OECD_CLI}", f"FRED:{FRED_CHN_OECD_CLI}"],
        "fetched_at": ["2026-06-01T00:00:00Z"] * 2,
    })

    def _fake_fetch(api_key):  # noqa: ARG001
        return {FRED_CHN_OECD_CLI: _df}

    monkeypatch.setattr("src.data.macro.tw_macro.fetch_china_macro", _fake_fetch)
    out = _mh.get_china_snapshot("fake-key-with-enough-length-for-truthy-30+")
    assert out["cli"]["value"] == 100.2  # 最新一筆
    assert out["cli"]["source"] == f"FRED:{FRED_CHN_OECD_CLI}"
    # 其餘 4 series 缺 → value=None
    for k in ("pmi", "cpi_yoy", "m2_yoy", "usdcny"):
        assert out[k]["value"] is None


def test_get_china_snapshot_symmetric_with_fund_interface():
    """跨專案對稱:Stock 與 Fund 同名同簽名同行為(空 key fail-safe)"""
    from macro_helpers import get_china_snapshot as _stock_wrapper
    # Stock 端 wrapper 簽名應與 Fund 等價:str → dict
    import inspect
    _sig = inspect.signature(_stock_wrapper)
    _params = list(_sig.parameters.values())
    assert len(_params) == 1, "wrapper 應只收 1 個參數(對稱 Fund)"
    assert _params[0].name == "fred_api_key"
    # 空 key 行為一致(回 {} 而非 None / raise)
    assert _stock_wrapper("") == {}
