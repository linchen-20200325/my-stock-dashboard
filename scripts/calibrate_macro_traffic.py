"""calibrate_macro_traffic.py — 台股紅綠燈系統校準腳本 (v1.0)

目的
----
對 `macro_helpers.calc_traffic_light` 做歷史回測，量化下列指標：
  (a) 每個燈號 (🟢🟡🔴) 在後 20/60 日 TWII 的真實勝率 / 命中率
  (b) `mkt_info.score` 與後 N 日報酬的相關性矩陣
  (c) 建議的門檻調整範圍（5+6 keys 中可調者）

DI 設計
-------
資料抓取層 (`fetch_*`) 與燈號計算層 (`calc_traffic_light`) 分離。
sandbox 內可注入 yfinance TWII (`macro_core.fetch_yf_ohlcv`)，
無 FinMind 歷史 quota 時自動降級為「TWII-only mode」並在報告
明標「樣本不足」。

真值定義
--------
- 🔴 高風險命中：後 20 日 TWII 跌幅 > 8% 或後 60 日跌幅 > 15%
- 🟢 多頭命中：後 20 日 TWII 漲幅 > 5%
- 🟡 中性：其餘狀態

執行
----
    python calibrate_macro_traffic.py            # 預設 1y 歷史
    python calibrate_macro_traffic.py --range 2y  # 2y 歷史
    python calibrate_macro_traffic.py --output MACRO_CALIBRATION.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


# ════════════════════════════════════════════════════════════════
# 資料抓取層 (DI hooks)
# ════════════════════════════════════════════════════════════════
_CACHE_DIR = "data_cache"


def load_from_cache(years: int = 5) -> Optional[pd.DataFrame]:
    """讀 data_cache/twii_ohlcv.parquet + enrich FinMind 欄位（首選資料源）。

    回傳 DataFrame indexed by date，含 Close/Volume + foreign_buy/m1b_m2_gap
    （缺檔欄位以 NaN 填、後續 _build_features_at 處理 NaN→中性值）。
    缺 cache 或讀檔失敗回 None，呼叫端應 fallback 到 fetch_twii_ohlcv。
    """
    import os as _os
    _twii_path = _os.path.join(_CACHE_DIR, "twii_ohlcv.parquet")
    if not _os.path.exists(_twii_path):
        return None
    try:
        df = pd.read_parquet(_twii_path)
    except Exception as e:
        print(f"[calibrate/cache] 讀 twii_ohlcv 失敗：{type(e).__name__}: {e}")
        return None
    # 整型化：date → DatetimeIndex、欄位首字母大寫對齊既有 _build_features_at
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High",
                            "low": "Low", "close": "Close", "volume": "Volume"})
    # 只保留指定年份（避免拉太久反而 walk-forward 計算過長）
    cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=years * 365))
    df = df[df.index >= cutoff]
    # Enrich：左 join FinMind 欄位（無檔則 NaN）
    df = _enrich_with_finmind(df)
    print(f"[calibrate/cache] ✅ 載入 {len(df)} 日 ({df.index[0].date()} ~ {df.index[-1].date()})")
    return df


def _enrich_with_finmind(df_twii: pd.DataFrame) -> pd.DataFrame:
    """對齊 FinMind 欄位到 TWII 日 index：左 join + ffill 月頻欄位。

    新增欄位（缺檔自動 NaN）：
      - foreign_buy: 三大法人外資淨買賣（億）
      - margin_balance: 融資餘額
      - m1b_m2_gap: M1B-M2 月年增率差
    """
    import os as _os
    out = df_twii.copy()
    for fname, cols, ffill in [
        ("finmind_inst.parquet", ["foreign_buy"], False),
        ("finmind_margin.parquet", ["margin_balance"], False),
        ("finmind_m1m2.parquet", ["m1b_m2_gap"], True),  # 月頻 → ffill 到日
    ]:
        path = _os.path.join(_CACHE_DIR, fname)
        if not _os.path.exists(path):
            for c in cols:
                out[c] = float("nan")
            continue
        try:
            sub = pd.read_parquet(path)
            sub["date"] = pd.to_datetime(sub["date"])
            sub = sub.set_index("date").sort_index()
            out = out.join(sub[cols], how="left")
            if ffill:
                out[cols] = out[cols].ffill()
        except Exception as e:
            print(f"[calibrate/enrich] {fname} 讀檔失敗：{type(e).__name__}: {e}")
            for c in cols:
                if c not in out.columns:
                    out[c] = float("nan")
    return out


def fetch_twii_ohlcv(range_: str = "2y") -> Optional[pd.DataFrame]:
    """抓 ^TWII OHLCV 全歷史；失敗回 None。"""
    try:
        from macro_core import fetch_yf_ohlcv
        df = fetch_yf_ohlcv("^TWII", range_=range_, interval="1d")
        if df is None or df.empty:
            return None
        cols = {c.lower(): c for c in df.columns}
        if "close" in cols and "Close" not in df.columns:
            df = df.rename(columns={cols["close"]: "Close",
                                    cols.get("volume", "volume"): "Volume"})
        if "Close" not in df.columns:
            return None
        try:
            df.index = df.index.tz_localize(None)
        except (AttributeError, TypeError):
            pass
        return df.sort_index()
    except Exception as e:
        print(f"[calibrate] fetch_twii_ohlcv 異常：{type(e).__name__}: {e}")
        return None


def synthetic_twii_ohlcv(n_days: int = 500, seed: int = 42) -> pd.DataFrame:
    """合成 ^TWII OHLCV（demo 模式 / NAS proxy 不可達時用）。

    GBM + 加入 3 段明顯回撤 + 復甦循環，確保紅綠燈分佈不退化為單一色。
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-02", periods=n_days, freq="B")
    drift = 0.0003
    vol = 0.012
    rets = rng.normal(drift, vol, n_days)
    # 注入 3 段急跌（模擬 2024/04、2024/10、2025/03 修正）
    for crash_start, length in [(80, 15), (200, 20), (350, 18)]:
        if crash_start + length < n_days:
            rets[crash_start:crash_start + length] = rng.normal(
                -0.008, 0.018, length)
    # 注入 2 段強漲（模擬 AI 行情）
    for rally_start, length in [(120, 30), (260, 40)]:
        if rally_start + length < n_days:
            rets[rally_start:rally_start + length] = rng.normal(
                +0.006, 0.010, length)
    prices = 17000 * np.exp(np.cumsum(rets))
    high = prices * (1 + np.abs(rng.normal(0, 0.005, n_days)))
    low = prices * (1 - np.abs(rng.normal(0, 0.005, n_days)))
    op = prices * (1 + rng.normal(0, 0.003, n_days))
    vol_series = rng.lognormal(mean=20, sigma=0.3, size=n_days)
    return pd.DataFrame({
        "Open": op, "High": high, "Low": low, "Close": prices,
        "Volume": vol_series,
    }, index=dates)


# ════════════════════════════════════════════════════════════════
# 逐日特徵建構（TWII-only mode）
# ════════════════════════════════════════════════════════════════
@dataclass
class _Features:
    date: pd.Timestamp
    close: float
    ma60: float
    ma120: float
    ma60_above_3d: bool
    ma60_below_3d: bool
    ma120_above_3d: bool
    ma120_below_3d: bool
    ma120_rising: bool
    ma120_falling: bool
    ma60_prev: float
    vol_today: float
    avg_vol_20: float
    # Enriched (cache 載入時填；缺檔則 NaN，後續用中性值代入)
    foreign_buy: float = float("nan")
    m1b_m2_gap: float = float("nan")
    m1b_m2_prev: float = float("nan")


def _build_features_at(df: pd.DataFrame, t: int) -> Optional[_Features]:
    """以 t 為「今日」，用 df.iloc[:t+1] 計算當日所需特徵。
    需 t >= 125 才能算出 MA120 斜率（5日前）。
    """
    if t < 125 or t >= len(df):
        return None
    sub = df.iloc[:t + 1]
    close = sub["Close"]
    cur = float(close.iloc[-1])
    ma60_series = close.rolling(60).mean()
    ma120_series = close.rolling(120).mean()
    ma60 = float(ma60_series.iloc[-1])
    ma120 = float(ma120_series.iloc[-1])
    if pd.isna(ma60) or pd.isna(ma120):
        return None
    c3 = close.iloc[-3:].values
    m60_3 = ma60_series.iloc[-3:].values
    m120_3 = ma120_series.iloc[-3:].values
    ma60_above_3d = bool(len(c3) == 3 and not pd.isna(m60_3).any()
                         and (c3 > m60_3).all())
    ma60_below_3d = bool(len(c3) == 3 and not pd.isna(m60_3).any()
                         and (c3 < m60_3).all())
    ma120_above_3d = bool(len(c3) == 3 and not pd.isna(m120_3).any()
                          and (c3 > m120_3).all())
    ma120_below_3d = bool(len(c3) == 3 and not pd.isna(m120_3).any()
                          and (c3 < m120_3).all())
    ma120_5ago = float(ma120_series.iloc[-6]) if len(sub) >= 126 else float("nan")
    ma120_rising = (not pd.isna(ma120_5ago)) and (ma120 > ma120_5ago)
    ma120_falling = (not pd.isna(ma120_5ago)) and (ma120 < ma120_5ago)
    ma60_prev = float(ma60_series.iloc[-2]) if len(sub) >= 61 else ma60
    vol_today = float(sub["Volume"].iloc[-1]) if "Volume" in sub.columns else 0.0
    avg_vol = (float(sub["Volume"].rolling(20).mean().iloc[-1])
               if "Volume" in sub.columns and len(sub) >= 20 else 1.0)
    # Enriched cols（cache 載入時存在；fallback fetch_twii_ohlcv 模式則無）
    fb = float(sub["foreign_buy"].iloc[-1]) if "foreign_buy" in sub.columns else float("nan")
    m_cur = float(sub["m1b_m2_gap"].iloc[-1]) if "m1b_m2_gap" in sub.columns else float("nan")
    m_prev = (float(sub["m1b_m2_gap"].iloc[-22])
              if "m1b_m2_gap" in sub.columns and len(sub) >= 22 else float("nan"))
    return _Features(
        date=pd.Timestamp(sub.index[-1]),
        close=cur, ma60=ma60, ma120=ma120,
        ma60_above_3d=ma60_above_3d, ma60_below_3d=ma60_below_3d,
        ma120_above_3d=ma120_above_3d, ma120_below_3d=ma120_below_3d,
        ma120_rising=ma120_rising, ma120_falling=ma120_falling,
        ma60_prev=ma60_prev, vol_today=vol_today, avg_vol_20=avg_vol,
        foreign_buy=fb, m1b_m2_gap=m_cur, m1b_m2_prev=m_prev,
    )


def _features_to_traffic_light(f: _Features) -> dict:
    """以特徵組成 mkt_info → 呼叫 calc_traffic_light（cache 模式餵真實值）。"""
    from src.services import market_regime
    from src.compute.macro import calc_traffic_light
    fb = 0 if pd.isna(f.foreign_buy) else float(f.foreign_buy)
    mg = None if pd.isna(f.m1b_m2_gap) else float(f.m1b_m2_gap)
    mp = None if pd.isna(f.m1b_m2_prev) else float(f.m1b_m2_prev)
    mkt = market_regime(
        index_close=f.close, ma60=f.ma60, ma120=f.ma120,
        foreign_buy=fb, ad_ratio=1.0,  # ADL 無歷史 cache，暫保留中性 1.0
        ma60_prev=f.ma60_prev, ma120_prev=None,
        vol_today=f.vol_today, avg_vol_20=f.avg_vol_20,
        m1b_m2_gap=mg, m1b_m2_prev=mp,
        ma60_above_3d=f.ma60_above_3d, ma60_below_3d=f.ma60_below_3d,
        ma120_above_3d=f.ma120_above_3d, ma120_below_3d=f.ma120_below_3d,
        ma120_rising=f.ma120_rising, ma120_falling=f.ma120_falling,
    )
    # 餵 cl_data 進去：foreign_buy 非 NaN 才填，否則沿用 None（避免假資料）
    cl = ({"inst": {"外資": {"net": fb * 1e8}}} if not pd.isna(f.foreign_buy) else None)
    tl = calc_traffic_light(mkt_info=mkt, jingqi_info=None,
                            cl_data=cl, li_latest=None)
    return tl or {}


# ════════════════════════════════════════════════════════════════
# 回測主流程
# ════════════════════════════════════════════════════════════════
def _forward_return(df: pd.DataFrame, t: int, n: int) -> Optional[float]:
    """index t 之後 n 個交易日報酬（%）。窗口未滿回 None。"""
    if t + n >= len(df):
        return None
    p0 = float(df["Close"].iloc[t])
    p1 = float(df["Close"].iloc[t + n])
    if p0 <= 0:
        return None
    return (p1 / p0 - 1.0) * 100.0


def run_backtest(df: pd.DataFrame) -> pd.DataFrame:
    """逐日重建燈號 + 配對後 20/60 日 TWII 報酬。"""
    rows = []
    for t in range(125, len(df) - 20):  # 至少有 20 日 forward 才有 ret_20d
        f = _build_features_at(df, t)
        if f is None:
            continue
        tl = _features_to_traffic_light(f)
        rows.append({
            "date": f.date,
            "close": f.close,
            "color": tl.get("icon", "?"),
            "label": tl.get("label", ""),
            "regime": tl.get("regime", ""),
            "score": float(tl.get("score") or 0),
            "health": float(tl.get("health") or 0),
            "ret_20d": _forward_return(df, t, 20),
            "ret_60d": _forward_return(df, t, 60),
        })
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════
# 真值定義 + 命中率
# ════════════════════════════════════════════════════════════════
RED_20D_THR = -8.0      # 後 20 日 TWII 跌幅 > 8%
RED_60D_THR = -15.0     # 或後 60 日跌幅 > 15%
GREEN_20D_THR = +5.0    # 後 20 日 TWII 漲幅 > 5%


def label_hit(row: pd.Series) -> str:
    """ground truth：'red_hit' / 'green_hit' / 'neutral'。"""
    r20 = row["ret_20d"]
    r60 = row["ret_60d"]
    if r20 is not None and not pd.isna(r20):
        if r20 < RED_20D_THR:
            return "red_hit"
        if r60 is not None and not pd.isna(r60) and r60 < RED_60D_THR:
            return "red_hit"
        if r20 > GREEN_20D_THR:
            return "green_hit"
    return "neutral"


def compute_metrics(bt: pd.DataFrame) -> dict:
    """precision / recall / confusion matrix 計算。"""
    bt = bt.copy()
    bt["truth"] = bt.apply(label_hit, axis=1)
    # 預測類別：🟢=green_pred / 🟡=neutral_pred / 🔴=red_pred
    bt["pred"] = bt["color"].map({"🟢": "green_pred", "🟡": "neutral_pred",
                                   "🔴": "red_pred"}).fillna("neutral_pred")

    # 命中率
    def _hit_rate(pred_lbl: str, truth_lbl: str) -> tuple[int, int, float]:
        mask = bt["pred"] == pred_lbl
        n = int(mask.sum())
        if n == 0:
            return 0, 0, 0.0
        tp = int(((bt["pred"] == pred_lbl) & (bt["truth"] == truth_lbl)).sum())
        return tp, n, round(tp / n * 100, 1)

    g_tp, g_n, g_rate = _hit_rate("green_pred", "green_hit")
    r_tp, r_n, r_rate = _hit_rate("red_pred", "red_hit")

    # recall（被真值抓到的比例）
    n_green_truth = int((bt["truth"] == "green_hit").sum())
    n_red_truth = int((bt["truth"] == "red_hit").sum())
    g_recall = round(g_tp / n_green_truth * 100, 1) if n_green_truth else 0.0
    r_recall = round(r_tp / n_red_truth * 100, 1) if n_red_truth else 0.0

    # confusion matrix
    cm = pd.crosstab(bt["pred"], bt["truth"], margins=False)

    # 平均報酬（按燈號分組）
    avg_ret = bt.groupby("color")[["ret_20d", "ret_60d"]].agg(
        ["mean", "median", "count"])

    # score vs forward return 相關性
    corr_20 = float(bt[["score", "ret_20d"]].dropna().corr().iloc[0, 1])
    corr_60 = float(bt[["score", "ret_60d"]].dropna().corr().iloc[0, 1])

    return {
        "n_total": len(bt),
        "n_green_pred": g_n, "n_red_pred": r_n,
        "green_precision": g_rate, "green_recall": g_recall,
        "red_precision": r_rate, "red_recall": r_recall,
        "n_green_truth": n_green_truth, "n_red_truth": n_red_truth,
        "confusion_matrix": cm,
        "avg_ret_by_color": avg_ret,
        "corr_score_ret20": round(corr_20, 3),
        "corr_score_ret60": round(corr_60, 3),
        "bt_df": bt,
    }


# ════════════════════════════════════════════════════════════════
# Walk-Forward Validation + Threshold Grid Search（反過擬合核心）
# ════════════════════════════════════════════════════════════════
#
# 設計原則
# --------
# 1. **永不在訓練窗報告分數**：每折在 train 找最佳門檻，metrics 只看 test
# 2. **正則化**：偏好接近現行門檻的解（避免劇烈調整）
# 3. **穩健性 > 帳面最佳**：選「各折一致性最高、train→test 衰退最小」那組
# 4. **誠實標警語**：IS/OOS 差距過大時，直接標「過擬合風險，不建議套用」


def _backtest_with_inputs_cache(df: pd.DataFrame) -> list[dict]:
    """跑一次 backtest，cache 每日的 (mkt_info, jq, cl, li) + 真實 forward 報酬。

    回傳 list[dict]，每筆含：date, close, ret_20d, ret_60d, mkt_info, jingqi_info,
    cl_data, li_latest。後續用於 evaluate_thresholds 重決色。

    cache 模式下：df 已含 foreign_buy / m1b_m2_gap 欄位 → 餵真實值給 market_regime
    與 calc_traffic_light（解 TWII-only score 結構性 0~3 問題）。
    """
    from src.services import market_regime
    cache = []
    for t in range(125, len(df) - 20):
        f = _build_features_at(df, t)
        if f is None:
            continue
        fb = 0 if pd.isna(f.foreign_buy) else float(f.foreign_buy)
        mg = None if pd.isna(f.m1b_m2_gap) else float(f.m1b_m2_gap)
        mp = None if pd.isna(f.m1b_m2_prev) else float(f.m1b_m2_prev)
        mkt = market_regime(
            index_close=f.close, ma60=f.ma60, ma120=f.ma120,
            foreign_buy=fb, ad_ratio=1.0,
            ma60_prev=f.ma60_prev, ma120_prev=None,
            vol_today=f.vol_today, avg_vol_20=f.avg_vol_20,
            m1b_m2_gap=mg, m1b_m2_prev=mp,
            ma60_above_3d=f.ma60_above_3d, ma60_below_3d=f.ma60_below_3d,
            ma120_above_3d=f.ma120_above_3d, ma120_below_3d=f.ma120_below_3d,
            ma120_rising=f.ma120_rising, ma120_falling=f.ma120_falling,
        )
        cl = ({"inst": {"外資": {"net": fb * 1e8}}}
              if not pd.isna(f.foreign_buy) else None)
        cache.append({
            'date': f.date,
            'close': f.close,
            'ret_20d': _forward_return(df, t, 20),
            'ret_60d': _forward_return(df, t, 60),
            'mkt_info': mkt,
            'jingqi_info': None,
            'cl_data': cl,
            'li_latest': None,
        })
    return cache


def evaluate_thresholds(cache: list[dict], h_thr: int, s_thr: int) -> dict:
    """用 (h_thr, s_thr) 重決所有 cache 行的色，回傳 precision/recall。"""
    from src.compute.macro import calc_traffic_light
    rows = []
    for c in cache:
        tl = calc_traffic_light(
            c['mkt_info'], c['jingqi_info'], c['cl_data'], c['li_latest'],
            health_defense_threshold=h_thr, bull_min_score=s_thr,
        )
        rows.append({
            'date': c['date'],
            'color': tl.get('icon', '?') if tl else '?',
            'regime': tl.get('regime', '') if tl else '',
            'score': float((tl or {}).get('score') or 0),
            'health': float((tl or {}).get('health') or 0),
            'ret_20d': c['ret_20d'],
            'ret_60d': c['ret_60d'],
        })
    bt = pd.DataFrame(rows)
    if bt.empty:
        return {'n_total': 0, 'green_precision': 0.0, 'red_precision': 0.0,
                'green_recall': 0.0, 'red_recall': 0.0,
                'n_green_pred': 0, 'n_red_pred': 0}
    m = compute_metrics(bt)
    return {
        'n_total': m['n_total'],
        'green_precision': m['green_precision'],
        'red_precision': m['red_precision'],
        'green_recall': m['green_recall'],
        'red_recall': m['red_recall'],
        'n_green_pred': m['n_green_pred'],
        'n_red_pred': m['n_red_pred'],
    }


def _f1(precision: float, recall: float) -> float:
    """precision/recall 為百分比（0~100），回 F1（百分比）。"""
    p, r = precision / 100.0, recall / 100.0
    if p + r == 0:
        return 0.0
    return 100.0 * 2 * p * r / (p + r)


def _objective_with_penalty(
    metrics: dict, h_thr: int, s_thr: int,
    h_default: int, s_default: int,
    min_predictions: int = 5,
    penalty_weight: float = 0.5,
) -> float:
    """雙燈號 F1 加總 − 偏離現行門檻的正則項。

    正則：每偏離預設 1 點扣 0.5，避免無理由大幅調整。
    若預測次數 < min_predictions，視為無效（直接 -inf）。
    """
    if metrics['n_red_pred'] < min_predictions and metrics['n_green_pred'] < min_predictions:
        return float('-inf')
    f1_red = _f1(metrics['red_precision'], metrics['red_recall'])
    f1_green = _f1(metrics['green_precision'], metrics['green_recall'])
    deviation = abs(h_thr - h_default) + abs(s_thr - s_default) * 5  # score 1 點權重等於 health 5 點
    return f1_red + f1_green - penalty_weight * deviation


def grid_search_thresholds(
    cache: list[dict],
    h_grid: list[int] | None = None,
    s_grid: list[int] | None = None,
    h_default: int = 35,
    s_default: int = 4,
) -> tuple[int, int, dict]:
    """在 (h, s) 網格上找最大 objective，回 (best_h, best_s, best_metrics)。"""
    if h_grid is None:
        h_grid = list(range(25, 46, 2))   # [25, 27, ..., 45]
    if s_grid is None:
        s_grid = [2, 3, 4, 5]
    best = (-float('inf'), h_default, s_default, None)
    for h in h_grid:
        for s in s_grid:
            m = evaluate_thresholds(cache, h, s)
            score = _objective_with_penalty(m, h, s, h_default, s_default)
            if score > best[0]:
                best = (score, h, s, m)
    return best[1], best[2], best[3] or evaluate_thresholds(cache, h_default, s_default)


def walk_forward_validate(
    df: pd.DataFrame,
    n_folds: int = 4,
    h_default: int = 35,
    s_default: int = 4,
) -> dict:
    """Walk-forward 驗證：滾動切 n_folds 折，每折 train 找最佳、test 報告 OOS。

    回傳 dict：
      - folds: list of {train_period, test_period, train_best, train_metrics,
                        test_metrics, drift_pct}
      - aggregated: 各折 test 指標平均
      - recommended: 穩健門檻（票選 + 衰退過濾）
      - overfit_warning: 是否標警語
    """
    cache = _backtest_with_inputs_cache(df)
    if len(cache) < n_folds * 60:  # 至少每折 60 日
        return {
            'folds': [],
            'aggregated': None,
            'recommended': (h_default, s_default),
            'overfit_warning': False,
            'error': f'cache 樣本 {len(cache)} 不足 {n_folds} 折 × 60 日門檻',
        }

    # 按 cache index 等分（順序滾動，無 shuffle 防 look-ahead）
    n = len(cache)
    fold_size = n // (n_folds + 1)  # 留 1 份當第一折的初始 train
    folds = []
    for k in range(n_folds):
        train_end = (k + 1) * fold_size
        test_end = train_end + fold_size
        if test_end > n:
            break
        train_cache = cache[:train_end]
        test_cache = cache[train_end:test_end]
        if len(train_cache) < 60 or len(test_cache) < 20:
            continue
        # train 找最佳
        best_h, best_s, train_m = grid_search_thresholds(
            train_cache, h_default=h_default, s_default=s_default)
        # test OOS 評分
        test_m = evaluate_thresholds(test_cache, best_h, best_s)
        # 衰退率：以紅燈 F1 為主
        f1_train = _f1(train_m['red_precision'], train_m['red_recall'])
        f1_test = _f1(test_m['red_precision'], test_m['red_recall'])
        drift = (f1_train - f1_test) / max(f1_train, 1e-6) * 100 if f1_train > 0 else 0.0
        folds.append({
            'fold': k + 1,
            'train_start': train_cache[0]['date'].strftime('%Y-%m-%d'),
            'train_end': train_cache[-1]['date'].strftime('%Y-%m-%d'),
            'test_start': test_cache[0]['date'].strftime('%Y-%m-%d'),
            'test_end': test_cache[-1]['date'].strftime('%Y-%m-%d'),
            'best_h': best_h,
            'best_s': best_s,
            'train_red_f1': round(f1_train, 1),
            'test_red_f1': round(f1_test, 1),
            'test_red_precision': test_m['red_precision'],
            'test_red_recall': test_m['red_recall'],
            'test_green_precision': test_m['green_precision'],
            'test_green_recall': test_m['green_recall'],
            'drift_pct': round(drift, 1),
        })

    if not folds:
        return {
            'folds': [],
            'aggregated': None,
            'recommended': (h_default, s_default),
            'overfit_warning': False,
            'error': '所有折皆樣本不足，無法回傳結果',
        }

    # 票選穩健門檻：取最常被選中的 (h, s)
    from collections import Counter
    votes = Counter((f['best_h'], f['best_s']) for f in folds)
    most_common, _vote_count = votes.most_common(1)[0]
    rec_h, rec_s = most_common

    # 衰退過濾：若所有折 drift > 30% → 過擬合警語
    high_drift_count = sum(1 for f in folds if f['drift_pct'] > 30)
    overfit_warning = high_drift_count > len(folds) // 2

    # 若警語觸發，回退到預設門檻
    if overfit_warning:
        rec_h, rec_s = h_default, s_default

    # 各折 test 平均
    agg = {
        'mean_test_red_f1': round(sum(f['test_red_f1'] for f in folds) / len(folds), 1),
        'mean_test_red_precision': round(sum(f['test_red_precision'] for f in folds) / len(folds), 1),
        'mean_test_red_recall': round(sum(f['test_red_recall'] for f in folds) / len(folds), 1),
        'mean_test_green_precision': round(sum(f['test_green_precision'] for f in folds) / len(folds), 1),
        'mean_test_green_recall': round(sum(f['test_green_recall'] for f in folds) / len(folds), 1),
        'mean_drift_pct': round(sum(f['drift_pct'] for f in folds) / len(folds), 1),
    }

    return {
        'folds': folds,
        'aggregated': agg,
        'recommended': (rec_h, rec_s),
        'overfit_warning': overfit_warning,
        'vote_count': _vote_count,
        'total_folds': len(folds),
    }


def build_proposal_report(wf: dict, df_twii: pd.DataFrame, mode: str,
                          h_current: int, s_current: int) -> str:
    """產出 MACRO_CALIBRATION_PROPOSAL.md：walk-forward + 建議門檻 + OOS 數字。"""
    now = _dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    md = []
    md.append('# MACRO_CALIBRATION_PROPOSAL.md — 門檻校準建議')
    md.append('')
    md.append(f'> 自動產生：{now}　|　模式：**{mode}**')
    md.append('')
    md.append(f'- **回測期間**：{df_twii.index[0].date()} ~ {df_twii.index[-1].date()}')
    md.append(f'- **Walk-forward 折數**：{wf.get("total_folds", 0)}')
    md.append('')
    if wf.get('error'):
        md.append(f'> ❌ 校準失敗：{wf["error"]}')
        return '\n'.join(md)

    rec_h, rec_s = wf['recommended']
    md.append('## 🎯 建議門檻 vs 現行')
    md.append('')
    md.append('| 參數 | 現行 | 建議 | 變動 |')
    md.append('|------|------|------|------|')
    md.append(f'| `HEALTH_DEFENSE_THRESHOLD` | {h_current} | **{rec_h}** | {rec_h - h_current:+d} |')
    md.append(f'| `BULL_MIN_SCORE` | {s_current} | **{rec_s}** | {rec_s - s_current:+d} |')
    md.append('')
    if wf['overfit_warning']:
        md.append('> ⚠️ **過擬合警語觸發**：超過半數折 drift > 30%，建議**維持現行門檻不調整**。')
        md.append('> 建議門檻已自動回退到現行值。本報告僅供觀察 walk-forward 結果，**不建議 merge 套用**。')
    elif (rec_h, rec_s) == (h_current, s_current):
        md.append('> ✅ 票選結果與現行門檻一致，**無需調整**。')
    else:
        md.append(f'> 📊 票選結果（{wf.get("vote_count", 0)}/{wf["total_folds"]} 折）建議微調。'
                  '請審閱下方各折 OOS 表現再決定是否 merge。')
    md.append('')

    md.append('## 📈 OOS（測試窗）平均表現')
    md.append('')
    agg = wf['aggregated']
    md.append(f'- 🔴 防禦 F1：**{agg["mean_test_red_f1"]}%** '
              f'（precision {agg["mean_test_red_precision"]}% / recall {agg["mean_test_red_recall"]}%）')
    md.append(f'- 🟢 多頭 precision / recall：**{agg["mean_test_green_precision"]}%** / '
              f'{agg["mean_test_green_recall"]}%')
    md.append(f'- 平均 train→test 衰退：**{agg["mean_drift_pct"]}%**（>30% 即警語）')
    md.append('')

    md.append('## 🔍 各折細節（train→test）')
    md.append('')
    md.append('| 折 | Train 窗 | Test 窗 | best (H, S) | Train F1🔴 | Test F1🔴 | Drift | OOS 🔴 P/R | OOS 🟢 P/R |')
    md.append('|----|----------|---------|-------------|-----------|-----------|-------|------------|------------|')
    for f in wf['folds']:
        md.append(
            f'| {f["fold"]} | {f["train_start"]}~{f["train_end"]} | '
            f'{f["test_start"]}~{f["test_end"]} | ({f["best_h"]}, {f["best_s"]}) | '
            f'{f["train_red_f1"]}% | **{f["test_red_f1"]}%** | {f["drift_pct"]}% | '
            f'{f["test_red_precision"]}%/{f["test_red_recall"]}% | '
            f'{f["test_green_precision"]}%/{f["test_green_recall"]}% |'
        )
    md.append('')
    md.append('---')
    md.append('')
    md.append('## 反過擬合方法')
    md.append('')
    md.append('- **Walk-forward**：滾動切 N 折，每折用前段 train 找門檻、後段 test 報告 OOS（永不在訓練窗自評）')
    md.append('- **正則化**：目標函數含「偏離現行門檻」懲罰項，避免劇烈調整')
    md.append('- **穩健性票選**：取最多折選中的同一組門檻；若衰退中位 > 30% 直接回退預設')
    md.append('- **季度排程**：Actions workflow 每季首日跑一次，commit JSON 後開 PR 給人類審閱')
    md.append('')
    md.append(f'*產生工具：`calibrate_macro_traffic.py --optimize`　|　報告時間：{now}*')
    return '\n'.join(md)


def emit_thresholds_json(rec_h: int, rec_s: int, method: str,
                         path: str = 'macro_thresholds.json') -> bool:
    """寫 macro_thresholds.json；若值未變回 False（避免空 commit）。"""
    import json as _json
    import os as _os
    current = {'HEALTH_DEFENSE_THRESHOLD': 35, 'BULL_MIN_SCORE': 4}
    if _os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                current = _json.load(fp)
        except Exception:
            pass
    if (int(current.get('HEALTH_DEFENSE_THRESHOLD', 35)) == rec_h
            and int(current.get('BULL_MIN_SCORE', 4)) == rec_s):
        return False
    payload = {
        'HEALTH_DEFENSE_THRESHOLD': rec_h,
        'BULL_MIN_SCORE': rec_s,
        'last_calibrated': _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'method': method,
        '_comment': 'By recalibrate_macro Actions workflow. PR-reviewed before applied.',
    }
    with open(path, 'w', encoding='utf-8') as fp:
        _json.dump(payload, fp, indent=2, ensure_ascii=False)
        fp.write('\n')
    return True


# ════════════════════════════════════════════════════════════════
# 報告產生
# ════════════════════════════════════════════════════════════════
def _df_to_md(df: pd.DataFrame, float_fmt: str = "{:.2f}") -> str:
    return df.to_markdown(floatfmt=".2f") if hasattr(df, "to_markdown") \
        else str(df)


def build_report(metrics: dict, df_twii: pd.DataFrame, mode: str) -> str:
    bt = metrics["bt_df"]
    period_start = bt["date"].min().date()
    period_end = bt["date"].max().date()
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 燈號分佈
    color_dist = bt["color"].value_counts().to_dict()
    color_dist_str = " · ".join(f"{c} {n} 日" for c, n in color_dist.items())

    md = []
    md.append("# MACRO_CALIBRATION.md — 台股紅綠燈系統校準報告")
    md.append("")
    md.append(f"> 自動產生：{now}　|　模式：**{mode}**")
    md.append("")
    md.append(f"- **回測期間**：{period_start} ~ {period_end}")
    md.append(f"- **有效樣本**：{metrics['n_total']} 個交易日")
    md.append(f"- **燈號分佈**：{color_dist_str}")
    md.append("")
    # v18.141：TWII-only mode top-banner — 校準是 sandbox 驗證，非 production 真實表現
    if "TWII-only" in mode:
        md.append("> ⚠️ **TWII-only 模式校準警語**：本表僅注入 ^TWII OHLCV，"
                  "外資 / 籌碼 / ADL / 外資期貨 / M1B-M2 / jingqi 全以「中性 0」代入 → "
                  "**score 結構性偏低**（多落在 0~3，難以踩 🟢 多頭門檻 `score≥4`），"
                  "**health 結構性偏低**（多落在 20~36，易踩 🔴 防禦門檻 `<35`） → "
                  "本表代表「校準 pipeline 是否暢通」，**不代表 production 真實表現**"
                  "（production 每日讀數有完整 FinMind 資料，請以 Tab Macro 當下顯示為準）。")
        md.append("")
    md.append("---")
    md.append("")

    # ── (a) 真實 vs 預測勝率 ─────────────────────────────────
    md.append("## (a) 每個燈號的真實 vs 預測勝率")
    md.append("")
    md.append("**真值定義**：")
    md.append(f"- 🔴 高風險命中 = 後 20 日 TWII 跌幅 > {abs(RED_20D_THR)}% "
              f"或 後 60 日跌幅 > {abs(RED_60D_THR)}%")
    md.append(f"- 🟢 多頭命中 = 後 20 日 TWII 漲幅 > {GREEN_20D_THR}%")
    md.append("- 🟡 中性 = 其他")
    md.append("")
    md.append("**勝率指標**：")
    md.append("")
    md.append("| 燈號 | 預測次數 | 真值次數 | Precision (對的%) | Recall (抓到%) | 備註 |")
    md.append("|------|----------|----------|-------------------|----------------|------|")
    md.append(f"| 🟢 多頭 | {metrics['n_green_pred']} | "
              f"{metrics['n_green_truth']} | **{metrics['green_precision']}%** | "
              f"{metrics['green_recall']}% | 預測 🟢 後實際 20 日漲 >5% 比例 |")
    md.append(f"| 🔴 防禦 | {metrics['n_red_pred']} | "
              f"{metrics['n_red_truth']} | **{metrics['red_precision']}%** | "
              f"{metrics['red_recall']}% | 預測 🔴 後實際發生 8% 跌幅比例 |")
    md.append("")
    md.append("**Confusion Matrix**：")
    md.append("")
    md.append("```")
    md.append(str(metrics["confusion_matrix"]))
    md.append("```")
    md.append("")
    md.append("**按燈號分組的後續報酬**（mean / median / count）：")
    md.append("")
    md.append("```")
    md.append(str(metrics["avg_ret_by_color"]))
    md.append("```")
    md.append("")

    # ── (b) 因子相關性矩陣 ───────────────────────────────────
    md.append("## (b) 因子相關性矩陣")
    md.append("")
    md.append("**`mkt_info.score` 與後 N 日報酬的相關係數**：")
    md.append("")
    md.append(f"- score ↔ ret_20d：**{metrics['corr_score_ret20']}**")
    md.append(f"- score ↔ ret_60d：**{metrics['corr_score_ret60']}**")
    md.append("")
    md.append("> 絕對值 > 0.2 視為弱相關，> 0.4 為中等，> 0.6 為強相關。")
    md.append("> 若 corr 接近 0：score 對未來報酬幾乎無預測力，需重新設計分數權重。")
    md.append("")

    # ── (c) 門檻調整建議 ─────────────────────────────────────
    md.append("## (c) 門檻調整建議")
    md.append("")
    # v18.141：動態讀現行門檻，不再寫死「health<40」舊文字
    try:
        from src.compute.macro import (  # noqa: PLC0415
            BULL_MIN_SCORE as _BMS,
            HEALTH_DEFENSE_THRESHOLD as _HDT,
        )
    except Exception:
        _BMS, _HDT = 4, 35
    md.append(f"> 現行門檻（讀自 `macro_helpers`）：🔴 防禦 `health < {_HDT}`、"
              f"🟢 多頭 `regime=='bull' AND score >= {_BMS}`。")
    md.append("")
    # TWII-only 模式：先擺一條共用註記，避免每條建議重複「校準失真」說明
    _twii_only = "TWII-only" in mode
    suggestions = []
    if _twii_only and metrics["n_green_pred"] == 0:
        suggestions.append(
            f"- 🟢 **多頭 0 預測**：TWII-only 模式因子缺失，score 結構性卡在 0~3，"
            f"永遠無法踩 `score >= {_BMS}` → 0 fire。**Production 不受影響**"
            f"（今日讀數 score=4.0/6 仍會踩 🟢）。要看真實多頭命中率，需 NAS 端"
            "batch 抓 365 日 FinMind 歷史後重跑。"
        )
    elif metrics["green_precision"] < 50 and metrics["n_green_pred"] >= 5:
        suggestions.append(
            f"- 🟢 **多頭 precision {metrics['green_precision']}% < 50%**："
            f"現行已要求 `regime=='bull' AND score >= {_BMS}`，仍偏鬆。"
            "可考慮追加「外資連續買超 3 日」或把 score 門檻拉到 5。"
        )
    if metrics["red_precision"] < 40 and metrics["n_red_pred"] >= 5:
        if _twii_only:
            suggestions.append(
                f"- 🔴 **防禦 precision {metrics['red_precision']}% < 40%**："
                f"TWII-only 下 health 結構性偏低，紅燈狂響是模式 artifact 不是規則 bug。"
                f"現行 `health < {_HDT}` 在 production（有完整資料）下表現另計，"
                "本表 precision **不宜直接套用**到 production 規則微調。"
            )
        else:
            suggestions.append(
                f"- 🔴 **防禦 precision {metrics['red_precision']}% < 40%**："
                f"現行 `health < {_HDT}`，可考慮再收緊至 {max(_HDT - 5, 25)}，"
                "或追加「外資連續賣超 3 日」作為門檻共識條件。"
            )
    if metrics["red_recall"] < 30 and metrics["n_red_truth"] >= 5:
        suggestions.append(
            f"- 🔴 **防禦 recall {metrics['red_recall']}% < 30%**："
            "未抓到的大跌事件多。建議放寬 ma120_below_3d 為 ma120_below_2d，"
            "或追加「VIX > 28」作為平行防禦觸發條件。"
        )
    if abs(metrics["corr_score_ret20"]) < 0.1:
        suggestions.append(
            "- ⚠️ **score 對 20d 報酬幾無預測力（|corr| < 0.1）**："
            "目前 score 權重均為 +1 等權，建議改為「MA120 三日 = 2 分、"
            "MA60 三日 = 1 分、外資 = 1 分」（趨勢權重加倍）。"
        )
    if not suggestions:
        suggestions.append(
            "- ✅ 各項指標均達合理範圍（precision > 50%、|corr| > 0.1），"
            "無需立即調整門檻。建議定期（每季）重跑校準確認穩定性。"
        )
    md.extend(suggestions)
    md.append("")

    # ── 限制聲明 ──────────────────────────────────────────────
    md.append("---")
    md.append("")
    md.append("## ⚠️ 樣本不足 / 限制聲明")
    md.append("")
    md.append("- **TWII-only mode**：本次回測僅注入 ^TWII OHLCV 資料，"
              "外資買賣超、ADL、外資期貨、M1B-M2、jingqi 等指標均以「中性預設」"
              "（0 / 1.0 / None）代入。實務上完整版會多 2~3 分 score。")
    md.append("- **FinMind 歷史 quota 限制**：M1B-M2、ADL、外資期貨日 series "
              "目前無歷史 fixture，校準完整版需先在 NAS 端 batch 抓 365 日"
              "歷史並 cache 至本機後重跑。")
    md.append("- **真值定義為單一閾值**：8% / 15% / 5% 為經驗值，未做 OOS 驗證；"
              "若改用 Sharpe / max drawdown 為真值，結論可能不同。")
    md.append("")
    md.append("---")
    md.append(f"*產生工具：`calibrate_macro_traffic.py`　|　"
              f"資料源：^TWII (Yahoo Chart via NAS proxy)　|　"
              f"報告時間：{now}*")
    return "\n".join(md)


# ════════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--range", default="2y",
                   help="^TWII 抓取期間 (yfinance range: 1y/2y/5y/max)")
    p.add_argument("--output", default="MACRO_CALIBRATION.md",
                   help="輸出 Markdown 報告路徑")
    p.add_argument("--demo", action="store_true",
                   help="使用合成資料（NAS proxy 不可達時 fallback）")
    p.add_argument("--use-cache", action="store_true", default=True,
                   help="優先讀 data_cache/twii_ohlcv.parquet + FinMind 欄位（預設開啟）")
    p.add_argument("--no-cache", dest="use_cache", action="store_false",
                   help="強制走 fetch_twii_ohlcv（網路 API）而非 cache")
    p.add_argument("--optimize", action="store_true",
                   help="跑 walk-forward 找最佳門檻（用於季度排程）")
    p.add_argument("--n-folds", type=int, default=4,
                   help="walk-forward 折數（預設 4）")
    p.add_argument("--emit-json", default=None,
                   help="把建議門檻寫到 JSON 檔（預設 macro_thresholds.json）")
    p.add_argument("--emit-proposal", default=None,
                   help="把 walk-forward 報告寫到 .md（預設 MACRO_CALIBRATION_PROPOSAL.md）")
    args = p.parse_args()

    mode_label = "TWII-only (歷史 fixture 缺)"
    df: Optional[pd.DataFrame] = None
    if args.demo:
        print("[calibrate] [DEMO] 產生合成 ^TWII 500 日 ...")
        df = synthetic_twii_ohlcv()
        mode_label = "TWII-only · DEMO 合成資料 (sandbox 用)"
    elif args.use_cache:
        _yrs_map = {"1y": 1, "2y": 2, "5y": 5, "max": 10}
        _years = _yrs_map.get(args.range, 5)
        df = load_from_cache(years=_years)
        if df is None:
            print("[calibrate] cache 缺檔，fallback 抓 fetch_twii_ohlcv")
        else:
            mode_label = f"Cache enriched (TWII + FinMind 籌碼/M1M2, {_years}y)"
    if df is None and not args.demo:
        print(f"[calibrate] 抓 ^TWII range={args.range} ...")
        df = fetch_twii_ohlcv(args.range)
        if df is None or df.empty:
            print("[calibrate] ⚠️  抓不到 ^TWII（NAS proxy 不可達），"
                  "自動 fallback 至 DEMO 合成資料模式")
            df = synthetic_twii_ohlcv()
            mode_label = "TWII-only · DEMO 合成資料 (proxy fallback)"
    print(f"[calibrate] ✅ ^TWII {len(df)} 筆 ({df.index[0].date()} ~ {df.index[-1].date()})")

    print("[calibrate] 逐日重建燈號中 ...")
    bt = run_backtest(df)
    print(f"[calibrate] ✅ 有效樣本 {len(bt)} 日")

    print("[calibrate] 計算 precision/recall/confusion matrix ...")
    metrics = compute_metrics(bt)
    print(f"  🟢 預測 {metrics['n_green_pred']} 次 (precision={metrics['green_precision']}%)")
    print(f"  🔴 預測 {metrics['n_red_pred']} 次 (precision={metrics['red_precision']}%)")
    print(f"  score↔ret_20d corr = {metrics['corr_score_ret20']}")

    print(f"[calibrate] 產出報告 → {args.output}")
    report = build_report(metrics, df, mode=mode_label)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print("[calibrate] ✅ 完成")

    # ── --optimize：walk-forward 找最佳門檻 + 寫 proposal/json ──
    if args.optimize:
        from src.compute.macro import HEALTH_DEFENSE_THRESHOLD as _H_CUR, BULL_MIN_SCORE as _S_CUR
        print(f"[calibrate] 跑 walk-forward 驗證（{args.n_folds} 折）...")
        wf = walk_forward_validate(df, n_folds=args.n_folds,
                                   h_default=_H_CUR, s_default=_S_CUR)
        if wf.get('error'):
            print(f"[calibrate/optimize] ❌ {wf['error']}")
        else:
            rec_h, rec_s = wf['recommended']
            print(f"[calibrate/optimize] 建議：H={rec_h} (現行 {_H_CUR})、S={rec_s} (現行 {_S_CUR})")
            if wf['overfit_warning']:
                print("[calibrate/optimize] ⚠️ 過擬合警語，建議維持現行")

            proposal_path = args.emit_proposal or 'MACRO_CALIBRATION_PROPOSAL.md'
            with open(proposal_path, 'w', encoding='utf-8') as fp:
                fp.write(build_proposal_report(
                    wf, df, mode=mode_label,
                    h_current=_H_CUR, s_current=_S_CUR))
            print(f"[calibrate/optimize] ✅ proposal → {proposal_path}")

            if args.emit_json is not None:
                json_path = args.emit_json or 'macro_thresholds.json'
                changed = emit_thresholds_json(
                    rec_h, rec_s,
                    method=f'walk-forward {args.n_folds} folds ({mode_label})',
                    path=json_path)
                if changed:
                    print(f"[calibrate/optimize] ✅ JSON 寫入 → {json_path}")
                else:
                    print("[calibrate/optimize] ↺ JSON 無變動，跳過寫入")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
