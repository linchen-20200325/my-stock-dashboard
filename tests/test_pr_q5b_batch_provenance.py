"""v18.356 PR-Q5b — 6 檔 11 fetcher batch provenance。

策略一致(對齊 Q1-Q5a):
- DataFrame return → df.attrs.setdefault
- Series return → series.attrs.setdefault
- dict/scalar return → stderr audit trail
"""
from __future__ import annotations

import unittest


class TestQ5bMarkersInSource(unittest.TestCase):
    """11 fetcher 主 success 路徑都有 PR-Q5b marker。"""

    @staticmethod
    def _read(path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def test_tab_stock_picker_2(self):
        src = self._read('src/ui/tabs/tab_stock_picker.py')
        self.assertIn('[_fetch_fs_safe]', src)
        self.assertIn('src.data.core.data_loader.fetch_financial_statements', src)
        self.assertIn('[_fetch_quarterly_is]', src)
        self.assertIn('FinMind:TaiwanStockFinancialStatements', src)

    def test_etf_tab_grp_compare_1(self):
        src = self._read('src/ui/etf/etf_tab_grp_compare.py')
        self.assertIn('[_fetch_one_etf]', src)
        self.assertIn('etf_fetch(7-metrics aggregator)', src)

    def test_yield_screener_2(self):
        # P1-1b v18.375:fetch_dividend_history 整檔搬至 src/data/stock/dividend_fetcher.py。
        # source check 改合集(yield_screener 仍有 fetch_twse_yield_pe + thin re-export)。
        src = (self._read('src/ui/tabs/yield_screener.py')
               + self._read('src/data/stock/dividend_fetcher.py'))
        # fetch_twse_yield_pe — DataFrame attrs
        self.assertIn("'TWSE:OpenAPI:BWIBBU_d'", src)
        # fetch_dividend_history → 改 fetch_annual_dividends — Series attrs
        self.assertIn('yfinance.Ticker', src)

    def test_monthly_revenue_screener_2(self):
        src = self._read('src/ui/tabs/monthly_revenue_screener.py')
        self.assertIn("'FinMind:TaiwanStockMonthRevenue:single'", src)
        self.assertIn("'FinMind:TaiwanStockMonthRevenue:batch(all-market)'", src)

    def test_data_loader_2(self):
        src = self._read('src/data/core/data_loader.py')
        self.assertIn('src.data.core.data_loader._fetch_twse_inst_fallback:TWSE T86', src)
        self.assertIn('src.data.core.data_loader._fetch_tpex_inst_fallback:TPEx 三大法人', src)

    def test_tab_stock_2(self):
        src = self._read('src/ui/tabs/tab_stock.py')
        # _fetch_share_capital + _fetch_pbratio_from_twse 新增 success-path log
        self.assertIn('FinMind:TaiwanStockBalanceSheet', src)
        self.assertIn('TWSE:OpenAPI:BWIBBU_d(via yield_screener)', src)


class TestImports(unittest.TestCase):

    def test_tab_stock_picker(self):
        from src.ui.tabs import tab_stock_picker  # noqa

    def test_etf_tab_grp_compare(self):
        from src.ui.etf import etf_tab_grp_compare  # noqa

    def test_yield_screener(self):
        from src.ui.tabs import yield_screener  # noqa

    def test_monthly_revenue_screener(self):
        from src.ui.tabs import monthly_revenue_screener  # noqa

    def test_data_loader(self):
        from src.data.core import data_loader  # noqa

    def test_tab_stock(self):
        from src.ui.tabs import tab_stock  # noqa


if __name__ == "__main__":
    unittest.main()
