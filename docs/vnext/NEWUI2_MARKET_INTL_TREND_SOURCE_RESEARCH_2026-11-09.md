# 國際趨勢｜UI2 唯讀來源研究（2026-11-09）
> **研究候選，非授權、非投資判斷。** 基準 main `ca5fdc9`（唯讀 `git show/grep`，未跑網路、未改 repo）。
> 證據等級：〔事實〕＝讀原碼；〔推論〕＝由事實推得；**NOT VERIFIED**＝未查／沙箱無法驗（含任何 Yahoo／FRED 實際回應、盤中行為）。
> 前提：`session_state['cl_data']['intl']` 不得作為來源（G9/G2F 禁，見 `NEWUI2_MARKET_READONLY_CONTRACT_AUDIT_2026-11-09.md` 列 b）。

## 0. 結論先行
- **沒有任何一項達 READY**：repo 內不存在「唯讀、不連網、不碰 session、帶 as_of 與 is_stale」的國際指標 L3 服務〔事實：`src/services/` 僅 `macro_v2_service.get_chart_series/get_twii_ohlc` 讀本地 parquet，只含 TWII 與融資；`data_cache/` 無 VIX／US10Y／DXY／^DJI／^IXIC／^SOX 任何落地檔〕。
- 現有可重用最小單位是 L1 `macro_core.fetch_yf_close`（有網路、TTL 3600s、失敗冷卻、`attrs` 含 source/fetched_at）；UI2 不得直接 import L1，故任何路徑都需 adapter（Gate 文件方案 B）。
- 三項只有客戶能定：US10Y 口徑、VIX 已收盤規則的實作方式、利差定義（見 §4）。

## 1. Evidence Matrix
| 指標 | 現有取數（file::symbol） | 來源／Tier／endpoint | 日期語意 | 已收盤／盤中處理 | 本地落地／離線讀取 | 新鮮度 helper | 備援鏈 | 缺值 | 副作用 | 既有 L3 帶 as_of/is_stale？ | 分類 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| VIX | `macro_snapshot.py::fetch_vix_block`（yfinance `^VIX` 3mo 1d，`_cache_success_only(TTL_1HOUR)`）；`macro_core.py::fetch_yf_close('^VIX')`（`dividend_station_service._latest_vix_close` 用，回純量）；`macro_core` 另有 `fetch_macro_compass` 含 vix series | Yahoo／T2；FRED `VIXCLS` 僅出現在 `scripts/analyze_ring1_gate.py` 註解，**非**取數備援 | `date`＝K 棒日期標籤（`_vd` 切成 10 碼，丟掉時刻時區）；`fetched_at` 另存、經 `dated_inputs.extract_vix`→`DatedValue` 被丟棄〔事實，PROJECT_STATE §10.1〕 | **`fetch_vix_block` 未呼叫 `drop_in_progress_bar`**；該函式只在 `macro_cache_reader.py::fetch_lead_market_changes`（僅 LEAD_MARKETS：^GSPC/^IXIC/^DJI/^SOX/ES=F/NQ=F，不含 ^VIX）使用。DEC-070 的 VIX 規則**語意已裁示、程式未實作**（BACKLOG `VN1-PG-VIX-ASOF`） | **無** | `shared/freshness_policy.py::assess_daily(calendar_kind="weekday")`（平日計、不扣美國假日）；日期標籤法分不出暫定 bar（研究：2026-10-22 run 39755679219 於 05:29 EDT 已得當日 bar 18.4） | 無 | 末筆非有限／≤0／>`VIX_FETCH_MAX`→失敗；<3 筆→`not enough data` | 連網＋Streamlit cache；不寫 session（寫 session 的是上層 refresh） | 無（`dated_inputs`／`macro_engine_inputs` 是風控編排，讀 session） | **NEEDS-ADAPTER ＋ NEEDS-SOURCE-DECISION（已收盤規則實作）** |
| US10Y（FRED） | `macro_snapshot.py::fetch_us10y_block`（fredgraph.csv `id=DGS10`，無 key，`attempts=1`，TTL_1HOUR 成功才快取）；`macro_core.py::fetch_fred('DGS10', key)` | FRED／T1；`fredgraph.csv` 或 API | `date`＝observation_date（FRED 日頻，U.S. 市場日；當日值通常次日才出，**NOT VERIFIED**）；`fetched_at`＝UTC ISO | 不適用（官方日值）；休市日無值，末列＝最後有值日 | 無 parquet；`macro_last_good` 僅 `tw_pmi.json` | `assess_daily(weekday)` 可用；`shared/staleness.py` 日頻門檻值 **NOT VERIFIED** | 僅 fredgraph 一路（Tier1 API 在 docstring 但函式內只見一路，**NOT VERIFIED 是否尚有**） | 失敗→`{'us10y':{'_err':…,'current':None}}` | 連網；無 session 寫入 | 無單點唯讀 L3 | **NEEDS-ADAPTER ＋ NEEDS-SOURCE-DECISION（口徑）** |
| US10Y／^TNX | `macro_core.py::fetch_yf_close('^TNX')`；舊戰情 `INTL_MAP`（`daily_checklist.py`）經 `daily_data_fetchers.fetch_single`；`risk_radar.py` 以 ^TNX 對帳 | Yahoo／T2（`query1` Chart API，經 NAS proxy）；`data_registry.py` 有登錄 | 序列索引＝K 棒日（tz 處理 **NOT VERIFIED**）；`attrs['fetched_at']` | 不剔除進行中棒（`fetch_yf_close` 無此邏輯）；非美股交易日末日行為 **NOT VERIFIED** | 無 | 同上 | 無（`fetch_single` 僅對 DXY 有備援） | 空 Series | 連網；TTL 3600s＋失敗冷卻 | 無 | **NEEDS-ADAPTER ＋ NEEDS-SOURCE-DECISION** |
| 10Y-2Y／10Y-3M 利差 | **repo 無取數**：全 src 只有 `tab_edu.py` 教學文字提及 DGS2／DGS3MO；`macro_core.recession_probability(spread_10y3m)` 只收參數；`real_canonical._not_provided("spread")` | （FRED 有相關序列，**NOT VERIFIED**，且「新增取數」＝新資料契約，未授權） | — | — | 無 | — | — | — | — | 無 | **UNDEFINED**（業務定義＋取數皆無） |
| DXY | `macro_core.py::fetch_yf_close('DX-Y.NYB')`（單一源）；舊戰情 `daily_data_fetchers.py::fetch_single` 備援 `DX-Y.NYB→DX=F→UUP` | Yahoo／T2 | 同 ^TNX | 同 ^TNX | 無 | 同上 | **兩條路徑口徑不同**：`fetch_yf_close` 無備援；`fetch_single` 會落到 **UUP（ETF 約 27 美元，尺度不同）**，`macro_buckets.py`／`macro_helpers.py` 註解已警示須範圍檢查〔事實〕 | 空 Series／None | 連網；pkl 30 分＋cache 1h | 無 | **NEEDS-ADAPTER**（須固定走 `fetch_yf_close`，禁用 UUP 備援；可對齊 `[70,130]` 合理範圍，CLAUDE §3.2） |
| ^DJI／^IXIC／^SOX | `macro_core.py::fetch_yf_close`；`macro_cache_reader.py::fetch_lead_market_changes`（回 `{symbol: pct|None}`）；`INTL_MAP` | Yahoo／T2 | 美股 EOD＝美東交易日；對台股是前一個美股日（日期錯位須逐項標示） | `fetch_lead_market_changes` 有 `drop_in_progress_bar`（UTC hour<21 且最後棒＝今日才丟；`US_SESSION_CLOSE_UTC_HOUR=21` 取冬令，夏令收盤 20:00 UTC 時 20–21 點會保守誤丟已收盤棒〔推論〕）＋`LEAD_QUOTE_MAX_AGE_DAYS=5` 過舊判未取得；但只回**漲跌幅**、無水位、無 as_of、用 `print` 記 log、無 dict 帶日期 | 無 | 僅 5 日年齡判斷；`assess_daily(weekday)` 可補 | 無 | None（不以 0 代替） | 連網；`print` | 無 | **NEEDS-ADAPTER**（可重用 `drop_in_progress_bar`，但需新增「水位＋日期」輸出） |
| TW PMI | `macro_cache_reader.py::load_tw_pmi_history`（讀 `data_cache/tw_pmi.parquet`，缺檔→None＋log，**不連網、不判新鮮度**）；`macro_snapshot.py::fetch_tw_pmi_block`／`macro_core.py::fetch_tw_pmi`（8 源賽跑，連網）；`data_cache/macro_last_good/tw_pmi.json`（cron 寫、runtime 只讀，`macro_core._macro_durable_save`） | data.gov.tw／CIER 等 T1–T3（`PMI_SOURCE_REGISTRY`） | 資料月（月初 1 日），**非**抓取日；月後約第 1 營業日發布（CLAUDE §2.3） | 不適用（月頻） | **有**：parquet＋last_good；`compute_cache_staleness(dataset)` 可回 `{as_of,is_stale,reason}`（`tw_pmi` 是否登錄於 `CACHE_DATASET_CADENCE` **NOT VERIFIED**） | `freshness_policy.assess_monthly(data_month, lag_key)` 為正式規則 | 8 源（fetch 端）→ durable last_good | 缺→未取得，不計分 | 讀檔無副作用 | **無 L3**（L3 `macro_engine_inputs` 屬風控編排且讀 session，不可用） | **NEEDS-ADAPTER**（最接近 READY：薄 adapter 讀 parquet＋`compute_cache_staleness`／`assess_monthly`，免網路）＋業務定義待定（PMI vs 景氣燈號） |
| US PMI（ISM） | `macro_core.py::fetch_ism_pmi`（FRED NAPM/ISPMANPMI 需 API key→DBnomics→ISM 官網…，5 段備援，連網，`max_age_days=90`） | T1–T3 混合 | 資料月；ISM 次月首營業日發布（**NOT VERIFIED**） | 不適用 | 無落地檔 | `assess_monthly`（需 `lag_key`，ISM 是否已登錄 **NOT VERIFIED**） | 5 段 | `{'_err_pmi':…}` | 連網 | 無 | **NEEDS-SOURCE-DECISION**；⚠️ session 鍵 `ism_pmi` 實際是**台灣 PMI（CIER）**（DEC-075，`macro_v2_service._EDU_KEY`），**不可**把它當 US PMI |

## 2. 重點觀察
1. **同概念不同口徑**：US10Y 有 FRED DGS10（T1，日頻官方值，無盤中問題）與 Yahoo ^TNX（T2，供國際趨勢 `INTL_MAP`）。CLAUDE §2.1 規定衝突時上層贏、**禁止平均**；`src/compute/risk/reconcile.py` 已有雙源對帳與**刻度自動偵測**（v19.177；CLAUDE §4.1 的「×10」為舊說，現行是否仍 ×10 **NOT VERIFIED**，故任何 adapter 不得寫死 ÷10）。
2. **DEC-070 只約束 Risk Cap**（`PROJECT_STATE` §10.1）：國際趨勢顯示並不自動受其約束，但 `fetch_vix_block` 同樣取「最後一根」，顯示路徑可能出現盤中暫定值（NOT VERIFIED 實際出現率）。總管候選實作＝「取美東日期早於 D 的最後一根」，**不是客戶裁示**；替代＝美東牆鐘＋收盤 cutoff（Cboe 16:15 ET 收盤為外部摘要級、未讀原文）。
3. **日曆缺口**：repo 有台股日曆（`shared/trading_days.py`、`trading_calendar_service`），**無美股日曆**〔事實，PROJECT_STATE §10.1〕；`assess_daily(calendar_kind="weekday")` 以平日計、不扣美國假日，偏嚴不會假新鮮。
4. **時區**：Yahoo 日線日期標籤為交易所當地日；台北顯示需註明「美股前一日」。`fetch_vix_block` 把時刻切掉，無法事後補判（需 adapter 保留）。
5. **離線讀取能力現況**：僅 TW PMI（parquet＋last_good）與 TWII／融資。VIX／US10Y／DXY／指數無任何 last-known-good，沙箱／離線一律「無法判定」；若要落地＝新 cron＋schema＝方案 C，**未授權**。
6. **side effect**：全部候選 fetcher 皆連網；adapter 若只在使用者按鈕後呼叫、不寫 session、失敗沿用 `_FAIL_COOLDOWN_SEC` 退避（值 NOT VERIFIED），可符合 CLAUDE §1.A-3。

## 3. 路徑比較（對應 Gate 文件 A/B/C；僅研究）
| 路徑 | 說明 | 適用指標 | 是否需客戶 Gate |
|---|---|---|---|
| A 直接重用 | 無符合者 | — | — |
| B 薄唯讀 adapter（`src/services/…`，包 `fetch_yf_close`／讀 parquet） | 補 as_of／fetched_at／stale／absent·empty·ok 三態、不寫 session | DXY、指數、^TNX、TW PMI（免網路）、VIX（含已收盤規則） | VIX 規則與 US10Y 口徑須先裁示；新增 I/O 入口須 QA |
| C 新來源／cron 落地 | 例如 `data_cache/intl.parquet`、改用 FRED VIXCLS 作 VIX 收盤備援 | 全部 | **未授權**；僅標註為「not authorized」候選 |

## 4. 只有客戶能決定的事項
**D1｜US10Y 口徑**
| 選項 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| a. 只顯示 FRED DGS10（T1） | 官方、無盤中問題、與 Risk Cap／`macro_info['us10y']` 同源 | 日期落後約 1 日（NOT VERIFIED）；無 FRED 時需無 key 的 fredgraph 單路 | 與舊戰情國際趨勢的 ^TNX 數字可能差異，需文案說明 |
| b. 只顯示 Yahoo ^TNX（T2） | 與舊 intl 同源、可畫短序列 | T2、刻度需自動偵測、無備援 | 與風控用值不同口徑，易被誤認同一數 |
| c. 主 FRED、^TNX 僅對帳徽章 | 對齊 §2.1 層級與既有 `reconcile` | 兩次取數、畫面更複雜 | 差距過大時需決定顯示規則 |
AI 推薦：**a（單一口徑 FRED），明標來源與資料日；^TNX 不上 UI2 首屏**。理由：禁止平均、與 Risk Cap 一致、最小新增面。

**D2｜VIX 已收盤規則（DEC-070 語意）如何實作於顯示**
| 選項 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| a. 取美東日期早於台股日 D 的最後一根 | 與 DEC-070 語意直接對應、無需牆鐘 | 需 D 的定義與美東日期（時刻資訊現被丟） | 夏令切換日、美國假日需測；最新值顯得落後 |
| b. 美東牆鐘＋收盤 cutoff（沿用 `drop_in_progress_bar` 概念） | 可顯示當日已收盤值 | cutoff 時刻（Cboe 16:15 ET）待官方驗證；現碼為保守 21:00 UTC | 夏令誤丟已收盤棒或標籤錯 |
| c. 暫不顯示 VIX（維持 `not_provided`） | 零風險 | 市場頁缺關鍵指標 | 無 |
AI 推薦：**c 先行，待 `VN1-PG-VIX-ASOF` 實作並驗證後再採 a**（與 Risk Cap 共用同一規則，避免兩套 VIX 口徑）。

**D3｜利差定義**
| 選項 | 優點 | 缺點 | 風險 |
|---|---|---|---|
| a. 10Y-2Y | 通用 | repo 無 DGS2 取數 | 需新增取數＝新資料契約（未授權） |
| b. 10Y-3M | `recession_probability` 已以此為輸入 | 同上無取數 | 同上 |
| c. 維持空槽 | 無新增 | 版面一格空 | 無 |
AI 推薦：**c**，待客戶指定定義與是否授權新增取數。（M1B-M2 為台灣貨幣指標，與「利差」是不同概念，建議從卡槽命名中分離——僅提案。）

**D4（較小）｜PMI**：台灣 PMI 與景氣燈號擇一，或兩者並列；若選 TW PMI，可走 B 免網路讀 parquet。AI 推薦：先上 TW PMI（有落地檔與正式月頻規則），US PMI 不上。

## 5. 無法判定（NOT VERIFIED 清單）
Yahoo／FRED 實際回應與盤中行為；`fetch_yf_close` 索引時區；^TNX 現行刻度；`_FAIL_COOLDOWN_SEC` 與 `shared/staleness.py` 日頻門檻實值；`tw_pmi`／ISM 是否登錄於 `CACHE_DATASET_CADENCE`／`MACRO_PUBLICATION_LAG_DAYS`；`fetch_us10y_block` 是否另有 API 路徑；FRED 當日值發布時刻；全 repo 是否另有未被 grep 到的利差取數（僅 grep `DGS2|T10Y|yield_curve` 為 0 命中，單組搜尋）。
> 本檔未建議變更 G2F allowlist、OAuth、Sheet、Risk Cap、OneBrain、公式；FRED VIXCLS 備援與新 cron 落地僅為「not authorized」候選。
