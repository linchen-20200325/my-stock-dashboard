# 👤 我的 —— Stage B 新版設計草稿（文字線框＋舊→新能力對照＋7 題裁示）

- 日期：2026-10-25｜基準：`286e0075`（#922）；本檔撰寫時工作分支 `claude/determined-euler-32xqjn` @ `cebb19e6`，與 `286e0075` 之間只差 4 份文件（`git diff --stat 286e0075 cebb19e6`：`docs/BACKLOG.md`／`DECISIONS.md`／`HANDOFF.md`／`PROJECT_STATE.md`），**程式碼相同，下文行號兩邊通用**｜撰寫：產品／IA 撰寫組（AI 總管派工）
- 📌 **狀態：已裁示（`docs/DECISIONS.md` DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：Stage C 客戶裁示 Q1～Q7 全採 A。下一步依 DEC-083 H 段：Sheet Safety 修復批（B1～B5，High）→ 獨立 QA → CI／merge／main verification → 👤 我的 P1（Stage D）。本檔盤點／線框／對照原文**不改**，只改本狀態行、§0「是否已核准」、§2 F8、§4 M08、§6 S5 與 §7 逐題加註。
- 治理依據：`docs/DECISIONS.md` **DEC-082**（Stage A 唯讀盤點 → **Stage B 草稿（本檔）** → Stage C 客戶裁示 → Stage D 實作）；DEC-081 第 7 點（互動控制完整性）、第 8 點（Sheet CRUD 單一 SSOT、⛔ 不刪舊 CRUD）、第 9 點（OAuth／credential／Sheet 寫入／權限模型／L3 → High）
- 對應待辦：`UIX-ME-SHEET-SSOT`、`UIX-HOLD-DEADEND`、`UIX-INTERACTION-COVERAGE`（`docs/BACKLOG.md` 5.1.13）
- 沿用：`docs/vnext/INTERACTION_COVERAGE_MATRIX_2026-10-25.md`（下稱「互動矩陣」）§1（👤 我的）、§2（🛡️ 持股）、§7（Sheet CRUD 專題）、§8（dead-end）；格式比照 `docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`
- 標記：**【FACT】**＝讀碼可查證（file:line）｜**【INFERENCE】**＝由事實推出、未實跑｜**【RECOMMENDATION】**＝AI 總管推薦，待客戶裁示

---

## 0. 狀態與邊界

| 項目 | 狀態 |
|---|---|
| 本文件是什麼 | DEC-082 **Stage B** 草稿：👤 我的頁的文字線框、舊→新能力對照、Sheet SSOT 技術提案、7 題請客戶裁示 |
| 是否已核准 | ~~⛔ **未核准**。§3 線框、§4 對照表的「去向」欄、§7 的推薦都等客戶在 Stage C 拍板~~ **已裁示（DEC-083）**：Q1～Q7 全採 A；§3 線框在 P1 範圍內「維持核准草稿方向」；另含 Sheet Safety 修復批（先於 P1）、取消唯一本自動綁、dead-end 導向規則、舊 UI Removal Gate、禁止事項，全文見 `docs/DECISIONS.md` DEC-083（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083） |
| 本批**沒有做**的事 | 沒寫任何 code、沒改導航（`shared/ia_nav.py::PAGE_LABELS` 未動，現無 👤 我的）、沒動 OAuth／Sheet 綁定／Sheet 寫入、沒刪舊 UI（側欄、📁 組合管理、🔗 我的組合狀態列、Sheet CRUD 全部原樣）。只有本檔。 |
| 頁名讀法 | 目標 IA 的 🛡️ 持股／🎯 標的／🩺 資料中心，在現行程式分別是 💼 我的持股（`page_hold`）／🔍 找標的＋🔬 查一檔（`page_find`／`page_inspect`）／📖 憑什麼 › 資料體檢（`page_why`）（`shared/ia_nav.py:53-60`；對照依互動矩陣 §0.2） |
| Effort | 👤 我的**第一期就碰 Google 登入／登出與 Sheet 綁定（權限模型、L3）** ⇒ 依 DEC-081 第 9 點，Stage D 一律 **High**；第二期（Sheet 內容寫入）另開 High Gate |
| ⚠️ 未複驗揭露 | 見 §9 |

---

## A. Stage A 唯讀盤點摘要（兩組獨立唯讀盤點，核心事實一致；撰寫組再逐條讀碼核對）

### A.1 新版模式的路由（承重事實）

| # | 事實 | 出處 |
|---|---|---|
| A1 | 新版模式：畫完選到的頁 → `_render_footer()` → `st.stop()` | `app.py:609-629` |
| A2 | 側欄在 `st.stop()` **之前**，新舊模式都畫：🔐 Google 帳號區（`app.py:340-404`）、🚪 登出（`:361-366`）、Sheet ID／URL 貼上框（`:368-392`，**只在「OAuth 已設定且已登入」時出現**，`:357-359`）、🔐 登入鈕（`:397`）、OAuth 未設定說明（`:399-404`）、🔍 測試連線（`:447-466`）、🔄 強制刷新（`:485-489`，`st.cache_data.clear()` 全域） | `app.py:310-472`、`:485-498` |
| A3 | `st.stop()` **之後**、新版模式**不畫**：🔗 我的組合狀態列（`:640-641`）、🧭 總經指南針（`:647-648`）、7 個舊頁籤（`:661`，含 📁 組合管理、舊 💼 存股戰情室） | `app.py:640-661` |
| A4 | `shared/ia_nav.py` 沒有 👤 我的；`SECTION_HOLD_PORTFOLIO_SETUP` 註解寫「綁 Google Sheet 的入口」，但該葉唯讀（見 A.3） | `shared/ia_nav.py:53-60`、`:69-70` |

### A.2 舊 UI 能力清單（帳號＋Sheet）

| 能力 | 位置 | 備註 |
|---|---|---|
| Google 登入 | 側欄 `app.py:397`；`portfolio_binder.render_login_cta`（`portfolio_binder.py:46-67`） | 登入 state 夾帶目前 Sheet ID，回來自動回綁 |
| 登入狀態 | 側欄 `app.py:358-360`（印 email） | |
| 登出 | **只有側欄**，L6 inline：pop `gsheet_tokens／gsheet_email／_oauth_state` ＋ `forget_silent_reauth` | `app.py:361-366`；**不清** `portfolio_sheet_id`、**不清**讀取快取 |
| 靜默恢復登入／逾時 | `oauth_state.maybe_silent_reauth`（`oauth_state.py:551`）、`gsheet_portfolio._login_needs_reauth`（`gsheet_portfolio.py:263`）／`_expire_session_login`（`:279`）／`login_expired`（`:298`） | 逾時是灰色有效態 |
| OAuth 未設定說明 | 側欄 `app.py:399-404`；`render_login_cta` `portfolio_binder.py:59-61` | |
| 貼 Sheet URL／ID | ① 側欄 inline（解析 `app.py:374`）② `portfolio_binder.render_paste_id_binder`（`:70-83`，regex `:28`） | 兩份 |
| Drive 列資料夾／列 Sheets／選一本／✅ 使用 | `portfolio_binder.render_drive_picker`（`:86-141`）→ `list_user_folders`／`list_user_sheets`（`gsheet_portfolio.py:993`、`:941`） | 清單只有 1 本且未綁 → **自動綁**（`:126-130`） |
| 🆕 建立新投組 Sheet | `portfolio_binder.py:110-117` → `create_new_sheet`（`gsheet_portfolio.py:1081`） | **寫入 Drive** |
| 改 Sheet 名稱 | `gsheet_portfolio.rename_sheet`（`:1137`） | **只有 backend，0 UI caller** |
| 刪除 Sheet | — | **全 repo 沒有**（只有刪組合／刪清單） |
| 🔄 重新讀取 | 舊 💼 存股戰情室 `etf_tab_dividend_station.py:142-145`（`clear_read_cache`）；側欄 🔄 強制刷新（全域 `st.cache_data.clear()`） | 兩者都是**全站共用快取的 `.clear()`** ⇒ 清掉所有使用者的快取項【INFERENCE：依 `st.cache_data` 的 `.clear()` 語意，未實測】 |
| 組合／觀察清單 CRUD | 📁 組合管理 `portfolio_manager.py:161-228`（組合，worksheet `portfolios`）、`:230-298`（觀察清單，`stock_watchlist`）；刪除兩段式確認（`:193-204`、`:258-263`）；`st.data_editor` 自由編輯＋整表重寫（`:211`、`:276`；`gsheet_portfolio._write_whole_sheet` `:740`） | 兩段近乎逐字重複 |
| ➕ 加入觀察清單 | 選股網 `app.py:900-933` → `watchlist_service.add_picks_to_watchlist` | 寫 Sheet |
| 🧊 凍結前 20 名 | 選股網 `app.py:938-959` → `forward_test_service.freeze_current_picks` → worksheet `forward_test_picks`（`gsheet_portfolio.py:887-910`） | **不可重建的歷史**（`CLAUDE.md` §-1.5.F 判定 3(5)） |

### A.3 新 UI 現況

| 頁 | 事實 | 出處 |
|---|---|---|
| 🛡️（`page_hold`） | 只顯示綁定狀態（`load_binding` → `get_binding_state`），**刻意不印 Sheet ID** | `page_hold.py:1063-1095`、檔頭 `:24-26` |
| 🛡️ | 讀持股走 `holdings_service`：組合只讀**第一本**（`_names[0]`），組合用 ETF 通道（`get_binding_state().sheet_id`），觀察清單用個股通道 | `holdings_service.py:201-218`、`:240-247` |
| 🛡️ | 測試釘死唯讀：AST 白名單＋寫入面黑名單（`save_portfolio`／`create_new_sheet`／`rename_sheet`…） | `page_hold.py:27-31`；`tests/test_p04_hold_view.py:282`（`TestReadOnly`） |
| 全部 view | **沒有**貼 ID／列清單／選擇／切換／建立／CRUD／重新讀取 | 互動矩陣 §1、§2 |
| 🎯（`page_find`） | **沒有**「帶入我的持股」（無 `get_holdings`）；板塊資金讀 `stock_portfolio_sheet_id`（`:455`、`:1464`）與 `etf_portfolio_rows`（`:453`、`:1418`） | `page_find.py` |
| 🎯 | `etf_portfolio_rows` 只由舊 UI 寫（`etf_tab_dividend_station.py:164`、`etf_tab_portfolio.py:451`），新 🛡️ 不寫 ⇒ 新版模式下板塊資金的「ETF 持股標示」恆為空【INFERENCE：讀碼推得，未實跑】 | 同上 |

### A.4 沒有單一 Sheet SSOT

| 面向 | 現況 | 出處 |
|---|---|---|
| 兩條 session 通道 | `portfolio_sheet_id`（ETF／legacy，**有 secrets fallback**）、`stock_portfolio_sheet_id`（個股，session-only） | `gsheet_portfolio.py:102-109`、`:151-180` |
| 解析器 4 份 | ① `app.py:374` ② `portfolio_binder.py:28` —— 兩者都把發布連結 `/spreadsheets/d/e/…` 解析成 **`e`（BUG）**；③ `portfolio_manager.parse_sheet_id`（`:78-95`）正確拒絕發布連結，但 **0 production caller**；④ `oauth_state._sanitize_sheet_id`（`:263-270`，白名單 `[A-Za-z0-9_-]{1,120}` `:260`），不解析 URL | |
| 綁定寫入者 | ① `?sheet=` 還原 `app.py:152-158`（`setdefault`、**未消毒**）② 側欄 `app.py:375-386`（**沒呼叫** `apply_active_sheet`，雖然 binder docstring `portfolio_binder.py:34-35` 說有；多做一步 `_sb_sync_silent()` `:386`）③ `portfolio_binder.apply_active_sheet`（`:31-43`）④ OAuth 回呼回綁（`oauth_state.py:645-647`、`:724-730`）；死殼 `portfolio_manager._apply_active_sheet`（`:150-158`，0 caller） | |
| 兩套 UI | 側欄 inline 一份；`portfolio_binder` 一份被重用 3 次（`portfolio_manager.py:146`、`portfolio_status_bar.py:78`、`etf_tab_dividend_station.py:187`） | 互動矩陣 §7.1 |
| 消費者 | `holdings_service`（組合←ETF 通道、清單←個股通道）、`page_today` 綁定狀態（`get_binding_presence`，ETF 通道）、`page_find`／`sector_flow_service`（個股通道，`sector_flow_service.py:48`）、`watchlist_service`、`forward_test`（ETF 通道）、舊 戰情室寫 `etf_portfolio_rows` | |
| 與 UI 無關的第三條 | cron `scripts/push_holdings_daily.py` 讀環境變數 `PORTFOLIO_SHEET_ID`／`STOCK_PORTFOLIO_SHEET_ID`（`:42-45`），與畫面綁定**互不影響** | |

### A.5 新版模式的 dead-end（詳見 §5）

`page_hold` 多處 where 指到「📁 組合管理」；`page_hold.py:1689-1692`／`page_today.py:1051` 指到側欄貼上框，但那格**只在登入後出現**，字面沒說「先登入」；`page_hold.py:1783` 指回自己的唯讀葉；`app.py:398` 側欄 caption 指 📁 組合管理；OAuth 未設定 → 新版模式**無任何綁定方法**；沒有任何頁告訴使用者「把側欄切回『不使用』」。

### A.6 High-gate 項目

| # | 項目 | 為什麼 High |
|---|---|---|
| H1 | ⭐ **讀取路徑會寫使用者的 Sheet**：`_get_worksheet`（`gsheet_portfolio.py:431-461`）在 worksheet 不存在時 `add_worksheet` ＋ `append_row(headers)`（`:454-457`）；第 1 列 ≠ 預期表頭時 `ws.update` 覆寫第 1 列（`:459-461`）。所有讀取都經過它：`list_portfolios`（`:597-599` → `_all_records` `:480-493`）、`holdings_service`、`get_binding_state`（`portfolio_binding_service.py:100`）、`sector_flow` 的 `list_stock_watchlists`（`:847-853`）。**同一模式第二處**：`_ft_worksheet`（`:891-907`）—— 讀取用的 `load_forward_test_picks`（`:922`；caller `forward_test_service.py:88`，對帳）也經過它：缺 `forward_test_picks` 分頁 → `add_worksheet`＋`append_row`；表頭不符 → `ws.update('A1:F1')` 覆寫。`forward_test_picks` 是**不可重建的凍結歷史**（`CLAUDE.md` §-1.5.F 判定 3(5)） | 🛡️／`holdings_service` 的「唯讀」承諾**在 L1 不成立**；對帳讀取可能改到凍結歷史的表頭。⚠️ 讀碼結論，**未實測** |
| H2 | 寫入面：`create_new_sheet`／`save_*`／`delete_*`／`add_to_stock_watchlist`／`append_forward_test_picks`／`rename_sheet` | Sheet 寫入（DEC-081 第 9 點） |
| H3 | 綁定信任模型：`?sheet=` 未消毒進 session（`app.py:152-158`）；單本自動綁（`portfolio_binder.py:126-130`）；`sync_silent_marker` 只信 session 的 `portfolio_sheet_id`（`oauth_state.py:433-479`），綁定寫入者若繞過它會讓靜默重登退化 | 權限模型 |
| H4 | 登出語意＋每人快取清除（SEC-1 後續） | OAuth security |
| H5 | Sheet ID 顯示政策不一：側欄印全 ID（`app.py:388-389`）、狀態列印前 16 碼／全 ID（`portfolio_status_bar.py:61`、`:87`）、Drive 選單印前 12 碼（`portfolio_binder.py:132`）、🛡️ 不印 | 識別碼外露 |
| H6 | OAuth scope：`spreadsheets`（全權）、`drive.file`、`drive.metadata.readonly`（可列使用者**全部**檔案的名稱）、`openid`、`userinfo.email` | `infra/oauth.py:33-39` |
| H7 | `custom_oauth_cfg` 殘留讀取路徑（session 可提供 OAuth client 設定；**production 無寫入者**） | `oauth_state.py:122-137` |
| H8 | 全域快取清除影響其他使用者（側欄 🔄、`clear_read_cache`） | 多使用者隔離 |

### A.7 畫面包袱（只登記，本批不修）

側欄 inline 的 Sheet／登出複本；側欄 🔍 測試連線（L6 inline HTTP、`verify=False`，與 `src/ui/pages/api_diagnostic.py:153` 重疊，宜歸 🩺）；`portfolio_manager` 組合／清單兩段重複＋自由 `data_editor`＋整表重寫；死碼 `parse_sheet_id`（無 production caller）／`_apply_active_sheet`／`_STOCK_DRIVE_FOLDER_NAME`（`gsheet_portfolio.py:100`，0 reader）／`rename_sheet`／`get_sheet_title`（`:1154`，0 UI caller）；過期註解（`app.py:378`「與 _apply_active_sheet 一致」、`app.py:620-623`「本頁的組合設定葉」是綁 Sheet 入口、`ia_nav.py:69`、`portfolio_binder.py:34-35`）；「兩條通道」這個概念本身。

---

## 1. 頁面目的

> **👤 我的只回答一個問題：「我用哪個 Google 帳號、這個 App 現在讀哪一本 Sheet、它是不是最新的？」**

| 是 | 不是 |
|---|---|
| 帳號＋Sheet 綁定的**唯一**入口（一套 Sheet SSOT，多頁共用） | 持股分析（那是 🛡️） |
| 顯示這本 Sheet 裡**有什麼**（幾本組合、幾份清單、名稱）與**誰在用它** | 資料健康、外部來源診斷（那是 🩺） |
| 「重新讀取」（只清**本人**的讀取快取） | 編輯持股內容（第一期不做，見 Q2） |

完成條件（DEC-081 第 7 點）：凡新頁叫使用者「去綁 Sheet／換 Sheet／重新讀取」，終點都是 👤 我的，且 👤 我的上**真的有那顆控制**。

---

## 2. 使用者流程【RECOMMENDATION】

| # | 情境 | 流程 |
|---|---|---|
| F1 | 第一次（未登入） | 👤 我的 → 卡① 顯示「⬜ 尚未登入」→ [🔐 用 Google 登入] → 回來後卡② 顯示「⬜ 尚未選 Sheet」→ 展開 [切換 Sheet]：貼網址／ID **或** 從 Drive 清單選一本 → [✅ 使用此 Sheet] → 卡②③ 更新 → 提示「去 🛡️ 持股看持股」 |
| F2 | 回訪（已綁） | 首屏直接看到帳號、Sheet 標題、最後讀取時間 → 需要時 [切換 Sheet] 或 [重新讀取（只清我的快取）] |
| F3 | 登入逾時 | 卡① 灰色「登入已逾時（不是故障）」＋[重新登入]；卡② 保留「上次用的是哪一本」但標「需重新登入才能讀」；⛔ 不畫紅 |
| F4 | OAuth 未設定（部署端缺 `[google_oauth]`） | 卡① 灰色「本站尚未設定 Google 登入，無法讀取你的 Sheet」＋一句「這是部署設定，不是你的操作問題」；⛔ 不出現指向側欄貼上框的假指路（側欄那格在未登入時不出現） |
| F5 | 貼了**發布連結**（`/spreadsheets/d/e/…`） | 拒絕並說明「這是『發布到網路』的連結，不能用來讀寫；請改貼瀏覽器網址列的編輯網址（含 `/spreadsheets/d/<ID>/edit`）或 Sheet ID」；⛔ 不得當成 ID `e` |
| F6 | 貼了亂碼／非法字元 | 拒絕：「看不出 Sheet ID（只接受英數、`_`、`-`）」；⛔ 不寫 session、不寫網址 |
| F7 | 網址帶 `?sheet=`（書籤） | 卡② 標「綁定來源：網址書籤還原」；經同一消毒器（§6）才採用 |
| F8 | 清單只有 1 本 | **不自動綁**：列出那一本，仍需按 [✅ 使用]（技術提案見 §6 S5、對照表 M08）<br>📌 客戶已裁示**取消唯一本自動綁**：就算 Drive 只有一本，仍要使用者明確按「使用這本」（DEC-083 C 段）（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083） |
| F9 | Sheet 裡有好幾本組合／清單 | 卡③ 照實寫「🛡️ 目前只分析名稱排序第一本『X』」；要不要能選哪一本，見 **Q7** |

---

## 3. 文字線框【RECOMMENDATION】

> 數字、名稱都是**示意**。燈色一律附文字，不只靠顏色（v3 §02：灰＝未載入／有效空狀態，紅＝真的出錯）。

### 3.1 首屏

```
┌─ 👤 我的 ───────────────────────────────────────────────────────────────┐
│ 我用哪個 Google 帳號、這個 App 現在讀哪一本 Sheet、它是不是最新的？           │
│ 狀態：🟢 已登入 ab***@gmail.com｜📗 讀取中：「台股投組 2026」（…f3K9aQ）｜    │
│       最後讀取 10/25 14:02（本人快取）                                      │
├────────────────────────┬────────────────────────┬────────────────────────┤
│ ① Google 帳號          │ ② 目前讀取的 Sheet      │ ③ 這本 Sheet 裡有什麼   │
│ 🟢 已登入               │ 📗「台股投組 2026」      │ 組合 2 本：             │
│ ab***@gmail.com        │ ID 末 6 碼：…f3K9aQ      │   長期存股、波段         │
│ 權限：可讀寫你帳號內的  │ 綁定來源：你在本頁選的   │ 觀察清單 1 份：AI 鏈     │
│ 試算表（本站只用你選的  │                        │ ⚠️ 🛡️ 目前只分析名稱排序 │
│ 那一本）；列出雲端硬碟  │                        │ 第一本「波段」／第一份   │
│ 檔名 ⓘ                 │                        │ 「AI 鏈」（Q7）          │
│                        │                        │ 最後讀取 10/25 14:02    │
│                        │                        │ 用到這本的頁：           │
│ [ 🚪 登出 ]             │ [ 🔄 切換 Sheet ▾ ]     │ 🛡️ 持股（組合＋清單）   │
│                        │ [ ⟳ 重新讀取（只清我的）]│ 🎯 標的（板塊資金；未來帶入）│
│                        │                        │ ⚡ 行動（未來）          │
│                        │                        │ 🚦／📊（只看有沒有綁）   │
└────────────────────────┴────────────────────────┴────────────────────────┘
  ▸ 為什麼是這本？｜▸ 權限說明｜▸ 詳細資料
  （正常狀態**不顯示**「通道」；只有組合與觀察清單指向不同本時，卡② 才出現白話警示）
```

卡① 各態（只用文字＋燈，⛔ 不只靠顏色）：

| 狀態 | 卡面 | 按鈕 |
|---|---|---|
| 未登入 | ⬜ 尚未登入 —— 登入後才能讀你的 Sheet | [🔐 用 Google 登入] |
| 已登入 | 🟢 已登入 ＋ email（遮罩，見 Q4 同一原則） | [🚪 登出]（語意見 Q5） |
| 登入已逾時 | ⬜ 登入已逾時（自動恢復的登入約 1 小時後逾時，**不是故障**） | [🔐 重新登入] |
| OAuth 未設定 | ⬜ 本站尚未設定 Google 登入（部署設定） | 無；說明一句 |
| 授權讀不出來 | 🔴 登入狀態讀取失敗：〈原因〉，可重試 | [重試] |

卡② 各態：

| 狀態 | 卡面 |
|---|---|
| 尚未選 | ⬜ 尚未選 Sheet —— 按 [切換 Sheet] 選一本 |
| 已選、未讀 | 📗 ID 末 6 碼 …f3K9aQ ｜ ⬜ 標題尚未讀取 |
| 已選、已讀 | 📗 標題 ＋ 末 6 碼（Q4） |
| 組合與觀察清單指向不同本（只在此時出現） | ⚠️ 你的「組合」和「觀察清單」目前讀的是**兩本不同**的 Sheet（…f3K9aQ／…Zq81Lp）—— 按 [切換 Sheet] 重選一本即可統一（Q6）；⛔ 正常狀態不出現「通道」字樣 |
| 綁定來源 | 「你在本頁選的」／「網址書籤還原」／「登入時自動回綁」／「部署預設（secrets）」 |
| 找不到／無權限 | 🔴 這本 Sheet 打不開：找不到（404）或沒有權限（403）—— 請重新選一本 |

卡③ 各態：

| 狀態 | 卡面 |
|---|---|
| 尚未讀取 | ⬜ **尚未讀取**（≠ 0 本）—— 按 [重新讀取] |
| 讀完、真的是空 | ⬜ 這本 Sheet 裡還沒有任何組合（**有效結果，不是故障**） |
| 有 2 本以上組合／清單 | ⚠️ 照實寫：「🛡️ 目前只分析名稱排序第一本『X』／第一份『Y』，其餘沒有分析」（`holdings_service.py:213-215` 取 `_names[0]`；`list_portfolios` 回 `sorted()`，`gsheet_portfolio.py:603`）；可否選擇見 Q7 |
| 缺分頁（讀取改為真唯讀後，見 Q3） | ⬜ 尚無「portfolios」分頁／尚無「stock_watchlist」分頁（本頁**不會**替你建立） |
| 表頭不符（讀取改為真唯讀後，見 Q3） | ⚠️ 資料疑義：「portfolios」第 1 列不是預期的欄名（應為 name／ticker／lots／avg_price／updated_at），本頁未讀取、也未修改 |
| 讀取逾時／失敗 | 🔴 讀取失敗：逾時（或 429 配額），可稍後重試 |

### 3.2 主要控制：[🔄 切換 Sheet] 展開區

```
┌─ 🔄 切換 Sheet ─────────────────────────────────────────────────────┐
│ 方法一：貼網址或 ID（自動解析）                                         │
│ [ https://docs.google.com/spreadsheets/d/…/edit           ]           │
│ 解析結果：ID 末 6 碼 …f3K9aQ ✅ 可用                                    │
│   （發布連結 → ❌ 這是「發布到網路」的連結，請改貼編輯網址；            │
│     非法字元 → ❌ 看不出 Sheet ID）                                     │
│                                                                       │
│ 方法二：從我的雲端硬碟選                                                │
│ 限定資料夾：[ 整個帳號（不限資料夾）▾ ]   [ 📂 列出 Sheets ]             │
│ 清單共 3 本 —— 選一本：[ 台股投組 2026（…f3K9aQ）▾ ]                    │
│                                                                       │
│ [ ✅ 使用此 Sheet ]   ← 兩種方法共用同一顆；按下才寫入綁定               │
│ ⓘ 只改「這個 App 讀哪一本」，不會改你 Sheet 裡的任何內容                 │
└───────────────────────────────────────────────────────────────────────┘
```

> 🆕 建立新 Sheet **不在第一期**（Q2）；第一期在此處只放一行文字：「要建立新 Sheet：目前請用舊版（側欄選『不使用（用下方原功能）』→ 📁 組合管理）」。

### 3.3 第二層（預設收合）

| 區塊 | 內容 |
|---|---|
| 為什麼是這本？ | 綁定來源（卡② 同欄）的白話說明；若來自 secrets 預設，講明「這是部署預設，你可以改選」 |
| 組合與觀察清單不同本時的說明（只在警示出現時提供） | 白話：「組合和觀察清單本來應讀同一本；目前兩者不同，可能是舊版分別設定過。按 [切換 Sheet] 選一本就會統一」（Q6）；⛔ 不對使用者講「通道」 |
| 權限說明 | 逐項白話列 `infra/oauth.py:33-39` 的 5 個 scope，與卡① 同一說法：`spreadsheets`（`:34`，全權）＝「可讀寫你帳號內的試算表（本站只用你選的那一本）」；`drive.metadata.readonly`＝「可以列出你雲端硬碟所有檔案的**名稱**（不讀內容），只用在『從 Drive 選』」 |

### 3.4 詳細（第三層，預設收合）

| 欄 | 內容 |
|---|---|
| Sheet ID | 依 Q4（推薦仍只顯示末 6 碼；完整 ID 提供 [複製] 而不直接印出） |
| Worksheet | 實際讀到的分頁名（`portfolios`／`stock_watchlist`／`forward_test_picks`）與各自列數 |
| 最後讀取時間 | 本人快取的寫入時間（⛔ 不寫成「資料日」） |
| 來源 | `gsheet_portfolio`（L1）經 L3 讀取；cron 推播讀的是部署環境變數，**與本頁綁定無關**（`scripts/push_holdings_daily.py:42-45`） |

### 3.5 狀態用語總表

| 狀態 | 顏色＋文字 | 用在 |
|---|---|---|
| 尚未載入／尚未讀取 | ⬜ 灰「尚未讀取」 | 卡②③ |
| 有效的空 | ⬜ 灰「還沒有…（有效結果，不是故障）」 | 卡③ |
| 未登入／逾時／OAuth 未設定 | ⬜ 灰 ＋ 原因句 | 卡① |
| 資料疑義 | ⚠️ 黃「資料疑義：…」 | 卡③（表頭不符） |
| 真的出錯 | 🔴 紅「〈什麼〉失敗：〈原因〉，可重試」 | 卡①②③ |

---

## 4. 舊 → 新能力對照

**去向欄**：P1＝👤 我的第一期｜P2＝第二期（另開 High Gate）｜OLD＝暫留舊 UI（凍結不刪）｜🩺＝移資料中心｜DROP?＝刪除候選（須走 removal Gate，**本批不刪**）｜DG＝需獨立 Decision Gate

| # | 舊能力 | 舊位置 | 去向 | 備註／Gate |
|---|---|---|---|---|
| M01 | 🔐 Google 登入 | 側欄 `app.py:397`；`render_login_cta` | **P1** 卡① | High（OAuth）；登入 state 夾帶目前 Sheet ID（`app.py:395`、`portfolio_binder.py:62-63`）的行為受 **Q5** 影響：Q5=A 時登出後不再夾帶 |
| M02 | 登入狀態（email） | 側欄 `app.py:358-360` | **P1** 卡① | email 遮罩屬 Q4 同原則 |
| M03 | 🚪 登出 | 側欄 `app.py:361-366`（L6 inline） | **P1** 卡①，邏輯抽 L3 | 語意 **Q5**；High |
| M04 | 靜默恢復／逾時提示 | `oauth_state`／`gsheet_portfolio` | **P1** 卡① 逾時態 | 沿用既有 L1，不改行為 |
| M05 | OAuth 未設定說明 | 側欄 `app.py:399-404` | **P1** 卡① | 改正假指路（§5 D10） |
| M06 | 貼 URL／ID | 側欄 `app.py:368-392`；binder `:70-83` | **P1** 切換區方法一 | 改走單一解析器（§6）；修 `/d/e/` |
| M07 | Drive 列資料夾／列 Sheets／選一本／✅ 使用 | `render_drive_picker` `:86-141` | **P1** 切換區方法二 | 重用元件，不寫第 5 份 |
| M08 | 只有 1 本時自動綁 | `portfolio_binder.py:126-130` | **P1 改為不自動**（仍要按 ✅） | §6 第 5 點；屬權限模型 → High<br>📌 唯一本自動綁**已由客戶裁示取消**（DEC-083 C 段）（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083） |
| M09 | `?sheet=` 書籤還原 | `app.py:152-158` | **P1** 保留，改經消毒器＋卡② 標來源 | High（H3） |
| M10 | OAuth 回呼自動回綁 | `oauth_state.py:645-647`、`:724-730` | **P1** 保留（已消毒），卡② 標來源 | 不改行為；但**依 Q5：登出後不再回綁**（Q5=A 時登入 state 不夾帶舊 Sheet ID，回呼就沒有東西可回綁） |
| M11 | 🔄 重新讀取（`clear_read_cache`） | 舊戰情室 `etf_tab_dividend_station.py:142-145` | **P1** 卡② [重新讀取（只清我的）] | 須先有「只清本人」能力（H8、Q5）；High |
| M12 | 🔄 強制刷新數據（全域清） | 側欄 `app.py:485-489` | OLD（側欄照舊）；長期 → 🩺 | 全域影響他人 → DG（H8） |
| M13 | 🔍 測試連線 | 側欄 `app.py:447-466` | 🩺（另案） | 與 `src/ui/pages/api_diagnostic.py:153` 合併屬 🩺 Gate |
| M14 | 🆕 建立新投組 Sheet | binder `:110-117` → `create_new_sheet` | **P2** | 寫 Drive → 第二期 High Gate；期間 OLD |
| M15 | 改 Sheet 名稱 | `rename_sheet`（0 UI caller） | DROP? 或 P2 | 無舊畫面可「承接」；要不要做由客戶決定（第二期） |
| M16 | 刪除 Sheet | 不存在 | ⛔ 不做 | 不可逆（`CLAUDE.md` §-1.5.F 判定 3(5)） |
| M17 | 組合 載入／儲存／刪除 | `portfolio_manager.py:161-228` | **P2**；期間 OLD | 寫 Sheet；先抽 L3 CRUD service（互動矩陣 §7.4 第 4 點） |
| M18 | 觀察清單 載入／儲存／刪除 | `portfolio_manager.py:230-298` | **P2**；期間 OLD | 同上，與 M17 共用 |
| M19 | ➕ 加入觀察清單 | 選股網 `app.py:900-933` | DG（屬 🎯 標的頁 Gate） | 寫 Sheet，High |
| M20 | 🧊 凍結前 20 名 | 選股網 `app.py:938-959` | DG（🎯 或 ⚡ 頁 Gate） | 不可重建歷史，High |
| M21 | 🔗 我的組合狀態列 | `app.py:640-641`（新版模式不畫） | 由 👤 我的首屏狀態列取代（新版模式）；OLD 照舊 | 舊模式不動 |
| M22 | Sheet ID 顯示 | 側欄全 ID／狀態列 16 碼／選單 12 碼／🛡️ 不顯示 | **P1** 統一（Q4） | 舊 UI 本批不改 |
| M23 | 組合與觀察清單分開設（L1 的兩個 session 欄位） | 無 UI（概念存在於 L1） | **P1** 一個選擇器同時設兩者（Q6） | 正常不顯示；不一致時才白話警示 |
| M25 | 選用哪一本組合／清單 | 舊 📁 組合管理 selectbox 載入指定那本（`portfolio_manager.py:178`、`:246`）；新 🛡️ 固定取名稱排序第一本（`holdings_service.py:213-215`、`gsheet_portfolio.py:603`） | **Q7**（推薦：P1 加入 👤 我的共用選擇器） | 只改「分析哪一本」，不寫 Sheet；跨頁共用 → 綁定模型，High |
| M24 | 死殼 `_apply_active_sheet`／`parse_sheet_id`（無 production caller）／`_STOCK_DRIVE_FOLDER_NAME`／`get_sheet_title` | 見 A.7 | DROP?；`parse_sheet_id`、`get_sheet_title` **改為 P1 會用到**（§6） | 依 v3 §01-2：因本次改動才變孤兒者才在本次清 |

---

## 5. Interaction Coverage（dead-end 怎麼關）

> ⚠️ 關掉這些 dead-end 是 **Stage D** 的工作：要改 `page_hold.py`（被 `tests/test_p04_hold_view.py`、`tests/test_batch_z54.py` 釘住字面，例 `test_batch_z54.py:115-128` 斷言 where 不含「組合管理」）、`page_today.py`、`app.py`。本批**一行未改**。

| # | dead-end | 位置 | 第一期後的出口 | 第一期後是否仍有缺口 |
|---|---|---|---|---|
| D1 | 「用 Google 登入後選一本 Sheet —— 現行入口在側欄…」（未說要先登入；側欄沒有清單可選） | `page_hold.py:1689-1692`（`NOT_BOUND_WHERE`）；`page_today.py:1051`（`SHEET_UNBOUND_WHERE`）；`page_hold.py:4291`（pick_sheet 卡「現行入口」） | 改指「👤 我的 › 切換 Sheet」 | ✅ 關閉 |
| D2 | 「到既有的 📁 組合管理分頁新增一本組合並填入持股列」 | `page_hold.py:1716-1718`（`EMPTY_SHEET_WHERE`）、`:4274`、`:4443`、`:4704` | 第一期**沒有**新 UI 寫入入口 ⇒ 改成誠實版：「新增組合目前要用舊版：側欄『🆕 新版戰情室』選『不使用（用下方原功能）』→ 📁 組合管理；第二期會搬到 👤 我的」 | ⚠️ **仍是半 dead-end**（有正確指路、但需切模式），直到 P2 |
| D3 | 「到 📁 組合管理補張數／均價／確認代號」 | `page_hold.py:1867`、`:2683`、`:2788`、`:3195`、`:3305`、`:3407`、`:3738`、`:4399`、`:4477-4481`、`:4598`、`:4662` | 同 D2 誠實版指路 | ⚠️ 同上，直到 P2（「新增／修改持股列」第一期**沒有**新 UI 控制） |
| D4 | 唯讀說明「現行入口仍在既有的 📁 組合管理分頁」 | `page_hold.py:565-569`（`READONLY_WHERE`）、`:4710`、`:5202`（caption） | 同 D2 誠實版；Sheet 選擇那張改指 👤 我的 | 部分（Sheet 選擇關閉；觀察清單管理仍待 P2） |
| D5 | 「到『💼 我的持股 › 組合設定』新增至少一列持股」——指回自己的唯讀葉 | `page_hold.py:1783`（`CASH_WATCHLIST_ONLY_WHERE`；客戶逐字提供的句子） | 改句需客戶同意（E3-r1 客戶逐字）；建議改指 D2 誠實版 | ⚠️ 需客戶確認改字 |
| D6 | 觀察清單管理「現行入口：📁 組合管理／選股網加入觀察清單」 | `page_hold.py:4296-4297` | 新版模式兩者都看不到 ⇒ 同 D2 誠實版 | ⚠️ 直到 P2／🎯 Gate |
| D7 | 側欄 caption「登入後可在『📁 組合管理』頁雲端存取」 | `app.py:398` | 新版模式改顯示「登入後到 👤 我的選 Sheet」；舊模式原句不動 | ✅ 關閉（新版模式） |
| D8 | OAuth 未設定 → 新版模式無任何綁定方法 | `app.py:399-404` | 👤 我的卡① 誠實說明（F4）；⛔ 不提供未登入綁定（讀取本來就需登入，SEC-3） | ✅ 關閉（變成誠實的終點，不是死路） |
| D9 | 沒有任何頁說「把側欄切回『不使用』」 | 全部 view | D2 誠實版指路統一帶這句 | ✅ 關閉 |
| D10 | `render_login_cta` 的 OAuth 未設定句「可用左側『🔐 Google 帳號』貼 Sheet 網址／ID」—— 側欄貼上框在未登入時不出現 | `portfolio_binder.py:60` | 若 👤 我的重用此元件須改句（舊模式消費者同受影響） | ✅ 關閉（隨元件重用） |
| D11 | 選股網「需先在側欄貼 Google Sheet ID（或在 📁 組合管理設定）」 | `app.py:917`、`:945` | 屬舊模式；🎯 頁 Gate 時改指 👤 我的 | 不在本頁範圍 |
| D12 | 「本頁只取**第一本**組合／**第一份**觀察清單 —— 畫面上這幾檔不是你的全部」，但**沒有任何控制可以選**哪一本；`list_portfolios` 回 `sorted()`（`gsheet_portfolio.py:603`）⇒「第一本」＝**名稱排序第一本**；舊 📁 組合管理可以載入指定那本（`portfolio_manager.py:178`、`:246`） | `page_hold.py:4325-4329`；`holdings_service.py:213-215` | 第一期：卡③ 照實寫「🛡️ 目前只分析名稱排序第一本『X』」；能不能選由 **Q7** 決定 | ⚠️ Q7 裁示前**仍是 dead-end**（只有揭露、沒有控制） |

**第一期之後仍存在的缺口（照實寫）**：新增／修改／刪除持股列、組合、觀察清單，以及建立新 Sheet，在新 UI **仍沒有控制項**；出口是「切回舊版 → 📁 組合管理」的誠實指路，不是 👤 我的。⚠️ 互動矩陣 §8.2 已揭露 `page_hold.py` 的「📁 組合管理」命中**未逐一判讀**是否真的畫到畫面；本表 D2～D6 的行號清單同樣需要 Stage D 前由獨立一組重新窮舉（`CLAUDE.md` §-2 規則 4）。

---

## 6. Sheet SSOT 提案（技術實作，屬內部拍板；只列不做）

> ⚠️ 實作會動 OAuth／Sheet 綁定 ⇒ 依 DEC-081 第 9 點屬 **High**；且 Stage D 前須客戶核准本草稿（DEC-082）。

| # | 提案 | 現況 → 目標 |
|---|---|---|
| S1 | **單一解析器** | 4 份 → 1 份：`portfolio_manager.parse_sheet_id` 的語意（拒絕發布連結）外層套 `oauth_state._sanitize_sheet_id`；放 L0（`shared/`）或 L1 `oauth_state` 旁。順帶修 `/d/e/` → `e` 的 BUG（`app.py:374`、`portfolio_binder.py:28`） |
| S2 | **單一寫入者** | `portfolio_binder.apply_active_sheet` 為唯一寫入契約，**併入** `sync_silent_marker()`（側欄現行多做的那一步，`app.py:386`），避免靜默重登退化 |
| S3 | 側欄與 `?sheet=` 都走 S1＋S2 | 側欄 inline（`app.py:375-386`）改呼叫 S2；`?sheet=` 還原（`app.py:152-158`）先過 S1 消毒（保留 `setdefault`「當次選擇優先」語意） |
| S4 | **一個選擇器元件** | 👤 我的重用 `render_drive_picker`／`render_paste_id_binder`（調整後），不寫第 5 份 |
| S5 | 單本不自動綁 | 移除 `portfolio_binder.py:126-130` 的自動綁（或改為「預選但要按 ✅」）—— 綁定是權限決定，應由使用者明確按下<br>📌 客戶裁示：唯一本自動綁**取消**，「不要替使用者做綁定決策」；不論是否預選，綁定都必須由使用者明確按「使用這本」（後半句為撰寫組讀法）（DEC-083 C 段）（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083） |
| S6 | 消費者經一支 L3 讀取 | 新增 L3 accessor（例：`portfolio_binding_service` 擴充 `get_active_sheet()` 回傳 `{sheet_id, title, source, channels_consistent}`）；`holdings_service`／`page_today`／`page_find`／`watchlist_service`／`forward_test` 逐步改讀它，⛔ 不再各自讀兩個 session key |
| S7 | Sheet 標題 | 啟用既有 `get_sheet_title`（`gsheet_portfolio.py:1154-1163`），經 L3 帶快取。⚠️ 現行它 `except Exception: return ''`，**吞掉所有例外**（違 `CLAUDE.md` §1）⇒ 必須改成 fail loud（或新增一支會 raise 的版本），讓 404（找不到）／403（沒權限）／逾時分得開，卡② 才能照 §3.1 顯示正確原因 |
| S8 | 死殼清理 | `portfolio_manager._apply_active_sheet`（0 caller）等，依 v3 §01-2 只清「因本次改動才變孤兒」者，逐檔列在交付報告 |

---

## 7. 需要客戶裁示的 7 題

> 只問業務與畫面。純技術（§6）內部拍板，不在這裡問。每題標明是否碰 OAuth／credential／Sheet 寫入（→ High）。

### Q1｜👤 我的放哪？（碰 OAuth 與綁定 → High）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 側欄新增第 7 頁「👤 我的」** | 符合客戶 2026-10-25 IA（👤 我的是獨立頁）；帳號／Sheet 只有一個家；其他頁都能指到同一處 | 導航多一項（改 `ia_nav.PAGE_LABELS` ＋ `app.py` 對帳） | 低 |
| B 放進 🛡️ 持股的「組合設定」葉 | 不加頁 | 🛡️ 被測試釘死唯讀，要放登入／切換就得改它的唯讀政策；🎯／🚦 要綁 Sheet 也得繞到持股頁 | 中：🛡️ 職責混雜 |
| C 維持只在側欄 | 改動最小 | 側欄沒有 Drive 清單、未登入看不到貼上框；dead-end 關不掉 | 高：違反 DEC-081 第 7 點 |

**AI 總管推薦：A。** 理由：帳號與 Sheet 是**全站**設定，不屬於任何一頁；放 🛡️ 會破壞它的唯讀保證。施工期間側欄的登入／貼 ID 照舊保留（比照 DEC-020「先並存、驗收後才切換」）。

**客戶裁示：A（DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：側欄新增獨立「👤 我的」，為 Google 帳號、Sheet 綁定與新版 Sheet SSOT 的唯一設定入口。

### Q2｜第一期做多少？（A 碰 OAuth＋綁定 → High；B 另含 Sheet 寫入 → High）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 第一期＝帳號＋綁定＋Drive 清單＋切換＋重新讀取（只清本人）；⛔ 不寫 Sheet 內容。建立 Sheet、組合／清單 CRUD ＝第二期，另開 High Gate；期間舊 📁 組合管理仍是寫入入口** | 第一期只改「讀哪一本」，不碰你 Sheet 裡的資料；可先關掉最痛的「選不到 Sheet」 | 新增／修改持股列仍要切回舊版（§5 D2～D6 照實指路） | 低 |
| B 第一期就含建立 Sheet＋組合／清單 CRUD | 一次到位 | 同一批同時改登入、綁定、寫入三件 High 事項；CRUD 兩段重複、整表重寫要先重構 | 高：一次動到使用者資產 |
| C 第一期只顯示狀態（不能切換） | 最安全 | 還是要去側欄或舊版才能綁 | 中：dead-end 不減 |

**AI 總管推薦：A。** ⚠️ 前提：A 的「不寫 Sheet 內容」**要先修好讀取路徑才真的成立**（Q3）—— 現行連「列出組合」都可能寫入你的 Sheet，**前進式驗證的對帳讀取（`load_forward_test_picks` → `_ft_worksheet`）也一樣**（A.6 H1）；兩處都要修。

**客戶裁示：A（DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：P1 只做登入／登出／重新登入、Sheet URL／ID、Drive 清單、明確選擇／切換、重新讀取、active Sheet／portfolio／watchlist；建立／rename／刪 Sheet 與組合／觀察清單／持股列 CRUD 留 P2（另開 Stage A/B/C Gate）；P2 完成前保留舊「📁 組合管理」。

### Q3｜「讀取時會改你的 Sheet」這個修正排在哪一批？（Sheet 資料層寫入行為 → High）

現況（讀碼，未實測）：只要讀，系統就可能 (a) 在你的 Sheet **自動新增**「portfolios」「stock_watchlist」或「forward_test_picks」分頁，(b) 第 1 列不是預期欄名時**直接覆寫你的第 1 列**（`gsheet_portfolio.py:454-461`；前進式驗證凍結紀錄 `:891-907`，覆寫 `A1:F1`）。🛡️ 持股、今天頁綁定狀態、板塊資金、選股對帳的讀取都經過這兩段。`forward_test_picks` 是**不可重建的凍結歷史**（`CLAUDE.md` §-1.5.F 判定 3(5)）。

**這一題不問「要不要修」**：讀取時改寫使用者的 Sheet 違反 `CLAUDE.md` §1 與 v3 §02，**AI 總管已判定為內部 bug 修正**（缺分頁 → 顯示「⬜ 尚無此分頁」；表頭不符 → 「⚠️ 資料疑義」；讀取一律不寫；建分頁改到使用者按下寫入時才做）。因為它改的是 Sheet 資料層的寫入行為，依客戶 Effort 規則（DEC-081 第 9 點）屬 **High**；**唯一要請您決定的是排程**：

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 在 👤 我的 Stage D 之前，先開一個獨立 High 批次修好** | 範圍小、好驗；👤 我的上線時「唯讀」承諾已經成立；🛡️ 與對帳也同時受益 | 👤 我的晚一個批次開工 | 低（需完整回歸測試，含舊模式「第一次存檔」） |
| B 併入 👤 我的 Stage D 一起做（同樣 High） | 少開一批 | 同一批同時改登入、綁定、資料層三件 High 事項，驗收面大 | 中：問題出在哪一件較難切分 |

**AI 總管推薦：A。**

**客戶裁示：A（DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：👤 我的正式實作前，先獨立完成 Sheet Safety 修復批（DEC-083 B1～B5，High；含 forward-test 歷史零寫入、單一 parser、單一綁定寫入契約、per-user cache 失效）。

### Q4｜Sheet 身分怎麼顯示？（識別碼外露；不碰寫入）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 標題＋ID 末 6 碼** | 認得出是哪本；ID 不整串外露（截圖、分享畫面較安全） | 需多讀一次標題（可快取） | 低 |
| B 完整 ID | 最精確、可直接比對 | 截圖即外露完整識別碼 | 中 |
| C 只顯示標題 | 最乾淨 | 同名 Sheet 分不出來 | 中：綁錯本不自知 |

**AI 總管推薦：A。** 完整 ID 放在「詳細」裡用 [複製] 取得、不直接印出；email 依同一原則遮罩。⚠️ Sheet ID 非憑證（存取仍需登入＋Google 權限），本題是**降低外露**，不是修安全漏洞。

**客戶裁示：A（DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：一般 UI 顯示「Sheet 名稱＋ID 末 6 碼」。

### Q5｜登出代表什麼？（OAuth security → High）

現況：登出只清登入權杖，**綁定的 Sheet 和網址上的 `?sheet=` 都留著**（`app.py:361-366`）。讀取快取本來就按「呼叫 Google 的身分指紋」分開存（SEC-1，`gsheet_portfolio.py:362-418`），別人不會讀到你的快取內容。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 登出同時清掉本分頁的 Sheet 綁定（兩個 session 欄位）、清掉網址上的 `?sheet=`，且之後的登入 state 不再夾帶舊的 Sheet ID** | 在同一個瀏覽器接著用的人，**看不到你綁的是哪一本 Sheet** | 同一人重新登入要再選一次 Sheet（Sheet 清單一鍵可選） | 低 |
| B 保留綁定（現行） | 重新登入最快 | 「登出」名不副實：下一個人看得到你綁的是哪本 | 中 |

⚠️ **A 必須三件一起做**：只清 session 不清網址，重新整理後 `app.py:152-158` 會從 `?sheet=` 把它綁回來；若登入鈕仍把目前 Sheet ID 夾進 state（`app.py:395`），下一個人一登入也會被回綁到你那本。

**AI 總管推薦：A。**

**客戶裁示：A（DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：另明列須一併清除「OAuth state／登入流程攜帶的舊 Sheet ID」與「會造成登出後重新自動綁回舊 Sheet 的 silent marker」；不得登出後自動恢復上一個 Sheet。

### Q6｜組合和觀察清單要不要能放在不同本 Sheet？（綁定模型 → High）

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 一本 Sheet 同時放組合與觀察清單（＝現行實際行為）；兩者讀到不同本時顯示白話警示＋一鍵統一** | 符合你實際的用法；只要選一次 | 想刻意分兩本的人做不到（現行新舊 UI 本來也做不到） | 低 |
| B 允許組合與觀察清單各選一本 | 可分開管理 | 多一個選擇器；容易選錯，🛡️ 的組合與清單可能來自不同本 | 中 |

**AI 總管推薦：A。**

**客戶裁示：A（DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：legacy 兩者不一致時顯示白話警示；不偷偷選 ETF 通道或個股通道、不自動覆寫其中一個，讓使用者在 👤 我的明確重新選定。

### Q7｜要不要能選 🛡️／🎯 分析「哪一本組合／哪一份觀察清單」？（綁定模型 → High；不寫 Sheet）

現況：Sheet 裡有好幾本組合時，🛡️ 只分析**名稱排序第一本**（`holdings_service.py:213-215`、`gsheet_portfolio.py:603`），畫面只寫「還有別的沒讀」（`page_hold.py:4325-4329`），沒有地方可以換（§5 D12）。

| 方案 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| **A 可以選：👤 我的提供一個選擇器（哪一本組合、哪一份清單），🛡️／🎯 等頁共用同一個選擇** | 想看哪一本就看哪一本；全站一致，不會這頁看 A、那頁看 B | 👤 我的多一個控制項；選擇要記住（同 Sheet 綁定的持久化方式） | 低 |
| B 維持名稱排序第一本，畫面照實揭露 | 不加控制項 | 想看第二本只能改名字或切回舊版 | 中：使用者以為看的是全部 |
| C 把所有組合合併成一份分析 | 一次看全部 | 同一檔在兩本組合會重複計算張數／均價，合併規則本身要另定義 | 高：數字語意改變 |

**AI 總管推薦：A。** 理由：「分析哪一本」是你的業務選擇，系統不該用名稱排序替你決定；A 只改「讀哪一本」，不寫你的 Sheet。

**客戶裁示：A（DEC-083）**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）：👤 我的提供全站共用 active portfolio／active watchlist；🛡️／🎯／⚡ 等頁只能讀這個共同選擇；不得再以「名稱排序第一本」作為不可見的業務決策。

---

## 8. 不能刪的東西／本草稿不做的事

- ⛔ 不刪、不改：舊 UI 全部、📁 組合管理、側欄登入／登出／貼 ID／🔍 測試連線／🔄 強制刷新、🔗 我的組合狀態列、所有 Sheet CRUD 與其 backend（DEC-081 第 8 點：須 Old capability → New coverage → regression → customer verification → removal Decision Gate）。
- ⛔ 不改導航（`shared/ia_nav.py`、`app.py` 路由）、不寫 code、不動 OAuth／綁定／Sheet 寫入 wiring（DEC-082 第 6 點）。
- ⛔ 不碰 `forward_test_picks` 與 `data_cache/forward_test/picks.parquet`（不可重建）。
- C2b 未開始；`PRODUCTION_WRITE_APPROVED=False`（`shared/risk_cap_history_policy.py:216`）不變；本檔與 Risk Cap 無關。
- §4 的「DROP?」只是**刪除候選登記**，不是刪除決定。

---

## 9. 揭露（`CLAUDE.md` §-2 規則 6）

1. §A 盤點由**兩組獨立唯讀盤點**產出，核心事實一致；撰寫組另逐條讀碼核對 §A 所列 file:line（基準 `286e0075`，程式碼與 `cebb19e6` 相同）。「沒有其他遺漏」**未證明**：兩組都以 grep／讀碼為主，會漏動態 import 與間接 widget。
2. **H1「讀取路徑會寫 Sheet」是讀碼結論，沒有對真的 Google Sheet 實測**；「每一次讀取都經過它」以 `_all_records` → `_ws` → `_get_worksheet` 的呼叫鏈推得，快取命中時（`TTL_15MIN`）不會走到 `_get_worksheet`【INFERENCE】。`_ft_worksheet`（`:891-907`）由 `load_forward_test_picks` 直接呼叫、**沒有快取**，依讀碼每次對帳讀取都會走到；同樣未實測。目前只有舊模式的「📊 對帳」按鈕（`app.py:969-972` → `reconcile_all`）會觸發這條讀取（撰寫組 grep `reconcile_all`／`load_forward_test_picks` 所得，單組）。
3. 「`clear_read_cache`／側欄 🔄 會清掉所有使用者的快取」依 `st.cache_data` 函式 `.clear()` 的語意推得，**未實測**。
4. 「新版模式下板塊資金的 ETF 持股標示恆為空」為讀碼推論，**未實跑**。
5. §5 的 dead-end 行號清單沿用互動矩陣 §8 並補讀；互動矩陣 §8.2 已承認未逐一判讀，本檔**同樣未判讀**每一處是否真的畫到畫面。
6. §2／§3／§4「去向」／§6／§7 的所有推薦都是 **AI 總管的推薦，不是客戶決定**；Stage C 客戶裁示前一律不得當成已核准規格。
7. 本檔本身**尚未經第二組獨立複驗**。

---

## 10. 狀態補註（append-only；本檔 §0～§9 一字未改）

📌 **2026-10-25**（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））：
- **Stage C 已裁示**：`docs/DECISIONS.md` **DEC-083**（Q1～Q7 全採 A＋A～H 段）。
- **Stage D P1 已實作，在 PR #927（待合併）**：分支 `claude/determined-euler-32xqjn`（撰寫組讀碼基準 `4e8c0876`）；新頁 `src/ui/views/page_me.py`。實作狀態摘要見 `docs/PROJECT_STATE.md` §38；與本草稿線框的已知落差（例：§3.5「最後讀取時間」未實作）與其他殘留登記於 `docs/BACKLOG.md` 5.1.13（`NAV-PERSIST` 起 11 列）。
- P2（建立／rename／刪 Sheet、各類 CRUD）**未開始、未授權**（DEC-083 H.9）；舊 UI 照留（E 段）。
- ⚠️ 本補註由單一撰寫組產出，**沒有第二組驗過**（`CLAUDE.md` §-2 規則 6）。
