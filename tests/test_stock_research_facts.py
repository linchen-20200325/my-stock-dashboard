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


# ════════════════════════════════════════════════════════════════════
# F1 數值安全（非有限 / 溢位 / 下溢 → None + 具名限制；不設價量業務上限）
# ════════════════════════════════════════════════════════════════════

from src.compute.strategy.tech_indicators import (  # noqa: E402
    calc_ma_series, calc_rsi, calc_volume_ratio)

_NUM = "下列指標因數值超出可穩定計算的範圍而不予輸出："
_FMAX = 1.7e308
_FMAX_REAL = float(np.finfo(np.float64).max)


def _num_sentence(*names: str) -> str:
    return _NUM + "、".join(names) + "。"


def _num_lims(f: StockResearchFacts) -> list[str]:
    return [s for s in f.limitations if s.startswith(_NUM)]


def _shape_df(n: int, level: float, vol=None) -> pd.DataFrame:
    """確定性、有漲跌的價格序列，價位約 level（OHLC 一致：low<=open/close<=high）。"""
    i = np.arange(n)
    close = level * (0.95 + 0.04 * ((i * 7) % 10) / 10.0)
    open_ = close.copy()
    high = close * 1.01
    low = close * 0.99
    volume = (np.full(n, 1000.0) if vol is None else np.asarray(vol, dtype="float64"))
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": volume},
                        index=pd.bdate_range(_START, periods=n))


def _vol(n: int, prev5=None, today=None, base=1000.0):
    v = np.full(n, base)
    if prev5 is not None:
        v[-6:-1] = prev5
    if today is not None:
        v[-1] = today
    return v


def _exact_ratio(prev5, today) -> float:
    """獨立精確算式（Python 整數有理數，不經浮點加總）。"""
    from fractions import Fraction
    avg = sum(Fraction(float(x)) for x in prev5) / 5
    return float(Fraction(float(today)) / avg)


# ── 斷言輔助（突變測試也會呼叫它們，故寫成函式）────────────────────────

def _assert_volume_overflow_guard() -> None:
    for vol in (_vol(30, 1.7e308, 1.7e308), _vol(30, 1.7e308), _vol(30, 1.79e308, 1.0),
                np.full(30, 1.79e308)):
        f = facts_of(_shape_df(30, 100.0, vol))
        assert f.volume_ratio5 is None
        assert _num_sentence("量比5") in f.limitations


def _assert_ma_overflow_guard() -> None:
    f = facts_of(_shape_df(300, 1.7e308))
    assert all(f.ma[w] is None for w in (5, 20, 60, 120, 240))
    assert _num_sentence("MA5", "MA20", "MA60", "MA120", "MA240") in [
        s.replace("乖離20與過熱評估、", "") for s in _num_lims(f)] or \
        any("MA5、MA20、MA60、MA120、MA240" in s for s in _num_lims(f))


def _assert_tiny_price_guard() -> None:
    f = facts_of(_shape_df(300, 1e-300))
    assert f.close is None and f.rsi14 is None and f.bias20_pct is None
    assert f.support_20d is None and f.resistance_20d is None
    assert all(v is None for v in f.ma.values())
    assert len(_num_lims(f)) == 1


class TestF1VolumeNumericSafety:
    def test_all_volume_1_7e308_ratio_is_none_not_fake_zero(self):
        # 修復前：前 5 日量加總溢位 → inf 均量 → 量比偽 0.0（真值 1.0）
        f = facts_of(_shape_df(30, 100.0, np.full(30, _FMAX)))
        assert f.volume_ratio5 is None
        assert _num_sentence("量比5") in f.limitations

    @pytest.mark.parametrize("prev5", [
        [1.7e308, 1.7e308, 1000.0, 1000.0, 1000.0],   # 2 根極大：精確總和 > float 上限
        [1.7e308] * 5,
        [1.79e308, 1.0, 1.0, 1.0, 1.0],               # 單根逼近上限但總和仍可表示 → 見下方獨立斷言
    ])
    def test_overflowing_prev5_sum_gives_none(self, prev5):
        v = _vol(30)
        v[-6:-1] = prev5
        f = facts_of(_shape_df(30, 100.0, v))
        if sum(__import__("fractions").Fraction(x) for x in prev5) > __import__("fractions").Fraction(_FMAX_REAL):
            assert f.volume_ratio5 is None
            assert _num_sentence("量比5") in f.limitations
        else:
            # 總和未溢位：照常輸出（極小比值屬四捨五入精度，非偽值），無數值限制句
            assert f.volume_ratio5 is not None and not _num_lims(f)

    def test_three_of_five_1_7e308(self):
        v = _vol(30)
        v[-6:-3] = 1.7e308
        f = facts_of(_shape_df(30, 100.0, v))
        assert f.volume_ratio5 is None and _num_lims(f)

    def test_ratio_overflow_with_subnormal_prev5(self):
        # 前 5 日量 5e-324、今日 1000：比值 > float 上限（修復前為 inf）
        f = facts_of(_shape_df(30, 100.0, _vol(30, 5e-324)))
        assert f.volume_ratio5 is None
        assert _num_sentence("量比5") in f.limitations

    def test_mean_underflow_to_zero_is_flagged_not_silent(self):
        # 精確均量 > 0 但 float 均量下溢成 0 → 來源回 None；不可無聲略過，須具名
        v = _vol(30)
        v[-6:-1] = [5e-324, 0.0, 0.0, 0.0, 0.0]
        f = facts_of(_shape_df(30, 100.0, v))
        assert f.volume_ratio5 is None
        assert _num_sentence("量比5") in f.limitations

    @pytest.mark.parametrize("big", [1e300, 1e200, 1e100])
    def test_large_volumes_still_computable(self, big):
        # 1e300 級量能不得被誤殺
        for vol, expect in (
            (np.full(30, big), 1.0),
            (_vol(30, big, big), 1.0),
            (_vol(30, 1000.0, big), None),   # 今日極大：以獨立精確算式比對
        ):
            f = facts_of(_shape_df(30, 100.0, vol))
            assert f.volume_ratio5 is not None
            if expect is None:
                ex = _exact_ratio(vol[-6:-1], vol[-1])
                assert math.isclose(f.volume_ratio5, ex, rel_tol=1e-9)
            else:
                assert isc(f.volume_ratio5, expect)
            assert not _num_lims(f)

    def test_ratio_matches_legacy_function_for_1e300_mixed(self):
        v = _vol(30)
        v[-6:-1] = [1e300, 2e300, 3e300, 4e300, 5e300]
        v[-1] = 6e300
        df = _shape_df(30, 100.0, v)
        f = facts_of(df)
        assert f.volume_ratio5 == calc_volume_ratio(df, 5) == 2.0
        assert not _num_lims(f)

    @pytest.mark.parametrize("small", [1e-300, 5e-324])
    def test_tiny_volume_no_fake_zero(self, small):
        f = facts_of(_shape_df(30, 100.0, np.full(30, small)))
        assert isc(f.volume_ratio5, 1.0)
        # 前 5 日量極小、今日正常：比值極大但有限（1e-300 時可表示）
        if small == 1e-300:
            f2 = facts_of(_shape_df(30, 100.0, _vol(30, small)))
            assert math.isclose(f2.volume_ratio5, _exact_ratio([small] * 5, 1000.0), rel_tol=1e-9)

    def test_true_zero_vs_missing_vs_legit_zero(self):
        # 真 0：今日量 0 且前 5 日正常 → 0.0（合法，停牌 / 跌停鎖死）
        f0 = facts_of(_shape_df(30, 100.0, _vol(30, today=0.0)))
        assert f0.volume_ratio5 is not None and isc(f0.volume_ratio5, 0.0)
        assert not _num_lims(f0)
        # 前 5 日均量精確為 0：沿用來源既有語意（None），不是數值失真，不加數值限制句
        fz = facts_of(_shape_df(30, 100.0, _vol(30, 0.0)))
        assert fz.volume_ratio5 is None and not _num_lims(fz)
        # 缺值（根數不足）：None + 根數不足句，非數值句
        fm = facts_of(_shape_df(5, 100.0))
        assert fm.volume_ratio5 is None and not _num_lims(fm)
        assert any("量比5" in s and s.startswith("下列指標根數不足") for s in fm.limitations)

    def test_window_boundary_volume_ratio(self):
        v6 = np.full(6, _FMAX)
        f6 = facts_of(_shape_df(6, 100.0, v6))          # 6 根：量比 5 恰可算
        assert f6.volume_ratio5 is None and _num_sentence("量比5") in f6.limitations
        f5 = facts_of(_shape_df(5, 100.0, np.full(5, _FMAX)))   # 5 根：根數不足
        assert f5.volume_ratio5 is None and not _num_lims(f5)

    def test_volume_extremes_never_touch_price_fields(self):
        base = facts_of(_shape_df(300, 100.0))
        f = facts_of(_shape_df(300, 100.0, _vol(300, 1.7e308)))
        for name in ("close", "ma", "rsi14", "bias20_pct", "overextension_level",
                     "overheated", "support_20d", "resistance_20d"):
            assert getattr(f, name) == getattr(base, name)


class TestF1PriceNumericSafety:
    def test_price_1e300_and_1e200_fully_computable(self):
        base = facts_of(_shape_df(300, 100.0))
        for lvl in (1e300, 1e200):
            f = facts_of(_shape_df(300, lvl))
            assert not _num_lims(f)
            assert f.rsi14 == base.rsi14
            assert f.overextension_level == base.overextension_level
            assert f.overheated == base.overheated
            assert math.isclose(f.bias20_pct, base.bias20_pct, abs_tol=1.5e-4)
            for w in (5, 20, 60, 120, 240):
                ex = _exact_mean_of_last(_shape_df(300, lvl)["close"].to_numpy(), w)
                assert math.isclose(f.ma[w], ex, rel_tol=1e-9)
            assert f.support_20d is not None and f.resistance_20d is not None

    def test_price_1_7e308_ma_none_with_named_limitation(self):
        # 修復前：rolling 加總溢位 → NaN → MA 被無聲吞成 None；乖離改用較早的 MA（有限偽值）
        f = facts_of(_shape_df(300, _FMAX))
        _assert_ma_overflow_guard()
        assert f.bias20_pct is None and f.overextension_level is None and f.overheated is None
        assert any("乖離20與過熱評估" in s for s in _num_lims(f))
        assert f.close is not None and np.isfinite(f.close)
        assert f.support_20d is not None and f.resistance_20d is not None
        assert f.rsi14 is not None     # RSI 為尺度不變量，仍可算且與獨立算式一致
        assert f.rsi14 == facts_of(_shape_df(300, 100.0)).rsi14

    def test_price_1_7e308_does_not_use_stale_earlier_ma_for_bias(self):
        # 前段價位正常、最後 20 根逼近上限：MA20 溢位，不得退用較早 MA 算乖離
        df = _shape_df(60, 100.0)
        for c in ("open", "high", "low", "close"):
            df.iloc[-20:, df.columns.get_loc(c)] = df.iloc[-20:, df.columns.get_loc(c)] * 1e305
        f = facts_of(df)
        assert f.bias20_pct is None and f.overheated is None
        assert _num_lims(f)

    def test_tiny_price_1e300_no_fake_zero_anywhere(self):
        # 修復前：close / MA / 支撐 / 壓力 四捨五入成 0.0；RSI 因 +1e-10 epsilon 成偽 0.0
        f = facts_of(_shape_df(300, 1e-300))
        _assert_tiny_price_guard()
        assert _num_lims(f) == [_num_sentence(
            "收盤價", "MA5", "MA20", "MA60", "MA120", "MA240", "RSI14",
            "乖離20與過熱評估", "支撐壓力")]
        assert f.overextension_level is None and f.overheated is None

    def test_5e324_prices(self):
        n = 300
        c = np.full(n, 5e-324)
        df = pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                           "volume": np.full(n, 1000.0)},
                          index=pd.bdate_range(_START, periods=n))
        f = facts_of(df)
        assert f.close is None and f.support_20d is None
        assert all(v is None for v in f.ma.values()) and f.rsi14 is None

    def test_normal_small_price_unaffected(self):
        # 台股最小報價級距 0.01：價位 0.05 的輸出須與一般算式一致且無數值限制句
        df = _shape_df(300, 0.05)
        f = facts_of(df)
        assert not _num_lims(f)
        assert f.close is not None and f.close > 0 and f.support_20d > 0
        assert f.rsi14 == calc_rsi(df, 14)

    def test_zero_never_substituted_for_positive_price_output(self):
        for lvl in (1e-300, 1e-200, 1e-10, 1e-6, 1e-4, 1e-3, 1.0, 1e50, 1e300, _FMAX):
            f = facts_of(_shape_df(300, lvl))
            for v in (f.close, f.support_20d, f.resistance_20d, *f.ma.values()):
                assert v is None or v > 0, (lvl, v)
            assert f.rsi14 is None or f.rsi14 > 0

    def test_mixed_extreme_price_and_volume(self):
        f = facts_of(_shape_df(300, 1e-300, np.full(300, _FMAX)))
        assert f.volume_ratio5 is None and f.close is None
        (sent,) = _num_lims(f)
        assert "量比5" in sent and "收盤價" in sent
        g = facts_of(_shape_df(300, _FMAX, np.full(300, 1e-300)))
        assert isc(g.volume_ratio5, 1.0) and all(v is None for v in g.ma.values())

    @pytest.mark.parametrize("w", [5, 20, 60, 120, 240])
    def test_ma_window_boundary(self, w):
        at = facts_of(_shape_df(w, _FMAX))
        assert at.ma[w] is None and any(f"MA{w}" in s for s in _num_lims(at))
        below = facts_of(_shape_df(w - 1, _FMAX))
        assert below.ma[w] is None
        assert not any(f"MA{w}" in s for s in _num_lims(below))      # 根數不足句，不是數值句
        assert any(f"MA{w}" in s and s.startswith("下列指標根數不足") for s in below.limitations)

    def test_rsi_window_boundary(self):
        at = facts_of(_shape_df(15, 1e-300))
        assert at.rsi14 is None and any("RSI14" in s for s in _num_lims(at))
        below = facts_of(_shape_df(14, 1e-300))
        assert below.rsi14 is None and not any("RSI14" in s for s in _num_lims(below))

    def test_overextension_window_boundary(self):
        at = facts_of(_shape_df(21, _FMAX))
        assert at.bias20_pct is None and any("乖離20與過熱評估" in s for s in _num_lims(at))
        below = facts_of(_shape_df(20, _FMAX))
        assert not any("乖離" in s for s in _num_lims(below))

    @pytest.mark.parametrize("n", [5, 6, 12, 19, 20, 21])
    def test_support_resistance_window_boundary(self, n):
        f = facts_of(_shape_df(n, 1e-300))
        assert f.support_20d is None and f.resistance_20d is None and f.support_resistance_bars is None
        assert any("支撐壓力" in s for s in _num_lims(f))
        g = facts_of(_shape_df(4, 1e-300))
        assert not any("支撐壓力" in s for s in _num_lims(g))
        assert any("支撐壓力" in s and s.startswith("下列指標根數不足") for s in g.limitations)

    def test_flat_prices_still_use_existing_rsi_note(self):
        c = np.full(40, 100.0)
        df = pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c,
                           "volume": np.full(40, 1000.0)},
                          index=pd.bdate_range(_START, periods=40))
        f = facts_of(df)
        assert f.rsi14 is None and not _num_lims(f)
        assert "RSI14 因整段收盤價完全沒有變動而無定義。" in f.limitations


def _exact_mean_of_last(arr, w) -> float:
    from fractions import Fraction
    return float(sum(Fraction(float(x)) for x in arr[-w:]) / w)


class TestF1LimitationsWording:
    def test_sentence_verbatim_and_names_only(self):
        assert _NUM == "下列指標因數值超出可穩定計算的範圍而不予輸出："
        assert srf._LIMITATION_NUMERIC_PREFIX == _NUM
        f = facts_of(_shape_df(300, 1e-300, np.full(300, _FMAX)))
        (sent,) = _num_lims(f)
        assert not any(ch.isdigit() for ch in sent.replace("MA5", "").replace("MA20", "")
                       .replace("MA60", "").replace("MA120", "").replace("MA240", "")
                       .replace("RSI14", "").replace("量比5", "").replace("乖離20", ""))

    @pytest.mark.parametrize("df", [
        _shape_df(300, 1e-300, np.full(300, _FMAX)),
        _shape_df(300, _FMAX),
        _shape_df(30, 100.0, _vol(30, 5e-324)),
    ])
    def test_no_forbidden_words_in_new_sentences(self, df):
        f = facts_of(df)
        assert _num_lims(f)
        for s in _all_strings(f):
            for w in _FORBIDDEN:
                assert w not in s, f"禁字 {w!r} 出現在 {s!r}"

    def test_sentence_order_after_existing_ones(self):
        f = facts_of(_shape_df(10, 1e-300))
        lim = f.limitations
        assert lim[0] == LIMITATION_UNADJUSTED and lim[1] == LIMITATION_MA_REFERENCE
        assert lim[-1].startswith(_NUM)


class TestF1BaselineUnchanged:
    """正常輸入逐欄等於「直接呼叫既有函式」的結果（即修復前行為），且不含數值限制句。"""

    _NS = [1, 4, 5, 6, 14, 15, 16, 20, 21, 22, 30, 59, 60, 61, 100, 119, 120, 121,
           239, 240, 241, 300]

    @pytest.mark.parametrize("seed,n", list(enumerate(_NS)))
    def test_fields_equal_legacy_calls(self, seed, n):
        df = make_bars(n, seed=seed)
        f = facts_of(df)
        assert not _num_lims(f)
        close = df["close"].astype("float64")
        for w in (5, 20, 60, 120, 240):
            exp = None if n < w else round(float(calc_ma_series(close, w).iloc[-1]), 4)
            assert f.ma[w] == exp
        assert f.rsi14 == (calc_rsi(df, 14) if n >= 15 else None)
        assert f.volume_ratio5 == (calc_volume_ratio(df, 5) if n >= 6 else None)
        if n >= 21:
            oe = assess_price_overextension(close, ma_window=20, rsi_period=14)
            assert f.bias20_pct == round(float(oe["bias_pct"]), 4)
            assert f.overextension_level == oe["level"] and f.overheated == oe["overheated"]
        else:
            assert f.bias20_pct is None and f.overheated is None
        assert f.close == round(float(close.iloc[-1]), 4)
        if n >= 5:
            m = min(n, 20)
            assert f.support_20d == round(float(df["low"].tail(m).min()), 2)
            assert f.resistance_20d == round(float(df["high"].tail(m).max()), 2)
            assert f.support_resistance_bars == m
        else:
            assert f.support_20d is None


class TestF1Mutations:
    """拔掉數值防線 → 對應斷言輔助函式必紅（pytest.raises(AssertionError)）。"""

    def test_baseline_helpers_pass(self):
        _assert_volume_overflow_guard()
        _assert_ma_overflow_guard()
        _assert_tiny_price_guard()

    def test_mutation_volume_guard_removed(self, monkeypatch):
        monkeypatch.setattr(srf, "_volume_ratio_valid", lambda legacy, volumes: True)
        with pytest.raises(AssertionError):
            _assert_volume_overflow_guard()

    def test_mutation_overflow_check_dropped_keeps_fake_zero(self, monkeypatch):
        # 只檢查「來源輸出是否貼近精確值」而不看中間值溢位 → 前 5 日極大 + 今日正常的 0.0 會被放行
        orig = srf._volume_ratio_valid

        def legacy_noerr(df, period=5):   # 重現預設警告設定下的來源行為（溢位不轉例外）
            with np.errstate(all="ignore"):
                avg = float(df["volume"].iloc[-(period + 1):-1].mean())
                return round(float(df["volume"].iloc[-1]) / avg, 2)
        monkeypatch.setattr(srf, "calc_volume_ratio", legacy_noerr)

        def weak(legacy, volumes):
            if legacy is not None and legacy == 0.0:
                return True
            return orig(legacy, volumes)
        monkeypatch.setattr(srf, "_volume_ratio_valid", weak)
        with pytest.raises(AssertionError):
            _assert_volume_overflow_guard()

    def test_mutation_rsi_guard_removed(self, monkeypatch):
        monkeypatch.setattr(srf, "_rsi_valid", lambda legacy, exact: legacy is not None)
        with pytest.raises(AssertionError):
            _assert_tiny_price_guard()

    def test_mutation_round_to_zero_guard_removed(self, monkeypatch):
        monkeypatch.setattr(srf, "_positive_rounds_to_zero", lambda x: False)
        with pytest.raises(AssertionError):
            _assert_tiny_price_guard()

    def test_mutation_ma_guard_removed_with_garbage_series(self, monkeypatch):
        # 來源給出「有限的錯值」且防線被拔 → 斷言必紅；防線在時改為 None
        import src.compute.strategy.tech_indicators as ti
        garbage = lambda close, window=20: close.rolling(window).mean() * 2.0 + 1.0  # noqa: E731
        monkeypatch.setattr(srf, "calc_ma_series", garbage)
        f = facts_of(make_bars(300))
        assert all(f.ma[w] is None for w in (5, 20, 60, 120, 240))
        assert len(_num_lims(f)) == 1
        monkeypatch.setattr(srf, "_ma_valid", lambda legacy, closes, w: True)
        g = facts_of(make_bars(300))
        with pytest.raises(AssertionError):
            assert all(g.ma[w] is None for w in (5, 20, 60, 120, 240))
        assert ti is not None

    def test_mutation_stale_ma_bias_guard_removed(self, monkeypatch):
        # 來源（模擬）在 MA20 溢位時退用較早 MA，給出有限的乖離與過熱判定。
        stale = {"level": "正常", "overheated": False, "bias_pct": 5.0,
                 "rsi": 50.0, "reasons": [], "icon": "🟢"}
        monkeypatch.setattr(srf, "assess_price_overextension", lambda *a, **k: dict(stale))
        df = _shape_df(60, 100.0)
        for c in ("open", "high", "low", "close"):
            df.iloc[-20:, df.columns.get_loc(c)] = df.iloc[-20:, df.columns.get_loc(c)] * 1e305
        f = facts_of(df)
        assert f.bias20_pct is None and f.overheated is None      # 防線在：不採用
        # 拔掉 MA20 驗證並讓 NaN 被前值填補 → 偽乖離 5.0 被輸出 → 斷言必紅
        monkeypatch.setattr(srf, "_ma_valid", lambda legacy, closes, w: True)
        monkeypatch.setattr(srf, "calc_ma_series",
                            lambda close, window=20: close.rolling(window).mean().ffill())
        g = facts_of(df)
        with pytest.raises(AssertionError):
            assert g.bias20_pct is None


class TestF1ValidatorUnits:
    """驗證器本身：有限但錯誤的來源值必須被拒；正確值必須被放行（防止驗證器被放鬆）。"""

    def test_ma_valid_rejects_finite_wrong_value(self):
        closes = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        assert srf._ma_valid(30.0, closes, 5)
        assert not srf._ma_valid(30.001, closes, 5)      # 相對誤差 3e-5，遠大於浮點誤差
        assert not srf._ma_valid(float("nan"), closes, 5)
        assert not srf._ma_valid(float("inf"), closes, 5)

    def test_volume_ratio_valid_rejects_finite_wrong_value(self):
        v = np.array([1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 2000.0])
        assert srf._volume_ratio_valid(2.0, v) is True
        assert srf._volume_ratio_valid(2.5, v) is False  # 偏離超過半個四捨五入階
        assert srf._volume_ratio_valid(None, v) is False
        assert srf._volume_ratio_valid(float("inf"), v) is False
        z = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 5.0])
        assert srf._volume_ratio_valid(None, z) is None  # 均量精確為 0：沿用來源語意

    def test_rsi_valid_rejects_finite_wrong_value(self):
        assert srf._rsi_valid(58.4, 58.43)
        assert not srf._rsi_valid(0.0, 58.43)            # epsilon 偽 0.0
        assert not srf._rsi_valid(58.4, 70.0)
        assert not srf._rsi_valid(None, 58.4)
        assert not srf._rsi_valid(58.4, None)

    def test_rsi_unbiased_scale_invariant(self):
        c = _shape_df(60, 1.0)["close"].to_numpy()
        base = srf._rsi_unbiased(c)
        for k in (1e-300, 1e-100, 1e100, 1e300):
            assert math.isclose(srf._rsi_unbiased(c * k), base, rel_tol=1e-9)

    def test_exact_mean_overflow_returns_none_not_inf(self):
        assert srf._exact_mean_float(np.array([1.7e308] * 5)) == 1.7e308
        assert srf._exact_mean_float(np.array([5e-324, 0.0])) is not None


# ── 補強：中度失真必須被拒（容差不得被放大）、支撐壓力歸零、尺度正規化、精確平均 ──

def _walk_df(n: int, level: float, seed: int) -> pd.DataFrame:
    """價位約 level 的隨機漫步（OHLC 一致）。"""
    rng = np.random.default_rng(seed)
    c = level * (1.0 + np.cumsum(rng.normal(0.0, 0.02, n)))
    c = np.maximum(c, level * 0.5)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
                         "volume": np.full(n, 1000.0)},
                        index=pd.bdate_range(_START, periods=n))


class TestF1ToleranceNotInflated:
    """來源值與獨立精確值相差「略大於一個四捨五入階」時必須判失真；
    把 _RSI_TOL / _REL_TOL / _VOL_RATIO_HALF_STEP 放大 10 倍的突變會讓這些轉紅。"""

    @pytest.mark.parametrize("delta", [0.2, 0.5, 0.9])
    def test_rsi_moderate_distortion_rejected(self, delta):
        assert not srf._rsi_valid(58.4 + delta, 58.4)
        assert not srf._rsi_valid(58.4 - delta, 58.4)

    def test_rsi_within_one_rounding_step_accepted(self):
        assert srf._rsi_valid(58.4, 58.43)          # 四捨五入內
        assert srf._rsi_valid(58.4, 58.49)          # 差 0.09：仍在一個四捨五入階內

    def test_rsi_rel_tol_additive_boundary(self):
        assert not srf._rsi_valid(58.5 + 5e-9, 58.4)   # 差 0.1 + 5e-9：略超出

    @pytest.mark.parametrize("delta", [0.01, 0.03, 0.049])
    def test_volume_ratio_moderate_distortion_rejected(self, delta):
        v = np.array([1000.0] * 5 + [2000.0])        # 精確比值 2.0
        assert srf._volume_ratio_valid(2.0 + delta, v) is False
        assert srf._volume_ratio_valid(2.0 - delta, v) is False

    def test_volume_ratio_rounding_step_accepted(self):
        v = np.array([1000.0] * 5 + [2034.0])        # 精確 2.034，來源四捨五入 2.03
        assert srf._volume_ratio_valid(2.03, v) is True

    def test_volume_ratio_relative_tolerance_not_inflated(self):
        v = np.array([1.0] * 5 + [1e12])             # 精確比值 1e12
        assert srf._volume_ratio_valid(1e12, v) is True
        assert srf._volume_ratio_valid(1e12 * (1 + 5e-9), v) is False   # 相對差 5e-9 > 1e-9

    def test_ma_relative_tolerance_not_inflated(self):
        closes = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        assert srf._ma_valid(30.0 * (1 + 5e-10), closes, 5)
        assert not srf._ma_valid(30.0 * (1 + 5e-9), closes, 5)

    def test_integration_rsi_off_by_half_is_none(self, monkeypatch):
        df = make_bars(60)
        exact = srf._rsi_unbiased(df["close"].to_numpy())
        monkeypatch.setattr(srf, "calc_rsi", lambda d, period=14: round(exact + 0.5, 1))
        f = facts_of(df)
        assert f.rsi14 is None and any("RSI14" in s for s in _num_lims(f))
        assert f.overheated is None          # 同時不輸出依 RSI 而定的過熱判定

    def test_integration_volume_ratio_off_by_003_is_none(self, monkeypatch):
        df = make_bars(60)
        true = calc_volume_ratio(df, 5)
        monkeypatch.setattr(srf, "calc_volume_ratio", lambda d, period=5: round(true + 0.03, 2))
        f = facts_of(df)
        assert f.volume_ratio5 is None and _num_sentence("量比5") in f.limitations


class TestF1SupportResistanceZeroGuard:
    @pytest.mark.parametrize("seed", [0, 1, 2, 3])
    def test_price_around_1e_3_support_resistance_none_with_sentence(self, seed):
        # 價位約 1e-3：來源 2 位小數四捨五入會給出 0.0 / 0.0（偽 0）
        df = _walk_df(60, 1e-3, seed)
        from src.compute.strategy.entry_stop_levels import compute_support_resistance
        legacy = compute_support_resistance(df, current_price=float(df["close"].iloc[-1]))
        assert legacy.support is not None and not legacy.support > 0     # 舊路徑確為偽 0.0
        f = facts_of(df)
        assert f.support_20d is None and f.resistance_20d is None
        assert f.support_resistance_bars is None
        assert any("支撐壓力" in s for s in _num_lims(f))
        assert f.close is not None and f.close > 0      # close 在 4 位小數仍可表示，不受影響


class TestF1RsiScaleNormalizationAndExactMean:
    def test_rsi_normalization_needed_for_subnormal_prices(self):
        # 價格為 5e-324 的整數倍（次正規數）：未正規化時 ewm 的乘法下溢而失真
        rng = np.random.default_rng(5)
        k = np.maximum(np.round(1000 + rng.normal(0, 3, 40).cumsum()), 1.0)
        c = k * 5e-324 * 2.0 ** 0           # 次正規數網格上的精確價格
        c = np.maximum(c, 5e-324)
        got = srf._rsi_unbiased(c)
        assert got is not None
        # 獨立算式：以 2**1000 精確放大回常規範圍後，用一般 Wilder 公式
        s = pd.Series(np.ldexp(c, 1000))
        d = s.diff()
        g = float(d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
        lo = float((-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
        expect = 100.0 - 100.0 / (1.0 + g / lo)
        assert math.isclose(got, expect, rel_tol=1e-9)

    def test_ma_valid_uses_exact_mean_not_float_mean(self):
        # 精確平均 1.7e308 可表示；浮點加總會溢位成 inf。來源若（例如換版 pandas）給出正確值，
        # 驗證器須放行；若改成以浮點平均當基準，會把正確值誤判為失真。
        closes = np.array([1.7e308] * 5)
        assert srf._ma_valid(1.7e308, closes, 5)
        assert not srf._ma_valid(1.6e308, closes, 5)
