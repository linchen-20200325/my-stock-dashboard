"""v18.346 PR-N3 — daily_data_fetchers 加 _fetch_otc_via_finmind + fetch_institutional。

驗證:
1. 兩個函式從 daily_data_fetchers 可 import
2. daily_checklist re-export identity 仍維持
3. fetch_institutional 接 cache_layer SSOT(_pkl_get/put)
4. _get_finmind_token 純函式可獨立呼叫
"""
from __future__ import annotations

import unittest


class TestNewFetchersExtracted(unittest.TestCase):

    def test_fetch_institutional_importable(self):
        from src.data.daily import fetch_institutional  # noqa
        import inspect
        sig = inspect.signature(fetch_institutional)
        self.assertIn('date_str', sig.parameters)
        self.assertIsNone(sig.parameters['date_str'].default)

    def test_fetch_otc_importable(self):
        from src.data.daily import _fetch_otc_via_finmind  # noqa
        import inspect
        sig = inspect.signature(_fetch_otc_via_finmind)
        self.assertIn('token', sig.parameters)

    def test_reexport_identity(self):
        from daily_checklist import fetch_institutional as _i1, _fetch_otc_via_finmind as _o1
        from src.data.daily import fetch_institutional as _i2, _fetch_otc_via_finmind as _o2
        self.assertIs(_i1, _i2)
        self.assertIs(_o1, _o2)

    def test_get_finmind_token_helper(self):
        """_get_finmind_token 可獨立呼叫,不爆。"""
        from src.data.daily import _get_finmind_token
        _t = _get_finmind_token()
        self.assertIsInstance(_t, str)  # 可能空字串(無 token)但必須是 str

    def test_cache_layer_imported_at_module_level(self):
        """fetch_institutional 接 cache_layer SSOT(import 在 module level)。"""
        with open('src/data/daily/daily_data_fetchers.py', encoding='utf-8') as f:
            src = f.read()
        self.assertIn('from shared.cache_layer import', src)
        self.assertIn('_pkl_get', src)
        self.assertIn('_pkl_put', src)


if __name__ == "__main__":
    unittest.main()
