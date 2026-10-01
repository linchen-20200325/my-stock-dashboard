"""批 P2 · M2N-f5：§八 三環 D 徽章 M1B-M2 差額四捨五入成 −0.0 時，不得印「-0.00%」。

修前：`_gap8c = round(m1b - m2, 2)`，例 3.001−3.004 → −0.0；徽章 `f'{_gap8c:+.2f}%'`
印成「D M1B-M2=-0.00%」。修後：`+ 0.0` 正規化 −0.0 → +0.0（同 #764 M2N-f2 的 `_gap8`）。
`_cD`（≥ 1.0）判定、徽章顏色與文案一字未動（非新字）。

harness 沿用 `tests/test_m2n2_no_zero_fill.py` 的 `_run_mid`（假 st、全部離線）。
"""
from __future__ import annotations

import pytest

from tests.test_m2n2_no_zero_fill import _D_SPAN, _apply, _load, _mod, _run_mid, _source, _text

_NEG_ZERO = [(3.001, 3.004), (2.0, 2.004), (-1.0, -0.996), (0.0, 0.001)]


def _d_badges(mod, m1b, m2, mp) -> list:
    text = _text(_run_mid(mod, {"m1b_yoy": m1b, "m2_yoy": m2, "source": "CBC-tier1"}, mp))
    return [m.group(1) for m in _D_SPAN.finditer(text)]


@pytest.mark.parametrize("m1b,m2", _NEG_ZERO)
def test_rounded_negative_zero_d_badge_prints_plus_zero(m1b, m2, monkeypatch):
    assert str(round(m1b - m2, 2)) == "-0.0"   # 前提：真的是負零
    assert _d_badges(_mod("mid"), m1b, m2, monkeypatch) == ["D M1B-M2=+0.00%"]


@pytest.mark.parametrize("m1b,m2,want", [
    (3.004, 3.001, "D M1B-M2=+0.00%"),   # 正零照舊
    (2.0, 2.0, "D M1B-M2=+0.00%"),
    (2.04, 2.0, "D M1B-M2=+0.04%"),
    (1.0, 2.04, "D M1B-M2=-1.04%"),
    (5.1, 2.0, "D M1B-M2=+3.10%"),
    (3.0, 2.0, "D M1B-M2=+1.00%"),
])
def test_other_gaps_unchanged(m1b, m2, want, monkeypatch):
    assert _d_badges(_mod("mid"), m1b, m2, monkeypatch) == [want]


def test_mutant_without_normalisation_is_caught(monkeypatch):
    """突變：拿掉 `+ 0.0` → 負零徽章退回「-0.00%」，上面的測試必須抓得到。"""
    line = "_gap8c = round(float(_m1b8_v) - float(_m2b8_v), 2) + 0.0\n"
    mut = _load("mid", _apply(_source("mid"),
                              ((line, line.replace(" + 0.0", "")),)), "p2_f5_mut")
    assert _d_badges(mut, 3.001, 3.004, monkeypatch) == ["D M1B-M2=-0.00%"]
