# -*- coding: utf-8 -*-
"""資料層修錯（2026-09-28，CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）三條：

  · **D2-f6** `macro_core.fetch_fred`（函式體內 30 分鐘成功快取 `_FRED_CACHE`，外層 `@monitored`）：
    修前 fetch_url 回 None／JSON 解析失敗／observations 為空三個出口**都不記退避** →
    每呼叫一次就再走一次 fetch_url（v1 風險雷達每輪 rerun 呼叫 2 次、每次 timeout 20 秒）。
    其中「回 None」那條每次都真的重打上游（實測 5 次呼叫＝15 次 GET＋5 次 NAS 中繼）；另兩條只會在
    HTTP 200 時出現，300 秒內的實際 GET 本來就被 fetch_url 的 URL 快取擋住 —— 對它們加冷卻的效果是
    不再重走 fetch_url／重解析，且退避不再依賴 URL 快取的存活（與 D2-f2 一致）。
    現在三者都寫進 `_FRED_FAIL_CACHE`（同 D2-f2：同一把鎖、同一個鍵、同一個時點＝本次呼叫的 now）：
    冷卻期內不重打、回同一種空 DataFrame、期滿重抓、成功即清。「observations 為空」算失敗的
    理由寫在 macro_core 該出口的註解（既有 FE-20 註與 success_check 早就把它當失敗路徑）。
    冷卻期回的空 DataFrame 照樣被 `@monitored` 記成 failed（`TestD2f6MonitoredStillFailed`）。
  · **D2-f10** `macro_core.fetch_yf_ohlcv`（沒有成功快取）：fetch_url 回 None／解析失敗兩個出口記
    退避（`_YF_OHLCV_FAIL_CACHE`）。因為沒有成功快取可以「先查」，另以成功世代防「並行時晚一步
    寫入的失敗蓋掉剛發生的成功」（`TestD2f10Race`）。成功路徑照舊（不加快取）。
  · **D2-f3** `macro_alert._yf_latest`（`st.cache_data` 30 分鐘）：結果含 None（任一檔抓不到）時改拋
    `_YfLatestIncomplete`（st.cache_data 不快取例外），`fetch_macro_snapshot` 接住取 `.payload` ——
    回傳與修前逐字相同，只差不再被快取。重算時不轟炸上游：已取到的檔命中 L1 1 小時成功快取、
    抓不到的檔落在 L1 退避（`TestD2f3NoBombardment` 走真的 L1；`TestUpstreamHttpCount`
    走真的 fetch_url ＋ 假 HTTP session，數到實際 GET 次數）。

「修前」的回傳一律用**獨立寫出的期望值**比對（不從被測檔推導），來源是 origin/main 修前原始碼的字面。
不觸網：一律換掉 fetch_url、L1 批次函式或 HTTP session。
property 式（`TestRandomizedModel`，本 repo 無 hypothesis，改用固定 seed 的隨機序列 vs 參考模型）。
突變測試（`TestMutations`）：把修復改回修前 → 本檔對應斷言所擋的失效確實出現。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import random
import sys
import threading
import time
import types

import pandas as pd
import pytest
import requests

import shared.fetch_monitor as FM
import src.data.macro.macro_alert as MA
import src.data.macro.macro_core as MC
import src.data.proxy.proxy_helper as PH
from shared.fail_cooldown import FAIL_COOLDOWN_SEC, CachedFailure
from shared.ttls import TTL_30MIN


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str], tag: str) -> types.ModuleType:
    """同 tests/test_d3_backoff_d2f1_d2f2.py：原始碼字面替換後另建一份模組（真模組不動）。

    `tag` 讓每個突變體有自己的模組名 —— `st.cache_data` 以「模組名＋函式名＋原始碼」當快取鍵。
    """
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_d3a_{tag}_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ══════════════════════════════════════════════════════════════════
# 共用替身與夾具
# ══════════════════════════════════════════════════════════════════
_T0 = 1767225600          # 2026-01-01T00:00:00Z —— 測資一律固定日期，不吃執行當天
_DAY = 86400
_FROZEN = pd.Timestamp("2026-09-28T01:02:03.456789", tz="UTC")


class _Raw:
    """`r.json()` 回任意結構（或拋例外）的回應替身。"""

    def __init__(self, payload=None, exc: Exception | None = None):
        self._payload = payload
        self._exc = exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._payload


def _counting_fetch(plan: dict, calls: dict):
    lock = threading.Lock()

    def _fetch(*_a, **_k):
        with lock:
            calls["n"] += 1
        return plan["resp"]
    return _fetch


@pytest.fixture
def clock(monkeypatch):
    """可手動推進的假時鐘：被測三支函式都以 `time.time()` 判斷冷卻期／TTL。
    （st.cache_data 的 TTL 用 time.monotonic，不受影響 —— 本檔只靠「清快取」控制它。）"""
    t = {"now": float(_T0 + 300 * _DAY)}
    monkeypatch.setattr(time, "time", lambda: t["now"])
    return t


@pytest.fixture
def frozen_now(monkeypatch):
    """`fetched_at` 取 `pd.Timestamp.now("UTC")` —— 凍結後才能與修前的期望值逐字比。"""
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: _FROZEN))
    return _FROZEN


@pytest.fixture
def registry(monkeypatch):
    """隔離 `@monitored` 登錄表：本檔要讀 fetch_fred 那一盞；突變模組重跑 `@monitored` 也不污染別的測試。"""
    snap = {k: dict(v) for k, v in FM._MONITOR_REGISTRY.items()}
    monkeypatch.setattr(FM, "_MONITOR_REGISTRY", snap)
    return snap


def _assert_empty_df(df) -> None:
    """修前 fetch_fred／fetch_yf_ohlcv 的失敗出口都是 `return pd.DataFrame()` —— 逐字比。"""
    ref = pd.DataFrame()
    assert type(df) is pd.DataFrame
    assert repr(df) == repr(ref)
    pd.testing.assert_frame_equal(df, ref)
    assert type(df.index) is type(ref.index) and list(df.columns) == [] and df.attrs == {}


def test_cooldown_seconds_is_the_existing_ssot_constant():
    """沿用既有冷卻秒數常數（`shared.fail_cooldown.FAIL_COOLDOWN_SEC`），不另立 magic number。"""
    assert MC._FAIL_COOLDOWN_SEC is FAIL_COOLDOWN_SEC


# ══════════════════════════════════════════════════════════════════
# D2-f6 fetch_fred
# ══════════════════════════════════════════════════════════════════
_FRED_KEY = ("DGS10", "k-test", 120)


def _obs(rows) -> dict:
    """FRED observations 的真實樣態（含 realtime_start/realtime_end）。rows = [(date, value 字串), ...]。"""
    return {"observations": [{"realtime_start": "2026-09-28", "realtime_end": "2026-09-28",
                              "date": d, "value": v} for d, v in rows]}


def _fred_ok(rows) -> _Raw:
    return _Raw(_obs(rows))


def _fred_expected(rows_kept, series: str = "DGS10") -> pd.DataFrame:
    """修前成功路徑的字面：去掉 '.' → value 轉 float64 → date 轉時間 → dropna → 依 date 升冪 →
    reset_index → 補 source / fetched_at。`rows_kept` 為**已排序、已去掉 '.'** 的 (date, float)。"""
    n = len(rows_kept)
    df = pd.DataFrame({
        "realtime_start": ["2026-09-28"] * n,
        "realtime_end": ["2026-09-28"] * n,
        "date": pd.to_datetime(pd.Series([d for d, _ in rows_kept])),
        "value": pd.Series([v for _, v in rows_kept], dtype="float64"),
    })
    df["source"] = f"FRED:{series}"
    df["fetched_at"] = _FROZEN.isoformat()
    return df


#: 走「JSON 解析失敗」出口（`r.json().get(...)` 拋例外）的三種樣態
_FRED_PARSE_FAILURES = {
    "json_decode": _Raw(exc=ValueError("Expecting value: line 1 column 1 (char 0)")),
    "json_is_list": _Raw(["unexpected"]),        # list 沒有 .get → AttributeError
    "json_is_null": _Raw(None),                  # None.get → AttributeError
}
#: 走「observations 為空」出口的三種樣態（HTTP 200 才會走到這裡）
_FRED_OBS_EMPTY = {
    "empty_list": _Raw({"observations": []}),
    "key_missing": _Raw({"count": 0}),
    "null": _Raw({"observations": None}),
}


def _use_fred(mod, monkeypatch, fetch) -> None:
    monkeypatch.setattr(mod, "fetch_url", fetch)
    monkeypatch.setattr(mod, "_FRED_CACHE", {})
    monkeypatch.setattr(mod, "_FRED_FAIL_CACHE", {})


@pytest.fixture
def fred(monkeypatch):
    """換掉 L1 `fetch_url`：`plan["resp"]` 是每次要回的東西（None ＝ 抓取失敗）。"""
    plan, calls = {"resp": None}, {"n": 0}
    _use_fred(MC, monkeypatch, _counting_fetch(plan, calls))
    return plan, calls


def _call_fred(mod=MC):
    return mod.fetch_fred(*_FRED_KEY)


class TestD2f6FredNoneBackoff:
    def test_none_backs_off_within_cooldown(self, fred, clock):
        plan, calls = fred
        _assert_empty_df(_call_fred())
        assert calls["n"] == 1
        assert _FRED_KEY not in MC._FRED_CACHE, "失敗不得進 30 分鐘成功快取"
        assert MC._FRED_FAIL_CACHE == {_FRED_KEY: clock["now"]}, \
            "與 _FRED_CACHE 同一個鍵、值＝本次呼叫的時點（同 D2-f2）"
        clock["now"] += FAIL_COOLDOWN_SEC - 1
        for _ in range(3):
            _assert_empty_df(_call_fred())
        assert calls["n"] == 1, "冷卻期內不重打上游"

    def test_none_refetches_after_cooldown_then_recovers(self, fred, clock, frozen_now):
        plan, calls = fred
        _call_fred()
        clock["now"] += FAIL_COOLDOWN_SEC            # `<` 比較：剛好滿即過期（同 D2-f2）
        _assert_empty_df(_call_fred())
        assert calls["n"] == 2, "冷卻期過 → 重打"
        assert MC._FRED_FAIL_CACHE == {_FRED_KEY: clock["now"]}, "仍失敗 → 以這次時點重新起算"
        _call_fred()
        assert calls["n"] == 2, "新的冷卻期內又不重打"
        clock["now"] += FAIL_COOLDOWN_SEC
        plan["resp"] = _fred_ok([("2026-01-05", "4.20"), ("2026-01-02", "4.10")])
        got = _call_fred()
        assert calls["n"] == 3, "恢復 → 打一次"
        pd.testing.assert_frame_equal(got, _fred_expected([("2026-01-02", 4.10), ("2026-01-05", 4.20)]))
        assert MC._FRED_FAIL_CACHE == {}, "成功即解除退避"
        _call_fred()
        assert calls["n"] == 3, "成功照舊入 30 分鐘快取"


class TestD2f6FredParseFailureBackoff:
    @pytest.mark.parametrize("kind", sorted(_FRED_PARSE_FAILURES))
    def test_parse_failure_backs_off_then_refetches(self, kind, fred, clock, capsys):
        plan, calls = fred
        plan["resp"] = _FRED_PARSE_FAILURES[kind]
        _assert_empty_df(_call_fred())
        assert "[macro_core/fred] DGS10 JSON 解析失敗" in capsys.readouterr().out, "確實走解析失敗出口"
        assert calls["n"] == 1 and _FRED_KEY not in MC._FRED_CACHE
        assert MC._FRED_FAIL_CACHE == {_FRED_KEY: clock["now"]}
        clock["now"] += FAIL_COOLDOWN_SEC - 1
        _assert_empty_df(_call_fred())
        assert calls["n"] == 1, "冷卻期內不重打上游"
        clock["now"] += 1
        _assert_empty_df(_call_fred())
        assert calls["n"] == 2, "冷卻期過 → 重打"
        clock["now"] += FAIL_COOLDOWN_SEC
        plan["resp"] = _fred_ok([("2026-01-02", "1.5")])
        assert list(_call_fred()["value"]) == [1.5] and calls["n"] == 3
        assert MC._FRED_FAIL_CACHE == {}, "成功即解除退避"


class TestD2f6FredObservationsEmptyBackoff:
    """「observations 為空」依既有語意算失敗（理由見 macro_core 該出口註解），同樣退避。"""

    @pytest.mark.parametrize("kind", sorted(_FRED_OBS_EMPTY))
    def test_obs_empty_backs_off_then_refetches(self, kind, fred, clock, capsys):
        plan, calls = fred
        plan["resp"] = _FRED_OBS_EMPTY[kind]
        _assert_empty_df(_call_fred())
        assert "[macro_core/fred] DGS10 observations 為空" in capsys.readouterr().out, \
            "確實走 observations 為空出口"
        assert calls["n"] == 1 and _FRED_KEY not in MC._FRED_CACHE, "修前就不入成功快取，現在也不入"
        assert MC._FRED_FAIL_CACHE == {_FRED_KEY: clock["now"]}
        clock["now"] += FAIL_COOLDOWN_SEC - 1
        _assert_empty_df(_call_fred())
        assert calls["n"] == 1, "冷卻期內不重打上游"
        clock["now"] += 1
        plan["resp"] = _fred_ok([("2026-01-02", "2.5")])
        assert list(_call_fred()["value"]) == [2.5] and calls["n"] == 2, "冷卻期過 → 重打、恢復"
        assert MC._FRED_FAIL_CACHE == {}


class TestD2f6FredSuccessUnchanged:
    def test_success_identical_to_prefix_and_ttl_unchanged(self, fred, clock, frozen_now):
        plan, calls = fred
        plan["resp"] = _fred_ok([("2026-01-05", "4.61"), ("2026-01-02", "."), ("2026-01-01", "4.57")])
        got = _call_fred()
        want = _fred_expected([("2026-01-01", 4.57), ("2026-01-05", 4.61)])
        pd.testing.assert_frame_equal(got, want, check_index_type=True)
        assert repr(got) == repr(want) and list(got.columns) == list(want.columns)
        assert MC._FRED_FAIL_CACHE == {}, "成功不寫失敗紀錄"
        # TTL 用修前的值（30 分鐘）推進，不讀被測模組的常數 —— 否則 TTL 被改了也驗不出來
        assert MC._FRED_TTL == TTL_30MIN, "成功快取 TTL 同修前（30 分鐘）"
        clock["now"] += TTL_30MIN - 1
        pd.testing.assert_frame_equal(_call_fred(), want)
        assert calls["n"] == 1, "TTL 內照舊命中成功快取"
        clock["now"] += 1
        _call_fred()
        assert calls["n"] == 2, "TTL 滿 → 重抓（TTL 不變）"

    def test_all_missing_values_path_is_untouched(self, fred, clock):
        """observations 有列、但值全是 '.'（FRED 缺值記號）：修前走成功路徑、空結果照樣入 30 分鐘快取。
        這一條**不屬於** D2-f6 的三個失敗出口，本次未動 —— 釘住現行語意，避免被順手改掉。"""
        plan, calls = fred
        plan["resp"] = _fred_ok([("2026-01-02", "."), ("2026-01-03", ".")])
        got = _call_fred()
        assert got.empty and list(got.columns) == \
            ["realtime_start", "realtime_end", "date", "value", "source", "fetched_at"]
        assert MC._FRED_FAIL_CACHE == {} and _FRED_KEY in MC._FRED_CACHE
        _call_fred()
        assert calls["n"] == 1

    def test_fresh_success_wins_over_leftover_failure_record(self, fred, clock):
        """先查成功快取、再查退避：殘留的失敗紀錄（例：並行呼叫晚一步寫入）擋不住已快取的成功。"""
        plan, calls = fred
        plan["resp"] = _fred_ok([("2026-01-02", "1.0")])
        _call_fred()
        MC._FRED_FAIL_CACHE[_FRED_KEY] = clock["now"]
        assert list(_call_fred()["value"]) == [1.0] and calls["n"] == 1

    def test_success_after_failure_is_not_tainted(self, fred, clock):
        """失敗 → 冷卻期滿 → 成功：之後上游再掛，TTL 內仍回那份成功、不重打。"""
        plan, calls = fred
        _call_fred()
        clock["now"] += FAIL_COOLDOWN_SEC
        plan["resp"] = _fred_ok([("2026-01-02", "3.0")])
        assert list(_call_fred()["value"]) == [3.0]
        plan["resp"] = None
        clock["now"] += TTL_30MIN - 1
        assert list(_call_fred()["value"]) == [3.0] and calls["n"] == 2

    def test_backoff_is_per_key(self, fred, clock):
        """鍵 ＝ (series_id, api_key, n)：一個鍵失敗不擋別的 series、別的 n、別的 key。"""
        plan, calls = fred
        _call_fred()
        plan["resp"] = _fred_ok([("2026-01-02", "1.0")])
        assert not MC.fetch_fred("BAMLH0A0HYM2", "k-test", 120).empty
        assert not MC.fetch_fred("DGS10", "k-test", 60).empty
        assert not MC.fetch_fred("DGS10", "k-other", 120).empty
        _assert_empty_df(_call_fred())
        assert calls["n"] == 4, "原鍵仍在冷卻期 → 不打"

    def test_no_api_key_path_unchanged(self, fred, clock, capsys):
        plan, calls = fred
        _assert_empty_df(MC.fetch_fred("DGS10", "", 120))
        assert "[macro_core/fred] DGS10 跳過:無 api_key" in capsys.readouterr().out
        assert calls["n"] == 0 and MC._FRED_FAIL_CACHE == {}, "沒打上游 → 不記退避（同修前：直接回空）"


class TestD2f6MonitoredStillFailed:
    """外層 `@monitored('fetch_fred', success_check=...)`：冷卻期回的失敗仍記 failed，資料體檢不會亮綠。"""

    @pytest.mark.parametrize("fail", ["fetch_none", "parse_failure", "obs_empty"])
    def test_cooldown_hit_is_recorded_as_failed(self, fail, fred, clock, registry):
        plan, calls = fred
        plan["resp"] = {"fetch_none": None,
                        "parse_failure": _FRED_PARSE_FAILURES["json_decode"],
                        "obs_empty": _FRED_OBS_EMPTY["empty_list"]}[fail]
        _call_fred()
        assert FM.get_monitor_registry()["fetch_fred"]["last_status"] == "failed"
        # 先讓這一盞轉綠（別的 series 成功），再看冷卻期那一次會不會把它拉回 failed
        plan["resp"] = _fred_ok([("2026-01-02", "1.0")])
        MC.fetch_fred("BAMLH0A0HYM2", "k-test", 120)
        assert FM.get_monitor_registry()["fetch_fred"]["last_status"] == "ok"
        n = calls["n"]
        _assert_empty_df(_call_fred())
        assert calls["n"] == n, "確實走冷卻期那一條（沒打上游）"
        ent = FM.get_monitor_registry()["fetch_fred"]
        assert ent["last_status"] == "failed", "冷卻期回的空結果不得在資料體檢顯示成成功"
        assert ent["last_rows"] == 0 and ent["last_error"]


class TestD2f6Concurrency:
    def test_parallel_failures_no_deadlock_and_backoff_holds(self, fred, clock):
        plan, calls = fred
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        results, errors = [], []

        def _worker():
            try:
                barrier.wait(timeout=5)
                results.append(_call_fred())
            except Exception as e:  # noqa: BLE001 — 收集起來讓斷言報出來
                errors.append(e)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert not any(t.is_alive() for t in threads), "不得死鎖"
        assert errors == [] and len(results) == n_threads
        for df in results:
            _assert_empty_df(df)
        assert 1 <= calls["n"] <= n_threads
        assert MC._FRED_FAIL_CACHE == {_FRED_KEY: clock["now"]}
        n = calls["n"]
        _call_fred()
        assert calls["n"] == n, "並行失敗之後：冷卻期內不再重打"


# ══════════════════════════════════════════════════════════════════
# D2-f10 fetch_yf_ohlcv
# ══════════════════════════════════════════════════════════════════
_OHLCV_KEY = ("^TWII", "9mo", "1d")


def _chart(rows) -> dict:
    """Yahoo Chart API 成功回應。rows = [(ts, open, high, low, close, volume)]（值可為 None）。"""
    return {"chart": {"result": [{
        "timestamp": [r[0] for r in rows],
        "indicators": {"quote": [{
            "open": [r[1] for r in rows], "high": [r[2] for r in rows],
            "low": [r[3] for r in rows], "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows]}]}}]}}


_ROWS = [(_T0, 9.5, 10.5, 9.0, 10.0, 1000),
         (_T0 + _DAY, 10.0, 11.0, 9.5, None, 1100),       # close 缺 → 修前 dropna 掉
         (_T0 + 2 * _DAY, 11.5, 12.5, 11.0, 12.0, 1200)]


def _ohlcv_expected(rows_kept, ticker="^TWII", range_="9mo", interval="1d") -> pd.DataFrame:
    """修前成功路徑的字面：index＝timestamp(秒) → 五欄 → dropna(Close) → 補 source / fetched_at。"""
    df = pd.DataFrame({
        "Open": [r[1] for r in rows_kept], "High": [r[2] for r in rows_kept],
        "Low": [r[3] for r in rows_kept], "Close": [r[4] for r in rows_kept],
        "Volume": [r[5] for r in rows_kept],
    }, index=pd.to_datetime([r[0] for r in rows_kept], unit="s"))
    df["source"] = f"Yahoo:chart:{ticker}:{range_}:{interval}"
    df["fetched_at"] = _FROZEN.isoformat()
    return df


#: 走「解析失敗」出口（try 區塊內拋例外）的四種真實樣態
_OHLCV_PARSE_FAILURES = {
    "json_decode": _Raw(exc=ValueError("Expecting value: line 1 column 1 (char 0)")),
    "yahoo_error_result_null": _Raw({"chart": {"result": None, "error": {
        "code": "Not Found", "description": "No data found, symbol may be delisted"}}}),
    "missing_indicators": _Raw({"chart": {"result": [{"timestamp": [_T0]}]}}),
    "length_mismatch": _Raw({"chart": {"result": [{
        "timestamp": [_T0], "indicators": {"quote": [{"close": [1.0, 2.0]}]}}]}}),
}


def _use_ohlcv(mod, monkeypatch, fetch) -> None:
    monkeypatch.setattr(mod, "fetch_url", fetch)
    monkeypatch.setattr(mod, "_YF_OHLCV_FAIL_CACHE", {})
    monkeypatch.setattr(mod, "_YF_OHLCV_OK_GEN_CACHE", {})


@pytest.fixture
def ohlcv(monkeypatch):
    plan, calls = {"resp": None}, {"n": 0}
    _use_ohlcv(MC, monkeypatch, _counting_fetch(plan, calls))
    return plan, calls


def _call_ohlcv(mod=MC):
    return mod.fetch_yf_ohlcv("^TWII", range_="9mo", interval="1d")


class TestD2f10OhlcvNoneBackoff:
    def test_none_backs_off_within_cooldown(self, ohlcv, clock):
        plan, calls = ohlcv
        _assert_empty_df(_call_ohlcv())
        assert calls["n"] == 1
        assert MC._YF_OHLCV_FAIL_CACHE == {_OHLCV_KEY: clock["now"]}, "鍵＝(ticker, range_, interval)"
        clock["now"] += FAIL_COOLDOWN_SEC - 1
        for _ in range(3):
            _assert_empty_df(_call_ohlcv())
        assert calls["n"] == 1, "冷卻期內不重打上游（修前：每呼叫一次打一次）"

    def test_none_refetches_after_cooldown_then_recovers(self, ohlcv, clock, frozen_now):
        plan, calls = ohlcv
        _call_ohlcv()
        clock["now"] += FAIL_COOLDOWN_SEC
        _assert_empty_df(_call_ohlcv())
        assert calls["n"] == 2 and MC._YF_OHLCV_FAIL_CACHE == {_OHLCV_KEY: clock["now"]}
        clock["now"] += FAIL_COOLDOWN_SEC
        plan["resp"] = _Raw(_chart(_ROWS))
        got = _call_ohlcv()
        assert calls["n"] == 3
        pd.testing.assert_frame_equal(got, _ohlcv_expected([_ROWS[0], _ROWS[2]]))
        assert MC._YF_OHLCV_FAIL_CACHE == {}, "成功即解除退避"

    def test_default_args_share_the_key(self, ohlcv, clock):
        """呼叫端寫法不同（位置參數／省略預設值）但打的是同一組 URL 參數 → 同一個鍵。"""
        plan, calls = ohlcv
        MC.fetch_yf_ohlcv("^TWII")
        _assert_empty_df(MC.fetch_yf_ohlcv("^TWII", "9mo", "1d"))
        assert calls["n"] == 1


class TestD2f10OhlcvParseFailureBackoff:
    @pytest.mark.parametrize("kind", sorted(_OHLCV_PARSE_FAILURES))
    def test_parse_failure_backs_off_then_refetches(self, kind, ohlcv, clock, capsys):
        plan, calls = ohlcv
        plan["resp"] = _OHLCV_PARSE_FAILURES[kind]
        _assert_empty_df(_call_ohlcv())
        assert "[macro_core/yf_ohlcv] ^TWII 解析失敗" in capsys.readouterr().out, "確實走解析失敗出口"
        assert calls["n"] == 1 and MC._YF_OHLCV_FAIL_CACHE == {_OHLCV_KEY: clock["now"]}
        clock["now"] += FAIL_COOLDOWN_SEC - 1
        _assert_empty_df(_call_ohlcv())
        assert calls["n"] == 1, "冷卻期內不重打上游"
        clock["now"] += 1
        plan["resp"] = _Raw(_chart(_ROWS))
        assert list(_call_ohlcv()["Close"]) == [10.0, 12.0] and calls["n"] == 2, "冷卻期過 → 重打、恢復"
        assert MC._YF_OHLCV_FAIL_CACHE == {}


class TestD2f10OhlcvSuccessUnchanged:
    def test_success_identical_to_prefix_and_still_uncached(self, ohlcv, clock, frozen_now):
        """成功回傳逐字同修前；本層照舊**沒有**成功快取（每次呼叫都交給 fetch_url，修前同）。"""
        plan, calls = ohlcv
        plan["resp"] = _Raw(_chart(_ROWS))
        want = _ohlcv_expected([_ROWS[0], _ROWS[2]])
        for i in range(1, 4):
            got = _call_ohlcv()
            pd.testing.assert_frame_equal(got, want, check_index_type=True)
            assert repr(got) == repr(want) and list(got.columns) == list(want.columns)
            assert calls["n"] == i
        assert MC._YF_OHLCV_FAIL_CACHE == {}, "成功不寫失敗紀錄"

    def test_all_null_close_path_is_untouched(self, ohlcv, clock):
        """HTTP 200 但 Close 全缺：修前回「有五個欄位的空表」、不當成失敗；本次未動（不屬兩個失敗出口）。"""
        plan, calls = ohlcv
        plan["resp"] = _Raw(_chart([(_T0, 1.0, 1.0, 1.0, None, 0), (_T0 + _DAY, 1.0, 1.0, 1.0, None, 0)]))
        got = _call_ohlcv()
        assert got.empty and list(got.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert MC._YF_OHLCV_FAIL_CACHE == {}
        _call_ohlcv()
        assert calls["n"] == 2, "同修前：不退避（上游保護由 fetch_url 對 HTTP 200 的 300 秒 URL 快取承接）"

    def test_backoff_is_per_key(self, ohlcv, clock):
        plan, calls = ohlcv
        _call_ohlcv()
        plan["resp"] = _Raw(_chart(_ROWS))
        assert not MC.fetch_yf_ohlcv("^GSPC", range_="9mo", interval="1d").empty
        assert not MC.fetch_yf_ohlcv("^TWII", range_="1y", interval="1d").empty
        assert not MC.fetch_yf_ohlcv("^TWII", range_="9mo", interval="1wk").empty
        _assert_empty_df(_call_ohlcv())
        assert calls["n"] == 4, "原鍵仍在冷卻期 → 不打"


class TestD2f10Race:
    """沒有成功快取可先查 → 以成功世代防「晚到的失敗蓋掉剛發生的成功」（同 FailCooldown 的競態說明）。"""

    def _gated(self, monkeypatch, first_resp, rest_resp):
        """第一次呼叫 fetch_url 卡在 gate 上（模擬慢的那一次），之後的呼叫立即回 rest_resp。"""
        gate, entered = threading.Event(), threading.Event()
        state = {"n": 0}
        lock = threading.Lock()

        def _fetch(*_a, **_k):
            with lock:
                state["n"] += 1
                first = state["n"] == 1
            if first:
                entered.set()
                assert gate.wait(timeout=10), "gate 未開（測試本身的問題）"
                return first_resp
            return rest_resp
        _use_ohlcv(MC, monkeypatch, _fetch)
        return gate, entered, state

    def test_late_failure_does_not_mask_a_success_that_happened_meanwhile(self, monkeypatch, clock):
        gate, entered, state = self._gated(monkeypatch, first_resp=None, rest_resp=_Raw(_chart(_ROWS)))
        out = {}
        slow = threading.Thread(target=lambda: out.setdefault("slow", _call_ohlcv()), daemon=True)
        slow.start()
        assert entered.wait(timeout=5)
        assert not _call_ohlcv().empty, "並行的另一次成功"
        gate.set()
        slow.join(timeout=10)
        assert not slow.is_alive()
        _assert_empty_df(out["slow"])
        assert MC._YF_OHLCV_FAIL_CACHE == {}, "期間已有人成功 → 晚到的失敗不記退避"
        assert not _call_ohlcv().empty and state["n"] == 3, "下一次照常取數（不被假失敗擋住）"

    def test_success_clears_a_failure_recorded_while_it_was_in_flight(self, monkeypatch, clock):
        gate, entered, state = self._gated(monkeypatch, first_resp=_Raw(_chart(_ROWS)), rest_resp=None)
        out = {}
        slow = threading.Thread(target=lambda: out.setdefault("slow", _call_ohlcv()), daemon=True)
        slow.start()
        assert entered.wait(timeout=5)
        _assert_empty_df(_call_ohlcv())                       # 並行的另一次失敗，先記下退避
        assert MC._YF_OHLCV_FAIL_CACHE == {_OHLCV_KEY: clock["now"]}
        gate.set()
        slow.join(timeout=10)
        assert not slow.is_alive() and not out["slow"].empty
        assert MC._YF_OHLCV_FAIL_CACHE == {}, "成功即清掉那筆失敗紀錄"

    def test_parallel_failures_no_deadlock_and_backoff_holds(self, ohlcv, clock):
        plan, calls = ohlcv
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        results, errors = [], []

        def _worker():
            try:
                barrier.wait(timeout=5)
                results.append(_call_ohlcv())
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert not any(t.is_alive() for t in threads) and errors == []
        for df in results:
            _assert_empty_df(df)
        n = calls["n"]
        assert 1 <= n <= n_threads and MC._YF_OHLCV_FAIL_CACHE == {_OHLCV_KEY: clock["now"]}
        _call_ohlcv()
        assert calls["n"] == n, "並行失敗之後：冷卻期內不再重打"


# ══════════════════════════════════════════════════════════════════
# D2-f3 macro_alert._yf_latest ／ fetch_macro_snapshot
# ══════════════════════════════════════════════════════════════════
_SRC = "macro_alert:fetch_macro_snapshot(session+yfinance)"


def _snap_expected(**vals) -> dict:
    """修前 `fetch_macro_snapshot` 的組法：依序填 vix → cpi → pcr → us10y → dxy →（vix 補抓）→
    source → fetched_at。`vals` 依呼叫端順序給。"""
    out = dict(vals)
    out["source"] = _SRC
    out["fetched_at"] = _FROZEN.isoformat()
    return out


def _assert_snap(got: dict, want: dict) -> None:
    assert got == want
    assert list(got) == list(want), "鍵的順序也同修前"
    assert repr(got) == repr(want)


@pytest.fixture
def batch(monkeypatch, frozen_now):
    """換掉 `_yf_latest` 底下的 L1 批次函式（依序回 plan 裡的 dict），並數它被叫幾次。"""
    assert hasattr(MA._yf_latest, "clear"), "前提：_yf_latest 是真的 st.cache_data（否則驗不到快取）"
    plan = {"rets": [], "n": 0}

    def _batch(tickers):
        i = min(plan["n"], len(plan["rets"]) - 1)
        plan["n"] += 1
        r = plan["rets"][i]
        if isinstance(r, BaseException):
            raise r
        return dict(r)
    monkeypatch.setattr(MA, "_macro_core_yf_latest", _batch)
    MA._yf_latest.clear()
    yield plan
    MA._yf_latest.clear()


class TestD2f3NotCachedWhenIncomplete:
    def test_raises_private_subclass_carrying_the_same_dict(self, batch):
        batch["rets"] = [{"^TNX": None, "DX-Y.NYB": 104.3}]
        with pytest.raises(MA._YfLatestIncomplete) as ei:
            MA._yf_latest(("^TNX", "DX-Y.NYB"))
        assert isinstance(ei.value, CachedFailure)
        assert ei.value.payload == {"^TNX": None, "DX-Y.NYB": 104.3}
        assert list(ei.value.payload) == ["^TNX", "DX-Y.NYB"]

    def test_incomplete_not_cached_next_call_gets_new_value(self, batch):
        batch["rets"] = [{"^TNX": None, "DX-Y.NYB": 104.3}, {"^TNX": 4.31, "DX-Y.NYB": 104.3}]
        with pytest.raises(MA._YfLatestIncomplete):
            MA._yf_latest(("^TNX", "DX-Y.NYB"))
        assert MA._yf_latest(("^TNX", "DX-Y.NYB")) == {"^TNX": 4.31, "DX-Y.NYB": 104.3}, \
            "上游恢復 → 下一次呼叫即拿到新值（修前：30 分鐘內一直回 None）"
        assert batch["n"] == 2
        for _ in range(3):
            assert MA._yf_latest(("^TNX", "DX-Y.NYB")) == {"^TNX": 4.31, "DX-Y.NYB": 104.3}
        assert batch["n"] == 2, "完整結果照舊入快取"

    def test_missing_key_counts_as_incomplete(self, batch):
        """L1 回傳少了某一檔（值與 None 同義）→ 同樣不入快取；呼叫端讀法同修前。"""
        batch["rets"] = [{"DX-Y.NYB": 104.3}, {"^TNX": 4.2, "DX-Y.NYB": 104.3}]
        _assert_snap(MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}}),
                     _snap_expected(vix=20.0, dxy=104.3))
        _assert_snap(MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}}),
                     _snap_expected(vix=20.0, us10y=4.2, dxy=104.3))

    def test_complete_result_cached_within_ttl_and_decorator_unchanged(self, batch):
        batch["rets"] = [{"^TNX": 4.2, "DX-Y.NYB": 102.0, "^VIX": 18.3}]
        first = MA.fetch_macro_snapshot()
        for _ in range(3):
            assert MA.fetch_macro_snapshot() == first
        assert batch["n"] == 1, "全部取到 → 照舊入 30 分鐘快取"
        tree = ast.parse(pathlib.Path(MA.__file__).read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_yf_latest")
        assert [ast.unparse(d) for d in fn.decorator_list] == \
            ["_safe_cache(ttl=TTL_30MIN, show_spinner=False)"], "快取層與 TTL 同修前"


#: (session_macro, L1 回傳, 修前 fetch_macro_snapshot 應回的內容（不含 source/fetched_at）)
_SNAP_CASES = {
    "all_ok": ({"vix": {"current": 20.0}}, {"^TNX": 4.55, "DX-Y.NYB": 105.2},
               {"vix": 20.0, "us10y": 4.55, "dxy": 105.2}),
    "tnx_missing": ({"vix": {"current": 20.0}}, {"^TNX": None, "DX-Y.NYB": 105.2},
                    {"vix": 20.0, "dxy": 105.2}),
    "dxy_missing": ({"vix": {"current": 20.0}, "us_core_cpi": {"yoy": 3.1}},
                    {"^TNX": 4.55, "DX-Y.NYB": None},
                    {"vix": 20.0, "cpi": 3.1, "us10y": 4.55}),
    "both_missing": ({"us_core_cpi": {"yoy": 2.8}}, {"^TNX": None, "DX-Y.NYB": None, "^VIX": 18.3},
                     {"cpi": 2.8, "vix": 18.3}),
    "vix_backfill_missing": (None, {"^TNX": 4.2, "DX-Y.NYB": 102.0, "^VIX": None},
                             {"us10y": 4.2, "dxy": 102.0}),
    "all_missing": (None, {"^TNX": None, "DX-Y.NYB": None, "^VIX": None}, {}),
}


class TestD2f3CallerOutputIdentical:
    @pytest.mark.parametrize("case", sorted(_SNAP_CASES))
    def test_snapshot_identical_to_prefix(self, case, batch):
        sess, ret, want = _SNAP_CASES[case]
        batch["rets"] = [ret]
        _assert_snap(MA.fetch_macro_snapshot(session_macro=sess), _snap_expected(**want))
        n_after_first = batch["n"]
        _assert_snap(MA.fetch_macro_snapshot(session_macro=sess), _snap_expected(**want))
        complete = all(v is not None for v in ret.values())
        assert batch["n"] == (n_after_first if complete else n_after_first + 1), \
            "只差在：含 None 的那一份不入快取（完整的照舊快取）"

    def test_generic_exception_path_unchanged(self, batch, capsys):
        batch["rets"] = [RuntimeError("network error")]
        _assert_snap(MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}}),
                     _snap_expected(vix=20.0))
        assert "[MacroAlert] yfinance 批次抓取失敗: network error" in capsys.readouterr().out

    def test_foreign_cached_failure_is_not_used_as_payload(self, batch, capsys):
        """別的模組的 CachedFailure 從下層漏上來：不得被當成 {ticker: 值} 拆開（私有子類別的理由）。"""
        batch["rets"] = [CachedFailure({"^TNX": 9.99, "DX-Y.NYB": 99.9})]
        _assert_snap(MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}}),
                     _snap_expected(vix=20.0))
        assert "[MacroAlert] yfinance 批次抓取失敗" in capsys.readouterr().out


def _close_resp(close) -> _Raw:
    return _Raw({"chart": {"result": [{
        "timestamp": [_T0 + _DAY * i for i in range(len(close))],
        "indicators": {"quote": [{"close": list(close)}]}}]}})


@pytest.fixture
def real_l1(monkeypatch, frozen_now):
    """走真的 L1（fetch_yf_latest → fetch_yf_close → _fetch_yf_close_base，含 1hr 成功快取與退避），
    只換最底層的 fetch_url，逐檔數上游呼叫次數；另外數 L1 批次函式被 `_yf_latest` 叫了幾次。"""
    assert hasattr(MA._yf_latest, "clear"), "前提：_yf_latest 是真的 st.cache_data"
    plan = {"^TNX": None, "DX-Y.NYB": _close_resp([104.1, 104.3]), "^VIX": _close_resp([17.9, 18.2])}
    calls = {"^TNX": 0, "DX-Y.NYB": 0, "^VIX": 0}
    batch_n = {"n": 0}
    lock = threading.Lock()

    def _fetch(url, params=None, timeout=15, **_k):
        t = url.rsplit("/", 1)[-1]
        with lock:
            calls[t] += 1
        return plan[t]

    real_batch = MC.fetch_yf_latest

    def _batch(tickers):
        with lock:
            batch_n["n"] += 1
        return real_batch(tickers)

    monkeypatch.setattr(MC, "fetch_url", _fetch)
    monkeypatch.setattr(MC, "_YF_CLOSE_CACHE", {})
    monkeypatch.setattr(MC, "_YF_CLOSE_EMPTY_FAIL_CACHE", {})
    monkeypatch.setattr(MA, "_macro_core_yf_latest", _batch)
    MA._yf_latest.clear()
    yield plan, calls, batch_n
    MA._yf_latest.clear()


class TestD2f3NoBombardment:
    def test_not_cached_yet_upstream_protected_then_recovers(self, real_l1, clock):
        plan, calls, batch_n = real_l1
        sess = {"vix": {"current": 20.0}}
        want = _snap_expected(vix=20.0, dxy=104.3)
        _assert_snap(MA.fetch_macro_snapshot(session_macro=sess), want)
        assert batch_n["n"] == 1 and calls == {"^TNX": 1, "DX-Y.NYB": 1, "^VIX": 0}
        for i in range(2, 6):
            _assert_snap(MA.fetch_macro_snapshot(session_macro=sess), want)
            assert batch_n["n"] == i, "含 None → 不入快取 → 每次重算"
        assert calls == {"^TNX": 1, "DX-Y.NYB": 1, "^VIX": 0}, \
            "重算也不轟炸：失敗那檔在 L1 退避、成功那檔在 L1 1 小時快取 —— 5 次呼叫上游共 2 次"
        # 上游恢復、L1 冷卻期滿 → 下一次呼叫即拿到新值（修前：_yf_latest 快取了 None，要等 30 分鐘）
        clock["now"] += FAIL_COOLDOWN_SEC
        plan["^TNX"] = _close_resp([4.25, 4.31])
        _assert_snap(MA.fetch_macro_snapshot(session_macro=sess),
                     _snap_expected(vix=20.0, us10y=4.31, dxy=104.3))
        assert calls == {"^TNX": 2, "DX-Y.NYB": 1, "^VIX": 0}
        n = batch_n["n"]
        for _ in range(3):
            MA.fetch_macro_snapshot(session_macro=sess)
        assert batch_n["n"] == n and calls == {"^TNX": 2, "DX-Y.NYB": 1, "^VIX": 0}, \
            "全部取到 → 照舊入 30 分鐘快取，之後上游 0 次"

    def test_everything_down_many_calls_one_hit_per_ticker(self, real_l1, clock):
        plan, calls, batch_n = real_l1
        plan["DX-Y.NYB"] = None
        plan["^VIX"] = None
        for _ in range(6):
            _assert_snap(MA.fetch_macro_snapshot(), _snap_expected())
        assert calls == {"^TNX": 1, "DX-Y.NYB": 1, "^VIX": 1}, "每檔在冷卻期內只打 1 次"


# ══════════════════════════════════════════════════════════════════
# 真的 fetch_url ＋ 假 HTTP session：數實際 GET 次數（含 fetch_url 自己的重試）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def http(monkeypatch):
    """換掉 fetch_url 用的 HTTP session／proxy 設定／NAS 中繼；`routes[URL 末段] = (status, body)`。"""
    routes: dict = {}
    gets: dict = {}
    relay = {"n": 0}
    lock = threading.Lock()

    class _Sess:
        def get(self, url, headers=None, params=None, timeout=None, proxies=None, verify=None):
            key = url.rsplit("/", 1)[-1]
            with lock:
                gets[key] = gets.get(key, 0) + 1
            status, body = routes[key]
            r = requests.models.Response()
            r.status_code, r._content, r.encoding, r.url = status, body, "utf-8", url
            return r

    def _relay(url, timeout=15):
        with lock:
            relay["n"] += 1
        return None

    monkeypatch.setattr(PH, "_get_thread_session", lambda lean=False: _Sess())
    monkeypatch.setattr(PH, "get_proxy_config", lambda: None)
    monkeypatch.setattr(PH, "nas_relay_fetch", _relay)
    monkeypatch.setattr(PH, "_URL_CACHE", {})
    monkeypatch.setattr(MC, "fetch_url", PH.fetch_url)
    for name in ("_FRED_CACHE", "_FRED_FAIL_CACHE", "_YF_CLOSE_CACHE", "_YF_CLOSE_EMPTY_FAIL_CACHE",
                 "_YF_OHLCV_FAIL_CACHE", "_YF_OHLCV_OK_GEN_CACHE"):
        monkeypatch.setattr(MC, name, {})
    return routes, gets, relay


_HTTP_500 = (500, b"internal error")


class TestUpstreamHttpCount:
    def test_fred_outage_one_fetch_per_cooldown(self, http, clock):
        routes, gets, relay = http
        routes["observations"] = _HTTP_500
        for _ in range(5):
            _assert_empty_df(MC.fetch_fred("DGS10", "k-test", 120))
        assert gets == {"observations": 3} and relay["n"] == 1, \
            "5 次呼叫只觸發 1 次 fetch_url（其內 3 次重試 + 1 次中繼）；修前是 15 次 GET + 5 次中繼"
        clock["now"] += FAIL_COOLDOWN_SEC
        routes["observations"] = (200, b'{"observations": [{"date": "2026-01-02", "value": "4.1"}]}')
        assert list(MC.fetch_fred("DGS10", "k-test", 120)["value"]) == [4.1]
        for _ in range(3):
            MC.fetch_fred("DGS10", "k-test", 120)
        assert gets == {"observations": 4} and relay["n"] == 1

    def test_ohlcv_outage_one_fetch_per_cooldown(self, http, clock):
        routes, gets, relay = http
        routes["^TWII"] = _HTTP_500
        for _ in range(5):
            _assert_empty_df(MC.fetch_yf_ohlcv("^TWII", range_="9mo", interval="1d"))
        assert gets == {"^TWII": 3} and relay["n"] == 1, "修前是 15 次 GET + 5 次中繼"

    def test_yf_latest_partial_outage_not_cached_and_not_bombarding(self, http, clock, frozen_now):
        assert hasattr(MA._yf_latest, "clear")
        routes, gets, relay = http
        ok = b'{"chart": {"result": [{"timestamp": [%d], "indicators": {"quote": [{"close": [%s]}]}}]}}'
        routes["^TNX"] = _HTTP_500
        routes["DX-Y.NYB"] = (200, ok % (_T0, b"104.3"))
        MA._yf_latest.clear()
        try:
            for _ in range(5):
                _assert_snap(MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}}),
                             _snap_expected(vix=20.0, dxy=104.3))
            assert gets == {"^TNX": 3, "DX-Y.NYB": 1} and relay["n"] == 1
            clock["now"] += FAIL_COOLDOWN_SEC
            routes["^TNX"] = (200, ok % (_T0, b"4.31"))
            _assert_snap(MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}}),
                         _snap_expected(vix=20.0, us10y=4.31, dxy=104.3))
            for _ in range(3):
                MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}})
            assert gets == {"^TNX": 4, "DX-Y.NYB": 1} and relay["n"] == 1
        finally:
            MA._yf_latest.clear()


# ══════════════════════════════════════════════════════════════════
# property 式（無 hypothesis 依賴）：隨機事件序列 vs 參考模型，逐步比「打不打上游」與「回什麼」
# ══════════════════════════════════════════════════════════════════
class TestRandomizedModel:
    """seed 固定、可重現。時間推進刻意落在邊界（冷卻 −1／＝／+1、TTL −1／＝）。

    參考模型只寫規格（先查成功快取 → 再查退避 → 否則打一次上游；失敗記時點、成功清紀錄），
    不看被測實作；每一步都比：上游呼叫增量、回傳內容。
    """

    _STEPS = (0, 1, FAIL_COOLDOWN_SEC - 1, FAIL_COOLDOWN_SEC, FAIL_COOLDOWN_SEC + 1,
              TTL_30MIN - 1, TTL_30MIN, 37)

    @pytest.mark.parametrize("seed", range(5))
    def test_fred_matches_model(self, seed, fred, clock):
        rng = random.Random(seed)
        plan, calls = fred
        fails = {"none": None, "parse": _FRED_PARSE_FAILURES["json_decode"],
                 "obs_empty": _FRED_OBS_EMPTY["empty_list"]}
        model = {"ok_at": None, "ok_val": None, "fail_at": None}
        for step in range(300):
            clock["now"] += rng.choice(self._STEPS)
            kind = rng.choice(["none", "parse", "obs_empty", "ok", "ok"])
            val = round(rng.uniform(1, 5), 2)
            plan["resp"] = _fred_ok([("2026-01-02", str(val))]) if kind == "ok" else fails[kind]
            before, now = calls["n"], clock["now"]
            got = _call_fred()
            if model["ok_at"] is not None and now - model["ok_at"] < TTL_30MIN:
                want_calls, want = 0, [model["ok_val"]]
            elif model["fail_at"] is not None and now - model["fail_at"] < FAIL_COOLDOWN_SEC:
                want_calls, want = 0, None
            elif kind == "ok":
                want_calls, want = 1, [val]
                model.update(ok_at=now, ok_val=val, fail_at=None)
            else:
                want_calls, want = 1, None
                model["fail_at"] = now
            assert calls["n"] - before == want_calls, (seed, step, kind)
            if want is None:
                _assert_empty_df(got)
            else:
                assert list(got["value"]) == want, (seed, step, kind)

    @pytest.mark.parametrize("seed", range(5))
    def test_ohlcv_matches_model(self, seed, ohlcv, clock):
        rng = random.Random(1000 + seed)
        plan, calls = ohlcv
        fails = {"none": None, "parse": _OHLCV_PARSE_FAILURES["missing_indicators"]}
        fail_at = None
        for step in range(300):
            clock["now"] += rng.choice(self._STEPS)
            kind = rng.choice(["none", "parse", "ok"])
            v = round(rng.uniform(10, 20), 2)
            plan["resp"] = _Raw(_chart([(_T0, v, v + 1, v - 1, v, 1000)])) if kind == "ok" else fails[kind]
            before, now = calls["n"], clock["now"]
            got = _call_ohlcv()
            if fail_at is not None and now - fail_at < FAIL_COOLDOWN_SEC:
                want_calls, want = 0, None                  # 冷卻期內：不打、回空
            elif kind == "ok":
                want_calls, want, fail_at = 1, [v], None    # 本層沒有成功快取：照舊每次打
            else:
                want_calls, want, fail_at = 1, None, now
            assert calls["n"] - before == want_calls, (seed, step, kind)
            if want is None:
                _assert_empty_df(got)
            else:
                assert list(got["Close"]) == want, (seed, step, kind)

    @pytest.mark.parametrize("seed", range(5))
    def test_yf_latest_matches_model(self, seed, batch):
        """`_yf_latest` 這一層：只快取完整結果；呼叫端每一步拿到的都等於「修前組法 ∘ 這一步該回的 dict」。"""
        rng = random.Random(2000 + seed)
        cached = None
        for step in range(120):
            if rng.random() < 0.15:                         # 模擬 30 分鐘 TTL 到期
                MA._yf_latest.clear()
                cached = None
            ret = {t: (None if rng.random() < 0.4 else round(rng.uniform(1, 200), 2))
                   for t in ("^TNX", "DX-Y.NYB")}
            batch["rets"], batch["n"] = [ret], 0
            snap = MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}})
            if cached is not None:
                want_n, used = 0, cached
            else:
                want_n, used = 1, ret
                if all(v is not None for v in ret.values()):
                    cached = ret
            assert batch["n"] == want_n, (seed, step)
            want = {"vix": 20.0}
            if used["^TNX"] is not None:
                want["us10y"] = used["^TNX"]
            if used["DX-Y.NYB"] is not None:
                want["dxy"] = used["DX-Y.NYB"]
            _assert_snap(snap, _snap_expected(**want))


# ══════════════════════════════════════════════════════════════════
# 突變：把修復改回修前 → 本檔所擋的失效確實出現
# ══════════════════════════════════════════════════════════════════
_FRED_NONE_WRITE = ("同一把鎖、同一個鍵、同一個時點(本次呼叫的 now);不入成功快取;回傳同修前。\n"
                    "        with _FRED_CACHE_LOCK:\n"
                    "            _FRED_FAIL_CACHE[key] = now\n")
_FRED_PARSE_WRITE = ("        with _FRED_CACHE_LOCK:   # D2-f6:解析失敗同樣記退避(寫法同上)\n"
                     "            _FRED_FAIL_CACHE[key] = now\n")
_FRED_OBS_WRITE = ("不必每次 rerun 都再走一次 fetch_url 與解析。回傳同修前。\n"
                   "        with _FRED_CACHE_LOCK:\n"
                   "            _FRED_FAIL_CACHE[key] = now\n")
_FRED_GATE = ("    if _failed_at is not None and (now - _failed_at) < _FAIL_COOLDOWN_SEC:\n"
              "        # D2-f6:冷卻期內")
_OHLCV_NONE_WRITE = ("# 時點＝本次呼叫的 now(同 D2-f2);期間有人成功過(世代已變)就不記。\n"
                     "        with _YF_OHLCV_FAIL_LOCK:\n"
                     "            if _YF_OHLCV_OK_GEN_CACHE.get(key, 0) == _gen:\n"
                     "                _YF_OHLCV_FAIL_CACHE[key] = now\n")
_OHLCV_PARSE_WRITE = ("# D2-f10:解析失敗(JSON 壞／結構不符／長度對不上)同樣記退避(寫法同上)\n"
                      "        with _YF_OHLCV_FAIL_LOCK:\n"
                      "            if _YF_OHLCV_OK_GEN_CACHE.get(key, 0) == _gen:\n"
                      "                _YF_OHLCV_FAIL_CACHE[key] = now\n")
_OHLCV_NONE_GEN_GUARD = ("世代已變)就不記。\n"
                         "        with _YF_OHLCV_FAIL_LOCK:\n"
                         "            if _YF_OHLCV_OK_GEN_CACHE.get(key, 0) == _gen:\n")


def _keep_first_line(snippet: str) -> tuple[str, str]:
    """把片段換成只剩第一行（＝拔掉其後的退避寫入）。"""
    return snippet, snippet.split("\n", 1)[0] + "\n"


class TestMutations:
    @pytest.mark.parametrize("snippet,tag,resp", [
        (_FRED_NONE_WRITE, "fred_none", None),
        (_FRED_PARSE_WRITE, "fred_parse", _FRED_PARSE_FAILURES["json_decode"]),
        (_FRED_OBS_WRITE, "fred_obs", _FRED_OBS_EMPTY["empty_list"]),
    ], ids=["fetch_none", "parse_failure", "obs_empty"])
    def test_mutation_fred_exit_without_backoff_bombards(self, snippet, tag, resp, monkeypatch, registry):
        pair = _keep_first_line(snippet) if tag != "fred_parse" else (snippet, "")
        m = _mutant(MC, pair, tag=tag)
        plan, calls = {"resp": resp}, {"n": 0}
        _use_fred(m, monkeypatch, _counting_fetch(plan, calls))
        m.fetch_fred(*_FRED_KEY)
        m.fetch_fred(*_FRED_KEY)
        assert calls["n"] == 2, "修前：該出口不記退避 → 每呼叫一次重打一次"

    def test_mutation_fred_cooldown_gate_removed_bombards(self, monkeypatch, registry):
        m = _mutant(MC, (_FRED_GATE, _FRED_GATE.replace(
            "if _failed_at is not None and (now - _failed_at) < _FAIL_COOLDOWN_SEC:", "if False:")),
            tag="fred_gate")
        plan, calls = {"resp": None}, {"n": 0}
        _use_fred(m, monkeypatch, _counting_fetch(plan, calls))
        m.fetch_fred(*_FRED_KEY)
        m.fetch_fred(*_FRED_KEY)
        assert calls["n"] == 2, "只記不查 → 仍然每次重打"

    @pytest.mark.parametrize("snippet,tag,resp", [
        (_OHLCV_NONE_WRITE, "ohlcv_none", None),
        (_OHLCV_PARSE_WRITE, "ohlcv_parse", _OHLCV_PARSE_FAILURES["json_decode"]),
    ], ids=["fetch_none", "parse_failure"])
    def test_mutation_ohlcv_exit_without_backoff_bombards(self, snippet, tag, resp, monkeypatch, registry):
        m = _mutant(MC, _keep_first_line(snippet), tag=tag)
        plan, calls = {"resp": resp}, {"n": 0}
        _use_ohlcv(m, monkeypatch, _counting_fetch(plan, calls))
        m.fetch_yf_ohlcv(*_OHLCV_KEY)
        m.fetch_yf_ohlcv(*_OHLCV_KEY)
        assert calls["n"] == 2, "修前：沒有退避 → 每呼叫一次重打一次"

    def test_mutation_ohlcv_without_generation_guard_masks_success(self, monkeypatch, registry, clock):
        m = _mutant(MC, (_OHLCV_NONE_GEN_GUARD, _OHLCV_NONE_GEN_GUARD.replace(
            "if _YF_OHLCV_OK_GEN_CACHE.get(key, 0) == _gen:", "if True:")), tag="ohlcv_gen")
        gate, entered = threading.Event(), threading.Event()
        state = {"n": 0}

        def _fetch(*_a, **_k):
            state["n"] += 1
            if state["n"] == 1:
                entered.set()
                gate.wait(timeout=10)
                return None
            return _Raw(_chart(_ROWS))
        _use_ohlcv(m, monkeypatch, _fetch)
        slow = threading.Thread(target=lambda: m.fetch_yf_ohlcv(*_OHLCV_KEY), daemon=True)
        slow.start()
        assert entered.wait(timeout=5)
        assert not m.fetch_yf_ohlcv(*_OHLCV_KEY).empty
        gate.set()
        slow.join(timeout=10)
        assert m.fetch_yf_ohlcv(*_OHLCV_KEY).empty and state["n"] == 2, \
            "沒有世代守衛：晚到的失敗蓋掉剛發生的成功 → 下一次被假失敗擋住"

    def test_mutation_yf_latest_caches_incomplete(self, monkeypatch, frozen_now):
        m = _mutant(MA, ("raise _YfLatestIncomplete(out)", "return out"), tag="ma_cache")
        assert hasattr(m._yf_latest, "clear")
        rets = [{"^TNX": None, "DX-Y.NYB": 104.3}, {"^TNX": 4.31, "DX-Y.NYB": 104.3}]
        state = {"n": 0}

        def _batch(tickers):
            r = rets[min(state["n"], 1)]
            state["n"] += 1
            return dict(r)
        monkeypatch.setattr(m, "_macro_core_yf_latest", _batch)
        m._yf_latest.clear()
        try:
            m.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}})
            snap = m.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}})
            assert "us10y" not in snap and state["n"] == 1, \
                "修前：含 None 的結果被快取 → 上游恢復也拿不到、上游 0 次呼叫"
        finally:
            m._yf_latest.clear()

    def test_mutation_caller_not_catching_loses_partial_values(self, monkeypatch, frozen_now):
        m = _mutant(MA, ("except _YfLatestIncomplete as _yf_inc:", "except KeyboardInterrupt as _yf_inc:"),
                    tag="ma_caller")
        monkeypatch.setattr(m, "_macro_core_yf_latest", lambda t: {"^TNX": None, "DX-Y.NYB": 104.3})
        m._yf_latest.clear()
        try:
            snap = m.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}})
            assert snap != _snap_expected(vix=20.0, dxy=104.3) and "dxy" not in snap, \
                "呼叫端沒接住 → 落進通用 except，已取到的 DXY 也一起丟掉（與修前不同）"
        finally:
            m._yf_latest.clear()
