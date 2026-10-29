"""DEC-102(3)（QA M1，2026-10-28）：⑦／LINE AI 總結 prompt —— 持股資料不足時 VIX 不得據以給行動建議。

觸發條件與 `_INSUFFICIENT_INSTRUCTION` 同一謂詞（L0 `holdings_data_short.digest_data_short`）。
資料齊全時 prompt 與修前（`1e603094`，經 `tests/test_dec102_revert_chain.base_module` 還原）逐字相同。
"""
from __future__ import annotations

import pandas as pd
import pytest

import src.services.dividend_station_service as S
from shared import holdings_data_short as HDS
from tests.test_dec102_revert_chain import base_module

VIX_LINE = "VIX 只可陳述分級事實，不得據以給任何行動建議（如照原計畫、定期定額）。"

_WK = pd.Series([20.0 + i * 0.1 for i in range(160)],
                index=pd.date_range("2023-01-06", periods=160, freq="W-FRI"))


def _mf(tk, kind, *, price=500.0):
    if kind == "etf":
        return {"weekly_close": _WK, "premium_pct": 0.3, "sharpe": 0.8, "total_return_1y_pct": 10.0,
                "annual_yield_pct": 5.0, "inception_years": 5.0, "ann_return_3y_pct": 8.0,
                "cum_return_3y_pct": 25.0, "peer_ranks": {3: .2, 6: .2, 12: .2},
                "current_price": 180.0}
    return {"mj_grade": "A", "kd_state": None, "current_price": price}


_HOLD = [{"ticker": "0050", "lots": 2, "avg_price": 150}, {"ticker": "2330", "lots": 1, "avg_price": 400}]


@pytest.fixture(scope="module")
def BS():
    return base_module("src/services/dividend_station_service.py", "_dec102_base_svc_prompt")


def _prompt(mod, mf, vix):
    rows = mod.build_station_rows(_HOLD, vix=vix, metrics_fn=mf)
    d = mod.build_station_digest(rows, vix)
    return d, mod.build_summary_prompt(d, switch={"switch_out": [], "switch_in": []})


@pytest.mark.parametrize("vix", [None, 15.0, 35.0])
def test_complete_data_prompt_identical_to_base(BS, vix):
    d, p = _prompt(S, _mf, vix)
    _bd, bp = _prompt(BS, _mf, vix)
    assert not HDS.digest_data_short(d)
    assert p == bp
    assert VIX_LINE not in p


@pytest.mark.parametrize("vix", [None, 15.0, 35.0])
def test_short_data_prompt_forbids_vix_action(vix):
    d, p = _prompt(S, lambda tk, kind: _mf(tk, kind, price=None) if tk == "2330" else _mf(tk, kind), vix)
    assert HDS.digest_data_short(d)
    assert S._INSUFFICIENT_INSTRUCTION in p
    assert VIX_LINE in p
    assert "續抱、定期定額即可" not in p


def test_line_is_inside_the_insufficient_instruction():
    """同一謂詞：這一句只跟著 `_INSUFFICIENT_INSTRUCTION` 走（⛔ 不另造觸發條件）。"""
    assert S._INSUFFICIENT_INSTRUCTION.endswith("\n" + VIX_LINE)
