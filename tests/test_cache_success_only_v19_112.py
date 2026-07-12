# -*- coding: utf-8 -*-
"""v19.112 — 「失敗不進快取」(user 核准提案①) 行為鎖。

病灶(user 2026-07-12 回報兩張總經卡「無資料」的機制面根因):六個總經 block
掛 @st.cache_data(ttl=1h) 且**失敗 dict 也被快取** — 一次上游打嗝(當日實錘:
dgtw 05:32 cron 死、14:13 探針活)凍存一小時,「🚀 一鍵更新」吃暖快取拿到的
仍是凍住的失敗。修法:_cache_success_only — 失敗以內部例外穿透 st.cache_data
(官方語意:拋例外不落快取),外層還原 err dict,caller 契約零改變。

三個最容易出錯的輸入(§6):
1. 失敗後上游復原 → 同參數再呼叫**必須真重抓**(舊行為會回凍住的失敗)
2. 成功後上游斷線 → TTL 內再呼叫**必須回快取成功**(效能/quota 契約不變)
3. 混合鍵(資料鍵+`_`診斷鍵)不得誤判為失敗
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


class _BoomSession:
    """CKAN 段 requests.Session 替身:任何 get 一律拋線路錯誤。"""

    def __init__(self):
        self.headers = {}
        self.verify = True

    def get(self, *a, **k):
        raise ConnectionError('boom: 測試模擬全斷線')


class _FakeResp:
    """stat.gov.tw 復原場景的 Response 替身(僅出口 Tier0 會用到的介面)。"""
    status_code = 200

    def __init__(self, text: str):
        self.text = text
        self.content = text.encode('utf-8')
        self.encoding = 'utf-8'


# 對照財政部 2026-07-09 公布之 6 月出口 YoY +40.3%(對帳基準,§4.3)
_HEAL_HTML = '中華民國統計資訊網 2026年6月 出口 年增率 40.3 % 統計指標'


@pytest.fixture()
def _snap(monkeypatch):
    import src.data.macro.macro_snapshot as snap
    monkeypatch.setattr(snap, '_make_proxy_session', lambda: _BoomSession())
    snap.fetch_export_block.clear()
    yield snap
    snap.fetch_export_block.clear()


class TestFailureNotCached:
    def test_failure_then_heal_then_break_full_cycle(self, _snap, monkeypatch):
        # ⚠️ patch 真正持有者 proxy_helper,不可 patch package src.data.proxy
        # (PEP 562 轉發,v19.74 地雷;詳見 test_zz_proxy_pollution_lock.py)
        from src.data.proxy import proxy_helper as _ph
        snap = _snap
        # ── 階段 1:全源斷線 → 誠實回 _err_export(且不落快取) ──
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
        out1 = snap.fetch_export_block(fred_api_key='', finmind_token='')
        assert 'tw_export' not in out1 and '_err_export' in out1

        # ── 階段 2:stat.gov.tw 復原 → 同參數再呼叫必須「真重抓」──
        # 舊行為(失敗進快取)此處會回凍住的 out1 → 本斷言就是凍結 bug 的棺材釘
        monkeypatch.setattr(_ph, 'fetch_url',
                            lambda *a, **k: _FakeResp(_HEAL_HTML))
        out2 = snap.fetch_export_block(fred_api_key='', finmind_token='')
        assert out2.get('tw_export', {}).get('source') == 'stat.gov.tw', (
            f'上游復原後必須重抓成功,不得回凍住的失敗;got={out2}')
        assert math.isclose(out2['tw_export']['yoy'], 40.3), '對帳:財政部 6 月 +40.3%'
        assert out2['tw_export']['date'] == '2026-06'

        # ── 階段 3:上游再斷線 → TTL 內必須回快取成功(效能契約不變) ──
        monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
        out3 = snap.fetch_export_block(fred_api_key='', finmind_token='')
        assert out3.get('tw_export', {}).get('yoy') == out2['tw_export']['yoy'], (
            '成功結果須照常入快取,TTL 內斷線也要回快取值')


class TestFailurePredicate:
    def test_predicate_shapes(self):
        from src.data.macro.macro_snapshot import _is_block_failure
        assert _is_block_failure({}) is True                       # 空 = 失敗
        assert _is_block_failure({'_err_pmi': 'x'}) is True        # 純診斷鍵 = 失敗
        assert _is_block_failure({'ism_pmi': {'value': 55.0}}) is False
        # 混合鍵(資料+診斷)= 成功,不得誤判
        assert _is_block_failure({'tw_export': {'yoy': 1.0},
                                  '_loaded_at': 'x'}) is False

    def test_clear_passthrough_exists(self):
        """強制重抓按鈕依賴 .clear();裝飾器必須透傳。"""
        from src.data.macro import macro_snapshot as snap
        for fn in (snap.fetch_vix_block, snap.fetch_cpi_block,
                   snap.fetch_fed_funds_block, snap.fetch_tw_pmi_block,
                   snap.fetch_ndc_block, snap.fetch_export_block):
            assert callable(getattr(fn, 'clear', None)), fn


def test_six_blocks_wrapped_source_scan():
    """六個總經 block 全掛 _cache_success_only;不得殘留裸 @st.cache_data。
    (m1b_m2 / us10y 失敗形狀不同(回 None / 資料鍵包 _err),本次不納入 —
    見 STATE v19.112;此掃描僅鎖定六個同形狀 block。)"""
    body = (REPO / 'src/data/macro/macro_snapshot.py').read_text(encoding='utf-8')
    for fn in ('fetch_vix_block', 'fetch_cpi_block', 'fetch_fed_funds_block',
               'fetch_tw_pmi_block', 'fetch_ndc_block', 'fetch_export_block'):
        seg = body.split(f'def {fn}(')[0].rstrip().splitlines()[-1]
        assert '_cache_success_only' in seg, (
            f'{fn} 應掛 @_cache_success_only(失敗不進快取),當前裝飾行:{seg}')
