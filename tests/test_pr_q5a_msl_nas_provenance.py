"""v18.355 PR-Q5a — macro_signal_lookback_tw 8 + nas_server 4 provenance。

策略:
- macro_signal_lookback_tw 8 fetch_*_series 套 _attach_prov(Series.attrs setdefault)
- nas_server 4 _fetch_X 套 _prov_log(stderr,server module)

§2.2 audit trail 完整化;介面 0 改。
"""
from __future__ import annotations

import unittest


class TestMacroSignalLookbackTwProvenance(unittest.TestCase):

    def setUp(self):
        with open('macro_signal_lookback_tw.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_attach_prov_helper(self):
        self.assertIn('def _attach_prov(', self.src)
        self.assertIn('PR-Q5a — S-PROV-1 phase 19 helper', self.src)

    def test_8_fetchers_attach_prov(self):
        """8 個 fetch_*_series 主 return 都套 _attach_prov。"""
        # Count _attach_prov calls — should be 8
        _count = self.src.count('_attach_prov(')
        # 8 fetcher returns + 1 helper def = 9 occurrences
        self.assertGreaterEqual(_count, 9,
                                f'_attach_prov occurrences should be >= 9, got {_count}')

    def test_signal_keys_in_sources(self):
        """每個 signal 的 source label 有 parquet 路徑 + 計算公式。"""
        for _src in [
            'data_cache:finmind_inst.parquet',
            'data_cache:finmind_margin.parquet',
            'data_cache:finmind_m1m2.parquet',
            'data_cache:twii_ohlcv.parquet',
            'data_cache:tw_pmi.parquet',
        ]:
            self.assertIn(_src, self.src, f'{_src} 應出現在 source label')


class TestNasServerProvenance(unittest.TestCase):

    def setUp(self):
        with open('src/data/proxy/nas_server.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_prov_log_helper(self):
        self.assertIn('def _prov_log(', self.src)
        self.assertIn('PR-Q5a — S-PROV-1 phase 19 helper', self.src)

    def test_4_fetchers_log(self):
        for _fn in [
            '_fetch_institutional',
            '_fetch_margin_balance',
            '_fetch_export_yoy',
            '_fetch_business_indicator',
        ]:
            self.assertIn(f"_prov_log('{_fn}'", self.src,
                          f'{_fn} 應呼叫 _prov_log')

    def test_source_labels(self):
        """主要 source label 都標(NAS direct 表示 NAS 中繼站直連)。"""
        self.assertIn('TWSE:BFI82U(NAS direct)', self.src)
        self.assertIn('TWSE:MI_MARGN(NAS direct)', self.src)
        self.assertIn('MOF:trade(NAS direct)', self.src)
        self.assertIn('(NAS direct)', self.src)


class TestImports(unittest.TestCase):

    def test_macro_signal_lookback_tw_imports(self):
        import macro_signal_lookback_tw  # noqa
        from macro_signal_lookback_tw import _attach_prov
        import pandas as pd
        _s = pd.Series([1, 2, 3], name='TEST')
        _attach_prov(_s, 'test_source')
        self.assertEqual(_s.attrs.get('source'), 'test_source')
        self.assertIn('fetched_at', _s.attrs)

    def test_nas_server_ast_parse(self):
        """nas_server.py 用 AST parse 避 FastAPI runtime boot。"""
        import ast
        with open('src/data/proxy/nas_server.py', encoding='utf-8') as f:
            ast.parse(f.read())


if __name__ == "__main__":
    unittest.main()
