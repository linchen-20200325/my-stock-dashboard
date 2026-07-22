"""shared/finmind_subject_aliases.py — 財報科目別名對照 SSOT(L0)。

深層技術債藍圖 B4(SSOT-H1,user 核准「保守 SSOT」)。財報科目(營業收入 / 毛利 /
淨利 / EPS …)在不同來源有不同欄名別名,原散落多檔各自維護。本檔集中「各來源分組」
的別名常數(**不強行 union** —— 各組來源不同,硬併可能改變 priority-match「先命中
哪個欄位」→ 財報數字走鐘),各 fetcher import 對應那組,零行為改變。

- `FIELD_ALIASES`:MOPS / 混合來源,**priority-ordered**(`tw_stock_data_fetcher._g`
  依序取第一個命中的欄名),涵蓋 BS / IS / CF 全表。
- `FINMIND_FS_*_KEYS`:FinMind `TaiwanStockFinancialStatements` SDK 專屬欄碼
  (含 GrossProfitLoss / NetRevenue / 營業毛利（毛損）等 FinMind 特有別名)。

純常數、無 I/O、可被全層 import(L0)。新增別名一律改本檔,勿在 fetcher 內另立。
"""
from __future__ import annotations

# ─────────────────────────────────────────────
# MOPS / 混合來源 —— priority-ordered(第一個命中即取)。
# 原定義於 src/data/stock/tw_stock_data_fetcher.py,B4 搬入,行為不變。
# ─────────────────────────────────────────────
FIELD_ALIASES: dict[str, list[str]] = {
    # Balance Sheet
    "現金及約當現金": ["現金及約當現金", "Cash and Cash Equivalents", "現金", "現金及銀行存款"],
    "應收帳款": [
        "應收帳款淨額", "應收票據淨額", "應收帳款－關係人淨額",
        "應收票據及應收帳款", "應收帳款", "AccountsReceivable",
        "合約資產", "工程應收款", "應收帳款及合約資產",
    ],
    "存貨": ["存貨", "Inventory", "存貨淨額", "商品存貨"],
    "流動資產": ["流動資產", "流動資產合計", "CurrentAssets", "總流動資產"],
    "非流動資產": ["非流動資產", "非流動資產合計", "NonCurrentAssets"],
    "總資產": ["總資產", "資產合計", "資產總計", "資產總額", "TotalAssets"],
    "流動負債": ["流動負債", "流動負債合計", "CurrentLiabilities", "總流動負債"],
    "非流動負債": ["非流動負債", "非流動負債合計", "NonCurrentLiabilities"],
    "總負債": ["總負債", "負債合計", "負債總計", "負債總額", "TotalLiabilities"],
    "股東權益": ["股東權益合計", "權益合計", "TotalEquity", "股東權益總額"],
    "保留盈餘": ["保留盈餘", "RetainedEarnings", "累積盈虧", "未分配盈餘"],
    "合約負債": ["合約負債", "ContractLiabilities", "預收款項", "合約負債-流動"],
    # Income Statement
    "營業收入": ["營業收入", "Revenue", "營業收入淨額", "收入合計"],
    "營業成本": ["營業成本", "CostOfRevenue", "銷售成本", "製造成本"],
    "毛利": ["毛利", "GrossProfit", "毛利額"],
    "營業費用": ["營業費用", "OperatingExpenses", "銷管研費用"],
    "營業利益": ["營業利益", "OperatingIncome", "營業利潤"],
    "稅前淨利": ["稅前淨利", "IncomeBefore Tax", "稅前損益"],
    "淨利": ["淨利", "NetIncome", "本期淨利", "稅後淨利"],
    "EPS": ["EPS", "BasicEPS", "每股盈餘", "稀釋每股盈餘"],
    # Cash Flow Statement
    "營業現金流": ["營業活動現金流量", "OCF", "來自營業活動之現金流量", "OperatingCashFlow"],
    "投資現金流": ["投資活動現金流量", "InvestingCashFlow", "用於投資活動之現金流量"],
    "融資現金流": ["籌資活動現金流量", "FinancingCashFlow", "來自籌資活動之現金流量"],
    "資本支出": [
        "資本支出", "CapEx", "AcquisitionOfPropertyPlantAndEquipment",
        "取得不動產、廠房及設備", "購置不動產、廠房及設備",
    ],
    "股利支付": ["支付現金股利", "DividendsPaid", "支付股利"],
}

# ─────────────────────────────────────────────
# FinMind TaiwanStockFinancialStatements SDK 專屬欄碼。
# 原定義於 src/data/stock/quarterly_financials_fetcher.py,B4 搬入,行為不變。
# ─────────────────────────────────────────────
FINMIND_FS_REVENUE_KEYS = ("Revenue", "營業收入合計", "營業收入", "NetRevenue",
                           "OperatingRevenue", "營業總收入", "銷貨收入淨額", "收入合計")
FINMIND_FS_GROSS_KEYS = ("GrossProfit", "GrossProfitLoss", "營業毛利（毛損）",
                         "營業毛利", "營業毛利（毛損）淨額", "營業毛利(毛損)")
FINMIND_FS_COGS_KEYS = ("CostOfGoodsSold", "營業成本", "銷售成本", "OperatingCosts", "營業總成本")
FINMIND_FS_INV_KEYS = ("Inventories", "InventoriesNet", "存貨", "存貨淨額", "商品存貨")
