"""批 Z31 —— 客戶 2026-10-10 核准 Q-z9／Q-z10／Q-z11（皆選 A；基底 origin/main `64158a76`，含批 Z30 #818）。

- Q-z9（Z30-n1，L1 `leading_indicators.render_leading_table`）：「成交量」欄文字型缺值「None」「<NA>」「NaT」
  （含前後空白；物件 pd.NaT 的 str 亦為「NaT」）修前原樣照印 ⇒ 改走本欄既有缺值「-」。
  「nan」「NaN」「NAN」等可被 `float()` 解析者，批 Z30 起已走非有限 ⇒「-」（本檔一併釘住）。
  ⛔ 不是「轉不了數字就一律 -」：其餘非數字字串（如「3,000.0億」「abc」）照舊原樣輸出。
- Q-z10（Z30-n2／Z21-n2，L5 `section_chips.py`「🔍 資料來源診斷」→「最新一筆原始值」）：±inf 修前印
  「外資大小=+inf」「選PCR=+inf」⇒ 比照 NaN 既有處理不列；非數值字串（如「abc」）照舊走 except 原樣印出。
- Q-z11（Z9-n7，同檔「🎯 {日期} 籌碼綜合判斷」卡）：5 項（外資期貨／PCR／外選／前五大／韭菜指數）個別缺
  （None／NaN／pd.NA／±inf）⇒ 訊號列加同頁既有格式「📌 ○○ 未取得」、不計分；5 項全缺 ⇒ 總結論改同頁既有
  「⬜ 無法判定」（同頁 v4 卡既有灰 `TRAFFIC_NEUTRAL`）、不給任何操作建議；至少一項有效 ⇒ 計分、門檻、
  判斷分支與輸出字句全部不變（score 0 仍「⚪ 多空分歧」）。前五大介於 [-10000, 0] 為「有值但中性」，不是缺值。

golden：修前輸出於基底 `64158a76` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
本檔所有斷言皆為實跑行為斷言；`Z31_CHIPS_REVERT_PAIRS` 為字面錨點（正式碼一改即失敗）。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import math
import re

import numpy as np
import pandas as pd
import pytest

import src.ui.tabs.macro.section_chips as SC
from shared.colors import TRAFFIC_NEUTRAL
from src.data.macro.leading_indicators import render_leading_table
from tests.test_batch_z30 import (
    _DAY, _VOL_DASH, _chips, _chips_mod, _digest, _li, _raw_line, _strip, _vol_df,
)

_INFNAN = re.compile(r'(?<![A-Za-z])(inf|nan|infinity)(?![A-Za-z])', re.I)


def _h(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# 1. Q-z9：先行指標表「成交量」欄文字型缺值 ⇒ 「-」
# ══════════════════════════════════════════════════════════════════════════
_TXT_MISSING = [
    pytest.param('None', id='str-None'),
    pytest.param('<NA>', id='str-NA'),
    pytest.param('NaT', id='str-NaT'),
    pytest.param(' None ', id='str-None-spaced'),
    pytest.param('NaT ', id='str-NaT-spaced'),
    pytest.param(pd.NaT, id='pd-NaT'),
    pytest.param(np.datetime64('NaT', 'D'), id='np-NaT'),
]
_ALREADY_DASH = [   # 批 Z30 起已走非有限（`float()` 解析得了）——本批不動，一併釘住
    pytest.param('nan', id='str-nan'),
    pytest.param('NaN', id='str-NaN'),
    pytest.param('NAN', id='str-NAN'),
    pytest.param('nan億', id='str-nan-yi'),
    pytest.param(math.nan, id='float-nan'),
    pytest.param(math.inf, id='float-pinf'),
    pytest.param(-math.inf, id='float-ninf'),
    pytest.param(None, id='None'),
    pytest.param(pd.NA, id='pd-NA'),
]


class TestQz9VolumeTextMissing:
    @pytest.mark.parametrize('vol', _TXT_MISSING + _ALREADY_DASH)
    def test_dash(self, vol):
        html = render_leading_table(_vol_df('3000.0億', vol))
        assert _VOL_DASH in html.split('<tr>')[-1]
        assert 'None' not in html and '<NA>' not in html and 'NaT' not in html
        assert not _INFNAN.search(_strip(html)), _strip(html)

    @pytest.mark.parametrize('vol', _TXT_MISSING + _ALREADY_DASH)
    def test_same_as_l1_missing(self, vol):
        """與 L1 自己寫入的缺值「-」逐字相同（本欄既有缺值顯示）。"""
        assert render_leading_table(_vol_df('3000.0億', vol)) == render_leading_table(_vol_df('3000.0億', '-'))

    #: 修前基底 `64158a76` 實跑：該格照印原樣（「None」「<NA>」「NaT」）的整張表 sha256。
    _PRE = {
        'None': ('None', '9c8731757ed115f21de1da9d169790e2192a9a505983107b1e9a90cd8d2a8ebb'),
        '<NA>': ('<NA>', '0404f1f60a91fed570a5d8c1533851d002d084c551416abf1e2e092b58fb513a'),
        'NaT': ('NaT', '1cab17bdee4941071759aff2a56c8548080052c409698afbf9a43e9e2d6eb2dd'),
        'pd.NaT': (pd.NaT, '1cab17bdee4941071759aff2a56c8548080052c409698afbf9a43e9e2d6eb2dd'),
    }

    @pytest.mark.parametrize('case', sorted(_PRE))
    def test_only_that_cell_changed(self, case):
        """把「-」換回原樣字串後，整張表等於修前基底實跑（只差這一格）。"""
        vol, gold = self._PRE[case]
        html = render_leading_table(_vol_df('3000.0億', vol))
        head, sep, tail = html.rpartition(_VOL_DASH)
        assert sep
        assert _h(head + f'<td><span style="color:#9CDCFE;">{vol}</span></td>' + tail) == gold
        assert _h(html) != gold


#: 修前基底 `64158a76` 實跑：正常數字／非數字字串原樣輸出的整張表 sha256。
_VOL_KEEP_BASE = {
    'yi': (('1,234.5億', '3,000.0億', '123.4億', '3000.0億'), '6a75aeab0f7a14a969854deb4a43a6c46f03a9466dae34ff127aefe11621ef24'),
    'misc': (('abc', 'none', 'N/A', '-', '0.0億'), 'f2f0742a80f3dd3b7d411763f7e1f63b72dcaff3deb0ac19e95fa2894a4e277e'),
}


class TestQz9KeepUnchanged:
    @pytest.mark.parametrize('case', sorted(_VOL_KEEP_BASE))
    def test_golden(self, case):
        vols, gold = _VOL_KEEP_BASE[case]
        assert _h(render_leading_table(_vol_df(*vols))) == gold

    @pytest.mark.parametrize('vol', ['1,234.5億', '3,000.0億', '123.4億', 'abc'])
    def test_text(self, vol):
        assert f'<td><span style="color:#9CDCFE;">{vol}</span></td>' in render_leading_table(_vol_df(vol))


# ══════════════════════════════════════════════════════════════════════════
# 2. Q-z10：「最新一筆原始值」±inf 不列（比照 NaN）
# ══════════════════════════════════════════════════════════════════════════
def _raw(mp, **last):
    li = _li(_DAY, dict(_DAY, **last))
    obj = [c for c, v in last.items() if not isinstance(v, float)]
    if obj:
        li = li.astype({c: object for c in obj})
    return _raw_line(_chips(li, mp))


#: _DAY 末列（全有限）的「最新一筆原始值」（基底 `64158a76` 實跑逐字）
_RAW_DAY = ('外資大小=-40,000 | 前五大留倉=-12,000 | 前十大留倉=-15,000 | 選PCR=+70 | 外(選)=-5,000 | '
            '韭菜指數=+40 | 外資=+80 | 投信=+10 | 自營=-3')


class TestQz10RawInf:
    @pytest.mark.parametrize('col', ['外資大小', '選PCR'])
    @pytest.mark.parametrize('bad', [math.inf, -math.inf, math.nan], ids=['pinf', 'ninf', 'nan'])
    def test_not_listed(self, col, bad, monkeypatch):
        line = _raw(monkeypatch, **{col: bad})
        assert f'{col}=' not in line
        assert not _INFNAN.search(line), line
        # 其餘 8 項照舊
        assert line == ' | '.join(p for p in _RAW_DAY.split(' | ') if not p.startswith(f'{col}='))

    def test_z21_n2_pcr_pinf(self, monkeypatch):
        """Z21-n2：同區修前印「選PCR=+inf」—— 本批後不再出現。"""
        line = _raw(monkeypatch, 選PCR=math.inf)
        assert '選PCR=+inf' not in line and 'inf' not in line

    def test_all_inf_empty(self, monkeypatch):
        cols = ['外資大小', '前五大留倉', '前十大留倉', '選PCR', '外(選)', '韭菜指數', '外資', '投信', '自營']
        assert _raw(monkeypatch, **{c: (math.inf if i % 2 else -math.inf) for i, c in enumerate(cols)}) == ''

    def test_finite_unchanged(self, monkeypatch):
        assert _raw(monkeypatch) == _RAW_DAY

    def test_abc_printed_as_is(self, monkeypatch):
        """非數值字串照舊走 except 原樣印出（regression）。"""
        line = _raw(monkeypatch, 選PCR='abc')
        assert '選PCR=abc' in line

    @pytest.mark.parametrize('val, txt', [(np.float64(np.inf), None), (np.float32(-np.inf), None),
                                          ('inf', None), (True, '選PCR=+1')])
    def test_other_types(self, val, txt, monkeypatch):
        line = _raw(monkeypatch, 選PCR=val)
        if txt is None:
            assert '選PCR=' not in line and not _INFNAN.search(line)
        else:
            assert txt in line


# ══════════════════════════════════════════════════════════════════════════
# 3. Q-z11：「🎯 籌碼綜合判斷」卡缺值揭露
# ══════════════════════════════════════════════════════════════════════════
_COLS = {'fnet': '外資大小', 'pcr': '選PCR', 'opt': '外(選)', 'top5': '前五大留倉', 'leek': '韭菜指數'}
_LABEL = {'fnet': '外資期貨', 'pcr': 'PCR', 'opt': '外選', 'top5': '前五大', 'leek': '韭菜指數'}
_ADVICE = ('建議大幅降倉，等待空單回補訊號', '籌碼不穩，建議觀望為主', '訊號分歧，小倉觀察，詳見策略手冊',
           '籌碼偏健康，可正常持倉', '聰明錢明顯佈多，積極持倉')
_SIGS_RE = re.compile(r'<div style="font-size:12px;color:#484f58;">(.*?)</div>')


def _li_last(**vals):
    """前一日 = _DAY（全有值），今日 = _DAY 覆寫 vals（key 為 fnet/pcr/opt/top5/leek）。"""
    last = dict(_DAY)
    for k, v in vals.items():
        last[_COLS[k]] = v
    li = _li(_DAY, last)
    return li.astype({_COLS[k]: object for k in vals})


def _card_of(out) -> str:
    cards = [t for _k, t in out if ' 籌碼綜合判斷</div>' in t]
    assert len(cards) == 1
    return cards[0]


def _card(mp, **vals) -> str:
    return _card_of(_chips(_li_last(**vals), mp))


def _sigs(card) -> list[str]:
    m = _SIGS_RE.search(card)
    assert m
    return m.group(1).split(' ； ') if m.group(1) else []


def _missing_tag(k) -> str:
    return f'📌 {_LABEL[k]} 未取得'


# ── 還原體：本批 section_chips 改動逐字換回基底 `64158a76` 寫法 ──
#: (修後逐字, 修前逐字)。⚠️ 正式碼字面一改，這裡會因找不到替換點而失敗 —— 那是字面錨點。
#: 📌 批 Z35（Q-z17，客戶 2026-10-10 核准 A，有意識的變更，⛔ 不是漏改）：本批「5 項全缺」條件改為「有效項數 < 2」。
#:   該行正是下方 Q-z11 錨點的一部分 ⇒ 先把批 Z35 那幾行換回批 Z31 寫法（恰一處），再接本批還原；
#:   還原體仍逐字等於基底 `64158a76`（下游 z28／z30 串接本常數者不必改）。批 Z35 自己的還原也取用本對（單一來源）。
Z35_QZ17_CHIPS_PAIR = (
    "        # 批 Z35（Q-z17，客戶 2026-10-10 核准 A）：條件由「5 項全缺」放寬為「有效（非 None）項數 < 2」——\n"
    "        #   只剩 1 項有效（含落在中性、不出訊號者，如前五大介於 [-10000,0]、PCR=110）同樣「⬜ 無法判定」、\n"
    "        #   不給操作建議；≥ 2 項有效 ⇒ 既有計分／門檻／結論逐字不變；「📌 ○○ 未取得」標記照舊。\n"
    "        if sum(_x is not None for _x in (_fnet, _pcr, _opt, _top5, _leek)) < 2:\n",
    "        if _fnet is None and _pcr is None and _opt is None and _top5 is None and _leek is None:\n")
Z31_QZ11_REVERT_PAIRS = (Z35_QZ17_CHIPS_PAIR,) + tuple(
    (f"        else:\n            _sigs.append('{_missing_tag(k)}')\n", '') for k in _COLS
) + (
    ("        # 批 Z31（Q-z11，客戶 2026-10-10 核准）：5 項全缺（皆 None）⇒ 同頁既有「⬜ 無法判定」＋同頁 v4 卡既有灰\n"
     "        #   `TRAFFIC_NEUTRAL`，不給任何操作建議（`_va` 空 ⇒ 下方建議列整個不輸出）；至少一項有效 ⇒ 下列分支逐字不變。\n"
     "        if _fnet is None and _pcr is None and _opt is None and _top5 is None and _leek is None:\n"
     "            _vd='⬜ 無法判定'\n"
     "            _vc=TRAFFIC_NEUTRAL\n"
     "            _va=''\n"
     "        elif _score <= -3:\n",
     "        if   _score <= -3:\n"),
    ("            + (f'<div style=\"font-size:13px;color:#c9d1d9;margin:6px 0 10px 0;\">{_va}</div>' if _va else '')\n"
     "            + f'<div style=\"font-size:12px;color:#484f58;\">{\" ； \".join(_sigs)}</div>'\n",
     "            f'<div style=\"font-size:13px;color:#c9d1d9;margin:6px 0 10px 0;\">{_va}</div>'\n"
     "            f'<div style=\"font-size:12px;color:#484f58;\">{\" ； \".join(_sigs)}</div>'\n"),
)


@functools.lru_cache(maxsize=None)
def _variant_with(pairs):
    src = open(SC.__file__, encoding='utf-8').read()
    for new, old in pairs:
        assert src.count(new) == 1, f'替換點不唯一或已不存在：{new!r}'
        src = src.replace(new, old)
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader('_z31_pre_chips', loader=None))
    m.__file__ = SC.__file__
    exec(compile(src, SC.__file__, 'exec'), m.__dict__)
    return m


#: Q-z10「最新一筆原始值」±inf 不列 —— (修後逐字, 修前逐字)
Z31_QZ10_REVERT_PAIRS = (
    ("                            # 批 Z31（Q-z10／Z30-n2／Z21-n2）：±inf 比照 NaN 不列（修前印「選PCR=+inf」）；\n"
     "                            #   條件放在 try 內，非數值字串（如「abc」）仍走 except 原樣印出。\n"
     "                            if not _pd_raw.isna(_v) and math.isfinite(float(_v)):  # [BUG FIX] 過濾 NaN 避免 format 崩潰\n",
     "                            if not _pd_raw.isna(_v):  # [BUG FIX] 過濾 NaN 避免 format 崩潰\n"),
)
#: 本批 section_chips 全部改動（供既有「還原為某基底」的還原體串接，比照批 Z30 對 z28 的作法）
Z31_CHIPS_REVERT_PAIRS = Z31_QZ10_REVERT_PAIRS + Z31_QZ11_REVERT_PAIRS


def pre_qz11_chips_module():
    return _variant_with(Z31_QZ11_REVERT_PAIRS)


def pre_qz17_chips_module():
    """現行 section_chips 只把批 Z35（Q-z17：有效項 < 2 ⇒ 無法判定）換回批 Z31 寫法（「5 項全缺」）。"""
    return _variant_with((Z35_QZ17_CHIPS_PAIR,))


def pre_z31_chips_module():
    """現行 section_chips 只把本批（Q-z10＋Q-z11）換回基底 `64158a76` 寫法。"""
    return _variant_with(Z31_CHIPS_REVERT_PAIRS)


_CARD_KEY = ' 籌碼綜合判斷</div>'
_MISSING_SIG = re.compile(r'^📌 (外資期貨|PCR|外選|前五大|韭菜指數) 未取得$')


def undo_qz11_card(out):
    """把 `out` 中「🎯 籌碼綜合判斷」卡的本批（Q-z11）改動逐字換回修前樣子（其餘段原封不動）：
    訊號列移除「📌 ○○ 未取得」；5 項全缺的「⬜ 無法判定」（灰、無建議列）換回修前「⚪ 多空分歧」（黃＋既有建議句）。
    供修前寫死的 §三 整段 golden 保留原 digest；本函式的正確性由 `TestUndoHelperIsExact` 以還原體實跑自證。"""
    from shared.colors import TRAFFIC_YELLOW
    res = []
    for k, t in out:
        if _CARD_KEY in t:
            m = _SIGS_RE.search(t)
            assert m, t
            kept = [s for s in (m.group(1).split(' ； ') if m.group(1) else []) if not _MISSING_SIG.match(s)]
            t = t[:m.start(1)] + ' ； '.join(kept) + t[m.end(1):]
            undecided = f'<div style="font-size:24px;font-weight:900;color:{TRAFFIC_NEUTRAL};">⬜ 無法判定</div>'
            if undecided in t:
                t = (t.replace(f'border:2px solid {TRAFFIC_NEUTRAL}44;', f'border:2px solid {TRAFFIC_YELLOW}44;', 1)
                      .replace(undecided,
                               f'<div style="font-size:24px;font-weight:900;color:{TRAFFIC_YELLOW};">⚪ 多空分歧</div>'
                               '<div style="font-size:13px;color:#c9d1d9;margin:6px 0 10px 0;">'
                               '訊號分歧，小倉觀察，詳見策略手冊</div>', 1))
        res.append((k, t))
    return res


#: 修前基底 `64158a76` 同一支 `_chips` 實跑：今日 5 項全部有效時整段 §三 的 sha256（必須逐字不變）。
_ALL_PRESENT_BASE = {
    'day(-5)': ({}, '3d5c11c18c5b609df3c4331f56d539a7ae061b0cd73c1b8153c0f564ddf490f1'),
    'bull(+5)': (dict(fnet=5000.0, pcr=140.0, opt=20000.0, top5=3000.0, leek=-10.0), '8a37e5a4992ae8626fd68061c95767e8c141c6a9d7f5b9c3b52fb281b5784fda'),
    'zero(0)': (dict(fnet=-1000.0, pcr=140.0, opt=0.0, top5=-5000.0, leek=5.0), '7d09d752697d491f5a6ae804ccb521d6b7568fb3eaa75dfbe90b63c9b4ffc552'),
    'mild(-1)': (dict(fnet=-20000.0, pcr=110.0, opt=0.0, top5=0.0, leek=0.0), 'bad0a621d44eb7d7eec694bb44afe309ba9666efc9e287881f6aeb4f012c4ef5'),
    'plus2(+2)': (dict(fnet=100.0, pcr=150.0, opt=10000.0, top5=-10000.0, leek=10.0), '5149bb93209e0f7e8fa9d02469005aedefaf0bd25997b4a57e26d29c36445501'),
    'edge(-3)': (dict(fnet=-30000.0, pcr=100.0, opt=-10001.0, top5=-10001.0, leek=10.1), '4533b21a8452e83b524b1c021e0dd539cbb4aa86cd469c5f8826650fd8b9287f'),
}

_BAD = [pytest.param(None, id='None'), pytest.param(math.nan, id='nan'), pytest.param(pd.NA, id='pdNA'),
        pytest.param(math.inf, id='pinf'), pytest.param(-math.inf, id='ninf')]


class TestQz11AllPresentUnchanged:
    @pytest.mark.parametrize('case', sorted(_ALL_PRESENT_BASE))
    def test_golden(self, case, monkeypatch):
        vals, gold = _ALL_PRESENT_BASE[case]
        assert _digest(_chips(_li_last(**{k: float(v) for k, v in vals.items()}), monkeypatch)) == gold

    @pytest.mark.parametrize('case', sorted(_ALL_PRESENT_BASE))
    def test_no_missing_tag(self, case, monkeypatch):
        vals, _ = _ALL_PRESENT_BASE[case]
        card = _card(monkeypatch, **vals)
        assert '未取得' not in card and '⬜ 無法判定' not in card


class TestQz11SomeMissing:
    @pytest.mark.parametrize('bad', _BAD)
    @pytest.mark.parametrize('k', sorted(_COLS))
    def test_single_missing_tag(self, k, bad, monkeypatch):
        """(a)(f) 單項缺（各種缺法）⇒ 該項「📌 ○○ 未取得」；其餘訊號、計分、結論、建議與修前同一份輸入逐字相同。"""
        card = _card(monkeypatch, **{k: bad})
        assert _missing_tag(k) in _sigs(card)
        assert sum('未取得' in s for s in _sigs(card)) == 1
        assert not _INFNAN.search(_strip(card)) and 'None' not in card and '<NA>' not in card
        monkeypatch.undo()
        pre = _card_of(_chips_mod(_li_last(**{k: bad}), monkeypatch, pre_qz11_chips_module()))
        assert _SIGS_RE.sub('', card) == _SIGS_RE.sub('', pre)
        assert [s for s in _sigs(card) if not s.startswith('📌 ')] == _sigs(pre)

    def test_only_fnet_missing_text(self, monkeypatch):
        """(a) 只缺外資期貨：_DAY 其餘 4 項 ⇒ -3 ⇒ 🚨 強烈偏空；訊號列外資期貨位置改「📌 外資期貨 未取得」。"""
        card = _card(monkeypatch, fnet=math.nan)
        assert _sigs(card) == ['📌 外資期貨 未取得', '🔴 PCR=70（<100偏空）', '⚪ 外選 -5,000千元（中性）',
                               '🔴 前五大淨空 -12,000口（警戒）', '🔴 韭菜指數40.0%（散戶過熱）']
        assert '🚨 強烈偏空' in card and _ADVICE[0] in card

    def test_multi_missing(self, monkeypatch):
        """(b) 缺外資期貨＋PCR＋韭菜指數：只剩外選中性＋前五大 -1 ⇒ 🔴 偏空。"""
        card = _card(monkeypatch, fnet=None, pcr=math.inf, leek=pd.NA)
        assert _sigs(card) == ['📌 外資期貨 未取得', '📌 PCR 未取得', '⚪ 外選 -5,000千元（中性）',
                               '🔴 前五大淨空 -12,000口（警戒）', '📌 韭菜指數 未取得']
        assert '🔴 偏空' in card and _ADVICE[1] in card and '⬜ 無法判定' not in card

    def test_one_present_score_zero_divergent(self, monkeypatch):
        """(e) 只有 PCR=110 有值（不計分）⇒ score 0 ⇒ 仍「⚪ 多空分歧」與既有建議句。

        📌 批 Z35（Q-z17，客戶 2026-10-10 核准 A，有意識的變更，⛔ 不是漏改）：有效項 < 2 起改「⬜ 無法判定」
        （現行行為由 test_batch_z35 斷言）。本測試守的是批 Z31 當時的規則 ⇒ 改對只把批 Z35 換回的還原體實跑，斷言不改。"""
        card = _card_of(_chips_mod(_li_last(fnet=None, opt=None, top5=None, leek=None, pcr=110.0), monkeypatch,
                                   pre_qz17_chips_module()))
        assert '⚪ 多空分歧' in card and _ADVICE[2] in card and '⬜ 無法判定' not in card
        assert _sigs(card) == ['📌 外資期貨 未取得', '🔵 PCR=110（偏多）', '📌 外選 未取得',
                               '📌 前五大 未取得', '📌 韭菜指數 未取得']

    @pytest.mark.parametrize('top5', [-10000.0, -5000.0, 0.0])
    def test_top5_neutral_is_not_missing(self, top5, monkeypatch):
        """前五大介於 [-10000, 0]：有值但中性（本來就不加訊號）≠ 缺值 ⇒ 不出「📌 前五大 未取得」；
        其餘 4 項缺 ⇒ score 0 ⇒ 「⚪ 多空分歧」（不是「⬜ 無法判定」）。

        📌 批 Z35（Q-z17，客戶 2026-10-10 核准 A，有意識的變更，⛔ 不是漏改）：只剩 1 項有效起改「⬜ 無法判定」
        （現行行為由 test_batch_z35 斷言；「前五大中性仍算有效一項、不出未取得」兩批一致）。
        本測試守的是批 Z31 當時的規則 ⇒ 改對只把批 Z35 換回的還原體實跑，斷言不改。"""
        card = _card_of(_chips_mod(_li_last(fnet=None, pcr=None, opt=None, leek=None, top5=top5), monkeypatch,
                                   pre_qz17_chips_module()))
        assert '📌 前五大 未取得' not in card and '前五大' not in card
        assert '⚪ 多空分歧' in card and '⬜ 無法判定' not in card
        assert _sigs(card) == ['📌 外資期貨 未取得', '📌 PCR 未取得', '📌 外選 未取得', '📌 韭菜指數 未取得']


class TestQz11AllMissing:
    @pytest.mark.parametrize('bad', _BAD)
    def test_cannot_judge(self, bad, monkeypatch):
        """(c)(f) 5 項全缺 ⇒「⬜ 無法判定」、灰、不給任何操作建議、不出「多空分歧」。"""
        card = _card(monkeypatch, **{k: bad for k in _COLS})
        assert '⬜ 無法判定' in card
        assert f'color:{TRAFFIC_NEUTRAL};">⬜ 無法判定</div>' in card
        assert f'border:2px solid {TRAFFIC_NEUTRAL}44;' in card
        for a in _ADVICE:
            assert a not in card
        assert '多空分歧' not in card and '建議' not in card
        assert 'margin:6px 0 10px 0' not in card            # 建議列整個不輸出（不留空白殘影）
        assert _sigs(card) == [_missing_tag(k) for k in ('fnet', 'pcr', 'opt', 'top5', 'leek')]
        assert not _INFNAN.search(_strip(card)) and 'None' not in card and '<NA>' not in card

    def test_mixed_bad_kinds(self, monkeypatch):
        card = _card(monkeypatch, fnet=None, pcr=math.nan, opt=pd.NA, top5=math.inf, leek=-math.inf)
        assert '⬜ 無法判定' in card and '多空分歧' not in card

    def test_pre_was_divergent(self, monkeypatch):
        """還原體（修前）：全缺 ⇒ score 0 ⇒「⚪ 多空分歧／訊號分歧，小倉觀察」—— 本批修掉的正是這個。"""
        card = _card_of(_chips_mod(_li_last(**{k: math.nan for k in _COLS}), monkeypatch,
                                   pre_qz11_chips_module()))
        assert '⚪ 多空分歧' in card and _ADVICE[2] in card

    def test_card_structure_kept(self, monkeypatch):
        """卡片外框／標題／結論／訊號列結構不變（只少了建議列）。"""
        card = _card(monkeypatch, **{k: None for k in _COLS})
        assert card.startswith('<div style="background:#0d1117;border:2px solid ')
        assert '<div style="font-size:11px;color:#8b949e;margin-bottom:4px;">🎯 10月2日 籌碼綜合判斷</div>' in card
        assert card.count('<div') == 4 and card.endswith('</div></div>')


class TestQz11YesterdayNotUsed:
    def test_today_fnet_nan_yesterday_value(self, monkeypatch):
        """昨日外資大小 -40,000、今日 NaN ⇒ 卡片走今日缺值「📌 外資期貨 未取得」，不讀昨日。"""
        card = _card(monkeypatch, fnet=math.nan)
        assert '📌 外資期貨 未取得' in card
        assert '期貨空單' not in card and '-40,000' not in card and '期貨淨' not in card

    def test_today_all_nan_yesterday_values(self, monkeypatch):
        card = _card(monkeypatch, **{k: math.nan for k in _COLS})
        assert '⬜ 無法判定' in card and '-40,000' not in card and 'PCR=70' not in card


# ══════════════════════════════════════════════════════════════════════════
# 4. 還原體／還原函式自證（供既有修前 golden 串接用）
# ══════════════════════════════════════════════════════════════════════════
_UNDO_CASES = {
    'all_present': lambda: _li_last(),
    'fnet_nan': lambda: _li_last(fnet=math.nan),
    'multi': lambda: _li_last(fnet=None, pcr=math.inf, leek=pd.NA),
    'all_nan': lambda: _li_last(**{k: math.nan for k in _COLS}),
    'all_none': lambda: _li_last(**{k: None for k in _COLS}),
    'only_fnet_pcr_cols': lambda: pd.DataFrame({'日期': ['a', 'b'], '外資大小': [-1000.0, -2000.0],
                                                 '選PCR': [100.0, 110.0]}),
    'only_fnet_col_nan': lambda: pd.DataFrame({'日期': ['a', 'b'], '外資大小': [-1000.0, math.nan]}),
}


class TestUndoHelperIsExact:
    @pytest.mark.parametrize('case', sorted(_UNDO_CASES))
    def test_undo_equals_pre_variant(self, case, monkeypatch):
        """`undo_qz11_card(現行輸出)` 逐字等於還原體（只把 Q-z11 換回修前）實跑；且除該卡外其餘段逐字相同。"""
        cur = _chips(_UNDO_CASES[case](), monkeypatch)
        monkeypatch.undo()
        pre = _chips_mod(_UNDO_CASES[case](), monkeypatch, pre_qz11_chips_module())
        assert undo_qz11_card(cur) == pre
        diff = [i for i, (a, b) in enumerate(zip(cur, pre)) if a != b]
        assert len(cur) == len(pre) and all(_CARD_KEY in cur[i][1] for i in diff)

    def test_pre_z31_raw_pinf(self, monkeypatch):
        """還原體（Q-z10＋Q-z11 換回）重現修前「選PCR=+inf」（Z21-n2）—— 本批修掉的正是這個。"""
        li = _li(_DAY, dict(_DAY, 選PCR=math.inf))
        assert '選PCR=+inf' in _raw_line(_chips_mod(li, monkeypatch, pre_z31_chips_module()))
