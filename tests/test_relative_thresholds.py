"""tests/test_relative_thresholds.py — shared/relative_thresholds 純函式測試（v19.172）

聚焦 `vol_normalized_bias()` 的 🔴 量綱錯誤修正：

    舊式（v19.170，錯）  bias_sigma = bias_pct / ann_vol_pct
    新式（v19.172，對）  bias_sigma = (bias_pct − μ_a·(N−1)/(2T))
                                     / (ann_vol_pct · sqrt((N−1)(2N−1)/(6·N·T)))

測試分三層：
  1. golden   — 稽核報告的實測數字（BIAS240 = +32.7%）逐格對帳，每個期望值都在
                docstring 裡寫出手算過程。
  2. property — 尺度不變性 / 單調性 / 邊界（不需 hypothesis，用固定格點窮舉）。
  3. 蒙地卡羅 — 直接**模擬隨機漫步**驗證 Var(X) 與 E[X] 的封閉解，
                這是唯一能證明「0.5617 這個係數是推導出來的、不是掰的」的測試。
                固定 seed → 完全可重現（CLAUDE.md §5）。
"""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.relative_thresholds import (  # noqa: E402
    DEFAULT_BIAS_MA_LEN,
    _bias_drift_factor,
    _bias_sd_factor,
    vol_normalized_bias,
)
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR  # noqa: E402

_N = DEFAULT_BIAS_MA_LEN          # 240
_T = TRADING_DAYS_PER_YEAR        # 252


class TestBiasFactors(unittest.TestCase):
    """換算係數必須由 (N, T) 推導，且對得上手算值。"""

    def test_sd_factor_240_252(self):
        """手算：sqrt(239×479 / (6×240×252)) = sqrt(114481 / 362880)
                = sqrt(0.3154789) = 0.5616751。"""
        self.assertAlmostEqual(_bias_sd_factor(240, 252), 0.5616751, places=6)

    def test_drift_factor_240_252(self):
        """手算：(240−1) / (2×252) = 239 / 504 = 0.4742063。"""
        self.assertAlmostEqual(_bias_drift_factor(240, 252), 0.4742063, places=6)

    def test_sd_factor_matches_large_n_approximation(self):
        """精確式 vs 大 N 近似 sqrt(N/(3T))：N=240 時 0.5616751 vs 0.5634362，
        差 +0.313%。近似只能當量級參考，本模組採精確式。"""
        exact = _bias_sd_factor(240, 252)
        approx = math.sqrt(240 / (3 * 252))
        self.assertAlmostEqual(approx, 0.5634362, places=6)
        self.assertAlmostEqual(approx / exact - 1.0, 0.00313, places=4)

    def test_sd_factor_shorter_ma_is_smaller(self):
        """N 越短，BIAS 的 σ 越小（累積的報酬筆數少）：
        手算 N=20 → sqrt(741/30240)  = sqrt(0.0245040) = 0.156537
             N=60 → sqrt(7021/90720) = sqrt(0.0773919) = 0.278194
             N=240→ 0.561675。"""
        self.assertAlmostEqual(_bias_sd_factor(20, 252), 0.156537, places=5)
        self.assertAlmostEqual(_bias_sd_factor(60, 252), 0.278194, places=5)
        self.assertLess(_bias_sd_factor(20, 252), _bias_sd_factor(60, 252))
        self.assertLess(_bias_sd_factor(60, 252), _bias_sd_factor(240, 252))


class TestVolNormalizedBiasGolden(unittest.TestCase):
    """稽核實測 BIAS240 = +32.7% 的三格對帳（μ = 0）。

    SD(BIAS240) = σ_a × 0.5616751
      σ_a = 20% → SD = 11.233502% → 32.7 / 11.233502 = 2.910935 → **2.911**
      σ_a = 25% → SD = 14.041877% → 32.7 / 14.041877 = 2.328748 → **2.329**
      σ_a = 30% → SD = 16.850253% → 32.7 / 16.850253 = 1.940624 → **1.941**
    舊式（錯）分別給 32.7/20 = 1.635、32.7/25 = 1.308、32.7/30 = 1.090。
    """

    def test_golden_vol_20(self):
        self.assertAlmostEqual(vol_normalized_bias(32.7, 20.0), 2.911, delta=0.002)

    def test_golden_vol_25(self):
        self.assertAlmostEqual(vol_normalized_bias(32.7, 25.0), 2.329, delta=0.002)

    def test_golden_vol_30(self):
        self.assertAlmostEqual(vol_normalized_bias(32.7, 30.0), 1.941, delta=0.002)

    def test_understatement_ratio_is_constant_when_no_drift(self):
        """μ=0 時，新式 / 舊式 恆為 1/0.5616751 = **1.780384**（與波動無關）。
        這就是「舊式系統性低估」的量化證據 —— 不是偶爾偏，是每次都偏同一倍。"""
        for vol in (12.0, 18.0, 20.0, 25.0, 30.0, 45.0):
            new = vol_normalized_bias(32.7, vol)
            old = 32.7 / vol
            self.assertAlmostEqual(new / old, 1.780384, delta=0.002,
                                   msg=f'vol={vol}')

    def test_retracted_conclusion_296_is_actually_extreme(self):
        """撤回 v19.170「+29.6% 在高波動的結構多頭裡並不極端」。

        手算（μ=0）：
          σ_a = 30% → 29.6 / 16.850253 = 1.756650 → **1.757σ**
          σ_a = 25% → 29.6 / 14.041877 = 2.108122 → **2.108σ**
          σ_a = 20% → 29.6 / 11.233502 = 2.634952 → **2.635σ**
        舊式在 σ_a = 30% 只給 29.6/30 = 0.987σ（才會得出「並不極端」）。
        即使假設波動高達 30%，正確值仍 > 1.7σ。
        """
        self.assertAlmostEqual(vol_normalized_bias(29.6, 30.0), 1.757, delta=0.002)
        self.assertAlmostEqual(vol_normalized_bias(29.6, 25.0), 2.108, delta=0.002)
        self.assertAlmostEqual(vol_normalized_bias(29.6, 20.0), 2.635, delta=0.002)
        # 舊結論的依據（0.987σ）與正確值差距 > 0.75σ，足以跨越黃/紅判級
        self.assertGreater(vol_normalized_bias(29.6, 30.0), 1.7)

    def test_retracted_20pct_bias_examples(self):
        """v19.170 docstring 另兩個錯數字的正解：
          18% 波動 → SD = 10.110152% → 20 / 10.110152 = 1.978212（原寫 1.11）
          30% 波動 → SD = 16.850253% → 20 / 16.850253 = 1.186925（原寫 0.67）
        """
        self.assertAlmostEqual(vol_normalized_bias(20.0, 18.0), 1.978, delta=0.002)
        self.assertAlmostEqual(vol_normalized_bias(20.0, 30.0), 1.187, delta=0.002)


class TestVolNormalizedBiasDrift(unittest.TestCase):
    """可選漂移修正 μ_a·(N−1)/(2T)。"""

    def test_drift_10pct(self):
        """手算：μ_bias = 10 × 0.4742063 = 4.742063
                分子 = 32.7 − 4.742063 = 27.957937
                σ_a = 25% → SD = 14.041877 → 27.957937 / 14.041877 = 1.991042
        """
        self.assertAlmostEqual(vol_normalized_bias(32.7, 25.0, drift_ann_pct=10.0),
                               1.991, delta=0.002)

    def test_drift_reduces_sigma_count(self):
        """正漂移 → 扣掉趨勢本身帶來的乖離 → σ 數必然變小（保守方向反過來）。"""
        no_drift = vol_normalized_bias(32.7, 25.0)
        with_drift = vol_normalized_bias(32.7, 25.0, drift_ann_pct=12.0)
        self.assertLess(with_drift, no_drift)

    def test_drift_none_equals_zero(self):
        """不給 drift ＝ 假設 μ=0（docstring 明說），數值必須與顯式傳 0.0 相同。"""
        self.assertEqual(vol_normalized_bias(32.7, 25.0),
                         vol_normalized_bias(32.7, 25.0, drift_ann_pct=0.0))

    def test_understatement_ratio_range_with_drift(self):
        """加上 10%~15% 年漂移後，低估倍率由 1.780 降到約 1.52~1.39
        ⇒ 綜合區間 **1.4~1.8 倍**（稽核報告的說法在此被釘住）。
        手算 σ_a=25%、bias=32.7：
          μ=10% → 1.991042 / 1.308 = 1.5222
          μ=15% → (32.7 − 7.113095)/14.041877 = 1.822320 → /1.308 = 1.3932
        """
        old = 32.7 / 25.0
        r10 = vol_normalized_bias(32.7, 25.0, drift_ann_pct=10.0) / old
        r15 = vol_normalized_bias(32.7, 25.0, drift_ann_pct=15.0) / old
        self.assertAlmostEqual(r10, 1.5222, delta=0.003)
        self.assertAlmostEqual(r15, 1.3932, delta=0.003)
        for r in (r10, r15, 1.780384):
            self.assertGreater(r, 1.35)
            self.assertLess(r, 1.79)


class TestVolNormalizedBiasMaLen(unittest.TestCase):
    """ma_len 參數化 —— BIAS20 / BIAS60 也能用同一個函式。"""

    def test_bias20(self):
        """手算：N=20 → factor 0.156537 → SD = 20 × 0.156537 = 3.130740
                5 / 3.130740 = 1.597064 → **1.597**"""
        self.assertAlmostEqual(vol_normalized_bias(5.0, 20.0, ma_len=20),
                               1.597, delta=0.003)

    def test_shorter_ma_gives_larger_sigma_count(self):
        """同樣 +10% 乖離，對 20MA 比對 240MA 誇張得多（分母 σ 小很多）。
        手算 σ_a=20%：N=20 → 10/3.130740 = 3.194；N=240 → 10/11.233502 = 0.890。"""
        s20 = vol_normalized_bias(10.0, 20.0, ma_len=20)
        s240 = vol_normalized_bias(10.0, 20.0, ma_len=240)
        self.assertAlmostEqual(s20, 3.194, delta=0.003)
        self.assertAlmostEqual(s240, 0.890, delta=0.003)
        self.assertGreater(s20, s240)

    def test_trading_days_must_match_annualization(self):
        """T 變小 → 年化波動換算回日波動變大 → SD 變大 → σ 數變小。
        手算 T=52（週頻誤用）：factor = sqrt(114481/74880) = sqrt(1.5288600)
                             = 1.2364708 → SD = 24.729416
                             → 32.7 / 24.729416 = 1.322312 → **1.322**"""
        self.assertAlmostEqual(vol_normalized_bias(32.7, 20.0, trading_days=52),
                               1.322, delta=0.003)


class TestVolNormalizedBiasBoundaries(unittest.TestCase):
    """§1 Fail Loud：算不出就回 None，不除零、不填 0。"""

    def test_none_inputs(self):
        self.assertIsNone(vol_normalized_bias(None, 25.0))
        self.assertIsNone(vol_normalized_bias(32.7, None))
        self.assertIsNone(vol_normalized_bias(None, None))

    def test_non_positive_vol(self):
        self.assertIsNone(vol_normalized_bias(32.7, 0.0))
        self.assertIsNone(vol_normalized_bias(32.7, -25.0))

    def test_nan_inf(self):
        self.assertIsNone(vol_normalized_bias(float('nan'), 25.0))
        self.assertIsNone(vol_normalized_bias(float('inf'), 25.0))
        self.assertIsNone(vol_normalized_bias(32.7, float('nan')))
        self.assertIsNone(vol_normalized_bias(32.7, float('inf')))

    def test_bad_drift_is_not_silently_zero(self):
        """drift 有給但壞掉 → 回 None（資料壞掉 ≠ 沒有資料，不可靜默當 0）。"""
        self.assertIsNone(vol_normalized_bias(32.7, 25.0, drift_ann_pct=float('nan')))
        self.assertIsNone(vol_normalized_bias(32.7, 25.0, drift_ann_pct=float('inf')))

    def test_non_numeric(self):
        self.assertIsNone(vol_normalized_bias('abc', 25.0))
        self.assertIsNone(vol_normalized_bias(32.7, 'abc'))

    def test_zero_bias_is_zero_not_none(self):
        """bias 恰好 0 是**合法**輸入（不是缺值），必須回 0.0 而非 None。"""
        self.assertEqual(vol_normalized_bias(0.0, 25.0), 0.0)

    def test_negative_bias_keeps_sign(self):
        """負乖離手算：−32.7 / 14.041877 = −2.328748 → **−2.329**"""
        self.assertAlmostEqual(vol_normalized_bias(-32.7, 25.0), -2.329, delta=0.002)

    def test_invalid_params_raise(self):
        with self.assertRaises(ValueError):
            vol_normalized_bias(32.7, 25.0, ma_len=1)
        with self.assertRaises(ValueError):
            vol_normalized_bias(32.7, 25.0, trading_days=0)


class TestVolNormalizedBiasProperties(unittest.TestCase):
    """property 風格（固定格點窮舉，不引入 hypothesis 依賴）。"""

    def test_scale_invariance(self):
        """bias 與 vol 同乘 c > 0 → σ 數不變（純比值，無量綱）。"""
        base = vol_normalized_bias(20.0, 25.0)
        for c in (0.1, 0.5, 2.0, 10.0):
            self.assertAlmostEqual(vol_normalized_bias(20.0 * c, 25.0 * c), base,
                                   delta=1e-3, msg=f'c={c}')

    def test_monotone_in_bias_and_vol(self):
        for vol in (15.0, 20.0, 25.0, 30.0):
            prev = None
            for bias in (-30.0, -10.0, 0.0, 10.0, 30.0):
                cur = vol_normalized_bias(bias, vol)
                if prev is not None:
                    self.assertGreater(cur, prev)
                prev = cur
        for bias in (10.0, 30.0):
            prev = None
            for vol in (15.0, 20.0, 25.0, 30.0):
                cur = vol_normalized_bias(bias, vol)
                if prev is not None:
                    self.assertLess(cur, prev)   # 波動越大 → 同乖離越不極端
                prev = cur

    def test_sign_preserved(self):
        for bias in (-50.0, -1.0, 1.0, 50.0):
            for vol in (10.0, 25.0, 60.0):
                self.assertEqual(np.sign(vol_normalized_bias(bias, vol)),
                                 np.sign(bias), msg=f'{bias}/{vol}')


class TestBiasVarianceMonteCarlo(unittest.TestCase):
    """蒙地卡羅：直接模擬帶漂移隨機漫步，驗證封閉解。

    設 L_j = Σ_{i<=j} r_i（L_0 = 0），取 N 步後
        X = L_N − (1/N)·Σ_{j=1}^{N} L_j
    理論（推導見 vol_normalized_bias docstring）：
        Var(X) = σ_d²·(N−1)(2N−1)/(6N)   → N=240 時 79.500694·σ_d²
        SD(X)  = σ_d·8.916316
        E[X]   = μ_d·(N−1)/2             → N=240 時 119.5·μ_d
    固定 seed → 可重現（CLAUDE.md §5）。全向量化，無 Python 迴圈。
    """
    SEED = 20260805
    PATHS = 12000

    def _simulate(self, mu_d, sigma_d):
        rng = np.random.default_rng(self.SEED)
        r = rng.normal(mu_d, sigma_d, size=(self.PATHS, _N))
        lvl = np.cumsum(r, axis=1)
        return lvl[:, -1] - lvl.mean(axis=1)

    def test_variance_closed_form(self):
        """σ_d = 1 → 理論 SD(X) = sqrt(79.500694) = 8.916316。

        12000 條路徑的 std 估計 SE ≈ SD/sqrt(2·P) = 0.65%，容差取 3%（≈4.6 SE）
        —— 足以把 0.5617 與舊式隱含的 1.0 分得一清二楚，又不會因抽樣抖動誤紅。
        """
        x = self._simulate(0.0, 1.0)
        theo = math.sqrt((_N - 1) * (2 * _N - 1) / (6.0 * _N))
        self.assertAlmostEqual(theo, 8.916316, places=5)
        self.assertAlmostEqual(float(x.std(ddof=1)) / theo, 1.0, delta=0.03)

    def test_sd_factor_reproduces_simulation(self):
        """把模擬的日尺度 SD 換算成「年化波動的幾倍」，必須等於 _bias_sd_factor。

        σ_d = 1 ⇒ σ_a = sqrt(252) = 15.874508
        模擬 SD(X) / σ_a 應 ≈ _bias_sd_factor(240, 252) = 0.5616751。
        這是本次修正的**根證據**：0.5617 不是掰的，是模擬得出來的。
        """
        x = self._simulate(0.0, 1.0)
        sigma_a = math.sqrt(_T)
        measured_factor = float(x.std(ddof=1)) / sigma_a
        self.assertAlmostEqual(measured_factor / _bias_sd_factor(_N, _T), 1.0,
                               delta=0.03)

    def test_old_formula_is_wrong_by_1_78x(self):
        """模擬佐證舊式錯在哪：舊式的隱含假設是 SD(X) = σ_a（factor = 1），
        實測 factor ≈ 0.56 ⇒ 舊式的 σ 數被低估 1/0.56 ≈ 1.78 倍。"""
        x = self._simulate(0.0, 1.0)
        sigma_a = math.sqrt(_T)
        measured_factor = float(x.std(ddof=1)) / sigma_a
        self.assertLess(measured_factor, 0.60)
        self.assertGreater(measured_factor, 0.52)
        self.assertAlmostEqual(1.0 / measured_factor, 1.780384, delta=0.06)

    def test_drift_closed_form(self):
        """μ_d = 0.01、σ_d = 0.5 → 理論 E[X] = 0.01 × 119.5 = 1.195。
        SD(X) = 0.5 × 8.916316 = 4.458158，12000 條路徑的均值 SE ≈ 0.0407，
        容差 0.25 ≈ 6 SE（固定 seed，僅為抗 numpy 版本間的極小差異）。"""
        x = self._simulate(0.01, 0.5)
        theo_mean = 0.01 * (_N - 1) / 2.0
        self.assertAlmostEqual(theo_mean, 1.195, places=6)
        self.assertAlmostEqual(float(x.mean()), theo_mean, delta=0.25)

    def test_drift_factor_reproduces_simulation(self):
        """換算成年化：μ_a = μ_d × 252 = 2.52 ⇒ E[X]/μ_a 應 = _bias_drift_factor
        = 0.4742063（容差 0.10 ≈ 6 SE）。"""
        x = self._simulate(0.01, 0.5)
        mu_a = 0.01 * _T
        self.assertAlmostEqual(float(x.mean()) / mu_a,
                               _bias_drift_factor(_N, _T), delta=0.10)


if __name__ == '__main__':
    unittest.main()
