"""v18.330 PR-2B 守衛：總經出口 YoY 全來源失敗時不得捏造靜態值（§1 Fail Loud）。

原 `_fetch_export` 全敗回傳寫死 `{'yoy': 18.9, 'date': '2026-03-01',
'source': '靜態備援'}`，把假出口數據灌進儀表板 / MK 拐點 / AI 摘要。
PR-2B 改回空 dict（不貢獻 tw_export key），下游退「待取得」placeholder。
"""
from __future__ import annotations

import re


def _src(p="src/ui/tabs/tab_macro.py"):
    # P3-D1 v18.389:_fetch_export 下沉 macro_snapshot.fetch_export_block;
    # 守衛斷言改掃合集(主檔仍須無 "靜態備援"/"18.9" — 雙檔同步檢查)。
    base = open(p, encoding="utf-8").read()
    try:
        base += open("src/data/macro/macro_snapshot.py", encoding="utf-8").read()
    except FileNotFoundError:
        pass
    return base


class TestNoStaticExportFallback:
    def test_no_static_fallback_label(self):
        assert "靜態備援" not in _src(), "出口全敗不得回『靜態備援』捏造值（§1）"

    def test_no_fabricated_189_literal(self):
        # 不得再出現寫死的 yoy 18.9 靜態出口值
        assert not re.search(r"'yoy':\s*18\.9", _src()), "出口捏造值 18.9 應已移除"
        assert "'date': '2026-03-01'" not in _src()

    def test_export_total_fail_returns_empty(self):
        """_fetch_export 末段 fallback 應為 `return {}`（不捏造）。"""
        src = _src()
        # 鎖定 fallback 段落：log 行 + 緊接的 return {}
        assert "所有方案全失敗" in src
        m = re.search(r"所有方案全失敗.*?\n\s*return\s*\{\}", src, re.S)
        assert m, "全敗 fallback 應緊接 `return {}`（誠實回空）"
