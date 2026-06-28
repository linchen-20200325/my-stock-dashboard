"""src/ui/tabs/tab_macro_validation.py — 台股總經 tab 歷史驗證 UI section (v18.161 v2 edge UI).

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

from src.compute.macro import (
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
    st.markdown("### 🚦 總經訊號預測力驗證（Phase 3 · v2 轉折偵測）")
    st.caption(
        "🔄 **v2 edge detection**：對每個歷史危機事件，在峰前 M 天區間內搜尋訊號"
        "**從非警戒跨越到警戒**的最早**轉折日**（不是「找最早一個觸發警戒的日子」），"
        "排除「常態性已在警戒 → 假預警」誤判。公式鏡像 my-Fund-dashboard Phase 3；"
        "訊號來源為 `data_cache/` 4 表本地計算（外資 5 日累積賣超 / 融資餘額 / "
        "M1B-M2 缺口惡化 / TWII 20 日跌幅）。"
    )

    col_a, col_b, col_c = st.columns(3)
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
            min_value=60, max_value=365, value=180, step=30,
            help="在峰前 M 天內搜尋訊號『從非警戒跨越到警戒』的最早轉折日（edge detection）",
            key="macro_tw_phase3_max_lookback",
        )
    with col_c:
        # v18.163：精確率追蹤期 — 訊號響起後 K 天內若有 crisis 算 TP
        max_forward_days = st.slider(
            "📐 精確率追蹤期（crossing 後 K 天）",
            min_value=90, max_value=540, value=365, step=30,
            help="訊號響起後 K 天內若有危機事件 → TP；無 → FP（誤報）"
                 "。改此 slider 即時重算精確率，不需重按按鈕。",
            key="macro_tw_phase3_max_forward",
        )

    if not st.button("🚦 跑訊號回看", type="secondary",
                     key="macro_tw_phase3_run"):
        cached_p3 = st.session_state.get(_PHASE3_CACHE_KEY)
        if not cached_p3:
            st.caption("⬆️ 按按鈕開始（4 訊號 × N 事件 × 點觀測，耗時 < 2 秒）")
            return
    else:
        # 跑訊號回看
        from dataclasses import replace as _replace
        from src.compute.macro import (
            DEFAULT_TW_SIGNALS,
            compute_signal_hit_rate,
            fetch_all_tw_signal_series,
            lookback_all_signals_tw,
        )

        # v18.164: 套用 session-only threshold overrides（若 user 已採用建議）
        _overrides = st.session_state.get("_phase3_overrides", {})
        active_specs = [_replace(s, threshold=_overrides[s.key])
                         if s.key in _overrides else s
                         for s in DEFAULT_TW_SIGNALS]

        with st.spinner("讀取 4 訊號 series ..."):
            series_by_key = fetch_all_tw_signal_series(cache_dir)
        with st.spinner(f"對 {len(events)} 個事件做訊號回看 ..."):
            lookbacks_by_key = lookback_all_signals_tw(
                events, series_by_key,
                specs=active_specs,
                lookback_days=int(offset_days),
                max_lookback_days=int(max_lookback_days),
            )
        # 計算命中率彙總
        summary_rows = []
        for spec in active_specs:
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
                "平均提前轉折天數": (f"{stats['avg_lead_days']:.0f}"
                                       if stats["avg_lead_days"] is not None else "—"),
                "解讀": spec.note,
            })
        st.session_state[_PHASE3_CACHE_KEY] = {
            "offset": offset_days,
            "max_lookback": max_lookback_days,
            "summary_rows": summary_rows,
            "lookbacks": lookbacks_by_key,
            "specs": active_specs,  # v18.164: 含 session overrides
            "series_by_key": series_by_key,  # v18.163 for precision compute
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
                cell = f"✅ 轉折提前 {lb.lead_time_days}d"
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
        "✅ = 峰前 M 天區間內捕捉到「從非警戒**跨越**到警戒」的轉折日，顯示距峰提前天數；"
        "❌ = 訊號序列涵蓋但區間內無轉折事件（顯示峰前 offset 觀測值，可能整段未警戒或整段已警戒）；"
        "— = 訊號歷史不涵蓋該事件（Parquet 缺檔 / 序列過短）。"
    )

    # ── 📐 v18.163：訊號精確率分析（forward-looking）─────────────
    series_by_key = cached_p3.get("series_by_key")
    if not series_by_key:
        return  # 舊 cache 沒存 series，等下次按按鈕
    from src.compute.macro import compute_signal_precision
    st.markdown("---")
    st.markdown("#### 📐 訊號精確率分析（forward-looking · v18.163）")
    st.caption(
        f"🔍 與上方「召回率」互補 — 遍歷歷史所有 crossings，檢查後 "
        f"**{max_forward_days} 天**內是否真的爆 TWII crisis。"
        "**精確率高 = 訊號響起時相信它的勝率高**；**誤報率高 = 狼來了**。"
    )
    precision_rows = []
    for spec in specs:
        series = series_by_key.get(spec.key)
        if series is None or series.empty:
            precision_rows.append({
                "訊號": spec.label, "歷史 crossings": "—",
                "真實預警 TP": "—", "假警報 FP": "—",
                "精確率": "—", "誤報率": "—", "TP 平均提前天數": "—",
            })
            continue
        stat = compute_signal_precision(series, events, spec, max_forward_days)
        precision_rows.append({
            "訊號": spec.label,
            "歷史 crossings": stat["n_crossings"],
            "真實預警 TP": stat["n_true_positives"],
            "假警報 FP": stat["n_false_positives"],
            "精確率": (f"{stat['precision_pct']:.1f}%"
                       if stat["precision_pct"] is not None else "—"),
            "誤報率": (f"{stat['false_alert_rate_pct']:.1f}%"
                       if stat["false_alert_rate_pct"] is not None else "—"),
            "TP 平均提前天數": (f"{stat['avg_lead_to_crisis_days']:.0f}"
                                  if stat["avg_lead_to_crisis_days"] is not None else "—"),
        })
    st.dataframe(pd.DataFrame(precision_rows),
                  use_container_width=True, hide_index=True)
    st.caption(
        "💡 解讀：召回率高 + 精確率高 = 神準預警；召回率高但精確率低 = 警鈴常響但只少數真的爆；"
        "兩者皆低 = 訊號失效。理想 ≥ 50% 精確率代表「賭一半以上」。"
    )

    # ── 📡 v18.178 Phase E：跨資料源比對矩陣（事件 × 訊號）─────────
    _render_phase4_cross_source_matrix(events, specs, series_by_key,
                                        offset_days, max_lookback_days)

    # ── 🎯 v18.164：MT5-style 自動校準（walk-forward）────────────
    _render_phase3_auto_calibration(events, specs, series_by_key)

    # ── 🔬 v18.165：多因子權重最佳化（高原區 + walk-forward OOS）─────
    _render_phase3_multi_factor_optimization(events, series_by_key)


def _render_phase4_cross_source_matrix(events, specs, series_by_key,
                                         offset_days: int,
                                         max_lookback_days: int) -> None:
    """v18.178 Phase E：跨資料源比對視角矩陣。

    Phase 3 是命中率彙總視角（縱軸訊號、橫軸事件、單元格 0/1，行尾命中率%）；
    本區塊是「資料源視角」交叉表：
    - 橫軸：N 場歷史 TWII crisis 事件（峰日 yyyy-mm-dd）
    - 縱軸：所有訊號（含 PMI 等月頻訊號）
    - 單元格：✅ 提前 Xd / ⚪ 未命中 / — 無資料
    讓 user 一眼看出「在 2020 COVID 那場，哪 5 個資料源同時發警報，哪 2 個失靈」。
    """
    from src.compute.macro import evaluate_signal_at_event

    with st.expander("📡 跨資料源比對視角矩陣（Phase E）", expanded=False):
        st.caption(
            "🔄 **資料源視角**：行 = 各訊號（含月頻 PMI v18.176/178），"
            "列 = 各 TWII crisis 事件（峰日）；單元格顯示「提前 N 天」或「未命中」。"
            "Phase 3 是命中率彙總（看訊號好壞），Phase E 是事件分析（看哪場危機"
            "多少訊號同步預警 → 高交集 = 多源驗證的可信警報）。"
        )
        if not events or not specs:
            st.info("ℹ️ 無事件或無訊號可繪矩陣。")
            return

        peak_labels = [evt.peak_date.strftime('%Y-%m-%d') for evt in events]
        matrix_rows: list[dict] = []
        for spec in specs:
            series = series_by_key.get(spec.key, pd.Series(dtype=float))
            row: dict = {"訊號": spec.label}
            hit_count = 0
            for evt, lbl in zip(events, peak_labels):
                if series.empty:
                    row[lbl] = "—"
                    continue
                lkb = evaluate_signal_at_event(
                    series, spec, evt, offset_days=offset_days,
                    max_lookback_days=max_lookback_days)
                # first_warning_date 有值 → 命中
                if lkb.first_warning_date is not None:
                    lead = (evt.peak_date - lkb.first_warning_date.date()).days
                    row[lbl] = f"✅ {lead}d"
                    hit_count += 1
                else:
                    row[lbl] = "⚪"
            row["命中"] = f"{hit_count}/{len(events)}"
            matrix_rows.append(row)

        # 加事件「多源共識」尾列
        consensus_row: dict = {"訊號": "📊 多源共識"}
        for evt, lbl in zip(events, peak_labels):
            count = sum(1 for r in matrix_rows
                         if isinstance(r[lbl], str) and r[lbl].startswith("✅"))
            consensus_row[lbl] = f"{count}/{len(specs)}"
        consensus_row["命中"] = "—"
        matrix_rows.append(consensus_row)

        st.dataframe(pd.DataFrame(matrix_rows),
                      use_container_width=True, hide_index=True)
        st.caption(
            "💡 解讀：✅ Xd = 訊號於峰前 X 天首次轉折警戒；⚪ = 該事件未命中；"
            "— = 該訊號無資料。最末列「📊 多源共識」= 該事件被多少訊號預警，"
            "≥3 為高可信，<2 屬低可信（單源警報誤判率高）。"
        )


def _render_phase3_auto_calibration(events, specs, series_by_key) -> None:
    """🎯 MT5-style threshold 自動校準 — walk-forward + 3 重 anti-overfit gate."""
    from src.compute.scoring import (
        make_default_grid, optimize_signal_threshold,
    )

    with st.expander(
            "🎯 MT5-style 自動校準（walk-forward + 3 重 anti-overfit gate）",
            expanded=False):
        st.caption(
            "🤖 對選定訊號跑 walk-forward 4 折回測：grid sweep × train/test "
            "OOS 驗證 × 折間票選 × drift > 30% 自動回退預設。**採用建議僅本 "
            "session 生效**，cloud reboot 後回原值。"
        )
        col_pick, col_grid = st.columns([2, 1])
        with col_pick:
            spec_by_label = {s.label: s for s in specs}
            sel_label = st.selectbox(
                "選擇訊號", options=list(spec_by_label.keys()),
                key="phase3_calib_signal",
            )
        with col_grid:
            n_steps = st.slider(
                "grid 步數", min_value=5, max_value=21, value=11, step=2,
                key="phase3_calib_n_steps",
                help="grid 範圍 = 預設 threshold ±50%；步數越多越細。",
            )

        if not st.button("🚀 跑 walk-forward 回測", type="primary",
                          key="phase3_calib_run"):
            _last = st.session_state.get("_phase3_calib_result")
            if not _last:
                st.caption("⬆️ 點按鈕開始（< 5 秒）")
                return
        else:
            sel_spec = spec_by_label[sel_label]
            series = series_by_key.get(sel_spec.key)
            if series is None or series.empty:
                st.warning(f"⚠️ {sel_label} series 為空，無法校準")
                return
            grid = make_default_grid(sel_spec.threshold, n_steps=n_steps)
            with st.spinner(f"跑 walk-forward × {n_steps} grid × "
                             f"{len(events)} events ..."):
                result = optimize_signal_threshold(
                    series, events, sel_spec, grid=grid,
                    n_folds=4, max_forward_days=365,
                )
            st.session_state["_phase3_calib_result"] = {
                "spec_key": sel_spec.key, "spec_label": sel_label,
                "current": result["current"],
                "recommended": result["recommended"],
                "current_metrics": result["current_metrics"],
                "recommended_metrics": result["recommended_metrics"],
                "grid_results": result["grid_results"],
                "walk_forward": result["walk_forward"],
                "status": result["status"],
                "drift_warning": result["drift_warning"],
                "votes": result["votes"],
            }

        last = st.session_state.get("_phase3_calib_result")
        if not last:
            return

        # ── 結果展示 ────────────────────────────────────
        st.markdown(f"##### 📋 {last['spec_label']} 校準結果")
        status = last["status"]
        if status == "insufficient_events":
            st.error("❌ 危機事件數不足 ≥ 4，無法 4 折 walk-forward。"
                      "請先在 Phase 1 偵測更多事件（降回撤門檻或加長歷史）。")
            return
        if status == "fallback_overfit":
            st.warning(
                f"⚠️ **過擬合守門啟動**：過半折 drift > 30% → "
                f"建議**回退預設 {last['current']:g}**（不採用 grid 找到的值）。"
                f"樣本可能不足或週期偏移，需更多歷史資料。"
            )
        else:
            st.success(f"✅ **3 重 gate 全過** → 建議採用 "
                        f"**{last['recommended']:g}**")

        cur_m = last["current_metrics"] or {}
        rec_m = last["recommended_metrics"] or {}
        col_a, col_b = st.columns(2)
        col_a.metric(
            f"現行 threshold {last['current']:g}",
            f"F1 = {cur_m.get('f1', 0):.3f}",
            help=f"P = {cur_m.get('precision', 0):.1%} · "
                 f"R = {cur_m.get('recall', 0):.1%} · "
                 f"crossings = {cur_m.get('n_crossings', 0)}",
        )
        delta_f1 = rec_m.get("f1", 0) - cur_m.get("f1", 0)
        col_b.metric(
            f"建議 threshold {last['recommended']:g}",
            f"F1 = {rec_m.get('f1', 0):.3f}",
            delta=f"{delta_f1:+.3f}",
            help=f"P = {rec_m.get('precision', 0):.1%} · "
                 f"R = {rec_m.get('recall', 0):.1%} · "
                 f"crossings = {rec_m.get('n_crossings', 0)}",
        )

        # walk-forward 折表
        if last["walk_forward"]:
            st.markdown("##### 🔄 Walk-forward 各折 (OOS)")
            wf_df = pd.DataFrame(last["walk_forward"])
            wf_df["drift_pct"] = wf_df["drift_pct"].round(1)
            wf_df["train_f1"] = wf_df["train_f1"].round(3)
            wf_df["test_f1"] = wf_df["test_f1"].round(3)
            wf_df = wf_df.rename(columns={
                "fold": "折",
                "n_train": "train 事件",
                "n_test": "test 事件",
                "train_best": "train 最佳 threshold",
                "train_f1": "Train F1",
                "test_f1": "OOS Test F1",
                "drift_pct": "Drift %",
            })
            st.dataframe(wf_df, use_container_width=True, hide_index=True)

        # 採用按鈕
        if (status == "adopted"
                and abs(last["recommended"] - last["current"]) > 1e-9):
            if st.button(
                    f"✅ 採用建議 threshold {last['recommended']:g}"
                    f"（本 session 生效）",
                    type="primary", key="phase3_calib_adopt"):
                overrides = st.session_state.get("_phase3_overrides", {})
                overrides[last["spec_key"]] = last["recommended"]
                st.session_state["_phase3_overrides"] = overrides
                st.session_state.pop(_PHASE3_CACHE_KEY, None)
                st.success(
                    f"✅ 已採用 {last['spec_label']} → "
                    f"{last['recommended']:g}。"
                    f"請按上方「🚦 跑訊號回看」重新計算（cache 已清）。"
                )
                st.rerun()

        # 顯示已採用 overrides
        ov = st.session_state.get("_phase3_overrides", {})
        if ov:
            ov_df = pd.DataFrame([
                {"訊號": k, "session override threshold": v} for k, v in ov.items()
            ])
            st.markdown("##### 📌 已採用 overrides（本 session）")
            st.dataframe(ov_df, use_container_width=True, hide_index=True)
            if st.button("🔄 清空 overrides（回預設）",
                          key="phase3_calib_clear"):
                st.session_state.pop("_phase3_overrides", None)
                st.session_state.pop(_PHASE3_CACHE_KEY, None)
                st.rerun()


# ──────────────────────────────────────────────────────────────
# 🔬 v18.165：多因子權重最佳化 + 高原區 + Walk-Forward OOS
# 鏡像 fund v18.285 — 不是找單一最高績效，而是找「參數高原區」+ 滾動前向 OOS
# ──────────────────────────────────────────────────────────────
def _render_phase3_multi_factor_optimization(events, series_by_key) -> None:
    """🔬 多因子權重最佳化 — 高原評分 + walk-forward OOS 驗證."""

    from src.compute.scoring import (
        FACTOR_POOL_BY_KEY,
        build_plateau_heatmap_2d,
        build_plateau_surface_3d,
        evaluate_plateau,
        find_plateau_optimum,
        grid_search_performance,
        walk_forward_validate,
    )

    with st.expander(
            "🔬 多因子權重最佳化（高原區 + walk-forward OOS）",
            expanded=False):
        st.caption(
            "🤖 多因子加權綜合分數 S_t = Σ w_i × normalize(I_{i,t−1}) → 拐點偵測 → "
            "找**高原區**（不取單一最高 F1，而是鄰域 mean − λ × std 最大）→ "
            "walk-forward 滾動 train/test 串 OOS 權益曲線確認 robust。"
        )

        available_keys = [k for k in FACTOR_POOL_BY_KEY if k in series_by_key]
        if len(available_keys) < 2:
            st.warning(
                f"⚠️ 可用因子不足 2 個（目前 {len(available_keys)} 個）。"
                "請先在 Phase 1/2 抓更多訊號或加台股本地序列至 FACTOR_POOL。"
            )
            return

        col_pick, col_metric = st.columns([2, 1])
        with col_pick:
            sel_keys = st.multiselect(
                "選擇因子（建議 2–4 個避免 simplex 爆炸）",
                options=available_keys,
                default=available_keys[:min(3, len(available_keys))],
                key="multifactor_keys",
            )
        with col_metric:
            metric = st.radio(
                "Plateau 目標", options=["f1", "sharpe"],
                index=0, key="multifactor_metric",
                horizontal=True,
            )

        col_step, col_radius, col_lambda = st.columns(3)
        with col_step:
            step = st.slider(
                "Grid 步長", min_value=0.1, max_value=0.5, value=0.2, step=0.05,
                key="multifactor_step",
                help="權重 simplex 解析度；步長越小組合越多。",
            )
        with col_radius:
            radius = st.slider(
                "鄰域半徑", min_value=1, max_value=3, value=1, step=1,
                key="multifactor_radius",
                help="高原評分鄰域格數（chebyshev 距離）。",
            )
        with col_lambda:
            lambda_std = st.slider(
                "λ（std 懲罰係數）", min_value=0.0, max_value=2.0, value=0.5,
                step=0.1, key="multifactor_lambda",
                help="plateau_score = mean − λ × std；λ 越大越偏好平坦區。",
            )

        col_tr, col_te, col_th = st.columns(3)
        with col_tr:
            train_months = st.slider(
                "Train window（月）", min_value=12, max_value=72, value=36,
                step=6, key="multifactor_train_months",
            )
        with col_te:
            test_months = st.slider(
                "Test window（月）", min_value=3, max_value=24, value=12,
                step=3, key="multifactor_test_months",
            )
        with col_th:
            threshold = st.slider(
                "綜合分數警戒線", min_value=0.0, max_value=3.0, value=1.0,
                step=0.1, key="multifactor_threshold",
                help="S_t ≥ 此值即視為警戒；轉折日 = 由 <threshold 跨到 ≥threshold。",
            )

        if len(sel_keys) < 2:
            st.info("👆 請至少選 2 個因子才能跑最佳化。")
            return

        if st.button("🚀 跑多因子高原 + walk-forward",
                      type="primary", key="multifactor_run"):
            try:
                returns = _load_twii_returns()
            except FileNotFoundError:
                returns = pd.Series(dtype=float)
            sel_series = {k: series_by_key[k] for k in sel_keys}
            with st.spinner("跑 grid search + plateau + walk-forward 中..."):
                grid_result = grid_search_performance(
                    sel_series, returns, events, sel_keys,
                    threshold=threshold, step=step,
                )
                plateau_scores = evaluate_plateau(
                    grid_result, sel_keys, step, radius, lambda_std, metric,
                )
                opt = find_plateau_optimum(grid_result, plateau_scores)
                wf = walk_forward_validate(
                    sel_series, returns, events, sel_keys,
                    train_months=train_months, test_months=test_months,
                    threshold=threshold, step=step, radius=radius,
                    lambda_std=lambda_std, metric=metric,
                )
            st.session_state["_multifactor_result"] = {
                "sel_keys": sel_keys,
                "grid": grid_result,
                "plateau": plateau_scores,
                "opt": opt,
                "wf": wf,
                "metric": metric,
                "step": step,
            }
            st.success(
                f"✅ 完成 {len(grid_result['combos'])} 個權重組合 + "
                f"{wf['n_folds']} 折 walk-forward"
            )

        cached = st.session_state.get("_multifactor_result")
        if not cached:
            return
        sel_keys = cached["sel_keys"]
        opt = cached["opt"]
        wf = cached["wf"]
        plateau_scores = cached["plateau"]
        grid_result = cached["grid"]

        st.markdown("### 🏆 高原最佳權重（train 全期間）")
        opt_cols = st.columns(min(len(sel_keys), 4))
        for i, (k, w) in enumerate(opt["weights"].items()):
            with opt_cols[i % len(opt_cols)]:
                st.metric(k, f"{w:.2f}")
        c_f, c_s, c_p = st.columns(3)
        c_f.metric("Train F1", f"{opt['f1']:.3f}")
        c_s.metric("Train Sharpe", f"{opt['sharpe']:.3f}")
        c_p.metric("Plateau Score", f"{opt['plateau_score']:.3f}")

        st.markdown("### 📊 高原視覺化")
        if len(sel_keys) >= 2:
            col_x, col_y, col_viz = st.columns([1, 1, 1])
            with col_x:
                x_key = st.selectbox("X 軸因子", options=sel_keys,
                                     index=0, key="multifactor_x")
            with col_y:
                remaining = [k for k in sel_keys if k != x_key]
                y_key = st.selectbox("Y 軸因子", options=remaining,
                                     index=0, key="multifactor_y")
            with col_viz:
                viz_kind = st.radio(
                    "圖形類型", options=["2D heatmap", "3D surface"],
                    index=0, horizontal=True, key="multifactor_viz_kind",
                )
            metric_label = f"{cached['metric'].upper()} plateau"
            if viz_kind == "2D heatmap":
                fig = build_plateau_heatmap_2d(
                    grid_result, plateau_scores, sel_keys, (x_key, y_key),
                    metric_label,
                )
            else:
                fig = build_plateau_surface_3d(
                    grid_result, plateau_scores, sel_keys, (x_key, y_key),
                    metric_label,
                )
            st.plotly_chart(fig, use_container_width=True)

        if wf["folds"]:
            st.markdown("### 🚶 Walk-forward 各折（OOS 樣本外）")
            fold_rows = []
            for f in wf["folds"]:
                fold_rows.append({
                    "折": f["fold"],
                    "Train": f"{f['train_range'][0]} → {f['train_range'][1]}",
                    "Test": f"{f['test_range'][0]} → {f['test_range'][1]}",
                    "權重": ", ".join(f"{k}={v:.2f}" for k, v in f["weights"].items()),
                    "Train F1": f"{f['train_f1']:.3f}",
                    "Test F1": f"{f['test_f1']:.3f}",
                    "Train Sharpe": f"{f['train_sharpe']:.3f}",
                    "Test Sharpe": f"{f['test_sharpe']:.3f}",
                })
            st.dataframe(pd.DataFrame(fold_rows), use_container_width=True,
                         hide_index=True)
            c1, c2 = st.columns(2)
            c1.metric("OOS F1（全段）", f"{wf['oos_f1']:.3f}")
            c2.metric("OOS Sharpe（全段）", f"{wf['oos_sharpe']:.3f}")
        else:
            st.info(f"⚠️ Walk-forward 無有效折（status={wf.get('status')}）— "
                    "請調小 train/test 視窗或加長序列。")


def _load_twii_returns() -> pd.Series:
    """讀 TWII parquet 回傳 close 序列（給 Sharpe 計算用）."""
    p = Path(__file__).resolve().parent / "data_cache" / "twii_ohlcv.parquet"
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_parquet(p)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["close"]
