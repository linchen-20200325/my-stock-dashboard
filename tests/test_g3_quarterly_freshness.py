# -*- coding: utf-8 -*-
"""tests/test_g3_quarterly_freshness.py — 季頻新鮮度:期數規則 + 兩個消費端對帳(G3)。

═══ 這批測試在防什麼 ═══════════════════════════════════════════════════
`STALE_DAYS_QUARTERLY = 150`(v19.127)假設「季報 = 季末 + 45 天公告、每季等距」。
台股不是這樣:公告截止日是**四個固定日曆日**,而且 Q4 差很多 ——

    季別   as_of    法定公告截止      下一份         當期最大 as_of 年齡
    Q1     3/31     5/15   (+45d)    Q2  8/14       136d   ✅ < 150
    Q2     6/30     8/14   (+45d)    Q3  11/14      137d   ✅ < 150
    Q3     9/30     11/14  (+45d)    **年報 次年 3/31**  182d(含鏡像緩衝 196d) 🔴
    Q4     12/31    次年 3/31(+90d)  Q1  5/15       135d   ✅ < 150

Q3 公布後要等 **4.5 個月**才有下一份 ⇒ 每年約 3/02 起,一份**完全當期**的 Q3 財報
就會被 150 天門檻標成過期,一路假紅到年報真的該出來。

影響面比 G2 的月頻嚴重:除了 `health_inspector` 的季頻列(季營收 / EPS / 毛利率 /
存貨 / CapEx / 財報體檢),`ai_qa_service._annotate_staleness` 會把標記注進
**送給 Gemini 的 tool result** ⇒ 每年 3 月,AI 會對一份當期財報說「已過期」,
再據此寫進投資建議。

═══ 寫法(沿用 G2 的規矩)═══════════════════════════════════════════════
- **全部行為斷言**:建輸入 → 呼叫函式 → 驗回傳。無原始碼字面掃描
  (字面守衛照抄實作,實作錯了它也跟著錯)。
- **一律注入 `today`**。少數不注入的,是刻意設計成**與執行日無關**的不變量
  (見 `TestAiQaServiceEndToEnd` 的 docstring:輸入由 `latest_published_quarter(今天)`
  當場推導,故任何一天跑結論都一樣)。
- 同一個函式的多條斷言,都在**同一個 today** 下互相相容(相位不同的斷言各自
  給自己的 today,並在該處寫明為什麼)。
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from shared.data_freshness import (
    freshness_level_for_cadence,
    quarterly_freshness_level,
)
from shared.staleness import (
    QUARTERLY_PUBLICATION_MARGIN_DAYS,
    STALE_DAYS_QUARTERLY,
    TW_QUARTER_STATUTORY_DUE,
    expected_latest_data_quarter,
    latest_published_quarter,
    quarterly_periods_behind,
    quarterly_publication_due,
    quarterly_release_status,
    staleness_days,
)

# ── 季末 as_of(= production 實際餵進來的語意)────────────────────────────
# evidence:`data_loader.get_quarterly_data` / `get_quarterly_bs_cf` 都補
# `date` = 季末(03-31 / 06-30 / 09-30 / 12-31);`financial_statements_fetcher`
# 的 `period` 直接沿用 FinMind 財報 date,同為季末。
_Q3_2025 = "2025-09-30"
_Q4_2025 = "2025-12-31"
_Q1_2026 = "2026-03-31"
_Q2_2026 = "2026-06-30"

#: 台股法定公告截止日的**期望值**在本檔獨立寫一份 —— 日期本身不從
#: `TW_QUARTER_STATUTORY_DUE` 讀,這樣「實作把 11/14 打成 11/15」才會被抓到,
#: 而不是兩邊一起錯。(下方只有 `test_due_table_shape_is_sane` 會碰那張表,
#: 且它驗的是**形狀**(只有 Q4 跨年),不是日期值。)
_STATUTORY = {
    (2025, 3): dt.date(2025, 11, 14),
    (2025, 4): dt.date(2026, 3, 31),      # 年報:次年 3/31
    (2026, 1): dt.date(2026, 5, 15),
    (2026, 2): dt.date(2026, 8, 14),
    (2026, 3): dt.date(2026, 11, 14),
}

_RANK = {"🟢": 0, "⬜": 1, "🟡": 2, "🔴": 3}


# ══════════════════════════════════════════════════════════════════
# A. 要修的病:3 月拿著 Q3 財報
# ══════════════════════════════════════════════════════════════════
class TestQ3FalseRedIsGone:

    def test_march_first_holding_q3_is_green(self):
        """**這就是要修的那條**:2026-03-01 手上是 2025Q3 財報 → 必須 🟢。

        年報(2025Q4)的法定公告截止日是 2026-03-31,3/01 當下它**還沒到期**,
        所以 Q3 就是「市場上存在的最新一份財報」。把它標成過期 = 說謊。
        """
        _today = dt.date(2026, 3, 1)
        _emoji, _label = quarterly_freshness_level(_Q3_2025, today=_today)
        assert _emoji == "🟢", (
            f"2026-03-01 手上的 2025Q3 是當期最新一季"
            f"(年報 {_STATUTORY[(2025, 4)]} 才到期),卻判成 {_emoji} {_label}")
        assert _label == "當期"
        assert quarterly_periods_behind(_Q3_2025, today=_today) == 0

    def test_same_datum_would_have_been_red_under_the_150_day_rule(self):
        """反向釘死舊行為:同一筆當期 Q3,用 150 天門檻量必定紅。

        沒有這條,未來有人把季頻接回 `stale_days_threshold('quarterly')`
        也不會有人發現 —— 而那正是 v19.127 留下的坑。

        ⚠️ 基準日刻意用 2026-03-16 而**不是** 3/01:3/01 是週日,
        `staleness_days` 會退到 2/27(週五)⇒ 年齡恰好 150 = 門檻邊界上,
        舊規則在那一天還是綠的。拿 3/01 去斷言「舊規則是紅的」會自打嘴巴
        (本 session 已出現過測資自相矛盾,故此處把推導寫出來)。
        """
        _today = dt.date(2026, 3, 16)                 # 週一,無週末退位
        _age = staleness_days(_Q3_2025, today=_today)
        assert _age == 167, f"測資年齡算錯:{_age}"
        assert _age > STALE_DAYS_QUARTERLY, "前提:年齡已超過舊門檻"
        assert freshness_level_for_cadence(_age, "quarterly")[0] == "🔴", (
            "舊行為認定:150 天門檻對當期 Q3 判紅")
        assert quarterly_freshness_level(_Q3_2025, today=_today)[0] == "🟢", (
            "修後同一筆資料必須是綠的")

    def test_the_whole_false_red_window_is_gone(self):
        """量出假紅窗口有多寬,並確認新規則在整段窗口內一次都不紅。

        窗口 = 舊規則判紅、但年報(含鏡像緩衝)其實還沒到期的那段日子。
        新規則在窗口內只會是 🟢(年報未到期)或 🟡(過了 3/31 但還在緩衝內),
        **不得**出現 🔴。
        """
        _d = dt.date(2026, 3, 2)
        _end = dt.date(2026, 4, 13)                   # 4/14 = 緩衝用完,該紅了
        _old_red, _new_red, _new_lights = 0, [], set()
        while _d <= _end:
            if freshness_level_for_cadence(
                    staleness_days(_Q3_2025, today=_d), "quarterly")[0] == "🔴":
                _old_red += 1
            _e = quarterly_freshness_level(_Q3_2025, today=_d)[0]
            _new_lights.add(_e)
            if _e == "🔴":
                _new_red.append(_d.isoformat())
            _d += dt.timedelta(days=1)

        assert not _new_red, f"新規則在年報到期前仍判紅:{_new_red[:5]}"
        assert _new_lights <= {"🟢", "🟡"}, f"窗口內出現非預期燈號:{_new_lights}"
        assert _old_red >= 30, (
            f"舊規則在此窗口只紅了 {_old_red} 天 —— 若這個數字掉下來,"
            "代表 `staleness_days` 的基準或 STALE_DAYS_QUARTERLY 被動過,"
            "本測試的前提(舊規則確實每年假紅約一個月)需重新查證")

    def test_first_genuinely_red_day_is_grace_expiry(self):
        """假紅消失不等於永遠不紅:年報真的遲到,還是要紅(§1 不放水)。

        年報法定截止 2026-03-31,鏡像緩衝 14 天 ⇒ 2026-04-14 起算真正落後。
        邊界兩側都測,而不是只測「很久以後會紅」——後者連 off-by-one 都抓不到。
        """
        _due = _STATUTORY[(2025, 4)]
        _first_red = _due + dt.timedelta(days=QUARTERLY_PUBLICATION_MARGIN_DAYS)
        assert _first_red == dt.date(2026, 4, 14), "測資推導錯了,先修測資"
        assert quarterly_freshness_level(
            _Q3_2025, today=_first_red - dt.timedelta(days=1))[0] == "🟡"
        assert quarterly_freshness_level(_Q3_2025, today=_first_red) == (
            "🔴", "落後1期")


# ══════════════════════════════════════════════════════════════════
# B. 三態語意(與 G2 月頻逐字相同)
# ══════════════════════════════════════════════════════════════════
class TestQuarterlyThreeStates:

    def test_missing_a_whole_quarter_is_red(self):
        """漏掉一整季 → 🔴,而且 label 要講「期」不是「天」。

        2026-08-20 還停在 2025Q4(年報):2026Q1 早該在 5/15 公布,
        連 14 天緩衝都過完了(5/29)⇒ 確實漏了一整季。
        """
        _today = dt.date(2026, 8, 20)
        _emoji, _label = quarterly_freshness_level(_Q4_2025, today=_today)
        assert _emoji == "🔴", f"漏一季卻判 {_emoji} {_label}"
        assert _label == "落後1期"
        assert "日" not in _label, (
            f"季頻 label 應以『期』表達(可行動),實得 {_label!r} —— "
            "「落後 232 日」對季報是無意義的數字")

    def test_multiple_missed_quarters_count_up(self):
        """落後期數要真的數對(不是 red/green 兩態拍腦袋)。"""
        _today = dt.date(2026, 8, 20)                 # 預期最新季 = 2026Q1
        for _n, _asof in ((1, _Q4_2025), (2, _Q3_2025),
                          (3, "2025-06-30"), (4, "2025-03-31")):
            assert quarterly_periods_behind(_asof, today=_today) == _n, _asof
            assert quarterly_freshness_level(_asof, today=_today) == (
                "🔴", f"落後{_n}期")

    def test_upstream_late_but_within_grace_is_yellow(self):
        """黃燈有明確語意:下一季**法定截止日已過**、但還在鏡像緩衝內。

        年報原定 2026-03-31 前公布;4/05 當下仍停在 Q3 → 不該直接紅
        (FinMind 鏡像晚 5 天很正常),但也不該純綠。
        """
        _emoji, _label = quarterly_freshness_level(
            _Q3_2025, today=dt.date(2026, 4, 5))
        assert _emoji == "🟡", f"上游遲到 5 天應為 🟡,實得 {_emoji} {_label}"
        assert "5" in _label, f"應告知逾期天數,實得 {_label!r}"
        assert quarterly_release_status(
            _Q3_2025, today=dt.date(2026, 4, 5)) == (0, 5)

    def test_on_the_statutory_deadline_itself_still_green(self):
        """截止日**當天**還不算逾期(黃燈從隔天起算)——與月頻的 off-by-one 一致。"""
        assert quarterly_freshness_level(
            _Q3_2025, today=_STATUTORY[(2025, 4)]) == ("🟢", "當期")
        assert quarterly_freshness_level(
            _Q3_2025, today=_STATUTORY[(2025, 4)] + dt.timedelta(days=1)) == (
                "🟡", "待公布（逾1日）")

    def test_already_red_reports_zero_overdue(self):
        """已經紅了就不再談「逾期幾天」—— 兩種狀態不重疊,避免 UI 同時畫兩種字。"""
        assert quarterly_release_status(
            _Q4_2025, today=dt.date(2026, 8, 20)) == (1, 0)

    def test_data_newer_than_expected_is_still_green(self):
        """公司提前公布(比預期還新)→ 仍是 🟢,不得因為 behind<0 就走怪分支。

        2026-03-31 是年報截止日當天,含緩衝的預期最新季仍是 2025Q3;
        但手上已經有 2025Q4 → behind = −1,必須綠。
        """
        _today = dt.date(2026, 3, 31)
        assert quarterly_periods_behind(_Q4_2025, today=_today) == -1
        assert quarterly_freshness_level(_Q4_2025, today=_today) == ("🟢", "當期")

    @pytest.mark.parametrize("bad", [None, "", "  ", "not-a-date", float("nan")])
    def test_unparsable_asof_is_grey_not_fresh(self, bad):
        """§1:日期讀不出來 ≠ 新鮮。"""
        assert quarterly_freshness_level(bad, today=dt.date(2026, 3, 1)) == (
            "⬜", "未知")
        assert quarterly_periods_behind(bad, today=dt.date(2026, 3, 1)) is None

    def test_monotonic_in_asof(self):
        """單調性:as_of 越舊,燈號只會越差,不會忽紅忽綠。"""
        _today = dt.date(2026, 8, 20)
        _prev, _prev_asof = -1, None
        for _asof in (_Q2_2026, _Q1_2026, _Q4_2025, _Q3_2025,
                      "2025-06-30", "2024-09-30"):
            _e = quarterly_freshness_level(_asof, today=_today)[0]
            assert _RANK[_e] >= _prev, (
                f"as_of {_prev_asof} → {_asof} 燈號竟然變好了({_e})")
            _prev, _prev_asof = _RANK[_e], _asof


# ══════════════════════════════════════════════════════════════════
# C. Q4 / 年報那條 90 天的長窗口不得被誤判
# ══════════════════════════════════════════════════════════════════
class TestAnnualReportLongWindow:
    """年報的公告期限是季末 **+90 天**(不是 +45),而 Q4 之後 Q1 又只隔 45 天。

    這一季的兩端都是「不等距」的極端,最容易被寫成 off-by-one。
    """

    # ⚠️ 5/15 是 🟢 不是 🟡:截止日**當天**還不算逾期,黃燈從隔天起算
    #    (與 `test_on_the_statutory_deadline_itself_still_green` 同一條規則)。
    #    這兩組斷言必須用同一個 off-by-one,否則就是我自己在同一個函式上
    #    寫出互斥預期。
    @pytest.mark.parametrize("today,expect", [
        (dt.date(2026, 1, 15), "🟢"),   # Q4 剛結束,誰都還沒到期
        (dt.date(2026, 3, 31), "🟢"),   # 年報截止日當天(手上已有年報 → 比預期新)
        (dt.date(2026, 5, 14), "🟢"),   # Q1(5/15)還沒到期 → Q4 仍是最新
        (dt.date(2026, 5, 15), "🟢"),   # Q1 截止日當天,尚未逾期
        (dt.date(2026, 5, 16), "🟡"),   # 逾 1 日,鏡像緩衝內
        (dt.date(2026, 5, 28), "🟡"),   # 緩衝最後一天(逾 13 日)
        (dt.date(2026, 5, 29), "🔴"),   # 緩衝用完仍沒有 Q1 → 真的漏了
    ])
    def test_q4_window_walks_green_yellow_red_in_order(self, today, expect):
        _emoji, _label = quarterly_freshness_level(_Q4_2025, today=today)
        assert _emoji == expect, (
            f"{today} 手上 2025Q4(年報):預期 {expect},實得 {_emoji} {_label}"
            f"(下一季 Q1 法定截止 {_STATUTORY[(2026, 1)]}、"
            f"緩衝 {QUARTERLY_PUBLICATION_MARGIN_DAYS} 天)")

    def test_q4_max_current_age_stays_below_the_old_threshold(self):
        """對帳:Q4 當期最大年齡 135 天 < 150 → **Q4 本來就不會踩舊 bug**。

        這條確認「病只出在 Q3」不是猜的:如果哪天有人把年報截止日改成別的月份,
        這條會炸,逼他重新盤點四個季別各自的窗口。
        """
        _age = (_STATUTORY[(2026, 1)] - dt.date(2025, 12, 31)).days
        assert _age == 135
        assert _age < STALE_DAYS_QUARTERLY

    def test_q3_max_current_age_really_exceeds_the_old_threshold(self):
        """對帳另一半:Q3 當期最大年齡 182 天(含緩衝 196)> 150 → 必踩舊 bug。"""
        _statutory = (_STATUTORY[(2025, 4)] - dt.date(2025, 9, 30)).days
        _with_grace = _statutory + QUARTERLY_PUBLICATION_MARGIN_DAYS
        assert (_statutory, _with_grace) == (182, 196)
        assert _statutory > STALE_DAYS_QUARTERLY


# ══════════════════════════════════════════════════════════════════
# D. 法定公告日曆本身 + `latest_published_quarter` 收斂
# ══════════════════════════════════════════════════════════════════
class TestStatutoryCalendarSSOT:

    @pytest.mark.parametrize("asof,due", [
        (_Q1_2026, dt.date(2026, 5, 15)),
        (_Q2_2026, dt.date(2026, 8, 14)),
        (_Q3_2025, dt.date(2025, 11, 14)),
        (_Q4_2025, dt.date(2026, 3, 31)),      # 年報跨年
    ])
    def test_publication_due_matches_statute(self, asof, due):
        """四個法定公告截止日逐一對帳(本檔的期望值獨立寫,不 import 實作的表)。"""
        assert quarterly_publication_due(asof) == due

    def test_due_table_shape_is_sane(self):
        """只有 Q4 跨年(位移 1),其餘皆同年 —— 這是「不等距」的來源。"""
        assert sorted(TW_QUARTER_STATUTORY_DUE) == [1, 2, 3, 4]
        assert [TW_QUARTER_STATUTORY_DUE[s][0] for s in (1, 2, 3, 4)] == [0, 0, 0, 1]

    @pytest.mark.parametrize("today,expect", [
        (dt.date(2026, 1, 1), (114, 3)),
        (dt.date(2026, 3, 30), (114, 3)),
        (dt.date(2026, 3, 31), (114, 4)),      # 年報截止日當天 → 換季
        (dt.date(2026, 5, 14), (114, 4)),
        (dt.date(2026, 5, 15), (115, 1)),
        (dt.date(2026, 8, 13), (115, 1)),
        (dt.date(2026, 8, 14), (115, 2)),
        (dt.date(2026, 11, 13), (115, 2)),
        (dt.date(2026, 11, 14), (115, 3)),
        (dt.date(2026, 12, 31), (115, 3)),
        (dt.date(2027, 1, 1), (115, 3)),       # 跨年不換季(年報 3/31 才出)
    ])
    def test_latest_published_quarter_boundaries(self, today, expect):
        """`latest_published_quarter` 回**民國年**,每個截止日兩側都測。"""
        assert latest_published_quarter(today) == expect

    def test_latest_published_quarter_matches_the_scripts_copy(self):
        """漂移守衛(行為,非字面):`scripts/` 的私有同名實作必須逐日等值。

        L0 SSOT 已建在 `shared/staleness.py`,但 `scripts/update_fundamentals_snapshot.py`
        仍持有一份逐字等價的複本(該檔不在 G3 可改範圍)。**兩份會漂**,而漂掉的
        後果是「補抓哪一季」與「這一季新不新鮮」給出互相矛盾的答案。
        這條掃一整年逐日比對 —— scripts 那支改吃 L0 之後,本條依然成立(且變成廢話,
        那時可以刪);在它還沒改之前,本條就是唯一的防線。
        """
        from scripts.update_fundamentals_snapshot import (
            latest_published_quarter as _scripts_lpq,
        )

        _bad = []
        _d = dt.date(2025, 12, 1)
        for _ in range(500):
            if latest_published_quarter(_d) != _scripts_lpq(_d):
                _bad.append((_d.isoformat(), latest_published_quarter(_d),
                             _scripts_lpq(_d)))
            _d += dt.timedelta(days=1)
        assert not _bad, (
            f"L0 SSOT 與 scripts 私有複本已漂移,反例 (日期, L0, scripts) = {_bad[:5]}")

    def test_expected_quarter_is_the_quarter_end_of_latest_published(self):
        """兩個入口必須指向同一季:`expected_latest_data_quarter(grace=0)` 的季末
        就是 `latest_published_quarter` 那一季 —— 否則 UI 與 cron 會各認一季。"""
        _d = dt.date(2026, 1, 1)
        for _ in range(400):
            _roc, _season = latest_published_quarter(_d)
            _end = expected_latest_data_quarter(today=_d, grace_days=0)
            assert (_end.year - 1911, (_end.month - 1) // 3 + 1) == (_roc, _season), _d
            _d += dt.timedelta(days=1)


# ══════════════════════════════════════════════════════════════════
# E. 邊界輸入(§6 最容易出錯的三種)
# ══════════════════════════════════════════════════════════════════
class TestEdgeInputs:

    @pytest.mark.parametrize("asof", ["2025-09-30", "2025-09-15", "2025-07-01",
                                      "2025-08-31"])
    def test_any_day_inside_a_quarter_maps_to_that_quarter(self, asof):
        """as_of 不必剛好是季末:季內任一天都要判進同一季。

        來源差異(MOPS 用公告日、FinMind 用季末)不該讓同一季變成兩種燈號。
        """
        _today = dt.date(2026, 3, 1)
        assert quarterly_freshness_level(asof, today=_today) == ("🟢", "當期")

    def test_dataframe_input_uses_the_max_date(self):
        """健診頁餵的是 DataFrame 的最新一列(`_last_date_col`),要吃得下。"""
        pd = pytest.importorskip("pandas")
        _df = pd.DataFrame({"date": ["2025-03-31", "2025-06-30", _Q3_2025],
                            "EPS": [1.0, 2.0, 3.0]})
        assert quarterly_freshness_level(_df, today=dt.date(2026, 3, 1)) == (
            "🟢", "當期")

    def test_year_boundary_does_not_skip_a_quarter(self):
        """跨年不得漏季:逐日走過 2025-11 → 2026-06,期序只准遞增 0 或 1。"""
        _prev, _d = None, dt.date(2025, 11, 1)
        for _ in range(250):
            _cur = expected_latest_data_quarter(today=_d, grace_days=0)
            if _prev is not None:
                _step = ((_cur.year * 4 + (_cur.month - 1) // 3)
                         - (_prev.year * 4 + (_prev.month - 1) // 3))
                assert _step in (0, 1), f"{_d}: 預期季別跳了 {_step} 季({_prev}→{_cur})"
            _prev, _d = _cur, _d + dt.timedelta(days=1)


# ══════════════════════════════════════════════════════════════════
# F. health_inspector(🔎 原始資料健診)—— 端到端行為
# ══════════════════════════════════════════════════════════════════
class TestHealthInspectorPage:

    def test_march_first_holding_q3_is_green_on_the_page_too(self):
        from src.ui.pages.health_inspector import freshness_light

        assert freshness_light(_Q3_2025, 'quarterly',
                               today=dt.date(2026, 3, 1))[0] == '🟢'

    def test_quarterly_has_no_calendar_day_band(self):
        """季頻不得再有日曆天門檻(對齊 G2 對月頻的處置)。"""
        from src.ui.pages.health_inspector import freshness_bands

        with pytest.raises(ValueError):
            freshness_bands('quarterly')

    @pytest.mark.parametrize("asof", [_Q1_2026, _Q4_2025, _Q3_2025, "2025-06-30"])
    @pytest.mark.parametrize("today", [dt.date(2026, 3, 1), dt.date(2026, 4, 5),
                                       dt.date(2026, 8, 20)])
    def test_page_output_is_identical_to_the_shared_rule(self, asof, today):
        """健診頁的季頻輸出必須**逐字**等於共用規則 —— 不是「都紅就好」。"""
        from src.ui.pages.health_inspector import freshness_light

        _rule = quarterly_freshness_level(asof, today=today)
        _page = freshness_light(asof, 'quarterly', today=today)
        assert _rule == _page, (
            f"as_of={asof} today={today}:共用規則給 {_rule},"
            f"health_inspector 給 {_page} —— 同一筆資料不得有兩種說法")

    def test_daily_and_yearly_rows_untouched(self):
        """G3 只動季頻:日頻 / 年頻的門檻來源不得被順手改掉。"""
        from shared.staleness import stale_days_threshold
        from src.ui.pages.health_inspector import freshness_bands

        assert freshness_bands('daily')[1] == stale_days_threshold('daily')
        assert freshness_bands('yearly') == (370, 400)


# ══════════════════════════════════════════════════════════════════
# G. ai_qa_service —— 注給 Gemini 的那份 dict
# ══════════════════════════════════════════════════════════════════
def _payload_text(result: dict) -> str:
    """模擬 `_run_tool` 之後送進 Gemini 的字面(`json.dumps` 整包 tool result)。"""
    return json.dumps(result, ensure_ascii=False)


class TestAiQaServiceAnnotation:

    def test_current_quarter_gets_no_stale_marker_at_all(self):
        """**這是 G3 最要命的一條**:每年 3 月,AI 會對一份當期 Q3 說「已過期」。

        斷言的是**送進 payload 的字面**,不是某個內部旗標 —— 模型看得到的只有
        這串字。任何 stale / 過期 字樣都不得出現。
        """
        from src.services.ai_qa_service import _annotate_staleness

        _r = _annotate_staleness(
            {"ok": True, "data": {"EPS": 3.36},
             "provenance": {"source": "FinMind 季報", "as_of": _Q3_2025,
                            "cadence": "quarterly"}},
            today=dt.date(2026, 3, 1))
        _txt = _payload_text(_r)
        assert "_stale_days" not in _r, f"當期 Q3 被標過期天數:{_r}"
        assert "_stale_quarters" not in _r
        assert "stale" not in _txt.lower(), f"payload 仍帶過期字樣:{_txt}"
        assert "過期" not in _txt

    def test_truly_behind_quarter_is_still_flagged_in_periods(self):
        """§1 不放水:真的漏了一整季仍須標記,且要給**期數**(可行動)。"""
        from src.services.ai_qa_service import _annotate_staleness

        _today = dt.date(2026, 8, 20)
        _r = _annotate_staleness(
            {"ok": True, "data": {"EPS": 1.0},
             "provenance": {"as_of": _Q4_2025, "cadence": "quarterly"}},
            today=_today)
        assert _r["_stale_quarters"] == 1
        assert _r["_stale_days"] == (_today - dt.date(2025, 12, 31)).days == 232

    def test_daily_cadence_behaviour_is_unchanged(self):
        """日頻(未宣告 cadence → default daily)維持 7d 門檻,不得被順手改掉。"""
        from shared.staleness import stale_days_threshold
        from src.services.ai_qa_service import _annotate_staleness

        _today = dt.date(2026, 8, 20)
        _bad = stale_days_threshold("daily")
        _fresh = (_today - dt.timedelta(days=_bad)).isoformat()
        _stale = (_today - dt.timedelta(days=_bad + 1)).isoformat()
        assert "_stale_days" not in _annotate_staleness(
            {"ok": True, "data": {"x": 1}, "provenance": {"as_of": _fresh}},
            today=_today)
        assert _annotate_staleness(
            {"ok": True, "data": {"x": 1}, "provenance": {"as_of": _stale}},
            today=_today)["_stale_days"] == _bad + 1

    def test_quarterly_never_flagged_by_day_count_alone(self):
        """季頻不得再有任何「天數超過 N 就標」的殘留路徑。

        掃一整年:凡是**期數判定為當期**的日子,一律不得出現 stale 標記 ——
        即使那天的 as_of 年齡是 196 天(Q3 的合法上限)。
        """
        from src.services.ai_qa_service import _annotate_staleness

        _bad = []
        _d = dt.date(2026, 1, 1)
        for _ in range(365):
            for _asof in (_Q3_2025, _Q4_2025, _Q1_2026, _Q2_2026):
                _behind = quarterly_periods_behind(_asof, today=_d)
                _r = _annotate_staleness(
                    {"ok": True, "data": {},
                     "provenance": {"as_of": _asof, "cadence": "quarterly"}},
                    today=_d)
                _flagged = "_stale_days" in _r or "_stale_quarters" in _r
                if _flagged != (_behind >= 1):
                    _bad.append((_d.isoformat(), _asof, _behind, _flagged))
            _d += dt.timedelta(days=1)
        assert not _bad, (
            "標記與期數判定不一致,反例 (today, as_of, periods_behind, flagged) = "
            f"{_bad[:5]}")


class TestAiQaServiceEndToEnd:
    """走真正的 `_run_tool` 路徑(它**不**接受 today,production 就是吃當天)。

    為了不讓斷言隨執行日飄,輸入由 `latest_published_quarter(今天)` **當場推導**:
      - 「當下法定上應已公布的那一季」→ 依定義必為當期 ⇒ **任何一天都不得被標記**;
      - 「再往前兩季」→ 鏡像緩衝最多只讓預期季別退一季 ⇒ **任何一天都必被標記**。
    兩條都是與日期無關的不變量,不是「今天剛好成立」。
    """

    @staticmethod
    def _quarter_end(roc_year: int, season: int) -> str:
        _y = roc_year + 1911
        return dt.date(_y, season * 3,
                       {1: 31, 2: 30, 3: 30, 4: 31}[season]).isoformat()

    @classmethod
    def _shift(cls, roc_year: int, season: int, back: int) -> str:
        _i = (roc_year + 1911) * 4 + (season - 1) - back
        return cls._quarter_end(_i // 4 - 1911, _i % 4 + 1)

    def test_latest_published_quarter_is_never_flagged(self):
        from src.services.ai_qa_service import _run_tool

        _calls = []

        def _fake_tool():
            _calls.append(1)
            _roc, _s = latest_published_quarter(dt.date.today())
            return {"ok": True, "data": {"EPS": 1.0},
                    "provenance": {"as_of": self._quarter_end(_roc, _s),
                                   "cadence": "quarterly"}}

        _out = _run_tool({"fin": _fake_tool}, "fin", {})
        assert _calls, "假工具沒有被呼叫 —— 這條測試等於什麼都沒驗"
        assert "_stale_days" not in _out and "_stale_quarters" not in _out, _out
        assert "stale" not in json.dumps(_out, ensure_ascii=False).lower()

    def test_two_quarters_back_is_always_flagged(self):
        from src.services.ai_qa_service import _run_tool

        _calls = []

        def _fake_tool():
            _calls.append(1)
            _roc, _s = latest_published_quarter(dt.date.today())
            return {"ok": True, "data": {"EPS": 1.0},
                    "provenance": {"as_of": self._shift(_roc, _s, 2),
                                   "cadence": "quarterly"}}

        _out = _run_tool({"fin": _fake_tool}, "fin", {})
        assert _calls, "假工具沒有被呼叫 —— 這條測試等於什麼都沒驗"
        assert _out.get("_stale_quarters", 0) >= 1, _out
