"""批 Z37 —— 客戶 2026-10-10 裁示 Q-z21＝A（基底 origin/main `3fed8dd6`）。

- Q-z21（Z36-n2，L1 `src/data/macro/leading_indicators.py::build_leading_fast` §4「三大法人現貨」）：
  FinMind `TaiwanStockTotalInstitutionalInvestors` 的 buy／sell 整欄缺（欄不存在）、整欄 None（object 型別）、
  或某列 None／空字串／不可解析時，修前 `float(r.get("buy", 0) or 0)` 把缺值當 0 ⇒ 外資／投信／自營被印成
  真實 0 或「只剩買或只剩賣」的假淨額（不可解析字串則整支函式拋 ValueError、§三 整張表不見）。
  修法：該列 buy 或 sell 不可解析 ⇒ 該列淨額為 NaN（＝既有「單一儲存格 null」路徑：pandas 數值欄的 null
  修前就是 NaN），自營兩子列（Dealer_self、Dealer_Hedging）任一為 NaN ⇒ 自營加總為 NaN（半套不當完整）。
  ⛔ 子列「整列不存在」照舊以有的列加總（repo 內無證據顯示 FinMind 每日必回兩列；同 repo 既有
  DL-f1-s43、批 Z36 BFI82U／FinMind 補救皆以「列不存在≠缺值」處理）—— 列為限制，不猜。
  ⛔ 外資大小（期貨 TX／MTX，批 Z25）、外資自營商歸類（Q-z22 另案）皆不動。
- 真實 0 ＝ 0；正負數值逐字同修前（golden）。

golden：修前輸出於基底 `3fed8dd6` 以本檔同一支 harness 實跑後寫死（⛔ 不由現行碼反推）。
突變：`Z37_REVERT_PAIRS` 為「修後逐字 → 修前逐字」（恰一處替換）；還原體逐字 ＝ 基底檔（sha256 自證），
      實跑重現修前行為（假 0／假淨額／拋例外）⇒ 對應斷言轉紅。
本檔所有斷言皆為實跑行為斷言，不讀原始碼字面（還原體 sha 自證除外）。
"""
from __future__ import annotations

import datetime as dt
import functools
import hashlib
import importlib.util
import itertools
import json
import math
import pathlib
import re
import sys

import pandas as pd
import pytest

import shared.cache_layer as CL
import src.data.macro.leading_indicators as LI
from src.data.macro.leading_indicators import render_leading_table

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_LI = 'src/data/macro/leading_indicators.py'

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 pair（修後逐字 → 修前逐字）
# ══════════════════════════════════════════════════════════════════════════
Z37_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _LI: (
        ('                # 批 Z37（Q-z21，客戶 2026-10-10 核准 A）：buy／sell 缺欄／None／不可解析 ⇒ 該列淨額為 NaN（不補 0、\n'
         '                #   不推假淨額）；自營兩子列任一 NaN ⇒ 加總為 NaN（半套不當完整）。子列整列不存在照舊（無可靠證據判定應存在）。\n'
         '                if pd.isna(pd.to_numeric(r.get("buy"), errors="coerce")) or pd.isna(pd.to_numeric(r.get("sell"), errors="coerce")):\n'
         '                    net = float("nan")\n'
         '                else:\n'
         '                    net = round((float(r.get("buy",  0) or 0) - float(r.get("sell", 0) or 0)) / 1e8, 1)\n',
         '                net = round((float(r.get("buy",  0) or 0) - float(r.get("sell", 0) or 0)) / 1e8, 1)\n'),
    ),
}
#: 基底 `3fed8dd6` 原始檔 sha256（`git show 3fed8dd6:<檔> | sha256sum` 實算）
Z37_BASE_SHA = {_LI: '1693dc611e8977e761858ee08ca31a0cd73594be8014acb0059d6ad99449fc7c'}


def z37_revert(rel: str, code: str) -> str:
    for new, old in Z37_REVERT_PAIRS[rel]:
        assert code.count(new) == 1, f'{rel} 替換點不唯一或已不存在：{new!r}'
        code = code.replace(new, old)
    return code


@functools.lru_cache(maxsize=None)
def z37_pre_module(rel: str = _LI):
    """現行檔只把本批改動換回基底 `3fed8dd6` 寫法（獨立模組物件，不影響本尊）。"""
    path = _ROOT / rel
    name = '_z37_pre_' + rel.replace('/', '_').removesuffix('.py')
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(z37_revert(rel, path.read_text(encoding='utf-8')), str(path), 'exec'), m.__dict__)
    return m


def test_reverted_source_equals_base_file():
    """還原體原始碼逐字 ＝ 基底 `3fed8dd6` 檔案 ⇒ 下方「修前」突變斷言跑的是真修前碼。"""
    code = z37_revert(_LI, (_ROOT / _LI).read_text(encoding='utf-8'))
    assert hashlib.sha256(code.encode('utf-8')).hexdigest() == Z37_BASE_SHA[_LI]


# ══════════════════════════════════════════════════════════════════════════
# 1. harness：FinMind 三大法人形狀 → build_leading_fast（其餘來源離線）
# ══════════════════════════════════════════════════════════════════════════
def _weekdays(n: int) -> list[dt.date]:
    out, d = [], dt.date.today()
    while len(out) < n:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return sorted(out)


_D = _weekdays(4)
_DK = [d.strftime('%Y%m%d') for d in _D]
_NAMES = ('Foreign_Investor', 'Investment_Trust', 'Dealer_self', 'Dealer_Hedging')
#: (buy, sell) 元；各日不同，含正負、四捨五入、買賣相等（淨 0）、真實 0
_BASE = [
    {'Foreign_Investor': (5_000_000_000, 7_000_000_000), 'Investment_Trust': (3_000_000_000, 2_000_000_000),
     'Dealer_self': (2_000_000_000, 1_000_000_000), 'Dealer_Hedging': (1_000_000_000, 1_500_000_000)},
    {'Foreign_Investor': (12_345_678_901, 2_000_000_000), 'Investment_Trust': (400_000_000, 1_234_567_890),
     'Dealer_self': (300_000_000, 999_999_999), 'Dealer_Hedging': (2_222_222_222, 111_111_111)},
    {'Foreign_Investor': (8_000_000_000, 8_000_000_000), 'Investment_Trust': (0, 0),
     'Dealer_self': (0, 0), 'Dealer_Hedging': (0, 0)},
    {'Foreign_Investor': (9_876_543_210, 19_876_543_210), 'Investment_Trust': (5_555_555_555, 555_555_555),
     'Dealer_self': (1_000_000_000, 3_000_000_000), 'Dealer_Hedging': (4_000_000_000, 1_000_000_000)},
]


def _recs(base=_BASE):
    out = []
    for d, day in zip(_D, base):
        for nm in _NAMES:
            if nm in day:
                b, s = day[nm]
                out.append({'date': d.isoformat(), 'stock_id': '', 'name': nm, 'buy': b, 'sell': s})
        out.append({'date': d.isoformat(), 'stock_id': '', 'name': 'total', 'buy': 1, 'sell': 2})
    return out


def _set_last(recs, nm, **kv):
    hit = [r for r in recs if r['date'] == _D[-1].isoformat() and r['name'] == nm]
    assert len(hit) == 1
    hit[0].update(kv)
    return recs


def _drop_last(recs, nm):
    return [r for r in recs if not (r['date'] == _D[-1].isoformat() and r['name'] == nm)]


def _obj(recs):
    return pd.DataFrame(recs, dtype=object)


CASES = {
    # ── 不受影響（修前修後逐字相同）──
    'normal': lambda: pd.DataFrame(_recs()),
    'normal_object': lambda: _obj(_recs()),
    'real_zero_last': lambda: pd.DataFrame(_recs([*_BASE[:-1], {nm: (0, 0) for nm in _NAMES}])),
    'single_nan_foreign': lambda: pd.DataFrame(_set_last(_recs(), 'Foreign_Investor', buy=None)),
    'single_nan_trust': lambda: pd.DataFrame(_set_last(_recs(), 'Investment_Trust', sell=None)),
    'single_nan_hedge_sell': lambda: pd.DataFrame(_set_last(_recs(), 'Dealer_Hedging', sell=None)),
    'buy_sell_all_nan': lambda: pd.DataFrame([dict(r, buy=math.nan, sell=math.nan) for r in _recs()]),
    'self_row_absent': lambda: pd.DataFrame(_drop_last(_recs(), 'Dealer_self')),
    'hedge_row_absent': lambda: pd.DataFrame(_drop_last(_recs(), 'Dealer_Hedging')),
    'dealer_rows_absent': lambda: pd.DataFrame(_drop_last(_drop_last(_recs(), 'Dealer_self'), 'Dealer_Hedging')),
    # ── 本批修正對象 ──
    'no_buy_col': lambda: pd.DataFrame(_recs()).drop(columns=['buy']),
    'no_sell_col': lambda: pd.DataFrame(_recs()).drop(columns=['sell']),
    'no_buy_sell_cols': lambda: pd.DataFrame(_recs()).drop(columns=['buy', 'sell']),
    'buy_all_none_obj': lambda: _obj([dict(r, buy=None) for r in _recs()]),
    'sell_all_none_obj': lambda: _obj([dict(r, sell=None) for r in _recs()]),
    'buy_sell_all_none_obj': lambda: _obj([dict(r, buy=None, sell=None) for r in _recs()]),
    'foreign_none_obj': lambda: _obj(_set_last(_recs(), 'Foreign_Investor', buy=None, sell=None)),
    'trust_none_obj': lambda: _obj(_set_last(_recs(), 'Investment_Trust', buy=None, sell=None)),
    'trust_sell_none_obj': lambda: _obj(_set_last(_recs(), 'Investment_Trust', sell=None)),
    'dealer_both_none_obj': lambda: _obj(_set_last(_set_last(_recs(), 'Dealer_self', buy=None, sell=None),
                                                   'Dealer_Hedging', buy=None, sell=None)),
    'hedge_sell_none_obj': lambda: _obj(_set_last(_recs(), 'Dealer_Hedging', sell=None)),
    'self_buy_none_obj': lambda: _obj(_set_last(_recs(), 'Dealer_self', buy=None)),
    'self_buy_unparsable': lambda: _obj(_set_last(_recs(), 'Dealer_self', buy='n/a')),
    'hedge_sell_blank': lambda: _obj(_set_last(_recs(), 'Dealer_Hedging', sell='')),
}

_tok = itertools.count()
_OFFLINE = ('finmind_get', '_twse_margin_day', 'twse_volume', 'twse_volume_daily', '_bps', 'taifex_post')


def _patch(mp, df_inst, tmp_path, mod=LI):
    def _fake(ds, did, s, e, tok=''):
        if ds == 'TaiwanStockTotalInstitutionalInvestors':
            return df_inst.copy()
        return pd.DataFrame()

    def _no_taifex():
        raise RuntimeError('offline')
    fakes = {'finmind_get': _fake, '_twse_margin_day': lambda d: {}, 'twse_volume': lambda m: {},
             'twse_volume_daily': lambda d: None, '_bps': _no_taifex, 'taifex_post': lambda *a, **k: ''}
    for m in {LI, mod}:
        for k in _OFFLINE:
            mp.setattr(m, k, fakes[k])
    mp.setattr(LI.time, 'sleep', lambda s: None)
    mp.setattr(CL, '_PKL_DIR', str(tmp_path))


def _fast(mp, tmp_path, case, mod=LI):
    _patch(mp, CASES[case](), tmp_path, mod)
    df = mod.build_leading_fast(days=7, token=f'z37-{next(_tok)}')
    df['fetched_at'] = '2026-10-10T00:00:00+00:00'          # 時間戳固定（golden／比對用）
    return df


def _norm(v):
    if v is None:
        return None
    v = float(v)
    return 'nan' if math.isnan(v) else v


def _spot(df):
    """[(外資, 投信, 自營) for 各日]；None／'nan'／float。"""
    return [tuple(_norm(df.loc[df['_date'] == k, c].iloc[0]) for c in ('外資', '投信', '自營')) for k in _DK]


def _outcome(mp, tmp_path, case, mod=LI):
    try:
        df = _fast(mp, tmp_path, case, mod)
    except Exception as e:  # noqa: BLE001 —— 修前不可解析字串會拋，照實記錄
        return ('raise', type(e).__name__), None
    return ('ok', _spot(df)), hashlib.sha256(render_leading_table(df).encode('utf-8')).hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# 2. 修前 golden（基底 `3fed8dd6` 以本 harness 實跑寫死）
# ══════════════════════════════════════════════════════════════════════════
_N = 'nan'
_G_NORMAL = [(-20.0, 10.0, 5.0), (103.5, -8.3, 14.1), (0.0, 0.0, 0.0), (-100.0, 50.0, 10.0)]


def _last(t):
    return [*_G_NORMAL[:-1], t]


PRE_GOLDEN = {
    'normal': (('ok', _G_NORMAL), 'cccde1c4d8b3d1e8a80cfaab21997315dfdbbc57b182586c2d5eec92776d8935'),
    'normal_object': (('ok', _G_NORMAL), 'cccde1c4d8b3d1e8a80cfaab21997315dfdbbc57b182586c2d5eec92776d8935'),
    'real_zero_last': (('ok', _last((0.0, 0.0, 0.0))),
                       '7ca9afbf57708c2967e33ff2caefd7c24a0326d268ab9081efd775f3299764f6'),
    'single_nan_foreign': (('ok', _last((_N, 50.0, 10.0))),
                           '081b2dd4195d84a3674fabd12a2a9f939d1e96579a3f821de244fee66705d57a'),
    'single_nan_trust': (('ok', _last((-100.0, _N, 10.0))),
                         '841abdb4316a5f979c75b8825942e0851b713f5a8c054c6dc4aa62b64f24df04'),
    'single_nan_hedge_sell': (('ok', _last((-100.0, 50.0, _N))),
                              '3ed3848cb0a0de69849870a2c236442ff5554925ced290bed32b9ba5e48d36c5'),
    'buy_sell_all_nan': (('ok', [(_N, _N, _N)] * 4),
                         'a802dd3d3bc9f34c91c2a18b1964299b40a141bda33aa40353b75ea3c819d4ec'),
    'self_row_absent': (('ok', _last((-100.0, 50.0, 30.0))),
                        'cba1b1f1a1556fbbf70f6095509ece9748a4def3564f3eb633139df1b5c842b0'),
    'hedge_row_absent': (('ok', _last((-100.0, 50.0, -20.0))),
                         '204b0f525d1ffad942e88ef0d767296b97135aa4d809ef8f61a3be77e5e74f87'),
    'dealer_rows_absent': (('ok', _last((-100.0, 50.0, _N))),
                           '3ed3848cb0a0de69849870a2c236442ff5554925ced290bed32b9ba5e48d36c5'),
    # 以下為修前錯誤行為（突變時重現）：假 0／只剩買或只剩賣的假淨額／拋例外
    'no_buy_col': (('ok', [(-70.0, -20.0, -25.0), (-20.0, -12.3, -11.1), (-80.0, 0.0, 0.0), (-198.8, -5.6, -40.0)]),
                   '5cc98739a41842f029d34263614398768d354428918715364836a862aa1a446c'),
    'no_sell_col': (('ok', [(50.0, 30.0, 30.0), (123.5, 4.0, 25.2), (80.0, 0.0, 0.0), (98.8, 55.6, 50.0)]),
                    '7d822041ec2608f416cae97c02c1d33def00f5da024ca094c12ff803009b597f'),
    'no_buy_sell_cols': (('ok', [(0.0, 0.0, 0.0)] * 4),
                         'a0454553f81c4bd1470a5f40b7a4bd862b573ff1cf14bcdb78c4a5198e0c6989'),
    'buy_all_none_obj': (('ok', [(-70.0, -20.0, -25.0), (-20.0, -12.3, -11.1), (-80.0, 0.0, 0.0),
                                 (-198.8, -5.6, -40.0)]),
                         '5cc98739a41842f029d34263614398768d354428918715364836a862aa1a446c'),
    'sell_all_none_obj': (('ok', [(50.0, 30.0, 30.0), (123.5, 4.0, 25.2), (80.0, 0.0, 0.0), (98.8, 55.6, 50.0)]),
                          '7d822041ec2608f416cae97c02c1d33def00f5da024ca094c12ff803009b597f'),
    'trust_sell_none_obj': (('ok', _last((-100.0, 55.6, 10.0))),
                            'e69b7e5c93db4cf3785f42448cc1c79b017eb18f86f8598f2e597dce668cc748'),
    'hedge_sell_none_obj': (('ok', _last((-100.0, 50.0, 20.0))),
                            '03433a7874b35db0043d4e315bf9243cc9b128ba611a550e87e53892e0d215e5'),
    'self_buy_none_obj': (('ok', _last((-100.0, 50.0, 0.0))),
                          'b3171be3086338eaf79362e42eb06622f58a9e1caf8e441c44f796caa1ad7f1b'),
    'self_buy_unparsable': (('raise', 'ValueError'), None),
    'hedge_sell_blank': (('ok', _last((-100.0, 50.0, 20.0))),
                         '03433a7874b35db0043d4e315bf9243cc9b128ba611a550e87e53892e0d215e5'),
}

_UNAFFECTED = ('normal', 'normal_object', 'real_zero_last', 'single_nan_foreign', 'single_nan_trust',
               'single_nan_hedge_sell', 'buy_sell_all_nan', 'self_row_absent', 'hedge_row_absent',
               'dealer_rows_absent')
#: 修後應得（各日三欄）＋ 修後表格應與哪個「既有缺值路徑」案例（修前 golden）逐字相同
_ALL_NAN = ([(_N, _N, _N)] * 4, 'buy_sell_all_nan')
_FIXED = {
    'no_buy_col': _ALL_NAN, 'no_sell_col': _ALL_NAN, 'no_buy_sell_cols': _ALL_NAN,
    'buy_all_none_obj': _ALL_NAN, 'sell_all_none_obj': _ALL_NAN, 'buy_sell_all_none_obj': _ALL_NAN,
    'foreign_none_obj': (_last((_N, 50.0, 10.0)), 'single_nan_foreign'),
    'trust_none_obj': (_last((-100.0, _N, 10.0)), 'single_nan_trust'),
    'trust_sell_none_obj': (_last((-100.0, _N, 10.0)), 'single_nan_trust'),
    'dealer_both_none_obj': (_last((-100.0, 50.0, _N)), 'single_nan_hedge_sell'),
    'hedge_sell_none_obj': (_last((-100.0, 50.0, _N)), 'single_nan_hedge_sell'),
    'self_buy_none_obj': (_last((-100.0, 50.0, _N)), 'single_nan_hedge_sell'),
    'self_buy_unparsable': (_last((-100.0, 50.0, _N)), 'single_nan_hedge_sell'),
    'hedge_sell_blank': (_last((-100.0, 50.0, _N)), 'single_nan_hedge_sell'),
}
#: 修前結果確定（不依 pandas 對 object 列 None 的轉型細節）的錯誤案例 —— 突變比對用
_MUTANT = ('no_buy_col', 'no_sell_col', 'no_buy_sell_cols', 'buy_all_none_obj', 'sell_all_none_obj',
           'trust_sell_none_obj', 'hedge_sell_none_obj', 'self_buy_none_obj', 'self_buy_unparsable',
           'hedge_sell_blank')


def _row_cells(html: str, date_txt: str) -> list[str]:
    rows = [r for r in html.split('<tr>') if f'>{date_txt}</td>' in r]
    assert len(rows) == 1
    return [re.sub(r'<[^>]+>', '', c) for c in re.findall(r'<td[^>]*>(.*?)</td>', rows[0])]


# ══════════════════════════════════════════════════════════════════════════
# 3. L1：build_leading_fast
# ══════════════════════════════════════════════════════════════════════════
class TestL1:
    @pytest.mark.parametrize('case', _UNAFFECTED)
    def test_unaffected_equals_pre_golden(self, case, monkeypatch, tmp_path):
        """真實 0、正負值、單一儲存格 null（既有 NaN）、子列整列不存在 ⇒ 數值與表格逐字同修前。"""
        assert _outcome(monkeypatch, tmp_path, case) == PRE_GOLDEN[case]

    @pytest.mark.parametrize('case', sorted(_FIXED))
    def test_missing_is_nan_and_table_uses_existing_missing_path(self, case, monkeypatch, tmp_path):
        """整欄缺／整欄 None／該列 None 或不可解析／自營半套 ⇒ 缺（NaN），不是 0 或假淨額；
        表格逐字 ＝ 修前同位置本來就是 NaN 的案例（既有「-」路徑）；其他欄／其他日不變。"""
        want, same_as = _FIXED[case]
        (kind, got), html = _outcome(monkeypatch, tmp_path, case)
        assert kind == 'ok' and got == want
        assert html == PRE_GOLDEN[same_as][1]

    def test_table_shows_dash(self, monkeypatch, tmp_path):
        df = _fast(monkeypatch, tmp_path, 'no_buy_col')
        for d in df['日期']:
            assert _row_cells(render_leading_table(df), d)[2:5] == ['-', '-', '-']
        df = _fast(monkeypatch, tmp_path, 'hedge_sell_blank')
        html = render_leading_table(df)
        assert _row_cells(html, df['日期'].iloc[-1])[2:5] == ['▼ 100.0', '▲ 50.0', '-']
        assert _row_cells(html, df['日期'].iloc[0])[2:5] == ['▼ 20.0', '▲ 10.0', '▲ 5.0']

    def test_real_zero_shows_zero(self, monkeypatch, tmp_path):
        df = _fast(monkeypatch, tmp_path, 'real_zero_last')
        assert _row_cells(render_leading_table(df), df['日期'].iloc[-1])[2:5] == ['0.0', '0.0', '0.0']

    @pytest.mark.parametrize('case', _MUTANT)
    def test_mutation_revert_restores_pre_behavior(self, case, monkeypatch, tmp_path):
        """突變：還原本批那一處 ⇒ 重現修前假 0／假淨額／拋例外（＝修前 golden）⇒ 上方斷言轉紅。"""
        pre = _outcome(monkeypatch, tmp_path, case, z37_pre_module())
        assert pre == PRE_GOLDEN[case]
        assert pre[0] != ('ok', _FIXED[case][0])

    @pytest.mark.parametrize('case', _UNAFFECTED)
    def test_mutation_revert_unaffected_same(self, case, monkeypatch, tmp_path):
        """還原體在不受影響案例上與現行同結果（證明本批只動缺值路徑）。"""
        assert _outcome(monkeypatch, tmp_path, case, z37_pre_module()) == PRE_GOLDEN[case]


# ══════════════════════════════════════════════════════════════════════════
# 4. 下游：§三 籌碼段（表格、進階警示、最新一筆原始值、籌碼綜合判斷）＋ ai_qa
# ══════════════════════════════════════════════════════════════════════════
from tests.test_batch_z30 import _chips  # noqa: E402

#: 修後 → 應與「修前同位置本來就是 NaN」的案例畫面逐字相同
_CHIPS_PAIRS = [('no_buy_col', 'buy_sell_all_nan'), ('buy_all_none_obj', 'buy_sell_all_nan'),
                ('foreign_none_obj', 'single_nan_foreign'), ('trust_sell_none_obj', 'single_nan_trust'),
                ('hedge_sell_blank', 'single_nan_hedge_sell'), ('self_buy_unparsable', 'single_nan_hedge_sell')]


def _raw_line(out) -> str:
    codes = [t for k, t in out if k == 'code']
    assert len(codes) == 1
    return codes[0]


class TestDownstream:
    @pytest.mark.parametrize('case,ref', _CHIPS_PAIRS)
    def test_chips_same_as_existing_nan_path(self, case, ref, monkeypatch, tmp_path):
        """§三 整段（表格／警示／最新一筆原始值／綜合判斷）不崩，且逐字 ＝ 既有 NaN 路徑。"""
        out = _chips(_fast(monkeypatch, tmp_path, case), monkeypatch)
        assert out == _chips(_fast(monkeypatch, tmp_path, ref), monkeypatch)

    def test_raw_values_and_warning(self, monkeypatch, tmp_path):
        """整欄缺 ⇒ 最新一筆原始值不列外資／投信／自營、不出「外資投信同賣」；修前（突變）會出假警示與假值。"""
        out = _chips(_fast(monkeypatch, tmp_path, 'no_buy_col'), monkeypatch)
        raw = _raw_line(out)
        assert all(f'{c}=' not in raw for c in ('外資', '投信', '自營'))
        txt = '\n'.join(t for _k, t in out)
        assert '外資投信同賣' not in txt
        pre = _chips(_fast(monkeypatch, tmp_path, 'no_buy_col', z37_pre_module()), monkeypatch)
        assert '外資投信同賣' in '\n'.join(t for _k, t in pre)
        assert '外資=-199' in _raw_line(pre)

    def test_raw_values_dealer_half(self, monkeypatch, tmp_path):
        out = _chips(_fast(monkeypatch, tmp_path, 'hedge_sell_blank'), monkeypatch)
        raw = _raw_line(out)
        assert '外資=-100' in raw and '投信=+50' in raw and '自營=' not in raw
        pre = _chips(_fast(monkeypatch, tmp_path, 'hedge_sell_blank', z37_pre_module()), monkeypatch)
        assert '自營=+20' in _raw_line(pre)

    @pytest.mark.parametrize('case', ['no_buy_col', 'hedge_sell_blank', 'self_buy_unparsable'])
    def test_ai_qa_tool(self, case, monkeypatch, tmp_path):
        """ai_qa `_tool_get_market_leading`：缺值以 NaN 送出（同既有單格 null），可 JSON 化、不崩。"""
        import src.services.ai_qa_service as QA
        _patch(monkeypatch, CASES[case](), tmp_path)
        monkeypatch.setattr(QA, '_finmind_token', lambda: 'z37')
        r = QA._tool_get_market_leading(days=7)
        assert r['ok'] is True
        d = r['data']
        missing = ('外資', '投信', '自營') if case == 'no_buy_col' else ('自營',)
        for c in missing:
            assert isinstance(d[c], float) and math.isnan(d[c])
        for c in set(('外資', '投信', '自營')) - set(missing):
            assert not math.isnan(d[c])
        json.dumps(QA._json_safe(r))
