"""v19.132 效能:產業熱力圖改 opt-in 載入 — 防回退成「每次 app run 冷抓數十檔」。

背景:`render_sector_heatmap` 位於 `tab_market → 產業熱力圖` 巢狀 tab。Streamlit 全 tab
body 每次 app run 都執行,故 66 檔類股 batch 冷抓在首次載入就跑(即使 user 當下沒看熱力圖)
→ 拖慢首屏。改「按鈕 opt-in + session 記憶」後,未點過 → 不冷抓。

本檔以 inspect.getsource 當 golden,防未來又被改回「進頁即冷抓」。
"""
from __future__ import annotations

import inspect

import src.ui.render.etf_render as render


def test_sector_heatmap_gated_before_fetch():
    """render_sector_heatmap 的 get_sector_returns 取數必須在 opt-in gate 之後。"""
    src = inspect.getsource(render.render_sector_heatmap)
    # session 記憶 opt-in 狀態
    assert "heatmap_loaded" in src, '應以 session_state heatmap_loaded 記憶已載入'
    # 未載入 → 顯示載入按鈕 + early return(不冷抓)
    assert "st.button('🗺️ 載入產業熱力圖'" in src or "載入產業熱力圖" in src, (
        '未載入時應顯示「載入產業熱力圖」按鈕')
    # gate（未載入 → early return）必須出現在 get_sector_returns 取數之前
    _idx_gate = src.find("if not st.session_state.get(_loaded_key)")
    _idx_fetch = src.find("get_sector_returns(")
    assert _idx_gate != -1 and _idx_fetch != -1, 'gate 與取數皆應存在'
    assert _idx_gate < _idx_fetch, 'opt-in gate 必須在 get_sector_returns 取數之前(避免冷抓)'
