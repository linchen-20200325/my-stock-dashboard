# -*- coding: utf-8 -*-
"""批 D2 — D2-f54：ETF 取價 `history()` 帶 `raise_errors=True`，網路錯誤不再被吞成空表並快取。

三個最容易出錯的輸入（§6）：
1. yfinance 吞掉網路錯誤回空表（未帶 raise_errors 時的行為）→ 必須判失敗、不入快取
2. yfinance 自己回報「沒有資料」（裸 `Exception`）→ 照舊回空 df（不得當成失敗）
3. 舊／新版不認 `raise_errors`（TypeError）→ 退回修前呼叫，仍要 `auto_adjust=True`
"""
from __future__ import annotations

import contextlib

import pandas as pd
import pytest

from src.data.etf import etf_fetch


def _hist():
    idx = pd.date_range('2026-01-01', periods=5, freq='D')
    return pd.DataFrame({'Open': 1.0, 'High': 1.0, 'Low': 1.0, 'Close': [1.0, 2, 3, 4, 5],
                         'Volume': 10}, index=idx)


@pytest.fixture()
def _env(monkeypatch):
    @contextlib.contextmanager
    def _noop():
        yield
    monkeypatch.setattr(etf_fetch, '_proxy_env', _noop)
    etf_fetch._fetch_etf_price_max.clear()
    yield
    etf_fetch._fetch_etf_price_max.clear()


def _install(monkeypatch, behave):
    seen = []

    class _T:
        def __init__(self, ticker):
            pass

        def history(self, *args, **kwargs):
            seen.append(kwargs)
            return behave(kwargs)

    class _YF:
        Ticker = _T

    monkeypatch.setattr(etf_fetch, 'yf', _YF)
    return seen


def test_swallowed_network_error_is_failure_and_not_cached(_env, monkeypatch):
    state = {'down': True}

    def _behave(kw):
        if state['down']:
            if kw.get('raise_errors'):
                raise ConnectionError('proxy down')
            return pd.DataFrame()   # 修前：yfinance 吞成空表
        return _hist()

    _install(monkeypatch, _behave)
    out = etf_fetch._fetch_etf_price_max('0050.TW')
    assert out.empty and etf_fetch.PRICE_FETCH_FAILED_ATTR in out.attrs, (
        f'網路錯誤必須帶失敗旗標，不得當成「沒資料」：attrs={out.attrs}')
    state['down'] = False
    # 快取層不得留下那張空表：直接打快取層要拿到恢復後的資料
    healed = etf_fetch._fetch_etf_price_max_cached('0050.TW')
    assert len(healed) == 5, '失敗不得入快取（上游恢復後快取層須真重抓）'


def test_yf_reported_no_data_returns_empty_without_failure_flag(_env, monkeypatch):
    def _behave(kw):
        if kw.get('raise_errors'):
            raise Exception('0050.TW: possibly delisted; no price data found')
        return pd.DataFrame()

    _install(monkeypatch, _behave)
    out = etf_fetch._fetch_etf_price_max('0050.TW')
    assert out.empty and etf_fetch.PRICE_FETCH_FAILED_ATTR not in out.attrs


def test_legacy_signature_falls_back_with_auto_adjust(_env, monkeypatch):
    def _behave(kw):
        if 'raise_errors' in kw:
            raise TypeError("history() got an unexpected keyword argument 'raise_errors'")
        return _hist()

    seen = _install(monkeypatch, _behave)
    out = etf_fetch._fetch_etf_price_max('0050.TW')
    assert len(out) == 5
    assert seen[-1].get('auto_adjust') is True and 'raise_errors' not in seen[-1]


def test_success_requests_raise_errors_and_auto_adjust(_env, monkeypatch):
    seen = _install(monkeypatch, lambda kw: _hist())
    out = etf_fetch._fetch_etf_price_max('0050.TW')
    assert len(out) == 5
    assert seen[0].get('raise_errors') is True and seen[0].get('auto_adjust') is True
