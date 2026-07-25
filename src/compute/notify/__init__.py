"""src/compute/notify — 每日推播用純函式(L2):技術面快照 + 訊息組字。

無 I/O、無 streamlit、無 session_state(§8.2 L2)。推播的外部發送(Telegram HTTP)
在 L1 `src/data/notify/`,編排在 `scripts/push_daily_signals.py`(orchestrator)。
"""
