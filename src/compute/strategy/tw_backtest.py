"""
tw_backtest.py — 台股版倒掛翻正後 ^TWII 表現歷史回測（v1.0）

設計目標
========
複製 fund-dashboard `services.macro_service.backtest_turning_points` 的概念，
但對「台股加權指數 ^TWII」做後續 6/12/18M 表現回測——
讓使用者看到「美國 10Y-2Y 倒掛→翻正」這個全球領先訊號對台股的歷史含義。

資料源
======
- T10Y2Y：FRED API（全球無得替代，沿用美債曲線）
- ^TWII：透過 macro_core.fetch_yf_close 抓 Yahoo Chart REST API（NAS proxy）

對外 API
========
- `backtest_twii_turning_points(fred_api_key, ...) -> dict`
- `find_uninversion_events(s, ...) -> list`（重用）
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


# ════════════════════════════════════════════════════════════════
# 事件識別 — 與 fund-dashboard 同邏輯
# ════════════════════════════════════════════════════════════════
def find_uninversion_events(s: pd.Series,
                            min_inversion_depth: float = -0.10,
                            stable_days: int = 5,
                            cooldown_days: int = 365) -> list:
    """掃描 T10Y2Y 序列，識別所有「真倒掛 → 穩定翻正」事件。

    事件定義（同時滿足）：
      1. 區段內 min(T10Y2Y) ≤ min_inversion_depth（去除貼地噪音）
      2. 翻正日 T10Y2Y ≥ 0 且後續 stable_days 日皆 ≥ 0（去抖）
      3. 距上一事件 ≥ cooldown_days（避免同週期重複觸發）

    ⚠️ PIT / lookahead（v19.183 D2）—— `date` 不是可執行進場日
    -----------------------------------------------------------
    條件 2 的「後續 stable_days 日皆 ≥ 0」**用到 `date` 之後的資料**。
    站在 `date` 當天的人不可能知道接下來 5 天會不會再翻回負值，
    因此 `date` 是「事後標定的翻正首日」，不是「當下可決策的日子」。

    本函式因此同時回 `confirm_date = dates[i + stable_days - 1]`
    —— 去抖窗口的最後一天，也就是這個事件**第一次成為已知事實**的日子。
    任何前瞻報酬（`_forward_return`）都必須以 `confirm_date` 起算，
    否則會白吃 stable_days 根 K 棒的漲跌（CLAUDE.md §2.3 禁止 lookahead）。

    `date` 欄位保留原語意（翻正首日）供畫面標示與既有 caller，
    **不改值**；新增欄位為 schema-additive。

    Returns
    -------
    [{"date": Timestamp, "confirm_date": Timestamp, "t10y2y_min_pre": float}, ...]
    """
    if s is None or s.empty or len(s) < stable_days + 2:
        return []
    s = s.sort_index().dropna()
    vals  = s.values
    dates = s.index

    events: list = []
    in_inversion = False
    seg_min      = 0.0
    last_event_t = None

    for i in range(len(vals)):
        v = vals[i]
        if v < 0:
            if not in_inversion:
                in_inversion = True
                seg_min = v
            else:
                seg_min = min(seg_min, v)
        else:
            if in_inversion and seg_min <= min_inversion_depth:
                end = i + stable_days
                if end <= len(vals) and (vals[i:end] >= 0).all():
                    t = dates[i]
                    if last_event_t is None \
                       or (t - last_event_t).days >= cooldown_days:
                        events.append({
                            "date": t,
                            # 去抖窗口最後一天 = 事件第一次成為已知事實的日子。
                            # end = i + stable_days 已通過 `end <= len(vals)` 檢查，
                            # 故 i + stable_days - 1 必為合法索引。
                            "confirm_date": dates[i + stable_days - 1],
                            "t10y2y_min_pre": float(round(seg_min, 3)),
                        })
                        last_event_t = t
            in_inversion = False
            seg_min      = 0.0
    return events


def _entry_index(idx: pd.Series, t0: pd.Timestamp,
                 strict_after: bool = False) -> Optional[int]:
    """回「可進場那一根 K 棒」的位置索引；超出序列尾端回 None。

    strict_after=False → 第一根 **≥ t0** 的 K 棒（原行為）。
    strict_after=True  → 第一根 **> t0** 的 K 棒（v19.183 D2 PIT 修正）。

    為何需要 strict_after（CLAUDE.md §2.3 / §4.1 時區）
    -------------------------------------------------
    T10Y2Y 是 FRED 日頻序列，observation date = D 的那筆值要等 **D 當天美股收盤後**
    才發布（≈ D+1 04:00 台北時間）。台股當天 13:30 就收盤了 ——
    也就是「D 這天的 T10Y2Y」對台股投資人而言，最早只能在 **D 的下一根 TWII K 棒**
    才拿得到。用 D 當天的 TWII 收盤當進場價，等於用還沒發布的資料下單。
    """
    if idx is None or idx.empty:
        return None
    i0 = int(idx.index.searchsorted(t0, side='right' if strict_after else 'left'))
    return None if i0 >= len(idx) else i0


def _forward_return(idx: pd.Series, t0: pd.Timestamp,
                    days: int, *, strict_after: bool = False) -> Optional[float]:
    """指數從 t0（或其後第一根可交易 K 棒）起 days 天後的累計報酬（%）。

    窗口未到期回 None。`days` 為 **日曆日**（182 / 365 / 547 ≈ 6M / 12M / 18M），
    前瞻窗口以**實際進場 K 棒日期**起算，而非 t0（兩者在 strict_after=True 時不同）。

    strict_after：見 `_entry_index`。預設 False 保留原行為（既有 caller / 測試無感）；
    回測主路徑一律傳 True（§2.3 防 lookahead）。
    """
    if idx is None or idx.empty:
        return None
    try:
        idx0 = _entry_index(idx, t0, strict_after=strict_after)
        if idx0 is None:
            return None
        entry_ts = idx.index[idx0]
        p0 = float(idx.iloc[idx0])
        t1 = entry_ts + pd.Timedelta(days=days)
        idx1 = idx.index.searchsorted(t1)
        if idx1 >= len(idx):
            return None
        p1 = float(idx.iloc[idx1])
        if p0 <= 0:
            return None
        return round((p1 / p0 - 1.0) * 100.0, 2)
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════
# 主 API — 倒掛翻正後 ^TWII 表現
# ════════════════════════════════════════════════════════════════
def backtest_twii_turning_points(
    fred_api_key: str = "",
    min_inversion_depth: float = -0.10,
    stable_days: int = 5,
    cooldown_days: int = 365,
) -> dict:
    """倒掛翻正歷史回測 — 台股版（v1.0）

    抓 25Y T10Y2Y 日頻 + ^TWII 全歷史，識別所有「倒掛→翻正」事件，
    對每事件計算 TWII 後續 6M / 12M / 18M 累計報酬，及中位數與勝率。

    Returns
    -------
    {
      "events": [
        {"date": Timestamp,          # 翻正首日（事後標定，**非**可執行日）
         "confirm_date": Timestamp,  # 去抖窗口最後一天 = 事件成為已知事實之日
         "entry_date": Timestamp|None,  # 實際進場 K 棒（confirm_date 之後第一根）
         "t10y2y_min_pre": float,
         "ret_6m": float|None, "ret_12m": float|None, "ret_18m": float|None,
         "complete": bool},
        ...
      ],
      "summary": {"n_events": int, "n_complete_18m": int,
                  "median_6m/12m/18m": float, "mean_6m/12m/18m": float,
                  "win_rate_6m/12m/18m": float},
      "twii_series":   pd.Series,
      "t10y2y_series": pd.Series,
      "source_ok": bool,
      "note": str,
    }
    """
    out: dict = {
        "events": [],
        "summary": {"n_events": 0, "n_complete_18m": 0,
                    "median_6m": None,  "median_12m": None, "median_18m": None,
                    "mean_6m":   None,  "mean_12m":   None, "mean_18m":   None,
                    "win_rate_6m": None, "win_rate_12m": None,
                    "win_rate_18m": None},
        "twii_series":   pd.Series(dtype=float),
        "t10y2y_series": pd.Series(dtype=float),
        "source_ok": False,
        "note": "",
    }

    if not fred_api_key:
        out["note"] = "FRED API key 未設置"
        return out

    # ── 抓 T10Y2Y 25Y ─────────────────────────────────────────────
    try:
        from src.data.macro import fetch_fred as _ff_tw
        df_t = _ff_tw("T10Y2Y", fred_api_key, n=8000)
    except Exception as e:
        out["note"] = f"T10Y2Y 抓取異常：{str(e)[:80]}"
        return out
    if df_t is None or df_t.empty or len(df_t) < 1000:
        out["note"] = "T10Y2Y 資料不足（< 1000 obs）"
        return out

    s_t = (df_t.sort_values("date").set_index("date")["value"]
                 .astype(float).dropna())
    try:
        s_t.index = s_t.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    out["t10y2y_series"] = s_t

    # ── 抓 ^TWII 全歷史（多 range 備援）───────────────────────────
    try:
        from src.data.macro import fetch_yf_close as _fyf_tw
    except ImportError as e:
        out["note"] = f"macro_core.fetch_yf_close import 失敗：{e}"
        return out

    twii = None
    _twii_tried: list[str] = []
    for _rng in ("max", "30y", "20y", "10y", "5y"):
        try:
            _cand = _fyf_tw("^TWII", range_=_rng, interval="1d")
            _twii_tried.append(f"{_rng}={len(_cand) if _cand is not None else 0}")
            if _cand is not None and not _cand.empty:
                if twii is None or len(_cand) > len(twii):
                    twii = _cand
                if twii is not None and len(twii) >= 1000:
                    break
        except Exception as e:
            _twii_tried.append(f"{_rng}=ERR:{type(e).__name__}")
            continue
    if twii is None or twii.empty or len(twii) < 500:
        out["note"] = (
            f"^TWII history insufficient (< 500 trading days)"
            f" — 嘗試結果：{', '.join(_twii_tried)}"
        )
        return out
    try:
        twii.index = twii.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    out["twii_series"] = twii.sort_index()

    # ── 事件識別 ────────────────────────────────────────────────
    events = find_uninversion_events(
        s_t, min_inversion_depth=min_inversion_depth,
        stable_days=stable_days, cooldown_days=cooldown_days,
    )

    # ── 對每事件計算 TWII +6M/+12M/+18M 報酬 ──────────────────────
    today = pd.Timestamp.today().normalize()
    # v18.436 #10:18 月回測完整度門檻 547 inline → SSOT(同值原寫兩處)
    from shared.signal_thresholds import BACKTEST_18M_DAYS_THRESHOLD
    # ⚠️ v19.183 D2（§2.3 防 lookahead）：前瞻報酬一律以 **confirm_date 之後的
    #    第一根 TWII K 棒** 起算，不再用 `ev['date']`（翻正首日）。
    #    舊碼白吃了 stable_days 根 K 棒 + 1 天 FRED 發布延遲的漲跌 ——
    #    那段報酬只有「已經知道未來 5 天不會翻回負值」的人才拿得到。
    #    `date` 欄位語意不變（畫面仍標翻正首日），另出 `entry_date` 讓使用者
    #    看得到「真正可以下單的是哪一天」。
    enriched: list = []
    for ev in events:
        t0 = ev["date"]
        t_conf = ev.get("confirm_date") or t0
        _ei = _entry_index(out["twii_series"], t_conf, strict_after=True)
        _entry_ts = (out["twii_series"].index[_ei] if _ei is not None else None)
        r6  = _forward_return(out["twii_series"], t_conf, 182, strict_after=True)
        r12 = _forward_return(out["twii_series"], t_conf, 365, strict_after=True)
        r18 = _forward_return(out["twii_series"], t_conf,
                              BACKTEST_18M_DAYS_THRESHOLD, strict_after=True)
        complete = (_entry_ts is not None
                    and (today - _entry_ts).days >= BACKTEST_18M_DAYS_THRESHOLD
                    and r18 is not None)
        enriched.append({
            "date": t0,
            "confirm_date": t_conf,
            "entry_date": _entry_ts,
            "t10y2y_min_pre": ev["t10y2y_min_pre"],
            "ret_6m":  r6,
            "ret_12m": r12,
            "ret_18m": r18,
            "complete": complete,
        })
    out["events"] = enriched

    # ── Summary 統計 ──────────────────────────────────────────────
    def _stat(key: str, require_complete: bool = False):
        vals = [e[key] for e in enriched
                if e[key] is not None
                and (e["complete"] if require_complete else True)]
        if not vals:
            return None, None, None
        med = float(np.median(vals))
        avg = float(np.mean(vals))
        wr  = float(sum(1 for v in vals if v > 0) / len(vals) * 100.0)
        return round(med, 2), round(avg, 2), round(wr, 1)

    m6,  a6,  w6  = _stat("ret_6m")
    m12, a12, w12 = _stat("ret_12m")
    m18, a18, w18 = _stat("ret_18m", require_complete=True)

    out["summary"].update({
        "n_events":        len(enriched),
        "n_complete_18m":  sum(1 for e in enriched if e["complete"]),
        "median_6m":   m6,  "median_12m": m12, "median_18m": m18,
        "mean_6m":     a6,  "mean_12m":   a12, "mean_18m":   a18,
        "win_rate_6m": w6,  "win_rate_12m": w12, "win_rate_18m": w18,
    })
    out["source_ok"] = True
    out["note"] = (
        f"識別 {len(enriched)} 個事件"
        f"（去抖 stable={stable_days}d, depth≤{min_inversion_depth}）"
    )
    return out
