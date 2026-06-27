"""v18.332 Tier2 2-D slice 1：macro_snapshot.fetch_vix_block 抽出 + 單測。

把總經 VIX 抓取從 tab_macro 巨型 UI 函式下沉成 L1 純函式後，**首次可單測**
（mock yfinance → 驗證解析 + §1 失敗回診斷 token 不捏造）。
"""
from __future__ import annotations

import pandas as pd
import pytest

import macro_snapshot


class TestFetchVixBlock:
    def test_parses_synthetic_close(self, monkeypatch):
        import yfinance
        idx = pd.date_range('2026-04-01', periods=30, freq='D')
        df = pd.DataFrame({'Close': [15.0] * 29 + [22.0]}, index=idx)
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: df)
        out = macro_snapshot.fetch_vix_block()
        assert 'vix' in out and '_err_vix' not in out
        assert out['vix']['current'] == 22.0
        assert out['vix']['date'] == '2026-04-30'
        assert len(out['vix']['values']) <= 60

    def test_empty_returns_err_token_not_fabricated(self, monkeypatch):
        """§1：yfinance 回空 → 診斷 token，**不捏造**數值。"""
        import yfinance
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: pd.DataFrame())
        out = macro_snapshot.fetch_vix_block()
        assert out == {'_err_vix': 'yfinance empty'}
        assert 'vix' not in out

    def test_exception_returns_err_token(self, monkeypatch):
        import yfinance

        def _boom(*a, **k):
            raise RuntimeError('network down')

        monkeypatch.setattr(yfinance, 'download', _boom)
        out = macro_snapshot.fetch_vix_block()
        assert 'vix' not in out
        assert out['_err_vix'].startswith('network down')

    def test_too_few_rows(self, monkeypatch):
        import yfinance
        idx = pd.date_range('2026-04-01', periods=2, freq='D')
        df = pd.DataFrame({'Close': [15.0, 16.0]}, index=idx)
        monkeypatch.setattr(yfinance, 'download', lambda *a, **k: df)
        assert macro_snapshot.fetch_vix_block() == {'_err_vix': 'not enough data'}


class TestTabMacroWired:
    def test_tab_macro_imports_extracted_vix(self):
        src = open('tab_macro.py', encoding='utf-8').read()
        assert 'from macro_snapshot import fetch_vix_block as _fetch_vix' in src
        # 原 inline def 已移除（不得殘留兩份）
        assert 'def _fetch_vix' not in src
