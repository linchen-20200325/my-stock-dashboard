"""v18.352 PR-Q2 — etf_fetch.py 7 fetcher S-PROV-1 phase 19 provenance。

7 個 fetcher 補 §2.2 audit trail(stderr log,介面 0 改):
- fetch_sitca_expense_ratio
- ~~fetch_moneydj_expense_ratio~~(Issue #1208 PR2:MoneyDJ 全入口零請求止血刪除)
- _fetch_holdings_yahoo_tw
- fetch_etf_holdings
- ~~_fetch_sitca_manager~~(Issue #1208:隨 ETF 經理人換手策略取消刪除)
- fetch_etf_zh_name
- ~~fetch_etf_underlying_index~~(Issue #1208 PR2:MoneyDJ-only 死碼刪除)

共用 module 級 _prov_log() helper(L20 區間)避免重複實作。
"""
from __future__ import annotations

import unittest


class TestEtfFetchProvenanceMarkers(unittest.TestCase):
    """7 處 PR-Q2 marker 都在 source code(防 regression)。"""

    def setUp(self):
        with open('src/data/etf/etf_fetch.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_prov_log_helper_defined(self):
        """_prov_log helper 存在(共用 audit trail)。"""
        self.assertIn('def _prov_log(', self.src)
        self.assertIn('PR-Q2 — S-PROV-1 phase 19 helper', self.src)

    def test_sitca_expense_logged(self):
        self.assertIn("_prov_log('fetch_sitca_expense_ratio'", self.src)
        self.assertIn("'SITCA:IN2222_01'", self.src)

    # test_moneydj_expense_logged 已移除:fetch_moneydj_expense_ratio 隨 Issue #1208 PR2 刪除。
    # 反向守衛:tests/test_issue1208_moneydj_zero_requests.py。

    def test_yahoo_tw_holdings_logged(self):
        self.assertIn("_prov_log('_fetch_holdings_yahoo_tw'", self.src)
        self.assertIn("'Yahoo:tw.stock:quote/holding'", self.src)

    def test_etf_holdings_logged(self):
        self.assertIn("_prov_log('fetch_etf_holdings'", self.src)
        # source 標籤(yf / Yahoo / all-fail;#1208 PR2 已移除 MoneyDJ)
        self.assertIn("'yfinance:funds_data:top_holdings'", self.src)
        self.assertIn("'all-sources-failed'", self.src)

    # test_sitca_manager_logged 已移除:_fetch_sitca_manager 隨 Issue #1208 刪除。

    def test_zh_name_logged(self):
        self.assertIn("_prov_log('fetch_etf_zh_name'", self.src)

    # test_underlying_index_logged 已移除:fetch_etf_underlying_index 隨 Issue #1208 PR2 刪除。


class TestInterfaceUnchanged(unittest.TestCase):
    """7 函式簽章不變(caller compatibility)。"""

    def setUp(self):
        import ast
        with open('src/data/etf/etf_fetch.py', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        self.fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def test_signatures(self):
        # 各函式至少有第一個位置參數(其餘 caller 沒檢驗,因 kwargs 多變)
        for _name, _arg0 in [
            ('fetch_sitca_expense_ratio', 'ticker'),
            ('_fetch_holdings_yahoo_tw', 'symbol_yf'),
            ('fetch_etf_holdings', 'ticker'),
            ('fetch_etf_zh_name', 'ticker'),
        ]:
            fn = self.fns.get(_name)
            self.assertIsNotNone(fn, f'{_name} 應存在')
            self.assertEqual(fn.args.args[0].arg, _arg0,
                             f'{_name} 第一參數應 {_arg0}')


class TestImport(unittest.TestCase):
    def test_etf_fetch_imports(self):
        from src.data.etf import etf_fetch  # noqa
        # _prov_log 可呼叫
        from src.data.etf import _prov_log
        _prov_log('test_fn', 'test_source', 'TEST', 'unit_test')


if __name__ == "__main__":
    unittest.main()
