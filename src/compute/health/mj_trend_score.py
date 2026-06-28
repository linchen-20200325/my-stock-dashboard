"""src/compute/health/mj_trend_score.py — v18.189 月+季雙頻率融合進退分數（純函式 zero-IO）

整合兩個頻率：
- **月營收動能（月頻、權重 65%）**：近 3 月 YoY 平均 + 末月 MoM
- **MJ 季財報 trend（季頻、權重 35%）**：近 3 季快照逐期 diff 兩次 net_delta

設計理念：月營收 10 日公布更新快（先行指標）；MJ 季財報慢但見獲利品質（落後指標）。
月權重大搶時效、季權重小保品質 — 互補不對立。

公式：
  final = 0.65 × monthly_subscore + 0.35 × mj_subscore

合分 5 段判定：
  ≥+1.5 🚀 強進步 / +0.5~+1.5 📈 進步 / -0.5~+0.5 ➖ 中性
  / -1.5~-0.5 📉 退步 / ≤-1.5 🔻 強退步
"""
from __future__ import annotations

import math
from typing import Any

from src.compute.health.mj_health_diff import diff_mj_health  # v18.362 F-8:直打 submod 避 sibling self circular

# label 由高到低排序，命中第一個 threshold 即回
_LABEL_THRESHOLDS = [
    (1.5, "🚀 強進步", "strong_up"),
    (0.5, "📈 進步", "up"),
    (-0.5, "➖ 中性", "neutral"),
    (-1.5, "📉 退步", "down"),
]
_LOW_LABEL = ("🔻 強退步", "strong_down")


def _safe_num(x: Any) -> float | None:
    """容錯轉 float，None / NaN / inf / 非數字 → None。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _yoy_step_score(yoy_pct: float) -> float:
    """單月 YoY 分數階梯：≥+10% → +2 / >0 → +1 / <0 → -1 / ≤-10% → -2 / =0 → 0。"""
    if yoy_pct >= 10.0:
        return 2.0
    if yoy_pct > 0:
        return 1.0
    if yoy_pct <= -10.0:
        return -2.0
    if yoy_pct < 0:
        return -1.0
    return 0.0


def compute_monthly_revenue_subscore(monthly_3m: list[dict]) -> tuple[float, dict]:
    """月營收動能子分數，範圍 [-2.5, +2.5]。

    Args:
        monthly_3m: 近 3 月月營收 [{revenue, yoy_pct, mom_pct, date}, ...] 最新月在最後

    Returns:
        (subscore, detail_dict)
    """
    if not isinstance(monthly_3m, list) or not monthly_3m:
        return 0.0, {"reason": "no_data", "n_months": 0}

    yoy_vals: list[float] = []
    for m in monthly_3m:
        if not isinstance(m, dict):
            continue
        v = _safe_num(m.get("yoy_pct"))
        if v is not None:
            yoy_vals.append(v)
    if not yoy_vals:
        return 0.0, {"reason": "no_yoy", "n_months": 0}

    yoy_avg = sum(yoy_vals) / len(yoy_vals)
    yoy_score = _yoy_step_score(yoy_avg)

    # 末月 MoM
    mom_score = 0.0
    mom_val: float | None = None
    last = monthly_3m[-1] if isinstance(monthly_3m[-1], dict) else None
    if last is not None:
        mom_val = _safe_num(last.get("mom_pct"))
        if mom_val is not None:
            if mom_val > 0:
                mom_score = 0.5
            elif mom_val < 0:
                mom_score = -0.5

    subscore = yoy_score + mom_score
    return subscore, {
        "yoy_avg": round(yoy_avg, 2),
        "yoy_score": yoy_score,
        "last_mom": round(mom_val, 2) if mom_val is not None else None,
        "mom_score": mom_score,
        "n_months": len(yoy_vals),
    }


def _squash(net: int) -> float:
    """把 net_delta 線性壓到 [-1, +1]：每多 1 項 ~ +0.33，3 項以上飽和。"""
    return max(-1.0, min(1.0, net / 3.0))


def compute_mj_trend_subscore(mj_snapshots_3q: list[dict]) -> tuple[float, dict]:
    """MJ 季財報 trend 子分數，範圍 [-2, +2]。

    對近 3 季快照逐期 diff 兩次（Q-2→Q-1、Q-1→Q），兩次 net_delta 同向 → 自然累加；
    分歧 → 衰減 0.5×（避免假訊號）。

    Args:
        mj_snapshots_3q: 近 3 季快照 list[oldest..latest]，每元素為 analyze_financial_health 回傳 dict

    Returns:
        (subscore, detail_dict)
    """
    if not isinstance(mj_snapshots_3q, list):
        return 0.0, {"reason": "bad_input", "n_snapshots": 0}

    valid = [s for s in mj_snapshots_3q if isinstance(s, dict)]
    n = len(valid)
    if n < 2:
        return 0.0, {"reason": "insufficient_snapshots", "n_snapshots": n}

    if n == 2:
        v = diff_mj_health(valid[0], valid[1], stock_id="", min_net_delta=1)
        subscore = _squash(v.net_delta) * 2.0  # 線性放大到 [-2, +2]
        return max(-2.0, min(2.0, subscore)), {
            "n_snapshots": 2,
            "delta_1": v.net_delta,
            "delta_2": None,
            "same_direction": None,
            "subscore": round(subscore, 3),
        }

    # n >= 3：取最新 3 季
    last3 = valid[-3:]
    v1 = diff_mj_health(last3[0], last3[1], stock_id="", min_net_delta=1)
    v2 = diff_mj_health(last3[1], last3[2], stock_id="", min_net_delta=1)
    s1 = _squash(v1.net_delta)
    s2 = _squash(v2.net_delta)

    same_dir = (s1 > 0 and s2 > 0) or (s1 < 0 and s2 < 0)
    if same_dir:
        subscore = s1 + s2  # 同向累加，範圍 [-2, +2]
    else:
        subscore = (s1 + s2) * 0.5  # 分歧衰減
    subscore = max(-2.0, min(2.0, subscore))

    return subscore, {
        "n_snapshots": 3,
        "delta_1": v1.net_delta,
        "delta_2": v2.net_delta,
        "same_direction": same_dir,
        "subscore": round(subscore, 3),
    }


def _label_from_score(score: float) -> tuple[str, str]:
    """把 score 對應到 5 段標籤。"""
    for thr, lbl, code in _LABEL_THRESHOLDS:
        if score >= thr:
            return lbl, code
    return _LOW_LABEL


def compute_trend_score(
    monthly_revenue_3m: list[dict] | None,
    mj_snapshots_3q: list[dict] | None,
    w_monthly: float = 0.65,
) -> dict:
    """月+季雙頻率融合進退分數。

    Args:
        monthly_revenue_3m: 近 3 月月營收
        mj_snapshots_3q: 近 3 季 MJ 體檢快照
        w_monthly: 月營收權重（預設 0.65，季財報自動 = 1 - w_monthly）

    Returns:
        dict {
            score, label, label_code,
            monthly_subscore, mj_subscore,
            w_monthly, w_quarterly,
            monthly_detail, mj_detail,
        }
    """
    if not isinstance(w_monthly, (int, float)) or not (0.0 <= float(w_monthly) <= 1.0):
        w_monthly = 0.65
    w_monthly = float(w_monthly)
    w_quarterly = 1.0 - w_monthly

    mon_score, mon_detail = compute_monthly_revenue_subscore(monthly_revenue_3m or [])
    mj_score, mj_detail = compute_mj_trend_subscore(mj_snapshots_3q or [])

    final = mon_score * w_monthly + mj_score * w_quarterly
    label, code = _label_from_score(final)

    return {
        "score": round(final, 3),
        "label": label,
        "label_code": code,
        "monthly_subscore": round(mon_score, 3),
        "mj_subscore": round(mj_score, 3),
        "w_monthly": w_monthly,
        "w_quarterly": w_quarterly,
        "monthly_detail": mon_detail,
        "mj_detail": mj_detail,
    }


def compute_one_stock_trend(
    sid: str,
    yyyymm_curr: str,
    token: str,
    w_monthly: float,
    *,
    fetch_financial_statements,
    analyze_financial_health,
    list_snapshots,
    load_snapshot,
    save_snapshot,
) -> dict:
    """單檔 MJ 趨勢分數編排（SSOT,個股 Tab + 組合 Tab 共用）。

    流程：抓月營收 → 補抓 MJ 季財報 → 跑 compute_trend_score。
    例外永遠 graceful — 單檔失敗不阻斷批次。

    依賴注入維持本模組純編排特性（不 hard import L1 fetcher）。

    Returns: dict {sid, label, label_code, score, mon_sub, mj_sub,
                   mon_detail, mj_detail, snap_ym, snap_stale, note}
    """
    row: dict = {
        "sid": sid, "label": "—", "label_code": "error", "score": 0.0,
        "mon_sub": 0.0, "mj_sub": 0.0, "note": "",
        "snap_ym": "", "snap_stale": None,
    }
    monthly_3m: list[dict] = []
    mj_snaps: list[dict] = []

    # ── 1. 月營收 3 期 ──────────────────────────────────────────
    try:
        from src.ui.tabs import compute_yoy_mom, fetch_monthly_revenue
        df_rev = fetch_monthly_revenue(sid, months=15)
        stats = compute_yoy_mom(df_rev) if df_rev is not None and not df_rev.empty else {}
        yoy_last3 = (stats or {}).get("yoy_last3") or []
        mom_last = (stats or {}).get("mom_last")
        if isinstance(yoy_last3, list) and yoy_last3:
            for j, yoy in enumerate(yoy_last3):
                if yoy is None:
                    continue
                m_dict: dict = {"yoy_pct": yoy}
                if j == len(yoy_last3) - 1 and mom_last is not None:
                    m_dict["mom_pct"] = mom_last
                monthly_3m.append(m_dict)
    except Exception as e:  # pragma: no cover - defensive
        row["note"] += f"月營收抓取失敗 ({type(e).__name__}); "

    # ── 2. MJ 季財報快照（不足 3 季自動補抓本季）───────────────
    try:
        yms = list_snapshots(sid)
        if yyyymm_curr not in yms:
            try:
                fin = fetch_financial_statements(sid, token)
                if fin and not fin.get("error"):
                    mj = analyze_financial_health(token, sid, fin, news_context="")
                    if isinstance(mj, dict):
                        save_snapshot(sid, yyyymm_curr, mj)
                        yms = list_snapshots(sid)
            except Exception as e_in:  # pragma: no cover - defensive
                row["note"] += f"本季 MJ 補抓失敗 ({type(e_in).__name__}); "

        if yms:
            row["snap_ym"] = yms[0]
            row["snap_stale"] = (yms[0] != yyyymm_curr)

        for ym in yms[:3]:
            snap = load_snapshot(sid, ym)
            if isinstance(snap, dict):
                mj_snaps.append(snap)
        mj_snaps.reverse()  # oldest..latest
    except Exception as e:  # pragma: no cover - defensive
        row["note"] += f"MJ 快照載入失敗 ({type(e).__name__}); "

    # ── 3. 合議 ─────────────────────────────────────────────────
    try:
        out = compute_trend_score(monthly_3m, mj_snaps, w_monthly=w_monthly)
        row["label"] = out["label"]
        row["label_code"] = out["label_code"]
        row["score"] = out["score"]
        row["mon_sub"] = out["monthly_subscore"]
        row["mj_sub"] = out["mj_subscore"]
        row["mon_detail"] = out["monthly_detail"]
        row["mj_detail"] = out["mj_detail"]
        if not monthly_3m and not mj_snaps:
            row["note"] += "月+季資料皆缺; "
    except Exception as e:  # pragma: no cover - defensive
        row["note"] += f"合議失敗 ({type(e).__name__}); "
    return row
