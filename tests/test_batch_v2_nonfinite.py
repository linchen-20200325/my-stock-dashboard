"""批 V2：HANDOFF 優先 3 —— 非有限值 / 缺值捏 0 / 失敗快取（三類資料層授權）收尾。

只擋資料、不加新字句、不動門檻、不動版面。每段測試都附「拔掉修復即轉紅」的反向斷言
（以 monkeypatch / 原始碼字面守衛實作），有限 / 正常輸入行為與 main 相同。
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from src.data.macro import macro_snapshot


# ── 項 1：VIX L1 fetch_vix_block + L3 allocation_service._safe_float ──────────
@pytest.fixture
def _clear_vix_cache():
    if hasattr(macro_snapshot.fetch_vix_block, 'clear'):
        macro_snapshot.fetch_vix_block.clear()
    yield
    if hasattr(macro_snapshot.fetch_vix_block, 'clear'):
        macro_snapshot.fetch_vix_block.clear()


def _vix_df(closes):
    idx = pd.date_range('2026-04-01', periods=len(closes), freq='D')
    return pd.DataFrame({'Close': closes}, index=idx)


class TestFetchVixBlockNonFinite:
    @pytest.mark.parametrize('bad', [math.inf, -math.inf])
    def test_last_non_finite_goes_to_existing_failure(self, monkeypatch, _clear_vix_cache, bad):
        import yfinance
        monkeypatch.setattr(yfinance, 'download',
                            lambda *a, **k: _vix_df([15.0] * 29 + [bad]))
        out = macro_snapshot.fetch_vix_block()
        assert out == {'_err_vix': 'not enough data'}   # 既有失敗出口，非新字串

    @pytest.mark.parametrize('bad', [math.inf, -math.inf, math.nan])
    def test_interior_non_finite_dropped_like_nan(self, monkeypatch, _clear_vix_cache, bad):
        import yfinance
        closes = [15.0] * 10 + [bad] + [16.0] * 19
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df(closes))
        out = macro_snapshot.fetch_vix_block()['vix']
        assert all(math.isfinite(v) for v in out['values'])
        assert math.isfinite(out['ma20']) and out['current'] == 16.0
        assert len(out['values']) == 29 and len(out['dates']) == 29

    def test_finite_unchanged(self, monkeypatch, _clear_vix_cache):
        import yfinance
        closes = [15.0 + i * 0.1 for i in range(30)]
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df(closes))
        out = macro_snapshot.fetch_vix_block()['vix']
        vv = [round(v, 1) for v in closes]
        assert out['values'] == vv
        assert out['current'] == vv[-1]
        assert out['ma20'] == round(sum(vv[-20:]) / 20, 1)

    def test_failure_not_cached(self, monkeypatch, _clear_vix_cache):
        import yfinance
        monkeypatch.setattr(yfinance, 'download',
                            lambda *a, **k: _vix_df([15.0] * 29 + [math.inf]))
        assert '_err_vix' in macro_snapshot.fetch_vix_block()
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df([15.0] * 30))
        assert macro_snapshot.fetch_vix_block()['vix']['current'] == 15.0


class TestAllocationSafeFloat:
    @pytest.mark.parametrize('bad', [math.inf, -math.inf, math.nan, 'x', None])
    def test_non_finite_is_none(self, bad):
        from src.services.allocation_service import _safe_float
        assert _safe_float(bad) is None

    @pytest.mark.parametrize('ok', [0, 12.5, -3, '18.2'])
    def test_finite_passes(self, ok):
        from src.services.allocation_service import _safe_float
        assert _safe_float(ok) == float(ok)

    @pytest.mark.parametrize('bad', [math.inf, -math.inf])
    def test_read_vix_non_finite_is_unknown(self, bad):
        import streamlit as st
        from src.services import allocation_service as al
        st.session_state['macro_info'] = {'vix': {'current': bad}}
        try:
            assert al._read_vix() is None
            # +inf 不再觸發「VIX inf ≥ 30」天花板；與 VIX=None 結果一致
            from shared.allocation_decision import vix_veto_cap
            assert vix_veto_cap(al._read_vix()) == vix_veto_cap(None)
        finally:
            st.session_state.pop('macro_info', None)
