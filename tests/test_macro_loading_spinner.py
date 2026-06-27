"""v18.333 守衛：台股總經抓取改用 st.spinner 動畫載入指示（對齊 Fund tab1）。

原本只有靜態 st.info 文字 + 按鈕殘留，阻塞抓取時畫面看似凍結、分不清是否載完
（user 回報：基金有下載符號、台股看不出來是否下載好）。改 st.spinner 包住整段
抓取 → 動畫旋轉、結束自動消失。
"""
from __future__ import annotations

import re


def _src(p="tab_macro.py"):
    return open(p, encoding="utf-8").read()


class TestFetchSpinner:
    def test_spinner_wraps_fetch(self):
        src = _src()
        assert "with st.spinner('🚀 並行抓取 總經 + 籌碼 + 先行指標中" in src, \
            "抓取未用 st.spinner 動畫載入指示"
        # spinner 緊接抓取計時起點（確認包住的是抓取段，非他處）
        assert re.search(
            r"with st\.spinner\([^\n]*並行抓取[^\n]*\):\s*\n\s*import time as _t_spd",
            src,
        ), "spinner 未正確包住抓取 pipeline 起點"

    def test_old_static_only_info_replaced(self):
        """舊『_fetch_ph.info(並發抓取全部市場數據中)』靜態唯一指示已移除。"""
        src = _src()
        assert "並發抓取全部市場數據中" not in src, "舊靜態載入文字應已由 spinner 取代"
