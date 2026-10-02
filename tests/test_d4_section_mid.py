"""批 D4（客戶 2026-10-02）：§八 兩處字句列的程式面。

- M2N-f6（C2＝A）：總經基本面否決檢查有輸入缺值時，✅ 行講出缺項，⛔ 不再宣稱
  「景氣／通膨／外需面無系統性風險訊號」；五項都有值時原句不動。
- M2N-f1 餘 (a)(b)(c)：bias_240 缺鍵／CLI 缺值／外資期貨 NaN 不再被捏成 0／100／nan，
  改走既有或擬稿字句。

harness 沿用 `tests/test_m2n2_no_zero_fill.py` 的假 st（全部離線）。
"""
from __future__ import annotations

import math
import types

import pandas as pd
import pytest

from tests.test_m2n2_no_zero_fill import _FakeST, _mod

_OLD_OK = "✅ 總經基本面否決檢查：無觸發 — 景氣／通膨／外需面無系統性風險訊號"
_ALL5 = {"vix": {"current": 18.0}, "ism_pmi": {"value": 52.0},
         "us_core_cpi": {"yoy": 3.0}, "tw_export": {"yoy": 5.0, "date": "2026-08"},
         "ndc_signal": {"score": 27}}


def _run(macro_info: dict, mp, **ss) -> list[str]:
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    mod = _mod("mid")
    fake = _FakeST({"macro_info": macro_info, **ss})
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: None)
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None))
    mp.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
    mod.render_section_mid(False, {}, {}, {})
    return [t for _k, t in fake.out]


def test_m2n_f6_all_five_present_keeps_original_line(monkeypatch):
    out = _run(dict(_ALL5), monkeypatch, bias_info={"bias_240": 5.0})
    assert _OLD_OK in out


@pytest.mark.parametrize("drop,name", [("tw_export", "台灣出口 YoY"), ("ndc_signal", "NDC 燈號"),
                                       ("us_core_cpi", "美國核心 CPI")])
def test_m2n_f6_missing_input_is_named(drop, name, monkeypatch):
    info = {k: v for k, v in _ALL5.items() if k != drop}
    out = _run(info, monkeypatch, bias_info={"bias_240": 5.0})
    want = f"✅ 總經基本面否決檢查：無觸發（⚠️ {name}待取得，未納入任何判斷）"
    assert want in out, out
    assert _OLD_OK not in out


def test_m2n_f6_two_missing_joined(monkeypatch):
    info = {k: v for k, v in _ALL5.items() if k not in ("tw_export", "ndc_signal")}
    out = _run(info, monkeypatch, bias_info={"bias_240": 5.0})
    assert "✅ 總經基本面否決檢查：無觸發（⚠️ 台灣出口 YoY／NDC 燈號待取得，未納入任何判斷）" in out


@pytest.mark.parametrize("bias_info", [{"other": 1}, {"bias_240": None}, {"bias_240": math.nan}])
def test_m2n_f1a_missing_bias_shows_loading_hint(bias_info, monkeypatch):
    out = _run(dict(_ALL5), monkeypatch, bias_info=bias_info)
    assert "年線乖離數據載入後自動顯示 BIAS240 × 台灣出口判斷" in out
    assert not any("年線乖離 0.0%" in t or "年線乖離 +0.0%" in t or "nan%" in t for t in out)


def test_m2n_f1a_finite_bias_still_draws_matrix(monkeypatch):
    out = _run(dict(_ALL5), monkeypatch, bias_info={"bias_240": 5.0})
    assert any("年線乖離 +5.0%" in t or "年線乖離 5.0%" in t for t in out), out
    assert "年線乖離數據載入後自動顯示 BIAS240 × 台灣出口判斷" not in out


def test_m2n_f1b_missing_cli_value_is_unknown(monkeypatch):
    info = {k: v for k, v in _ALL5.items() if k != "tw_export"}
    info["ism_pmi"] = {"is_oecd_cli": True}
    out = _run(info, monkeypatch, bias_info={"bias_240": 5.0})
    assert any("CLI未知" in t for t in out), out
    assert not any("CLI=100.0" in t for t in out)


def test_m2n_f1c_nan_futures_is_unknown(monkeypatch):
    li = pd.DataFrame({"外資大小": [math.nan]})
    out = _run(dict(_ALL5), monkeypatch, bias_info={"bias_240": 5.0}, li_latest=li)
    joined = "\n".join(out)
    assert "B 期貨未知" in joined or "B 外資期貨未知" in joined, joined[-2000:]
    assert "nan口" not in joined
