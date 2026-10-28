"""xview V7（M2）：本益比對照表（TWSE BWIBBU／TPEX peratio）失敗不入快取＋失敗退避。

修前兩支 fetcher 的所有失敗分支都 `return pd.DataFrame()`，被 `@st.cache_data(ttl=TTL_1DAY)`
當正常值快取 1 天。修後：快取層失敗 → raise（不入快取）；公開函式照舊回空表（形狀不變），
並接 `shared.fail_cooldown` —— 冷卻期內不重打上游；成功一次即解除。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data.stock import yield_pe_fetcher as Y

_TWSE_OK = [{"Code": "2330", "Name": "台積電", "PEratio": "20.1",
             "DividendYield": "1.5", "PBratio": "5.0"}]
_TPEX_OK = [{"SecuritiesCompanyCode": "5314", "CompanyName": "世紀",
             "PriceEarningRatio": "12.0", "YieldRatio": "3.0", "PriceBookRatio": "1.2"}]

_CASES = {
    "twse": (Y.fetch_twse_yield_pe, Y._twse_fail_cooldown, _TWSE_OK),
    "tpex": (Y.fetch_tpex_yield_pe, Y._tpex_fail_cooldown, _TPEX_OK),
}


def _resp(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


class _Upstream:
    """依序回應；記錄被打幾次。"""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, url, *a, **kw):
        self.calls += 1
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def _clean():
    for fn, _cd, _ in _CASES.values():
        fn.clear()
    yield
    for fn, cd, _ in _CASES.values():
        fn.clear()
        cd.seconds = Y._FailCooldown().seconds


_FAILS = {
    "non200": lambda: _resp([], 503),
    "none": lambda: None,
    "bad_format": lambda: _resp({"oops": 1}),
    "empty_list": lambda: _resp([]),
    "exception": lambda: RuntimeError("boom"),
}


@pytest.mark.parametrize("market", list(_CASES))
@pytest.mark.parametrize("fail", list(_FAILS))
def test_failure_returns_empty_and_is_not_cached(monkeypatch, market, fail):
    fn, cd, ok = _CASES[market]
    up = _Upstream(_FAILS[fail](), _resp(ok))
    monkeypatch.setattr(Y, "proxy_fetch_url", up)
    first = fn()
    assert isinstance(first, pd.DataFrame) and first.empty
    cd.seconds = 0          # 模擬冷卻期滿（不碰快取層）
    second = fn()
    assert not second.empty, "失敗被快取了：上游恢復後仍回空表"
    assert up.calls == 2


def test_tpex_missing_code_column_is_not_cached(monkeypatch):
    up = _Upstream(_resp([{"CompanyName": "x"}]), _resp(_TPEX_OK))
    monkeypatch.setattr(Y, "proxy_fetch_url", up)
    assert Y.fetch_tpex_yield_pe().empty
    Y._tpex_fail_cooldown.seconds = 0
    assert not Y.fetch_tpex_yield_pe().empty


@pytest.mark.parametrize("market", list(_CASES))
def test_cooldown_blocks_hammering_upstream(monkeypatch, market):
    fn, _cd, _ = _CASES[market]
    up = _Upstream(_resp([], 503))
    monkeypatch.setattr(Y, "proxy_fetch_url", up)
    for _ in range(5):
        assert fn().empty
    assert up.calls == 1, "冷卻期內不得重打上游"


@pytest.mark.parametrize("market", list(_CASES))
def test_success_is_cached_and_shape_unchanged(monkeypatch, market):
    fn, _cd, ok = _CASES[market]
    up = _Upstream(_resp(ok))
    monkeypatch.setattr(Y, "proxy_fetch_url", up)
    a = fn()
    b = fn()
    assert list(a.columns) == list(b.columns)
    assert {"代碼", "名稱", "本益比", "殖利率(%)", "股價淨值比"} <= set(a.columns)
    assert up.calls == 1, "成功結果應被快取"


@pytest.mark.parametrize("market", list(_CASES))
def test_public_clear_clears_cache_and_cooldown(monkeypatch, market):
    fn, _cd, ok = _CASES[market]
    up = _Upstream(_resp([], 503), _resp(ok))
    monkeypatch.setattr(Y, "proxy_fetch_url", up)
    assert fn().empty
    fn.clear()                          # 冷卻期內清除 → 立即重抓
    assert not fn().empty
    assert up.calls == 2
    fn.clear()                          # 成功快取也被清 → 再打一次
    up.responses = [_resp(ok)]
    fn()
    assert up.calls == 3


def test_markets_cooldowns_are_independent(monkeypatch):
    up = _Upstream(_resp([], 503))
    monkeypatch.setattr(Y, "proxy_fetch_url", up)
    assert Y.fetch_twse_yield_pe().empty
    up.responses = [_resp(_TPEX_OK)]
    assert not Y.fetch_tpex_yield_pe().empty, "上市失敗冷卻不得連坐上櫃"


def test_pe_name_maps_failsoft_unchanged(monkeypatch):
    """呼叫端不變：一半失敗 → 只少半邊、不炸，failed_markets 照報。"""
    def _url(url, *a, **kw):
        return _resp([], 503) if url == Y.TWSE_BWIBBU_URL else _resp(_TPEX_OK)
    monkeypatch.setattr(Y, "proxy_fetch_url", _url)
    _failed: list = []
    pe, names = Y.fetch_pe_name_maps(failed_markets=_failed)
    assert "5314" in pe and "2330" not in pe
    assert _failed


def test_late_failure_after_success_is_not_recorded(monkeypatch):
    """守 `_only_cache_success` 內的 `cooldown.success(_KEY)`（世代遞增擋晚到失敗覆蓋）。

    A 開始抓（記世代）→ B 成功 → A 才失敗 → A 的失敗不得寫入（否則下一位在 B 的成功已快取時
    拿到假失敗）。拿掉 `cooldown.success(_KEY)` → 世代不變 → A 的失敗被記下 → 本測試轉紅。
    """
    cd = Y._twse_fail_cooldown
    calls = {"n": 0}

    def _cached():
        calls["n"] += 1
        if calls["n"] == 1:
            # A 抓取途中，B 成功（走同一個 wrapper）
            assert not Y._only_cache_success(cd, lambda: pd.DataFrame({"代碼": ["2330"]})).empty
            raise Y._YieldPeFetchError("A 晚到的失敗")
        return pd.DataFrame({"代碼": ["2330"]})
    assert Y._only_cache_success(cd, _cached).empty      # A 本身仍回空表
    assert len(cd) == 0, "晚到失敗覆蓋了 B 的成功"
    assert not Y._only_cache_success(cd, _cached).empty
