# Final UI Capability Map：Old UI Capability → New UI Location（2026-11-02）

- **狀態**：**客戶拍板版**（客戶 2026-11-02 裁示 Q1=A／Q2=A／Q3=A；嚴重度定義仍為 AI 總管暫定）（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）；原文刪除線保留）；~~**客戶指示 A 生效；Freeze 內容待客戶拍板（含 Q1～Q3）**~~（Final UI Contract Freeze 配套，隨 Freeze 送拍板；嚴重度定義為 AI 總管暫定；契約本體 `docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md`，取代關係 `docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md`，決策 `docs/DECISIONS.md` DEC-122）。
- **日期**：2026-11-02　**基準**：`origin/main`＝`ce8422d`（撰寫組 `git fetch` 實查；cron 會推進 main，以當下 `git fetch` 為準）。
- **客戶依據**：Old UI Capability → New UI Location Map〔客戶裁示 A 清單〕；「不得靜默移除的舊能力」重新盤點：大盤判斷、台股趨勢、國際趨勢、EPS × PE 研究、macro、industry、chip、valuation、risk、portfolio、candidate、source audit〔客戶 §42〕；Stage J 第 6 條「old/new capability map 無 critical gap」〔客戶 Stage J〕。
- **方法**：invB 調查（2026-11-02，單組；**讀程式為主**：`app.py` 路由、`shared/ia_nav4.py`、`src/ui/views/*`、`src/ui_v2/compact.py`、`src/services/*`、`src/compute/etf/dividend_station.py`、`shared/decision_digest*`；文件為輔：`docs/vnext/NEWUI_D25_B_COVERAGE_2026-10-27.md` 70 列 CV-xx、Phase 1 baseline、P4-3／P5-3 Gate 報告）。本檔把 invB 的 85 列表正式化；**列內容逐列轉錄自 invB**，撰寫組只做結構化與機械計數，未逐列重驗。
- **與既有能力守恆文件的關係**：Presentation Contract §17 能力守恆表、`NEWUI_D25_B_COVERAGE_2026-10-27.md`、`INTERACTION_COVERAGE_MATRIX_2026-10-25.md`、Phase 4／5 線框 §3 **繼續有效**；本檔是 Final UI 主線的**合併版落點表**，衝突時以「新 UI 現況」較新的一方為準（本檔 2026-11-02 讀碼）。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：單組產出、**未經第二組獨立複驗**；所有「沒有／只有／0 caller／全部」類全稱句於該列註明驗證方法，未註明者視為未窮舉；新頁現況以讀碼為準、**未跑 runtime**；本表 85 列為彙總（M15、H11、T26 等合併了子能力）。獨立複驗列 BACKLOG `FUI-FREEZE-SECOND-AUDIT`。

---

## §1 嚴重度定義（**AI 總管暫定**，非客戶核准；客戶可推翻）

- **critical**：Final 完成定義硬項／§51 invariant 所依賴、但目前**無正式 deterministic 來源或無任何承接**；或舊 UI 獨有的投資判斷能力在新 UI 無承接位置（移除即消失）。**任一 critical 未解，Stage J Removal Gate 第 6 條不成立。**
- **major**：Final 指示明列的 L1／L2 能力缺或只部分；或舊 UI 獨有的研究／輔助能力。
- **minor**：便利、文案、已有替代、或刻意不搬的副作用控制項。
- **—**：已承接、無 gap。**n/a**：非能力遺失（例：大盤 EPS×PE 舊 UI 本來就沒有，維持 Research）。
- 「舊獨有」欄 `●`＝目前**只有舊 UI**（`?legacy=1`）有＝Old UI Removal Gate 的阻擋項。
- **承接程度**：✅ 已承接｜部分｜❌ 未承接｜替代（以新設計取代，非遺失）｜空位（Research）。

## §2 統計（機械計數：以 `| [MTHE]\d\d ` 開頭的表列逐列解析 Gap 欄與舊獨有欄；量測日 2026-11-02）

| 頁 | 列數 |
|---|---|
| 市場 M | 22 |
| 標的 T | 30 |
| 持股 H | 16 |
| 我的／Audit E | 17 |
| **合計** | **85** |

| 嚴重度 | 列數 |
|---|---|
| critical | **7** |
| major | 38 |
| minor | 28 |
| —（無 gap） | 11 |
| n/a | 1 |

- 舊獨有 `●`：**41 列**。
- ⇒ **「old/new capability map 無 critical gap」（Stage J 第 6 條）目前不成立。**

## §3 Critical 7 列（Stage J 阻擋項；逐列處置）

| ID | 能力 | 為什麼是 critical | 承接 Stage | 解法前提 |
|---|---|---|---|---|
| **M02** | Risk Cap／建議總持股水位（市場端） | 數值顯示未核准（DEC-081 Q2-2／`RC-VISIBILITY`）；**市場頁藏數字、持股頁 ⑤ 外露 `range_text`**＝跨頁不一致（讀碼，未實機） | B（市場 L1）、D、H | **Q1**；RC Gate |
| **M03** | System Action State（市場層） | 無正式來源（grep `system_action\|SystemAction\|SYSTEM_ACTION` 於 src／shared 非測試檔 0 命中） | F（System Action 層）→ B 掛載 | Stage F Pipeline「Risk Cap → System Action」 |
| **T16** | 歷史估值區間（殖利率／PE／PB 河流圖） | 舊獨有；新 UI 無；客戶 §16 Historical 明列 | C | 純歷史呈現；357 倍數帶屬 HI-3 未核准 → ⛔ 情境線 |
| **T21** | 個股買賣語意（停利停損、目標價、部位大小、即時操作建議、統一判決、三維出場） | 舊獨有判斷；新 UI 刻意不承接（HI-3 未核准；`RESEARCH_ONLY_NOTE`）；§18 Ad-hoc 不是 action engine | J（保留或正式退場＝客戶 Gate，屆時送題） | deterministic action contract 或客戶裁示退場 |
| **H01** | Portfolio Risk Cap＋目前曝險 vs Cap | 無曝險資料（Sheet 表頭無現金／總資產；單組 grep）；無封鎖規則 | D | **Q1** |
| **H02** | System Action（客戶五詞） | 現行 ETF 七分支＋個股四級，無「減碼 1/2」「全出」；無 Risk Cap 封鎖 | D（＋F） | **Q2**；DEC-053 |
| **E08** | Decision Digest Viewer | builder／summary **0 production caller**（grep `decision_digest` import，除自身模組與 `shared/strategy_class_schema` 外 0 命中） | E（殼）→ F（真資料） | Stage F Headless Digest |


### §3.1 客戶裁示 Q1～Q3 後的落點更新（2026-11-02；append-only，上表與 §4 原列一字未改；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示））

| ID | 依據 | 更新後 Final 落點與說明 | critical 是否解除 |
|---|---|---|---|
| **M02** Risk Cap／建議總持股水位 | Q1=A | 📊 市場 L1（手機第一屏必含，Q3=A）：**只凍結規則形狀**；數值仍隱藏、`⬜ 尚未核准／無法判定`；💼 持股頁卡⑤已核准區間（DEC-051／PQ-C6-3）**維持**；兩頁統一、數值啟用、曝險分母、現金／總資產來源 → `FUI-RC-NUMERIC-GATE`（另開正式 Decision Gate） | **否**（待 RC Gate） |
| **M03** System Action State（市場層） | 架構鏈＋invariant 3 | 正式來源＝架構鏈中的 **System Action State** 層（Risk Cap／Hard Constraints 下游、Digest 上游）；Stage F 建層，Stage B 先以 `⬜ 尚未提供` 呈現 | **否**（待 Stage F） |
| **M04** 是否需行動 | Q3=A | 📊 市場**手機第一屏必含**（不用滑）；判不出 ⛔ 寫成「今日無需調整」（Q2-4 同精神） | —（原 minor） |
| **M07** 主要風險 | Q3=A | L1；手機**緊接第一屏之後**、⛔ 被 L2／L3 插隊 | —（原 minor） |
| **M19** 一鍵更新 | Q3=A | 主 Update CTA＝手機第一屏必含 | — |
| **H01** Portfolio Risk Cap＋目前曝險 vs Cap | Q1=A | 💼 持股 L1：曝險或有效上限任一不可得 → `⬜ 無法判定`；⛔ 發明分母／現金／總資產／替代值；超限＝`🔴 Risk Cap 超限 · 禁止新增曝險`（數值啟用後）；`⬜` 時加碼 ⛔ 被當成允許 | **否**（待 RC Gate） |
| **H02** System Action（客戶五詞） | Q2=A | 💼 持股 L1「今日需處理」：沿用既有分支原名（ETF 七分支、個股 `swap_level`）；「加／留／換／減」只作呈現分組；只有無正式動作時才「今日無需調整」；資料不足／未評估 ⛔ 算無需調整；「減碼 1/2」「全出」⛔ 映射或產生 → `FUI-PROPORTIONAL-ACTION-RULES` | **部分**：第一版承接方式已定；比例 Action 仍缺正式規則（客戶 Q2-6），critical 維持至 Stage D 實作＋獨立 QA |
| **H03** 今日需處理 | Q2=A | 同 H02；「沒事 vs 判不出」分開（Q2-3、Q2-4） | — |
| **E08** Decision Digest Viewer | invariant 6 | Viewer 顯示**完整 Digest**；OneBrain 亦讀完整 Digest，⛔ 只讀 Top-N／摘要 | **否**（待 Stage F） |

- ⇒ 裁示後 critical 仍為 **7 列**（M02、M03、T16、T21、H01、H02、E08；H02 部分承接）；**Stage J 第 6 條仍不成立**。critical 的解除只能由實作合併＋獨立 QA 證據或客戶裁示達成（附錄 D 第 2 條）。

## §4 能力清單表（Old → New → Final 落點）

**落點縮寫**：市＝📊 市場｜標精＝🎯 標的·市場精選｜標查＝🎯 標的·即時查一檔｜持＝💼 持股｜我設＝👤 我的·設定｜我A＝👤 我的·Audit｜L1／L2／L3＝層級。
**欄位**：ID｜舊能力｜舊位置（檔＋符號）｜新 UI 現況（檔＋符號）｜**承接程度**｜**Final 新落點**｜**Gap 嚴重度**｜舊獨有｜證據等級／備註。`CV-nn`＝`NEWUI_D25_B_COVERAGE_2026-10-27.md` 列號（2026-10-27 基準，「新 UI 現況」欄以 2026-11-02 讀碼覆寫）。
### §4.A 市場（§42：大盤判斷、台股趨勢、國際趨勢、macro、risk、EPS×PE 大盤）

| ID | 舊能力 | 舊位置（檔＋符號） | 新 UI 現況（檔＋符號） | 承接 | Final 建議落點 | Gap | 舊獨有 | 證據等級／備註 |
|---|---|---|---|---|---|---|---|---|
| M01 | **大盤判斷**（紅綠燈多空＋綜合結論句；CV-02） | `src/ui/tabs/macro/section_traffic_light.py`；`app.py::_gl_slot` 置底條 | `page_market.render_page_market` → `blocks.render_core_tiles`（市場位階 tile，來自 `page_today.build_verdict_tiles`）＋今日結論 `shared/market_conclusion.build_market_conclusion` | 部分 | 市 L1「Regime」 | major | — | FACT。紅綠燈 label／action 刻意不帶入（DEC-081 Q4=C）；新頁用字「市場位階」≠ 客戶 §39「Regime」統一用語 |
| M02 | **Risk Cap／建議總持股水位**（CV-06／08） | `src/services/macro_state_locker.py::calculate_system_state`（曝險上限 30/20/40 硬否決）→ `risk_cap_apply` 寫 `risk_cap_state.json` → `allocation_service.get_allocation` 取最低 | 市：`_market_blocks.WATER_VALUE`＝「⬜ 尚未核准／無法判定」，卡面不顯示數字；原出手區間（含 `risk_cap.v2`）收在「🔍 查看依據」。持：`page_hold.build_position_cap_card` **有上限時卡面直接顯示 `range_text`** | 部分 | 市 L1＋持 L1（同一來源） | **critical** | — | FACT。`RC-VISIBILITY` 未裁示；**同一數字市場頁藏、持股頁 ⑤ 外露**＝Stage H 跨頁不一致（INFERENCE：依讀碼，未實機） |
| M03 | **System Action State（市場層）** | 無正式名稱的狀態；最接近：舊「今日作戰室 唯一行動建議」`src/ui/tabs/tab_today.py::build_today_blocks`／`macro/section_warroom.py`、`market_strategy` 的 `exposure_pct` | 無 | ❌ | 市 L1 | **critical** | ● | FACT（grep `system_action\|SystemAction\|SYSTEM_ACTION` 於 src/shared 非測試檔 0 命中）|
| M04 | 今日需處理／關鍵警示（CV-05） | `page_today._load_key_alerts`（舊今天頁）、總經頁首橫幅 | `blocks.render_alerts_block`（⚡ 需要處理）；手機依 DEC-118 例外 | ✅ | 市 L1「是否需行動」 | minor | — | FACT |
| M05 | 今日作戰室：唯一行動、5 分鐘清單、**月虧損停機 7 天**（CV-09） | `tab_today.build_today_blocks`、`MONTHLY_LOSS_HALT_*` | 無 | ❌ | 持 L1（若納入 System Action）或維持舊 | major | ● | FACT（引 CV-09；本輪未重讀 tab_today）|
| M06 | 指標危險度＋16 盞燈（CV-04） | `section_overview`、🚦 總經 v2 | `page_market` expander「指標明細（16 項）」：`today.build_indicator_tiles` | ✅ | 市 L2 | minor | — | FACT |
| M07 | 主要風險 3–5 項（圖 D） | （舊無） | `blocks.render_chart_d`；「是否惡化：⬜ 尚未定義」 | 部分 | 市 L1/L2 | minor | — | FACT |
| M08 | **核心指標卡**（台股、VIX、US10Y、利差、DXY、PMI／景氣；value＋state＋as_of＋source） | 舊：散在 `section_mid／long／short` 與 sparkline（`render/macro_ui_components.sparkline`） | **L1 無指標卡**；VIX 等只在 16 燈（L2）與「總經／景氣（原始資料）」L3 表（`page_market` 的 `X7_FIELDS` 含 VIX 值／資料日／來源）；頁面明說「逐項資料日：尚未提供（現行契約沒有逐指標的資料日欄位）」`page_market.AS_OF_NOT_PROVIDED` | 部分 | 市 L1（精簡卡）＋L2 | major | — | FACT。§7「不要共用假的全域更新時間」：現行只有「按更新時間」＋加權指數資料日 |
| M09 | **台股趨勢**（CV-07） | 舊無正式定義；`section_short` 廣度、紅綠燈 | `blocks.render_chart_a`：加權收盤＋MA5/60/120/200「最新值水平參考線」；結論固定「⬜ 尚未定義」 | 部分 | 市 L1 主圖 | major | — | FACT。§8 要「正式趨勢線／均線、Regime annotation」：均線非歷史曲線（`CHART_A_MA_NOTE`）、無 Regime 標註；正式定義 `VN1-MT-TREND-DEF` blocked-on-customer |
| M10 | **國際趨勢** | `section_long`（國際列）、指南針 | `blocks.render_chart_b`：small multiples `INTL_GROUPS`＝DJI／IXIC／SOX／US10Y／DXY；結論「⬜ 尚未定義」 | 部分（圖✅、結論未定義） | 市 L1/L2 | minor | — | FACT。§8 小倍數清單已對齊 |
| M11 | Volatility 圖（VIX＋正式門檻帶） | 舊：VIX 在 sparkline／燈 | 無 VIX 圖 | ❌ | 市 L2 | major | — | FACT（`_market_blocks` 的 `render_chart_*` 只有 a/b/c/d；VIX 只出現在 `page_market` 原始資料欄定義）|
| M12 | Macro mini charts（PMI、景氣、M1B/M2、CPI…；CV-13） | `section_mid`／`section_long` 圖與 sparkline | 只有 L3 原始表 | 部分 | 市 L2 | major | ●（圖） | FACT（新頁無 macro 圖元件）|
| M13 | 景氣拐點六大面向、CPI×Fed 雙頂回落、總經拼圖（CV-11／13） | `section_state`、`section_long_term` | `page_market` 只有 caption 指回舊版 | ❌ | 市 L2/L3 | major | ● | FACT（caption「景氣拐點六大面向本批未接到本頁」）|
| M14 | 市場廣度／ADL（CV-12） | `section_short` | L3「台股盤勢（原始資料）」（ADL 為推估） | 部分 | 市 L2 | minor | — | FACT（引 CV-12） |
| M15 | **大盤籌碼**（法人、融資、先行；外資連買、熱錢、融券、韭菜；CV-14／17） | `section_chips`、`tabs/hot_money.py` | L3「籌碼（原始資料）」`page_market._render_x8` | 部分 | 市 L2 | major | ●（熱錢／外資連買等） | FACT（引 CV-14；本輪未逐項重驗）|
| M16 | 風險雷達 9 項、攻擊發動判定、VIX 否決結論、策略 1/3 矩陣、跨桶五維度（CV-10／15／17） | `section_mid`、`section_cross_ai`、`compute/risk/risk_radar.py` | 無（VIX 否決已內生於 `allocation_service._derive_intrinsic_caps`） | ❌ | 市 L2/L3 或客戶裁示退場 | major | ● | FACT（CV-15 刻意不帶入：同名不同義）|
| M17 | 總經指南針＋「抓取最新羅盤」（CV-18） | `src/ui/render/app_render.py::render_macro_compass` | 新模式刻意不畫 | ❌ | 市 L2 或退場 | minor | ● | FACT |
| M18 | News AI 總裁決＋新聞掃描（CV-16） | `macro/section_news_ai.py`（寫 `macro_state.json`） | 無 | ❌ | OneBrain（Stage G，只讀 Digest）；新聞來源需另議 | major | ● | FACT |
| M19 | 一鍵更新今日戰情（CV-01） | `page_today._render_update_form` | `blocks.render_update_cta`（頁首主 CTA） | ✅ | 市 L1 refresh | — | — | FACT |
| M20 | **大盤 EPS×PE 模型**（§43） | **舊 UI 不存在**（grep `本益比` 於 macro sections 只有文案句） | `blocks.render_chart_c`：「圖C 💰 大盤合理區間｜研究框架，未啟用」，不畫任何圖 | 空位（Research） | 市 L2 Research 槽（保持 Research） | n/a（非能力遺失） | — | FACT。BACKLOG `VN1-MT-VALUATION`：大盤 EPS／PE／forward EPS 不存在 |
| M21 | 總經 v2 密度／搜尋／分類（CV-19） | `tabs/tab_macro_v2.py` | 無 | ❌ | 退場或市 L3 | minor | ● | FACT |
| M22 | 全域置底常駐條（多空＋建議持股；CV-67） | `app.py::_gl_slot` | 刻意不畫（新模式讀不到 `warroom_summary` 會說假話） | 替代 | 市 L1 取代 | minor | ● | FACT |

### §4.B 標的（§42：EPS×PE 研究、industry、chip、valuation、candidate）

| ID | 舊能力 | 舊位置 | 新 UI 現況 | 承接 | Final 落點 | Gap | 舊獨有 | 證據／備註 |
|---|---|---|---|---|---|---|---|---|
| T01 | **產業機會**（熱力圖、板塊資金泡泡圖；CV-20／21） | 🗺️ `sector_heatmap`（市場／區間切換＋排行＋AI）、🌊 `tab_sector_flow` | `_target_blocks.render_zone_industry`：產業 Top 5 橫條（`ZONE1_RANK_FIELD="x_yi"` 近 5 日法人淨流入，DEC-121 Q1=A）＋「查看全部」6 欄表；熱力圖／泡泡圖在 expander；**無市場／區間切換**（`HEATMAP_SWITCH_PLAIN`） | 部分 | 標精 L1 | minor | ●（切換、熱力圖 AI） | FACT |
| T02 | **產業趨勢**（基本面成長／相對強弱／估值維度） | 舊無正式 | 6 欄表內「⬜ 尚未建置」（`ZONE1_MISSING_DIMS`）；「產業趨勢為研究中，尚未定義」 | ❌（定義未核准） | 標精 L2 | major | — | FACT。RS-1 研究報告存在（`NEWUI_D25_RS1_*`），未 production |
| T03 | **候選標的 Top N＋完整清單＋CSV**（CV-24） | `app.py` 選股網結果表 | `render_zone_candidates`：Top 10 純顯示切片（`CANDIDATE_TOP_N=10`）＋「查看全部」expander＋💾 CSV；請求參數 `DEFAULT_TOP_N=50` 不變 | ✅ | 標精 L1 | minor | — | FACT。§11「完整 universe 不可丟失」：見 T04 |
| T04 | 基本面初篩逐檔明細＋涵蓋率警示（CV-22） | `tab_stock_picker.render_prescreen_panel` | 只有條件說明＋存活池檔數（CV-22 判讀） | 部分 | 標精 L2 | major | ● | INFERENCE（引 CV-22；本輪未重讀新版是否已加逐檔表）。⚠️ 「完整 candidate universe」＝存活池；排名上限 50（20／50／100）以外的存活股新 UI 無法逐檔看 |
| T05 | 選股網 5 因子勾選＋開始選股（CV-23） | `app.py` 選股網區塊（V-APP-1） | 「選股條件」expander（預設收合，DEC-121 Q2=B）＋一行摘要 | ✅ | 標精 L2 | — | — | FACT |
| T06 | **➕ 加入觀察清單（寫 Sheet）**（CV-25） | `app.py` 選股網 → `src/services/watchlist_service.add_picks_to_watchlist` → L1 `gsheet_portfolio.add_to_stock_watchlist`；另 `tabs/portfolio_manager.py` 用 `save_stock_watchlist` | 無；`_target_blocks.UNCOVERED_ITEMS` 自陳「會寫入您的 Google Sheet，新版尚未接上」 | ❌ | 標查 CTA（§13：未核准則 disabled／not available） | major（＋需裁示） | ● | FACT。⚠️ `watchlist_service` 經 L1 私有符號 `_get_active_stock_sheet_id` 取 sheet（跨檔 private，V-PICKER-PRIV-1 同類）；新 UI 寫入面屬 HI-5 未核准 |
| T07 | 🧊 凍結前 20 名＋📊 前進式驗證對帳（CV-26） | `app.py` → `services/forward_test_service`；cron `update_forward_test.yml` 每月自動凍結 | 無（UNCOVERED_ITEMS 列出） | ❌ | 我A（唯讀對帳）；凍結維持 cron | major | ● | FACT。寫 `data_cache/forward_test/picks.parquet`（不可重建） |
| T08 | 全台股跨季趨勢排行＋CSV（CV-27） | `fundamental_screener_service.get_cross_quarter_trends` | 無（UNCOVERED_ITEMS） | ❌ | 標精 L3 | minor | ● | FACT |
| T09 | 單檔查詢（代碼） | `tab_stock` `text_input('個股代碼')` | `B.render_search_form`（代碼＋進階選項） | ✅ | 標查 L1 | — | — | FACT |
| T10 | **名稱搜尋**（§12） | **舊也沒有**（`tab_stock` 只收代碼） | 無；UNCOVERED_ITEMS「目前只能輸入代碼」 | ❌（新能力） | 標查 L1 | major | — | FACT。`src/config/stock_names.py::get_stock_name` 僅 code→name；反查屬新功能 |
| T11 | **雙模式切換**（§10） | — | 無；`page_target.render_page_target` 單頁直排：搜尋→AI→第一區→第二區→第三區→進階 | ❌ | 標 頂部 mode | major | — | FACT。DEC-107 1A 核准的是單頁順序 ⇒ **與 §10 有 supersede 關係**（需 Freeze 記錄） |
| T12 | **單檔 Header＋6 維 Snapshot**（§15） | 舊：判決三卡（健康度／357／籌碼） | `_target_blocks` 第三區：判型 chip＋3 張摘要 tile（`SUMMARY_HEALTH_LABEL`／`SUMMARY_VALUATION_LABEL`／`SUMMARY_CHIPS_LABEL`）＋命中／缺漏兩顆計數 chip | 部分（3/6：無趨勢、產業、市場環境） | 標查 L1 | major | — | FACT |
| T13 | **Primary Price Chart（K 線＋均線）**（CV-28／29） | `stock_sections/section_kline_chart.py` | 灰色 placeholder「K 線新版尚未接上」（`SINGLE_CHART_REASON`）；MA 勾選「僅顯示」 | ❌ | 標查 L1 | major | ● | FACT |
| T14 | **Fundamental**：財報體檢、財報領先、D2 先行、龍頭預警、月營收（CV-29／32） | `stock_sections/section_health_score／financial_leading／d2_leading／dragon_alert／revenue` | 財報體檢卡 ✅；EPS／營收「⬜ 趨勢圖尚未建置」；其餘無 | 部分 | 標查 L2 | major | ●（領先／龍頭／月營收圖） | FACT |
| T15 | **Valuation current**：357 殖利率評價、PE、PB | `section_357_valuation`；選股網 PE | 第三區 357 卡；候選表 PE（當日本益比，資料日「⬜ 未提供」，`PE_COL_NOTE` 明說與 357 口徑不同）；**PB 無** | 部分 | 標查 L2 | major | ●（PB） | FACT。§16 要求 EPS basis／source／as_of、PE source／policy、calculation 揭露：現無 |
| T16 | **Valuation historical**：殖利率／PE／PB 河流圖（歷史估值區間） | `section_357_valuation.py`（docstring：3 河流圖，PE 3 種區間 selectbox、PB 產業動態閾值） | 無（在「明細七段」未接） | ❌ | 標查 L2 | **critical**（§42 valuation；舊獨有） | ● | FACT |
| T17 | **Forward EPS／Fair Value＝Forward EPS×PE**（§16／17） | **不存在**（grep `forward_?eps\|NTM\|FY20xxE\|consensus\|forwardPE` 於 src/shared/scripts/app.py **0 命中**） | 無 | n/a（新能力，資料不存在） | 標查 L2「Forward：⬜ 資料未備」 | major（資料源 Gate） | — | FACT（grep 方法如左）|
| T18 | **Institution／Chip（單檔）**：近 20 日籌碼、單日爆量、集保大戶雷達（CV-33） | `section_chips_20d`、`tabs/chip_radar.py` | 籌碼卡（`stock_chips_service`）＋爆量徽章；集保大戶無 | 部分 | 標查 L2 | major | ●（集保大戶） | FACT（chip_radar 只被 `tab_stock` import）|
| T19 | **Industry（單檔所屬產業脈絡）** | 舊無單檔產業區 | 第三區無產業區塊；只有候選表「產業」欄（`target_industry_service.get_ticker_sector_map`） | ❌ | 標查 L2 | major | — | FACT |
| T20 | **Risk（單檔）**：VCP／布林、心理檢查 | `section_vcp_bollinger`、`section_psy_checklist` | 「⬜ 個股風險指標尚未提供」（`RISK_PLACEHOLDER`） | ❌ | 標查 L2 | major | ● | FACT |
| T21 | 個股買賣語意：停利停損、目標價、部位大小、即時操作建議、統一判決、三維出場（CV-30） | `section_when_buy_sell`、`section_op_recommendation`、`section_strategy_conclusion`、`compute/strategy/exit_signals` | 無（HI-3 未核准；`RESEARCH_ONLY_NOTE`「本頁只呈現研究資訊，不提供交易操作」） | ❌（刻意） | §18：標查不承接；若保留需 deterministic action contract | **critical**（舊獨有判斷；需客戶裁示保留／退場） | ● | FACT |
| T22 | 型態目標價（ZigZag；CV-31） | `tabs/pattern_targets_ui.py`（`tab_stock`、`stock_grp_sections/section_portfolio_summary` 引用） | 無 | ❌ | 同 T21（目標價語意） | major（需裁示） | ● | FACT |
| T23 | AI 首席顧問、AI 財報體檢（Gemini；CV-32／34） | `tab_stock`、`financial_health_engine` | 「🤖 AI 投資總結：⬜ 尚未提供」 | ❌ | 標查 L2「OneBrain Research Explanation」（Stage G） | major | ● | FACT |
| T24 | 個股↔總經 banner、個股↔持倉 banner、相關新聞（CV-33） | `macro_stock_link`、`portfolio_linkage`（`tab_stock`） | 無 | ❌ | 標查 L2 | minor | ● | FACT |
| T25 | ETF 單檔三判決卡（折溢價／配息／同儕） | `etf_tab_single` | 第三區 ETF 版型（`page_inspect` builder） | ✅ | 標查 L1/L2 | — | — | FACT |
| T26 | ETF 明細七段（淨值 vs 市價、折溢價帶、配息紀錄、成分股、同儕 7 維、標準差帶、破發） | `etf_tab_single`、`etf_render.render_etf_holdings` | 無（UNCOVERED_ITEMS） | ❌ | 標查 L2/L3 | major | ● | FACT |
| T27 | ETF smart：3-3-3、標準差買賣帶、分散度（CV-36） | `etf_tab_smart`（V-SMART-CACHE-1） | 無 | ❌ | 標查 L3 或退場 | minor（帶買賣語意者需裁示） | ● | FACT |
| T28 | 多檔比較（個股 ≤10、ETF 7 維 PK；CV-38） | `tab_stock_grp`、`etf_tab_grp_compare` | 「進階分析」批次表 ≤20 混貼 | 部分 | 標 L3 | minor | ●（ETF 7 維、財報趨勢×轉機） | FACT |
| T29 | 三階段濾網＋AI 報告、組合體檢 vs 基準（CV-39／40） | `tab_stock_grp`／`stock_grp_sections` | 無 | ❌ | 持 L2 或退場 | minor | ● | INFERENCE（CV-40：舊 UI 內亦可能不可達，未重驗）|
| T30 | 帶入我的持股 | （舊：持股頁） | 無（UNCOVERED_ITEMS） | ❌ | 標查 | minor | — | FACT |

### §4.C 持股（§42：portfolio、risk）

| ID | 舊能力 | 舊位置 | 新 UI 現況 | 承接 | Final 落點 | Gap | 舊獨有 | 證據／備註 |
|---|---|---|---|---|---|---|---|---|
| H01 | **Portfolio Risk Cap＋目前曝險 vs Cap**（§19） | 無 exposure-vs-cap 比較；只有市場端 `get_allocation` 區間 | `page_hold` ⑤ `build_position_cap_card`（市場端水位，非 L1）；**無「目前曝險」**；首屏無 Risk Cap | ❌ | 持 L1 | **critical** | — | FACT。Sheet 表頭只有 `name/ticker/lots/avg_price/updated_at`（`gsheet_portfolio._HEADERS`）⇒ 無現金／總資產，**「目前曝險 %」無資料可算**（INFERENCE：除非改用「市值÷某分母」新定義＝新語意 Gate）|
| H02 | **System Action（加碼／持有／減碼 1/2／全出）**（§20） | ETF：`compute/etf/dividend_station.action_branch`（`ACTION_CUT／TAKE_PROFIT_FORCE／TAKE_PROFIT_PARTIAL／PAUSE_ADD／ADD／PREMIUM／CRUISE`）＋`suggest_action` 字串；個股：`StockAssessment.swap_level`（🔴換出／🟡留意／🟢續抱／⚪資料不足） | ① `build_action_card` 只列「N 檔亮汰弱紅燈、N 檔亮加碼燈」或巡航句（`cruise_or_gap`） | 部分 | 持 L1「今日需處理」 | **critical** | — | FACT。**客戶 5 動作詞彙無 1:1 對映**：無「減碼 1/2」「全出」代碼；`take_profit_partial`＝「分批停利（>+2σ）」、`cut`＝「汰弱」；個股軌與 ETF 軌兩套；Q4 序在 `shared/decision_digest_rules.Q4_ACTION_PRIORITY`。對映＝新投資語意 ⇒ Decision Gate |
| H03 | 今日需處理（只列真 Action；無則「今日無需調整」） | 舊戰情室結論三卡 | ①「該做什麼」卡＋「可信度 N/M」卡（巡航句須所有燈判得出才准說） | 部分 | 持 L1 | major | — | FACT。「沒事 vs 判不出」已有 gate（`cruise_or_gap`）|
| H04 | **Holdings Table**（代碼／名稱／比例／成本／現價／報酬／策略／System Action） | 舊戰情表 `etf_tab_dividend_station` | 無逐檔表（只有燈牆 `build_lightwall_card`；G6／D3 凍結） | ❌ | 持 L1 | major | ●（逐檔戰情表） | FACT（引 CV-43＋讀 `_render_warroom_leaf` 區段）|
| H05 | Portfolio Overview charts：performance、benchmark、sector exposure、strategy distribution、concentration（§21） | 產業集中度 `stock_grp_sections/section_industry_concentration`（等權、無門檻）；對 0050／效率前緣 `etf/etf_tab_portfolio.py`；風險貢獻 `render/risk_contribution_render.py` | **0 張圖**（Phase 1 baseline 實量） | ❌ | 持 L1/L2 | major | ●（集中度、風險貢獻、對 0050） | FACT。performance 歷史＝無交易流水（MISSING，資料缺口非 UI 缺口）|
| H06 | **策略分類**（存股／資本利得／未分類） | 無；AB-4r 唯讀 reader `src/data/portfolio/strategy_class_reader.py`＋`shared/strategy_class_schema.py` | 無 UI consumer；digest builder 一律「未分類」 | ❌ | 持 L1 欄＋我設 | major | — | FACT（grep `strategy_class_reader` 只在 L1 自身與 `gsheet_portfolio`）；寫入 AB-4w＝HI-5 未核准 |
| H07 | 235 燈／健檢／燈牆；逐盞明細＋週線／布林 z 圖（CV-43／44） | `etf_tab_dividend_station`、`station_cards` | ③ 燈牆 ✅；逐盞明細與兩圖無 | 部分 | 持 L2 | minor | ●（明細圖） | FACT |
| H08 | 80/20 配置偏離＋衛星停利（CV-45） | 同上 | ⑤ `build_allocation_split_card`／`build_take_profit_card` | ✅ | 持 L2 | — | — | FACT |
| H09 | 換股建議（CV-46） | 同上 | ④ `build_switch_card` | ✅ | 持 L2 | — | — | FACT |
| H10 | VaR、壓測、配息現金流（CV-48 部分） | `etf_tab_portfolio` | ⑥ `build_deep_cards`（`portfolio_deep_service`） | ✅ | 持 L2 | — | — | FACT |
| H11 | 再平衡、Overlap／相關、效率前緣、對 0050、稅後（CV-48 其餘） | `etf_tab_portfolio` | 再平衡 `UnwiredSpec(key="hold.deep.rebalance")`；其餘無 | ❌ | 持 L2/L3 | major | ● | FACT |
| H12 | 🍇 葡萄串領息（CV-49） | `tabs/grape_ladder.py` | `UnwiredSpec(key="hold.deep.grape")` | ❌ | 持 L3（HI-4） | minor | ● | FACT |
| H13 | **AI 戰情總結**（CV-50） | 舊戰情室 ⑥ | ⑦ 按鈕 → `dividend_station_service.build_ai_summary(digest, app_ai_service.gemini_call)`（**付費 Gemini、輸入＝station digest，非 Decision Digest、無 grounding**） | 部分 | 持 L2「OneBrain 持股摘要」（Stage G） | major | — | FACT。現行行為與 §23／§33／§36 不符，屬 Stage G 替換對象 |
| H14 | 同名兩套刻度揭露（CV-47） | — | ② 常駐 | ✅ | 持 L3 | — | — | FACT |
| H15 | 持股↔Sheet 綁定狀態、組合設定葉 | 舊 📁 | 葉2「組合設定」（唯讀；Sheet 選擇／觀察清單管理為 `UnwiredSpec`） | 部分 | 我設 | minor | — | FACT |
| H16 | LINE／Telegram 推播（CV-51） | `scripts/push_daily_signals／push_holdings_daily／push_watchlist_signals／push_weekly_report.py`＋同名 workflows | 無 UI | n/a | 我設（唯讀狀態） | minor | — | FACT（`ls scripts .github/workflows`）|

### §4.D 我的／Audit（§42：source audit；§24–27）

| ID | 舊能力 | 舊位置 | 新 UI 現況 | 承接 | Final 落點 | Gap | 舊獨有 | 證據／備註 |
|---|---|---|---|---|---|---|---|---|
| E01 | Google 登入／登出／重新登入（CV-52） | 側欄、📁 | `page_me` ① ＋側欄（兩模式） | ✅ | 我設 L1 | — | — | FACT |
| E02 | Sheet URL／ID、Drive 清單、使用這本、重新讀取（CV-53） | 側欄、`portfolio_binder` | `page_me` ②（ID 只顯示末 6 碼） | ✅ | 我設 L1 | — | — | FACT |
| E03 | active portfolio／watchlist 選定（CV-54） | 隱性「第一本」 | `page_me` ③（只活在 session） | ✅ | 我設 L1 | minor（不持久化） | — | FACT |
| E04 | Sheet／組合／觀察清單／持股列 CRUD（CV-55） | `tabs/portfolio_manager.py`（`save_stock_watchlist` 等） | 無（`page_me` 檔頭「⛔ 不搬 CRUD」） | ❌ | 我設（HI-5 核准後） | major | ● | FACT |
| E05 | Strategy 設定（每檔策略） | 無 | 無 | ❌ | 我設 | major | — | FACT（AB-4w 未做）|
| E06 | Notifications 設定 | 無（只有 cron） | 無 | ❌ | 我設（唯讀狀態即可） | minor | — | FACT |
| E07 | Display preference | 無 | 無 | ❌ | 我設 | minor | — | FACT |
| E08 | **Decision Digest Viewer**（§25／27） | 無 | 無；`src/services/decision_digest_builder.build_decision_digest`、`decision_digest_summary` **0 production caller** | ❌ | 我A L1/L2 | **critical**（Stage F 前置） | — | FACT（grep `decision_digest` import 於 src/app.py/scripts/shared，除自身模組與 `shared/strategy_class_schema` 外 0 命中）|
| E09 | **Rule Registry（唯讀）**（§26） | 半成品：`page_why.load_specs`（讀 L0 `shared/macro_buckets.DangerSpec`、`shared/station_specs`）—預設模式到不了；`tab_edu` 逐盞門檻對照表 | 無 | ❌ | 我A L2 | major | ●（門檻對照表） | FACT。L0 規格無 rule_id／version／effective_from 欄（`DangerSpec` 欄位：key/label/bucket/unit/direction/yellow/red/…/note）|
| E10 | **Data Freshness**（資料健康牆、覆蓋率；CV-58／62） | `pages/data_coverage.py`、`page_why` 葉2、側欄 `render_sidebar_data_health` | 側欄總覽（兩模式）；頁內「⬜ 資料狀態：尚未彙總」 | 部分 | 我A L1 | major | ●（燈號牆） | FACT。`page_why` 自陳 `@monitored` 只涵蓋少數 fetcher |
| E11 | System Information | 無 | 無 | ❌ | 我A | minor | — | FACT |
| E12 | 進階診斷（資料源清單、Fetcher 監控、§4.3 對帳、API 根因、原始表、門檻校準）（CV-59） | 🔧 工具箱 expander＋checkbox；`page_why._render_engineer_block` | 無（預設模式） | ❌ | 我A L3（唯讀部分） | minor | ● | FACT |
| E13 | 副作用控制：測試連線、強制刷新、測融資／NAS、清快取、執行校準（CV-60／61／63／64） | 側欄、`health_inspector`、`calibration_ui` | 側欄兩顆仍在（兩模式）；其餘舊獨有 | 部分 | 不進四頁（維持既有處置） | minor | ● | FACT |
| E14 | 教學（策略說明書、總經小教室、門檻對照）（CV-65） | `tabs/tab_edu.py`、`macro_classroom` | 無（預設模式） | ❌ | 我A L3 或各處「查看依據」 | minor | ● | FACT。⚠️ `tab_edu` 展示 `recession_probability` logit 公式與代入示例 %（見 §2.9） |
| E15 | AI 問答 chat（CV-66） | `tabs/tab_ai_chat.py`；`page_why` 葉3（`ai_qa_service.run_agent`） | 無（預設模式）；市場頁「問 AI」expander 寫「新版尚未提供」 | ❌ | OneBrain（Stage G，只讀 Digest） | major | ● | FACT |
| E16 | Risk Cap 歷史紀錄 | `services/risk_cap_history_service`（寫，由 `macro_refresh_service` 呼叫）／`risk_cap_history_reader_service`（只有 `run_smoke_if_flagged`） | 無 viewer | ❌ | 我A L2 | minor | — | FACT |
| E17 | 免責聲明 footer（CV-68） | `_render_footer` | 同 | ✅ | 全站 | — | — | FACT |

---

## §5 路由現況（決定「新 UI 目前看得到什麼」；FACT，讀碼）

- 預設模式＝新版四頁（📊／🎯／💼／👤），桌機側欄 radio＋手機底部固定列，同一 SSOT `_nav4_page`（`app.py::_nav4_resolve_legacy`、`_ia_view_nav4`；`shared/ia_nav4.PAGE4_LABELS`／`PAGE4_TO_VIEW`）。
- 💼 持股仍是 IA v2 版 `page_hold.render_page_hold`（Phase 6 未開工）。
- `page_today`（🚦 今天）、`page_why`（📖 憑什麼）＝`ia_nav4.LEGACY_ONLY_VIEWS`，**預設模式到不了**；舊 7 頁籤只有 `?legacy=1`（不在任何導覽放連結，DEC-097）。
- 兩模式都在的側欄：🔐 Google 帳號、🔌 連線狀態＋🔍 測試連線、🔄 強制刷新、`render_sidebar_data_health`。
- 新模式刻意不畫：全域置底常駐條（`_gl_slot`）、🔗 我的組合狀態列、🧭 總經指南針。

## 附錄 A　專項查核（轉錄自 invB §2；單組）
#### 2.1 持股頁 Risk Cap／曝險／System Action 的正式 deterministic 來源 — FACT
- **Risk Cap（市場端上限）**：有。`src/services/macro_state_locker.py::calculate_system_state`（外資期貨／薩姆／PMI 連兩月等硬否決，常數 `MACRO_VETO_*`）→ `src/services/risk_cap_apply.py`（寫新 UI 專用 `risk_cap_state.json`）→ `shared/risk_cap_policy.py`（`RISK_CAP_RULESET_VERSION="risk_cap.v2"`、`is_valid_risk_cap_snapshot`、`risk_cap_disclosure_from_snapshot`）→ `src/services/allocation_service.get_allocation`（`shared/allocation_decision.build_allocation_decision` 取 caps 最低）→ 新頁閘門 `src/ui/views/risk_cap_gate.has_system_risk_cap`。狀態：**未經 C2b／RC-VISIBILITY 核准顯示**（市場頁藏數字）。
- **Portfolio 曝險（Exposure）**：**無**。無現金／總資產欄（`gsheet_portfolio._HEADERS`）；全 repo 無 `current_exposure` 類函式（grep `def .*exposure|current_exposure|曝險` 於 services/compute/shared：只有規則文字與 macro 上限）。⇒ §19「Exposure > Cap」**目前無法 deterministic 判定**。
- **System Action**：只有 ETF 軌 `dividend_station.action_branch`（7 碼）＋個股軌 `swap_level`（4 級）；**無「持有／減碼 1/2／全出」的正式代碼**；無 Risk Cap 對個股動作的封鎖邏輯（例：Cap 超限 ⇒ 禁止 `add`）。grep `system_action` 0 命中。
- ⇒ **Single Action Authority 的 deterministic 來源目前不完整**：需新 contract（動作詞彙對映＋Risk Cap 封鎖規則＋曝險分母定義），屬新投資語意 ⇒ Decision Gate。

#### 2.2 Rule ID — FACT
- 存在但極窄：`shared/decision_digest_rules.RULE_ID_ALLOWLIST` 只有 `risk_cap`（`risk_cap.v2`）＋ 5 個行動碼（`cut／take_profit_force／take_profit_partial／pause_add／add`，版本標籤 `ACTION_RULE_VERSION="action_branch.v1"`，檔內自陳為**AB-1 內部命名、非客戶核准**）。
- 客戶範例 `R-VIX-02` 類 ID：**不存在**（grep `R-VIX` 0 命中於產品碼）。16 燈門檻（`shared/macro_buckets.DangerSpec`）無 ID／version／effective_from。

#### 2.3 Decision Digest builder／headless 現況 — FACT
- 契約與工具已在：`shared/decision_digest.py`（`DataStatus` OK/STALE/MISSING/PROXY/FAILED/INVALID；`MissingReason` 含 NOT_DEFINED／NOT_WIRED；`Availability`；`AiParticipation`）、`decision_digest_validator.py`、`decision_digest_grounding.py`（G1–G6）、`decision_digest_rules.py`、`decision_digest_terms.py`；L3 `decision_digest_builder.build_decision_digest`（純函式、不取數、不碰 streamlit）、`decision_digest_summary`（規則式摘要）。
- **headless 性質**：builder 本身不依賴 session（docstring＋import 只有 L0）。**但沒有任何 orchestrator 去取數並呼叫它**——0 production caller（見 E08）。現行頁面的資料仍由 session（`st.session_state` 的 `mkt_info`、`warroom_summary`、更新報告）驅動；市場頁 `page_market` 直接讀 session key。⇒ §28「Digest must exist without rendering any page」**尚未成立**。
- 契約覆蓋 vs §31：只搬 market（regime／light／health）、risk_cap、holdings、actions（截斷 `MAX_ACTIONS=3`）；tw_trend／intl_trend／industry／valuation 固定定義狀態；**不搬** raw 指標值、candidates、industries（docstring 明言「產業集中度與選股排名不搬：契約沒有對應段」）。⇒ §31 要求的 candidates／industries／raw values 段缺。
- OneBrain：**只有文件**（`docs/vnext/ONEBRAIN_*`、`docs/governance/ONEBRAIN_AI_GOVERNANCE_2026-10-31.md`）；產品碼 0 檔（find `*onebrain*` 只命中 docs）。現行 AI 出口仍是 `app_ai_service.gemini_call`（持股 ⑦）、`ai_qa_service`（legacy）、各舊頁 Gemini。

#### 2.4 watchlist 寫入流程 — FACT
- 存在於**舊 UI**：`app.py` 選股網 → `src/services/watchlist_service.add_picks_to_watchlist`（L3）→ `gsheet_portfolio.add_to_stock_watchlist`（讀現有→聯集→存）；另 `src/ui/tabs/portfolio_manager.py` → `save_stock_watchlist`（覆寫式 CRUD）。
- 新 UI：0 寫入（`page_hold` 檔頭以 `tests/test_p04_hold_view.py::TestReadOnly` 黑名單釘死；`_target_blocks.UNCOVERED_ITEMS` 列「加入觀察清單」未接）。
- ⚠️ Freeze 需裁定：§13「既有正式 watchlist 流程」是否包含舊 UI 這條（HI-5／AB-4w 未核准）。推薦讀法（INFERENCE）：**未經新 UI 寫入面核准前，CTA 一律 disabled**。

#### 2.5 Forward EPS 資料源 — FACT：不存在（grep 方法見 T17）。現行估值只有：TWSE 當日 PE（`yield_pe_fetcher.fetch_pe_name_maps` via `valuation_service.get_pe_name_maps`）、357 殖利率（`app_stock_fetchers.fetch_dividend_data` via `valuation_service.get_stock_dividends`）、舊 UI 的 TTM EPS PE 河流與 PB 河流（`section_357_valuation`）。

#### 2.6 大盤 EPS×PE 模型 — FACT：產品碼不存在；新市場頁 `render_chart_c` 為「研究框架，未啟用」空槽（`CHART_C_EMPTY`：需先核准 EPS 來源、PE 情境、公式、更新頻率）；BACKLOG `VN1-MT-VALUATION`＝Research Candidate＋缺資料。另：`compute/risk/risk_radar.synthesize_dual_verdict` 的 `valuation_level` 無人產生（BACKLOG 原文）。⇒ 符合 §43「保持 Research」。

#### 2.7 Semantic Chip 現況（§4）— FACT
- `src/ui_v2/compact.py::META_KINDS` 封閉集：info 族（asof／source／retrieved_at／window／pretax／ai）、status 族（readable／stale／freshness／coverage／asof_missing）、guard 族（not_defined／not_approved／estimated／proxy／imputed／data_quality／fx_*）；另 `guard_chip`（逐字護欄句）、`status_chip`、`topn_more`。**無 neutral／info 自由文字 kind**。
- 違反 §4 的現存用法：🎯 標的頁判型 chip（`🏢 個股`／`ETF`）、計數 chip（`✅ 命中 N 項`／`⬜ 未通過／缺漏 M 項`）、估值口徑 chip（`PE_BASIS_CHIP`）以 `guard_chip`（護欄族）承載——`_target_blocks` 註解自陳暫名，BACKLOG `P5-CHIP-KIND-NAMES`。

#### 2.8 四態（Missing／Stale／Unavailable／Not evaluated）現況 — FACT
- UI 側：`shared/ui_state.py` 十態（idle／loading／failed／empty／missing_retryable／not_applicable／partial／degraded／unwired／live）＋`compact` 的 `stale`／`asof_missing`／`unavailable`（委派 ⛔ 未接線）。
- Digest 側：`DataStatus`＋`MissingReason`＋`Availability`。
- 兩套命名未對齊客戶四詞（INFERENCE：需一張映射表；例如 `UI_UNWIRED`「⛔ 未接線」vs 客戶 Unavailable「來源目前不可用」語意不同）。

#### 2.9 機率／勝率類顯示 — FACT（grep `機率|勝率|probab|logit` 於 src/shared/app.py）
| 位置 | 內容 | 預設模式可見？ | 校準 |
|---|---|---|---|
| `src/data/macro/macro_core.py::recession_probability`（L1）；係數 `shared/signal_thresholds.RECESSION_LOGIT_COEF_SPREAD=-1.5`／`_INTERCEPT=-0.8` | 10Y-3M logit 衰退機率 % | 函式 **0 production caller**；`tab_edu`（legacy 教學）以 `shared/edu_tokens` 複刻算式並列代入示例 % | **無校準證據**（常數 docstring「對齊 Fund 端同名常數」、「原 inline」） |
| `src/compute/macro/macro_helpers.py`（紅綠燈文案「歷史勝率最高」）→ legacy `section_state` | 定性勝率宣稱 | 否（legacy） | 無（同檔另一處 2026-08-19 文案曾用校準管線 n=4,741 實測 27% vs 18% 改寫，**僅該句**） |
| legacy `section_long`／`section_chips`／`section_cross_ai`／`section_state`、`app_ai_service`（RSI 文案） | 「機率高」定性句 | 否 | 無 |
| `src/compute/strategy/v5_modules.py` | 「營收爆發機率高」 | 否（legacy 個股） | 無 |
| `etf_tab_single` | 「PR 百分位（勝率越好）」 | 否 | 百分位統計，非機率模型 |
| `page_hold` VaR 說明 | 「機率約 95%」 | **是**（持股 ⑥） | VaR 信賴水準定義，非預測機率（INFERENCE：合規） |
| `forward_test.py` | hit rate「勝率」 | 否（legacy 對帳） | 實際已實現比例，非預測 |
→ 新四頁預設模式**未見**未校準機率數字（只掃字串，未跑 runtime；INFERENCE）。

---

## 附錄 B　四頁現況 vs 客戶條款（轉錄自 invB §3；單組；讀碼）
#### 3.1 📊 市場（§6–9、§40）— 現行 L1（`page_market.render_page_market`，P4-1～P4-5 後）
現行順序（FACT）：頁首（標題＋問句＋按更新時間｜加權指數資料日）→ 🚀 更新 CTA → 今日結論（五項並列）→ 3 核心狀態 tile（市場位階｜建議總持股水位｜今日主要風險）→ ⚡ 需要處理 → AI／資料狀態一行（「🤖 ⬜ 尚未提供」）→ 圖 A（台股＋MA 參考線，Primary）→ 圖 B（國際 small multiples）→ 圖 D（主要風險）→ 圖 C（大盤 EPS×PE 研究空槽）→ L2/L3 expanders（位階為什麼、五桶、X3、16 燈、台股原始、國際原始、總經原始、籌碼原始、X9、資料來源與完整度、問 AI／查看依據）。

| 客戶條款 | 現況 | 差距 |
|---|---|---|
| §6 Regime | 市場位階 tile ✅（用字不同） | 術語統一（§39） |
| §6 Risk Cap | 水位 tile「⬜ 尚未核准／無法判定」 | RC-VISIBILITY 未裁；與持股 ⑤ 不一致 |
| §6 System Action State | 無 | critical（無來源） |
| §6 OneBrain Outlook | 佔位 | Stage G |
| §6 是否需行動 | ⚡ ✅ | — |
| §7 指標卡（value/state/as_of/source） | 無 L1 卡；逐指標 as_of 契約不存在 | major |
| §8 主圖 index＋正式趨勢線＋Regime 註記 | 收盤＋MA 最新值水平線；無 Regime 註記；趨勢定義未核准 | major |
| §8 VIX＋門檻帶 | 無 | major |
| §8 International small multiples | ✅ | — |
| §8 Macro mini／sparkline | 無（只有 L3 表） | major |
| §9 L2/L3 | 已有大量 expander；「為什麼／來源／限制／去哪補」四段摺疊 ✅；counter evidence 段無 | minor |

#### 3.2 🎯 標的（§10–18）— 現行（`page_target`，P5-1～P5-3 後）
現行順序（FACT）：標題＋問句 →「⬜ 資料狀態：尚未彙總」→ 搜尋（代碼＋進階選項）→「🤖 AI：⬜ 尚未提供」→ 第一區 產業 Top 5 橫條＋查看全部 → 第二區 選股條件（收合＋摘要）＋候選 Top 10＋全部＋CSV＋選一檔／查看此檔 → 第三區 單一股票（判型 chip、3 摘要 tile、計數 chip、K 線 placeholder、▸ 完整分析 收合）→ 進階分析（多檔比較、仍未覆蓋功能清單）。

| 客戶條款 | 現況 | 差距 |
|---|---|---|
| §10 雙模式、不得同時完整展開 | 單頁三區直排 | major；**DEC-107 1A 頁序需標 supersede** |
| §11 產業 Top N bar＋score/state＋freshness | Top 5 bar ✅、抓取時間 chip ✅；score/state 只有資金象限 | minor |
| §11 候選 Top N 不丟 universe | Top 10＋全部 ✅；存活池逐檔表待查（T04） | major（待驗） |
| §12 代碼／名稱搜尋、查詢後收合精選 | 只代碼；不收合 | major |
| §13 Session-only、不自動寫入 | ✅ 0 寫入（FACT：讀 `_target_blocks` 檔頭＋UNCOVERED）；CTA 不存在 | 需 disabled CTA＋裁示 |
| §14 workspace 順序 | 有 Header（chip）、Fundamental、Valuation(357)、Chip；Price Chart／Industry／Risk／OneBrain 缺 | major |
| §15 6 維 Snapshot | 3/6 | major |
| §16 Valuation current／historical／forward／scenario＋EPS basis 揭露 | current 部分（357、PE 無 as_of）；historical 舊獨有；forward 不存在；scenario 無 | critical（historical）／major |
| §17 EPS×PE 時間軸 | 無 EPS×PE | n/a（未實作即無違反） |
| §18 Ad-hoc OneBrain 不給買賣 | 佔位；`RESEARCH_ONLY_NOTE` 已在 | Stage G |

#### 3.3 💼 持股（§19–23）— 現行（`page_hold`，**IA v2 版，Phase 6 未開工**）
現行結構（FACT）：`st.tabs([戰情室, 組合設定])`；戰情室 ①結論三卡（該做什麼／訊號可信度 N/M／需處理）→ ②兩套刻度揭露（常駐表）→ ③燈牆＋VIX → ④換股＋總經位階 → ⑤80/20＋停利＋建議持股水位（市場端）→ ⑥深度分析（VaR／壓測／配息現金流／再平衡未接／葡萄串未接）→ ⑦AI 戰情總結（付費 Gemini 按鈕）。gate：葉2 form「🚀 跑存股戰情室」。

| 客戶條款 | 現況 | 差距 |
|---|---|---|
| §19 Risk Cap 第一屏＋Exposure>Cap 🔴 禁止新增曝險 | 無首屏 Risk Cap；無 exposure；無封鎖規則 | **critical** |
| §20 今日需處理只列正式 Action | ① 有（汰弱／加碼計數＋巡航 gate），詞彙非客戶五詞 | critical（詞彙對映＝語意 Gate） |
| §21 Overview charts | 0 圖 | major |
| §22 Holdings Table L1 | 無逐檔表 | major |
| §23 OneBrain 持股摘要＋grounding | ⑦ 直呼 Gemini，無 Digest、無 grounding | major（Stage G 替換） |
| 結構 | 與 blueprint（AI→⚡→🌱/📈/⬜ 三區）不同（Phase 1 Visual Gap Audit） | Phase 6 全面重做 |

#### 3.4 👤 我的（§24–27）— 現行（`page_me`）
現行（FACT）：① Google 帳號 ② 目前 Sheet（切換 expander）③ 這本 Sheet 內容（組合／觀察清單選擇器）→「▸ 詳細」收合。
| 客戶條款 | 現況 | 差距 |
|---|---|---|
| §24 Google／Sheet／Portfolio／Watchlist | ✅（選定不持久化） | minor |
| §24 Strategy／Notifications／Display | 無 | major／minor／minor |
| §25 Audit 入口（Digest／Rule Registry／Freshness／System Info） | 無 | critical（Digest viewer）／major |
| §26 Rule Registry 唯讀 | 無；L0 規格無 ID／version／effective_from | major |
| §27 Digest Viewer 不顯示 secret | 無 viewer；（現有：`page_me` 只印 Sheet ID 末 6 碼、`shared/secret_scrub.scrub_secrets` 已廣泛使用） | — |

---

## 附錄 C　手機 L1 現況量測（轉錄自 invB §4）

> ⚠️ 全部為**夾具**（`tools/visual_fidelity/harness_app.py`，L3 假資料，Streamlit 1.59.2，沙箱）；**非真機、非真資料、非 Streamlit Cloud**。手機 viewport 390×844，第一屏可用高 791（扣底部導覽 53px）。
⚠️ 全部為 **夾具（`tools/visual_fidelity/harness_app.py`，L3 假資料，Streamlit 1.59.2，沙箱）**；**非真機、非真資料、非 Streamlit Cloud**。手機 viewport 390×844，第一屏可用高 791（扣底部導覽 53px）。

| 頁 | 日期／基準 | 第一屏可見（§40 要求） | 數字 |
|---|---|---|---|
| 📊 市場 | 2026-10-31，P4-3 Gate（`docs/vnext/phase4_market/p4_3/GATE_REPORT.md`，基準 `228b9fa9`）＋P4-4／P4-5 更新；DEC-119／120 判 PASS | 市場狀態 ✅（位階 tile y537）、Risk Cap 卡 ✅（水位 tile 同列，但值＝尚未核准）、refresh ✅（頁首 CTA）、**是否行動 ⚡ y1016 不在第一屏**（DEC-118 手機例外） | 結論頂 y427（Q11 +269～+379 > 建議 +260，🟡）；風險 tile 只露 42px；KPI 區塊 461／394／461px（>340，🟡 A11）；手機 Primary 220px（DEC-119 例外）；全頁高 loaded 3789（floor 1.56）；手機圖例 5 項可見約 2（F1，P4-5 改自訂圖例後另見 PR_NOTES） |
| 🎯 標的 | 2026-11-01，P5-3 Gate（`docs/vnext/phase5_target/p5_3/GATE_REPORT.md`，基準 `f2a6a8a`，單組自評「🟡 有條件 PASS」待獨立 QA） | mode ❌（無模式切換）、search ✅（搜尋卡在第一屏）、查詢摘要：第三區不在第一屏（INFERENCE：位於候選之後） | Primary（產業 Top5）633–773，在導覽 791 之上（餘裕 18px）；第一屏字數 282；全頁高 loaded 2850（3 候選）／3105（50 候選）；無水平捲動；最大單元素 406 |
| 💼 持股 | 2026-10-29，Phase 1 baseline（`docs/vnext/visual_fidelity/phase1_baseline/VISUAL_GAP_AUDIT_2026-10-29.md`）；之後持股頁未重做（Phase 6 未開工；INFERENCE：數字仍近似） | portfolio status 部分（① 卡自 y506）、**Risk Cap ❌**、是否處理（① 該做什麼）部分 | 全頁高 11,416（13.5 屏）；⑦ AI 按鈕 y10,535；0 圖；桌機 4,464 字、18 張卡 |
| 👤 我的 | **無量測**（harness 只支援 `?p=market\|target\|hold`，`tools/visual_fidelity/README.md`） | connection state／primary actions：未量 | — |

---

---

## 附錄 D　維護規則

1. 每個 Stage（B～E）完成時，把該頁列的「新 UI 現況／承接程度／Gap」更新（append-only：舊值刪除線＋日期＋決策者）。
2. 新增或降級 critical 須寫理由；**critical → 非 critical 只能由實作合併＋獨立 QA 證據或客戶裁示（例 T21 退場）達成**，⛔ 改定義讓 gap 消失。
3. Stage J 提出 Removal Gate 前，本檔須經第二組獨立複驗（`FUI-FREEZE-SECOND-AUDIT`）。
