"""批 P3 · M2N-f8：§八 策略1「BIAS240 × 台灣出口」卡，出口缺值時走既有 CLI 備援分枝。

修前：`_exp_yoy8 = float(_m8_exp.get('yoy', 0)) if _m8_exp else None`
  · dict 在、缺 'yoy' 鍵 → 捏成 0.0 進矩陣，印「台灣出口 YoY=+0.0%」並下結論；
  · None → TypeError；'-' → ValueError（拋出 render_section_mid）；
  · NaN →「+nan%」且落進錯格（所有比較皆 False → 落到最後一格）；±inf 同理印 inf。
修後：沿用 KPI 卡同一組有限值 `_ey8_v` → 不可用時走**既有**「Export 無資料 → 降級用 CLI」
分枝（文案一字未動，與整個 tw_export 不存在時的輸出相同）。有限值時輸出與修前逐字相同。

harness 沿用 `tests/test_m2n2_no_zero_fill.py` 的假 st（全部離線）。
"""
from __future__ import annotations

import itertools
import math
import types

import numpy as np
import pytest

from tests.test_m2n2_no_zero_fill import _FakeST, _apply, _load, _mod, _source

_FIX = "            _exp_yoy8 = float(_ey8_v) if _ey8_v is not None else None\n"
_REVERT = ((_FIX, "            _exp_yoy8 = float(_m8_exp.get('yoy', 0)) if _m8_exp else None\n"),)


def _run(mod, macro_info: dict, bias, mp) -> dict:
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    fake = _FakeST({"macro_info": macro_info, "bias_info": {"bias_240": bias}})
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: None)
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None))
    mp.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
    exc = None
    try:
        mod.render_section_mid(False, {}, {}, {})
    except Exception as e:  # noqa: BLE001
        exc = (type(e).__name__, str(e))
    return {"exc": exc, "out": fake.out}


def _card(r) -> list[str]:
    return [t for _k, t in r["out"] if "年線乖離" in t]


@pytest.fixture(scope="module")
def pre_fix():
    return _load("mid", _apply(_source("mid"), _REVERT), "p3_f8_pre")


_MISSING = {
    "absent_key": {},
    "none": {"yoy": None},
    "dash": {"yoy": "-"},
    "nan": {"yoy": math.nan},
    "+inf": {"yoy": math.inf},
    "-inf": {"yoy": -math.inf},
    "bool": {"yoy": False},
}
_BIAS = (20.0, 5.0, -3.0)
#: CLI 備援三態：無 PMI／OECD CLI 擴張／收縮
_CLI = ({}, {"ism_pmi": {"value": 101.2, "is_oecd_cli": True}},
        {"ism_pmi": {"value": 98.7, "is_oecd_cli": True}})


def _info(exp, cli):
    d = dict(cli)
    if exp is not None:
        d["tw_export"] = dict(exp, date="2026-08")
    return d


# ── B：缺值 → 與「tw_export 根本不存在」走同一個既有 CLI 備援分枝 ─────────
@pytest.mark.parametrize("name", sorted(_MISSING))
def test_missing_uses_existing_cli_fallback(name, monkeypatch):
    for bias, cli in itertools.product(_BIAS, _CLI):
        now = _run(_mod("mid"), _info(_MISSING[name], cli), bias, monkeypatch)
        base = _run(_mod("mid"), _info(None, cli), bias, monkeypatch)
        assert now["exc"] is None, now["exc"]
        card = _card(now)
        assert card and card == _card(base), (name, bias, cli)
        assert not any("台灣出口 YoY=" in t for t in card)


# ── C：修前確實出事（前提守衛）───────────────────────────────────────────
def test_pre_fix_symptoms(pre_fix, monkeypatch):
    def card(exp):
        return _run(pre_fix, _info(exp, {}), 5.0, monkeypatch)
    assert any("台灣出口 YoY=+0.0%" in t for t in _card(card({})))
    assert card({"yoy": None})["exc"][0] == "TypeError"
    assert card({"yoy": "-"})["exc"][0] == "ValueError"
    assert any("+nan%" in t for t in _card(card({"yoy": math.nan})))


# ── D：有限值 → 與修前逐字相同（含矩陣各格邊界）─────────────────────────
_FINITE = [-12.3, -0.0, 0, 0.0, 0.01, 9.99, 10, 10.0, 15.5, np.float64(10.0), np.float64(-2.5)]


@pytest.mark.parametrize("v", _FINITE, ids=[repr(v) for v in _FINITE])
def test_finite_output_identical_to_pre_fix(v, pre_fix, monkeypatch):
    for bias in (20.0, 15.0, 5.0, 0.0, -3.0):
        info = _info({"yoy": v}, {})
        now = _run(_mod("mid"), info, bias, monkeypatch)
        pre = _run(pre_fix, info, bias, monkeypatch)
        assert now["exc"] is None and pre["exc"] is None
        assert now["out"] == pre["out"], (v, bias)
        assert any(f"台灣出口 YoY={float(v):+.1f}%" in t for t in _card(now))


# ── G：突變 —— 修前體／捏 0／直取原值都必須讓 B 轉紅 ──────────────────────
_MUTANTS = {
    "reverted": _REVERT,
    "zero_fill": ((_FIX, "            _exp_yoy8 = float(_ey8_v) if _ey8_v is not None else 0.0\n"),),
    "raw_get": ((_FIX, "            _exp_yoy8 = _m8_exp.get('yoy') if _m8_exp else None\n"),),
}


@pytest.mark.parametrize("mut", sorted(_MUTANTS))
def test_mutants_are_caught(mut, monkeypatch):
    m = _load("mid", _apply(_source("mid"), _MUTANTS[mut]), f"p3_f8_mut_{mut}")
    caught = 0
    for exp in _MISSING.values():
        now = _run(m, _info(exp, {}), 5.0, monkeypatch)
        base = _run(_mod("mid"), _info(None, {}), 5.0, monkeypatch)
        if now["exc"] is not None or _card(now) != _card(base):
            caught += 1
    assert caught > 0
