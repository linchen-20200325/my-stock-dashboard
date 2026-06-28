"""v18.334 守衛：抓取進行中只留下方 spinner，頂部看板空標題不先冒出。

User 回報：載入時有兩個下載畫面（頂部「正在重新載入」+ 底部 spinner），且
今日市場總覽 / 今日作戰室等空標題在資料到位前先出現。修法：抓取時清空頂部
placeholder、並 gate 這些標題 / 空狀態於 `not do_refresh`（非抓取照常顯示）。
"""
from __future__ import annotations

import re


def _src(p="src/ui/tabs/tab_macro.py"):
    return open(p, encoding="utf-8").read()


class TestLoadingGate:
    def test_top_reloading_message_removed(self):
        src = _src()
        assert "正在重新載入市場數據" not in src, "頂部『正在重新載入』訊息應移除（只留下方 spinner）"
        # 抓取時清空頂部 placeholder
        assert re.search(r"if do_refresh:\s*\n\s*_tl_placeholder\.empty\(\)", src), \
            "抓取時應 _tl_placeholder.empty() 清空頂部"

    def test_overview_heading_gated(self):
        src = _src()
        assert re.search(r"if not do_refresh:\s*\n\s*st\.divider\(\)\s*\n\s*\n?\s*st\.markdown\(\"\"\"<div[^\n]*\n<span[^\n]*🌍 今日市場總覽", src), \
            "今日市場總覽標題未 gate 於 not do_refresh"

    def test_warroom_heading_gated(self):
        src = _src()
        assert re.search(r"if not do_refresh:\s*\n\s*st\.markdown\('''<div[^\n]*linear-gradient", src), \
            "今日作戰室標題未 gate 於 not do_refresh"

    def test_warroom_empty_state_gated(self):
        src = _src()
        assert "elif not do_refresh:" in src
        assert re.search(r"elif not do_refresh:.*?點擊「🚀 一鍵更新全部數據」載入今日作戰室", src, re.S), \
            "今日作戰室空狀態未 gate 於 not do_refresh"
