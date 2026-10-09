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
  numpy bool 的缺值與正常形狀，渲染與修前相同（修前就拋例外的非數字字串／超大 int 除外 —— 改走
  bias_info 為空的既有路徑，見 test_pre_fix_raised_now_renders_empty_path）。numpy bool（📌 重驗更正：
  原句「單邊 numpy bool 改走價／年線缺值路徑（…fd989ae 是把 np.True_ 當 1 印假乖離）」不精確 ——
  np.False_ 那半不變，印假乖離只在另一邊是有限正數時成立）：價給 np.True_、年線給有限正數，或反過來
  → fd989ae 把 np.True_ 當 1 印假乖離；價給 np.True_、年線缺值／0／np.False_／np.True_／Python True，
  或價給 Python True、年線給 np.True_ → fd989ae 在引擎相減拋 TypeError、整個作戰室崩潰（缺值／0／
  np.False_ 經作戰室 `or 0` 換 0，引擎再把年線的 0 換成價 np.True_）；兩類修後都改走價／年線缺值路徑、
  不崩（有意識的變更）。單邊 np.False_，或年線給 np.True_ 而價缺值：fd989ae 就不讀（守衛 `> 0` 或
  `is not None` 不成立），不變（見 TestWarroomNumpyBool）。
  📌 驗收（重驗）：正常形狀的「📐 年線位階參考」另以 fd989ae 實跑結果寫死（TestWarroomV4HintGolden，
  含乖離 +0.0 的三例），不再只靠同一份 warroom 換引擎的相對比對。
- V1-n2（L5 v1）`section_mid`：VIX 為負（實跑 −5）印「✅ 市場平靜」「平靜期 🟢」「A VIX=-5.0<20 ✅」、
  否決權收到 −5。總管決定 VIX ≤ 0（定義上不可能）視同非有限值 —— 在 §八 自己取 VIX 的 `_vcur8_v` 處理，
  由它取值的 KPI「待取得」、基本面否決檢查「VIX待取得」、§八 否決權那句、三環「A VIX未知」、
  apply_vix_veto(None) 走 #781 既有缺值路徑。📌 範圍更正（驗收）：原句「本檔取 VIX 的單一入口／全部走」
  過寬 —— 本頁另有 §三 `read_v4_macro_veto()` 與頂部總經警示看板（L1，正式載入才出現）自行讀 VIX，
  不在上述清單內：前者供 §八 跨區揭露框如實列出 §三 那盞燈的實際狀態與它看的 VIX（總管改判，撤回
  db7b2e2「驗收阻擋 2」的閘門 —— §三 判得出燈時，「§三 因 VIX 未取得而無法判定」反而是假話；
  §八 其餘欄位有值時揭露框與 fd989ae 相同，下方以真函式對寫死的 golden 驗；例外：只有 VIX 一項且
  無效、其餘皆缺時，§八 不可評估（3-4 的連帶結果），揭露框的比對句與缺值句都不出，等於 fd989ae 在
  VIX=None 同情境的輸出（皆無；見 TestV1CrossDisclosureOnlyVix））；§三 收下無效 VIX 屬
  section_chips、不在本批範圍，總管另登記為新項。後者屬 L1、總管另登記為已知限制。
- V1-n5（同檔）：VIX「有值但無效」（非有限或 ≤ 0；含非數值）時，§八 那句原寫「VIX 數據載入中，VIX 否決權
  暫無法判斷」—— 值明明到了，「載入中」是假的。只在此時於子句界純刪「VIX 數據載入中，」；
  真的沒值（None／缺鍵）原句一字不變。界定（驗收阻擋 3-8，總管確認）：只有 None 與缺鍵＝真的沒值；
  pd.NA、pd.NaT、''、'N/A'、bool、list 等一律算「有值但無效」；VIX 節點本身不是 dict 比照缺鍵。

只擋資料、不加新字句、不動門檻、不動版面；有限輸入與修前逐位相同（下方對拍修前副本）。
每段都有「拔掉修復即轉紅」的斷言（修前副本在同一組輸入上必須給出不同答案）。
"""
from __future__ import annotations

import math
import random
import re
import struct
import types
import warnings
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from shared import macro_compute as MC
from src.config import (
    VETO_FUNDAMENTAL_INPUTS, VETO_FUNDAMENTAL_NAME, VETO_FUNDAMENTAL_SCOPE_NOTE, VETO_V4_ENGINE_NAME,
)
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
#: 批 Z10（Q-r10b，客戶 2026-10-09「等於門檻歸防禦」）：現行引擎在剛好 −30000 的期望值（凍結副本仍用表內原值）
_V4_GOLDEN_Z10 = {(20000.0, 19000.0, -30000): ('🟡 多頭過熱 / 震盪警戒', 5.26, True, False, True)}
_V4_GOLDEN_HOLD = {_G_BULL: '80% - 100%', _G_HOT: '50% - 70%', _G_BEAR: '20% - 40%'}
#: (價, 年線, 外資期貨) → (Signal, Bias_240, Is_Bull, Is_Overheated, Is_Foreign_Hedging)
_V4_GOLDEN = [pytest.param(a, w, id=repr(a)) for a, w in (
    ((20000.0, 19000.0, 0), (_G_BULL, 5.26, True, False, False)),          # round 2 位（改 1 位 → 5.3）
    ((20000.0, 19000.0, -40000), (_G_HOT, 5.26, True, False, True)),       # 多頭 × 外資避險
    ((20000.0, 19000.0, -30000), (_G_BULL, 5.26, True, False, False)),     # 避險門檻（凍結副本不含等號；現行見 _V4_GOLDEN_Z10）
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
        # 不依賴價格的鍵照舊；批 Z10（C8-n6）起外資期貨 None ⇒ None（未知），其餘同修前
        # 批 Z10（Q-r10b，客戶 2026-10-09）：剛好 −30000 歸避險側 ⇒ `<=`（原 `<`）
        assert out['Is_Foreign_Hedging'] is (None if fut is None else ((fut or 0) <= -30000))

    @pytest.mark.parametrize('args', [(None, None, None), (0, 0, 0)])
    def test_reported_cases(self, args):
        pre = _V4_PRE(*args)
        assert (pre['Bias_240'], pre['Is_Bull'], pre['Signal']) == (0.0, True, '🟢 強勢多頭')  # 前提：修前捏值
        new = _V4(*args)
        assert (new['Bias_240'], new['Is_Bull'], new['Is_Overheated']) == (None, None, None)
        assert (new['Signal'], new['Action_Advice'], new['Suggested_Holding']) == (None, None, None)
        assert new['Is_Foreign_Hedging'] is (None if args[2] is None else False)   # 批 Z10（C8-n6）

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
        for fn in (_V4, _V4_PRE):
            # 批 Z10（Q-r10b）：剛好 −30000 現行引擎歸避險側（凍結副本仍為修前嚴格 `<`）
            sig, bias, bull, hot, hedge = (_V4_GOLDEN_Z10.get(args, want) if fn is _V4 else want)
            out = fn(*args)
            assert list(out) == _V4_KEYS
            assert (out['Signal'], out['Suggested_Holding'], out['Action_Advice']) == (
                sig, _V4_GOLDEN_HOLD[sig], _V4_GOLDEN_ACTION[sig]), fn
            assert _hexbits(out['Bias_240']) == _hexbits(bias), (fn, out['Bias_240'])
            # 批 Z10（C8-n6）：外資期貨 None ⇒ 現行引擎回 None（未知），凍結副本仍為 False
            _hedge = None if (fn is _V4 and args[2] is None) else hedge
            assert (out['Is_Bull'], out['Is_Overheated'], out['Is_Foreign_Hedging']) == (bull, hot, _hedge)
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
                        # 批 Z10（C8-n6）：f 為 None 時只有 Is_Foreign_Hedging 由 False 改 None，其餘逐位比對
                        _fn = _V4 if f is not None else (
                            lambda *a: {**_V4(*a), 'Is_Foreign_Hedging': False})
                        # 批 Z10（Q-r10b）：剛好 −30000 現行引擎歸避險側 ⇒ 對拍凍結副本的「−30001」（避險成立、其餘同）
                        _fp = -30001 if (f is not None and f == -30000) else f
                        new, pre = _outcome(_fn, p, m, f), _outcome(_V4_PRE, p, m, _fp)
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
    # 📌 批 Z6（C7-n9，有意識的更正，⛔ 不是漏改）：作戰室改讀 `warroom_summary['futures_net']` ——
    #   原讀的 session key `futures_net` 全 repo 0 寫入點、修後作戰室不再用它（L3 `load_section_inputs`
    #   仍會讀它並轉 int，見 section_warroom 模組 docstring）。期貨值改由 warroom_summary 餵入，
    #   本檔 fut=−40000 的各例（含 TestWarroomV4HintGolden 的三個避險例）才照原意出現「外資期貨避險」。
    fake = _FakeST({'bias_info': bias, 'cl_data': {'margin': 2000.0},
                    'warroom_summary': {'futures_net': futures_net}})
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
    # 重驗更正：下列 fd989ae 整個作戰室崩潰（見 test_pre_fix_crashed），修後同樣走缺值路徑
    ({'price': np.True_}, {'price': None}, 'price-np.True_-ma-absent'),
    ({'price': np.True_, 'ma240': None}, {'price': None, 'ma240': None}, 'price-np.True_-ma-None'),
    ({'price': np.True_, 'ma240': 0.0}, {'price': None, 'ma240': 0.0}, 'price-np.True_-ma-0'),
    ({'price': np.True_, 'ma240': np.False_}, {'price': None, 'ma240': np.False_},
     'price-np.True_-ma-np.False_'),
    ({'price': np.True_, 'ma240': True}, {'price': None, 'ma240': True}, 'price-np.True_-ma-True'),
    ({'price': True, 'ma240': np.True_}, {'price': None, 'ma240': np.True_}, 'price-True-ma-np.True_'),
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
        # （只在另一邊是有限正數時如此；另一邊不是時見 test_pre_fix_crashed）
        out = '\n'.join(_wr(bias, monkeypatch, _V4_PRE))
        assert '📐 年線位階參考：年線乖離 ' in out

    @pytest.mark.parametrize('bias', [
        {'price': np.True_}, {'price': np.True_, 'ma240': None}, {'price': np.True_, 'ma240': 0.0},
        {'price': np.True_, 'ma240': np.False_}, {'price': np.True_, 'ma240': np.True_},
        {'price': np.True_, 'ma240': True}, {'price': True, 'ma240': np.True_}], ids=repr)
    def test_pre_fix_crashed(self, bias, monkeypatch):
        # 重驗更正：另一邊不是有限正數時，fd989ae 不是印假乖離，而是在引擎相減拋 TypeError
        # （置換後兩邊都是布林、至少一邊 numpy bool）—— 整個作戰室崩潰；修後見 _WR_NPBOOL
        with pytest.raises(TypeError, match='numpy boolean subtract'):
            _wr(bias, monkeypatch, _V4_PRE)

    @pytest.mark.parametrize('fut', [0, -40000])
    @pytest.mark.parametrize('bias', [
        {'price': np.False_, 'ma240': 16000.0}, {'price': 20000.0, 'ma240': np.False_},
        {'ma240': np.True_}, {'price': None, 'ma240': np.True_}], ids=repr)
    def test_unchanged_vs_fd989ae(self, bias, fut, monkeypatch):
        # 單邊 np.False_，或年線 np.True_ 而價缺值：fd989ae 就不讀 Bias_240 —— 修後渲染逐字相同
        assert _wr(bias, monkeypatch, _V4, fut) == _wr(bias, monkeypatch, _V4_PRE, fut)


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
    ("    _vix_cur8_raw = _m8_vix.get('current') if isinstance(_m8_vix, dict) else None\n"
     "    _vcur8_v = (None if isinstance(_vix_cur8_raw, (np.bool_, complex, np.complexfloating))\n"
     "                else _finite_yoy(_m8_vix, 'current'))\n",
     "    _vcur8_v = _finite_yoy(_m8_vix, 'current')\n"),          # 驗收 3-3 延伸：numpy bool／複數先排除
    ("    if _vcur8_v is not None and _vcur8_v <= 0:\n"
     "        _vcur8_v = None\n", ""),
    ("            st.info('VIX 否決權暫無法判斷' if _vix_bad8\n"
     "                    else 'VIX 數據載入中，VIX 否決權暫無法判斷')\n",
     "            st.info('VIX 數據載入中，VIX 否決權暫無法判斷')\n"),
)


# ── 驗收（重驗）阻擋 1：warroom 正常形狀的「📐 年線位階參考」以 fd989ae 實跑結果寫死 ───────────
# 前面的 warroom 測試都是同一份 warroom 程式換引擎／輸入的相對比對 —— 守衛被改成判真值
# （`and _v4.get('Bias_240')`）時，乖離四捨五入成 0.0 的「年線乖離 +0.0%」那段會消失（沒有外資避險
# 片段時整行消失；有時只剩「外資期貨避險」），相對比對抓不到。
# 這裡改釘絕對字串（fd989ae 實跑後凍結於本檔，不讀 git）。⛔ 不釘「-0.0%」（價略低於年線時
# fd989ae 起就印 -0.0% 的負零顯示，屬範圍外、總管另登記）。
_WR_V4_DIV = '<div style="font-size:11px;color:#8b949e;margin-top:4px;">📐 年線位階參考：{}</div>'
_WR_V4_GOLDEN = [pytest.param(b, f, h, id=i) for b, f, h, i in (
    ({'bias_240': 25.0, 'bias_20': 12.0, 'price': 20000.0, 'ma240': 16000.0, 'data_days': 300,
      'is_estimated': False}, 0, '年線乖離 +25.0%｜乖離過熱', 'overheated'),
    ({'price': 15000.0, 'ma240': 16000.0}, 0, '年線乖離 -6.2%｜股價在年線下', 'below-ma'),
    ({'price': 20000.0, 'ma240': 19000.0}, -40000, '年線乖離 +5.3%｜外資期貨避險', 'bull-hedging'),
    # 乖離 +0.0 的三例（總管要求的兩例：價＝年線、資料 1 天估算；另加與外資避險並存的一例）
    ({'price': 16000.0, 'ma240': 16000.0}, 0, '年線乖離 +0.0%', 'zero-bias-price-eq-ma'),
    ({'price': 16500.0, 'ma240': 16500.0, 'bias_240': 0.0, 'bias_20': 0.0, 'data_days': 1,
      'is_estimated': True}, 0, '年線乖離 +0.0%（估算）', 'zero-bias-1day-estimated'),
    ({'price': 16000.0, 'ma240': 16000.0}, -40000, '年線乖離 +0.0%｜外資期貨避險', 'zero-bias-hedging'),
    # 批 Z9 第 2 組（Z6-n7，客戶 2026-10-08 核字）：價缺＋避險改印「未知｜外資期貨避險」（fd989ae 時為「外資期貨避險」）。
    ({'ma240': 16000.0}, -40000, '未知｜外資期貨避險', 'price-missing-hedging'),
    ({}, 0, None, 'empty'),
)]


class TestWarroomV4HintGolden:
    @pytest.mark.parametrize('bias,fut,hint', _WR_V4_GOLDEN)
    def test_v4_hint_line_matches_fd989ae(self, bias, fut, hint, monkeypatch):
        joined = '\n'.join(_wr(bias, monkeypatch, _V4, fut))
        if hint is None:
            assert '📐 年線位階參考' not in joined
        else:
            assert _WR_V4_DIV.format(hint) in joined, re.findall(r'📐 年線位階參考：[^<]*', joined)
            assert joined.count('📐 年線位階參考') == 1


class _FakeSTFig(_FakeST):
    """多記一筆 VIX 走勢圖標題（「✅ 市場平靜」等燈義只出現在圖標題裡）。"""

    def plotly_chart(self, fig, *a, **k):
        self.out.append(("plotly_chart", str(fig.layout.title.text)))


def _run_mid_raw(mod, vix_node, mp, drop_key=False, base=None):
    """回 (元素種類, 文字) 清單 —— 驗收阻擋 3-5：要能分辨 st.info 與 st.warning 等。"""
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    info = dict(_MID_BASE if base is None else base)
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
    return list(fake.out), calls


def _run_mid(mod, vix_node, mp, drop_key=False):
    out, calls = _run_mid_raw(mod, vix_node, mp, drop_key)
    return [t for _k, t in out], calls


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


_COMPLEX_WARNING = getattr(np, "exceptions", np).ComplexWarning


# ── 驗收阻擋 3-3：≤ 0 守衛不得只認 Python int／float；numpy bool／複數同屬無效（延伸）────────────
_NONPOS_TYPES = [pytest.param(v, id=i) for v, i in (
    (np.int64(-3), "np.int64(-3)"), (np.int64(0), "np.int64(0)"), (np.float32(-5), "np.float32(-5)"),
    (Decimal("-5"), "Decimal(-5)"), (Fraction(-5, 1), "Fraction(-5,1)"), (np.False_, "np.False_"),
)]
_NUMPY_BOOL_COMPLEX = [pytest.param(v, id=i) for v, i in (
    (np.True_, "np.True_"), (np.complex128(18), "np.complex128(18)"),
    (np.complex128(-5), "np.complex128(-5)"), (np.complex64(25), "np.complex64(25)"),
)]


class TestV1n2GuardTypes:
    @pytest.mark.parametrize("v", _NONPOS_TYPES + _NUMPY_BOOL_COMPLEX)
    def test_invalid_path(self, v, monkeypatch):
        with warnings.catch_warnings():
            warnings.simplefilter("error", _COMPLEX_WARNING)    # 不得靠丟掉虛部把複數當實數
            out, calls = _run_mid_raw(_mod("mid"), _node(v), monkeypatch)
        joined = "\n".join(t for _k, t in out)
        assert "平靜期" not in joined and "市場平靜" not in joined and "A VIX=" not in joined, joined[-1500:]
        assert "A VIX未知" in joined
        assert calls == [(None,)]                                # 否決權不得收到負值／假值
        assert ("info", _INVALID) in out
        assert any("VIX 恐慌指數" in t and "待取得" in t for _k, t in out)

    @pytest.mark.parametrize("v", _NONPOS_TYPES + _NUMPY_BOOL_COMPLEX)
    def test_pre_fix_used_the_value(self, v, mid_pre, monkeypatch):
        # 前提自證：修前（還原體）把這些值當成有效 VIX —— 印出「A VIX=…」並把它送進否決權
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", _COMPLEX_WARNING)
            out, calls = _run_mid_raw(mid_pre, _node(v), monkeypatch)
        assert any("A VIX=" in t for _k, t in out)
        assert calls and calls[0][0] is not None


# ── 驗收阻擋 3-4：只有 VIX 一項且無效、其餘四項皆缺 → 基本面否決檢查不可評估 ─────────────────
class TestV1FundEvaluableOnlyVix:
    @pytest.mark.parametrize("v", [-5, 0, np.int64(-3), math.nan, "18.5", np.True_], ids=repr)
    def test_no_ok_line(self, v, monkeypatch):
        out, _ = _run_mid_raw(_mod("mid"), {"current": v}, monkeypatch, base={})
        assert not any(VETO_FUNDAMENTAL_NAME in t and t.startswith("✅") for _k, t in out), out
        assert ("caption", f"📌 {VETO_FUNDAMENTAL_SCOPE_NOTE}") not in out

    def test_pre_fix_printed_ok_line_for_negative(self, mid_pre, monkeypatch):
        out, _ = _run_mid_raw(mid_pre, {"current": -5}, monkeypatch, base={})
        assert any(k == "success" and t.startswith(f"✅ {VETO_FUNDAMENTAL_NAME}：無觸發") for k, t in out)

    def test_valid_vix_alone_still_evaluable(self, monkeypatch):
        out, _ = _run_mid_raw(_mod("mid"), {"current": 18.0}, monkeypatch, base={})
        assert any(k == "success" and t.startswith(f"✅ {VETO_FUNDAMENTAL_NAME}：無觸發") for k, t in out)


# ── 驗收阻擋 3-5／3-8：那句必須以 st.info 呈現；「有值」界定（總管確認）────────────────────────
_HAS_VALUE_CONFIRMED = [pytest.param(v, id=i) for v, i in (
    (pd.NA, "pd.NA"), (pd.NaT, "pd.NaT"), ("", "empty-str"), ("N/A", "str-N/A"), (True, "True"),
    (False, "False"), ([1, 2], "list"), (np.True_, "np.True_"), (math.nan, "nan"), (-5, "-5"),
)]


class TestV1n5ElementKindAndDefinition:
    @pytest.mark.parametrize("v", _HAS_VALUE_CONFIRMED)
    def test_has_value_invalid_is_info_short_sentence(self, v, monkeypatch):
        out, calls = _run_mid_raw(_mod("mid"), _node(v), monkeypatch)
        assert ("info", _INVALID) in out, out
        assert ("info", _LOADING) not in out
        assert not any(t in (_INVALID, _LOADING) for k, t in out if k != "info")
        assert calls == [(None,)]

    @pytest.mark.parametrize("node,drop", _TRUE_MISSING)
    def test_true_missing_is_info_original_sentence(self, node, drop, monkeypatch):
        out, _ = _run_mid_raw(_mod("mid"), node, monkeypatch, drop)
        assert ("info", _LOADING) in out and ("info", _INVALID) not in out
        assert not any(t in (_INVALID, _LOADING) for k, t in out if k != "info")


# ══════════════════════════════════════════════════════════════════════════
# §八 跨區揭露框（總管改判：撤回 db7b2e2「驗收阻擋 2」的閘門）—— 真 `read_v4_macro_veto`、不 stub
# ══════════════════════════════════════════════════════════════════════════
# 改判理由：本框的職責是如實寫出 §三 那盞燈的實際狀態；`read_v4_macro_veto()` 就是 §三 自己的入口。
# §八 判 VIX 無效、但 §三 照樣判得出燈時（VIX=−5、0、−0.0、數字字串、bool…），fd989ae 的比對句
# 「（§三 籌碼）：🔴 紅燈　看的是 VIX=-5.0、外資期貨=-40,000 口」是真話；閘門改走的「§三 …因 VIX
# 未取得而無法判定」在這些情況下是假話。真實優先於表面一致（§1）。根因（§三 收下無效 VIX）屬
# section_chips、不在本批範圍，總管另登記為新項。下方 golden 以 fd989ae 實跑後寫死（不讀 git）。
#: 既有缺值句：只在 §三 的 `read_v4_macro_veto()` 回 None 時出現（與 fd989ae 相同）
_V4_UNAVAILABLE = (f'（§三 籌碼的「{VETO_V4_ENGINE_NAME}」因 VIX 未取得而無法判定，'
                   '本區與該燈暫時無法比對 —— 兩區都缺 VIX 時請先按「🚀 一鍵更新全部數據」）')


def _cmp_fd989ae(status, vix_txt, fut_txt, has_veto=False):
    """fd989ae 揭露框比對句：f-string 逐字凍結於本檔（名稱常數取自 src.config），VIX／期貨字樣寫死。"""
    return (f'⚖️ **同一頁的兩套判定結論不一致 —— 這不是系統算錯，'
            f'是它們看的資料本來就不同**\n\n'
            f'- **{VETO_FUNDAMENTAL_NAME}**（本區）：'
            f'{"🚨 已觸發" if has_veto else "✅ 無觸發"}　'
            f'看的是 {VETO_FUNDAMENTAL_INPUTS}\n'
            f'- **{VETO_V4_ENGINE_NAME}**（§三 籌碼）：'
            f'{status}　'
            f'看的是 VIX={vix_txt}、'
            f'外資期貨={fut_txt} 口\n\n'
            f'👉 兩者不是同一個指標，不必也不該互相覆蓋；'
            f'實際持股水位一律以 🎚️ 建議持股油門 為準。')


def _disclosure(out):
    """只取揭露框的輸出（比對句 warning／缺值句 caption），保留元素種類與順序。"""
    return [(k, t) for k, t in out
            if (k == "warning" and "兩套判定結論不一致" in t) or (k == "caption" and t.startswith("（§三 籌碼的「"))]


def _run_mid_real_v4(mod, vix_node, mp, fut=-40000.0, base=None):
    """同 `_run_mid`，但 §三 的 `read_v4_macro_veto` 用真函式（只把它讀的 st 換成同一個假 st）。"""
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    assert (SC.read_v4_macro_veto.__module__, SC.read_v4_macro_veto.__qualname__) == (
        'src.ui.tabs.macro.section_chips', 'read_v4_macro_veto')          # 確定沒被 stub
    info = dict(_MID_BASE if base is None else base)
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


_RED, _F40K = "🔴 紅燈", "-40,000"
#: 📌 批 Z7（Z3-n4，併 Z3-n11；有意識的更正，⛔ 不是漏改 —— 總管規格明定的預期變更）：§三
#:   `read_v4_macro_veto()` 改走 L0 共用判定 `shared.vix_validity.vix_value_or_none`（與 §八 `_vcur8_v`
#:   同一套規則）→ 下表前 14 組「§八 判無效、§三 原本照樣判燈」的 VIX，§三 也回 None ⇒ 揭露框改走既有
#:   缺值句 `_V4_UNAVAILABLE`（此時屬實：§三 確實判不出）。fd989ae 實跑值逐組凍結於第三欄（`pre`，
#:   ⛔ 不再是斷言目標，只供對照「修前 → 修後」）；斷言目標為第四欄（`want`）。
_Z7_UNAVAILABLE = [("caption", _V4_UNAVAILABLE)]
#: (§八 判無效的 VIX, 外資期貨, fd989ae 揭露框輸出〔實跑寫死〕, 批 Z7 起的揭露框輸出)
_DISCLOSURE_GOLDEN = [pytest.param(v, fut, pre, want, id=f"{v!r}|{fut:g}") for v, fut, pre, want in (
    (-5, -40000.0, [("warning", _cmp_fd989ae(_RED, "-5.0", _F40K))], _Z7_UNAVAILABLE),
    (0, -40000.0, [("warning", _cmp_fd989ae(_RED, "0.0", _F40K))], _Z7_UNAVAILABLE),
    (-0.0, -40000.0, [("warning", _cmp_fd989ae(_RED, "-0.0", _F40K))], _Z7_UNAVAILABLE),
    ("18.5", -40000.0, [("warning", _cmp_fd989ae(_RED, "18.5", _F40K))], _Z7_UNAVAILABLE),
    (True, -40000.0, [("warning", _cmp_fd989ae(_RED, "1.0", _F40K))], _Z7_UNAVAILABLE),
    (np.True_, -40000.0, [("warning", _cmp_fd989ae(_RED, "1.0", _F40K))], _Z7_UNAVAILABLE),
    (False, -40000.0, [("warning", _cmp_fd989ae(_RED, "0.0", _F40K))], _Z7_UNAVAILABLE),
    (np.int64(-3), -40000.0, [("warning", _cmp_fd989ae(_RED, "-3.0", _F40K))], _Z7_UNAVAILABLE),
    (Decimal("-5"), -40000.0, [("warning", _cmp_fd989ae(_RED, "-5.0", _F40K))], _Z7_UNAVAILABLE),
    (np.complex128(18), -40000.0, [("warning", _cmp_fd989ae(_RED, "18.0", _F40K))], _Z7_UNAVAILABLE),
    # fd989ae：§三 判得出、且為 🟢 → 與 §八 一致 → 不出揭露；批 Z7 起 §三 判不出 → 既有缺值句
    (-5, 0.0, [], _Z7_UNAVAILABLE), ("18.5", 0.0, [], _Z7_UNAVAILABLE),
    (True, 0.0, [], _Z7_UNAVAILABLE), (np.True_, 0.0, [], _Z7_UNAVAILABLE),
    # §三 自己也判不出（read_v4_macro_veto 回 None）→ 既有缺值句（fd989ae 與批 Z7 相同）
    (math.nan, -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    (math.inf, -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    (-math.inf, -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    (None, -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    ("", -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    ("N/A", -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    (pd.NA, -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    ([1, 2], -40000.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
    (math.nan, 0.0, [("caption", _V4_UNAVAILABLE)], [("caption", _V4_UNAVAILABLE)]),
)]


class TestV1CrossDisclosure:
    # 📌 批 Z7（Z3-n4）：原名 `test_disclosure_matches_fd989ae_golden` —— 前 14 組自批 Z7 起刻意不再等於
    #   fd989ae（見上表註），改名以免名實不符；斷言目標改為 `want` 欄。
    @pytest.mark.parametrize("v,fut,pre,want", _DISCLOSURE_GOLDEN)
    def test_disclosure_matches_golden(self, v, fut, pre, want, monkeypatch):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", _COMPLEX_WARNING)   # §三 自讀 numpy complex 的既有警告（範圍外）
            out, _light = _run_mid_real_v4(_mod("mid"), {"current": v}, monkeypatch, fut)
        assert _disclosure(out) == want, _disclosure(out)

    def test_negative_vix_section3_now_unavailable_too(self, monkeypatch):
        # 📌 批 Z7（Z3-n4，預期變更；原名 `test_negative_vix_states_section3_value_verbatim`）：
        #   fd989ae 實跑 VIX=−5＋外資期貨 −40,000 口時，比對句為「（§三 籌碼）：🔴 紅燈　看的是 VIX=-5.0、
        #   外資期貨=-40,000 口」（§三 收下無效 VIX）。批 Z7 起 §三 同樣判 −5 無效 → 該句不再出現，改出既有
        #   缺值句；同一區的 §八 自己照舊判 VIX 無效（A VIX未知、否決權那句）。
        out, _light = _run_mid_real_v4(_mod("mid"), {"current": -5}, monkeypatch)
        assert not [t for k, t in out if k == "warning" and "兩套判定結論不一致" in t]
        assert ("caption", _V4_UNAVAILABLE) in out
        joined = "\n".join(t for _k, t in out)
        assert "看的是 VIX=-5.0" not in joined
        assert "A VIX未知" in joined and ("info", _INVALID) in out

    def test_section3_reader_rejects_invalid_vix(self, monkeypatch):
        # 📌 批 Z7（Z3-n4，預期變更；原名 `test_section3_reader_judges_light_from_invalid_vix`）：
        #   fd989ae 時 §三 自己的入口拿 −5 判出 🔴 燈（本條原註「若日後 §三 改為不收無效 VIX，本條會轉紅提醒
        #   同步更新 golden」—— 批 Z7 即該次更新）。批 Z7 起回 None。
        _out, light = _run_mid_real_v4(_mod("mid"), {"current": -5}, monkeypatch)
        assert light is None

    @pytest.mark.parametrize("v,fut", [(18.0, -40000.0), (35.0, 0.0), (18.0, 0.0), (25.0, -40000.0)])
    def test_valid_vix_disclosure_unchanged(self, v, fut, mid_pre, monkeypatch):
        now, _ = _run_mid_real_v4(_mod("mid"), {"current": v}, monkeypatch, fut)
        pre, _ = _run_mid_real_v4(mid_pre, {"current": v}, monkeypatch, fut)
        assert now == pre
        if (v, fut) == (18.0, -40000.0):          # §八 無觸發、§三 紅燈 → 照舊揭露分歧
            assert _disclosure(now) == [("warning", _cmp_fd989ae(_RED, "18.0", _F40K))]

    def test_true_missing_vix_unchanged(self, mid_pre, monkeypatch):
        now, _ = _run_mid_real_v4(_mod("mid"), {"current": None}, monkeypatch)
        pre, _ = _run_mid_real_v4(mid_pre, {"current": None}, monkeypatch)
        assert now == pre and ("caption", _V4_UNAVAILABLE) in now


# ── 只有 VIX 一項且無效、其餘四項皆缺（3-4 的連帶結果；總管裁定維持）——真 `read_v4_macro_veto` ──────
# 理由：依規格「VIX 無效＝走既有缺值路徑」，此情境應與 fd989ae 在「VIX=None、其餘四項皆缺」時相同 ——
# §八 沒有可評估的結論（3-4：`_fund_evaluable` 不把無效 VIX 算進去），就沒有可比對的對象，揭露框的
# 比對句與缺值句都不出；§八 不印任何結論，頁面上也就沒有互相矛盾的說法。注意這不是 §三 判不出：
# 同情境下 §三 真函式照樣拿 −5 判出 🔴 燈（見 test_premise_section3_still_judges_alone）。
# 📌 批 Z7（Z3-n4）：上一句只在 fd989ae～批 Z6 成立 —— 批 Z7 起 §三 也判下列第一行的值無效、回 None
#   （見改名後的 test_premise_section3_now_unavailable_alone）；本段「揭露框不出」的斷言不受影響。
#: fd989ae 在「VIX=None、其餘四項皆缺、外資期貨 −40,000 口」時的揭露框輸出 —— 以 fd989ae 實跑後寫死（無）
_FD989AE_DISCLOSURE_ONLY_VIX_NONE: list = []
_ONLY_VIX_INVALID = [pytest.param(v, id=repr(v)) for v in (
    -5, 0, -0.0, "18.5", True, np.True_, np.int64(-3),          # fd989ae：§三 判得出燈（皆 🔴）；批 Z7 起 §三 也回 None
    math.nan, math.inf, pd.NA, "", "N/A",                      # §三 也判不出（read_v4_macro_veto 回 None）
)]


class TestV1CrossDisclosureOnlyVix:
    @pytest.mark.parametrize("v", _ONLY_VIX_INVALID)
    def test_no_disclosure_when_section8_not_evaluable(self, v, monkeypatch):
        out, _light = _run_mid_real_v4(_mod("mid"), {"current": v}, monkeypatch, base={})
        assert _disclosure(out) == _FD989AE_DISCLOSURE_ONLY_VIX_NONE == [], _disclosure(out)
        assert not any("看的是 VIX=" in t for _k, t in out)
        assert ("caption", _V4_UNAVAILABLE) not in out
        assert not any(k == "success" and VETO_FUNDAMENTAL_NAME in t for k, t in out)   # §八 不印結論

    def test_vix_none_same_scenario_also_none(self, monkeypatch):
        # 對照組：VIX=None 同情境（＝fd989ae 寫死值的情境）—— 修後同樣無揭露框
        out, light = _run_mid_real_v4(_mod("mid"), {"current": None}, monkeypatch, base={})
        assert light is None
        assert _disclosure(out) == _FD989AE_DISCLOSURE_ONLY_VIX_NONE

    def test_premise_section3_now_unavailable_alone(self, monkeypatch):
        # 📌 批 Z7（Z3-n4，預期變更；原名 `test_premise_section3_still_judges_alone`）：fd989ae 時同情境下
        #   §三 照樣拿 −5 判出 🔴 燈（揭露框不出純因 §八 不可評估）。批 Z7 起 §三 也判 −5 無效、回 None；
        #   揭露框照舊不出（§八 不可評估 ⇒ 比對句與缺值句皆不出，見上方 test_no_disclosure_when_section8_not_evaluable）。
        _out, light = _run_mid_real_v4(_mod("mid"), {"current": -5}, monkeypatch, base={})
        assert light is None


# ── 驗收（重驗）：極小正 VIX 仍是有效值 —— 不依賴 mid_pre，以 fd989ae 實跑結果寫死 ───────────────
# 原本只靠 mid_pre 字面比對＋單一參數 5e-324 擋「下限 `<= 0` 改 `<= 1e-300`」這類突變。
# 這裡直接斷言走有效路徑、輸出（圖標題、§八 結論、三環徽章、否決權參數、基本面檢查句）與 fd989ae 相同。
_TINY_VIX_GOLDEN = [pytest.param(v, t, id=repr(v)) for v, t in (
    (5e-324, 'VIX 恐慌指數 5e-324（MA20=17.5）— ✅ 市場平靜'),
    (2.2250738585072014e-308, 'VIX 恐慌指數 2.2250738585072014e-308（MA20=17.5）— ✅ 市場平靜'),
    (1e-300, 'VIX 恐慌指數 1e-300（MA20=17.5）— ✅ 市場平靜'),
    (1e-9, 'VIX 恐慌指數 1e-09（MA20=17.5）— ✅ 市場平靜'),
)]


class TestV1TinyPositiveVixGolden:
    @pytest.mark.parametrize('v,title', _TINY_VIX_GOLDEN)
    def test_valid_path_matches_fd989ae(self, v, title, monkeypatch):
        out, calls = _run_mid_raw(_mod('mid'), _node(v), monkeypatch)
        texts = [t for _k, t in out]
        joined = '\n'.join(texts)
        assert ('plotly_chart', title) in out                               # 走勢圖照畫、燈義照舊
        assert 'VIX 0.0 < 20（平靜期）' in joined
        assert '🟢 全球風險情緒穩定，未觸發 VIX 否決權。回歸個股籌碼面與基本面操作。' in joined
        assert 'A VIX=0.0<20' in joined and 'A VIX未知' not in joined
        assert len(calls) == 1 and type(calls[0][0]) is float and calls[0][0].hex() == float(v).hex()
        assert ('success', f'✅ {VETO_FUNDAMENTAL_NAME}：無觸發 — 景氣／通膨／外需面無系統性風險訊號') in out
        assert not any(t in (_INVALID, _LOADING) for t in texts)
