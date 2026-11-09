# 📊 市場頁：台股歷史主圖＋國際趨勢｜Old UI First 資料接線稽核（2026-11-09）

> **研究候選，非授權、非投資判斷。**
> **狀態：研究候選，非施工授權。** 基準 main `e909152`（clean detached worktree 唯讀）。僅讀程式碼與 repo 內 `data_cache` 快照；**未連網、未跑 Streamlit、未驗證部署端資料**。
> 不重複 `NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT` 的 A2/A3 結論；本檔補：實際 symbol、欄位、新鮮度/缺值規則、副作用、守衛可行路徑。EPS×PE 維持 Research，不在本檔範圍。

## 1. Evidence Matrix
| 項目 | Old UI caller | L3 | L1 | 來源/as_of | 新鮮度/PIT | fallback | 缺值 | 副作用 | UI2 現況 |
|---|---|---|---|---|---|---|---|---|---|
| **(a1) 台股歷史收盤線** | `src/ui/views/_market_blocks.py::twii_chart_frame`／`twii_chart_spec`／`render_twii_chart`（收盤線＋MA 水平參考線，MA 取自 session「市場評估」，非歷史 MA 曲線） | `src/services/market_twii_view_service.py::get_twii_trend_view(n)`→`TwiiTrendView`(xs/close/n_available/as_of/is_stale/stale_reason/age_days/upstream_error/upstream_state/failed) | `src/data/macro/macro_cache_reader.py::load_twii_close`→`_attach_staleness`→`compute_cache_staleness`；`CACHE_DATASET_CADENCE["twii_ohlcv"]=("daily",None)` | `data_cache/twii_ohlcv.parquet`，由 `scripts/update_macro_history.py::fetch_twii_ohlcv` 以 cron 寫入（Yahoo Chart `^TWII` 1d，`source="Yahoo:^TWII:chart"`）。as_of＝parquet 最後 `date`。repo 快照（非部署證據）：4912 列，2006-09-29～2026-11-06 | 日頻天數門檻在 `shared/staleness.py`（本檔未逐值核對）；判不出→`is_stale=True`；資料日>今日→過期。Yahoo EOD≈翌日 04:00 TW（CLAUDE §2.3）；**本路徑無「進行中 K 棒」剔除**（`drop_in_progress_bar` 只用於 `fetch_lead_market_changes`，與此圖無關） | 單一來源；無備援。讀不到→`ok=False`，例外→`failed=True`（灰/紅分離）。cron 失敗不覆寫舊檔，改記 `last_error`→`upstream_state`（NO_NEW_DATA／FETCH_FAILED／UNDETERMINED，`shared/upstream_state.py`） | close 先 `dropna`、不補值；`n_trading_days<1`→`ValueError`；attrs 缺→`is_stale=None`（⬜未判定，不當新鮮） | **無**：不快取、不碰 session、無網路；只讀本機 parquet（但 `load_twii_close` 會 print log） | **canonical-only**：`real_feed._read_twii` 只取 `TWII_CARD_DAYS=1`；主圖 `src/ui2/components/html.py::primary_slot_html` 為誠實空槽（capability not_provided） |
| **(a2) 成交量處理** | 舊主圖**不畫量**（`_market_blocks.py` 無 volume 用法，grep 0 命中） | `TwiiTrendView` **不含 volume**；`macro_v2_service.py::_TWII_OHLC_COLS` 明確排除 volume；`market_strategy.py::volume_window_stats` 把 0 視為缺值 | `twii_ohlcv.parquet` 有 volume 欄；`update_macro_history.py` 寫入時 **volume==0 且 high>low → 顯式寫 NaN＋log**（非 0） | 同上。repo 快照：volume 34 列 NaN，最近 8 列僅 11-05 有值（4,239,400）→ **量欄極稀疏** | 量欄不可信（歷史上連 33 交易日為 0，後零星 0；見 `macro_cache_reader.load_extreme_risk_legs` docstring） | 無 | CLAUDE §1.A：全 0 隱藏。現行等價作法＝**根本不取量**。若 UI2 要畫量：必須由 L3 新增並輸出 NaN≠0、全空/全0→整欄不給 | 無 | **preview-slot**（無量欄；不是 bug，是刻意） |
| **(b) 國際趨勢（DJI/IXIC/SOX/US10Y(^TNX)/DXY）** | `_market_blocks.py::intl_series(session)`←`session["cl_data"]["intl"]`；`INTL_GROUPS`；`basis_chart_b`；`page_market.py` 約 L560/L727 | **無乾淨 L3**：資料來自 session `cl_data`，由 `macro_fetch_orchestrator`（`_job_intl`，`INTL_MAP` 取自 `daily_checklist.INTL_MAP`）→`macro_session_patch`（`intl=bundle["intl_raw"]`）→ 舊戰情更新寫 session | `macro_core.py::fetch_yf_close`（NAS proxy→Yahoo Chart，module-level TTL＋失敗冷卻 `_FAIL_COOLDOWN_SEC`，attrs 含 source/fetched_at） | Yahoo `^DJI ^IXIC ^SOX ^TNX DX-Y.NYB`。`IntlSeries.last_date` 取序列末列；**無 is_stale/age 判定** | 無 freshness 規則、無 PIT 剔除進行中棒（`fetch_yf_close` 不呼叫 `drop_in_progress_bar`）；US EOD 時差未處理 | `absent`／`empty`／`ok` 三態；無備援 | 缺系列→`absent`（不補 0）；`dropna` | **有**：資料需先按「🚀更新」→`refresh_macro_now` 寫 `st.session_state`（cl_data 等）＋網路；`intl_series` 本身純讀 session | **未接**（`real_canonical._not_provided("us10y"/"dxy", _R_SESSION)`） |
| **(b2) VIX** | 舊戰情 `macro_info['vix']`；`dated_inputs.extract_vix` | 無單點唯讀 L3 可直接給「歷史序列」；`dividend_station_service.fetch_vix(strict)` 回**純量**且會連網 | `macro_snapshot.py::fetch_vix_block`：`yfinance.download('^VIX',3mo)`（**非 NAS proxy 路徑**），`_cache_success_only(TTL_1HOUR)`，失敗不入快取；回 current/ma20/dates/values/date/source/fetched_at | Yahoo `^VIX`；as_of＝`date` | DEC-070 要求「VIX 只用已完成收盤」**只裁示語意於 Risk Cap（PROJECT_STATE.md L67），程式未實作**；顯示路徑不剔除進行中棒 → **NOT VERIFIED 是否出現盤中值** | 無（FRED `VIXCLS` 未作為此路徑備援） | 末筆非有限/≤0/>`VIX_FETCH_MAX`→視為失敗；<3 筆→`not enough data` | 連網＋Streamlit cache；經 refresh 才進 session | **未接**（`not_provided`） |
| **(b3) US10Y** | session `macro_info['us10y']`（FRED DGS10）與 `cl_data.intl['10Y公債殖利率']`（^TNX）兩源 | 同上；對帳在 `src/compute/risk/reconcile.py`、`src/services/reconcile_service.py` | `macro_snapshot.py::fetch_us10y_block`（FRED fredgraph.csv→FRED API，`TTL_1HOUR`，失敗不快取） | **兩個口徑不同源**（FRED 官方 vs Yahoo ^TNX，註記見 `page_market.py` L214）；FRED 發布有延遲（細節 NOT VERIFIED） | FRED 為 T1、Yahoo 為 T2（CLAUDE §2.1）；UI2 若顯示須標單一來源，**不得平均** | 見 `fetch_us10y_block` 內 Tier 0/1 | `{'_err':…, 'current': None}` | 同 b2 | **未接** |
| **(b4) 利差** | 無統一定義 | — | — | `real_canonical` 文案：「10Y-2Y／10Y-3M／M1B-M2 擇一，待定義」 | — | — | — | — | **blocked（需業務定義）** |
| **(b5) PMI** | `tab_macro_v2`、`macro_engine_inputs` | `macro_engine_inputs.py::build_engine_inputs`（L3，**編排風控**，含 session 讀取，非單純顯示）；`risk_cap_apply.py` 另讀 PMI 歷史 | `macro_cache_reader.py::load_tw_pmi_history`（讀 `data_cache/tw_pmi.parquet`；`update_macro_history.py::fetch_tw_pmi_history`；`data_cache/macro_last_good/tw_pmi.json`） | data.gov.tw dataset/6100 等（CLAUDE §2.1 PMI 多源）；as_of＝資料月（月初 1 日），**非**抓取日 | 月頻：`shared/freshness_policy.py::assess_monthly`／`assess_previous_month`；月後第 1 營業日發布 | `PMI_SOURCE_REGISTRY` 8 源賽跑（fetch 端） | 缺→不計分、標未取得 | 讀檔為主；`load_tw_pmi_history` 無新鮮度判斷 | **未接**；`real_canonical` 另註「PMI 與景氣燈號意義不同，用哪個待定義」 |
| **DXY** | 同 b：`cl_data.intl['美元指數 DXY']` | 同 b | `fetch_yf_close('DX-Y.NYB')` | Yahoo；僅單一源 | 同 b | 無 | 同 b | 同 b | **未接** |

## 2. UI2 合法接線邊界（已讀 `tests/test_ui2_guards.py`）
- L5（`src/ui2/**`）只准 import `src.services.ui2`（`test_g4b_l5_only_reads_services_ui2`）；禁 `src.data`/`src.compute`/`src.ui`/`app`（G4）；G9 禁 producer、`session_state` 受限。
- 純 VM 層（G2）只准 `shared`、`src.services.ui2`；**唯一可做 I/O 的是 `src/services/ui2/real_feed.py`**（G2F）：import 為**精確白名單** `G2F_IMPORT_ALLOWLIST`（現僅 `get_twii_trend_view`、`get_macro_regime`、`real_canonical` 具名符號）；禁 `pandas/datetime/getattr/os/…`、禁 `register_/apply_/save_/…` 前綴、禁 `refresh_macro_now` 等 producer。
- 因此：**新增任何來源＝(1) 白名單具名加入、(2) 同步 `docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md`（我只見引用，未讀）、(3) 讓 G2F teeth 測試仍紅綠正確**。feed 不得 import pandas ⇒ 若 L3 回 pandas Series 就**不合格**，L3 必須回 tuple/list/dataclass（`TwiiTrendView` 範式）。
- (a) 完全合法：加大 `get_twii_trend_view(n)` 的 n（或另開 `TWII_CHART_DAYS`）＋ `TwiiFact` 擴欄＋ VM chart contract；**不需新 L3、不需改 L1**。
- (b) 無合法既有路徑：`intl_series` 讀 session（G9/G2F 禁）；`fetch_*_block`/`fetch_yf_close` 在 L1（feed 不得 import）；`macro_engine_inputs`/`dividend_station_service.fetch_vix` 會連網或讀 session，且屬風控編排/純量。

## 3. 方案比較
| 方案 | (a) 台股歷史圖 | (b) 國際趨勢 |
|---|---|---|
| **A 重用 canonical L3** | **適用**：`get_twii_trend_view(n)` 已含 xs/close/as_of/is_stale/upstream_state；風險最低、最快、token 最省。限制：僅收盤線，無 MA 曲線/量 | **不適用**：沒有不依賴 session 的 L3 |
| **B 薄唯讀 adapter（新 `src/services/…`）** | 僅在要畫量/OHLC 時需要（把 NaN/全0 隱藏邏輯放 L3，仿 `macro_v2_service.get_twii_ohlc` 但帶 attrs） | **可行但非薄**：需包 `fetch_yf_close`（有網路、冷卻、TTL）＋補 as_of/staleness/PIT 規則；屬「新增 I/O 取數入口」，須 QA 與 Gate；VIX 還要處理進行中棒（對應 DEC-070 語意，屬 High Gate） |
| **C 新來源/改公式** | 不需要 | 例如 cron 落 `data_cache/intl.parquet`：新增資料契約、cron、schema，成本最高；現階段不建議 |
| 風險／速度／token | A 低/快/低；B 中/中/中 | B 中高/慢/中高；C 高/最慢/高 |

## 4. 建議
1. **(a) 走 A**：先做「歷史收盤線」的 feed 擴充（窗口天數由呈現決策決定、需 User Visual Gate 確認天數/週期），顯示 as_of＋stale＋upstream_state；**不畫量、不畫 MA 曲線**（MA 曲線與趨勢評分另走 Gate）。量欄若日後要畫，走 B，規則＝NaN≠0、整欄全空/全 0 隱藏，且須在 L3 而非 View。
2. **(b) 不要在 UI2 直接讀 session，也不要立即做 B/C**。先做一份純研究：決定顯示哪一組、哪個口徑（FRED 或 ^TNX、DXY 唯一 Yahoo）、是否需要序列或只要最新值；之後若客戶要，優先 B 的**最小子集：單一 `fetch_yf_close`＋ as_of/stale，且只讀、不寫 session、失敗不連擊**。利差與 PMI（景氣燈號 vs PMI）卡在**業務定義**，先維持 `not_provided`。
3. 維持現有卡的 `not_provided`，不用 0/中性/安全補洞。

## 5. 給 UI 設計的資料狀態（View 需能表達）
- 台股線：OK（有 as_of）／Stale（`is_stale=True`＋原因＋age_days）／Undetermined（`is_stale=None`，⬜）／上游三態（無新資料／抓取失敗／未能判定，文案已有 `upstream_state_text`）／Missing（讀不到，灰）／Unavailable（例外，紅）。
- 圖本身另需：資料不足短窗（`n_available` vs 實際點數）、日期為「交易日列」非日曆日（x 軸不要假設連續）。
- 國際指標：每個系列獨立 as_of（各自末日不同，美股 vs 台股日期錯位須逐項標示）、口徑標示（FRED vs Yahoo）、`absent/empty/ok`、「尚未開放（capability）」與「讀不到（data）」兩軸分開。
- 成交量：若不畫須在 spec 說明「量欄不納入」，不要顯示 0。

## 6. NOT VERIFIED
- 部署端 cron 是否在跑、`data_cache` 在 Streamlit Cloud 是否與 repo 快照相同；Yahoo 今日是否可抓（沙箱不可連）。
- `shared/staleness.py` 日頻過期天數的實際數值（僅引用機制）；`FreshnessVerdict` 對日頻/國際序列是否適用。
- `fetch_yf_close` 是否包含盤中棒、`^TNX`/`DX-Y.NYB` 在非美股交易日的末日行為（僅讀 docstring）。
- `fetch_vix_block` 的 yfinance 路徑在 Cloud 是否實際走 proxy（從程式看是直呼 `yfinance.download`）。
- `docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` 內容、Visual/Wireframe Gate 現況、PROJECT_STATE 之外的 DEC-070 後續。
- `macro_fetch_orchestrator`/`refresh_macro_service` 的完整 session 寫入清單（僅引用已見段落）。
- 未跑任何 pytest；上述守衛判讀來自讀測試原始碼，非執行結果。

---

## 2026-11-09 QA 補正（附註；原研究內容不改）

> 本節為 append-only 附註；上文任何一行均未改動，原證據保留。不升格任何項目為 approved。以下均已對 origin/main 原碼／文件 grep 核對。

1. **路徑與行號**：上文 (b2) 列的「PROJECT_STATE.md L67」應為 `docs/PROJECT_STATE.md` 第 67 行（已驗證該行仍含「VIX 只用判斷時點已完成收盤、不造成 look-ahead 的資料」）。補充：該句是 DEC-070 的客戶裁示，**出現在 Risk Cap 段落的一句話內**，屬**僅語意**裁示（Risk Cap 輸入時點語意），不是顯示路徑的實作規格，也不是 UI 顯示授權。
2. **`page_market.py` 呼叫關係精確說法**：上文 (b) 列「`page_market.py` 約 L560/L727」。實測 L727 為 `blocks.render_chart_b(_session, source_note=FRAME_SOURCE_NOTE["intl"], where_label=_intl_raw_label)`；`intl_series` 定義於 `src/ui/views/_market_blocks.py`（約 L772），由 `render_chart_b`（`_market_blocks.py` 約 L1296，內部於約 L1300 呼叫 `intl_series(session)`）間接取用，`page_market.py` 並未以 `intl_series` 之名直接呼叫。L560 為 `_render_x6` 內的 `_render_frames_block(session, "intl", gate_key=SS_GATE_INTL_CHART, …)`（已驗證）；該函式是否再經 `intl_series` 取數，本次未追，**NOT VERIFIED**。故「約 L560/L727」讀作兩個進入點（frames 區塊與 chart B），皆非 `intl_series` 的直接 call site。
