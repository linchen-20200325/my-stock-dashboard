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

    起點取真實 monotonic（萬一某個退避表沒清乾淨，殘留的時點也不會離真實時間太遠）；
    所有用到的退避表都在各夾具收尾時清掉。"""
    t = {"now": time.monotonic()}
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

    def test_persistent_failure_rescans_once_per_cooldown(self, rs, fc_clock):
        """持續失敗：每個冷卻期重掃 1 次 —— 證明不在 1 小時快取裡（在的話推過冷卻期也不會重掃）。"""
        plan, calls = rs
        for i in range(1, 4):
            for _ in range(3):
                rows, meta = RS.run_rs_leader_scan(lookback=_LB)
                assert rows == [] and meta["note"] == _d3d_note(3)
            assert calls == {"market": i, "pool": i, "price": 3 * i}
            fc_clock["now"] += FAIL_COOLDOWN_SEC

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
    """D2-f9（死碼登記 `DEAD_CODE.md` D-015）。既有 `tests/test_d3_backoff_d2f1_d2f2.py` 的
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
