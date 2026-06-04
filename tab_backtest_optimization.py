"""tab_backtest_optimization.py — 🧪 回測找參數 Tab (v18.167).

完整版多因子權重最佳化 + 高原區 + Walk-Forward 驗證 UI（top-level tab）。
與 macro validation tab 內的快速版 expander 並存：此 tab 給「沉浸式調參」場景。

引擎來源：multi_factor_optimization.py（v18.165 已合 main）
資料來源：data_cache/ 既有 4 表 + TWII OHLCV + macro_validation_tw crisis events
"""
from __future__ import annotations


import pandas as pd
import streamlit as st


def render_backtest_optimization_tab() -> None:
    """🧪 回測找參數 — 多因子權重最佳化 + 高原區 + walk-forward OOS."""
    st.markdown("# 🧪 回測找參數")
    st.caption(
        "**目標**：不是找歷史回測「單一最高 F1」，而是找**參數高原區** — "
        "鄰域 mean − λ × std 最大的權重組合 → walk-forward 滾動 OOS 驗證穩定性。"
    )

    from multi_factor_optimization import (
        FACTOR_POOL_BY_KEY,
        build_plateau_heatmap_2d,
        build_plateau_surface_3d,
        evaluate_plateau,
        find_plateau_optimum,
        grid_search_performance,
        walk_forward_validate,
    )

    with st.expander("📖 操作說明（第一次用先讀）", expanded=False):
        st.markdown(
            """
**核心數學**
```
拐點偵測：
  S_t = Σᵢ wᵢ × normalize(I_{i,t-1})      ← lag=1 防未來引用
  warn_t = (S_t ≥ threshold)
  crossing_t = warn_t & ¬warn_{t-1}        ← 從非警戒「跨到」警戒

高原評分（不取單一最高）：
  N(w) = 鄰域 chebyshev 距離 ≤ radius × step 的點
  plateau(w) = mean(perf(N)) − λ × std(perf(N))
  w* = argmax plateau

Walk-Forward OOS：
  for t in [start, end-train-test, step=test]:
    w*_t = argmax plateau on train_window
    record OOS perf on test_window with w*_t
  OOS_curve = concat all test crossings
```

**6 顆 slider 怎麼調**
1. **Grid 步長**（0.1～0.5）：權重 simplex 解析度；步長越小組合越多但越慢
2. **鄰域半徑**（1～3）：算 plateau 用幾格鄰居；越大越平滑
3. **λ（std 懲罰）**（0～2）：plateau = mean − λ·std，λ 越大越偏好平坦區
4. **Train window**（12～72 月）：每折訓練多久找 plateau
5. **Test window**（3～24 月）：每折 OOS 驗證多久
6. **綜合分數警戒線**（0～3）：S_t ≥ 此值算警戒；對應 z-score 1σ
"""
        )

    # ── 1️⃣ 資料抓取（用 macro validation 的同套 cache + crisis 偵測）─
    st.markdown("### 1️⃣ 危機事件 + 訊號序列")
    col_thresh, col_run = st.columns([3, 1])
    with col_thresh:
        threshold_pct = st.slider(
            "TWII 回撤門檻 ≥",
            min_value=10, max_value=40, value=20, step=5,
            key="backtest_thresh",
            help="峰前→谷底跌幅達此 % 算危機事件，越小事件越多 walk-forward 越穩。",
        )
    with col_run:
        st.write("")
        if st.button("📊 抓資料 + 偵測事件", type="secondary",
                     key="backtest_fetch", use_container_width=True):
            _fetch_data_to_state(threshold_pct)

    cached = st.session_state.get("_backtest_data_cache")
    if not cached:
        st.info("👆 先按「📊 抓資料 + 偵測事件」開始。")
        return

    events = cached["events"]
    series_by_key = cached["series_by_key"]
    twii = cached["twii"]
    st.success(
        f"✅ TWII {twii.index.min():%Y-%m-%d}~{twii.index.max():%Y-%m-%d} "
        f"｜偵測到 {len(events)} 個 ≥{cached['threshold_pct']}% 回撤事件 "
        f"｜{len(series_by_key)} 個訊號序列就緒"
    )

    # ── 2️⃣ 因子 + 參數 ─────────────────────────────────
    st.markdown("### 2️⃣ 因子選擇 + 參數")
    available_keys = [k for k in series_by_key
                       if k in FACTOR_POOL_BY_KEY and not series_by_key[k].empty]
    if len(available_keys) < 2:
        st.error(
            f"⚠️ 可用因子不足 2 個（目前 {len(available_keys)}）。"
            "請確認 `data_cache/` 內 4 個 parquet 都已 cron 更新。"
        )
        return

    col_factors, col_metric = st.columns([2, 1])
    with col_factors:
        sel_keys = st.multiselect(
            "因子（建議 2–4 個避免 simplex 爆炸）",
            options=available_keys,
            default=available_keys[:min(3, len(available_keys))],
            format_func=lambda k: FACTOR_POOL_BY_KEY[k].label,
            key="backtest_factors",
        )
    with col_metric:
        metric = st.radio(
            "Plateau 目標",
            options=["f1", "sharpe"],
            index=0, key="backtest_metric",
            horizontal=True,
            help="F1 = 拐點預警準度；Sharpe = 持倉年化風險調整報酬。",
        )

    col_step, col_radius, col_lambda = st.columns(3)
    with col_step:
        step = st.slider(
            "Grid 步長", 0.1, 0.5, 0.2, 0.05,
            key="backtest_step",
        )
    with col_radius:
        radius = st.slider(
            "鄰域半徑", 1, 3, 1, 1,
            key="backtest_radius",
        )
    with col_lambda:
        lambda_std = st.slider(
            "λ（std 懲罰）", 0.0, 2.0, 0.5, 0.1,
            key="backtest_lambda",
        )

    col_tr, col_te, col_th = st.columns(3)
    with col_tr:
        train_months = st.slider(
            "Train window（月）", 12, 72, 36, 6,
            key="backtest_train",
        )
    with col_te:
        test_months = st.slider(
            "Test window（月）", 3, 24, 12, 3,
            key="backtest_test",
        )
    with col_th:
        threshold = st.slider(
            "綜合分數警戒線", 0.0, 3.0, 1.0, 0.1,
            key="backtest_score_thresh",
        )

    if len(sel_keys) < 2:
        st.info("👆 請至少選 2 個因子。")
        return

    if st.button("🚀 跑 grid + plateau + walk-forward",
                  type="primary", key="backtest_run",
                  use_container_width=True):
        twii_returns = twii
        sel_series = {k: series_by_key[k] for k in sel_keys}
        with st.spinner("跑 grid search → plateau → walk-forward 中..."):
            grid_result = grid_search_performance(
                sel_series, twii_returns, events, sel_keys,
                threshold=threshold, step=step,
            )
            plateau_scores = evaluate_plateau(
                grid_result, sel_keys, step, radius, lambda_std, metric,
            )
            opt = find_plateau_optimum(grid_result, plateau_scores)
            wf = walk_forward_validate(
                sel_series, twii_returns, events, sel_keys,
                train_months=train_months, test_months=test_months,
                threshold=threshold, step=step, radius=radius,
                lambda_std=lambda_std, metric=metric,
            )
        st.session_state["_backtest_run_result"] = {
            "sel_keys": sel_keys,
            "grid": grid_result,
            "plateau": plateau_scores,
            "opt": opt,
            "wf": wf,
            "metric": metric,
        }
        st.success(
            f"✅ 完成 {len(grid_result['combos'])} 個權重組合 "
            f"+ {wf['n_folds']} 折 walk-forward OOS 驗證"
        )

    run = st.session_state.get("_backtest_run_result")
    if not run:
        return

    sel_keys = run["sel_keys"]
    opt = run["opt"]
    wf = run["wf"]

    # ── 3️⃣ 高原最佳權重 ─────────────────────────────────
    st.markdown("### 3️⃣ 🏆 高原最佳權重（train 全期間）")
    opt_cols = st.columns(min(len(sel_keys), 4))
    for i, k in enumerate(sel_keys):
        with opt_cols[i % len(opt_cols)]:
            st.metric(
                FACTOR_POOL_BY_KEY[k].label,
                f"{opt['weights'].get(k, 0.0):.2f}",
            )
    m_f, m_s, m_p = st.columns(3)
    m_f.metric("Train F1", f"{opt['f1']:.3f}")
    m_s.metric("Train Sharpe", f"{opt['sharpe']:.3f}")
    m_p.metric("Plateau Score", f"{opt['plateau_score']:.3f}")

    # 最佳權重 CSV 匯出
    best_w_df = pd.DataFrame([
        {"factor_key": k, "label": FACTOR_POOL_BY_KEY[k].label,
         "weight": opt["weights"].get(k, 0.0)}
        for k in sel_keys
    ])
    st.download_button(
        "📥 最佳權重 CSV",
        data=best_w_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"best_weights_{pd.Timestamp.today():%Y%m%d}.csv",
        mime="text/csv",
        key="backtest_export_weights",
    )

    # ── 4️⃣ 高原視覺化 ─────────────────────────────────
    st.markdown("### 4️⃣ 📊 參數高原視覺化")
    col_x, col_y, col_viz = st.columns([1, 1, 1])
    with col_x:
        x_key = st.selectbox(
            "X 軸因子", sel_keys, index=0,
            format_func=lambda k: FACTOR_POOL_BY_KEY[k].label,
            key="backtest_x",
        )
    with col_y:
        remaining = [k for k in sel_keys if k != x_key]
        y_key = st.selectbox(
            "Y 軸因子", remaining, index=0,
            format_func=lambda k: FACTOR_POOL_BY_KEY[k].label,
            key="backtest_y",
        )
    with col_viz:
        viz_kind = st.radio(
            "圖形",
            options=["2D heatmap", "3D surface"],
            index=0, horizontal=True, key="backtest_viz_kind",
        )
    metric_label = f"{run['metric'].upper()} plateau"
    if viz_kind == "2D heatmap":
        fig = build_plateau_heatmap_2d(
            run["grid"], run["plateau"], sel_keys, (x_key, y_key), metric_label,
        )
    else:
        fig = build_plateau_surface_3d(
            run["grid"], run["plateau"], sel_keys, (x_key, y_key), metric_label,
        )
    st.plotly_chart(fig, use_container_width=True)

    # ── 5️⃣ Walk-forward 各折 ─────────────────────────
    st.markdown("### 5️⃣ 🚶 Walk-Forward 各折（OOS 樣本外）")
    if not wf["folds"]:
        st.warning(
            f"⚠️ 無有效折（status={wf.get('status')}）— "
            "請調小 train/test 視窗或調低事件門檻讓資料更密。"
        )
        return
    fold_rows = []
    for f in wf["folds"]:
        fold_rows.append({
            "折": f["fold"],
            "Train 期間": f"{f['train_range'][0]} → {f['train_range'][1]}",
            "Test 期間": f"{f['test_range'][0]} → {f['test_range'][1]}",
            "權重": ", ".join(
                f"{FACTOR_POOL_BY_KEY[k].label}={v:.2f}"
                for k, v in f["weights"].items()
            ),
            "Train F1": f"{f['train_f1']:.3f}",
            "Test F1": f"{f['test_f1']:.3f}",
            "Train Sharpe": f"{f['train_sharpe']:.3f}",
            "Test Sharpe": f"{f['test_sharpe']:.3f}",
            "Test 事件數": f["n_test_events"],
        })
    df_folds = pd.DataFrame(fold_rows)
    st.dataframe(df_folds, use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("OOS F1（全段）", f"{wf['oos_f1']:.3f}")
    c2.metric("OOS Sharpe（全段）", f"{wf['oos_sharpe']:.3f}")
    c3.metric("OOS Crossings 總數", int(wf["oos_crossings"].sum())
              if not wf["oos_crossings"].empty else 0)

    st.download_button(
        "📥 各折結果 CSV",
        data=df_folds.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"walk_forward_folds_{pd.Timestamp.today():%Y%m%d}.csv",
        mime="text/csv",
        key="backtest_export_folds",
    )


def _fetch_data_to_state(threshold_pct: int) -> None:
    """讀 TWII parquet + 偵測 crisis + 抓 4 訊號 series → 存 session_state."""
    from macro_signal_lookback_tw import fetch_all_tw_signal_series
    from macro_validation_tw import (
        DEFAULT_PARQUET_CACHE_DIR,
        detect_twii_crisis_events,
        load_twii_close_from_parquet,
    )
    cache_dir = DEFAULT_PARQUET_CACHE_DIR
    with st.spinner("讀 Parquet → 偵測 crisis → 抓 4 訊號 series ..."):
        twii = load_twii_close_from_parquet(cache_dir)
        if twii.empty:
            st.error("❌ twii_ohlcv.parquet 讀回空 — 等下次 cron 或 bootstrap")
            return
        events = detect_twii_crisis_events(
            twii, drop_threshold=threshold_pct / 100.0,
        )
        series_by_key = fetch_all_tw_signal_series(cache_dir=cache_dir)
    st.session_state["_backtest_data_cache"] = {
        "threshold_pct": threshold_pct,
        "twii": twii,
        "events": events,
        "series_by_key": series_by_key,
    }
