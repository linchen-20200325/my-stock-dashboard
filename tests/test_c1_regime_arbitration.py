"""tests/test_c1_regime_arbitration.py — C1：大盤 regime 唯一仲裁點（v19.182）。

修的是什麼
----------
同一天、同一份資料下，全站有 4 個各自為政的 regime producer：

- **P1** `calc_traffic_light()` 的 if/elif 決策樹（消費端由 **icon 反推** regime）
  → 總經頁燈號卡 / 戰情概覽 / 今日作戰室 / 5 分鐘清單 / section_news_ai
- **P2** raw `mkt_info['regime']` → `warroom_summary['regime']` → `get_macro_state()`
  → `AllocationDecision.regime` → 置底常駐條 / ETF 配置橫幅 / 個股組合評分
- **P3** `mkt_info.get('regime', 'neutral')` 直讀（未載入時捏 `'neutral'`）
  → ETF 核衛目標 60/40 vs 70/30 / ETF AI prompt
- **P4** `warroom_summary['traffic_light']` 的中文 substring 比對 → 個股組合 🚦 燈號卡

P1 的分支 1/2（外資期貨大額淨空 / 健康分跌破門檻）**直接判 🔴，不看
`mkt_info['regime']`**，於是趨勢 bull + 總經惡化的那天，四個消費端會給出
互相矛盾的答案。

本檔的斷言策略
--------------
**一律行為斷言**（建構輸入 → 呼叫真函式 → 驗結果）。全檔只有一處看原始碼
（`TestNoSecondImplementation`），而它檢查的是「有沒有第二份實作」這個**結構性質**，
不是「某一行長得像不像」—— 照抄實作字面的守衛永遠不會發現實作本身有問題。

`TestLegacyTreeParity` 在測試檔內**重寫一份 v19.181 的舊決策樹**，對輸入網格
逐點對拍，證明本次重構「行為零位移」。舊樹是獨立的第二份實作，不是抄 arbiter
的字面，所以 arbiter 判定若被改壞它會變紅。
"""
from __future__ import annotations

import ast
import itertools
import pathlib

import pandas as pd
import pytest

from shared.allocation_decision import (
    allocation_sleeves,
    build_allocation_decision,
)
from shared.macro_calibration import load_calibrated_thresholds
from shared.regime_arbiter import (
    DEFENSE_MAX_MARKET_SCORE,
    LIGHT_BEAR,
    LIGHT_BULL,
    LIGHT_NEUTRAL,
    LIGHT_UNKNOWN,
    SOURCE_BEAR_TREND,
    SOURCE_BULL_SCORE,
    SOURCE_DEFENSE_FUTURES,
    SOURCE_DEFENSE_HEALTH,
    SOURCE_NEUTRAL_FALLTHROUGH,
    SOURCE_UNLOADED,
    arbitrate_regime,
    is_foreign_futures_defense,
)
from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
from src.compute.macro import calc_traffic_light
from src.services.macro_state_locker import get_macro_state

_REPO = pathlib.Path(__file__).resolve().parents[1]
_HD_THR, _BULL_THR = load_calibrated_thresholds()


# ══════════════════════════════════════════════════════════════════════════
# 共用 fixture / helper
# ══════════════════════════════════════════════════════════════════════════
def _no_file(tmp_path) -> str:
    """指向一個不存在的 macro_state.json → 強制只走 warroom 來源。"""
    return str(tmp_path / "no_such_macro_state.json")


def _li(fut_net=None, leek=50.0):
    """先行指標 DataFrame（`calc_traffic_light` 的 li_latest）。"""
    return pd.DataFrame({'外資大小': [fut_net], '韭菜指數': [leek]})


def _warroom_full(tl: dict, mkt: dict) -> dict:
    """完整 warroom —— 逐欄對齊 `section_traffic_light.render_traffic_light_top()`。

    含 C1 新增的 `effective_regime` / `light` / `regime_source`。
    """
    return {
        'traffic_light': tl['label'],
        'health_score': tl['health'],
        'regime': mkt.get('regime', 'neutral'),          # 趨勢面輸入（舊 key）
        'effective_regime': tl['effective_regime'],       # 結論
        'light': tl['light'],
        'regime_source': tl['regime_source'],
        'market_score': tl['score'],
        'jingqi_avg': tl['jqavg'],
        'leek_index': tl['leek'],
        'foreign_net_bn': tl['fnet'],
        'futures_net': tl['fut_net'],
        'confidence_pct': tl['conf'],
    }


def _warroom_primitives_only(tl: dict, mkt: dict) -> dict:
    """只有 primitives 的 warroom —— 對齊 `section_state.py` 的 `_wr_sum.update({...})`。

    那支 writer（本輪不在授權改動範圍）**不寫** `effective_regime`，而且它跑在
    `render_traffic_light_top` 之後、會把 `'regime'` 蓋回 raw 值。
    `get_macro_state` 必須在這種形狀下也給出同一個答案，否則畫面會因為
    render 順序不同而漂移。
    """
    return {
        'traffic_light': tl['label'],
        'health_score': tl['health'],
        'regime': mkt.get('regime', 'neutral'),
        'market_score': tl['score'],
        'jingqi_avg': tl['jqavg'],
        'leek_index': tl['leek'],
        'foreign_net_bn': tl['fnet'],
        'futures_net': tl['fut_net'],
        'confidence_pct': tl['conf'],
    }


# 舊碼的 icon → regime 反推表（`section_traffic_light.py` v19.181）。
# 保留在測試裡當**獨立對照組**：新實作的 `effective_regime` 必須與它一致，
# 才叫「行為零位移」。
_LEGACY_ICON_TO_REGIME = {'🔴': 'bear', '🟢': 'bull', '🟡': 'neutral'}


# ══════════════════════════════════════════════════════════════════════════
# ① arbiter 單元行為
# ══════════════════════════════════════════════════════════════════════════
class TestArbiterBranches:
    """五條分支各自的 regime / light / source。"""

    def test_defense_by_foreign_futures_overrides_bull_trend(self):
        v = arbitrate_regime(trend_regime='bull', market_score=1, health=60.0,
                             futures_net_lots=-35000)
        assert v.regime == 'bear'
        assert v.light == LIGHT_BEAR
        assert v.source == SOURCE_DEFENSE_FUTURES
        assert v.defense is True

    def test_defense_by_health_overrides_bull_trend(self):
        v = arbitrate_regime(trend_regime='bull', market_score=6, health=_HD_THR - 1,
                             futures_net_lots=None)
        assert v.regime == 'bear'
        assert v.source == SOURCE_DEFENSE_HEALTH
        assert v.defense is False          # 這條不是期貨防禦

    def test_bull_needs_both_trend_and_score(self):
        v = arbitrate_regime(trend_regime='bull', market_score=_BULL_THR,
                             health=80.0, futures_net_lots=None)
        assert (v.regime, v.light, v.source) == ('bull', LIGHT_BULL, SOURCE_BULL_SCORE)

    def test_bull_trend_but_low_score_falls_through_to_neutral(self):
        v = arbitrate_regime(trend_regime='bull', market_score=_BULL_THR - 1,
                             health=80.0, futures_net_lots=None)
        assert (v.regime, v.light, v.source) == (
            'neutral', LIGHT_NEUTRAL, SOURCE_NEUTRAL_FALLTHROUGH)

    @pytest.mark.parametrize('trend', ['bear', 'caution'])
    def test_bear_and_caution_trend(self, trend):
        v = arbitrate_regime(trend_regime=trend, market_score=3, health=80.0,
                             futures_net_lots=None)
        assert (v.regime, v.light, v.source) == ('bear', LIGHT_BEAR, SOURCE_BEAR_TREND)

    def test_neutral_fallthrough(self):
        v = arbitrate_regime(trend_regime='neutral', market_score=3, health=60.0,
                             futures_net_lots=None)
        assert (v.regime, v.light, v.source) == (
            'neutral', LIGHT_NEUTRAL, SOURCE_NEUTRAL_FALLTHROUGH)


class TestArbiterUnknownState:
    """§1 Fail Loud —— 未評估**絕不**退回 'neutral'。"""

    def test_is_loaded_false(self):
        v = arbitrate_regime(trend_regime='bull', market_score=6, health=90.0,
                             is_loaded=False)
        assert (v.regime, v.light, v.source) == ('unknown', LIGHT_UNKNOWN, SOURCE_UNLOADED)
        assert v.is_loaded is False

    @pytest.mark.parametrize('bad_health', [None, float('nan'), 'N/A', ''])
    def test_unusable_health_is_unknown_not_neutral(self, bad_health):
        v = arbitrate_regime(trend_regime='bull', market_score=6, health=bad_health)
        assert v.regime == 'unknown', (
            f'health={bad_health!r} 應視為未評估，實得 {v.regime!r} —— '
            "'neutral' 是一個市場判斷（🟡 震盪），不是缺值標記")
        assert v.light == LIGHT_UNKNOWN


class TestForeignFuturesDefenseThreshold:
    """門檻是 **30,000 口**（SSOT），不是 15,000 也不是 20,000。

    這組把 C1 任務描述裡「外資期貨 −20,000 口 → 🔴」那個誤判釘死：
    −20,000 **不會**觸發防禦。
    """

    def test_threshold_constant_is_30000(self):
        assert FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD == 30000

    def test_minus_20000_does_not_trigger(self):
        assert is_foreign_futures_defense(market_score=1, futures_net_lots=-20000) is False

    def test_exact_threshold_is_not_enough_strict_gt(self):
        """判定式是嚴格大於（`abs(fut) > 門檻`），剛好等於不觸發。"""
        assert is_foreign_futures_defense(
            market_score=1, futures_net_lots=-FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD) is False
        assert is_foreign_futures_defense(
            market_score=1,
            futures_net_lots=-(FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD + 1)) is True

    def test_long_side_never_defends(self):
        """淨多單再大也不是防禦訊號（方向必須為空）。"""
        assert is_foreign_futures_defense(market_score=1, futures_net_lots=+99999) is False

    def test_score_gate(self):
        """趨勢夠強（score ≥ 門檻）時，期貨空單視為避險而非轉空。"""
        assert is_foreign_futures_defense(
            market_score=DEFENSE_MAX_MARKET_SCORE, futures_net_lots=-99999) is False
        assert is_foreign_futures_defense(
            market_score=DEFENSE_MAX_MARKET_SCORE - 1, futures_net_lots=-99999) is True

    @pytest.mark.parametrize('missing', [None, float('nan'), '', 'N/A'])
    def test_missing_fut_net_neither_triggers_nor_raises(self, missing):
        """缺資料不是「沒有大空單」，但也不能拿它當防禦訊號 —— 且不得拋例外。"""
        assert is_foreign_futures_defense(market_score=1, futures_net_lots=missing) is False


# ══════════════════════════════════════════════════════════════════════════
# ② 與 v19.181 舊決策樹逐點對拍（行為零位移）
# ══════════════════════════════════════════════════════════════════════════
def _legacy_tree(trend_regime, score, health, fut_net) -> str:
    """v19.181 `calc_traffic_light` 的原始 if/elif 樹 → 舊碼的 `_tl_eff_reg`。

    **獨立重寫**（照 git 上的舊碼語意，不是引用 arbiter），才有對拍價值。
    舊碼流程：先算 `_defense`，再走四段 if/elif 決定 icon，
    最後由 `section_traffic_light` 用 `{'🔴':'bear','🟢':'bull','🟡':'neutral'}`
    反推 regime。
    """
    _defense = (fut_net is not None and score < DEFENSE_MAX_MARKET_SCORE
                and abs(fut_net) > FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
                and fut_net < 0)
    if _defense or health < _HD_THR:
        icon = '🔴'
    elif trend_regime == 'bull' and score >= _BULL_THR:
        icon = '🟢'
    elif trend_regime in ('caution', 'bear'):
        icon = '🔴'
    else:
        icon = '🟡'
    return _LEGACY_ICON_TO_REGIME[icon]


class TestLegacyTreeParity:
    """輸入網格上，新 arbiter 與舊決策樹**逐點一致**。"""

    _TRENDS = ('bull', 'neutral', 'bear', 'caution')
    _SCORES = (0, 1, 2, 3, 4, 5, 6)
    _HEALTHS = (0.0, 20.0, float(_HD_THR) - 0.1, float(_HD_THR), 50.0, 85.0, 100.0)
    _FUTS = (None, 0.0, -20000.0, -30000.0, -30001.0, -87455.0, 45000.0)

    def test_grid_parity(self):
        mismatches = []
        for trend, score, health, fut in itertools.product(
                self._TRENDS, self._SCORES, self._HEALTHS, self._FUTS):
            got = arbitrate_regime(
                trend_regime=trend, market_score=score, health=health,
                futures_net_lots=fut,
                health_defense_threshold=_HD_THR, bull_min_score=_BULL_THR,
            ).regime
            want = _legacy_tree(trend, score, health, fut)
            if got != want:
                mismatches.append(
                    f'trend={trend} score={score} health={health} fut={fut}: '
                    f'新={got} 舊={want}')
        assert not mismatches, (
            'arbiter 與 v19.181 舊決策樹不一致（本次重構宣稱行為零位移）：\n'
            + '\n'.join(mismatches[:20])
            + (f'\n…共 {len(mismatches)} 筆' if len(mismatches) > 20 else ''))


class TestCalcTrafficLightSelfConsistency:
    """`calc_traffic_light` 的 icon / light / effective_regime 三者必須同源。

    舊碼下游是「由 icon 反推 regime」；只要這三欄能互相還原，就證明
    重構沒有把畫面上的燈號和 canonical 結論分開。
    """

    _CASES = [
        # (mkt, jq, li)
        ({'score': 4, 'regime': 'bull', 'max_score': 4}, {'avg': 75}, None),
        ({'score': 3, 'regime': 'bull', 'max_score': 4}, {'avg': 75}, None),
        ({'score': 3, 'regime': 'neutral', 'max_score': 4}, {'avg': 60}, None),
        ({'score': 3, 'regime': 'bear', 'max_score': 4}, {'avg': 80}, None),
        ({'score': 3, 'regime': 'caution', 'max_score': 4}, {'avg': 80}, None),
        ({'score': 0, 'regime': 'bull', 'max_score': 4}, {'avg': 10}, None),
        ({'score': 1, 'regime': 'bull', 'max_score': 4}, {'avg': 60}, _li(-35000)),
    ]

    @pytest.mark.parametrize('mkt,jq,li', _CASES)
    def test_icon_light_and_effective_regime_agree(self, mkt, jq, li):
        tl = calc_traffic_light(mkt, jq, {'inst': {}}, li)
        assert tl is not None
        assert tl['light'] == tl['icon'], 'light 與 icon 不同步（兩者應同源）'
        assert _LEGACY_ICON_TO_REGIME[tl['icon']] == tl['effective_regime'], (
            f"icon={tl['icon']} 反推 ≠ effective_regime={tl['effective_regime']}")

    @pytest.mark.parametrize('mkt,jq,li', _CASES)
    def test_raw_regime_key_keeps_old_semantics(self, mkt, jq, li):
        """`regime` 這個舊 key 仍是**趨勢面輸入**，不得被偷偷改成結論。

        （畫面要靠它顯示「被壓制的反向訊號」。）
        """
        tl = calc_traffic_light(mkt, jq, {'inst': {}}, li)
        assert tl['regime'] == mkt['regime']

    def test_defense_case_reports_source(self):
        tl = calc_traffic_light({'score': 1, 'regime': 'bull', 'max_score': 4},
                                {'avg': 60}, {'inst': {}}, _li(-35000))
        assert tl['regime_source'] == SOURCE_DEFENSE_FUTURES
        assert tl['effective_regime'] == 'bear'
        assert tl['regime'] == 'bull'      # 趨勢面輸入仍看得見（矛盾要被揭露）


# ══════════════════════════════════════════════════════════════════════════
# ③ 【核心】矛盾情境：所有消費端拿到同一個答案
# ══════════════════════════════════════════════════════════════════════════
#
# 場景：趨勢面 regime='bull'、大盤評分 1（遠低於 BULL_MIN_SCORE=4）、
#       外資期貨淨空 35,000 口（> SSOT 門檻 30,000）。
# 修復前：
#   - 總經頁上半（P1，吃 icon）        → 🔴 空頭防禦
#   - 頁底常駐條（P2，吃 warroom.regime）→ 🟢 多頭市場
#   - ETF 核衛目標（P3，直讀 mkt_info） → 多頭 60/40
#   - 個股組合 🚦 卡（P4，中文 substring）→ 灰色（比對恆不命中）
# ══════════════════════════════════════════════════════════════════════════
_CONFLICT_MKT = {'score': 1, 'regime': 'bull', 'max_score': 4}
_CONFLICT_JQ = {'avg': 60}                 # health = 60*0.6 + 25*0.4 = 46 ≥ 35
_CONFLICT_FUT = -35000.0


class TestConflictScenarioAllConsumersAgree:

    @pytest.fixture()
    def tl(self):
        _tl = calc_traffic_light(_CONFLICT_MKT, _CONFLICT_JQ,
                                 {'inst': {'外資': {'net': -500}}, 'adl': 1},
                                 _li(_CONFLICT_FUT))
        assert _tl is not None
        # 前提成立才算真回歸：health 必須**高於**防禦門檻，
        # 否則這個案例會退化成「健康分觸發」而不是「趨勢 bull vs 期貨防禦」。
        assert _tl['health'] >= _HD_THR, (
            f"fixture 失效：health={_tl['health']} 已低於門檻 {_HD_THR}，"
            '本案例要驗的是「趨勢 bull 但外資期貨大空單」')
        return _tl

    def test_p1_traffic_light_card_is_bear(self, tl):
        """P1：總經頁燈號卡 / 戰情概覽 / 今日作戰室 / 5 分鐘清單 / news_ai。"""
        assert tl['icon'] == LIGHT_BEAR
        assert tl['effective_regime'] == 'bear'
        assert '空頭防禦' in tl['label']

    @pytest.mark.parametrize('build_wr', [_warroom_full, _warroom_primitives_only],
                             ids=['warroom_full', 'warroom_primitives_only'])
    def test_p2_allocation_decision_is_bear(self, tl, build_wr, tmp_path):
        """P2：置底常駐條 / ETF 配置橫幅（`AllocationDecision.regime`）。

        兩種 warroom 形狀都測 —— `section_state.py` 只寫 primitives，
        canonical 結論不得依賴「哪一支 writer 先跑」。
        """
        ms = get_macro_state(build_wr(tl, _CONFLICT_MKT),
                             state_file_path=_no_file(tmp_path))
        assert ms['regime'] == 'bear'
        assert ms['light'] == LIGHT_BEAR
        assert ms['trend_regime'] == 'bull'      # 反向訊號仍看得見
        d = build_allocation_decision(ms)
        assert d.regime == 'bear'
        assert d.regime_text == '空頭'

    @pytest.mark.parametrize('build_wr', [_warroom_full, _warroom_primitives_only],
                             ids=['warroom_full', 'warroom_primitives_only'])
    def test_p3_etf_core_satellite_target_is_bear(self, tl, build_wr, tmp_path):
        """P3：ETF 核衛目標 —— 必須是空頭 85/15，不是多頭 60/40。"""
        from src.compute.strategy import CoreSatelliteManager

        ms = get_macro_state(build_wr(tl, _CONFLICT_MKT),
                             state_file_path=_no_file(tmp_path))
        regime = ms['regime'] if ms['is_loaded'] else None
        mgr = CoreSatelliteManager(1_000_000, regime=regime)
        assert mgr.core_ratio == pytest.approx(0.85), (
            f'核衛目標吃到 regime={regime}，core_ratio={mgr.core_ratio}；'
            '多頭 0.60 代表 ETF 頁又走回 raw mkt_info 那條路')

    @pytest.mark.parametrize('build_wr', [_warroom_full, _warroom_primitives_only],
                             ids=['warroom_full', 'warroom_primitives_only'])
    def test_p4_group_light_card_is_red(self, tl, build_wr, tmp_path):
        """P4：個股組合 🚦 大盤燈號卡 —— 讀 canonical `light`。

        （舊碼對 label 找 '綠'/'黃'/'紅'，四個 label 全不含這三字 → 恆灰。
        見 `TestOldSubstringMatchWasDead`。）
        """
        ms = get_macro_state(build_wr(tl, _CONFLICT_MKT),
                             state_file_path=_no_file(tmp_path))
        assert ms['light'] == LIGHT_BEAR

    def test_all_four_consumers_report_the_same_regime(self, tl, tmp_path):
        """一句話總結：四個消費端的答案必須**完全相同**。"""

        ms = get_macro_state(_warroom_full(tl, _CONFLICT_MKT),
                             state_file_path=_no_file(tmp_path))
        d = build_allocation_decision(ms)
        answers = {
            'P1 燈號卡(effective_regime)': tl['effective_regime'],
            'P2 置底條(AllocationDecision)': d.regime,
            'P3 ETF(get_macro_state)': ms['regime'],
            'P4 組合燈號卡(light→regime)': {LIGHT_BULL: 'bull', LIGHT_NEUTRAL: 'neutral',
                                            LIGHT_BEAR: 'bear',
                                            LIGHT_UNKNOWN: 'unknown'}[ms['light']],
        }
        assert len(set(answers.values())) == 1, f'消費端答案分歧：{answers}'
        assert set(answers.values()) == {'bear'}

    def test_core_satellite_target_differs_from_trend_regime(self, tl, tmp_path):
        """反向護欄：如果有人把 canonical 改回 raw regime，本測試會抓到。

        趨勢 regime='bull' 對應 core_ratio 0.60；canonical 'bear' 對應 0.85。
        兩者不同才代表仲裁真的生效（否則這整組測試等於沒測）。
        """
        from src.compute.strategy import CoreSatelliteManager

        ms = get_macro_state(_warroom_full(tl, _CONFLICT_MKT),
                             state_file_path=_no_file(tmp_path))
        assert CoreSatelliteManager(1_000_000, regime=ms['regime']).core_ratio != \
            pytest.approx(CoreSatelliteManager(
                1_000_000, regime=ms['trend_regime']).core_ratio)


# ══════════════════════════════════════════════════════════════════════════
# ④ 【核心】未載入：所有消費端都是 ⬜，沒有任何一處退回 neutral
# ══════════════════════════════════════════════════════════════════════════
class TestUnloadedNeverFallsBackToNeutral:

    def test_macro_state_is_unknown(self, tmp_path):
        ms = get_macro_state(None, state_file_path=_no_file(tmp_path))
        assert ms['is_loaded'] is False
        assert ms['regime'] == 'unknown'
        assert ms['regime'] != 'neutral'
        assert ms['light'] == LIGHT_UNKNOWN
        assert ms['source'] == SOURCE_UNLOADED
        assert ms['health'] is None

    @pytest.mark.parametrize('wr', [
        None,
        {},
        {'traffic_light': '🟡 震盪整理'},                 # 有 label 但沒 health
        {'health_score': None, 'regime': 'bull'},         # health 明確為 None
        {'health_score': float('nan'), 'regime': 'bull'},  # health 是 NaN
    ], ids=['none', 'empty', 'label_only', 'health_none', 'health_nan'])
    def test_incomplete_warroom_is_unloaded(self, wr, tmp_path):
        ms = get_macro_state(wr, state_file_path=_no_file(tmp_path))
        assert ms['is_loaded'] is False, f'{wr!r} 不該被當成已評估'
        assert ms['regime'] == 'unknown'

    def test_p2_allocation_shows_unevaluated(self, tmp_path):
        """P2：置底常駐條 / 配置橫幅 —— 不得回填任何持股% 或多空結論。"""
        ms = get_macro_state(None, state_file_path=_no_file(tmp_path))
        d = build_allocation_decision(ms)
        assert d.is_loaded is False
        assert d.regime == 'unknown'
        assert d.regime_text == '未評估'
        assert d.range_text == '--'
        assert d.final_lo is None and d.final_hi is None and d.final_mid is None
        assert d.icon == LIGHT_UNKNOWN
        assert '未評估' in d.headline()

    def test_p2_etf_banner_sleeves_are_none(self, tmp_path):
        """P2：ETF 配置橫幅三桶 —— 未評估回 None（不假裝有一份配置建議）。"""
        ms = get_macro_state(None, state_file_path=_no_file(tmp_path))
        assert allocation_sleeves(build_allocation_decision(ms)) is None

    def test_p3_etf_core_satellite_cannot_judge(self, tmp_path):
        """P3：ETF 核衛 —— 拿不到目標比 → ⚪ 無法判定，**不得出現綠燈**。"""
        from src.compute.etf.portfolio_gates import (
            STATUS_UNKNOWN,
            evaluate_core_satellite_gate,
        )

        ms = get_macro_state(None, state_file_path=_no_file(tmp_path))
        regime = ms['regime'] if ms['is_loaded'] else None
        assert regime is None
        gate = evaluate_core_satellite_gate(
            [{'ticker': '0050.TW', 'value': 700_000},
             {'ticker': '00878.TW', 'value': 300_000}],
            target_core_pct=None, regime=(regime or ''))
        assert gate['status'] == STATUS_UNKNOWN
        assert '無法判定' in gate['headline']

    def test_p3_core_ratio_default_is_not_silently_neutral(self, tmp_path):
        """P3 反向護欄：`CoreSatelliteManager(regime=None)` 會**靜默**給 0.70
        （= 中性 70/30）。UI 端因此必須在 regime 未知時**根本不建 manager**。

        本測試把那個陷阱釘出來，說明為什麼 `etf_tab_portfolio` 的守衛條件是
        `if total_value > 0 and regime`。
        """
        from src.compute.strategy import CoreSatelliteManager
        assert CoreSatelliteManager(1_000_000, regime=None).core_ratio == \
            pytest.approx(CoreSatelliteManager(1_000_000, regime='neutral').core_ratio)

    def test_p4_group_light_card_is_grey_placeholder(self, tmp_path):
        ms = get_macro_state(None, state_file_path=_no_file(tmp_path))
        assert ms['light'] == LIGHT_UNKNOWN
        assert ms['traffic_light'] is None

    def test_no_consumer_returns_neutral(self, tmp_path):
        """總結：未載入時，四個消費端沒有**任何一處**吐出 'neutral' / 🟡。"""
        ms = get_macro_state(None, state_file_path=_no_file(tmp_path))
        d = build_allocation_decision(ms)
        answers = {
            'get_macro_state.regime': ms['regime'],
            'get_macro_state.light': ms['light'],
            'AllocationDecision.regime': d.regime,
            'AllocationDecision.icon': d.icon,
            'AllocationDecision.range_text': d.range_text,
        }
        assert 'neutral' not in answers.values(), f'仍有消費端退回中性：{answers}'
        assert LIGHT_NEUTRAL not in answers.values(), f'仍有消費端亮 🟡：{answers}'


# ══════════════════════════════════════════════════════════════════════════
# ⑤ P4 舊 substring 比對其實是死碼（永遠灰色）
# ══════════════════════════════════════════════════════════════════════════
class TestOldSubstringMatchWasDead:
    """`section_market_status` 舊碼找 '綠'/'黃'/'紅' —— 四個 label 全不含。

    這不是「比對脆弱」而是**恆不命中**：個股組合頁的 🚦 大盤燈號卡從來沒有
    亮過顏色。用真的 `calc_traffic_light` 產生 label 來證明，而不是抄字串。
    """

    _SCENARIOS = [
        ({'score': 4, 'regime': 'bull', 'max_score': 4}, {'avg': 75}, None),
        ({'score': 3, 'regime': 'neutral', 'max_score': 4}, {'avg': 60}, None),
        ({'score': 3, 'regime': 'bear', 'max_score': 4}, {'avg': 80}, None),
        ({'score': 0, 'regime': 'bull', 'max_score': 4}, {'avg': 10}, None),
        ({'score': 1, 'regime': 'bull', 'max_score': 4}, {'avg': 60}, _li(-35000)),
    ]

    def test_no_label_contains_colour_characters(self):
        offenders = []
        for mkt, jq, li in self._SCENARIOS:
            label = calc_traffic_light(mkt, jq, {'inst': {}}, li)['label']
            if any(ch in label for ch in ('綠', '黃', '紅')):
                offenders.append(label)
        assert not offenders, (
            'label 現在含顏色字，舊 substring 比對可能「意外」開始生效 —— '
            f'請確認 section_market_status 沒有退回 substring 寫法：{offenders}')

    def test_canonical_light_covers_every_scenario(self, tmp_path):
        """對照組：canonical `light` 在每個情境都給得出非灰的燈色。"""
        lights = set()
        for mkt, jq, li in self._SCENARIOS:
            tl = calc_traffic_light(mkt, jq, {'inst': {}}, li)
            ms = get_macro_state(_warroom_full(tl, mkt),
                                 state_file_path=_no_file(tmp_path))
            assert ms['light'] != LIGHT_UNKNOWN, f'{mkt} 應有明確燈色'
            lights.add(ms['light'])
        assert lights == {LIGHT_BULL, LIGHT_NEUTRAL, LIGHT_BEAR}, (
            f'三種燈色未全部出現（代表情境覆蓋不足）：{lights}')


# ══════════════════════════════════════════════════════════════════════════
# ⑥ 唯一實作（結構性質，非字面抄襲）
# ══════════════════════════════════════════════════════════════════════════
class TestNoSecondImplementation:
    """全域只能有一份 regime 決策樹。

    ⚠️ 本類是全檔唯一看原始碼的地方。它檢查的是**結構性質**（有沒有第二份
    實作 / 有沒有繞過唯一出口），不是「某一行長得像不像」——
    照抄實作字面的守衛永遠不會發現實作本身是錯的。
    掃描一律走 AST，因此 docstring / 註解裡提到這些名字不會誤判。
    """

    @staticmethod
    def _module_ast(rel: str) -> ast.Module:
        return ast.parse((_REPO / rel).read_text(encoding='utf-8'))

    @staticmethod
    def _attribute_reads(tree: ast.AST, key: str) -> list[int]:
        """找 `<expr>.get('<key>'...)` 與 `<expr>['<key>']` 的行號（AST，非字串）。"""
        hits = []
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get' and n.args
                    and isinstance(n.args[0], ast.Constant) and n.args[0].value == key):
                hits.append(n.lineno)
            elif (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                    and n.slice.value == key):
                hits.append(n.lineno)
        return hits

    @pytest.mark.parametrize('rel', [
        'src/ui/etf/etf_tab_portfolio.py',
        'src/ui/etf/etf_tab_single.py',
        'src/ui/etf/etf_tab_ai.py',
    ])
    def test_etf_tabs_do_not_read_mkt_info_regime(self, rel):
        """ETF 三個分頁不得再直讀 `mkt_info['regime']`（P3）。"""
        src_lines = (_REPO / rel).read_text(encoding='utf-8').splitlines()
        tree = self._module_ast(rel)
        bad = []
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get' and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == 'regime'):
                continue
            # 只在意「從 mkt_info 取」的那種
            if isinstance(n.func.value, ast.Name) and n.func.value.id == 'mkt_info':
                bad.append(f'{rel}:{n.lineno}: {src_lines[n.lineno - 1].strip()}')
        assert not bad, (
            'ETF 分頁又直讀 mkt_info["regime"]（那是趨勢面輸入，不是總經結論）：\n'
            + '\n'.join(bad)
            + '\n請改用 `allocation_service.get_macro_regime()`。')

    def test_group_status_card_has_no_colour_substring_match(self):
        """個股組合 🚦 卡不得再對中文 label 做 '綠'/'黃'/'紅' 比對（P4）。"""
        rel = 'src/ui/tabs/stock_grp_sections/section_market_status.py'
        src_lines = (_REPO / rel).read_text(encoding='utf-8').splitlines()
        tree = self._module_ast(rel)
        bad = []
        for n in ast.walk(tree):
            if not isinstance(n, ast.Compare):
                continue
            if not any(isinstance(op, ast.In) for op in n.ops):
                continue
            if isinstance(n.left, ast.Constant) and n.left.value in ('綠', '黃', '紅'):
                bad.append(f'{rel}:{n.lineno}: {src_lines[n.lineno - 1].strip()}')
        assert not bad, (
            "又出現 '綠'/'黃'/'紅' substring 比對 —— 那四個 label 根本不含這些字，"
            '比對恆不命中（卡片永遠灰色）：\n' + '\n'.join(bad))

    def test_traffic_light_section_does_not_reverse_map_icon(self):
        """`section_traffic_light` 不得再由 icon 反推 regime。

        判準：不存在「dict literal 的 key 是 🔴/🟢/🟡 且 value 是 regime 字串」。
        """
        rel = 'src/ui/tabs/macro/section_traffic_light.py'
        src_lines = (_REPO / rel).read_text(encoding='utf-8').splitlines()
        tree = self._module_ast(rel)
        bad = []
        for n in ast.walk(tree):
            if not isinstance(n, ast.Dict):
                continue
            keys = {k.value for k in n.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if keys & {LIGHT_BEAR, LIGHT_BULL, LIGHT_NEUTRAL}:
                vals = {v.value for v in n.values
                        if isinstance(v, ast.Constant) and isinstance(v.value, str)}
                if vals & {'bull', 'neutral', 'bear', 'caution'}:
                    bad.append(f'{rel}:{n.lineno}: {src_lines[n.lineno - 1].strip()}')
        assert not bad, (
            'icon → regime 反推表又出現了；決策樹知道自己走了哪條分支，'
            '應直接讀 `calc_traffic_light(...)["effective_regime"]`：\n' + '\n'.join(bad))
