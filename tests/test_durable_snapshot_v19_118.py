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


# ══════════════════════════════════════════════════════════════════════
# committed seed 檔本體的守衛（2026-09-05 去凍結值重寫）
# ══════════════════════════════════════════════════════════════════════
#
# 【為什麼這裡不能釘死一個值】
# `data_cache/macro_last_good/tw_pmi.json` 是 **cron 每天在寫的活檔案**
# （`.github/workflows/update_macro_history.yml` cron `0 9 * * *`
#   → `scripts/update_macro_history.py` → `macro_core._macro_durable_save`）。
# 實測 2026-08-28 ~ 2026-09-04 逐日都有 commit 覆寫它。
# 原本這裡寫死 `value == 60.7` / `date == '2026-06-01'`，是 2026-06 那筆人工
# seed 的字面快照；上游一旦真的抓回來（現況：2026-08 的 62.5，
# source=data.gov.tw/6100），CI 就轉紅 —— 紅的不是機制壞了，是**測試把一個
# 會被刷新的值當常數**。
#
# ⛔ 因此**不得**把它改成 `== 62.5`：那只是把同一顆地雷重新埋好，
#    下一次 cron 刷新（最慢一個月，PMI 是月頻）就再炸一次。
# ✅ 這裡要守的是「**這個檔誠不誠實**」這個性質，不是它今天剛好等於多少：
#    值域合理、資料日可解析且不在未來、provenance 在既有來源 SSOT 內、帶 cached_at。
#    這四條**不隨時間腐爛** —— 它們對 cron 明天寫進來的任何一筆合法資料都成立。
#
# 【刻意不加的一條】這裡**不驗**「seed 有多新」。
# 那屬於新鮮度，已由兩個鄰居各自守著，重複驗只會製造第三顆時間炸彈：
#   - `tests/test_macro_last_good_expiry.py` —— TTL 到期前 21 天預警（含 cached_at 可解析性）
#   - `tests/test_export_pmi_freshness_gate.py` —— 過期良值不得外送下游
def _pmi_source_whitelist() -> list[str]:
    """來源白名單一律取自 production SSOT `macro_core.PMI_SOURCE_REGISTRY`（§3.3 反捏造）。

    不在本檔另寫一份名單:新增/移除來源時 registry 改一處,本測試自動跟上。
    """
    from src.data.macro.macro_core import PMI_SOURCE_REGISTRY
    return [_name for _name, _fn in PMI_SOURCE_REGISTRY]


def test_seed_file_honest_and_valid():
    """committed seed 檔:值域 + 資料日 + 誠實 provenance（**不驗字面值**,理由見上方區塊註）。"""
    seed = json.loads(
        (REPO / 'data_cache/macro_last_good/tw_pmi.json').read_text(encoding='utf-8'))

    # (1) 值域 —— §3.2 PMI ∈ [30,70]
    assert seed.get('value') is not None, 'seed 無值 → 等於沒有 last-good（§1 不寫空值）'
    assert 30 <= seed['value'] <= 70, f"PMI 須 ∈ [30,70]（§3.2）,實得 {seed['value']!r}"

    # (2) 資料日可解析,且**不得晚於今天** —— 未來日期是捏造（§1）
    #     這條不會腐爛:時間往前走只會讓「不在未來」更容易成立。
    #     且它真的守得到東西 —— 各 handler 的年齡檢查寫成
    #     `(today - last_date).days <= max_age_days`,資料日若在未來,天數為負仍會通過。
    _raw_date = seed.get('date')
    assert _raw_date, 'seed 缺 date 欄 → 下游無從判定它是哪一期（§1）'
    try:
        _as_of = datetime.date.fromisoformat(str(_raw_date))
    except ValueError:
        raise AssertionError(f'seed date={_raw_date!r} 無法解析為日期')
    assert _as_of <= datetime.date.today(), (
        f'seed date={_as_of} 晚於今天 → 未來日期的觀測值不存在,是捏造（§1）')

    # (3) provenance 必須存在、非空,且落在既有來源 SSOT 內（§2.2）
    #
    #     ⚠️ 比對規則是「**有邊界的前綴**」：`_src == n` 或 `_src.startswith(n + '/')`,
    #     **不是**裸的 `startswith(n)`,也不是 `in`。三者的差別是這條斷言的全部價值:
    #
    #       source                      `in`   裸 startswith   有邊界前綴（現行）
    #       ─────────────────────────── ────── ────────────── ──────────────────
    #       data.gov.tw/6100（真來源）   PASS       PASS             PASS
    #       CIER / NDC / MoneyDJ …      PASS       PASS             PASS
    #       stale-cache(CIER)           PASS        red              red
    #       CIER 官方公布 2026-06        PASS       PASS             red   ←★
    #       NDC 我自己編的               PASS       PASS             red
    #       data.gov.tw-FABRICATED       red       PASS             red
    #
    #     ★ 那一列**就是本檔要防的原始事故**:`test_export_pmi_freshness_gate.py`
    #       檔頭記載的那筆人工 seed,source 正是 `"CIER 官方公布 2026-06"`。
    #       裸 startswith 會**原封放行它** —— 一個宣稱在擋假來源、卻放行事故本尊的
    #       守衛，比沒有守衛更危險（§1）。故加上邊界。
    #
    #     真實來源不受影響:8 個 registry handler 實際吐出的 7 個相異字面值
    #     （`CIER-EN` / `data.gov.tw/6100` / `NDC` / `CIER` / `StockFeel` /
    #       `Cnyes` / `MoneyDJ`）在新規則下全綠 —— `/` 是唯一被允許的延伸邊界,
    #     因為 `data.gov.tw/6100` 這種「來源/資料集編號」是既有寫法。
    _src = str(seed.get('source', '')).strip()
    assert _src, 'seed 缺 source → 無 provenance（§2.2）'
    _allowed = _pmi_source_whitelist()
    assert any(_src == _n or _src.startswith(_n + '/') for _n in _allowed), (
        f'seed source={_src!r} 不是 PMI_SOURCE_REGISTRY 任一來源名'
        f'（或其 `<來源名>/<資料集>` 形式）:{_allowed}\n'
        '三種可能,都不該靠放寬本斷言來放行:\n'
        '  (a) 它是**人工 seed 或自由文字**（如 "CIER 官方公布 2026-06"）→ 正是本條要擋的,\n'
        '      修的是寫入端,不是這裡;\n'
        '  (b) 它是 **stale 被回存**（如 "stale-cache(CIER)"）→ §1 造假,cron 明文只回存 live hit;\n'
        '  (c) 真的新增了來源 → 該 handler 回傳的 source 必須**等於**它的 registry 名稱,\n'
        '      或為 `<registry 名稱>/<資料集>`。\n'
        '⚠️ 已知既有耦合:registry 第 7 項登記 `CIER-cid8`,但 `_pmi_src_cier8` 實際回傳 `CIER`,\n'
        '   靠兄弟項 `CIER` 通過本條（另案處理,本測試不因此放寬）。'
    )

    # (4) cached_at 必須在 —— `_macro_cache_load` 靠它算 TTL,缺了整筆會被靜默跳過。
    #     （可解析性由 tests/test_macro_last_good_expiry.py 守,此處不重複。）
    assert 'cached_at' in seed, 'seed 缺 cached_at → _macro_cache_load 會當壞檔跳過'
