# New UI2｜五頁頂部導覽正式視覺方向與施工安全驗收（2026-11-07）

> **使用者核准的視覺方向 / APPROVED DIRECTION；尚未通過真瀏覽器驗收 / NOT IMPLEMENTED。**
> 來源：2026-11-07 使用者明確裁示：「我核准方案 B 作為五頁頂部導覽的視覺方向，不做臨時 B0 五頁抽屜。請將裁示寫入 GitHub，收斂正式線框與安全驗收條件，再安排 Claude Sonnet＋Medium 最小施工；未通過安全 Gate 不得合併。」
> 連結：DEC-146（docs/DECISIONS.md）；方案 B 是「流程方案 B＝直接以頂部五頁作為施工目標」，**不是** #1048 原草案 §A 的「所有內容擠手機單一列的方案 B」。所採畫面依 ChatGPT 對客戶流程方案 B 的**設計解讀**，參考 #1048 **§A 方案 A（頂部兩列）**；其中「A1／重用既有 header 保留帶」是本次 GPT 提出的受控細化候選，**不是 #1048 原文件中的方案編號，也不是已驗證的高度實作**。客戶明文核准的是流程方案 B 與不做臨時五頁 Drawer，並未逐字確認「A1」名稱或固定像素。不得混淆編號與客戶原話。
> 本文件為已批准的呈現方向與可驗收邊界，不構成已通過像素/真機驗收，也不授權正式 OAuth/Sheet、資料來源、公式、Risk Cap、System Action 或 OneBrain runtime。

## 1. 使用者已核准的範圍與不再採行的過渡方案

- 下一版唯一目標：📊市場 → 🎯標的 → 💼持股 → 👤我的 → 🗂資料，兩端均**頂部**五頁導覽，Dark-only、Mobile-first。桌機不留左 rail，手機不留 Drawer 作正式導航。
- 頂部第一列為 Active Sheet 選擇／狀態 + 右側帳號入口；第二列為五頁主導覽。手機第二列**只在自身容器內橫向捲動**，最後的 🗂資料可用鍵盤或觸控到達；桌機五項可見。Active Sheet 和帳號**未完成正式契約前**僅使用核准的「尚未接線」能力揭露，不得以 FAKE/query/session 當登入。
- **拒絕臨時 B0**：不得先將現行 Drawer/rail 改成五項，然後再做另一批替換。避免二次導航工程與測試負擔。
- **允許最小分階段工程**：可先製作正式頂部五頁的路由/🗂空殼/安全測試，**前提是同一批交付完整可測的正式頂部導覽，不留下五頁 Drawer 作合併後狀態**。若為安全重構需要內部分 commit，PR 最終交付及每個外部可用 checkpoint 均須遵守此限制。
- 現有四頁功能、正確性、空槽、來源/資料日/缺值、首屏決策與 CTA 不得退化；舊 UI/Legacy 不修改。不得直接修改共用 `shared/ia_nav4`，避免影響既有舊介面；優先在 `shared/ui2_contract/pages.py` 設 UI2 自有五頁登錄。

## 2. 核准的資訊架構／文字線框

### 手機 390×844（核准位置與順序，不核准固定像素高度）

```text
┌────────────────────────────────────┐
│ Active Sheet ▾ / ⬜ 尚未接線   帳號 │  第一列，盡量取代/重用現有 header 保留帶
├────────────────────────────────────┤
│ 📊市場  🎯標的  💼持股  👤我的  ⇢ │  第二列；在此列水平捲動至 🗂資料
├────────────────────────────────────┤
│ 各頁現有主要狀態 / 是否需要行動     │
│ 下一步 / 主要 CTA（首屏可觸及）     │
│ 必要資料日期、缺值及來源提示       │
├── 既有首屏安全量測邊界 ────────────┤
│ Primary 圖／誠實空槽與 SPEC        │
│ 後續必要資訊                       │
└────────────────────────────────────┘
```

### 桌機 1440×900

```text
┌──────────────────────────────────────────────────────────┐
│ Active Sheet ▾                              帳號／狀態  │
├──────────────────────────────────────────────────────────┤
│ 📊市場   🎯標的   💼持股   👤我的   🗂資料               │
├──────────────────────────────────────────────────────────┤
│ 既有頁面標題／主要 CTA、狀態／是否需行動／下一步          │
│ 既有圖表／合法資料與必要來源、資料日、限制                 │
└──────────────────────────────────────────────────────────┘
```

**🗂資料頁第一批只做獨立 Preview View、正確導航、可讀「尚未提供／尚未接線」狀態，並保留 Data State / Capability 分軸。** 不新增真實來源健康度欄位、分母、retrieved_at、proxy、刷新時間、真正登錄/Sheet 或完整 Evidence。👤我的僅在具合法連結的階段可提供資料頁入口，不複製來源健康度牆。任何尚未設計/核准的資料欄位均維持 missing/unavailable，不填 0、不假裝已上線。

## 3. 工程拆分（Claude Code，Sonnet＋Medium）

首個**完整可合併**工程 PR 只做以下三項緊密相關的交付（允許內部多 commit，但合併 Gate 針對完整 head）：
1. 在 UI2 範圍登錄第五頁、接上 View/Preview VM，🗂誠實空殼且可導覽；避免碰舊 UI 的 `shared/ia_nav4`，檢查 `_WRAP_TAGS` 四個元素造成的越界問題。
2. 用已核准的**頂部兩列五頁**正式呈現替換 UI2 舊導航，不保留臨時五頁 Drawer/rail。保護既有同一 radiogroup/keyboard/focus/ARIA/inert/ESC 行為；舊 JS_V4 只能在已證明等價安全保障後退役，禁止先刪 hash/allowlist/測試求綠。
3. 更新相依且原本硬編四頁的測試與 viewport 判定器，真瀏覽器量測並重生 `source_hash` 相關 JSON；守衛只因正規需求調整，不能降低驗收門檻或刪除失敗案例。

若實測發現要改 Auth/Sheet 內部、增加全新 JS 權限、移動主要 CTA 或破壞既有首屏安全空間，**STOP**，另提三案與證據供裁示。不要用填空假資料來讓 UI 看似完成。

## 4. 絕不可跳過的安全與驗收 Gate

- **版本與來源**：施工開始、每次 push、merge 前重新驗 main SHA、Open/Draft PR head/diff、相關 branches、CI/review；不得與 #1047、#1030/#1034 等治理 Draft 的共享檔重疊；不要把此 docs PR 或 Draft 當 main 已實作。
- **Viewport**：390×844 與 1440×900，Streamlit 1.56.0、1.59.2 真 Chromium；FAKE cold/loaded/stale/unavailable 及現有 Real snapshots 的相關守衛；頁面不可水平溢出，五個選項最後一項可透過滑動/Tab 到達，可見選中狀態不只靠顏色；鍵盤、focus、ESC、inert、listener 不累積，reduced-motion 與 safe-area 不退化。
- **首屏硬門檻**：兩列導覽的實際高度必須重算；導航從底部改頂部後，`p2_nav_margin_160` 的量測錨點須先定義可比較的首屏可操作空間並經獨立 QA，禁止只搬用原底部錨點讀值。既有 `p2_nav_margin_160` **≥160px** 保留，歷史最窄 unavailable 162.5px（只剩 2.5px），不得把新增兩列當額外 header 擠內容；必須用實測量淨高度及 CTA 可操作性。若不達標，回視覺設計 Gate，不改 160px 門檻、不透過隱藏關鍵資訊作弊。
- **安全與資料語意**：維持 G2/G2F/G4/G9、no-write、Data State / Capability、缺值/PIT/Risk Cap、同一 Action Authority、不可把 FAKE/Preview 當正式實況；不新增 API、公式、Schema、正式 OneBrain runtime、真 OAuth/Sheet。
- **證據與 CI**：保留所有既有守衛或以能證明等價/更嚴的負測取代；重新生成四份 `viewport_measurements*.json`（以實際檔案清單為準）及相關 hash、審核變化原因；最新 PR head 五條原生 CI jobs 都 completed/success、獨立非作者 QA、review threads 0 未解、mergeability clean，方可 squash merge。不能把 workflow_dispatch 綠當 head required-check。
- **未驗揭露**：iOS/Android 真機、Safari/WebKit、Cloud Manage app/CSP、VoiceOver/TalkBack 未實測則標 NOT VERIFIED，不得宣稱完成真機/無障礙全面驗收。

## 5. 後續仍獨立待辦（不在本次 code 授權）

正式 🗂 資料健康度清單及分母/欄位、第一版 Old UI 資料資格、正式 Active Sheet/持續登入、完整 Evidence→Digest coverage、OneBrain 協調、財報/EPS/PE／產業缺貨公式與實數來源、正式 Risk Cap/System Action 均各走獨立 Source/Schema/Security/Investment Decision Gate，不在五頁外殼工程中順手接線。

## 6. Gate 判定與核准邊界

- **已核准**：五頁頂部兩列方向；不用臨時五項 Drawer B0；以首屏安全/身分資料正確性為必要保護；規劃最小施工與驗收。
- **未聲稱已通過**：具體像素、真瀏覽器高度、完整視覺 pixel parity、Auth/Sheet 實接、資料頁完整真資料、JS_V4 等價退役、production 切換。
- **不得合併條件**：首屏 <160px、缺任一必需測試/CI、真瀏覽器/等價安全證據不足、資料或權限造假、與現行 PR 衝突。以 fail-closed 回到本文件 Gate 調整，不要求使用者重覆核准同一大方向。
