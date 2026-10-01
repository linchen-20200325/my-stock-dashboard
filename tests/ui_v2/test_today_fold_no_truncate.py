"""SA2-f14（2026-10-01）：今天頁 16 張燈卡「▸ 詳細」摺疊區 ⛔ 不截斷（`fold_truncate=False`），
與查一檔／我的持股／找標的／憑什麼四頁對齊（客戶 2026-09-25「完整原文進摺疊、⛔ 不得只剩 hover」）。

修前：摺疊區的值超過 `FACT_VALUE_MAX_CHARS`（46）就截成「…」，全文只剩 `title=` hover。
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib

from src.ui.views import page_today as P
from src.ui_v2 import markup as M
from tests.ui_v2.test_lamp_card_fold import _live_tiles, _split

_LONG = "很長的命中來源" * 12          # 遠超過 46 字


def test_long_hit_source_is_shown_in_full_inside_the_fold():
    tiles = _live_tiles()
    assert len(tiles) == 16
    for key, t in tiles.items():
        t2 = dataclasses.replace(
            t, facts=tuple((k, (_LONG if P.v2_plain(k) == "命中來源" else v)) for k, v in t.facts))
        _outside, body = _split(P.v2_card_html(t2))
        assert _LONG in body, f"{key}: 摺疊區的「命中來源」被截斷了"
        assert M.FACT_VALUE_ELLIPSIS not in body, key


def test_call_site_passes_fold_truncate_false():
    """結構守衛：`v2_card_html()` 呼叫 `card_html()` 時明寫 `fold_truncate=False`（同另四頁）。"""
    src = pathlib.Path(P.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "v2_card_html")
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)
             and ast.unparse(c.func).endswith("card_html") and ast.unparse(c.func) != "v2_card_html"]
    assert len(calls) == 1
    kw = {k.arg: ast.unparse(k.value) for k in calls[0].keywords}
    assert kw.get("fold_truncate") == "False", kw
