"""tests/test_app_stock_fetchers_coverage.py — L1 fetcher smoke + pure helpers.

Target: src/data/stock/app_stock_fetchers.py (kind: fetcher, §8.2 L1 Data).

涵蓋範圍(NO network):
- import smoke + 5 fetcher callable
- `_get_finmind_token()` graceful：無 token → ''；env > 空；st.secrets > env 優先序
- `_expected_latest_trading_date()`：純日期邏輯(週末退到週五)
- `_make_proxy_session()`：建 session 物件(不發 HTTP)、verify=False

NEVER calls the network fetchers (fetch_price_data / fetch_dividend_data /
fetch_financials / fetch_revenue / fetch_quarterly / fetch_quarterly_extra)。
"""
from __future__ import annotations

import datetime
import os

import pytest

from src.data.stock import app_stock_fetchers as m


FETCHERS = [
    "fetch_price_data",
    "fetch_dividend_data",
    "fetch_financials",
    "fetch_revenue",
    "fetch_quarterly",
    "fetch_quarterly_extra",
]


class TestModuleSmoke:
    def test_import_and_helpers_present(self):
        assert callable(m._get_finmind_token)
        assert callable(m._expected_latest_trading_date)
        assert callable(m._make_proxy_session)
        assert callable(m._get_loader)

    @pytest.mark.parametrize("name", FETCHERS)
    def test_fetchers_callable(self, name):
        # 5 fetcher(+ price) 對外 API 存在且 callable(不實際呼叫 → 不碰網路)
        assert hasattr(m, name)
        assert callable(getattr(m, name))


class TestGetFinmindToken:
    def test_no_token_returns_empty_string(self, monkeypatch):
        # 無 st.secrets、無 env → graceful 回 '' (不 raise)
        monkeypatch.delenv("FINMIND_TOKEN", raising=False)
        # 確保 st.secrets 不提供(NoOpST.secrets 為空 dict;真 streamlit 環境亦讀不到 key)
        result = m._get_finmind_token()
        assert isinstance(result, str)
        assert result == ""

    def test_env_token_is_read(self, monkeypatch):
        monkeypatch.setenv("FINMIND_TOKEN", "env-tok-xyz")
        # st.secrets 缺 key 時應 fall through 到 os.environ
        assert m._get_finmind_token() == "env-tok-xyz"

    def test_secrets_takes_priority_over_env(self, monkeypatch):
        # st.secrets > os.environ:patch st.secrets 帶 key,即使 env 有值仍取 secrets
        monkeypatch.setenv("FINMIND_TOKEN", "env-tok")

        class _FakeSecrets:
            @staticmethod
            def get(key, default=""):
                return "secrets-tok" if key == "FINMIND_TOKEN" else default

        monkeypatch.setattr(m.st, "secrets", _FakeSecrets(), raising=False)
        assert m._get_finmind_token() == "secrets-tok"

    def test_empty_secrets_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv("FINMIND_TOKEN", "env-fallback")

        class _EmptySecrets:
            @staticmethod
            def get(key, default=""):
                return default  # 空字串 → falsy → 走 env

        monkeypatch.setattr(m.st, "secrets", _EmptySecrets(), raising=False)
        assert m._get_finmind_token() == "env-fallback"

    def test_secrets_raising_is_swallowed(self, monkeypatch):
        # st.secrets.get 拋例外 → except → 退回 env(不向上爆)
        monkeypatch.setenv("FINMIND_TOKEN", "env-after-raise")

        class _BoomSecrets:
            @staticmethod
            def get(key, default=""):
                raise RuntimeError("no secrets file")

        monkeypatch.setattr(m.st, "secrets", _BoomSecrets(), raising=False)
        assert m._get_finmind_token() == "env-after-raise"


class TestExpectedLatestTradingDate:
    def test_returns_date(self):
        d = m._expected_latest_trading_date()
        assert isinstance(d, datetime.date)

    def test_never_weekend(self):
        # 回傳日永遠是工作日(weekday < 5);週末應退到週五
        d = m._expected_latest_trading_date()
        assert d.weekday() < 5

    def test_within_two_days_of_today(self):
        # 最多退 2 天(週日退到週五)
        today = datetime.date.today()
        d = m._expected_latest_trading_date()
        delta = (today - d).days
        assert 0 <= delta <= 2

    def test_weekday_today_returns_today(self):
        # 若今天是工作日,應回今天(loop 不執行)
        today = datetime.date.today()
        d = m._expected_latest_trading_date()
        if today.weekday() < 5:
            assert d == today
        else:
            # 週末:回傳的應 <= today 且為週五
            assert d < today and d.weekday() == 4


class TestMakeProxySession:
    def test_returns_session_without_network(self):
        # 建 session 物件本身不發 HTTP;driver fallback 後仍是 requests.Session
        import requests

        s = m._make_proxy_session()
        assert isinstance(s, requests.Session)

    def test_verify_disabled(self):
        # 對齊 app.py:_bps 行為 — verify=False(NAS proxy 自簽憑證)
        s = m._make_proxy_session()
        assert s.verify is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
