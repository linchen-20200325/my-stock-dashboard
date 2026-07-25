"""src/data/notify/chunk.py — 長訊息分塊(純函式,Telegram / LINE 共用)。

各推播平台單則有字數上限(Telegram 4096 / LINE text 5000)。超長依行切塊,
盡量在換行處斷;單行超長才硬切。§8.2:純函式,無 I/O。
"""
from __future__ import annotations


def split_chunks(text: str, limit: int) -> list[str]:
    """把長訊息依行切成 <= limit 的塊(盡量在換行處斷;單行超長才硬切)。"""
    if not text:
        return []
    chunks: list[str] = []
    cur = ""
    for line in text.split("\n"):
        while len(line) > limit:          # 單行本身超長 → 硬切
            chunks.append(line[:limit])
            line = line[limit:]
        _add = (cur + "\n" + line) if cur else line
        if len(_add) > limit:
            if cur:
                chunks.append(cur)
            cur = line
        else:
            cur = _add
    if cur:
        chunks.append(cur)
    return chunks
