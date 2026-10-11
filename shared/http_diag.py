"""shared/http_diag.py — 外部 HTTP 回應「診斷用 body 片段」的 L0 helper(批 Z39)。

用途:L1 fetcher 在「回應格式不對 / 解析 0 筆 / 例外」時,把 response body **前
`LOG_BODY_HEAD_CHARS` 字**印進 log 供排查(例:TPEx 改版 / 擋爬時回 HTML 錯誤頁)。

§資安:**只印 body**,不碰 headers / proxy URL / token;且一律先過
`shared.secret_scrub.scrub_secrets` 再截斷 —— 先截再洗可能把一段金鑰切成洗不到的半截。
為免對 MB 級 body 跑整套正則,先取前 `_SCRUB_WINDOW_CHARS` 字再洗、再截到 500。
純函式、零 I/O(只讀已拿到的 response 物件屬性),不 import streamlit。
"""
from __future__ import annotations

from shared.secret_scrub import scrub_secrets

#: 診斷 log 印出的 body 字數上限(客戶 2026-10-11 Q-z28 診斷要求:前 500 字)。
LOG_BODY_HEAD_CHARS: int = 500
#: 洗秘密前先取的視窗(> LOG_BODY_HEAD_CHARS,避免洗前截斷把金鑰切半)。
_SCRUB_WINDOW_CHARS: int = 4000


def scrubbed_body_head(resp) -> str:
    """response → 洗過秘密的 body 前 500 字。無 `.text` / 讀取失敗 → 說明字串(不炸)。"""
    if resp is None:
        return "<no response>"
    try:
        _text = resp.text
    except Exception as _e:  # noqa: BLE001 — 診斷 helper 不得讓 fetcher 多炸一次
        return f"<body 讀取失敗: {type(_e).__name__}>"
    if _text is None:
        return "<empty body>"
    if isinstance(_text, (bytes, bytearray)):
        _text = bytes(_text[:_SCRUB_WINDOW_CHARS]).decode("utf-8", "replace")
    return scrub_secrets(str(_text)[:_SCRUB_WINDOW_CHARS])[:LOG_BODY_HEAD_CHARS]
