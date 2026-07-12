# -*- coding: utf-8 -*-
"""v19.106 — 大工程清單 🟢 兩項(股票側)回歸鎖。

- ⑨ ETF 夏普 rf 動態化:寫死 5.33 → SSOT fallback + L3 注入即時 FEDFUNDS
  (L2 純函式不 I/O,setter 注入,對齊 Fund repo fund_service._RF_ANNUAL pattern)
- ①a 連線層 thread-local Session 複用:fetch_url 原每呼叫新建 Session
  (批次抓重複 TLS 握手)→ per-thread 複用(比照 Fund infra/proxy v19.333 F6)
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding='utf-8')


def _mk_price_df(n: int = 300) -> pd.DataFrame:
    """波動非零的價格序列(讓 sharpe 分母 > 0,結果對 rf 敏感)。"""
    close = 100.0 + np.cumsum(np.tile([1.0, -0.4], n // 2))
    return pd.DataFrame({'Close': close})


@pytest.fixture()
def _rf_restore():
    """測試會動模組級 rf — 前後還原,不汙染其他測試(§3.3 隔離精神)。"""
    from src.compute.etf import etf_calc
    _orig = etf_calc.get_risk_free_rate_pct()
    yield
    etf_calc.set_risk_free_rate_pct(_orig)


# ═════════════════════════════════════════════════════════════════
# ⑨ 夏普 rf 動態化
# ═════════════════════════════════════════════════════════════════
class TestSharpeRfDynamic:
    def test_default_equals_ssot_fallback(self):
        from shared.signal_thresholds import ETF_SHARPE_RF_FALLBACK_PCT
        from src.compute.etf.etf_calc import get_risk_free_rate_pct
        import math
        assert math.isclose(ETF_SHARPE_RF_FALLBACK_PCT, 5.33)  # 原行為零位移
        assert math.isclose(get_risk_free_rate_pct(), ETF_SHARPE_RF_FALLBACK_PCT)

    def test_setter_changes_calc_sharpe(self, _rf_restore):
        from src.compute.etf.etf_calc import calc_sharpe, set_risk_free_rate_pct
        df = _mk_price_df()
        base = calc_sharpe(df)                      # rf=5.33(fallback)
        set_risk_free_rate_pct(1.0)
        after = calc_sharpe(df)
        assert after == calc_sharpe(df, rf=1.0)     # 模組值生效
        assert after != base                         # rf 變 → 夏普變
        assert calc_sharpe(df, rf=5.33) == base      # 顯式傳值不受 setter 影響

    def test_setter_rejects_garbage(self, _rf_restore):
        from src.compute.etf.etf_calc import (
            get_risk_free_rate_pct, set_risk_free_rate_pct,
        )
        before = get_risk_free_rate_pct()
        set_risk_free_rate_pct('abc')     # 非數
        set_risk_free_rate_pct(-1.0)      # 負利率(拒收,fallback 語意)
        set_risk_free_rate_pct(999.0)     # 越界(防單位誤傳)
        set_risk_free_rate_pct(float('nan'))
        assert get_risk_free_rate_pct() == before, '非法值一律拒收,不腦補(§1)'

    def test_service_injects_live_fedfunds(self, _rf_restore, monkeypatch):
        import src.data.macro.macro_snapshot as ms
        from src.compute.etf.etf_calc import get_risk_free_rate_pct
        from src.services.etf_grp_compare_service import ensure_etf_rf_injected
        monkeypatch.setattr(
            ms, 'fetch_fed_funds_block',
            lambda fred_api_key='': {'fed_funds': {'current': 4.25}})
        assert ensure_etf_rf_injected() == 4.25
        assert get_risk_free_rate_pct() == 4.25

    def test_service_failure_keeps_fallback(self, _rf_restore, monkeypatch):
        import src.data.macro.macro_snapshot as ms
        from src.compute.etf.etf_calc import get_risk_free_rate_pct
        from src.services.etf_grp_compare_service import ensure_etf_rf_injected
        before = get_risk_free_rate_pct()
        monkeypatch.setattr(
            ms, 'fetch_fed_funds_block',
            lambda fred_api_key='': {'_err_fed_funds': 'all failed'})
        assert ensure_etf_rf_injected() is None
        assert get_risk_free_rate_pct() == before, 'FRED 全斷 → 維持 fallback(§1)'

    def test_no_inline_533_default_left(self):
        text = _src('src/compute/etf/etf_calc.py')
        assert 'rf: float = 5.33' not in text, '寫死預設應已 SSOT 化'
        assert 'ETF_SHARPE_RF_FALLBACK_PCT' in text

    def test_grp_compare_wired(self):
        assert 'ensure_etf_rf_injected' in _src('src/ui/etf/etf_tab_grp_compare.py')


# ═════════════════════════════════════════════════════════════════
# ①a thread-local Session 複用
# ═════════════════════════════════════════════════════════════════
class TestThreadLocalSession:
    def test_same_thread_reuses_session(self):
        from src.data.proxy.proxy_helper import _get_thread_session
        assert _get_thread_session(lean=True) is _get_thread_session(lean=True)
        assert _get_thread_session(lean=False) is _get_thread_session(lean=False)
        assert _get_thread_session(lean=True) is not _get_thread_session(lean=False), (
            'lean(無 Retry)與 retry 版須各自一份,不可混用')

    def test_other_thread_gets_own_session(self):
        from src.data.proxy.proxy_helper import _get_thread_session
        main_s = _get_thread_session(lean=True)
        box = {}
        t = threading.Thread(
            target=lambda: box.update(s=_get_thread_session(lean=True)))
        t.start()
        t.join()
        assert box['s'] is not main_s, 'Session 非跨執行緒安全 → per-thread 隔離'

    def test_fetch_url_uses_thread_session(self):
        text = _src('src/data/proxy/proxy_helper.py')
        assert '_get_thread_session(lean=(attempts <= 1))' in text
        # fetch_url 本體不應再逐呼叫新建 Session
        import inspect
        from src.data.proxy import proxy_helper
        body = inspect.getsource(proxy_helper.fetch_url)
        assert 'requests.Session()' not in body
