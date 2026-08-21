"""v19.203 稽核修 — 資料診斷 🔴 項目根因修正守衛。

三修:
  #1 fetch_ndc_block 補官方 data.gov.tw 6099 ZIP fallback(原從 TBI 直跳 StockFeel 凍結文章)。
  #3 fetch_url 對 402/429/5xx fail loud(不再靜默回 None 記成「無回應」)。
  #4 資料診斷燈號圖例正名(🔴 分「真失敗」vs「落後/過舊」)。
"""
from __future__ import annotations

import pandas as pd

import src.data.macro.macro_snapshot as ms
import src.data.macro.tw_macro as tw


# ── #1 NDC 官方 ZIP fallback ───────────────────────────────────
def test_fetch_ndc_block_falls_back_to_official_dgtw_zip(monkeypatch):
    """TBI 失敗 → 應由官方 6099 ZIP 命中(不落到 StockFeel 凍結文章 / _err)。"""
    monkeypatch.setattr(tw, 'fetch_business_indicator_series', lambda **_k: None)
    _zdf = pd.DataFrame({
        'date': ['2026-05-01', '2026-06-01'],   # 升序,末列最新
        'value': [28, 31],
        'color': ['黃藍燈', '綠燈'],
    })
    monkeypatch.setattr(tw, '_dgtw_ndc_signal_from_zip', lambda label='ndc_signal': _zdf)

    out = ms.fetch_ndc_block()
    sig = out.get('ndc_signal')
    assert sig is not None, '應由官方 ZIP 命中,不應回 _err_ndc'
    assert sig['date'] == '2026-06-01'          # 末列最新(非卡在舊月)
    assert sig['score'] == 31
    assert sig['signal'] == '綠燈'               # 官方 monitoring_color 帶入
    assert 'data.gov.tw:6099' in sig['source']


def test_fetch_ndc_block_zip_before_stockfeel(monkeypatch):
    """官方 ZIP 有值時,StockFeel 不應被呼叫(官方優先 §2.1)。"""
    monkeypatch.setattr(tw, 'fetch_business_indicator_series', lambda **_k: None)
    monkeypatch.setattr(tw, '_dgtw_ndc_signal_from_zip',
                        lambda label='ndc_signal': pd.DataFrame(
                            {'date': ['2026-06-01'], 'value': [31], 'color': ['綠燈']}))
    _sf_called = {'hit': False}

    def _boom_fu(*_a, **_k):
        _sf_called['hit'] = True          # StockFeel/MacroMicro 走 fetch_url
        return None
    # patch 真正持有者 proxy_helper.fetch_url,**不要** patch `src.data.proxy.fetch_url`
    # ——後者是 PEP 562 __getattr__ 轉發,monkeypatch teardown 會把它變成具體屬性遮蔽
    # 轉發器,污染整包(test_zz_proxy_pollution_lock 專門守這個;v19.74/v19.113 前科)。
    # fetch_ndc_block 於呼叫時 `from src.data.proxy import fetch_url`,轉發器仍會解析到本 mock。
    monkeypatch.setattr('src.data.proxy.proxy_helper.fetch_url', _boom_fu)

    ms.fetch_ndc_block()
    assert _sf_called['hit'] is False, 'ZIP 命中後不應再打 StockFeel/MacroMicro(fetch_url)'


# ── #3 / #4 原始碼守衛(fail-loud + 圖例正名)──────────────────────
def test_proxy_fetch_url_fail_loud_on_non_200():
    src = _read('src/data/proxy/proxy_helper.py')
    assert '非 200/403/407' in src, 'fetch_url 應對非 200/403/407 狀態 fail loud(log 狀態碼)'


def test_diag_legend_distinguishes_stale_from_failure():
    src = _read('src/ui/pages/health_inspector.py')
    # 兩處圖例(頂部 :363 + 異常清單 :1603)都應把「落後/過舊(≠程式當掉)」與「真失敗」分開。
    # 兩處措辭略異(「不是程式當掉」/「非程式當掉」),共同子字串「程式當掉」。
    assert src.count('程式當掉') >= 2, '兩處燈號圖例都應標明「落後N期≠程式當掉」'
    assert '抓不到／過舊' in src


def _read(path: str) -> str:
    with open(path, encoding='utf-8') as f:
        return f.read()
