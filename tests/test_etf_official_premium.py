"""tests/test_etf_official_premium.py — v18.445 TWSE MIS ETF 即時淨值解析守衛。

fetch_etf_official_premium 改抓 TWSE MIS `etf_nav.jsp`(官方 ETF 申贖/即時淨值揭露)。
本測試釘死欄位對映(a=代號 / f=即時估計淨值 iNAV / g=折溢價率% / h=市價 / i=日期),
避免日後誤把 f(iNAV)與 h(市價)接反 → 又算出假溢價。
"""
from __future__ import annotations

import pytest

import src.data.etf.etf_fetch as ef
import src.data.proxy.proxy_helper as ph


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


_MIS_PAYLOAD = {
    'msgArray': [
        # 0050:f=iNAV 109.58 / h=市價 109.45 / g=折溢價 -0.13%(對齊 wantgoo 盤中值)
        {'a': '0050', 'b': '元大台灣50', 'e': '106.74', 'f': '109.58',
         'g': '-0.13', 'h': '109.45', 'i': '20260701', 'j': '11:54:00'},
        {'a': '0056', 'b': '元大高股息', 'f': '40.0',
         'g': '0.5', 'h': '40.2', 'i': '20260701', 'j': '11:54:00'},
    ],
    'rtCode': '0000',
}


def _patch_proxy_and_mis(monkeypatch, payload=_MIS_PAYLOAD):
    monkeypatch.setattr(ph, 'get_proxy_config', lambda: {'http': 'x', 'https': 'x'})
    monkeypatch.setattr(ph, 'fetch_url', lambda *a, **k: _FakeResp(payload))
    ef.fetch_etf_official_premium.clear()


def test_mis_field_mapping_0050(monkeypatch):
    """f=iNAV(淨值)、h=市價、g=折溢價率 —— 對映不可接反。"""
    _patch_proxy_and_mis(monkeypatch)
    out = ef.fetch_etf_official_premium('0050.TW')
    assert out is not None, '有代理 + MIS 有 0050 → 應回值'
    assert out['nav'] == pytest.approx(109.58), 'nav 應取 f(即時估計淨值)'
    assert out['price'] == pytest.approx(109.45), 'price 應取 h(市價)'
    assert out['premium_pct'] == pytest.approx(-0.13), 'premium_pct 應取 g(折溢價率)'
    assert out['data_date'] == '2026/07/01'
    assert 'TWSE-MIS' in out['source']


def test_mis_premium_backfill_when_g_missing(monkeypatch):
    """g(折溢價率)缺 → 由 (市價-iNAV)/iNAV 反推(fail-loud 保底,不留空)。"""
    payload = {'msgArray': [
        {'a': '0050', 'f': '100.0', 'h': '101.0', 'i': '20260701'},  # 無 g
    ]}
    _patch_proxy_and_mis(monkeypatch, payload)
    out = ef.fetch_etf_official_premium('0050.TW')
    assert out is not None
    assert out['premium_pct'] == pytest.approx(1.0, abs=0.001)  # (101-100)/100


def test_no_proxy_returns_none(monkeypatch):
    """完全未設代理 → 回 None(不觸網,呼叫端走既有鏈)。"""
    monkeypatch.setattr(ph, 'get_proxy_config', lambda: None)
    monkeypatch.setattr(ph, 'get_nas_relay', lambda: None)
    ef.fetch_etf_official_premium.clear()
    assert ef.fetch_etf_official_premium('0050.TW') is None


def test_us_etf_skipped(monkeypatch):
    """海外 ETF(SPY)非數字碼 → 直接 None(TWSE 無資料),不觸網。"""
    ef.fetch_etf_official_premium.clear()
    assert ef.fetch_etf_official_premium('SPY') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
