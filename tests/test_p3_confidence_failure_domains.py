"""P3（2026-08-19）：信心分數的「假獨立性」—— 方案 C。

背景（實測，非推論）
--------------------
`calc_traffic_light` 的 5 個信心來源只有 **3 個獨立故障域**：

| 故障域 | 涵蓋項 | 舊公式一次失敗扣多少 conf |
|---|---|---|
| yfinance `^TWII` | score / jqavg / adl | **60 分（3/5）** |
| TWSE BFI82U | fnet | 20 分 |
| FinMind 期貨 + TAIFEX | li | 20 分 |

`jqavg` 與 `adl` 來自**同一次** `fetch_adl()` 的同一個 DataFrame；`score`
（`market_regime`）的價格骨幹與它吃的 `ad_ratio` 參數也是同一條 ^TWII 線。
於是舊的 `conf < 70` 數量門檻把「同一份資料掉了 2 個視角」判得比
「一整個獨立來源全滅」更嚴重 —— **方向是反的**。

本檔釘什麼
----------
1. 分組表是 SSOT，且與 `_conf_sources` 的項目代號完全對得起來（防漂移）。
2. `conf` 公式**一字未改**（畫面數字不變）—— 方案 C 的核心承諾。
3. 新 gate 的三個條件，逐條有反例。
4. **新 gate 相對舊 gate 是純放寬**：32 種組合中 12 種「擋→顯示」、
   **0 種**反向。這條斷言是刻意寫死的 —— 若日後有人改條件讓某個組合
   變嚴，本測試會紅燈，強迫他明確面對「這會讓原本看得到燈的日子看不到」。
"""
from __future__ import annotations

import inspect
from itertools import product

import pytest

from shared.signal_thresholds import (
    CONFIDENCE_SOURCE_COUNT,
    CONFIDENCE_SOURCE_GROUPS,
)

_KEYS = ('score', 'jqavg', 'fnet', 'li', 'adl')


def _new_gate_passes(ok: dict) -> bool:
    """複刻 `handlers._render_traffic_light` 的新擋燈條件（三條件全成立才顯示）。"""
    grp = {g: any(ok[k] for k in ks) for g, ks in CONFIDENCE_SOURCE_GROUPS.items()}
    return (
        grp['yfinance_twii']
        and (grp['twse_bfi82u'] or grp['finmind_taifex'])
        and (ok['score'] or ok['jqavg'])          # health 至少一條腿
    )


def _old_gate_passes(ok: dict) -> bool:
    return round(sum(ok.values()) / CONFIDENCE_SOURCE_COUNT * 100) >= 70


class TestGroupTableIsSSOT:
    def test_groups_cover_exactly_the_five_conf_sources(self):
        covered = [k for ks in CONFIDENCE_SOURCE_GROUPS.values() for k in ks]
        assert sorted(covered) == sorted(_KEYS), (
            f'分組表與 _conf_sources 項目對不起來：{sorted(covered)}')
        assert len(covered) == len(set(covered)), '同一項不可歸屬兩個故障域'
        assert len(covered) == CONFIDENCE_SOURCE_COUNT

    def test_conf_source_keys_match_macro_helpers(self):
        """分組表的代號必須真的出現在 `_conf_sources` 的第 3 元素裡。

        這條防的是「改了 macro_helpers 的代號但忘了改 SSOT」——
        那會讓 `_ok_by_key.get(k, False)` 靜默回 False，整組被判成掛掉。
        """
        from src.compute.macro import macro_helpers
        src = inspect.getsource(macro_helpers.calc_traffic_light)
        for key in _KEYS:
            assert f"'{key}')" in src, f'macro_helpers 找不到來源代號 {key!r}'

    def test_three_domains_not_five(self):
        assert len(CONFIDENCE_SOURCE_GROUPS) == 3
        assert len(CONFIDENCE_SOURCE_GROUPS['yfinance_twii']) == 3, (
            'score/jqavg/adl 同源於一次 ^TWII 抓取，必須同組')


class TestConfFormulaUnchanged:
    """方案 C 的核心承諾：畫面數字不變。"""

    def test_divisor_is_still_five(self):
        assert CONFIDENCE_SOURCE_COUNT == 5

    def test_all_five_present_is_100(self):
        ok = dict.fromkeys(_KEYS, True)
        assert round(sum(ok.values()) / CONFIDENCE_SOURCE_COUNT * 100) == 100

    def test_conf_formula_line_intact(self):
        from src.compute.macro import macro_helpers
        src = inspect.getsource(macro_helpers.calc_traffic_light)
        assert '/ CONFIDENCE_SOURCE_COUNT * 100)' in src, (
            'conf 公式被動了 —— 方案 C 明確承諾分母不動')


class TestNewGateConditions:
    @pytest.mark.parametrize('missing,expected,why', [
        ((), True, '全齊'),
        (('score', 'jqavg', 'adl'), False, '^TWII 域全滅'),
        (('fnet', 'li'), False, '兩個獨立域同時失效，只剩 ^TWII 自我印證'),
        (('score', 'jqavg'), False, 'health 兩條腿都缺，arbiter 只會回 ⬜'),
        (('adl', 'fnet'), True, '先行指標這個獨立域還在，health 兩腿都在'),
        (('jqavg', 'adl'), True, '^TWII 域只剩 score 但還活著，兩獨立域都在'),
    ])
    def test_conditions(self, missing, expected, why):
        ok = {k: k not in missing for k in _KEYS}
        assert _new_gate_passes(ok) is expected, why


class TestChangeIsPureLoosening:
    """新 gate 只會讓燈更常顯示，不會讓原本看得到的日子看不到。"""

    def _diffs(self):
        out = []
        for combo in product((True, False), repeat=len(_KEYS)):
            ok = dict(zip(_KEYS, combo))
            o, n = _old_gate_passes(ok), _new_gate_passes(ok)
            if o != n:
                out.append((tuple(k for k in _KEYS if not ok[k]), o, n))
        return out

    def test_no_combination_becomes_stricter(self):
        stricter = [d for d in self._diffs() if d[1] and not d[2]]
        assert stricter == [], (
            f'有組合從「顯示」變成「擋」，這會讓使用者原本看得到的燈消失：{stricter}')

    def test_exactly_twelve_combinations_loosen(self):
        looser = [d for d in self._diffs() if not d[1] and d[2]]
        assert len(looser) == 12, (
            f'放寬的組合數從 12 變成 {len(looser)} —— 若這是刻意的，'
            f'請連同 handlers 的註解一起更新，不要只改數字。實際：{looser}')


class TestBackwardCompatibility:
    def test_missing_conf_groups_falls_back_to_old_gate(self):
        """舊版 tl dict（無 conf_groups）必須退回數量門檻，不可靜默放行（§1）。"""
        import src.ui.tabs.macro.handlers as h
        src = inspect.getsource(h._render_traffic_light)
        assert "tl.get('conf', 0) < 70" in src, (
            'conf_groups 缺席時的 fallback 被拿掉了 —— 舊 fixture 會被靜默放行')
