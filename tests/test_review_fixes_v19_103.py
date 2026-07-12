# -*- coding: utf-8 -*-
"""v19.103 — scripts/ sys.path guard 通用不變量(第二個現場後一次鎖死)。

病史:`python scripts/xxx.py` 直跑時 sys.path[0]=scripts/,不含 repo root →
`src.*` import 必 ImportError。已兩度實錘:
- v19.101:update_macro_history m1m2 段(靜默跳過數月)
- v19.103:calibrate_macro_traffic(季度校準 Actions run 當場炸,user 回報)

本測試把不變量升級為**通用掃描**:凡 scripts/*.py 內含 `src.*` import
(頂層或函式內 lazy),必須有 repo-root sys.path guard — 未來新增 script
漏 guard 會在 CI 直接紅,不必再等生產炸。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = sorted((REPO / "scripts").glob("*.py"))


def _has_src_import(text: str) -> bool:
    return re.search(r"^\s*(from|import) src\.", text, re.M) is not None


def _has_guard(text: str) -> bool:
    return "sys.path.insert" in text


@pytest.mark.parametrize("script", _SCRIPTS, ids=lambda p: p.name)
def test_scripts_with_src_imports_have_syspath_guard(script):
    text = script.read_text(encoding="utf-8")
    if not _has_src_import(text):
        pytest.skip("此 script 無 src.* import,不需 guard")
    assert _has_guard(text), (
        f"{script.name} 內含 src.* import 但缺 repo-root sys.path guard — "
        f"`python scripts/{script.name}` 直跑必 ImportError"
        f"(v19.101/v19.103 兩度實錘的同病)。模板見 calibrate_health_weights.py 頂部。"
    )


def test_calibrate_macro_traffic_guard_present():
    # 本次實錘個案的具名回歸鎖
    text = (REPO / "scripts/calibrate_macro_traffic.py").read_text(encoding="utf-8")
    assert "_REPO_ROOT" in text and "sys.path.insert" in text
