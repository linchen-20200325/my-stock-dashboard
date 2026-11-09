# New UI2｜📊市場＋🎯標的：Old UI First 深入接線差異矩陣（2026-11-09）
> **研究／需求候選，非施工授權。** GitHub 基準 main `f5e78e10672da2a4c22d880825241e502401c533`；當時 open #1093（另案五頁總覽）。本檔不同於 #1093：只做市場/標的的具名 caller→canonical→UI2 欄位契約與安全順序，不修改既有正式 Decision／BACKLOG／HANDOFF。新接手請重新驗 GitHub。程式閱讀≠即時資料可用／runtime 測試。 
> 上位依據：`docs/governance/OLD_UI_FIRST_ADAPTATION_GATE_2026-11-08.md`、DEC-125（市場研究）、DEC-128（Human UI vs Evidence）、DEC-146（頂部五頁）。歷史 `FINAL_UI_CAPABILITY_MAP_2026-11-02.md` 的 T11 狀態**不能**當現行 New UI2 接線事實。

## A. 📊 市場（保留現有首屏順序／暗色／兩列頂導）
| 能力／前端目標 | Legacy 程式與已有 canonical | New UI2 2026-11-09 code 事實 | 方案／必要 Gate |
|---|---|---|---|
| A1 台股當前收盤＋資料日 | `src/services/market_twii_view_service.py::get_twii_trend_view` → L1 `macro_cache_reader.load_twii_close`（保留 freshness attrs） | `src/services/ui2/real_feed.py::_read_twii` 現只取 `TWII_CARD_DAYS=1`；`real_canonical.twii_card_spec` 顯示最新收盤 | **KEEP**；已接 Real Preview，不得當長期走勢 |
| A2 台股歷史收盤圖／MA | `src/ui/views/_market_blocks.py::twii_chart_frame/render_twii_chart`；L3 `get_twii_trend_view(n_trading_days)` 可回歷史 xs/close，MA 舊呈現有參考線（非完整歷史 MA 曲線） | `src/ui2/components/html.py::primary_slot_html`（由 `src/ui2/views/market.py` 呼叫） **明確為無歷史序列空槽** | **A 優先**：先純研究 L3 視窗、資料日、NaN/回填/PIT 與 VM chart contract，再決定可否加性呈現；新增 MA 曲線/趨勢評分需獨立 Gate |
| A3 國際趨勢 | `_market_blocks.py::intl_series` 從舊 session 的 `cl_data['intl']` 讀；來源不是可直接搬到 UI2 的純 canonical L3 | Real Feed 僅 TWII+Regime，**未接**國際指標 | **B 候選**：查找無副作用的既有 L3；若只有 session 資料，先做 thin readonly adapter／PIT／source 比對；不得直接 import 舊 render 或 session |
| A4 市場位階（Regime） | `src/services/allocation_service.py::get_macro_regime(strict=True,require_valid_risk_cap=True)` | `real_feed._read_regime` 已接；`real_canonical` 跨市場/標的共用同一 RegimeFact | **KEEP** 現行權威，絕不新算多空燈或自主出手 |
| A5 市場動作／Risk Cap | 舊 `page_today.py`、`page_market.py` 有更新與風險卡，但舊 `page_today`/`page_market` 的「🚀更新今日戰情」（`macro_refresh_service` 寫 session／檔；寫入內容未逐項查證）不是 UI2 合法 caller | `src/services/ui2/market_vm.py` 對 action 恆標待 Aggregator；Risk Cap 無獨立已核准可顯示上限 | **BLOCK**：先確認 System Action/Risk Cap 正式裁示與 write permissions；現階段誠實不可判定 |
| A6 16 燈、CPI/PMI、國際宏觀、風險面向 | 舊 `page_market.py` + `page_today.py` + `src/ui/tabs/macro/*`；完整細節先核對 caller→L3→L1 | UI2 `MARKET_CARD_IDS=(twii,vix,us10y,spread,dxy,pmi)` 是**排列契約**，不是 6 項真資料全接 | **A/B 分類稽核**：逐項 source/status/as_of/published/fetched/資料資格；未驗證保持空槽 |
| A7 大盤 EPS×PE | `docs/vnext/MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md`、`NEWUI2_XIAO_PDF_MARKET_RESEARCH_EXTRACTION_2026-11-06.md`（簡報內容屬引用/假設） | 無正式大盤 forward EPS/PE source/model，UI2 無合法實數 | **RESEARCH ONLY**；年度/預估版本／發布時間／估值假設／情境組合必走 Source/Model High Gate，不用簡報假設當現值 |

## B. 🎯 標的（雙模式已存在，別重做）
| 能力／使用者任務 | Old/Legacy 與 service 依據 | New UI2 code 事實 | 方案／必要 Gate |
|---|---|---|---|
| B1 市場精選／查一檔雙模式 | `src/ui/views/_target_blocks.py` 原本單頁多區＋session 事件隔離；T11 為 2026-11-02 歷史狀態，已被 `target.py` 雙模式取代 | `src/ui2/views/target.py` 現有兩模式，radio `ui2_target_mode` 僅呈現切片 | **KEEP**；不另設導航／不搬 Streamlit session |
| B2 單檔代碼輸入查詢 | 舊 `page_target.py`、`_target_blocks.py::load_single` 具真正 loader/builder；需追其 L3 實際副作用 | UI2 `src/ui2/components/html.py::search_html(t.search)` 的 search/CTA 明確 **disabled Preview** | **A→B**：先證明可安全重用 canonical L3；需要 read-only query boundary、格式與快取、失敗不連擊；不得變相寫 Sheet |
| B3 基本面初篩與候選池 | `src/services/fundamental_screener_service.py::get_fundamental_prescreen/get_fundamental_survivors/get_ranked_picks`，L1 snapshot+L2 prescreen；有 cache／refresh 參數 | UI2 僅 Preview 候選卡；Real Feed 未接 candidate | **A 優先**：核對 `refresh=False` 無外部副作用、coverage/meta/as_of/PIT、全母體 vs Top N，不擅改候選排名與排名資格 |
| B4 產業動能/資金潮汐 | `src/services/sector_flow_service.py::get_sector_flow_view` L3 已存在；**有**可選 stock_sheet_id→GSHEET 的 read path，且失敗可能略過 watchlist highlights | UI2 Real Feed 沒有接 sector；不可以「看不到 highlight」冒充無持股 | **A/B with explicit arg contract**：研究固定不傳 stock_sheet_id 的唯讀路徑及 source completeness，不可默默帶入私有 Sheet；部分涵蓋要明示 |
| B5 估值與財報分析 | 舊 `_target_blocks.py`、`page_inspect.py`、Fundamental L3/compute 已有部分能力；先找每一計算的正式 RuleID | UI2 未正式顯示 PE/PB 河流/Forward EPS 或完整 6 維 Snapshot | **個別資料契約 Gate**；禁止重算買賣點、目標價或用無來源估值數補空槽 |
| B6 觀察清單／持股寫入 | 舊 `watchlist_service.add_picks_to_watchlist`、`gsheet_portfolio` | UI2 target 明文禁止寫入 watchlist、portfolio、Sheet | **STOP** 直到 OAuth/Sheet/Write Risk Gate；不以「搜尋可用」暗示可加入持股 |

## C. 優先級與工作拆分（最多三項安全研究）
1. **MKT-01 台股主圖**：只產出 canonical input/schema/時間軸/缺值/來源契約與 Real Feed read-only 擴充提案；不碰資料/程式。先驗圖表渲染可接受的 `xs/close` 日期單位與 freshness、週期切換成本。判定 KEEP/A 或 thin B。
2. **TGT-01 查一檔**：描出舊 `load_single` 實際 L3 calls/副作用，核對 UI2 disabled CTA 的最小只讀解封前提；不得提早啟用。
3. **MKT-02/TGT-02 一致性**：市場 Regime canonical 同次結果、候選池是否引用同一 Regime，列出 not evaluated/missing/stale/unavailable/proxy、狀態與技術驗收；只做設計不動權重/門檻。

## D. 三方案比較
| A 重用 L3／UI2 Feed VM | B 新薄唯讀 L3 | C 新來源或公式 |
|---|---|---|
| 最少風險、最快、Token 最省；先查實際 I/O 與 schema，再決定能否接 | 現有 service 只靠 session/old UI 時可行；要負測及雙向差異比對 | Source/PIT/授權/公式風險最高；在更高 Decision Gate 前禁做 |

**設計決定尚待**：市場主圖是歷史收盤圖或加性 MA 曲線、標的搜尋具體欄位/手勢、國際趨勢輸入明細、候選篩選操作、是否顯示研究性 EPS×PE 情境；都不能以本研究文件取代 User Visual Gate。已核准五頁頂部兩列導航和首屏 ≥160px 的安全門檻沿用。
