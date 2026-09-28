# -*- coding: utf-8 -*-
"""資料層修錯（2026-09-28，CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）兩條：

  · **D2-f2** `macro_core._fetch_yf_close_base`（Yahoo 收盤，1hr 成功快取）：
    修前只有 Q2-r2 的「HTTP 200 但收盤全 null」那一條會記退避；`fetch_url` 回 None 與
    回應解析失敗這兩個出口**不記** → 每呼叫一次就重打上游一次（轟炸）。
    現在兩者都用與 Q2-r2 相同的方式（同一把鎖 `_YF_CLOSE_CACHE_LOCK`、同一個鍵
    `(ticker, interval)`、同一個冷卻期 `FAIL_COOLDOWN_SEC`、同一個時點＝本次呼叫的 now）
    寫進 `_YF_CLOSE_EMPTY_FAIL_CACHE`：冷卻期內不重打、期滿重抓、成功即清。
    成功路徑、TTL、回傳形狀不變。
  · **D2-f1** `rs_leader_service._scan_cached`（`@st.cache_data`，TTL 1 小時）：
    大盤 ^TWII 抓取失敗的結果修前被快取 1 小時 → Yahoo 恢復後使用者仍一直看到失敗。
    現在那一條出口改拋私有例外（`st.cache_data` 不快取例外），由 `run_rs_leader_scan`
    接住，回傳與修前**逐字相同**的 (rows, meta)。正常結果（含正當的空排行、部分個股缺價）
    照舊快取。L3 不另加冷卻層：失敗那條路唯一的上游就是 L1 `fetch_yf_close`，D2-f2 之後
    它的每一種失敗都有退避（`TestD2f1NoBombardment` 以真的 L1 驗證）。

「修前」的回傳一律用**獨立寫出的期望值**比對（不從被測檔推導），來源是 origin/main 修前
原始碼的字面：失敗回 `pd.Series(dtype=float, name=ticker)`；RS 失敗 meta 見 `_fail_meta()`。

不觸網：一律 monkeypatch `fetch_url`／`fetch_yf_close`／存活池／逐檔抓價／涵蓋率。
突變測試（`TestMutations`）：把修復改回修前 → 本檔對應斷言所擋的失效確實出現。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
import threading
import time
import types

import numpy as np
import pandas as pd
import pytest

import src.data.macro.macro_core as MC
import src.services.fundamental_screener_service as FSS
import src.services.rs_leader_service as RS
from shared.rs_screen_thresholds import (
    RS_DEFAULT_LOOKBACK,
    RS_LEADER_TOP_N,
    RS_LEADER_VERSION,
    RS_SCAN_MAX,
)
from shared.ttls import TTL_1HOUR
from src.compute.screener.rs_leader_screener import (
    market_interval_return,
    rank_rs_leaders,
    to_rows,
)


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str], tag: str) -> types.ModuleType:
    """同 tests/test_d2_cache_backoff_q2r2_dlf4_b6r5.py：原始碼字面替換後另建一份模組（真模組不動）。

    `tag` 讓每個突變體有自己的模組名 —— `st.cache_data` 以「模組名＋函式名＋原始碼」當快取鍵，
    同名的兩個突變體會共用同一格快取。
    """
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_d3_{tag}_{mod.__name__.rsplit('.', 1)[-1]}"
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
# 共用替身
# ══════════════════════════════════════════════════════════════════
_T0 = 1767225600          # 2026-01-01T00:00:00Z —— 測資一律固定日期，不吃執行當天
_DAY = 86400


class _Resp:
    """Yahoo Chart API 成功回應替身（`r.json()` 回合法結構；close 可含 None）。"""

    def __init__(self, close, t0: int = _T0):
        self._close = list(close)
        self._t0 = t0

    def json(self):
        return {"chart": {"result": [{
            "timestamp": [self._t0 + _DAY * i for i in range(len(self._close))],
            "indicators": {"quote": [{"close": self._close}]}}]}}


class _Raw:
    """`r.json()` 回任意結構（或拋例外）的回應替身 —— 走解析失敗那個出口。"""

    def __init__(self, payload=None, exc: Exception | None = None):
        self._payload = payload
        self._exc = exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._payload


#: 解析失敗的四種真實樣態（全部落在 `_fetch_yf_close_base` 的 `except Exception` 出口）。
_PARSE_FAILURES = {
    "json_decode": _Raw(exc=ValueError("Expecting value: line 1 column 1 (char 0)")),
    "yahoo_error_result_null": _Raw({"chart": {"result": None, "error": {
        "code": "Not Found", "description": "No data found, symbol may be delisted"}}}),
    "missing_indicators": _Raw({"chart": {"result": [{"timestamp": [_T0]}]}}),
    "length_mismatch": _Raw({"chart": {"result": [{
        "timestamp": [_T0], "indicators": {"quote": [{"close": [1.0, 2.0]}]}}]}}),
}

_KEY = ("^VIX", "1d")


@pytest.fixture
def clock(monkeypatch):
    """可手動推進的假時鐘。`_fetch_yf_close_base` 每次呼叫都 `import time` 後取 `time.time()`，
    換掉 `time.time` 就能控制「冷卻期／TTL 是否已過」，不必改常數。"""
    t = {"now": float(_T0 + 300 * _DAY)}
    monkeypatch.setattr(time, "time", lambda: t["now"])
    return t


@pytest.fixture
def frozen_now(monkeypatch):
    """`fetched_at` 取 `pd.Timestamp.now("UTC")` —— 凍結後才能與修前的期望值逐字比。"""
    fixed = pd.Timestamp("2026-09-28T01:02:03.456789", tz="UTC")
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: fixed))
    return fixed


def _use_mc(mod, monkeypatch, fetch) -> None:
    monkeypatch.setattr(mod, "fetch_url", fetch)
    monkeypatch.setattr(mod, "_YF_CLOSE_CACHE", {})
    monkeypatch.setattr(mod, "_YF_CLOSE_EMPTY_FAIL_CACHE", {})


def _counting_fetch(plan: dict, calls: dict):
    lock = threading.Lock()

    def _fetch(*_a, **_k):
        with lock:
            calls["n"] += 1
        return plan["resp"]
    return _fetch


@pytest.fixture
def yf(monkeypatch):
    """換掉 L1 `fetch_url`：`plan["resp"]` 是每次要回的東西（None ＝ 抓取失敗）。"""
    plan, calls = {"resp": None}, {"n": 0}
    _use_mc(MC, monkeypatch, _counting_fetch(plan, calls))
    return plan, calls


def _assert_failure_shape(s: pd.Series, ticker: str) -> None:
    """修前（origin/main）三個失敗出口都是 `return pd.Series(dtype=float, name=ticker)` —— 逐字比。"""
    ref = pd.Series(dtype=float, name=ticker)
    assert repr(s) == repr(ref)
    pd.testing.assert_series_equal(s, ref, check_index_type=True)
    assert type(s.index) is type(ref.index) and s.attrs == {}


# ══════════════════════════════════════════════════════════════════
# D2-f2 ① fetch_url 回 None
# ══════════════════════════════════════════════════════════════════
class TestD2f2FetchNoneBackoff:
    def test_none_not_cached_and_backs_off_within_cooldown(self, yf, clock):
        plan, calls = yf
        _assert_failure_shape(MC.fetch_yf_close("^VIX"), "^VIX")
        assert calls["n"] == 1
        assert _KEY not in MC._YF_CLOSE_CACHE, "失敗不得進 1hr 成功快取"
        assert MC._YF_CLOSE_EMPTY_FAIL_CACHE == {_KEY: clock["now"]}, \
            "與 Q2-r2 同一個鍵、同一種值（本次呼叫的時點）"
        clock["now"] += MC._FAIL_COOLDOWN_SEC - 1
        for _ in range(3):
            _assert_failure_shape(MC.fetch_yf_close("^VIX"), "^VIX")
        assert calls["n"] == 1, "冷卻期內不重打上游"

    def test_none_refetches_after_cooldown_then_recovers(self, yf, clock):
        plan, calls = yf
        MC.fetch_yf_close("^VIX")
        clock["now"] += MC._FAIL_COOLDOWN_SEC          # `<` 比較：剛好滿即過期（同 Q2-r2）
        _assert_failure_shape(MC.fetch_yf_close("^VIX"), "^VIX")
        assert calls["n"] == 2, "冷卻期過 → 重打"
        assert MC._YF_CLOSE_EMPTY_FAIL_CACHE == {_KEY: clock["now"]}, "仍失敗 → 以這次時點重新起算"
        MC.fetch_yf_close("^VIX")
        assert calls["n"] == 2, "新的冷卻期內又不重打"
        clock["now"] += MC._FAIL_COOLDOWN_SEC
        plan["resp"] = _Resp([10.0, 11.0, 12.5])
        s = MC.fetch_yf_close("^VIX")
        assert calls["n"] == 3 and list(s) == [10.0, 11.0, 12.5], "恢復 → 拿到成功"
        assert _KEY not in MC._YF_CLOSE_EMPTY_FAIL_CACHE, "成功即解除退避"
        MC.fetch_yf_close("^VIX")
        assert calls["n"] == 3, "成功照舊入 1hr 快取"


# ══════════════════════════════════════════════════════════════════
# D2-f2 ② 回應解析失敗
# ══════════════════════════════════════════════════════════════════
class TestD2f2ParseFailureBackoff:
    @pytest.mark.parametrize("kind", sorted(_PARSE_FAILURES))
    def test_parse_failure_backs_off_then_refetches(self, kind, yf, clock, capsys):
        plan, calls = yf
        plan["resp"] = _PARSE_FAILURES[kind]
        _assert_failure_shape(MC.fetch_yf_close("^VIX"), "^VIX")
        assert "[macro_core/yf] ^VIX 解析失敗" in capsys.readouterr().out, "確實走解析失敗出口"
        assert calls["n"] == 1 and _KEY not in MC._YF_CLOSE_CACHE
        assert MC._YF_CLOSE_EMPTY_FAIL_CACHE == {_KEY: clock["now"]}
        clock["now"] += MC._FAIL_COOLDOWN_SEC - 1
        _assert_failure_shape(MC.fetch_yf_close("^VIX"), "^VIX")
        assert calls["n"] == 1, "冷卻期內不重打上游"
        clock["now"] += 1
        _assert_failure_shape(MC.fetch_yf_close("^VIX"), "^VIX")
        assert calls["n"] == 2, "冷卻期過 → 重打"
        clock["now"] += MC._FAIL_COOLDOWN_SEC
        plan["resp"] = _Resp([7.0, 8.0])
        assert list(MC.fetch_yf_close("^VIX")) == [7.0, 8.0] and calls["n"] == 3
        assert _KEY not in MC._YF_CLOSE_EMPTY_FAIL_CACHE, "成功即解除退避"


# ══════════════════════════════════════════════════════════════════
# D2-f2 ③ 成功路徑與現行語意不變
# ══════════════════════════════════════════════════════════════════
class TestD2f2SuccessUnchanged:
    def test_success_identical_to_prefix_and_not_recorded(self, yf, clock, frozen_now):
        plan, calls = yf
        plan["resp"] = _Resp([1.0, None, 3.0])
        s = MC.fetch_yf_close("^GSPC")
        # 修前成功路徑的字面：dropna → 帶名 → attrs(source, fetched_at)
        ref = pd.Series([1.0, 3.0], index=pd.to_datetime([_T0, _T0 + 2 * _DAY], unit="s"),
                        dtype=float, name="^GSPC")
        pd.testing.assert_series_equal(s, ref, check_index_type=True)
        assert s.attrs == {"source": "Yahoo:^GSPC", "fetched_at": frozen_now.isoformat()}
        assert MC._YF_CLOSE_EMPTY_FAIL_CACHE == {}, "成功不寫失敗紀錄"
        # TTL 用修前的值（1 小時）推進，不讀被測模組的常數 —— 否則 TTL 被改了也驗不出來
        assert MC._YF_CLOSE_TTL == TTL_1HOUR, "成功快取 TTL 同修前（1 小時）"
        clock["now"] += TTL_1HOUR - 1
        pd.testing.assert_series_equal(MC.fetch_yf_close("^GSPC"), ref, check_index_type=True)
        assert calls["n"] == 1, "TTL 內照舊命中成功快取"
        clock["now"] += 1
        MC.fetch_yf_close("^GSPC")
        assert calls["n"] == 2, "TTL 滿 → 重抓（TTL 不變）"

    def test_fresh_success_wins_over_leftover_failure_record(self, yf, clock):
        """現行語意：先查成功快取 —— 殘留的失敗紀錄（例：並行呼叫晚一步寫入）擋不住新鮮的成功。"""
        plan, calls = yf
        plan["resp"] = _Resp([5.0, 6.0])
        MC.fetch_yf_close("^GSPC")
        MC._YF_CLOSE_EMPTY_FAIL_CACHE[("^GSPC", "1d")] = clock["now"]
        assert list(MC.fetch_yf_close("^GSPC")) == [5.0, 6.0] and calls["n"] == 1

    def test_success_after_failure_is_not_tainted(self, yf, clock):
        """失敗 → 冷卻期滿 → 成功：失敗紀錄清掉、成功入快取；之後上游再掛，TTL 內仍回那份成功。"""
        plan, calls = yf
        MC.fetch_yf_close("^GSPC")
        clock["now"] += MC._FAIL_COOLDOWN_SEC
        plan["resp"] = _Resp([1.5, 2.5])
        assert list(MC.fetch_yf_close("^GSPC")) == [1.5, 2.5]
        assert MC._YF_CLOSE_EMPTY_FAIL_CACHE == {}
        plan["resp"] = None
        clock["now"] += TTL_1HOUR - 1
        assert list(MC.fetch_yf_close("^GSPC")) == [1.5, 2.5] and calls["n"] == 2

    def test_backoff_is_per_key(self, yf, clock):
        """鍵 ＝ (ticker, interval)：一檔失敗不擋別檔，也不擋同一檔的其他 interval。"""
        plan, calls = yf
        MC.fetch_yf_close("^VIX")
        plan["resp"] = _Resp([1.0, 2.0])
        assert list(MC.fetch_yf_close("^GSPC")) == [1.0, 2.0]
        assert list(MC.fetch_yf_close("^VIX", interval="1wk")) == [1.0, 2.0]
        _assert_failure_shape(MC.fetch_yf_close("^VIX"), "^VIX")
        assert calls["n"] == 3, "原鍵仍在冷卻期 → 不打"


# ══════════════════════════════════════════════════════════════════
# D2-f2 ④ 並行存取
# ══════════════════════════════════════════════════════════════════
class TestD2f2Concurrency:
    def test_parallel_failures_no_deadlock_and_backoff_holds(self, yf, clock):
        plan, calls = yf
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        results, errors = [], []

        def _worker():
            try:
                barrier.wait(timeout=5)
                results.append(MC.fetch_yf_close("^VIX"))
            except Exception as e:  # noqa: BLE001 — 收集起來讓斷言報出來
                errors.append(e)

        # daemon：若真的死鎖，執行緒不會卡住整個 pytest 行程（斷言照樣報紅）
        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert not any(t.is_alive() for t in threads), "不得死鎖（鎖只在非巢狀的短區段持有）"
        assert errors == [] and len(results) == n_threads
        for s in results:
            _assert_failure_shape(s, "^VIX")
        assert 1 <= calls["n"] <= n_threads
        assert MC._YF_CLOSE_EMPTY_FAIL_CACHE == {_KEY: clock["now"]}
        n = calls["n"]
        MC.fetch_yf_close("^VIX")
        assert calls["n"] == n, "並行失敗之後：冷卻期內不再重打"


# ══════════════════════════════════════════════════════════════════
# D2-f1 共用：合成大盤／個股 + 換掉 RS 的上游
# ══════════════════════════════════════════════════════════════════
_FAIL_NOTE = "⚠️ 大盤 ^TWII 抓取失敗（Yahoo 暫時不可用），無基準可比較 RS，稍後再試。"
_COVERAGE = "（涵蓋率替身）"
_N = 160
_LB = 120


def _closes(total_ret: float, n: int = _N, seed: int = 0, noise: float = 0.012) -> np.ndarray:
    rng = np.random.RandomState(seed)
    drift = (1 + total_ret) ** (1 / (n - 1)) - 1
    rets = drift + rng.normal(0, noise, n)
    rets[0] = 0.0
    return 100 * np.cumprod(1 + rets)


def _idx(n: int = _N) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=n, freq="D")      # 與 _T0 同一天起算


def _stock(total_ret: float, seed: int, n: int = _N) -> pd.DataFrame:
    return pd.DataFrame({"Close": _closes(total_ret, n, seed)}, index=_idx(n))


def _market(total_ret: float = -0.30, seed: int = 1, n: int = _N) -> pd.Series:
    return pd.Series(_closes(total_ret, n, seed), index=_idx(n), name="^TWII")


def _frozen_market(n: int = _N) -> pd.Series:
    """收盤恆定 ⇒ 日報酬 σ = 0 ⇒ RS 分母不成立（資料品質問題，不是抓取失敗）。"""
    return pd.Series([18_000.0] * n, index=_idx(n), name="^TWII")


def _default_prices() -> dict:
    return {"A": _stock(+0.10, seed=11), "B": _stock(-0.05, seed=12), "C": _stock(-0.55, seed=13)}


def _install_world(mod, monkeypatch, plan: dict, calls: dict) -> None:
    assert hasattr(mod._scan_cached, "clear"), "前提：_scan_cached 是真的 st.cache_data（否則驗不到快取）"
    lock = threading.Lock()

    def _bump(k):
        with lock:
            calls[k] += 1

    def _yf(tk, range_="2y"):
        _bump("market")
        m = plan["market"]
        return pd.Series(dtype=float, name=tk) if m is None else m.copy()   # L1 失敗契約：空、不拋

    def _pool(max_n):
        _bump("pool")
        return list(plan["pool"])[:max_n]

    def _price(sid):
        _bump("price")
        df = plan["prices"].get(sid)
        return (None if df is None else df.copy()), f"{sid}.TW"

    monkeypatch.setattr(mod, "fetch_yf_close", _yf)
    monkeypatch.setattr(mod, "_survivor_pool", _pool)
    monkeypatch.setattr(mod, "fetch_stock_history_1y", _price)
    monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
    mod._scan_cached.clear()


@pytest.fixture
def rs_world(monkeypatch):
    """換掉 RS 的上游（存活池／大盤／逐檔抓價／涵蓋率）。plan["market"] 為 None ＝ 大盤抓取失敗。"""
    plan = {"market": None, "pool": ["A", "B", "C"], "prices": _default_prices()}
    calls = {"market": 0, "pool": 0, "price": 0}
    _install_world(RS, monkeypatch, plan, calls)
    yield plan, calls
    RS._scan_cached.clear()


def _fail_meta(*, lookback: int, top_n: int, fetched_at: str) -> dict:
    """修前（origin/main）`_scan_cached` 大盤抓取失敗那一條回傳的 meta（逐字抄寫）＋ 快取外注入。"""
    return {"lookback": lookback, "top_n": top_n,
            "source": "FundamentalsSnapshot(survivors)+yfinance:1y+Yahoo:^TWII",
            "fetched_at": fetched_at, "version": RS_LEADER_VERSION,
            "candidates": 0, "scanned": 0, "scored": 0,
            "pool_source": "（無）", "market": {"banner": ""},
            "note": _FAIL_NOTE,
            "coverage_note": _COVERAGE}


# ══════════════════════════════════════════════════════════════════
# D2-f1 ① 失敗不入快取
# ══════════════════════════════════════════════════════════════════
class TestD2f1MarketFailNotCached:
    def test_fail_then_recover_recomputes(self, rs_world):
        plan, calls = rs_world
        rows, meta = RS.run_rs_leader_scan(lookback=_LB)
        assert rows == [] and meta["note"] == _FAIL_NOTE
        assert calls == {"market": 1, "pool": 0, "price": 0}, "大盤先抓；抓不到就不碰存活池與個股"
        plan["market"] = _market()
        rows2, meta2 = RS.run_rs_leader_scan(lookback=_LB)
        assert calls["market"] == 2, "失敗不入快取 → 第二次重算（上游呼叫數增加）"
        assert rows2 and meta2["note"] == "" and meta2["scored"] == len(rows2)
        before = dict(calls)
        assert RS.run_rs_leader_scan(lookback=_LB) == (rows2, meta2)
        assert calls == before, "恢復後的成功照舊入快取"

    def test_persistent_failure_recomputes_every_call_at_this_layer(self, rs_world):
        """本層不快取失敗：大盤持續失敗時每次都重算（打不打上游交給 L1 退避，見 TestD2f1NoBombardment）。"""
        plan, calls = rs_world
        for i in range(1, 4):
            assert RS.run_rs_leader_scan(lookback=_LB)[1]["note"] == _FAIL_NOTE
            assert calls == {"market": i, "pool": 0, "price": 0}

    @pytest.mark.parametrize("kwargs", [
        {"beat_only": False, "top_n": RS_SCAN_MAX},                  # app.py／page_find／get_ranked_picks 的呼叫法
        {"beat_only": False, "top_n": RS_SCAN_MAX, "refresh": True},
        {"lookback": 20, "beat_only": True, "name_map": {"A": "甲"}},
    ], ids=["callers", "refresh", "beat_only_name_map"])
    def test_failure_never_raises_to_caller_and_output_identical(self, rs_world, frozen_now, kwargs):
        rows, meta = RS.run_rs_leader_scan(**kwargs)
        assert rows == []
        want = _fail_meta(lookback=kwargs.get("lookback", RS_DEFAULT_LOOKBACK),
                          top_n=kwargs.get("top_n", RS_LEADER_TOP_N),
                          fetched_at=frozen_now.isoformat())
        assert meta == want
        assert list(meta) == list(want), "鍵的順序也同修前"
        assert repr((rows, meta)) == repr(([], want))


# ══════════════════════════════════════════════════════════════════
# D2-f1 ② 正常結果照舊快取、輸出同修前
# ══════════════════════════════════════════════════════════════════
#: 非失敗分支（逐條對 `_scan_cached` 讀過，理由見交付報告的判定表）。
_NORMAL_CASES = {
    # ② 存活池為空：來源是本機季快照（不觸網），程式標的是「快照未就緒」，不是上游抓取失敗
    "survivor_pool_empty": {"pool": [], "market": _market, "kwargs": {}, "note_has": "存活池為空"},
    # ③a 有量測成功、勾「只留贏過大盤」後 0 檔 —— 正當的空排行
    "beat_only_zero_winners": {"pool": ["C"], "market": lambda: _market(+0.20),
                               "kwargs": {"beat_only": True}, "note_has": "0 檔"},
    # ③c 大盤凍結（σ 不成立）→ 全部資料不足 —— 資料品質，不是抓取失敗
    "frozen_market": {"pool": ["A", "B"], "market": _frozen_market, "kwargs": {},
                      "note_has": "問題指向大盤側"},
    # ③d 大盤正常、個股全抓不到價 —— 程式標的是「個股側的資料問題」（非「上游抓取失敗」分支）
    # ⚠️ D2-f7（2026-09-28）起這一種**不再入快取**，改由掃描層退避擋重打；下方「TTL 內第二次上游
    # 呼叫數不變」在冷卻期內仍成立（由退避達成，不是快取）。不入快取的證明見
    # tests/test_d3b_backoff_d2f4_d2f7_d2f9.py。
    "all_prices_missing": {"pool": ["X", "Y"], "market": _market, "kwargs": {},
                           "note_has": "完全抓不到 K 線"},
    # ④ 只有部分個股缺價的正常排行
    "partial_prices_missing": {"pool": ["A", "B", "X"], "market": _market, "kwargs": {},
                               "note_has": None},
}


class TestD2f1NormalResultsStillCached:
    @pytest.mark.parametrize("case", sorted(_NORMAL_CASES))
    def test_normal_results_cached_within_ttl(self, rs_world, case):
        plan, calls = rs_world
        spec = _NORMAL_CASES[case]
        plan["pool"], plan["market"] = spec["pool"], spec["market"]()
        rows, meta = RS.run_rs_leader_scan(lookback=_LB, **spec["kwargs"])
        assert meta["note"] != _FAIL_NOTE
        if spec["note_has"] is None:
            assert rows and meta["note"] == ""
        else:
            assert rows == [] and spec["note_has"] in meta["note"], meta["note"]
        before = dict(calls)
        assert before["market"] == 1
        again = RS.run_rs_leader_scan(lookback=_LB, **spec["kwargs"])
        assert calls == before, "正常結果（含正當的空排行）照舊入快取：TTL 內第二次上游呼叫數不變"
        assert again == (rows, meta)

    def test_success_output_identical_to_prefix(self, rs_world, frozen_now):
        """成功：以修前 `_scan_cached` 成功分支的組法（L2 直呼）獨立算出期望值，逐字比。"""
        plan, calls = rs_world
        plan["market"] = _market()
        name_map = {"A": "強者"}
        got = RS.run_rs_leader_scan(lookback=_LB, beat_only=False, top_n=RS_SCAN_MAX,
                                    name_map=name_map)
        dfm = _market().rename("close").to_frame()
        stocks = [{"stock_id": s, "name": "", "df": plan["prices"][s]} for s in plan["pool"]]
        want_rows = to_rows(rank_rs_leaders(stocks, dfm, lookback=_LB, top_n=RS_SCAN_MAX,
                                            beat_only=False))
        want_rows = [dict(r) for r in want_rows]
        for r in want_rows:
            if r.get("代碼") in name_map:
                r["名稱"] = name_map[r["代碼"]]
        ret = float(market_interval_return(dfm, _LB))
        assert ret < -0.5, "前提：合成大盤為下跌情境"
        want_meta = {
            "lookback": _LB, "top_n": RS_SCAN_MAX,
            "source": "FundamentalsSnapshot(survivors)+yfinance:1y+Yahoo:^TWII",
            "fetched_at": frozen_now.isoformat(), "version": RS_LEADER_VERSION,
            "candidates": 3, "scanned": 3, "scored": len(want_rows),
            "pool_source": "基本面存活池（免費離線快照）",
            "market": {"market_ret_pct": ret, "is_down": True,
                       "banner": (f"📉 此期間大盤（^TWII）約 {ret:+.2f}% — 屬下跌情境；"
                                  f"以下為「跌勢中仍相對抗跌 / 逆勢贏過大盤」的個股。")},
            "note": "",
            "coverage_note": _COVERAGE,
        }
        assert len(want_rows) == 3 and want_rows[0]["名稱"] == "強者"
        assert got == (want_rows, want_meta)
        assert list(got[1]) == list(want_meta)
        assert repr(got) == repr((want_rows, want_meta))

    def test_success_cached_within_ttl(self, rs_world):
        plan, calls = rs_world
        plan["market"] = _market()
        first = RS.run_rs_leader_scan(lookback=_LB)
        before = dict(calls)
        assert before == {"market": 1, "pool": 1, "price": 3}
        assert RS.run_rs_leader_scan(lookback=_LB) == first
        assert calls == before, "TTL 內第二次呼叫：上游呼叫數不變"
        # TTL 同修前（1 小時）：讀裝飾器原文，不依賴 streamlit 的私有屬性
        # （D2-f7 2026-09-28：快取層由 `_scan_cached` 改名 `_scan_body`，`_scan_cached` 改為不快取的
        #  退避入口 —— 故改查 `_scan_body`；斷言內容〔裝飾器原文逐字〕不變。）
        tree = ast.parse(pathlib.Path(RS.__file__).read_text(encoding="utf-8"))
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_scan_body")
        assert [ast.unparse(d) for d in fn.decorator_list] == \
            ["st.cache_data(ttl=TTL_1HOUR, show_spinner=False)"]


# ══════════════════════════════════════════════════════════════════
# D2-f1 ③ 為何 L3 不另加 FailCooldown：走真的 L1，失敗期間不轟炸上游
# ══════════════════════════════════════════════════════════════════
class TestD2f1NoBombardment:
    @pytest.mark.parametrize("fail_resp", [None, _PARSE_FAILURES["json_decode"], _Resp([None] * 5)],
                             ids=["fetch_none", "parse_failure", "all_null"])
    def test_real_l1_backoff_blocks_repeat_hits(self, fail_resp, monkeypatch, clock):
        plan = {"resp": fail_resp}
        calls = {"n": 0}
        _use_mc(MC, monkeypatch, _counting_fetch(plan, calls))
        side = {"pool": 0, "price": 0}
        side_lock = threading.Lock()                 # 逐檔抓價在執行緒池裡跑

        def _pool(max_n):
            with side_lock:
                side["pool"] += 1
            return ["A", "B", "C"][:max_n]

        prices = _default_prices()

        def _price(sid):
            with side_lock:
                side["price"] += 1
            return prices[sid].copy(), f"{sid}.TW"

        monkeypatch.setattr(RS, "fetch_yf_close", MC.fetch_yf_close)      # 真的 L1（含退避）
        monkeypatch.setattr(RS, "_survivor_pool", _pool)
        monkeypatch.setattr(RS, "fetch_stock_history_1y", _price)
        monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
        RS._scan_cached.clear()
        try:
            for _ in range(5):
                rows, meta = RS.run_rs_leader_scan(lookback=_LB)
                assert rows == [] and meta["note"] == _FAIL_NOTE
            assert calls["n"] == 1 and side == {"pool": 0, "price": 0}, \
                "失敗不入 L3 快取，但 L1 退避擋住重打：5 次呼叫只打上游 1 次"
            clock["now"] += MC._FAIL_COOLDOWN_SEC
            plan["resp"] = _Resp(list(_market().values))
            rows, meta = RS.run_rs_leader_scan(lookback=_LB)
            assert calls["n"] == 2 and rows and meta["note"] == "", "冷卻期滿 → 重打一次、恢復"
            for _ in range(3):
                RS.run_rs_leader_scan(lookback=_LB)
            assert calls["n"] == 2 and side == {"pool": 1, "price": 3}, "恢復後照舊入快取"
        finally:
            RS._scan_cached.clear()

    def test_parallel_calls_during_failure(self, rs_world):
        """並行：大盤失敗時多執行緒同時呼叫 —— 每一個都拿到同一份失敗回傳，不拋、不死鎖。"""
        plan, calls = rs_world
        results, errors = [], []

        def _worker():
            try:
                results.append(RS.run_rs_leader_scan(lookback=_LB))
            except Exception as e:  # noqa: BLE001 — 收集起來讓斷言報出來
                errors.append(e)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not any(t.is_alive() for t in threads)
        assert errors == [] and len(results) == 4
        assert all(r == [] and m["note"] == _FAIL_NOTE for r, m in results)
        assert calls["pool"] == 0 and calls["price"] == 0


# ══════════════════════════════════════════════════════════════════
# 突變：把修復改回修前 → 本檔所擋的失效確實出現
# ══════════════════════════════════════════════════════════════════
_MC_NONE_WRITE = ('fetch_url 回 None(不快取,冷卻 {_FAIL_COOLDOWN_SEC:.0f}s)")\n'
                  '        with _YF_CLOSE_CACHE_LOCK:\n'
                  '            _YF_CLOSE_EMPTY_FAIL_CACHE[key] = now\n')
_MC_PARSE_WRITE = ('解析失敗: {e}")\n'
                   '        with _YF_CLOSE_CACHE_LOCK:\n'
                   '            _YF_CLOSE_EMPTY_FAIL_CACHE[key] = now\n')


def _drop_write(snippet: str) -> tuple[str, str]:
    return snippet, snippet.split("\n", 1)[0] + "\n"


class TestMutations:
    def test_mutation_none_path_no_backoff(self, monkeypatch):
        m = _mutant(MC, _drop_write(_MC_NONE_WRITE), tag="none")
        plan, calls = {"resp": None}, {"n": 0}
        _use_mc(m, monkeypatch, _counting_fetch(plan, calls))
        m.fetch_yf_close("^VIX")
        m.fetch_yf_close("^VIX")
        assert calls["n"] == 2, "修前：fetch_url 回 None 不記退避 → 每呼叫一次重打一次"

    def test_mutation_parse_path_no_backoff(self, monkeypatch):
        m = _mutant(MC, _drop_write(_MC_PARSE_WRITE), tag="parse")
        plan, calls = {"resp": _PARSE_FAILURES["json_decode"]}, {"n": 0}
        _use_mc(m, monkeypatch, _counting_fetch(plan, calls))
        m.fetch_yf_close("^VIX")
        m.fetch_yf_close("^VIX")
        assert calls["n"] == 2, "修前：解析失敗不記退避 → 每呼叫一次重打一次"

    def test_mutation_rs_failure_cached(self, monkeypatch):
        m = _mutant(RS, ("raise _UpstreamFetchFailed(_fail)", "return _fail"), tag="rs")
        plan = {"market": None, "pool": ["A", "B", "C"], "prices": _default_prices()}
        calls = {"market": 0, "pool": 0, "price": 0}
        _install_world(m, monkeypatch, plan, calls)
        try:
            assert m.run_rs_leader_scan(lookback=_LB)[1]["note"] == _FAIL_NOTE
            plan["market"] = _market()
            rows, meta = m.run_rs_leader_scan(lookback=_LB)
            assert rows == [] and meta["note"] == _FAIL_NOTE and calls["market"] == 1, \
                "修前：失敗被 st.cache_data 凍成 1 小時，上游恢復也看不到"
        finally:
            m._scan_cached.clear()
