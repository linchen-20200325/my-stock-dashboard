"""shared/fetch_outcome.py — 「空抓取」三態（L0 純規則，零 I/O、不 import pandas）。

D3（客戶 2026-11-08 核准，DEC-148）：fetcher 回空表時，過去一律被記成「抓取結果為空」
（`shared.staleness.EMPTY_FETCH_MARKER`），讀取端分不出下列三種完全不同的情況。本檔把它分成：

- ``NO_NEW_DATA``   有正面證據：請求與來源讀取都成功，且在可確認範圍內來源沒有新觀測。
                    （例：FinMind HTTP 200、status 200、``data == []``。）
- ``FETCH_FAILED``  明確的網路／API／認證／解析／欄位驗證錯誤。**必須附錯誤證據**。
- ``UNDETERMINED``  空回應或證據不足。**保守預設**：fetcher 沒有標記就是這個。
                    ⛔ 不得以「今天是週末／休市」推論成功 —— 那是推論，不是證據。

與 freshness 分離（⛔ 不得混用）
--------------------------------
本三態描述的是**這一次抓取請求**的結果；`shared.freshness_policy.FreshnessStatus`
描述的是**資料本身相對今天夠不夠新**。兩者互不蘊含：
- NO_NEW_DATA ≠ 資料新鮮（來源可能本來就很久沒更新）；
- FETCH_FAILED ≠ 資料過期（上次抓到的值可能仍然是當期）。
本三態**不取代** Last Good 觀測日（metadata 的 ``last_updated``／``row_count`` 仍描述磁碟上現有資料）；
空抓取**不寫 0、不寫 neutral**，既有檔原封不動。本檔刻意不 import freshness_policy／staleness。

攜帶方式（向後相容）
--------------------
fetcher 仍只回 DataFrame；結果掛在 ``DataFrame.attrs``：
``attrs["fetch_outcome"]``（三態字串）與 ``attrs["fetch_evidence"]``（短字串）。
缺 attrs ＝ UNDETERMINED。evidence 會進 metadata.json 並被 `publish_data_pr` 視為實質欄位，
所以**不得含每輪變動的內容（時間戳等）**：`sanitize_evidence` 會把 ISO 日期時間洗成 ``<ts>``。
"""
from __future__ import annotations

import re
from enum import Enum

ATTR_OUTCOME = "fetch_outcome"
ATTR_EVIDENCE = "fetch_evidence"

#: metadata 欄位名（與 attrs 鍵同名）
META_OUTCOME_KEY = ATTR_OUTCOME
META_EVIDENCE_KEY = ATTR_EVIDENCE

EVIDENCE_MAX_LEN = 120

#: fetcher 沒有標記時的保守說明
EVIDENCE_NOT_PROVIDED = "fetcher 未提供 fetch_outcome（保守預設）"

_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?")


class FetchOutcome(str, Enum):
    """空抓取三態（見模組 docstring）。繼承 str：可直接 json.dumps／與字串比較。"""
    NO_NEW_DATA = "NO_NEW_DATA"
    FETCH_FAILED = "FETCH_FAILED"
    UNDETERMINED = "UNDETERMINED"


def parse_outcome(value) -> FetchOutcome | None:
    """字串／列舉 → FetchOutcome；不是三態之一 → None（呼叫端決定怎麼處置，不在此猜）。"""
    if isinstance(value, FetchOutcome):
        return value
    if isinstance(value, str):
        try:
            return FetchOutcome(value)
        except ValueError:
            return None
    return None


def sanitize_evidence(evidence) -> str:
    """單行、洗掉 ISO 日期時間、截到 EVIDENCE_MAX_LEN。evidence 不得含每輪變動的時間戳。"""
    s = " ".join(str(evidence or "").split())
    s = _TS_RE.sub("<ts>", s)
    if len(s) > EVIDENCE_MAX_LEN:
        s = s[: EVIDENCE_MAX_LEN - 1] + "…"
    return s


def tag_outcome(df, outcome: FetchOutcome, evidence: str = ""):
    """在 DataFrame 上標記抓取結果並原樣回傳 df。FETCH_FAILED 必須附證據（否則 ValueError）。"""
    oc = parse_outcome(outcome)
    if oc is None:
        raise ValueError(f"fetch_outcome 必須是 FetchOutcome 三態之一，收到 {outcome!r}")
    ev = sanitize_evidence(evidence)
    if oc is FetchOutcome.FETCH_FAILED and not ev:
        raise ValueError("FETCH_FAILED 必須附錯誤證據（evidence 不可為空）")
    df.attrs[ATTR_OUTCOME] = oc.value
    df.attrs[ATTR_EVIDENCE] = ev
    return df


def read_outcome(df) -> tuple[FetchOutcome, str]:
    """讀 df.attrs → (outcome, evidence)。缺／不合法／FETCH_FAILED 缺證據 → UNDETERMINED（保守預設）。"""
    attrs = getattr(df, "attrs", None) or {}
    raw = attrs.get(ATTR_OUTCOME)
    if raw is None:
        return FetchOutcome.UNDETERMINED, EVIDENCE_NOT_PROVIDED
    oc = parse_outcome(raw)
    ev = sanitize_evidence(attrs.get(ATTR_EVIDENCE))
    if oc is None:
        return FetchOutcome.UNDETERMINED, sanitize_evidence(f"fetch_outcome 值不合法：{raw!r}（保守預設）")
    if oc is FetchOutcome.FETCH_FAILED and not ev:
        return FetchOutcome.UNDETERMINED, "FETCH_FAILED 缺錯誤證據 → 降為 UNDETERMINED（保守預設）"
    if oc is FetchOutcome.UNDETERMINED and not ev:
        ev = EVIDENCE_NOT_PROVIDED
    return oc, ev
