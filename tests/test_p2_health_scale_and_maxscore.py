"""2026-08-19 — 總經 health 的兩個尺度問題（user 核准後修）。

問題一｜「積極」級 20 年 0 次 —— 尺度借用錯誤
--------------------------------------------
`THROTTLE_HEALTH_A` 原為 80，註解寫「對齊 HEALTH_GRADE_A_MIN」。但那是
**個股六因子健康分**的 A 級線（趨勢30+RSI20+量比15+IBS10+KD15+布林10，
滿分 100 且真的會到 80+），與總經 health 是兩個不同尺度的量。

`shared/health_thresholds.py` 的模組 docstring **自己就禁止這種借用**：
    「本模組僅收個股健康度評分 0~100 的 A/B/C 三級分界…不收市場曝險、
      廣度評分、ETF 星評等獨立評分系統的閾值——那些屬不同維度。」

總經 health = 0.6×jqavg + 0.4×score_pct，而 jqavg（σ=3.32）在數學上是個
準常數 ≈ +29.8（貢獻 health 變異僅 2.8%）⇒ 值域被壓成 [21.6, 78.1]。
要 health ≥ 80 需 score_pct=100 **且** jqavg ≥ 66.7 —— 後者 20 年只有 2 天，
兩者同時成立 0 天。

問題二｜max_score 浮動讓「缺資料」變成「利多」
---------------------------------------------
`market_regime` 的 `_max = 4.0 + (ad_ratio有值) + (m1b_m2_gap有值)`。
同一組原始 score，腿缺席時分母縮小 ⇒ 百分比**上升**。
`market_assessment_apply` 的備援分支原本漏傳 `m1b_m2_gap`，於是同一天走
主路徑 vs 備援路徑會算出不同分數（實測 12.4% 的交易日換 tier，方向偏綠）。

與 P1（commit 5ab04cf）修的 6 處同一類病、方向相反。
"""
import inspect

import pytest

from shared.position_throttle import (
    THROTTLE_HEALTH_A, THROTTLE_HEALTH_B, THROTTLE_HEALTH_DEF,
    THROTTLE_TIERS, compute_position_throttle,
)
from src.services.market_strategy import market_regime


# ══════════════════════════════════════════════════════════════
# 問題一：A 切點必須落在總經 health 的實際值域內
# ══════════════════════════════════════════════════════════════
#: 2007-01-12~2026-07-21、n=4,769 的實測值域（scripts/calibrate_macro_traffic.run_backtest）
MEASURED_HEALTH_MIN, MEASURED_HEALTH_MAX = 21.6, 78.1


class TestHealthScaleBoundaries:

    def test_aggressive_cut_is_inside_observed_range(self):
        """A 切點若落在觀測值域之外，該級就是永遠不亮的死燈。"""
        assert MEASURED_HEALTH_MIN < THROTTLE_HEALTH_A < MEASURED_HEALTH_MAX, (
            f'THROTTLE_HEALTH_A={THROTTLE_HEALTH_A} 落在總經 health 實際值域 '
            f'[{MEASURED_HEALTH_MIN}, {MEASURED_HEALTH_MAX}] 之外 → 「積極」級永不觸發')

    def test_aggressive_cut_not_borrowed_from_stock_grade(self):
        """不得再退回個股六因子分的 80（借出方 docstring 明文禁止跨尺度借用）。"""
        from shared.health_thresholds import HEALTH_GRADE_A_MIN
        assert HEALTH_GRADE_A_MIN == 80, '個股 A 級線本身不該被本次變更動到'
        assert THROTTLE_HEALTH_A != HEALTH_GRADE_A_MIN, (
            '總經 health 的 A 切點不可對齊個股六因子分的 A 級線 —— 兩者尺度不同')

    def test_cuts_remain_strictly_descending(self):
        assert THROTTLE_HEALTH_A > THROTTLE_HEALTH_B > THROTTLE_HEALTH_DEF > 0

    def test_tier_table_still_sorted_and_covers_zero(self):
        mins = [t[0] for t in THROTTLE_TIERS]
        assert mins == sorted(mins, reverse=True), 'tier 表必須由高到低'
        assert mins[-1] == 0, '最後一級必須涵蓋 health=0'

    def test_aggressive_tier_is_actually_reachable(self):
        """在觀測值域上端，積極級必須真的會亮。"""
        r = compute_position_throttle(MEASURED_HEALTH_MAX, regime='bull')
        assert r['posture'] == '積極', (
            f'health={MEASURED_HEALTH_MAX}（20 年實測最高）仍非積極 → 該級不可達')

    @pytest.mark.parametrize('health,expect', [
        (78.1, '積極'), (65, '積極'), (64.9, '中性偏多'),
        (50, '中性偏多'), (49.9, '轉守'), (35, '轉守'), (34.9, '防禦'), (21.6, '防禦'),
    ])
    def test_band_edges(self, health, expect):
        assert compute_position_throttle(health, regime='bull')['posture'] == expect

    def test_defense_band_unchanged_by_this_change(self):
        """本次只動 A 切點；防禦帶天數必須完全不受影響（依定義）。"""
        assert THROTTLE_HEALTH_DEF == 35
        assert THROTTLE_TIERS[-1][1:3] == (0, 20)


# ══════════════════════════════════════════════════════════════
# 問題二：缺資料不得讓分數變好
# ══════════════════════════════════════════════════════════════
class TestMaxScoreDoesNotRewardMissingData:

    @staticmethod
    def _pct(r):
        return r['score'] / r['max_score'] * 100

    def test_missing_leg_is_disclosed(self):
        r = market_regime(100, 90, 80, 1e9, ad_ratio=None, m1b_m2_gap=None)
        assert r['score_partial'] is True
        assert '市場廣度' in r['missing_factors']
        assert 'M1B-M2 資金活水' in r['missing_factors']

    def test_full_inputs_report_no_missing(self):
        r = market_regime(100, 90, 80, 1e9, ad_ratio=60.0,
                          m1b_m2_gap=1.0, m1b_m2_prev=0.5)
        assert r['score_partial'] is False
        assert r['missing_factors'] == []
        assert r['max_score'] == 6.0

    def test_renormalisation_asymmetry_is_known_and_must_be_disclosed(self):
        """釘住一個**不可消除、只能揭露**的性質（這條測試本身就是文件）。

        權重歸一化下，「腿缺席」的 score_pct 必然高於「腿有值但拿 0 分」：
            有值但偏弱 -> 1/6 = 16.7%
            兩腿都缺   -> 1/4 = 25.0%

        為什麼不「修掉」它
        ------------------
        唯一能讓兩者相等的做法，是缺腿時不縮分母（即把缺席當 0 分）——
        那正是 P1（commit 5ab04cf）明令禁止的「缺資料被編碼成利空」。
        兩種編碼各有一個方向的偏誤，沒有中立選項：

            縮分母（現行）-> 「不知道」看起來比「知道它不好」更樂觀
            不縮分母      -> 「不知道」直接等於最壞情況（P1 已否決）

        本專案的立場：選擇歸一化（與 macro_helpers 對 jqavg 的處理一致），
        並強制揭露。這條測試釘的就是「揭露不得消失」。

        真正的 bug 不是這個不對稱，而是同一天走不同程式路徑得到不同分母
        —— 那個由 TestFallbackPathPassesAllLegs 守住。
        """
        weak = market_regime(100, 90, 80, 1e9, ad_ratio=30.0,
                             m1b_m2_gap=-1.0, m1b_m2_prev=-0.5)
        absent = market_regime(100, 90, 80, 1e9, ad_ratio=None, m1b_m2_gap=None)
        # 不對稱存在（若哪天不存在了，代表有人改了歸一化語意，該回來重讀本 docstring）
        assert self._pct(absent) > self._pct(weak), (
            '歸一化語意似乎被改動 —— 請重讀本測試 docstring 再決定是否更新')
        # 但缺席必須被標出來，否則消費端無從得知這個偏誤
        assert absent['score_partial'] is True and absent['missing_factors']
        assert weak['score_partial'] is False and weak['missing_factors'] == []



class TestFallbackPathPassesAllLegs:
    """`market_assessment_apply` 的備援分支必須與主分支傳一樣的腿。

    原 bug：主分支傳 m1b_m2_gap、備援分支沒傳 ⇒ 同一天走哪條路徑算出不同分母，
    進而算出不同分數（實測 12.4% 的交易日換 tier，方向偏綠）。

    用 AST 找真正的 Call node 而非字串切割 —— 該函式的 docstring 裡就寫著
    「get_market_assessment(...)主路徑」，字串比對會把它誤判成一處呼叫。
    """

    def test_all_call_sites_pass_the_same_optional_legs(self):
        import ast
        from src.services import market_assessment_apply as mod

        tree = ast.parse(inspect.getsource(mod.compute_and_apply_market_assessment))
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, 'id', None) == 'get_market_assessment']
        assert len(calls) >= 2, f'應有主分支與備援分支兩處呼叫，實得 {len(calls)}'

        for i, call in enumerate(calls, 1):
            kw = {k.arg for k in call.keywords}
            for leg in ('m1b_m2_gap', 'ad_ratio', 'foreign_net'):
                assert leg in kw, (
                    f'第 {i} 處 get_market_assessment 呼叫未傳 {leg} '
                    f'（實傳 {sorted(kw)}）→ 分母浮動，同一天不同路徑會算出不同分數')
