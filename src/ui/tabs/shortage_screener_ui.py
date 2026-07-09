"""src/ui/tabs/shortage_screener_ui.py — 缺貨 / 供不應求選股器 UI（L5，v19.65）。

「缺貨選股」用四個間接財務/營運訊號交叉驗證「市場供不應求」：
  ① 合約負債大增  ② 毛利率走揚  ③ 存貨週轉天數下降  ④ 月營收 YoY 連續成長
四項計分（滿分 100）→ 🟥強 / 🟧中 / ⬜不明顯，全市場掃描出排行。

§8.2 layer:L5 UI — 只組裝畫面 + 呼叫 L3 service（`shortage_screener_service`）。
  fetch 在 L1、計分在 L2、編排在 L3，本檔無任何 I/O / 計算邏輯。
§8.2.A EX-PASSTHRU-1：`fetch_twse_yield_pe` 為 L5 sibling（名稱對照用），非 L1 fetcher。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.data.stock.monthly_revenue_fetcher import _get_token
from src.services.shortage_screener_service import (
    build_shortage_ai_prompt,
    run_shortage_scan,
)
from shared.shortage_screen_thresholds import (
    SHORTAGE_DEEP_SCAN_MAX,
    TIER_MID,
    TIER_STRONG,
    TIER_WEAK,
)


def render_shortage_screener(gemini_fn=None) -> None:
    """缺貨 / 供不應求選股器主畫面。

    Args:
        gemini_fn: 可選 AI 呼叫函式（app.py 傳 gemini_call）；有才顯示 AI 三型報告按鈕。
    """
    st.markdown("### 🔥 缺貨 / 供不應求選股")
    st.caption(
        "🎯 用四個**間接財務/營運訊號**交叉驗證「市場供不應求」的股票（現貨即時報價難取得，改看財報足跡）："
        "① 合約負債大增（客戶預付訂金搶產能）② 毛利率走揚（成功轉嫁漲價）"
        "③ 存貨週轉天數下降（做出來就賣掉）④ 月營收 YoY 連續成長。"
    )

    if not _get_token():
        st.error(
            "🔴 **未偵測到 FINMIND_TOKEN 環境變數**\n\n"
            "本功能需 FinMind sponsor tier 抓月營收 + 季財報。請至「🔎 資料診斷」Tab 檢查 API 金鑰狀態。"
        )
        return

    with st.expander("💡 計分規則 + 誠實揭露（點開看細節）", expanded=False):
        st.markdown(
            "**計分（滿分 100）**：\n"
            "- ① 合約負債 **35 分**：YoY≥30%→滿分｜15–30%→20｜QoQ≥20% 再 +10；"
            "**查無合約負債科目 → 0 分並標降級**（服務/金融業常見，不當成壞事）\n"
            "- ② 毛利率 **25 分**：季增+年增雙升→滿分｜只一項→12\n"
            "- ③ 存貨天數 **20 分**：較上季+去年同季雙降→滿分｜只一項→10"
            "（DIO＝存貨 ÷（近 4 季成本 ÷ 365），年化避免單季粗估失真）\n"
            "- ④ 月營收 **20 分**：近月 YoY 皆>15% 且逐月遞增→滿分｜皆>15%→12｜部分→5\n\n"
            "**分級**：≥65 🟥 強缺貨訊號｜40–64 🟧 中度｜<40 ⬜ 不明顯\n\n"
            "⚠️ **誠實揭露（候選池來源）**：為避免撞 FinMind 速限 + 相容免費方案，候選池**優先用**"
            "選股網那份**免費離線基本面存活池**（四項全過的股票），再逐檔（單股）深掃前 "
            f"{SHORTAGE_DEEP_SCAN_MAX} 檔的合約負債/毛利/存貨/月營收。代表本器找的是「**基本面健康 + 出現缺貨"
            "財務特徵**」的股票；只在存活池抓不到時，才退回需 FinMind sponsor 等級的「全市場月營收批次」。"
            "金融股（代號 28/58）不適用本模型，已排除。\n\n"
            "🚨 **這不是買賣建議**：財報有 ~45 天發布延遲，訊號屬「事後驗證」，請搭配技術面/籌碼面自行判斷。"
        )

    _refresh = st.checkbox(
        "強制重新抓取（忽略當日快取）", value=False, key="shortage_refresh",
        help="預設用當日快取（TTL 1 天）。勾選會重打 FinMind，較慢。",
    )

    if st.button("🔍 掃描全市場缺貨股", key="shortage_scan_btn", type="primary"):
        # 名稱對照（L5 sibling，非 L1）
        _name_map: dict[str, str] = {}
        try:
            from src.ui.tabs import fetch_twse_yield_pe
            _df_names = fetch_twse_yield_pe()
            if not _df_names.empty and "代碼" in _df_names.columns:
                _name_map = dict(zip(
                    _df_names["代碼"].astype(str),
                    _df_names.get("名稱", pd.Series([""] * len(_df_names))).astype(str),
                ))
        except Exception as _en:
            print(f"[shortage-ui] 名稱對照載入失敗: {_en}")

        with st.spinner(
            f"掃描中：基本面存活池 → 深掃前 {SHORTAGE_DEEP_SCAN_MAX} 檔財報（合約負債/毛利/存貨/月營收）"
            "（約 1–3 分鐘，每檔打 FinMind）…"
        ):
            _rows, _meta = run_shortage_scan(refresh=_refresh, name_map=_name_map)
        st.session_state["_shortage_rows"] = _rows
        st.session_state["_shortage_meta"] = _meta

    _rows = st.session_state.get("_shortage_rows")
    _meta = st.session_state.get("_shortage_meta")
    if _rows is None:
        st.info("👆 點「🔍 掃描全市場缺貨股」開始（結果快取一天，隔日或勾重抓才會再打 FinMind）")
        return

    if _meta and _meta.get("note"):
        st.warning(_meta["note"])
    if not _rows:
        st.info("本次掃描無可評分標的（多為候選池財報季數不足或缺科目）。")
        return

    _df = pd.DataFrame(_rows)

    # ── Summary 卡 ──────────────────────────────────────────
    _cols = st.columns(4)
    _tier_series = _df["_tier"] if "_tier" in _df.columns else pd.Series([], dtype=str)
    with _cols[0]:
        st.metric("深掃檔數", f"{_meta.get('deep_scanned', len(_df))} 檔")
    with _cols[1]:
        st.metric("🟥 強缺貨", f"{int((_tier_series == TIER_STRONG).sum())} 檔")
    with _cols[2]:
        st.metric("🟧 中度", f"{int((_tier_series == TIER_MID).sum())} 檔")
    with _cols[3]:
        st.metric("⬜ 不明顯", f"{int((_tier_series == TIER_WEAK).sum())} 檔")

    _df_show = _df.drop(columns=[c for c in ["_tier"] if c in _df.columns])

    st.markdown(f"#### 📋 缺貨排行（共 {len(_df_show)} 檔 · 依缺貨分數降冪）")
    st.dataframe(
        _df_show,
        use_container_width=True,
        hide_index=True,
        column_config={
            "缺貨分數": st.column_config.ProgressColumn(
                "缺貨分數", min_value=0, max_value=100, format="%.0f",
                help="四訊號加總（滿分 100）。≥65 強缺貨 / 40–64 中度 / <40 不明顯",
            ),
            "訊號強度": st.column_config.TextColumn(
                "訊號強度", help="🟥 強缺貨 / 🟧 中度 / ⬜ 不明顯"),
            "①合約負債": st.column_config.NumberColumn(
                "①合約負債", help="滿分 35：合約負債 YoY/QoQ 成長（客戶預付搶產能）"),
            "②毛利率": st.column_config.NumberColumn(
                "②毛利率", help="滿分 25：毛利率季增+年增雙升（成功轉嫁漲價）"),
            "③存貨天數": st.column_config.NumberColumn(
                "③存貨天數", help="滿分 20：存貨週轉天數下降（做出來就賣掉）"),
            "④月營收": st.column_config.NumberColumn(
                "④月營收", help="滿分 20：月營收 YoY 連續成長"),
            "理由": st.column_config.TextColumn("理由", width="large"),
        },
    )

    # ── CSV 下載 ────────────────────────────────────────────
    _csv = _df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "💾 下載缺貨排行 CSV", data=_csv,
        file_name="shortage_screen.csv", mime="text/csv", key="shortage_csv_dl",
    )

    if _meta:
        st.caption(
            f"候選池來源：{_meta.get('pool_source', '?')}｜{_meta.get('candidates', '?')} 檔 → "
            f"深掃 {_meta.get('deep_scanned', '?')} 檔｜抓取時間 {_meta.get('fetched_at', '')[:19]} UTC"
        )

    # ── AI 三型建議報告（積極 / 穩健 / 保守）─────────────────────
    st.markdown("---")
    if not gemini_fn:
        st.caption("💡 未設定 GEMINI_API_KEY，無法生成 AI 三型建議報告。")
        return
    _ai_key = f"_shortage_ai_report_{hash(tuple(str(r.get('代碼', '')) for r in _rows[:10]))}"
    _clicked = st.button(
        "🤖 生成缺貨股 AI 三型建議報告（積極 / 穩健 / 保守）",
        key="shortage_ai_btn", use_container_width=True, type="primary",
    )
    if _clicked:
        _md = st.session_state.get(_ai_key)
        if _md is None:
            _news = ""
            try:  # best-effort 相關新聞（L5→L1 lazy，EX-PASSTHRU-1）
                from src.data.etf import _fetch_news_for
                _news = _fetch_news_for("台股", "台股 缺貨 供不應求 產能 漲價 急單", 5)
            except Exception as _en:
                print(f"[shortage-ui] news 抓取失敗: {_en}")
            with st.spinner("AI 三型策略分析中（約 8–12 秒）…"):
                _prompt = build_shortage_ai_prompt(_rows, top_n=10, news_text=_news)
                try:
                    _md = gemini_fn(_prompt)
                except Exception as _ea:
                    _md = f"❌ AI 生成失敗：{type(_ea).__name__}: {_ea}"
            st.session_state[_ai_key] = _md
        st.markdown(_md)
    elif st.session_state.get(_ai_key):
        st.markdown(st.session_state[_ai_key])
