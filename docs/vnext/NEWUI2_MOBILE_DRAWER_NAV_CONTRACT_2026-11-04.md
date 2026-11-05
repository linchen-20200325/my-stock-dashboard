# New UI2 手機抽屜式主選單與 Google 登入入口（2026-11-04）

> ⚠️ **SUPERSEDED IN PRESENTATION BY LATER CUSTOMER DIRECTION（2026-11-06）**：客戶最新要求為**手機與桌機頂部五頁導覽、Google Sheet 下拉置頂、右上帳號入口，取消左側收縮欄／☰ Drawer**。本文件的「抽屜是現行導航」及「四頁上限」**只保留作 2026-11-04 歷史決策與安全測試依據，不得再當作未來施工的有效布局指令**。已施工的 JS_V4、keyboard/focus/inert/guard 仍須在新導航正式 Gate 與等價瀏覽器/可及性回歸通過後，才可安全遷移或退役；不得為了消除衝突而直接刪除 JS 或測試。新提案見 #1030 文檔與最新 PR 說明；尚未代表 production 已改。
>
> 客戶需求：手機畫面的底部四格受到 Streamlit Manage app 浮層遮擋，希望保留舊版左側選項和 Google 登入按鈕。ChatGPT 提供常駐側欄／抽屜／雙導航三方案，建議「☰ 可收合左側抽屜，桌機維持固定左側 rail」，客戶答覆「好」。這是新方向的確認，不代表詳細線框或 OAuth 已核准施工。
>
> 與舊 DEC-128～133（含 DEC-129 等）「手機只有底部四格」衝突時，以此後出的客戶要求為準；歷史裁示仍 append-only。四頁名稱、桌機導航及投資語意不變。此文件為 Active Contract 的手機導航變更附件；程式修改另需線框 Gate。

## 四頁與操作

| 畫面 | 新手機要求 | 既有規格如何處理 |
|---|---|---|
| 首屏 | 左上角 ☰，收起時主內容全寬 | 不可常駐側欄把 390px 主內容擠窄 |
| 抽屜展開 | 顯示 📊 市場／🎯 標的／💼 持股／👤 我的 | 保持四頁，不增第五頁 |
| Google 區 | 登入入口及登入狀態顯示區 | 正式 Auth 未接線時按鈕 disabled，不能假裝已登入或直接沿用 FAKE 情境 |
| 底部 | 不再以固定底部四格作唯一導航；採單一抽屜主導航 | 避免底部固定列可能被 Manage app 遮擋（客戶截圖回報，尚未重現）而無法換頁；不要雙主導航 |
| 桌機 | 左側固定 compact rail／帳號區 | P7 原方向保留 |
| 我的 | Google／Sheet 詳細設定及資料健康度 | P6 不變，抽屜只是輕量登入入口 |

## 線框草案（僅供 Claude 細化，非詳細布局已核准）

手機收合： [☰] 台股 AI 戰情室／當前頁 → 四頁內容全寬，無底部固定主導覽。

手機展開： [×] 台股 AI 戰情室 → 市場、標的、持股、我的 → 分隔 → Google 帳號 → 真實狀態／若尚未接線顯示限制 → Google 登入（Auth Gate 前禁用）。

## 三方案選擇

- A. 手機常駐舊側欄：擠壓內容，不採（舊版自訂常駐側欄的擠壓；原生 st.sidebar 於手機為覆蓋層、不擠壓內容，已於 Streamlit 1.56.0 與 1.59.2 最小應用實測，且切頁後不會自動收合）。
- B. 可展開左側抽屜：保有選項／登入、收合主內容全寬，客戶同意。
- C. 抽屜＋底部雙主導航：重複且仍被 Manage app 擋，不採。

## 施工前 Gate

1. 先提正式 390px、1440px 文字線框，確認抽屜寬度、閉合、切頁、焦點／鍵盤、safe-area 與原有內容及 CTA；不能直接從此草案動工。
2. 舊 Active Contract、Wireframes、UI Execution Spec、CSS 與 test/viewport 的「手機固定底部四格」都屬需明確 supersede 的舊導航位置規則。不得刪掉歷史 DEC 原文；正式施工時將守衛改成新導航行為，而不是只刪測試。
3. 必須核查 Android／Streamlit Cloud 的 Manage app 浮層，並在 1.56／1.59 的 FAKE／Real、390px／1440px 執行回歸。不得以 CSS 隱藏平台 UI 當唯一保證。Safari／iOS 未實測須揭露。
4. 僅允許導航殼與誠實 disabled 登入入口，不授權 Google OAuth、session 身分判斷、Sheet 操作、canonical、VM schema、Risk Cap、System Action 或 Digest。真正 Auth 改動另走 Opus High Gate。
5. 舊固定底部導覽的 160px 餘裕驗收應有新的對等安全區及第一屏四問防護，不能因不再有底部導航就默默移除所有 viewport 檢查。
6. 線框須說明手機切頁後抽屜自動關閉（原生 sidebar 實測不會自動關）與桌機 rail 並存方式（原生 sidebar 桌機預設展開 300px，與自訂 11rem rail 衝突）。
7. query param／ui2_dev／FAKE account 不得當登入證據；正式 Auth 契約為 NUI2-AUTH-CONTRACT-GATE（Opus 5.5＋High）。
8. 與正在規劃的 P6 資料健康度分批，先核對 GitHub 主幹與 open PR。新增布局線框經客戶／治理驗收後才由 Claude 施工。

## 驗收要點

單一主導航、四頁切換可操作、抽屜能開／關與切頁後重新開啟、登入狀態不虛構、Google 按鈕無正式 OAuth 前 disabled、畫面不水平捲動、主內容不被側欄永久佔位、無底部 Manage app 擋住的唯一入口、桌機左 rail 保留、P1/P2/P3 既有 VM/Evidence 測試不退化。