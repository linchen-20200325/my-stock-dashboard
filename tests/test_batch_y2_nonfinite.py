"""批 Y2：HANDOFF 優先 3 —— 三類資料層授權 (b) 缺值不填 0、(c) 擋非有限值。

- V2-n2：`compute_twii_bias` 的 `calc_bias_pct(...) or 0` 把算不出的乖離捏成 0
- V2-n3：`fetch_fed_funds_block` 末筆非有限值不再放行（比照同檔 us10y／vix）
- V2-n6：`fetch_vix_block` 中段剔除非有限值補 log 筆數（輸出不變）
- V2-n8／X2-n2：有限值 helper 漏攔 OverflowError（`float(10**400)`）

只擋資料、不加新字句（log 除外）、不動門檻、不動版面；有限 / 正常輸入與 main 相同。
每段都有「拔掉修復即轉紅」的斷言（在 main `88d562a` 上會失敗）。
"""
from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from src.data.macro import macro_snapshot

_HUGE = 10 ** 400   # float() → OverflowError（不是 inf）


# ── V2-n2：compute_twii_bias 缺值不填 0 ─────────────────────────────────────────
def _twii(closes):
    idx = pd.date_range('2025-01-01', periods=len(closes), freq='D')
    return pd.DataFrame({'Close': closes}, index=idx)


class TestTwiiBiasMissingNotZero:
    def test_ma_non_positive_is_none_not_zero(self):
        # MA240 ≤ 0 → calc_bias_pct 回 None（算不出）；修前 `or 0` 捏成 0（＝「乖離正常」）
        closes = [-1000.0] * 220 + [100.0] * 20
        out = macro_snapshot.compute_twii_bias(_twii(closes))
        assert out['bias_240'] is None
        assert out['bias_60'] is None                 # MA60 = (-40000+2000)/60 < 0
        # 同一份資料裡真 0.0（price == MA20）照樣是 0.0，不被當缺
        assert out['bias_20'] == 0.0 and isinstance(out['bias_20'], float)

    def test_all_zero_close_all_none(self):
        out = macro_snapshot.compute_twii_bias(_twii([0.0] * 240))
        assert (out['bias_20'], out['bias_60'], out['bias_240']) == (None, None, None)
        # 其餘欄位與修前相同
        assert out['price'] == 0.0 and out['data_days'] == 240 and out['is_estimated'] is False

    def test_genuine_zero_stays_zero(self):
        out = macro_snapshot.compute_twii_bias(_twii([100.0] * 240))
        for k in ('bias_20', 'bias_60', 'bias_240'):
            assert out[k] == 0.0 and out[k] is not None

    def test_negative_zero_normalised(self, capsys):
        # QA-A:乖離 round 到 -0.0 時,修前 `-0.0 or 0` 收斂成 0;必須維持 +0.0,
        #   否則五桶 / KPI / AI prompt / log 印「-0.0%」。
        from src.compute.macro.macro_helpers import compute_five_bucket_summary
        out = macro_snapshot.compute_twii_bias(_twii([100.0] * 239 + [99.97]))
        for k in ('bias_20', 'bias_60', 'bias_240'):
            v = out[k]
            assert v == 0.0 and isinstance(v, float) and math.copysign(1, v) == 1, (k, v)
            assert f'{v:+.1f}%' == '+0.0%'
        assert 'bias240=0.0% (n=240)' in capsys.readouterr().out
        summ = compute_five_bucket_summary(bias_info=out)
        rows = [d for b in summ.values() if isinstance(b, dict)
                for d in (b.get('details') or []) if d.get('key') == 'bias_240']
        assert rows and rows[0]['value_str'] == '0.0%'

    def test_finite_unchanged(self):
        closes = [15000.0 + 7.3 * i + (i % 11) * 13.1 for i in range(260)]
        out = macro_snapshot.compute_twii_bias(_twii(closes))
        s = pd.Series(closes)
        lp = float(s.iloc[-1])

        def _b(n):
            ma = float(s.tail(n).mean())
            return round((lp - ma) / ma * 100.0, 1)
        assert out['bias_20'] == _b(20)
        assert out['bias_60'] == _b(60)
        assert out['bias_240'] == _b(240)
        assert out['data_days'] == 260 and out['is_estimated'] is False

    def test_log_line_survives_none(self, capsys):
        # 修前 log 用 `{_b240_log:.1f}`；None 時必須不炸、仍印一行
        macro_snapshot.compute_twii_bias(_twii([0.0] * 240))
        assert 'bias240=None' in capsys.readouterr().out

    def test_log_line_genuine_zero(self, capsys):
        macro_snapshot.compute_twii_bias(_twii([100.0] * 240))
        assert 'bias240=0.0% (n=240)' in capsys.readouterr().out

    def test_log_line_finite_unchanged(self, capsys):
        macro_snapshot.compute_twii_bias(_twii([100.0] * 239 + [110.0]))
        assert 'bias240=10.0% (n=240)' in capsys.readouterr().out

    def test_five_bucket_shows_missing_not_zero(self):
        # 下游：五桶明細拿到 None → 既有「—」，不再印「0.0%」
        from src.compute.macro.macro_helpers import compute_five_bucket_summary
        bi = macro_snapshot.compute_twii_bias(_twii([0.0] * 240))
        summ = compute_five_bucket_summary(bias_info=bi)
        rows = [d for b in summ.values() if isinstance(b, dict)
                for d in (b.get('details') or []) if d.get('key') == 'bias_240']
        assert rows and rows[0]['value_str'] == '—'


# ── V2-n3：fetch_fed_funds_block 擋非有限值 ─────────────────────────────────────
class _Resp:
    def __init__(self, *, text=None, js=None):
        self.status_code = 200
        self._js = js
        self.content = (text or '').encode('utf-8')

    def json(self):
        return self._js


def _fred_csv(vals):
    lines = ['observation_date,FEDFUNDS']
    lines += [f'2026-{i + 1:02d}-01,{v}' for i, v in enumerate(vals)]
    return '\n'.join(lines) + '\n'


def _fred_api(vals):
    return {'observations': [{'date': f'2026-{i + 1:02d}-01', 'value': v}
                             for i, v in enumerate(vals)]}


@pytest.fixture
def _ff(monkeypatch):
    import src.data.proxy.proxy_helper as _ph
    macro_snapshot.fetch_fed_funds_block.clear()
    state = {}

    def _fake(url, *a, **k):
        if 'fredgraph' in url:
            return state.get('csv')
        return state.get('api')
    monkeypatch.setattr(_ph, 'fetch_url', _fake)
    yield state
    macro_snapshot.fetch_fed_funds_block.clear()


class TestFedFundsNonFinite:
    @pytest.mark.parametrize('bad', ['inf', '-inf'])
    def test_fredgraph_last_non_finite_falls_to_api(self, _ff, bad):
        _ff['csv'] = _Resp(text=_fred_csv(['4.33', bad]))
        _ff['api'] = _Resp(js=_fred_api(['4.33', '4.08']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out['fed_funds']['source'] == 'FRED-API'
        assert out['fed_funds']['current'] == 4.08 and out['fed_funds']['prev'] == 4.33

    @pytest.mark.parametrize('bad', ['inf', '-inf', 'NaN', 'nan'])
    def test_both_tiers_non_finite_existing_failure_exit(self, _ff, bad):
        _ff['csv'] = _Resp(text=_fred_csv(['4.33', 'inf']))
        _ff['api'] = _Resp(js=_fred_api(['4.33', bad]))
        out = macro_snapshot.fetch_fed_funds_block()
        # 既有失敗出口、既有字串（fredgraph 走 us10y 同款 rows<2；FRED-API 沉默落空同修前）
        assert out == {'_err_fed_funds': 'fredgraph:rows<2(2)'}

    @pytest.mark.parametrize('bad', ['inf', '-inf'])
    @pytest.mark.parametrize('head', [['5.0', '4.5'], ['5.33', '5.0', '4.75', '4.5']],
                             ids=['3rows', '5rows'])
    def test_fredgraph_long_csv_last_non_finite_no_prev_as_current(self, _ff, head, bad):
        # QA M32:守衛若只砍掉末筆(`iloc[:-1]`)而非清空,≥3 列時會把上月 4.5 當成
        #   current、掛在最新日期下。必須整段走既有失敗出口,4.5 不得出現。
        #   (NaN 不適用:fredgraph 先 `dropna()`,NaN 列本來就被剔除,屬既有行為。)
        rows = head + [bad]
        _ff['csv'] = _Resp(text=_fred_csv(rows))
        _ff['api'] = None
        out = macro_snapshot.fetch_fed_funds_block()
        assert out == {'_err_fed_funds': f'fredgraph:rows<2({len(rows)})'}
        assert (out.get('fed_funds') or {}).get('current') is None
        assert '4.5' not in repr(out)

    def test_failure_not_cached(self, _ff):
        _ff['csv'] = _Resp(text=_fred_csv(['4.33', 'inf']))
        _ff['api'] = None
        assert '_err_fed_funds' in macro_snapshot.fetch_fed_funds_block()
        _ff['csv'] = _Resp(text=_fred_csv(['4.33', '4.08']))
        assert macro_snapshot.fetch_fed_funds_block()['fed_funds']['current'] == 4.08

    def test_fredgraph_finite_unchanged(self, _ff):
        _ff['csv'] = _Resp(text=_fred_csv(['5.33', '4.333', '4.087']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out == {'fed_funds': {'current': 4.09, 'prev': 4.33, 'date': '2026-03-01',
                                     'source': 'FRED/fredgraph.csv', 'series_id': 'FEDFUNDS'}}

    def test_api_finite_unchanged(self, _ff):
        _ff['csv'] = None
        _ff['api'] = _Resp(js=_fred_api(['5.33', '.', '4.333', '4.087']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out == {'fed_funds': {'current': 4.09, 'prev': 4.33, 'date': '2026-04-01',
                                     'source': 'FRED-API', 'series_id': 'FEDFUNDS'}}

    def test_api_too_few_rows_unchanged(self, _ff):
        _ff['csv'] = None
        _ff['api'] = _Resp(js=_fred_api(['4.087']))
        assert macro_snapshot.fetch_fed_funds_block() == {
            '_err_fed_funds': 'fredgraph:HTTPNone'}

    # ── 批 Z1（Y2-n1）：前一筆（prev，[-2]）非有限值同樣不放行 ──
    # fredgraph 的 NaN 列先被既有 `dropna()` 剔除（列數 2→1，走既有 rows<2）；±inf 才會碰到新守衛。
    @staticmethod
    def _fredgraph_rows_after_dropna(bad):
        return 1 if bad.lower() == 'nan' else 2

    _LOG_FG_PREV = '[Macro/FedFunds/fredgraph] ⚠️ 前一筆非有限值'
    _LOG_API_PREV = '[Macro/FedFunds/FRED-API] ⚠️ 前一筆非有限值'

    @pytest.mark.parametrize('bad', ['inf', '-inf', 'nan'])
    def test_fredgraph_prev_non_finite_falls_to_api(self, _ff, capsys, bad):
        _ff['csv'] = _Resp(text=_fred_csv([bad, '4.08']))
        _ff['api'] = _Resp(js=_fred_api(['4.33', '4.08']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out['fed_funds']['source'] == 'FRED-API'
        assert out['fed_funds']['current'] == 4.08 and out['fed_funds']['prev'] == 4.33
        log = capsys.readouterr().out
        # NaN 列先被 dropna 剔除、不經新守衛 → 不印；±inf 才印
        assert (self._LOG_FG_PREV in log) is (bad.lower() != 'nan')
        assert self._LOG_API_PREV not in log

    @pytest.mark.parametrize('bad', ['inf', '-inf', 'nan'])
    def test_both_tiers_prev_non_finite_existing_failure_exit(self, _ff, capsys, bad):
        _ff['csv'] = _Resp(text=_fred_csv([bad, '4.08']))
        _ff['api'] = _Resp(js=_fred_api([bad, '4.08']))
        out = macro_snapshot.fetch_fed_funds_block()
        n = self._fredgraph_rows_after_dropna(bad)
        assert out == {'_err_fed_funds': f'fredgraph:rows<2({n})'}
        assert 'prev' not in repr(out)
        log = capsys.readouterr().out
        assert (self._LOG_FG_PREV in log) is (bad.lower() != 'nan')
        assert self._LOG_API_PREV in log

    # QA 追加：≥3 列，區分 [-2] 與 [0]、「整段清空」與「只剔除壞列／濾掉非有限值」
    @pytest.mark.parametrize('bad', ['inf', '-inf'])
    def test_fredgraph_3rows_bad_prev_whole_tier_rejected(self, _ff, bad):
        _ff['csv'] = _Resp(text=_fred_csv(['5.33', bad, '4.08']))
        _ff['api'] = _Resp(js=_fred_api(['4.33', '4.08']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out['fed_funds']['source'] == 'FRED-API'
        assert out['fed_funds']['current'] == 4.08 and out['fed_funds']['prev'] == 4.33
        assert '5.33' not in repr(out)

    @pytest.mark.parametrize('bad', ['inf', '-inf'])
    def test_fredgraph_older_non_finite_not_rejected(self, _ff, bad):
        _ff['csv'] = _Resp(text=_fred_csv([bad, '4.33', '4.08']))
        _ff['api'] = None
        out = macro_snapshot.fetch_fed_funds_block()
        assert out['fed_funds']['source'] == 'FRED/fredgraph.csv'
        assert out['fed_funds']['current'] == 4.08 and out['fed_funds']['prev'] == 4.33

    @pytest.mark.parametrize('bad', ['inf', '-inf', 'nan'])
    def test_api_3rows_bad_prev_existing_failure_exit(self, _ff, bad):
        _ff['csv'] = None
        _ff['api'] = _Resp(js=_fred_api(['5.33', bad, '4.08']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out == {'_err_fed_funds': 'fredgraph:HTTPNone'}

    @pytest.mark.parametrize('bad', ['inf', '-inf', 'nan'])
    def test_api_older_non_finite_not_rejected(self, _ff, bad):
        _ff['csv'] = None
        _ff['api'] = _Resp(js=_fred_api([bad, '4.33', '4.08']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out['fed_funds']['source'] == 'FRED-API'
        assert out['fed_funds']['current'] == 4.08 and out['fed_funds']['prev'] == 4.33

    def test_finite_no_prev_guard_log(self, _ff, capsys):
        """QA N4/N6：值皆有限時，兩道 prev 守衛的 log 都不得出現。"""
        _ff['csv'] = _Resp(text=_fred_csv(['5.33', '4.333', '4.087']))
        assert macro_snapshot.fetch_fed_funds_block()['fed_funds']['source'] == 'FRED/fredgraph.csv'
        _ff['csv'] = None
        _ff['api'] = _Resp(js=_fred_api(['5.33', '4.333', '4.087']))
        macro_snapshot.fetch_fed_funds_block.clear()
        assert macro_snapshot.fetch_fed_funds_block()['fed_funds']['source'] == 'FRED-API'
        log = capsys.readouterr().out
        assert self._LOG_FG_PREV not in log and self._LOG_API_PREV not in log

    @pytest.mark.parametrize('bad', ['inf', '-inf', 'nan'])
    def test_prev_non_finite_failure_not_cached(self, _ff, bad):
        _ff['csv'] = _Resp(text=_fred_csv([bad, '4.08']))
        _ff['api'] = _Resp(js=_fred_api([bad, '4.08']))
        assert '_err_fed_funds' in macro_snapshot.fetch_fed_funds_block()
        _ff['csv'] = _Resp(text=_fred_csv(['4.33', '4.08']))
        out = macro_snapshot.fetch_fed_funds_block()
        assert out['fed_funds']['current'] == 4.08 and out['fed_funds']['prev'] == 4.33


# ── V2-n6：fetch_vix_block 中段剔除補 log ───────────────────────────────────────
@pytest.fixture
def _clear_vix_cache():
    macro_snapshot.fetch_vix_block.clear()
    yield
    macro_snapshot.fetch_vix_block.clear()


def _vix_df(closes):
    idx = pd.date_range('2026-04-01', periods=len(closes), freq='D')
    return pd.DataFrame({'Close': closes}, index=idx)


class TestVixInteriorDropLogged:
    def test_count_logged_output_unchanged(self, monkeypatch, capsys, _clear_vix_cache):
        import yfinance
        closes = [15.0] * 5 + [math.inf] + [15.5] * 5 + [-math.inf, math.inf] + [16.0] * 17
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df(closes))
        out = macro_snapshot.fetch_vix_block()['vix']
        assert '[Macro/VIX] ⚠️ 剔除中段非有限/非數值 Close 3 筆' in capsys.readouterr().out
        # 輸出與修前相同（剔除 3 筆後 27 筆）
        kept = [c for c in closes if math.isfinite(c)]
        assert out['values'] == [round(v, 1) for v in kept]
        assert out['ma20'] == round(sum(kept[-20:]) / 20, 1) and out['current'] == 16.0

    def test_no_drop_no_log(self, monkeypatch, capsys, _clear_vix_cache):
        import yfinance
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: _vix_df([15.0] * 30))
        macro_snapshot.fetch_vix_block()
        assert '剔除中段' not in capsys.readouterr().out


# ── V2-n8／X2-n2：OverflowError 視同非有限 ─────────────────────────────────────
class TestOverflowHelpers:
    def test_allocation_safe_float(self):
        from src.services.allocation_service import _safe_float
        assert _safe_float(_HUGE) is None and _safe_float(-_HUGE) is None
        assert _safe_float(10 ** 300) == float(10 ** 300)     # 大但可表示 → 照舊

    def test_allocation_read_vix(self):
        import streamlit as st
        from src.services import allocation_service as al
        st.session_state['macro_info'] = {'vix': {'current': _HUGE}}
        try:
            assert al._read_vix() is None
        finally:
            st.session_state.pop('macro_info', None)

    def test_macro_state_locker_is_finite_number(self):
        from src.services.macro_state_locker import _is_finite_number
        assert _is_finite_number(_HUGE) is False
        assert _is_finite_number(10 ** 300) is True and _is_finite_number(0) is True

    def test_macro_state_locker_engine_treats_as_missing(self):
        from src.services.macro_state_locker import calculate_system_state
        base = {'VIX_Index': 18.0, 'ISM_PMI_or_OECD_CLI': 51.0, 'PMI_Prev_Month': 50.5,
                'M1B_YoY_pct': 4.0, 'M2_YoY_pct': 5.0, 'BIAS240_pct': 3.0,
                'PCR': 1.0, 'Futures_Net_Short': -1000}
        bad = dict(base, VIX_Index=_HUGE)
        miss = {k: v for k, v in base.items() if k != 'VIX_Index'}
        assert calculate_system_state(bad) == calculate_system_state(miss)

    def test_macro_helpers_safe_float(self):
        from src.compute.macro.macro_helpers import _safe_float
        assert _safe_float(_HUGE) is None
        assert _safe_float(12.5) == 12.5 and _safe_float('3') == 3.0

    def test_long_term_regime_overflow_is_missing(self):
        from src.compute.macro.macro_helpers import classify_long_term_regime
        a = classify_long_term_regime(_HUGE, 4.0, 4.25, 25, 51)
        b = classify_long_term_regime(None, 4.0, 4.25, 25, 51)
        assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)

    def test_read_v4_macro_veto(self):
        import streamlit as st
        from src.ui.tabs.macro.section_chips import read_v4_macro_veto
        st.session_state['macro_info'] = {'vix': {'current': _HUGE}}
        try:
            assert read_v4_macro_veto() is None
        finally:
            st.session_state.pop('macro_info', None)


def _exec_between(path, start, stop, ns):
    """執行上線原始碼中 `start` 那行起、`stop` 那行前的片段（拔修復 → 這裡跟著變紅）。"""
    import textwrap
    src = open(path, encoding='utf-8').read()
    i = src.index(start)
    j = src.index(stop, i)
    code = textwrap.dedent(src[src.rfind('\n', 0, i) + 1:src.rfind('\n', 0, j) + 1])
    ns.setdefault('math', math)
    exec(compile(code, path, 'exec'), ns)
    return ns


class TestOverflowL5Snippets:
    def _hs(self, cur):
        ns = {'st': type('S', (), {'session_state': {'macro_info': {'vix': {'current': cur}}}})()}
        return _exec_between('src/ui/tabs/stock_sections/section_health_score.py',
                             "_mi_v4 = st.session_state.get('macro_info')",
                             "_li_for_v4 = ", ns)['_v4_vix2']

    def test_health_score_v4_vix_overflow(self):
        assert self._hs(_HUGE) is None

    def test_health_score_v4_vix_finite_unchanged(self):
        assert self._hs(21.3) == 21.3

    def _tab_stock_lines(self, cur):
        ns = {'_macro_info2': {'vix': {'current': cur}}, '_ma_snap2': {},
              '_drt2': lambda k: 'D', '_macro_lines2': []}
        return _exec_between('src/ui/tabs/tab_stock.py',
                             "_vix_v2 = (_macro_info2.get('vix') or {})",
                             "_cpi_v2 = ", ns)['_macro_lines2']

    def test_tab_stock_ai_prompt_vix_omitted(self):
        assert self._tab_stock_lines(_HUGE) == []

    def test_tab_stock_finite_unchanged(self):
        assert self._tab_stock_lines(19.234) == ['VIX 恐慌指數=19.23（D）']


class TestSavePortfolioOverflow:
    def _ws(self):
        from tests.test_gsheet_portfolio import _FakeWorksheet, _mixed_sheet
        return _FakeWorksheet([list(r) for r in _mixed_sheet()], row_count=5, col_count=5)

    @pytest.mark.parametrize('field', ['lots', 'avg_price'])
    @pytest.mark.parametrize('bad', [_HUGE, -_HUGE], ids=['huge', 'neg_huge'])
    def test_raises_existing_value_error_before_any_write(self, field, bad):
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
        assert ws.row_count == 5 and ws.col_count == 5

    def test_non_numeric_still_skipped(self):
        from unittest.mock import patch
        import src.data.portfolio.gsheet_portfolio as gsp
        ws = self._ws()
        with patch.object(gsp, '_ws', return_value=ws):
            n = gsp.save_portfolio('A', [{'ticker': 'voo', 'lots': 0.1, 'avg_price': 400.0},
                                         {'ticker': 'y', 'lots': 'abc', 'avg_price': 1}])
        assert n == 1 and [c[0] for c in ws.calls][-1] == 'update'
