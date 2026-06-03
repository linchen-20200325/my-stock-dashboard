"""tab_macro_validation.py — 台股總經 tab 歷史驗證 UI section (v18.159 Phase 3).

對應 tab_macro.py section 十「📊 總經訊號歷史驗證」.

v18.157 C 案降級：只剩 TWII drawdown 事件表（NDC + 領先指標移除）
v18.159 Phase 3 增量：對齊 fund repo macro_signal_lookback 風格，加 4 個台股本地
        訊號（外資 5 日累積賣超 / 融資餘額 / M1B-M2 缺口惡化 / TWII 20 日跌幅）
        對 TWII crisis 的命中率 + 平均提前天數驗證
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

# Session state cache：Phase 1 events 跨 rerun 保活，避免 Phase 3 button 吞 events
_PHASE1_CACHE_KEY = "_macro_tw_valid_phase1"
_PHASE3_CACHE_KEY = "_macro_tw_valid_phase3"


def render_history_validation_section(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> None:
    """渲染「總經訊號歷史驗證」section（tab_macro section 十）.

    讀 TWII Parquet → 偵測 high-water-mark drawdown 事件 → 表 + 圖 + Phase 3 訊號回看。
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

    # ── 按鈕觸發 Phase 1 重算（結果存 session_state，避免 Phase 3 rerun 吞掉）
    if st.button("📊 跑歷史驗證", type="secondary", key="macro_tw_valid_run"):
        with st.spinner("讀取 Parquet ..."):
            twii_raw = load_twii_close_from_parquet(cache_dir)
        if twii_raw.empty:
            st.error("❌ twii_ohlcv.parquet 讀回空 series — 檢查 Parquet 完整性")
            return
        events_raw = detect_twii_crisis_events(
            twii_raw, drop_threshold=threshold_pct / 100.0)
        st.session_state[_PHASE1_CACHE_KEY] = {
            "threshold": threshold_pct,
            "events": events_raw,
            "twii": twii_raw,
        }
        # 門檻變動 → 失效 Phase 3 cache
        st.session_state.pop(_PHASE3_CACHE_KEY, None)

    cached = st.session_state.get(_PHASE1_CACHE_KEY)
    if not cached:
        st.caption("⬆️ 按按鈕開始（讀 Parquet → 偵測 crisis 事件，耗時 < 1 秒）")
        return

    if cached["threshold"] != threshold_pct:
        st.info(
            f"⚠️ 門檻已變動（cached={cached['threshold']}%, 目前={threshold_pct}%），"
            "請重按「跑歷史驗證」更新結果"
        )

    events = cached["events"]
    twii = cached["twii"]

    st.caption(
        f"📈 TWII 區間：{twii.index.min():%Y-%m-%d} ~ {twii.index.max():%Y-%m-%d}"
        f"（{len(twii):,} 筆）｜⚠️ 偵測到 {len(events)} 個 ≥{cached['threshold']}% 回撤事件"
    )

    if not events:
        st.warning(
            f"⚠️ 在 TWII 區間內無 ≥{cached['threshold']}% 回撤事件 — "
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

    # ── Phase 3：總經訊號預測力驗證 ────────────────
    _render_phase3_signal_section(events, cache_dir)


def _render_phase3_signal_section(events: list, cache_dir: Path) -> None:
    """🚦 Phase 3 — 4 個台股本地訊號 × TWII crisis 命中率（鏡像 fund Phase 3）。"""
    st.markdown("---")
    st.markdown("### 🚦 總經訊號預測力驗證（Phase 3）")
    st.caption(
        "對每個歷史危機事件回看 N 天前的總經訊號 → 量化「Tab1 訊號是否真的有預警」。"
        "公式鏡像 my-Fund-dashboard Phase 3；訊號來源為 `data_cache/` 4 表本地計算（"
        "外資 5 日累積賣超 / 融資餘額 / M1B-M2 缺口惡化 / TWII 20 日跌幅）。"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        offset_days = st.slider(
            "點觀測 offset（峰前 N 天）",
            min_value=30, max_value=180, value=90, step=10,
            help="觀察峰日往前 N 天的訊號值是否觸發警戒",
            key="macro_tw_phase3_offset",
        )
    with col_b:
        max_lookback_days = st.slider(
            "提前預警搜尋上限（峰前 M 天）",
            min_value=90, max_value=540, value=365, step=30,
            help="在峰前 M 天內搜尋訊號最早一次進入警戒區的日期",
            key="macro_tw_phase3_max_lookback",
        )

    if not st.button("🚦 跑訊號回看", type="secondary",
                     key="macro_tw_phase3_run"):
        cached_p3 = st.session_state.get(_PHASE3_CACHE_KEY)
        if not cached_p3:
            st.caption("⬆️ 按按鈕開始（4 訊號 × N 事件 × 點觀測，耗時 < 2 秒）")
            return
    else:
        # 跑訊號回看
        from macro_signal_lookback_tw import (
            DEFAULT_TW_SIGNALS,
            compute_signal_hit_rate,
            fetch_all_tw_signal_series,
            lookback_all_signals_tw,
        )

        with st.spinner("讀取 4 訊號 series ..."):
            series_by_key = fetch_all_tw_signal_series(cache_dir)
        with st.spinner(f"對 {len(events)} 個事件做訊號回看 ..."):
            lookbacks_by_key = lookback_all_signals_tw(
                events, series_by_key,
                specs=DEFAULT_TW_SIGNALS,
                lookback_days=int(offset_days),
                max_lookback_days=int(max_lookback_days),
            )
        # 計算命中率彙總
        summary_rows = []
        for spec in DEFAULT_TW_SIGNALS:
            stats = compute_signal_hit_rate(lookbacks_by_key[spec.key])
            arrow = "≥" if spec.direction == "above" else "≤"
            threshold_disp = f"{arrow} {spec.threshold:g}{spec.unit}"
            summary_rows.append({
                "訊號": spec.label,
                "閾值": threshold_disp,
                "涵蓋事件": stats["n_covered"],
                "命中事件": stats["n_hit"],
                "命中率": (f"{stats['hit_rate']:.0%}"
                            if stats["hit_rate"] is not None else "—"),
                "平均提前天數": (f"{stats['avg_lead_days']:.0f}"
                                  if stats["avg_lead_days"] is not None else "—"),
                "解讀": spec.note,
            })
        st.session_state[_PHASE3_CACHE_KEY] = {
            "offset": offset_days,
            "max_lookback": max_lookback_days,
            "summary_rows": summary_rows,
            "lookbacks": lookbacks_by_key,
            "specs": DEFAULT_TW_SIGNALS,
        }

    cached_p3 = st.session_state.get(_PHASE3_CACHE_KEY)
    if not cached_p3:
        return

    # ── 命中率總覽表 ────────────────────────────────
    st.markdown("#### 📊 訊號命中率總覽")
    st.dataframe(pd.DataFrame(cached_p3["summary_rows"]),
                  use_container_width=True, hide_index=True)

    # ── 逐事件 × 逐訊號明細 ──────────────────────────
    st.markdown("#### 🔬 逐事件明細")
    specs = cached_p3["specs"]
    lookbacks_by_key = cached_p3["lookbacks"]
    detail_rows = []
    for i, ev in enumerate(events):
        row = {
            "事件": str(ev.peak_date.date())[:7],
            "高點日": str(ev.peak_date.date()),
        }
        for spec in specs:
            lb = lookbacks_by_key[spec.key][i]
            if lb.lead_time_days is not None:
                cell = f"✅ 提前 {lb.lead_time_days}d"
            elif lb.value_at_lookback is not None:
                cell = (f"❌ ({lb.value_at_lookback:.2f}{spec.unit})"
                        if spec.unit else f"❌ ({lb.value_at_lookback:.2f})")
            else:
                cell = "—"
            row[spec.label] = cell
        detail_rows.append(row)
    st.dataframe(pd.DataFrame(detail_rows),
                  use_container_width=True, hide_index=True)

    st.caption(
        "✅ = 峰前搜尋上限區間內，訊號曾進入警戒區，並顯示提前天數；"
        "❌ = 訊號序列涵蓋但未警戒（顯示峰前 offset 觀測值）；"
        "— = 訊號歷史不涵蓋該事件（Parquet 缺檔 / 序列過短）。"
    )
