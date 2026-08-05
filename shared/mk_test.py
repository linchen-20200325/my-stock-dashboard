"""shared/mk_test.py — Mann-Kendall 無母數趨勢檢定 + Sen's slope(L0 Infra,v19.173)。

為什麼有這支模組
----------------
`src/compute/macro/macro_helpers.py` 原本有個叫 `detect_mk_golden_inflection`
的函式,UI 上顯示為「MK 黃金拐點」。**它不是 Mann-Kendall** —— 實作是
「本月 vs 上月」兩點差分 + 固定 ±0.05/±0.2ppt 門檻,沒有 S 統計量、沒有
Var(S)、沒有 Z、沒有 p-value、沒有 tie 修正。而「MK」在統計文獻裡是
Mann-Kendall 的通用縮寫,這個命名會讓讀者以為那條規則有無母數趨勢檢定背書。

v19.173 的處理是「正名 + 補真的」:
  1. 原函式正名為 `detect_cpi_fed_double_top`(舊名保留 alias,不破壞 caller);
  2. **本模組**提供真正的 Mann-Kendall,**規劃**在 UI 上與該規則並列當佐證。
     ⚠️ 本模組**不參與**任何既有判定 —— 判定邏輯一律不動。

⚠️ 接線狀態:**零 production caller(工具已備、尚未接線)**
------------------------------------------------------
`macro_snapshot.fetch_cpi_block()` / `fetch_fed_funds_block()` 目前只回
「本月 + 上月」兩個純量,全 repo 沒有任何地方存 CPI/Fed 的歷史序列。
n=2 時本模組本來就回 `None` —— 寧可不顯示,也不拿兩個點硬算一個沒有
檢定力的 Z(§1 Fail Loud)。要接線須先新增「回整條月頻序列」的 fetcher,
屬新資料流,CLAUDE.md §7 要求先對齊 endpoint / 欄位單位 / 發布延遲 /
PIT 對齊鍵(**FRED CPI 必須用 `release_date` 而非 `observation_date`**)。
本模組已備妥且有測試,序列到位即可直接接上。

數學定義(逐條列出,供稽核對帳)
--------------------------------
令樣本為 x_1 … x_n(依時間遞增排序,等間隔)。

(1) Mann-Kendall 統計量 S (Mann 1945; Kendall 1975)

        S = Σ_{i<j} sgn(x_j − x_i)

    其中 sgn(a) = +1 (a>0) / 0 (a=0) / −1 (a<0)。
    直觀:所有「後面的點比前面的點大」計 +1、小計 −1、相等計 0。
    無 tie 的嚴格遞增序列 → S = n(n−1)/2(所有配對皆 +1)。

(2) S 的變異數(含 tie 修正,Kendall 1975)

        Var(S) = [ n(n−1)(2n+5) − Σ_p t_p (t_p−1)(2t_p+5) ] / 18

    t_p = 第 p 組「同值(tie)」的元素個數(單一值自成一組時 t_p = 1,
    其項 1·0·7 = 0,不影響結果)。tie 讓有效配對數下降,故 Var(S) 變小。

(3) 標準化統計量 Z(帶連續性修正 ±1)

        Z = (S − 1)/√Var(S)   若 S > 0
          = 0                 若 S = 0
          = (S + 1)/√Var(S)   若 S < 0

    連續性修正的用途:S 是離散量,用連續的常態近似時扣掉 1 個單位,
    避免小樣本下 p-value 系統性偏小(過度宣稱顯著)。

(4) 雙尾 p-value

        p = 2·(1 − Φ(|Z|))          Φ = 標準常態 CDF

    本模組**不依賴 scipy**,Φ 由 `math.erf` 組出:

        Φ(z) = 0.5·(1 + erf(z / √2))

(5) Sen's slope 斜率估計 (Sen 1968)

        β̂ = median{ (x_j − x_i) / (j − i) : i < j }

    對離群值穩健(breakdown point ≈ 29%),單位 = x 的單位 / 一個取樣間隔。
    月頻資料 → 「每月變化量」。線性序列 x_t = a + b·t 時 β̂ 恰為 b。

(6) 趨勢判定

        p < alpha 且 Z > 0 → 'increasing'
        p < alpha 且 Z < 0 → 'decreasing'
        其餘               → 'no trend'

⚠️ 誠實揭露 — 本實作的已知限制
--------------------------------
* **未做序列相關修正**。Mann-Kendall 的 Var(S) 推導假設觀測值**獨立**。
  總經月頻序列(CPI YoY、Fed Funds)有強自相關,自相關會讓真實 Var(S)
  被低估 → |Z| 偏大 → **p-value 偏小 → 過度宣稱顯著**。
  標準修法是 Hamed & Rao (1998) 的變異數校正(用有效樣本數 n* 取代 n)
  或 Yue & Wang (2004) 的 pre-whitening。**本模組沒做**,呼叫端解讀
  p-value 時必須自行留裕度,不得把 p<0.05 當成「趨勢確立」的鐵證。
* **檢定力提醒**:n 小的時候幾乎測不出東西。無 tie 時
    n=4  → S 最大 6,  Z_max = 5/√8.667  ≈ 1.70 → p ≈ 0.089  (連完美單調都達不到 0.05)
    n=5  → S 最大 10, Z_max = 9/√16.67  ≈ 2.20 → p ≈ 0.027
    n=8  → S 最大 28, Z_max = 27/√65.33 ≈ 3.34 → p ≈ 0.00084
  也就是說 **n < 5 時本檢定在 alpha=0.05 下不可能顯著**,n ≥ 8~10 才有
  實用檢定力。本模組對 n < 4 直接回 `None`(§1 不給沒有意義的數字),
  但 n ∈ [4, 8) 仍會給結果 —— 請把它當「證據不足」而非「無趨勢」。
* **等間隔假設**。Sen's slope 的分母用的是「索引距離 j − i」,不是真實
  日期差。月頻序列請確保已補齊缺月(或接受近似)。若序列中含 NaN 被剔除,
  索引會重新編號,分母用的是**剔除後**的距離。
* **tie 判定用浮點精確相等**(`np.unique`)。CLAUDE.md §4.3 禁止用 `==` 做
  浮點「數值」比較,但 tie 的定義本來就是「同一個觀測值」——CPI 兩個月都
  回報 3.20 才算 tie,3.20 與 3.2000000001 是兩個不同的公布值,不該併。
  這裡用精確相等是**定義正確**,不是精度疏漏。

出處
----
* Mann, H.B. (1945). "Nonparametric Tests Against Trend." *Econometrica* 13(3), 245–259.
* Kendall, M.G. (1975). *Rank Correlation Methods*, 4th ed. Charles Griffin, London.
* Sen, P.K. (1968). "Estimates of the Regression Coefficient Based on Kendall's Tau."
  *JASA* 63(324), 1379–1389.
* Hamed, K.H. & Rao, A.R. (1998). "A modified Mann-Kendall trend test for
  autocorrelated data." *Journal of Hydrology* 204, 182–196.(本模組**未**實作)

分層 / 依賴
-----------
L0 Infra —— 只用 `math` + `numpy`。**不得** import streamlit / requests /
pandas 以外的 I/O,亦**不依賴 scipy**(requirements.txt 沒有它)。

效能
----
S 與 Sen's slope 都用 `x[None,:] − x[:,None]` 全向量化,**無 Python 雙層迴圈**。
時間與記憶體皆 O(n²)。月頻總經序列(n ≈ 12~120)成本可忽略;
若日後拿去跑 n > 5000 的日頻序列,請改用分塊或 Kendall tau 的 O(n log n) 演算法。
"""
from __future__ import annotations

import math
import sys
from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np

# ── 常數(§3.3 反捏造:全部具名,不 inline)────────────────────────────
_SQRT2: float = math.sqrt(2.0)

#: 低於此樣本數直接回 None —— n=3 時 S 最大只有 3、Var(S)=(3·2·11)/18≈3.67,
#: Z_max=(3−1)/1.915≈1.04 → p≈0.30,無論資料多完美單調都不可能顯著,
#: 給數字只會讓人誤讀。§1 Fail Loud:寧可沒有,不可誤導。
MK_MIN_SAMPLES: int = 4

#: 建議的最低「有檢定力」樣本數 —— 僅供呼叫端顯示提醒用,不影響計算。
#: 見模組 docstring「檢定力提醒」:月頻資料 n ≥ 8~10 才測得動。
MK_RECOMMENDED_SAMPLES: int = 10

#: 預設顯著水準
MK_DEFAULT_ALPHA: float = 0.05

TREND_INCREASING: str = 'increasing'
TREND_DECREASING: str = 'decreasing'
TREND_NONE: str = 'no trend'


def norm_cdf(z: float) -> float:
    """標準常態累積分佈 Φ(z) = 0.5·(1 + erf(z/√2))。

    為何自己組而不用 scipy:requirements.txt 只有 numpy / pandas,
    本專案禁止為此新增依賴。`math.erf` 是 CPython 內建(C 實作,
    相對誤差 ~1e-16),精度遠優於任何級數近似。
    """
    return 0.5 * (1.0 + math.erf(float(z) / _SQRT2))


@dataclass(frozen=True)
class MannKendallResult:
    """Mann-Kendall 檢定結果(frozen:結果一旦算出不可被下游竄改)。

    欄位
    ----
    n          : 實際參與計算的樣本數(**已扣除 NaN/inf**)
    S          : Mann-Kendall 統計量,見模組 docstring (1)
    var_s      : Var(S),**已含 tie 修正**,見 (2)
    z          : 標準化統計量(含連續性修正),見 (3)
    p          : 雙尾 p-value,見 (4)
    sen_slope  : Sen's slope β̂(單位 = x 單位 / 一個取樣間隔),見 (5)
    trend      : 'increasing' / 'decreasing' / 'no trend',見 (6)
    n_dropped  : 因 NaN / inf 被剔除的筆數(§1 誠實揭露資料完整度)
    alpha      : 本次判定所用的顯著水準
    """

    n: int
    S: float
    var_s: float
    z: float
    p: float
    sen_slope: float
    trend: str
    n_dropped: int
    alpha: float

    @property
    def underpowered(self) -> bool:
        """樣本數不足 `MK_RECOMMENDED_SAMPLES` → True(呼叫端可據此加註警語)。"""
        return self.n < MK_RECOMMENDED_SAMPLES

    def as_dict(self) -> dict:
        """轉 dict(欄位同 dataclass;方便塞進既有 dict-based 的 UI 契約)。"""
        return asdict(self)

    def summary(self) -> str:
        """一行摘要,供 UI 並列顯示。例:`MK: Z = -1.87, p = 0.061, ...`"""
        return (f'MK: Z = {self.z:+.2f}, p = {self.p:.3f}, '
                f"Sen's β = {self.sen_slope:+.3f}/期, n = {self.n}")


def mann_kendall(x: Any, alpha: float = MK_DEFAULT_ALPHA) -> Optional[MannKendallResult]:
    """對時間序列 `x` 做 Mann-Kendall 趨勢檢定 + Sen's slope 估計。

    參數
    ----
    x : array-like
        **依時間遞增排序**的一維數值序列(list / np.ndarray / pd.Series 皆可)。
        非一維會先 `ravel()`。NaN / ±inf 會被剔除,剔除筆數記於 `n_dropped`。
        呼叫端**必須**自行確保排序正確 —— 本函式無法從數值本身推回時間軸,
        傳入亂序資料會得到無意義的 S(這是 GIGO,不是本函式的 bug)。
    alpha : float
        顯著水準,需落在開區間 (0, 1),預設 0.05。

    回傳
    ----
    MannKendallResult | None
        `None` 表示**有效樣本數 < MK_MIN_SAMPLES(4)**,此時檢定沒有意義
        (見模組 docstring「檢定力提醒」)。回 None 時會往 stderr 印出原因,
        呼叫端應顯示「樣本不足」而**不得**自行補一個中性值(§1 Fail Loud)。

    Raises
    ------
    ValueError
        `alpha` 不在 (0,1),或 `x` 無法轉成 float 陣列(型別錯是程式 bug,
        不是資料缺漏,故 raise 而非回 None)。

    邊界行為
    --------
    * **全同值**(所有 x 相等)→ tie 修正使 Var(S) = 0 → 回 z=0 / p=1 /
      trend='no trend' / sen_slope=0.0。**不除零**。
    * **含 NaN** → 先剔除再算;`n_dropped` 記錄剔除筆數。
      剔除後 n < 4 → None。
    * **全 NaN / 空序列** → n=0 → None。

    數學式
    ------
    見模組 docstring (1)~(6),此處不重複。

    效能
    ----
    O(n²) 時間與記憶體,全向量化(`np.sign` 上三角 + `np.triu_indices`),
    無 Python 迴圈。
    """
    # ── ① 參數合法性(與資料是否齊全無關,先驗)──────────────────────
    try:
        _alpha = float(alpha)
    except (TypeError, ValueError):
        raise ValueError(f'mann_kendall: alpha 需為 (0,1) 的浮點數,收到 {alpha!r}') from None
    if not (0.0 < _alpha < 1.0):
        raise ValueError(f'mann_kendall: alpha 需落在 (0,1),收到 {alpha}')

    # ── ② 轉型(型別錯 → fail loud)────────────────────────────────
    try:
        arr = np.asarray(x, dtype=float).ravel()
    except (TypeError, ValueError) as _e:
        raise ValueError(f'mann_kendall: x 無法轉成數值陣列 — {type(_e).__name__}: {_e}') from None

    # ── ③ 顯式剔除缺值 + 記錄筆數(§3.3:dropna 必須顯式且可稽核)──
    n_raw = int(arr.size)
    _finite = np.isfinite(arr)
    n_dropped = int(n_raw - int(_finite.sum()))
    arr = arr[_finite]
    n = int(arr.size)

    if n < MK_MIN_SAMPLES:
        print(
            f'[mk_test.mann_kendall] 有效樣本 n={n} < {MK_MIN_SAMPLES}'
            f'(原始 {n_raw} 筆,剔除 NaN/inf {n_dropped} 筆)→ 回 None。'
            f'Mann-Kendall 在 n<4 時 |Z| 上限不足以達到任何常用 alpha,'
            f'給數字等同誤導;月頻資料建議 n >= {MK_RECOMMENDED_SAMPLES}。',
            file=sys.stderr,
        )
        return None

    # ── ④ S 統計量(全向量化,無雙層 for)────────────────────────────
    # diff[i, j] = x_j - x_i;只取 i<j 的上三角即為 Σ_{i<j}
    diff = arr[None, :] - arr[:, None]
    iu = np.triu_indices(n, k=1)
    upper = diff[iu]
    S = float(np.sign(upper).sum())

    # ── ⑤ Var(S) 含 tie 修正 ────────────────────────────────────────
    # t_p = 各相異值的出現次數;t_p=1 的項 1·0·7=0,自然不影響總和。
    _, counts = np.unique(arr, return_counts=True)
    _c = counts.astype(float)
    tie_term = float(np.sum(_c * (_c - 1.0) * (2.0 * _c + 5.0)))
    var_s = (n * (n - 1.0) * (2.0 * n + 5.0) - tie_term) / 18.0

    # ── ⑥ Z 與 p(Var(S)=0 → 全同值,z=0/p=1,不除零)──────────────
    if var_s <= 0.0:
        z = 0.0
        p = 1.0
    else:
        _sd = math.sqrt(var_s)
        if S > 0.0:
            z = (S - 1.0) / _sd
        elif S < 0.0:
            z = (S + 1.0) / _sd
        else:
            z = 0.0
        # 浮點誤差可能讓 Φ 略越界 → clip 回 [0,1](不是掩蓋,是數值衛生)
        p = min(1.0, max(0.0, 2.0 * (1.0 - norm_cdf(abs(z)))))

    # ── ⑦ Sen's slope(同樣向量化;分母是索引距離 j−i)──────────────
    lag = (iu[1] - iu[0]).astype(float)   # 恆 >= 1,不會除零
    sen_slope = float(np.median(upper / lag))

    # ── ⑧ 趨勢判定 ─────────────────────────────────────────────────
    if p < _alpha and z > 0.0:
        trend = TREND_INCREASING
    elif p < _alpha and z < 0.0:
        trend = TREND_DECREASING
    else:
        trend = TREND_NONE

    return MannKendallResult(
        n=n, S=S, var_s=float(var_s), z=float(z), p=float(p),
        sen_slope=sen_slope, trend=trend, n_dropped=n_dropped, alpha=_alpha,
    )
