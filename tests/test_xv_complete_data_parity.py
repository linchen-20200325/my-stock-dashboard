"""複驗 C：資料完整情境下，戰情表列、⑦ AI prompt、LINE 正文、① 巡航句與 `f3d77703`（本批開工前）**逐字相同**。

「修前」＝現行原始碼套上 `tests/test_xvext_revert_chain.xvext_revert_for`（基底 sha 由該檔守住）；
測試本身不呼叫 git（`tests/test_zz_test_portability.py`）。無網路（metrics stub）。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from tests.test_xvext_revert_chain import XVEXT_BASE_SHA, xvext_revert_for

REPO = Path(__file__).resolve().parents[1]


def _base_module(rel: str, name: str) -> types.ModuleType:
    assert rel in XVEXT_BASE_SHA
    code = xvext_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
    m = types.ModuleType(name)
    m.__file__ = str(REPO / rel)
    sys.modules[name] = m
    exec(compile(code, str(REPO / rel), "exec"), m.__dict__)
    return m


_WK = pd.Series([20.0 + i * 0.1 for i in range(160)],
                index=pd.date_range("2023-01-06", periods=160, freq="W-FRI"))


def _mf(tk, kind):
    if kind == "etf":
        return {"weekly_close": _WK, "premium_pct": 0.3, "sharpe": 0.8, "total_return_1y_pct": 10.0,
                "annual_yield_pct": 5.0, "inception_years": 5.0, "ann_return_3y_pct": 8.0,
                "cum_return_3y_pct": 25.0, "peer_ranks": {3: .2, 6: .2, 12: .2},
                "current_price": 180.0}
    return {"mj_grade": "A", "kd_state": None, "current_price": 500.0}


_HOLD = [{"ticker": "0050", "lots": 2, "avg_price": 150}, {"ticker": "2330", "lots": 1, "avg_price": 400},
         {"ticker": "00878", "held": False}]


@pytest.mark.parametrize("vix", [None, 15.0, 35.0])
def test_complete_data_prompt_and_line_byte_identical_to_base(vix):
    import src.compute.notify.holdings_digest_message as M
    import src.services.dividend_station_service as S
    BS = _base_module("src/services/dividend_station_service.py", "_xv_base_svc")
    BM = _base_module("src/compute/notify/holdings_digest_message.py", "_xv_base_msg")
    rows, brows = (S.build_station_rows(_HOLD, vix=vix, metrics_fn=_mf),
                   BS.build_station_rows(_HOLD, vix=vix, metrics_fn=_mf))
    assert [r["建議動作"] for r in rows] == [r["建議動作"] for r in brows]
    d, bd = S.build_station_digest(rows, vix), BS.build_station_digest(brows, vix)
    assert d == bd                                  # 資料完整：digest 逐鍵相同（無新鍵）
    sw = {"switch_out": [], "switch_in": []}
    assert S.build_summary_prompt(d, switch=sw) == BS.build_summary_prompt(bd, switch=sw)
    assert "續抱、定期定額即可" in S.build_summary_prompt(d)
    assert (M.format_holdings_message(d, sw, as_of="t")
            == BM.format_holdings_message(bd, sw, as_of="t"))


def test_complete_data_action_card_still_cruise(monkeypatch):
    import src.services.dividend_station_service as S
    import src.ui.views.page_hold as P
    from src.ui.render.station_cards import CRUISE_TEXT
    rows = S.build_station_rows(_HOLD[:1], vix=15.0, metrics_fn=_mf)
    monkeypatch.setattr("src.services.dividend_station_service.get_station_rows",
                        lambda hs: (rows, 15.0))
    st = P.load_station(P.HoldingsReadout(requested=True, submitted=True, bound=True,
                                          holdings=({"ticker": "0050", "held": True},)))
    assert st.cruise_text == P._clean_signal(CRUISE_TEXT) and st.unjudged_rows == 0


def test_complete_data_weekly_prompt_and_message_identical_to_base():
    import src.compute.notify.weekly_review_prompt as WP
    BW = _base_module("src/compute/notify/weekly_review_prompt.py", "_xv_base_wprompt")
    rows = [{"代號": "0050.TW", "燈號": "🟢 體質正常", "連敗季數": 0, "相對基準%": 1.0},
            {"代號": "2330.TW", "燈號": "🔴 雙向弱勢", "連敗季數": 1, "相對基準%": -3.0}]
    assert (WP.build_weekly_review_prompt(["加權指數 收 1"], rows, as_of="t")
            == BW.build_weekly_review_prompt(["加權指數 收 1"], rows, as_of="t"))
    import src.services.weekly_review_service as WS
    BWS = _base_module("src/services/weekly_review_service.py", "_xv_base_wsvc")
    for rs in (rows, rows[:1]):
        rv = {"macro_lines": ["x"], "rows": rs, "ai_text": None}
        assert WS.format_weekly_message(rv, as_of="t") == BWS.format_weekly_message(rv, as_of="t")
