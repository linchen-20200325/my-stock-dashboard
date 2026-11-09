# New UI2｜五頁 Old UI First 功能差異初審（2026-11-09；唯讀研究）
> 狀態：ChatGPT 獨立產品規劃／**候選**，不是正式 Design Decision、施工授權、實測結果或新增資料來源。驗證起點 main `f5e78e10672da2a4c22d880825241e502401c533`；Open PR 0。每次接手須先 LIVE GitHub Gate。本表不能把 2026-11-02 歷史 Capability Map 的「✅／❌」直接當成 2026-11-09 新 UI2 實況。

## 依據與版本差異
- 治理：`docs/governance/OLD_UI_FIRST_ADAPTATION_GATE_2026-11-08.md` 五步驟；現行五頁、Dark-only、頂部兩列導覽已核准，**不重設計導航**。
- 現行 UI2：`src/ui2/views/{market,target,hold,me,data}.py`、`src/services/ui2/{real_feed,data_page}.py`。Real-data Preview 目前只讀 TWII 收盤及嚴格 Regime 兩個事實；`data_page` 是 Capability 「尚未接線」空殼。View 不能直接 import 舊 UI/render 或資料 fetcher。
- 舊能力索引：`docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md` 及 `docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`，**時間較舊**、部分落點已被 DEC-128 取代，僅供待稽核候選。具體入口需重讀現行 code，非當日 source 可用性證明。

## 初審五頁（舊入口 → 新 UI2 現況 → 建議）
| 頁 | Old/Legacy 參考與功能 | 最新程式已核對的 UI2 限制 | 候選處置（未授權接線） | 優先級 |
|---|---|---|---|---|
| 📊 市場 | `src/ui/views/page_market.py`、`page_today.py`；市場位階、今日關鍵、16 燈、台股/國際趨勢、總經/風險研究 | `src/ui2/views/market.py` 有首屏行動、OneBrain Outlook **既有槽**、TWII **主圖誠實空槽**、核心卡；Real Feed 只有 TWII 末日收盤＋Regime，不能宣稱歷史趨勢圖/國際資料已接 | 保留首屏順序與已核准導航；先盤點有 canonical L3 的台股趨勢、國際市場與來源日期，再做可用資料/缺失矩陣；EPS×PE 大盤仍是 Research，禁止造數 | P1 |
| 🎯 標的 | `src/ui/views/page_target.py`、`_target_blocks.py`，選股/產業機會/候選池/單股資料；舊 Capability Map T01/T03/T09/T14/T16/T18 | `src/ui2/views/target.py` 已有市場精選/查一檔雙模式，**搜尋 CTA Preview disabled**，不可當實際可搜尋；歷史 Map 的 T11「無雙模式」已過期 | 先重用現有 canonical 檢索/初篩能力做唯讀 Evidence 契約研究；保留合法候選條件，未經授權不加 Sheet 寫入/新排名/估值公式 | P1 |
| 💼 持股 | `src/ui/views/page_hold.py`；資產 Sheet 唯讀、持倉/風險/策略/警示、80/20、ETF/股管理路徑（部分需寫） | `src/ui2/views/hold.py` 已有 W-11 版面、持股表與產業集中度誠實空槽、OneBrain 表示槽；**W-11 不授權實際持倉接線** | 先做權限與資產讀寫隔離 Gate，對照持股表欄位／Risk Cap Authority／空值；任何 OAuth/Sheet/CRUD 額外 Gate | P1（高風險） |
| 👤 我的 | `src/ui/views/page_me.py` 的 account／active Sheet 狀態；Legacy 的登入/Sheet/CRUD 路徑 | `src/ui2/views/me.py` 是 FAKE skeleton，⛔ 真 OAuth／Sheet，不能宣稱能登入／保存 | 先盤點現有 canonical Auth/Sheet 只讀能力與 security/scope，分離「已連線狀態」和「可編輯 CRUD」，後者需客戶 Gate | P2 |
| 🗂 資料 | 舊 `page_market` 指標來源/資料日及診斷入口；`docs/vnext/NEWUI2_P6_DATA_HEALTH_TEXT_WIREFRAME_2026-11-04.md` 的來源健康度研究 | `src/services/ui2/data_page.py` 固定「尚未提供」；無正式來源健康/分母/時間/Sheet | 優先設計 Data State（健康度）與 Capability（有無接線）雙軸；用 canonical metadata＋缺資料理由，**不可用 cron 時刻冒充觀測日**；新欄/分母須先 Data Contract Gate | P2 |

## 三方案（Old UI First §4）
| 方案 | 正確性/風險 | 速度/Token | 裁示 |
|---|---|---|---|
| A. 重用既有 canonical L3 + UI2 唯讀 Feed/VM | 優先；須驗證無副作用、PIT、資料/缺值契約 | 最快、最省 | **預設推薦**，可先做 P1 個案的唯讀資料契約盤點 |
| B. 舊能力保留，在 L3 新增 thin readonly adapter | 中風險；需來源與錯誤語意等價及獨立 QA | 中等 | 只在 A 無合格介面時 |
| C. 新 fetcher/API 或改造投資公式／動作 | 高風險；可能改 Source、費用、Schema、Risk Cap、PIT | 最慢/Token 高 | **未授權，不施工** |

## 下一個最小安全批
1. 針對 **📊 市場 + 🎯 標的**，非作者獨立盤點各 5～8 個舊能力的 actual caller → L3 → L1 → 來源/日期/缺值/PIT/權限 → 現行 UI2 VM，標示 KEEP / WRAP / PORT / LATER；不得依歷史 map 推斷已接線。
2. 針對 **💼 持股**，只做 Auth/Sheet/Risk Cap 與持股表 read-only 權限/欄位契約稽核（不執行 CRUD、不連新資料、不更動公式）。
3. 每頁產出一份可供使用者視覺判斷的 HTML 草稿**方案規格**（尚未要求生成 HTML 檔），Dark-only／mobile-first／五頁頂部兩列保留。新增分區/欄位/動線先送 Visual Gate，非核准不得寫 UI Code。

**反向提醒**：歷史 Map T11 的「雙模式未實作」、E01/E02 的「已承接」屬當時 Legacy New UI 實況，不能照抄到 New UI2；現行 UI2 雖有 target 雙模式，Google/Sheet 仍未接。相反地，舊圖/畫面具備計算不等於資料層已有可供 UI2 合法復用的 L3。缺值≠0，未驗≠PASS，Proxy≠正式，CI≠部署/來源實測。
