# 💼 持股頁｜Old UI First 盤點（唯讀研究）

> **研究候選，非授權、非投資判斷。**
> **研究候選，不是授權**：不授權接線、OAuth、Sheet 讀寫、Risk Cap 顯示、公式變更。基準 main `e909152`（程式碼閱讀；未執行任何 Sheet／OAuth／網路）。
> 依據：Gap Audit 2026-11-09、Old UI First Gate 2026-11-08、DEC-141（W-11：僅版面／空槽）、DEC-080／RC-VISIBILITY、DEC-122 Q2、DEC-092 Q4。

## 0. 結論先講
- 舊 `page_hold.py` **本身唯讀**（檔頭 + `tests/test_p04_hold_view.py::TestReadOnly` 以 AST 白名單／黑名單釘住，已讀檔頭；測試本體 NOT VERIFIED 逐行）。但**讀取憑證的 OAuth scope 含寫入**（見 §2），唯讀是「程式紀律」不是「憑證限制」。
- UI2 現況：`src/ui2/views/hold.py` 只渲染 PageVM；`scenarios.py` 的 hold 是 FAKE 骨架；`real_feed.py` 只讀 TWII＋Regime 兩個事實。持股／Sheet／Risk Cap **0 接線**。
- G2F 守衛（`tests/test_ui2_guards.py::G2F_IMPORT_ALLOWLIST`）僅放行 `get_twii_trend_view`、`get_macro_regime` 與 `real_canonical` 具名符號；`_G2F_BANNED_NAMES` 明列 `get_holdings／get_sheet_view／get_account／get_allocation／compute_and_lock_risk_cap／logout／build_login_url`，G9 禁 `session_state`（僅 `ui2_` 前綴）。→ 目前**結構上就接不進去**，擴充必須先過 Gate。

## 1. Evidence Matrix
| 項目 | 舊 caller | L3 | L1 | 來源／as_of | 新鮮度／PIT | 缺值處理 | 讀寫／權限 | UI2 狀態 |
|---|---|---|---|---|---|---|---|---|
| Sheet 綁定／登入狀態 | `page_hold.py::load_binding` | `portfolio_binding_service.get_binding_state(ssot=True)`、`get_active_sheet`、`get_active_selection` | `gsheet_portfolio` 的 `session_binding_snapshot`、`_has_oauth_tokens`；`oauth_state.get_login_state` | `st.session_state['gsheet_tokens']`／`portfolio_sheet_id`（OAuth token＋Sheet ID）；無 as_of | session 級；`login_expired` 逾時另有狀態 | 未綁＝`bound=False`＋空清單（灰，有效結果）；讀失敗＝紅 | L3 docstring 自陳純讀；底層讀 session（G9 禁） | **canonical-only**（me.py 為 FAKE） |
| 持股清單原料（ticker／lots／avg_price） | `load_holdings` | `holdings_service.get_holdings(keep_blank, resolve_names)`→`HoldingsResult` | `gsheet_portfolio.list_portfolios`／`load_portfolio`（`portfolios` 分頁；欄 `name,ticker,lots,avg_price,updated_at`）；快取 TTL_15MIN，鍵含身分指紋＋sheet_id＋B5 世代 | 使用者自有 Google Sheet；列有 `updated_at` 但未傳 UI；**無單一組合資料日** | 使用者手填；非 PIT（無成交日／淨值日） | 預設丟 lots≤0／avg≤0 列；`keep_blank=True` 空白格＝None（⛔ 非 0）；無 `portfolios` 分頁＝`worksheet_missing`（灰，不建分頁）；表頭不符／權限／網路＝raise；未選組合＝`not_selected`（不讀任何一本） | 純讀；唯組合讀取失敗 raise、觀察清單失敗只記 `watchlist_error` | **canonical-only**（G2F 明列禁 `get_holdings`） |
| 逐檔戰情列（現價、市值、損益%、燈號、建議動作） | `load_station` | `dividend_station_service.get_station_rows`→`build_station_rows`／`fetch_metrics` | Yahoo／FinMind 等 fetcher（現價、週線、財報）；NOT VERIFIED 各源逐一 | 價格 as_of／src／stale 在非顯示鍵 `PAL.KEY_PRICE_AS_OF` 等（`_price_asof_fields`，台北日 `taipei_today`） | 價格新鮮度以 `assess_price_freshness`；過期價仍計入市值（DEC-102 只標示） | 缺現價存 None（不捏 0）；異常輸入→`KEY_INVALID_INPUTS`；外幣未確認→總額／比例回 None（XV-H3） | **純讀但對外網路**（行情） | **canonical-only** |
| 組合總額／損益 | `page_hold`（station 區） | `compute_portfolio_totals(rows)`（lots×1000×price，`SHARES_PER_LOT` SSOT） | — | 由列推 | 部分缺價→`partial=True`＋`valued_n/held_n`；全缺→None | 不顯示 0 | 純函式（需列） | **canonical-only**；DEC-141 Q4：組合層日期不得自算 |
| 80/20 配置 | `build_allocation_split_card` | `compute_allocation_split(rows)`（核心=ETF／衛星=個股，近似；目標 `T.CORE_TARGET_PCT`） | — | 用「市值＝張×現價」（張·元） | 同上 | 無市值→None；partial 標示；異常輸入／外幣→None | **純函式，但輸入需 Sheet 持股＋現價** | canonical-only |
| 衛星停利 | `build_take_profit_card` | `flag_take_profit(rows)`（損益%≥`SATELLITE_TAKE_PROFIT_PCT`=15） | — | 同上 | — | 無成本→不判 | 純函式（需列）；DEC-093：停利排位未裁示 | canonical-only |
| 建議持股水位／Risk Cap | `load_allocation`→`build_position_cap_card` | `allocation_service.get_allocation(strict, require_valid_risk_cap=True)` | `macro_state_locker.get_macro_state` 讀 `risk_cap_state.json`（新）／`macro_state.json`（舊）；`calculate_system_state`（`macro_state_locker.py:722`）為規則引擎 | 本地快照檔（`compute_and_lock_risk_cap` 寫）；`input_asof`／`not_evaluated`／`snapshot_ts` 在揭露物件 | 7 天沿用須揭露（DEC-080 §5，RC-VISIBILITY）；PIT 見 C2a／PIT #1038 阻塞 | 無有效上限→「建議持股：無法判定」（`risk_cap_gate.RISK_CAP_UNAVAILABLE_*`）；核心缺→不寫檔 | **讀路徑會寫 session 快取鍵**（`_ALLOC_CACHE_KEY`）；**寫路徑** `risk_cap_apply.compute_and_lock_risk_cap` 寫兩個本地檔（由「🚀 更新」觸發） | **preview-slot（空槽）**；DEC-141 Q5 禁讀數值 |
| Risk Cap 歷史（排程） | 非 page_hold | `risk_cap_history_service`／`risk_cap_history_reader_service.read_history` | `src/data/risk_cap/history.py`；`PRODUCTION_WRITE_APPROVED=False` | 服務帳號／WIF；與 UI 無關 | — | — | 讀：SA 唯讀 scope；寫：WIF 且旗標 False 一律拒 | **不得接 UI2**（DEC-141 Q8） |
| 產業曝險／集中度 | **page_hold.py 無**（grep `concentration/industry` 0 命中） | 舊用在個股組合：`stock_grp_service`→`compute_industry_concentration` | L2 `compute/risk/concentration.py`（純函式）；產業別 L1 `fetch_industry_category` TTL_1DAY | 個股組合走 `stock_watchlist`（**無張數**）→ 等權 1/N，`basis='equal_weight'`；未分類排除並給 `coverage_pct` | 產業別無 PIT | 未分類不入分母 | 純函式；輸入產業別需 L1 | **preview-slot（誠實空槽）**；W-11 Primary 但舊頁無對應＝**無對應，須新定義** |
| 出場訊號 | 非 page_hold（`tab_stock`／`section_portfolio_summary`／`watchlist_triggers`） | `evaluate_exit_signals`（L2，含 pandas 與可選 Gemini 新聞判斷） | 需個股 K 線、新聞 | — | — | — | L2 內有 `judge_news_sentiment`（AI，須 Gate） | 不在持股頁範圍 |
| 策略分類（存股／資本利得） | 非 page_hold | `strategy_class` 讀（DEC 內稱 AB-4r，`read_worksheet_values`） | 使用者手建分頁 | Sheet | — | 未分類；badge 值→`bad_strategy` | 純讀；**寫入面 HI-5 未核准** | 欄「策略」恆 `⬜ 未分類`（DEC-122） |

## 2. OAuth／Sheet 權限事實（`infra/oauth.py::GOOGLE_OAUTH_SCOPES`）
- 請求 scope：`spreadsheets`（**讀寫**）、`drive.file`、`drive.metadata.readonly`、`openid`、`userinfo.email`。**沒有 `spreadsheets.readonly`**；`gsheet_sa_reader` 才是 `spreadsheets.readonly`（排程用，Q8 禁入 UI）。
- 讀取函式（零寫入，B1）：`list_portfolios`、`load_portfolio`、`list_stock_watchlists`、`load_stock_watchlist`、`read_sheet_title`、`get_sheet_title`、`read_worksheet_values`、`read_forward_test_picks`、`load_forward_test_picks`、`list_user_sheets`、`list_user_folders`。
- 會 mutate：`save_portfolio`、`delete_portfolio`、`save_stock_watchlist`、`add_to_stock_watchlist`、`delete_stock_watchlist`、`append_forward_test_picks`、`create_new_sheet`（含 `_get_or_create_app_folder`）、`rename_sheet`。session 副作用：`oauth_state.apply_sheet_binding`／`clear_sheet_binding`／`set_active_selection`／`logout_google_session`／`handle_oauth_callback`（`st.query_params`、session）；`_expire_session_login` 也在**讀取中**改 session。
- 風險：憑證可寫 ⇒ 唯讀只靠 code 守衛（`tests/test_sheet_safety_guards.py` 的 `_READ_ENTRIES` 未含 `read_worksheet_values`，見 DEC AB4R-SHEET-SAFETY-ENTRIES）。

## 3. 權限矩陣（UI2）
| 類別 | 項目 |
|---|---|
| 可合法唯讀接線（需先 Gate 更新 G2F 白名單＋非作者 QA） | 以**單一新 L3 唯讀 facade** 提供：綁定四態（未登入／逾時／未綁／已綁）布林＋筆數；持股列原料（ticker、lots、avg_price，缺值 None）；`compute_portfolio_totals`／`compute_allocation_split` 純函式輸出；價格 as_of 分組（DEC-102）。**前提**：UI2 取得身分的方式（目前 G9 禁 session_state）須客戶 Gate。 |
| 需 OAuth／Sheet Gate（客戶） | 任何 token 流入 UI2、Sheet ID 綁定／選組合、登入／登出、登入逾時處理、`strategy_class` 讀入、scope 收窄為 `spreadsheets.readonly`（新 consent 流程）。 |
| 需 Risk Cap／RC-VISIBILITY Gate | 顯示任何 Risk Cap 數值／日期／「沿用 N 天」；`get_allocation`（會寫 session）；`compute_and_lock_risk_cap`（寫檔）；C2b 之前不得顯示獨立數字。 |
| **永不得無客戶 Gate 接線** | 所有 `save_/delete_/append_/create_/rename_/add_to_` Sheet CRUD；Drive 建檔；`PRODUCTION_WRITE_APPROVED`；`gsheet_sa_reader`／cron 快照／SA（DEC-141 Q8）；AI 自行取數或回寫；System Action／今日需處理聚合（Q6：Aggregator 前維持「⬜ 尚未提供」）；策略分類寫入（HI-5）。 |

## 4. 三方案
| 方案 | 正確性 | 風險 | 速度／Token | 備註 |
|---|---|---|---|---|
| A 重用 canonical L3（`get_holdings`＋`compute_*`） | 高（已有 fail-loud、四態、XV-H3） | 中：身分取得在 session，UI2 G9／G2F 不允；L3 讀取會碰 `st.session_state` | 最快最省 | 無法直接用，須先改守衛 |
| B 薄唯讀 adapter（L3 `ui2` facade，回 frozen VM 事實；內部呼叫 A） | 中高（需與舊頁 parity 比對、獨立 QA） | 中低 | 中 | 可把 session 讀取收斂到一處、輸出僅布林／筆數／數值 |
| C 新 fetcher／縮 scope／重做 Risk Cap | 未知 | 高（新 consent、Schema、公式） | 最慢最貴 | 未授權 |

## 5. 建議
**B（建 A 之上的 thin read-only facade）**，且分階段：(1) 先只做「綁定狀態＋持股原料＋總額／80-20」的資料契約與缺值矩陣（零 Risk Cap、零 AI、零寫入）；(2) Risk Cap 區維持空槽直到 RC-VISIBILITY／C2b；(3) scope 收窄與 Auth 屬獨立客戶 Gate。理由：A 直接用被守衛擋；C 無必要。**目前不建議任何施工，先送 Gate。**

## 6. 下一步 UI 設計輸入
- 客戶 Gate 題目：UI2 如何取得登入身分（session 橋接）＋是否收窄 scope；持股原料欄位定案（僅 ticker／張數／均價，或加 `updated_at`）；Primary「產業曝險／集中度」資料來源（舊持股頁無此功能；`concentration` 為等權、無張數，須明示假設）。
- 欄位：桌機 8／手機 4＋展開（DEC-141）；「策略」欄 `⬜ 未分類`；單位：lots=張、市值=張·元、總額=元；缺值寫原因不寫 0。
- 資料日採 DEC-102「多數＋例外分組」；不得以最舊一檔／今日／抓取時間冒充。

## 7. NOT VERIFIED
- 實際執行任何讀取（Sheet、行情、OAuth）— 全部未執行。
- `tests/test_p04_hold_view.py::TestReadOnly`、`test_sheet_safety_guards.py` 內容僅讀檔頭引用，未逐行驗。
- `page_hold.py` 5759 行僅讀函式清單、載入器與檔頭，未逐函式驗證所有卡片。
- 各行情 fetcher（`fetch_metrics`／`_fetch_stock_metrics`）來源、費用、fallback 未逐一追。
- `calculate_system_state` 內部公式、`get_macro_state` 完整優先序僅讀 docstring。
- DEC「Risk Cap 不獨立顯示」確切條文位置（DEC-092 Q2-2／DEC-081 Q2-2 以 DECISIONS 引述為準）；DEC-141 Q8 以全文引述。
- Streamlit Cloud 部署行為、`updated_at` 欄是否始終有值、使用者實際 Sheet 內容。
- `section_portfolio_summary`／`tab_stock` 的出場訊號是否與持股頁有未來整合需求（僅註記無對應）。
