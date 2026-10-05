"""批 Z3：第七輪分類判定可自主的四列（程式真相 origin/main `fd989ae`）。

- Y2-n4（L2）`macro_helpers._safe_float`：原只擋 NaN，±inf（含字串 'inf'／'-Infinity'、numpy inf）
  照樣過關 → `classify_long_term_regime`／`calc_traffic_light` 拿 ±inf 判位階、判燈
  （分類組實跑：CPI 給 inf 判「🟡 過熱/震盪期」、給 None 判「🔵 復甦期」）。
  改為非有限一律 None ⇒ 走既有缺值路徑；給 ±inf 的輸出 ＝ 給 None 的輸出。

只擋資料、不加新字句、不動門檻、不動版面；有限輸入與修前逐位相同（下方對拍修前副本）。
每段都有「拔掉修復即轉紅」的斷言（修前副本在同一組輸入上必須給出不同答案）。
"""
from __future__ import annotations

import math
import random
import struct
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from src.compute.macro import macro_helpers as MH

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
