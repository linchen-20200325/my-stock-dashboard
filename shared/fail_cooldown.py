"""shared/fail_cooldown.py — 「失敗不入快取、但短時間內不重打上游」的共用小元件（L0,無 I/O）。

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
import heapq
import itertools
import threading
import time

#: 失敗後冷卻秒數（見檔頭）。
FAIL_COOLDOWN_SEC: float = 180.0

#: 失敗紀錄的鍵數上限（長時間斷線時不無限成長；`_combined_inst_fail_cooldown` 每鍵存一整張 df）。
#: 取 64 ＝ 原 `StockDataLoader.get_combined_data` 快取的 `max_entries`。超過時逐出最舊的紀錄。
FAIL_COOLDOWN_MAX_ENTRIES: int = 64

#: 成功世代計數表（及遞增退避的連續次數表）的鍵數**下限**（每鍵只存一個 int；超過時逐出最早插入者）。
#: 實際上限 ＝ max(`max_entries`, 本值)（D2-f47，2026-10-01）：跟著失敗紀錄的上限走，
#: 但不低於 4096（既有 `max_entries ≤ 4096` 的使用者逐字不變）。
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

    連續失敗次數**隨時間衰減**（D2-f38，2026-10-01）：新一波失敗時，若距上一次失敗已超過
    「上一次的冷卻秒數 ＋ `max_seconds`」（冷卻結束後整整一個上限期間都沒再失敗），視為新的一串，
    連續次數從頭算（冷卻回到 `seconds`）。冷卻一過期就再失敗的正常遞增路徑不受影響。
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
        #: 遞增退避用：鍵 → 最近一次記下失敗的時點（D2-f38 衰減判斷用）。`max_seconds` 為 None 時永不寫入。
        self._last_fail: dict = {}
        # D2-f48（2026-10-01）：`_prune_locked` 不再每次整表掃描。兩個延遲刪除的 heap：
        #   `_exp_heap`（到期時點, 推入序, 鍵, 失敗時點）—— 依到期先後清過期紀錄；
        #   `_age_heap`（失敗時點, 鍵的插入序, 推入序, 鍵）—— 超過上限時逐出最舊者
        #   （同時點時取插入序最小者 ＝ 修前 `min(self._fail, ...)` 依 dict 順序取第一個）。
        # 過時的項目（鍵已被移除或之後又失敗過）浮到頂端時才丟掉。冷卻秒數只在 `seconds`／
        # `max_seconds` 被改、或仍有紀錄的鍵的連續次數被逐出時改變 → 那時整個重建到期 heap。
        self._ins: dict = {}
        self._exp_heap: list = []
        self._age_heap: list = []
        self._push_seq = itertools.count()
        self._heap_params = (self.seconds, self.max_seconds)
        self._exp_dirty = False
        self._lock = threading.Lock()

    @property
    def _gen_cap(self) -> int:
        """`_gen`／`_streak`／`_last_fail` 的鍵數上限（D2-f47：跟著 `max_entries` 走）。"""
        return max(self.max_entries, _GEN_MAX_ENTRIES)

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
        last = self._last_fail.get(key)
        if last is not None and now - last >= self._window_locked(key) + self.max_seconds:
            self._streak.pop(key, None)                   # D2-f38：沉寂超過一個上限期間 → 從頭算
        n = self._streak.get(key, 0)
        if n == 0 or self._window_locked(key) < self.max_seconds:
            self._streak[key] = n + 1

    def _record_locked(self, key, now: float, payload) -> None:
        """（持鎖呼叫）寫入失敗紀錄並推入兩個 heap（冷卻秒數須已依本次失敗更新）。"""
        if key not in self._fail:
            self._ins[key] = next(self._push_seq)
        self._fail[key] = (now, payload)
        seq = next(self._push_seq)
        heapq.heappush(self._exp_heap, (now + self._window_locked(key), seq, key, now))
        heapq.heappush(self._age_heap, (now, self._ins[key], seq, key))

    def _drop_locked(self, key) -> None:
        self._fail.pop(key, None)
        self._ins.pop(key, None)

    def _rebuild_exp_locked(self) -> None:
        self._exp_heap = [(v[0] + self._window_locked(k), next(self._push_seq), k, v[0])
                          for k, v in self._fail.items()]
        heapq.heapify(self._exp_heap)
        self._heap_params = (self.seconds, self.max_seconds)
        self._exp_dirty = False

    def _prune_locked(self, now: float) -> None:
        """（持鎖呼叫）清掉已過冷卻期的紀錄；仍超過上限則逐出最舊者。

        結果與修前「每次整表掃描」逐字相同；成本為攤銷 O(log n)（D2-f48）。"""
        bloat = 2 * len(self._fail) + 64                  # 過時項目太多 → 壓實（攤銷 O(1)）
        if (self._exp_dirty or self._heap_params != (self.seconds, self.max_seconds)
                or len(self._exp_heap) > bloat):
            self._rebuild_exp_locked()
        if len(self._age_heap) > bloat:
            self._age_heap = [(v[0], self._ins[k], next(self._push_seq), k) for k, v in self._fail.items()]
            heapq.heapify(self._age_heap)
        heap = self._exp_heap
        while heap:
            _exp, _seq, k, ts = heap[0]
            cur = self._fail.get(k)
            if cur is None or cur[0] != ts:
                heapq.heappop(heap)                       # 過時項目
            elif now - ts >= self._window_locked(k):
                heapq.heappop(heap)
                self._drop_locked(k)
            else:
                break                                     # 其餘紀錄都還在冷卻期內
        age = self._age_heap
        while len(self._fail) > self.max_entries:
            ts, ins, _seq, k = heapq.heappop(age)
            cur = self._fail.get(k)
            if cur is not None and cur[0] == ts and self._ins.get(k) == ins:
                self._drop_locked(k)
        cap = self._gen_cap
        while len(self._gen) > cap:
            del self._gen[next(iter(self._gen))]
        while len(self._streak) > cap:
            k = next(iter(self._streak))
            del self._streak[k]
            if k in self._fail:
                self._exp_dirty = True                    # 這個鍵的冷卻秒數變了 → 下次重建
        while len(self._last_fail) > cap:
            del self._last_fail[next(iter(self._last_fail))]

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
                    self._last_fail.pop(key, None)        # 重新插入：表內維持「最近失敗在後」的順序
                    self._last_fail[key] = _now
                self._record_locked(key, _now, copy.deepcopy(payload))
                self._prune_locked(_now)
        return payload

    def success(self, key):
        with self._lock:
            self._gen[key] = self._gen.get(key, 0) + 1
            self._drop_locked(key)
            self._streak.pop(key, None)
            self._last_fail.pop(key, None)
            self._prune_locked(time.monotonic())

    def clear(self):
        with self._lock:
            self._fail.clear()
            self._gen.clear()
            self._streak.clear()
            self._last_fail.clear()
            self._ins.clear()
            self._exp_heap = []
            self._age_heap = []
            self._exp_dirty = False

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
