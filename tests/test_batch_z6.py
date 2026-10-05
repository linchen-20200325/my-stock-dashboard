"""批 Z6（2026-10-05）—— C7-n9 ＋ Z3-n10 釘子（基底 origin/main `84c1ca4`）。

- C7-n9（L5 v1 `src/ui/tabs/macro/section_warroom.py`，修正錯誤）：作戰室「外資期貨避險」片段從來出不來 ——
  作戰室讀 `st.session_state['futures_net']`（經 L3 `load_section_inputs`），全 repo 沒有任何地方寫這個 key
  （恆為 0）；同一輪 `render_traffic_light_top` 早已把 `calc_traffic_light` 的外資期貨淨口寫進
  `warroom_summary['futures_net']`。修法：作戰室改讀後者，並做有限值檢查 —— 缺鍵／None／NaN／±inf／
  非數值／bool／numpy bool／複數 ＝ 視同沒有、片段不出（−inf 若照送引擎會成立避險，必須擋）。
  ⛔ 不補寫 session_state['futures_net']（L3 `UNTOUCHED_BLOCKS`「全 repo 沒有任何一處寫這個 key」須維持為真；
  守衛在 `tests/test_p01_macro_refresh.py::test_futures_net_still_has_no_writer_anywhere`，本檔另釘作戰室不寫）。
  畫面字只用既有「外資期貨避險」那段；門檻（引擎 `< -30000`）與判式一字未動。
- Z3-n10（同檔）：價略低於年線（例 19999.99／20000）時「📐 年線位階參考」印「年線乖離 -0.0%」，同頁
  「年線位置」卡讀的是上游已正規化的 +0.0% —— 同一頁正負號不一致。修法：格式化結果是「-0.0」時改印
  「+0.0」，其餘值逐字不變。⚠️ 未照規格舉例寫 `round(x, 1) + 0.0`：引擎收 numpy 浮點時 numpy 的 round
  不是正確捨入（例 np.float64 乖離 0.05：`:+.1f` 印 +0.1、round 後印 +0.0）、收 Decimal 時 `+ 0.0` 拋
  TypeError —— 都會動到其他值的顯示（見 TestZ3n10WhyNotRoundPlusZero）。

修前輸出：於基底 `84c1ca4` 以本檔同一支 `_run`（`_FakeST`）實跑後寫死於本檔（⛔ 不讀 git）——
- `_BASE`：整個作戰室輸出（每個 st.* 文字呼叫的種類＋內容）的 sha256；
- 各例的「📐 年線位階參考」整段字串另以字面值寫死（`_FUT_CASES`／`_BIAS_CASES` 的第三欄是修後、
  `_BASE_HINT` 是修前），兩段代表性輸出（行動建議卡）以完整字面值寫死（`_CARD`）。
修後與修前的差異逐例以「還原替換」表達（`undo`：把修後輸出中**唯一**預期改變的字串換回修前寫法後，
sha256 必須等於修前 golden）—— 等於斷言「除了這一處，整個作戰室輸出逐字與基底相同」。
`get_allocation` 換成 L0 `build_allocation_decision(None)`（＝「總經未評估」的真 AllocationDecision，與 bare mode
下真 get_allocation 的結果相同）—— 只為讓本檔不受工作目錄有沒有 `macro_state.json` 影響，與本批無關。
"""
from __future__ import annotations

import datetime as _dt
import functools
import hashlib
import importlib.util
import math
import random
import re
import warnings
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_warroom as W
from shared.allocation_decision import build_allocation_decision
from shared.macro_compute import evaluate_market_status_v4_final as _V4
from tests.test_m2n2_no_zero_fill import _FakeST

_UNLOADED = build_allocation_decision(None)


@pytest.fixture(autouse=True)
def _hermetic_allocation(monkeypatch):
    monkeypatch.setattr(AS, 'get_allocation', lambda *a, **k: _UNLOADED)


def _run(state, mod=W):
    """跑一次 v1 今日作戰室（`render_section_warroom('bull', True, False)`）；回 ([(種類, 文字)], fake)。"""
    fake = _FakeST(state)
    saved, mod.st = mod.st, fake
    try:
        mod.render_section_warroom('bull', True, False)
    finally:
        mod.st = saved
    return [(k, t) for k, t in fake.out], fake


def _out(state, mod=W):
    return _run(state, mod)[0]


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode('utf-8')).hexdigest()


def _hint(out) -> list:
    """「📐 年線位階參考：」後面那整段字串（每次出現一筆）。"""
    return re.findall(r'📐 年線位階參考：([^<]*)', '\n'.join(t for _k, t in out))


def _undo(out, pairs):
    for new, old in pairs:
        out = [(k, t.replace(new, old)) for k, t in out]
    return out


# ══════════════════════════════════════════════════════════════════════════
# 修前 golden（基底 84c1ca4 實跑；⛔ 不讀 git）
# ══════════════════════════════════════════════════════════════════════════
#: 整個作戰室輸出的 sha256。同一個值代表輸出逐字相同。
_D_BULL = '353d20727c06e794815cf60e3fd0fdcbd9ef26690b62cb99c01a5cdcb4539367'          # 乖離 +5.3%、無避險
_D_BULL_HEDGE = '419b4c56151b6dda6fce1a1066b97c99268e0a038bf32756596600b04f71b124'    # 同上＋避險（修前只有舊 key 走得到）
_D_NO_HINT = 'dff46aeb62fd42156c4f40181be5c8fecc15a2a1603dc9ee9e4a060e81dd8430'       # 整行「📐」不出
_D_ONLY_HEDGE = '1439a4c7e1acb148e2721b7dd25a28c45735a684f819a98d061d92108bfb5311'    # 價缺、只剩避險（修前只有舊 key）
_D_ZERO = '6c1b1934f4a4154b2b3c548a2f9abe3623c9c07862b0b55274a7b69b0c12b620'          # 乖離 +0.0%
_D_NEGZERO = 'fc75b76426a44f1be0c132cee3476b80b8fbef83f5ea9564bdd946647b7dce26'       # 乖離 -0.0%（修前）
_D_M01 = '7e07f1f89608afead953d27a04295d07bfb6c058754aaed414abde4ced677789'           # 乖離 -0.1%
_D_P01 = 'd91c02cede7806da8dcf356452b88684f12be5d0e634fec4396640bba641b711'           # 乖離 +0.1%

_BASE = {
    'b-est-19999.99': 'c549cea04ceff4552d4eefd64d019fd0a99c8d37bd9706c97de6706ba2f6af52',
    'b-legacy-hedge-19999.99': '11d4853478eb03c27a9171dcafd65227778627e7c653d59dce770c495474ef48',
    'b-full-card': 'c8f02d8a51474db6f4ec7d8d45c661b5eca842bcaba5a0d38c1551745fd431c2',
    'full': 'c3470fc9710a5e37b04c0df650fa95d5faf6792da7ad6f0ef39d5c36e24d8820',
    'below-ma': 'c8780f5fc630d854ba19d66211fc10a95f8aecfffbd2ea71a363a2cfbaf0bc7f',
    'below-ma-25': '842dbb1f7b1377982e1072b2a7110e355ddda9138aa3adb1a26f1171fb31d4cd',
    'ints': 'e90b9875a1bc560c1e356b66afb1b4585f74a9860f610f3aca27bb23d5766100',
    'numpy': '25681675b2d2613fa54a6e4271935880924d0dde57273d2889d2b482df57701b',
    'estimated': 'b6a0cdc3ea8e493291196ffa76a5957062e405cd837a096445022cc3fc7bc730',
    'zero-1day-est': 'ea894dfec43f93de4dd11455ecec2dcbd68994013f9990ea939bfdd4a297764e',
    'no-data': '8f91ced9b4d60c3a8b87398b2c8f546c07a4b08a03ba3f00e5f1b7233ba44bd6',
}

#: 行動建議卡（第 2 個 st.markdown）完整字面值；`{}` ＝「📐 年線位階參考」那一行（含外框 div），無則空字串。
_CARD = ('<div style="background:#0a2818;border-left:5px solid #22c55e;border-radius:0 10px 10px 0;'
         'padding:14px 18px;margin:8px 0;"><div style="font-size:11px;color:#484f58;margin-bottom:4px;">'
         '📌 今日唯一行動建議</div><div style="font-size:17px;font-weight:900;color:#22c55e;">'
         '🟢 趨勢偏多 — 可逢回布局核心部位</div>{}</div>')
_HINT_DIV = '<div style="font-size:11px;color:#8b949e;margin-top:4px;">📐 年線位階參考：{}</div>'

# ══════════════════════════════════════════════════════════════════════════
# 情境
# ══════════════════════════════════════════════════════════════════════════
_BULL = {'price': 20000.0, 'ma240': 19000.0}       # 年線乖離 +5.3%
_PXMISS = {'ma240': 16000.0}                       # 價缺 → 不列三個位階片段


def _S(bias, wr=..., legacy=...):
    """`wr` ＝ warroom_summary（`...` ＝ 不放這個 key）；`legacy` ＝ 舊 session key `futures_net`（同上）。"""
    st = {'bias_info': bias, 'cl_data': {'margin': 2000.0}}
    if wr is not ...:
        st['warroom_summary'] = wr
    if legacy is not ...:
        st['futures_net'] = legacy
    return st


_H = '年線乖離 +5.3%'
_HH = '年線乖離 +5.3%｜外資期貨避險'
_UNDO_HEDGE = (('｜外資期貨避險', ''),)
_UNDO_ONLY_HEDGE = ((_HINT_DIV.format('外資期貨避險'), ''),)

#: (id, state, 修後「📐」那一行, 修前 golden digest, undo)
#:   修前 golden：修前同一個 state 的整段輸出；undo：把修後輸出換回修前寫法的唯一替換。
#:   修前一律不讀 warroom_summary ⇒ 經 warroom_summary 餵的各例修前都是「無避險」那份。
_FUT_CASES = [
    # ── 有限值、−30000 上下界（引擎 `< -30000`，嚴格小於）──────────────────────────
    ('wr-m40000', _S(_BULL, {'futures_net': -40000.0}), [_HH], _D_BULL, _UNDO_HEDGE),
    ('wr-m30000', _S(_BULL, {'futures_net': -30000.0}), [_H], _D_BULL, ()),
    ('wr-m30000-int', _S(_BULL, {'futures_net': -30000}), [_H], _D_BULL, ()),
    ('wr-below-30000', _S(_BULL, {'futures_net': math.nextafter(-30000.0, -math.inf)}), [_HH], _D_BULL,
     _UNDO_HEDGE),
    ('wr-above-30000', _S(_BULL, {'futures_net': math.nextafter(-30000.0, math.inf)}), [_H], _D_BULL, ()),
    ('wr-m30000.01', _S(_BULL, {'futures_net': -30000.01}), [_HH], _D_BULL, _UNDO_HEDGE),
    ('wr-m30001', _S(_BULL, {'futures_net': -30001.0}), [_HH], _D_BULL, _UNDO_HEDGE),
    ('wr-m29999', _S(_BULL, {'futures_net': -29999.0}), [_H], _D_BULL, ()),
    ('wr-zero', _S(_BULL, {'futures_net': 0.0}), [_H], _D_BULL, ()),
    ('wr-negzero', _S(_BULL, {'futures_net': -0.0}), [_H], _D_BULL, ()),
    ('wr-p40000', _S(_BULL, {'futures_net': 40000.0}), [_H], _D_BULL, ()),
    ('wr-int', _S(_BULL, {'futures_net': -40000}), [_HH], _D_BULL, _UNDO_HEDGE),
    ('wr-np-float', _S(_BULL, {'futures_net': np.float64(-40000.0)}), [_HH], _D_BULL, _UNDO_HEDGE),
    ('wr-np-int', _S(_BULL, {'futures_net': np.int64(-40000)}), [_HH], _D_BULL, _UNDO_HEDGE),
    ('wr-decimal', _S(_BULL, {'futures_net': Decimal('-40000')}), [_HH], _D_BULL, _UNDO_HEDGE),
    # ── 缺值：缺鍵／None／warroom_summary 不在或為空 ⇒ 視同沒有 ───────────────────
    ('wr-none', _S(_BULL, {'futures_net': None}), [_H], _D_BULL, ()),
    ('wr-key-missing', _S(_BULL, {'health_score': 60.0}), [_H], _D_BULL, ()),
    ('wr-empty', _S(_BULL, {}), [_H], _D_BULL, ()),
    ('wr-absent', _S(_BULL), [_H], _D_BULL, ()),
    ('wr-is-None', _S(_BULL, None), [_H], _D_BULL, ()),
    # ── 非有限 ⇒ 視同沒有（−inf 照送引擎會成立避險 —— 必須擋）──────────────────────
    ('wr-nan', _S(_BULL, {'futures_net': math.nan}), [_H], _D_BULL, ()),
    ('wr-pinf', _S(_BULL, {'futures_net': math.inf}), [_H], _D_BULL, ()),
    ('wr-ninf', _S(_BULL, {'futures_net': -math.inf}), [_H], _D_BULL, ()),
    ('wr-np-ninf', _S(_BULL, {'futures_net': np.float64(-np.inf)}), [_H], _D_BULL, ()),
    ('wr-decimal-ninf', _S(_BULL, {'futures_net': Decimal('-Infinity')}), [_H], _D_BULL, ()),
    # ── 非數值 ⇒ 視同沒有（字串照送引擎會在比較時拋 TypeError、整個作戰室崩潰）─────────
    ('wr-str', _S(_BULL, {'futures_net': '-40000'}), [_H], _D_BULL, ()),
    ('wr-bool', _S(_BULL, {'futures_net': True}), [_H], _D_BULL, ()),
    ('wr-np-bool', _S(_BULL, {'futures_net': np.True_}), [_H], _D_BULL, ()),
    ('wr-np-complex', _S(_BULL, {'futures_net': np.complex128(-40000)}), [_H], _D_BULL, ()),
    ('wr-np-complex-imag', _S(_BULL, {'futures_net': np.complex128(-40000 + 1j)}), [_H], _D_BULL, ()),
    ('wr-complex', _S(_BULL, {'futures_net': complex(-40000, 0)}), [_H], _D_BULL, ()),
    ('wr-huge-int', _S(_BULL, {'futures_net': -10 ** 400}), [_H], _D_BULL, ()),
    ('wr-pd-na', _S(_BULL, {'futures_net': pd.NA}), [_H], _D_BULL, ()),
    ('wr-list', _S(_BULL, {'futures_net': [-40000.0]}), [_H], _D_BULL, ()),
    # ── 價缺：三個位階片段不列，只剩與價格無關的避險片段 ─────────────────────────────
    ('pxmiss-wr-m40000', _S(_PXMISS, {'futures_net': -40000.0}), ['外資期貨避險'], _D_NO_HINT,
     _UNDO_ONLY_HEDGE),
    ('pxmiss-wr-ninf', _S(_PXMISS, {'futures_net': -math.inf}), [], _D_NO_HINT, ()),
    ('pxmiss-wr-none', _S(_PXMISS, {'futures_net': None}), [], _D_NO_HINT, ()),
    # ── 舊 session key（全 repo 0 寫入點）：修後不再讀 ────────────────────────────────
    ('legacy-m40000', _S(_BULL, legacy=-40000), [_H], _D_BULL_HEDGE, (('年線乖離 +5.3%', _HH),)),
    ('legacy-m40000-wr-zero', _S(_BULL, {'futures_net': 0.0}, legacy=-40000), [_H], _D_BULL_HEDGE,
     (('年線乖離 +5.3%', _HH),)),
    ('legacy-zero-wr-m40000', _S(_BULL, {'futures_net': -40000.0}, legacy=0), [_HH], _D_BULL, _UNDO_HEDGE),
    ('pxmiss-legacy-m40000', _S(_PXMISS, legacy=-40000), [], _D_ONLY_HEDGE,
     (('🟢 趨勢偏多 — 可逢回布局核心部位</div></div>',
       '🟢 趨勢偏多 — 可逢回布局核心部位</div>' + _HINT_DIV.format('外資期貨避險') + '</div>'),)),
]

#: 修前（基底 84c1ca4）同一 state 的「📐」那一行。
_BASE_HINT = {
    **{_c[0]: [_H] for _c in _FUT_CASES if _c[1]['bias_info'] is _BULL},
    'pxmiss-wr-m40000': [], 'pxmiss-wr-ninf': [], 'pxmiss-wr-none': [],
    'legacy-m40000': [_HH], 'legacy-m40000-wr-zero': [_HH], 'pxmiss-legacy-m40000': ['外資期貨避險'],
}

_EST = {'is_estimated': True, 'data_days': 120}
_NZ = (('年線乖離 +0.0%', '年線乖離 -0.0%'),)

#: (id, state, 修後「📐」那一行, 修前「📐」那一行, 修前 golden digest, undo)
_BIAS_CASES = [
    # ── 改：格式化為「-0.0」者 ─────────────────────────────────────────────────────
    ('b-19999.99', _S({'price': 19999.99, 'ma240': 20000.0}), ['年線乖離 +0.0%'], ['年線乖離 -0.0%'],
     _D_NEGZERO, _NZ),
    ('b-19992', _S({'price': 19992.0, 'ma240': 20000.0}), ['年線乖離 +0.0%'], ['年線乖離 -0.0%'],
     _D_NEGZERO, _NZ),                                                 # 乖離 −0.04 → `:+.1f` 也是 -0.0
    ('b-19999', _S({'price': 19999, 'ma240': 20000}), ['年線乖離 +0.0%'], ['年線乖離 -0.0%'],
     _D_NEGZERO, _NZ),
    ('b-tiny-neg', _S({'price': 19999.999999, 'ma240': 20000.0}), ['年線乖離 +0.0%'], ['年線乖離 -0.0%'],
     _D_NEGZERO, _NZ),
    ('b-est-19999.99', _S({'price': 19999.99, 'ma240': 20000.0, **_EST}), ['年線乖離 +0.0%（估算）'],
     ['年線乖離 -0.0%（估算）'], _BASE['b-est-19999.99'], _NZ),
    ('b-np-19999.99', _S({'price': np.float64(19999.99), 'ma240': np.float64(20000.0)}), ['年線乖離 +0.0%'],
     ['年線乖離 -0.0%'], _D_NEGZERO, _NZ),
    ('b-dec-19999.99', _S({'price': Decimal('19999.99'), 'ma240': 20000}), ['年線乖離 +0.0%'],
     ['年線乖離 -0.0%'], _D_NEGZERO, _NZ),
    ('b-full-card', _S({'price': 19999.99, 'ma240': 20000.0, 'bias_240': 0.0, 'bias_20': -0.1, 'bias_60': 0.0,
                        'data_days': 300, 'is_estimated': False}), ['年線乖離 +0.0%'], ['年線乖離 -0.0%'],
     _BASE['b-full-card'], _NZ),
    # 與避險片段並存：修前經 warroom_summary 餵的避險不出（C7-n9）、乖離印 -0.0（Z3-n10）—— 兩處都改
    ('b-hedge-19999.99', _S({'price': 19999.99, 'ma240': 20000.0}, {'futures_net': -40000.0}),
     ['年線乖離 +0.0%｜外資期貨避險'], ['年線乖離 -0.0%'], _D_NEGZERO,
     (('年線乖離 +0.0%｜外資期貨避險', '年線乖離 -0.0%'),)),
    ('b-legacy-hedge-19999.99', _S({'price': 19999.99, 'ma240': 20000.0}, legacy=-40000), ['年線乖離 +0.0%'],
     ['年線乖離 -0.0%｜外資期貨避險'], _BASE['b-legacy-hedge-19999.99'],
     (('年線乖離 +0.0%', '年線乖離 -0.0%｜外資期貨避險'),)),
    # ── 不改：其餘值逐字不變（含 ±0.1 與真 0）──────────────────────────────────────
    ('b-19990.02', _S({'price': 19990.02, 'ma240': 20000.0}), ['年線乖離 -0.1%'], ['年線乖離 -0.1%'],
     _D_M01, ()),
    ('b-19990', _S({'price': 19990.0, 'ma240': 20000.0}), ['年線乖離 -0.1%'], ['年線乖離 -0.1%'], _D_M01, ()),
    ('b-eq', _S({'price': 20000.0, 'ma240': 20000.0}), ['年線乖離 +0.0%'], ['年線乖離 +0.0%'], _D_ZERO, ()),
    ('b-20001', _S({'price': 20001.0, 'ma240': 20000.0}), ['年線乖離 +0.0%'], ['年線乖離 +0.0%'], _D_ZERO, ()),
    ('b-20009.98', _S({'price': 20009.98, 'ma240': 20000.0}), ['年線乖離 +0.1%'], ['年線乖離 +0.1%'],
     _D_P01, ()),
    # numpy：引擎的 round 走 numpy（非正確捨入）—— 乖離 0.05 修前印 +0.1，修後必須照舊
    ('b-np-20010', _S({'price': np.float64(20010.0), 'ma240': np.float64(20000.0)}), ['年線乖離 +0.1%'],
     ['年線乖離 +0.1%'], _D_P01, ()),
    ('b-np-19990', _S({'price': np.float64(19990.0), 'ma240': np.float64(20000.0)}), ['年線乖離 -0.1%'],
     ['年線乖離 -0.1%'], _D_M01, ()),
]

_BIAS_BY_ID = {_c[0]: _c for _c in _BIAS_CASES}

#: 與本批無關的形狀（批 Z3 `_WR_SAME`／`_WR_V4_GOLDEN` 的代表形狀，不帶期貨）：(id, state, 修前「📐」, digest)
_SAME_CASES = [
    ('empty', _S({}), [], _D_NO_HINT),
    ('keys-missing', _S({'is_estimated': False}), [], _D_NO_HINT),
    ('none', _S({'price': None, 'ma240': None}), [], _D_NO_HINT),
    ('nan', _S({'price': math.nan, 'ma240': math.nan}), [], _D_NO_HINT),
    ('price-inf', _S({'price': math.inf, 'ma240': 1.0}), [], _D_NO_HINT),
    ('price-zero', _S({'price': 0.0, 'ma240': 16000.0}), [], _D_NO_HINT),
    ('ma-missing', _S({'price': 20000.0}), [], _D_NO_HINT),
    ('bool', _S({'price': True, 'ma240': True}), [], _D_NO_HINT),
    ('full', _S({'bias_240': 25.0, 'bias_20': 12.0, 'price': 20000.0, 'ma240': 16000.0, 'data_days': 300,
                 'is_estimated': False}), ['年線乖離 +25.0%｜乖離過熱'], _BASE['full']),
    ('below-ma', _S({'price': 15000.0, 'ma240': 16000.0, 'bias_240': -6.3}), ['年線乖離 -6.2%｜股價在年線下'],
     _BASE['below-ma']),
    ('below-ma-25', _S({'price': 15000.0, 'ma240': 20000.0, 'bias_240': -25.0}),
     ['年線乖離 -25.0%｜股價在年線下'], _BASE['below-ma-25']),
    ('at-ma', _S({'price': 16000.0, 'ma240': 16000.0}), ['年線乖離 +0.0%'], _D_ZERO),
    ('ints', _S({'price': 20000, 'ma240': 16000}), ['年線乖離 +25.0%｜乖離過熱'], _BASE['ints']),
    ('numpy', _S({'price': np.float64(25000.0), 'ma240': np.float64(19000.0)}), ['年線乖離 +31.6%｜乖離過熱'],
     _BASE['numpy']),
    ('estimated', _S({'price': 20000.0, 'ma240': 16000.0, 'is_estimated': True, 'data_days': 120}),
     ['年線乖離 +25.0%（估算）｜乖離過熱'], _BASE['estimated']),
    ('zero-1day-est', _S({'price': 16500.0, 'ma240': 16500.0, 'bias_240': 0.0, 'bias_20': 0.0, 'data_days': 1,
                          'is_estimated': True}), ['年線乖離 +0.0%（估算）'], _BASE['zero-1day-est']),
    ('bull', _S(_BULL), [_H], _D_BULL),
    ('pxmiss', _S(_PXMISS), [], _D_NO_HINT),
    ('no-data', {'bias_info': _BULL}, [], _BASE['no-data']),                    # 無 cl_data／mkt_info → 空狀態
]


def _ids(cases):
    return [c[0] for c in cases]


# ══════════════════════════════════════════════════════════════════════════
# 還原體（修前碼）：把本批兩處改動換回基底 84c1ca4 的寫法（只動程式行）
# ══════════════════════════════════════════════════════════════════════════
_WR_SRC = open(W.__file__, encoding='utf-8').read()

_REVERT_FUT = (
    "    _wr_sum = _wr_inp.warroom_summary\n"
    "    _wr_fut_raw = _wr_sum.get('futures_net') if isinstance(_wr_sum, dict) else None\n"
    "    _wr_fut_net = (None if isinstance(_wr_fut_raw, (np.bool_, complex, np.complexfloating))\n"
    "                   else _finite_yoy(_wr_sum, 'futures_net'))\n",
    "    _wr_fut_net = _wr_inp.futures_net\n")
_REVERT_NEGZERO = (
    "            _wr_b240_txt = f'{_v4[\"Bias_240\"]:+.1f}'\n"
    "            if _wr_b240_txt == '-0.0':\n"
    "                _wr_b240_txt = '+0.0'\n"
    "            _v4_bits.append(f'年線乖離 {_wr_b240_txt}%{_wr_bias_badge}')\n",
    "            _v4_bits.append(f'年線乖離 {_v4[\"Bias_240\"]:+.1f}%{_wr_bias_badge}')\n")


def _variant(pairs, tag):
    """把一份改過的 section_warroom 原始碼載成獨立模組（不進 sys.modules、不碰本尊）。"""
    code = _WR_SRC
    for old, new in pairs:
        assert code.count(old) == 1, f'替換點不唯一或已不存在：{old!r}'
        code = code.replace(old, new)
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(f'_z6_wr_{tag}', loader=None))
    m.__file__ = W.__file__
    exec(compile(code, W.__file__, 'exec'), m.__dict__)
    return m


@functools.lru_cache(maxsize=None)
def _pre():
    """還原體（延遲建立：還原點若不存在，只有用到它的測試失敗，其餘行為斷言照跑）。"""
    return _variant((_REVERT_FUT, _REVERT_NEGZERO), 'pre')


class TestRevertedCopyIsTheBase:
    """前提：還原體在本檔每個情境都重現基底 84c1ca4 的 golden —— 本批對這支檔的行為改動只有這兩處。"""

    @pytest.mark.parametrize('case', _FUT_CASES, ids=_ids(_FUT_CASES))
    def test_fut(self, case):
        _id, state, _post, base_d, _u = case
        out = _out(state, _pre())
        assert _digest(out) == base_d and _hint(out) == _BASE_HINT[_id]

    @pytest.mark.parametrize('case', _BIAS_CASES, ids=_ids(_BIAS_CASES))
    def test_bias(self, case):
        _id, state, _post, base_hint, base_d, _u = case
        out = _out(state, _pre())
        assert _digest(out) == base_d and _hint(out) == base_hint

    @pytest.mark.parametrize('case', _SAME_CASES, ids=_ids(_SAME_CASES))
    def test_same(self, case):
        _id, state, base_hint, base_d = case
        out = _out(state, _pre())
        assert _digest(out) == base_d and _hint(out) == base_hint


# ══════════════════════════════════════════════════════════════════════════
# C7-n9：外資期貨避險片段改讀 warroom_summary['futures_net']（＋有限值檢查）
# ══════════════════════════════════════════════════════════════════════════
class TestC7n9FuturesHedgingFragment:
    @pytest.mark.parametrize('case', _FUT_CASES, ids=_ids(_FUT_CASES))
    def test_hint_line(self, case):
        _id, state, post_hint, _d, _u = case
        assert _hint(_out(state)) == post_hint

    @pytest.mark.parametrize('case', _FUT_CASES, ids=_ids(_FUT_CASES))
    def test_only_the_fragment_differs_from_base(self, case):
        """修後輸出經 `undo`（唯一預期的改變換回修前寫法）後，整段與基底 golden 逐字相同。"""
        _id, state, _p, base_d, undo = case
        out = _out(state)
        assert _digest(_undo(out, undo)) == base_d
        if undo:
            assert _digest(out) != base_d          # 真的有改（不是 undo 空轉）

    @pytest.mark.parametrize('case', [c for c in _FUT_CASES if c[2] in ([_HH], ['外資期貨避險'])],
                             ids=_ids([c for c in _FUT_CASES if c[2] in ([_HH], ['外資期貨避險'])]))
    def test_fragment_output_equals_base_designed_output(self, case):
        """避險成立時，整個作戰室輸出＝基底在舊 key 有同一個值時本來就設計好的那份（逐字）。"""
        _id, state, post_hint, _d, _u = case
        want = _D_BULL_HEDGE if post_hint == [_HH] else _D_ONLY_HEDGE
        assert _digest(_out(state)) == want

    @pytest.mark.parametrize('fut,hint', [
        (-40000.0, _HINT_DIV.format(_HH)),
        (-30000.0, _HINT_DIV.format(_H)),
        (None, _HINT_DIV.format(_H)),
        (-math.inf, _HINT_DIV.format(_H)),
    ], ids=['m40000', 'm30000', 'none', 'ninf'])
    def test_action_card_literal(self, fut, hint):
        out = _out(_S(_BULL, {'futures_net': fut}))
        assert out[1] == ('markdown', _CARD.format(hint))

    def test_action_card_literal_price_missing(self):
        assert _out(_S(_PXMISS, {'futures_net': -40000.0}))[1] == (
            'markdown', _CARD.format(_HINT_DIV.format('外資期貨避險')))
        assert _out(_S(_PXMISS, {'futures_net': math.nan}))[1] == ('markdown', _CARD.format(''))

    @pytest.mark.parametrize('state', [
        _S(_BULL, {'futures_net': -40000.0}), _S(_BULL, {'futures_net': -math.inf}), _S(_BULL, legacy=-40000),
        _S(_BULL, {'futures_net': '-40000'}), _S(_BULL)],
        ids=['wr-m40000', 'wr-ninf', 'legacy-m40000', 'wr-str', 'wr-absent'])
    def test_warroom_writes_no_session_key(self, state):
        """⛔ 補寫 session_state['futures_net']：作戰室跑完後 session 的 key 與值一個都沒變。"""
        before = {k: v for k, v in state.items()}
        _o, fake = _run(state)
        assert set(fake.session_state) == set(before)
        assert ('futures_net' in fake.session_state) == ('futures_net' in before)
        for k, v in before.items():
            assert fake.session_state[k] is v

    def test_random_values_fragment_iff_finite_and_below_minus_30000(self):
        """隨機外資期貨值（含 −30000 附近）：片段出現 ⟺ 有限實數且 < −30000；拿掉片段後與修前「沒有期貨」逐字相同。"""
        rng = random.Random(20261005)
        base_no_fut = _D_BULL                               # 基底「沒有期貨」那份（golden）
        vals = [rng.uniform(-60000, 60000) for _ in range(120)]
        vals += [-30000.0 + rng.uniform(-1, 1) for _ in range(60)]
        vals += [math.nextafter(-30000.0, -math.inf), -30000.0, math.nextafter(-30000.0, math.inf),
                 -1e300, 1e300, -5e-324, math.nan, math.inf, -math.inf, None]
        hits = 0
        for v in vals:
            out = _out(_S(_BULL, {'futures_net': v}))
            want = v is not None and math.isfinite(v) and v < -30000
            hits += want
            assert _hint(out) == ([_HH] if want else [_H]), v
            assert _digest(_undo(out, _UNDO_HEDGE)) == base_no_fut, v
        assert hits >= 40                                   # 真的走到「成立」那一枝

    def test_e2e_traffic_light_producer_to_warroom(self, monkeypatch):
        """真上游：`render_traffic_light_top`（calc_traffic_light → warroom_summary）先寫、作戰室後讀。"""
        import src.ui.tabs.macro.handlers as H
        import src.ui.tabs.macro.section_traffic_light as TL

        def _e2e(fut, mod):
            state = {'cl_ts': _dt.datetime.now().strftime('%Y-%m-%d %H:%M'),      # 30 分鐘內 ⇒ 快取新鮮
                     'mkt_info': {'score': 3.0, 'regime': 'bull', 'max_score': 4.0},
                     'jingqi_info': {'avg': 55.0},
                     'cl_data': {'inst': {'外資': {'net': 12.5}}, 'adl': pd.DataFrame({'ad_ratio': [50.0]}),
                                 'margin': 2000.0},
                     'li_latest': pd.DataFrame({'外資大小': [fut], '韭菜指數': [10.0]}),
                     'bias_info': dict(_BULL)}
            fake = _FakeST(state)
            with monkeypatch.context() as m:
                m.setattr(TL, 'st', fake)
                m.setattr(H, 'st', fake)
                m.setattr(mod, 'st', fake)
                _ph, show, reg = TL.render_traffic_light_top()
                assert show is True
                n0 = len(fake.out)
                mod.render_section_warroom(reg, show, False)
            return fake, _hint(fake.out[n0:])

        fake, hint = _e2e(-40000.0, W)
        assert fake.session_state['warroom_summary']['futures_net'] == -40000.0
        assert 'futures_net' not in fake.session_state                     # 上游也沒寫舊 key
        assert hint == [_HH]
        assert _e2e(-30000.0, W)[1] == [_H]
        assert _e2e(math.nan, W)[1] == [_H]                                 # 上游 _safe_float → None
        # 拔掉修復（還原體）：同一份上游輸出，片段出不來 —— 即本列的錯誤
        assert _e2e(-40000.0, _pre())[1] == [_H]


class TestC7n9WhyTheFiniteCheck:
    """前提：不做有限值檢查、直接把 warroom_summary 的值送進引擎會怎樣（說明守衛不是多餘的）。"""

    def test_engine_accepts_minus_inf_as_hedging(self):
        assert _V4(20000.0, 19000.0, -math.inf)['Is_Foreign_Hedging'] is True
        assert _V4(20000.0, 19000.0, None)['Is_Foreign_Hedging'] is False

    def test_engine_raises_on_str(self):
        with pytest.raises(TypeError):
            _V4(20000.0, 19000.0, '-40000')

    def test_finite_yoy_alone_lets_numpy_complex_through(self):
        """`_finite_yoy` 只排除 Python bool：numpy complex 經 `math.isfinite` 丟掉虛部放行、引擎再判成避險。"""
        from src.ui.tabs.macro.section_long import _finite_yoy
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            z = _finite_yoy({'f': np.complex128(-40000 + 1j)}, 'f')
            assert z is not None and isinstance(z, np.complexfloating)
            assert bool(_V4(20000.0, 19000.0, z)['Is_Foreign_Hedging']) is True
            only_finite_yoy = _variant(((
                "    _wr_fut_net = (None if isinstance(_wr_fut_raw, (np.bool_, complex, np.complexfloating))\n"
                "                   else _finite_yoy(_wr_sum, 'futures_net'))\n",
                "    _wr_fut_net = _finite_yoy(_wr_sum, 'futures_net')\n"),), 'only_finite_yoy')
            assert _hint(_out(_S(_BULL, {'futures_net': np.complex128(-40000 + 1j)}), only_finite_yoy)) == [_HH]
            assert _hint(_out(_S(_BULL, {'futures_net': np.complex128(-40000 + 1j)}))) == [_H]

    def test_naive_read_without_check_breaks(self):
        naive = _variant(((
            "    _wr_fut_net = (None if isinstance(_wr_fut_raw, (np.bool_, complex, np.complexfloating))\n"
            "                   else _finite_yoy(_wr_sum, 'futures_net'))\n",
            "    _wr_fut_net = _wr_fut_raw\n"),), 'naive')
        assert _hint(_out(_S(_BULL, {'futures_net': -math.inf}), naive)) == [_HH]      # 假避險
        with pytest.raises(TypeError):
            _out(_S(_BULL, {'futures_net': '-40000'}), naive)                           # 整個作戰室崩潰
        assert _hint(_out(_S(_BULL, {'futures_net': -math.inf}))) == [_H]
        assert _hint(_out(_S(_BULL, {'futures_net': '-40000'}))) == [_H]


# ══════════════════════════════════════════════════════════════════════════
# Z3-n10：「年線乖離 -0.0%」→「+0.0%」，其餘值逐字不變
# ══════════════════════════════════════════════════════════════════════════
class TestZ3n10NegativeZeroBias:
    @pytest.mark.parametrize('case', _BIAS_CASES, ids=_ids(_BIAS_CASES))
    def test_hint_line(self, case):
        _id, state, post_hint, _bh, _d, _u = case
        out = _out(state)
        assert _hint(out) == post_hint
        assert '-0.0%' not in '\n'.join(t for _k, t in out)

    @pytest.mark.parametrize('case', _BIAS_CASES, ids=_ids(_BIAS_CASES))
    def test_only_the_sign_differs_from_base(self, case):
        _id, state, _p, _bh, base_d, undo = case
        out = _out(state)
        assert _digest(_undo(out, undo)) == base_d
        if undo:
            assert _digest(out) != base_d

    @pytest.mark.parametrize('state', [_S({'price': 19999.99, 'ma240': 20000.0}),
                                       _S({'price': 19992.0, 'ma240': 20000.0}),
                                       _S({'price': np.float64(19999.99), 'ma240': np.float64(20000.0)}),
                                       _S({'price': Decimal('19999.99'), 'ma240': 20000})],
                             ids=['19999.99', '19992', 'numpy', 'decimal'])
    def test_negzero_output_equals_exact_zero_output(self, state):
        """負零改印後，整個作戰室輸出＝基底「價＝年線」（真 0）那份，逐字。"""
        assert _digest(_out(state)) == _D_ZERO

    def test_card_and_hint_same_sign(self):
        """同頁兩處：「年線位置」卡（上游已正規化）與「📐 年線位階參考」同為 +0.0%（修前一正一負）。"""
        state = _BIAS_BY_ID['b-full-card'][1]
        joined = '\n'.join(t for _k, t in _out(state))
        assert '乖離+0.0%' in joined and _HINT_DIV.format('年線乖離 +0.0%') in joined
        assert '-0.0' not in joined
        pre = '\n'.join(t for _k, t in _out(state, _pre()))
        assert '乖離+0.0%' in pre and _HINT_DIV.format('年線乖離 -0.0%') in pre

    def test_random_near_ma_only_negzero_changes(self):
        """價在年線附近隨機取樣：修後＝修前把「年線乖離 -0.0%」換成「+0.0%」，其餘逐字相同。"""
        rng = random.Random(10005)
        hits = 0
        for i in range(400):
            ma = rng.uniform(1000.0, 30000.0)
            d = rng.choice((rng.uniform(-6e-4, 6e-4), rng.uniform(-0.3, 0.3), rng.uniform(-1e-9, 1e-9)))
            px = ma * (1 + d)
            if i % 3 == 0:
                px, ma = np.float64(px), np.float64(ma)
            state = _S({'price': px, 'ma240': ma})
            pre = _out(state, _pre())
            post = _out(state)
            hits += any('年線乖離 -0.0%' in t for _k, t in pre)
            assert post == [(k, t.replace('年線乖離 -0.0%', '年線乖離 +0.0%')) for k, t in pre], (px, ma)
            assert not any('-0.0%' in t for _k, t in post), (px, ma)
        assert hits >= 50                                   # 真的走到「-0.0」那一枝

    def test_random_near_ma_display_matches_engine(self):
        """（不靠還原體）「📐」第一段＝引擎 `Bias_240` 以 `:+.1f` 格式化，唯「-0.0」改印「+0.0」。"""
        rng = random.Random(777)
        hits = 0
        for i in range(300):
            ma = rng.uniform(1000.0, 30000.0)
            px = ma * (1 + rng.uniform(-6e-4, 6e-4))
            if i % 2:
                px, ma = np.float64(px), np.float64(ma)
            raw = f'{_V4(px, ma, None)["Bias_240"]:+.1f}'
            hits += raw == '-0.0'
            want = '+0.0' if raw == '-0.0' else raw
            assert _hint(_out(_S({'price': px, 'ma240': ma})))[0].split('｜')[0] == f'年線乖離 {want}%', (px, ma)
        assert hits >= 50


class TestZ3n10WhyNotRoundPlusZero:
    """前提：規格舉例的 `round(x, 1) + 0.0` 會動到其他值的顯示 —— 本批改用「格式化結果是 -0.0 才換」。"""

    def test_numpy_round_is_not_the_display_rounding(self):
        b = _V4(np.float64(20010.0), np.float64(20000.0), None)['Bias_240']
        assert isinstance(b, np.floating) and f'{b:+.1f}' == '+0.1'
        assert f'{round(b, 1) + 0.0:+.1f}' == '+0.0'           # 換成 round 版會把 +0.1% 印成 +0.0%

    def test_decimal_plus_float_raises(self):
        b = _V4(Decimal('19999.99'), 20000, None)['Bias_240']
        assert isinstance(b, Decimal) and f'{b:+.1f}' == '-0.0'
        with pytest.raises(TypeError):
            round(b, 1) + 0.0                                    # 換成 round 版：修前不崩的輸入改崩

    def test_round_variant_would_fail_the_unchanged_cases(self):
        rnd = _variant(((
            "            _wr_b240_txt = f'{_v4[\"Bias_240\"]:+.1f}'\n"
            "            if _wr_b240_txt == '-0.0':\n"
            "                _wr_b240_txt = '+0.0'\n",
            "            _wr_b240_txt = f'{round(_v4[\"Bias_240\"], 1) + 0.0:+.1f}'\n"),), 'round')
        assert _hint(_out(_S({'price': np.float64(20010.0), 'ma240': np.float64(20000.0)}), rnd)) == [
            '年線乖離 +0.0%']                                      # 基底與修後皆 +0.1%
        with pytest.raises(TypeError):
            _out(_S({'price': Decimal('19999.99'), 'ma240': 20000}), rnd)


# ══════════════════════════════════════════════════════════════════════════
# 與本批無關的形狀：整段輸出與基底逐字相同
# ══════════════════════════════════════════════════════════════════════════
class TestUnrelatedShapesIdenticalToBase:
    @pytest.mark.parametrize('case', _SAME_CASES, ids=_ids(_SAME_CASES))
    def test_identical(self, case):
        _id, state, base_hint, base_d = case
        out = _out(state)
        assert _hint(out) == base_hint
        assert _digest(out) == base_d

    def test_bull_card_literal(self):
        assert _out(_S(_BULL))[1] == ('markdown', _CARD.format(_HINT_DIV.format(_H)))
