"""批 Z10（優先 1 可自主·可即派）—— C8-n1 (a) ＋ C8-n6 ＋ Z6-n2（SSOT 接線）釘子（基底 origin/main `1354d9ac`）。

- C8-n1 (a)（L5 `src/ui/tabs/macro/section_chips.py` §三「外資期貨」快速結論卡）：外資大小**整欄**沒有任何
  有限值（全 None／NaN／±inf）時，修前 `float(None)` 拋 TypeError（被 `_render_tab_isolated` 接住 ⇒ §三 之後
  整段不渲染）、全 NaN 則印「外資期貨 nan口…微空 nan口」。改走同卡既有分支
  「外資期貨留倉 → 先行指標欄位異常，請確認 FinMind Token」（不下結論、不填 0）。
  欄內有任一有限值 ⇒ 整段輸出逐字不變（末列缺＝C8-n1 (b)，本批未動）。
- C8-n6（L0 `shared/macro_compute.evaluate_market_status_v4_final`）：`futures_net_oi or 0` 把缺值捏成 0 ⇒
  改為 None 時 `Is_Foreign_Hedging` 回 None；其餘鍵（Signal／建議／持股／乖離…）與修前相同。
- Z6-n2（同函式）：`-30000` 改接 SSOT `FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD`（同值，判式仍為嚴格 `<`；
  等號歸屬本批未動）。

golden：修前輸出於基底 `1354d9ac` 以本檔同一支 `_chips`（`_FakeST`）實跑後寫死 sha256（⛔ 不讀 git、
不由現行碼反推）。本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import hashlib
import math
import types
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

import shared.macro_compute as MC
import src.services.allocation_service as AS
import src.ui.tabs.macro.section_chips as SC
from src.ui.render.ui_widgets import STRATEGY_TECHNICAL, strategy_conclusion
from tests.test_m2n2_no_zero_fill import _FakeST


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode('utf-8')).hexdigest()


def _chips(li, mp):
    """實跑 §三（法人／融資空、VIX 15、先行指標 = li）。回 [(種類, 文字)]；拋例外照拋。"""
    fake = _FakeST({"macro_info": {"vix": {"current": 15.0, "ma20": 15.0}}, "li_latest": li})
    mp.setattr(SC, "st", fake)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, range_text="", capped=False, cap_text="", final_hi=None))
    mp.setattr(AS, "get_allocation_sleeves", lambda *a, **k: None)
    SC.render_section_chips({}, None, {})
    return list(fake.out)


def _li(fut, pcr=None, *, dtype=None):
    n = len(fut)
    d = {"日期": [f"2026-10-0{i + 1}" for i in range(n)],
         "外資大小": pd.Series(fut, dtype=dtype)}
    if pcr is not None:
        d["選PCR"] = pcr
    return pd.DataFrame(d)


_NA = math.nan
_INF = math.inf

# ══════════════════════════════════════════════════════════════════════════
# C8-n1 (a)
# ══════════════════════════════════════════════════════════════════════════
#: 同卡既有分支（修前即存在的字句；本批未新增任何使用者可見字）
_CARD_EXISTING = strategy_conclusion(STRATEGY_TECHNICAL, '外資期貨留倉',
                                     '先行指標欄位異常，請確認 FinMind Token', '')

#: 欄內有任一有限值 ⇒ 整段 §三 輸出與基底逐字相同（含 C8-n1 (b) 末列 NaN／inf 的現行輸出）
_UNCHANGED = {
    'single_-40000': (lambda: _li([-40000.0], [110.0]),
                      'c256b818ab0f37dd557ba0fe403c8c4d509dfe4c9f0045e4f3398e46a39a17d4'),
    'eq_-30000': (lambda: _li([-30000.0], [110.0]), 'eb44d95f5f417d85dd35c84e6917dd7d0ee8f7bc2c8b22b1b1865a41a0d37337'),
    'mixed_nan_mid': (lambda: _li([-20000.0, _NA, 5000.0], [100.0, _NA, 90.0]), '5e2b699887b7ba0b01eef8e83f8160fe26d3ccdb4a806478e34843ba4f892cf7'),
    'b_last_nan': (lambda: _li([-20000.0, _NA], [100.0, 110.0]), '28d2533f1f64e7e605b1e486e1967767e63907c8b694c242e11d63426b1c09a4'),
    'pos_pcr_nan': (lambda: _li([12000.0], [_NA]), 'b73114fc2f7948ef36bd6a0c5374e2595b6bb6d0fdb4b54894aad121c78d58c9'),
    'obj_none_then_finite': (lambda: _li([None, -16000.0], [100.0, 120.0], dtype=object), '1afdd356fab04aba4fd17e25ce7898f32ed06a17075078ce8244d08fa7093f01'),
    'no_fut_col': (lambda: pd.DataFrame({"日期": ["2026-10-01"], "選PCR": [110.0]}), '14cc920355eb807e2219cd6c7ab7e35fdb73d83014a2f92f60323811e3029481'),
}

#: 外資大小整欄無有限值。修前於基底實跑：None 類 ⇒ TypeError（§三 之後整段不渲染）；全 NaN ⇒ 印
#: 「外資期貨 nan口 | PCR 120.0 → 外資期貨微空 nan口，水位正常…」。
#: （±inf／pd.NA 整欄：卡片同樣走既有分支，但其後 L1 `render_leading_table` 另拋例外 —— 非本列範圍，未列入。）
_ALL_NONFINITE = {
    'none_1row': lambda: _li([None], [110.0]),
    'none_3row': lambda: _li([None, None, None], [100.0, 110.0, 120.0]),
    'none_pcr_none': lambda: pd.DataFrame({"日期": ["d1", "d2"], "外資大小": [None, None],
                                           "選PCR": [None, None], "外資": [1.0, 2.0]}),
    'nan_3row': lambda: _li([_NA, _NA, _NA], [100.0, 110.0, 120.0]),
}

class TestC8n1aAllNonFiniteFutures:
    @pytest.mark.parametrize('case', sorted(_ALL_NONFINITE))
    def test_no_raise_and_existing_branch_card(self, case, monkeypatch):
        out = _chips(_ALL_NONFINITE[case](), monkeypatch)
        texts = [t for _k, t in out]
        assert texts.count(_CARD_EXISTING) == 1, case
        joined = '\x1e'.join(texts)
        # 不下籌碼結論：不印 nan／inf 口數、不印任何期貨結論句
        for bad in ('nan口', 'inf口', '啟動強制防禦，等待空單回補', '空單累積中', '外資期貨翻多', '水位正常'):
            assert bad not in joined, (case, bad)
        # §三 之後的段落照常渲染（修前 None 類在卡片處就拋，這兩段不會出現）
        assert ('expander', '🔍 資料來源診斷（點此確認各欄數據正確性）') in out
        assert any('籌碼綜合判斷' in t for t in texts)


class TestC8n1aUnchangedWhenAnyFinite:
    @pytest.mark.parametrize('case', sorted(_UNCHANGED))
    def test_digest_equals_base(self, case, monkeypatch):
        mk, want = _UNCHANGED[case]
        assert _digest(_chips(mk(), monkeypatch)) == want


# ══════════════════════════════════════════════════════════════════════════
# C8-n6 ＋ Z6-n2：L0 v4 引擎
# ══════════════════════════════════════════════════════════════════════════
_V4 = MC.evaluate_market_status_v4_final


def _v4_pre_z10(current_price, ma_240, futures_net_oi):
    """基底 `1354d9ac` 的 `evaluate_market_status_v4_final` 凍結副本（逐字；僅 `_is_finite_positive` 改取 MC）。"""
    futures_net_oi = futures_net_oi or 0
    is_foreign_hedging = futures_net_oi < -30000

    if not (MC._is_finite_positive(current_price) and MC._is_finite_positive(ma_240)):
        return {
            "Signal": None,
            "Action_Advice": None,
            "Suggested_Holding": None,
            "Bias_240": None,
            "Is_Bull": None,
            "Is_Overheated": None,
            "Is_Foreign_Hedging": is_foreign_hedging,
        }

    bias_240 = ((current_price - ma_240) / ma_240) * 100
    is_bull_market = current_price >= (ma_240 * 0.99)
    is_overheated = bias_240 > 20.0

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


def _outcome(fn, *args):
    try:
        r = fn(*args)
    except Exception as e:  # noqa: BLE001
        return 'raise', type(e).__name__, str(e)
    return 'ok', tuple(r.items()), tuple(type(v) for v in r.values())


_PRICES = [(20000.0, 19000.0), (25000.0, 19000.0), (18000.0, 19000.0), (18810.0, 19000.0),
           (None, 19000.0), (20000.0, None), (None, None), (0, 0), ('N/A', 16000.0)]


class TestC8n6FuturesMissingIsUnknown:
    @pytest.mark.parametrize('px,ma', _PRICES)
    def test_none_futures_hedging_unknown_rest_unchanged(self, px, ma):
        new, pre = _V4(px, ma, None), _v4_pre_z10(px, ma, None)
        assert pre['Is_Foreign_Hedging'] is False            # 前提：修前把缺值當「確定沒避險」
        assert new['Is_Foreign_Hedging'] is None
        assert list(new) == list(pre)
        assert {k: v for k, v in new.items() if k != 'Is_Foreign_Hedging'} == \
               {k: v for k, v in pre.items() if k != 'Is_Foreign_Hedging'}

    def test_warroom_hint_unchanged_for_none(self):
        # 唯一 production caller（作戰室）只取 truthiness：None 與 False 同為不成立
        assert not _V4(20000.0, 19000.0, None).get('Is_Foreign_Hedging')

    @pytest.mark.parametrize('fut', [0, 0.0, -0.0, 5000, -29999, -30000, -30000.0, -30000.5, -30001,
                                     -40000, -40000.0, np.int64(-40000), np.float64(-30001.0),
                                     -_INF, _INF, _NA, Decimal('-30000.0000000000000001'),
                                     Fraction(-60001, 2), True, '-40000', np.int64(0), np.float64(0.0),
                                     np.False_, False, '', [], pd.NA])
    @pytest.mark.parametrize('px,ma', _PRICES)
    def test_non_none_identical_to_base(self, px, ma, fut):
        assert _outcome(_V4, px, ma, fut) == _outcome(_v4_pre_z10, px, ma, fut)


class TestZ6n2SsotWired:
    def test_threshold_follows_ssot(self, monkeypatch):
        assert _V4(20000.0, 19000.0, -20000)['Is_Foreign_Hedging'] is False
        monkeypatch.setattr(MC, 'FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD', 10000)
        out = _V4(20000.0, 19000.0, -20000)
        assert out['Is_Foreign_Hedging'] is True
        assert out['Signal'] == '🟡 多頭過熱 / 震盪警戒'

    def test_equal_threshold_still_strict(self):
        # 等號歸屬本批未動：剛好 −30000 仍不判避險（與 regime_arbiter 同為嚴格比較）
        assert _V4(20000.0, 19000.0, -30000)['Is_Foreign_Hedging'] is False
        assert _V4(20000.0, 19000.0, -30001)['Is_Foreign_Hedging'] is True
