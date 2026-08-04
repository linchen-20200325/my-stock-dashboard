"""src/compute/macro/flow_engine.py — 全球資金流向 / 跨資產流動性：純計算層（無 streamlit、無網路 IO）。

設計理念：真實基金資金流量（EPFR/ICI 美元流入流出）為付費資料、免費源不可得，
故以各「區域 / 資產類別代表性 ETF」的相對強弱當資金流向「代理指標」：
  - 世界區域股市：近 N 日報酬率排名（高=資金流入代理、低=流出代理）。
  - 跨資產風險情緒：採 252 日滾動 Z-score + clip(-3,3) 合成 risk-on/off 分數。

本模組只做純計算，方便單元測試；網路抓取在 daily_checklist.fetch_flow_snapshot。
"""
from __future__ import annotations

import math

import numpy as np  # v19.170：向量化 winsorize / 相關矩陣（requirements.txt 既有依賴）

# v18.424 Phase 2 Batch 2b:REGIONAL_ETFS / CROSS_ASSET_ETFS / all_symbols 下沉 L0
# (shared/etf_universe.py)解 L1→L2 反向 import(daily_data_fetchers.py:158)。
# 本 re-export 維持 backward compat,既有 L2 caller(flow_engine 內 + 下游 macro_compute)無感。
from shared.etf_universe import (  # noqa: F401
    REGIONAL_ETFS,
    CROSS_ASSET_ETFS,
    all_symbols,
)
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR  # B5 SSOT-M1


def to_close_list(df) -> list:
    """從 fetch_single 回傳的 DataFrame 取收盤序列 list[float]；無效回 []。"""
    if df is None:
        return []
    try:
        if not hasattr(df, "columns"):
            return []
        col = "close" if "close" in df.columns else ("Close" if "Close" in df.columns else None)
        if col is None:
            return []
        out = []
        for x in df[col].tolist():
            try:
                fx = float(x)
            except (TypeError, ValueError):
                continue
            if fx == fx:  # 過濾 NaN
                out.append(fx)
        return out
    except Exception:
        return []


def pct_return(closes, days):
    """近 days 個交易日報酬率(%)。資料不足或除以零回 None。"""
    if not closes or days <= 0 or len(closes) <= days:
        return None
    prev = closes[-days - 1]
    if prev == 0:
        return None
    return round((closes[-1] / prev - 1) * 100, 2)


def zscore_latest(closes, window=TRADING_DAYS_PER_YEAR, clip=3.0, min_window=60):
    """最新值相對過去 window 日分布的 Z-score（v19.170 修正三處統計瑕疵）。

    數學式
    ------
        vals   = closes[-window:]
        q_lo, q_hi = quantile(vals, 1%), quantile(vals, 99%)
        vals'  = clip(vals, q_lo, q_hi)                      # (2) winsorize 治因
        mean   = mean(vals')
        std    = sqrt( Σ(vals' − mean)² / (n − 1) )          # (1) 樣本變異數
        z      = clip( (closes[-1] − mean) / std, ±clip )    # (3) clip 治果

    v19.170 修正
    ------------
    (1) **母體 → 樣本變異數**：原本除以 n，是把「一段抽樣視窗」當成完整母體，
        會系統性低估 σ（偏誤 = √((n−1)/n)），z 因此被系統性放大。
        改除以 n−1（Bessel 校正）為無偏估計。
    (2) **winsorize 先於統計量**：原本只在算完 z 之後 hard clip。那是治果不治因 ——
        離群值早就流進 mean / std 把分母撐大，導致所有 z 被壓小、訊號鈍化。
        改成先把視窗資料的 1% / 99% 尾端壓回分位數再算 mean / std。
        **兩者並存**：clip(±3) 保留作最後一道防線（分子用的仍是**未 winsorize 的
        原始最新值**，若最新值本身就是離群點，z 會很大並由 clip 兜住）。
    (3) **樣本門檻 30 → min_window（預設 60）**：原本 30 點就照算，卻對外宣稱是
        「252 日滾動 Z-score」，等同用 6 週資料冒充 1 年分布（§1 反捏造）。
        不足時回 None 並 print 實際樣本數留跡，不猜。

    Args
    ----
    closes : Sequence[float]  價格 / 比率序列（時間遞增）
    window : int              統計視窗（交易日），預設 252
    clip : float              z 的最終截斷邊界（最後防線）
    min_window : int          最少樣本數，低於此回 None（v19.170 新增，預設 60）

    Returns
    -------
    float | None
        z-score（小數 2 位）；樣本不足回 None；winsorize 後 std=0（視窗內幾乎常數）
        回 0.0（此時「偏離幾個 σ」無定義，0.0 代表「與視窗水準無異」，非捏造方向）。
    """
    if not closes:
        return None
    n_all = len(closes)
    if n_all < min_window:
        # §1 Fail Loud：不足就說不足，並留下實際樣本數，不靜默回 0 也不硬算
        print(f"[flow_engine] zscore_latest 樣本不足:實得 {n_all} 點 < min_window={min_window}"
              f"(宣稱 {window} 日 Z-score 需足量樣本)→ 回 None")
        return None

    vals = np.asarray(closes[-window:] if n_all > window else closes, dtype=float)
    vals = vals[np.isfinite(vals)]
    n = vals.size
    if n < 2:  # 樣本變異數需 n>=2（除 n-1）
        print(f"[flow_engine] zscore_latest 有效點數 {n} < 2(NaN/inf 過濾後)→ 回 None")
        return None

    # (2) winsorize：向量化，無 for 迴圈
    q_lo, q_hi = np.quantile(vals, [0.01, 0.99])
    w_vals = np.clip(vals, q_lo, q_hi)
    mean = float(w_vals.mean())
    std = float(w_vals.std(ddof=1))  # (1) ddof=1 → 樣本變異數（除 n-1）
    if not np.isfinite(std) or std == 0:
        return 0.0

    last = float(closes[-1])
    if not np.isfinite(last):
        print("[flow_engine] zscore_latest 最新值非有限數 → 回 None")
        return None
    z = (last - mean) / std
    # (3) clip 仍保留：winsorize 治「分母被汙染」，clip 治「分子本身是離群點」
    return round(max(-clip, min(clip, z)), 2)


def rank_regional_flow(close_map, days=5):
    """各區域近 days 報酬率排名（高→低 = 資金流入→流出代理）。
    close_map: {名稱: closes_list}。回 list[(名稱, pct)]，已過濾 None、由高到低。"""
    rows = []
    for name, closes in close_map.items():
        r = pct_return(closes, days)
        if r is not None:
            rows.append((name, r))
    rows.sort(key=lambda kv: kv[1], reverse=True)
    return rows


def _ratio_series(close_map, a, b, min_len=30):
    """對齊尾段後計算 a/b 比率序列；長度不足或分母為零略過 → 回 []。"""
    ca = close_map.get(a) or []
    cb = close_map.get(b) or []
    n = min(len(ca), len(cb))
    if n < min_len:
        return []
    ca, cb = ca[-n:], cb[-n:]
    return [x / y for x, y in zip(ca, cb) if y]


def _risk_label(score):
    if score >= 50:
        return "🟢 強烈 Risk-on（資金追逐風險）"
    if score >= 15:
        return "🟢 偏 Risk-on"
    if score > -15:
        return "🟡 中性"
    if score > -50:
        return "🔴 偏 Risk-off（避險防禦）"
    return "🔴 強烈 Risk-off（資金撤退）"


def _direction_adjusted_corr(series_dirs, window, min_obs=30, use_diff=True):
    """算「方向調整後」序列的相關矩陣 ρ（v19.170；v19.171 新增 use_diff）。

    ⚠️⚠️ 本函式會依 `use_diff` 回傳**兩種在數學上不同**的 ρ，用途**不可互換** ⚠️⚠️
    -------------------------------------------------------------------------
    ==========  ==================  ================================================
    use_diff    估計對象            唯一正確用途
    ==========  ==================  ================================================
    True(預設)  一階差分(日變動)    算**權重 w**（成分間的資訊冗餘度 / 共同波動）
    False       方向調整後水位序列  算**組合標準差 σ_p**（合成量的分母）
    ==========  ==================  ================================================

    為何**權重**要用「日變動」ρ（保留 v19.170 的判斷，不要改回去）
    -----------------------------------------------------------
    視窗內的 z 序列 z=(x−mean)/std 是水位序列的**仿射變換**，
    ρ(z_i, z_j) ≡ ρ(x_i, x_j)。而兩條同時走多頭的價格序列，即使日變動幾乎無關，
    水位相關也會逼近 1（spurious correlation，Yule 1926）。
    若直接用它算權重，所有 |ρ|→1、權重退化成等權，等於白做。
    改用一階差分（日變動）估共同波動，才是「重複計價 / 資訊冗餘」的正確度量。

    為何 **σ_p** 反而要用「水位」ρ（v19.171 修正，稽核 AI-2 手算驗證）
    ----------------------------------------------------------------
    合成量的**分子**是 s = Σ_i w_i·(d_i·z_i)，其中 z_i 是 `zscore_latest()` 給的
    **水位** z。變異數恆等式

        Var(s) = ΣΣ w_i w_j·Cov(d_i z_i, d_j z_j) = wᵀ ρ w        (∵ Var(z_i)=1)

    **只在 ρ = corr(d_i z_i, d_j z_j)（即水位的 ρ）時成立**。
    v19.170 誤把「差分的 ρ」代進去 —— 分子是水位、分母是差分，兩者不是同一組
    隨機變數，恆等式斷裂。實測量級（n=7、水位 ρ̄≈0.8、差分 ρ̄≈0.3、等權）：

        正確(水位 ρ)：var_p = 1/7 + (6/7)(0.8) = 0.829 → σ_p = 0.911
        錯誤(差分 ρ)：var_p = 1/7 + (6/7)(0.3) = 0.400 → σ_p = 0.632

    分數被系統性放大 1.44×，score=38（🟢 偏 Risk-on）會變成 55 → 跨過 ±50 邊界
    誤報「強烈 Risk-on」，等於燈號整級上調。故**兩個 ρ 各司其職**：
    差分 ρ 管「該給誰多少票」，水位 ρ 管「這票加總後有多少個 σ」。

    為何兩者都要先乘方向 d
    ----------------------
    合成量是 Σ w_i·(d_i·z_i)。組合變異數需要的是**方向調整後**成分之間的
    ρ(d_i z_i, d_j z_j) = d_i d_j ρ(z_i, z_j)，符號不可省（省了 σ_p 會算錯）。

    Args
    ----
    series_dirs : list[(Sequence[float], int)]   [(closes, direction), ...]
    window : int                                  對齊上限（交易日）
    min_obs : int                                 最少觀測筆數，不足回 None
    use_diff : bool                               True=一階差分ρ（權重用）
                                                  False=水位ρ（σ_p 用）

    Returns
    -------
    np.ndarray | None
        n×n 相關矩陣；序列長度不足 / 某序列在對齊窗內為常數（std=0）/
        出現非有限值 → 回 None（呼叫端據此顯式降級成等權，不猜）。
    """
    if len(series_dirs) < 2:
        return None
    lengths = [len(c) for c, _ in series_dirs]
    L = min(min(lengths), window)
    # 差分後少一筆，故門檻是 min_obs+1。水位模式其實只需 min_obs，但**刻意沿用
    # 同一道門檻**，讓兩種 ρ 必然同時算得出／同時降級 —— 否則會出現「權重用
    # inv_corr、σ_p 卻退回 1.0」這種半套狀態，難以推理也難以測試。
    if L < min_obs + 1:
        return None
    mat = np.asarray([np.asarray(c[-L:], dtype=float) * float(d) for c, d in series_dirs])
    if not np.all(np.isfinite(mat)):
        return None
    rows = np.diff(mat, axis=1) if use_diff else mat   # 向量化：一階差分 / 原水位
    if rows.shape[1] < min_obs:
        return None
    sd = rows.std(axis=1, ddof=1)
    if not np.all(np.isfinite(sd)) or np.any(sd <= 0):
        return None                        # 常數序列 → 相關無定義，降級
    corr = np.corrcoef(rows)
    corr = np.atleast_2d(corr)
    if corr.shape[0] != len(series_dirs) or not np.all(np.isfinite(corr)):
        return None
    return corr


def compute_risk_score(close_map, window=TRADING_DAYS_PER_YEAR, min_window=60):
    """用跨資產序列合成 risk-on/off 分數（v19.170 修 P1-3 等權共線）。

    close_map 需含 CROSS_ASSET_ETFS 的 key（缺的自動略過）。
    各代理指標「上升」代表 risk-on(+1) 或 risk-off(-1)。

    v19.170 修正一：相關性倒數加權（解「重複計價」）
    ------------------------------------------------
    原本 7 個成分等權相加，但 SPY/TLT 與 HYG/LQD、VIX 之間的 |ρ| 常 > 0.8 ——
    同一件事被投票 3 次，等於偷偷放大權重。改成：

        w_i = (1 / Σ_j |ρ_ij|) / Σ_k (1 / Σ_j |ρ_kj|)

    直覺：一個成分跟其他人越像（Σ_j|ρ_ij| 越大），越可能是重複資訊，權重越低；
    獨立成分權重高。權重恆正且加總為 1。

    v19.170 修正二：改用組合理論標準差標準化（解「分數永遠打不到極值」）
    ------------------------------------------------------------------
    原本 `score = avg / 3 × 100`，avg 是 n 個 z 的算術平均。當成分不完全相關時，
    平均會把彼此抵消的雜訊拉平，avg 幾乎不可能靠近 ±3 →
    分數長期壓在 ±50 內，`_risk_label` 的「強烈 Risk-on/off」（±50）幾乎觸發不到。
    改成除以**加權組合的理論標準差**：

        s     = Σ_i w_i · (d_i · z_i)
        σ_p   = sqrt( Σ_i w_i² + 2·ΣΣ_{i<j} w_i w_j ρ_ij )   （= sqrt(wᵀ ρ w)）
        score = clip( (s / σ_p) / 3 × 100 , −100, +100 )

    因為每個 z_i 都已標準化（單位變異數），wᵀρw 正是組合的變異數。
    除以 σ_p 後 s/σ_p 回到「單位 σ」尺度，與單一成分 z 同尺度、與 ±3 的 clip 邊界可比。
    效果（**理論上**）：全相關（ρ≈1）時 σ_p≈1，退化成原本的平均；
    成分互相獨立時 σ_p≈1/√n，分數被放大 √n 倍（n 個獨立證據本來就更強）。

    ⚠️ v19.171 誠實補述：上面這句「放大 √n 倍」**實務上幾乎不會發生**。
    v19.171 把 σ_p 的 ρ 改吃**水位**（ρ_level，見下方修正三）之後，趨勢價格
    序列的水位相關恆逼近 1（成因即本檔 `_direction_adjusted_corr` 引用的
    Yule 1926 spurious correlation）→ wᵀρ_level·w ≈ (Σw)² = 1，
    實測 var_p≈1、σ_p≈1、n_effective≈1：分數基本上就是原本的加權平均，
    放大效果有限，`_risk_label` 的 ±50「強烈」門檻依舊不容易觸發。
    這是**刻意付出的代價**，不是 bug：水位 ρ 保證分母與分子（水位 z）同源、
    `Var(s)=wᵀρw` 的恆等式才成立。改用差分 ρ 確實能換到 √n 放大，但那個放大
    是**假的**（分子分母不同源，量化影響見修正三：一律虛增 1.44×、燈號整級
    上調）。寧可不放大，也不要放大一個算錯的數。

    v19.171 修正三【🔴 數學錯誤】：σ_p 的分子分母必須同源
    ----------------------------------------------------
    上式 `Var(s) = wᵀρw` 的成立條件是 **ρ = corr(d_i z_i, d_j z_j)**，
    也就是「與分子同一組隨機變數」的相關矩陣。v19.170 卻把 `w` 與 `σ_p`
    **共用同一個差分 ρ**：分子 Σ w_i d_i z_i 的 z 是**水位** z，分母卻用
    **一階差分**的 ρ —— 兩者不是同一組變數，恆等式直接斷裂。

    量化影響（n=7、水位 ρ̄≈0.8、差分 ρ̄≈0.3、等權）：
    σ_p 由 0.911 被低估成 0.632 → 分數一律放大 1.44×，
    score=38（🟢 偏 Risk-on）→ 55 跨過 ±50 邊界變「強烈 Risk-on」，燈號整級上調。

    修法（兩個 ρ 各司其職，見 `_direction_adjusted_corr` docstring）::

        w   ← ρ_diff  （一階差分）：估「資訊冗餘 / 重複計價」。水位 ρ 在共同
                                    趨勢下→1 是 spurious correlation，
                                    拿來配權會退化成等權，等於白做。
        σ_p ← ρ_level （水位）    ：與分子的水位 z 同源，恆等式才成立。

    另加**保守地板 / 天花板** `1/√n ≤ σ_p ≤ 1`（等價 `1 ≤ n_effective ≤ n`）：
      - 地板 1/√n：防「強負相關對」把 var_p 壓到 0.01 量級、分數被假性放大到 ±100
        （n 個成分的有效獨立資訊量不可能超過 n）。
      - 天花板 1：`wᵀρw ≤ (Σw)² = 1`（w≥0、ρ_ij≤1）本就恆成立，
        此處僅為浮點誤差的數值防護，數學上是 no-op。

    降級（CLAUDE.md §1 顯式降級 + 旗標，不靜默）
    --------------------------------------------
    相關矩陣算不出（樣本不足 / 常數序列 / 只有 1 個成分）→ 退回等權，
    且**保守地假設 σ_p = 1（視同完全相關）**，數值即等於 v19.169 的舊行為，
    回傳 dict 標 `'weighting': 'equal'`。

    Args
    ----
    close_map : dict[str, Sequence[float]]
    window : int         Z-score / 相關矩陣視窗（交易日）
    min_window : int     單一序列最少樣本數（v19.170 新增，透傳 zscore_latest）

    Returns
    -------
    dict
        既有 key（下游 section_long.py 依賴，**不得移除**）：
          'score'      : int | None      −100..100
          'label'      : str             _risk_label() 文案
          'components' : list[(名稱, z, 方向)]
        v19.170 新增 key：
          'weighting'  : 'inv_corr' | 'equal'
          'weights'    : list[(名稱, w)]  w 加總為 1
          'n_effective': float            有效獨立成分數 = 1/σ_p²
                                          （全相關→1；n 個獨立→n）
                                          v19.171 起由 σ_p 的地板/天花板保證
                                          落在 [1, n]，不會再出現 >n 的假性放大。
    """
    signals = []  # (顯示名, closes, 方向)

    spy_tlt = _ratio_series(close_map, "股票 SPY", "長天期美債 TLT")
    if spy_tlt:
        signals.append(("股債比 SPY/TLT", spy_tlt, +1))
    hyg_lqd = _ratio_series(close_map, "高收益債 HYG", "投資級債 LQD")
    if hyg_lqd:
        signals.append(("信用利差 HYG/LQD", hyg_lqd, +1))
    move_vix = _ratio_series(close_map, "美債波動 MOVE", "VIX 波動率")
    if move_vix:
        signals.append(("MOVE/VIX 債市壓力", move_vix, -1))
    for name, direction in (
        ("VIX 波動率", -1),
        ("美元 UUP", -1),
        ("黃金 GLD", -1),
        ("美元日圓 USDJPY", +1),  # USD/JPY 升 = 日圓貶 = carry-on = risk-on
    ):
        if close_map.get(name):
            signals.append((name, close_map[name], direction))

    components = []
    used = []  # (顯示名, closes, 方向) — 僅保留 z 算得出來的
    for label, closes, direction in signals:
        z = zscore_latest(closes, window=window, min_window=min_window)
        if z is None:
            continue
        components.append((label, z, direction))
        used.append((label, closes, direction))

    if not components:
        # 既有回傳契約：score=None / components=[]（tests/test_flow_engine.py 斷言）
        return {"score": None, "label": "資料不足", "components": [],
                "weighting": "equal", "weights": [], "n_effective": 0.0}

    names = [c[0] for c in components]
    contrib = np.asarray([c[1] * c[2] for c in components], dtype=float)  # d_i · z_i
    n = int(contrib.size)

    # v19.171：兩個 ρ 各司其職 —— 差分 ρ 配權重、水位 ρ 算 σ_p（見 docstring 修正三）。
    # 兩者共用同一道長度門檻，故必然同時算得出／同時降級，不會出現半套狀態。
    _series_dirs = [(c[1], c[2]) for c in used]
    corr_diff = _direction_adjusted_corr(_series_dirs, window, use_diff=True)
    corr_level = _direction_adjusted_corr(_series_dirs, window, use_diff=False)
    weighting = "inv_corr"
    if corr_diff is None or corr_level is None:
        weighting = "equal"
    else:
        # 權重＝資訊冗餘度的倒數 → 必須用**差分** ρ（水位 ρ 會被共同趨勢帶到 1）
        abs_row_sum = np.abs(corr_diff).sum(axis=1)  # Σ_j |ρ_ij|（含 j=i，|ρ_ii|=1）
        if not np.all(np.isfinite(abs_row_sum)) or np.any(abs_row_sum <= 0):
            weighting = "equal"
        else:
            inv = 1.0 / abs_row_sum
            weights = inv / inv.sum()
            # σ_p² = wᵀ ρ_level w —— 分子 Σ w_i·d_i·z_i 的 z 是**水位** z，
            # 分母只能用同一組變數（水位）的 ρ，否則 Var(s)=wᵀρw 恆等式斷裂。
            var_p = float(weights @ corr_level @ weights)
            if not np.isfinite(var_p) or var_p <= 1e-12:
                # 完全對沖的組合（理論 σ→0）→ 除下去會爆炸，顯式降級
                print("[flow_engine] compute_risk_score 組合理論變異數退化 "
                      f"(var_p={var_p:.3e}) → 降級等權")
                weighting = "equal"
            else:
                # 保守地板 1/√n（限 n_effective ≤ n，防強負相關對把分數假性放大到 ±100）
                # 與天花板 1.0（wᵀρw ≤ (Σw)²=1 恆成立，僅防浮點誤差；數學上 no-op）。
                sigma_p = min(1.0, max(math.sqrt(var_p), 1.0 / math.sqrt(n)))

    if weighting == "equal":
        # 降級路徑：等權 + 保守假設 σ_p = 1（視同成分完全相關），
        # 數值等同 v19.169 舊行為（avg/3×100），不會因降級而放大分數。
        weights = np.full(n, 1.0 / n, dtype=float)
        sigma_p = 1.0

    combo = float(np.dot(weights, contrib))
    norm = combo / sigma_p                       # 回到「單位 σ」尺度
    score = int(round(max(-100.0, min(100.0, norm / 3.0 * 100.0))))
    n_effective = round(1.0 / (sigma_p ** 2), 2)  # 有效獨立成分數
    return {
        "score": score,
        "label": _risk_label(score),
        "components": components,
        "weighting": weighting,
        "weights": [(nm, round(float(w), 4)) for nm, w in zip(names, weights)],
        "n_effective": n_effective,
    }
