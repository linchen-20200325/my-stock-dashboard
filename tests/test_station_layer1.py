"""tests/test_station_layer1.py — 戰情室第 1 層(結論卡)+ 兩套刻度表守衛（2026-08-26）

## 這批測試守什麼

1. **N/M 的定義**（防呆 1）—— 分子要「state ∈ {live, degraded}」**且**「有 level」
   兩個條件同時成立;分母扣掉「結構上不適用」與「依規格就不出等級」兩種燈,
   **不扣**「今天沒抓到」。這幾件事各自都出過事:
   - 只看 `state` → 個股 KD 被算進分子(它資料通、但從不判等級)→ **高估**;
   - 只看 `level` 非空 → **`missing` 的格子常態帶著非空 level**(缺值的 health_a
     是 ⚪、缺值的 screen_return 是 ❔)→ 可選指標全缺的新上市 ETF 會印出
     「8/8 給得出判定」並放行巡航,正好是這個指標要擋的坑 → **高估**;
   - 分母扣掉算不出來的燈 → 資料越爛分數越高,正好是這個指標要防的東西;
   - KD 留在分母 → 只要有一檔個股,那一列就永遠不可能滿,巡航變成印不出來的死碼
     (2026-08-26 user 裁示移出分母;它只離開分母,沒離開畫面)。
   ⚠️ **2026-08-26 第二次裁示**:`degraded`(門檻已失準但給得出等級)**算「有判定」**,
   不阻斷巡航。分子的 state 條件因此從「== live」放寬為**白名單** {live, degraded};
   `missing` / `unwired` 仍然不進分子(理由見上面第二點)。
2. **同一頁只准有一個數字** —— 第 1 層結論卡與第 3 層燈格牆 / 選列表 / 明細面板
   共用同一把尺(`judged_count`)。改動前第 3 層走寬鬆的 `watch_count`,
   2330 在同一頁印出 2/4 與 3/4 兩個數字。
   ⚠️ `SC.watch_count` **已於 2026-08-26 刪除**(production caller 歸零 → user 裁示
   刪死碼)。本檔需要「另一把尺」當對照組時,改用檔內的 `_loose_by_state` /
   `_loose_by_level`(見檔頭),**不要**把它加回 production。
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

# ── 兩把「錯的尺」（**測試檔內**,不是 production API）────────────────────
#
# 2026-08-26 起 production 只有一把尺 `judged_count`;原本拿來當對照組的
# `SC.watch_count` 已隨 caller 歸零而刪除（user 裁示刪死碼）。
# 但**對照組不能一起消失** —— 沒有對照組,「gate 用的是嚴格計數」那幾條就變成
# 在測自己（測資有沒有鑑別力沒人驗）。故把兩種**已知會出錯的實作**寫在這裡,
# 讓它們與 `judged_count` 在同一批測資上分家,`judged_count` 才證明得了自己嚴格。
#
# ⚠️ 這兩支**刻意不放進 production** —— 放回去就會有人拿去印在畫面上,
# 那正是 2026-08-26 前「同一頁兩個數字」的成因。

def _loose_by_state(cells) -> tuple[int, int]:
    """錯法一（舊 `watch_count`）:只看四態 live,**不管有沒有等級**。分母 = 整列燈數。"""
    _cs = tuple(cells or ())
    return sum(1 for c in _cs if c.state == SS.STATE_LIVE), len(_cs)


def _loose_by_level(cells) -> tuple[int, int]:
    """錯法二:只看 level 非空,**不管四態** —— 即 user 那句裁示的字面讀法。

    §1 這個讀法會放行「缺值但帶非空等級」的格子（缺值的 health_a 是 ⚪、
    缺值的 screen_return 是 ❔），見 `TestJudgedCountDefinition` 那一組。
    """
    _cs = tuple(cells or ())
    return sum(1 for c in _cs if c.level != ds.LEVEL_UNJUDGED), len(_cs)


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
        # 只看四態的那把尺會算成 2/2 —— 兩者刻意不同,不是誰壞掉。
        # (`SC.watch_count` 已於 2026-08-26 刪除,對照組改用本檔的 `_loose_by_state`。)
        assert _loose_by_state(_cells) == (2, 2)

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

    def test_degraded_with_a_level_is_judged(self):
        """**2026-08-26 user 第二次裁示**:degraded = 門檻已失準**但給得出等級**
        → 算「有判定」,不阻斷巡航。

        原文這條斷言的是 `(0, 1)`（degraded 不算判定）。那是同一天稍早的現況,
        不是被推翻的錯誤 —— user 看過那個現況之後才裁示放寬,故此處**反向重寫**
        而不是刪掉:留著名字與位置,讓 blame 查得到語意是哪一次改的。
        """
        _cells = (_Cell(level="🟡", state=SS.STATE_DEGRADED),)
        assert SC.judged_count(_cells) == (1, 1)

    def test_degraded_without_a_level_is_still_not_judged(self):
        """放寬的是 **state** 這個條件,不是「有沒有等級」那個條件。

        degraded 且**沒有**等級 → 照樣不算判定(分母仍在)。少了這條,
        「degraded 一律放行」的寫法會通過上一條而不被發現。
        """
        _cells = (_Cell(level=ds.LEVEL_UNJUDGED, state=SS.STATE_DEGRADED),)
        assert SC.judged_count(_cells) == (0, 1)

    def test_missing_with_a_non_empty_level_is_not_judged(self):
        """⚠️ **本條是「別把 state 條件拿掉」的防線** —— 拿掉就紅。

        user 那句裁示的字面是「只要有非空等級即放行」。**照字面做會違憲(§1)**:
        `missing` 的格子**常態帶著非空 level** —— 四個 `_*_light_cells` 分支的
        `has_value` 定義就是「level 不是 ⚪」,所以缺值的 `health_a` 是 `⚪`、
        缺值的 `screen_return` 是 `❔`,兩個都**不是** `LEVEL_UNJUDGED`。
        只看 level 的話,可選指標全缺的新上市 ETF 會印出「8/8 盞給得出判定」
        並放行巡航「今天沒有需要動作的部位」。

        這裡用的就是那兩個**真實形狀**(不是自己編的假格子形狀)——
        下一條 `test_the_real_shape_above_really_occurs_in_production` 直接
        從 `assess_holding` 生出同樣的形狀,證明這不是假想案例。
        """
        _cells = (_Cell(key=SS.KEY_HEALTH_A, level="⚪", state=SS.STATE_MISSING,
                        miss_reason=SS.MISS_NOT_ENOUGH),
                  _Cell(key=SS.KEY_SCREEN_RETURN, level="❔", state=SS.STATE_MISSING,
                        miss_reason=SS.MISS_NOT_ENOUGH))
        # 兩格都有非空等級 —— 照字面實作會算成 2/2。
        assert all(_c.level != ds.LEVEL_UNJUDGED for _c in _cells)
        assert SC.judged_count(_cells) == (0, 2)

    def test_the_real_shape_above_really_occurs_in_production(self):
        """上一條的前提**不是**假想:`assess_holding` 可選指標全缺就長這樣。

        `build_station_rows` 傳的是 `metrics_fn` 拿得到什麼就傳什麼,新上市 /
        冷門 ETF 的 sharpe / 同類排名 / 成立年數本來就是 None → production 可達。
        """
        _idx = pd.date_range("2024-01-07", periods=60, freq="W-SUN")
        _cells = ds.light_cells(ds.assess_holding(
            ticker="00XXX.TW", name="新上市", asset_class=T.ASSET_CORE,
            asset_kind=T.KIND_ETF,
            weekly_close=pd.Series([100.0] * 60, index=_idx),
            vix=None, premium_pct=None, sharpe=None, total_return_1y_pct=None,
            annual_yield_pct=None, inception_years=None, ann_return_3y_pct=None,
            cum_return_3y_pct=None, peer_ranks=None))
        _missing = [_c for _c in _cells if _c.state == SS.STATE_MISSING]
        assert len(_missing) == 6, "前提變了:這一列的缺值格數不再是 6,本組要重算"
        assert all(_c.level != ds.LEVEL_UNJUDGED for _c in _missing), \
            "前提變了:missing 不再帶非空 level —— 那 docstring 裡的理由要重寫"
        # 照字面「只要有非空等級即放行」→ 8/8;實裝擋在 2/8。
        assert sum(1 for _c in _cells if _c.level != ds.LEVEL_UNJUDGED) == 8
        assert SC.judged_count(_cells) == (2, 8)
        assert SC.is_fully_judged(_cells) is False

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
        assert (_n, _m) == (11, 11)      # 2026-08-26 第二次裁示前為 (10, 11)
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
        """分母 3、格子 4 —— 少的是分母,不是燈。

        ⚠️ 分子 2026-08-26 起是 **3**(原本 2):財報趨勢那盞燈是 degraded 且有等級,
        第二次裁示把 degraded 併進「有判定」。KD 的部分(分母 3、牆上 4 格、
        state 仍 live)**完全不受影響** —— 那三句本來就與 degraded 無關。
        """
        _cells = self._stock_cells()
        assert len(_cells) == 4, "KD 不准從燈格牆上消失"
        _kd = [c for c in _cells if c.key == SS.KEY_STOCK_KD]
        assert len(_kd) == 1 and _kd[0].state == SS.STATE_LIVE, \
            "KD 仍然「在看」(K、D 都抓到了),只是不給判定"
        assert SC.judged_count(_cells) == (3, 3)

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

    def test_stock_rows_are_no_longer_blocked_by_the_degraded_trend_light(self):
        """⚠️ **這條是那道「封條」,2026-08-26 user 裁示後被有意識地拆掉。**

        ═══ 原文（保留在這裡,因為它是這個缺口存在過的唯一追溯紀錄）═════════
        原本這條叫 `test_stock_rows_are_still_blocked_by_the_degraded_trend_light`,
        斷言的是**已知殘留缺口**:KD 移出分母後,個股列仍然不可能「每盞都給得出
        判定」—— 財報趨勢那盞燈在規格表被標為「門檻已失準」(只比兩季),有值時
        四態是 degraded 而非 live,而當時分子的條件是 `state == live`
        → 它永遠不進分子,但留在分母裡。**只要組合裡有個股,巡航那句話就印不出來。**
        原文並寫明:「要不要讓『門檻已失準但有等級』算進分子,是語意決定,不是
        當次授權的範圍……哪天 user 裁示改了,這條會紅,**改的人必須有意識地改它**,
        而不是默默地讓一個已知缺口消失。」

        ═══ 現況（2026-08-26 user 第二次裁示）═══════════════════════════════
        user 拍板:**門檻已失準但給得出等級 → 算「有判定」,不阻斷巡航。**
        缺口因此關閉 —— 這條依原文的要求**有意識地反向重寫**(改斷言、改名字、
        留原文),不是把它刪掉。刪掉等於把「這裡曾經有個缺口、是誰在哪一天用什麼
        理由關掉的」一起刪掉。

        ⚠️ 注意這條**不是**在測「degraded 一律放行」:下面仍然釘住那盞燈
        **有等級**(`level != LEVEL_UNJUDGED`)。degraded 而沒有等級的格子照樣
        不進分子,由 `TestJudgedCountDefinition` 那一組守。
        """
        _cells = self._stock_cells()
        _trend = next(c for c in _cells if c.key == SS.KEY_STOCK_TREND)
        # 前提不變:這盞燈仍然是 degraded(規格表沒改),而且它**有等級**。
        assert _trend.state == SS.STATE_DEGRADED and _trend.level != ds.LEVEL_UNJUDGED
        # 變的是這三句 —— 原文分別是 False / (2, 3) / != CRUISE_TEXT。
        assert SC.is_fully_judged(_cells) is True
        assert SC.judged_count(_cells) == (3, 3)
        _n, _m = SC.aggregate_judged([_cells])
        assert SC.cruise_or_gap(_n, _m, all_rows_judged=True) == SC.CRUISE_TEXT


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
    有人把 `render_light_wall` 改回寬鬆計數就會紅(`SC.watch_count` 本身已於
    2026-08-26 刪除,所以現在「改回去」得先自己寫一支 —— 這一條照樣抓得到)。
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
        assert _pairs == [(8, 8), (3, 3)]      # 個股 2026-08-26 第二次裁示前為 (2, 3)
        # 逐列相加 = 第 1 層卡②印的那個 N/M。
        assert (sum(_n for _n, _ in _pairs), sum(_m for _, _m in _pairs)) \
            == SC.aggregate_judged([_etf, _stk]) == (11, 11)
        # 舊的寬鬆計數不准再出現在這一層(它會印「N/M 在看」)。
        assert not re.search(r"\d+/\d+ 在看", _fake.text())

    def test_detail_panel_prints_the_same_number_as_the_wall(self, monkeypatch):
        _, _stk = self._cells()
        _fake = _CapturingST()
        monkeypatch.setattr(SC, "st", _fake)
        SC.render_holding_detail("2330", "台積電", _stk)
        _m = re.search(r"(\d+)/(\d+) 盞有判定", _fake.text())
        assert _m, "明細面板沒有印出 N/M"
        assert (int(_m.group(1)), int(_m.group(2))) == SC.judged_count(_stk) == (3, 3)

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


class TestKdBlockIsTrueInAllFourStates:
    """「這盞燈還沒有判定規則」那一塊 —— **四種狀態下印出來的話都必須為真**。

    2026-08-26 兩組稽核抓到的洞:那段文字原本帶著**現在式的事實斷言**
    (「K、D 值都抓得到、鈍化／背離也照印」「把 K、D 數字…當短線參考自己判讀」),
    而明細面板的渲染條件**只看規格旗標、不看四態** → 兩條 production 路徑會讀到假話:
      · KD 沒有 k / d 值那一列(`assess_stock(kd=None)`)—— 該格四態 missing 而且
        **沒有缺值原因可印**(`miss_reason` 是空字串),畫面上唯一的解釋就是這一段,
        它卻叫使用者去看一個不存在的 K/D 數字;
      · 整檔抓取失敗那一列(`missing_light_cells`)—— 每一盞燈都 missing,同一個面板
        會同時印出「重跑一百次也一樣」與「這一檔整批抓取失敗,看該列的錯誤訊息」。

    **修法選的是改文案(與狀態無關的結構事實),不是把渲染條件收成只在 live 印。**
    理由:分母少一盞這件事在四態全部成立,只在 live 印會讓「今天沒抓到」那幾列的
    分母**沒有人交代得出來** —— 而交代分母正是這一塊存在的另一半理由。
    代價是這段字必須自己站得住:故下面第一條直接釘「四種狀態印的是同一段字」,
    其餘幾條釘那段字的內容本身為真。
    """

    _HEAD = "這盞燈還沒有判定規則"

    @staticmethod
    def _kd_spec():
        return SS.SPECS_BY_KEY[SS.KEY_STOCK_KD]

    @staticmethod
    def _render(cells, monkeypatch, *, error=""):
        _fake = _CapturingST()
        monkeypatch.setattr(SC, "st", _fake)
        SC.render_holding_detail("2330", "台積電", cells, error=error)
        return _fake

    @classmethod
    def _kd_block(cls, fake):
        """面板裡「這盞燈還沒有判定規則」那一塊(整段 html)。"""
        _hit = [_m for _m in fake.md if cls._HEAD in _m]
        assert len(_hit) == 1, f"這一塊應該剛好印一次,實際 {len(_hit)} 次"
        return _hit[0]

    # ── 四種狀態的格子 ───────────────────────────────────────────────
    @staticmethod
    def _cells_live():
        """live:K、D 都抓到了(production 正常路徑)。"""
        return TestKdDeclaredNotToEmitLevels._stock_cells()

    @staticmethod
    def _cells_missing_no_kd():
        """missing 之一:**production 可達** —— 上游沒給 KD,`kd_state` 是 None。

        `build_station_rows` 傳的就是 `m.get("kd_state")`,拿不到就是 None。
        """
        return ds.light_cells(ds.assess_stock(
            ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
            mj_grade="A", mj_score_pct=88, mj_headline="體質佳", mj_fail_items=[],
            kd=None, trend={"verdict": "improving"}))

    @staticmethod
    def _cells_missing_fetch_failed():
        """missing 之二:**production 必經** —— 整檔抓取失敗的那一列。"""
        return ds.missing_light_cells(T.KIND_STOCK, reason=SS.MISS_FETCH_FAILED)

    @staticmethod
    def _cells_forced(state):
        """degraded / unwired:KD 的規格旗標讓它在 production 走不到這兩態
        (`wired=True` + `discriminative=True`),但渲染條件不看四態 ——
        故照樣把這兩態餵進去,確認印出來的話仍然為真。
        """
        return (_Cell(key=SS.KEY_STOCK_KD, level=ds.LEVEL_UNJUDGED, state=state),)

    def _all_four(self):
        return {
            SS.STATE_LIVE: self._cells_live(),
            SS.STATE_MISSING: self._cells_missing_no_kd(),
            SS.STATE_DEGRADED: self._cells_forced(SS.STATE_DEGRADED),
            SS.STATE_UNWIRED: self._cells_forced(SS.STATE_UNWIRED),
        }

    def test_the_kd_cell_really_reaches_all_four_states(self):
        """先確認測資真的把 KD 那一格擺在四種狀態(否則下面幾條在測空氣)。"""
        for _state, _cells in self._all_four().items():
            _kd = next(_c for _c in _cells if _c.key == SS.KEY_STOCK_KD)
            assert _kd.state == _state
        _kd_err = next(_c for _c in self._cells_missing_fetch_failed()
                       if _c.key == SS.KEY_STOCK_KD)
        assert _kd_err.state == SS.STATE_MISSING

    def test_the_block_prints_the_same_words_in_all_four_states(self, monkeypatch):
        """**本組的骨幹**:四態印的是同一段字 → 這段字為真與否與狀態無關,
        只要它在任一態為真就在四態都為真(下面幾條負責驗它為真)。

        有人把文案改回帶狀態的寫法(「K、D 值都抓得到」)不會被這一條抓到 ——
        那件事由 `test_the_block_makes_no_claim_about_what_is_available_now` 抓;
        這一條抓的是另一半:有人把渲染條件改成只在某一態印。
        """
        _blocks = {_s: self._kd_block(self._render(_c, monkeypatch))
                   for _s, _c in self._all_four().items()}
        _blocks[SS.MISS_FETCH_FAILED] = self._kd_block(
            self._render(self._cells_missing_fetch_failed(), monkeypatch,
                         error="HTTPError: 404"))
        assert len(set(_blocks.values())) == 1, \
            "同一塊在不同狀態下印出不同的字 —— 它就不再是「與狀態無關的結構事實」"
        assert self._kd_spec().no_level_reason in next(iter(_blocks.values()))

    def test_the_block_makes_no_claim_about_what_is_available_now(self):
        """§1:這段字只准講**結構事實**,不准講「現在有什麼」。

        下面這幾句都是原文真的寫過、而且在兩條 missing 路徑上是**假話**的句子。
        它們用條件句 / 反事實句改寫之後才站得住(「就算 K、D 都抓得到…」)。
        """
        _txt = self._kd_spec().no_level_reason
        for _lie in ("K、D 值都抓得到、鈍化／背離也照印",
                     "把 K、D 數字和鈍化／背離當短線參考",
                     "也**不是**「今天沒抓到」"):
            assert _lie not in _txt, f"這句在缺資料時是假話:{_lie}"
        # 條件句框架必須在 —— 少了它,同樣的內容就變回事實斷言。
        assert "就算 K、D 都抓得到" in _txt
        assert "有 K、D 數字時" in _txt

    def test_the_block_never_denies_that_the_data_could_be_missing(self):
        """與缺值原因**不得互相打架**(這是憲法點名過的同一種錯)。

        整檔抓取失敗那一列會同時印出「整批抓取失敗,看該列的錯誤訊息」——
        這段字若還說「不是今天沒抓到」,兩句在同一個面板上正面矛盾。
        現行寫法把「有沒有等級」與「這輪有沒有抓到」明確分開,兩句可以並存。
        """
        _txt = self._kd_spec().no_level_reason
        assert "今天沒抓到" not in _txt and "這輪沒抓到" not in _txt
        assert "這輪有沒有抓到" in _txt, "要嘛不提,要嘛把它指去「狀態」那一行"
        # 「重跑一百次」只准掛在**等級**上,不准掛在「抓不抓得到」上。
        assert "重跑一百次也一樣不會有等級" in _txt

    def test_all_four_states_still_explain_the_missing_denominator(self, monkeypatch):
        """硬要求:分母少一盞這件事,四態都要有交代(這是不收渲染條件的理由)。"""
        for _state, _cells in self._all_four().items():
            _blk = self._kd_block(self._render(_cells, monkeypatch))
            assert "分母不把它算進去" in _blk, f"{_state} 少了分母的交代"

    def test_missing_kd_row_has_no_other_explanation_on_screen(self, monkeypatch):
        """釘住稽核那條路徑的前提:這一列的 KD 格**沒有缺值原因可印**。

        `_stock_light_cells` 對 KD 刻意 `reason=""`(上游沒登記就不代它挑一個)——
        所以畫面上唯一解釋「這格為什麼是空的」的就是這一塊。它一旦講假話,
        使用者沒有第二個地方可以對照。
        """
        _cells = self._cells_missing_no_kd()
        _kd = next(_c for _c in _cells if _c.key == SS.KEY_STOCK_KD)
        assert _kd.miss_reason == "", "前提變了:KD 現在有缺值原因,這條要重寫"
        _fake = self._render(_cells, monkeypatch)
        assert not any(_t in _fake.text() for _t in SS.MISS_TEXT.values()), \
            "這一列不該有任何 MISS_TEXT —— 唯一的解釋就是那一塊"
        assert self._HEAD in _fake.text()

    def test_fetch_failed_row_prints_both_and_they_do_not_contradict(self, monkeypatch):
        """整檔抓取失敗:兩塊同時印,而且兩句都為真、互不否定。"""
        _fake = self._render(self._cells_missing_fetch_failed(), monkeypatch,
                             error="HTTPError: 404")
        _txt = _fake.text()
        assert SS.MISS_TEXT[SS.MISS_FETCH_FAILED] in _txt
        assert self._HEAD in _txt
        # 抓取失敗那句叫人去看錯誤訊息;KD 這句只講「就算抓到也沒有等級」。
        # 兩者的交集只有「等級」,沒有「抓不抓得到」—— 那才是不打架的條件。
        assert "就算 K、D 都抓得到" in self._kd_block(_fake)


class TestCruiseGateIsPinnedToTheStrictScale:
    """`is_fully_judged` **必須**走 `judged_count`,不准偷換成任何一把寬鬆的尺。

    2026-08-26 稽核實測:把 `is_fully_judged` 裡的 `judged_count` 換成
    `watch_count`,完整 fast lane **6494 passed / 0 failed** —— 巡航 gate 這個
    最關鍵的消費端,當時沒有任何一條測試釘住它用的是哪一把尺。
    兩把尺在目前的 production 資料上碰巧同值,所以那不是行為 bug;但這顆改動的
    核心交付物就是「同一把尺」,而**一個沒有防護力的 gate 跟沒有 gate 一樣**。

    ⚠️ **2026-08-26 `SC.watch_count` 已刪除,本組的守衛力沒有跟著消失。**
    本組守的一直是**行為**（「這一列不准通過 gate」）,不是「有沒有比對到某支
    函式」—— 最關鍵的 `test_gate_is_closed_by_a_live_but_unjudged_light` 原文就
    只斷言 `is_fully_judged(...) is False`,一個字都沒提 `watch_count`（只在
    docstring 舉例）。刪掉函式不影響它。
    改掉的只有**對照組**:由 production 的 `SC.watch_count` 換成本檔的
    `_loose_by_state`（見檔頭）。對照組的用途是證明**測資有鑑別力**
    ——「這一列上兩把尺確實分家」,沒有它,下面兩條可能在測一列根本分不出高下的
    資料而自己不知道。

    ⚠️ 本組現在同時守**兩種**錯法（原本只有一種）:
      · `_loose_by_state` —— 只看四態,不管有沒有等級（舊 `watch_count`）;
      · `_loose_by_level` —— 只看等級,不管四態（user 那句裁示的字面讀法,
        會放行「缺值但帶非空等級」的格子,§1）。
    兩種都必須被 gate 擋下。

    要讓尺分家,測資必須含一盞**資料通(live)但沒有等級**的燈:
    `_loose_by_state` 會把它算成「在看」→ 說這一列滿了;`judged_count` 不算進分子
    → 擋下。個股 KD 以外的燈只要 `emits_level=True` 卻沒出等級就是這種格子
    (那正是 `judged_count` 分子多一個條件的理由)。
    """

    @staticmethod
    def _live_but_unjudged_row():
        """一盞有等級的 live 燈 + 一盞 live 但沒有等級的燈。

        兩盞都在分母裡(假 key 不在規格表 → `_in_judged_denominator` 一律算進
        分母,寧可分數偏低),差別只在**分子**。
        """
        return (_Cell(level="🟢"), _Cell(level=ds.LEVEL_UNJUDGED))

    @staticmethod
    def _missing_but_levelled_row():
        """一盞有等級的 live 燈 + 一盞**缺值但帶非空等級**的燈(錯法二的測資)。

        形狀取自 production:缺值的 `health_a` 是 `⚪`、缺值的 `screen_return`
        是 `❔`,兩個都不是 `LEVEL_UNJUDGED`(見 `TestJudgedCountDefinition`)。
        """
        return (_Cell(level="🟢"),
                _Cell(key=SS.KEY_HEALTH_A, level="⚪", state=SS.STATE_MISSING,
                      miss_reason=SS.MISS_NOT_ENOUGH))

    def test_two_scales_really_disagree_on_this_row(self):
        """前提:這一列上尺確實分家(否則下面兩條抓不到偷換)。

        `SC.watch_count` 2026-08-26 已刪 → 對照組改用檔頭的 `_loose_by_state`,
        斷言的數字與原文一字不差。
        """
        _cells = self._live_but_unjudged_row()
        assert SC.judged_count(_cells) == (1, 2)
        assert _loose_by_state(_cells) == (2, 2)

    def test_the_level_only_scale_also_disagrees(self):
        """同樣的前提,套在**錯法二**上(2026-08-26 新增)。"""
        _cells = self._missing_but_levelled_row()
        assert SC.judged_count(_cells) == (1, 2)
        assert _loose_by_level(_cells) == (2, 2)

    def test_gate_is_closed_by_a_live_but_unjudged_light(self):
        """**本組最重要的一條** —— gate 改用只看四態的寬鬆尺,這裡就會紅。"""
        assert SC.is_fully_judged(self._live_but_unjudged_row()) is False, \
            "巡航 gate 走的是寬鬆計數:「在看」被當成「有判定」放行了"

    def test_gate_is_closed_by_a_missing_but_levelled_light(self):
        """同一件事,擋的是**錯法二**(2026-08-26 新增)。

        gate 改成「只要有非空等級即放行」,這裡就會紅 —— 而那正是 user 那句裁示的
        字面讀法。缺資料的列絕不可以印出「今天沒有需要動作的部位」(§1)。
        """
        assert SC.is_fully_judged(self._missing_but_levelled_row()) is False, \
            "巡航 gate 只看等級不看四態:缺資料的格子被當成「有判定」放行了"

    def test_gate_opens_when_every_light_has_a_level(self):
        """反向:三把尺一致時 gate 照樣開得了(不是把 gate 焊死才通過上面兩條)。"""
        _cells = (_Cell(level="🟢"), _Cell(level="🔴"))
        assert SC.judged_count(_cells) == _loose_by_state(_cells) \
            == _loose_by_level(_cells) == (2, 2)
        assert SC.is_fully_judged(_cells) is True

    def test_gate_opens_for_a_degraded_light_with_a_level(self):
        """2026-08-26 第二次裁示的反向:degraded 有等級 → gate 開得了。

        放在這一組,是為了讓「放寬」與「不准放寬到缺資料」兩件事並排 ——
        下一個人同時看得到界線在哪裡。
        """
        _cells = (_Cell(level="🟢"),
                  _Cell(level="🟡", state=SS.STATE_DEGRADED))
        assert SC.judged_count(_cells) == (2, 2)
        assert SC.is_fully_judged(_cells) is True
        # 但只看四態的舊尺會把它算成 1/2 —— 兩把尺仍然是分家的。
        assert _loose_by_state(_cells) == (1, 2)

    def test_todo_card_counts_that_row_as_unjudged(self):
        """同一件事在卡③的下游:那一列必須被算成「未判定」。

        這行運算式與 L5 的 `_unjudged_n` 同型(見 `etf_tab_dividend_station`)——
        gate 一旦偷換成寬鬆計數,卡③會少算一檔,畫面顯示「沒有待處理」。
        """
        _rows = [self._live_but_unjudged_row()]
        assert sum(1 for _r in _rows if not SC.is_fully_judged(_r)) == 1


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


class TestAssetKindNormalisation:
    """第 5 項（user 2026-08-26 核准）：`asset_kind` 不准把第三種值放進 `assess_holding`。

    ## 這一組在守什麼

    `build_station_rows` 原本寫 `h.get("asset_kind", T.KIND_ETF)`。
    `dict.get(k, default)` 的預設值**只在 key 缺席時生效** —— key 在、值是 `None`
    或 `""` 時會**原樣通過**。那個值一路傳進 `assess_holding`,而該函式用
    `_is_etf = asset_kind == T.KIND_ETF` 判斷,第三種值一律判 False →
    折溢價 + 3-3-3 三項共 **4 盞燈**被標成 `MISS_NOT_APPLICABLE`。
    後果是一檔正常 ETF 憑空少 4 盞燈,而畫面會對使用者說「這類持股結構上沒有
    這盞燈」—— 那是假話（§1）。改成 `or` + `T.classify_asset_kind(tk)` 後補起來。

    ## 與第 2 項（清「不適用」假文案）的關係

    第 2 項把可信度卡與明細 caption 裡的「個股沒有折溢價」拿掉,前提是
    **production 走不到 `MISS_NOT_APPLICABLE`**。在這一項修好之前,那個前提是
    **偶然為真**（剛好沒有人餵得出第三種值),不是結構性為真。
    這一組測試就是把「偶然」變成「有東西在守」——
    文案站得住,靠的是這裡紅不紅,不是靠沒有人去踩。

    ⚠️ `T.classify_asset_kind`（`shared/dividend_station_thresholds.py`）回 **兩值**。
    `src/compute/etf/asset_lag.py` 有個**同名**函式回**三值**（多一個 `'unknown'`）,
    那支是給組合體檢落後燈號用的 —— 拿錯會讓 `unknown` 直接走進
    `assess_holding(_is_etf=False)`,正好把這個洞放大。下面有一條直接釘住這件事。
    """

    @staticmethod
    def _metrics(_tk, _ak=T.KIND_ETF):
        if _ak == T.KIND_STOCK:
            return {"mj_grade": "A", "mj_score_pct": 88, "mj_headline": "體質佳",
                    "mj_fail_items": [], "kd_state": {"k": 70.0, "d": 65.0, "label": "無"},
                    "trend": {"verdict": "improving"}}
        return {"weekly_close": pd.Series(
            [100.0] * 60,
            index=pd.date_range("2024-01-07", periods=60, freq="W-SUN")),
            "premium_pct": 0.2}

    def _rows(self, holding):
        return SVC.build_station_rows([holding], vix=17.0, metrics_fn=self._metrics)

    @staticmethod
    def _na_lights(rows):
        return [_c.key for _r in rows for _c in (_r.get("_lights") or ())
                if _c.miss_reason == SS.MISS_NOT_APPLICABLE]

    @pytest.mark.parametrize("kind", [None, ""])
    def test_falsy_asset_kind_does_not_leak_a_third_value(self, kind):
        """**本組最重要的一條** —— 把 `or` 改回 `get(k, default)` 這裡就會紅。

        `None` / `""` 是 Google Sheet 空白欄位最可能長出來的兩種值。
        """
        _rows = self._rows({"ticker": "0050.TW", "name": "台灣50",
                            "asset_class": T.ASSET_CORE, "asset_kind": kind})
        assert self._na_lights(_rows) == [], \
            f"asset_kind={kind!r} 漏出第三種值 → 一檔正常 ETF 被標成「結構上不適用」"
        # 正面斷言:它被正規化成 ETF,8 盞燈一盞不少。
        assert len(_rows[0]["_lights"]) == len(SS.specs_for(T.KIND_ETF)) == 8

    @pytest.mark.parametrize("kind", [None, ""])
    def test_falsy_asset_kind_on_a_stock_ticker_goes_to_the_stock_path(self, kind):
        """正規化走的是**代號規則**,不是「一律當 ETF」。

        2330 是 4 碼純數字 → `classify_asset_kind` 回 stock → 走 `assess_stock`
        (4 盞個股燈),而不是被塞進 ETF 的 235/3-3-3。
        ⚠️ 這條同時揭露一個**原寫法也錯、但不在原始回報表格裡**的情形:
        `{"ticker": "2330"}`(asset_kind **key 缺席**)在舊寫法下 `default=KIND_ETF`
        → 個股被當 ETF 跑 235/3-3-3。原始回報的表格用 0050 舉例,0050 本來就判 ETF,
        所以那一格看起來「兩種寫法一樣」—— 換個代號就不一樣了。
        """
        _rows = self._rows({"ticker": "2330", "name": "台積電",
                            "asset_class": T.ASSET_SATELLITE, "asset_kind": kind})
        assert _rows[0]["種類"] == "個股"
        assert len(_rows[0]["_lights"]) == len(SS.specs_for(T.KIND_STOCK)) == 4
        assert self._na_lights(_rows) == []

    def test_absent_key_on_a_stock_ticker_also_goes_to_the_stock_path(self):
        """key **完全缺席**同樣走代號規則(舊寫法會回 `KIND_ETF` 把個股當 ETF 跑)。"""
        _rows = self._rows({"ticker": "2330", "name": "台積電",
                            "asset_class": T.ASSET_SATELLITE})
        assert _rows[0]["種類"] == "個股"
        assert self._na_lights(_rows) == []

    @pytest.mark.parametrize("kind,expect", [(T.KIND_ETF, "ETF"), (T.KIND_STOCK, "個股")])
    def test_explicit_values_are_untouched(self, kind, expect):
        """反向:正常的 etf / stock 一個字都沒變(這一項不准動到既有行為)。"""
        _tk = "0050.TW" if kind == T.KIND_ETF else "2330"
        _rows = self._rows({"ticker": _tk, "name": "x",
                            "asset_class": T.ASSET_CORE, "asset_kind": kind})
        assert _rows[0]["種類"] == expect
        assert self._na_lights(_rows) == []

    @pytest.mark.parametrize("kind", ["ETF", "fund", "unknown"])
    def test_truthy_unknown_string_is_a_KNOWN_REMAINING_GAP(self, kind):
        """⚠️ **這條釘的是「還沒修好」,不是「已經修好」—— 讀的人別誤會。**

        `or` 只攔 **falsy**。truthy 的未知字串（`"ETF"` 大寫 / `"fund"` /
        `asset_lag` 那支三值函式會回的 `"unknown"`）**照樣原樣通過**,實測仍會標出
        4 盞 `MISS_NOT_APPLICABLE`。

        為什麼不順手一起修:2026-08-26 核准的改法明文是「改成與
        `resolve_holding_names` 相同的寫法」(也就是 `or`)。要**結構上**保證兩值
        得再加白名單,那是**另一個決定**,不在本次核准範圍(§-1 / §8.4「禁止自作主張」)。

        為什麼今天不是 bug:兩個 production 產出端
        (`_load_holdings_from_portfolio` 與 `scripts/push_holdings_daily.py`)
        都已先跑 `T.classify_asset_kind`,只吐 etf / stock 兩值 → 不可達。

        **哪天有人加白名單修掉它,這條會紅** —— 那時把它改成正向斷言,
        並回頭把 `build_station_rows` 的註解與本組 docstring 一起更新。
        """
        _rows = self._rows({"ticker": "0050.TW", "name": "台灣50",
                            "asset_class": T.ASSET_CORE, "asset_kind": kind})
        assert sorted(self._na_lights(_rows)) == sorted(
            [SS.KEY_HEALTH_D, SS.KEY_SCREEN_INCEPTION,
             SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER]), \
            "這個洞被修掉了(好事) —— 請把本條改成正向斷言並更新兩處註解"

    def test_the_right_classify_asset_kind_only_ever_returns_two_values(self):
        """釘住「拿對函式」:`T.classify_asset_kind` 只回 etf / stock。

        `src/compute/etf/asset_lag.classify_asset_kind` **同名但回三值**
        (多一個 `'unknown'`)。真的拿錯的話,`unknown` 是 truthy → `or` 攔不住 →
        直接走進 `assess_holding(_is_etf=False)`,把上一條那個洞從「不可達」
        變成「每天都在發生」。故兩支一起釘。
        """
        from src.compute.etf.asset_lag import classify_asset_kind as _lag_classify

        _probe = ["0050", "0050.TW", "00878", "00980A", "2330", "2330.TW",
                  "2881A", "6488", "BND", "VOO", "^TWII", "", "???"]
        assert {T.classify_asset_kind(_t) for _t in _probe} <= {T.KIND_ETF, T.KIND_STOCK}
        # 對照組:那支同名函式**確實**會回第三種值 —— 所以不能拿它來正規化。
        assert "unknown" in {_lag_classify(_t) for _t in _probe}
        assert T.classify_asset_kind is not _lag_classify


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
