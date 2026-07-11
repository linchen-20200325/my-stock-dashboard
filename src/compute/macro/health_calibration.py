"""src/compute/macro/health_calibration.py — 紅綠燈健康評分權重「離線校準」L2 純函式 (v19.92).

方法論定案見 `MACRO_HEALTH_REWEIGHT_PROPOSAL.md`。
User 決策(AskUserQuestion)：①風險姿態 ②20日 ③現 3 輸入(jqavg/score/fnet) ④建管線 + 數學式照定義。

§8.2 L2 純函式：**無 I/O、無 streamlit、無 requests**（只 numpy + pandas）。三個演算法：
- `breadth_from_twii()` — 由 ^TWII 日 K 重建 jqavg（鏡像 live `fetch_adl` ① proxy +
  `jingqi_calc` 5 日均，SSOT parity；此為 live jqavg 的 PROXY tier）。
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
# jqavg 重建：鏡像 live fetch_adl ① 的 inline 公式「漲跌幅 ±1% ≈ ±150 家、900 基準」
# + jingqi_calc.py:43 的 tail(5).mean。若改此處務必與該兩處同步（SSOT parity）。
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


def breadth_from_twii(twii_close: pd.Series) -> pd.Series:
    """由 ^TWII 收盤序列重建 jqavg（大盤廣度 proxy）。

    鏡像 live 公式（SSOT parity，`fetch_adl` ① + `jingqi_calc.py:43`）：
        r%      = 日漲跌幅（pct_change × 100）
        up      = clip(900 + 150·r, ≥0)
        down    = clip(900 − 150·r, ≥0)
        ad_ratio = up / (up + down) × 100          （total=0 → NaN，不偽造）
        jqavg   = ad_ratio 的 5 日移動平均

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
    if twii_close is None or len(twii_close) == 0:
        return pd.Series(dtype=float)
    close = pd.Series(twii_close, dtype=float)
    r_pct = close.pct_change() * 100.0
    up = (BREADTH_BASE_COUNT + BREADTH_PCT_TO_COUNT * r_pct).clip(lower=0.0)
    down = (BREADTH_BASE_COUNT - BREADTH_PCT_TO_COUNT * r_pct).clip(lower=0.0)
    total = up + down
    # total=0（極端雙邊 clip）→ NaN；否則 up 佔比 ×100
    ad_ratio = pd.Series(
        np.where(total.to_numpy() > 0, up.to_numpy() / total.to_numpy() * 100.0, np.nan),
        index=close.index,
    )
    return ad_ratio.rolling(JQAVG_ROLLING_DAYS).mean()


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
