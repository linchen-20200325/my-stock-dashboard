"""批 D5（2026-10-02）：證交所休市表新源（HANDOFF B4 (a)，客戶裁示頁1⑤「接休市日曆」）。

⚠️ 夾具 `tests/fixtures/twse_holiday_schedule_115_synthetic.json` 是**合成**資料
（官方欄名與 7 位民國日期格式，日期與星期已逐列核對一致），⛔ 不是證交所真實回應 ——
撰寫時沙箱連不到 `openapi.twse.com.tw`。第 3、7 列以外的「補行上班日」情形另以
測試內的合成列表達。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.data.proxy import proxy_helper as _proxy_helper
from shared import fail_cooldown as _fc
from src.compute import trading_calendar as tc
from src.data.stock import twse_holiday_fetcher as hf
from src.services import trading_calendar_service as svc

FIXTURE = Path(__file__).parent / "fixtures" / "twse_holiday_schedule_115_synthetic.json"
UTC = timezone.utc


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _cal(extra=()):
    return hf.parse_holiday_schedule(_payload() + list(extra),
                                     fetched_at=datetime(2026, 10, 2, tzinfo=UTC))


def _sets(cal):
    return dict(closed=cal.dates_of("closed"), trading=cal.dates_of("trading"),
                unclassified=cal.dates_of("unclassified"), covered_years=cal.covered_years)


@pytest.fixture(autouse=True)
def _clear():
    hf.fetch_twse_holiday_calendar.clear()
    yield
    hf.fetch_twse_holiday_calendar.clear()


# ── L1 解析 ─────────────────────────────────────────────────────────
class TestParse:
    def test_fixture_kinds(self):
        cal = _cal()
        assert cal.source == hf.SOURCE_ID == "TWSE:openapi/holidaySchedule"
        assert cal.fetched_at.tzinfo is not None
        assert cal.covered_years == frozenset({2026})
        closed, trading = cal.dates_of("closed"), cal.dates_of("trading")
        assert date(2026, 1, 1) in closed
        assert date(2026, 2, 12) in closed  # 市場無交易，僅辦理結算交割
        assert date(2026, 9, 25) in closed
        assert date(2026, 10, 9) in closed  # 補假
        # 表內「開始交易／最後交易」是交易日，⛔ 不得被當休市
        assert {date(2026, 1, 2), date(2026, 2, 11), date(2026, 2, 23)} <= trading
        assert not (closed & trading)
        assert cal.dates_of("unclassified") == frozenset()

    def test_roc_date(self):
        assert hf.parse_roc_date("1150101") == date(2026, 1, 1)
        for bad in ("115011", "2026-01-01", "11501a1", "", None, "1151301", "0000101"):
            with pytest.raises(ValueError):
                hf.parse_roc_date(bad)

    @pytest.mark.parametrize("payload", [{}, [], ["x"], [{"Name": "a"}],
                                         [{"Date": "1150101"}]])
    def test_bad_payload_raises(self, payload):
        with pytest.raises(ValueError):
            hf.parse_holiday_schedule(payload, fetched_at=datetime.now(UTC))

    def test_weekday_mismatch_raises(self):
        row = {"Name": "中秋節", "Date": "1150925", "Weekday": "四", "Description": "依規定放假1日。"}
        with pytest.raises(ValueError, match="星期"):
            hf.parse_holiday_schedule([row], fetched_at=datetime.now(UTC))

    @pytest.mark.parametrize("name,desc,kind", [
        ("中秋節", "依規定放假1日。", "closed"),
        ("颱風", "本日休市。", "closed"),
        ("臨時", "集中交易市場停止交易。", "closed"),
        ("市場無交易，僅辦理結算交割作業", "", "closed"),
        ("國曆新年開始交易日", "國曆新年開始交易。", "trading"),
        ("補行上班日", "", "unclassified"),             # 兩類都沒中
        ("農曆春節前最後交易日", "次日起放假。", "unclassified"),  # 兩類都中
    ])
    def test_classify_entry(self, name, desc, kind):
        assert hf.classify_entry(name, desc) == kind


# ── L1 取數：只快取成功、失敗退避 ─────────────────────────────────────
class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class TestFetch:
    def _patch(self, monkeypatch, responses):
        calls = []

        def fake(url, **kw):
            calls.append(url)
            r = responses[min(len(calls), len(responses)) - 1]
            return r

        # ⚠️ 打在實體模組上，⛔ 不打在 barrel：barrel 靠 PEP 562 `__getattr__` 即時轉發，
        #    對 barrel setattr 會在還原時把舊函式「釘」進 barrel 的模組字典，
        #    之後別的測試 patch `proxy_helper.fetch_url` 就轉發不到了（實測汙染 2 支測試）。
        monkeypatch.setattr(_proxy_helper, "fetch_url", fake)
        return calls

    def test_success_is_cached(self, monkeypatch):
        calls = self._patch(monkeypatch, [_Resp(200, _payload())])
        a = hf.fetch_twse_holiday_calendar(taipei_year=2026)
        b = hf.fetch_twse_holiday_calendar(taipei_year=2026)
        assert calls == [hf.TWSE_HOLIDAY_URL]
        assert a.dates_of("closed") == b.dates_of("closed")

    @pytest.mark.parametrize("resp", [None, _Resp(500, None),
                                      _Resp(503, json.loads(FIXTURE.read_text(encoding="utf-8"))),
                                      _Resp(200, [{"Name": "中秋節", "Date": "1150925",
                                                   "Weekday": "五", "Description": "依規定放假1日。"}]), _Resp(200, ValueError("x")),
                                      _Resp(200, []), _Resp(200, {"stat": "no"})])
    def test_failure_raises_not_cached_and_backs_off(self, monkeypatch, resp):
        calls = self._patch(monkeypatch, [resp, _Resp(200, _payload())])
        with pytest.raises(hf.HolidayCalendarUnavailable):
            hf.fetch_twse_holiday_calendar(taipei_year=2026)
        # 冷卻期內：不重打上游，再拋同一則失敗
        with pytest.raises(hf.HolidayCalendarUnavailable, match="冷卻中"):
            hf.fetch_twse_holiday_calendar(taipei_year=2026)
        assert len(calls) == 1
        # 冷卻過期 → 重抓；失敗沒有被快取，所以這次拿得到成功結果
        monkeypatch.setattr(hf._calendar_fail_cooldown, "seconds", 0.0)
        cal = hf.fetch_twse_holiday_calendar(taipei_year=2026)
        assert len(calls) == 2
        assert date(2026, 9, 25) in cal.dates_of("closed")

    def test_cooldown_constant_is_shared_ssot(self):
        assert hf._calendar_fail_cooldown.seconds == _fc.FAIL_COOLDOWN_SEC


# ── 批 D5 QA 修 1／修 2：殘表與衝突列 ─────────────────────────────
class TestCompletenessAndConflicts:
    def test_single_row_table_raises(self):
        row = {"Name": "中秋節", "Date": "1150925", "Weekday": "五", "Description": "依規定放假1日。"}
        with pytest.raises(ValueError, match="不完整"):
            hf.parse_holiday_schedule([row], fetched_at=datetime.now(UTC))

    @pytest.mark.parametrize("drop", ["1150101", "1150228", "1151010"])
    def test_missing_anchor_raises(self, drop):
        rows = [r for r in _payload() if r["Date"] != drop]
        with pytest.raises(ValueError, match="不完整"):
            hf.parse_holiday_schedule(rows, fetched_at=datetime.now(UTC))

    def test_partial_extra_year_not_covered(self):
        cal = _cal([{"Name": "中華民國開國紀念日", "Date": "1160101", "Weekday": "五",
                     "Description": "依規定放假1日。"}])
        assert cal.covered_years == frozenset({2026})
        v = tc.classify_day(date(2027, 2, 8), **_sets(cal))  # 2027 平日
        assert v.status == tc.UNDETERMINED

    def test_conflicting_duplicate_is_undetermined(self):
        dup = {"Name": "中秋節後開始交易日", "Date": "1150925", "Weekday": "五",
               "Description": "開始交易。"}
        cal = _cal([dup])
        assert date(2026, 9, 25) in cal.dates_of("unclassified")
        assert date(2026, 9, 25) not in cal.dates_of("closed")
        assert date(2026, 9, 25) not in cal.dates_of("trading")
        assert tc.classify_day(date(2026, 9, 25), **_sets(cal)).status == tc.UNDETERMINED

    def test_conflicting_anchor_breaks_completeness(self):
        dup = {"Name": "國曆新年開始交易日", "Date": "1150101", "Weekday": "四",
               "Description": "開始交易。"}
        with pytest.raises(ValueError, match="不完整"):
            _cal([dup])


# ── L2 判定 ─────────────────────────────────────────────────────────
class TestClassifyDay:
    @pytest.mark.parametrize("d,status", [
        (date(2026, 10, 2), tc.TRADING),   # 週五平日
        (date(2026, 10, 3), tc.CLOSED),    # 週六
        (date(2026, 10, 4), tc.CLOSED),    # 週日
        (date(2026, 9, 25), tc.CLOSED),    # 中秋（平日休市）
        (date(2026, 2, 12), tc.CLOSED),    # 結算交割、無交易
        (date(2026, 2, 11), tc.TRADING),   # 表內「最後交易日」
        (date(2026, 1, 2), tc.TRADING),
    ])
    def test_basic(self, d, status):
        assert tc.classify_day(d, **_sets(_cal())).status == status

    def test_makeup_saturday_trading_vs_closed(self):
        trade_sat = {"Name": "補行上班日", "Date": "1150307", "Weekday": "六",
                     "Description": "集中交易市場開始交易。"}
        s = _sets(_cal([trade_sat]))
        assert tc.classify_day(date(2026, 3, 7), **s).status == tc.TRADING
        closed_sat = dict(trade_sat, Description="市場無交易。")
        s = _sets(_cal([closed_sat]))
        assert tc.classify_day(date(2026, 3, 7), **s).status == tc.CLOSED
        # 未列在表內的週六 → 照週末規則
        assert tc.classify_day(date(2026, 3, 14), **s).status == tc.CLOSED

    def test_unclassified_is_undetermined_not_guessed(self):
        odd = {"Name": "補行上班日", "Date": "1150307", "Weekday": "六", "Description": ""}
        v = tc.classify_day(date(2026, 3, 7), **_sets(_cal([odd])))
        assert v.status == tc.UNDETERMINED and v.reason

    def test_uncovered_year_is_undetermined(self):
        v = tc.classify_day(date(2027, 1, 4), **_sets(_cal()))  # 平日，但表不涵蓋 2027
        assert v.status == tc.UNDETERMINED and "2027" in v.reason

    def test_next_trading_day(self):
        s = _sets(_cal())
        assert tc.next_trading_day(date(2026, 10, 2), **s).day == date(2026, 10, 5)
        assert tc.next_trading_day(date(2026, 10, 8), **s).day == date(2026, 10, 12)
        # 春節長假：2/11 最後交易 → 2/23 開始交易
        assert tc.next_trading_day(date(2026, 2, 11), **s).day == date(2026, 2, 23)
        assert tc.next_trading_day(date(2026, 9, 24), **s).day == date(2026, 9, 28)

    def test_next_trading_day_across_uncovered_year(self):
        v = tc.next_trading_day(date(2026, 12, 31), **_sets(_cal()))
        assert v.status == tc.UNDETERMINED and "2027" in v.reason


# ── L3 編排 ─────────────────────────────────────────────────────────
class TestService:
    def _fake_cal(self, monkeypatch, cal=None, exc=None):
        def fake(*, taipei_year):
            fake.years.append(taipei_year)
            if exc is not None:
                raise exc
            return cal
        fake.years = []
        monkeypatch.setattr(svc._hf, "fetch_twse_holiday_calendar", fake)
        return fake

    def test_failure_is_unavailable_not_trading_day(self, monkeypatch):
        self._fake_cal(monkeypatch, exc=hf.HolidayCalendarUnavailable("無回應"))
        r = svc.get_today_trading_status(datetime(2026, 10, 2, 3, tzinfo=UTC))
        assert r.is_trading_day is None and r.next_trading_day is None
        assert r.error == "無回應"

    def test_midnight_taipei_edge(self, monkeypatch):
        f = self._fake_cal(monkeypatch, cal=_cal())
        before = svc.get_today_trading_status(datetime(2026, 10, 2, 15, 59, 59, tzinfo=UTC))
        after = svc.get_today_trading_status(datetime(2026, 10, 2, 16, 0, 0, tzinfo=UTC))
        assert (before.today, before.is_trading_day) == (date(2026, 10, 2), True)
        assert (after.today, after.is_trading_day) == (date(2026, 10, 3), False)
        assert after.next_trading_day == date(2026, 10, 5)
        assert before.source == hf.SOURCE_ID and before.fetched_at is not None
        assert f.years == [2026, 2026]

    def test_year_boundary_uses_taipei_year(self, monkeypatch):
        f = self._fake_cal(monkeypatch, cal=_cal())
        r = svc.get_today_trading_status(datetime(2026, 12, 31, 16, 0, tzinfo=UTC))
        assert f.years == [2027]
        assert r.today == date(2027, 1, 1)
        assert r.is_trading_day is None and "2027" in r.error

    def test_table_listed_weekday_holiday(self, monkeypatch):
        self._fake_cal(monkeypatch, cal=_cal())
        r = svc.get_today_trading_status(datetime(2026, 9, 25, 2, tzinfo=UTC))
        assert r.is_trading_day is False and r.error is None
        assert r.next_trading_day == date(2026, 9, 28)

    def test_table_listed_trading_saturday(self, monkeypatch):
        sat = {"Name": "補行上班日", "Date": "1150307", "Weekday": "六",
               "Description": "集中交易市場開始交易。"}
        self._fake_cal(monkeypatch, cal=_cal([sat]))
        r = svc.get_today_trading_status(datetime(2026, 3, 7, 2, tzinfo=UTC))
        assert r.is_trading_day is True and r.error is None

    def test_table_unclassified_weekday_is_unavailable(self, monkeypatch):
        odd = {"Name": "補行上班日", "Date": "1150306", "Weekday": "五", "Description": ""}
        self._fake_cal(monkeypatch, cal=_cal([odd]))
        r = svc.get_today_trading_status(datetime(2026, 3, 6, 2, tzinfo=UTC))
        assert r.is_trading_day is None and r.error

    def test_today_known_next_unknown(self, monkeypatch):
        self._fake_cal(monkeypatch, cal=_cal())
        r = svc.get_today_trading_status(datetime(2026, 12, 31, 2, tzinfo=UTC))
        assert r.is_trading_day is True and r.error is None
        assert r.next_trading_day is None and "2027" in r.next_reason

    def test_naive_now_raises(self):
        with pytest.raises(ValueError):
            svc.taipei_today(datetime(2026, 10, 2, 12))

    def test_taipei_offset(self):
        assert svc.TAIPEI_TZ.utcoffset(None) == timedelta(hours=8)
