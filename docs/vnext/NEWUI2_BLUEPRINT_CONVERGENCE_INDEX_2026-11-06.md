# New UI2 藍圖收斂交接表｜2026-11-06

> 此文件是 **索引與衝突盤點，非 Active Contract，也非施工核准**。base main `343f0e0e`。只針對 #1022 全站藍圖、#1027 W-11 線框、#1028 已合併施工與本次 📊／🎯 提案對帳；Claude Code New UI2 工作優先，不改其程式與檔案。

| 主題 | GitHub 可驗事實 | 藍圖收斂／裁示狀態 | 下一步 |
|---|---|---|---|
| 全站 #1022 | Draft、舊 base `fb466d15`，仍寫 #1020／#1021 為 open | **PROPOSED；歷史狀態過期** | 不直接合併；先以新 main reconcile 已合併 DEC／PR，再處理 BACKLOG 同段 append |
| 💼 #1027 | Draft、已加入 DEC-141 Q1～Q8 純版面授權；與 #1022 都 append BACKLOG | **本次 Q1～Q8 已核准，資料接線未核准** | 合併前 rebase 與防衝突，比對 #1028 已完成項，不覆蓋 |
| 💼 #1028 | 已 squash merge；純版面／空槽，非持股資料接線 | **已施工 ≠ 真資料完成** | 依最新客戶手機序：⑤市場端水位 → OneBrain → 產業集中度 Primary → 持股表；正式行動／持股來源仍另 Gate |
| 🎯 | #1022 §4 僅段落級提案；本 PR 新增 390／1440 兩模式線框 | **T-01～T-04 待裁示** | UI 優先基本面；先核對候選／六維 producer → canonical → VM；才施工 |
| 📊 | #1022 §4 段落級提案；本 PR 新增 390／1440 市場線框 | **M-01～M-04 待裁示** | 先維持手機已核准首屏，不插隊；確認歷史序列才畫 Primary |
| 👤 | #1022 §4、Active Contract 的 P6/Account 規格 | **P6 Level1/2、手機 Account 細部 Gate 未完** | 下批獨立線框；不從 SA、FAKE 或 query 建立登入 |
| 主題與顏色 | #1020 已合併、DEC-138 Dark-only | **不得視 #1022 亮卡提案為已核准 Light** | 先用 Dark-only 視覺方案；色彩改動另 Gate |
| OneBrain | DEC-128／129／136 完整 Digest 與 UI 展示分流 | **設計護欄已核准，資料 coverage 須逐欄稽核** | UI 上不恢復 raw evidence，Digest 不能只看 Top-N |

## 三種收斂路徑

1. **A｜直接合併 #1022 舊 base**：含 outdated status／可能 conflict；不採。
2. **B｜先以新 main 建獨立補充文件（本批）→ 各頁視覺核准 → 同步回單一正式藍圖**：風險低、避免與 Claude 編修重疊；**採用**。
3. **C｜先重寫所有已核准舊線框**：破壞 append-only、Token 成本高；不採。

## 優先序與交付門檻

1. 本批只新增 📊／🎯 可審閱文字線框及本表，**0 src／tests／workflow 改動**。
2. 下一批為 👤（Account 與 P6）設計，需先查新 main、活躍 PR、Claude 改動，不能自動蓋掉 #1022 或 #1027。
3. 只有拿到客戶對應 Layout 的明確核准，才把各頁標為 **APPROVED** 並產出 Claude Code 最小施工包（≤3 項）；未核准只存 **PROPOSED**。
4. 後續統一藍圖收斂不得形成第二套 SSOT，必須對照既有 CLAUDE／PROCESS／PROJECT_RULES／DECISIONS／Active Contract；資料來源、Risk Cap、Auth、Action、OneBrain 一律保留原 Gate。
