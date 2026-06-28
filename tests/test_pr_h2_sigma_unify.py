"""v18.334 PR-H2 — calc_sigma_metrics() σ 計算統一 SSOT 守衛測試。

R-3 audit 結論「部分統一」實作:
- 計算層統一(etf_helpers.calc_sigma_metrics)
- 分級邏輯保留兩套(Quick=MA20±nσ 5段 / Deep=MA240 z-score 4段)
- UX 加文案標註「⚡短線」/「📅長線」消除 user 對「同檔不同訊號」困惑

驗證:
- calc_sigma_metrics 函式契約(回傳 7 個 key)
- 邊界:空 df / df < 20 / 20≤n<60 / 60≤n<240 / n≥240 / n≥window
- caller 已改用 SSOT(etf_calc + etf_tab_single)
- 文案標註已加(短線/長線前綴 + 對照說明 caption)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compute.etf import calc_sigma_metrics


def _make_df(n: int, seed: int = 42) -> pd.DataFrame:
    """造 n 日合成價格序列(隨機漫步)。"""
    rng = np.random.RandomState(seed)
    returns = rng.normal(0, 0.01, n)
    prices = 100 * (1 + returns).cumprod()
    return pd.DataFrame({'Close': prices})


class TestCalcSigmaMetricsContract:
    """函式 API 契約 — 回傳 7 個固定 key。"""

    def test_returns_dict_with_seven_keys(self):
        result = calc_sigma_metrics(_make_df(300))
        expected_keys = {'std_price', 'std_pct_annual', 'ma20', 'ma60', 'ma240', 'n'}
        assert expected_keys.issubset(set(result.keys()))

    def test_returns_dict_not_raise(self):
        """fail loud:邊界輸入應回 None 欄位,不 raise。"""
        result = calc_sigma_metrics(None)
        assert result['n'] == 0
        assert all(v is None for k, v in result.items() if k != 'n')


class TestEmptyAndSmall:
    """邊界 — 空 / 小資料。"""

    def test_none_input(self):
        r = calc_sigma_metrics(None)
        assert r['n'] == 0
        assert r['ma20'] is None
        assert r['std_price'] is None

    def test_empty_df(self):
        r = calc_sigma_metrics(pd.DataFrame())
        assert r['n'] == 0

    def test_no_close_column(self):
        r = calc_sigma_metrics(pd.DataFrame({'Open': [1, 2, 3]}))
        assert r['n'] == 0
        assert r['ma20'] is None

    def test_below_20_days_all_none(self):
        r = calc_sigma_metrics(_make_df(15))
        assert r['n'] == 15
        assert r['ma20'] is None
        assert r['ma60'] is None
        assert r['ma240'] is None
        assert r['std_price'] is None

    def test_20_to_59_days_only_ma20(self):
        r = calc_sigma_metrics(_make_df(30))
        assert r['n'] == 30
        assert r['ma20'] is not None
        assert r['ma60'] is None
        assert r['ma240'] is None

    def test_60_to_239_days_ma20_and_ma60(self):
        r = calc_sigma_metrics(_make_df(100))
        assert r['ma20'] is not None
        assert r['ma60'] is not None
        assert r['ma240'] is None

    def test_240_plus_days_all_ma(self):
        r = calc_sigma_metrics(_make_df(260))
        assert r['ma20'] is not None
        assert r['ma60'] is not None
        assert r['ma240'] is not None


class TestStdComputation:
    """σ 計算 — std_price 與 std_pct_annual 邏輯。"""

    def test_full_window_has_both_stds(self):
        r = calc_sigma_metrics(_make_df(300), window=252)
        assert r['std_price'] is not None
        assert r['std_price'] > 0
        assert r['std_pct_annual'] is not None
        assert r['std_pct_annual'] > 0

    def test_below_window_no_stds(self):
        """n < window 時 std 應為 None(對應原 etf_calc 行為)。"""
        r = calc_sigma_metrics(_make_df(100), window=252)
        assert r['std_price'] is None
        assert r['std_pct_annual'] is None

    def test_zero_volatility_constant_price(self):
        """常數價格 std = 0 → 應回 None(避免下游除 0)。"""
        df = pd.DataFrame({'Close': [100.0] * 300})
        r = calc_sigma_metrics(df, window=252)
        assert r['std_price'] is None or r['std_price'] == 0
        assert r['std_pct_annual'] is None

    def test_std_pct_annual_is_annualized(self):
        """年化 σ ≈ daily_std × √252 × 100。"""
        df = _make_df(300, seed=1)
        r = calc_sigma_metrics(df, window=252)
        daily_ret = df['Close'].tail(252).pct_change().dropna()
        expected = float(daily_ret.std()) * (252 ** 0.5) * 100
        assert abs(r['std_pct_annual'] - expected) < 1e-6


class TestCustomWindow:
    """window 參數行為。"""

    def test_smaller_window_works(self):
        r = calc_sigma_metrics(_make_df(60), window=30)
        assert r['std_price'] is not None

    def test_window_larger_than_data_returns_none_std(self):
        r = calc_sigma_metrics(_make_df(50), window=100)
        assert r['std_price'] is None


class TestEtfCalcUsesSSOT:
    """etf_calc 已改用 calc_sigma_metrics SSOT,不再 inline std。"""

    def test_etf_calc_imports_sigma_metrics(self):
        """v18.335 PR-H3 multi-line import 後仍可偵測。"""
        src = open('src/compute/etf/etf_calc.py', encoding='utf-8').read()
        assert 'from src.compute.etf.etf_helpers import' in src
        assert 'calc_sigma_metrics' in src

    def test_etf_calc_uses_metrics_dict(self):
        src = open('src/compute/etf/etf_calc.py', encoding='utf-8').read()
        assert 'calc_sigma_metrics(df, window=TRADING_DAYS_PER_YEAR)' in src
        # 舊 inline 已淨空
        assert "_std = float(df['Close'].tail(TRADING_DAYS_PER_YEAR).std())" not in src
        assert "df['Close'].rolling(20).mean().iloc[-1]" not in src


class TestEtfSingleUsesSSOT:
    """etf_tab_single MK#11 已改用 calc_sigma_metrics SSOT。"""

    def test_etf_single_imports_sigma_metrics(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert 'calc_sigma_metrics' in src

    def test_etf_single_uses_metrics_dict(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert 'calc_sigma_metrics(df, window=252)' in src
        # 舊 inline 已淨空
        assert "df['Close'].pct_change().tail(252).dropna()" not in src


class TestUxAnnotation:
    """文案標註 — 「⚡ 短線」/「📅 長線」前綴消除 user 困惑。"""

    def test_etf_calc_has_short_term_prefix(self):
        src = open('src/compute/etf/etf_calc.py', encoding='utf-8').read()
        assert '⚡短線' in src

    def test_etf_single_has_long_term_prefix(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert '📅 長線' in src or '📅長線' in src

    def test_etf_single_has_disambiguation_caption(self):
        """應加 caption 說明兩套 σ 的時間尺度差異。"""
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert '不同時間尺度' in src

    def test_portfolio_column_header_disambiguated(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert '⚡短線 σ 位階' in src


class TestModulesImportable:
    def test_etf_helpers_clean(self):
        from src.compute.etf import etf_helpers  # noqa: F401

    def test_etf_calc_clean(self):
        from src.compute.etf import etf_calc  # noqa: F401

    def test_etf_tab_single_clean(self):
        import etf_tab_single  # noqa: F401

    def test_etf_tab_portfolio_clean(self):
        import etf_tab_portfolio  # noqa: F401
