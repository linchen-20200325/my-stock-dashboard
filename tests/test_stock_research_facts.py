"""src/compute/strategy/stock_research_facts.py 單元測試（離線、決定性、無網路）。

涵蓋：與獨立手算一致 / 各指標根數邊界（不足 → None，絕不是 0 / False）/ 壞輸入 raise /
不改輸入 / 決定性 / limitations 逐字 / 禁字掃描 / 模組純度（AST）/ 突變防守 / volume 不換算。

突變防守說明（class TestMutationGuards）：
把「不足 → None 前置」拔掉（常數改小）並讓下游函式改回偽值（0.0 / False），
**邊界斷言輔助函式必須因此失敗**（pytest.raises(AssertionError)）。
若有人日後把前置檢查刪掉或改成依賴下游函式的不足行為，這些測試會轉紅。
"""
from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import inspect
import math
import pathlib
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest

import src.compute.strategy.stock_research_facts as srf
from src.compute.strategy.overextension import assess_price_overextension
from src.compute.strategy.stock_research_facts import (
    LIMITATION_EX_RIGHTS_DISTORTION,
    LIMITATION_MA_REFERENCE,
    LIMITATION_UNADJUSTED,
    LIMITATION_UNADJUSTED_DECLARED,
    PRICE_BASIS_UNADJUSTED_DECLARED,
    StockResearchFacts,
    StockResearchFactsInputError,
    build_stock_research_facts,
)

# ── fixture 工具 ─────────────────────────────────────────────────────

_START = "2025-01-01"


def make_bars(n: int, seed: int = 7, volume_scale: int = 1) -> pd.DataFrame:
    """確定性 OHLCV（隨機漫步，種子固定）。價格皆 > 0，OHLC 一致。"""
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    close = np.maximum(close, 20.0)
    open_ = close + rng.normal(0.0, 0.3, n)
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, n)
    volume = rng.integers(1000, 5000, n) * volume_scale
    idx = pd.bdate_range(_START, periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": volume}, index=idx)


def facts_of(df: pd.DataFrame) -> StockResearchFacts:
    return build_stock_research_facts(df, as_of=df.index[-1].date())


def isc(a, b, tol=1e-9) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# ── 正常路徑：與獨立手算一致 ─────────────────────────────────────────

class TestNormalAgainstHandCalc:
    def setup_method(self):
        self.df = make_bars(300)
        self.f = facts_of(self.df)

    def test_metadata(self):
        assert self.f.bar_count == 300
        assert self.f.as_of == self.df.index[-1].date()
        assert self.f.first_date == self.df.index[0].date()
        assert self.f.price_basis == "unadjusted"
        assert isc(self.f.close, round(float(self.df["close"].iloc[-1]), 4))

    @pytest.mark.parametrize("w", [5, 20, 60, 120, 240])
    def test_ma_matches_rolling_mean(self, w):
        expect = float(self.df["close"].rolling(w).mean().iloc[-1])
        assert self.f.ma[w] is not None
        assert isc(self.f.ma[w], round(expect, 4))

    def test_ma_keys_exact(self):
        assert set(self.f.ma) == {5, 20, 60, 120, 240}

    def test_rsi_matches_independent_wilder(self):
        c = self.df["close"].to_numpy()
        d = np.diff(c)
        g, l = np.clip(d, 0, None), np.clip(-d, 0, None)
        ag, al = g[0], l[0]
        for gi, li in zip(g[1:], l[1:]):
            ag = ag * 13 / 14 + gi / 14
            al = al * 13 / 14 + li / 14
        expect = 100 - 100 / (1 + ag / (al + 1e-10))
        assert self.f.rsi14 is not None
        assert abs(self.f.rsi14 - expect) <= 0.0501  # calc_rsi 取 1 位小數

    def test_volume_ratio_matches_formula(self):
        v = self.df["volume"].to_numpy(dtype=float)
        expect = v[-1] / v[-6:-1].mean()
        assert self.f.volume_ratio5 is not None
        assert abs(self.f.volume_ratio5 - expect) <= 0.0051  # 2 位小數

    def test_bias20_matches_formula(self):
        c = self.df["close"]
        ma20 = float(c.rolling(20).mean().iloc[-1])
        expect = (float(c.iloc[-1]) - ma20) / ma20 * 100
        assert isc(self.f.bias20_pct, round(expect, 4))

    def test_support_resistance_matches_tail20(self):
        hi = float(self.df["high"].tail(20).max())
        lo = float(self.df["low"].tail(20).min())
        assert abs(self.f.resistance_20d - hi) <= 0.0051
        assert abs(self.f.support_20d - lo) <= 0.0051
        assert self.f.support_resistance_bars == 20

    def test_overextension_matches_source(self):
        src_r = assess_price_overextension(self.df["close"].reset_index(drop=True))
        assert self.f.overextension_level == src_r["level"]
        assert self.f.overheated == src_r["overheated"]
        assert self.f.overextension_level in {"正常", "偏熱", "過熱"}

    def test_full_data_has_only_fixed_limitations(self):
        assert self.f.limitations == (LIMITATION_UNADJUSTED, LIMITATION_MA_REFERENCE)

    def test_overheated_case(self):
        c = np.array([100.0] * 40 + [140.0])
        df = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c,
                           "volume": np.full(41, 1000)},
                          index=pd.bdate_range(_START, periods=41))
        f = facts_of(df)
        assert f.overextension_level == "過熱"
        assert f.overheated is True
        assert f.bias20_pct is not None and f.bias20_pct > 25.0

    def test_flat_series_rsi_is_none_not_zero(self):
        c = np.full(40, 50.0)
        df = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c,
                           "volume": np.full(40, 100)},
                          index=pd.bdate_range(_START, periods=40))
        f = facts_of(df)
        assert f.rsi14 is None  # 不是 0.0
        assert any("RSI14" in s and "沒有變動" in s for s in f.limitations)
        # 過熱評估含 RSI 項、RSI 無定義 → 整體不判定（不是「正常 / False」）
        assert f.overextension_level is None
        assert f.overheated is None
        assert f.bias20_pct is not None and isc(f.bias20_pct, 0.0, 1e-12)  # 乖離照實列出
        assert any("過熱評估缺 RSI 項" in s for s in f.limitations)


# ── 邊界根數 ─────────────────────────────────────────────────────────

def _assert_ma_boundary(w: int) -> None:
    short = facts_of(make_bars(w - 1))
    assert short.ma[w] is None
    ok = facts_of(make_bars(w))
    assert ok.ma[w] is not None


def _assert_rsi_boundary() -> None:
    assert facts_of(make_bars(14)).rsi14 is None
    assert facts_of(make_bars(15)).rsi14 is not None


def _assert_volume_ratio_boundary() -> None:
    assert facts_of(make_bars(5)).volume_ratio5 is None
    assert facts_of(make_bars(6)).volume_ratio5 is not None


def _assert_overext_boundary() -> None:
    f20 = facts_of(make_bars(20))
    assert f20.overheated is None
    assert f20.overextension_level is None
    assert f20.bias20_pct is None
    f21 = facts_of(make_bars(21))
    assert f21.overheated is not None
    assert f21.overextension_level is not None
    assert f21.bias20_pct is not None


def _assert_sr_boundary() -> None:
    f4 = facts_of(make_bars(4))
    assert f4.support_20d is None and f4.resistance_20d is None
    assert f4.support_resistance_bars is None
    f5 = facts_of(make_bars(5))
    assert f5.support_20d is not None and f5.resistance_20d is not None
    assert f5.support_resistance_bars == 5


class TestBoundaryBars:
    @pytest.mark.parametrize("w", [5, 20, 60, 120, 240])
    def test_ma_window_boundary(self, w):
        _assert_ma_boundary(w)

    def test_rsi_boundary_14_vs_15(self):
        _assert_rsi_boundary()

    def test_volume_ratio_boundary_5_vs_6(self):
        _assert_volume_ratio_boundary()

    def test_overext_boundary_20_vs_21(self):
        _assert_overext_boundary()

    def test_support_resistance_boundary_4_vs_5(self):
        _assert_sr_boundary()

    def test_sr_bars_reported_honestly_between_5_and_19(self):
        f = facts_of(make_bars(12))
        assert f.support_resistance_bars == 12
        assert any("實際僅涵蓋 12 根" in s for s in f.limitations)

    def test_insufficient_sentence_lists_names_only(self):
        f = facts_of(make_bars(10))
        line = [s for s in f.limitations if s.startswith("下列指標根數不足而無法計算：")]
        assert len(line) == 1
        for name in ("MA20", "MA60", "MA120", "MA240", "RSI14", "乖離20與過熱評估"):
            assert name in line[0]
        assert "MA5" not in line[0]            # 10 根時 MA5 可算
        assert "量比5" not in line[0]          # 10 根時量比可算
        assert "支撐壓力" not in line[0]

    def test_single_bar_no_zero_false_pseudo_values(self):
        f = facts_of(make_bars(1))
        assert f.rsi14 is None
        assert f.volume_ratio5 is None
        assert f.bias20_pct is None
        assert f.overheated is None
        assert f.overextension_level is None
        assert f.support_20d is None and f.resistance_20d is None
        assert f.support_resistance_bars is None
        assert all(v is None for v in f.ma.values())
        # 不得出現由不足造成的 0.0 / False / 0.5
        for v in (f.rsi14, f.volume_ratio5, f.bias20_pct, f.overheated,
                  f.support_20d, f.resistance_20d):
            assert v is None

    def test_zero_prior_volume_ratio_none(self):
        df = make_bars(30)
        df.iloc[-6:-1, df.columns.get_loc("volume")] = 0
        assert facts_of(df).volume_ratio5 is None


# ── 壞輸入 ───────────────────────────────────────────────────────────

def _ok_df() -> pd.DataFrame:
    df = make_bars(30)
    df["volume"] = df["volume"].astype(float)   # 避免整數欄被賦 NaN 時 pandas 2.x 的 dtype 警告
    return df


class TestBadInputRaises:
    def test_not_dataframe(self):
        with pytest.raises(StockResearchFactsInputError):
            build_stock_research_facts([1, 2, 3], as_of="2025-01-01")  # type: ignore[arg-type]

    def test_empty(self):
        with pytest.raises(StockResearchFactsInputError):
            build_stock_research_facts(pd.DataFrame(), as_of="2025-01-01")

    @pytest.mark.parametrize("col", ["open", "high", "low", "close", "volume"])
    def test_missing_column(self, col):
        df = _ok_df().drop(columns=[col])
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    def test_uppercase_columns_rejected(self):
        df = _ok_df().rename(columns=str.upper)
        with pytest.raises(StockResearchFactsInputError):
            build_stock_research_facts(df, as_of=df.index[-1].date())

    def test_non_increasing_index(self):
        df = _ok_df().iloc[::-1]
        with pytest.raises(StockResearchFactsInputError):
            build_stock_research_facts(df, as_of=df.index.max().date())

    def test_duplicate_dates(self):
        df = _ok_df()
        idx = list(df.index)
        idx[5] = idx[4]
        df.index = pd.DatetimeIndex(idx)
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    def test_numeric_index_rejected(self):
        df = _ok_df().reset_index(drop=True)
        with pytest.raises(StockResearchFactsInputError, match="純數字索引"):
            build_stock_research_facts(df, as_of="1970-01-01")  # 若未被拒，as_of 恰會相符

    def test_decreasing_with_last_date_equal_as_of(self):
        df = _ok_df().iloc[::-1]               # 遞減；最後一列 = 最早日期
        with pytest.raises(StockResearchFactsInputError, match="非嚴格遞增"):
            build_stock_research_facts(df, as_of=df.index[-1].date())

    def test_bool_dtype_column(self):
        df = _ok_df()
        df["volume"] = np.ones(len(df), dtype=bool)
        with pytest.raises(StockResearchFactsInputError, match="volume"):
            facts_of(df)

    def test_complex_dtype_column(self):
        df = _ok_df()
        df["close"] = df["close"].astype(complex)
        with pytest.raises(StockResearchFactsInputError, match="close"):
            facts_of(df)

    def test_duplicate_column_names(self):
        df = _ok_df()
        df = pd.concat([df, df[["close"]]], axis=1)
        with pytest.raises(StockResearchFactsInputError, match="欄名重複"):
            facts_of(df)

    def test_tz_aware_index_uses_wall_date(self):
        df = _ok_df()
        # 當地 00:30：若誤轉 UTC，日期會退一天而與 as_of 不符
        df.index = (df.index + pd.Timedelta(minutes=30)).tz_localize("Asia/Taipei")
        f = build_stock_research_facts(df, as_of=df.index[-1].date())
        assert f.as_of == df.index[-1].date()
        assert f.first_date == df.index[0].date()

    def test_tz_aware_two_times_same_day_is_duplicate(self):
        df = _ok_df()
        idx = list(df.index.tz_localize("Asia/Taipei"))
        idx[5] = idx[4] + pd.Timedelta(hours=3)
        df.index = pd.DatetimeIndex(idx)
        with pytest.raises(StockResearchFactsInputError, match="重複"):
            facts_of(df)

    @pytest.mark.parametrize("col", ["open", "high", "low", "close", "volume"])
    def test_nan(self, col):
        df = _ok_df()
        df.iloc[3, df.columns.get_loc(col)] = np.nan
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    @pytest.mark.parametrize("bad", [np.inf, -np.inf])
    def test_inf(self, bad):
        df = _ok_df()
        df["volume"] = df["volume"].astype(float)
        df.iloc[3, df.columns.get_loc("volume")] = bad
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    @pytest.mark.parametrize("col", ["open", "high", "low", "close"])
    @pytest.mark.parametrize("bad", [0.0, -1.0])
    def test_non_positive_price(self, col, bad):
        df = _ok_df()
        df.iloc[3, df.columns.get_loc(col)] = bad
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    def test_high_below_low(self):
        df = _ok_df()
        df.iloc[3, df.columns.get_loc("high")] = float(df["low"].iloc[3]) - 0.5
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    def test_negative_volume(self):
        df = _ok_df()
        df.iloc[3, df.columns.get_loc("volume")] = -1
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    def test_non_numeric_dtype(self):
        df = _ok_df()
        df["volume"] = df["volume"].astype(str)
        with pytest.raises(StockResearchFactsInputError):
            facts_of(df)

    def test_as_of_mismatch(self):
        df = _ok_df()
        with pytest.raises(StockResearchFactsInputError):
            build_stock_research_facts(df, as_of=df.index[-2].date())

    @pytest.mark.parametrize("bad", ["2025/01/01", "not-a-date", "", "20250101", 20250101, None,
                                     dt.datetime(2025, 2, 11, 9, 0)])
    def test_as_of_unparsable(self, bad):
        with pytest.raises(StockResearchFactsInputError):
            build_stock_research_facts(_ok_df(), as_of=bad)  # type: ignore[arg-type]

    def test_as_of_str_ok(self):
        df = _ok_df()
        f = build_stock_research_facts(df, as_of=df.index[-1].strftime("%Y-%m-%d"))
        assert f.as_of == df.index[-1].date()

    def test_error_is_valueerror(self):
        assert issubclass(StockResearchFactsInputError, ValueError)


class TestValidEdgeInputs:
    def test_volume_zero_is_valid(self):
        df = make_bars(40)
        df.iloc[-1, df.columns.get_loc("volume")] = 0
        f = facts_of(df)
        assert f.volume_ratio5 is not None and isc(f.volume_ratio5, 0.0, 1e-12)
        # 此處 0.0 是「今日量為 0」的真實比值，不是不足的偽值

    def test_string_date_index_ok(self):
        df = make_bars(30)
        df.index = [d.strftime("%Y-%m-%d") for d in df.index]
        f = build_stock_research_facts(df, as_of=df.index[-1])
        assert f.bar_count == 30


# ── 不改輸入 / 決定性 / 單位 ─────────────────────────────────────────

class TestPurityOfBehavior:
    def test_input_not_mutated(self):
        df = make_bars(120)
        snapshot = df.copy(deep=True)
        cols = list(df.columns)
        facts_of(df)
        pd.testing.assert_frame_equal(df, snapshot)
        assert list(df.columns) == cols

    def test_deterministic(self):
        df = make_bars(300)
        assert facts_of(df) == facts_of(df.copy())

    def test_ma_mapping_is_read_only(self):
        f = facts_of(make_bars(30))
        assert isinstance(f.ma, MappingProxyType)
        with pytest.raises(TypeError):
            f.ma[5] = 1.0  # type: ignore[index]

    def test_frozen(self):
        f = facts_of(make_bars(30))
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.close = 1.0  # type: ignore[misc]

    def test_volume_not_converted_ratio_dimensionless(self):
        a = facts_of(make_bars(40, volume_scale=1))
        b = facts_of(make_bars(40, volume_scale=1000))   # 例如 張 → 股
        assert a.volume_ratio5 is not None and b.volume_ratio5 is not None
        assert abs(a.volume_ratio5 - b.volume_ratio5) <= 0.0101
        # 其餘與 volume 無關的欄位完全相同
        assert a.ma == b.ma and a.rsi14 == b.rsi14 and a.bias20_pct == b.bias20_pct


# ── limitations / 禁字 ───────────────────────────────────────────────

_FORBIDDEN = ("買進", "賣出", "加碼", "減碼", "目標價", "停損", "信心", "機率",
              "看多", "看空", "AI", "評分", "風報比")


def _all_strings(f: StockResearchFacts) -> list[str]:
    out = [fld.name for fld in dataclasses.fields(f)]
    for fld in dataclasses.fields(f):
        v = getattr(f, fld.name)
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, tuple):
            out.extend(s for s in v if isinstance(s, str))
    return out


class TestLimitationsAndWording:
    def test_fixed_sentences_verbatim(self):
        assert LIMITATION_UNADJUSTED == "價格為未調整原始價，除權息日前後指標可能失真。"
        assert LIMITATION_MA_REFERENCE == "均線為參考，不等於正式台股趨勢判斷。"
        for n in (1, 10, 21, 300):
            lim = facts_of(make_bars(n)).limitations
            assert "價格為未調整原始價，除權息日前後指標可能失真。" in lim
            assert "均線為參考，不等於正式台股趨勢判斷。" in lim

    def test_insufficient_sentence_present_only_when_needed(self):
        assert not any(s.startswith("下列指標根數不足") for s in facts_of(make_bars(300)).limitations)
        assert any(s.startswith("下列指標根數不足而無法計算：")
                   for s in facts_of(make_bars(30)).limitations)

    def test_insufficient_example_shape(self):
        # 100 根：MA120 / MA240 不足
        lim = facts_of(make_bars(100)).limitations
        assert "下列指標根數不足而無法計算：MA120、MA240。" in lim

    @pytest.mark.parametrize("n", [1, 5, 12, 21, 100, 300])
    def test_no_forbidden_words(self, n):
        for s in _all_strings(facts_of(make_bars(n))):
            for w in _FORBIDDEN:
                assert w not in s, f"禁字 {w!r} 出現在 {s!r}"

    def test_no_forbidden_words_overheated_case(self):
        c = np.array([100.0] * 40 + [140.0])
        df = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c,
                           "volume": np.full(41, 1000)},
                          index=pd.bdate_range(_START, periods=41))
        for s in _all_strings(facts_of(df)):
            for w in _FORBIDDEN:
                assert w not in s

    def test_no_forbidden_field_names(self):
        names = {f.name for f in dataclasses.fields(StockResearchFacts)}
        for bad in ("target", "stop", "score", "confidence", "probability", "action", "rr"):
            assert not any(bad in n for n in names)


# ── 模組純度（AST）與常數對齊 ────────────────────────────────────────

_SRC = pathlib.Path(srf.__file__).read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)

_BANNED_IMPORT_PREFIXES = ("streamlit", "requests", "yfinance", "FinMind", "time",
                           "src.data", "src.ui", "src.services", "src.ui2", "app",
                           "src.compute.scoring", "src.compute.strategy.exit_signals",
                           "exit_signals", "scoring_engine", "shared.proxy_helper",
                           "proxy_helper")
_BANNED_NAMES = {
    "calc_trend_score", "compute_tech_bearish", "calc_ibs", "calc_volume_score",
    "calc_momentum_score", "calc_atr_stop", "compute_pattern_targets",
    "summarize_pattern", "compute_entry_stop_levels", "calc_rr_ratio", "stock_score",
}
_CLOCK_ATTRS = {"now", "today", "utcnow", "utcfromtimestamp", "fromtimestamp",
                "monotonic", "perf_counter", "time", "sleep"}


def _imported_modules() -> list[str]:
    mods: list[str] = []
    for node in ast.walk(_TREE):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
    return mods


class TestModulePurity:
    def test_no_banned_imports(self):
        for m in _imported_modules():
            for p in _BANNED_IMPORT_PREFIXES:
                assert not (m == p or m.startswith(p + ".")), f"禁止 import {m}"

    def test_no_banned_function_names_used(self):
        used = {n.id for n in ast.walk(_TREE) if isinstance(n, ast.Name)}
        used |= {n.attr for n in ast.walk(_TREE) if isinstance(n, ast.Attribute)}
        used |= {a.name for n in ast.walk(_TREE) if isinstance(n, ast.ImportFrom)
                 for a in n.names}
        assert not (used & _BANNED_NAMES)

    def test_no_clock_calls(self):
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                assert n.func.attr not in _CLOCK_ATTRS, f"禁止時鐘呼叫 .{n.func.attr}()"
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in _CLOCK_ATTRS

    def test_no_file_or_print_io(self):
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in {"open", "print", "input"}

    def test_constants_align_with_source_function_defaults(self):
        sig = inspect.signature(assess_price_overextension).parameters
        assert sig["ma_window"].default == srf.OVEREXT_MA_WINDOW
        assert sig["rsi_period"].default == srf.RSI_PERIOD
        assert srf.MIN_BARS_OVEREXT == srf.OVEREXT_MA_WINDOW + 1
        from src.compute.strategy import tech_indicators as ti
        assert inspect.signature(ti.calc_rsi).parameters["period"].default == srf.RSI_PERIOD
        assert (inspect.signature(ti.calc_volume_ratio).parameters["period"].default
                == srf.VOLUME_RATIO_PERIOD)
        from src.compute.strategy import entry_stop_levels as el
        assert el.MIN_BARS == srf.SR_MIN_BARS == 5
        assert inspect.signature(el.compute_support_resistance).parameters["window"].default \
            == srf.SR_WINDOW_BARS == 20


# ── 突變防守 ─────────────────────────────────────────────────────────

class TestMutationGuards:
    """拔掉「不足 → None」前置、讓下游回偽值時，邊界斷言必須失敗。

    每個測試 = 突變（monkeypatch 常數 + 下游改回 0.0 / False）→ 斷言輔助函式必須 raise
    AssertionError，證明邊界測試真的守得到前置檢查，而非只是下游函式碰巧回 None。
    """

    def test_baseline_unmutated_passes(self):
        _assert_rsi_boundary()
        _assert_volume_ratio_boundary()
        _assert_overext_boundary()

    def test_rsi_guard_removed_goes_red(self, monkeypatch):
        monkeypatch.setattr(srf, "MIN_BARS_RSI", 1)
        monkeypatch.setattr(srf, "calc_rsi", lambda df, period=14: 0.0)
        with pytest.raises(AssertionError):
            _assert_rsi_boundary()

    def test_volume_ratio_guard_removed_goes_red(self, monkeypatch):
        monkeypatch.setattr(srf, "MIN_BARS_VOLUME_RATIO", 1)
        monkeypatch.setattr(srf, "calc_volume_ratio", lambda df, period=5: 0.0)
        with pytest.raises(AssertionError):
            _assert_volume_ratio_boundary()

    def test_overextension_guard_removed_goes_red(self, monkeypatch):
        fake = {"level": "正常", "overheated": False, "bias_pct": 0.0,
                "rsi": None, "reasons": [], "icon": "🟢"}
        monkeypatch.setattr(srf, "MIN_BARS_OVEREXT", 1)
        monkeypatch.setattr(srf, "assess_price_overextension", lambda *a, **k: dict(fake))
        with pytest.raises(AssertionError):
            _assert_overext_boundary()

    def test_insufficient_never_becomes_zero_or_false(self):
        """直接行為斷言：任何不足欄位都不是 0 / False / 0.5。"""
        f = facts_of(make_bars(3))
        for v in (f.rsi14, f.volume_ratio5, f.bias20_pct, f.overheated,
                  f.support_20d, f.resistance_20d, *f.ma.values()):
            assert v is None
            assert v != 0 and v is not False


# ── basis_verified（口徑是否已驗證）────────────────────────────────────

_DECL = "價格口徑由使用者聲明為未調整原始價，系統未驗證。"
_DIST = "除權息日前後指標可能失真。"
_OLD1 = "價格為未調整原始價，除權息日前後指標可能失真。"
_MA = "均線為參考，不等於正式台股趨勢判斷。"


def facts_unverified(df: pd.DataFrame) -> StockResearchFacts:
    return build_stock_research_facts(df, as_of=df.index[-1].date(), basis_verified=False)


class TestBasisVerified:
    def test_default_true_unchanged_verbatim(self):
        f = facts_of(make_bars(300))
        assert f.price_basis == "unadjusted"
        assert f.price_basis_verified is True
        assert f.limitations == (_OLD1, _MA)
        explicit = build_stock_research_facts(make_bars(300), as_of=f.as_of, basis_verified=True)
        assert explicit == f

    def test_false_fields_and_limitations_verbatim(self):
        f = facts_unverified(make_bars(300))
        assert f.price_basis == "unadjusted_declared" == PRICE_BASIS_UNADJUSTED_DECLARED
        assert f.price_basis_verified is False
        assert f.limitations == (_DECL, _DIST, _MA)
        assert LIMITATION_UNADJUSTED_DECLARED == _DECL
        assert LIMITATION_EX_RIGHTS_DISTORTION == _DIST
        assert _OLD1 not in f.limitations
        assert not any("價格為未調整原始價" in s for s in f.limitations)

    def test_false_other_facts_identical(self):
        df = make_bars(300)
        a, b = facts_of(df), facts_unverified(df)
        for fld in dataclasses.fields(StockResearchFacts):
            if fld.name in ("price_basis", "price_basis_verified", "limitations"):
                continue
            assert getattr(a, fld.name) == getattr(b, fld.name), fld.name
        assert isc(a.close, b.close) and isc(a.rsi14, b.rsi14)

    def test_false_with_insufficient_bars(self):
        f = facts_unverified(make_bars(12))
        assert f.limitations[:3] == (_DECL, _DIST, _MA)
        assert any(s.startswith("下列指標根數不足而無法計算：") for s in f.limitations)
        assert any("實際僅涵蓋 12 根" in s for s in f.limitations)
        assert f.price_basis_verified is False

    def test_false_flat_series_notes_coexist(self):
        c = np.full(40, 50.0)
        df = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c,
                           "volume": np.full(40, 100)},
                          index=pd.bdate_range(_START, periods=40))
        f = facts_unverified(df)
        assert f.rsi14 is None
        assert f.limitations[:3] == (_DECL, _DIST, _MA)
        assert any("RSI14" in s for s in f.limitations)

    @pytest.mark.parametrize("bad", [1, 0, None, np.True_, np.False_, "False", "True"])
    def test_non_bool_rejected(self, bad):
        df = make_bars(30)
        with pytest.raises(StockResearchFactsInputError, match="basis_verified"):
            build_stock_research_facts(df, as_of=df.index[-1].date(),
                                       basis_verified=bad)  # type: ignore[arg-type]

    def test_keyword_only(self):
        df = make_bars(30)
        with pytest.raises(TypeError):
            build_stock_research_facts(df, df.index[-1].date(), False)  # type: ignore[misc]

    @pytest.mark.parametrize("n", [1, 5, 12, 21, 300])
    def test_no_forbidden_words_false(self, n):
        for s in _all_strings(facts_unverified(make_bars(n))):
            for w in _FORBIDDEN:
                assert w not in s, f"禁字 {w!r} 出現在 {s!r}"

    def test_no_new_imports_beyond_original(self):
        mods = set(_imported_modules())
        assert mods <= {"__future__", "datetime", "dataclasses", "types", "typing", "numpy",
                        "pandas", "src.compute.strategy.entry_stop_levels",
                        "src.compute.strategy.overextension",
                        "src.compute.strategy.tech_indicators"}


class TestBasisVerifiedMutations:
    """改壞實作 → 上列斷言必紅（以 monkeypatch 模擬突變，離線不改檔）。"""

    def test_mutation_false_still_old_sentence_goes_red(self, monkeypatch):
        # 突變：False 路徑仍輸出舊第一句
        monkeypatch.setattr(srf, "LIMITATION_UNADJUSTED_DECLARED", srf.LIMITATION_UNADJUSTED)
        monkeypatch.setattr(srf, "LIMITATION_EX_RIGHTS_DISTORTION", "")
        f = facts_unverified(make_bars(300))
        with pytest.raises(AssertionError):
            assert f.limitations == (_DECL, _DIST, _MA)
        with pytest.raises(AssertionError):
            assert _OLD1 not in f.limitations

    def test_mutation_bool_check_removed_goes_red(self):
        # 突變：以 truthy 轉型取代 bool 檢查的行為 → 非 bool 不再 raise，拒絕測試會紅
        def mutant(df, *, as_of, basis_verified=True):
            return srf.build_stock_research_facts(df, as_of=as_of, basis_verified=bool(basis_verified))
        df = make_bars(30)
        for bad in (1, 0, None, "False"):
            with pytest.raises(pytest.fail.Exception):   # 內層「應 raise 卻沒 raise」→ Failed
                with pytest.raises(StockResearchFactsInputError, match="basis_verified"):
                    mutant(df, as_of=df.index[-1].date(), basis_verified=bad)

    def test_mutation_basis_not_switched_goes_red(self, monkeypatch):
        monkeypatch.setattr(srf, "PRICE_BASIS_UNADJUSTED_DECLARED", srf.PRICE_BASIS_UNADJUSTED)
        f = facts_unverified(make_bars(30))
        with pytest.raises(AssertionError):
            assert f.price_basis == "unadjusted_declared"
