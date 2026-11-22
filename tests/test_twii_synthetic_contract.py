# -*- coding: utf-8 -*-
"""tests/test_twii_synthetic_contract.py — ^TWII 日 K 合成資料契約測試（A-TWII-SYNTHETIC-CONTRACT-TESTS-1）。

標籤：synthetic tests only / no source retrieval / no publish
授權：#1199 comment 7072858477（正式技術裁定 1–5）；決策稿 #1199 7072670677 §1–§3。

範圍與紀律
- 只用**測試內合成**的 Yahoo chart JSON；⛔ 不連網、不讀 Secrets、不讀／寫真實 data_cache（一律 tmp_path／記憶體）、
  ⛔ 不啟用 workflow、⛔ 不新增任何生產用函式。
- 時鐘固定：today／時間戳全部由測試給定；主機時區由 `_host_tz` 在測試內釘住並還原（不依賴 CI 環境 TZ）。
- 命名分兩類：
  `test_current_behavior_*`  ＝ 特徵化（記錄**現行**程式實際行為，**不代表它是對的**）。
  `test_target_state_*`      ＝ 新隔離契約的**目標狀態**（fail-closed）；現況不符者標
                               `xfail(strict=True)`，待第二階段另授權修正後轉綠（strict：意外變綠＝紅燈，逼人更新契約）。
  `test_known_gap_*`         ＝ 以 AST／事實斷言釘住「缺口存在」，缺口被修掉時此測試會轉紅提醒更新。
- ⚠️ `known divergence` 證據只證明「現行函式在兩種主機時區下結果不同」，**不是**真實 PIT 證明。
- ⚠️ 本檔內的 `_reference_*` 函式一律是 `TARGET_STATE reference, NOT a production API`。
"""
from __future__ import annotations

import ast
import datetime as dt
import hashlib
import inspect
import io
import json
import math
import os
import socket
import textwrap
import time
from pathlib import Path

import pandas as pd
import pytest
import requests

import scripts.publish_data_pr as pdp
import scripts.update_macro_history as umh
from shared import twii_ohlc_contract as C
from shared.fetch_outcome import FetchOutcome, read_outcome

# ══════════════════════════════════════════════════════════════
# 固定常數（時鐘／時間戳全部寫死）
# ══════════════════════════════════════════════════════════════
TODAY = dt.date(2026, 11, 22)                      # 固定「今日」（週日）
UTC = dt.timezone.utc


def _utc_ts(y, m, d, hh=1, mm=0) -> int:
    """UTC 時間 → epoch 秒（與主機 TZ 無關）。"""
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp())


# Yahoo 對 ^TWII 日 K 的典型時間戳＝交易日 09:00 台北＝01:00 UTC。
TS_THU_1119 = _utc_ts(2026, 11, 19)                # 週四
TS_FRI_1120 = _utc_ts(2026, 11, 20)                # 週五
TS_SAT_1121 = _utc_ts(2026, 11, 21)                # 週六（週末 K 棒）
TS_MON_1123 = _utc_ts(2026, 11, 23)                # > TODAY（未來日）
TS_UTC_1559 = _utc_ts(2026, 11, 19, 15, 59)        # 台北 11-19 23:59
TS_UTC_1600 = _utc_ts(2026, 11, 19, 16, 0)         # 台北 11-20 00:00（日期邊界）
FIXED_FETCHED_AT = "2026-11-20T10:00:00+00:00"     # 台北 18:00（>17:00，契約視為已收盤）

KNOWN_GAPS = {
    "fetch_twii_ohlcv uses host-local datetime.fromtimestamp(t).date() (no tz)",
    "update_macro_history.main() uses host-local date.today() and writes data_cache/metadata.json (not callable zero-I/O)",
    "fetch_twii_ohlcv stamps fetched_at from wall clock pd.Timestamp.now('UTC') (clock not injectable)",
    "_fetch_url_via_proxy performs network I/O (only callable via monkeypatch of the module attribute)",
    "no weekday / trading-calendar rule in fetch_twii_ohlcv or shared.twii_ohlc_contract",
    "metadata.json has no content hash / schema claim for twii_ohlcv (only row_count / last_updated)",
}


# ══════════════════════════════════════════════════════════════
# 護欄 fixtures（autouse）：禁網路、禁 Secrets
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


@pytest.fixture
def _host_tz(monkeypatch):
    """回傳 setter：在測試內釘住主機時區（os.environ['TZ'] + time.tzset），結束還原。"""
    if not hasattr(time, "tzset"):
        pytest.fail("time.tzset 不可用（非 POSIX）；本檔時區證據需要 POSIX")
    orig = os.environ.get("TZ")

    def _set(name: str) -> None:
        os.environ["TZ"] = name
        time.tzset()
    yield _set
    if orig is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = orig
    time.tzset()


def test_guard_no_secrets_and_network_blocked():
    for k in ("FINMIND_TOKEN", "PROXY_URL"):
        assert k not in os.environ
    assert not [k for k in os.environ if k.startswith("NAS_")]
    with pytest.raises(AssertionError, match="網路存取被禁止"):
        socket.create_connection(("example.com", 80))
    with pytest.raises(AssertionError, match="網路存取被禁止"):
        requests.get("http://example.invalid/")


# ══════════════════════════════════════════════════════════════
# 合成 Yahoo chart 與假回應
# ══════════════════════════════════════════════════════════════
def chart(ts, o, h, l, c, v=None, *, with_volume=True):
    quote = {"open": list(o), "high": list(h), "low": list(l), "close": list(c)}
    if with_volume:
        quote["volume"] = list(v) if v is not None else [1000] * len(ts)
    return {"chart": {"result": [{"timestamp": list(ts), "indicators": {"quote": [quote]}}], "error": None}}


def one_bar(ts=TS_THU_1119, o=100.0, h=110.0, l=90.0, c=105.0, v=5000):
    return chart([ts], [o], [h], [l], [c], [v])


class FakeResp:
    def __init__(self, data=None, status=200, bad_json=False):
        self.status_code, self._d, self._bad = status, data, bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._d


def run_fetch(monkeypatch, resp, start=dt.date(2026, 11, 19), end=dt.date(2026, 11, 20)):
    """以假 `_fetch_url_via_proxy`（模組屬性）取代網路層；回傳 (df, 捕捉到的 params)。"""
    seen = {}

    def fake(url, params=None, timeout=25):
        seen["url"], seen["params"] = url, params
        return resp
    monkeypatch.setattr(umh, "_fetch_url_via_proxy", fake)
    return umh.fetch_twii_ohlcv(start, end), seen


def oc(df):
    return read_outcome(df)[0]


def contract_args(df, *, fetched_at=FIXED_FETCHED_AT, as_of=None, today=TODAY):
    """把 df 轉成 validate_ohlc_window 參數；fetched_at 以固定值覆蓋（fetch 的 fetched_at 是牆鐘）。"""
    d = [str(x) for x in df["date"]]
    n = len(d)
    fa = fetched_at if isinstance(fetched_at, list) else [fetched_at] * n
    return (d, list(df["open"]), list(df["high"]), list(df["low"]), list(df["close"]), fa), {"as_of": as_of, "today": today}


def validate(df, **kw):
    a, k = contract_args(df, **kw)
    return C.validate_ohlc_window(*a, **k)


# ══════════════════════════════════════════════════════════════
# ① 空回應／缺 timestamp／chart.error（現行三態特徵化）
# ══════════════════════════════════════════════════════════════
def test_current_behavior_no_response_is_fetch_failed(monkeypatch):
    df, _ = run_fetch(monkeypatch, None)
    assert df.empty and oc(df) is FetchOutcome.FETCH_FAILED


def test_current_behavior_http_error_is_fetch_failed(monkeypatch):
    df, _ = run_fetch(monkeypatch, FakeResp(status=500))
    assert df.empty and oc(df) is FetchOutcome.FETCH_FAILED


def test_current_behavior_non_json_is_fetch_failed(monkeypatch):
    df, _ = run_fetch(monkeypatch, FakeResp(bad_json=True))
    assert df.empty and oc(df) is FetchOutcome.FETCH_FAILED


def test_current_behavior_chart_error_is_fetch_failed(monkeypatch):
    body = {"chart": {"result": None, "error": {"code": "Not Found", "description": "x"}}}
    df, _ = run_fetch(monkeypatch, FakeResp(body))
    assert df.empty and oc(df) is FetchOutcome.FETCH_FAILED
    assert "Not Found" in read_outcome(df)[1]


def test_current_behavior_missing_timestamp_is_undetermined(monkeypatch):
    body = {"chart": {"result": [{"indicators": {"quote": [{"close": []}]}}], "error": None}}
    df, _ = run_fetch(monkeypatch, FakeResp(body))
    assert df.empty and oc(df) is FetchOutcome.UNDETERMINED     # 與「區間無交易日」不可分


def test_current_behavior_empty_arrays_is_undetermined(monkeypatch):
    df, _ = run_fetch(monkeypatch, FakeResp(chart([], [], [], [], [])))
    assert df.empty and oc(df) is FetchOutcome.UNDETERMINED


def test_current_behavior_result_none_is_undetermined(monkeypatch):
    df, _ = run_fetch(monkeypatch, FakeResp({"chart": {"result": None, "error": None}}))
    assert df.empty and oc(df) is FetchOutcome.UNDETERMINED


def test_current_behavior_all_close_null_is_undetermined(monkeypatch):
    df, _ = run_fetch(monkeypatch, FakeResp(chart([TS_THU_1119], [1], [2], [1], [None])))
    assert df.empty and oc(df) is FetchOutcome.UNDETERMINED


# ══════════════════════════════════════════════════════════════
# ② 時間戳／時區邊界（known divergence 證據；非 PIT 證明）
# ══════════════════════════════════════════════════════════════
def _reference_taipei_date(ts: int) -> dt.date:
    """TARGET_STATE reference, NOT a production API：時間戳 → Asia/Taipei 日期（與主機 TZ 無關）。"""
    return dt.datetime.fromtimestamp(ts, tz=C.taipei_tz()).date()


def test_reference_taipei_date_boundary():
    assert _reference_taipei_date(TS_UTC_1559) == dt.date(2026, 11, 19)
    assert _reference_taipei_date(TS_UTC_1600) == dt.date(2026, 11, 20)


def _fetch_dates(monkeypatch, tzname, _host_tz, tss):
    _host_tz(tzname)
    body = chart(tss, [100] * len(tss), [110] * len(tss), [90] * len(tss), [105] * len(tss))
    df, seen = run_fetch(monkeypatch, FakeResp(body))
    return list(df["date"]), seen["params"]


def test_current_behavior_fetch_date_depends_on_host_tz(monkeypatch, _host_tz):
    """FACT：同一時間戳（UTC 16:00＝台北隔日 00:00）在兩種主機時區得到不同日期。"""
    d_utc, _ = _fetch_dates(monkeypatch, "UTC", _host_tz, [TS_UTC_1559, TS_UTC_1600])
    d_tpe, _ = _fetch_dates(monkeypatch, "Asia/Taipei", _host_tz, [TS_UTC_1559, TS_UTC_1600])
    assert d_utc == [dt.date(2026, 11, 19), dt.date(2026, 11, 19)]
    assert d_tpe == [dt.date(2026, 11, 19), dt.date(2026, 11, 20)]
    assert d_utc != d_tpe                                        # known divergence


def test_current_behavior_period_params_depend_on_host_tz(monkeypatch, _host_tz):
    """FACT：period1/period2（本地午夜 .timestamp()）也隨主機 TZ 位移 8 小時。"""
    _, p_utc = _fetch_dates(monkeypatch, "UTC", _host_tz, [TS_THU_1119])
    _, p_tpe = _fetch_dates(monkeypatch, "Asia/Taipei", _host_tz, [TS_THU_1119])
    assert p_utc["period1"] - p_tpe["period1"] == 8 * 3600
    assert p_utc["period2"] - p_tpe["period2"] == 8 * 3600
    assert p_utc["period1"] == _utc_ts(2026, 11, 19, 0, 0)


def test_current_behavior_date_today_depends_on_host_tz(monkeypatch, _host_tz):
    """FACT：`update_macro_history.main()` 用 date.today()（主機本地）；固定 time.time 後兩 TZ 結果不同。"""
    fixed = _utc_ts(2026, 11, 19, 17, 0)                         # 台北 11-20 01:00
    monkeypatch.setattr(time, "time", lambda: float(fixed))
    _host_tz("UTC")
    d_utc = dt.date.today()
    _host_tz("Asia/Taipei")
    d_tpe = dt.date.today()
    assert (d_utc, d_tpe) == (dt.date(2026, 11, 19), dt.date(2026, 11, 20))


@pytest.mark.xfail(strict=True, reason="known divergence: fetch_twii_ohlcv 以主機本地時區取日期，非 Asia/Taipei；"
                   "目標＝與主機 TZ 無關（#1199 7072858477 / 7072670677）")
def test_target_state_fetch_date_is_taipei_regardless_of_host_tz(monkeypatch, _host_tz):
    d_utc, _ = _fetch_dates(monkeypatch, "UTC", _host_tz, [TS_UTC_1559, TS_UTC_1600])
    assert d_utc == [_reference_taipei_date(t) for t in (TS_UTC_1559, TS_UTC_1600)]


def test_current_behavior_typical_bar_same_date_both_tz(monkeypatch, _host_tz):
    """典型 Yahoo 時間戳（01:00 UTC）在兩種主機時區日期相同（所以現況在 GH runner 上「僥倖」正確）。"""
    d_utc, _ = _fetch_dates(monkeypatch, "UTC", _host_tz, [TS_THU_1119])
    d_tpe, _ = _fetch_dates(monkeypatch, "Asia/Taipei", _host_tz, [TS_THU_1119])
    assert d_utc == d_tpe == [dt.date(2026, 11, 19)]


# ══════════════════════════════════════════════════════════════
# ③ 單日 ④ 週末 ⑤ 未來日（現行放行；契約部分攔截）
# ══════════════════════════════════════════════════════════════
def test_current_behavior_single_day_ok(monkeypatch, _host_tz):
    _host_tz("UTC")
    df, _ = run_fetch(monkeypatch, FakeResp(one_bar()))
    assert len(df) == 1 and df.loc[0, "source"] == "Yahoo:^TWII:chart"
    assert validate(df) == (True, C.OHLC_OK, "")


def test_current_behavior_fetched_at_is_wall_clock_tz_aware(monkeypatch, _host_tz):
    _host_tz("UTC")
    df, _ = run_fetch(monkeypatch, FakeResp(one_bar()))
    assert pd.Timestamp(df.loc[0, "fetched_at"]).tzinfo is not None   # 帶時區；但值是牆鐘（KNOWN_GAPS）


def test_current_behavior_weekend_bar_passes_both_fetch_and_contract(monkeypatch, _host_tz):
    """FACT：週六 K 棒既不被 fetch 剔除、也不被契約拒收（無 weekday 規則＝缺口，非期望行為）。"""
    _host_tz("UTC")
    df, _ = run_fetch(monkeypatch, FakeResp(one_bar(ts=TS_SAT_1121)))
    assert list(df["date"]) == [dt.date(2026, 11, 21)] and dt.date(2026, 11, 21).weekday() == 5
    assert validate(df, fetched_at="2026-11-22T10:00:00+00:00")[0] is True   # 抓取於 11-21 17:00（台北）之後


def test_current_behavior_future_bar_passes_fetch_but_contract_rejects(monkeypatch, _host_tz):
    _host_tz("UTC")
    df, _ = run_fetch(monkeypatch, FakeResp(one_bar(ts=TS_MON_1123)))
    assert list(df["date"]) == [dt.date(2026, 11, 23)]           # fetch 不濾未來日
    ok, code, _d = validate(df)
    assert (ok, code) == (False, C.FUTURE_DATE)


# ══════════════════════════════════════════════════════════════
# ⑥ 零／負價、high<low、close 超出範圍 ⑩ 契約拒收
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("o,h,l,c,code", [
    (100, 110, 90, 0, C.NON_POSITIVE),
    (-1, 110, 90, 105, C.NON_POSITIVE),
    (100, 90, 110, 100, C.OHLC_RELATION),       # high < low
    (100, 110, 90, 120, C.OHLC_RELATION),       # close > high
    (100, 110, 90, 80, C.OHLC_RELATION),        # close < low
    (120, 110, 90, 100, C.OHLC_RELATION),       # open > high
])
def test_current_behavior_bad_prices_pass_fetch_but_contract_rejects(monkeypatch, _host_tz, o, h, l, c, code):
    _host_tz("UTC")
    df, _ = run_fetch(monkeypatch, FakeResp(chart([TS_THU_1119], [o], [h], [l], [c])))
    assert len(df) == 1                                          # fetch 只 dropna(close)，不驗價格關係
    ok, got, _d = validate(df)
    assert (ok, got) == (False, code)


def test_current_behavior_null_open_passes_fetch_contract_rejects_not_finite(monkeypatch, _host_tz):
    _host_tz("UTC")
    df, _ = run_fetch(monkeypatch, FakeResp(chart([TS_THU_1119], [None], [110], [90], [105])))
    assert len(df) == 1 and pd.isna(df.loc[0, "open"])
    assert validate(df)[:2] == (False, C.NOT_FINITE)


def test_current_behavior_null_close_row_is_dropped_by_fetch(monkeypatch, _host_tz):
    _host_tz("UTC")
    body = chart([TS_THU_1119, TS_FRI_1120], [1, 2], [3, 3], [1, 1], [None, 2])
    df, _ = run_fetch(monkeypatch, FakeResp(body))
    assert list(df["date"]) == [dt.date(2026, 11, 20)]


@pytest.mark.parametrize("fa,code", [
    ("2026-11-20T10:00:00", C.FETCHED_AT_MISSING),                # naive
    (None, C.FETCHED_AT_MISSING),
    ("2026-11-19T08:00:00+00:00", C.INCOMPLETE_BAR),              # 台北 16:00 < 17:00（同日）
])
def test_contract_rejects_bad_fetched_at(monkeypatch, _host_tz, fa, code):
    _host_tz("UTC")
    df, _ = run_fetch(monkeypatch, FakeResp(one_bar()))
    assert validate(df, fetched_at=fa)[:2] == (False, code)


def test_contract_boundary_taipei_17h():
    """台北 16:59 不合格、17:00 合格（UTC 08:59 / 09:00）。"""
    row = (["2026-11-19"], [100.0], [110.0], [90.0], [105.0])
    bad = C.validate_ohlc_window(*row, ["2026-11-19T08:59:00+00:00"], as_of=None, today=TODAY)
    good = C.validate_ohlc_window(*row, ["2026-11-19T09:00:00+00:00"], as_of=None, today=TODAY)
    assert bad[:2] == (False, C.INCOMPLETE_BAR) and good[0] is True


def test_contract_rejects_empty_dup_unordered_asof():
    r = lambda d: (d, [1.0] * len(d), [2.0] * len(d), [1.0] * len(d), [1.5] * len(d), [FIXED_FETCHED_AT] * len(d))
    assert C.validate_ohlc_window(*r([]), as_of=None, today=TODAY)[1] == C.EMPTY
    assert C.validate_ohlc_window(*r(["2026-11-19", "2026-11-19"]), as_of=None, today=TODAY)[1] == C.DUPLICATE_DATE
    assert C.validate_ohlc_window(*r(["2026-11-20", "2026-11-19"]), as_of=None, today=TODAY)[1] == C.NOT_ASCENDING
    assert C.validate_ohlc_window(*r(["2026-11-19"]), as_of="2026-11-18", today=TODAY)[1] == C.AS_OF_MISMATCH
    assert C.validate_ohlc_window(["x"], [1.0], [2.0], [1.0], [1.5], [FIXED_FETCHED_AT],
                                  as_of=None, today=TODAY)[1] == C.BAD_DATE


def test_contract_rejects_future_date_even_when_fetched_after():
    ok, code, _d = C.validate_ohlc_window(["2026-11-23"], [1.0], [2.0], [1.0], [1.5], ["2026-11-24T10:00:00+00:00"],
                                          as_of=None, today=TODAY)
    assert (ok, code) == (False, C.FUTURE_DATE)


# ══════════════════════════════════════════════════════════════
# ⑦ volume==0／缺值（特徵化）
# ══════════════════════════════════════════════════════════════
def test_current_behavior_volume_zero_with_range_becomes_nan(monkeypatch, _host_tz):
    _host_tz("UTC")
    body = chart([TS_THU_1119, TS_FRI_1120], [100, 100], [110, 100], [90, 100], [105, 100], [0, 0])
    df, _ = run_fetch(monkeypatch, FakeResp(body))
    assert math.isnan(df.loc[0, "volume"])                       # high>low 且 0 → NaN（顯式）
    assert df.loc[1, "volume"] == 0                              # high==low（整日無成交）保留 0


def test_current_behavior_volume_missing_key_and_null(monkeypatch, _host_tz):
    _host_tz("UTC")
    df1, _ = run_fetch(monkeypatch, FakeResp(chart([TS_THU_1119], [1], [2], [1], [1.5], with_volume=False)))
    df2, _ = run_fetch(monkeypatch, FakeResp(chart([TS_THU_1119], [1], [2], [1], [1.5], [None])))
    assert len(df1) == 1 and df1["volume"].isna().all()
    assert len(df2) == 1 and df2["volume"].isna().all()


# ══════════════════════════════════════════════════════════════
# ⑧ 重複日衝突：producer keep-last vs publisher fail-closed
# ══════════════════════════════════════════════════════════════
def _mk(dates, closes, fa="2026-11-20T10:00:00+00:00"):
    return pd.DataFrame({"date": pd.to_datetime(dates).date, "open": closes, "high": [c + 1 for c in closes],
                         "low": [c - 1 for c in closes], "close": closes, "volume": [1000.0] * len(dates),
                         "source": "Yahoo:^TWII:chart", "fetched_at": fa})


def _pq(df) -> bytes:
    b = io.BytesIO()
    df.to_parquet(b, index=False)
    return b.getvalue()


def test_current_behavior_producer_merge_keeps_last_silently():
    old, new = _mk(["2026-11-18", "2026-11-19"], [100.0, 101.0]), _mk(["2026-11-19", "2026-11-20"], [999.0, 102.0])
    out = umh._merge_dedupe(old, new)
    assert list(out["close"]) == [100.0, 999.0, 102.0]           # 新覆蓋舊，無任何錯誤或旗標


def test_current_behavior_publisher_conflict_is_fail_closed():
    base, new = _mk(["2026-11-19"], [101.0]), _mk(["2026-11-19"], [999.0])
    with pytest.raises(pdp.PublishError, match="衝突"):
        pdp.union_parquet_by_date(_pq(base), _pq(new), ctx="twii")


def test_current_behavior_publisher_ignores_volatile_fetched_at_and_keeps_old():
    base = _mk(["2026-11-19"], [101.0], fa="2026-11-19T10:00:00+00:00")
    new = _mk(["2026-11-19", "2026-11-20"], [101.0, 102.0], fa="2026-11-21T10:00:00+00:00")
    out = pd.read_parquet(io.BytesIO(pdp.union_parquet_by_date(_pq(base), _pq(new), ctx="twii")))
    assert list(out["close"]) == [101.0, 102.0]
    assert out.loc[0, "fetched_at"] == "2026-11-19T10:00:00+00:00"   # 舊值優先


def test_current_behavior_publisher_rejects_duplicate_key_within_input():
    dup = _mk(["2026-11-19", "2026-11-19"], [1.0, 2.0])
    with pytest.raises(pdp.PublishError, match="重複"):
        pdp.union_parquet_by_date(_pq(_mk(["2026-11-18"], [1.0])), _pq(dup), ctx="twii")


def test_current_behavior_fetch_emits_duplicate_dates_without_dedupe(monkeypatch, _host_tz):
    """FACT：同一主機日內兩根時間戳 → fetch 輸出重複日期（無 dedupe、無錯誤）。"""
    _host_tz("UTC")
    body = chart([_utc_ts(2026, 11, 19, 1), _utc_ts(2026, 11, 19, 6)], [1, 1], [2, 2], [1, 1], [1.5, 1.6])
    df, _ = run_fetch(monkeypatch, FakeResp(body))
    assert list(df["date"]) == [dt.date(2026, 11, 19)] * 2


@pytest.mark.xfail(strict=True, reason="known divergence: producer _merge_dedupe 同日衝突 keep-last 靜默覆蓋；"
                   "目標＝fail-closed 與 publisher 一致（#1199 7072858477 / 7072670677）")
def test_target_state_producer_merge_conflict_fails_closed():
    old, new = _mk(["2026-11-19"], [101.0]), _mk(["2026-11-19"], [999.0])
    with pytest.raises(Exception):
        umh._merge_dedupe(old, new)


@pytest.mark.xfail(strict=True, reason="known divergence: fetch_twii_ohlcv 會輸出重複日期；"
                   "目標＝重複日 fail-closed（#1199 7072858477 / 7072670677）")
def test_target_state_fetch_rejects_duplicate_dates(monkeypatch, _host_tz):
    _host_tz("UTC")
    body = chart([_utc_ts(2026, 11, 19, 1), _utc_ts(2026, 11, 19, 6)], [1, 1], [2, 2], [1, 1], [1.5, 1.6])
    df, _ = run_fetch(monkeypatch, FakeResp(body))
    assert df.empty or not df["date"].duplicated().any()


def _patch_cache(monkeypatch, tmp_path):
    cd = tmp_path / "data_cache"
    cd.mkdir()
    monkeypatch.setattr(umh, "CACHE_DIR", cd)
    assert str(umh.CACHE_DIR).startswith(str(tmp_path))          # 絕不寫真實 data_cache
    return cd


@pytest.mark.xfail(strict=True, reason="known divergence: update_one 對與既有檔同日衝突的新 bar 靜默覆蓋既有值；"
                   "目標＝fail-closed／既有值不變（#1199 7072858477 / 7072670677）")
def test_target_state_update_one_does_not_overwrite_existing_day(monkeypatch, tmp_path, _host_tz):
    _host_tz("UTC")
    cd = _patch_cache(monkeypatch, tmp_path)
    _mk(["2026-11-18"], [100.0]).to_parquet(cd / "twii_ohlcv.parquet", index=False)
    body = chart([_utc_ts(2026, 11, 18), _utc_ts(2026, 11, 19)], [1, 1], [900, 900], [1, 1], [500.0, 501.0])
    monkeypatch.setattr(umh, "_fetch_url_via_proxy", lambda *a, **k: FakeResp(body))
    try:
        umh.update_one("twii_ohlcv", dt.date(2026, 11, 20), False, 20, "")
    except Exception:
        pass
    kept = pd.read_parquet(cd / "twii_ohlcv.parquet")
    assert float(kept.loc[kept["date"] == dt.date(2026, 11, 18), "close"].iloc[0]) == 100.0


def test_current_behavior_update_one_overwrites_existing_day(monkeypatch, tmp_path, _host_tz):
    """特徵化 xfail 的反面：現況確實覆蓋（不是期望行為）。"""
    _host_tz("UTC")
    cd = _patch_cache(monkeypatch, tmp_path)
    _mk(["2026-11-18"], [100.0]).to_parquet(cd / "twii_ohlcv.parquet", index=False)
    body = chart([_utc_ts(2026, 11, 18), _utc_ts(2026, 11, 19)], [1, 1], [900, 900], [1, 1], [500.0, 501.0])
    monkeypatch.setattr(umh, "_fetch_url_via_proxy", lambda *a, **k: FakeResp(body))
    meta = umh.update_one("twii_ohlcv", dt.date(2026, 11, 20), False, 20, "")
    kept = pd.read_parquet(cd / "twii_ohlcv.parquet")
    assert float(kept.loc[kept["date"] == dt.date(2026, 11, 18), "close"].iloc[0]) == 500.0
    assert meta["row_count"] == 2 and meta["last_updated"] == "2026-11-19" and meta["last_error"] is None


# ══════════════════════════════════════════════════════════════
# ⑨ 合成 metadata 與 publisher 對帳（tmp_path；零網路、零 git）
# ══════════════════════════════════════════════════════════════
def _reference_expected_metadata(parquet_bytes: bytes) -> dict:
    """TARGET_STATE reference, NOT a production API：由 parquet 位元組重算 row_count／last_updated／sha256。"""
    df = pd.read_parquet(io.BytesIO(parquet_bytes))
    return {"row_count": len(df), "last_updated": pd.to_datetime(df["date"]).max().date().isoformat(),
            "sha256": hashlib.sha256(parquet_bytes).hexdigest()}


def _write_meta(root: Path, entry: dict) -> Path:
    p = root / "data_cache" / "metadata.json"
    p.write_text(json.dumps({"updated_at": "2026-11-20T10:00:00+00:00", "datasets": {"twii_ohlcv": entry}},
                            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _synthetic_published_tree(tmp_path):
    (tmp_path / "data_cache").mkdir()
    df = _mk(["2026-11-18", "2026-11-19", "2026-11-20"], [100.0, 101.0, 102.0])
    raw = _pq(df)
    (tmp_path / "data_cache" / "twii_ohlcv.parquet").write_bytes(raw)
    return raw


def test_current_behavior_metadata_verify_passes_on_consistent_claims(tmp_path):
    raw = _synthetic_published_tree(tmp_path)
    ref = _reference_expected_metadata(raw)
    _write_meta(tmp_path, {"name": "twii_ohlcv", "last_updated": ref["last_updated"],
                           "row_count": ref["row_count"], "last_error": None})
    assert pdp.verify_metadata(tmp_path, ["data_cache/"]) == []


def test_current_behavior_metadata_verify_flags_row_count_and_last_updated_drift(tmp_path):
    _synthetic_published_tree(tmp_path)
    _write_meta(tmp_path, {"name": "twii_ohlcv", "last_updated": "2026-11-19", "row_count": 2, "last_error": None})
    bad = pdp.verify_metadata(tmp_path, ["data_cache/"])
    assert any("row_count" in b for b in bad) and any("last_updated" in b for b in bad)


def test_current_behavior_reconcile_rewrites_claims_from_data(tmp_path):
    raw = _synthetic_published_tree(tmp_path)
    mp = _write_meta(tmp_path, {"name": "twii_ohlcv", "last_updated": "2026-11-19", "row_count": 2, "last_error": None})
    fixes = pdp.reconcile_metadata(tmp_path, ["data_cache/"], log=lambda *_: None)
    assert len(fixes) == 2
    got = json.loads(mp.read_text(encoding="utf-8"))["datasets"]["twii_ohlcv"]
    ref = _reference_expected_metadata(raw)
    assert (got["row_count"], got["last_updated"]) == (ref["row_count"], ref["last_updated"])
    assert pdp.verify_metadata(tmp_path, ["data_cache/"]) == []


def test_current_behavior_missing_parquet_with_claims_is_flagged(tmp_path):
    (tmp_path / "data_cache").mkdir()
    _write_meta(tmp_path, {"name": "twii_ohlcv", "last_updated": "2026-11-19", "row_count": 2, "last_error": None})
    assert pdp.verify_metadata(tmp_path, ["data_cache/"])


def test_current_behavior_update_one_meta_reconciles_with_publisher(monkeypatch, tmp_path, _host_tz):
    """producer 的 update_one metadata ↔ publisher 對帳（均在 tmp_path）。"""
    _host_tz("UTC")
    cd = _patch_cache(monkeypatch, tmp_path)
    body = chart([TS_THU_1119, TS_FRI_1120], [100, 101], [110, 111], [90, 91], [105, 106])
    monkeypatch.setattr(umh, "_fetch_url_via_proxy", lambda *a, **k: FakeResp(body))
    meta = umh.update_one("twii_ohlcv", dt.date(2026, 11, 21), True, 1, "")
    _write_meta(tmp_path, meta)
    assert pdp.verify_metadata(tmp_path, ["data_cache/"]) == []
    raw = (cd / "twii_ohlcv.parquet").read_bytes()
    ref = _reference_expected_metadata(raw)
    assert (meta["row_count"], meta["last_updated"]) == (ref["row_count"], ref["last_updated"]) == (2, "2026-11-20")
    assert "sha256" not in meta                                  # KNOWN_GAPS：現行 metadata 無內容雜湊


def test_target_state_reference_hash_detects_content_change():
    a = _reference_expected_metadata(_pq(_mk(["2026-11-19"], [101.0])))
    b = _reference_expected_metadata(_pq(_mk(["2026-11-19"], [999.0])))
    assert (a["row_count"], a["last_updated"]) == (b["row_count"], b["last_updated"])   # 現行 claims 看不出
    assert a["sha256"] != b["sha256"]                                                   # 目標：雜湊可看出


# ══════════════════════════════════════════════════════════════
# 缺口：以 AST／事實釘住（缺口修掉時這些測試會轉紅，提醒更新契約）
# ══════════════════════════════════════════════════════════════
def _fn_ast(fn):
    return ast.parse(textwrap.dedent(inspect.getsource(fn)))


def _calls(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f, parts = n.func, []
            while isinstance(f, ast.Attribute):
                parts.append(f.attr)
                f = f.value
            if isinstance(f, ast.Name):
                parts.append(f.id)
            out.append((".".join(reversed(parts)), n))
    return out


def test_known_gap_fetch_uses_naive_fromtimestamp_and_wall_clock():
    calls = _calls(_fn_ast(umh.fetch_twii_ohlcv))
    ft = [n for name, n in calls if name.endswith("fromtimestamp")]
    assert ft and all(len(n.args) == 1 and not n.keywords for n in ft)       # 無 tz 參數
    assert any(name.endswith("Timestamp.now") for name, _ in calls)           # 牆鐘 fetched_at
    assert any(name == "_fetch_url_via_proxy" for name, _ in calls)           # 網路只能靠 monkeypatch


def test_known_gap_main_is_not_zero_io_callable():
    calls = {name for name, _ in _calls(_fn_ast(umh.main))}
    assert "_dt.date.today" in calls                                          # 主機本地今日
    assert "META_PATH.write_text" in calls and "CACHE_DIR.mkdir" in calls     # 寫 data_cache
    assert "update_one" in calls


def test_known_gap_fetch_url_via_proxy_has_network_io():
    names = {name for name, _ in _calls(_fn_ast(umh._fetch_url_via_proxy))}
    assert "fetch_url" in names and "requests.get" in names


def test_known_gap_no_weekday_rule_anywhere():
    for fn in (umh.fetch_twii_ohlcv, C.validate_ohlc_window):
        attrs = {n.attr for n in ast.walk(_fn_ast(fn)) if isinstance(n, ast.Attribute)}
        assert not ({"weekday", "isoweekday", "dayofweek"} & attrs)


def test_known_gaps_registry_is_pinned():
    assert len(KNOWN_GAPS) == 6          # 變動需同步更新回報（待第二階段另授權抽離純函式）
