"""tests/test_strategy_code_wiring.py — v19.175 守衛：策略代號 SSOT 接線。

背景（實機 DOM 掃描抓到的 regression）
=====================================
v19.174 去識別化把 `ui_widgets._STRATEGY_MAP`（10 個真實人名 key）整份刪除，
改成三個代號常數 `STRATEGY_VALUATION/FINANCIAL/TECHNICAL`。34,052 字元全站
DOM 掃描（含隱藏 tab panel）發現：

1. **`STRATEGY_FINANCIAL`（策略2）+ 🏥 全站 0 次** —— 三個代號只剩兩個真的在用。
   「財報體檢」內容雖然存在（🔬 個股 / 🏆 個股組合），但那幾處是**手打字串
   「策略2」**，沒有走 `strategy_conclusion()` / `strategy_label()`。
2. 「📖 系統說明書」同一個「策略3」底下，兩章括號寫「（技術 / 動能）」、
   一章寫「（資金面）」—— **同一代號兩種括號說明**，讀者無從判斷是分類本來
   就寬還是編號寫錯。成因：括號由各 caller 自己 f-string 拼（§3.3 inline magic）。
3. `👤` 全站 0 次 —— `_to_strategy()` 的退化訊號沒觸發，代表**沒有**遺留
   caller 還在傳人名字串；(1)(2) 兩點與「漏改 caller」無關。

考證結論（判定 (2) 不是分類錯誤）
--------------------------------
被刪掉的 `_STRATEGY_MAP` 自己的分組註解是：
「策略 1：估值 / 存股」「策略 2：財報體檢」「策略 3：技術 / 動能 / 資金面」，
型態學 / VCP / 資金動能三章原本就同屬第三組 → 三章都叫策略3 **是對的**，
不是遷移時把策略2 錯標成策略3。真正要修的是「策略2 沒有章節」與「括號不一致」。

本檔釘四件事（都是上面各點的直接反面）
-------------------------------------
- `STRATEGY_SCOPE` / `STRATEGY_LABELS` / `strategy_label()` 的 SSOT 契約與 fail-loud
- **一個代號只能有一種括號說明**（掃 `src/**` 所有字串常數，非註解）
- **三個代號都至少有一個真實 caller**（AST 掃 `src/ui/**`，docstring / 註解不算）
- **`👤` 退化路徑不得被 production caller 觸發**（AST 檢查每個
  `strategy_conclusion` / `strategy_box` 呼叫的第 1 個引數）

⚠️ 已知未收斂（不在本檔守備範圍，另案處理）：
`src/ui/tabs/tab_stock.py`、`src/ui/tabs/stock_grp_sections/section_financial_health.py`、
`shared/stock_buckets.py`、`src/services/financial_health_engine.py` 仍寫字面
「策略2」（**不帶括號**，故不觸發本檔的括號一致性守衛）而非 import
`STRATEGY_FINANCIAL`。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from src.ui.render.ui_widgets import (
    STRATEGY_FINANCIAL,
    STRATEGY_LABELS,
    STRATEGY_SCOPE,
    STRATEGY_TECHNICAL,
    STRATEGY_VALUATION,
    _STRATEGY_ICON,
    _to_strategy,
    strategy_label,
)

_REPO = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO / 'src'
_UI_ROOT = _SRC_ROOT / 'ui'
_WIDGETS = _UI_ROOT / 'render' / 'ui_widgets.py'

_ALL_CODES = (STRATEGY_VALUATION, STRATEGY_FINANCIAL, STRATEGY_TECHNICAL)
_CONST_NAME = {
    STRATEGY_VALUATION: 'STRATEGY_VALUATION',
    STRATEGY_FINANCIAL: 'STRATEGY_FINANCIAL',
    STRATEGY_TECHNICAL: 'STRATEGY_TECHNICAL',
}
_CONST_NAMES = frozenset(_CONST_NAME.values())

# 「策略N（範疇 / 範疇）」— 章節標題解析用
_TITLE_RE = re.compile(r'(策略[123])（([^）]+)）')

# 會把第 1 個引數丟進 `_to_strategy()` 的函式（含 shim 與過渡期 alias）
_STRATEGY_SINKS = frozenset({
    'strategy_conclusion', 'strategy_box',
    '_strategy_conclusion',                      # etf_render shim
    'teacher_conclusion', 'teacher_box', '_teacher_conclusion',  # 過渡 alias
})


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - 不該發生
        return None


def _referenced_names(path: Path) -> set[str]:
    """檔案中**真的被當識別字用**的名稱集合（AST `Name` 節點）。

    刻意用 AST 而非字串搜尋：docstring / 註解裡提到常數名（例如
    `etf_render.py` 的說明文字）**不算** caller，否則這條守衛會被文件騙過去。
    """
    tree = _parse(path)
    if tree is None:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """module / class / def 的 docstring 常數節點 id 集合。

    括號一致性守衛只管**會被渲染的字串**；docstring 是給開發者看的說明，
    本檔自己的 docstring 就在描述壞掉的長相（「策略3（技術 / 動能）」），
    掃進去會自我否定。註解（`#`）不進 AST，天然被排除。
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


def _render_strings(path: Path) -> list[str]:
    """檔案中所有「可能被渲染」的字串常數（排除 docstring）。

    f-string 會被拆成 `JoinedStr` 的字面片段 —— 這剛好是我們要的：
    `f'📐 {strategy_label(CODE)} — 型態學…'` 的字面片段不含括號，
    只有**手打**括號才會留下 `策略N（…）` 的完整字面。
    """
    tree = _parse(path)
    if tree is None:
        return []
    skip = _docstring_nodes(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


def _iterable_element_exprs(tree: ast.Module,
                            iter_node: ast.expr) -> list[ast.expr] | None:
    """回傳「這個 iterable 的元素運算式清單」；無法靜態確定則 `None`。

    支援兩種就地建構的形狀（涵蓋 `section_long._macro_concl` 那類「先蒐集
    再統一渲染」的 caller）：
      1. 字面序列：`for x in (A, B)`
      2. 空 list + append：`xs = []` → `xs.append(<expr>)` × N → `for x in xs`

    刻意**不**追蹤 `+=` / `extend` / 跨函式傳遞 —— 證不出來就回 None，
    讓上層 `_resolves_to_registered_code` 判失敗（保守優於漏放）。
    """
    if isinstance(iter_node, (ast.List, ast.Tuple)):
        return list(iter_node.elts)
    if isinstance(iter_node, ast.Name):
        elts: list[ast.expr] = [
            n.args[0] for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == 'append'
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == iter_node.id
            and len(n.args) == 1
        ]
        return elts or None
    return None


def _simple_assignments(tree: ast.Module) -> dict[str, list[ast.expr]]:
    """`名稱 → 被指派過的運算式`。

    收三種綁定：
      - `ast.Assign` / `ast.AnnAssign` 的單一 Name target
        （解 `_strat7 = A if cond else B` 這種先算後傳的 caller）
      - `ast.For` 的 Name / Tuple target
        （解 `for code, ind, res, col in _macro_concl:` 這種先蒐集再渲染的
        caller —— v19.176 `section_long.py` 改成此形狀後才發現原本沒涵蓋，
        會把「可靜態證明安全」的寫法誤判成違規）

    Tuple target 會**逐位對齊**：`for a, b in xs` 且 `xs.append((A, B))`
    ⇒ `a → A`、`b → B`。元素不是可拆的字面 tuple 時，整個元素運算式原樣
    綁上去，交由上層判失敗。
    """
    out: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    out.setdefault(tgt.id, []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                out.setdefault(node.target.id, []).append(node.value)
        elif isinstance(node, ast.For):
            _elts = _iterable_element_exprs(tree, node.iter)
            if _elts is None:
                continue
            if isinstance(node.target, ast.Name):
                for _e in _elts:
                    out.setdefault(node.target.id, []).append(_e)
            elif isinstance(node.target, ast.Tuple):
                for _i, _t in enumerate(node.target.elts):
                    if not isinstance(_t, ast.Name):
                        continue
                    for _e in _elts:
                        if isinstance(_e, (ast.Tuple, ast.List)) and _i < len(_e.elts):
                            out.setdefault(_t.id, []).append(_e.elts[_i])
                        else:
                            out.setdefault(_t.id, []).append(_e)
    return out


def _resolves_to_registered_code(node: ast.expr,
                                 assigns: dict[str, list[ast.expr]],
                                 depth: int = 0) -> tuple[bool, str]:
    """第 1 個引數是否**保證**是已登記的策略代號。

    回 `(ok, reason)`。判定規則刻意保守 —— 無法靜態證明就算失敗，
    因為證不出來就等於「可能在畫面上變成 👤」。
    """
    if depth > 4:
        return False, '解析深度超限（賦值鏈太長，請直接傳 STRATEGY_* 常數）'
    if isinstance(node, ast.Name):
        if node.id in _CONST_NAMES:
            return True, ''
        if node.id in assigns:
            for sub in assigns[node.id]:
                ok, why = _resolves_to_registered_code(sub, assigns, depth + 1)
                if not ok:
                    return False, f'{node.id} → {why}'
            return True, ''
        return False, f'變數 {node.id} 來源不明'
    if isinstance(node, ast.Attribute):          # ui_widgets.STRATEGY_TECHNICAL
        if node.attr in _CONST_NAMES:
            return True, ''
        return False, f'屬性 .{node.attr} 非策略常數'
    if isinstance(node, ast.IfExp):              # A if cond else B
        for sub in (node.body, node.orelse):
            ok, why = _resolves_to_registered_code(sub, assigns, depth + 1)
            if not ok:
                return False, why
        return True, ''
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return False, (f'手打字串 {node.value!r} —— 請 import '
                       f'STRATEGY_VALUATION / _FINANCIAL / _TECHNICAL')
    return False, f'無法靜態判定的運算式（{type(node).__name__}）'


def _strategy_call_args(path: Path):
    """yield `(lineno, func_name, 第1個位置引數 node, 該檔賦值表)`。"""
    tree = _parse(path)
    if tree is None:
        return
    assigns = _simple_assignments(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = (fn.id if isinstance(fn, ast.Name)
                else fn.attr if isinstance(fn, ast.Attribute) else None)
        if name not in _STRATEGY_SINKS or not node.args:
            continue
        yield node.lineno, name, node.args[0], assigns


class TestStrategyScopeSSOT:
    def test_keys_match_icon_and_label_tables(self):
        # 三張表必須同步：有 icon 就要有範疇、有範疇就要有顯示字串
        assert (set(STRATEGY_SCOPE) == set(_STRATEGY_ICON)
                == set(STRATEGY_LABELS) == set(_ALL_CODES))

    def test_values_are_non_empty_string_tuples(self):
        for code, scope in STRATEGY_SCOPE.items():
            assert isinstance(scope, tuple) and scope, f'{code} 範疇不可為空'
            assert all(isinstance(s, str) and s for s in scope)

    def test_scopes_do_not_overlap(self):
        # 三類語意邊界必須互斥，否則「這章到底算哪一策略」又會塌回去
        seen: set[str] = set()
        for scope in STRATEGY_SCOPE.values():
            dup = seen & set(scope)
            assert not dup, f'範疇字樣跨策略重複：{dup}'
            seen |= set(scope)

    def test_labels_are_derived_from_scope(self):
        # STRATEGY_LABELS 必須是 STRATEGY_SCOPE 的純函數 —— 不可各寫各的
        for code, scope in STRATEGY_SCOPE.items():
            assert STRATEGY_LABELS[code] == f'{code}（{" / ".join(scope)}）'


class TestStrategyLabel:
    def test_returns_ssot_label(self):
        assert strategy_label(STRATEGY_VALUATION) == '策略1（估值 / 存股）'
        assert strategy_label(STRATEGY_FINANCIAL) == '策略2（財報體檢）'
        assert strategy_label(STRATEGY_TECHNICAL) == '策略3（技術 / 動能 / 資金面）'

    def test_no_scope_override_parameter(self):
        """回歸核心：不得再提供「只顯示子集」的參數。

        v19.175 之前 `strategy_label(code, scope)` 允許傳子集，結果就是
        「策略3（技術 / 動能）」與「策略3（資金面）」並存。移除該參數讓
        「同代號兩種括號」在**型別層**就不可能發生。
        """
        import inspect
        params = list(inspect.signature(strategy_label).parameters)
        assert params == ['strategy'], (
            f'strategy_label 多了參數 {params}；括號說明必須全站唯一')
        with pytest.raises(TypeError):
            strategy_label(STRATEGY_TECHNICAL, ('資金面',))  # type: ignore[call-arg]

    def test_unknown_code_raises(self):
        # 與 `_to_strategy()` 的寬鬆退化不同：靜態標題寫錯要當場炸（§1）
        with pytest.raises(ValueError):
            strategy_label('策略9')
        with pytest.raises(ValueError):
            strategy_label('尚未遷移的字串')
        with pytest.raises(ValueError):
            strategy_label('')


class TestBracketTextIsGlobalSSOT:
    """全站不得出現「同一策略代號配不同括號說明」。"""

    @pytest.fixture(scope='class')
    def bracket_usages(self) -> dict[str, dict[str, list[str]]]:
        """`代號 → {括號內容: [出處…]}`，掃 `src/**` 全部可渲染字串。"""
        out: dict[str, dict[str, list[str]]] = {c: {} for c in _ALL_CODES}
        for py in _SRC_ROOT.rglob('*.py'):
            where = str(py.relative_to(_REPO))
            for text in _render_strings(py):
                for code, scope_txt in _TITLE_RE.findall(text):
                    out.setdefault(code, {}).setdefault(scope_txt, []).append(where)
        # 由 SSOT 產出的執行期字串也一起納入（f-string 拼不出字面，掃不到）
        for code, label in STRATEGY_LABELS.items():
            m = _TITLE_RE.fullmatch(label)
            assert m, f'STRATEGY_LABELS[{code}] 格式不符：{label!r}'
            out[code].setdefault(m.group(2), []).append('ui_widgets.STRATEGY_LABELS')
        return out

    @pytest.mark.parametrize('code', _ALL_CODES)
    def test_one_bracket_text_per_code(self, bracket_usages, code):
        variants = bracket_usages.get(code, {})
        assert len(variants) <= 1, (
            f'{code} 出現 {len(variants)} 種括號說明 —— {variants}；'
            f'請一律改用 ui_widgets.strategy_label()')

    @pytest.mark.parametrize('code', _ALL_CODES)
    def test_bracket_text_equals_ssot(self, bracket_usages, code):
        canonical = ' / '.join(STRATEGY_SCOPE[code])
        for scope_txt, where in bracket_usages.get(code, {}).items():
            assert scope_txt == canonical, (
                f'{code}（{scope_txt}）於 {where} 與 SSOT'
                f'「{canonical}」不符')

    def test_scan_would_catch_a_handwritten_variant(self, tmp_path):
        """守衛的自我驗證：手打一個不同括號，掃描器要抓得到。"""
        fake = tmp_path / 'fake_ui.py'
        fake.write_text("X = '📐 策略3（技術 / 動能）— 型態學'\n", encoding='utf-8')
        hits = [m for t in _render_strings(fake) for m in _TITLE_RE.findall(t)]
        assert hits == [('策略3', '技術 / 動能')]
        assert '技術 / 動能' != ' / '.join(STRATEGY_SCOPE[STRATEGY_TECHNICAL])

    def test_docstrings_are_excluded_from_scan(self, tmp_path):
        """docstring 不算渲染字串（本檔自己的 docstring 就在描述壞掉的長相）。"""
        fake = tmp_path / 'fake_doc.py'
        fake.write_text('"""說明：策略3（技術 / 動能）曾經是錯的。"""\nX = 1\n',
                        encoding='utf-8')
        assert not [m for t in _render_strings(fake) for m in _TITLE_RE.findall(t)]


class TestNoDegradedStrategyCaller:
    """`👤` 退化路徑不得被 production caller 觸發。

    `_to_strategy()` 對未登記字串刻意不 raise（退化成 `('策略','👤')`），
    那是「還有 caller 沒改乾淨」的**可見訊號**，不是可接受的常態。
    這裡靜態檢查每個 sink 呼叫的第 1 個引數必然是已登記代號。
    """

    @pytest.fixture(scope='class')
    def calls(self) -> list[tuple[str, int, str, ast.expr, dict]]:
        out = []
        for py in _SRC_ROOT.rglob('*.py'):
            if py.resolve() == _WIDGETS.resolve():
                continue  # 定義處 + 過渡 alias 指派本身不算 caller
            for lineno, fname, arg, assigns in _strategy_call_args(py):
                out.append((str(py.relative_to(_REPO)), lineno, fname, arg, assigns))
        return out

    def test_scan_found_call_sites(self, calls):
        # 掃不到任何 call site 代表掃描器壞了，後面的斷言會假性通過
        assert len(calls) >= 20, f'只掃到 {len(calls)} 個策略卡 caller，掃描器可能失效'

    def test_no_caller_can_reach_the_fallback(self, calls):
        bad = []
        for where, lineno, fname, arg, assigns in calls:
            ok, why = _resolves_to_registered_code(arg, assigns)
            if not ok:
                bad.append(f'{where}:{lineno} {fname}(...) → {why}')
        assert not bad, (
            '以下 caller 的策略代號無法靜態證明已登記，畫面可能出現 👤 策略：\n'
            + '\n'.join(bad))

    def test_registered_codes_never_render_the_fallback(self):
        """執行期對帳：三個代號走 `_to_strategy` 都不得回退化值。"""
        for code in _ALL_CODES:
            label, icon = _to_strategy(code)
            assert (label, icon) != ('策略', '👤'), f'{code} 命中退化路徑'
            assert icon == _STRATEGY_ICON[code]

    def test_fallback_still_exists_for_unregistered(self):
        """退化路徑本身要留著 —— 它是漏改 caller 的可見訊號（§1 不靜默）。"""
        assert _to_strategy('尚未遷移的字串') == ('策略', '👤')

    def test_scan_would_catch_a_literal_first_arg(self, tmp_path):
        """守衛的自我驗證：手打字串當第 1 引數要被抓出來。"""
        fake = tmp_path / 'fake_caller.py'
        fake.write_text("strategy_conclusion('某個人名', 'x', 'y')\n", encoding='utf-8')
        found = list(_strategy_call_args(fake))
        assert len(found) == 1
        ok, why = _resolves_to_registered_code(found[0][2], found[0][3])
        assert not ok and '手打字串' in why


class TestEveryStrategyCodeHasCaller:
    """三個代號**都**要有真實 caller —— 少一個就代表一整類內容從畫面消失。"""

    @pytest.fixture(scope='class')
    def callers(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {n: [] for n in _CONST_NAME.values()}
        for py in _UI_ROOT.rglob('*.py'):
            if py.resolve() == _WIDGETS.resolve():
                continue  # 定義處本身不算 caller
            names = _referenced_names(py)
            for const in out:
                if const in names:
                    out[const].append(str(py.relative_to(_REPO)))
        return out

    @pytest.mark.parametrize('code', _ALL_CODES)
    def test_code_has_at_least_one_caller(self, callers, code):
        const = _CONST_NAME[code]
        assert callers[const], (
            f'{const}（{code}）在 src/ui/** 沒有任何 caller —— '
            f'該策略的內容不會出現在畫面上（v19.174 就是這樣掉了策略2）')

    def test_docstring_or_comment_mention_is_not_a_caller(self, tmp_path):
        """AST 作法的自我驗證：只在 docstring / 註解提到常數名不算接線。

        （`etf_render.py` 就是這種情況 —— 說明文字寫了 `STRATEGY_FINANCIAL`，
        但整檔沒有真的用它。字串搜尋會被騙，AST 不會。）
        """
        fake = tmp_path / 'fake_module.py'
        fake.write_text(
            '"""說明文字提到 STRATEGY_FINANCIAL 但沒有使用它。"""\n'
            '# STRATEGY_FINANCIAL\n'
            'X = 1\n',
            encoding='utf-8')
        names = _referenced_names(fake)
        assert 'STRATEGY_FINANCIAL' not in names
        assert 'X' in names, 'AST helper 連真的識別字都抓不到，測試本身失效'


class TestEduChapterTitles:
    """📖 系統說明書的策略章節標題：編號、括號、涵蓋度三件事一起釘。"""

    @pytest.fixture(scope='class')
    def titles(self) -> dict[str, str]:
        from src.ui.tabs import tab_edu
        return dict(tab_edu._EDU_STRATEGY_TITLES)

    def test_titles_are_non_empty(self, titles):
        assert titles, '說明書策略章節標題表為空'
        for key, title in titles.items():
            assert isinstance(title, str) and title.strip(), key

    def test_every_title_uses_the_ssot_label_verbatim(self, titles):
        """章節標題的「策略N（範疇）」必須**逐字**等於 SSOT。"""
        for key, title in titles.items():
            m = _TITLE_RE.search(title)
            assert m, f'{key} 標題缺「策略N（範疇）」結構：{title}'
            code = m.group(1)
            assert code in STRATEGY_LABELS, f'{key} 用了未登記代號 {code}'
            assert m.group(0) == STRATEGY_LABELS[code], (
                f'{key}：「{m.group(0)}」≠ SSOT「{STRATEGY_LABELS[code]}」')

    def test_same_code_chapters_share_one_bracket(self, titles):
        """策略3 底下三章：代號相同，括號也必須相同（差異寫在破折號後）。"""
        seen: dict[str, set[str]] = {}
        for title in titles.values():
            m = _TITLE_RE.search(title)
            assert m
            seen.setdefault(m.group(1), set()).add(m.group(2))
        for code, variants in seen.items():
            assert len(variants) == 1, (
                f'{code} 在說明書出現多種括號說明：{sorted(variants)}')

    def test_all_three_strategies_have_a_chapter(self, titles):
        """策略2 消失 regression：說明書三類都要有章節。"""
        codes = {m.group(1) for t in titles.values()
                 if (m := _TITLE_RE.search(t)) is not None}
        missing = set(_ALL_CODES) - codes
        assert not missing, f'說明書缺少策略章節：{sorted(missing)}'

    def test_financial_chapter_exists_and_is_strategy2(self, titles):
        assert 'financial_health' in titles, '說明書缺財報體檢章節'
        assert STRATEGY_FINANCIAL in titles['financial_health']
        assert '🏥' in titles['financial_health'], '策略2 章節缺 🏥（DOM 掃描 0 次）'

    def test_titles_are_unique(self, titles):
        assert len(set(titles.values())) == len(titles), '章節標題重複'

    def test_technical_has_three_chapters(self, titles):
        """三章掛策略3 是**預期行為**（分類本來就寬），釘住避免有人「順手改編號」。"""
        n = sum(1 for t in titles.values()
                if (m := _TITLE_RE.search(t)) and m.group(1) == STRATEGY_TECHNICAL)
        assert n == 3, f'策略3 章節數 {n} ≠ 3（型態學 / VCP / 資金動能）'


class TestEduSourceUsesSSOT:
    """說明書原始碼不得再手打「策略N（…）」或財報門檻數字（§3.3 反 inline magic）。"""

    @pytest.fixture(scope='class')
    def src(self) -> str:
        return (_REPO / 'src/ui/tabs/tab_edu.py').read_text(encoding='utf-8')

    def test_no_hardcoded_strategy_code_in_expander_titles(self, src):
        hit = re.search(r"st\.expander\(\s*[rf]*['\"][^'\"]*策略[123]", src)
        assert hit is None, (
            f'st.expander 標題仍手打策略代號：{hit.group(0)!r}；'
            f'請改用 _EDU_STRATEGY_TITLES / strategy_label()')

    def test_no_handwritten_bracket_in_render_strings(self):
        """tab_edu 的可渲染字串裡不得留下任何手打的「策略N（…）」字面。"""
        leftovers = [t for t in _render_strings(_REPO / 'src/ui/tabs/tab_edu.py')
                     if _TITLE_RE.search(t)]
        assert not leftovers, f'仍有手打括號：{leftovers}'

    def test_imports_strategy_ssot(self, src):
        assert 'from src.ui.render.ui_widgets import' in src
        assert 'strategy_label' in src

    def test_financial_thresholds_come_from_shared_ssot(self, src):
        assert 'from shared.financial_health_thresholds import' in src, \
            '策略2 章節門檻未走 SSOT'

    def test_imported_fh_constants_are_actually_used(self):
        """import 了就要用到 —— 防止章節退化成手打數字、常數變裝飾品。"""
        names = _referenced_names(_REPO / 'src/ui/tabs/tab_edu.py')
        for const in ('FH_CASH_RATIO_SAFE_PCT', 'FH_DEBT_RATIO_WARN_PCT',
                      'FH_CURRENT_RATIO_MIN_PCT', 'FH_GROSS_MARGIN_GOOD_PCT',
                      'FH_EARNINGS_QUALITY_MIN_PCT'):
            assert const in names, f'策略2 章節未實際使用 {const}'
