"""
test_etf_price_proxy.py — 迴歸鎖:ETF 價格歷史抓取必須走 NAS proxy。

BUG(修前):`_fetch_etf_price_max` 直呼 `yf.Ticker(ticker).history(period='max')`
無 proxy → Streamlit Cloud 海外 IP 被 Yahoo 封鎖/rate-limit → 回空 df →
每檔 ETF(0050.TW 為預設首檔)顯示「找不到 0050.TW 的歷史/價格資料」,並連帶
拖垮 VaR 與 vs-0050 比較。

FIX:把 history 呼叫包進 yf_proxy._proxy_env()(臨時設 HTTPS/HTTP_PROXY,finally
還原)。本測試驗證:
1. history 呼叫確實在 _proxy_env context 內執行(enter → history → exit 順序)。
2. 空 history 仍回空 DataFrame(§1 fail loud,不造假)。
3. etf_fetch 複用 yf_proxy._proxy_env SSOT(未自行重寫 env backup/restore)。
4. import etf_fetch + yf_proxy 無 import cycle。
5. history 必須帶 auto_adjust=True(還原權息)—— 見下方 §auto_adjust 兩條釘子。

CLAUDE.md §8:etf_fetch(L1 Data)import L1 proxy helper 合法,EX-CACHE-1 適用。
"""
from __future__ import annotations

import contextlib

import pandas as pd
import pytest

from src.data.etf import etf_fetch
from src.data.proxy import yf_proxy


def _install_recording_env(monkeypatch, calls: list):
    """把 etf_fetch._proxy_env 換成會記錄進出的 context manager。"""
    @contextlib.contextmanager
    def _recording_env():
        calls.append('proxy_enter')
        try:
            yield
        finally:
            calls.append('proxy_exit')
    monkeypatch.setattr(etf_fetch, '_proxy_env', _recording_env)


def _install_fake_yf(monkeypatch, calls: list, hist_df: pd.DataFrame):
    """把 etf_fetch.yf 換成回傳指定 history df 的假 yfinance。"""
    class _FakeTicker:
        def __init__(self, ticker):
            calls.append(('ticker', ticker))

        def history(self, *args, **kwargs):
            calls.append('history')
            return hist_df.copy()

    class _FakeYF:
        Ticker = _FakeTicker

    monkeypatch.setattr(etf_fetch, 'yf', _FakeYF)


def test_price_max_runs_history_inside_proxy_env(monkeypatch):
    """history 呼叫必須在 _proxy_env 內:順序 enter → history → exit。"""
    calls: list = []
    _install_recording_env(monkeypatch, calls)
    idx = pd.to_datetime(['2020-01-02', '2020-01-03'])
    _df = pd.DataFrame(
        {'Open': [1.0, 2.0], 'High': [2.0, 3.0], 'Low': [0.5, 1.5],
         'Close': [1.5, 2.5], 'Volume': [100, 200]},
        index=idx,
    )
    _install_fake_yf(monkeypatch, calls, _df)

    etf_fetch._fetch_etf_price_max.clear()  # 清 st.cache_data,強制跑函式體
    out = etf_fetch._fetch_etf_price_max('0050.TW')

    assert 'proxy_enter' in calls, '_proxy_env 未被進入 — history 沒走 proxy'
    assert 'history' in calls, 'history 未被呼叫'
    # 順序鐵則:proxy 進入 → history → proxy 離開
    assert calls.index('proxy_enter') < calls.index('history') < calls.index('proxy_exit'), \
        f'history 未包在 _proxy_env context 內:{calls}'
    assert not out.empty
    assert list(out['Close']) == [1.5, 2.5]


def test_price_max_empty_history_returns_empty_df(monkeypatch):
    """空 history → 回空 DataFrame(§1:不造假、不 raise、caller 依 empty 判斷)。"""
    calls: list = []
    _install_recording_env(monkeypatch, calls)
    _install_fake_yf(monkeypatch, calls, pd.DataFrame())

    etf_fetch._fetch_etf_price_max.clear()
    out = etf_fetch._fetch_etf_price_max('0050.TW')

    assert isinstance(out, pd.DataFrame)
    assert out.empty
    # 即使結果為空,history 仍應在 proxy context 內嘗試過
    assert 'proxy_enter' in calls
    assert calls.index('proxy_enter') < calls.index('history')


def test_price_max_swallows_exception_returns_empty_df(monkeypatch):
    """history 拋錯 → print log + 回空 df(L1 不得 st.error;不吞成假資料)。"""
    calls: list = []
    _install_recording_env(monkeypatch, calls)

    class _BoomTicker:
        def __init__(self, ticker):
            pass

        def history(self, *args, **kwargs):
            raise RuntimeError('yahoo 429 rate limit')

    class _BoomYF:
        Ticker = _BoomTicker

    monkeypatch.setattr(etf_fetch, 'yf', _BoomYF)

    etf_fetch._fetch_etf_price_max.clear()
    out = etf_fetch._fetch_etf_price_max('0050.TW')

    assert isinstance(out, pd.DataFrame)
    assert out.empty
    # 例外發生在 proxy context 內,context manager 的 finally 仍應還原(exit)
    assert calls == ['proxy_enter', 'proxy_exit'], \
        f'例外路徑下 _proxy_env 進出不完整:{calls}'


def test_reuses_yf_proxy_proxy_env_ssot():
    """etf_fetch._proxy_env 必須是 yf_proxy._proxy_env 本尊(複用 SSOT,未重寫)。"""
    assert etf_fetch._proxy_env is yf_proxy._proxy_env


def test_no_import_cycle():
    """import etf_fetch + yf_proxy 皆成功 → 無 import cycle。"""
    import importlib
    m1 = importlib.import_module('src.data.etf.etf_fetch')
    m2 = importlib.import_module('src.data.proxy.yf_proxy')
    assert hasattr(m1, '_fetch_etf_price_max')
    assert hasattr(m2, '_proxy_env')
    # yf_proxy 不得反向 import etf_fetch(cycle 來源)
    import inspect
    src = inspect.getsource(m2)
    assert 'etf_fetch' not in src, 'yf_proxy 不應 import etf_fetch(否則成環)'


def test_source_wraps_history_in_proxy_env():
    """靜態鎖:原始碼中 history('max') 呼叫必須被 _proxy_env 包住(防回歸裸抓)。"""
    import inspect
    src = inspect.getsource(etf_fetch._fetch_etf_price_max)
    assert 'with _proxy_env():' in src, '_fetch_etf_price_max 未用 _proxy_env 包 history'
    # _proxy_env 的 with 必須出現在 history 呼叫之前
    assert src.index('with _proxy_env():') < src.index(".history(period='max'"), \
        'history 呼叫未被 _proxy_env 包住'


# ── §auto_adjust:`auto_adjust=True` 是「含息」的唯一來源,不是可調參數 ──────
#
# 2026-08-25 稽核發現:`auto_adjust` 在整個 tests/ 只出現在一句 docstring 裡,
# **沒有任何測試釘它**。這很危險 —— `etf_calc.calc_total_return_1y` 在同日
# 修掉了「配息算兩次」的 bug,而它之所以正確,整個建立在這裡拿到的是**還原價**:
#
#     還原價序列 → (p_end - p_start) / p_start 本身就已經是含息總報酬
#
# 把它翻成 False,`Close` 變成未還原的原始收盤價,除息日的跳空不再被補回 →
# `calc_total_return_1y` 會**靜默地**變成「純價差報酬」(低估一整年的配息),
# 「賺息賠本」紅燈開始對健康的高股息 ETF 亂噴,多檔比較表的綜合分集體下修。
# 而所有既有守衛用的都是**合成 df**(自己造 Close 欄),永遠不會知道上游翻了面。
#
# ⚠️ 後人看到本節紅燈:要修的是**程式**,不是測試。若真有「需要原始價」的需求,
#    請另開一個 fetcher(或加參數並在呼叫端明確選擇),不要就地把 True 改掉 ——
#    `calc_total_return_1y` / `dividend_station.total_return_pct` /
#    `calc_avg_yield` 全部預設吃還原價,就地改等於同時改掉三個算式的意思。


def _install_kwarg_recording_yf(monkeypatch, seen: dict, hist_df: pd.DataFrame):
    """把 etf_fetch.yf 換成會記下 history() 收到哪些 kwargs 的假 yfinance。"""
    class _RecTicker:
        def __init__(self, ticker):
            seen['ticker'] = ticker

        def history(self, *args, **kwargs):
            seen['args'] = args
            seen['kwargs'] = kwargs
            return hist_df.copy()

    class _RecYF:
        Ticker = _RecTicker

    monkeypatch.setattr(etf_fetch, 'yf', _RecYF)


def test_price_max_requests_adjusted_history(monkeypatch):
    """行為鎖:history() 必須**顯式**收到 auto_adjust=True。

    顯式的理由:yfinance 的 `Ticker.history` 預設值跨版本改過,靠 library 預設
    等於把「含息與否」外包給 requirements.txt 的版本浮動 —— 那正是會靜默漂移
    的那種前提(§5 可重現性)。
    """
    seen: dict = {}
    _install_recording_env(monkeypatch, [])
    idx = pd.to_datetime(['2020-01-02', '2020-01-03'])
    _df = pd.DataFrame({'Close': [1.5, 2.5]}, index=idx)
    _install_kwarg_recording_yf(monkeypatch, seen, _df)

    etf_fetch._fetch_etf_price_max.clear()   # 清 st.cache_data,強制跑函式體
    etf_fetch._fetch_etf_price_max('0050.TW')

    assert seen.get('kwargs', {}).get('auto_adjust') is True, (
        f"history() 收到的 kwargs = {seen.get('kwargs')} —— "
        'auto_adjust 必須顯式為 True。翻成 False / 省略改吃 yfinance 預設值,'
        'Close 就不再是還原價,calc_total_return_1y 會靜默變成「純價差報酬」'
        '(低估一整年配息),而所有守衛都用合成 df,不會有任何一條紅。'
    )


def test_source_pins_auto_adjust_true():
    """靜態鎖:原始碼裡 history(period='max') 那一呼必須寫死 auto_adjust=True。

    與上一條的分工:上一條驗「這次呼叫確實傳了 True」,本條驗「原始碼裡就是
    這個字面值」—— 擋掉把它換成變數 / 環境變數 / 設定檔的寫法(那種寫法在測試
    環境剛好是 True、在 production 可能不是,比直接改成 False 更難查)。
    """
    import inspect
    src = inspect.getsource(etf_fetch._fetch_etf_price_max)
    assert "auto_adjust=True" in src, (
        '_fetch_etf_price_max 不再寫死 auto_adjust=True —— '
        '含息總報酬(etf_calc.calc_total_return_1y / dividend_station.total_return_pct '
        '/ calc_avg_yield)全部預設 Close 是還原價,這一行是那個前提的唯一出處。'
    )
    assert "auto_adjust=False" not in src, \
        '_fetch_etf_price_max 出現 auto_adjust=False —— 還原價前提被翻面'
    # 必須就掛在 period='max' 那一呼上(而不是別處某個順手加的呼叫)
    assert ".history(period='max', auto_adjust=True)" in src, \
        f'auto_adjust=True 未掛在 history(period=\'max\') 那一呼上:\n{src}'


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-q']))
