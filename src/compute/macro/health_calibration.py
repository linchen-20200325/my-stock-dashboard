"""src/compute/macro/health_calibration.py — 紅綠燈健康評分權重「離線校準」L2 純函式 (v19.92).

方法論定案見 `MACRO_HEALTH_REWEIGHT_PROPOSAL.md`。
User 決策(AskUserQuestion)：①風險姿態 ②20日 ③現 3 輸入(jqavg/score/fnet) ④建管線 + 數學式照定義。

§8.2 L2 純函式：**無 I/O、無 streamlit、無 requests**（只 numpy + pandas）。三個演算法：
- `breadth_from_twii()` — 由 ^TWII 日 K 重建 jqavg（live jqavg 的 PROXY tier）。
  ⚠️ **不是** live `fetch_adl` 的鏡像,見下方 `ad_ratio_from_twii` 的 parity 警語。
- `risk_posture_label()` — 未來 20 交易日最大回撤 → 風險姿態真值 y∈{0,1}（1=該防禦）。
- `fit_health_weights()` — walk-forward L2-logistic（**純 numpy，不引 sklearn/scipy**）擬 3 權重
  + robustness voting + overfit guard。資料不足 → raise（§1 fail loud，不回偽權重）。

「跑真實資料 → 產出提案權重」在 `scripts/` + 部署 cron；本層只提供**可單測的演算法**。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ── domain-local SSOT 常數（同 etf_margin_simulator 先例：單功能常數 domain-local，
#    不外移 shared/ — §-1 避免多餘抽象。若未來他模組共用再升格）──────────────
# jqavg 重建：對齊 live fetch_adl ① 的「漲跌幅 ±1% ≈ ±150 家、900 基準」係數
# + jingqi_calc 的 tail(5).mean 視窗。
#
# ⚠️ **係數相同不等於同一個變數** —— 見 `ad_ratio_from_twii` 的 parity 警語:
#    兩者餵進公式的「漲跌幅」定義不同（日內 vs 收對收），clip 方式也不同。
BREADTH_BASE_COUNT = 900.0        # 家/側（漲家、跌家各以 900 為基準）
BREADTH_PCT_TO_COUNT = 150.0      # 每 1% 漲跌幅 ≈ ±150 家
JQAVG_ROLLING_DAYS = 5            # jingqi_calc tail(5).mean

# 風險姿態真值：未來 20 交易日最大回撤 ≥ θ_dd 即「該防禦」
RISK_POSTURE_HORIZON_DAYS = 20        # 對齊 user ② 20 交易日
RISK_POSTURE_MDD_THRESHOLD_PCT = 8.0  # θ_dd 預設（對齊既有 RED_20D_THR 精神；待 OOS 驗證）

# 擬合 guard
HEALTH_FIT_MIN_SAMPLES = 60       # labeled 樣本下限；不足即 raise（§1）
HEALTH_FIT_MIN_FOLDS = 3          # walk-forward fold 下限
HEALTH_FIT_OVERFIT_DRIFT = 0.30   # 跨 fold 權重相對方差 > 此 → overfit flag


def ad_ratio_from_twii(twii_close: pd.Series) -> pd.Series:
    """由 ^TWII **收盤對收盤**報酬重建日 ad_ratio proxy。

        r%      = close.pct_change() × 100          ← **收對收**
        up      = clip(900 + 150·r, ≥0)
        down    = clip(900 − 150·r, ≥0)
        ad_ratio = up / (up + down) × 100          （total=0 → NaN，不偽造）

    ⚠️ **與線上不是同一個變數（parity 警語,2026-08-19 稽核更正）**
    ------------------------------------------------------------------
    本函式的 docstring 原本寫「鏡像 `fetch_adl` ①」「SSOT parity」——**不實**。
    線上 `src/data/daily/daily_data_fetchers.fetch_adl` 實際算的是:

        p       = (close − open) / open             ← **日內**,非收對收
        up      = clip(int(900 + p·15000), 50, 1750)
        down    = max(50, 1800 − up)                ← 分母恆為 1800
        ad_ratio = up / 1800 × 100 = 50 + 8.333 × 日內漲跌%

    **每 1% ≈ ±150 家這個係數兩邊相同**（150 vs 15000×0.01），所以乍看像鏡像。
    真正的差異有兩處,而且都不小:

      (1) **報酬定義**:日內 `(close−open)/open` vs 收對收 `pct_change()`。
          兩者是不同的隨機變數 —— 實測 2006-2026 全樣本:日內平均報酬
          **−0.047%/日**、隔夜跳空 **+0.094%/日**。TWII 二十年的正報酬幾乎
          全部來自隔夜,而線上公式恰好只取沒有 drift 的那一半。
          兩序列 corr ≈ 0.79,對 ">50" 的判定有 **20.25% 的日子相反**。
      (2) **clip 方式**:線上對 up 做 clip(50,1750) 且 down = 1800−up ⇒ 分母
          **恆為 1800**;本函式對 up/down 各自 clip(lower=0) ⇒ 分母會變動。

    **後果（影響權重的證據等級,見 shared/signal_thresholds.HEALTH_WEIGHT_JQ）**:
    `scripts/calibrate_health_weights.reconstruct_score` 呼叫的是本函式,所以
    v19.102 擬合出的 `HEALTH_WEIGHT_JQ = 0.6` 是在**收對收版本**上取得的,
    套用在線上的**日內版本**尚未經過驗證。

    保留本函式的收對收定義而不逕改為日內,是因為 `tests/test_health_calibration.py`
    以 `pd.Series([100*(1.01**i)])` 釘死了本公式的數值,且 v19.102 已採納的權重
    以此為擬合基礎 —— 逕改數學會讓那組權重失去其唯一的實證依據。
    要收斂應走「重跑校準」而非「改動歷史基準」(見 scripts/calibrate_macro_traffic.py)。

    market_regime ④ 市場廣度用**日** ad_ratio；health 的 jqavg 是其 5 日均
    （見 `breadth_from_twii`）。第 1 列因 pct_change=NaN → ad_ratio=NaN。
    空輸入 → 空 Series。
    """
    if twii_close is None or len(twii_close) == 0:
        return pd.Series(dtype=float)
    close = pd.Series(twii_close, dtype=float)
    r_pct = close.pct_change() * 100.0
    up = (BREADTH_BASE_COUNT + BREADTH_PCT_TO_COUNT * r_pct).clip(lower=0.0)
    down = (BREADTH_BASE_COUNT - BREADTH_PCT_TO_COUNT * r_pct).clip(lower=0.0)
    total = up + down
    # total=0（極端雙邊 clip）→ NaN；否則 up 佔比 ×100
    return pd.Series(
        np.where(total.to_numpy() > 0, up.to_numpy() / total.to_numpy() * 100.0, np.nan),
        index=close.index,
    )


# ── live parity 重建（2026-08-19 新增,PR-2）────────────────────────────────
# 上面兩個 *_from_twii 是「收對收」版本(v19.102 權重的擬合基準,不可改動)。
# 下面兩個是**與線上 `fetch_adl` 逐位等價**的日內版本,給校準管線用 ——
# 讓「校準的 health」與「線上的 health」終於是同一個變數。
LIVE_UP_BASE = 900              # fetch_adl:900 基準
LIVE_PCT_TO_COUNT = 15000       # fetch_adl:pct(ratio) × 15000,即每 1% ±150 家
LIVE_UP_MIN, LIVE_UP_MAX = 50, 1750   # fetch_adl:clip(50, 1750)
LIVE_TOTAL = 1800               # down = max(50, 1800 − up);因 up ≤ 1750 故分母恆 1800


def ad_ratio_live_parity(twii_open: pd.Series, twii_close: pd.Series) -> pd.Series:
    """與線上 `fetch_adl` **逐位等價**的日 ad_ratio 重建（日內口徑）。

    逐字對照 `src/data/daily/daily_data_fetchers.fetch_adl`::

        _pct = (_cl - _op) / _op
        _up  = max(50, min(1750, int(900 + _pct * 15000)))
        rows[_dk] = {'up': _up, 'down': max(50, 1800 - _up)}
        df['ad_ratio'] = (up / (up + down) * 100).round(1)

    三個必須逐位複製的細節（漏任一個就不是 parity,只是「很像」）:
      1. **`int()` 截斷**（不是四捨五入）—— 直接影響 ad_ratio 的最後一位。
      2. `clip(50, 1750)` 只作用在 up;`down = max(50, 1800-up)` 的 max 因
         `up ≤ 1750` 而**永不生效** ⇒ 分母恆為 1800。
      3. 出口 `.round(1)`。

    與 `ad_ratio_from_twii`（收對收）的差異、以及為何兩者不可混用,
    見該函式的 parity 警語。

    Args:
        twii_open / twii_close: 同 index 的開盤/收盤序列。

    Returns:
        pd.Series（同 index）。open ≤ 0 或缺值 → NaN（§1 不偽造）。
    """
    if twii_open is None or twii_close is None or len(twii_close) == 0:
        return pd.Series(dtype=float)
    op = pd.Series(twii_open, dtype=float)
    cl = pd.Series(twii_close, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(op.to_numpy() > 0,
                       (cl.to_numpy() - op.to_numpy()) / op.to_numpy(),
                       np.nan)
    raw = LIVE_UP_BASE + pct * LIVE_PCT_TO_COUNT
    # int() 截斷:np.trunc 對正負皆向零取整,與 Python int() 一致
    up = np.clip(np.trunc(raw), LIVE_UP_MIN, LIVE_UP_MAX)
    ratio = np.where(np.isnan(pct), np.nan,
                     np.round(up / LIVE_TOTAL * 100.0, 1))
    return pd.Series(ratio, index=cl.index)


def breadth_live_parity(twii_open: pd.Series, twii_close: pd.Series) -> pd.Series:
    """`ad_ratio_live_parity` 的 5 日移動平均 = 與線上等價的 jqavg（旌旗指數）。"""
    ar = ad_ratio_live_parity(twii_open, twii_close)
    if ar.empty:
        return ar
    return ar.rolling(JQAVG_ROLLING_DAYS).mean()


def breadth_from_twii(twii_close: pd.Series) -> pd.Series:
    """由 ^TWII 收盤序列重建 jqavg（大盤廣度 proxy）。

    jqavg = 日 ad_ratio 的 5 日移動平均（視窗對齊 `jingqi_calc` 的 tail(5).mean）。
    此為 live jqavg 的 PROXY tier。

    ⚠️ **視窗相同,但底層 ad_ratio 與線上不同源** —— 見 `ad_ratio_from_twii`
    的 parity 警語（日內 vs 收對收,corl≈0.79、判定 20.25% 相反）。

    Parameters
    ----------
    twii_close : pd.Series
        ^TWII 收盤價（DatetimeIndex 升序）。

    Returns
    -------
    pd.Series
        與輸入同 index 的 jqavg（前 ~5 日因均線不足 → NaN，**不 ffill**）。
        空輸入 → 空 Series。
    """
    ar = ad_ratio_from_twii(twii_close)
    if ar.empty:
        return ar
    return ar.rolling(JQAVG_ROLLING_DAYS).mean()


def risk_posture_label(
    twii_close: pd.Series,
    *,
    theta_dd_pct: float = RISK_POSTURE_MDD_THRESHOLD_PCT,
    horizon: int = RISK_POSTURE_HORIZON_DAYS,
) -> pd.Series:
    """未來 `horizon` 交易日最大回撤 → 風險姿態真值 y_t ∈ {0,1}（1=該防禦）。

        MDD_t = max_{t<k≤t+h} ( (max_{t≤j≤k} C_j − C_k) / max_{t≤j≤k} C_j )
        y_t   = 1  if MDD_t·100 ≥ θ_dd   else 0

    尾端不足 `horizon` 的列 → NaN（無法標記，訓練時 drop；§1 不偽造）。
    複雜度 O(n·h)，h=20 對日頻資料可忽略。
    """
    if twii_close is None or len(twii_close) == 0:
        return pd.Series(dtype=float)
    if horizon < 1:
        raise ValueError(f"horizon 必須 ≥1，收到 {horizon}")
    close = pd.Series(twii_close, dtype=float)
    C = close.to_numpy(dtype=float)
    n = len(C)
    y = np.full(n, np.nan)
    for t in range(n):
        end = t + horizon
        if end >= n:
            break  # 尾端不足 horizon → 保持 NaN
        window = C[t:end + 1]              # C[t .. t+h]
        run_peak = np.maximum.accumulate(window)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.where(run_peak > 0, (run_peak - window) / run_peak, 0.0)
        mdd = float(dd[1:].max())          # 未來 1..h 的最大回撤（不含 t 自身 dd=0）
        y[t] = 1.0 if mdd * 100.0 >= theta_dd_pct else 0.0
    return pd.Series(y, index=close.index)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    """數值穩定 sigmoid。"""
    z = np.clip(z, -500.0, 500.0)
    return 1.0 / (1.0 + np.exp(-z))


def _fit_logistic_l2(
    Xs: np.ndarray, y: np.ndarray, lam: float, *, iters: int = 800, lr: float = 0.3
) -> tuple[np.ndarray, float]:
    """標準化特徵上的 L2-logistic（純 numpy 梯度下降）。回傳 (w, b)。

    L2 只罰權重不罰截距。梯度：∂/∂w = Xᵀ(p−y)/n + λw；∂/∂b = mean(p−y)。
    """
    n, k = Xs.shape
    w = np.zeros(k, dtype=float)
    b = 0.0
    for _ in range(iters):
        p = _sigmoid(Xs @ w + b)
        err = p - y
        gw = Xs.T @ err / n + lam * w
        gb = float(np.mean(err))
        w -= lr * gw
        b -= lr * gb
    return w, b


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    """平均二元交叉熵（clip 防 log(0)）。"""
    eps = 1e-12
    p = np.clip(p, eps, 1.0 - eps)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def fit_health_weights(
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray | pd.Series,
    *,
    feature_names: list[str] | None = None,
    n_folds: int = 5,
    lambda_grid: tuple[float, ...] = (0.0, 0.01, 0.1, 1.0, 10.0),
) -> dict:
    """walk-forward L2-logistic 擬健康評分權重（純 numpy）。

    Parameters
    ----------
    X : (n, k) 特徵矩陣（欄序建議 [jqavg, score_norm, fnet]）。
    y : (n,) 風險姿態真值 ∈ {0,1}。
    feature_names : 欄名（診斷用）。
    n_folds : walk-forward 展開窗數。
    lambda_grid : L2 強度候選（inner-CV 選）。

    Returns
    -------
    dict
        `weights_raw`(映回原特徵空間 dict) / `weights_std` / `intercept_std` /
        `lambda_selected` / `n_samples` / `class_balance` /
        `cv`(per-fold val log-loss/auc) / `robustness`(跨 fold 權重相對方差) /
        `overfit_flag`(bool)。

    Raises
    ------
    ValueError
        labeled 樣本 < HEALTH_FIT_MIN_SAMPLES，或有效 fold < HEALTH_FIT_MIN_FOLDS，
        或單一類別（全 0 / 全 1）— §1 fail loud，不回偽權重。
    """
    Xarr = X.to_numpy(dtype=float) if isinstance(X, pd.DataFrame) else np.asarray(X, dtype=float)
    yarr = y.to_numpy(dtype=float) if isinstance(y, pd.Series) else np.asarray(y, dtype=float)
    if feature_names is None:
        if isinstance(X, pd.DataFrame):
            feature_names = list(X.columns)
        else:
            feature_names = [f"x{i}" for i in range(Xarr.shape[1])]

    # 去 NaN（特徵或標籤缺 → drop，§1 不填補）
    mask = ~(np.isnan(Xarr).any(axis=1) | np.isnan(yarr))
    Xarr, yarr = Xarr[mask], yarr[mask]
    n = len(yarr)
    if n < HEALTH_FIT_MIN_SAMPLES:
        raise ValueError(
            f"labeled 樣本 {n} < 下限 {HEALTH_FIT_MIN_SAMPLES}（§1：資料不足不擬合偽權重）"
        )
    pos = float(yarr.sum())
    if pos == 0.0 or pos == n:
        raise ValueError(
            f"單一類別（正例 {pos:.0f}/{n}）無法擬 logistic；請放寬 θ_dd 或延長歷史（§1）"
        )

    # 標準化（用全樣本統計；std=0 欄 → 該欄置 0 特徵，避免 ÷0）
    mu = Xarr.mean(axis=0)
    sigma = Xarr.std(axis=0)
    sigma_safe = np.where(sigma > 0, sigma, 1.0)
    Xs = (Xarr - mu) / sigma_safe

    # walk-forward 展開窗：train=[0,split_i) / val=[split_i,split_{i+1})
    bounds = np.linspace(0, n, n_folds + 1, dtype=int)
    fold_val_loss: dict[float, list[float]] = {lam: [] for lam in lambda_grid}
    fold_weights: list[np.ndarray] = []
    aucs: list[float] = []
    valid_folds = 0
    for i in range(1, n_folds):
        tr_end = bounds[i]
        va_end = bounds[i + 1]
        if tr_end < 5 or va_end - tr_end < 3:
            continue
        Xtr, ytr = Xs[:tr_end], yarr[:tr_end]
        Xva, yva = Xs[tr_end:va_end], yarr[tr_end:va_end]
        if ytr.sum() == 0 or ytr.sum() == len(ytr):
            continue  # train fold 單類別 → 跳過
        valid_folds += 1
        best_loss, best_w, best_b = np.inf, None, 0.0
        for lam in lambda_grid:
            w, b = _fit_logistic_l2(Xtr, ytr, lam)
            vloss = _log_loss(yva, _sigmoid(Xva @ w + b))
            fold_val_loss[lam].append(vloss)
            if vloss < best_loss:
                best_loss, best_w, best_b = vloss, w, b
        fold_weights.append(best_w)
        aucs.append(_auc(yva, _sigmoid(Xva @ best_w + best_b)))  # 用 best_w 對應的 best_b

    if valid_folds < HEALTH_FIT_MIN_FOLDS:
        raise ValueError(
            f"有效 fold {valid_folds} < 下限 {HEALTH_FIT_MIN_FOLDS}"
            f"（歷史過短或類別過度不均；§1 不勉強擬合）"
        )

    # inner-CV 選 λ：跨 fold 平均 val log-loss 最小
    lam_mean = {lam: float(np.mean(v)) for lam, v in fold_val_loss.items() if v}
    lambda_selected = min(lam_mean, key=lam_mean.get)

    # 全樣本 refit
    w_std, b_std = _fit_logistic_l2(Xs, yarr, lambda_selected)

    # robustness：跨 fold 權重相對方差（overfit voting）
    fw = np.vstack(fold_weights)
    rel_var = float(np.mean(np.std(fw, axis=0) / (np.abs(np.mean(fw, axis=0)) + 1e-9)))
    sign_flip = bool(np.any(np.ptp(np.sign(fw), axis=0) > 1))  # 某特徵跨 fold 正負翻轉
    overfit_flag = bool(rel_var > HEALTH_FIT_OVERFIT_DRIFT or sign_flip)

    # 映回原特徵空間：z=(x-μ)/σ → w_raw = w_std/σ；b_raw = b_std − Σ w_std·μ/σ
    w_raw = w_std / sigma_safe
    b_raw = float(b_std - np.sum(w_std * mu / sigma_safe))

    return {
        "weights_raw": {name: float(v) for name, v in zip(feature_names, w_raw)},
        "intercept_raw": b_raw,
        "weights_std": {name: float(v) for name, v in zip(feature_names, w_std)},
        "intercept_std": float(b_std),
        "lambda_selected": lambda_selected,
        "n_samples": int(n),
        "class_balance": float(pos / n),
        "cv": {
            "mean_val_log_loss": lam_mean.get(lambda_selected),
            "mean_val_auc": float(np.mean(aucs)) if aucs else None,
            "valid_folds": valid_folds,
        },
        "robustness": {"fold_weight_rel_var": rel_var, "sign_flip": sign_flip},
        "overfit_flag": overfit_flag,
    }


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    """ROC-AUC（純 numpy，rank 法）；單類別回 0.5。"""
    pos = y == 1
    neg = y == 0
    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    # 同分取平均 rank
    _, inv, counts = np.unique(p, return_inverse=True, return_counts=True)
    sum_rank = np.zeros(len(counts))
    np.add.at(sum_rank, inv, ranks)
    avg_rank = sum_rank / counts
    ranks = avg_rank[inv]
    auc = (ranks[pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)
