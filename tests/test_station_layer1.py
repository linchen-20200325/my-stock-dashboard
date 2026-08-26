"""tests/test_station_layer1.py — 戰情室第 1 層(結論卡)+ 兩套刻度表守衛（2026-08-26）

## 這批測試守什麼

1. **N/M 的定義**（防呆 1）—— 分子要「live **且** 有 level」兩個條件同時成立;
   分母只扣「結構上不適用」,**不扣**「今天沒抓到」。這兩件事各自都出過事:
   - 只看 `state == live` → 個股 KD 被算進去(它資料通、但從不判等級)→ **高估**;
   - 分母扣掉算不出來的燈 → 資料越爛分數越高,正好是這個指標要防的東西。
2. **巡航 gate 做在顯示層**(防呆 2)—— L2 `suggest_action` 一個字都不准動,
   因為它同時餵著主表「建議動作」欄與 `scripts/push_holdings_daily.py` 的
   **LINE 每日推播**。這裡釘住「兩句話刻意不同字」,避免有人日後「順手統一」
   而把推播文案一起改掉。
3. **金額的單位**（§4.1）—— 張 → 股要乘 `SHARES_PER_LOT`;漏乘 = 1000 倍低估。
4. **兩套刻度表**只揭露不改判定,且引用的門檻來自 L0 SSOT(§3.3)。

⚠️ 本檔只測純函式與文案,**不啟動 Streamlit runtime、不做網路 I/O**。
"""
from __future__ import annotations

import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from shared.sector_flow_thresholds import SHARES_PER_LOT
from src.compute.etf import dividend_station as ds
from src.services import dividend_station_service as SVC
from src.ui.render import station_cards as SC


# ── 假格子（不碰真 assessment，讓每個案例只表達一件事）────────────────────
class _Cell:
    def __init__(self, key="k", level="🟢", state=SS.STATE_LIVE, miss_reason=""):
        self.key, self.level, self.state, self.miss_reason = key, level, state, miss_reason
        self.axes_used = ()


def _cruise_assessment():
    """一檔「什麼事都沒有」的 ETF —— 平盤週線 + 缺可選指標 → `suggest_action` 落巡航。

    刻意把可選指標全給 None:本檔要釘的是**巡航那句話**,不是健檢細節;
    給 None 讓健檢四盞落 ⚪、235 落 cruise,路徑最短也最穩定。
    """
    return ds.assess_holding(
        ticker="X", name="X", asset_class=T.ASSET_CORE, asset_kind=T.KIND_ETF,
        weekly_close=pd.Series(
            [100.0] * 60,
            index=pd.date_range("2024-01-07", periods=60, freq="W-SUN")),
        vix=None, premium_pct=None, sharpe=None, total_return_1y_pct=None,
        annual_yield_pct=None, inception_years=None, ann_return_3y_pct=None,
        cum_return_3y_pct=None, peer_ranks=None)


class TestJudgedCountDefinition:
    """防呆 1：分子兩個條件、分母只扣不適用。"""

    def test_live_without_level_is_not_judged(self):
        """**本檔最重要的一條**：資料通不等於給得出判定。

        個股 KD 就是這種燈 —— `classify_state` 判 live(K、D 都在),但
        `assess_stock` 從來沒為它判過等級。只看 state 會把它算進分子。
        """
        _cells = (_Cell(level="🟢"), _Cell(level=ds.LEVEL_UNJUDGED))
        assert SC.judged_count(_cells) == (1, 2)
        # 舊的那把尺會算成 2/2 —— 兩者刻意不同,不是誰壞掉。
        assert SC.watch_count(_cells) == (2, 2)

    def test_missing_light_stays_in_denominator(self):
        """「今天沒抓到」必須留在分母裡把分數拉低（§1）。"""
        _cells = (_Cell(level="🟢"),
                  _Cell(level=ds.LEVEL_UNJUDGED, state=SS.STATE_MISSING,
                        miss_reason=SS.MISS_NO_INPUT))
        assert SC.judged_count(_cells) == (1, 2)

    def test_not_applicable_leaves_the_denominator(self):
        """只有「結構上不適用」才准離開分母（個股沒有折溢價這盞燈）。"""
        _cells = (_Cell(level="🟢"),
                  _Cell(level="⚪", state=SS.STATE_MISSING,
                        miss_reason=SS.MISS_NOT_APPLICABLE))
        assert SC.judged_count(_cells) == (1, 1)

    def test_degraded_is_not_judged(self):
        """degraded 的門檻已失準 → 不算「給得出判定」（分母仍在）。"""
        _cells = (_Cell(level="🟡", state=SS.STATE_DEGRADED),)
        assert SC.judged_count(_cells) == (0, 1)

    def test_empty_is_zero_zero_not_a_pass(self):
        assert SC.judged_count(()) == (0, 0)
        assert SC.judged_count(None) == (0, 0)
        # 空列**不是**「全部都好」——否則 all(...) 會在最糟時放行。
        assert SC.is_fully_judged(()) is False

    def test_denominator_is_dynamic_not_hardcoded(self):
        """ETF 8 盞、個股 4 盞 —— 呼叫端不得寫死總數。"""
        assert len(SS.specs_for(T.KIND_ETF)) == 8
        assert len(SS.specs_for(T.KIND_STOCK)) == 4
        _etf = SC.judged_count(ds.missing_light_cells(T.KIND_ETF,
                                                     reason=SS.MISS_FETCH_FAILED))
        _stk = SC.judged_count(ds.missing_light_cells(T.KIND_STOCK,
                                                      reason=SS.MISS_FETCH_FAILED))
        assert _etf == (0, 8) and _stk == (0, 4)


class TestAggregatesShareOneDenominator:
    """N/M 與四態分佈條**必須同一個分母** —— 否則同一張卡自己打自己。"""

    def test_tally_total_equals_judged_denominator(self):
        _rows = [(_Cell(level="🟢"),
                  _Cell(level="⚪", state=SS.STATE_MISSING,
                        miss_reason=SS.MISS_NOT_APPLICABLE),
                  _Cell(level=ds.LEVEL_UNJUDGED, state=SS.STATE_MISSING,
                        miss_reason=SS.MISS_NO_INPUT))]
        _n, _m = SC.aggregate_judged(_rows)
        assert (_n, _m) == (1, 2)
        assert sum(SC.tally_states(_rows).values()) == _m

    def test_tally_always_has_all_four_keys(self):
        _t = SC.tally_states([(_Cell(),)])
        assert set(_t) == {SS.STATE_LIVE, SS.STATE_DEGRADED,
                           SS.STATE_MISSING, SS.STATE_UNWIRED}


class TestCruiseGate:
    """防呆 2：巡航只在全部給得出判定時才准印,而且做在顯示層。"""

    def test_cruise_only_when_everything_is_judged(self):
        assert SC.cruise_or_gap(8, 8, all_rows_judged=True) == SC.CRUISE_TEXT

    @pytest.mark.parametrize("judged,total,all_judged", [
        (7, 8, True),      # 分子分母對不上 → 不准印
        (8, 8, False),     # 有某一列不完整 → 不准印
        (0, 0, True),      # 一盞燈都沒有 → 不是「沒事」,是「沒東西」
    ])
    def test_gap_message_when_not_fully_judged(self, judged, total, all_judged):
        _txt = SC.cruise_or_gap(judged, total, all_rows_judged=all_judged)
        assert _txt != SC.CRUISE_TEXT
        assert "沒東西可以判" in _txt
        assert f"{judged}/{total}" in _txt

    def test_layer1_cruise_text_is_not_the_l2_push_string(self):
        """L4 這句與 L2 `suggest_action` 的巡航**刻意不同字**。

        L2 那一句同時進主表「建議動作」欄與 LINE 每日推播;兩邊共用同一個字串,
        日後任何人「順手統一文案」就會**改到推播內容**。這條測試把兩者釘開。
        """
        _l2 = ds.suggest_action(_cruise_assessment())
        assert _l2 == "⚪ 巡航：維持定期定額"        # L2 現況（若這行紅了 = 推播文案被改）
        assert SC.CRUISE_TEXT != _l2


class TestPortfolioTotals:
    """§4.1：張 → 股必須乘 SHARES_PER_LOT;§1：算不出來回 None,不填 0。"""

    @staticmethod
    def _row(tk, lots, avg, cur, *, held=True, error=""):
        return {"代號": tk, "種類": "ETF", "held": held,
                "張數": lots, "均價": avg, "現價": cur,
                "_detail": {"error": error} if error else {}}

    def test_lots_are_converted_to_shares(self):
        _t = SVC.compute_portfolio_totals([self._row("A", 2, 10.0, 12.0)])
        assert _t["cost_twd"] == pytest.approx(2 * SHARES_PER_LOT * 10.0)
        assert _t["value_twd"] == pytest.approx(2 * SHARES_PER_LOT * 12.0)
        assert _t["pnl_twd"] == pytest.approx(2 * SHARES_PER_LOT * 2.0)
        assert _t["pnl_pct"] == pytest.approx(20.0)

    def test_partial_is_flagged_not_silently_dropped(self):
        _t = SVC.compute_portfolio_totals([
            self._row("A", 2, 10.0, 12.0),
            self._row("B", None, None, 30.0),      # 觀察清單:沒有成本
        ])
        assert _t["held_n"] == 2 and _t["valued_n"] == 1 and _t["partial"] is True

    def test_nothing_priced_returns_none_not_zero(self):
        assert SVC.compute_portfolio_totals(
            [self._row("A", None, None, None)]) is None
        assert SVC.compute_portfolio_totals([]) is None

    def test_error_and_unheld_rows_are_excluded(self):
        _t = SVC.compute_portfolio_totals([
            self._row("A", 2, 10.0, 12.0),
            self._row("B", 9, 10.0, 99.0, error="無日線"),   # 抓取失敗
            self._row("C", 9, 10.0, 99.0, held=False),       # 觀察清單,沒持有
        ])
        assert _t["held_n"] == 1 and _t["valued_n"] == 1 and _t["partial"] is False


class TestTwoScalesTable:
    """兩套刻度表：四列、只揭露不改、門檻走 SSOT（§3.3）。"""

    def test_has_exactly_four_rows(self):
        assert len(SC._two_scale_rows()) == 4

    def test_first_row_says_it_is_already_fixed(self):
        """第 1 列已當 bug 修掉(commit 1a0992b / 1030c28)——不得再寫「可能相反」。"""
        _name, _a, _b, _status = SC._two_scale_rows()[0]
        assert "吃到本金" in _name
        assert "已修正" in _status and "只剩一套" in _status
        assert "可能相反" not in _status

    def test_other_three_rows_say_disclose_only(self):
        for _row in SC._two_scale_rows()[1:]:
            assert "只揭露不改" in _row[3]

    def test_targets_come_from_ssot(self):
        """80/20 必須組自 `T.*` —— 上游改目標,這張表要跟著動。"""
        _txt = SC._two_scale_rows()[2][1]
        assert f"{T.CORE_TARGET_PCT:.0f}/{T.SATELLITE_TARGET_PCT:.0f}" in _txt

    def test_boll_period_comes_from_ssot(self):
        _txt = SC._two_scale_rows()[1][1]
        assert f"{T.BOLL_PERIOD_WEEKS} 週布林" in _txt

    def test_table_is_static_copy_only(self):
        """本表不吃任何 row 資料 → `render_two_scales` 不得有參數（防呆 4）。

        一旦它開始收 rows,就會有人想在裡面「順便判一下哪邊比較準」。
        """
        import inspect
        assert list(inspect.signature(SC.render_two_scales).parameters) == []


class TestSuggestActionUntouched:
    """L2 判燈與推播路徑零改動的行為釘子（防呆 2 / 防呆 4）。"""

    def test_l2_cruise_still_reachable_and_unchanged(self):
        assert ds.suggest_action(_cruise_assessment()) == "⚪ 巡航：維持定期定額"

    def test_layer1_counts_reuse_the_push_digest(self):
        """卡③的「該加碼 / 該換掉」與 LINE 推播吃同一支 `build_station_digest`。

        釘住這件事,是為了避免有人在 UI 端另立一套「什麼算紅燈」——
        那會讓畫面與推播對同一個組合講不同的話。
        """
        _rows = [
            {"代號": "A", "健檢": "🔴", "建議動作": "汰弱", "加碼金": "", "_detail": {}},
            {"代號": "B", "健檢": "🟢", "建議動作": "加碼", "加碼金": "20%",
             "235 燈號": "🟢 小跌加碼", "_detail": {}},
            {"代號": "C", "健檢": "⚪", "建議動作": "x", "加碼金": "",
             "_detail": {"error": "無日線"}},
        ]
        _d = SVC.build_station_digest(_rows, None)
        assert len(_d["reds"]) == 1 and len(_d["adds"]) == 1 and len(_d["errors"]) == 1
