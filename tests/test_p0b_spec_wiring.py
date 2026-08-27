"""tests/test_p0b_spec_wiring.py — P0-B 兩項接線缺口守衛（v19.175 新增）

本檔守兩個「靜態看 code 看不出來、要連上線才會現形」的缺口：

修正一：`us10y` / `dxy` 在五桶是**永久灰燈**
--------------------------------------------
兩者自 v18.286 就註冊了 `DangerSpec`（`shared/macro_buckets.py`），但
`macro_helpers.compute_five_bucket_summary()` 組 `values` dict 時**從來沒有
這兩個 key** → `values.get(s.key)` 恆為 None → `classify_danger(None)` → gray。
實機證據：五桶明細印「⬜ 10Y 公債殖利率：—」，同一頁國際指標卡卻印
「10Y公債殖利率 4.63 %」、總經警示印「🟢 DXY 美元指數 99.75」。

本檔守的不變式：
  1. **有值就要亮燈**（接線存在）
  2. **T1 官方源優先**（FRED DGS10 > Yahoo ^TNX，§2.1 不平均）
  3. **越界就回灰、不猜尺度**（§1 + §3.2；防 DXY→UUP 假綠 / ^TNX×10 假紅）
  4. **其餘 14 條 spec 判級行為零變更**（回歸守衛）

修正二：`20–20%` 怪字串（SSOT 模組自己漏網）
--------------------------------------------
`AllocationDecision.range_text` 有 lo==hi 收斂邏輯，但同檔
`build_allocation_decision()` 組 `_drivers` 時用 raw f-string 拼
`→ {lo}–{hi}%` 繞過它，線上兩處照樣印「→ 20–20%」。
本檔守：格式化只有一份實作（AST 掃描 + 行為斷言）。

⚠️ 本檔只測 L0 純函式 + L2 純函式，**不碰 streamlit / 不做網路 I/O**。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from shared import macro_buckets as mb
from shared.allocation_decision import (
    Cap,
    _fmt_range,
    build_allocation_decision,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ALLOC_SRC_PATH = _REPO_ROOT / 'shared' / 'allocation_decision.py'
_DAILY_CHECKLIST_PATH = _REPO_ROOT / 'src' / 'services' / 'daily_checklist.py'

#: U+2013 EN DASH —— 就是線上「20–20%」用的那一個字元（**不是** ASCII '-'）。
EN_DASH = '–'

#: 線上實測值（2026-08-05 擷取自同一頁面），用來算「接線後燈號會不會變」。
LIVE_US10Y_PCT = 4.63     # 國際指標卡：10Y公債殖利率 4.63 %
LIVE_DXY_POINTS = 99.75   # 總經警示：🟢 DXY 美元指數 99.75


# ════════════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════════════
def _intl_df(close: float) -> pd.DataFrame:
    """模擬 `cl_data['intl'][name]` —— fetch_single 產出的 lower-case OHLCV。"""
    return pd.DataFrame(
        {'open': [close], 'high': [close], 'low': [close],
         'close': [close], 'volume': [0]},
        index=pd.DatetimeIndex(['2026-08-05']),
    )


def _detail(summary: dict, bucket: str, key: str) -> dict:
    """從五桶 summary 取某桶某指標的明細列。"""
    for d in summary[bucket]['details']:
        if d['key'] == key:
            return d
    raise AssertionError(f'{bucket} 桶找不到 key={key} 的明細列')


def _five(**kw) -> dict:
    from src.compute.macro import compute_five_bucket_summary
    return compute_five_bucket_summary(**kw)


# ════════════════════════════════════════════════════════════════
# 修正一 A. 接線存在（本次修的核心 bug）
# ════════════════════════════════════════════════════════════════
class TestUs10yDxyWired:

    def test_regression_they_were_permanently_gray(self):
        """釘住 bug 的形狀：沒有任何來源時仍應是 gray（§1 不偽綠）。

        這條**不是**在保護舊 bug —— 沒資料本來就該灰。真正的 bug 是
        「有資料也灰」，由下面兩條測。
        """
        out = _five()
        assert _detail(out, 'mid', 'us10y')['danger'] == 'gray'
        assert _detail(out, 'mid', 'dxy')['danger'] == 'gray'
        assert _detail(out, 'mid', 'us10y')['value_str'] == '—'

    def test_us10y_lights_up_from_macro_info(self):
        """macro_info['us10y']['current'] = 4.63（FRED DGS10，單位 %）→ 🟡。

        手算：high_bad，yellow=4.5 / red=5.0；4.63 ≥ 4.5 且 < 5.0 → yellow。
        """
        out = _five(macro_info={'us10y': {'current': LIVE_US10Y_PCT}})
        _d = _detail(out, 'mid', 'us10y')
        assert _d['danger'] == 'yellow'
        assert _d['value_str'] == '4.63%'      # decimals=2 + unit='%'

    def test_us10y_accepts_value_key_alias(self):
        """fetch_us10y_block 同時寫 current 與 value；只有 value 時也要接得到。"""
        out = _five(macro_info={'us10y': {'value': 5.4}})
        assert _detail(out, 'mid', 'us10y')['danger'] == 'red'   # ≥5.0

    def test_us10y_falls_back_to_yahoo_tnx(self):
        """FRED 全敗（current/value 皆 None）→ 退 Yahoo ^TNX（cl_data.intl）。"""
        out = _five(
            macro_info={'us10y': {'_err': 'fredgraph:HTTP503',
                                  'current': None, 'value': None}},
            cl_data={'intl': {mb.CL_INTL_KEY_US10Y: _intl_df(4.63)}},
        )
        assert _detail(out, 'mid', 'us10y')['danger'] == 'yellow'

    def test_dxy_lights_up_from_cl_data_intl(self):
        """cl_data['intl']['美元指數 DXY'] 收盤 99.75 → 🟢（< 105）。"""
        out = _five(cl_data={'intl': {mb.CL_INTL_KEY_DXY: _intl_df(LIVE_DXY_POINTS)}})
        _d = _detail(out, 'mid', 'dxy')
        assert _d['danger'] == 'green'
        assert _d['value_str'] == '99.8'       # decimals=1 + unit=''

    def test_dxy_red_above_110(self):
        out = _five(cl_data={'intl': {mb.CL_INTL_KEY_DXY: _intl_df(112.0)}})
        assert _detail(out, 'mid', 'dxy')['danger'] == 'red'


# ════════════════════════════════════════════════════════════════
# 修正一 B. §2.1 權威分級：T1 FRED 優先，禁止平均
# ════════════════════════════════════════════════════════════════
class TestUs10ySourcePriority:

    def test_fred_wins_over_yahoo_and_never_averages(self):
        """兩源同時有值且不同 → 取 T1 FRED，**不平均**（§2.1）。

        FRED=4.63（yellow）vs Yahoo=3.00（green）；平均 3.815 也會是 green，
        故用「值字串」而非只看燈號來釘死取的是哪一源。
        """
        out = _five(
            macro_info={'us10y': {'current': 4.63}},
            cl_data={'intl': {mb.CL_INTL_KEY_US10Y: _intl_df(3.00)}},
        )
        _d = _detail(out, 'mid', 'us10y')
        assert _d['value_str'] == '4.63%'
        assert _d['danger'] == 'yellow'


# ════════════════════════════════════════════════════════════════
# 修正一 C. §3.2 合理範圍：越界回灰、**不猜尺度**（§1）
#   這是本次接線最危險的副作用防線 —— 沒有它，接上去反而製造假燈號。
# ════════════════════════════════════════════════════════════════
class TestPlausibilityGuard:

    def test_dxy_uup_fallback_is_gray_not_false_green(self):
        """DXY 上游備援鏈 DX-Y.NYB → DX=F → **UUP**（ETF ~27 美元）。

        落到 UUP 時欄名不變但尺度差約 4 倍。27.5 < 105 會被判「🟢 綠」＝**假綠**，
        比灰燈危險（§1：錯的數字比沒有數字更危險）→ 必須是 gray。
        """
        out = _five(cl_data={'intl': {mb.CL_INTL_KEY_DXY: _intl_df(27.5)}})
        _d = _detail(out, 'mid', 'dxy')
        assert _d['danger'] == 'gray', 'UUP 尺度被當成 DXY → 假綠（§1 違憲）'
        assert _d['value_str'] == '—', '越界值不得顯示成看似正常的數字'

    def test_us10y_times_ten_convention_is_gray_not_false_red(self):
        """^TNX 若改回「殖利率×10」慣例（46.3）→ 46.3 ≥ 5.0 會判假紅 → 須 gray。

        `compute/risk/reconcile.py:106` 文件寫的正是 ×10 慣例，實機卻是直接 %；
        兩種慣例並存 = 隨時可能翻轉，這條就是翻轉時的攔截點。
        """
        out = _five(cl_data={'intl': {mb.CL_INTL_KEY_US10Y: _intl_df(46.3)}})
        assert _detail(out, 'mid', 'us10y')['danger'] == 'gray'

    def test_out_of_range_source_falls_through_to_next_source(self):
        """T1 越界 → 跳過該源改用 T2（而非直接放棄）。"""
        out = _five(
            macro_info={'us10y': {'current': 463.0}},   # 明顯壞值（×100）
            cl_data={'intl': {mb.CL_INTL_KEY_US10Y: _intl_df(4.63)}},
        )
        _d = _detail(out, 'mid', 'us10y')
        assert _d['danger'] == 'yellow'
        assert _d['value_str'] == '4.63%'

    def test_guard_never_rescales(self):
        """§1：越界一律拒收，**不得**自行 /10 或 ×10「救回來」。

        46.3 若被偷偷除以 10 會變成合法的 4.63（yellow）→ 這條會 fail。
        """
        out = _five(cl_data={'intl': {mb.CL_INTL_KEY_US10Y: _intl_df(46.3)}})
        assert _detail(out, 'mid', 'us10y')['value_str'] == '—'

    @pytest.mark.parametrize('value,expected', [
        (0.0, True),      # 邊界含端點
        (20.0, True),
        (-0.01, False),
        (20.01, False),
        (4.63, True),
        (None, False),
        (float('nan'), False),
        ('abc', False),
    ])
    def test_within_valid_range_us10y(self, value, expected):
        assert mb.within_valid_range(value, mb.SPECS_BY_KEY['us10y']) is expected

    def test_within_valid_range_no_bounds_means_no_check(self):
        """未設 valid_* 的 spec → 一律 True（維持既有行為，零回歸）。"""
        _vix = mb.SPECS_BY_KEY['vix']
        assert _vix.valid_min is None and _vix.valid_max is None
        assert mb.within_valid_range(999.0, _vix) is True
        assert mb.within_valid_range(-999.0, _vix) is True
        assert mb.within_valid_range(None, _vix) is False   # 沒值就是沒值


# ════════════════════════════════════════════════════════════════
# 修正一 D. 回歸守衛：只有 us10y / dxy 掛範圍，其餘 14 條零變更
# ════════════════════════════════════════════════════════════════
class TestNoCollateralDamage:

    def test_only_us10y_dxy_have_valid_range(self):
        _with_range = {s.key for s in mb.BUCKET_DANGER_SPECS
                       if s.valid_min is not None or s.valid_max is not None}
        assert _with_range == {'us10y', 'dxy'}, (
            '本次刻意只給新接線的兩條掛 §3.2 範圍；替其他 spec 加範圍屬行為變更，'
            '需獨立提案（例如 PMI 已有 signal_thresholds.PMI_VALID_MIN/MAX）'
        )

    def test_classify_danger_untouched_by_range_fields(self):
        """`classify_danger` **沒有**被改成會看 valid_*（避免全域行為變更）。

        直接餵越界值給 classify_danger 仍應照門檻判級；過濾發生在取值端。
        """
        _spec = mb.SPECS_BY_KEY['dxy']
        assert mb.classify_danger(27.5, _spec) == 'green'    # 純門檻判級不變
        assert mb.classify_danger(112.0, _spec) == 'red'

    def test_other_buckets_unchanged_when_us10y_dxy_present(self):
        """接線只影響 mid 桶；long / short / chips / news 不受波及。"""
        _base = _five(
            macro_info={'vix': {'current': 15}, 'ndc_signal': {'score': 28}},
            warroom_summary={'health_score': 70},
        )
        _with = _five(
            macro_info={'vix': {'current': 15}, 'ndc_signal': {'score': 28},
                        'us10y': {'current': 4.63}},
            warroom_summary={'health_score': 70},
            cl_data={'intl': {mb.CL_INTL_KEY_DXY: _intl_df(99.75)}},
        )
        for _b in ('long', 'short', 'chips', 'news'):
            assert _base[_b]['level'] == _with[_b]['level']
            assert _base[_b]['details'] == _with[_b]['details']


# ════════════════════════════════════════════════════════════════
# 修正一 E. 行為變更的具體影響（線上實測值代入）
# ════════════════════════════════════════════════════════════════
class TestMidBucketBehaviourChange:
    """接上去之後「中期」桶多兩盞燈 —— 這裡把實際影響釘死成可驗證的事實。"""

    def test_mid_bucket_now_has_six_lights(self):
        assert [s.key for s in mb.specs_for_bucket('mid')] == [
            'ism_pmi', 'us_core_cpi', 'tw_export', 'bias_240', 'us10y', 'dxy',
        ]

    def test_live_values_do_not_flip_a_red_mid_bucket(self):
        """線上實測情境：BIAS240 +32.7% 已經是 🔴，新增兩盞不改變 worst-of。

        代入 10Y=4.63 → 🟡、DXY=99.75 → 🟢；worst-of(紅,綠,綠,紅,黃,綠) 仍是紅。
        紅燈主因（headline / 過熱 vs 惡化標籤）也不變，因為新增的兩盞都不是紅。
        """
        _kw = dict(
            macro_info={'ism_pmi': {'value': 52}, 'us_core_cpi': {'yoy': 2.8},
                        'tw_export': {'yoy': 54.6}},
            bias_info={'bias_240': 32.7},
        )
        _before = _five(**_kw)
        _after = _five(
            **_kw,
            cl_data={'intl': {mb.CL_INTL_KEY_US10Y: _intl_df(LIVE_US10Y_PCT),
                              mb.CL_INTL_KEY_DXY: _intl_df(LIVE_DXY_POINTS)}},
        )
        assert _before['mid']['level'] == 'red'
        assert _after['mid']['level'] == 'red'
        assert _after['mid']['label'] == _before['mid']['label'] == '循環過熱'
        assert _after['mid']['headline'] == _before['mid']['headline']
        assert _detail(_after, 'mid', 'us10y')['danger'] == 'yellow'
        assert _detail(_after, 'mid', 'dxy')['danger'] == 'green'

    def test_all_green_mid_bucket_can_now_turn_yellow(self):
        """**這是真正的行為變更**：原本全綠的中期桶，10Y ≥ 4.5 會讓它變 🟡。

        接線前 us10y 恆 gray（gray 不參與 worst-of）→ 桶維持 green；
        接線後 4.63 → yellow → 桶被拉成 yellow「局部走弱」。
        """
        _green_macro = {'ism_pmi': {'value': 55}, 'us_core_cpi': {'yoy': 2.0},
                        'tw_export': {'yoy': 5}}
        _bias = {'bias_240': 5}

        _before = _five(macro_info=_green_macro, bias_info=_bias)
        assert _before['mid']['level'] == 'green'

        _after = _five(macro_info={**_green_macro, 'us10y': {'current': 4.63}},
                       bias_info=_bias)
        assert _after['mid']['level'] == 'yellow'
        assert _after['mid']['label'] == '局部走弱'


# ════════════════════════════════════════════════════════════════
# 修正一 F. 邊界輸入（§6：3 個最容易讓這段出錯的輸入）
# ════════════════════════════════════════════════════════════════
class TestWiringEdgeCases:

    def test_intl_missing_none_and_empty_df(self):
        for _cl in (
            None,
            {},
            {'intl': None},
            {'intl': {}},
            {'intl': {mb.CL_INTL_KEY_DXY: None}},
            {'intl': {mb.CL_INTL_KEY_DXY: pd.DataFrame()}},
            {'intl': {mb.CL_INTL_KEY_DXY: pd.DataFrame({'open': [1.0]})}},  # 缺 close
        ):
            out = _five(cl_data=_cl)
            assert _detail(out, 'mid', 'dxy')['danger'] == 'gray', f'cl_data={_cl!r}'

    def test_intl_capitalised_close_column(self):
        """calc_stats 同時支援 'close' / 'Close'；取值端不可只認一種。"""
        _df = pd.DataFrame({'Close': [99.75]}, index=pd.DatetimeIndex(['2026-08-05']))
        out = _five(cl_data={'intl': {mb.CL_INTL_KEY_DXY: _df}})
        assert _detail(out, 'mid', 'dxy')['danger'] == 'green'

    def test_non_numeric_and_nan_are_gray(self):
        out = _five(macro_info={'us10y': {'current': 'N/A'}})
        assert _detail(out, 'mid', 'us10y')['danger'] == 'gray'
        out2 = _five(macro_info={'us10y': {'current': float('nan')}})
        assert _detail(out2, 'mid', 'us10y')['danger'] == 'gray'

    def test_macro_info_us10y_not_a_dict(self):
        """上游若把 us10y 寫成純量（契約破壞）→ 灰燈，不得 raise。"""
        out = _five(macro_info={'us10y': 4.63})
        assert _detail(out, 'mid', 'us10y')['danger'] == 'gray'


# ════════════════════════════════════════════════════════════════
# 修正一 G. key 名漂移守衛（L0 鏡像 vs L3 SSOT）
# ════════════════════════════════════════════════════════════════
def test_intl_key_mirror_matches_daily_checklist():
    """`macro_buckets.CL_INTL_KEY_*` 必須 == `daily_checklist.INTL_MAP` 的 key。

    L0 不可 import L3（§8.2 跨層上行），故用 AST 讀原始碼比對 —— 這樣既不
    破壞分層、也不需要把 streamlit / plotly 拉進單元測試。
    key 名一旦在 L3 改掉而 L0 沒跟，燈號會**無聲**退回永久灰（正是本次的 bug）。
    """
    _tree = ast.parse(_DAILY_CHECKLIST_PATH.read_text(encoding='utf-8'))
    _intl_map = None
    for _node in ast.walk(_tree):
        if isinstance(_node, ast.Assign):
            for _t in _node.targets:
                if isinstance(_t, ast.Name) and _t.id == 'INTL_MAP':
                    _intl_map = ast.literal_eval(_node.value)
    assert _intl_map, 'daily_checklist.INTL_MAP 找不到（模組被重構？）'
    assert mb.CL_INTL_KEY_US10Y in _intl_map
    assert mb.CL_INTL_KEY_DXY in _intl_map
    # 順帶釘住 symbol，確認鏡像指到的是「殖利率 / 美元指數」而非別的東西
    assert _intl_map[mb.CL_INTL_KEY_US10Y] == '^TNX'
    assert _intl_map[mb.CL_INTL_KEY_DXY] == 'DX-Y.NYB'


def test_tw_key_mirror_matches_daily_checklist():
    """`macro_buckets.CL_TW_KEY_USDTWD` 必須 == `daily_checklist.TW_MAP` 的 key。

    與上一支同一個理由、同一個手法（AST 讀原始碼，不跨層 import）。
    2026-08-27 卡 A「美元指數 / 台幣」新增：台幣序列走
    `cl_data['tw']['新台幣匯率']`，key 名在 L3 改掉而 L0 沒跟 → 台幣那條線
    **無聲**變成「取不到」，而卡片會照畫（只剩 DXY 一條），看起來完全正常。
    """
    _tree = ast.parse(_DAILY_CHECKLIST_PATH.read_text(encoding='utf-8'))
    _tw_map = None
    for _node in ast.walk(_tree):
        if isinstance(_node, ast.Assign):
            for _t in _node.targets:
                if isinstance(_t, ast.Name) and _t.id == 'TW_MAP':
                    _tw_map = ast.literal_eval(_node.value)
    assert _tw_map, 'daily_checklist.TW_MAP 找不到（模組被重構？）'
    assert mb.CL_TW_KEY_USDTWD in _tw_map
    assert _tw_map[mb.CL_TW_KEY_USDTWD] == 'TWD=X'


def test_thresholds_and_valid_range_are_coherent():
    """§4.1 量綱自洽：門檻必須落在合理範圍內，否則兩者不是同一個刻度。

    這條就是「接上去變成 100 倍誤差」的攔截點 —— 若哪天有人把 DXY 門檻改成
    小數（1.05）或把範圍改成 [0,1]，此處會立刻 fail。
    """
    for _key in ('us10y', 'dxy'):
        _s = mb.SPECS_BY_KEY[_key]
        assert _s.valid_min <= _s.yellow <= _s.valid_max, _key
        assert _s.valid_min <= _s.red <= _s.valid_max, _key
        assert _s.yellow < _s.red, f'{_key} high_bad：黃線必須低於紅線'


# ════════════════════════════════════════════════════════════════
# 修正二 A. `20–20%` 不得再出現（行為斷言）
# ════════════════════════════════════════════════════════════════
def _ms(health, regime='neutral', defense=False, exposure_limit_pct=None):
    return {'is_loaded': True, 'regime': regime, 'health': health,
            'defense': defense, 'exposure_limit_pct': exposure_limit_pct}


class TestNoDegenerateRangeString:

    def test_drivers_last_line_collapses_when_lo_eq_hi(self):
        """實機文案：「最終 = min(姿態 70%, 天花板 20%) → 20–20%」。

        health=75 → 姿態帶 50–70%；cap=20 → final_lo=final_hi=20
        → 最後一行必須印「→ 20%」而非「→ 20–20%」。
        """
        d = build_allocation_decision(_ms(75), caps=[Cap('三環第一環', 20, '')])
        assert (d.final_lo, d.final_hi) == (20, 20)
        _last = d.drivers[-1]
        assert _last.startswith('最終 = min('), _last
        assert '20%' in _last
        assert f'20{EN_DASH}20' not in _last, f'怪字串復活：{_last}'

    def test_no_driver_line_contains_degenerate_range(self):
        """整份 drivers（🎚️ 油門明細印全部）都不得出現 `N–N%`。"""
        d = build_allocation_decision(
            _ms(75), caps=[Cap('三環第一環', 20, 'VIX 過高'),
                           Cap('VIX 否決權', 30, 'VIX 25')])
        for _line in d.drivers:
            for _p in range(0, 101):
                assert f'{_p}{EN_DASH}{_p}%' not in _line, f'{_line}'

    def test_normal_range_still_shows_both_ends(self):
        """收斂只在 lo == hi 時發生；正常區間仍要印完整兩端。

        ⚠️ 2026-08-19 期望值自 `50–70%` 改為 `80–100%` —— **本測試的意圖沒變，
        是 tier 邊界動了**：`THROTTLE_HEALTH_A` 自 80 改為 65（總經 health 的
        20 年實測值域是 [21.6, 78.1]，舊切點 80 落在值域外，「積極」級從未觸發過；
        新值取 n=4,769 的 P90≈65.6）。於是 health=75 由「中性偏多」升為「積極」。

        本測試驗的是「非退化區間必須印完整兩端」，與 tier 無關；期望值跟著
        SSOT 走即可。刻意**不改 fixture 的 75**去閃避 —— 改 fixture 會讓這次
        行為變更在測試裡消失無蹤。
        """
        d = build_allocation_decision(_ms(75))
        assert d.range_text == f'80{EN_DASH}100%'
        assert f'80{EN_DASH}100%' in d.drivers[-1]

    def test_range_text_and_drivers_agree(self):
        """SSOT 內部自我一致：drivers 末行的區間字串 == range_text。"""
        for _h, _caps in ((75, ()), (75, (Cap('c', 20),)), (43, (Cap('c', 20),)),
                          (20, ()), (55, (Cap('c', 60),))):
            d = build_allocation_decision(_ms(_h), caps=list(_caps))
            assert d.range_text in d.drivers[-1], (
                f'health={_h} caps={_caps}: range_text={d.range_text!r} '
                f'不在 drivers[-1]={d.drivers[-1]!r}'
            )

    @pytest.mark.parametrize('lo,hi,expected', [
        (30, 50, f'30{EN_DASH}50%'),
        (20, 20, '20%'),
        (0, 0, '0%'),
        (0, 20, f'0{EN_DASH}20%'),
        (None, 50, '--'),
        (30, None, '--'),
        (None, None, '--'),
    ])
    def test_fmt_range_unit(self, lo, hi, expected):
        assert _fmt_range(lo, hi) == expected

    def test_unloaded_returns_placeholder_not_zero(self):
        """§1：未評估回 '--'，不得回填 0% / 80% 之類假預設。"""
        d = build_allocation_decision({'is_loaded': False})
        assert d.range_text == '--'
        assert d.final_lo is None and d.final_hi is None


# ════════════════════════════════════════════════════════════════
# 修正二 B. AST 守衛：「用 f-string 直接把 lo/hi 拼成區間」不得再出現
# ════════════════════════════════════════════════════════════════
def _joinedstr_nodes_outside(func_name: str, tree: ast.AST) -> list[ast.JoinedStr]:
    """回傳「不屬於 func_name 函式」的所有 f-string 節點。"""
    _inside: set[int] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, ast.FunctionDef) and _n.name == func_name:
            for _sub in ast.walk(_n):
                _inside.add(id(_sub))
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, ast.JoinedStr) and id(_n) not in _inside]


def test_no_adhoc_range_fstring_in_allocation_decision():
    """`shared/allocation_decision.py` 內不得再出現 `f'...{a}–{b}...'` 這種
    「兩個內插值被一個 en dash 夾住」的區間拼字串 —— 唯一例外是 `_fmt_range`。

    這正是 v19.170 修了 UI 端卻漏掉 SSOT 模組自己的那類漏網之魚；
    純看行為測不出來（新加一處 raw 拼接、剛好 lo != hi 就不會 fail），
    所以用 AST 從結構上擋。
    """
    _tree = ast.parse(_ALLOC_SRC_PATH.read_text(encoding='utf-8'))
    _bad: list[str] = []
    for _js in _joinedstr_nodes_outside('_fmt_range', _tree):
        _vals = _js.values
        for _i, _part in enumerate(_vals):
            if not (isinstance(_part, ast.Constant)
                    and isinstance(_part.value, str)
                    and EN_DASH in _part.value):
                continue
            _prev_is_interp = _i > 0 and isinstance(_vals[_i - 1], ast.FormattedValue)
            _next_is_interp = (_i + 1 < len(_vals)
                               and isinstance(_vals[_i + 1], ast.FormattedValue))
            if _prev_is_interp and _next_is_interp:
                _bad.append(f'line {_js.lineno}: 內插值被「{EN_DASH}」夾住')
    assert not _bad, (
        '偵測到繞過 _fmt_range 的區間拼字串（會再生出「20–20%」）：\n'
        + '\n'.join(_bad)
    )


def test_fmt_range_is_the_only_range_formatter():
    """`_fmt_range` 必須存在，且 `range_text` 確實委派給它（非各自實作）。"""
    _src = _ALLOC_SRC_PATH.read_text(encoding='utf-8')
    _tree = ast.parse(_src)
    _fns = {_n.name for _n in ast.walk(_tree) if isinstance(_n, ast.FunctionDef)}
    assert '_fmt_range' in _fns
    _range_text = next(_n for _n in ast.walk(_tree)
                       if isinstance(_n, ast.FunctionDef) and _n.name == 'range_text')
    _calls = {_c.func.id for _c in ast.walk(_range_text)
              if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)}
    assert '_fmt_range' in _calls, 'range_text 應委派 _fmt_range，不可自行拼字串'
