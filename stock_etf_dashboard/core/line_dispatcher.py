"""L0 Infra — LINE 推播 (資料憲法 §1).

缺 token / 缺收件人 / API 失敗 → raise，不靜默吞掉（否則「以為有推播其實沒有」）。
"""
from __future__ import annotations

import os

import requests

from .circuit_breaker import require

_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_MAX_TEXT_LEN = 5000  # LINE 單則上限


def send_line_message(
    text: str,
    *,
    token: str | None = None,
    user_id: str | None = None,
    timeout: float = 10.0,
) -> dict:
    """推一則文字。回傳 {'ok': True, 'status': 200}；失敗 raise。"""
    token = token or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = user_id or os.environ.get("LINE_USER_ID")
    require(bool(token), "缺 LINE_CHANNEL_ACCESS_TOKEN,無法推播")
    require(bool(user_id), "缺 LINE_USER_ID,無法推播")
    require(bool(text and text.strip()), "訊息內容為空,拒絕推播")

    body = text if len(text) <= _MAX_TEXT_LEN else text[: _MAX_TEXT_LEN - 1] + "…"
    resp = requests.post(
        _PUSH_URL,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": body}]},
        timeout=timeout,
    )
    require(
        resp.status_code == 200,
        f"LINE 推播失敗 status={resp.status_code} body={resp.text[:200]}",
    )
    return {"ok": True, "status": resp.status_code}
