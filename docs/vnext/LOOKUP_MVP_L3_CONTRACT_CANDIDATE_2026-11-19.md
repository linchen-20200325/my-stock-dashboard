# 【候選／草案／NO CODE／待來源取證與 Decision Gate】查一檔 MVP：「4 位數代碼 → 最新一期一般業財報事實」read-only L3 契約候選

> 日期 2026-11-19｜基準 main `f1f199e5`｜授權 #1199 comment `7007425153` §3「Claude B」｜DEC-205｜**非施工授權、非 Schema 裁示、非來源核准。** 沒有完整權利／PIT／Schema 前絕對 NO CODE／NO PR。
> 標記：**〔F〕**事實（附出處：`file:符號` 或 comment id）｜**〔I〕**推論｜**〔NV〕**NOT VERIFIED。`c7007425153`＝#1199 comment 7007425153；`c7006417845`＝同 issue comment 7006417845（PREGATE NO-GO）。
> 本文不宣稱任何來源已獲准、不宣稱任何資料 PIT 已通過、不宣稱官方資料集的欄位／單位／口徑已證實。本文作者為單組，未經第二組獨立複驗。

## 1. 前提與邊界

| 項 | 內容 | 出處 |
|---|---|---|
| DG-PIT＝B＋X | 僅顯示最新值的資料日；`fetched_at` 僅內部稽核、絕不作官方公布日；不拿缺 `published_at` 的資料做歷史序列／比較／回測／訊號。本 MVP 僅「最新已證季報事實＋年季／期別、期間截止日」；**不是證明季度 PIT 已通過**，季度別 PIT／修訂語意須具名審核 | 〔F〕c7007425153 §1；DATA_WIRING_GATE_DECISION_SHEET 決策 3 |
| DG-LIC＝A | 逐資料集 A（條款可回查）／B（條款適用實際資料資源與下載路徑）／C（對本專案公開、儲存、顯名義務之適用與符合）三層分列；A 層不得宣稱 C 層核准；權利 Gate **仍 HOLD** 至逐資料集證據完成 | 〔F〕c7007425153 §1；決策 4 |
| 範圍 | 只含營收、毛利、營業利益、稅後淨利、EPS（一般業）。**排除**：金融業（91995，另 Schema）、產業、價格、籌碼、估值、推薦／OneBrain | 〔F〕c7007425153 §3 |
| 維持 HOLD（絕不推定授權） | 資料下載／定期取用／發布／再散布、改 cache、Cloud/NAS/Secrets、workflow 啟用、`src/ui2`／`real_feed`／G2F、production、真 OneBrain、System Action／Risk Cap／Schema | 〔F〕c7007425153 §1 |

## 2. 輸入契約

| 規則 | 說明 |
|---|---|
| 形式 | 恰 4 位 ASCII 數字字串（去頭尾空白後）。不支援名稱、不支援 5～6 碼／英文字尾／ETF（`00` 開頭）。〔I〕格式不合＝輸入未通過、**不進入查詢**（對應既有 `LookupResultVM.queried=False` 冷啟狀態），不屬於 §4 五類結果 |
| 代碼格式 ≠ 存在 | `classify_asset_kind` 純前綴 heuristic（4 碼且首位 1–9 → `stock`），**不代表該代碼存在**〔F〕`src/compute/etf/asset_lag.py:classify_asset_kind`。存在與否只能由資料來源回答（→ `code_not_found`） |
| 市場 | 上市（sii）／上櫃（otc）由來源回答，使用者不需輸入；來源若同時命中兩市場 → 視為資料異常，回 `source_unavailable`（不擇一） |
| 副作用 | 查詢不寫入持股／觀察／候選池／Sheet（沿用 `LookupResultVM` 隔離說明）〔F〕`shared/ui2_contract/models.py:LookupResultVM` |

## 3. 輸出事實欄位候選（單一代碼 → 單一「最新一期」）

**整體（headline）欄位**

| 欄位 | 型別 | 規則 |
|---|---|---|
| `stock_id` | str(4) | 原樣回傳輸入 |
| `dataset_id` | str | 例：官方資料集 ID（91998／94865）；**〔NV〕**是否採用這兩個資料集，取決於 Work 取證與 Gate |
| `market` | `sii`／`otc` | 由來源判定 |
| `source_url` | str | **內部**稽核用；公開 UI 不顯示原始網址／錯誤內文 |
| `report_year`／`season` | int／int | 年季（民國或西元須由來源證實後固定一種表示） |
| `period_end` | date｜null | 期間截止日；**僅當來源可證**才填（日曆年度公司 Q2→6/30 屬〔I〕，非年度公司不可套）；否則 null |
| `published_at` | datetime｜null | 官方公布時間；**未知→null，不得用 `fetched_at`、`出表日期`、metadata 出表日補**（`出表日期` 的語意 **〔NV〕** 待 Work 取證） |
| `fetched_at` | datetime | **內部稽核，不外顯**；絕不作公布日 |
| `lookup_status` | enum | 見 §4 |

**逐欄（營收／毛利／營業利益／稅後淨利／EPS 各一組，同一結構）**

| 子欄 | 規則 |
|---|---|
| `value` | 原樣數值；缺值＝null，**不補 0、不 ffill、不由其他欄反推** |
| `unit` | **來源證實前一律「待證」**。〔F〕現有 MOPS 快照 parquet 無單位欄（欄位：`stock_id, revenue, gross_profit, op_income, net_income, eps, market, roc_year, season, source, fetched_at, ...`，已讀本地 `data_cache/fundamentals/sii_115Q2.parquet`）；單位「千元／元」僅見於 c7006417845，**〔I〕**非 parquet 內證 |
| `basis`（口徑） | `ytd_cumulative`｜`single_quarter`｜`unknown`。**必須來源證實。**〔F〕現有 MOPS 快照為年初至今累計：本地實測 1101 之 營收 115Q1＝33,168,148、115Q2＝71,289,957（Q2 ≈ 上半年累計，非單季）；114Q4＝149,804,135（全年累計）。**〔NV〕**官方 data.gov.tw 資料集（91998／94865）口徑未證；在證實前一律 `unknown`，且**不得**自行相減求單季 |
| `as_of` | per-field；未知→null；**不假定六維／各欄共用同一時間** |
| `missing_reason` | `not_reported`（來源列在但該欄空）｜`not_applicable`（例：金融業營收，本 MVP 直接排除）｜`unverified`（來源未證）｜`source_unavailable`。不得以 0 或空字串代替 |

〔F〕本地快照缺值實況：115Q2 上市 1,083 檔中 revenue NaN 35、gross_profit NaN 35、op_income NaN 27（金融股營收為 NaN，例：2801、2812）；net_income、eps 0 缺（同上檔案實讀）。

## 4. 查詢結果分類（**這是查詢結果分類，不是新的 Data State**）

| `lookup_status` | 意義 | 對映既有 `FieldState`（DEC-124 五態，不新增） |
|---|---|---|
| `found` | 在已證來源的最新一期找到該代碼 | 逐欄：有值且 `as_of`/`period_end` 可信 → OK；有值但時間未證 → 值不外顯＋**NOT_EVALUATED**（〔I〕在時間可信前不給 OK）；該欄空 → MISSING |
| `code_not_found` | 來源可讀、快照完整，但無此代碼 | 整體：不顯示六欄；對映 MISSING（非 UNAVAILABLE；**不等於**抓取失敗） |
| `snapshot_missing` | 本地／約定快照不存在或該季檔缺（沿用 `FileNotFoundError.snapshot_missing` 語意） | UNAVAILABLE |
| `source_unavailable` | 來源讀取失敗、格式異常、雙市場命中等 | UNAVAILABLE；**公開 UI 不印來源錯誤內文** |
| `date_untrusted` | 有值但資料日／期別晚於基準日或無法解析 | 對映 MISSING 式 fail-closed（作法比照〔F〕`src/services/ui2/real_canonical.py:TWII_FUTURE_AS_OF_TEXT`／#1202；個股專用字句屬 Visual Gate，本文不新增字句）；不顯示該日期與值 |

規則：不補 0；不假定六維共用時間；STALE 判定 **〔NV〕** 未定——`shared/staleness.py` 季頻以「法定公告截止日」為應發布日（`quarterly_publication_due`／`quarterly_release_status`），那是**法定期限而非 `published_at`**，是否可用於 STALE 須列入 Schema Gate，不得倒推成公布日。

## 5. 與現況 mapping 風險表

| 現況（讀碼 〔F〕） | 風險 | 要求 |
|---|---|---|
| `fundamentals_snapshot_loader.load_fundamentals_snapshot`：讀本地 `data_cache/fundamentals/{sii,otc}_*.parquet`＋`latest.json`，回 `(current, prev, meta)`；`FileNotFoundError` 表快照缺 | 不帶代碼參數；整表讀取；本地 MOPS 快照 `fundamentals/**` 在 5 檔授權矩陣之外、條款 NV（c7006417845） | 即使重用也須新增薄層，且權利 Gate 未解前不得外顯 |
| `fundamental_screener_service`／`run_fundamental_prescreen`：輸出 `eps`、`pass_debt/three_rise/net_current/eps_positive`、`survivor` | **丟 provenance**（`source`/`fetched_at` 不在輸出）；`pass_*` 為布林，**無法表達「缺值／不適用」三態**；營收 NaN 之金融股被判定語意不清 | 查一檔 L3 必須回原始列＋provenance，**不得**沿用 `pass_*` |
| MOPS 快照：年初至今累計；無公告日；`fetched_at` 2026-09-18 | `basis` 與官方資料集可能不同；`fetched_at` 易被誤當公布日 | `basis`/`published_at` 顯式、未知 null |
| 官方資料集（c7007425153 §3，由總管唯讀核到，**本文未獨立複驗**）：中文欄名、公司代號、年季、營收、毛利、營業利益、淨利、基本 EPS；資源連結在 `mopsfin.twse.com.tw` | 單位、累計／單季、`出表日期` 語意、最新季與修訂紀錄皆 **〔NV〕**；**不能推定其與現有 `ajax_t163sb04/05` 快照同一權利鏈** | 欄位逐一對映待 Work 取證；未證欄位 → `unit="待證"`／`basis="unknown"`／null |
| 名稱→代碼：repo 無此能力（c7006417845） | — | 不支援名稱（§2） |

## 6. Headless 邊界檢查：最短 GO／NO-GO＋blocker

**問題**：能否在「不新增聯網、Secrets、寫檔、副作用、公開儲存新資料」下提供此 read-only L3？

**結論：NO-GO（以目前證據）。**〔I〕結構性理由：官方資料集本體若要被查詢，只能是即時取用（新增聯網）或先落地儲存（新增公開 repo data cache），兩者都被本批排除；唯一已存在的本地來源（MOPS 季快照）權利 NV、無公告日、口徑為累計。

| Blocker | 解除條件／owner |
|---|---|
| B1 DG-LIC 逐資料集 A／B／C 證據未完成（含 91998／94865 實際下載路徑 `mopsfin.twse.com.tw` 之適用，及政府資料開放授權條款第 1 版原文） | Work 唯讀取證 → 客戶／法務裁定 |
| B2 DG-PIT 季度修訂語意未審；官方 `出表日期` 語意未證 | 具名審核（Work 取證＋總管） |
| B3 官方資料集欄位／單位／口徑（累計 vs 單季）未證，最新季與修訂紀錄未證 | Work（不下載本體者標 NV，並回報所需最小授權） |
| B4 L3 Schema 未裁示（本文僅候選） | 總管＋客戶 Decision Gate |
| B5 資料入庫／儲存位置未定（不得新增公開 repo data cache） | Decision Gate |
| B6 G2F 白名單／UI2 接線未授權；`LookupResultVM` 僅 FAKE 呈現側 | Decision Gate＋Visual Gate |

## 7. 將來最小合法 PR 的接口草圖（**文件內草稿，非 code、非 Schema 裁示**）

```
lookup_latest_general_financials(stock_id: str) -> LatestFinancialsResult   # 純讀、無網路、無寫檔、無 streamlit
LatestFinancialsResult(
  lookup_status: Literal["found","code_not_found","snapshot_missing","source_unavailable","date_untrusted"],
  stock_id: str, dataset_id: str|None, market: Literal["sii","otc"]|None,
  report_year: int|None, season: int|None, period_end: date|None,
  published_at: datetime|None,          # 未知 None；不得由 fetched_at 補
  fetched_at: datetime|None,            # 內部稽核，UI 不外顯
  revenue/gross_profit/op_income/net_income/eps: FactField,
)
FactField(value: float|None, unit: str, basis: Literal["ytd_cumulative","single_quarter","unknown"],
          as_of: date|None, missing_reason: str|None)
```

驗收條件（皆需 PR 前授權）：(1) 無 `requests`／`streamlit`／檔案寫入／`os.environ` 讀取（AST 守衛）；(2) 5 類結果各有反例測試；(3) 缺值不補 0；(4) `published_at` 永不等於 `fetched_at`（突變測試：拿掉驗證必紅）；(5) 公開輸出無來源錯誤內文與 `source_url`；(6) 未證 `unit`／`basis` 不得外顯為確定值；(7) 層次符合 CLAUDE.md §8.2（L3 不 import L4/L5）。

## 8. 需要的 Decision Gate（具名；每項附建議與理由）

| Gate | 建議方案 | 理由 |
|---|---|---|
| HEADLESS-MVP-IMPLEMENTATION 授權 | **維持 HOLD，B1～B6 取證完成後再另送** | c7007425153 §4：不得因有原型或授權標示自行施工 |
| 財報欄位定義與單位／口徑 | 建議 v1 只收「來源證實為同一口徑」的五欄，並顯式標「累計／單季」；不求單季衍生 | 現有快照為累計，反推單季會製造未驗證數字 |
| L3 Schema | 採本文 §3 結構為討論底稿，由總管裁示 | 缺值／口徑／時間三者必須可表達 |
| 資料入庫與儲存位置 | 優先「不新增公開 repo data cache」的方案；細節待 DG-LIC C 層 | 公開 repo 歷史曝露疑慮不因另一資料集開放條款解除（c7007425153 §1） |
| G2F allowlist | 待上列全數裁示後再提，並先過 Visual Gate | UI2 接線屬獨立 HOLD |
