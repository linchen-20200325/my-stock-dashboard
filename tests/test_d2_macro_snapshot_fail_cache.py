# -*- coding: utf-8 -*-
"""批 D2 — `macro_snapshot` 三個 block 失敗不入快取（D2-f51／D2-f52／D2-f53）
＋ M1B／M2 年增率擋非有限值（DL-f1-s46）。

三個最容易出錯的輸入（§6）：
1. 失敗 → 上游復原：同參數再呼叫必須真重抓（舊行為回凍住的失敗 1 小時）
2. 成功 → 上游斷線：TTL 內必須回快取成功（效能契約不變）
3. 年增率 NaN／+inf（基期為 0）：不得以「有值」回傳，須落下一層／全敗回 None
"""
from __future__ import annotations

import math

import pandas as pd
import pytest


def _unwrap(fn, *a, **k):
    return fn.__wrapped__(*a, **k)


class _CsvResp:
    status_code = 200

    def __init__(self, text: str):
        self.content = text.encode('utf-8')


_DGS10_CSV = 'observation_date,DGS10\n2026-09-29,4.10\n2026-09-30,4.12\n'


@pytest.fixture()
def _snap():
    import src.data.macro.macro_snapshot as snap
    for fn in (snap.fetch_us10y_block, snap.fetch_m1b_m2_block,
               snap.fetch_twii_2y_for_ma240):
        fn.clear()
    yield snap
    for fn in (snap.fetch_us10y_block, snap.fetch_m1b_m2_block,
               snap.fetch_twii_2y_for_ma240):
        fn.clear()


class TestUs10yFailureNotCached:
    """D2-f52：失敗 dict（資料鍵包 `_err`）不得進快取。"""

    def test_fail_heal_break_cycle(self, _snap, monkeypatch):
        # 地雷：patch 真正持有者 proxy_helper，不可 patch package src.data.proxy
        import src.data.proxy.proxy_helper as _ph
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
        out1 = _snap.fetch_us10y_block(fred_api_key='')
        assert out1['us10y']['current'] is None and '_err' in out1['us10y']

        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: _CsvResp(_DGS10_CSV))
        out2 = _snap.fetch_us10y_block(fred_api_key='')
        assert out2['us10y']['current'] == pytest.approx(4.12), (
            f'上游復原後必須重抓，不得回凍住的失敗：{out2}')

        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
        out3 = _snap.fetch_us10y_block(fred_api_key='')
        assert out3['us10y']['current'] == pytest.approx(4.12), '成功結果須照常入快取'

    def test_predicate(self):
        from src.data.macro.macro_snapshot import _is_us10y_failure
        assert _is_us10y_failure({'us10y': {'_err': 'x', 'current': None, 'value': None}})
        assert _is_us10y_failure(None)
        assert _is_us10y_failure({})
        assert not _is_us10y_failure({'us10y': {'current': 4.1, 'value': 4.1}})


class TestM1bBlockNoneNotCached:
    """D2-f51：三條鏈全敗回 None 不得進快取。"""

    def test_fail_then_heal(self, _snap, monkeypatch):
        import src.data.proxy.proxy_helper as _ph
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
        state = {'ok': False}

        def _cbc():
            if not state['ok']:
                raise RuntimeError('CBC 全敗')
            return {'m1b_yoy': 1.2, 'm2_yoy': 3.4, 'gap': -2.2,
                    'tier_used': 1, 'is_proxy_tier': False}

        monkeypatch.setattr('src.data.macro.fetch_cbc_m1b_m2', _cbc)
        assert _snap.fetch_m1b_m2_block('') is None
        state['ok'] = True
        out = _snap.fetch_m1b_m2_block('')
        assert out is not None and out['m1b_yoy'] == 1.2, (
            f'上游復原後必須重抓，不得回凍住的 None：{out}')
        state['ok'] = False
        assert _snap.fetch_m1b_m2_block('')['m1b_yoy'] == 1.2, '成功結果須照常入快取'


class TestTwii2yNoneNotCached:
    """D2-f53：回 None 不得進快取。"""

    def test_fail_then_heal(self, _snap, monkeypatch):
        import yfinance as yf
        state = {'n': 0}
        good = pd.DataFrame({'Close': [100.0 + i for i in range(260)]},
                            index=pd.date_range('2025-01-01', periods=260, freq='D'))

        def _dl(*a, **k):
            state['n'] += 1
            if state['n'] == 1:
                raise ConnectionError('boom')
            return good.copy()

        monkeypatch.setattr(yf, 'download', _dl)
        assert _snap.fetch_twii_2y_for_ma240() is None
        out = _snap.fetch_twii_2y_for_ma240()
        assert out is not None and len(out) == 260, '上游復原後必須重抓'
        assert state['n'] == 2


class TestM1bNonFinite:
    """DL-f1-s46：NaN／±inf 不得以「有值」流出。"""

    @pytest.mark.parametrize('bad', [float('nan'), float('inf'), float('-inf')])
    def test_tier0_nonfinite_falls_through_to_none(self, monkeypatch, bad):
        import src.data.macro.macro_snapshot as ms
        import src.data.proxy.proxy_helper as _ph
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: {'m1b_yoy': bad, 'm2_yoy': 5.0, 'gap': bad,
                     'tier_used': 1, 'is_proxy_tier': False})
        assert _unwrap(ms.fetch_m1b_m2_block, '') is None

    def test_tier0_nonfinite_m2_falls_through(self, monkeypatch):
        import src.data.macro.macro_snapshot as ms
        import src.data.proxy.proxy_helper as _ph
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: {'m1b_yoy': 1.0, 'm2_yoy': float('nan'), 'gap': float('nan'),
                     'tier_used': 1, 'is_proxy_tier': False})
        assert _unwrap(ms.fetch_m1b_m2_block, '') is None

    def test_fred_zero_base_inf_not_returned(self, monkeypatch):
        """FRED 第 13 筆前為 0 → 年增率 +inf，不得回傳。"""
        import src.data.macro.macro_snapshot as ms
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: (_ for _ in ()).throw(RuntimeError('CBC 全敗')))

        class _R:
            status_code = 200

            def __init__(self, obs):
                self._obs = obs

            def json(self):
                return {'observations': self._obs}

        import src.data.proxy.proxy_helper as _ph
        vals = [str(100 + i) for i in range(20)]
        vals[-13] = '0'

        def _fu2(url, params=None, **k):
            if 'stlouisfed' not in url:
                return None
            return _R([{'date': f'2024-{i % 12 + 1:02d}-01', 'value': v}
                       for i, v in enumerate(vals)])

        monkeypatch.setattr(_ph, 'fetch_url', _fu2)
        assert _unwrap(ms.fetch_m1b_m2_block, '') is None

    def test_imf_nan_not_returned(self, monkeypatch):
        import src.data.macro.macro_snapshot as ms
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: (_ for _ in ()).throw(RuntimeError('CBC 全敗')))

        class _R:
            status_code = 200

            def __init__(self, series, val):
                self._s, self._v = series, val

            def json(self):
                return {'values': {self._s: {'TW': {'2026': self._v}}}}

        def _fu(url, **k):
            if 'MANMM101' in url:
                return _R('MANMM101', 'nan')
            if 'MABMM301' in url:
                return _R('MABMM301', 9.0)
            return None

        import src.data.proxy.proxy_helper as _ph
        monkeypatch.setattr(_ph, 'fetch_url', _fu)
        assert _unwrap(ms.fetch_m1b_m2_block, '') is None

    def test_finite_still_passes(self, monkeypatch):
        import src.data.macro.macro_snapshot as ms
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: {'m1b_yoy': 1.2, 'm2_yoy': 13.83, 'gap': -12.63,
                     'tier_used': 1, 'is_proxy_tier': False})
        r = _unwrap(ms.fetch_m1b_m2_block, '')
        assert r is not None and math.isclose(r['gap'], -12.63)

    def test_is_finite_num(self):
        from src.data.macro.macro_snapshot import _is_finite_num
        assert _is_finite_num(1.5) and _is_finite_num(0) and _is_finite_num(-3)
        for bad in (None, float('nan'), float('inf'), float('-inf'), True, 'x'):
            assert not _is_finite_num(bad), bad


class TestUs10yNonFinite:
    """批 D2 QA：fredgraph 末筆為 ±inf → 不得以 current=inf 回傳、不得入快取。"""

    @pytest.mark.parametrize("bad", ["inf", "-inf"])
    def test_inf_is_failure_and_not_cached(self, _snap, monkeypatch, bad):
        import src.data.proxy.proxy_helper as _ph
        csv_bad = f'observation_date,DGS10\n2026-09-29,4.10\n2026-09-30,{bad}\n'
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: _CsvResp(csv_bad))
        out = _snap.fetch_us10y_block(fred_api_key='')
        assert out['us10y']['current'] is None and '_err' in out['us10y']
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: _CsvResp(_DGS10_CSV))
        assert _snap.fetch_us10y_block(fred_api_key='')['us10y']['current'] == pytest.approx(4.12)
