"""v19.75 — 外部 review B/D 類收斂守衛測試(user 2026-07-10 核准「B+C+D 請繼續」)。

B5 監控盲區:籌碼集中度 / 股本 / 5年現金流量允當比率 登錄 data_registry
D13 月營收 pandera log-mode → blocking(schema 違反整檔棄用,§1 錯值比缺值危險)
D14b cache dir 可攜化(/tmp/stock_cache 寫死 → env + tempfile.gettempdir())
D14c 月營收無 token 靜默回空 → 補 log
"""
from __future__ import annotations

import types
import unittest

import pandas as pd


# ═══════════════════════════════════════════════════════════════
# D13 validate_or_reject(blocking 驗證)
# ═══════════════════════════════════════════════════════════════
class TestValidateOrReject(unittest.TestCase):

    def _good_df(self):
        return pd.DataFrame({
            'date': pd.date_range('2025-01-01', periods=6, freq='MS'),
            'revenue': pd.array([1e9, 1.1e9, 0.9e9, 1.2e9, float('nan'), 1.3e9],
                                dtype='float64'),
        })

    def test_good_df_passes_through(self):
        from shared.schemas import MonthlyRevenueSchema, validate_or_reject
        df = self._good_df()
        out = validate_or_reject(df, MonthlyRevenueSchema, label='t')
        self.assertEqual(len(out), 6, '合法 df(含 NaN 停業態)不得誤殺')

    def test_negative_revenue_rejected_whole(self):
        """負營收(schema 違反)→ 整檔棄用回空,不是丟壞列(§1 部分刪列 = 掩蓋)。"""
        from shared.schemas import MonthlyRevenueSchema, validate_or_reject
        df = self._good_df()
        df.loc[2, 'revenue'] = -5.0
        out = validate_or_reject(df, MonthlyRevenueSchema, label='t')
        self.assertTrue(out.empty)
        self.assertListEqual(list(out.columns), list(df.columns), '空殼須保留欄位')

    def test_unsorted_date_rejected(self):
        from shared.schemas import MonthlyRevenueSchema, validate_or_reject
        df = self._good_df().iloc[::-1].reset_index(drop=True)  # 降序
        out = validate_or_reject(df, MonthlyRevenueSchema, label='t')
        self.assertTrue(out.empty)

    def test_empty_df_passthrough(self):
        from shared.schemas import MonthlyRevenueSchema, validate_or_reject
        out = validate_or_reject(pd.DataFrame(), MonthlyRevenueSchema, label='t')
        self.assertTrue(out.empty)


# ═══════════════════════════════════════════════════════════════
# D13/D14c 月營收 fetcher:dtype 強轉 + blocking 接線 + no-token log
# ═══════════════════════════════════════════════════════════════
class TestMonthlyRevenueFetcherBlocking(unittest.TestCase):

    def test_int_revenue_coerced_to_float_and_survives(self):
        """FinMind 整數營收(int64)→ 強轉 float64,blocking 驗證不誤殺
        (Fund repo v19.172 FRED 全整數 series 同型教訓)。"""
        import src.data.stock.monthly_revenue_fetcher as m

        _orig_get, _orig_tok = m.finmind_get, m._get_token
        try:
            m._get_token = lambda: 'tok'
            m.finmind_get = lambda *a, **k: pd.DataFrame({
                'date': ['2025-01-01', '2025-02-01', '2025-03-01'],
                'revenue': [100, 200, 300],  # int → 原始 int64
            })
            out = m.fetch_monthly_revenue('9997', months=17)
            self.assertEqual(len(out), 3, 'int64 營收不得被 blocking 誤殺')
            self.assertEqual(str(out['revenue'].dtype), 'float64')
        finally:
            m.finmind_get, m._get_token = _orig_get, _orig_tok

    def test_bad_shape_rejected_to_empty(self):
        """負營收 → blocking 整檔棄用,caller 拿到空 df(走既有無資料路徑)。"""
        import src.data.stock.monthly_revenue_fetcher as m

        _orig_get, _orig_tok = m.finmind_get, m._get_token
        try:
            m._get_token = lambda: 'tok'
            m.finmind_get = lambda *a, **k: pd.DataFrame({
                'date': ['2025-01-01', '2025-02-01'],
                'revenue': [100.0, -999.0],  # 負值違反 schema
            })
            out = m.fetch_monthly_revenue('9996', months=16)
            self.assertTrue(out.empty, 'schema 違反須整檔棄用')
        finally:
            m.finmind_get, m._get_token = _orig_get, _orig_tok

    def test_no_token_logs_not_silent(self):
        """無 token → 回空且 stdout 有跡可循(D14c,§5 可觀測性)。"""
        import contextlib
        import io

        import src.data.stock.monthly_revenue_fetcher as m
        _orig_tok = m._get_token
        try:
            m._get_token = lambda: ''
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                out = m.fetch_monthly_revenue('9995', months=15)
            self.assertTrue(out.empty)
            self.assertIn('無 FinMind token', buf.getvalue())
        finally:
            m._get_token = _orig_tok


# ═══════════════════════════════════════════════════════════════
# B5 data_registry 盲區登錄
# ═══════════════════════════════════════════════════════════════
class TestRegistryBlindSpots(unittest.TestCase):

    def _run_scanner(self, session: dict) -> dict:
        import src.services.data_registry_scanner as sc
        _orig_st = sc.st
        try:
            sc.st = types.SimpleNamespace(session_state=session)
            sc.scan_and_write_data_registry(intl_map={}, tw_map={}, tech_map={})
            return session.get('data_registry', {})
        finally:
            sc.st = _orig_st

    def test_chip_concentration_registered(self):
        reg = self._run_scanner({'chip_conc_meta': {
            'sid': '2330', 'rows': 26, 'last_date': '2026-07-04'}})
        e = reg.get('[個股] 2330 | 籌碼集中度')
        self.assertIsNotNone(e, '籌碼集中度應登錄 registry')
        self.assertEqual(e['rows'], 26)
        self.assertEqual(e['frequency'], 'weekly')
        self.assertEqual(e['last_updated'], '2026-07-04')

    def test_chip_concentration_failure_shows_missing(self):
        reg = self._run_scanner({'chip_conc_meta': {
            'sid': '2330', 'rows': 0, 'last_date': 'N/A'}})
        e = reg.get('[個股] 2330 | 籌碼集中度')
        self.assertIsNotNone(e)
        self.assertTrue(e.get('missing'), '抓失敗須亮 missing(紅燈可見)')

    def test_share_capital_registered_and_missing(self):
        reg_ok = self._run_scanner({'t2_xsec_meta': {'sid': '2330', 'capital': 259.3}})
        self.assertFalse(reg_ok.get('[個股] 2330 | 股本', {}).get('missing', False))
        reg_bad = self._run_scanner({'t2_xsec_meta': {'sid': '2330', 'capital': 0.0}})
        self.assertTrue(reg_bad.get('[個股] 2330 | 股本', {}).get('missing'),
                        'fetcher 失敗回 0.0 須登 missing')

    def test_b_item_5y_registered_from_fin_raw_stash(self):
        reg = self._run_scanner({
            't2_data': {'sid': '2330', 'name': '台積電'},
            '_fin_raw_2330': {'b_item_5y': {'status': 'ok', 'years': 5, 'ratio': 87.2}},
        })
        e = reg.get('[個股] 2330 | 5年現金流量允當比率')
        self.assertIsNotNone(e)
        self.assertEqual(e['rows'], 5)
        self.assertEqual(e['frequency'], 'yearly')

    def test_b_item_5y_insufficient_shows_missing(self):
        reg = self._run_scanner({
            't2_data': {'sid': '2330', 'name': '台積電'},
            '_fin_raw_2330': {'b_item_5y': {'status': 'insufficient_data'}},
        })
        self.assertTrue(
            reg.get('[個股] 2330 | 5年現金流量允當比率', {}).get('missing'))

    def test_not_registered_when_never_fetched(self):
        """未查過該股 → 不登錄(避免固定清單膨脹)。"""
        reg = self._run_scanner({})
        self.assertFalse(any('籌碼集中度' in k or '股本' in k
                             or '5年現金流量' in k for k in reg))


# ═══════════════════════════════════════════════════════════════
# D14b cache dir 可攜(源碼守衛)
# ═══════════════════════════════════════════════════════════════
class TestPortableCacheDir(unittest.TestCase):

    def test_no_hardcoded_tmp_stock_cache_left(self):
        """production 代碼不得再寫死 '/tmp/stock_cache' / '/tmp/_adl_log.txt'
        (統一 env STK_PKL_DIR + tempfile.gettempdir();Linux 結果不變)。"""
        import pathlib
        offenders = []
        root = pathlib.Path('.')
        for base in ('src', 'shared'):
            for f in (root / base).rglob('*.py'):
                txt = f.read_text(encoding='utf-8')
                for bad in ("'/tmp/stock_cache", "'/tmp/_adl_log.txt'"):
                    for i, line in enumerate(txt.splitlines(), 1):
                        if bad in line and not line.strip().startswith('#'):
                            offenders.append(f'{f}:{i}')
        self.assertFalse(offenders, '殘留寫死路徑:\n' + '\n'.join(offenders))

    def test_pkl_dir_linux_value_unchanged(self):
        """Linux(部署環境)上可攜寫法結果須仍為 /tmp/stock_cache(行為 0 變)。"""
        import os
        import tempfile
        if os.environ.get('STK_PKL_DIR'):
            self.skipTest('env 覆寫中,略過預設值驗證')
        from shared.cache_layer import _PKL_DIR
        self.assertEqual(_PKL_DIR, os.path.join(tempfile.gettempdir(), 'stock_cache'))


if __name__ == '__main__':
    unittest.main()
