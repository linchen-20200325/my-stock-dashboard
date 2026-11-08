"""shared/monthly_revenue_month_key.py — 月營收『來源宣稱月份鍵』的驗證狀態 SSOT(L0,DEC-152 C4-D)。

背景:FinMind `TaiwanStockMonthRevenue` 提供 `revenue_year` / `revenue_month`,官方範例顯示 `date` 與營收所屬月份
可能不同(客戶 2026-11-08 裁示)。C4-D 把這兩欄原樣傳進全市場批次長表(來源有才帶,不由 date 推導補欄)。
但**沒有真實資料驗證過**這兩欄的語意(沙箱無 FinMind token、連不到 FinMind)前,不得讓它們使
『公告時點資格』變 True —— 否則全市場 STRONG(逐月加速)會在未經驗證下恢復。

本檔只放一個旗標,**不是**評分權重 / 門檻 / 封頂 / 排名例外。
"""
from __future__ import annotations

#: 全市場批次路徑(`_batch_finmind` → 候選池)帶進來的 revenue_year/revenue_month 是否已經『真實資料驗證』。
#: False ＝ NOT VERIFIED:契約 month_key_verified=False、target_date_eligible 維持 None,全市場 STRONG 維持 0 檔。
#: ⚠️ 翻成 True 的前提是有人用真實 FinMind 全市場回應核對過 (a) revenue_year/month 即營收所屬月、
#: (b) 與公告時點 SSOT 的關係,並經客戶(Decision Gate)裁示;不得為了讓 STRONG 出現而翻。
BATCH_SOURCE_MONTH_KEY_VERIFIED: bool = False
