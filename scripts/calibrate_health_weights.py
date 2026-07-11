"""scripts/calibrate_health_weights.py — 紅綠燈健康評分權重「離線校準」CLI (v19.93 Phase 2).

方法論定案 `MACRO_HEALTH_REWEIGHT_PROPOSAL.md`（user 核准 Path 1）。本 script 是 Phase 2
「wiring」:讀 `data_cache/` 真實歷史 parquet → 重建 3 特徵（jqavg / score_norm / fnet）
+ 20 日回撤風險姿態真值 → walk-forward L2-logistic 擬權重 → 寫 `MACRO_HEALTH_WEIGHT_PROPOSAL.md`
給人審。**不直接改 SSOT 常數**（Phase 3 人審後才改 signal_thresholds）。

⚠️ 真實資料在**部署 cron**（沙箱無 `twii_ohlcv.parquet` + egress 擋）;本 script 的純函式
（`_prep_close` / `reconstruct_score` / `build_feature_frame` / `render_proposal`）由
`tests/test_calibrate_health_weights.py` 以合成 df 單測,`main()` 的 parquet I/O 走部署環境。

架構（§8.2）:scripts 層 orchestrator,可同時 import L2（`health_calibration`）+ L3
（`market_strategy.market_regime`）。score 重建含 L3 呼叫,故置於本 script 而非 L2（L2 不得 import L3）。
score_norm = score / max_score × 100（用真 max_score 4/6,**修正 health 原本除以 5 的錯配**,對齊 ③）。

資料來源（`scripts/update_macro_history.py` 產出）:
- `twii_ohlcv.parquet`  : date / open / high / low / close / volume
- `finmind_inst.parquet`: date / foreign_buy（**億**,外資淨買賣超;score 只看正負號,單位不影響）
- `finmind_m1m2.parquet`: date / m1b / m2 / m1b_m2_gap（月頻,百分點）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.compute.macro.health_calibration import (  # noqa: E402
    ad_ratio_from_twii,
    breadth_from_twii,
    fit_health_weights,
    risk_posture_label,
)
from src.services.market_strategy import market_regime  # noqa: E402

_CACHE = _REPO / "data_cache"
_FEATURES = ["jqavg", "score_norm", "fnet"]
# PIT 對齊容差（§2.3）:外資 T+1（給 7d 容納連假）、m1b_m2 月頻 backward 40d
_INST_TOLERANCE = pd.Timedelta("7D")
_M1M2_TOLERANCE = pd.Timedelta("40D")


def _prep_close(twii_df: pd.DataFrame) -> pd.Series:
    """twii_ohlcv df → 收盤 Series（DatetimeIndex 升序、去重、float）。"""
    s = twii_df[["date", "close"]].copy()
    s["date"] = pd.to_datetime(s["date"])
    s = (s.dropna(subset=["close"]).drop_duplicates("date", keep="last")
         .sort_values("date").set_index("date")["close"].astype(float))
    return s


def _ma_flags(close: pd.Series, window: int) -> dict:
    """回傳每日 above_3d / below_3d / rising / falling 布林序列 + ma / ma_prev。

    連 3 日站上/跌破 = `(close vs ma)` 布林的 3 日滾動和 == 3（對齊 market_regime hysteresis）。
    """
    ma = close.rolling(window).mean()
    above_3d = (close > ma).rolling(3).sum() == 3
    below_3d = (close < ma).rolling(3).sum() == 3
    return {
        "ma": ma, "ma_prev": ma.shift(1),
        "above_3d": above_3d, "below_3d": below_3d,
        "rising": ma > ma.shift(1), "falling": ma < ma.shift(1),
    }


def _opt(s: pd.Series, dt) -> float | None:
    """對齊序列取值 → float | None（NaN/缺 → None，供 market_regime 選填參數）。"""
    v = s.get(dt)
    return float(v) if v is not None and pd.notna(v) else None


def reconstruct_score(close: pd.Series, inst_df: pd.DataFrame,
                      m1m2_df: pd.DataFrame) -> pd.DataFrame:
    """逐日呼叫**真** `market_regime`（SSOT parity）重建 score / max_score / score_norm / fnet。

    PIT-safe（§2.3）:外資 backward merge（T+1、無 lookahead）、m1b_m2 月頻 backward 40d。
    僅在 MA120 有效（≥120 日歷史）的日子評分,不足者 score_norm=NaN（訓練 drop）。
    回傳 index=close.index 的 DataFrame。
    """
    adr = ad_ratio_from_twii(close)          # 日 ad_ratio（market_regime ④ 用）
    f60, f120 = _ma_flags(close, 60), _ma_flags(close, 120)

    inst = inst_df[["date", "foreign_buy"]].copy()
    inst["date"] = pd.to_datetime(inst["date"])
    inst = inst.dropna(subset=["foreign_buy"]).sort_values("date")
    fnet = pd.merge_asof(
        pd.DataFrame({"date": close.index}), inst,
        on="date", direction="backward", tolerance=_INST_TOLERANCE,
    ).set_index("date")["foreign_buy"]

    m = m1m2_df[["date", "m1b_m2_gap"]].copy()
    m["date"] = pd.to_datetime(m["date"])
    m = m.dropna(subset=["m1b_m2_gap"]).sort_values("date")
    m["gap_prev"] = m["m1b_m2_gap"].shift(1)          # 上一（月）期 gap
    gapdf = pd.merge_asof(
        pd.DataFrame({"date": close.index}), m,
        on="date", direction="backward", tolerance=_M1M2_TOLERANCE,
    ).set_index("date")

    rows = []
    for dt in close.index:
        ma120 = f120["ma"].get(dt)
        if ma120 is None or pd.isna(ma120):
            rows.append({"date": dt, "score": np.nan, "max_score": np.nan,
                         "score_norm": np.nan, "fnet": _opt(fnet, dt)})
            continue
        r = market_regime(
            index_close=float(close[dt]),
            ma60=float(f60["ma"][dt]), ma120=float(ma120),
            foreign_buy=_opt(fnet, dt), ad_ratio=_opt(adr, dt),
            ma60_prev=_opt(f60["ma_prev"], dt), ma120_prev=_opt(f120["ma_prev"], dt),
            m1b_m2_gap=_opt(gapdf["m1b_m2_gap"], dt), m1b_m2_prev=_opt(gapdf["gap_prev"], dt),
            ma60_above_3d=bool(f60["above_3d"].get(dt, False)),
            ma60_below_3d=bool(f60["below_3d"].get(dt, False)),
            ma120_above_3d=bool(f120["above_3d"].get(dt, False)),
            ma120_below_3d=bool(f120["below_3d"].get(dt, False)),
            ma120_rising=bool(f120["rising"].get(dt, False)),
            ma120_falling=bool(f120["falling"].get(dt, False)),
        )
        sc, mx = float(r["score"]), float(r["max_score"])
        rows.append({
            "date": dt, "score": sc, "max_score": mx,
            # score_norm 用真 max_score（4/6）→ 修 health 原本 /5 的錯配（對齊 ③）
            "score_norm": min(sc / mx * 100.0, 100.0) if mx > 0 else np.nan,
            "fnet": _opt(fnet, dt),
        })
    return pd.DataFrame(rows).set_index("date")


def build_feature_frame(twii_df: pd.DataFrame, inst_df: pd.DataFrame,
                        m1m2_df: pd.DataFrame) -> pd.DataFrame:
    """組出對齊的特徵表 [jqavg, score_norm, fnet, y]（含頭尾 NaN,fit 內部 drop）。"""
    close = _prep_close(twii_df)
    jqavg = breadth_from_twii(close)                 # 5 日均廣度
    y = risk_posture_label(close)                    # 20 日回撤真值
    sc = reconstruct_score(close, inst_df, m1m2_df)
    return pd.DataFrame({
        "jqavg": jqavg, "score_norm": sc["score_norm"], "fnet": sc["fnet"], "y": y,
    })


def run_calibration(feat: pd.DataFrame) -> dict:
    """對特徵表跑 walk-forward L2-logistic（資料不足 → fit_health_weights raise，§1）。"""
    clean = feat.dropna(subset=[*_FEATURES, "y"])
    X = clean[_FEATURES].to_numpy(dtype=float)
    y = clean["y"].to_numpy(dtype=float)
    return fit_health_weights(X, y, feature_names=_FEATURES)


def render_proposal(result: dict, feat: pd.DataFrame) -> str:
    """把擬合結果格式化成人審用 Markdown（**不改任何 SSOT 常數**）。"""
    w = result["weights_raw"]
    cv = result["cv"]
    span = feat.dropna(subset=["y"]).index
    date_range = (f"{span.min().date()} ~ {span.max().date()}" if len(span) else "—")
    auc = cv.get("mean_val_auc")
    ll = cv.get("mean_val_log_loss")
    return (
        "# 紅綠燈健康評分權重 — 校準提案（自動產生，待人審）\n\n"
        "> 由 `scripts/calibrate_health_weights.py` 產出。方法論見 `MACRO_HEALTH_REWEIGHT_PROPOSAL.md`。\n"
        "> **本檔僅為提案,未改任何 code / SSOT 常數**;Phase 3 人審後才手動改 `signal_thresholds`。\n\n"
        f"- 樣本區間: {date_range}（labeled n={result['n_samples']}）\n"
        f"- 正例（該防禦）比例: {result['class_balance']:.1%}\n"
        f"- 選定 λ（L2）: {result['lambda_selected']}\n"
        f"- 交叉驗證 val AUC: {auc:.3f}" + (f" / log-loss: {ll:.4f}\n" if ll is not None else "\n")
        + f"- 穩健性 fold 權重相對方差: {result['robustness']['fold_weight_rel_var']:.3f}"
        f"（sign_flip={result['robustness']['sign_flip']}）\n"
        f"- ⚠️ overfit_flag: **{result['overfit_flag']}**"
        "（True = 跨 fold 不穩,**勿貿然採納**）\n\n"
        "## 擬合權重（raw 特徵空間 → 對照現行 0.4 / 0.4 / +20）\n\n"
        "| 特徵 | 擬合權重 | 現行 |\n|---|---|---|\n"
        f"| jqavg | {w['jqavg']:+.4f} | 0.40 |\n"
        f"| score_norm | {w['score_norm']:+.4f} | 0.40 |\n"
        f"| fnet | {w['fnet']:+.6f} | +20（sign-only）|\n"
        f"| intercept | {result['intercept_raw']:+.4f} | — |\n\n"
        "## 人審檢查點（Phase 3 才動 code）\n"
        "1. AUC 是否顯著 > 0.5？overfit_flag 是否 False？否則**不採納**。\n"
        "2. 權重方向是否合理（低廣度→該防禦 = jqavg 負向）？\n"
        "3. 若採納:改 `shared/signal_thresholds` 的 `HEALTH_WEIGHT_JQ` / `HEALTH_WEIGHT_SCORE` /\n"
        "   `HEALTH_FNET_BONUS` + 修 `CONFIDENCE_SOURCE_COUNT` 除數錯配,附本提案為 PR 證據。\n"
        "4. ⚠️ 資料為 ^TWII proxy 廣度 + 本地重建 score;若日後接精確漲跌家數需重跑。\n"
    )


def main() -> None:
    missing = [n for n in ("twii_ohlcv", "finmind_inst", "finmind_m1m2")
               if not (_CACHE / f"{n}.parquet").exists()]
    if missing:
        # §1 Fail Loud:缺真實資料就炸,不用合成資料擬合偽權重
        raise SystemExit(
            f"[calibrate] ❌ 缺 parquet: {missing} — 請先於部署環境跑 "
            f"scripts/update_macro_history.py（沙箱無此資料、egress 被擋）"
        )
    twii = pd.read_parquet(_CACHE / "twii_ohlcv.parquet")
    inst = pd.read_parquet(_CACHE / "finmind_inst.parquet")
    m1m2 = pd.read_parquet(_CACHE / "finmind_m1m2.parquet")
    feat = build_feature_frame(twii, inst, m1m2)
    result = run_calibration(feat)
    md = render_proposal(result, feat)
    out = _REPO / "MACRO_HEALTH_WEIGHT_PROPOSAL.md"
    out.write_text(md, encoding="utf-8")
    print(f"[calibrate] ✅ 寫入 {out}（overfit_flag={result['overfit_flag']}）")
    print(md)


if __name__ == "__main__":
    main()
