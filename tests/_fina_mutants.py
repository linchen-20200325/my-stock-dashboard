"""tests/_fina_mutants.py — 真正的原始碼突變工具（DEC-150 QA 回修）。

把被測模組的原始碼改寫一處（`old` 必須恰出現 1 次）後 exec 成獨立模組物件，**不動磁碟檔案、不影響其他測試**；
讓「拔掉 guard → 測試轉紅」測的是被測碼本身，而不是 monkeypatch 一個必然失敗的 lambda。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_mutant(rel_path: str, old: str, new: str, name: str = "_fina_mutant") -> types.ModuleType:
    src = (REPO / rel_path).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變錨點應恰出現 1 次，實得 {src.count(old)}：{old!r}"
    mod_name = f"{name}_{abs(hash((rel_path, old, new)))}"
    mod = types.ModuleType(mod_name)
    mod.__file__ = str(REPO / rel_path)
    mod.__package__ = ".".join(Path(rel_path).with_suffix("").parts[:-1])
    sys.modules[mod_name] = mod          # dataclass 等需要 sys.modules 查得到
    try:
        exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    return mod


def load_real(rel_path: str) -> types.ModuleType:
    """未突變的同一套載入流程（對照組：確認 harness 本身載得起來、guard 測試在原碼上為綠）。"""
    src = (REPO / rel_path).read_text(encoding="utf-8")
    mod_name = f"_fina_real_{abs(hash(rel_path))}"
    mod = types.ModuleType(mod_name)
    mod.__file__ = str(REPO / rel_path)
    mod.__package__ = ".".join(Path(rel_path).with_suffix("").parts[:-1])
    sys.modules[mod_name] = mod
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return mod
