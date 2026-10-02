"""批 V1 D4-n1（§1 Fail Loud）：§八 動態結論的 VIX 非有限值不得印假綠燈。

原 `_vix_now8 = float(_vix_raw8)` 讓 NaN／±inf 過關 →
「VIX nan < 20（平靜期）🟢 全球風險情緒穩定，未觸發 VIX 否決權」、徽章「A VIX=nan<20」，
且 `apply_vix_veto(nan)`。修正後非有限／None／缺鍵／非數值一律走既有缺值路徑：
「VIX 數據載入中，VIX 否決權暫無法判斷」＋「A VIX未知」，veto 收到 None。
有限值輸出逐字不變（下方 golden 釘住）。harness 沿用 `tests/test_d4_section_mid.py`。
"""
from __future__ import annotations

import math
import types

import pytest

from tests.test_m2n2_no_zero_fill import _FakeST, _mod

_BASE = {"ism_pmi": {"value": 52.0}, "us_core_cpi": {"yoy": 3.0},
         "tw_export": {"yoy": 5.0, "date": "2026-08"}, "ndc_signal": {"score": 27}}
_GREEN = "全球風險情緒穩定，未觸發 VIX 否決權"
_LOADING = "VIX 數據載入中，VIX 否決權暫無法判斷"


def _run(vix_node, mp, drop_key=False):
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    info = dict(_BASE)
    if not drop_key:
        info["vix"] = vix_node
    mod = _mod("mid")
    fake = _FakeST({"macro_info": info, "bias_info": {"bias_240": 5.0}})
    calls: list = []
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: calls.append(a))
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None))
    mp.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
    mod.render_section_mid(False, {}, {}, {})
    return [t for _k, t in fake.out], calls


_BAD = [
    pytest.param({"current": math.nan}, False, id="nan"),
    pytest.param({"current": math.inf}, False, id="+inf"),
    pytest.param({"current": -math.inf}, False, id="-inf"),
    pytest.param({"current": None}, False, id="none"),
    pytest.param({"dates": []}, False, id="missing-current"),
    pytest.param({"current": "18.5"}, False, id="numeric-string"),
    pytest.param(None, True, id="missing-vix-key"),
]


@pytest.mark.parametrize("node,drop", _BAD)
def test_nonfinite_vix_takes_missing_path(node, drop, monkeypatch):
    out, calls = _run(node, monkeypatch, drop_key=drop)
    joined = "\n".join(out)
    assert _GREEN not in joined, joined[-1500:]
    assert _LOADING in out
    assert "A VIX未知" in joined
    assert "VIX=nan" not in joined and "VIX nan" not in joined
    assert "VIX=inf" not in joined and "VIX inf" not in joined and "VIX -inf" not in joined
    assert "VIX 數值異常" not in joined      # inf 不得走「>100 API 錯置」分支
    # veto 只能收到 None（撤銷天花板），不得收到 NaN／inf
    assert calls == [(None,)], calls
    # 與上方缺項清單（M2N-f6）一致：VIX 列為待取得
    assert any("VIX待取得" in t or "VIX／" in t for t in out if "總經基本面否決檢查" in t), out


@pytest.mark.parametrize("vix,line,badge", [
    (18.0, "VIX 18.0 < 20（平靜期）", "A VIX=18.0<20"),
    (0, "VIX 0.0 < 20（平靜期）", "A VIX=0.0<20"),
    (25.0, "VIX 25.0（20~30 警戒）", "A VIX=25.0<20"),
    (35.0, "VIX 35.0 ≥ 30", "A VIX=35.0<20"),
])
def test_finite_vix_unchanged(vix, line, badge, monkeypatch):
    out, calls = _run({"current": vix}, monkeypatch)
    joined = "\n".join(out)
    assert line in joined
    assert badge in joined
    assert _LOADING not in out
    assert len(calls) == 1 and calls[0][0] == float(vix)
    assert type(calls[0][0]) is float


def test_vix_over_100_still_api_error(monkeypatch):
    out, calls = _run({"current": 150.0}, monkeypatch)
    assert any("VIX 數值異常（150）" in t for t in out)
    assert calls == []
