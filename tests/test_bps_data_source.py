"""v18.174 P/B 股價淨值比資料源修正測試 — data_loader.fetch_bps / fetch_bps_from_finmind。

v18.326 更新:這兩個 fetcher 已從 tab_stock.py 私有版本下沉到 data_loader.py(L1)
作為 public SSOT,供個股 Tab + 組合 Tab 共用。本測試對應改 import 來源。

驗證重點：
1. 公式正確性：BPS = 股東權益總額 ÷ (普通股股本 ÷ 10)
2. FinMind PRIMARY 命中 → 回 FinMind 值，不打 yfinance
3. FinMind 失敗 / 0 → fallback 到 yfinance bookValue
4. 全失敗 → 0.0
5. Sanity 守門：BPS 範圍 (0.1, 5000) 外回 0.0
6. 多季資料只取最新 date
7. 父子科目辨識：避免抓到子科目「特別股股本」當作普通股股本
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _stub_streamlit_cache(monkeypatch):
    """讓 @st.cache_data decorator 變成 no-op，避免測試間 cache 串擾。"""
    from src.data.core import data_loader
    monkeypatch.setattr(data_loader.fetch_bps_from_finmind, 'clear', lambda: None,
                         raising=False)
    monkeypatch.setattr(data_loader.fetch_bps, 'clear', lambda: None, raising=False)
    try:
        data_loader.fetch_bps_from_finmind.clear()
        data_loader.fetch_bps.clear()
    except Exception:
        pass
    yield
    try:
        data_loader.fetch_bps_from_finmind.clear()
        data_loader.fetch_bps.clear()
    except Exception:
        pass


def _mk_finmind_resp(rows: list[dict]) -> MagicMock:
    """模擬 FinMind /api/v4/data 回應。"""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {'data': rows}
    return resp


# ════════════════════════════════════════════════════════════════════
# §1 公式正確性：BPS = 股東權益 / (股本/10)
# ════════════════════════════════════════════════════════════════════
class TestBpsFormula:
    def test_tsmc_like_realistic_values(self):
        """模擬類 TSMC：股東權益 3.5 兆元 / 股本 2,593 億 → BPS ≈ 135 元。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'TotalEquity',
             'origin_name': '股東權益總額', 'value': '3500000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '259300000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_TSMC_1001')
        assert 130.0 < bps < 140.0, f"expected ~135, got {bps}"

    def test_financial_stock_like_low_pb(self):
        """模擬金融股：股東權益 1 兆元 / 股本 800 億 → BPS = 125 元。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'StockholdersEquity',
             'origin_name': '股東權益合計', 'value': '1000000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '80000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_FIN_1002')
        assert 120.0 < bps < 130.0


# ════════════════════════════════════════════════════════════════════
# §2 PRIMARY/FALLBACK 鏈
# ════════════════════════════════════════════════════════════════════
class TestPrimaryFallback:
    def test_finmind_primary_skips_yfinance(self):
        """FinMind 有資料 → 不打 yfinance。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '500000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '50000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)), \
             patch('yfinance.Ticker') as _yf_mock:
            bps = data_loader.fetch_bps('T_PRIM_2001')
            _yf_mock.assert_not_called()
        assert 95.0 < bps < 105.0

    def test_finmind_empty_falls_back_to_yfinance(self):
        """FinMind 回空 → yfinance fallback。"""
        from src.data.core import data_loader
        empty_resp = _mk_finmind_resp([])
        fake_yf_info = {'bookValue': 88.5}
        fake_ticker = MagicMock()
        fake_ticker.info = fake_yf_info
        with patch('requests.get', return_value=empty_resp), \
             patch('yfinance.Ticker', return_value=fake_ticker):
            bps = data_loader.fetch_bps('T_FBYF_2002')
        assert bps == 88.5

    def test_all_sources_fail_returns_zero(self):
        """FinMind + yfinance 都失敗 → 0.0（call site 用 if bps > 0 守門）。"""
        from src.data.core import data_loader
        empty_resp = _mk_finmind_resp([])
        fake_ticker = MagicMock()
        fake_ticker.info = {}
        with patch('requests.get', return_value=empty_resp), \
             patch('yfinance.Ticker', return_value=fake_ticker):
            bps = data_loader.fetch_bps('T_ZERO_2003')
        assert bps == 0.0


# ════════════════════════════════════════════════════════════════════
# §3 Sanity 守門：BPS 範圍 (0.1, 5000) 外回 0
# ════════════════════════════════════════════════════════════════════
class TestSanityGuard:
    def test_absurdly_high_bps_returns_zero(self):
        """異常高 BPS（如資料單位錯抓成元誤算成千元）→ 0.0 守住。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '3500000000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '259300000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_HIBPS_3001')
        assert bps == 0.0

    def test_absurdly_low_bps_returns_zero(self):
        """異常低 BPS（< 0.1）→ 0.0。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '100'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '50000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_LOBPS_3002')
        assert bps == 0.0


# ════════════════════════════════════════════════════════════════════
# §4 多季資料 → 只取最新 date
# ════════════════════════════════════════════════════════════════════
class TestLatestQuarterOnly:
    def test_picks_latest_date_only(self):
        """提供 3 季資料 → 只用最新一季（Q1 2026）算。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2025-09-30', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '900000000000'},
            {'date': '2025-09-30', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '1200000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
            {'date': '2025-12-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '1050000000000'},
            {'date': '2025-12-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_LATEST_4001')
        assert 118.0 < bps < 122.0


# ════════════════════════════════════════════════════════════════════
# §5 父子科目辨識：避免「特別股股本」干擾
# ════════════════════════════════════════════════════════════════════
class TestFieldDisambiguation:
    def test_skips_preferred_stock(self):
        """特別股股本不應被誤抓為普通股股本。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '1000000000000'},
            {'date': '2026-03-31', 'type': 'PreferredStock',
             'origin_name': '特別股股本', 'value': '5000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_PREF_5001')
        assert 98.0 < bps < 102.0

    def test_total_equity_preferred_over_substaff(self):
        """有「股東權益總額」科目時正確識別。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'TotalEquity',
             'origin_name': '股東權益總額', 'value': '2000000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_TOTEQ_5002')
        assert 195.0 < bps < 205.0


# ════════════════════════════════════════════════════════════════════
# §6 防呆：HTTP 失敗 / malformed
# ════════════════════════════════════════════════════════════════════
class TestDefensive:
    def test_http_500_returns_zero(self):
        from src.data.core import data_loader
        bad_resp = MagicMock()
        bad_resp.status_code = 500
        bad_resp.json.return_value = {}
        with patch('requests.get', return_value=bad_resp), \
             patch('yfinance.Ticker', return_value=MagicMock(info={})):
            bps = data_loader.fetch_bps('T_HTTP500_6001')
        assert bps == 0.0

    def test_missing_equity_field_returns_zero(self):
        """有股本但無股東權益 → 算不出 BPS → 0.0。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_NOEQ_6002')
        assert bps == 0.0

    def test_missing_common_stock_returns_zero(self):
        """有股東權益但無股本 → 算不出流通股數 → 0.0。"""
        from src.data.core import data_loader
        rows = [
            {'date': '2026-03-31', 'type': 'TotalEquity',
             'origin_name': '股東權益總額', 'value': '1000000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = data_loader.fetch_bps_from_finmind('T_NOCS_6003')
        assert bps == 0.0
