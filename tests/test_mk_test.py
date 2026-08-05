"""tests/test_mk_test.py — `shared/mk_test.py`（真 Mann-Kendall）單元測試（v19.173）。

每一條斷言的期望值都先手算過（推導寫在各 test 的 docstring 裡），
不是「跑一次看輸出再貼回來」——那種寫法只能鎖住現狀，鎖不住正確性。

共用手算基礎（無 tie 時）
------------------------
    Var(S) = n(n−1)(2n+5) / 18
    n=4 → 4·3·13/18 = 156/18 = 8.6667
    n=5 → 5·4·15/18 = 300/18 = 50/3 ≈ 16.6667
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest

from shared.mk_test import (
    MK_MIN_SAMPLES,
    MK_RECOMMENDED_SAMPLES,
    MannKendallResult,
    mann_kendall,
    norm_cdf,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MK_SRC_PATH = _REPO_ROOT / 'shared' / 'mk_test.py'


class TestLayerHygiene:
    """L0 依賴守門：shared/ 不得碰 UI / 網路，且本專案無 scipy。"""

    def test_no_forbidden_imports(self):
        _src = _MK_SRC_PATH.read_text(encoding='utf-8')
        _bad = re.findall(
            r'^\s*(?:import|from)\s+(streamlit|requests|scipy)\b',
            _src, flags=re.MULTILINE)
        assert not _bad, f'shared/mk_test.py 不得 import：{sorted(set(_bad))}'

    def test_no_nested_python_loops(self):
        """S 與 Sen's slope 必須向量化 —— 出現 `for` 巢狀就是退化成 O(n²) Python 迴圈。

        以「函式本體是否有兩個以上 for 陳述式」當粗略守門（註解/docstring 不算，
        因為它們不含 `for ... in ...` 的陳述式語法）。
        """
        _src = _MK_SRC_PATH.read_text(encoding='utf-8')
        _fors = [ln for ln in _src.splitlines()
                 if re.match(r'^\s*for\s+\w', ln)]
        assert not _fors, f'不得用 Python for 迴圈（應向量化）：{_fors}'


class TestNormCdf:
    """Φ(z) = 0.5·(1 + erf(z/√2))，用 math.erf 組（無 scipy）。"""

    def test_zero(self):
        assert norm_cdf(0.0) == pytest.approx(0.5, abs=1e-12)

    def test_symmetry(self):
        """Φ(−z) = 1 − Φ(z)。"""
        for z in (0.5, 1.0, 1.96, 3.0):
            assert norm_cdf(-z) == pytest.approx(1.0 - norm_cdf(z), abs=1e-12)

    def test_known_quantiles(self):
        """教科書值：Φ(1.959964) = 0.975、Φ(1.644854) = 0.95。"""
        assert norm_cdf(1.959964) == pytest.approx(0.975, abs=1e-6)
        assert norm_cdf(1.644854) == pytest.approx(0.95, abs=1e-6)


class TestStrictlyIncreasing:
    """嚴格遞增：S = n(n−1)/2（所有配對皆 +1）。

    手算（x = [1,2,3,4,5]，n=5，無 tie）
    -----------------------------------
    配對數 = 5·4/2 = 10，全部 sgn = +1  → S = 10 = n(n−1)/2 ✔
    Var(S) = 5·4·15/18 = 300/18 = 50/3 ≈ 16.6667
    Z = (S−1)/√Var = 9 / 4.082483 = 2.204541
    p = 2(1 − Φ(2.204541)) ≈ 2(1 − 0.986254) ≈ 0.02749  →  < 0.05 ✔
    Sen's β = median{全部 (x_j−x_i)/(j−i)} = median{1,1,…,1} = 1.0 ✔
    """

    def test_s_equals_n_choose_2(self):
        r = mann_kendall([1, 2, 3, 4, 5])
        assert r is not None
        assert r.n == 5
        assert r.S == pytest.approx(5 * 4 / 2)

    def test_var_s_no_tie_formula(self):
        r = mann_kendall([1, 2, 3, 4, 5])
        assert r.var_s == pytest.approx(300 / 18)

    def test_z_and_p(self):
        r = mann_kendall([1, 2, 3, 4, 5])
        assert r.z == pytest.approx(9 / math.sqrt(300 / 18), rel=1e-12)
        assert r.z == pytest.approx(2.204541, abs=1e-5)
        assert 0.02 < r.p < 0.04            # 手算 ≈ 0.0275
        assert r.trend == 'increasing'

    def test_sen_slope_is_one(self):
        r = mann_kendall([1, 2, 3, 4, 5])
        assert r.sen_slope == pytest.approx(1.0)

    def test_monotone_but_uneven_still_max_s(self):
        """S 只看**順序**，不看間距 —— 任意嚴格遞增序列 S 都是 n(n−1)/2。"""
        r = mann_kendall([0.1, 0.5, 0.6, 2.0, 9.9])
        assert r.S == pytest.approx(10.0)
        assert r.trend == 'increasing'


class TestStrictlyDecreasing:
    """嚴格遞減：S = −n(n−1)/2，Z 用 (S+1)/√Var。

    手算（x = [5,4,3,2,1]，n=5）
    ---------------------------
    S = −10；Var(S) = 50/3（同上，無 tie）
    Z = (−10+1)/4.082483 = −2.204541
    p 與遞增情形相同（雙尾） ≈ 0.0275 < 0.05
    Sen's β = median{全部 −1} = −1.0
    """

    def test_full_result(self):
        r = mann_kendall([5, 4, 3, 2, 1])
        assert r.S == pytest.approx(-10.0)
        assert r.var_s == pytest.approx(300 / 18)
        assert r.z == pytest.approx(-9 / math.sqrt(300 / 18), rel=1e-12)
        assert 0.02 < r.p < 0.04
        assert r.trend == 'decreasing'
        assert r.sen_slope == pytest.approx(-1.0)

    def test_reversal_flips_s_sign(self):
        """把序列反轉，所有配對的 sgn 都翻號 → S → −S（無 tie 時）。"""
        up = mann_kendall([1, 2, 3, 4, 5, 6, 7])
        down = mann_kendall([7, 6, 5, 4, 3, 2, 1])
        assert down.S == pytest.approx(-up.S)
        assert down.z == pytest.approx(-up.z)
        assert down.p == pytest.approx(up.p)


class TestAllIdentical:
    """全同值：tie 修正把 Var(S) 打成 0，必須回 z=0 / p=1，且**不除零**。

    手算（x = [3,3,3,3,3]，n=5）
    ---------------------------
    所有配對 sgn = 0 → S = 0
    tie：只有一組，t = 5 → Σ t(t−1)(2t+5) = 5·4·15 = 300
    Var(S) = (5·4·15 − 300)/18 = (300 − 300)/18 = 0  ✔
    → z = 0、p = 1、trend = 'no trend'
    Sen's β = median{全部 0} = 0.0
    """

    def test_zero_variance_no_division_error(self):
        r = mann_kendall([3, 3, 3, 3, 3])
        assert r is not None
        assert r.S == 0.0
        assert r.var_s == pytest.approx(0.0)
        assert r.z == 0.0
        assert r.p == 1.0
        assert r.trend == 'no trend'
        assert r.sen_slope == pytest.approx(0.0)


class TestTieCorrection:
    """含 tie 時 Var(S) 必須變小（有效配對數下降）。

    手算（x = [1, 1, 2, 3]，n=4）
    ----------------------------
    S：配對 (0,1)=0、(0,2)=+1、(0,3)=+1、(1,2)=+1、(1,3)=+1、(2,3)=+1 → S = 5
    tie：值 1 出現 2 次（t=2），值 2、3 各 1 次（t=1，其項 = 0）
         Σ t(t−1)(2t+5) = 2·1·9 = 18
    無 tie 版 Var = 4·3·13/18 = 156/18 = 8.6667
    含 tie 版 Var = (156 − 18)/18 = 138/18 = 7.6667  ← 確實變小 ✔
    Z = (5−1)/√7.6667 = 4/2.768875 = 1.444632
    p = 2(1 − Φ(1.444632)) ≈ 2(1 − 0.92573) ≈ 0.1485  → > 0.05 → 'no trend' ✔
    Sen's β：slopes = [0/1, 1/2, 2/3, 1/1, 2/2, 1/1] = [0, .5, .6667, 1, 1, 1]
             排序後取中間兩個平均 = (2/3 + 1)/2 = 5/6 ≈ 0.83333 ✔
    """

    _X = [1, 1, 2, 3]

    def test_s_counts_tie_as_zero(self):
        r = mann_kendall(self._X)
        assert r.S == pytest.approx(5.0)

    def test_var_s_shrinks_by_tie_term(self):
        r = mann_kendall(self._X)
        assert r.var_s == pytest.approx(138 / 18)
        assert r.var_s < 156 / 18          # 沒做 tie 修正的話會是 156/18

    def test_z_p_and_trend(self):
        r = mann_kendall(self._X)
        assert r.z == pytest.approx(4 / math.sqrt(138 / 18), rel=1e-12)
        assert r.z == pytest.approx(1.444632, abs=1e-5)
        assert r.p == pytest.approx(0.1485, abs=5e-4)
        assert r.trend == 'no trend'       # 小樣本 + tie → 測不出來，這是正確行為

    def test_sen_slope_median_of_pairwise(self):
        r = mann_kendall(self._X)
        assert r.sen_slope == pytest.approx(5 / 6)


class TestSenSlopeOnLinearSeries:
    """線性序列 x_t = a + b·t → 所有 pairwise slope 都是 b → median = b。"""

    def test_exact_slope_positive(self):
        # x = [2, 5, 8, 11, 14] → b = 3
        r = mann_kendall([2, 5, 8, 11, 14])
        assert r.sen_slope == pytest.approx(3.0)
        assert r.trend == 'increasing'

    def test_exact_slope_negative_fractional(self):
        # x = [10, 9.5, 9, 8.5, 8, 7.5] → b = −0.5，n=6
        r = mann_kendall([10, 9.5, 9, 8.5, 8, 7.5])
        assert r.sen_slope == pytest.approx(-0.5)
        assert r.S == pytest.approx(-(6 * 5 / 2))
        assert r.trend == 'decreasing'

    def test_robust_to_single_outlier(self):
        """Sen's slope 對單一離群值穩健（對比 OLS 會被拉走）。

        x = [0,1,2,3,4,5,6,7,8,100]：前 9 點斜率 1，最後一點被汙染。
        pairwise slope 共 C(10,2)=45 個：不含最後一點的 C(9,2)=36 個全部剛好 = 1，
        含最後一點的只有 9 個（值 11.1~92）。45 個數的中位數是第 23 小，
        23 <= 36 → 中位數仍是 1.0。
        （對照組手算：OLS 斜率 = Σ(t−t̄)(y−ȳ)/Σ(t−t̄)² = 492.0/82.5 = 5.96，
          被單一離群值拉高近 6 倍。）
        """
        x = [0, 1, 2, 3, 4, 5, 6, 7, 8, 100]
        r = mann_kendall(x)
        assert r.sen_slope == pytest.approx(1.0)
        _ols = float(np.polyfit(np.arange(len(x), dtype=float),
                                np.asarray(x, dtype=float), 1)[0])
        assert _ols > 4.0                  # OLS 確實被汙染，Sen's 沒有


class TestSmallSampleGuard:
    """n < MK_MIN_SAMPLES → None（§1：不給沒有檢定力的數字）。"""

    def test_min_samples_is_four(self):
        assert MK_MIN_SAMPLES == 4
        assert MK_RECOMMENDED_SAMPLES >= MK_MIN_SAMPLES

    def test_three_points_returns_none(self):
        assert mann_kendall([1, 2, 3]) is None

    def test_two_points_returns_none(self):
        assert mann_kendall([1, 2]) is None

    def test_empty_returns_none(self):
        assert mann_kendall([]) is None

    def test_exactly_four_works(self):
        """n=4 是門檻邊界：可以算，但完美單調也達不到 alpha=0.05。

        手算：S_max = 6、Var = 156/18 = 8.6667、Z = 5/2.943920 = 1.698417
              p = 2(1 − Φ(1.698417)) ≈ 0.0894  → 'no trend'（檢定力不足）
        """
        r = mann_kendall([1, 2, 3, 4])
        assert r is not None
        assert r.n == 4
        assert r.S == pytest.approx(6.0)
        assert r.z == pytest.approx(5 / math.sqrt(156 / 18), rel=1e-12)
        assert r.p == pytest.approx(0.0894, abs=5e-4)
        assert r.trend == 'no trend'
        assert r.underpowered is True


class TestNaNHandling:
    """NaN / inf 顯式剔除 + 記錄筆數（§3.3：dropna 必須可稽核）。"""

    def test_nan_dropped_and_counted(self):
        """[1, nan, 2, 3, 4, 5] → 剔除 1 筆後等同 [1,2,3,4,5]。"""
        r = mann_kendall([1, float('nan'), 2, 3, 4, 5])
        assert r is not None
        assert r.n == 5
        assert r.n_dropped == 1
        assert r.S == pytest.approx(10.0)
        assert r.var_s == pytest.approx(300 / 18)
        assert r.sen_slope == pytest.approx(1.0)

    def test_none_is_treated_as_nan(self):
        r = mann_kendall([1, None, 2, 3, 4, 5])
        assert r.n == 5 and r.n_dropped == 1

    def test_inf_dropped(self):
        r = mann_kendall([1, 2, float('inf'), 3, 4, 5])
        assert r.n == 5 and r.n_dropped == 1

    def test_all_nan_returns_none(self):
        assert mann_kendall([float('nan')] * 10) is None

    def test_drop_below_min_returns_none(self):
        """剔除後不足 4 筆 → None（不是「用剩下的硬算」）。"""
        assert mann_kendall([1, 2, 3, float('nan'), float('nan')]) is None

    def test_sen_slope_lag_uses_index_after_drop(self):
        """⚠️ 誠實揭露：剔除 NaN 後索引會**重編**，Sen's β 的分母是重編後的距離。

        [0, nan, 2] 剔除後變 [0, 2]，若還有第 4 點就會被當成「相鄰兩期」。
        這裡釘住這個行為，避免日後有人以為它用的是原始時間軸。
        """
        r = mann_kendall([0.0, float('nan'), 2.0, 4.0, 6.0])
        assert r.n == 4 and r.n_dropped == 1
        assert r.sen_slope == pytest.approx(2.0)   # 不是 1.5（原始時間軸下的斜率）


class TestAlphaParameterisation:
    """alpha 可調，且判定完全由 p < alpha 決定。"""

    def test_alpha_005_significant_alpha_001_not(self):
        """x=[1..5] 的 p ≈ 0.0275：落在 0.01 與 0.05 之間，是乾淨的分界樣本。"""
        assert mann_kendall([1, 2, 3, 4, 5], alpha=0.05).trend == 'increasing'
        assert mann_kendall([1, 2, 3, 4, 5], alpha=0.01).trend == 'no trend'

    def test_alpha_recorded_in_result(self):
        r = mann_kendall([1, 2, 3, 4, 5], alpha=0.10)
        assert r.alpha == pytest.approx(0.10)

    @pytest.mark.parametrize('bad', [0.0, 1.0, -0.1, 1.5, float('nan')])
    def test_invalid_alpha_raises(self, bad):
        """§1 Fail Loud：參數錯是程式 bug，不得靜默改成預設值。"""
        with pytest.raises(ValueError):
            mann_kendall([1, 2, 3, 4, 5], alpha=bad)

    def test_alpha_validated_before_data(self):
        """參數合法性先於資料可用性 —— 即使樣本不足也要 raise，不是回 None。"""
        with pytest.raises(ValueError):
            mann_kendall([1, 2], alpha=-1.0)


class TestInputTypes:
    def test_numpy_array(self):
        r = mann_kendall(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
        assert r.S == pytest.approx(10.0)

    def test_pandas_series(self):
        pd = pytest.importorskip('pandas')
        r = mann_kendall(pd.Series([1, 2, 3, 4, 5]))
        assert r.S == pytest.approx(10.0)

    def test_2d_is_ravelled(self):
        r = mann_kendall(np.array([[1, 2], [3, 4]]))
        assert r is not None and r.n == 4

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            mann_kendall(['a', 'b', 'c', 'd'])


class TestResultContract:
    def test_is_frozen_dataclass(self):
        r = mann_kendall([1, 2, 3, 4, 5])
        assert isinstance(r, MannKendallResult)
        with pytest.raises(Exception):
            r.z = 999.0            # frozen：結果不可被下游竄改

    def test_as_dict_has_required_keys(self):
        d = mann_kendall([1, 2, 3, 4, 5]).as_dict()
        for _k in ('n', 'S', 'var_s', 'z', 'p', 'sen_slope', 'trend'):
            assert _k in d, f'回傳契約缺欄位：{_k}'

    def test_summary_is_human_readable(self):
        s = mann_kendall([5, 4, 3, 2, 1]).summary()
        assert s.startswith('MK: Z = ')
        assert 'p = ' in s and 'n = 5' in s

    def test_p_in_unit_interval(self):
        """p 永遠落在 [0, 1]（浮點誤差不得讓它越界）。"""
        for _x in ([1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [3, 3, 3, 3],
                   list(range(40)), list(range(40, 0, -1))):
            r = mann_kendall(_x)
            assert r is not None
            assert 0.0 <= r.p <= 1.0

    def test_underpowered_flag(self):
        assert mann_kendall(list(range(5))).underpowered is True
        assert mann_kendall(list(range(20))).underpowered is False


class TestPropertyLike:
    """輕量 property-based（固定種子，不引入 hypothesis 依賴）。"""

    def test_shift_invariance(self):
        """S / Z / p 只看順序 → 整體平移常數不改變任何統計量。"""
        rng = np.random.default_rng(20260805)
        x = rng.normal(size=30)
        a = mann_kendall(x)
        b = mann_kendall(x + 1000.0)
        assert a.S == pytest.approx(b.S)
        assert a.z == pytest.approx(b.z)
        assert a.p == pytest.approx(b.p)
        # +1000 後做差會有災難性抵消（誤差 ~1000·2⁻⁵³ ≈ 1e-13），
        # 故 Sen's β 用絕對容差比對；§4.3 禁止 `==` 直接比浮點。
        assert a.sen_slope == pytest.approx(b.sen_slope, abs=1e-9)

    def test_positive_scaling_invariance_of_s(self):
        """乘正數不改變 sgn → S 不變；Sen's β 等比例縮放。"""
        rng = np.random.default_rng(19731)
        x = rng.normal(size=25)
        a = mann_kendall(x)
        b = mann_kendall(x * 3.0)
        assert a.S == pytest.approx(b.S)
        assert b.sen_slope == pytest.approx(a.sen_slope * 3.0)

    def test_white_noise_rarely_significant(self):
        """白噪音在 alpha=0.05 下應該多數不顯著（固定種子，避免 flaky）。"""
        rng = np.random.default_rng(4242)
        _hits = sum(
            1 for _ in range(50)
            if mann_kendall(rng.normal(size=40)).trend != 'no trend'
        )
        # 理論期望 ≈ 50 × 0.05 = 2.5；放寬到 10 仍能抓到「永遠顯著」的實作錯誤
        assert _hits <= 10, f'白噪音誤報 {_hits}/50 次，Var(S) 或 Z 可能算錯'

    def test_s_bounded_by_pair_count(self):
        """|S| <= n(n−1)/2 恆成立（不變量）。"""
        rng = np.random.default_rng(7)
        for _n in (5, 12, 33):
            r = mann_kendall(rng.normal(size=_n))
            assert abs(r.S) <= _n * (_n - 1) / 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
