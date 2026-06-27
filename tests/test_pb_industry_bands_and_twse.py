"""v18.175 P/B 升級測試 — TWSE PBratio PRIMARY + 產業別動態閾值。

v18.326 更新:_get_pb_bands / _pb_bands_label / _fetch_industry_category /
_fetch_bps_from_finmind / _fetch_bps 已從 tab_stock.py 私有版本下沉到 SSOT:
- get_pb_bands / pb_bands_label → shared.stock_buckets
- fetch_industry_category / fetch_bps / fetch_bps_from_finmind → data_loader
本測試對應更新 import 來源。`_fetch_pbratio_from_twse` 仍為 tab_stock.py 私有。

驗證重點：
1. TWSE PBratio 抓取 + sanity 範圍 (0.01, 100)
2. 產業別閾值映射：金融 / 成長科技 / 製造 default
3. 產業類別 fetcher：FinMind TaiwanStockInfo industry_category
4. 產業 label：caption 顯示用字串
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_caches():
    """每個 case 前後清快取，避免 streamlit cache_data 串擾。"""
    import data_loader
    import tab_stock
    try:
        tab_stock._fetch_pbratio_from_twse.clear()
    except Exception:
        pass
    for _fn in ('fetch_industry_category', 'fetch_bps_from_finmind', 'fetch_bps'):
        try:
            getattr(data_loader, _fn).clear()
        except Exception:
            pass
    yield
    try:
        tab_stock._fetch_pbratio_from_twse.clear()
    except Exception:
        pass
    for _fn in ('fetch_industry_category', 'fetch_bps_from_finmind', 'fetch_bps'):
        try:
            getattr(data_loader, _fn).clear()
        except Exception:
            pass


def _mk_twse_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _mk_finmind_resp(rows: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {'data': rows}
    return resp


# ════════════════════════════════════════════════════════════════════
# §1 TWSE PBratio 抓取
# ════════════════════════════════════════════════════════════════════
class TestTwsePbratioFetch:
    def test_finds_target_stock(self):
        import tab_stock
        df = _mk_twse_df([
            {'代碼': '2330', '名稱': '台積電', '股價淨值比': 5.5},
            {'代碼': '2317', '名稱': '鴻海', '股價淨值比': 1.2},
        ])
        with patch('yield_screener.fetch_twse_yield_pe', return_value=df):
            pb = tab_stock._fetch_pbratio_from_twse('2330')
        assert abs(pb - 5.5) < 0.01

    def test_target_not_found_returns_zero(self):
        import tab_stock
        df = _mk_twse_df([{'代碼': '2330', '名稱': '台積電', '股價淨值比': 5.5}])
        with patch('yield_screener.fetch_twse_yield_pe', return_value=df):
            pb = tab_stock._fetch_pbratio_from_twse('9999')
        assert pb == 0.0

    def test_high_pb_passes_sanity(self):
        import tab_stock
        df = _mk_twse_df([{'代碼': '2330', '名稱': '台積電', '股價淨值比': 50.0}])
        with patch('yield_screener.fetch_twse_yield_pe', return_value=df):
            pb = tab_stock._fetch_pbratio_from_twse('2330')
        assert abs(pb - 50.0) < 0.01

    def test_absurd_pb_returns_zero(self):
        import tab_stock
        df = _mk_twse_df([{'代碼': '2330', '名稱': '台積電', '股價淨值比': 200.0}])
        with patch('yield_screener.fetch_twse_yield_pe', return_value=df):
            pb = tab_stock._fetch_pbratio_from_twse('2330')
        assert pb == 0.0

    def test_negative_pb_returns_zero(self):
        import tab_stock
        df = _mk_twse_df([{'代碼': '2330', '名稱': '台積電', '股價淨值比': -1.0}])
        with patch('yield_screener.fetch_twse_yield_pe', return_value=df):
            pb = tab_stock._fetch_pbratio_from_twse('2330')
        assert pb == 0.0

    def test_empty_df_returns_zero(self):
        import tab_stock
        with patch('yield_screener.fetch_twse_yield_pe', return_value=pd.DataFrame()):
            pb = tab_stock._fetch_pbratio_from_twse('2330')
        assert pb == 0.0


# ════════════════════════════════════════════════════════════════════
# §2 產業別閾值映射(SSOT: shared.stock_buckets)
# ════════════════════════════════════════════════════════════════════
class TestIndustryBands:
    def test_financial_bank(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('銀行業') == (0.5, 0.9, 1.2)

    def test_financial_insurance(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('金融保險業') == (0.5, 0.9, 1.2)

    def test_growth_semiconductor(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('半導體業') == (1.5, 2.5, 4.0)

    def test_growth_electronics(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('電子工業') == (1.5, 2.5, 4.0)

    def test_growth_optoelectronics(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('光電業') == (1.5, 2.5, 4.0)

    def test_mfg_default(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('鋼鐵工業') == (0.8, 1.5, 2.5)

    def test_empty_industry_uses_mfg_default(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('') == (0.8, 1.5, 2.5)
        assert get_pb_bands(None) == (0.8, 1.5, 2.5)

    def test_unknown_industry_uses_mfg_default(self):
        from shared.stock_buckets import get_pb_bands
        assert get_pb_bands('外星科技業') == (0.8, 1.5, 2.5)


# ════════════════════════════════════════════════════════════════════
# §3 產業 label 顯示字串(SSOT: shared.stock_buckets)
# ════════════════════════════════════════════════════════════════════
class TestIndustryLabel:
    def test_financial_label(self):
        from shared.stock_buckets import pb_bands_label
        assert '金融' in pb_bands_label('銀行業')

    def test_growth_label(self):
        from shared.stock_buckets import pb_bands_label
        assert '成長科技' in pb_bands_label('半導體業')

    def test_mfg_label(self):
        from shared.stock_buckets import pb_bands_label
        assert '製造業' in pb_bands_label('鋼鐵工業')

    def test_empty_falls_back_to_mfg_default(self):
        from shared.stock_buckets import pb_bands_label
        assert pb_bands_label('') == '製造業預設'


# ════════════════════════════════════════════════════════════════════
# §4 產業類別 fetcher(SSOT: data_loader)
# ════════════════════════════════════════════════════════════════════
class TestFetchIndustryCategory:
    def test_extracts_industry_from_finmind(self):
        import data_loader
        rows = [{'stock_id': '2330', 'industry_category': '半導體業',
                  'stock_name': '台積電'}]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            ind = data_loader.fetch_industry_category('IC_TST_8001')
        assert ind == '半導體業'

    def test_empty_data_returns_empty_string(self):
        import data_loader
        with patch('requests.get', return_value=_mk_finmind_resp([])):
            ind = data_loader.fetch_industry_category('IC_TST_8002')
        assert ind == ''

    def test_no_industry_field_returns_empty(self):
        import data_loader
        rows = [{'stock_id': '2330', 'stock_name': '台積電'}]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            ind = data_loader.fetch_industry_category('IC_TST_8003')
        assert ind == ''

    def test_http_500_returns_empty(self):
        import data_loader
        bad_resp = MagicMock()
        bad_resp.status_code = 500
        bad_resp.json.return_value = {}
        with patch('requests.get', return_value=bad_resp):
            ind = data_loader.fetch_industry_category('IC_TST_8004')
        assert ind == ''


# ════════════════════════════════════════════════════════════════════
# §5 整合：TWSE → BPS 反推
# ════════════════════════════════════════════════════════════════════
class TestTwseBpsBackCalc:
    def test_back_calc_bps_from_pbratio_and_price(self):
        """模擬：TWSE PBratio=5.0、股價=750 → BPS 反推 = 150。"""
        import tab_stock
        df = _mk_twse_df([{'代碼': '2330', '名稱': '台積電', '股價淨值比': 5.0}])
        with patch('yield_screener.fetch_twse_yield_pe', return_value=df):
            pb = tab_stock._fetch_pbratio_from_twse('2330')
        bps = 750.0 / pb if pb > 0 else 0
        assert 149.0 < bps < 151.0
