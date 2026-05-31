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
    return _Features(
        date=pd.Timestamp(sub.index[-1]),
        close=cur, ma60=ma60, ma120=ma120,
        ma60_above_3d=ma60_above_3d, ma60_below_3d=ma60_below_3d,
        ma120_above_3d=ma120_above_3d, ma120_below_3d=ma120_below_3d,
        ma120_rising=ma120_rising, ma120_falling=ma120_falling,
        ma60_prev=ma60_prev, vol_today=vol_today, avg_vol_20=avg_vol,
    )


def _features_to_traffic_light(f: _Features) -> dict:
    """以特徵組成 mkt_info → 呼叫 calc_traffic_light（TWII-only 中性外資/籌碼）。"""
    from market_strategy import market_regime
    from macro_helpers import calc_traffic_light
    mkt = market_regime(
        index_close=f.close, ma60=f.ma60, ma120=f.ma120,
        foreign_buy=0, ad_ratio=1.0,  # TWII-only mode：中性值
        ma60_prev=f.ma60_prev, ma120_prev=None,
        vol_today=f.vol_today, avg_vol_20=f.avg_vol_20,
        m1b_m2_gap=None, m1b_m2_prev=None,
        ma60_above_3d=f.ma60_above_3d, ma60_below_3d=f.ma60_below_3d,
        ma120_above_3d=f.ma120_above_3d, ma120_below_3d=f.ma120_below_3d,
        ma120_rising=f.ma120_rising, ma120_falling=f.ma120_falling,
    )
    tl = calc_traffic_light(mkt_info=mkt, jingqi_info=None,
                            cl_data=None, li_latest=None)
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
    md.append(f"# MACRO_CALIBRATION.md — 台股紅綠燈系統校準報告")
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
    md.append(f"- 🟡 中性 = 其他")
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
        from macro_helpers import (  # noqa: PLC0415
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
            f"- ⚠️ **score 對 20d 報酬幾無預測力（|corr| < 0.1）**："
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
    md.append(f"- **TWII-only mode**：本次回測僅注入 ^TWII OHLCV 資料，"
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
    args = p.parse_args()

    mode_label = "TWII-only (歷史 fixture 缺)"
    df: Optional[pd.DataFrame]
    if args.demo:
        print(f"[calibrate] [DEMO] 產生合成 ^TWII 500 日 ...")
        df = synthetic_twii_ohlcv()
        mode_label = "TWII-only · DEMO 合成資料 (sandbox 用)"
    else:
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
    print(f"[calibrate] ✅ 完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
