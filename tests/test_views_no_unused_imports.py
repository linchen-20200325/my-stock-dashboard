"""tests/test_views_no_unused_imports.py — SA-r6：`src/ui/views/` 未用 import 的 CI 守衛。

缺口（HANDOFF SA-r6）：`src/ui/views/page_inspect.py` 曾出現未用的 import，只有 pyflakes 抓得到；
既有 `tests/test_no_undefined_names.py` 只查**未定義**名稱（`UndefinedName`），不查**未使用**。

範圍刻意只到 `src/ui/views/`（IA v2 View 層，逐頁落地中、改動最頻繁）——
⛔ 不擴到全 `src/`：本守衛只補 SA-r6 點名的缺口，其他目錄的既有狀態不在本項射程（§-1）。

現況（2026-09-27，基底 `1894b50`）：pyflakes 對 `src/ui/views/` **0 則** UnusedImport，
故豁免清單 `_ALLOWLIST` 為空。日後若真的需要保留某個「看似未用」的 import
（例如 re-export），在這裡登記 `(相對路徑, 名稱)` 並寫理由，⛔ 不要把整個檔案排除。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

try:
    from pyflakes.checker import Checker
    from pyflakes.messages import UnusedImport
    _HAS_PYFLAKES = True
except ImportError:  # CI（pr-check.yml）有 `pip install pyflakes`；本機沒裝時同既有守衛的處置
    _HAS_PYFLAKES = False

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VIEWS_DIR = _REPO_ROOT / "src" / "ui" / "views"

#: 明確豁免：`{(repo 相對路徑, import 名稱)}`。現況為空（見檔頭）。
_ALLOWLIST: frozenset = frozenset()


def _unused_imports_in_source(src: str, rel: str) -> list[tuple[str, str, int]]:
    tree = ast.parse(src, filename=rel)
    checker = Checker(tree, filename=rel)
    return [(rel, m.message_args[0], m.lineno) for m in checker.messages
            if isinstance(m, UnusedImport)]


def _view_files() -> list[Path]:
    return sorted(_VIEWS_DIR.rglob("*.py"))


pytestmark = pytest.mark.skipif(not _HAS_PYFLAKES, reason="pyflakes 未安裝(pip install pyflakes)")


def test_views_dir_is_non_empty():
    """前提：掃描範圍真的有檔（路徑改名時不要默默掃 0 檔變綠）。"""
    assert len(_view_files()) >= 5, _view_files()


def test_no_unused_imports_in_ui_views():
    hits = []
    for f in _view_files():
        rel = f.relative_to(_REPO_ROOT).as_posix()
        hits.extend(h for h in _unused_imports_in_source(f.read_text(encoding="utf-8"), rel)
                    if (h[0], h[1]) not in _ALLOWLIST)
    assert not hits, ("src/ui/views/ 有未使用的 import（刪掉，或在 _ALLOWLIST 登記理由）：\n"
                      + "\n".join(f"{r}:{ln}: {name!r}" for r, name, ln in hits))


def test_allowlist_entries_are_still_needed():
    """豁免清單不得留殘項：登記的 import 若已不再被 pyflakes 報，就該從清單拿掉。"""
    live = set()
    for f in _view_files():
        rel = f.relative_to(_REPO_ROOT).as_posix()
        live.update((r, n) for r, n, _ln in
                    _unused_imports_in_source(f.read_text(encoding="utf-8"), rel))
    stale = set(_ALLOWLIST) - live
    assert not stale, f"_ALLOWLIST 有已不需要的項目：{sorted(stale)}"


def test_detector_catches_an_unused_import_in_a_real_view_file():
    """自我驗證：在真的 view 原始碼裡插一行未用 import，偵測器必須報出來（不是恆綠）。"""
    f = _VIEWS_DIR / "page_inspect.py"
    rel = f.relative_to(_REPO_ROOT).as_posix()
    src = f.read_text(encoding="utf-8")
    assert _unused_imports_in_source(src, rel) == []
    mutated = src.replace("from __future__ import annotations\n",
                          "from __future__ import annotations\nimport colorsys\n", 1)
    assert mutated != src, "前提：page_inspect.py 仍以 `from __future__ import annotations` 開頭"
    got = _unused_imports_in_source(mutated, rel)
    assert [n for _r, n, _l in got] == ["colorsys"], got
