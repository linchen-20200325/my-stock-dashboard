"""tab_macro_validation.py — 台股總經 tab 歷史驗證 UI section (v18.157 C 案降級).

對應 tab_macro.py section 十「📊 總經訊號歷史驗證」.

設計（v18.157 簡化版）：
- 純 Streamlit 渲染薄殼，邏輯在 macro_validation_tw.py
- 只讀 data_cache/twii_ohlcv.parquet（NDC + 領先指標因 NAS FastAPI 中繼站
  未就緒已移除，請見 STATE.md v18.157）
- 缺檔（cron 尚未執行）→ 友善 banner 引導 user
- 跑驗證 → TWII drawdown 事件表 + 走勢圖 + CSV 下載
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from macro_validation_tw import (
    DEFAULT_PARQUET_CACHE_DIR,
    detect_twii_crisis_events,
    load_twii_close_from_parquet,
)


def render_history_validation_section(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> None:
    """渲染「總經訊號歷史驗證」section（tab_macro section 十）.

    讀 TWII Parquet → 偵測 high-water-mark drawdown 事件 → 表 + 圖。
    """
    st.markdown("---")
    st.markdown(
        "## 📊 十、總經訊號歷史驗證 — TWII 歷史崩盤事件清單"
    )
    st.caption(
        "把 data_cache 抓的 TWII 日 K 跑 high-water-mark 找 ≥X% 回撤事件，"
        "對應到歷史上的 7 場大型 crisis（2000 dot-com / 2008 GFC / 2011 歐債 /"
        " 2015 中股 / 2018 縮表 / 2020 COVID / 2022 升息）。"
        "資料源：`data_cache/twii_ohlcv.parquet`（每日 cron 自動更新）。"
    )

    # ── 資料存在性檢查 ────────────────────────────────
    twii_path = cache_dir / "twii_ohlcv.parquet"
    if not twii_path.exists():
        st.info(
            "⏳ TWII Parquet 尚未生成（等下次每日 cron / 或手動觸發 "
            "`update_macro_history.yml` workflow + bootstrap=true）。"
        )
        return

    # ── Slider ──────────────────────────────────────────
    threshold_pct = st.slider(
        "TWII 回撤門檻 ≥",
        min_value=10, max_value=40, value=20, step=5,
        help="峰前→谷底跌幅達此 % 才算「危機事件」",
        key="macro_tw_valid_threshold",
    )

    if not st.button(
            "📊 跑歷史驗證", type="secondary", key="macro_tw_valid_run"):
        st.caption("⬆️ 按按鈕開始（讀 Parquet → 偵測 crisis 事件，耗時 < 1 秒）")
        return

    # ── 讀 Parquet ─────────────────────────────────────
    with st.spinner("讀取 Parquet ..."):
        twii = load_twii_close_from_parquet(cache_dir)

    if twii.empty:
        st.error("❌ twii_ohlcv.parquet 讀回空 series — 檢查 Parquet 完整性")
        return

    # ── 偵測 crisis 事件 ──────────────────────────────
    events = detect_twii_crisis_events(
        twii, drop_threshold=threshold_pct / 100.0)

    st.caption(
        f"📈 TWII 區間：{twii.index.min():%Y-%m-%d} ~ {twii.index.max():%Y-%m-%d}"
        f"（{len(twii):,} 筆）｜⚠️ 偵測到 {len(events)} 個 ≥{threshold_pct}% 回撤事件"
    )

    if not events:
        st.warning(
            f"⚠️ 在 TWII 區間內無 ≥{threshold_pct}% 回撤事件 — "
            "試試把門檻調低（e.g. 10%）或等 Parquet 累積更多歷史"
        )
        return

    # ── 走勢圖：TWII + crisis 紅區 ────────────────────
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=twii.index, y=twii.values, mode="lines",
            name="TWII", line=dict(color="#1976d2", width=1.5),
        ))
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
            yaxis_title="TWII 收盤",
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:  # noqa: BLE001
        st.warning(f"⚠️ 走勢圖繪製失敗：{e}")

    # ── 事件表 ────────────────────────────────────────
    st.markdown("#### 🎯 TWII Crisis 事件清單")
    rows = []
    for ev in events:
        duration_days = (
            (ev.trough_date - ev.peak_date).days
            if hasattr(ev.peak_date, "to_pydatetime") else None
        )
        rows.append({
            "事件峰日": str(ev.peak_date.date()),
            "峰時收盤": f"{ev.peak_close:,.0f}",
            "谷底日": str(ev.trough_date.date()),
            "谷底收盤": f"{ev.trough_close:,.0f}",
            "回撤幅度": f"{ev.drawdown_pct:.1%}",
            "下跌天數": duration_days if duration_days is not None else "—",
            "復原日": (str(ev.recovery_date.date())
                       if ev.recovery_date is not None else "尚未復原"),
        })
    df_events = pd.DataFrame(rows)
    st.dataframe(df_events, use_container_width=True, hide_index=True)

    # ── CSV 下載 ─────────────────────────────────────
    try:
        ts = pd.Timestamp.today().strftime("%Y%m%d")
        st.download_button(
            "📥 Crisis 事件 CSV",
            data=df_events.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"twii_crisis_events_{ts}.csv",
            mime="text/csv",
            key="macro_tw_valid_events_csv",
            help="事件峰日 / 峰時收盤 / 谷底 / 回撤 / 復原日",
        )
    except Exception as e:  # noqa: BLE001
        st.caption(f"⚠️ CSV 匯出失敗：{e}")
