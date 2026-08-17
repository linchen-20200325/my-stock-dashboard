"""L2 Service layer — 純運算/業務編排（評分、ETF 穿透、池狀態機）。

只 import L0/L1；本層不得 import L3 UI。狀態機依賴 PoolStore 介面（依賴反轉）。
"""
