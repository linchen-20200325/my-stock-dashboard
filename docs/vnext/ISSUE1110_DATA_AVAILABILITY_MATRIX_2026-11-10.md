# Issue #1110｜Secrets／API 唯讀驗證：舊 UI 資料來源可用性與 New UI2 接線缺口（2026-11-10）
> **研究證據紀錄，非授權、非新決策、非投資判斷。** Issue：https://github.com/linchen-20200325/my-stock-dashboard/issues/1110 。基準 main `db04dac`（唯讀 `git show/grep`＋讀已 commit 的 `data_cache/`，未跑任何外部網路請求、未讀任何憑證值、未改 code／資料／測試）。
> 證據等級：〔事實〕＝讀原碼或已 commit 資料；〔推論〕＝由事實推得；**NOT VERIFIED**＝沙箱無法驗（含 Streamlit Cloud 線上實況與任何 API 實際回應）。
> ⛔ 本檔只出現 Secret／環境變數的**名稱**，不含任何值、尾碼、片段、長度或帶憑證的網址。

## 0. 結論先行
1. **客戶在 Streamlit Cloud 新增 Secrets，不會讓 New UI2 多出任何資料。** UI2 的真實資料 feed 只讀兩件事：本機已追蹤的台股 parquet、以及 session／本機位階狀態檔；不經手 VIX／US10Y／DXY／PMI／Gemini／Google 的任何 Secret（§2）。
2. **「Key 存在」「API 可用」「資料語意有效」「UI2 已接線」是四層，本檔逐層分開**；沙箱只能看到第四層與部分第三層，前兩層在 Cloud 上全部 **NOT VERIFIED**（§1、§9）。
3. **舊 UI 抓得到 ≠ UI2 可採用**：舊服務多半讀 `session_state`、回 DataFrame 無 `as_of`，且 UI2 的 G2F 守衛禁止 import `src.data`（§7）。
4. **資安發現（需客戶授權才可修，本檔不修）**：舊 UI 診斷面板與側欄會顯示 Secret 的前後 4 字元＋長度，並列出全部 Secret 名；側欄在特定組合下可能印出整段 `PROXY_URL`（§5）。**在修好前，不要截圖那兩處。**
5. **最快且安全的路（AI 推薦）**：VIX／DXY／利差／PMI 現階段維持「未提供」（方案 C）；US10Y 待客戶選口徑後，以單一 FRED DGS10 最小唯讀 adapter（方案 B）最快（§8）。需客戶決定 D1–D6（§9）。

## 1. 範圍與方法（四層分離）
| 層 | 問題 | 本檔能回答？ |
|---|---|---|
| L-1 `credential_loaded` | Cloud 是否讀到該 Secret（非空） | 否——**NOT VERIFIED**。客戶說「已加入」只證明做過設定，不證明格式、載入、認證成功 |
| L-2 `network_reachable`＋`auth_ok` | 外連通不通、認證過不過 | 否——**NOT VERIFIED**（沙箱不是 Cloud 執行環境，也不得連網） |
| L-3 `data_semantics_valid`＋`as_of` | 值是否為預期口徑、資料日、是否已完成觀測 | 僅限「已 commit 的 `data_cache/` 與原碼語意」；線上值 NOT VERIFIED |
| L-4 UI2 contract | UI2 有沒有合法路徑可吃這份資料 | 是（讀原碼＋守衛） |
- 方法：靜態讀 main 的 code 與已 commit 資料；沙箱僅做 `import` 實測（確認 UI2 匯入鏈會載入 `src.config.config`），無網路、無憑證讀取。
- 與 #1107（UI2 Cloud 日 K 驗收，仍 PARTIAL）、#1108／PR #1109（市場頁順序，已合併）去重：本檔不碰它們的範圍，也不關閉任何一項。

## 2. UI2 本身用不到任何 Secret〔事實〕
- 入口 `app_ui2.py` → `src.ui2.shell`。`src/ui2`、`src/services/ui2`、`app_ui2.py` 內以 `st.secrets`／`os.environ`／`getenv`／`from src.data` 全文 grep：**0 個實際讀取**（命中的 `proxy`／`oauth`／`gsheet` 字樣全是「⛔ 禁止」類註解或固定文案）。
- `src/services/ui2/real_feed.py` 僅呼叫兩個白名單入口：
  1. `get_twii_trend_view`：卡片 `days=1`；主圖 `days=20, with_ohlc=True`——讀 git 追蹤的 `data_cache/twii_ohlcv.parquet`，**不連網、不快取、不碰 session**。
  2. `get_macro_regime(strict=True, require_valid_risk_cap=True)`：讀 `session_state['warroom_summary']`＋本機 `macro_state.json`／`risk_cap_state.json`。這兩個 JSON 在 `.gitignore`、`git ls-files` 無此二檔 ⇒ **全新 Cloud 部署不會有**；不呼叫 FRED／FinMind／Gemini。
- 匯入鏈會載入 `src.config.config`（沙箱實測 `config loaded: True`），其模組載入時讀一次 `st.secrets` 的 `FINMIND_TOKEN`；**UI2 不使用該結果**。
- OneBrain 欄位在 `real_canonical` 一律硬編 `not_provided`（無 Gemini 路徑）。我的（帳戶）頁為 FAKE／`not_provided`，`account=None`；登入與否不影響 UI2。
- ⇒ 能改變 UI2 輸出的只有：①重新整理並 commit 的追蹤 parquet；②本機位階狀態檔。

## 3. Secret 名稱對照表（僅名稱；Runtime 最多能推論「非空存在」，永遠無法推論「有效」）
| 名稱 | 載入處（file::symbol） | 缺少時的行為 | UI2 今日可用？ |
|---|---|---|---|
| `FINMIND_TOKEN` | `src/config/config.py`（模組載入快照＋`get_finmind_token()`）；`app.py::_get_secret` | 靜默回空字串；舊 UI 顯示「未設定」 | 否 |
| `FRED_API_KEY` | 就地讀取：`tab_macro`、`section_long_term`、`health_inspector`、`tab_edu`、`macro_refresh_service`（env 優先）——此清單**非窮舉**；`macro_trio_orchestrator`、`etf_scoring_service`、`macro_snapshot`、`data_registry` 亦出現該名稱（是否各自讀取該 Secret：NOT VERIFIED；僅 `etf_scoring_service` 在檢視中可見直接讀環境變數） | FRED 路徑被略過 | 否 |
| `GEMINI_API_KEY`、`GEMINI_API_KEY_2`～`_6` | `src/services/app_ai_service.py::gemini_keys` | 回警告字串 | 否 |
| `PROXY_URL`（亦認 `NAS_PROXY_URL`、`[proxy]` 表，再退 env） | `proxy_helper.get_proxy_config` | 無 proxy ⇒ 直連 | 否 |
| `PROXY_HOST`／`PROXY_PORT`（`PROXY_USER`／`PROXY_PASS`） | **不被 `proxy_helper` 讀**；`tw_stock_data_fetcher._load_proxy_config` 當第二選項讀；`app.py` 側欄與診斷面板顯示 | 見左 | 否 |
| `NAS_BASE_URL`（`NAS_RELAY_URL`）／`NAS_API_KEY` | `proxy_helper.get_nas_relay`（fetch_url 最後手段） | 無中繼站 | 否 |
| `[google_oauth]` 的 `client_id`／`client_secret`／`redirect_uri`（選配 `portfolio_sheet_id`） | OAuth 與 `gsheet_portfolio` | 登入不可用、Sheet fail-closed（`LoginRequiredError`） | 否 |
| `[gcp_service_account]` | 僅 cron 經 env（SEC-3） | — | 否 |

## 4. PROXY_URL 在 Streamlit Cloud 的行為〔事實；後果評估為推論〕
- `fetch_url` 順序：NAS Squid proxy（預設 3 次、逾時 20 秒、重試間 sleep 2 秒，單次呼叫最壞約 64 秒）→ 直連（**僅** `ProxyError` 或 HTTP 403 才降級）→ NAS 中繼 → `None`。
- **Timeout 不會降級直連**；HTTP 407 立即回 `None`；失敗不入 URL 快取（只快取 200）；`proxy_helper` 本身無熔斷器（全檔 grep 熔斷／cooldown 0 命中）；fetcher 層另有失敗冷卻（`FAIL_COOLDOWN_SEC=180`，例如 `macro_core` 的 Yahoo 收盤價取數層，`macro_alert` 沿用），但不在 `fetch_url` 內，也不涵蓋 `fetch_us10y_block` 這類直接呼叫 `fetch_url` 的路徑。
- 有設 proxy 時 `fetch_url` 以 `verify=False` 發送（`_verify = not bool(_proxy)`）。
- 連 FRED 的 `fetch_us10y_block` 也經 `fetch_url`，所以 `PROXY_URL` 若指向不通的家用 NAS，這些舊路徑都會先吃 proxy 的逾時〔**INFERENCE，NOT VERIFIED**：`fetch_url` 預設最壞約 64 秒；`fetch_us10y_block` 為 `attempts=1`／`timeout=10`（約 10 秒，另加選配的 NAS 中繼）；PMI 的 data.gov.tw 路徑為 `attempts=2`／`timeout=25`；各路徑實際延遲 NOT VERIFIED〕。
- 診斷面板自身也警告「Timeout 不降級」並建議暫刪 `PROXY_URL` 驗證。**建議**：先用證據比較「直連 vs proxy」（Issue 第 2 項），**不要自動移除** `PROXY_URL`。

## 5. ⚠ 資安發現：舊 UI 會顯示部分金鑰〔事實；是否外洩取決於是否被截圖／轉貼〕
1. `src/ui/pages/api_diagnostic.py`：
   - `_mask()` 顯示**前 4＋後 4 字元＋長度**，對象 `GEMINI_API_KEY`／`FINMIND_TOKEN`／`FRED_API_KEY`（含 env 同步欄），`PROXY_HOST` 前後 4；`PROXY_URL` 以 `http…`＋後 4＋長度顯示（Proxy 警告區）。
   - 另以 caption 列出 `st.secrets` **全部頂層 key 名**。
   - 探測請求一律 `verify=False` 且帶憑證（FinMind／Gemini 走 header；FRED 依其 API 限制走 query string）；結果顯示 body 前 80 字。
   - 檔案本身**沒有**驗證或按鈕閘門；呼叫端 `app.py`（🔎 資料診斷 → 收合的「🔧 進階診斷」）只有一個「載入進階診斷」checkbox，**不是驗證**。
2. `app.py` 側欄：`_px_host` 在 `PROXY_HOST` 為空時退而取**整段 `PROXY_URL`**，之後以 `🔒 {host}:{port}` 印出——僅當「`PROXY_HOST` 空且 `PROXY_URL` 有值且 `PROXY_PORT` 非空」時會印出整段 URL（URL 可能內含帳密）。程式路徑確定存在；**實際是否發生 NOT VERIFIED**。
- 分類：對舊診斷頁／側欄任何截圖皆有「部分機敏資訊外洩風險」。測試現況：`tests/test_sec3_scrub_legacy_pages.py` 單次 grep 未見釘住 `_mask` 格式；`tests/test_render_smoke.py::test_render_api_diagnostic` 只驗不拋例外——**是否有其他測試釘住遮罩格式仍 NOT VERIFIED**。
- **本檔不修。** 建議後續（動到舊 UI，**須客戶授權**，見 D6）：最小 PR——只顯示「名稱＋來源＋✅／❌」（限白名單）、proxy 只顯示「已設定／未設定」、探測結果只顯示通過／失敗＋HTTP 狀態、不顯示 body 片段；動手前先查 `test_sec3_scrub_legacy_pages.py` 的期望。
- **在此之前**：不要截圖這兩處；向 Cloud 管理員要求的證據僅限「布林／HTTP 狀態」表（§10）。

## 6. 資料可用性矩陣
> 「Key 狀態」欄凡無 commit 內 `fetch_outcome` 證據者一律寫 `NAME only; loaded = NOT VERIFIED`，「API 結果」寫 `NOT VERIFIED`。常數實查：`FAIL_COOLDOWN_SEC=180`、`STALE_DAYS_DAILY=7`。

| 資料名稱 | 舊 UI 來源 | Key 狀態 | API 結果 | 資料日期（committed） | PIT／新鮮度 | New UI2 缺口 | 建議方案 |
|---|---|---|---|---|---|---|---|
| VIX | `macro_snapshot.fetch_vix_block`（yfinance `^VIX`，3 個月日線）；`macro_alert` 也可補抓；無備援鏈 | 不需 Key（Yahoo 免 Key） | NOT VERIFIED | 無落地檔（`data_cache/` 無 VIX） | 「只用已完成收盤」語意已由 DEC-070 裁示、`VN1-PG-VIX-ASOF` **未實作**；`drop_in_progress_bar` 全 repo 僅用於 `fetch_lead_market_changes`（`LEAD_MARKETS`，不含 `^VIX`），**`fetch_vix_block` 未套用** | `real_canonical` 硬編 `not_provided`；無 L3 唯讀服務 | **C**（維持空槽）；待完成收盤規則實作後才考慮 B |
| US10Y | `macro_snapshot.fetch_us10y_block`：FRED 公開 `fredgraph.csv`、系列 `DGS10`、**單一路徑**（docstring 寫的 Tier 1 API 路徑在函式內不存在，`fred_api_key` 參數未被使用）、經 `fetch_url`（吃 proxy）；`macro_alert` 的 `us10y`、舊國際趨勢另用 Yahoo `^TNX` | FRED 路徑不需 Key；`FRED_API_KEY`：NAME only; loaded = NOT VERIFIED（此路徑用不到） | NOT VERIFIED | 無落地檔 | FRED `date`＝觀測日；末列＝最後有值日（當日值何時出 NOT VERIFIED）；`^TNX` 刻度（÷10 與否）現行 NOT VERIFIED | `not_provided`；口徑待客戶（D1） | **B**（僅單一 FRED DGS10＋`source`＋`as_of`，需客戶先選口徑）；未選則 **C** |
| DXY | 顯示路徑：`macro_alert._yf_latest`→`macro_core._fetch_yf_close_base` 單一代號 `DX-Y.NYB`、無備援；**另有**舊戰情 `daily_data_fetchers.fetch_single` 備援鏈 `DX-Y.NYB→DX=F→UUP` | 不需 Key | NOT VERIFIED | 無落地檔 | ⚠ 備援鏈回傳的 DataFrame **不帶 `source`／`is_proxy`**，落到 `UUP`（ETF，約 27 美元）時可能被當成「DXY」；已有緩解：`shared/macro_buckets.py` 對 `dxy` 設合理範圍 `[70,130]`（五桶 `macro_helpers` 的 `_first_sane` 對越界值拒收並記 log；`dxy` 在該路徑只有 Yahoo 美元指數序列這一個候選，故越界結果為 `None`＝灰燈、缺值原因 out_of_range，**不會**改用其他來源；`us10y` 有三個候選才會依序往下試）、`macro_helpers` 註解警示；**顯示卡片路徑是否擋 UUP：NOT VERIFIED** | `not_provided` | **C**；或 **B** 且固定走單一 `DX-Y.NYB`、禁用 UUP、加範圍檢查 |
| 台灣 PMI | `PMI_SOURCE_REGISTRY` 8 源賽跑（連網）；runtime 讀 `data_cache/tw_pmi.parquet`（不連網）＋`macro_last_good/tw_pmi.json` | 多源多為免 Key（來源層級 Key 需求 NOT VERIFIED）；NAME only | `metadata.json` 的 `tw_pmi.fetch_outcome=UNDETERMINED`、`last_error`＝「抓取結果為空」（證據：data.gov.tw 6100 窗口內 0 列）；其餘 NOT VERIFIED | parquet 172 列、末列 **2026-10-01＝62.5**、來源 `data.gov.tw:dataset:6100`、`fetched_at` 2026-11-02；`tw_pmi.json` 同值同日同源，且 `is_proxy: true`（data.gov.tw/6100 路徑在原碼寫死 `is_proxy=True`）；parquet 無 proxy 欄 | `CACHE_DATASET_CADENCE` **未登錄** `tw_pmi` ⇒ `compute_cache_staleness('tw_pmi')` 必回 `is_stale=True`；`MACRO_PUBLICATION_LAG_DAYS` 有 `ism_pmi`（lag 1，註解載明即台灣 PMI），可配 `assess_monthly`；DEC-155：proxy PMI 不得成為正式訊號 | `not_provided`；無 L3 唯讀服務；PMI vs 景氣燈號待客戶（D4） | **C**（預設）；客戶要的話 **B**：唯讀 parquet、標「proxy／抓取未確認」，並先登錄 cadence |
| 利差（10Y-2Y／10Y-3M） | **repo 內無任何取數**（`DGS2`／`DGS3MO` 僅出現在 `tab_edu` 教學文字；單組 grep） | — | — | — | 定義未訂 | `not_provided`（「尚無正式定義」） | **C**（D3） |
| FinMind 法人／融資、TWII | `data_cache/finmind_inst`、`finmind_margin`、`twii_ohlcv` parquet（cron 落地） | `FINMIND_TOKEN`：NAME only; loaded = NOT VERIFIED | `metadata.json` 無 `last_error`（committed 證據），無 `fetch_outcome`；線上 NOT VERIFIED | 末列 **2026-11-09**（inst／margin 4939 列、TWII 4913 列） | 日頻；`STALE_DAYS_DAILY=7` | **TWII 已接線**於 UI2；法人／融資不在本 Issue 範圍 | 不動 |
| M1B／M2 | `data_cache/finmind_m1m2.parquet`（CBC EF15M01） | 不需 Key | `fetch_outcome=NO_NEW_DATA`（證據：窗口內無新月份） | 末列 **2026-09-01**（239 列） | `NO_NEW_DATA` ≠ fresh | 與「利差」是不同概念 | **C**／另案 |
| Gemini／OneBrain | `app_ai_service.gemini_call` | `GEMINI_API_KEY`（及 `_2`～`_6`）：NAME only; loaded = NOT VERIFIED | NOT VERIFIED | — | — | UI2 無任何 Gemini 路徑，OneBrain 硬編 `not_provided` | 否（N） |
| Google Sheet／OAuth | `oauth_state`、`gsheet_portfolio` | `[google_oauth]` 各欄：NAME only; loaded = NOT VERIFIED | NOT VERIFIED | — | fail-closed | UI2 帳戶 FAKE；不接 | 否（N） |

註：DEC-155 文字記載 `finmind_inst`／`finmind_margin` 曾被補 `fetch_outcome=NO_NEW_DATA`，但 main `db04dac` 的 `metadata.json` 只有 `finmind_m1m2` 與 `tw_pmi` 帶 `fetch_outcome`（後續每日資料 PR 已覆寫）；本表以現行 committed 內容為準。

## 7. 為何「舊服務重用」對 UI2 不成立
舊服務多讀 `session_state`、回傳 DataFrame 不帶 `as_of`／`is_stale`，且 UI2 守衛 G2F 禁止 `src.data` import；`session_state['cl_data']['intl']` 不得作為來源（見 `NEWUI2_MARKET_READONLY_CONTRACT_AUDIT_2026-11-09.md`）。細節與逐指標證據見 `NEWUI2_MARKET_INTL_TREND_SOURCE_RESEARCH_2026-11-09.md`。

## 8. 三方案對比（每個缺口項）
| 方案 | 內容 | 正確性 | 速度 | Token／成本 | 結論 |
|---|---|---|---|---|---|
| A 直接重用舊服務 | 讓 UI2 呼叫舊 fetcher／session | 低（無 `as_of`、可能口徑錯、DXY 有 UUP 風險） | 快 | 低 | **不可行**（G2F 禁；session 耦合） |
| B 最小唯讀 adapter | 新 L3 服務，PR-1 風格 fail-closed 契約（`source`＋`as_of`＋三態），不寫 session | 高 | 中（需 PR＋獨立 QA） | 中 | 僅在客戶裁示後 |
| C 維持「未提供」 | 不動 | 最高（不造假） | 立即 | 最低 | 現階段預設 |

排序——正確性：C ≥ B ≫ A；速度：C > A > B；token：C < B < A。
**建議最快且安全**：VIX／DXY／利差／PMI 現在走 **C**；US10Y 在客戶選定 D1 後，單一 FRED DGS10 的 **B** 最快。

## 9. 需客戶決定（商業語言＋AI 推薦）
| 編號 | 題目 | AI 推薦 |
|---|---|---|
| D1 | 美債 10 年期殖利率要顯示哪個口徑？ | 官方 FRED DGS10，並標示資料日；Yahoo 版本不放首屏 |
| D2 | VIX 何時開始顯示？ | 先留空，待「只用已完成收盤」規則實作並驗證後再議 |
| D3 | 「利差」指哪一個（10Y-2Y／10Y-3M），是否授權新增取數？ | 先留空 |
| D4 | 要顯示台灣 PMI 還是景氣燈號？ | 若要 PMI：僅在明確標示「proxy／抓取未確認」下顯示；否則維持留空 |
| D5 | 是否授權為 VIX／US10Y 新增每日落地排程（cron）？ | 不授權，除非客戶需要首屏即時顯示 |
| D6 | 是否授權最小 PR，移除舊診斷頁／側欄的「部分金鑰遮罩顯示」？ | 授權（見 §5） |
以上均**未授權施工**；依 CLAUDE.md §-1，無客戶指派不動工。

## 10. NOT VERIFIED 清單與關閉方式
- Cloud：是否以 `app_ui2.py`、branch main、最新設定重啟；各 Secret 是否載入／有效；FinMind／FRED／Yahoo／Gemini／TWSE 的可達性與認證；線上 `data_as_of`；Yahoo 日線索引時區；`^TNX` 現行刻度；FRED 當日值發布時刻；舊顯示卡片是否擋 UUP；全 repo 是否另有利差取數（僅單組 grep）；是否有測試釘住 `_mask` 格式。
- **關閉方式**：依 Issue 第 5 項，請 Cloud 管理員提供**一張**只含「每項是否成功、HTTP 狀態／資料日」的布林／狀態表；**不含**任何 Key、尾碼、長度、Secrets 截圖。
