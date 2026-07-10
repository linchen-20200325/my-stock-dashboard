"""v19.74 — 外部 code review 修正守衛測試。

對應 dashboard_code_review.md 建議（user 2026-07-10 指派）:
1. P0 三大法人 BFI82U:買賣超欄改 fields 欄名定位,不寫死 row[3]
   （TWSE 改版欄序位移 → 靜默回反向籌碼結論,最危險）
2. P0 融資餘額 FinMind:廢除數值區間猜單位,固定仟元÷1e5=億 + §3.2 sanity 區間
   （原四分支猜測在來源改單位時靜默錯 1 個數量級）
3. P0 fetch_goodinfo_metrics:`proxies: dict` → `_proxies`
   （dict 不可雜湊,@st.cache_data 對非底線參數雜湊 → UnhashableParamError）
4. P1 fetch_price_data:連假容忍窗 5 → 14 日曆日 SSOT
   （春節封關最長 13 日曆日,原 5 天窗連假期間全檔強制重抓撞限流）
5. P2 MOPS fallback 全零偵測 → mops_parse_failed
   （MOPS 長格式塞進 Goodinfo 寬表計算 → 全零假財報餵下游）
6. P2 cache 無上界 → max_entries=64（Streamlit Cloud OOM 防護）
7. tab_stock.py CSS f-string 字面大括號 bug（{TRAFFIC_GREEN}18 未插值）
"""
from __future__ import annotations

import inspect
import unittest

import pandas as pd


# ═══════════════════════════════════════════════════════════════
# 1. BFI82U 欄名定位解析
# ═══════════════════════════════════════════════════════════════
class TestParseBfi82uRows(unittest.TestCase):
    """三大法人買賣超解析:欄名定位取代寫死 row[3]。"""

    _FIELDS_STD = ['單位名稱', '買進金額', '賣出金額', '買賣差額']

    def _rows(self, foreign='10,000,000,000', trust='2,000,000,000',
              dealer_a='500,000,000', dealer_b='-300,000,000'):
        return [
            ['自營商(自行買賣)', '1,111', '1,111', dealer_a],
            ['自營商(避險)', '2,222', '2,222', dealer_b],
            ['投信', '3,333', '3,333', trust],
            ['外資及陸資(不含外資自營商)', '4,444', '4,444', foreign],
        ]

    def test_standard_field_order(self):
        """正常欄序:買賣差額在 index 3(元 → 億,自營商兩列加總)。"""
        from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
        out = _parse_bfi82u_rows(self._FIELDS_STD, self._rows())
        self.assertIsNotNone(out)
        self.assertAlmostEqual(out['外資及陸資']['net'], 100.0)
        self.assertAlmostEqual(out['投信']['net'], 20.0)
        self.assertAlmostEqual(out['自營商']['net'], 2.0)  # 5 + (-3) 億

    def test_shifted_field_order(self):
        """TWSE 改版欄序位移:買賣差額移到 index 2 → 仍抓對欄(舊 row[3] 會抓到賣出金額)。"""
        from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
        fields = ['單位名稱', '買進金額', '買賣差額', '賣出金額']
        rows = [
            ['投信', '9,999', '2,000,000,000', '8,888,888,888'],
            ['外資及陸資(不含外資自營商)', '9,999', '-5,000,000,000', '7,777,777,777'],
        ]
        out = _parse_bfi82u_rows(fields, rows)
        self.assertAlmostEqual(out['投信']['net'], 20.0)
        self.assertAlmostEqual(out['外資及陸資']['net'], -50.0)  # 負值買賣超

    def test_missing_net_field_returns_none(self):
        """fields 無「買賣差額」欄 → 回 None(§1 fail loud,不猜位置)。"""
        from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
        fields = ['單位名稱', '買進金額', '賣出金額']  # 改版砍欄
        self.assertIsNone(_parse_bfi82u_rows(fields, self._rows()))

    def test_short_row_skipped(self):
        """單列長度不足(row 缺欄)→ 跳過該列不炸,其他列照算。"""
        from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
        rows = [['投信'], ['外資及陸資(不含外資自營商)', '1', '1', '3,000,000,000']]
        out = _parse_bfi82u_rows(self._FIELDS_STD, rows)
        self.assertAlmostEqual(out['外資及陸資']['net'], 30.0)
        self.assertAlmostEqual(out['投信']['net'], 0.0)

    def test_non_numeric_skipped(self):
        """買賣差額欄為非數字(如 '--')→ 跳過不炸。"""
        from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
        rows = [['投信', '1', '1', '--']]
        out = _parse_bfi82u_rows(self._FIELDS_STD, rows)
        self.assertAlmostEqual(out['投信']['net'], 0.0)


# ═══════════════════════════════════════════════════════════════
# 2. 融資餘額固定單位換算 + sanity 區間
# ═══════════════════════════════════════════════════════════════
class TestFinmindMarginToYi(unittest.TestCase):
    """FinMind 融資餘額 Money 列:元固定換算(÷1e8),超出合理區間 → None。

    v19.79 語意修正:v19.74 誤把 TWSE MI_MARGN 的「仟元」搬到本 dataset(÷1e5),
    2026-07-10 production log 實證 Money 列單位是「元」— 舊斷言反向,已改為
    以線上真實值為 golden。
    """

    def test_production_golden_yuan_accepted(self):
        """2026-07-10 線上真實值:619,648,244,000 元 = 6,196.5 億 → 接受。
        (v19.74 舊換算 ÷1e5 會得 6,196,482 億而錯誤棄用 → FinMind 路徑全滅)"""
        from src.data.daily.daily_data_fetchers import _finmind_margin_to_yi
        self.assertAlmostEqual(_finmind_margin_to_yi(619_648_244_000), 6196.5)

    def test_volume_row_scale_rejected(self):
        """2026-07-10 線上另一列 9,614,955(MarginPurchaseVolume,單位=張):
        若誤入換算 ÷1e8 = 0.096 億 → 低於下限 → None(雙保險;第一道防線是
        caller 的 name==Money 過濾)。"""
        from src.data.daily.daily_data_fetchers import _finmind_margin_to_yi
        self.assertIsNone(_finmind_margin_to_yi(9_614_955))

    def test_unit_shift_to_qianyuan_rejected(self):
        """來源若改「仟元」(6.19e8 仟元=6,196億的仟元表示)→ ÷1e8 = 6.2 億,
        低於下限 → None(單位漂移被 sanity 擋下,不會靜默錯 1000×)。"""
        from src.data.daily.daily_data_fetchers import _finmind_margin_to_yi
        self.assertIsNone(_finmind_margin_to_yi(6.19e8))

    def test_zero_and_negative_rejected(self):
        from src.data.daily.daily_data_fetchers import _finmind_margin_to_yi
        self.assertIsNone(_finmind_margin_to_yi(0))
        self.assertIsNone(_finmind_margin_to_yi(-100))

    def test_sanity_bounds_ssot(self):
        """sanity 區間走 SSOT 常數,邊界外拒收。"""
        from shared.signal_thresholds import (
            MARGIN_BALANCE_SANITY_MAX_YI, MARGIN_BALANCE_SANITY_MIN_YI)
        from src.data.daily.daily_data_fetchers import _margin_sanity_ok
        self.assertTrue(_margin_sanity_ok(2800.0))
        self.assertFalse(_margin_sanity_ok(MARGIN_BALANCE_SANITY_MIN_YI))    # 邊界不含
        self.assertFalse(_margin_sanity_ok(MARGIN_BALANCE_SANITY_MAX_YI))
        self.assertFalse(_margin_sanity_ok(280.0))     # 10× 低估
        self.assertFalse(_margin_sanity_ok(28000.0))   # 10× 高估
        # 歷史極值不誤殺:2008 低點 ~1100 億 / 2024 高點 ~3300 億
        self.assertTrue(_margin_sanity_ok(1100.0))
        self.assertTrue(_margin_sanity_ok(3300.0))

    def test_no_interval_unit_guessing_left(self):
        """方案0 原四分支區間猜單位已移除(源碼守衛)。"""
        with open('src/data/daily/daily_data_fetchers.py', encoding='utf-8') as f:
            src = f.read()
        self.assertNotIn('elif _raw0 > 1e9', src, '區間猜單位分支應已移除')
        self.assertNotIn('elif _raw0 > 1e4', src, '區間猜單位分支應已移除')
        self.assertNotIn('30_000', src, '舊 inline 區間應全數改走 _margin_sanity_ok SSOT')


# ═══════════════════════════════════════════════════════════════
# 3. fetch_goodinfo_metrics 快取鍵
# ═══════════════════════════════════════════════════════════════
class TestGoodinfoMetricsCacheKey(unittest.TestCase):

    def test_proxies_param_renamed_underscore(self):
        """proxies → _proxies(底線前綴讓 @st.cache_data 略過雜湊,dict 不可雜湊)。"""
        from src.data.stock.tw_stock_data_fetcher import fetch_goodinfo_metrics
        params = inspect.signature(fetch_goodinfo_metrics).parameters
        self.assertIn('_proxies', params)
        self.assertNotIn('proxies', params)
        self.assertIsNone(params['_proxies'].default)


# ═══════════════════════════════════════════════════════════════
# 4. 價格快取連假容忍窗
# ═══════════════════════════════════════════════════════════════
class TestPriceCacheHolidayTolerance(unittest.TestCase):

    def test_constant_covers_cny_worst_case(self):
        """SSOT 常數 ≥ 13(2025 春節 1/21 封關 → 2/3 開紅盤 = 13 日曆日)。"""
        from shared.signal_thresholds import PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS
        self.assertGreaterEqual(PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS, 13)
        self.assertLessEqual(PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS, 21,
                             '容忍窗過寬會弱化 stale 偵測')

    def test_fetch_price_data_uses_ssot(self):
        """fetch_price_data 不再 inline `<= 5`,改用 SSOT 常數(源碼守衛)。"""
        with open('src/data/stock/app_stock_fetchers.py', encoding='utf-8') as f:
            src = f.read()
        self.assertIn('PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS', src)
        self.assertNotIn('.days <= 5', src, '原 inline 5 天窗應已移除')


# ═══════════════════════════════════════════════════════════════
# 5. MOPS fallback 全零偵測
# ═══════════════════════════════════════════════════════════════
class TestMopsFallbackAllZeroDetection(unittest.TestCase):

    def test_mops_unparsed_returns_parse_failed(self):
        """Goodinfo 全敗 + MOPS 回非 Goodinfo schema 的長格式 → 全零 →
        應回 {"error": "mops_parse_failed"} 而非零值假財報。"""
        import src.data.stock.tw_stock_data_fetcher as m

        _orig_gi = m.fetch_goodinfo_financials
        _orig_mops = m.fetch_mops_financials
        _orig_sess = m.build_proxy_session
        try:
            m.build_proxy_session = lambda: None
            m.fetch_goodinfo_financials = lambda sid, session=None: {
                'BS': pd.DataFrame(), 'IS': pd.DataFrame(), 'CF': pd.DataFrame()}
            # MOPS 長格式(會計項目/金額),fuzzy 比對不到 Goodinfo 欄名 → 全零
            m.fetch_mops_financials = lambda sid, y, s, session=None: pd.DataFrame(
                {0: ['資產總額', '負債總額'], 1: ['123', '45']})
            _fetch = m._make_cached_fetcher()
            out = _fetch('9999', False)
            self.assertEqual(out.get('error'), 'mops_parse_failed')
            self.assertNotIn('營業收入(千)', out, '不得回傳零值假財報 dict')
        finally:
            m.fetch_goodinfo_financials = _orig_gi
            m.fetch_mops_financials = _orig_mops
            m.build_proxy_session = _orig_sess

    def test_all_sources_failed_unchanged(self):
        """三表全空(MOPS 也空)→ 既有 all_sources_failed 行為不變。"""
        import src.data.stock.tw_stock_data_fetcher as m

        _orig_gi = m.fetch_goodinfo_financials
        _orig_mops = m.fetch_mops_financials
        _orig_sess = m.build_proxy_session
        try:
            m.build_proxy_session = lambda: None
            m.fetch_goodinfo_financials = lambda sid, session=None: {
                'BS': pd.DataFrame(), 'IS': pd.DataFrame(), 'CF': pd.DataFrame()}
            m.fetch_mops_financials = lambda sid, y, s, session=None: pd.DataFrame()
            _fetch = m._make_cached_fetcher()
            out = _fetch('9998', False)
            self.assertEqual(out.get('error'), 'all_sources_failed')
        finally:
            m.fetch_goodinfo_financials = _orig_gi
            m.fetch_mops_financials = _orig_mops
            m.build_proxy_session = _orig_sess


# ═══════════════════════════════════════════════════════════════
# 6. cache max_entries 上界(源碼守衛)
# ═══════════════════════════════════════════════════════════════
class TestCacheMaxEntries(unittest.TestCase):

    def test_per_stock_caches_have_max_entries(self):
        """以 stock_id 為鍵的 5 處 @st.cache_data 均設 max_entries(防 OOM)。"""
        import re as _re
        for path, expect in [
            ('src/data/core/data_loader.py', 2),          # get_combined_data / get_monthly_revenue
            ('src/data/stock/tw_stock_data_fetcher.py', 3),  # _fetch / 5y_cash_flow / goodinfo_metrics
        ]:
            with open(path, encoding='utf-8') as f:
                src = f.read()
            n = len(_re.findall(r'@st\.cache_data\([^)]*max_entries=\d+', src))
            self.assertGreaterEqual(n, expect, f'{path} 應至少 {expect} 處 max_entries')


# ═══════════════════════════════════════════════════════════════
# 7. tab_stock.py CSS f-string 字面大括號 bug(源碼守衛)
# ═══════════════════════════════════════════════════════════════
class TestTabStockCssLiteralBrace(unittest.TestCase):

    def test_no_literal_traffic_placeholder_in_quotes(self):
        """f-string 內不得再出現字面 '"{TRAFFIC_'(引號包住的插值變數 = 不會展開,
        渲染出字面 {TRAFFIC_GREEN}18 而非色碼 → 卡片背景/邊框壞掉)。"""
        with open('src/ui/tabs/tab_stock.py', encoding='utf-8') as f:
            src = f.read()
        self.assertNotIn('"{TRAFFIC_', src)
        self.assertNotIn("'{TRAFFIC_", src)


if __name__ == '__main__':
    unittest.main()
