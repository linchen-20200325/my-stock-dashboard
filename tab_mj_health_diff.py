"""tab_mj_health_diff.py — v18.188「📊 MJ 體檢變化」批次 Tab

v18.188 重寫：從 v18.186 單股 selectbox 改成「text_area 多檔 batch」模式，
鏡像 `tab_stock_grp.py` 個股組合介面：

  1. text_area 自由貼代號（逗號/空格/換行，最多 10 檔）
  2. 對每檔 fetch_financial_statements → analyze_financial_health（純規則，零 LLM）
  3. save_snapshot(sid, current_yyyymm, mj_result) — 累積歷史
  4. load_latest_two(sid) → 若 ≥2 季 → diff_mj_health → verdict
  5. 結果表（紅綠燈）+ 退步在前排序 + 轉機/雷股 icon

引擎全 deterministic（不傳 news_context）。第一次跑只有本季快照、無法 diff；
跨季再跑後 diff 自動可用。**每按鈕都重新計算 MJ 指標**（user 拍板），但結果落 disk 累積歷史。
"""
from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from financial_health_engine import analyze_financial_health
from mj_health_diff import HealthDiffVerdict, diff_mj_health
from mj_snapshot_io import (
    current_finmind_yyyymm,
    load_latest_two,
    save_snapshot,
)

_VERDICT_BADGES = {
    "improving": ("🟢 進步", "#22c55e"),
    "deteriorating": ("🔴 退步", "#ef4444"),
    "mixed": ("🟡 分歧", "#eab308"),
    "stable": ("⚪ 不變", "#888"),
    "first_snapshot": ("⏳ 首季快照", "#3b82f6"),
    "fetch_failed": ("❌ 抓取失敗", "#6b7280"),
}

_VERDICT_SORT_ORDER = {
    "deteriorating": 0,
    "mixed": 1,
    "improving": 2,
    "stable": 3,
    "first_snapshot": 4,
    "fetch_failed": 5,
}


def parse_codes(raw: str, limit: int = 10) -> list[str]:
    """解析逗號/空格/換行分隔的股票代碼，過濾無效碼，去重保序。"""
    if not raw:
        return []
    parts = re.split(r"[,\s\n；，]+", str(raw).strip())
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        s = p.strip().upper()
        if not s or not re.match(r"^\d{4,6}[A-Z]?$", s):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _badge(verdict: str) -> tuple[str, str]:
    return _VERDICT_BADGES.get(verdict, (verdict, "#888"))


def _run_single_stock_diff(
    sid: str,
    yyyymm: str,
    finmind_token: str,
) -> dict[str, Any]:
    """單檔流程：fetch → analyze → save_snapshot → diff。

    回傳 row dict 供結果表渲染。
    """
    from src.data.core import fetch_financial_statements

    row: dict[str, Any] = {
        "代碼": sid,
        "本季": yyyymm,
        "verdict": "fetch_failed",
        "改善": 0,
        "惡化": 0,
        "淨變化": 0,
        "icon": "",
        "上季": "—",
        "_verdict_obj": None,
        "_error": "",
    }

    try:
        fin = fetch_financial_statements(sid, finmind_token)
    except Exception as e:  # pragma: no cover - defensive
        row["_error"] = f"{type(e).__name__}: {e}"
        return row

    if not fin or fin.get("error"):
        row["_error"] = (fin or {}).get("error", "fin_data 為空")
        return row

    try:
        mj_result = analyze_financial_health(finmind_token, sid, fin, news_context="")
    except Exception as e:  # pragma: no cover - defensive
        row["_error"] = f"analyze failed: {type(e).__name__}: {e}"
        return row

    if not isinstance(mj_result, dict):
        row["_error"] = "analyze_financial_health 回傳非 dict"
        return row

    save_snapshot(sid, yyyymm, mj_result)

    prev, curr, p_ym, c_ym = load_latest_two(sid)
    if not prev or not curr:
        row["verdict"] = "first_snapshot"
        row["上季"] = "—"
        return row

    v: HealthDiffVerdict = diff_mj_health(prev, curr, stock_id=sid, min_net_delta=1)
    row["verdict"] = v.verdict
    row["改善"] = v.improve_count
    row["惡化"] = v.deteriorate_count
    row["淨變化"] = v.net_delta
    row["上季"] = p_ym or "—"
    row["本季"] = c_ym or yyyymm
    row["_verdict_obj"] = v
    if v.is_turnaround:
        row["icon"] = "🌟 轉機"
    elif v.is_breakdown:
        row["icon"] = "⚠️ 雷股"
    return row


def _verdict_label(v: str) -> str:
    return _badge(v)[0]


def _render_result_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    rows_sorted = sorted(rows, key=lambda r: _VERDICT_SORT_ORDER.get(r["verdict"], 99))
    df = pd.DataFrame([{
        "代碼": r["代碼"],
        "判定": _verdict_label(r["verdict"]),
        "上季 → 本季": f"{r['上季']} → {r['本季']}",
        "改善": r["改善"],
        "惡化": r["惡化"],
        "淨變化": r["淨變化"],
        "標記": r["icon"] or "",
    } for r in rows_sorted])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_per_stock_detail(rows: list[dict[str, Any]]) -> None:
    """每檔可展開看變好/變差/不變項。"""
    diffable = [r for r in rows if r.get("_verdict_obj") is not None]
    if not diffable:
        return
    st.markdown("#### 🔍 逐檔細節")
    for r in diffable:
        v: HealthDiffVerdict = r["_verdict_obj"]
        label = _verdict_label(r["verdict"])
        with st.expander(
            f"{label}｜{r['代碼']}｜{r['上季']} → {r['本季']}｜"
            f"改善 {v.improve_count} / 惡化 {v.deteriorate_count}"
            + (f"｜{r['icon']}" if r["icon"] else ""),
            expanded=False,
        ):
            if v.improvements:
                st.markdown(f"##### 🟢 變好 ({v.improve_count} 項)")
                st.dataframe(pd.DataFrame([{
                    "模組": m.module.replace("_Module", ""),
                    "指標": m.metric,
                    "上期": m.prev_status,
                    "本期": m.curr_status,
                } for m in v.improvements]), use_container_width=True, hide_index=True)
            if v.deteriorations:
                st.markdown(f"##### 🔴 變差 ({v.deteriorate_count} 項)")
                st.dataframe(pd.DataFrame([{
                    "模組": m.module.replace("_Module", ""),
                    "指標": m.metric,
                    "上期": m.prev_status,
                    "本期": m.curr_status,
                } for m in v.deteriorations]), use_container_width=True, hide_index=True)
            if v.unchanged:
                with st.expander(f"⚪ 不變 ({len(v.unchanged)} 項)", expanded=False):
                    st.dataframe(pd.DataFrame([{
                        "模組": m.module.replace("_Module", ""),
                        "指標": m.metric,
                        "Status": m.curr_status,
                    } for m in v.unchanged]), use_container_width=True, hide_index=True)


def _render_fetch_failures(rows: list[dict[str, Any]]) -> None:
    fails = [r for r in rows if r["verdict"] == "fetch_failed"]
    if not fails:
        return
    with st.expander(f"❌ 抓取失敗（{len(fails)} 檔）— 點開看錯誤", expanded=False):
        for r in fails:
            st.markdown(f"- **{r['代碼']}**：{r['_error']}")


def render_mj_health_diff_tab() -> None:
    """v18.188 批次 MJ 體檢主畫面。"""
    st.markdown("## 📊 MJ 體檢變化（v18.188 批次版）")
    st.caption(
        "**批次跑 MJ 林明樟「4 力 1 棒子」財報體檢**，每按一次重新計算（零 LLM 燒錢，純規則引擎）。"
        "結果自動存 `data_cache/mj_snapshots/` 累積歷史 — **首季只有本季快照**，"
        "下季再跑後自動跨期 diff 出進步/退步。"
    )

    finmind_token = os.environ.get("FINMIND_TOKEN", "")
    if not finmind_token:
        try:
            finmind_token = st.secrets.get("FINMIND_TOKEN", "")
        except (FileNotFoundError, OSError, AttributeError):
            finmind_token = ""
    if not finmind_token:
        st.error("🔴 未設定 `FINMIND_TOKEN`（環境變數 / st.secrets）→ 無法抓財報。")
        return

    yyyymm = current_finmind_yyyymm(date.today())
    st.caption(f"📅 本次落地季別 **{yyyymm}**（依今日推算最近完成季）")

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            raw_input = st.text_area(
                "輸入多檔代碼（逗號/空格/換行，最多 10 檔）",
                value="2330 2454 2317 2382 3017 2308 2303 2376 6669 3661",
                height=68,
                key="_mj_batch_input",
                placeholder="例：2330 2454 2317 2382 3017",
            )
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            run_btn = st.button(
                "📡 跑批次體檢",
                type="primary",
                use_container_width=True,
                key="_mj_batch_run",
            )

    sids = parse_codes(raw_input, limit=10)
    if sids:
        st.caption(f"待體檢：{', '.join(sids)}（共 {len(sids)} 檔）")
    elif run_btn:
        st.warning("⚠️ 請先輸入至少一個有效股票代碼")
        return

    if not (run_btn and sids):
        return

    rows: list[dict[str, Any]] = []
    prog = st.progress(0.0, text=f"批次體檢 {len(sids)} 檔...")
    for i, sid in enumerate(sids, 1):
        prog.progress(i / len(sids), text=f"[{i}/{len(sids)}] {sid} 計算中...")
        row = _run_single_stock_diff(sid, yyyymm, finmind_token)
        rows.append(row)
    prog.empty()

    # ── 統計 banner ─────────────────────────────────────────────
    counts = {k: 0 for k in _VERDICT_BADGES}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    cols = st.columns(6)
    cols[0].metric("🔴 退步", counts["deteriorating"])
    cols[1].metric("🟡 分歧", counts["mixed"])
    cols[2].metric("🟢 進步", counts["improving"])
    cols[3].metric("⚪ 不變", counts["stable"])
    cols[4].metric("⏳ 首季", counts["first_snapshot"])
    cols[5].metric("❌ 失敗", counts["fetch_failed"])

    turnaround = [r["代碼"] for r in rows if r["icon"].startswith("🌟")]
    breakdown = [r["代碼"] for r in rows if r["icon"].startswith("⚠️")]
    if turnaround:
        st.success(f"🌟 **本業虧轉盈轉機股**：{', '.join(turnaround)}")
    if breakdown:
        st.error(f"⚠️ **本業盈轉虧雷股**：{', '.join(breakdown)}")

    _render_result_table(rows)
    _render_per_stock_detail(rows)
    _render_fetch_failures(rows)
