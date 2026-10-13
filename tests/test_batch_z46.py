"""批 Z46 —— 新 UI `src/ui/views/page_inspect.py::_num` 擋非有限值（NaN／±inf）。

Bug（實測重現）：`_num(nan)` 回 nan → `EtfReadout(premium_pct=nan)` → `build_premium_card`
得 state='live'、value='+nan%'（綠燈卡印 nan）；`_fmt_num(_num('nan'))` 印 'nan'。
依 CLAUDE.md §1（Fail Loud, Never Fake）＋客戶 2026-10-02 ② 授權「擋非有限值」：
非有限值 ＝ 缺值（None），走既有 empty／灰卡路徑。⛔ 不新增文案、不改版面、不新增 helper。

本檔驗：
  A. nan／inf／-inf／'nan'／'inf'／'-inf' → None；正常數值、0、負數、數字字串不變。
  B. `build_premium_card`：premium_pct 經 `_num(nan)` → 不是 live，輸出不含 'nan'。
  C. 突變：把本批修正還原（還原 pair）→ A／B 的斷言轉紅。
"""
from __future__ import annotations

import functools
import math
import pathlib
import sys
import types

import pytest

import src.ui.views.page_inspect as PI

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_INSPECT = 'src/ui/views/page_inspect.py'

#: (修後逐字, 修前逐字) —— 正式碼字面一改即找不到替換點而失敗（字面錨點）
Z46_NUM_PAIR = (
    "        _f = float(value)\n"
    "    except (TypeError, ValueError):\n"
    "        return None\n"
    "    if not math.isfinite(_f):   # NaN／±inf ＝ 缺值（§1：不印 nan／inf）\n"
    "        return None\n"
    "    return _f\n",
    "        return float(value)\n"
    "    except (TypeError, ValueError):\n"
    "        return None\n",
)


@functools.lru_cache(maxsize=None)
def z46_pre_inspect_module():
    """現行 page_inspect 只把本批 `_num` 換回修前寫法（獨立模組物件，不影響本尊）。"""
    path = _ROOT / _INSPECT
    code = path.read_text(encoding='utf-8')
    new, old = Z46_NUM_PAIR
    assert code.count(new) == 1, '替換點不唯一或已不存在'
    name = '_z46_pre_inspect'
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m          # dataclass 解析註解需要模組已註冊
    exec(compile(code.replace(new, old), str(path), 'exec'), m.__dict__)
    return m


_NON_FINITE = [float('nan'), float('inf'), float('-inf'), 'nan', 'NaN', 'inf', '-inf']
_FINITE = [(1.5, 1.5), (0, 0.0), (0.0, 0.0), (-2, -2.0), (-0.75, -0.75),
           ('3.25', 3.25), ('-4', -4.0), ('0', 0.0)]


def _premium_card(mod, raw):
    return mod.build_premium_card(mod.EtfReadout(requested=True, premium_pct=mod._num(raw)))


# ── A ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('raw', _NON_FINITE, ids=repr)
def test_non_finite_is_missing(raw):
    assert PI._num(raw) is None
    assert PI._fmt_num(PI._num(raw)) == '—'
    assert PI._fmt_pct(PI._num(raw)) == '—'


@pytest.mark.parametrize('raw,want', _FINITE, ids=repr)
def test_finite_unchanged(raw, want):
    got = PI._num(raw)
    assert isinstance(got, float) and math.isclose(got, want, rel_tol=0, abs_tol=0)


@pytest.mark.parametrize('raw', [None, True, False, 'abc', '', object()], ids=repr)
def test_existing_missing_semantics_unchanged(raw):
    assert PI._num(raw) is None


# ── B ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('raw', _NON_FINITE, ids=repr)
def test_premium_card_non_finite_goes_empty(raw):
    card = _premium_card(PI, raw)[0]
    assert card.state != 'live'
    assert card.state == _premium_card(PI, None)[0].state     # 與既有缺值路徑同一態
    assert 'nan' not in repr(_premium_card(PI, raw)).lower()
    assert 'inf' not in str(card.value or '').lower()


def test_premium_card_finite_still_live():
    card = _premium_card(PI, 1.234)[0]
    assert card.state == 'live' and card.value == '+1.23%'


# ── C 突變 ───────────────────────────────────────────────────────────────
def test_mutation_revert_turns_red():
    pre = z46_pre_inspect_module()
    assert math.isnan(pre._num(float('nan')))                  # 還原體：nan 漏過
    # Z47 起 `_fmt_num`／`_fmt_pct` 自己也擋非有限值（第二道），所以只還原 `_num`
    # 時症狀從「印 nan」變成「nan 漏成綠燈卡（值印 —）」—— 仍是錯的態，照樣抓得到。
    card = _premium_card(pre, float('nan'))[0]
    assert card.state == 'live'                                # 還原體：nan 漏成綠燈卡
    # 本尊對同樣輸入給出相反結果 → A／B 在還原體上必紅
    assert PI._num(float('nan')) is None
    assert _premium_card(PI, float('nan'))[0].state != 'live'


# ══════════════════════════════════════════════════════════════════════════
# 同批第 2 項：`src/ui/views/page_hold.py::_num` 原本只擋 NaN，±inf 漏過 → 也回 None
# （NaN 既有行為不變；不新增文案／helper）。消費端驗：`_fmt_lots`、`load_vix` → `build_vix_card`。
# ══════════════════════════════════════════════════════════════════════════
import src.ui.views.page_hold as PH  # noqa: E402

_HOLD = 'src/ui/views/page_hold.py'

#: (修後逐字, 修前逐字)
Z46_HOLD_PAIR = (
    "    if not math.isfinite(_f):   # NaN／±inf ＝ 缺值（§1：不印 nan／inf）\n",
    "    if _f != _f:        # NaN\n",
)


@functools.lru_cache(maxsize=None)
def z46_pre_hold_module():
    """現行 page_hold 只把本批 `_num` 換回修前寫法（獨立模組物件，不影響本尊）。"""
    path = _ROOT / _HOLD
    code = path.read_text(encoding='utf-8')
    new, old = Z46_HOLD_PAIR
    assert code.count(new) == 1, '替換點不唯一或已不存在'
    name = '_z46_pre_hold'
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(code.replace(new, old), str(path), 'exec'), m.__dict__)
    return m


def _vix_card(mod, raw, monkeypatch):
    import src.services.dividend_station_service as DSS
    monkeypatch.setattr(DSS, 'fetch_vix', lambda strict=True: raw)
    return mod.build_vix_card(mod.load_vix(mod.HoldRequest(submitted=True)))[0]


@pytest.mark.parametrize('raw', _NON_FINITE, ids=repr)
def test_hold_non_finite_is_missing(raw):
    assert PH._num(raw) is None
    assert PH._fmt_lots(raw) == '—'
    assert PH._fmt_num(PH._num(raw), digits=2) == '—'


@pytest.mark.parametrize('raw,want', _FINITE, ids=repr)
def test_hold_finite_unchanged(raw, want):
    got = PH._num(raw)
    assert isinstance(got, float) and math.isclose(got, want, rel_tol=0, abs_tol=0)


@pytest.mark.parametrize('raw', [float('inf'), float('-inf'), 'inf', float('nan')], ids=repr)
def test_hold_vix_card_non_finite_not_live(raw, monkeypatch):
    card = _vix_card(PH, raw, monkeypatch)
    assert card.state != PH.UI_LIVE
    assert card.state == _vix_card(PH, None, monkeypatch).state   # 與既有「抓不到」同一態
    assert 'inf' not in str(card.value or '').lower()
    assert 'nan' not in str(card.value or '').lower()


def test_hold_vix_card_finite_still_live(monkeypatch):
    card = _vix_card(PH, 18.5, monkeypatch)
    assert card.state == PH.UI_LIVE and card.value == '18.50'


def test_hold_mutation_revert_turns_red(monkeypatch):
    pre = z46_pre_hold_module()
    assert pre._num(float('inf')) == float('inf')               # 還原體：inf 漏過
    assert pre._fmt_lots('inf') == 'inf'
    assert pre._num(float('nan')) is None                       # NaN 既有行為（修前即擋）
    # 批 Z52 起 VIX 卡另有兩道「資料異常」判定（`load_vix` 分流＋`build_vix_card`）——
    # 只拔 Z46 這一道時 inf 會被 Z52 擋成資料異常紅卡；要重現 Z46 修前的 inf 漏網，三道一起拔。
    from tests.test_batch_z52 import Z52_CARD_PAIR, Z52_LOAD_PAIR
    _code = (_ROOT / _HOLD).read_text(encoding='utf-8')
    for _new, _old in (Z46_HOLD_PAIR, Z52_CARD_PAIR, Z52_LOAD_PAIR):
        assert _code.count(_new) == 1, '替換點不唯一或已不存在'
        _code = _code.replace(_new, _old)
    pre3 = types.ModuleType('_z46_pre_hold_z52')
    pre3.__file__ = str(_ROOT / _HOLD)
    sys.modules[pre3.__name__] = pre3
    exec(compile(_code, str(_ROOT / _HOLD), 'exec'), pre3.__dict__)
    card = _vix_card(pre3, float('inf'), monkeypatch)
    assert card.state == pre3.UI_LIVE and 'inf' in str(card.value)
    assert _vix_card(pre, float('inf'), monkeypatch).state != pre.UI_LIVE   # Z52 仍擋
    assert PH._num(float('inf')) is None and PH._fmt_lots('inf') == '—'
