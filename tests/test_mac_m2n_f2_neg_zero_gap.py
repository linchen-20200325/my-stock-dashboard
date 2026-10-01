"""批 MAC · M2N-f2：§八 策略3 M1B-M2 差額四捨五入成 −0.0 時，畫面不得印「+-0.00%」。

修前：`_gap8 = round(m1b - m2, 2)`，例 3.001−3.004 → −0.0；`−0.0 >= 0` 成立 → 走
「資金溫和·中性擴張」那枝，字串 `f'+{_gap8:.2f}%'` 印成「Gap = +-0.00%」。
修後：`+ 0.0` 正規化 −0.0 → +0.0，印「Gap = +0.00%」。分支、文案一字未動（非新字）。

harness 沿用 `tests/test_m2n2_no_zero_fill.py` 的 `_run_mid`（假 st、全部離線）。
"""
from __future__ import annotations

import pytest

from tests.test_m2n2_no_zero_fill import _mod, _run_mid, _text

_NEUTRAL = "（資金溫和·中性擴張）"


@pytest.mark.parametrize("m1b,m2", [(3.001, 3.004), (2.0, 2.004), (-1.0, -0.996), (0.0, 0.001)])
def test_rounded_negative_zero_gap_prints_plus_zero(m1b, m2, monkeypatch):
    assert round(m1b - m2, 2) == 0.0 and str(round(m1b - m2, 2)) == "-0.0"   # 前提：真的是負零
    text = _text(_run_mid(_mod("mid"), {"m1b_yoy": m1b, "m2_yoy": m2, "source": "CBC-tier1"},
                          monkeypatch))
    assert "+-" not in text
    assert f"M1B-M2 Gap = +0.00%{_NEUTRAL}" in text      # 分支照舊（−0.0 本來就落這枝）


@pytest.mark.parametrize("m1b,m2,want", [
    (3.004, 3.001, f"M1B-M2 Gap = +0.00%{_NEUTRAL}"),    # 正零照舊
    (2.0, 2.0, f"M1B-M2 Gap = +0.00%{_NEUTRAL}"),
    (2.04, 2.0, f"M1B-M2 Gap = +0.04%{_NEUTRAL}"),
    (1.0, 2.04, "M1B-M2 Gap = -1.04%（死亡交叉·資金退潮）"),
    (5.1, 2.0, "M1B-M2 Gap = +3.10%（黃金交叉·熱錢狂潮）"),
])
def test_other_gaps_unchanged(m1b, m2, want, monkeypatch):
    text = _text(_run_mid(_mod("mid"), {"m1b_yoy": m1b, "m2_yoy": m2, "source": "CBC-tier1"},
                          monkeypatch))
    assert want in text and "+-" not in text
