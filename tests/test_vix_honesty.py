"""VIX 誠實化守衛 — 擋「註解宣稱 SSOT、實作卻是 inline literal」的回歸。

⛔ **本檔一個 VIX 門檻數值都不改、也不主張要統一。**
   user 2026-06-26 已撤銷過「harmonize 統一值」；同一個 VIX 在不同語意下
   本來就可以有不同的刀（短線交易 vs 長期定期定額加碼）。
   本檔守的是**另一件事**：文件說的話，程式有沒有真的在做。

覆蓋：
- `shared/allocation_decision.py::vix_veto_cap`
  —— docstring 曾宣稱「門檻對齊 VIX_MEDIUM_RISK_THRESHOLD(20) /
     VIX_HIGH_RISK_THRESHOLD(25) 與 macro_buckets 紅線 30」，
     但該檔當時**一個 SSOT 都沒 import**，且 25 在函式裡根本不是任何一刀。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared.allocation_decision import vix_veto_cap
import shared.allocation_decision as _ad
from shared.macro_buckets import SPECS_BY_KEY
from shared.signal_thresholds import (
    VIX_HIGH_RISK_THRESHOLD,
    VIX_MEDIUM_RISK_THRESHOLD,
)

_REPO = pathlib.Path(__file__).resolve().parents[1]


class TestVixVetoCapIsRealSSOT:
    """`vix_veto_cap` 的兩條線必須**真的**來自 SSOT，不是碰巧數字一樣。"""

    def test_module_really_imports_the_ssot_it_cites(self):
        """AST：本檔必須真的 import 那兩個 SSOT —— 宣稱要可執行，不能只寫在註解裡。

        突變測試：把 import 拔掉改回 inline `>= 30` / `>= 20` → 本測試轉紅。
        """
        _tree = ast.parse((_REPO / 'shared' / 'allocation_decision.py')
                          .read_text(encoding='utf-8'))
        _imported: dict[str, set[str]] = {}
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.ImportFrom) and _n.module:
                _imported.setdefault(_n.module, set()).update(
                    a.name for a in _n.names)
        assert 'VIX_MEDIUM_RISK_THRESHOLD' in _imported.get(
            'shared.signal_thresholds', set()), (
            'vix_veto_cap 的黃線宣稱對齊 signal_thresholds，'
            '但本檔沒有 import 它 → 宣稱不成立（§3.3 反捏造）')
        assert 'SPECS_BY_KEY' in _imported.get('shared.macro_buckets', set()), (
            'vix_veto_cap 的紅線宣稱對齊 macro_buckets，'
            '但本檔沒有 import 它 → 宣稱不成立（§3.3 反捏造）')

    def test_branches_read_the_module_constants_not_literals(self, monkeypatch):
        """把 SSOT 常數搬走，判斷式必須跟著走 —— 證明分支讀的是常數不是字面值。

        突變測試：分支改回 `_v >= 30` / `_v >= 20` → 本測試轉紅。
        """
        monkeypatch.setattr(_ad, '_VIX_VETO_WARN', 25.0)
        monkeypatch.setattr(_ad, '_VIX_VETO_PANIC', 40.0)
        assert vix_veto_cap(24.0) is None                 # 24 < 新黃線 25
        assert vix_veto_cap(31.0).pct == 30               # 31 < 新紅線 40 → 只吃黃
        assert vix_veto_cap(41.0).pct == 10               # 41 >= 新紅線 40

    def test_thresholds_have_not_drifted(self):
        """漂移鎖：兩條線的**值**與現行 SSOT 一致（本輪刻意不改任何數值）。"""
        assert _ad._VIX_VETO_WARN == VIX_MEDIUM_RISK_THRESHOLD == 20.0
        assert _ad._VIX_VETO_PANIC == SPECS_BY_KEY['vix'].red == 30.0

    @pytest.mark.parametrize('vix', [24.9, 25.0, 25.1])
    def test_there_is_no_cut_at_25(self, vix):
        """`VIX_HIGH_RISK_THRESHOLD`(25) **不是**本函式的刀 —— 三點輸出必須相同。

        這條測試是給未來的人看的：舊 docstring 引了 25，那是**誤引**
        （25 是 v4_strategy_engine 的持股上限分級門檻，語意不同），
        **不是漏實作**。誰要「補上第三段」，會先撞到這條測試並讀到這段話——
        那會改變判燈輸出，屬業務規則，須送客戶，不得內部自決。
        """
        assert VIX_HIGH_RISK_THRESHOLD == 25.0        # 這個常數本身沒被動
        _c = vix_veto_cap(vix)
        assert _c is not None and _c.pct == 30
        assert '警戒帶' in _c.reason
