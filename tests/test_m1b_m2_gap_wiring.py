"""tests/test_m1b_m2_gap_wiring.py — v18.454 M1B-M2 頂部燈號恆顯示「—」真回歸修。

production bug(user 截圖):總經頁頂部「M1B-M2 資金動能」恆顯示「—」(無資料),
但同一頁下方「策略3」區塊卻正確顯示「M1B-M2=-12.63% 負值→資金撤離」。

根因:`tw_macro.fetch_cbc_m1b_m2()` 本就算好 `gap = round(m1b_yoy - m2_yoy, 2)`,
但 `macro_snapshot.fetch_m1b_m2_block()` 重新打包成要寫入
`session_state['m1b_m2_info']` 的 dict 時,三個 return 路徑(CBC/FRED/IMF)全部
漏帶 'gap' 鍵。`macro_helpers.py` 算頂部燈號/KPI 卡是讀
`m1b_m2_info.get('gap')`(恆 None → 顯示「—」);而 section_long.py「策略3」
區塊是自己內聯重算 `m1b_yoy - m2_yoy`(不依賴此鍵),才會兩處不一致。

本測試 mock 三層各自的上游呼叫,驗證 fetch_m1b_m2_block() 回傳 dict 一律含
正確的 'gap' 鍵(= m1b_yoy - m2_yoy)。
"""
from __future__ import annotations

import pytest


def _unwrap(fn, *a, **k):
    """st.cache_data 裝飾函式測試時繞過快取直接呼叫底層邏輯。"""
    return fn.__wrapped__(*a, **k)


class TestTier0CbcGap:
    def test_gap_threaded_through_from_tw_macro(self, monkeypatch):
        import src.data.macro.macro_snapshot as ms
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: {'m1b_yoy': 1.2, 'm2_yoy': 13.83, 'gap': -12.63,
                     'tier_used': 1, 'is_proxy_tier': False},
        )
        r = _unwrap(ms.fetch_m1b_m2_block, '')
        assert r is not None
        assert r['gap'] == -12.63, f'gap 未正確透傳:{r}'
        assert r['m1b_yoy'] == 1.2 and r['m2_yoy'] == 13.83

    def test_gap_matches_m1b_minus_m2(self, monkeypatch):
        """數學驗算:gap 必須等於 m1b_yoy - m2_yoy(容差)。"""
        import src.data.macro.macro_snapshot as ms
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: {'m1b_yoy': 5.0, 'm2_yoy': 8.5, 'gap': -3.5,
                     'tier_used': 1, 'is_proxy_tier': False},
        )
        r = _unwrap(ms.fetch_m1b_m2_block, '')
        assert r['gap'] == pytest.approx(r['m1b_yoy'] - r['m2_yoy'], abs=1e-6)


class TestTier1FredGap:
    def test_gap_computed_inline_for_fred_path(self, monkeypatch):
        """Tier 0(CBC)失敗 → 落到 FRED,FRED 路徑本身沒有 gap 欄,須內聯算出。"""
        import pandas as pd
        import src.data.macro.macro_snapshot as ms

        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: (_ for _ in ()).throw(RuntimeError('CBC 全敗')),
        )

        class _FakeResp:
            status_code = 200
            def json(self):
                return {'observations': self._obs}

        def _fake_fetch_url(url, params=None, **kwargs):
            _series = params.get('series_id', '')
            _r = _FakeResp()
            if _series == 'MYAGM1TWA189S':
                _r._obs = [{'date': f'2024-{(i % 12) + 1:02d}-01', 'value': str(100 + i)}
                           for i in range(20)]
            else:
                _r._obs = [{'date': f'2024-{(i % 12) + 1:02d}-01', 'value': str(200 + i * 2)}
                           for i in range(20)]
            return _r

        monkeypatch.setattr('src.data.proxy.fetch_url', _fake_fetch_url)
        r = _unwrap(ms.fetch_m1b_m2_block, '')
        assert r is not None
        assert r['source'] == 'FRED'
        assert r['gap'] == pytest.approx(r['m1b_yoy'] - r['m2_yoy'], abs=1e-6)


class TestTier2ImfGap:
    def test_gap_computed_inline_for_imf_path(self, monkeypatch):
        """Tier 0/1 皆失敗 → 落到 IMF,IMF 路徑本身沒有 gap 欄,須內聯算出。"""
        import src.data.macro.macro_snapshot as ms

        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: (_ for _ in ()).throw(RuntimeError('CBC 全敗')),
        )

        class _FakeResp:
            status_code = 200
            def __init__(self, series, val):
                self._series, self._val = series, val
            def json(self):
                return {'values': {self._series: {'TW': {'2025': self._val, '2026': self._val + 1.0}}}}

        def _fake_fetch_url(url, **kwargs):
            if 'MANMM101' in url:
                return _FakeResp('MANMM101', 3.0)
            if 'MABMM301' in url:
                return _FakeResp('MABMM301', 9.0)
            return None

        # FRED 路徑也失敗(fetch_url 回 None)才會落到 IMF —— 用同一個 fake 分派
        def _dispatch(url, **kwargs):
            if 'stlouisfed' in url:
                return None
            return _fake_fetch_url(url, **kwargs)

        monkeypatch.setattr('src.data.proxy.fetch_url', _dispatch)
        r = _unwrap(ms.fetch_m1b_m2_block, '')
        assert r is not None
        assert r['source'].startswith('IMF')
        assert r['gap'] == pytest.approx(r['m1b_yoy'] - r['m2_yoy'], abs=1e-6)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
