"""批 Z47 —— 新 UI 查一檔頁「籌碼」卡擋非有限值（NaN／±inf）。

Bug（合成資料重現）：外資欄含 ±inf → L0 集中度 inf／nan → L3
`src/services/stock_chips_service.py::_num` 只 `float()`、不擋非有限 →
`page_inspect._fmt_num` 只擋 None → live 卡印「集中度 inf%／nan%」；
最新一日主力合計 = inf → L2 `inst_sanity` ratio=inf、is_outlier=True →
徽章印「達均量的 inf 倍」。
依 CLAUDE.md §1 ＋客戶授權「擋非有限值」：
  (1) L3 `_num`：非有限 → None（對齊 `page_inspect._num`）；
  (2) L3 `_outlier_fields`：ratio 非有限 → 不下有／沒有異常的結論，走既有「判不出來」；
  (3) `page_inspect._fmt_num`／`_fmt_pct`：非有限值與 None 同輸出「—」。
⛔ 不新增文案、不改版面、不新增 helper、不改門檻、不動 L0 fillna(0)。

本檔驗：
  A. L3 `_num`／`_int`、UI `_fmt_num`／`_fmt_pct` 單元。
  B. 外資含 ±inf／最新一日 inf 的合成 df → 卡片輸出不含 'nan'／'inf'。
  C. 有限值輸出與修前逐字相同（還原體對照）。
  D. 突變：把本批修正還原（還原 pair）→ B 的斷言轉紅。
"""
from __future__ import annotations

import functools
import math
import pathlib
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.data.stock.app_stock_fetchers as F
import src.services.stock_chips_service as SVC
import src.ui.views.page_inspect as PI

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SVC = 'src/services/stock_chips_service.py'
_INSPECT = 'src/ui/views/page_inspect.py'

#: (修後逐字, 修前逐字) —— 正式碼字面一改即找不到替換點而失敗（字面錨點）
Z47_SVC_PAIRS = (
    ("        _f = float(value)\n"
     "    except (TypeError, ValueError):\n"
     "        return None\n"
     "    if not math.isfinite(_f):   # NaN／±inf ＝ 缺值（§1：不印 nan／inf；對齊 page_inspect._num）\n"
     "        return None\n"
     "    return _f\n",
     "        return float(value)\n"
     "    except (TypeError, ValueError):\n"
     "        return None\n"),
    ('    if bool(getattr(_res, "is_outlier", False)) and _ratio is not None:\n'
     '        _verdict = OUTLIER_ANOMALY\n'
     '    elif _reason == "ok" and _ratio is not None:\n',
     '    if bool(getattr(_res, "is_outlier", False)):\n'
     '        _verdict = OUTLIER_ANOMALY\n'
     '    elif _reason == "ok":\n'),
)
Z47_INSPECT_PAIRS = (
    ('    return ("—" if value is None or not math.isfinite(value)\n'
     '            else f"{value:+.{digits}f}%")\n',
     '    return "—" if value is None else f"{value:+.{digits}f}%"\n'),
    ('    return ("—" if value is None or not math.isfinite(value)\n'
     '            else f"{value:.{digits}f}{unit}")\n',
     '    return "—" if value is None else f"{value:.{digits}f}{unit}"\n'),
)


def _pre(rel, pairs, name):
    path = _ROOT / rel
    code = path.read_text(encoding='utf-8')
    for new, old in pairs:
        assert code.count(new) == 1, f'替換點不唯一或已不存在：{new[:40]!r}'
        code = code.replace(new, old)
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m          # dataclass 解析註解需要模組已註冊
    exec(compile(code, str(path), 'exec'), m.__dict__)
    return m


@functools.lru_cache(maxsize=None)
def z47_pre_svc():
    return _pre(_SVC, Z47_SVC_PAIRS, '_z47_pre_svc')


@functools.lru_cache(maxsize=None)
def z47_pre_inspect():
    return _pre(_INSPECT, Z47_INSPECT_PAIRS, '_z47_pre_inspect')


# ── 合成資料 ─────────────────────────────────────────────────────────────
def _df(foreign=None, inst_last=100.0):
    n = 40
    d = pd.DataFrame({'外資': [50.0] * n, '投信': [10.0] * n,
                      '主力合計': [60.0] * n, 'volume': [1000] * n},
                     index=pd.date_range('2026-01-01', periods=n))
    if foreign is not None:
        d['外資'] = foreign
    d.iloc[-1, d.columns.get_loc('主力合計')] = inst_last
    return d


_CASES = {
    'inf_in_foreign': dict(foreign=[50.0] * 39 + [np.inf]),
    'pos_neg_inf_foreign': dict(foreign=[np.inf] * 39 + [-np.inf]),
    'inf_inst_last': dict(inst_last=np.inf),
}


class _Verdict:
    requested = True
    is_stock = True
    code = '2330'


class _Req:
    period_days = 120


def _render(svc_mod, ui_mod, df, monkeypatch):
    """L1 換成合成 df → L3 → load_chips → build_chips_card，回整份輸出的 repr。"""
    monkeypatch.setattr(F, 'fetch_price_data', lambda sid, days: (df, 'X', ''))
    monkeypatch.setitem(sys.modules, 'src.services.stock_chips_service', svc_mod)
    card, facts, sig = ui_mod.build_chips_card(ui_mod.load_chips(_Verdict(), _Req()))
    return card, facts, sig


# ── A ────────────────────────────────────────────────────────────────────
_NON_FINITE = [float('nan'), float('inf'), float('-inf'), 'nan', 'inf', '-inf', np.inf]


@pytest.mark.parametrize('raw', _NON_FINITE, ids=repr)
def test_svc_num_non_finite_is_missing(raw):
    assert SVC._num(raw) is None
    assert SVC._int(raw) is None          # 修前 int(inf) 會 OverflowError、int(nan) ValueError


@pytest.mark.parametrize('raw,want', [(1.5, 1.5), (0, 0.0), (-2, -2.0), ('3.25', 3.25)], ids=repr)
def test_svc_num_finite_unchanged(raw, want):
    got = SVC._num(raw)
    assert isinstance(got, float) and math.isclose(got, want, rel_tol=0, abs_tol=0)


@pytest.mark.parametrize('raw', [None, True, 'abc', object()], ids=repr)
def test_svc_num_existing_missing_unchanged(raw):
    assert SVC._num(raw) is None


@pytest.mark.parametrize('v', [float('nan'), float('inf'), float('-inf'), None], ids=repr)
def test_fmt_non_finite_dash(v):
    assert PI._fmt_num(v) == '—' and PI._fmt_num(v, digits=2, unit='%') == '—'
    assert PI._fmt_pct(v) == '—'


@pytest.mark.parametrize('v', [0.0, 1.234, -5.0, 12], ids=repr)
def test_fmt_finite_same_as_pre(v):
    pre = z47_pre_inspect()
    assert PI._fmt_num(v, digits=2) == pre._fmt_num(v, digits=2)
    assert PI._fmt_pct(v) == pre._fmt_pct(v)


# ── B ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('case', sorted(_CASES), ids=str)
def test_card_never_prints_nan_inf(case, monkeypatch):
    out = repr(_render(SVC, PI, _df(**_CASES[case]), monkeypatch)).lower()
    assert 'nan' not in out and 'inf' not in out


def test_inf_ratio_is_not_judged(monkeypatch):
    monkeypatch.setattr(F, 'fetch_price_data', lambda sid, days: (_df(inst_last=np.inf), 'X', ''))
    r = SVC.get_chips_readout('2330', days=120)
    assert r.outlier_verdict == SVC.OUTLIER_UNKNOWN and r.outlier_ratio is None
    assert r.outlier_threshold is not None            # 門檻照讀，未改


# ── C ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('kw', [{}, dict(inst_last=10000.0), dict(inst_last=0.0)], ids=repr)
def test_finite_output_byte_identical_to_pre(kw, monkeypatch):
    now = repr(_render(SVC, PI, _df(**kw), monkeypatch))
    pre = repr(_render(z47_pre_svc(), z47_pre_inspect(), _df(**kw), monkeypatch))
    assert now == pre


# ── D 突變 ───────────────────────────────────────────────────────────────
def test_mutation_revert_turns_red(monkeypatch):
    pre_svc, pre_ui = z47_pre_svc(), z47_pre_inspect()
    assert pre_svc._num(float('inf')) == float('inf')                       # 還原體：inf 漏過
    assert pre_ui._fmt_num(float('nan')) == 'nan'
    out = repr(_render(pre_svc, pre_ui, _df(**_CASES['inf_in_foreign']), monkeypatch))
    assert 'inf%' in out                                                    # 還原體：集中度 inf%
    out = repr(_render(pre_svc, pre_ui, _df(**_CASES['pos_neg_inf_foreign']), monkeypatch))
    assert 'nan%' in out
    out = repr(_render(pre_svc, pre_ui, _df(**_CASES['inf_inst_last']), monkeypatch))
    assert 'inf 倍' in out                                                  # 還原體：徽章 inf 倍
    # 只還原 verdict 那一處（_num 保留修後）→ 徽章退成「有異常 … — 倍」（仍斷言錯誤結論）
    code = (_ROOT / _SVC).read_text(encoding='utf-8')
    new, old = Z47_SVC_PAIRS[1]
    m = types.ModuleType('_z47_pre_verdict_only')
    m.__file__ = str(_ROOT / _SVC)
    sys.modules[m.__name__] = m
    exec(compile(code.replace(new, old), m.__file__, 'exec'), m.__dict__)
    monkeypatch.setattr(F, 'fetch_price_data', lambda sid, days: (_df(inst_last=np.inf), 'X', ''))
    assert m.get_chips_readout('2330', days=120).outlier_verdict == m.OUTLIER_ANOMALY


# ── E：`elif _reason == "ok" and _ratio is not None` 的行為測試（QA 補缺口）──
#: 只還原 NORMAL 那一行的 pair（ANOMALY 那一行保留修後）
Z47_OK_LINE_PAIR = ('    elif _reason == "ok" and _ratio is not None:\n',
                    '    elif _reason == "ok":\n')


def _df_inf_inst_and_vol():
    d = _df(inst_last=np.inf)
    d['volume'] = d['volume'].astype(float)
    d.iloc[-1, d.columns.get_loc('volume')] = np.inf      # ratio = inf / inf = NaN、reason='ok'
    return d


def test_l2_precondition_nan_ratio_reason_ok():
    from src.compute.risk.inst_sanity import flag_latest_inst_outlier_from_df
    r = flag_latest_inst_outlier_from_df(_df_inf_inst_and_vol())
    assert r.reason == 'ok' and not r.is_outlier and math.isnan(r.ratio)


def test_nan_ratio_ok_not_judged_normal(monkeypatch):
    card = _render(SVC, PI, _df_inf_inst_and_vol(), monkeypatch)
    out = repr(card)
    assert '判過了，沒有異常' not in out
    assert 'nan' not in out.lower()


def test_mutation_ok_line_only_turns_red(monkeypatch):
    code = (_ROOT / _SVC).read_text(encoding='utf-8')
    new, old = Z47_OK_LINE_PAIR
    assert code.count(new) == 1, '替換點不唯一或已不存在'
    m = types.ModuleType('_z47_pre_ok_line_only')
    m.__file__ = str(_ROOT / _SVC)
    sys.modules[m.__name__] = m
    exec(compile(code.replace(new, old), m.__file__, 'exec'), m.__dict__)
    out = repr(_render(m, PI, _df_inf_inst_and_vol(), monkeypatch))
    assert '判過了，沒有異常' in out                     # 還原體：NaN 倍數被判成「沒有異常」
