"""tab_mj_health_diff.py — v18.186 「📊 MJ 體檢變化」Streamlit Tab

純讀 disk 快照（zero LLM cost）。流程：
  1. 由 user 選股或從快照清單下拉選
  2. load_latest_two → 自動撈最近 2 季快照
  3. diff_mj_health → 變好/變差/不變 verdict
  4. 渲染紅綠雙色矩陣 + is_turnaround / is_breakdown banner

新增快照走既有 MJ 體檢 Tab 的「💾 存檔本季結果」按鈕（未來補）；
本 Tab 只負責 view 既有快照。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from mj_health_diff import diff_mj_health
from mj_snapshot_io import (
    list_all_stocks_with_snapshots,
    list_snapshots,
    load_latest_two,
    load_snapshot,
)

_VERDICT_BADGES = {
    "improving": ("🟢 變好", "#22c55e"),
    "deteriorating": ("🔴 變差", "#ef4444"),
    "mixed": ("🟡 分歧", "#eab308"),
    "stable": ("⚪ 穩定", "#888"),
}


def _badge(verdict: str) -> tuple[str, str]:
    return _VERDICT_BADGES.get(verdict, (verdict, "#888"))


def _render_diff_table(verdict) -> None:
    """渲染變好/變差/不變 3 區塊。"""
    if verdict.improvements:
        st.markdown(f"#### 🟢 變好 ({verdict.improve_count} 項)")
        df = pd.DataFrame([{
            "模組": m.module.replace("_Module", ""),
            "指標": m.metric,
            "上期": m.prev_status,
            "本期": m.curr_status,
        } for m in verdict.improvements])
        st.dataframe(df, use_container_width=True, hide_index=True)

    if verdict.deteriorations:
        st.markdown(f"#### 🔴 變差 ({verdict.deteriorate_count} 項)")
        df = pd.DataFrame([{
            "模組": m.module.replace("_Module", ""),
            "指標": m.metric,
            "上期": m.prev_status,
            "本期": m.curr_status,
        } for m in verdict.deteriorations])
        st.dataframe(df, use_container_width=True, hide_index=True)

    if verdict.unchanged:
        with st.expander(f"⚪ 不變 ({len(verdict.unchanged)} 項) — 點開細看", expanded=False):
            df = pd.DataFrame([{
                "模組": m.module.replace("_Module", ""),
                "指標": m.metric,
                "Status": m.curr_status,
            } for m in verdict.unchanged])
            st.dataframe(df, use_container_width=True, hide_index=True)


def render_mj_health_diff_tab() -> None:
    """v18.186 主畫面。"""
    st.markdown("## 📊 MJ 體檢變化（v18.186）")
    st.caption(
        "讀本地 MJ 體檢快照（`data_cache/mj_snapshots/`），"
        "對最近 2 季做 status 等級比對，偵測「**變好 / 變差 / 不變**」逐項。"
        "**零 LLM 成本** — 新增快照請至 MJ 體檢 Tab。"
    )

    # ── 1. 列出有快照的股票 ───────────────────────────────────
    sids = list_all_stocks_with_snapshots()
    if not sids:
        st.warning(
            "🟡 **目前 `data_cache/mj_snapshots/` 無任何快照**\n\n"
            "請先到 MJ 體檢 Tab 跑單股分析並存檔。"
            "未來會在該 Tab 加「💾 存檔本季結果」按鈕。"
        )
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        sid = st.selectbox(
            "股票代碼",
            sids,
            key="_mj_diff_sid",
            help=f"目前有快照的標的：{len(sids)} 檔",
        )
    with c2:
        min_net_delta = st.number_input(
            "雜訊緩衝門檻",
            min_value=1, max_value=10, value=1, step=1,
            key="_mj_diff_min_delta",
            help="improve − deteriorate ≥ 此值才判 improving，避免 1 項異動誤觸",
        )

    if not sid:
        return

    # ── 2. 顯示可用快照清單 ───────────────────────────────────
    yms = list_snapshots(sid)
    st.caption(f"📁 {sid} 可用快照：{', '.join(yms) if yms else '無'}")

    if len(yms) < 2:
        st.info(
            f"ℹ️ **{sid} 僅有 {len(yms)} 季快照**，需至少 2 季才能比對變化。"
            f"請至 MJ 體檢 Tab 跑下一季財報後存檔。"
        )
        if yms:
            with st.expander(f"📄 顯示既有快照 {yms[0]}（單期）", expanded=False):
                st.json(load_snapshot(sid, yms[0]))
        return

    # ── 3. 載入最近 2 季 + diff ──────────────────────────────
    prev, curr, p_ym, c_ym = load_latest_two(sid)
    verdict = diff_mj_health(prev, curr, stock_id=sid, min_net_delta=int(min_net_delta))

    # ── 4. Verdict banner ────────────────────────────────────
    label, color = _badge(verdict.verdict)
    st.markdown(
        f"### {label} ｜ {p_ym} → {c_ym} ｜ "
        f"net Δ = <span style='color:{color}'>**{verdict.net_delta:+d}**</span> "
        f"(變好 {verdict.improve_count} / 變差 {verdict.deteriorate_count})",
        unsafe_allow_html=True,
    )

    # 鏡像旗標 banner
    if verdict.is_turnaround:
        st.success(
            "🌅 **本業虧轉盈**（Core_Business_Profitable: No → Yes）— "
            "MJ 體檢偵測到核心業務由虧轉賺，是強烈轉機訊號。"
        )
    if verdict.is_breakdown:
        st.error(
            "⛈️ **本業盈轉虧**（Core_Business_Profitable: Yes → No）— "
            "MJ 體檢偵測到核心業務由賺轉虧，需高度警戒。"
        )

    # ── 5. 變好/變差/不變表 ──────────────────────────────────
    _render_diff_table(verdict)

    # ── 6. Raw JSON debug ────────────────────────────────────
    with st.expander("🛠️ Raw verdict JSON（diff 細節）", expanded=False):
        st.json(verdict.to_dict())
