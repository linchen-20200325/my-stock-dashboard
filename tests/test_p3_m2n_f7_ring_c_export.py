"""批 P3 · M2N-f7：§八 ⚔️ 三環 C 徽章（台灣出口）缺值不再捏 0、不再崩潰、不再印 nan。

修前：`_exp_c = float(_m8_exp.get('yoy', 0)) if _m8_exp else None`
  · dict 在、缺 'yoy' 鍵 → 假的「C 出口=+0.0%」；
  · None → TypeError；'-' → ValueError（拋出 render_section_mid）；
  · NaN →「C 出口=+nan%」；±inf →「+inf%」／「-inf%」。
修後：沿用 KPI 卡已算好的有限值 `_ey8_v`（`_finite_yoy`）→ 上列一律走既有徽章「C 出口未知」。
有限值時輸出與修前逐字相同（D 類，基準為反向替換出的修前體）。

產線型別（查證 `src/data/macro/macro_snapshot.py` 六條 `tw_export` 出口）：
stat.gov.tw `float(...)`、FRED-API／FRED `round(float 運算, 2)`、MOF CSV `_parse_customs_export_csv`
→ `round(...)`，皆 Python float；`macro_info` 只存在 session_state（不經 JSON 序列化）
⇒ 產線不會出現數字字串，`_finite_yoy` 把字串當缺不會讓真實資料退化。

harness 沿用 `tests/test_p2_m2n_f4_veto_finite.py` 的 `_run`（全部離線）。
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from tests.test_m2n2_no_zero_fill import _apply, _load, _mod, _source
from tests.test_p2_m2n_f4_veto_finite import _run

#: 修後 → 修前（反向替換；恰好一處）。
_REVERT = (
    ("            _exp_c    = float(_ey8_v) if _ey8_v is not None else None\n",
     "            _exp_c    = float(_m8_exp.get('yoy', 0)) if _m8_exp else None\n"),
)

_UNKNOWN = "C 出口未知"


def _ring_c(r) -> list[str]:
    """所有輸出中含「C 出口」徽章的片段（未知或有值）。"""
    return [t for _k, t in r["out"] if isinstance(t, str) and "C 出口" in t]


@pytest.fixture(scope="module")
def pre_fix():
    return _load("mid", _apply(_source("mid"), _REVERT), "p3_f7_pre")


_MISSING = {
    "absent_key": {},
    "none": {"yoy": None},
    "dash": {"yoy": "-"},
    "nan": {"yoy": math.nan},
    "+inf": {"yoy": math.inf},
    "-inf": {"yoy": -math.inf},
    "np_nan": {"yoy": np.float64("nan")},
    "bool": {"yoy": True},
}


# ── B：修後缺值契約 ───────────────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(_MISSING))
def test_missing_shows_existing_unknown_badge(name, monkeypatch):
    r = _run(_mod("mid"), {"tw_export": dict(_MISSING[name], date="2026-08")}, monkeypatch)
    assert r["exc"] is None, r["exc"]
    hits = _ring_c(r)
    assert hits and all(_UNKNOWN in t for t in hits), hits
    assert not any("C 出口=" in t for t in hits)


# ── C：修前確實出事（前提守衛）───────────────────────────────────────────
def test_pre_fix_symptoms(pre_fix, monkeypatch):
    def run(v):
        return _run(pre_fix, {"tw_export": v}, monkeypatch)
    assert any("C 出口=+0.0%" in t for t in _ring_c(run({"date": "2026-08"})))
    assert run({"yoy": None})["exc"][0] == "TypeError"
    assert run({"yoy": "-"})["exc"][0] == "ValueError"
    assert any("+nan%" in t for t in _ring_c(run({"yoy": math.nan})))


# ── D：有限值 → 與修前逐字相同 ────────────────────────────────────────────
_FINITE = [-12.34, -0.05, -0.0, 0, 0.0, 3.2, 9.95, 9.99, 10, 10.0, 12.3, 55.55,
           np.float64(10.0), np.float64(-7.25)]


@pytest.mark.parametrize("v", _FINITE, ids=[repr(v) for v in _FINITE])
def test_finite_output_identical_to_pre_fix(v, pre_fix, monkeypatch):
    info = {"tw_export": {"yoy": v, "date": "2026-08"}}
    now = _run(_mod("mid"), info, monkeypatch)
    pre = _run(pre_fix, info, monkeypatch)
    assert now["exc"] is None and pre["exc"] is None
    assert now["out"] == pre["out"]
    assert any(f"C 出口={float(v):+.1f}%" in t for t in _ring_c(now))


def test_no_export_dict_unchanged(pre_fix, monkeypatch):
    now = _run(_mod("mid"), {}, monkeypatch)
    pre = _run(pre_fix, {}, monkeypatch)
    assert now["exc"] is None and now["out"] == pre["out"]
    assert any(_UNKNOWN in t for t in _ring_c(now))


# ── G：突變 —— 修前體／常見錯誤修法都必須讓 B 轉紅 ───────────────────────
_MUTANTS = {
    "reverted": _REVERT,
    "zero_fill": ((_REVERT[0][0],
                   "            _exp_c    = float(_ey8_v) if _ey8_v is not None else 0.0\n"),),
    "raw_get": ((_REVERT[0][0],
                 "            _exp_c    = _m8_exp.get('yoy') if _m8_exp else None\n"),),
}


@pytest.mark.parametrize("mut", sorted(_MUTANTS))
def test_mutants_are_caught(mut, monkeypatch):
    m = _load("mid", _apply(_source("mid"), _MUTANTS[mut]), f"p3_f7_mut_{mut}")
    caught = 0
    for v in _MISSING.values():
        r = _run(m, {"tw_export": dict(v)}, monkeypatch)
        hits = _ring_c(r)
        if r["exc"] is not None or not hits or not all(_UNKNOWN in t for t in hits):
            caught += 1
    assert caught > 0
