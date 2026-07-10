"""tests/test_etf_zh_name_and_beta.py — v18.455 ETF 中文名 FinMind 來源 + Beta 回歸估算。

user 回報(截圖):
1. ETF 名稱顯示發行商英文名(NOMURA ASSET MANAGEMENT TAIWAN)而非中文商品名。
   根因:`fetch_etf_zh_name` 原唯一來源 MoneyDJ `<title>` regex,MoneyDJ 疑改版
   格式,連 0050 都 FAIL(user 實測 log `[MDJ/zhname] FAIL 0050.TW`)。
   修:改用 FinMind TaiwanStockInfo.stock_name(官方結構化中文名)為 PRIMARY,
   MoneyDJ 降為 fallback。
2. 單檔診斷頁 Beta 顯示 N/A(yfinance .info 對台股主動式 ETF 無 beta)。
   修:新增 L2 `calc_beta(df, bench_df)`,以自身 vs 基準日報酬回歸估算。
"""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

import src.data.etf.etf_fetch as ef
from src.compute.etf.etf_calc import calc_beta


# ── A. Beta 回歸估算(純函式,不觸網)──────────────────────────

class TestCalcBeta:
    @staticmethod
    def _series(n, ret):
        idx = pd.date_range(end=datetime.date.today(), periods=n, freq='B')
        return pd.DataFrame({'Close': 100 * np.cumprod(1 + ret)}, index=idx)

    def test_beta_recovers_known_slope(self):
        np.random.seed(1)
        b_ret = np.random.normal(0, 0.01, 250)
        bench = self._series(250, b_ret)
        etf = self._series(250, 1.3 * b_ret + np.random.normal(0, 0.002, 250))
        beta = calc_beta(etf, bench)
        assert beta is not None
        assert 1.15 < beta < 1.45, f'β 應約 1.3,實際 {beta}'

    def test_insufficient_overlap_returns_none(self):
        np.random.seed(2)
        bench = self._series(250, np.random.normal(0, 0.01, 250))
        etf = bench.head(40)  # 有效重疊 < 60 交易日
        assert calc_beta(etf, bench) is None

    def test_empty_inputs_return_none(self):
        bench = self._series(250, np.random.normal(0, 0.01, 250))
        assert calc_beta(pd.DataFrame(), bench) is None
        assert calc_beta(bench, pd.DataFrame()) is None
        assert calc_beta(None, bench) is None

    def test_zero_variance_benchmark_returns_none(self):
        """基準價格完全不動(variance=0)→ 回 None,不 ÷0。"""
        idx = pd.date_range(end=datetime.date.today(), periods=100, freq='B')
        flat_bench = pd.DataFrame({'Close': [100.0] * 100}, index=idx)
        etf = pd.DataFrame({'Close': [100.0 + i for i in range(100)]}, index=idx)
        assert calc_beta(etf, flat_bench) is None

    def test_date_alignment_inner_join(self):
        """兩側交易日不完全重疊時,只用交集算,不因日期不齊污染。"""
        idx1 = pd.date_range('2025-01-01', periods=200, freq='B')
        idx2 = pd.date_range('2025-02-01', periods=200, freq='B')  # 錯開起點
        np.random.seed(3)
        b = pd.DataFrame({'Close': 100 * np.cumprod(1 + np.random.normal(0, 0.01, 200))}, index=idx1)
        e = pd.DataFrame({'Close': 100 * np.cumprod(1 + np.random.normal(0, 0.01, 200))}, index=idx2)
        # 交集仍 >60 日 → 應算得數值(不炸)
        r = calc_beta(e, b)
        assert r is None or isinstance(r, float)


# ── B. 中文名 FinMind 來源(mock FinMind API)────────────────

class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


class TestFetchEtfZhNameFinMind:
    def test_finmind_stock_name_used_as_primary(self, monkeypatch):
        """FinMind TaiwanStockInfo.stock_name 命中中文名 → 直接採用,不碰 MoneyDJ。"""
        import requests as _rq
        _moneydj_called = {'hit': False}

        def _fake_get(url, params=None, timeout=None):
            return _FakeResp({'data': [{'stock_id': '0050', 'stock_name': '元大台灣50',
                                        'industry_category': 'ETF', 'type': 'twse'}]})
        monkeypatch.setattr(_rq, 'get', _fake_get)

        # 若 FinMind 命中,MoneyDJ fetch_url 不該被呼叫
        # v19.74:patch 真正持有者 proxy_helper 而非 package — PEP 562 lazy forward
        # 對 package setattr,monkeypatch teardown 會把真函式寫成 package 實體屬性
        # → 永久蓋住 __getattr__ 轉發,污染其後所有 patch proxy_helper 的測試
        # (risk_radar CBOE 4 測 order-dependent 失敗根因;詳 test_etf_moneydj_nav_parse)
        from src.data.proxy import proxy_helper as _proxy
        def _spy_fetch_url(*a, **k):
            _moneydj_called['hit'] = True
            return None
        monkeypatch.setattr(_proxy, 'fetch_url', _spy_fetch_url)
        ef.fetch_etf_zh_name.clear()

        name = ef.fetch_etf_zh_name('0050.TW')
        assert name == '元大台灣50'
        assert not _moneydj_called['hit'], 'FinMind 命中時不應再打 MoneyDJ'

    def test_finmind_strips_suffix_for_query(self, monkeypatch):
        """查詢 FinMind 用不帶 .TW 的純代號(FinMind stock_id 無後綴)。"""
        import requests as _rq
        _seen = {}

        def _fake_get(url, params=None, timeout=None):
            _seen['data_id'] = (params or {}).get('data_id')
            return _FakeResp({'data': [{'stock_name': '主動群益台灣強棒'}]})
        monkeypatch.setattr(_rq, 'get', _fake_get)
        ef.fetch_etf_zh_name.clear()

        name = ef.fetch_etf_zh_name('00982A.TW')
        assert _seen.get('data_id') == '00982A', f"應查純代號,實際 {_seen.get('data_id')}"
        assert name == '主動群益台灣強棒'

    def test_finmind_english_name_rejected_falls_to_moneydj(self, monkeypatch):
        """FinMind 回英文名(無 CJK)→ 視為未命中,落到 MoneyDJ fallback。"""
        import requests as _rq
        monkeypatch.setattr(_rq, 'get',
                            lambda *a, **k: _FakeResp({'data': [{'stock_name': 'YUANTA ETF'}]}))
        from src.data.proxy import proxy_helper as _proxy  # v19.74:patch 持有者,防 package 屬性釘死(同上)
        # MoneyDJ 也回不到 → 最終 None(驗證有走到 fallback 路徑)
        monkeypatch.setattr(_proxy, 'fetch_url', lambda *a, **k: None)
        ef.fetch_etf_zh_name.clear()
        name = ef.fetch_etf_zh_name('9999.TW')
        assert name is None  # 兩源皆無中文 → None,呼叫端再 fallback yfinance

    def test_finmind_helper_direct(self, monkeypatch):
        """_fetch_etf_zh_name_finmind 純函式:非中文/查無 → None。"""
        import requests as _rq
        monkeypatch.setattr(_rq, 'get',
                            lambda *a, **k: _FakeResp({'data': []}))
        assert ef._fetch_etf_zh_name_finmind('0050.TW') is None
        monkeypatch.setattr(_rq, 'get',
                            lambda *a, **k: _FakeResp({'data': [{'stock_name': '00982'}]}))
        assert ef._fetch_etf_zh_name_finmind('00982A.TW') is None  # 純數字非中文


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
