# -*- coding: utf-8 -*-
"""v19.118 — PMI durable（committed）快照回歸鎖。

決定性背景（user 5 張圖實錘 + smoke run 29223581269）:
- NAS / proxy / 直連 / FinMind / TWSE / Yahoo / Gemini 全 200 → **問題 100% 不在連線**。
- `fetch_tw_pmi` 監控恆綠但回 `value=None`（假綠燈:回 dict 不拋例外 → 舊 @monitored 記 ok）。
- 真根因:v18.225 的 stale-cache 存在 **`cache/`（Streamlit Cloud ephemeral 磁碟）**,
  container recycle 即抹 → 全敗時 `_macro_cache_load` 找不到 → 卡片「待取得」。
- 修:加 durable 層 `data_cache/macro_last_good/`（committed，隨 deploy 帶上;cron 寫 + commit）,
  `_macro_cache_load` 兩層 fallback（ephemeral → durable）。並 seed 當月 CIER 官方值 60.7。
  + `@monitored` success_check 治假綠燈（value=None → 🔴）。

三個最容易出錯的輸入（§6）:
1. ephemeral `cache/` 空（雲端 recycle 後）+ durable 有 → 須讀到 durable（不得回 None）
2. durable 過期（cached_at > 90 天）→ 須回 None（§1 不把 3 個月前的值當現在）
3. 全 8 源失敗 + durable 存在 → fetch_tw_pmi 回 value=60.7 帶 is_stale;監控綠。
   全 8 源失敗 + durable 也無 → 回 value=None;監控 🔴（success_check 治假綠燈）。
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent


def _write(dirpath: Path, key: str, payload: dict):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f'{key}.json').write_text(
        json.dumps(payload, ensure_ascii=False), encoding='utf-8')


class TestDurableLoad:
    def test_reads_durable_when_ephemeral_absent(self, tmp_path):
        """雲端 recycle 後 cache/ 空 → 須讀到 durable data_cache/。"""
        import src.data.macro.macro_core as mc
        eph = tmp_path / 'eph'
        dur = tmp_path / 'dur'
        _write(dur, 'tw_pmi', {'value': 58.3, 'date': '2026-05-01',
                               'cached_at': datetime.datetime.now().isoformat()})
        with patch.object(mc, '_MACRO_CACHE_DIR', str(eph)), \
             patch.object(mc, '_MACRO_DURABLE_DIR', str(dur)):
            out = mc._macro_cache_load('tw_pmi')
        assert out is not None and out['value'] == 58.3, 'durable 應被讀到'

    def test_ephemeral_preferred_over_durable(self, tmp_path):
        """兩層都有 → 先取 ephemeral（session 內最新）。"""
        import src.data.macro.macro_core as mc
        eph = tmp_path / 'eph'
        dur = tmp_path / 'dur'
        now = datetime.datetime.now().isoformat()
        _write(eph, 'tw_pmi', {'value': 61.0, 'cached_at': now})
        _write(dur, 'tw_pmi', {'value': 58.3, 'cached_at': now})
        with patch.object(mc, '_MACRO_CACHE_DIR', str(eph)), \
             patch.object(mc, '_MACRO_DURABLE_DIR', str(dur)):
            out = mc._macro_cache_load('tw_pmi')
        assert out['value'] == 61.0, 'ephemeral 應優先'

    def test_expired_durable_returns_none(self, tmp_path):
        """durable cached_at > 90 天 → 回 None（§1 不把過期值當現在）。"""
        import src.data.macro.macro_core as mc
        eph = tmp_path / 'eph'
        dur = tmp_path / 'dur'
        old = (datetime.datetime.now() - datetime.timedelta(days=120)).isoformat()
        _write(dur, 'tw_pmi', {'value': 58.3, 'cached_at': old})
        with patch.object(mc, '_MACRO_CACHE_DIR', str(eph)), \
             patch.object(mc, '_MACRO_DURABLE_DIR', str(dur)):
            out = mc._macro_cache_load('tw_pmi')
        assert out is None, '過期 durable 應回 None'

    def test_durable_save_writes_to_data_cache(self, tmp_path):
        import src.data.macro.macro_core as mc
        dur = tmp_path / 'dur'
        with patch.object(mc, '_MACRO_DURABLE_DIR', str(dur)):
            mc._macro_durable_save('tw_pmi', {'value': 60.7, 'date': '2026-06-01'})
            loaded = json.loads((dur / 'tw_pmi.json').read_text(encoding='utf-8'))
        assert loaded['value'] == 60.7
        assert 'cached_at' in loaded, 'durable save 須蓋 cached_at'


class TestFetchAllFailFallback:
    """全 8 源失敗 → durable fallback 端到端（mock 全源 None，不觸網）。"""

    def test_allfail_with_durable_returns_stale_value(self, tmp_path):
        import src.data.macro.macro_core as mc
        eph = tmp_path / 'eph'
        dur = tmp_path / 'dur'
        _write(dur, 'tw_pmi', {'value': 60.7, 'date': '2026-06-01',
                               'source': 'CIER 官方公布 2026-06',
                               'cached_at': datetime.datetime.now().isoformat()})
        fake_registry = [('fake_dead', lambda today, age, errs: None)]
        with patch.object(mc, 'PMI_SOURCE_REGISTRY', fake_registry), \
             patch.object(mc, '_MACRO_CACHE_DIR', str(eph)), \
             patch.object(mc, '_MACRO_DURABLE_DIR', str(dur)):
            out = mc.fetch_tw_pmi()
        assert out['value'] == 60.7, '全敗應回 durable seed 值'
        assert out.get('is_stale') is True, '須帶 is_stale 旗標（§2.4）'
        assert 'stale-cache' in out['source']
        # 假綠燈治理:有值（含 stale）→ 監控綠
        from shared.fetch_monitor import get_monitor_registry
        assert get_monitor_registry()['fetch_tw_pmi']['last_status'] == 'ok'

    def test_allfail_without_durable_returns_none_and_red(self, tmp_path):
        import src.data.macro.macro_core as mc
        eph = tmp_path / 'eph'      # 兩層都空
        dur = tmp_path / 'dur'
        fake_registry = [('fake_dead', lambda today, age, errs: None)]
        with patch.object(mc, 'PMI_SOURCE_REGISTRY', fake_registry), \
             patch.object(mc, '_MACRO_CACHE_DIR', str(eph)), \
             patch.object(mc, '_MACRO_DURABLE_DIR', str(dur)):
            out = mc.fetch_tw_pmi()
        assert out.get('value') is None, '連 durable 都無 → 誠實回 None'
        assert '_err_pmi' in out
        # 假綠燈治理:value=None → 監控 🔴（治 user 圖中的假綠燈）
        from shared.fetch_monitor import get_monitor_registry
        assert get_monitor_registry()['fetch_tw_pmi']['last_status'] == 'failed'


def test_seed_file_honest_and_valid():
    """committed seed 檔:值域合理 + 誠實 provenance（CIER 官方，非捏造）。"""
    seed = json.loads(
        (REPO / 'data_cache/macro_last_good/tw_pmi.json').read_text(encoding='utf-8'))
    assert 30 <= seed['value'] <= 70, 'PMI 須 ∈ [30,70]（§3.2）'
    assert seed['value'] == 60.7, 'CIER 2026-06 官方公布值'
    assert seed['date'] == '2026-06-01'
    assert 'CIER' in seed['source'], 'provenance 須標官方來源（§2.2）'
    assert 'cached_at' in seed
