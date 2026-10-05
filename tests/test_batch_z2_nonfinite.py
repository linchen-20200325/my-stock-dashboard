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


# ── Y2-n5 QA-B：每條均線／每個乖離各自都要被檢查（單一非有限、其餘有限）──────────
_MA_WINDOWS = {'ma20': 20, 'ma60': 60, 'ma120': 120, 'ma240': 240}


def _put(n, pts, base=100.0):
    c = [base] * n
    for i, v in pts:
        c[i] = v
    return c


def _mas_like_code(closes, dtype=None):
    """與 compute_twii_bias 同一算法（dropna → tail(min(w, n)).mean()）獨立重算四條均線。"""
    cs = _twii(closes, dtype)['Close'].dropna()
    n = len(cs)
    return {k: float(cs.tail(min(w, n)).mean()) for k, w in _MA_WINDOWS.items()}


def _assert_only_non_finite(vals: dict, target: str):
    """前提自證：恰好 target 一個非有限。±1e308 加總順序若隨 numpy 版本漂移，
    這裡會大聲失敗，而不是讓測試悄悄不再隔離該均線／乖離。"""
    bad = sorted(k for k, v in vals.items() if v is not None and not math.isfinite(v))
    assert bad == [target], f'前提不成立（輸入已無法隔離 {target}）：{vals}'


class TestTwiiBiasEachValueChecked:
    # 均線 +inf 會讓對應乖離變 NaN（被結果檢查擋）；故 ma20/60/240 用 -inf
    #   （calc_bias_pct 視為 ma≤0 回 None），ma120 沒有對應乖離可用 +inf。
    #   inf 只能靠 ±1e308 在小窗溢位、大窗相消做出 —— 依加總順序，所以先自證前提。
    @pytest.mark.parametrize('target, closes', [
        ('ma20', _put(240, [(180, 1.5e308), (220, -1e308), (228, -1e308)])),
        ('ma60', _put(130, [(25, 1.5e308), (64, 9e307), (81, -1e308), (122, -9e307)])),
        ('ma120', _put(203, [(68, -1.5e308), (90, 9e307), (140, -9e307), (186, 9e307)])),
        # ma240 單獨非有限是確定性的：-inf 只落在 ma240 的窗內
        ('ma240', _put(240, [(50, -math.inf)])),
    ])
    def test_single_ma_non_finite_is_failure(self, target, closes, _no_2y):
        _assert_only_non_finite(_mas_like_code(closes), target)
        assert macro_snapshot.compute_twii_bias(_twii(closes)) is None

    # 乖離溢位、均線全有限：object 欄的 Python int 精確相消（確定性，與 numpy 版本無關）
    #   → 均線很小、末筆價很大。
    @pytest.mark.parametrize('target, closes', [
        ('bias_20', _put(240, [(-1, 17 * 10**307), (-5, -17 * 10**307), (-30, 10**307)], base=50)),
        ('bias_60', _put(240, [(-1, 17 * 10**307), (-30, -17 * 10**307), (-100, 10**307)], base=50)),
        ('bias_240', _put(240, [(-1, 17 * 10**307), (50, -17 * 10**307)], base=50)),
    ])
    def test_single_bias_non_finite_is_failure(self, target, closes, _no_2y):
        from shared.calc_helpers import calc_bias_pct
        mas = _mas_like_code(closes, object)
        assert all(math.isfinite(v) for v in mas.values()), mas
        lp = float(closes[-1])
        biases = {f'bias_{w}': calc_bias_pct(lp, mas[f'ma{w}'], decimals=1) for w in (20, 60, 240)}
        _assert_only_non_finite(biases, target)
        assert macro_snapshot.compute_twii_bias(_twii(closes, dtype=object)) is None


# ── Y2-n9：fetch_vix_block 的 ma20 溢位 ─────────────────────────────────────────
@pytest.fixture
def _clear_vix_cache():
    macro_snapshot.fetch_vix_block.clear()
    yield
    macro_snapshot.fetch_vix_block.clear()


def _vix_df(closes):
    idx = pd.date_range('2026-04-01', periods=len(closes), freq='D')
    return pd.DataFrame({'Close': closes}, index=idx)


def _no_non_finite(obj):
    if isinstance(obj, dict):
        return all(_no_non_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return all(_no_non_finite(v) for v in obj)
    if isinstance(obj, float):
        return math.isfinite(obj)
    return True


class TestVixMa20Overflow:
    def test_ma20_overflow_takes_existing_failure(self, monkeypatch, capsys, _clear_vix_cache):
        import yfinance
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df([1.7e308] * 30))
        out = macro_snapshot.fetch_vix_block()
        # 既有失敗形狀與既有錯誤碼（同「末筆非有限」出口），不帶 inf/nan
        assert out == {'_err_vix': 'not enough data'}, out
        assert _no_non_finite(out)
        assert 'ma20 非有限值' in capsys.readouterr().out

    def test_ma20_negative_overflow(self, monkeypatch, _clear_vix_cache):
        # QA-B：負向溢位（ma20 = -inf）也要擋，不能只查 +inf
        import yfinance
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df([-1.7e308] * 30))
        assert macro_snapshot.fetch_vix_block() == {'_err_vix': 'not enough data'}

    def test_ma20_overflow_short_series(self, monkeypatch, _clear_vix_cache):
        # 不足 20 筆時以全部筆數平均 —— 同樣要擋
        import yfinance
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df([1.0e308] * 5))
        assert macro_snapshot.fetch_vix_block() == {'_err_vix': 'not enough data'}

    def test_failure_not_cached(self, monkeypatch, _clear_vix_cache):
        import yfinance
        state = {'df': _vix_df([1.7e308] * 30)}
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: state['df'])
        assert '_err_vix' in macro_snapshot.fetch_vix_block()
        state['df'] = _vix_df([15.0] * 30)
        assert macro_snapshot.fetch_vix_block()['vix']['ma20'] == 15.0

    def test_large_but_safe_unchanged(self, monkeypatch, _clear_vix_cache):
        import yfinance
        closes = [1.0e306] * 30          # 20 × 1e306 不溢位 → 照常輸出
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df(closes))
        out = macro_snapshot.fetch_vix_block()['vix']
        assert out['ma20'] == round(sum(closes[-20:]) / 20, 1) and _no_non_finite(out)

    def test_finite_unchanged(self, monkeypatch, _clear_vix_cache):
        import yfinance
        closes = [14.0 + 0.37 * i for i in range(40)]
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df(closes))
        out = macro_snapshot.fetch_vix_block()['vix']
        vv = [round(c, 1) for c in closes]
        assert out['ma20'] == round(sum(vv[-20:]) / 20, 1)
        assert out['current'] == vv[-1] and out['values'] == vv[-60:]
