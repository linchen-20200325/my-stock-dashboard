# -*- coding: utf-8 -*-
"""v19.119 — PMI 8 源並行賽跑「硬上限」回歸鎖 + 出口 timeout fit budget。

決定性根因(user 部署 v19.117/118 後 PMI/出口**仍**待取得):
- macro_trio_orchestrator 給每個 block **70s inner budget**,逾時即 cancel。
- v19.116 把 dgtw metadata timeout 放寬到 25s×2 attempts×3 URL = 最壞 ~150s,
  而 fetch_tw_pmi 原碼 `for _fut: _fut.result()` **無限等最慢源** → 雲端
  data.gov.tw「連得上但 hang」時 fetch_tw_pmi 要 ~150s 才回 → orchestrator 70s
  就砍掉整個 block → **v19.118 的 durable seed 根本讀不到** → 卡片「待取得」。
- 即 v19.116(慢 timeout)反噬 v19.118(durable):fetch 在回落 durable 前就被砍。

修:fetch_tw_pmi 用 as_completed(deadline=45s) + shutdown(wait=False),慢源背景
自生自滅、主流程準時回 → durable fallback 生效。出口鏈(sequential)則收 timeout
fit 70s budget(customs 15/1、metadata 10/1、CSV 12/1)。

三個最容易出錯的輸入(§6):
1. 某源 hang 遠超 deadline → fetch_tw_pmi 必須在 deadline+餘裕內回(不得無限等)
2. 逾時且有 durable → 回 durable seed 值帶 is_stale(不得回 None)
3. deadline 必須 < orchestrator 70s inner budget(否則 block 仍被砍)
"""
from __future__ import annotations

import datetime
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent


def _write(dirpath: Path, key: str, payload: dict):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f'{key}.json').write_text(
        json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def test_deadline_constant_under_orchestrator_budget():
    """race deadline 必須 < macro_trio inner_pool_timeout_s(預設 70s),且不能太短。"""
    import src.data.macro.macro_core as mc
    # orchestrator 預設 inner budget 70s(macro_trio_orchestrator.py:28)
    orch = (REPO / 'src/services/macro_trio_orchestrator.py').read_text(encoding='utf-8')
    assert 'inner_pool_timeout_s: int = 70' in orch, 'orchestrator budget 假設漂移,請同步'
    assert mc._PMI_RACE_DEADLINE_S < 70, 'race deadline 須 < orchestrator 70s budget'
    assert mc._PMI_RACE_DEADLINE_S >= 20, 'deadline 太短會殺掉正常慢站(data.gov.tw 12-18s)'


def test_bounded_race_returns_within_deadline_uses_durable(tmp_path):
    """某源 hang 遠超 deadline → fetch_tw_pmi 在 deadline+餘裕內回 durable seed。"""
    import src.data.macro.macro_core as mc
    dur = tmp_path / 'dur'
    _write(dur, 'tw_pmi', {'value': 60.7, 'date': '2026-06-01',
                           'source': 'CIER 官方公布 2026-06',
                           'cached_at': datetime.datetime.now().isoformat()})
    _stop = threading.Event()

    def _slow_source(today, age, errs):
        _stop.wait(60)        # 遠超 deadline;測試結束由 _stop.set() 即時釋放
        return None

    try:
        with patch.object(mc, '_PMI_RACE_DEADLINE_S', 2), \
             patch.object(mc, 'PMI_SOURCE_REGISTRY', [('slow_hang', _slow_source)]), \
             patch.object(mc, '_MACRO_CACHE_DIR', str(tmp_path / 'eph')), \
             patch.object(mc, '_MACRO_DURABLE_DIR', str(dur)):
            t0 = time.monotonic()
            out = mc.fetch_tw_pmi()
            elapsed = time.monotonic() - t0
        # deadline=2s → 應 ~2s 回(給 8s 餘裕),絕不能等到 60s
        assert elapsed < 15, f'race 未在 deadline 內回,實際 {elapsed:.1f}s(疑無限等最慢源)'
        assert out.get('value') == 60.7, f'逾時應回 durable seed;out={out}'
        assert out.get('is_stale') is True
    finally:
        _stop.set()


def test_bounded_race_fast_hit_still_works(tmp_path):
    """deadline 內就命中的快源 → 正常回該值(不受 deadline 影響、不誤走 durable)。"""
    import src.data.macro.macro_core as mc

    def _fast_hit(today, age, errs):
        return {'value': 58.9, 'date': '2026-06-01', 'label': 'x',
                'source': 'fast', 'series_id': 'z'}

    with patch.object(mc, '_PMI_RACE_DEADLINE_S', 30), \
         patch.object(mc, 'PMI_SOURCE_REGISTRY', [('fast', _fast_hit)]), \
         patch.object(mc, '_MACRO_CACHE_DIR', str(tmp_path / 'eph')), \
         patch.object(mc, '_MACRO_DURABLE_DIR', str(tmp_path / 'dur')):
        out = mc.fetch_tw_pmi()
    assert out['value'] == 58.9 and not out.get('is_stale'), '快源命中應回 live 值'


def test_bounded_race_structure_present():
    """碼結構鎖:as_completed(deadline) + shutdown(wait=False) 必須都在。"""
    mc = (REPO / 'src/data/macro/macro_core.py').read_text(encoding='utf-8')
    assert '_as_completed_pmi(_fut2name, timeout=_PMI_RACE_DEADLINE_S)' in mc
    assert 'shutdown(wait=False)' in mc, '慢 thread 不可 join(否則 block ~150s)'
