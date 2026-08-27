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


# ════════════════════════════════════════════════════════════════
# src/ui/tabs/macro/section_mid.py —— 第二處假宣稱
#   註解寫「VIX 燈號門檻統一至 SSOT（macro_buckets / MACRO_THRESHOLDS：22 黃 / 30 紅）」，
#   下一行卻是 `_vcur8 >= 30` / `>= 22` 兩個字面值，全檔只 import 了 MACRO_INFO_KEYS。
#   同一張圖裡 add_danger_hlines(_vfig8,'vix') 畫的線**是**讀 SSOT 的 ——
#   SSOT 一改，線會動、字和顏色不會動，圖會自打嘴巴。
# ════════════════════════════════════════════════════════════════
_SECTION_MID = _REPO / 'src' / 'ui' / 'tabs' / 'macro' / 'section_mid.py'


def _eval_assign(var: str, ns: dict):
    """把 section_mid.py 裡 `<var> = <expr>` 的**真實 production 運算式**抓出來求值。

    不是複寫一份等價邏輯（那會變成自己驗自己），是直接 eval 原始碼那一行。
    """
    _tree = ast.parse(_SECTION_MID.read_text(encoding='utf-8'))
    for _n in ast.walk(_tree):
        if (isinstance(_n, ast.Assign) and len(_n.targets) == 1
                and isinstance(_n.targets[0], ast.Name)
                and _n.targets[0].id == var):
            _expr = ast.Expression(body=_n.value)
            ast.fix_missing_locations(_expr)
            return eval(compile(_expr, str(_SECTION_MID), 'eval'), dict(ns))
    raise AssertionError(f'section_mid.py 找不到 `{var} = ...` 指派')


class _FakeSpec:
    """假的 DangerSpec —— 只要判斷式真的讀 spec，門檻就會跟著搬家。"""
    yellow = 40.0
    red = 60.0


class TestSectionMidVixReadsSSOT:

    def test_file_really_imports_the_ssot_it_claims(self):
        """註解宣稱「統一至 SSOT」，那就必須真的 import 得到它。"""
        _src = _SECTION_MID.read_text(encoding='utf-8')
        assert 'from shared.macro_buckets import SPECS_BY_KEY' in _src, (
            'section_mid.py 宣稱 VIX 燈號門檻統一至 SSOT，卻沒有 import 它')

    @pytest.mark.parametrize('vix,want_yellow_or_worse,want_red', [
        (39.9, False, False),   # 假 spec 黃線 40 之下 → 綠
        (40.0, True, False),
        (59.9, True, False),
        (60.0, True, True),     # 假 spec 紅線 60 → 紅
    ])
    def test_colour_and_label_follow_the_spec_not_literals(
            self, vix, want_yellow_or_worse, want_red):
        """搬走 spec 門檻，顏色與文案必須跟著搬。

        突變測試：改回 `_vcur8 >= 30` / `>= 22` → 這幾點全部答錯 → 轉紅。
        （用 40/60 這種現實中不會與 22/30 混淆的值，避免「碰巧也對」。）
        """
        from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
        _ns = {'_vcur8': vix, '_vspec8': _FakeSpec,
               'TRAFFIC_GREEN': TRAFFIC_GREEN, 'TRAFFIC_YELLOW': TRAFFIC_YELLOW,
               'TRAFFIC_RED': TRAFFIC_RED}
        _colour = _eval_assign('_vc8', _ns)
        _label = _eval_assign('_vl8', _ns)
        if want_red:
            assert _colour == TRAFFIC_RED and _label.startswith('🚨')
        elif want_yellow_or_worse:
            assert _colour == TRAFFIC_YELLOW and _label.startswith('⚠️')
        else:
            assert _colour == TRAFFIC_GREEN and _label.startswith('✅')

    @pytest.mark.parametrize('vix,colour_name,label_head', [
        (21.9, 'green', '✅'), (22.0, 'yellow', '⚠️'),
        (29.9, 'yellow', '⚠️'), (30.0, 'red', '🚨'),
    ])
    def test_real_spec_gives_the_same_answers_as_before(
            self, vix, colour_name, label_head):
        """漂移鎖：接上真 spec 後，四個邊界點的判燈與本版前**完全一樣**。

        本輪只修文件說謊，**不改任何門檻值**
        （user 2026-06-26 已撤銷過「harmonize 統一值」）。
        """
        from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
        _want = {'green': TRAFFIC_GREEN, 'yellow': TRAFFIC_YELLOW,
                 'red': TRAFFIC_RED}[colour_name]
        _ns = {'_vcur8': vix, '_vspec8': SPECS_BY_KEY['vix'],
               'TRAFFIC_GREEN': TRAFFIC_GREEN, 'TRAFFIC_YELLOW': TRAFFIC_YELLOW,
               'TRAFFIC_RED': TRAFFIC_RED}
        assert _eval_assign('_vc8', _ns) == _want
        assert _eval_assign('_vl8', _ns).startswith(label_head)

    def test_no_bare_vix_literals_left_in_the_file(self):
        """反向守衛：不准把 22 / 30 再寫回去（含「待取得」KPI 副標那一行）。"""
        _tree = ast.parse(_SECTION_MID.read_text(encoding='utf-8'))
        _bad = [f'line {_n.lineno}'
                for _n in ast.walk(_tree)
                if isinstance(_n, ast.Compare)
                and isinstance(_n.left, ast.Name) and _n.left.id == '_vcur8'
                and any(isinstance(_c, ast.Constant) and _c.value in (22, 30, 22.0, 30.0)
                        for _c in _n.comparators)]
        assert not _bad, f'_vcur8 又被拿去和字面值 22/30 比較：{_bad}'
        _src = _SECTION_MID.read_text(encoding='utf-8')
        assert '≥22警戒 / ≥30危機' not in _src, (
            '「待取得」KPI 副標的 22/30 是字面值 —— 留著就是下一個會漂移的說謊點')
