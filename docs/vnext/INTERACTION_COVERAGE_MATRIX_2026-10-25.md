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

| 控制項 | 舊位置 | backend | 新 UI 位置 | 狀態 | 備註 |
|---|---|---|---|---|---|
| 讀持股 gate（只讀市場／加讀 Sheet）＋ 🚀 執行 | 舊：`etf_tab_dividend_station.py:196`（無範圍選擇） | `holdings_service::get_holdings` | `page_hold.py:4984`（`single_submit_form`，label 在 `:439`） | 已接 | |
| 顯示目前綁定的 Sheet | `portfolio_status_bar.py:84`（印 sheet_id）；`portfolio_manager.py:141` | `get_binding_state` | 🛡️ 只顯示「有沒有綁」（刻意不印 ID，`page_hold.py:991-996`） | 部分 | 要不要顯示 Sheet 名稱：`get_sheet_title` 已存在但沒人用 |
| 往「我的」設定的入口 | — | — | 文字指到側欄（`page_hold.py:1689-1692`、`page_today.py:1051`） | 部分（只有文字） | 沒有按鈕或連結；👤 我的頁還不存在 |
| 重新載入持股（繞過快取） | `etf_tab_dividend_station.py:142` | `clear_read_cache` | 無；`holdings_service.py:27` 明寫**不**呼叫 `clear_read_cache` | **待接** | INFERENCE：重按 🚀 可能在 L1 快取 TTL 內拿到舊值 |
| 資料狀態（idle／empty／failed／登入過期） | `etf_tab_dividend_station.py:171-197` | `portfolio_binding_service`、`holdings_service` | 🛡️ 卡片（`page_hold.py:1064-1230`） | 已接 | |
| 缺 Sheet 時就地綁定 | `etf_tab_dividend_station.py:187`、`portfolio_status_bar.py:78` → `portfolio_binder::render_holdings_binder` | 同 §1 | 無，只有文字指到側欄 | **dead-end（半）** | 見 §8 |
| ⚡ 生成 AI 總結 | `etf_tab_dividend_station.py:698`；`section_ai_portfolio.py:63／65` | AI L3 | `page_hold.py:5072`（label 在 `:3816`） | 已接 | |
| 組合／觀察清單管理（載入／儲存／刪除） | `portfolio_manager.py:166-298` | `gsheet_portfolio` CRUD | 未接線卡 `hold.setup.watchlist`（`page_hold.py:1798`）；`page_hold.py:5202` caption「唯讀 —— 要新增／修改／刪除請到既有的 📁 組合管理分頁」 | **待接**＋**dead-end** | 寫入 Google，High；🛡️ 目前以黑名單釘死唯讀（`page_hold.py:25-31`） |

## 3. 🎯 標的

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

FACT：沒有 view。候選舊控制項（INFERENCE；⚡ 行動的範圍尚未裁示，`DEC076-CONFIRM` ②）：

| 控制項 | 舊位置 | 狀態 |
|---|---|---|
| 🚀 跑存股戰情室 | `etf_tab_dividend_station.py:196` | 待接（⚡ 或 🛡️ 未定） |
| ✍️ AI 推播文字 | `etf_tab_dividend_station.py:698` | 待接 |
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
| 3 | `portfolio_manager.py:78`（`parse_sheet_id`） | 拒絕發布連結，回空字串 | **沒有 production caller**（只有測試） |
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
| 🔴 High（寫進使用者的 Google 帳號） | `create_new_sheet`、`save_portfolio`、`save_stock_watchlist`、`delete_portfolio`、`delete_stock_watchlist`、`add_to_stock_watchlist`、`freeze_current_picks`、`rename_sheet` | 需客戶核准；🛡️ 目前以黑名單釘死唯讀（`page_hold.py:25-31`），接這些等於改變唯讀政策。刪除與凍結快照屬「無法重建」（`CLAUDE.md` §-1.5.F 判定 3(5)），⛔ 不得逕行 |
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
