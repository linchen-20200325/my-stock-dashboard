"""src/ui/tabs/rs_leader_ui.py — 抗跌 RS 選股器 UI（L5，v19.70）。

需求:大盤下跌時（例如 2020 疫情崩盤），排出「仍贏過大盤」的相對強弱前 50。
Phase 1 = 即時模式（掃最近一段可調 lookback）；歷史視窗模式為 Phase 2（待接）。

§8.2 layer:L5 UI — 只組裝畫面 + 呼叫 L3 service（`rs_leader_service`）。
  fetch 在 L1、σRS 計分/排序在 L2、編排在 L3，本檔無任何 I/O / 計算邏輯。
§8.2.A EX-PASSTHRU-1：`fetch_twse_yield_pe`（名稱對照）/ `_fetch_news_for`（新聞）為 L5→L1 lazy。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.rs_screen_thresholds import (
    RS_DEFAULT_LOOKBACK,
    RS_LEADER_TOP_N,
    RS_LOOKBACK_PRESETS,
)
from src.services.rs_leader_service import build_rs_ai_prompt, run_rs_leader_scan


def render_rs_leader_screener(gemini_fn=None) -> None:
    """抗跌 / 逆勢 RS 選股器主畫面。

    Args:
        gemini_fn: 可選 AI 呼叫函式（app.py 傳 gemini_call）；有才顯示 AI 三型報告按鈕。
    """
    st.markdown("### 🛡️ 抗跌 / 逆勢贏大盤選股（RS 前 50）")
    st.caption(
        "🎯 找「大盤在跌時仍相對抗跌、甚至逆勢贏過大盤」的個股。以 **σ 標準化超額報酬**"
        "（個股報酬 − 大盤報酬，再用大盤波動標準化）排序——這是「跌勢中誰扛得住」最直接的衡量。"
    )

    with st.expander("💡 怎麼算 + 誠實揭露（點開看細節）", expanded=False):
        st.markdown(
            "**計算**（區間可調）：\n"
            "- 個股區間報酬 − 大盤（^TWII）同期報酬 = **超額報酬**（>0＝贏過大盤）\n"
            "- 再除以大盤日報酬標準差 → **RS（σ）**：+1σ 以上＝顯著逆勢強、0 附近＝與大盤連動、負值＝弱於大盤\n"
            "- 依 RS 降冪取前 " + str(RS_LEADER_TOP_N) + " 名\n\n"
            "**分級（TW 慣例，紅＝強）**：🔴 逆勢強股｜🟡 偏強抗跌｜⚪ 同步大盤｜🟢 落後大盤\n\n"
            "⚠️ **誠實揭露**：\n"
            "- 只掃**免費基本面存活池**（選股網那份「四項全過」約 300 多檔體質股），**非全上市**；"
            "很抗跌但體質沒過篩的個股可能沒進榜。\n"
            "- 這是**相對強弱**，不是買點：抗跌只代表跌得比大盤少 / 逆勢強，**不等於便宜或該追**。\n"
            "- 用**已收盤日線**；當日盤中不完整，隔日才齊。\n"
            "- **大盤在漲時「抗跌」語意不成立**，此時 RS 只代表誰漲更多（畫面會標示當期大盤漲跌）。\n\n"
            "🕹️ 你選了「兩者都要（先即時）」：目前是**即時模式**（掃最近一段）；"
            "**自訂歷史視窗（如回看 2020 疫情崩盤）**為第二階段，之後再加。"
        )

    # ── 參數 ────────────────────────────────────────────────
    _c1, _c2 = st.columns([2, 1])
    with _c1:
        _labels = list(RS_LOOKBACK_PRESETS.keys())
        _default_label = next(
            (k for k, v in RS_LOOKBACK_PRESETS.items() if v == RS_DEFAULT_LOOKBACK),
            _labels[0])
        _pick = st.radio(
            "觀察區間", _labels, index=_labels.index(_default_label),
            horizontal=True, key="rs_lookback_pick")
        _lookback = RS_LOOKBACK_PRESETS[_pick]
    with _c2:
        _beat_only = st.checkbox(
            "只留贏過大盤", value=True, key="rs_beat_only",
            help="勾選：只顯示區間報酬勝過大盤的（超額>0）。取消：全排（含落後，供對照）。")

    _refresh = st.checkbox(
        "強制重新抓取（忽略快取）", value=False, key="rs_refresh",
        help="預設用快取（TTL 1 小時）。勾選會重抓大盤 + 全池個股價，較慢。")

    if st.button("🔍 掃描抗跌強勢股", key="rs_scan_btn", type="primary"):
        _name_map: dict[str, str] = {}
        try:  # 名稱對照（L5 sibling，非 L1）
            from src.ui.tabs import fetch_twse_yield_pe
            _df_names = fetch_twse_yield_pe()
            if not _df_names.empty and "代碼" in _df_names.columns:
                _name_map = dict(zip(
                    _df_names["代碼"].astype(str),
                    _df_names.get("名稱", pd.Series([""] * len(_df_names))).astype(str)))
        except Exception as _en:
            print(f"[rs-ui] 名稱對照載入失敗: {_en}")

        with st.spinner(
            f"掃描中：基本面存活池逐檔抓 1 年日線 + 對比大盤 ^TWII（近 {_lookback} 交易日）"
            "（約 30 秒～1 分鐘）…"
        ):
            _rows, _meta = run_rs_leader_scan(
                lookback=_lookback, beat_only=_beat_only,
                refresh=_refresh, name_map=_name_map)
        st.session_state["_rs_rows"] = _rows
        st.session_state["_rs_meta"] = _meta

    _rows = st.session_state.get("_rs_rows")
    _meta = st.session_state.get("_rs_meta")
    if _rows is None:
        st.info("👆 點「🔍 掃描抗跌強勢股」開始（結果快取 1 小時，隔時或勾重抓才會再打）")
        return

    # ── 市場情境橫幅（抗跌語意是否成立）──────────────────────
    _mkt = (_meta or {}).get("market") or {}
    if _mkt.get("banner"):
        (st.info if _mkt.get("is_down") else st.warning)(_mkt["banner"])

    if _meta and _meta.get("note"):
        st.warning(_meta["note"])
    if not _rows:
        st.info("本次掃描無可排名標的（多為個股歷史不足或大盤暫時抓不到）。")
        return

    _df = pd.DataFrame(_rows)

    # ── Summary 卡 ──────────────────────────────────────────
    _cols = st.columns(4)
    with _cols[0]:
        st.metric("掃描檔數", f"{_meta.get('scanned', len(_df))} 檔")
    with _cols[1]:
        st.metric("進榜", f"{_meta.get('scored', len(_df))} 檔")
    with _cols[2]:
        _beat = int(_df["贏過大盤"].sum()) if "贏過大盤" in _df.columns else 0
        st.metric("贏過大盤", f"{_beat} 檔")
    with _cols[3]:
        _mr = _mkt.get("market_ret_pct")
        st.metric("大盤區間報酬", f"{_mr:+.1f}%" if isinstance(_mr, (int, float)) else "—")

    _df_show = _df.drop(columns=[c for c in ["_tier"] if c in _df.columns])

    st.markdown(f"#### 📋 抗跌 RS 排行（共 {len(_df_show)} 檔 · 依 RS(σ) 降冪）")
    st.dataframe(
        _df_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "RS(σ)": st.column_config.NumberColumn(
                "RS(σ)", format="%.2f",
                help="σ 標準化超額報酬。+1 以上＝顯著逆勢強、0 附近＝連動大盤、負值＝弱於大盤"),
            "個股報酬%": st.column_config.NumberColumn("個股報酬%", format="%+.1f"),
            "大盤報酬%": st.column_config.NumberColumn("大盤報酬%", format="%+.1f"),
            "超額%": st.column_config.NumberColumn(
                "超額%", format="%+.1f", help="個股 − 大盤（>0＝贏過大盤）"),
            "贏過大盤": st.column_config.CheckboxColumn("贏過大盤"),
            "訊號": st.column_config.TextColumn(
                "訊號", help="🔴 逆勢強股 / 🟡 偏強抗跌 / ⚪ 同步大盤 / 🟢 落後大盤"),
        },
    )

    _csv = _df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "💾 下載抗跌 RS 排行 CSV", data=_csv,
        file_name="rs_leader_screen.csv", mime="text/csv", key="rs_csv_dl")

    if _meta:
        st.caption(
            f"候選池來源：{_meta.get('pool_source', '?')}｜掃描 {_meta.get('scanned', '?')} 檔"
            f"｜觀察 {_meta.get('lookback', '?')} 交易日"
            f"｜抓取時間 {_meta.get('fetched_at', '')[:19]} UTC"
        )

    # ── AI 三型建議報告（積極 / 穩健 / 保守）─────────────────────
    st.markdown("---")
    if not gemini_fn:
        st.caption("💡 未設定 GEMINI_API_KEY，無法生成 AI 三型建議報告。")
        return
    _ai_key = f"_rs_ai_report_{hash(tuple(str(r.get('代碼', '')) for r in _rows[:10]))}"
    _clicked = st.button(
        "🤖 生成抗跌股 AI 三型建議報告（積極 / 穩健 / 保守）",
        key="rs_ai_btn", use_container_width=True, type="primary")
    if _clicked:
        _md = st.session_state.get(_ai_key)
        if _md is None:
            _news = ""
            try:  # best-effort 相關新聞（L5→L1 lazy，EX-PASSTHRU-1）
                from src.data.etf import _fetch_news_for
                _news = _fetch_news_for("台股", "台股 大盤 下跌 抗跌 逆勢 強勢股 資金", 5)
            except Exception as _en:
                print(f"[rs-ui] news 抓取失敗: {_en}")
            with st.spinner("AI 三型策略分析中（約 8–12 秒）…"):
                _prompt = build_rs_ai_prompt(_rows, _meta, top_n=10, news_text=_news)
                try:
                    _md = gemini_fn(_prompt)
                except Exception as _ea:
                    _md = f"❌ AI 生成失敗：{type(_ea).__name__}: {_ea}"
            st.session_state[_ai_key] = _md
        st.markdown(_md)
    elif st.session_state.get(_ai_key):
        st.markdown(st.session_state[_ai_key])
