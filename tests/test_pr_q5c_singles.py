"""v18.357 PR-Q5c — 8 single-use fetcher 收尾,phase 19 全套收齊。

8 fetcher 各 1 個檔(每檔小量 edit):
- macro_snapshot.fetch_vix_block (dict)
- chip_radar.fetch_chip_concentration (dict stderr)
- update_etf_managers.fetch_manager (dict stderr)
- market_strategy.fetch_market_data (dict source/fetched_at)
- hot_money.fetch_foreign_flow_series (DataFrame attrs)
- risk_radar._fetch_cboe_csv (Series attrs)
- tab_edu._fetch_fred_series_edu (Series attrs)
- tab_etf_margin_simulator._fetch_etf_history (Series attrs)

phase 19 累計 50+8 = 58 fetcher 全套清完。
"""
from __future__ import annotations

import unittest


class TestQ5cMarkers(unittest.TestCase):

    @staticmethod
    def _read(p):
        with open(p, encoding='utf-8') as f:
            return f.read()

    def test_macro_snapshot_vix(self):
        src = self._read('src/ui/render/macro_snapshot.py')
        self.assertIn("'source': 'yfinance:^VIX:3mo:1d'", src)

    def test_chip_radar(self):
        src = self._read('src/ui/tabs/chip_radar.py')
        self.assertIn('[fetch_chip_concentration]', src)
        self.assertIn('norway.twsthr.info', src)

    def test_update_etf_managers(self):
        # v18.359 F-2 update_etf_managers.py 已搬入 scripts/
        src = self._read('scripts/update_etf_managers.py')
        self.assertIn('[fetch_manager]', src)
        self.assertIn('MoneyDJ:Basic(multi-page)', src)

    def test_market_strategy(self):
        src = self._read('src/services/market_strategy.py')
        self.assertIn("'source': 'tw_macro.fetch_finmind_foreign_investor'", src)

    def test_hot_money(self):
        src = self._read('src/ui/tabs/hot_money.py')
        self.assertIn('FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign', src)

    def test_risk_radar(self):
        src = self._read('src/compute/risk/risk_radar.py')
        self.assertIn("'CBOE:{short_name}_History.csv'", src) or self.assertIn(
            'CBOE:', src)

    def test_tab_edu(self):
        src = self._read('src/ui/tabs/tab_edu.py')
        self.assertIn("'FRED:{series_id}:units={units}:months={months}'", src)

    def test_tab_etf_margin_simulator(self):
        src = self._read('src/ui/tabs/tab_etf_margin_simulator.py')
        self.assertIn("'yfinance:{symbol}:{years}y:auto_adjust'", src)


class TestImports(unittest.TestCase):

    def test_macro_snapshot(self):
        from src.ui.render import macro_snapshot  # noqa

    def test_chip_radar(self):
        from src.ui.tabs import chip_radar  # noqa

    def test_update_etf_managers(self):
        from scripts import update_etf_managers  # noqa

    def test_market_strategy(self):
        from src.services import market_strategy  # noqa

    def test_hot_money(self):
        from src.ui.tabs import hot_money  # noqa

    def test_risk_radar(self):
        from src.compute.risk import risk_radar  # noqa

    def test_tab_edu(self):
        from src.ui.tabs import tab_edu  # noqa

    def test_tab_etf_margin_simulator(self):
        from src.ui.tabs import tab_etf_margin_simulator  # noqa


if __name__ == "__main__":
    unittest.main()
