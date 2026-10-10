"""批 Z35 —— 客戶 2026-10-10 裁示 Q-z15＝A、Q-z16＝A'（修正版）、Q-z17＝A（基底 origin/main `26a43064`）。

- Q-z15（Z33-n1，L2 `macro_helpers.calc_traffic_light`）：外資淨額「未觀測」（`InstNetDict.unobserved_net`，
  F1 BFI82U 缺列／'--' 預填 0、F2 FinMind buy 或 sell NaN 補零推出）⇒ 當缺值：走 net 為 None 的既有路徑
  （信心扣 20、缺失清單列既有「外資買賣超 (三大法人)」、`conf_groups` 同缺 key ⇒ 燈號閘門照既有機制）。
  觀測值（含觀測到的 0）逐字不變。forward-test 落地列（conf／missing_sources）因此與缺 key 時一致（預期效果）。
- Q-z16（Z33-n2，L3 `market_assessment_apply` → L2 `market_strategy.market_regime`）：外資淨額未觀測 ⇒
  不再出「➖ 外資買賣相抵（持平，0 分）」；0 分不變；未觀測無法可靠區分「尚未發布」與「取得失敗」
  （BFI82U 回 stat OK 且有表、FinMind 有當日列，只是外資格不可用）⇒ 不猜原因，走同頁（總經分頁）§三 籌碼卡
  既有不帶原因的缺值字「外資買賣超 ⬜ 未取得」；不另抓備援（`fetch_market_data`）。觀測到的 0 照舊「持平」。
- Q-z17（Z32-n1，L5 `section_chips.py`「🎯 籌碼綜合判斷」）：有效（非 None）項數 < 2 ⇒ 既有「⬜ 無法判定」、
  灰、不給操作建議；≥ 2 項 ⇒ 計分／門檻／結論逐字不變；「📌 ○○ 未取得」照舊。

golden：修前輸出於基底 `26a43064` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
突變：`Z35_REVERT_PAIRS` 為「修後逐字 → 修前逐字」（恰一處替換）；還原體重現修前行為 ⇒ 對應斷言轉紅（本檔自證）。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import math
import types

import pandas as pd
import pytest

import src.compute.macro.macro_helpers as MH
import src.services.market_assessment_apply as MAA
import src.services.market_strategy as MS
import src.ui.tabs.macro.section_chips as SC
from shared.colors import TRAFFIC_NEUTRAL
import tests.test_batch_z31 as Z31
from tests.test_batch_z31 import Z35_QZ17_CHIPS_PAIR
from tests.test_batch_z33_inst import MISSING_KEY, OBSERVED, UNOBSERVED, _drop_foreign

_MISS_LABEL = '外資買賣超 (三大法人)'      # calc_traffic_light 既有缺失名稱（逐字）
_MA_MISSING = '外資買賣超 ⬜ 未取得'        # 同頁 §三 籌碼卡既有字（section_chips.py，逐字）


def _h(x) -> str:
    return hashlib.sha256(repr(x).encode('utf-8')).hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# 還原體：本批改動逐字換回基底 `26a43064`（修後逐字, 修前逐字）—— 正式碼一改即找不到替換點而失敗（字面錨點）
# ══════════════════════════════════════════════════════════════════════════
Z35_REVERT_PAIRS = {
    'tl': ((
        "    # 批 Z35（Q-z15，客戶 2026-10-10 核准 A）：外資淨額「未觀測」（L1 缺列預填 0／L3 補零推出，\n"
        "    #   `shared/inst_net.is_net_observed`）⇒ 當缺值（同 net 為 None 的既有路徑：信心扣 20、缺失列\n"
        "    #   「外資買賣超 (三大法人)」、燈號閘門照既有機制）；觀測值逐字不變。\n"
        "    _fnet   = (_safe_float(_inst.get(_fk, {}).get('net'))\n"
        "               if _fk and is_net_observed(_inst, _fk) else None)\n",
        "    _fnet   = _safe_float(_inst.get(_fk, {}).get('net')) if _fk else None\n"),),
    'maa': (
        ("from shared.inst_net import is_net_observed  # 批 Z35（Q-z16）：外資淨額未觀測（L1 預填／L3 補零推出）不當真值\n",
         ""),
        ("        # 批 Z35（Q-z16，客戶 2026-10-10 核准 A'）：外資淨額未觀測 ⇒ 當缺值（分數 0 不變），\n"
         "        #   不得再顯示「外資買賣相抵（持平）」；文案改由 L2 依本旗標走同頁既有不帶原因的缺值字。\n"
         "        _foreign_unobserved = False\n", ""),
        ("                if not is_net_observed(inst, _k):\n"
         "                    _foreign_unobserved = True\n"
         "                elif _net_v is not None:\n",
         "                if _net_v is not None:\n"),
        ("            m1b_m2_is_proxy=_m1b2_is_proxy,\n"
         "            foreign_net_unobserved=_foreign_unobserved,\n",
         "            m1b_m2_is_proxy=_m1b2_is_proxy,\n"),
        ("                                            m1b_m2_is_proxy=_m1b2_is_proxy,\n"
         "                                            foreign_net_unobserved=_foreign_unobserved)\n",
         "                                            m1b_m2_is_proxy=_m1b2_is_proxy)\n"),
    ),
    'ms': (
        ("                  ma120_rising=False, ma120_falling=False,\n"
         "                  m1b_m2_is_proxy=False, foreign_net_unobserved=False):\n",
         "                  ma120_rising=False, ma120_falling=False,\n"
         "                  m1b_m2_is_proxy=False):\n"),
        ("    # 批 Z35（Q-z16，客戶 2026-10-10 核准 A'）：外資淨額「未觀測」（呼叫端以 `foreign_net_unobserved`\n"
         "    #   告知，foreign_buy 已為 None ⇒ 0 分不變）⇒ 無法可靠區分「尚未發布」與「取得失敗」，不猜原因 ——\n"
         "    #   走同頁 §三 籌碼卡既有不帶原因的缺值字（section_chips 批 Z33 起同一情境即顯示此字），⛔ 不出「相抵／持平」。\n"
         "    if foreign_buy is None and foreign_net_unobserved:\n"
         "        signals.append('外資買賣超 ⬜ 未取得')\n"
         "    elif foreign_buy is None:\n",
         "    if foreign_buy is None:\n"),
        ("                          m1b_m2_is_proxy=False, foreign_net_unobserved=False):\n",
         "                          m1b_m2_is_proxy=False):\n"),
        ("    # 批 Z35（Q-z16）：外資淨額「未觀測」＝ 呼叫端已拿到當日表但外資格不是觀測值 ⇒ 不另抓備援\n"
         "    #   （分數維持 0、不改模型；備援 `fetch_market_data` 讀同一 FinMind 資料集，缺 buy／sell 時\n"
         "    #   以 `.get(…, 0)` 推淨額），只把旗標交給 market_regime 決定文案。\n"
         "    if foreign_net is None and not foreign_net_unobserved:\n",
         "    if foreign_net is None:\n"),
        ("        m1b_m2_is_proxy=m1b_m2_is_proxy, foreign_net_unobserved=foreign_net_unobserved,\n",
         "        m1b_m2_is_proxy=m1b_m2_is_proxy,\n"),
    ),
    # 單一來源：與 test_batch_z31 串接的同一對（該檔 Q-z11 錨點含本批改的那一行）
    'chips': (Z35_QZ17_CHIPS_PAIR,),
}
_MODS = {'tl': MH, 'maa': MAA, 'ms': MS, 'chips': SC}
#: 還原後原始碼 sha256 ＝ 基底 `26a43064` 該檔（證明還原體就是修前碼）
_PRE_FILE_SHA = {
    'tl': '163d4e0d76084fabc55bffa1676007739ad449889bd32cfc9c15b41465fccc57',
    'maa': 'd58062957564e7868869ce6d0c8f9a7c7bf9ff8eb9bb7349f60788f2bb00b59c',
    'ms': '62edcaa1de9e0d8e3caf0168a8ed7987aa6d974677c463a15141522ef1381fa3',
    'chips': '749283102c6682af6a4a594f266f35f5dbee7dc7b639fea43f9560a10beb7965',
}


def _pre_source(k) -> str:
    # 📌 批 Z36（Q-z18／Q-z20，客戶 2026-10-10 核准 A，有意識的變更，⛔ 不是漏改）：本批改了 'ms'（整包未取得改缺值字）
    #   與 'chips'（投信／自營未觀測）—— 還原體一併換回本批那幾行（仍逐字等於基底 26a43064，`_PRE_FILE_SHA` 不改；
    #   同 Z33 串接 Z34 慣例）。⛔ 不動 `Z35_REVERT_PAIRS` 本身。
    from tests.test_batch_z36 import z36_pairs_for
    src = open(_MODS[k].__file__, encoding='utf-8').read()
    for new, old in z36_pairs_for(_MODS[k].__file__) + Z35_REVERT_PAIRS[k]:
        assert src.count(new) == 1, f'替換點不唯一或已不存在：{new!r}'
        src = src.replace(new, old)
    return src


@functools.lru_cache(maxsize=None)
def z35_pre_module(k):
    """現行模組只把本批改動換回基底 `26a43064` 寫法（獨立模組物件，不影響本尊）。"""
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(f'_z35_pre_{k}', loader=None))
    m.__file__ = _MODS[k].__file__
    exec(compile(_pre_source(k), _MODS[k].__file__, 'exec'), m.__dict__)
    return m


class TestRevertBodiesAreBase:
    @pytest.mark.parametrize('k', sorted(Z35_REVERT_PAIRS))
    def test_reverted_source_equals_base_file(self, k):
        """還原體原始碼逐字 ＝ 基底 `26a43064` 檔案 ⇒ 下方「修前」對照與突變斷言都是真修前碼。"""
        assert hashlib.sha256(_pre_source(k).encode('utf-8')).hexdigest() == _PRE_FILE_SHA[k]


# ══════════════════════════════════════════════════════════════════════════
# 1. Q-z15：calc_traffic_light 外資未觀測 ⇒ 當缺值
# ══════════════════════════════════════════════════════════════════════════
def _li_df():
    return pd.DataFrame({'日期': ['10/1', '10/2'], '外資大小': [-12000.0, -8000.0], '韭菜指數': [10.0, 12.0]})


#: (mkt_info, jingqi_info, 有先行指標, 有 ADL)
_CTX = {
    'full': ({'score': 4, 'max_score': 6, 'regime': 'bull'}, {'avg': 55.0}, True, True),
    'weak': ({'score': 1, 'max_score': 6, 'regime': 'neutral'}, {'avg': 30.0}, True, True),
    'no_li_no_adl': ({'score': 3, 'max_score': 6, 'regime': 'neutral'}, {'avg': 50.0}, False, False),
}


def _tl(inst, ctx, mod=MH):
    mkt, jq, li, adl = _CTX[ctx]
    cd = {'inst': inst}
    if adl:
        cd['adl'] = pd.DataFrame({'ad_ratio': [50.0]})
    return mod.calc_traffic_light(dict(mkt), dict(jq), cd, _li_df() if li else None)


#: 修前（基底 `26a43064`）同一支 harness 實跑的 sha256（觀測值必須逐字不變）
_TL_GOLDEN = {
    ('obs_buy_150', 'full'): '04201af536f7942b60bf2a8290a01a35cf7f863c9f9c9c798e2178aacf45de6a',
    ('obs_buy_150', 'no_li_no_adl'): 'fbef032f562b03eda27184e0c3a60f6bfba6a2c5cb7c67c4a4027a45b07231af',
    ('obs_buy_150', 'weak'): '35fcd792997954ad29032668398a119d639010da2895f36d6661c56f315e305a',
    ('obs_sell_201', 'full'): '7acac4b0db895a9c88ff77bee0cff8872808693917feec26afc115d15664e21f',
    ('obs_sell_201', 'no_li_no_adl'): 'a56b6cc639030de174c5d5e6a87642221f2c24e0b6334745408565987253e2e8',
    ('obs_sell_201', 'weak'): '378da8617e0af812e411edb1df09670cac9bcde929e422a1c2e2f1f023b1f4d7',
    ('obs_zero', 'full'): '8680b1984ab5749695f284b766308e2d727d1ae0bd56c96cc3ef0843f8b93032',
    ('obs_zero', 'no_li_no_adl'): '89f96266cb04c12a2986c42aec7c43e07393e3f44568cbc7e67352cc97d010fa',
    ('obs_zero', 'weak'): '39ade08cdda2eb1742a2453dbee8d89dd25b145b883d12c5cd76b3140fb841e8',
    ('plain_dict_150', 'full'): '04201af536f7942b60bf2a8290a01a35cf7f863c9f9c9c798e2178aacf45de6a',
    ('plain_dict_150', 'no_li_no_adl'): 'fbef032f562b03eda27184e0c3a60f6bfba6a2c5cb7c67c4a4027a45b07231af',
    ('plain_dict_150', 'weak'): '35fcd792997954ad29032668398a119d639010da2895f36d6661c56f315e305a',
}


def _without_fk(r):
    """缺 key 時 `fk` 為 None、未觀測時為 key 名（無消費端讀 `fk`）—— 比對其餘全部欄位。"""
    return {k: v for k, v in r.items() if k != 'fk'}


class TestQz15ObservedUnchanged:
    @pytest.mark.parametrize('name, ctx', sorted(_TL_GOLDEN))
    def test_golden(self, name, ctx):
        assert _h(_tl(OBSERVED[name](), ctx)) == _TL_GOLDEN[(name, ctx)]

    @pytest.mark.parametrize('ctx', sorted(_CTX))
    def test_observed_zero_counts_as_data(self, ctx):
        """觀測到的 0（真的持平）仍是有效資料：不列缺失、fnet 0.0。"""
        r = _tl(OBSERVED['obs_zero'](), ctx)
        assert r['fnet'] == 0.0 and _MISS_LABEL not in r['missing_sources']

    @pytest.mark.parametrize('ctx', sorted(_CTX))
    def test_other_row_unobserved_does_not_matter(self, ctx):
        """只有投信列未觀測：外資觀測值照舊（與同內容 plain dict 逐字相同）。"""
        inst = OBSERVED['other_row_unobserved']()
        assert _h(_tl(inst, ctx)) == _h(_tl(dict(inst), ctx))


class TestQz15UnobservedIsMissing:
    @pytest.mark.parametrize('ctx', sorted(_CTX))
    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_same_as_missing_key(self, name, ctx):
        """未觀測 ⇒ 與「同一份資料拿掉外資 key」（既有缺值路徑）除 `fk` 外逐欄相同。"""
        inst = UNOBSERVED[name]()
        r, m = _tl(inst, ctx), _tl(_drop_foreign(inst), ctx)
        assert r['fnet'] is None
        assert r['conf'] == m['conf'] and r['missing_sources'] == m['missing_sources']
        assert r['conf_groups'] == m['conf_groups']
        assert _h(_without_fk(r)) == _h(_without_fk(m))

    @pytest.mark.parametrize('ctx', sorted(_CTX))
    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_conf_minus_20_and_listed(self, name, ctx):
        """信心依既有規則扣 20（1/5 項）、缺失清單列既有字「外資買賣超 (三大法人)」。"""
        r = _tl(UNOBSERVED[name](), ctx)
        obs = _tl(OBSERVED['obs_zero'](), ctx)
        assert r['conf'] == obs['conf'] - 20
        assert _MISS_LABEL in r['missing_sources'] and _MISS_LABEL not in obs['missing_sources']
        assert r['conf_groups']['twse_bfi82u'] is False

    def test_conf_values(self):
        assert [_tl(UNOBSERVED['f1_missing_row'](), c)['conf'] for c in ('full', 'no_li_no_adl')] == [80, 40]
        assert [_tl(OBSERVED['obs_zero'](), c)['conf'] for c in ('full', 'no_li_no_adl')] == [100, 60]

    @pytest.mark.parametrize('name', sorted(MISSING_KEY))
    def test_missing_key_unchanged(self, name):
        """缺 key（既有路徑）修前修後逐字相同。"""
        for ctx in _CTX:
            inst = MISSING_KEY[name]()
            assert _h(_tl(inst, ctx)) == _h(_tl(inst, ctx, z35_pre_module('tl')))


def _render_gate(tl):
    """走真的 `handlers._render_traffic_light`（既有閘門）；回傳畫面文字。"""
    import src.ui.tabs.macro.handlers as H
    from tests.test_m2n2_no_zero_fill import _FakeST
    fake = _FakeST(session_state={'chips_loaded': True})
    _orig, H.st = H.st, fake
    try:
        H._render_traffic_light(fake, tl, None, requested=True)
    finally:
        H.st = _orig
    return '\n'.join(t for _k, t in fake.out)


_BLOCKED = '燈號無法計算'


class TestQz15Gate:
    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_gate_follows_existing_mechanism(self, name):
        """沒有先行指標與 ADL 時：外資未觀測 ⇒ 兩個獨立域全滅 ⇒ 既有閘門擋燈並逐項列缺（與缺 key 同）；
        同情境觀測到的 0 ⇒ 照舊出燈。"""
        inst = UNOBSERVED[name]()
        txt = _render_gate(_tl(inst, 'no_li_no_adl'))
        assert _BLOCKED in txt and f'❌ {_MISS_LABEL}' in txt
        assert txt == _render_gate(_tl(_drop_foreign(inst), 'no_li_no_adl'))
        assert _BLOCKED not in _render_gate(_tl(OBSERVED['obs_zero'](), 'no_li_no_adl'))

    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_not_blocked_when_other_domain_alive(self, name):
        """先行指標仍在 ⇒ 既有閘門照舊出燈（conf 80%，缺項警示列外資）。"""
        txt = _render_gate(_tl(UNOBSERVED[name](), 'full'))
        assert _BLOCKED not in txt and _MISS_LABEL in txt


class TestQz15ForwardTestRow:
    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_row_conf_missing_same_as_missing_key(self, name):
        """forward-test 落地列（`build_signal_row`）的 conf／missing_sources／conf_groups 與缺 key 時一致（預期效果）。"""
        from src.compute.macro.macro_forward_test import build_signal_row
        inst = UNOBSERVED[name]()
        kw = dict(date='2026-10-09', captured_at='2026-10-09T18:00:00+08:00', twii_close=None,
                  inputs_as_of=None, git_sha='x', ruleset_hash='y')
        a = build_signal_row(_tl(inst, 'full'), **kw)
        b = build_signal_row(_tl(_drop_foreign(inst), 'full'), **kw)
        assert a == b
        assert a['conf'] == 80 and _MISS_LABEL in a['missing_sources']


class TestQz15Mutation:
    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_pre_fix_counted_unobserved_as_data(self, name):
        """還原體（修前）：未觀測仍當有資料（conf 100、不列缺失）⇒ 上方 TestQz15UnobservedIsMissing 轉紅。"""
        r = _tl(UNOBSERVED[name](), 'full', z35_pre_module('tl'))
        assert r['conf'] == 100 and _MISS_LABEL not in r['missing_sources'] and r['fnet'] is not None


# ══════════════════════════════════════════════════════════════════════════
# 2. Q-z16：市場評估外資訊號
# ══════════════════════════════════════════════════════════════════════════
def _tw_raw():
    idx = pd.date_range(end=pd.Timestamp.now().normalize(), periods=260, freq='D')
    return {'台股加權指數': pd.DataFrame({'Close': [17000.0 + 3 * i for i in range(260)],
                                       'Volume': [1000.0 + i for i in range(260)]}, index=idx)}


def _ma(inst, monkeypatch, *, maa=MAA, ms=MS):
    """實跑 compute_and_apply_market_assessment（真 get_market_assessment；備援抓取以 spy 擋網路、回 None）。"""
    calls = []

    def _spy():
        calls.append(1)
        return {'foreign_net': None, 'date': ''}
    ss = {}
    monkeypatch.setattr(maa, 'st', types.SimpleNamespace(session_state=ss))
    monkeypatch.setattr(ms, 'fetch_market_data', _spy)
    monkeypatch.setattr('src.services.get_market_assessment', ms.get_market_assessment)
    maa.compute_and_apply_market_assessment(inst=inst, tw_raw=_tw_raw(), margin=2000.0,
                                            df_adl=pd.DataFrame({'ad_ratio': [60.0]}))
    return ss['mkt_info'], len(calls)


#: 修前（基底 `26a43064`）同一支 harness 實跑：mkt_info 的 sha256
_MA_GOLDEN = {
    'obs_buy_150': 'eb908a3d49d45c601ae16efe628826f817ae39250f5614c49de603a4030ec648',
    'obs_sell_201': 'd68a02c8e4ebfab4127efca34f27c084371e972f2151931096bf54df6cfa5419',
    'obs_zero': '1631482e2071512c287b27e4a0d7d8f3df948a098ff4c471daf23a9984d4c254',
    'plain_dict_150': 'eb908a3d49d45c601ae16efe628826f817ae39250f5614c49de603a4030ec648',
}
_WAIT = '⏰ 外資數據待更新（收盤後15:30可用）'
_FLAT = '➖ 外資買賣相抵（持平，0 分）'


def _fsig(r):
    return [s for s in r['signals'] if '外資' in s]


class TestQz16ObservedUnchanged:
    @pytest.mark.parametrize('name', sorted(_MA_GOLDEN))
    def test_golden(self, name, monkeypatch):
        r, n = _ma(OBSERVED[name](), monkeypatch)
        assert _h(r) == _MA_GOLDEN[name] and n == 0

    def test_observed_zero_still_flat(self, monkeypatch):
        """觀測到的真 0 ⇒ 照舊「持平」（觀測值不變）。"""
        r, _ = _ma(OBSERVED['obs_zero'](), monkeypatch)
        assert _fsig(r) == [_FLAT] and r['score'] == 4.0

    def test_missing_key_unchanged(self, monkeypatch):
        """缺 key（既有路徑）：照舊打備援；本批（Z35）未改其文案，修前修後除該句外逐字相同。

        📌 批 Z36（Q-z18，客戶 2026-10-10 核准 A，有意識的變更，⛔ 不是漏改）：缺 key 且備援也沒拿到時，
        「⏰ 外資數據待更新（收盤後15:30可用）」改為同頁既有「外資買賣超 ⬜ 未取得」（現行行為由 tests/test_batch_z36.py 斷言）。
        原斷言 `_fsig(r) == [_WAIT]` 改為現行字；修前還原體（已串接 Z36 pair）仍出 `_WAIT`，比對時只換那一句。"""
        inst = MISSING_KEY['no_foreign_key']()
        r, n = _ma(inst, monkeypatch)
        assert _fsig(r) == [_MA_MISSING] and n == 1
        monkeypatch.undo()
        p, pn = _ma(inst, monkeypatch, maa=z35_pre_module('maa'), ms=z35_pre_module('ms'))
        assert _fsig(p) == [_WAIT] and pn == 1
        assert _h(dict(r, signals=[_WAIT if s == _MA_MISSING else s for s in r['signals']])) == _h(p)


class TestQz16Unobserved:
    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_no_flat_and_existing_missing_text(self, name, monkeypatch):
        """未觀測 ⇒ 不出「相抵」「持平」，改同頁既有不帶原因的「外資買賣超 ⬜ 未取得」；不出「⏰ 待更新」（不猜原因）。"""
        r, _ = _ma(UNOBSERVED[name](), monkeypatch)
        txt = ' '.join(r['signals'])
        assert '相抵' not in txt and '持平' not in txt and '⏰' not in txt
        assert _fsig(r) == [_MA_MISSING]
        assert r['foreign_net'] is None

    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_score_zero_and_rest_same_as_missing(self, name, monkeypatch):
        """外資腿 0 分：除外資那一句外，mkt_info 與缺 key（既有缺值路徑）逐字相同；不另抓備援。"""
        inst = UNOBSERVED[name]()
        r, n = _ma(inst, monkeypatch)
        monkeypatch.undo()
        m, mn = _ma(_drop_foreign(inst), monkeypatch)
        assert n == 0 and mn == 1
        assert r['score'] == m['score'] == 4.0
        m2 = dict(m, signals=[_MA_MISSING if s == _WAIT else s for s in m['signals']])
        assert _h(r) == _h(m2)

    def test_the_string_exists_on_same_page(self):
        """沿用字串的出處：同頁（總經分頁）§三 籌碼卡外資判斷既有字（逐字）。"""
        src = open(SC.__file__, encoding='utf-8').read()
        assert f"_hye_ind = '{_MA_MISSING}'" in src


class TestQz16Mutation:
    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_pre_fix_showed_value(self, name, monkeypatch):
        """還原體（修前）：未觀測照舊讀預填／補零值（F1 ⇒「持平」）⇒ 上方 TestQz16Unobserved 轉紅。"""
        r, _ = _ma(UNOBSERVED[name](), monkeypatch, maa=z35_pre_module('maa'), ms=z35_pre_module('ms'))
        assert _MA_MISSING not in r['signals'] and r['foreign_net'] is not None
        if name.startswith('f1_'):
            assert _fsig(r) == [_FLAT]

    @pytest.mark.parametrize('name', sorted(UNOBSERVED))
    def test_only_maa_reverted_still_red(self, name, monkeypatch):
        """只還原 L3（不讀旗標）⇒ 仍讀預填值 ⇒ 轉紅。"""
        r, _ = _ma(UNOBSERVED[name](), monkeypatch, maa=z35_pre_module('maa'))
        assert _MA_MISSING not in r['signals']

    def test_only_ms_text_reverted_shows_wait(self, monkeypatch):
        """只把 L2 文案分支拿掉（保留其餘修正）⇒ 改出「⏰ 待更新」（猜原因）⇒ 轉紅。"""
        src = open(MS.__file__, encoding='utf-8').read()
        new, old = Z35_REVERT_PAIRS['ms'][1]
        assert src.count(new) == 1
        # 📌 批 Z36（Q-z18）：缺值文案另一分支本批已改字 ⇒ 先換回本批（基底 0ef68f93）寫法，本突變語意不變
        from tests.test_batch_z36 import z36_pairs_for
        for _n36, _o36 in z36_pairs_for(MS.__file__):
            assert src.count(_n36) == 1
            src = src.replace(_n36, _o36)
        m = importlib.util.module_from_spec(importlib.util.spec_from_loader('_z35_mut_ms', loader=None))
        m.__file__ = MS.__file__
        exec(compile(src.replace(new, old), MS.__file__, 'exec'), m.__dict__)
        r, _ = _ma(UNOBSERVED['f1_missing_row'](), monkeypatch, ms=m)
        assert _fsig(r) == [_WAIT]


# ══════════════════════════════════════════════════════════════════════════
# 3. Q-z17：籌碼綜合判斷有效項 < 2 ⇒ 無法判定
# ══════════════════════════════════════════════════════════════════════════
_ADVICE = ('建議大幅降倉，等待空單回補訊號', '籌碼不穩，建議觀望為主', '訊號分歧，小倉觀察，詳見策略手冊',
           '籌碼偏健康，可正常持倉', '聰明錢明顯佈多，積極持倉')
_KEYS = ('fnet', 'pcr', 'opt', 'top5', 'leek')


def _only(k, v):
    return {**{x: None for x in _KEYS}, k: v}


#: 只剩 1 項有效（其餘 4 項缺）：(項, 值, 該項訊號 —— 不出訊號者為 None)
_ONE = {
    'top5_neutral_-5000': ('top5', -5000.0, None),
    'top5_neutral_-10000': ('top5', -10000.0, None),
    'top5_neutral_0': ('top5', 0.0, None),
    'pcr_110_neutral_bias': ('pcr', 110.0, '🔵 PCR=110（偏多）'),
    'pcr_140_bull': ('pcr', 140.0, '🟢 PCR=140（>130強支撐）'),
    'pcr_90_bear': ('pcr', 90.0, '🔴 PCR=90（<100偏空）'),
    'fnet_bull': ('fnet', 5000.0, '✅ 期貨淨多 +5,000口'),
    'fnet_danger': ('fnet', -30000.0, '🔴 期貨空單 -30,000口（達3萬危險線）'),
    'opt_bull': ('opt', 20000.0, '🟢 外選 +20,000千元（多方佈局）'),
    'leek_hot': ('leek', 40.0, '🔴 韭菜指數40.0%（散戶過熱）'),
}

#: ≥ 2 項有效：修前（基底 `26a43064`）以 test_batch_z31 同一支 `_chips` harness 實跑的整段 §三 sha256
_TWO_PLUS_GOLDEN = {
    'two_neutral_pcr110_top5': (dict(fnet=None, opt=None, leek=None, pcr=110.0, top5=-5000.0),
                                '79f58b7bd1041365c5b48f5ddc95686afd3ee6bc30675d97a3fad0b12b22667e'),
    'two_zero_fnet_neg_pcr140': (dict(opt=None, top5=None, leek=None, fnet=-1000.0, pcr=140.0),
                                 '7f50843bac962b3ead564ecc8c95c42f04b64aec8703dad10118ba7727ed45f9'),
    'two_bull_fnet_opt': (dict(pcr=None, top5=None, leek=None, fnet=5000.0, opt=20000.0),
                          'c16033d40cfabe83d8eb79b96bee2bb67cabd3fe9f567eb80f53b482f657fc2b'),
    'two_bear_fnet_leek': (dict(pcr=None, top5=None, opt=None, fnet=-30000.0, leek=40.0),
                           '91e3f39d8b1a17bc51e2d9075263e31bcff1af6499519ec1d74be011ce046689'),
    'three_mixed': (dict(fnet=None, leek=None, pcr=90.0, opt=0.0, top5=3000.0),
                    '52e55ae890f017c2c5979362f7d258302a25888d653f554805f53ba8e347feb5'),
    'four_present': (dict(leek=None, fnet=100.0, pcr=150.0, opt=10000.0, top5=-10000.0),
                     '064b69067eeb58d2810f7d030f8bab8b7a33b1ae568494b1b8795f5ad86f9058'),
    'all_present_day': (dict(), '3d5c11c18c5b609df3c4331f56d539a7ae061b0cd73c1b8153c0f564ddf490f1'),
}


def _card(mp, mod=None, **vals):
    if mod is None:
        return Z31._card(mp, **vals)
    return Z31._card_of(Z31._chips_mod(Z31._li_last(**vals), mp, mod))


def _assert_cannot_judge(card):
    assert f'color:{TRAFFIC_NEUTRAL};">⬜ 無法判定</div>' in card
    assert f'border:2px solid {TRAFFIC_NEUTRAL}44;' in card
    for a in _ADVICE:
        assert a not in card
    assert '多空分歧' not in card and '建議' not in card
    assert 'margin:6px 0 10px 0' not in card            # 建議列整個不輸出


class TestQz17FewerThanTwo:
    @pytest.mark.parametrize('case', sorted(_ONE))
    def test_one_valid_cannot_judge(self, case, monkeypatch):
        """只剩 1 項有效（含中性不出訊號、單項偏多／偏空）⇒「⬜ 無法判定」、灰、無任何操作建議；
        訊號列照舊（4 個「📌 ○○ 未取得」＋該項既有訊號）。"""
        k, v, sig = _ONE[case]
        card = _card(monkeypatch, **_only(k, v))
        _assert_cannot_judge(card)
        want = [(sig if x == k else Z31._missing_tag(x)) for x in _KEYS if not (x == k and sig is None)]
        assert Z31._sigs(card) == want

    @pytest.mark.parametrize('case', sorted(_ONE))
    def test_signals_same_as_pre(self, case, monkeypatch):
        """除結論／建議外，卡片訊號列與修前同一份輸入逐字相同。"""
        k, v, _ = _ONE[case]
        card = _card(monkeypatch, **_only(k, v))
        monkeypatch.undo()
        pre = _card(monkeypatch, z35_pre_module('chips'), **_only(k, v))
        assert Z31._sigs(card) == Z31._sigs(pre)

    @pytest.mark.parametrize('bad', [None, math.nan, math.inf])
    def test_zero_valid_cannot_judge(self, bad, monkeypatch):
        _assert_cannot_judge(_card(monkeypatch, **{k: bad for k in _KEYS}))

    def test_one_valid_nan_others(self, monkeypatch):
        """其餘 4 項以 NaN／±inf 缺（非 None）同樣只算 1 項有效。"""
        _assert_cannot_judge(_card(monkeypatch, fnet=math.nan, pcr=math.inf, opt=-math.inf, leek=None, top5=-5000.0))


class TestQz17TwoOrMoreUnchanged:
    @pytest.mark.parametrize('case', sorted(_TWO_PLUS_GOLDEN))
    def test_golden(self, case, monkeypatch):
        """≥ 2 項有效（含 score 0）⇒ 整段 §三 與修前逐字相同。"""
        vals, gold = _TWO_PLUS_GOLDEN[case]
        assert Z31._digest(Z31._chips(Z31._li_last(**vals), monkeypatch)) == gold

    def test_two_neutral_still_divergent(self, monkeypatch):
        card = _card(monkeypatch, **_TWO_PLUS_GOLDEN['two_neutral_pcr110_top5'][0])
        assert '⚪ 多空分歧' in card and _ADVICE[2] in card and '⬜ 無法判定' not in card


class TestQz17Mutation:
    @pytest.mark.parametrize('case', sorted(_ONE))
    def test_pre_fix_gave_verdict(self, case, monkeypatch):
        """還原體（修前）：只剩 1 項有效仍給結論與操作建議 ⇒ 上方 TestQz17FewerThanTwo 轉紅。"""
        k, v, _ = _ONE[case]
        card = _card(monkeypatch, z35_pre_module('chips'), **_only(k, v))
        assert '⬜ 無法判定' not in card and any(a in card for a in _ADVICE)
