# PROJECT_STATE — 目前仍有效的專案知識（my-stock-dashboard）

> **定位**：ChatGPT 與 Claude 共用、「**目前仍有效**」且下一個沒有舊聊天記憶的 AI 必須知道的專案知識（客戶 2026-10-22 裁示，`docs/DECISIONS.md` DEC-068；分工見 `PROJECT_RULES.md` §0.3、§15）。
> **原則**：本檔「**保存專案知識，不保存聊天紀錄**」。
> **不是什麼**：不是 BACKLOG（未完成工作只在 `docs/BACKLOG.md`）、不是 HANDOFF（current／blocker／next safe point 只在 `docs/HANDOFF.md`）、**不取代 DECISIONS**（正式裁示只在 `docs/DECISIONS.md`）。本檔只做摘要＋出處；與出處不一致時**以出處為準**。
> **優先序**：本檔的狀態快照**低於** GitHub 實況與 `docs/HANDOFF.md`（`PROJECT_RULES.md` §15）。
> **量測**：~~2026-10-22；量測時 `origin/main`＝`d3a3e676`（cron tip；最後非 cron 合併＝#898 `1d9e6c1c`）~~ ~~2026-10-22T18:57Z；量測時 `origin/main`＝`7f58a25a`（#901，最後非 cron 合併；撰寫組 `git fetch` 實查）~~ 2026-10-22T20:41Z；量測時 `origin/main`＝`08272e5`（#902，最後非 cron 合併；撰寫組 `git fetch origin main` 實查）（2026-10-22 更新，有意識的變更，不是漏刪，決策者 AI 總管（事實更正））。cron 會推進 tip，引用前重查。
> **標示**：「Approved」＝有 DEC 或硬規則出處；「Candidate／Decision Gate」＝未核准；「GitHub 無定義來源」＝不得推測，待客戶提供或研究後經 Decision Gate。
> ⚠️ 本檔由單一撰寫組撰寫（`CLAUDE.md` §-2 規則 6）；各段結論以所附出處為準。⛔ 本檔不含任何 secret、credential、private key。

## 1. North Star／產品定位

- 產品方向「投資決策 OS／Investment Inbox」—— **只核准方向，不是實作授權**（DEC-056）。客戶接手提示另稱「Decision-first Investment OS」；撰寫組讀法（非客戶明示）：兩者指同一方向。
- North Star 客戶原文：「每天替使用者過濾市場噪音，只把真正需要做決定的事情送到面前；每個結論都可以一路追溯到正式規則與客觀資料。」（`docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md` §1）
- 反北極星：「不要把專案做成：更多資料＋更多指標＋更多卡片＋更多 Gate＋更多 AI 文字」（同上）。
- Blueprint 是方向承載者，不帶 Decision 效力、不是施工授權（DEC-057；`PROJECT_RULES.md` §0.3）。

## 2. 產品階段與 roadmap

- 路線 vNext 0.9 → 1.0 → 2.0 → 3.0（Blueprint §20）。**目前階段＝vNext 1.0**（DEC-062；`docs/HANDOFF.md` §1）。
- 1.0 已裁示範圍：DEC-062 Q1～Q5（全文見 `docs/vnext/VNEXT_1_0_DECISION_GATES.md`）。
- 1.0 建議批次現況（`VNEXT_1_0_DECISION_GATES.md` §6；建議不是授權）：`1.0-B1` 安全地基完成（#877）；`1.0-B2` 靜默恢復登入程式已合併（#879），待客戶正式網站驗收（`B2-FU-1`）；`1.0-B3` 保存方式研究完成（#881）→ 延伸為 `VN1-STORE` 主線（DEC-063～066）；`1.0-B4` 線框送審**未開始**。
- Roadmap 每一批都要客戶指派（DEC-015、DEC-006）；已完成批次不得重做。
- 📌 2026-10-22（DEC-071，append-only）：客戶確認第一個主頁改以「大盤／市場趨勢」為核心、導航後續改名（候選非 final）；與 DEC-062 Q1「今天頁」送審範圍及 DEC-057「首頁不是 Dashboard」的關係**待 Decision Gate**（BACKLOG `VN1-MT-HOME`／`VN1-MT-NAV`）；`1.0-B4` 線框仍未開始。見 §22。

## 3. Data ≠ AI reasoning（Approved）

- 資料層只負責取得、驗證、標準化、缺值狀態；AI 只讀已驗證資料，不得生成客觀資料、猜缺值、自成 primary source、把推論寫回資料、偷改公式／權重／rule（DEC-027；`PROJECT_RULES.md` §13 D3／D4）。
- 四層責任邊界：① Data → ② Rule → ③ Decision → ④ AI 解釋（Blueprint §3）。強 Action 不得只靠生成式 AI（DEC-054）。
- 相關硬規則：missing ≠ 0（D5）、unavailable ≠ neutral（D6）、not evaluated ≠ safe（D7）、provenance／as-of／freshness 必須真實（D8）、no fake precision（D10）。

## 4. Risk Cap v2 現行架構（**原碼為準**）

> 以下為 2026-10-22 對照原碼的**概要**，不是規格；數值以 `src/services/macro_state_locker.py::calculate_system_state` 與其模組常數為準。正式架構文件缺口已登記 `docs/BACKLOG.md` `AUD-C23`。改任何公式／門檻屬 Decision Gate（`PROJECT_RULES.md` §4 #1）。

- **規則版本**：`shared/risk_cap_policy.py::RISK_CAP_RULESET_VERSION`＝`risk_cap.v2`（M1B−M2 腿停用後的版本，DEC-049）。
- **基準**：score 從 60 起算；缺的輸入整條不算（不加不扣、不代預設值）。
- **計分項**：VIX（高檔扣分、低檔加分）、台灣 PMI 當期水位（收縮扣分、擴張加分）、BIAS240（高乖離須伴隨 VIX 偏高或 PMI 收縮才扣分；深度負乖離加分）、PCR（標準比值刻度；偏高扣分、偏低加分）。M1B−M2 資金項**已停用、不計分、不算缺值**（`shared/signal_thresholds.py::M1B_M2_LEG_ENABLED`＝False；DEC-049；D14）。
- **初始曝險**：分數四捨五入到 10 的倍數、夾在 0～100。
- **三大硬否決（只會往下壓上限）**：薩姆規則觸發 → 上限 20；PMI 當期與前月皆低於 48 → 上限 40；外資期貨淨空（TX 當量口）低於 −35,000 **且**加權指數跌破 MA5 → 上限 30（常數見 `macro_state_locker` 模組頂端 `MACRO_VETO_*`）。
- **等級**：上限 ≥70 多頭／安全；≥40 震盪／警告；其餘空頭／危險（`MACRO_EXPOSURE_*_MIN_PCT`）。
- **全缺 fail-safe**：所有啟用中的數值輸入全缺且薩姆未觸發 → 回「系統異常」預設狀態，不給投資結論（DEC-041）。
- **Required Core**：VIX、PMI 當期、PMI 前月、外資期貨、指數是否跌破 MA5（`shared/risk_cap_policy.py::REQUIRED_CORE_INPUTS`；DEC-048）。任一無法評估 → 本輪不產生新上限。
- **沿用**：可沿用 7 天內最近一次有效快照（`shared/staleness.py::MACRO_VERDICT_MAX_AGE_DAYS`），超過 → 建議持股「無法判定」；不得因缺資料放寬風控（DEC-044、DEC-048；D13）。
- **揭露**：Optional 缺項須揭露（DEC-051）；新 UI 使用獨立快照檔（DEC-052）。

## 5. Risk Cap History／System Risk Cap Sheet（現況）

- 保存方式：系統專用 Google Sheet（DEC-063）；Git repo 不得當 production datastore（DEC-062 Q4）。紀錄 schema 版本 `shared/risk_cap_history_policy.py::HISTORY_SCHEMA_VERSION`（`risk_cap_history.v1`）。
- **現況：Sheet 沒有任何正式列**（DEC-066 狀態補註三）。今天頁維持「從今天開始記錄」，不得製造不存在的歷史比較（DEC-062 Q4）。
- 舊 `macro_state.json` 只在 Streamlit Cloud ephemeral 磁碟（`AUD-C12`，仍 open）。
- 研究與 PoC 的待決設計項：`docs/vnext/VN1_STORE_RESEARCH.md` §8.4（12 項，BACKLOG 有指標列）。

## 6. Writer／Reader／WIF／Environment（現行架構與已完成驗證）

- **Writer**：GitHub Actions workflow 的 `production-write` mode，只在 `main`、人工 `workflow_dispatch`；以 WIF 換短期憑證、**無 JSON key**（DEC-064 G1）。寫入 job 在任何 auth 之前先檢查核准旗標（#890）；依賴 hash 鎖定、共用 concurrency（#891）。單一 writer，⛔ 第二 writer、distributed lock（DEC-066 D）。
- **Reader**：L3 `src/services/risk_cap_history_reader_service.read_history`，唯讀身分只放 Streamlit secrets（DEC-064 G2）；空表真連線 smoke **PASS**（`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 8.10）；**有資料狀態未驗**（`VN1-PG-READBACK`）；**沒有任何 UI 呼叫端**（畫面顯示歷史須先過線框 Gate，DEC-003）。
- **Environment／WIF**（DEC-066 C）：Step 1 客戶建立 Environment `production-risk-cap`；Step 2 workflow 只有 `production_write` 引用它（#894）；Step 3 客戶收緊 WIF attribute condition（加 environment 與 `workflow_dispatch` 條件），反向驗證 run 39589906182 預期失敗 PASS。
- **已完成驗證**：規格第 5 節 P1／P2／R1～R5 全部 PASS（規格 5.4，DEC-064 補註）。⚠️ **正向換 token 未實測**；WIF describe 原文不在 repo。設定細節以規格為準。

## 7. production-write 真實歷史與目前 Gate

- **production-write 從未執行**；System Risk Cap Sheet 無首筆正式紀錄（DEC-066 狀態補註三）。
- 經過：#896 一次性開旗標（DEC-066 A）→ 同日 dry-run run 39755679219（2026-10-22 17:28 台北，main `e7e580c`）`VALID`、上限 30%（紅線三）但判 **Fail-Stop**：VIX 為美股未開盤的暫定日線、veto 判定未留痕 → 客戶裁示 B 關窗 → #897（`c2824c8f`）旗標改回 False。前兩次 dry-run：39608164307（10-21）、39695843255（10-22 早上，^TWII 少一根造成跨日配對，客戶不接受）。
- **目前 Gate**：`shared/risk_cap_history_policy.py::PRODUCTION_WRITE_APPROVED`＝False。重開前須先完成並驗證 `VN1-PG-VIX-ASOF`／`VN1-PG-VETO-TRACE`／`VN1-PG-PIT-CONSISTENCY`，再走**新的**旗標 Gate（DEC-066 補註三）。**Daily Schedule NOT APPROVED**（DEC-066 F），⛔ 新增 `schedule:`；且現行 WIF `workflow_dispatch` 條件會擋 schedule。
- 失敗政策 FAIL-STOP：禁止自動刪列／rollback／覆寫／盲目 retry（DEC-066 E）。
- 📌 2026-10-22（DEC-070）：三項 MUST 的**資料語意已裁示** —— Risk Cap 每日代表時點採「盤後版」：正式語意「盤後且 D 日必要台股資料均已正式可得」；台股輸入以同一錨定交易日 D 為原則、外資期貨與 MA5 屬同一台股交易日；VIX 只用判斷時點已完成收盤、不造成 look-ahead 的資料；PMI 資料月規則不變；Yahoo 缺 ^TWII 必要 K 棒 → Fail-Stop／無法評估並明示（⛔ 不以前一交易日頂替、暫不新增或替換來源）。**台北 16:00＝保守執行時間／Candidate，未固化**。⛔ 三項**仍未實作**；重開仍須實作＋驗證＋新的旗標 Gate；DEC-070 不是實作授權、不是重開授權。

## 8. OAuth／Sheet Picker／multi-Sheet

- **已完成**：`SEC-2` OAuth state 綁瀏覽器一次性 nonce、`SEC-3` 匿名不得經 service account 讀持股 Sheet（#877；DEC-062 Q3＝A）；`1.0-B2` 重新整理後以 Google `prompt=none` 靜默恢復登入、不保存 Google 憑證（#879；DEC-062 Q2＝B；機制與安全閥見 `docs/OAUTH_SETUP.md`）。
- **待驗**：正式網站真實登入驗收 `B1-FU-2`／`B2-FU-1`（客戶動作）；驗不過依 Q2 退回 A。
- **Sheet 選擇（Sheet Picker）**：屬 1.0 已核准範圍（DEC-062 Q1＝B：晶片彈窗與「我的」頁），但 `1.0-B4` 線框**未送審、未開始**；線框拍板前不寫 UI code（DEC-003）。加 Google Picker API key、改 OAuth scope 屬 credentials Gate（Blueprint §7.7）。已知缺口：換第二本 Sheet 不生效（`B2-FU-2`）、URL `?sheet=` 信任模型（`B2-FU-3`）。
- **multi-Sheet 方向**：客戶 2026-10-19 接手提示原話（聊天，未入 DECISIONS；**方向，不是裁示**）：同一 Google 帳號可以有多本 Sheet；未來須能選、切換、管理多個有權限的 Sheet；Sheet 成為 current 是因使用者經正式 UI 明確選擇，不得把 URL 參數當成授權；沿用既有 OAuth infrastructure。**細節（UI 流程、資料模型、權限模型）：GitHub 無定義來源；不得推測；待客戶提供或研究後經 Decision Gate。**

## 9. 已完成的重要安全治理

- `SEC-1` 持股讀取快取依使用者隔離（#870）；`SEC-2`／`SEC-3`（#877）。
- `VN1-STORE` 身分分離：writer 無 key（WIF）、reader 唯讀且只在 Streamlit secrets（DEC-064）；一次性測試 secret 已清除（DEC-065）；Actions 以完整 SHA 釘版（#886）；writer 依賴 hash 鎖定（#891）。
- 文件 secret scrub 守衛：`tests/test_sec_s3_batch_s3.py`、`tests/test_sec_s4_batch_s4.py` 掃所有追蹤的 md 段落。
- 回報、log、PR、issue 不得貼出任何金鑰內容或 secret 值（`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 4 節開頭）。

## 10. 已知資料時點、freshness、PIT 問題

- 原則（Approved）：No Look-ahead（DEC-039；D9）；觀測日＝真正所屬交易日（DEC-028）；cache 存活 ≠ 資料新鮮（DEC-029；D8）；FRED 用 release_date（`CLAUDE.md` §2.3）。
- **VIX 暫定日線**：傍晚台北時間的 VIX 標當日日期，但美股尚未收盤 ⇒ 是盤前／未收盤暫定值；現行 freshness 只看日期標籤無法區分（`VN1-PG-VIX-ASOF`）。
- **^TWII 早上少一根**：yfinance 偶發缺最新 K 棒，`dropna` 不 log（`VN1-PG-L-TWII-DROPNA-LOG`）；導致 MA5 與外資期貨跨日配對（`VN1-PG-PIT-CONSISTENCY`）。
- **veto 未留痕**：log 未留外資期貨口數、MA5 判定、veto_flags（`VN1-PG-VETO-TRACE`）。
- ~~**互鎖結論**（2026-10-22 總管分析，AI 研究結論、單組、非客戶裁示）：傍晚跑 → VIX 必為暫定日線；早上跑 → ^TWII 可能少一根 ⇒ **不改程式就沒有任何時段能完整通過 Gate**。三項 MUST 必須一起研究。~~
  **現行**（2026-10-22 更正，有意識的變更，不是漏刪，決策者 AI 總管（研究更正）；**AI 研究結論、四組研究＋總管抽查原碼，非客戶裁示**）：「不改程式仍沒有時段能完整通過」**大致成立**，但**原因更正**為：(1) VIX 問題來自「取最後一根 bar」的選值方式，**不是** VIX 與 ^TWII 結構互斥；改成依日期／收盤完成度選值即與執行時刻無關；(2) ^TWII 缺棒是**獨立**問題，依 DEC-070 Q2 應 Fail-Stop；(3) 根本缺口＝沒有跨輸入日期一致性檢查、沒有「已收盤／已發布」時刻概念。研究證據見 10.1。
- 欄位：`fetched_at` 只在 `fetch_fred` 落地（`CLAUDE.md` §2.2 S-PROV-1）。**`published_at`／`available_at` 欄位契約：GitHub 無定義來源；不得推測；待客戶提供或研究後經 Decision Gate**（概念見 `VN1-PG-VIX-ASOF`）。
- 交易日曆：無第三方 trading calendar（`CLAUDE.md` §4.5）；平日國定假日異常 K 棒（`AUD-C13`）。**期貨結算日規則：GitHub 無定義來源；不得推測**（候選 `VN1-C-CALENDAR`）。


### 10.1 研究結論摘要（2026-10-22；`VN1-PG-VIX-ASOF`／`VN1-PG-VETO-TRACE`／`VN1-PG-PIT-CONSISTENCY`）

> **AI 研究結論（四組研究＋總管抽查原碼；總管轉述，撰寫組未重跑），非客戶裁示。** 客戶裁示只有 DEC-070 的語意部分。證據等級：〔repo 事實〕＝讀 main 原碼（HEAD `7f58a25a`）；〔外部摘要級，未讀原文〕＝WebSearch 摘要，沙箱無法讀原文（URL 為真）；〔二手〕＝非官方網站；〔未驗證〕＝沒有實測；〔推論〕＝由前述證據推得。剩餘待辦只在 BACKLOG（5.1.4 `VN1-PG-*`）。

**VIX 取數與 freshness**
- 〔repo 事實〕`src/data/macro/macro_snapshot.py::fetch_vix_block` 以 `yf.download('^VIX', period='3mo', interval='1d')` 取數；`_vd` 只留日期（bar 時刻與時區被切掉）；回傳的 `fetched_at` 在 `src/compute/macro/dated_inputs.py::extract_vix` → `shared/dated_value.py::DatedValue`（無 fetched_at 欄）時被丟掉。
- 〔repo 事實〕`shared/freshness_policy.py` 的 VIX 為 `DailyPolicy(calendar="weekday")`；`assess_daily` 只比「資料日期 vs 台北日期」相差平日數 ≤3，沒有收盤時刻比較 ⇒ 當日暫定 bar 判 FRESH。
- 〔repo 事實〕以正式 `assess_daily` 重現：MA5@10-20／評估日 10-22 → FRESH；期貨@10-21 → FRESH；VIX@10-22／評估日 10-22 → FRESH ⇒ 兩次 Fail-Stop 案例在現行判定下**都會通過**。
- 〔Actions log，總管轉述〕run 39755679219 log：runner yfinance 1.7.0；抓取時刻 2026-10-22T09:29:58Z（05:29:58 EDT）已得 `^VIX` 10-22 bar 18.4。
- 〔外部摘要級，未讀原文〕Cboe VIX：一般時段約 09:30–16:15 ET；自 2016-04 起美東約 03:00（另有 03:15 之說）–09:25 ET 也發布 VIX 指數值；20:15–03:00 ET 不發布（SR-CBOE-2024-031）。Cboe 官方「日收盤值」定義時點**查不到原文**。〔推論〕05:28 ET 那根是 GTH 盤中暫定值。
- 〔原始碼已讀：yfinance 1.7.0〕`utils.fix_Yahoo_returning_live_separate` 不濾除當日 live bar；日線無盤前過濾；issue #2353：當日 live 列存在與否取決於 period 參數；issue #2704：`^VIX` info 欄位曾回錯值（不可當判據）。
- 〔tzdata 計算〕美國 2026-11-01 結束夏令時間；VIX 16:15 ET＝台北 04:15（夏令）／05:15（標準）（16:15 ET 收盤時刻本身為〔外部摘要級〕，只有換算是 tzdata 計算）；GTH 03:00 ET＝台北 15:00（夏令）／16:00（標準）。

**veto 留痕**
- 〔repo 事實〕`src/services/macro_state_locker.py::calculate_system_state` 已計算 `veto_flags`（opt-in；呼叫鏈：`src/services/macro_engine_inputs.py::run_rule_engine` 帶 `include_veto_flags=True` 呼叫引擎，`run_rule_engine` 的唯一呼叫者為 `src/services/risk_cap_apply.py`）；VALID 寫快照時含 `veto_flags`、`red_lines`、`input_detail`（值／status／as_of）；但 `src/services/risk_cap_history_service.py::build_record` 不讀這些欄位。
- 〔repo 事實〕workflow `.github/workflows/risk_cap_history_poc.yml` 的 record JSON 保留天數：dry-run 14 天、`production_write_compute` 7 天；兩者都只上傳 record JSON，快照未上傳；無頭執行時步驟 detail 不印。**完全未保存**：MA5 數值與加權指數收盤（`dated_inputs.extract_ma5` 只存 bool）、否決前曝險值、各計分項分數。
- 〔repo 事實〕`shared/risk_cap_history_policy.py::HISTORY_COLUMNS` 20 欄、`HISTORY_SCHEMA_VERSION`＝`risk_cap_history.v1`；`input_asof` 只有日期無時刻；`snapshot_timestamp` 為台北 naive；無每項輸入的 fetched_at／available_at。`tests/test_batch_z65.py` 釘死 `veto_flags` 鍵集合 ⇒ trace 須另開鍵；讀端逐字比對表頭 ⇒ 改 schema 時寫端與網站須同版部署。

**PIT／跨輸入一致性**
- 〔repo 事實，單組 grep〕全 repo 無跨輸入日期一致性檢查；MA5＝`src/services/market_strategy.py::get_market_assessment` 取 yfinance 最後 5 列 rolling mean，不對照交易日曆；`src/data/daily/daily_data_fetchers.py` 的 `dropna(subset=['close'])` 不 log 筆數。
- 〔repo 事實〕台股交易日曆已存在（`src/data/stock/twse_holiday_fetcher.py`、`shared/trading_days.py`、`src/services/trading_calendar_service.py`；不含颱風臨時休市、只拿當年表）；無美股交易日曆。
- 〔外部摘要級，未讀原文〕TWSE 收盤 13:30，暫緩收盤至 13:33。〔二手：CMoney／HiStock〕期交所 13:45 收盤商品（含 TX）未平倉約 15:00 後揭示（2021-12 新制），官方原文未找到。〔外部摘要級，官方 Q&A〕夜盤交易量與未平倉併入次一交易日。⇒ 台北 16:00 只是**保守執行時間／Candidate**（DEC-070；驗證見 `VN1-PG-CUTOFF-VERIFY`）。
- 〔未驗證〕Yahoo 實測全部未做（沙箱 proxy CONNECT 403）；Yahoo 早上缺 ^TWII 只有 1 次觀測（run 39695843255）。未驗證項清單見 `VN1-PG-YAHOO-PROBE`；其他技術缺口見 `VN1-PG-L-PIT-GAPS`。

**技術方案候選**（研究建議、非客戶裁示、未實作；實作批仍須客戶指派）
- VIX：總管推薦「取美東日期早於 D 的最後一根」（前一個已收盤美股交易日）—— ⚠️ 這是符合 DEC-070 語意的**一種候選實作**，**不是客戶裁示**；替代為美東牆鐘＋收盤 cutoff、Yahoo metadata（未實測，只能當交叉檢查）。
- VETO-TRACE：推薦混合方案 C（歷史紀錄新增精簡 trace 欄位、schema 只增不改；完整快照另上傳 artifact；非 VALID 列也帶 trace）。
- PIT：錨定 D 依證交所日曆；台股輸入 as_of＝D（以資料日期驗證）〔客戶原文為「台股輸入以同一錨定交易日 D 為原則」（「為原則」）；Required Core（外資期貨、MA5）同日已裁示，Optional 台股輸入（PCR、BIAS240）例外範圍待實作批定〕；MA5 五根對得上交易日曆、缺一根＝無法評估；MA5／BIAS240 共用同一次 ^TWII 抓取；`dropna` log 筆數。
- 細節與剩餘待辦：BACKLOG `VN1-PG-VIX-ASOF`／`VN1-PG-VETO-TRACE`／`VN1-PG-PIT-CONSISTENCY`。

## 11. Market Regime／Market State 的定位

- 現行 `market_regime`（多頭／震盪／空頭）是 Risk Cap 引擎依上限分級的**輸出**（§4），不是獨立模型；`macro_state_locker.normalize_regime` 做中→英正規化。
- Regime 作為 Context（非 Core）：`VN-23`，Research Candidate；Context 升 Core／hard veto 須客戶裁示（DEC-009；D18）。
- 「Market State」：**GitHub 無定義來源**；Regime／State／Conflict Resolver 的統整為候選 `VN1-C-REGIME-RESOLVER`。
- 📌 2026-10-22（append-only）：市場位階／指標危險度／Risk Cap／台股趨勢四概念分開、同名不同義 regime 的對照見 §22.3（客戶要求不合併、不建綜合分數；DEC-071）。

## 12. 決策層候選構想（**一律 Candidate／Decision Gate，未核准**）

| 構想 | 現況與出處 |
|---|---|
| Shadow Mode | **程序要求已裁示**：正式加減碼比例須經「資料驗證 → 規則設計 → 回測／Shadow Mode → 客戶裁示」（DEC-053；D17）；Required Core 分類非永久、日後以校準／Shadow 證據回客戶裁示（DEC-048）。**Shadow Mode 本身的實作與結構＝Candidate**（`VN-31`；Blueprint §19） |
| Counterfactual evaluation | Candidate（`VN1-C-COUNTERFACTUAL`） |
| Hysteresis／persistence／cooldown | Candidate（`VN1-C-HYSTERESIS`） |
| Calendar context | Candidate（`VN1-C-CALENDAR`） |
| Data Quality SLO | Candidate（`VN1-C-DQ-SLO`） |
| Market Decision Snapshot | Candidate（`VN1-C-DECISION-SNAPSHOT`；相鄰 `VN-27` Decision Log） |
| Conflict Resolver | Candidate（`VN1-C-REGIME-RESOLVER`；相鄰 `AUD-C10` 方向相反無仲裁） |
| No-Action Zone | Candidate（`VN1-C-NO-ACTION`） |
| Action Engine | **邊界已裁示**：方向性 Action 有條件允許（DEC-054），但不是實作授權；`VN-09`／`VN-10` 是 DEC-056 的方向登記，引擎規格與狀態轉移規則仍待 Decision Gate（DEC-056 第 3 點；Blueprint §16） |

- **候選構想之間的關係（只是候選構想的關係，不是已定架構）**：Blueprint 的概念稿把 Shadow 結果與正式結果放在同一個 Decision Log 結構比較（Blueprint §19）；Counterfactual 與 Decision Review（`VN-29`）、前進式驗證（`CLAUDE.md` §2.3）相鄰；Conflict Resolver 處理 Regime 與其他訊號方向相反（`AUD-C10`）；No-Action Zone 併 Action 規格批評估。彼此的順序與介面**未定**。

## 13. Rule／Parameter versioning

- 已存在：`RISK_CAP_RULESET_VERSION`（`risk_cap.v2`）、`HISTORY_SCHEMA_VERSION`（`risk_cap_history.v1`）、`shared/fundamental_prescreen_thresholds.py::PRESCREEN_VERSION`；停用訊號保留歷史版本、不改寫歷史 Decision（DEC-049）；凍結 cohort 不改寫、方法版本切換須保留（DEC-050；D15）。
- 規則、資料、Thesis 的整體版本化：`VN-30`（open）。**參數（門檻）版本化的正式規則：GitHub 無定義來源。**

## 14. Derived dataset persistence 原則

- 可重建（程式＋外部源可重產）vs 不可重建（凍結快照、使用者資產）的刪除界線：`CLAUDE.md` §-1.5.F 判定 3(5)。`data_cache/forward_test/picks.parquet` 屬不可重建，GC 不得碰。
- Git repo 不當 production datastore（DEC-062 Q4）；系統歷史放系統 Sheet（DEC-063）；新 UI Risk Cap 獨立快照（DEC-052）。
- derived datasets 持久化 inventory：Candidate（`VN1-C-DERIVED-INVENTORY`）。

## 15. 自動資料來源 vs Proxy（代理值）

- **已有出處的部分**：代理值只顯示、不計分；停用項明示停用；沒有資料來源不得宣稱通過（DEC-062 Q5）。M1B 代理值只顯示不計分、裁決設有效期限（DEC-037；期限值未查）。官方只缺外資時不跨來源拼 FinMind（DEC-035；D16）。多源依權威分級與 fallback 順序取第一命中、禁止平均（`CLAUDE.md` §2.1）。新增或替換 production 來源屬 Decision Gate（`PROJECT_RULES.md` §4 #3）。
- ~~更廣的「自動來源 vs Proxy」原則：**GitHub 無定義來源；不得推測。**~~（注意：此處 Proxy 指代理值，不是 NAS 網路 proxy。）（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更正：B 組治理文件盤點指出本句已過時））
  **現行**：GitHub **已有**出處 —— `PROJECT_RULES.md` 16.1「proxy ≠ real data」（客戶 2026-10-23 Freeze §9 首句；後半句「代理值不得以正式資料的身分顯示或計分」屬撰寫組整理，Freeze §9 全文未入庫）、本檔 §29.3；客戶 2026-10-10〈資料品質、資料來源與公式正確性治理規則〉§六禁止「把 fallback 資料偽裝成主來源」（C 類，handoff 分支 `HANDOFF.md@1510f3f0:563-580`；main 落點 DEC-008 為摘要）。⚠️ 但 BIAS240 估算、PCR 法人估算、台灣 PMI 標記值「算不算代理值」及能否計分，**仍待** `PROXY-SEMANTICS` 裁示（DEC-077 3B；`docs/BACKLOG.md` `CV1-DR-11`；本檔 §31）。

## 16. cleanup／dead code／old UI 治理

- GC 是任務的收尾義務，不是找任務的理由；本次改動造成的孤兒才在本次清（`CLAUDE.md` §-1.5.F 判定 3；§-1）。
- New UI 是唯一主線；舊 UI 凍結、實體刪除屬不可逆操作，須客戶裁示（DEC-019、DEC-020；D1／D2）。死碼登記不動工（`PROJECT_RULES.md` §5；`CLAUDE.md` §8.2.A.2）。

## 17. 重要限制

- **workflow 須客戶手動觸發**：從 claude.ai 整合以 API dispatch workflow 會得到 403（DEC-063 狀態補註「代理觸發 403」），所有 run（dry-run、wif-auth-only、權限測試、production-write）都由客戶手動觸發。
- **pandas 3.1**：只修了測試（#899，`tests/test_batch_z2_nonfinite.py`）；`requirements.txt` 宣告 `pandas>=2.0.0,<4.0.0`，未排除 3.x；production 程式在 3.1 下的相容性**未稽核**（BACKLOG Candidate）。
- 沙箱跑不到 Streamlit Cloud 與真 Google 登入；部署端結果以客戶回報為準（`docs/HANDOFF.md` §6）。
- main 會被每日 cron 資料 commit 推進（`PROJECT_RULES.md` §2）。
- Claude Code session 內 `gh` 的 GraphQL 呼叫回 403，須改用 REST（2026-10-22 單一 session 觀察，可能隨環境變動，使用前重測）。

## 18. App-ready 方向（**研究方向，非已核准 refactor**）

- 客戶 2026-10-19 接手提示 §16 原話要點：「目前不替換 Streamlit。」保留 Python data／rules engine；長期 layering「資料層 → Rule／Decision Engine → API-ready → Streamlit／未來 App」；「PWA / Web App 優先於 Flutter / React Native / native。」未來安全點做「App-ready architecture audit」，「只 audit / research，不代表已核准 refactor」；「不得拿此方向中斷目前 1.0 工作」。
- BACKLOG 指標：`VN1-C-APP-READY-AUDIT`（Candidate）。

## 19. 已核准 vs Candidate／Decision Gate 的界線

- **Approved**：`docs/DECISIONS.md` 狀態「生效」的 DEC；`PROJECT_RULES.md` §13 D1～D19；`CLAUDE.md`。
- **Candidate／Decision Gate**：BACKLOG §4（`CV1-DR-*`／`CV1-RC-*`）、§5（`VN-*`）、5.1.5（`VN1-C-*`）、Blueprint 線框與 `BP-DR-*`。
- 登記不構成動工授權（`CLAUDE.md` §-1；DEC-002）；DEC-054／056／057 都不是實作授權。須停下問客戶的事項見 `PROJECT_RULES.md` §4。

## 20. GitHub 無定義來源（不得推測；待客戶提供或研究後經 Decision Gate）

- Market Direction v2（`VN1-C-MD-V2-AUDIT` 只有標題）。
- valuation／breadth／positioning／crowding 訊號的定位（Core／Context／不採用）。
- `published_at`／`available_at` 欄位契約。
  📌 2026-10-22 註：DEC-070 只裁示**語意**（盤後且 D 日必要台股資料均已正式可得；VIX 只用已完成收盤資料），**未定欄位契約**；本條仍成立。
- multi-Sheet 細節（UI 流程、資料模型、權限模型）。
- 期貨結算日規則。
- 「自動來源 vs Proxy」更廣原則；「Market State」定義；參數（門檻）版本化規則。
- 「台股趨勢」「國際趨勢」定義（2026-10-22 新增，append-only；DEC-071 第 5 點只定兩主軸名稱；本輪寫入前全 repo grep 0 命中；⛔ 不得與市場位階／指標危險度／Risk Cap 合併、不得成綜合分數；`VN1-MT-TREND-DEF`；見 §22）。
- 真實市場廣度（漲跌家數）的正式來源與可達性（2026-10-23 新增，append-only）：`daily_data_fetchers.fetch_adl` 註解稱 TWSE MI_INDEX 永久停用，但 sector_flow cron 2026-10-22 仍讀到 MI_INDEX，矛盾未查清；代理 ADL／旌旗是否續計分屬 Decision Gate `DH-GATE-BREADTH`（見 §25）。
- 資料健康狀態的判定規則與全站狀態列「N 項需處理」的計數口徑（2026-10-23 新增，append-only）：`docs/vnext/DATA_HEALTH_AUDIT_2026-10-23.md` 第 6、7 節只是**草案**；四類狀態的客戶原文定義見該檔第 2 節；`DH-DATA-CENTER`。

## 21. 治理入口（只列指標）

- 新對話啟動、優先序、Handoff Save Check、Context Loss Check：`PROJECT_RULES.md` §15（DEC-067、DEC-068）。
- 靜默自主巡航與回報格式：`PROJECT_RULES.md` §3（DEC-059、DEC-060）；客戶回報語言：DEC-069。
- Minimum Sufficient Effort 與階段邊界 Effort Check：`PROJECT_RULES.md` §9（DEC-059、DEC-061）。
- 額度／context 預判不足時的提前落盤（預判性 Safe Checkpoint）：`PROJECT_RULES.md` §11（DEC-079）。

## 22. 大盤／市場趨勢研究框架與 repo 對照（Research Framework，非 Approved）

> 2026-10-22 新增（客戶同日訊息；DEC-071）。量測：`origin/main`＝`08272e5`（#902；撰寫組 `git log` 實查），cron 會推進 tip，引用前重查。剩餘待辦只在 BACKLOG 5.1.6（`VN1-MT-*`）。

### 22.1 客戶 UI 方向（已確認；出處 DEC-071，本節只摘要）

- 新 UI 視覺方向維持；舊 UI 既有功能與判讀邏輯是新版重要參考、不因簡化而大量刪除；第一個主頁改以「大盤／市場趨勢」為核心（不再以「今天」）；導航後續重新命名（候選非 final）；市場趨勢研究只保留兩主軸：台股趨勢、國際趨勢；「大盤」字樣必須明確保留。
- ⛔ 不是動工授權、不取代 DEC-003 線框 gate、不授權修改或刪除舊 UI（DEC-019／020）。與 DEC-057「首頁不是 Dashboard」、DEC-062 Q1 今天頁的張力**未解決**（`VN1-MT-HOME`）；客戶用詞「今天／找標的／我的持股／我的」與 repo 現存兩套名稱（DEC-017 五頁、DEC-062 四格送審範圍）都不完全相同（`VN1-MT-NAV`）。

### 22.2 研究框架（**Research Framework，非 Approved、非 production rule**）

> 出處：客戶訊息 2026-10-22，經總管轉交；總管已逐字比對客戶訊息（撰寫組未見原件）。
> ⚠️ **以下是客戶提供的蕭碧燕老師資料，只保存研究框架**。repo 查無任何相關 Decision ⇒ 一律**不是** Approved production rule。客戶原文逐字：「以上屬 Research Framework；除非 repo 已有正式 Decision，否則不得寫成 Approved production rule。」
> ⛔ 客戶原文逐字：「不要建立新的綜合分數。」「尤其不要把：「市場位階」「指標危險度」「Risk Cap」「台股趨勢」四者合併成同一概念。」（見 22.3）。⛔ 歷史泡沫案例的數字**不得**成為門檻或 production threshold（客戶原文：「歷史泡沫案例只作研究比較，不直接變成永久 production threshold。」）。任何一項要變成正式判斷依據，須經 Decision Gate（DEC-009；`PROJECT_RULES.md` §4）。

**台股**（客戶原文逐條）
- 短期修正與長期趨勢應分開閱讀。
- 使用「EPS × PE」建立台股加權指數的情境估值矩陣。
- EPS × PE 是大盤估值方法之一，不代表完整的市場趨勢判斷。
- 外資籌碼是台股趨勢的重要觀察面向。
- AI／CSP 資本支出可透過台灣供應鏈企業獲利與 EPS 預期影響台股；同時也要保留資本支出過高、現金流下降的反面風險。

**國際**（客戶原文逐條）
- 研究框架會同時觀察長天期公債殖利率與景氣領先指標。
- 重點不只是絕對數值，也包括兩者的方向。
- 歷史泡沫案例只作研究比較，不直接變成永久 production threshold。
- 國際景氣／利率環境可透過企業投資、AI/CSP CAPEX、台灣企業獲利與 EPS 影響台股。

### 22.3 四個概念分開（客戶原文「尤其不要把：「市場位階」「指標危險度」「Risk Cap」「台股趨勢」四者合併成同一概念。」；現況以程式為準）

| 概念 | repo 現況（`檔案::符號`） | 問的是什麼 |
|---|---|---|
| **市場位階** | `src/services/allocation_service.py::get_macro_regime`（包 `macro_state_locker.get_macro_state`；仲裁 `shared/regime_arbiter.py::arbitrate_regime`；標籤 `shared/allocation_decision.py::REGIME_LABEL`） | 多空（SPEC.md §16.5） |
| **指標危險度** | 16 盞燈 `shared/macro_buckets.py::BUCKET_DANGER_SPECS`；`src/ui/tabs/tab_macro_v2.py::overall_verdict`（worst-of、不含多空） | 指標有多危險（不含方向）；與位階**並列**，SPEC §16.5「不平均、不取 worst、不合成第三顆燈」 |
| **Risk Cap** | `src/services/macro_state_locker.py::calculate_system_state`（risk_cap.v2；§4） | 建議持股上限 |
| **台股趨勢** | **無定義**（本輪寫入前全 repo 0 命中；`VN1-MT-TREND-DEF`）；原料候選（未定義前只是候選）＝`src/services/market_strategy.py::get_market_assessment`（MA5/60/120/200、MA120 斜率 → `mkt_info`）；⛔ `classify_long_term_regime` 同名不同義、易混淆，未經客戶定義不得當台股趨勢原料 | 待客戶定義 |

- **同名不同義的 regime（易混淆）**：`src/compute/macro/macro_helpers.py::classify_long_term_regime`（12M 長期位階，舊 UI；⛔ 未經客戶定義不得當台股趨勢原料）；`calculate_system_state` 輸出的 `market_regime`（Risk Cap 上限分級，§11）；另舊版 `src/ui/tabs/macro/section_cross_ai.py` 有自判的「目前總經位階」（獨立 QA 已讀原碼確認 `render_section_cross_ai` 渲染「① 目前總經位階」）。皆**不是**「市場位階」SSOT。
- ⚠️ `src/data/macro/leading_indicators.py` 是**籌碼先行指標**（期貨／PCR 等），**不是景氣領先指標**。

### 22.4 研究框架 → repo 對照（簡表）

| 研究框架 | repo 現有資料／規則 | 舊 UI | 新 UI | 缺口／分類（BACKLOG） |
|---|---|---|---|---|
| 短期修正 vs 長期趨勢 | `get_market_assessment`（均線、MA120 斜率）；`classify_long_term_regime`（12M，同名不同義、易混淆） | `get_market_assessment` 有；長期位階 `classify_long_term_regime` 只間接餵雙速合議卡（`section_long_term.py` 檔頭：UI 已移，保留 `_lt`） | 經 `macro_refresh_service` STEP_MARKET 間接用 `mkt_info`；長期位階未接 | 部分存在／已存在但新版漏接／需要 Decision Gate（切法未定義）→ `VN1-MT-TREND-DEF`、`VN1-MT-LEGACY-GAP` |
| EPS×PE 大盤情境估值 | 大盤層級不存在；EPS、本益比只在個股層；`risk_radar.synthesize_dual_verdict` 的 `valuation_level` 參數無人產生 | 無 | 無 | 缺資料／Research Candidate（大盤 EPS／PE 來源未定；新資料源＝Decision Gate）→ `VN1-MT-VALUATION` |
| 外資籌碼 | 現貨 `foreign_net` 燈、期貨 `fut_net` 燈（`leading_indicators.finmind_fut_oi`；Risk Cap 紅線三（外資期貨淨口＋跌破 MA5）的輸入之一）、`tw_macro.fetch_foreign_consecutive_days`、hot_money | 有 | 只經燈與 Risk Cap 間接；連買／hot_money／明細未接 | 已存在可重用（燈）／已存在但新版漏接 → `VN1-MT-LEGACY-GAP`、`VN1-MT-IA` |
| AI／CSP capex 傳導（含 capex 過高、現金流下降的反面風險） | 大盤層級不存在；`capex_intensity` 只在個股層；Blueprint `BP-RC-07`（AI CapEx 下修情境）、`BP-RC-08`（產業雷達 CapEx） | 無（大盤層） | 無 | Research Candidate／缺資料 → `VN1-MT-CAPEX-EPS` |
| 長天期公債殖利率：水位 | 16 燈 `us10y`（FRED DGS10 單點）；30Y 不存在 | 有（另 `risk_radar._signal_yield_10y_shock` 單日 bp 衝擊） | 有（16 燈） | 已存在可重用／缺資料（30Y）→ `VN1-MT-YIELD-CLI` |
| 長天期公債殖利率：方向 | 方向列刻意 mode none（`shared/lamp_direction_thresholds.py`；不混源 ^TNX）；中長期方向計算不存在 | ^TNX 走勢小圖（`section_long.py`，`cl_data['intl']`）＋`risk_radar._signal_yield_10y_shock` 單日 bp 衝擊 | 無 | Research Candidate／已存在但新版漏接（^TNX 走勢；與 DGS10 燈值不同源，⛔ 不得混源）／需要 Decision Gate（改方向規則或取數源）→ `VN1-MT-YIELD-CLI` |
| 景氣領先指標：水位與方向 | `tw_macro.py::fetch_ndc_leading_index`（mom／smooth6m／inflection／trend）；`shared/fred_series.py::FRED_CHN_OECD_CLI`（只中國、只水位）；美國／全球 CLI 不存在（`data_registry.py` 雖把 `HG=F` 標為「全球景氣領先指標」，但無 fetcher 抓取） | NDC（`section_state`）、中國 CLI 有 | 未接；相鄰：16 燈 `ism_pmi`（顯示名台灣 PMI）、`ndc_signal`（含方向列，`page_today.py::_session_ndc_series`）；兩者不等於景氣領先指標 | 已存在但新版漏接（NDC）／缺資料（美國／全球 CLI）→ `VN1-MT-YIELD-CLI`、`VN1-MT-LEGACY-GAP` |
| 殖利率×領先指標方向組合；歷史泡沫比較 | 不存在 | 無 | 無 | Research Candidate（案例只作研究比較，⛔ 不成門檻）→ `VN1-MT-YIELD-CLI` |
| 國際景氣／利率 → 企業投資 → 台股 EPS | 不存在（大盤 EPS 不存在） | 無 | 無 | Research Candidate／缺資料 → `VN1-MT-CAPEX-EPS`、`VN1-MT-VALUATION` |
| 定位：市場位階 | 22.3 | 有 | 有（位階卡） | 已存在可重用；⛔ 不與其他三者合併 → `VN1-MT-TREND-DEF` |
| 定位：指標危險度 | 22.3 | 有 | 有（危險度卡） | 已存在可重用；⛔ 不與其他三者合併 → `VN1-MT-TREND-DEF` |
| 定位：Risk Cap | 22.3、§4 | 有 | 有（建議持股卡） | 已存在可重用；⛔ 不與其他三者合併 → `VN1-MT-TREND-DEF` |
| 定位：台股趨勢／國際趨勢 | 無定義 | — | — | 需要 Decision Gate → `VN1-MT-TREND-DEF`；版面 → `VN1-MT-IA`（DEC-003） |

### 22.5 揭露（`CLAUDE.md` §-2 規則 6）

- 本節 mapping 由**兩組唯讀盤點＋總管抽查**（總管轉述）、撰寫組彙整並抽查部分符號（`PAGE_LABELS`、`fetch_ndc_leading_index`、`FRED_CHN_OECD_CLI`、`us10y` 方向列、「台股趨勢」0 命中、新 UI `src/ui/views/page_today.py` 只在註解提到 `classify_long_term_regime`）。
- 「不存在」「0 命中」「未接」類全稱句為 **grep 結果**，**未經第三組驗證**；只能當待驗事項，⛔ 不得作為實作批的前提（實作前須重查）。

## 23. 舊 UI＋既有引擎能力盤點（2026-10-23，對照新 UI）

> 2026-10-23 新增（總管指派「盤點結果接受、先落盤」；非客戶新裁示、⛔ 不是動工授權）。量測 2026-10-23：`origin/main`＝`d07bcfe9`（#904），cron 會推進 tip，引用前重查。剩餘待辦只在 BACKLOG 5.1.6（`VN1-MT-LEGACY-GAP`、`VN1-MT-SSOT-*`）。⚠️ 未窮舉、未經第三組驗證（見 23.5）。

### 23.1 能力總表

| 領域 | 已有能力與真正計算來源 | 新 UI 狀態 |
|---|---|---|
| 大盤綜合判讀 | 位階 `shared/regime_arbiter.arbitrate_regime` → `allocation_service.get_macro_regime`；16 燈 `shared/macro_buckets.BUCKET_DANGER_SPECS`；五桶 `macro_helpers.compute_five_bucket_summary`；總經健康分 `calc_traffic_light`（旌旗 0.6＋大盤評分 0.4） | 已接 |
| 指數技術趨勢 | `services/market_strategy.get_market_assessment`（MA5/60/120/200、連 3 日確認、MA120 斜率、量比、market_score）；指數 K 線 `macro_v2_service.get_twii_ohlc`；BIAS240 | `get_market_assessment` 只經 `mkt_info` 當輸入、畫面未呈現；K 線未接；BIAS240 已接 |
| 廣度 | `daily_data_fetchers.fetch_adl`（^TWII 推估，`is_proxy=True`）；真實家數 `tw_macro.fetch_twse_breadth`；旌旗 | ADL 推估已接；真實家數只舊 UI；旌旗已接 |
| 外資 | 現貨燈 `foreign_net`、期貨燈 `fut_net`；連續天數 `tw_macro.fetch_foreign_consecutive_days`；熱錢（計算在 L5 `src/ui/tabs/hot_money.py`） | 兩燈已接；連續天數、熱錢未接 |
| 融資融券／散戶／PCR | 融資燈；融券、韭菜、投信／自營、PCR 數值 | 融資燈已接；其餘未接（PCR 僅 Risk Cap Optional） |
| 總經單燈 | VIX、台灣 PMI、美國核心 CPI、10Y、DXY、出口、NDC 燈號；M1B/M2 | 已接；M1B/M2 顯示不計分（腿停用） |
| 景氣領先 | NDC 領先 `tw_macro.fetch_ndc_leading_index`；中國 CLI 與中國 regime（`tw_macro.fetch_china_macro`、`classify_china_regime`） | 未接 |
| 國際 | 總經指南針 `macro_core.fetch_macro_compass`；全球風險雷達 `risk_radar.detect_risk_radar`（9 燈）；跨資產資金流 `compute/macro/flow_engine`；國際指數 `daily_checklist.INTL_MAP/TECH_MAP`（資料經 refresh 抓進） | 表格未呈現 |
| Risk Cap | `calculate_system_state`＋三條 Hard Veto；`get_allocation` | 已接 |
| 個股選股（page_find） | `fundamental_screener_service.get_ranked_picks/build_trend_map`、shortage、rs_leader、pe_low、空頭濾網、sector_flow、sector_heatmap | 已接 |
| 個股判讀（page_inspect） | 財報體檢、357、20 日籌碼＋異常值、ETF 折溢價／配息／同儕／品質 | 已接；⚠️「健康度」卡是財報體檢分，與舊 UI 技術健康 6 因子 `scoring_helpers.calc_health_score` **同名不同義** |
| 個股技術與策略 | 6 因子技術健康、RSI、KD（`fetch_metrics` 已算 `kd_state`；持股評估 `assess_stock` 有讀，`page_inspect` 畫面未呈現）、MACD、量比、VPOC、VCP、布林／squeeze、軋空、RS 分數、多因子評級 `score_single_stock`、統一判決、乖離過熱、型態目標價、15 項深篩（L5 `tab_stock_picker._check_*`，舊 UI 多檔比較仍用）、出場訊號、風報比／部位 | 未接（page_why AI 問答工具可間接呼叫 `get_stock_score`／`get_risk_plan`／`get_financial_health`） |
| 個股籌碼明細 | 集保大戶、個股融資融券、V4 相對籌碼 | 未接 |
| ETF | 配息站、壓測、VaR、配息現金流；7 維評分、留／觀察／換、智慧選 ETF、效率前緣、重疊度、股債一致性、ETF 明細七段 | 前四項已接；其餘未接 |
| 持股風控 | 燈牆、80/20、停利、換股；風險貢獻、產業集中度、組合限額／停損；觀察清單 | 燈牆／80/20／停利／換股已接；風險貢獻、集中度、組合限額／停損未接；觀察清單讀取已接、寫入未接 |
| 訊號推播（不在 UI） | 持股每日推播、週報；每日選股、觀察清單推播 | 前兩者有排程；後兩者排程已停（只看 yml） |
| 歷史快照 | macro_history、sector_flow、`risk_cap_state.json`、校準；前進式驗證 `picks.parquet`；總經前進式驗證；Risk Cap History Sheet | 前四者已接；`picks.parquet` 未接；總經前進式驗證只寫不讀；History Sheet 只 PoC |

- **名詞**：`src/ui_v2/` 是新 UI 引用的版面契約／卡面函式庫（`app_today.py`、`render.py` 為獨立預覽原型），**不是另一套 UI**。「v2」有三種指涉：`tab_macro_v2.py`（舊 UI 總經分頁）／`src/ui_v2/`（卡面函式庫）／IA v2 `src/ui/views/`（新 UI View 層）。

### 23.2 舊能力 → 新四頁候選 mapping

> ⚠️ 新四頁「📊 大盤趨勢／🎯 標的雷達／⚡ 交易行動／🛡️ 持股防護」是**客戶候選、非最終導航裁示**；DEC-017 五頁仍生效（`VN1-MT-NAV`）。⛔ 不是動工授權；版面變動須先出線框（DEC-003）。

| 候選頁 | 舊能力 |
|---|---|
| 📊 大盤趨勢 | 位階、危險度、Risk Cap（三張並列不合併）、指數技術趨勢、K 線、廣度、外資、融資融券、韭菜、PCR、NDC 領先、國際指數、指南針、風險雷達、資金流、板塊潮汐 |
| 🎯 標的雷達 | 選股網、熱力圖、個股技術／籌碼／估值／財報、ETF 7 維與智慧選、深篩 |
| ⚡ 交易行動 | 出場訊號、風報比／部位、型態目標價、換股、停利、80/20 |
| 🛡️ 持股防護 | 燈牆、壓測、VaR、配息現金流、風險貢獻、集中度、組合限額；Risk Cap 天花板僅 presentation |
| 無位置 | 憑什麼（教學、資料體檢、AI 問答）、「我的」頁 |

- **原則**：同一能力多頁引用時只有**一處 SSOT 計算**，其餘頁只做 presentation，⛔ 不得複製第二套。

### 23.3 真正缺口三類

1. **已有未接**：見 BACKLOG `VN1-MT-LEGACY-GAP`（23.1「未接」各列）。
2. **部分存在需整理**：見 BACKLOG 5.1.6 `VN1-MT-SSOT-*` 各條（ATR 停損、fakeout、時間停損、MA5/MA100、持股水位、ADL 標示、ISM PMI 錯置、總經前進式驗證、文件／教學無資料流）。
3. **真正沒有**：大盤 EPS×PE、大盤 forward EPS、大盤本益比、AI／CSP CAPEX、TIPS（`calc_real_rate` 是政策利率−CPI、非 TIPS，且無 production caller）、美 2Y／10Y−2Y／10Y−3M、30Y、台灣／美國／全球 OECD CLI、借券、Sahm 資料 → 一律 **Research Candidate／缺資料**，⛔ 不得升格 Approved。

### 23.4 台股趨勢／國際趨勢現有原料

| 主軸 | 已有資料 | 已有規則 | 缺資料 | 缺定義 |
|---|---|---|---|---|
| 台股 | ^TWII 多年日線、BIAS240、廣度（推估＋真實）、旌旗、外資現貨／期貨、融資融券、PCR、USDTWD、NDC 燈號／領先、台灣 PMI、出口、板塊潮汐 | `market_strategy`、位階仲裁、16 燈門檻 | 大盤 EPS×PE、forward EPS、CAPEX | 台股趨勢本身（`VN1-MT-TREND-DEF`） |
| 國際 | ^GSPC／^DJI／^IXIC／^SOX、科技權值股、VIX／VIX3M、FRED DGS10 與 ^TNX（⛔ 不同源不得混源）、DXY、美核心 CPI、Fed Funds、HY OAS、MOVE、區域／跨資產 ETF、中國 CLI | 風險雷達、`flow_engine` z-score、10Y／DXY 燈 | 2Y／利差、30Y、TIPS、美／全球 CLI、美 ISM（`macro_core.fetch_ism_pmi` 有 fetcher 無 caller） | 國際趨勢本身、殖利率×領先方向規則 |

- ⛔ 四概念（市場位階／指標危險度／Risk Cap／台股趨勢）**分離、不得合併、不建綜合分數**（§22.3；DEC-071）。

### 23.5 揭露（`CLAUDE.md` §-2 規則 6）

- 方法：四組唯讀盤點＋兩組獨立稽核讀原碼抽驗後修正（總管轉述）；撰寫組只彙整，**未逐項重查**。
- **未窮舉**：「已接／未接」以 grep `src/ui/views` 為準，**未追動態 import**；「0 讀取」「無 caller」「無 fetcher」類全稱句為 grep 結果。
- 第二輪修正**未經第三組驗證** ⇒ 本節只能當待驗事項，⛔ 不得作為實作批的前提（實作前須重查）。

## 24. 產品方向：底層完整、前台極簡（DEC-072）

> 2026-10-23 新增（客戶同日訊息；裁示全文與「與其他 DEC 的關係」只在 `docs/DECISIONS.md` DEC-072，本節只摘要）。剩餘待辦見 BACKLOG 5.1.6（`VN1-MT-NAV`、`VN1-MT-HOME`）、5.1.2 `BP-DR-01`、5.1.7 `DH-DATA-CENTER`。

- 客戶原文：「目前方向是「底層能力完整，前台流程極簡」。」狀態＝產品方向（**暫定**）；⛔ 未核准線框、⛔ 非動工授權。
- 投資主流程暫定四頁（各頁回答一個問題，客戶原文）：
  - 📊 大盤 —「現在適合承擔多少風險？」台股趨勢、國際趨勢、Risk Cap、重要警示；首屏先給結論與少數關鍵原因，詳細指標 progressive disclosure。
  - 🎯 標的 —「現在有哪些值得看的？」「找標的＋查一檔」整合為同一主頁，點選標的直接進同一流程的詳細健檢；底層能力保留、不製造大量頁面層級。
  - ⚡ 行動 —「現在有什麼需要處理？」僅盤點既有 deterministic action 能力；不新增未核准的買賣語意、加減碼比例或新投資規則。
  - 🛡️ 持股 —「我的投資組合健康嗎？」持股健檢、曝險、集中度、風險、壓測等。
- 輔助入口：👤 我的（帳戶／設定）；🩺 資料中心（資料維護與健康狀態，不屬主要投資流程）。「憑什麼」轉為各頁 contextual explainability，不作主要導航。主 UI 只放簡單全站狀態（例「🩺 資料健康：🟡｜3 項需處理」），點擊才進資料中心（規格草案見 §25）。
- **現行仍照舊**：DEC-017 五頁（`shared/ia_nav.py::PAGE_LABELS`）在新線框經 DEC-003 拍板前仍為現行實作依據；DEC-062 Q1 四格送審範圍待依新方向調整（原條不刪）；舊 UI 不改不刪（DEC-019／020）。
- ⛔ 第 1 點同列「台股趨勢、國際趨勢、Risk Cap」不代表合併；四概念分開（§22.3）。「台股趨勢」「國際趨勢」仍無定義（§20、`VN1-MT-TREND-DEF`）。
- §23.2 的候選頁名（📊 大盤趨勢／🎯 標的雷達／⚡ 交易行動／🛡️ 持股防護）是盤點時的候選；客戶較新用詞見本節，仍非 final（`VN1-MT-NAV`）。

## 25. Data Health Audit 摘要（2026-10-23）

> 2026-10-23 新增。全表、方法、未驗證事項只在 `docs/vnext/DATA_HEALTH_AUDIT_2026-10-23.md`；待辦只在 BACKLOG 5.1.7（`DH-*`）。本節不複製全表。量測：`origin/main`＝`1bfca551`（#905），cron 會推進 tip，引用前重查。

- **方法與限制**：四組領域／橫向唯讀稽核＋兩組獨立複驗讀原碼並重現（總管轉述）；沙箱無網路，「最新資料日」只量本地 `data_cache/`，⛔ 非 production 值；FinMind API 403、未實測。
- **統計**（該檔第 3 節表格列數，腳本計數）：🟢 HEALTHY 7／🟡 LIMITED 25／🔴 BROKEN／MISLEADING 27／⬜ UNAVAILABLE 5（合計 64 列；一列可能合併數個相近資料）。依客戶原文「禁止把 missing 當 0、neutral、false 或正常。」，補 0、回中性、ffill 當現價、代理／估算值計分一律判 🔴。
- **重大問題**（會讓目前投資結論不可信）：
  1. 市場位階與建議持股姿態帶受代理廣度主導（近似常數、落後一日）；代理值計分本身已不符 DEC-062 Q5「代理值只顯示、不計分」（BIAS240、PCR 估算同類：`DH-BIAS240-EST`、`DH-PCR-PROXY`）。待裁示的是移除代理廣度後健康分怎麼辦 → Decision Gate `DH-GATE-BREADTH`：(A) 重新歸一為只含大盤評分並揭露「廣度未評估」（總管推薦；需另批重新校準或揭露未校準）／(B) 健康分判「未評估」、位階與姿態帶不給結論。
     📌 2026-10-23（append-only，上句一字未改）：**已裁示 B（DEC-074）**：代理廣度不得計分；受 breadth 影響且無法依既有正式規則可靠計算的健康分 →「⬜ 未評估／資料不足」；不重新設計 0.6／0.4、不重新正規化、不為「有結論」補結論；總管推薦 A ⛔ 不採用。~~⛔ 實作待客戶指派。~~ **實作完成、待 PR #910 合併**（DEC-075 指派批 A；見 §28）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新：DEC-075 已指派，批 A＋1' 已於分支實作））。
  2. Risk Cap 核心輸入 VIX、MA5 的 PIT 未實作，新 UI 的 `risk_cap_state.json` 仍判 VALID（正式 Sheet 寫入已關）→ `VN1-PG-VIX-ASOF`、`VN1-PG-PIT-CONSISTENCY`。
  3. 刷新失敗沿用舊值而無揭露 → `DH-REFRESH-STALE`。
  4. 個股／ETF：357 配息欄位、財報體檢現金流未年化、法人與融資融券補 0、未還原價無旗標、月營收記 0 分、評分例外回中性 50、ETF 尾端 ffill 當現價 → `DH-357-DIV-FIELD`、`DH-FIN-HEALTH-CF`、`DH-INST-FILL0`、`DH-KLINE-ADJ`、`DH-REVENUE-ZERO`、`DH-SCORE-NEUTRAL50`、`DH-ETF-FFILL`。
  5. 前進式驗證對帳口徑不一（影響「選股是否贏 0050」）→ `DH-FWD-RECON`。
- 「真正沒有資料來源」與「repo 有、新版沒接」分列於該檔第 4 節（後者完整清單見 §23）；⛔ 研究候選不得升格、四概念不合併、缺資料不得補值或當中性。
- 資料中心 schema 與全站狀態列只是**規格草案**（該檔第 6、7 節；`DH-DATA-CENTER`），⛔ 未實作，畫面須先出線框（DEC-003）。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：稽核內容為總管轉述，撰寫組只抽查部分符號存在；「0 caller」類為 grep 結果、未經第三組驗證，⛔ 不得作為實作批的前提（實作前須重查）。

## 26. Minimum Sufficient Model／Effort Gate（DEC-073，2026-10-23）

> 2026-10-23 新增。規則本文只在 `PROJECT_RULES.md` 第 9.0 節（另見第 3、15 節）；客戶原文全文只在 `docs/DECISIONS.md` DEC-073。本節只是摘要，⛔ 不是規範來源。

- 每個下一完整工作階段／Batch 開始前，必判**模型／能力等級＋Minimum Sufficient Effort**（Low／Medium／High；分級見 9.1）。
- 目前設定**低於**所需 → 立即停手、不硬做、不假設已切換、不降低問題複雜度繞過；回報建議模型／Effort、不足原因、切換後工作，等客戶確認已切換。這是 Silent Autonomous Cruise 的正式例外。
- 目前設定**高於**所需 → 不需為形式要求降級（修訂 DEC-059／DEC-061 的降級主動提醒）。
- 新對話啟動與每階段前都執行 Gate；`docs/HANDOFF.md` 第 0 節記錄下一階段建議模型／Effort（僅供參考，須重新判斷）。

## 27. Data Health 修復計畫提案（2026-10-23；DEC-074 B 落地＋其餘 🔴 分批）

> 2026-10-23 新增。全文只在 `docs/vnext/DATA_HEALTH_REPAIR_PLAN_2026-10-23.md`（**提案**，⛔ 非 Approved、⛔ 非動工授權、範圍待客戶裁示 DR-2026-10-23-3）；待辦與 Decision Gate 只在 BACKLOG 5.1.7（`DH-*`、`DH-GATE-REGIME-FALLBACK`）。本節不複製全表。量測：分支 `ccr-310717b7-37xwl6`，工作樹 HEAD `1196bb7f`（merge of main `50411d33`）。

- **來源**：三組唯讀（A 組 DEC-074 B 落地踩點、B 組其餘 🔴 分批、QA 獨立稽核）；**QA 的 REFUTED／MUST 凌駕前兩組**，已全部套用（MUST-A1 `_wr_ok`／#11 可達性、MUST-B1 `MISSING_STALE` 缺值原因對映、MUST-B2 `DH-FIN-HEALTH-CF`(a) 是公式變更、MUST-B3 `DH-TWII-MA200` 無新 UI 讀者、MUST-D1 五桶側車撞批 A）。三組皆單組，未經第三組驗證（`CLAUDE.md` §-2 規則 6）。
- **批 A（DEC-074 B 落地；Effort High，QA CONFIRMED）**：L0 旗標 `BREADTH_PROXY_SCORING_ENABLED=False`＋`shared/macro_provenance` 三支純函式（鏡像 M1B 先例 DEC-037）；L3 `jingqi_calc`／`market_assessment_apply` 入口剝離（`is_proxy` 第 8 鍵、`ad_ratio_is_proxy`）；L2 `calc_traffic_light` 缺旌旗 ⇒ health None（⛔ 不歸一；QA A2 CONFIRMED 現況即重新歸一＝DEC-074 排除路徑）；新 source `SOURCE_UNEVALUATED_BREADTH`＋不指引重抓的文案；五桶 jingqi／adl 兩盞灰不進桶；`compute_ruleset_hash` 加旗標；`DH-TWII-MA200` 併入（同函式 `get_market_assessment`）。不需線框（修正錯誤）；⚠️ 若出現新增卡／列、移除區塊、拿掉五桶盞 → 須先線框。
- **D-1 Decision Gate `DH-GATE-REGIME-FALLBACK`（送題中）**：健康分因缺真實廣度而 ⬜ 時，市場位階是否也一併 ⬜（總管推薦 (a)）、還是退 `macro_state.json` 規則引擎位階 (b)。QA MUST-A1：現況 health None 時 `get_macro_state._wr_ok` 不讀 warroom `regime_source`，(a) 需改該守衛語意（C1 v19.182）；(b) 下計畫 #11 不可達。⛔ 裁示前不得實作。D-2～D-4 內部拍板。
- **其餘 🔴 分批**：批 1'（Medium，可選加掛）＝`DH-FOREIGN-FILL0`（⚠️ 新 UI 畫面不變）／`DH-EXPORT-LABEL`（一句業務確認：訂單 vs 金額，推薦改名不換源）／ISM 教學 key（Low）；`DH-LAMP-STALE`(a) 排批 A 之後；批 2（High，併 `VN1-PG-*`）＝`DH-BIAS240-EST`／`DH-PCR-PROXY`／`DH-MACRO-FWD-ASOF`／`DH-REFRESH-STALE`；批 3（High，L1 契約）＝`DH-357-DIV-FIELD`／`DH-KLINE-ADJ`／`DH-INST-FILL0`（QA：`calc_chip_score` 遇 NaN 靜默回 40／0 分，非 NaN 傳播）／`DH-ETF-FFILL`（`page_hold` 只經 L3 間接用）／`DH-REVENUE-ZERO`／`DH-FIN-HEALTH-CF`(a)；批 4 延後＝`DH-SCORE-NEUTRAL50`（總分函式是 `stock_score`，repo 無 `calc_total_score`）／`DH-FWD-RECON`／`DH-FIN-HEALTH-CF`(b)／`DH-WHY-FRED-LAMP`；不排批＝舊 UI 凍結類、研究候選、`DH-DOC-VIX-CBOE` 文件批、`DH-HEALTH-HISTORY` 送題（推薦不啟用）、`DH-DATA-CENTER` 線框。
- **總管推薦範圍**：只做批 A（D-1 裁示後）；批 1' 可選加掛；其餘依序。客戶只需答：D-1 (a)/(b)、是否指派批 A、要不要加掛批 1'、批 2 是否併 `VN1-PG` 實作批。
- **`ruleset_hash` 二次切換風險**（QA D 表）：批 A 加旗標翻一次，`DH-MACRO-FWD-ASOF` 的 schema bump（payload 含 `'schema'`）再翻一次 ⇒ 三段不可混比。建議批 A 一併 bump schema 並納入 per-leg as_of 加欄（前提：`fetch_adl` off-by-one 同批定案）；否則 PR 明寫三段區間。
  - 📌 **2026-10-24 C1 後註記（append-only；上句一字未改；有意識的更新，不是漏刪，決策者 撰寫組判讀、AI 總管確認（2026-10-24））**：C1（#913，`DH-C1-FWD-LEG-ASOF`）以**純新增四欄**落地 ⇒ 依 `shared/macro_forward_test_schema.py` 規則「純新增欄不必動」**不 bump**（schema 維持 3、`ruleset_hash` 不變 `6c716f5411fb`），C1 **未產生**第二切換點；「改 `inputs_as_of` 語意（修 `fetch_adl` 差一日）」那半仍未授權，若日後做**仍須 +1**。見 **§30.9**。
- ⚠️ 揭露：撰寫組未實跑任何測試、只 grep 抽查關鍵符號存在；計畫內「0 讀者／唯一」皆 grep；預期紅測試清單未實跑；實作批開工前須重查（該檔第 0.3 節）。
- 📌 **2026-10-23 客戶裁示結果（DEC-075；append-only，上文一字未改）**：(1) **D-1＝(a)** —— 健康分因缺少正式 breadth 而未評估時，受此資料契約影響、無法可靠成立的市場位階也顯示「⬜ 未評估／資料不足」；不允許靜默 fallback 到另一套規則引擎產生位階結論；缺資料不得為了維持畫面結論而補結論（(b) 不採用）。(2) **指派批 A**（#908 合併後為下一批；含 DEC-074 B 落地＋`DH-TWII-MA200`）。(3) **同意加掛批 1'**（外資缺值不得補 0／台灣出口燈依實際資料內容修正名稱／修正 ISM 教學對映；⛔ 不得藉此新增資料來源或改變投資公式）。(4) **批 2 暫不與 VN1-PG 一起指派**：等批 A＋1' 完成、獨立 QA、CI、main verification 後重評邊界。⇒ 本節開頭「⛔ 非 Approved、⛔ 非動工授權」**對批 A＋1' 自本日起不再成立**（有意識的變更，不是漏刪，決策者 客戶）；批 2～4、`DH-LAMP-STALE` 仍為提案。批 A High，開工前依 DEC-073 Gate 自判（總管判目前模型足夠；總管自判，撰寫組無法查證）。⛔ 畫面結構異動仍受 DEC-003 線框 gate（計畫 1.6）；⛔ DEC-019 舊 UI 凍結不豁免。(a) 技術落點：`macro_state_locker.get_macro_state` 於 health None 時不退檔案位階、位階→未評估、`is_loaded=False`（`_wr_ok` 守衛語意改；相關測試斷言更新）—— 詳 DEC-075。
- 📌 **2026-10-23 第二則（append-only，上文一字未改）**：批 A＋1' **已於分支 `ccr-310717b7-37xwl6` 實作完成、~~待 PR #910 合併~~ 已合併 #910（merge `066f461e`）（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**；實作內容、客戶可見行為變更與已知殘留見 **§28**。

## 28. Data Health 批 A＋1' 實作完成（2026-10-23；~~待 PR 合併~~ 已合併 #910，merge `066f461e`（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））

> 2026-10-23 新增。裁示全文只在 `docs/DECISIONS.md` DEC-074／DEC-075；殘留與延後項只在 BACKLOG 5.1.8；現況與唯一下一步只在 `docs/HANDOFF.md` §0。本節只摘要。量測：分支 `ccr-310717b7-37xwl6`，HEAD `04a9bc2e`（commits `1f4f5b19`、`7ef52869`、`ee4bde01`、`04a9bc2e`；base＝main `b9ed892d`）。~~**PR 尚未開、尚未合併**~~ **PR 已開、尚未合併**（PR #910）；~~QA 第四輪複驗中~~ QA-1～QA-5 獨立複驗，QA-5 判定可合併（見 PR #910）（QA-5 後補的 SHOULD-1 測試 commit 為實作組自跑、未經第二組驗證）；CI：合併條件：PR #910 CI 綠（結果見 PR checks）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管）。

- **狀態**：~~**實作完成、待 PR #910 合併**~~ **已合併 #910（2026-10-24 squash，merge `066f461e`；最後產品碼 commit `9714d0b3`）**（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。⛔ 合併＋main CI＋main verification 完成前不得寫成「已上線」（📌 2026-10-24：合併＋main CI＋main verification **已成立**（main `066f461e` PR Check run 39995254045 success；`649f739` run 39999485112 success；`PROJECT_RULES.md` 第 7 節）⇒ 可寫「已上線 main」（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））；⛔ 總管確認前不得寫「QA 通過」。
- **批 A（DEC-074 B 落地＋DEC-075 D-1(a)＋`DH-TWII-MA200`）**：
  - L0 旗標 `BREADTH_PROXY_SCORING_ENABLED=False`（`shared/signal_thresholds`）：代理廣度（`fetch_adl` 由 ^TWII 估算、`jingqi_calc` 大盤估算）**只顯示、不計分**；健康分算不出 ⇒「⬜ 未評估」；**無新權重、無重新歸一化**（DEC-074）。
  - 健康分因缺正式 breadth 未評估時，市場位階 ⬜、`is_loaded=False`、**不退** `macro_state.json` 規則引擎位階 ~~；含 ^TWII 全滅情境（`04a9bc2e` 補）~~；~~**限 warroom 存在的路徑**（含該路徑下的 ^TWII 全滅情境，`04a9bc2e` 補）；**冷啟動／warroom 不存在路徑未完成（見 `DH-REGIME-NOWARROOM`）**~~ **代理廣度不計分時涵蓋 warroom 存在（含 ^TWII 全滅，`04a9bc2e`）與不存在（冷啟動未載入、warroom 被移除；PR #910 `DH-REGIME-NOWARROOM`）兩條路徑**（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））（⚠️ 實作組自述、待 QA 複驗（`CLAUDE.md` §-2 規則 6））（DEC-075 D-1(a)）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-4 M-1：D-1(a) 只完成 warroom 存在的路徑））。
  - `DH-TWII-MA200`：MA200 不足 200 根時回 None＋`ma200_status`，不再以現價頂替；`MA200_WINDOW_DAYS=200` 移入 L0（與 `config.ANNUAL_MA=240` 是不同量測，不合併）。
  - 總經前進式驗證：`ruleset_hash` 納入旗標、schema 2→3；**v2 列與 v3 列不可混比**（健康分口徑不同）。
- **批 1'**：外資（大盤）FinMind 備援缺值不再 `fillna(0)`；台灣出口燈改名「台灣出口金額 YoY（海關）」（不換源）；台灣 PMI 教學對映改 TW_PMI（歷史數字來自 `data_cache/tw_pmi.parquet`）；`XTEXVA01TWM664S` 教學文字依實際來源鏈 DGBAS → OECD via FRED → 海關 6053 更正；`SPEC.md`／`DATASTATION.md` 以刪除線＋DEC-075 註記同步。⛔ 未新增資料來源、未改投資公式（DEC-075 第 3 點）。
- **客戶可見行為變更**（在正式 breadth 來源出現前持續有效）：
  1. 📊 大盤／🛡️ 持股等處的**健康分、市場位階、建議持股姿態帶通常顯示「⬜ 未評估／資料不足」**（DEC-072「首屏先給結論」在資料不足時以 DEC-074／075 為準，客戶送題時已知情）。~~「通常」而非「一律」：warroom 不存在的路徑仍有殘留（見下）。~~ 「通常」而非「一律」：旗標開啟（代理計分）或日後接上正式廣度來源時不成立；warroom 不存在路徑的殘留已併入本 PR 修正（見下第 6 項）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））。
  2. 🎯 找標的頁（`page_find`）**空頭濾網通常不套用**（位階未評估 ⇒ 不套用）；⚠️ 目前畫面**沒有**註記告知使用者（`DH-FIND-UNEVAL-NOTE`）。
  3. 總經前進式驗證帳本：**健康欄為 None**；`ruleset_hash` 與 schema（2→3）變更，前後列不可混比。
  4. 台灣出口燈名改為「台灣出口金額 YoY（海關）」（待客戶驗收，`DH-EXPORT-LABEL-READING`）；台灣 PMI 燈的教學與歷史數字改為台灣 PMI（不再是美國 ISM）。
  5. 外資備援缺值時顯示為缺值、不再顯示假的 0 淨額（主要在舊 UI；新 UI 畫面不變）。
  6. 📌 **冷啟動（`DH-REGIME-NOWARROOM`，PR #910；2026-10-23 新增，有意識的更新，決策者 AI 總管）**：開新 session、尚未按「🚀 更新今日戰情」時（或更新時紅綠燈三源全空、warroom 被移除時），**不再顯示**由規則引擎快照 `macro_state.json` 推出的多空位階 —— 改為灰色「總經尚未載入」，並同句說明「正式廣度來源接上前，載入後位階仍為未評估」。具體：🚦 今天頁卡①③、狀態列「總經」、三欄摘要「位階」為灰色未載入（不是紅色錯誤）；~~🛡️ 持股頁卡④ **不再印 `bull`／`bear`**（灰）；~~ 🛡️ 持股頁卡④ 不再印 `bull`／`bear`，顯示灰色「總經本輪未評估」（⚠️ **QA-6 發現**：`c8e30d84` 時這張卡在 v2 卡面實際畫成**紅卡**「這一格畫不出來」—— 短句表 `V2_SHORT_ROWS` 的摘錄對不上新原文 ⇒ KeyError；卡⑤「建議持股水位」缺真實廣度那一支同型（`f3dd098c` 起即有）。修正 commit 後 AppTest 實測（旗標關、有效空頭檔、按「🚀 跑存股戰情室」）卡④ 為灰（#7），實作組自述、待 QA-7）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-6 MUST-1／S-2））；換股建議攻守 stance 冷啟動為「未評估」（只做汰弱、不套攻守）；🎯 找標的頁冷啟動不套空頭濾網；AI 多因子評分冷啟動拒評、AI 問答「市場狀態」回未評估。**系統風險上限（Risk Cap）不受影響**（7 天有效快照照舊）。**舊 UI 連帶**（共用契約，舊 UI 程式碼未改；DEC-019 揭露）：`app.py` 選股網濾網、`section_batch_fetcher`／`section_portfolio_summary` 評分、`section_op_recommendation`、`section_psy_checklist`、`macro_stock_link`、`tab_macro_v2` 等在冷啟動同樣變 unknown／未評估（走各自既有的未評估處理）。旗標開啟時行為同修前。⚠️ 實作組自述、待 QA 複驗（`CLAUDE.md` §-2 規則 6）
  7. 📌 **QA-6 補揭露（S-4；2026-10-23 新增，有意識的更新，決策者 AI 總管；數字為 QA-6 量測轉述，實作組未重跑）**：冷啟動自 #910 起還有兩處**方向變化**（都走各自既有的未評估路徑，屬實，但修前沒寫出）：(a) 舊 UI `section_op_recommendation`（凍結，DEC-019）冷啟動＋有效**空頭**檔：修前印「大盤空頭格局…先控制風險」，修後「大盤」項不計分（附既有 caption），結論可能變成「2個訊號共振，中性偏多，可小倉試水溫」—— **建議方向由保守轉為偏積極**；(b) 換股建議：修前空頭檔冷啟動攻守 stance＝defensive、換入候選 **3 檔**；修後 stance＝unknown（只做汰弱、不套攻守）、換入候選 **5 檔**（既有 `_in_n = 3 if _defense else 5`）。另：AI 個股評分冷啟動被擋時的字串（`ai_qa_service._regime_blocked_error`）不再附「按一鍵更新…再問一次」，改為屬實句「可以按更新載入，但正式廣度來源接上前載入後位階仍為未評估」（QA-6 MUST-2 修正；旗標開時舊句照舊）。⚠️ 實作組自述、待 QA-7 複驗（`CLAUDE.md` §-2 規則 6）
- **附帶行為變更（QA-4 S-2 揭露；2026-10-23 補，有意識的更新，決策者 AI 總管；`04a9bc2e` commit 訊息只寫了第 3 項）**：
  1. 🛡️ 持股頁 ④ 總經位階／⑤ 建議持股水位：warroom **存在**、健康分缺、舊 `macro_state.json` 讀壞時，由紅（讀不出來）轉灰（缺真實廣度 ⇒ 未評估）。這兩卡在 warroom 存在時本不讀舊檔（位階不靠舊檔、上限只讀 `risk_cap_state.json`），原本的紅屬假警報（v3 §02）；warroom **不存在**時讀壞**仍紅**（未改）。
  2. 🚦 今天頁卡① 能不能出手、卡③ 市場位階：F1（三源全滅、warroom 仍存在）／F3（^TWII 全滅）由「按更新會原地重抓」（灰）改為「更新資料不會改變、等正式廣度來源」（灰）；兩卡過去就不是紅，沒有紅色被拿掉；本輪取數失敗仍在更新報告逐條列出。
  3. strict 模式：warroom 有、但健康分缺＋舊檔損毀時**不再 raise**（rvrc 關時改帶 `file_error`、rvrc 開時不帶）；warroom 不存在＋損毀**仍 raise**。
  4. 本 PR（QA-4 S-1 回修）：新 UI 廣度未評估說明（今天頁卡①③／狀態列「總經」／三欄摘要「位階」、持股頁④⑤、AI 問答「市場狀態」工具）依「本輪紅綠燈輸入有沒有被擋下的代理值」給「目前只有代理值」或「這一輪連代理值也沒有」；拿不到區分訊號處（`allocation_decision` drivers、訊號讀不出來）改用兩種情境都屬實的中性句；今天頁／持股頁的出口句改為兩態皆屬實。更新報告「整理紅綠燈結論」步驟說明：旗標關時 warroom 在而健康分缺，一律寫缺真實廣度句（不再寫「位階若有可用的 macro_state.json 會改讀它」）。只改文案與選擇邏輯：⛔ 未增刪 st 元件、未改版面／公式／權重／門檻／Risk Cap、未動凍結舊 UI。
- **已知殘留**（登記於 BACKLOG 5.1.8，⛔ 不在此重複細節）：~~`DH-REGIME-NOWARROOM`（D-1(a) 殘留：warroom 不存在路徑仍回規則引擎位階、`is_loaded=True`；**下一安全段落第一個動作**）~~ `DH-REGIME-NOWARROOM` 本 PR #910 修正（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））、`DH-STATUSBAR-AI-SNAPSHOT-WORDING`、`DH-NOWR-COPY-RESIDUAL`（2026-10-23 新增登記）、`DH-CALIB-CRON`（季度校準在新旗標下健康恆 None、自動 PR 本文「無需調整」有誤導；**期限 2027-01-01 前**）、~~`DH-BREADTH-COPY-NOPROXY`~~ `DH-BREADTH-COPY-NOPROXY`（新 UI 本 PR 修正；殘留僅凍結舊 UI 的 F3 擋燈文案，只登記不改）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-4 S-1））、`DH-FIND-UNEVAL-NOTE`、`DH-OLDUI-PROXY-LABELS`、`DH-NONE-TO-ZERO-RENDER`、`DH-FT-SCHEMA-ASOF`、`DH-MKTSCORE-DENOM`、`DH-EXPORT-LABEL-READING`、`DH-M1B-COVERAGE`、`DH-RISKCAP-OLDFILE-NONRVRC`、`DH-TEST-Z8-ALLOC-NARROW`（2026-10-23 QA-4 新增登記）、`DH-JINGQI-STALE-SESSION`、`DH-REFRESH-HEALTH-NAN`（2026-10-23 QA-5 新增登記）。批 2／VN1-PG：依 DEC-075 第 4 點待重評邊界，**未開始**。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節實作內容與殘留為**總管轉述**；撰寫組只以 `git grep` 抽查 `BREADTH_PROXY_SCORING_ENABLED`、`MA200_WINDOW_DAYS`、`ma200_status`、新燈名、`shared/macro_forward_test_schema` 的「v2 列與 v3 列不可混比」註記存在，**未重跑任何測試**。本機測試 Python 3.13、CI Python 3.11，以 CI 結果為準。
- 📌 **2026-10-23 Freeze 補註（append-only，上文一字未改；有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：本節開頭量測行「HEAD `04a9bc2e`」已過時 —— PR #910 其後又有 `0122eec1`（治理文件）、`3003bb3c`（QA-4 S-1 文案）、`f3dd098c`（QA-5 SHOULD-1 測試＋佔位）、**`c8e30d84`（冷啟動修正 `DH-REGIME-NOWARROOM`，最後一個產品碼 commit）**，以及 Freeze 文件 commit（以 PR #910 最新 commit 為準）。**客戶可見**：冷啟動（未按「🚀 更新今日戰情」／三源全空／warroom 被移除）**不再顯示規則引擎（`macro_state.json`）推出的多空位階**，改灰色「總經尚未載入」；Risk Cap `exposure_limit_pct` 不變（見上第 6 項）。QA-6 對 `c8e30d84` 的獨立複驗於 Freeze 撰寫時**進行中、結果未知**。耐久狀態總覽見 **§29**。
- 📌 **2026-10-24 #910 合併補註（append-only，上文一字未改；有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：PR #910 已於 2026-10-24 squash 合併進 main（merge `066f461e`）。上方 Freeze 補註「`c8e30d84`＝最後一個產品碼 commit」「QA-6 進行中」已過時 —— **最後產品碼 commit＝`9714d0b3`**（PR 最後 head）。QA 經過：QA-6 對 `c8e30d84` 判**不可合併**（2 MUST：MUST-1 持股頁卡④（冷啟動、缺真實廣度）與卡⑤（缺真實廣度）在 v2 卡面畫成紅卡；MUST-2 AI 個股評分被擋字串冷啟動附不實救法）→ `9714d0b3` 修正 → **QA-7 對 `9714d0b3` 判可合併（0 MUST）**；`9714d0b3` CI Fast＋Slow success；完整判定見 PR #910 留言。上文第 6、7 項「待 QA-7」自此讀作「QA-7 已判可合併」。**客戶可見行為（main 現行）**：正式廣度來源接上前，健康分／市場位階通常 ⬜ 未評估；冷啟動（尚未按更新）位階亦 ⬜（灰色「總經尚未載入」，不退規則引擎位階）；🛡️ 持股頁卡④⑤ 在冷啟動／缺真實廣度時為**灰卡、不是紅卡**；Risk Cap 不受影響。QA-7 SHOULD S-1（灰卡沿用 #7「缺漏 · 可重跑」徽章的語意張力）已登記 BACKLOG `DH-BADGE-RERUN-SEMANTICS`（視覺規格，待客戶裁示）。~~main CI 以 GitHub Actions 為準（撰寫組未查）。~~ main CI＋main verification **已成立**（main `066f461e` PR Check run 39995254045 success；`649f739` run 39999485112 success；`PROJECT_RULES.md` 第 7 節；總管 GitHub Actions API 實查＋撰寫組 `gh api` 獨立複查）（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。

## 29. 2026-10-23 GitHub 交接 Freeze 耐久狀態

> 2026-10-23 新增（客戶同日 Freeze 指示：專案 AI 額度預計 2026-10-24 00:00 台北取消，下一個 AI 只讀 GitHub 也要能無損接手）。本節只放**耐久狀態**；現況與唯一下一步只在 `docs/HANDOFF.md` §0「~~Freeze 版~~ ~~#910 合併後~~ DEC-077 裁示後」段（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（2026-10-24 再更新：改指 DEC-077 裁示後段，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；裁示全文只在 `docs/DECISIONS.md`；待辦只在 `docs/BACKLOG.md`；規則本文只在 `PROJECT_RULES.md`。量測：Freeze 撰寫時 `origin/main`＝`397398a2`（cron tip；`b9ed892d` 之後只多 2 個 cron 資料 commit，無程式變更），PR #910 未合併（總管 `git fetch`／GitHub API 實查轉述，撰寫組未重查）。📌 2026-10-24：PR #910 已合併，main＝`066f461e`（含 #910；撰寫組 `git fetch origin main` 確認）（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。⚠️ cron 會推進 tip，引用前重查（`CLAUDE.md` §8.2.A.0 規則 4）。

### 29.1 產品階段與新 UI 方向

> 出處：客戶 2026-10-23 Freeze 指示；正式裁示見 `docs/DECISIONS.md` ~~新 DEC（另組撰寫中，**號碼以 DECISIONS 為準**）~~ **DEC-076**（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實修正））；先前方向見 DEC-071、DEC-072（§24）。⛔ 本節是摘要，不是規範來源；⛔ 非線框核准、非動工授權（畫面結構異動仍須先出文字線框，DEC-003）。

- **階段**：vNext 新 UI 尚在成形；Data Health 修復批進行中（§25、§27、§28、本節 29.4）。**現行實作依據仍是 DEC-017 五頁**（`shared/ia_nav.py::PAGE_LABELS`），直到新線框經客戶拍板。
- **核心原則（客戶原文）**：「**底層能力完整保留，前台流程極簡。**」新 UI 不是把舊 UI 原封不動搬過去，也不能因新版簡化就把舊 UI 的投資能力刪掉。正確順序：舊 UI 有價值的功能／判讀邏輯 → 重整資訊架構 → 決定新 UI 位置 → 重新設計顯示方式 → 驗證能力覆蓋 → 最後才考慮刪除舊 UI。
- **主要投資流程（各頁回答一個問題）**：
  - 📊 **大盤／市場趨勢** —「現在市場環境適不適合投資？目前可以承擔多少風險？」含大盤、市場位階、台股趨勢、國際趨勢、指標危險度、Risk Cap、重要總經／籌碼／技術資訊；**底層語意分開**（29.2）。
  - 🎯 **標的** — 整合找標的、查一檔、個股健檢、ETF、財報、籌碼、技術、估值等既有標的分析能力；體驗＝標的清單 → 點一檔 → 同頁／淺層 route 完整健檢。
  - ⚡ **行動** — 承接既有 deterministic action logic（exit signal、take profit、swap、汰弱換強、watch、action required）；⛔ 不得為 UI 自行發明新的加減碼比例或投資語意。
  - 🛡️ **持股** — 個股／ETF 健檢、配息、stress、VaR、risk contribution、concentration、portfolio limits 等既有組合風險能力。
- **輔助入口**：🩺 **資料中心**＝系統／資料維護入口，**不是**第五個投資決策頁（追蹤資料、狀態、最新資料日、來源、問題、影響功能、處理方式：可自行修復／需研究替代來源／API／MCP／需客戶裁示／暫不處理；規格草案 `DH-DATA-CENTER`，未實作）；👤 **我的**＝account／settings／connection／utility，不塞回投資流程。
- **「憑什麼」**：改為**每頁 contextual explainability**（為什麼這樣判斷、指標、日期、資料來源、規則），不是主要導航頁。
- **Progressive disclosure 三層**：第一層＝結論／狀態；第二層＝主要原因；第三層（需要時展開）＝原始指標、日期、source、rule、technical detail、confidence／completeness。⛔ 不把舊 UI 全部燈號、數字一次攤在首頁。
- **舊 UI 的地位**：新 UI 成立以前，舊 UI 是**重要 capability／logic reference**（含既有個股健檢：財報健檢、KD／技術輸入、replacement／rotation、stock trend input、個股燈號、持股戰情整合；盤點見 §23）。**刪除前提**：capability inventory → new UI mapping → implementation → coverage validation（Old UI Capability → New UI Coverage Matrix）→ regression → 客戶核准，之後才進舊 UI removal Decision Gate；⛔「新版比較漂亮」不是刪除理由；舊 UI 仍凍結（DEC-019／020）。待辦見 BACKLOG（UI 搬遷相關項）。

### 29.2 投資語意界線（不得合成單一分數）

- **市場位階**：市場 bull／bear／trend 狀態。
- **指標危險度**：目前多少危險條件／門檻被觸發；**≠ 市場多空**。
- **Risk Cap**：允許承擔的最大曝險／風險控制；**≠ 市場趨勢**。
- **台股趨勢**、**國際趨勢**：新的 research／market trend concept，**仍無正式定義**（`VN1-MT-TREND-DEF`，§20、§22）。
- 因此完全可能出現「**趨勢偏多，但風險升高、Risk Cap 降低**」。⛔ 不得為 UI 簡化把上述概念偷偷合成單一 score／light（另見 §22.3、§24）。

### 29.3 Data ≠ AI 與 missing 規則

- **Data Layer** 只負責 acquire、clean、normalize、validate、provenance；**AI Layer** 只能讀已取得、可追溯、驗證狀態清楚的資料做分析／解釋，⛔ 不得補造客觀資料。
- missing ≠ 0；missing ≠ neutral；missing ≠ normal；missing ≠ HOLD；proxy ≠ real data；缺資料與真 0 必須區分；顏色不得是唯一資訊載體；⛔ 不得為了讓產品「有答案」而製造結論。
- 規則本文只在 `PROJECT_RULES.md`（資料規則 D 系列，例 D5「missing ≠ 0」）與 `docs/DECISIONS.md`（DEC-026、DEC-040、DEC-054、DEC-062 Q5「代理值只顯示、不計分」）；`CLAUDE.md` §1 Fail Loud。本節只摘要。

### 29.4 Data Health 現況

- **Audit**：§25（全表 `docs/vnext/DATA_HEALTH_AUDIT_2026-10-23.md`）。
- **DEC-074（裁示 B）**：代理廣度不得計分；受 breadth 影響且無法依既有正式規則可靠計算的健康分 →「⬜ 未評估／資料不足」；不重新設計權重、不重新正規化。
- **DEC-075 D-1(a) 完整語意**：正式 breadth 不存在／無法可靠計算相關 health 時 —— ⛔ 代理 breadth 不得參與 scoring；⛔ 不得偷偷 fallback（含退 `macro_state.json` 規則引擎）產生看似正式的市場位階；受影響結果 →「⬜ 未評估／資料不足」；⛔ 不得因產品想保持有答案而補結論。**同時不過度擴張**：⛔ 不得把它擴張成「所有市場／Risk Cap 概念都失效」—— **只有真正依賴失效資料的 component 不可判定**；**Risk Cap 保持自己的既有語意**（PR #910 未改 `exposure_limit_pct`）。
- **批 A＋批 1'**：實作在 **PR #910**（§28；含冷啟動 `DH-REGIME-NOWARROOM` 修正 `c8e30d84`），**未合併**；QA-1～QA-5 完成，~~QA-6 對 `c8e30d84` 複驗中、CI 進行中（Freeze 撰寫時）~~ QA-6 對 `c8e30d84` 判不可合併（2 MUST），已於後續修正 commit 處理、待獨立 QA-7＋CI（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-6 結果））；📌 ~~**未合併**~~（同列前句）→ `9714d0b3` 修正、QA-7 判可合併、**已合併 #910（merge `066f461e`）**（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；殘留／deferred 項登記於 BACKLOG 5.1.8（清單見 §28「已知殘留」）。
- **批 2／3／4 與新來源研究：皆未開始**（定義以 BACKLOG 與 `docs/vnext/DATA_HEALTH_REPAIR_PLAN_2026-10-23.md` 為準；撰寫組 grep 該檔第 2.2～2.4 節）：
  - 批 2（PIT／代理不計分，High，原提案併 `VN1-PG-*`）＝`DH-BIAS240-EST`／`DH-PCR-PROXY`／`DH-MACRO-FWD-ASOF`／`DH-REFRESH-STALE`；DEC-075 第 4 點：等批 A＋1' 合併＋QA＋CI＋main verification 後**重評邊界並送客戶裁示**，未指派（📌 「批 A＋1' 合併」已成立：#910 merge `066f461e`（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））。📌 2026-10-24 再更新：main verification 已成立 ⇒ 重評完成、**已裁示 DEC-077**（採方案 C：批 2 拆 **C1**（已指派、~~未開工~~ **已完成並合併 #913（merge `37cf87e6`）**（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：C1 #913 已合併）））／**C1′**（等 DEC-076 ①）／**C2**（併 VN1-PG，另開 Decision Gate））；研究摘要見 **§30**（2026-10-24 更新，有意識的更新，不是漏刪，決策者 客戶（DEC-077））。
  - 批 3（L1 契約，High，需能連 FinMind／Yahoo 的環境）＝`DH-357-DIV-FIELD`／`DH-KLINE-ADJ`／`DH-INST-FILL0`／`DH-ETF-FFILL`／`DH-REVENUE-ZERO`／`DH-FIN-HEALTH-CF`(a)；未指派。
  - 批 4（延後）＝`DH-SCORE-NEUTRAL50`／`DH-FWD-RECON`／`DH-FIN-HEALTH-CF`(b)／`DH-WHY-FRED-LAMP`；未指派。
  - 新資料來源研究（real market breadth、Sahm、US 2Y、利差、30Y、TIPS、OECD CLI、借券、TDCC、ETF 配息／成分、市場 EPS／PE／forward EPS、CSP／AI capex 等）＝**research candidates，⛔ 非已授權接入 production**；⛔ 不得看到 BACKLOG 就自行換源。
- **客戶可見常態**：正式 breadth 來源出現前，健康分／市場位階／建議持股姿態帶**通常顯示 ⬜ 未評估**（旗標 `BREADTH_PROXY_SCORING_ENABLED=False`）。
- **硬期限**：`DH-CALIB-CRON` 須在 **2027-01-01**（下次季度校準排程）前修正或暫停。
- 📌 **2026-10-24 Freeze 部分解除（append-only，上文一字未改；決策者 客戶（DEC-077））**：Freeze 禁止清單中的「**新 Batch」僅對 Data Health C1 解除**（C1＝缺值清理筆數 log、PCR 來源標記、前進式驗證帳本 per-input as-of；零投資輸出變更）；C1′／C2／VN1-PG 與其餘 Freeze 禁止項（大型研究、改公式／權重／門檻、刪舊 UI、刪 branch、不可逆清理、新資料來源、開 production write／Daily Schedule）**不變**。詳見 `docs/DECISIONS.md` DEC-077、本檔 §30。

### 29.5 Production 安全

- `PRODUCTION_WRITE_APPROVED = False`（`shared/risk_cap_history_policy.py`，撰寫組 grep 實查）；Daily Schedule NOT APPROVED（DEC-066 F）。⛔ 不得因交接自行開啟。
- `.github/workflows/` 內含 `schedule:` 的 workflow（撰寫組 grep 列舉，Freeze 撰寫時）：`calibrate_health_weights.yml`（季）、`export_db.yml`（每日）、`push_holdings_daily.yml`（平日）、`push_weekly_report.yml`（週）、`recalibrate_macro.yml`（季）、`update_etf_managers.yml`（週）、`update_forward_test.yml`（月）、`update_fundamentals.yml`（季，財報公布後）、`update_macro_forward_test.yml`（平日）、`update_macro_history.yml`（每日）、`update_sector_flow.yml`（每日）；`update_health_history.yml` 的 schedule **已註解停用**。其餘（`pr-check`、`probe_tw_sources`、`push_daily_signals`、`push_watchlist_signals`、`risk_cap_history_poc`、`risk_cap_wif_negative_r5`）無 schedule。**是否有外部寫入／推播副作用以各 workflow 檔為準**（撰寫組未逐檔判讀）；**本 Freeze 未改任何排程或 workflow**。

### 29.6 Branch

- 遠端 branch ~~共 **8 條**~~ **8 條（量測日 2026-10-23）**（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實修正））（Freeze 撰寫時 `git branch -r`：`auto/recalibrate-20261001`、`ccr-310717b7-37xwl6`（#910 head）、`ccr-8d5a141e-3fdtwt`、`claude/investment-inbox-product-design-m1lu7v`、`claude/stock-dashboard-handoff-g9dtm0`、`data`、`main`、`v2`）。⚠️ `data` 為 `export_db.yml` 的輸出分支（依其 workflow name）；~~其餘是否含 unique commit **未查**。~~ 各條 unique commit 數已於 `docs/BACKLOG.md` `BR-CLEANUP` 實測（2026-10-23），以該列為準（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實修正））。
- 客戶方向：**最後再一次清**；**刪 branch 視為不可逆治理動作**，⛔ 本次交接不刪；未來刪除前須重查 GitHub（unique commit、是否被 workflow 使用）並經客戶核准。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節 GitHub 實況（main SHA、open PR、#910 commits、QA／CI 狀態）為**總管實查轉述**；workflow 列舉、`PRODUCTION_WRITE_APPROVED`、branch 名、批 2～4 定義為撰寫組 grep；均**未經第二組驗證**，接手時依 `PROJECT_RULES.md` 第 15 節重查。

## 30. Data Health 批 2 × VN1-PG 邊界研究結論（2026-10-24；AI 研究結論、非客戶裁示；四組獨立＋紅隊）

> 2026-10-24 新增（append-only）。⚠️ **本節是 AI 研究結論，不是客戶裁示**；客戶依此送題所作的裁示只在 `docs/DECISIONS.md` **DEC-077**（採方案 C）；待辦與拆分明細只在 `docs/BACKLOG.md` **5.1.10**；現況與唯一下一步只在 `docs/HANDOFF.md` §0「DEC-077 裁示後」段。本節只摘要＋出處。
> **方法**：A 組（治理文件）、B 組（程式碼重疊）、D 組（資料血緣）、E 組（VN1-PG 失效傳播，沙箱以 stub 取代 streamlit／yfinance、只實跑純函式）四組獨立唯讀調查 → 總管交叉比對 → F 組獨立紅隊否證 14 條承重宣稱（9 成立、4 部分成立已修正、1 條（CI run）由總管以 GitHub Actions API 自查成立）。基準 main `649f7393`。**全部唯讀、未跑 pytest**；缺值清理位置清單**非窮舉**。撰寫組只以 `git grep`／`gh api` 抽查部分符號與 CI run，未重跑實驗（`CLAUDE.md` §-2 規則 6）。

### 30.1 Dependency Matrix（裁示後採方案 C）

| 子批 | 內容（摘要） | 為何這樣切 | 狀態 |
|---|---|---|---|
| **C1**（DH-only） | ① 既有缺值清理路徑（`dropna` 類）記錄筆數（`DH-C1-NA-DROP-LOG`；承接 `VN1-PG-L-TWII-DROPNA-LOG`）；② PCR 每日來源／來源類型欄（`DH-C1-PCR-SRC`；`DH-PCR-PROXY` 前置）；③ 前進式驗證帳本 per-leg as_of 欄（`DH-C1-FWD-LEG-ASOF`；既有 `date`／`inputs_as_of` 語意不變） | 只加「從哪來、哪一天、清掉多少」的可觀測性 metadata，**可做到零投資輸出變更**；帳本無 production reader（`macro_fwd_test_store.load_signals` 只被 `append_signals` 去重） | 已指派（DEC-077）、~~未開工~~ **已完成（#913，merge `37cf87e6`；見 30.9）**（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：C1 #913 已合併）） |
| **C1′**（指標危險度子批） | 16 燈依 `shared/freshness_policy.py` 套日期閘（僅限有可追溯日期且有核准規則之燈）、`bias_240` 燈估算值、五桶 `fut_net` 燈凍結一致性、`DH-REFRESH-STALE` 燈號側、`DH-JINGQI-STALE-SESSION` 文案、出口燈 freshness（撰寫組歸類，研究檔未明列於 C1′） | **灰掉燈號會改變「最差燈／N/M」**＝改指標危險度輸出 ⇒ 不屬 C1；且口徑（worst-of vs 觸發計數）待 DEC-076 ① | 等 DEC-076 ① |
| **C2**（VN1-PG「Risk Cap 輸入有效性批」） | `VN1-PG-VIX-ASOF`、`VN1-PG-PIT-CONSISTENCY`（吸收 `DH-REFRESH-STALE` Risk Cap 側；DEC-070 Q1／Q2）、`VN1-PG-VETO-TRACE`（Sheet 表頭變更宜在首寫前）、`VN1-PG-L-PIT-GAPS` (a)(b)(c)、外資期貨凍結值 Risk Cap 側、`DH-BIAS240-EST`／`DH-PCR-PROXY` 計分准入＋台灣 PMI proxy 語意 | 會改 Risk Cap 計分准入／PIT 判斷；BIAS240／PCR／PMI 合併研究、一次裁示，`RISK_CAP_RULESET_VERSION` 至多升一次 | 另開 Decision Gate |
| 獨立 | `DH-LAMP-STALE`(b)（需線框，併資料中心）、margin 無 as_of（L1 資料契約，批 3 性質）、`DH-CALIB-CRON`（2027-01-01 期限） | 與批 2 邊界無耦合 | 見 BACKLOG |

⚠️「DEC-029 涵蓋 16 燈過期改未評估」為**總管判讀**；DEC-062 Q5 **不涵蓋過期**（F 組指出）。

### 30.2 失效傳播事實（E 組沙箱實跑＋F 組複跑）

- **Required Core**（`shared/risk_cap_policy.py::REQUIRED_CORE_INPUTS`）＝VIX、台灣 PMI 當月、PMI 前月、外資期貨淨空、加權指數跌破 MA5；任一非 FRESH 或 None ⇒ `risk_cap_apply` 不寫檔、7 天內沿用（DEC-044／DEC-048）。
- **Optional**（`OPTIONAL_INPUTS`）＝M1B、M2、BIAS240、PCR；缺 ⇒ 照常產生上限、揭露未評估（M1B／M2 停用列 disabled）。
- **跨日配對實跑**：評估時點 2026-10-23 20:00 台北，MA5 資料日 10-23、外資期貨最後有效 10-21 ⇒ 全 FRESH、`required_core_gaps=()`、上限 40%；`risk_cap_history_service.build_record` 不檢查跨日 ⇒ 會記 **VALID** —— 與 DEC-070 Q1（外資期貨與 MA5 同一台股交易日）**不符**（歸 C2 `VN1-PG-PIT-CONSISTENCY`）。VIX 當日 bar 落後 0 平日亦判 FRESH（盤前暫定 bar 存在的證據只有 BACKLOG 轉述的 run 39755679219）。

### 30.3 位階／16 燈／健康分與 Risk Cap 相互獨立

- 市場位階、指標危險度 16 燈、健康分與 Risk Cap 的程式路徑**互相獨立**；Risk Cap 缺失不會讓位階／16 燈失效；**計算路徑互相獨立；顯示層例外見 30.4**（健康分未評估時新 UI 看不到 Risk Cap）（與 DEC-076 第 8、10 節「不得合成單一分數」「Risk Cap 保持自己的既有語意」同向）。

### 30.4 Risk Cap visibility 為 #910 副作用（`RC-VISIBILITY`）

- #910 前健康分缺旌旗時以權重重新歸一化仍有值；#910 後（`BREADTH_PROXY_SCORING_ENABLED=False`、`fetch_adl` 只有 ^TWII 代理）**健康分恆 None** ⇒ `shared/allocation_decision.py` 在 `not _is_loaded or _health is None` 回未評估 ⇒ 今天頁卡①（`src/ui/views/page_today.py::build_verdict_tiles`，`_alloc_state == UI_LIVE` 才顯示上限）、持股頁卡⑤、AI 問答 `_tool_get_market_state`（`ok=False`）**都看不到 Risk Cap**；只有當輪重算時，今天頁更新報告巢狀「逐來源結果」的 `STEP_RISK_CAP` 說明含「系統風險上限 X%」。**Risk Cap 本身仍計算、檔案有效。**
- 與 DEC-075「本條不改 Risk Cap」、DEC-076 第 10 節有張力。客戶裁示（DEC-077）：獨立待決，PIT／C2 後再做 UI Decision Gate，**目前不恢復顯示**。

### 30.5 台灣 PMI proxy 旗標（`PROXY-SEMANTICS` 證據）

- `src/data/macro/macro_core.py` 的 data.gov.tw/6100 段與 NDC 段回傳 `is_proxy=True`；durable 快照 `data_cache/macro_last_good/tw_pmi.json` 目前 `is_proxy=true`（source data.gov.tw/6100）；`dated_inputs.extract_monthly`、`freshness_policy`、16 燈皆不讀 ⇒ **Required Core 正以標 `is_proxy` 的值計分**。旗標原意查不到（同檔註解稱 6100 為「同一份官方數字」；淺 clone 追不到歷史）。
- **含意**：若通則化「proxy → 不計分」，Required Core PMI 會被剔除、Risk Cap 不產生新上限 ⇒ 客戶裁示（DEC-077）**不得先立通則**，BIAS240、PCR、台灣 PMI 在 C2 開工前一起研究與裁示。BIAS240 估算觸發頻率、PCR 走 FinMind 估算頻率在 production **皆無紀錄**（後者可由 C1 `DH-C1-PCR-SRC` 累積）。

### 30.6 C1／C1′／C2 切分理由（一句話）

- **C1** 只增加可觀測性、不改任何投資輸出；**C1′** 會改指標危險度輸出且口徑待 DEC-076 ①；**C2** 會改 Risk Cap 計分准入與 PIT 判斷、需與 VN1-PG 一次設計並先裁 proxy 語意。三者混批會讓「零投資輸出變更」無法驗證。

### 30.7 其他研究發現（只登記、未施工；明細見 BACKLOG 5.1.10）

- 外資期貨凍結值處理不一致（`DH-FUT-FROZEN-MISMATCH`）；出口燈無資料月新鮮度閘（`DH-EXPORT-FRESHNESS`）且「出口 90 天 stale cache」文件不實（`DH-AUDIT-EXPORT-CACHE-DOC`）；schema version 規則 vs 預告註解衝突（併 `DH-FT-SCHEMA-ASOF`：C1 只加欄 ⇒ 依規則不 bump；本檔 §27「`ruleset_hash` 二次切換風險」一句據此在 C1 範圍內不成立，若日後改 `inputs_as_of` 語意才會發生）；修復計畫 §2.2 與程式不符（`DH-PLAN-22-DRIFT`）；16 燈中 margin／news_systemic／health 無可用 as_of（`DH-LAMP-NO-ASOF`）；`fetch_adl` docstring 不實（併 `DH-ADL-PROXY`）；`DH-MACRO-FWD-ASOF` 原動機變弱（#910 後 jqavg／health 恆 None）。

### 30.8 GitHub 實況（總管實查；撰寫組 `gh api` 複查 CI run；量測日 2026-10-24，會過期）

- ~~main `649f7393`（#911）；Open／Draft PR 0；~~ main `37cf87e6`（#913 C1 squash merge；其前 `1c8c1415`＝#912、`649f7393`＝#911）；open PR 以 GitHub 為準（C1 後 SSOT 同步 PR 由總管開立）；main `37cf87e6` CI：main push run 40066433398（PR Check）conclusion=success；Fast job 120790571734 success（05:29:19→05:41:31Z）、Slow job 120792951874 success（05:41:34→05:59:31Z）（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更新：C1 #913 已合併））；（以下為 `649f7393` 時點事實）main CI 兩個 run success（見 DEC-075 2026-10-24 附註）⇒ **DEC-075 第 4 點前置之 main verification 已成立**。遠端分支含 main 共 8 條（#910 head `ccr-310717b7-37xwl6` 已不在，多了本對話分支 `claude/gracious-hypatia-1cjuh8`；量測日 2026-10-24，會過期）。`PRODUCTION_WRITE_APPROVED: bool = False`（`shared/risk_cap_history_policy.py`）。⚠️ 未驗：squash 後 main 樹是否等同 `9714d0b3`。

### 30.9 C1 完成狀態（2026-10-24；append-only；決策者 AI 總管（事實更新））

> 2026-10-24 新增。C1＝DEC-077 第 2 點指派的三類「資料可觀測性／provenance metadata」。執行紀錄（含偏離規格，屬總管內部技術拍板、非客戶裁示）只在 `docs/DECISIONS.md` DEC-077「執行紀錄」；結案與新登記只在 `docs/BACKLOG.md` 5.1.10；現況與下一步只在 `docs/HANDOFF.md` §0「C1 合併後」段。本節只摘要＋出處。

- **PR／SHA**：PR #913（https://github.com/linchen-20200325/my-stock-dashboard/pull/913）；squash merge `37cf87e6`（完整 `37cf87e6103a72cac45d812fc633ab641f9a6b7b`）；PR head `29cd7f3e`。
- **CI**：PR CI＝PR head 29cd7f3e：Fast checks（job 120785311814）success、Slow tests AppTest（job 120788338331）success；run 40064619133。main CI＝main push run 40066433398（PR Check）conclusion=success；Fast job 120790571734 success（05:29:19→05:41:31Z）、Slow job 120792951874 success（05:41:34→05:59:31Z）。⚠️ main verification（`PROJECT_RULES.md` 第 7 節）~~在 main CI 結論回填前**不成立**~~ **已成立**（main SHA `37cf87e6`＋main CI success）（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管，事實回填）。
- **完成內容**（三項全部 done）：
  - `DH-C1-NA-DROP-LOG`：11 處 production ^TWII／VIX `dropna` 開始記錄清理筆數，清掉 >0 筆時印一行（筆數算不出來時也會印一行說明；stdout 寫不出去時改寫 stderr）；共用 helper＝新 L0 檔 `shared/na_drop_log.py`。8 處＝`daily_data_fetchers._fetch_single_cached`／`fetch_adl`、`macro_core.fetch_yf_ohlcv`／`_fetch_yf_close_base`、`macro_snapshot.compute_twii_bias`／`fetch_vix_block`、`scripts/update_macro_forward_test._twii_close_and_asof`、`scripts/update_macro_history.fetch_twii_ohlcv`；另 3 處＝`macro_cache_reader.load_twii_close`、`weekly_review_service._macro_lite_lines`、`risk_radar._fetch_cboe_csv`。⚠️ 驗證方式：兩組盤點交叉（實作組＋QA-A），**非形式化窮舉**。
  - `DH-C1-PCR-SRC`：先行指標 df 新增 `_pcr_src` 欄（TAIFEX＝`official`、FinMind-TXO-inst-est＝`proxy_estimate`）；只描述來源、**不是計分資格**，下游不讀；欄名與計畫的 `選PCR_src` 不同，因底線開頭會被 CSV 匯出排除。
  - `DH-C1-FWD-LEG-ASOF`：帳本附加四欄 `score_index_as_of`／`inst_as_of`／`adl_as_of`／`li_as_of`；schema 維持 3、`ruleset_hash` 不變（`6c716f5411fb`）；schema 檔「per-leg as_of 會再 bump」預告已加刪除線並註明理由 ⇒ §27「`ruleset_hash` 二次切換風險」在 C1 **未發生**（若日後改 `inputs_as_of` 語意才會發生，見 §30.7）。
- **QA 摘要（零投資輸出變更）**：before／after 測試（還原鏈到 `1c8c1415`）＋四輪、共五組獨立 QA（A／B／C／D／E）；最終 head 29cd7f3e（只改測試與 docstring）由總管讀 diff＋PR CI 驗證，未再派獨立 QA：下游 `extract_leading`／`build_engine_inputs`→`calculate_system_state`／`calc_traffic_light`／`compute_five_bucket_summary`／`render_leading_table`／CSV **全部相同**。已知、接受的唯一差異：`src/ui/tabs/tab_macro.py` 約 :463 stdout log「有效欄=N」多 1（只影響 log）。
- **Production**：既有帳本 cron 合併後預期會（程式路徑讀碼成立；GH Actions cron 未實機驗證）把四欄寫進 `data_cache/macro_forward_test/signals.parquet` —— 既有寫入多了四欄，**不是新的 production write**；`PRODUCTION_WRITE_APPROVED=False` 未動（撰寫組 grep 實查）；Daily Schedule 仍 NOT APPROVED（DEC-066 F）。
- **限制（未實測）**：Streamlit Cloud、GitHub Actions cron、Windows cp950 都沒有實機跑；外部 API 用 mock。四欄語意限制（`li_as_of` 可能是補位平日列、`inst_as_of` 淨額全 None 仍記日期、`adl_as_of` 照實反映 `fetch_adl` 可能差一日）登記 BACKLOG `DH-LI-ASOF-SEMANTICS`。
- **新發現（只登記、未施工）**：`DH-RS-PREP-DROPNA`、`DH-NONUTF8-PRINT`、`DH-LI-ASOF-SEMANTICS`、`DH-TAB-MACRO-LOG-COUNT`（BACKLOG 5.1.10）；`src/compute/macro/macro_forward_test.py::leg_as_of_from_inputs`／`scripts/update_macro_forward_test.py::main` 另有 C1 新增的一般中文 print 未走安全列印，見 BACKLOG `DH-NONUTF8-PRINT`（文件 QA 2026-10-24 讀碼發現，總管確認；未實測）。
- **階段狀態**：C1 完成後**停下等客戶裁示**；下一步**不是**自動做 C2（DEC-077 第 5 點）。C2 前仍需裁示：`DEC076-CONFIRM` ①②、`PROXY-SEMANTICS`（BIAS240／PCR／台灣 PMI 一起）、`CV1-DR-11`、C2 Decision Gate、`RC-VISIBILITY`（C2 後）。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：CI、QA、零輸出驗證結論為**總管查證後轉述**；撰寫組只以 `git show --stat 37cf87e6`、`gh api repos/:owner/:repo/pulls/913` 與 `git grep` 核對 merge／head SHA 與關鍵符號，**未重跑測試、未重做 before／after**。

## 31. `PROXY-SEMANTICS`／C2 Decision Gate 研究摘要（2026-10-24，~~待裁示~~ **已裁示 DEC-080**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080））

> 2026-10-24 新增（append-only）。⚠️ **AI 研究結論，不是客戶裁示**；三組獨立唯讀研究（A 程式路徑、B 治理文件、C 紅隊行為實證；基準 main `f48b30bf`）。**方案全文、Q1～Q6、三套方案比較、六題待裁示只在 `docs/vnext/VNEXT_1_0_DECISION_GATES.md` §7**；新登記只在 `docs/BACKLOG.md` 5.1.11；本節只放現行契約摘要＋pointer。各事實的「兩組交叉／單組」標記見 Gate §7.1。

- **Required Core**：DEC-048 客戶原文「{VIX、PMI 當期、PMI 前月、外資期貨＋MA5}」；依 DEC-048 展開＝VIX、台灣 PMI 當期＋前月、外資期貨淨空單＋加權指數跌破 MA5（`shared/risk_cap_policy.py:56-62`）；任一無效 → 不產生新 cap、兩檔不寫；讀端沿用 7 天內快照，超過 →「無法判定」（DEC-048／044／040；C 組實測 6 種缺值情境 `written=False`、6.9 天沿用、7.1 天 None）。7 天以**快照寫入時間**計、不看輸入 as-of ⇒ 沿用期末實際資料年齡可 >10 天（推論＋實測邊界）。
- **Optional**（BIAS240、PCR）缺 → 照算並揭露「未評估」（DEC-046／051；實測正確）。
- **proxy／estimated 對 Risk Cap 的正式契約不存在**；程式對 proxy／estimated／stale-cache 完全無處置：BIAS240 <240 日的估算值（`is_estimated` 另欄、`extract_bias240` 不讀）進 Risk Cap 計分（實測 +20% 估算值在共振條件 VIX≥22 或 PMI<50 下使上限 40% → 20%、卡面仍「皆已評估」；<−10 時反而加 10 分放寬上限）；PCR 同欄逐日混源（FinMind TXO 法人估算／TAIFEX），`_pcr_src` 零讀者且由 `test_c1_observability::test_new_fields_have_no_readers` 強制；台灣 PMI `is_proxy` 語意倒置（官方鏡像標 True、第三方標 False）且無讀者、前月恆取 data.gov.tw 6100、8 源全敗時 stale-cache 在發布期內判 FRESH 可滿足 Core、字樣不上 UI；無任何 DEC 指定 PMI 正式來源。
- **freshness／PIT**：各 input 各自判新鮮、無跨 input 同日比對；16 燈無新鮮度閘門、無 as_of（VIX 燈可用過期值判燈，Risk Cap 同時判過期不計分）；盤中未收 K 棒排除不涵蓋 VIX／BIAS／MA5；快照有 `input_asof` 但 UI 不揭露混日；forward ledger 不含 Risk Cap。
- **新 UI 看不到 Risk Cap 的根因**（單組實測，C）：`BREADTH_PROXY_SCORING_ENABLED=False` → 健康分恆 None → allocation 未評估 →「系統風險上限」不進 `caps` ⇒ 快照有效上限 40% 但卡①／卡⑤ 顯示「尚未評估」（`RC-VISIBILITY`）。
- **§30.3 補正（append-only；§30.3 原文未改）**：「位階／16 燈／健康分與 Risk Cap 互相獨立」需加限定 —— 健康分是 16 燈第一盞（單組，C）；位階第 3 順位來源＝Risk Cap 引擎 `market_regime`，目前被同一旗標封住（兩組交叉，A、C）。
- ~~**待客戶裁示**~~ **已裁示（見本節末條 DEC-080）**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）（6 題，Gate §7.4；推薦一律「總管推薦，待客戶裁示」，⛔ 非 Approved）：資料身分規則選方案（推薦方案 2 分層兩軸）；BIAS240 估算是否退出 Risk Cap 計分；PCR 法人估算是否退出；PMI 第三方轉載／沿用快照可否滿足必要核心；7 天沿用是否加揭露（不改計算）；C2 是否先做 shadow（C2a）再改計分（C2b）。`DEC076-CONFIRM` ①② 仍未裁示且與 16 燈處置相關。
- **仍禁止施工**（裁示前狀態；現行範圍見本節末條）：C1′、C2 實作（~~含 C2a~~ C2a 已由 DEC-080 指派（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080））、VN1-PG production write（`PRODUCTION_WRITE_APPROVED=False`）、Risk Cap 公式／門檻／權重、`is_proxy` 語意修正、新增或替換 production source、`RC-VISIBILITY` UI 改動（需線框）。
- **已裁示（DEC-080，客戶 2026-10-24；append-only）**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）：裁示逐字全文只在 `docs/DECISIONS.md` **DEC-080**；Gate 各題標記見 `docs/vnext/VNEXT_1_0_DECISION_GATES.md` §7.4／7.7；施工列見 `docs/BACKLOG.md` 5.1.10 **C2a**／**C2b**。摘要：(1) 資料身分／計分契約＝**方案 2**（provenance 與 freshness 分開；as_of、source_id；exists／fresh／displayable／scoring eligible／Risk Cap eligible 不得壓成同一 boolean）；(2) BIAS240 估算＝不參與 Risk Cap 計分、可顯示＋標示、Optional 未評估、不阻斷；(3) PCR 法人估算＝不參與 Risk Cap 計分、可顯示＋標示 `proxy_estimate`、只有正式 PCR 契約資料可用原門檻；(4) 台灣 PMI＝不套 blanket rule，正式來源修正為正確 provenance，同一正式序列 secondary 可滿足 Core（揭露來源），carried_forward 只在**正式定義**的發布期內並顯示「沿用」，超過 → unavailable → 不產生新 cap；⛔ 不自定發布期天數（現有規則是否構成正式定義待確認：`docs/BACKLOG.md` `DH-PMI-PUBLICATION-WINDOW-SPEC`）；(5) 7 天沿用要揭露，屬 `RC-VISIBILITY`、先線框；(6) **先 C2a 再 C2b**：C2a＝observability／contract implementation（零投資輸出變更，高能力模型／Effort High／完整 QA），C2b＝C2a 觀測結果後另送 Decision Gate、未另行裁示不得改計分。`DEC076-CONFIRM` ①② 維持 pending、與 C2 分開。⛔ 現行仍禁止：C2b、C1′、DEC-076 ①②、Risk Cap 公式／門檻／權重／Required Core 數量、production write（`PRODUCTION_WRITE_APPROVED=False`）、Daily Schedule、`RC-VISIBILITY` 正式 UI、新增或替換 production source。
