# 舊 UI → 新 UI 互動控制覆蓋矩陣（Interaction Coverage Matrix，初稿）

- 日期：2026-10-25｜撰寫：文件撰寫組（AI 總管派工）
- 對應待辦：`docs/BACKLOG.md` 5.1.13 `UIX-INTERACTION-COVERAGE`（並供 `UIX-ME-SHEET-SSOT`、`UIX-HOLD-DEADEND`、`UIX-FIND-INPUTS`、`UIX-DATACENTER-CONTROLS`、`UIX-ACTION-PAGE` 引用）
- 裁示依據：`docs/DECISIONS.md` **DEC-081** 第 7 點（客戶原文：「新版不能只『看』，必須能『操作』」）
- 狀態：**初稿，⛔ 非 Approved、未經獨立複驗**。本檔只是盤點與提案；任何新增控制項都屬 UI 變更，動工前要先出文字線框草稿送客戶（`CLAUDE.md` §-1.5.D §03-2 ①、DEC-003）。
- 標記：**FACT**＝有 file:line 或讀碼實證｜**INFERENCE**＝由事實推得，沒有在 Streamlit 實測｜**PROPOSAL**＝撰寫組／總管提案，待客戶裁示

---

## 0. 基準、方法與限制

### 0.1 基準
- 盤點基準：`main` @ `5e2e6e23`（量測日 2026-10-25）。之後的 `6dad38cb`（大盤頁實作）只改了 `app.py`、`shared/ia_nav.py`、新增 `page_market.py` 等，`page_hold.py`／`page_today.py`／`src/ui/tabs/**` 等其他 UI 檔**未動**（FACT：`git diff 5e2e6e23 6dad38cb --stat`），所以下表行號在 `6dad38cb` 仍然有效，**只有 `app.py` 例外**。
- ⚠️ **`app.py` 行號以 `5e2e6e23` 為準**。在 `6dad38cb`：第 290 行以後 ＋1、第 554 行以後 ＋8、第 584 行以後 ＋9（FACT：`git diff 5e2e6e23 6dad38cb -- app.py` 的 hunk 標頭）。例：本檔寫的 `app.py:620`（`st.stop()` 附近）在 `6dad38cb` 約為第 629 行。
- 「大盤頁互動」一節（§4.1）以 `6dad38cb` 為準。

### 0.2 目標頁與現行程式的落差（FACT）
- 目標頁採客戶 2026-10-25 的 IA：👤 我的／🛡️ 持股／🎯 標的／📊 大盤／🩺 資料中心／⚡ 行動。
- 現行程式的新 UI（`shared/ia_nav.py`）：`6dad38cb` 起是 **📊 大盤**＋原 IA v2 五頁（🚦 今天／🔍 找標的／🔬 查一檔／💼 我的持股／📖 憑什麼）。**👤 我的、⚡ 行動、🩺 資料中心三頁還沒有 view。**
- 下表「新 UI 位置」寫的是現行頁面。對照方式（撰寫組讀法，依 `docs/DECISIONS.md:654`）：今天→📊 大盤；找標的＋查一檔→🎯 標的；我的持股→🛡️ 持股；憑什麼的資料體檢→🩺 資料中心。

### 0.3 方法
1. AST 掃描 `app.py` 與 `src/ui/**/*.py`（共 100 檔），列出所有 `button／text_input／text_area／selectbox／radio／multiselect／checkbox／form／form_submit_button／file_uploader／link_button／page_link／switch_page／toggle／number_input／date_input／slider／select_slider／segmented_control／pills／download_button／data_editor／tabs／chat_input／popover` 呼叫 → **179 個呼叫點**（基準 `5e2e6e23`，不含 `page_market.py`）。`file_uploader`、`page_link`、`switch_page`、`toggle` 為 0 命中。
2. 頁面歸屬靠人工讀 `app.py` 路由判斷（新版模式在 `app.py:600-620` render 選到的頁後 `st.stop()`；舊頁籤在 `app.py:652` 之後）。
3. 大盤頁（§4.1）另讀 `page_market.py` 原始碼。

### 0.4 盲點（`CLAUDE.md` §-2 規則 6）
- 掃不到：經 helper 間接產生的 widget（例：`_ui_kit.single_submit_form`，已人工追到 caller）；迴圈產生的 widget，AST 只算 1 個（例：`page_inspect.py:2984` 的 MA checkbox、`pattern_targets_ui.py:241` 的 number_input）；`getattr(st, …)` 動態呼叫；`st.expander` 未列入 widget 清單。
- 全部由單一調查組＋單一撰寫組產出，**沒有第二組驗過**。「沒有遺漏」**未證明**，本檔只能當待驗事項，不得當驗收依據。
- 「狀態」只看「新 UI 有沒有對應入口」，**沒有**驗證行為是否與舊 UI 等價。

### 0.5 路由的承重事實（FACT）
- `app.py:600-620`：新版模式畫完選到的頁就 `st.stop()`。以下三樣寫在其後，新版模式**都不畫**：
  - `render_portfolio_status_bar()`（`app.py:632`，全域「🔗 我的組合」popover，內含 Drive 挑選器）
  - `render_macro_compass()`（`app.py:639`）
  - 7 個舊頁籤（`app.py:652`），含 📁 組合管理
- 側欄（`app.py:308-500`）在 `st.stop()` 之前，新舊模式都畫：Google 登入／登出、Sheet ID 貼上框、🔍 測試連線、🔄 強制刷新、側欄資料健康（含 🤖 AI 解讀）。

### 0.6 狀態用語
| 狀態 | 意思 |
|---|---|
| **已接** | 新 UI 有對應入口（含「借側欄」：寫在側欄、新版模式看得到，但不在目標頁內） |
| **部分** | 有入口，但少了舊 UI 的部分輸入或選項 |
| **待接** | 新 UI 沒有入口 |
| **dead-end** | 新頁叫使用者去做某事，但新版模式下沒有地方可以做（DEC-081 禁止） |
| **重複** | 同一個操作有兩份以上實作 |

---

## 1. 👤 我的（帳戶／連線／Sheet 設定）— ~~新 UI 尚無此頁~~ ~~👤 我的 P1 在 PR #927（待合併）~~ 👤 我的 P1 PR #927 已合併（squash `ab705fbf` on main），覆蓋更新見 §11（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））

| 控制項 | 舊位置 | backend | 新 UI 位置 | 狀態 | 備註 |
|---|---|---|---|---|---|
| 🔐 用 Google 登入（link_button） | `app.py:396` 側欄；`portfolio_binder.py:66`（`render_login_cta`） | `infra.oauth::build_authorize_url`；`oauth_state::get_oauth_cfg／login_state_with_sheet` | 側欄（新版模式可見） | 已接（借側欄） | 要搬進 👤 我的 |
| 🚪 登出 | `app.py:360` | 就地 pop `gsheet_tokens／gsheet_email／_oauth_state`＋`oauth_state::forget_silent_reauth` | 側欄 | 已接（借側欄） | 登出邏輯寫在 L6 inline，**沒有** service |
| 登入狀態顯示 | `app.py:358` | `st.session_state['gsheet_tokens']` | 側欄；🛡️ 綁定卡顯示是否已綁（`page_hold.py:991-1125`） | 已接 | |
| Sheet 連線狀態 | `portfolio_status_bar.py:46`（popover）；`portfolio_manager.py:138-143` | `portfolio_binding_service::get_binding_state` | 🛡️ 葉2 兩張卡（`build_binding_card`／`build_portfolio_count_card`，唯讀、不印 sheet_id） | 已接（在持股頁） | status bar 新版模式**看不到**（`app.py:632` 在 stop 之後） |
| Sheet URL／ID 輸入＋URL 自動解析 | ① `app.py:368`（側欄；解析 `app.py:373` inline regex）<br>② `portfolio_binder.py:73`（`render_paste_id_binder`，`_SHEET_URL_RE` 在 `:28`） | 解析有 **4 份實作**（§7.2）；寫入：① 側欄 inline（`app.py:381-387`）、② `portfolio_binder::apply_active_sheet` | 只有側欄 ① | 已接（借側欄）＋**重複** | 最嚴格的解析器 `portfolio_manager.py:78::parse_sheet_id` 沒有 production caller（只有 `tests/test_portfolio_manager.py`） |
| 📂 從 Drive 列出可用 Sheet（＋資料夾選單） | `portfolio_binder.py:104`（資料夾 selectbox `:101`） | `gsheet_portfolio::list_user_folders／list_user_sheets` | 無 | **待接** | 三個舊入口（status bar、📁 組合管理、舊 💼 戰情室）新版模式都看不到 |
| 選擇／切換 Sheet（selectbox＋✅ 使用此 Sheet） | `portfolio_binder.py:133／135` | `portfolio_binder::apply_active_sheet` | 無；🛡️ 未接線卡 `hold.setup.pick_sheet` 明說「本頁不提供」（`page_hold.py:1797`、`4286-4291`） | **待接** | 寫 session＋`?sheet=`，不寫 Google |
| 🆕 建立新投組 Sheet | `portfolio_binder.py:110` | `gsheet_portfolio::create_new_sheet` | 無 | 待接 | ⚠️ **寫入使用者的 Google Drive**（High） |
| 🔄 重新讀取（清讀取快取） | `etf_tab_dividend_station.py:142` | `gsheet_portfolio::clear_read_cache` | 無 | 待接 | 可歸 👤 或 🛡️ |
| 🔍 測試連線 | `app.py:446` | L6 inline `requests.get`（FinMind／TWSE／Yahoo），`verify=False` | 側欄 | 已接（借側欄）＋**重複** | 與 `api_diagnostic.py:153` 重疊；建議歸 🩺 |

`gsheet_portfolio::rename_sheet`、`get_sheet_title` 沒有 UI caller（FACT：grep `app.py src`）。

## 2. 🛡️ 持股

> 📌 2026-10-26 append-only 註記（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））：本節的行號、狀態與備註已由 **§12.2**（Stage A 深度盤點；基準：程式碼＝main @ `15cd8fff`，4e6bf8ee→15cd8fff 僅 docs 變更、0 程式碼變更，見 §12.0）核對並更正；不符處彙整於 §12.6。本節舊文字保留，下表被推翻的狀態以刪除線標註。

| 控制項 | 舊位置 | backend | 新 UI 位置 | 狀態 | 備註 |
|---|---|---|---|---|---|
| 讀持股 gate（只讀市場／加讀 Sheet）＋ 🚀 執行 | 舊：`etf_tab_dividend_station.py:196`（無範圍選擇） | `holdings_service::get_holdings` | `page_hold.py:4984`（`single_submit_form`，label 在 `:439`） | 已接 | |
| 顯示目前綁定的 Sheet | `portfolio_status_bar.py:84`（印 sheet_id）；`portfolio_manager.py:141` | `get_binding_state` | 🛡️ 只顯示「有沒有綁」（刻意不印 ID，`page_hold.py:991-996`） | 部分 | 要不要顯示 Sheet 名稱：`get_sheet_title` 已存在但沒人用 |
| 往「我的」設定的入口 | — | — | 文字指到側欄（`page_hold.py:1689-1692`、`page_today.py:1051`） | 部分（只有文字） | 沒有按鈕或連結；👤 我的頁還不存在 |
| 重新載入持股（繞過快取） | `etf_tab_dividend_station.py:142` | `clear_read_cache` | 無；`holdings_service.py:27` 明寫**不**呼叫 `clear_read_cache` | **待接** | INFERENCE：重按 🚀 可能在 L1 快取 TTL 內拿到舊值 |
| 資料狀態（idle／empty／failed／登入過期） | `etf_tab_dividend_station.py:171-197` | `portfolio_binding_service`、`holdings_service` | 🛡️ 卡片（`page_hold.py:1064-1230`） | 已接 | |
| 缺 Sheet 時就地綁定 | `etf_tab_dividend_station.py:187`、`portfolio_status_bar.py:78` → `portfolio_binder::render_holdings_binder` | 同 §1 | 無，只有文字指到側欄 | **dead-end（半）** | 見 §8 |
| ⚡ 生成 AI 總結 | `etf_tab_dividend_station.py:698`；`section_ai_portfolio.py:63／65` | AI L3 | `page_hold.py:5072`（label 在 `:3816`） | 已接 | |
| 組合／觀察清單管理（載入／儲存／刪除） | `portfolio_manager.py:166-298` | `gsheet_portfolio` CRUD | 未接線卡 `hold.setup.watchlist`（~~`page_hold.py:1798`~~ 重驗 @15cd8fff 更正：行號漂移，現為 `page_hold.py` 的 `key="hold.setup.watchlist"` 卡片定義，約 `:4449`；以符號為準）；~~`page_hold.py:5202` caption「唯讀 —— 要新增／修改／刪除請到既有的 📁 組合管理分頁」~~（現文為客戶逐字句「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」，`ia_nav.CONTENT_EDIT_OLD_UI_WHERE`；見 §12.6）（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） | **待接**＋**dead-end** | 寫入 Google，High；🛡️ 目前以黑名單釘死唯讀（~~`page_hold.py:25-31`~~ 重驗 @15cd8fff 更正：該行號已不是此宣稱所在；現為 `page_hold.py` 檔頭 docstring「測試釘死」段，指向 `tests/test_p04_hold_view.py::TestReadOnly`；本輪未跑該測試，屬轉述） |

## 3. 🎯 標的

> 📌 2026-10-26 append-only 註記（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））：本節已由 **§12.1**（Stage A 深度盤點；基準：程式碼＝main @ `15cd8fff`，4e6bf8ee→15cd8fff 僅 docs 變更、0 程式碼變更，見 §12.0）核對、補深與更正（含「板塊資金潮汐」已驗、三階段濾網全不可達、型態目標價等漏列）；不符處彙整於 §12.6。本節舊文字保留。

| 控制項 | 舊位置 | backend | 新 UI 位置 | 狀態 | 備註 |
|---|---|---|---|---|---|
| 個股代碼＋🔍 載入完整分析 | `tab_stock.py:211／218` | 個股 L1／L3 | `page_inspect.py:2958／2986`（form） | 已接 | 只吃代碼；**名稱搜尋新舊都沒有**（INFERENCE：label 只寫「代碼」） |
| ETF 代號＋對照基準＋🔍 開始診斷 | `etf_tab_single.py:95／98／103` | ETF L1／L2 | `page_inspect.py:2962`（判型）＋同一 form | 部分 | 「對照基準」輸入沒有 |
| 天數／期間 | `tab_stock.py:213`（slider） | — | `page_inspect.py:2968`（selectbox） | 已接 | |
| MA5～MA240 勾選 | `tab_stock.py:225-235` | — | `page_inspect.py:2984`（迴圈） | 已接 | |
| 一般 K 線 | `tab_stock.py:215` | — | 無 | 待接 | |
| 🔄 強制重抓（個股） | `tab_stock.py:538` | 清快取 | 無 | 待接 | |
| 🤖 AI 首席顧問報告／清除 | `tab_stock.py:1543／1545` | AI L3 | 無 | 待接 | |
| 🔬 AI 財報體檢 | `tab_stock.py:1022` | financial_health | 無 | 待接 | |
| PE 估值區間 | `section_357_valuation.py:306` | — | 無 | 待接 | |
| 心理檢核三勾 | `section_psy_checklist.py:169／190／202` | — | 無 | 待接 | |
| 總資金（部位計算） | `section_when_buy_sell.py:195` | — | 無 | 待接 | |
| 型態目標價 ZigZag／go／override | `pattern_targets_ui.py:198／210／241／242` | pattern targets L2 | 無 | 待接 | |
| 多檔代碼＋🚀 批次分析 | `tab_stock_grp.py:52／58`；ETF `etf_tab_grp_compare.py:116／127` | `run_batch_fetch` 等 | `page_inspect.py:3008／3012／3017` | 已接（個股與 ETF 合併） | |
| 下鑽看某一檔 | `section_portfolio_summary.py:558` | — | `page_inspect.py:3155` | 已接 | |
| **帶入我的持股** | **新舊都沒有**（grep `帶入` 0 命中；舊 `tab_stock_grp.py:46-47` 預設值是寫死的 10 檔） | 可接 `holdings_service::get_holdings`（唯讀） | 無 | **待接（新功能，不是移植）** | 屬新增控制項 → 先出線框（DEC-003 ①） |
| 風險貢獻 editor＋🎚️ 算 | `tab_stock_grp.py:160／166` | `risk_contribution` | 無 | 待接 | |
| 月營收權重 slider | `tab_stock_grp.py:320` | — | 無 | 待接 | |
| 🤖 AI 掃利空 | `section_portfolio_summary.py:715` | — | 無 | 待接 | |
| 選股條件 multiselect＋🎯 開始選股 | `app.py:773／780` | `fundamental_screener_service::get_ranked_picks` | `page_find.py:2227／2235／2240` | 已接 | |
| 💾 下載選股 CSV | `app.py:888` | — | `page_find.py:2291` | 已接 | |
| ➕ 加入觀察清單（勾選／選清單／新清單名／加入） | `app.py:895／904／911／913／916` | `watchlist_service::add_picks_to_watchlist` | 無 | 待接 | ⚠️ 寫入 Google（High） |
| 🧊 凍結前 20 名 | `app.py:937` | `forward_test_service::freeze_current_picks` | 無 | 待接 | ⚠️ 寫入不可重建的凍結快照（High） |
| 📊 對帳 | `app.py:960` | `forward_test_service::reconcile_all` | 無 | 待接 | |
| 🌍 掃全台股跨季趨勢＋CSV | `app.py:1003／1029` | cross_quarter_trends | 無 | 待接 | |
| 預篩「顯示全市場」 | `tab_stock_picker.py:187` | — | 無 | 待接 | |
| 三階段篩選（多選／額外代碼／go／AI） | `tab_stock_picker.py:395／400／435／572` | — | 無 | 待接 | |
| 產業熱力圖（市場／區間／刷新／載入／AI） | `etf_render.py:674／676／679／715／783` | `etf_sector_service` | `page_find.py:2309`（🗺️ 載入板塊地圖，一顆） | 部分 | 選市場、選區間、AI 都沒接 |
| 板塊資金潮汐 | `tab_sector_flow`（掃描範圍內 0 個 widget） | `sector_flow_service` | 板塊地圖葉 | 已接？（未驗） | |
| ETF smart（代號／窗口／分散度／同儕） | `etf_tab_smart.py:93／127／282／498` | — | 無 | 待接 | 歸 🎯 或 🛡️ 未定 |

## 4. 📊 大盤

### 4.1 大盤頁互動（本批已接，`6dad38cb`）

FACT：讀 `src/ui/views/page_market.py`。本頁的計算與更新流程全部呼叫 `page_today` 的同一段程式（`today._xxx`），不另寫一套。

| 互動 | 位置（`page_market.py`） | 做什麼 | 狀態 | 備註 |
|---|---|---|---|---|
| 🚀 更新（warm／force 二選一＋送出） | `render_page_market` → `today._render_update_form(_session)` | 與今天頁同一支 form，同一份更新報告 | 已接 | ⚠️ 按鈕字樣仍是「🚀 更新今日戰情」，與 Gate 檔 §1.1 線框「🚀 更新大盤資料」不同（form 與今天頁共用，今天頁驗收前不改） |
| 上一次更新的報告 | `_render_report_guarded` → `today._render_refresh_report` | 逐來源成功／失敗 | 已接 | 舊格式畫不出來時紅字＋清掉，不靜默 |
| 展開理由（11 個 expander，預設收合） | `render_page_market` | 市場位階為什麼（X1）、危險度五桶（X2）、風險上限說明（X3）、16 項明細（X4）、台股／國際／總經／籌碼原始資料（X5～X8）、研究中（X9）、資料來源與完整度（X10）、問 AI（X11） | 已接 | |
| 重區塊勾選才畫（4 顆 checkbox） | `SS_GATE_TW_CHART`、`SS_GATE_ADL`、`SS_GATE_INTL_CHART`、`SS_GATE_LEADING` | 加權／台幣走勢、ADL 逐日、國際走勢、先行指標逐日 | 已接 | 本頁自有 key 前綴 `p00m_` |
| 資料中心入口 | 狀態列 caption＋X10：`ia_nav.where_to_find(SECTION_WHY_DATA_HEALTH)` | 文字指到 📖 憑什麼 › 資料體檢 | 部分（只有文字指路，沒有按鈕） | 🩺 資料中心頁尚未存在 |
| 問 AI／查看依據 | X11：`ia_nav.where_to_find(SECTION_WHY_QA)` | 文字指到 📖 憑什麼 › AI 問答 | 部分（只有文字指路，本頁沒有輸入框） | 刻意沿用既有 AI 問答，不另開一套 |
| 🔄 強制刷新數據（全站清快取） | `app.py:485` 側欄 | `st.cache_data.clear()` | 已接（借側欄） | 全域動作，非本頁 |
| Sheet 相關 | — | — | 不適用 | 本頁沒有任何 Sheet 讀寫（DEC-081：⛔ 不得塞 Sheet CRUD） |

📌 2026-10-25 QA 回修（`ad09a04d`；append-only）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管）：上表互動清單**沒有增減**（無新按鈕、無新輸入框）。改的是指路與字樣：X10「資料來源與完整度」依這一輪有沒有更新報告照實指路（沒按過更新時講明報告還沒有）；X3 改指「頁首更新鈕下方」；舊分頁指路寫明側欄「不使用（用下方原功能）」→「🌍 市場環境」；結論句風險上限子句改為客戶逐字。上表「資料中心入口」「問 AI」仍只有文字指路（見 BACKLOG `UIX-MKT-ENTRY-BUTTONS`）；更新鈕字樣仍未改（`UIX-MKT-UPDATE-LABEL`）。全文見 Gate 檔附錄 D.5。

### 4.2 舊 UI 大盤互動對照

| 控制項 | 舊位置 | backend | 新 UI 位置 | 狀態 | 備註 |
|---|---|---|---|---|---|
| 🚀 一鍵更新／🆕 強制重抓 | `tab_macro.py:154／172`；`tab_today.py:620-628`（form） | macro fetch orchestrator | `page_today.py:3901`；大盤頁同一支（§4.1） | 已接（兩顆合成一個 form）＋**重複**（舊 `tab_today` 另有一份） | INFERENCE：`tab_today` 可能已沒有 caller，未驗 |
| 📡 抓取最新羅盤 | `app_render.py:189` | `fetch_macro_compass` | 無（羅盤在 `app.py:639`，新版模式不畫） | 待接 | |
| 展開理由 | `tab_today.py:671`（tabs） | — | `page_today.py:3820／3836`；大盤頁 11 個 expander | 已接 | |
| 問 AI（舊 🧬 AI 問答、新聞 AI） | `tab_ai_chat.py:99／127`；`section_news_ai.py:159／164／167` | AI L3 | `page_why.py:3327`；大盤頁 X11 指路 | 部分 | 新聞掃描與 AI 裁決沒接（Gate 檔 G16、H02） |
| 總經 v2：密度／搜尋／分類 | `tab_macro_v2.py:1253／1316／1321` | — | 無 | 待接 | |
| hot money 4 個 slider | `hot_money.py:251-259` | — | 無 | 待接 | 熱錢三角本批未接（Gate 檔附錄 D） |
| 籌碼雷達清快取 | `chip_radar.py:138` | — | 無 | 待接 | |

大盤頁沒接上的**資料區塊**（不是互動控制項）：全球資金流向、全球風險雷達 9 項、外資連續天數、熱錢三角、櫃買、跨頁狀態列 —— 見 Gate 檔附錄 D 與 `docs/BACKLOG.md` 5.1.13。

## 5. 🩺 資料中心 — 新 UI 尚無此頁

| 控制項 | 舊位置 | backend | 新 UI 位置 | 狀態 | 備註 |
|---|---|---|---|---|---|
| 載入進階診斷 checkbox | `app.py:1097` | `render_data_registry_panel` 等 | `page_why.py:3269`（expander＋checkbox） | 已接 | |
| 🔄 重新整理／🩺 測融資／🛰️ 測 NAS 代理 | `health_inspector.py:373／379／419` | — | 無 | 待接 | |
| 狀態／來源／頻率篩選 | `health_inspector.py:669／673／677` | — | 無 | 待接 | |
| ETF 清快取／深度診斷 | `health_inspector.py:1361／1373` | — | 無 | 待接 | |
| 🚀 開始診斷外連 | `api_diagnostic.py:153` | — | 無 | 待接＋**重複**（側欄 🔍 測試連線） | |
| 校準：期間／執行／清除／下載 | `calibration_ui.py:86／93／98／171` | calibration | `page_why` 只讀校準卡 | 部分 | 「執行校準」沒接 |
| 🤖 AI 解讀資料異常 | `sidebar_health.py:295` | — | 側欄 | 已接（借側欄） | |
| Sheet 建立／刪除 | 見 §7 | — | — | **PROPOSAL：不放資料中心** | 那是使用者資產的 CRUD，不是系統資料維護；建議歸 👤 我的（`UIX-DATACENTER-CONTROLS` 待客戶裁示） |

## 6. ⚡ 行動 — 新 UI 尚無此頁

> 📌 2026-10-26 append-only 註記（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））：本節只列 5 個候選，已由 **§12.3**（Stage A 深度盤點，33 個候選；基準：程式碼＝main @ `15cd8fff`，見 §12.0）補深；不符處彙整於 §12.6。本節舊文字保留，下表兩列自相矛盾的「待接」以刪除線標註。

FACT：沒有 view。候選舊控制項（INFERENCE；⚡ 行動的範圍尚未裁示，`DEC076-CONFIRM` ②）：

| 控制項 | 舊位置 | 狀態 |
|---|---|---|
| 🚀 跑存股戰情室 | `etf_tab_dividend_station.py:196` | ~~待接（⚡ 或 🛡️ 未定）~~ 已接（目前只掛在現行 nav 的 `page_hold`〔💼 我的持股〕，表單提交鈕 `ACTION_RUN_WARROOM_LABEL`，重驗 @15cd8fff），歸屬待 IA Decision Gate（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；見 §12.3 C-01 |
| ✍️ AI 推播文字 | `etf_tab_dividend_station.py:698` | ~~待接~~ 已接（生成：`page_hold` 的 `⚡ 生成 AI 總結`〔`AI_SUMMARY_LABEL`，重驗 @15cd8fff〕；「兩邊都不推送，推送只在 cron」本輪未複驗，標 INFERENCE），與 §2 同列矛盾已解（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；見 §12.3 C-09 |
| 🍇 葡萄串提議 | `grape_ladder.py:426-438` | 待接 |
| ETF 組合計算／再平衡／演算法／稅率 | `etf_tab_portfolio.py:232／255／259／574／950／1438` | 待接 |
| 🎯 今日作戰室 | 🌍 總經（舊）；今天頁 ⑤（未接線） | 待接（`UIX-ACTION-PAGE`；舊今天頁作戰室在新版驗收前不刪） |

`page_hold` 戰情室葉的出場／235 等行動卡只是**顯示**，沒有控制項。

---

## 7. Sheet CRUD 專題

### 7.1 舊 UI 所有實作點（FACT）

| 操作 | 位置 | backend | 寫入對象 |
|---|---|---|---|
| 貼 URL／ID 綁定 | **A** `app.py:368-387`（側欄，inline 寫兩個 session 通道＋`?sheet=`＋`_sb_sync_silent`）<br>**B** `portfolio_binder.py:73-85`（`render_paste_id_binder` → `apply_active_sheet`） | session＋query param | 綁定設定（不寫 Google） |
| 列資料夾／列 Sheets | `portfolio_binder.py:101／104` | `list_user_folders／list_user_sheets` | 讀 |
| 選一本／✅ 使用 | `portfolio_binder.py:133／135`（只有 1 本時自動選，`:123-126`） | `apply_active_sheet` | 綁定設定 |
| 🆕 建立新 Sheet | `portfolio_binder.py:110` | `create_new_sheet` | ⚠️ 寫 Google Drive |
| 組合：載入／儲存／刪除→確認／取消 | `portfolio_manager.py:178／181／193／200／207／211／219／220` | `list_portfolios／load_portfolio／save_portfolio／delete_portfolio` | ⚠️ 寫／刪 Google Sheet |
| 觀察清單：同上 | `portfolio_manager.py:246／249／258／265／272／276／281／282` | `list_stock_watchlists／load／save／delete_stock_watchlist` | ⚠️ 寫／刪 |
| 加入觀察清單 | `app.py:895-929` | `watchlist_service::add_picks_to_watchlist` | ⚠️ 寫 |
| 凍結選股 | `app.py:937` | `forward_test_service::freeze_current_picks` | ⚠️ 寫（不可重建的歷史） |

**「三套」的實際情形（FACT）**：
- 綁定 UI 已收斂成一份共用元件 `portfolio_binder.render_drive_picker／render_holdings_binder`，被 3 處呼叫：`portfolio_manager.py:146`、`portfolio_status_bar.py:78`、`etf_tab_dividend_station.py:187`（各用不同 key 前綴）。
- **側欄 A 是獨立的 inline 複本**：`apply_active_sheet` 的 docstring（`portfolio_binder.py:34-36`）寫「側欄改為呼叫本函式」，但 `app.py:381-387` 實際上沒有呼叫它（grep `apply_active_sheet` 在 `app.py` 0 命中）。
- 組合／觀察清單 CRUD 只有 `portfolio_manager` 一份，但兩段近乎逐字重複（`:166-226` 對 `:229-298`）。

### 7.2 URL → Sheet ID 解析：4 份實作，行為不一致（FACT）

| # | 位置 | 行為 | 問題 |
|---|---|---|---|
| 1 | `app.py:373`（側欄 inline） | `re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)')` | 發布連結 `/d/e/…` 會被解析成 `e` |
| 2 | `portfolio_binder.py:28`（`_SHEET_URL_RE`） | 同一條 regex | 同上 |
| 3 | `portfolio_manager.py:78`（`parse_sheet_id`） | 拒絕發布連結，回空字串 | **沒有 production caller**（只有測試；靜態 grep，未排除 getattr／字串動態引用） |
| 4 | `oauth_state.py:263`（`_sanitize_sheet_id`） | 只做字元集與長度消毒，不解析 URL | 只用在 OAuth state 路徑 |

另外 A、B 寫入 session 前都**沒有**經過 `_sanitize_sheet_id`。INFERENCE：貼任意字串都會進 session 與 `?sheet=`。

### 7.3 共用 backend 現況（FACT）
- L1 `src/data/portfolio/gsheet_portfolio.py`：所有 Sheet 讀寫的單一來源（list／load／save／delete／create／rename／list_user_sheets／clear_read_cache／add_to_stock_watchlist）。
- L1 `src/data/portfolio/oauth_state.py`：登入狀態、靜默重登（EX-OAUTH-1）。
- L3 唯讀：`portfolio_binding_service::get_binding_state`、`holdings_service::get_holdings`。
- L3 寫入：只有 `watchlist_service::add_picks_to_watchlist`、`forward_test_service::freeze_current_picks`。
- **沒有** L3 的「綁定寫入」或「組合 CRUD」service；現在是 L5 經 EX-PASSTHRU-1 直接呼叫 L1。

### 7.4 單一 SSOT 流程提案（**PROPOSAL，未實作、未核准**）

> ⛔ 本節只是提案。任何寫入操作屬 **High**（DEC-081 第 9 點：Sheet 寫入、Google OAuth、credential、權限模型、L3）且需客戶核准；新增控制項須先出線框（DEC-003 ①）。⛔ **不刪舊 Sheet CRUD**（DEC-081 第 8 點）：舊 CRUD 只有在 Old capability → New coverage → regression → customer verification → removal Decision Gate 之後才可移除。

1. **解析統一**：以 `portfolio_manager.parse_sheet_id` 的語意為準（拒絕發布連結），外層再套 `oauth_state._sanitize_sheet_id`；抽到一處（L0 `shared/` 或 L1 `oauth_state` 旁），側欄 A 與 binder B 都改呼叫它。順帶修掉 `/d/e/` 被解析成 `e` 的問題（屬內部自修，但仍需獨立 QA）。
2. **綁定寫入只有一個入口**：`portfolio_binder.apply_active_sheet`，側欄 A 改呼叫它。⚠️ A 多做了一步 `_sb_sync_silent()`（`app.py:386`），要併進契約或由 caller 保留，避免靜默重登行為退化。
3. **綁定 UI 不寫第 5 份**：👤 我的頁重用 `render_holdings_binder`／`render_drive_picker`。🛡️ 持股的 dead-end 改成「到 👤 我的」（頁內入口或導覽）。
4. **組合／清單 CRUD**：若要進新 UI，先抽 L3 `portfolio_crud_service`（list／load／save／delete＋兩段式確認狀態機＋`portfolio_manager._classify_sheet_api_error` 錯誤分類），ETF 組合與觀察清單共用；新 view 只呼叫 L3。
5. **權限與風險分級**：

| 等級 | 操作 | 處置 |
|---|---|---|
| 🔴 High（寫進使用者的 Google 帳號） | `create_new_sheet`、`save_portfolio`、`save_stock_watchlist`、`delete_portfolio`、`delete_stock_watchlist`、`add_to_stock_watchlist`、`freeze_current_picks`、`rename_sheet` | 需客戶核准；🛡️ 目前以黑名單釘死唯讀（~~`page_hold.py:25-31`~~ 重驗 @15cd8fff 更正：該行號已不是此宣稱所在；現為 `page_hold.py` 檔頭 docstring「測試釘死」段，指向 `tests/test_p04_hold_view.py::TestReadOnly`；本輪未跑該測試，屬轉述），接這些等於改變唯讀政策。刪除與凍結快照屬「無法重建」（`CLAUDE.md` §-1.5.F 判定 3(5)），⛔ 不得逕行 |
| 🟡 只改綁定設定（session＋`?sheet=`） | 貼 URL、選一本 Sheet | 線框核准後可施工 |
| 🟢 只讀 | 列 Sheets、列組合、`clear_read_cache` | 線框核准後可施工 |

---

## 8. Dead-end 清單（FACT；新版模式下 📁 組合管理頁籤不畫，`app.py:620`；`page_hold.py:1684-1688` 註解也自承）

### 8.1 調查組列出的 9 處（新頁叫使用者去 📁 組合管理，或去一個沒有選單的地方）

| # | 位置 | 內容（節錄） | 類型 |
|---|---|---|---|
| 1 | `page_hold.py:1690` | `SHEET_UNBOUND_WHERE`／`NOT_BOUND_WHERE`：「用 Google 登入後**選一本**持股 Sheet —— 現行入口在側欄…『Google Sheet ID 或完整 URL』」 | 半 dead-end：側欄只有貼上框，沒有清單可選；且貼上框只在「OAuth 已設定且已登入」時才出現（`app.py:356-357`） |
| 2 | `page_hold.py:1717` | `EMPTY_SHEET_WHERE`：「到既有的 📁 組合管理分頁新增一本組合並填入持股列」 | dead-end |
| 3 | `page_hold.py:1867` | `IF_LOTS_AVG_MISSING_WHERE`：「若是缺張數／均價，到既有的 📁 組合管理分頁補齊」 | dead-end |
| 4 | `page_hold.py:2683` | 卡片 `where=`：到 📁 組合管理補張數與均價 | dead-end |
| 5 | `page_hold.py:2788` | 卡片 `where=`：到 📁 組合管理確認個股均價 | dead-end |
| 6 | `page_hold.py:3195` | 到 📁 組合管理補張數／均價 | dead-end |
| 7 | `page_hold.py:3305` | `_where`：到 📁 組合管理確認代號與張數 | dead-end |
| 8 | `page_hold.py:3407` | 卡片 `where=`：到 📁 組合管理補張數與均價 | dead-end |
| 9 | `page_hold.py:3738` | 卡片 `where=`：到 📁 組合管理補張數 | dead-end |
| — | `page_today.py:1051` | 同 #1 的「選一本持股 Sheet → 側欄…」 | 半 dead-end |

批 Z54 只把 #1「未綁」那一句改指到側欄，#2～#9 沒改（FACT：grep `📁 組合管理`）。

### 8.2 撰寫組補掃到的其他命中（**未判讀**，待查是否真的畫到畫面）

撰寫組在 `6dad38cb` 對 `page_hold.py` grep `📁 組合管理`，共 29 行命中，除註解與 §8.1 外還有：`:568`（`READONLY_WHERE`）、`:4274`、`:4297`（「現行入口」＝既有的 📁 組合管理分頁）、`:4399`（`_V2_FILL_LOTS`）、`:4443`、`:4477-4481`、`:4598`、`:4662`、`:4704`、`:4710`、`:5202`（caption「唯讀 —— 要新增／修改／刪除請到既有的 📁 組合管理分頁」）。
- INFERENCE：部分可能是 v2 版面的節錄常數或守衛用的字串，不一定會畫出來；**撰寫組沒有逐一判讀**。
- ⚠️ 這表示 §8.1 的「9 處」**不是完整清單**。修 dead-end 前要由獨立一組重新窮舉（`CLAUDE.md` §-2 規則 4）。

---

## 9. 其他重複

| 項目 | 位置 | 說明 |
|---|---|---|
| 測試連線 | `app.py:446`（側欄，L6 inline HTTP、`verify=False`）vs `api_diagnostic.py:153` | 功能重疊 |
| 大盤更新 form | `tab_today.py:620-628`（舊）vs `page_today.py:3901`（新，大盤頁共用） | INFERENCE：`tab_today` 可能已沒有 caller，未驗 |
| Sheet 綁定寫入 | `app.py:381-387` vs `portfolio_binder::apply_active_sheet` | §7.1 |
| URL 解析 | 4 份 | §7.2 |
| 組合 vs 觀察清單 CRUD | `portfolio_manager.py:166-226` vs `:229-298` | 近乎逐字重複 |

新舊 UI 都沒有 `file_uploader`。

---

## 10. 限制與下一步

- **限制**（`CLAUDE.md` §-2 規則 6）：
  1. 179 個呼叫點的清單與頁面歸屬由單一調查組產出；本檔由單一撰寫組整理；**沒有第二組驗過**。
  2. 「狀態」欄只看有沒有入口，沒有在 Streamlit 實測行為。
  3. §8 dead-end 清單已知不完整（§8.2）。
  4. 大盤頁（§4.1）是讀碼結果，沒有實機操作。
- **下一步**：
  1. 由獨立一組複驗本檔（`UIX-INTERACTION-COVERAGE`）；複驗前本檔只能當待驗事項。
  2. 客戶驗收 📊 大盤頁時，§4.1 是互動完整性的檢查清單。
  3. 其他頁（👤／🛡️／🎯／🩺／⚡）依客戶指派各自出線框；本檔的「待接」列是線框的輸入，**不是**動工授權（`CLAUDE.md` §-1）。

---

## 11. 👤 我的 P1 覆蓋更新（PR #927，~~**待合併**~~ **已合併 `ab705fbf`**（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；append-only；上文 §0～§10 除 §1 標題外一字未改）

> 2026-10-25 新增（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。基準：分支 `claude/determined-euler-32xqjn` @ `4e8c0876`（撰寫組讀 `git log 55601f42..HEAD`＋diff＋檔案，單組）。「新 UI 位置」只寫**新版模式**；舊 UI 全部照留（DEC-083 E 段：⛔ 不刪舊 UI，刪除須走 Removal Gate）。狀態欄「已接」＝讀碼可見入口，**沒有在 Streamlit 實機操作過**。

| 控制項（§1／§2 原列） | 新 UI 位置（PR #927） | backend | 狀態 | 備註 |
|---|---|---|---|---|
| 🔐 用 Google 登入 | 👤 我的卡①「🔐 用 Google 登入」 | L1 `oauth_state.build_login_url`（state 夾帶本 session 綁定，不夾帶 secrets 預設） | 已接（PR #927） | 側欄、`render_login_cta` 仍各自組網址（`BACKLOG` `LOGIN-URL-SSOT`） |
| 🚪 登出 | 👤 我的卡①「🚪 登出」；側欄「🚪 登出」 | L1 `oauth_state.logout_google_session`（兩處同一支） | 已接（PR #927） | ~~登出邏輯寫在 L6 inline，沒有 service~~ 已收斂為 L1 共用一支（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；舊 UI binder 的 Drive 清單未清（`SHEET-LOGOUT-DRIVE-LIST`） |
| 重新登入（逾時） | 👤 我的卡①「🔐 重新登入」 | 同登入 | 已接（PR #927） | |
| 登入狀態顯示 | 👤 我的卡①（email 遮罩） | L3 `me_account_service.get_account` | 已接（PR #927） | |
| Sheet 連線狀態 | 👤 我的卡②（Sheet 名稱＋ID 末 6 碼；兩本不同／只有部署預設各有說法） | L3 `portfolio_binding_service.get_active_sheet`＋L1 `read_sheet_title`（fail loud） | 已接（PR #927） | 🔗 狀態列新版模式仍看不到（未動） |
| Sheet URL／ID 輸入＋URL 自動解析 | 👤 我的卡②「🔄 切換 Sheet」方法一（`p07me_paste_sheet`） | L0 `shared/sheet_id` 單一 parser＋L1 唯一寫入契約（#926） | 已接（PR #927） | ~~側欄貼 ID 框照留；新版模式不預填、只露末 6 碼~~ 側欄貼 ID 框照留；新版模式下**框本身是空的**（不預填、也留不住完整 ID；`075e8da7` 起以 Session State API 指定為空字串），末 6 碼只出現在框下方的「✅ Sheet ID」caption（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） |
| 📂 從 Drive 列出可用 Sheet（＋資料夾） | 👤 我的卡②「🔄 切換 Sheet」方法二 | L1 既有 `list_user_folders`／`list_user_sheets`（經 L3） | ~~待接~~ 已接（PR #927）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） | 清單只有一本也不自動綁（DEC-083 C 段） |
| 選擇／切換 Sheet（明確「✅ 使用這本」） | 👤 我的卡②（Drive 選一本後按；部署預設、兩本不同時各有明確按鈕） | L1 `apply_sheet_binding` | ~~待接~~ 已接（PR #927）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） | |
| 🔄 重新讀取 | 👤 我的卡②「🔄 重新讀取」（只在 active Sheet 成立時出現） | L3 `reload_my_sheet_reads`（只本人×active Sheet，⛔ 不 `.clear()`） | ~~待接~~ 已接（PR #927）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） | 💼 本頁沒有重新讀取鈕；舊 UI 的全域清除照留（`SHEET-GLOBAL-CLEARS`） |
| active 組合／觀察清單（新能力，§1／§2 原無此列） | 👤 我的卡③ 兩個選擇器＋「取消選定」；觀察清單另有「（不使用觀察清單）」 | L1 `oauth_state.set_active_selection`（只寫 session）；L3 `holdings_service`／`sector_flow_service` 讀 | 已接（PR #927） | 只活在 session（`NAV-PERSIST`）；沒選定 → 💼／🔍 不讀任何一本 |
| 🛡️ 往「我的」設定的入口 | 💼／🔍／🚦 指路句改指「👤 我的 › …」 | `ia_nav.where_to_find` | 部分（只有文字） | 仍沒有可點的跳頁按鈕 |
| 🛡️ 缺 Sheet 時就地綁定 | 無（💼 刻意不放）；指路到 👤 我的 | — | 指路（不是 dead-end） | |
| 🛡️ 重新載入持股 | 經 👤 我的「🔄 重新讀取」 | 同上 | 部分 | 💼 本頁無按鈕 |
| 🆕 建立新投組 Sheet | 無；👤 我的只放客戶 D 段指路句 | — | **只在舊 UI**（`ME-P2`，未授權） | |
| 組合／觀察清單管理（載入／儲存／刪除）、持股列 CRUD、➕ 加入觀察清單 | 無；指路句「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」 | — | **只在舊 UI**（`ME-P2`，未授權） | 依草稿 §5 仍是半 dead-end，直到 P2 |
| 🔍 測試連線 | 側欄（未動） | — | 不在 P1 範圍 | |

- ⛔ **舊 UI 不得因本表而刪**（DEC-083 E 段）：舊側欄 🔐 Google 帳號、📁 組合管理、`portfolio_binder`、🔗 我的組合狀態列、Sheet CRUD 全部照留。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組產出，**沒有第二組驗過**；未在 Streamlit 實機操作。

---

## 12. Stage A 深度盤點（🎯 標的／🛡️ 持股／⚡ 行動；盤點範圍標籤，基準：程式碼＝main @ `15cd8fff`）

> 2026-10-26 新增（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。append-only：上文 §0～§11 原文**一字未改**；只在 §2、§3、§6 標題下各加一行指向本節的註記，並對 §2、§6 內已被推翻的少數狀態字樣加刪除線。
> 對應裁示：`docs/DECISIONS.md` **DEC-082**（所有下一頁先草稿、後施工 Stage A→B→C→D；本節＝其 **Stage A 唯讀盤點**；**Stage C 才是正式客戶 Gate**，Stage B 草稿完成後停手等裁示）、**DEC-085／`PROJECT_RULES.md` §19**（長期 UI 責任方向與 Old→New Coverage 規則；本節的定位與圖例依其 §19.2／§19.6，見下方「本節定位」）、DEC-081 第 7 點（互動控制完整性）、DEC-083（👤 我的 Stage C，Sheet SSOT）。對應待辦：`docs/BACKLOG.md` `NEWUI-STAGE-A-GAPS`（本批新增）、`UIX-INTERACTION-COVERAGE`、`UIX-FIND-INPUTS`、`UIX-HOLD-DEADEND`、`UIX-ACTION-PAGE`。
> ⛔ **本節不是設計、不是授權**：不寫任何 UI code；不新增或改定義任何投資語意、公式、門檻；任何新控制項、版面、分頁動線異動都須先出文字線框送客戶（DEC-003 ①、DEC-082 Stage B/C）。§12.5 的 S1～S28 是「Stage B 前置候選問題／decision-note」，**本輪不要求客戶逐題裁示**，Stage B 再收斂為少量 Decision Gates。（~~客戶尚未裁示 §12.5 之前，Stage B 不得開始~~：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；該句會被讀成 DEC-082 條文，實際不是。若本批在 Stage B 前停手，那是「**本輪工作安全停點／總管流程（非 DEC-082 條文）**」。）

### 12.0 方法與揭露

**範圍與基準**
- 基準：程式碼＝main @ `15cd8fff`（~~`4e6bf8ee`~~：原調查量測基準；4e6bf8ee→15cd8fff 僅 docs 變更，0 程式碼變更，已實測 `git diff --name-only 4e6bf8ee HEAD` 無非 `.md` 檔；量測日 2026-10-26）。下文凡寫「量測於 `4e6bf8ee`」者，程式碼層面等同 `15cd8fff`。**唯讀盤點**：各組沒有改 repo 任何檔、沒有跑會寫 Google／外部系統的東西。
- 範圍（**盤點範圍標籤，依現行 nav 暫代**；見下方「本節定位」）：🎯 標的（現行 nav：🔍 找標的、🔬 查一檔）＝新 UI `page_find`（🔍 找標的）＋`page_inspect`（🔬 查一檔），對照舊 UI 的選股網、個股、多檔個股比較、三階段濾網、型態目標價、ETF 單檔／多檔／smart、產業熱力圖、板塊資金潮汐；🛡️ 持股（現行 nav：💼 我的持股）＝新 UI `page_hold`（💼 我的持股），對照舊 UI 的存股戰情室、組合管理、🔗 狀態列、綁定器、ETF 組合；⚡ 行動（現行 nav：尚無對應頁；歸屬待 IA Decision Gate）＝新 UI **尚無此頁**，盤點舊 UI 中屬「現在需要採取什麼行動」的內容（出場訊號、235 燈、再平衡、葡萄串、AI 推播、作戰室等）。
- 起點：本檔 §2／§3／§6／§8／§9／§11；**核對、補深、修正，不整份重寫**。

**本節定位（DEC-085／`PROJECT_RULES.md` §19）**
1. **本節是事實盤點，不是設計。** 不決定頁面歸屬、不新增控制項、不改 nav。
2. 🎯／🛡️／⚡ 只是**盤點範圍標籤，依現行 nav 暫代**；它們**不是** §19.2 長期責任方向（📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股／👤 我的／🩺 資料中心）與現行 nav 或既有 view 的一對一對映，**對映屬後續 IA Decision Gate，本盤點不決定**。下文凡寫「歸屬 🎯／🛡️／⚡」，一律讀作「目前只掛在現行 nav 的…；歸屬待 IA Decision Gate」，不得據程式碼目前掛在哪頁斷言歸屬已可判定。
3. **DEC-082 更正**：Stage A→B→C→D 中 **Stage C 才是正式客戶 Gate**；Stage B 草稿完成後停手等裁示。本節不得被引用為「Stage B 須先過客戶裁示」。
4. **S1～S28 定位更正**：§12.5 的 S 項＝**Stage B 前置候選問題／decision-note**；Stage B 再收斂為少量 Decision Gates；本輪不要求客戶逐題裁示。

**Coverage 狀態圖例（DEC-085 §19.6，只有這四種，一字不改）**

| 狀態 | 意義 |
|---|---|
| `✅ 已覆蓋` | 新 UI 已有對應入口／能力（只比較入口／能力是否存在，未驗行為等價） |
| `🟡 部分覆蓋` | 新 UI 有部分能力，缺的部分須列明 |
| `⬜ 未覆蓋` | 新 UI 尚無對應 |
| `🚫 明確不再需要／不應搬入` | **AI 盤點建議**不搬／不應搬入；**最終認定屬客戶**；**不構成任何舊 UI 刪除授權**（未完成替代前不得因新 UI 上線就直接刪舊 UI，§19.6、DEC-019／020／081／083）。「不是 UI 能力」**不是** 🚫 的容許理由；只憑單組 grep 判「死碼／過時」者不得直接標 🚫，須標 INFERENCE、重驗後仍成立才保留並註明驗證方式 |

- **不得有第五種正式狀態。** 需要客戶表態者，只能放在狀態格**以外**的 decision-note，固定格式：`【decision-note：待客戶裁示 S#】`；**不得出現在狀態格內**。
- 混合狀態不得寫在同一格，須拆成兩列或兩個項目。
- 本節以下各表若仍有舊式狀態寫法，由各小節（c1～c6）依此圖例更正。

**流程：三份各一組調查＋一組獨立複驗（各一輪）**

| 頁 | 調查（單組） | 獨立複驗（另一組，方法與原組不同） | 確認 | 更正 | 無法確認 |
|---|---|---|---|---|---|
| 🎯 標的 | 組 A | 複驗 A（從新 UI 常數／widget 往回查；關鍵字計數反證「新 UI 沒有」） | 38 | 9 | 5 |
| 🛡️ 持股 | 組 B | 複驗 B（直接讀被引用函式本體；中文功能關鍵字反向搜；對照 `docs/wireframes/stock_ia_v1.html`、DEC-017／DEC-083） | 38 | 9 | 5 |
| ⚡ 行動 | 組 C | 複驗 C（以「呼叫者反查」重做全稱句；直接讀 DEC 原文、`.github/workflows/*`、`app.py` 路由） | 39 | 16 | 3 |

- **本節的處理方式**：複驗判為「更正」者，本節**已套用更正**，並在該處標「（複驗更正）」；複驗判為「無法確認」者，**保留原敘述並標「（複驗：無法確認）」**，不升格為事實；複驗與原檔衝突而落盤組無法判定者，兩者並陳並標「待查」。
- 本節由落盤組（文件組）**彙整**三份調查與三份複驗而成；落盤組**沒有重新讀碼驗證**其中任何一條 FACT。引用以 `檔案::符號` 為主，行號只當輔助，一律「量測於 `4e6bf8ee`」。

**必須說清楚的限制（`CLAUDE.md` §-2 規則 6）**
1. ⚠️ **複驗只抽驗部分列，其餘未逐列驗**。抽驗概況：🎯 ✅抽 9、🚫 全 2、⬜抽 15、🟡抽 7；🛡️ ✅抽 11 列以上、🚫 全部、⬜抽 12 以上、🟡抽 4；⚡ ✅全 9、🚫全 4、⬜抽 12、🟡全 2。**沒被抽到的列，仍是「單組觀察，未窮舉」**，不得當成「已雙重驗證」。
2. ⚠️ **沒有在 Streamlit 實機操作；沒有跑任何測試**（含 `tests/test_c3_layering_guard.py`、`tests/test_p04_hold_view.py`）。所有「按下去會怎樣」都是讀碼推論；Coverage 只比較「入口／能力是否存在」，**沒有驗證行為與舊 UI 等價**。檔頭對測試的宣稱（例如 `page_hold` 的 AST 黑名單釘死唯讀）一律照轉述。
3. **FACT／INFERENCE 標示沿用**：🎯、⚡ 用 FACT／INFERENCE；🛡️ 用 [F]／[I]（意思相同）。沒標的敘述句，依各調查檔原慣例為 FACT（讀碼或 grep 可驗證）。
4. 「新 UI 沒有 X」這類全稱句，成立範圍僅限各組列出的搜尋方法（關鍵字／符號 grep，🎯 限 `src/ui/views/page_find.py`、`page_inspect.py`；⚡ 限 `src/ui/views/page_*.py`；🛡️ 限 `app.py src shared scripts` 排除 tests）。若新 UI 用不含該關鍵字的別名實作，仍可能漏。
5. **交叉引用對照**：各小節內若寫「見 §9／§10／§11…」，指**調查檔自己的章節編號**，對照如下；寫「矩陣 §N」者仍指本檔既有章節。

| 調查檔章節 | 本節位置 |
|---|---|
| A：§9 重複／§10 高風險／「需客戶裁示」／「與既有矩陣不符處」／「本組盲點」 | §12.1.9／§12.1.10／§12.5／§12.6／§12.0 |
| B：§9 重複／§10 高風險／§11 規格缺口／§12 紀律發現／§13 不符／§14 盲點 | §12.2.9／§12.2.10／§12.5／§12.7／§12.6／§12.0 |
| C：§9 重複／§10 高風險／§11 規格缺口（G1～G13）／§12 不符／§13 盲點 | §12.3.9／§12.3.10／§12.5（G 編號對照見 §12.5.3）／§12.6／§12.0 |

**三組各自的盲點（濃縮；完整版見各調查檔，已併入本節）**
- 🎯：只讀 `section_*` 的 widget 與頂層呼叫，未逐段讀內部邏輯；ETF 單檔診斷只讀到約 520 行與標題清單；`tab_ai_chat`、`tab_edu`、`render_data_coverage` 未盤；名稱反查「不存在」的 grep 只涵蓋 `src shared` 的 `*.py`；`get_ranked_picks(top_n=…)` 前後行為差異見複驗定論（§12.1.6 列 A-04）。
- 🛡️：`page_hold.py`（5462 行）以符號與卡片 id 盤點，未逐行讀；未逐一判讀本檔 §8.2 的 20 餘處 `📁 組合管理` 命中；未讀 `dividend_station_service` 內部判燈規則、`etf_tab_portfolio.py` 全文、`gsheet_portfolio.py` 內部；`TTL_15MIN` 實際值、DIVERGED 路徑實機畫面、登入逾時→重新整理後的實機狀態皆未驗。
- ⚡：沒有逐行讀完 `page_hold`、`tab_macro`、`tab_stock`、`tab_stock_picker`；`macro_classroom`、`tab_edu`、`tab_sector_flow`、`yield_screener`、`tab_macro` 其餘 section 內是否另有行動語句**未掃**，所以「只有 C-31 一項漏列」**不可成立**，僅為複驗找到的漏項；DEC-040、DEC-027 全文、`section_chips`／`section_mid` 部分結論句行號未驗；各燈的資料新鮮度／PIT 未驗。
- **三組共同**：未檢查 `docs/wireframes/stock_ia_v1.html` 對各頁的核可範圍是否全面（複驗 B 只讀了 ③⑤⑥⑦ 與問答區），故任何「這個元件須先出草稿」的說法，都須對照該線框再判斷（見 §12.2 列 H-09b）。

**本輪（Stage A v2，基準 `15cd8fff`）code 宣稱重驗揭露**
- **已重驗成立（對 worktree，2026-10-26）**：4e6bf8ee→15cd8fff 無程式碼變更（`git diff --name-only`）；`src/ui/views/` 檔案組成（`page_find/hold/inspect/market/me/today/why`、`risk_cap_gate`、`_ui_kit`、`__init__`）；`page_hold.py` 共 5462 行；`tests/test_c3_layering_guard.py`、`tests/test_p04_hold_view.py`、`docs/wireframes/stock_ia_v1.html` 存在；`shared/ia_nav.py::CONTENT_EDIT_OLD_UI_WHERE`（現文「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」）；`page_hold` 的 `ACTION_RUN_WARROOM_LABEL`（🚀 跑存股戰情室）、`AI_SUMMARY_LABEL`（⚡ 生成 AI 總結）。
- **已更正（行號漂移）**：矩陣 §2 組合／觀察清單管理列的 `page_hold.py:1798`、`page_hold.py:25-31` 已不是原宣稱所在，改以符號／檔頭 docstring 為準（見該列）。
- **降級為 INFERENCE／未複驗**：「推送只在 cron、兩邊都不推送」；各調查組「抽驗概況」與 38／9／5 等計數為彙整轉述；上方「三組各自的盲點」所列未讀範圍；§12.0 所有「沒有在 Streamlit 實機操作、沒有跑測試」仍成立。其餘 §1～§11 與 §12.1～§12.8 的 code 宣稱由各 chunk 負責人重驗，揭露見各小節。

### 12.1 🎯 標的（盤點範圍標籤，依現行 nav 暫代；調查組 A＋獨立複驗 A；更正已套用）

> 基準：程式碼＝main @ `15cd8fff`（4e6bf8ee→15cd8fff 僅 docs 變更，0 程式碼變更；本 chunk 重驗時已再跑 `git diff --name-only 4e6bf8ee 15cd8fff`＝4 檔、皆 docs／.md）。
> **盤點範圍標籤說明（DEC-085／PROJECT_RULES §19.2）**：本節「🎯 標的」是**盤點範圍標籤，依現行 nav 暫代**（現行 nav：🔍 找標的／🔬 查一檔）。🎯 標的是長期「責任方向」，**不等於**現行 nav 名稱或既有 view 一對一對映；本節凡寫到 📊 大盤／⚡ 行動／🛡️ 持股／👤 我的／🩺 資料中心，同樣是責任名並附「（現行 nav：…）」，**目前只掛在…；歸屬待 IA Decision Gate**，本盤點不決定。
> 範圍：新 UI `src/ui/views/page_find.py`（🔍 找標的）＋`page_inspect.py`（🔬 查一檔）；舊 UI 見下表。行號：重驗 @15cd8fff（能改 `file::symbol` 者已改；仍保留行號者為 15cd8fff 實測值，原標「量測於 `4e6bf8ee`」的舊行號不再沿用）。ID 前綴：S＝選股網、T＝個股、G＝多檔個股比較、E＝ETF、M＝板塊；Coverage 表的列號為 **A-nn**（調查檔原用 `#nn`，本節加前綴避免與他頁混淆）。

#### 12.1.0 一頁結論（複驗後）

1. **新 UI 現況**：選股網（篩選→排名→CSV）與板塊資金潮汐已完整且狀態誠實地接上；查一檔只接了「判型＋三張判決卡＋獲利能力三格」（重驗 @15cd8fff：`page_inspect.py` 有 `inspect.kind`／`inspect.stock.health`／`inspect.stock.valuation`／`inspect.stock.chips` 卡 key；獲利能力三格未逐格重讀，沿用 A-45 的複驗結論）。個股明細七段、ETF 明細七段、K 線、AI、新聞、集保大戶、型態目標價**都沒有**，卡上寫明「未接線」並指回舊分頁（`DETAIL_WHERE`）。

2. **寫入 Google／不可重建歷史的三個能力全在舊 UI**：➕ 加入觀察清單（寫 Sheet）、🧊 凍結前 20 名（寫 `forward_test_picks`）、📊 對帳（讀凍結列＋抓現價）。新 UI **沒有入口也沒有指路句**（靜默缺席）。重驗 @15cd8fff：`page_find.py`／`page_inspect.py` 內「對帳」0 次；「凍結」共 8 次（`page_find.py` 8、`page_inspect.py` 0），其中 7 次為「盤後凍結快取」語意，另 1 次（~~皆為「盤後凍結快取」語意~~ 更正：`page_find.py` 檔頭 docstring 那一處）只是提到 `get_ranked_picks` 是「畫面／每月凍結／MCP／推播」的同源入口，**並非凍結入口**；兩頁對 `add_picks_to_watchlist`／`add_to_stock_watchlist`／`forward_test` 的 grep 皆 0 命中；唯一碰 watchlist 的是 `get_sector_flow_view(use_active_selection=True)` 的**唯讀**持股標示。

3. **會動但沒作用的控制項**：🔬 查一檔表單的 6 個 MA 勾選沒有任何**計算**消費者（K 線未接線，頁面自己有揭露）；複驗更正：它們的值會**回顯**在判型結果卡 fact「期間 / 均線」（`page_inspect.py` 約 1901–1903 行，重驗 @15cd8fff）。「期間」只決定籌碼卡載入的日線長度（`get_chips_readout(days=…)`）。這違反 DEC-081 第 7 點精神（可操作≠有效果）。

4. **名稱同名不同義**：舊個股頁「健康評分」＝技術面六因子（`calc_health_score`）；新查一檔「健康度」＝財報體檢綜合分 0–100＋等第（`analyze_financial_health`）。複驗確認兩者路徑不同、**不是同一把尺**；💼 持股頁另有第三套「序數燈號」。Stage B 不得合併或改名 → §12.5 S13。

5. **既有矩陣有需更正處**：見 §12.6（行號全面過期；三階段濾網在 production 全不可達——此點為**複驗對調查組原結論的更正**；ETF smart 只掛在單檔診斷；`render_smart_ticker_input` 在 production 零 caller（僅測試釘住其存在，見 A-75）；型態目標價等多項漏列）。

#### 12.1.1 舊 UI 有哪些功能（項目 1；FACT；重驗 @15cd8fff，~~量測於 `4e6bf8ee`~~ 基準更新：4e6bf8ee→15cd8fff 0 程式碼變更）

入口：`app.py` 舊頁籤（側欄 radio 選「不使用」時才畫）：`🔬 選股` 群組（`with tab_stocks`）→ 子頁 `🔬 個股`／`📊 多檔個股比較`／`🔭 選股網`；`🏦 ETF` 群組 → `🔍 單檔診斷`／`📊 多檔比較`；`🌍 市場環境` 群組 → `🗺️ 產業熱力圖`／`🌊 板塊資金潮汐`。

**1.1 🔭 選股網（`app.py` 的 `with tab_screener`，起於 810 行、止於下一個頂層 `with tab_etf_main`〔1105 行〕之前；重驗 @15cd8fff）**
| ID | 功能 |
|---|---|
| S1 | ① 基本面優選說明＋初篩明細面板（`tab_stock_picker.py::render_prescreen_panel`：四項全過檔數、民國年季、三率三升 YoY 說明、快照涵蓋率警示 `describe_snapshot_coverage`、「顯示全市場」checkbox、逐檔數值表） |
| S2 | ② 勾條件 multiselect（`SCREEN_ANGLE_LABELS` 5 因子：估值／EPS／缺貨動能／抗跌 RS／跨季轉強；**預設＝第一項（估值）**） |
| S3 | ③ 🎯 開始選股（按下才自動掃缺貨／RS／跨季趨勢，結果存 session；再 `get_ranked_picks(top_n=300, regime=…)`） |
| S4 | 結果總覽卡＋dataframe（固定顯示 `head(50)`）＋「本次因子」命中摘要（`summarize_factor_hits`） |
| S5 | 空頭濾網（`allocation_service.get_macro_regime` → `regime`，僅畫面傳；cron／MCP／推播傳 None） |
| S6 | 💾 下載選股 CSV（`head(50)`） |
| S7 | ➕ 加入觀察清單（勾選 multiselect＋選清單／新建＋`add_picks_to_watchlist`） |
| S8 | 🧊 凍結前 20 名（`freeze_current_picks` → Google Sheet `forward_test_picks`） |
| S9 | 📊 前進式驗證對帳（`reconcile_all`，expander，讀凍結列＋抓現價＋0050） |
| S10 | 🌍 掃全台股跨季趨勢排行（`get_cross_quarter_trends`，前 100）＋ CSV |
| S11 | 🧬 AI 總結本頁（`tab_ai_chat.render_tab_summary('選股網', …)`） |

**1.2 🔬 個股（`tab_stock.py::render_tab_stock`，檔案共 1917 行，重驗 @15cd8fff）**
| ID | 功能 |
|---|---|
| T1 | 個股代碼（預設 `2330`）＋ 天數 slider(60–400 step 10) ＋ 一般K線(還原切換) ＋ 🔍 載入完整分析（並行抓價／股利／財報／月營收／季報／新聞） |
| T2 | 6 個 MA 勾選（MA5/20/60/100/120/240） |
| T3 | 🎯 型態目標價 expander（`pattern_targets_ui.py`：ZigZag 靈敏度 slider＋手動微調 number_input×N＋型態 selectbox；隨「載入完整分析」一併算） |
| T4 | 資料來源 chip／降級警示／過期值警示／🔄 強制重抓（`st.cache_data.clear()`＋pop session） |
| T5 | 個股↔總經 regime 聯動 banner（`macro_stock_link.render_macro_stock_backdrop`，讀 session `mkt_info`／`jingqi_info`） |
| T6 | 個股↔ETF 組合／個股組合持倉聯動 banner（`portfolio_linkage.render_stock_portfolio_membership`，讀 session `etf_portfolio_rows`／`t3_data`） |
| T7 | 即時價格＋MA20/60/120 趨勢總覽＋趨勢燈號 |
| T8 | 🧭 一眼判讀（`summarize_stock_verdict`，4 桶綜合） |
| T9 | 目錄 TOC＋6 桶 section header（`compute_stock_section_levels`） |
| T10 | 停利停損建議＋近期支撐壓力／操作雷達／多因子評分 |
| T11 | 心理檢查（3 checkbox）＋勝利方程式＋禁止操作（`section_psy_checklist`） |
| T12 | 什麼時候買？什麼時候賣？（`section_when_buy_sell`：總資金 number_input、AI 新聞情緒判斷） |
| T13 | 龍頭預警（`section_dragon_alert`） |
| T14 | 技術健康度評分六因子（`section_health_score`／`calc_health_score`） |
| T15 | VCP＋布林（`section_vcp_bollinger`） |
| T16 | 籌碼定位 20 日（`section_chips_20d`，含 `inst_sanity` 異常值徽章） |
| T17 | K 線技術圖（`section_kline_chart`） |
| T18 | 即時文字建議（`section_op_recommendation`） |
| T19 | 357 殖利率評價＋3 河流圖＋PE 區間 preset selectbox（`section_357_valuation`） |
| T20 | 財報領先指標（合約負債／資本支出，`section_financial_leading`） |
| T21 | 月營收＋季毛利率（`section_revenue`） |
| T22 | 策略 1 結論＋財報趨勢分數 65/35（`section_strategy_conclusion`；會寫本機快照 `data_cache/fin_health_snapshots`，非 Google） |
| T23 | D2 基本面先行（`section_d2_leading`） |
| T24 | 🔬 AI 財報體檢（`tab_stock.py` 的「🔬 AI 財報體檢（策略2）」expander，起於 1016 行、按鈕 key `_fh_btn_{sid2}`〔重驗〕；生死／五力／DNA／存活／經營／獲利 5 大／財務結構／短期償債／綜合避雷等模組清單為原組轉述，**INFERENCE／未複驗**；按鈕觸發 Gemini） |
| T25 | 統一判決（`assess_unified`＋`render_unified_verdict_html`） |
| T26 | 💠 集保大戶雷達（`chip_radar.py`，爬 norway.twsthr.info） |
| T27 | 近期相關新聞（Google News RSS） |
| T28 | 🤖 AI 首席顧問戰略評估報告／🗑️ 清除報告 |

**1.3 📊 多檔個股比較（`tab_stock_grp.py`，檔案共 571 行，重驗 @15cd8fff）**
| ID | 功能 |
|---|---|
| G1 | 多檔代碼 text_area（≤10 檔；**預設寫死 10 檔** `'2330 2454 2317 …'`）＋ 🚀 批次分析 ＋ 🩺 組合體檢 |
| G2 | ① 市場狀態快覽（`section_market_status`，讀 session `warroom_summary`／`cl_data`） |
| G3 | 🩺 組合體檢 vs 基準（個股→^TWII、ETF→0050 落後判定，`watchlist_health_service`） |
| G4 | 組合排行總表＋多因子維度拆解＋基本面明細＋逐檔技術明細（`section_portfolio_summary`；批次抓取結果存本機快取 `_save_cache('t3v2')`） |
| G5 | 🔎 型態線圖下鑽 selectbox＋手動微調關鍵點 |
| G6 | 批次財報體檢（DNA expander，`section_financial_health`） |
| G7 | 財報趨勢×轉機（月營收權重 slider 0.4–0.9，`_render_fin_trend_section`） |
| G8 | 三階段濾網（`tab_stock_picker.render_tab_stock_picker`，由 `_render_stage_picker_section` 以 `auto_run=True`＋`source_label='個股組合輸入'` 呼叫）。（複驗更正）：production 為批次分析後**自動串跑並自動生成 AI 報告**，multiselect／額外代碼／go／AI 按鈕四個 widget 全部不可達，**零可操作控制項** |
| G9 | 🤖 AI 投資組合綜合判讀（按鈕）／🤖 AI 掃利空（按鈕） |
| G10 | 🏭 產業集中度（等權假設）＋總經建議持股 vs 檔數 |
| G11 | 🎚️ 風險貢獻分解（data_editor 輸入張數＋🎚️ 算） |

**1.4 ETF（`src/ui/etf/*`）**
| ID | 功能 |
|---|---|
| E1 | 🔍 單檔診斷：ETF 代號（預設 `0050`）＋對照基準（留空自動偵測 `auto_detect_benchmark`）＋ 🔍 開始診斷（`etf_tab_single.py`） |
| E2 | 🚦 綜合研判 留／觀察／換（`build_etf_score_row`＋`recommend_etf_action`） |
| E3 | 基本指標：收盤／內扣費用率／Beta／AUM（含 PROXY 健診警示） |
| E4 | 策略一 以息養股避雷／配息健康度／策略二 7% 存股估值買賣點／策略三 VCP |
| E5 | 折溢價＋建議買賣時機 |
| E6 | BIAS 乖離率／長線 σ 量化買點／季線×趨勢聯合警示／存股三大訊號（破發檢測） |
| E7 | smart 三區塊（`etf_tab_smart.py`，由 `app.py` 以 `before_ai_hook` 掛在單檔診斷）：3-3-3 優質標的（含「啟用同儕排名」checkbox）／標準差買賣參考帶（窗口 selectbox 120/252/500）／🔗 計算分散度（按鈕，冷抓約 30 檔） |
| E8 | 🧠 AI 白話總結（按鈕） |
| E9 | 📊 多檔比較：最多 10 檔（預設 5 檔寫死）→ 7 維加權 5 星評等 PK 表（`etf_tab_grp_compare.py`＋`etf_grp_compare_service`） |

**1.5 板塊**
| ID | 功能 |
|---|---|
| M1 | 🗺️ 產業熱力圖（`etf_render.py::render_sector_heatmap`）：市場 selectbox（美股 GICS／台股）＋區間 selectbox＋🔄 刷新＋🗺️ 載入（opt-in gate）＋ treemap ＋漲跌排行表＋覆蓋率＋ 🤖 AI 白話總結 |
| M2 | 🌊 板塊資金潮汐（`tab_sector_flow.py`）：泡泡圖＋持股板塊 ⭐＋資料不足板塊＋過期警示 |

**複驗補列（原組漏列的舊 ETF 單檔能力，`etf_tab_single.py`：同儕排名約 825–828 行、近 5 年走勢約 855 行、`render_etf_holdings` 約 862 行；重驗 @15cd8fff，~~約 737 行起~~ 更正：該起點不是這三段的實際位置）**：E10 🏆 同儕排名（vs 類）｜E11 📈 近 5 年走勢圖｜E12 🧩 成分股持股明細（`render_etf_holdings(ticker, top_n=15)`）｜E13 PROXY_URL 缺席警示（`etf_tab_single.py` 約 121–138 行〔~~112–132~~ 更正：重驗實測〕：未設 PROXY_URL → 內扣費用率／折溢價／經理人／AUM 全 N/A 並說明原因；另約 558–570、596 行有「NAV 抓不到→折溢價無法計算」的 PROXY 說明）。另：`src/ui_v2/*`（`page_find`／`page_inspect`／`blocks`／`markup`）是新頁的樣式／密度登記層，非能力層，無缺口（重驗 @15cd8fff：`src/ui_v2/page_find.py`、`page_inspect.py` 無 streamlit import、無 widget；其餘檔未逐一讀，「非能力層」為檔頭自述＋檔名推論）。

#### 12.1.2 使用者目的（項目 2；INFERENCE，依功能命名與 docstring 推得）

- S1：確認「基本面四項全過」池子是哪些、多大、快照是否完整。S2–S6：從存活池依自選因子排出候選清單並匯出。S7：把選到的標的收進自己的觀察清單以便持續追蹤。S8：把「當下真實選股」凍結成日後可驗證的樣本（零 lookahead）。S9：驗證選股法是否贏 0050。S10：不限存活池，看全市場基本面改善榜。S11：AI 摘要。
- T1–T3：輸入一檔、看 K 線與均線、自動抓型態關鍵位。T4：知道資料有沒有降級、必要時重抓。T5–T6：把個股放進總經與自己持倉的脈絡。T7–T10、T12–T13、T18：判斷「現在貴不貴、趨勢、何時進出、停利停損」。T14–T17、T19–T23：技術／籌碼／估值／基本面細節。T24–T25：財報深度體檢與統一判決。T26–T27：籌碼大戶與新聞佐證。T28：AI 總結。
- G1–G11：同時比較多檔、找落後股、看組合排行與集中度、算風險貢獻、三階段篩選。
- E1–E9：ETF 單檔體檢與多檔 PK；E7 的三區塊是以息養股框架的補充。
- M1–M2：先看產業輪動與法人資金流，再選股。

#### 12.1.3 資料來源／service／資料層（項目 3；檔案::符號）

**新 UI（FACT；兩頁自述全走 L3、零 L1 import，由 `tests/test_c3_layering_guard.py` 管。重驗 @15cd8fff：兩頁以 grep 檢查，`from src.data` 的 import 陳述 0 筆，僅 docstring 提及；`src/ui/views/` 在該測試被歸為 L5）**
- `page_find.py`：L3 `services/fundamental_screener_service.py::{get_ranked_picks, get_fundamental_survivors, build_trend_map, SCREEN_ANGLE_LABELS}`、`valuation_service::get_pe_name_maps`、`shortage_screener_service::run_shortage_scan`、`rs_leader_service::run_rs_leader_scan`、`allocation_service::get_macro_regime`、`sector_flow_service::get_sector_flow_view(strict=True, use_active_selection=True)`、`sector_heatmap_service::get_sector_heatmap_view`；L4 `ui/render/sector_flow_render::build_sector_flow_figure`、`sector_heatmap_render::build_sector_treemap`；L5 純函式 `tab_stock_picker::summarize_factor_hits`；L0 `shared/{sector_heatmap, sector_flow_thresholds, fundamental_prescreen_thresholds, station_specs, ui_state, ia_nav}`（重驗：另有 `shared/{rs_screen_thresholds, secret_scrub, sheet_id}`、L3 `me_account_service`／`holdings_service`〔👤 我的 選定持股標示〕、L5 同層 `tab_today`／`page_today` 的共用常數，原清單未列）。
- `page_inspect.py`：L2 `compute/etf/asset_lag::{classify_asset_kind, pick_benchmark}`、`compute/strategy/v5_modules::calc_dividend_yield_357`；L3 `dividend_station_service::fetch_metrics`、`valuation_service::get_stock_dividends`、`stock_chips_service::get_chips_readout`、`stock_grp_service::get_financial_statements`＋`financial_health_engine::analyze_financial_health`；L0 `shared/{secret_scrub, station_specs, ui_state, financial_health_thresholds}`、`src/config/config::MA_*`。

**舊 UI（FACT）**
- 選股網：L3 同上（`get_ranked_picks` 等）＋ `watchlist_service::{add_picks_to_watchlist, get_watchlist_add_context}`（→ L1 `gsheet_portfolio::{add_to_stock_watchlist, list_stock_watchlists, _get_active_stock_sheet_id}`，讀 session 通道 `STOCK_PORTFOLIO_SHEET_KEY`）、`forward_test_service::{freeze_current_picks, reconcile_all, is_freeze_available}`（→ L1 `gsheet_portfolio::append_forward_test_picks`；cron 版 `freeze_current_picks_local` → `forward_test_store`／`data_cache/forward_test/picks.parquet`，git 追蹤）。**另直呼 L1**：`app.py` 的 `from src.ui.tabs.yield_screener import fetch_pe_name_maps`（EX-PASSTHRU-1 範圍內）。
- 個股：`app_stock_fetchers::{fetch_price_data, fetch_dividend_data, fetch_financials, fetch_revenue, fetch_quarterly, fetch_quarterly_extra}`（L1，經 `tab_stock.py` 直接 import）、`app_ai_service::gemini_call`（L3）、`compute/health::{compute_one_stock_trend, save_snapshot…}`、`_fetch_stock_news`、`chip_concentration_fetcher`（爬 norway.twsthr.info）。
- 個股組合：`stock_grp_service`、`watchlist_health_service`、`section_batch_fetcher`（`shared.app_cache::_save_cache`）、`compute/risk::risk_contribution`。
- ETF：`src/data/etf::{fetch_etf_price, fetch_etf_dividends, fetch_etf_info, fetch_etf_zh_name, get_etf_expense_ratio_safe…}`（L1，EX-PASSTHRU-1）、`compute/etf::*`、`etf_grp_compare_service`、`etf_scoring_service::ensure_etf_rf_injected`（FEDFUNDS）。
- 板塊：`etf_sector_service::get_sector_returns`（熱力圖）、`sector_flow_service`（資金潮汐；舊分頁讀 session `etf_portfolio_rows`／`stock_portfolio_sheet_id`，新頁改讀 👤 我的 選定）。

#### 12.1.4 是否涉及 Sheet／portfolio／watchlist／OAuth／AI 分析／外部 API（項目 4）

| 功能 | Sheet | portfolio | watchlist | OAuth | AI 分析 | 外部 API／爬蟲 |
|---|---|---|---|---|---|---|
| S1–S6（選股、CSV） | 否 | 否 | 否 | 否 | 否 | 是（FinMind／TWSE／TPEX／yfinance，經 L3） |
| **S7 加入觀察清單** | **是（寫）** | 否 | **是（寫）** | 是（需 session 綁定／token） | 否 | 否 |
| **S8 凍結前 20** | **是（寫 `forward_test_picks`）** | 否 | 否 | 是 | 否 | 是（抓進場價） |
| **S9 對帳** | 是（讀凍結列；可能合併本機 parquet） | 否 | 否 | 是 | 否 | 是（現價＋0050） |
| S10 跨季趨勢 | 否 | 否 | 否 | 否 | 否 | 否（讀本機季快照） |
| S11 / T28 / T24（按鈕）/ G9 / E8 / M1-AI | 否 | 否 | 否 | 否 | **是（Gemini）** | 是 |
| T1–T23、T25、T27 | 否 | 否 | 否 | 否 | 否（T12 內含 AI 新聞情緒判斷＝是） | 是（FinMind／yfinance／TWSE；T27＝Google News RSS） |
| T22 財報趨勢分數 | 否 | 否 | 否 | 否 | 否 | 是；**寫本機快照** `data_cache/fin_health_snapshots` |
| T26 集保大戶雷達 | 否 | 否 | 否 | 否 | 否 | **是（第三方網站爬蟲）** |
| T5／T6 聯動 banner | 否 | 讀 session 殘值（ETF 組合／個股組合） | 否 | 否 | 否 | 否 |
| G3／G10／G11 | 否（輸入來自畫面） | 否 | 否 | 否 | 否 | 是 |
| E1–E7、E9 | 否 | 否 | 否 | 否 | 否 | 是（yfinance／MoneyDJ／SITCA／TWSE，部分需 PROXY_URL） |
| M2 資金潮汐 | 舊：讀 session 的 Sheet ID 取觀察清單；新：讀 👤 我的 選定 | 是（持股標示） | 是（讀） | 是（需登入才有標示） | 否 | 否（讀 GitHub Actions 凍結的本地快取） |

其餘（FACT）：新 UI 兩頁**零 Google 寫入**；唯一碰 Sheet 的是 `get_sector_flow_view(use_active_selection=True)` 的**唯讀**持股標示。

#### 12.1.5 舊 UI 主要互動流程（項目 5）

- **選股網**：①（自動，唯讀）→ ② 勾因子 → ③ 按「🎯 開始選股」（spinner；缺貨／RS／跨季各自 try，失敗只 `print`）→ 看總覽卡＋表（前 50）→（可選）下載 CSV → 勾選標的＋選清單＋➕ 加入 → 🧊 凍結前 20（需 `is_freeze_available()`）→ 展開 📊 對帳 → 另一個 expander 🌍 跨季趨勢排行。
- **個股**：輸入代碼／天數／MA → 按「🔍 載入完整分析」（型態目標價隨之計算）→ 長頁面往下 9 大段 → 可按 🔄 強制重抓、🔬 生成 AI 財報體檢、🤖 生成 AI 首席顧問報告。
- **多檔個股比較**：貼代碼 → 「🚀 批次分析 ＋ 🩺 組合體檢」一鍵串跑（體檢→排行→型態→財報趨勢→三階段濾網→AI 組合判讀）。
- **ETF 單檔**：輸入代號＋基準 → 「🔍 開始診斷」→ 研判卡→指標→策略一/二/三→折溢價→BIAS 等→smart 三區塊→AI。
- **熱力圖**：選市場／區間 →（首次）🗺️ 載入 → 圖＋排行表＋覆蓋率 →（可選）AI。

新 UI 流程（FACT）：側欄「🆕 新版戰情室」radio 選 🔍 找標的／🔬 查一檔 → 頁內 `st.tabs` 兩葉 → 表單 submit 一次（widget 當下值與已套用值分家）→ 判決卡。

#### 12.1.6 新 UI 現況與 Old→New Interaction Coverage 表（項目 6；複驗更正已套用）

**Coverage 狀態（DEC-085 §19.6，只有四種，一字不改）**：`✅ 已覆蓋`｜`🟡 部分覆蓋`｜`⬜ 未覆蓋`｜`🚫 明確不再需要／不應搬入`。🚫＝AI 盤點**建議**不搬／不應搬入，**最終認定屬客戶**；**不構成任何舊 UI 刪除授權**（舊 UI Removal Gate 見 DEC-083 第 11 項）。「不是 UI 能力」不是 🚫 的理由。「待裁示」不得出現在狀態格；需要時以 `【decision-note：待客戶裁示 S#】` 獨立標示。
Dead-end：是＝新 UI 叫使用者去一個新版模式下去不了的地方；半＝指路到舊頁籤（需先切回舊版，且句子未說怎麼切）；否＝沒有指路（靜默缺席）；—＝不適用。欄位「資料來源」「風險／限制」中的 INFERENCE 保留原標示。
**重驗總註 @15cd8fff**：下表凡引 `file::symbol`、widget key、行號、grep 結果者，本輪已逐項對 worktree 重驗；個別更正處以刪除線＋（更正原因）標示；無法重驗者標「INFERENCE／未複驗」。

| # | 舊功能 | 舊入口 | 新 UI 現況 | 新入口候選（僅候選） | Coverage | Dead-end | 資料來源 | 風險／限制 |
|---|---|---|---|---|---|---|---|---|
| A-01 | S1 初篩明細面板（逐檔數值／顯示全市場／涵蓋率警示） | 🔭 選股網 `render_prescreen_panel` | 只有四項條件說明 caption（門檻讀 L0 SSOT）＋存活池檔數；**沒有逐檔表、沒有涵蓋率警示** | 🔍 找標的 葉1 下方折疊區 | 🟡 部分覆蓋 | 否 | `fundamental_screener_service::get_fundamental_prescreen`、`describe_snapshot_coverage` | 涵蓋率警示＝「慢公布是否已納入」的資料品質揭露，缺了會讓使用者以為池子完整（INFERENCE） |
| A-02 | S2 勾條件 5 因子 | 🔭 `screener_factors` | `page_find.py::_render_screen_form` multiselect（label 讀 L3 SSOT）；**預設改為「EPS」**（舊預設＝第一項「估值」） | — | ✅ 已覆蓋 | — | `SCREEN_ANGLE_LABELS` | 預設因子不同＝使用者無意識下名單不同；見 §9／§客戶裁示 |
| A-03 | S3 開始選股（自動掃缺貨／RS／跨季） | 🔭 `screener_go` | form submit「🎯 開始選股」；三掃描顯式發、各自 try、失敗上紅卡；**勾選因子輸入沒拿到→整卡轉紅「選股中止」** | — | ✅ 已覆蓋 | — | `run_shortage_scan`、`run_rs_leader_scan`、`build_trend_map` | 新版比舊版更嚴（舊版失敗只 `print`，名單照出）— 行為差異是改善，但屬判定語意（見 §10） |
| A-04 | S4 結果總覽＋表 | 🔭 | 總覽卡＋dataframe；筆數 20/50/100 selectbox（舊：固定 50） | — | ✅ 已覆蓋 | — | `get_ranked_picks(top_n=req.top_n)` | 舊版 `top_n=300` 後截 50；新版直接傳 top_n。（複驗更正）（已由 INFERENCE 定論為 FACT；重驗 @15cd8fff：`get_ranked_picks` 內 `ranked = ranked[: int(top_n)]` 後才 `return _apply_bear_market_filter(...)`；舊 `app.py` 傳 `top_n=300` 後 `_cands.head(50)`）：`fundamental_screener_service` 先排後 `ranked[:top_n]`，**排名與 top_n 無關**；但**空頭濾網在截斷之後才套用**（`_apply_bear_market_filter`），舊版 `top_n=300` 後過濾再 `head(50)`，新版 `top_n=50/20` 直接截再過濾 ⇒ **bear／caution 下新版列數會少於所選筆數，舊版仍能補滿 50** |
| A-05 | S4' 本次因子命中摘要 | 🔭 | `summarize_factor_hits`（卡上「本次因子」） | — | ✅ 已覆蓋 | — | L5 純函式 | — |
| A-06 | S5 空頭濾網（regime） | 🔭 | `_load_regime` 同樣只在畫面傳；取不到上 `aux_errors` 並寫明「空頭濾網未套用」 | — | ✅ 已覆蓋 | — | `allocation_service::get_macro_regime` | 畫面傳／cron 不傳的不對稱是**刻意**（PIT 可比性），Stage B 不得改 |
| A-07 | S6 下載 CSV | 🔭 `screener_csv` | `p02v_screen_csv`（form 外） | — | ✅ 已覆蓋 | — | — | 匯出的是 top_n 列，舊版固定 50 |
| A-08 | **S7 加入觀察清單**（勾選／選清單／新建／加入） | 🔭 `screener_add_watch_*` | **無**；也沒有指路句 | 🔍 葉1 結果下（需線框＋High gate） | ⬜ 未覆蓋 | 否（靜默缺席） | `watchlist_service::add_picks_to_watchlist`→`gsheet_portfolio::add_to_stock_watchlist` | ⚠️ **寫 Google（High）**；依賴 `STOCK_PORTFOLIO_SHEET_KEY` session 通道，新 👤 我的 P1 已能寫該通道（INFERENCE，未逐行核對）；DEC-083 P2（Sheet CRUD）未授權 |
| A-09 | **S8 凍結前 20 名** | 🔭 `ft_freeze_go` | **無** | 🔍 葉1 結果下（需線框＋High gate） | ⬜ 未覆蓋 | 否 | `forward_test_service::freeze_current_picks`→`append_forward_test_picks` | ⚠️ **寫 Google 且為不可重建的歷史快照**（CLAUDE.md §-1.5.F 判定 3(5)）；cron 另有一條本機 parquet 路徑，**兩條凍結語意不同**（見 §10） |
| A-10 | S9 對帳 | 🔭 `ft_reconcile_go` | **無** | 🔍 或獨立「驗證」區 | ⬜ 未覆蓋 | 否 | `forward_test_service::reconcile_all` | 唯讀但依賴 Sheet＋抓現價；單獨移植無意義（沒有凍結入口就沒有樣本來源，除 cron parquet） |
| A-11 | S10 全台股跨季趨勢排行＋CSV | 🔭 `trend_rank_go` | **無**（跨季轉強僅作為因子） | 🔍 葉1 折疊區 | ⬜ 未覆蓋 | 否 | `get_cross_quarter_trends` | 前 100 的定義與「佳項數」排序規則是判定語意 |
| A-12 | S11 選股網 AI 總結 | 🔭 `render_tab_summary` | **無** | — | ⬜ 未覆蓋 | 否 | `tab_ai_chat.summarize_tab`（Gemini） | AI 結論；Data≠AI 須分層（見 §10） |
| A-13 | G8 三階段濾網（基本面→籌碼技術→AI；15 條件）。（複驗更正）：production 為 auto 串跑、零可操作控制項 | 🔬 多檔個股比較（auto 模式）；`tab_stock_picker.py::render_tab_stock_picker` | **無** | 🔬 查一檔 葉2 批次後的進階區 | ⬜ 未覆蓋 | 否 | `tab_stock_picker::_check_*`、`_generate_ai_report`（Gemini） | 15 條件＋min_pass 為判定語意；（複驗更正；重驗 @15cd8fff）：`tab_stock_picker.py` 內 `from src.data.core.data_loader import _fm_raw_headers` 共 4 處〔`_fetch_quarterly_is`、`_check_contract_liab_yoy`、`_check_institutional_buying`、`_check_major_holders`〕屬 **V-PICKER-PRIV-1（已登記）**；這 4 個函式在 L5 檔內自行 `requests.get(FINMIND_API_URL…)` 抓取則**另未登記**（~~`_fetch_quarterly_is` 約 739–755 行~~ 更正為 `file::symbol`；`CLAUDE.md` §-1.5.F 判定 2 排除項 ①）；舊入口實為 auto 串跑而非可操作入口，新入口候選的取向須由客戶決定（§12.5 S27） |
| A-14 | M1 產業熱力圖：圖＋覆蓋率 | 🌍 `heatmap_load` | 葉2「🗺️ 載入板塊地圖」→ treemap＋覆蓋率 fact；**固定台股／1 日** | 🔍 葉2 | 🟡 部分覆蓋 | 半（`HEATMAP_SWITCH_HINT` 指向「🌍 市場環境 › 🗺️ 產業熱力圖」，新版模式下去不了；句子未說如何切回舊版） | `sector_heatmap_service`→`etf_sector_service::get_sector_returns` | 新頁刻意不放選擇器（線框沒畫＝UI 異動需客戶拍板）；複驗：列入「半 dead-end」，但該句與 DEC-083 第 10 項規範衝突，見 §12.1.7 |
| A-15 | M1 市場（美股 GICS）／區間 selectbox／🔄 刷新 | 🌍 `heatmap_market/period/refresh` | **無** | 🔍 葉2 | ⬜ 未覆蓋 | 半（同上） | `shared/sector_heatmap::US_SECTORS` | 美股 GICS 視角在新頁完全沒有 |
| A-16 | M1 漲跌排行表（含方向欄、缺值排最後） | 🌍 | **無**（只有圖） | 🔍 葉2 圖下 | ⬜ 未覆蓋 | 否 | `etf_render` 內組表（L4） | 色盲／無障礙：treemap 以紅綠為主，排行表是文字備援（INFERENCE） |
| A-17 | M1 AI 白話總結 | 🌍 `sector_ai_btn` | **無** | — | ⬜ 未覆蓋 | 否 | Gemini | AI |
| A-18 | M2 板塊資金潮汐（泡泡圖／⭐持股板塊／資料不足／過期警示／圖例） | 🌍 `render_tab_sector_flow` | 葉2 泡泡圖＋四象限圖例＋TPEx 提示＋缺值板塊列名＋資料不足列名＋快取時戳；持股標示改讀 👤 我的 選定 | — | ✅ 已覆蓋 | — | `sector_flow_service::get_sector_flow_view(strict=True, use_active_selection=True)` | **既有矩陣標「已接？（未驗）」→ 本次讀碼確認已接**；`strict=True` 下壞檔轉紅（舊版轉灰 info） |
| A-19 | T1 個股代碼＋載入 | 🔬 `t2_sid`/`t2_run` | 查一檔 葉1 form「代碼」＋submit；**只吃代碼，無名稱搜尋**；預設空白（舊預設 2330） | 🔬 葉1 | ✅ 已覆蓋 | — | `classify_asset_kind`、`fetch_metrics` | 名稱搜尋新舊皆無（見 A-67） |
| A-20 | T1 天數 slider 60–400（step 10） | 🔬 `t2_days` | selectbox 120/250/500；**僅決定籌碼那格載入的日線長度** | — | 🟡 部分覆蓋 | — | `get_chips_readout(days=)` | 量化方式不同；期間對結論無影響（頁面自己揭露） |
| A-21 | T1 一般K線（還原／非還原切換） | 🔬 `t2_use_normal` | **無**；form 內 caption 寫「K 線一律用還原價」，但 **K 線本身未接線** | 🔬 葉1 K 線區（K 線接線時一併） | ⬜ 未覆蓋 | 半（明細卡指回 🔬 個股） | `fetch_price_data(adjusted=)` | 新頁 caption 在沒有 K 線的頁面宣稱 K 線口徑（INFERENCE：易誤導，輕度） |
| A-22 | T2 MA 勾選（6 個） | 🔬 `t2_ma5…t2_ma240` | 6 個 checkbox 存在（3×2）；**無計算消費者**，僅回顯於判型卡 fact「期間 / 均線」（`page_inspect.py` 約 1901–1903 行，重驗 @15cd8fff）；頁面自己揭露「目前沒有東西會用到」（複驗更正；狀態＝控制項有、效果無，故列 🟡 部分覆蓋） | 隨 K 線 | 🟡 部分覆蓋 | 半 | `MA_*`（L0，其中 5／100 無 SSOT） | 「看得到、按得動、沒效果」；5 與 100 無 SSOT（頁面已登記） |
| A-23 | T17 K 線技術圖 | 🔬 `section_kline_chart` | **無**（明細卡 `unwired`） | 🔬 葉1 明細 | ⬜ 未覆蓋 | 半 | L1 `app_stock_fetchers`、`section_kline_chart` 內含 score_hist session 旗標 | `DETAIL_WHERE` 明寫「沒有你可以執行的出口」 |
| A-24 | T3 型態目標價（ZigZag／微調／型態） | 🔬 `pattern_targets_ui.py`（`render_pattern_targets_for_ticker`） | **無** | 🔬 葉1 明細 | ⬜ 未覆蓋 | 否（未列在 7 段清單內！） | `compute/strategy::compute_pattern_targets` | ⚠️ 目標價／止損＝投資語意；**新頁的「七段」清單沒有它**，是靜默遺漏（見 §「與既有矩陣不符處」A-05） |
| A-25 | T4 資料來源 chip／降級警示／過期值警示 | 🔬 `tab_stock.py` 降級／過期警示段（約 480–560 行，邊界未逐行界定，INFERENCE） | 新版以**每張卡的四態**呈現失敗／缺值；**沒有逐來源 chip 與抓取時間** | 🩺 資料中心（責任方向；現行 nav：無同名頁）。目前只掛在舊 🔬 個股頁側的來源 chip；歸屬待 IA Decision Gate；或卡 fact | 🟡 部分覆蓋 | 否 | `_ps/_is/_ms` 來源標記（L1） | 來源與 `fetched_at` 的 provenance 在新頁看不到（INFERENCE：未見對應 fact）；（複驗：無法確認）複驗未逐卡讀完 fact 欄，「看不到來源／抓取時間」僅為原組推論 |
| A-26 | T4 🔄 強制重抓（`st.cache_data.clear()`＋pop session）——**原樣搬入的部分** | 🔬 `tab_stock.py::render_tab_stock` 的 `t2_force_refresh` 按鈕（重驗：約 538 行；呼叫 `st.cache_data.clear()` 約 541 行） | **無** | — | 🚫 明確不再需要／不應搬入 | 否 | Streamlit 全域 cache | **🚫 理由（不是「不是 UI 能力」，而是「原樣搬入有已知的跨使用者副作用」）**：`st.cache_data.clear()` 為 process 全域，原樣搬會清所有使用者的快取（FACT，重驗）；DEC-083 B5 已立「⛔ 不得用全域 `.clear()` 假裝完成」先例（重驗：`docs/DECISIONS.md` DEC-083 B5）。這是 AI 盤點**建議**，最終認定屬客戶，不構成舊 UI 刪除授權。⚠️ 另（重驗補）：側欄 `app.py` 另有全站「🔄 強制刷新數據」（key `_sb_force_refresh`，約 521–524 行，同樣 `st.cache_data.clear()`），位於 `with st.sidebar:` 頂部、不受「不使用」開關影響，故新版模式下**不是完全沒有**全站重抓手段（只是沒有 scoped 版）；新頁卡面本身沒有重抓入口 |
| A-26b | T4 重抓的**能力本身**（scoped invalidation：只清本人×該代碼；A-26 拆列，原混合格拆開） | 同上 | **無**（重按 submit 可能吃 TTL 內舊值，INFERENCE） | 🔬 葉1（若要補須 scoped） | ⬜ 未覆蓋 | 否 | 同 A-26 | 使用者失去 per-ticker 重抓手段；Streamlit 能否做安全 per-user invalidation 屬技術不確定（DEC-083 B5：做不到須先送 Gate）；不在本盤點決定 |
| A-27 | T5 個股↔總經 regime 聯動 banner | 🔬 `macro_stock_link` | **無** | 🔬 葉1 脈絡區（讀 `get_macro_state` L3） | ⬜ 未覆蓋 | 否 | session `mkt_info`（舊頁籤寫入！新模式下該 key 不存在，INFERENCE） | 舊實作依賴別的頁籤先跑；不可原樣搬 |
| A-28 | T6 個股↔持倉聯動 banner | 🔬 `portfolio_linkage` | **無** | 🔬 葉1（讀 👤 我的〔現行 nav：👤 我的〕選定／`holdings_service`） | ⬜ 未覆蓋 | 否 | session `etf_portfolio_rows`／`t3_data`（舊頁籤寫入） | 同上；與「帶入我的持股」同源議題 |
| A-29 | T7 即時價＋MA20/60/120 趨勢總覽＋趨勢燈號 | 🔬 | 現價在健康度卡 fact；**無 MA 趨勢燈號** | 🔬 葉1 | 🟡 部分覆蓋 | 否 | `safe_ma` | 燈號規則（3 條 MA 計分）是判定語意；（複驗：無法確認）「3 條 MA 計分」規則未被複驗讀到 |
| A-30 | T8 🧭 一眼判讀（4 桶） | 🔬 `summarize_stock_verdict` | **無** | — | ⬜ 未覆蓋 | 否 | `shared/stock_buckets` | 綜合結論；新 UI 目前不做跨桶綜合（四態分離哲學） |
| A-31 | T9 TOC＋6 桶 header | 🔬 | **無** | — | ⬜ 未覆蓋 | 否 | `compute_stock_section_levels` | 桶規則 SSOT |
| A-32 | T10 停利停損／支撐壓力／操作雷達／多因子評分 | 🔬 約 646–880 | **無** | ⚡ 行動（責任方向；現行 nav：無同名頁）。目前只掛在舊 🔬 個股頁；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 否 | `scoring_engine`、`v4_strategy_engine` | ⛔ 買賣語意＋評分權重（見 §10） |
| A-33 | T11 心理檢查 3 勾＋勝利方程式＋禁止操作 | 🔬 `section_psy_checklist` | **無** | — | ⬜ 未覆蓋 | 半 | — | 輸入不寫入任何地方（INFERENCE）；Dead-end 欄（複驗更正）：否→半（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路） |
| A-34 | T12 什麼時候買賣（總資金）＋AI 新聞情緒 | 🔬 `section_when_buy_sell` | **無** | ⚡ 行動（責任方向；現行 nav：無同名頁）。目前只掛在舊 🔬 個股頁；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 半 | `judge_news_sentiment_cached`（Gemini） | 部位計算＝高風險語意；Dead-end 欄（複驗更正）：否→半（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路） |
| A-35 | T13 龍頭預警 | 🔬 `section_dragon_alert` | **無** | — | ⬜ 未覆蓋 | 否 | 合約負債／資本支出 | — |
| A-36 | T14 技術健康度評分六因子 | 🔬 `section_health_score`／`calc_health_score` | **無**；新「健康度」＝財報體檢分數（**不同尺**） | — | ⬜ 未覆蓋 | 否 | `compute/scoring/scoring_helpers::calc_health_score`、L0 `shared/health_score_factors` | ⚠️ 同名異義（見 §10 A-01） |
| A-37 | T15 VCP＋布林 | 🔬 `section_vcp_bollinger` | **無** | — | ⬜ 未覆蓋 | 半 | `calc_vcp`、`calc_bollinger` | — |
| A-38 | T16 籌碼定位 20 日＋異常值徽章 | 🔬 `section_chips_20d` | 籌碼判決卡＋異常值徽章三態 | — | ✅ 已覆蓋 | — | `stock_chips_service::get_chips_readout`（L3） | 新舊口徑一致性（同一份 df）由頁面自述；未獨立複驗 |
| A-39 | T18 即時文字建議 | 🔬 `section_op_recommendation` | **無** | ⚡ 行動（責任方向；現行 nav：無同名頁）。目前只掛在舊 🔬 個股頁；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 否 | — | 買賣建議語意 |
| A-40 | T19 357 評價＋河流圖＋PE preset | 🔬 `section_357_valuation` | 估值判決卡（357 位階）；**無河流圖、無 PE 區間選擇** | 🔬 葉1 | 🟡 部分覆蓋 | 半 | `get_stock_dividends`→`calc_dividend_yield_357` | PE preset 屬估值區間假設 |
| A-41 | T20 財報領先指標 | 🔬 `section_financial_leading` | **無** | — | ⬜ 未覆蓋 | 半 | 合約負債／資本支出 | — |
| A-42 | T21 月營收＋季毛利率 | 🔬 `section_revenue` | **無** | — | ⬜ 未覆蓋 | 半 | `fetch_revenue`、`fetch_quarterly` | — |
| A-43 | T22 策略1結論＋財報趨勢分數（65/35） | 🔬 `section_strategy_conclusion` | 健康度卡 fact 帶「跨季趨勢」一列；**無 65/35 合議分數／標籤** | — | 🟡 部分覆蓋 | 否 | `compute_one_stock_trend` | 65/35 權重＝評分權重（見 §10）；Dead-end 欄（複驗更正）：半→否（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路） |
| A-44 | T23 D2 基本面先行 | 🔬 `section_d2_leading` | **無** | — | ⬜ 未覆蓋 | 否 | — | —；Dead-end 欄（複驗更正）：半→否（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路） |
| A-45 | T24 AI 財報體檢（8 模組；按鈕觸發 Gemini） | 🔬 約 1016–1500 | 獲利能力 **3 格**（no-AI 路徑 `api_key=""`），其餘模組無 | 🔬 葉1 | 🟡 部分覆蓋 | 否 | `analyze_financial_health` | 新頁「5 大指標」只接 3；第 2 排預留未補；AI 路徑完全沒有；Dead-end 欄（本輪重驗更正）：~~半~~→否（`STOCK_DETAIL_SECTIONS` 的七段清單不含財報體檢其餘模組，DETAIL_WHERE 不覆蓋，與 A-33／A-43 同一判準） |
| A-46 | T25 統一判決 | 🔬 `assess_unified` | **無** | — | ⬜ 未覆蓋 | 否 | `compute/scoring` | 結論語意；複驗確認 `assess_unified` 位置（`tab_stock.py` 約 1490–1494 行） |
| A-47 | T26 💠 集保大戶雷達 | 🔬 `chip_radar.py` | **無** | — | ⬜ 未覆蓋 | 否（未列在 7 段清單） | `chip_concentration_fetcher`（第三方站爬蟲） | 爬蟲穩定性；靜默遺漏；複驗補：`tab_stock.py` 約 1873 行將集保大戶摘要注入 AI 首席顧問 prompt，未來移植 AI 層需連動（Data≠AI 分層） |
| A-48 | T27 近期新聞 | 🔬 `_fetch_stock_news` | **無** | — | ⬜ 未覆蓋 | 否 | Google News RSS | 資料層（非 AI）；雲端 IP 易被限流 |
| A-49 | T28 AI 首席顧問報告／清除 | 🔬 `btn_ai_sum2` | **無** | — | ⬜ 未覆蓋 | 否 | `gemini_call` | AI 結論 |
| A-50 | G1 多檔輸入＋批次分析 | 🔬 `multi_input`/`t3_run_btn` | 查一檔 葉2 form（可混貼個股＋ETF；**≤20 檔**，舊 ≤10）＋型別篩選 | — | ✅ 已覆蓋 | — | `fetch_metrics`（每檔） | 上限 10→20 為節流常數變更；無預設範例代碼（舊版預設寫死 10 檔） |
| A-51 | G2 市場狀態快覽 | 🔬 `section_market_status` | **無** | 📊 大盤（責任方向；現行 nav：📊 大盤）。目前只掛在舊 🔬 多檔個股比較；歸屬待 IA Decision Gate（是否已被現行 📊 大盤取代需另行對照，本盤點未查） | ⬜ 未覆蓋 | 否 | session `warroom_summary`（舊頁籤寫入） | 依賴別頁籤先跑 |
| A-52 | G3 組合體檢 vs 基準（落後判定） | 🔬 `section_watchlist_health` | **無** | 🛡️ 持股（責任方向；現行 nav：💼 我的持股）。目前只掛在舊 🔬 多檔個股比較；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 否 | `watchlist_health_service` | 「落後」規則＝判定語意 |
| A-53 | G4 排行總表／多因子拆解／基本面明細／逐檔技術明細 | 🔬 `section_portfolio_summary` | 批次表四欄（代碼／型別／狀態／明細 `key=value`）；欄位＝`fetch_metrics` 結果（個股：財報體檢分＋KD）；**無多因子排行** | — | 🟡 部分覆蓋 | 否 | `fetch_metrics` vs 舊 `run_batch_fetch` | 排名／權重未移植（刻意：頁面寫明「批次表不含估值與籌碼」） |
| A-54 | G5 型態線圖下鑽 | 🔬 `_csgrp_drill` | 下鑽 selectbox（判決卡 metrics），**無型態線圖** | — | 🟡 部分覆蓋 | 否 | 同 A-24 | — |
| A-55 | G6 批次財報體檢 | 🔬 `section_financial_health` | **無**（批次內僅財報分） | — | ⬜ 未覆蓋 | 否 | `analyze_financial_health` | — |
| A-56 | G7 財報趨勢×轉機（權重 slider） | 🔬 `_render_fin_trend_section` | **無** | — | ⬜ 未覆蓋 | 否 | `compute_one_stock_trend` | 權重 0.4–0.9 slider＝使用者可調評分權重（見 §10） |
| A-57 | G9 AI 投資組合綜合判讀／AI 掃利空 | 🔬 `section_ai_portfolio`、`_grp_scan_news` | **無** | — | ⬜ 未覆蓋 | 否 | Gemini | AI |
| A-58 | G10 產業集中度＋總經建議持股對照 | 🔬 | **無** | 🛡️ 持股（責任方向；現行 nav：💼 我的持股）。目前只掛在舊 🔬 多檔個股比較；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 否 | 等權假設（docstring 自陳） | 等權假設與總經建議持股「刻意不相減」 |
| A-59 | G11 風險貢獻分解（張數 data_editor） | 🔬 `_render_risk_contribution_section` | **無** | 🛡️ 持股（責任方向；現行 nav：💼 我的持股）。目前只掛在舊 🔬 多檔個股比較；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 否 | `compute/risk::risk_contribution` | 輸入張數＝使用者資料（不寫入） |
| A-60 | E1 ETF 代號＋🔍 開始診斷 | 🏦 `etf_s_btn` | 同一個代碼框，自動判型 ETF；可覆寫判型 | — | ✅ 已覆蓋 | — | `classify_asset_kind`、`fetch_metrics(etf)` | ETF 對 `fetch_metrics` 是 fail-loud（日線拿不到即 raise），個股是 best-effort |
| A-61 | E1 對照基準輸入 | 🏦 `etf_s_bench` | **無**（判型卡有 `pick_benchmark` 結果但不可改） | 🔬 葉1 | ⬜ 未覆蓋 | 否 | `auto_detect_benchmark` | 既有矩陣已列；新頁顯示「基準」但不可改 |
| A-62 | E2 🚦 綜合研判（留／觀察／換） | 🏦 `recommend_etf_action` | **無** | ⚡ 行動（責任方向；現行 nav：無同名頁）。目前只掛在舊 🏦 ETF 單檔診斷；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 否 | `build_etf_score_row`＋`recommend_etf_action` | ⛔ 持有建議語意 |
| A-63 | E3 收盤／內扣費用率／Beta／AUM | 🏦 | 追蹤／同儕卡 fact 只放「品質評等（星）」「成立年數」；**費用率／Beta／AUM 數值不在卡面**（INFERENCE：`quality` dict 內有，卡面只取 stars） | 🔬 葉1-B | 🟡 部分覆蓋 | 否 | `etf_quality`、`fetch_etf_info` | 資料異常（`invalid_items`）已用 `invalid_data_text` 處理（Z53）；Dead-end 欄（複驗更正）：半→否（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路）；（複驗：無法確認）「費用率／Beta／AUM 數值不在卡面」僅見 `quality` dict 取 stars／`invalid_items` 處理，未逐行確認所有 fact |
| A-64 | E4 策略一/二/三（以息養股避雷／配息健康度／7% 估值／VCP） | 🏦 | 配息卡只有「年化配息率」 | — | 🟡 部分覆蓋 | 半（ETF 明細七段卡） | `fetch_etf_dividends` | 7% 門檻＝估值語意 |
| A-65 | E5 折溢價＋建議買賣時機 | 🏦 | 折溢價卡（%）；**無買賣時機、無折溢價帶** | — | 🟡 部分覆蓋 | 半 | `fetch_etf_nav_history`→`calc_premium_discount` | 折溢價拿不到＝不填，不用 yfinance navPrice（已修事故） |
| A-66 | E6 BIAS／長線 σ／季線×趨勢／破發檢測 | 🏦 | **無** | — | ⬜ 未覆蓋 | 半 | — | 存股規格三大訊號＝買賣語意；複驗更正：`ETF_DETAIL_SECTIONS` 只列「破發檢查」，BIAS／長線 σ／季線×趨勢三項**未列**，宜拆列（拆列後後三項 Dead-end＝否） |
| A-67 | E7a 3-3-3 優質標的 | 🏦 smart | 追蹤／同儕卡有「近 3/6/12 月分位」「成立年數」；**無 3-3-3 三條判定** | — | 🟡 部分覆蓋 | 否 | `etf_smart_analysis` | 3-3-3（>3 年／3 年年化>7%／同儕前 1/3）＝篩選門檻；Dead-end 欄（複驗更正）：半→否（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路） |
| A-68 | E7b 標準差買賣參考帶 | 🏦 smart | **無** | — | ⬜ 未覆蓋 | 半 | `compute_std_bands` | 買賣帶語意 |
| A-69 | E7c 🔗 ETF 分散度分析 | 🏦 smart | **無** | — | ⬜ 未覆蓋 | 否 | `_cached_peer_prices`（L5 自建 cache，V-SMART-CACHE-1） | 冷抓約 30 檔 ETF；Dead-end 欄（複驗更正）：半→否（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路） |
| A-70 | E8 ETF AI 白話總結 | 🏦 | **無** | — | ⬜ 未覆蓋 | 否 | Gemini | AI |
| A-71 | E9 ETF 多檔比較（7 維加權 5 星 PK） | 🏦 `render_etf_grp_compare` | 葉2 批次表對 ETF 給 `fetch_metrics`（折溢價／配息／同儕）；**無 7 維加權、無 5 星綜合** | 🔬 葉2 | 🟡 部分覆蓋 | 半 | `etf_grp_compare_service`、`build_etf_score_row` | 7 維權重＝評分權重；新批次表是另一套欄位，不可視為等價；Dead-end 欄（複驗更正）：否→半（比對 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 清單；清單內才有 `DETAIL_WHERE` 指路） |
| A-72 | 名稱搜尋（代號／名稱） | **新舊皆無** | 只吃代碼 | 🔬 葉1／葉2 輸入框 | ⬜ 未覆蓋 | 否 | `src/config/stock_names::get_stock_name`（只有 code→name；無 name→code，見 §9） | 新增控制項＝UI 異動，須線框；同名歧義處理規則屬 Stage B 前置候選問題 【decision-note：待客戶裁示 S17】 |
| A-73 | 帶入我的持股（新功能，不是移植） | **新舊皆無** | 無 | 🔬 葉2 | ⬜ 未覆蓋 | 否 | `holdings_service::get_holdings`（唯讀） | 須線框（DEC-003 ①） |
| A-74 | 候選清單 → 查一檔（跳頁／預填） | **新舊皆無**（舊：要自己複製代碼到個股分頁） | 🔍 結果表與 🔬 表單之間**沒有任何連結** | 🔍 結果列 → 🔬（導覽＋預填） | ⬜ 未覆蓋 | 半（流程斷點；不是指路句） | session `p03v_*` widget key；`ia_nav` 無跨頁跳轉 | 跨頁導覽＝新互動；`ia_nav` 檔頭自述「不做導覽」 |
| A-75 | `render_smart_ticker_input`（ETF 組合頁共用代號框；原 ETF 組合頁三項 smart 分析共用輸入框） | 舊 `src/ui/etf/etf_tab_smart.py::render_smart_ticker_input`；**目前沒有任何 production 入口** | 無對應使用者功能可比對 | — | 🚫 明確不再需要／不應搬入 | — | — | **INFERENCE→重驗後保留（驗證方式，@15cd8fff）**：(a) `git grep -n "smart_ticker" -- '*.py'` 全 repo 只命中定義（`etf_tab_smart.py`）與 `tests/test_etf_smart_ticker_wiring.py`，無任何 production 呼叫（原僅 grep `src app.py`，此次擴大到全 repo）；(b) 該測試的註解明寫「P3 v19.202：組合頁 `_grp` smart 區塊應已移除（搬戰情室／去重複）」並斷言 `render_smart_ticker_input(key_suffix='_grp')` **不在** `app.py`——即舊 UI 刻意移除，不是遺漏。🚫 理由＝使用者已不可達、無可搬的互動（AI 盤點**建議**；最終認定屬客戶，不構成刪除授權）。⚠️ 該函式仍被測試 `test_shared_ticker_input_exists` 釘住，動它須同 PR 改測試（`docs/audit-2026-08/LIVE_VERIFY_AND_DECLUTTER.md` 亦有記載）。動態呼叫（`getattr`／字串）未窮舉排除，INFERENCE |
| A-76 | E10 🏆 同儕排名（vs 類）（複驗補列） | 🏦 單檔診斷 `#### 🏆 同儕排名(vs 類)` | 追蹤／同儕卡部分覆蓋（近 3/6/12 月分位、成立年數）；**無 vs 類排名** | 🔬 葉1-B | 🟡 部分覆蓋 | 半（七段清單含「同儕7維評分」，與此排名是否等價待查） | `etf_quality` | 複驗補列；是否等價（複驗：無法確認） |
| A-77 | E11 📈 近 5 年走勢圖（複驗補列） | 🏦 單檔診斷 `#### 📈 近5年走勢` | **無**；七段清單的「淨值 vs 市價走勢」資料不同（淨值對照 vs 價格走勢），是否等價 **（複驗：無法確認）** | 🔬 葉1-B | ⬜ 未覆蓋 | 半 | `fetch_etf_price` | 複驗補列 |
| A-78 | E12 🧩 成分股持股明細（top 15）＋ E13 PROXY_URL 缺席警示（複驗補列） | 🏦 單檔診斷 `render_etf_holdings(ticker, top_n=15)`；`etf_tab_single.py` 約 121–138 行（~~112–132~~ 更正：重驗實測） | 成分股：七段清單有「成分股與集中度」但未接線（半 dead-end）；**PROXY 缺席警示新頁沒有**（`page_inspect.py` 無 `PROXY` 字串；`page_find.py` 的 `PROXY` 1 次僅為 `*_SINGLE_STOCK_PROXY`） | 🔬 葉1-B（缺值原因揭露） | ⬜ 未覆蓋 | 成分股：半；PROXY：否 | `render_etf_holdings`、`proxy_helper` | 違反「缺值必須說明原因」的精神：費用率／折溢價／AUM 為 N/A 時，新頁看不到「因為沒設 PROXY」的說明（INFERENCE） |

**Coverage 計數（本輪逐列重數 @15cd8fff，79 列；A-26 拆為 A-26／A-26b）**：✅ 已覆蓋 11｜🟡 部分覆蓋 17｜⬜ 未覆蓋 49｜🚫 明確不再需要／不應搬入 2（合計 79）。~~舊計數 78 列（✅11｜🟡17｜⬜48｜🚫2）~~（更正原因：A-26 原為「🚫（原樣不搬）」混合格＋「使用者失去重抓手段另列 ⬜ 候選」的註文，依 DEC-085 §19.6 拆為 A-26［🚫］＋A-26b［⬜］，⬜ 由 48 變 49；另外 A-22「🟡（控制項有、效果無）」與 A-75「🚫（死碼，過時）」的括註移出狀態格，狀態格只剩四種正式狀態，不改計數）。調查組原計數 75 列（11／16／46／2）；本節新增 A-76～A-78 三列（複驗補列），故 🟡 16→17、⬜ 46→48，再加 A-26b 為 49。Dead-end 欄經複驗更正 8 列＋本輪 A-45（半→否）共 9 列（見各列），原調查檔若有 Dead-end 分佈統計句，以本表為準。

#### 12.1.7 若未覆蓋：新 UI 應放哪裡、是否形成 dead-end（項目 7；候選非設計決定）

- **候選位置（僅候選，非設計決定）**：
  - 🔍 找標的 葉1「選股結果」之後：➕ 加入觀察清單、🧊 凍結、📊 對帳、🌍 跨季趨勢排行、初篩明細折疊區、CSV 之外的「下一步」列（→ 查一檔）。
  - 🔍 葉2：熱力圖市場／區間切換、排行表、AI。
  - 🔬 葉1 單檔：K 線／型態目標價／357 河流圖／月營收／財報領先／VCP／ETF 七段；脈絡區（總經聯動、持倉聯動）。
  - ⚡ 行動（責任方向；現行 nav：無同名頁）：T10／T12／T18／E2／E6／E7b 這類「何時買賣／停利停損／留觀察換」內容，**目前只掛在舊 🔬 個股／🏦 ETF 單檔診斷；歸屬待 IA Decision Gate**（本盤點不決定它屬 🎯 還是 ⚡）。
  - 🛡️ 持股（責任方向；現行 nav：💼 我的持股）：G3 組合體檢、G10 集中度、G11 風險貢獻、E7c 分散度（與持股／組合相關）；目前只掛在舊 🔬 多檔個股比較／🏦 ETF 單檔診斷；歸屬待 IA Decision Gate。
  - 📊 大盤（責任方向；現行 nav：📊 大盤）：G2 市場狀態快覽；目前只掛在舊 🔬 多檔個股比較；歸屬待 IA Decision Gate（是否已被現行 📊 大盤取代，需 B/C 組對照）。
- **dead-end 判定（FACT）**：
  - **半 dead-end（明寫指路到舊頁籤）**：`page_inspect.py::DETAIL_WHERE`（個股七段、ETF 七段，句子含 `NO_EXIT_MARKER`「沒有你可以執行的出口」＋「現行入口仍在既有的 🔬 個股 / 🏦 ETF 分頁」）；`page_find.py::HEATMAP_SWITCH_HINT`（「到 🌍 市場環境 › 🗺️ 產業熱力圖」）。兩句都**沒有說明如何切回舊版**（側欄 radio 選「不使用」）。
  - **靜默缺席（沒有指路也沒有入口）**：S7／S8／S9／S10／S11、T24（AI 路徑）、T26／T27／T28、型態目標價（A-24）、E2、E8、G3–G11。使用者看不到新頁缺了什麼，也不知道去哪裡找。
  - **流程斷點**：A-74 候選→查一檔無連結。
  - **控制項有、效果無**：A-22 MA 勾選（頁面有揭露）。

- **複驗補（DEC-083 第 10 項衝突）**：`docs/DECISIONS.md` DEC-083 第 10 項明定「不得再出現：新版模式看不到的頁面卻叫使用者直接去點」，指定統一句型為「目前請切回舊版 → …」。`DETAIL_WHERE`（「現行入口仍在既有的 🔬 個股 / 🏦 ETF 分頁」）與 `HEATMAP_SWITCH_HINT`（「到 🌍 市場環境 › 🗺️ 產業熱力圖」）在新版模式下正屬此型，**與該客戶規範直接衝突**。但 DEC-083 第 10 項的文字限於 Sheet／持股類語境，**是否延伸到明細指路**【decision-note：待客戶裁示 S24】（Stage B 前置候選問題，Stage B 再收斂為少量 Decision Gates；本輪不要求逐題裁示）（§12.5 S24；`BACKLOG` `ME-OLD-TAB-POINTERS` 已登相關現象）。

- **複驗補（七段清單與指路覆蓋）**：`DETAIL_WHERE` 指路**只覆蓋** `STOCK_DETAIL_SECTIONS`（K線＋均線／357 河流圖／財報領先／VCP·布林／月營收／什麼時候買賣／心理檢查）與 `ETF_DETAIL_SECTIONS`（淨值 vs 市價走勢／折溢價帶／配息紀錄與以息養股試算／成分股與集中度／同儕 7 維評分／標準差買賣帶／破發檢查）所列段落；清單外的能力（型態目標價、集保大戶、新聞、統一判決、一眼判讀、策略 1 結論、D2、3-3-3、分散度、BIAS／σ、費用率等）是**靜默缺席**。

#### 12.1.8 哪些能力目前仍只能切回舊 UI（項目 8）

必須切回舊版（側欄 radio「不使用」）才能做：
1. **寫入類**：➕ 加入觀察清單、🧊 凍結前 20 名。（Google 寫入／不可重建歷史）
2. **驗證類**：📊 對帳。
3. **選股延伸**：全台股跨季趨勢排行＋CSV、初篩逐檔明細表、三階段濾網（G8）、選股網 AI 總結。
4. **個股**：K 線＋均線＋一般K線切換、型態目標價、357 河流圖、財報領先、月營收／季毛利、VCP／布林、停利停損／操作雷達／多因子評分、心理檢查、買賣時機、龍頭預警、統一判決、一眼判讀、集保大戶雷達、新聞、AI 財報體檢（AI 路徑）、AI 首席顧問報告、強制重抓。
5. **多檔**：排行總表／多因子拆解、組合體檢 vs 基準、批次財報體檢、財報趨勢×轉機、產業集中度、風險貢獻、AI 組合判讀、AI 掃利空。
6. **ETF**：綜合研判（留／觀察／換）、基準覆寫、費用率／Beta／AUM 數值、策略一～三、買賣時機、BIAS／σ／季線×趨勢／破發、3-3-3 三條判定、標準差帶、分散度、AI 白話總結、7 維 5 星 PK。
7. **板塊**：熱力圖市場（美股）／區間切換、排行表、AI 白話。

#### 12.1.9 重複邏輯／重複入口／需 SSOT 收斂（項目 9）

1. **「健康」兩把尺**：技術六因子 `calc_health_score`（舊 🔬／🏆）vs 財報體檢綜合分（新「健康度」，`page_hold.py::INSPECT_SCALE_SHAPE` 自述「連續分數 0–100＋等第」）。持股頁另有「序數燈號」第三套（`HOLD_SCALE_SHAPE`）。三套各自分開本是刻意，但**名稱沒有區隔**（INFERENCE：客戶讀「健康度」不會知道是哪一把）。
2. **選股網兩份實作**：舊 `app.py` 內嵌（直呼 `yield_screener.fetch_pe_name_maps` 與 L3）vs 新 `page_find.py::load_screen_result`（全走 L3）。排名同源 `get_ranked_picks`，但**前處理不同**：舊＝失敗只 `print`、名單照出；新＝勾選因子輸入缺→紅卡中止。兩套並存期間，**同一組條件可能一邊出名單、一邊中止**。
3. **熱力圖兩份入口**：舊 `etf_render.py::render_sector_heatmap`（widget key `heatmap_*`，重驗：`heatmap_market`／`heatmap_period`／`heatmap_refresh`／`heatmap_load`；AI 鈕為 `sector_ai_btn`）vs 新 `sector_heatmap_service`＋`sector_heatmap_render`（`p02v_*`）；類股宇宙已上移 L0 `shared/sector_heatmap`，舊 L4 以別名轉發（FACT，頁面自述）。treemap 組裝 `_build_treemap_data = build_sector_treemap`（`etf_render.py` 約 655 行別名，~~末尾~~ 更正：後面仍有 `render_sector_heatmap` 等）。
4. **資金潮汐兩份讀持股的方式**：舊 `tab_sector_flow.py` 讀 session `etf_portfolio_rows`／`stock_portfolio_sheet_id`；新頁讀 👤 我的 選定。兩邊「你的持股」來源**不同**（舊＝舊頁籤算出來的 ETF 組合列；新＝選定的組合＋觀察清單）。
5. **凍結兩條路徑**（重驗 @15cd8fff：cron 腳本 `get_ranked_picks(_factors, top_n=max(args.top_n,300), … auto_fetch=True)` 未傳 `regime`，`get_ranked_picks` 的 `regime` 預設 `None`；`--factors` 留空＝`list(SCREEN_ANGLE_LABELS.values())` 5 因子）：手動 UI（`freeze_current_picks` → Google Sheet，使用者勾的因子，**含空頭濾網**）vs cron（`update_forward_test_freeze.py` → 本機 git 追蹤 parquet，**全 5 因子、`regime=None`**，`top_n=max(top_n,300)` 後取 `FORWARD_TEST_FREEZE_TOP_N`）。對帳讀「本地 ∪ Google Sheet」去重（CLAUDE.md §2.3）。**兩種 cohort 的語意不同**，混在一起對帳是否仍有意義＝需客戶裁示（見 §10、§客戶裁示）。
6. **名稱 → 代碼反查不存在**：`src/config/stock_names.py` 只有 `get_stock_name`／`refresh_name_cache`（重驗 @15cd8fff：`^def` 實測 `src/config/stock_names.py` 僅此二函式，`stock_names_fetcher.py` 有 `_ensure_cache`／`lookup_via_yfinance` 等但無 name→code 函式；以下 pattern 仍為單組 grep，「目前沒有」限於該 pattern 與 `src shared` 範圍：`name_to_|by_name|find_by_name|lookup_name|search_by_name|{v: k for` 在 `src shared` 無相關命中，唯一命中是無關的 `_SEVERITY_TO_VERDICT`）。但 L1 `stock_names_fetcher._ensure_cache` 持有 code→name 全表，反查技術上可行（INFERENCE，未實作驗證）。
7. **三階段濾網（G8）在 L5 檔內直接取數**：（重驗 @15cd8fff，~~`_fetch_fs_safe`／`_fetch_quarterly_is`／`_check_*` 在 L5 做 FinMind 抓取~~ 更正：`_fetch_fs_safe` 只是包 L1 public `src.data.core.fetch_financial_statements`〔EX-PASSTHRU-1 範圍〕，**不自己抓**；直接在 L5 檔內 `requests.get(FINMIND_API_URL…)` 的是 `_fetch_quarterly_is`、`_check_contract_liab_yoy`、`_check_institutional_buying`、`_check_major_holders` 四個函式，各自 `from src.data.core.data_loader import _fm_raw_headers`＝**V-PICKER-PRIV-1（已登記，4 處）**；L5 檔內自行 `requests` 抓取本身另未登記，屬 `CLAUDE.md` §-1.5.F 判定 2 排除項 ①）。若新 UI 要移植，須先下沉 L3（CLAUDE.md §-1.5.F 判定 2 的排除項 ①）。
8. **`render_smart_ticker_input` 在 production 零 caller**（重驗 @15cd8fff：全 repo `git grep -n "smart_ticker" -- '*.py'` 只命中定義與 `tests/test_etf_smart_ticker_wiring.py`；`app.py:1110-1119` 單檔頁只呼叫 `render_333_section`／`render_std_band_section`／`render_correlation_finder` 三者〔~~`app.py:1112-1119`~~ 更正：1111–1113 為 import、1117–1119 為呼叫〕。~~單組 grep~~ 已擴大到全 repo＋測試註解交叉驗證，見 A-75；動態呼叫未窮舉排除）。
9. **L5 自建 cache**：`etf_tab_smart.py` 5 個 `@st.cache_data`（V-SMART-CACHE-1，已登記）；`section_batch_fetcher` 用 `shared.app_cache._save_cache('t3v2', …)` 寫本機檔。
10. **預設值寫死**：`tab_stock_grp.py` 預設 10 檔、`etf_tab_grp_compare.py` 預設 5 檔 ETF、`etf_tab_single.py` 預設 `0050`、`tab_stock.py` 預設 `2330`。新頁一律空白（更誠實，但「預設代碼讓人一鍵看到示範」的行為消失）。
11. **按鈕 gating 與 AI 重複**：選股網 `render_tab_summary`、個股 `btn_ai_sum2`、多檔 `t3_ai_gen`、ETF `etf_ai_sum_{ticker}`、熱力圖 `sector_ai_btn` — 五套 AI 觸發各自實作，新 UI 一套都還沒有（ETF 單檔的 key 為動態 `etf_ai_sum_{ticker}`，~~`etf_s_ai`~~ 更正：重驗 @15cd8fff 該字面 key 不存在；多檔為 `section_ai_portfolio.py` 內的 `t3_ai_gen`）；Stage B 設計 AI 層時應收斂為單一入口，並與資料層分區（Data≠AI）。

#### 12.1.10 高風險投資語意（項目 10；Stage B 不得自行改定義；只能標「需客戶裁示」）

1. **兩把「健康」尺同名**（見 §9 #1）：不得合併、不得改名、不得把技術分數與財報分數並排成同一排名。
2. **選股網綜合評分**：各因子百分位平均排序、5 因子定義（估值=本益比低、EPS 高、缺貨動能 4 訊號、抗跌 RS σ、跨季轉強）、`RS_RANKABLE_TIERS` 含「落後大盤」、`SHORTAGE` tier 邊界、`PRESCREEN_REQUIRED_PASSES`（四項全過）與其門檻（負債比<50%、EPS>0、三率三升 YoY、淨流動值>0）— **全在 L0/L3 SSOT，Stage B 只能呈現不能改**。
3. **空頭濾網（regime ∈ {bear, caution} 剔除未贏大盤）**：只有畫面傳、cron 不傳 — **不得為了「一致」而統一**。
4. **前進式驗證（forward test）**：`data_cache/forward_test/picks.parquet` 是**凍結歷史快照＝不可重建**（CLAUDE.md §-1.5.F 判定 3(5)）；任何「凍結」入口不得重算歷史、不得覆蓋、不得刪；手動與 cron 兩種 cohort 語意不同（§9 #5）；PIT／零 lookahead 是其存在理由。
5. **Google 寫入類**（加入觀察清單、凍結）：High，須客戶核准＋DEC-082 Stage C（Stage C 才是正式客戶 Gate）；`PRODUCTION_WRITE_APPROVED=False`（重驗 @15cd8fff：`shared/risk_cap_history_policy.py` 為 `False`）、DEC-066 F 不變（DEC-066 F 本輪未複驗）。
6. **停利停損／支撐壓力／操作雷達／多因子評分／買賣時機（總資金部位）／即時文字建議／ETF 留觀察換／標準差帶／存股三大訊號／破發檢測**：買賣建議語意，目前新 UI 沒有；Stage B 不得為了「補齊」而發明規則，也不得決定它們歸 🎯 還是 ⚡（責任方向歸屬待 IA Decision Gate，DEC-085 §19.2）。
7. **評分權重與門檻**：財報趨勢 65/35（使用者可用 slider 0.4–0.9 調）、`calc_health_score` 六因子配分（L0 `shared/health_score_factors`）、ETF 7 維加權 5 星、3-3-3（>3 年／3 年年化>7%／同儕前 1/3）、357 殖利率帶（`YIELD_HIGH/MID/LOW`）、PE 區間 preset、三階段 15 條件＋`min_pass`。
8. **PIT／look-ahead**：新頁 357 位階與舊頁同一份股利來源（`fetch_dividend_data`）；季財報用公告日對齊的處理在 L3，Stage B 不得改日期鍵。
9. **AI 結論**：S11／T24／T28／G9／E8／M1-AI 都是 Gemini 產出；Stage B 須把 AI 層與資料／規則判讀層分區，且不得讓 AI 結論覆蓋規則判讀（Data ≠ AI）。
10. **proxy／estimated／missing**：新頁已遵守「缺值≠0／中性／正常」（`UI_EMPTY`／`UI_FAILED` 分離、折溢價拿不到就不填、NaN／±inf 視為缺值）；Stage B 新增卡時須維持。**舊 UI 違規發現（FACT；重驗 @15cd8fff：`app.py` 844 缺貨掃描、855 抗跌 RS、862 跨季趨勢、873 存活池不可用、899 regime 取得失敗，皆為 `print(f'[screener] …失敗／不可用…')`）**：`app.py` 選股網在存活池／~~PE 取數~~（更正：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；實為抗跌 RS 與跨季趨勢計算）／缺貨掃描失敗時只 `print`，結果區顯示「目前沒有符合的標的」— 把「取數失敗」畫成「0 檔」。這是舊 UI 的 missing≠empty 問題（新 UI 已修；舊 UI 照留，DEC-081 第 8、10 項）。

### 12.2 🛡️ 持股（盤點範圍標籤，依現行 nav 暫代；調查組 B＋獨立複驗 B；更正已套用）

> 範圍：新 UI `src/ui/views/page_hold.py`（💼 我的持股，5462 行，以符號與卡片 id 盤點）＋`src/services/holdings_service.py`、`portfolio_binding_service.py`、`portfolio_deep_service.py`；舊 UI `src/ui/etf/etf_tab_dividend_station.py`（🏦 存股戰情室／頁籤「💼 我的持股戰情室」）、`src/ui/tabs/portfolio_manager.py`（📁 組合管理）、`portfolio_status_bar.py`、`portfolio_binder.py`、`src/ui/etf/etf_tab_portfolio.py`（ETF 組合，現只掛在戰情室 expander 內）。H-nn 為調查組編號（非 BACKLOG ID）。

> **名稱說明（DEC-085 §19.2／PROJECT_RULES §19）**：「🛡️ 持股」是長期「責任方向」，**不等於**現行 nav 名稱或既有 view 一對一對映；本節標題與 H-nn 範圍只是「**盤點範圍標籤，依現行 nav 暫代**」。現行 nav：新版模式（側欄 radio「🆕 新版戰情室（試用中）」，`shared/ia_nav.py::PAGE_LABELS`）的「💼 我的持股」（`page_hold`）與「👤 我的」（`page_me`）；「不使用」模式的頁籤「💼 我的持股戰情室」「📁 組合管理」。本節各缺口的程式碼**目前只掛在**上述頁；**歸屬待 IA Decision Gate，本盤點不決定**。
>
> **基準與重驗**：程式碼＝main @ `15cd8fff`（4e6bf8ee→15cd8fff 僅 docs 變更，0 程式碼變更；本輪重跑 `git diff --name-only 4e6bf8ee 15cd8fff` 排除 `docs/`、`*.md` 後 0 檔）。**重驗 @15cd8fff**：本節寫成 FACT 的 code 層級宣稱（`file::symbol`、行號、grep／AST 結果、widget 清單、caller 清單）已逐條對 worktree 重跑；成立者保留，有出入者在該處以 ~~刪除線~~＋（更正原因）更正；行號是重驗當下實測、會漂移，**以 `檔案::符號` 為準**；未能重驗者就地標「INFERENCE／未複驗」。

#### 12.2.0 一頁結論（複驗後）

1. **新 💼 的戰情室葉已顯示**汰弱／加碼／停利／換股／80-20／建議持股水位／VIX／兩套刻度／壓測／VaR／配息現金流／AI 總結（唯讀）；**沒有**舊戰情室的逐檔戰情表（現價／損益%／市值／健檢／235／加碼金／3-3-3／建議動作）、點列展開逐盞燈明細＋兩張週線圖、規則式 235 加碼金額文字、ETF 組合 11 格分析中的大部分、葡萄串、任何 CRUD。

2. **新頁實際 widget 只有三個**：頁首表單 `form_holdings_view`（一組 radio＋一顆 submit）、`⚡ 生成 AI 總結` 按鈕，加上 `st.tabs` 兩葉；**無**重新載入、無列選取、無 `page_link`／`switch_page`（重驗 @15cd8fff：AST 掃 `page_hold.py` 全檔 `st.<attr>(` 呼叫＝`button`〔:5279〕、`tabs`〔:5440〕、純顯示的 `dataframe`〔:5352、:5413，無 `on_select`〕與 `markdown`／`caption`，另 `_ui_kit.single_submit_form`；`git grep "page_link\|switch_page"` 於全 repo〔排除 `docs/`、`*.md`〕0 命中。~~全 repo 範圍複驗：無法確認~~（更正：本輪已重跑，0 命中）；`page_me` 的 widget 不在本節範圍）。

3. **最嚴重的複驗更正（三項）**：(a) 客戶 2026-09-05 拍板的線框 `docs/wireframes/stock_ia_v1.html`（DEC-017）葉1 ③ **已逐字含**「點任一檔，右側展開週線與布林 z」——調查組採信的 `page_hold.py` 檔內說法「新增互動元件須先過 A-8 草稿」不能直接採信（見 H-09b）；(b) 舊戰情室讀 ETF 通道用 `_get_active_sheet_id()`，它**會 fallback 到 secrets 部署預設**，新 UI 則把「只有部署預設」判為未綁（`ACTIVE_DEPLOY_DEFAULT_ONLY`）——這是比「名稱排序第一本」更大的 SSOT 分歧（見 R2）；(c) 每日推播 cron 不是「攤平所有 portfolios 分頁列」，而是「聯集＋以 ticker 去重、保留首見」，會**靜默丟棄同代號不同均價的列**（見 R6）。

4. **Data≠AI 發現（新頁）**：235 加碼**金額**與規則式文字只存在於付費 AI 的 digest 輸入；舊版是規則式事實永遠先出、AI 在後（H-14b；複驗更正了調查組「代號也只在 AI 文字」的過度敘述）。

5. **「推播」命名衝突**：⑦ 卡名稱「唯一推播出口」，但頁上沒有任何推播動作；真正的推播是 cron（見 §12.4）。

#### 12.2.0a 搜尋方法（全稱句依據）

| 查證 | 方法 | 結果 |
|---|---|---|
| `render_etf_portfolio`／`render_grape_ladder`／`render_etf_ai` 有誰呼叫 | `grep -rn` 於 `app.py src`（排除定義檔與 tests） | `render_etf_portfolio`、`render_grape_ladder` 的唯一 production 呼叫點＝`etf_tab_dividend_station.py::render_dividend_station`（expander「5️⃣ 組合深度分析」，:273-286）；`render_etf_ai` 只剩 `etf_dashboard.py:57` 的 re-export，**無** production 呼叫 [F]（單組 grep，未窮舉動態載入）。**重驗 @15cd8fff**：重跑 `git grep` 結果相同——`render_etf_portfolio` 呼叫在 `etf_tab_dividend_station.py:277-278`、`render_grape_ladder` 在 `:283-284`（expander 起點 :273）；`etf_dashboard.py:56-57` 為 re-export；`app.py:41`、`:209` 僅註解；`render_etf_ai` 於 `app.py`／`src`／`scripts` 無呼叫（`src/ui/etf/__init__.py` 僅列模組名）。仍為單組 grep，`getattr`／字串動態載入不在範圍 |
| 誰在讀 Sheet 持股／觀察清單 | `grep -rn "list_portfolios 或 load_portfolio 或 list_stock_watchlists 或 load_stock_watchlist 或 _get_active_sheet_id 或 _get_active_stock_sheet_id 或 get_holdings"`（`app.py src shared scripts`，排除 tests／L1 本體） | 見 12.2.9 表 R1–R8 [F]（~~5 條讀取路徑~~ 更正：該表現列 R1–R8 共 8 列）；`scripts/` 另有 SA 路徑 [F]。**重驗 @15cd8fff**：重跑 `git grep`（排除 L1 本體、tests），命中檔＝`holdings_service`／`me_account_service`／`portfolio_binding_service`／`sector_flow_service`／`watchlist_service`／`etf_tab_dividend_station`／`portfolio_binder`／`portfolio_manager`／`page_hold`（僅 `get_holdings`）／`page_today`（僅 docstring 提及）；SA 路徑＝`scripts/push_holdings_daily.py`→`gsheet_sa_reader`。單組 grep，非窮舉 |
| `page_hold` 的 widget | `grep -n` 於 page_hold 搜 st.button／checkbox／selectbox／radio／text_input／download_button／link_button／page_link／switch_page／expander／popover／toggle | 實際 widget 只有：①`_ui_kit.single_submit_form` 的一組 radio＋一顆 submit（`_render_holdings_form`:5170）②`st.button(AI_SUMMARY_LABEL)`（`_render_ai_button`:5258-5279）。**無**重新載入、無列選取、無 link／page_link／切頁鈕 [F]。**重驗 @15cd8fff**：以 AST 重掃（見 12.2.0 第 2 點），結果相同 |
| 新版模式下哪些舊東西不畫 | 讀 `app.py:326`（側欄 radio）、`:675`（`st.stop()`）、`:687`（`render_portfolio_status_bar()`）、`:707`（7 頁籤） | 新版模式在 `:675` `st.stop()`；`:687` 以後（status bar、羅盤、7 頁籤含 💼 戰情室 `:1185`、📁 組合管理 `:1191`）不畫 [F]（重驗 @15cd8fff：`app.py` `st.radio(`:326、`st.stop()`:675、`render_portfolio_status_bar()`:687、`st.tabs([...])`:707、`with tab_warroom`:1185、`with tab_mgmt`:1191 皆成立） |
| 「切回舊版」是什麼動作 | 讀 `app.py:299-330`、`page_me.py:195-197` | 側欄 radio「🆕 新版戰情室（試用中）」選「不使用（用下方原功能）」；**該 radio 預設就是「不使用」（`index=0`，`app.py:327`；`_IA_NAV_OPTIONS` 第一項＝`_IA_NAV_OFF`，`app.py:301-302`）** [F]（重驗 @15cd8fff 成立） |

#### 12.2.1–12.2.2 舊 UI 有哪些功能（項目 1）與使用者目的（項目 2）

> 「舊入口」＝舊 UI 的 `檔案::符號`；全部在 **「不使用（用下方原功能）」模式**才畫得出來。

**A. 🏦 存股戰情室（`etf_tab_dividend_station.py::render_dividend_station`，頁籤「💼 我的持股戰情室」`app.py:1185`）**

| ID | 功能 | 使用者目的 | 舊入口 |
|---|---|---|---|
| H-01 | 進頁自動載入持股（投資組合 held＋觀察清單 held=False；各取名稱排序第一本） | 不重打持股，直接分析「我有什麼」 | `_load_holdings_from_portfolio`:710（`_names[0]`:736、`_snames[0]`:763） |
| H-02 | 持股預覽表（代號／名稱／種類／**類別 核心·衛星**／張數／均價） | 確認系統讀到哪些部位 | `_holding_preview_row`:106 |
| H-03 | 🔄 重新載入（清 L1 讀取快取＋清 session 結果） | 改了 Sheet 後立刻拿新資料 | `render_dividend_station`:142（`_gsp.clear_read_cache()`:145） |
| H-04 | 缺 Sheet／空表時就地綁定（登入 CTA、Drive 挑選、貼 URL） | 不離開本頁完成綁定 | `render_dividend_station`:167-188 → `portfolio_binder.render_holdings_binder` |
| H-05 | 🚀 跑存股戰情室（button-gated 取數） | 顯式觸發逐檔抓取（週K／折溢價／VIX） | `render_dividend_station`:196 |
| H-06 | 1️⃣ 結論三卡（該做什麼／訊號可信度 N/M／需要處理）＋未實現損益／總市值 | 一眼知道今天要不要動 | `_render_layer1`:322 |
| H-07 | 3️⃣ 戰情表（分兩區）：**每檔**張數／均價／現價／損益%／市值／健檢／235 燈號／**加碼金**／3-3-3／**建議動作**（個股：財報體檢／趨勢／KD） | 逐檔看賺賠與該做什麼 | `_perf_row`:55、`_ETF_COLS`:49、`_STOCK_COLS`:51、:243-252 |
| H-08 | VIX 顯示 | 判斷 235 的 VIX 條件 | :236-237 |
| H-09 | 🔎 逐盞燈明細：燈格牆＋圖例；**選列就地展開**單檔每盞燈的判定／可信度／算出值／門檻／來源／缺值原因＋**兩張週線走勢圖**（週K vs 均線、布林 z） | 理解「為什麼這一檔亮這盞燈」 | `_render_light_detail`:461（`st.dataframe(` :508，`on_select="rerun"` :517；圖 :547-555） |
| H-10 | 📊 80/20 實際配置偏離＋衛星停利清單 | 該減什麼 | `_render_allocation_take_profit`:572 |
| H-11 | 同名兩套刻度揭露 | 防 ETF 健檢與個股健檢互比 | `render_two_scales`（L4）:260 |
| H-12 | 4️⃣ 換股建議（換出＝持有🔴汰弱；換入＝觀察清單綠燈優先、其次選股池；搭配總經位階攻守） | 該換什麼 | `_render_switch_advice`:628 |
| H-13 | 5️⃣ 📊 組合深度分析 expander（內掛 ETF 組合 H-20…H-36＋葡萄串 H-37） | 組合層風險／配息／再平衡 | :273-286 |
| H-14 | 6️⃣ 🤖 AI 戰情總結：**規則式事實永遠先出**（汰弱警訊代號＋建議動作、235 加碼觸發代號＋**加碼金**、無事句、抓取失敗代號清單）→ 有金鑰才 AI 潤稿 | 把結論濃縮成可推播文字 | `_render_ai_summary`:671；按鈕 :698；結果存 `_station_ai_text` |
| H-15 | 目標配置常駐註腳（核心 80／衛星 20／停利 %） | 揭露規則 | :291-293 |

**B. 📁 組合管理（`portfolio_manager.py::render_portfolio_manager`，頁籤 `app.py:1191`）**

| ID | 功能 | 使用者目的 | 舊入口 |
|---|---|---|---|
| H-40 | 🚀 從 Drive 挑 Sheet（資料夾→📂列出→選→✅使用此 Sheet） | 綁定投組資料庫 | `_render_drive_picker`:127 → `portfolio_binder.render_drive_picker`:103（~~:130／:112~~ 行號漂移更正） |
| H-41 | 🆕 建立新投組 Sheet（寫 Google Drive） | 第一次使用 | `portfolio_binder.py`:129（`_gsp.create_new_sheet()` 呼叫；~~:134~~ 行號漂移更正）→ `gsheet_portfolio.create_new_sheet` |
| H-42 | 顯示目前 ETF／個股兩通道 Sheet（「同一本 ✅」／「兩本不同」） | 確認綁到哪 | `_render_drive_picker`:140-146 |
| H-43 | 投資組合：選一本→📂載入進 data_editor→編輯（代號／張數／均價）→命名→💾儲存→🗑️刪除（兩段確認） | 管理持有部位 | `_render_etf_section`:162 |
| H-44 | 觀察清單：同上（純代號） | 管理追蹤清單 | `_render_stock_section`:231 |
| H-45 | Sheet API 錯誤白話分類（429／401／403／404） | 看懂為什麼讀不到 | `_classify_sheet_api_error`:43 |

**C. 🔗 我的組合狀態列（`portfolio_status_bar.py::render_portfolio_status_bar`，`app.py:687`，標題下常駐 popover）**

| ID | 功能 | 目的 |
|---|---|---|
| H-50 | 三態晶片（🟢已綁定 N 本／🟡綁了但空／⚪未綁定／🔴讀取有問題）＋popover 內就地綁定／換一本 | 任何頁都看得到綁定狀態 |

**D. ETF 組合（`etf_tab_portfolio.py::render_etf_portfolio`，現僅經 H-13 expander 到達）**

| ID | 功能 | 使用者目的 | 符號／行 |
|---|---|---|---|
| H-20 | 持股輸入 data_editor（代號／張數／均價／**目標比例%選填**；有持股時以組合管理持股 seed，否則顯示 4 檔**範例列**） | 組合分析輸入 | :181-253 |
| H-21 | 再平衡容忍偏離度 slider＋📊 計算組合 | 設門檻、觸發計算 | :255-259 |
| H-22 | 🔄 強制重抓 | 繞過快取 | :574 |
| H-23 | 外幣（USD ETF）FX 換算；匯率取不到者「未納入組合統計」 | 不 1:1 硬加 | `_fetch_usdtwd_spot`:91、:628（~~:104-133~~ 行號漂移更正） |
| H-24 | 🛰️ ETF 追蹤戰情室（核衛分流健檢；核心 80%／衛星 20% σ 分級／其他持倉） | ETF 逐檔健檢 | :641-754（`_compute_etf_warroom_row`） |
| H-25 | 🎯 核心／衛星配置 **vs regime 目標**（依總經位階的核心比例） | 看配置是否符合位階建議 | :755（`CoreSatelliteManager`、`_regime_core_sat_text`:71） |
| H-26 | ⚖️ 再平衡交易指令（買／賣、金額、建議股數） | 具體調整動作 | :822-882 |
| H-27 | 🏗️ 產業曝險上限檢查（單一 GICS ≤30%） | 集中度風險 | :884 |
| H-28 | 🔗 相關係數矩陣（近 1 年） | 分散度 | :888 |
| H-29 | 🧩 各檔 ETF 成分股明細 | 看穿持股 | :926 |
| H-30 | 🧬 持股 Overlap 矩陣（method radio） | 重複押注 | :946-950 |
| H-31 | 🎯 主動 ETF 弱勢度檢測 | 主動 vs 被動 | :1022 |
| H-32 | 📉 VaR | 風險值 | :1086 |
| H-33 | 📈 與 0050 累積報酬比較 | 基準比較 | :1173 |
| H-34 | 📐 效率前緣 | 風險報酬地圖 | :1233 |
| H-35 | 💰 配息日曆 × 年度現金流（含每月明細） | 現金流預估 | :1270-1383 |
| H-36 | 💰 配息稅後試算（二代健保＋綜所稅，稅率 selectbox） | 稅後現金流 | :1432-1438 |
| H-37 | 🍇 葡萄串領息（以持股評估月月領覆蓋；無持股則「生成提議」＋3 控制項） | 領息排程 | `grape_ladder.py::_render_propose_subtab`:408；:426-438 |
| H-38 | 壓力測試（Beta 缺值以 1.0 估） | 崩盤情境損失 | `etf_tab_portfolio.py`:1056（`calc_portfolio_stress_test` 呼叫；匯入在 :160；~~:159~~ 行號漂移更正） |

**E. 非 UI 但屬「持股」的出口**

| ID | 功能 | 目的 | 位置 |
|---|---|---|---|
| H-60 | 每日 LINE／Telegram 持股續抱／換股推播 cron（service account 讀 Sheet；兩個 env Sheet 皆讀持股與觀察清單。`gsheet_sa_reader.read_holdings` 於**單一 Sheet 內**聯集所有命名組合，以 normalize 後 ticker 去重、保留首見，同代號不同均價列丟棄並只 log；`_build_entries` 再對**兩個 Sheet 合併後的持股**以同一 normalize key 去重（只 log 代號、不標均價衝突），之後再做持股>觀察清單去重。重驗 @15cd8fff 成立，並補上跨 Sheet 去重一層） | 真正的「推播」 | `scripts/push_holdings_daily.py::_read_inputs`:111（~~:112~~ 行號漂移更正）；`gsheet_sa_reader.read_holdings`:92；`.github/workflows/push_holdings_daily.yml` |
| H-61 | `portfolio_analysis_bridge` 把持股寫成 session `etf_portfolio_rows`，餵葡萄串／`portfolio_linkage`（個股頁「已在你的 ETF 投組」banner）／`tab_sector_flow` | 舊 UI 內部管線 | `etf_tab_dividend_station.py`:158-166；`portfolio_analysis_bridge.py` |

#### 12.2.3 資料來源／service／資料層（項目 3）

| 功能群 | 路徑（新 UI） | 路徑（舊 UI） |
|---|---|---|
| 讀持股／觀察清單 | L3 `holdings_service::get_holdings`:213 → L3 `portfolio_binding_service::get_binding_state(ssot=True)`:100／`get_active_selection`:354 → L1 `gsheet_portfolio::list_portfolios／load_portfolio／list_stock_watchlists／load_stock_watchlist`（皆 `sheet_id=` 顯式、`raise_if_missing=True`） | L5 `_load_holdings_from_portfolio`（EX-PASSTHRU-1 直呼 L1）；legacy `_get_active_sheet_id`／`_get_active_stock_sheet_id`；`_names[0]`／`_snames[0]` |
| 綁定狀態 | `page_hold::load_binding`:1092 → `get_binding_state(ssot=True)` | status bar 與 manager：`get_binding_state()`（legacy 通道）、`_gsp._get_active_*` |
| 戰情表／digest／燈 | L3 `dividend_station_service::get_station_rows／build_station_digest／compute_portfolio_totals`（L2 `compute.etf.dividend_station`；L4 `ui.render.station_cards`） | **同一組 L3**（兩邊共用） |
| 換股建議／總經位階 | L3 `get_switch_in_candidates／build_switch_advice／get_station_macro`（`page_hold::load_switch`:1532、`load_macro`:884） | 同上 |
| 建議持股水位 | L3 `allocation_service::get_allocation`（`page_hold::load_allocation`:978；`build_position_cap_card`:2919） | 舊戰情室**沒有**此卡 |
| 壓測／VaR／配息現金流 | L3 `portfolio_deep_service::get_portfolio_stress／get_portfolio_var／get_dividend_cash_flow`（內含 L2 `calc_portfolio_stress_test`、L3 `dividend_tax_service`） | L5 `etf_tab_portfolio.py` **inline**（逐檔 `fetch_etf_price`→`quantile`→×總市值）＋L2 `calc_portfolio_stress_test`、`compute_etf_annual_cashflow` |
| AI | L3 `dividend_station_service::build_ai_summary`（`gemini_fn`＝`app_ai_service.gemini_call`）；`page_hold::load_ai_summary`:4087 | 同 L3，`gemini_fn` 由 `app.py` 傳入 |
| Sheet 寫入（CRUD） | **無**（page_hold AST 黑名單釘死唯讀，`tests/test_p04_hold_view.py::TestReadOnly`） | L1 `gsheet_portfolio::save_portfolio／delete_portfolio／save_stock_watchlist／delete_stock_watchlist／create_new_sheet`（L5 直呼） |
| 綁定寫入 | 👤 我的（`page_me`→L1 `oauth_state.apply_sheet_binding`／`set_active_selection`），**不在 💼** | `portfolio_binder::apply_active_sheet`→同一支 L1 契約；側欄另有 inline 複本（矩陣 §7 已列） |
| 排程推播 | 不存在於 UI | `scripts/push_holdings_daily.py`（SA）＋`gsheet_sa_reader` |

#### 12.2.4 涉及 Sheet／portfolio／watchlist／OAuth／AI／外部 API（項目 4）

| 項目 | Sheet | portfolio | watchlist | OAuth | AI | 外部 API |
|---|---|---|---|---|---|---|
| 新 💼 持股讀取（H-01 對應） | 是（讀） | 是（讀選定一本） | 是（讀選定一份） | 是（僅檢查登入／逾時；登入鈕在 👤） | 否 | 否（Sheet 之外） |
| 新 💼 戰情表／燈牆／VIX／換股／總經位階／水位 | 否 | 否 | 否 | 否 | 否（規則式；AI 另按鈕） | 是（yfinance／FinMind／TWSE 等逐檔週K、折溢價、VIX；經 L1） |
| 新 💼 ⑥ 壓測／VaR／配息 | 否 | 否 | 否 | 否 | 否 | 是（`fetch_etf_price／info／dividends`） |
| 新 💼 ⑦ AI | 否 | 否 | 否 | 否 | **是（付費 Gemini，按鈕才發）** | 是 |
| 舊 H-01…H-15 | 是（讀） | 是 | 是 | 是（就地登入 CTA） | H-14 是 | 是 |
| 舊 H-40…H-45 | **是（讀＋寫）** | 是（寫／刪） | 是（寫／刪） | 是 | 否 | 是（Drive API） |
| 舊 H-20…H-38 | 否（輸入來自 session；目標% **不存 Sheet**） | 間接 | 否 | 否 | H-37 無；（etf_tab_ai 已無呼叫） | 是 |
| H-60 cron | 是（SA 讀） | 是 | 是 | **否（SA，非使用者 OAuth）** | 是（選配 Gemini） | 是 |

#### 12.2.5 舊 UI 主要互動流程（項目 5）

1. **戰情室（H-01…H-15）**：切到「不使用」→ 頁籤「💼 我的持股戰情室」→ 進頁即自動讀 Sheet（無範圍選擇；`st.session_state['_station_holdings']`）→ 看持股預覽（空則就地綁定 H-04）→ 〔可按 🔄 重新載入〕→ 按「🚀 跑存股戰情室」（逐檔抓取＋換股建議）→ 讀 1️⃣ 結論卡 → 看 3️⃣ 戰情表（分 ETF／個股兩區）→ 點燈牆下左表任一列→右側展開該檔每盞燈＋兩張週線圖 → 看 80/20＋停利 → 看 4️⃣ 換股 → 〔展開 5️⃣ 組合深度分析→按「📊 計算組合」→逐段看 ETF 組合結果（H-20…H-38）；葡萄串另有按鈕〕→ 看 6️⃣ 規則式摘要（直接顯示代號）→ 〔按「✍️ 讓 AI 潤成推播文字」〕。
2. **組合管理（H-40…H-45）**：頁籤「📁 組合管理」→（未登入：被指向側欄登入）→ 從 Drive 挑 Sheet／新建 → ✅ 使用 → 左欄選組合→📂載入→在 data_editor 改→命名→💾儲存 ／🗑️→✅確認刪除；右欄觀察清單同理。
3. **綁定（H-04／H-50）**：任何頁標題下 popover →（未登入）用 Google 登入 → Drive 挑選／貼 URL → 綁定；戰情室空狀態同一個元件（`render_holdings_binder`）。
4. **ETF 組合（H-20…H-38）**：持股由 H-61 bridge seed → 填「目標比例%」（不存 Sheet）→ 調容忍度 → 📊 計算組合 → 一長頁各區塊（核衛戰情室→regime 目標→再平衡指令→產業曝險→相關→成分股→Overlap→弱勢→VaR→0050 比較→效率前緣→配息日曆→稅後）。

#### 12.2.6 新 UI 現況與 Old→New Interaction Coverage 表（項目 6；複驗更正已套用）

> **Dead-end 欄的區分標準（複驗要求明文寫出）**：「是」＝卡片或指路句指到**錯的／新版模式不存在**的地方（例：葡萄串卡寫「既有的 🏦 ETF 分頁」，實際在戰情室 expander 內）；「半」＝只有純文字指路、無可點入口，或指向舊版但未說怎麼切回；「否」＝沒指路（資訊靜默只在舊版）或不適用。因此「是」只有 H-37 一列，**不代表其他列沒有問題**。

圖例（DEC-085 §19.6 四種正式狀態，一字不改）：`✅ 已覆蓋`｜`🟡 部分覆蓋`｜`⬜ 未覆蓋`｜`🚫 明確不再需要／不應搬入`。表內「Coverage」格只放上述四態之一的圖示（圖示旁以本圖例對照文字；顏色不是唯一資訊）；**「待客戶裁示」不是狀態**，只以 `【decision-note：待客戶裁示 S#】` 寫在說明欄（S# 見 §12.5，為 Stage B 前置候選問題）。🚫＝AI 盤點建議不搬／不應搬入，**最終認定屬客戶；不構成任何舊 UI 刪除授權**；「不是 UI 能力」**不是** 🚫 的理由。Dead-end：**是**＝新頁叫使用者去新版模式看不到的地方／指到不存在的控制項；**半**＝只有純文字指路、無可點入口，或指向舊版需自行找到「不使用」radio；**否**。

**重驗 @15cd8fff（本節三張表）**：所引 `page_hold.py` 符號行號（`load_*`、`build_*_card`、`_render_*`、`DEEP_SPECS`:3007、`NOT_BOUND_WHY`:1737、`ACTION_RUN_WARROOM_LABEL`:443、`AI_SUMMARY_LABEL`:3950）與舊 UI 各檔符號行號已逐一實測；有出入處已在該列用刪除線更正。

**新頁的入口形態**：葉1 戰情室（①結論三卡→②兩套刻度→③燈牆＋VIX→④換股＋總經位階→⑤80/20＋停利＋建議持股水位→⑥六格→⑦AI）／葉2 組合設定（綁定卡、組合數卡、持股列預覽、2 張未接線卡）；頁首表單 `form_holdings_view`（radio：只讀市場端／加讀 Google Sheet）。新版側欄入口：`🆕 新版戰情室（試用中）`→「💼 我的持股」（`app.py::_ia_view_hold`:615）。

**6.1 戰情室（H-01…H-15）**

| 舊功能 | 舊入口 | 新 UI 現況（含理由） | 新入口候選 | Coverage | Dead-end | 資料來源 | 風險／限制 |
|---|---|---|---|---|---|---|---|
| H-01 自動載入持股 | `etf_tab_dividend_station::_load_holdings_from_portfolio` | 表單選「加讀 Google Sheet：綁定狀態＋你的持股清單」＋🚀 才讀（`load_holdings`:1236）；**只讀 👤 我的選定的一本組合／一份觀察清單**（`get_holdings`:213；Q7 取消「名稱排序第一本」）[F]。理由：能力在，但行為已依 DEC-083 變更；預設 radio 為「只讀市場端」（第一項），不改選就全灰 [F] | 現位置即可 | ✅ | 半（未選定時只有文字指向「👤 我的 › 這本 Sheet 內容」，無按鈕） | L3 `get_holdings` | 見 §10-a、§12-3；複驗更正（C-6）：預設 radio 為「只讀市場端」（`SCOPE_OPTIONS` 第一項）＝不改選就不讀持股；舊版**沒有「選定」概念**，且舊版 ETF 通道含 secrets 部署預設路徑（見 R2）；💼 葉1 戰情室**完全不寫「正在分析哪一本組合／哪一份觀察清單」**（`portfolio_name`／`watchlist_name` 僅出現在葉2 預覽卡 facts），舊版唯一的揭露「此 Sheet 有多本組合，只取第一本」也已不在 → DEC-083 Q7「不可見業務決策」精神下的可見性缺口（複驗新增） |
| H-02 持股預覽（含 類別 核心/衛星） | `_holding_preview_row` | 葉2 `build_holdings_preview_card`:4459＋`_render_holdings_preview`:5398；欄位 代號／名稱／種類／張數／均價／來源；**無「類別」欄** [F]（類別資訊改進 ⑤⑥ 核心／衛星卡） | 同頁 | 🟡 | 否 | L3 `get_holdings` | 缺值顯示「—」非 0（符合 §1） |
| H-03 🔄 重新載入 | `render_dividend_station`:142 | 💼 **無**重新載入鈕；`holdings_service.py` 檔頭明寫不呼叫 `clear_read_cache()`（重驗 @15cd8fff，:38）；重按 🚀 可能在 L1 TTL（15 分）內拿到舊值 [I]；👤 我的有「🔄 重新讀取」（只失效本人×active Sheet） [F] | 💼 葉2 加導覽至 👤；或 💼 加讀取鈕（須線框） | 🟡 | 半（💼 無任何一句告訴使用者「要重讀請去 👤 我的」）[F]* | L1 `gsheet_portfolio` 快取；L3 `reload_my_sheet_reads` | 舊全域 `clear_read_cache()` 照留（BACKLOG `SHEET-GLOBAL-CLEARS`）。*此條 grep：`grep -n "重新讀取" src/ui/views/page_hold.py` 0 行（重驗 @15cd8fff 仍 0）；【decision-note：待客戶裁示 S25】 |
| H-04 缺 Sheet 就地綁定 | `render_dividend_station`:167-188 | 💼 刻意不放；`_not_bound_note`:1778 指路「👤 我的」（`SHEET_UNBOUND_WHERE`） [F]。理由：DEC-083 Q1 綁定唯一入口在 👤 | 指路句改可點入口（見 §7） | 🟡 | 半 | `page_me`／L1 `oauth_state` | 入口只是文字，無 `page_link`／`switch_page`（重驗 @15cd8fff：全 repo grep 0 命中） |
| H-05 🚀 跑戰情室 | :196 | `_render_holdings_form`:5170（`single_submit_form`，label `ACTION_RUN_WARROOM_LABEL`:443） | — | ✅ | 否 | — | 新增 radio「只讀市場端／加讀 Sheet」為新控制項（已存在） |
| H-06 結論三卡＋總損益／總市值 | `_render_layer1`:322 | `build_conclusion_cards`:2214（該做什麼／訊號可信度／需要處理）；損益／市值在「該做什麼」卡 facts（`_totals_facts`:2011） | — | ✅ | 否 | L3 digest／totals | 兩邊都只給**檔數**，不點名代號（見 H-14） |
| H-07 **逐檔戰情表**（現價／損益%／市值／健檢／235／加碼金／3-3-3／建議動作） | `_perf_row`:55、:243-252 | **新頁沒有**。燈牆只畫燈格 glyph＋N/M；預覽表無現價與損益；逐檔損益只出現在「衛星停利」命中者 [F]（~~`grep "加碼金 或 損益%" page_hold.py` 非註解命中僅停利卡與 digest 計數~~ 重驗 @15cd8fff 更正：「加碼金」於 `page_hold.py` 0 命中；「損益%」非註解命中僅在 `build_take_profit_card`〔:2813 起，約 :2817–2871〕，digest 計數〔`add_n`〕不含這兩個字串） | 葉1 ③ 區（逐檔表）— 候選，須線框 | ⬜ | 否（新頁沒指任何地方）；但**資訊只在舊版** | L3 `get_station_rows` rows | **最大功能縮水**；「建議動作」「加碼金」是投資語意輸出（§10）；【decision-note：待客戶裁示 S21】 |
| H-08 VIX | :236 | `build_vix_card`:2330 | — | ✅ | 否 | L3 `fetch_vix` | 缺值走 L0 缺值語彙 |
| H-09a 燈牆＋圖例 | `render_light_wall`／`render_legend`（L4） | `_render_light_wall`:5301，同一支 L4 [F]。**燈名只在 `title=`（桌機 hover）**；L4 自己註解「手機沒有 hover，故明細面板必須把同樣的話再講一次」 | 同頁 | 🟡 | 否 | L4 `station_cards` | 手機上只有 glyph 條，看不出每格是哪盞燈／值多少 [F+I] |
| H-09b 選列展開逐盞燈明細＋2 張週線圖 | `_render_light_detail`:461 | **刻意未做**（`_render_light_wall` docstring:5310-5313：新增互動元件須先過 A-8 草稿） [F]。（複驗更正）：客戶 2026-09-05 拍板之線框 `docs/wireframes/stock_ia_v1.html`（DEC-017）葉1 ③ 已含「點任一檔，右側展開週線與布林 z」（重驗 @15cd8fff：該句位於 `stock_ia_v1.html` 第 860 行〔葉1 ③ 的 `live:` 文案〕；~~html 約 770、859–861 行~~ 更正：770 行附近是葉2「指標明細」的類似句，不是葉1 ③；DEC-017 日期 2026-09-05、決策者客戶，見 `docs/DECISIONS.md`）；`page_hold.py` 檔內「新增互動元件須先過 A-8 草稿」的說法是否仍適用，**待總管／客戶確認（本節不認定）** | ③ 區 `st.dataframe(on_select)`＋明細面板（線框已有，待確認可否直接施工，見左欄） | ⬜ | 否 | L4 `render_holding_detail`、`station_charts`；L3 row `_detail`／`KEY_WEEKLY_SERIES` | 是 H-09a 可解釋性的前提；「不只靠顏色」需此面板補；【decision-note：待客戶裁示 S21】 |
| H-10 80/20＋衛星停利 | :572 | `build_allocation_split_card`:2747、`build_take_profit_card`:2813 | — | ✅ | 否 | L3 `compute_allocation_split／flag_take_profit` | 80/20 與停利門檻 L0 `dividend_station_thresholds`（§10） |
| H-11 兩套刻度 | `render_two_scales` | `build_scale_card`:2228＋`_render_scale_tables`:5338 | — | ✅ | 否 | L0 `station_specs` | 新頁另標 degraded（`KEY_STOCK_TREND` `discriminative=False`） |
| H-12 換股建議＋總經位階 | :628 | `build_switch_card`:2432＋`build_macro_stage_card`:2602 | — | ✅ | 否 | L3 | 換出／換入規則在 L2／L3（§10） |
| H-14a 規則式摘要：汰弱代號＋建議動作 | `_render_ai_summary`:682 | 汰弱換出代號在 ④ 卡 facts；**未單獨成區** | — | ✅ | 否 | L3 digest | — |
| H-14b 規則式摘要：**235 加碼觸發代號＋加碼金**、抓取失敗代號清單 | :686-692 | 新頁只有**檔數**（`add_n`／`err_n`，`StationReadout`）；**加碼金額與規則式文字**只存在於 AI digest（`digest["adds"]` 只在 `load_ai_summary` 傳入 AI）；代號可從燈牆讀出但無文字說明，抓取失敗代號亦同 [F]（複驗更正） | ① 區卡 facts 或 ③ 逐檔表（H-07） | ⬜ | 否 | L3 `build_station_digest` | **Data≠AI 問題**：規則式事實被藏在 AI 按鈕後面（舊版是永遠先出）；【decision-note：待客戶裁示 S21】；複驗補：未接 AI 金鑰時，舊版規則式摘要仍是推播內容來源（`etf_tab_dividend_station.py::_render_ai_summary` :682-694），新 💼 無金鑰時只剩紅卡／錯誤、沒有規則式摘要可看（強化嚴重度） |
| H-14c ✍️ AI 潤稿 | :698 | `⚡ 生成 AI 總結`（`_render_ai_button`:5258；`AI_SUMMARY_LABEL`:3950）；不存 session、無複製鈕、下次互動即消失（刻意）[F] | — | 🟡 | 否 | L3 `build_ai_summary`；付費 Gemini | 卡名寫「唯一推播出口」，但頁上**沒有任何推播動作**（真推播是 cron H-60）[F]；§12-5；【decision-note：待客戶裁示 S11】 |
| H-15 目標配置註腳 | :291 | 分散於 ⑤ 卡 facts | — | ✅ | 否 | L0 | — |

**6.2 ETF 組合（H-20…H-38，現僅在舊戰情室 expander 內）**

| 舊功能 | 舊入口 | 新 UI 現況 | 新入口候選 | Coverage | Dead-end | 資料來源 | 風險／限制 |
|---|---|---|---|---|---|---|---|
| H-20a 範例列 fallback（0050／00713／BND／00878 無持股時顯示） | `etf_tab_portfolio`:218-227 | 新頁拒絕範例持股（`NOT_BOUND_WHY`:1737「本站不拿範例持股頂替」） | — | 🚫 | 否 | — | 理由（非「不是 UI 能力」）：§1 不拿範例頂替真實持股；新頁已明文拒絕（`NOT_BOUND_WHY`:1737 實測存在）；AI 盤點建議不搬，最終認定屬客戶、不構成舊 UI 刪除授權；複驗（C-7）補：舊碼 `etf_tab_portfolio.py` 約 195–227 行明示「未載入時才退回範例列供試玩」——舊版用途＝新手試玩；新頁**刻意取消試玩入口**，供客戶知悉（不改 Coverage） |
| H-20b 手動微調持股列（session 內，不存 Sheet） | `etf_tab_portfolio`:232 | 無 | 屬持股列 CRUD → P2 | ⬜ | 半（卡片只說「切回舊版 → 📁 組合管理」，而 H-20b 不在 📁 組合管理，在 🏦 戰情室 expander） | session | 兩處編輯入口（組合管理 vs 組合分析 editor）語意不同、皆不回寫（§9）；複驗補：該 data_editor 也允許手打任意標的（含不在 Sheet 的海外 ETF，如 BND／VOO）做**假設性試算（what-if）**，用途不同於「持股列 CRUD」，不應全併入 P2 |
| H-20c 目標比例%（每檔，session 內不存 Sheet） | `etf_tab_portfolio`:244-250 | 新頁 ⑥ 再平衡卡明寫**缺這個輸入**（`DEEP_SPECS`:3009）；Sheet 欄位只有 name／ticker／lots／avg_price／updated_at（`page_hold.py` 檔頭） | 新輸入元件＋持久化位置 | ⬜ | 半（卡上無「去舊版」指路，只有 `NO_EXIT_MARKER`） | 無 | 【decision-note：待客戶裁示 S3】（輸入元件＋是否存 Sheet＝寫入） |
| H-21a 再平衡容忍度 slider（混合格拆列） | `etf_tab_portfolio`:255（`st.slider`） | 無 | 跟 H-26 | ⬜ | — | L0 `PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT` | 隨 H-26 再平衡一起缺；【decision-note：待客戶裁示 S3】 |
| H-21b 📊 計算組合按鈕（混合格拆列） | `etf_tab_portfolio`:259（`st.button`） | 新頁以 `form_holdings_view` 的「🚀 跑存股戰情室」gate 觸發計算（`_render_holdings_form`:5170） | — | ✅ | — | — | ~~原標 🚫（被表單取代）~~（更正原因：「被等價控制項取代」＝該互動已被覆蓋，標 ✅ 較貼 §19.6 定義；限定：僅限「觸發運算」的 gate——🚀 觸發的是戰情室與 ⑥ 三格，不觸發 ETF 組合 H-24…H-36 的分析內容；此鈕所觸發的 ETF 組合內容之覆蓋另見 H-24…H-36，不因此鈕 ✅ 而算已覆蓋） |
| H-22 🔄 強制重抓 | :574 | 無 | 跟 H-03 | ⬜ | 半 | — | 【decision-note：待客戶裁示 S25】 |
| H-23 外幣／FX 處理 | `_fetch_usdtwd_spot`:91、:628（~~:104-133~~ 行號漂移更正） | ⑥ 三格**只有台幣口徑**，海外標的排除（`portfolio_deep_service` 已知限制 2、配息 §4.6） | — | 🟡 | 否 | L1 | 新頁已在卡面揭露；FX 規則未搬 |
| H-24a ETF 追蹤戰情室：ETF 逐檔健檢（複驗 C-5 拆列） | `etf_tab_portfolio.py` 約 641–754 行（`_compute_etf_warroom_row`） | 戰情表走 `dividend_station` 的 ETF 健檢 A–D＋235＋3-3-3（另一套引擎） | — | 🟡 | 否 | 舊：L2 `_compute_etf_warroom_row`；新：L2 `dividend_station` | **同一頁舊 UI 內有兩套 ETF 健檢引擎**（§12.2.9 第 4 項） |
| H-24b ETF 追蹤戰情室：衛星 σ 分級五階買點／核心總報酬 vs 殖利率（複驗 C-5 拆列） | 同上 | **無對應** | — | ⬜ | 否 | 同上 | 複驗：原組 🟡 偏寬，σ 五階買點（MA20±σ）與核心的總報酬／殖利率欄在新頁皆無對應；買點屬買賣語意（§12.2.10）；【decision-note：待客戶裁示 S22】 |
| H-25 核衛 vs **regime 目標** | :755 | 新 ⑥「核心／衛星」只算固定 80/20（L0）；`page_hold` 檔頭明言**不採** `CoreSatelliteManager`（依位階 0.60–0.85）[F] | — | 🟡 | 否 | 舊：`compute.strategy.portfolio_manager.CoreSatelliteManager` | **舊 UI 自己就有兩個核心比例**（戰情室寫死 80%／regime 目標）→ 【decision-note：待客戶裁示 S12】（§11-2） |
| H-26 ⚖️ 再平衡交易指令 | :822 | `hold.deep.rebalance` 未接線卡（`DEEP_SPECS`:3007 起，該卡 key 在 :3009；~~:3008~~ 行號漂移更正） | 見 H-20c | ⬜ | 半 | L2 `portfolio_gates.evaluate_rebalance_gate` | 具體買賣股數／金額＝投資語意（§10）；【decision-note：待客戶裁示 S3】 |
| H-27 產業曝險 ≤30% | :884 | 無（`grep "產業曝險 或 GICS" page_hold.py` 0 行） | ⑥ 新格 | ⬜ | 否 | `_check_sector_exposure`（L4） | 30% 上限是門檻（§10） |
| H-28 相關係數矩陣 | :888 | 無 | ⑥ 或現行 nav「🔬 查一檔」 | ⬜ | 否 | `_plot_correlation` | — |
| H-29 成分股明細 | :926 | 無 | 現行 nav「🔬 查一檔」（ETF）較適合 [I] | ⬜ | 否 | `render_etf_holdings` | 歸屬待 IA Decision Gate（🎯 標的 vs 🛡️ 持股兩個責任方向；DEC-085 §19.2）；【decision-note：待客戶裁示 S22】 |
| H-30 Overlap 矩陣 | :946 | 無 | ⑥ | ⬜ | 否 | `build_holdings_overlap_matrix` | 跨市場量不到→需標「無法判定」 |
| H-31 主動 ETF 弱勢度 | :1022 | 無 | ⑥ | ⬜ | 否 | `compute_etf_weakness_row` | — |
| H-32 VaR | :1086 | `build_var_card`:3551（L3 重寫版，已揭露覆蓋率與台幣口徑） | — | ✅ | 否 | L3 `get_portfolio_var` | **與舊版為兩份實作**（§9-3）；95／99% 分位為數學常數 |
| H-33 與 0050 累積報酬比較 | :1173 | 無 | ⑥ | ⬜ | 否 | L2 `compute_portfolio_vs_benchmark` | — |
| H-34 效率前緣 | :1233 | 無 | ⑥ | ⬜ | 否 | — | — |
| H-35 配息日曆×年度現金流 | :1270 | `build_dividend_cash_card`:3682（年度總額；**無逐月明細**） | ⑥ 展開區 | 🟡 | 否 | L3 `get_dividend_cash_flow` | 不含綜所稅（卡面已講） |
| H-36 配息稅後試算（稅率 selectbox） | :1438 | 只算二代健保（`marginal_rate=None`） | 新輸入元件（A-8） | 🟡 | 半（無指路到舊版稅率入口） | L3 `dividend_tax_service` | 稅率是使用者輸入＝新控制項；已在檔頭承認未拍板 |
| H-37 🍇 葡萄串領息 | `grape_ladder.py`:408-438 | `hold.deep.grape` 未接線卡；`facts`「現行入口：既有的 🏦 ETF 分頁」（新版模式看不到）[F] | 實作重構後掛載（§8.4 step 4 scope） | ⬜ | **是**（指向新版模式不存在的分頁；BACKLOG `ME-OLD-TAB-POINTERS`） | session `etf_portfolio_rows` | 舊版 葡萄串吃的 session 只有舊戰情室會寫 [F]；複驗：卡面字串確認（`DEEP_SPECS` 的 `hold.deep.grape` facts「現行入口 / 既有的 🏦 ETF 分頁」）、指路錯誤確認（實際只掛在戰情室 expander 5️⃣）、新版模式看不到確認；**v2 卡面短句**（`_v2_rows_for("hold.deep.grape")`）只摘「實作住在 L5／自帶寫死 widget key」，**不含**「🏦 ETF 分頁」錯誤指路 ⇒ 同一張卡在 v2 版面與完整版面說法不一致，使用者預設看到哪一版（複驗：無法確認，INFERENCE）；重驗 @15cd8fff：`_render_propose_subtab`:408、3 控制項〔2 slider＋1 checkbox〕:426-438 成立；【decision-note：待客戶裁示 S3】 |
| H-38 壓力測試 | `etf_tab_portfolio`:1056（~~:159~~ 行號漂移更正；匯入在 :160） | `build_stress_card`:3446 | — | ✅ | 否 | L3 `get_portfolio_stress`（共用 L2 `calc_portfolio_stress_test`） | Beta 缺值以 1.0 估（新頁卡面揭露＋降級；§10） |
| etf_tab_ai（ETF AI 首席策略師） | `etf_tab_ai.py::render_etf_ai` | 無 production 呼叫 [F]（`app.py`:41 註解稱已由戰情室 AI 等價取代） | — | 🚫 | 否 | — | 理由：舊 UI 本身也無入口（`render_etf_ai` 無 production 呼叫）；「已由戰情室 AI 等價取代」只是 `app.py`:41 的註解宣稱，等價性為 **INFERENCE／未複驗**；AI 建議不搬，**最終認定屬客戶，不構成任何舊 UI 刪除授權**（不屬本輪動工，§-1）。驗證方式：@15cd8fff 重跑 `git grep render_etf_ai`（排除 tests／docs），僅剩定義、`etf_dashboard.py:57` re-export 與註解；~~單組 grep，未查動態載入~~（2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；依圖例補第二種獨立證據，重驗 @15cd8fff）：(i) `git grep render_etf_ai`／`etf_tab_ai`（排除 docs、*.md）僅剩定義、`etf_dashboard.py:57` re-export、`src/ui/etf/__init__.py` 模組清單、`app.py` 註解（:41、:209）、其他檔註解與測試的文字引用；(ii) `tests/test_etf_smart_ticker_wiring.py:90` 反向斷言 `render_etf_ai(gemini_fn=gemini_call)` 不得出現在 `app.py`（呼叫已於 P3 v19.202 搬離）；(iii) `src/`、`app.py` 對 `importlib`／`__import__`／`getattr(` 搭配 `render_etf` 的搜尋 0 命中。限制：`git log -S` 在本 worktree 找不到移除 commit（歷史不足）；字串拼接式動態呼叫無法完全排除（INFERENCE，機率低）；「已由戰情室 AI 等價取代」仍未複驗、不得引用，🚫 僅依「舊 UI 亦無入口」。與 12.3 C-29 同一函式、判定一致 |

**6.3 組合管理／綁定／狀態列（H-40…H-50）**

| 舊功能 | 舊入口 | 新 UI 現況 | 新入口候選 | Coverage | Dead-end | 資料來源 | 風險／限制 |
|---|---|---|---|---|---|---|---|
| H-40 Drive 列出／選一本／✅使用 | `portfolio_binder::render_drive_picker`:103（~~:112~~ 行號漂移更正） | 👤 我的 卡②（PR #927）；💼 只指路 | 💼 可點入口 → 👤 | ✅ | 半（💼 側純文字；覆蓋位置在 👤 我的，非 💼） | L1 `list_user_sheets`、`apply_sheet_binding` | 與 `portfolio_binder`／側欄為 3 份 UI（§9-1） |
| H-41 🆕 建立新投組 Sheet | `portfolio_binder`:129（~~:134~~ 行號漂移更正） | 無；ME-P2 未授權 | P2 | ⬜ | 半（💼 無對應指路；只有 👤 的客戶 D 段句） | L1 `create_new_sheet` | ⚠️ 寫使用者 Google Drive（High）；本輪不提實作 |
| H-42 顯示目前 Sheet 兩通道（同一本／兩本不同） | `portfolio_manager`:140-146 | 💼 `ACTIVE_DIVERGED` 灰卡；👤 我的顯示 | — | ✅ | 否 | L3 `get_active_sheet` | 💼 不顯示 Sheet 名稱＋末 6 碼（只顯示「有沒有綁」）|
| H-43a 選定要分析哪一本組合 | manager selectbox:179（僅載入編輯，**並不影響戰情室**；戰情室取第一本） | 👤 我的 卡③ selector（Q7） | 💼 指路 | ✅ | 半 | L1 `oauth_state.set_active_selection` | 舊 UI **沒有**「選定分析哪本」概念，是新能力 |
| H-43b 載入組合到編輯器／編輯／💾儲存／🗑️刪除（兩段確認） | `_render_etf_section`:162 | 💼 卡片：「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」（客戶逐字句，`ia_nav.CONTENT_EDIT_OLD_UI_WHERE`:124） | P2 | ⬜ | 半（句子未告訴使用者**怎麼**切回：側欄 radio「不使用（用下方原功能）」；該步驟只寫在 👤 我的 `SWITCH_BACK_TEXT`:197） | L1 CRUD | 寫入／刪除＝High；刪除屬不可重建 |
| H-44 觀察清單 載入／儲存／刪除 | `_render_stock_section`:231 | `hold.setup.watchlist` 未接線卡，同上句 | P2 | ⬜ | 半（同上） | L1 | 同上 |
| H-45 Sheet API 錯誤白話分類 | `_classify_sheet_api_error`:43 | `sheet_read_issue`／`_schema_mismatch_where`:4345／登入逾時灰卡；**未見 429 配額的白話提示** [F複驗更正：`page_hold.py` 只對 `schema_mismatch` 分流；L1 `classify_read_error`（`gsheet_portfolio.py` 約 735–770 行）**已有** `READ_ERROR_QUOTA_EXCEEDED`，👤 我的（`me_account_service.py` 約 245 行）有使用，💼 沒接——資料已有、只是 💼 沒接] | — | 🟡 | 否 | L3 `sheet_read_issue` | 配額用罄會被分類成「讀取失敗」紅卡，指路是「確認網路與 Google 授權」（`STATION_ERROR_WHERE`:1949），不是「等 1 分鐘」[I]；【decision-note：待客戶裁示 S25】 |
| H-50 全域🔗狀態列 popover | `portfolio_status_bar::render_portfolio_status_bar`:30（~~:48~~ 行號漂移更正） | 新版模式 `app.py:687` 在 `st.stop()`〔:675〕之後不畫；各新頁各自畫綁定卡 | 側欄／頁首跨頁 chip（須線框） | 🟡 | 否 | L3 `get_binding_state` | 矩陣 §4 已列「跨頁狀態列」未接；複驗補：舊 popover 內直接顯示**完整 Sheet ID**（`portfolio_status_bar.py`:92，`_render_bar_body`；~~約 131–133 行~~ 行號漂移更正），新頁刻意只露末 6 碼——資訊面的揭露差異，非缺陷；【decision-note：待客戶裁示 S26】 |
| H-61 `etf_portfolio_rows` bridge（把持股帶進分析頁的內部管線） | `portfolio_analysis_bridge` | 新頁不寫；現行 nav「🔍 找標的」（`page_find`）的持股標示已改讀 `holdings_service`（`page_find.py` 註解:448，重驗存在）＝**只有這一個下游**已換。其餘下游仍吃此 session key（重驗 @15cd8fff：`git grep etf_portfolio_rows`）：`grape_ladder.py`:410（H-37）、`etf_tab_portfolio.py`:200（H-20 seed）、`portfolio_linkage.py`:54（個股頁「已在你的 ETF 投組」banner，`tab_stock.py`:572-573 呼叫（~~:575~~ 更正：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；重驗 @15cd8fff：572 import、573 呼叫、575 為 except 內 print））、舊 `tab_sector_flow.py`:24 | 隨 H-37／H-20 的掛載方案決定 | 🟡 | 否 | — | ~~原標 🚫：「舊管線，已被 `holdings_service` 取代」~~（更正：只對 `page_find` 一個下游成立；其餘下游的使用者可見能力〔葡萄串、ETF 組合 seed、個股頁 banner〕在新 UI 仍未覆蓋，不能整條判「不應搬入」；若下游日後都改讀 `holdings_service`，此管線才可能變成「不再需要」，該認定屬客戶）；【decision-note：待客戶裁示 S3／S22】 |
| H-60 每日 LINE 推播 | `scripts/push_holdings_daily.py` | 新 UI **沒有任何入口或揭露**：cron 不受新／舊 UI 切換影響、照常執行；`page_me.KNOWN_LIMITS` 的一句「排程推播讀的是部署環境的設定，與本頁選哪一本無關」（重驗 @15cd8fff 存在）是唯一揭露，💼 本頁沒有 | 見 §12.4／S11（候選：檢視／揭露；是否做屬客戶） | ⬜ | 否 | SA | ~~原標 🚫：「非 UI 能力、不由新頁觸發」~~（更正：「不是 UI 能力」不是 🚫 的容許理由；cron 本體不是 UI 項目，但使用者目的〔知道每天推了什麼、推播讀哪本〕在新 UI 沒有對應入口或說明，故依「新 UI 是否覆蓋此使用者目的」標 ⬜）。**這不是要在 UI 新增推播功能的提議**，cron 不得因整理 UI 而動；與「AI 推播出口」命名衝突見 §12-5；cron 讀法見 §12.4（單 Sheet 內聯集去重、丟棄衝突均價列，不是「攤平」）；【decision-note：待客戶裁示 S11】 |

**Coverage 計數（本輪以腳本逐列重數第 5 欄，三張表合計；H-21 混合格已拆成 H-21a／H-21b，狀態格已無混合格）**：✅ 15｜🟡 13｜⬜ 21｜🚫 2（合計 51）。~~原計數 ✅ 14｜🟡 12｜⬜ 20｜🚫 4（合計 50）~~（更正：原計數可重現；變動＝H-21 拆列〔⬜＋✅，+1 列〕、H-60 🚫→⬜、H-61 🚫→🟡；現存 🚫＝H-20a、etf_tab_ai）。原計數未經第二組複驗；本輪重數仍為單組，且 H-21b／H-60／H-61 的新判定屬 AI 盤點建議，最終認定屬客戶。

#### 12.2.7 未覆蓋項：新 UI 候選落點與 dead-end（候選，非設計決定）

> 下表「💼 葉1 ③」等落點，指**現行程式碼目前掛在** `page_hold`（現行 nav：新版模式「💼 我的持股」）的區塊，僅供盤點定位；🛡️ 持股責任方向與各 view 的對映屬後續 IA Decision Gate（DEC-085 §19.2），**本表不以「程式碼目前掛在哪頁」斷言歸屬已可判定**。每個缺口搬不搬、搬到哪，均為 Stage B 前置候選問題／decision-note（S 項見 §12.5），不是本表的決定。

| 缺口 | 候選落點（現行 nav 暫代，非歸屬認定） | Dead-end 形態 |
|---|---|---|
| H-07 逐檔表（含損益／建議動作／加碼金） | 💼 葉1 ③「戰情表」區 | 無 dead-end，但**資訊只在舊版**（新頁沒有任何指路句） |
| H-09b 逐盞燈明細＋週線圖 | 💼 葉1 ③ | 無；但 H-09a 在手機上不可解釋 |
| H-14b 加碼觸發代號／加碼金、抓取失敗名單 | 💼 ① 卡 facts 或 ③ 逐檔表 | 無 |
| H-03／H-22 重新載入 | 💼 葉2 導覽至 👤「🔄 重新讀取」（文字或可點） | **半 dead-end**：💼 全頁 0 句提到重讀 |
| H-04／H-40 綁定、H-01 選定 | 💼 指路句改可點入口（現為純文字）。⚠️ `st.page_link`／`switch_page` 在本 repo 0 命中，且導覽是 `app.py` 側欄 radio（不是 multipage）→ 可點入口牽涉改 navigation＝UI 動線異動，須先出線框並經客戶 Gate（DEC-082 的 Stage A→B→C→D 中，**Stage C 才是正式客戶 Gate**）；歸屬對映另屬後續 IA Decision Gate，本盤點不決定 | **半** |
| H-26/H-20c 再平衡＋目標% | ⑥ 區新輸入元件＋（若要存）Sheet 欄位＝寫入 | **半**：未接線卡不指向舊版（舊版有此能力，session-only） |
| H-27…H-31／H-33／H-34 組合分析 6 格 | ⑥ 區或現行 nav「🔬 查一檔」（ETF）；歸屬待 IA Decision Gate | 無（新頁完全沒提到它們存在）；舊版入口 = 戰情室 expander |
| H-37 葡萄串 | ⑥ 掛載需先重構 L5 實作 | **是**：卡上寫「現行入口：既有的 🏦 ETF 分頁」，新版模式看不到（且該分頁其實是「💼 我的持股戰情室」expander 內，非 🏦 ETF 頁籤）[F：葡萄串只在 `etf_tab_dividend_station.py:283` 掛載] |
| H-36 稅率 | ⑥ 配息格新輸入（A-8） | 半 |
| 切回舊版步驟 | 💼 指路句補「側欄 › 不使用」（客戶逐字句不可改，可在句後補） | 半（只有 👤 說明） |
| H-41、H-43b、H-44（CRUD） | P2（未授權） | 半（客戶逐字句已誠實指路；不得再改） |

#### 12.2.8 目前仍只能切回舊 UI 的能力（項目 8）

1. 逐檔戰情表（現價／損益%／市值／建議動作／加碼金）— H-07
2. 點列展開逐盞燈明細與週K／布林走勢圖 — H-09b
3. 規則式 235 加碼代號／加碼金、抓取失敗清單（不經 AI）— H-14b
4. 🔄 全域快取重載（`clear_read_cache`，刻意保留）— H-03
5. ETF 組合 11 格：目標%／再平衡交易指令／regime 目標／產業曝險／相關／成分股／Overlap／弱勢度／0050 比較／效率前緣／配息逐月／稅率 — H-20…H-36
6. 葡萄串領息 — H-37
7. 建立 Sheet、組合與觀察清單 CRUD、持股列編輯 — H-41／43b／44（P2）
8. 全域🔗狀態列 popover — H-50
9. 429 配額白話提示 — H-45 [I]
10. 選股網「➕ 加入觀察清單」（盤點範圍標籤 🎯 標的，依現行 nav 暫代；現行位置＝舊版「🔬 選股」頁籤內的選股網，`app.py`:947-979〔重驗 @15cd8fff〕；附帶列出因為寫的是同一份觀察清單）— 【decision-note：待客戶裁示 S15】

#### 12.2.9 重複邏輯／重複入口／SSOT 是否被繞過（項目 9）

**讀取路徑（單組 grep，未窮舉；方法見 §12.2.0a；重驗 @15cd8fff：重跑後 R1–R8 涉及的檔案集合一致）**：

| # | 讀取者 | 讀哪本／哪份 | 是否走 DEC-083 SSOT（active Sheet＋選定名稱） |
|---|---|---|---|
| R1 | 新 💼／`sector_flow_service._active_selection_tickers`（現行 nav「🔍 找標的」`page_find` 的持股標示）| `holdings_service.get_holdings` → 選定一本 | ✅ 是 |
| R2 | 舊戰情室 `_load_holdings_from_portfolio` | legacy 兩通道；`_names[0]`／`_snames[0]` 名稱排序第一本 [F]（`gsheet_portfolio` 的 `_list_portfolios_names` 回 `sorted(names)`，複驗確認）。（複驗更正）：ETF 通道讀 `_get_active_sheet_id()`，**session 空時 fallback 到 secrets 部署預設**（`gsheet_portfolio.py` 約 164–181 行）；個股通道 `_get_active_stock_sheet_id()` **不 fallback**（約 184–193 行）；兩通道各讀各的，戰情室不檢查是否同一本 | ❌ 否（舊 UI，照留）。新 UI 的 `get_active_sheet`（`portfolio_binding_service.py` 約 310–336 行）把「兩格空＋有部署預設」判為 `ACTIVE_DEPLOY_DEFAULT_ONLY`＝未綁 ⇒ **舊戰情室可能讀一本新 UI 視為「未綁」的 Sheet**；DEC-083 E 段明令舊 UI 全留，故屬已知分歧、非違規，但須列入 Removal Gate 前的 Old→New mapping；【decision-note：待客戶裁示 S23】 |
| R3 | 舊 📁 組合管理 `_render_etf_section`／`_render_stock_section` | legacy 通道，使用者自選載入 | ❌ 否（舊 UI） |
| R4 | 舊狀態列 `get_binding_state()` | legacy（`ssot=False`） | ❌ 否 |
| R5 | `watchlist_service.add_picks_to_watchlist`／`get_watchlist_add_context`（選股網「➕ 加入觀察清單」）| `_get_active_stock_sheet_id()` legacy（不 fallback）；清單名由舊 UI 下拉選 | ❌ 否。（複驗更正）：**機制 [F]、使用者看到什麼 [I]**——`get_active_sheet` 的 `ACTIVE_DIVERGED` 含「其中一格空」（約 328–329 行），即**只綁了個股那一格**也算 DIVERGED；此時新 UI 沒有「顯示的那本」可對照（🛡️ 整頁當未綁），舊「➕」仍寫進個股通道那本。`ACTIVE_OK` 時 Sheet 相同，只剩「清單名與 👤 選定無關」。另：舊成功訊息「到 💼 戰情室按 🔄 重新載入即生效」只對舊 UI 成立。實機畫面（複驗：無法確認） |
| R6 | `scripts/push_holdings_daily.py` | env `PORTFOLIO_SHEET_ID`／`STOCK_PORTFOLIO_SHEET_ID`；每個 Sheet 都跑 `read_holdings` **與** `read_watchlist`；`gsheet_sa_reader.read_holdings`（約 92–121 行）**聯集所有命名組合並以 ticker（`normalize_ticker`，2330≡2330.TW）去重、保留首見**，同代號不同均價列被丟棄並只 log；`_build_entries` 再對兩個 Sheet 合併後的持股去重、再做持股>觀察清單去重（重驗 @15cd8fff）[F]。（複驗更正）：不是「攤平」，是「去重並丟棄衝突均價」；【decision-note：待客戶裁示 S11】 | ❌ 否（`page_me.KNOWN_LIMITS` 已揭露「排程讀部署設定，與本頁選哪一本無關」，但 💼 的 AI 卡名稱「推播出口」未揭露）。與 👤「選定一本」語意的差異是**資料丟棄**而非攤平 |
| R7 | `portfolio_manager.parse_sheet_id` | 委派 L0 `shared.sheet_id`（矩陣 §7.2 的 4 份解析已收斂為 1 份 L0）| ✅（委派；重驗 @15cd8fff：`parse_sheet_id` 本體呼叫 `shared.sheet_id.parse_sheet_input`，`git grep parse_sheet_id`〔`app.py src shared scripts`〕除定義外僅 docstring 提及，production 0 caller 仍成立（靜態 grep，未排除 getattr／字串動態引用））|
| R8（複驗新增） | `sector_flow_service._collect_stock_watchlist_tickers`（舊 `tab_sector_flow.py` 呼叫）；`portfolio_binding_service.py` 約 216 行直呼 `_get_active_sheet_id`；`me_account_service.py` 約 234–235 行為 👤 自己的讀取（合規） | 個股 Sheet **所有**觀察清單（不受 👤 選定影響） | ❌ 否（舊 UI／舊管線）；方法：`grep -rn "_get_active_sheet_id\|_get_active_stock_sheet_id\|list_portfolios\|list_stock_watchlists\|load_stock_watchlist"` 於 `app.py src scripts shared`（單組，非窮舉） |

**其他重複：**
1. **綁定 UI 三份**：側欄 inline、`portfolio_binder`（status bar／戰情室空狀態／組合管理）、👤 我的 `page_me`（新 UI，不重用 binder）；寫入契約已收斂為 L1 `apply_sheet_binding` 一支，但 **UI 元件是三份** [F]（`page_me.py::_render_sheet`:553／`_render_switch_sheet`:574 vs `portfolio_binder.py::render_drive_picker`:103／`render_holdings_binder`:166（~~:553-615／:112-185~~ 行號漂移更正））。
2. **持股讀取兩份**：L5 私有 `_load_holdings_from_portfolio` vs L3 `holdings_service`（`holdings_service.py` 檔頭自承並存、暫不併）。行為已分歧（Q7：舊取第一本、新取選定）。
3. **VaR／壓測／配息**：`portfolio_deep_service`（新）vs `etf_tab_portfolio` inline（舊）兩份；L3 檔頭自承「兩者暫時並存」；全站至少三處「張→股」乘法（`_lot_to_shares`、`compute_portfolio_totals`、`compute/sector_flow`；重驗 @15cd8fff：`portfolio_deep_service.py`:235、`dividend_station_service.py`:1145、`compute/sector_flow.py`:202）。
4. **ETF 健檢引擎兩套（舊 UI 內）**：`etf_calc._compute_etf_warroom_row`（組合分析）vs `dividend_station` ETF 健檢 A–D（戰情表），新頁只接後者。
5. **核心比例兩個定義（舊 UI 內）**：戰情室／ETF 組合標題「目標 80%」vs「regime 目標」（`CoreSatelliteManager` 0.60–0.85）。
6. **「重新載入／重新讀取」**：舊全域 `clear_read_cache()`、👤 本人限定、新 💼 無 → 三種語意。
7. **兩份「持有列編輯」**：📁 組合管理 data_editor（回寫 Sheet）vs ETF 組合 data_editor（session-only，不回寫）→ 使用者會以為在改 Sheet。
8. **「推播」一詞**：⑦卡名「唯一推播出口」vs 真推播 cron（H-60）。

#### 12.2.10 高風險投資語意（項目 10；Stage B 不得自行改定義；以下僅列位置與性質，不提議任何數值或公式）

> 以下**僅列位置與性質**，不提議任何數值／公式。

| # | 語意 | 位置 | 為何高風險 |
|---|---|---|---|
| a | 「誰是我的持股」＝只讀選定的一本；**未選定→整頁不分析**（含觀察清單，`load_holdings`:1276-1282）| `holdings_service::_pick`:182；`page_hold::load_holdings` | 規則由 AI 總管裁示（「沒選定→不分析」非客戶原文，見 DEC-083 說明）；影響所有下游 |
| b | 核心＝ETF、衛星＝個股的**近似**（主題 ETF 會被算成核心） | `holdings_service::_row`:191；L0 `classify_asset_kind` | 決定 80/20 與停利適用對象 |
| c | 80/20 目標、衛星停利門檻、VIX 三段門檻 | L0 `shared/dividend_station_thresholds` | 改值＝改投資規則 |
| d | 235 加碼燈、加碼金、3-3-3、健檢 A–D、財報體檢、KD、「建議動作」 | L2 `compute.etf.dividend_station`；`shared/station_specs` | 進出場／加碼語意；「🔴＝深水加碼」非體質差 |
| e | 汰弱＝換出、換入優先序（觀察清單綠燈→選股池）、總經攻守閘門（defensive 換入從嚴）| L3 `build_switch_advice` | 換股行為建議 |
| f | 建議持股水位／**系統風險上限（Risk Cap）**：新頁 `build_position_cap_card` 已實作且受 `risk_cap_gate` 守衛；DEC-083 G 段禁止「顯示 Risk Cap 正式數字」 | `page_hold`:2919；`risk_cap_gate.py` | Stage B 不得動顯示規則 |
| g | 再平衡：目標權重來源、容忍偏離度、買賣股數與金額 | `etf_tab_portfolio`:822；L2 `portfolio_gates.evaluate_rebalance_gate` | 具體交易指令 |
| h | regime 核心比例 0.60–0.85（`CoreSatelliteManager`）與固定 80/20 並存 | `etf_tab_portfolio`:755 | 兩個互相矛盾的核心比例 |
| i | 產業曝險上限 30% | `_check_sector_exposure` | 門檻 |
| j | 壓力測試：**Beta 缺值以 1.0 估**（L2）；VaR 95／99% 常態分位、月度 √N、最小樣本一個月；配息「不含綜所稅」、海外標的排除 | `calc_portfolio_stress_test`；`portfolio_deep_service` 常數 | 缺值補中性值；新頁以降級＋揭露處理，不得改成靜默 |
| k | PIT／look-ahead：本頁用即時現價與現持股，**無歷史重算**；前進式驗證凍結 `picks.parquet` 為不可重建歷史 | CLAUDE.md §2.3／§-1.5.F 判定 3(5) | 任何 GC／重建都不得碰 |
| l | AI 結論：AI 只潤稿、digest 為輸入；不存 session | `build_ai_summary`；`AI_DISCLOSURE` | Data≠AI；不可讓 AI 取代規則式事實 |
| m | 缺值語意：缺張數／均價＝`None`，不是 0；`keep_blank=True` | `get_holdings(keep_blank=True)` | 影響損益與 80/20 分母 |

### 12.3 ⚡ 行動（調查組 C＋獨立複驗 C；更正已套用）

> 範圍：~~新 UI **尚無 ⚡ 行動頁**~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；⚡ 是責任方向，非現行 nav 頁，DEC-085 §19.2）現行 nav 無對應頁（⚡ 為責任方向，見 §19.2）（`shared/ia_nav.py::PAGE_LABELS` 只有 📊大盤／🚦今天／🔍找標的／🔬查一檔／💼我的持股／📖憑什麼／👤我的；`grep -n "⚡" shared/ia_nav.py` 0 命中，複驗確認）。本節盤點舊 UI 中屬「現在需要採取什麼行動」的內容，並區分四類：**① 客觀市場／個股資料**、**② 規則判讀**（L2 規則算出的燈／結論，deterministic）、**③ AI 分析**（LLM 產出文字）、**④ 使用者真正可採取的動作**（button／輸入／會改變系統狀態的操作）。C-nn 為調查組編號（非 BACKLOG ID）；複驗新增 C-31～C-33。

> **基準**：程式碼＝main @ `15cd8fff`（4e6bf8ee→15cd8fff 僅 docs 變更，0 程式碼變更，已實測 `git diff --name-only`）。本節下文凡寫「量測於 4e6bf8ee」者，指原盤點的量測基準；其中的程式碼層級宣稱已於 15cd8fff 逐項重驗（見下「重驗總註」）。
>
> **責任名 vs 現行 nav（DEC-085／PROJECT_RULES §19.2）**：📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股／👤 我的／🩺 資料中心 是長期「責任方向」，**不等於**現行 nav 名稱，也不與既有 view 一對一對映；對映屬後續 IA Decision Gate，**本盤點不決定**。本節的「⚡」是**盤點範圍標籤（依現行 nav 暫代）**，表示「責任方向偏向『現在需要採取什麼行動』的舊 UI 功能」；凡出現 🎯／🛡️ 等其他責任名處，均括註現行 nav。程式碼目前掛在哪一頁，**不構成**「歸屬已可判定」；寫「目前只掛在…；歸屬待 IA Decision Gate」。
>
> **重驗總註（@15cd8fff，由本節複驗者實測）**：下列 code 層級宣稱已逐項對 worktree 重驗成立：`shared/ia_nav.py::PAGE_LABELS` 七項且 `⚡` 0 命中；`etf_tab_dividend_station.py` 的 `render_dividend_station`／`_render_layer1`／`_render_light_detail`／`_render_allocation_take_profit`／`_render_switch_advice`／`_render_ai_summary` 與其 `st.button`（:142／:196／:698）及 `etf_portfolio_rows` 寫入（:164）；`app.py` :1186／:1187；`dividend_station_service.flag_take_profit`（:1200）；`dividend_station.py::action_branch`（:751）／`suggest_action`（:777）；`section_when_buy_sell.py` 各行號（:171／:195／:200／:279／:303／:375-376）；`exit_signals.py::evaluate_exit_signals`（:236）、`_LEVELS`（:36-41）；`section_portfolio_summary.py` :715／:747；`tab_helpers.py::classify_stock_status_lamp`（:134）；`section_warroom.py` :55／:321、`section_mid.py` :685／:535／:540、`section_chips.py` :210／:272／:341；`etf_tab_portfolio.py` 各行號；`grape_ladder.py` :426-438；`section_psy_checklist.py` 各 checkbox；4 條 push cron；`page_hold.py` 各 `build_*`／`DEEP_SPECS`（:3007）／:4087／:5258；`page_inspect.py::STOCK_DETAIL_SECTIONS`（:2388）；`evaluate_exit_signals` 全 repo 呼叫者；`monthly_loss_pct` 全 repo 0 寫入；`etf_portfolio_rows` 20 行。**經重驗而更正者**以刪除線＋（更正原因）就地標示（C-16、C-08、C-17、C-29 等列，12.3.7 第 1 點，12.3.10 `section_warroom` inline 行號）。**未窮舉／未驗者**仍標 INFERENCE。

#### 12.3.0 一頁摘要（複驗後）

1. **客戶已定的 ⚡ 方向只有一句**：「現在有什麼需要處理？僅盤點既有 deterministic action 能力。不新增未核准的買賣語意、加減碼比例或新投資規則」（DEC-072 第 3 點，複驗確認與 `DECISIONS.md` 原文逐字一致）＋「作戰室／今天要做什麼」移往未來的 ⚡ 行動（DEC-081 Q1＝C；⚡ 為責任方向，現行 nav 尚無此頁）。**範圍（例示射程）仍 pending**：`DEC076-CONFIRM` ②、`CV1-FU-02`、`CV1-FU-03`。

2. **候選共 33 個**（C-01～C-30 為調查組；C-31 心理檢查／勝利方程式／今日禁止操作、C-32 每週大盤報告推播、C-33 每日選股訊號推播為複驗新增），分四類。**帶控制項的約 9 個（C-01、C-04、C-09、C-12、C-14、C-17、C-23、C-27、C-28）；複驗補註：這些控制項沒有任何一個會下單、改帳本或寫 Sheet**（C-01 的「缺 Sheet 就地綁定」子流程除外，可建立新 Sheet、寫使用者 Drive）。真正屬「⚡ 行動」語意的是 ② 類的結論句（C-11／C-13／C-15／C-18／C-20／C-21），不要把「9 個控制項」讀成「9 個行動」。

3. **新 UI 現況**：💼 我的持股頁（現行 nav）已**顯示**汰弱／加碼／停利／換股／80-20／AI 總結（唯讀）；**完全沒有**個股側三維出場訊號、個股進出場／停損／目標價／部位大小、今日作戰室、攻擊發動判定、各種結論句＋行動建議、再平衡交易指令、葡萄串、ETF 組合計算輸入、心理檢查。作戰室目前**兩頁都沒有**（🚦 今天 ⑤ 是 staged stub「尚無作戰項目」；📊 大盤檔頭明示不放）。

4. **治理張力（複驗後的正確形狀）**：(a) **再平衡股數指令／葡萄串提議 vs DEC-022**——**屬實**（DEC-022 禁一鍵再平衡按鈕、禁預設最佳配置推薦；DEC-054 承接表第 5～7 列寫「DEC-022 暫時保留」、DEC-055 寫「不把 DEC-054 擴張到投資組合再平衡」）；(b) **235「加碼 X%」vs DEC-053——降級為「待釐清」**：DEC-053 全文只有標題與「日後須經 資料驗證→規則設計→回測／Shadow→客戶裁示 才能進 production」，**沒有內容條文**，且 DEC-045 反而明文只重用 `suggest_action` 既有優先序、不新增比例；現行 20／30／50% 早於這些裁示。問題是「是否把既有 20/30/50% 視為 DEC-053 所稱『正式比例』」，**未裁**，**不能寫成已違反**；(c) **三維出場含 LLM vs DEC-054 第 6 點——不寫成已違反**：「🔴 強烈出場」＝三維**全中**（score==3），LLM 利空維度是**必要條件但非唯一依據**；待裁的是「LLM 維度能否成為強 Action 的必要條件」。

#### 12.3.1 舊 UI 有哪些功能（項目 1）與四類分類

分類欄位定義：
- **類別**：①客觀市場／個股資料　②規則判讀（deterministic，L2 規則算出的燈／結論）　③AI 分析（LLM 產出文字）　④使用者真正可採取的動作（按鈕／輸入框／會改變系統狀態的操作）。
- **型態**：**顯示**＝只顯示；**控制**＝有 button／輸入／slider 等 widget（讀外部資料、打付費 AI 也算控制，但不改變使用者資產）；**寫外部**＝寫入外部系統（Google Sheet、LINE／Telegram）。
- 一個候選可跨類，欄位寫「主類＋次類」。

| ID | 候選（功能） | 舊入口（重驗 @15cd8fff；原量測 4e6bf8ee） | 類別 | 型態 | 寫外部？ |
|---|---|---|---|---|---|
| C-01 | 🚀 跑存股戰情室（按鈕；逐檔抓價／週K／折溢價／VIX 後算燈） | `src/ui/etf/etf_tab_dividend_station.py::render_dividend_station`（:196 `st.button`） | ④（觸發運算） | 控制 | 否（讀 Sheet、讀外部行情）。（複驗更正）：缺 Sheet 時的就地綁定子流程（`portfolio_binder.render_holdings_binder`→`render_drive_picker` 的 `🆕 建立新投組 Sheet` → `_gsp.create_new_sheet()`）**可在使用者 Drive 建檔**，並有 `✅ 使用此 Sheet…` 寫綁定 |
| C-02 | 「該做什麼／需要處理」摘要：汰弱 N／加碼 N／未判 N | 同上 `_render_layer1`（:322）；L3 `dividend_station_service.build_station_digest` | ②（匯總） | 顯示 | 否 |
| C-03 | 逐檔燈號：ETF 健檢 A/B/C/D＋235 加碼燈＋3-3-3；個股財報體檢＋KD | 同上 戰情表 `_safe_dataframe`；L2 `compute/etf/dividend_station.py::assess_holding / light_235 / assess_stock` | ② | 顯示 | 否 |
| C-04 | 點一列就地展開逐燈明細 | `etf_tab_dividend_station.py::_render_light_detail`（:461） | ①②（明細） | 控制（`on_select`） | 否 |
| C-05 | 衛星停利（個股損益% ≥ 門檻 → 嚴格停利、滾回核心） | `etf_tab_dividend_station.py::_render_allocation_take_profit`（:572）；L3 `flag_take_profit`（`dividend_station_service.py:1200`）；L0 `SATELLITE_TAKE_PROFIT_PCT=15.0` | ② | 顯示 | 否 |
| C-06 | 80/20 核心／衛星實際配置偏離 | 同上；L3 `compute_allocation_split`；L0 `CORE_TARGET_PCT=80 / SATELLITE_TARGET_PCT=20` | ② | 顯示 | 否 |
| C-07 | 換股建議（換出＝持有的健檢紅燈；換入＝觀察清單綠燈，空才用選股池；搭配總經 stance） | `etf_tab_dividend_station.py::_render_switch_advice`（:628）；L3 `build_switch_advice / get_switch_in_candidates` | ② | 顯示 | 否 |
| C-08 | 建議持股水位（市場端上限）／「今日唯一行動建議」的持股區間 | L3 `services/allocation_service.get_allocation`；顯示處見第 9 節 | ② | 顯示 | 否 |
| C-09 | ✍️ 讓 AI 潤成推播文字（單顆按鈕，打付費 Gemini；結果只 `st.info` 顯示，不推送） | `etf_tab_dividend_station.py::_render_ai_summary`（:671；:698 `st.button`）；L3 `build_ai_summary` | ③ | 控制（付費） | **否**（見 C-10） |
| C-10 | LINE／Telegram 每日持股續抱／換股推播（**無 UI 入口**）。（複驗更正）：~~寫外部系統的 cron **共 4 條**~~ 寫外部通訊系統的推播 workflow 共 4 條（2 條有排程，2 條僅 workflow_dispatch），見 C-10／C-30／C-32／C-33 | `scripts/push_holdings_daily.py`；`.github/workflows/push_holdings_daily.yml`（cron `30 22 * * 0-4`＝TW 週一～五 06:30）；L2 `compute/notify/holdings_digest_message.py::format_holdings_message`；L1 `src/data/notify/{line_notify,telegram_notify,dispatch}.py` | ②（＋可選 ③） | cron，非 UI | **是（LINE／Telegram）** |
| C-11 | 🚨 三維出場訊號（利空新聞 LLM＋技術轉空＋籌碼倒貨 → 0～3 → 🟢清淡／🟡留意／🟠建議減碼／🔴強烈出場） | `src/ui/tabs/stock_sections/section_when_buy_sell.py`（:171 呼叫 `evaluate_exit_signals`）；L2 `src/compute/scoring/exit_signals.py::evaluate_exit_signals`（:236） | ②（含一維 ③） | 顯示 | 否 |
| C-12 | 個股組合「出場」欄＋🤖 AI 掃利空（按鈕，逐檔打 Gemini） | `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py`（:715 `st.button`、:747 呼叫） | ②＋④（按鈕）＋③ | 控制（付費） | 否 |
| C-13 | 個股「減碼／出場訊號」清單、進場訊號清單、目標價（現價＋20日震幅）、硬停損、月線停損、5MA 停利、加碼點 | `section_when_buy_sell.py`（約 :208 起的 `_entry`／`_exit` 清單（~~:215 以後~~，重驗更正：`_entry` 起於 208）與「🎯 目標＋停損」欄） | ② | 顯示 | 否 |
| C-14 | 💰 總資金輸入 → 建議買幾張＋ATR 停損 | `section_when_buy_sell.py`（:195 `st.number_input`；:303 `calculate_position_size`） | ④（輸入）＋② | 控制 | 否（僅 session） |
| C-15 | 💡 即時操作建議（4 訊號共振：健康／大盤／VCP／估值 → 「可積極進場」「小倉試水溫」「今日不操作」）＋AI 文案 | `src/ui/tabs/stock_sections/section_op_recommendation.py::render_op_recommendation_section` | ②＋③ | 顯示 | 否 |
| C-16 | 操作狀態燈 🔵加碼／🟡警示／🟠減碼／⚪ | `src/ui/tabs/tab_helpers.py::classify_stock_status_lamp`（:134）；用於 `tab_stock.py` 約 725 行（~~:724~~，重驗 @15cd8fff 更正：呼叫在 725，724 為上一行）、`section_batch_fetcher.py` 約 294 行（~~:284~~，重驗更正：284 為註解，呼叫 `classify_stock_status_lamp(` 在 294） | ② | 顯示 | 否 |
| C-17 | AI 報告類按鈕：🤖 生成 AI 投資組合分析報告／🔄 重新生成；🤖 AI 三型建議報告（積極／保守／止損紀律）；🤖 AI 首席顧問報告 | `section_ai_portfolio.py`（:63／:65）；`tab_stock_picker.py`（:572）；`tab_stock.py`（:1543 `🤖 生成 AI 首席顧問戰略評估報告`／:1545 `🗑️ 清除報告`；重驗 @15cd8fff 成立。另 `section_ai_portfolio.py` 在 `stock_grp_sections/`，:63／:65 重驗成立） | ③ | 控制（付費） | 否 |
| C-18 | 🎯 今日作戰室：「今日唯一行動建議」（依 regime 的一句話）＋5 分鐘清單（大盤燈號／外資／融資／年線／持股）＋今日風險警示 | `src/ui/tabs/macro/section_warroom.py::render_section_warroom`（:55）；掛在 `tab_macro.py` | ②（含 ①） | 顯示 | 否 |
| C-19 | ⛔ 月虧損強制停機警示（當月 < -10% → 建議暫停操作 7 天） | `section_warroom.py`（:321）；L0 `shared/signal_thresholds.py::MONTHLY_LOSS_HALT_PCT / MONTHLY_LOSS_HALT_DAYS` | ② | 顯示 | 否 |
| C-20 | ⚔️ 攻擊發動判定（三環公式＋SSS／A／B 火力分級） | `src/ui/tabs/macro/section_mid.py`（:685 expander） | ② | 顯示 | 否 |
| C-21 | 總經／籌碼「結論句＋行動建議」：§八 VIX 否決結論句（現金為王／停止加槓桿）、§八 策略1/3 矩陣、§三 三大法人／融資／先行指標結論卡 | `section_mid.py`（:530 以後、:552-673）；`section_chips.py`（:210／:272／:341） | ② | 顯示 | 否 |
| C-22 | 今日關鍵橫幅／風險警示（門檻類＋急變） | 新 UI 已在 `page_today::build_key_alert_tile`（④）與 `page_market` 首屏；舊 UI 在 🌍總經頁首 | ①②（偏市場） | 顯示 | 否 |
| C-23 | ETF 組合輸入＋計算：data_editor（代號／張數／均價／目標比例%）、容忍偏離 slider、📊 計算組合、🔄 強制重抓 | `src/ui/etf/etf_tab_portfolio.py::render_etf_portfolio`（:232／:255／:259／:574） | ④ | 控制 | 否（目標比例%**不會**存進 Sheet，檔內自述） |
| C-24 | ⚖️ 再平衡交易指令（買進／賣出＋建議股數＋金額，由使用者填的目標權重驅動；全填滿且總和 100% 才判） | `etf_tab_portfolio.py`（:822 以後）；L2 `portfolio_gates.evaluate_rebalance_gate` | ② | 顯示（內容是具體交易量） | 否 |
| C-25 | 核心／衛星 vs **regime 目標**（`CoreSatelliteManager` 依市場狀態 0.60～0.85）＋容忍帶 | `etf_tab_portfolio.py`（:755 以後）；`src/compute/strategy` | ② | 顯示 | 否 |
| C-26 | 壓力測試／VaR／配息日曆×年度現金流 | `etf_tab_portfolio.py`（:1055／:1086／:1270） | ①② | 顯示 | 否 |
| C-27 | 其他組合分析：產業曝險 ≤30%、相關係數、成分股／Overlap 矩陣、主動 ETF 弱勢度、與 0050 比較、效率前緣、配息稅後試算（二代健保＋綜所稅，含稅率 selectbox :1438）、Overlap 方法 radio（:950） | `etf_tab_portfolio.py` 各段 | ①② | 顯示／控制 | 否 |
| C-28 | 🍇 葡萄串領息：持股月月領覆蓋評估／補缺口建議／「🍇 生成提議」（最多 ETF 數／最低星等 slider、排除月配 checkbox） | `src/ui/tabs/grape_ladder.py`（:426／:431／:436／:438；`evaluate_income_ladder`、`suggest_fill_for_gaps`、`recommend_income_ladder`） | ②（提議＝配置推薦） | 控制 | 否 |
| C-29 | ETF AI 研判（`render_etf_ai`）。（複驗更正）：全 repo 無 production caller（定義＋`etf_dashboard.py` re-export＋反向斷言測試＋`app.py` 註解；重驗 @15cd8fff 見 Coverage 列的兩法驗證），見 Coverage 列 | `src/ui/etf/etf_tab_ai.py` | ③ | — | — |
| C-30 | 觀察池觸發推播（均線跌破／技術轉空／三維出場，LINE／TG；**無 UI 入口**） | `scripts/push_watchlist_signals.py`；`src/compute/notify/watchlist_triggers.py`；workflow 目前只保留 `workflow_dispatch`（排程已停，檔內自述） | ② | cron／手動 dispatch | **是（LINE／TG）** |

**搜尋方法（說明為何認為這份清單接近完整，但仍未窮舉）**：(a) 讀 `app.py` 7 個舊頁籤的路由與 `etf_tab_dividend_station.py` 全檔；(b) 對 `src/ui/**` grep `exit_signal|evaluate_exit|出場|減碼|停損|停利|汰弱|加碼|作戰室|再平衡|葡萄串`；(c) 對 `src/ui/views/page_*.py` 同樣 grep；(d) 讀 `MARKET_PAGE_DECISION_GATE_2026-10-24.md` 內標為 ⚡ 行動的列（E11／H05／S05／S08～S10／G10／G22）。**未窮舉**：`tab_macro.py` 其餘 section、`tab_stock_picker.py` 非 AI 部分、`macro_classroom.py`、`tab_edu.py` 內是否另有行動語句。
| C-31 | **（複驗新增）** 個股「🧠 心理檢查＋🏆 勝利方程式＋🚫 今日禁止操作」：3 個 `st.checkbox`（SOP 進場強制檢核）、「可以考慮操作／建議等待」、「今日禁止操作…今天暫停」 | `src/ui/tabs/stock_sections/section_psy_checklist.py::render_psy_checklist_section`（`tab_stock.py` 約 888 行呼叫（重驗 @15cd8fff）；checkbox 約 169／190／202、判語約 246、禁止約 251／300） | ②＋④（checkbox 控制） | 控制 | 否 |
| C-32 | **（複驗新增）** 每週大盤報告推播（定調＋逐檔體檢＋**AI 建議**推到 LINE；**無 UI 入口**） | `.github/workflows/push_weekly_report.yml`（`cron "0 21 * * 0"`，現行啟用）；`scripts/push_weekly_report.py` | ②＋③ | cron，非 UI | **是（LINE）** |
| C-33 | **（複驗新增）** 每日選股訊號推播（推選股前 N 名；排程已停，保留 `workflow_dispatch`；**無 UI 入口**） | `.github/workflows/push_daily_signals.yml`；`scripts/push_daily_signals.py` | ② | 手動 dispatch | **是（推播）** |

**複驗補列說明**：C-31～C-33 為複驗用「呼叫者反查」與 `.github/workflows/push_*.yml` 掃描新增；**搜尋仍未窮舉**（`tab_macro.py` 其餘 section、`macro_classroom.py`、`tab_edu.py`、`tab_sector_flow.py`、`yield_screener.py` 內是否另有行動語句未掃，「只有這三項漏列」不可成立）。

#### 12.3.2 使用者目的（項目 2；INFERENCE，依 UI 文案與 docstring）

| ID | 使用者目的（INFERENCE，依 UI 文案與 docstring） |
|---|---|
| C-01 | 一次把持股（含觀察清單）逐檔判完，回答「今天要不要動」 |
| C-02 | 不看明細就知道有幾檔要處理 |
| C-03 | ETF：定期定額策略的加碼時點；個股：基本面汰換 |
| C-04 | 看某一檔每盞燈為什麼亮／不亮 |
| C-05 | 衛星個股獲利到一定程度提醒落袋 |
| C-06 | 核心與衛星比例是否偏離目標 |
| C-07 | 持有的紅燈該換掉誰、換成誰 |
| C-08 | 以現在市場風險，整體股票部位最多放多少 |
| C-09 | 把規則事實濃縮成一段可轉貼的文字 |
| C-10 | 不開 App 也收到每日提醒 |
| C-11／C-12 | 單檔／整個個股組合有沒有該出場的跡象 |
| C-13 | 單檔的進出場、停損停利、目標價參考 |
| C-14 | 依資金與波動算一次能買幾張 |
| C-15 | 單檔「現在能不能進場」的共振判斷 |
| C-16 | 組合表一眼分出加碼／警示／減碼 |
| C-17 | 要一份 AI 寫好的長篇報告 |
| C-18 | 開盤前 5 分鐘知道今天大盤環境下該怎麼做 |
| C-19 | 虧太多時被迫冷靜 |
| C-20 | 大盤環境是否允許積極進攻 |
| C-21 | 市場端的白話結論＋建議 |
| C-22 | 今天有沒有踩線的總經／籌碼警示 |
| C-23 | 輸入一個假想／實際 ETF 組合做試算 |
| C-24 | 依自己設的目標權重算要買賣多少 |
| C-25 | 組合核衛比例是否符合市場狀態建議帶 |
| C-26 | 壓測／風險值／預估現金流 |
| C-27 | 組合的集中度、重疊、稅後等進階分析 |
| C-28 | 讓持股配息月份湊滿 12 個月 |
| C-29 | ETF 長篇 AI 研判 |
| C-30 | 觀察池有東西破線時被通知 |
| C-31 | 在進場前被迫過一遍檢核、虧太多時被提醒今天不要操作（INFERENCE） |
| C-32／C-33 | 不開 App 也收到每週大盤報告／每日選股訊號（INFERENCE） |

#### 12.3.3 資料來源／service／資料層（項目 3）

（原量測 4e6bf8ee，重驗 @15cd8fff；只寫 `檔案::符號`）

| ID | 取數／計算路徑 |
|---|---|
| C-01～C-07 | L5 `etf_tab_dividend_station.py` → L3 `src/services/dividend_station_service.py::get_station_rows / build_station_digest / compute_portfolio_totals / compute_allocation_split / flag_take_profit / get_station_macro / get_switch_in_candidates / build_switch_advice / switch_in_invalid_rows` → L2 `src/compute/etf/dividend_station.py::assess_holding / assess_stock / light_235 / suggest_action / action_branch`；門檻 L0 `shared/dividend_station_thresholds.py`；持股來源舊 UI＝`etf_tab_dividend_station.py::_load_holdings_from_portfolio`（私有，L5），新 UI＝L3 `services/holdings_service.get_holdings` |
| C-08 | L3 `services/allocation_service.get_allocation`（仲裁「姿態油門 × 系統風險上限 × VIX／三環天花板」取最低）；同檔 `apply_vix_veto / apply_ring_gate`（舊 §八 render 內還會呼叫，但 `register_cap` docstring 自述 v19.170 起內在天花板由 `get_allocation` 自行推導） |
| C-09 | L3 `dividend_station_service.build_ai_summary`；L3 `services/app_ai_service.gemini_call`（付費 API，不丟例外、失敗回 `⚠️…` 說明字串）；舊 UI 傳入 `gemini_fn=gemini_call`（`app.py:1187`） |
| ~~C-10／C-30~~ C-10 | cron CLI（L6 orchestrator）→ Service Account 讀環境變數指定的兩個私有 Sheet（`portfolios`＋`stock_watchlist`）→ 同一批 L3 戰情引擎 → L2 `compute/notify/*` 組訊息 → L1 `data/notify/dispatch` 推 LINE／TG；secret 缺 → exit 1（腳本自述）（更正：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；C-10 與 C-30 路徑不同，拆列；重驗 @15cd8fff：`push_holdings_daily.py` 呼叫 `load_sa_credentials`） |
| C-30 | cron CLI → 讀「發布為 CSV 的公開連結」（`--csv-url` > `WATCHLIST_CSV_URL` > `WEEKLY_WATCH_CSV_URL`；複用 `push_weekly_report` 的 `_split_urls`／`collect_tickers`）→ L1 `fetch_stock_history_1y` 取價 → L2 `watchlist_triggers`（`scan_watchlist`／`evaluate_ticker`，內含 `exit_signals` 判定）組訊息 → L1 `data/notify/dispatch` 推 LINE／TG；**不經 Service Account、不走 L3 戰情引擎**（重驗 @15cd8fff：`scripts/push_watchlist_signals.py` 無 `load_sa_credentials`、無 `src.services` import） |
| C-11/C-12 | L2 `src/compute/scoring/exit_signals.py::compute_tech_bearish / evaluate_exit_signals / judge_news_sentiment_cached`；籌碼＝`analyze_20d_chips_from_df`；新聞標題＝`_fetch_stock_news`（L1 RSS）；LLM＝`gemini_call`（TTL 6h，`st.cache_data`） |
| C-13 | `section_when_buy_sell.py` 直接用 df（K 線）＋L0 `HARD_STOP_LOSS_PCT=7.0`、`STOP_LOSS_DEFAULT_PCT=8.0`、`BB_DROP_OUT_RATIO` 等 |
| C-14 | L2 `src.compute.scoring.calc_atr_stop / calculate_position_size`；`st.session_state['_pos_capital']` |
| C-15 | L3 `allocation_service.get_macro_regime`；L0 `HEALTH_GRADE_A_MIN`、`YIELD_MID_DEC`；L3 `app_ai_service.generate_ai_comment` |
| C-16 | `tab_helpers.py::classify_stock_status_lamp`（L5 檔內純函式）＋L0 `GRP_*` 門檻 |
| C-18/C-19/C-20/C-21 | `st.session_state` 內舊總經頁寫入的 `mkt_info / cl_data / bias_info / m1b_m2_info / warroom_summary / li_latest`（經 L3 `services/section_inputs.load_section_inputs` 取）；`evaluate_market_status_v4_final`；`get_allocation` |
| C-23～C-27 | L5 `etf_tab_portfolio.py` → L2 `compute/etf/*`（`calc_portfolio_stress_test`、`compute_etf_annual_cashflow`、`etf_calc`）、`compute/strategy/CoreSatelliteManager`、L1（EX-PASSTHRU-1）`etf_fetch` |
| C-28 | L5 `grape_ladder.py`，輸入＝`st.session_state['etf_portfolio_rows']` |

#### 12.3.4 是否涉及 Sheet／portfolio／watchlist／OAuth／AI 分析／外部 API（項目 4）

「是（讀）」＝只讀，不改使用者資產。

| ID | Sheet | portfolio | watchlist | OAuth | AI 分析 | 外部 API |
|---|---|---|---|---|---|---|
| C-01～C-07 | 是（讀） | 是（讀） | 是（讀；C-07 換入優先取觀察清單綠燈） | 是（Sheet 需 Google 登入；舊 UI 缺 Sheet 時就地 `render_holdings_binder`） | 否 | 是（Yahoo／FinMind／TWSE 等，經 L1；VIX） |
| C-08 | 否 | 否 | 否 | 否 | 否 | 否（讀 session 內總經快照） |
| C-09 | 是（讀） | 是 | 是 | 是 | **是**（付費） | 是（Gemini） |
| C-10 | 是（讀；Service Account） | 是 | 是 | 否（SA，不走使用者 OAuth） | 選配（Gemini 潤稿） | 是（LINE／TG 寫出） |
| C-11 | 否 | 否 | 否 | 否 | **是**（利空新聞維度） | 是（新聞 RSS＋Gemini） |
| C-12 | 否（輸入來自批次抓取結果） | 組合比較清單 | 否 | 否 | **是** | 是 |
| C-13/C-16 | 否 | 否 | 否 | 否 | 否 | 是（K 線） |
| C-14 | 否 | 否 | 否 | 否 | 否 | 否（吃 C-13 的現價與 ATR） |
| C-15 | 否 | 否 | 否 | 否 | **是**（AI 文案） | 是 |
| C-17/C-29 | 視入口 | 視入口 | 視入口 | 否 | **是** | 是 |
| C-18～C-21 | 否 | 否（C-18 5 分鐘清單有「持股比例」＝C-08 的區間，不是你的持股） | 否 | 否 | 否 | 否（讀 session） |
| C-22 | 否 | 否 | 否 | 否 | 否 | 否 |
| C-23～C-27 | 否（目前輸入表可由 C-01 橋接帶入；**不寫回** Sheet） | 是（橋接） | 否 | 否 | C-29 才有 | 是（行情／匯率／配息） |
| C-28 | 否 | 是（吃橋接 session） | 否 | 否 | 否 | 是（配息歷史） |
| C-30 | ~~是（讀；SA）~~ 否（讀公開 CSV） | 否 | 是（讀公開 CSV） | 否（無 OAuth、無 SA） | 否 | 是 |

**FACT複驗更正（全稱句已更正）**：⚡ 候選功能本體（C-02～C-30）不寫 Sheet；**C-01 的「缺 Sheet 就地綁定」子流程（`portfolio_binder.py::render_drive_picker`）可 `create_new_sheet()` 在使用者 Drive 建檔並寫綁定**（原組 grep 的檔案清單沒包含 `portfolio_binder.py`，故漏掉）。相鄰的 🎯 範圍另有兩個寫 Sheet 的舊 widget：`app.py` 的 `➕ 加入觀察清單`（`watchlist_service.add_picks_to_watchlist`）與 `🧊 凍結前 20 名`（存 Google Sheet）。**~~寫外部系統的 cron 共 4 條~~ 寫外部通訊系統的推播 workflow 共 4 條（2 條有排程，2 條僅 workflow_dispatch）**（更正：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；原組只列 2 條）：`push_holdings_daily`（啟用，`cron "30 22 * * 0-4"`）、`push_weekly_report`（啟用，`cron "0 21 * * 0"`，含「AI 建議」）、`push_watchlist_signals`（僅 `workflow_dispatch`，排程已停）、`push_daily_signals`（僅 `workflow_dispatch`，排程已停）。

#### 12.3.5 舊 UI 主要互動流程（項目 5）

**流程 A：持股戰情室（C-01～C-09）**
1. 開「💼 我的持股戰情室」頁籤（`app.py:1186`）。
2. 自動載入持股 `_load_holdings_from_portfolio()`；沒綁 Sheet → 就地三態綁定（未登入／已登入未綁／已綁但空）。
3. 〔可選〕按 🔄 重新載入（清 L1 讀取快取、清 `_station_rows`／`_station_ai_text`）。
4. 按 🚀 跑存股戰情室 → 抓 VIX＋逐檔 → 產 `_station_rows`；同輪另算換股建議（best-effort，失敗只顯示 caption）。
5. 顯示順序：①結論三卡 → ③戰情表（ETF 與個股分兩區）→ 80/20＋停利 → ②兩套刻度揭露 → 點一列展開燈明細 → ④換股建議 → ⑤📊 組合深度分析 expander（內含 C-23～C-28）→ ⑥AI 戰情總結。
6. AI 總結：先出「規則事實」（汰弱警訊／235 加碼觸發／全清則寫「續抱、定期定額即可」），有金鑰才顯示 ✍️ 按鈕；按了才打 Gemini，結果存 `_station_ai_text`。
7. **副作用（FACT）**：第 2 步會把橋接結果寫 `st.session_state['etf_portfolio_rows']`（`etf_tab_dividend_station.py:164`），供 C-23／C-28／`tab_sector_flow`／`portfolio_linkage` 下游使用。

**流程 B：個股出場（C-11～C-16）**
1. 在「🔬 個股」輸入代號載入 → 「什麼時候買賣」區塊（`section_when_buy_sell.py`）自動算（不需按鈕）。
2. 三維出場橫幅：技術＋籌碼立即算；新聞維度需自動抓標題後打 Gemini（6h 快取）。
3. 〔可選〕填總資金 → 顯示建議張數與 ATR 停損。
4. 個股組合：「🤖 AI 掃利空」按鈕 → 逐檔 Gemini → 出場欄改三維計分；未按則只有技術＋籌碼兩維（caption 自述）。

**流程 C：今日作戰室（C-18～C-21）**
1. 在「🌍 市場環境」按 🚀 一鍵更新全部數據 → session 寫入 `mkt_info`…。
2. 作戰室只在 `_show_market_data` 為真時畫；否則 `st.info('📡 點擊「🚀 一鍵更新全部數據」載入今日作戰室')`。

**流程 D：ETF 組合／葡萄串（C-23～C-28）**
1. 戰情室 ⑤ expander 展開 → 輸入表（預設吃橋接持股，目標比例%需自填）→ 調容忍度 → 按 📊 計算組合 → 逐段顯示 → 再平衡指令（需全部目標比例填滿且總和 100%）。
2. 葡萄串：有橋接持股 → 顯示月月領覆蓋；無 → fallback 高股息 10 檔「系統提議」，按 🍇 生成提議。

#### 12.3.6 新 UI 現況與 Old→New Interaction Coverage 表（項目 6；複驗更正已套用）

**狀態用語（DEC-085 §19.6，只有四種，一字不改）**：`✅ 已覆蓋`（能力等價，至少能看到同樣的結論與限制揭露）｜`🟡 部分覆蓋`｜`⬜ 未覆蓋`｜`🚫 明確不再需要／不應搬入`。**沒有第五種正式狀態**；「待客戶裁示」只能以獨立標註 `【decision-note：待客戶裁示 S#】` 放在狀態格**以外**。🚫＝「AI 盤點建議不搬／不應搬入，**最終認定屬客戶**；不構成任何舊 UI 刪除授權」，🚫 理由限「重複／過時／風險／已被取代」，「不是 UI 能力」不是容許理由。S# 為 §12.5 的 Stage B 前置候選問題（decision-note），Stage B 再收斂為少量 Decision Gates，本輪不要求逐題裁示。

**新 UI 現有「行動相關」位置（FACT，重驗 @15cd8fff；原量測 4e6bf8ee）**
- `src/ui/views/page_hold.py`（💼 我的持股）葉1 戰情室：`_render_warroom_leaf` 的 ①結論三卡（`build_action_card`:2097／`build_confidence_card`／`build_todo_card`:2186）、②兩套刻度、③燈牆＋VIX、④換股建議（`build_switch_card`:2432）、⑤80/20＋衛星停利＋建議持股水位（`build_allocation_split_card`／`build_take_profit_card`:2813／`build_position_cap_card`:2919）、⑥深度（壓測／VaR／配息現金流／核心衛星；再平衡與葡萄串 `unwired`，`DEEP_SPECS`:3007）、⑦AI 戰情總結（`load_ai_summary`:4087，按鈕 `_render_ai_button`:5258）。本頁一律唯讀（檔頭自述＋測試黑名單）。
- `src/ui/views/page_today.py`（🚦 今天）：⑤作戰室／⑥AI 摘要仍是 staged stub（`tab_today.py` 約 542–545 行：`warroom.todo`「尚無作戰項目」、`warroom.ai`「AI 摘要尚未接線」；`page_today.py` 約 2729–2730 行（~~2729-2731~~，重驗 @15cd8fff 更正：2731 為 dict 結尾括號）的 `warroom.todo`／`warroom.ai` 對應；stub 卡本體在 `tab_today.py` 約 542–545 行（~~:540 起~~，重驗更正））。
- `src/ui/views/page_market.py`（📊 大盤）：首屏含卡①「能不能出手 · 出手到幾成」與今日關鍵警示；檔頭自述「作戰室日後移到 ⚡ 行動（本批不做）」。
- `src/ui/views/page_inspect.py` / `page_find.py` / `page_why.py` / `page_me.py`：grep `exit_signal|出場|減碼|停損|停利|汰弱|加碼` 0 命中（搜尋法：對這 4 檔各 grep 一次，見 §1 搜尋方法）。`page_inspect` 檔頭明列「什麼時候買賣」「心理檢查」等七段**未接線**（`STOCK_DETAIL_SECTIONS`，:2388）。

**Old→New Interaction Coverage 表**

| 舊功能 | 舊入口 | 新 UI 現況 | 新入口候選（**僅候選，非設計決定**） | Coverage | Dead-end | 資料來源 | 風險／限制 |
|---|---|---|---|---|---|---|---|
| C-01 🚀 跑存股戰情室 | `etf_tab_dividend_station.py:196` | `page_hold` 葉2 表單 `single_submit_form`（`ACTION_RUN_WARROOM_LABEL="🚀 跑存股戰情室"`，:443）＋「只讀市場端／連同 Sheet」radio；兩個選項都不寫 Sheet | 若 ⚡ 要有「現在重算」入口，可引用同一個 gate，避免兩份 form | ✅ 已覆蓋 | 否 | L3 `get_station_rows` 等 | 目前只掛在 💼 我的持股頁（戰情室葉）；⚡／🛡️ 歸屬待 IA Decision Gate（G10）；複驗附註：舊 UI 另有 `🔄 重新載入`（`etf_tab_dividend_station.py` 約 142 行，清 L1 讀取快取）未列為候選，新 UI 對應物（重新讀取）在 👤 我的，非 ⚡／🛡️，視為依附功能 |
| C-02 該做什麼／需要處理 | `_render_layer1` | `page_hold` ①三卡：「汰弱 N · 加碼 N · 未判 N」＋可信度 N/M＋巡航 gate（有未判列就不准說「沒事」） | 同 | 🟡 部分覆蓋 | 否 | digest `reds/adds` | 只顯示**檔數**；個別代號與加碼 % 不在三卡上（見 C-03）。新 UI 比舊 UI 嚴格（舊 UI 全清時直接寫「續抱」，見第 9 節 F5）——**應保留新 UI 的作法** |
| C-03 逐檔燈號 | 戰情表 dataframe | `page_hold` ③燈牆（L4 `render_light_wall`，四態＋N/M 同一把尺） | — | 🟡 部分覆蓋 | 否 | L2 `light_cells` | 舊表有「建議動作」欄（`suggest_action` 字串，含「加碼 X%」）；`page_hold` 只在換股卡列出換出的「建議動作」，**加碼的部署 % 沒顯示**（grep `加碼金\|deploy` 於 `page_hold.py` 0 命中）→ 加碼要加多少仍只能看舊 UI／AI 摘要。INFERENCE：此為「顯示縮水」，不是 bug。狀態說明：燈牆等價但逐檔動作字串與部署 % 缺 ⇒ 🟡（~~原 ✅~~，複驗降級：同一格寫 ✅ 又承認顯示縮水，內部矛盾；舊 `_render_ai_summary` 會印「加碼 {加碼金}」；重驗 @15cd8fff：`page_hold.py` grep `加碼金\|deploy` 仍 0 命中） |
| C-04 點一列展開燈明細 | `_render_light_detail`（:461） | 無；`page_hold._render_light_wall` docstring 自陳「刻意不做」（新增互動元件須先出線框，A-8） | 責任方向 🛡️ 持股（現行 nav：💼 我的持股）內展開，或 🎯 標的（現行 nav：🔬 查一檔／🔍 找標的）；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 半（燈亮了但看不到為什麼，只能回舊 UI） | L4 `render_holding_detail` | 需線框（DEC-003） |
| C-05 衛星停利 | `_render_allocation_take_profit` | `page_hold` ⑤`build_take_profit_card`（含「沒被判過≠沒達標」升紅規則） | — | ✅ 已覆蓋 | 否 | L3 `flag_take_profit` | 門檻 15%＝L0 常數，來源是策略參數（`dividend_station_thresholds.py` 檔頭自述「非本站發明」），**Stage B 不得改** |
| C-06 80/20 偏離 | 同上 | `page_hold` ⑤`build_allocation_split_card` | — | ✅ 已覆蓋 | 否 | L3 `compute_allocation_split` | 與 C-25 的 regime 核心比例是**兩套**（G13） |
| C-07 換股建議 | `_render_switch_advice` | `page_hold` ④`build_switch_card`（附 `excluded_n`、總經未評估只做汰弱） | — | ✅ 已覆蓋 | 否 | L3 `build_switch_advice` | 覆蓋範圍為「顯示」；「汰弱換強」語意歸屬 G1／G2 |
| C-08 建議持股水位 | 作戰室「今日唯一行動建議」、🎚️ 建議持股油門 | 三處新 UI 副本：`page_today` 卡①「能不能出手 · 出手到幾成」；`page_market` 同一卡；`page_hold` ⑤`build_position_cap_card` | 責任方向 📊 大盤（現行 nav：📊 大盤）；⚡ 只引用不複算；歸屬待 IA Decision Gate | ✅ 已覆蓋 | 否 | L3 `get_allocation` | **重複入口**（第 9 節）；缺有效 Risk Cap → 「無法判定」（DEC-040）；複驗補第 6 份副本：`app.py` 全域置底常駐條（`_gl_slot` 建立於約 733 行、填入於約 1206–1275 行（~~約 1215 行起~~，重驗 @15cd8fff 更正行號）；`_gl_pos = _alloc.range_text` 約 1242 行，顯示「建議持股」＋多空燈）→ 重複入口 D1；覆蓋狀態含「多處副本」 |
| C-09 AI 推播文字 | `etf_tab_dividend_station.py:698` | `page_hold` ⑦`⚡ 生成 AI 總結`（:5279；結果不存 session；附 AI 揭露；失敗字串不當摘要） | — | ✅ 已覆蓋 | 否 | L3 `build_ai_summary` | 覆蓋範圍僅「生成」，**推送不存在**。舊鈕叫「推播文字」、新卡標「唯一推播出口」，但**兩邊都不推送**（C-10 才推）。命名容易讓人以為按了就會推（INFERENCE） |
| C-10 LINE／TG 每日推播 | cron | 無 UI | 若客戶要在 ⚡ 看「今天推了什麼」或手動觸發，屬新能力 | ⬜ 未覆蓋 | 否 | `scripts/push_holdings_daily.py` | 見 G12；**寫外部系統**，不得因整理 UI 而動。cron 本身不依賴新舊 UI、照常運作（`push_holdings_daily.yml` 啟用中，cron `30 22 * * 0-4`，重驗 @15cd8fff）；⬜ 僅指「新 UI 沒有對應入口」。狀態判斷：啟用中、寫外部、仍被使用 ⇒ 不符 🚫 的任一容許理由（~~原 🚫~~，理由「不是 UI 能力」不是容許理由，已退回；~~待裁示~~ 為第五種狀態，已移除）。【decision-note：待客戶裁示 S11】 |
| C-11 三維出場訊號 | `section_when_buy_sell.py:171` | **無**（`page_inspect` 的「什麼時候買賣」未接線；`page_hold` 的「汰弱」是健檢紅燈，不是三維出場） | 責任方向 ⚡（出場訊號；DEC-076 例示 exit signal）或 🎯 標的（現行 nav：🔬 查一檔／🔍 找標的）；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | **是**（最核心的「出場」能力新 UI 完全沒有） | L2 `evaluate_exit_signals` | G1／G5；含 LLM 維度；複驗：新 UI 零處呼叫 `evaluate_exit_signals`（靜態 grep，未排除 getattr／字串動態引用）（呼叫者反查：僅 `section_when_buy_sell.py`、`section_portfolio_summary.py`、`watchlist_triggers.py`；`tab_stock.py` 約 148 行僅 import 未用） |
| C-12 組合出場欄＋AI 掃利空 | `section_portfolio_summary.py:715／:747` | 無 | 責任方向 ⚡／🎯 標的 批次（現行 nav 對映歸屬待 IA Decision Gate） | ⬜ 未覆蓋 | 是 | 同上＋Gemini | G5；付費 AI 按鈕 |
| C-13 個股進出場／停損／目標價／加碼點 | `section_when_buy_sell.py` | 無 | 責任方向 🎯 標的（現行 nav：🔬 查一檔／🔍 找標的）（個股明細）＋⚡ 摘要；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 是 | K 線＋L0 常數 | G6；含「目標價」「硬停損 7%」「停損 8%」兩個停損常數並列 |
| C-14 總資金→建議張數＋ATR 停損 | `:195／:303` | 無 | 同上 | ⬜ 未覆蓋 | 是 | L2 `calculate_position_size` | G6；Position Sizing 屬 CV1-FU-04 缺口；輸入欄＝新增控制項須線框 |
| C-15 即時操作建議（4 訊號共振） | `section_op_recommendation.py` | 無 | 責任方向 🎯 標的（現行 nav：🔬 查一檔／🔍 找標的）；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 是 | L3 regime、L0 | G6；「可積極進場」類語句＋AI 文案；inline 60／3／2 門檻（第 10 節） |
| C-16 操作狀態燈 | `tab_helpers.py:134` | 無 | 責任方向 🎯 標的（現行 nav：🔍 找標的／🔬 查一檔 清單列）／⚡；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 是 | L0 `GRP_*` | ⚪ 把「中性」與「資料不足」混為同一個符號（F2） |
| C-17 AI 報告類 | 多處 | 無（`page_why` 有 AI 問答，不等價） | 責任方向 ⚡／🎯 標的（現行 nav 對映歸屬待 IA Decision Gate） | ⬜ 未覆蓋 | 是（對應既有矩陣已列「待接」） | Gemini | AI 結論不得當客觀資料；付費；DEC-054 第 5／6 點 |
| C-18 今日作戰室 | `section_warroom.py` | `page_today` ⑤ stub「尚無作戰項目」；`page_market` 不含 | 責任方向 ⚡（DEC-081 Q1＝C 已定方向；現行 nav 尚無 ⚡ 頁；實作未指派＝`UIX-ACTION-PAGE`） | ⬜ 未覆蓋 | **是**（今天頁 ⑤ 空殼＋大盤頁已移走 → 作戰室目前兩邊都沒有） | `warroom_summary` 等 | G8；內含 regime 一句話行動建議 |
| C-19 月虧損強制停機 | `section_warroom.py:321` | 無 | 責任方向 ⚡ | ⬜ 未覆蓋 | 否 | `session['monthly_loss_pct']` | **輸入全站無寫入點**（`section_psy_checklist.py:271` 自述；本組 grep `monthly_loss_pct` 只有 2 處讀、0 處寫）→ 警示永遠不會觸發，且預設 `0` 把「沒資料」當「沒虧損」。需客戶決定留／去（G7）；複驗：`section_warroom.py` 約 321 行 `session_state.get('monthly_loss_pct', 0)` 預設 0；`section_psy_checklist.py` 約 271–273 行把同一欄位當「未追蹤」處理——**同一欄位兩種處理，不一致**。狀態判斷：新 UI 沒有此警示 ⇒ ⬜（~~原 🚫~~：「輸入無來源」是現況缺陷、不是 🚫 的容許理由，已退回；~~待裁示~~ 為第五種狀態，已移除）。重驗 @15cd8fff（第二法）：全 repo（排除 `.git`／`docs`）grep `monthly_loss` 僅 `section_warroom.py::render_section_warroom` 與 `section_psy_checklist.py::render_psy_checklist_section` 各 1 處 `session_state.get(...)` 讀、0 處寫，其餘為常數定義與註解；仍屬靜態 grep，無法排除字串動態組 key（INFERENCE，機率低）。【decision-note：待客戶裁示 S7】 |
| C-20 ⚔️ 攻擊發動判定 | `section_mid.py:685` | 無 | 責任方向 ⚡（Gate 檔 E11 標「⚡ 行動（盤點）」，盤點範圍標籤） | ⬜ 未覆蓋 | 是 | session `li_latest` 等 | G11；「🚀 SSS 級全面總攻」類字樣 |
| C-21 結論句＋行動建議 | `section_mid.py:530／:552`、`section_chips.py:210／:272／:341` | 無（Gate 檔：首批不帶，暫留舊 UI） | 責任方向 ⚡ 或 📊 大盤（現行 nav：📊 大盤）第 3 層；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 是 | session | G11；與 `VN1-MT-TREND-DEF` 相鄰；重驗 @15cd8fff：`section_mid.py` 約 530–540 行 VIX 否決段（:535 現金為王、:540 停止加槓桿）屬實，`section_chips.py` :210／:272／:341 均為 `strategy_conclusion(...)` 結論卡呼叫，成立（~~「行號未逐行驗」~~ 已逐行驗） |
| C-22 今日關鍵橫幅 | 舊總經頁首 | `page_today` ④／`page_market` 首屏一行 | 責任方向 📊 大盤（盤點範圍標籤，依現行 nav 暫代；非歸屬判定） | ✅ 已覆蓋 | 否 | L2 `daily_key_alerts` | 不屬 ⚡ 盤點範圍；門檻類在新版常態「本次未評估」（既有 Gate 檔 E07） |
| C-23 ETF 組合輸入＋計算 | `etf_tab_portfolio.py:232／:255／:259／:574` | 無（`page_hold` ⑥ 只接 L3 `portfolio_deep_service` 三項） | 責任方向 🛡️ 持股（現行 nav：💼 我的持股）；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 是 | L2 etf_calc | 需新增輸入控制項（線框） |
| C-24 ⚖️ 再平衡交易指令 | `:822` | `page_hold` `hold.deep.rebalance` 明示 `unwired`：缺帳本「目標比例」欄；且「不會拿現況當目標」 | 責任方向 ⚡ 或 🛡️ 持股（現行 nav：💼 我的持股）；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 是 | L2 `portfolio_gates` | **G3**：DEC-022 再平衡硬禁令暫時保留；舊 UI 目前會輸出「買進／賣出 N 股、金額」。目標比例%要存哪＝Sheet 寫入（High）；複驗：類別欄宜加註「（準指令）」——內容是具體交易量（買進／賣出 N 股），非一般判讀 |
| C-25 核衛 vs regime 目標 | `:755` | `page_hold` 只做 L0 固定 80/20（C-06），**不做** regime 版 | 責任方向 🛡️ 持股（現行 nav：💼 我的持股）；歸屬待 IA Decision Gate | 🟡 部分覆蓋 | 否 | `CoreSatelliteManager` | G13：兩套核心比例；`page_hold` 檔內明寫「不改用 CoreSatelliteManager 頂替」 |
| C-26 壓測／VaR／配息現金流 | `:1055／:1086／:1270` | `page_hold` ⑥ 三卡已接（`build_stress_card／build_var_card／build_dividend_cash_card`） | — | ✅ 已覆蓋 | 否 | L3 `portfolio_deep_service` | 盤點範圍標籤：🛡️（依現行 nav 💼 我的持股暫代），不屬 ⚡ 盤點範圍；歸屬待 IA Decision Gate |
| C-27 其餘組合分析 | `etf_tab_portfolio.py` 各段 | 無 | 責任方向 🛡️／🎯（交其他組；現行 nav 對映待 IA Decision Gate） | ⬜ 未覆蓋 | 是 | 同上 | 稅後試算含稅率 selectbox（:1438）；非 ⚡ |
| C-28 🍇 葡萄串 | `grape_ladder.py:426-438` | `page_hold` `hold.deep.grape` 明示 `unwired`（L5 寫死 widget key；吃 `etf_portfolio_rows`） | 責任方向 ⚡ 或 🛡️ 持股（現行 nav：💼 我的持股）；歸屬待 IA Decision Gate | ⬜ 未覆蓋 | 是 | `etf_portfolio_rows` | G3；「🍇 生成提議」＝最佳組合推薦；**隱藏依賴**：`etf_portfolio_rows` 只由舊 UI 寫（第 9 節 F8） |
| C-29 ETF AI 研判 | `etf_tab_ai.py` | 無 | — | 🚫 明確不再需要／不應搬入 | 否 | — | **舊 UI 也沒有 production caller**（`grep -rn render_etf_ai --include=*.py .`：定義 `etf_tab_ai.py`、re-export `etf_dashboard.py:57`、反向斷言 `tests/test_etf_smart_ticker_wiring.py:90`、`app.py` 僅註解）→ 🚫 理由為「過時（無 production 呼叫者）」，AI 盤點建議，最終認定屬客戶，不構成刪除授權。**重驗 @15cd8fff（兩法）**：(i) 全 repo `grep -rI` 名稱／模組 `render_etf_ai`／`etf_tab_ai`：僅定義、`etf_dashboard.py:57` re-export、`src/ui/etf/__init__.py` 模組清單（PEP 562 `__getattr__` 轉發，無名稱使用者）、測試、`app.py` 兩處註解（:41、:209）與 STATE／ARCHITECTURE／docs 文字，無 production 呼叫；(ii) `render_etf_portfolio`／`render_grape_ladder` 在 `etf_tab_dividend_station.py` 約 277–284 行被呼叫，`render_etf_ai` 不在其中；`tests/test_etf_smart_ticker_wiring.py:90` 反向斷言 app.py 不含 `render_etf_ai(gemini_fn=gemini_call)`。仍為靜態 grep，無法排除字串動態呼叫（INFERENCE，機率低）。（複驗更正）：原組引用「`app.py:41` 註解稱功能已併入戰情室 AI 總結」**不實**——該註解實為「`render_etf_portfolio / render_etf_ai / render_grape_ladder` 的呼叫已搬進 💼 戰情室」，且對 `render_etf_ai` 並不屬實（戰情室只呼叫 portfolio 與 grape）；「已被取代」依據不足，不得引用該註解 |
| C-30 觀察池觸發推播 | cron | 無 | — | 🚫 明確不再需要／不應搬入 | 否 | `watchlist_triggers.py` | **寫外部系統**（LINE／TG）。狀態判斷 🚫（AI 盤點建議不搬入；最終認定屬客戶；不構成任何舊 UI 刪除授權）：理由＝已被取代／重複，**不是**「非 UI 能力」——`push_watchlist_signals.yml` 檔內自述「排程已停用（user 2026-08-23）：與「每日持股續抱/換股推播」重複」，僅保留 `workflow_dispatch`（重驗 @15cd8fff）。~~待裁示~~ 為第五種狀態，已移除；~~原 🚫~~ 的舊理由「非 UI」已捨棄，改採此一致標準。【decision-note：待客戶裁示 S11】 |
| C-31 心理檢查＋勝利方程式＋今日禁止操作（複驗新增） | `section_psy_checklist.py::render_psy_checklist_section` | **無**；`page_inspect.py` 的 `STOCK_DETAIL_SECTIONS` 列「心理檢查」但未接線 | 責任方向 🎯 標的（現行 nav：🔬 查一檔／🔍 找標的）明細／⚡（歸屬待 IA Decision Gate；內容去留見 S7） | ⬜ 未覆蓋 | 半（`STOCK_DETAIL_SECTIONS` 列「心理檢查」，`DETAIL_WHERE` 有指路到舊分頁；與 🎯 A-33 同項、口徑一致） | 5 條勝利方程式門檻、4 條禁止操作條款；`monthly_loss_pct` | ⛔ 行為紀律規則，Stage B 不得改；與 C-19 共用 `monthly_loss_pct` 缺陷；輸入（3 checkbox）似不寫入任何地方（INFERENCE） |
| C-32 每週大盤報告推播（複驗新增） | `push_weekly_report.yml`／`scripts/push_weekly_report.py` | 無 UI | 若客戶要在 ⚡ 看「今天推了什麼」或手動觸發＝新能力（S11） | ⬜ 未覆蓋 | 否 | 大盤定調＋逐檔體檢＋AI 建議 | **寫外部系統**（LINE）；內含「AI 建議」，應納入 DEC-054 第 5 點（AI 不得創造客觀資料或目標價）檢視；不得因整理 UI 而動。cron 重驗 @15cd8fff：`push_weekly_report.yml` 啟用中（`0 21 * * 0`）。狀態判斷：啟用中、寫外部、含 AI 建議 ⇒ 不符 🚫 容許理由，新 UI 無對應入口 ⇒ ⬜（~~待裁示~~ 為第五種狀態，已移除）。【decision-note：待客戶裁示 S11】 |
| C-33 每日選股訊號推播（複驗新增） | `push_daily_signals.yml`／`scripts/push_daily_signals.py` | 無 UI | 同 C-32 | 🚫 明確不再需要／不應搬入 | 否 | 選股前 N 名 | **寫外部系統**（推播）；僅 `workflow_dispatch`。狀態判斷 🚫（AI 盤點建議不搬入；最終認定屬客戶；不構成任何舊 UI 刪除授權）：理由＝已被取代／重複——`push_daily_signals.yml` 檔內自述「排程已停用（user 2026-08-23）：改由「每日持股續抱/換股推播」整合「換入候選」，此則全市場選股清單對 user 重複」（重驗 @15cd8fff）。~~待裁示~~ 為第五種狀態，已移除。【decision-note：待客戶裁示 S11】 |

**Coverage 計數（重算 @15cd8fff：逐列數上表第 5 欄；調查組原計數 30 列 ✅9／🟡2／⬜15／🚫4；上一版複驗計數 ✅8｜🟡3｜⬜16｜🚫1｜待裁示5＝33，其中「待裁示」是第五種狀態，違反 DEC-085 §19.6，已移除）**：✅ 已覆蓋 8｜🟡 部分覆蓋 3｜⬜ 未覆蓋 19｜🚫 明確不再需要／不應搬入 3（合計 33）。與上一版差異＝C-10／C-19／C-32 改 ⬜（原「待裁示」）；C-30／C-33 改 🚫（原「待裁示」，改採「已被取代／重複」之一致理由，且不再以「非 UI 能力」為由）；五列皆另附 `【decision-note：待客戶裁示 S#】`（C-10／C-30／C-32／C-33→S11，C-19→S7）。**屬「⚡ 行動」盤點範圍標籤（依現行 nav 暫代，非歸屬判定）且為 ⬜ 者**（不含應歸其他責任方向者）：C-11、C-12、C-13、C-14、C-15、C-16、C-18、C-20、C-21、C-31（個股出場與環境行動語意）；C-19、C-10、C-32 為 ⬜ 但屬行為紀律／推播（見各列）；C-24、C-28 責任方向歸屬未定；C-04、C-17、C-23、C-27 偏 🎯 標的／🛡️ 持股方向。

#### 12.3.7 若未覆蓋：新 UI 應放哪裡／是否形成 dead-end（項目 7；候選非設計決定）

（候選位置只是候選，不是設計決定；任何版面變動須先出文字線框，DEC-003 ①）

1. **個股出場／進出場（C-11～C-16）**：兩條候選路線——(a) 放責任方向 🎯 標的（現行 nav：🔬 查一檔／🔍 找標的）的個股明細（`page_inspect` 本來就列了「什麼時候買賣」）；(b) 在責任方向 ⚡ 行動做彙總（只呈現「哪幾檔有出場跡象」），明細連回 🎯 標的。⚠️ 以上只是候選路線：⚡ 是責任方向、不是現行 nav 頁，**歸屬待 IA Decision Gate，本盤點不判定**。**dead-end：是。** 新 UI 使用者看到「汰弱 N／加碼 N」，卻沒有任何入口能看個股技術面出場或停損停利；且 `page_inspect` 的「什麼時候買賣」是 `unwired`，~~但**不指向舊 UI**（INFERENCE：未見指路句，需另一組核對）~~（更正：重驗 @15cd8fff，`page_inspect.py::DETAIL_WHERE` 明寫「現行入口仍在既有的 🔬 個股 / 🏦 ETF 分頁」，**有指向舊 UI**；與 C-31 列一致）。
2. **今日作戰室（C-18）**：DEC-081 Q1＝C 已指定移往未來的 ⚡ 行動（責任方向；現行 nav 尚無此頁）。目前 **半 dead-end**：舊今天頁 ⑤ 只是空殼、📊 大盤頁已把作戰室劃出去，兩邊都沒有。
3. **攻擊發動判定／結論句（C-20、C-21）**：Gate 檔列「⚡ 行動範圍（`DEC076-CONFIRM` ②）」。目前都只在舊 UI。
4. **再平衡指令／葡萄串（C-24、C-28）**：新 UI `unwired` 卡自己有寫為何缺（目標比例欄／L5 widget key），**指路句是「需先出線框」而不是去哪補**——是否形成 dead-end 取決於客戶要不要這兩項（G3）。
5. **ETF 組合計算輸入（C-23）**：新 UI 的壓測／VaR／配息現金流是吃**持股 Sheet**；舊 UI 能讓使用者**手填一個假想組合**試算。新 UI 沒有「假想組合」入口＝能力縮水（INFERENCE：是否需要要由客戶說）。
6. **逐檔燈明細（C-04）**：~~⬜ 但屬 🛡️ 小動作~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；DEC-085 §19.2 責任方向不等於現行 nav）⬜；責任方向傾向 🛡️ 持股（現行 nav：💼 我的持股），歸屬待 IA Decision Gate；影響「亮燈卻看不到原因」。

#### 12.3.8 哪些能力目前仍只能切回舊 UI（項目 8）

（新版模式下，舊 7 頁籤不畫；使用者要靠切換回舊版入口。FACT：`app.py` 新版模式 `st.stop()`，見既有矩陣 §0.5。）

- 三維出場訊號（個股頁＋組合出場欄＋AI 掃利空）：C-11、C-12
- 個股進場／出場訊號清單、停損／停利／目標價／加碼點：C-13
- 總資金→建議張數＋ATR 停損：C-14
- 即時操作建議（4 訊號共振）：C-15；操作狀態燈：C-16
- 長篇 AI 報告（組合／三型／首席顧問）：C-17
- 今日作戰室全部（唯一行動建議、5 分鐘清單、風險警示）：C-18
- 攻擊發動判定、各結論句＋行動建議：C-20、C-21
- ETF 組合輸入計算、再平衡交易指令、核衛 regime 版、其餘組合分析：C-23、C-24、C-25(regime 版)、C-27
- 葡萄串：C-28
- 逐檔燈明細展開：C-04
- 加碼的部署 %（「加碼 X%」）逐檔顯示：C-03 的一部分

#### 12.3.9 重複邏輯／重複入口／需 SSOT 收斂（項目 9）

| # | 發現 | 證據（FACT／INFERENCE） | 風險 |
|---|---|---|---|
| D1 | **建議持股水位出現在多處**：📊 大盤卡①、🚦 今天卡①、💼 持股 ⑤`build_position_cap_card`、舊作戰室「今日唯一行動建議」、舊 🎚️ 油門、`app.py` 全域置底常駐條（`_gl_slot`，複驗補第 6 份） | FACT；`page_hold.build_position_cap_card` 的 facts 自承「這**不是**全站唯一的持股水位算法」，另列 `market_alert_banner`（推播）、v4 否決權 `max_position`、`market_strategy.exposure_pct` 三套獨立算法；`section_op_recommendation` 也說「實際持股見 🎚️」 | 同一問題多個數字；⚡ 若再加一份會變第 5 份。只引用 `get_allocation`，不得另算 |
| D2 | **核心比例兩套**：L0 80/20（`CORE_TARGET_PCT`）vs `CoreSatelliteManager`（依 regime 0.60～0.85） | FACT：`page_hold` DEEP_SPECS 再平衡 `where` 明寫「不會改用 CoreSatelliteManager 頂替…同一頁出現兩個互相矛盾的核心比例」；舊 `etf_tab_portfolio` 同檔兩套並存 | 投資語意，G13 |
| D3 | **停損兩個常數並列**：`HARD_STOP_LOSS_PCT=7.0` 與 `STOP_LOSS_DEFAULT_PCT=8.0` 同畫面（硬停損／圖上停損線） | FACT：`section_when_buy_sell.py:200／:279／:375-376`；`shared/signal_thresholds.py:1038／:1055` | 兩個停損語意；G6 |
| D4 | **出場語彙三套**：①`suggest_action`（汰弱／強制停利／分批停利／暫停加碼／加碼 X%／巡航）②三維出場（強烈出場／建議減碼／留意／清淡）③操作狀態燈（加碼／警示／減碼／中性）＋DEC-054 七種 Action | FACT：分別在 `dividend_station.py:777`、`exit_signals.py:36-41`、`tab_helpers.py:134`、DEC-054 第 1 點；`CV1-FU-03` 已記「七種是否封閉清單」未裁 | ⚡ 若統一呈現，必須先有語彙對映（G2） |
| D5 | **「全清時說續抱」**：舊 `_render_ai_summary` 在 `reds` 與 `adds` 皆空時寫「今日無汰弱紅燈、無 235 加碼觸發 —— 續抱、定期定額即可」，不看**判不全但沒 error 的列**（`unjudged_n`，`_render_layer1` 才算）。（複驗更正）：原組寫「不看抓取失敗」**不實**——緊接著會另印 `⚠️ N 檔抓取失敗未納入判斷`（約 690–692 行）；屬實的是成功橫幅與失敗 caption **同時出現造成語意打架**，且不看 `unjudged` 列；`_render_switch_advice` 寫「✅ 持有部位無健檢紅燈 —— 無汰弱換出需求」亦同。新 UI `cruise_or_gap()` 要求每列每盞適用燈都判得出才准講「沒事」 | FACT（讀 `etf_tab_dividend_station.py:671-696／:628-668` 與 `page_hold.build_action_card` docstring） | 搬 ⚡ 時**不可沿用舊句**。屬 `not evaluated ≠ safe`（DEC-040） |
| D6 | **AI 摘要重複**：作戰室 ⑥ AI 摘要（今天頁 stub）、持股 ⑦AI 戰情總結、持股舊 ✍️、個股組合 AI 報告、📖 憑什麼 AI 問答 | FACT：Gate 檔 :106 寫「AI 摘要以 X11『問 AI』代替」 | ⚡ 是否需要自己的 AI 區塊＝G8 |
| D7 | **`etf_portfolio_rows` 隱藏耦合**：只由舊 UI 寫（`etf_tab_portfolio.py:451`、`etf_tab_dividend_station.py:164`），下游有 `grape_ladder`、`tab_sector_flow`、`portfolio_linkage`；新 UI 從不寫（`page_hold` 只在註解提到） | FACT（`grep -rn etf_portfolio_rows --include=*.py src app.py`，複驗實測 **20 行**（樣式不同，原組寫 13 行；寫入點仍只有 `etf_tab_portfolio.py` 約 451 與 `etf_tab_dividend_station.py` 約 164）） | 任何要把葡萄串／組合計算搬進新 UI 的人，必須先決定輸入從 `holdings_service` 取，而不是繼續靠舊頁副作用 |
| D8 | 推播邏輯與畫面邏輯共用 `build_station_digest` 與 `suggest_action`（DEC-045 要求一致）；`market_alert_banner` 另有一套目標持股水位常數 | FACT（`etf_tab_dividend_station.py:_render_layer1` 註解、Gate 檔 E12） | 若 ⚡ 要顯示「今天推了什麼」，必須用同一個 digest，不得重算 |
| D9 | `etf_tab_ai.render_etf_ai` 無 caller，卻仍被 `etf_dashboard.py:57` re-export | FACT | 死碼；依 §-1 不主動動工，只登記 |

#### 12.3.10 高風險投資語意（項目 10；Stage B 不得自行改定義）

**通則：Stage B 對下列項目一律只能「原樣顯示／原樣引用 L2·L3·L0 的結果」，不得改定義、不得換門檻、不得合併成單一分數、不得自創加減碼比例或新 Action 語彙。需動者一律標「需客戶裁示」（第 11 節）。**

| 項 | 現行定義位置 | 為何高風險 |
|---|---|---|
| 235 加碼燈（VIX×週線×20 週布林 z；`VIX_LIGHT1/2/3=20/25/30`、`Z_LIGHT1/2/3=-1/-2/-3`）、加碼金比例 20／30／50% | `shared/dividend_station_thresholds.py`；`dividend_station.py::light_235` | 門檻＋「部署多少閒置資金」＝加碼比例，DEC-053 要求正式加減碼比例須經驗證程序（G4） |
| 衛星停利：個股損益% ≥ 15%；ETF 停利：週布林 z > +2σ 分批／> +3σ 強制 | 同上；`flag_take_profit` | 出場規則 |
| 80/20 目標與 regime 版核衛比 | 同上；`CoreSatelliteManager` | 配置規則，兩套（G13） |
| `suggest_action` 優先序（汰弱＞停利＞暫停加碼＞加碼＞高溢價＞巡航） | `dividend_station.py::action_branch`（:751） | DEC-045 要求不得改優先序／不得新增 action semantics |
| 健檢 A/B/C/D（吃本金、夏普<0、季線、折溢價）、個股汰換（財報 grade C/F＋KD） | 同檔 `health_a…d`、`assess_stock`；`STOCK_SWAP_GRADES=("C","F")` | 汰弱＝出場規則 |
| 三維出場（命中維度數→等級）、技術轉空判定、利空新聞信心門檻（50） | `exit_signals.py`、`compute_tech_bearish` | **含 LLM 維度**；DEC-054 第 6 點「強 Action 不得只靠生成式 AI」（G5） |
| 個股進出場訊號、停損 7%／8%、5MA 停利、目標價＝現價＋20 日震幅、加碼點、ATR 停損、單筆風險 1.5%、建議張數 | `section_when_buy_sell.py`、`calc_atr_stop / calculate_position_size` | Position Sizing（CV1-FU-04）、「目標價」詞（DEC-022 保留非 AI 目標價仍受限）（G6） |
| 4 訊號共振判定（≥3 積極進場／≥2 小倉／否則不操作；「停損設健康度跌破 60」） | `section_op_recommendation.py`（inline 3、2、60） | 進場規則＋inline magic number（§3.3），Stage B 不得「順手抽常數改值」 |
| 操作狀態燈合議規則 | `classify_stock_status_lamp`（`GRP_*`） | 加碼／減碼語意 |
| 今日作戰室：regime→「逢回布局核心部位／區間操作／優先保留現金、嚴設停損」；乖離／融資／外資／廣度警示門檻（融資 >閾值 極危、年線 ±`_BIAS240_RED`、外資賣超 <-20 億、上漲家數 <35%） | `section_warroom.py` | inline `-20`、`35` 兩個數字未走 SSOT（重驗 @15cd8fff 為 FACT：`section_warroom.py` 約 215 行 `_wr_fnet < -20`、約 220 行 `_adl_r < 35`；~~讀碼 :274-290~~ 行號更正）；行動語句屬「多空判斷字樣」，與 `VN1-MT-TREND-DEF` 相鄰 |
| 月虧損停機 -10%／7 天 | L0 `signal_thresholds` | 行為紀律規則，標 DESIGN；輸入無來源（G7） |
| 攻擊發動（三環公式、SSS/A/B 分級）、VIX 否決結論句、§八 策略矩陣 | `section_mid.py`、`allocation_service` | 持股上限與進攻語意；RC-VISIBILITY（Risk Cap 顯示）未過，不得在 ⚡ 顯示獨立 Risk Cap 數字（DEC-081 Q2-2） |
| 建議持股水位（Risk Cap／姿態油門／VIX 天花板取最低） | `allocation_service.get_allocation` | Risk Cap 計算與顯示 Gate（C2b＋RC-VISIBILITY）；缺有效上限須「無法判定」 |
| 再平衡（目標權重、容忍帶、股數換算）與葡萄串「最佳組合」 | `portfolio_gates`、`grape_ladder.recommend_income_ladder` | DEC-022 暫時保留的再平衡三項限制（G3）；葡萄串的 10 檔高股息清單與星等門檻是策略參數 |
| 換股建議的 stance（攻守）與選股池候選 | `build_switch_advice` | 汰弱換強語意（G1／G2） |
| PIT／look-ahead | 本頁範圍的規則多為「當下狀態」判讀，**未見回測**；ⓘ 本組未逐一驗證各燈的資料日 | INFERENCE；資料新鮮度另屬 Data Health 範圍 |
| AI 結論 | C-09／C-12／C-15／C-17／C-29 | AI 不得創造客觀資料或目標價（DEC-027／DEC-054 第 5 點）；新 UI 的 ⑦ 已附揭露，**搬入 ⚡ 時揭露不得縮減** |

- **（複驗新增）心理檢查／勝利方程式／今日禁止操作（C-31）**：5 條勝利方程式門檻與 4 條禁止操作條款屬行為紀律規則，Stage B 不得改；與 C-19 月虧損停機共用同一個無寫入點的欄位。

- **（複驗修正）三維出場**：上表「三維出場」列的「含 LLM 維度；DEC-054 第 6 點『強 Action 不得只靠生成式 AI』」須讀作——🔴 強烈出場＝三維全中，LLM 為**必要非唯一**；組合表未按「🤖 AI 掃利空」時最高只到 🟠（兩維）。待裁示形狀見 §12.5 S5（Stage B 前置候選問題／decision-note，非逐題裁示要求）。

### 12.4 跨頁：Sheet／portfolio／watchlist SSOT 繞過與重複入口／重複邏輯

> 基準：程式碼＝main @ `15cd8fff`（4e6bf8ee→15cd8fff 僅 docs 變更，0 程式碼變更，已實測 `git diff --name-only`）。**重驗 @15cd8fff**（Stage A v2，本節 12.4.1～12.4.4 的 code 宣稱已對 worktree 逐項重讀，更正處用刪除線標示；未逐項重驗者標「INFERENCE／未複驗」）。治理依據：DEC-085／`PROJECT_RULES.md` §19.3（SSOT：Sheet binding、portfolio、watchlist 等不得各頁維護第二套實作）。
>
> 彙整自三份調查與複驗。**成立範圍仍是各組列出的 grep 方法，全為單組＋單次複驗，非窮舉。** DEC-083 E 段明令**舊 UI 全留**，故下列「舊 UI 不走 SSOT」屬**已知分歧，不是違規**；真正未治理的缺口是 R5（舊「➕」仍寫入）與 R6（cron）。

#### 12.4.1 誰在讀／寫 Sheet 持股與觀察清單（SSOT 是否被繞過）

| # | 讀寫者 | 讀／寫哪本 | 走 DEC-083 SSOT（active Sheet＋👤 選定名稱）？ |
|---|---|---|---|
| R1 | 新 💼 `holdings_service.get_holdings`；`sector_flow_service._active_selection_tickers`（`page_find` 持股標示；現行 nav：🔍 找標的） | 👤 選定的一本組合／一份觀察清單 | ✅ 是 |
| R2 | 舊戰情室 `etf_tab_dividend_station.py::_load_holdings_from_portfolio`（重驗 @15cd8fff：ETF 通道 `_get_active_sheet_id()` 先讀 session、空則退回 `st.secrets`；個股通道 `_get_active_stock_sheet_id()` 只讀 session、不退回；兩通道皆取 `list_*(...)[0]`） | ETF 通道：`_get_active_sheet_id()`——**session 空時退回 secrets 部署預設**；個股通道：`_get_active_stock_sheet_id()`——不退回；兩通道各讀各的；各取**名稱排序第一本**（`_list_portfolios_names` 回 `sorted(names)`） | ❌ 否。新 UI 把「只有部署預設」判為 `ACTIVE_DEPLOY_DEFAULT_ONLY`＝未綁，所以**舊戰情室可能讀一本新 UI 視為「未綁」的 Sheet**（複驗更正，比「名稱排序第一本」更大） |
| R3 | 舊 📁 組合管理 | legacy 通道，使用者自選載入 | ❌ 否（舊 UI） |
| R4 | 舊 🔗 狀態列 `get_binding_state()` | legacy（`ssot=False`） | ❌ 否 |
| R5 | 舊選股網（`app.py` 內嵌）「➕ 加入觀察清單」`watchlist_service.add_picks_to_watchlist`（重驗 @15cd8fff：用 `_get_active_stock_sheet_id()`，空則 `raise`） | **寫入** `_get_active_stock_sheet_id()` 那一本（不 fallback）；清單名由舊下拉選 | ❌ 否。`ACTIVE_DIVERGED` 含「只綁了個股那一格」，此時新 UI 當未綁、舊「➕」仍寫那一本；`ACTIVE_OK` 時 Sheet 相同、只剩「清單名與 👤 選定無關」。**機制 [F]、使用者實際看到什麼 [I]（DIVERGED 實機畫面未驗）** |
| R6 | `scripts/push_holdings_daily.py`（cron） | env `PORTFOLIO_SHEET_ID`／`STOCK_PORTFOLIO_SHEET_ID`；兩個 Sheet 皆讀持股與觀察清單；`gsheet_sa_reader.py::read_holdings`（重驗 @15cd8fff）**聯集所有命名組合、以 normalize 後 ticker 去重、保留首見**（同代號不同均價列**丟棄**，只 log）；`_build_entries` 再做持股>觀察清單去重 | ❌ 否（與 👤「選定一本」語意不同，差異是**資料丟棄**而非攤平；`page_me.KNOWN_LIMITS` 已揭露「排程與本頁選哪本無關」，💼 的「推播出口」卡名未揭露） |
| R7 | `portfolio_manager.parse_sheet_id` | 委派 L0 `shared.sheet_id` | ✅（委派；矩陣 §7.2 的 4 份解析已收斂為 1 份） |
| R8 | `sector_flow_service._collect_stock_watchlist_tickers`（舊 `tab_sector_flow.py` 呼叫）；`portfolio_binding_service.py`（~~約 216 行~~ 重驗 @15cd8fff：該檔內有 `_gsp._get_active_sheet_id()` 呼叫，位置改以符號描述） | 個股 Sheet **所有**觀察清單（不受 👤 選定影響；重驗 @15cd8fff：舊 `tab_sector_flow.py` 以 `stock_portfolio_sheet_id` 呼叫 `get_sector_flow_view` → `_collect_stock_watchlist_tickers`；新 🔍 找標的 走 `use_active_selection=True` → `holdings_service.get_holdings`，不經此路）；直呼 `_get_active_sheet_id` | ❌ 否（舊管線） |
| — | 另：`etf_portfolio_rows` 隱藏耦合 | 只由舊 UI 寫（`etf_tab_portfolio.py`、`etf_tab_dividend_station.py`；重驗 @15cd8fff：`st.session_state['etf_portfolio_rows'] =` 僅此 2 處），下游有 `grape_ladder`、`tab_sector_flow`、`portfolio_linkage`、`portfolio_analysis_bridge`；`src/ui/views/` 內無寫入（`page_hold` 僅在說明文字中提及） | ❌ 任何要把葡萄串／組合計算搬進新 UI 的人，必須先決定輸入改從 `holdings_service` 取，不能繼續靠舊頁副作用 |

方法：`grep -rn "_get_active_sheet_id\|_get_active_stock_sheet_id\|list_portfolios\|list_stock_watchlists\|load_stock_watchlist\|get_holdings"` 於 `app.py src shared scripts`（排除 tests、L1 本體）；單組＋複驗重做一次，**不含 `importlib`／字串動態載入**。重驗 @15cd8fff：同 pattern 再跑一次，命中的讀寫者與 R1～R8 一致，未發現新增讀寫者（仍為單組重跑，非窮舉）。

**⚠️ 加入觀察清單寫的是「個股通道」**：選股網（現行 nav：🔍 找標的 對應的舊功能）的 ➕ 屬寫 Google Sheet 的 High 操作（`watchlist_service` → `gsheet_portfolio::add_to_stock_watchlist`），新 UI 兩頁零 Google 寫入（`page_hold` 另以 AST 黑名單釘死唯讀，檔頭宣稱；INFERENCE／未複驗：本輪未跑該測試）。

#### 12.4.2 重複實作（同一件事兩份以上）

1. **選股網兩份**：舊 `app.py` 內嵌（直呼 `yield_screener.fetch_pe_name_maps` 與 L3）vs 新 `page_find.py::load_screen_result`（全走 L3；符號重驗 @15cd8fff 存在）。排名同源 `get_ranked_picks`，但**前處理不同**：舊＝取數失敗只 `print`、名單照出（畫成「目前沒有符合的標的」）；新＝勾選因子輸入缺→紅卡「選股中止」。**兩套並存期間，同一組條件可能一邊出名單、一邊中止。**
2. **熱力圖兩份入口**：舊 `etf_render.py::render_sector_heatmap`（widget key `heatmap_market`／`heatmap_period`／`heatmap_refresh`，重驗 @15cd8fff）vs 新 `sector_heatmap_service`＋`sector_heatmap_render`（頁面 key 前綴 `p02v_`，見 `page_find.py`）；類股宇宙已上移 L0 `shared/sector_heatmap`。
3. **持股讀取兩份**：L5 私有 `_load_holdings_from_portfolio` vs L3 `holdings_service`（行為已分歧：舊取第一本、新取選定）。
4. **VaR／壓測／配息兩份**：`portfolio_deep_service`（新）vs `etf_tab_portfolio` inline（舊）；全站至少三處「張→股」乘法（`portfolio_deep_service::_lot_to_shares`、`dividend_station_service::compute_portfolio_totals`、`compute/sector_flow.py`〔檔頭自述走 `SHARES_PER_LOT`〕；三個符號 @15cd8fff 皆存在，「乘法逐處等價與否」INFERENCE／未複驗）。
5. **ETF 健檢引擎兩套（舊 UI 內）**：`etf_calc._compute_etf_warroom_row` vs `dividend_station` ETF 健檢 A–D（符號重驗 @15cd8fff 存在）；新頁只接後者（INFERENCE：本輪未逐項比對）。
6. **綁定 UI 三份**：側欄 inline、`portfolio_binder`（狀態列／戰情室空狀態／組合管理）、👤 我的 `page_me`（不重用 binder）；寫入契約已收斂為 L1 `apply_sheet_binding` 一支，但**元件是三份**。
7. **持有列編輯兩份**：📁 組合管理 data_editor（回寫 Sheet）vs ETF 組合 data_editor（session-only、不回寫）→ 使用者會以為在改 Sheet。
8. **「健康」三把尺同名**：技術六因子 `calc_health_score`／財報體檢綜合分／持股頁序數燈號（`HOLD_SCALE_SHAPE`）。
9. **AI 觸發各自實作**：舊 UI 至少五套（選股網 `render_tab_summary`〔`app.py`〕、個股 `btn_ai_sum2`、多檔 `t3_ai_gen`、ETF 單檔 `etf_tab_single.py` 的「生成 AI 白話總結」鈕、熱力圖 `sector_ai_btn`；~~ETF `etf_s_ai`~~ 重驗 @15cd8fff：該 key 字串不存在，ETF 單檔鈕的 key 為變數 `_ai_sum_key`），另有個股組合 AI 報告／AI 掃利空、💼 舊 ✍️；新 UI 目前有 💼 `⚡ 生成 AI 總結` 與 📖 憑什麼的 AI 問答（後者來自盤點範圍標籤「⚡」組的觀察，不等價）。Stage B 設計 AI 層時應收斂為單一入口並與資料層分區（Data≠AI）。
10. **預設值寫死**：舊 `tab_stock_grp` 預設 10 檔、`etf_tab_grp_compare` 預設 5 檔 ETF、`etf_tab_single` 預設 `0050`、`tab_stock` 預設 `2330`；新頁一律空白（更誠實，但「預設代碼讓人一鍵看到示範」的行為消失）。
11. **L5 自建 cache／取數**：`etf_tab_smart.py` 5 個 `@st.cache_data`（V-SMART-CACHE-1，已登記）；`section_batch_fetcher` 用 `shared.app_cache._save_cache('t3v2', …)` 寫本機檔；`tab_stock_picker.py` 的 V-PICKER-PRIV-1（已登記）與 L5 自行 `import requests`（重驗 @15cd8fff：該檔內確有多處；是否「未登記」僅依 `CLAUDE.md` §8.2.A.2 現文，未複驗）。5 個 `@st.cache_data` 已重驗（`_cached_price`／`_cached_peer_prices`／`_cached_holdings`／`_cached_price_long`／`_cached_zh_name`）。
12. **死碼**：`render_smart_ticker_input` 零 production caller（重驗 @15cd8fff：對 `src app.py scripts` grep，除定義外無呼叫；`tests/test_etf_smart_ticker_wiring.py` 以存在性斷言引用，不是 caller）；`render_etf_ai` 無 production caller（重驗：`app.py` 僅註解提及；仍被 `etf_dashboard.py` 以 `# noqa: F401` re-export，~~`etf_dashboard.py:57`~~ 行號改以符號描述）。**此為單組 grep；依 BRIEF，「死碼」不構成 🚫 理由，另需獨立重驗方可作為 Coverage 判斷依據。**依 `CLAUDE.md` §-1 只登記，不主動動工。

#### 12.4.3 重複入口（同一個問題多個數字／多個地方）

1. **建議持股水位／「出手到幾成」至少 6 份**：📊 大盤卡①、🚦 今天卡①、💼 持股 ⑤ `build_position_cap_card`、舊作戰室「今日唯一行動建議」、舊 🎚️ 油門、`app.py` 全域置底常駐條 `_gl_slot`（複驗補第 6 份；`_gl_slot` 符號 @15cd8fff 存在於 `app.py`，「六處皆顯示建議持股水位」的逐處內容未逐項重驗，INFERENCE）。`page_hold.py::build_position_cap_card`（符號重驗 @15cd8fff 存在）的 facts 自承「這**不是**全站唯一的持股水位算法」，另列 `market_alert_banner`（推播）、v4 否決權 `max_position`、`market_strategy.exposure_pct` 三套獨立算法。行動類頁面（盤點範圍標籤「⚡」，現行 nav 尚無對應頁）若再加一份會變第 7 份；只能引用 `get_allocation`，不得另算（呼應 §19.3 SSOT）。
2. **「重新載入／重新讀取」三種語意**：舊全域 `clear_read_cache()`（`gsheet_portfolio.py` 定義、`etf_tab_dividend_station.py` 呼叫，重驗 @15cd8fff；`SHEET-GLOBAL-CLEARS` 為 docs 內的議題代號，非 code 符號）、👤 我的本人限定 `reload_my_sheet_reads`（不 `.clear()`，DEC-083 B5）、新 💼 **無**（重驗：💼 檔頭說明刻意不呼叫 `clear_read_cache()`）。強制重抓（`st.cache_data.clear()`）是 process 全域，原樣搬入會清所有使用者的快取。
3. **「推播」一詞**：⑦ 卡名「唯一推播出口」vs 真推播 cron（見 12.4.4）；舊鈕「讓 AI 潤成推播文字」也不推送。
4. **「切回舊版」的步驟只在 👤 我的 `SWITCH_BACK_TEXT` 說明**（側欄 radio「不使用（用下方原功能）」，`app.py` 該 radio 的 `index=0`，重驗 @15cd8fff；選項字串 `OLD_UI_NAV_OFF` 存在於 `page_me.py`／`page_market.py`）；💼／🔍 的指路句（含客戶逐字句 `CONTENT_EDIT_OLD_UI_WHERE`）沒有說怎麼切。
5. **核心比例兩個定義**（舊 UI 內）：L0 固定 80/20（`shared/dividend_station_thresholds.py` 的 `CORE_TARGET_PCT=80.0`／`SATELLITE_TARGET_PCT=20.0`）vs `CoreSatelliteManager` 依總經位階 0.60–0.85（重驗 @15cd8fff：`portfolio_manager.py::_CORE_RATIO` bull 0.60／neutral 0.70／caution 0.80／bear 0.85）；新頁只採前者並明寫不以後者頂替（否則「同一頁出現兩個互相矛盾的核心比例」）。
6. **出場語彙三套**：`suggest_action`（汰弱／強制停利／分批停利／暫停加碼／加碼 X%／巡航）、三維出場（強烈出場／建議減碼／留意／清淡）、操作狀態燈（加碼／警示／減碼／中性）；另有 DEC-054 七種 Action（`CV1-FU-03` 未裁是否封閉清單）。
7. **兩個停損常數並列**：`HARD_STOP_LOSS_PCT=7.0` 與 `STOP_LOSS_DEFAULT_PCT=8.0`（皆在 `shared/signal_thresholds.py`，值重驗 @15cd8fff）同畫面（`section_when_buy_sell.py` 同檔同時使用）。
8. **同名兩個「凍結」路徑**：手動 UI（`app.py` 選股網 → `forward_test_service.freeze_current_picks` → Google Sheet，使用者勾的因子，**含空頭濾網**：畫面把 canonical regime 傳進 `get_ranked_picks`）vs cron（`update_forward_test_freeze.py` → `freeze_current_picks_local` → 本機 git 追蹤 `data_cache/forward_test/picks.parquet`，**全 5 因子、未傳 `regime`＝None**，`get_ranked_picks(top_n=max(args.top_n,300))` 後取 `head(args.top_n)`，預設 `FORWARD_TEST_FREEZE_TOP_N=20`；以上重驗 @15cd8fff，`app.py` 註解亦自述凍結 cron／MCP／推播三處維持 `regime=None`）；對帳讀「本地 ∪ Google Sheet」去重（`CLAUDE.md` §2.3）。**兩種 cohort 的語意不同**（複驗確認）。

#### 12.4.4 推播 cron 的範圍（複驗更正：4 條，不是 2 條；重驗 @15cd8fff：`.github/workflows/push_*.yml` 恰 4 檔，排程狀態與 cron 字串逐檔讀 `on:` 區塊確認）

| cron／workflow | 排程 | 讀什麼 | 寫到哪 | 備註 |
|---|---|---|---|---|
| `push_holdings_daily.yml`／`scripts/push_holdings_daily.py` | 啟用，`cron "30 22 * * 0-4"`（UTC 週日～四 22:30＝台灣週一～五 06:30） | Service Account 讀 env 兩個 Sheet（持股＋觀察清單，見 R6；`scripts/push_holdings_daily.py` 迴圈讀 `PORTFOLIO_SHEET_ID`／`STOCK_PORTFOLIO_SHEET_ID`） | LINE／Telegram | 與畫面共用 `build_station_digest`／`suggest_action`（DEC-045 要求一致）；選配 Gemini 潤稿 |
| `push_weekly_report.yml`／`scripts/push_weekly_report.py` | 啟用，`cron "0 21 * * 0"`（UTC 週日 21:00＝台灣週一 05:00） | 追蹤清單來自使用者「發布到網路」的 Google Sheet **CSV**（`WEEKLY_WATCH_CSV_URL`，非 Service Account；重驗 @15cd8fff 檔頭自述）→ 大盤定調＋逐檔體檢＋**AI 建議** | LINE | 原組漏列；內含「AI 建議」，應納入 DEC-054 第 5 點檢視 |
| `push_watchlist_signals.yml`／`scripts/push_watchlist_signals.py` | 僅 `workflow_dispatch`（排程已停，檔內自述：user 2026-08-23 停用） | ~~Service Account 讀觀察清單~~（更正：重驗 @15cd8fff，`scripts/push_watchlist_signals.py::_collect_watchlist` 讀公開 CSV，來源優先序 `--csv-url` > `WATCHLIST_CSV_URL` > `WEEKLY_WATCH_CSV_URL`，並複用 `push_weekly_report` 的解析函式） | LINE／TG | 均線跌破／技術轉空／三維出場觸發 |
| `push_daily_signals.yml`／`scripts/push_daily_signals.py` | 僅 `workflow_dispatch`（排程已停，檔內自述：user 2026-08-23 停用） | 選股前 N 名（`get_ranked_picks`，`top_n=max(args.top_n,300)`） | 推播（LINE／Telegram） | 原組漏列 |

- 以上為「推播（寫外部通訊系統）」的全部已知 cron（`.github/workflows/push_*.yml` 掃描＋複驗；**單組＋單次複驗，非窮舉**）。另有 `update_*`／`recalibrate_*`／`calibrate_*`／`export_db` 等 workflow 含 `git commit`／`git push`（重驗 @15cd8fff：10 個檔案命中），屬資料落地、不在本表範圍，本輪未逐檔盤點其寫入目標~~（INFERENCE／未複驗：是否另有寫 Google Sheet 者）~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；重驗 @15cd8fff）`risk_cap_history_poc.yml`／`scripts/risk_cap_history_poc.py` 會經 `build_writer_client` 寫 Google Sheet，但僅 `workflow_dispatch`（無排程），且受 `PRODUCTION_WRITE_APPROVED=False` 與 `load_writer_credentials_or_refuse` 閘門擋下（該旗標為 False 期間 `--write` 一律 exit 2）；其餘 workflow 的寫入目標仍未逐檔盤點（INFERENCE／未複驗）。**這四條與任何 UI 都沒有入口關係**（靜態 grep，未排除 getattr／字串動態引用；INFERENCE）（重驗 @15cd8fff：`app.py`／`src/` 對 `push_*` 腳本名只在註解／docstring 出現，無 import 或 subprocess 呼叫）；任何手動觸發入口＝寫外部系統，須客戶核准（`PRODUCTION_WRITE_APPROVED` 類治理、§12.5 S11）。
- 這四條**是否有重複推播同一件事**（例如日報與週報、持股推播與觀察池推播的內容重疊）：**本輪未查證，不下結論**（單組盲點）。


### 12.5 Stage B 前置候選問題（decision-notes）

> 三份調查的缺口（🎯 10 項、🛡️ 10 項、⚡ 13 項＋複驗新增 1 項）**合併去重**為 **S1～S28 共 28 項**；對照見 12.5.3。每項格式：問題｜為何需裁示（＝為何屬 decision-note）｜候選方案（≤3）｜總管推薦與理由｜相關 DEC。
> **定位（本輪 v2 更正）**：S1～S28 是 **Stage B 前置候選問題／decision-notes**，**本輪不要求客戶逐題裁示**；由 Stage B 草稿把它們收斂為**少量 Decision Gates**，再依 DEC-082 在 **Stage C** 送客戶（Stage C 才是正式客戶 Gate）。S 項內容與「總管推薦」保留供 Stage B 參考。
> ~~⛔ **客戶尚未裁示前，Stage B 不得開始**（DEC-082）；~~（**更正原因**：DEC-082 的 Stage A→B→C→D 中，停手等客戶裁示的是 **Stage C**〔「草稿完成後必須停手」〕；Stage B 之前並無「須先過客戶裁示」的條文，舊句誤引 DEC-082。重驗 @15cd8fff：DECISIONS.md DEC-082 要點 3～5。）
> **本輪工作安全停點／總管流程（非 DEC-082 條文）**：本批在 Stage A 盤點交付後停手，不自行進 Stage B。這是總管對本輪範圍的安排，不是客戶裁示、不是 DEC-082 的規定。
> **Stage B 約束（DEC-085／`PROJECT_RULES.md` 第 19 節）**：S 項涉及的頁名 📊／🎯／⚡／🛡️／👤／🩺 是**長期責任方向**，**不等於**現行 nav 名稱或既有 view 一對一對映；對映屬後續 IA Decision Gate，本節不決定。本節凡指現行頁面者以「責任名（現行 nav：…）」書寫，現行 nav 名依 `shared/ia_nav.py`：📊 大盤／🚦 今天／🔍 找標的／🔬 查一檔／💼 我的持股／📖 憑什麼／👤 我的（⚡ 行動、🩺 資料中心尚無 view，DEC-085 讀碼事實）。任何新控制項、版面、分頁動線異動仍須先出文字線框（DEC-003 ①）。
> **decision-note 格式**：本節各 S 項**不是 coverage 狀態**。若矩陣其他表需引用，只能在狀態格**以外**加註 `【decision-note：待客戶裁示 S#】`；coverage 狀態僅四種（`✅ 已覆蓋`｜`🟡 部分覆蓋`｜`⬜ 未覆蓋`｜`🚫 明確不再需要／不應搬入`，DEC-085 §19.6）。
> ⚠️ **「總管推薦」欄由落盤組依三份調查彙整擬稿，未經第二組驗證，仍待總管確認後才送客戶**（`CLAUDE.md` §-1.5.D 請示規範：商業語言＋附推薦方案；§-2 規則 6）。推薦只是「建議先怎麼走」，**不是**決定任何投資語意。
> **重驗註（@15cd8fff，worktree 實測）**：本節寫成事實的程式碼層級宣稱已逐條對 worktree 重驗；成立者保留，不成立者以刪除線＋更正原因標示，無法重驗者標 INFERENCE／未複驗。清單見各 S 項內的「重驗」標記。

#### 12.5.1 S 項清單

**S1｜⚡ 行動（責任方向；現行 nav：尚無此 view）的範圍，與「持股戰情室／買賣語意／作戰室」各歸哪個責任方向**
- 問題：⚡ 行動要收哪些能力？(i) 持股戰情室（汰弱／加碼／停利／換股／AI 總結——目前只掛在 💼 我的持股〔現行 nav〕唯讀顯示；歸屬待 IA Decision Gate）；(ii) 個股／ETF 買賣語意（停利停損、操作雷達、何時買賣、即時文字建議、ETF 留／觀察／換、標準差買賣帶、存股三大訊號——目前新 UI 一概沒有）；(iii) 今日作戰室。各自歸 ⚡ 行動、🛡️ 持股（責任方向）或 🎯 標的（責任方向）？**子問題：「查一檔／個股明細」（現行 nav：🔬 查一檔）歸哪個責任方向？**（DEC-072 把「找標的＋查一檔」寫為同一 🎯 標的主頁，DEC-085 又指明責任名≠現行 nav；對映屬後續 IA Decision Gate，本盤點不決定。）
- 為何需裁示：DEC-072 只說「僅盤點既有 deterministic action 能力」，例示射程仍 pending（`DEC076-CONFIRM` ②、`CV1-FU-02`、`CV1-FU-03`）；歸屬決定畫面結構（UI 異動）且牽涉買賣語意。
- 候選（皆為責任方向層級的候選，非現行 nav 改動）：(a) 戰情室留 🛡️ 持股責任方向，⚡ 行動只做「現在有什麼需要處理」的彙總並連回，個股買賣語意放 🎯 標的責任方向的個股明細；(b) 戰情室與買賣語意整組移 ⚡ 行動；(c) 維持現況，⚡ 行動暫不建，~~待 S2～S10 逐項釐清。~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；S 項不構成前置裁示）由 Stage B 收斂為 Decision Gate 後於 Stage C 處理；與 S2～S10 相關。
- 總管推薦：(a)。理由：戰情室目前已在 💼 我的持股（現行 nav）唯讀運作且有「沒判完就不准說沒事」的可信度閘門；⚡ 行動以引用同一份 L3 digest 為原則，避免多一份算法。（INFERENCE：推薦本身；歸屬待 IA Decision Gate。）
- 相關 DEC：DEC-072、DEC-081（Q1／Q4）、DEC-076、DEC-054。

**S2｜行動語彙：七種 Action 與現行語彙如何對映**
- 問題：DEC-054 的七種 Action（建立第一筆部位／加碼／續抱／暫停加碼／減碼／全部退出／無法判定）是否封閉清單？與現行語彙（汰弱／強制停利／分批停利／暫停加碼／加碼 X%／巡航）、三維出場（強烈出場／建議減碼／留意／清淡）、操作狀態燈（加碼／警示／減碼／中性）如何對映？
- 為何需裁示：統一呈現必須先有語彙對映，而對映本身是新的行動語意；`CV1-FU-03` 仍 open。
- 候選：(a) 封閉七種，由客戶審一張對映表；(b) 各處沿用現行語彙原樣，不統一；(c) 兩套並陳（不建議，易互相矛盾）。
- 總管推薦：先出**對映表草稿（只列現況，不新增語彙）**給客戶看，由客戶選 (a) 或 (b)。理由：不替客戶定義語意。
- 相關 DEC：DEC-054、DEC-045、`CV1-FU-03`。

**S3｜再平衡交易指令與葡萄串「生成提議」要不要進新 UI**
- 問題：舊 UI 會輸出「買進／賣出 N 股、金額」（由使用者填的目標權重驅動，全填滿且總和 100% 才判）；葡萄串無持股時以高股息 10 檔做「系統提議」。要不要搬？目標比例%存哪（目前 session-only，不存 Sheet；寫 Sheet＝High）？
- 為何需裁示：DEC-022 寫明「再平衡只做偏離提示／客觀對照／情境試算；禁一鍵再平衡按鈕、禁預設最佳配置推薦」，DEC-054 承接表第 5～7 列寫「DEC-022 暫時保留」，DEC-055 寫「不把 DEC-054 擴張到投資組合再平衡」；舊 UI 輸出的具體股數超出該字面。**複驗確認此張力屬實。**
- 重驗 @15cd8fff：「目標比例%目前無處輸入」成立（`page_hold.py::DEEP_SPECS` 再平衡卡自述帳本只有 name／ticker／lots／avg_price／updated_at 五欄、沒有目標權重；`portfolio_gates.py` 對無目標權重判「⚪ 無法判定」）；「全填滿且總和 100% 才判」成立（`portfolio_gates.py` 缺目標權重／總和≠100% 皆回無法判定）。「session-only、不存 Sheet」與「葡萄串無持股時以高股息 10 檔做提議」**未獨立重驗（INFERENCE／未複驗）**。
- 候選：(a) 新版暫不搬，仍留舊 UI，並把未接線卡的指路句改正（~~現葡萄串卡指向錯誤分頁~~〔更正原因：重驗 @15cd8fff，`page_hold.py::DEEP_SPECS` 葡萄串卡的 `where` 並未指向任何分頁，只說「要先讓現行實作能被外部重複掛載」；「指向錯誤分頁」找不到對應文字，降為 INFERENCE／未複驗，疑為前一版指路句〕）；(b) 只做偏離提示／情境試算（不出股數、不提議）；(c) 完整搬入（須先裁示 DEC-054 是否延伸，並決定目標%存放）。
- 總管推薦：(a)。理由：涉具體股數與寫入 High，且與既有 DEC 的張力未解；先修正 dead-end 指路即可。
- 相關 DEC：DEC-022、DEC-054、DEC-055、`CV1-FU-02`。

**S4｜235「加碼 X%」是否算 DEC-053 所稱「正式加減碼比例」；⚡ 可不可以逐檔顯示加碼金**
- 問題：現行 20／30／50% 閒置加碼金（`DEPLOY_LIGHT1/2/3_PCT`）是否視為 DEC-053 的「正式比例」？新 💼 現只顯示加碼**檔數**，不顯示逐檔加碼金（金額只在舊戰情表與 AI digest）。（重驗 @15cd8fff：`DEPLOY_LIGHT1/2/3_PCT = 20.0／30.0／50.0` 成立，見 `shared/dividend_station_thresholds.py`；`page_hold.py` 內 `deploy_pct`／「加碼金」0 命中、「加碼 N」事實列成立。**「金額只在舊戰情表與 AI digest」未重驗 L4 `station_cards.render_light_wall` 是否印金額 → INFERENCE／未複驗**。）
- 為何需裁示：**複驗更正：這是「待釐清」，不是已成立的違反**——DEC-053 全文只有標題＋「日後須經…才能進 production」，無內容條文；DEC-045 只重用 `suggest_action` 既有優先序、不新增比例；現行比例早於這些裁示。
- 候選：(a) 視為既有規則，新版可顯示逐檔加碼金（原樣引用 L2／L3，不改比例）；(b) 視為待驗證規則，新版只顯示檔數與燈號；(c) 顯示但加註「規則來源與驗證狀態」。
- 總管推薦：(c)。理由：資訊不縮水（對照 DEC-081 第 7 點）、不替客戶判定規則地位。
- 相關 DEC：DEC-053、DEC-045。

**S5｜三維出場含 LLM 維度：LLM 能否成為「強烈出場」的必要條件**
- 問題：🔴 強烈出場＝三維（利空新聞 LLM＋技術轉空＋籌碼倒貨）**全中**；LLM 維度是必要、非唯一依據。組合表未按「🤖 AI 掃利空」時最高只到 🟠（兩維）。是否可接受？要不要把 LLM 維度分開標示或降權？
- 為何需裁示：**複驗更正：字面上未違反** DEC-054 第 6 點（強 Action 不得「只」靠生成式 AI），待裁的是「必要條件」的地位；分開標示或降權是投資語意。
- 候選：(a) 維持現規則，UI 明示「含 AI 維度」；(b) AI 維度只作旁註、不計入分數；(c) 維持現狀不搬（留舊 UI）。
- 總管推薦：(a)；若搬入，卡面須明示哪一維度是 AI。理由：不改定義、符合 Data≠AI 分區揭露。
- 相關 DEC：DEC-054（第 5／6 點）。

**S6｜個股停損／停利／目標價／加碼點／Position Sizing 是否屬可帶入 ⚡ 行動／🎯 標的（皆為責任方向，非現行 nav）的「既有 deterministic action」**
- 問題：進出場訊號清單、硬停損 7%／停損 8% 兩個常數並列、5MA 停利、目標價（現價＋20 日震幅）、加碼點、ATR 停損、單筆風險 1.5% 與建議張數、4 訊號共振的即時操作建議（≥3 積極進場／≥2 小倉／否則不操作）、操作狀態燈。（重驗 @15cd8fff：`HARD_STOP_LOSS_PCT=7.0`、`STOP_LOSS_DEFAULT_PCT=8.0`〔`shared/signal_thresholds.py`〕成立；單筆風險 1.5% ＝ `POS_MAX_RISK_PCT=0.015` 成立；4 訊號共振 ≥3／≥2 為 `section_op_recommendation.py` 內 inline 判斷成立〔`_sig_count >= 3`／`>= 2`〕。5MA 停利、「現價＋20 日震幅」目標價公式、操作狀態燈**未重驗 → INFERENCE／未複驗**。）
- 為何需裁示：Position Sizing 正式規則仍是缺口（`CV1-FU-04`）；「目標價」一詞適用範圍（DEC-022 保留非 AI 部分仍受限）；「總資金」輸入框是新控制項。
- 候選：(a) 全數留舊 UI；(b) 僅搬純顯示的訊號清單與停損線，不搬 Position Sizing 與共振建議；(c) 全搬至 🎯 標的責任方向的個股明細（現行 nav：🔬 查一檔；歸屬待 IA Decision Gate）。
- 總管推薦：(a)；~~待 S1、S2 裁示後再議 (b)~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；S 項不構成前置裁示）(b) 由 Stage B 收斂為 Decision Gate 後於 Stage C 處理，與 S1、S2 相關。理由：避免在歸屬未定前搬進未核准的買賣語意。
- 相關 DEC：DEC-022、DEC-072、`CV1-FU-04`。

**S7｜心理檢查／勝利方程式／今日禁止操作（C-31），與月虧損強制停機（C-19）要不要留**
- 問題：C-31 的 5 條勝利方程式門檻、4 條禁止操作條款屬行為紀律規則；C-19「當月 < -10% → 建議暫停操作 7 天」的輸入 `monthly_loss_pct` **全站無寫入點**，警示永遠不會觸發，且預設 0 把「沒資料」當「沒虧損」（複驗確認）。（重驗 @15cd8fff：`git grep monthly_loss_pct` 全部 `*.py` 僅 4 處命中——`section_warroom.py` 檔頭說明與 `st.session_state.get('monthly_loss_pct', 0)`、`section_psy_checklist.py` 註解與 `.get('monthly_loss_pct')`——**無任何賦值／widget key**，「無寫入點」成立。C-19（作戰室）的 `.get(…, 0)` 預設 0 成立；C-31（心理檢查）側是 `.get(…)` 無預設、註解自稱「恆為未追蹤」，所以「把沒資料當沒虧損」**只適用 C-19 側**。）留或去？若留，當月累積報酬從哪來（新資料來源／可能讀 Sheet）？
- 為何需裁示：留／去是功能取捨；新增輸入來源＝新資料 Gate。
- 候選：(a) 兩者都不搬，C-19 列為已知死功能；(b) 搬 C-31（3 個 checkbox 不寫入），C-19 暫不搬；(c) 兩者都搬並先定義 `monthly_loss_pct` 來源。
- 總管推薦：(a)。理由：C-19 現況是死功能，搬入只會把「永不觸發」當成保護；C-31 ~~歸屬依 S1 再定~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；S 項不構成前置裁示）歸屬由 Stage B 收斂為 Decision Gate 後於 Stage C 處理，與 S1 相關（責任方向歸屬，非現行 nav）。
- 相關 DEC：DEC-081（Q1）。

**S8｜今日作戰室的內容界定，以及 ⚡ 要不要有自己的 AI 摘要區塊**
- 問題：「今天值得處理的事項」由哪些規則組成？舊作戰室 regime 一句話（「逢回布局核心部位」「優先保留現金、嚴設停損」）算不算行動語意？⑥ AI 摘要在 ⚡ 要不要存在（Gate 檔寫以「問 AI」代替）？
- 為何需裁示：目前作戰室**兩頁都沒有**（🚦 今天〔現行 nav〕⑤ 是空殼、📊 大盤〔現行 nav〕已移走）；內容界定是行動語意。（**INFERENCE／未複驗**：本輪未對 `page_today` ⑤ 與 `page_market` 重驗此句；且 `page_hold.py` 內仍有 `ACTION_RUN_WARROOM_LABEL` 指路字樣，作戰室入口現況需另行確認。）
- 候選：(a) 作戰室只放「客觀事實＋已核准規則的結果」，regime 一句話不搬；(b) 照舊搬 regime 一句話與 5 分鐘清單；(c) 暫不建。
- 總管推薦：(a)。理由：DEC-072 不新增未核准買賣語意。
- 相關 DEC：DEC-081（Q1／Q4）、DEC-072、`UIX-ACTION-PAGE`。

**S9｜⚔️ 攻擊發動判定與 §八／§三 結論句＋行動建議進不進 ⚡**
- 問題：三環公式＋SSS／A／B 火力分級、VIX 否決結論句（現金為王／停止加槓桿）、策略 1/3 矩陣、三大法人／融資結論卡。
- 為何需裁示：Gate 檔列「⚡ 行動範圍（`DEC076-CONFIRM` ②）」且首批不帶；與 `VN1-MT-TREND-DEF`（多空判斷字樣）相鄰；Risk Cap 顯示 Gate 未過，不得在 ⚡ 顯示獨立 Risk Cap 數字。
- 候選：(a) 留舊 UI；(b) 搬原始數值、不搬結論句；(c) 全搬。
- 總管推薦：(a)。理由：行動語句屬多空判斷字樣，~~待 S1 與 `VN1-MT-TREND-DEF` 裁示。~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；S 項不構成前置裁示）由 Stage B 收斂為 Decision Gate 後於 Stage C 處理；與 S1、`VN1-MT-TREND-DEF` 相關。
- 相關 DEC：DEC-081、DEC-076、`VN1-MT-TREND-DEF`。

**S10｜「建議持股水位／出手到幾成」的歸屬（~~現已 6 份副本~~ → 現況多處引用，數量待查）**
- 問題：只放 📊 大盤（責任方向；現行 nav：📊 大盤）還是 ⚡ 行動（責任方向；現行 nav：尚無 view）／💼 我的持股（現行 nav）也放一份引用？
- 重驗 @15cd8fff：~~「6 份副本」~~（**更正原因**：`git grep 'get_allocation('` 於 `app.py`、`etf_tab_ai`、`etf_tab_portfolio`、`etf_render`、`section_cross_ai`、`section_mid`、`section_traffic_light`、`section_warroom`、`macro_stock_link`、`section_industry_concentration`、`page_hold`、`page_today` 等處有實際呼叫，≥12 個 call site，且「副本」是指呼叫點、畫面顯示處、還是文案，原稿未定義；6 這個數字**無法重現**，降為 INFERENCE／未複驗）。「皆引用同一個 L3 `get_allocation` SSOT」成立（多處註解與 `page_hold.py`／`page_today.py` 自述皆指向它）。
- 為何需裁示：同一問題多個數字；缺有效 Risk Cap 須「無法判定」（DEC-040）；Risk Cap 正式數字的顯示受 Gate 拘束。
- 候選：(a) 只在 📊 大盤顯示，其他頁連回；(b) 各頁保留引用同一 `get_allocation` 結果；(c) 維持現況。
- 總管推薦：(b)，且硬性規定「只引用、不複算」。理由：現況已多處，統一來源比移除成本低。
- 相關 DEC：DEC-072（第 1 點）、DEC-040、DEC-083（G 段 Risk Cap 顯示禁令）。

**S11｜LINE／TG 推播：新 UI 要不要有入口；「推播」命名；cron 讀的 Sheet 與 👤 選定不一致**
- 問題：4 條 cron（見 12.4.4）沒有任何 UI 入口。要不要有「檢視今天推了什麼」或「手動觸發」？⑦ 卡「唯一推播出口」名稱與無推播動作不符？cron 讀 env Sheet（聯集去重、丟棄衝突均價）而非 👤 選定那一本，是否接受？
- 為何需裁示：手動觸發＝寫外部系統（`PRODUCTION_WRITE_APPROVED` 類治理）；改 cron 讀法屬資料來源語意。
- 候選：(a) 不做入口，只改卡名並在 💼 揭露「排程不依 👤 選定」；(b) 做唯讀「今天推了什麼」檢視；(c) 做手動觸發。
- 總管推薦：(a)。理由：最小改動、消除誤導，不碰寫外部系統。
- 相關 DEC：DEC-045、DEC-066 A／F（A＝`PRODUCTION_WRITE_APPROVED` 一次性旗標、F＝Daily Schedule NOT APPROVED；重驗 @15cd8fff：DEC-066 F 原文不是「production 寫入」總稱，已更正標籤）、DEC-054（第 5 點，weekly 含 AI 建議）。

**S12｜核心／衛星目標兩套（L0 固定 80/20 vs 依總經位階 0.60–0.85）以哪套為準**
- 問題：舊 UI 同一檔內並存兩個互相矛盾的核心比例；新 💼 只採固定 80/20 並明寫不以 `CoreSatelliteManager` 頂替。（重驗 @15cd8fff：`CORE_TARGET_PCT = 80.0`〔`shared/dividend_station_thresholds.py`〕成立；`CoreSatelliteManager` 的 `_CORE_RATIO` 為 bull 0.60／neutral 0.70／caution 0.80／bear 0.85〔`src/compute/strategy/portfolio_manager.py`〕，0.60–0.85 成立；`page_hold.py::DEEP_SPECS` 再平衡卡明寫「也不會改用 `CoreSatelliteManager` 頂替」成立；「舊 UI 同一檔內並存」＝`etf_tab_portfolio.py` 同時用 L0 80/20 與 `CoreSatelliteManager`，成立至兩者皆被呼叫〔line 61／78／758〕，未逐段追顯示位置。）
- 為何需裁示：配置規則＝投資語意。
- 候選：(a) 維持只顯示固定 80/20；(b) 兩套並陳並標明適用情境；(c) 淘汰其一。
- 總管推薦：(a)。理由：現況已一致且不新增語意；regime 版留舊 UI 待客戶決。
- 相關 DEC：DEC-072。

**S13｜「健康度」命名：技術六因子 vs 財報體檢分數（vs 持股頁序數燈號）**
- 問題：三把尺同叫健康（度／評分），舊 🔬 的 0–100 是技術六因子，新 🔬 的 0–100＋等第是財報體檢分，💼 是序數燈號。新 UI 是否兩把都呈現？如何命名區隔？
- 為何需裁示：命名涉及使用者對分數的理解；不得合併、不得並排成同一排名。
- 候選：(a) 新 UI 只呈現財報體檢分，並另行命名以與技術六因子區分（由客戶定名）；(b) 兩把都呈現並分別命名；(c) 維持現名並在卡面註明是哪一把。
- 總管推薦：(c)，待客戶另行定名。理由：最小改動、不替客戶改名。
- 相關 DEC：（命名無專屬 DEC；`page_hold::INSPECT_SCALE_SHAPE`／`HOLD_SCALE_SHAPE` 自述；重驗 @15cd8fff：兩常數存在，分別為「連續分數 0–100＋等第（沒有燈號）」與「序數燈號 ⚪／🟢／🟡／🔴（四盞燈取最嚴重，沒有分數）」，`page_why.py` 另有逐字同值副本）。

**S14｜選股網預設因子：新「EPS」vs 舊「估值（本益比低）」**
- 問題：新頁 `DEFAULT_FACTOR_KEY="eps_high"`（檔內有意識保留註解），舊頁預設為 `SCREEN_ANGLE_LABELS` 首項「估值便宜（本益比低）」。（重驗 @15cd8fff：`src/ui/views/page_find.py::DEFAULT_FACTOR_KEY = "eps_high"` 成立；`src/services/fundamental_screener_service.py::SCREEN_ANGLE_LABELS` 首項為 `"估值便宜（本益比低）": "pe_low"` 成立；舊 `app.py` 選股網區塊 `st.multiselect(list(SCREEN_ANGLE_LABELS), default=[list(SCREEN_ANGLE_LABELS)[0]])` 成立。）
- 為何需裁示：預設因子決定每位使用者未改動時的名單（複驗確認兩者不同）。
- 候選：(a) 沿用新頁 EPS；(b) 改回舊頁估值；(c) 不預設，要求使用者明確勾選。
- 總管推薦：(c)。理由：避免無意識下名單不同，也最符合「不替使用者選」。
- 相關 DEC：無專屬 DEC（單組觀察）。

**S15｜寫入類能力（➕ 加入觀察清單、🧊 凍結前 20 名、📊 對帳）的歸屬與時程；舊「➕」與 👤 選定不同步**
- 問題：留在 🎯 標的（責任方向；現行 nav：🔍 找標的）、移 ⚡ 行動（責任方向）或 🛡️ 持股（責任方向；現行 nav：💼 我的持股）？歸屬待 IA Decision Gate；新版 CRUD（`ME-P2`）之前，舊「➕」寫入的 Sheet／清單名與 👤 選定可能不同步（見 12.4.1 R5），是否接受？
- 為何需裁示：High——寫 Google、凍結快照不可重建；DEC-083 P2 未授權；`PRODUCTION_WRITE_APPROVED=False`。
- 候選：(a) 新版暫不做，保留舊 UI，並在 🔍 結果旁加指路句（句型待客戶定）；(b) 隨 P2 一併設計；(c) 先對齊舊「➕」與 👤 選定再開放。
- 總管推薦：(a)。理由：High 且 P2 未授權；先消除「靜默缺席」。
- 相關 DEC：DEC-082、DEC-083（Q2：P2 項目〔建立／rename／刪 Sheet、組合與觀察清單 CRUD〕留 P2、另開 Gate）、DEC-066 A／F（重驗 @15cd8fff：`PRODUCTION_WRITE_APPROVED: bool = False` 於 `shared/risk_cap_history_policy.py`）。

**S16｜兩種凍結 cohort（手動：使用者因子＋空頭濾網；cron：全因子、無濾網）並存時，對帳是否合併顯示、如何標示**
- 問題：對帳讀「本地 ∪ Google Sheet」去重，兩種 cohort 語意不同，混在一起是否仍有意義？
- 為何需裁示：影響前進式驗證樣本的詮釋；凍結快照是**不可重建**資料。
- 候選：(a) 分開顯示並標 cohort；(b) 合併顯示並標註；(c) 只顯示 cron cohort。
- 總管推薦：(a)。理由：不改變樣本、不丟資訊。
- 相關 DEC：`CLAUDE.md` §2.3、§-1.5.F 判定 3(5)。

**S17｜🎯 輸入面：名稱搜尋規則、「帶入我的持股」、候選→查一檔的跳轉**
- 問題：新舊皆無名稱搜尋（只吃代碼）；是否要做？代號＋名稱、同名歧義、ETF 簡稱如何處理？「帶入我的持股」（唯讀 `holdings_service`）要不要做？🔍 結果表與 🔬 表單之間沒有連結，要不要做跳頁＋預填？
- 為何需裁示：均為新控制項／新互動（UI 異動）；比對規則是業務語意；`ia_nav` 檔頭自述「不做導覽」。（重驗 @15cd8fff：`shared/ia_nav.py` 第 24 行「**不做導覽**。它只回字串，不切分頁、不碰 session、不 import streamlit」成立；導覽實際是 `app.py` 側欄 radio〔`_IA_NAV_OFF = '不使用（用下方原功能）'`〕。「新舊皆無名稱搜尋（只吃代碼）」**未逐檔重驗 → INFERENCE／未複驗**。）
- 候選：(a) 三項皆暫不做；(b) 只做「帶入我的持股」與跳轉；(c) 三項皆做（先定同名歧義規則）。
- 總管推薦：(b)。理由：不需新比對規則，且直接改善流程斷點。
- 相關 DEC：DEC-081（第 7 點）、DEC-003 ①、`UIX-FIND-INPUTS`。

**S18｜熱力圖補全：市場（美股 GICS／台股）與區間切換、漲跌排行表、AI 白話**
- 問題：新頁固定台股／1 日，無排行表（treemap 以紅綠為主，排行表是文字備援）；舊頁有市場／區間 selectbox、🔄 刷新、排行表、AI。
- 為何需裁示：線框原本沒畫＝UI 異動；無障礙（不只靠顏色）。
- 候選：(a) 補排行表文字備援；(b) 補市場與區間切換；(c) 全補（含 AI）。
- 總管推薦：(a)+(b)。理由：能力不縮水，AI 層另案收斂。
- 相關 DEC：DEC-081、DEC-003 ①。

**S19｜🔬 查一檔的 6 個 MA 勾選：K 線接線前要不要先移除**
- 問題：目前「控制項有、效果無」（僅回顯於判型卡 fact）。（重驗 @15cd8fff：`src/ui/views/page_inspect.py` 內的均線文案自述「均線的選擇目前**沒有東西會用到**（K 線那一段未接線）」成立；`req.mas` 僅出現在回顯 fact（「期間 / 均線」）成立。「6 個」勾選的個數未逐一點算 → 個數為 INFERENCE／未複驗。）
- 為何需裁示：移除／保留都是 UI 異動；違反 DEC-081 第 7 點精神（可操作≠有效果）。
- 候選：(a) 先移除，K 線接線時再加；(b) 保留並維持現有揭露；(c) 保留並在控制項旁加「尚未接線」。
- 總管推薦：(c)。理由：不改版面結構，又消除誤導。
- 相關 DEC：DEC-081。

**S20｜批次上限 10→20 與「型別篩選只影響顯示」是否維持**
- 問題：舊版個股／ETF 各 ≤10，新版混貼 ≤20（`BATCH_MAX_TICKERS=20`）；型別篩選只影響顯示。（重驗 @15cd8fff：`src/ui/views/page_inspect.py::BATCH_MAX_TICKERS: int = 20` 成立；舊版個股 ≤10 成立〔`tab_stock_grp.py` `parse_stocks(multi_input)[:10]`〕；**舊版 ETF ≤10 與「型別篩選只影響顯示」未重驗 → INFERENCE／未複驗**。）
- 為何需裁示：節流常數變更與顯示語意。
- 候選：(a) 維持 20；(b) 回到 10；(c) 20 但分批提示。
- 總管推薦：(a)。理由：已在新頁運作，無資料語意變動。
- 相關 DEC：無專屬 DEC。

**S21｜💼 逐檔戰情表、規則式事實先出、逐盞燈明細要不要回到 💼**
- 問題：新頁只給檔數，不給「哪幾檔亮 235、各加碼多少、各自損益」；逐盞燈明細（點列展開＋週線圖）未做；手機上燈牆只剩 glyph。
- 為何需裁示：畫面結構＋資訊揭露層級；**線框已有「點任一檔，右側展開週線與布林 z」（DEC-017），是否仍須先出草稿須總管／客戶確認**。
- 候選：(a) 補逐檔表＋規則式事實（不經 AI）；(b) 只補規則式事實文字；(c) 維持現況。
- 總管推薦：(a)。理由：~~現況把規則式事實藏在 AI 按鈕後（Data≠AI 違反）；舊版相反。~~
  - **（更正原因，重驗 @15cd8fff）**：此句**不成立**。`src/ui/views/page_hold.py` 的規則式事實**不在 AI 鈕後**：「加碼 N／汰弱 N／未判 N」事實列（`build_*` 以 digest 的 `adds`／`reds` 組成）與燈牆卡（`build_lightwall_card`，逐檔燈條由 ~~`_render_light_wall_block()`~~ `_render_light_wall()`〔`page_hold.py` 定義約 :5301，更正：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管〕走 L4 `render_light_wall()`）都在 `st.button`〔`AI_SUMMARY_LABEL = "⚡ 生成 AI 總結"`〕**之外**畫出，AI 鈕只負責 ⑦ 的文字總結。原稿「Data≠AI 違反」缺依據，撤回。（只撤回「檔數與燈牆」部分；逐檔加碼金與觸發代號文字仍只存在於 AI 路徑，見 H-14b、D9。）
  - **仍可成立的缺口（重驗範圍有限）**：`page_hold.py` 內 `deploy_pct`／「加碼金」0 命中，即逐檔加碼金不在該檔；逐檔損益僅在總計層（`pnl_twd`／`pnl_pct`）。「點列展開＋週線圖」與「手機燈牆只剩 glyph」**未重驗 → INFERENCE／未複驗**。
  - **現行推薦理由改為**：(a) 補齊的是**資訊揭露層級**（逐檔 235 加碼金與損益），不是修一個 Data≠AI 違規；是否構成「畫面結構」異動仍須走 DEC-003 ① 草稿。
- 相關 DEC：DEC-017、DEC-082、DEC-081（第 7 點）。

**S22｜ETF 組合分析 11 格、多檔比較的組合層分析、「假想組合」試算的去留與歸屬**
- 問題：產業曝險 30%、相關係數、成分股、Overlap、主動 ETF 弱勢度、0050 比較、效率前緣、配息逐月、稅率、組合體檢 vs 基準、集中度、風險貢獻；以及舊 UI 可手填假想組合（含不在 Sheet 的海外 ETF）what-if 試算，新 UI 沒有。留 🛡️ 持股責任方向（現行 nav 尚無對應 view；舊 UI 掛在 🏦 ETF 分頁，INFERENCE）、搬 🎯 標的責任方向、或不搬？歸屬待 IA Decision Gate。
- 為何需裁示：歸屬、門檻（30%）、可得性（Overlap 跨市場量不到須標「無法判定」）、新輸入控制項。
- 候選：(a) 全留舊 UI；(b) 逐格評估，先搬純顯示格；(c) 全搬。
- 總管推薦：(b)；~~待 S1 後逐格排序~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；S 項不構成前置裁示）逐格排序由 Stage B 收斂為 Decision Gate 後於 Stage C 處理，與 S1 相關。理由：避免一次搬入多個門檻。
- 相關 DEC：DEC-081、DEC-082。

**S23｜「誰是我的持股」語意與舊新分歧**
- 問題：(i) 新頁只讀 👤 選定的一本；**未選定→整頁不分析（含觀察清單）**——此規則為 AI 總管裁示，非客戶原文，需確認；只有觀察清單、沒有持股（或未選定）的使用者，舊版仍跑觀察清單 235 燈，新版不跑。(ii) 舊戰情室可讀「新 UI 視為未綁」的部署預設 Sheet。(iii) 💼 葉1 不顯示正在分析哪一本。
- 為何需裁示：影響所有下游；DEC-083 Q7「不可見業務決策」。
- 候選：(a) 維持現規則，葉1 補一行「正在分析：〈組合名〉／〈清單名〉」；(b) 未選定時退回「名稱排序第一本」（不建議，正是 DEC-083 禁止的）；(c) 未選定時分析觀察清單。
- 總管推薦：(a)。理由：不改規則、補可見性。
- 相關 DEC：DEC-083（Q7）。

**S24｜「切回舊版」指路句：能否在客戶逐字句後補操作步驟；明細七段的指路是否也適用 DEC-083 第 10 項**
- 問題：DEC-083 第 10 項「不得再出現：新版模式看不到的頁面卻叫使用者直接去點」，指定句型「目前請切回舊版 → …」；`DETAIL_WHERE`、`HEATMAP_SWITCH_HINT`、葡萄串卡與此衝突（重驗 @15cd8fff：`page_inspect.py::DETAIL_WHERE` 寫「現行入口仍在既有的 🔬 個股 / 🏦 ETF 分頁」、`page_find.py::HEATMAP_SWITCH_HINT` 寫「到 🌍 市場環境 ›「🗺️ 產業熱力圖」」，皆**沒有**「切回舊版」步驟，成立；葡萄串卡 `DEEP_SPECS` 的 `where` 未指任何入口，是否算「叫使用者去點看不到的頁」**降為 INFERENCE／未複驗**）；💼 的客戶逐字句未說怎麼切（側欄 radio「不使用」）。是否允許在逐字句後補一句步驟（不改本體）？
- 為何需裁示：客戶逐字句不可由 AI 改；DEC-083 第 10 項文字限於 Sheet／持股語境，延伸到明細指路屬需裁示。
- 候選：(a) 允許補步驟並統一句型；(b) 僅 Sheet／持股類補；(c) 不動。
- 總管推薦：(a)。理由：消除半 dead-end，不改客戶句本體。
- 相關 DEC：DEC-083（第 10 項）、`ME-OLD-TAB-POINTERS`。

**S25｜重新讀取／重新抓取，與 429 配額白話提示**
- 問題：💼 全頁沒有任何一句提到重讀（重讀入口在 👤）；原樣搬「🔄 強制重抓」會清全域快取，不可搬；🔬 查一檔也失去重抓手段；429 配額用罄在 💼 被當成「讀取失敗」紅卡（資料層其實已分類出 `READ_ERROR_QUOTA_EXCEEDED`，👤 有用、💼 沒接）。（重驗 @15cd8fff：`src/data/portfolio/gsheet_portfolio.py::READ_ERROR_QUOTA_EXCEEDED = 'quota_exceeded'` 成立；`page_me.py` 有 `SHEET_TITLE_QUOTA`／`ISSUE_TEXT_QUOTA`〔含「可稍後按「🔄 重新讀取」」〕成立；`page_hold.py` 內 `QUOTA`／`quota`／`429` 0 命中、「重新讀取」0 命中，成立。）
- 為何需裁示：新控制項（UI 異動）；快取失效範圍須 scoped（DEC-083 B5：⛔ 不 `.clear()`）。
- 候選：(a) 只加文字指路到 👤「🔄 重新讀取」並接 429 白話；(b) 💼 加讀取鈕（scoped：只清本人×active Sheet）；(c) 不做。
- 總管推薦：(a)。理由：最小改動，零新寫入。
- 相關 DEC：DEC-083（B5）。

**S26｜全域🔗綁定狀態列在新版是否需要跨頁常駐**
- 問題：舊 popover 在新版模式不畫；各新頁各自畫綁定卡；`st.page_link`／`switch_page` 在 `page_hold`／`page_me` 範圍內 0 命中且導覽是 `app.py` 側欄 radio。（重驗 @15cd8fff：`git grep -E 'page_link|switch_page' -- src/ui/views app.py` 全 0 命中；`app.py` 側欄 radio 預設「不使用（用下方原功能）」成立。）
- 為何需裁示：牽涉 navigation，DEC-082：客戶核准草稿（Stage C）前不得改 navigation；`UIX-MKT-STATUSBAR`、`DH-DATA-CENTER`。
- 候選：(a) 不做；(b) 併 🩺 資料中心線框評估；(c) 側欄加 chip。
- 總管推薦：(b)。理由：與資料中心狀態列同題，避免兩次改 navigation。
- 相關 DEC：DEC-082、`DH-DATA-CENTER`。

**S27｜三階段濾網（G8）與選股網延伸（初篩逐檔明細／跨季趨勢排行／AI 總結）的去留**
- 問題：三階段濾網在 production 實為批次分析後 auto 串跑、零可操作控制項（15 條件＋`min_pass`）；初篩明細面板（逐檔表、快照涵蓋率警示）、全台股跨季趨勢排行＋CSV、選股網 AI 總結，新頁皆無。
- 為何需裁示：15 條件、前 100 的定義與排序是判定語意；涵蓋率警示缺失會讓使用者以為池子完整；L5 檔內自行 `requests` 抓取須先下沉才能移植（**INFERENCE／未複驗**：本輪未對 `tab_stock_picker.py` 重驗〔15 條件＋`min_pass` 中 `filter_by_custom_conditions(results, selected_keys, min_pass)` 簽名成立；「零可操作控制項」「檔內 `requests`」未重驗〕）。
- 候選：(a) 全留舊 UI；(b) 只補初篩涵蓋率警示與逐檔表（純資料揭露）；(c) 全補。
- 總管推薦：(b)。理由：補回資料品質揭露，不碰判定語意。
- 相關 DEC：DEC-081、DEC-082。

**S28｜🔬 查一檔明細：七段清單之外的靜默缺席能力，範圍與優先序**
- 問題：型態目標價、集保大戶雷達、近期新聞、統一判決、一眼判讀 4 桶、策略 1 結論／財報趨勢 65/35、D2 基本面先行、3-3-3 三條判定、分散度、BIAS／σ、費用率／Beta／AUM 數值、PROXY 缺席原因說明等，不在 `STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS`，**新頁沒有也沒有指路**。哪些屬 🎯 標的責任方向（現行 nav：🔬 查一檔）？哪些不搬？（以下「新頁沒有」為 `page_inspect.py::STOCK_DETAIL_SECTIONS`／`ETF_DETAIL_SECTIONS` 存在、名單外各項**未逐項 grep 重驗 → INFERENCE／未複驗**。）
- 為何需裁示：多項為投資語意（目標價／統一判決）或評分權重；歸屬 vs ⚡ 見 S1。
- 候選：(a) 先補純資料揭露（新聞、集保大戶、費用率／Beta／AUM、PROXY 原因）；(b) 連七段接線一併排序；(c) 全留舊 UI 並補指路句。
- 總管推薦：(c) 為底，(a) 為先。理由：先消除靜默缺席，再處理語意。
- 相關 DEC：DEC-081、DEC-082。

#### 12.5.2 高風險投資語意：Stage B **不得自行改定義**（只能原樣引用或標 `【decision-note：待客戶裁示 S#】`；依 DEC-085／`PROJECT_RULES.md` 第 19 節，本表不弱化、不放寬任何投資語意約束）

> 重驗 @15cd8fff（本表常數）：`VIX_LIGHT1/2/3 = 20/25/30`、`Z_LIGHT1/2/3 = -1/-2/-3`、`DEPLOY_LIGHT1/2/3_PCT = 20/30/50`（`shared/dividend_station_thresholds.py`）；`HARD_STOP_LOSS_PCT=7.0`／`STOP_LOSS_DEFAULT_PCT=8.0`／`POS_MAX_RISK_PCT=0.015`／`VAR_Z_SCORE_95=1.645`／`VAR_Z_SCORE_99=2.326`（`shared/signal_thresholds.py`）；`PRESCREEN_REQUIRED_PASSES=4`（`shared/fundamental_prescreen_thresholds.py`）；`RS_RANKABLE_TIERS` 存在（`shared/rs_screen_thresholds.py`）；財報趨勢 slider `min_value=0.4, max_value=0.9, value=0.65, step=0.05`（`src/ui/tabs/tab_stock_grp.py`）；4 訊號共振 inline `>=3`／`>=2`、「健康度跌破 60」（`section_op_recommendation.py`）；Beta 缺值以 1.0 估並帶旗標（`etf_calc.py`，`beta_imputed_count`）；`PRODUCTION_WRITE_APPROVED: bool = False`。**未重驗（INFERENCE／未複驗）**：產業曝險 30% 門檻值、財報趨勢 65/35 權重（僅 slider 預設 0.65 已證）、`SHORTAGE` tier 邊界、3-3-3 與 357 殖利率帶、ETF 7 維加權 5 星、三階段 15 條件的條件數、月虧損「7 天」、配息不含綜所稅／海外標的排除、PIT 對齊細節。

1. 出場訊號（三維出場含 LLM 維度、操作狀態燈、個股進出場訊號）、衛星停利與 ETF 停利（z>+2σ／+3σ）、汰弱＝換出（S5、S1）。
2. **加碼**：235 燈（`VIX_LIGHT1/2/3`、`Z_LIGHT1/2/3`）與加碼金比例 20／30／50%、`suggest_action` 優先序（汰弱＞停利＞暫停加碼＞加碼＞高溢價＞巡航；DEC-045 不得改優先序或新增 action semantics）（S4）。
3. **再平衡**：目標權重、容忍偏離度、買賣股數與金額（S3）；**葡萄串**「生成提議」與 10 檔高股息清單／星等門檻（S3）。
4. **強烈出場含 LLM**（S5）。
5. **核心比例兩套**（80/20 vs regime 0.60–0.85；S12）。
6. **凍結 cohort 語意**：手動（使用者因子＋空頭濾網）vs cron（全因子、`regime=None`）；`picks.parquet` 為不可重建歷史，任何入口不得重算、覆蓋、刪除（S15、S16）。
7. 其餘須一併遵守者：選股綜合評分與 5 因子定義、`PRESCREEN_REQUIRED_PASSES`（四項全過）及其門檻、`RS_RANKABLE_TIERS`、`SHORTAGE` tier 邊界；**空頭濾網只在畫面傳、cron 不傳（刻意，PIT 可比性），不得為「一致」而統一**；兩把「健康」尺（不得合併、不得並排成同一排名）；評分權重與門檻（財報趨勢 65/35 與使用者可調 slider 0.4–0.9、六因子配分、ETF 7 維加權 5 星、3-3-3、357 殖利率帶、PE 區間 preset、三階段 15 條件＋`min_pass`）；停損 7%／8%、單筆風險 1.5%、建議張數；4 訊號共振門檻（inline 3／2／60 不得「順手抽常數改值」）；月虧損 -10%／7 天；VIX 三段門檻；產業曝險 30%；Beta 缺值以 1.0 估（新頁以降級＋揭露處理，揭露不得移除）；VaR 95／99% 常態分位；配息不含綜所稅、海外標的排除；建議持股水位／Risk Cap 顯示 Gate（缺有效上限須「無法判定」）；PIT／look-ahead（357 位階與舊頁同一份股利來源、季財報公告日對齊在 L3）；AI 結論不得創造客觀資料或目標價且不得覆蓋規則判讀（Data≠AI；搬入 ⚡ 行動責任方向時揭露不得縮減）。
8. **缺值語意**：缺值≠0／中性／正常／HOLD；proxy／estimated≠real（新頁已遵守，Stage B 新增卡須維持）。

#### 12.5.3 缺口來源對照（可追溯）

| 調查檔缺口 | 對應 S 項 |
|---|---|
| A：1 歸屬（寫入類）／2 預設因子／3 買賣語意歸屬／4 健康命名／5 名稱搜尋＋帶入持股／6 熱力圖／7 候選→查一檔／8 兩種凍結 cohort／9 MA 勾選／10 批次上限 | S15／S14／S1＋S6／S13／S17／S18／S17／S16／S19／S20 |
| B：1 逐檔戰情表＋規則式事實／2 核心比例／3 再平衡／4 組合分析 11 格／5 僅觀察清單者／6 推播語意／7 切回舊版／8 429＋重新載入／9 全域狀態列／10 ➕ 寫入不同步 | S21／S12／S3／S22／S23／S11／S24／S25／S26／S15 |
| C：G1 範圍／G2 七種 Action／G3 再平衡＋葡萄串／G4 235 vs DEC-053／G5 三維出場含 LLM／G6 個股停損停利＋Position Sizing／G7 月虧損停機／G8 作戰室內容／G9 持股水位／G10 戰情室歸屬／G11 攻擊發動＋結論句／G12 推播／G13 核心比例兩套／G14（複驗新增）C-31 心理檢查 | S1／S2／S3／S4／S5／S6／S7／S8／S10／S1／S9／S11／S12／S7 |
| 落盤組補列（未列於三份「裁示」節，但為各組發現） | S24（DEC-083 第 10 項衝突）／S27（三階段濾網＋選股網延伸）／S28（明細靜默缺席） |


### 12.6 與既有矩陣（本檔 §2／§3／§6／§8／§9）不符處

> 基準：程式碼＝main @ `15cd8fff`（4e6bf8ee→15cd8fff 僅 docs 變更，0 程式碼變更，已實測 `git diff --name-only`）。**重驗 @15cd8fff**：本節（12.6.1～12.6.3）的 code 宣稱（`file::symbol`、行號、widget key、caller、卡 key 全集）已對 worktree 逐項重讀；成立者保留，不同者用刪除線更正，未能重驗者標 INFERENCE／未複驗。頁面名稱一律採「責任名＋（現行 nav：…）」寫法：📊🎯⚡🛡️👤🩺 是 DEC-085／`PROJECT_RULES.md` §19.2 的長期責任方向，**不等於**現行 nav 名稱或既有 view 的一對一對映；對映屬後續 IA Decision Gate，本盤點不決定（現行 nav：📊 大盤、🚦 今天、🔍 找標的、🔬 查一檔、💼 我的持股、📖 憑什麼、👤 我的，見 `shared/ia_nav.py::PAGE_LABELS`）。
>
> 彙整三組調查與複驗。**§0～§11 原文不改**；舊文字保留，被推翻的狀態以 ~~刪除線~~ 標註並寫明「（2026-10-26 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））」（見 §2、§6 對應列）。下列「矩陣第 N 行」指本檔未加 §12 前的行號（量測於 `4e6bf8ee` 的檔案）；`page_hold`／`app.py` 行號僅供定位。

#### 12.6.1 全面性問題

1. **行號全面過期**：§2／§3／§6／§8 引用的 `app.py` 行號以 `5e2e6e23`（§0.1 已警告）為準，現行 `4e6bf8ee` 已位移（例：選股網按鈕 `app.py` 約 835、multiselect 約 830；status bar 約 687、`st.stop()` 約 675、羅盤約 694、7 頁籤約 707）；`page_hold.py` 行號亦已漂移（form 現為 `_render_holdings_form` 約 5170、AI 鈕 `_render_ai_button` 約 5258–5279、預覽 caption `_render_holdings_preview` 約 5398–5412，且文字已改）。重驗 @15cd8fff：`app.py` 的 `st.stop()` 在 675、`st.tabs([...7 頁籤...])` 在 707、選股網 multiselect 在 828、「開始選股」區在 834 附近；`page_hold.py` 三個 `def` 行號 5170／5258／5398 與上述一致。**§3 沒有加註**。本節一律改用「檔案::符號」。
2. **§2 與 §6 對同一顆按鈕自相矛盾**：§2 寫「⚡ 生成 AI 總結…已接」，§6 對同一個舊按鈕（`etf_tab_dividend_station.py` 約 698 行）寫「✍️ AI 推播文字｜待接」。以「已接（生成）；兩邊都沒有推送能力，推送只在 cron」為準。
3. **§6「🚀 跑存股戰情室｜待接（⚡ 或 🛡️ 未定）」已不成立**：`page_hold.py` 已有同名表單提交鈕（`ACTION_RUN_WARROOM_LABEL`，經 `single_submit_form`）。~~應為「已接（在 🛡️），歸屬未定」~~（更正原因：BRIEF／DEC-085 §19.2——責任名不得當現行 nav 使用、不得以程式碼目前掛在哪頁斷言歸屬）→ 改為「**已接（現行 nav：💼 我的持股，`page_hold.py::ACTION_RUN_WARROOM_LABEL`＝「🚀 跑存股戰情室」，經 `_ui_kit.single_submit_form`）；歸屬待 IA Decision Gate**」。（重驗 @15cd8fff：符號存在）
4. **§6 只列 5 個候選，漏列核心「行動」能力**：三維出場（C-11／C-12）、個股進出場與停損停利（C-13）、總資金→建議張數（C-14）、即時操作建議（C-15）、操作狀態燈（C-16）、作戰室內的 5 分鐘清單／風險警示／月虧損（C-18／C-19）、攻擊發動判定（C-20）、結論句＋行動建議（C-21）、逐檔燈明細展開（C-04）、**心理檢查（C-31）**、2 條漏列推播 cron（C-32／C-33）。其中 C-14、C-12 已出現在 §3（盤點範圍標籤 🎯）但標「無」，C-11 在全矩陣沒出現（`grep 出場` 僅 §6 末句）。
5. **§6 末句「`page_hold` 戰情室葉的出場／235 等行動卡只是顯示，沒有控制項」**：控制項部分屬實（有 form 提交鈕與 ⑦ 按鈕），但「出場」措辭易誤導——`page_hold` 沒有**三維出場訊號**（只有健檢紅燈＝汰弱、衛星停利）；且沒指出顯示內容比舊戰情室**少**（H-07／H-09b／H-14b）。
6. **§6「ETF 組合計算／再平衡／演算法／稅率｜待接」過粗**：壓力測試、VaR、配息現金流、80/20 核衛已在 `page_hold` ⑥接線；真正未接的是輸入表／容忍度／計算鈕／強制重抓、再平衡指令、regime 版核衛、產業曝險等其餘分析、稅後試算。應拆列。另：葡萄串、ETF 組合計算在舊 UI 並不獨立存在，自 P2b v19.202 起只掛在戰情室 expander 內（`app.py` 註解；重驗 @15cd8fff：`render_grape_ladder` 於 `etf_tab_dividend_station.py` 呼叫一處，且 `app.py` 無直接呼叫），矩陣寫成獨立入口卻沒寫「無其他入口」。
7. **§0.2「👤 我的…三頁還沒有 view」已過期**：`page_me.py` 與 `ia_nav.PAGE_ME` 已存在（§11 已更新，§0.2 未回頭改）。
8. **§9 重複清單缺**：`watchlist_service` 走 legacy 通道（R5）、cron 的去重丟棄（R6）、`sector_flow_service` 全觀察清單讀取（R8）、VaR／壓測雙實作、ETF 健檢兩引擎、核心比例兩定義、建議持股水位第 6 份副本、凍結兩路徑、3 份綁定 UI（見 §12.4）。
9. **§2 第 1 列未提預設 radio 為「只讀市場端」**＝新手第一次按 🚀 得到整片灰（`SCOPE_OPTIONS` 第一項為預設）。
10. **§2 的 INFERENCE「重按 🚀 可能在 TTL 內拿到舊值」**維持 [I]：補 `holdings_service` 以 `sheet_id=` 顯式帶入，L1 快取鍵含身分指紋＋sheet_id，所以**換 Sheet 不會拿舊值**，但**同一 Sheet 內改內容**仍受 `TTL_15MIN` 影響（檔頭自述；實際數值未驗）。
11. **§2「組合／觀察清單管理」列的備註**（caption「唯讀 —— 要新增／修改／刪除請到既有的 📁 組合管理分頁」）**已不成立**：現文為客戶逐字句「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」（`ia_nav.CONTENT_EDIT_OLD_UI_WHERE`）。§11 末列有更新，§2／§8 原表未標。
12. **§8.1「9 處 dead-end」已全部改寫**：`📁 組合管理` 字樣在 `page_hold.py` 非註解行僅剩 `_V2_OLD_UI` 一處（客戶句開頭），其餘 23 行皆 `#` 註解（重驗 @15cd8fff：該字串共 24 行命中，其中 1 行非註解＝`_V2_OLD_UI`、23 行註解），畫面字串皆為客戶逐字句。dead-end 型態由「指到看不到的頁籤」變成「**指向舊版但不說怎麼切**」（半 dead-end）。**§8.2 的 20 餘處「未判讀」仍未被逐一判讀**（三組皆未做）。
13. **§2 未列新頁顯示元件**（只列控制項，不列顯示元件）：`hold.position_cap`（建議持股水位／Risk Cap 閘）、`hold.macro_stage`、`hold.scales`、`hold.vix`、`hold.deep.*` 六格、`hold.setup.*` 卡片。卡 key 全集（複驗以 `grep -o "hold\.[a-z_.]*"` 列出；重驗 @15cd8fff 再跑一次，與下列一致）：conclusion.action／confidence／todo、scales、lightwall、vix、switch、macro_stage、alloc_split、take_profit、position_cap、deep.{rebalance,core_satellite,stress,var,dividend_cash,grape}、ai_summary、binding、portfolio_count、setup.{preview,pick_sheet,watchlist}。
14. **§6 候選「⚡ 或 🛡️ 未定」措辭**：宜改為「歸屬待 IA Decision Gate；目前控制項已存在於 現行 nav 的 💼 我的持股」（🚀、✍️ 兩項）。

#### 12.6.2 §3 🎯 標的（盤點範圍標籤，依現行 nav 暫代：🔍 找標的、🔬 查一檔）

15. **三階段篩選（多選／額外代碼／go／AI）→ `tab_stock_picker.py` 的四個 widget 在 production 全不可達（複驗更正調查組原結論）**：唯一 caller 是 `tab_stock_grp.py::_render_stage_picker_section`（內部呼叫 `render_tab_stock_picker(source_label='個股組合輸入', auto_run=…)`，外層以 `auto_run=True` 呼叫；重驗 @15cd8fff：`render_tab_stock_picker(` 全 repo 僅此一處呼叫）→ `_t3_mode=True` → multiselect 與額外代碼 text_input 不畫；go 按鈕因 `auto_run=True` 不畫；`auto_run` 時直接自動生成 AI 報告，`elif st.button(…)`（AI 三型建議按鈕）也不會畫。**三階段整段是「批次分析後自動串跑、零控制項」**（調查組原寫「可達的只有 AI 按鈕 572」為誤）。選股網（`app.py`）已在 v19.111 移除 picker。
16. **「預篩『顯示全市場』→ `tab_stock_picker.py:187`」**位置正確，但屬選股網的 `render_prescreen_panel`；§3 沒列同面板的**涵蓋率警示**（`describe_snapshot_coverage`，重驗 @15cd8fff 位於該面板「顯示全市場」checkbox 之前）與**逐檔數值表**（INFERENCE：逐檔數值表的有無本輪未再逐行比對）。
17. **「板塊資金潮汐：已接？（未驗）」→ 已驗（複驗確認）**：`page_find.py::load_sector_flow`／`build_sector_flow_card` 全套對應（泡泡圖、象限圖例、TPEx 提示、缺值列名、資料不足列名、時戳），持股標示改讀 👤 我的（現行 nav：👤 我的 選定的組合／觀察清單）；`strict=True`（壞檔轉紅，舊版轉灰 info）。
18. **矩陣漏列**：型態目標價在個股頁有整合入口（`pattern_targets_ui.py` 行已列），但**新頁 `STOCK_DETAIL_SECTIONS` 七段清單沒有型態目標價**，所以 `DETAIL_WHERE` 指路覆蓋不到它；同樣漏列：個股↔總經聯動 banner、個股↔持倉聯動 banner、集保大戶雷達、新聞、統一判決、一眼判讀、策略 1 結論／財報趨勢分數、D2 基本面先行、統一 TOC（§3 只列 widget，沒列非 widget 區塊）；選股網 AI 總結（S11）與 expander 內 📊 對帳說明；舊 ETF 單檔的同儕排名／近 5 年走勢／成分股明細／PROXY 缺席警示（複驗補）。
19. ~~**ETF smart 的歸屬已可判定**~~（更正原因：不得以程式碼目前掛在哪頁斷言歸屬已可判定，見 DEC-085 §19.2）→ **ETF smart 目前只掛在…；歸屬待 IA Decision Gate**：§3 寫「歸 🎯 或 🛡️ 未定」；重驗 @15cd8fff：三個 smart 區塊（`render_333_section`／`render_std_band_section`／`render_correlation_finder`）只由 `app.py` 的 `_etf_single_smart` 以 `before_ai_hook` 掛在**舊 ETF 單檔診斷**（`render_etf_single(before_ai_hook=…)`）；`render_smart_ticker_input`（原「組合頁共用輸入框」）無 production caller（對 `src app.py scripts` grep；`tests/test_etf_smart_ticker_wiring.py` 僅以存在性斷言引用）。新 UI 的 現行 nav 🔬 查一檔 是否已涵蓋 smart 三區塊，見 12.1 對應列，此處不判定歸屬。
20. **「ETF 代號＋對照基準＋開始診斷：部分」正確**；補：新頁判型卡顯示 `pick_benchmark` 結果但不可改，且個股／ETF 型別覆寫是新頁額外提供的能力（舊 UI 沒有）。
21. **「個股代碼＋載入完整分析：已接」略有保留**：新頁「期間」只決定籌碼那格的日線長度，天數對其他明細無效，不是舊 slider 的等價物（A-20 判 🟡）。
22. **「多檔代碼＋🚀 批次分析：已接（個股與 ETF 合併）」正確**；補：上限由 ≤10 變 ≤20 混貼；舊版一鍵串跑的「組合體檢、排行、型態、財報趨勢、三階段、AI」六件事，新批次表只對應「逐檔指標」（A-53 判 🟡）。

#### 12.6.3 §6 ⚡ 行動（盤點範圍標籤；現行 nav 尚無對應頁，歸屬待 IA Decision Gate）的其餘複驗發現

23. **§6 寫「今天頁 ⑤（未接線）」**與現況一致（`tab_today.py` staged「尚無作戰項目」「AI 摘要尚未接線」）；補：📊 大盤頁檔頭已明示作戰室不放，所以作戰室目前**兩頁（現行 nav：🚦 今天、📊 大盤）都沒有**（重驗 @15cd8fff：`tab_today.py` 仍有「尚無作戰項目」「AI 摘要尚未接線」；`page_market.py` 檔頭寫「作戰室日後移到 ⚡ 行動（本批不做）」）。
24. **§6 引用的舊入口行號在 `4e6bf8ee` 大致仍對得上**（複驗抽驗；重驗 @15cd8fff 再逐行讀：`etf_tab_dividend_station.py` 196＝🚀 鈕／322＝`_render_layer1`／461＝`_render_light_detail`／572＝`_render_allocation_take_profit`／628＝`_render_switch_advice`／671＝`_render_ai_summary`／698＝✍️ 鈕；`grape_ladder.py` 426 slider、438 🍇 鈕；`etf_tab_portfolio.py` 232 data_editor／255 slider／259 計算鈕／574 強制重抓／950 radio／1438 selectbox，皆對）。


### 12.7 資料治理發現（缺值當 0／當中性、Data≠AI、不只靠顏色、proxy≠real）

> 基準：程式碼＝main @ `15cd8fff`（4e6bf8ee→15cd8fff 僅 docs 變更，0 程式碼變更，已實測 `git diff --name-only`）。**重驗 @15cd8fff**：D1～D15 的 code 宣稱（位置、符號、數值、caller）已逐條對 worktree 重讀，更正處以刪除線標示。
>
> **範圍聲明（誠實揭露）**：DEC-085／`PROJECT_RULES.md` §19.8 列了 7 條 Missing 語意（missing≠0／中性／正常／HOLD；proxy／estimated≠real；stale≠current；error≠missing）。本節的盤點主軸是 **missing≠0／中性（12.7.1）**、Data≠AI、不只靠顏色、proxy≠real；**「stale≠current」與「error≠missing」兩項沒有逐條盤點**，僅 D14（429 配額被當成一般讀取失敗，涉及 error 分類）與 D15（舊來源 chip／過期值警示是否保留）順帶涉及。因此本節**不能**當作「新頁在 stale／error 語意上已無問題」的證據；可補查（Stage B 草稿涉及該類卡片時，應由獨立一組補盤）。
>
> 依 BRIEF 紀律彙整。**這些是讀碼觀察，不是已確認的 production bug**，也未判斷是否在 production 觸發；沒被複驗的條目標「單組觀察」。依 `CLAUDE.md` §-1，**不構成動工授權**；本批只登記。已加註「複驗更正」者為複驗後版本。

#### 12.7.1 缺值被當成 0／中性／正常（missing≠0）

| # | 發現 | 位置（`檔案::符號`，行號為重驗 @15cd8fff 實測，會漂移） | 狀態 |
|---|---|---|---|
| D1 | **`monthly_loss_pct` 預設 0**：`st.session_state.get('monthly_loss_pct', 0)` → `_monthly_loss < MONTHLY_LOSS_HALT_PCT(-10.0)`；**全站無寫入點** ⇒ 判斷式恆 False，警示永不出現且沒有「未追蹤」提示。對照 `section_psy_checklist.py`（約 271–273 行）已把同一欄位當「未追蹤」處理——**同一欄位兩種處理，不一致** | `src/ui/tabs/macro/section_warroom.py`（約 321 行）；`src/ui/tabs/stock_sections/section_psy_checklist.py`（約 271–273 行） | 複驗確認（重驗 @15cd8fff：對 `app.py src shared scripts` grep `monthly_loss_pct`，僅 2 處 `session_state.get`、0 處寫入；`MONTHLY_LOSS_HALT_PCT=-10.0` 在 `shared/signal_thresholds.py`。註：grep 不含字串動態組 key，單組） |
| D2 | **`generate_ai_comment` 傳 `'score': 0`**（註解「此處無法取得,用0」）：`app_ai_service.py` 以 `score>=85/75` 分支生成文案 ⇒ 該分支在此路徑**永遠不可能觸發**（缺值當最低分餵 AI 文案分支）。**複驗更正範圍**：`foreign_buy` 在「未觀測」時已由批 Z33 改送 `None`，只有「找不到外資列」時才送 0，且註解自承「缺 key 仍照舊送 0」 | `src/ui/tabs/stock_sections/section_op_recommendation.py`（`'score': 0` 約 109 行；外資約 128–130 行）；`app_ai_service.py::generate_ai_comment`（`score >= 85`／`>= 75` 分支） | 複驗確認（範圍窄於原述；重驗 @15cd8fff：同一 `_comment_data` 的 `val_label`／`trend` 也恆為 `''`，所以「強烈買入」分支此路徑更不可能觸發） |
| D3 | **操作狀態燈 ⚪ 雙義**：docstring「⚪ 中性：其餘／資料不足」，任一輸入為 None 時各條件皆不成立而落到 ⚪ ⇒ 把「中性」與「資料不足」混為同一個符號 | `src/ui/tabs/tab_helpers.py::classify_stock_status_lamp`（~~約 134–170 行~~ 重驗 @15cd8fff：134–177 行；末行 `return '⚪'`） | 複驗確認 |
| D4 | **三維出場「未掃描」仍顯示綠色**：score=0 時 headline 一律「🟢 訊號清淡（三維未轉空）」；新聞維度未掃描時 dims 寫「未掃描」，個股頁抓不到標題 → `_ex_news=None` 同樣落綠。**複驗更強**：個股頁 dim chip 對「未命中」一律畫 `✓`，所以「利空新聞：未掃描」前面是 **✓**，且該頁沒有 caption 說明只有兩維（組合表 `src/ui/tabs/stock_grp_sections/section_portfolio_summary.py` ~~約 42 行~~ 約 741 行有 caption「出場欄目前為「技術＋籌碼」兩維…」，重驗 @15cd8fff 更正行號）。屬 `not evaluated ≠ safe` 風險 | `src/compute/scoring/exit_signals.py::evaluate_exit_signals`（重驗 @15cd8fff：「未掃描」在 `news_desc`，`_LEVELS[0]`＝🟢 訊號清淡，headline 「（三維未轉空）」於約 267–270 行）；`src/ui/tabs/stock_sections/section_when_buy_sell.py`（約 156–185 行；dim chip 未命中一律 `✓`，頁尾小字只寫「三維計分」） | 複驗確認，且比原述更強（INFERENCE：是否在 production 觸發未驗） |
| D5 | **「全清時說續抱」**：舊 `_render_ai_summary` 在 `reds`、`adds` 皆空時寫「續抱、定期定額即可」，不看**判不全但沒 error 的列**（`unjudged_n`）。**複驗更正**：原述「不看抓取失敗」不實——緊接著會另印 `⚠️ N 檔抓取失敗未納入判斷`；屬實的是成功橫幅與失敗 caption **同時出現造成語意打架**。新 UI `cruise_or_gap()` 要求每列每盞適用燈都判得出才准說「沒事」，**搬進 ⚡ 時不可沿用舊句** | `src/ui/etf/etf_tab_dividend_station.py::_render_ai_summary`（約 671–696 行，重驗 @15cd8fff：成功橫幅「續抱、定期定額即可」與其後的 `⚠️ N 檔抓取失敗未納入判斷` caption 確實同時可出現） | 複驗更正（半對） |
| D6 | **舊選股網取數失敗畫成「0 檔」**：存活池／PE 取數／缺貨掃描失敗只 `print`，結果區顯示「目前沒有符合的標的」，把「取數失敗」畫成「沒有結果」。新 UI 已修（紅卡「選股中止」／`aux_errors`）；舊 UI 照留（DEC-081 第 8 點） | `app.py` 選股網區塊（重驗 @15cd8fff：存活池失敗 `print('[screener] 存活池不可用…')`、缺貨／RS／跨季掃描失敗各 `print`；`fetch_pe_name_maps` 於 `yield_pe_fetcher.py` 內也以 `print` 記失敗；結果空時畫面為 `st.info('目前沒有符合的標的…')`） | 複驗確認 |
| D7 | **Beta 缺值以 1.0 估**（壓力測試 L2）：新頁以降級＋揭露處理（`coverage_pct`、`imputed_value_twd`）；Stage B 不得移除揭露 | `src/compute/etf/etf_calc.py::calc_portfolio_stress_test`（重驗 @15cd8fff：docstring 自述 beta 缺→1.0 估算並帶 `_beta_imputed`／`beta_imputed_count` 旗標，NaN／±inf 不補）；`portfolio_deep_service` | 複驗確認（做得好但須保留） |
| D8 | **inline 數字未走 L0 SSOT**：`section_warroom.py` 的外資賣超 -20 億、上漲家數 <35%（約 274–290 行）；`section_op_recommendation.py` 的 60／3／2 共振門檻（`CLAUDE.md` §3.3）。Stage B 不得「順手抽常數改值」 | `src/ui/tabs/macro/section_warroom.py`（~~約 274–290 行~~ 重驗 @15cd8fff：外資賣超 `< -20` 約 215 行、`ad_ratio < 35` 約 220 行；行號更正）；`section_op_recommendation.py`（`_sig_count >= 3`／`>= 2` 與「健康度跌破60」文字約 65–68 行） | 複驗確認（inline 數字存在；是否違反 SSOT 仍依 `CLAUDE.md` §3.3 判斷，INFERENCE） |

**新頁做得好、須保留的缺值處理（[F]）**：`keep_blank=True`→`None`（缺張數／均價不是 0）；持股預覽缺值顯示「—」；總額算不出來不填 0；VaR／壓測／配息 `computed=False`＋`reason`；折溢價拿不到就不填、不用 yfinance navPrice；`UI_EMPTY`／`UI_FAILED` 分離；NaN／±inf 視為缺值；新頁拒絕範例持股頂替（`NOT_BOUND_WHY`：本站不拿範例持股頂替）。

#### 12.7.2 Data≠AI、狀態只靠顏色、揭露不足

| # | 發現 | 位置 | 狀態 |
|---|---|---|---|
| D9 | **新 💼 Data≠AI 違反**：235 加碼**金額**與規則式文字只存在於付費 AI 的 digest 輸入；舊版相反（規則先出、AI 在後）。**複驗更正**：代號可從燈牆讀出，但無文字說明；抓取失敗代號亦同。未接 AI 金鑰時，舊版仍有規則式摘要，新 💼 只剩紅卡／錯誤 | `page_hold.py::load_ai_summary`（把 `station.digest` 送 `build_ai_summary`）；`StationReadout.add_n`＝`len(digest["adds"])` 只顯示檔數（重驗 @15cd8fff）；`etf_tab_dividend_station.py::_render_ai_summary`（規則式先出） | 複驗更正（H-14b） |
| D10 | **燈牆格名與數值只在 `title=`（桌機 hover）**，手機沒有 hover；逐檔明細面板（H-09b）未做 ⇒ 手機上只剩 glyph 條。判定符號（glyph）本身有傳達，缺的是「哪一盞燈」的非 hover 可讀性 | `page_hold.py::_render_light_wall`；`src/ui/render/station_cards.py`（`title=` 約 570–573 行、`render_legend` 約 601 行；重驗 @15cd8fff） | [F+I]（F：`title=` 存在；I：手機無 hover 的實機體驗未驗） |
| D11 | **熱力圖 treemap 以紅綠為主，缺排行表文字備援**（色盲／無障礙）；舊版有排行表 | `page_find.py` 熱力圖（`sector_heatmap_render.build_sector_treemap`）；舊 `etf_render.py::render_sector_heatmap` | INFERENCE／未複驗（本輪未讀 treemap 顏色與排行表程式） |
| D12 | **新頁卡片已以「狀態 glyph＋文字」呈現**（`Card.__post_init__` 擋「非 live 帶結論文字」與自帶 glyph）；舊 UI 的趨勢燈號／橫幅多為「顏色＋emoji＋文字」，未見純色狀態 | `src/ui/tabs/tab_today.py::Card`／`Note`（重驗 @15cd8fff：`Note.__post_init__` 約 199 行、`Card.__post_init__` 約 235 行存在） | 單組觀察，未窮舉（`__post_init__` 具體擋哪些條件 INFERENCE／未逐行複驗） |
| D13 | **Proxy 缺席說明缺**：舊 ETF 單檔有「PROXY_URL 未設→費用率／折溢價／經理人／AUM 全 N/A」專屬警示；新頁無此提示（`page_inspect.py` 無 `PROXY` 字串）⇒ N/A 的**原因**看不到 | `src/ui/etf/etf_tab_single.py`（~~約 112–132 行~~ 重驗 @15cd8fff：PROXY 健診約 121–135 行，僅 `.TW`／`.TWO` 代號，查環境變數與 secrets 的 `PROXY_URL`／`NAS_PROXY_URL`）；新頁 `page_inspect.py` 對 `PROXY` 字串 0 命中（grep -c） | 複驗確認 |
| D14 | **429 配額用罄在 💼 被當成「讀取失敗」紅卡**，指路是「確認網路與 Google 授權」而非「等 1 分鐘」；資料層其實已分類（`READ_ERROR_QUOTA_EXCEEDED`），👤 有用、💼 沒接 | `src/ui/views/page_hold.py` 讀取分流（`error_src`／`read_error`；指路句 `_V2_CHECK_NET`＝「先確認網路與 Google 授權是否仍有效」，約 4566 行）；`src/data/portfolio/gsheet_portfolio.py::classify_read_error`／`READ_ERROR_QUOTA_EXCEEDED`（約 729–760 行）；`src/services/me_account_service.py`（👤 使用） | 複驗升為 [F]（重驗 @15cd8fff：`page_hold.py` 內無 `READ_ERROR_QUOTA_EXCEEDED` 引用；本項屬 §19.8「error≠missing」類，但僅此一項） |
| D15 | **舊資料來源 chip／抓取時間在新頁看不到**：舊個股頁有逐來源 chip、降級警示、過期值警示；新版以每張卡四態呈現失敗／缺值 | 舊 `tab_stock.py` 約 480–560 行 | **INFERENCE／未複驗**（重驗 @15cd8fff：本輪未重讀該段，也未逐卡讀完新頁 fact 欄；舊 chip 的有無與新版是否等價均不得當 FACT） |
| D16 | **新頁在沒有 K 線的頁面宣稱 K 線口徑**：form 內 caption「K 線一律用還原價」，但 K 線本身未接線 | `page_inspect.py` form（重驗 @15cd8fff：caption「K 線一律用**還原價**…」約 2972 行存在；`STOCK_DETAIL_SECTIONS` 內「K 線＋均線」被標 `unwired`，指路 `DETAIL_WHERE`） | 複驗確認文字存在；「易誤導」為 INFERENCE |
| D17 | **MA 勾選「看得到、按得動、沒效果」**（僅回顯於判型卡 fact） | `page_inspect.py`（重驗 @15cd8fff：6 個 checkbox key 前綴 `SS_MA_WIDGET_PREFIX="p03v_ma_"`，勾選值寫入 `SS_APPLIED_TICKER["mas"]`；`req.mas` 在檔內僅 1 處讀取，用於組判型卡 fact 字串〔約 1903 行〕） | 複驗更正（A-22）；重驗成立（單檔 grep） |

#### 12.7.3 文案誤導與指路問題

1. 卡名「AI 戰情總結（唯一推播出口）」無任何推播動作（真推播是 cron）；舊鈕「讓 AI 潤成推播文字」也不推送。
2. `LEAF_SETUP_TITLE`「組合設定（＝組合管理＋Sheet 綁定）」在唯讀後會被誤讀（`BACKLOG` `ME-LEAF-SETUP-TITLE` 已登）。
3. 葡萄串卡寫「現行入口：既有的 🏦 ETF 分頁」：新版模式看不到，且實際不在 🏦 ETF 頁籤（唯一掛載是戰情室 expander 5️⃣；重驗 @15cd8fff：`render_grape_ladder` 全 repo 僅 `etf_tab_dividend_station.py` 一處呼叫）；v2 卡面短句不含此錯誤指路，**同一張卡在兩種卡面說法不一致**，使用者預設看到哪版（複驗：無法確認）。
4. 登入逾時指路「請重新整理頁面以自動恢復登入」（`LOGIN_EXPIRED_WHERE`）與 NAV-PERSIST 衝突：重新整理會使選定組合／觀察清單消失、側欄回到「不使用」（`page_me.KNOWN_LIMITS`）⇒ 照指路做後 💼 落到「還沒選定」灰卡。[F：兩段文字；I：實機是否必然發生，未驗]
5. `ME-OLD-TAB-POINTERS`、`ME-HOLD-CARDFACE-PHRASE`、`ME-HOLD-COUNT-DIVERGED`、`ME-UI-STRINGS-REVIEW` 等 BACKLOG 既有列與上述現象相關，本批不動。

#### 12.7.4 預設值與示範行為的消失（資訊面）

- 舊 UI 預設代碼（`2330`／`0050`／寫死的 10 檔與 5 檔 ETF）與範例持股（0050／00713／BND／00878）讓使用者一鍵看到示範；新頁一律空白或拒絕範例持股，**更誠實，但示範入口消失**（客戶是否在意：見 S 系列，未單列）。
- 舊戰情室「此 Sheet 有多本組合，只取第一本」是唯一讓使用者看見「系統替你選了」的揭露；新頁取而代之的 👤 選定，但 💼 葉1 不寫正在分析哪一本（S23）。


### 12.8 Stage B 建議（**只是建議，不是設計**）

> 本節不決定任何投資語意、不設計任何畫面、不授權任何施工。
>
> **流程定位（更正 DEC-082 誤引）**：~~DEC-082：客戶裁示 §12.5 之後才可進 Stage B~~（更正原因：DEC-082 的 Stage A→B→C→D 中，**正式客戶 Gate 在 Stage C**——Stage B 草稿完成後停手等客戶裁示，Stage C 核准後才可進 Stage D 施工；DEC-082 沒有「須先裁示 §12.5 才能進 Stage B」這一條）。本盤點若選擇在進入 Stage B 之前停手，那是「**本輪工作安全停點／總管流程（非 DEC-082 條文；DEC-082 的正式客戶 Gate 在 Stage C）**」。
>
> **S1～S28 的定位**：本輪**不要求客戶逐題裁示 S1～S28**。S 項是「Stage B 前置候選問題／decision-note」（格式：`【decision-note：待客戶裁示 S#】`）；Stage B 再把它們收斂為少量 Decision Gates，隨線框草稿一併送 Stage C 客戶 Gate。以下僅是「落盤組依三份盤點，建議總管如何排序」，**待總管確認**。
>
> 頁名採「責任名＋（現行 nav：…）」寫法；責任名不等於現行 nav 命名（DEC-085／`PROJECT_RULES.md` §19.2），對映屬後續 IA Decision Gate，本節不決定。

#### 12.8.1 建議的頁面順序（**待總管確認；不是已核准的順序**）

1. **先整理「前置候選問題」（不寫任何草稿）**：S1（⚡／🛡️／🎯 這三個盤點範圍標籤各自涵蓋什麼）、S13（「健康度」命名）、S23（誰是我的持股）、S24（指路句與切回舊版）。這四項會影響三塊範圍的結構與用字；Stage B 草稿應把它們作為 decision-note 明列，而不是預設答案。**本輪不要求逐題裁示。**
2. **🛡️ 持股（現行 nav：💼 我的持股）優先出線框——此為待總管確認的建議，不是已核准的順序**：理由——(i) 新頁已存在、已唯讀運作，缺口具體（逐檔戰情表、規則式事實先出、逐盞燈明細、指路句、重新讀取）；(ii) 其中 Data≠AI 違反（D9）是現成的資料治理問題；(iii) 多數缺口不涉及新投資語意（是把舊版已有的規則式結果原樣呈現）。相關 decision-note：S21、S23、S24、S25。
3. **🎯 標的（現行 nav：🔍 找標的、🔬 查一檔）第二**：先以「讀取類」補強為主——名稱搜尋／帶入持股／候選→查一檔跳轉（S17）、熱力圖補全（S18）、MA 勾選處置（S19）、批次上限（S20）、選股網預設因子（S14）、初篩涵蓋率警示（S27）、七段清單外的靜默缺席（S28）。**寫入類（S15、S16）不放 Stage B 第一批**，另走 High Gate。
4. **⚡ 行動（現行 nav：尚無對應頁；歸屬待 IA Decision Gate）最後**：整頁尚不存在，且幾乎每一項都落在投資語意或歸屬未定。建議 Stage B 對此塊只從「彙總＋連回」（S1 候選 a）的最小版本起草，不複算任何規則；S1～S12 以 decision-note 呈現，**不得在草稿中預設答案**，由 Stage C 客戶 Gate 一併裁示。

#### 12.8.2 Stage B 草稿的處理方式建議（S 項分類；**不是客戶逐題裁示順序**）

> 本輪不要求逐題裁示 S1～S28。下表只說明「Stage B 草稿遇到這些 S 項時的建議處理方式」；S 項本身是 decision-note，Stage B 再收斂為少量 Decision Gates。

| 類別 | 項目（S 編號） | 說明 |
|---|---|---|
| **風險較低、可隨線框草稿一併呈現的 decision-note**（輸入面／揭露面／指路用字，不涉及新投資語意） | S14、S17、S18、S19、S20、S21、S24、S25、S26、S27、S28 | 草稿可附推薦並標 `【decision-note：待客戶裁示 S#】`；其中 S21 須先確認 DEC-017 線框是否已涵蓋「點列展開」（見 12.2 H-09b） |
| **涉及投資語意、歸屬、寫入或 High 的 decision-note**（草稿須標明、不得預設答案，不納入 Stage B 第一批的可施工範圍） | S1～S12、S15、S16、S22、S23 | S3／S4／S5／S6／S12 屬高風險投資語意（12.5.2 清單）；S15／S16 寫 Google 或涉及不可重建歷史；S11 涉及寫外部系統；S22 涉及門檻與歸屬。Stage B 應把它們收斂為少量 Decision Gates |
| **Stage B 前置候選問題**（建議最先整理，見 12.8.1 第 1 點） | S1、S13、S23、S24 | 影響結構與用字；同樣是 decision-note，本輪不要求逐題裁示 |

#### 12.8.3 Stage B 工作規則（沿用既有治理，非新規則）

- 任何新控制項、欄位增減、分頁動線異動都須先出**文字線框**（`CLAUDE.md` §-1.5.D v3 §03-2 ①、DEC-003）；修正錯誤（畫錯欄位）不在此列，但須在交付報告揭露。
- 一律**原樣引用** L2／L3／L0 的結果：不改門檻、不換權重、不合併分數、不新增 Action 語彙、不複算建議持股水位（只引用 `get_allocation`）。
- ⛔ 不碰：`PRODUCTION_WRITE_APPROVED=False`（DEC-066 F）、不可重建歷史（`data_cache/forward_test/picks.parquet` 等）、Google 寫入與 OAuth（DEC-082／083）、不刪舊 UI（DEC-081 第 8 點、DEC-083 E 段 Removal Gate）。
- 新頁每個 Card 沿用「狀態 glyph＋文字」「缺值≠0／中性／正常／HOLD」「Data≠AI 分區」；搬入 AI 時揭露不得縮減。
- Stage A 的限制延續到 Stage B：**未實機操作、未跑測試、複驗僅抽驗**；Stage B 草稿引用本節任何 FACT 前，應由獨立一組就該條重新讀碼（`CLAUDE.md` §-2 規則 3／6）。
- 本節產出前沒有任何 UI code、navigation、舊 UI 刪除、Sheet 寫入或 OAuth wiring 被改動（本批只動 `docs/**`）。

#### 12.8.4 DEC-085／`PROJECT_RULES.md` §19 對 Stage B 的約束

> 以下為後續 Stage B 草稿**必須遵守**的約束（DEC-085 客戶 2026-10-26 裁示；`PROJECT_RULES.md` 第 19 節為忠實濃縮，與 `docs/DECISIONS.md` DEC-085 原文有出入時以原文為準）。**本節不授權任何施工**（§19.11）：不開 P2、不刪舊 UI、不改 nav、不改投資規則；~~Stage B／C／D 仍依 DEC-082 須客戶 Gate（正式客戶 Gate 在 Stage C）。~~（更正原因：2026-10-26 有意識的更正，不是漏刪，決策者 AI 總管；原句易被讀成 Stage B 亦須客戶 Gate）依 DEC-082，正式客戶 Gate 在 Stage C（Stage B 草稿完成後停手）；Stage D 須客戶核准。

1. **Stable responsibilities（§19.1／§19.2）**：Stage B 草稿不得把 📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股／👤 我的／🩺 資料中心 這六個長期責任方向，直接當成現行 nav 名稱或既有 view 的一對一對映；責任名與現行 nav 的對映屬後續 IA Decision Gate，草稿只能以 decision-note 提出。不得因小功能增加就反覆改變主要頁面責任與導航定位；重大 IA／頁面責任變更仍屬客戶 Decision Gate。UI 依賴穩定的 domain contract，不得綁死單一 API、資料供應商或抓取方式。
2. **SSOT（§19.3）**：Sheet binding、portfolio、watchlist、authentication、market state、investment rule output、data-health state 不得在新頁各自維護第二套實作或另建來源；UI 只消費既有狀態（例：持股／觀察清單經 `holdings_service`、建議持股水位經 `get_allocation`）。對照本盤點 12.4 的重複入口（R2／R5／R6／R8、建議持股水位 6 份）——草稿不得再增加第 N+1 份。
3. **Data Contract（§19.7）**：草稿中的資料需求以穩定 domain contract 描述（價格、日期、freshness、source、status），不得依賴「Yahoo 回傳第幾欄」「MoneyDJ HTML selector」「某 API 特定 JSON 路徑」；provider-specific parsing 限制在 adapter／ingestion layer。
4. **Missing semantics（§19.8）**：missing≠0；missing≠中性；missing≠正常；missing≠HOLD；proxy／estimated≠real；**stale≠current；error≠missing**。UI 必須能表達這些不同狀態，不得只靠顏色。⚠️ 本盤點 12.7 對「stale≠current」「error≠missing」**未逐條盤點**（僅 D14、D15 順帶涉及），Stage B 草稿涉及相關卡片時須先補查。
5. **Presentation／Decision Logic 分離（§19.9）**：layout、component、copy 的調整不得偷偷改變 threshold、weights、eligibility、investment semantics、Risk Cap、trend／valuation definition；UI change 與 investment-rule change 是不同類型、不同 Gate（對照 12.7 D8：inline 數字不得「順手」抽常數改值）。
6. **Old→New capability conservation（§19.6）**：新 UI 改版必須先做 Old UI → New UI Interaction Coverage；舊 UI 是功能、邏輯、互動、資料來源的參考，**不是視覺模板**；每個舊功能的 Coverage 狀態只能是四種之一：`✅ 已覆蓋`｜`🟡 部分覆蓋`｜`⬜ 未覆蓋`｜`🚫 明確不再需要／不應搬入`（待客戶裁示的事項只能放 `【decision-note：待客戶裁示 S#】`，不得成為第五種狀態）。`🚫` 是 AI 盤點建議，**最終認定屬客戶**，不構成任何舊 UI 刪除授權；未完成替代前不得因新 UI 上線就直接刪舊 UI（與 DEC-019／020／081／083 同向，不放寬）。
7. **併注意（§19.4／§19.5）**：規則模組（市場位階、指標危險度、Risk Cap、台股趨勢、國際趨勢、估值、個股／持股判讀）不得為 UI 簡化而硬合併成單一不可追溯分數（需要 aggregate view 時，constituent signals 與 provenance 必須保存）；AI 只是分析／解釋層，只能讀取既有、可追溯的資料與規則輸出，更換 model／provider／prompt 不應迫使資料層、核心規則或 UI 資訊架構重做（對照 12.4.2 第 9 點 AI 觸發各自實作）。
