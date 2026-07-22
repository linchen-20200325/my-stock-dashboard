"""src/compute/screener/forward_test.py — 前進式驗證對帳(Forward-test, L2 純函式).

前進式驗證:凍結每期選股(pick snapshot)→ 一段時間後拿現價對帳,累積真實績效
vs 被動基準(0050)。**零 lookahead、零存活者偏誤**(都是當下真實決定 + 事後真實現價)。
取代已移除的舊回測引擎(v18.265) — 舊回測有未來函數 + 只含現存公司的偏誤問題。

對帳邏輯(§7 對齊):
  每檔前進報酬  fwd_i     = 現價_i / 進場價_i − 1
  cohort 等權報酬 avg     = mean(fwd_i)                     (等權,不加權)
  基準報酬        bench    = 0050 同期報酬(caller 給,各 cohort 窗不同)
  超額報酬        excess   = avg − bench
  勝率            hit      = 「fwd_i > 0」的比例
  贏基準率        beat     = 「fwd_i > bench」的比例

§1 fail-loud / §3.3:
  - 凍結後抓不到現價(下市/停牌)的檔 → **剔除並計數**(不灌 0、不假設 0 報酬)。
  - 進場價 ≤ 0 / NaN → 該筆無效剔除。
  - cohort 有效檔 < FORWARD_TEST_MIN_COHORT_PICKS → 標記略過(§1 樣本太小不硬算)。
  - 基準缺(0050 該窗抓不到)→ excess/beat = NaN(只報絕對報酬,不猜)。
§8.2:L2 純函式,零 I/O、零 streamlit。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.forward_test_thresholds import FORWARD_TEST_MIN_COHORT_PICKS

# picks 必備欄(每列一「凍結持股」)。cohort = 凍結批次標籤(通常為凍結日字串)。
REQUIRED_COLS = ("cohort", "stock_id", "entry_price")

_OUT_COLS = [
    "cohort", "n_picks", "n_valid", "n_dropped",
    "avg_return_pct", "hit_rate_pct", "benchmark_return_pct",
    "excess_pct", "beat_bench_rate_pct", "enough_sample",
]


def reconcile_forward_test(
    picks: pd.DataFrame,
    current_prices: dict,
    *,
    benchmark_returns: dict | None = None,
    min_cohort_picks: int = FORWARD_TEST_MIN_COHORT_PICKS,
) -> tuple[pd.DataFrame, dict]:
    """對帳每個 cohort 的前進績效。

    Args:
        picks: 凍結持股 long-form,須含 REQUIRED_COLS(cohort/stock_id/entry_price)。
        current_prices: {stock_id: 現價}。缺 key 的檔 → 剔除(不灌 0)。
        benchmark_returns: {cohort: 0050 該窗報酬(小數,如 0.05)};None/缺 → excess=NaN。
        min_cohort_picks: 有效檔數低於此 → enough_sample=False(仍算但標樣本不足)。

    Returns:
        (per_cohort_df, overall)。
          per_cohort_df 欄見 _OUT_COLS(依 cohort 排序);報酬皆 %。
          overall: {n_cohorts, n_picks_total, n_valid_total, avg_excess_pct(有基準的加權),
                    overall_hit_rate_pct, note}。
        空 picks / 缺欄 → 空表 + note。
    """
    _empty = pd.DataFrame(columns=_OUT_COLS)
    if picks is None or picks.empty:
        return _empty, {"n_cohorts": 0, "n_picks_total": 0, "note": "尚無凍結選股紀錄。"}
    _missing = [c for c in REQUIRED_COLS if c not in picks.columns]
    if _missing:
        raise ValueError(f"forward_test 缺必備欄:{_missing}")

    df = picks.copy()
    df["stock_id"] = df["stock_id"].astype(str).str.strip()
    df["cohort"] = df["cohort"].astype(str)
    df["entry_price"] = pd.to_numeric(df["entry_price"], errors="coerce")
    _prices = {str(k).strip(): v for k, v in (current_prices or {}).items()}
    _bench = {str(k): v for k, v in (benchmark_returns or {}).items()}

    rows = []
    for cohort, g in df.groupby("cohort", sort=True):
        _n = int(len(g))
        _fwd = []
        for _sid, _ep in zip(g["stock_id"], g["entry_price"]):
            _cur = _prices.get(_sid)
            if _ep is None or not (_ep > 0) or _ep != _ep:   # 進場價無效
                continue
            if _cur is None or not (float(_cur) > 0):          # 現價缺/無效 → 剔除(§1)
                continue
            _fwd.append(float(_cur) / float(_ep) - 1.0)
        _n_valid = len(_fwd)
        _n_drop = _n - _n_valid
        _b = _bench.get(cohort)
        _has_b = _b is not None and _b == _b
        if _n_valid == 0:
            rows.append({
                "cohort": cohort, "n_picks": _n, "n_valid": 0, "n_dropped": _n_drop,
                "avg_return_pct": np.nan, "hit_rate_pct": np.nan,
                "benchmark_return_pct": round(_b * 100, 2) if _has_b else np.nan,
                "excess_pct": np.nan, "beat_bench_rate_pct": np.nan,
                "enough_sample": False,
            })
            continue
        _arr = np.array(_fwd, dtype=float)
        _avg = float(_arr.mean())
        _hit = float((_arr > 0).mean()) * 100
        _beat = float((_arr > _b).mean()) * 100 if _has_b else np.nan
        _excess = (_avg - _b) if _has_b else np.nan
        rows.append({
            "cohort": cohort, "n_picks": _n, "n_valid": _n_valid, "n_dropped": _n_drop,
            "avg_return_pct": round(_avg * 100, 2),
            "hit_rate_pct": round(_hit, 1),
            "benchmark_return_pct": round(_b * 100, 2) if _has_b else np.nan,
            "excess_pct": round(_excess * 100, 2) if _has_b else np.nan,
            "beat_bench_rate_pct": round(_beat, 1) if _has_b else np.nan,
            "enough_sample": _n_valid >= int(min_cohort_picks),
        })

    out = pd.DataFrame(rows, columns=_OUT_COLS).sort_values("cohort").reset_index(drop=True)

    # overall:只用「樣本足夠 + 有基準」的 cohort 算平均超額(誠實,不被小樣本汙染)
    _solid = out[out["enough_sample"] & out["excess_pct"].notna()]
    _valid_all = out[out["enough_sample"]]
    overall = {
        "n_cohorts": int(len(out)),
        "n_cohorts_solid": int(len(_solid)),
        "n_picks_total": int(out["n_picks"].sum()),
        "n_valid_total": int(out["n_valid"].sum()),
        "avg_excess_pct": round(float(_solid["excess_pct"].mean()), 2) if not _solid.empty else np.nan,
        "avg_return_pct": round(float(_valid_all["avg_return_pct"].mean()), 2) if not _valid_all.empty else np.nan,
        "overall_hit_rate_pct": round(float(_valid_all["hit_rate_pct"].mean()), 1) if not _valid_all.empty else np.nan,
        "note": ("樣本足夠的 cohort 尚不足,績效僅供參考(前進式驗證需時間累積)。"
                 if _solid.empty else ""),
    }
    return out, overall
