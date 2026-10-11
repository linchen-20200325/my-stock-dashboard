"""批 Z40 跟進 —— 先行指標 BFI82U 自營商避險缺值時不再退回半套自行買賣（客戶 Q-z25＝A／Q-z21；基底 `7de354e8`）。

L1 `src/data/macro/leading_indicators.py::twse_institutional_day`（`build_leading_indicators` full 路徑逐日呼叫）：
- 自營商 ＝ 自營商（自行買賣）＋ 自營商（避險）（Q-z25＝A）；
- 自行、避險**兩列都可解析**才給「自營」；任一列缺／不可解析（`to_num` → None）⇒ 不給「自營」key
  ＝ 本函式既有缺值表示（修前「兩列都缺」本來就走這條），下游 `inst.get("自營")` → None → 表格「-」；
  ⛔ 修前 `elif self_diff is not None: result["自營"] = self_diff`（只剩自行買賣的半套）已拔（Q-z21：半套不當完整）。
- 真 0 ＝ 0；外資自營商列（Q-z24＝A'）不進任何一類（現況已排除，本檔以行為守）。

突變：`Z40B_REVERT_PAIRS` 為「修後逐字 → 修前逐字」（恰一處）；還原體逐字 ＝ 基底 `7de354e8` 檔（sha256 自證），
實跑重現修前半套 ⇒ 對應斷言轉紅。舊批次 Z37 還原鏈（`tests/test_batch_z37.py::z37_revert`）先串本批 pair
（同 Z36 串 Z40 慣例）。本檔所有斷言皆為實跑行為斷言（還原體 sha 自證除外）。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_LI = 'src/data/macro/leading_indicators.py'

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 pair（先於任何 tests.* import 定義 —— tests/test_batch_z37.py 會回頭 import 本表）
# ══════════════════════════════════════════════════════════════════════════
Z40B_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _LI: (
        ('        # 批 Z40 跟進（客戶 Q-z25＝A：自營商＝自行＋避險；Q-z21：半套不當完整）：自行、避險任一列缺／\n'
         '        #   不可解析 ⇒ 不給「自營」key（＝本函式既有缺值表示，下游 `inst.get("自營")` → None → 表格「-」），\n'
         '        #   ⛔ 不退回只取自行買賣（修前半套）。外資自營商列不進任何一類（上方分支皆不命中）。\n'
         '        elif self_diff is not None or hedge_diff is not None:\n'
         '            print(f"[twse_institutional_day] {date_ymd} 自營商半套（自行={self_diff} 避險={hedge_diff}）"\n'
         '                  f"→ 自營商為缺值（不以單邊充當自營商）", file=sys.stderr)\n',
         '        elif self_diff is not None:\n'
         '            result["自營"] = self_diff\n'),
    ),
}
#: 基底 `7de354e8` 原始檔 sha256（`git show 7de354e8:<檔> | sha256sum` 實算；寫死以免測試依賴 git）
Z40B_BASE_SHA = {_LI: 'b6badbdf225f1085f99486e271a3f63297b9e4440a5a0cf9f153bd32c164fb4e'}


def z40b_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。"""
    p = pathlib.Path(file_path)
    rel = (p.resolve().relative_to(_ROOT) if p.is_absolute() else p).as_posix()
    for new, old in Z40B_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f'{rel} 替換點不唯一或已不存在：{new!r}'
        code = code.replace(new, old)
    return code


@functools.lru_cache(maxsize=None)
def z40b_pre_module(rel: str = _LI):
    """現行檔只把本批改動換回基底 `7de354e8` 寫法（獨立模組物件，不影響本尊）。"""
    path = _ROOT / rel
    name = '_z40b_pre_' + rel.replace('/', '_').removesuffix('.py')
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(z40b_revert_for(rel, path.read_text(encoding='utf-8')), str(path), 'exec'), m.__dict__)
    return m


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試
# ══════════════════════════════════════════════════════════════════════════
import datetime as _dt  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

import src.data.macro.leading_indicators as LI  # noqa: E402


def test_reverted_source_equals_base_file():
    """還原體原始碼逐字 ＝ 基底 `7de354e8` 檔案 ⇒ 下方「修前」突變斷言跑的是真修前碼。"""
    code = z40b_revert_for(_LI, (_ROOT / _LI).read_text(encoding='utf-8'))
    assert hashlib.sha256(code.encode('utf-8')).hexdigest() == Z40B_BASE_SHA[_LI]


def test_z37_chain_includes_z40b_pairs():
    """Z37 還原鏈已串接本批（否則 Z37 的 `test_reverted_source_equals_base_file` 會轉紅）。"""
    from tests import test_batch_z37 as Z37
    code = Z37.z37_revert(_LI, (_ROOT / _LI).read_text(encoding='utf-8'))
    assert hashlib.sha256(code.encode('utf-8')).hexdigest() == Z37.Z37_BASE_SHA[_LI]


# ══════════════════════════════════════════════════════════════════════════
# 1. harness：BFI82U JSON 形狀 → twse_institutional_day（離線）
# ══════════════════════════════════════════════════════════════════════════
_SELF, _HEDGE, _TRUST, _FGN, _FD = ('自營商(自行買賣)', '自營商(避險)', '投信',
                                    '外資及陸資(不含外資自營商)', '外資自營商')

#: 元（買賣差額字串，同 TWSE 千分位格式）
_BASE_ROWS = {
    _SELF: '1,234,567,890',      # 12.3456… 億
    _HEDGE: '-456,789,012',      # -4.5678… 億
    _TRUST: '2,000,000,000',
    _FGN: '-15,050,000,000',
    _FD: '0',
}


def _payload(rows: dict) -> dict:
    data = [[nm, '1', '1', v] for nm, v in rows.items()]
    data.append(['合計', '1', '1', '999'])           # 末列合計（函式 `[:-1]` 丟掉）
    return {'stat': 'OK', 'fields': ['單位名稱', '買進金額', '賣出金額', '買賣差額'], 'data': data}


class _Resp:
    def __init__(self, j):
        self._j = j

    def json(self):
        return self._j


class _Sess:
    def __init__(self, j):
        self._j = j

    def get(self, *a, **k):
        return _Resp(self._j)


def _call(monkeypatch, rows: dict, mod=LI):
    monkeypatch.setattr(mod, '_TWSE_S', _Sess(_payload(rows)))
    return mod.twse_institutional_day('20261008')


def _without(name):
    return {k: v for k, v in _BASE_ROWS.items() if k != name}


def _with(name, val):
    return {**_BASE_ROWS, name: val}


_SELF_BN = round(1_234_567_890 / 1e8, 1)
_HEDGE_BN = round(-456_789_012 / 1e8, 1)
_WANT_FULL = {'自營': round(_SELF_BN + _HEDGE_BN, 1), '投信': 20.0, '外資': -150.5}

#: 自營半套情境（自行或避險缺／髒）
_HALF = {
    'hedge_row_missing': _without(_HEDGE),
    'hedge_dash': _with(_HEDGE, '--'),
    'hedge_blank': _with(_HEDGE, ''),
    'hedge_na': _with(_HEDGE, 'N/A'),
    'hedge_text': _with(_HEDGE, 'abc'),
    'self_row_missing': _without(_SELF),
    'self_dash': _with(_SELF, '--'),
    'self_none_str': _with(_SELF, 'None'),
}


# ══════════════════════════════════════════════════════════════════════════
# 2. L1 行為
# ══════════════════════════════════════════════════════════════════════════
class TestL1:
    def test_both_present_sum(self, monkeypatch):
        assert _call(monkeypatch, _BASE_ROWS) == _WANT_FULL

    @pytest.mark.parametrize('case', sorted(_HALF))
    def test_half_dealer_is_missing(self, case, monkeypatch, capsys):
        """自行或避險任一缺／不可解析 ⇒ 不給「自營」（缺值），外資／投信不受影響；有 log。"""
        got = _call(monkeypatch, _HALF[case])
        assert '自營' not in got
        assert got == {'投信': 20.0, '外資': -150.5}
        assert '自營商半套' in capsys.readouterr().err

    def test_both_missing_same_as_before(self, monkeypatch, capsys):
        """兩列都缺 ⇒ 缺值（修前即如此）；不印半套 log。"""
        got = _call(monkeypatch, {k: v for k, v in _BASE_ROWS.items() if k not in (_SELF, _HEDGE)})
        assert got == {'投信': 20.0, '外資': -150.5}
        assert '自營商半套' not in capsys.readouterr().err

    def test_real_zero_stays_zero(self, monkeypatch):
        got = _call(monkeypatch, {**_BASE_ROWS, _SELF: '0', _HEDGE: '0'})
        assert '自營' in got and got['自營'] == 0 and not math.isnan(got['自營'])

    def test_one_side_real_zero_is_complete(self, monkeypatch):
        """避險真 0（可解析）≠ 缺：自營 ＝ 自行 ＋ 0。"""
        got = _call(monkeypatch, {**_BASE_ROWS, _HEDGE: '0'})
        assert got['自營'] == _SELF_BN

    @pytest.mark.parametrize('fd', ['35,206,790', '-35,206,790', '9,999,999,999'])
    def test_foreign_dealer_not_counted(self, fd, monkeypatch):
        """外資自營商非零（Q-z24＝A'）⇒ 不進外資、不進自營、不進投信。"""
        assert _call(monkeypatch, _with(_FD, fd)) == _WANT_FULL

    @pytest.mark.parametrize('fd', ['35,206,790', '-35,206,790'])
    def test_foreign_dealer_not_counted_when_half(self, fd, monkeypatch):
        """避險缺時，外資自營商也不得被拿來補自營。"""
        rows = {**_HALF['hedge_row_missing'], _FD: fd}
        assert '自營' not in _call(monkeypatch, rows)

    def test_stat_not_ok_empty(self, monkeypatch):
        monkeypatch.setattr(LI, '_TWSE_S', _Sess({'stat': 'NO DATA'}))
        assert LI.twse_institutional_day('20261008') == {}


class TestMutation:
    @pytest.mark.parametrize('case', [c for c in sorted(_HALF) if c.startswith('hedge')])
    def test_revert_restores_half_dealer(self, case, monkeypatch):
        """突變：還原本批那一處 ⇒ 避險缺時退回半套「自營 ＝ 自行買賣」⇒ 上方 `test_half_dealer_is_missing` 轉紅。"""
        pre = _call(monkeypatch, _HALF[case], z40b_pre_module())
        assert pre.get('自營') == _SELF_BN
        assert pre != _call(monkeypatch, _HALF[case])

    @pytest.mark.parametrize('rows', [_BASE_ROWS, _HALF['self_row_missing'], _with(_FD, '35,206,790')],
                             ids=['full', 'self_missing', 'fd_nonzero'])
    def test_revert_unaffected_same(self, rows, monkeypatch):
        """還原體在不受影響情境上與現行同結果（證明本批只動半套路徑）。"""
        assert _call(monkeypatch, rows, z40b_pre_module()) == _call(monkeypatch, rows)


# ══════════════════════════════════════════════════════════════════════════
# 3. 下游：build_leading_indicators（full）→ DataFrame → render_leading_table
# ══════════════════════════════════════════════════════════════════════════
_DAYS = ['20261006', '20261007', '20261008']


def _full_df(monkeypatch, per_day_rows: dict, mod=LI):
    payloads = {d: _payload(r) for d, r in per_day_rows.items()}

    class _DaySess:
        def get(self, url, params=None, **k):
            return _Resp(payloads[params['dayDate']])

    monkeypatch.setattr(mod, '_TWSE_S', _DaySess())
    monkeypatch.setattr(mod, 'twse_volume', lambda m: {d: 3000.0 for d in _DAYS})
    monkeypatch.setattr(mod, 'finmind_fut_oi', lambda s, e, t: {})
    monkeypatch.setattr(mod, 'taifex_pcr', lambda s, e: {})
    monkeypatch.setattr(mod, 'taifex_large_trader', lambda d: {})
    monkeypatch.setattr(mod, 'taifex_calls_puts_day', lambda d: None)
    monkeypatch.setattr(mod, 'taifex_mtx_data', lambda d: None)
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)
    return mod.build_leading_indicators(_dt.date(2026, 10, 6), _dt.date(2026, 10, 8))


def _cells(html: str, date_txt: str) -> list[str]:
    rows = [r for r in html.split('<tr>') if f'>{date_txt}</td>' in r]
    assert len(rows) == 1
    return [re.sub(r'<[^>]+>', '', c) for c in re.findall(r'<td[^>]*>(.*?)</td>', rows[0])]


class TestDownstream:
    def test_half_day_is_missing_and_table_dash(self, monkeypatch):
        """避險缺的那天 ⇒ df「自營」為缺值（非 0）、表格走既有「-」；其他天／其他欄不變。"""
        df = _full_df(monkeypatch, {_DAYS[0]: _BASE_ROWS, _DAYS[1]: _HALF['hedge_dash'],
                                    _DAYS[2]: _BASE_ROWS})
        v = df.loc[df['_date'] == _DAYS[1], '自營'].iloc[0]
        assert v is None or (isinstance(v, float) and math.isnan(v))
        assert df.loc[df['_date'] == _DAYS[0], '自營'].iloc[0] == _WANT_FULL['自營']
        html = LI.render_leading_table(df)
        half = _cells(html, '10月7日')
        assert half[2:5] == ['▼ 150.5', '▲ 20.0', '-']
        assert _cells(html, '10月6日')[4] == f'▲ {_WANT_FULL["自營"]}'

    def test_half_cell_same_as_existing_both_missing_path(self, monkeypatch):
        """半套那天的表格列 ＝ 修前就存在的「自行、避險兩列都缺」那天的表格列（既有缺值路徑，逐字）。"""
        both_missing = {k: v for k, v in _BASE_ROWS.items() if k not in (_SELF, _HEDGE)}
        a = _full_df(monkeypatch, {d: _HALF['hedge_row_missing'] for d in _DAYS})
        b = _full_df(monkeypatch, {d: both_missing for d in _DAYS})
        cols = ['_date', '日期', '外資', '投信', '自營']
        pd.testing.assert_frame_equal(a[cols], b[cols])
        assert LI.render_leading_table(a) == LI.render_leading_table(b)

    def test_mutation_downstream_shows_half_value(self, monkeypatch):
        """突變：還原後半套那天表格顯示自行買賣單邊值（▲ 12.3），不是「-」⇒ 上方斷言轉紅。"""
        df = _full_df(monkeypatch, {d: _HALF['hedge_dash'] for d in _DAYS}, z40b_pre_module())
        assert df['自營'].tolist() == [_SELF_BN] * 3
        assert _cells(z40b_pre_module().render_leading_table(df), '10月7日')[4] == f'▲ {_SELF_BN}'
