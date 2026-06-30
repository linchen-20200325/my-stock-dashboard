"""src/ui/tabs/monthly_revenue_screener.py — 月營收進退篩選器 UI(L5).

v18.180 新增功能:篩選台股近 3 個月月營收呈現「進步 / 退步」趨勢的標的。

v18.400 U1 重構:fetch 層下沉 `src/data/stock/monthly_revenue_fetcher.py`(L1),
compute 層下沉 `src/compute/health/monthly_revenue_calc.py`(L2)。本檔僅留 UI。

判斷基準(YoY + MoM 雙條件):
  • 強進步 = 近 3 月 YoY 全 ≥ +threshold% 且 末月 MoM ≥ 0
  • 進步   = 近 3 月 YoY 全 > 0% 且 末月 MoM ≥ 0
  • 強退步 = 近 3 月 YoY 全 ≤ -threshold% 且 末月 MoM ≤ 0
  • 退步   = 近 3 月 YoY 全 < 0% 且 末月 MoM ≤ 0
  • 中性   = 其餘情境
  • 資料不足 = 不足 15 個月歷史
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.compute.health.monthly_revenue_calc import (
    TREND_LABELS,  # noqa: F401  # re-export for downstream callers
    filter_by_mode,
    screen_from_batch,
)
from src.data.stock.monthly_revenue_fetcher import (
    _get_token,
    fetch_batch_monthly_revenue,
)


def render_monthly_revenue_screener() -> None:
    """月營收進退篩選器主畫面。"""
    st.markdown("### 📈 月營收進退篩選")
    st.caption(
        "🎯 **判斷基準（YoY + MoM 雙條件）**：近 3 月年增率全正且末月月增率 ≥ 0 → 進步；"
        "全負且末月月增率 ≤ 0 → 退步。資料源：FinMind `TaiwanStockMonthRevenue`（每月 10 日公告）"
    )

    if not _get_token():
        st.error(
            "🔴 **未偵測到 FINMIND_TOKEN 環境變數**\n\n"
            "本功能需 FinMind sponsor tier 抓月營收歷史。請至「🔎 資料診斷」Tab 檢查 API 金鑰狀態。"
        )
        return

    with st.expander("💡 判斷規則細節（強進步 / 進步 / 退步 / 強退步）", expanded=False):
        st.markdown(
            "- **🚀 強進步** = 近 3 月 YoY 全 ≥ 門檻（預設 +15%）且末月 MoM ≥ 0\n"
            "- **📈 進步**   = 近 3 月 YoY 全 > 0% 且末月 MoM ≥ 0\n"
            "- **🔻 強退步** = 近 3 月 YoY 全 ≤ -門檻（預設 -15%）且末月 MoM ≤ 0\n"
            "- **📉 退步**   = 近 3 月 YoY 全 < 0% 且末月 MoM ≤ 0\n"
            "- **➖ 中性**   = 其餘情境（震盪/拐點未確認/混合方向）\n"
            "- **⚪ 資料不足** = 不足 15 個月歷史（含 12 個月 YoY 基期 + 3 個月當期）；上市未滿 1.5 年常見\n\n"
            "**為什麼要 YoY + MoM 雙條件？** YoY 排除季節性偏差（如 1 月電子業淡季），MoM 補捉「近期動量」防止靠基期低估的假進步。"
        )

    # ── 篩選條件 ──────────────────────────────────────────
    _c1, _c2, _c3 = st.columns([1, 1, 1])
    with _c1:
        _yoy_thr = st.slider(
            "強進步 / 強退步 YoY 門檻 (%)", 5.0, 50.0, 15.0, 1.0,
            help="近 3 月 YoY 全部超過此門檻 → 強進步；全部低於 -此門檻 → 強退步",
            key="mrev_yoy_threshold",
        )
    with _c2:
        _mode_label = st.radio(
            "篩選模式",
            ["🚀 強進步", "📈 進步（含強進步）", "📉 退步（含強退步）",
             "🔻 強退步", "全部"],
            index=1,
            key="mrev_mode",
            horizontal=False,
        )
        _mode_key = {
            "🚀 強進步": "strong_up",
            "📈 進步（含強進步）": "any_up",
            "📉 退步（含強退步）": "any_down",
            "🔻 強退步": "strong_down",
            "全部": "all",
        }[_mode_label]
    with _c3:
        _topn = st.number_input(
            "顯示上限筆數", min_value=10, max_value=500, value=100, step=10,
            help="排序後取前 N 筆（依末月 YoY 絕對值排序）",
            key="mrev_topn",
        )

    if st.button("📡 抓取全市場月營收 + 計算", key="mrev_fetch_btn", type="primary"):
        with st.spinner("正在抓全市場月營收（FinMind batch，約 15-60 秒）…"):
            _df_batch = fetch_batch_monthly_revenue(months=18)
        if _df_batch.empty:
            st.error(
                "🔴 **全市場月營收抓取失敗**\n\n"
                "可能原因：① FinMind tier 不支援 batch（無 data_id） ② token 過期 ③ 網路逾時\n\n"
                "👉 請至「🔎 資料診斷」Tab 檢查 API 狀態"
            )
            return
        st.success(f"✅ 抓到 **{_df_batch['stock_id'].nunique()}** 檔股票 × **{_df_batch['date'].nunique()}** 個月資料")
        st.session_state["_mrev_batch"] = _df_batch

        # 同步抓 TWSE 名稱對照
        try:
            from src.ui.tabs import fetch_twse_yield_pe
            _df_names = fetch_twse_yield_pe()
            if not _df_names.empty and "代碼" in _df_names.columns:
                st.session_state["_mrev_namemap"] = dict(zip(
                    _df_names["代碼"].astype(str),
                    _df_names.get("名稱", pd.Series([""] * len(_df_names))).astype(str),
                ))
        except Exception as _en:
            print(f"[mrev-screener] 名稱對照載入失敗: {_en}")
            st.session_state["_mrev_namemap"] = {}

    _df_batch = st.session_state.get("_mrev_batch")
    if _df_batch is None or _df_batch.empty:
        st.info("👆 請點擊「📡 抓取全市場月營收」開始")
        return

    # ── 計算 + 篩選 ─────────────────────────────────────────
    _namemap = st.session_state.get("_mrev_namemap", {})
    _df_screen = screen_from_batch(_df_batch, yoy_threshold=_yoy_thr, name_map=_namemap)
    _df_filtered = filter_by_mode(_df_screen, _mode_key)

    if _df_filtered.empty:
        st.warning(f"🟡 在「{_mode_label}」模式 + YoY 門檻 {_yoy_thr}% 下無符合標的，請放寬條件")
        return

    # 排序:依末月 YoY 絕對值降冪(強進步/退步浮上來)
    _df_filtered = _df_filtered.copy()
    _df_filtered["_abs_yoy"] = _df_filtered["YoY(%)"].abs()
    _df_filtered = _df_filtered.sort_values("_abs_yoy", ascending=False).head(int(_topn))
    _df_show = _df_filtered.drop(columns=["_abs_yoy", "_trend_key"])

    # ── Summary 卡 ─────────────────────────────────────────
    _summary_cols = st.columns(5)
    for _i, (_k, _label) in enumerate([
        ("strong_up", "🚀 強進步"),
        ("up", "📈 進步"),
        ("neutral", "➖ 中性"),
        ("down", "📉 退步"),
        ("strong_down", "🔻 強退步"),
    ]):
        _cnt = int((_df_screen["_trend_key"] == _k).sum())
        with _summary_cols[_i]:
            st.metric(_label, f"{_cnt} 檔")

    st.markdown(f"#### 📋 結果（共 {len(_df_show)} 檔 · 依 YoY 絕對值排序）")
    st.dataframe(_df_show, use_container_width=True, hide_index=True)

    # ── CSV 下載 ────────────────────────────────────────────
    _csv = _df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "💾 下載結果 CSV",
        data=_csv,
        file_name=f"monthly_revenue_screen_{_mode_key}_yoy{int(_yoy_thr)}.csv",
        mime="text/csv",
        key="mrev_csv_dl",
    )
