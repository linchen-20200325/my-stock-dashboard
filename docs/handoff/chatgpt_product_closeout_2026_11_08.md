# ChatGPT 完整產品交接快照｜台股 AI 戰情室（2026-11-08）
> **狀態：交接索引／時點快照，非新 Decision、非新規格、非新施工授權。** 本文件為換 ChatGPT 對話而建；不可凌駕 CLAUDE.md、PROCESS.md、PROJECT_RULES.md、已合併 DECISIONS 或正式 UI 契約。**接手時先查即時 GitHub，不可將這份快照的 PR 狀態當最新。** 本檔獨立於共用 BACKLOG／HANDOFF，避免與 Claude Code 施工衝突。

> **2026-11-09 合併後補正（本 PR 仍為 Draft，未進 main；以最新 GitHub 實況為準）**：此檔 A/F/G 節中的 #1083／#1084「Draft」與 main `412d15b` 只是 **2026-11-08 時點快照，已過時**；#1083、#1084、#1086 已在 main，五步驟 Old UI First 治理 #1087 已 squash merge，main 實查 `5eb3ee9e0e506dc97c643a188ade21e69d4a754a`；`PROJECT_RULES.md` 已有正式入口與 `docs/governance/OLD_UI_FIRST_ADAPTATION_GATE_2026-11-08.md`。#1089 AppTest 失敗已按 Streamlit 版本漂移結案：CI 1.59.2 兩項 PASS，舊沙箱 1.67.0 超出 `requirements.txt` 的 `<1.60.0`；無 production UI2 修改。當時 Open PR：#1088 資料自動發布、#1085 本交接、#1038 PIT **NO MERGE**；#1034（舊治理文件）與 #1080 已關閉未合併（#1034 於 2026-11-08T23:44Z 關閉）。**本更正涵蓋 A、F、G 三節（含 G 節「不要因換對話停止 #1083／#1084」的停止指令）；各節標題已加過時標記，舊正文保留。** #1089 是 issue 不是 PR；Streamlit 1.67 超出 `requirements.txt` 的 `<1.60.0` 造成 AppTest `filtered_state` AttributeError，環境漂移結案，非 UI2 缺陷。另：`PROJECT_RULES.md` 的 Old UI First 入口目前仍寫『PR #1087 未合併前僅 Draft，合併後適用』，與實況不符；屬 main 上另一文件漂移，不在本 PR 範圍，另案登記。**本補正不是新增裁示／實作授權，也不宣稱五頁真資料全接線、FinMind 月份／公告時點已驗、Risk Cap／OneBrain runtime 已完成。** 下一對話必須重查 main/head/CI/QA，不可把本段當永久現況。

## A. GitHub Verification Gate（快照） 【2026-11-08 時點，已過時，見頂部更正】
- repo：`linchen-20200325/my-stock-dashboard`；main：`412d15bec6d478f48654e2a275e2ac542bd07484`（#1082，DEC-154）。
- 目前 Open Draft：#1083（G1 缺貨證據資格呈現，head `691eaa3`）；#1084（FinMind 一次性手動唯讀探針，head `eb2e20a`）；#1034（舊治理文件待逐項核銷）；#1038（macro-forward-test PIT 失格，**NO MERGE**）。
- #1075～#1079 C4 月份契約、評分、月份鍵傳遞與未驗證 5 分上限；#1081 docs 狀態收斂；#1082 DEC-154 均已合併。#1080 已關閉未合併，原分支保留。
- 遠端歷史保留：`docs/newui2-data-page-trend-onebrain-pdf-20261106`、`docs/newui2-hold-w11-draft-20261105`、`docs/newui2-top-five-nav-wireframe-gate-20261107` **依客戶裁示保留**；`main`、`data`、`v2`、`claude/stock-dashboard-handoff-g9dtm0` 不刪。#1034／#1038 對應分支有獨有內容，不能以無 PR 依賴推定可刪。`ccr-ed362375-uplnw7` 為已關閉 #1080 的舊分支，亦未授權刪除。
- GitHub PR head CI／非作者 QA **必須現查**；本檔建立時未宣稱 #1083／#1084 QA 或 CI 成功，也未執行實際 FinMind 取樣。

## B. 新對話閱讀順序與事實優先級
1. 現查 main HEAD、所有 Open/Draft PR 的 head/base/diff/CI/QA/threads、必要 branch 與近期 merged；**HANDOFF/STATE 只做索引**。
2. `CLAUDE.md`、`PROCESS.md`、`PROJECT_RULES.md`，再讀 `docs/DECISIONS.md` 的 DEC-141～DEC-154（如有後續決策則讀最新）。
3. `docs/BACKLOG.md`（`NUI2-DEC154`、`NUI2-C4`、`NUI2-SHORTAGE-VERIFIED-EVIDENCE`、New UI2 各頁待辦）、`docs/HANDOFF.md` 的 **最末有效 Safe Handoff**、`docs/PROJECT_STATE.md` §70。
4. 核准五頁視覺文件 `docs/vnext/NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md`（DEC-146）；Old UI 稽核 `docs/vnext/NEWUI2_SUPERSESSION_AND_DATA_GAP_AUDIT_2026-11-06.md`；頁面接線 `docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md`。
5. 台股／國際趨勢：`docs/vnext/NEWUI2_XIAO_PDF_MARKET_RESEARCH_EXTRACTION_2026-11-06.md`（70 頁教材的研究抽取）、`docs/vnext/MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md`；完整 OneBrain 方向先查正式 DEC/規格，再把 `docs/vnext/ONEBRAIN_EVIDENCE_COVERAGE_TOKEN_BUDGET_SHORT_MED_LONG_2026-11-06.md` 當**歷史研究材料**，不得直接當已核准 runtime 規格。
6. 以程式驗證已完成度：`shared/ui2_contract/pages.py`、`src/ui2/views/__init__.py`、`src/ui2/shell/app.py`、`src/services/ui2/real_feed.py` 及各頁 view／VM builder。以最新 source 實際 caller 對照文件。

## C. 產品方向與 UI 核心
- 產品不是純看盤看板，而是**台股 AI 投資決策作業系統**；基本面優先，候選有成長動能與價值錯殺兩條研究方向；產業／總經／籌碼／事件作 Context Overlay，**未經授權不可新增硬性排名 Gate**。
- 已核准：**Dark-only、Mobile-first、五頁頂部兩列導覽**，順序 📊市場／🎯標的／💼持股／👤我的／🗂資料。手機第二列可橫滑，桌機頂部五頁；不恢復 Drawer／左 rail／☰／JS_V4。第一列 Active Sheet、FAKE/Real、帳號入口，**占位不是正式 OAuth 或 Sheet 綁定**。
- #1055 已將五頁導覽與 🗂資料頁空殼進 main；`shared/ui2_contract/pages.py` 與 `src/ui2/views/__init__.py` 皆有五頁。🗂資料只 Capability 空殼；市場 OneBrain Outlook 是呈現槽、非真實 production；持股 W-11 僅部分版面／空槽。**不將五頁可導覽誤稱五頁全功能完成**。
- Preview 預設 FAKE，有六種 scenario；Real Preview 唯讀且有限：`real_feed.py` 只接台股大盤歷史、總經／Risk Cap 位階的既有 canonical services，並**不將 Risk Cap 確認為 UI2 可下正式動作**；無完整 production Auth/Sheet/持股整合/OneBrain Digest。若有新 head UI 改動需重新查。
- 首屏「現在狀態／是否需行動／下一步／主 CTA」是產品體驗方向，**不因空槽或研究候選冒充正式可行動建議**；資料缺失、不可評估、無來源、來源失敗不得補 0 或以顏色單獨傳達。
- #1055 head 在 Chromium 153、390×844 量測 FAKE unavailable 首屏餘裕 169.4px、Real 175.8px，且通過原生鍵盤／零 JS 等安全測試（`docs/PROJECT_STATE.md` §70.4）；**不等於 iOS/Android 真機、Safari/WebKit、VoiceOver、Cloud CSP 已驗證**，不得弱化 160px 安全回歸守衛。

## D. 五頁交接矩陣（每次用最新 code/PR 重驗）
| 頁 | 現有可證據化能力 | 未完成／不得宣稱 |
|---|---|---|
| 📊市場 | 五頁導航 route、市場 Preview、有限 TWII/Regime Real Preview | 完整國際市場、EPS×PE 即時模型、真正 OneBrain Outlook、正式 Risk Cap action 未證 |
| 🎯標的 | route，市場精選／即時查一檔雙模式 Preview；舊 screener 可以作能力稽核來源 | 完整真實候選池／全域缺貨與財報資格串接、正式操作能力未證 |
| 💼持股 | route、W-11 第一批欄位及誠實空槽 | 正式持股、Auth／Sheet、風險水位、買賣建議接線未證 |
| 👤我的 | route、帳戶狀態 Preview | 真 OAuth、Sheet 綁定／登入持久化不能由占位推論 |
| 🗂資料 | route、Capability「尚未提供」空殼 | 正式全量來源健康度／可追溯稽核頁未接線 |
> 上表是已讀 repo 文件／程式時點，必須由新對話對 latest main 覆核；**已核准版型 ≠ 已實作頁面 ≠ 真資料接通 ≠ OneBrain 可以決策**。

## E. 投資模型、研究與 OneBrain 的安全界線
- 歷史 PDF 簡報中的**大盤 EPS×PE** 是情境研究（EPS 年份／發布時點、PE 假設、成長率、估算日期分開），不是即時合理價、正式交易門檻或可直接替代當前金融數據；正式 forward EPS source 未補齊前不擅啟用。
- 國際／台股研究保留美債利率、美元、景氣與 EPS 修正、外資／融資／集保、AI/CSP CAPEX／OCF／FCF、半導體供需、折舊與擁擠交易反證等；資料日與發布日分開，研究結論不得回填 canonical facts。
- OneBrain 方向是 canonical evidence → 確定性 Domain／Risk Cap／Single Action Authority → 精簡 Human VM 與可追溯完整 Decision Digest → 市場／籌碼／財報／產業／持股／資料稽核六研究領域與全域正反證檢查。AI 只讀既有核准資料，不創造、不寫回、不繞過正式行動權威；**方向已確認 ≠ production runtime 已完成**。
- 對外文字短／中／長期不固定 3/6/9 個月，具體時間長度／公式仍須 Gate。完整證據覆蓋、來源／as_of／缺失矩陣和證據 ID 不得為省 token 而被裁切。

## F. 最近投資資料資格治理 【2026-11-08 時點，已過時，見頂部更正】
- DEC-151～154：C4 以最近三個完整且符合可信公告時點的日曆月份、保留缺月與日期證據；#1075 A、#1076 B、#1077 D、#1079 E 已合併，未驗證月份鍵在合法有效資料時最高 5，無證據不得保底。全市場 `BATCH_SOURCE_MONTH_KEY_VERIFIED=False`、STRONG 暫時為 0 是 **fail-closed 過渡**，不是市場真實統計。
- DEC-154：一次性手動唯讀 FinMind 探針（#1084 Draft）、禁止洩漏 Token、自動排程／production writer；沒有合法 Secret 就不執行，真實月份及公告時點 **NOT VERIFIED**，不得因探針合併自行翻 verified。
- 缺貨缺值先 G1（#1083 Draft），原始分數與資料資格分離、呈現部分有效 n/4／缺值原因；**不動正式 composite／percentile／排名／權重**；G2、G3 僅為研究方案，不核准新硬門檻。
- `_candidate_pool` 末三列 vs C4 三目標日曆月尚需唯讀影響研究；`SHORTAGE_VERSION` 只設計回溯策略，未准改既有凍結 cohort。
- 財報缺任一必要腿不產正式綜合評級、不得把缺值當 0／中性（DEC-150）；缺貨獨立證據品質、財報差分、真實歷史績效、畫面診斷分母仍有待驗／裁示。
- #1038 PIT 歷史前視偏差阻塞，**NO MERGE**；資料發布/Cloud/真實 push、forward_test 端到端未全部驗證。

## G. 治理與換對話 【2026-11-08 時點，已過時，見頂部更正】
- ChatGPT 是**獨立治理／產品設計／投資語意審查層**；Claude Code 是工程施工、測試／非作者 QA、CI、PR merge、條件式 branch 清理及文件同步者（DEC-147）。
- 任何專案現況、下一步、裁示、PR Gate、提示語，必須獨立 GitHub Verification Gate；至少在選方案時比較三路徑：正確性／風險、速度、Token 成本。提示語附建議模型＋Effort（Minimum Sufficient Effort）。
- 靜默巡航：每批最多三項安全工作；不重複 subscription／CI pending；QA must-fix、最新 head CI 不綠、與既有 PR 同檔競爭、Layout／Risk Cap／PIT／Schema／新來源／不可逆操作即停手。
- 本次是**ChatGPT 對話交接，不是專案結案**。~~不要因換對話停止 #1083／#1084，~~（現行：#1083／#1084 已合併；後續為 FinMind 探針手動執行授權（客戶）與 DEC-154 待客戶事項。）也不要重做已合併的 #1075～#1082；正式 BACKLOG／HANDOFF 有優先級。
- 下一位 ChatGPT 首次回報應有：最新 GitHub Gate；五頁「已核准／已實作／真來源／缺口／驗證」矩陣；Old UI 能力重用；總經與 EPS×PE 研究；OneBrain Evidence/Risk Cap 完成度；#1083/#1084/1034/1038 QA/CI；**唯一下一個安全動作**。若本文件與 main 實況不同，立即標記 STALE 並以 main 為準。

## H. 保證與限制
這份快照**不宣稱**有登入真實 Streamlit Cloud、瀏覽手機實機、讀到 FinMind Token、跑真實營收驗證、執行 production 訂閱或獨立複驗所有歷史 UI 測試。先閱讀 repo，再檢驗 live head。
