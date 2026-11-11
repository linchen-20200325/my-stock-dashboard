# Stage F｜G-F1 方案 A：既有 canonical 市場資料 headless 唯讀契約與缺口驗證（2026-11-11）

- **基準**：main `3cf13a02`；量測日 2026-11-11。
- **授權**：Issue #1132（G-F1 方案 A，客戶裁示轉錄，見 `docs/DECISIONS.md` DEC-161）。
- **驗證程度**：本文事實經**兩位獨立 agent 二次核對**。但兩者仍是 agent 產出，**未經人工複驗**，不是 QA PASS。
- **證據級別**：`FACT`＝讀碼／讀檔直接確認；`INFERENCE`＝由事實推得，未實測；`NOT VERIFIED`＝未驗證或無法在沙箱驗。
- **引用規則**：只寫 `path::symbol`，不寫行號。量測值（列數、日期）會漂移，以量測日為準。
- **非施工授權**：本文只做唯讀契約設計、證據核對與缺口登記。**不是**任何 runtime 接線、新來源、新 fetcher／cron／Secret、或投資語意變更的授權。

---

## §1 契約矩陣：source → producer → consumer → as_of → PIT → authorization

### 1.1 加權指數日 K（TWII）：唯一已有可重用 headless 讀取路徑

| 項目 | 內容 | 級別 |
|---|---|---|
| source | Yahoo Chart `query1…/chart/^TWII`（經 proxy） | FACT |
| producer | `scripts/update_macro_history.py::fetch_twii_ohlcv`；cron `0 9 * * *`（UTC）＝台北 17:00；經 `publish_data_pr.py` 開 `auto/data-macro-history` PR，**不啟用 auto-merge，人工合併** | FACT |
| 落地 | `data_cache/twii_ohlcv.parquet`，4913 列（量測日 2026-11-11）。欄位：`date`(str)／`open`／`high`／`low`／`close`／`volume`(float)／`source`／`fetched_at`。最新 `date`＝2026-11-09 | FACT |
| 資料品質 | `volume==0` 且 `high>low` 的列，寫入前改 NaN。現值：`volume==0` 為 0 列、NaN 為 35 列 | FACT |
| consumer | `src/services/market_twii_view_service.py::get_twii_trend_view`。輸出：`ok`／`xs`／`close`／`n_available`／`as_of`／`is_stale`(True／False／None)／`stale_reason`／`age_days`／`upstream_error`／`upstream_state`／`ohlc_*`。讀本地 parquet，無 session、不快取、無網路 | FACT |
| 缺 metadata | 缺 `attrs.as_of` → `is_stale=None`，不當新鮮 | FACT |
| UI2 接線 | `real_feed` 兩次呼叫 `get_twii_trend_view`：卡片 1 日＋日 K 20 根 | FACT |
| as_of／stale | `compute_cache_staleness` ＋ `STALE_DAYS_DAILY=7` 日曆天。`as_of > today` 視為過期；缺 metadata／缺 `date` 欄／未登記 → 一律 stale | FACT |
| PIT | 日頻；無 `release_date` 欄（風險低：INFERENCE）。Yahoo 歷史值可被事後更動，檔內僅有列級 `fetched_at` | FACT／INFERENCE |
| 收盤後可信時點 | 碼內無明文 | NOT VERIFIED |
| 授權／再散布 | Yahoo 條款是否允許在本專案使用情境再散布 | NOT VERIFIED |

### 1.2 其他 data_cache 檔：可 headless 讀 git 檔，但 UI2 未接

| 資料 | 現況 | 級別 |
|---|---|---|
| `finmind_inst`／`finmind_margin`／`sector_flow` | 皆可 headless 讀 git 檔。已驗 `src/ui`、`src/ui2`、`app.py`、`app_ui2.py`、`src/services/ui2` 對 inst／margin／sector_flow 皆無引用 | FACT |
| `finmind_margin` 單位 | **「元」**。依 v3 §02，單位混用區間須標「資料疑義」 | FACT |
| `finmind_m1m2` | 檔名沿用舊名，實為 CBC EF15M01。末列 2026-09-01；metadata `fetch_outcome=NO_NEW_DATA` | FACT |
| `tw_pmi` | 末列 2026-10-01＝62.5；`fetch_outcome=UNDETERMINED`。不在 `CACHE_DATASET_CADENCE`，故預設 stale | FACT；「預設 stale」為 INFERENCE |
| `sector_flow` | cron `30 9`（UTC） | FACT |
| PIT | 上述五個 parquet **皆無 `release_date` 欄** | FACT |
| 授權／再散布 | 各上游 | NOT VERIFIED |

### 1.3 位階／light／health／曝險：輸入只活在 session

- **輸入鏈**：session `warroom_summary`（`warroom_apply.compute_and_store_warroom_summary` → `calc_traffic_light` → `build_warroom_summary`）→ `macro_state_locker.get_macro_state` → `allocation_service.get_macro_regime`。
- **輸入來源**：`mkt_info`／`jingqi_info`／`cl_data`／`li_latest` 只存在於 session。**無 headless 副本。**（FACT）
- **輸出**：9 鍵 `regime`、`light`、`source`、`trend_regime`、`health`、`defense`、`exposure_limit_pct`、`traffic_light`、`is_loaded`。**無 `as_of`。**（FACT）
- **「無法判定」的保證**：`get_macro_state` 內的 `_wr_no_real_breadth`、`_nowr_no_real_breadth`、結尾 else 回 `UNLOADED_VERDICT`。註解寫「絕不退回 neutral」。守衛測試：`tests/test_dh_regime_nowarroom.py`、`tests/test_dec074_breadth_gate.py`（含 mutant）、`tests/test_macro_state_locker.py`。（FACT）
- **現行 production**（無 warroom、無廣度）：`regime=unknown`、`light=⬜`、`is_loaded=False`、`health=None`。（FACT）
- **曝險 `exposure_limit_pct`**：仍可讀檔（DH-REGIME-NOWARROOM：「不動 Risk Cap」）。但 `macro_state.json`、`risk_cap_state.json` 為 gitignore，7 天過期；寫入者僅 session（`section_news_ai`、`risk_cap_apply.compute_and_lock_risk_cap`）；無檔／過期／格式不合 → `None`，不補 0。`PRODUCTION_WRITE_APPROVED=False`。（FACT）
- **模組副作用**：`allocation_service` 模組層 `import streamlit`，headless 直接 import 有副作用。（FACT）
- **UI2 現況**：`real_feed` 檔頭「Risk Cap 不收，恆⬜無法判定」。（FACT）

### 1.4 UI2 Real 軸現況

- 只呼叫 `get_twii_trend_view` 與 `get_macro_regime(strict=True)`。（FACT）
- VIX／US10Y／DXY ＝ `not_provided`「尚未開放」；利差「尚無正式定義」；PMI「台灣PMI與景氣燈號意義不同，待定義」。（FACT）

### 1.5 廣度

- 廣度旗標：`BREADTH_PROXY_SCORING_ENABLED=False`（`shared/signal_thresholds.py`）。出處 DEC-074 B（客戶 2026-10-23）；DEC-075 D-1(a)：位階一併⬜，**不得靜默 fallback 到另一套規則引擎**。（FACT）
- **復活條件**實掛在上方 `M1B_M2_LEG_ENABLED` 註解下（非旗標註解本身）：
  1. `update_macro_history` 餘額／流量解析修正，並過 sanity gate（m1b>0 且 |gap|<30）；
  2. 重跑 AUC 顯著 >0.55；
  3. 線上路徑能回報 as-of 與是否走代理；
  4. 同批重跑門檻校準。（FACT）
- **目前缺口**：`fetch_adl` 由 `^TWII` 日內漲跌反推（`is_proxy=True`）；`data_cache` 無逐日漲跌家數序列；`tw_macro.fetch_twse_breadth` 只給單日值且非正式口徑（5 日均）。（FACT）
- **「恢復」是否等於「新增來源」須客戶裁示**：走 `fetch_twse_breadth` 逐日落地即新增 fetcher＋cron，本批禁止。（INFERENCE，待裁示）

### 1.6 前進驗證帳本 `data_cache/macro_forward_test/signals.parquet`

- **事實**：47 列（date 2026-08-20～11-03，25 欄）；`effective_regime` bull 22／neutral 18／unknown 6／bear 1；`schema_version` 1:37／2:4／3:6；`date_source=backfill_from_captured_at` 37 列、`live_as_of` 10 列；`captured_at` 晚於 `date` 最多約 2 天。（FACT，量測日 2026-11-11）
- **PIT 缺口**：BACKLOG `NUI2-PIT-1038-BLOCK`、`DATA-FWDTEST-PIT-BACKFILL`（缺逐列來源發布時間、回填列）；#1124～#1126 PIT 仍 NOT VERIFIED。
- **用途**＝前進驗證帳本。**不得充當 live 市場判斷**，理由：歷史凍結且最新列 11-03；37/47 為回填；PIT 被拒；旗標生效前 v1／v2 的 bull／neutral 為舊規則值；授權作 live＝NOT VERIFIED。
- **引用**：`src/ui`、`src/ui2`、`app.py`、`app_ui2.py`、`src/services/ui2` 皆無引用。但**沒有「禁止讀取」測試，僅靠無 caller**（INFERENCE）。

### 1.7 Digest market 段

- `_market_section` 需要 `macro_state['is_loaded']`／`regime`／`light`／`health` ＋ `macro_stamp`（`SourceStamp`）。`get_macro_state` 無 `as_of` → headless 無人供 `macro_stamp`。`tw_trend`／`intl_trend` 在 `build_decision_digest` 寫死 `NOT_DEFINED`。（FACT）
- **若不新增來源，Digest market 段最多只能誠實呈現**：位階／燈號／健康分「未評估或無法判定」＋加權指數最新收盤／as_of／是否 stale（stale 只放 coverage／audit，A2-i）。（INFERENCE）
- 呈現 TWII 趨勢需要 `tw_trend` 定義＝v2／schema Gate（G-F4），未授權。

---

## §2 對前一份研究的二次核對更正

前一份：`docs/vnext/STAGE_F_HEADLESS_INPUT_AND_STALE_SEMANTICS_2026-11-11.md`。**原文件不改，以本段為準。**

- (a) 原稱「`signals.parquet` 引用者為 `macro_forward_test.py`、`macro_fwd_test_store.py`、`macro_refresh_service.py`、`macro_session_patch.py`」**不完全屬實**。production 唯一 import 是 `scripts/update_macro_forward_test.py`；`compute/macro/macro_forward_test.py`、`data/macro/macro_fwd_test_store.py` 是被它呼叫的模組；`macro_refresh_service` 僅註解提到。
- (b) 原稱「無任何 headless 位階」**需修正**：`update_macro_forward_test` cron 確實 headless 產位階（與畫面同一組 L3 函式，bare-mode）。但旗標 False 下輸出 `unknown`，**不等於**存在 headless 有效位階。
- (c) 前份未載：`signals` 的 `date_source` 37 回填／10 live。
- (d) 旗標註解只寫 DEC-074 B；復活條件掛在 `M1B_M2_LEG_ENABLED` 註解下。
- 其餘宣稱經複驗屬實：9 鍵無 `as_of`、gitignore、`PRODUCTION_WRITE_APPROVED`、`allocation_service` 模組層 import streamlit、metadata 現值、parquet 無 `release_date`。

---

## §3 缺口清單

| 項目 | 狀態 | 說明 |
|---|---|---|
| 加權指數日 K ＋ as_of／stale | **具備** | 已有 L3 唯讀 service，UI2 已接 |
| inst／margin／sector_flow／m1m2／pmi 讀檔 | **半具備** | git 檔可讀，但無 L3 唯讀 service、UI2 未接；無 `release_date`；margin 單位「元」；tw_pmi 未登記 cadence |
| 市場位階／light／health | **不具備** | 輸入只在 session；旗標 False |
| 曝險 `exposure_limit_pct` | **不具備**（headless） | 檔為 gitignore、只由 session 寫入 |
| 市場廣度 | **不具備** | 僅 `^TWII` 反推 proxy；無逐日序列 |
| VIX／US10Y／DXY／利差／PMI | **不具備**（UI2） | UI2 顯示「尚未開放」／「尚無正式定義」 |
| PIT `release_date` | **不具備** | 五個 parquet 皆無此欄 |
| 各上游授權／再散布 | **NOT VERIFIED** | 見 §5 |

**維持「無法判定」／「尚未提供」的項目**：位階、light、health、曝險、VIX、US10Y、DXY、利差、PMI。

**硬性禁止**：不得補 neutral／0／safe；**不得以舊訊號、forward-test 歷史或 proxy 產生有效市場判斷**。

---

## §4 下一階段三方案比較

Token 欄為 INFERENCE，以預估改動檔數／測試量／QA 輪數表示。

| | 方案 1：保留「未提供」並完善契約 | 方案 2：凍結語意下研究恢復既有有效廣度資料 | 方案 3：新位階／新來源 |
|---|---|---|---|
| 內容 | 把 Digest market 段「最多誠實呈現」寫成契約測試；補 `tw_pmi` staleness 登記（屬正式碼，需另授權） | 只研究恢復條件與來源，**不改旗標**；先裁示「恢復是否等於新增來源」 | 新位階算法／新 fetcher／新 cron |
| 正確性／風險 | 低風險；不新增任何判斷 | 中；研究本身無風險，但若結論是「需新 fetcher」即進入方案 3 邊界 | **高**：投資語意、PIT、授權皆未解；與 DEC-074／075 衝突風險 |
| 速度 | 快 | 中（需客戶先裁示前置問題） | 慢 |
| Token（INFERENCE） | 約 1～3 檔、1 個測試檔、1～2 輪 QA | 文件為主，約 1 份研究、1～2 輪 QA | 多檔＋多測試＋多輪 QA，且需 PIT 驗證 |
| 對 UI2 推進 | 小到中（讓既有事實可信呈現） | 間接（解鎖位階） | 理論最大，實際被 Gate 擋住 |
| 授權 | 文件／測試層面可；正式碼另授權 | 研究可；恢復旗標需另授權 | **未授權** |

**AI 推薦（非客戶裁示）**：

1. 先做方案 1 的最小可推進項：讓 UI2 市場頁以「既有 canonical 事實」呈現，即 TWII 日 K ＋ as_of／stale（已接），再加 inst／margin／sector_flow 的唯讀 service，先做 **Old-UI-First 盤點**。仍需 Gate，本批不施工。
2. 同時請客戶裁示方案 2 的前置問題：「恢復」是否等於「新增來源」。
3. **方案 3 不建議**：高風險、未授權，且與 DEC-074／075 的凍結語意直接衝突。

---

## §5 殘餘 NOT VERIFIED

- 各上游授權／再散布；repo 是否公開。
- Yahoo 收盤後可信時點。
- `tw_pmi` 登記狀態（INFERENCE：預設 stale）。
- `signals.parquet` 無禁讀測試（INFERENCE：僅靠無 caller）。
- Cloud UI2、真機、ETF Managers 2026-11-16 20:00 UTC 首次排程。
- 資料 PR #1124～#1126 的 PIT；#1119 維持 HOLD。

**本文完成 ≠ Stage F ≠ C1～C7 通過。**
