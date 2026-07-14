"""v19.120:fetch_url lean-path(attempts=1)直連降級修復。

Bug:原直連門檻 `_block >= 2` 在 attempts=1 時永遠達不到——單次 proxy 403 只讓
`_block=1` 且因 `attempts <= 1` 立即 break,直連整段被跳過。這使得 attempts=1 且
無非-FRED 逃生口的 macro 卡片(Fed Funds:兩條 fallback 都打 stlouisfed.org)在
proxy 一 403 時直接卡「待取得」,而 CPI 因第三條 BLS 自己直連(不走 fetch_url)得以存活。

修:門檻改 `_block >= 1`,任一次 proxy 403 都退直連(FRED 為公開 API,直連可通)。
對 attempts>1 多重試路徑無影響(該路徑本就累到 _block>=2 或先 return 200)。
"""
import time

import pytest

import src.data.proxy.proxy_helper as ph


class _FakeResp:
    def __init__(self, status_code, content=b'OK'):
        self.status_code = status_code
        self._content = content
        self.content = content
        self.encoding = 'utf-8'


class _FakeSession:
    """proxies 非空 → 回 proxy_status;proxies 空(直連)→ 回 direct_status。

    記錄每次 get 的 proxies,供斷言「直連確有發生」。
    """

    def __init__(self, proxy_status, direct_status, direct_content=b'DIRECT-OK'):
        self.proxy_status = proxy_status
        self.direct_status = direct_status
        self.direct_content = direct_content
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None,
            proxies=None, verify=None):
        self.calls.append({'proxies': proxies, 'verify': verify})
        if proxies:                       # 走 NAS proxy
            return _FakeResp(self.proxy_status)
        return _FakeResp(self.direct_status, self.direct_content)   # 直連

    @property
    def n_proxy(self):
        return sum(1 for c in self.calls if c['proxies'])

    @property
    def n_direct(self):
        return sum(1 for c in self.calls if not c['proxies'])


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    ph._URL_CACHE.clear()
    monkeypatch.setattr(time, 'sleep', lambda *a, **k: None)   # 免 retry 真睡
    yield
    ph._URL_CACHE.clear()


def _use_proxy(monkeypatch):
    monkeypatch.setattr(ph, 'get_proxy_config',
                        lambda: {'http': 'p', 'https': 'p'})


def test_lean_path_403_falls_back_to_direct(monkeypatch):
    """核心:attempts=1 + proxy 403 → 必須退直連並取回 200(修前直連被跳過 → None)。"""
    _use_proxy(monkeypatch)
    fake = _FakeSession(proxy_status=403, direct_status=200)
    monkeypatch.setattr(ph, '_get_thread_session', lambda lean=False: fake)

    r = ph.fetch_url('https://fred.stlouisfed.org/graph/fredgraph.csv',
                     params={'id': 'FEDFUNDS'}, timeout=10, attempts=1)

    assert r is not None and r.status_code == 200, 'proxy 403 後應退直連取回 200'
    assert fake.n_proxy >= 1, '應先試過 proxy'
    assert fake.n_direct >= 1, '應真的發生直連(proxies 為空)呼叫'


def test_lean_path_no_regression_when_proxy_ok(monkeypatch):
    """proxy 直接 200 → 不多打直連,成功路徑零影響。"""
    _use_proxy(monkeypatch)
    fake = _FakeSession(proxy_status=200, direct_status=200)
    monkeypatch.setattr(ph, '_get_thread_session', lambda lean=False: fake)

    r = ph.fetch_url('https://example.com/ok', timeout=10, attempts=1)

    assert r is not None and r.status_code == 200
    assert fake.n_proxy == 1 and fake.n_direct == 0, 'proxy 成功不應再直連'


def test_multi_attempt_persistent_403_still_direct(monkeypatch):
    """attempts>1 持續 403 → 仍退直連(原行為不回歸)。"""
    _use_proxy(monkeypatch)
    fake = _FakeSession(proxy_status=403, direct_status=200)
    monkeypatch.setattr(ph, '_get_thread_session', lambda lean=False: fake)

    r = ph.fetch_url('https://fred.stlouisfed.org/x', timeout=5, attempts=3)

    assert r is not None and r.status_code == 200
    assert fake.n_direct >= 1, 'attempts>1 持續 403 仍應退直連'


def test_direct_also_fails_returns_none_no_fabrication(monkeypatch):
    """proxy 403 + 直連也非 200 + 無 NAS 中繼 → 誠實回 None(§1 不假裝成功)。"""
    _use_proxy(monkeypatch)
    fake = _FakeSession(proxy_status=403, direct_status=503)
    monkeypatch.setattr(ph, '_get_thread_session', lambda lean=False: fake)
    monkeypatch.setattr(ph, 'nas_relay_fetch', lambda *a, **k: None)

    r = ph.fetch_url('https://fred.stlouisfed.org/y',
                     params={'id': 'FEDFUNDS'}, timeout=10, attempts=1)

    assert r is None, 'proxy+直連皆敗且無中繼 → 應回 None(fail loud)'
    assert fake.n_direct >= 1, '仍應試過直連才放棄'
