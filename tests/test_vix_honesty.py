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

import shared.allocation_decision as _ad
from shared.allocation_decision import vix_veto_cap
from shared.macro_buckets import SPECS_BY_KEY, classify_danger
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


# ════════════════════════════════════════════════════════════════
# MACRO_THRESHOLDS['VIX']['green_below'] = 18 是**死參數**
#   CLAUDE.md §3.2 把它列在表上 → 讀憲法的人會以為「全站綠線是 18」。
#   實際上 classify_danger 只有黃 22 / 紅 30 兩刀，18 這條線在畫面上不存在。
#   本組**不刪**它（動到對外 schema / JSON 契約），改成把「它不判燈」這件事
#   釘成可執行規格：值怎麼動，判燈輸出都不准動。
# ════════════════════════════════════════════════════════════════
class TestVixGreenBelowIsDead:

    @pytest.mark.parametrize('vix', [10.0, 16.0, 17.9, 18.0, 19.0, 21.0, 21.9])
    def test_18_is_not_a_cut_at_all(self, vix):
        """18 兩側全部是 green —— 那條線在畫面上不存在。"""
        assert classify_danger(vix, SPECS_BY_KEY['vix']) == 'green'

    def test_moving_green_below_changes_nothing(self, monkeypatch):
        """把 green_below 從 18 搬到 99，判燈輸出必須一字不變。

        這就是「死參數」的可執行定義。哪天有人把它接上判燈（那會改變輸出、
        屬業務規則、須送客戶），這條測試會先紅。
        """
        from src.data.macro import macro_alert as _ma
        from src.data.macro import macro_core as _mc
        _probe = [10.0, 16.0, 18.0, 19.0, 21.9, 22.0, 25.0, 29.9, 30.0, 31.0]

        def _snap():
            return ([classify_danger(v, SPECS_BY_KEY['vix']) for v in _probe],
                    # 直接把本表當 rule 餵進 macro_alert 的分級器 ——
                    # 它若讀 green_below，搬家後就會變。
                    [_ma._classify_level(v, _mc.MACRO_THRESHOLDS['VIX']) for v in _probe])

        _before = _snap()
        monkeypatch.setitem(_mc.MACRO_THRESHOLDS['VIX'], 'green_below', 99)
        assert _snap() == _before

    def test_sig_vix_only_reads_yellow_and_red(self):
        """`macro_core._sig_vix`（巢狀函式，runtime 取不到）以 AST 證明它不讀 green_*。"""
        _tree = ast.parse((_REPO / 'src' / 'data' / 'macro' / 'macro_core.py')
                          .read_text(encoding='utf-8'))
        _fn = next(_n for _n in ast.walk(_tree)
                   if isinstance(_n, ast.FunctionDef) and _n.name == '_sig_vix')
        _keys = {_n.slice.value for _n in ast.walk(_fn)
                 if isinstance(_n, ast.Subscript)
                 and isinstance(_n.slice, ast.Constant)
                 and isinstance(_n.slice.value, str)}
        assert _keys == {'VIX', 'red_above', 'yellow_above'}, (
            f'_sig_vix 讀取的 key 變了：{_keys}')

    def test_no_production_code_reads_it(self):
        """全 repo（不含 tests）不得出現讀 `MACRO_THRESHOLDS[...]['green_below']` 的程式碼。

        唯一合法的 `green_below` 讀取點是 `macro_helpers._classify_china_zone`，
        而它吃的是自己那份 `_CHINA_SUBSCORE_THRESHOLDS`，**不是**本表 —— 名字一樣，
        來源不同，別被騙。
        """
        _hits: list[str] = []
        for _p in _REPO.rglob('*.py'):
            _rel = _p.relative_to(_REPO).as_posix()
            if _rel.startswith(('tests/', '.git/')) or '__pycache__' in _rel:
                continue
            for _i, _line in enumerate(_p.read_text(encoding='utf-8').splitlines(), 1):
                if 'green_below' not in _line or _line.lstrip().startswith('#'):
                    continue
                # 允許：定義本身、macro_buckets 的 USDTWD 鏡像、China 副盤自己那份
                if _rel in ('src/data/macro/macro_core.py',
                            'shared/macro_buckets.py',
                            'src/compute/macro/macro_helpers.py'):
                    continue
                _hits.append(f'{_rel}:{_i}: {_line.strip()}')
        assert not _hits, (
            'green_below 出現了新的讀取點 —— 它若真的開始判燈，'
            '就不再是死參數，CLAUDE.md §3.2 與本檔註記都要同步更新：\n'
            + '\n'.join(_hits))


# ════════════════════════════════════════════════════════════════
# macro_helpers.classify_short_term_regime —— 已於 2026-08-27 刪除（死碼）
#   它是本 repo 的**第 8 套 VIX 門檻**（15/20/25/30，見刪除前的 docstring），
#   卻 0 production caller —— 一套沒人用、也沒人知道它存在的尺。
#   守衛不是「永遠不准回來」，而是「要回來就得帶著 caller」。
# ════════════════════════════════════════════════════════════════
_DEAD_SYMBOL = 'classify_short_term_regime'


def _production_py_files():
    for _p in _REPO.rglob('*.py'):
        _rel = _p.relative_to(_REPO).as_posix()
        if _rel.startswith(('tests/', 'scratchpad/')) or '__pycache__' in _rel:
            continue
        yield _rel, _p


def test_dead_ruleset_stays_dead_or_comes_back_with_a_caller():
    """`classify_short_term_regime` 要嘛不存在，要嘛有真的 production caller。

    以 AST 掃描全部 production .py：分別統計「定義」與「引用」。
    - 兩者皆 0 → 已刪除，通過。
    - 有定義但 0 引用 → 又是一套沒人用的孤兒 VIX 門檻 → 紅燈。
    - 有定義也有引用 → 有人真的用它，通過（此時該補回它的測試）。
    """
    _defs: list[str] = []
    _refs: list[str] = []
    for _rel, _p in _production_py_files():
        for _n in ast.walk(ast.parse(_p.read_text(encoding='utf-8'))):
            if isinstance(_n, ast.FunctionDef) and _n.name == _DEAD_SYMBOL:
                _defs.append(f'{_rel}:{_n.lineno}')
            elif ((isinstance(_n, ast.Name) and _n.id == _DEAD_SYMBOL)
                    or (isinstance(_n, ast.Attribute) and _n.attr == _DEAD_SYMBOL)):
                _refs.append(f'{_rel}:{_n.lineno}')
            elif isinstance(_n, ast.alias) and _DEAD_SYMBOL in (_n.name, _n.asname):
                _refs.append(f'{_rel}: import')
    assert not (_defs and not _refs), (
        f'{_DEAD_SYMBOL} 又被定義了，但 0 production caller：{_defs}\n'
        '它是本 repo 第 8 套 VIX 門檻（15/20/25/30）。'
        '沒有 caller 的門檻＝沒人知道它存在的第 8 把尺，'
        '不是「先寫好等以後用」，是下一個誤讀源。')


def test_barrel_no_longer_forwards_the_dead_symbol():
    """PEP 562 barrel 會即時轉發任何 submodule 屬性 —— 確認它現在真的轉發不到。"""
    import src.compute.macro as _cm
    with pytest.raises(AttributeError):
        getattr(_cm, _DEAD_SYMBOL)
