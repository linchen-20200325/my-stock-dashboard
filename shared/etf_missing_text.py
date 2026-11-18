"""shared/etf_missing_text.py — ETF「資料缺失」顯示句單一來源（L0，零 I/O、零 streamlit）。

背景（A-likely-private-unknown，GPT 核准 plan C+A 保守版）：
  程式內沒有任何可靠的「正向」身分證據（沒有私募名單、沒有投信揭露旗標），
  ⇒ 不得由「AUM／費用率／NAV 三項都缺」推斷成私募（缺值 ≠ 私募）。
  ETF 身分在本頁一律是「未知」。ETF 單檔頁（etf_tab_single）與資料診斷頁（health_inspector）
  共用本檔的句子，避免兩頁各寫一份而漂移。
"""
from __future__ import annotations

#: ETF 單檔頁「內扣費用率」N/A 的 tooltip，與資料診斷頁無關。
ETF_EXPENSE_MISSING_TEXT = '目前沒有可用的 ETF 費用率資料，暫時無法顯示。'
#: AUM 缺值句（ETF 單檔頁 tooltip＋資料診斷頁 AUM 列共用）。
ETF_AUM_MISSING_TEXT = '目前沒有可用 ETF 規模資料，暫時無法顯示。'
#: NAV 有取到但被折溢價守門員判過期（stale_nav）且無可用值：不得說成網路失敗、也不得套今天日期。
ETF_NAV_STALE_TEXT = '淨值資料已過期，暫時無法顯示。'
#: 身分說明：僅在「非海外、非主動式、AUM＋費用率＋NAV 全缺」時附在 AUM 列後。
ETF_IDENTITY_UNKNOWN_NOTE = 'ETF 類型無法確認；資料未取得不代表私募。'
#: NAV 有值但 payload 內沒有任何可信的 NAV 日期：不得套今天日期、不得判綠燈（只能說日期無法確認）。
ETF_NAV_DATE_UNKNOWN_TEXT = 'NAV 已取得，但資料日期無法確認，暫不判定新鮮度。'
#: NAV 資料日期在未來（晚於今日）：日期不可信，不得顯示「今天」或任何已驗證新鮮度（fail-closed，#1217 NOTE-3）。
ETF_NAV_DATE_FUTURE_TEXT = 'NAV 資料日期不可信，暫不判定新鮮度。'
