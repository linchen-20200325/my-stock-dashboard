"""src/ui/tabs/stock_grp_sections/section_watchlist_health.py — 🩺 組合體檢 section(L5).

就使用者維護的清單(上方輸入框 / 「帶入我的持股」/ 選股池)逐檔判「vs 基準是否落後」:
個股 vs 大盤(加權指數 ^TWII)、ETF vs 0050。資料入口 = L3 watchlist_health_service
(它讀 L1 取價 + L2 純判定);本層只組裝畫面。

§8.2 L5:只呼叫 L3 service,不直呼 L1 fetcher / 不算指標。
§1:抓價成本高 → 按鈕觸發(不每次 rerun 重抓);缺資料/無法判定由 service 誠實標 ⚪,
本層不補值、不亂建議替換股(MVP 只點名 + 理由)。

對外 API:render_watchlist_health_section(stock_list) -> None
"""
from __future__ import annotations

import streamlit as st

_ROWS_KEY = "_watchlist_health_rows"
_LIST_KEY = "_watchlist_health_for"

_TABLE_COLS = ["代號", "類型", "基準", "燈號", "連敗季數",
               "相對基準%", "大跌弱勢率%", "反彈弱勢率%", "動作建議"]


def render_watchlist_health_section(stock_list) -> None:
    """🩺 組合體檢：逐檔 vs 基準（個股→大盤、ETF→0050）落後判定。"""
    st.markdown("#### 🩺 組合體檢 — 逐檔 vs 基準（是否該檢視變更）")
    st.caption(
        "就你上方清單逐檔比基準：**個股 vs 大盤（加權指數）、ETF vs 0050**。"
        "看誰連續季輸基準、累積落後多少 → 判斷是否該檢視。即時抓價，按鈕觸發。")

    _codes = [str(c).strip() for c in (stock_list or []) if str(c).strip()]
    if not _codes:
        st.info("💡 先在上方輸入代碼、或按「🔗 帶入我的持股（Google Sheet）」載入清單，再執行體檢。")
        return

    if st.button("🩺 執行組合體檢（逐檔抓價比對，約數秒）", key="_wh_run_btn"):
        with st.spinner("體檢中：逐檔抓價 vs 基準…"):
            from src.services.watchlist_health_service import get_watchlist_health_rows
            st.session_state[_ROWS_KEY] = get_watchlist_health_rows(_codes)
            st.session_state[_LIST_KEY] = list(_codes)

    _rows = st.session_state.get(_ROWS_KEY)
    if not _rows:
        return

    # 清單已變更 → 提示重跑(§1:不拿舊清單的結果冒充新清單)
    if st.session_state.get(_LIST_KEY) != _codes:
        st.warning("⚠️ 清單已變更，以下為上次體檢結果，請重按「執行組合體檢」更新。")

    from src.services.watchlist_health_service import summarize_laggards
    _lag = summarize_laggards(_rows)
    if _lag:
        st.warning("⚠️ **亮警示（連續輸基準 / 雙向弱勢）**：建議檢視是否保留 —— "
                   + "、".join(f"{r['代號']}（{r['燈號']}）" for r in _lag))
    else:
        st.success("✅ 清單內沒有標的連續落後基準；體質正常者續抱觀察即可。")

    import pandas as pd
    _df = pd.DataFrame([{_c: r.get(_c) for _c in _TABLE_COLS} for r in _rows])
    st.dataframe(_df, use_container_width=True, hide_index=True)
    st.caption(
        "相對基準% = 該檔近 1 年累積報酬 − 基準累積報酬（**負 = 落後**）；"
        "連敗季數 = 最近連續幾季輸基準；⚪ = 資料不足 / 樣本不足 / 非台股代號（誠實不判，不猜）。"
        "本區只點名 + 理由，不自動建議替換標的。")
