"""💰 存股戰情室 L2：均線 / 布林 z 的**序列版**（走勢圖用）。

本檔的核心交付物是 **§4.3 重算對帳**：序列版最後一點必須等於既有純量版
（`week_ma` / `bollinger_z`）—— 圖上的線與 235 燈用的數字**必須是同一把尺**。
一律用 `math.isclose` 容差比較,**禁止 `==`**（§4.3）。

視窗長度全部自 L0 `shared.dividend_station_thresholds` 引入,不 inline 寫死（§3.3）。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from src.compute.etf import dividend_station as ds

_ALL_MA_WINDOWS = (T.MA_MONTH_WEEKS, T.MA_QUARTER_WEEKS,
                   T.BOLL_PERIOD_WEEKS, T.MA_YEAR_WEEKS)


def _wk_index(n: int, start: str = "2021-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="W-FRI")


def _wk_random(n: int = 140, seed: int = 20260826) -> pd.Series:
    """幾何布朗運動的假週收盤（固定種子 → 可重現,§5）。"""
    rng = np.random.default_rng(seed)
    vals = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.025, n)))
    return pd.Series(vals, index=_wk_index(n), dtype=float)


def _wk_flat(n: int, val: float = 50.0) -> pd.Series:
    return pd.Series([val] * n, index=_wk_index(n), dtype=float)


# ── §4.3 對帳：序列最後一點 ≡ 純量版 ────────────────────────────────────
def test_bollinger_z_series_last_reconciles_with_scalar():
    """布林 z：序列[-1] vs 純量,容差比較（禁 `==`）。"""
    wk = _wk_random()
    got = float(ds.bollinger_z_series(wk).iloc[-1])
    expect = ds.bollinger_z(wk)
    assert expect is not None
    assert math.isclose(got, expect, rel_tol=1e-12), f"{got!r} vs {expect!r}"


@pytest.mark.parametrize("period_weeks", _ALL_MA_WINDOWS)
def test_week_ma_series_last_reconciles_with_scalar(period_weeks):
    """均線：四條週期（4/13/20/52 週,皆自 L0 取）序列[-1] vs 純量。"""
    wk = _wk_random()
    got = float(ds.week_ma_series(wk, period_weeks).iloc[-1])
    expect = ds.week_ma(wk, period_weeks)
    assert expect is not None
    assert math.isclose(got, expect, rel_tol=1e-12), f"N={period_weeks}: {got!r} vs {expect!r}"


def test_bollinger_z_series_reconciles_at_every_point():
    """**逐點**對帳：第 i 點 ≡ `bollinger_z(前綴序列)`,含「純量回 None ⇔ 序列 NaN」。

    只釘最後一點會漏掉「中間某段用了另一把尺」。這條把整條線釘死。
    """
    wk = _wk_random()
    z = ds.bollinger_z_series(wk)
    for i in range(len(wk)):
        scalar = ds.bollinger_z(wk.iloc[:i + 1])
        point = float(z.iloc[i])
        if scalar is None:
            assert math.isnan(point), f"i={i}: 純量不判定,序列卻給了 {point!r}"
        else:
            assert math.isclose(point, scalar, rel_tol=1e-12), f"i={i}: {point!r} vs {scalar!r}"


def test_week_ma_series_reconciles_at_every_point():
    wk = _wk_random()
    n = T.MA_QUARTER_WEEKS
    ma = ds.week_ma_series(wk, n)
    for i in range(len(wk)):
        scalar = ds.week_ma(wk.iloc[:i + 1], n)
        point = float(ma.iloc[i])
        if scalar is None:
            assert math.isnan(point), f"i={i}: 純量不判定,序列卻給了 {point!r}"
        else:
            assert math.isclose(point, scalar, rel_tol=1e-12), f"i={i}: {point!r} vs {scalar!r}"


def test_series_versions_do_not_use_stats_helpers_rulers():
    """z 必須是「(收 − 20週均) / 20週母體std」,不是 `stats_helpers` 的另外兩把尺。

    `zscore`（全序列 mean/std）與 `robust_z`（rolling median/MAD）公式都不同 ——
    若哪天序列版被偷換成它們,本條會紅。
    """
    wk = _wk_random()
    n = T.BOLL_PERIOD_WEEKS
    window = wk.iloc[-n:]
    manual = (float(wk.iloc[-1]) - float(window.mean())) / float(window.std(ddof=0))
    assert math.isclose(float(ds.bollinger_z_series(wk).iloc[-1]), manual, rel_tol=1e-12)
    # 全序列 zscore 與本函式**不應**相等(尺不同 → 若相等代表被換掉了)
    whole = (float(wk.iloc[-1]) - float(wk.mean())) / float(wk.std(ddof=0))
    assert not math.isclose(manual, whole, rel_tol=1e-6)


# ── §4.6 邊界：空 / 單筆 / 全空值 ───────────────────────────────────────
def test_empty_series_returns_empty_series():
    empty = pd.Series([], dtype="float64")
    assert ds.bollinger_z_series(empty).empty
    assert ds.week_ma_series(empty, T.MA_QUARTER_WEEKS).empty


def test_none_input_returns_empty_series_not_raise():
    """與純量兄弟語意對齊:純量回 None,序列回空 Series（不 raise）。"""
    assert ds.bollinger_z_series(None).empty
    assert ds.week_ma_series(None, T.MA_QUARTER_WEEKS).empty


def test_single_row_is_nan_not_a_number():
    """單筆 → 週數不足,留白。純量版此時回 None。"""
    one = pd.Series([100.0], index=_wk_index(1))
    assert math.isnan(float(ds.bollinger_z_series(one).iloc[0]))
    assert ds.bollinger_z(one) is None
    assert math.isnan(float(ds.week_ma_series(one, T.BOLL_PERIOD_WEEKS).iloc[0]))
    assert ds.week_ma(one, T.BOLL_PERIOD_WEEKS) is None


def test_all_nan_series_stays_all_nan_and_keeps_length():
    """全 NaN → 等長全 NaN,**不補 0、不 ffill**（§1）。"""
    n = T.BOLL_PERIOD_WEEKS + 5
    s = pd.Series([np.nan] * n, index=_wk_index(n))
    z = ds.bollinger_z_series(s)
    ma = ds.week_ma_series(s, T.BOLL_PERIOD_WEEKS)
    assert len(z) == n and z.isna().all()
    assert len(ma) == n and ma.isna().all()
    assert ds.bollinger_z(s) is None


# ── §4.6 邊界：週數剛好 / 差一週 ────────────────────────────────────────
def test_exactly_period_weeks_gives_exactly_one_point():
    """剛好 N 週 → 只有最後一點有值,前 N−1 點留白。"""
    n = T.BOLL_PERIOD_WEEKS
    wk = _wk_random(n=n)
    z = ds.bollinger_z_series(wk)
    assert z.iloc[:n - 1].isna().all(), "前 N−1 點必須留白"
    assert np.isfinite(z.iloc[-1])
    assert math.isclose(float(z.iloc[-1]), ds.bollinger_z(wk), rel_tol=1e-12)


def test_one_week_short_is_all_nan():
    """N−1 週（差一週）→ 整條留白,與純量版回 None 對齊。"""
    n = T.BOLL_PERIOD_WEEKS
    wk = _wk_random(n=n - 1)
    assert ds.bollinger_z_series(wk).isna().all()
    assert ds.bollinger_z(wk) is None
    assert ds.week_ma_series(wk, n).isna().all()
    assert ds.week_ma(wk, n) is None


def test_ma_warmup_length_matches_each_window():
    """每條均線的留白長度 = 該條自己的週期 − 1（不是共用一個門檻）。"""
    wk = _wk_random()
    for n in _ALL_MA_WINDOWS:
        ma = ds.week_ma_series(wk, n)
        assert ma.iloc[:n - 1].isna().all(), f"N={n}: 前 N−1 點應留白"
        assert np.isfinite(ma.iloc[n - 1]), f"N={n}: 第 N 點應該有值"


# ── §4.6 邊界：NaN 破洞 ────────────────────────────────────────────────
def test_nan_hole_skips_like_scalar_version_not_blanking_whole_window():
    """窗內破洞 → 跟純量版一樣跳過 NaN 照算,**不是整窗變 NaN**。

    這條防的是「改用 `rolling(N)` 預設 min_periods」那種寫法 —— 它會讓一個破洞
    吃掉整個窗,線就跟燈用的均線對不起來了。
    """
    n = T.BOLL_PERIOD_WEEKS
    s = pd.Series(np.linspace(100.0, 130.0, n + 6), index=_wk_index(n + 6))
    s.iloc[n] = np.nan                       # 中間戳一個洞
    ma = ds.week_ma_series(s, n)
    z = ds.bollinger_z_series(s)
    assert math.isclose(float(ma.iloc[-1]), ds.week_ma(s, n), rel_tol=1e-12)
    assert math.isclose(float(z.iloc[-1]), ds.bollinger_z(s), rel_tol=1e-12)
    assert np.isfinite(ma.iloc[-1]), "破洞不該讓後面整段變 NaN"


def test_nan_at_that_point_is_nan_not_a_bogus_z():
    """該點週收本身是 NaN → 該點 z 為 NaN（純量版同一位置回 None,稽核 L5 同坑）。"""
    n = T.BOLL_PERIOD_WEEKS
    s = pd.Series(np.linspace(100.0, 130.0, n + 6), index=_wk_index(n + 6))
    s.iloc[n] = np.nan
    z = ds.bollinger_z_series(s)
    assert math.isnan(float(z.iloc[n]))
    assert ds.bollinger_z(s.iloc[:n + 1]) is None


# ── §4.6 + §4.4 邊界：std ≈ 0（水平線）─────────────────────────────────
def test_flat_line_gives_nan_never_inf():
    """一條水平線 std≈0 → 全 NaN,**絕不可出現 ±inf**（§4.4 大數除以小數）。"""
    n = T.BOLL_PERIOD_WEEKS
    flat = _wk_flat(n + 3)
    z = ds.bollinger_z_series(flat)
    assert z.isna().all(), "std≈0 應為不判定"
    assert not np.isinf(z.to_numpy()).any(), "不可炸出 inf"
    assert ds.bollinger_z(flat) is None
    # 均線在水平線上仍然有值（水平線的均線就是那個常數）
    assert math.isclose(float(ds.week_ma_series(flat, n).iloc[-1]), ds.week_ma(flat, n),
                        rel_tol=1e-12)


def test_near_zero_std_uses_same_tolerance_as_scalar():
    """std 落在 `FLOAT_ABS_TOL` 之下 → 與純量版同時判「不判定」。"""
    n = T.BOLL_PERIOD_WEEKS
    s = _wk_flat(n).copy()
    s.iloc[-1] = s.iloc[-1] + T.FLOAT_ABS_TOL / 1000.0   # 擾動遠小於容差
    assert ds.bollinger_z(s) is None
    assert math.isnan(float(ds.bollinger_z_series(s).iloc[-1]))


def test_inf_contamination_is_nan():
    """inf 污染 → NaN（純量版 `math.isfinite` 三連檢回 None）。"""
    n = T.BOLL_PERIOD_WEEKS
    s = pd.Series(np.linspace(100.0, 130.0, n + 2), index=_wk_index(n + 2))
    s.iloc[-1] = np.inf
    assert math.isnan(float(ds.bollinger_z_series(s).iloc[-1]))
    assert ds.bollinger_z(s) is None


# ── 契約：索引 / 長度 / 非法視窗 ────────────────────────────────────────
def test_index_and_length_preserved():
    """畫圖要對得上時間軸 → index 與長度必須原樣保留。"""
    wk = _wk_random(n=60)
    for out in (ds.bollinger_z_series(wk), ds.week_ma_series(wk, T.MA_QUARTER_WEEKS)):
        assert len(out) == len(wk)
        assert out.index.equals(wk.index)


@pytest.mark.parametrize("bad", [0, -1])
def test_non_positive_period_raises(bad):
    """視窗長度無意義 → fail loud,不靜默給結果（§1）。"""
    wk = _wk_random(n=30)
    with pytest.raises(ValueError):
        ds.week_ma_series(wk, bad)
    with pytest.raises(ValueError):
        ds.bollinger_z_series(wk, bad)


def test_default_period_comes_from_l0_ssot():
    """預設視窗必須是 L0 的 `BOLL_PERIOD_WEEKS`,不是 inline 的 20（§3.3）。"""
    import inspect
    sig = inspect.signature(ds.bollinger_z_series)
    assert sig.parameters["period_weeks"].default == T.BOLL_PERIOD_WEEKS
    # 顯式傳同一個值 → 與預設同結果
    wk = _wk_random()
    a = ds.bollinger_z_series(wk).iloc[-1]
    b = ds.bollinger_z_series(wk, T.BOLL_PERIOD_WEEKS).iloc[-1]
    assert math.isclose(float(a), float(b), rel_tol=1e-12)
