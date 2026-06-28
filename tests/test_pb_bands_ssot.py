"""v18.326 P/B 帶狀 SSOT + BPS / industry fetcher 下沉 守衛測試。

涵蓋:
1. shared/stock_buckets 新增 PB_BANDS_* 常數值 + 產業分類
2. get_pb_bands() / pb_bands_label() / classify_pb_level() 行為
3. data_loader 新增 fetch_bps / fetch_industry_category / fetch_bps_from_finmind 三個 public 函式
4. tab_stock.py 私有 _fetch_bps / _fetch_industry_category 已退役(SSOT 化)
5. tab_stock_grp.py 已 import P/B SSOT + 加 P/B 評價欄
"""
from __future__ import annotations


class TestPBBandsConstants:
    def test_constants_exist_and_values(self):
        from shared.stock_buckets import (
            PB_BANDS_FINANCIAL, PB_BANDS_GROWTH, PB_BANDS_MFG,
        )
        assert PB_BANDS_FINANCIAL == (0.5, 0.9, 1.2)
        assert PB_BANDS_GROWTH == (1.5, 2.5, 4.0)
        assert PB_BANDS_MFG == (0.8, 1.5, 2.5)

    def test_bands_strictly_increasing(self):
        """每組 bands 必須 low < mid < high(便宜→合理→偏貴 單調)。"""
        from shared.stock_buckets import (
            PB_BANDS_FINANCIAL, PB_BANDS_GROWTH, PB_BANDS_MFG,
        )
        for bands in (PB_BANDS_FINANCIAL, PB_BANDS_GROWTH, PB_BANDS_MFG):
            low, mid, high = bands
            assert low < mid < high, f"bands {bands} 非單調遞增"


class TestGetPBBands:
    def test_financial_industry_keywords(self):
        from shared.stock_buckets import PB_BANDS_FINANCIAL, get_pb_bands
        for kw in ('金融保險業', '銀行業', '證券業', '保險業'):
            assert get_pb_bands(kw) == PB_BANDS_FINANCIAL, f'{kw} 應分到金融帶'

    def test_growth_industry_keywords(self):
        from shared.stock_buckets import PB_BANDS_GROWTH, get_pb_bands
        for kw in ('半導體業', '電子工業', '光電業', '其他電子業'):
            assert get_pb_bands(kw) == PB_BANDS_GROWTH, f'{kw} 應分到成長帶'

    def test_default_to_manufacturing(self):
        from shared.stock_buckets import PB_BANDS_MFG, get_pb_bands
        assert get_pb_bands(None) == PB_BANDS_MFG
        assert get_pb_bands('') == PB_BANDS_MFG
        assert get_pb_bands('鋼鐵工業') == PB_BANDS_MFG  # 非金融/成長


class TestClassifyPBLevel:
    def test_invalid_value_returns_dash(self):
        from shared.stock_buckets import PB_BANDS_MFG, classify_pb_level
        assert classify_pb_level(0, PB_BANDS_MFG) == '—'
        assert classify_pb_level(-1.0, PB_BANDS_MFG) == '—'
        assert classify_pb_level(None, PB_BANDS_MFG) == '—'

    def test_four_levels_monotone(self):
        """便宜 < low < 合理 < mid < 偏貴 < high < 超貴 — 四級依序。"""
        from shared.stock_buckets import PB_BANDS_MFG, classify_pb_level
        # PB_BANDS_MFG = (0.8, 1.5, 2.5)
        assert '便宜' in classify_pb_level(0.5, PB_BANDS_MFG)   # < 0.8
        assert '合理' in classify_pb_level(1.0, PB_BANDS_MFG)   # 0.8-1.5
        assert '偏貴' in classify_pb_level(2.0, PB_BANDS_MFG)   # 1.5-2.5
        assert '超貴' in classify_pb_level(3.0, PB_BANDS_MFG)   # >= 2.5


class TestDataLoaderSSOTPublic:
    def test_public_fetchers_exist(self):
        """data_loader 已加 3 個 public fetcher,個股 + 組合 Tab 共用。"""
        from src.data.core import data_loader as dl
        assert hasattr(dl, 'fetch_bps'), 'data_loader 缺 fetch_bps()'
        assert hasattr(dl, 'fetch_industry_category'), \
            'data_loader 缺 fetch_industry_category()'
        assert hasattr(dl, 'fetch_bps_from_finmind'), \
            'data_loader 缺 fetch_bps_from_finmind()'


class TestTabStockNoPrivateFetchers:
    def test_no_inline_pb_bands_constants(self):
        """tab_stock.py 不再 inline 定義 _PB_BANDS_*(已下沉 shared/stock_buckets)。"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '_PB_BANDS_FINANCIAL = (0.5' not in src
        assert '_PB_BANDS_GROWTH    = (1.5' not in src
        assert '_PB_BANDS_MFG       = (0.8' not in src

    def test_imports_ssot_from_shared(self):
        """tab_stock.py 已 import shared.stock_buckets P/B SSOT。"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'get_pb_bands' in src
        assert 'pb_bands_label' in src

    def test_no_private_fetch_definitions(self):
        """tab_stock.py 不再 def 私有 _fetch_bps / _fetch_industry_category(已下沉 data_loader)。"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'def _fetch_bps_from_finmind(' not in src
        assert 'def _fetch_bps(' not in src
        assert 'def _fetch_industry_category(' not in src


class TestTabStockGrpHasPB:
    def test_imports_pb_ssot(self):
        """組合 Tab 已 import P/B SSOT + data_loader fetcher。"""
        src = open('tab_stock_grp.py', encoding='utf-8').read()
        assert 'classify_pb_level' in src
        assert 'get_pb_bands' in src
        assert 'fetch_bps' in src
        assert 'fetch_industry_category' in src

    def test_pb_eval_column_added(self):
        """組合 Tab 多因子排行已加 P/B 評價欄。"""
        src = open('tab_stock_grp.py', encoding='utf-8').read()
        assert "'P/B評價'" in src


class TestMJTrendSSOT:
    def test_compute_one_stock_trend_in_mj_module(self):
        """compute_one_stock_trend 已抽到 mj_trend_score(SSOT,兩 Tab 共用)。"""
        import mj_trend_score
        assert hasattr(mj_trend_score, 'compute_one_stock_trend'), \
            'mj_trend_score 缺 compute_one_stock_trend()'

    def test_grp_uses_ssot(self):
        """組合 Tab 走 SSOT,不再有 file-local _compute_one_stock_trend。"""
        src = open('tab_stock_grp.py', encoding='utf-8').read()
        assert 'def _compute_one_stock_trend(' not in src
        assert 'compute_one_stock_trend' in src  # 是 import 來的

    def test_individual_tab_uses_ssot(self):
        """個股 Tab 已引入 compute_one_stock_trend(MJ 趨勢分數)。"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'compute_one_stock_trend' in src
