"""v18.345 PR-N2 — daily_data_fetchers.py 抽出 fetch_single + fetch_flow_snapshot。

驗證:
1. daily_data_fetchers 可獨立 import
2. daily_checklist re-export 仍可用(caller 0 改)
3. Re-export identity (IS 同物件,非 copy)
4. 模組無 streamlit import(L1 Data 層,EX-CACHE-1 例外但本檔未用 @st.cache_data)
"""
from __future__ import annotations

import unittest


class TestDailyDataFetchersModule(unittest.TestCase):

    @staticmethod
    def _has_import_stmt(src: str, mod: str) -> bool:
        import ast
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.split('.')[0] == mod for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] == mod:
                    return True
        return False

    def test_module_imports(self):
        import daily_data_fetchers  # noqa
        from daily_data_fetchers import fetch_single, fetch_flow_snapshot  # noqa

    def test_no_streamlit_import(self):
        """daily_data_fetchers 不依賴 streamlit(本檔尚未引入 @st.cache_data)。"""
        with open('daily_data_fetchers.py', encoding='utf-8') as f:
            src = f.read()
        assert not self._has_import_stmt(src, 'streamlit'), \
            'daily_data_fetchers 不應 import streamlit'

    def test_reexport_identity(self):
        """daily_checklist 的 fetch_single/fetch_flow_snapshot IS 新模組同物件。"""
        from daily_checklist import fetch_single as _s1, fetch_flow_snapshot as _f1
        from daily_data_fetchers import fetch_single as _s2, fetch_flow_snapshot as _f2
        self.assertIs(_s1, _s2)
        self.assertIs(_f1, _f2)

    def test_fetch_single_signature(self):
        """fetch_single 仍接受 symbol + period 參數。"""
        import inspect
        from daily_data_fetchers import fetch_single
        sig = inspect.signature(fetch_single)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ['symbol', 'period'])
        self.assertEqual(sig.parameters['period'].default, '60d')

    def test_fetch_flow_snapshot_signature(self):
        """fetch_flow_snapshot 仍接受 period 參數。"""
        import inspect
        from daily_data_fetchers import fetch_flow_snapshot
        sig = inspect.signature(fetch_flow_snapshot)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ['period'])
        self.assertEqual(sig.parameters['period'].default, '2y')


if __name__ == "__main__":
    unittest.main()
