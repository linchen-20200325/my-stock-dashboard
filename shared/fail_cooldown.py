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


NO_HIT = _NO_HIT


class CachedFailure(Exception):
    """快取層「失敗但有回傳值」的出口：拋出（不入 st.cache_data）,由外層 wrapper 取 `.payload`。"""

    def __init__(self, payload, msg: str = ""):
        super().__init__(msg or "fetch failed (not cached)")
        self.payload = payload
