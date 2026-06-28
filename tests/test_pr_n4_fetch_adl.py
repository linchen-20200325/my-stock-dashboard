"""v18.347 PR-N4 — daily_data_fetchers 加 fetch_adl + _adl_selftest。

MEDIUM risk:fetch_adl 138 LOC 含 yfinance 抓取 + ADL 公式 + cache + log,
proxy env handling 複雜。守衛測重點:
1. 函式可獨立 import
2. re-export identity 維持
3. _adl_selftest 內建邏輯仍正確(無迴歸)
4. 簽章不變(days=60 預設)
"""
from __future__ import annotations

import unittest


class TestFetchAdlExtracted(unittest.TestCase):

    def test_fetch_adl_importable(self):
        from daily_data_fetchers import fetch_adl  # noqa
        import inspect
        sig = inspect.signature(fetch_adl)
        self.assertIn('days', sig.parameters)
        self.assertEqual(sig.parameters['days'].default, 60)
        self.assertIn('token', sig.parameters)

    def test_selftest_importable(self):
        from daily_data_fetchers import _adl_selftest  # noqa
        # 直接執行內建 selftest(不抓網路,純解析邏輯)
        _adl_selftest()  # 若有 regression assert fail 會炸

    def test_reexport_identity(self):
        from daily_checklist import fetch_adl as _a1, _adl_selftest as _s1
        from daily_data_fetchers import fetch_adl as _a2, _adl_selftest as _s2
        self.assertIs(_a1, _a2)
        self.assertIs(_s1, _s2)


if __name__ == "__main__":
    unittest.main()
