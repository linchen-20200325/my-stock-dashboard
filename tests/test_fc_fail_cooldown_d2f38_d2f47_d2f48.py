# -*- coding: utf-8 -*-
"""批 FC（2026-10-01）：`shared/fail_cooldown.FailCooldown` 三條。

  · **D2-f38** 遞增退避的連續失敗次數**隨時間衰減**：冷卻結束後整整一個 `max_seconds` 都沒再失敗
    → 下一次失敗視為新的一串（冷卻回到 `seconds`）。修前升到上限後，隔天再失敗仍直接冷卻上限秒數。
  · **D2-f47** `_gen`／`_streak` 的鍵數上限跟著 `max_entries` 走（取 `max(max_entries, _GEN_MAX_ENTRIES)`，
    既有 `max_entries ≤ 4096` 的使用者逐字不變）。修前固定 4096 → 不設上限的單股月營收冷卻表
    超過 4096 個鍵後遞增退避失效。
  · **D2-f48** `_prune_locked` 不再每次存取都整表掃描（改以兩個延遲刪除的 heap 依到期／失敗時點排序）。

既有行為以「批 FC 前的原始實作」（`_FC_BEFORE_SRC`，origin/main `8a99564` 逐字）當參考模型逐步比對。
不觸網；假時鐘只換 `shared.fail_cooldown` 的 `time`。
"""
from __future__ import annotations

import random
import threading
import time
import types

import pytest

import shared.fail_cooldown as FC
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from shared.ttls import TTL_1HOUR


@pytest.fixture
def fc_clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


def _fail_once(c, key, payload="x"):
    _hit, g = c.begin(key)
    assert _hit is FC.NO_HIT, "前提：此刻不在冷卻期"
    c.fail(key, g, payload)


def _window_now(c, key, clock):
    """實測這個鍵目前的冷卻秒數（從剛失敗的時點往後逐秒推，不讀內部）。"""
    start = clock["now"]
    while c.begin(key)[0] is not FC.NO_HIT:
        clock["now"] += 1
    w = clock["now"] - start
    clock["now"] = start
    return w


# ══════════════════════════════════════════════════════════════════
# D2-f38 連續失敗次數隨時間衰減
# ══════════════════════════════════════════════════════════════════
class TestD2f38StreakDecay:
    def _climb_to_cap(self, c, clock):
        w = FAIL_COOLDOWN_SEC
        while True:
            _fail_once(c, "k")
            got = _window_now(c, "k", clock)
            assert got == w
            clock["now"] += got                             # 冷卻一過期就再失敗（正常遞增路徑）
            if w >= TTL_1HOUR:
                return
            w = min(w * 2, TTL_1HOUR)

    def test_next_day_failure_restarts_from_base(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        self._climb_to_cap(c, fc_clock)
        fc_clock["now"] += 86400                             # 隔天，中間沒成功、也沒再失敗
        _fail_once(c, "k")
        assert _window_now(c, "k", fc_clock) == FAIL_COOLDOWN_SEC, "沉寂一整天 → 從基準冷卻重新起算"

    def test_boundary_quiet_period(self, fc_clock):
        """門檻 ＝ 上一次冷卻秒數 ＋ max_seconds（自上一次失敗起算）：差 1 秒仍延續、剛好滿即重算。"""
        for extra, expect in ((-1, 2 * FAIL_COOLDOWN_SEC), (0, FAIL_COOLDOWN_SEC)):
            c = FC.FailCooldown(max_seconds=TTL_1HOUR)
            _fail_once(c, "k")
            fc_clock["now"] += FAIL_COOLDOWN_SEC + TTL_1HOUR + extra
            _fail_once(c, "k")
            assert _window_now(c, "k", fc_clock) == expect

    def test_after_decay_escalates_again(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        self._climb_to_cap(c, fc_clock)
        fc_clock["now"] += 86400
        self._climb_to_cap(c, fc_clock)                      # 衰減後照常再一路加倍到上限

    def test_continuous_failure_never_decays(self, fc_clock):
        """持續失敗、每 60 秒 rerun 一次（`TestQaN1LoadAmplification` 的情境）：一天內冷卻始終封頂。"""
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        starts = []
        end = fc_clock["now"] + 86400
        while fc_clock["now"] < end:
            h, g = c.begin("k")
            if h is FC.NO_HIT:
                starts.append(fc_clock["now"])
                c.fail("k", g, "x")
            fc_clock["now"] += 60
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        assert gaps[:5] == [180, 360, 720, 1440, 2880]
        assert all(gp == TTL_1HOUR for gp in gaps[5:]), "持續失敗不觸發衰減"

    def test_default_mode_never_writes_decay_state(self, fc_clock):
        c = FC.FailCooldown()
        for _ in range(5):
            _fail_once(c, "k")
            fc_clock["now"] += 86400
        assert c._streak == {} and c._last_fail == {}

    def test_success_and_clear_drop_decay_state(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        _fail_once(c, "a")
        _fail_once(c, "b")
        c.success("a")
        assert "a" not in c._last_fail and "b" in c._last_fail
        c.clear()
        assert c._last_fail == {}


# ══════════════════════════════════════════════════════════════════
# D2-f47 `_gen`／`_streak` 上限跟著 max_entries 走
# ══════════════════════════════════════════════════════════════════
class TestD2f47GenCapFollowsMaxEntries:
    N = FC._GEN_MAX_ENTRIES + 500

    def test_unbounded_table_keeps_escalating_past_4096_keys(self, fc_clock):
        """單股月營收的設定（`max_entries=sys.maxsize`）：超過 4096 個不同鍵後，最早的鍵仍照常加倍。"""
        import sys
        c = FC.FailCooldown(max_seconds=TTL_1HOUR, max_entries=sys.maxsize)
        _fail_once(c, 0)
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        for i in range(1, self.N):
            _fail_once(c, i)
        _fail_once(c, 0)                                     # 鍵 0 的第 2 次失敗
        assert _window_now(c, 0, fc_clock) == 2 * FAIL_COOLDOWN_SEC, "修前退回基準 180 秒"
        assert len(c._streak) == self.N and len(c._gen) == 0

    def test_success_generation_survives_past_4096_keys(self):
        import sys
        c = FC.FailCooldown(max_entries=sys.maxsize)
        for i in range(self.N):
            c.success(i)
        assert len(c._gen) == self.N and c.begin(0)[1] == 1

    @pytest.mark.parametrize("max_entries", [64, 200, FC._GEN_MAX_ENTRIES])
    def test_small_max_entries_keep_4096_floor(self, max_entries):
        """既有使用者（預設 64、K 線 200）：上限仍是 4096，逐出順序不變（最早插入者先出）。"""
        c = FC.FailCooldown(max_entries=max_entries)
        for i in range(self.N):
            c.success(i)
        assert list(c._gen) == list(range(self.N - FC._GEN_MAX_ENTRIES, self.N))

    def test_cap_between_follows_max_entries(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR, max_entries=5000)
        for i in range(6000):
            c.success(i)
            _fail_once(c, ("s", i))
        assert len(c._gen) == 5000 and len(c._streak) == 5000 and len(c._last_fail) == 5000

    def test_live_instances(self):
        import sys

        import src.data.stock.monthly_revenue_fetcher as MR
        assert MR._single_fail_cooldown._gen_cap == sys.maxsize
        assert MR._batch_fail_cooldown._gen_cap == FC._GEN_MAX_ENTRIES


# ══════════════════════════════════════════════════════════════════
# D2-f48  不再每次整表掃描 —— 結果逐字不變、成本有界
# ══════════════════════════════════════════════════════════════════
#: 批 FC 前的原始實作（origin/main `8a99564` 的 shared/fail_cooldown.py，逐字）。
_FC_BEFORE_SRC = r'''"""shared/fail_cooldown.py — 「失敗不入快取、但短時間內不重打上游」的共用小元件（L0,無 I/O）。

2026-09-27（Q3-r5／Q5-r2-r3）。CLAUDE.md §1.A-3 兩個獨立要求：
  (a) **只快取成功結果** —— `st.cache_data` 對「正常回傳」一律快取 TTL 那麼久；
      失敗若被包成空值回傳,一次網路抖動就被凍成 30 分～1 小時的假答案。
      作法：快取層內**拋出**（st.cache_data 不快取例外）,外層 wrapper 接住。
  (b) **失敗要退避** —— 但不快取失敗後,每一次 Streamlit rerun 都會再打一次上游
      （轟炸）。本元件記住「某個鍵剛失敗過」與當時的失敗回傳,冷卻期內直接回那一份,
      **不打上游**；冷卻期過後才重抓；任何一次成功立即解除。

冷卻期刻意遠短於 `shared/ttls.py` 的任何 TTL（最短 `TTL_10MIN`）—— 它只擋同一輪／
連續幾次 rerun 的重複打擊,不是把失敗凍成長時間的答案。故不放 `shared/ttls.py`
（那裡是 `@st.cache_data(ttl=N)` 的 SSOT,語意不同）。沿用
`src/data/etf/etf_fetch._DIVIDENDS_FAIL_COOLDOWN_SEC`（180 秒）既有取值。

冷卻期內**失敗旗標照帶**（回的是當時那一份失敗結果的複本）——
呼叫端看到的仍是「抓取失敗」,不會被說成「沒有資料」。

**遞增退避（選用，2026-09-28 批 D3b QA N1）**：`FailCooldown(max_seconds=...)` 開啟後，同一鍵
**連續**失敗時冷卻由 `seconds` 起、每次失敗加倍，上限 `max_seconds`；任何一次成功即歸零。
給「一次重抓就要打數百次上游」的呼叫端用（RS 掃描層）。**預設 `max_seconds=None` ＝ 關閉，
行為與新增前逐字相同**（既有使用者都不開；`tests/test_d3b_backoff_d2f4_d2f7_d2f9.py` 以
新增前的原始實作當參考模型逐步比對）。
"""
from __future__ import annotations

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

    `max_seconds`（遞增退避，見檔頭；預設 None ＝ 關閉 → 每次失敗都冷卻 `seconds` 秒，既有行為）：
    開啟後，鍵的冷卻秒數 ＝ min(`seconds` × 2^(連續失敗次數−1), `max_seconds`)。「連續」只在
    「上一筆冷卻已過期（或已被逐出）之後又失敗」時加一 —— 冷卻期內同一波並行呼叫晚到的失敗
    只更新時點、不再加倍；世代已變（期間有人成功）的失敗照舊不記、也不加。`success`／`clear` 歸零。
    冷卻秒數在查詢時才由**當下**的 `seconds` 算出（測試把 `seconds` 設 0 仍能讓紀錄立即過期）。
    """

    def __init__(self, seconds: float = FAIL_COOLDOWN_SEC,
                 max_entries: int = FAIL_COOLDOWN_MAX_ENTRIES,
                 max_seconds: float | None = None):
        self.seconds = float(seconds)
        self.max_entries = int(max_entries)
        self.max_seconds = None if max_seconds is None else float(max_seconds)
        self._fail: dict = {}
        self._gen: dict = {}
        #: 遞增退避用：鍵 → 連續失敗次數。`max_seconds` 為 None 時**永不寫入**（恆為空）。
        self._streak: dict = {}
        self._lock = threading.Lock()

    def _window_locked(self, key) -> float:
        """（持鎖呼叫）這個鍵目前的冷卻秒數。未開遞增退避 → 恆為 `seconds`（既有行為）。"""
        if self.max_seconds is None:
            return self.seconds
        window = self.seconds
        for _ in range(self._streak.get(key, 1) - 1):
            if window >= self.max_seconds:
                break
            window *= 2                                   # 每次失敗加倍
        return min(window, self.max_seconds)

    def _escalate_locked(self, key, now: float) -> None:
        """（持鎖呼叫；只在遞增退避開啟時）新一波失敗 → 連續失敗次數 +1（冷卻已達上限就不再加）。"""
        prev = self._fail.get(key)
        if prev is not None and now - prev[0] < self._window_locked(key):
            return                                        # 同一波（冷卻期內晚到的失敗）不加倍
        n = self._streak.get(key, 0)
        if n == 0 or self._window_locked(key) < self.max_seconds:
            self._streak[key] = n + 1

    def _prune_locked(self, now: float) -> None:
        """（持鎖呼叫）清掉已過冷卻期的紀錄；仍超過上限則逐出最舊者。"""
        for k in [k for k, v in self._fail.items() if now - v[0] >= self._window_locked(k)]:
            del self._fail[k]
        while len(self._fail) > self.max_entries:
            oldest = min(self._fail, key=lambda k: self._fail[k][0])
            del self._fail[oldest]
        while len(self._gen) > _GEN_MAX_ENTRIES:
            del self._gen[next(iter(self._gen))]
        while len(self._streak) > _GEN_MAX_ENTRIES:
            del self._streak[next(iter(self._streak))]

    def begin(self, key):
        """回 (冷卻中的失敗結果或 `NO_HIT`, 世代)。"""
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now)
            prev = self._fail.get(key)
            gen = self._gen.get(key, 0)
            window = self._window_locked(key)
        if prev is not None and now - prev[0] < window:
            return copy.deepcopy(prev[1]), gen
        return _NO_HIT, gen

    def fail(self, key, gen, payload):
        """記下失敗（期間沒有人成功過才記）；回傳 payload 的複本給呼叫端。"""
        with self._lock:
            if self._gen.get(key, 0) == gen:
                _now = time.monotonic()
                if self.max_seconds is not None:
                    self._escalate_locked(key, _now)
                self._fail[key] = (_now, copy.deepcopy(payload))
                self._prune_locked(_now)
        return payload

    def success(self, key):
        with self._lock:
            self._gen[key] = self._gen.get(key, 0) + 1
            self._fail.pop(key, None)
            self._streak.pop(key, None)
            self._prune_locked(time.monotonic())

    def clear(self):
        with self._lock:
            self._fail.clear()
            self._gen.clear()
            self._streak.clear()

    def __len__(self):
        with self._lock:
            return len(self._fail)

    def __contains__(self, key):
        with self._lock:
            return key in self._fail


NO_HIT = _NO_HIT


class CachedFailure(Exception):
    """快取層「失敗但有回傳值」的出口：拋出（不入 st.cache_data）,由外層 wrapper 取 `.payload`。"""

    def __init__(self, payload, msg: str = ""):
        super().__init__(msg or "fetch failed (not cached)")
        self.payload = payload
'''


class _BruteForce(FC.FailCooldown):
    """修前的「每次整表掃描」寫法（上限取現行 `_gen_cap`）：D2-f48 前後語意的參考模型。"""

    def _prune_locked(self, now):
        for k in [k for k, v in self._fail.items() if now - v[0] >= self._window_locked(k)]:
            del self._fail[k]
        while len(self._fail) > self.max_entries:
            oldest = min(self._fail, key=lambda k: self._fail[k][0])
            del self._fail[oldest]
        for d in (self._gen, self._streak, self._last_fail):
            while len(d) > self._gen_cap:
                del d[next(iter(d))]


def _clocked(monkeypatch, start=10_000.0):
    clock = {"now": start}
    fake = types.SimpleNamespace(monotonic=lambda: clock["now"])
    monkeypatch.setattr(FC, "time", fake)
    return clock, fake


_KEYS = ["a", "b", ("2330.TW", "1y"), ("2330.TW", "5d"), 7, (60, 300, False, 300), "c", "d"]


def _random_ops(rng, new, ref, ref_no_hit, clock, base_seconds, steps, check_internals):
    gens: dict = {}
    for step in range(steps):
        op = rng.choices(["tick", "begin", "fail", "success", "clear", "seconds"],
                         weights=[5, 6, 5, 2, 0.3, 0.6])[0]
        k = rng.choice(_KEYS)
        if op == "tick":
            clock["now"] += rng.choice([0, 1, 29, 30, 31, 90, 179, 180, 181, 400, 3600, 7200])
        elif op == "begin":
            (hn, gn), (ho, go) = new.begin(k), ref.begin(k)
            assert gn == go and (hn is FC.NO_HIT) == (ho is ref_no_hit), f"第 {step} 步 begin 分岔"
            if hn is not FC.NO_HIT:
                assert hn == ho
            gens.setdefault(k, []).append(gn)
        elif op == "fail":
            g = rng.choice(gens.get(k) or [0])
            payload = {"k": repr(k), "step": step}
            assert new.fail(k, g, dict(payload)) == ref.fail(k, g, dict(payload))
        elif op == "success":
            new.success(k)
            ref.success(k)
        elif op == "clear":
            new.clear()
            ref.clear()
        else:
            new.seconds = ref.seconds = rng.choice([0.0, base_seconds])
        assert len(new) == len(ref)
        assert all((kk in new) == (kk in ref) for kk in _KEYS)
        assert new._fail == ref._fail and new._gen == ref._gen, f"第 {step} 步（{op}）內部狀態分岔"
        if check_internals:
            assert new._streak == ref._streak and new._last_fail == ref._last_fail


_MODES = {
    "defaults": {},
    "small": {"seconds": 30.0, "max_entries": 3},
    "backoff": {"max_seconds": TTL_1HOUR},
    "backoff_small": {"seconds": 30.0, "max_entries": 3, "max_seconds": 100.0},
}


class TestD2f48SameResultsAsFullScan:
    @pytest.mark.parametrize("seed", range(8))
    @pytest.mark.parametrize("mode", list(_MODES))
    def test_random_ops_match_full_scan(self, monkeypatch, mode, seed):
        kw = _MODES[mode]
        clock, _ = _clocked(monkeypatch)
        new, ref = FC.FailCooldown(**kw), _BruteForce(**kw)
        _random_ops(random.Random(seed), new, ref, FC.NO_HIT, clock,
                    float(kw.get("seconds", FAIL_COOLDOWN_SEC)), 800, check_internals=True)

    @pytest.mark.parametrize("seed", range(6))
    @pytest.mark.parametrize("mode", ["defaults", "small", "backoff_no_decay"])
    def test_random_ops_match_pre_batch_model(self, monkeypatch, mode, seed):
        """golden：與批 FC 前的原始實作逐步相同（遞增退避模式把上限設極大，排除 D2-f38 的衰減）。"""
        kw = {"defaults": {}, "small": {"seconds": 30.0, "max_entries": 3},
              "backoff_no_decay": {"max_seconds": 1e12}}[mode]
        clock, fake = _clocked(monkeypatch)
        ns: dict = {"__name__": "_fail_cooldown_before_fc"}
        exec(compile(_FC_BEFORE_SRC, "<shared/fail_cooldown.py@8a99564>", "exec"), ns)
        ns["time"] = fake
        new, old = FC.FailCooldown(**kw), ns["FailCooldown"](**kw)
        _random_ops(random.Random(seed), new, old, ns["_NO_HIT"], clock,
                    float(kw.get("seconds", FAIL_COOLDOWN_SEC)), 800, check_internals=False)
        assert new._streak == old._streak

    def test_many_keys_expire_in_order(self, fc_clock):
        c = FC.FailCooldown(seconds=1000.0, max_entries=10_000)
        for i in range(500):
            _fail_once(c, i)
            fc_clock["now"] += 1
        fc_clock["now"] += 500
        c.begin("probe")
        assert len(c) == 499 and 0 not in c and 1 in c
        fc_clock["now"] += 250
        c.begin("probe")
        assert len(c) == 249 and 250 not in c and 251 in c


class TestD2f48HeapRebuildTriggers:
    def test_runtime_max_seconds_change(self, fc_clock):
        """執行期改 `max_seconds`：到期順序會變 → 必須重建（否則較晚到期的頂端擋住已過期者）。"""
        new, ref = FC.FailCooldown(max_seconds=TTL_1HOUR), _BruteForce(max_seconds=TTL_1HOUR)
        t0 = fc_clock["now"]
        for c in (new, ref):
            fc_clock["now"] = t0 - 280
            _fail_once(c, "a")
            fc_clock["now"] = t0 - 100
            _fail_once(c, "a")                               # a：冷卻 360，到期 t0+260
            fc_clock["now"] = t0
            _fail_once(c, "b")                               # b：冷卻 180，到期 t0+180（heap 頂）
            c.max_seconds = 180.0                            # a 的冷卻縮成 180 → 到期 t0+80
        fc_clock["now"] = t0 + 100
        for c in (new, ref):
            c.begin("probe")
        assert new._fail == ref._fail and "a" not in new and "b" in new

    def test_streak_eviction_of_live_key(self, fc_clock):
        """仍在冷卻中的鍵，其連續次數被上限逐出 → 冷卻秒數變短 → 必須重建。"""
        cap = FC._GEN_MAX_ENTRIES
        new, ref = FC.FailCooldown(max_seconds=TTL_1HOUR, max_entries=cap), \
            _BruteForce(max_seconds=TTL_1HOUR, max_entries=cap)
        t0 = fc_clock["now"]
        for c in (new, ref):
            fc_clock["now"] = t0
            for dt in (0, 180, 540):                         # old：連續 3 次 → 冷卻 720，到期 t0+1260
                fc_clock["now"] = t0 + dt
                _fail_once(c, "old")
            for i in range(cap - 1):                         # 4095 個鍵，t0+720 到期
                _fail_once(c, i)
            fc_clock["now"] = t0 + 720
            c.begin("probe")                                 # 清掉那 4095 筆（連續次數表仍在）
            _fail_once(c, "z")                               # 連續次數表超過上限 → 逐出 old 的次數
            assert "old" not in c._streak
        for c in (new, ref):
            c.begin("probe")                                 # old 的冷卻退回 180 → 已過期
        assert new._fail == ref._fail and "old" not in new and "z" in new

    def test_stale_entries_are_compacted(self, fc_clock):
        c = FC.FailCooldown(max_entries=10_000)
        _fail_once(c, "anchor")                              # 頂端一直是仍在冷卻中的 anchor
        for i in range(5000):
            _fail_once(c, i)
            c.success(i)                                     # 留下過時項目
        bound = 2 * len(c) + 64 + 1
        assert len(c._exp_heap) <= bound and len(c._age_heap) <= bound


class TestD2f48EqualTimestampReinsert:
    """QA FAIL（2026-10-01）：同一時點「被移除後又重新插入」的鍵，舊 heap 項目時點相同 → 須以插入序判過時。"""

    def _pair(self, **kw):
        return FC.FailCooldown(**kw), _BruteForce(**kw)

    def test_exp_heap_evicted_then_refailed_same_instant(self, fc_clock):
        """max_entries=2：t=0 依序失敗 A、B、C（A 被逐出）、再失敗 A（連續次數 +1 → 冷卻不同）。"""
        new, ref = self._pair(seconds=10.0, max_entries=2, max_seconds=100.0)
        t0 = fc_clock["now"]
        for c in (new, ref):
            fc_clock["now"] = t0
            for k in ("A", "B", "C", "A"):
                _h, g = c.begin(k)
                c.fail(k, g, k)
        fc_clock["now"] = t0 + 15
        for c in (new, ref):
            c.begin("probe")
        assert new._fail == ref._fail and len(new) == len(ref)
        assert "C" not in new, "C 冷卻 10 秒，t=15 已過期，不得被 A 的過時項目擋住"

    def test_age_heap_removed_then_refailed_same_instant(self, fc_clock):
        """success 移除 A 後同一時點又失敗 A：逐出最舊者須依**新的**插入序（B 先於新 A）。"""
        new, ref = self._pair(max_entries=2)
        for c in (new, ref):
            for k in ("A", "B"):
                _fail_once(c, k)
            c.success("A")
            for k in ("A", "C"):
                _fail_once(c, k)
        assert new._fail == ref._fail
        assert set(new._fail) == {"A", "C"}, "應逐出 B（插入序最早），不是重新插入的 A"

    @pytest.mark.parametrize("seed", range(40))
    @pytest.mark.parametrize("kw", [{"seconds": 10.0, "max_entries": 2, "max_seconds": 100.0},
                                    {"seconds": 10.0, "max_entries": 2}], ids=["backoff", "fixed"])
    def test_frozen_clock_differential(self, monkeypatch, kw, seed):
        """凍結時鐘為主（多數操作在同一時點）＋極小上限：逐步與整表掃描參考模型比對內部狀態。"""
        clock, _ = _clocked(monkeypatch)
        new, ref = FC.FailCooldown(**kw), _BruteForce(**kw)
        rng = random.Random(seed)
        gens: dict = {}
        keys = ["A", "B", "C", "D"]
        for step in range(400):
            op = rng.choices(["tick", "begin", "fail", "success"], weights=[1, 4, 6, 2])[0]
            k = rng.choice(keys)
            if op == "tick":
                clock["now"] += rng.choice([0, 0, 5, 10, 15, 25])
            elif op == "begin":
                (hn, gn), (ho, go) = new.begin(k), ref.begin(k)
                assert gn == go and (hn is FC.NO_HIT) == (ho is FC.NO_HIT) and (hn == ho or hn is FC.NO_HIT)
                gens.setdefault(k, []).append(gn)
            elif op == "fail":
                g = rng.choice(gens.get(k) or [0])
                new.fail(k, g, step)
                ref.fail(k, g, step)
            else:
                new.success(k)
                ref.success(k)
            assert new._fail == ref._fail and new._streak == ref._streak, f"第 {step} 步（{op}）分岔"


class _Counting(FC.FailCooldown):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.window_calls = 0

    def _window_locked(self, key):
        self.window_calls += 1
        return super()._window_locked(key)


class TestD2f48BoundedCost:
    """以「算冷卻秒數的次數」當操作數（不量牆鐘）：修前每次存取都把整張表算一遍。"""
    N = 5000

    @pytest.mark.parametrize("kw", [{}, {"max_seconds": TTL_1HOUR}], ids=["fixed", "backoff"])
    def test_begin_cost_independent_of_table_size(self, fc_clock, kw):
        import sys
        c = _Counting(max_entries=sys.maxsize, **kw)
        for i in range(self.N):
            _fail_once(c, i)
        c.window_calls = 0
        rng = random.Random(0)
        for _ in range(1000):
            c.begin(rng.randrange(self.N * 2))
        assert c.window_calls <= 2 * 1000, f"每次 begin 應為常數次，實得 {c.window_calls}（修前 ≈ {self.N * 1000}）"

    def test_total_cost_amortised_over_mixed_ops(self, fc_clock):
        import sys
        c = _Counting(max_entries=sys.maxsize, max_seconds=TTL_1HOUR)
        rng = random.Random(1)
        ops = 20_000
        for _ in range(ops):
            k = rng.randrange(3000)
            r = rng.random()
            if r < 0.5:
                h, g = c.begin(k)
                if h is FC.NO_HIT and rng.random() < 0.7:
                    c.fail(k, g, "x")
            elif r < 0.6:
                c.success(k)
            fc_clock["now"] += rng.choice([0, 1, 5, 30])
        assert c.window_calls <= 8 * ops, f"攤銷有界：{c.window_calls} 次 / {ops} 次操作"

    def test_eviction_cost_bounded(self, fc_clock):
        c = _Counting(max_entries=64)
        for i in range(5000):
            _fail_once(c, i)
        assert len(c) == 64 and set(c._fail) == set(range(5000 - 64, 5000)), "逐出最舊者（同修前）"
        assert len(c._age_heap) <= 2 * 64 + 64 + 1 and len(c._exp_heap) <= 2 * 64 + 64 + 1, "heap 有壓實"


class TestThreadSafety:
    def test_concurrent_ops_keep_invariants_and_match_after_expiry(self):
        """真時鐘、多執行緒同時 begin／fail／success：不拋例外、內部結構一致；全部過期後清空。"""
        c = FC.FailCooldown(seconds=0.05, max_entries=50, max_seconds=0.4)
        errors = []
        stop = threading.Event()

        def worker(seed):
            rng = random.Random(seed)
            try:
                while not stop.is_set():
                    k = rng.randrange(120)
                    h, g = c.begin(k)
                    if h is FC.NO_HIT:
                        if rng.random() < 0.8:
                            c.fail(k, g, {"k": k})
                        else:
                            c.success(k)
            except Exception as e:  # pragma: no cover — 失敗時才會走到
                errors.append(e)

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in ts:
            t.start()
        time.sleep(0.6)
        stop.set()
        for t in ts:
            t.join()
        assert not errors
        with c._lock:
            assert len(c._fail) <= 50 and set(c._ins) == set(c._fail)
            live_exp = {k for _e, _s, k, ts_, ins in c._exp_heap
                        if k in c._fail and c._fail[k][0] == ts_ and c._ins[k] == ins}
            live_age = {k for ts_, ins, _s, k in c._age_heap
                        if k in c._fail and c._fail[k][0] == ts_ and c._ins[k] == ins}
            assert live_exp == set(c._fail) == live_age, "每筆紀錄在兩個 heap 都有有效項目"
        time.sleep(0.4 + 0.4 + 0.05)                          # 超過任何冷卻（封頂 0.4）
        c.begin("probe")
        assert len(c) == 0
