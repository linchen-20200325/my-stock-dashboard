"""src/data/notify/line_notify.py — LINE 推播(Messaging API push,L1 I/O)。

⚠️ LINE Notify 已於 2025-03-31 停用 → 改用 **Messaging API**:需 LINE 官方帳號的
**Channel access token** + 收訊者 **userId**(見 docs/push_daily_signals.md)。

`send_line_message(text, *, token=None, to=None)` → push,回實際送出的訊息物件數。
token/to 未提供則讀環境變數 `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`(GitHub Secrets)。

§1 fail-loud:token/userId 缺 → raise(cron 紅燈,**不靜默**);HTTP 非 200 → raise 帶狀態碼。
LINE 限制:單則 text ≤ 5000 字、單次 push ≤ 5 則 → 超長依行分塊、每 5 則一批(§4.6 邊界)。
§8.2 L1:唯一 I/O(requests POST),無 streamlit、無業務邏輯 / 門檻 / 組字。
"""
from __future__ import annotations

import os

import requests

from src.data.notify.chunk import split_chunks

_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_MAX = 4900          # LINE text 上限 5000;留 buffer
_MSGS_PER_PUSH = 5   # 單次 push 最多 5 則 message


def send_line_message(text, *, token: str | None = None,
                      to: str | None = None, timeout: int = 20) -> int:
    """LINE Messaging API push(超長自動分塊 + 每 5 則一批)。回實際送出訊息物件數。

    §1:token/userId 缺 → ValueError(cron 紅燈,不靜默);HTTP 非 200 → RuntimeError。
    """
    _tok = token or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    _to = to or os.environ.get("LINE_USER_ID", "")
    if not _tok or not _to:
        raise ValueError(
            "LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID 未設定"
            "(請於 GitHub repo Settings → Secrets 新增;LINE Notify 已停用,改用 Messaging API)")
    _headers = {"Authorization": f"Bearer {_tok}", "Content-Type": "application/json"}
    _chunks = split_chunks(str(text), _MAX) or [""]
    _sent = 0
    for _i in range(0, len(_chunks), _MSGS_PER_PUSH):
        _batch = _chunks[_i:_i + _MSGS_PER_PUSH]
        _msgs = [{"type": "text", "text": _c} for _c in _batch]
        _r = requests.post(_PUSH_URL, headers=_headers,
                           json={"to": _to, "messages": _msgs}, timeout=timeout)
        if _r.status_code != 200:
            raise RuntimeError(
                f"LINE push 失敗 HTTP {_r.status_code}: {_r.text[:200]}")
        _sent += len(_batch)
    return _sent
