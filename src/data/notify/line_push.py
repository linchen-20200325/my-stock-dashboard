"""src/data/notify/line_push.py — LINE Messaging API 推播 sender(L1 outbound I/O)

morning_brief 早報用。打 LINE **官方 Messaging API** `/push` endpoint
(舊 LINE Notify 已於 2025/3 停用,只能走 Messaging API)。

- token / user id 由環境變數讀(GitHub Actions secrets 注入):
  `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`
- **§1 Fail Loud**:重試 N 次後仍失敗 → `raise`(讓 cron job 紅燈,你會發現「今天沒收到」對得上)
- 訊息 > 5000 字 → 依 LINE 限制切多則;單次 push 最多 5 則 message,超過分批

§8.2:L1 outbound sender,可用 `requests`;**不得 import streamlit**。
LINE API 為全球 endpoint,GitHub Actions(美國 IP)可直連,**不需**走 NAS proxy。
"""
from __future__ import annotations

import os
import time
from typing import Optional

import requests

_LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_MAX_TEXT_LEN = 5000        # LINE 單則 text message 字數上限
_MAX_MSGS_PER_PUSH = 5      # LINE push 單次最多 5 則 message
_DEFAULT_RETRY = 3
_TIMEOUT = 15


def _chunk_text(text: str, size: int = _MAX_TEXT_LEN) -> list:
    """把長文字切成 ≤ size 的片段,優先在換行處切(避免切在字中間)。"""
    if not text:
        return []
    chunks = []
    remaining = text
    while len(remaining) > size:
        cut = remaining.rfind("\n", 0, size)
        if cut <= 0:                      # 該窗口內無換行 → 硬切
            cut = size
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def push_line(
    text: str,
    *,
    token: Optional[str] = None,
    to: Optional[str] = None,
    retry: int = _DEFAULT_RETRY,
) -> int:
    """推一則(或多則)文字到 LINE。失敗重試,最終仍敗 → raise(§1 Fail Loud)。

    Parameters
    ----------
    text : str
        訊息內容。> 5000 字自動切多則(單次 push 最多 5 則,超過分批送)。
    token / to : str | None
        預設讀環境變數 `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`。
    retry : int
        單一 push 呼叫的重試次數(指數退避 2/4/8s)。

    Returns
    -------
    int
        實際送出的 message 則數(切段後)。

    Raises
    ------
    RuntimeError:缺 token/user id,或重試後仍失敗。
    ValueError:訊息為空(避免 LINE 400)。
    """
    token = token or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    to = to or os.environ.get("LINE_USER_ID")
    if not token or not to:
        raise RuntimeError(
            "LINE 推播缺 token/user id:請設 LINE_CHANNEL_ACCESS_TOKEN + LINE_USER_ID"
            "(GitHub Actions → Settings → Secrets)"
        )
    if not (text or "").strip():
        raise ValueError("push_line:訊息為空,拒推(避免 LINE 400)")

    chunks = _chunk_text(text)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    # LINE push 單次最多 5 則 → 分批
    for i in range(0, len(chunks), _MAX_MSGS_PER_PUSH):
        batch = chunks[i:i + _MAX_MSGS_PER_PUSH]
        body = {"to": to, "messages": [{"type": "text", "text": c} for c in batch]}
        _post_with_retry(headers, body, retry)
    return len(chunks)


def _post_with_retry(headers: dict, body: dict, retry: int) -> None:
    """POST 到 LINE,失敗指數退避重試;最終仍敗 → raise。"""
    last_err = None
    for attempt in range(1, max(1, retry) + 1):
        try:
            resp = requests.post(
                _LINE_PUSH_URL, headers=headers, json=body, timeout=_TIMEOUT
            )
            if resp.status_code == 200:
                return
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
        except Exception as e:                       # noqa: BLE001 網路例外皆重試
            last_err = f"{type(e).__name__}: {e}"
        if attempt < retry:
            time.sleep(2 ** attempt)                 # 2 / 4 / 8s 退避
    raise RuntimeError(f"LINE 推播失敗(重試 {retry} 次):{last_err}")
