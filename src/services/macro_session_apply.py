"""src/services/macro_session_apply.py — session patch 的**寫入端**（L3，薄）。

T3-1 寫入層的**下半**。上半是 L2 純函式
`src/compute/macro/macro_session_patch.py::build_macro_session_patch`
（要寫什麼 / 要刪什麼，零 streamlit）。

本檔**只做三件事**：把上一輪的兩個值從 session 讀出來 → 呼叫純函式 →
`update()` ＋逐個 `pop()`。**不得**在這裡長出任何分支判斷 ——
一旦有判斷，它就跟著 streamlit 一起變成不可測的東西，
拆這兩半的意義（見純函式檔頭）就沒了。

§8.2 分層：L3。import streamlit **只為 `st.session_state`**（不是 cache、
不是 UI 呼叫），與既有的 `jingqi_calc` / `market_assessment_apply` 同一個形態。
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from src.compute.macro.macro_session_patch import build_macro_session_patch


def apply_macro_bundle(bundle: Mapping[str, Any], *,
                       load_heavy: bool,
                       now_str: str) -> tuple[dict[str, Any], tuple[str, ...]]:
    """把 bundle 寫進 `st.session_state`，並回傳「實際寫了什麼 / 刪了什麼」。

    Args:
        bundle: `fetch_macro_bundle()` 的回傳。
        load_heavy: 這一輪有沒有抓重資料。**呼叫端傳**（見純函式檔頭：
            拿 bundle 內容反推會在「熱啟動但全敗」時判錯）。
        now_str: 時間戳（`shared.macro_compute.tw_now_str()`）。

    Returns:
        `(patch, pops)` 原樣回傳 —— 呼叫端據此在交付報告 / 畫面上
        **逐鍵列出這一輪碰了什麼**（§-1.5.F 判定 6：清理與寫入項目是強制欄位，
        不得只寫「更新了一些資料」）。
    """
    patch, pops = build_macro_session_patch(
        bundle,
        load_heavy=load_heavy,
        prev_li_latest=st.session_state.get("li_latest"),
        prev_li_retain_meta=st.session_state.get("li_retain_meta"),
        now_str=now_str,
    )
    st.session_state.update(patch)
    for _k in pops:
        st.session_state.pop(_k, None)
    return patch, pops
