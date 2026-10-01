"""DL-f1-s62（2026-10-01）：掃描排除條件只看 repo 內的路徑段，不看 repo 放在哪。

修前 `tests/test_deprecation_honesty.py` 與 `tests/test_sector_heatmap_universe_single_source.py` 以
`any(s in str(f) for s in ("__pycache__", ".git", "scratchpad", "wt-"))` 對**絕對路徑**做子字串比對 ——
repo 一放在含 `scratchpad` 或 `wt-` 字樣的路徑底下（代理的暫存工作區、`git worktree` 的 `wt-*` 目錄），
掃描集合就變成空集合，前者的 `test_accepted_table_has_no_stale_entries`、後者的 `test_the_one_place_is_l0`
因此假失敗（其餘「沒有違規」類斷言則對空集合假通過）。

本檔用 `tmp_path` 底下自建的假 repo（其**上層**路徑刻意含 `scratchpad` 與 `wt-`）驗兩件事：
1. 上層路徑的字樣不再讓檔案被濾掉；
2. repo **內**的 `__pycache__` / `.git` / `scratchpad` / `wt-*` 目錄照舊被濾掉（修前的排除意圖不變）。
"""
from __future__ import annotations

import pathlib

import pytest

from tests import test_deprecation_honesty as DH
from tests import test_sector_heatmap_universe_single_source as SHU

_MODS = pytest.mark.parametrize("mod", [DH, SHU], ids=["deprecation_honesty", "heatmap_single_source"])

#: repo 內應被濾掉的路徑（相對 repo）。
_EXCLUDED = (
    "src/__pycache__/x.py",
    "src/.git/x.py",
    "src/scratchpad/x.py",
    "src/wt-abc/x.py",
    "shared/pkg/wt-1/x.py",
)
#: repo 內應被收進來的路徑（含「字樣出現在段中、但不是整段／不是開頭」的邊界）。
_INCLUDED = (
    "src/a.py",
    "shared/b.py",
    "src/my_scratchpad_notes/x.py",   # 段名含 scratchpad 但不等於 → 收
    "src/newt-x/x.py",                # 段名含 wt- 但不在開頭 → 收
    "scripts/c.py",
)


def _fake_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    repo = tmp_path / "scratchpad" / "wt-agent" / "repo"     # 上層刻意含兩種字樣
    for rel in _EXCLUDED + _INCLUDED + ("app.py",):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("X = 1\n", encoding="utf-8")
    return repo


def _scanned(mod, repo: pathlib.Path) -> set[str]:
    return {f.relative_to(repo).as_posix() for f in mod._py_files()}


@_MODS
def test_parent_path_words_do_not_empty_the_scan(mod, tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    monkeypatch.setattr(mod, "_REPO", repo)
    got = _scanned(mod, repo)
    assert set(_INCLUDED) | {"app.py"} == got, "repo 上層路徑含 scratchpad / wt- 時不得整棵跳過"


@_MODS
def test_in_repo_excludes_still_apply(mod, tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path)
    monkeypatch.setattr(mod, "_REPO", repo)
    assert not set(_EXCLUDED) & _scanned(mod, repo), "repo 內的快取／暫存工作區照舊不掃"


@_MODS
def test_real_repo_scan_set_matches_legacy_rule_when_path_is_clean(mod):
    """在本 repo 實際檔案上：新規則與修前規則（套在**相對路徑**上）掃到的集合相同 —— 只修了「看哪段路徑」。"""
    legacy = ("__pycache__", ".git", "scratchpad", "wt-")
    got = {f.relative_to(mod._REPO).as_posix() for f in mod._py_files()}
    assert got, "掃描集合不得為空"
    for rel in got:
        assert not any(s in rel for s in legacy), rel
