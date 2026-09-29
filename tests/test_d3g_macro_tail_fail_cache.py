# -*- coding: utf-8 -*-
"""資料層修錯 批 D3g（2026-09-29，CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）：

  · **D2-f13** `tw_macro._ttl_cache`（本模組自帶、純 stdlib 的 TTL＋LRU 快取）不分成敗照存回傳值：
      - `fetch_china_macro`（30 分鐘）：5 條 FRED 序列任一條失敗（空表）時整包照存 —— FRED 恢復後
        30 分鐘內仍 0/5、上游 0 次請求（呼叫端：L5 `tabs/macro/helpers` → L2 `macro_helpers.get_china_snapshot`）。
      - `fetch_usdtwd_close`（1 小時）：`fetch_yf_close('TWD=X')` 失敗回 None 也被凍 1 小時
        （呼叫端：L5 `etf_tab_portfolio._fetch_usdtwd_spot`）。
    修法：`_ttl_cache` 加選用的判定式 `cache_if`（預設 None ＝ 修前行為）；china 給「5 條全有資料」
    （同 D2-f23「半邊失敗不入快取」），usdtwd 給「不是 None」。`fetch_cbc_discount_rate`
    （交接本 DEAD_CODE.md D-016，疑似死碼）與其餘 11 個 `_ttl_cache` 函式不啟用（`TestTtlCacheHook` 以 AST
    釘住「只有這兩支啟用」）。
    退避：不入快取後重算也不打上游 —— 底層 `fetch_fred`（成功 30 分鐘快取／失敗 FAIL_COOLDOWN_SEC 退避）、
    `_fetch_yf_close_base`（成功 1 小時快取／失敗 FAIL_COOLDOWN_SEC 退避）；唯一不在 180 秒退避裡的是
    `fetch_fred` 在 HTTP 200 之後拋例外那條（合成情境），由 fetch_url 的 300 秒 URL 快取擋住
    （`TestUpstreamHttpCount` 走真的 fetch_url 數實際 GET）。
  · **D2-f14 ①** `macro_core.fetch_fred` 三個失敗出口、`fetch_yf_ohlcv` 兩個失敗出口，以及同檔同一缺陷的
    `_fetch_yf_close_base` 三個失敗出口（fetch_url 回 None／收盤全 null／解析失敗；總管 2026-09-29 裁定併入
    本列）：寫退避紀錄時與既有紀錄取 max —— 並行時「較早開始、較晚失敗」的呼叫不再用較舊的 now 蓋掉較新的
    紀錄（冷卻提早結束）。時點仍取「呼叫開始」的 now（不改成失敗當下 —— 那會拉長冷卻）。
  · **D2-f14 ②** `macro_alert._yf_latest` 以 `is None` 判缺值：補測試釘住「0.0 算有值」
    （批 D3a QA：把 `is None` 突變成 falsy 判斷，相關既有測試全綠 —— 突變存活）。

「修前」一律用**修前模型**重現：把本次改動換回 origin/main `8bb46f4` 的寫法、另建一份模組（`_mutant`，
真模組不動）；同一份檢查（`_check_*`）在修前模型上必須轉紅（`TestPrefixReproducesBug`）。
期望值一律獨立寫出（不從被測檔推導）。不觸網：一律換掉 fetch_url 或 HTTP session。冷卻期／TTL 用假時鐘
（`time.time`；`st.cache_data` 的 TTL 不吃它，只靠清快取控制）。
突變（`TestMutations`）：逐一拿掉每一處修正 → 本檔對應的 `_check_*` 轉紅，其餘不受影響。
"""
from __future__ import annotations

import ast
import concurrent.futures
import importlib.util
import pathlib
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
import src.data.macro.tw_macro as TW
import src.data.proxy.proxy_helper as PH
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from shared.fred_series import FRED_CHN_CPI, FRED_CHN_M2, FRED_CHN_OECD_CLI, FRED_CHN_PMI, FRED_USDCNY
from shared.ttls import TTL_1HOUR, TTL_30MIN


def _mutant(mod: types.ModuleType, *pairs: tuple, tag: str) -> types.ModuleType:
    """原始碼字面替換後另建一份模組（真模組不動；同 tests/test_d3a_backoff_d2f6_d2f10_d2f3.py）。

    pair ＝ (old, new) 或 (old, new, 次數)：次數省略時 old 必須恰好出現 1 次。
    """
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for pair in pairs:
        old, new = pair[0], pair[1]
        times = pair[2] if len(pair) > 2 else 1
        assert src.count(old) == times, f"突變點次數不符（{src.count(old)} ≠ {times}）：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_d3g_{tag}_{mod.__name__.rsplit('.', 1)[-1]}"
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
_FROZEN = pd.Timestamp("2026-09-29T01:02:03.456789", tz="UTC")


class _Raw:
    """`r.json()` 回任意結構（或拋例外）的回應替身。"""

    def __init__(self, payload=None, exc: Exception | None = None):
        self._payload = payload
        self._exc = exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._payload


@pytest.fixture
def clock(monkeypatch):
    """可手動推進的假時鐘：`_ttl_cache`、`fetch_fred`、`_fetch_yf_close_base`、`fetch_yf_ohlcv`、
    `fetch_url` 的 URL 快取都以 `time.time()` 判斷 TTL／冷卻期。"""
    t = {"now": float(_T0 + 300 * _DAY)}
    monkeypatch.setattr(time, "time", lambda: t["now"])
    return t


@pytest.fixture
def frozen_now(monkeypatch):
    """`fetched_at` 取 `pd.Timestamp.now("UTC")` —— 凍結後才能與期望值逐字比。"""
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: _FROZEN))
    return _FROZEN


@pytest.fixture
def registry(monkeypatch):
    """隔離 `@monitored` 登錄表：突變／修前模組重跑 `@monitored` 不污染別的測試。"""
    snap = {k: dict(v) for k, v in FM._MONITOR_REGISTRY.items()}
    monkeypatch.setattr(FM, "_MONITOR_REGISTRY", snap)
    return snap


def _assert_empty_df(df) -> None:
    """`fetch_fred`／`fetch_yf_ohlcv` 失敗出口與 `fetch_china_macro` 例外補位都是 `pd.DataFrame()` —— 逐字比。"""
    ref = pd.DataFrame()
    assert type(df) is pd.DataFrame
    assert repr(df) == repr(ref)
    pd.testing.assert_frame_equal(df, ref)
    assert list(df.columns) == [] and df.attrs == {}


def test_cooldown_seconds_is_the_existing_ssot_constant():
    """退避沿用既有冷卻秒數（`shared.fail_cooldown.FAIL_COOLDOWN_SEC`），本批不另立常數、不新增冷卻機制。"""
    assert MC._FAIL_COOLDOWN_SEC is FAIL_COOLDOWN_SEC


# ══════════════════════════════════════════════════════════════════
# D2-f13 ① fetch_china_macro
# ══════════════════════════════════════════════════════════════════
_KEY = "k" * 32                       # get_china_snapshot 要求 ≥30 字元；fetch_china_macro 只看非空
#: tw_macro._china_fred_specs 的順序（修前字面）＝ 回傳 dict 的鍵順序
_SIDS = [FRED_USDCNY, FRED_CHN_OECD_CLI, FRED_CHN_CPI, FRED_CHN_M2, FRED_CHN_PMI]
#: 每條序列兩筆（刻意倒序給，驗 fetch_fred 升冪排序照舊）
_ROWS = {sid: [("2026-02-01", f"{100 + 10 * i + 1}.5"), ("2026-01-01", f"{100 + 10 * i}.25")]
         for i, sid in enumerate(_SIDS)}


def _fred_ok(rows) -> _Raw:
    return _Raw({"observations": [{"date": d, "value": v} for d, v in rows]})


def _fred_expected(sid: str) -> pd.DataFrame:
    """修前 `fetch_fred` 成功路徑的字面：value 轉 float64 → date 轉時間 → 依 date 升冪 → 補 source／fetched_at。"""
    kept = sorted((d, float(v)) for d, v in _ROWS[sid])
    df = pd.DataFrame({
        "date": pd.to_datetime(pd.Series([d for d, _ in kept])),
        "value": pd.Series([v for _, v in kept], dtype="float64"),
    })
    df["source"] = f"FRED:{sid}"
    df["fetched_at"] = _FROZEN.isoformat()
    return df


class _YfWorld:
    """Yahoo `TWD=X` 的上游替身：`resp`（None ＝ 抓取失敗），數上游呼叫。"""

    def __init__(self):
        self.resp = None
        self.calls = 0

    def fetch_url(self, url, headers=None, params=None, timeout=15, **_k):
        assert url == f"{MC.YF_CHART_BASE}/TWD=X", url
        self.calls += 1
        return self.resp


class _FredWorld:
    """FRED 的上游替身：每條序列各自的回應（None ＝ 抓取失敗），逐條數上游呼叫（執行緒安全）。"""

    def __init__(self):
        self.resp = {sid: None for sid in _SIDS}
        self.calls = {sid: 0 for sid in _SIDS}
        self._lock = threading.Lock()

    def fetch_url(self, url, headers=None, params=None, timeout=20, **_k):
        sid = params["series_id"]
        with self._lock:
            self.calls[sid] += 1
        return self.resp[sid]

    def all_ok(self):
        for sid in _SIDS:
            self.resp[sid] = _fred_ok(_ROWS[sid])


@pytest.fixture
def worlds(monkeypatch, frozen_now):
    """換掉 `macro_core.fetch_url`：FRED 的請求交給 `_FredWorld`、Yahoo 的交給 `_YfWorld`（兩者可並存）。"""
    w, y = _FredWorld(), _YfWorld()

    def _dispatch(url, *a, **k):
        return (w if url.startswith(MC.FRED_BASE) else y).fetch_url(url, *a, **k)
    monkeypatch.setattr(MC, "fetch_url", _dispatch)
    for name in ("_FRED_CACHE", "_FRED_FAIL_CACHE", "_YF_CLOSE_CACHE", "_YF_CLOSE_EMPTY_FAIL_CACHE"):
        monkeypatch.setattr(MC, name, {})
    return w, y


@pytest.fixture
def fred_world(worlds):
    return worlds[0]


@pytest.fixture
def yf_world(worlds):
    return worlds[1]


def _ok_sids(out: dict) -> list:
    return [sid for sid, df in out.items() if df is not None and not df.empty]


def _assert_all_expected(out: dict) -> None:
    assert list(out) == _SIDS, "鍵與順序同修前（依 specs 順序）"
    for sid in _SIDS:
        pd.testing.assert_frame_equal(out[sid], _fred_expected(sid))


def _check_china_outage_then_recovers(tw, w: _FredWorld, clock) -> None:
    """FRED 全掛 → 0/5、不入快取；冷卻期內重叫不打上游；恢復＋冷卻期滿 → 下一次呼叫即 5/5；之後照舊快取。"""
    out = tw.fetch_china_macro(_KEY)
    assert list(out) == _SIDS
    for sid in _SIDS:
        _assert_empty_df(out[sid])
    assert w.calls == {sid: 1 for sid in _SIDS}
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    out = tw.fetch_china_macro(_KEY)
    assert _ok_sids(out) == [] and w.calls == {sid: 1 for sid in _SIDS}, "冷卻期內重叫：不重打上游"
    w.all_ok()                                             # 上游恢復
    clock["now"] += 1                                      # 剛好滿冷卻期（`<` 比較）
    out = tw.fetch_china_macro(_KEY)
    assert _ok_sids(out) == _SIDS, \
        "冷卻期滿的下一次呼叫即拿到 5/5（修前：30 分鐘內一直 0/5、上游 0 次）"
    assert w.calls == {sid: 2 for sid in _SIDS}
    _assert_all_expected(out)
    clock["now"] += TTL_30MIN - 1
    for _ in range(3):
        assert tw.fetch_china_macro(_KEY) is out, "完整結果照舊入 30 分鐘快取（同一個物件）"
    assert w.calls == {sid: 2 for sid in _SIDS}


def _check_china_partial_failure(tw, w: _FredWorld, clock) -> None:
    """只有 1 條失敗 → 4/5、不入快取；重算時 4 條命中 fetch_fred 的 30 分鐘成功快取、1 條在退避 → 上游 0 次；
    恢復＋冷卻期滿 → 只重打失敗那 1 條 → 5/5 → 照舊快取。"""
    bad = FRED_CHN_PMI
    w.all_ok()
    w.resp[bad] = None
    t_fail = clock["now"]
    out = tw.fetch_china_macro(_KEY)
    assert _ok_sids(out) == [s for s in _SIDS if s != bad]
    _assert_empty_df(out[bad])
    assert w.calls == {sid: 1 for sid in _SIDS}
    clock["now"] += 10
    again = tw.fetch_china_macro(_KEY)
    assert again is not out, "結果不完整 → 不入 30 分鐘快取（每次重算）"
    assert _ok_sids(again) == _ok_sids(out) and w.calls == {sid: 1 for sid in _SIDS}, \
        "重算不轟炸：成功 4 條在 fetch_fred 成功快取、失敗 1 條在退避"
    w.resp[bad] = _fred_ok(_ROWS[bad])
    clock["now"] = t_fail + FAIL_COOLDOWN_SEC
    out = tw.fetch_china_macro(_KEY)
    _assert_all_expected(out)
    assert w.calls == {sid: (2 if sid == bad else 1) for sid in _SIDS}, "只重打失敗的那 1 條"
    assert tw.fetch_china_macro(_KEY) is out, "5/5 → 照舊快取"


def _check_china_success_cached(tw, w: _FredWorld, clock) -> None:
    """全部成功：回傳逐字同修前、同一個物件快取 30 分鐘（TTL 同修前）。"""
    w.all_ok()
    out = tw.fetch_china_macro(_KEY)
    _assert_all_expected(out)
    clock["now"] += TTL_30MIN - 1
    assert tw.fetch_china_macro(_KEY) is out, "完整結果照舊入 30 分鐘快取（同一個物件）"
    assert w.calls == {sid: 1 for sid in _SIDS}
    clock["now"] += 1                                      # 快取與 fetch_fred 的 30 分鐘同時到期
    out2 = tw.fetch_china_macro(_KEY)
    assert out2 is not out and w.calls == {sid: 2 for sid in _SIDS}
    _assert_all_expected(out2)


class TestD2f13ChinaMacro:
    def test_outage_not_cached_backs_off_then_recovers(self, fred_world, clock):
        _check_china_outage_then_recovers(TW, fred_world, clock)

    def test_partial_failure_not_cached_only_failed_series_refetched(self, fred_world, clock):
        _check_china_partial_failure(TW, fred_world, clock)

    def test_success_identical_and_cached_30min(self, fred_world, clock):
        _check_china_success_cached(TW, fred_world, clock)

    def test_no_key_path_unchanged(self, fred_world, clock, capsys):
        """api_key 空 → `{}`、不打上游，且照舊入快取（設定狀態、不是抓取失敗；同修前）。"""
        assert TW.fetch_china_macro("") == {}
        assert TW.fetch_china_macro("") == {}
        assert capsys.readouterr().out.count("[tw_macro/china_macro] fred_api_key 空,跳過") == 1, \
            "第二次命中快取、函式本體沒再跑"
        assert fred_world.calls == {sid: 0 for sid in _SIDS}

    def test_all_dot_series_counts_as_incomplete_but_never_hits_upstream(self, fred_world, clock):
        """FRED 200 但該序列全是 '.'（fetch_fred 成功路徑、得到空表並入它自己的 30 分鐘快取）：
        本層視為不完整、不入快取；重算時那條命中 fetch_fred 的成功快取 → 上游 0 次（退避路徑之一）。"""
        fred_world.all_ok()
        fred_world.resp[FRED_CHN_CPI] = _fred_ok([("2026-01-01", "."), ("2026-02-01", ".")])
        out = TW.fetch_china_macro(_KEY)
        assert _ok_sids(out) == [s for s in _SIDS if s != FRED_CHN_CPI]
        assert out[FRED_CHN_CPI].empty and list(out[FRED_CHN_CPI].columns) == \
            ["date", "value", "source", "fetched_at"], "修前同形：有欄位的空表"
        for _ in range(3):
            clock["now"] += 60
            again = TW.fetch_china_macro(_KEY)
            assert again is not out and _ok_sids(again) == _ok_sids(out)
        assert fred_world.calls == {sid: 1 for sid in _SIDS}

    def test_worker_exception_series_counts_as_incomplete(self, fred_world, clock, capsys):
        """某條在執行緒內拋例外（修前：補空表、整包照存 30 分鐘）→ 本層不入快取；補位與 log 同修前。"""
        fred_world.all_ok()
        fred_world.resp[FRED_CHN_M2] = _fred_ok([("not-a-date", "1.0")])   # to_datetime 拋例外
        out = TW.fetch_china_macro(_KEY)
        assert _ok_sids(out) == [s for s in _SIDS if s != FRED_CHN_M2]
        _assert_empty_df(out[FRED_CHN_M2])
        assert f"[tw_macro/china_macro/{FRED_CHN_M2}] 失敗:" in capsys.readouterr().out
        fred_world.resp[FRED_CHN_M2] = _fred_ok(_ROWS[FRED_CHN_M2])
        clock["now"] += 1
        _assert_all_expected(TW.fetch_china_macro(_KEY))   # 例外那條沒進快取 → 下一次即重抓成功


class TestD2f13ChinaCallerContract:
    """L2 `macro_helpers.get_china_snapshot`（唯一的 production 呼叫端，L5 `tabs/macro/helpers` 經它取數）：
    每一次呼叫拿到的 snapshot ＝ 修前模型同一次呼叫拿到的（本批只改「入不入快取」）。"""

    @pytest.mark.parametrize("bad", [(), (FRED_CHN_PMI,), (FRED_USDCNY, FRED_CHN_M2), tuple(_SIDS)],
                             ids=["all_ok", "pmi_down", "two_down", "all_down"])
    def test_snapshot_identical_to_prefix_first_call(self, bad, fred_world, clock, monkeypatch, registry):
        from src.compute.macro import macro_helpers as MH
        fred_world.all_ok()
        for sid in bad:
            fred_world.resp[sid] = None
        got = MH.get_china_snapshot(_KEY)
        pre = _prefix_tw("contract")
        monkeypatch.setattr(MC, "_FRED_CACHE", {})
        monkeypatch.setattr(MC, "_FRED_FAIL_CACHE", {})
        monkeypatch.setattr(TW, "fetch_china_macro", pre.fetch_china_macro)
        want = MH.get_china_snapshot(_KEY)
        assert got == want and list(got) == list(want)
        # m2_yoy 需 ≥13 個月才算得出年增率（本測資只有 2 筆）→ 只數其餘 4 個直接取值的欄位
        direct = {"cli": FRED_CHN_OECD_CLI, "pmi": FRED_CHN_PMI, "cpi_yoy": FRED_CHN_CPI, "usdcny": FRED_USDCNY}
        assert {k for k, sid in direct.items() if got[k]["value"] is not None} == \
            {k for k, sid in direct.items() if sid not in bad}


# ══════════════════════════════════════════════════════════════════
# D2-f13 ② fetch_usdtwd_close
# ══════════════════════════════════════════════════════════════════
_TS = [_T0 + _DAY * i for i in range(3)]
_CLOSE = [32.105, 32.2, 32.35]


def _yf_resp(close) -> _Raw:
    return _Raw({"chart": {"result": [{"timestamp": list(_TS[:len(close)]),
                                       "indicators": {"quote": [{"close": list(close)}]}}]}})


def _usdtwd_expected() -> pd.DataFrame:
    """修前成功路徑的字面：timestamp（秒）→ 日期（normalize）、收盤、固定 source、fetched_at。"""
    return pd.DataFrame({
        "date": pd.to_datetime(_TS, unit="s").normalize(),
        "value": pd.Series(_CLOSE, dtype="float64").values,
        "source": "Yahoo:TWD=X:Close",
        "fetched_at": _FROZEN.isoformat(),
    }).reset_index(drop=True)


def _check_usdtwd_outage_then_recovers(tw, y: _YfWorld, clock) -> None:
    """Yahoo 失敗 → None、不入快取；冷卻期內重叫不打上游；恢復＋冷卻期滿 → 下一次呼叫即有資料；之後照舊快取。"""
    assert tw.fetch_usdtwd_close(days_back=60) is None and y.calls == 1
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    assert tw.fetch_usdtwd_close(days_back=60) is None
    assert y.calls == 1, "冷卻期內重叫：不重打上游"
    y.resp = _yf_resp(_CLOSE)
    clock["now"] += 1
    df = tw.fetch_usdtwd_close(days_back=60)
    assert df is not None, "冷卻期滿的下一次呼叫即拿到資料（修前：1 小時內一直 None、上游 0 次）"
    assert y.calls == 2
    pd.testing.assert_frame_equal(df, _usdtwd_expected())
    clock["now"] += TTL_1HOUR - 1
    assert tw.fetch_usdtwd_close(days_back=60) is df and y.calls == 2, "有資料 → 照舊入 1 小時快取"


def _check_usdtwd_sanity_empty_recomputed_without_upstream(tw, y: _YfWorld, clock, capsys) -> None:
    """Yahoo 有回、但全落在 sanity [25,40] 外 → None：不入本層快取（每次重算），但底層那份序列在它自己的
    1 小時成功快取 → 重算不打上游。"""
    y.resp = _yf_resp([1.0, 2.0, 3.0])
    capsys.readouterr()
    for _ in range(4):
        assert tw.fetch_usdtwd_close(days_back=60) is None
        clock["now"] += 60
    assert y.calls == 1, "底層成功快取擋住上游"
    assert capsys.readouterr().out.count("[tw_macro/usdtwd] sanity 過濾後資料為空") == 4, \
        "None 不入快取 → 每次都重算（修前：1 小時內只算 1 次、其餘回快取裡的 None）"


def _check_usdtwd_success_cached(tw, y: _YfWorld, clock) -> None:
    y.resp = _yf_resp(_CLOSE)
    df = tw.fetch_usdtwd_close(days_back=60)
    pd.testing.assert_frame_equal(df, _usdtwd_expected())
    clock["now"] += TTL_1HOUR - 1
    assert tw.fetch_usdtwd_close(days_back=60) is df and y.calls == 1, "有資料 → 照舊入 1 小時快取（同一個物件）"


class TestD2f13UsdTwd:
    def test_outage_not_cached_backs_off_then_recovers(self, yf_world, clock):
        _check_usdtwd_outage_then_recovers(TW, yf_world, clock)

    def test_sanity_empty_not_cached_and_no_upstream(self, yf_world, clock, capsys):
        _check_usdtwd_sanity_empty_recomputed_without_upstream(TW, yf_world, clock, capsys)

    def test_success_identical_and_cached_1hour(self, yf_world, clock):
        _check_usdtwd_success_cached(TW, yf_world, clock)

    def test_parse_failure_also_backs_off(self, yf_world, clock):
        """底層第三個失敗出口（回應解析失敗）同樣在冷卻期內不重打。"""
        yf_world.resp = _Raw(exc=ValueError("Expecting value"))
        for _ in range(4):
            assert TW.fetch_usdtwd_close(days_back=60) is None
            clock["now"] += 30
        assert yf_world.calls == 1


class TestD2f13UsdTwdCallerContract:
    """L5 `etf_tab_portfolio._fetch_usdtwd_spot`（唯一的 production 呼叫端）：主來源有值時回
    (匯率, as_of, source) 同修前；主來源 None → 走既有備援；主來源恢復＋冷卻期滿 → 下一次即回到主來源
    （修前：None 被凍 1 小時，這 1 小時一直落在備援）。"""

    def test_fallback_while_down_then_primary_right_after_cooldown(self, yf_world, clock, monkeypatch):
        import src.data.etf.etf_fetch as EF
        from src.ui.etf import etf_tab_portfolio as ETP
        fb = {"n": 0}

        def _fake_fep(ticker, period="5d", *a, **k):
            fb["n"] += 1
            return pd.DataFrame({"Close": [31.9]}, index=pd.to_datetime(["2026-01-05"]))
        monkeypatch.setattr(EF, "fetch_etf_price", _fake_fep)

        yf_world.resp = None
        assert ETP._fetch_usdtwd_spot() == (31.9, "2026-01-05", "Yahoo:TWD=X:Close")
        assert fb["n"] == 1 and yf_world.calls == 1
        yf_world.resp = _yf_resp(_CLOSE)
        clock["now"] += FAIL_COOLDOWN_SEC
        assert ETP._fetch_usdtwd_spot() == (32.35, "2026-01-03", "Yahoo:TWD=X:Close")
        assert fb["n"] == 1 and yf_world.calls == 2, "主來源恢復 → 下一次即不再走備援"


# ══════════════════════════════════════════════════════════════════
# `_ttl_cache` 判定式掛鉤：預設行為不變、只有兩支函式啟用
# ══════════════════════════════════════════════════════════════════
def _ttl_cache_decorators() -> dict:
    tree = ast.parse(pathlib.Path(TW.__file__).read_text(encoding="utf-8"))
    out = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef):
            for d in fn.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "id", None) == "_ttl_cache":
                    out[fn.name] = ast.unparse(d)
    return out


class TestTtlCacheHook:
    def test_default_still_caches_none_and_empty(self, clock):
        """沒給 `cache_if` → 修前行為：None／空表照樣入快取。"""
        calls = {"n": 0}

        @TW._ttl_cache(ttl_sec=60, maxsize=4)
        def _f(x):
            calls["n"] += 1
            return None if x == "none" else pd.DataFrame()
        assert _f("none") is None and _f("none") is None
        a = _f("empty")
        assert _f("empty") is a and calls["n"] == 2
        clock["now"] += 60
        _f("none")
        assert calls["n"] == 3, "TTL 同修前（`<` 比較，剛好滿即過期）"

    def test_cache_if_false_returns_result_without_caching(self, clock):
        calls = {"n": 0}
        val = object()

        @TW._ttl_cache(ttl_sec=60, maxsize=4, cache_if=lambda r: r is not val)
        def _f(x):
            calls["n"] += 1
            return val if x == "bad" else [x]
        assert _f("bad") is val and _f("bad") is val and calls["n"] == 2, "判為失敗 → 照常回傳、不入快取"
        ok = _f("ok")
        assert _f("ok") is ok and calls["n"] == 3, "判為成功 → 照舊快取"

    def test_rejected_result_does_not_evict_cached_entries(self, clock):
        """不入快取就不觸發 LRU 逐出 —— 失敗不會把別的參數的成功結果擠掉。"""
        calls = {"n": 0}

        @TW._ttl_cache(ttl_sec=60, maxsize=1, cache_if=lambda r: r is not None)
        def _f(x):
            calls["n"] += 1
            return None if x == "bad" else [x]
        ok = _f("ok")
        for _ in range(3):
            assert _f("bad") is None
        assert _f("ok") is ok and calls["n"] == 4

    def test_cache_clear_and_wraps_unchanged(self):
        assert callable(TW.fetch_china_macro.cache_clear) and callable(TW.fetch_usdtwd_close.cache_clear)
        assert TW.fetch_china_macro.__wrapped__.__name__ == "fetch_china_macro"
        assert TW.fetch_usdtwd_close.__wrapped__.__name__ == "fetch_usdtwd_close"

    def test_only_two_fetchers_opt_in_ttl_and_maxsize_unchanged(self):
        decos = _ttl_cache_decorators()
        opted = {k: v for k, v in decos.items() if "cache_if" in v}
        assert opted == {
            "fetch_usdtwd_close": "_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=4, cache_if=_usdtwd_ok)",
            "fetch_china_macro": "_ttl_cache(ttl_sec=TTL_30MIN, maxsize=4, cache_if=_china_macro_complete)",
        }, "只有這兩支啟用；TTL／maxsize 同修前"
        assert decos["fetch_cbc_discount_rate"] == "_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=4)", \
            "D-016（疑似死碼）本批不動"

    @pytest.mark.parametrize("result,want", [
        ({}, True),
        ({s: pd.DataFrame({"value": [1.0]}) for s in _SIDS}, True),
        ({**{s: pd.DataFrame({"value": [1.0]}) for s in _SIDS}, FRED_CHN_PMI: pd.DataFrame()}, False),
        ({s: pd.DataFrame() for s in _SIDS}, False),
        ({**{s: pd.DataFrame({"value": [1.0]}) for s in _SIDS}, FRED_CHN_CPI: None}, False),
    ], ids=["no_key", "all_ok", "one_empty", "all_empty", "one_none"])
    def test_china_criterion(self, result, want):
        assert TW._china_macro_complete(result) is want

    @pytest.mark.parametrize("result,want", [(None, False), (pd.DataFrame({"value": [32.0]}), True)],
                             ids=["none", "df"])
    def test_usdtwd_criterion(self, result, want):
        """fetch_usdtwd_close 只會回 None 或有資料的表（兩個「無資料」出口都回 None）。"""
        assert TW._usdtwd_ok(result) is want


# ══════════════════════════════════════════════════════════════════
# D2-f14 ① 退避紀錄寫入時與既有紀錄取 max
# ══════════════════════════════════════════════════════════════════
_FRED_KEY = ("DGS10", "k-test", 120)
_OHLCV_KEY = ("^TWII", "9mo", "1d")
_YFC_TICKER = "^VIX"
_YFC_KEY = (_YFC_TICKER, "1d")                        # _fetch_yf_close_base 的鍵 (ticker, interval)
_ALL_NULL_CLOSE = _Raw({"chart": {"result": [{"timestamp": [_T0, _T0 + _DAY],
                                              "indicators": {"quote": [{"close": [None, None]}]}}]}})
#: 八個失敗出口 → (哪支函式, 讓「較早開始的 A」走到該出口的回應)
_EXITS = {
    "fred_none": ("fred", None),
    "fred_parse": ("fred", _Raw(exc=ValueError("Expecting value: line 1 column 1 (char 0)"))),
    "fred_obs_empty": ("fred", _Raw({"observations": []})),
    "ohlcv_none": ("ohlcv", None),
    "ohlcv_parse": ("ohlcv", _Raw(exc=ValueError("Expecting value: line 1 column 1 (char 0)"))),
    "yfc_none": ("yfc", None),
    "yfc_all_null": ("yfc", _ALL_NULL_CLOSE),
    "yfc_parse": ("yfc", _Raw(exc=ValueError("Expecting value: line 1 column 1 (char 0)"))),
}


def _assert_empty_close(s) -> None:
    """`_fetch_yf_close_base` 三個失敗出口都是 `pd.Series(dtype=float, name=ticker)` —— 逐字比。"""
    ref = pd.Series(dtype=float, name=_YFC_TICKER)
    assert type(s) is pd.Series
    pd.testing.assert_series_equal(s, ref)
    assert s.attrs == {}


def _target(mc, kind: str, monkeypatch):
    """(呼叫, 鍵, 讀退避紀錄, 失敗回傳的逐字檢查)；並清空該函式用到的快取。"""
    if kind == "fred":
        names, rec_name = ("_FRED_CACHE", "_FRED_FAIL_CACHE"), "_FRED_FAIL_CACHE"
        call, key, check = (lambda: mc.fetch_fred(*_FRED_KEY)), _FRED_KEY, _assert_empty_df
    elif kind == "ohlcv":
        names, rec_name = ("_YF_OHLCV_FAIL_CACHE", "_YF_OHLCV_OK_GEN_CACHE"), "_YF_OHLCV_FAIL_CACHE"
        call, key, check = (lambda: mc.fetch_yf_ohlcv(*_OHLCV_KEY)), _OHLCV_KEY, _assert_empty_df
    else:
        names, rec_name = ("_YF_CLOSE_CACHE", "_YF_CLOSE_EMPTY_FAIL_CACHE"), "_YF_CLOSE_EMPTY_FAIL_CACHE"
        call, key, check = (lambda: mc.fetch_yf_close(_YFC_TICKER)), _YFC_KEY, _assert_empty_close
    for name in names:
        monkeypatch.setattr(mc, name, {})
    return call, key, (lambda: dict(getattr(mc, rec_name))), check


def _check_late_failure_keeps_newer_record(mc, exit_name: str, clock, monkeypatch) -> None:
    """A 在 t0 開始、還在路上；B 在 t0+10 開始、先失敗（記 t0+10）；A 在 t0+15 才經由 `exit_name` 出口失敗。
    寫入取 max → 紀錄仍是 t0+10：B 的冷卻期內（t0+189）不重打；t0+190 期滿即重打
    （時點仍是「呼叫開始」—— 沒改成失敗當下 t0+15，冷卻沒被拉長）。"""
    kind, a_resp = _EXITS[exit_name]
    call, key, rec, check = _target(mc, kind, monkeypatch)
    t0 = clock["now"]
    st = {"n": 0}

    def _fetch(*_a, **_k):
        st["n"] += 1
        if st["n"] == 1:                                   # A 還在路上
            clock["now"] = t0 + 10
            check(call())                                  # B：晚開始、先失敗
            assert rec() == {key: t0 + 10}
            clock["now"] = t0 + 15                         # A 的失敗晚到
            return a_resp
        return None
    monkeypatch.setattr(mc, "fetch_url", _fetch)
    check(call())                                          # A
    assert rec() == {key: t0 + 10}, "較早開始、較晚失敗的 A 不得用較舊的 t0 蓋掉 B 的 t0+10"
    clock["now"] = t0 + 10 + FAIL_COOLDOWN_SEC - 1
    check(call())
    assert st["n"] == 2, "B 的冷卻期內不重打（修前：紀錄被蓋回 t0，t0+180 起就重打）"
    clock["now"] = t0 + 10 + FAIL_COOLDOWN_SEC
    check(call())
    assert st["n"] == 3, "冷卻期從 B 的「呼叫開始」起算、期滿即重打（沒改成失敗當下 → 冷卻沒被拉長）"
    assert rec() == {key: t0 + 10 + FAIL_COOLDOWN_SEC}


class TestD2f14MaxOnWrite:
    @pytest.mark.parametrize("exit_name", sorted(_EXITS))
    def test_late_failure_of_earlier_call_does_not_shorten_cooldown(self, exit_name, clock, monkeypatch):
        _check_late_failure_keeps_newer_record(MC, exit_name, clock, monkeypatch)

    @pytest.mark.parametrize("exit_name", sorted(_EXITS))
    def test_sequential_failures_restart_from_this_call(self, exit_name, clock, monkeypatch):
        """沒有並行時行為同修前：過期後再失敗 → 以這次的時點重新起算（max 取到的就是這次的 now）。"""
        kind, resp = _EXITS[exit_name]
        n = {"n": 0}

        def _fetch(*_a, **_k):
            n["n"] += 1
            return resp
        monkeypatch.setattr(MC, "fetch_url", _fetch)
        call, key, rec, check = _target(MC, kind, monkeypatch)
        check(call())
        assert rec() == {key: clock["now"]}
        clock["now"] += FAIL_COOLDOWN_SEC - 1
        check(call())
        assert n["n"] == 1, "冷卻期內不重打（同修前）"
        clock["now"] += 1
        check(call())
        assert n["n"] == 2 and rec() == {key: clock["now"]}


# ══════════════════════════════════════════════════════════════════
# D2-f14 ② `_yf_latest`：0.0 算有值
# ══════════════════════════════════════════════════════════════════
_SRC = "macro_alert:fetch_macro_snapshot(session+yfinance)"


def _install_batch(ma, monkeypatch, rets: list) -> dict:
    """換掉 `_yf_latest` 底下的 L1 批次函式（依序回 rets 裡的 dict），並數它被叫幾次。"""
    assert hasattr(ma._yf_latest, "clear"), "前提：_yf_latest 是真的 st.cache_data（否則驗不到快取）"
    plan = {"n": 0}

    def _batch(tickers):
        r = rets[min(plan["n"], len(rets) - 1)]
        plan["n"] += 1
        return dict(r)
    monkeypatch.setattr(ma, "_macro_core_yf_latest", _batch)
    ma._yf_latest.clear()
    return plan


def _check_zero_is_a_value(ma, monkeypatch) -> None:
    """值為 0.0 的檔算「取到了」：`_yf_latest` 正常回傳（不拋 `_YfLatestIncomplete`）、照舊入 30 分鐘快取；
    呼叫端照樣把 0.0 放進快照。"""
    plan = _install_batch(ma, monkeypatch, [{"^TNX": 0.0, "DX-Y.NYB": 0.0}])
    try:
        try:
            got = ma._yf_latest(("^TNX", "DX-Y.NYB"))
        except ma._YfLatestIncomplete:
            raise AssertionError("0.0 被當成缺值 → 拋 _YfLatestIncomplete、不入快取") from None
        assert got == {"^TNX": 0.0, "DX-Y.NYB": 0.0}
        snap = ma.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}})
        assert plan["n"] == 1, "0.0 算有值 → 完整結果照舊入快取（第二次不再叫 L1）"
        assert snap == {"vix": 20.0, "us10y": 0.0, "dxy": 0.0, "source": _SRC,
                        "fetched_at": _FROZEN.isoformat()}
    finally:
        ma._yf_latest.clear()


class TestD2f14YfLatestZeroIsAValue:
    def test_zero_is_a_value_and_cached(self, monkeypatch, frozen_now):
        _check_zero_is_a_value(MA, monkeypatch)

    def test_zero_next_to_none_still_incomplete_and_zero_kept(self, monkeypatch, frozen_now):
        """同一批裡另一檔真的缺（None）→ 仍判不完整、不入快取；0.0 那檔照樣進快照。"""
        plan = _install_batch(MA, monkeypatch, [{"^TNX": 0.0, "DX-Y.NYB": None}])
        try:
            with pytest.raises(MA._YfLatestIncomplete) as ei:
                MA._yf_latest(("^TNX", "DX-Y.NYB"))
            assert ei.value.payload == {"^TNX": 0.0, "DX-Y.NYB": None}
            snap = MA.fetch_macro_snapshot(session_macro={"vix": {"current": 20.0}})
            assert plan["n"] == 2, "含 None → 不入快取"
            assert snap == {"vix": 20.0, "us10y": 0.0, "source": _SRC, "fetched_at": _FROZEN.isoformat()}
        finally:
            MA._yf_latest.clear()


# ══════════════════════════════════════════════════════════════════
# 真的 fetch_url ＋ 假 HTTP session：數實際 GET 次數（含 fetch_url 自己的重試與 NAS 中繼）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def http(monkeypatch, frozen_now):
    """`routes[鍵] = (status, body)`；FRED 的鍵是 series_id、Yahoo 的鍵是 ticker。"""
    routes: dict = {}
    gets: dict = {}
    relay = {"n": 0}
    lock = threading.Lock()

    class _Sess:
        def get(self, url, headers=None, params=None, timeout=None, proxies=None, verify=None):
            key = (params or {}).get("series_id") or url.rsplit("/", 1)[-1]
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


class _SyncPool:
    """依序執行的 ThreadPoolExecutor 替身（只給本段兩條 china 測試用）。

    `proxy_helper._url_cache_put` 沒有鎖，多執行緒同時寫入有機率拋
    `RuntimeError: dictionary keys changed during iteration`（既有問題、不在本批範圍，見交付報告）——
    這兩條只數「真的 fetch_url」打出去的 GET 次數、不測並行，改成依序執行以免偶發紅燈。"""

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *a, **k):
        fut = concurrent.futures.Future()
        try:
            fut.set_result(fn(*a, **k))
        except BaseException as e:  # noqa: BLE001 —— 同真 executor：例外存進 future，由 .result() 拋
            fut.set_exception(e)
        return fut


@pytest.fixture
def sync_pool(monkeypatch):
    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", _SyncPool)


def _fred_body(sid: str) -> bytes:
    import json
    return json.dumps({"observations": [{"date": d, "value": v} for d, v in _ROWS[sid]]}).encode()


class TestUpstreamHttpCount:
    def test_china_outage_one_fetch_per_series_per_cooldown(self, http, clock, sync_pool):
        routes, gets, relay = http
        for sid in _SIDS:
            routes[sid] = _HTTP_500
        for _ in range(5):
            assert _ok_sids(TW.fetch_china_macro(_KEY)) == []
            clock["now"] += 30
        assert gets == {sid: 3 for sid in _SIDS} and relay["n"] == 5, \
            "5 次呼叫：每條只觸發 1 次 fetch_url（其內 3 次重試＋1 次中繼）—— 不入快取也不轟炸"
        clock["now"] += FAIL_COOLDOWN_SEC
        for sid in _SIDS:
            routes[sid] = (200, _fred_body(sid))
        _assert_all_expected(TW.fetch_china_macro(_KEY))
        for _ in range(3):
            TW.fetch_china_macro(_KEY)
        assert gets == {sid: 4 for sid in _SIDS} and relay["n"] == 5, "恢復後 1 次取回、之後照舊快取"

    def test_china_post_200_exception_path_bounded_by_url_cache(self, http, clock, sync_pool):
        """合成情境（真實 FRED 不會回）：HTTP 200 但 fetch_fred 解析時拋例外 —— 這條**不在** 180 秒退避裡，
        重算時由 fetch_url 的 300 秒 URL 快取擋住（每 300 秒至多 1 次 GET），不是每次 rerun 都重打。"""
        routes, gets, relay = http
        for sid in _SIDS:
            routes[sid] = (200, _fred_body(sid))
        routes[FRED_CHN_M2] = (200, b'{"observations": [{"date": "not-a-date", "value": "1.0"}]}')
        for _ in range(6):
            out = TW.fetch_china_macro(_KEY)
            assert _ok_sids(out) == [s for s in _SIDS if s != FRED_CHN_M2]
            clock["now"] += 45
        assert gets == {sid: 1 for sid in _SIDS}, "6 次呼叫、270 秒內：壞的那條 GET 1 次（URL 快取）"
        clock["now"] += 300
        TW.fetch_china_macro(_KEY)
        assert gets[FRED_CHN_M2] == 2 and relay["n"] == 0

    def test_usdtwd_outage_one_fetch_per_cooldown(self, http, clock):
        routes, gets, relay = http
        routes["TWD=X"] = _HTTP_500
        for _ in range(5):
            assert TW.fetch_usdtwd_close(days_back=60) is None
            clock["now"] += 30
        assert gets == {"TWD=X": 3} and relay["n"] == 1
        clock["now"] += FAIL_COOLDOWN_SEC
        routes["TWD=X"] = (200, b'{"chart": {"result": [{"timestamp": [%d, %d, %d], "indicators": '
                                b'{"quote": [{"close": [32.105, 32.2, 32.35]}]}}]}}' % tuple(_TS))
        pd.testing.assert_frame_equal(TW.fetch_usdtwd_close(days_back=60), _usdtwd_expected())
        for _ in range(3):
            TW.fetch_usdtwd_close(days_back=60)
        assert gets == {"TWD=X": 4} and relay["n"] == 1


# ══════════════════════════════════════════════════════════════════
# 修前模型：同一份檢查必須轉紅
# ══════════════════════════════════════════════════════════════════
#: tw_macro：`_ttl_cache` 拿掉判定兩行 ≡ 修前的無條件存入（判定式照傳、但沒人看）
_TTL_CHECK = ("            if cache_if is not None and not cache_if(result):\n"
              "                return result   # D2-f13:判為失敗／不完整 → 不入快取(回傳內容不變)\n")
#: macro_core：八個寫入換回修前字面 `= now`
_FRED_WRITE = "_FRED_FAIL_CACHE[key] = max(now, _FRED_FAIL_CACHE.get(key, now))   # D2-f14:與既有紀錄取 max\n"
_OHLCV_WRITE = "_YF_OHLCV_FAIL_CACHE[key] = max(now, _YF_OHLCV_FAIL_CACHE.get(key, now))   # D2-f14:取 max\n"
_YFC_WRITE = ("_YF_CLOSE_EMPTY_FAIL_CACHE[key] = max(now, _YF_CLOSE_EMPTY_FAIL_CACHE.get(key, now))"
              "   # D2-f14:取 max\n")
#: 出口種類 → (修後寫入字面, 修前寫入字面)
_WRITES = {
    "fred": (_FRED_WRITE, "_FRED_FAIL_CACHE[key] = now\n"),
    "ohlcv": (_OHLCV_WRITE, "_YF_OHLCV_FAIL_CACHE[key] = now\n"),
    "yfc": (_YFC_WRITE, "_YF_CLOSE_EMPTY_FAIL_CACHE[key] = now\n"),
}


def _prefix_tw(tag: str) -> types.ModuleType:
    return _mutant(TW, (_TTL_CHECK, ""), tag=f"prefix_{tag}")


def _prefix_mc(tag: str) -> types.ModuleType:
    return _mutant(MC, (*_WRITES["fred"], 3), (*_WRITES["ohlcv"], 2), (*_WRITES["yfc"], 3),
                   tag=f"prefix_{tag}")


class TestPrefixReproducesBug:
    def test_china_prefix_freezes_outage(self, fred_world, clock, registry):
        with pytest.raises(AssertionError, match="冷卻期滿的下一次呼叫即拿到 5/5"):
            _check_china_outage_then_recovers(_prefix_tw("china"), fred_world, clock)
        assert fred_world.calls == {sid: 1 for sid in _SIDS}, "修前：恢復＋過冷卻期仍 0 次上游（0/5 凍 30 分鐘）"

    def test_china_prefix_freezes_partial(self, fred_world, clock, registry):
        with pytest.raises(AssertionError, match="結果不完整 → 不入 30 分鐘快取"):
            _check_china_partial_failure(_prefix_tw("china_partial"), fred_world, clock)

    def test_usdtwd_prefix_freezes_none(self, yf_world, clock, registry):
        with pytest.raises(AssertionError, match="冷卻期滿的下一次呼叫即拿到資料"):
            _check_usdtwd_outage_then_recovers(_prefix_tw("usdtwd"), yf_world, clock)
        assert yf_world.calls == 1, "修前：恢復＋過冷卻期仍 0 次上游（None 凍 1 小時）"

    def test_usdtwd_prefix_caches_sanity_none(self, yf_world, clock, capsys, registry):
        with pytest.raises(AssertionError, match="None 不入快取"):
            _check_usdtwd_sanity_empty_recomputed_without_upstream(_prefix_tw("usdtwd_s"), yf_world, clock, capsys)

    @pytest.mark.parametrize("exit_name", sorted(_EXITS))
    def test_prefix_late_failure_shortens_cooldown(self, exit_name, clock, monkeypatch, registry):
        with pytest.raises(AssertionError, match="不得用較舊的 t0 蓋掉"):
            _check_late_failure_keeps_newer_record(_prefix_mc(exit_name), exit_name, clock, monkeypatch)


# ══════════════════════════════════════════════════════════════════
# 突變：逐一拿掉每一處修正 → 對應的檢查轉紅（其餘不受影響）
# ══════════════════════════════════════════════════════════════════
#: 各出口寫入前的唯一前文（取自 D2-f6／D2-f10／D2-f2／Q2-r2 的註解與 log 字面）
_EXIT_CTX = {
    "fred_none": "同一把鎖、同一個鍵、同一個時點(本次呼叫的 now);不入成功快取;回傳同修前。\n"
                 "        with _FRED_CACHE_LOCK:\n            ",
    "fred_parse": "        with _FRED_CACHE_LOCK:   # D2-f6:解析失敗同樣記退避(寫法同上)\n            ",
    "fred_obs_empty": "不必每次 rerun 都再走一次 fetch_url 與解析。回傳同修前。\n"
                      "        with _FRED_CACHE_LOCK:\n            ",
    "ohlcv_none": "# 時點＝本次呼叫的 now(同 D2-f2);期間有人成功過(世代已變)就不記。\n"
                  "        with _YF_OHLCV_FAIL_LOCK:\n"
                  "            if _YF_OHLCV_OK_GEN_CACHE.get(key, 0) == _gen:\n                ",
    "ohlcv_parse": "# D2-f10:解析失敗(JSON 壞／結構不符／長度對不上)同樣記退避(寫法同上)\n"
                   "        with _YF_OHLCV_FAIL_LOCK:\n"
                   "            if _YF_OHLCV_OK_GEN_CACHE.get(key, 0) == _gen:\n                ",
    "yfc_none": "fetch_url 回 None(不快取,冷卻 {_FAIL_COOLDOWN_SEC:.0f}s)\")\n"
                "        with _YF_CLOSE_CACHE_LOCK:\n            ",
    "yfc_all_null": "收盤全為空值(不快取,冷卻 {_FAIL_COOLDOWN_SEC:.0f}s)\")\n"
                    "            with _YF_CLOSE_CACHE_LOCK:\n                ",
    "yfc_parse": "解析失敗: {e}\")\n"
                 "        with _YF_CLOSE_CACHE_LOCK:\n            ",
}


def _one_exit_reverted(exit_name: str) -> types.ModuleType:
    ctx = _EXIT_CTX[exit_name]
    new, old = _WRITES[_EXITS[exit_name][0]]
    return _mutant(MC, (ctx + new, ctx + old), tag=f"one_{exit_name}")


class TestMutations:
    def test_m1_china_decorator_without_criterion(self, fred_world, yf_world, clock, capsys, monkeypatch,
                                                  registry):
        m = _mutant(TW, ("@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=4, cache_if=_china_macro_complete)",
                         "@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=4)"), tag="m1")
        with pytest.raises(AssertionError, match="冷卻期滿的下一次呼叫即拿到 5/5"):
            _check_china_outage_then_recovers(m, fred_world, clock)
        _check_usdtwd_outage_then_recovers(m, yf_world, clock)      # 另一支不受影響

    def test_m2_usdtwd_decorator_without_criterion(self, yf_world, clock, registry):
        m = _mutant(TW, ("@_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=4, cache_if=_usdtwd_ok)",
                         "@_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=4)"), tag="m2")
        with pytest.raises(AssertionError, match="冷卻期滿的下一次呼叫即拿到資料"):
            _check_usdtwd_outage_then_recovers(m, yf_world, clock)

    def test_m3_china_criterion_any_instead_of_all(self, fred_world, clock, registry):
        """判準寫成「有一條就算成功」→ 全掛那種抓得到、半邊失敗那種抓不到 —— 由 partial 檢查擋住。"""
        m = _mutant(TW, ("return all(df is not None and not df.empty for df in result.values())",
                         "return any(df is not None and not df.empty for df in result.values())"), tag="m3")
        with pytest.raises(AssertionError, match="結果不完整 → 不入 30 分鐘快取"):
            _check_china_partial_failure(m, fred_world, clock)

    def test_m4_hook_inverted_success_no_longer_cached(self, fred_world, yf_world, clock, registry):
        m = _mutant(TW, ("if cache_if is not None and not cache_if(result):",
                         "if cache_if is not None and cache_if(result):"), tag="m4")
        with pytest.raises(AssertionError, match="完整結果照舊入 30 分鐘快取"):
            _check_china_success_cached(m, fred_world, clock)
        with pytest.raises(AssertionError, match="有資料 → 照舊入 1 小時快取"):
            _check_usdtwd_success_cached(m, yf_world, clock)

    @pytest.mark.parametrize("exit_name", sorted(_EXITS))
    def test_m5_each_exit_reverted_alone(self, exit_name, clock, monkeypatch, registry):
        """只把這一個出口換回 `= now`：這個出口的檢查轉紅，其餘四個出口照樣通過（每處修正各自有測試擋）。"""
        m = _one_exit_reverted(exit_name)
        with pytest.raises(AssertionError, match="不得用較舊的 t0 蓋掉"):
            _check_late_failure_keeps_newer_record(m, exit_name, clock, monkeypatch)
        for other in sorted(set(_EXITS) - {exit_name}):
            clock["now"] += 10 * FAIL_COOLDOWN_SEC
            _check_late_failure_keeps_newer_record(m, other, clock, monkeypatch)

    def test_m6_yf_latest_falsy_check_treats_zero_as_missing(self, monkeypatch, frozen_now):
        m = _mutant(MA, ("if any(out.get(t) is None for t in tickers):",
                         "if any(not out.get(t) for t in tickers):"), tag="m6")
        with pytest.raises(AssertionError, match="0.0 被當成缺值"):
            _check_zero_is_a_value(m, monkeypatch)
