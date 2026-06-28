"""v18.354 PR-Q4 — S-PROV-1 phase 19 收尾 batch 9 fetcher。

範圍(分散 3 檔):
- daily_data_fetchers.py 6 fetcher(剛 PR-N 系列抽出,未補 provenance):
  fetch_single / fetch_flow_snapshot / _fetch_otc_via_finmind /
  fetch_institutional / fetch_adl / fetch_margin_balance
- tw_macro.py 2 fetcher:fetch_cbc_ms1_rows / fetch_china_macro
- app.py 1 fetcher:fetch_quarterly_extra (Q1 漏的第 6 個)

策略(對齊 Q1/Q2/Q3 既有模式):
- scalar/tuple return → stderr audit trail
- DataFrame return → df.attrs setdefault
- aggregator (china_macro) → 彙整級 stderr
"""
from __future__ import annotations

import unittest


class TestDailyDataFetchersProvenance(unittest.TestCase):
    """daily_data_fetchers 6 fetcher 主成功路徑都呼叫 _prov_log。"""

    def setUp(self):
        with open('src/data/daily/daily_data_fetchers.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_prov_log_helper_defined(self):
        self.assertIn('def _prov_log(', self.src)
        self.assertIn('PR-Q4 — S-PROV-1 phase 19 helper', self.src)

    def test_fetch_single_logged(self):
        self.assertIn("_prov_log('fetch_single', 'yf_proxy.cached_history'", self.src)

    def test_fetch_flow_snapshot_logged(self):
        self.assertIn("_prov_log('fetch_flow_snapshot'", self.src)
        self.assertIn("'flow_engine+yf_proxy(parallel)'", self.src)

    def test_fetch_otc_logged(self):
        self.assertIn("_prov_log('_fetch_otc_via_finmind'", self.src)
        self.assertIn("'FinMind:TaiwanStockDaily:OTC'", self.src)

    def test_fetch_institutional_logged(self):
        self.assertIn("_prov_log('fetch_institutional'", self.src)
        self.assertIn("'TWSE:BFI82U(via Squid Proxy)'", self.src)

    def test_fetch_adl_logged(self):
        self.assertIn("_prov_log('fetch_adl'", self.src)
        self.assertIn("'yfinance:^TWII(估算 ADL)'", self.src)

    def test_fetch_margin_balance_logged(self):
        self.assertIn("_prov_log('fetch_margin_balance'", self.src)
        self.assertIn("'6-fallback-all-fail'", self.src)


class TestTwMacroProvenance(unittest.TestCase):

    def setUp(self):
        with open('src/data/macro/tw_macro.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_fetch_cbc_ms1_rows_logged(self):
        self.assertIn('[fetch_cbc_ms1_rows]', self.src)
        self.assertIn("source=CBC:ms1.json:", self.src)

    def test_fetch_china_macro_logged(self):
        self.assertIn('[fetch_china_macro]', self.src)
        self.assertIn('FRED:china_macro(5-series-parallel)', self.src)


class TestAppFetchQuarterlyExtraProvenance(unittest.TestCase):

    def test_fetch_quarterly_extra_attrs(self):
        with open('app.py', encoding='utf-8') as f:
            src = f.read()
        self.assertIn("setdefault('source',\n                    'app:fetch_quarterly_extra:data_loader.get_quarterly_bs_cf')",
                      src)


class TestImports(unittest.TestCase):

    def test_daily_data_fetchers(self):
        from src.data.daily import daily_data_fetchers  # noqa
        from src.data.daily import _prov_log
        _prov_log('test_fn', 'test_source', 'TEST', 'unit_test')

    def test_tw_macro(self):
        from src.data.macro import tw_macro  # noqa

    def test_app_ast_parse(self):
        """app.py 用 AST parse 驗證(避開 streamlit secrets pre-existing env bug)。"""
        import ast
        with open('app.py', encoding='utf-8') as f:
            ast.parse(f.read())


if __name__ == "__main__":
    unittest.main()
