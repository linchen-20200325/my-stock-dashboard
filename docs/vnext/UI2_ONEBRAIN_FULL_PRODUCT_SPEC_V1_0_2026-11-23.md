# New UI2 × OneBrain｜v1.0 完整產品規格書（2026-11-23 核准）

> **Canonical Product Baseline:** `UI2-ONEBRAIN-PRODUCT-V1.0-APPROVED-2026-11-23`  
> 版本：v1.0；原核准日期：2026-11-23；文件存檔：2026-11-24。Repo：`linchen-20200325/my-stock-dashboard`。  
> **地位：APPROVED PRODUCT SPECIFICATION / NOT A CONSTRUCTION, MERGE, SOURCE, NOTIFICATION OR DEPLOY GATE**。依客戶提供之《投資股票 UI2＋OneBrain 產品規格書》十一章整合，與 [#1199 核准裁示](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110182570) 及 [三方案紀律](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110402272) 一致；核准的五項安全紅線不得弱化。產品基準取代 2026-11-23 舊 READ_FIRST 內「v1.0 仍 DRAFT」的**產品方向敘述**，不取代現行有效 DEC、ADR-OB-001、Active Presentation Contract、CLAUDE.md／PROCESS.md 或正式施工 Gate。  
> 歷史 main `34f682b3`／`c75ec8f` 不是永久最新，開工前重核 main/head/base/CI/QA。視覺核對稿 `stock_newui2_onebrain_design_review_v2.html` 是離線設計稿，不能當部署證據；其原檔當時未入 repo。

## 第一章｜產品定位與權威邊界

**目的**：建立台灣股票為主的個人智慧投資決策輔助儀表板，逐步整合台股、美股、國際總經、產業、籌碼、公司基本面及使用者持股；以經授權可追溯規則判斷風險／持股動作，OneBrain 對短中長期與反證作中文有據解釋，回答「目前發生什麼、對我有何影響、下一步應觀察什麼」，目標「每天三分鐘知道今天變了什麼」。

**最高產品安全界線**：`資料 ≠ 規則 ≠ AI 推理 ≠ UI`。已核准資料與驗證→既有確定性規則→Risk Cap／風控→System Action Aggregator／State→Decision Digest→UI／OneBrain；Risk Cap、正式 System Action 的**唯一權威是確定性規則**。OneBrain 只能有根據地分析／解釋，不能自行設計交易規則、改寫正式 Risk Cap 或命令交易。「提前布局」只是研究觀察，非自動買進。

新 UI2 目前不是完整正式投資系統，也不是自動下單系統。真持股、Google Sheet OAuth、付費模型 production caller、正式 LINE、Cloud 切換與 #1237 NAS 均 HOLD。

## 第二章｜系統架構與兩軌隔離

```text
合法且經核准的來源 → 取得/驗證/標準化 → 規則 (ruleset_version)
  → Risk Cap → System Action Aggregator → System Action State → Decision Digest
  ├─ New UI2 五頁／Level 0–2 呈現／四個 Topic Lenses
  ├─ LINE 合成事件契約（v1.0 只設計；正式通知 HOLD）
  └─ OneBrain 有據解釋（正式 Provider/caller HOLD）
未來 Canonical Evidence Store：僅 v1.1 候選，HOLD，不冒充當前資料層
```

- Data 負責事實、來源、日期與狀態，不能填缺值或把舊資料視為今天。
- Rules/風控專屬公式、分類、門檻與正式約束；Aggregator 僅彙整既有動作，不能自創買賣策略。
- Digest 保留完整證據、缺值、時間、來源與反證；UI 縮減不能回推／改動原始決策；OneBrain 不擅取新來源。
- 獨立 Preview 入口 `streamlit run app_ui2.py`；`app.py` 仍是舊入口、非 UI2 production cutover。`src/services/ui2/real_feed.py` → `real_canonical.py` → View Model → `src/ui2` → Streamlit。Real 不可回退 Fake 數值。

## 第三章｜New UI2 五頁

共用導覽順序：**📊 市場 → 🎯 標的 → 💼 持股 → 👤 我的 → 🗂 資料**；OneBrain 不新增第六個主頁。手機 390×844 優先，兼顧 1280×900／1440×900；首屏極簡，明細可展開但不可丟證據。

### 3.1 📊 市場
**v1.0 新產品目標首屏**（目標，非現行順序）：① Delta Strip（今日變化）②市場位階／Level 0–2 *呈現*、正式 Risk Cap、正式 System Action 三大核心狀態（不存在時缺值）③ OneBrain 四主題膠囊及短核心觀察。次要展開：台股加權指數／同源 20 根日 K（**K 棒色依 DEC-156：以當日開盤對收盤決定——收>開紅、收<開綠、收=開灰十字線；不以前收決定 K 色，前收漲跌幅另為獨立指標（取合法前收資料、獨立語意），不得與紅綠 K 混用；最近 20 根只取已驗證完整日 K，不足不補假棒、不補 0**；OHLC 自洽）、四格決策檢核、VIX、10Y 美債、利差、DXY、台灣 PMI、前夜美股、產業強弱／風險條。僅為規劃的項目**不能**當已接入顯示。

> **現行契約 vs 本章新目標（差額；不修改 Active Contract）**：現行 📊 市場順序依 DEC-157：同一組首屏狀態／今日主要風險 → **日 K 主圖／空槽 → 核心指標卡 → OneBrain Outlook**（DEC-157 只取代 DEC-133 G-3 中「OneBrain 的位置」；Active Contract §3.1 該列文字仍是 DEC-133 舊序，原文保留）。Active Contract §3（含 DEC-130 (b)）：📊🎯💼 整頁 0 個完整 evidence expander；👤 稽核面入口預設收合；DEC-209 的例外僅限 🗂 **Real-data Preview 資料頁**預設收合的「各項明細」。本章把 OneBrain 移到首屏（③），與第八章「證據預設展開」，都是**新目標、與現行契約不同**，須先過原 Active Contract／線框 Gate（草稿先行），**不得以本規格直接改 UI**。保留不變的目標：完整證據可追溯、不因首屏縮減而丟證據，以及上述新首屏目標本身。

### 3.2 🎯 標的
兩模式：「市場精選」（產業機會、候選股、正式篩選條件）與「即時查一檔」（股票代號輸入後的公司基本面、估值、籌碼、趨勢／產業／市場環境）。現有查詢 P1 功能不等於行情 P2 已接線。**What-If** 僅規劃唯讀記憶體、合成輸入，未來重用已核准持股集中度及 Risk Cap 規則評估擬議股數／金額，禁止寫 Google Sheet、下單、覆寫 HoldingsReadSnapshot 或自製正式動作；真持股未接顯示「⬜ 需先接入持股」。新正式文案另待 Copy Gate。

### 3.3 💼 持股
目標包含組合選擇、持股清單、集中度、成本／現價／損益、正式 Risk Cap／正式規則動作、不可評估部位與原因、OneBrain 持股健檢、Delta Strip；真持股/OAuth 未通不得報「0 檔」「沒有持股」、不得計算虛構曝險。

### 3.4 👤 我的
規劃帳戶／Google Sheet 授權、觀察清單、通知設定、Decision Digest／Rule Registry 唯讀稽核；OAuth、Sheet、真通知全部保持 HOLD。

### 3.5 🗂 資料
目標固定八個「資料可得性/新鮮度」項目（卡與 K 同來源不雙算）：台股加權指數、外資買賣超、融資餘額、M1B／M2、台灣 PMI、板塊資金流、市場位階、基本面季報。原設計盤點：台股既有讀取路徑；市場位階有讀路徑但常無值；其餘尚未正式接入。不得將「有讀取程式」說成「資料有值」或「已取得授權」。

## 第四章｜外部資料、持股、AI

現有 TWII 路徑參考：Yahoo `^TWII` → `data_cache/twii_ohlcv.parquet` → `macro_cache_reader` → `market_twii_view_service` → UI2 Real Feed；市場位階讀 `warroom_summary/macro_state.json/risk_cap_state.json` 經 `allocation_service.get_macro_regime`，缺廣度與時點契約通常無可用結果。**程式存在≠正式來源授權／PIT 驗證／實際接入／Cloud 可用**。合法安全直接連線優先；有具體直連失敗或雲端 IP 限制才評估 NAS，NAS 不得繞過政策，#1237 HOLD。

Sheet 目標：登入→授權→組合選擇→欄位/代碼/值驗證→`HoldingsReadSnapshot`→adapter→正式規則/Digest→OneBrain；僅規劃，只讀不寫；未登入/失敗 ≠ 零持股；token/私人持股不入公開 repo、PNG、logs、未授權 AI。

模型架構採可替換 Provider；Claude 只為候選、OpenAI／Gemini 待核准、FakeProvider 僅合成測試。正式呼叫需 model/provider 設定、成本/token cap、超時重試、證據白名單、output schema、grounding、稽核及降級；**現在不開 production caller**。

## 第五章｜資料來源、更新、新鮮度

目標事實欄位 `value/unit/source/as_of/fetched_at/published_at/status/coverage/error/license-or-usage-policy`（**非宣稱現行每一來源已有全部欄位**）。台股/美股依交易日，籌碼依發布日，營收及財報依實際公告日，持股依用戶更新／有效讀取；不可僅因今天 fetch 就升為今日發布。TWII 現行「7 日曆天內、到第 8 日進入過期」作歷史既有契約描述；**不可把研究候選 3 交易日擅自取代**，實際生效值仍須以 live DEC/程式核實；published_at/PIT 缺失不可用於正式跨期比較或回測。

## 第六章｜資料可信度與 Level 0–2

嚴格分離 DataStatus、判斷 availability/result、capability（有無接線），不增加新的正式狀態列舉，不以 UI 字詞取代原有效 `FieldVM`／DEC-124。
- 過期：⚠ 過期 N 天；不確定：⚠ 可能已過期；缺：⬜ 資料未取得／資料未備；來源錯：🔴 來源目前不可用；未評估：⬜ 尚未評估；無結論：⬜ 無法判定；未接：⬜ 尚未提供。**皆為 v1.0 目標呈現詞**；實際新字樣先核 Active Contract 的 Copy Gate。
- **Level 2**：所有原正式必要條件成立，才照既有規則得正式結論，並揭露日期來源。
- **Level 1**：核心價格證據有效、輔助證據（例如廣度）不足時，Level 1 最多是有來源與缺口揭露的研究參考；**不得新增正式市場位階、正式第三狀態、動作或放寬 Risk Cap**。
- **Level 0**：核心證據不足、過期／不可用，禁止投資結論。
- 均不構成新信心分數、公式、擇時判斷或買賣權限；missing≠0、unknown≠safe、STALE≠fresh、Real≠FAKE。
- **與正式判定軸／#1275 的關係（據實，2026-11-24 查證）**：FORMAL／UNDETERMINABLE 二分是 [#1275](https://github.com/linchen-20200325/my-stock-dashboard/pull/1275) DRAFT **擬議**的兩級判定軸，**不是已存在的正式軸**——現行 `shared/ui2_contract/models.py` 的 `JudgementState` 只有 `UNDETERMINABLE`、**無 `FORMAL` 成員**（main `c75ec8f4` :32-49）。#1275 現況：Draft、DEC 未生效且無編號；Work 原四項 Must-Fix 已修（head `17a9d32b`／`13fae4d4`，非作者差額 QA PASS，見 [7110815346](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110815346)）；Level 0–2 對照已加於 #1275 §3A（head `6d4c9f2f`，非作者差額 QA PASS、同 head CI 五項 success，見 [7111783774](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7111783774)；該對映屬 INFERENCE，待客戶確認）；剩餘＝客戶正式 DEC Gate 與呈現／文案裁示。

## 第七章｜正式規則與 v1.0 MVP

正式次序：有效合法證據→正式 ruleset（帶版本）→Risk Cap→既有動作分支→System Action Aggregator→正式 State→Digest→OneBrain 解釋。Aggregator 不自製加碼、續抱、換股、減碼的計算邏輯；正式資料不足則「無法判定」而非風險零。v1.0 最小 ruleset **先盤點既有有效規則**，不授權未批准季線／年線／月線斜率、成長/PE 門檻、權重、排行或新買賣公式；Digest 的 frozen v1 schema 及各 ruleset_version 受既有 DEC 保護。

## 第八章｜OneBrain、短摘要、快取

四個 Topic Lenses：**大盤、產業前瞻、持股健檢、反方風險**。分析須可追溯支持／反證、短中長期與缺口。不得把事件可信度（v1.1 的 `RUMOR/REPORTED/CORROBORATED/CONFIRMED`）混成投資命題可信度；「VALIDATED_IMPACT」若作研究候選亦不取代正式規則。無反方證據 → 誠實「無法判定」，不得從 Risk Cap 猜出反證。

**首屏 Text Budget**：核心觀察 **≤3 句且 <100 個字**；行動／觀察重點目標 ≤3 點且每點 <25 字；其他說明／證據／反證／缺項目標為**完整可追溯，且（本目標）預設展開**——此「預設展開」與 OneBrain 首屏位置同屬**新目標、與現行 Active Contract §3 不同**（📊🎯💼 無完整 evidence expander；👤 稽核入口預設收合；DEC-209 例外僅 🗂 Real 資料頁「各項明細」），展開方式與位置須先過原 Contract／線框 Gate。字數等這些是**產品目標**，是否計入強制揭露 badge、計數字元口徑及欄位投影須既有 Contract/Copy Gate 明確落地，不自行裁定為已生效型別或驗收測試。完整 Digest 不刪；每短句可追溯 evidence-id→fact→rule/source/as_of/status。若證據不足或 ground fail，維持規則式摘要或「無法判定」，AI 錯誤不導出安全。

**預計算＋完整快取失效鍵**：開頁零同步 LLM；成功的預計算輸出可在合法 Gate 後快取，鍵涵蓋 Digest/Coverage/evidence 的內容與狀態、source、as_of／有效日期、REAL/FAKE origin、schema、ruleset/risk_cap/system_action、contract、topic id/lens_def_version、model、prompt 版本；缺維度／unknown schema／invalid origin fail-closed；過期與新證據必失效。若 hash 排除抓取時間，**取用時仍重新判定 freshness／TTL**；None 必須獨立編碼。cache miss 只能顯示合約允許的非 AI 規則式摘要或無法判定，不可顯示過期 AI 充新。**不授權新 provider、API、離線排程或持久快取施工**。

## 第九章｜介面、Delta Strip、LINE

主要尺寸 390×844；桌機 1280×900／1440×900。Real/FAKE 隔離，真頁載入失敗不可拿示範數值補圖。

Delta Strip 置 📊／💼 首屏，只有**當期與前次相同來源/口徑、授權/PIT、有效日期、新鮮度、可追溯且完整指定訊號**才可說「今日無重大訊號變更」（也不代表安全或維持昨日策略）。前次缺、發佈時點未證、回填、不一致或未完成時固定落入不可比較；**目標文案**「⬜ 暫無足夠資料比較今日變化」。不得把未有 compare pipeline 的 UI 顯示說成驗證 PASS。

LINE **v1.0 只允許合成事件契約與設計**：動作切換／風控觸發／持股異常／資料斷線，需去重、冷卻、用戶同意/權限與失敗政策的設計；AI 自由文字不得單獨觸發。實際通知、帳號、事件 producer、Secrets、部署均 HOLD。

## 第十章｜v1.1（全部 HOLD）

**Catalyst Radar** 為獨立研究軌，四道防線：存在→同源去重確認新事件→真實公司/產業曝險→可否證 Confirmation Trigger/失效條件；**不是正式交易權威**。事件可信度 `RUMOR/REPORTED/CORROBORATED/CONFIRMED`、投資命題可信度及交易吸引力三軸分離。

**Canonical Evidence Store** 僅候選非 AI 結構化、去重、主題檢索方向；手動/合成、MOPS/SEC 亦受授權、著作權、個資、PIT/SCOPE、儲存散布 Gate。不得新增抓取/儲存/production。

**Signal Log** 預計不可變首見時間／當時價位資料日／原論點與反證／可否證條件，追蹤 30/60/90 日成功/失效/未到期/無法判定，禁止事後改寫原始預測。v1.1 未獲任何施工、真通知或模型授權。

## 第十一章｜施工治理與派工規範

每輪 GitHub Verification Gate：main SHA、Open/Draft PR head/base、五項 CI（明確包含 Slow AppTest step）、reviews/threads、#1199 最新與有效 DEC/Contract。已 PASS 且同規格同 SHA 不重做；單檔單 writer，最小差額、非作者 QA，Ready/merge/deploy 另依原 Gate。#1272 已 merge，勿重派舊合併。

**三案**：僅真有合法解法選擇才列三案（每案 2–3 行：優點/缺點/風險），三案均符合最新 DEC/缺值紅線，取最小且可回退者；固定 Must-Fix、docs-only、差額 QA 不硬湊三案，不自增 Gate。

**所有 A/B/C/Work 卡片三行硬約束（逐字）**：
- 【範圍鎖定】只改本卡授權檔案／指定差額；不順手重構、不跨線共編、不解鎖 HOLD、不自行新增 Gate。
- 【誠實降級】缺值、NaN、STALE、不可比較等依有效契約顯示或標 NOT VERIFIED；不得補 0、冒充 fresh／安全／續抱，Real 不以 FAKE 補畫。
- 【退回門檻】遇最新 DEC/Contract 衝突、授權缺失、指定 Must-Fix 未清、有效 QA FAIL／CI FAIL、head/base 改變而證據失效，停在現有 Gate，明列阻塞及最小解除證據；不得硬上 Ready/merge/deploy。

**任務邊界**：A＝#1275 後續（四 Must-Fix 與 Level 0–2 §3A 對照已完成並過差額 QA，見第六章；餘為客戶正式 DEC Gate 與呈現／文案裁示）；B＝首屏 Delta/不可比較/OneBrain 字數線框、原 R1/手機 CI；C＝S1/G-F4（G-F3=A2-i）、Topic Lens＋快取和 What Changed M1/M2 **設計**；Work＝最新差額非作者 QA、TWII 可比性與 PIT、Contract 抽查。不改舊已 PASS、不新增實作 Gate。

**HOLD 清單不因本文件改變**：#1237、真持股／Sheet／OAuth、Cloud cutover/R1～R4、外部新行情/新聞來源、Secrets、正式 OneBrain 付費模型 caller、正式 LINE、v1.1 雷達/Signal Log/Evidence Store、未核准規則、PR #1237 merge、停用 workflows（包括 DEC-185）、比較 producer／歷史寫入。遇現行 DEC 或 Active Contract 衝突，**將差額送原 Gate**，而非宣告產品方向可直接施工。

## 規格差額索引
| 類別 | 已核准產品目標 | 非本次授權／待原 Gate |
|---|---|---|
| Level 0–2 | L1 僅研究呈現（核心價格證據有效、輔助證據不足時最多是有來源與缺口揭露的研究參考），L2 原正式規則，L0 無結論 | 第三正式狀態、新 DataStatus、動作、Risk Cap 變更、#1275 正式 DEC Gate（四 Must-Fix 與 §3A 已修並過差額 QA；Draft、DEC 未生效） |
| Delta Strip | 有有效雙快照才可比較；否則不可比較 | 真快照持久化、未經 PIT 授權的跨期比較、直接插新 FieldVM copy |
| OneBrain | 四主題、短觀察、trace、完整快取失效 | Digest v1 變更、LLM caller、provider、快取 producer |
| LINE / What-If | 合成事件設計／記憶體唯讀規劃 | 真通知、真持股、寫 Sheet、交易 |
| v1.1 | 題目與研究規劃 | Radar/Signal Log/Canonical Evidence Store 正式施工 |

**指定參照**：[#1199 SSOT](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199)；[正式產品裁示 7110182570](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110182570)；[執行規則 7110402272](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110402272)；[G-F3=A2-i 7109632982](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7109632982)。