# Stage F：Headless 輸入／授權矩陣、A2 stale 語意、Digest v2 方向（唯讀研究）

> **基準**：main `8df4797d898f7002ff6c55a3fa6c3b2371a93720`　**量測日**：2026-11-11
> **授權來源**：GitHub Issue #1130（客戶於 ChatGPT 對話裁示的**轉錄**，非客戶逐字原文、非 QA PASS；方案 A）。
> **本檔性質**：唯讀研究與文件契約。**不是施工授權**；不新增任何程式、市場位階計算、headless fetcher、proxy、OAuth bypass、服務帳號讀私人 Sheet、API、Secret、持久化／排程、production caller；不改 Digest 欄位／schema／validator。
> **單組撰寫，未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。其中「由事實推出的判斷」一律只能當待驗事項，不得作為後續動作的前提。

## 0. 標示規則

| 標示 | 意義 |
|---|---|
| **FACT** | 本次對照程式、設定檔或 data_cache 實測／實讀所得（附 `path::symbol`，不寫行號，除非行號本身是被引用之證據） |
| **INFERENCE** | 由 FACT 推得的判斷；單組、未經第二組複驗 |
| **MISSING** | repo 內找不到現成、可授權的對象 |
| **NOT VERIFIED** | 未實測、或需外部環境（Streamlit Cloud、真機、GitHub Secret、第三方授權條款）才能驗 |
| **AI 推薦** | 單組 AI 的建議，**不是客戶裁示**；各 Gate 的答案不得由本檔預設 |

⚠️ 「資料能讀」不等於「可公開」、不等於「可跨使用者使用」、也不等於「是有效（fresh／PIT 合格）來源」。本檔三者分開判斷。

---

## 1. Headless 輸入矩陣（source → consumer → authorization → freshness → PIT）

### 1.1 公共市場資料

| 來源（FACT） | Consumer（FACT） | 授權／存取（INFERENCE 或 NOT VERIFIED） | Freshness（FACT） | PIT（FACT／MISSING） | Headless 可用性結論 |
|---|---|---|---|---|---|
| **市場位階**：`src/services/macro_state_locker.py::get_macro_state`（純函式；輸入 `warroom_summary`，由 session 內 `warroom_apply.compute_and_store_warroom_summary` 寫入）。回傳 9 鍵，**無 `as_of`** | UI2／舊 UI／`allocation_service.get_macro_regime`（只讀 warroom 與 `macro_state.json`） | 屬站內運算結果、無第三方授權問題；但輸入是 session，非獨立來源 | production 因 `shared/signal_thresholds.py::BREADTH_PROXY_SCORING_ENABLED = False`，健康分非有限 → 位階恆 `unknown`／`is_loaded=False`（`warroom_summary=None` 時亦同） | 無 `as_of` 欄 → **MISSING** | **不可 headless**：無 session 即無輸入；MISSING 位階算法與來源（不得新增） |
| **`macro_state.json`**（裁決檔） | `get_macro_state` 讀檔；7 天過期（`shared/staleness.py::MACRO_VERDICT_MAX_AGE_DAYS = STALE_DAYS_DAILY`） | `.gitignore` 第 22 行 `macro_state.json`（第 25 行 `risk_cap_state.json`、第 26 行為其 `.tmp`）＝不入 git | 檔內 `timestamp`＝**裁決產生時間，非資料日**；資料日在 `input_asof`（`src/services/risk_cap_apply.py` 輸出附帶欄位） | 以 `input_asof` 為資料日；無 release_date | **僅 session 內寫**（舊 UI `section_news_ai.py`；新 UI 按鈕 `risk_cap_apply.compute_and_lock_risk_cap`）。`.github`／`scripts` 無任何寫入此檔者（`scripts/risk_cap_history_poc.py` 僅**保護**該檔不被覆寫，跑前跑後比雜湊）。**無任何 headless 副本** |
| **`allocation_service`**（`src/services/allocation_service.py`） | 持股上限／建議配置 | 站內運算 | 讀 session：`warroom_summary`、`_EXTRA_CAPS_KEY`、`cl_ts`、`_alloc_*`；`_read_vix` 讀 `session['macro_info']`；`_read_foreign_futures_lots` 讀 `session['li_latest']` | — | **模組層 `import streamlit`，無 session 不可獨立使用**；`get_allocation` 還會**寫** session。`get_macro_regime` 只讀 warroom＋檔 |
| **無頭 Risk Cap PoC**：`scripts/risk_cap_history_poc.py` | 歷史重放研究 | `shared/risk_cap_history_policy.py::PRODUCTION_WRITE_APPROVED = False` | — | PoC 自述有資料時點問題待修（見該常數上方註解） | **未核准寫入**，不是可用來源 |
| **git 追蹤落地：`data_cache/{twii_ohlcv,finmind_inst,finmind_margin,finmind_m1m2,tw_pmi}.parquet`＋`macro_last_good/`** | 校準與重放；UI2 `real_feed` 部分重用 | **FinMind 等第三方資料再散布授權＝NOT VERIFIED**（repo 為 git 追蹤、PR 發布；是否可對外／跨使用者再使用未見條款核對） | `update_macro_history.yml` cron `0 9 * * *`（UTC 09:00）→ `auto/data-macro-history` 分支＋PR。`data_cache/metadata.json`：twii／inst／margin `last_updated` 2026-11-09、`last_error` null；**`finmind_m1m2` `last_updated` 2026-09-01，`last_error`「抓取結果為空」，`fetch_outcome=NO_NEW_DATA`**；**`tw_pmi` `last_updated` 2026-10-01，「抓取結果為空」，`fetch_outcome=UNDETERMINED`**（metadata `updated_at` 2026-11-09T19:40Z） | parquet 僅 `date` 欄，**無 `release_date`／公告日** → PIT 欄 **MISSING**（對照 `CLAUDE.md` §2.3：月資料須以公告日對齊） | 可讀、可作研究；**不可直接視為 headless 有效市場位階來源**（無位階算法、無 PIT 欄、部分資料 `NO_NEW_DATA`／`UNDETERMINED`） |
| **`data_cache/sector_flow/`** | 板塊資金流 | 同上（再散布授權 NOT VERIFIED） | `update_sector_flow.yml` cron `30 9 * * *`（UTC 09:30） | 未逐欄查 | 非位階輸入；本批未深入 |
| **`data_cache/macro_forward_test/signals.parquet`** | 前進式驗證（凍結當日位階） | 站內產物 | `update_macro_forward_test.yml` cron `40 9 * * 1-5`（UTC，週一至五）。47 列、`date` 2026-08-20～2026-11-03：`effective_regime` bull 22／neutral 18／unknown 6／bear 1；`schema_version` 1：37、2：4、3：6；6 列 unknown 的 `regime_source`＝`unevaluated:breadth_unavailable` | 有 `captured_at`／`inputs_as_of`／`date_source` | **FACT**：`src/ui`、`src/ui2`、`src/services/ui2`、`app.py`、`app_ui2.py` 內**無**引用；引用者為 `src/compute/macro/macro_forward_test.py`、`src/data/macro/macro_fwd_test_store.py`、`src/services/macro_refresh_service.py`、`src/compute/macro/macro_session_patch.py`。**「授權作 live 位階使用」＝NOT VERIFIED**（它是驗證紀錄，不是授權的 live 來源；且 Open PR #1126 的 PIT 獨立驗證本批未處理） |
| **`picks.parquet`／`fundamentals`／`health_watchlist.json`** | 選股排名凍結／基本面／觀察清單 | — | — | — | **非位階輸入**，與 Digest 市場段無關 |
| **UI2 `real_feed`**（`src/services/ui2/real_feed.py`） | New UI2 Real Preview | — | `src/services/market_twii_view_service.py::get_twii_trend_view` 回傳附 `as_of`／`is_stale`／`upstream_state`；`get_macro_regime(strict)` 僅作橋；**Risk Cap 刻意不收** | 有 `as_of` | **可重用**的只有「加權指數日 K 趨勢」一項；位階／light／health、`exposure_limit_pct`／allocation **MISSING** |

**公共資料結論表**

| 類別 | 結論 |
|---|---|
| **可 headless（公共）** | 加權指數日 K 趨勢（`get_twii_trend_view`，有 `as_of`／`is_stale`）；git 追蹤歷史 parquet 的**讀取**（FACT 可讀；**再散布授權 NOT VERIFIED**；僅可作研究輸入，PIT 欄 MISSING） |
| **必須登入脈絡** | 無（公共市場資料不需登入） |
| **MISSING／NOT VERIFIED** | 位階／light／health；`exposure_limit_pct`／allocation；任何 `macro_state.json` 的 headless 副本；真實市場廣度（`BREADTH_PROXY_SCORING_ENABLED=False` 下為 `unevaluated:breadth_unavailable`）；PIT `release_date` 欄；FinMind 等再散布授權；`signals.parquet` 作 live 位階之授權 |

### 1.2 私有持股

| 環節（FACT） | 內容 | 授權／隔離（FACT 與 INFERENCE 分開） |
|---|---|---|
| **取得鏈 ①** | `src/data/portfolio/oauth_state.py`：token 只存在 `st.session_state['gsheet_tokens']`，檔頭明訂「不得保存 Google 憑證」 | FACT：token 不落檔 |
| **② 讀取** | `src/data/portfolio/gsheet_portfolio.py::_build_client`：OAuth＋Sheet ACL；SEC-3 已拔 Service Account fallback；未登入拋 `LoginRequiredError` | FACT |
| **③ 綁定** | `portfolio_binding_service.get_active_sheet` | FACT（Active Sheet Gate 細節 **NOT VERIFIED**） |
| **④ 持股** | `src/services/holdings_service.py::get_holdings`：需登入＋active Sheet＋使用者選定；`HoldingsResult` **無日期欄** | FACT；**持股 `as_of`＝MISSING** |
| **⑤ 鍵** | `shared/strategy_class_schema.py::build_holding_keys`（L0 純函式；`derive_portfolio_id`＝`pfv1-`＋sha256 前 20 hex） | FACT：純函式但**輸入私有** |
| **隔離** | 快取鍵以 token `sub` 雜湊（SEC-1）；`data_cache` 無使用者持股（`picks.parquet` 為選股排名凍結，100 列，非個人持股）；風險 Cap 的系統 Sheet 與個人持股 Sheet 分離（DR-2026-10-19-2） | SEC-1：FACT（BACKLOG 記載已修）。**「無『缺資料改用其他帳戶』的程式路徑」＝INFERENCE（單組）**。不得以「缺資料」改用其他帳戶 |
| **既有「不需 session」路徑** | `scripts/push_holdings_daily.py`＋`.github/workflows/push_holdings_daily.yml`（cron `30 22 * * 0-4`，UTC 週日～週四＝台灣週一～週五 06:30）→ `src/data/portfolio/gsheet_sa_reader.py`（`GCP_SERVICE_ACCOUNT_JSON`＋`PORTFOLIO_SHEET_ID`，scope `spreadsheets.readonly`；單一擁有者） | FACT：路徑存在。**授權範圍是「每日持股推播」，不等於授權 Digest**（授權裁示 **MISSING**）。secret 現況 **NOT VERIFIED**。`VN1-G3-FU-1`（BACKLOG）：該 SA 可能與 fund-dashboard 共用身分，遷移待客戶決定。`BP-DR-06`（單人／多人部署）未裁 |
| **UI2 現況** | `src/ui2/views/me.py` 禁真 OAuth／Sheet；`NUI2-AUTH-CONTRACT-GATE`（BACKLOG 約 L1614）、`NUI2-ME-ACCOUNT-REAL-GATE`（約 L1424）、`P1R-DIGEST-HEADLESS-ASSEMBLY`（約 L1090）皆 open | FACT（行號為本次量測，會漂移） |

**Digest builder 輸入的 headless 可得性**

| 輸入 | 合法 headless 可得性 |
|---|---|
| `holdings_rows` | **私有**，僅登入脈絡可得（`holdings_service`） |
| `holding_keys` | 函式純，但輸入私有 → 同上 |
| `station_rows` | `dividend_station_service.build_station_rows` 為純函式（依賴注入），但需私有持股＋公共 metrics → 取決於持股 |
| `assemble_digest` | 純函式（`src/services/decision_digest_assembly.py`），**0 production caller** |

**私有持股結論表**

| 類別 | 結論 |
|---|---|
| **可 headless** | 無（沒有已授權用於 Digest 的 headless 持股路徑） |
| **必須登入脈絡** | `holdings_rows`、`holding_keys`、`station_rows` 的持股面 |
| **NOT VERIFIED** | 推播 SA 的 secret 現況與權限範圍；Active Sheet Gate；單人／多人部署（BP-DR-06）；持股 `as_of` 由誰提供（MISSING） |

⚠️ 「能讀」≠「可跨戶使用」≠「有效來源」：即使 SA 技術上讀得到單一擁有者 Sheet，也沒有裁示允許把它餵給 Digest；本檔不預設答案。

---

## 2. A2 stale 語意（Issue #1130 裁示 2）

### 2.1 裁示要點（轉錄）

- **Retained evidence（保留的證據）**：stale／來源失敗／PIT 不合格的值，可在**隔離的 Evidence／audit／coverage 記錄**保留 `source`、`as_of`、`observed_at`、`fetched_at` 等已存在且可追溯的 provenance 與**拒用原因**；數值是否保留須遵守原始存取權限與既有契約。
- **Eligible evidence（可用證據）**：通過 freshness／PIT／權限驗證後，才可進入 deterministic decision。
- **禁止**：stale 值當 fresh／eligible 進入決策、動作、Risk Cap、排序、信心或摘要的有效依據；不得偷補 0、neutral、safe、HOLD。要區分 **`stale evidence retained`** 與 **`stale value used for decision`**。
- P-4 現有 fail-closed 拒用**維持有效**。本次只核准語意方向與文件契約研究，不改 Digest 欄位、schema／validator、計算、UI；若 A2 與凍結契約衝突，回報 Gate，不自行折衷。

### 2.2 與現況對照

| 項目 | 現況（FACT） | 與裁示 |
|---|---|---|
| P-4 `assemble_digest`（DEC-159） | 證據被拒用（無日期戳、`FETCH_FAILED`／`UNDETERMINED`、freshness 非 `FRESH`——含 stale、PIT 違反）時，**連同該段上游輸入一併不傳 builder**，只在 `DigestCoverage` 記原因與 `as_of`／`source` | **一致**：stale 值不進決策；coverage 即為隔離的 retained 記錄。維持有效 |
| 契約 §6 A2（`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`） | 字面為「builder 依 `shared/staleness` 產出 STALE」——即 **STALE 值（`DataStatus.STALE`）進入 Digest** | **有衝突風險**：若 STALE 事實進 Digest 且與 OK 路徑共用段落，可能被下游當有效依據；與裁示的「retained ≠ used」要靠額外隔離才相容 |
| 凍結 v1 | `shared/decision_digest*.py`：不得改欄位／升版 | 任何 A2 落地都屬 v2，本批**不得**做 |

### 2.3 兩種解法（INFERENCE；待後續 schema Decision Gate）

| | **A2-i：STALE 事實僅進 audit／coverage 區，不進決策段** | **A2-ii：`DataStatus.STALE` 進 Digest 段，但 validator＋grounding 禁止其支援任何 action／cap／摘要有效依據** |
|---|---|---|
| 做法 | 延續 P-4 現行方向：stale 值不傳 builder；retained 只在 coverage／audit 欄（含 `source`／`as_of`／`observed_at`／`fetched_at`／拒用原因） | Digest 段內可見 STALE 事實；validator 禁止 stale 出現在 actions／risk_cap 的 OK 路徑，grounding 檢查 stale 不得為任何有效依據 |
| 優點 | 與 P-4 現況與裁示最直接一致；隔離最乾淨；不需新增「STALE 不得被引用」的驗證規則；v1 側車可平順併入 v2 coverage | 消費者在 Digest 本體即可看到「這段有陳舊證據」，不必另取 coverage；較貼近契約 §6 A2 字面 |
| 缺點 | 需 v2 強制 coverage 才能避免「只拿裸 Digest 看不到 stale」（與 DEC-159 已知限制 1 同源）；契約 §6 A2 字面須修訂 | 風險最高：任何一個 validator／grounding 漏洞即讓 stale 被當 fresh 用（正是裁示要防的「stale value used for decision」）；需新增大量反例測試；與 P-4 已落地的 fail-closed 行為需重新對齊 |
| 與凍結 v1 | 僅 v2 能吸收 | 僅 v2（STALE 值進欄位＝改 Provenance／Fact 語意）|

**AI 推薦（非裁示）**：A2-i 較安全。**本批不改任何欄位；取向待 G-F3 與 G-F4 一併裁示。**

---

## 3. Digest v2 方向：B＋M1（Issue #1130 裁示 3）

### 3.1 記錄的方向（轉錄，非施工授權）

`Digest v2 加性欄位吸收 S8 coverage；M1 v1／v2 雙版並存；v2 強制 coverage；v1 保留相容驗證。` 這是 **architecture direction**，**不是**破壞凍結 v1 的授權。**禁止**：實作 v2、新增 `schema_version`、A1／A2／A6／A7 新欄、升降版轉換、移除 v1、P-1 runtime、production caller、OneBrain。須另開獨立 schema／compatibility／PIT Decision Gate 並明確驗收後才開工。

### 3.2 相容性分析（取自 Issue #1127 研究留言，單組，未複驗）

來源：https://github.com/linchen-20200325/my-stock-dashboard/issues/1127#issuecomment-6786133501

| 項目 | 內容 |
|---|---|
| `_check_root` | `shared/decision_digest.py` 對 `schema_version` 嚴格比對 `!= SCHEMA_VERSION`（本次實讀約 L983 仍如此）→ 須改為接受 `{v1, v2}` 並分支（FACT：嚴格比對存在；「須改為」為 INFERENCE） |
| 硬寫 v1 的測試 | assembly 測試約 L163、contract 測試約 L218／L407（來自留言，**本次未逐一複查**） |
| 測試量 | digest 測試約 599 函式（留言數字，未重算）；另有**列舉鎖測試**（新增列舉成員會紅） |
| 凍結常數 | `MAX_ACTIONS = 3`（本次實讀 `shared/decision_digest.py` 為 3）；凍結 |
| 側車退役 | `DigestCoverage` 日後被 v2 吸收時須退役，不可並行維護兩套定義（DEC-159 已記）；雙軌期有第二 SSOT 風險 |
| 持久化與 caller | 無 `from_dict`、無持久化 Digest、`assemble_digest` **0 production caller**（本次 grep 實證）→ 向後相容的實際對象只有記憶體物件與測試 |

---

## 4. 後續 Decision Gate（全部未啟動；等客戶裁示）

> 「AI 推薦」欄只是單組建議，**不得視為客戶已選**。

| Gate | 問題 | 阻塞前置 | AI 推薦 | 誰裁示 |
|---|---|---|---|---|
| **G-F1** headless 市場輸入供應 | 是否授權新增 headless 市場位階來源（位階／light／health／exposure；真實廣度；PIT `release_date`）？由誰供應？ | 無現成可授權來源（§1.1）；`BREADTH_PROXY_SCORING_ENABLED=False`；第三方資料再散布授權 NOT VERIFIED；D1～D5 現狀不變 | 先裁示「是否要 headless 位階」（投資語意＋資料來源），再談來源；在裁示前不建任何 fetcher | **客戶**（投資語意與資料來源） |
| **G-F2** headless 持股授權 | Digest 是否可消費私有持股？沿用 SA 推播授權範圍，或專用唯讀憑證？單人或多人部署（BP-DR-06）？持股 `as_of` 由誰提供？ | `VN1-G3-FU-1`（SA 可能共用身分）；`BP-DR-06` 未裁；`HoldingsResult` 無日期欄；SEC-3 已拔 SA fallback | 預設**不**消費私有持股，直到上述裁示；若要做，以專用唯讀憑證＋單一擁有者為最小範圍 | **客戶**（授權與安全）；技術實作細節由總管 |
| **G-F3** A2 取向 | A2-i（STALE 僅進 audit／coverage）或 A2-ii（STALE 進 Digest 段＋validator／grounding 禁用）？ | 與 G-F4 同批較佳 | A2-i（見 §2.3） | 客戶確認語意；schema 細節內部拍板 |
| **G-F4** v2 schema／compat／PIT Gate | 是否授權實作 B＋M1（v2 加性欄、M1 雙版、強制 coverage、v1 相容驗證）？ | 須 Effort High＋獨立非作者 QA；G-F3 結論；列舉鎖／v1 硬寫測試的遷移方案；PIT 設計 | 先出 schema／相容性設計文件再裁 | **客戶**（授權）；總管提設計 |
| **G-F5** production caller 建立時機 | 何時可建立 `assemble_digest` 的 production caller？ | G-F1／G-F2 裁示；`XV-C05` 驗證（DEC-101 要求接摘要前完成並驗證）；`AB4R-WIRE-BUILDER`；`P1R-FIVE-BUCKET-L3`；契約 §9 測試 | 前置未滿足不建 caller，以免把 session 缺值包成「看似 headless」的 Digest；`is_complete` 零行動恆 False 亦不會完整 | **客戶**（時機）；技術前置由總管 |
| **G-F6** 登入前置 | `NUI2-AUTH-CONTRACT-GATE`／Active Sheet 是否為 Digest 持股段的前置？ | repo 目前沒有 New UI2 用的 auth contract（BACKLOG 該列）；Active Sheet Gate 細節 NOT VERIFIED | 若 G-F2 要消費持股，則列為前置 | **客戶** |

---

## 5. 殘餘 NOT VERIFIED 與限制

- 本檔全部判斷單組撰寫，未經第二組複驗；§1.2「無『缺資料改用其他帳戶』程式路徑」為 INFERENCE。
- 未實測：Streamlit Cloud 上的 New UI2、真機、ETF Managers 2026-11-16 20:00 UTC 首次排程真實 Actions PR、Open 資料 PR #1124／#1125／#1126 的 PIT（本批與其完全隔離，未碰）、GitHub Secret 現況、第三方資料再散布授權。
- 行號類引用（BACKLOG 各列、`decision_digest.py` 約 L983）為 2026-11-11 量測，會漂移（`CLAUDE.md` §8.2.A.0 規則 4）。
- 本檔完成 ≠ Stage F 完成 ≠ C1～C7 通過；#1119 維持 HOLD；#1124～#1126 未碰。
