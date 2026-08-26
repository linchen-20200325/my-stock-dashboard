"""tests/test_station_cards.py — L4 戰情室燈格渲染守衛（2026-08-25, B2）。

## 這些測試在守什麼

燈格有**三種死法**,三種都不會讓畫面看起來壞掉,所以只能靠測試釘住:

1. **新增一種判定符號但沒決定怎麼畫** —— `LEVEL_STYLES` 漏一個 key,
   畫面只會在該情境下炸(或更糟:被誰加上 `.get(..., 預設)` 之後靜默畫成灰格)。
   本檔守「L2 能吐出的每一個 `level` 都登錄在 `LEVEL_STYLES`」。

2. **3-3-3 的 ❌ 被畫成紅燈** —— 主表刻意沒有這盞紅燈(`_worst_level` 只收四盞
   健檢 `Flag`,3-3-3 從不參與 `worst_health`)。上色成紅 = 在格子牆上憑空多一盞
   主表沒有的紅燈,那是**新判斷**不是轉換。本檔守「❌ 不得有填色」。

3. **`LEVEL_UNJUDGED` 被填了顏色** —— 那等於假裝「從來沒判過等級」的燈有判定。
   本檔守「`LEVEL_UNJUDGED` 不得有填色,且要與 ❌ 在視覺上分得開」。

另加守一條 user 2026-08-25 明確點名的:**狀態頻道不得出 emoji**
(`STATE_META[live]` 是 `("運作中", "🟢")`,而判定通過也是 🟢 —— 兩個 🟢 並排
印出去等於自己製造混淆)。

⚠️ 本檔只測 L0/L2/L4 純轉換,**不啟動 Streamlit runtime**。
"""
from __future__ import annotations

import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from src.compute.etf import dividend_station as ds
from src.ui.render import station_cards as SC


def _weekly(n: int = 60, base: float = 100.0) -> pd.Series:
    idx = pd.date_range("2024-01-07", periods=n, freq="W-SUN")
    return pd.Series([base + i * 0.1 for i in range(n)], index=idx)


# ════════════════════════════════════════════════════════════════
# 一、LEVEL_STYLES 必須涵蓋 L2 吐得出來的每一個符號
# ════════════════════════════════════════════════════════════════
class TestEveryLevelIsPaintable:

    def test_all_235_icons_registered(self):
        """235 的 5 個 icon(含 💰 停利)全部要能畫。"""
        for _meta in T.LIGHT_META.values():
            assert _meta["icon"] in SC.LEVEL_STYLES, \
                f"235 icon {_meta['icon']!r} 沒登錄在 LEVEL_STYLES"

    def test_health_and_screen_and_unjudged_registered(self):
        """健檢 4 級 + 3-3-3 3 符號 + 未判定 sentinel。"""
        for _lv in ("🔴", "🟡", "🟢", "⚪", "✅", "❌", "❔", ds.LEVEL_UNJUDGED):
            assert _lv in SC.LEVEL_STYLES

    def test_real_etf_assessment_cells_all_paintable(self):
        """走真的 `assess_holding` → `light_cells`,每一格都畫得出來。"""
        a = ds.assess_holding(
            ticker="0056.TW", name="高股息", asset_class=T.ASSET_CORE,
            weekly_close=_weekly(), vix=15.0, premium_pct=0.2, sharpe=0.8,
            total_return_1y_pct=9.0, annual_yield_pct=5.0, inception_years=10.0,
            ann_return_3y_pct=8.0, cum_return_3y_pct=25.0, peer_ranks=None)
        for _c in ds.light_cells(a):
            assert SC.cell_html(_c)          # 不炸 = 有登錄

    def test_missing_light_cells_are_paintable(self):
        """整檔抓取失敗的列(全部 `LEVEL_UNJUDGED` + missing)也要畫得出來。"""
        for _kind in (T.KIND_ETF, T.KIND_STOCK):
            for _c in ds.missing_light_cells(_kind, reason=SS.MISS_FETCH_FAILED):
                assert SC.cell_html(_c)

    def test_unknown_level_raises_not_silently_grey(self):
        """§1：沒登錄的符號當場炸,**不**畫成一格沒人知道是什麼的灰格子。"""
        with pytest.raises(KeyError):
            SC.cell_html(SC._DemoCell(level="🟣", state=SS.STATE_LIVE))


# ════════════════════════════════════════════════════════════════
# 二、user 2026-08-25 明文禁止的三件事
# ════════════════════════════════════════════════════════════════
class TestForbiddenMappings:

    def test_screen_fail_is_not_red(self):
        """❌ 未過**不得**被畫成紅燈 —— 主表沒有這盞紅燈,上色就是新判斷。"""
        _sty = SC.LEVEL_STYLES["❌"]
        assert _sty.fill == "", "3-3-3 的 ❌ 不得有填色"
        assert _sty.glyph, "不填色就必須有記號,否則與『未判定』分不開"

    def test_unjudged_has_no_fill(self):
        """`LEVEL_UNJUDGED` 不得有顏色 —— 填色 = 假裝它有判定。"""
        _sty = SC.LEVEL_STYLES[ds.LEVEL_UNJUDGED]
        assert _sty.fill == ""
        assert _sty.dashed, "未判定要用虛線框,才與有判定的 ❌(實線)分得開"

    def test_unjudged_and_screen_fail_are_visually_distinct(self):
        """兩種 hollow 不可長得一樣(否則『沒判過』與『判了沒過』混為一談)。"""
        assert SC.LEVEL_STYLES["❌"] != SC.LEVEL_STYLES[ds.LEVEL_UNJUDGED]

    def test_state_channel_emits_no_emoji(self):
        """狀態頻道只出中文標籤,不出 `STATE_META` 的第二欄 emoji。"""
        _emojis = {_e for _, _e in SS.STATE_META.values()}
        for _state in SS.STATE_META:
            _html = SC.cell_html(SC._DemoCell(level="🟢", state=_state))
            # 格子本體(去掉 title= 提示文字)不得含任何四態 emoji
            _body = _html.split('title="')[0]
            for _e in _emojis:
                assert _e not in _body, f"{_state}: 格子裡印出了狀態 emoji {_e}"


# ════════════════════════════════════════════════════════════════
# 三、level_meaning 必須按「該盞燈自己那把尺」回答
# ════════════════════════════════════════════════════════════════
class TestMeaningIsPerScale:

    def test_same_symbol_two_scales_two_meanings(self):
        """🔴 在健檢是踩紅線、在 235 是崩盤加碼 —— 不可回同一句。"""
        _h = SC.level_meaning("health", "🔴")
        _t = SC.level_meaning("timing", "🔴")
        assert _h and _t and _h != _t

    def test_235_meaning_comes_from_ssot(self):
        """235 的文案讀 `LIGHT_META`,不在 L4 重打一次(改上游要自動跟著改)。"""
        assert SC.level_meaning("timing", "🔴") == T.LIGHT_META[T.LIGHT_3]["label"]
        assert SC.level_meaning("timing", "💰") == \
            T.LIGHT_META[T.LIGHT_TAKE_PROFIT]["label"]

    def test_every_spec_group_has_a_scale(self):
        """規格表出現的每個 group 都要有對應的尺,否則明細面板會空白。"""
        for _s in SS.STATION_SPECS:
            assert _s.group in SC._MEANING_BY_GROUP, \
                f"規格表 group {_s.group!r} 沒有對應的判定尺"

    def test_each_stock_light_answers_on_its_own_scale(self):
        """B3:個股 4 盞同符號、**三把不同的尺** —— 不可回同一句。

        `_SWAP_MEANING` 的 🔴 是「建議換出」。財報趨勢的 🔴 只是
        「上一季到這一季變差的項目多於變好」—— 一檔 A+ 的公司也可能是 🔴。
        共用汰換那把尺,明細面板會對著體質良好的股票印「建議換出」= 假敘述(§1)。
        """
        _swap = SC.level_meaning("stock", "🔴", key=SS.KEY_STOCK_SWAP)
        _health = SC.level_meaning("stock", "🔴", key=SS.KEY_STOCK_HEALTH)
        _trend = SC.level_meaning("stock", "🔴", key=SS.KEY_STOCK_TREND)
        assert _swap and _health and _trend
        assert len({_swap, _health, _trend}) == 3, "三盞燈的 🔴 講了同一句話"
        # 趨勢那盞刻意**明說**它不是換出建議 —— 只檢查「不等於汰換那句」不夠,
        # 那樣把 `_SWAP_MEANING` 改一個標點就會綠。
        assert "不等於建議換出" in _trend

    def test_stock_trend_neutral_is_a_verdict_not_a_blank(self):
        """趨勢的 ⚪ 是「比過了、都沒變」;汰換的 ⚪ 才是「沒有判定」。"""
        _trend = SC.level_meaning("stock", "⚪", key=SS.KEY_STOCK_TREND)
        _swap = SC.level_meaning("stock", "⚪", key=SS.KEY_STOCK_SWAP)
        assert _trend != _swap
        assert "沒有判定" not in _trend

    def test_key_scale_falls_back_to_the_group_scale(self):
        """沒有自己一把尺的燈照舊走 group(舊呼叫端行為不變)。"""
        assert SC.level_meaning("stock", "🔴", key=SS.KEY_STOCK_SWAP) == \
            SC.level_meaning("stock", "🔴")
        assert SC.level_meaning("health", "🟢", key=SS.KEY_HEALTH_A) == \
            SC.level_meaning("health", "🟢")

    def test_every_level_the_stock_lights_emit_has_a_meaning(self):
        """L2 個股燈吐得出來的每一個符號,都要查得到「在這把尺上是什麼意思」。

        查不到 → 明細面板那一行只剩一個裸符號,使用者無從判讀。
        """
        for _g in ("A+", "A", "B+", "B", "C", "F", None, "Z+"):
            for _v in ("improving", "deteriorating", "mixed", "stable", "junk"):
                _sa = ds.assess_stock(
                    ticker="2330", name="t", asset_class=T.ASSET_SATELLITE,
                    mj_grade=_g, mj_score_pct=80, mj_headline="", mj_fail_items=[],
                    kd={"label": "無", "k": 50.0, "d": 50.0},
                    trend={"verdict": _v})
                for _c in ds.light_cells(_sa):
                    _spec = SS.SPECS_BY_KEY[_c.key]
                    assert SC.level_meaning(_spec.group, _c.level, key=_c.key), \
                        f"{_c.key}={_c.level!r} 查不到意思"

    def test_unjudged_text_does_not_lie_about_lights_that_do_have_levels(self):
        """B3:財報體檢 / 財報趨勢**有**自己的等級,只是有時算不出來。

        通用 `UNJUDGED_TEXT` 說「這盞燈從來沒有各自的等級」—— 那句話對這兩盞
        已經是假的(§1)。KD 那一盞才該拿到通用句(它真的沒有判燈邏輯)。
        這條會在「有人日後給 KD 補了等級卻沒改文案」時同樣紅。
        """
        _kd = SC.level_meaning("stock", ds.LEVEL_UNJUDGED, key=SS.KEY_STOCK_KD)
        assert _kd == SC.UNJUDGED_TEXT
        for _k in (SS.KEY_STOCK_HEALTH, SS.KEY_STOCK_TREND):
            _txt = SC.level_meaning("stock", ds.LEVEL_UNJUDGED, key=_k)
            assert _txt and _txt != SC.UNJUDGED_TEXT, f"{_k} 拿到了假敘述"
            assert "從來沒有" not in _txt

    def test_unjudged_meaning_is_not_the_missing_meaning(self):
        """「從來沒判過」與「這輪沒抓到」是兩件事,文案不可共用。"""
        assert SC.UNJUDGED_TEXT != SS.MISS_TEXT[SS.MISS_NO_INPUT]
        assert SC.level_meaning("stock", ds.LEVEL_UNJUDGED) == SC.UNJUDGED_TEXT


# ════════════════════════════════════════════════════════════════
# 四、分母 —— 抓取失敗的列不可縮水
# ════════════════════════════════════════════════════════════════
#
# ⚠️ 原本這一節叫 `TestWatchCount`,測的是 `SC.watch_count`(「N/M 在看」)。
#    該函式 2026-08-26 隨 production caller 歸零而刪除(user 裁示刪死碼),
#    本節**沒有跟著刪掉,而是改測 `judged_count`** —— 它守的那件事
#    (「抓取失敗的列分母不可縮水」)與哪一把尺無關,兩把尺都必須成立。
class TestDenominatorDoesNotShrink:

    def test_denominator_survives_total_fetch_failure(self):
        """抓取失敗的列分母不可縮水(縮水會讓畫面顯示可信度更高,§1)。"""
        _cells = ds.missing_light_cells(T.KIND_ETF, reason=SS.MISS_FETCH_FAILED)
        _n, _m = SC.judged_count(_cells)
        assert _n == 0, "一盞燈都沒跑過的列不准有任何一格算「有判定」"
        assert _m == len(SS.specs_for(T.KIND_ETF)) == 8

    def test_empty_is_zero_zero_not_a_crash(self):
        assert SC.judged_count(()) == (0, 0)
        assert SC.judged_count(None) == (0, 0)
