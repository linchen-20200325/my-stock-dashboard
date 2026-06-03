"""tab_macro_validation.py — 台股總經 tab 歷史驗證 UI section (v18.150 Phase C).

對應 tab_macro.py section 十「📊 總經訊號歷史驗證」.

設計：
- 純 Streamlit 渲染薄殼，純函式邏輯在 macro_validation_tw.py
- 讀 data_cache/finmind_ndc_signal.parquet + finmind_leading_index.parquet + twii_ohlcv.parquet
- 缺檔（cron 尚未執行）→ 友善 banner 引導 user
- 跑驗證 → 兩張命中表（NDC + 領先指標）+ 走勢圖 + 兩張命中率卡 + CSV 下載
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from macro_validation_tw import (
    DEFAULT_PARQUET_CACHE_DIR,
    compute_hit_rate,
    compute_smoothed_change_pct,
    detect_twii_crisis_events,
    load_leading_index_from_parquet,
    load_ndc_signal_from_parquet,
    load_twii_close_from_parquet,
    verify_leading_index_vs_crises,
    verify_ndc_signal_vs_crises,
)


def render_history_validation_section(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> None:
    """渲染「總經訊號歷史驗證」section（tab_macro section 十）.

    讀 Parquet → 偵測 TWII crisis → 同步驗證 NDC 信號 + 領先指標的預警能力。
    """
    st.markdown("---")
    st.markdown(
        "## 📊 十、總經訊號歷史驗證 — 「Tab 判定 vs 歷史崩盤」 對照"
    )
    st.caption(
        "把 data_cache 抓的 TWII 日 K 跑 high-water-mark 找 ≥20% 回撤事件 → "
        "回去驗 NDC 景氣對策信號 + 領先指標在崩盤前 N 月是否真的有翻空訊號。"
        "資料源：`data_cache/*.parquet`（每日 cron 自動更新；無 streamlit 即時抓 FinMind）。"
    )

    # ── 資料存在性檢查 ────────────────────────────────
    ndc_path = cache_dir / "finmind_ndc_signal.parquet"
    li_path = cache_dir / "finmind_leading_index.parquet"
    twii_path = cache_dir / "twii_ohlcv.parquet"

    missing = []
    if not ndc_path.exists():
        missing.append("NDC 景氣對策信號（finmind_ndc_signal.parquet）")
    if not li_path.exists():
        missing.append("領先指標（finmind_leading_index.parquet）")
    if not twii_path.exists():
        missing.append("TWII 日 K（twii_ohlcv.parquet）")

    if missing:
        st.info(
            "⏳ 以下 Parquet 尚未生成（等下次每日 cron / 或手動觸發 "
            "`update_macro_history.yml` workflow + bootstrap=true）：\n\n"
            + "\n".join(f"- {m}" for m in missing)
        )
        return

    # ── Sliders ──────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        threshold_pct = st.slider(
            "TWII 回撤門檻 ≥",
            min_value=10, max_value=40, value=20, step=5,
            help="峰前→谷底跌幅達此 % 才算「危機事件」",
            key="macro_tw_valid_threshold",
        )
    with col_b:
        lead_months = st.slider(
            "預警觀測：峰前 N 月",
            min_value=3, max_value=12, value=6, step=1,
            help="比較峰前 N 月 NDC/領先指標 vs 峰月，判定是否預警下降",
            key="macro_tw_valid_lead",
        )
    with col_c:
        ndc_drop_pts = st.slider(
            "NDC 命中門檻：下降 ≥ 分",
            min_value=2, max_value=10, value=4, step=1,
            help="NDC 9-45 分，4 分 ≈ 跨 1 燈號（藍→黃 / 黃→紅）",
            key="macro_tw_valid_ndc_pts",
        )

    if not st.button(
            "📊 跑歷史驗證", type="secondary", key="macro_tw_valid_run"):
        st.caption(
            "⬆️ 按按鈕開始（讀 Parquet → 偵測 crisis → 雙指標命中表，耗時 < 1 秒）")
        return

    # ── 讀 Parquet ─────────────────────────────────────
    with st.spinner("讀取 Parquet ..."):
        ndc = load_ndc_signal_from_parquet(cache_dir)
        li = load_leading_index_from_parquet(cache_dir)
        twii = load_twii_close_from_parquet(cache_dir)

    if twii.empty:
        st.error("❌ twii_ohlcv.parquet 讀回空 series — 檢查 Parquet 完整性")
        return

    # ── 偵測 crisis 事件 ──────────────────────────────
    events = detect_twii_crisis_events(
        twii, drop_threshold=threshold_pct / 100.0)

    cap_parts = [
        f"📈 TWII 區間：{twii.index.min():%Y-%m-%d} ~ {twii.index.max():%Y-%m-%d}（{len(twii):,} 筆）",
        f"📊 NDC 月份：{len(ndc)}",
        f"📊 領先指標月份：{len(li)}",
        f"⚠️ 偵測到 {len(events)} 個 ≥{threshold_pct}% 回撤事件",
    ]
    st.caption("｜".join(cap_parts))

    if not events:
        st.warning(
            f"⚠️ 在 TWII 區間內無 ≥{threshold_pct}% 回撤事件 — "
            "試試把門檻調低（e.g. 10%）或等 Parquet 累積更多歷史"
        )
        return

    # ── 跑驗證 ─────────────────────────────────────────
    ndc_results = verify_ndc_signal_vs_crises(
        ndc, events, lead_months=lead_months,
        drop_pts_threshold=ndc_drop_pts,
    )
    li_results = verify_leading_index_vs_crises(
        li, events, lead_months=lead_months, smooth_window=6,
    )

    # ── 命中率卡 ─────────────────────────────────────
    col_x, col_y = st.columns(2)
    with col_x:
        n_hit, n_total, rate = compute_hit_rate(ndc_results)
        st.metric(
            "NDC 信號預警命中率",
            f"{n_hit}/{n_total} = {rate:.0%}" if n_total > 0 else "—",
            help=f"命中 = 峰前 {lead_months} 月 → 峰時 NDC 下降 ≥ {ndc_drop_pts} 分",
        )
    with col_y:
        n_hit, n_total, rate = compute_hit_rate(li_results)
        st.metric(
            "領先指標預警命中率",
            f"{n_hit}/{n_total} = {rate:.0%}" if n_total > 0 else "—",
            help="命中 = 峰月 6M smoothed change < 0（領先指標已翻負）",
        )

    # ── 走勢圖：TWII + NDC + crisis 紅區 ────────────
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        # TWII 主軸
        fig.add_trace(go.Scatter(
            x=twii.index, y=twii.values, mode="lines",
            name="TWII", line=dict(color="#1976d2", width=1.5),
        ), secondary_y=False)
        # NDC 副軸
        if not ndc.empty:
            fig.add_trace(go.Scatter(
                x=ndc.index, y=ndc.values, mode="lines+markers",
                name="NDC 景氣分數", line=dict(color="#f57c00", width=1.5),
                marker=dict(size=4),
            ), secondary_y=True)
        # crisis 紅區
        for ev in events:
            x1 = ev.recovery_date if ev.recovery_date is not None else ev.trough_date
            fig.add_vrect(
                x0=ev.peak_date, x1=x1,
                fillcolor="#d32f2f", opacity=0.12,
                line_width=0,
            )
        fig.update_layout(
            height=420,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", y=1.05),
        )
        fig.update_yaxes(title_text="TWII 收盤", secondary_y=False)
        fig.update_yaxes(title_text="NDC 分數（9~45）", secondary_y=True,
                          range=[5, 47])
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:  # noqa: BLE001
        st.warning(f"⚠️ 走勢圖繪製失敗：{e}")

    # ── NDC 命中表 ────────────────────────────────────
    st.markdown("#### 🎯 NDC 信號 × TWII 事件命中表")
    if ndc_results:
        rows = [{
            "事件峰日": str(r.peak_date.date()),
            "TWII 回撤": f"{r.drawdown_pct:.1%}",
            f"峰前 {lead_months}M NDC": r.ndc_at_lead if r.ndc_at_lead is not None else "—",
            "峰時 NDC": r.ndc_at_peak if r.ndc_at_peak is not None else "—",
            "下降分數": (f"{r.ndc_drop_pts:+d}" if r.ndc_drop_pts is not None else "—"),
            "預警": "✅" if r.hit else "❌",
        } for r in ndc_results]
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                      hide_index=True)
    else:
        st.caption("（NDC 資料不足，無命中表）")

    # ── 領先指標命中表 ──────────────────────────────
    st.markdown("#### 🎯 領先指標 6M Smoothed × TWII 事件命中表")
    if li_results:
        rows = [{
            "事件峰日": str(r.peak_date.date()),
            "TWII 回撤": f"{r.drawdown_pct:.1%}",
            f"峰前 {lead_months}M 6M%": (f"{r.li_smooth_at_lead:+.2f}"
                                     if r.li_smooth_at_lead is not None else "—"),
            "峰時 6M%": (f"{r.li_smooth_at_peak:+.2f}"
                       if r.li_smooth_at_peak is not None else "—"),
            "預警": "✅" if r.hit else "❌",
        } for r in li_results]
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                      hide_index=True)
    else:
        st.caption("（領先指標資料不足，無命中表）")

    # ── CSV 下載 ─────────────────────────────────────
    try:
        ts = pd.Timestamp.today().strftime("%Y%m%d")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            ndc_df = ndc.reset_index().rename(columns={"index": "date"})
            ndc_df.columns = ["date", "ndc_signal"]
            st.download_button(
                "📥 NDC 月序列 CSV",
                data=ndc_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"ndc_signal_{ts}.csv",
                mime="text/csv",
                key="macro_tw_valid_ndc_csv",
                help="date, ndc_signal（9-45 分）",
            )
        with col_d2:
            li_df_out = li.reset_index().rename(columns={"index": "date"})
            li_df_out.columns = ["date", "leading_index"]
            # 順便附 smoothed change
            sm = compute_smoothed_change_pct(li, window=6)
            if not sm.empty:
                sm_df = sm.reset_index().rename(columns={"index": "date"})
                sm_df.columns = ["date", "smooth_6m_change_pct"]
                li_df_out = li_df_out.merge(sm_df, on="date", how="left")
            st.download_button(
                "📥 領先指標 + 6M smoothed CSV",
                data=li_df_out.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"leading_index_{ts}.csv",
                mime="text/csv",
                key="macro_tw_valid_li_csv",
                help="date, leading_index, smooth_6m_change_pct",
            )
    except Exception as e:  # noqa: BLE001
        st.caption(f"⚠️ CSV 匯出失敗：{e}")
