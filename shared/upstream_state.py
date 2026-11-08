"""shared/upstream_state.py — 「cron 自陳的上游抓取狀態」統一判定（L0 純規則，零 I/O、不 import pandas／streamlit）。

D3 B2（客戶 2026-11-08 核准，DEC-148）：B1 讓 `metadata.json` 的 dataset 在「空抓取」時多帶
``fetch_outcome``／``fetch_evidence``；但讀取端（`macro_cache_reader`、`calibrate_health_weights.check_inputs_fresh`、
UI 文案）仍只看 ``last_error`` 字串，所以：
- ``FETCH_FAILED`` 時 ``last_error`` 仍是 `EMPTY_FETCH_MARKER` → 校準閘門把它當「沒新資料」放行；
- UI 把所有空抓取一律稱為「上游最近一次抓取失敗」。

本檔是**唯一**把 (last_error, fetch_outcome, fetch_evidence) 折成「上游狀態」的地方，所有 consumer 走同一判定。

三個語意彼此獨立（⛔ 不得互相取代）
------------------------------------
- ``last_error``      cron 自陳的錯誤字串（保持原樣、原樣轉述）；
- ``fetch_outcome``   **這一次抓取請求**的結果（`shared.fetch_outcome` 三態）；
- freshness           **資料本身**相對今天夠不夠新（`macro_cache_reader.compute_cache_staleness` 的 `is_stale`）。
本檔只處理前兩者；freshness 由呼叫端另外判，不在此蘊含。NO_NEW_DATA 不重設觀測日、不代表資料最新。

判定規則（保守優先）
--------------------
1. ``last_error`` 為空：無上游問題（回 None）。例外：``fetch_outcome`` 明確是帶證據的 FETCH_FAILED，或
   UNDETERMINED → 照該態回（矛盾 metadata 不得被當成功）；NO_NEW_DATA 配空 last_error → None。
2. ``last_error`` **完全等於** `shared.staleness.EMPTY_FETCH_MARKER`（空抓取）：以 ``fetch_outcome`` 為準 ——
   NO_NEW_DATA／FETCH_FAILED／UNDETERMINED；**缺欄、值不合法、FETCH_FAILED 缺證據 → UNDETERMINED**
   （舊 metadata 無三態欄，不得預設成成功，也不得預設成失敗）。
3. ``last_error`` 是**任何其他**非空字串（例外型別名、HTTP 錯誤、複合字串如「抓取結果為空；既有檔 sanity 不過,待重建」、
   缺 token 跳過）：一律 FETCH_FAILED —— **不論 fetch_outcome 寫什麼**（例如複合字串配 NO_NEW_DATA 仍是錯誤，
   因為既有檔已知不合格，不是「沒有新資料」）。這也是 `update_macro_history` 例外路徑「不寫 outcome 欄」的向後相容讀法。
"""
from __future__ import annotations

from shared import staleness as _staleness
from shared.fetch_outcome import FetchOutcome, parse_outcome, sanitize_evidence

#: 畫面文案（僅文字）。三態各自一句，⛔ 不得把所有空抓取都稱為「抓取失敗」。
UPSTREAM_TEXT_FETCH_FAILED = "上游最近一次抓取失敗"
UPSTREAM_TEXT_NO_NEW_DATA = "最近一次抓取成功，來源無新資料（不代表資料最新）"
UPSTREAM_TEXT_UNDETERMINED = "最近一次抓取結果無法判定"

_TEXT_BY_STATE = {
    FetchOutcome.FETCH_FAILED: UPSTREAM_TEXT_FETCH_FAILED,
    FetchOutcome.NO_NEW_DATA: UPSTREAM_TEXT_NO_NEW_DATA,
    FetchOutcome.UNDETERMINED: UPSTREAM_TEXT_UNDETERMINED,
}


def is_empty_fetch_marker(last_error) -> bool:
    """`last_error` 是否**完全等於**空抓取標記（不去空白、不比前綴／包含）。每次呼叫才讀 `shared.staleness.EMPTY_FETCH_MARKER`
    （SSOT：寫入端與讀取端同一個常數，改字一起變）。"""
    return isinstance(last_error, str) and last_error == _staleness.EMPTY_FETCH_MARKER


def classify_upstream(last_error, fetch_outcome=None, fetch_evidence=None) -> tuple[FetchOutcome | None, str]:
    """(last_error, fetch_outcome, fetch_evidence) → (上游狀態或 None, 證據短字串)。見模組 docstring 規則 1~3。"""
    _err = last_error if isinstance(last_error, str) else ("" if last_error is None else str(last_error))
    _ev = sanitize_evidence(fetch_evidence)
    _oc = parse_outcome(fetch_outcome)
    # FETCH_FAILED 缺證據 → 證據不足，降為 UNDETERMINED（與 `shared.fetch_outcome.read_outcome` 同規則）
    if _oc is FetchOutcome.FETCH_FAILED and not _ev:
        _oc = FetchOutcome.UNDETERMINED
    if not _err.strip():
        if _oc is FetchOutcome.FETCH_FAILED or _oc is FetchOutcome.UNDETERMINED:
            return _oc, _ev
        return None, ""
    if is_empty_fetch_marker(_err):       # 完全相等（不去空白、不比前綴／包含）
        return (_oc if _oc is not None else FetchOutcome.UNDETERMINED), _ev
    return FetchOutcome.FETCH_FAILED, _ev


def upstream_state_value(state) -> str:
    """狀態 → 可放進 `.attrs`／dataclass 的字串（None → ""）。"""
    return state.value if isinstance(state, FetchOutcome) else ""


def upstream_state_text(state) -> str:
    """狀態（FetchOutcome 或其字串值）→ 畫面文案；None／空／不合法 → ""。"""
    _s = parse_outcome(state)
    return _TEXT_BY_STATE.get(_s, "") if _s is not None else ""


def gate_allows(state) -> bool:
    """校準閘門：只有「無上游問題」（None／""）或 NO_NEW_DATA 可放行（仍須另外通過 freshness 判定）。
    FETCH_FAILED／UNDETERMINED／不合法值一律不放行。"""
    if state is None or state == "":
        return True
    return parse_outcome(state) is FetchOutcome.NO_NEW_DATA
