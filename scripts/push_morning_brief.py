#!/usr/bin/env python3
"""scripts/push_morning_brief.py — 每日股票早報 → LINE 推播 CLI(cron 入口)。

GitHub Actions `morning_push.yml` 呼叫。

- **v1 pilot**:只送「管線測試 + 時間戳」訊息,證明 LINE 推播接通(deps 僅 requests,
  不碰 src.services 的重 import 鏈)。內容誠實(狀態訊息,非假資料)。
- **下一步**:改呼 `src.services.morning_brief.build_brief()` —— 接總經紅綠燈 →
  個股/群組出場訊號 → AI 判讀摘要(屆時 workflow 補 pandas / gemini 等依賴)。

失敗 → 非 0 退出(Action 紅燈,對得上「今天沒收到」)。§1 Fail Loud。
env(GitHub Actions secrets):`LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`
"""
from __future__ import annotations

import datetime as _dt
import sys

_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))   # Asia/Taipei UTC+8(§4.5)


def build_pilot_message(now=None) -> str:
    """v1 pilot 訊息:時間戳 + 管線接通狀態(誠實,非假資料)。

    now 可注入(測試用),預設台灣現在時間。
    """
    now = now or _dt.datetime.now(_TW_TZ)
    ts = now.strftime("%Y-%m-%d (%a) %H:%M")
    return "\n".join([
        "📈 股票儀表板・每日早報",
        f"🕕 {ts} TW",
        "",
        "✅ 早報推播管線已接通(pilot v1)。",
        "下一步接:總經紅綠燈 → 個股/群組出場訊號 → AI 判讀摘要。",
    ])


def main() -> int:
    # push_line lazy import:只需 requests,避免 module load 就拉依賴
    try:
        from src.data.notify import push_line
    except Exception as e:                       # noqa: BLE001
        print(f"[morning_brief] import 失敗:{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    text = build_pilot_message()
    try:
        n = push_line(text)
        print(f"[morning_brief] ✅ 已推播 {n} 則")
        return 0
    except Exception as e:                        # noqa: BLE001
        print(f"[morning_brief] ❌ 推播失敗:{type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
