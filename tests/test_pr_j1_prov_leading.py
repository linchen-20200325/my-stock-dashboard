"""v18.338 PR-J1 — S-PROV-1 A 級:6 先行指標 source_chain 守衛測試。

§2.2 Provenance 出口 — calc_leading_indicators_detail 各指標 dict 補 source_chain 欄。

驗證:
- 6 指標 dict 都有 'source_chain' key
- _resolve_li_source 優先吃 df.attrs['source'] 或 'source' 欄,fallback 到靜態 map
- UI 渲染 chip:tab_stock.py 含「📡 來源」段
"""
from __future__ import annotations

import pandas as pd


# ─────────── A. source_chain key 存在 ───────────

class TestSourceChainEmitted:
    """所有 I1~I6 dict 都帶 source_chain 鍵。"""

    def test_all_six_have_source_chain(self):
        from src.compute.scoring import calc_leading_indicators_detail
        # 全 None 路徑(都是 ⚪)依然要有 source_chain
        results = calc_leading_indicators_detail(rev_df=None, qtr_df=None, bs_cf_df=None)
        assert len(results) == 6
        for _r in results:
            assert 'source_chain' in _r, f"{_r['id']} 缺 source_chain"
            assert isinstance(_r['source_chain'], str)
            assert len(_r['source_chain']) > 0

    def test_static_defaults_per_indicator(self):
        from src.compute.scoring import calc_leading_indicators_detail
        results = calc_leading_indicators_detail()
        _m = {r['id']: r['source_chain'] for r in results}
        # I1/I2 月營收
        assert 'MonthRevenue' in _m['I1']
        assert 'MonthRevenue' in _m['I2']
        # I3 BS
        assert 'BalanceSheet' in _m['I3']
        # I4 CF + FS
        assert 'CashFlows' in _m['I4'] or 'FinancialStatements' in _m['I4']
        # I5 BS + FS
        assert 'BalanceSheet' in _m['I5']
        # I6 N/A
        assert '—' in _m['I6'] or '無' in _m['I6']


# ─────────── B. _resolve_li_source helper ───────────

class TestResolveLiSource:
    """source 解析 helper:attrs / 'source' 欄 / fallback。"""

    def test_none_inputs_returns_default(self):
        from src.compute.scoring import _resolve_li_source
        r = _resolve_li_source('DEFAULT_X')
        assert r == 'DEFAULT_X'

    def test_df_attrs_source_wins_over_default(self):
        from src.compute.scoring import _resolve_li_source
        _df = pd.DataFrame({'x': [1, 2, 3]})
        _df.attrs['source'] = 'FinMind:Live:Test'
        r = _resolve_li_source('STATIC_DEFAULT', _df)
        assert 'FinMind:Live:Test' in r
        # default 因為 attrs 命中而被覆蓋
        assert 'STATIC_DEFAULT' not in r

    def test_source_column_used_when_no_attrs(self):
        from src.compute.scoring import _resolve_li_source
        _df = pd.DataFrame({
            'x': [1, 2, 3],
            'source': ['FinMind:Col:Test', 'FinMind:Col:Test', None],
        })
        r = _resolve_li_source('STATIC', _df)
        assert 'FinMind:Col:Test' in r

    def test_multiple_dfs_dedupe(self):
        from src.compute.scoring import _resolve_li_source
        _d1 = pd.DataFrame({'x': [1]})
        _d1.attrs['source'] = 'S_A'
        _d2 = pd.DataFrame({'x': [1]})
        _d2.attrs['source'] = 'S_A'  # 重複
        _d3 = pd.DataFrame({'x': [1]})
        _d3.attrs['source'] = 'S_B'  # 新
        r = _resolve_li_source('DEFAULT', _d1, _d2, _d3)
        # 應只有 S_A / S_B 不重複
        assert r.count('S_A') == 1
        assert 'S_B' in r

    def test_empty_df_falls_back_to_default(self):
        from src.compute.scoring import _resolve_li_source
        _df = pd.DataFrame()
        r = _resolve_li_source('FALLBACK_OK', _df)
        assert r == 'FALLBACK_OK'

    def test_corrupt_df_does_not_raise(self):
        from src.compute.scoring import _resolve_li_source
        # 不可 hash 的物件當 df → 不該 raise
        r = _resolve_li_source('SAFE', 'not a df', 12345, None)
        # 字串 'not a df' 沒有 attrs / columns,fallback
        assert r == 'SAFE'


# ─────────── C. Live wiring with attrs ───────────

class TestLiveAttrsWiring:
    """當 caller 傳入帶 attrs['source'] 的 df 時,出口應反映即時 source。"""

    def test_rev_df_attrs_propagates_to_i1(self):
        from src.compute.scoring import calc_leading_indicators_detail
        _rev = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=13, freq='ME'),
            'revenue': [100 + i * 5 for i in range(13)],
            'yoy': [5.0 + i * 0.5 for i in range(13)],
        })
        _rev.attrs['source'] = 'FinMind:TaiwanStockMonthRevenue:live'
        results = calc_leading_indicators_detail(rev_df=_rev)
        _m = {r['id']: r for r in results}
        assert 'FinMind:TaiwanStockMonthRevenue:live' in _m['I1']['source_chain']
        assert 'FinMind:TaiwanStockMonthRevenue:live' in _m['I2']['source_chain']

    def test_bs_cf_attrs_propagates_to_i3_i4_i5(self):
        from src.compute.scoring import calc_leading_indicators_detail
        _bs = pd.DataFrame()
        _bs.attrs['source'] = 'FinMind:BS:live'
        results = calc_leading_indicators_detail(bs_cf_df=_bs)
        _m = {r['id']: r for r in results}
        assert 'FinMind:BS:live' in _m['I3']['source_chain']
        assert 'FinMind:BS:live' in _m['I4']['source_chain']
        assert 'FinMind:BS:live' in _m['I5']['source_chain']


# ─────────── D. UI chip ───────────

class TestUIChipRendered:
    """tab_stock D2 chip 段已加 _src_chip。"""

    def test_tab_stock_has_source_chip(self):
        # U4 Phase 3-D2 v18.408:D2 section 已抽至 stock_sections.section_d2_leading
        src = open('src/ui/tabs/stock_sections/section_d2_leading.py',
                   encoding='utf-8').read()
        assert '_src_chip' in src
        assert '📡 來源' in src
        assert "_ind.get('source_chain')" in src


# ─────────── E. Caller migration smoke ───────────

class TestModulesImportable:
    def test_scoring_engine_clean(self):
        from src.compute.scoring import scoring_engine  # noqa: F401

    def test_tab_stock_clean(self):
        from src.ui.tabs import tab_stock  # noqa: F401

    def test_li_source_map_defined(self):
        from src.compute.scoring import _LI_SOURCE_CHAINS
        assert set(_LI_SOURCE_CHAINS.keys()) == {'I1', 'I2', 'I3', 'I4', 'I5', 'I6'}
