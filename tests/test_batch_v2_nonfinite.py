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


# ── 共用：從原始碼抽出一段「實際上線的程式碼」來執行（拔修復 → 這裡跟著變紅）──────
def _exec_snippet(path, start, end, ns):
    import textwrap
    src = open(path, encoding='utf-8').read()
    i = src.index(start)
    j = src.index(end, i) + len(end)
    line0 = src.rfind('\n', 0, i) + 1
    code = textwrap.dedent(src[line0:j])
    ns.setdefault('math', math)
    exec(compile(code, path, 'exec'), ns)
    return ns


# ── 項 2：V1-n3 L5 VIX 讀取點 ±inf → 既有缺值路徑 ──────────────────────────────
class TestReadV4MacroVeto:
    @pytest.mark.parametrize('bad', [math.inf, -math.inf, math.nan])
    def test_non_finite_is_none(self, bad):
        import streamlit as st
        from src.ui.tabs.macro.section_chips import read_v4_macro_veto
        st.session_state['macro_info'] = {'vix': {'current': bad}}
        try:
            assert read_v4_macro_veto() is None
        finally:
            st.session_state.pop('macro_info', None)

    def test_finite_unchanged(self):
        import streamlit as st
        from src.ui.tabs.macro.section_chips import read_v4_macro_veto
        st.session_state['macro_info'] = {'vix': {'current': 18.5}}
        st.session_state.pop('li_latest', None)
        try:
            out = read_v4_macro_veto()
            assert out is not None and out['_vix'] == 18.5
        finally:
            st.session_state.pop('macro_info', None)


_HS = 'src/ui/tabs/stock_sections/section_health_score.py'


class TestHealthScoreV4Vix:
    def _run(self, macro_info):
        ns = {'st': type('S', (), {'session_state': {'macro_info': macro_info}})()}
        return _exec_snippet(_HS, "_mi_v4 = st.session_state.get('macro_info')",
                             "except (TypeError, ValueError):\n                    _v4_vix2 = None\n",
                             ns)['_v4_vix2']

    @pytest.mark.parametrize('bad', [math.inf, -math.inf, math.nan, 'x', None])
    def test_non_finite_is_none(self, bad):
        assert self._run({'vix': {'current': bad}}) is None

    def test_finite_unchanged(self):
        assert self._run({'vix': {'current': 21.3}}) == 21.3

    def test_non_dict_is_none(self):
        assert self._run({'vix': 5}) is None


_TS = 'src/ui/tabs/tab_stock.py'


class TestTabStockAiPromptVix:
    def _run(self, cur):
        ns = {'_macro_info2': {'vix': {'current': cur}}, '_ma_snap2': {},
              '_drt2': lambda k: 'D', '_macro_lines2': []}
        _exec_snippet(_TS, "_vix_v2 = (_macro_info2.get('vix') or {})",
                      "                except (TypeError, ValueError):\n                    pass\n", ns)
        return ns['_macro_lines2']

    @pytest.mark.parametrize('bad', [math.inf, -math.inf, math.nan])
    def test_non_finite_line_omitted(self, bad):
        assert self._run(bad) == []          # 同缺值：不列該行

    def test_missing_line_omitted(self):
        assert self._run(None) == []

    def test_finite_unchanged(self):
        assert self._run(19.234) == ['VIX 恐慌指數=19.23（D）']
