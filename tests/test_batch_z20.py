"""批 Z20（優先 1 可自主·可即派）—— C9-n2 (b) ＋ Z10-n2 ＋ Z6-n4 釘子（基底 origin/main `0482ebd5`）。

- C9-n2 (b)（L5 `section_chips.py` §三 進階警示「（≥3萬口門檻）」、綜合判斷「（達3萬危險線）」；
  `section_state.py` §二 拐點「≥ 3萬口 → 頂部起跌訊號」）：「3萬」改由 SSOT
  `FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD` 插值（`/ 10_000:g`）；30000 時逐字不變（既有 test_batch_z10 釘住）。
- Z10-n2（`section_chips.py` §三 外資期貨快速結論卡）：PCR 末列 None 時 `float(None)` 拋 TypeError
  （§三 後段不渲染）、NaN 印「| PCR nan」⇒ 改走 `_finite_yoy`，缺／非有限走既有「不印 PCR」分支；有限值逐字不變。
- Z6-n4（`section_warroom.py` 作戰室「📐 年線位階參考」）：引擎 `Bias_240` 已 round 2 位、再 `:+.1f`
  ＝雙重捨入，與同頁「年線位置」卡（bias_info['bias_240']＝calc_bias_pct(decimals=1)）可差 0.1／正負號相反
  ⇒ 卡片值有限時優先讀它，缺值才退回引擎。

golden：有限 PCR 的修前輸出於基底 `0482ebd5` 以 test_batch_z10 同一支 `_chips` 實跑後寫死 sha256（⛔ 不由現行碼反推）。
本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import math
import random
import re
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_chips as SC
import src.ui.tabs.macro.section_state as STATE
from shared.allocation_decision import build_allocation_decision
from shared.calc_helpers import calc_bias_pct
from shared.macro_compute import evaluate_market_status_v4_final as _V4
from tests.test_batch_z5 import _FI_FAIL, _H_FLAT, _LI_FLAT, _render_state
from tests.test_batch_z6 import _S, _hint, _out
from tests.test_batch_z10 import _chips, _digest, _li


def _joined(out) -> str:
    return '\x1e'.join(t for _k, t in out)


# ══════════════════════════════════════════════════════════════════════════
# C9-n2 (b)：「3萬」三處接 SSOT
# ══════════════════════════════════════════════════════════════════════════
def _pivot_texts(fut, mp):
    df = pd.DataFrame({"外資大小": [fut], "韭菜指數": [math.nan]})
    pv = _render_state(mp, _H_FLAT, _LI_FLAT, _FI_FAIL, ss={"li_latest": df}).pivots
    return [str(x) for p in pv for x in p]


class TestC9n2bWanFollowsSsot:
    def test_g_format_of_30000_is_3(self):
        assert f'{30000 / 10_000:g}' == '3' and f'{25000 / 10_000:g}' == '2.5'

    def test_ssot_30000_strings_unchanged(self, monkeypatch):
        joined = _joined(_chips(_li([-30000.0], [110.0]), monkeypatch))
        assert '外資期貨空單 30,000 口（≥3萬口門檻）' in joined
        assert '🔴 期貨空單 -30,000口（達3萬危險線）' in joined
        monkeypatch.undo()
        assert '外資期貨淨空 30,000口 ≥ 3萬口 → 頂部起跌訊號' in _pivot_texts(-30000.0, monkeypatch)

    def test_mutated_threshold_25000_all_three_say_2_5(self, monkeypatch):
        """突變：常數改 25000 ⇒ 三處都印「2.5萬」，不再出現寫死的「3萬」。"""
        monkeypatch.setattr(SC, 'FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD', 25000)
        monkeypatch.setattr(STATE, 'FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD', 25000)
        joined = _joined(_chips(_li([-25000.0], [110.0]), monkeypatch))
        assert '外資期貨空單 25,000 口（≥2.5萬口門檻）' in joined
        assert '🔴 期貨空單 -25,000口（達2.5萬危險線）' in joined
        assert '3萬' not in joined
        piv = _pivot_texts(-25000.0, monkeypatch)
        assert '外資期貨淨空 25,000口 ≥ 2.5萬口 → 頂部起跌訊號' in piv
        assert not any('3萬' in t for t in piv)


# ══════════════════════════════════════════════════════════════════════════
# Z10-n2：PCR 缺值不崩、不印「PCR nan」；有限值逐字不變
# ══════════════════════════════════════════════════════════════════════════
_CARD_HEAD = '外資期貨 12,000口'


def _card_text(out) -> str:
    """§三 外資期貨快速結論卡（策略 3）那段純文字。"""
    hits = [re.sub(r'<[^>]+>', '', t) for _k, t in out if _CARD_HEAD in t]
    assert len(hits) == 1, hits
    return hits[0]


_MISSING_PCR = {
    'none': lambda: pd.Series([None], dtype=object),
    'nan': lambda: [math.nan],
    'pinf': lambda: [math.inf],
    'ninf': lambda: [-math.inf],
}


class TestZ10n2MissingPcrNoCrash:
    @pytest.mark.parametrize('case', sorted(_MISSING_PCR))
    def test_card_without_pcr(self, case, monkeypatch):
        out = _chips(_li([12000.0], _MISSING_PCR[case]()), monkeypatch)   # 修前 none ⇒ TypeError
        card = _card_text(out)
        assert card.startswith('🎯 策略3：外資期貨 12,000口 → '), card    # 既有「不印 PCR」分支
        assert 'PCR' not in card
        # §三 後段（籌碼綜合判斷）有渲染到 ⇒ 不再中斷
        assert '籌碼綜合判斷' in re.sub(r'<[^>]+>', '', _joined(out))

    @pytest.mark.parametrize('case', ['none', 'nan'])
    def test_no_nan_anywhere(self, case, monkeypatch):
        out = _chips(_li([12000.0], _MISSING_PCR[case]()), monkeypatch)
        assert not re.search(r'\bnan\b', re.sub(r'<[^>]+>', '', _joined(out)), re.I)

    @pytest.mark.parametrize('dtype', [object, 'Float64'])
    def test_pd_na_card(self, dtype, monkeypatch):
        """pd.NA：卡片本身不再拋（修前在本行 `float(pd.NA)` 拋）。

        ⚠️ 其後 L1 `render_leading_table` 的 `fmt` 對 pd.NA 另拋 TypeError（不在本列範圍，另登）——
        此處以 stub 隔開該 L1 表格，只驗本列這一行。
        """
        monkeypatch.setattr(SC, 'render_leading_table', lambda df: '')
        out = _chips(_li([12000.0], pd.array([pd.NA], dtype=dtype)), monkeypatch)
        card = _card_text(out)
        assert card.startswith('🎯 策略3：外資期貨 12,000口 → ') and 'PCR' not in card


#: 有限 PCR：修前（基底 `0482ebd5`）同一支 `_chips` 實跑的整段 §三 sha256。
_FINITE_PCR_BASE = {
    'f110': (lambda: _li([-20000.0], [110.0]),
             'b0b590bad506217ad7a1675b8d212effe1463c17939b6bdfa19b1ee703bc293b'),
    'f85.25': (lambda: _li([12000.0], [85.25]),
               '4c4073b4674a1a832b78b55740136c7e446025c7809c8c989111b6751aad9538'),
    'f0': (lambda: _li([-35000.0], [0.0]),
           '07a6f7c5dae9304a4c518b750a93df3fdeae2ce93636adce515c465e33c0412f'),
    'int95': (lambda: _li([-16000.0], [95]),
              '0bd9d93693faca21f69325c61df91aa1e25cbab61fcef3c6f088f955c7ca2b6d'),
    'np32': (lambda: _li([5000.0], [np.float32(99.95)]),
             '52c1a07e6fa72993f7cfea20ba060411ec2258ff3daa0b195b742a1bad4b7b79'),
    'dec': (lambda: _li([-30000.0], pd.Series([Decimal('120.05')], dtype=object)),
            '0b4a34fcca4c34a0d79c0b697d677cc944d4b449c457b32c71f5595130d227ac'),
    'multi': (lambda: _li([-20000.0, -31000.0], [100.0, 77.7]),
              'afb862a3ec152ade7566375ea1d02027d67938b0e18fea5d464a5346cecd50bb'),
}


class TestZ10n2FiniteUnchanged:
    @pytest.mark.parametrize('case', sorted(_FINITE_PCR_BASE))
    def test_digest_equals_base(self, case, monkeypatch):
        mk, want = _FINITE_PCR_BASE[case]
        assert _digest(_chips(mk(), monkeypatch)) == want

    def test_finite_pcr_still_printed(self, monkeypatch):
        card = _card_text(_chips(_li([12000.0], [85.25]), monkeypatch))
        assert ' | PCR 85.2 → ' in card


# ══════════════════════════════════════════════════════════════════════════
# Z6-n4：作戰室「📐」乖離與同頁「年線位置」卡同源同捨入
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def _hermetic_allocation(monkeypatch):
    monkeypatch.setattr(AS, 'get_allocation', lambda *a, **k: build_allocation_decision(None))


def _bias_info(px, ma):
    """與 L1 `macro_snapshot` 同法：calc_bias_pct(decimals=1)，round 到 -0.0 正規化成 +0.0。"""
    b = calc_bias_pct(px, ma, decimals=1)
    return {'price': px, 'ma240': ma, 'bias_240': 0.0 if b == 0 else b}


def _both(px, ma):
    """回（「📐」第一段乖離字串, 「年線位置」卡乖離字串）。"""
    joined = '\n'.join(t for _k, t in _out(_S(_bias_info(px, ma))))
    hint = _hint(_out(_S(_bias_info(px, ma))))
    assert len(hint) == 1, hint
    m_hint = re.match(r'年線乖離 ([+-]\d+\.\d)%', hint[0])
    m_card = re.search(r'乖離([+-]\d+\.\d)%', re.sub(r'年線乖離 [+-]\d+\.\d%', '', joined))
    assert m_hint and m_card, (hint, joined)
    return m_hint.group(1), m_card.group(1)


@pytest.mark.usefixtures('_hermetic_allocation')
class TestZ6n4NoDoubleRounding:
    @pytest.mark.parametrize('px,ma,want', [
        (21029.92, 20000.0, '+5.1'),     # 真乖離 5.1496：引擎 round2 → 5.15 → `:+.1f` +5.2；卡片 +5.1
        (19990.08, 20000.0, '+0.0'),     # 真乖離 -0.0496：引擎 round2 → -0.05 → -0.1；卡片 -0.0 → +0.0（正負號相反）
        (20009.92, 20000.0, '+0.0'),     # 真乖離 +0.0496：引擎 → +0.1；卡片 +0.0
    ], ids=['5.1496', '-0.0496', '+0.0496'])
    def test_boundary_hint_equals_card(self, px, ma, want):
        # 前提：這些輸入在修前確實會雙重捨入出不同值
        assert f'{_V4(px, ma, None)["Bias_240"]:+.1f}' != want
        hint, card = _both(px, ma)
        assert hint == card == want

    def test_random_hint_equals_card(self):
        rng = random.Random(2020)
        for i in range(400):
            ma = rng.uniform(1000.0, 30000.0)
            px = ma * (1 + rng.uniform(-0.3, 0.3))
            if i % 2:
                px, ma = np.float64(px), np.float64(ma)
            hint, card = _both(px, ma)
            assert hint == card, (px, ma, hint, card)

    @pytest.mark.parametrize('bad', [None, math.nan, math.inf, 'x'], ids=['none', 'nan', 'inf', 'str'])
    def test_card_value_missing_falls_back_to_engine(self, bad):
        """卡片值缺／非有限 ⇒ 退回引擎 `Bias_240`（既有路徑，輸出照舊）。"""
        hint = _hint(_out(_S({'price': 20000.0, 'ma240': 19000.0, 'bias_240': bad})))
        assert hint == ['年線乖離 +5.3%']
