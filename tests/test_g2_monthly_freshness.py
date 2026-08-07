# -*- coding: utf-8 -*-
"""tests/test_g2_monthly_freshness.py — 月頻新鮮度:期數規則 + 三頁燈號對帳(G2)。

═══ 這批測試在防什麼 ═══════════════════════════════════════════════════
B4-a(v19.182)把 `data_coverage` 的月頻紅燈接上 `stale_days_threshold('monthly')`
= 45 天。但 `macro_info` 月頻指標的 `date` 是**資料月月初**
(PMI/CPI/出口/NDC/Fed 全部),當期最新一筆的 as_of 年齡天生就是 63~89 天
⇒ **健康狀態下這一列每天都是 🔴**。一個 100% 觸發的警告等於沒有警告。

G2 的修法不是「把 45 調大」,而是換掉量法:月頻改判
「as_of 距**預期最新資料月**落後幾個發布期」。理由見
`shared/staleness.py` 的 G2 區塊 —— 任何日曆天門檻都會二選一:
  設小 → 當期假紅;設大 → 漏一整期卻假綠(短月組合 59 天 < 門檻 62+lag)。

═══ 寫法 ═══════════════════════════════════════════════════════════════
- **全部行為斷言**:建輸入 → 呼叫函式 → 驗回傳燈號。無原始碼字面掃描
  (字面守衛照抄實作,實作錯了它也跟著錯 —— 本 session 已被這種假紅燈擋 9 次)。
- **一律注入 `today`**;唯一例外是 `data_registry_panel._freshness_emoji`,
  它內部寫死 `date.today()`(不在本輪可改範圍),故該組測試改用
  「相對天數 + 與另一把尺同基準」的斷言,結論不依賴執行當天是哪一天
  (推導見 `TestThreeRulersOnTheSameDatum` 的 docstring)。
"""
from __future__ import annotations

import datetime as dt

import pytest

from shared.data_freshness import (
    freshness_level,
    freshness_level_for_cadence,
    monthly_freshness_level,
)
from shared.staleness import (
    MACRO_PUBLICATION_LAG_DAYS,
    MONTHLY_PUBLICATION_MARGIN_DAYS,
    expected_latest_data_month,
    monthly_periods_behind,
    monthly_release_status,
    monthly_stale_threshold,
    staleness_days,
)

# 固定基準日(2026-08-07,週五)—— 與 tests/test_g1_llm_stale_tagging.py 同一天,
# 兩批測試對同一筆 as_of 的判定必須相容(本 session 已出現過兩個 agent 對同一
# 對象寫出互斥預期,故刻意對齊)。
_TODAY = dt.date(2026, 8, 7)

#: macro_info 的 5 個月頻 key(vix 是日頻,不在此列)
_MACRO_MONTHLY_KEYS = ("us_core_cpi", "ism_pmi", "tw_export",
                       "ndc_signal", "fed_funds")

#: 2026-08-07 當下,五個指標的 as_of 都仍是 6 月(下一期尚未「連緩衝都過完」)。
#: 但 8/07 **不是**「五個都純綠」的日子 —— 見下方 `_today_current()`。
_CURRENT_ASOF = "2026-06-01"
#: 再往前一個月 = 確定漏掉一整期
_MISSED_ASOF = "2026-05-01"

_RANK = {"🟢": 0, "⬜": 1, "🟡": 2, "🔴": 3}


def _today_current(key: str) -> dt.date:
    """回一個「6 月資料純綠」的基準日:下一期**連原定發布日都還沒到**。

    ⚠️ 為什麼不能五個指標共用一個 `_TODAY`(原測資的錯)
    ────────────────────────────────────────────────────
    三態語意是:
        🟢 下期尚未到原定發布日            (t < (M+2)/01 + lag)
        🟡 原定發布日已過、還在緩衝內       (+0 ~ +margin)
        🔴 連緩衝都過完 = 真的漏掉一期      (> +margin)

    原測資把 `_TODAY = 8/07` 套在五個指標上,並在註解裡算出
    「7 月號應發布日(含緩衝)PMI 8/09、Fed 8/13…全都晚於 8/07」→ 判定全綠。
    **但 8/09 是緩衝期的結束,不是開始** —— PMI 的原定發布日是 8/02,
    8/07 當下它已經進入 🟡 待公布(逾5日),Fed 是 8/06(逾1日)。實作沒錯,
    是測資把「還沒紅」讀成「還是綠」。

    更根本的是:五個指標的發布延遲從 1 天(PMI)到 27 天(NDC),相位不重疊。
    實測**不存在任何一天**同時滿足「五個都 🟢」與「五個的 2026-05-01 都算落後
    一期」—— 前者要求 t < 8/02(PMI 綁),後者要求 t ≥ 8/04(NDC 綁)。
    把五條不同排程當成同一條 parametrize,本身就是無解的測資設計。

    故「當期必綠」這組改用**逐指標**基準日;「漏一期必紅」那組維持 `_TODAY`
    (8/07 對五個指標都已越過各自的 6 月 graced due,May 一律算落後一期)。
    """
    return dt.date(2026, 8, 1) + dt.timedelta(
        days=MACRO_PUBLICATION_LAG_DAYS[key] - 1)


#: 「五個同時純綠」唯一可行的日子(PMI 原定發布日 8/02 的前一天)。
#: NDC 在此日的預期最新資料月是 5 月,6 月資料 = 比預期還新 → periods_behind=-1 → 仍綠。
_TODAY_ALL_GREEN = dt.date(2026, 8, 1)


# ══════════════════════════════════════════════════════════════════
# A. 規則本體(L0):當期不得紅 / 漏一期必須紅
# ══════════════════════════════════════════════════════════════════
class TestMonthlyRuleCore:

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_current_release_is_green(self, key):
        """當期最新一筆(2026-06-01)→ 🟢,**不得**亮紅。

        這就是 G2 要修的病:同一筆資料在舊碼(45 天門檻)是 🔴。
        """
        _t = _today_current(key)
        _emoji, _label = monthly_freshness_level(
            _CURRENT_ASOF, indicator=key, today=_t)
        assert _emoji == "🟢", (
            f"{key} as_of={_CURRENT_ASOF} 在 {_t} 是當期最新一筆"
            f"(下一期原定發布日 {dt.date(2026, 8, 1) + dt.timedelta(days=MACRO_PUBLICATION_LAG_DAYS[key])}"
            f" 都還沒到),卻判成 {_emoji} {_label}")

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_current_release_would_have_been_red_under_45d(self, key):
        """反向釘死舊行為:同一筆當期資料,用 45 天門檻量必定紅。

        沒有這條,未來有人把月頻接回 `stale_days_threshold('monthly')`
        也不會有人發現 —— 而那正是 B4-a 留下的坑。
        """
        _t = _today_current(key)
        _age = staleness_days(_CURRENT_ASOF, today=_t)
        assert _age is not None and _age > 45, "測資年齡算錯,先修測資"
        assert freshness_level_for_cadence(_age, "monthly")[0] == "🔴", (
            "舊行為認定:45 天門檻對當期資料判紅")
        assert monthly_freshness_level(
            _CURRENT_ASOF, indicator=key, today=_t)[0] == "🟢"

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_one_missed_release_is_red(self, key):
        """漏掉一整期 → 必須 🔴,而且 label 要講「期」不是「天」。"""
        _emoji, _label = monthly_freshness_level(
            _MISSED_ASOF, indicator=key, today=_TODAY)
        assert _emoji == "🔴", f"{key} 漏一期卻判 {_emoji} {_label}"
        assert "期" in _label, (
            f"月頻 label 應以『期』表達(可行動),實得 {_label!r} —— "
            "「落後 98 日」對月頻資料是無意義的數字")
        assert monthly_periods_behind(
            _MISSED_ASOF, indicator=key, today=_TODAY) == 1

    def test_multiple_missed_releases_count_up(self):
        """落後期數要真的數對(不是 red/green 兩態拍腦袋)。"""
        for _months, _asof in ((2, "2026-04-01"), (3, "2026-03-01"),
                               (4, "2026-02-01")):
            assert monthly_periods_behind(
                _asof, indicator="us_core_cpi", today=_TODAY) == _months
            assert monthly_freshness_level(
                _asof, indicator="us_core_cpi", today=_TODAY) == (
                    "🔴", f"落後{_months}期")

    def test_data_newer_than_expected_is_still_green(self):
        """比預期還新(上游提前公布)→ 仍是 🟢,不得因為 behind<0 就走怪分支。"""
        assert monthly_freshness_level(
            "2026-07-01", indicator="ism_pmi", today=_TODAY) == ("🟢", "當期")
        assert monthly_periods_behind(
            "2026-07-01", indicator="ism_pmi", today=_TODAY) == -1

    def test_upstream_late_but_within_grace_is_yellow(self):
        """黃燈有明確語意:下一期**原定發布日已過**、但還在緩衝內。

        台灣 PMI(lag=1):7 月 PMI 原定 8/02 前公布,緩衝到 8/09。
        8/05 當下仍停在 6 月資料 → 不該直接紅(來源遲 3 天),但也不該純綠。
        """
        _emoji, _label = monthly_freshness_level(
            _CURRENT_ASOF, indicator="ism_pmi", today=dt.date(2026, 8, 5))
        assert _emoji == "🟡", f"上游遲到 3 天應為 🟡,實得 {_emoji} {_label}"
        assert "3" in _label, f"應告知逾期天數,實得 {_label!r}"

    def test_grace_expiry_flips_yellow_to_red(self):
        """緩衝用完仍沒有新的一期 → 必須翻紅(黃燈不是永久免死金牌)。

        台灣 PMI(lag=1):7 月資料原定 8/02 公布,緩衝 7 天 ⇒ 8/09 起算真正逾期。
        邊界兩側都測,而不是只測「很久以後會紅」——後者連 off-by-one 都抓不到。
        """
        _lag = MACRO_PUBLICATION_LAG_DAYS["ism_pmi"]
        _due = dt.date(2026, 8, 1) + dt.timedelta(days=_lag)          # 8/02
        _first_red = _due + dt.timedelta(days=MONTHLY_PUBLICATION_MARGIN_DAYS)
        assert _first_red == dt.date(2026, 8, 9), "測資推導錯了,先修測資"
        assert monthly_freshness_level(
            _CURRENT_ASOF, indicator="ism_pmi",
            today=_first_red - dt.timedelta(days=1))[0] == "🟡"
        assert monthly_freshness_level(
            _CURRENT_ASOF, indicator="ism_pmi", today=_first_red)[0] == "🔴"

    def test_unregistered_indicator_is_grey_not_guessed(self):
        """§1:未登錄發布延遲 → ⬜「門檻未登錄」,**不得**猜一個門檻。

        猜綠 = 掩蓋(把可能過期的資料講成新鮮);猜紅 = 假警報。
        兩個都不行,唯一誠實的答案是「我判不出來」。
        """
        _emoji, _label = monthly_freshness_level(
            _CURRENT_ASOF, indicator="沒登錄的指標", today=_TODAY)
        assert _emoji == "⬜", f"未登錄卻給了燈號 {_emoji} {_label}"
        assert _label == "門檻未登錄"
        # 沒給 indicator 也一樣(不得靜默退回某個預設 lag)
        assert monthly_freshness_level(_CURRENT_ASOF, today=_TODAY)[0] == "⬜"

    @pytest.mark.parametrize("bad", [None, "", "  ", "not-a-date", float("nan")])
    def test_unparsable_asof_is_grey_not_fresh(self, bad):
        """§1:日期讀不出來 ≠ 新鮮。且要與「門檻未登錄」分得開(修法不同)。"""
        _emoji, _label = monthly_freshness_level(
            bad, indicator="us_core_cpi", today=_TODAY)
        assert _emoji == "⬜"
        assert _label == "未知", f"日期不可解析卻回 {_label!r}(應與門檻問題區分)"

    def test_month_only_string_is_accepted(self):
        """出口來源回的是 'YYYY-MM'(見 macro_snapshot 出口 5 段)—— 必須吃得下。"""
        assert monthly_freshness_level(
            "2026-06", indicator="tw_export", today=_TODAY) == ("🟢", "當期")

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_monotonic_in_asof(self, key):
        """單調性:as_of 越舊,燈號只會越差,不會忽紅忽綠。"""
        _prev, _prev_asof = -1, None
        for _asof in ("2026-07-01", "2026-06-01", "2026-05-01",
                      "2026-03-01", "2025-08-01"):
            _e = monthly_freshness_level(_asof, indicator=key, today=_TODAY)[0]
            _r = _RANK[_e]
            assert _r >= _prev, (
                f"{key}: as_of {_prev_asof} → {_asof} 燈號竟然變好了({_e})")
            _prev, _prev_asof = _r, _asof

    def test_conflicting_lag_inputs_raise(self):
        """同時給 indicator 與 lag_days = 語意衝突,不猜(§1)。"""
        with pytest.raises(ValueError):
            monthly_periods_behind(_CURRENT_ASOF, indicator="ism_pmi",
                                   lag_days=5, today=_TODAY)

    def test_release_status_reports_zero_overdue_when_red(self):
        """已經紅了就不再談「逾期幾天」—— 兩種狀態不重疊,避免 UI 同時畫兩種字。"""
        assert monthly_release_status(
            _MISSED_ASOF, indicator="us_core_cpi", today=_TODAY) == (1, 0)


# ══════════════════════════════════════════════════════════════════
# B. 期數規則 vs 日曆天投影:差異是刻意的,而且方向固定
# ══════════════════════════════════════════════════════════════════
class TestPeriodRuleVsCalendarDayProjection:
    """`monthly_stale_threshold`(天)是 `monthly_periods_behind`(期)的保守投影。

    兩者不是兩把互相打架的尺,而是同一條規則的精確版與投影版:
      - 投影版只在「呼叫端手上只有天數」時用(prompt 標記 `[STALE:Nd]`);
      - 方向固定:**投影版只會偏綠,永遠不會比期數規則更嚴**。
    這兩條在下面被機器釘住,所以「為什麼兩處數字不同」不必靠讀註解。
    """

    def test_calendar_day_projection_has_a_false_green_window(self):
        """實例:短月組合會讓日曆天規則說「還新鮮」,但其實已漏一整期。

        今天 2026-03-10,台灣 PMI 停在 2026-01-01:
          - 2 月 PMI 原定 3/01 + lag(1) 公布,緩衝到 3/08 → 3/10 已確定漏掉;
          - 但 as_of 年齡只有 68 天 < 門檻 70 天 → 日曆天規則判「當期」。
        這正是「把門檻調大」解不掉的另一半,也是本檔改判期數的理由。
        """
        _today = dt.date(2026, 3, 10)
        _asof = "2026-01-01"
        _age = staleness_days(_asof, today=_today)
        assert _age == 68, f"測資年齡算錯:{_age}"
        assert _age < monthly_stale_threshold("ism_pmi"), "前提:天數未達門檻"
        assert monthly_periods_behind(
            _asof, indicator="ism_pmi", today=_today) == 1, "但確實漏了一期"
        assert monthly_freshness_level(
            _asof, indicator="ism_pmi", today=_today)[0] == "🔴"

    @pytest.mark.parametrize("key", sorted(MACRO_PUBLICATION_LAG_DAYS))
    def test_day_projection_never_stricter_than_period_rule(self, key):
        """property:日曆天投影判過期 ⇒ 期數規則也判過期(反向不成立)。

        掃一整年的 (today, as_of) 組合。若哪天有人把 62 / margin 動壞,
        方向性一破,這條會炸並印出反例。
        """
        _th = monthly_stale_threshold(key)
        _bad = []
        for _dd in range(0, 365, 7):
            _today = dt.date(2026, 1, 1) + dt.timedelta(days=_dd)
            for _back in range(0, 13):
                _asof = dt.date(_today.year, _today.month, 1)
                _asof = _asof.replace(year=_asof.year - (1 if _back >= _asof.month else 0),
                                      month=(_asof.month - _back - 1) % 12 + 1)
                _age = (_today - _asof).days
                _day_stale = _age > _th
                _period_stale = monthly_periods_behind(
                    _asof, indicator=key, today=_today) >= 1
                if _day_stale and not _period_stale:
                    _bad.append((_today.isoformat(), _asof.isoformat(), _age))
        assert not _bad, (
            f"{key}: 日曆天投影比期數規則更嚴(方向反了),反例 "
            f"(today, as_of, age) = {_bad[:5]}")


# ══════════════════════════════════════════════════════════════════
# C. data_coverage(🔎 資料診斷 ⓪ 表)—— 端到端行為
# ══════════════════════════════════════════════════════════════════
def _cover(state, today=_TODAY):
    from src.ui.pages.data_coverage import compute_tab_coverage
    return compute_tab_coverage(state=state, today=today)


def _macro_row(state, today=_TODAY):
    return next(r for r in _cover(state, today) if "總經" in r["tab"])


class TestDataCoveragePage:

    @staticmethod
    def _state(**blocks):
        _mi = {"_loaded_at": "2026-08-07 09:00:00"}
        _mi.update(blocks)
        return {"macro_info": _mi}

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_current_monthly_indicator_does_not_turn_the_row_red(self, key):
        """B4-a 的假紅:當期最新一筆讓整列 🌍 總經 恆紅。"""
        _r = _macro_row(self._state(**{key: {"value": 1.0, "date": _CURRENT_ASOF}}),
                        today=_today_current(key))
        assert _r["fresh_emoji"] == "🟢", (
            f"{key} 當期資料把總經列判成 {_r['fresh_emoji']} {_r['fresh_label']}")
        assert "當期" in _r["fresh_label"]

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_missed_release_turns_the_row_red_and_names_the_key(self, key):
        _r = _macro_row(self._state(**{key: {"value": 1.0, "date": _MISSED_ASOF}}))
        assert _r["fresh_emoji"] == "🔴"
        assert key in _r["fresh_label"], (
            f"紅燈沒指名是哪個指標:{_r['fresh_label']!r}")

    def test_healthy_full_macro_board_is_green(self):
        """六個 key 全部當期(vix 日頻當日 + 五個月頻 6 月)→ 整列必須綠。

        這是 user 每天看到的正常狀態;G2 之前它每天都是 🔴。
        """
        _blocks = {k: {"value": 1.0, "date": _CURRENT_ASOF}
                   for k in _MACRO_MONTHLY_KEYS}
        _blocks["vix"] = {"current": 18.2,
                          "date": _TODAY_ALL_GREEN.strftime("%Y-%m-%d")}
        # 整列 = 取最差,故必須用**五個同時純綠**的那一天(見 `_today_current` docstring:
        # 8/07 當下 PMI/Fed 已進入 🟡 待公布,整列會被它們拉黃 —— 那是正確行為,
        # 不是 bug,所以這條測試要改基準日而不是改實作)。
        _r = _macro_row(self._state(**_blocks), today=_TODAY_ALL_GREEN)
        assert _r["fresh_emoji"] == "🟢", (
            f"健康狀態下總經列仍是 {_r['fresh_emoji']} {_r['fresh_label']}")

    def test_worst_indicator_still_drives_the_row(self):
        """一個月頻漏期 + 其餘全當期 → 整列必須跟著最差的走(不得被平均掉)。"""
        _blocks = {k: {"value": 1.0, "date": _CURRENT_ASOF}
                   for k in _MACRO_MONTHLY_KEYS}
        _blocks["ndc_signal"] = {"value": 1.0, "date": "2026-02-01"}
        _r = _macro_row(self._state(**_blocks))
        assert _r["fresh_emoji"] == "🔴"
        assert "ndc_signal" in _r["fresh_label"]

    def test_daily_key_still_uses_the_daily_rule(self):
        """月頻改期數規則不得波及日頻:vix 落後 30 天仍須紅。"""
        _r = _macro_row(self._state(
            vix={"current": 18.2, "date": (_TODAY - dt.timedelta(days=30)).isoformat()}))
        assert _r["fresh_emoji"] == "🔴"
        assert "30" in _r["fresh_label"], "日頻仍應以『日』表達"

    def test_fetch_time_still_does_not_change_the_light(self):
        """D-2 的保護不得被 G2 弄丟:抓取時間變化不得影響月頻燈號。"""
        _lights = set()
        for _lt in ("2020-01-01 00:00:00", "2026-08-07 09:00:00", ""):
            _mi = {"us_core_cpi": {"yoy": 3.1, "date": _CURRENT_ASOF},
                   "_loaded_at": _lt}
            _lights.add(_macro_row({"macro_info": _mi})["fresh_emoji"])
        assert len(_lights) == 1, f"抓取時間影響了月頻燈號:{_lights}"

    def test_every_monthly_key_has_a_registered_publication_lag(self):
        """漂移守衛(資料一致性,非字面):標 monthly 的 key 必須登錄發布延遲。

        漏登 → 該格顯示 ⬜「門檻未登錄」,燈號靜默失效。這條讓漏登在 CI 就炸。
        """
        from src.ui.pages.data_coverage import _MACRO_KEY_CADENCE

        _missing = sorted(k for k, c in _MACRO_KEY_CADENCE.items()
                          if c == "monthly" and k not in MACRO_PUBLICATION_LAG_DAYS)
        assert not _missing, (
            f"這些 key 標了 monthly 卻沒登錄發布延遲:{_missing} —— "
            "請在 shared/staleness.MACRO_PUBLICATION_LAG_DAYS 補一筆")


# ══════════════════════════════════════════════════════════════════
# D. health_inspector(🔎 原始資料健診)—— 端到端行為
# ══════════════════════════════════════════════════════════════════
class TestHealthInspectorPage:

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_current_release_is_green(self, key):
        from src.ui.pages.health_inspector import freshness_light
        # 逐指標基準日,理由同 `_today_current` docstring:8/07 當下 PMI(原定 8/02)
        # 與 Fed(8/06)已進入 🟡 待公布,那是正確行為,不是 health_inspector 的 bug。
        assert freshness_light(_CURRENT_ASOF, 'monthly',
                               today=_today_current(key), indicator=key)[0] == '🟢'

    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_missed_release_is_red_not_yellow(self, key):
        """舊碼的 90/120 帶會把「漏掉一整期」畫成 🟡 —— 那是低報,不是寬鬆。"""
        from src.ui.pages.health_inspector import freshness_light

        _age = staleness_days(_MISSED_ASOF, today=_TODAY)
        assert freshness_level(_age, warn=90, bad=120)[0] == '🟡', (
            "舊行為認定:90/120 帶對漏一期的資料只給黃燈")
        assert freshness_light(_MISSED_ASOF, 'monthly',
                               today=_TODAY, indicator=key)[0] == '🔴'

    def test_monthly_without_indicator_is_grey(self):
        """沒指名序列 → ⬜,不得退回猜一個門檻(否則等於第四把尺復活)。"""
        from src.ui.pages.health_inspector import freshness_light
        assert freshness_light(_CURRENT_ASOF, 'monthly', today=_TODAY)[0] == '⬜'

    def test_monthly_has_no_calendar_day_band(self):
        from src.ui.pages.health_inspector import freshness_bands
        with pytest.raises(ValueError):
            freshness_bands('monthly')

    def test_daily_and_quarterly_bands_untouched(self):
        """G2 只動月頻:日頻 / 季頻的門檻來源不得被順手改掉。"""
        from shared.staleness import stale_days_threshold
        from src.ui.pages.health_inspector import freshness_bands

        assert freshness_bands('daily')[1] == stale_days_threshold('daily')
        assert freshness_bands('quarterly') == (stale_days_threshold('quarterly'),
                                                stale_days_threshold('quarterly'))

    def test_monthly_revenue_row_uses_its_own_publication_lag(self):
        """個股月營收(月後 ~10 天)也走同一條規則,而不是另外一套數字。"""
        from src.ui.pages.health_inspector import freshness_light

        assert freshness_light(_CURRENT_ASOF, 'monthly', today=_TODAY,
                               indicator='tw_monthly_revenue')[0] == '🟢'
        assert freshness_light(_MISSED_ASOF, 'monthly', today=_TODAY,
                               indicator='tw_monthly_revenue')[0] == '🔴'


# ══════════════════════════════════════════════════════════════════
# E. 三頁對**同一筆資料**的燈號:哪裡必須一樣、哪裡刻意不一樣
# ══════════════════════════════════════════════════════════════════
class TestThreeRulersOnTheSameDatum:
    """收斂後只剩兩把尺,而且兩把尺量的東西不同、方向被釘住。

    ① `data_coverage` 與 `health_inspector` —— 量 **as_of**,
       G2 後共用同一條 L0 規則 ⇒ **同一筆資料必須給出完全相同的燈號**。
    ② `data_registry_panel` —— 量 registry 的 `last_updated` 欄,
       而該欄語意是混的(`rp_entry` 塞 as_of、`rp_scalar` 塞 proxy_date≈今天;
       月頻裡 M1B / M2 / M1B-M2 缺口三筆走後者)。同一欄兩種語意 ⇒ 沒有任何
       一組門檻對兩者都正確,故它刻意當一把**較寬**的「這條線還活著嗎」的尺。
       這裡不強求它跟前兩者一致,但釘住**差異的方向**:
       它只會更寬,不會更嚴(monthly crit=180 天 > 任何指標的當期上限 96 天)。

    為什麼 ② 這組可以不注入 today:`_freshness_emoji` 內部寫死 `date.today()`
    (不在本輪可改範圍)。故改用「距今 N 天」建構輸入,並讓 as_of 尺用同一個
    `date.today()` 作基準。所選的 N(30 / 98 / 200)在**任何**一天都落在同一
    個判定區間:
      - 30 天 → as_of 落在上個月或本月 ⇒ 期數規則必為當期;
      - 98 天 → as_of 至少是 3 個月前,而預期最新資料月最多只到 2 個月前
                ⇒ 期數規則必定落後 ≥1 期;registry 側 90 < 98 ≤ 180 ⇒ 必為 🟡;
      - 200 天 → 兩邊都必定紅。
    """

    _INDICATOR = "us_core_cpi"

    @pytest.mark.parametrize("asof", ["2026-07-01", _CURRENT_ASOF, _MISSED_ASOF,
                                      "2026-03-01", "2025-06-01"])
    @pytest.mark.parametrize("key", _MACRO_MONTHLY_KEYS)
    def test_coverage_and_inspector_are_identical(self, asof, key):
        """health_inspector 的月頻輸出必須**逐字**等於共用規則 —— 不是「都紅就好」。

        另一半(data_coverage 的整列燈號 == 共用規則)由下一條測試接上,
        兩條合起來才是「兩頁同一份規則」。分兩條寫是因為 data_coverage 回的是
        整列取最差後的 label(前綴指標名),不能直接對字串相等。
        """
        from src.ui.pages.health_inspector import freshness_light

        _rule = monthly_freshness_level(asof, indicator=key, today=_TODAY)
        _ins = freshness_light(asof, 'monthly', today=_TODAY, indicator=key)
        assert _rule == _ins, (
            f"{key} as_of={asof}:共用規則給 {_rule},"
            f"health_inspector 給 {_ins} —— 同一筆資料不得有兩種說法")

    def test_coverage_page_row_matches_the_shared_rule(self):
        """再往上一層:整列燈號也必須等於共用規則的輸出(不是只有 helper 一致)。"""
        for _asof in (_CURRENT_ASOF, _MISSED_ASOF, "2026-03-01"):
            _row = _macro_row({"macro_info": {
                "us_core_cpi": {"yoy": 3.1, "date": _asof},
                "_loaded_at": "2026-08-07 09:00:00"}})
            _e, _l = monthly_freshness_level(
                _asof, indicator=self._INDICATOR, today=_TODAY)
            assert _row["fresh_emoji"] == _e
            assert _l in _row["fresh_label"]

    @pytest.mark.parametrize("days_old", [30, 98, 200, 400])
    def test_registry_panel_is_never_stricter_than_the_asof_ruler(self, days_old):
        """不變量:registry 判 🔴 ⇒ as_of 尺必定也 🔴(它只會更寬,不會更嚴)。

        反過來成立才是 bug —— 那代表一把「較寬的存活度尺」比「精確的當期尺」
        更早喊過期,兩張表會互相否定。
        """
        from src.ui.pages.data_registry_panel import _freshness_emoji

        _today = dt.date.today()
        _asof = _today - dt.timedelta(days=days_old)
        _reg = _freshness_emoji(_asof.isoformat(), 'monthly', False)[0]
        _cov = monthly_freshness_level(
            _asof, indicator=self._INDICATOR, today=_today)[0]
        assert _RANK[_reg] <= _RANK[_cov], (
            f"距今 {days_old} 天:data_registry_panel 給 {_reg}、"
            f"as_of 尺給 {_cov} —— 較寬的尺竟然比較嚴")
        if _reg == "🔴":
            assert _cov == "🔴"

    def test_registry_panel_difference_is_real_and_named(self):
        """具名差異:漏掉一期的月頻資料,兩張表**確實**不同色。

        這條刻意斷言「不一樣」——如果哪天有人把 registry 的月頻門檻改成跟
        as_of 尺一樣,這條會炸,逼他先回答「last_updated 的混語意解決了嗎」
        (見 shared/data_categories.py 的 FRESHNESS_THRESHOLDS_DAYS 註解)。
        """
        from src.ui.pages.data_registry_panel import _freshness_emoji

        _today = dt.date.today()
        _asof = _today - dt.timedelta(days=98)      # 必定落後 ≥1 期
        assert monthly_freshness_level(
            _asof, indicator=self._INDICATOR, today=_today)[0] == "🔴"
        assert _freshness_emoji(_asof.isoformat(), 'monthly', False)[0] == "🟡", (
            "data_registry_panel 的月頻尺(90/180)刻意較寬:它量的是語意混雜的 "
            "`last_updated`(rp_scalar 塞的是抓取時間),不是 as_of")
