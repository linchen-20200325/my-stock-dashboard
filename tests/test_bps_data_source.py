"""v18.174 P/B 股價淨值比資料源修正測試 — tab_stock._fetch_bps / _fetch_bps_from_finmind。

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


# tab_stock 是 streamlit-heavy 模組，需要先 stub st 才能 import
# 我們直接 import 兩個目標函式進行單元測試
@pytest.fixture(autouse=True)
def _stub_streamlit_cache(monkeypatch):
    """讓 @st.cache_data decorator 變成 no-op，避免測試間 cache 串擾。"""
    import tab_stock
    # 把 cache_data 包成穿透 wrapper（直接呼叫底層函式）
    monkeypatch.setattr(tab_stock._fetch_bps_from_finmind, 'clear', lambda: None,
                         raising=False)
    monkeypatch.setattr(tab_stock._fetch_bps, 'clear', lambda: None, raising=False)
    # 清快取避免 case 之間互相污染
    try:
        tab_stock._fetch_bps_from_finmind.clear()
        tab_stock._fetch_bps.clear()
    except Exception:
        pass
    yield
    try:
        tab_stock._fetch_bps_from_finmind.clear()
        tab_stock._fetch_bps.clear()
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
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'TotalEquity',
             'origin_name': '股東權益總額', 'value': '3500000000000'},  # 3.5 兆
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '259300000000'},  # 2,593 億
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_TSMC_1001')
        # BPS = 3.5T / (259.3B / 10) = 3.5T / 25.93B = 135.0
        assert 130.0 < bps < 140.0, f"expected ~135, got {bps}"

    def test_financial_stock_like_low_pb(self):
        """模擬金融股：股東權益 1 兆元 / 股本 800 億 → BPS = 125 元。"""
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'StockholdersEquity',
             'origin_name': '股東權益合計', 'value': '1000000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '80000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_FIN_1002')
        # BPS = 1T / (80B / 10) = 1T / 8B = 125.0
        assert 120.0 < bps < 130.0


# ════════════════════════════════════════════════════════════════════
# §2 PRIMARY/FALLBACK 鏈
# ════════════════════════════════════════════════════════════════════
class TestPrimaryFallback:
    def test_finmind_primary_skips_yfinance(self):
        """FinMind 有資料 → 不打 yfinance。"""
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '500000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '50000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)), \
             patch('yfinance.Ticker') as _yf_mock:
            bps = tab_stock._fetch_bps('T_PRIM_2001')
            _yf_mock.assert_not_called()
        # BPS = 500B / (50B/10) = 100.0
        assert 95.0 < bps < 105.0

    def test_finmind_empty_falls_back_to_yfinance(self):
        """FinMind 回空 → yfinance fallback。"""
        import tab_stock
        empty_resp = _mk_finmind_resp([])
        fake_yf_info = {'bookValue': 88.5}
        fake_ticker = MagicMock()
        fake_ticker.info = fake_yf_info
        with patch('requests.get', return_value=empty_resp), \
             patch('yfinance.Ticker', return_value=fake_ticker):
            bps = tab_stock._fetch_bps('T_FBYF_2002')
        assert bps == 88.5

    def test_all_sources_fail_returns_zero(self):
        """FinMind + yfinance 都失敗 → 0.0（call site 用 if bps > 0 守門）。"""
        import tab_stock
        empty_resp = _mk_finmind_resp([])
        fake_ticker = MagicMock()
        fake_ticker.info = {}
        with patch('requests.get', return_value=empty_resp), \
             patch('yfinance.Ticker', return_value=fake_ticker):
            bps = tab_stock._fetch_bps('T_ZERO_2003')
        assert bps == 0.0


# ════════════════════════════════════════════════════════════════════
# §3 Sanity 守門：BPS 範圍 (0.1, 5000) 外回 0
# ════════════════════════════════════════════════════════════════════
class TestSanityGuard:
    def test_absurdly_high_bps_returns_zero(self):
        """異常高 BPS（如資料單位錯抓成元誤算成千元）→ 0.0 守住。"""
        import tab_stock
        # 故意把 equity 放千倍 → BPS 會破萬
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '3500000000000000'},  # 3.5 千兆
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '259300000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_HIBPS_3001')
        assert bps == 0.0  # sanity 擋下

    def test_absurdly_low_bps_returns_zero(self):
        """異常低 BPS（< 0.1）→ 0.0。"""
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '100'},  # 太小
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '50000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_LOBPS_3002')
        # BPS = 100/(5B) ≈ 2e-8 → 守門擋下
        assert bps == 0.0


# ════════════════════════════════════════════════════════════════════
# §4 多季資料 → 只取最新 date
# ════════════════════════════════════════════════════════════════════
class TestLatestQuarterOnly:
    def test_picks_latest_date_only(self):
        """提供 3 季資料 → 只用最新一季（Q1 2026）算。"""
        import tab_stock
        rows = [
            # Q3 2025（舊）
            {'date': '2025-09-30', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '900000000000'},
            {'date': '2025-09-30', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
            # Q1 2026（最新）
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '1200000000000'},  # 用這個
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
            # Q4 2025（中間）
            {'date': '2025-12-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '1050000000000'},
            {'date': '2025-12-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_LATEST_4001')
        # Q1 2026: 1.2T / (100B / 10) = 120
        assert 118.0 < bps < 122.0


# ════════════════════════════════════════════════════════════════════
# §5 父子科目辨識：避免「特別股股本」干擾
# ════════════════════════════════════════════════════════════════════
class TestFieldDisambiguation:
    def test_skips_preferred_stock(self):
        """特別股股本不應被誤抓為普通股股本。"""
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'Equity',
             'origin_name': '股東權益總額', 'value': '1000000000000'},
            {'date': '2026-03-31', 'type': 'PreferredStock',
             'origin_name': '特別股股本', 'value': '5000000000'},  # 不該抓
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},  # 該抓
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_PREF_5001')
        # 應使用普通股 100B 算：BPS = 1T / (100B/10) = 100
        assert 98.0 < bps < 102.0

    def test_total_equity_preferred_over_substaff(self):
        """有「股東權益總額」科目時正確識別。"""
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'TotalEquity',
             'origin_name': '股東權益總額', 'value': '2000000000000'},
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_TOTEQ_5002')
        # BPS = 2T / 10B = 200
        assert 195.0 < bps < 205.0


# ════════════════════════════════════════════════════════════════════
# §6 防呆：HTTP 失敗 / malformed
# ════════════════════════════════════════════════════════════════════
class TestDefensive:
    def test_http_500_returns_zero(self):
        import tab_stock
        bad_resp = MagicMock()
        bad_resp.status_code = 500
        bad_resp.json.return_value = {}
        with patch('requests.get', return_value=bad_resp), \
             patch('yfinance.Ticker', return_value=MagicMock(info={})):
            bps = tab_stock._fetch_bps('T_HTTP500_6001')
        assert bps == 0.0

    def test_missing_equity_field_returns_zero(self):
        """有股本但無股東權益 → 算不出 BPS → 0.0。"""
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'CommonStock',
             'origin_name': '普通股股本', 'value': '100000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_NOEQ_6002')
        assert bps == 0.0

    def test_missing_common_stock_returns_zero(self):
        """有股東權益但無股本 → 算不出流通股數 → 0.0。"""
        import tab_stock
        rows = [
            {'date': '2026-03-31', 'type': 'TotalEquity',
             'origin_name': '股東權益總額', 'value': '1000000000000'},
        ]
        with patch('requests.get', return_value=_mk_finmind_resp(rows)):
            bps = tab_stock._fetch_bps_from_finmind('T_NOCS_6003')
        assert bps == 0.0
