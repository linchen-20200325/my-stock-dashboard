"""src/data/notify/dispatch.py — 推播管道 dispatcher(L1)。

依環境變數 `NOTIFY_CHANNEL`(`line` | `telegram`;預設 `line`)選送信管道 → 呼叫對應
send 函式。兩個真實管道(user 曾 Telegram、後改 LINE),故用薄 dispatcher 切換
(非過度抽象:一個 env 變數即可換,不重造 send 邏輯)。

§1 fail-loud:未知 channel → ValueError;各 channel 自身缺 token → 由該 channel raise。
§8.2 L1:無業務邏輯,只按 env 分派。
"""
from __future__ import annotations

import os


def send_notification(text, *, channel: str | None = None) -> int:
    """依 NOTIFY_CHANNEL 送出推播。回實際送出的訊息塊/物件數。"""
    _ch = (channel or os.environ.get("NOTIFY_CHANNEL", "line")).strip().lower()
    if _ch == "line":
        from src.data.notify.line_notify import send_line_message
        return send_line_message(text)
    if _ch == "telegram":
        from src.data.notify.telegram_notify import send_telegram_message
        return send_telegram_message(text)
    raise ValueError(f"未知推播管道 NOTIFY_CHANNEL={_ch!r}(支援:line / telegram)")
