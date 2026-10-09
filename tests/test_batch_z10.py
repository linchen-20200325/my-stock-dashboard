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

📌 續作（客戶 2026-10-09 裁示，逐字）：「Q-r10a：B 缺值不得視為 0，也不得因此產生假綠燈。Z10 與 Y2-n10 一起處理到
資料語意一致後再合併。」「Q-r10b：A -30,000 等於門檻時統一歸「防禦」。依既有 Q-r9d「等於門檻歸較差側」原則，
全站相關判定統一，不另創規則。」（基底＝`wip/batch-z10` merge origin/main 後 `66ffb1f0`）
- Y2-n10（§三 `read_v4_macro_veto`）：外資期貨缺值不再當 0 ⇒ 走引擎既有「⬜ 無法判定…外資期貨 未取得」，不再印
  「🟢 綠燈…外資期貨=0口 — 可依策略佈局」；§八 揭露框 `_futures` 為 None 時走引擎既有字「未取得」、不崩。
- C7-n3 (a)（§三 v5 段）：`or 0` 缺值改走同頁 v4 卡既有字「外資期貨 未取得」（灰），不再印「水位中性…」。
- Q-r10b：外資期貨防禦門檻（`FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD`）全站判式統一 `<=`（含 `regime_arbiter` 的
  `abs >=`）並接 SSOT：L0 v4_final、L0 regime_arbiter、§三 結論卡（原即 `<=`）、v5 段（原即 `<=`，接 SSOT）、
  進階警示「期貨大空警戒」、籌碼綜合判斷、§二 拐點面板 5。

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
#: 📌 續作移出兩例（客戶 2026-10-09 裁示後預期改變，改由下方 TestQr10b／TestY2n10 斷言）：
#:   'eq_-30000'（修前 eb44d95f…：進階警示無「期貨大空警戒」、綜合判斷印「⚠️ 期貨淨空」）；
#:   'no_fut_col'（修前 14cc9203…：v4 卡「🟢 綠燈…外資期貨=0口 — 可依策略佈局」、v5 卡「水位中性…」）。
#: 續作新增（於 `66ffb1f0` 以同一支 `_chips` 實跑寫死）：−29999／−30001／−15000／+5000／0。
#: 📌 客戶 2026-10-09 裁示 2（≥／達 邊界文字）後重寫死：與舊值逐項比對，差異**僅限**表 caption
#:   「外資空單>」→「≥」（每例 1 處）＋ −40000／−30001 的防禦三句「口 >」→「≥」「>3萬口門檻」→「≥」「超越」→「達」；其餘逐字相同。
_UNCHANGED = {
    'single_-40000': (lambda: _li([-40000.0], [110.0]),
                      '0aeb2b755a136bdaad52b0bda15b9b2d919deb6ebbecd4d65f130c0e2123e355'),
    'm29999': (lambda: _li([-29999.0], [110.0]), '121a0374d7d0176341de4a83b470da5a59c24dfaf8f2c51efb37e7a53e1cc11a'),
    'm30001': (lambda: _li([-30001.0], [110.0]), '1468fc8afe58633f90088e9c049c5e321569db76c3e860ec8992e9ba028606ba'),
    'm15000': (lambda: _li([-15000.0], [110.0]), '7c21ea806e42e799ce72139bd922c2c46b27677c7f39975e72c1ffbcee9f39ea'),
    'p5000': (lambda: _li([5000.0], [110.0]), '870ef4d55d05b3e473f00efeee87c6c6c22e544cb283a1b876b1b779fbd8c908'),
    'zero': (lambda: _li([0.0], [110.0]), '9e73377d8f047b9e390559deb67db20fd888a67d5d29765309eb54340b5851d1'),
    'mixed_nan_mid': (lambda: _li([-20000.0, _NA, 5000.0], [100.0, _NA, 90.0]), '32ecb3b02f1d09510413c928768d8fa57ed3c30c89419d1ae709b0779c417022'),
    'b_last_nan': (lambda: _li([-20000.0, _NA], [100.0, 110.0]), '42bcb378d663bd051421ba5ea2a4d8fa52692509353672be4282930cd19b83ff'),
    # 📌 批 Z20（Z10-n2）：PCR 末列 NaN 不再印「| PCR nan」（走既有「不印 PCR」分支）。新 digest 於本批實跑寫死；
    #   與舊值 4f39360c…（基底 `0482ebd5` 同一支 `_chips` 實跑）逐段比對：25 段僅 §三 外資期貨結論卡少「 | PCR nan」，其餘逐字相同。
    'pos_pcr_nan': (lambda: _li([12000.0], [_NA]), '5e58a478112f676752636c75add1f4dfd3bb8f90e8b0c764a352f78aca93631f'),
    'obj_none_then_finite': (lambda: _li([None, -16000.0], [100.0, 120.0], dtype=object), '5ecf33a9e12db76df51de1a672ec4b73325be1611e8908309a1d5bcc90e31f9b'),
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
        # 續作（Q-r10b）：剛好 −30000 改歸避險側 ⇒ 對拍凍結副本的 −30001（避險成立、其餘同）；
        #   比較子 `<` → `<=` 只改了例外訊息的運算子字面（型別不變）
        pre_fut = -30001 if (isinstance(fut, (int, float)) and fut == -30000) else fut
        now, pre = _outcome(_V4, px, ma, fut), _outcome(_v4_pre_z10, px, ma, pre_fut)
        if now[0] == 'raise':
            now = (now[0], now[1], now[2].replace("'<='", "'<'"))
        assert now == pre


class TestZ6n2SsotWired:
    def test_threshold_follows_ssot(self, monkeypatch):
        assert _V4(20000.0, 19000.0, -20000)['Is_Foreign_Hedging'] is False
        monkeypatch.setattr(MC, 'FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD', 10000)
        out = _V4(20000.0, 19000.0, -20000)
        assert out['Is_Foreign_Hedging'] is True
        assert out['Signal'] == '🟡 多頭過熱 / 震盪警戒'

    def test_equal_threshold_is_defense(self):
        # 續作（Q-r10b，客戶 2026-10-09）：剛好 −30000 歸避險（防禦）側；−29999 不成立
        assert _V4(20000.0, 19000.0, -30000)['Is_Foreign_Hedging'] is True
        assert _V4(20000.0, 19000.0, -30000.0)['Is_Foreign_Hedging'] is True
        assert _V4(20000.0, 19000.0, -29999)['Is_Foreign_Hedging'] is False
        assert _V4(20000.0, 19000.0, -30001)['Is_Foreign_Hedging'] is True


# ══════════════════════════════════════════════════════════════════════════
# 續作（客戶 2026-10-09）：Y2-n10 ＋ C7-n3 (a) —— 外資大小整欄缺值時 §三 全段無「把缺值當 0」的結論
# ══════════════════════════════════════════════════════════════════════════
import tests.test_batch_z7 as Z7  # noqa: E402
from shared.regime_arbiter import is_foreign_futures_defense  # noqa: E402
from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD as _THR  # noqa: E402
from tests.test_batch_z5 import _FI_FAIL, _H_FLAT, _LI_FLAT, _render_state  # noqa: E402

#: 整欄缺值的各種形狀（含欄位不存在）
_COL_MISSING = {
    'none_1row': lambda: _li([None], [110.0]),
    'none_3row': lambda: _li([None, None, None], [100.0, 110.0, 120.0]),
    'nan_3row': lambda: _li([_NA, _NA, _NA], [100.0, 110.0, 120.0]),
    'obj_none': lambda: _li([None, None], [100.0, 110.0], dtype=object),
    'no_fut_col': lambda: pd.DataFrame({"日期": ["2026-10-01"], "選PCR": [110.0]}),
}
#: 修前（`66ffb1f0` 實跑）在這些情境出現過的「缺值當 0」結論字樣
_FAKE_ZERO = ('外資期貨=0口', '外資期貨=0 口', '可依策略佈局', '🟢 綠燈', '水位中性', 'nan口', 'nan 口',
              '外資期貨微空', '總經環境安全')
_V5_MISSING_LINE = '📌 外資期貨 未取得'
_V4_UNKNOWN_MSG = ('⬜ 總經環境無法判定：外資期貨 未取得（VIX=15.0 / 外資期貨=未取得）— 缺的這項有可能正是會亮紅燈的'
                   '那一項，故不給結論、也不用預設值代替')


class TestY2n10WholeColumnMissing:
    @pytest.mark.parametrize('case', sorted(_COL_MISSING))
    def test_no_fake_zero_conclusion_in_section3(self, case, monkeypatch):
        out = _chips(_COL_MISSING[case](), monkeypatch)
        joined = '\x1e'.join(t for _k, t in out)
        for bad in _FAKE_ZERO:
            assert bad not in joined, (case, bad)
        v4 = [t for _k, t in out if '🏛️' in t and '風險燈' in t]
        assert len(v4) == 1 and '⬜ 無法判定' in v4[0] and _V4_UNKNOWN_MSG in v4[0], v4
        v5 = [t for _k, t in out if '💰 v5' in t]
        assert len(v5) == 1 and _V5_MISSING_LINE in v5[0], v5

    @pytest.mark.parametrize('case', sorted(_COL_MISSING))
    def test_v5_card_gray_with_sleeves(self, case, monkeypatch):
        out = _chips(_COL_MISSING[case](), monkeypatch)       # 先跑一次（sleeves=None）建立 monkeypatch
        monkeypatch.setattr(AS, "get_allocation_sleeves",
                            lambda *a, **k: {"股票型ETF": 50, "債券型ETF": 30, "貨幣/現金": 20})
        fake = SC.st
        n0 = len(fake.out)
        SC.render_section_chips({}, None, {})
        v5 = [t for _k, t in fake.out[n0:] if '💰 v5' in t]
        assert len(v5) == 1 and _V5_MISSING_LINE in v5[0] and '水位中性' not in v5[0]
        assert 'border-left:5px solid #888888' in v5[0] and '#58a6ff' not in v5[0]   # 灰，不是「中性」藍
        assert out

    def test_read_v4_macro_veto_futures_none(self, monkeypatch):
        _chips(_COL_MISSING['none_3row'](), monkeypatch)
        r = SC.read_v4_macro_veto()
        assert r['status'] == '⬜ 無法判定' and r['_futures'] is None and r['futures'] is None

    def test_li_not_loaded_futures_none(self, monkeypatch):
        # li_latest 不在 session：§八 入口不得以 0 口判綠燈
        fake = _FakeST({"macro_info": {"vix": {"current": 15.0}}})
        monkeypatch.setattr(SC, "st", fake)
        r = SC.read_v4_macro_veto()
        assert r['status'] == '⬜ 無法判定' and r['_futures'] is None


def _mid_out(fut, vix, veto, mp):
    base = dict(Z7._MID_BASE)
    if veto == 'trig':
        base['ism_pmi'] = {'value': 45.0}
        base['tw_export'] = {'yoy': -10.0, 'date': '2026-08'}
    return Z7._mid(Z7._node(vix), mp, real_v4=True, fut=fut, base=base)[0]


class TestY2n10Section8Disclosure:
    @pytest.mark.parametrize('fut', [None, _NA], ids=['none', 'nan'])
    @pytest.mark.parametrize('vix', [18.0, 26.0])
    @pytest.mark.parametrize('veto', ['ok', 'trig'])
    def test_missing_futures_no_crash_no_zero(self, fut, vix, veto, monkeypatch):
        out = _mid_out(fut, vix, veto, monkeypatch)
        joined = '\x1e'.join(t for _k, t in out)
        assert '外資期貨=0 口' not in joined and 'nan 口' not in joined
        warns = [t for k, t in out if k == 'warning' and '兩套判定結論不一致' in t]
        for w in warns:
            assert f'看的是 VIX={vix:.1f}、外資期貨=未取得' in w

    def test_none_disclosure_uses_existing_missing_word(self, monkeypatch):
        # 修前（`66ffb1f0`）：整欄 None ⇒ 揭露框不出（§三 假綠燈與本區「無觸發」一致）；
        #   修後 §三 ⬜ ⇒ 揭露框出現，期貨走引擎既有缺值字「未取得」（`None:,.0f` 不得 TypeError）
        warns = [t for k, t in _mid_out(None, 18.0, 'ok', monkeypatch)
                 if k == 'warning' and '兩套判定結論不一致' in t]
        assert len(warns) == 1
        assert '（§三 籌碼）：⬜ 無法判定　看的是 VIX=18.0、外資期貨=未取得' in warns[0]

    #: 有限期貨值 ⇒ §八 整段輸出與 `66ffb1f0` 逐字相同（同一支 `_mid_out` 實跑寫死）
    _GOLD = {
        (-30000.0, 18.0, 'ok'): '9cbb665b96373e955ec428ad58ef099feadbde005edb0fc9bce74cf417db640c',
        (-30000.0, 18.0, 'trig'): '3b2f3d37394b2fbc5eec7f44e6437b1d4731ba1fee5df7a05d4752dc3a0ffe8a',
        (-30000.0, 26.0, 'ok'): '83a65baa177436cfae3139bfea5244bb8b2a154b22f1a74fa957a739a941efa5',
        (-29999.0, 18.0, 'ok'): '2f7e306b0069d7c7882e035b7134e55a409d77e975f7faf11341f64434dce2f2',
        (-29999.0, 26.0, 'trig'): '5ae5f82fbc3ac8b8cc215ad3ada2f30e18d3a5903e82015b6efb86f786dd4c4a',
        (-40000.0, 18.0, 'ok'): 'ae5b8f47c481f5eaca89bdced7a4e7e46eb9f501206c5365c72f6ea6638a88ca',
        (-40000.0, 26.0, 'trig'): '2fa308cb99f4392068509a16f162137bd53230ccb78f73b44b3c964db6424f2a',
        (0.0, 18.0, 'ok'): '560aa4db05b788efcd6b0f2f1811d2cd4e822bccbf38e591ed54adf055379f38',
        (0.0, 18.0, 'trig'): '252afb949678aa70c9fecd34c48e32f6319c38a35d9ea3f000fe200e85f77c99',
        (5000.0, 26.0, 'ok'): 'c01539c6d59a9ec831b458f8b08f02112193663405cf06058450349444dadb25',
        (5000.0, 18.0, 'trig'): '0ea7998deca08c860089f9e3770091f8cb425f7fc2e1f82cf6c9157b714d6025',
    }

    #: 批 Z19（客戶裁示 PMI=50 ＝ 中性／榮枯線）：§八 PMI 卡門檻帶改字。雜湊**不重算**、不放寬：
    #   先斷言新字串恰出現 1 次，再換回 `66ffb1f0` 原字串比對（比照 test_batch_z9_g2 `_undo`）；
    #   新字串本身另由下方 `test_pmi_band_caption_present` 與 `tests/test_batch_z19.py` 守。
    _PMI_CAP_NEW = '門檻帶：✅>50｜🟡=50｜⚠️≥47｜🔴<47'
    _PMI_CAP_OLD = '門檻帶：✅≥50｜⚠️≥47｜🔴<47'

    @classmethod
    def _undo_z19(cls, out):
        joined = '\x1e'.join(t for _k, t in out)
        assert joined.count(cls._PMI_CAP_NEW) == 1, joined.count(cls._PMI_CAP_NEW)
        return [(k, t.replace(cls._PMI_CAP_NEW, cls._PMI_CAP_OLD)) for k, t in out]

    @pytest.mark.parametrize('key', sorted(_GOLD))
    def test_finite_futures_identical_to_base(self, key, monkeypatch):
        assert _digest(self._undo_z19(_mid_out(*key, monkeypatch))) == self._GOLD[key]

    def test_pmi_band_caption_present(self, monkeypatch):
        """批 Z19 正向斷言：§八 輸出含新 PMI 門檻帶、不含舊字。"""
        joined = '\x1e'.join(t for _k, t in _mid_out(-30000.0, 18.0, 'ok', monkeypatch))
        assert self._PMI_CAP_NEW in joined and self._PMI_CAP_OLD not in joined


# ══════════════════════════════════════════════════════════════════════════
# 續作（客戶 2026-10-09）：Q-r10b —— −30000 全站一致判防禦；−29999 一致不防禦
# ══════════════════════════════════════════════════════════════════════════
def _state_pivots(fut, mp):
    df = pd.DataFrame({"外資大小": [fut], "韭菜指數": [_NA]})
    return [p[0] for p in _render_state(mp, _H_FLAT, _LI_FLAT, _FI_FAIL, ss={"li_latest": df}).pivots]


class TestQr10bEqualThresholdIsDefense:
    def test_threshold_is_ssot_30000(self):
        assert _THR == 30000

    @pytest.mark.parametrize('fut,want', [(-30000.0, True), (-30000, True), (-29999.0, False),
                                          (-30001.0, True)])
    def test_all_judgement_points_agree(self, fut, want, monkeypatch):
        got = {}
        got['L0 v4_final'] = bool(_V4(20000.0, 19000.0, fut)['Is_Foreign_Hedging'])
        got['L0 regime_arbiter'] = is_foreign_futures_defense(market_score=1, futures_net_lots=fut)
        out = _chips(_li([fut], [110.0]), monkeypatch)
        joined = '\x1e'.join(t for _k, t in out)
        got['§三 結論卡'] = '啟動強制防禦，等待空單回補' in joined
        got['§三 v5'] = '嚴禁追高攤平，保護本金優先' in joined
        got['§三 進階警示'] = '期貨大空警戒' in joined
        got['§三 綜合判斷'] = '🔴 期貨空單' in joined
        monkeypatch.undo()
        got['§二 拐點'] = '外資期貨大量空單' in _state_pivots(fut, monkeypatch)
        assert got == {k: want for k in got}, got

    def test_minus_30000_section3_text(self, monkeypatch):
        out = _chips(_li([-30000.0], [110.0]), monkeypatch)
        texts = [t for _k, t in out]
        # 客戶 2026-10-09 裁示 2：等於門檻歸防禦 ⇒ 使用者文字改為「≥／達」正確邊界
        assert any('外資期貨空單 30,000 口（≥3萬口門檻）' in t for t in texts)
        assert any('🔴 期貨空單 -30,000口（達3萬危險線）' in t for t in texts)
        assert not any('⚠️ 期貨淨空 -30,000口' in t for t in texts)

    def test_minus_30000_no_strict_gt_contradiction(self, monkeypatch):
        """剛好 −30000 時，§三／§二 畫面不得出現「30,000口 > 30,000口」類矛盾句。"""
        import re
        out = _chips(_li([-30000.0], [110.0]), monkeypatch)
        texts = [t for _k, t in out]
        monkeypatch.undo()
        df = pd.DataFrame({"外資大小": [-30000.0], "韭菜指數": [_NA]})
        pv = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL, ss={"li_latest": df}).pivots
        texts += [str(x) for p in pv for x in p]
        joined = '\x1e'.join(texts)
        # 真的有渲染到防禦文字（避免空集合假綠）
        assert '外資期貨空單 30,000口 ≥ 30,000口' in joined
        assert '外資期貨淨空 30,000口 ≥ 3萬口' in joined
        bad = re.compile(r'30,000\s*口?\s*>\s*(30,000|3萬)|>\s*3萬口門檻|超越3萬')
        assert not bad.search(joined), bad.search(joined)

    def test_section3_card_threshold_follows_ssot(self, monkeypatch):
        import src.ui.tabs.macro.section_state as STATE
        monkeypatch.setattr(SC, 'FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD', 25000)
        monkeypatch.setattr(STATE, 'FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD', 25000)
        out = _chips(_li([-25000.0], [110.0]), monkeypatch)
        joined = '\x1e'.join(t for _k, t in out)
        for s in ('啟動強制防禦，等待空單回補', '嚴禁追高攤平，保護本金優先', '期貨大空警戒', '🔴 期貨空單'):
            assert s in joined, s
        assert '外資期貨大量空單' in _state_pivots(-25000.0, monkeypatch)
