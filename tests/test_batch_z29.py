"""批 Z29 —— 客戶 2026-10-09 核准（基底 origin/main `b00288a3`）。

- Z24-n1（L5 `section_chips.py` §三「⚡ 進階警示」訊號 5 成交量萎縮／急放）：`成交量` 欄經 `pd.to_numeric`
  解析後可含 ±inf，修前印「今日成交量inf億…」「均量inf億的0%」⇒ 取到的任一筆非有限 → 整個訊號 5 不列
  （同批 Z24 訊號 1／3 作法）；⛔ 不得剔掉 inf 後拿前一天當今天。有限值逐字不變。
- Z26-n2（L5 `section_warroom.py` 作戰室「融資餘額」卡＋風險警示句）：`cl_data['margin']` NaN／±inf 修前印
  「nan億」並判色，+inf 還出「融資 inf億 極度危險」⇒ 非有限與缺值同路徑（「未取得 (N/A)」＋灰、無警示句）。
- C9-n6 (b)（同檔「外資方向」卡）：外資淨額真實觀測值剛好 0 修前印「賣超 0億」⇒ 改客戶核准字句
  「0億（持平）」（逐字）；第 3 欄判定值不變（📌 批 Z30 起依客戶 Q-z8＝B 改 None 灰框，見 TestForeignNetZero）。外資淨額 NaN／±inf ⇒ 走既有「未知」＋判定 None
  （與未觀測／None 同路徑；-inf 修前另出「外資賣超 inf億」警示句，一併不再出現）。

golden：有限值的修前輸出於基底 `b00288a3` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np
import pandas as pd
import pytest

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_warroom as W
from shared.allocation_decision import build_allocation_decision
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from shared.inst_net import InstNetDict
from tests.test_batch_z10 import _chips
from tests.test_batch_z21 import _txt
from tests.test_m2n2_no_zero_fill import _FakeST

_GRAY = '#484f58'
_FK = '外資及陸資'
_BIAS = {'price': 20000.0, 'ma240': 19000.0, 'bias_240': 5.3}
_UNLOADED = build_allocation_decision(None)
_INFNAN = re.compile(r'(?<![A-Za-z])(inf|nan|infinity)(?![A-Za-z])', re.I)


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode('utf-8')).hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# 1. Z24-n1：訊號 5 成交量非有限不列
# ══════════════════════════════════════════════════════════════════════════
def _li_v(vols):
    n = len(vols)
    return pd.DataFrame({'日期': [f'2026-10-0{i + 1}' for i in range(n)], '外資大小': [-1000.0] * n,
                         '選PCR': [110.0] * n, '成交量': pd.Series(vols, dtype=object)})


def _warn_txt(out) -> str:
    """只取「⚡ 進階警示」區塊（先行指標表會照實印原始欄值，不在本批範圍）。"""
    blocks = [t for _k, t in out if '⚡ 進階警示' in t]
    return re.sub(r'<[^>]+>', '', '\x1e'.join(blocks))


_S5_BAD = [
    pytest.param(['3000億', '3000億', '1000億', 'inf億'], id='last-pinf-str(prev-would-shrink)'),
    pytest.param(['3000億', '3000億', '9000億', '-inf億'], id='last-ninf-str(prev-would-surge)'),
    pytest.param(['3000億', '3000億', '3000億', 'Infinity'], id='last-Infinity'),
    pytest.param(['inf億', '3000億', '3000億', '1000億'], id='first-pinf(avg-inf)'),
    pytest.param(['3000億', '-inf億', '3000億', '9000億'], id='mid-ninf(avg-ninf)'),
    pytest.param([3000.0, 3000.0, 3000.0, math.inf], id='float-pinf'),
    pytest.param([3000.0, 3000.0, 3000.0, -math.inf], id='float-ninf'),
    pytest.param([3000.0, 3000.0, 3000.0, np.float64(np.inf)], id='np-pinf'),
    pytest.param(['3000億', 'nan', '3000億', 'inf億'], id='nan-dropped-plus-inf'),
]


class TestSignal5NonFinite:
    @pytest.mark.parametrize('vols', _S5_BAD)
    def test_signal5_not_listed(self, vols, monkeypatch):
        out = _chips(_li_v(vols), monkeypatch)
        txt = _txt(out)
        assert '成交量急萎縮' not in txt and '成交量急放' not in txt, txt
        assert '今日成交量' not in txt, txt
        assert not _INFNAN.search(_warn_txt(out)), _warn_txt(out)

    def test_not_shifted_to_previous_day(self, monkeypatch):
        """剔掉 inf 後前 3 筆（3000／3000／1000）本會判「急萎縮」——⛔ 不得拿前一天當今天。"""
        txt = _txt(_chips(_li_v(['3000億', '3000億', '3000億', '1000億', 'inf億']), monkeypatch))
        assert '成交量急萎縮' not in txt and '今日成交量1000億' not in txt


#: 修前基底 `b00288a3` 同一支 `_chips` 實跑的整段 §三 sha256（萎縮／急放／中性／不足 3 筆／nan 被 dropna）。
_S5_BASE = {
    'shrink': (['3000億', '3000億', '3000億', '1000億'], 'e2265454f7de6fca6ec9483a9dde80173fab2633b197ad0fc5583ac7d3a5d2e9'),
    'surge': (['3000億', '3000億', '3000億', '9000億'], 'd32d3b55693eb955c978255eee376dcbaabcf4b2e698b58a4f7bd9726a66dc72'),
    'neutral': (['3000億', '3000億', '3000億', '3100億'], '6a103966f9148e6f40565fbff3678c7e74412b5d191f2fcc4bfda44a308375ba'),
    'too_few': (['3000億', '1000億'], '840ff5ef84d4c81003901ff5e96c9f070be39f7188fa6bba60d525d04f74f381'),
    'nan_dropped': (['3000億', 'nan', '3000億', '3000億', '1000億'], 'f7e9f658c5b65f1fa53d073770dea56419ee3cf3539fa65fe7abf072215f60d0'),
    'float_shrink': ([3000.0, 2800.0, 3200.0, 1500.0, 1000.0], '88b81ecec634a19f6795f0c81f837fe25d333bbcba93a08e52a96f2e290e1c7a'),
}


class TestSignal5FiniteUnchanged:
    @pytest.mark.parametrize('case', sorted(_S5_BASE))
    def test_golden(self, case, monkeypatch):
        vols, gold = _S5_BASE[case]
        out = _chips(_li_v(vols), monkeypatch)
        if case == 'nan_dropped':
            # 📌 批 Z30（Z29-n1，客戶 2026-10-09 核准）：先行指標表「成交量」欄字串 'nan' 原照印「nan」⇒ 改印「-」。
            #   golden 不改（仍是修前基底實跑）；把該格換回原值後整段須逐字等於基底，且差異僅此一格。
            _d, _n = '<td><span style="color:#9CDCFE;">-</span></td>', '<td><span style="color:#9CDCFE;">nan</span></td>'
            assert sum(t.count(_d) for _k, t in out) == 1
            undone = [(k, t.replace(_d, _n)) for k, t in out]
            assert _digest(out) != gold
            out = undone
        assert _digest(out) == gold

    def test_still_alerts(self, monkeypatch):
        txt = _txt(_chips(_li_v(['3000億', '3000億', '3000億', '1000億']), monkeypatch))
        assert '今日成交量1000億（前3日均量3000億的33%）' in txt
        monkeypatch.undo()
        txt = _txt(_chips(_li_v(['3000億', '3000億', '3000億', '9000億']), monkeypatch))
        assert '今日成交量9000億（前均量3000億的300%）' in txt


# ══════════════════════════════════════════════════════════════════════════
# 作戰室 harness
# ══════════════════════════════════════════════════════════════════════════
def _rows(net) -> dict:
    return {_FK: {'net': net}, '投信': {'net': 1.0}, '自營商': {'net': -1.0}}


def _wr(mp, *, net=12.0, margin=2000.0, unobserved=False):
    mp.setattr(AS, 'get_allocation', lambda *a, **k: _UNLOADED)
    inst = InstNetDict(_rows(net), unobserved_net={_FK} if unobserved else frozenset())
    state = {'bias_info': _BIAS, 'cl_data': {'margin': margin, 'inst': inst},
             'warroom_summary': {'futures_net': None}}
    fake = _FakeST(state)
    mp.setattr(W, 'st', fake)
    W.render_section_warroom('bull', True, False)
    return list(fake.out)


def _card(out, name) -> str:
    cards = [t for _k, t in out if f'{name}</div>' in t]
    assert len(cards) == 1
    return cards[0]


def _val(text: str) -> str:
    return f"line-height:1.25;'>{text}</div>"


def _joined(out) -> str:
    return '\x1e'.join(t for _k, t in out)


_NONFINITE = [
    pytest.param(math.nan, id='nan'),
    pytest.param(math.inf, id='pinf'),
    pytest.param(-math.inf, id='ninf'),
    pytest.param(np.float64(np.nan), id='np-nan'),
    pytest.param(np.float64(np.inf), id='np-pinf'),
    pytest.param(np.float64(-np.inf), id='np-ninf'),
    pytest.param(np.float32(np.inf), id='f32-pinf'),
    # 總管補充規格：pd.NA 修前 `if _wr_margin`／`(pd.NA or 0)` 拋 TypeError 整段崩潰；-inf 修前融資印「-inf億」✅。
    pytest.param(pd.NA, id='pd-NA'),
]


# ══════════════════════════════════════════════════════════════════════════
# 2. Z26-n2：融資非有限 ⇒ 未取得 (N/A)＋灰、無融資警示句
# ══════════════════════════════════════════════════════════════════════════
class TestMarginNonFinite:
    @pytest.mark.parametrize('margin', _NONFINITE)
    def test_card_unavailable_gray(self, margin, monkeypatch):
        out = _wr(monkeypatch, margin=margin)
        card = _card(out, '融資餘額')
        assert _val('未取得 (N/A)') in card
        assert f'border-top:3px solid {_GRAY};' in card and '⬜ 融資餘額</div>' in card
        assert TRAFFIC_GREEN not in card and TRAFFIC_RED not in card

    @pytest.mark.parametrize('margin', _NONFINITE)
    def test_no_margin_warning(self, margin, monkeypatch):
        j = _joined(_wr(monkeypatch, margin=margin))
        assert '融資 ' not in j and '極度危險' not in j and '警戒，注意風險' not in j
        assert not _INFNAN.search(re.sub(r'<[^>]+>', '', j))

    @pytest.mark.parametrize('margin', _NONFINITE)
    def test_same_as_missing(self, margin, monkeypatch):
        got = _wr(monkeypatch, margin=margin)
        ref = _wr(monkeypatch, margin=None)
        assert _digest(got) == _digest(ref)

    #: 修前基底 `b00288a3` 實跑（正常／警戒／極危／np.float64）。
    _BASE = {
        'normal': (2000.0, 'd849910444e75f134db4dba93dbdda046b3603befa708d78dbfaca02242e8701'),
        'warn': (3000.0, '25d54dc45247b3ea01b804fceef296963c69e1381473c152d5436b8b2080f0be'),
        'overheat': (3500.0, 'dbd9c50e7391f90b7d67ada52c7ecb30f126bab1d90d6db0c30ef5de30b27b44'),
        'np_overheat': (np.float64(3600.4), 'f2b2259288a3349f94ef72c7f427603654307181d42c7356d3d77335cabb9584'),
    }

    @pytest.mark.parametrize('case', sorted(_BASE))
    def test_finite_unchanged(self, case, monkeypatch):
        m, gold = self._BASE[case]
        assert _digest(_wr(monkeypatch, margin=m)) == gold

    def test_finite_still_warns(self, monkeypatch):
        assert '融資 3500億 極度危險' in _joined(_wr(monkeypatch, margin=3500.0))
        assert '融資 3000億 警戒' in _joined(_wr(monkeypatch, margin=3000.0))


# ══════════════════════════════════════════════════════════════════════════
# 3. C9-n6 (b)：外資淨額剛好 0 ⇒「0億（持平）」；非有限 ⇒「未知」
# ══════════════════════════════════════════════════════════════════════════
_ZEROS = [
    pytest.param(0.0, id='zero-float'),
    pytest.param(-0.0, id='neg-zero'),
    pytest.param(0, id='zero-int'),
    pytest.param(np.float64(0.0), id='np-zero'),
]
#: 修前基底 `b00288a3` 實跑：外資淨額剛好 0（印「賣超 0億」、判定 False ⇒ 紅 ⚠️）的整段 sha256。
_PRE_ZERO_GOLD = '3b2f35af1f43bc2a52f3d4ec96f11a218643941f6cd6ac6993768a107d8e3b0e'


class TestForeignNetZero:
    @pytest.mark.parametrize('net', _ZEROS)
    def test_text(self, net, monkeypatch):
        card = _card(_wr(monkeypatch, net=net), '外資方向')
        assert _val('0億（持平）') in card
        assert _val('賣超 0億') not in card and _val('買超 0億') not in card   # 修前：「賣超 0億」

    @pytest.mark.parametrize('net', _ZEROS)
    def test_judgement_gray_after_qz8(self, net, monkeypatch):
        """判定值與修前相同（False ⇒ 紅 ⚠️）；把新字換回「賣超 0億」後整段等於修前基底實跑。

        📌 批 Z30 改（客戶 2026-10-09 Q-z8＝B）：剛好 0 第 3 欄判定改 None ⇒ 灰框 ⬜（原斷言 False ⇒ 紅框 ⚠️）。
        強度不減：改斷言灰框／⬜、無紅綠；把新字換回「賣超 0億」並把該卡灰框／灰字／⬜ 換回紅框／紅字／⚠️ 後，
        整段仍須逐字等於修前基底 `b00288a3` 實跑，且差異只在這一張卡。"""
        out = _wr(monkeypatch, net=net)
        card = _card(out, '外資方向')
        assert f'border-top:3px solid {_GRAY};' in card and '⬜ 外資方向</div>' in card
        assert TRAFFIC_RED not in card and TRAFFIC_GREEN not in card
        undone = [(k, t.replace(_val('0億（持平）'), _val('賣超 0億'))
                   .replace(f'border-top:3px solid {_GRAY};', f'border-top:3px solid {TRAFFIC_RED};')
                   .replace(f'font-weight:800;color:{_GRAY};', f'font-weight:800;color:{TRAFFIC_RED};')
                   .replace('⬜ 外資方向</div>', '⚠️ 外資方向</div>'))
                  if '外資方向</div>' in t else (k, t) for k, t in out]
        assert sum(a != b for a, b in zip(out, undone)) == 1
        assert _digest(undone) == _PRE_ZERO_GOLD
        assert _digest(out) != _PRE_ZERO_GOLD


class TestForeignNetNonFinite:
    @pytest.mark.parametrize('net', _NONFINITE)
    def test_unknown_gray(self, net, monkeypatch):
        out = _wr(monkeypatch, net=net)
        card = _card(out, '外資方向')
        assert _val('未知') in card
        assert f'border-top:3px solid {_GRAY};' in card and '⬜ 外資方向</div>' in card
        assert '外資賣超' not in _joined(out)
        assert not _INFNAN.search(re.sub(r'<[^>]+>', '', _joined(out)))

    @pytest.mark.parametrize('net', _NONFINITE)
    def test_same_as_unobserved(self, net, monkeypatch):
        got = _wr(monkeypatch, net=net)
        ref = _wr(monkeypatch, net=0.0, unobserved=True)
        assert _digest(got) == _digest(ref)


#: 修前基底 `b00288a3` 實跑（買超／賣超／賣超達警示／四捨五入成 0 的非 0 值）。
_F_BASE = {
    'buy': (25.4, '5683abec9fc6c88f5337c1781c6137dd0cfd8e8eff68bb7c80856e6a161e174a'),
    'sell': (-12.0, '66d6b452706b253b6d6f3c10a7a33a31c8b144fd7c7a942ba7a7b3551e477932'),
    'sell_warn': (-30.0, '66599b147157f1ad70b16b4206bc22c36f1ef7c3c735e0a2ffd31a5ebaa503b2'),
    'tiny_pos': (0.4, 'c48c74b9149a6a4fc9c6149240ca6c6955dc89cfe11883d6cb211ea0f149457e'),
    'tiny_neg': (-0.4, '3b2f35af1f43bc2a52f3d4ec96f11a218643941f6cd6ac6993768a107d8e3b0e'),
    'np_buy': (np.float64(7.6), 'c8a5cbdbfd0f559dcb678b38ec57dbe91f011108b6168dfd47fc188130735ed9'),
}


class TestCombinedBad:
    """融資與外資淨額同時非有限／pd.NA：不崩、兩格皆灰、無融資／外資警示句。"""

    @pytest.mark.parametrize('bad', [pd.NA, -math.inf, math.inf, math.nan])
    def test_both_bad(self, bad, monkeypatch):
        out = _wr(monkeypatch, net=bad, margin=bad)
        j = _joined(out)
        assert _val('未取得 (N/A)') in _card(out, '融資餘額') and _val('未知') in _card(out, '外資方向')
        assert '⬜ 融資餘額</div>' in j and '⬜ 外資方向</div>' in j
        assert '融資 ' not in j and '外資賣超' not in j


class TestForeignNetFiniteUnchanged:
    @pytest.mark.parametrize('case', sorted(_F_BASE))
    def test_golden(self, case, monkeypatch):
        net, gold = _F_BASE[case]
        assert _digest(_wr(monkeypatch, net=net)) == gold

    def test_text(self, monkeypatch):
        assert _val('買超 25億') in _card(_wr(monkeypatch, net=25.4), '外資方向')
        j = _joined(_wr(monkeypatch, net=-30.0))
        assert _val('賣超 30億') in j and '外資賣超 30.0億' in j
