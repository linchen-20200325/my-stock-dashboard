"""v18.214 K7：health_grade 分界閾值 SSOT 常數模組。

Phase 1 audit 找到 health 分級閾值散落多處（scoring_helpers/tab_helpers/tab_stock 等），
且 STATE.md 列為 K7 待辦項。本模組僅收「個股健康度評分 0~100 的 A/B/C 三級分界」，
不收市場曝險（macro_state_locker）、廣度評分（tab_macro）、ETF 星評（etf_quality）等
獨立評分系統的閾值——那些屬不同維度。

設計：純常數模組，零 import 依賴；caller 用
`from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN`。

對外 API：
- HEALTH_GRADE_A_MIN = 80  優質優良（A 級）下界
- HEALTH_GRADE_B_MIN = 50  震盪盤整（B 級）下界；< B 為弱勢危險（C 級）

閾值來源：test_scoring_helpers.py 11 項測試背書（80/50 為 v18 spec 標準）。
"""
from __future__ import annotations

HEALTH_GRADE_A_MIN: int = 80  # 優質優良（A）下界
HEALTH_GRADE_B_MIN: int = 50  # 震盪盤整（B）下界；低於此為弱勢危險（C）

# v18.326 PR-D：個股 tab 健康度「標籤中間級」下界。
# ⚠️ 分歧旗標：tab_stock 標籤用 60 為中間級，但同檔評語/分級用 HEALTH_GRADE_B_MIN=50，
#    同一 health2 在 50~60 間「標籤=弱勢、評語=可分批布局」不一致（SPEC §15 旗標待統一）。
#    本版各自具名保行為，待 user 決定是否對齊 50。原 tab_stock.py:1137 inline。
HEALTH_LABEL_MID_MIN: int = 60
