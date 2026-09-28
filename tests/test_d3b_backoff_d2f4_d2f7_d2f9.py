# -*- coding: utf-8 -*-
"""資料層修錯（2026-09-28，CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）三條：

  · **D2-f4** `yf_proxy.cached_history`（`st.cache_data` 1 小時、max_entries=200）：修前 yfinance
    **拋例外**（例：429 `YFRateLimitError`）時回的空表被快取 1 小時 —— Yahoo 恢復後同參數仍回空表、
    上游只被叫 1 次（v1 選股網、v2 RS 卡、每日清單都吃這一層）。現在快取層 `_cached_history_cached`
    讓例外往上拋（`st.cache_data` 不快取例外），外層 `cached_history` 接住、記 `FailCooldown`
    （`FAIL_COOLDOWN_SEC`）：冷卻期內同一 (ticker, period) 不重打、期滿重抓、成功即解除。
    手法同同檔 `cached_dividends`（Q5-r2-r3）。**「沒拋、只回 None／空表」照舊快取**
    （這一層與「真的沒資料」分不出來，不猜，同 Q5-r2 判準）。
  · **D2-f7** `rs_leader_service`：③ 空排行裡「大盤正常、存活池**每一檔**都完全抓不到 K 線」修前被
    快取 1 小時 —— 個股恢復後仍原樣回傳失敗。現在快取層（原 `_scan_cached`，改名 `_scan_body`）
    改拋 `_PoolPricesFetchFailed`（`_UpstreamFetchFailed` 子類別，不入快取），外層 `_scan_cached`
    接住並記**掃描層退避**（一次掃描要打數百檔上游，不能每次 rerun 都重掃）。其餘結果（含混合／
    太短／大盤凍結／存活池為空／beat_only 後 0 檔等空排行）照舊快取。
    **批 D3b QA N1（同日）**：固定 180 秒冷卻在「Yahoo＋FinMind 持續全失敗、每 60 秒 rerun」下
    1 小時會重掃 21 次（修前 1 次）→ 掃描層改**遞增退避**：`shared.fail_cooldown.FailCooldown`
    新增選用參數 `max_seconds`（**預設 None ＝ 關閉，行為逐字不變**，`TestFailCooldownDefaultUnchanged`
    以新增前的原始實作當參考模型逐步比對），RS 掃描層開啟：`FAIL_COOLDOWN_SEC` 起每次失敗加倍、
    上限 `TTL_1HOUR`、成功即歸零。負載測試見 `TestQaN1LoadAmplification`。
  · **D2-f9** `run_rs_leader_scan(refresh=True)`：刪掉兩行空操作 `_clear(fetch_yf_close)`、
    `_clear(fetch_stock_history_1y)`（兩者都沒有 `.clear`），docstring 改成實情；零行為變更
    （`TestD2f9RefreshUnchanged` 以「修前那兩行放回去」的對照模組逐項比對）。

「修前」的回傳一律用**獨立寫出的期望值**比對（不從被測檔推導）。
不觸網：一律換掉 `yfinance.Ticker`／存活池／大盤／逐檔抓價／FinMind 備援／涵蓋率。
冷卻期用假時鐘：**只換 `shared.fail_cooldown` 的 `time`**（`st.cache_data` 的 TTL 不受影響，
故「把假時鐘推過冷卻期仍不重打」＝ 真的在 1 小時成功快取裡，不是在退避裡）。
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

import numpy as np
import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

import shared.fail_cooldown as FC
import src.data.core.data_loader as DL
import src.data.proxy as PX
import src.data.proxy.yf_proxy as YP
import src.services.fundamental_screener_service as FSS
import src.services.rs_leader_service as RS
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from shared.rs_screen_thresholds import (
    RS_LEADER_TOP_N,
    RS_LEADER_VERSION,
    RS_MIN_ALIGNED_ROWS,
    RS_SCAN_MAX,
)
from shared.ttls import TTL_1HOUR
from src.compute.screener.rs_leader_screener import (
    market_interval_return,
    rank_rs_leaders,
    to_rows,
)


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str], tag: str) -> types.ModuleType:
    """同 tests/test_d3_backoff_d2f1_d2f2.py：原始碼字面替換後另建一份模組（真模組不動）。

    `tag` 讓每個突變體有自己的模組名 —— `st.cache_data` 以「模組名＋函式名＋原始碼」當快取鍵。
    """
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_d3b_{tag}_{mod.__name__.rsplit('.', 1)[-1]}"
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
# 共用：假時鐘、合成 K 線、假 yfinance
# ══════════════════════════════════════════════════════════════════
_N = 160
_LB = 120
_COVERAGE = "（涵蓋率替身）"
_FAIL_NOTE = "⚠️ 大盤 ^TWII 抓取失敗（Yahoo 暫時不可用），無基準可比較 RS，稍後再試。"


@pytest.fixture
def fc_clock(monkeypatch):
    """可手動推進的假 monotonic 時鐘 —— **只**換 `shared.fail_cooldown` 模組裡的 `time`。

    起點取真實 monotonic 的**整數秒**（萬一某個退避表沒清乾淨，殘留的時點也不會離真實時間太遠；
    取整數是為了讓「剛好滿冷卻期」的邊界比較不受浮點捨入影響）；所有用到的退避表都在各夾具收尾時清掉。"""
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


@pytest.fixture
def frozen_now(monkeypatch):
    """`fetched_at` 取 `pd.Timestamp.now("UTC")` —— 凍結後才能與修前的期望值逐字比。"""
    fixed = pd.Timestamp("2026-09-28T01:02:03.456789", tz="UTC")
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: fixed))
    return fixed


def _closes(total_ret: float, n: int = _N, seed: int = 0, noise: float = 0.012) -> np.ndarray:
    rng = np.random.RandomState(seed)
    drift = (1 + total_ret) ** (1 / (n - 1)) - 1
    rets = drift + rng.normal(0, noise, n)
    rets[0] = 0.0
    return 100 * np.cumprod(1 + rets)


def _idx(n: int = _N) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=n, freq="D")      # 固定日期，不吃執行當天


def _stock(total_ret: float, seed: int, n: int = _N) -> pd.DataFrame:
    return pd.DataFrame({"Close": _closes(total_ret, n, seed)}, index=_idx(n))


def _market(total_ret: float = -0.30, seed: int = 1, n: int = _N) -> pd.Series:
    return pd.Series(_closes(total_ret, n, seed), index=_idx(n), name="^TWII")


def _frozen_market(n: int = _N) -> pd.Series:
    """收盤恆定 ⇒ 日報酬 σ = 0 ⇒ RS 分母不成立（大盤側資料品質，不是抓取失敗）。"""
    return pd.Series([18_000.0] * n, index=_idx(n), name="^TWII")


def _ok_frame(ticker: str) -> pd.DataFrame:
    """某檔「上游正常」時的 1y K 線（依代號決定，可重算出同一份當期望值）。"""
    seed = sum(map(ord, ticker)) % 997
    return _stock(0.10 - (seed % 7) * 0.05, seed=seed)


def _assert_prefix_failure_frame(df) -> None:
    """修前 `cached_history` 的失敗回傳是 `return pd.DataFrame()` —— 逐字比（無旗標、無 attrs）。"""
    ref = pd.DataFrame()
    assert isinstance(df, pd.DataFrame)
    assert repr(df) == repr(ref)
    pd.testing.assert_frame_equal(df, ref)
    assert type(df.index) is type(ref.index) and df.attrs == {}


class _FakeYF:
    """`yfinance.Ticker` 替身：`mode` 為 raise／ok／empty／none；記下每一次 `history()` 的 (ticker, period)。"""

    def __init__(self):
        self.mode = "raise"
        self.calls: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def Ticker(self, ticker):  # noqa: N802 — 對齊 yfinance API
        outer = self

        class _T:
            def history(self, period="1mo", **_kw):
                with outer._lock:
                    outer.calls.append((ticker, period))
                if outer.mode == "raise":
                    raise YFRateLimitError()          # yfinance 1.x 對 429 一律往上拋
                if outer.mode == "empty":
                    return pd.DataFrame()             # 上游正常回應、只是沒有資料
                if outer.mode == "none":
                    return None
                return _ok_frame(ticker)
        return _T()


@pytest.fixture
def yfh(monkeypatch, fc_clock):
    import yfinance
    fake = _FakeYF()
    monkeypatch.setattr(yfinance, "Ticker", fake.Ticker)
    YP.cached_history.clear()
    yield fake
    YP.cached_history.clear()


# ══════════════════════════════════════════════════════════════════
# D2-f4 ① 拋例外：不入快取、冷卻期內不重打、期滿重打拿到新值
# ══════════════════════════════════════════════════════════════════
class TestD2f4HistoryFailureNotCached:
    def test_exception_backs_off_then_recovers(self, yfh, fc_clock, capsys):
        out = YP.cached_history("2330.TW", period="1y")
        _assert_prefix_failure_frame(out)
        assert yfh.calls == [("2330.TW", "1y")]
        assert ("[yf_proxy.history] 2330.TW: YFRateLimitError: "
                "Too Many Requests. Rate limited. Try after a while.") in capsys.readouterr().out, \
            "失敗 log 同修前"
        yfh.mode = "ok"                                   # 上游恢復，但仍在冷卻期內
        fc_clock["now"] += FAIL_COOLDOWN_SEC - 1
        for _ in range(3):
            _assert_prefix_failure_frame(YP.cached_history("2330.TW", period="1y"))
        assert len(yfh.calls) == 1, "冷卻期內 0 次上游呼叫"
        assert capsys.readouterr().out == "", "冷卻期內不重打，也就不再印失敗 log"
        fc_clock["now"] += 1                              # 剛好滿冷卻期（`<` 比較：滿即過期）
        pd.testing.assert_frame_equal(YP.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
        assert len(yfh.calls) == 2, "冷卻期過 → 重打並拿到新值（修前：空表凍 1 小時）"
        assert ("2330.TW", "1y") not in YP._history_fail_cooldown, "成功即解除退避"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC       # 退避時鐘怎麼走都碰不到 1 小時成功快取
        pd.testing.assert_frame_equal(YP.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
        assert len(yfh.calls) == 2, "成功照舊快取"

    def test_persistent_failure_hits_upstream_once_per_cooldown(self, yfh, fc_clock):
        for i in range(1, 4):
            for _ in range(4):
                _assert_prefix_failure_frame(YP.cached_history("2330.TW", period="1y"))
            assert len(yfh.calls) == i, "持續失敗：每個冷卻期只打 1 次（不入快取、也不轟炸）"
            fc_clock["now"] += FAIL_COOLDOWN_SEC

    def test_cooldown_is_per_ticker_and_period(self, yfh):
        YP.cached_history("2330.TW", period="1y")
        yfh.mode = "ok"
        pd.testing.assert_frame_equal(YP.cached_history("2330.TW", period="5d"), _ok_frame("2330.TW"))
        pd.testing.assert_frame_equal(YP.cached_history("2317.TW", period="1y"), _ok_frame("2317.TW"))
        _assert_prefix_failure_frame(YP.cached_history("2330.TW", period="1y"))
        assert yfh.calls == [("2330.TW", "1y"), ("2330.TW", "5d"), ("2317.TW", "1y")], \
            "退避鍵＝(ticker, period)，與快取鍵同義；別的檔／別的區間照常抓"

    def test_late_failure_does_not_override_peer_success(self, yfh, monkeypatch):
        """競態：本次抓取期間另一個 session 已成功 → 本次較晚的失敗不得寫進退避表。"""
        def _raise_after_peer_success(ticker, period="1y"):
            YP._history_fail_cooldown.success((ticker, period))
            raise ConnectionError("late failure")
        monkeypatch.setattr(YP, "_cached_history_cached", _raise_after_peer_success)
        _assert_prefix_failure_frame(YP.cached_history("7777.TW", period="1y"))
        assert ("7777.TW", "1y") not in YP._history_fail_cooldown

    def test_success_bumps_generation(self, yfh):
        """別的 session 已開抓（記下世代）→ 本次成功 → 那次較晚寫入的失敗不得進退避表
        （`cached_history` 成功時必須呼叫 `success()` 推進世代，否則下一位拿到假失敗）。"""
        _, g = YP._history_fail_cooldown.begin(("8888.TW", "1y"))
        yfh.mode = "ok"
        pd.testing.assert_frame_equal(YP.cached_history("8888.TW", period="1y"), _ok_frame("8888.TW"))
        YP._history_fail_cooldown.fail(("8888.TW", "1y"), g, pd.DataFrame())   # 同儕晚到的失敗
        assert ("8888.TW", "1y") not in YP._history_fail_cooldown
        pd.testing.assert_frame_equal(YP.cached_history("8888.TW", period="1y"), _ok_frame("8888.TW"))


# ══════════════════════════════════════════════════════════════════
# D2-f4 ② 成功與「真的沒資料」照舊快取；公開介面不變
# ══════════════════════════════════════════════════════════════════
class TestD2f4SuccessAndEmptyUnchanged:
    def test_success_identical_and_cached(self, yfh):
        yfh.mode = "ok"
        pd.testing.assert_frame_equal(YP.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
        pd.testing.assert_frame_equal(YP.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
        assert yfh.calls == [("2330.TW", "1y")], "TTL 內第二次命中快取"
        tree = ast.parse(pathlib.Path(YP.__file__).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        assert [ast.unparse(d) for d in fns["_cached_history_cached"].decorator_list] == \
            ["st.cache_data(ttl=TTL_1HOUR, max_entries=200, show_spinner=False)"], \
            "快取層參數同修前（修前掛在 cached_history 上的那一行逐字搬下來）"
        assert fns["cached_history"].decorator_list == [], "外層不快取 —— 失敗才不會被凍住"

    @pytest.mark.parametrize("mode", ["empty", "none"])
    def test_genuinely_empty_still_cached(self, yfh, fc_clock, mode):
        yfh.mode = mode
        _assert_prefix_failure_frame(YP.cached_history("9999.TW", period="1y"))
        yfh.mode = "ok"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        _assert_prefix_failure_frame(YP.cached_history("9999.TW", period="1y"))
        assert yfh.calls == [("9999.TW", "1y")], "沒拋、只回空＝照舊快取（TTL 內不重打）"
        assert ("9999.TW", "1y") not in YP._history_fail_cooldown, "不是失敗，不記退避"

    def test_clear_resets_cache_and_backoff(self, yfh):
        YP.cached_history("2330.TW", period="1y")         # 失敗 → 退避中
        yfh.mode = "ok"
        YP.cached_history.clear()
        pd.testing.assert_frame_equal(YP.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
        assert len(yfh.calls) == 2, "clear() 清掉退避紀錄 → 立刻重打"
        YP.cached_history.clear()
        YP.cached_history("2330.TW", period="1y")
        assert len(yfh.calls) == 3, "clear() 清掉成功快取 → 重打"
        assert PX.cached_history is YP.cached_history, "套件層轉發（caller 的 import 路徑）拿到同一支"
        assert callable(PX.cached_history.clear)


# ══════════════════════════════════════════════════════════════════
# D2-f4 ③ 經 v1 選股網／RS 共用的 L1 `fetch_stock_history_1y`（真的 L1）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def finmind_down(monkeypatch):
    """FinMind 備援（`fetch_stock_history_1y` 的第二來源）也失敗：記呼叫數、回空表。"""
    fm = {"n": 0}
    lock = threading.Lock()

    def _fm(*_a, **_k):
        with lock:
            fm["n"] += 1
        return pd.DataFrame()
    monkeypatch.setattr(DL, "_fetch_finmind_price_raw", _fm)
    return fm


class TestD2f4ThroughPickerFetcher:
    def test_fetch_stock_history_1y_recovers_after_cooldown(self, yfh, fc_clock, finmind_down):
        from src.data.stock.picker_fetcher import fetch_stock_history_1y
        assert fetch_stock_history_1y("2330") == (None, None)
        assert yfh.calls == [("2330.TW", "1y"), ("2330.TWO", "1y")]
        yfh.mode = "ok"
        assert fetch_stock_history_1y("2330") == (None, None), "冷卻期內照舊回失敗"
        assert len(yfh.calls) == 2, "冷卻期內 Yahoo 0 次"
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        df, resolved = fetch_stock_history_1y("2330")
        assert resolved == "2330.TW"
        pd.testing.assert_frame_equal(df, _ok_frame("2330.TW"))
        assert len(yfh.calls) == 3, "冷卻期過 → 重打 .TW 即拿到新值（修前：1 小時內一直 (None, None)）"


# ══════════════════════════════════════════════════════════════════
# D2-f7 共用：換掉 RS 的上游
# ══════════════════════════════════════════════════════════════════
def _prices(**spec) -> dict:
    return {sid: _stock(ret, seed=seed) for sid, (ret, seed) in spec.items()}


_RECOVERED = _prices(X=(+0.10, 11), Y=(-0.05, 12), Z=(-0.55, 13))


def _install_rs_world(mod, monkeypatch, plan: dict, calls: dict) -> None:
    assert callable(getattr(mod._scan_body, "clear", None)), \
        "前提：_scan_body 是真的 st.cache_data（否則驗不到「照舊快取」）"
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
        return (None, None) if df is None else (df.copy(), f"{sid}.TW")    # L1 失敗契約：(None, None)

    monkeypatch.setattr(mod, "fetch_yf_close", _yf)
    monkeypatch.setattr(mod, "_survivor_pool", _pool)
    monkeypatch.setattr(mod, "fetch_stock_history_1y", _price)
    monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
    mod._scan_cached.clear()


@pytest.fixture
def rs(monkeypatch, fc_clock):
    """預設世界：大盤正常、存活池 X/Y/Z **每一檔都抓不到 K 線**（③d 個股全失敗）。"""
    plan = {"market": _market(), "pool": ["X", "Y", "Z"], "prices": {}}
    calls = {"market": 0, "pool": 0, "price": 0}
    _install_rs_world(RS, monkeypatch, plan, calls)
    yield plan, calls
    RS._scan_cached.clear()


def _d3d_note(n: int, *, beat_only: bool = False) -> str:
    """修前 `_empty_scan_note` 對「大盤正常、n 檔全部完全抓不到 K 線」寫的字（逐字抄寫）。"""
    note = (f"⚠️ 掃描 {n} 檔後無可排名標的,{n} 檔全部判「資料不足」:"
            f"其中 {n} 檔完全抓不到 K 線(yfinance 回空)、"
            f"0 檔有 K 線但與大盤對齊後的共同交易日 < {max(_LB, RS_MIN_ALIGNED_ROWS)} 日"
            f"(歷史太短 / 欄位不符 / 日期對不上)。"
            f"大盤基準 ^TWII 本身正常(σ 可用),因此這是個股側的資料問題。")
    if beat_only:
        note += ("(已勾選「只留贏過大盤」,但本次沒有任何一檔被成功量測,"
                 "因此**無法**判斷有沒有人贏過大盤 —— 這不等於「全數落後」。)")
    return note


# ══════════════════════════════════════════════════════════════════
# D2-f7 ① ③d 個股全失敗：不入快取、掃描層退避、恢復後下一次即拿到新排行
# ══════════════════════════════════════════════════════════════════
class TestD2f7AllPricesMissingNotCached:
    def test_backoff_then_next_call_after_cooldown_gets_new_ranking(self, rs, fc_clock):
        plan, calls = rs
        rows, meta = RS.run_rs_leader_scan(lookback=_LB)
        assert rows == [] and meta["note"] == _d3d_note(3)
        assert calls == {"market": 1, "pool": 1, "price": 3}
        plan["prices"] = dict(_RECOVERED)                 # 個股恢復，但仍在冷卻期內
        fc_clock["now"] += FAIL_COOLDOWN_SEC - 1
        for _ in range(3):
            assert RS.run_rs_leader_scan(lookback=_LB) == (rows, meta)
        assert calls == {"market": 1, "pool": 1, "price": 3}, "冷卻期內 0 次上游呼叫（不重掃）"
        fc_clock["now"] += 1
        rows2, meta2 = RS.run_rs_leader_scan(lookback=_LB)
        assert len(rows2) == 3 and meta2["note"] == "" and meta2["scored"] == 3, \
            "冷卻期過的下一次即拿到新排行（修前：失敗排行凍 1 小時）"
        # 新排行＝以 L2 直呼（修前成功分支的組法）獨立算出的那一份
        stocks = [{"stock_id": s, "name": "", "df": _RECOVERED[s]} for s in ("X", "Y", "Z")]
        assert rows2 == to_rows(rank_rs_leaders(stocks, _market().rename("close").to_frame(),
                                                lookback=_LB, top_n=RS_LEADER_TOP_N, beat_only=False))
        assert calls == {"market": 2, "pool": 2, "price": 6}
        assert len(RS._scan_fail_cooldown) == 0, "成功即解除退避"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        assert RS.run_rs_leader_scan(lookback=_LB) == (rows2, meta2)
        assert calls == {"market": 2, "pool": 2, "price": 6}, "恢復後的成功照舊入快取"

    def test_persistent_failure_rescans_with_doubling_cooldown(self, rs, fc_clock):
        """持續失敗：每個冷卻期期滿重掃 1 次（證明不在 1 小時快取裡），且冷卻每次加倍到 1 小時封頂
        （QA N1；原「固定 180 秒」版本的斷言因規格改為遞增退避而改寫）。"""
        plan, calls = rs
        for i in range(1, 8):
            window = min(FAIL_COOLDOWN_SEC * 2 ** (i - 1), TTL_1HOUR)
            rows, meta = RS.run_rs_leader_scan(lookback=_LB)
            assert rows == [] and meta["note"] == _d3d_note(3)
            assert calls == {"market": i, "pool": i, "price": 3 * i}, f"第 {i} 次失敗才重掃第 {i} 次"
            fc_clock["now"] += window - 1
            RS.run_rs_leader_scan(lookback=_LB)
            assert calls["pool"] == i, f"第 {i} 次失敗後的冷卻（{window:.0f} 秒）期內不重掃"
            fc_clock["now"] += 1

    @pytest.mark.parametrize("kwargs", [
        {"beat_only": False, "top_n": RS_SCAN_MAX},                   # app.py／page_find／get_ranked_picks
        {"beat_only": True, "name_map": {"X": "甲"}},
    ], ids=["callers", "beat_only_name_map"])
    def test_output_identical_to_prefix(self, rs, frozen_now, kwargs):
        rows, meta = RS.run_rs_leader_scan(lookback=_LB, **kwargs)
        dfm = _market().rename("close").to_frame()
        ret = float(market_interval_return(dfm, _LB))
        assert ret < -0.5, "前提：合成大盤為下跌情境"
        want = {
            "lookback": _LB, "top_n": kwargs.get("top_n", RS_LEADER_TOP_N),
            "source": "FundamentalsSnapshot(survivors)+yfinance:1y+Yahoo:^TWII",
            "fetched_at": frozen_now.isoformat(), "version": RS_LEADER_VERSION,
            "candidates": 3, "scanned": 3, "scored": 0,
            "pool_source": "基本面存活池（免費離線快照）",
            "market": {"market_ret_pct": ret, "is_down": True,
                       "banner": (f"📉 此期間大盤（^TWII）約 {ret:+.2f}% — 屬下跌情境；"
                                  f"以下為「跌勢中仍相對抗跌 / 逆勢贏過大盤」的個股。")},
            "note": _d3d_note(3, beat_only=kwargs.get("beat_only", False)),
            "coverage_note": _COVERAGE,
        }
        assert rows == [] and meta == want
        assert list(meta) == list(want), "鍵的順序也同修前"
        assert repr((rows, meta)) == repr(([], want))
        again = RS.run_rs_leader_scan(lookback=_LB, **kwargs)
        assert again == ([], want), "冷卻期內回的是同一份（fetched_at 仍是當次抓取時點）"

    def test_backoff_is_per_scan_args(self, rs):
        plan, calls = rs
        RS.run_rs_leader_scan(lookback=_LB)              # ③d → 這一組參數進退避
        plan["prices"] = dict(_RECOVERED)
        rows, meta = RS.run_rs_leader_scan(lookback=60)
        assert len(rows) == 3 and meta["note"] == "" and calls["pool"] == 2, \
            "退避鍵＝掃描參數（與快取鍵同義）：別組參數照常掃"

    def test_scan_success_bumps_generation(self, rs):
        """同 D2-f4 的世代防護：同儕開抓後本次成功 → 同儕較晚寫入的失敗不得進掃描層退避表。"""
        plan, _calls = rs
        plan["prices"] = dict(_RECOVERED)
        key = (_LB, RS_SCAN_MAX, False, RS_LEADER_TOP_N)   # run_rs_leader_scan 預設參數正規化後的鍵
        _, g = RS._scan_fail_cooldown.begin(key)
        assert len(RS.run_rs_leader_scan(lookback=_LB)[0]) == 3
        RS._scan_fail_cooldown.fail(key, g, ([], {"note": "同儕晚到的失敗"}))
        assert key not in RS._scan_fail_cooldown
        assert len(RS.run_rs_leader_scan(lookback=_LB)[0]) == 3

    def test_backoff_returns_a_copy(self, rs):
        rows, meta = RS.run_rs_leader_scan(lookback=_LB)
        rows.append({"代碼": "污染"})
        meta["market"]["banner"] = "污染"
        rows2, meta2 = RS.run_rs_leader_scan(lookback=_LB)
        assert rows2 == [] and meta2["market"]["banner"] != "污染", "呼叫端改回傳值不得污染退避紀錄"

    def test_parallel_calls_during_failure(self, rs):
        plan, calls = rs
        n_threads = 6
        barrier = threading.Barrier(n_threads)
        results, errors = [], []

        def _worker():
            try:
                barrier.wait(timeout=5)
                results.append(RS.run_rs_leader_scan(lookback=_LB))
            except Exception as e:  # noqa: BLE001 — 收集起來讓斷言報出來
                errors.append(e)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not any(t.is_alive() for t in threads), "不得死鎖"
        assert errors == [] and len(results) == n_threads
        assert all(r == [] and m["note"] == _d3d_note(3) for r, m in results)
        assert 1 <= calls["pool"] <= n_threads
        n = calls["pool"]
        RS.run_rs_leader_scan(lookback=_LB)
        assert calls["pool"] == n, "並行失敗之後：冷卻期內不再重掃"


# ══════════════════════════════════════════════════════════════════
# D2-f7 ② 其餘結果照舊快取（「真的沒資料」／非本判準的空排行／正常排行）
# ══════════════════════════════════════════════════════════════════
_STILL_CACHED = {
    # ③d 混合：一檔抓不到、一檔有 K 線但太短 —— 上游有回應，分不出抓不到那檔是失敗還是真的沒有，不猜
    "mixed_missing_and_short": {"pool": ["X", "S"], "prices": {"S": _stock(+0.10, seed=41, n=10)},
                                "market": _market, "kwargs": {}, "note_has": "1 檔完全抓不到 K 線"},
    # ③d 每一檔都有 K 線、只是太短 —— 真的沒資料（夠長的），重抓不會變
    "all_short_history": {"pool": ["S", "T"], "prices": {"S": _stock(+0.10, seed=41, n=10),
                                                         "T": _stock(-0.10, seed=42, n=8)},
                          "market": _market, "kwargs": {}, "note_has": "0 檔完全抓不到 K 線"},
    # ③c 大盤凍結 ＋ 個股全抓不到 —— 歸因在大盤側（不在 D2-f7 判準內）
    "frozen_market_all_missing": {"pool": ["X", "Y"], "prices": {}, "market": _frozen_market,
                                  "kwargs": {}, "note_has": "問題指向大盤側"},
    # ② 存活池為空（本機季快照，不觸網）
    "survivor_pool_empty": {"pool": [], "prices": {}, "market": _market, "kwargs": {},
                            "note_has": "存活池為空"},
    # ③a 有量測成功、勾「只留贏過大盤」後 0 檔 —— 正當的空排行
    "beat_only_zero_winners": {"pool": ["Z"], "prices": {"Z": _stock(-0.55, seed=13)},
                               "market": lambda: _market(+0.20), "kwargs": {"beat_only": True},
                               "note_has": "0 檔"},
    # ④ 部分個股缺價的正常排行（範圍外：D2-f7 只管空排行）
    "partial_missing": {"pool": ["X", "A"], "prices": {"A": _stock(+0.10, seed=11)},
                        "market": _market, "kwargs": {}, "note_has": None},
}


class TestD2f7OtherResultsStillCached:
    @pytest.mark.parametrize("case", sorted(_STILL_CACHED))
    def test_cached_even_after_cooldown_window(self, rs, fc_clock, case):
        plan, calls = rs
        spec = _STILL_CACHED[case]
        plan["pool"], plan["prices"], plan["market"] = spec["pool"], dict(spec["prices"]), spec["market"]()
        first = RS.run_rs_leader_scan(lookback=_LB, **spec["kwargs"])
        rows, meta = first
        if spec["note_has"] is None:
            assert rows and meta["note"] == ""
        else:
            assert rows == [] and spec["note_has"] in meta["note"], meta["note"]
        assert len(RS._scan_fail_cooldown) == 0, "不是 D2-f7 的失敗，不記退避"
        before = dict(calls)
        plan["prices"] = dict(_RECOVERED)                 # 就算上游此刻變了……
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC       # ……且遠超過冷卻期
        assert RS.run_rs_leader_scan(lookback=_LB, **spec["kwargs"]) == first
        assert calls == before, "照舊入 1 小時快取（不是退避）：第二次上游呼叫數不變"


# ══════════════════════════════════════════════════════════════════
# D2-f1 路徑不變（大盤抓取失敗：本層不記退避，交給 L1）
# ══════════════════════════════════════════════════════════════════
class TestD2f1PathUnchanged:
    def test_market_failure_recomputed_each_call_and_not_in_scan_backoff(self, rs):
        plan, calls = rs
        plan["market"] = None
        for i in range(1, 4):
            rows, meta = RS.run_rs_leader_scan(lookback=_LB)
            assert rows == [] and meta["note"] == _FAIL_NOTE
            assert calls == {"market": i, "pool": 0, "price": 0}
        assert len(RS._scan_fail_cooldown) == 0

    def test_subclass_relation(self):
        assert issubclass(RS._PoolPricesFetchFailed, RS._UpstreamFetchFailed), \
            "同型例外：萬一漏出 _scan_cached，run_rs_leader_scan 的 D2-f1 接點仍接得住"


# ══════════════════════════════════════════════════════════════════
# D2-f9 refresh=True：刪兩行空操作，行為不變
# ══════════════════════════════════════════════════════════════════
_REFRESH_NOW = "    if refresh:\n        _clear(_scan_cached)\n"
_REFRESH_PREFIX = ("    if refresh:\n        _clear(fetch_yf_close)\n"
                   "        _clear(fetch_stock_history_1y)\n        _clear(_scan_cached)\n")


class TestD2f9RefreshUnchanged:
    """D2-f9（死碼登記見交接本〔開發線〕的 `DEAD_CODE.md` D-015；main 上沒有該檔）。既有 `tests/test_d3_backoff_d2f1_d2f2.py` 的
    `[refresh]` 參數化案例（refresh=True、大盤失敗路徑）在刪行前後都通過 —— 它的 `_install_world`
    也把兩支 L1 換成沒有 `.clear` 的純函式，那兩行在該測試裡同樣是空操作，斷言不依賴它們。"""

    def test_premise_l1_functions_have_no_clear(self):
        from src.data.macro import fetch_yf_close
        from src.data.stock.picker_fetcher import fetch_stock_history_1y
        assert RS.fetch_yf_close is fetch_yf_close
        assert RS.fetch_stock_history_1y is fetch_stock_history_1y
        assert not callable(getattr(fetch_yf_close, "clear", None)), \
            "前提：修前 `_clear(fetch_yf_close)` 是空操作（若日後這支加了 .clear，須重新決定 refresh 要不要清它）"
        assert not callable(getattr(fetch_stock_history_1y, "clear", None)), \
            "前提：修前 `_clear(fetch_stock_history_1y)` 是空操作"

    def test_dead_lines_removed_and_docstring_truthful(self):
        src = pathlib.Path(RS.__file__).read_text(encoding="utf-8")
        assert "_clear(fetch_yf_close)" not in src and "_clear(fetch_stock_history_1y)" not in src
        assert src.count(_REFRESH_NOW) == 1
        assert "清 L1 大盤/個股 cache" not in RS.run_rs_leader_scan.__doc__

    @pytest.mark.parametrize("scenario", ["all_missing", "success", "market_fail"])
    def test_refresh_identical_to_prefix_lines(self, monkeypatch, fc_clock, frozen_now, scenario):
        """對照組＝把修前那兩行放回去的同一份模組；同一個世界、同一串呼叫 → 回傳與上游呼叫數逐項相同。"""
        prefix = _mutant(RS, (_REFRESH_NOW, _REFRESH_PREFIX), tag="refresh_prefix")
        worlds = {
            "all_missing": {"market": _market(), "prices": {}},
            "success": {"market": _market(), "prices": dict(_RECOVERED)},
            "market_fail": {"market": None, "prices": dict(_RECOVERED)},
        }
        out = {}
        for label, mod in (("now", RS), ("prefix", prefix)):
            plan = {"pool": ["X", "Y", "Z"], **worlds[scenario]}
            calls = {"market": 0, "pool": 0, "price": 0}
            _install_rs_world(mod, monkeypatch, plan, calls)
            try:
                seq = [mod.run_rs_leader_scan(lookback=_LB),
                       mod.run_rs_leader_scan(lookback=_LB, refresh=True),
                       mod.run_rs_leader_scan(lookback=_LB)]
                out[label] = (seq, dict(calls))
            finally:
                mod._scan_cached.clear()
        assert out["now"] == out["prefix"]
        assert repr(out["now"][0]) == repr(out["prefix"][0])

    def test_refresh_during_backoff_rescans(self, rs):
        """修前：refresh 清掉被快取的失敗排行並重掃；現在失敗在退避裡 —— refresh 同樣清掉並重掃。"""
        plan, calls = rs
        RS.run_rs_leader_scan(lookback=_LB)
        plan["prices"] = dict(_RECOVERED)
        rows, meta = RS.run_rs_leader_scan(lookback=_LB, refresh=True)
        assert len(rows) == 3 and meta["note"] == ""
        assert calls == {"market": 2, "pool": 2, "price": 6}

    def test_clear_resets_both_layers(self, rs):
        plan, calls = rs
        RS.run_rs_leader_scan(lookback=_LB)
        RS._scan_cached.clear()
        RS.run_rs_leader_scan(lookback=_LB)
        assert calls["pool"] == 2, "_scan_cached.clear() 清掉退避紀錄"
        plan["prices"] = dict(_RECOVERED)
        RS._scan_cached.clear()
        RS.run_rs_leader_scan(lookback=_LB)
        RS._scan_cached.clear()
        RS.run_rs_leader_scan(lookback=_LB)
        assert calls["pool"] == 4, "_scan_cached.clear() 清掉成功快取"


# ══════════════════════════════════════════════════════════════════
# QA N1 ① `FailCooldown(max_seconds=None)`（預設）與新增前**逐字相同** —— 以原始實作當參考模型逐步比對
# ══════════════════════════════════════════════════════════════════
#: 新增 `max_seconds` 之前的 `shared/fail_cooldown.py`（origin/main `3f001cd`）實作，逐字抄錄（含註解）當參考模型。
_FC_BEFORE_SRC = '''
import copy
import threading
import time

#: 失敗後冷卻秒數（見檔頭）。
FAIL_COOLDOWN_SEC: float = 180.0

#: 失敗紀錄的鍵數上限（長時間斷線時不無限成長；`_combined_inst_fail_cooldown` 每鍵存一整張 df）。
#: 取 64 ＝ 原 `StockDataLoader.get_combined_data` 快取的 `max_entries`。超過時逐出最舊的紀錄。
FAIL_COOLDOWN_MAX_ENTRIES: int = 64

#: 成功世代計數表的鍵數上限（每鍵只存一個 int；超過時逐出最早插入者）。
_GEN_MAX_ENTRIES: int = 4096

_NO_HIT = object()


class FailCooldown:
    """每個鍵：最近一次失敗的時點與回傳值；成功世代計數防競態。

    競態：A 抓取失敗、B 同時成功並清掉紀錄,之後 A 才寫入失敗 → 下一位在 B 的成功
    已快取的情況下拿到假失敗。A 抓之前記下世代（`begin`）,寫失敗時世代已變就不寫。
    """

    def __init__(self, seconds: float = FAIL_COOLDOWN_SEC,
                 max_entries: int = FAIL_COOLDOWN_MAX_ENTRIES):
        self.seconds = float(seconds)
        self.max_entries = int(max_entries)
        self._fail: dict = {}
        self._gen: dict = {}
        self._lock = threading.Lock()

    def _prune_locked(self, now: float) -> None:
        """（持鎖呼叫）清掉已過冷卻期的紀錄；仍超過上限則逐出最舊者。"""
        for k in [k for k, v in self._fail.items() if now - v[0] >= self.seconds]:
            del self._fail[k]
        while len(self._fail) > self.max_entries:
            oldest = min(self._fail, key=lambda k: self._fail[k][0])
            del self._fail[oldest]
        while len(self._gen) > _GEN_MAX_ENTRIES:
            del self._gen[next(iter(self._gen))]

    def begin(self, key):
        """回 (冷卻中的失敗結果或 `NO_HIT`, 世代)。"""
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now)
            prev = self._fail.get(key)
            gen = self._gen.get(key, 0)
        if prev is not None and now - prev[0] < self.seconds:
            return copy.deepcopy(prev[1]), gen
        return _NO_HIT, gen

    def fail(self, key, gen, payload):
        """記下失敗（期間沒有人成功過才記）；回傳 payload 的複本給呼叫端。"""
        with self._lock:
            if self._gen.get(key, 0) == gen:
                _now = time.monotonic()
                self._fail[key] = (_now, copy.deepcopy(payload))
                self._prune_locked(_now)
        return payload

    def success(self, key):
        with self._lock:
            self._gen[key] = self._gen.get(key, 0) + 1
            self._fail.pop(key, None)
            self._prune_locked(time.monotonic())

    def clear(self):
        with self._lock:
            self._fail.clear()
            self._gen.clear()

    def __len__(self):
        with self._lock:
            return len(self._fail)

    def __contains__(self, key):
        with self._lock:
            return key in self._fail
'''


def _fc_pair(monkeypatch, **kwargs):
    """(新實作, 新增前的參考實作, 參考實作的 NO_HIT, 共用假時鐘)。兩邊吃同一個 monotonic。"""
    clock = {"now": 10_000.0}
    fake = types.SimpleNamespace(monotonic=lambda: clock["now"])
    monkeypatch.setattr(FC, "time", fake)
    ns: dict = {"__name__": "_fail_cooldown_before_max_seconds"}
    exec(compile(_FC_BEFORE_SRC, "<shared/fail_cooldown.py@3f001cd>", "exec"), ns)
    ns["time"] = fake
    return FC.FailCooldown(**kwargs), ns["FailCooldown"](**kwargs), ns["_NO_HIT"], clock


class TestFailCooldownDefaultUnchanged:
    @pytest.mark.parametrize("seed", range(6))
    @pytest.mark.parametrize("kwargs", [{}, {"seconds": 30.0, "max_entries": 3}], ids=["defaults", "small"])
    def test_random_ops_match_pre_change_model(self, monkeypatch, kwargs, seed):
        """隨機操作序列（固定 seed）：begin／fail（含舊世代＝晚到的並行失敗）／success／clear／
        推時鐘／把 seconds 設 0 再改回（既有測試手法）。每一步的回傳與內部狀態都必須與參考模型相同。"""
        new, old, old_no_hit, clock = _fc_pair(monkeypatch, **kwargs)
        rng = random.Random(seed)
        keys = ["a", "b", ("2330.TW", "1y"), ("2330.TW", "5d"), 7, (60, RS_SCAN_MAX, False, RS_SCAN_MAX)]
        gens: dict = {}
        for step in range(600):
            op = rng.choices(["tick", "begin", "fail", "success", "clear", "seconds"],
                             weights=[5, 6, 5, 2, 0.3, 0.6])[0]
            k = rng.choice(keys)
            if op == "tick":
                clock["now"] += rng.choice([0, 1, 29, 30, 31, 90, 179, 180, 181, 400, 3600])
            elif op == "begin":
                (hn, gn), (ho, go) = new.begin(k), old.begin(k)
                assert gn == go and (hn is FC.NO_HIT) == (ho is old_no_hit)
                if hn is not FC.NO_HIT:
                    assert hn == ho
                gens.setdefault(k, []).append(gn)
            elif op == "fail":
                g = rng.choice(gens.get(k) or [0])
                payload = {"k": repr(k), "step": step, "rows": [step]}
                assert new.fail(k, g, dict(payload)) == old.fail(k, g, dict(payload))
            elif op == "success":
                new.success(k)
                old.success(k)
            elif op == "clear":
                new.clear()
                old.clear()
            else:
                new.seconds = old.seconds = rng.choice([0.0, float(kwargs.get("seconds", FAIL_COOLDOWN_SEC))])
            assert len(new) == len(old)
            assert new._fail == old._fail and new._gen == old._gen, f"第 {step} 步（{op}）內部狀態分岔"
            assert all((kk in new) == (kk in old) for kk in keys)
            assert new._streak == {}, "預設關閉：遞增退避的狀態永不寫入"

    def test_generation_table_eviction_matches(self, monkeypatch):
        new, old, _no_hit, _clock = _fc_pair(monkeypatch)
        for i in range(FC._GEN_MAX_ENTRIES + 50):
            new.success(i)
            old.success(i)
        assert new._gen == old._gen and len(new._gen) == FC._GEN_MAX_ENTRIES

    def test_signature_backward_compatible_and_existing_users_do_not_opt_in(self):
        import inspect

        import src.data.etf.etf_fetch as F
        import src.data.stock.app_stock_fetchers as A
        params = inspect.signature(FC.FailCooldown).parameters
        assert list(params) == ["seconds", "max_entries", "max_seconds"], "既有的位置參數順序不變"
        assert params["max_seconds"].default is None
        for name, inst in {"yf_proxy._dividends_fail_cooldown": YP._dividends_fail_cooldown,
                           "yf_proxy._history_fail_cooldown": YP._history_fail_cooldown,
                           "etf_fetch._price_fail_cooldown": F._price_fail_cooldown,
                           "data_loader._combined_inst_fail_cooldown": DL._combined_inst_fail_cooldown,
                           "app_stock_fetchers._dividend_fail_cooldown": A._dividend_fail_cooldown}.items():
            assert inst.max_seconds is None and inst.seconds == FAIL_COOLDOWN_SEC, f"{name} 不得開遞增退避"
        assert RS._scan_fail_cooldown.max_seconds == TTL_1HOUR, "只有 RS 掃描層開（上限＝成功快取 TTL）"
        assert RS._scan_fail_cooldown.seconds == FAIL_COOLDOWN_SEC


# ══════════════════════════════════════════════════════════════════
# QA N1 ② `FailCooldown(max_seconds=...)` 遞增退避本身
# ══════════════════════════════════════════════════════════════════
def _fail_once(c, key, payload="x"):
    _hit, g = c.begin(key)
    assert _hit is FC.NO_HIT, "前提：此刻不在冷卻期"
    c.fail(key, g, payload)


class TestFailCooldownEscalation:
    def test_doubles_from_base_up_to_cap(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        windows = [min(FAIL_COOLDOWN_SEC * 2 ** i, TTL_1HOUR) for i in range(9)]
        assert windows[:6] == [180, 360, 720, 1440, 2880, 3600], "以現行常數即 QA 給的序列"
        for w in windows:
            _fail_once(c, "k", {"w": w})
            fc_clock["now"] += w - 1
            assert c.begin("k")[0] == {"w": w}, f"冷卻 {w:.0f} 秒：期滿前 1 秒仍在冷卻"
            fc_clock["now"] += 1
            assert c.begin("k")[0] is FC.NO_HIT, f"冷卻 {w:.0f} 秒：期滿即過期"
        assert c._streak["k"] == 6, "封頂後不再累加（不會無限成長）"

    def test_success_resets_to_base(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        _fail_once(c, "k")
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        _fail_once(c, "k")                                    # 第 2 次：冷卻 2×
        c.success("k")
        _fail_once(c, "k")
        fc_clock["now"] += FAIL_COOLDOWN_SEC - 1
        assert c.begin("k")[0] == "x"
        fc_clock["now"] += 1
        assert c.begin("k")[0] is FC.NO_HIT, "一次成功即歸零：下一次失敗又從 FAIL_COOLDOWN_SEC 起"

    def test_same_wave_failures_escalate_once(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        (h1, g1), (h2, g2) = c.begin("k"), c.begin("k")      # 兩個 session 同時錯過冷卻
        assert h1 is FC.NO_HIT and h2 is FC.NO_HIT
        c.fail("k", g1, "a")
        fc_clock["now"] += 30
        c.fail("k", g2, "b")                                 # 同一波晚 30 秒到的失敗
        fc_clock["now"] += FAIL_COOLDOWN_SEC - 1
        assert c.begin("k")[0] == "b", "晚到的失敗只更新時點"
        fc_clock["now"] += 1
        assert c.begin("k")[0] is FC.NO_HIT, "同一波只算一次：冷卻仍是基準值，不是加倍"

    def test_stale_generation_neither_records_nor_escalates(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        _fail_once(c, "k")
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        _h, g = c.begin("k")
        c.success("k")                                       # 期間有人成功
        c.fail("k", g, "late")
        assert "k" not in c and c._streak == {}

    def test_clear_resets_streak(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        for _ in range(3):
            _fail_once(c, "k")
            fc_clock["now"] += TTL_1HOUR
        c.clear()
        _fail_once(c, "k")
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        assert c.begin("k")[0] is FC.NO_HIT

    def test_escalation_is_per_key(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        for _ in range(3):
            _fail_once(c, "a")
            fc_clock["now"] += TTL_1HOUR
        _fail_once(c, "b")
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        assert c.begin("b")[0] is FC.NO_HIT, "別的鍵不受連坐"

    def test_seconds_zero_idiom_still_expires(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        for _ in range(4):
            _fail_once(c, "k")
            fc_clock["now"] += TTL_1HOUR
        _fail_once(c, "k")
        c.seconds = 0
        assert c.begin("k")[0] is FC.NO_HIT, "既有測試手法（seconds 設 0 讓紀錄立即過期）在遞增模式仍有效"


# ══════════════════════════════════════════════════════════════════
# QA N1 ③ 負載放大：Yahoo＋FinMind 持續全失敗、每 60 秒 rerun、1 小時
# ══════════════════════════════════════════════════════════════════
_QA_POOL = [str(1101 + i) for i in range(324)]      # QA 模擬的存活池規模（全規模重現，slow lane）
_FAST_POOL = _QA_POOL[:12]                           # fast lane 用：重掃「次數」與池子大小無關，呼叫數按檔數等比
_QA_STEP = 60                                        # QA：每 60 秒 rerun 一次
_QA_HORIZON = TTL_1HOUR                              # QA：持續 1 小時（含 t=3600 那一次，共 61 次呼叫）


def _expected_scan_times(base: float, cap: float) -> list[int]:
    """獨立參考模型：每次重掃都失敗 → 下次最早 t＋w，w 每次加倍到 cap（base＝cap 即固定冷卻）。"""
    times, next_at, w = [], 0, base
    for t in range(0, _QA_HORIZON + 1, _QA_STEP):
        if t >= next_at:
            times.append(t)
            next_at, w = t + w, min(w * 2, cap)
    return times


def _drive_qa_scenario(mod, calls: dict, fc_clock, pool: list[str]) -> list[int]:
    """照 QA 情境呼叫 `run_rs_leader_scan`；回傳真的重掃（`_survivor_pool` 被叫）的時點。"""
    scans_at, t0 = [], fc_clock["now"]
    for t in range(0, _QA_HORIZON + 1, _QA_STEP):
        fc_clock["now"] = t0 + t
        before = calls["pool"]
        rows, meta = mod.run_rs_leader_scan(lookback=_LB)
        assert rows == [] and meta["note"] == _d3d_note(len(pool))
        if calls["pool"] > before:
            scans_at.append(t)
    return scans_at


def _install_real_l1_scan(mod, monkeypatch, pool: list[str]) -> dict:
    """RS 走**真的** L1（`fetch_stock_history_1y` → `cached_history`），只換大盤／存活池／涵蓋率。"""
    calls = {"pool": 0}

    def _pool(max_n):
        calls["pool"] += 1
        return pool[:max_n]
    monkeypatch.setattr(mod, "fetch_yf_close", lambda tk, range_="2y": _market())
    monkeypatch.setattr(mod, "_survivor_pool", _pool)
    monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
    mod._scan_cached.clear()
    return calls


class TestQaN1LoadAmplification:
    def test_hour_of_reruns_every_60s_scans_single_digit_times(self, rs, fc_clock):
        plan, calls = rs
        plan["pool"] = list(_FAST_POOL)                       # prices 空 ＝ 每一檔都抓不到
        scans_at = _drive_qa_scenario(RS, calls, fc_clock, _FAST_POOL)
        assert scans_at == _expected_scan_times(FAIL_COOLDOWN_SEC, TTL_1HOUR) == [0, 180, 540, 1260, 2700]
        assert len(scans_at) <= 9, "1 小時內重掃次數落在個位數（固定 180 秒冷卻是 21 次，見 TestMutations M7）"
        n = len(scans_at)
        assert calls == {"market": n, "pool": n, "price": n * len(_FAST_POOL)}, \
            "逐檔抓價呼叫 ＝ 重掃次數 × 存活池檔數"

    def test_upstream_calls_over_real_l1(self, yfh, fc_clock, finmind_down, monkeypatch):
        """同一情境走真的 L1，數 Yahoo／FinMind 實際呼叫：每次重掃 ＝ 每檔（.TW ＋ .TWO ＋ FinMind）。
        全規模 324 檔的數字（含拿掉遞增的對照）見 slow lane 的 `TestQaN1FullScale`。"""
        calls = _install_real_l1_scan(RS, monkeypatch, _FAST_POOL)
        try:
            scans_at = _drive_qa_scenario(RS, calls, fc_clock, _FAST_POOL)
            n = len(scans_at)
            assert n == len(_expected_scan_times(FAIL_COOLDOWN_SEC, TTL_1HOUR)) == 5
            assert len(yfh.calls) == n * 2 * len(_FAST_POOL), "Yahoo：每次重掃每檔 .TW＋.TWO 各 1 次"
            assert finmind_down["n"] == n * len(_FAST_POOL), "FinMind：每次重掃每檔 1 次（本身沒有快取）"
        finally:
            RS._scan_cached.clear()

    def test_brief_outage_recovers_after_base_cooldown_and_success_resets(self, rs, fc_clock):
        plan, calls = rs
        RS.run_rs_leader_scan(lookback=_LB)                   # 失敗 1 次
        plan["prices"] = dict(_RECOVERED)                     # 隨即恢復
        fc_clock["now"] += FAIL_COOLDOWN_SEC - 1
        assert RS.run_rs_leader_scan(lookback=_LB)[0] == []
        fc_clock["now"] += 1
        rows, meta = RS.run_rs_leader_scan(lookback=_LB)
        assert len(rows) == 3 and meta["note"] == "", "短暫中斷：180 秒後即拿到新排行（不因遞增而變慢）"
        assert calls["pool"] == 2
        # 成功一次即歸零：成功結果的快取過期後（此處以 _scan_body.clear() 模擬）又壞 → 冷卻從基準值起
        RS._scan_body.clear()
        plan["prices"] = {}
        RS.run_rs_leader_scan(lookback=_LB)
        assert calls["pool"] == 3
        fc_clock["now"] += FAIL_COOLDOWN_SEC - 1
        RS.run_rs_leader_scan(lookback=_LB)
        assert calls["pool"] == 3
        fc_clock["now"] += 1
        RS.run_rs_leader_scan(lookback=_LB)
        assert calls["pool"] == 4, "成功歸零：之後的失敗冷卻又從 FAIL_COOLDOWN_SEC 起，不是接著加倍"


@pytest.mark.slow
class TestQaN1FullScale:
    """QA N1 全規模重現（324 檔、真的 L1；單測數十秒 → slow lane）：遞增退避 vs 拿掉遞增的對照。"""

    def test_qa_numbers_reproduced_before_and_after(self, yfh, fc_clock, finmind_down, monkeypatch):
        no_escalation = _mutant(RS, ("_scan_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)",
                                     "_scan_fail_cooldown = _FailCooldown()"), tag="fullscale_fixed")
        results = {}
        for label, mod in (("escalating", RS), ("fixed_180s", no_escalation)):
            YP.cached_history.clear()
            yfh.calls.clear()
            finmind_down["n"] = 0
            calls = _install_real_l1_scan(mod, monkeypatch, _QA_POOL)
            try:
                scans_at = _drive_qa_scenario(mod, calls, fc_clock, _QA_POOL)
                results[label] = (len(scans_at), len(yfh.calls), finmind_down["n"])
            finally:
                mod._scan_cached.clear()
            fc_clock["now"] += 10 * TTL_1HOUR              # 兩輪之間拉開，避免 L1 退避紀錄互相影響
        assert results["fixed_180s"] == (21, 13_608, 6_804), "QA 量到的固定冷卻版本（修後、本次修正前）"
        assert results["escalating"] == (5, 3_240, 1_620), "遞增退避：1 小時重掃 5 次"


# ══════════════════════════════════════════════════════════════════
# 端對端：真的 L1（cached_history ＋ fetch_stock_history_1y）＋ RS 掃描層 —— 失敗期間不轟炸、恢復即拿到
# ══════════════════════════════════════════════════════════════════
class TestEndToEndNoBombardment:
    def test_scan_over_real_l1(self, yfh, fc_clock, finmind_down, monkeypatch):
        pool = ["1101", "1102", "1103"]
        monkeypatch.setattr(RS, "fetch_yf_close", lambda tk, range_="2y": _market())
        monkeypatch.setattr(RS, "_survivor_pool", lambda max_n: pool[:max_n])
        monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
        RS._scan_cached.clear()
        try:
            for _ in range(5):
                rows, meta = RS.run_rs_leader_scan(lookback=_LB)
                assert rows == [] and meta["note"] == _d3d_note(3)
            assert len(yfh.calls) == 6 and finmind_down["n"] == 3, \
                "5 次呼叫只掃 1 次：Yahoo 6 次（.TW／.TWO）、FinMind 3 次"
            yfh.mode = "ok"
            fc_clock["now"] += FAIL_COOLDOWN_SEC
            rows, meta = RS.run_rs_leader_scan(lookback=_LB)
            assert len(rows) == 3 and meta["note"] == "", "冷卻期過 → 重掃即拿到新排行"
            assert len(yfh.calls) == 9 and finmind_down["n"] == 3
            for _ in range(3):
                RS.run_rs_leader_scan(lookback=_LB)
            assert len(yfh.calls) == 9, "恢復後照舊入快取"
        finally:
            RS._scan_cached.clear()


# ══════════════════════════════════════════════════════════════════
# 突變：把修復改回修前 → 本檔所擋的失效確實出現
# ══════════════════════════════════════════════════════════════════
_YP_CALL = ("    with _proxy_env():\n"
            "        _df = yf.Ticker(ticker).history(period=period)\n")
_YP_CALL_SWALLOW = ("    try:\n"
                    "        with _proxy_env():\n"
                    "            _df = yf.Ticker(ticker).history(period=period)\n"
                    "    except Exception:\n"
                    "        return pd.DataFrame()\n")


class TestMutations:
    def test_m1_history_failure_cached_again(self, yfh, fc_clock):
        """M1：快取層自己吞例外（修前結構）→ 失敗被凍住，恢復＋過冷卻期仍回空表。"""
        m = _mutant(YP, (_YP_CALL, _YP_CALL_SWALLOW), tag="m1")
        try:
            _assert_prefix_failure_frame(m.cached_history("2330.TW", period="1y"))
            yfh.mode = "ok"
            fc_clock["now"] += FAIL_COOLDOWN_SEC
            _assert_prefix_failure_frame(m.cached_history("2330.TW", period="1y"))
            assert len(yfh.calls) == 1, "修前：失敗被 st.cache_data 凍成 1 小時，上游恢復也看不到"
        finally:
            m.cached_history.clear()

    def test_m2_history_no_backoff(self, yfh):
        """M2：失敗不記退避 → 冷卻期內每呼叫一次就重打一次（轟炸）。"""
        m = _mutant(YP, ("return _history_fail_cooldown.fail(_key, _gen, pd.DataFrame())",
                         "return pd.DataFrame()"), tag="m2")
        try:
            for _ in range(3):
                m.cached_history("2330.TW", period="1y")
            assert len(yfh.calls) == 3, "沒有退避：3 次呼叫打 3 次上游"
        finally:
            m.cached_history.clear()

    def test_m3_scan_failure_cached_again(self, monkeypatch, fc_clock):
        """M3：③d 改回 return（修前）→ 失敗排行被凍住，個股恢復＋過冷卻期仍回失敗。"""
        m = _mutant(RS, ("raise _PoolPricesFetchFailed(_result)", "return _result"), tag="m3")
        plan = {"market": _market(), "pool": ["X", "Y", "Z"], "prices": {}}
        calls = {"market": 0, "pool": 0, "price": 0}
        _install_rs_world(m, monkeypatch, plan, calls)
        try:
            m.run_rs_leader_scan(lookback=_LB)
            plan["prices"] = dict(_RECOVERED)
            fc_clock["now"] += FAIL_COOLDOWN_SEC
            rows, meta = m.run_rs_leader_scan(lookback=_LB)
            assert rows == [] and meta["note"] == _d3d_note(3) and calls["pool"] == 1, \
                "修前：個股全失敗的排行被 st.cache_data 凍成 1 小時"
        finally:
            m._scan_cached.clear()

    def test_m4_scan_no_backoff(self, monkeypatch):
        """M4：不入快取但不記退避（「直接改成拋出」）→ 每次呼叫都重掃整個存活池。"""
        m = _mutant(RS, ("return _scan_fail_cooldown.fail(_key, _gen, _pf.payload)",
                         "return _pf.payload"), tag="m4")
        plan = {"market": _market(), "pool": ["X", "Y", "Z"], "prices": {}}
        calls = {"market": 0, "pool": 0, "price": 0}
        _install_rs_world(m, monkeypatch, plan, calls)
        try:
            for _ in range(3):
                m.run_rs_leader_scan(lookback=_LB)
            assert calls == {"market": 3, "pool": 3, "price": 9}, "沒有掃描層退避：3 次呼叫重掃 3 次"
        finally:
            m._scan_cached.clear()

    def test_m5_classification_too_broad(self, monkeypatch, fc_clock):
        """M5：判準放寬成「一檔都沒量到就算失敗」→ 「每一檔都太短」這種真的沒資料也被重掃。"""
        m = _mutant(RS, ("if not stocks or any(_has_price(s) for s in stocks):",
                         "if not stocks:"), tag="m5")
        spec = _STILL_CACHED["all_short_history"]
        plan = {"market": _market(), "pool": spec["pool"], "prices": dict(spec["prices"])}
        calls = {"market": 0, "pool": 0, "price": 0}
        _install_rs_world(m, monkeypatch, plan, calls)
        try:
            m.run_rs_leader_scan(lookback=_LB)
            fc_clock["now"] += FAIL_COOLDOWN_SEC
            m.run_rs_leader_scan(lookback=_LB)
            assert calls["pool"] == 2, "判準過寬：確定性的「資料太短」每個冷卻期被重掃一次"
        finally:
            m._scan_cached.clear()

    def test_m6_clear_keeps_backoff(self, monkeypatch):
        """M6：`_scan_cached.clear()` 沒清退避 → refresh=True 在冷卻期內不重掃（refresh 行為被改變）。"""
        m = _mutant(RS, ("    _scan_fail_cooldown.clear()\n", "    pass\n"), tag="m6")
        plan = {"market": _market(), "pool": ["X", "Y", "Z"], "prices": {}}
        calls = {"market": 0, "pool": 0, "price": 0}
        _install_rs_world(m, monkeypatch, plan, calls)
        try:
            m.run_rs_leader_scan(lookback=_LB)
            plan["prices"] = dict(_RECOVERED)
            rows, _meta = m.run_rs_leader_scan(lookback=_LB, refresh=True)
            assert rows == [] and calls["pool"] == 1, "refresh 被退避擋住（修前 refresh 一定重掃）"
        finally:
            m._scan_fail_cooldown.clear()
            m._scan_cached.clear()

    def test_m7_no_escalation_amplifies_load(self, monkeypatch, fc_clock):
        """M7（QA N1）：拿掉遞增、回到固定 FAIL_COOLDOWN_SEC → QA 情境 1 小時重掃 21 次（負載測試轉紅）。"""
        m = _mutant(RS, ("_scan_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)",
                         "_scan_fail_cooldown = _FailCooldown()"), tag="m7")
        plan = {"market": _market(), "pool": list(_FAST_POOL), "prices": {}}
        calls = {"market": 0, "pool": 0, "price": 0}
        _install_rs_world(m, monkeypatch, plan, calls)
        try:
            scans_at = _drive_qa_scenario(m, calls, fc_clock, _FAST_POOL)
            assert scans_at == _expected_scan_times(FAIL_COOLDOWN_SEC, FAIL_COOLDOWN_SEC)
            assert len(scans_at) == 21 and calls["price"] == 21 * len(_FAST_POOL), \
                "固定冷卻：1 小時重掃 21 次（全規模即 QA 量到的 13,608 次 Yahoo ／ 6,804 次 FinMind）"
        finally:
            m._scan_cached.clear()
