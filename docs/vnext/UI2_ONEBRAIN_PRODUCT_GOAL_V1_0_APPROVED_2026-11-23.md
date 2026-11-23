# New UI2 × OneBrain｜產品目標 v1.0 正式核准基準

> **基準標記：UI2-ONEBRAIN-PRODUCT-V1.0-APPROVED-2026-11-23**  
> 核准日：2026-11-23；回存日：2026-11-24（Asia/Taipei）。**APPROVED：產品方向、五項安全修正與階段優先級；NOT A CONSTRUCTION / MERGE / DEPLOY GATE。**  
> 權威來源：[客戶核准紀錄 #1199/7110182570](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110182570)（created 2026-11-23T18:27Z）、[客戶追加協作規則（三方案最小化）#7110402272](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110402272)（18:36Z，晚於核准紀錄、僅適用後續卡片）、[G-F3=A2-i #7109632982](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7109632982)（18:05Z，早於前兩者）。本文件**取代 2026-11-23 READ_FIRST 中 v1.0 產品方向仍 DRAFT 的說法**，但不取代任何既有有效 DEC、ADR-OB-001、Active Presentation Contract、資料／規則／來源 Gate。設計稿 v2 是視覺參考版號，**非**產品 v2 或程式上線驗收。

## 0. 產品目的與權威
- 讓使用者「每天三分鐘知道今天變了什麼」，手機 390px／30 秒首屏聚焦可信變化與缺口；New UI2 維持五頁 **📊市場／🎯標的／💼持股／👤我的／🗂資料**，Dark-only，極簡首屏；薄 UI、厚 Decision Digest。
- **資料 ≠ 規則 ≠ AI 推理 ≠ UI**。已授權資料→驗證→確定性 Rules→Risk Cap→System Action→Decision Digest→UI/OneBrain。正式權威只有確定性 Rules／Risk Cap／System Action；AI 只可基於證據解釋、摘要、提出可驗證疑問，不可改寫、補算、繞過或發出正式行動。完整來源、資料日、缺值、反證、狀態與可追溯性不得因首屏縮減而消失。
- **missing≠0；unknown≠safe**。None、NaN、±Inf、STALE、PROXY、fetch_failed、無證據／無法比較皆誠實降級；不說「0／正常／安全／續抱／無變化」作替代。Real 不能以 FAKE 補畫。

## 1. 五項安全修正（核准產品目標；不得自行解鎖施工）
1. **呈現 Level 0–2，L1 不改正式決策**：Level 2＝原正式判斷必要條件全滿，才可由**既有規則**得正式結果；Level 1＝核心價格證據有效、輔助證據例如廣度不足時，最多是**有來源／缺口揭露的研究參考**，**絕不**生成正式市場位階、System Action、放寬或改寫 Risk Cap；Level 0＝核心證據缺、過期或不能判定時，不給投資結論。此處僅**呈現分級**，不是新公式、正式三態／DataStatus、信心分數、買賣規則。FORMAL／UNDETERMINABLE 二分是 [#1275](https://github.com/linchen-20200325/my-stock-dashboard/pull/1275) DRAFT **擬議**的判定軸（現行 `JudgementState` 僅 `UNDETERMINABLE`、無 `FORMAL` 成員），Level 1 不是它的第三值；正式文案／對映仍須 DEC-124、DEC-081/092 等 Contract Gate。**#1275 現況**：Draft、DEC 未生效；四項 Must-Fix 已修（head `17a9d32b`／`13fae4d4`，非作者差額 QA PASS），Level 0–2 對照已加於 §3A（head `6d4c9f2f`，差額 QA PASS、同 head CI success）；剩餘＝客戶正式 DEC Gate 與呈現／文案裁示。
2. **Delta Strip／What Changed 比較前置**：📊市場與 💼持股首屏的今日變化列僅在當期與前次**同來源、同口徑、有效日期、可回查快照、PIT／授權／freshness 允許且指定訊號完整檢查**時可比較；「今日無重大訊號變更」只在全部證據符合時才可說，且**不等於安全或續抱**。前次不存在、資料過期、跨來源/口徑、時間不明或訊號未全時顯示**不可比較**；核准目標文案：「⬜ 暫無足夠資料比較今日變化」。此為目標 wording；正式 FieldVM／DEC-124／Active Presentation Contract 的新字樣需獨立 Copy/Contract Gate；目前不得直接插 UI 或建立新正式 compare pipeline。
3. **OneBrain 四鏡頭、嚴格短摘要、完整證據**：主題膠囊為 **大盤／產業前瞻／持股健檢／反方風險**。首屏核心觀察**最多 3 句、嚴格少於 100 個字**（數字限制是產品驗收目標，精確計數口徑與強制揭露徽章的預算分配尚待 Contract/Copy Gate）；內容必有 evidence→Digest fact→rule/source/as_of/status 的 trace，可展開完整證據、缺項、provenance 與反證。無反證資料就明示不可判定，不能由 Risk Cap 或 LLM 憑空補反證。持股缺真資料須降級，不可假裝已接。
4. **快取有效性完整且開頁零同步 LLM**：快取政策/鍵至少辨識 **Digest 與 Coverage／evidence 內容及狀態、新鮮度或其重新評估依據、資料日期／as_of、來源與 REAL/FAKE origin、schema 與 rule/risk cap/system action 版本、active contract 版本、Topic Lens id/definition version、model id、prompt version**；缺維度、未知 schema、日期或來源不明須 fail-closed；新證據、過期、規則或提示/模型變更須失效。新鮮度不得只靠舊 hash 而漏判，應於取用時依已核准 freshness 規則重新評估；None 不可省略或補 0。預計算／快取 miss 回退到已核准規則式輸出並標非 AI（無可用證據則「無法判定」）；開頁不得同步呼叫 LLM。**僅為契約目標**，沒有核准新 provider、caller、批次工作或持久快取。
5. **LINE v1.0 僅限設計，v1.1 雷達 HOLD**：v1.0 只可定義**動作切換／風控觸發／持股異常／資料斷線**的合成確定性事件契約、去重、冷卻、失敗政策。正式 LINE 推播、用戶授權、帳號綁定、Secrets、production caller 都不放行。**Catalyst Radar／Signal Log／Canonical Evidence Store** 均屬 v1.1，維持 HOLD。

## 2. What-If 僅唯讀規劃
只規劃記憶體中的唯讀合成試算，不回寫 Google Sheet、無真持股接線、無訂單／正式 System Action、無自行創設 Risk Cap。無持股資料顯示目標提示「⬜ 需先接入持股」；正式新文案/呈現仍經 Copy Gate。

## 3. v1.1 明確 HOLD／不預先施工
- Catalyst Radar（研究觀察）：事件存在→同源去重的新變化→真實公司／產業曝險關聯→可否證 Confirmation Trigger 與失效條件；提前布局≠買進。
- 三軸不可合併：事件可信度 RUMOR/REPORTED/CORROBORATED/CONFIRMED ≠ 投資假說可信度 ≠ 交易吸引力。
- Signal Log：不可變首見日期、當時價位／資料日、原始假說、反證、確認／失效門檻；30／60／90 日回顧成功／失效／未到期／資料不足，不得事後改原始論點。
- Canonical Evidence Store 只作未來方向；不得新接新聞、MOPS/SEC 抓取、producer、workflows、儲存／散布，逐來源須通過合法授權、版權、PIT、個資及 SCOPE Gate。手動輸入亦不豁免權利限制。
- 其他既有 HOLD：真持股/Sheet/OAuth、Cloud 切換、NAS #1237、正式 LINE 通知、付費模型/OneBrain production caller、未核准外部來源及投資公式、停止中的 workflows、任何未獨立解鎖的 PR/Gate。

## 4. 與有效 Contract／DEC 的最小差額（不是自行改寫已生效規則）
| 差額 | 現有邊界 | v1.0 核准目標 | 後續獨立 Gate |
|---|---|---|---|
| Level 0–2 | #1275 Draft（四 Must-Fix 已修、§3A 對照已加並過差額 QA，DEC 未生效）；正式判定沿用原有效 DEC，DEC-124 禁新增狀態 | 呈現層標明 L1「研究參考」（核心價格證據有效、輔助證據不足時最多如此），正式判定不變 | 客戶對 #1275 的正式 DEC Gate；正式呈現/文案另裁 |
| Delta Strip | PIT、來源、前次快照／口徑證據缺；Active Contract 的 FieldVM 文案仍有效 | 首屏有不可比較分支，不因空值稱無變化 | C 比較純契約研究；B 線框／Copy Gate；Work 獨立 PIT QA |
| OneBrain | Digest v1 frozen；G-F3=A2-i；S1/G-F4 未授權實作；production caller 0 | 四鏡頭、≤3句、<100字、可追溯短投影 | C docs-only 設計與非作者 QA，既有 G-F4/Topic Lens Gate |
| Cache | Provider/caller／真快取未授權 | 全維度失效與取用時新鮮度重估、零同步 LLM | C 契約差額，不新增 caller |
| LINE/What-If/v1.1 | 真持股、正式通知、雷達／新聞/Store 均 HOLD | 設計／唯讀規劃與 v1.1 明確隔離 | 各自未來獨立授權，不併入本文件施工 |

**G-F3=A2-i 特別保護**：Digest v1 事實仍為原本的 MISSING/NO_INPUT/schema；STALE／fetch_failed 的原因只容於 coverage/audit 可稽核側車，不升格成新事實／行動證據，不能支持 Risk Cap 或 System Action；S1 僅 G-F4 設計、未批准 K2 或 code。

## 5. 協作執行規範與派工
- 每輪先核即時 main、Open/Draft PR head/base、五項 CI 含 Slow AppTest step、reviews/threads、#1199 最新與有效 DEC/Contract。單檔單 writer；只做核准差額、非作者 QA、已 PASS 不重做；**文件批准不等於 Ready／merge／deploy**。
- 有真正可選解法時才簡短比三案（各 2–3 行優缺點/風險）；**三案全部必須符合最新 DEC 與誠實降級紅線**，選最小、可回退者；純文件修訂、固定 Must-Fix、QA 不硬湊三案，不增新 Gate。
- 每張卡必有以下三行：
  - **【範圍鎖定】**只改本卡授權檔案／指定差額；不重構、不跨線共編、不解 HOLD、不自增 Gate。
  - **【誠實降級】**缺值、NaN、STALE、不可比較依有效契約揭露或標 NOT VERIFIED；不補 0／假裝 fresh、安全、續抱；Real 不由 FAKE 補。
  - **【退回門檻】**DEC/Contract 衝突、授權不足、Must-Fix 未清、QA/CI FAIL、head/base 證據過期即停在現有 Gate，列最小解除證據；不硬上 Ready/merge/deploy。
- **A**：#1275 後續（四 Must-Fix 與 §3A 對照已完成；僅餘客戶正式 DEC Gate 後的呈現／文案對帳）；不碰規則／公式。
- **B**：390/1280 極簡首屏／Delta Strip／四膠囊線框與六態、不可比較及缺值文案差額；正式 Copy/UX Gate 前不改 UI；既有 R1/手機 CI 分案。
- **C**：Digest/Topic Lens/Cache 設計契約、G-F3 A2-i 與 G-F4 S1、What Changed M1/M2 僅設計；不改 Digest v1 或 caller。
- **Work**：非作者獨立差額 QA（#1275/#1268 與相關 head）、PIT／可比性、有效 Contract 與資料來源事實核證；不當作者或放行 HOLD。
- 最後附修改檔、exact SHA、差額、測試/CI/Slow、非作者 QA、HOLD 與下一 Gate，append-only 存 #1199。

## 6. 版本優先序
**本 v1.0 正式產品目標** ＞ 2026-11-23 舊 v1.0 DRAFT 討論描述（僅就**產品目標的核准身分與內容**）。**現行有效 DEC/Contract、原規則與明確 Gate** 仍是正式系統行為的優先基準；遇衝突先記錄差額、停止受影響施工，不能以本文件覆蓋有效判定。設計稿 v2 與產品 v1.0 不互相替代。#1199 為決策與 QA 追加紀錄 SSOT。
