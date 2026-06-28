"""src/compute/scoring/signal_threshold_optimization.py — MT5-style Phase 3 訊號自動校準 (v18.164).

核心：walk-forward 4 折 grid sweep 找最佳 threshold + 3 重 anti-overfit gate
（折間票選 / drift > 30% 回退預設 / cap 守門）→ 輸出建議值供 UI session-only
採用，不自動覆寫 production threshold。

對齊 my-Fund-dashboard v18.283 同步上線。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Optional

import pandas as pd

from src.compute.macro import (
    TwSignalSpec,
    compute_signal_precision,
    evaluate_signal_at_event,
)
from src.compute.macro import TwiiCrisisEvent

# 折 drift > 此 % 視為 overfitting；超過半數折 drift 過此 → 回退預設
DRIFT_THRESHOLD_PCT = 30.0


def make_default_grid(default_threshold: float, n_steps: int = 11) -> tuple[float, ...]:
    """以預設值為中心做 ±50% 線性 grid。

    default=0 特例：用 [-1, 1] 線性 grid（如 T10Y2Y 倒掛場景）。
    """
    if abs(default_threshold) < 1e-9:
        return tuple(round(-1 + 2 * i / (n_steps - 1), 4) for i in range(n_steps))
    span = abs(default_threshold) * 0.5
    return tuple(round(default_threshold - span + (2 * span * i / (n_steps - 1)), 4)
                 for i in range(n_steps))


def _eval_threshold_f1(
    signal_series: pd.Series,
    events: list[TwiiCrisisEvent],
    base_spec: TwSignalSpec,
    threshold: float,
    max_forward_days: int,
    lookback_days: int = 90,
) -> dict:
    """單一 threshold 的 precision / recall / F1（forward + backward 合成）."""
    if not events or signal_series is None or signal_series.empty:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "n_crossings": 0}
    new_spec = replace(base_spec, threshold=threshold)

    # Forward-looking precision
    prec_stat = compute_signal_precision(signal_series, events, new_spec, max_forward_days)
    p = (prec_stat["precision_pct"] or 0) / 100
    n_cross = prec_stat["n_crossings"]

    # Backward-looking recall：known events 有 lookback edge 命中的比例
    n_hit = 0
    for ev in events:
        lb = evaluate_signal_at_event(
            ev, signal_series, new_spec,
            lookback_days=lookback_days,
            max_lookback_days=max_forward_days,
            mode="edge",
        )
        if lb.lead_time_days is not None:
            n_hit += 1
    r = n_hit / len(events)

    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1, "n_crossings": n_cross}


def optimize_signal_threshold(
    signal_series: pd.Series,
    events: list[TwiiCrisisEvent],
    base_spec: TwSignalSpec,
    grid: Optional[tuple[float, ...]] = None,
    n_folds: int = 4,
    max_forward_days: int = 365,
    drift_threshold_pct: float = DRIFT_THRESHOLD_PCT,
) -> dict:
    """Walk-forward 自動校準訊號 threshold（MT5 strategy tester 對等）.

    Args:
        signal_series: 訊號歷史 series（index 為日期）
        events: 已知 crisis events（必要按 peak_date 升序）
        base_spec: 現行 TwSignalSpec（含預設 threshold）
        grid: candidate thresholds；None 則自動生成 ±50% × 11 steps
        n_folds: 折數（預設 4 → 3 個 train/test split）
        max_forward_days: precision 追蹤期
        drift_threshold_pct: 折 drift > 此 % 算 overfit

    Returns:
        dict:
            recommended       : 建議 threshold（drift 過大則回退預設）
            current           : 現行 threshold
            current_metrics   : 現行門檻於全資料的 {precision, recall, f1, n_crossings}
            recommended_metrics : 建議門檻同上
            grid_results      : list[{threshold, precision, recall, f1, n_crossings}]
            walk_forward      : list[{fold, n_train, n_test, train_best, train_f1,
                                       test_f1, drift_pct}]
            votes             : dict {threshold: vote_count}
            drift_warning     : bool 過半折 drift 過閾值
            status            : 'adopted' / 'fallback_overfit' / 'insufficient_events'
    """
    base = {
        "recommended": base_spec.threshold,
        "current": base_spec.threshold,
        "current_metrics": None,
        "recommended_metrics": None,
        "grid_results": [],
        "walk_forward": [],
        "votes": {},
        "drift_warning": False,
        "status": "insufficient_events",
    }
    if signal_series is None or signal_series.empty:
        return base
    if not events or len(events) < n_folds:
        return base
    if grid is None:
        grid = make_default_grid(base_spec.threshold)

    sorted_events = sorted(events, key=lambda e: e.peak_date)

    # 1) 全資料 grid sweep（給 UI 對照表用，非 OOS）
    grid_results = [
        {"threshold": thr,
         **_eval_threshold_f1(signal_series, sorted_events, base_spec,
                               thr, max_forward_days)}
        for thr in grid
    ]

    # 2) Walk-forward expanding window：fold i train [0:i*fs] / test [i*fs:(i+1)*fs]
    fold_size = max(1, len(sorted_events) // n_folds)
    walk_forward = []
    train_bests: list[float] = []
    drifts: list[float] = []
    for fold_i in range(1, n_folds):
        train_end = fold_i * fold_size
        test_end = min((fold_i + 1) * fold_size, len(sorted_events))
        train_events = sorted_events[:train_end]
        test_events = sorted_events[train_end:test_end]
        if not train_events or not test_events:
            continue
        # train 找最佳 threshold
        train_scores = [
            (thr, _eval_threshold_f1(signal_series, train_events, base_spec,
                                      thr, max_forward_days)["f1"])
            for thr in grid
        ]
        best_thr, best_train_f1 = max(train_scores, key=lambda x: x[1])
        # OOS 評分
        test_m = _eval_threshold_f1(signal_series, test_events, base_spec,
                                      best_thr, max_forward_days)
        drift = ((best_train_f1 - test_m["f1"]) / max(best_train_f1, 1e-6)) * 100
        walk_forward.append({
            "fold": fold_i,
            "n_train": len(train_events),
            "n_test": len(test_events),
            "train_best": best_thr,
            "train_f1": best_train_f1,
            "test_f1": test_m["f1"],
            "drift_pct": drift,
        })
        train_bests.append(best_thr)
        drifts.append(drift)

    if not train_bests:
        return base

    # 3) 票選 + drift 守門
    votes_counter = Counter(train_bests)
    recommended, _ = votes_counter.most_common(1)[0]
    n_drift_high = sum(1 for d in drifts if d > drift_threshold_pct)
    drift_warning = n_drift_high * 2 > len(drifts)  # strict majority

    if drift_warning:
        recommended = base_spec.threshold  # fallback
        status = "fallback_overfit"
    else:
        status = "adopted"

    current_m = _eval_threshold_f1(signal_series, sorted_events, base_spec,
                                     base_spec.threshold, max_forward_days)
    rec_m = _eval_threshold_f1(signal_series, sorted_events, base_spec,
                                 recommended, max_forward_days)

    return {
        "recommended": recommended,
        "current": base_spec.threshold,
        "current_metrics": current_m,
        "recommended_metrics": rec_m,
        "grid_results": grid_results,
        "walk_forward": walk_forward,
        "votes": dict(votes_counter),
        "drift_warning": drift_warning,
        "status": status,
    }
