"""tests/test_no_undefined_names.py — v18.452 全域 undefined-name 靜態守衛。

production 事故根因盤點(這輪同一天內連續發現 6 處):
- section_357_valuation.py:152-157  cheap2/fair2/dear2(U4 Phase 3-B 抽出殘留)
- section_short.py                  TRAFFIC_GREEN/RED/YELLOW/os/go/
                                     BREADTH_BULL_PCT/BREADTH_NEUTRAL_PCT/
                                     add_danger_hlines(F-7.1 B-2 抽出殘留,
                                     整個「總經」Tab §6 短線急殺桶 100% 會炸)
- section_news_ai.py                json/datetime(F-7.1 B-3 抽出殘留)
- section_state.py                  pd(F-7.1 B-S2 抽出殘留)
- tab_stock_picker.py               _t_yf(v18.374 P1-1a 抽出時漏改,Stage 1/2
                                     兩張表無論輸入什麼股票全部顯示 N/A)

共通根因:把大檔案的一段程式碼「抽出」成獨立函式/模組時,遺漏原本在外層 scope
才有的 import / 變數,extracted 函式在特定資料分支下才會執行到那行 → 只有
production 真實資料觸發特定分支時才會現形,AppTest smoke test 若用空 session_state
測試會完全繞過這些分支(見 test_render_smoke.py 既有測試皆用空/預設 state)。

本測試用 pyflakes 靜態掃描全 src/ + shared/,直接抓出所有「名稱從未被 import /
賦值卻被使用」的個案 —— 不需要真的執行到該分支即可攔截,比功能測試更早、更全面。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

try:
    from pyflakes.checker import Checker
    from pyflakes.messages import UndefinedName
    _HAS_PYFLAKES = True
except ImportError:
    _HAS_PYFLAKES = False

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCAN_DIRS = ['src', 'shared']


def _iter_py_files():
    for _d in _SCAN_DIRS:
        yield from (_REPO_ROOT / _d).rglob('*.py')


def _find_undefined_names(path: Path) -> list[str]:
    _src = path.read_text(encoding='utf-8')
    try:
        _tree = ast.parse(_src, filename=str(path))
    except SyntaxError as _e:
        return [f'SyntaxError: {_e}']
    _checker = Checker(_tree, filename=str(path))
    return [
        f'{path.relative_to(_REPO_ROOT)}:{_m.lineno}: undefined name {_m.message_args[0]!r}'
        for _m in _checker.messages
        if isinstance(_m, UndefinedName)
    ]


@pytest.mark.skipif(not _HAS_PYFLAKES, reason='pyflakes 未安裝(pip install pyflakes)')
def test_no_undefined_names_anywhere_in_src_or_shared():
    """全 src/ + shared/ 逐檔靜態掃描,任何一個 undefined name 都視為潛在 production NameError。

    §1 Fail Loud:此類 bug 一旦資料剛好落入對應分支就會讓整個 Tab / section 全炸,
    且不一定馬上被發現(空狀態測試會繞過);靜態掃描不需要資料就能 100% 攔截。
    """
    _violations: list[str] = []
    for _f in _iter_py_files():
        _violations.extend(_find_undefined_names(_f))
    assert not _violations, (
        f'發現 {len(_violations)} 處 undefined name(production NameError 風險):\n'
        + '\n'.join(_violations)
    )


@pytest.mark.skipif(not _HAS_PYFLAKES, reason='pyflakes 未安裝(pip install pyflakes)')
class TestSpecificRegressions:
    """逐一釘住這輪修復的 6 處,防止未來重構又漏改。"""

    def test_section_357_valuation_clean(self):
        assert not _find_undefined_names(
            _REPO_ROOT / 'src/ui/tabs/stock_sections/section_357_valuation.py')

    def test_section_short_clean(self):
        assert not _find_undefined_names(
            _REPO_ROOT / 'src/ui/tabs/macro/section_short.py')

    def test_section_news_ai_clean(self):
        assert not _find_undefined_names(
            _REPO_ROOT / 'src/ui/tabs/macro/section_news_ai.py')

    def test_section_state_clean(self):
        assert not _find_undefined_names(
            _REPO_ROOT / 'src/ui/tabs/macro/section_state.py')

    def test_tab_stock_picker_clean(self):
        assert not _find_undefined_names(
            _REPO_ROOT / 'src/ui/tabs/tab_stock_picker.py')

    def test_picker_fetcher_clean(self):
        assert not _find_undefined_names(
            _REPO_ROOT / 'src/data/stock/picker_fetcher.py')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
