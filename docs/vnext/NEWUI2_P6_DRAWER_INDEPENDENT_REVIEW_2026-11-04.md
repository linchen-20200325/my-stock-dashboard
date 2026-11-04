# New UI2 P6／Mobile Drawer：ChatGPT 獨立線框審查及建議採用方案（2026-11-04）

> **決策性質**：使用者回覆「我看不到圖片 所以只能聽你建議了」，係委託 ChatGPT 依文字與已提交線框作專業建議，不等於使用者看過、逐一確認了實際視覺稿。**本文件記錄治理層推薦的實作前配置，仍須按照 repo 現有 Layout Gate／Auth Gate／QA／CI；不宣稱使用者親眼驗收圖像或完成程式施工。**
>
> GitHub 基準 main `f106a6af5e4b7695406396f84d1f1a1d9b29bd50`（#1015）；兩份線框：`docs/vnext/NEWUI2_P6_DATA_HEALTH_TEXT_WIREFRAME_2026-11-04.md` 與 `docs/vnext/NEWUI2_MOBILE_DRAWER_TEXT_WIREFRAME_2026-11-04.md`。並行 docs PR #1013、#1014 不得覆蓋。本文件不改 DEC-128～134 原文；建議內容不得暗中升格為投資規則。

## 1. 採用方案（針對完整 H/J 題的治理建議）

| 題號 | 建議 | 理由與限制 |
|---|---|---|
| P6 H-1 | A：Level 1 展開，Level 2／3 預設收合 | 一眼可讀資料狀態，細節不擠主頁 |
| P6 H-2 | 有條件 A：市場位階完整原因的使用者可讀版置 Level 2 | 必須與兩份 L0 逐字常數語意逐條比對，維持「廣度代理不計分／不回退第二引擎」；不改 L0 原文或再造判定 |
| P6 H-3 | A：Data Gap 顯示尚未提供，欄位擴充另外 Gate | 不補 now()、不創造 retrieved_at/source health |
| P6 H-4 | A：Unavailable 真錯誤採紅色 | 不能用紅色表示未接線／未評估，文字符號同時保留 |
| P6 H-5 | A：登入操作唯一入口在側欄／抽屜，『我的』只有清楚指引 | 正式 Auth 未接線時 disabled；不能有兩套登入動作權威 |
| P6 H-6 | A：桌機設定／稽核兩欄，資料健康度整列在下 | 沿已核准線框，手機依序單欄 |
| P6 H-7 | A：位階判定放 Level 2 說明，不混 Data State 五態 | Unable to Determine 不等於 Not Evaluated |
| P6 H-8 | A：Level 3 限安全、遮罩後識別碼 | 不顯示 raw exception、token、env var、module path 等 |
| P6 H-9 | A：Human UI 欄名「狀態」「接線」 | HTML／規格維持 Data State 與 Capability 欄位分離；字彙測試僅針對 health 容器特例 |
| P6 H-10 | A：健康度比率的分母只計正式已接線且適用評估的項目 | 額外分列總項數、可評估數、未接線數；Not Evaluated／未接線不可混成 OK 或失敗 |
| P6 H-11／Drawer J-6 | **B**：三處共用固定「⬜ 尚未提供」+ disabled 登入按鈕+「登入與 Sheet 操作尚未開放」 | 因無正式 auth truth，不得宣稱「⬜ 尚未登入」；FAKE 帳號示意與一般使用者可見真實狀態分開 |
| P6 H-12 | A：TWII 資料來源原文先保留 | 維持 P2 SPEC 與 TWII freshness 逐字一致；其「歷史／每日」不可暗示主圖歷史序列已接 |
| Drawer J-2／3／4 | A：桌機 rail 固定；手機切頁抽屜收合；半透明遮罩可點關閉 | 手機主頁保持完整寬度 |
| Drawer J-8 | A：☰ 選單（文字與 icon） | 讓觸控與讀屏辨識操作意圖 |
| Drawer J-9 | A：保留 ≥160px 門檻，暫以 844-53=791 為底部保留帶 | 等價沿用舊防擋規則；Android/Cloud 真機未驗，禁止稱已解決 Manage app 覆蓋 |
| Drawer J-10 | A：☰ 觸控 ≥44px、抽屜 min(82vw,320px)、導覽列高 48px 為**施工起始值** | 非最終像素驗收，仍需用 390px/1440px 實測並覆核安全區 |

## 2. Drawer 技術路線再次比較（不能只以 Token 最省作最終依據）

| 路線 | 開發／成本 | 功能性、可用性與風險 | Gate 結論 |
|---|---|---|---|
| A Streamlit 原生 sidebar | 可重用，但與現有 CSS、固定 desktop rail 衝突 | 目前 prototype 的 Esc／aria／自動收合未達 | 不建議 |
| C CSS checkbox + :has() | 速度快、不需 session key／rerun | **Esc 無法關、焦點不回 ☰、焦點進入不完整、切頁自動收合依 DOM 技巧、AppTest 測不到** | **候選，非無條件核准施工／正式上線** |
| B session-controlled 或經核准的語意型 drawer | 可能需要更改白名單或更多測試 | 有機會提高控制性，但原 prototype 也未達 Esc／焦點目標，不能直接視為安全備案 | 需比較可驗證的 accessible interaction |

**施工前強制驗收**：Escape 關閉、展開時焦點可辨識且可進入抽屜、切頁／關閉後焦點回合理操作點、關閉態不可被 Tab／讀屏誤讀、有效 accessible name、可透過鍵盤完成四頁導覽、reduced motion、390px 無水平捲動。若技術方案無法在目前 Streamlit 限制下符合，應 STOP 呈報，不得以『實作細節自行拍板』迴避基本可及性。需要新增 JS、改安全白名單則另過 Gate。

## 3. 用户在看不到圖像時的驗收方式

以**可在手機直接閱讀的每頁短版文字操作流程**加真實 screenshot 的審查清單交付，而不是只給長篇 ASCII 線框；明列每頁的第一屏、登入位置、資料健康度折疊層與主要 CTA。不能聲稱使用者親自看過或核准任何未顯示的畫面。仍以使用者提供的參考圖片為外觀基準；無法做 pixel-perfect parity 時揭露限制。

## 4. 施工分批

1. 先完成本 docs 審查及並行 PR 狀態調和，**不直接施工 UI**。
2. 下一個候選施工批：手機 drawer **先做可操作／可及性設計驗證**（不可用缺陷未解之前不能以 CSS-only 直接 Auto-Ship）。正式最小改動及守衛須保持 160px、單一導航及四頁切換；P6 不同批。
3. P6-a：L1 摘要及兩軸表、去重；P6-b：L2/L3、位階使用者說明。Data Gap／Auth／Digest schema／Risk Cap／System Action 全部分案 Gate。
4. 對資料語意、登錄來源、OneBrain Evidence/Digest 保持**雙投影**；UI 缺欄不得當 OneBrain Evidence 已完整。

## 5. 未驗項目

- 現有 #1015 線框 P6 的 17～20 項資料清單尚無真正 render 截圖或 service 呼叫驗證。
- CSS-only drawer 的原型僅 Chromium 模擬，未在 Android／iOS／Streamlit Cloud 與 Manage app overlay 進行實機覆驗。
- 本 docs QA 不等於 P6、Drawer 實作已獲驗收；CI、真機、accessibility 仍是後續交付必要條件。
- 有關已合併 main `f106a6af` 的 workflow checks，在本次 GitHub 查詢仍 in_progress；不將其說成獨立核實 success。