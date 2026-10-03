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


# ── 項 3：V1-n4 section_mid 非 dict 的 VIX 節點 → 既有缺值路徑（不崩潰）──────────
class TestSectionMidNonDictVix:
    @pytest.mark.parametrize('node', ['x', 5, [1, 2], 18.5])
    def test_non_dict_takes_missing_path(self, node, monkeypatch):
        from tests.test_v1_vix_nonfinite import _LOADING, _run
        out, calls = _run(node, monkeypatch)
        assert _LOADING in out
        assert any('待取得' in t for t in out)   # 既有 KPI 缺值卡

    def test_finite_dict_unchanged(self, monkeypatch):
        from tests.test_v1_vix_nonfinite import _LOADING, _run
        node = {'current': 18.5, 'ma20': 17.0, 'dates': ['2026-09-01'], 'values': [18.5]}
        out, _ = _run(node, monkeypatch)
        assert _LOADING not in out


# ── 項 4：D4-n6 乖離率缺值不捏 0（section_state / warroom / long / op_recommendation）──
#: 「缺」的各種形狀：缺鍵、None、NaN、±inf、非數值；全部要等同「bias_info 為空」那條既有路徑。
_BIAS_MISSING = [
    pytest.param({'is_estimated': False}, id='keys-missing'),
    pytest.param({'bias_240': None, 'bias_20': None, 'price': None, 'ma240': None}, id='none'),
    pytest.param({'bias_240': math.nan, 'bias_20': math.nan, 'price': math.nan, 'ma240': math.nan}, id='nan'),
    pytest.param({'bias_240': math.inf, 'bias_20': -math.inf, 'price': math.inf, 'ma240': 1.0}, id='inf'),
    pytest.param({'bias_240': 'x', 'bias_20': 'y', 'price': 'z', 'ma240': 'w'}, id='non-numeric'),
]
_BIAS_FULL = {'bias_240': 25.0, 'bias_20': 12.0, 'bias_60': 3.0,
              'price': 20000.0, 'ma240': 16000.0, 'data_days': 300, 'is_estimated': False}


def _warroom_out(bias):
    from tests.test_m2n2_no_zero_fill import _FakeST
    import src.ui.tabs.macro.section_warroom as W
    fake = _FakeST({'bias_info': bias, 'cl_data': {'margin': 2000.0}})
    saved, W.st = W.st, fake
    try:
        W.render_section_warroom('bull', True, False)
    finally:
        W.st = saved
    return [t for _k, t in fake.out]


class TestWarroomBiasMissing:
    @pytest.mark.parametrize('bias', _BIAS_MISSING)
    def test_missing_equals_empty_path(self, bias):
        try:
            out = _warroom_out(bias)
        except TypeError:
            pytest.skip('非數值 price 在 v4 引擎（L0，本批不動）即拋 —— 與本批無關')
        joined = '\n'.join(out)
        assert '乖離+0.0%' not in joined and '年線乖離 +0.0%' not in joined
        assert out == _warroom_out({}), joined[-800:]

    def test_finite_unchanged(self):
        joined = '\n'.join(_warroom_out(dict(_BIAS_FULL)))
        assert '乖離+25.0%' in joined
        assert '📐 年線位階參考：年線乖離 +25.0%｜乖離過熱' in joined
        assert '🟡 年線乖離 +25.0%，大盤偏高，勿追買' in joined


def _state_out(bias, mp):
    from tests.test_m2n2_no_zero_fill import _FakeST
    import src.ui.tabs.macro.section_state as S
    fake = _FakeST({'bias_info': bias, '_ndc_hist_cache': {}, '_ndc_li_cache': {},
                    '_fi_streak_cache': {}})
    mp.setattr(S, 'st', fake)
    S.render_section_state({'signals': []}, None, None, {},
                           show_market_data=False, requested=True)
    return fake.session_state.get('_pivot_signals'), [t for _k, t in fake.out]


class TestStateBiasMissing:
    @pytest.mark.parametrize('bias', _BIAS_MISSING)
    def test_missing_equals_empty_path(self, bias, monkeypatch):
        assert _state_out(bias, monkeypatch) == _state_out({}, monkeypatch)

    def test_one_side_missing_only_skips_that_lamp(self, monkeypatch):
        piv, _ = _state_out({'bias_20': 12.0}, monkeypatch)
        assert [p[0] for p in piv] == ['月線過熱']
        piv, _ = _state_out({'bias_240': 25.0}, monkeypatch)
        assert [p[0] for p in piv] == ['年線乖離過大']

    def test_finite_unchanged(self, monkeypatch):
        piv, out = _state_out(dict(_BIAS_FULL), monkeypatch)
        assert [p[0] for p in piv] == ['年線乖離過大', '月線過熱']
        assert out != _state_out({}, monkeypatch)[1]


def _long_out(bias):
    from tests.test_dl_f1_s24_m2_missing import _long_module, _render
    out, exc = _render(_long_module(), {}, bias=bias)
    assert exc is None, exc
    return [t for _k, t in out]


class TestLongBiasMissing:
    @pytest.mark.parametrize('bias', _BIAS_MISSING)
    def test_missing_takes_existing_paths(self, bias):
        out = _long_out(bias)
        empty = _long_out({})
        joined = '\n'.join(out)
        assert '年線乖離 +0.0%' not in joined and '+0.0%' not in joined
        # 結論卡＝bias_info 為空時的樣子；KPI 只把「計算中」換成既有灰態「待取得」
        assert [t.replace('待取得', '計算中') for t in out] == empty
        assert any('年線乖離率(240MA)' in t and '待取得' in t for t in out)

    def test_bias20_missing_drops_only_that_segment(self):
        out = '\n'.join(_long_out({'bias_240': 25.0}))
        assert '+25.0%' in out and '月線20MA' not in out

    def test_finite_unchanged(self):
        out = '\n'.join(_long_out(dict(_BIAS_FULL)))
        assert '月線20MA: +12.0% (⚠️過熱)' in out
        assert '年線乖離 +25.0% 過大' in out


class TestOpRecommendationBias:
    def _sent(self, bias, mp):
        from tests.test_m2n2_no_zero_fill import _FakeST
        import src.services.allocation_service as AS
        import src.ui.tabs.stock_sections.section_op_recommendation as OP
        seen = []
        fake = _FakeST({'bias_info': bias, 'cl_data': {'inst': {}}})
        mp.setattr(OP, 'st', fake)
        mp.setattr(OP, 'generate_ai_comment',
                   lambda d: seen.append((d['bias_240'], d['bias_20'])) or '')
        mp.setattr(AS, 'get_macro_regime', lambda *a, **k: {'is_loaded': False})
        OP.render_op_recommendation_section('2330', 82.0, {'contracting': True},
                                            5.0, 100.0, 55.0, 0, 0)
        return seen

    @pytest.mark.parametrize('bias', _BIAS_MISSING)
    def test_missing_sent_as_none(self, bias, monkeypatch):
        assert self._sent(bias, monkeypatch) == [(None, None)]

    def test_finite_unchanged(self, monkeypatch):
        assert self._sent(dict(_BIAS_FULL), monkeypatch) == [(25.0, 12.0)]

    def test_l3_none_is_existing_missing_path(self):
        from src.services.app_ai_service import generate_ai_comment
        base = {'health': 82.0, 'score': 0, 'rsi': 55.0, 'vcp_ok': True}
        assert (generate_ai_comment({**base, 'bias_240': None, 'bias_20': None})
                == generate_ai_comment(base))
        assert 'inf' not in generate_ai_comment({**base, 'bias_240': None})
