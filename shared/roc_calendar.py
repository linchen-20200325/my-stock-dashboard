"""shared/roc_calendar.py — 中華民國(ROC)曆 ↔ 西元(Gregorian)年換算 SSOT(L0)。

深層技術債藍圖 B3(SSOT-H2)。ROC 年換算的 magic number `1911` 原散落 8+ 處
(leading_indicators / macro_snapshot / data_loader / tw_stock_data_fetcher /
app_stock_fetchers / monthly_revenue_fetcher / scripts/update_fundamentals_snapshot)。
CLAUDE.md §3.3 反捏造要求 domain 常數走單一來源 —— 本檔即該 SSOT。

核心事實:**西元年 = 民國年 + 1911**。
民國元年(民國 1 年)= 西元 1912 年 → 位移 = 1912 − 1 = 1911。民國 0 年不存在。

純函式、無 I/O、可被全層 import(L0)。壞值不臆造:呼叫端自行決定 fail-loud(§1)。
本檔僅做算術換算,**不含格式解析**(各來源字串格式如 '11505' / '1150401' 不同,
仍由各 fetcher 自解,只把 ± 1911 這一步收攏至此)。
"""
from __future__ import annotations

# 民國 ↔ 西元 紀元位移。西元 = 民國 + ROC_EPOCH_OFFSET;民國 = 西元 − ROC_EPOCH_OFFSET。
ROC_EPOCH_OFFSET = 1911


def roc_to_gregorian_year(roc_year: int) -> int:
    """民國年 → 西元年。e.g. roc_to_gregorian_year(115) == 2026。"""
    return int(roc_year) + ROC_EPOCH_OFFSET


def gregorian_to_roc_year(greg_year: int) -> int:
    """西元年 → 民國年。e.g. gregorian_to_roc_year(2026) == 115。"""
    return int(greg_year) - ROC_EPOCH_OFFSET
