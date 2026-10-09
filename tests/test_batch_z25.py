"""批 Z25：Z19-n5、Z16-n1。

- Z19-n5（L1 `src/data/macro/leading_indicators.py`）：「外資大小」＝ TX 淨口 ＋ 0.25×MTX 淨口。
  修前 `build_leading_fast` 的 `fut_net.get(dk, 0)` 與 `finmind_fut_oi` 的 `result.get(dk, 0)`
  把缺的那一支當 0 ⇒ FinMind 限流讓 TX 回空表時只剩 0.25×MTX（低估約 4 倍），且半套結果照樣入快取。
  修法：同一天 TX、MTX 任一缺 ⇒ 該日 None（不補 0）；任一支整體沒有可用外資列 ⇒ 本次結果不入快取
  （`finmind_fut_oi` 另比照既有「主源失敗」走 TAIFEX 備援）。兩支都有的日子輸出與修前逐字相同。
- Z16-n1（L5 `src/ui/tabs/macro/section_warroom.py`）：作戰室「外資方向」未取得（None）時
  原畫紅框 ⚠️（把「沒資料」畫成「出錯／偏空」，違 §1.A 第 4 點）⇒ 改用同檔既有「無資料」
  灰 #484f58 ＋ ⬜，文字「未知」不變；有值時整段輸出逐字不變（golden 於修前基底實跑寫死）。

本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import os

import pandas as pd
import pytest

import shared.cache_layer as CL
import src.data.macro.leading_indicators as LI
import src.services.allocation_service as AS
import src.ui.tabs.macro.section_warroom as W
from shared.allocation_decision import build_allocation_decision
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from shared.inst_net import InstNetDict
from tests.test_m2n2_no_zero_fill import _FakeST
from tests.test_batch_z26 import undo_z26_gray_card  # 批 Z26:持股比例未載入改灰,本檔沿用修前 golden


# ══════════════════════════════════════════════════════════════════════════
# Z19-n5：TX／MTX 缺一不補 0、半套不入快取
# ══════════════════════════════════════════════════════════════════════════
def _weekdays(n: int) -> list[dt.date]:
    out, d = [], dt.date.today()
    while len(out) < n:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return sorted(out)


_D = _weekdays(5)
_DK = [d.strftime('%Y%m%d') for d in _D]
#: (多方 OI, 空方 OI)。MTX 刻意含 0.25 倍後為 .5 / .75 的淨口（round 與相加順序都會被測到）。
_TX = [(1200, 3400), (5000, 1000), (777, 778), (0, 0), (4321, 1234)]
_MTX = [(10, 7), (100, 106), (3, 13), (20000, 1), (5, 5)]
#: 修前基底（`e9fbd6c4`）實跑寫死：兩支都有時的「外資大小」。
_GOLDEN_FAST = [-2199, 3998, -3, 5000, 3087]
_GOLDEN_OI = dict(zip(_DK, [-2199, 3998, -4, 5000, 3087]))

_tok = itertools.count()


def _frame(vals, skip=()):
    rows = []
    for i, (d, (lo, sh)) in enumerate(zip(_D, vals)):
        if i in skip:
            continue
        rows.append(dict(date=d.isoformat(), institutional_investors='外資',
                         long_open_interest_balance_volume=lo,
                         short_open_interest_balance_volume=sh))
        rows.append(dict(date=d.isoformat(), institutional_investors='投信',
                         long_open_interest_balance_volume=99,
                         short_open_interest_balance_volume=1))
    return pd.DataFrame(rows)


def _patch(mp, tx, mtx, calls=None):
    def _fake(ds, did, s, e, tok=''):
        if calls is not None:
            calls.append((ds, did))
        if ds == 'TaiwanFuturesInstitutionalInvestors':
            return (tx if did == 'TX' else mtx).copy()
        return pd.DataFrame()

    def _no_taifex():
        raise RuntimeError('offline')

    mp.setattr(LI, 'finmind_get', _fake)
    mp.setattr(LI, '_twse_margin_day', lambda d: {})
    mp.setattr(LI, 'twse_volume', lambda m: {})
    mp.setattr(LI, 'twse_volume_daily', lambda d: None)
    mp.setattr(LI, '_bps', _no_taifex)
    mp.setattr(LI.time, 'sleep', lambda s: None)
    mp.setattr(LI, 'taifex_post', lambda *a, **k: '')


def _fast(mp, tmp_path, tx, mtx):
    _patch(mp, tx, mtx)
    mp.setattr(CL, '_PKL_DIR', str(tmp_path))
    df = LI.build_leading_fast(days=7, token=f'z25-{next(_tok)}')
    by_day = dict(zip(df['_date'], df['外資大小']))
    cached = any(f.endswith('.pkl') for f in os.listdir(tmp_path))
    return [by_day.get(k) for k in _DK], cached


_EMPTY = pd.DataFrame()
_NO_COL = pd.DataFrame([{'date': _D[0].isoformat(), 'long_open_interest_balance_volume': 1,
                         'short_open_interest_balance_volume': 2}])


class TestBuildLeadingFast:
    def test_both_present_golden_and_cached(self, monkeypatch, tmp_path):
        vals, cached = _fast(monkeypatch, tmp_path, _frame(_TX), _frame(_MTX))
        assert vals == _GOLDEN_FAST
        assert all(type(v) is int for v in vals)
        assert cached

    @pytest.mark.parametrize('tx, mtx', [
        pytest.param(_EMPTY, _frame(_MTX), id='tx-empty'),
        pytest.param(_frame(_TX), _EMPTY, id='mtx-empty'),
        pytest.param(_NO_COL, _frame(_MTX), id='tx-no-investor-column'),
    ])
    def test_one_contract_missing_is_none_and_not_cached(self, monkeypatch, tmp_path, tx, mtx):
        vals, cached = _fast(monkeypatch, tmp_path, tx, mtx)
        assert vals == [None] * 5          # 修前 tx-empty 為 0.25×MTX（[1, -2, -2, 5000, 0]）
        assert not cached

    def test_single_day_missing_one_side(self, monkeypatch, tmp_path):
        vals, cached = _fast(monkeypatch, tmp_path, _frame(_TX, skip={2}), _frame(_MTX, skip={4}))
        # 混入缺值後 pandas 把該欄轉 float／NaN（與修前「某天整天沒有期貨列」同一既有行為）。
        assert [pd.isna(v) for v in vals] == [False, False, True, False, True]
        assert [vals[i] for i in (0, 1, 3)] == [_GOLDEN_FAST[i] for i in (0, 1, 3)]
        assert cached                      # 兩支整體都有 ⇒ 照舊快取（缺的那天誠實記 None）


def _oi(mp, tx, mtx, *, ctx=False):
    calls: list = []
    _patch(mp, tx, mtx, calls)
    if ctx:   # 模擬 Streamlit 腳本執行中 ⇒ `_safe_cache` 走 st.cache_data
        import streamlit.runtime.scriptrunner as _sr
        mp.setattr(_sr, 'get_script_run_ctx', lambda *a, **k: object())
    tok = f'z25-oi-{next(_tok)}'
    args = (_DK[0], _DK[-1], tok)
    first = LI.finmind_fut_oi(*args)
    n1 = len(calls)
    second = LI.finmind_fut_oi(*args)
    return first, second, n1, len(calls) - n1


class TestFinmindFutOi:
    def test_both_present_golden(self, monkeypatch):
        first, _s, _n1, _n2 = _oi(monkeypatch, _frame(_TX), _frame(_MTX))
        assert first == _GOLDEN_OI
        assert list(first) == list(_GOLDEN_OI)      # 鍵序同修前
        assert all(type(v) is int for v in first.values())

    @pytest.mark.parametrize('tx, mtx', [
        pytest.param(_EMPTY, _frame(_MTX), id='tx-empty'),
        pytest.param(_frame(_TX), _EMPTY, id='mtx-empty'),
    ])
    def test_one_contract_missing_falls_back_not_half(self, monkeypatch, tx, mtx):
        first, *_ = _oi(monkeypatch, tx, mtx)
        assert first == {}                 # TAIFEX 備援（本測離線）也空 ⇒ 不回 0.25×MTX 半套

    def test_single_day_missing_one_side(self, monkeypatch):
        first, *_ = _oi(monkeypatch, _frame(_TX, skip={1}), _frame(_MTX))
        exp = dict(_GOLDEN_OI)
        exp[_DK[1]] = None
        assert first == exp

    def test_complete_result_is_cached(self, monkeypatch):
        first, second, n1, n2 = _oi(monkeypatch, _frame(_TX), _frame(_MTX), ctx=True)
        assert first == second == _GOLDEN_OI
        assert n1 == 2 and n2 == 0

    @pytest.mark.parametrize('tx, mtx', [
        pytest.param(_EMPTY, _frame(_MTX), id='tx-empty'),
        pytest.param(_frame(_TX), _EMPTY, id='mtx-empty'),
    ])
    def test_half_result_not_cached(self, monkeypatch, tx, mtx):
        first, second, n1, n2 = _oi(monkeypatch, tx, mtx, ctx=True)
        assert first == second == {}
        assert n1 == 2 and n2 == 2         # 第二次照樣重抓（失敗不入快取）


# ══════════════════════════════════════════════════════════════════════════
# Z16-n1：作戰室「外資方向」未取得 ⇒ 灰，不畫紅框 ⚠️
# ══════════════════════════════════════════════════════════════════════════
_FK = '外資及陸資'
_GRAY = '#484f58'
#: 修前基底（`e9fbd6c4`）實跑寫死：「外資方向」未取得時的整格輸出（紅框 ⚠️）。
_PRE_UNKNOWN_CARD = (
    "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #ef4444;"
    "border-radius:8px;padding:8px 10px;margin:2px 0;min-height:108px;display:flex;"
    "flex-direction:column;justify-content:space-between;'><div><div style='font-size:11px;"
    "color:#8b949e;'>⚠️ 外資方向</div><div style='font-size:15px;font-weight:800;color:#ef4444;"
    "margin:5px 0;line-height:1.25;'>未知</div></div><div style='font-size:10px;color:#484f58;"
    "line-height:1.3;'>外資買超=跟著走</div></div>")


def undo_z25_gray_card(out):
    """把修後「外資方向」灰框 ⬜ 那一格換回修前紅框 ⚠️ 寫法（只動該格的 3 處；其他格不碰）。

    供既有作戰室整段 golden 測試（批 Z6／Z9 第 2 組／Z16）沿用修前 golden：那些測試守的不是這一格，
    這一格的修後行為由本檔 `TestWarroomForeignDirectionGray` 守。
    """
    def _one(t):
        if '⬜ 外資方向</div>' not in t:
            return t
        return (t.replace(f'border-top:3px solid {_GRAY};', f'border-top:3px solid {TRAFFIC_RED};')
                 .replace(f'font-weight:800;color:{_GRAY};', f'font-weight:800;color:{TRAFFIC_RED};')
                 .replace('⬜ 外資方向</div>', '⚠️ 外資方向</div>'))
    return [(k, _one(t)) for k, t in out]


def _wr(inst, mp):
    mp.setattr(AS, 'get_allocation', lambda *a, **k: build_allocation_decision(None))
    fake = _FakeST({'bias_info': {'price': 20000.0, 'ma240': 19000.0, 'bias_240': 5.3},
                    'cl_data': {'margin': 2000.0, 'inst': inst},
                    'warroom_summary': {'futures_net': None}})
    mp.setattr(W, 'st', fake)
    W.render_section_warroom('bull', True, False)
    # 批 Z26（Z25-(b)）：本組以未載入的 allocation 實跑 ⇒「持股比例」修後改灰框 ⬜ ⇒ 換回修前紅框再比修前 golden
    #   （該格由 test_batch_z26 守）。本組「融資餘額」「年線位置」皆有值，還原不碰。
    return undo_z26_gray_card(list(fake.out))


def _rows(net):
    return {_FK: {'net': net}, '投信': {'net': 1.0}, '自營商': {'net': -1.0}}


def _fnet_card(out) -> str:
    cards = [t for _k, t in out if '外資方向</div>' in t]
    assert len(cards) == 1
    return cards[0]


class TestWarroomForeignDirectionGray:
    @pytest.mark.parametrize('inst', [
        pytest.param(InstNetDict(_rows(0.0), unobserved_net={_FK}), id='unobserved-prefill'),
        pytest.param({'投信': {'net': 1.0}}, id='no-foreign-row'),
        pytest.param({}, id='inst-empty'),
    ])
    def test_none_is_gray(self, monkeypatch, inst):
        card = _fnet_card(_wr(inst, monkeypatch))
        assert f'border-top:3px solid {_GRAY};' in card
        assert f"font-weight:800;color:{_GRAY};" in card
        assert '⬜ 外資方向' in card
        assert f"line-height:1.25;'>未知</div>" in card     # 文字不變
        assert TRAFFIC_RED not in card and '⚠️' not in card

    def test_undo_restores_pre_fix_card(self, monkeypatch):
        """還原替換只改「外資方向」一格，且還原後等於修前紅框寫法（修前基底實跑字面）。"""
        out = _wr({}, monkeypatch)
        undone = undo_z25_gray_card(out)
        diff = [(a, b) for a, b in zip(out, undone) if a != b]
        assert len(diff) == 1
        assert _fnet_card(undone) == _PRE_UNKNOWN_CARD

    def test_other_cards_untouched(self, monkeypatch):
        out = _wr(InstNetDict(_rows(0.0), unobserved_net={_FK}), monkeypatch)
        joined = '\x1e'.join(t for _k, t in out)
        assert joined.count('⬜ 外資方向') == 1
        assert joined.count(f'border-top:3px solid {_GRAY};') == 1
        assert f'border-top:3px solid {TRAFFIC_GREEN};' in joined   # 其他格照舊

    #: 修前基底（`e9fbd6c4`）實跑寫死：整段輸出 sha256（kind\x1ftext 以 \x1e 串接）。
    @pytest.mark.parametrize('net, golden', [
        (25.4, '0a83b21ff62466eb79ffb90ddf70ff6073ed0cd319556dca4c592c2caca7e81b'),
        (-30.0, '61fc9e1edd345f2a496fe64fbcedfa5987b66d88946b90b9359ac6b90ac0b470'),
        (0.0, '6153e3fa84ed524496d642d4603b091f6be9e32f20dc45f002ae49b79a1bb97d'),
        (0.4, 'e7f044ce2e134159942a547e5d32b3073643af1f41d4e4149358dbee053c3b45'),
        (-0.6, 'cfe91f7c5f062fe5c27fa1222ae43a81ed9d5b616f0e73499b8e693ff17d9ddb'),
        (1234567.8, 'b1c6d9f6a6390e5a508ce10a52a8d677feff9f7d7f3d390a93079aea53e78af1'),
        (-1e-9, '6153e3fa84ed524496d642d4603b091f6be9e32f20dc45f002ae49b79a1bb97d'),
    ])
    def test_finite_output_unchanged(self, monkeypatch, net, golden):
        out = _wr(InstNetDict(_rows(net)), monkeypatch)
        j = '\x1e'.join(f'{k}\x1f{t}' for k, t in out)
        assert hashlib.sha256(j.encode()).hexdigest() == golden
