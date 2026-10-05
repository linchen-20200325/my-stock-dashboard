"""批 Z2：HANDOFF 優先 3 —— 資料層授權 (c) 擋非有限值。

- Y2-n5：`compute_twii_bias` 遇 ±inf 收盤、均值溢位（近 1e308）或超大 int（10**400）
  不再產出 NaN／inf 乖離或拋 OverflowError，改走既有失敗值 None。
- Y2-n9：`fetch_vix_block` 的 `ma20` 在 VIX 收盤近 1e308 時溢位成 inf。

只擋資料、不加新字句（log 除外）、不動門檻、不動版面；有限 / 正常輸入與 main 相同。
每段都有「拔掉修復即轉紅」的斷言。
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from src.data.macro import macro_snapshot

_HUGE = 10 ** 400   # float() → OverflowError（不是 inf）


# ── Y2-n5：compute_twii_bias 擋非有限值 ─────────────────────────────────────────
def _twii(closes, dtype=None):
    idx = pd.date_range('2025-01-01', periods=len(closes), freq='D')
    return pd.DataFrame({'Close': pd.Series(closes, index=idx, dtype=dtype)}, index=idx)


@pytest.fixture
def _no_2y(monkeypatch):
    # 240 筆以上不會走 2y fallback；保險起見仍擋掉網路
    monkeypatch.setattr(macro_snapshot, 'fetch_twii_2y_for_ma240', lambda: None)


class TestTwiiBiasNonFinite:
    @pytest.mark.parametrize('bad', [math.inf, -math.inf])
    def test_latest_close_inf_is_failure(self, bad, _no_2y):
        assert macro_snapshot.compute_twii_bias(_twii([100.0] * 239 + [bad])) is None

    def test_latest_close_huge_int_is_failure_not_raise(self, _no_2y):
        # 修前 float(10**400) 拋 OverflowError
        out = macro_snapshot.compute_twii_bias(_twii([100] * 239 + [_HUGE], dtype=object))
        assert out is None

    def test_interior_huge_int_mean_is_failure_not_raise(self, _no_2y):
        closes = [100] * 200 + [_HUGE] + [100] * 39
        assert macro_snapshot.compute_twii_bias(_twii(closes, dtype=object)) is None

    def test_mean_overflow_is_failure(self, _no_2y):
        # 每筆都有限，但加總溢位 → 均值 inf（修前 bias 變 NaN、ma 變 inf）
        assert macro_snapshot.compute_twii_bias(_twii([1.7e308] * 240)) is None

    def test_interior_inf_is_failure(self, _no_2y):
        closes = [100.0] * 120 + [math.inf] + [100.0] * 119
        assert macro_snapshot.compute_twii_bias(_twii(closes)) is None

    def test_interior_neg_inf_is_failure(self, _no_2y):
        # 均線 -inf → calc_bias_pct 視為 ma≤0 回 None（乖離不會是 NaN），
        #   但修前 dict 仍帶 ma120/ma240 = -inf 出去 → 必須由均線檢查擋下
        closes = [100.0] * 120 + [-math.inf] + [100.0] * 119
        assert macro_snapshot.compute_twii_bias(_twii(closes)) is None

    def test_bias_result_non_finite_is_failure(self, monkeypatch, _no_2y):
        # 輸入有限、但乖離本身算成非有限 → 同樣走失敗值
        monkeypatch.setattr(macro_snapshot, 'calc_bias_pct', lambda *a, **k: math.inf)
        assert macro_snapshot.compute_twii_bias(_twii([100.0] * 240)) is None

    def test_latest_nan_still_dropped(self, _no_2y):
        # NaN 末筆早已由 dropna 剔除（既有行為，不變）：以前一筆為末筆照常計算
        out = macro_snapshot.compute_twii_bias(_twii([100.0] * 239 + [math.nan]))
        assert out is not None and out['price'] == 100.0 and out['data_days'] == 239
        assert out['bias_20'] == 0.0

    def test_finite_unchanged(self, _no_2y):
        closes = [15000.0 + 7.3 * i + (i % 11) * 13.1 for i in range(260)]
        out = macro_snapshot.compute_twii_bias(_twii(closes))
        s = pd.Series(closes)
        lp = float(s.iloc[-1])

        def _b(n):
            ma = float(s.tail(n).mean())
            return round((lp - ma) / ma * 100.0, 1)
        assert (out['bias_20'], out['bias_60'], out['bias_240']) == (_b(20), _b(60), _b(240))
        assert out['price'] == lp and out['ma120'] == float(s.tail(120).mean())
        assert out['data_days'] == 260 and out['is_estimated'] is False

    def test_negative_zero_still_normalised(self, _no_2y):
        out = macro_snapshot.compute_twii_bias(_twii([100.0] * 239 + [99.97]))
        for k in ('bias_20', 'bias_60', 'bias_240'):
            assert out[k] == 0.0 and math.copysign(1, out[k]) == 1, (k, out[k])

    def test_uncomputable_bias_still_none_not_failure(self, _no_2y):
        # Y2 語意不變：MA ≤ 0 算不出 → 欄位 None，整體仍回 dict
        out = macro_snapshot.compute_twii_bias(_twii([0.0] * 240))
        assert out is not None and (out['bias_20'], out['bias_60'], out['bias_240']) == (None, None, None)
