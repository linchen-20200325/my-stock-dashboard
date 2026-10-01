"""批 P2 · M2N-f4：§八 基本面否決檢查遇 None／字串／非有限值時不得崩潰、不得假稱「✅ 無觸發」。

修前：
  · `_m8_vix.get('current', 0) >= 30` 等五條比較 —— 值為 None／字串 → TypeError，§八 整段炸掉；
  · `_fund_evaluable = any([dict...])` 看 dict 真值 —— dict 在、值為 None／NaN 也算「可評估」，
    印出假的「✅ 無觸發」。
修後：沿用 KPI 卡已算好的有限值（`_finite_yoy`）；非有限 → 該條件略過；可評估只算有限值。
全為有限值時輸出與修前逐字相同（下方 D 類，基準為反向替換出的修前體）。

harness 沿用 `tests/test_m2n2_no_zero_fill.py` 的假 st / `_load` / `_apply`（全部離線）。
"""
from __future__ import annotations

import itertools
import math
import types

import pytest

from tests.test_m2n2_no_zero_fill import _FakeST, _apply, _load, _mod, _source

#: 修後 → 修前（反向替換；恰好一處）。
_REVERT = (
    ("    if _vcur8_v is not None and _vcur8_v >= 30:\n",
     "    if _m8_vix and _m8_vix.get('current', 0) >= 30:\n"),
    ("    if _pv8_v is not None and _pv8_v < 48:\n",
     "    if _m8_pmi and _m8_pmi.get('value', 55) < 48:\n"),
    ("    if _cy8_v is not None and _cy8_v > 4.0:\n",
     "    if _m8_cpi and _m8_cpi.get('yoy', 0) > 4.0:\n"),
    ("    if _ey8_v is not None and _ey8_v < -5:\n",
     "    if _m8_exp and _m8_exp.get('yoy', 0) < -5:\n"),
    ("    _crisis_buy = _sc8_v is not None and _sc8_v <= 16\n",
     "    _crisis_buy = _m8_ndc and _m8_ndc.get('score', 25) <= 16\n"),
    ("    _fund_evaluable = any(_v is not None for _v in (_vcur8_v, _pv8_v, _cy8_v, _sc8_v))\n",
     "    _fund_evaluable = any([_m8_vix, _m8_pmi, _m8_cpi, _m8_ndc])\n"),
)

from src.config import VETO_FUNDAMENTAL_NAME

_OK = f"✅ {VETO_FUNDAMENTAL_NAME}："


def _run(mod, macro_info: dict, mp, v4_light=None) -> dict:
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    fake = _FakeST({"macro_info": macro_info})
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: None)
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None))
    mp.setattr(SC, "read_v4_macro_veto", lambda *a, **k: v4_light)
    exc = None
    try:
        mod.render_section_mid(False, {}, {}, {})
    except Exception as e:  # noqa: BLE001
        exc = (type(e).__name__, str(e))
    return {"exc": exc, "out": fake.out}


def _info(vix=None, pmi=None, cpi=None, exp=None, ndc=None) -> dict:
    d = {}
    if vix is not None:
        d["vix"] = {"current": vix}
    if pmi is not None:
        d["ism_pmi"] = {"value": pmi}
    if cpi is not None:
        d["us_core_cpi"] = {"yoy": cpi}
    if exp is not None:
        d["tw_export"] = {"yoy": exp}
    if ndc is not None:
        d["ndc_signal"] = {"score": ndc}
    return d


def _ok_line(r) -> bool:
    return any(k == "success" and t.startswith(_OK) for k, t in r["out"])


@pytest.fixture(scope="module")
def pre_fix():
    return _load("mid", _apply(_source("mid"), _REVERT), "p2_f4_pre")


# ── D：全為有限值 → 與修前逐字相同（含缺 dict、整數、門檻邊界） ────────────
_GRID = list(itertools.product(
    (None, 10, 30, 45.5),       # VIX（30 = 門檻邊界）
    (None, 47.9, 48, 55),       # PMI（48 = 邊界）
    (None, 3.0, 4.1),           # CPI
    (None, -6, 0),              # 出口
    (None, 16, 30),             # NDC（16 = 邊界）
))


@pytest.mark.parametrize("v4", [None, {"status": "🟢 安全", "_vix": 12.0, "_futures": 1000.0},
                                {"status": "🔴 否決", "_vix": 35.0, "_futures": -40000.0}],
                         ids=["v4_none", "v4_green", "v4_red"])
def test_all_finite_output_identical_to_pre_fix(v4, pre_fix, monkeypatch):
    for vix, pmi, cpi, exp, ndc in _GRID:
        info = _info(vix, pmi, cpi, exp, ndc)
        now = _run(_mod("mid"), info, monkeypatch, v4)
        pre = _run(pre_fix, info, monkeypatch, v4)
        assert now["exc"] is None and pre["exc"] is None
        assert now["out"] == pre["out"], info


# ── 修前會崩潰的輸入：None／字串 ─────────────────────────────────────────
@pytest.mark.parametrize("key,inner", [
    ("vix", "current"), ("ism_pmi", "value"), ("us_core_cpi", "yoy"),
    ("tw_export", "yoy"), ("ndc_signal", "score")])
@pytest.mark.parametrize("bad", [None, "n/a", "31"])
def test_none_or_string_no_longer_crashes(key, inner, bad, pre_fix, monkeypatch):
    info = {key: {inner: bad}}
    assert _run(pre_fix, info, monkeypatch)["exc"] is not None      # 前提：修前真的炸
    now = _run(_mod("mid"), info, monkeypatch)
    # 📌 批 P3 M2N-f7（有意識的更正，⛔ 不是漏刪）：原本此處對 tw_export 的 None／非數字字串
    # 另開一枝，釘「仍炸在下游 ⚔️ 三環 `_exp_c = float(_m8_exp.get('yoy', 0))`」（範圍外）。
    # 三環已改用同一組有限值 `_ey8_v` → 不再崩潰，該分枝移除，tw_export 與其他鍵同一契約。
    # 三環 C 徽章本身的缺值契約見 tests/test_p3_m2n_f7_ring_c_export.py。
    assert now["exc"] is None
    assert not _ok_line(now)        # 唯一來源不可評估 → 不下「無觸發」結論


# ── 修前假「✅ 無觸發」：dict 在、值非有限 ────────────────────────────────
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, None])
def test_non_finite_only_is_not_evaluable(bad, pre_fix, monkeypatch):
    info = {"vix": {"current": bad if bad is not None else math.nan},
            "ism_pmi": {"value": math.nan}, "us_core_cpi": {"yoy": math.nan},
            "ndc_signal": {"score": math.nan}}
    if bad is None:
        info["vix"] = {"current": None}
        info["ism_pmi"] = {}            # dict 在、缺鍵
    now = _run(_mod("mid"), info, monkeypatch)
    assert now["exc"] is None
    assert not _ok_line(now)
    assert not any(k == "expander" and "🚨" in t for k, t in now["out"])   # +inf 不再觸發


def test_pre_fix_nan_shows_false_ok(pre_fix, monkeypatch):
    """前提釘住：修前 dict 在、值 NaN → 印出假的「✅ 無觸發」。"""
    assert _ok_line(_run(pre_fix, {"vix": {"current": math.nan}}, monkeypatch))


def test_mixed_finite_and_non_finite_evaluates_finite_part(monkeypatch):
    """一個有限、其餘非有限：有限那條照常判定；非有限那條略過（不新增文案）。"""
    r = _run(_mod("mid"), {"vix": {"current": 45}, "ism_pmi": {"value": None},
                           "us_core_cpi": {"yoy": "x"}}, monkeypatch)
    assert r["exc"] is None
    assert any(k == "expander" and "🚨" in t for k, t in r["out"])
    r = _run(_mod("mid"), {"vix": {"current": 12}, "ism_pmi": {"value": None}}, monkeypatch)
    assert r["exc"] is None and _ok_line(r)


# ── 突變：每條守衛退回原式都必須被抓到 ───────────────────────────────────
@pytest.mark.parametrize("i", range(len(_REVERT)))
def test_each_reverted_guard_is_caught(i, monkeypatch):
    m = _load("mid", _apply(_source("mid"), _REVERT[i:i + 1]), f"p2_f4_mut{i}")
    keys = [("vix", "current"), ("ism_pmi", "value"), ("us_core_cpi", "yoy"),
            ("tw_export", "yoy"), ("ndc_signal", "score")]
    if i < 5:
        k, inner = keys[i]
        r = _run(m, {k: {inner: None}, "vix" if k != "vix" else "ism_pmi":
                     {"current" if k != "vix" else "value": 12 if k != "vix" else 55}},
                 monkeypatch)
        # 必須炸在否決檢查的比較本身（出口那條另有三環的範圍外崩潰，不可拿它充數）
        assert r["exc"] is not None and "not supported between" in r["exc"][1]
    else:
        assert _ok_line(_run(m, {"vix": {"current": math.nan}}, monkeypatch))
