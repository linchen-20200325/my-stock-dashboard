"""tests/test_station_layer1.py — 戰情室第 1 層(結論卡)+ 兩套刻度表守衛（2026-08-26）

## 這批測試守什麼

1. **N/M 的定義**（防呆 1）—— 分子要「live **且** 有 level」兩個條件同時成立;
   分母扣掉「結構上不適用」與「依規格就不出等級」兩種燈,**不扣**「今天沒抓到」。
   這幾件事各自都出過事:
   - 只看 `state == live` → 個股 KD 被算進分子(它資料通、但從不判等級)→ **高估**;
   - 分母扣掉算不出來的燈 → 資料越爛分數越高,正好是這個指標要防的東西;
   - KD 留在分母 → 只要有一檔個股,那一列就永遠不可能滿,巡航變成印不出來的死碼
     (2026-08-26 user 裁示移出分母;它只離開分母,沒離開畫面)。
2. **同一頁只准有一個數字** —— 第 1 層結論卡與第 3 層燈格牆 / 選列表 / 明細面板
   共用同一把尺(`judged_count`)。改動前第 3 層走寬鬆的 `watch_count`,
   2330 在同一頁印出 2/4 與 3/4 兩個數字。
3. **巡航 gate 做在顯示層**(防呆 2)—— L2 `suggest_action` 一個字都不准動,
   因為它同時餵著主表「建議動作」欄與 `scripts/push_holdings_daily.py` 的
   **LINE 每日推播**。這裡釘住「兩句話刻意不同字」,避免有人日後「順手統一」
   而把推播文案一起改掉。
4. **金額的單位**（§4.1）—— 張 → 股要乘 `SHARES_PER_LOT`;漏乘 = 1000 倍低估。
5. **兩套刻度表**只揭露不改判定,且引用的門檻來自 L0 SSOT(§3.3)。

⚠️ 本檔只測純函式與文案,**不啟動 Streamlit runtime、不做網路 I/O**
(渲染那幾條用一個只收字串的假 `st`,見 `_CapturingST`)。
"""
from __future__ import annotations

import re
from pathlib import Path

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
        """ETF 8 盞、個股 4 盞畫在牆上 —— 但個股分母是 **3**(KD 不進分母)。

        2026-08-26 user 裁示:結構上永遠不出等級的燈視同不適用,移出分母。
        燈的**張數**沒變(牆上還是 4 格,KD 照畫、照點得開),變的是分母。
        呼叫端一律不得寫死總數 —— 混合持股的總格數隨組合成分變。
        """
        assert len(SS.specs_for(T.KIND_ETF)) == 8
        assert len(SS.specs_for(T.KIND_STOCK)) == 4
        _etf = SC.judged_count(ds.missing_light_cells(T.KIND_ETF,
                                                     reason=SS.MISS_FETCH_FAILED))
        _stk = SC.judged_count(ds.missing_light_cells(T.KIND_STOCK,
                                                      reason=SS.MISS_FETCH_FAILED))
        assert _etf == (0, 8)
        assert _stk == (0, 3), "個股分母應為 3(4 盞扣掉不出等級的 KD)"
        # 燈**沒有**從畫面上消失 —— 這條是硬要求,別把「移出分母」做成「移出畫面」。
        assert len(ds.missing_light_cells(T.KIND_STOCK,
                                          reason=SS.MISS_FETCH_FAILED)) == 4


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

    def test_tally_matches_the_denominator_on_real_cells(self):
        """用**真的** assessment 再驗一次 —— 假格子的 key 不在規格表裡,
        驗不到「依規格不出等級」那條排除規則(KD)。

        兩邊口徑一旦分家,卡②會同時印出「N/11 盞給得出判定」與一排加起來
        是 12 的四態分佈 —— 同一張卡自己打自己。
        """
        _k = TestKdDeclaredNotToEmitLevels
        _rows = [_k._etf_cells(), _k._stock_cells()]
        _n, _m = SC.aggregate_judged(_rows)
        assert (_n, _m) == (10, 11)
        assert sum(SC.tally_states(_rows).values()) == _m

    def test_tally_always_has_all_four_keys(self):
        _t = SC.tally_states([(_Cell(),)])
        assert set(_t) == {SS.STATE_LIVE, SS.STATE_DEGRADED,
                           SS.STATE_MISSING, SS.STATE_UNWIRED}


class TestKdDeclaredNotToEmitLevels:
    """個股 KD:**結構上永遠不出等級** → 移出分母（user 2026-08-26 裁示）。

    這一組守的是「移出分母」與「移出畫面」是兩件事,以及「不准為了讓分母好看
    而在畫面上寫一句假話」。
    """

    @staticmethod
    def _stock_cells():
        """一檔資料齊全的個股(財報 A、KD 有值、有上季可比)。"""
        return ds.light_cells(ds.assess_stock(
            ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
            mj_grade="A", mj_score_pct=88, mj_headline="體質佳", mj_fail_items=[],
            kd={"k": 70.0, "d": 65.0, "label": "無"},
            trend={"verdict": "improving"}))

    @staticmethod
    def _etf_cells():
        """一檔什麼都算得出來的 ETF —— 8 盞全部給得出判定。"""
        _idx = pd.date_range("2024-01-07", periods=60, freq="W-SUN")
        return ds.light_cells(ds.assess_holding(
            ticker="0050.TW", name="台灣50", asset_class=T.ASSET_CORE,
            weekly_close=pd.Series([100.0] * 60, index=_idx),
            vix=17.0, premium_pct=0.2, sharpe=1.1, total_return_1y_pct=12.0,
            annual_yield_pct=4.0, inception_years=6.0, ann_return_3y_pct=9.0,
            cum_return_3y_pct=30.0, peer_ranks={3: 0.2, 6: 0.2, 12: 0.2}))

    def test_kd_leaves_the_denominator_but_not_the_wall(self):
        """分母 3、格子 4 —— 少的是分母,不是燈。"""
        _cells = self._stock_cells()
        assert len(_cells) == 4, "KD 不准從燈格牆上消失"
        _kd = [c for c in _cells if c.key == SS.KEY_STOCK_KD]
        assert len(_kd) == 1 and _kd[0].state == SS.STATE_LIVE, \
            "KD 仍然「在看」(K、D 都抓到了),只是不給判定"
        assert SC.judged_count(_cells) == (2, 3)

    def test_kd_is_not_moved_out_by_calling_it_not_applicable(self):
        """§1:不准借用「不適用」的文案 —— 那對 KD 是假話(它對個股完全適用)。"""
        _spec = SS.SPECS_BY_KEY[SS.KEY_STOCK_KD]
        assert _spec.emits_level is False and _spec.no_level_reason.strip()
        _kd = next(c for c in self._stock_cells() if c.key == SS.KEY_STOCK_KD)
        assert _kd.miss_reason != SS.MISS_NOT_APPLICABLE, \
            "用 MISS_NOT_APPLICABLE 把 KD 移出分母 = 在畫面上寫假話"
        assert SS.MISS_TEXT[SS.MISS_NOT_APPLICABLE] not in _spec.no_level_reason
        assert "還沒有判定規則" in _spec.no_level_reason

    def test_a_light_that_claims_to_emit_levels_must_actually_emit_one(self):
        """反向守衛:宣告 `emits_level=True` 的燈,亮著(live)就必須有等級。

        這條是把旗標翻回 True 之後的保險 —— 哪天有人替 KD 接上判燈邏輯、
        把旗標改回 True 卻沒真的產出等級,分母會長回來而分子長不回來,
        巡航又會變成死碼。這裡當場抓到。
        """
        for _cells in (self._etf_cells(), self._stock_cells()):
            for _c in _cells:
                if _c.state != SS.STATE_LIVE:
                    continue
                if not SS.SPECS_BY_KEY[_c.key].emits_level:
                    continue
                assert _c.level != ds.LEVEL_UNJUDGED, \
                    f"{_c.key} 宣告會出等級,實際亮著卻沒有等級"

    def test_cruise_is_reachable_for_an_etf_only_portfolio(self):
        """巡航分支**真的印得出來** —— 不是死碼。"""
        _cells = self._etf_cells()
        assert SC.is_fully_judged(_cells) is True
        _n, _m = SC.aggregate_judged([_cells])
        assert SC.cruise_or_gap(_n, _m, all_rows_judged=True) == SC.CRUISE_TEXT

    def test_stock_rows_are_still_blocked_by_the_degraded_trend_light(self):
        """⚠️ **已知殘留缺口,已回報 user(2026-08-26),不是預設接受的設計。**

        KD 移出分母後,個股列仍然不可能「每盞都給得出判定」:財報趨勢那盞燈在
        規格表被標為「門檻已失準」(只比兩季),有值時四態是 degraded 而非 live,
        分子的條件是 live → 它永遠不進分子,但留在分母裡。
        也就是說:**只要組合裡有個股,巡航那句話仍然印不出來**。

        要不要讓「門檻已失準但有等級」算進分子,是語意決定(degraded 的等級算不算
        數),不是這次授權的範圍 —— 故照實釘住現況。哪天 user 裁示改了,這條會紅,
        改的人必須有意識地改它,而不是默默地讓一個已知缺口消失。
        """
        _cells = self._stock_cells()
        _trend = next(c for c in _cells if c.key == SS.KEY_STOCK_TREND)
        assert _trend.state == SS.STATE_DEGRADED and _trend.level != ds.LEVEL_UNJUDGED
        assert SC.is_fully_judged(_cells) is False
        assert SC.cruise_or_gap(2, 3, all_rows_judged=False) != SC.CRUISE_TEXT


class _CapturingST:
    """假的 `st` —— 只收 markdown 文字。**不啟動 Streamlit runtime。**"""

    def __init__(self) -> None:
        self.md: list[str] = []

    def markdown(self, body="", **_kw) -> None:
        self.md.append(str(body))

    def error(self, *_a, **_kw) -> None:
        pass

    def caption(self, *_a, **_kw) -> None:
        pass

    def text(self) -> str:
        return " ".join(self.md)


class TestBothLayersPrintTheSameNumber:
    """**本次改動真正的交付物**:同一組資料餵第 1 層與第 3 層 → 同一組數字。

    2026-08-26 前:第 3 層走寬鬆的 `watch_count`(只看四態 live)、第 1 層走
    嚴格的 `judged_count`,實測 2330 在同一頁印出 3/4 與 2/4 —— 兩個都不算錯,
    但使用者只會讀成「有一邊算錯了」。user 裁示第 3 層改用嚴格計數。

    這裡**不是**斷言 `judged_count == judged_count`(那是廢話),而是去讀
    第 3 層渲染出來的 HTML 字串,確認它印的就是第 1 層那把尺算出來的數字 ——
    有人把 `render_light_wall` 改回 `watch_count` 就會紅。
    """

    def _cells(self):
        _k = TestKdDeclaredNotToEmitLevels
        return _k._etf_cells(), _k._stock_cells()

    def test_light_wall_prints_the_layer1_numbers(self, monkeypatch):
        _etf, _stk = self._cells()
        _fake = _CapturingST()
        monkeypatch.setattr(SC, "st", _fake)
        SC.render_light_wall([("0050", "台灣50", _etf), ("2330", "台積電", _stk)])
        _pairs = [(int(_a), int(_b))
                  for _a, _b in re.findall(r"(\d+)/(\d+) 有判定", _fake.text())]
        assert _pairs == [SC.judged_count(_etf), SC.judged_count(_stk)]
        assert _pairs == [(8, 8), (2, 3)]
        # 逐列相加 = 第 1 層卡②印的那個 N/M。
        assert (sum(_n for _n, _ in _pairs), sum(_m for _, _m in _pairs)) \
            == SC.aggregate_judged([_etf, _stk]) == (10, 11)
        # 舊的寬鬆計數不准再出現在這一層(它會印「N/M 在看」)。
        assert not re.search(r"\d+/\d+ 在看", _fake.text())

    def test_detail_panel_prints_the_same_number_as_the_wall(self, monkeypatch):
        _, _stk = self._cells()
        _fake = _CapturingST()
        monkeypatch.setattr(SC, "st", _fake)
        SC.render_holding_detail("2330", "台積電", _stk)
        _m = re.search(r"(\d+)/(\d+) 盞有判定", _fake.text())
        assert _m, "明細面板沒有印出 N/M"
        assert (int(_m.group(1)), int(_m.group(2))) == SC.judged_count(_stk) == (2, 3)

    def test_detail_panel_explains_why_the_denominator_is_smaller(self, monkeypatch):
        """少一盞不是算錯 —— 畫面必須講得出「這盞燈還沒有判定規則」。"""
        _, _stk = self._cells()
        _fake = _CapturingST()
        monkeypatch.setattr(SC, "st", _fake)
        SC.render_holding_detail("2330", "台積電", _stk)
        assert "這盞燈還沒有判定規則" in _fake.text()
        assert SS.SPECS_BY_KEY[SS.KEY_STOCK_KD].no_level_reason in _fake.text()
        # 不准借用「不適用」那句文案。
        assert SS.MISS_TEXT[SS.MISS_NOT_APPLICABLE] not in _fake.text()

    def test_layer3_table_column_uses_the_same_counter(self):
        """L5 選列表那一欄(第三個呼叫點)同樣不准留著寬鬆計數。

        這一欄住在 `st.dataframe` 裡,沒有 markdown 可以讀 → 改用原始碼掃描
        (本 repo 既有做法,見 `test_station_empty_state.py`)。
        """
        _src = (Path(__file__).resolve().parents[1]
                / "src" / "ui" / "etf" / "etf_tab_dividend_station.py"
                ).read_text(encoding="utf-8")
        # 只禁**用法**(呼叫 / import),不禁字面 —— 檔內註解要講得出「以前用的是
        # 哪一把尺、為什麼換掉」,連提都不准提會逼人把歷史刪掉。
        assert "watch_count(" not in _src, "第 3 層仍在呼叫寬鬆計數"
        assert "    watch_count," not in _src, "第 3 層仍 import 寬鬆計數"
        assert 'judged_count(r.get("_lights")' in _src
        assert '"有判定": [' in _src, "欄名要跟著數字的意思改(掛舊名賣新東西 = §1)"


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
