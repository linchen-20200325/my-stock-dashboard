"""v18.348 PR-N5 — daily_data_fetchers 加 fetch_margin_balance(6 路 fallback)。

MEDIUM-HIGH risk:219 LOC,包含
- FinMind TaiwanStockTotalMarginPurchaseShortSale(海外可達)
- TWSE MI_MARGN(MS→ALL 雙 selectType,仟元÷100,000=億)
- HiStock / Goodinfo / Yahoo / cnyes HTML 爬蟲 + BeautifulSoup + 正則

守衛測重點(無 IO):
1. 函式可獨立 import
2. 簽章不變(date_str 預設 None)
3. re-export identity 維持
4. daily_checklist 已無原 def fetch_margin_balance(僅 re-export)
"""
from __future__ import annotations

import unittest


class TestFetchMarginBalanceExtracted(unittest.TestCase):

    def test_importable(self):
        from daily_data_fetchers import fetch_margin_balance  # noqa
        import inspect
        sig = inspect.signature(fetch_margin_balance)
        self.assertIn('date_str', sig.parameters)
        self.assertIsNone(sig.parameters['date_str'].default)

    def test_reexport_identity(self):
        from daily_checklist import fetch_margin_balance as _m1
        from daily_data_fetchers import fetch_margin_balance as _m2
        self.assertIs(_m1, _m2)

    def test_daily_checklist_no_inline_def(self):
        """daily_checklist.py 應已無原 def fetch_margin_balance(僅 re-export)。"""
        import ast
        with open('daily_checklist.py', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        _defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        self.assertNotIn('fetch_margin_balance', _defs,
                         'fetch_margin_balance 應已抽至 daily_data_fetchers,'
                         'daily_checklist 應只 re-export')

    def test_caller_health_inspector_works(self):
        """health_inspector L204 `from daily_checklist import fetch_margin_balance` 仍 OK。"""
        # 不執行(無 token),只驗 import 路徑
        import importlib
        _mod = importlib.import_module('daily_checklist')
        self.assertTrue(hasattr(_mod, 'fetch_margin_balance'))


if __name__ == "__main__":
    unittest.main()
