# New UI2｜研究資料承接、第一版重用與 ChatGPT 對話交接提案（2026-11-06）

> 狀態：**Draft / proposal / docs-only**。使用者本輪明確要求：(1) 保留六領域 OneBrain→全域證據複核；(2) 將 2026/10 PDF 所研究的「大盤 EPS×PE 情境估值」和「產業缺貨／大型訂單前瞻判斷」納入 Sheet 資料承接；(3) UI 簡潔、OneBrain 保留完整證據；(4) 重新查第一版 UI 以重用實質能力；(5) 防對話中斷，主動提醒切換、寫 GitHub 交接、提供新對話提示。此檔只是當次規格與交接提案，不代表 Rule ID、正式來源、Sheet schema、授權寫入、公式、AI runtime、UI layout 已通過既有 Gate。
>
> 必須與 PR #1030 的五頁藍圖、DEC-142、#1022/#1027/#1029 的線框與治理衝突收斂。**不得獨立採本草案施工。** Claude Code 主線優先；ChatGPT Work 死碼清理不得碰同檔。

## 一、架構不變，加入研究證據

唯一經核准資料層 → Evidence Registry＋確定性 Domain 計算 → (A) UI ViewModel 少量重點 / (B) Decision Digest 完整證據清單、版本與按需唯讀回查 → 同一 OneBrain 的六領域單元（市場趨勢／籌碼資金／財報品質／產業前景／持股風險／資料稽核） → 全域正反證交叉複核 → UI 白話文短／中／長＋下一步。

- 六域代表分析任務，而非每次必須呼叫六次 LLM。任務按需 scoped 執行，避免重複 Token。
- AI 僅可讀批准的 canonical/evidence，不得自行外連抓數、改寫事實、回寫 Sheet 或繞過 Single Action Authority / Risk Cap。
- UI ViewModel 的 Top-N / 折疊 / 省略資訊不得影響 Digest 覆蓋範圍。證據帶 source_id / observation_date / fetched_at / validity / missing_reason / hypothesis-vs-observation / positive-and-counterevidence。
- 以 required evidence manifest、deterministic coverage、Token-budget 分批/索引唯讀回查與 partial 狀態防止 silent truncation；沒取得的資料不補 0、不標 neutral/healthy/safe。

## 二、PDF 兩項研究工作保留，但不直接新增正式買賣規則

來源：使用者提供 `9778_202610(永旭保經)-蕭碧燕老師 (1).pdf`（70 頁）；本次查讀 PDF 文字內容中「從獲利分析，台股後市仍值得期待」引用凱基證券 2026-08-11 情境矩陣（EPS 預估增長、15–21 倍 PE 與特定歷史指數區間），「產業變數，CSP 高資本支出難以為繼」涉及 CAPEX/OCF、FCF、籌資風險；教材並有 AI 產業多空觀點。它們是**歷史研究材料及第三方情境，非當前行情、非自動生效規則**。產業缺貨、訂單是否實際有明確可驗證個案，需再逐頁逐來源確認；沒有來源不得把推論冒充事實。

A. **大盤 EPS × PE 情境研究資料**：候選欄位包括 `asof_date`, `market`, `eps_type`(TTM/forward、期間與定義), `eps_value`, `eps_unit`, `eps_source`, `pe_scenario_low/base/high`, `pe_assumption_source`, `index_scenario_low/base/high`, `model_version`, `data_quality`, `counterevidence`。試算 `index_scenario = index EPS × scenario PE` 只能在 **EPS 定義/數值/來源、乘數期別與 PE 假設都被核准且同口徑** 時產生研究情境；不使用 2026-08 的舊情境值充當現價，亦不可直接生成加碼或減碼命令。
B. **產業缺貨與大型訂單前瞻研究資料**：候選欄位 `company_id`, `industry`, `event_type`(shortage/order/capex/guidance), `event_date`, `source_url_or_document_id`, `source_class`(official/third-party), `claim_text`, `confirmation_status`(verified/unverified/contradicted), `effective_period`, `capacity_or_order_quantity`, `unit`, `revenue_realization_assumption`, `capex`, `operating_cash_flow`, `free_cash_flow`, `counterevidence`, `staleness`。傳聞、券商預測、公司公告與實際營收**分開記**；不能把訂單量直接視為未來 EPS。
C. **CSP 財務／產業互證**：CAPEX/OCF、FCF、融資來源、公司 guidance、產業供需及反證。產業熱度／缺貨故事與資本開支失速風險需同時保存。

**Sheet 承接設計**：先提出「Research Evidence」邏輯表（可以是同一 Google 帳戶下的獨立 Sheet 或既有核准 workbook 的獨立 tab），以 append-only 研究記錄、來源、有效期、更新時間、版本、驗證狀態保存；**不直接修改持股／登入／Active Sheet 的資料契約，也不把它當正式原始資料真相**。先盤點現有 Google Sheets 寫入 WIF、reader、OAuth、schema、權限、憑證與版本，再走新來源／新欄位／寫入 Gate。只有獲核准 adapter 能寫研究材料；OneBrain 一律唯讀。未證明可用的欄位應標 unavailable，禁止自動產生假資料。

## 三、已查到的第一版模組：能力可取，畫面勿搬

依 GitHub `docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`（當次 main `343f0e0e...`）及程式碼搜尋線索，以下只提出承接候選，**不是已完成接線**：

| 第一版能力／證據 | New UI2 承接位置 | 方式／邊界 |
|---|---|---|
| `src/services/financial_health_engine.py`, `shared/financial_health_thresholds.py`, `src/compute/health/fin_trend_score.py` | 🎯標的：財務安全、獲利、營收/季報與改善惡化 | 已核准確定性路徑與完整 evidence；不抄舊 AI prompt，不改門檻 |
| `src/data/stock/monthly_revenue_fetcher.py`、月營收計算、跨季趨勢 | 🎯標的、💼持股風險 | 經 L3 service/feed；保留來源時點與缺值 |
| `src/data/stock/chip_concentration_fetcher.py`、`src/ui/tabs/chip_radar.py` | 📊市場籌碼／🎯標的 | 舊 UI 可參考呈現，但使用 headless L3；大戶比例、散戶人數、散戶持股比例不可互換 |
| `src/services/sector_heatmap_service.py`, `sector_flow_service.py` | 🎯標的產業機會／📊市場類股 | 以已核准來源與確定性結果承接，不直接匯入舊 UI |
| `src/services/fundamental_screener_service.py`、`shortage_screener_service.py` | 🎯標的研究候選 | 先核對既有來源、計算、必要反證；缺貨敘事非正式投資動作 |
| `src/services/market_twii_view_service.py`、總經16指標、海外指數/外資/融資 | 📊市場 | 保留台股+國際短中長兩軸；前夜美股日期與台灣交易日映射要核對 |
| `shared/risk_cap_policy.py` 及現有 Rule ID / Single Action Authority | 📊市場／💼持股 | 原樣重用；AI 不另算動作權限 |
| `src/services/portfolio_deep_service.py`、持股/ETF 服務 | 💼持股 | 直接曝險與 ETF look-through 分開，缺成分不宣稱完整 |
| `src/services/data_registry_scanner.py` 等資料診斷 | 🗂資料 | 完整來源健康度、抓取失敗、日期與原因；不顯示已刪功能的永久假警報 |

**體驗建議**：五頁維持「一屏結論/狀態/下一步 CTA → 主要圖表 → 展開細節」；資料頁集中全量診斷；各頁仍保留必要資料時點/缺失；390px 和 1440px、頂部五頁橫滑導航、頂部 Active Sheet、右上帳號與 a11y 須另視覺/安全 Gate。不得搬回第一版複雜 tabs、舊版互相競爭的交易建議、過期 ETF 回測文案。

## 四、ChatGPT 對話不中斷／GitHub durable handoff 規則提案

**精確能力邊界**：ChatGPT 無法保證預先知道平台何時截斷對話、額度何時用盡，或在會話失聯後自主寫 GitHub；沒有可用 GitHub 連線/權限時也不能聲稱已同步。下列是**每次實際執行/交接可操作**的規則，不承諾無人值守的背景存檔。

1. **主動提醒切換**：在訊息極長、歷史內容取回失敗、工具上下文即將不足、重要規格多輪累積或重大 Batch 結束等可觀察風險出現時，於安全停點主動說「建議更換新對話」，不待使用者詢問。不得虛構剩餘 token 數。
2. **重要決定即時落盤**：有實際 GitHub 寫權限且不碰 Claude Code 衝突檔時，先 GitHub Verification Gate（main tip、Open/Draft PR、head/diff、CI/QA、branches），將已核准 Decision、BACKLOG、PROJECT_STATE、HANDOFF 按既有五檔治理分工更新；只用獨立 branch/PR，經原有審查與 CI Gate 合併，不直接改 main。**本草案不能代替正式 DEC**。
3. **頻繁 checkpoint**：重大裁示、藍圖收斂、分批交付／有風險斷點時，在既有治理檔寫「已核准／草案／未實作／阻塞／下一步」和證據 URL；若共享文件與施工 PR 衝突，改用單獨 handoff 草案 PR，並明示尚未合併。
4. **新對話交接包**：回覆可複製的完整提示語，需含 repo、角色、當下核實 main SHA+時間、Open/Draft PR、Claude 工作 owner、最新產品裁示與 superseded 規則、工作完成／未完成／不可碰範圍、文件索引、具體下一步和驗證 Gate；新對話首先**重新驗證** GitHub，而非照抄舊 SHA。
5. **聊天與 repo 的界線**：「保存專案知識，不保存全部聊天逐字稿」。不可入 repo 的 secrets、OAuth token、私人持股資料、未授權個資不得落盤；Decision 只摘錄必要裁示與來源時間。不得建立第二套權威狀態系統或名稱為「GPT 對話」的平行 SSOT；需要專門入口時只做現有 `docs/HANDOFF.md` / `docs/PROJECT_STATE.md` 的索引。
6. **回覆節制**：平常靜默自主巡航；主動提醒換對話僅在確有上下文丟失風險時，不因每則訊息進行狀態播報。模型與 Effort 不足仍按原有正式 Gate 提醒。

## 五、下一安全 Gate

1. 先與 #1030 / #1022 / #1027 / #1029 協調，核對最新五頁/六域決策及舊約束 superseded，完成獨立 QA。
2. Sheet 先唯讀盤點 schema、讀寫權、研究 evidence 存放位置、內外來源與估值 EPS 口徑；沒有核准前不得實際寫入或取得新資料。
3. 舊 UI 以模組級 parity 與 lineage audit 做 A/B/C 盤點；對 UI 做 390/1440 視覺驗收，再分批 Claude Code 施工。
4. 此文件及其 PR 的 GitHub 狀態是本次對話交接證據；合併前不能說「規則已正式生效」。

## 六、新對話啟動提示（可複製）

接手 `linchen-20200325/my-stock-dashboard` New UI2 的 GitHub 獨立治理與產品架構工作。先現場檢查 origin/main SHA（含時間）、所有 Open/Draft PR（尤其 #1022/#1027/#1029/#1030 及 ChatGPT 研究/交接草案）、PR head/diff/CI、遠端分支、PROJECT_RULES/DECISIONS/BACKLOG/HANDOFF/PROJECT_STATE；不得把 Draft 當正式決策，也不得覆蓋 Claude Code/Work 正在施工的檔案。產品五頁：市場/標的/持股/我的/資料，頂部五頁＋Active Sheet＋帳號，暗色/手機優先。OneBrain 六領域單一協調＋全域反證複核，Human UI 簡潔、Decision Digest 保留完整 headless evidence；AI 不自行上網取數/寫入，不越權改 Risk Cap。研究候選包括大盤 EPS×PE、缺貨及大型訂單、CSP CAPEX/FCF，應設計 Sheet Evidence 承接但須經來源/公式/Schema/寫入 Gate，教材歷史數字不是現況。重用第一版確定性財報、籌碼、宏觀、選股、持股/ETF 能力，不搬複雜 UI。工作成果及裁示按既有治理五檔分工經 PR 留存，風險時主動提供可複製交接包。繁中、精簡、表格優先；提示語附模型及 Minimum Sufficient Effort。 


## 七、2026-11-07 獨立治理狀態更新（僅為文件註記）

- #1022 的舊四頁 Draft 已關閉、未合併；歷史概念可回查，但不得再作為生效規格或施工依據。
- #1032 的對話預警與交接規則已合併到 main；本檔第四節及交接範例只作歷史研究提案，**不建立第二套治理權威**。
- #1023、#1025 的唯讀稽核／限定靜態血緣工具已合併；不代表完整 runtime/資料正確性驗證或清碼授權。
- #1030 的五頁、OneBrain 及 PDF 藍圖仍屬待整合草案；本檔的 Research Evidence Sheet 欄位是候選，不代表已核准 schema、正式來源、公式、寫入或 AI runtime。
- 本檔是獨立補充研究紀錄；任何正文舊時點描述（例如 #1022 當時尚 Open）都只能按歷史時點閱讀。後續施工必須以最新 main + 正式 DEC/Active Contract + 當下 PR Gate 重驗。
