# -*- coding: utf-8 -*-
"""批 D2 — D2-f31：`fetch_flow_snapshot` 有代號確定抓取失敗時不入快取（st.cache_data 與 pkl 兩層）。

三個最容易出錯的輸入（§6）：
1. 部分代號確定失敗（SPY 正常）→ 回傳同修前（失敗者為 None），但不得被快取
2. 上游恢復後同參數再呼叫 → 必須真重抓、拿到完整結果
3. 「真的沒資料」（`_fetch_single_cached` 正常回 None）→ 照舊快取（不猜）
"""
from __future__ import annotations

import pandas as pd
import pytest

import src.data.daily.daily_data_fetchers as DDF
from shared.etf_universe import all_symbols


def _frame():
    return pd.DataFrame({'close': [1.0, 2.0]},
                        index=pd.date_range('2026-01-01', periods=2, freq='D'))


@pytest.fixture()
def _world(monkeypatch):
    pkl: dict = {}
    puts: list = []
    monkeypatch.setattr(DDF, '_pkl_get', lambda k, ttl: pkl.get(k, DDF._CACHE_SENTINEL))

    def _put(k, v):
        puts.append(k)
        pkl[k] = v
    monkeypatch.setattr(DDF, '_pkl_put', _put)
    state = {'fail': set(), 'nodata': set(), 'calls': 0}

    def _fake_single(sym, period='60d'):
        state['calls'] += 1
        if sym in state['fail']:
            raise DDF._SingleFetchFailed(None, f'抓取失敗:{sym}')
        if sym in state['nodata']:
            return None
        return _frame()

    monkeypatch.setattr(DDF, '_fetch_single_cached', _fake_single)
    DDF.fetch_flow_snapshot.clear()
    yield state, puts
    DDF.fetch_flow_snapshot.clear()


def _a_non_spy_symbol():
    return next(s for s in sorted(set(all_symbols().values())) if s != 'SPY')


def test_partial_failure_not_cached_then_heals(_world):
    state, puts = _world
    bad = _a_non_spy_symbol()
    state['fail'] = {bad}
    out1 = DDF.fetch_flow_snapshot()
    bad_names = [n for n, s in all_symbols().items() if s == bad]
    assert all(out1[n] is None for n in bad_names)
    assert '_flow_snapshot' not in puts, '部分失敗不得寫 pkl'

    state['fail'] = set()
    out2 = DDF.fetch_flow_snapshot()
    assert all(out2[n] is not None for n in bad_names), '上游恢復後必須重抓，不得回凍住的部分失敗'
    assert '_flow_snapshot' in puts

    calls = state['calls']
    state['fail'] = set(all_symbols().values())
    out3 = DDF.fetch_flow_snapshot()
    assert state['calls'] == calls, '成功結果須照常入快取（TTL 內不重抓）'
    assert all(v is not None for v in out3.values())


def test_true_no_data_still_cached(_world):
    state, _puts = _world
    state['nodata'] = {_a_non_spy_symbol()}
    DDF.fetch_flow_snapshot()
    calls = state['calls']
    DDF.fetch_flow_snapshot()
    assert state['calls'] == calls, '「真的沒資料」照舊快取'
