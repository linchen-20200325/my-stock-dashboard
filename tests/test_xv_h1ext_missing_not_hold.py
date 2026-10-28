"""XV-H1-EXT（客戶 2026-10-28 裁示 A）：missing ≠ HOLD；unavailable ≠ safe。

- 列：燈全判不出（ETF 健檢四燈 ⚪＋235 巡航；個股汰換燈 ⚪）、持有列缺現價 → 標 `SS.KEY_INSUFFICIENT`；
  原本是持有結論（ETF「⚪ 巡航：維持定期定額」、個股 🟢「續抱」）者改為 `⬜ 資料不足／無法判定`；
  可證明結論（🔴 汰弱、加碼…）與資料完整列一字不動。
- ⑦／LINE AI prompt：只在 total 有限且 ≥1、無抓取失敗、無燈全判不出、無缺現價時放續抱句；否則放資料不足指示。
- LINE 規則式正文：缺資料不印「續抱」；total 為 NaN／±inf 不再拋例外（走「未能判斷」）。
無網路：metrics_fn 為 stub。
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from shared import station_specs as SS
from src.compute.notify import holdings_digest_message as M
from src.services import dividend_station_service as S

_HOLD = "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。"
_WK2 = pd.Series([20.0, 21.0], index=pd.date_range("2026-01-02", periods=2, freq="W-FRI"))


def _rows(etf_metrics=None, stock_metrics=None, vix=None):
    def mf(tk, kind):
        if kind == "etf":
            return etf_metrics or {"weekly_close": _WK2, "current_price": 21.0}
        return stock_metrics or {"mj_grade": "A", "kd_state": None, "current_price": 500.0}
    return S.build_station_rows([{"ticker": "0056", "name": "e", "lots": 1, "avg_price": 20},
                                 {"ticker": "2330", "name": "s", "lots": 1, "avg_price": 400}],
                                vix=vix, metrics_fn=mf)


# ── 列 ─────────────────────────────────────────────────────────────
def test_etf_all_lights_unjudged_shows_insufficient():
    etf = _rows()[0]
    assert etf["健檢"] == "⚪" and etf["_action"] == "cruise"
    assert etf["建議動作"] == SS.INSUFFICIENT_ACTION_TEXT == "⬜ 資料不足／無法判定"
    assert etf[SS.KEY_INSUFFICIENT] == (SS.INSUFF_ALL_UNJUDGED,)


def test_stock_hold_without_price_shows_insufficient():
    st = _rows(stock_metrics={"mj_grade": "A", "kd_state": None, "current_price": None})[1]
    assert st["健檢"] == "🟢" and st["現價"] is None
    assert st["建議動作"] == SS.INSUFFICIENT_ACTION_TEXT
    assert st[SS.KEY_INSUFFICIENT] == (SS.INSUFF_NO_PRICE,)


def test_stock_with_price_keeps_hold_text():
    st = _rows()[1]
    assert st["建議動作"].startswith("🟢 續抱") and SS.KEY_INSUFFICIENT not in st


def test_provable_red_kept_even_without_price():
    """QA 回修 #7：可證明結論（🔴）缺現價 → 不列入「無法判定」，只另標「缺現價（結論不受影響）」。"""
    st = _rows(stock_metrics={"mj_grade": "F", "kd_state": None, "current_price": None})[1]
    assert st["建議動作"].startswith("🔴") and SS.KEY_INSUFFICIENT not in st
    assert st[SS.KEY_PRICE_MISSING_KEPT] is True
    d = S.build_station_digest([st], vix=15.0)
    assert "insufficient" not in d and d["price_missing_kept"] == ["2330"]
    p = S.build_summary_prompt(d)
    assert "- 缺現價（結論不受影響）：2330\n" in p and "資料不足／無法判定（" not in p
    assert _HOLD not in p
    msg = M.format_holdings_message(d, None, as_of="t")
    assert "ℹ️ 缺現價（結論不受影響）：2330" in msg and "⬜ 資料不足／無法判定（" not in msg


def test_stock_unjudged_replaced_and_original_kept_in_detail():
    """QA 回修 #7：個股汰換燈 ⚪ ＝ 燈全判不出 → 建議動作換成 ⬜（原句留在 `_detail`）。"""
    st = _rows(stock_metrics={"mj_grade": None, "kd_state": None, "current_price": 500.0})[1]
    assert st["建議動作"] == SS.INSUFFICIENT_ACTION_TEXT
    assert st["_detail"]["原建議動作"].startswith("⚪ 財報資料不足")
    assert st[SS.KEY_INSUFFICIENT] == (SS.INSUFF_ALL_UNJUDGED,)


def test_insufficient_marks_only_replaced_rows():
    """QA 回修 #7：帶 `KEY_INSUFFICIENT` 的列，建議動作一定是 ⬜ 句（反之亦然）。"""
    for sm in ({"mj_grade": "A", "kd_state": None, "current_price": None},
               {"mj_grade": "F", "kd_state": None, "current_price": None},
               {"mj_grade": None, "kd_state": None, "current_price": None},
               {"mj_grade": "A", "kd_state": None, "current_price": 1.0}):
        for r in _rows(stock_metrics=sm):
            assert (SS.KEY_INSUFFICIENT in r) == (r["建議動作"] == SS.INSUFFICIENT_ACTION_TEXT), r


def test_watch_and_held_labelled_separately():
    """QA 回修 #11：持有／觀察清單分開標明（prompt 與 LINE）。"""
    rows = [{"代號": "0056", "_detail": {}, "held": True, SS.KEY_INSUFFICIENT: (SS.INSUFF_ALL_UNJUDGED,)},
            {"代號": "00878", "_detail": {}, "held": False, SS.KEY_INSUFFICIENT: (SS.INSUFF_ALL_UNJUDGED,)}]
    d = S.build_station_digest(rows, vix=15.0)
    assert [x["held"] for x in d["insufficient"]] == [True, False]
    p = S.build_summary_prompt(d)
    assert "- 資料不足／無法判定（持有）：0056（燈號全部判不出）\n" in p
    assert "- 資料不足／無法判定（觀察清單）：00878（燈號全部判不出）\n" in p
    msg = M.format_holdings_message(d, None, as_of="t")
    assert "⬜ 資料不足／無法判定（持有）：0056（燈號全部判不出）" in msg
    assert "⬜ 資料不足／無法判定（觀察清單）：00878（燈號全部判不出）" in msg


def test_watchlist_missing_price_not_flagged():
    rows = S.build_station_rows([{"ticker": "2330", "held": False}], vix=None,
                                metrics_fn=lambda tk, k: {"mj_grade": "A", "kd_state": None,
                                                          "current_price": None})
    assert SS.KEY_INSUFFICIENT not in rows[0] and rows[0]["建議動作"].startswith("🟢 續抱")


# ── digest / prompt（V 探針四案＋完整）──────────────────────────────
_CASES = {
    "A_all_fail": [{"代號": "0056", "_detail": {"error": "x"}, "held": True},
                   {"代號": "00878", "_detail": {"error": "y"}, "held": True}],
    "B_all_white": [{"代號": c, "_detail": {}, "held": True, "健檢": "⚪", "_action": "cruise",
                     SS.KEY_INSUFFICIENT: (SS.INSUFF_ALL_UNJUDGED,)} for c in ("0056", "00878")],
    "C_unpriced": [{"代號": "2330", "_detail": {}, "held": True, "健檢": "🟢", "現價": None,
                    SS.KEY_INSUFFICIENT: (SS.INSUFF_NO_PRICE,)}],
    "D_partial_fail": [{"代號": "0056", "_detail": {"error": "x"}, "held": True},
                       {"代號": "2330", "_detail": {}, "held": True, "健檢": "🟢"}],
}


@pytest.mark.parametrize("case", list(_CASES))
def test_prompt_short_data_no_hold(case):
    d = S.build_station_digest(_CASES[case], vix=15.0)
    p = S.build_summary_prompt(d)
    assert _HOLD not in p and S._INSUFFICIENT_INSTRUCTION in p
    assert "資料不足／無法判定" in p and "全部續抱" in p


def test_prompt_complete_data_keeps_hold():
    d = S.build_station_digest([{"代號": "2330", "_detail": {}, "held": True, "健檢": "🟢"}], vix=15.0)
    assert "insufficient" not in d
    p = S.build_summary_prompt(d)
    assert _HOLD in p and S._INSUFFICIENT_INSTRUCTION not in p


def test_digest_insufficient_lists_codes_and_reasons():
    d = S.build_station_digest(_CASES["B_all_white"] + _CASES["C_unpriced"])
    assert d["insufficient"] == [{"代號": "0056", "原因": (SS.INSUFF_ALL_UNJUDGED,), "held": True},
                                 {"代號": "00878", "原因": (SS.INSUFF_ALL_UNJUDGED,), "held": True},
                                 {"代號": "2330", "原因": (SS.INSUFF_NO_PRICE,), "held": True}]
    p = S.build_summary_prompt(d)
    assert "- 資料不足／無法判定（持有）：0056（燈號全部判不出）、00878（燈號全部判不出）、2330（缺現價）\n" in p


# ── LINE 規則式正文 ─────────────────────────────────────────────────
@pytest.mark.parametrize("case", ["B_all_white", "C_unpriced", "D_partial_fail"])
def test_line_short_data_no_hold(case):
    d = S.build_station_digest(_CASES[case], vix=15.0)
    msg = M.format_holdings_message(d, {"switch_out": [], "switch_in": []}, as_of="t")
    assert "續抱、定期定額即可" not in msg and "無紅燈,續抱" not in msg
    assert "資料不足或抓取失敗的標的未下結論" in msg


def test_line_lists_insufficient():
    d = S.build_station_digest(_CASES["C_unpriced"], vix=15.0)
    msg = M.format_holdings_message(d, None, as_of="t")
    assert "⬜ 資料不足／無法判定（持有）：2330（缺現價）" in msg


def test_line_complete_keeps_hold():
    d = S.build_station_digest([{"代號": "2330", "_detail": {}, "held": True, "健檢": "🟢"}], vix=15.0)
    msg = M.format_holdings_message(d, {"switch_out": [], "switch_in": []}, as_of="t")
    assert "📭 今日無需動作：續抱、定期定額即可。" in msg and "無紅燈,續抱" in msg


@pytest.mark.parametrize("total", [math.nan, math.inf, -math.inf])
def test_line_nonfinite_total_does_not_raise(total):
    msg = M.format_holdings_message({"total": total, "vix": 15.0}, None, as_of="t")
    assert "未能判斷" in msg and "續抱、定期定額即可" not in msg


def test_line_invalid_inputs_no_hold_and_listed():
    """QA 回修 #2：持有列輸入異常（均價 NaN）→ LINE 不印續抱，並列出異常（同 ⑦ prompt 格式）。"""
    rows = [{"代號": "2330", "_detail": {}, "held": True, "健檢": "🟢", "現價": 500.0,
             SS.KEY_INVALID_INPUTS: (SS.ITEM_AVG_PRICE,)}]
    d = S.build_station_digest(rows, vix=15.0)
    msg = M.format_holdings_message(d, {"switch_out": [], "switch_in": []}, as_of="t")
    assert "續抱、定期定額即可" not in msg and "無紅燈,續抱" not in msg
    assert "⚠️ 資料異常未判：2330（均價：均價資料異常，無法計算，不下結論。）" in msg
    p = S.build_summary_prompt(d)
    assert "- 資料異常未判：2330（均價：均價資料異常，無法計算，不下結論。）\n" in p
