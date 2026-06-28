"""v18.351 PR-Q1 — app.py hot path 5 fetcher S-PROV-1 phase 19 provenance。

5 個 fetcher 補 provenance(§2.2):
- fetch_price_data: df.attrs['source']/['fetched_at'] setdefault
- fetch_dividend_data: source 已在 3-tuple,新增 stderr log 帶 fetched_at
- fetch_financials: 3 src 欄已在 7-tuple,新增 stderr log
- fetch_revenue: DataFrame attrs setdefault
- fetch_quarterly: DataFrame attrs setdefault

介面 0 改原則:
- DataFrame return → schema-additive attrs setdefault(不覆蓋既有上游 phase 15/16)
- Tuple return → stderr audit trail(不破 caller 簽章)
"""
from __future__ import annotations

import unittest


class TestAppProvenanceMarkersInSource(unittest.TestCase):
    """5 處 PR-Q1 marker 都在 source code(防 regression)。"""

    def setUp(self):
        with open('app.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_fetch_price_data_marker(self):
        # df.attrs setdefault + ref data_loader.get_combined_data
        self.assertIn('PR-Q1 S-PROV-1 phase 19', self.src)
        self.assertIn("setdefault('source', 'app:fetch_price_data:data_loader.get_combined_data')",
                      self.src)
        self.assertIn("setdefault('fetched_at'", self.src)

    def test_fetch_dividend_data_stderr_marker(self):
        self.assertIn('[fetch_dividend_data]', self.src)
        self.assertIn('source={source or "FAIL"}', self.src)
        self.assertIn('avg_div={avg_div', self.src)

    def test_fetch_financials_stderr_marker(self):
        self.assertIn('[fetch_financials]', self.src)
        self.assertIn('cl_src=', self.src)
        self.assertIn('cx_src=', self.src)
        self.assertIn('capex_src=', self.src)

    def test_fetch_revenue_attrs_setdefault(self):
        self.assertIn("setdefault('source',\n                    'app:fetch_revenue:data_loader.get_monthly_revenue')",
                      self.src)

    def test_fetch_quarterly_attrs_setdefault(self):
        self.assertIn("setdefault('source',\n                    'app:fetch_quarterly:data_loader.get_quarterly_data')",
                      self.src)


class TestInterfaceUnchanged(unittest.TestCase):
    """5 函式簽章 + return shape 沒改(caller compatibility)。"""

    def setUp(self):
        import ast
        with open('app.py', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        self.fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def test_fetch_price_data_signature(self):
        fn = self.fns.get('fetch_price_data')
        self.assertIsNotNone(fn)
        args = [a.arg for a in fn.args.args]
        self.assertEqual(args, ['sid', 'days'])

    def test_fetch_dividend_data_signature(self):
        fn = self.fns.get('fetch_dividend_data')
        self.assertIsNotNone(fn)
        args = [a.arg for a in fn.args.args]
        self.assertEqual(args, ['sid'])

    def test_fetch_financials_signature(self):
        fn = self.fns.get('fetch_financials')
        self.assertIsNotNone(fn)
        args = [a.arg for a in fn.args.args]
        self.assertEqual(args, ['sid', 'industry'])

    def test_fetch_revenue_signature(self):
        fn = self.fns.get('fetch_revenue')
        self.assertIsNotNone(fn)
        args = [a.arg for a in fn.args.args]
        self.assertEqual(args, ['sid'])

    def test_fetch_quarterly_signature(self):
        fn = self.fns.get('fetch_quarterly')
        self.assertIsNotNone(fn)
        args = [a.arg for a in fn.args.args]
        self.assertEqual(args, ['sid', '_ver'])


if __name__ == "__main__":
    unittest.main()
