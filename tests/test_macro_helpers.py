"""src/compute/macro/macro_helpers.py 純函式 unit test — Phase 7A-Ext / 7E。"""
from __future__ import annotations

import pandas as pd
import pytest

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.compute.macro import (
    BULL_MIN_SCORE,
    HEALTH_DEFENSE_THRESHOLD,
    PIVOT_FAMILIES,
    PIVOT_FAMILY_OF,
    PIVOT_MIN_SIDE_FAMILIES,
    aggregate_pivot_families,
    calc_traffic_light,
    classify_long_term_regime,
    classify_short_term_regime,
    detect_cpi_fed_double_top,
    detect_mk_golden_inflection,
    rp_entry,
    rp_scalar,
    rp_ts,
)


class TestCalibrationConstants:
    """v18.141：校準收斂門檻常數對外 export，校準腳本與測試共用真值。"""

    def test_defense_threshold_value(self):
        assert HEALTH_DEFENSE_THRESHOLD == 35

    def test_bull_min_score_value(self):
        assert BULL_MIN_SCORE == 4

    def test_threshold_drives_actual_decision(self):
        # health 剛好 ≥ 常數 → 不 defense；驗證 calc_traffic_light 真的讀這個常數
        mkt = {'score': 1, 'regime': 'neutral'}
        target_jqavg = (HEALTH_DEFENSE_THRESHOLD - 1 / 5 * 100 * 0.4) / 0.4
        tl_at = calc_traffic_light(mkt, {'avg': target_jqavg}, {'inst': {}}, None)
        assert tl_at['health'] >= HEALTH_DEFENSE_THRESHOLD
        assert tl_at['defense'] is False


class TestCalcTrafficLight:
    def test_all_empty_returns_none(self):
        assert calc_traffic_light({}, {}, {}, None) is None
        assert calc_traffic_light(None, None, None, None) is None

    def test_bull_regime_green(self):
        mkt = {'score': 4, 'regime': 'bull'}
        jq  = {'avg': 75}
        cl  = {'inst': {'外資自營': {'net': 1000}}, 'adl': 1}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl is not None
        assert tl['icon'] == '🟢'
        assert tl['color'] == '#22c55e'
        assert '多頭' in tl['label']
        assert tl['regime'] == 'bull'

    def test_caution_regime_red(self):
        # avg=80, score=3 → health = 32+24 = 56 ≥ 40，不觸發 defense，regime=caution
        mkt = {'score': 3, 'regime': 'caution'}
        jq  = {'avg': 80}
        cl  = {'inst': {'外資自營': {'net': -500}}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['icon'] == '🔴'
        assert '保守' in tl['label']
        assert tl['defense'] is False

    def test_bear_regime_red(self):
        # avg=80, score=3, fnet=0 → health=56 ≥ 40，regime=bear
        tl = calc_traffic_light(
            {'score': 3, 'regime': 'bear'}, {'avg': 80}, {}, None,
        )
        assert tl['icon'] == '🔴'
        assert '保守' in tl['label']
        assert tl['defense'] is False

    def test_neutral_regime_yellow(self):
        mkt = {'score': 3, 'regime': 'neutral'}
        jq  = {'avg': 60}
        cl  = {'inst': {'外資自營': {'net': 100}}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['icon'] == '🟡'
        assert '震盪' in tl['label']

    def test_defense_override_red(self):
        # score<2 + 期貨大空單 → 強制空頭防禦（即使 regime=bull）
        mkt = {'score': 1, 'regime': 'bull'}
        jq  = {'avg': 50}
        cl  = {'inst': {'外資自營': {'net': -1000}}}
        li  = pd.DataFrame({'外資大小': [-40000], '韭菜指數': [80]})
        tl = calc_traffic_light(mkt, jq, cl, li)
        assert tl['icon'] == '🔴'
        assert tl['defense'] is True
        assert '空頭防禦' in tl['label']

    def test_health_below_35_forces_defense(self):
        # jqavg=10 + score=0 + fnet=0 → health=10*0.4+0+0=4 < 35 → defense override
        mkt = {'score': 0, 'regime': 'bull'}
        jq  = {'avg': 10}
        cl  = {'inst': {}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['icon'] == '🔴'
        assert '空頭防禦' in tl['label']

    def test_health_38_no_longer_defense_v18_140(self):
        # v18.140 校準收斂：health 介於 35~40 不再觸發防禦
        # v19.102 權重校準(0.6/0.4/0,score/max_score):
        # jqavg=55 + score=1(max 預設 4)+ fnet=0
        # → health = 55*0.6 + (1/4*100)*0.4 + 0 = 33 + 10 = 43 ≥ 35 → 不防禦
        mkt = {'score': 1, 'regime': 'neutral'}
        jq  = {'avg': 55}
        cl  = {'inst': {}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['health'] == pytest.approx(43.0)
        assert tl['icon'] == '🟡'  # neutral，不再強制 🔴
        assert tl['defense'] is False

    def test_bull_low_score_falls_to_neutral_v18_140(self):
        # v18.140 校準收斂：regime=bull 但 score<4 → 不升綠燈，退回 🟡 中性
        mkt = {'score': 3, 'regime': 'bull'}
        jq  = {'avg': 75}
        cl  = {'inst': {'外資自營': {'net': 1000}}, 'adl': 1}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['icon'] == '🟡'
        assert '震盪' in tl['label']
        assert tl['regime'] == 'bull'  # regime 仍是 bull，只是門檻不夠

    def test_foreign_net_extraction(self):
        cl = {'inst': {'外資 (自營+投信)': {'net': 12345}}}
        tl = calc_traffic_light({'score': 3, 'regime': 'neutral'}, {'avg': 60}, cl, None)
        assert tl['fk'] == '外資 (自營+投信)'
        assert tl['fnet'] == 12345

    def test_confidence_score(self):
        # 5 來源齊全 → conf=100
        mkt = {'score': 3, 'regime': 'neutral'}
        jq  = {'avg': 60}
        cl  = {'inst': {'外資': {'net': 100}}, 'adl': 1}
        li  = pd.DataFrame({'外資大小': [100], '韭菜指數': [50]})
        tl = calc_traffic_light(mkt, jq, cl, li)
        assert tl['conf'] == 100

    def test_confidence_partial(self):
        # 只有 mkt + jq → 2/5 = 40
        tl = calc_traffic_light({'score': 3, 'regime': 'neutral'}, {'avg': 60}, {}, None)
        assert tl['conf'] == pytest.approx(40)

    def test_li_latest_safe_parsing(self):
        # 欄位缺失：不報錯，fut_net=0、leek=50
        li = pd.DataFrame({'其他欄': [1]})
        tl = calc_traffic_light({'score': 3, 'regime': 'neutral'}, {'avg': 60}, {}, li)
        assert tl['fut_net'] == 0
        assert tl['leek'] == 50

    def test_health_formula(self):
        # v19.102 校準採納(方案 B):health = avg*0.6 + min(score/max*100,100)*0.4
        # + (0 if fnet>0)。avg=50, score=5, max_score=5, fnet=100
        # → 30 + min(100,100)*0.4 + 0 = 30 + 40 = 70(fnet bonus 歸零)
        mkt = {'score': 5, 'max_score': 5, 'regime': 'bull'}
        jq  = {'avg': 50}
        cl  = {'inst': {'外資': {'net': 100}}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['health'] == pytest.approx(70.0)

    def test_health_score_norm_uses_true_max_score(self):
        # v19.102 修除5錯配:score=4/max=4 → score 分項滿分 100(舊 /5 只有 80)
        mkt = {'score': 4, 'max_score': 4, 'regime': 'neutral'}
        jq  = {'avg': 0}
        cl  = {'inst': {}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['health'] == pytest.approx(40.0)   # 0*0.6 + 100*0.4

    def test_health_fnet_no_longer_bonus(self):
        # v19.102:fnet>0 不再 +20(校準:fnet 對 20 日回撤零預測力)
        mkt = {'score': 0, 'regime': 'neutral'}
        jq  = {'avg': 50}
        base = calc_traffic_light(mkt, jq, {'inst': {}}, None)
        with_fnet = calc_traffic_light(mkt, jq, {'inst': {'外資': {'net': 999}}}, None)
        assert base['health'] == pytest.approx(with_fnet['health'])  # 同分


class TestRpTs:
    def test_none_returns_na(self):
        assert rp_ts(None) == 'N/A'

    def test_non_df_returns_na(self):
        assert rp_ts({'x': 1}) == 'N/A'
        assert rp_ts([1, 2, 3]) == 'N/A'

    def test_empty_df_returns_na(self):
        assert rp_ts(pd.DataFrame()) == 'N/A'

    def test_datetime_index(self):
        df = pd.DataFrame({'close': [10, 20]}, index=pd.to_datetime(['2024-01-15', '2024-03-22']))
        assert rp_ts(df) == '2024-03-22'

    def test_quarter_label_q4(self):
        # 季度標籤 '2024Q4' → '2024-12-31'
        df = pd.DataFrame({'季度標籤': ['2024Q1', '2024Q4'], 'val': [1, 2]})
        assert rp_ts(df) == '2024-12-31'

    def test_quarter_label_q1_q2_q3(self):
        # Q1=03-31, Q2=06-30, Q3=09-30
        for q, expect in [('1', '03-31'), ('2', '06-30'), ('3', '09-30')]:
            df = pd.DataFrame({'季度標籤': [f'2023Q{q}']})
            assert rp_ts(df) == f'2023-{expect}'

    def test_quarter_label_invalid_qnum_defaults_to_1231(self):
        df = pd.DataFrame({'季度標籤': ['2024Q9']})
        assert rp_ts(df) == '2024-12-31'

    def test_year_int_column(self):
        df = pd.DataFrame({'年度': [2022, 2023, 2024], 'val': [1, 2, 3]})
        assert rp_ts(df) == '2024-12-31'

    def test_underscore_date_format(self):
        # _date 強制 '%Y%m%d'
        df = pd.DataFrame({'_date': ['20240515', '20240601']})
        assert rp_ts(df) == '2024-06-01'

    def test_date_column_auto_parse(self):
        df = pd.DataFrame({'date': ['2024-05-15', '2024-06-01']})
        assert rp_ts(df) == '2024-06-01'

    def test_unparseable_returns_na(self):
        df = pd.DataFrame({'foo': ['bar', 'baz']})
        assert rp_ts(df) == 'N/A'


class TestRpEntry:
    def test_none_df_missing(self):
        e = rp_entry(None, '個股', 'daily')
        assert e['missing'] is True
        assert e['rows'] == 0
        assert e['last_updated'] == 'N/A'
        assert e['category'] == '個股'
        assert e['frequency'] == 'daily'

    def test_empty_df_missing(self):
        e = rp_entry(pd.DataFrame(), 'ETF', 'monthly')
        assert e['missing'] is True
        assert e['rows'] == 0

    def test_valid_df_uses_rp_ts(self):
        df = pd.DataFrame({'date': ['2024-05-15']})
        e = rp_entry(df, 'ETF', 'daily')
        assert 'missing' not in e
        assert e['rows'] == 1
        assert e['last_updated'] == '2024-05-15'
        assert e['category'] == 'ETF'
        assert e['frequency'] == 'daily'


class TestRpScalar:
    def test_none_val_missing(self):
        e = rp_scalar(None, '個股', 'daily', '2026-05-16')
        assert e['missing'] is True
        assert e['rows'] == 0
        assert e['last_updated'] == 'N/A'

    def test_valid_val_uses_proxy_date(self):
        e = rp_scalar(42, 'ETF', 'daily', '2026-05-16')
        assert 'missing' not in e
        assert e['rows'] == 1
        assert e['last_updated'] == '2026-05-16'
        assert e['category'] == 'ETF'

    def test_zero_treated_as_valid(self):
        # 0 不是 None → 視為有值（如 RSI=0、健康度=0 仍是有效讀數）
        e = rp_scalar(0, '個股', 'daily', '2026-05-16')
        assert e.get('missing') is None
        assert e['rows'] == 1
        assert e['last_updated'] == '2026-05-16'

    def test_empty_string_treated_as_valid(self):
        # '' 也不是 None
        e = rp_scalar('', 'ETF', 'daily', '2026-01-01')
        assert e.get('missing') is None
        assert e['rows'] == 1


class TestDetectMkGoldenInflection:
    """v18.169：CPI×Fed 雙頂回落偵測 — CPI YoY × Fed Funds Rate 同步回落。

    v19.173 正名：函式 `detect_mk_golden_inflection` → `detect_cpi_fed_double_top`，
    label「MK 黃金拐點」→「CPI×Fed 雙頂回落」。判定邏輯**零變更**，
    故本 class 的所有數值斷言原封不動，只改被改掉的兩個 label 字串。
    """

    def test_alias_is_same_object(self):
        """舊名必須仍可呼叫（section_state / section_long_term 還在用）。"""
        assert detect_mk_golden_inflection is detect_cpi_fed_double_top

    def test_label_no_longer_claims_mann_kendall(self):
        """正名守門：label 不得再出現「MK」/「Mann」—— 這條規則沒有趨勢檢定背書。

        本函式只做兩點 MoM 差分 + 固定門檻，掛 Mann-Kendall 的縮寫等於借了一個
        它沒有的統計背書。真的 MK 在 `shared/mk_test.py`。
        """
        for _out in (detect_cpi_fed_double_top(3.0, 3.3, 5.25, 5.33),
                     detect_cpi_fed_double_top(3.2, 3.3, 5.25, 5.33)):
            assert _out is not None
            assert 'MK' not in _out['label']
            assert 'mann' not in _out['label'].lower()
            assert 'CPI×Fed' in _out['label']

    def test_strong_signal_cpi_drop_fed_drop(self):
        # CPI 月降 0.3ppt + Fed 月降 0.08ppt → 強訊號 ⭐
        sig = detect_mk_golden_inflection(3.0, 3.3, 5.25, 5.33)
        assert sig is not None
        assert sig['strength'] == 'strong'
        assert sig['color'] == '#22c55e'
        assert '⭐' in sig['icon']
        assert 'CPI×Fed 雙頂回落' in sig['label']   # v19.173 正名（原 'MK 黃金拐點'）

    def test_strong_signal_cpi_drop_fed_flat(self):
        # CPI 月降 0.25ppt + Fed 持平 → 強訊號 ⭐
        sig = detect_mk_golden_inflection(3.0, 3.25, 5.33, 5.33)
        assert sig is not None
        assert sig['strength'] == 'strong'
        assert '持平' in sig['detail']

    def test_weak_signal_cpi_mild_drop_fed_drop(self):
        # CPI 月降 0.1ppt + Fed 月降 0.08ppt → 弱訊號 ✅
        sig = detect_mk_golden_inflection(3.2, 3.3, 5.25, 5.33)
        assert sig is not None
        assert sig['strength'] == 'weak'
        assert sig['color'] == '#eab308'
        assert 'CPI×Fed 回落觀察中' in sig['label']   # v19.173 正名（原 'MK 拐點觀察中'）

    def test_no_signal_cpi_rising(self):
        # CPI 上升 → 無訊號
        assert detect_mk_golden_inflection(3.4, 3.0, 5.25, 5.33) is None

    def test_no_signal_fed_rising(self):
        # Fed 升息 → 無訊號
        assert detect_mk_golden_inflection(3.0, 3.3, 5.5, 5.33) is None

    def test_no_signal_cpi_flat(self):
        # CPI 持平（diff 在噪聲區 ±0.05） → 無訊號
        assert detect_mk_golden_inflection(3.32, 3.30, 5.25, 5.33) is None
        assert detect_mk_golden_inflection(3.30, 3.30, 5.25, 5.33) is None

    def test_no_signal_missing_data(self):
        assert detect_mk_golden_inflection(None, 3.3, 5.25, 5.33) is None
        assert detect_mk_golden_inflection(3.0, None, 5.25, 5.33) is None
        assert detect_mk_golden_inflection(3.0, 3.3, None, 5.33) is None
        assert detect_mk_golden_inflection(3.0, 3.3, 5.25, None) is None

    def test_invalid_data_returns_none(self):
        # 非數值（字串等） → graceful None
        assert detect_mk_golden_inflection('abc', 3.3, 5.25, 5.33) is None

    def test_detail_text_includes_values(self):
        sig = detect_mk_golden_inflection(2.8, 3.3, 5.0, 5.33)
        assert sig is not None
        # 強訊號 detail 應該包含 CPI + Fed 數字
        assert '2.80' in sig['detail']
        assert '3.30' in sig['detail']
        assert '5.00' in sig['detail']
        assert '5.33' in sig['detail']

    def test_threshold_boundary_strong_vs_weak(self):
        # 0.20ppt 邊界：cpi_delta = -0.20 → 強
        sig_strong = detect_mk_golden_inflection(3.0, 3.20, 5.33, 5.33)
        assert sig_strong is not None and sig_strong['strength'] == 'strong'
        # 0.19ppt → 弱
        sig_weak = detect_mk_golden_inflection(3.01, 3.20, 5.33, 5.33)
        assert sig_weak is not None and sig_weak['strength'] == 'weak'

    def test_boundary_cpi_just_above_noise(self):
        # CPI 降 0.06ppt（剛過噪聲門檻 0.05） + Fed 持平 → 弱訊號
        sig = detect_mk_golden_inflection(3.24, 3.30, 5.33, 5.33)
        assert sig is not None and sig['strength'] == 'weak'

    def test_fed_slight_uptick_within_noise_still_signals(self):
        # Fed 微升 0.03ppt（在 ±0.05 噪聲區） + CPI 月降 0.3 → 強訊號（Fed 視為持平）
        sig = detect_mk_golden_inflection(3.0, 3.3, 5.36, 5.33)
        assert sig is not None and sig['strength'] == 'strong'


class TestClassifyLongTermRegime:
    """v18.170：長期總經 12M 視角分類（景氣大循環位階）。"""

    def test_growth_regime_full_bull(self):
        # CPI 溫和 + Fed 降息 + NDC 黃紅 + PMI 強 + MK 強 → 🟢 成長期
        mk = detect_mk_golden_inflection(2.0, 2.5, 4.5, 4.75)
        r = classify_long_term_regime(2.0, 4.5, 4.75, 35, 56, mk)
        assert r['regime'].startswith('🟢')
        assert r['score'] >= 1.0
        assert r['suggest_pct'] == '80%+'

    def test_recovery_regime_mid_bull(self):
        # CPI 3% + Fed 持平 + NDC 綠 + PMI 53 + 無 MK → 🔵 復甦期
        r = classify_long_term_regime(3.0, 5.25, 5.25, 27, 53, None)
        assert r['regime'].startswith('🔵')
        assert 0.0 <= r['score'] < 1.0

    def test_overheat_regime_caution(self):
        # CPI 4.5% + Fed 持平 + NDC 綠 + PMI 49 + 無 MK → 🟡 過熱/震盪期
        # 計算：(-1)*25 + (+1)*20 + 0*20 + (-1)*20 + 0*15 = -25 / 100 = -0.25
        r = classify_long_term_regime(4.5, 5.5, 5.5, 25, 49, None)
        assert r['regime'].startswith('🟡')
        assert -1.0 <= r['score'] < 0.0

    def test_recession_regime_defense(self):
        # CPI 5.5% + Fed 升息 + NDC 藍 + PMI 47 + 無 MK → 🔴 衰退期
        r = classify_long_term_regime(5.5, 5.5, 5.0, 15, 47, None)
        assert r['regime'].startswith('🔴')
        assert r['score'] < -1.0
        assert r['suggest_pct'] == '<30%'

    def test_insufficient_data_returns_grey(self):
        # 所有指標皆 None → ⚪ 資料不足
        r = classify_long_term_regime(None, None, None, None, None, None)
        assert r['regime'] == '⚪ 資料不足'
        assert r['score'] == 0.0
        assert r['suggest_pct'] == 'N/A'

    def test_mk_alone_not_enough(self):
        # 只有 MK 訊號、其他全 None → ⚪ 資料不足（MK 不該獨自驅動 regime）
        mk = detect_mk_golden_inflection(3.0, 3.3, 5.25, 5.33)
        r = classify_long_term_regime(None, None, None, None, None, mk)
        assert r['regime'] == '⚪ 資料不足'

    def test_partial_data_works(self):
        # 只有 CPI + PMI 兩項 → 仍能算分（部分權重）
        r = classify_long_term_regime(2.0, None, None, None, 56, None)
        assert r['regime'] != '⚪ 資料不足'
        assert len(r['components']) == 3  # CPI + PMI + CPI×Fed 雙頂(0)（v19.173 正名）

    def test_components_structure(self):
        # components 應為 list of (name, score, weight)
        r = classify_long_term_regime(2.0, 5.0, 5.0, 27, 53, None)
        for comp in r['components']:
            assert len(comp) == 3
            name, score, weight = comp
            assert isinstance(name, str)
            assert isinstance(score, int)
            assert isinstance(weight, int)

    def test_invalid_data_graceful(self):
        # 字串/NaN 等不該炸
        r = classify_long_term_regime('bad', float('nan'), None, 'x', None, None)
        assert r['regime'] == '⚪ 資料不足'

    def test_score_range_clamp(self):
        # 分數應在 [-2, +2] 區間內
        r = classify_long_term_regime(1.5, 4.0, 4.5, 40, 58, None)
        assert -2.0 <= r['score'] <= 2.0

    def test_mk_strong_vs_weak_boost(self):
        # 同樣中性主指標下，強 MK 應比弱 MK 分數高
        mk_strong = {'strength': 'strong'}
        mk_weak = {'strength': 'weak'}
        r_s = classify_long_term_regime(3.0, 5.0, 5.0, 27, 50, mk_strong)
        r_w = classify_long_term_regime(3.0, 5.0, 5.0, 27, 50, mk_weak)
        assert r_s['score'] > r_w['score']


class TestClassifyShortTermRegime:
    """v18.170：短期總經 1Q 視角分類（對齊台股財報季偏向）。"""

    def test_bullish_full_strong(self):
        # 出口強 + PMI 強 + VIX 低 + 連買多 + CPI 月降 → ⚡ 偏多
        r = classify_short_term_regime(18, 55, 14, 7, 3.0, 3.3)
        assert r['regime'].startswith('⚡')
        assert r['score'] >= 0.8

    def test_neutral_mixed_signals(self):
        # 出口溫 + PMI 51 + VIX 22 + 微連買 + CPI 持平 → ⚖️ 中性
        r = classify_short_term_regime(3, 51, 22, 1, 3.0, 3.05)
        assert r['regime'].startswith('⚖️')
        assert -0.3 <= r['score'] < 0.8

    def test_bearish_full_weak(self):
        # 出口降 + PMI 弱 + VIX 高 + 連賣多 + CPI 上升 → ⚠️ 偏空
        r = classify_short_term_regime(-10, 47, 32, -8, 3.5, 3.1)
        assert r['regime'].startswith('⚠️')
        assert r['score'] < -0.3

    def test_insufficient_data(self):
        r = classify_short_term_regime(None, None, None, None, None, None)
        assert r['regime'] == '⚪ 資料不足'

    def test_partial_data_export_only(self):
        # 只有出口 YoY 一項，仍算
        r = classify_short_term_regime(20, None, None, None, None, None)
        assert r['regime'] != '⚪ 資料不足'
        assert r['score'] > 0  # 出口強 → 應偏多

    def test_foreign_investor_streak_positive(self):
        # 外資連買 5 日（+2）vs 連賣 5 日（-2），分數差應顯著
        r_buy = classify_short_term_regime(10, 52, 18, 5, 3.0, 3.1)
        r_sell = classify_short_term_regime(10, 52, 18, -5, 3.0, 3.1)
        assert r_buy['score'] > r_sell['score']

    def test_vix_threshold_boundaries(self):
        # VIX < 15 → +2；VIX >= 30 → -2
        r_calm = classify_short_term_regime(0, 50, 14, 0, 3.0, 3.0)
        r_panic = classify_short_term_regime(0, 50, 35, 0, 3.0, 3.0)
        assert r_calm['score'] > r_panic['score']

    def test_components_includes_weights(self):
        r = classify_short_term_regime(10, 52, 18, 3, 3.0, 3.2)
        assert len(r['components']) == 5  # 五項全有
        names = [c[0] for c in r['components']]
        assert '出口 YoY' in names
        assert '台 PMI' in names
        assert 'VIX 波動' in names
        assert '外資籌碼' in names
        assert 'CPI 月降' in names

    def test_invalid_data_graceful(self):
        # 字串輸入不該炸
        r = classify_short_term_regime('bad', 'x', None, 'y', float('nan'), None)
        assert r['regime'] == '⚪ 資料不足'

    def test_cpi_month_drop_boosts_score(self):
        # 同樣其他指標，CPI 月降 0.4 vs 月升 0.4 應有顯著分數差
        r_drop = classify_short_term_regime(5, 51, 20, 0, 3.0, 3.4)
        r_rise = classify_short_term_regime(5, 51, 20, 0, 3.4, 3.0)
        assert r_drop['score'] > r_rise['score']

    def test_action_message_present(self):
        r = classify_short_term_regime(15, 54, 15, 5, 3.0, 3.3)
        assert r.get('action') and isinstance(r['action'], str)
        assert len(r['action']) > 5


# ════════════════════════════════════════════════════════════════════════════
# v19.173 — 拐點訊號分群聚合（修「4 個空頭訊號」誇大確信度）
# ════════════════════════════════════════════════════════════════════════════
def _sig(label: str, color: str) -> tuple:
    """建 pivot_signals 元素（label, icon, color, detail）—— 只有 label/color 有語意。"""
    return (label, '🔴', color, f'{label} 的敘述')


class TestAggregatePivotFamilies:
    """分群 + 分母聚合：共線性折減 + 資訊單調性。"""

    # ── 分群表本身的完整性 ────────────────────────────────────────
    def test_family_map_keys_are_all_registered_families(self):
        """PIVOT_FAMILY_OF 的 value 必須都是 PIVOT_FAMILIES 裡真的存在的 key。

        沒這條的話，打錯一個 family key 會讓那個訊號永遠歸不了群、
        從分子分母同時消失 —— 靜默失蹤比報錯危險。
        """
        _known = {k for k, _ in PIVOT_FAMILIES}
        _bad = {lab: fam for lab, fam in PIVOT_FAMILY_OF.items() if fam not in _known}
        assert not _bad, f'PIVOT_FAMILY_OF 指向不存在的 family：{_bad}'

    def test_detector_labels_are_registered(self):
        """`detect_cpi_fed_double_top` 實際吐出的 label 必須在分群表裡。

        這條抓的是「字元長得像但不是同一個」的坑（× U+00D7 vs x、全形空格、
        emoji 前後空白…）。label 是兩個檔之間唯一的契約，對不上就會讓
        通膨利率群永遠是空的，而且畫面上完全看不出來。
        """
        for _args in ((3.0, 3.3, 5.25, 5.33),      # strong
                      (3.2, 3.3, 5.25, 5.33)):     # weak
            _out = detect_cpi_fed_double_top(*_args)
            assert _out is not None
            assert _out['label'] in PIVOT_FAMILY_OF, (
                f"label {_out['label']!r} 不在 PIVOT_FAMILY_OF 裡")
            assert PIVOT_FAMILY_OF[_out['label']] == 'inflation'

    def test_every_family_has_at_least_one_signal_label(self):
        """每一群都要至少對應一個訊號 label，否則那群永遠是空的（殭屍分群）。"""
        _used = set(PIVOT_FAMILY_OF.values())
        _empty = [k for k, _ in PIVOT_FAMILIES if k not in _used]
        assert not _empty, f'以下 family 沒有任何訊號 label：{_empty}'

    # ── 核心：共線性折減 ──────────────────────────────────────────
    def test_same_family_signals_count_once(self):
        """同群三盞紅 → 只算 1 群偏空（群內取最壞、不累加）。

        這是本次修正的核心：「外資期貨大空單 + 散戶極度看多 + 外資連續賣超」
        全在籌碼群，是同一個因子的三種量測，不是三份獨立證據。
        """
        out = aggregate_pivot_families([
            _sig('外資期貨大量空單', TRAFFIC_RED),
            _sig('散戶極度看多（危險）', TRAFFIC_RED),
            _sig('外資連續賣超', TRAFFIC_RED),
        ])
        assert out['n_bear'] == 1          # 3 盞紅 → 1 群
        assert out['families']['chips']['side'] == 'bear'
        assert len(out['families']['chips']['labels']) == 3

    def test_three_same_family_reds_no_longer_declare_bear(self):
        """舊規則會說「🔴 3 個空頭訊號」，新規則只有 1 群 → 不宣稱方向。

        `PIVOT_MIN_SIDE_FAMILIES == 2` 是「群」而非「訊號」，故 1 群不成立。
        """
        out = aggregate_pivot_families([
            _sig('外資期貨大量空單', TRAFFIC_RED),
            _sig('散戶極度看多（危險）', TRAFFIC_RED),
            _sig('外資連續賣超', TRAFFIC_RED),
        ])
        assert PIVOT_MIN_SIDE_FAMILIES == 2
        assert out['n_bear'] < PIVOT_MIN_SIDE_FAMILIES
        assert out['verdict'] != 'bear'

    def test_worst_wins_inside_family(self):
        """群內一綠一紅 → 取最壞（bear），與登記順序無關。"""
        red_first = aggregate_pivot_families([
            _sig('外資期貨大量空單', TRAFFIC_RED),
            _sig('外資連續買超', TRAFFIC_GREEN),
        ])
        green_first = aggregate_pivot_families([
            _sig('外資連續買超', TRAFFIC_GREEN),
            _sig('外資期貨大量空單', TRAFFIC_RED),
        ])
        assert red_first['families']['chips']['side'] == 'bear'
        assert green_first['families']['chips']['side'] == 'bear'

    def test_cross_family_bears_do_declare(self):
        """跨群兩盞紅 → 成立（這是新舊規則等價的那一半）。"""
        out = aggregate_pivot_families([
            _sig('年線乖離過大', TRAFFIC_RED),       # 位階
            _sig('外資期貨大量空單', TRAFFIC_RED),   # 籌碼
        ])
        assert out['n_bear'] == 2
        assert out['verdict'] == 'bear'
        assert out['color'] == TRAFFIC_RED

    # ── 核心：分母揭露 + 資訊單調性 ───────────────────────────────
    def test_headline_shows_denominator(self):
        """結論句必須帶分母（可評估 K/N 群），不得只講分子。"""
        out = aggregate_pivot_families(
            [_sig('年線乖離過大', TRAFFIC_RED),
             _sig('外資期貨大量空單', TRAFFIC_RED)],
            evaluable={'trend', 'level', 'liquidity', 'chips', 'cycle'},
        )
        assert out['n_total'] == len(PIVOT_FAMILIES)
        assert out['n_evaluable'] == 5
        assert f"{out['n_evaluable']}/{out['n_total']}" in out['headline']
        assert '可評估' in out['headline']

    def test_unevaluated_excluded_from_denominator_and_disclosed(self):
        """沒資料的群 → 不進分母、不計多空，且必須在 note 裡點名。"""
        out = aggregate_pivot_families(
            [_sig('年線乖離過大', TRAFFIC_RED)],
            evaluable={'level'},
        )
        assert out['n_evaluable'] == 1                  # 只有位階群可評估
        assert out['families']['cycle']['side'] == 'unevaluated'
        assert out['n_bear'] == 1 and out['n_bull'] == 0 and out['n_neutral'] == 0
        assert '未評估' in out['note']
        assert '景氣（NDC 對策 / 領先指標）' in out['note']

    def test_missing_data_never_pushes_verdict_bullish(self):
        """§資訊單調性：把「未評估」拿掉不得讓結論變多。

        舊 bug 的形狀是「少抓到一個來源 → 分子變小 → 紅燈掉成白燈」。
        這裡驗證反向：未評估的群既不加到 n_bull 也不加到 n_bear。
        """
        few = aggregate_pivot_families(
            [_sig('年線乖離過大', TRAFFIC_RED),
             _sig('外資期貨大量空單', TRAFFIC_RED)],
            evaluable={'level', 'chips'},
        )
        many = aggregate_pivot_families(
            [_sig('年線乖離過大', TRAFFIC_RED),
             _sig('外資期貨大量空單', TRAFFIC_RED)],
            evaluable={k for k, _ in PIVOT_FAMILIES},
        )
        # 多知道 4 群「有資料但沒觸發」→ 偏空群數不變、方向不變，只有分母變大
        assert few['n_bear'] == many['n_bear'] == 2
        assert few['verdict'] == many['verdict'] == 'bear'
        assert many['n_evaluable'] > few['n_evaluable']
        assert many['n_neutral'] == 4

    def test_evaluable_but_silent_family_is_neutral_not_missing(self):
        """有資料但沒觸發訊號 → 'neutral' 且**計入分母**（不是「未評估」）。"""
        out = aggregate_pivot_families([], evaluable={'trend'})
        assert out['families']['trend']['side'] == 'neutral'
        assert out['n_evaluable'] == 1
        # 有資料的群不該被列進「未評估」——那會讓分母少算，等於謊報資料完整度
        assert '趨勢（均線結構）' not in out['unevaluated']
        assert len(out['unevaluated']) == len(PIVOT_FAMILIES) - 1

    # ── 邊界 ──────────────────────────────────────────────────────
    def test_empty_input_is_insufficient_not_bullish(self):
        """§1：完全沒資料 → 'insufficient'，**不得**回綠或紅。"""
        out = aggregate_pivot_families([], evaluable=None)
        assert out['verdict'] == 'insufficient'
        assert out['n_evaluable'] == 0
        assert out['color'] == TRAFFIC_YELLOW
        assert '不宣稱方向' in out['headline']

    def test_none_input_does_not_crash(self):
        out = aggregate_pivot_families(None, None)
        assert out['verdict'] == 'insufficient'

    def test_tie_is_mixed(self):
        """一群多、一群空 → 平手 → 訊號分歧（不偏袒任一方）。"""
        out = aggregate_pivot_families([
            _sig('年線乖離過大', TRAFFIC_RED),
            _sig('M1B>M2 黃金交叉', TRAFFIC_GREEN),
        ])
        assert out['n_bear'] == 1 and out['n_bull'] == 1
        assert out['verdict'] == 'mixed'

    def test_unknown_label_is_surfaced_not_swallowed(self):
        """對不上分群表的 label 要被回報（否則新增訊號會靜默失蹤）。"""
        out = aggregate_pivot_families([_sig('某個沒登記的新訊號', TRAFFIC_RED)])
        assert '某個沒登記的新訊號' in out['unknown_labels']
        assert out['n_bear'] == 0

    def test_malformed_signal_tuple_is_surfaced(self):
        """形狀不對的元素不炸、但也不吞。"""
        out = aggregate_pivot_families([('只有兩個欄位', '🔴')])
        assert out['unknown_labels']
        assert out['verdict'] == 'insufficient'

    def test_bull_side_symmetric(self):
        """多頭方向與空頭方向規則對稱。"""
        out = aggregate_pivot_families([
            _sig('年線深度低估', TRAFFIC_GREEN),        # 位階
            _sig('M1B>M2 黃金交叉', TRAFFIC_GREEN),     # 資金
        ])
        assert out['n_bull'] == 2
        assert out['verdict'] == 'bull'
        assert out['color'] == TRAFFIC_GREEN
        assert '偏多' in out['headline']

    def test_yellow_signal_counts_as_neutral_family(self):
        """黃燈訊號 → 該群 neutral（進分母，不計多空）。"""
        out = aggregate_pivot_families([_sig('台幣貶值', TRAFFIC_YELLOW)])
        assert out['families']['liquidity']['side'] == 'neutral'
        assert out['n_neutral'] == 1
        assert out['n_bear'] == 0 and out['n_bull'] == 0

    def test_live_shape_four_reds_collapse_to_three_families(self):
        """線上那組「4 個空頭訊號」在新規則下 → 3 群偏空（不是 4）。

        實測組合（見 STATE.md v19.173 稽核）：
          年線乖離過大(位階) / 外資期貨大量空單(籌碼) / 散戶極度看多(籌碼)
          / 領先指標 6M 由正轉負(景氣)
        籌碼群的兩盞紅屬同一因子 → 併為 1 群，故 4 訊號 = 3 群。
        """
        out = aggregate_pivot_families(
            [_sig('年線乖離過大', TRAFFIC_RED),
             _sig('外資期貨大量空單', TRAFFIC_RED),
             _sig('散戶極度看多（危險）', TRAFFIC_RED),
             _sig('領先指標 6M 由正轉負', TRAFFIC_RED)],
            evaluable={k for k, _ in PIVOT_FAMILIES},
        )
        assert out['n_bear'] == 3
        assert out['n_evaluable'] == 6
        assert out['verdict'] == 'bear'      # 燈號顏色不變，仍是 🔴
        assert '3 群偏空' in out['headline']
        assert '可評估 6/6 群' in out['headline']
