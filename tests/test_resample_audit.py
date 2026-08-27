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
# `.claude` 只是保險(agent 隔離 worktree 的慣用位置)。真正的防線是
# `_is_nested_checkout()` 的通用規則 —— 目錄名會換,「底下有 .git」不會。
_EXCLUDE_DIRS = {"tests", "scripts", "data_cache", "__pycache__", ".git", ".claude"}
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


def _is_nested_checkout(dir_path: Path) -> bool:
    """這個子目錄是不是「另一份獨立的 git checkout」?

    判定:目錄底下有 `.git` 就是 —— 它是**別份** checkout 的根,
    裡面的 .py 是本專案原始碼的**副本**,不是本專案的原始碼。
    兩種形態都要認得,故用 `exists()` 而非 `is_dir()`:
    - `.git` 是**檔案** → git worktree / submodule 的根(內容為 `gitdir: ...` 指標)
    - `.git` 是**目錄** → 一般 clone 的根

    為什麼寫通用規則,而不是硬編一個目錄名:
    agent 隔離用的 worktree 會被建在 repo 內(當前實例:
    `.claude/worktrees/agent-<id>/`,底下是一整份 repo 副本),
    於是每個 resample 呼叫被數兩遍 → 本檔 inventory 整齊翻倍。
    **下一次的目錄名不保證還叫 `.claude`**,但「巢狀 checkout 的根底下有 `.git`」
    是恆真的 —— 認 `.git` 才擋得住下一次。

    ⚠️ `.gitignore` 救不了這裡:本檔走的是檔案系統走訪,不看 git ignore。
    """
    return (dir_path / ".git").exists()


def _iter_prod_py_files():
    """走訪本專案自己的生產 .py。

    用 `os.walk` 而非 `rglob`,是為了能**就地剪枝** —— 被排除的目錄整棵不進去,
    而不是走進去之後再逐檔過濾(巢狀 checkout 有數百檔,逐檔過濾既慢又容易漏)。
    """
    for dirpath, dirnames, filenames in os.walk(PROJ_ROOT):
        here = Path(dirpath)
        # 就地改寫 dirnames:os.walk 讀它來決定下一層要不要進去
        dirnames[:] = [
            d for d in sorted(dirnames)
            if d not in _EXCLUDE_DIRS and not _is_nested_checkout(here / d)
        ]
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            if name.startswith(_EXCLUDE_FILE_PREFIXES):
                continue
            yield here / name


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
    """v18.298 audit inventory:生產 resample 呼叫應全部仍存在
    (用於 audit 文件對齊。新增/刪除 resample 時更新此 inventory + CLAUDE.md §4.5)。

    審計結果(v18.298 → v19.74 → v19.166 重新盤點):
    - etf_calc.py:`'W-SUN'`(週 K,v18.461 自 'W' 改錨定週日;right-closed 不變)x1
    - etf_calc.py:`'QE'`(季報酬累積)x2
    - macro_core.py:`'ME'`(月度對齊)x2
    - app.py:`'YE'`(年總和)x1
    - compute/etf/dividend_station.py:`'W-FRI'`(💰 存股戰情室週K,週五定案 +
      丟未收完當週防 lookahead;v19.166)x1

    v19.74:原 regex 只捕 `[A-Z]+` 純 alias,v18.461 'W'→'W-SUN' 後該筆
    從盤點消失(帶 anchor 的 alias 不匹配)→ 擴 regex 捕 anchored 形式。
    """
    counts: dict[str, int] = {}
    pat = re.compile(r"\.resample\(\s*['\"]([A-Z]+(?:-[A-Z]+)?)['\"]")
    for path in _iter_prod_py_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in pat.finditer(text):
            alias = m.group(1)
            counts[alias] = counts.get(alias, 0) + 1
    # 若 inventory 數量飄移,提醒重新 audit
    expected = {"W-SUN": 1, "QE": 2, "ME": 2, "YE": 1, "W-FRI": 1}
    assert counts == expected, (
        f"resample alias 數量飄移,須重新 audit + 更新本 test inventory:\n"
        f"  expected = {expected}\n"
        f"  actual   = {counts}"
    )
