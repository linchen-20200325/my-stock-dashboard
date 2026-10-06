"""批 Z9（客戶 2026-10-06 裁，三句逐字採用）：V2-n5 拒存訊息、X2-n1「N 項未評估」、Y1-n1 Yahoo 失敗訊息。"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.services.macro_state_locker import calculate_system_state as css

_FULL = {"VIX_Index": 18.0, "ISM_PMI_or_OECD_CLI": 51.0, "PMI_Prev_Month": 51.0,
         "M1B_YoY_pct": 3.0, "M2_YoY_pct": 3.0, "BIAS240_pct": 0.0, "PCR": 1.0,
         "Futures_Net_Short": 0.0}
_TAG = "項未評估（缺資料不計分）"


class TestX2n1MacroPhase:
    def test_n0_no_label_is_normal(self):
        got = css(dict(_FULL))
        assert got["Macro_Phase"] == "環境正常"
        assert "0 項未評估" not in got["Macro_Phase"] and "missing_inputs" not in got

    @pytest.mark.parametrize("gone,n", [(("PCR",), 1), (("PCR", "BIAS240_pct", "Futures_Net_Short"), 3)])
    def test_n_positive_no_other_label(self, gone, n):
        d = {k: v for k, v in _FULL.items() if k not in gone}
        assert css(d)["Macro_Phase"] == f"{n} {_TAG}"

    def test_with_other_labels_joined_after(self):
        d = {k: v for k, v in _FULL.items() if k != "PCR"}
        d["VIX_Index"] = 30.0
        assert css(d)["Macro_Phase"] == f"VIX高波動(30.0)、1 {_TAG}"

    def test_all_missing_is_eight(self):
        assert css({})["Macro_Phase"] == f"8 {_TAG}"

    def test_n0_with_label_has_no_tag(self):
        d = dict(_FULL, VIX_Index=30.0)
        assert css(d)["Macro_Phase"] == "VIX高波動(30.0)"


class TestY1n1Message:
    def test_empty_with_http_failure_new_message(self):
        import yfinance.exceptions as YFE
        from src.data.proxy import yf_proxy as YP

        class _T:
            def history(self, *a, **kw):
                return pd.DataFrame()
        with patch.object(YP, "_chart_reply_failure", return_value="HTTP 503"):
            with pytest.raises(YFE.YFPricesMissingError) as ei:
                YP._history_or_raise(_T(), "2330.TW", "1y")
        assert str(ei.value) == "2330.TW: Yahoo 回應 HTTP 503 → 抓取失敗"
        assert "possibly delisted" not in str(ei.value)
        assert ei.value.ticker == "2330.TW"


class TestV2n5RejectMessage:
    @pytest.mark.parametrize("lots,avg", [(float("nan"), 50), (2, float("inf")), (10 ** 400, 50)])
    def test_reject_wording_and_no_write(self, lots, avg):
        from src.data.portfolio import gsheet_portfolio as gsp
        ws = type("WS", (), {})()
        ws.calls = []
        ws.get_all_values = lambda: [list(gsp._HEADERS)]
        ws.update = lambda *a, **k: ws.calls.append(("update", a, k))
        ws.add_rows = lambda *a, **k: ws.calls.append(("add_rows", a))
        ws.add_cols = lambda *a, **k: ws.calls.append(("add_cols", a))
        with patch.object(gsp, "_ws", return_value=ws):
            with pytest.raises(ValueError) as ei:
                gsp.save_portfolio("A", [{"ticker": "2330", "lots": lots, "avg_price": avg}])
        assert str(ei.value) == "有張數或均價空白／無效的列，Sheet 維持原狀（檢查張數、均價）"
        assert ws.calls == []

    def test_no_valid_rows_wording_unchanged(self):
        from src.data.portfolio import gsheet_portfolio as gsp
        ws = type("WS", (), {})()
        ws.get_all_values = lambda: [list(gsp._HEADERS)]
        with patch.object(gsp, "_ws", return_value=ws):
            with pytest.raises(ValueError, match="^無有效持股可儲存（檢查代號、張數、均價）$"):
                gsp.save_portfolio("A", [{"ticker": "2330", "lots": 0, "avg_price": 50}])
