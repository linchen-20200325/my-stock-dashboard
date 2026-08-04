"""tests/test_allocation_decision.py — 建議持股 SSOT 純函式測試（v19.171 新增）。

`shared/allocation_decision.py` 的 `build_allocation_decision()` 是全站**唯一**
的持股仲裁點（稽核 P0-1：同一份資料曾並存 6 套互相矛盾的持股建議），
但在 v19.170 落地時是**零測試覆蓋**。本檔補上。

範圍
----
只測 L0 純函式（`shared/allocation_decision.py`），**不碰 streamlit** ——
`src/services/allocation_service.py` 的 session_state 接線屬另案。

核心規則（本檔守的不變式）::

    final_hi = min(posture_hi, min(caps))
    final_lo = min(posture_lo, final_hi)
    final_mid = round((final_lo + final_hi) / 2)

亦即「姿態油門決定該多積極，硬否決決定最多能到哪，取兩者較低」。
"""
from __future__ import annotations

import pytest

from shared.allocation_decision import (
    DEFENSE_HI_PCT,
    AllocationDecision,
    Cap,
    allocation_sleeves,
    build_allocation_decision,
    ring_gate_cap,
    vix_veto_cap,
)


def _ms(health=None, regime='neutral', defense=False,
        exposure_limit_pct=None, is_loaded=True) -> dict:
    """組一份 macro_state dict（等同 macro_state_locker.get_macro_state() 的輸出）。"""
    return {
        'is_loaded': is_loaded,
        'regime': regime,
        'health': health,
        'defense': defense,
        'exposure_limit_pct': exposure_limit_pct,
    }


# ════════════════════════════════════════════════════════════════
# A. 核心仲裁規則
# ════════════════════════════════════════════════════════════════
class TestArbitrationCore:
    """throttle 一律不外傳 → 由 build_allocation_decision 自行呼叫
    `compute_position_throttle(health, regime, defense)` 現算（與 production 同路徑）。"""

    def test_cap_below_posture_collapses_range(self):
        """health=43 → 轉守 30–50%；三環第一環 ≤20% → 最終塌成 20–20%。

        手算：43 落在 THROTTLE_TIERS 的 (35, 30, 50, '轉守') → lo=30, hi=50。
        regime='neutral' 不在 THROTTLE_VETO_REGIMES 且 defense=False → 不否決。
        cap=20 → final_hi=min(50,20)=20；final_lo=min(30,20)=20；
        capped=(20<50)=True；mid=round(20.0)=20；上下界相同 → range_text='20%'。
        """
        d = build_allocation_decision(
            _ms(health=43, regime='neutral'),
            caps=[Cap('三環第一環', 20, '')],
        )
        assert d.is_loaded is True
        assert (d.posture_lo, d.posture_hi) == (30, 50)
        assert d.posture == '轉守'
        assert (d.final_lo, d.final_hi, d.final_mid) == (20, 20, 20)
        assert d.capped is True
        assert d.cap_pct == 20
        assert d.cap_name == '三環第一環'
        assert d.range_text == '20%'      # 不得出現 '20–20%' 這種怪字串
        assert d.mid_text == '20%'

    def test_cap_at_posture_ceiling_is_not_capped(self):
        """health=85 → 積極 80–100%；系統上限 100% 剛好等於姿態上界 → 不算被壓制。

        手算：85 >= THROTTLE_HEALTH_A(80) → lo=80, hi=100。regime='bull' 不否決。
        exposure_limit_pct=100 → Cap('系統風險上限',100)；cap_pct=100。
        final_hi=min(100,100)=100；final_lo=min(80,100)=80；
        capped=(100<100)=False；mid=round(90.0)=90。
        """
        d = build_allocation_decision(_ms(health=85, regime='bull',
                                          exposure_limit_pct=100))
        assert (d.posture_lo, d.posture_hi) == (80, 100)
        assert d.posture == '積極'
        assert (d.final_lo, d.final_hi, d.final_mid) == (80, 100, 90)
        assert d.capped is False
        assert d.cap_pct == 100

    def test_lowest_cap_wins_among_multiple(self):
        """多條天花板並存 → 取最小者生效（VIX 10% 勝過三環 20% 與系統上限 20%）。

        手算：health=43 → 30–50%。caps = VIX(10)、三環(20)、系統風險上限(20)。
        min by pct → 10（唯一最小值，無 tie）→ cap_name='VIX 否決權'。
        final_hi=min(50,10)=10；final_lo=min(30,10)=10；mid=10；capped=True。
        """
        d = build_allocation_decision(
            _ms(health=43, regime='neutral', exposure_limit_pct=20),
            caps=[Cap('VIX 否決權', 10, ''), Cap('三環第一環', 20, '')],
        )
        assert d.cap_pct == 10
        assert d.cap_name == 'VIX 否決權'
        assert (d.final_lo, d.final_hi) == (10, 10)
        assert d.capped is True
        assert len(d.caps) == 3          # 三條都留著供明細展開，只是只有一條生效

    def test_not_loaded_returns_all_none_fail_loud(self):
        """§1 Fail Loud：總經未評估 → final_* 全 None，**不得**回填 80/50/20 假預設。"""
        d = build_allocation_decision(_ms(is_loaded=False, health=None,
                                          regime='unknown'))
        assert d.is_loaded is False
        assert d.final_lo is None
        assert d.final_hi is None
        assert d.final_mid is None
        assert d.posture_lo is None
        assert d.posture_hi is None
        assert d.posture == '未評估'
        assert d.icon == '⬜'
        assert d.cap_pct is None
        assert d.range_text == '--'
        assert d.mid_text == '--'
        assert d.capped is False
        assert d.drivers            # 要說明「為何沒有數字」，不能空手而回

    def test_bear_low_health_defense_band_no_cap(self):
        """health=30 → 防禦 0–20%；regime='bear' 但已在防禦帶 → 不重複否決。

        手算：30 < 35 → 落在 (0, 0, 20, '防禦') → lo=0, hi=20。
        veto 條件 `hi > _DEFENSE_HI_PCT(20)` 不成立（20 > 20 為 False）→ 不再壓。
        無 cap → final_hi=20；final_lo=min(0,20)=0；mid=round(10.0)=10；capped=False。
        """
        d = build_allocation_decision(_ms(health=30, regime='bear'))
        assert (d.posture_lo, d.posture_hi) == (0, 20)
        assert (d.final_lo, d.final_hi, d.final_mid) == (0, 20, 10)
        assert d.capped is False
        assert d.cap_pct is None
        assert d.cap_text == ''          # 無 cap → 不印鎖頭
        assert d.range_text.startswith('0')
        assert d.range_text.endswith('20%')

    def test_none_macro_state_treated_as_not_loaded(self):
        """macro_state=None（尚未載入任何總經）→ 同樣走未評估路徑，不 raise。"""
        d = build_allocation_decision(None)
        assert d.is_loaded is False
        assert d.final_mid is None
        assert d.regime == 'unknown'

    def test_health_none_but_loaded_still_not_evaluated(self):
        """is_loaded=True 但 health 缺 → 仍視為未評估（不可用 0 分硬算成防禦）。"""
        d = build_allocation_decision(_ms(health=None, is_loaded=True))
        assert d.is_loaded is False
        assert d.final_lo is None

    def test_explicit_throttle_is_respected(self):
        """外部已算好 throttle 時直接採用（production 由 allocation_service 傳入）。

        手算：throttle 給 50–70；cap=60 → final_hi=min(70,60)=60；
        final_lo=min(50,60)=50；mid=round(55.0)=55；capped=(60<70)=True。
        """
        thr = {'lo_pct': 50, 'hi_pct': 70, 'mid_pct': 60,
               'posture': '中性偏多', 'icon': '🟡', 'regime_capped': False}
        d = build_allocation_decision(
            _ms(health=62, regime='neutral'), throttle=thr,
            caps=[Cap('測試上限', 60, '')],
        )
        assert (d.final_lo, d.final_hi, d.final_mid) == (50, 60, 55)
        assert d.capped is True
        assert d.posture == '中性偏多'
        assert d.icon == '🟡'

    def test_conflicts_are_surfaced_not_swallowed(self):
        """被壓制的反向訊號要顯示，不要藏。"""
        d = build_allocation_decision(
            _ms(health=43), conflicts=['技術面突破但總經否決'])
        assert '技術面突破但總經否決' in d.conflicts

    def test_headline_and_cap_text_render(self):
        """顯示 helper 集中在 dataclass，避免各頁自己 f-string 出不同格式。"""
        d = build_allocation_decision(
            _ms(health=43), caps=[Cap('三環第一環', 20, '技術面視為誘多')])
        h = d.headline()
        assert '轉守' in h and '20%' in h
        assert '20' in d.cap_text and '三環第一環' in d.cap_text
        assert d.regime_text == '震盪'          # REGIME_LABEL['neutral']

        nd = build_allocation_decision(_ms(is_loaded=False))
        assert '未評估' in nd.headline()


# ════════════════════════════════════════════════════════════════
# B. 不變式（property-based，窮舉小網格）
# ════════════════════════════════════════════════════════════════
_HEALTHS = list(range(0, 101, 10))                 # 0,10,...,100
_CAPS = [None] + list(range(0, 101, 10))           # None,0,10,...,100
_REGIMES = ['bull', 'neutral', 'caution', 'bear']


class TestInvariants:
    """這兩條不變式若破了，UI 會印出「建議持股 50–20%」這種鬼區間。"""

    def test_final_lo_never_exceeds_final_hi(self):
        """final_lo = min(posture_lo, final_hi) → 結構上恆 <= final_hi。"""
        for h in _HEALTHS:
            for c in _CAPS:
                for rg in _REGIMES:
                    caps = () if c is None else (Cap('測試上限', c, ''),)
                    d = build_allocation_decision(_ms(health=h, regime=rg),
                                                  caps=caps)
                    assert d.final_lo is not None and d.final_hi is not None
                    assert d.final_lo <= d.final_hi, (h, c, rg, d.final_lo, d.final_hi)

    def test_final_mid_lies_within_range(self):
        """mid = round((lo+hi)/2)；lo<=hi 且兩者皆整數 → round 單調 → lo<=mid<=hi。"""
        for h in _HEALTHS:
            for c in _CAPS:
                for rg in _REGIMES:
                    caps = () if c is None else (Cap('測試上限', c, ''),)
                    d = build_allocation_decision(_ms(health=h, regime=rg),
                                                  caps=caps)
                    assert d.final_lo <= d.final_mid <= d.final_hi, (h, c, rg)

    def test_final_hi_never_exceeds_cap(self):
        """核心規則：硬否決是**天花板**，最終上界不得高於它。"""
        for h in _HEALTHS:
            for c in _CAPS:
                if c is None:
                    continue
                d = build_allocation_decision(
                    _ms(health=h, regime='neutral'), caps=(Cap('測試上限', c, ''),))
                assert d.final_hi <= c, (h, c, d.final_hi)

    def test_bounds_stay_in_0_100(self):
        for h in _HEALTHS:
            for c in _CAPS:
                caps = () if c is None else (Cap('測試上限', c, ''),)
                d = build_allocation_decision(_ms(health=h), caps=caps)
                assert 0 <= d.final_lo <= 100
                assert 0 <= d.final_hi <= 100


# ════════════════════════════════════════════════════════════════
# C. allocation_sleeves（ETF 三桶）
# ════════════════════════════════════════════════════════════════
def _decision_with_mid(mid: int, regime: str = 'neutral') -> AllocationDecision:
    """直接構造一個決策物件（frozen dataclass），繞過健康分反推。"""
    return AllocationDecision(
        is_loaded=True, regime=regime, health=50.0,
        posture_lo=0, posture_hi=100, posture='測試', icon='🟡',
        cap_pct=None, cap_name='',
        final_lo=mid, final_hi=mid, final_mid=mid,
    )


class TestAllocationSleeves:
    """_eq + _bond + _cash = _eq + (100-_eq) = 100，恆等式與 regime / 四捨五入無關。"""

    def test_three_buckets_always_sum_to_100(self):
        for mid in (0, 1, 33, 50, 67, 99, 100):
            for rg in _REGIMES + ['unknown']:
                sl = allocation_sleeves(_decision_with_mid(mid, rg))
                assert sl is not None
                assert sum(sl.values()) == 100, (mid, rg, sl)

    def test_three_buckets_never_negative(self):
        """_bond=round(_rest*share)、share<=0.70<1 → _bond<=_rest → _cash>=0。"""
        for mid in (0, 1, 33, 50, 67, 99, 100):
            for rg in _REGIMES + ['unknown']:
                sl = allocation_sleeves(_decision_with_mid(mid, rg))
                assert all(v >= 0 for v in sl.values()), (mid, rg, sl)

    def test_equity_bucket_equals_final_mid(self):
        """股票桶必須等於主決策中值 —— 這正是「永不矛盾」的定義。"""
        for mid in (0, 1, 33, 50, 67, 99, 100):
            sl = allocation_sleeves(_decision_with_mid(mid))
            assert sl['股票型ETF'] == mid

    def test_keys_are_stable(self):
        sl = allocation_sleeves(_decision_with_mid(50))
        assert set(sl) == {'股票型ETF', '債券型ETF', '貨幣/現金'}

    def test_bear_holds_more_bonds_than_bull(self):
        """空頭債券避險價值高（0.70）> 多頭（0.50），非股票部位分配應反映這點。

        手算：mid=50 → _rest=50。bull: round(25.0)=25；bear: round(35.0)=35。
        """
        assert allocation_sleeves(_decision_with_mid(50, 'bear'))['債券型ETF'] == 35
        assert allocation_sleeves(_decision_with_mid(50, 'bull'))['債券型ETF'] == 25

    def test_not_loaded_returns_none(self):
        """§1：總經未評估 → 不給假配置。"""
        d = build_allocation_decision(_ms(is_loaded=False, health=None))
        assert allocation_sleeves(d) is None


# ════════════════════════════════════════════════════════════════
# D. vix_veto_cap / ring_gate_cap
# ════════════════════════════════════════════════════════════════
class TestVixVetoCap:
    def test_none_vix_no_cap(self):
        assert vix_veto_cap(None) is None

    def test_below_20_no_cap(self):
        assert vix_veto_cap(19.9) is None
        assert vix_veto_cap(0) is None

    def test_20_to_30_caps_at_30(self):
        c = vix_veto_cap(20)
        assert c is not None
        assert c.pct == 30
        assert c.name == 'VIX 否決權'
        assert vix_veto_cap(29.9).pct == 30

    def test_30_and_above_caps_at_10(self):
        c = vix_veto_cap(30)
        assert c is not None and c.pct == 10
        assert vix_veto_cap(45).pct == 10

    def test_non_numeric_is_ignored_not_raised(self):
        assert vix_veto_cap('N/A') is None

    def test_thresholds_are_monotone(self):
        """VIX 越高，天花板只能越低（不得出現「更恐慌卻更敢買」）。"""
        pcts = [(vix_veto_cap(v).pct if vix_veto_cap(v) else 100)
                for v in (10, 19.9, 20, 25, 30, 40)]
        assert pcts == sorted(pcts, reverse=True)


class TestRingGateCap:
    def test_pass_no_cap(self):
        assert ring_gate_cap(True) is None
        assert ring_gate_cap(True, 'VIX 過高') is None   # 過了就是過了，detail 不影響

    def test_fail_caps_at_defense_band(self):
        c = ring_gate_cap(False)
        assert c is not None
        assert c.pct == 20 == DEFENSE_HI_PCT     # 對齊 EXPOSURE_BEAR，不另立數字
        assert c.name == '三環第一環'
        assert c.reason                          # 要有預設說明，不能空白

    def test_custom_detail_is_used(self):
        c = ring_gate_cap(False, 'VIX 31.2 ≥ 20')
        assert c.reason == 'VIX 31.2 ≥ 20'


class TestCapValidation:
    def test_out_of_range_pct_raises(self):
        with pytest.raises(ValueError):
            Cap('壞上限', 101, '')
        with pytest.raises(ValueError):
            Cap('壞上限', -1, '')

    def test_boundary_pct_ok(self):
        assert Cap('零上限', 0, '').pct == 0
        assert Cap('滿上限', 100, '').pct == 100


# ════════════════════════════════════════════════════════════════
# E. 防禦：exposure_limit_pct 髒資料（macro_state.json 是磁碟檔，可能被手改）
# ════════════════════════════════════════════════════════════════
class TestDirtyExposureLimit:
    """這條路徑的呼叫點之一是 app.py module level —— 一旦 raise 會整站白屏，
    故必須夾限 + log，而不是讓 Cap.__post_init__ 炸出來。"""

    def test_over_100_is_clamped_not_raised(self):
        """150 → 夾限成 100；health=43 姿態 30–50 → 天花板 100 不咬 → 維持 30–50。"""
        d = build_allocation_decision(_ms(health=43, exposure_limit_pct=150))
        assert d.cap_pct == 100
        assert (d.final_lo, d.final_hi, d.final_mid) == (30, 50, 40)
        assert d.capped is False          # 100 < 50 為 False

    def test_negative_is_clamped_to_zero(self):
        """-10 → 夾限成 0 → 天花板 0 全壓 → 0–0，capped=True。"""
        d = build_allocation_decision(_ms(health=43, exposure_limit_pct=-10))
        assert d.cap_pct == 0
        assert (d.final_lo, d.final_hi, d.final_mid) == (0, 0, 0)
        assert d.capped is True
        assert d.range_text == '0%'

    def test_non_numeric_is_ignored(self):
        """'N/A' → int() 丟 ValueError → 被接住並忽略該天花板，其餘照算。"""
        d = build_allocation_decision(_ms(health=43, exposure_limit_pct='N/A'))
        assert d.cap_pct is None
        assert (d.final_lo, d.final_hi, d.final_mid) == (30, 50, 40)
        assert d.capped is False

    def test_none_means_no_system_cap(self):
        d = build_allocation_decision(_ms(health=43, exposure_limit_pct=None))
        assert d.cap_pct is None
        assert len(d.caps) == 0

    def test_dirty_values_never_raise(self):
        """窮舉髒值：一律不得拋例外（白屏防線）。"""
        for bad in (150, -10, 'N/A', '', None, 1000, -999, [], {}):
            d = build_allocation_decision(_ms(health=43, exposure_limit_pct=bad))
            assert d.final_lo <= d.final_hi

    def test_zero_limit_is_a_real_cap_not_falsy_skip(self):
        """0% 是「清空持股」的合法指令，不可因為 falsy 就被當成沒設。"""
        d = build_allocation_decision(_ms(health=85, regime='bull',
                                          exposure_limit_pct=0))
        assert d.cap_pct == 0
        assert (d.final_lo, d.final_hi) == (0, 0)
        assert d.capped is True
