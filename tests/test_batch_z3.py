"""批 Z3：第七輪分類判定可自主的四列（程式真相 origin/main `fd989ae`）。

- Y2-n4（L2）`macro_helpers._safe_float`：原只擋 NaN，±inf（含字串 'inf'／'-Infinity'、numpy inf）
  照樣過關 → `classify_long_term_regime`／`calc_traffic_light` 拿 ±inf 判位階、判燈
  （分類組實跑：CPI 給 inf 判「🟡 過熱/震盪期」、給 None 判「🔵 復甦期」）。
  改為非有限一律 None ⇒ 走既有缺值路徑；給 ±inf 的輸出 ＝ 給 None 的輸出。
- V2-n1（併 V2-n10，L0）`shared.macro_compute.evaluate_market_status_v4_final`：原 `current_price or 1.0`、
  `ma_240 or current_price` 把缺值捏成「價 1.0、年線＝價」⇒ (None,None,None)／(0,0,0) 回乖離 0.0、
  Is_Bull True、「🟢 強勢多頭」；非數字價格（例 'N/A'）拋 TypeError。改為價或年線不是有限正實數 ⇒
  依賴價格／年線的鍵一律 None、不拋；Is_Foreign_Hedging 照舊（`futures_net or 0` 另登記，本批不動）。
  唯一消費端 v1 `section_warroom` 只在價與年線為有限正數時才讀 —— 各種缺值形狀的渲染修前修後逐字相同。
- V1-n2（L5 v1）`section_mid`：VIX 為負（實跑 −5）印「✅ 市場平靜」「平靜期 🟢」「A VIX=-5.0<20 ✅」、
  否決權收到 −5。總管決定 VIX ≤ 0（定義上不可能）視同非有限值 —— 在本檔取 VIX 的單一入口處理，
  全部走 #781 既有缺值路徑（KPI「待取得」、§八 否決權那句、三環「A VIX未知」、apply_vix_veto(None)）。

只擋資料、不加新字句、不動門檻、不動版面；有限輸入與修前逐位相同（下方對拍修前副本）。
每段都有「拔掉修復即轉紅」的斷言（修前副本在同一組輸入上必須給出不同答案）。
"""
from __future__ import annotations

import math
import random
import struct
import types
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from shared import macro_compute as MC
from src.compute.macro import macro_helpers as MH
from tests.test_m2n2_no_zero_fill import _FakeST, _apply, _load, _mod, _source

_HUGE = 10 ** 400   # float() → OverflowError（不是 inf）


def _hexbits(v):
    """逐位比對：float（含 numpy 浮點）取 `.hex()`（-0.0 的符號位也比），其餘比值；一律帶型別。"""
    if isinstance(v, float):
        return type(v), v.hex()
    if isinstance(v, np.floating):
        return type(v), float(v).hex()
    return type(v), v


# ══════════════════════════════════════════════════════════════════════════
# Y2-n4：macro_helpers._safe_float 擋 ±inf
# ══════════════════════════════════════════════════════════════════════════
def _safe_float_pre(x):
    """修前 `_safe_float`（`fd989ae` 逐字，只擋 NaN）—— 對拍有限值、自證修前放行 ±inf 用。"""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError, OverflowError):
        return None
    if f != f:  # NaN guard
        return None
    return f


_INF_LIKE = [
    pytest.param(math.inf, id='+inf'), pytest.param(-math.inf, id='-inf'),
    pytest.param('inf', id='str-inf'), pytest.param('-inf', id='str--inf'),
    pytest.param('Infinity', id='str-Infinity'), pytest.param('-Infinity', id='str--Infinity'),
    pytest.param(' +inf ', id='str-padded-inf'),
    pytest.param(np.inf, id='np.inf'), pytest.param(-np.inf, id='-np.inf'),
    pytest.param(np.float32('inf'), id='np.float32-inf'),
    pytest.param(Decimal('-Infinity'), id='Decimal--Infinity'),
]
_MISSING_ALREADY = [   # 修前就回 None 的形狀：照舊
    pytest.param(None, id='None'), pytest.param(math.nan, id='nan'), pytest.param('nan', id='str-nan'),
    pytest.param(np.float64('nan'), id='np.nan'),
    pytest.param(_HUGE, id='10**400'), pytest.param(-_HUGE, id='-10**400'),
    pytest.param('x', id='str-x'), pytest.param('', id='str-empty'), pytest.param([], id='list'),
]
_FINITE = [
    pytest.param(v, id=repr(v)) for v in (
        0.0, -0.0, 1e300, -1e300, 5e-324, -5e-324, 1.7976931348623157e308, -1.7976931348623157e308,
        12.5, -3.25, 0, 7, -7, 10 ** 300, -(10 ** 300), True, False,
        '3', ' 2.5 ', '-0.0', '1e300', '-1e-300',
        np.float64(1.5), np.float64(-0.0), np.float32(0.1), np.int64(7), np.int32(-3),
        Decimal('0.1'), Fraction(1, 3),
    )
]


class TestSafeFloatNonFinite:
    @pytest.mark.parametrize('bad', _INF_LIKE)
    def test_inf_is_none(self, bad):
        assert MH._safe_float(bad) is None

    @pytest.mark.parametrize('bad', _INF_LIKE)
    def test_pre_fix_let_inf_through(self, bad):
        # 前提自證：修前這些值會以 ±inf 回傳（＝本列 bug）
        assert math.isinf(_safe_float_pre(bad))

    @pytest.mark.parametrize('bad', _MISSING_ALREADY)
    def test_missing_still_none(self, bad):
        assert MH._safe_float(bad) is None and _safe_float_pre(bad) is None

    @pytest.mark.parametrize('ok', _FINITE)
    def test_finite_bitwise_unchanged(self, ok):
        new, pre = MH._safe_float(ok), _safe_float_pre(ok)
        assert pre is not None and math.isfinite(pre)
        assert _hexbits(new) == _hexbits(pre)          # 型別 float、位元相同（含 -0.0）

    def test_random_finite_doubles_bitwise_unchanged(self):
        rng = random.Random(20261005)
        n = 0
        while n < 5000:
            f = struct.unpack('<d', rng.getrandbits(64).to_bytes(8, 'little'))[0]
            if not math.isfinite(f):
                continue
            n += 1
            assert MH._safe_float(f).hex() == _safe_float_pre(f).hex() == f.hex()


# ── 呼叫點：給 ±inf 的輸出 ＝ 給 None 的輸出 ─────────────────────────────────────
_INF_VALUES = [
    pytest.param(math.inf, id='+inf'), pytest.param(-math.inf, id='-inf'),
    pytest.param('inf', id='str-inf'), pytest.param('-Infinity', id='str--Infinity'),
    pytest.param(np.inf, id='np.inf'), pytest.param(np.float64('-inf'), id='np.-inf'),
]


def _tl(score=3.0, jq=55.0, fnet=12.5, fut=1000.0, leek=10.0):
    """calc_traffic_light 五個 `_safe_float` 呼叫點（大盤評分／旌旗／外資淨額／外資期貨／韭菜）。"""
    mkt = {'score': score, 'regime': 'bull', 'max_score': 4.0}
    cl = {'inst': {'外資': {'net': fnet}}, 'adl': pd.DataFrame({'ad_ratio': [50.0]})}
    li = pd.DataFrame({'外資大小': [fut], '韭菜指數': [leek]})
    return MH.calc_traffic_light(mkt, {'avg': jq}, cl, li)


_TL_SLOTS = ('score', 'jq', 'fnet', 'fut', 'leek')
_LT_BASE = dict(cpi_yoy=2.5, fed_rate=5.0, fed_prev_rate=5.25, ndc_score=30, pmi=53.0)


class TestCallSitesInfEqualsNone:
    @pytest.mark.parametrize('slot', _TL_SLOTS)
    @pytest.mark.parametrize('bad', _INF_VALUES)
    def test_calc_traffic_light(self, slot, bad):
        assert _tl(**{slot: bad}) == _tl(**{slot: None})

    @pytest.mark.parametrize('slot', _TL_SLOTS)
    @pytest.mark.parametrize('bad', [math.inf, -math.inf])
    def test_calc_traffic_light_pre_fix_differs(self, slot, bad, monkeypatch):
        # 拔掉修復（還原只擋 NaN）→ 上一條轉紅：每個呼叫點、正負兩向都真的被 inf 影響
        monkeypatch.setattr(MH, '_safe_float', _safe_float_pre)
        assert _tl(**{slot: bad}) != _tl(**{slot: None})

    @pytest.mark.parametrize('slot', list(_LT_BASE))
    @pytest.mark.parametrize('bad', _INF_VALUES)
    def test_classify_long_term_regime(self, slot, bad):
        a = MH.classify_long_term_regime(**{**_LT_BASE, slot: bad})
        b = MH.classify_long_term_regime(**{**_LT_BASE, slot: None})
        assert a == b

    @pytest.mark.parametrize('slot', list(_LT_BASE))
    @pytest.mark.parametrize('bad', [math.inf, -math.inf])
    def test_classify_long_term_regime_pre_fix_differs(self, slot, bad, monkeypatch):
        monkeypatch.setattr(MH, '_safe_float', _safe_float_pre)
        a = MH.classify_long_term_regime(**{**_LT_BASE, slot: bad})
        b = MH.classify_long_term_regime(**{**_LT_BASE, slot: None})
        assert a != b

    def test_classifier_group_repro(self, monkeypatch):
        # 分類組實跑重現：CPI 給 inf 判「🟡 過熱/震盪期」、給 None 判「🔵 復甦期」
        kw = dict(fed_rate=5.0, fed_prev_rate=5.0, ndc_score=25, pmi=51.0)
        assert MH.classify_long_term_regime(cpi_yoy=None, **kw)['regime'] == '🔵 復甦期'
        assert MH.classify_long_term_regime(cpi_yoy=math.inf, **kw)['regime'] == '🔵 復甦期'
        monkeypatch.setattr(MH, '_safe_float', _safe_float_pre)
        assert MH.classify_long_term_regime(cpi_yoy=math.inf, **kw)['regime'] == '🟡 過熱/震盪期'

    @pytest.mark.parametrize('slot', _TL_SLOTS)
    def test_calc_traffic_light_finite_unchanged(self, slot, monkeypatch):
        # 有限值：修前／修後同一份輸出（-0.0、極大值也一樣）
        for v in (0.0, -0.0, 7.5, -12.25, 1e300):
            new = _tl(**{slot: v})
            monkeypatch.setattr(MH, '_safe_float', _safe_float_pre)
            pre = _tl(**{slot: v})
            monkeypatch.undo()
            assert new == pre and repr(new) == repr(pre), (slot, v)


# ══════════════════════════════════════════════════════════════════════════
# V2-n1（併 V2-n10）：shared.macro_compute.evaluate_market_status_v4_final 不捏價／年線
# ══════════════════════════════════════════════════════════════════════════
#: 修後 → 修前（反向替換，每組恰好一處）。還原後的函式本體 ＝ `fd989ae` 的引擎
#: （docstring 以外逐字；AST 已另以 git 版對過）—— 本檔不依賴 git 歷史，CI 淺 clone 亦可跑。
_V2N1_REVERT = (
    ("    futures_net_oi = futures_net_oi or 0\n"
     "    is_foreign_hedging = futures_net_oi < -30000\n"
     "\n"
     "    if not (_is_finite_positive(current_price) and _is_finite_positive(ma_240)):\n"
     "        return {\n"
     "            \"Signal\": None,\n"
     "            \"Action_Advice\": None,\n"
     "            \"Suggested_Holding\": None,\n"
     "            \"Bias_240\": None,\n"
     "            \"Is_Bull\": None,\n"
     "            \"Is_Overheated\": None,\n"
     "            \"Is_Foreign_Hedging\": is_foreign_hedging,\n"
     "        }\n"
     "\n"
     "    bias_240 = ((current_price - ma_240) / ma_240) * 100\n",
     "    current_price = current_price or 1.0\n"
     "    ma_240 = ma_240 or current_price\n"
     "    futures_net_oi = futures_net_oi or 0\n"
     "\n"
     "    bias_240 = ((current_price - ma_240) / ma_240) * 100\n"),
    ("    is_overheated = bias_240 > 20.0\n"
     "\n"
     "    if is_bull_market:\n",
     "    is_overheated = bias_240 > 20.0\n"
     "    is_foreign_hedging = futures_net_oi < -30000\n"
     "\n"
     "    if is_bull_market:\n"),
)


def _load_mc_pre():
    import importlib.util
    with open(MC.__file__, encoding='utf-8') as f:
        code = _apply(f.read(), _V2N1_REVERT)
    spec = importlib.util.spec_from_loader('_z3_macro_compute_pre', loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = MC.__file__
    exec(compile(code, MC.__file__, 'exec'), m.__dict__)
    return m


_V4_PRE = _load_mc_pre().evaluate_market_status_v4_final
_V4 = MC.evaluate_market_status_v4_final
_V4_KEYS = ['Signal', 'Action_Advice', 'Suggested_Holding', 'Bias_240', 'Is_Bull',
            'Is_Overheated', 'Is_Foreign_Hedging']
_PRICE_KEYS = _V4_KEYS[:-1]     # 依賴價格／年線的鍵（Is_Foreign_Hedging 只看外資期貨）

_NOT_FINITE_POSITIVE = [
    pytest.param(v, id=i) for v, i in (
        (None, 'None'), (0, '0'), (0.0, '0.0'), (-0.0, '-0.0'), (-1, '-1'), (-800.0, '-800.0'),
        (-5e-324, '-5e-324'), (math.nan, 'nan'), (math.inf, '+inf'), (-math.inf, '-inf'),
        (np.float64('nan'), 'np.nan'), (np.float64('inf'), 'np.inf'), (np.float64(-3.0), 'np.float64-neg'),
        (np.int64(0), 'np.int64-zero'), ('N/A', 'str-N/A'), ('', 'str-empty'), ('20000', 'str-20000'),
        ('inf', 'str-inf'), (True, 'True'), (False, 'False'), (np.bool_(True), 'np.True_'),
        (np.bool_(False), 'np.False_'), (_HUGE, '10**400'), (-_HUGE, '-10**400'), (pd.NA, 'pd.NA'),
        ([], 'list'), ({}, 'dict'), (complex(1, 0), 'complex'),
    )
]


def _outcome(fn, *args):
    """回傳值逐位（含鍵序）或例外型別＋訊息 —— 修前修後「同一個結果」含「同樣拋」。"""
    try:
        r = fn(*args)
    except Exception as e:  # noqa: BLE001
        return 'raise', type(e).__name__, str(e)
    return 'ok', tuple(r), tuple(_hexbits(v) for v in r.values())


class TestV4EngineNoFabrication:
    @pytest.mark.parametrize('fut', [None, 0, -30000, -30001, -40000, 5000])
    @pytest.mark.parametrize('side', ['price', 'ma', 'both'])
    @pytest.mark.parametrize('bad', _NOT_FINITE_POSITIVE)
    def test_price_dependent_keys_none_no_raise(self, bad, side, fut):
        price, ma = {'price': (bad, 16000.0), 'ma': (20000.0, bad), 'both': (bad, bad)}[side]
        out = _V4(price, ma, fut)
        assert list(out) == _V4_KEYS
        assert all(out[k] is None for k in _PRICE_KEYS), out
        # 不依賴價格的鍵照舊（含 `futures_net_oi or 0` —— 本批不動，另登記）
        assert out['Is_Foreign_Hedging'] is ((fut or 0) < -30000)

    @pytest.mark.parametrize('args', [(None, None, None), (0, 0, 0)])
    def test_reported_cases(self, args):
        pre = _V4_PRE(*args)
        assert (pre['Bias_240'], pre['Is_Bull'], pre['Signal']) == (0.0, True, '🟢 強勢多頭')  # 前提：修前捏值
        new = _V4(*args)
        assert (new['Bias_240'], new['Is_Bull'], new['Is_Overheated']) == (None, None, None)
        assert (new['Signal'], new['Action_Advice'], new['Suggested_Holding']) == (None, None, None)
        assert new['Is_Foreign_Hedging'] is False

    @pytest.mark.parametrize('price', ['N/A', '20000'])
    def test_non_numeric_price_no_longer_raises(self, price):
        with pytest.raises(TypeError):
            _V4_PRE(price, 16000.0, 0)                    # 前提：修前拋
        assert _V4(price, 16000.0, 0)['Bias_240'] is None

    @pytest.mark.parametrize('bad', [None, 0, -1.0])
    def test_price_side_only_not_fabricated(self, bad):
        # 只缺價（年線有值）／只缺年線（價有值）：修前各自捏 1.0／捏「年線＝價」
        assert _V4_PRE(bad, 16000.0, 0)['Bias_240'] is not None
        assert _V4_PRE(20000.0, bad, 0)['Bias_240'] is not None
        assert _V4(bad, 16000.0, 0)['Bias_240'] is None
        assert _V4(20000.0, bad, 0)['Bias_240'] is None

    def test_finite_positive_identical_to_pre_fix(self):
        pos = [1, 2, 99, 100, 101, 16000, 19000, 20000, 25000, 1e-300, 5e-324, 0.5, 1.0,
               15999.99, 16000.0, 16159.0, 18810.0, 19200.0, 22800.0, 22800.000000000004,
               1.7976931348623157e308, 10 ** 300, np.float64(20000.0), np.float32(19000.0),
               np.int64(18000), Fraction(39, 2), np.array(20000.0)]
        futs = [None, 0, -30000, -30001, -40000, 5000, np.int64(-40000), -30000.5]
        n = 0
        with np.errstate(all='ignore'):
            for p in pos:
                for m in pos:
                    for f in futs:
                        new, pre = _outcome(_V4, p, m, f), _outcome(_V4_PRE, p, m, f)
                        assert new == pre, (p, m, f, new, pre)
                        n += 1
        assert n == len(pos) ** 2 * len(futs)

    @pytest.mark.parametrize('p,want', [
        (20000.0, '🟢 強勢多頭'), (25000.0, '🟡 多頭過熱 / 震盪警戒'), (18000.0, '🔴 空頭防禦'),
        (18810.0, '🟢 強勢多頭'),                      # 19000×0.99 邊界（含等號）
        (22800.0, '🟢 強勢多頭'),                      # 乖離恰 20.0（不含等號）
        (22800.000000000004, '🟡 多頭過熱 / 震盪警戒'),  # 乖離 20.000000000000018
    ])
    def test_boundaries_unchanged(self, p, want):
        assert _V4(p, 19000.0, 0)['Signal'] == _V4_PRE(p, 19000.0, 0)['Signal'] == want


# ── 唯一消費端 v1 section_warroom：各種缺值形狀的渲染輸出修前修後相同 ────────────────
def _wr(bias, mp, engine, futures_net=0):
    import src.services.daily_checklist as DC
    import src.ui.tabs.macro.section_warroom as W
    mp.setattr(DC, 'evaluate_market_status_v4_final', engine)   # `from src.services import …` 即時轉發
    fake = _FakeST({'bias_info': bias, 'cl_data': {'margin': 2000.0}, 'futures_net': futures_net})
    mp.setattr(W, 'st', fake)
    W.render_section_warroom('bull', True, False)
    return [t for _k, t in fake.out]


_WR_SAME = [pytest.param(b, id=i) for b, i in (
    ({}, 'empty'), ({'is_estimated': False}, 'keys-missing'),
    ({'price': None, 'ma240': None}, 'none'), ({'price': math.nan, 'ma240': math.nan}, 'nan'),
    ({'price': math.inf, 'ma240': 1.0}, 'price-inf'), ({'price': 1.0, 'ma240': math.inf}, 'ma-inf'),
    ({'price': -math.inf, 'ma240': 16000.0}, 'price--inf'),
    ({'price': 0.0, 'ma240': 16000.0}, 'price-zero'), ({'price': 20000.0, 'ma240': 0.0}, 'ma-zero'),
    ({'price': 0, 'ma240': 0}, 'both-zero'), ({'price': -0.0, 'ma240': 16000.0}, 'price-negzero'),
    ({'price': -800.0, 'ma240': 16000.0}, 'price-negative'),
    ({'price': 20000.0, 'ma240': -5.0}, 'ma-negative'),
    ({'price': 20000.0}, 'ma-missing'), ({'ma240': 16000.0}, 'price-missing'),
    ({'price': True, 'ma240': True}, 'bool'), ({'price': 20000.0, 'ma240': False}, 'ma-false'),
    ({'bias_240': 25.0, 'price': None, 'ma240': 16000.0}, 'b240-with-price-none'),
    ({'bias_240': -25.0, 'price': 0.0, 'ma240': 0.0}, 'b240-with-zeros'),
    ({'bias_240': 3.0, 'price': 20000.0, 'ma240': None, 'is_estimated': True, 'data_days': 90},
     'estimated-ma-none'),
    # 有限正數（引擎照算、消費端照讀）
    ({'bias_240': 25.0, 'bias_20': 12.0, 'price': 20000.0, 'ma240': 16000.0, 'data_days': 300,
      'is_estimated': False}, 'full'),
    ({'price': 15000.0, 'ma240': 16000.0, 'bias_240': -6.3}, 'below-ma'),
    ({'price': 16000.0, 'ma240': 16000.0}, 'at-ma'), ({'price': 20000, 'ma240': 16000}, 'ints'),
    ({'price': np.float64(25000.0), 'ma240': np.float64(19000.0)}, 'numpy'),
    ({'price': 20000.0, 'ma240': 16000.0, 'is_estimated': True, 'data_days': 120}, 'estimated'),
)]


class TestWarroomConsumerUnchanged:
    @pytest.mark.parametrize('fut', [0, -40000])
    @pytest.mark.parametrize('bias', _WR_SAME)
    def test_render_identical_to_pre_fix_engine(self, bias, fut, monkeypatch):
        assert _wr(bias, monkeypatch, _V4, fut) == _wr(bias, monkeypatch, _V4_PRE, fut)

    @pytest.mark.parametrize('bias,exc', [
        pytest.param({'price': 'z', 'ma240': 'w'}, TypeError, id='non-numeric'),
        pytest.param({'price': 'N/A', 'ma240': 16000.0}, TypeError, id='price-str'),
        pytest.param({'price': 20000.0, 'ma240': 'N/A'}, TypeError, id='ma-str'),
        pytest.param({'price': '20000', 'ma240': '16000'}, TypeError, id='numeric-str'),
        pytest.param({'price': 10 ** 400, 'ma240': 16000.0}, OverflowError, id='huge-int'),
    ])
    def test_pre_fix_raised_now_renders_empty_path(self, bias, exc, monkeypatch):
        with pytest.raises(exc):
            _wr(bias, monkeypatch, _V4_PRE)               # 前提：修前整個作戰室炸掉
        assert _wr(bias, monkeypatch, _V4) == _wr({}, monkeypatch, _V4)


# ══════════════════════════════════════════════════════════════════════════
# V1-n2（L5 v1）：section_mid 的 VIX ≤ 0 視同非有限值
# ══════════════════════════════════════════════════════════════════════════
_MID_BASE = {"ism_pmi": {"value": 52.0}, "us_core_cpi": {"yoy": 3.0},
             "tw_export": {"yoy": 5.0, "date": "2026-08"}, "ndc_signal": {"score": 27}}
_LOADING = "VIX 數據載入中，VIX 否決權暫無法判斷"     # 既有句（#781 缺值路徑）

#: 修後 → 修前（反向替換，只動程式行；註解不影響行為）。還原體在 VIX > 0／真缺值上
#: 與 `fd989ae` 的 section_mid 渲染逐字相同（已另以 git 原始檔實跑對過）。
_MID_REVERT = (
    ("    if _vcur8_v is not None and _vcur8_v <= 0:\n"
     "        _vcur8_v = None\n", ""),
)


class _FakeSTFig(_FakeST):
    """多記一筆 VIX 走勢圖標題（「✅ 市場平靜」等燈義只出現在圖標題裡）。"""

    def plotly_chart(self, fig, *a, **k):
        self.out.append(("plotly_chart", str(fig.layout.title.text)))


def _run_mid(mod, vix_node, mp, drop_key=False):
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    info = dict(_MID_BASE)
    if not drop_key:
        info["vix"] = vix_node
    fake = _FakeSTFig({"macro_info": info, "bias_info": {"bias_240": 5.0}})
    calls: list = []
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: calls.append(a))
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None))
    mp.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
    mod.render_section_mid(False, {}, {}, {})
    return [t for _k, t in fake.out], calls


def _node(v):
    """有走勢資料的 VIX 節點（有 dates 才走「畫圖」那枝 —— 才看得到圖標題的「✅ 市場平靜」）。"""
    return {"current": v, "dates": ["2026-09-30", "2026-10-01"], "values": [18.0, v], "ma20": 17.5}


@pytest.fixture(scope="module")
def mid_pre():
    return _load("mid", _apply(_source("mid"), _MID_REVERT), "z3_pre")


_NONPOS = [pytest.param(v, id=repr(v)) for v in (0, 0.0, -0.0, -5, -5.0, -1e-9, -1e300, np.float64(-3.0))]
_TRUE_MISSING = [
    pytest.param({"current": None}, False, id="none"),
    pytest.param({"dates": []}, False, id="missing-current"),
    pytest.param(None, True, id="missing-vix-key"),
    pytest.param("x", False, id="non-dict-str"),
    pytest.param(18.5, False, id="non-dict-float"),
]


class TestV1n2NonPositiveVix:
    @pytest.mark.parametrize("v", _NONPOS)
    def test_takes_existing_missing_path(self, v, monkeypatch):
        out, calls = _run_mid(_mod("mid"), _node(v), monkeypatch)
        joined = "\n".join(out)
        # 修前（實跑 −5）：「✅ 市場平靜」「平靜期 🟢」「A VIX=-5.0<20 ✅」、否決權收到 −5
        assert "市場平靜" not in joined and "平靜期" not in joined, joined[-1500:]
        assert "A VIX=" not in joined and "未觸發 VIX 否決權" not in joined
        assert "A VIX未知" in joined                                       # 三環徽章
        assert calls == [(None,)], calls                                     # apply_vix_veto(None)
        assert any("VIX 恐慌指數" in t and "待取得" in t for t in out)        # KPI 卡「待取得」
        assert not any(t.startswith("VIX 恐慌指數 ") for t in out)           # 不畫走勢圖
        assert any("VIX待取得" in t or "VIX／" in t for t in out if "總經基本面否決檢查" in t)

    @pytest.mark.parametrize("v", _NONPOS)
    def test_output_equals_missing_current(self, v, monkeypatch):
        # 全部走既有缺值路徑：整份輸出 ＝ current 為 None 時（同一個節點形狀）
        assert (_run_mid(_mod("mid"), _node(v), monkeypatch)
                == _run_mid(_mod("mid"), _node(None), monkeypatch))

    @pytest.mark.parametrize("v", _NONPOS)
    def test_pre_fix_printed_fake_calm(self, v, mid_pre, monkeypatch):
        # 前提自證（拔掉修復即轉紅）：還原體在同一輸入印假的「平靜期」並把原值送進否決權
        out, calls = _run_mid(mid_pre, _node(v), monkeypatch)
        joined = "\n".join(out)
        assert "（平靜期）" in joined and "市場平靜" in joined and "A VIX=" in joined
        assert calls == [(float(v),)]

    @pytest.mark.parametrize("v", [1e-9, 5e-324, 0.01, 0.5, 18, 19.96, 20, 25.0, 30, 35.5, 100, 150.0])
    def test_positive_vix_identical_to_pre_fix(self, v, mid_pre, monkeypatch):
        for node in (_node(v), {"current": v}):
            assert _run_mid(_mod("mid"), node, monkeypatch) == _run_mid(mid_pre, node, monkeypatch)

    @pytest.mark.parametrize("node,drop", _TRUE_MISSING)
    def test_true_missing_identical_to_pre_fix(self, node, drop, mid_pre, monkeypatch):
        assert (_run_mid(_mod("mid"), node, monkeypatch, drop)
                == _run_mid(mid_pre, node, monkeypatch, drop))
