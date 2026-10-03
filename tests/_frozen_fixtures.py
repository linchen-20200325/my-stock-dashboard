"""tests 共用：全 repo 掃描類測試 `ast.parse` 凍結副本時，只壓掉那一則已知的跳脫警告（批 Y3 S7-n2，2026-10-03）。

為什麼：`tests/fixtures/secret_scrub_{792c7a2,bf0ada3}.py` 是 `shared/secret_scrub.py` 的**逐位元組凍結副本**
（sha256 守衛見 `tests/test_sec_s6_batch_s6.py`／`tests/test_sec_s4_batch_s4.py`，⛔ 不得改），其 docstring 含 `\\/`
⇒ 編譯時 Python 3.11 發 `DeprecationWarning: invalid escape sequence '\\/'`（3.12+ 改發 `SyntaxWarning`）。
載入端（`_load_main`／`_load_bf0`）在批 S7 已就地壓掉；但 `rglob` 全 repo 的掃描類測試
（`tests/test_zz_test_portability.py`、`tests/test_ui_state_model.py`）每次 `ast.parse` 這兩份副本仍各發一次。

怎麼做：同批 S7 載入端的寫法 —— **只對這兩份副本**、**只壓訊息比對 `invalid escape sequence` 的那一則**，
其餘檔案與其餘警告一律照常（⛔ 不是整類 DeprecationWarning 一起關掉）。
"""
from __future__ import annotations

import ast
import pathlib
import warnings

#: 已知 docstring 含 `\/`、且逐位元組凍結不得改的副本（檔名；位於 `tests/fixtures/`）。
FROZEN_ESCAPE_FIXTURES: frozenset[str] = frozenset({"secret_scrub_792c7a2.py", "secret_scrub_bf0ada3.py"})


def is_frozen_escape_fixture(path: pathlib.Path) -> bool:
    p = pathlib.Path(path)
    return p.parent.name == "fixtures" and p.parent.parent.name == "tests" and p.name in FROZEN_ESCAPE_FIXTURES


def parse_source(text: str, path: pathlib.Path, **kw) -> ast.Module:
    """`ast.parse(text, **kw)`；`path` 是上列凍結副本時，壓掉 `invalid escape sequence` 那一則警告。"""
    if not is_frozen_escape_fixture(path):
        return ast.parse(text, **kw)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"invalid escape sequence", category=DeprecationWarning)
        warnings.filterwarnings("ignore", message=r"invalid escape sequence", category=SyntaxWarning)
        return ast.parse(text, **kw)
