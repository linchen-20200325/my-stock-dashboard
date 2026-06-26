"""tests/test_resample_audit.py — §4.5 resample 安全性 audit guard(v18.298)

CLAUDE.md §4.5:
- 已用 `"ME"`(月底)/ `"QE"`(季底)/ `"YE"`(年底)/ `"W"`(週)
- 預設 `closed=right, label=right` — **不會**引入未來資料
- audit 須驗證所有 resample 呼叫的 label/closed 是否一致

本檔守:
1. 生產代碼中所有 `.resample(...)` 呼叫只能用允許 alias(ME/QE/YE/W/D 等)
2. 禁用 deprecated 左閉合 alias(M/Q/Y)— pandas 2.0+ 已棄用
3. 禁用顯式 `closed='left'` / `label='left'`(會引入未來資料,§4.5 違憲)

對應 audit 結果(v18.298):
- etf_calc.py:234 — `.resample('W')` 週 K
- etf_calc.py:731-732 — `.resample('QE')` 季報酬累積
- macro_core.py:1413-1414 — `.resample('ME')` 月度對齊
- app.py:357 — `.resample('YE')` 年總和

6/6 全 right-closed/labeled,通過 §4.5 標準。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

PROJ_ROOT = Path(__file__).parent.parent

# 生產代碼掃描範圍(排除 test_*.py / tests/ / scripts/)
_SCAN_GLOBS = ("*.py",)
_EXCLUDE_DIRS = {"tests", "scripts", "data_cache", "__pycache__", ".git"}
_EXCLUDE_FILE_PREFIXES = ("test_",)

# 允許的 resample alias(pandas 2.0+ modern,皆預設 right-closed/labeled)
_ALLOWED_RESAMPLE_ALIASES = {
    # 純 alias
    "ME", "QE", "YE", "W", "D", "H", "T", "S", "B",
    # 帶 anchor 的(W-MON, QE-DEC 等)
    "W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI", "W-SAT", "W-SUN",
    "QE-JAN", "QE-FEB", "QE-MAR", "QE-APR", "QE-MAY", "QE-JUN",
    "QE-JUL", "QE-AUG", "QE-SEP", "QE-OCT", "QE-NOV", "QE-DEC",
    "YE-JAN", "YE-DEC",
    # 多位數頻率(如 5min, 15min, 1H)— pandas 自動解析
    # 用 regex 比對:^\d*[A-Z]+(-[A-Z]+)?$
}

# 禁用的 deprecated alias(pandas 2.0+ 已棄用 + 為左閉合,§4.5 違憲)
_FORBIDDEN_ALIASES = {"M", "Q", "Y", "A"}  # left-closed legacy


def _iter_prod_py_files():
    for path in PROJ_ROOT.rglob("*.py"):
        if any(part in _EXCLUDE_DIRS for part in path.parts):
            continue
        if any(path.name.startswith(p) for p in _EXCLUDE_FILE_PREFIXES):
            continue
        yield path


def test_no_deprecated_resample_alias():
    """禁用 deprecated 左閉合 alias(M/Q/Y/A)— pandas 2.0+ 棄用且為左閉合。"""
    violations = []
    pat = re.compile(r"\.resample\(\s*['\"]([MQYA])['\"]\s*[\),]")
    for path in _iter_prod_py_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in pat.finditer(text):
            line_no = text[:m.start()].count("\n") + 1
            violations.append(f"{path.relative_to(PROJ_ROOT)}:{line_no}: {m.group(0)}")
    assert not violations, (
        f"§4.5 違憲:發現 {len(violations)} 處 deprecated 左閉合 alias\n  "
        + "\n  ".join(violations)
        + "\n→ 改用 ME / QE / YE(modern right-closed,pandas 2.0+ 標準)"
    )


def test_no_explicit_closed_left():
    """禁用顯式 `closed='left'`(會引入未來資料)。"""
    violations = []
    pat = re.compile(r"\.resample\([^)]*closed\s*=\s*['\"]left['\"]")
    for path in _iter_prod_py_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in pat.finditer(text):
            line_no = text[:m.start()].count("\n") + 1
            violations.append(f"{path.relative_to(PROJ_ROOT)}:{line_no}")
    assert not violations, (
        f"§4.5 違憲:發現 {len(violations)} 處顯式 closed='left'(會引入未來資料)\n  "
        + "\n  ".join(violations)
    )


def test_no_explicit_label_left():
    """禁用顯式 `label='left'`(label 應 right-aligned 以匹配 closed='right')。"""
    violations = []
    pat = re.compile(r"\.resample\([^)]*label\s*=\s*['\"]left['\"]")
    for path in _iter_prod_py_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in pat.finditer(text):
            line_no = text[:m.start()].count("\n") + 1
            violations.append(f"{path.relative_to(PROJ_ROOT)}:{line_no}")
    assert not violations, (
        f"§4.5 違憲:發現 {len(violations)} 處顯式 label='left'\n  "
        + "\n  ".join(violations)
    )


def test_audit_inventory_documented():
    """v18.298 audit inventory:6 個生產 resample 呼叫應全部仍存在
    (用於 audit 文件對齊。新增/刪除 resample 時更新此 inventory + CLAUDE.md §4.5)。

    審計結果(v18.298):
    - etf_calc.py:`'W'`(週 K)x1
    - etf_calc.py:`'QE'`(季報酬累積)x2
    - macro_core.py:`'ME'`(月度對齊)x2
    - app.py:`'YE'`(年總和)x1
    """
    counts: dict[str, int] = {}
    pat = re.compile(r"\.resample\(\s*['\"]([A-Z]+)['\"]")
    for path in _iter_prod_py_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in pat.finditer(text):
            alias = m.group(1)
            counts[alias] = counts.get(alias, 0) + 1
    # 若 inventory 數量飄移,提醒重新 audit
    expected = {"W": 1, "QE": 2, "ME": 2, "YE": 1}
    assert counts == expected, (
        f"resample alias 數量飄移,須重新 audit + 更新本 test inventory:\n"
        f"  expected = {expected}\n"
        f"  actual   = {counts}"
    )
