# -*- coding: utf-8 -*-
"""v19.101 — update_macro_history 舊頂層 import 路徑修正（m1m2 段真因）。

v18.359 檔案搬家後根目錄 proxy_helper.py / tw_macro.py shim 已刪,script 內
`from proxy_helper import ...` / `from tw_macro import ...` 恆 ImportError →
CBC(m1m2)段自搬家起靜默跳過(2026-07-11 Actions run 實錘;原 except 吞掉
exception 內容,只印固定字串,誤導成套件問題)。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = (REPO / "scripts/update_macro_history.py").read_text(encoding="utf-8")


class TestOldPathImportsGone:
    def test_no_bare_toplevel_proxy_helper_import(self):
        # 舊頂層路徑不得再出現(根目錄 shim v18.359 已刪)
        assert re.search(r"^\s*from proxy_helper import", SRC, re.M) is None
        assert re.search(r"^\s*from tw_macro import", SRC, re.M) is None

    def test_new_src_paths_present(self):
        assert "from src.data.proxy.proxy_helper import fetch_url" in SRC
        assert "from src.data.macro.tw_macro import CBC_MS1_URLS, fetch_cbc_ms1_rows" in SRC

    def test_repo_root_on_sys_path(self):
        # scripts/ 直跑時 sys.path[0]=scripts/,須顯式把 repo root 加進 sys.path
        assert "_REPO_ROOT" in SRC and "sys.path.insert" in SRC

    def test_import_error_message_carries_exception(self):
        # §1:except 不得吞掉真正錯誤內容(原固定字串害誤診成 bs4)
        assert "缺 proxy_helper / tw_macro，無法抓 CBC" not in SRC
        assert "{type(e).__name__}: {e}" in SRC


class TestImportResolution:
    def test_symbols_resolve_at_new_paths(self):
        # 新路徑的兩個符號必須真實存在(防再搬家後又留舊路徑)
        from src.data.macro.tw_macro import CBC_MS1_URLS, fetch_cbc_ms1_rows
        from src.data.proxy.proxy_helper import fetch_url
        assert callable(fetch_url) and callable(fetch_cbc_ms1_rows)
        assert isinstance(CBC_MS1_URLS, (list, tuple)) and len(CBC_MS1_URLS) >= 1
