# -*- coding: utf-8 -*-
"""v19.111 — 出口 YoY 全敗 fail-trace（`_err_export`）行為鎖。

背景（user 2026-07-12 回報「外需動能溫度計 台灣出口 YoY 無資料」）：
fetch_export_block 全敗原本回 `{}` — trio orchestrator 的 `if _part:` 連 merge
都進不去，導致 section_mid 錯誤碼面板(v18.194)與 health_inspector 的
`_err_export` 讀取端是**死鍵**（7 個 macro fetcher 中唯一漏接診斷的）。
v19.111 補 per-tier fail token，全敗回 `{'_err_export': 'src:err | ...'}`。

三個最容易出錯的輸入(§6)：
1. 全來源斷線（fetch_url 全回 None + session.get 全炸）→ 必回 _err_export，
   且不得夾帶 tw_export 數值 key（§1 不捏造）
2. 無 FRED key → FRED-API 段 skip 也要在 token 留痕（診斷不留盲區）
3. token 需含各 tier 標籤 → user 截圖即可定位死在哪一段
"""
from __future__ import annotations

import pytest


class _BoomSession:
    """CKAN 段用的 requests.Session 替身：任何 get 一律拋線路錯誤。"""

    def __init__(self):
        self.headers = {}
        self.verify = True

    def get(self, *a, **k):
        raise ConnectionError('boom: 測試模擬全斷線')


@pytest.fixture()
def _all_sources_down(monkeypatch):
    """讓全部 tier 失敗：fetch_url→None、proxy session→炸、無 FRED key。

    ⚠️ patch 目標必須是真正持有者 `proxy_helper`,**不可** patch package
    `src.data.proxy`(PEP 562 lazy forward,無實體 fetch_url 屬性)— 對 package
    setattr 後 teardown「還原」會把真函式寫成 package 實體屬性,永久遮蔽轉發,
    害其後所有 patch proxy_helper 的測試(etf_moneydj_nav_parse 等)打真網路
    (v19.74 已記載之地雷,v19.112 CI 紅實錘重演;回歸鎖見
    tests/test_zz_proxy_pollution_lock.py)。"""
    import src.data.macro.macro_snapshot as snap
    from src.data.proxy import proxy_helper as _ph

    monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
    monkeypatch.setattr(snap, '_make_proxy_session', lambda: _BoomSession())
    # st.cache_data 以參數為 key，先清避免吃到其他測試/先前呼叫的快取
    try:
        snap.fetch_export_block.clear()
    except Exception:
        pass
    return snap


class TestExportFailTrace:
    def test_all_fail_returns_err_token_no_value(self, _all_sources_down):
        snap = _all_sources_down
        out = snap.fetch_export_block(fred_api_key='', finmind_token='')
        assert 'tw_export' not in out, '全敗不得貢獻 tw_export 數值（§1 不捏造）'
        assert isinstance(out.get('_err_export'), str) and out['_err_export'], (
            '全敗必須回非空 _err_export 診斷 token（v18.194 錯誤碼面板才有料）')

    def test_err_token_covers_each_tier(self, _all_sources_down):
        snap = _all_sources_down
        out = snap.fetch_export_block(fred_api_key='', finmind_token='')
        tok = out['_err_export']
        # v19.112:MOF-CSV 段依探針實錘下架後拔除,tier 清單同步(6→5 段)
        for tier in ('stat.gov.tw', 'FRED-API',
                     'data.gov.tw/6053', 'FRED-CSV', 'CKAN'):
            assert tier in tok, f'{tier} 段失敗須在 token 留痕，token={tok!r}'
        # 無 key 場景：FRED-API 段要標 skip 而非無聲消失
        assert 'skip' in tok, 'FRED-API 無 key 應標 skip(無 FRED key)'

    def test_err_token_merges_into_macro_info_shape(self, _all_sources_down):
        """orchestrator `if _part: _r.update(_part)`：token dict 為 truthy 會被
        merge；`_err_*` 開頭不影響 `_all_failed` / MACRO_INFO_KEYS 判定。"""
        snap = _all_sources_down
        out = snap.fetch_export_block(fred_api_key='', finmind_token='')
        assert out, '回傳需為 truthy 才進得了 orchestrator merge'
        assert all(k.startswith('_') for k in out), (
            '全敗回傳只允許 _ 前綴診斷鍵（不得混入資料鍵）')


def test_ui_err_label_map_has_export_entry():
    """section_mid 錯誤碼面板的 `_err_export` 標籤已存在（本修復點亮它）。"""
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent /
            'src/ui/tabs/macro/section_mid.py').read_text(encoding='utf-8')
    assert "'_err_export': '台灣出口 YoY'" in body
