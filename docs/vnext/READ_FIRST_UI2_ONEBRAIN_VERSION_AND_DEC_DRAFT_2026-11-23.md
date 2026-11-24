> **⚠️ 2026-11-24 版本更正：本文件下方關於 v1.0「仍 DRAFT／未核准」均為 2026-11-23 歷史狀態，現已被正式核准產品規格取代，切勿再以舊文字派工。**  
> **最新產品基準**：[`UI2_ONEBRAIN_FULL_PRODUCT_SPEC_V1_0_2026-11-23.md`](UI2_ONEBRAIN_FULL_PRODUCT_SPEC_V1_0_2026-11-23.md)（完整十一章）＋[`UI2_ONEBRAIN_PRODUCT_GOAL_V1_0_APPROVED_2026-11-23.md`](UI2_ONEBRAIN_PRODUCT_GOAL_V1_0_APPROVED_2026-11-23.md)（五項安全修正與差額），版本 `UI2-ONEBRAIN-PRODUCT-V1.0-APPROVED-2026-11-23`，正式 DEC-224。核准來源：[Issue #1199/7110182570](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110182570)。**核准的是產品目標，不是正式 UI／資料／Rules／模型施工或 Ready／merge／deploy**；遇有效 Active Contract 差額保持原 Gate。設計稿 v2 仍只是離線視覺稿；v1.1 Radar／Signal Log／Canonical Evidence Store 全 HOLD。

# READ FIRST｜New UI2 × OneBrain 版本指引及 2026-11-23 決策封存

> **閱讀入口（2026-11-23）｜DRAFT，非正式施工 Gate**。此文件是新增的版本索引與產品討論封存；**不取代 GitHub Issue #1199、已生效 DEC/Contract、ADR-OB-001、當前 main/PR/CI/QA**。任何後續工作先查 GitHub live 狀態，不可套用此日 SHA 作為永遠最新。

## 一、未來應讀哪個版本（務必先看）

| 類別 | 當前優先版本 | 身分與權限 |
| --- | --- | --- |
| **UI 視覺核對稿** | **設計稿 v2**：`stock_newui2_onebrain_design_review_v2.html`（使用者 2026-11-23 提供） | **目前優先閱讀的設計參考**，非正式程式或已發布產品。原檔 SHA-256 `efaa95f8da9f13d5fffc63ca4d0a57172fbc3eb9069ffabbe4a33d06e91538ae`；目前尚未納入 GitHub repository，須取得原檔才能直接開啟，不可臆測 repo 已有該附件。 |
| **本次帶閱讀說明的本機核對稿** | `stock_newui2_onebrain_design_review_v2_READ_FIRST.html` | 由設計稿 v2 追加顯眼「版本閱讀指引」橫幅；僅本次對話可下載；**不取代**原上傳檔、未在 GitHub 部署。 |
| **產品目標版本** | **v1.0**：薄 UI＋厚 Digest＋Topic Lenses＋What Changed | **DEC DRAFT**。檔名 v2 是「視覺稿迭代」，畫面 v1.0 是「產品目標」，**不是二擇一的軟體版本**。 |
| **未來候選版本** | **v1.1**：Catalyst Radar＋Signal Log | **HOLD**，不授權接正式新聞來源、LLM、交易或通知。 |
| **目前實際運作版本** | Repo 最新 main、各 PR 及現行有效 DEC/Contract | 一律即時核對；**設計稿不可替代 Real Preview、Cloud 或 production 驗收**。 |
| **舊視覺稿** | `stock_newui2_onebrain_design_review(1).html` 等舊稿 | 僅供歷史比對；不作為後續新設計的預設閱讀版本。 |

**後續對話/AI 接手的明確指示**：先讀本文件，再讀 [Issue #1199](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199) 最新留言、[2026-11-23 交接](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7099424817)、[永久平行規則](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-6967443454)、ADR-OB-001 與最新有效 DEC/Contract。**視覺比較優先用 v2 上傳稿；產品開發仍受實際批准的 DEC/Gate 支配。** 不要因 HTML 顯示「v1.0」而回退到舊版設計稿。

## 二、2026-11-23 已討論產品方向（提案封存，未正式生效）

**定位**：每天三分鐘知道今天變了什麼；30 秒首屏看重點；OneBrain 回答「市場有哪些被低估或尚未充分驗證的變化？憑什麼判斷？什麼新證據會證明我錯了？」

1. **薄 UI、厚 Digest、Topic Lenses**：五頁維持「📊市場／🎯標的／💼持股／👤我的／🗂資料」，Dark-only、390px 優先。首屏聚焦可信 Delta Strip、正式市場位階/Risk Cap 狀態、一句核心結論；四鏡頭「大盤／產業前瞻／持股健檢／反方風險」。短摘要最多 3 句且少於 100 字，不得省略完整 Digest 的 evidence、provenance、missing、counter-evidence。
2. **正式/研究軌隔離**：已核准的 Rules → Risk Cap → System Action → Decision Digest 唯一正式動作權威；OneBrain 僅解釋，不能改寫 Risk Cap、公式或發交易指令。「提前布局」為研究觀察而非自動買進。
3. **正式判定首版僅 FORMAL／UNDETERMINABLE 兩級**（提案，未生效）：該功能必要條件全部成立才為 FORMAL；任一該功能的必要條件未滿足 → 該功能 UNDETERMINABLE（無法判定），只影響該功能，不影響其他功能與已授權的事實顯示；研究事實可依既有 DEC 展示，但不得升格為正式位階/動作/趨勢。不是新演算法/風險分數的授權。
4. **What Changed**：僅同來源、同口徑、時間有效、可回查的前次快照，且指定訊號完整檢查後，才可顯示「今日無重大訊號變更」。否則誠實顯示「不可比較」；無變化不代表安全、亦非維持昨日策略。
5. **OneBrain 快取/成本**：以 evidence/digest + rule/contract + topic + model + prompt + as_of 等版本因子作有效性辨識；新關鍵證據或過期必失效。盤後預計算、開頁不同步呼叫 LLM 是目標設計，未批准 Provider/成本/Secrets/caller 前不得接線。
6. **LINE**：v1.0 僅規劃動作切換、風控、持股異常、資料斷線之確定性事件契約、去重/冷卻/失敗政策；真實推播、授權與部署 HOLD。
7. **v1.1 Catalyst Radar**：事件存在→去重判定新變化→真實產業/公司關聯→可否證的 Confirmation Trigger。事件可信度（RUMOR/REPORTED/CORROBORATED/CONFIRMED）≠ 投資命題可信度 ≠ 交易吸引力；不提供交易權限。
8. **v1.1 Signal Log**：不可變首見、價位/資料日、原始論點/反證、驗證與失效條件；30/60/90 日追蹤成功、失效、未到期、資料不足，禁止事後竄改原始預測。
9. **v1.1 資料/模型**：先合成或依法可使用的手動輸入；MOPS/SEC、新聞、逐字稿是否可下載/存儲/再利用需逐來源 DG-LIC/PIT/個資與著作權 Gate；Claude 等模型僅候選，不自動准許正式 Provider。

## 三、目前執行與 HOLD 邊界（勿因封存改派工）

- 原 A/B/C/Work 任務不中斷：A 既有 MVP Rules、B What Changed/手機線框、C Digest Contract、Work #1268/#1272/#1273 獨立 QA 與 Snapshot Feasibility；既有已 PASS 範圍不重做。
- 2026-11-23 封存核對快照 main `34f682b353f87dbc23ced27b13e011765f8f434a`；當時四支 Draft：#1268、#1272、#1273、#1237。**本段是歷史快照，請重新查 live GitHub。**
- #1268 專屬瀏覽器 Q3-8 證據、#1272 手機 UX 取捨、#1273 Work 非作者差額 QA 依原 #1199 closure ledger；不能自動 Ready/merge。
- NAS #1237、Cloud/production cutover、Auth/OAuth/Sheet/Secrets、真持股、OneBrain production caller、付費 Provider、LINE 真推播、資料 producer/new workflows、DG-LIC/PIT/COV/SCOPE/I1144、未核准正式市場位階/公式繼續 HOLD。
- 本文件僅作**文件封存及閱讀路由**；沒有批准新施工、正式 DEC 生效、新聞抓取、資料發布、PR merge、部署或 Secrets 變更。正式 DEC 需使用者於 #1199 明確核准並逐項列 Gate。

## 四、後續版本切換規則

1. **設計稿 v2 是現在的預設視覺參考**。若之後有 v3，必須記載檔案路徑/URL、SHA-256、差額、QA 和明確的「取代 v2」決議，才可改讀新稿。
2. **產品規格 v1.0 DRAFT** 只有 #1199 正式核准的條文才生效；v1.1 始終 HOLD，直至有獨立 Decision Gate。
3. 每次新 Session 先讀本索引→GitHub #1199 最新留言→main/PR/CI→有效 DEC/Contract；**不要用設計稿宣稱正式系統能力**。

_2026-11-23｜ChatGPT 總管依使用者要求封存；append-only 思路，未取代既有文件。_
