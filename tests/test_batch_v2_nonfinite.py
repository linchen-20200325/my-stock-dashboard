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

    @pytest.mark.parametrize('n', [1, 30])
    def test_all_nan_close_matches_main(self, monkeypatch, _clear_vix_cache, n):
        # QA F1/N1：Close 全 NaN → dropna 後空 → 必須走 main 的 'not enough data'，
        # 不得外洩 KeyError "'Close'"（空布林 list 選 0 欄）。
        import yfinance
        monkeypatch.setattr(yfinance, 'download',
                            lambda *a, **k: _vix_df([math.nan] * n))
        assert macro_snapshot.fetch_vix_block() == {'_err_vix': 'not enough data'}

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
        from shared.vix_validity import vix_value_or_none   # 批 Z17：片段改呼叫 L0 共用判定（模組層 import）
        ns = {'st': type('S', (), {'session_state': {'macro_info': macro_info}})(),
              'vix_value_or_none': vix_value_or_none}
        return _exec_snippet(_HS, "_mi_v4 = st.session_state.get('macro_info')",
                             "except (TypeError, ValueError, OverflowError):   # OverflowError 視同非有限(批 Y2,V2-n8)\n"
                             "                    _v4_vix2 = None\n",   # 批 Y2:except 行多攔 OverflowError
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
                      "                except (TypeError, ValueError, OverflowError):   # OverflowError 視同非有限(批 Y2,V2-n8)\n"
                      "                    pass\n", ns)   # 批 Y2:except 行多攔 OverflowError
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
        # 📌 批 Z3 V2-n1（有意識的更正，⛔ 不是漏刪）：原本此處 `except TypeError: pytest.skip(...)`
        #   ——「非數值 price 在 v4 引擎（L0，本批不動）即拋」。v4 引擎已改為價或年線非有限正實數
        #   ⇒ 依賴價格的鍵回 None、不拋，non-numeric 形狀不再 skip，與其他缺值形狀同一契約。
        out = _warroom_out(bias)
        joined = '\n'.join(out)
        assert '乖離+0.0%' not in joined and '年線乖離 +0.0%' not in joined
        assert out == _warroom_out({}), joined[-800:]

    def test_finite_unchanged(self):
        joined = '\n'.join(_warroom_out(dict(_BIAS_FULL)))
        assert '乖離+25.0%' in joined
        assert '📐 年線位階參考：年線乖離 +25.0%｜乖離過熱' in joined
        assert '🟡 年線乖離 +25.0%，大盤偏高，勿追買' in joined

    # QA 突變殘存（守衛 `_wr_px is not None and _wr_px > 0 and _wr_ma ...` 各子句）：
    # 價格或年線任一不是有限正數 ⇒ 不得印出 v4 位階片段（假「+0.0%」／「-105.0%」）。
    @pytest.mark.parametrize('bias', [
        pytest.param({'price': 20000.0}, id='ma240-missing-only'),
        pytest.param({'price': 20000.0, 'ma240': 0.0}, id='ma240-zero'),
        pytest.param({'price': 0.0, 'ma240': 16000.0}, id='price-zero'),
        pytest.param({'price': -800.0, 'ma240': 16000.0}, id='price-negative'),
    ])
    def test_non_positive_or_missing_px_ma_no_v4_bits(self, bias):
        joined = '\n'.join(_warroom_out(bias))
        assert '年線位階參考' not in joined, joined[-800:]
        assert '年線乖離 +0.0%' not in joined and '-105.0%' not in joined
        assert '股價在年線下' not in joined and '乖離過熱' not in joined

    # QA 突變殘存（年線位置卡 `_wr_b240 is None or …`）：釘住「未知」時的既有圖示 ✅
    # （與 main 的 `not _wr_bias or …` 在 bias_info 為空時同一枝；只釘現況，不改行為）。
    @pytest.mark.parametrize('bias', [
        pytest.param({}, id='empty'),
        pytest.param({'price': 20000.0, 'ma240': 16000.0}, id='bias240-missing'),
        pytest.param({'bias_240': math.nan}, id='bias240-nan'),
    ])
    def test_unknown_card_icon_pinned(self, bias):
        joined = '\n'.join(_warroom_out(bias))
        assert '✅ 年線位置</div>' in joined
        assert '⚠️ 年線位置' not in joined
        assert "line-height:1.25;'>未知</div>" in joined


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

    # QA 突變殘存（`_fam_ok.add('level')` 的 `or`→`and`）：單邊乖離仍算位階群可評估。
    @pytest.mark.parametrize('bias,n', [
        pytest.param({'bias_20': 3.0}, 1, id='bias20-only'),
        pytest.param({'bias_240': 3.0}, 1, id='bias240-only'),
        pytest.param({'bias_20': 3.0, 'bias_240': 3.0}, 1, id='both'),
        pytest.param({}, 0, id='empty'),
    ])
    def test_level_family_evaluable_count(self, bias, n, monkeypatch):
        _, out = _state_out(bias, monkeypatch)
        joined = '\n'.join(out)
        assert f'6 群僅 {n} 群可評估' in joined, joined[-800:]

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


# ── 項 5：D4-n3 資料診斷頁「└」逐筆標註排在所屬分組正下方 ─────────────────────
def _coverage_parts(us10y_close, dxy_close):
    import streamlit as st
    from shared.macro_buckets import CL_INTL_KEY_DXY, CL_INTL_KEY_US10Y
    from src.ui.pages.data_coverage import compute_tab_coverage
    ss = {'macro_info': {'vix': {'current': 17.2}, '_loaded_at': '2026-08-20T01:00'},
          'cl_data': {'intl': {CL_INTL_KEY_US10Y: pd.DataFrame({'close': [us10y_close]}),
                               CL_INTL_KEY_DXY: pd.DataFrame({'close': [dxy_close]})}}}
    for k, v in ss.items():
        st.session_state[k] = v
    try:
        detail = [r for r in compute_tab_coverage() if '總經' in r['tab']][0]['detail']
    finally:
        for k in ss:
            st.session_state.pop(k, None)
    return detail.split(' ｜ ')


def _owner_of_each_tick(parts):
    """每一行「└ key:…」往上找最近的分組標頭 → (key, 標頭)。"""
    out, head = [], None
    for p in parts:
        if p.startswith('　└ '):
            out.append((p[3:].split(':', 1)[0], head))
        else:
            head = p
    return out


class TestCoverageTickLinesUnderOwnGroup:
    @pytest.mark.parametrize('bad', [math.nan, math.inf, -math.inf])
    def test_regrouped_lamp_ticks_under_no_value_group(self, bad):
        parts = _coverage_parts(bad, 500.0)       # us10y 全非有限 → 📵；dxy 有限超範圍 → 📐
        owners = _owner_of_each_tick(parts)
        assert owners, parts
        for key, head in owners:
            assert head is not None and key in head.split(':', 1)[1].split(' → ')[0].split('/'), (key, head)
        assert any(k == 'us10y' and head.startswith('📵 上游無值') for k, head in owners)
        assert any(k == 'dxy' and head.startswith('📐 量綱異常') for k, head in owners)

    def test_text_unchanged_only_position(self):
        parts = _coverage_parts(math.nan, 500.0)
        ticks = sorted(p for p in parts if p.startswith('　└ '))
        assert ticks and all(('= nan 非有限值' in t) or ('= 500.0 out_of_range' in t) for t in ticks), ticks

    def test_finite_out_of_range_only_unchanged(self):
        parts = _coverage_parts(46.3, 100.0)
        i = next(i for i, p in enumerate(parts) if p.startswith('📐 量綱異常(1):us10y'))
        assert parts[i + 1].startswith('　└ us10y:') and '= 46.3 out_of_range' in parts[i + 1]


# ── 項 6：D2-n5 外資連續日數 —— 缺的買／賣額不當 0 ──────────────────────────────
def _fii(rows, mp):
    from unittest.mock import MagicMock
    from src.data.macro import tw_macro as TW
    resp = MagicMock()
    resp.json.return_value = {'data': rows}
    mp.setattr(TW, 'fetch_url', lambda *a, **k: resp)
    TW.fetch_foreign_consecutive_days.cache_clear()
    try:
        return TW.fetch_foreign_consecutive_days(days_back=15)
    finally:
        TW.fetch_foreign_consecutive_days.cache_clear()


def _fii_rows(pairs):
    import datetime as _d
    base = _d.date(2026, 5, 1)
    out = []
    for i, (b, s) in enumerate(pairs):
        r = {'date': (base + _d.timedelta(days=i)).isoformat(), 'name': 'Foreign_Investor'}
        if b is not _ABSENT:
            r['buy'] = b
        if s is not _ABSENT:
            r['sell'] = s
        out.append(r)
    return out


_ABSENT = object()
_SELL = (0, 100)
_BUY = (100, 0)


class TestForeignConsecutiveMissingNotZero:
    @pytest.mark.parametrize('last', [(100, None), (None, 100), (None, None), (100, 'x'),
                                      (math.inf, 0), (100, _ABSENT)])
    def test_latest_day_missing_gives_no_streak(self, last, monkeypatch):
        r = _fii(_fii_rows([_SELL] * 6 + [last]), monkeypatch)
        assert r['consec_days'] is None and r['today_net'] is None
        assert r['inflection'] == '⬜ 資料不足'           # 既有缺值路徑
        assert r['error'] is None

    def test_missing_sell_not_counted_as_full_buy(self, monkeypatch):
        # 舊：缺「賣」→ 淨額 = +100 → 「🚀 連6賣→買（拐點）」假訊號
        r = _fii(_fii_rows([_SELL] * 6 + [(100, None)]), monkeypatch)
        assert '賣→買' not in r['inflection']

    def test_interior_missing_breaks_streak_like_before(self, monkeypatch):
        r = _fii(_fii_rows([_SELL] * 3 + [(None, None)] + [_SELL] * 2), monkeypatch)
        assert r['consec_days'] == -2 and r['prev_streak'] == 0

    def test_missing_columns_do_not_crash(self, monkeypatch):
        r = _fii(_fii_rows([(_ABSENT, _ABSENT)] * 3), monkeypatch)
        assert r['consec_days'] is None and r['inflection'] == '⬜ 資料不足'

    def test_finite_unchanged(self, monkeypatch):
        r = _fii(_fii_rows([_SELL] * 6 + [_BUY]), monkeypatch)
        assert (r['consec_days'], r['prev_streak'], r['today_net']) == (1, -6, 100)
        assert r['inflection'] == '🚀 連6賣→買（拐點）'
        r = _fii(_fii_rows([_BUY] * 5), monkeypatch)
        assert r['inflection'] == '🟢 連5日買超' and r['today_net'] == 100
        r = _fii(_fii_rows([_BUY, (50, 50)]), monkeypatch)    # 真 0 仍是 0
        assert r['consec_days'] == 0 and r['today_net'] == 0 and r['inflection'] == '📊 震盪'


# ── 項 7：D1-n2 save_portfolio —— NaN／±inf 張數或均價在任何寫入之前 fail loud ─────
class TestSavePortfolioNonFinite:
    def _ws(self):
        from tests.test_gsheet_portfolio import _FakeWorksheet, _mixed_sheet
        return _FakeWorksheet([list(r) for r in _mixed_sheet()], row_count=5, col_count=5)

    @pytest.mark.parametrize('field', ['lots', 'avg_price'])
    @pytest.mark.parametrize('bad', [math.nan, math.inf, -math.inf, 'nan', 'inf'])
    def test_raises_before_any_write(self, field, bad):
        from unittest.mock import patch
        import src.data.portfolio.gsheet_portfolio as gsp
        ws = self._ws()
        snap = ws.get_all_values()
        row = {'ticker': 'VOO', 'lots': 1, 'avg_price': 400.0}
        row[field] = bad
        with patch.object(gsp, '_ws', return_value=ws):
            with pytest.raises(ValueError, match='有張數或均價空白／無效的列，Sheet 維持原狀（檢查張數、均價）'):
                gsp.save_portfolio('A', [{'ticker': 'QQQ', 'lots': 2, 'avg_price': 300.0}, row])
        assert ws.calls == [] and ws.get_all_values() == snap
        assert ws.row_count == 5 and ws.col_count == 5         # 連 add_rows／add_cols 都沒碰

    def test_finite_unchanged(self):
        from unittest.mock import patch
        import src.data.portfolio.gsheet_portfolio as gsp
        ws = self._ws()
        with patch.object(gsp, '_ws', return_value=ws):
            n = gsp.save_portfolio('A', [{'ticker': 'voo', 'lots': 0.1, 'avg_price': 400.0},
                                         {'ticker': 'x', 'lots': 0, 'avg_price': 1},
                                         {'ticker': 'y', 'lots': 'abc', 'avg_price': 1}])
        assert n == 1 and [c[0] for c in ws.calls][-1] == 'update'


# ── 項 8：D2-n1（純測試）季報「第一次」確定失敗必須回報 failed=True ────────────────
class TestQuarterlyFirstFreshFailureFlag:
    def test_first_fresh_failure_reports_true(self, monkeypatch):
        import src.data.stock.quarterly_financials_fetcher as QF
        payload = [{'label': '2026Q1', 'revenue': 1.0}]

        def _boom(stock_id, quarters=12):
            raise QF._QuarterlyFetchFailed(payload, 'TaiwanStockBalanceSheet:ConnectionError')

        QF.fetch_quarterly_shortage_frame.clear()
        monkeypatch.setattr(QF, '_fetch_quarterly_shortage_frame_cached', _boom)
        try:
            out, failed = QF._fetch_quarterly_shortage_frame_with_status('9999', 12)
            # 存活突變（第一次新失敗那一行 `, True` → `, False`）會讓 L3 把半套結果寫進快取
            assert failed is True
            assert out == payload
            out2, failed2 = QF._fetch_quarterly_shortage_frame_with_status('9999', 12)
            assert failed2 is True and out2 == payload            # 冷卻期內：同一份、仍是失敗
        finally:
            QF._qtr_fail_cooldown.clear()

    def test_success_reports_false(self, monkeypatch):
        import src.data.stock.quarterly_financials_fetcher as QF
        QF.fetch_quarterly_shortage_frame.clear()
        monkeypatch.setattr(QF, '_fetch_quarterly_shortage_frame_cached',
                            lambda stock_id, quarters=12: [{'label': '2026Q1'}])
        try:
            assert QF._fetch_quarterly_shortage_frame_with_status('9998', 12) == (
                [{'label': '2026Q1'}], False)
        finally:
            QF._qtr_fail_cooldown.clear()
