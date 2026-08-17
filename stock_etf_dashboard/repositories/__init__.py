"""L1 Repository layer — 外部資料抓取與儲存（yfinance / TWSE / Google Sheets）。

只能被 L2 services 呼叫；本層不得 import L2+。出口過 schema、蓋 provenance。
"""
