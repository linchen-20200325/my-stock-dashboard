"""macro_helpers.py 純函式 unit test — Phase 7A-Ext / 7E。"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_helpers import (
    BULL_MIN_SCORE,
    HEALTH_DEFENSE_THRESHOLD,
    calc_traffic_light,
    classify_long_term_regime,
    classify_short_term_regime,
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
        assert tl['color'] == '#3fb950'
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
        # jqavg=80 + score=0 + fnet=0 → health=80*0.4+0+0=32... 改用更貼近 38 的設定
        # jqavg=70 + score=1 + fnet=0 → health=70*0.4+(1/5*100)*0.4+0=28+8=36 ≥ 35 → 不防禦
        mkt = {'score': 1, 'regime': 'neutral'}
        jq  = {'avg': 70}
        cl  = {'inst': {}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['health'] == pytest.approx(36.0)
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
        # health = avg*0.4 + min(score/5*100,100)*0.4 + (20 if fnet>0 else 0)
        # avg=50, score=5, fnet=100 → 20 + 40 + 20 = 80
        mkt = {'score': 5, 'regime': 'bull'}
        jq  = {'avg': 50}
        cl  = {'inst': {'外資': {'net': 100}}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['health'] == pytest.approx(80.0)


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
    """v18.169：MK 黃金拐點偵測 — CPI YoY × Fed Funds Rate 雙頂回落。"""

    def test_strong_signal_cpi_drop_fed_drop(self):
        # CPI 月降 0.3ppt + Fed 月降 0.08ppt → 強訊號 ⭐
        sig = detect_mk_golden_inflection(3.0, 3.3, 5.25, 5.33)
        assert sig is not None
        assert sig['strength'] == 'strong'
        assert sig['color'] == '#3fb950'
        assert '⭐' in sig['icon']
        assert 'MK 黃金拐點' in sig['label']

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
        assert sig['color'] == '#d29922'
        assert 'MK 拐點觀察中' in sig['label']

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
        assert len(r['components']) == 3  # CPI + PMI + MK 拐點(0)

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
