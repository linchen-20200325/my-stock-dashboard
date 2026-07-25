"""src/data/notify — 外部推播 I/O(L1)。目前:Telegram Bot。

L1 唯一 I/O 點(HTTP POST 到 Telegram API),無 streamlit、無業務邏輯 / 門檻 / 組字
(組字在 L2 `src/compute/notify/`,編排在 `scripts/push_daily_signals.py`)。
"""
