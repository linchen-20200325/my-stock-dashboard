# -*- coding: utf-8 -*-
"""tests/test_morning_push_pilot.py — morning_push pilot v1 訊息組裝守衛。

v1 只證明 LINE 推播管線接通,訊息為「時間戳 + 狀態」。守:
- 含儀表板標題 + 可解析時間戳(注入 now 可重現)
- 長度在單則 LINE 上限內
- import scripts.push_morning_brief 不需重依賴(push_line 為 lazy import)
"""
from __future__ import annotations

import datetime as _dt

from scripts.push_morning_brief import build_pilot_message


def test_pilot_message_structure():
    now = _dt.datetime(2026, 7, 20, 5, 50, tzinfo=_dt.timezone(_dt.timedelta(hours=8)))
    msg = build_pilot_message(now=now)
    assert "股票儀表板" in msg
    assert "2026-07-20" in msg and "05:50" in msg
    assert "管線已接通" in msg
    assert 0 < len(msg) < 5000            # 單則 LINE text 上限內


def test_default_now_does_not_crash():
    # 不注入 now → 用台灣現在時間,不可爆
    msg = build_pilot_message()
    assert "股票儀表板" in msg and "TW" in msg
