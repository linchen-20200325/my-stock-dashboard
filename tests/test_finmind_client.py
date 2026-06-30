"""tests/test_finmind_client.py — D5 v18.437 FinMind L1 SSOT client。

對應 src/data/core/finmind_client.py:finmind_get(收斂 ~12 處手寫 FinMind GET 樣板)。
驗:日期正規化、param 省略規則、status 判讀、retry、fail-safe(回空 DataFrame 不 raise)。
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.core import finmind_client as fc


class TestToDash:
    def test_ymd_compact_to_dash(self):
        assert fc._to_dash("20240401") == "2024-04-01"

    def test_dash_passthrough(self):
        assert fc._to_dash("2024-04-01") == "2024-04-01"

    def test_none_returns_none(self):
        assert fc._to_dash(None) is None


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class TestFinmindGet:
    def test_status_200_returns_dataframe(self, monkeypatch):
        captured = {}

        def _fake_get(url, params=None, headers=None, timeout=None):
            captured['url'] = url
            captured['params'] = params
            captured['timeout'] = timeout
            return _FakeResp({"status": 200, "data": [{"a": 1}, {"a": 2}]})

        monkeypatch.setattr(fc.requests, "get", _fake_get)
        out = fc.finmind_get("TaiwanStockMonthRevenue", data_id="2330",
                             start_date="2024-01-01", token="tok", timeout=20)
        assert isinstance(out, pd.DataFrame) and len(out) == 2
        # data_id / start_date / token 有送;end_date 未給 → 不送
        assert captured['params']['data_id'] == "2330"
        assert captured['params']['start_date'] == "2024-01-01"
        assert captured['params']['token'] == "tok"
        assert 'end_date' not in captured['params']
        assert captured['timeout'] == 20

    def test_omit_data_id_when_none(self, monkeypatch):
        captured = {}

        def _fake_get(url, params=None, headers=None, timeout=None):
            captured['params'] = params
            return _FakeResp({"status": 200, "data": []})

        monkeypatch.setattr(fc.requests, "get", _fake_get)
        fc.finmind_get("SomeDataset", start_date="20240101", end_date="20240201")
        assert 'data_id' not in captured['params']      # None → 不送(避免 422)
        assert captured['params']['start_date'] == "2024-01-01"  # YMD 正規化
        assert captured['params']['end_date'] == "2024-02-01"

    def test_non_200_returns_empty(self, monkeypatch):
        monkeypatch.setattr(fc.requests, "get",
                            lambda *a, **k: _FakeResp({"status": 402, "msg": "quota"}, 402))
        out = fc.finmind_get("X")
        assert isinstance(out, pd.DataFrame) and out.empty

    def test_exception_returns_empty_not_raise(self, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(fc.requests, "get", _boom)
        out = fc.finmind_get("X", retries=1)
        assert isinstance(out, pd.DataFrame) and out.empty  # §1 fail-safe:不 raise

    def test_retries_attempted(self, monkeypatch):
        calls = {"n": 0}

        def _flaky(*a, **k):
            calls["n"] += 1
            raise RuntimeError("transient")

        monkeypatch.setattr(fc.requests, "get", _flaky)
        monkeypatch.setattr(fc.time, "sleep", lambda *_a, **_k: None)  # 不真睡
        fc.finmind_get("X", retries=2)
        assert calls["n"] == 2  # 重試 2 次後放棄


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
