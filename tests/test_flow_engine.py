"""test_flow_engine.py — flow_engine 純計算單元測試。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.compute.macro import flow_engine as fe


class TestPctReturn(unittest.TestCase):
    def test_basic(self):
        # 100 → 110，近 1 日 = +10%
        self.assertEqual(fe.pct_return([100, 110], 1), 10.0)

    def test_multi_day(self):
        self.assertEqual(fe.pct_return([100, 105, 120], 2), 20.0)

    def test_insufficient(self):
        self.assertIsNone(fe.pct_return([100], 1))
        self.assertIsNone(fe.pct_return([], 1))

    def test_zero_prev(self):
        self.assertIsNone(fe.pct_return([0, 100], 1))


class TestZScore(unittest.TestCase):
    # v19.170：zscore_latest 新增 min_window（預設 60，原硬寫 30）。
    # 下列 40 點的既有案例改為顯式傳 min_window=30 —— 測的是 clip / 符號 /
    # 零標準差行為，非樣本門檻，故降門檻以保留原測試意圖。
    def test_insufficient(self):
        self.assertIsNone(fe.zscore_latest([1, 2, 3], window=252))

    def test_min_window_gate(self):
        # v19.170：40 點 < 預設 min_window=60 → 不得再冒充 252 日 Z-score
        self.assertIsNone(fe.zscore_latest([5.0] * 40))

    def test_flat_zero_std(self):
        self.assertEqual(fe.zscore_latest([5.0] * 40, min_window=30), 0.0)

    def test_clip(self):
        # 39 個 1.0 + 最後一個極大值 → Z 應被 clip 到 3.0
        series = [1.0] * 39 + [1000.0]
        self.assertEqual(fe.zscore_latest(series, clip=3.0, min_window=30), 3.0)

    def test_sign(self):
        # 最後一點高於平均 → 正 Z
        series = list(range(1, 41))  # 上升序列，最後一點最大
        z = fe.zscore_latest(series, min_window=30)
        self.assertIsNotNone(z)
        self.assertGreater(z, 0)


class TestRankRegionalFlow(unittest.TestCase):
    def test_ordering_and_filter(self):
        cm = {
            "A": [100, 110],   # +10%
            "B": [100, 105],   # +5%
            "C": [100, 90],    # -10%
            "D": [100],        # 不足 → 過濾
        }
        ranked = fe.rank_regional_flow(cm, days=1)
        self.assertEqual([n for n, _ in ranked], ["A", "B", "C"])
        self.assertEqual(ranked[0], ("A", 10.0))


class TestRiskScore(unittest.TestCase):
    def _trend(self, start, step, n=300):
        return [start + step * i for i in range(n)]

    def test_risk_on(self):
        # 股票漲、債跌、VIX 跌 → 應偏 risk-on（正分）
        cm = {
            "股票 SPY": self._trend(100, 0.5),
            "長天期美債 TLT": self._trend(150, -0.2),
            "VIX 波動率": self._trend(30, -0.05),
        }
        res = fe.compute_risk_score(cm)
        self.assertIsNotNone(res["score"])
        self.assertGreater(res["score"], 0)
        self.assertIn("Risk-on", res["label"])

    def test_risk_off(self):
        # 股票跌、債漲、VIX 漲 → 應偏 risk-off（負分）
        cm = {
            "股票 SPY": self._trend(250, -0.5),
            "長天期美債 TLT": self._trend(100, 0.2),
            "VIX 波動率": self._trend(15, 0.1),
        }
        res = fe.compute_risk_score(cm)
        self.assertIsNotNone(res["score"])
        self.assertLess(res["score"], 0)
        self.assertIn("Risk-off", res["label"])

    def test_insufficient(self):
        res = fe.compute_risk_score({"股票 SPY": [1, 2, 3]})
        self.assertIsNone(res["score"])
        self.assertEqual(res["components"], [])

    def test_score_bounds(self):
        cm = {
            "股票 SPY": [100.0] * 200 + [10000.0],
            "長天期美債 TLT": [100.0] * 200 + [0.01],
        }
        res = fe.compute_risk_score(cm)
        self.assertLessEqual(res["score"], 100)
        self.assertGreaterEqual(res["score"], -100)

    def test_contract_keys_preserved(self):
        """v19.170：既有 key 不得移除，新 key 需存在且自洽（下游 section_long 依賴）。"""
        cm = {
            "股票 SPY": self._trend(100, 0.5),
            "長天期美債 TLT": self._trend(150, -0.2),
            "VIX 波動率": self._trend(30, -0.05),
        }
        res = fe.compute_risk_score(cm)
        for k in ("score", "label", "components", "weighting", "weights", "n_effective"):
            self.assertIn(k, res)
        self.assertIn(res["weighting"], ("inv_corr", "equal"))
        self.assertEqual(len(res["weights"]), len(res["components"]))
        self.assertAlmostEqual(sum(w for _, w in res["weights"]), 1.0, places=3)
        self.assertGreaterEqual(res["n_effective"], 1.0)

    def test_degraded_flags_equal_weighting(self):
        """v19.170：相關矩陣算不出（只有 1 個成分）→ 顯式降級標 'equal'。"""
        cm = {
            "股票 SPY": self._trend(100, 0.5),
            "長天期美債 TLT": self._trend(150, -0.2),
        }
        res = fe.compute_risk_score(cm)
        self.assertEqual(len(res["components"]), 1)   # 只有 SPY/TLT 比率
        self.assertEqual(res["weighting"], "equal")
        self.assertEqual(res["n_effective"], 1.0)


# ══════════════════════════════════════════════════════════════════
# v19.171 迴歸測試：σ_p 的分子分母必須同源（水位 ρ），權重仍用差分 ρ
# ══════════════════════════════════════════════════════════════════
def _antiphase_pair(n=300, base=100, slope=1.0, amp=50.0):
    """造一對「水位高度相關、日變動完全反相關」的序列（用來分離兩種 ρ）。

        a[i] = base + slope·i + amp·(−1)^i
        b[i] = base + slope·i − amp·(−1)^i

    - **水位**：共同趨勢 slope·i 主導 → ρ(a,b) 明顯為正。
    - **日變動**：da 在 −99/+101 之間跳、db 恰為 2−da → ρ(da,db) = −1（精確）。
    這正是「水位 ρ ≠ 差分 ρ」的最小可控案例。
    """
    a = [base + slope * i + (amp if i % 2 == 0 else -amp) for i in range(n)]
    b = [base + slope * i - (amp if i % 2 == 0 else -amp) for i in range(n)]
    return a, b


class TestDirectionAdjustedCorr(unittest.TestCase):
    """v19.171：`use_diff` 兩種模式必須估出**不同**的 ρ（否則修正等於沒做）。"""

    def test_level_and_diff_corr_are_different_objects(self):
        # 手算：t=位置(方差 (N²−1)/12)、s=±50 交替(方差 2500, cov(t,s)=−25)
        #   ρ_level = (var t − 2500) / sqrt((var t −50+2500)(var t +50+2500))
        #   252 點視窗 → var t = 5291.92 → ρ_level ≈ +0.358
        #   ρ_diff  : da ∈ {−99, +101}、db = 2 − da → 精確 −1
        a, b = _antiphase_pair()
        sd = [(a, +1), (b, +1)]
        c_diff = fe._direction_adjusted_corr(sd, 252, use_diff=True)
        c_lvl = fe._direction_adjusted_corr(sd, 252, use_diff=False)
        self.assertIsNotNone(c_diff)
        self.assertIsNotNone(c_lvl)
        self.assertAlmostEqual(float(c_diff[0][1]), -1.0, places=6)
        self.assertGreater(float(c_lvl[0][1]), 0.2)      # 手算 ≈ +0.358
        self.assertLess(float(c_lvl[0][1]), 0.5)

    def test_direction_sign_flips_level_corr(self):
        """方向 d 不可省：把其中一條反向，水位 ρ 必須跟著變號。"""
        a, b = _antiphase_pair()
        pos = fe._direction_adjusted_corr([(a, +1), (b, +1)], 252, use_diff=False)
        neg = fe._direction_adjusted_corr([(a, -1), (b, +1)], 252, use_diff=False)
        self.assertAlmostEqual(float(pos[0][1]), -float(neg[0][1]), places=6)

    def test_constant_series_degrades_in_both_modes(self):
        """常數序列 → 水位 std=0、差分亦全 0 → 兩種模式都回 None（顯式降級，不猜）。"""
        const = [5.0] * 120
        ramp = [float(i) for i in range(120)]
        sd = [(const, +1), (ramp, +1)]
        self.assertIsNone(fe._direction_adjusted_corr(sd, 252, use_diff=True))
        self.assertIsNone(fe._direction_adjusted_corr(sd, 252, use_diff=False))

    def test_single_series_returns_none(self):
        a, _ = _antiphase_pair()
        self.assertIsNone(fe._direction_adjusted_corr([(a, +1)], 252, use_diff=False))
        self.assertIsNone(fe._direction_adjusted_corr([(a, +1)], 252, use_diff=True))

    def test_too_short_returns_none(self):
        a, b = _antiphase_pair(n=20)
        self.assertIsNone(fe._direction_adjusted_corr([(a, +1), (b, +1)], 252))


class TestSigmaPUsesLevelCorr(unittest.TestCase):
    """v19.171 修 🔴 數學錯誤：σ_p 必須用**水位** ρ（與分子的水位 z 同源）。

    舊實作把「差分 ρ」代進 wᵀρw。下面兩案在舊碼會走到 `var_p<=1e-12` 而降級
    成 'equal'（n_effective=1.0），修好後才會得到 'inv_corr' 與 >1 的有效成分數。
    """

    def test_level_corr_drives_sigma_p(self):
        """VIX(−1) 與 UUP(−1) 同結構反相位。

        手算：兩者方向皆 −1 → 方向調整後 ρ 不變。
          ρ_level ≈ +0.3583 → var_p = ¼(1+1+2×0.3583) = 0.6792
          σ_p = 0.8241（地板 1/√2 = 0.7071 未咬）→ n_eff = 1/0.6792 ≈ 1.47
        舊碼：ρ_diff = −1 → var_p = ¼(2−2) = 0 → 降級 'equal' → n_eff = 1.0。
        """
        a, b = _antiphase_pair()
        res = fe.compute_risk_score({"VIX 波動率": a, "美元 UUP": b})
        self.assertEqual(len(res["components"]), 2)
        self.assertEqual(res["weighting"], "inv_corr")
        self.assertGreater(res["n_effective"], 1.3)
        self.assertLess(res["n_effective"], 1.7)

    def test_sigma_p_floor_caps_n_effective_at_n(self):
        """VIX(−1) 與 USDJPY(+1)：方向調整後水位 ρ 轉負 → var_p 偏小 → 地板生效。

        手算：ρ_level = −0.3583 → var_p = ¼(2−0.7166) = 0.3208
              σ_p = 0.5664 < 1/√2 = 0.7071 → **地板咬住** → σ_p = 0.7071
              n_eff = 1/0.5 = 2.0 = n（無地板則 1/0.3208 = 3.12 > n，是假性放大）。
        """
        a, b = _antiphase_pair()
        res = fe.compute_risk_score({"VIX 波動率": a, "美元日圓 USDJPY": b})
        n = len(res["components"])
        self.assertEqual(n, 2)
        self.assertEqual(res["weighting"], "inv_corr")
        self.assertEqual(res["n_effective"], 2.0)       # 恰好等於 n，未超過

    def test_n_effective_never_exceeds_component_count(self):
        """不變式：1 <= n_effective <= n（σ_p 的地板 1/√n 與天花板 1 的直接推論）。"""
        cases = [
            {"VIX 波動率": _antiphase_pair()[0], "美元 UUP": _antiphase_pair()[1]},
            {"VIX 波動率": _antiphase_pair()[0],
             "美元日圓 USDJPY": _antiphase_pair()[1]},
            {"股票 SPY": [100 + 0.5 * i for i in range(300)],
             "長天期美債 TLT": [150 - 0.2 * i for i in range(300)],
             "VIX 波動率": [30 - 0.05 * i for i in range(300)]},
        ]
        for cm in cases:
            res = fe.compute_risk_score(cm)
            n = len(res["components"])
            self.assertGreaterEqual(res["n_effective"], 1.0)
            self.assertLessEqual(res["n_effective"], float(n))

    def test_score_still_bounded_with_level_corr(self):
        """換用水位 ρ 後 score 仍必須落在 ±100（clip 未失效）。"""
        a, b = _antiphase_pair()
        for cm in ({"VIX 波動率": a, "美元 UUP": b},
                   {"VIX 波動率": a, "美元日圓 USDJPY": b}):
            res = fe.compute_risk_score(cm)
            self.assertLessEqual(res["score"], 100)
            self.assertGreaterEqual(res["score"], -100)


# ══════════════════════════════════════════════════════════════════
# v19.172 契約測試：放大倍率 / σ_p / 缺席成分 三個「揭露」key
#
# 背景（誠實度 bug，非計算 bug）：score = (Σ w·d·z / σ_p)/3×100，σ_p 每日重估。
# 線上反推 σ_p = 0.473 → 分數被放大 2.11× 而使用者完全不知道，
# 且 47 距離「強烈 Risk-on」的 ±50 只差 3 分。本組測試釘住揭露欄位的存在與自洽。
# ══════════════════════════════════════════════════════════════════
class TestDisclosureKeys(unittest.TestCase):

    def _full_close_map(self, n=300):
        """涵蓋全部 7 個成分所需的 9 個 close_map key（斜率各異，避免常數序列）。"""
        def ramp(start, step):
            return [start + step * i for i in range(n)]
        return {
            "股票 SPY": ramp(100, 0.50),
            "長天期美債 TLT": ramp(150, -0.20),
            "高收益債 HYG": ramp(80, 0.11),
            "投資級債 LQD": ramp(110, -0.07),
            "美債波動 MOVE": ramp(90, 0.13),
            "VIX 波動率": ramp(30, -0.05),
            "美元 UUP": ramp(28, 0.03),
            "黃金 GLD": ramp(180, 0.17),
            "美元日圓 USDJPY": ramp(140, 0.09),
        }

    def test_expected_components_is_ssot_of_seven(self):
        """`EXPECTED_RISK_COMPONENTS` 必須剛好 7 個且不重複（missing 的分母）。"""
        exp = fe.EXPECTED_RISK_COMPONENTS
        self.assertEqual(len(exp), 7)
        self.assertEqual(len(set(exp)), 7)
        self.assertIn("美元日圓 USDJPY", exp)

    def test_missing_empty_when_all_present(self):
        """9 個 key 全給 → 7 個成分全到 → missing 為空，且順序等於 SSOT 名單。"""
        res = fe.compute_risk_score(self._full_close_map())
        self.assertEqual(len(res["components"]), 7)
        self.assertEqual(res["missing"], [])
        self.assertEqual([c[0] for c in res["components"]],
                         list(fe.EXPECTED_RISK_COMPONENTS))

    def test_missing_lists_absent_components(self):
        """線上實況重現：USDJPY 缺席時必須被點名（原本沒人知道少了它）。"""
        cm = self._full_close_map()
        cm.pop("美元日圓 USDJPY")
        res = fe.compute_risk_score(cm)
        self.assertEqual(len(res["components"]), 6)
        self.assertEqual(res["missing"], ["美元日圓 USDJPY"])

    def test_missing_covers_all_when_no_component(self):
        """完全沒資料 → 7 個全列 missing；σ_p / amplification 回 None（不捏造 1.0）。"""
        res = fe.compute_risk_score({"股票 SPY": [1, 2, 3]})
        self.assertIsNone(res["score"])
        self.assertEqual(res["missing"], list(fe.EXPECTED_RISK_COMPONENTS))
        self.assertIsNone(res["sigma_p"])
        self.assertIsNone(res["amplification"])

    def test_degraded_path_amplification_is_one(self):
        """降級（相關矩陣算不出）→ σ_p = 1、放大倍率 = 1（不因降級而放大）。"""
        cm = {"股票 SPY": [100 + 0.5 * i for i in range(300)],
              "長天期美債 TLT": [150 - 0.2 * i for i in range(300)]}
        res = fe.compute_risk_score(cm)
        self.assertEqual(res["weighting"], "equal")
        self.assertEqual(res["sigma_p"], 1.0)
        self.assertEqual(res["amplification"], 1.0)

    def test_amplification_equals_inverse_sigma_p(self):
        """手算：VIX(−1) 與 UUP(−1)，ρ_level ≈ +0.3583、等權
        → var_p = ¼(2 + 2×0.3583) = 0.67915 → σ_p = 0.8241
        → amplification = 1/0.8241 = **1.213**、n_eff = 1/0.67915 = **1.47**
        （amplification² 必須等於 n_effective，兩者同源不可漂移）。
        """
        a, b = _antiphase_pair()
        res = fe.compute_risk_score({"VIX 波動率": a, "美元 UUP": b})
        self.assertEqual(res["weighting"], "inv_corr")
        self.assertAlmostEqual(res["sigma_p"], 0.8241, delta=0.002)
        self.assertAlmostEqual(res["amplification"], 1.213, delta=0.003)
        self.assertAlmostEqual(res["amplification"] ** 2, res["n_effective"],
                               delta=0.01)

    def test_amplification_hits_sqrt_n_ceiling(self):
        """手算：VIX(−1) 與 USDJPY(+1) → ρ_level = −0.3583 → σ_p 被地板 1/√2 咬住
        → σ_p = 0.70711、amplification = √2 = **1.414**（= 理論上限 √n）。
        本例 >= UI 的 1.3 揭露門檻，正是「該跳警告」的情境。
        """
        a, b = _antiphase_pair()
        res = fe.compute_risk_score({"VIX 波動率": a, "美元日圓 USDJPY": b})
        self.assertEqual(res["sigma_p"], 0.7071)
        self.assertAlmostEqual(res["amplification"], 1.4142, delta=0.001)
        self.assertGreaterEqual(res["amplification"], 1.3)

    def test_amplification_bounds_across_cases(self):
        """不變式：1 <= amplification <= √n（σ_p ∈ [1/√n, 1] 的直接推論）。"""
        a, b = _antiphase_pair()
        cases = [
            self._full_close_map(),
            {"VIX 波動率": a, "美元 UUP": b},
            {"VIX 波動率": a, "美元日圓 USDJPY": b},
        ]
        for cm in cases:
            res = fe.compute_risk_score(cm)
            n = len(res["components"])
            self.assertGreaterEqual(res["amplification"], 1.0)
            self.assertLessEqual(res["amplification"], (n ** 0.5) + 1e-9)
            self.assertAlmostEqual(res["amplification"],
                                   1.0 / res["sigma_p"], delta=0.002)


class TestRiskLabelBoundariesUnchanged(unittest.TestCase):
    """v19.172 只把 ±15 / ±50 抽成具名常數 + 加註解，**數值與判級行為不得變**
    （改門檻須先回測，見 flow_engine `_risk_label` 上方註解）。"""

    def test_design_values(self):
        self.assertEqual(fe._RISK_LABEL_STRONG, 50)
        self.assertEqual(fe._RISK_LABEL_MILD, 15)

    def test_boundary_behaviour(self):
        self.assertIn("強烈 Risk-on", fe._risk_label(50))
        self.assertIn("偏 Risk-on", fe._risk_label(49))
        self.assertIn("偏 Risk-on", fe._risk_label(15))
        self.assertIn("中性", fe._risk_label(14))
        self.assertIn("中性", fe._risk_label(0))
        self.assertIn("中性", fe._risk_label(-14))
        self.assertIn("偏 Risk-off", fe._risk_label(-15))
        self.assertIn("偏 Risk-off", fe._risk_label(-49))
        self.assertIn("強烈 Risk-off", fe._risk_label(-50))


if __name__ == "__main__":
    unittest.main()
