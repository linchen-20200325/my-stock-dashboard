# PROJECT_STATE — 目前仍有效的專案知識（my-stock-dashboard）

> **定位**：ChatGPT 與 Claude 共用、「**目前仍有效**」且下一個沒有舊聊天記憶的 AI 必須知道的專案知識（客戶 2026-10-22 裁示，`docs/DECISIONS.md` DEC-068；分工見 `PROJECT_RULES.md` §0.3、§15）。
> **原則**：本檔「**保存專案知識，不保存聊天紀錄**」。
> **不是什麼**：不是 BACKLOG（未完成工作只在 `docs/BACKLOG.md`）、不是 HANDOFF（current／blocker／next safe point 只在 `docs/HANDOFF.md`）、**不取代 DECISIONS**（正式裁示只在 `docs/DECISIONS.md`）。本檔只做摘要＋出處；與出處不一致時**以出處為準**。
> **優先序**：本檔的狀態快照**低於** GitHub 實況與 `docs/HANDOFF.md`（`PROJECT_RULES.md` §15）。
> **量測**：~~2026-10-22；量測時 `origin/main`＝`d3a3e676`（cron tip；最後非 cron 合併＝#898 `1d9e6c1c`）~~ 2026-10-22T18:57Z；量測時 `origin/main`＝`7f58a25a`（#901，最後非 cron 合併；撰寫組 `git fetch` 實查）（2026-10-22 更新，有意識的變更，不是漏刪，決策者 AI 總管（事實更正））。cron 會推進 tip，引用前重查。
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
- 〔repo 事實〕run 39755679219 log：runner yfinance 1.7.0；抓取時刻 2026-10-22T09:29:58Z（05:29:58 EDT）已得 `^VIX` 10-22 bar 18.4。
- 〔外部摘要級，未讀原文〕Cboe VIX：一般時段約 09:30–16:15 ET；自 2016-04 起美東約 03:00（另有 03:15 之說）–09:25 ET 也發布 VIX 指數值；20:15–03:00 ET 不發布（SR-CBOE-2024-031）。Cboe 官方「日收盤值」定義時點**查不到原文**。〔推論〕05:28 ET 那根是 GTH 盤中暫定值。
- 〔原始碼已讀：yfinance 1.7.0〕`utils.fix_Yahoo_returning_live_separate` 不濾除當日 live bar；日線無盤前過濾；issue #2353：當日 live 列存在與否取決於 period 參數；issue #2704：`^VIX` info 欄位曾回錯值（不可當判據）。
- 〔tzdata 計算〕美國 2026-11-01 結束夏令時間；VIX 16:15 ET＝台北 04:15（夏令）／05:15（標準）；GTH 03:00 ET＝台北 15:00（夏令）／16:00（標準）。

**veto 留痕**
- 〔repo 事實〕`src/services/macro_state_locker.py::calculate_system_state` 已計算 `veto_flags`（opt-in `include_veto_flags=True`，唯一呼叫點 `src/services/risk_cap_apply.py`）；VALID 寫快照時含 `veto_flags`、`red_lines`、`input_detail`（值／status／as_of）；但 `src/services/risk_cap_history_service.py::build_record` 不讀這些欄位。
- 〔repo 事實〕workflow `.github/workflows/risk_cap_history_poc.yml` 只上傳 record JSON（保留 14 天），快照未上傳；無頭執行時步驟 detail 不印。**完全未保存**：MA5 數值與加權指數收盤（`dated_inputs.extract_ma5` 只存 bool）、否決前曝險值、各計分項分數。
- 〔repo 事實〕`shared/risk_cap_history_policy.py::HISTORY_COLUMNS` 20 欄、`HISTORY_SCHEMA_VERSION`＝`risk_cap_history.v1`；`input_asof` 只有日期無時刻；`snapshot_timestamp` 為台北 naive；無每項輸入的 fetched_at／available_at。`tests/test_batch_z65.py` 釘死 `veto_flags` 鍵集合 ⇒ trace 須另開鍵；讀端逐字比對表頭 ⇒ 改 schema 時寫端與網站須同版部署。

**PIT／跨輸入一致性**
- 〔repo 事實，單組 grep〕全 repo 無跨輸入日期一致性檢查；MA5＝`src/services/market_strategy.py::get_market_assessment` 取 yfinance 最後 5 列 rolling mean，不對照交易日曆；`src/data/daily/daily_data_fetchers.py` 的 `dropna(subset=['close'])` 不 log 筆數。
- 〔repo 事實〕台股交易日曆已存在（`src/data/stock/twse_holiday_fetcher.py`、`shared/trading_days.py`、`src/services/trading_calendar_service.py`；不含颱風臨時休市、只拿當年表）；無美股交易日曆。
- 〔外部摘要級，未讀原文〕TWSE 收盤 13:30，暫緩收盤至 13:33。〔二手：CMoney／HiStock〕期交所 13:45 收盤商品（含 TX）未平倉約 15:00 後揭示（2021-12 新制），官方原文未找到。〔外部摘要級，官方 Q&A〕夜盤交易量與未平倉併入次一交易日。⇒ 台北 16:00 只是**保守執行時間／Candidate**（DEC-070；驗證見 `VN1-PG-CUTOFF-VERIFY`）。
- 〔未驗證〕Yahoo 實測全部未做（沙箱 proxy CONNECT 403）；Yahoo 早上缺 ^TWII 只有 1 次觀測（run 39695843255）。未驗證項清單見 `VN1-PG-YAHOO-PROBE`；其他技術缺口見 `VN1-PG-L-PIT-GAPS`。

**技術方案候選**（研究建議、非客戶裁示、未實作；實作批仍須客戶指派）
- VIX：總管推薦「取美東日期早於 D 的最後一根」（前一個已收盤美股交易日）—— ⚠️ 這是符合 DEC-070 語意的**一種候選實作**，**不是客戶裁示**；替代為美東牆鐘＋收盤 cutoff、Yahoo metadata（未實測，只能當交叉檢查）。
- VETO-TRACE：推薦混合方案 C（歷史紀錄新增精簡 trace 欄位、schema 只增不改；完整快照另上傳 artifact；非 VALID 列也帶 trace）。
- PIT：錨定 D 依證交所日曆；台股輸入 as_of＝D（以資料日期驗證）；MA5 五根對得上交易日曆、缺一根＝無法評估；MA5／BIAS240 共用同一次 ^TWII 抓取；`dropna` log 筆數。
- 細節與剩餘待辦：BACKLOG `VN1-PG-VIX-ASOF`／`VN1-PG-VETO-TRACE`／`VN1-PG-PIT-CONSISTENCY`。

## 11. Market Regime／Market State 的定位

- 現行 `market_regime`（多頭／震盪／空頭）是 Risk Cap 引擎依上限分級的**輸出**（§4），不是獨立模型；`macro_state_locker.normalize_regime` 做中→英正規化。
- Regime 作為 Context（非 Core）：`VN-23`，Research Candidate；Context 升 Core／hard veto 須客戶裁示（DEC-009；D18）。
- 「Market State」：**GitHub 無定義來源**；Regime／State／Conflict Resolver 的統整為候選 `VN1-C-REGIME-RESOLVER`。

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
- 更廣的「自動來源 vs Proxy」原則：**GitHub 無定義來源；不得推測。**（注意：此處 Proxy 指代理值，不是 NAS 網路 proxy。）

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

## 21. 治理入口（只列指標）

- 新對話啟動、優先序、Handoff Save Check、Context Loss Check：`PROJECT_RULES.md` §15（DEC-067、DEC-068）。
- 靜默自主巡航與回報格式：`PROJECT_RULES.md` §3（DEC-059、DEC-060）；客戶回報語言：DEC-069。
- Minimum Sufficient Effort 與階段邊界 Effort Check：`PROJECT_RULES.md` §9（DEC-059、DEC-061）。
