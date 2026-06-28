"""v18.358 PR-R1 — §8.2 A7 違規修:etf_calc L2 純化。

audit (post v18.357) 結論:**僅剩 1 個** §8.2 違規 — etf_calc.py:587 在 L2 Compute
直呼 yf.download。本 PR 抽至 etf_fetch.fetch_etf_peer_history (L1)。

修法:
- etf_fetch.py +fetch_etf_peer_history(tickers, period)— 批次 yf.download,L1 Data
- etf_calc.compute_etf_peer_ranking — 改 import L1 fetcher,移除 yfinance I/O
- etf_calc.py 移除 module-level `import yfinance as yf`(原唯一用途已搬走)

§8.2 hard rule 守護:
- L2 Compute (etf_calc) 不得 import yfinance / requests / proxy_helper
- L1 Data (etf_fetch) 可 import yfinance(已有,且本檔 @st.cache_data 屬 EX-CACHE-1)
"""
from __future__ import annotations

import ast
import unittest


class TestEtfCalcL2Pure(unittest.TestCase):
    """etf_calc 已無 yfinance / requests / proxy_helper module-level import。"""

    def setUp(self):
        with open('src/compute/etf/etf_calc.py', encoding='utf-8') as f:
            self.tree = ast.parse(f.read())

    def _module_level_imports(self, mod_prefix: str):
        """回傳 module-level import 的模組名(prefix match)。"""
        out = []
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split('.')[0] == mod_prefix:
                        out.append(a.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] == mod_prefix:
                    out.append(node.module)
        return out

    def test_no_yfinance_module_level(self):
        self.assertFalse(self._module_level_imports('yfinance'),
                         'etf_calc 不得 module-level import yfinance (§8.2 L2 rule)')

    def test_no_requests_module_level(self):
        self.assertFalse(self._module_level_imports('requests'),
                         'etf_calc 不得 import requests (§8.2 L2 rule)')

    def test_no_proxy_helper_module_level(self):
        self.assertFalse(self._module_level_imports('proxy_helper'),
                         'etf_calc 不得 from src.data.proxy import proxy_helper (§8.2 L2 rule)')


class TestEtfFetchPeerHistoryExists(unittest.TestCase):

    def test_function_exists(self):
        from src.data.etf import fetch_etf_peer_history
        import inspect
        sig = inspect.signature(fetch_etf_peer_history)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ['tickers', 'period'])
        self.assertEqual(sig.parameters['period'].default, '2y')

    def test_caller_unchanged(self):
        """compute_etf_peer_ranking 簽章不變(caller compat)。"""
        from src.compute.etf import compute_etf_peer_ranking
        import inspect
        sig = inspect.signature(compute_etf_peer_ranking)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ['ticker', 'periods'])
        self.assertEqual(sig.parameters['periods'].default, (63, 126, 252))


class TestSourceMarker(unittest.TestCase):

    def test_etf_calc_a7_marker(self):
        src = open('src/compute/etf/etf_calc.py', encoding='utf-8').read()
        self.assertIn('PR-R1 §8.2 A7', src)
        # 確認從 etf_fetch import 新 fetcher
        self.assertIn('from src.data.etf import fetch_etf_peer_history', src)

    def test_etf_fetch_new_fn_marker(self):
        src = open('src/data/etf/etf_fetch.py', encoding='utf-8').read()
        self.assertIn('v18.358 PR-R1 §8.2 A7', src)
        self.assertIn('def fetch_etf_peer_history(', src)


if __name__ == "__main__":
    unittest.main()
