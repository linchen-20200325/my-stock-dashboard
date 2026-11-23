# -*- coding: utf-8 -*-
"""tests/test_twii_freshness_semantics_synthetic.py — ^TWII 新鮮度語意（曆日 vs 交易日）合成資料特徵化測試。

標籤：synthetic tests only / no source retrieval / no publish
授權：#1199 7079173656（總管，TWII synthetic tests-only 第二優先）；
      背景引 #1199 7079084985（TWII 新鮮度語意敘述）。

目的
- 固定**現行**兩套新鮮度規則各自的行為，並讓它們的**差異**可被看見、可被偵測：
    (1) `src.data.macro.macro_cache_reader.compute_cache_staleness('twii_ohlcv', ...)`
        ＝ 曆日規則：`age_days = (today - as_of).days`，嚴格大於 `shared.staleness.STALE_DAYS_DAILY`(7) 才判過期。
    (2) `shared.freshness_policy.assess_daily(...)`
        ＝ 客戶 2026-10-14 核准的交易日規則：落後交易日數 > `DAILY_MAX_LAG_TRADING_DAYS`(3) → STALE。
- ⚠️ 兩套規則「並存」是現況，**不是 bug、不是違規**；本檔**不宣稱**任何一方違反任何規定，
  只釘住「兩邊現況各是什麼」與「在哪些輸入上結論不同」。
- ⛔ 不改 production、不改任何既有門檻、不新增任何生產 API。

範圍與紀律
- 只用**測試內合成**的日期與數值（記憶體 DataFrame；cache_dir 一律 pytest `tmp_path`）。
- ⛔ 不連網、不讀 Secrets、不讀／寫真實 `data_cache/`（含任何 parquet／metadata.json）。
- 時鐘固定：`today` 全部由測試傳入，不呼叫 `date.today()`；結果與主機 TZ 無關。
- 合成休市表（`CalendarSets`）**不是**真實 TWSE 行事曆；其中的「連假」是為了構造邊界而編的日期。
- 命名分兩類：
  `test_current_behavior_*` ＝ 特徵化（記錄**現行**行為，**不代表它是對的**）。
  `test_target_state_*`     ＝ **未核准**的目標態；一律 `xfail(strict=True)`，被測物是本檔內的
                              reference 函式，**不是** production API，也**不暗示** production 應改。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import socket

import pandas as pd
import pytest
import requests

from shared.freshness_policy import (
    DAILY_MAX_LAG_TRADING_DAYS,
    FreshnessStatus,
    assess_daily,
)
from shared.staleness import STALE_DAYS_DAILY, stale_days_threshold
from shared.trading_days import CalendarSets
from src.data.macro import macro_cache_reader as mcr
from src.data.macro.macro_cache_reader import (
    CACHE_DATASET_CADENCE,
    compute_cache_staleness,
)

DS = "twii_ohlcv"

# ══════════════════════════════════════════════════════════════
# 固定日期（皆為 2026 年的週幾，由 test_guard_fixture_weekdays 驗證）
# ══════════════════════════════════════════════════════════════
MON_1109 = dt.date(2026, 11, 9)    # 週一
MON_1116 = dt.date(2026, 11, 16)   # 週一
THU_1119 = dt.date(2026, 11, 19)   # 週四
FRI_1120 = dt.date(2026, 11, 20)   # 週五
TODAY = MON_1116                   # 預設「今日」（週一）

# 合成連假：2026-12-07（一）～12-11（五）平日全休市，加上前後兩個週末 ＝ 12-05（六）～12-13（日）共 9 個曆日全休市。
# ⚠️ 這是為構造邊界而編的合成日期，**不是**真實 TWSE 行事曆。
SYN_HOLIDAY_WEEKDAYS = frozenset(dt.date(2026, 12, d) for d in range(7, 12))
FRI_1204 = dt.date(2026, 12, 4)    # 連假前最後一個交易日（週五）
MON_1214 = dt.date(2026, 12, 14)   # 連假後第一個交易日（週一）

CAL_PLAIN = CalendarSets(closed=frozenset(), trading=frozenset(), unclassified=frozenset(),
                         covered_years=frozenset({2026}))
CAL_SYN_HOLIDAY = CalendarSets(closed=SYN_HOLIDAY_WEEKDAYS, trading=frozenset(), unclassified=frozenset(),
                               covered_years=frozenset({2026}))


# ══════════════════════════════════════════════════════════════
# 護欄 fixtures（autouse）：禁網路、禁 Secrets、禁讀 parquet
# ══════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("synthetic tests only: 網路存取被禁止")
    monkeypatch.setattr(socket.socket, "connect", _boom)
    monkeypatch.setattr(socket.socket, "connect_ex", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    monkeypatch.setattr(requests.Session, "request", _boom)


@pytest.fixture(autouse=True)
def _no_secrets(monkeypatch):
    for k in list(os.environ):
        if k in ("FINMIND_TOKEN", "PROXY_URL", "GEMINI_API_KEY") or k.startswith("NAS_"):
            monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _no_parquet_read(monkeypatch):
    """本檔所有案例都以 `df=` 注入或指向空 tmp_path；任何 parquet 讀取＝誤觸真檔，直接炸。"""
    def _boom(*a, **k):
        raise AssertionError("synthetic tests only: 不得讀取任何 parquet")
    monkeypatch.setattr(pd, "read_parquet", _boom)


def test_guard_no_secrets_and_network_blocked():
    for k in ("FINMIND_TOKEN", "PROXY_URL"):
        assert k not in os.environ
    assert not [k for k in os.environ if k.startswith("NAS_")]
    with pytest.raises(AssertionError, match="網路存取被禁止"):
        socket.create_connection(("example.com", 80))
    with pytest.raises(AssertionError, match="網路存取被禁止"):
        requests.get("http://example.invalid/")
    with pytest.raises(AssertionError, match="不得讀取任何 parquet"):
        pd.read_parquet("nonexistent.parquet")


def test_guard_fixture_weekdays():
    """固定日期的星期要與註解一致（否則整檔的『週一／週五』推論失效）。"""
    assert MON_1109.weekday() == 0 and MON_1116.weekday() == 0 and MON_1214.weekday() == 0
    assert THU_1119.weekday() == 3
    assert FRI_1120.weekday() == 4 and FRI_1204.weekday() == 4
    assert all(d.weekday() < 5 for d in SYN_HOLIDAY_WEEKDAYS) and len(SYN_HOLIDAY_WEEKDAYS) == 5


# ══════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════
def _df(*dates) -> pd.DataFrame:
    return pd.DataFrame({"date": list(dates), "close": [100.0] * len(dates)})


def _calendar_rule(as_of: dt.date, today: dt.date, tmp_path, *, meta: dict | None = None) -> dict:
    """呼叫現行曆日規則（df= 注入；cache_dir 為 tmp_path）。"""
    if meta is not None:
        (tmp_path / mcr.CACHE_METADATA_NAME).write_text(json.dumps(meta), encoding="utf-8")
    return compute_cache_staleness(DS, cache_dir=tmp_path, df=_df(as_of), today=today)


def _trading_rule(as_of: dt.date, today: dt.date, cal: CalendarSets | None):
    return assess_daily(as_of, today=today, calendar=cal)


# TARGET_STATE reference, NOT a production API ───────────────────────────
def _reference_trading_day_lag(as_of: dt.date, today: dt.date, closed: frozenset) -> int:
    """TARGET_STATE reference, NOT a production API。

    獨立於 production 的最小參考實作：(as_of, today] 內「非週末且不在 closed」的天數。
    只用於本檔 target_state 測試的對照，不暗示 production 應改用它。
    """
    n, d = 0, as_of + dt.timedelta(days=1)
    while d <= today:
        if d.weekday() < 5 and d not in closed:
            n += 1
        d += dt.timedelta(days=1)
    return n


def _reference_is_stale_trading_day_rule(as_of: dt.date, today: dt.date, closed: frozenset) -> bool:
    """TARGET_STATE reference, NOT a production API：以交易日規則判 TWII 是否過期。"""
    return _reference_trading_day_lag(as_of, today, closed) > DAILY_MAX_LAG_TRADING_DAYS


# ══════════════════════════════════════════════════════════════
# 0. 常數與登錄現況（任一被改動即紅燈，提醒同步檢視本檔）
# ══════════════════════════════════════════════════════════════
def test_current_behavior_constants_and_registration():
    assert STALE_DAYS_DAILY == 7
    assert stale_days_threshold("daily") == 7
    assert DAILY_MAX_LAG_TRADING_DAYS == 3
    assert CACHE_DATASET_CADENCE[DS] == ("daily", None)


def test_current_behavior_unknown_cadence_threshold_falls_back_to_daily():
    """未知 cadence → 退 daily（最嚴門檻）。"""
    assert stale_days_threshold("no_such_cadence") == STALE_DAYS_DAILY


# ══════════════════════════════════════════════════════════════
# A. current_behavior：曆日規則（compute_cache_staleness）邊界
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("age,expected_stale", [
    (0, False),
    (1, False),
    (6, False),
    (7, False),   # 邊界：恰好 7 日 → 新鮮（嚴格大於 7 才過期）
    (8, True),    # 邊界：8 日 → 過期
    (9, True),
    (30, True),
])
def test_current_behavior_calendar_day_boundary_strictly_greater_than_7(tmp_path, age, expected_stale):
    as_of = TODAY - dt.timedelta(days=age)
    r = _calendar_rule(as_of, TODAY, tmp_path)
    assert r["age_days"] == age
    assert r["as_of"] == as_of
    assert r["is_stale"] is expected_stale
    if expected_stale:
        assert r["reason"] and f"{age} 天" in r["reason"] and "超過 daily 門檻 7 天" in r["reason"]
    else:
        assert r["reason"] is None


def test_current_behavior_future_as_of_is_stale_with_negative_age(tmp_path):
    """as_of 晚於 today → 判不出新鮮度 → is_stale=True；age_days 保留負值供診斷。"""
    r = _calendar_rule(TODAY + dt.timedelta(days=1), TODAY, tmp_path)
    assert r["is_stale"] is True
    assert r["age_days"] == -1
    assert r["as_of"] == TODAY + dt.timedelta(days=1)
    assert "晚於今日" in r["reason"]


def test_current_behavior_missing_date_column_is_stale(tmp_path):
    r = compute_cache_staleness(DS, cache_dir=tmp_path, df=pd.DataFrame({"close": [1.0]}), today=TODAY)
    assert r["is_stale"] is True
    assert r["as_of"] is None and r["age_days"] is None
    assert "缺" in r["reason"]


def test_current_behavior_empty_df_is_stale(tmp_path):
    r = compute_cache_staleness(DS, cache_dir=tmp_path, df=pd.DataFrame({"date": []}), today=TODAY)
    assert r["is_stale"] is True
    assert r["as_of"] is None and r["age_days"] is None


def test_current_behavior_all_unparseable_dates_is_stale(tmp_path):
    r = compute_cache_staleness(DS, cache_dir=tmp_path, df=pd.DataFrame({"date": ["not-a-date", None]}),
                                today=TODAY)
    assert r["is_stale"] is True
    assert r["as_of"] is None


def test_current_behavior_df_none_and_no_parquet_in_tmp_dir_is_stale(tmp_path):
    """df=None → 讀 cache_dir/twii_ohlcv.parquet；tmp_path 內沒有該檔 → 判不出 → is_stale=True。"""
    assert not (tmp_path / f"{DS}.parquet").exists()
    r = compute_cache_staleness(DS, cache_dir=tmp_path, today=TODAY)
    assert r["is_stale"] is True and r["as_of"] is None


def test_current_behavior_unregistered_dataset_is_stale(tmp_path):
    r = compute_cache_staleness("no_such_dataset", cache_dir=tmp_path, df=_df(TODAY), today=TODAY)
    assert r["is_stale"] is True
    assert "未登記" in r["reason"]


def test_current_behavior_as_of_uses_latest_row_not_last_row(tmp_path):
    """as_of 取 date 欄最大值（不依列序）。"""
    df = _df(TODAY, TODAY - dt.timedelta(days=30))
    r = compute_cache_staleness(DS, cache_dir=tmp_path, df=df, today=TODAY)
    assert r["as_of"] == TODAY and r["is_stale"] is False


# ── A'. metadata 缺失 vs 年齡判定：兩種情況分別釘住 ────────────────────────
def test_current_behavior_missing_metadata_does_not_force_stale_for_fresh_daily_df(tmp_path):
    """⚠️ 與函式 docstring「缺 metadata … 一律 is_stale=True」字面不同（現況觀察，非宣稱違規）：
    日頻且 df 新鮮時，缺 metadata.json **不會**把 is_stale 推成 True；只是 upstream_* 欄位為空。
    本測試釘住「現行實際行為」；若日後行為改為缺 metadata 即過期，本測試會紅燈提醒同步更新。"""
    assert not (tmp_path / mcr.CACHE_METADATA_NAME).exists()
    r = compute_cache_staleness(DS, cache_dir=tmp_path, df=_df(TODAY), today=TODAY)
    assert r["is_stale"] is False
    assert r["upstream_error"] is None and r["meta_last_updated"] is None
    assert r["upstream_state"] == ""


def test_current_behavior_missing_metadata_age_judgement_still_applies(tmp_path):
    """缺 metadata 時，年齡判定照常（8 日 → 過期）。"""
    r = _calendar_rule(TODAY - dt.timedelta(days=8), TODAY, tmp_path)
    assert not (tmp_path / mcr.CACHE_METADATA_NAME).exists()
    assert r["is_stale"] is True


def test_current_behavior_synthetic_metadata_age_judgement_is_independent_of_upstream_state(tmp_path):
    """合成 metadata（含 last_error）：upstream_error／upstream_state 被帶出，但 is_stale 仍只由年齡決定。"""
    meta = {"datasets": {DS: {"last_updated": "2026-11-15T10:00:00+00:00", "last_error": "synthetic boom"}}}
    fresh = _calendar_rule(TODAY, TODAY, tmp_path, meta=meta)
    assert fresh["is_stale"] is False                  # 年齡 0 → 新鮮，即使上游自陳錯誤
    assert fresh["upstream_error"] == "synthetic boom"
    assert fresh["upstream_state"] == "FETCH_FAILED"
    assert fresh["meta_last_updated"] == "2026-11-15T10:00:00+00:00"
    old = compute_cache_staleness(DS, cache_dir=tmp_path, df=_df(TODAY - dt.timedelta(days=8)), today=TODAY)
    assert old["is_stale"] is True                     # 年齡 8 → 過期
    assert old["upstream_error"] == "synthetic boom"


def test_current_behavior_corrupt_metadata_is_treated_as_missing(tmp_path, capsys):
    (tmp_path / mcr.CACHE_METADATA_NAME).write_text("{not json", encoding="utf-8")
    r = compute_cache_staleness(DS, cache_dir=tmp_path, df=_df(TODAY), today=TODAY)
    assert r["is_stale"] is False and r["upstream_error"] is None


# ══════════════════════════════════════════════════════════════
# A''. current_behavior：交易日規則（assess_daily）邊界（合成日曆，無假日）
# ══════════════════════════════════════════════════════════════
def test_current_behavior_trading_day_rule_boundary_3_fresh_4_stale():
    """週一 as_of：週四 today → 落後 3 個交易日 → FRESH；週五 today → 落後 4 → STALE（嚴格大於 3）。"""
    v3 = _trading_rule(MON_1116, THU_1119, CAL_PLAIN)
    assert (v3.status, v3.lag) == (FreshnessStatus.FRESH, 3)
    v4 = _trading_rule(MON_1116, FRI_1120, CAL_PLAIN)
    assert (v4.status, v4.lag) == (FreshnessStatus.STALE, 4)


def test_current_behavior_trading_day_rule_future_missing_and_no_calendar():
    fut = _trading_rule(TODAY + dt.timedelta(days=1), TODAY, CAL_PLAIN)
    assert fut.status is FreshnessStatus.UNDETERMINED
    assert _trading_rule(None, TODAY, CAL_PLAIN).status is FreshnessStatus.MISSING
    # 休市表取不到 → 區間法：落後 0～7，既非全新鮮也非全過期 → UNDETERMINED（不假設新鮮）
    nocal = _trading_rule(MON_1109, TODAY, None)
    assert nocal.status is FreshnessStatus.UNDETERMINED and nocal.lag is None


# ══════════════════════════════════════════════════════════════
# B. current_behavior：曆日 vs 交易日 —— 兩套規則並存、結論不同（不是 bug）
# ══════════════════════════════════════════════════════════════
def test_current_behavior_week_gap_calendar_rule_fresh_but_trading_rule_stale(tmp_path):
    """as_of 週一 11-09、today 下週一 11-16：相距 7 曆日、缺 5 個交易日（11-10～11-13 與 11-16）。

    - 曆日規則（compute_cache_staleness）：age=7 → 不大於 7 → 新鮮。
    - 交易日規則（assess_daily）：落後 5 > 3 → STALE。
    ⚠️ 兩套規則並存，是現況，**不是 bug**；本測試只釘住兩邊各自的現行結論。"""
    cal = _calendar_rule(MON_1109, MON_1116, tmp_path)
    assert cal["age_days"] == 7
    assert cal["is_stale"] is False

    trd = _trading_rule(MON_1109, MON_1116, CAL_PLAIN)
    assert trd.lag == 5
    assert trd.status is FreshnessStatus.STALE


def test_current_behavior_long_holiday_calendar_rule_stale_but_trading_rule_fresh(tmp_path):
    """合成 9 曆日全休市（12-05 六～12-13 日）：as_of＝連假前最後交易日 12-04（五）、today＝連假後第一個交易日 12-14（一）。

    - 曆日規則：age=10 > 7 → 過期。
    - 交易日規則：(12-04, 12-14] 內只有 12-14 一個交易日 → 落後 1 ≤ 3 → FRESH。
    ⚠️ 兩套規則並存，是現況，**不是 bug**；休市表為合成，不代表真實 TWSE 行事曆。"""
    cal = _calendar_rule(FRI_1204, MON_1214, tmp_path)
    assert cal["age_days"] == 10
    assert cal["is_stale"] is True

    trd = _trading_rule(FRI_1204, MON_1214, CAL_SYN_HOLIDAY)
    assert trd.lag == 1
    assert trd.status is FreshnessStatus.FRESH


def test_current_behavior_four_day_gap_calendar_fresh_trading_stale(tmp_path):
    """週一→週五：4 曆日／4 交易日。曆日規則（4 ≤ 7）新鮮；交易日規則（4 > 3）過期。"""
    assert _calendar_rule(MON_1116, FRI_1120, tmp_path)["is_stale"] is False
    assert _trading_rule(MON_1116, FRI_1120, CAL_PLAIN).status is FreshnessStatus.STALE


@pytest.mark.parametrize("as_of,today,cal", [
    (TODAY, TODAY, CAL_PLAIN),                                   # 同日：兩邊皆新鮮
    (FRI_1120, dt.date(2026, 11, 23), CAL_PLAIN),                # 週五→下週一：3 曆日／1 交易日，兩邊皆新鮮
    (TODAY - dt.timedelta(days=30), TODAY, CAL_PLAIN),           # 30 日前：兩邊皆過期
])
def test_current_behavior_regions_where_both_rules_agree(tmp_path, as_of, today, cal):
    """對照組：並非所有輸入都不同；差異只出現在特定區間（週間缺口、連假）。"""
    cal_stale = _calendar_rule(as_of, today, tmp_path)["is_stale"]
    trd_stale = _trading_rule(as_of, today, cal).status is FreshnessStatus.STALE
    assert cal_stale is trd_stale


def test_current_behavior_reference_agrees_with_assess_daily_on_synthetic_scenarios():
    """守住 reference 的正當性：在有完整合成休市表時，reference 與 assess_daily 的結論一致。
    （reference 只為 target_state 對照用；此測試確保它不是憑空另一套規則。）"""
    scenarios = [
        (MON_1109, MON_1116, CAL_PLAIN, frozenset()),
        (FRI_1204, MON_1214, CAL_SYN_HOLIDAY, SYN_HOLIDAY_WEEKDAYS),
        (MON_1116, THU_1119, CAL_PLAIN, frozenset()),
        (MON_1116, FRI_1120, CAL_PLAIN, frozenset()),
    ]
    for a, t, cal, closed in scenarios:
        assert (_trading_rule(a, t, cal).status is FreshnessStatus.STALE) \
            is _reference_is_stale_trading_day_rule(a, t, closed)
    # 明確釘住 xfail 兩個場景的 reference 期望值（避免 xfail 因 reference 本身壞掉而「偽失敗」）
    assert _reference_is_stale_trading_day_rule(MON_1109, MON_1116, frozenset()) is True
    assert _reference_is_stale_trading_day_rule(FRI_1204, MON_1214, SYN_HOLIDAY_WEEKDAYS) is False


# ══════════════════════════════════════════════════════════════
# C. target_state（未核准目標；xfail strict；被測物＝本檔 reference，非 production API）
# ══════════════════════════════════════════════════════════════
_TARGET_REASON = (
    "未獲核准的目標態，不改現行門檻；TARGET_STATE reference, NOT a production API。"
    "參照 #1199 7079173656（總管第二優先：固定現行語意、暴露差異）與 #1199 7079084985。"
    "假設性問題：UI 層的 TWII 新鮮度若採交易日規則，結論會與現行曆日規則不同。"
)


@pytest.mark.xfail(strict=True, reason=_TARGET_REASON + " 場景：週間缺口（曆日 7／缺 5 交易日）。")
def test_target_state_ui_twii_freshness_trading_day_rule_week_gap(tmp_path):
    expected = _reference_is_stale_trading_day_rule(MON_1109, MON_1116, frozenset())  # True（見 reference 對照測試）
    assert _calendar_rule(MON_1109, MON_1116, tmp_path)["is_stale"] is expected


@pytest.mark.xfail(strict=True, reason=_TARGET_REASON + " 場景：合成 9 曆日連假（曆日 10／缺 1 交易日）。")
def test_target_state_ui_twii_freshness_trading_day_rule_long_holiday(tmp_path):
    expected = _reference_is_stale_trading_day_rule(FRI_1204, MON_1214, SYN_HOLIDAY_WEEKDAYS)  # False（同上）
    assert _calendar_rule(FRI_1204, MON_1214, tmp_path)["is_stale"] is expected
