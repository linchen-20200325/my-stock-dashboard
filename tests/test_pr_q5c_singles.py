"""v18.357 PR-Q5c — 8 single-use fetcher 收尾,phase 19 全套收齊。

8 fetcher 各 1 個檔(每檔小量 edit):
- macro_snapshot.fetch_vix_block (dict)
- chip_radar.fetch_chip_concentration (dict stderr)
- ~~update_etf_managers.fetch_manager~~(Issue #1208 2026-11-17 客戶取消 ETF 經理人換手策略,腳本已刪)
- market_strategy.fetch_market_data (dict source/fetched_at)
- hot_money.fetch_foreign_flow_series (DataFrame attrs)
- risk_radar._fetch_cboe_csv (Series attrs)
- tab_edu._fetch_fred_series_edu (Series attrs)
- ~~tab_etf_margin_simulator._fetch_etf_history~~(整功能棧 v19.159 團隊稽核真刪,見 docs/ARCHIVED_FEATURES.md)

phase 19 累計 50+8 = 58 fetcher 全套清完(其中 etf_margin 段已隨孤兒功能退役)。
"""
from __future__ import annotations

import unittest


class TestQ5cMarkers(unittest.TestCase):

    @staticmethod
    def _read(p):
        with open(p, encoding='utf-8') as f:
            return f.read()

    def test_macro_snapshot_vix(self):
        src = self._read('src/data/macro/macro_snapshot.py')  # P1-2 v18.373:搬到 L1
        self.assertIn("'source': 'yfinance:^VIX:3mo:1d'", src)

    def test_chip_radar(self):
        # v18.426 Phase 2 Batch 3b:fetch_chip_concentration 下沉至 L1
        # src/data/stock/chip_concentration_fetcher.py(原 chip_radar.py:180 為 R-UI-FETCH-2 違憲)
        src = self._read('src/data/stock/chip_concentration_fetcher.py')
        self.assertIn('[fetch_chip_concentration]', src)
        self.assertIn('norway.twsthr.info', src)

    # test_update_etf_managers(source marker)已移除:scripts/update_etf_managers.py
    # 隨 Issue #1208(客戶取消 ETF 經理人換手策略)刪除;反向守衛見
    # tests/test_issue1208_manager_strategy_removed.py。

    def test_market_strategy(self):
        src = self._read('src/services/market_strategy.py')
        self.assertIn("'source': 'tw_macro.fetch_finmind_foreign_investor'", src)

    def test_hot_money(self):
        # v18.425 Phase 2 Batch 3a:fetch_foreign_flow_series 下沉至 L1
        # src/data/macro/foreign_flow_fetcher.py(原 hot_money.py:135 為 R-UI-FETCH-1 違憲)
        src = self._read('src/data/macro/foreign_flow_fetcher.py')
        self.assertIn('FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign', src)

    def test_risk_radar(self):
        src = self._read('src/compute/risk/risk_radar.py')
        self.assertIn("'CBOE:{short_name}_History.csv'", src) or self.assertIn(
            'CBOE:', src)

    def test_tab_edu(self):
        src = self._read('src/ui/tabs/tab_edu.py')
        self.assertIn("'FRED:{series_id}:units={units}:months={months}'", src)

    # test_tab_etf_margin_simulator(source marker)已移除:整功能棧 v19.159 團隊稽核真刪
    # (fetch_etf_close_history 隨孤兒 UI 一併刪,見 docs/ARCHIVED_FEATURES.md)


class TestImports(unittest.TestCase):

    def test_macro_snapshot(self):
        from src.data.macro import macro_snapshot  # noqa  # P1-2 v18.373:搬到 L1

    def test_chip_radar(self):
        from src.ui.tabs import chip_radar  # noqa

    # test_update_etf_managers(import)已移除:腳本隨 Issue #1208 刪除。

    def test_market_strategy(self):
        from src.services import market_strategy  # noqa

    def test_hot_money(self):
        from src.ui.tabs import hot_money  # noqa

    def test_risk_radar(self):
        from src.compute.risk import risk_radar  # noqa

    def test_tab_edu(self):
        from src.ui.tabs import tab_edu  # noqa

    # test_tab_etf_margin_simulator(import)已移除:孤兒 UI v19.159 真刪


if __name__ == "__main__":
    unittest.main()
