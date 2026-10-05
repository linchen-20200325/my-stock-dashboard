"""批 Z3：第七輪分類判定可自主的四列（程式真相 origin/main `fd989ae`）。

- Y2-n4（L2）`macro_helpers._safe_float`：原只擋 NaN，±inf（含字串 'inf'／'-Infinity'、numpy inf）
  照樣過關 → `classify_long_term_regime`／`calc_traffic_light` 拿 ±inf 判位階、判燈
  （分類組實跑：CPI 給 inf 判「🟡 過熱/震盪期」、給 None 判「🔵 復甦期」）。
  改為非有限一律 None ⇒ 走既有缺值路徑；給 ±inf 的輸出 ＝ 給 None 的輸出。
- V2-n1（併 V2-n10，L0）`shared.macro_compute.evaluate_market_status_v4_final`：原 `current_price or 1.0`、
  `ma_240 or current_price` 把缺值捏成「價 1.0、年線＝價」⇒ (None,None,None)／(0,0,0) 回乖離 0.0、
  Is_Bull True、「🟢 強勢多頭」；非數字價格（例 'N/A'）拋 TypeError。改為價或年線不是有限正實數 ⇒
  依賴價格／年線的鍵一律 None、不拋；Is_Foreign_Hedging 照舊（`futures_net or 0` 另登記，本批不動）。
  唯一消費端 v1 `section_warroom`：讀 `Bias_240` 前的守衛用 `_finite_yoy`（只排除 Python bool，numpy bool
  會過），引擎則把 numpy bool 判無效 —— 📌 驗收阻擋 1 更正：原句「只在價與年線為有限正數時才讀」不實
  （單邊 np.True_ 會讀到 None 而崩），warroom 已另判 `Bias_240 is not None`。對拍範圍：價／年線不是
  numpy bool 的缺值與正常形狀，渲染與修前相同；單邊 numpy bool 改走價／年線缺值路徑（有意識的變更，
  fd989ae 是把 np.True_ 當 1 印假乖離）。
- V1-n2（L5 v1）`section_mid`：VIX 為負（實跑 −5）印「✅ 市場平靜」「平靜期 🟢」「A VIX=-5.0<20 ✅」、
  否決權收到 −5。總管決定 VIX ≤ 0（定義上不可能）視同非有限值 —— 在 §八 自己取 VIX 的 `_vcur8_v` 處理，
  由它取值的 KPI「待取得」、基本面否決檢查「VIX待取得」、§八 否決權那句、三環「A VIX未知」、
  apply_vix_veto(None) 走 #781 既有缺值路徑。📌 範圍更正（驗收）：原句「本檔取 VIX 的單一入口／全部走」
  過寬 —— 本頁另有 §三 `read_v4_macro_veto()` 與頂部總經警示看板（L1，正式載入才出現）自行讀 VIX；
  前者在 §八 VIX 無效時已不取用（驗收阻擋 2，下方以真函式驗），後者屬 L1、總管另登記為已知限制。
- V1-n5（同檔）：VIX「有值但無效」（非有限或 ≤ 0；含非數值）時，§八 那句原寫「VIX 數據載入中，VIX 否決權
  暫無法判斷」—— 值明明到了，「載入中」是假的。只在此時於子句界純刪「VIX 數據載入中，」；
  真的沒值（None／缺鍵）原句一字不變。

只擋資料、不加新字句、不動門檻、不動版面；有限輸入與修前逐位相同（下方對拍修前副本）。
每段都有「拔掉修復即轉紅」的斷言（修前副本在同一組輸入上必須給出不同答案）。
"""
from __future__ import annotations

import math
import random
import struct
import types
import warnings
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from shared import macro_compute as MC
from src.config import VETO_V4_ENGINE_NAME
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
    # 📌 驗收阻擋 3-2：float() 溢位成 ±inf（不是 OverflowError）的形狀 —— 只比對 'inf' 字樣的擋法會漏
    pytest.param('1e400', id='str-1e400'), pytest.param('-1e400', id='str--1e400'),
    pytest.param('1e309', id='str-1e309'),
    pytest.param(Decimal('1e400'), id='Decimal-1e400'), pytest.param(Decimal('-1e400'), id='Decimal--1e400'),
    pytest.param(b'inf', id='bytes-inf'), pytest.param(b'-inf', id='bytes--inf'),
    pytest.param(b'1e400', id='bytes-1e400'), pytest.param(bytearray(b'inf'), id='bytearray-inf'),
    pytest.param(np.longdouble('1e400'), id='longdouble-1e400'),
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
    pytest.param('1e400', id='str-1e400'), pytest.param(Decimal('-1e400'), id='Decimal--1e400'),
    pytest.param(b'inf', id='bytes-inf'),
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
def _v4_fd989ae(current_price, ma_240, futures_net_oi):
    """修前引擎：`fd989ae` 的 `evaluate_market_status_v4_final` 函式本體，逐字凍結於本檔。

    📌 驗收阻擋 3-1 更正：原本由現行檔反向替換出「修前體」—— 修前修後共用的算式（`* 0.99`、
    `round(…, 2)`）一起被突變時兩邊同步改變，對拍抓不到。改為凍結副本（不讀 git 歷史、不由現行檔
    反推；CI 淺 clone 亦可跑），並由下方寫死的 golden 表雙重釘住。
    """
    current_price = current_price or 1.0
    ma_240 = ma_240 or current_price
    futures_net_oi = futures_net_oi or 0

    bias_240 = ((current_price - ma_240) / ma_240) * 100
    is_bull_market = current_price >= (ma_240 * 0.99)
    is_overheated = bias_240 > 20.0
    is_foreign_hedging = futures_net_oi < -30000

    if is_bull_market:
        if is_overheated or is_foreign_hedging:
            signal = "🟡 多頭過熱 / 震盪警戒"
            action = "大盤乖離與外資避險過高。建議暫停積極型基金單筆申購，轉為定期定額，並拉高防禦型/平衡型基金權重。"
            hold_ratio = "50% - 70%"
        else:
            signal = "🟢 強勢多頭"
            action = "均線多頭排列且籌碼穩定。建議擴大核心部位，增加成長型股票基金曝險。"
            hold_ratio = "80% - 100%"
    else:
        signal = "🔴 空頭防禦"
        action = "跌破年線，趨勢偏空。維持既有定期定額，單筆操作宜觀望。"
        hold_ratio = "20% - 40%"

    return {
        "Signal": signal,
        "Action_Advice": action,
        "Suggested_Holding": hold_ratio,
        "Bias_240": round(bias_240, 2),
        "Is_Bull": is_bull_market,
        "Is_Overheated": is_overheated,
        "Is_Foreign_Hedging": is_foreign_hedging,
    }


_V4_PRE = _v4_fd989ae
_V4 = MC.evaluate_market_status_v4_final
_V4_KEYS = ['Signal', 'Action_Advice', 'Suggested_Holding', 'Bias_240', 'Is_Bull',
            'Is_Overheated', 'Is_Foreign_Hedging']
_PRICE_KEYS = _V4_KEYS[:-1]     # 依賴價格／年線的鍵（Is_Foreign_Hedging 只看外資期貨）

# ── golden：以 `fd989ae` 實算後寫死（驗收阻擋 3-1；不在測試裡讀 git、不由任何程式反推）──────────
_G_BULL, _G_HOT, _G_BEAR = '🟢 強勢多頭', '🟡 多頭過熱 / 震盪警戒', '🔴 空頭防禦'
_V4_GOLDEN_ACTION = {
    _G_BULL: '均線多頭排列且籌碼穩定。建議擴大核心部位，增加成長型股票基金曝險。',
    _G_HOT: '大盤乖離與外資避險過高。建議暫停積極型基金單筆申購，轉為定期定額，並拉高防禦型/平衡型基金權重。',
    _G_BEAR: '跌破年線，趨勢偏空。維持既有定期定額，單筆操作宜觀望。',
}
_V4_GOLDEN_HOLD = {_G_BULL: '80% - 100%', _G_HOT: '50% - 70%', _G_BEAR: '20% - 40%'}
#: (價, 年線, 外資期貨) → (Signal, Bias_240, Is_Bull, Is_Overheated, Is_Foreign_Hedging)
_V4_GOLDEN = [pytest.param(a, w, id=repr(a)) for a, w in (
    ((20000.0, 19000.0, 0), (_G_BULL, 5.26, True, False, False)),          # round 2 位（改 1 位 → 5.3）
    ((20000.0, 19000.0, -40000), (_G_HOT, 5.26, True, False, True)),       # 多頭 × 外資避險
    ((20000.0, 19000.0, -30000), (_G_BULL, 5.26, True, False, False)),     # 避險門檻（不含等號）
    ((20000.0, 19000.0, -30001), (_G_HOT, 5.26, True, False, True)),
    ((25000.0, 19000.0, 0), (_G_HOT, 31.58, True, True, False)),           # 多頭 × 過熱
    ((22800.0, 19000.0, 0), (_G_BULL, 20.0, True, False, False)),          # 乖離恰 20（不含等號）
    ((22800.000000000004, 19000.0, 0), (_G_HOT, 20.0, True, True, False)),  # 乖離 20.000000000000018
    ((21004.0, 17503.0, 0), (_G_HOT, 20.0, True, True, False)),
    ((18000.0, 19000.0, 0), (_G_BEAR, -5.26, False, False, False)),        # 空頭
    ((18000.0, 19000.0, -40000), (_G_BEAR, -5.26, False, False, True)),    # 空頭 × 避險（燈仍空頭）
    ((18700.0, 19000.0, 0), (_G_BEAR, -1.58, False, False, False)),        # 0.98 < 價/年線 < 0.99
    ((18809.99, 19000.0, 0), (_G_BEAR, -1.0, False, False, False)),        # 0.99 邊界下方
    ((18810.0, 19000.0, 0), (_G_BULL, -1.0, True, False, False)),          # 0.99 邊界（含等號）
    ((17150.0, 17320.0, 0), (_G_BULL, -0.98, True, False, False)),
    ((19001.0, 19000.0, 0), (_G_BULL, 0.01, True, False, False)),          # round 2 位（改 1 位 → 0.0）
    ((18990.0, 19000.0, 0), (_G_BULL, -0.05, True, False, False)),
    ((19950.0, 19000.0, 0), (_G_BULL, 5.0, True, False, False)),
    ((20000, 16000, None), (_G_HOT, 25.0, True, True, False)),              # int、期貨 None
    ((16000, 20000, 5000), (_G_BEAR, -20.0, False, False, False)),
    ((1.0, 0.5, 0), (_G_HOT, 100.0, True, True, False)),
    ((0.5, 1.0, 0), (_G_BEAR, -50.0, False, False, False)),
)]

_NOT_FINITE_POSITIVE = [
    pytest.param(v, id=i) for v, i in (
        (None, 'None'), (0, '0'), (0.0, '0.0'), (-0.0, '-0.0'), (-1, '-1'), (-800.0, '-800.0'),
        (-5e-324, '-5e-324'), (math.nan, 'nan'), (math.inf, '+inf'), (-math.inf, '-inf'),
        (np.float64('nan'), 'np.nan'), (np.float64('inf'), 'np.inf'), (np.float64(-3.0), 'np.float64-neg'),
        (np.int64(0), 'np.int64-zero'), ('N/A', 'str-N/A'), ('', 'str-empty'), ('20000', 'str-20000'),
        ('inf', 'str-inf'), (True, 'True'), (False, 'False'), (np.bool_(True), 'np.True_'),
        (np.bool_(False), 'np.False_'), (_HUGE, '10**400'), (-_HUGE, '-10**400'), (pd.NA, 'pd.NA'),
        ([], 'list'), ({}, 'dict'), (complex(1, 0), 'complex'),
        (np.complex128(20000), 'np.complex128'), (np.complex64(20000), 'np.complex64'),
        (np.complex128(20000 + 5j), 'np.complex128-imag'), (np.array(20000 + 0j), 'complex-0d-array'),
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
        with warnings.catch_warnings():
            warnings.simplefilter('error')        # 不得靠 math.isfinite 丟虛部（ComplexWarning）過關
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

    @pytest.mark.parametrize('args,want', _V4_GOLDEN)
    def test_golden_fd989ae(self, args, want):
        # 修後與凍結副本都必須等於寫死值（乖離逐位；任一共用算式被改都會轉紅）
        sig, bias, bull, hot, hedge = want
        for fn in (_V4, _V4_PRE):
            out = fn(*args)
            assert list(out) == _V4_KEYS
            assert (out['Signal'], out['Suggested_Holding'], out['Action_Advice']) == (
                sig, _V4_GOLDEN_HOLD[sig], _V4_GOLDEN_ACTION[sig]), fn
            assert _hexbits(out['Bias_240']) == _hexbits(bias), (fn, out['Bias_240'])
            assert (out['Is_Bull'], out['Is_Overheated'], out['Is_Foreign_Hedging']) == (bull, hot, hedge)
            assert type(out['Is_Bull']) is bool and type(out['Is_Overheated']) is bool

    def test_finite_positive_identical_to_frozen_fd989ae(self):
        pos = [1, 2, 99, 100, 101, 16000, 19000, 20000, 25000, 1e-300, 5e-324, 0.5, 1.0,
               15999.99, 16000.0, 16159.0, 18700.0, 18809.99, 18810.0, 18990.0, 19001.0, 19200.0,
               22800.0, 22800.000000000004, 1.7976931348623157e308, 10 ** 300, np.float64(20000.0),
               np.float32(19000.0), np.int64(18000), Fraction(39, 2), np.array(20000.0),
               Decimal('20000'), Decimal('19000')]
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

    # ── 驗收阻擋 3-6：Decimal 是有限正實數 → 行為須與 fd989ae 相同（含它本來就會拋的組合）────────
    def test_decimal_with_int_ma_same_as_fd989ae(self):
        out = _V4(Decimal('20000'), 19000, 0)
        assert type(out['Bias_240']) is Decimal and out['Bias_240'] == Decimal('5.26')
        assert (out['Signal'], out['Suggested_Holding'], out['Is_Bull'], out['Is_Overheated'],
                out['Is_Foreign_Hedging']) == (_G_BULL, '80% - 100%', True, False, False)
        assert _outcome(_V4, Decimal('20000'), 19000, 0) == _outcome(_V4_PRE, Decimal('20000'), 19000, 0)

    @pytest.mark.parametrize('args,msg', [
        ((Decimal('20000'), 19000.0, 0), "unsupported operand type(s) for -: 'decimal.Decimal' and 'float'"),
        ((20000.0, Decimal('19000'), 0), "unsupported operand type(s) for -: 'float' and 'decimal.Decimal'"),
        ((Decimal('20000'), Decimal('19000'), 0), "unsupported operand type(s) for *: 'decimal.Decimal' and 'float'"),
        ((20000, Decimal('19000'), 0), "unsupported operand type(s) for *: 'decimal.Decimal' and 'float'"),
    ])
    def test_decimal_raises_like_fd989ae(self, args, msg):
        # 有限正數 → 照原算式算（不得另把 Decimal 判無效回 None）；fd989ae 在這些組合就拋這個訊息
        for fn in (_V4, _V4_PRE):
            with pytest.raises(TypeError) as ei:
                fn(*args)
            assert str(ei.value) == msg

    # ── 驗收阻擋 3-7：非實數（複數）→ 不是有限正實數 → 回 None、不拋 ───────────────────────────
    def test_pre_fix_complex_raised(self):
        with pytest.raises(TypeError):
            _V4_PRE(np.complex128(20000), 19000.0, 0)       # 前提：修前在 round() 拋


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


# ── 驗收阻擋 1：單邊 numpy bool（`_finite_yoy` 放行、引擎判無效）不得讓作戰室崩潰 ───────────
_WR_NPBOOL = [pytest.param(b, m, id=i) for b, m, i in (
    ({'price': np.True_, 'ma240': 16000.0}, {'price': None, 'ma240': 16000.0}, 'price-np.True_'),
    ({'price': 20000.0, 'ma240': np.True_}, {'price': 20000.0, 'ma240': None}, 'ma-np.True_'),
    ({'price': np.False_, 'ma240': 16000.0}, {'price': None, 'ma240': 16000.0}, 'price-np.False_'),
    ({'price': 20000.0, 'ma240': np.False_}, {'price': 20000.0, 'ma240': None}, 'ma-np.False_'),
    ({'price': np.True_, 'ma240': np.True_}, {'price': None, 'ma240': None}, 'both-np.True_'),
    ({'bias_240': 3.0, 'price': np.True_, 'ma240': 16000.0, 'is_estimated': True, 'data_days': 90},
     {'bias_240': 3.0, 'price': None, 'ma240': 16000.0, 'is_estimated': True, 'data_days': 90},
     'estimated-price-np.True_'),
)]


class TestWarroomNumpyBool:
    @pytest.mark.parametrize('fut', [0, -40000])
    @pytest.mark.parametrize('bias,missing', _WR_NPBOOL)
    def test_takes_price_missing_path_no_crash(self, bias, missing, fut, monkeypatch):
        out = _wr(bias, monkeypatch, _V4, fut)                     # 不得拋 TypeError
        assert out == _wr(missing, monkeypatch, _V4, fut)          # ＝價／年線缺值的既有路徑
        assert not any('📐 年線位階參考' in t and '年線乖離 ' in t for t in out)

    def test_premise_gate_and_engine_disagree_on_numpy_bool(self):
        # 前提：消費端守衛（`_finite_yoy` > 0）放行 np.True_、引擎判無效回 None ——
        # 少了 `Bias_240 is not None` 就會在 `:+.1f` 拋 TypeError（驗收阻擋 1 的成因）
        from src.ui.tabs.macro.section_long import _finite_yoy
        assert _finite_yoy({'p': np.True_}, 'p') is np.True_ and bool(np.True_ > 0)
        assert _V4(np.True_, 16000.0, 0)['Bias_240'] is None
        assert _V4(20000.0, np.True_, 0)['Bias_240'] is None

    @pytest.mark.parametrize('bias', [{'price': np.True_, 'ma240': 16000.0},
                                      {'price': 20000.0, 'ma240': np.True_}])
    def test_pre_fix_printed_fake_bias(self, bias, monkeypatch):
        # fd989ae 不崩，而是把 np.True_ 當 1 印假乖離 —— 改走缺值路徑是有意識的變更
        out = '\n'.join(_wr(bias, monkeypatch, _V4_PRE))
        assert '📐 年線位階參考：年線乖離 ' in out


# ══════════════════════════════════════════════════════════════════════════
# V1-n2（L5 v1）：section_mid 的 VIX ≤ 0 視同非有限值
# ══════════════════════════════════════════════════════════════════════════
_MID_BASE = {"ism_pmi": {"value": 52.0}, "us_core_cpi": {"yoy": 3.0},
             "tw_export": {"yoy": 5.0, "date": "2026-08"}, "ndc_signal": {"score": 27}}
_LOADING = "VIX 數據載入中，VIX 否決權暫無法判斷"     # 既有句（#781 缺值路徑；真的沒值）
_INVALID = "VIX 否決權暫無法判斷"                     # V1-n5：有值但無效（子句界純刪後）

#: 修後 → 修前（反向替換，只動程式行；註解不影響行為）。範圍：本檔 harness（`_FakeST`、
#: `_load_heavy=False` 不畫頂部警示看板）下，還原體與 `fd989ae` 的 section_mid 渲染逐字相同
#: （已另以 git 原始檔實跑對過；不是全頁、全輸入的等價證明）。
_MID_REVERT = (
    ("    if _vcur8_v is not None and _vcur8_v <= 0:\n"
     "        _vcur8_v = None\n", ""),
    ("    if _vcur8_v is None:\n"
     "        _v4_light = None\n", ""),                       # 驗收阻擋 2 的揭露框閘門
    ("            st.info('VIX 否決權暫無法判斷' if _vix_bad8\n"
     "                    else 'VIX 數據載入中，VIX 否決權暫無法判斷')\n",
     "            st.info('VIX 數據載入中，VIX 否決權暫無法判斷')\n"),
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
        # 範圍（驗收更正）：在本 harness（`_load_heavy=False` 不畫頂部警示看板、`read_v4_macro_veto`
        # stub 為 None）內，輸出 ＝ current 為 None 時（同一個節點形狀），唯一差別是 V1-n5 那一句
        # （≤ 0 屬「有值但無效」→ 刪去「VIX 數據載入中，」）。揭露框用真函式的情形見 TestV1CrossDisclosure。
        out, calls = _run_mid(_mod("mid"), _node(v), monkeypatch)
        base, base_calls = _run_mid(_mod("mid"), _node(None), monkeypatch)
        assert out == [_INVALID if t == _LOADING else t for t in base]
        assert calls == base_calls == [(None,)]

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


# ══════════════════════════════════════════════════════════════════════════
# V1-n5（同檔）：VIX「有值但無效」時，§八 那句於子句界刪「VIX 數據載入中，」
# ══════════════════════════════════════════════════════════════════════════
_HAS_VALUE_INVALID = [pytest.param(v, id=repr(v)) for v in (
    math.nan, math.inf, -math.inf, np.float64("nan"), 0, -5, -0.0, "18.5", "x", "", True, False)]
#: 修前（還原體）在這些值上說「數據載入中」（≤ 0 修前印假平靜期，前提另見 V1-n2 段）
_PRE_SAID_LOADING = [pytest.param(v, id=repr(v)) for v in (math.nan, math.inf, -math.inf, "18.5", True)]


class TestV1n5InvalidValueSentence:
    @pytest.mark.parametrize("v", _HAS_VALUE_INVALID)
    def test_has_value_invalid_drops_loading_clause(self, v, monkeypatch):
        out, calls = _run_mid(_mod("mid"), _node(v), monkeypatch)
        assert _INVALID in out and _LOADING not in out, out
        assert calls == [(None,)]
        # 本 harness 範圍內（同上）：與「真的沒值」只差這一句，其餘逐字相同
        base, _ = _run_mid(_mod("mid"), _node(None), monkeypatch)
        assert sum(t == _LOADING for t in base) == 1
        assert out == [_INVALID if t == _LOADING else t for t in base]

    @pytest.mark.parametrize("node,drop", _TRUE_MISSING)
    def test_true_missing_keeps_original_sentence(self, node, drop, monkeypatch):
        out, calls = _run_mid(_mod("mid"), node, monkeypatch, drop)
        assert _LOADING in out and _INVALID not in out, out
        assert calls == [(None,)]

    @pytest.mark.parametrize("v", _PRE_SAID_LOADING)
    def test_pre_fix_said_loading(self, v, mid_pre, monkeypatch):
        # 前提自證：修前有值但無效時照樣說「VIX 數據載入中，…」
        out, _ = _run_mid(mid_pre, _node(v), monkeypatch)
        assert _LOADING in out and _INVALID not in out

    def test_k1_pure_clause_deletion(self):
        # K1：新句＝既有句在子句界「，」刪掉前一子句，不新增任何字
        assert _LOADING.split("，", 1) == ["VIX 數據載入中", _INVALID]
        src = _source("mid")
        assert src.count(f"'{_INVALID}'") == 1 and src.count(f"'{_LOADING}'") == 1


# ══════════════════════════════════════════════════════════════════════════
# 驗收阻擋 2：§八 跨區揭露框 —— 不 stub `read_v4_macro_veto`（真函式）
# ══════════════════════════════════════════════════════════════════════════
#: 既有缺值路徑那句（#781 前就在；本批只讓 VIX 無效時也走它，不新增字）
_V4_UNAVAILABLE = (f'（§三 籌碼的「{VETO_V4_ENGINE_NAME}」因 VIX 未取得而無法判定，'
                   '本區與該燈暫時無法比對 —— 兩區都缺 VIX 時請先按「🚀 一鍵更新全部數據」）')


def _run_mid_real_v4(mod, vix_node, mp, fut=-40000.0):
    """同 `_run_mid`，但 §三 的 `read_v4_macro_veto` 用真函式（只把它讀的 st 換成同一個假 st）。"""
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    assert (SC.read_v4_macro_veto.__module__, SC.read_v4_macro_veto.__qualname__) == (
        'src.ui.tabs.macro.section_chips', 'read_v4_macro_veto')          # 確定沒被 stub
    info = dict(_MID_BASE)
    info["vix"] = vix_node
    li = pd.DataFrame({"日期": ["2026-10-01"], "外資大小": [fut]})
    fake = _FakeSTFig({"macro_info": info, "bias_info": {"bias_240": 5.0}, "li_latest": li})
    mp.setattr(mod, "st", fake)
    mp.setattr(SC, "st", fake)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: None)
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None))
    mod.render_section_mid(False, {}, {}, {})
    return fake.out, SC.read_v4_macro_veto()


_INVALID_FOR_DISCLOSURE = [pytest.param(v, id=repr(v)) for v in (-5, 0, -0.0, "18.5", True, math.nan)]


class TestV1CrossDisclosure:
    @pytest.mark.parametrize("v", _INVALID_FOR_DISCLOSURE)
    def test_invalid_vix_takes_unavailable_caption(self, v, monkeypatch):
        out, light = _run_mid_real_v4(_mod("mid"), {"current": v}, monkeypatch)
        assert ("caption", _V4_UNAVAILABLE) in out, out
        assert not any("看的是 VIX=" in t for _k, t in out)
        assert not any(k == "warning" and "兩套判定結論不一致" in t for k, t in out)

    def test_premise_real_reader_still_judges_negative_vix(self, monkeypatch):
        # 前提自證：真 `read_v4_macro_veto` 在同一份 session 下照樣拿 −5 判出 🔴 燈 ——
        # 少了 §八 的閘門，揭露框就會印「看的是 VIX=-5.0、外資期貨=-40,000 口」
        _out, light = _run_mid_real_v4(_mod("mid"), {"current": -5}, monkeypatch)
        assert light is not None and light["_vix"] == -5.0 and light["status"].startswith("🔴")

    def test_pre_fix_printed_contradiction(self, mid_pre, monkeypatch):
        out, _light = _run_mid_real_v4(mid_pre, {"current": -5}, monkeypatch)
        assert any(k == "warning" and "看的是 VIX=-5.0、外資期貨=-40,000 口" in t for k, t in out)

    @pytest.mark.parametrize("v,fut", [(18.0, -40000.0), (35.0, 0.0), (18.0, 0.0), (25.0, -40000.0)])
    def test_valid_vix_disclosure_unchanged(self, v, fut, mid_pre, monkeypatch):
        now, _ = _run_mid_real_v4(_mod("mid"), {"current": v}, monkeypatch, fut)
        pre, _ = _run_mid_real_v4(mid_pre, {"current": v}, monkeypatch, fut)
        assert now == pre
        if (v, fut) == (18.0, -40000.0):          # §八 無觸發、§三 紅燈 → 照舊揭露分歧
            assert any(k == "warning" and "看的是 VIX=18.0、外資期貨=-40,000 口" in t for k, t in now)

    def test_true_missing_vix_unchanged(self, mid_pre, monkeypatch):
        now, _ = _run_mid_real_v4(_mod("mid"), {"current": None}, monkeypatch)
        pre, _ = _run_mid_real_v4(mid_pre, {"current": None}, monkeypatch)
        assert now == pre and ("caption", _V4_UNAVAILABLE) in now
