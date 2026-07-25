"""src/data/notify/telegram_notify.py — Telegram Bot 推播(L1 I/O)。

`send_telegram_message(text, *, token=None, chat_id=None)` → 送出,回實際送出塊數。
token/chat_id 未提供則讀環境變數 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`(GitHub Secrets)。

§1 fail-loud:token/chat_id 缺 → raise(cron 紅燈,**不靜默**);HTTP 非 200 → raise 帶狀態碼。
Telegram 單訊息上限 4096 字 → 超長自動依行分塊(§4.6 邊界)。
§8.2 L1:唯一 I/O(requests POST),無 streamlit、無業務邏輯 / 門檻 / 組字。
"""
from __future__ import annotations

import os

import requests

from src.data.notify.chunk import split_chunks

_API = "https://api.telegram.org/bot{token}/sendMessage"
_MAX = 4000   # Telegram 上限 4096;留 buffer 給 emoji / 多位元組


def send_telegram_message(text, *, token: str | None = None,
                          chat_id: str | None = None, timeout: int = 20) -> int:
    """送 Telegram 訊息(超長自動分塊)。回實際送出的塊數。

    §1:token/chat_id 缺 → ValueError(cron 紅燈,不靜默);HTTP 非 200 → RuntimeError。
    """
    _tok = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    _cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not _tok or not _cid:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 未設定"
            "(請於 GitHub repo Settings → Secrets 新增)")
    _url = _API.format(token=_tok)
    _chunks = split_chunks(str(text), _MAX) or [""]
    for _c in _chunks:
        _r = requests.post(
            _url,
            json={"chat_id": _cid, "text": _c, "disable_web_page_preview": True},
            timeout=timeout,
        )
        if _r.status_code != 200:
            raise RuntimeError(
                f"Telegram sendMessage 失敗 HTTP {_r.status_code}: {_r.text[:200]}")
    return len(_chunks)
