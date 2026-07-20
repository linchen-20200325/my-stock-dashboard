"""src/data/notify/ — L1 outbound 推播 sender(LINE 等)。

morning_brief 早報用。與 L1 Data fetcher 同層(外部 I/O),但方向相反:
fetcher 是「抓進來」,notify 是「送出去」。§8.2:可用 requests,不得 import streamlit。
"""
from .line_push import push_line  # noqa: F401
