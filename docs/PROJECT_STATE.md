# PROJECT_STATE — 目前仍有效的專案知識（my-stock-dashboard）

> **定位**：ChatGPT 與 Claude 共用、「**目前仍有效**」且下一個沒有舊聊天記憶的 AI 必須知道的專案知識（客戶 2026-10-22 裁示，`docs/DECISIONS.md` DEC-068；分工見 `PROJECT_RULES.md` §0.3、§15）。
> **原則**：本檔「**保存專案知識，不保存聊天紀錄**」。
> **不是什麼**：不是 BACKLOG（未完成工作只在 `docs/BACKLOG.md`）、不是 HANDOFF（current／blocker／next safe point 只在 `docs/HANDOFF.md`）、**不取代 DECISIONS**（正式裁示只在 `docs/DECISIONS.md`）。本檔只做摘要＋出處；與出處不一致時**以出處為準**。
> **優先序**：本檔的狀態快照**低於** GitHub 實況與 `docs/HANDOFF.md`（`PROJECT_RULES.md` §15）。
> **量測**：~~2026-10-22；量測時 `origin/main`＝`d3a3e676`（cron tip；最後非 cron 合併＝#898 `1d9e6c1c`）~~ ~~2026-10-22T18:57Z；量測時 `origin/main`＝`7f58a25a`（#901，最後非 cron 合併；撰寫組 `git fetch` 實查）~~ ~~2026-10-22T20:41Z；量測時 `origin/main`＝`08272e5`（#902，最後非 cron 合併；撰寫組 `git fetch origin main` 實查）（2026-10-22 更新，有意識的變更，不是漏刪，決策者 AI 總管（事實更正））。~~ **現行**：2026-10-29；量測時 `origin/main`＝`978ecedc`（cron；最後非 cron 合併＝#969 `71587857`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留）。cron 會推進 tip，引用前重查；各節舊量測值為歷史。
> **標示**：「Approved」＝有 DEC 或硬規則出處；「Candidate／Decision Gate」＝未核准；「GitHub 無定義來源」＝不得推測，待客戶提供或研究後經 Decision Gate。
> ⚠️ 本檔由單一撰寫組撰寫（`CLAUDE.md` §-2 規則 6）；各段結論以所附出處為準。⛔ 本檔不含任何 secret、credential、private key。

## 1. North Star／產品定位

- 產品方向「投資決策 OS／Investment Inbox」—— **只核准方向，不是實作授權**（DEC-056）。客戶接手提示另稱「Decision-first Investment OS」；撰寫組讀法（非客戶明示）：兩者指同一方向。
- North Star 客戶原文：「每天替使用者過濾市場噪音，只把真正需要做決定的事情送到面前；每個結論都可以一路追溯到正式規則與客觀資料。」（`docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md` §1）
- 反北極星：「不要把專案做成：更多資料＋更多指標＋更多卡片＋更多 Gate＋更多 AI 文字」（同上）。
- Blueprint 是方向承載者，不帶 Decision 效力、不是施工授權（DEC-057；`PROJECT_RULES.md` §0.3）。

## 2. 產品階段與 roadmap

- 路線 vNext 0.9 → 1.0 → 2.0 → 3.0（Blueprint §20）。~~**目前階段＝vNext 1.0**（DEC-062；`docs/HANDOFF.md` §1）。~~ **現行（2026-10-29）**：新 UI 主線為 D2.5（DEC-091／092）→ 四頁 UI-M／UI-T 已合併 → **DEC-109 Phase 1 SSOT Reset／Contract Freeze**，其後 Phase 2～7（見 §48）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留）。
- 1.0 已裁示範圍：DEC-062 Q1～Q5（全文見 `docs/vnext/VNEXT_1_0_DECISION_GATES.md`）。
- 1.0 建議批次現況（`VNEXT_1_0_DECISION_GATES.md` §6；建議不是授權）：`1.0-B1` 安全地基完成（#877）；`1.0-B2` 靜默恢復登入程式已合併（#879），待客戶正式網站驗收（`B2-FU-1`）；`1.0-B3` 保存方式研究完成（#881）→ 延伸為 `VN1-STORE` 主線（DEC-063～066）；~~`1.0-B4` 線框送審**未開始**。~~（1.0-B4 線框已由 D2.5 線框 `docs/vnext/d25_wireframes/` 與 DEC-092 核准取代）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留）
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
- Scope Inflation Guard（新發現分 P0／P1／P2，P2 只登記不插隊、不因此開新 Stage）：`PROJECT_RULES.md` §23（DEC-103，客戶 2026-10-28；append-only）。

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

> 📌 **2026-11-03 DEC-125 後註（append-only；§22 上文一字未改）**：客戶 2026-11-03 (10) A1／A2 再確認並擴充台股／國際維度清單（台股新增融資／市場擁擠度／回撤與市場風險／市場廣度；國際新增殖利率曲線／PMI／Inflation／Fed／Real Yield／VIX／Credit Spread／USD／Major Equity Markets），正式 Research Baseline 見 `docs/vnext/MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md`（與本節 22.2 取聯集，不取代）；規則見 `PROJECT_RULES.md` 第 28 節。

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
- ~~**現行仍照舊**：DEC-017 五頁（`shared/ia_nav.py::PAGE_LABELS`）在新線框經 DEC-003 拍板前仍為現行實作依據；DEC-062 Q1 四格送審範圍待依新方向調整（原條不刪）；~~ **現行（2026-10-29）**：四主導航 📊 市場／🎯 標的／💼 持股／👤 我的（DEC-091 §二／DEC-092／DEC-097；`shared/ia_nav4.PAGE4_LABELS`）為預設；DEC-017 五頁與本節「⚡ 行動、🩺 資料中心」頁面結構已被取代（`docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）；「底層能力完整，前台流程極簡」原則仍有效（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留）；舊 UI 不改不刪（DEC-019／020）。
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
- **已裁示（DEC-080，客戶 2026-10-24；append-only）**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）：裁示逐字全文只在 `docs/DECISIONS.md` **DEC-080**；Gate 各題標記見 `docs/vnext/VNEXT_1_0_DECISION_GATES.md` §7.4／7.7；施工列見 `docs/BACKLOG.md` 5.1.10 **C2a**／**C2b**。摘要：(1) 資料身分／計分契約＝**方案 2**（provenance 與 freshness 分開；as_of、source_id；exists／fresh／displayable／scoring eligible／Risk Cap eligible 不得壓成同一 boolean）；(2) BIAS240 估算＝不參與 Risk Cap 計分、可顯示＋標示、Optional 未評估、不阻斷；(3) PCR 法人估算＝不參與 Risk Cap 計分、可顯示＋標示 `proxy_estimate`、只有正式 PCR 契約資料可用原門檻；(4) 台灣 PMI＝不套 blanket rule，正式來源修正為正確 provenance，同一正式序列 secondary 可滿足 Core（揭露來源），carried_forward 只在**正式定義**的發布期內並顯示「沿用」，超過 → unavailable → 不產生新 cap；⛔ 不自定發布期天數（總管判定現有規則不構成正式定義；C2a 記為 `undetermined_pending_spec`、不自定數字；規格提案於 C2a 觀測後隨 C2b Gate 送客戶：`docs/BACKLOG.md` `DH-PMI-PUBLICATION-WINDOW-SPEC`）；(5) 7 天沿用要揭露，屬 `RC-VISIBILITY`、先線框；(6) **先 C2a 再 C2b**：C2a＝observability／contract implementation（零投資輸出變更，高能力模型／Effort High／完整 QA），C2b＝C2a 觀測結果後另送 Decision Gate、未另行裁示不得改計分。`DEC076-CONFIRM` ①② 維持 pending、與 C2 分開。⛔ 現行仍禁止：C2b、C1′、DEC-076 ①②、Risk Cap 公式／門檻／權重／Required Core 數量、production write（`PRODUCTION_WRITE_APPROVED=False`）、Daily Schedule、`RC-VISIBILITY` 正式 UI、新增或替換 production source。

## 32. 2026-10-24 Safe Checkpoint：current-valid knowledge 核對與 AI 總管接手須知（append-only）

> 2026-10-24 新增（DEC-079 預判性 Safe Checkpoint；決策者 AI 總管（事實更新））。本節**不是新 SSOT**：只放 pointer 與狀態更新；規則本文只在 `PROJECT_RULES.md`，裁示只在 `docs/DECISIONS.md`，待辦只在 `docs/BACKLOG.md`，current／next 只在 `docs/HANDOFF.md`。量測：撰寫組 `git fetch`＋`gh api` 實查 main＝`74dc891d`（#918）、Open PR＝0、main CI run 40085401541 success（會過期，引用前重查）。

### 32.1 current-valid knowledge 核對（撰寫組 grep，已存在者只給 pointer）

| 主題 | 狀態 | 出處 |
|---|---|---|
| 新 UI 核心方向（📊 大盤、🎯 標的、⚡ 行動、🛡️ 持股；👤 我的＝輔助；🩺 資料中心＝維護頁；「憑什麼」改 contextual explainability） | 已存在 | §29.1；DEC-072、DEC-076 |
| 舊 UI＝能力／邏輯參考；舊→新 capability coverage 驗證後才可進移除 Gate | 已存在 | §29.1；`PROJECT_RULES.md` 16.5；BACKLOG 5.1.9 `UIM-*` |
| 台股趨勢與國際趨勢必須保留（兩主軸，仍無正式定義） | 已存在 | §22.1、§29.2；DEC-071；BACKLOG `VN1-MT-TREND-DEF` |
| 蕭碧燕 EPS 預估大盤研究方向（Research Framework，非 Approved）與未完成點（大盤 EPS／PE、CAPEX→EPS、殖利率×領先指標皆未落地） | 已存在 | §22.2、§22.4；BACKLOG 5.1.6 `VN1-MT-VALUATION`／`VN1-MT-CAPEX-EPS`／`VN1-MT-YIELD-CLI` |
| Risk Cap、台股趨勢、國際趨勢、市場位階、指標危險度彼此分離，不得合成單一分數 | 已存在 | §22.3、§29.2 |
| C1 已完成內容 | 已存在 | §30.9（#913） |
| DEC-080／C2a 正式語意 | 已存在 | §31 末條；DEC-080 |
| **C2a-1 已完成、未接線** | **本節新增（事實）** | PR #918（squash `74dc891d`）：新增 `shared/input_provenance_policy.py`（L0 兩軸政策表）、`src/compute/macro/input_provenance.py`（L2 純函式）、`tests/test_c2a_input_provenance.py`；產品碼零引用、零投資輸出變更；`is_proxy` 未翻轉、`RISK_CAP_RULESET_VERSION` 未動；PMI carried_forward 記 `undetermined_pending_spec`。C2a-1／C2a-2 切分為總管技術切分（出自 PR #918 描述），非客戶裁示 |
| ~~**C2a-2 尚未開始**~~ **C2a-2 已實作（PR #920），見 §33**（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） | **本節新增（事實）** | 前一對話本機草稿從未提交 GitHub、已遺失 ⇒ 須重新實作；六點稽核發現見 BACKLOG 5.1.10 C2a-2 列 |
| 下一步 | 指標 | 新對話須先做 GitHub Verification Gate，才進 C2a-2（`docs/HANDOFF.md` current handoff 段） |

### 32.2 AI 總管接手須知（接手操作規則與 current context；來源：客戶 2026-10-24 交接指示，經總管轉交；已有正式規則者以 pointer 引用）

1. 每次判斷前，AI 總管也須**獨立查 GitHub**（main／PR／CI），不得只信 subagent 回報或交接文件 —— `PROJECT_RULES.md` 第 2 節、第 15 節第 3 點；`CLAUDE.md` §-2 規則 3。
2. `docs/HANDOFF.md` **只作參考、不是事實來源** —— `PROJECT_RULES.md` 第 1.3 節、第 15 節第 3 點第 4 款。
3. 使用者偏好：繁體中文（DEC-069，第 3 節）；極簡回報（DEC-060，原則 ≤5 行）；**表格優先**（本則僅出自客戶 2026-10-24 交接指示，repo 無既有 DEC）；Claude 靜默自主巡航（第 3 節、16.3）。
4. 給 Claude 的提示語須附**建議模型與建議 Effort**（客戶 2026-10-24 交接指示；相鄰規則：第 9.0 節、第 15 節第 6 點）。
5. 額度／context 預判偏高時，提前到 Safe Checkpoint、文件落盤後再結束對話換新對話 —— 第 11 節「預判性觸發」（DEC-079）。
6. **資料 ≠ AI 推理**為永久原則 —— 第 13 節 D3／D4、16.1。
7. 不可因 context loss 重開已完成工作（例：C1、C2a-1 已合併，不重做）—— DEC-014「不重新摘要；不重問；不重做」、第 11 節。
8. 下一對話從 GitHub SSOT 接手，**不要求客戶重講** —— 第 11 節、第 15 節。

⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組撰寫；「已存在」為 grep＋讀檔結果，未經第二組驗證；C2a-2 稽核發現與 C2b 推算觀察為總管轉述，撰寫組未見稽核報告。

## 33. C2a-2 接線觀測（2026-10-24；append-only）

> 2026-10-24 新增（決策者 AI 總管（事實更新））。本節**不是新 SSOT**：裁示只在 `docs/DECISIONS.md` DEC-080（含執行紀錄 C2a-2 點）；待辦與新發現只在 `docs/BACKLOG.md` 5.1.10 C2a-2 列與 5.1.12；current／next 只在 `docs/HANDOFF.md`。量測：撰寫組 2026-10-24 21:47 台北 `git fetch`＋`gh api` 實查（會過期，引用前重查）。

| 主題 | 內容 | 性質 |
|---|---|---|
| 授權與停點 | DEC-080 C2a；客戶 2026-10-24：「同意，請切換到 Effort High 後開始 C2a-2…完成 C2a-2 後停手，不自動進 C2b。」 | 客戶指示（經總管轉交） |
| PR | #920（branch `claude/determined-euler-32xqjn`；首個 commit `981e2f69`＋QA 修正 commit，SHA 見 PR #920）；撰寫時 open、mergeable clean、`981e2f69` CI Fast＋Slow success；**合併狀態以 GitHub 為準** | 事實（撰寫組實查） |
| 做了什麼 | `src/services/risk_cap_apply.py::compute_and_lock_risk_cap` 只在三道閘門後的寫檔分支，於本機 `risk_cap_state.json`、`macro_state.json` 附加觀測欄 `input_provenance_shadow`（L2 `infer_input_provenance` 輸出，`shadow_policy_version`＝`c2a-shadow-1`）；未寫檔輪次不記錄。失敗 → `{"_error": <型別名>, "_stage": import／pmi_history／session／infer／sanitize／validate}`＋安全 log（`shared/na_drop_log` 公開別名 `safe_print` —— ⚠️ 該別名自 QA 修正 commit `dc2fa365` 起才存在，`981e2f69` 時為跨模組取 `_safe_print`（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更正））；log 失敗走 `_log_error`），⛔ 不改寫檔成敗 | 事實（PR #920 規格；總管轉述） |
| 六點稽核發現落實 | utf-8 encode 自驗；字串上限 `SHADOW_STR_MAX_LEN=512`（技術常數，非投資參數）；延遲 import；安全 log；呼叫點在閘門後；C2a 還原鏈頭在 `c1_revert_for` 前＋before／after 網格＋讀者守衛＋失敗注入 | 事實（總管轉述） |
| PMI 歷史 | 自同一本地 L1（`macro_cache_reader.load_tw_pmi_history`）再讀一次，無新來源。已知限制：cron 可能在兩次讀取之間替換 parquet（只影響觀測欄） | 事實＋已知限制 |
| 零投資輸出變更證據 | 實作組網格（22 具名＋120 隨機）；QA-A 獨立 harness 1937 情境（1183 寫檔／740 不寫檔／14 同例外）對 base `0a78f308` 0 差異（含落盤 bytes 扣除新欄、`get_macro_state` 三模式）；QA-B 對抗注入（怪型別、遞迴、surrogate、壞 stdout、cp950）皆照常寫檔且核心一致；突變測試。fast 30027 passed／28 skipped（base 29969）（`981e2f69` 時點；`dc2fa365` 後 30039 passed／28 skipped，實作組自測（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更正）））；slow 120 passed／5 skipped | 總管轉述（撰寫組未重跑） |
| 讀者 | production 無任何讀者讀新欄（grep＋讀碼；QA 單組結論） | ⚠️ 單組，未經第二組驗證 |
| 未變 | Risk Cap 數值、計分資格、Required Core、門檻／公式／權重、regime／燈號、`RISK_CAP_RULESET_VERSION`、`ENGINE_SOURCE`、`is_proxy`、`PRODUCTION_WRITE_APPROVED=False`（撰寫組 grep `shared/risk_cap_history_policy.py` 實查）、Google Sheet 寫入、UI | 事實（旗標實查；其餘總管轉述） |
| 下一步 | 合併後：取得真實寫檔輪次的觀測結果 → 準備 C2b Decision Gate（客戶裁示；⛔ 不得開始 C2b）；建議高能力模型／Effort High | 指標（`docs/HANDOFF.md`） |
| QA 修正（📌 2026-10-24 追加（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更正））） | `dc2fa365`：`shared/na_drop_log.py` 新增公開別名 `safe_print`（純別名）；錯誤標記讀端比對；BaseException 往外拋／非 str dict 鍵／list・tuple 分支補測；`_exc_type_name` 失敗時記 `<unrepresentable>`；`tests/test_c2a_risk_cap_shadow.py`（新檔，相對 main）70 tests（實作組自測，含參數化；撰寫組 grep `def test_` 35 個） | 事實（commit 實查）＋測試數總管轉述 |

⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組撰寫；測試數字、QA 結論、讀者判斷為總管轉述，撰寫組只實查 PR 狀態、CI、旗標與 working tree，未重跑測試、未見 QA 原始報告。

<!-- PROJECT_STATE_HISTORY_INDEX:BEGIN lines=613-621 archive=docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q2；只搬不改）**：原 L613–L621 已逐字搬至 `docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md`（分冊 L10–L18）。本處原為下列 1 節（標題逐字）：
  - 原 L613–L621 → [分冊 L10–L18](archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md#ps-hist-34)：## 34. 📊 大盤頁 Decision Gate 草稿（2026-10-24；append-only；~~**非 Approved**~~ **Q1～Q4 已裁示 DEC-081**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-081））
<!-- PROJECT_STATE_HISTORY_INDEX:END -->

## 35. 📊 大盤頁裁示與「互動控制完整性」完工條件（DEC-081，客戶 2026-10-25；append-only；**Approved**）

> 2026-10-25 新增。裁示逐字（摘錄）只在 `docs/DECISIONS.md` **DEC-081**；待辦只在 `docs/BACKLOG.md` 5.1.6（`VN1-MT-HOME`／`VN1-MT-IA` 補註）與 **5.1.13**（`UIX-*`）。本節只放摘要＋pointer，與 DEC-081 不一致時以 DEC-081 為準。

- **⭐ 互動控制完整性＝每一個新 UI 頁的完工條件**（客戶原文：「新版不能只『看』，必須能『操作』」；「新版 UI 完工條件必須包含『互動控制完整性』——不能缺按鈕、輸入框、搜尋、Sheet 選擇、持股綁定、更新操作」）。任何新 UI 頁（📊／🎯／⚡／🛡️／👤／🩺）只有畫面、缺舊 UI 既有的操作入口時，**不算完工**；驗收依 `UIX-INTERACTION-COVERAGE`（Old→New Interaction Coverage Matrix）。各頁應承接的互動清單見 DEC-081 第 7 點。
- **⛔ 禁止 dead-end**：頁面要求使用者做某事（例：選 Sheet）時，必須在該頁提供操作或明確入口（🛡️ 持股 → 👤 我的）。
- **Sheet CRUD 單一 SSOT 流程**：不可照搬三套；先查既有 backend／service 能否共用；舊 Sheet CRUD 依 Old capability → New coverage → regression → customer verification → removal Decision Gate 才可刪（`UIX-ME-SHEET-SSOT`；Sheet 寫入／OAuth／權限模型屬 High）。
- **頁面分工**（DEC-081 Q1、Q4）：📊 大盤回答「現在市場環境如何？目前適合承擔多少風險？」；⚡ 行動回答「今天有哪些事情值得我採取行動？」（承接作戰室，`UIX-ACTION-PAGE`）；🩺 資料中心＝資料健康／freshness／provenance／更新／來源狀態／缺值與抓取異常／資料維護；🎯 標的＝選股／個股搜尋／板塊／候選標的／個股健康檢查；🛡️ 持股＝持股／曝險／集中度／組合健康／資產配置・壓力測試。舊 UI 歷史綜合結論句暫不搬、也不刪。
- **大盤首屏**：結論句放（「；」並列、不硬做因果、missing／unavailable／未評估明寫、missing 不當中性）；Risk Cap 卡位放，卡面「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」、⛔ 不顯示未核准獨立數字、不自行推導值；三欄摘要移除（只移除新版 UI 元件，不刪底層能力或歷史程式）；台股／國際趨勢卡只顯示「尚未定義」（定義走 `VN1-MT-TREND-DEF`）。
- **舊 UI**：新版大盤頁正式驗收完成前，舊今天頁不得刪除；本批不刪舊 UI、不刪舊 Sheet CRUD（DEC-019／020、`UIM-REMOVAL-GATE`）。
- **仍禁止**（DEC-081 第 10 點）：開始 C2b；顯示未核准 Risk Cap 獨立數字；改 Risk Cap 計算／scoring eligibility／Required Core／公式／權重／門檻；自行定義趨勢；新增 EPS 來源；大規模刪 code；`PRODUCTION_WRITE_APPROVED=False` 不變。本批 Effort＝Medium，遇 DEC-081 第 9 點所列事項 → 停在安全點、告知升 High。

⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組撰寫；客戶原文為總管轉交的關鍵句、非全文；「實作批進行中」為總管轉述，撰寫組未查 PR。

## 36. 📊 大盤頁實作批與互動覆蓋矩陣初稿（2026-10-25；append-only；**實作完成、~~未驗收~~ 已合併 #922、待客戶驗收**（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管））

> 2026-10-25 新增（決策者 AI 總管（事實更新））。本節只放摘要＋pointer，不是新 SSOT。裁示見 `docs/DECISIONS.md` DEC-081；待辦見 `docs/BACKLOG.md` 5.1.13；交接見 `docs/HANDOFF.md`「2026-10-25 大盤頁實作批」段。

- **實作**：分支 `claude/determined-euler-32xqjn` @ `6dad38cb`（main `5e2e6e23`＋2 commit；**尚未開 PR、未合併、CI 未驗**，撰寫組 2026-10-25 10:00 台北 `gh api` 實查）。新增 `src/ui/views/page_market.py`（L5）、`shared/market_conclusion.py`（L0）；「📊 大盤」排在導覽第一；「🚦 今天」頁零改動、兩頁並存（DEC-081 Q1＝C）。Gate 檔 W1～W9、X1～X11 已做；全球資金流向、全球風險雷達、外資連續天數、熱錢三角、櫃買、跨頁狀態列未接（`UIX-MKT-*`）。施工結果全文：`docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md` 附錄 D。
- **互動覆蓋矩陣初稿**：`docs/vnext/INTERACTION_COVERAGE_MATRIX_2026-10-25.md`（179 個舊 widget 呼叫點 → 六個目標頁；Sheet CRUD 單一 SSOT **提案**；🛡️ dead-end 清單）。重點發現：Sheet URL→ID 解析有 4 份、行為不一致；側欄綁定是獨立 inline 複本；🛡️ 持股有多處指向新版模式下不存在的 📁 組合管理分頁。
- **下一步**：獨立 QA → 客戶驗收 📊 大盤頁 → 客戶指派下一頁（總管推薦 👤 我的／Sheet SSOT，屬 High）。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：矩陣與本節由單一組產出，**沒有第二組驗過**；矩陣「沒有遺漏」未證明，dead-end 清單已知不完整；大盤頁未經 Streamlit 實機驗收。大盤頁直接呼叫 `page_today` 的底線函式，屬已知耦合（`UIX-MKT-TODAY-COUPLING`）。
- 📌 **QA 回修 done**（2026-10-25；append-only）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管）：commit `ad09a04d`——結論句風險上限子句改客戶逐字、位階／危險度子句對齊卡面字樣與徽章、指路修正、X1 來源代碼改人話、X8 三大法人資料日與先行指標沿用揭露、BIAS240 改用 L2 helper（全文見 Gate 檔附錄 D.5）。測試（**實作組自跑**，~~獨立複驗進行中~~ 獨立 QA-A 已複驗，見下一點（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管））：fast 30119 passed／28 skipped／0 failed；slow 122 passed／5 skipped／0 failed。QA 非阻擋項已登記 BACKLOG 5.1.13 `UIX-MKT-*`。下一步：~~最終 head CI → merge → 客戶驗收 📊 大盤頁 → 客戶指派下一頁（推薦 👤 我的，High）~~ 見下一點（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管）。舊 UI 未刪、C2b 未開始、`PRODUCTION_WRITE_APPROVED=False` 未變。
- 📌 **#922 已合併**（2026-10-25；append-only）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管）：獨立 QA-A 於 `ad09a04d` 複驗判可合併（fast 30119 passed／28 skipped／0 failed）；PR head `88ccb364` 與 main `286e0075` CI 皆綠；Open PR＝0。下一步：**客戶驗收 📊 大盤頁**；👤 我的只做草稿（Stage A／B），不實作。
- 📌 **客戶指示（2026-10-25，永久規則；DEC-082）**：所有下一頁先草稿、後施工 —— 新主要頁面／重大互動流程（🎯 標的、⚡ 行動、🛡️ 持股、👤 我的、🩺 資料中心、contextual explainability、Sheet 管理／綁定、Google 登入／連線、跨頁互動控制）一律 Stage A 唯讀盤點（⛔ 不寫正式 UI code）→ Stage B 新版設計草稿 → Stage C 客戶裁示 Gate（草稿完成必須停手）→ 核准後才 Stage D 實作。全文見 `docs/DECISIONS.md` DEC-082。
- 📌 **👤 我的 Stage A／B 草稿 done**（2026-10-25；append-only）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管）：`docs/vnext/ME_PAGE_DRAFT_2026-10-25.md`（盤點＋文字線框＋7 題裁示）；PR #923 已合併（main `c9d8419a`）；**等客戶 Stage C 裁示 Q1～Q8**，核准前不進 Stage D。

## 37. 👤 我的 Stage C 裁示（DEC-083，客戶 2026-10-25；append-only；**Approved**）

> 2026-10-25 新增（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-083）。本節只放摘要＋pointer，不是新 SSOT。裁示全文（逐字）見 `docs/DECISIONS.md` DEC-083；待辦見 `docs/BACKLOG.md` 5.1.13；交接見 `docs/HANDOFF.md`「📌 2026-10-25 👤 我的 Stage C 已裁示（DEC-083）」；草稿 `docs/vnext/ME_PAGE_DRAFT_2026-10-25.md` 狀態改「已裁示」。

- **Q1～Q8 全採 A**：側欄獨立「👤 我的」為帳號／Sheet 綁定／Sheet SSOT 唯一入口；P1 只做登入／登出／重新登入、Sheet URL／ID、Drive 清單、明確選擇／切換、重新讀取、active Sheet／portfolio／watchlist（建立／rename／刪 Sheet 與各類 CRUD 留 P2，另開 Stage A/B/C）；先做 Sheet Safety 批；顯示「Sheet 名稱＋ID 末 6 碼」；登出全清（含 OAuth state 攜帶的舊 Sheet ID、silent marker），不得自動恢復；組合與觀察清單同一本，legacy 不一致時白話警示、使用者明確重選；全站共用 active portfolio／watchlist，不再用「名稱排序第一本」。
- **Sheet Safety 修復批（High，先於 👤 我的 P1）**：B1 read 真正唯讀（明確 `UNAVAILABLE／NOT_CONFIGURED`／`SCHEMA_MISMATCH`／`EMPTY`／error）；B2 `forward_test_picks` 讀取零寫入（無法安全分離 → 停手送 Decision Gate）；B3 單一 Sheet ID parser（`/d/e/` 不得解析成 `e`，不能安全轉換 → 明確拒絕）；B4 單一綁定寫入契約；B5 重新讀取只失效本人（做不到 → 研究送 Gate）。
- **P1 開工條件**：Sheet Safety 批 QA／CI／merge／main verification 全部完成；**唯一本自動綁取消**（即使只有一本也要按「使用這本」）；P1 完成後 Sheet／登入／切換提示統一導向 👤 我的，CRUD 照客戶字樣指回舊版 📁 組合管理。
- **未變**：📊 大盤頁仍待客戶 UI 驗收，驗收前不得刪 🚦 今天；舊 UI（🚦 今天、📁 組合管理、側欄 Google、Sheet CRUD、legacy controls）全部保留，刪除須走 Removal Gate 七步；C2b 未開始；`PRODUCTION_WRITE_APPROVED=False`；不改投資公式／門檻／權重、不動不可重建歷史。
- **施工順序**：落盤 → Sheet Safety 批 → 獨立 QA → CI／merge／main → 👤 我的 P1 → 獨立 QA → CI／merge／main → 停手回報 → 不自行進 P2。
- **Sheet Safety 修復批（B1～B5）~~done in PR #926（待 CI／合併）~~ done（PR #926 已合併，squash `55601f42` on main）**（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管）：讀取真正唯讀、`forward_test_picks` 讀取／對帳零寫入、單一 Sheet ID parser（發布連結明確拒絕）、`oauth_state` 唯一綁定寫入契約（登出同步清綁定、取消唯一本自動綁）、重新讀取只失效本人×本 Sheet（helper 尚無 UI caller，留 P1）；兩組獨立 QA 各一輪回修後皆判「可合併」；殘留 11 項登記於 `docs/BACKLOG.md` 5.1.13（`SHEET-GLOBAL-CLEARS` 起）。~~下一步：merge → main verification → 👤 我的 P1 Stage D。~~ 已合併；~~👤 我的 P1 在 PR #927（待合併）~~ 👤 我的 P1 PR #927 已合併（squash `ab705fbf` on main）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）），見 §38（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組產出，**沒有第二組驗過**。

## 38. 👤 我的 P1（Stage D）實作狀態（PR #927，~~**待合併**~~ **已合併 `ab705fbf`**（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；2026-10-25；append-only）

> 2026-10-25 新增（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。本節只放摘要＋pointer，不是新 SSOT。以下 **FACT** 皆為撰寫組讀分支 `claude/determined-euler-32xqjn` @ `4e8c0876`（`git log 55601f42..HEAD`＋diff＋檔案）所得；**INFERENCE** 另標。~~PR #927 為 draft、尚未合併；撰寫組查時 head CI（Fast checks／Slow tests）in_progress。~~ PR #927 已合併（squash `ab705fbf` on main）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。待辦見 `docs/BACKLOG.md` 5.1.13 `ME-P1` 與 `NAV-PERSIST` 起 11 列；裁示見 `docs/DECISIONS.md` DEC-083（及其下方 PR #927 註）。

- **新頁（FACT）**：第 7 頁「👤 我的」`src/ui/views/page_me.py`（L5；session／widget key 前綴 `p07me_`）；L0 `shared/ia_nav.PAGE_ME`（`PAGE_LABELS` 最後一項 ⇒ 側欄 radio 最後一個）；`app.py::_ia_view_me()` late import。首屏三張卡：① Google 帳號 ② 目前 Sheet（含「🔄 切換 Sheet」：貼網址／ID、Drive 資料夾＋Sheet 清單、「✅ 使用這本」）③ 這本 Sheet 內容（組合／觀察清單選擇器、「取消選定」、哪些頁在用）；「▸ 詳細：切回舊版、已知限制」預設收合。畫面只露 Sheet ID 末 6 碼（L0 `sheet_id_tail`）、email 遮罩（`me_account_service.mask_email`）。不寫使用者 Sheet、不新增 OAuth scope。
- **L3 `src/services/me_account_service.py`（FACT）**：帳號四態（未設定／未登入／逾時／已登入，另有讀取失敗）、卡② 標題讀取（只有 `ACTIVE_OK` 才讀，用新增的 fail-loud L1 `gsheet_portfolio.read_sheet_title`）、卡③ 清單（`None`＝未知、⛔ 不寫 0）、`bind_sheet`（委派 L1 唯一寫入契約 `apply_sheet_binding`）、`select_portfolio`／`select_watchlist`（先對清單核對名稱存在才寫）、`reload_reads`（`reload_my_sheet_reads`，只本人×active Sheet）、`logout`。
- **`portfolio_binding_service.get_active_sheet()` 狀態（FACT；值 SSOT 在 L0 `shared/sheet_id.py`）**：兩格（組合／觀察清單）同一本 → `ACTIVE_OK`；兩格不同（含一格空）→ `ACTIVE_DIVERGED`；兩格都空、只有 secrets 部署預設 → `ACTIVE_DEPLOY_DEFAULT_ONLY`（**不當 active**）；都沒有 → `ACTIVE_NONE`（快照讀不出來時也回 `ACTIVE_NONE` 並帶 `read_error`）。`get_binding_state(ssot=True)` 與 `get_binding_presence()` 只在 `ACTIVE_OK` 時算綁；`get_binding_state()` 預設呼叫（舊 UI）一字不變。
- **active 選定（FACT）**：session key `_me_active_portfolio`／`_me_active_watchlist`（L0 `ACTIVE_SELECTION_SESSION_KEYS`），值 `{"sheet_id","name","skip"}`；唯一寫入者 L1 `oauth_state.set_active_selection`／`clear_active_selection`；讀取只認同一本 Sheet；Sheet ID 真的變了（`_write_binding_session`）或解除綁定（`clear_sheet_binding`）時清掉；**只活在 session**。消費端：L3 `holdings_service.get_holdings()` 改讀 `get_binding_state(ssot=True)`＋選定，沒選定 → `SELECTION_NOT_SELECTED`、**不讀任何一本**（只有一本也一樣），選定名稱不在清單 → `SELECTION_MISSING`、不讀；觀察清單改讀與組合同一本 active Sheet，另有「不使用」`SELECTION_SKIPPED`。🔍 板塊資金持股標示改為 `get_sector_flow_view(use_active_selection=True)`（同一份選定），不再讀 `etf_portfolio_rows`／個股通道整本觀察清單。
- **登出（FACT）**：L1 `oauth_state.logout_google_session()` 為側欄與 👤 我的共用的唯一一支：清 `gsheet_tokens`／`gsheet_email`／`_oauth_state` → `forget_silent_reauth()`（`?gs=` 記號）→ `clear_sheet_binding()`（兩格 session、`?sheet=`、記號、active 選定）→ 清 L0 `LOGOUT_EXTRA_SESSION_KEYS`（👤 我的 Drive 清單／選擇器／Drive 錯誤／貼 ID 框、側欄貼 ID 框）；不 rerun。新增 `build_login_url()` 的 state 夾帶的是本 session 綁定（不是 secrets 預設）⇒ 登出後再登入不夾帶舊 Sheet。限制：只管得到本分頁網址與本 session（同 `SHEET-MULTITAB`）。
- **DIVERGED 處理（FACT）**：不偷選、不覆寫。👤 我的卡② 白話警示＋兩顆明確按鈕（「✅ 使用『組合』那一本」／「✅ 使用『觀察清單』那一本」，空的一側不畫）；💼／🔍／🚦 都照實說「兩本不同」並指到「👤 我的 › 目前 Sheet」（殘留：💼 本數卡標題仍是「還沒有可以數的 Sheet」，見 `ME-HOLD-COUNT-DIVERGED`）。
- **dead-end 改寫（FACT）**：Sheet／登入／切換類指路改為 `ia_nav.where_to_find(SECTION_ME_*)` 組出的「👤 我的 › …」（💼 `page_hold`、🚦 `page_today.SHEET_UNBOUND_WHERE`、🔍 `page_find` 持股標示來源）；要改內容類（新增組合、補張數／均價、管理觀察清單、唯讀說明）改為客戶 D 段原句 `ia_nav.CONTENT_EDIT_OLD_UI_WHERE`「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」（💼 `_edit_where`；卡面只摘前半，見 `ME-HOLD-CARDFACE-PHRASE`）；`CASH_WATCHLIST_ONLY_WHERE` 不再指回自己的唯讀葉。側欄在新版模式：說明改指 👤 我的、`✅ Sheet ID` 只顯示末 6 碼、貼 ID 框不預填也留不住完整 ID；~~「不使用」模式一字不變。~~ 「不使用」模式畫面行為不變（只在從新版切回時把框重設為目前綁定 ID）（`075e8da7` 起以 Session State API 明確指定框值）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。入口都是**文字**，沒有可點的跳頁按鈕。
- **未變（FACT）**：舊 UI 全部保留（側欄 🔐 Google 帳號、📁 組合管理、`portfolio_binder`、🔗 狀態列、Sheet CRUD）；舊 UI 仍經 `_get_active_sheet_id` 退回 secrets 預設；`restore_sheet_binding_from_query` 未改；`get_sheet_title` 未改（仍吞例外，0 production caller）；P2 CRUD 未開始；C2b 未開始。
- 📌 **head 前進**：本節讀碼基準 `4e8c0876`；撰寫組再查時 head 為 `075e8da7`，該 commit 只改 `app.py` 側欄貼 ID 框（改以 `st.session_state[key] = 值` 明確指定：新版模式指定為空字串、從新版切回「不使用」時指定為目前綁定 ID）＋2 個測試檔（`git diff --stat 6fd083e4..075e8da7`），本節其餘 FACT 不受影響（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
- **INFERENCE／未驗**：撰寫組沒有在 Streamlit 實機看過 👤 我的；「最多 3 次 Google 讀取／rerun、失敗不退避」為讀碼推論（`ME-READ-BACKOFF`）。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組產出，**沒有第二組驗過**；「舊 UI 全部保留」「入口都是文字」等全稱句為撰寫組 diff／grep 所得，未經第二組驗證。

## 39. Long-lived UI × Sustainable Logic（DEC-085，客戶 2026-10-26；append-only；Approved）

- 客戶 2026-10-26 立永久治理規則 10 條：UI 穩定／資料來源可替換、頁面責任長期穩定、SSOT、規則模組化、AI 可替換、能力守恆（Old→New Coverage）、Data Contract 優先、Missing 語意永久一致、Presentation 與 Decision Logic 分離、可演進不凍結。
- 六頁（📊 大盤／🎯 標的／⚡ 行動／🛡️ 持股／👤 我的／🩺 資料中心）是**責任方向，不等於現行 nav 命名**；命名與導航落地屬後續 IA Decision Gate。
- 規則落點 `PROJECT_RULES.md` 第 19 節；逐字原文與關係見 `docs/DECISIONS.md` DEC-085。
- 不新增功能需求、不改投資公式／門檻／權重／Risk Cap、不改資料來源、**不授權任何 implementation**；與 DEC-019／020／081／082／083 同向、不放寬。
- ⚠️ 單一撰寫組產出，無第二組驗過。

## 40. Quota-safe Resume Checkpoint（DEC-086，客戶 2026-10-26；append-only；Approved）

- 規則：額度／對話／連線／session／context 中斷後，新 session 只靠 GitHub 即可接續；`docs/HANDOFF.md` 為熱狀態，維持極短 Resume Checkpoint（15 欄），不建立 `SESSION_STATE`／`RESUME_STATE`／第二份 handoff。
- `docs/PROJECT_STATE.md`（DEC-068）必須保留；GitHub 操作事實優先於 HANDOFF／聊天記憶；80%／90% 額度門檻是操作門檻、不是產品邏輯。
- 規則落點 `PROJECT_RULES.md` 第 20 節；逐字原文與關係見 `docs/DECISIONS.md` DEC-086。
- 強化 DEC-067／068／079；不取代 DEC-084 與 Silent Autonomous Cruise；不降低任何 Gate；不改產品 code／投資語意。
- ⚠️ 單一撰寫組產出，無第二組驗過。

## 41. No Silent Stop／禁止無提示停手（DEC-087，客戶 2026-10-26；append-only；Approved）

- 規則：任何 user-visible 回覆首行標 🟢／🟡／🔴；🟡 必須說明為何停、要做什麼、精確回覆什麼；🔴 必須列問題、選項、總管推薦與客戶只需回覆的內容；禁止無提示停手；可自動恢復的外部等待（CI／audit／check_suite）屬 🟢。
- 因 🟡／🔴 停手時，Resume Checkpoint 同步記 stop reason／waiting_for_customer／exact customer action／exact resume condition／next single action（第 21 節）。
- 規則落點 `PROJECT_RULES.md` 第 21 節；逐字原文與關係見 `docs/DECISIONS.md` DEC-087。
- 強化 DEC-067／068／079／086；同向 DEC-084；不取代 Silent Autonomous Cruise；不降低任何 Gate；不改產品 code／投資語意。
- ⚠️ 單一撰寫組產出，無第二組驗過。

## 42. Proactive Conversation Handoff／主動建議換新對話（DEC-088，客戶 2026-10-26；append-only；Approved）

- 規則：當 context／token／quota／session 狀態不適合安全繼續下一完整工作階段時，依序完成 Safe Checkpoint → 更新 HANDOFF／Resume Checkpoint → 確認 branch／PR／CI／next single action 可恢復 → 主動回覆「🟡 需要你回覆：建議換新對話。」＋簡短原因＋可直接貼上的接手提示語。
- 禁止 checkpoint 後默默停住、禁止要求客戶重新解釋做到哪裡；接手提示語只做入口，新 session 仍以 GitHub Verification Gate 與 GitHub SSOT 為準；context 仍健康時不得為形式頻繁要求換對話。
- 規則落點 `PROJECT_RULES.md` 第 22 節；逐字原文與關係見 `docs/DECISIONS.md` DEC-088。
- 強化 DEC-086／087／067／068／079；不取代 DEC-084；不建立第二套狀態 SSOT；不降低任何 Gate；不改產品 code／投資語意。
- ⚠️ 單一撰寫組產出，無第二組驗過。

<!-- PROJECT_STATE_HISTORY_INDEX:BEGIN lines=709-717 archive=docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q2；只搬不改）**：原 L709–L717 已逐字搬至 `docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md`（分冊 L24–L32）。本處原為下列 1 節（標題逐字）：
  - 原 L709–L717 → [分冊 L24–L32](archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md#ps-hist-43)：## 43. 新 UI Stage B 設計草稿（DEC-082 Stage B；2026-10-26；append-only；~~**草稿，待 Stage C 客戶 Gate**~~ **historical：已由 DEC-089 核准，其六向 IA 再被 DEC-091／092 四頁取代**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留））
<!-- PROJECT_STATE_HISTORY_INDEX:END -->

## 44. New UI Stage C 核准（DEC-089，客戶 2026-10-26；append-only；~~Approved~~ **部分 historical：G1（六向導覽）與 Stage D 排程已被 DEC-091／092（D2.5 四頁）與 DEC-109 Phase 2～7 取代；G2／G5／G6／G7 與 7 項補充執行條件仍有效**（承接清單 BACKLOG `P1R-STAGE-D-CARRYOVER`）；本節內的 D2.5／AB／NAV-1／XV 補註為當時進度紀錄，現況見 §45～§48（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留））

- 裁示：**G1 C｜G2 X｜G3 B｜G4 B｜G5 B｜G6 A｜G7 B｜線框套件（B3～B7）核准｜「⚑／結構性自決項確認表」（24 項）全同意**，另有 7 項補充執行條件；逐字原文見 `docs/DECISIONS.md` DEC-089。
- 核准範圍：Stage C 的 IA／UX／線框**設計方向**；**不涵蓋** HI-1～HI-6（G7＝B：High 項目分批處理，須另走 High Gate，不得視為已核准施工）；**不**把 INFERENCE 升格為 FACT；不新增或修改投資語意、Risk Cap、threshold、weights、趨勢／估值定義、資料來源。
- G1＝C：Stage D 須**先出「導覽殼」文字線框並經客戶核准**後才可寫殼的 UI code（Stage B 草稿沒有殼的畫面；`CLAUDE.md` §-1.5.D v3 §03-2 ①）。
- Stage D 前置：以最新 main 實證所有未複驗項（資料契約、欄位可用性、L3 彙總讀法、動態引用），驗不到維持 missing／未確認；依 DEC-084 重做 Model × Effort Check；舊 UI 維持 Removal Gate（不刪）。
- 狀態：Stage C **已核准**；Stage D **尚未開始**（批次規劃見 `docs/BACKLOG.md` `NEWUI-STAGE-D-*`，各列 `not started`）；0 程式碼、0 測試、0 navigation 變更。
- 規則落點／依據：DEC-082、DEC-085、DEC-084、DEC-086／087／088、DEC-019／020；Stage B 草稿 `docs/vnext/NEWUI_STAGE_B_DRAFT_2026-10-26.md`（檔頭已追加核准狀態）。
- ⚠️ 核准範圍與關係為單一撰寫組讀法，無第二組驗過（`CLAUDE.md` §-2 規則 6）。
- 📌 **D0 實證報告已產出（2026-10-26；append-only；待獨立 QA／PR）**：`docs/vnext/NEWUI_STAGE_D0_EVIDENCE_2026-10-26.md`（基準 main `96206a96`；四組唯讀 agent 產出＋總管抽驗；**整份未經獨立 QA**）。耐久重點：(1) G6 逐檔表欄位多數已在 rows，但「健檢等第」只有圖示無字母等第、市值單位為「張·元」、235 燈僅 ETF、週線／布林 z 兩圖只對 ETF 成立、資料日（as_of／stale）不在 rows；(2) G3 三數的第三數「未判」與「訊號可信度 N/M」來自 L4 重算，不在 `build_station_digest`，digest 不跨頁；(3) G4 全站一行狀態**現無可直接呼叫的 L3 彙總**（`@monitored` 僅 9 支、registry 需先更新）；(4) 導覽殼測試對 `app.py`／`ia_nav` 多處逐字斷言，D2 須同步擴充並獨立 QA；rerun 中寫 nav key 的可行性未證（D9 前置）；(5) 全 repo 無 name→code 函式、個股資料無 scoped 失效函式；(6) 草稿 D-21「as_of（INFERENCE：L3 note 含）」不成立。（上述 (3)(5) 為單組讀碼的全稱句，報告第 10.2 節列為待驗事項，不得作為施工前提）。含草稿更正清單 E1～E7、E10（E8／E9 經 QA 移出 errata；草稿本檔未改）。驗不到者維持 MISSING／未確認；不授權施工，各批仍須 DEC-084 Check、獨立 QA、舊 UI 不刪。（有意識的更新，不是漏刪，決策者 AI 總管（事實更新））
- 📌 **D1 導覽殼線框草稿已產出（2026-10-26；append-only；待客戶核准）**：`docs/vnext/NEWUI_D1_SHELL_WIREFRAME_2026-10-26.md`（三輪獨立 QA 修正已套用；草稿提案，非已選）。🔴 Stop Gate＝客戶核准線框（waiting_for_customer＝true；未回覆＝不核准、不動工）；核准前 0 程式碼、0 導覽變更。內容見該檔，本檔不複製。
- 📌 **D1 導覽殼線框已核准（DEC-090，客戶 2026-10-26；append-only）**：「D1 採 b｜線框 核准｜②～⑧ 全部要｜⑨ 要｜P-1 同意｜P-2 同意」（逐字原文見 `docs/DECISIONS.md` DEC-090）。形式 (b)＝側欄兩層；⑨＝指路句補「側欄選『不使用』」步驟。為 D2 殼實作的授權依據；不授權投資語意／資料源變更或刪舊 UI；D2 開工前仍須 DEC-084 重判、擴充 `tests/test_ia_v2_sidebar_nav.py`、獨立 QA。本批 0 code、0 測試。上一條「待客戶核准」狀態已由本條取代。⚠️ 逐項對照為單組撰寫，無第二組驗過。
- 📌 **D2 導覽殼已實作（2026-10-26；append-only；待合併／待客戶驗收）**：commit `f413c52`（分支 `ccr-fa5b6ded-9rhvoj`，未 push；PR 待開）。依 DEC-090 核准線框（形式 b 側欄兩層）。**未做**：Old→New 對等驗收、手機與橫排視覺實機驗證。殘餘：第一層為直排 radio（線框示意橫排）需客戶實機確認；Streamlit 1.56 floor 未實跑（沙箱 1.59.2）；`reconcile_nav` import 時 `RuntimeError` 爆炸範圍＝整個 app（刻意 Fail Loud）；約 20 處頁內手抄頁名待清理（BACKLOG `NEWUI-STAGE-D2-RESIDUALS`）。不改投資語意／資料源、不刪舊 UI。⚠️ 單組撰寫，無第二組驗過。
- 📌 **D2 合併後 Cloud 啟動事故（2026-10-27；append-only；根因未確認）**：客戶回報 Streamlit Cloud 啟動 `app.py` 即 `ImportError`（指向 `app.py` 約 287 行 `from shared.ia_nav import (...)`），CI 全綠，沙箱乾淨 import 通過、無法重現。**根因未確認**（缺 Cloud 完整 traceback）；候選假說：Cloud 行程殘留舊模組、部署 commit 非 main、環境差異；沙箱已排除 exports 缺漏、Python 3.11–3.14 import、檔案未進 git、循環 import 靜態、sys.path 衝突靜態。已補 `tests/test_boot_import_smoke.py`（守衛，非根因結論）；~~D3～D5 凍結直到 D2 重新驗收；waiting_for_customer＝true。~~（已由 DEC-092 更新：Design Gate 已裁示，waiting_for_customer＝false）見 BACKLOG `NEWUI-STAGE-D2-BOOT-INCIDENT`。⚠️ 單組撰寫，無第二組驗過。
- 📌 **D2.5 Simple UI／One AI Brain 改道（DEC-091，客戶 2026-10-27；append-only；~~待客戶 Design Gate~~（已由 DEC-092 更新：Design Gate 已裁示，waiting_for_customer＝false））**：停止原 D3～D5 施工，改執行 D2.5 指定版（4 頁主導航 📊／🎯／💼／👤、資訊三層、全站唯一「🤖 AI 投資總結」、持股按投資目的分、產業趨勢新主線）；規劃文件 `docs/vnext/NEWUI_D25_A／B／C_*_2026-10-27.md`＋`docs/vnext/d25_wireframes/` **待客戶核准**；核准前 DEC-089 G1＝C／DEC-090／D2 殼（#944）／G3／G4 形態既不視為撤銷也不視為最終方案；D2 Cloud 啟動事故（BOOT-INCIDENT）仍 open。0 code、0 測試、不進 production UI code、不刪舊 UI；~~waiting_for_customer＝true~~（已由 DEC-092 更新：waiting_for_customer＝false）。待辦見 BACKLOG `NEWUI-STAGE-D25-SIMPLE-UI-ONE-BRAIN`、`DEC091-*`。註：本節上一條「D2 導覽殼已實作…PR 待開」已過時（#944／#945 已合併，main `a4ab3450`）。⚠️ 單組撰寫，無第二組驗過。
- 📌 **D2.5 Customer Design Gate 已裁示（DEC-092，客戶 2026-10-27；append-only）**：Q1 策略分類鍵＝`portfolio_id + symbol -> strategy`（🌱存股／📈資本利得／未分類；否決 symbol 全站唯一鍵；Sheet 寫入面仍屬 HI-5、須符合 writer／WIF／安全治理）；Q2 均線僅視覺參考、台股／國際趨勢＝⬜ 尚未定義（正式定義另列 High Gate）；Q3 五風險桶各取最需注意一項（資料不足不得硬選最差）；Q4 沿用既有「建議動作」與優先序；Q5 產業趨勢先開研究 RS-1（不導入 production、不新增 API／MCP）；Q6 D2 殼過渡版保留至四頁替代、D2 過渡版功能驗收通過、Boot incident＝實機已恢復但根因未確認（不得寫成 stale module；boot smoke guard 保留）、舊 UI Removal Gate 有效。設計方向（固定四主導航、One AI Brain 非第五主頁、Level 1/2/3 等）核准，wireframe 為後續視覺基準。上一條「待客戶 Design Gate」狀態已由本條解除；**DEC-092 為設計方向與資料口徑裁示，非實作授權**。待辦見 BACKLOG `DEC092-*`、`NEWUI-STAGE-D25-SIMPLE-UI-ONE-BRAIN`。⚠️ 摘要為單組撰寫，無第二組驗過。
- 📌 **RS-1 產業趨勢研究已產出（2026-10-27；append-only；docs-only）**：`docs/vnext/NEWUI_D25_RS1_INDUSTRY_TREND_RESEARCH_REPORT_2026-10-27.md`（DEC-092 Q5 授權）。結論：repo 現有資料僅能做 baseline（單季營收 YoY 僅 2 點）與資金動能（sector_flow 約 27 交易日）觀察，長期產業趨勢判斷尚缺歷史與多項資料；新外部來源皆未導入、官方站沙箱連不上（UNVERIFIED），導入前另開 Customer Gate；RS-2 需客戶同意才開（BACKLOG `DEC092-RS2-CANDIDATES`＝待客戶同意）。0 code／0 測試。⚠️ 單組撰寫，無第二組驗過。
- 📌 **AB-0 Decision Digest 契約已實作（2026-10-27；append-only；~~待 CI／merge~~ 已合併 PR #949，main `894b2f49`，CI 綠（總管轉述）（2026-10-27 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：客戶 2026-10-27 指示開工 AB-0（Opus＋Medium）。產出 `shared/decision_digest.py`（L0、stdlib-only、frozen dataclass；`SCHEMA_VERSION="decision_digest.v1"`）＋`tests/test_decision_digest_contract.py`，分支 `ccr-fa5b6ded-9rhvoj` commits `8f85bee9`→`2184d015`→`e005e98c`。耐久重點：(1) 段落＝market（FactSection）／tw_trend・intl_trend・valuation・industry（DefinitionSection：只有「尚未定義／研究框架，未啟用」，無結論欄位）／holdings（鍵 `portfolio_id+symbol`、策略預設未分類、缺鍵列以 `unkeyed_count` 計數不建列）／risk_cap（只引用、`cap_valid`）／actions（0..3、只來自規則層、available＋0 筆合法）；(2) `DataStatus` 無 neutral、`INVALID` 不附 missing_reason；unavailable ≠ 中性、缺值＝None 不是 0；(3) `AiParticipation`＝rule_only／ai_explained／ai_rejected＋G1～G6 檢查 id，無「AI 產生判斷」值；(4) AI／方向／佔位字拒收名單為盡力而為，權威 rule_id 允許名單與 Q4 優先序執行屬 AB-1；(5) 不接 AI／UI、不取數、不碰 `app.py`／`shared/ia_nav.py`、無 `from_dict`。與 C §4 草案差異見 `docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §11（單組比對）；內部設計選擇見 `docs/DECISIONS.md` DEC-093（AI 總管內部，非客戶裁示）；後續項見 BACKLOG `DEC092-DECISION-DIGEST-CONTRACT`、`AB1-*`、`AB-PORTFOLIO-ID-SEQUENCING`、`AB0-*`。驗證（執行組回報，撰寫組未重跑）：契約測試 353 passed、fast lane 31,186 passed／62 skipped（1 項需 `markdown_it`、沙箱未安裝而 deselect）、突變 77/77 killed；兩輪獨立 QA 已修正，最終獨立複驗見 PR；CI 未跑。下一批＝AB-1 Digest Builder（PLAN §5：Sonnet＋Medium，開工前 DEC-084 重判）。⚠️ 單組撰寫，無第二組驗過。
- 📌 **AB-1 Digest Builder 進行中（2026-10-27 交接；append-only；單組撰寫，未經獨立驗證）**：AB-0 已合併（#949，`894b2f49`）。AB-1 兩組獨立唯讀調查完成、總管設計已定案並落盤 `docs/vnext/NEWUI_D25_AB1_BUILDER_SPEC_2026-10-27.md`（`rule_id` 允許名單＝主要治理、Q4 優先序執行、純函式 Builder、無日期⇒MISSING）；實作組 WIP 草稿 4 檔（1,415 行）**未驗證**，存於 `WIP(AB-1)` Draft PR（branch `ccr-fa5b6ded-9rhvoj`，不得照原樣 merge，以 GitHub 實況為準）；客戶指示停止本 session 以交接。**尚未完成**：WIP 測試／突變檢查／兩組獨立 QA／CI／merge／DEC-094。**下一批＝接手 AB-1**（Sonnet 5.5＋Medium）。待客戶：RS-2 同意、AB-2b／AB-4w Gate；D2 啟動事故根因未確認；舊 UI Removal Gate 有效；HI-1～HI-6 未核准。後續項見 BACKLOG `AB1-BUILDER`、`AB1B-EXPOSE-AS-OF-AND-WRAPPER`、`AB1-STOCK-PATH-AND-TAKE-PROFIT-RANK`。
- 📌 **AB-1 Digest Builder 實作完成，~~待 CI／merge~~ 已合併 PR #951（squash，main `6a4c0628`，CI 綠 run 1775）（2026-10-27 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（2026-10-27；append-only；取代上一條「進行中」之現況，該條為歷史不刪；單組依 diff／commit 撰寫）**：`shared/decision_digest_rules.py`（L0：`rule_id` 允許名單、Q4 優先序、`assert_strict`）＋`src/services/decision_digest_builder.py`（L3 純函式）＋兩個測試檔；~~**PR #951 待 CI → ready → merge，尚未合併**~~ **PR #951 已合併（squash `6a4c0628`），CI 綠（run 1775）**。實作者自列突變 98/98 killed；兩組獨立 QA（對抗式＋語意）已跑並回修（`07cd93c`），**QA 後未重跑突變**；沙箱 Python 3.13，CI 3.11 未實跑。內部設計選擇（`action_branch.v1` 內部命名、`rule_wrong_location` 位置維度、資料異常列整列不搬、TypeError／ValueError fail loud、v1 不攜帶個股路徑與 `flag_take_profit`）見 `docs/DECISIONS.md` DEC-094（AI 總管內部，非客戶裁示）。**限制**：AB-0 尚無「actions AVAILABLE 且 0 筆」產生路徑；production 在 AB-4r 前不可達（無 production caller、`portfolio_id` 無來源）。新增後續列：`AB1-SNAPSHOT-TS-FORMAT-SSOT`（AB-1B）、`AB1-PERCENT-DOMAIN-CONSTANT`、`AB1-ACTION-TEXT-AI-WORDING`（均登記，不構成動工授權）。~~**下一個接手點**：PR #951 CI 綠→merge 後，~~ **下一個接手點**：#951 已合併，本批 docs 同步另開 docs-only PR；之後依 BACKLOG／`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 順序（序 4 為 AB-2a），開工前須先讀規格並依 DEC-084 重判 Model×Effort。**待客戶（原樣保留）**：RS-2 同意、AB-2b／AB-4w Gate、D2 啟動事故根因未確認、舊 UI Removal Gate 有效、HI-1～HI-6 未核准、EPS×PE／趨勢正式定義 High Gate、個股路徑／`flag_take_profit` 排位（`AB1-STOCK-PATH-AND-TAKE-PROFIT-RANK`，客戶若要納入才問）。
- ~~📌 **AB-2a Grounding／Validator＋規則式摘要實作完成，待 PR／CI／merge（2026-10-27；append-only；implementation complete／waiting CI，**不是 done、尚未合併**）**：L0 `shared/decision_digest_{terms,validator,grounding}.py`＋L3 `src/services/decision_digest_summary.py`＋5 個測試檔；G1～G6、降級四態（INVALID／UNAVAILABLE／PARTIAL／VALID）、規則式摘要（無 AI、無 LLM 呼叫、無 UI、未改 AB-0／AB-1）。主防線經兩組獨立 QA 實測 bypass 後由「黑名單＋quote 豁免」改為「句型白名單」（segment＝`Lit` 模板 id／`Ref` 欄位展開），歷經三輪 re-QA（總管轉述）。內部設計選擇見 `docs/DECISIONS.md` DEC-095（AI 總管內部，非客戶裁示）：INVALID 整份不保留（單組，待覆核）、Risk Cap 比任務字面更保守（不顯示 `exposure_lo/hi`，放行屬 `RC-VISIBILITY` Gate）、VALID 現行契約不可達、`SummaryResult` 僅 `rule_only`。**揭露**：突變 356（348 killed／8 等價／0 倖存）清單由實作者自列，QA 紅隊三輪另自行設計突變；沙箱 Python 3.13，**CI 3.11 未實跑**；承重判斷均單組。**限制**：production 無 caller（AB-4r 前 `portfolio_id` 無來源）；殘留限制見 DEC-095 與 BACKLOG `AB2A-GROUNDING-VALIDATOR`／`AB1-ACTION-TEXT-RULE-BINDING`／`AB2A-COMPLETENESS-CALLER-CHOICE`／`AB2A-RULE-TEXT-FAITHFUL-RELAY`／`AB2A-SYMBOL-PATTERN-REVIEW`／`AB2B-INTERFACE-NOTES`。PR 號：~~待開~~ #953（已合併 PR #953（squash，main `5c9b2750`，CI 綠；Fast checks 與 Slow tests 皆 success））。PR #953 CI 首輪紅燈兩項：(1) AB-2a 測試 `test_a8` 的 Python 3.11 `ValueError`／3.13 `TypeError` 差異（已修）；(2) `test_c1_observability::test_old_rows_unchanged_after_append` 與 cron 資料耦合（main `aacdb9e` 起 base 即紅，非 AB-2a 引入；只改該測試，一併併入 #953）。規格檔仍寫「回修版未經第二組獨立複驗」與實況一致，第四輪小修只經實作者自驗。**下一個接手點**：AB-2a 已合併後，依 `docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 順序（序 5 為 AB-4r 策略分類唯讀契約，PLAN 建議 Opus＋Medium，**開工前須先讀規格並依 DEC-084 Rule 8 重判 Model×Effort，配置不同須在 Safe Checkpoint 停手等客戶「改好了」**）；**AB-2b 為 Decision Gate，不可自行開始**；AB-5／AB-6 依賴 NAV-1（序 6），不可提前。**待客戶（原樣保留）**：RS-2 同意、AB-2b／AB-4w Gate、D2 啟動事故根因未確認、舊 UI Removal Gate 有效、HI-1～HI-6 未核准、EPS×PE／趨勢正式定義 High Gate、Risk Cap 正式核准／`RC-VISIBILITY`、個股路徑／`flag_take_profit` 排位（`AB1-STOCK-PATH-AND-TAKE-PROFIT-RANK`）。~~ 📌 **AB-2a 已合併 PR #953（squash，main `5c9b2750`，CI 綠；Fast checks 與 Slow tests 皆 success）（2026-10-27 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：本條上述內容為實作完成當時之記述，僅「待 PR／CI／merge」已由本句取代。PR #953 CI 首輪紅燈兩項：(1) AB-2a 測試 `test_a8` 的 Python 3.11 `ValueError`／3.13 `TypeError` 差異（已修）；(2) `test_c1_observability::test_old_rows_unchanged_after_append` 與 cron 資料耦合（main `aacdb9e` 起 base 即紅，非 AB-2a 引入；只改該測試，一併併入 #953）。規格檔仍寫「回修版未經第二組獨立複驗」與實況一致，第四輪小修只經實作者自驗。
- 📌 **AB-4r 策略分類唯讀契約實作完成，待 PR／CI／merge~~（2026-10-28；append-only；implementation complete／waiting CI，**不是 done、尚未合併**）**~~ ~~（2026-10-28；append-only；implementation complete；PR #955（Draft）waiting CI，**不是 done、尚未合併**）~~**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）） **merged：已合併 PR #955（squash，main `d97afec9`，CI 綠；Fast checks 與 Slow tests 皆 success，head `935df34`）**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））：L0 `shared/strategy_class_schema.py`（`derive_portfolio_id`、`build_holding_keys`、`parse_strategy_records`、`lookup`、`unmatched_keys`）＋L1 `src/data/portfolio/strategy_class_reader.py`（`read_strategy_classes`）＋`gsheet_portfolio.read_worksheet_values`（加法式 +46 行，既有函式未改）＋2 個測試檔；分支 `ccr-fa5b6ded-9rhvoj` commits `c2c3486`、`eb87591`。`portfolio_id`＝`pfv1-`＋sha256(sanitize_sheet_id(sheet_id)＋NUL＋組合名.strip()) 前 20 hex；策略存同 Sheet 獨立分頁 `strategy_class`（`name | ticker | strategy | updated_at`），`portfolios` 5 欄不動；缺值＝未分類、不合法列與同鍵衝突另行揭露、不擇一。不寫入、不建分頁、不接 AB-1 builder、無 production caller、未改 AB-0／AB-1／AB-2a。內部設計選擇見 `docs/DECISIONS.md` DEC-096（AI 總管內部，非客戶裁示）；規格 `docs/vnext/NEWUI_D25_AB4R_SPEC_2026-10-27.md`。~~**揭露**：兩組獨立 QA（QA-A、QA-B）＋一組回修複驗（總管轉述）；突變清單由實作者自列（第一輪 35 全紅；回修後 48 個中 47 套用全紅，M9 由 N11／N12 取代）；撰寫組未重跑測試、CI 未跑。~~ **揭露**：兩組獨立 QA（QA-A、QA-B）＋第三組兩輪回修複驗**皆 PASS**（第二輪複驗自選 9 突變全紅；總管轉述）；殘餘 MINOR：鍵重建驗證只套 entries，`conflict_keys`／`HoldingKeysResult.keys`／`lookup` 需 `object.__new__` 刻意繞過，風險低；突變清單由實作者自列（58 個中 57 套用全紅，M9 由 N11／N12 取代）；PR #955（Draft，waiting CI）；撰寫組未重跑測試。（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**限制與後續**：`AB4R-WIRE-BUILDER`（接線必改 AB-1、Digest 無欄位區分寫錯／衝突／孤兒與沒設定）、`AB4R-CACHE-CLEAR`、`AB4R-HI5-NOTICE`、`AB4R-SHEET-SAFETY-ENTRIES`、`AB2A-COMMENT-DRIFT`（均登記，不構成動工授權）。**下一個接手點**：AB-4r 合併後依 PLAN §5 序 6 NAV-1（見 `docs/HANDOFF.md` Resume Checkpoint）。
- 📌 **NAV-1 四頁導覽殼替換實作完成，~~待 PR／CI／客戶裁示~~ 已合併 PR #957（squash，main `5ff860b3`；CI Fast checks／Slow tests 皆 success，head `3f3c0b5d`）；客戶實機點驗待客戶（`NAV1-CLOUD-MOBILE-VERIFY`），**不是 done-verified**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（2026-10-28；append-only；~~implementation complete／waiting CI／待客戶裁示標的頁葉選擇，**不是 done、尚未合併**~~ → merged）**：新增 L0 `shared/ia_nav4.py`、L5 `src/ui/views/shell_nav4.py`；`app.py` 只動路由；預設入口翻轉為新四頁（桌機 `st.sidebar`、手機底部固定列、同一 SSOT key `_nav4_page`），舊 UI 改為 `?legacy=1`（session 旗標黏性、無可見入口、行為不變、不依賴新模組）；不改 `shared/ia_nav.py`／`PAGE_LABELS`／`src/ui/tabs/**`。`git diff origin/main --stat`＝26 檔、+2870／-52（含 6 支新增 `tests/test_nav1_*`、`tests/test_boot_import_smoke.py` 只加不削、4 支既有 AppTest 只加 legacy 旗標）。規格與交付記錄 `docs/vnext/NEWUI_D25_NAV1_SPEC_2026-10-28.md`；內部設計選擇 `docs/DECISIONS.md` DEC-098（AI 總管內部，非客戶裁示）。**揭露**：QA-A（對抗）、QA-B（語意）＋第三組回修複驗（~~**複驗進行中，勿視為已通過**~~ 第三組兩輪回修複驗皆 PASS，無 BLOCKER／MAJOR，殘餘 MINOR 已補行為測試或登記 BACKLOG（總管轉述）（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））；突變依實作組自報 40 項全紅（清單由實作者自列，未獨立複跑）；~~CI 未跑~~ CI 已跑（#957 兩項 success）（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；撰寫組未重跑測試。**限制與後續**：Cloud 啟動與手機實機未於沙箱實測，**客戶實機點驗為驗收必要條件**（`NAV1-CLOUD-MOBILE-VERIFY`）；標的頁多一條葉選擇橫排 radio＝偏離 wireframe 過渡項，~~待客戶裁示~~ 客戶已裁示方案 A（DEC-099）（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（`NAV1-TARGET-LEAF-SELECTOR`）；預設畫面暫時取不到的舊功能僅 `?legacy=1` 可達（`NAV1-DEFAULT-MISSING-CAPABILITIES`），**不代表通過 Old UI Removal Gate**；`NAV1-WAYFINDING-I1`、`NAV1-PAGE-TODAY-LEGACY-WORDING`。**下一個接手點**：~~NAV-1 PR 合併後~~ NAV-1 已合併 #957 → `CROSS-VIEW-DATA-CONSISTENCY-AUDIT`（見 `docs/HANDOFF.md` Resume Checkpoint）。
- 📌 **NAV-1 客戶裁示補註（2026-10-28；append-only；決策者＝客戶，DEC-099）**：客戶對 🎯 標的頁「🔍 找標的／🔬 查一檔」切換選方案 A——保留，僅作 NAV-1 → UI-T 之間的過渡控制；非最終 wireframe 設計、非新增正式 IA；UI-T 實作時須整合回單一 🎯 標的頁並移除此切換；不得改功能語意或新增投資規則；PR #957 其他範圍不變。~~**NAV-1 狀態：待 PR #957 合併；客戶裁示已取得（僅限此一項偏離）**，非 done；~~ **NAV-1 狀態：已合併 PR #957（squash，main `5ff860b3`，CI 綠）；客戶裁示已取得（僅限此一項偏離）**；非 done-verified；（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））客戶實機點驗仍為必要條件（`NAV1-CLOUD-MOBILE-VERIFY`）。DEC-098 仍為 AI 總管內部設計選擇。下一接手點＝~~NAV-1 合併後~~ NAV-1 已合併 → `CROSS-VIEW-DATA-CONSISTENCY-AUDIT`（開工前依 DEC-084 重判 Model×Effort）。
- 📌 **Cross-View 資料一致性稽核完成＋本批安全小修（2026-10-28；append-only；~~implementation complete／waiting CI，**不是 done、尚未合併**~~ **已合併 PR #959（squash，main `c6ad4567`；CI Fast checks 與 Slow tests 皆 success，head `7a233144`）；Audit 完成並合併；NAV1 實機點驗仍待客戶**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））**：報告 `docs/vnext/NEWUI_D25_XVIEW_AUDIT_2026-10-28.md`（基準 main `739fa361`；三組獨立稽核 A／B／C＋一組複驗 V；38 項不一致：HIGH 4／MED 15／LOW 19，非窮舉）。處置分類與安全小修見 `docs/DECISIONS.md` DEC-100（AI 總管內部，非客戶裁示）：(a) ⑦／LINE AI prompt 有效判斷檔數須有限值且 ≥1 才放「續抱」句；(b) 側欄「🔄 強制刷新數據」help 據實（行為不變，legacy 亦可見）；(c) 🔬 葉2 個股抓價失敗顯示整列錯誤（同列財報分數一併被蓋＝已揭露取捨）；(d) 熱力圖去後綴順序（`etf_smart_analysis` 舊 UI 依 DEC-019 停手）；(e) 本益比表只快取成功＋FailCooldown（模組層共用，冷卻期間所有使用者拿空表＝INFERENCE）。Commits：S1 `188c20e7`／S2 `96880543`／S3 `7dbfaf4b`／S4 `8bc93e8e`／S5 `99e10bc6`；守衛同步 `3c1a7550`；QA 回修 `183dbdc3`；稽核報告 `73e60339`。**揭露**：一組修正 QA 抓到 1 MAJOR＋2 MINOR 已回修，回修後未再經第二組複驗；突變由實作者與 QA 各自自列；沙箱無部署端網路、Cloud 未驗；撰寫組未重跑測試。**後續**：客戶 Gate `XV-H3`／`XV-H1-EXT`／`XV-ASOF`；內部技術 Gate 12 列與登記項見 `docs/BACKLOG.md` §5.1.14；`XV-C05` 須於 `AB4R-WIRE-BUILDER` 前修。
- 📌 **Cross-View 客戶 Gate 已裁示（DEC-101，客戶 2026-10-28；append-only；Approved）**：`XV-H3`＝A（未定義 FX 來源／時點／成本幣別前，外幣資產不得與 TWD 加總、先排除於總市值並列出代號與原因；不得把剩餘資產包裝成完整 80/20；完整分母不存在時顯示「⬜ 部分外幣資產未納入，總市值／配置比例無法完整判定」；換算另開 `FX-CANONICAL-GATE`）；`XV-H1-EXT`＝A（missing ≠ HOLD、unavailable ≠ safe；缺資料標的「⬜ 資料不足／無法判定」，組合層不得產生「全部續抱」等 blanket conclusion；Z51／Z52 舊語意與測試同步修正）；`XV-ASOF`＝A（價格旁簡潔「資料時間＋來源」，stale／fallback 文字標示、不只靠顏色；**先線框**：`docs/vnext/NEWUI_D25_XVIEW_ASOF_WIREFRAME_2026-10-28.md`，待客戶確認 Q1～Q3）；基金範圍聲明（本 repo 稽核不涵蓋基金，`FUND-REPO-XVIEW-AUDIT`）；內部技術議題授權邊界（純技術一致性可自治；canonical identity／schema／新 provider／公式／投資語意／客戶可見新口徑須另停 Gate；`XV-C05` 須在接摘要前完成並驗證）。**現況**：DEC-101 實作中 —— `XV-H1-EXT`／`XV-H3`／`XV-C05`／`XV-H2-EXT`＋`XV-M1`／`XV-V1`（實作組，分支 `ccr-fa5b6ded-9rhvoj`，未合併）；`XV-ASOF` 線框待客戶確認（0 UI code）。細節以 `docs/DECISIONS.md` DEC-101 為準。⚠️ 單一撰寫組撰寫，未經第二組驗（`CLAUDE.md` §-2 規則 6）。
- 📌 **DEC-101 實作（2026-10-28；append-only；決策者 AI 總管（事實更新））**：current task＝DEC-101 實作 —— `XV-H1-EXT`（L0 單一判定 `shared/holdings_data_short.py`）／`XV-H3`（L0 暫行判定 `shared/asset_currency_gate.py`，非 canonical）／`XV-C05`／`XV-H2-EXT`＋`XV-M1`／`XV-V1`：~~**implementation complete／PR 待開／waiting CI，未合併**~~ **merged（已合併 PR #961（squash，main `2e97482c`，CI 綠：Fast checks／Slow tests 皆 success，head `5783a59e`））**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；三組獨立 QA（A 對抗、B 語意、C 複驗兩輪）已回修。**待客戶**：`XV-ASOF` 線框 Q1～Q3、`XV-OLDUI-FX-REASON`、`XV-LINE-VIX-LINE`；其他仍待客戶 Gate 不變；`FUND-REPO-XVIEW-AUDIT` 未開始。~~下一接手點＝開 PR → CI → Auto-Ship。~~ 下一接手點＝待客戶裁示（見 `docs/HANDOFF.md` Resume Checkpoint）（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。細節以 `docs/DECISIONS.md` DEC-101 實作紀錄為準。⚠️ 單一撰寫組撰寫，未經第二組驗（`CLAUDE.md` §-2 規則 6）。
- 📌 **DEC-101 第四輪回修（2026-10-28；append-only；決策者 AI 總管（事實更新））**：`9c26106d`（觀察清單判不出計入組合層資料不足，AI 總管決定）／`e4742494`（契約漂移不計入有效判斷檔數、⑦／LINE 點名）／`303c9703`（① 替代句依原因組成）；獨立複驗組 C 三輪，最終 0 BLOCKER／0 MAJOR／3 MINOR（登記 LOW）；fast lane 32325 passed／1 環境失敗（z59）。~~**狀態＝implementation complete／PR 待開／waiting CI，未合併**~~ **狀態＝merged（已合併 PR #961（squash，main `2e97482c`，CI 綠：Fast checks／Slow tests 皆 success，head `5783a59e`））**（2026-10-28 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。**待客戶裁示**＝`XV-ASOF` 線框 Q1～Q3、`XV-OLDUI-FX-REASON`、`XV-LINE-VIX-LINE`、`XV-FX-ROW-ACTION`（新升客戶 Gate；推薦保留結論＋加註「停利未判：外幣」）。⚠️ 總管轉述，撰寫組未重跑測試、未經第二組驗。
- 📌 **DEC-101 後續四項客戶裁示（DEC-102，客戶 2026-10-28；append-only；Approved）**：`XV-ASOF` 線框 Q1 A／Q2 A／Q3 A 已核准可實作（表頭下一行共同時間＋例外列標示；「盤中或收盤未確認」不猜收盤；持股沿用總市值下方「價格資料日」位置；不只靠顏色；不擴張版面）；`XV-OLDUI-FX-REASON`＝B（舊 UI 只修外幣錯誤原因句一處，DEC-019／020 其餘不變）；`XV-LINE-VIX-LINE` 同意（資料不足時只陳述 VIX 事實、不附行動句）；`XV-FX-ROW-ACTION` 同意（可證明的「🟢 續抱」保留＋加註「停利未判：外幣」，局部降級）。過期價是否計入市值／損益／停利仍 open。狀態：實作中。⚠️ 單一撰寫組產出，無第二組驗過。
- 📌 **DEC-102 實作（2026-10-29；append-only；決策者 AI 總管（事實更新））**：`XV-ASOF`（價格旁資料時間＋來源，🔬 P1／P2／葉2、💼 ① E17／⑤；L0 `shared/price_asof_label.py`＋L3 加性非顯示鍵）／`XV-OLDUI-FX-REASON`／`XV-LINE-VIX-LINE`／`XV-FX-ROW-ACTION`＋AI 總結 prompt 同步 —— ~~**已實作，PR #963 待合併**~~ **已合併（PR #963，main `6bdd9af6`）**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；非 done-verified（待客戶實機點驗 NAV1／ASOF）。下一接手點＝UI-M（`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 序 7；開工前依 DEC-084 重判 Model×Effort）。

## 45. UI-M 📊 市場頁完成~~待合併~~已合併（PR #965，main `3dad82e0`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（DEC-105，客戶 2026-10-29；append-only）

- **狀態**：UI-M 已實作（~~PR #965 待合併~~ 已合併（PR #965，main `3dad82e0`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；非 done-verified，待客戶實機點驗）。客戶裁示 1A（結論句位置）／2A（市場位階五態字樣，不映射偏多／中性／偏空）／3A（指標危險度降階到「指標明細（16 項）」最上方，首屏需指路），見 `docs/DECISIONS.md` DEC-105。
- **架構**：L2 `compute_five_bucket_summary` 加性 `main_key`；L3 `market_twii_view_service`（圖 A，attrs 透傳）；L5 `src/ui/views/_market_blocks.py`（Hero 4 卡／⚡／圖 A～D／「查看依據」六欄）；`page_market.py` 只編排並保留既有展開區。還原鏈新頭節 `tests/test_uim_revert_chain.py`。
- **未動**：`PAGE_LABELS`／`ia_nav`／`app.py`／`page_today`／L1。
- **下一個主線 P1**：`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 序 7 剩餘頁（UI-T → UI-H → UI-ME）與序 8（AB-5／AB-6）；唯一下一步＝UI-T；開工前依 DEC-084 重判 Model×Effort、等客戶切換。⚠️ 「UI-T 先」為計畫表列序讀法，單組。
- **P2 登記**：`UIM-LAYOUT-DEVIATIONS`、`UIM-MA-FLAT-REFERENCE`、`UIM-UPDATE-BUTTON-WORDING`、`UIM-HERO-MAX-ITEMS-SSOT`（`UIM-REGIME-WORDING` 已由 DEC-105 結案為維持現狀）。

## 46. UI-T 🎯 標的頁整合（找標的＋查一檔）~~已實作，PR #968~~ 已合併（PR #968，main `9ec555e7`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（DEC-107，客戶 2026-10-29；append-only）

- **狀態**：~~已實作於分支 `uit-impl`（基準 `4521fc39`）；PR #968（合併 SHA 由總管同步）~~ 已合併（PR #968，main `9ec555e7`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；非 done-verified（待客戶實機點驗，見 `UIT-CLOUD-MOBILE-VERIFY`）。客戶線框五題 1A 2A 3A 4A 5A，見 `docs/DECISIONS.md` DEC-107。
- **架構**：新增 L5 `src/ui/views/page_target.py`（編排）＋`_target_blocks.py`（區塊）、薄 L3 `src/services/target_industry_service.py`；重用 `page_find`／`page_inspect` 既有 loader／builder（兩檔一字未改）；`shared/ia_nav4` 移除過渡切換並新增 `MERGED_VIEWS`；`app.py` 僅 `_ia_view_find()` 依旗標分流。
- **清理**：NAV-1 過渡切換（`NAV4_TARGET_LEAF_KEY`、`NAV4_WIDGET_LEAF_KEY`、`render_target_leaf_selector`、`has_leaves`、`leaf_options`、`leaf_from_label`、`current_leaf`、`_on_leaf_change`）已移除。
- **待客戶**：`UIT-S9-NO-POINTER` 一句話確認（非阻擋，總管推薦同意）。
- **下一個主線 P1**：`NEWUI_D25_PLAN_2026-10-27.md` §5 序 7 剩餘頁 UI-H（💼 持股）→ UI-ME，再序 8；開工前依 DEC-084／DEC-106 比對目前 Model×Effort，符合即靜默繼續。


<!-- PROJECT_STATE_HISTORY_INDEX:BEGIN lines=766-773 archive=docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q2；只搬不改）**：原 L766–L773 已逐字搬至 `docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md`（分冊 L38–L45）。本處原為下列 1 節（標題逐字）：
  - 原 L766–L773 → [分冊 L38–L45](archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md#ps-hist-47)：## 47. UI-CORRECTION 新 UI 視覺修正線框草稿（DEC-108，客戶 2026-10-29；append-only；**SUPERSEDED BY DEC-109**（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109）；上一值刪除線保留））
<!-- PROJECT_STATE_HISTORY_INDEX:END -->

## 48. Phase 1 SSOT Reset／Contract Freeze（DEC-109 客戶／DEC-110 總管內部，2026-10-29；append-only）

- **main**：**Phase 1 已於 PR #971 squash 合併（main `3bbdaf0f`；Fast checks／Slow tests 皆 success）**；#970 已關閉為 superseded（未合併，原貌只在 commit `06a7a3e5`，不在 main 歷史、不作 production baseline）。之後 cron 會推進 tip，**以 `git fetch origin` 實查為準**。**Phase 2 尚未開始；本對話已 Safe Handoff／Session Close**（`docs/HANDOFF.md` 置頂索引；客戶 Model×Effort 指示見 DEC-113：Phase 2＝Sonnet 5.5＋Medium）。（2026-10-29 Safe Handoff 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；上一值刪除線保留） ~~PR base＝`978ecedc`（cron；最後非 cron＝#969 `71587857`）；Phase 1 落盤＝分支 `ccr-6eace3b6-0gglrs` 新 docs PR（head=`ccr-6eace3b6-0gglrs` 的 open PR，取代 #970；以 **squash merge** 合併；合併後的 main 以 GitHub 為準）。#970（DEC-108 線框）**superseded、由總管關閉（留言指向 commit `06a7a3e5`）、不作 production baseline**；squash 後 `06a7a3e5` 不進 main 歷史，#970 原貌只保存在該 commit。**Phase 1 文件落盤完成；合併＋main verification 前 Phase 1 未完成。**~~
- **客戶方向（DEC-109，逐字見 DECISIONS）**：簡化 UI，不簡化判斷；圖表 > 數字 > 短句 > 長文字，但 Visual Priority ≠ Visual Quantity；Simple Decision Dashboard, not Report Wall and not Chart Wall；Presentation Simplification must never reduce AI Decision Context；Data View ≠ Decision Context ≠ AI Output；One AI Brain, Many Data Views；Conversation 不是 SSOT，GitHub 是 durable memory。
- **新文件位置**（正式契約層；位階見 `PROJECT_RULES.md` 第 25 節）：
  - Presentation Contract＋Visual SSOT：`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`
  - Visual Fidelity Gate：`docs/governance/UI_VISUAL_FIDELITY_GATE.md`（工具 `tools/visual_fidelity/`；baseline `docs/vnext/visual_fidelity/phase1_baseline/VISUAL_GAP_AUDIT_2026-10-29.md`）
  - Decision Digest Contract：`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`
  - One AI Brain Boundary：`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`
  - Supersede Map：`docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md`
  - Migration Plan（Phase 2→7）：`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md`
  - 治理：`PROJECT_RULES.md` 第 24 節（Visual Fidelity＋Presentation）、第 25 節（SSOT 位階兩軸）、第 26 節（Durable Memory Contract）；第 7 節 DoD 補註（UI Stage＝CI 綠＋Visual Fidelity PASS）；第 11 節必讀改指新契約；第 19.11 節呈現讀法
- **Phase 2～7 路線**：2 Helper／Test Contract Migration（畫面零變更）→ 3 Shared Visual Components → 4 📊 市場 reference → 5 🎯 標的 → 6 💼 持股 → 7 One AI Brain／Decision Digest／AI 投資總結（BACKLOG §5.1.16 `P1R-*`）。Digest contract 已凍結最低概念契約；**v2 schema（A1～A7）定案前不寫新 prompt／glue**（客戶 DEC-109 三十一）。Phase 3～7 每個 UI phase 寫 UI code 前先出文字線框（含該頁 W 點、版面差異、總管推薦；`CLAUDE.md` v3 §03-2 ①）。
- **凍結狀態**：UI 視覺實作凍結（DEC-108 第 3 點）的解除條件改為「Phase 1 契約合併後依 Phase 2→7 推進，每個 UI phase 過 Visual Fidelity Gate」；已合併 UI-M（#965）、UI-T（#968）不自動回退，由 Phase 4／5 回修。
- **吸收自 #970**：DEC-108 裁示（保留，標部分取代，並補登客戶原文）、§D 能力守恆（契約 §17）、§E 順序（Migration Plan）、A.5 工程字樣（契約 §18）、A.8 token 差異（契約 §14.2）；§C 偏差量測由 Phase 1 已載入量測取代；**冷啟動量測不吸收**，Phase 3 Gate 前重量（BACKLOG `P1R-COLD-START-BASELINE`）。
- **重要事實（影響未來架構判斷）**：(1) Decision Digest 市場段依賴 session warroom（新 UI 唯一寫入點＝今天頁「🚀 更新今日戰情」，`page_market` 只讀）；(2) 五桶 worst-of 只在 L5、輸入為 session 片段；(3) `build_ai_summary` 是 partial／legacy building block（帶 VIX、觀察清單 235 燈、資料不足、換入候選，不提總經位階），不是 One AI Brain；(4) AB-2a 程式寫死五段；(5) Google login 兩入口並存（側欄＋👤 我的卡①）。
- **總管改判（2026-10-29）**：AI 總管讀法不得推翻客戶核准過的呈現——DEC-107「選股條件預設展開」、DEC-017 葉1 ②「兩套刻度常駐非摺疊」、卡片「▸ 詳細」、DEC-105 指路說明句、DEC-092 Q5 排序說明句、tokens 客戶裁示色值**維持有效**，改否列各 phase 線框待客戶拍板點 W1～W9（第二輪 QA 追加：W8「最大 1～3 個變化」選取規則〔Phase 7〕、W9 KPI 欄數 vs `CLAUDE.md` v3 §00「固定 3 欄」〔Phase 4，`CV1-DR-12`〕；DEC-021 取代縮到 DEC-083 Q1 明確點名的「換一本／建新 Sheet」；舊 Stage D 能力項目維持 open〔`P1R-STAGE-D-CARRYOVER`〕）（`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md` §22；BACKLOG `P1R-P*-WF-*`）。
- **限制**：五份調查與 Phase 1 文件皆單組、未經第二組驗；量化上限為依 blueprint 量測的建議值；手機實機、Streamlit Cloud、1.56 floor 未驗；`PROCESS.md` §1 與五檔讀序衝突（`CV1-DR-04`）未裁示。
- **Phase 2 預備實測（未完成、單組）**：存於 `docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §11（含 `tab_today.py` 的 z60 目錄指紋守衛、真 golden 位置、hover-only 斷言範圍、文件與實測 11 項差異）；下一 session 以當時 main 重測為準。
- **Phase 2 步驟 0 實測（2026-10-30，main `64fdeae`；待本 PR merge）**：已完成並存於 Migration Plan **§12**（§11 預備實測的更新版；路徑更正 `src/ui/views/`、z60 守衛範圍 91 檔、`v2_short_rows` 計數視口徑（區分大小寫 39 檔／118 次；不分大小寫含常數 40 檔／165 次，見 §12.3）、helper 簽名／caller 修正）；單組各自結論＋總管自驗，未經第二輪 QA。Phase 2 步驟 1～5 尚未開始。
- **Phase 2 步驟 1 完成（2026-10-30；共用層可選參數：`card_html` chips／summary／fold_label／spark、`single_submit_form(options_label)`、`render_card(compact)`；預設輸出 byte-identical、0 production caller；工作樹 diff 未 commit）**：實測與已知限制存於 Migration Plan **§13**；步驟 2 為下一步。單組實作＋兩組獨立 QA，無第三輪。
- **Phase 2 步驟 2＋4 完成（2026-10-30；tests-only：p02～p05＋p01 compact 的 T1/T2/T3/T4/T7/T13 改寫為資訊守恆斷言＋通用 hover-only／預設收合斷言；`src/` 0 diff；工作樹未 commit）**：結果、等強論證、mutation 對照、已知缺口存於 Migration Plan **§14**；~~下一步＝步驟 5（mutation 清單）~~（已被取代，見下）。單組實作＋兩組獨立 QA；slow／AppTest／全套 pytest 未驗。
- **Phase 2 完成（2026-10-30；步驟 0、1、2＋4、5 完成，步驟 3 已取消；docs-only 收尾，`src/`、`tests/` 0 diff）**：M1～M13 判定與 18 個臨時 mutation（M5／M6／M13 必紅、M10 部分適用、spark／fold_label 重跑，無存活；其餘 N/A 待 Phase 3／`CV1-DR-12`）、零資料語意證明 a～g、DoD 對照存於 Migration Plan **§15**；全套 fast lane 35366 passed／0 failed／46 skipped／185 deselected（slow 未跑）。1440／390 截圖 Gate 以 byte golden＋QA 差分替代、未做（限制見 §15.3）。**下一階段 Phase 3 為 UI phase，寫 UI code 前須先出文字線框供客戶拍板。**
- **Phase 3 步驟 0 完成（2026-10-30；docs-only，`src/`、`tests/` 0 diff；PR 待 merge）**：共用視覺元件文字線框草稿＋客戶裁示表（rev3 七題：D1a、D1b、D3、D5、D6、D8、D10；站殼間距改內部先量測）存於 `docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md`（rev1 單組撰寫；rev2 依兩組獨立 QA 修訂，修訂版未再經第三輪驗證）；~~**待客戶拍板，拍板前不寫 UI code**；不裁示者維持現況。~~（已被下一行取代）
- **Phase 3 步驟 0 客戶裁示已落盤（2026-10-30，DEC-115；docs-only，`src/`、`tests/` 0 diff）**：客戶裁示 D1a=A（客戶裁示色全維持）／D1b=B（非客戶色與圓角延到 Phase 4～6 逐頁收斂）／D3=A（chip 三族、護欄實線粗框）／D5=A（迷你線與小倍數不顯示數字）／D6=B（Primary 同高、Secondary 缺資料縮一行，不隱藏 Missing）／D8=B（膠囊切換，先 floor 1.56 實跑，不成立退回 A、不升 floor）／D10=(a)（來源進摺疊、兩護欄各自獨立）。**調整三處契約字面**（§8-4 冷啟動圖槽、R15 tokens 收斂時程、§4 圖 A chip 配額；契約已就地加註、原文保留）。站殼間距先內部實測、整體 layout 變更才送客戶；W2～W9 維持原 Gate。施工拆分（步驟 1～5 與每步 DoD）＝`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §16；Phase 3 步驟 1（`src/ui_v2/compact.py`）尚未開始。限制：D8 的 1.56 實跑、D6 載入後位移量、D3 視覺權重皆**未驗**；落文為單組、未經第二組驗證。
- **Phase 3 步驟 1～5 已處理（2026-10-30；除站殼間距客戶裁示 D7 外完成）**：步驟 1＝`src/ui_v2/compact.py`（#979）；步驟 2（`_ui_kit` 薄封裝）判定不需要、未做（Phase 4 掛頁時以最小薄封裝處理，BACKLOG 已登）；步驟 3 站殼量測完成，AI 總管判定屬整體 layout 變更（nav4 全站第一屏上移 88px）→ 待客戶裁示（推薦方案 R；DEC-115 本文只寫「若屬整體 layout 變更再送客戶；不核准任何站殼改動」）；步驟 4 D8=B 在 floor 1.56.0（及 1.59.2）成立（5 條硬性約束；`st.html` 剝行內 `<svg>`，掛頁走 `st.markdown(unsafe_allow_html=True)` 或 data-URI `<img>`；1.57～1.58 未驗）；步驟 5 離線預覽＋Gate 元件層自評（單組自評，非 Gate 通過）。本輪修正（工作樹未 commit）：`compact.py` `non-scaling-stroke`、孤立點 r=2.5、`TopN.more_chip()`（`topn_more` 為契約 §6 META 表外的非 META 家族）。結果＝Migration Plan §17。**下一步＝Phase 4 步驟 0（重測 main＋📊 市場頁文字線框〔W2、W3、W9〕送客戶）**。限制：預覽為靜態 HTML 非 Streamlit 渲染、無實機；本節由執行 AI 起草，QA 結論為其回報轉錄。
- **Phase 3 站殼間距 D7=B 已施工（2026-10-30；DEC-116）**：客戶裁示 D7=B 最小改動＋七條限制；`src/ui/views/shell_nav4.py::_CSS_TEMPLATE` 加兩條無 media 規則（`padding-top:72px`＋隱藏 style-only 空容器）、`tests/test_nav1_shell_nav4.py::TestCss` 守衛調整（8 個 mutation 全紅）。實測（Streamlit 1.59.2）：四頁 H2／第一可見內容 y 一律 135.19（原 223.19／207.19）；`?legacy=1` 量測全同；規則剝除回到原值、無破版；無新增 layout jump。未觸發退回方案 C；`app.py`／z60 指紋／`requirements.txt`／`page_css()` 0 diff。**限制**：僅量 1.59.2（1.56～1.58 未驗）、真資料載入態未驗、實機／Cloud 未驗、Visual Fidelity Gate 判定與 CI 待獨立 QA／PR。結果＝Measurement §8／Migration Plan §18。**下一步＝Phase 4 步驟 0（📊 市場頁文字線框〔W2、W3、W9〕送客戶；拍板前不得寫 Phase 4 UI code）。**
- **Phase 4 步驟 0 完成（2026-10-30；docs-only，`src/`、`tests/`、`app.py` 0 diff；待客戶拍板）**：`docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md`（rev1）＝📊 市場頁現況重測（夾具、1.59.2；全頁高 5575／7966、結論句頂端相對 H2 +942／+1802、第一屏 0 張圖、6 張 350px 原生圖）＋能力盤點（Old→New 19 項、12 項改形資訊皆有保留處）＋桌機／手機文字線框（含冷啟動與 Missing 路徑）＋**客戶決策表 Q1～Q8**（W9／`CV1-DR-12` 欄數與手機排法、W2 指路句、W3 摺疊標籤、主圖形態、結論句位置、風險卡縮短行、手機第一屏）＋風險／守衛預估（FACT：`z60 _BASE_DIGEST` 不涵蓋 `src/ui/views`／`src/ui_v2`；`page_market.py` 受 `test_nav1_revert_chain`＋`test_uim_revert_chain` 兩條還原鏈、`_market_blocks.py`／`_ui_kit.py` 無 sha 鏈）。靜態示意（`compact.py` 真產出）實測 Q1 三案：桌機 tile 列 163／145／145、手機 356／B2 299（B1 389、C 467）。證據＝`docs/vnext/phase4_market/`；Plan §19；BACKLOG 同步。**下一唯一安全接手點＝等客戶就線框 §6 拍板；拍板前禁止任何 Phase 4 UI code。** ⚠️ 單組撰寫、未經第二組驗證；真資料態、真冷啟動、floor 1.56（本頁）、手機實機、Streamlit Cloud 未驗。
- **Phase 4 步驟 0 客戶裁示已落盤（2026-10-30，DEC-117；docs-only，`src/`、`tests/`、`app.py` 0 diff）**（上一點「待客戶拍板」已解除；有意識的更新，不是漏刪；決策者 客戶（DEC-117）＋AI 總管〔事實更新〕）：客戶裁示 **Q1=B**（桌機 3 個核心狀態 tile：市場位階／建議總持股水位／今日主要風險；「🚀 更新今日戰情」為頁首主 CTA、不占 tile；手機 2＋1；客戶明示「固定 3 欄」是桌機核心狀態網格要求、手機依可讀性自適應——客戶解釋記於 DEC-117，`CLAUDE.md` 不改；`CV1-DR-12` 結案）／**Q2=A′**（維持說明句、縮短、保留「指標危險度」「指標明細（16 項）」與指向最上方，不新增 chip）／**Q3=A**（圖用「為什麼／來源／限制／去哪補」；tile／⚡ 維持「查看依據」）／**Q4=P-B**（台股趨勢＝Primary，原生圖＋MA＋y 軸＋圖例；國際 5 系列＝Secondary small multiples、無數字；不做切換列；趨勢未定義仍顯示 `⬜ 尚未定義`）／**Q5=B**（**新順序：頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡需要處理 → AI／資料狀態 → Primary Visual**；**取代 DEC-105 1A 在市場頁的舊相對順序**，DEC-105 原文不改、條頭加 📌）／**Q6=A**（風險縮短行「燈色＋桶名＋燈名＋方向」；未評估不等於安全、資料不足／無法判定、尚未載入、真錯誤等退化／護欄句外露逐字）／**Q7=A**（手機 Primary 可在第一屏下方，Gate 登記 mobile exception；手機優先序 結論 > 核心狀態 > 是否需行動 > Primary；Primary 緊接 L1 決策區、不得被 L2／L3 插隊）／**Q8 全 A**（圖 C 原句→「為什麼」、更新 radio＋長說明→「更新選項」、⚡→一行 bar＋展開清單；只能下沉不得刪除）。落點：DEC-117（逐字原文＋supersede 表）；線框 §6 各題裁示＋**§10 施工驗收條件**；契約、Gate、Migration Plan **§20**。**Model×Effort**：客戶同意頁面組裝切 **Opus 5.5＋High**，並指示先停在安全 checkpoint 等其回覆「改好了」才施工；機械式工作可在完整安全 checkpoint 通知後降回 Sonnet 5.5＋Medium。**下一唯一安全接手點＝等客戶回覆「改好了」後才寫 Phase 4 UI code。** ⚠️ 整理表與 supersede 判讀為單組產出、待兩組獨立 QA。
- **Phase 4 P4-1（📊 市場頁第一屏）實作完成、待獨立 QA（2026-10-30；分支 `ccr-c8ef17de-9tw7yt` 本地 commit，未 push、未開 PR；中間批，Visual Fidelity Gate 未判）**（上一點「等客戶回覆『改好了』」已解除：客戶已回覆；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）：動檔＝`src/ui/views/page_market.py`（區塊順序 Q5=B；頁首 CTA；狀態列逐字拆兩處；逐項資料日句下沉「資料來源與完整度」）、`src/ui/views/_market_blocks.py`（`render_core_tiles` 3 tile／手機 2＋1、`render_update_cta`、風險縮短行與整句下沉、`DANGER_POINTER` 24 字、位階 tile 唯一「🔍 查看依據」吸收原 hover-only 出處、⚡ 一行 bar；`render_hero` 因被取代成孤兒而刪）、`src/ui/views/_ui_kit.py`（`single_submit_form` 加性 `options_note`，None 時逐呼叫不變）；`page_today.py`、`app.py`、`services／compute／data／shared`、`requirements.txt`、`compact.py` 0 diff。守衛＝`tests/test_p4_1_market_first_screen.py`（新）＋既有三檔改寫（等強／加嚴，皆附 📌）＋P4 還原鏈頭節 `tests/test_p4_revert_chain.py`（基底 `7484c57b`，接 `uim_revert_for` 開頭，全鏈實跑綠）；17 項 mutation 全轉紅。逐條狀態＝線框 §10.7；PR 五段＝`docs/vnext/phase4_market/p4_1/PR_NOTES.md`。**未過／待總管判斷**：C1-10（手機第一屏放不下 ⚡ bar，loaded y1016／cold y900 vs 可用 791）、C1-9 與 2026-09-24「真錯誤留在收合區外」客戶裁示的衝突（partial 報告態手機結論被推出第一屏）。其他三頁與 `?legacy=1` 與開工前基底逐字相同（實測 8 組）。⚠️ 全部為實作組單組產出，未經第二組驗證。
- **DEC-118 客戶裁示已落盤（2026-10-30）**：問題 1=A（手機「⚡ 需要處理」列 mobile exception：緊接 3 核心狀態之後、不得被 L2／L3 插隊；第一屏優先今日結論＋核心狀態）／問題 2=D1（更新部分失敗的真錯誤外露、放今日結論正下方、不得擠出今日結論）；另落盤 Customer Decision Gate 輸出硬限制（`PROJECT_RULES.md` 第 3 節）與 GitHub Verification Gate 以當下 `origin/main` 為準（第 2 節）。P4-1：C1-10 新條件守衛已落地；**D1 實作停點（實作組未動結構、未改 `page_today.py`）**：① `page_today._render_refresh_report` 一次畫完「真錯誤 `st.error`」與「預設收合的報告 expander」，沒有可單獨呼叫的 API；要把真錯誤放到今日結論下方、報告標題留在 CTA 下方，只能 (X) 改 `page_today.py`（拆成兩支、今天頁輸出逐字不變，但受多條還原鏈守衛且 DEC-081 Q1=C「驗收前不改」）、(Y) 在 `page_market` 複寫約 90 行報告渲染（第二套、需逐字 parity 測試防漂移）、或 (Z) 只在「報告有真錯誤」時把整份既有報告（真錯誤＋收合標題）改畫在今日結論正下方（零複寫，但 X3／X10「頁首更新鈕下方」指路句在該態不準）；② 即使 D1 落地，partial 態真錯誤區塊在手機約 330px 高，放在結論下方會把位階｜水位列推出第一屏（結論底 ≈632＋330 ≈ 960 > 可用 791），與 DEC-118 理由 1「第一屏優先維持今日結論＋核心狀態」互相牽制。 ⚠️ 單組產出。
- **DEC-118 D1 已實作（總管判定 Z，2026-10-30）**：報告含真錯誤時整份既有報告畫在今日結論正下方（真錯誤外露、緊接結論），否則照舊在 CTA 下方；C1-9 嚴格化、D1 partial、C1-10（⚡ 緊接 tile）守衛＋M26～M30 必紅；還原鏈以基底 `7484c57b` 重產；手機今日結論四態皆在第一屏內（partial 449～568），partial 態 3 tile 被下推（客戶知情接受）；Fast 35737／slow 183 passed、0 failed；floor 1.56.0 市場頁 AppTest 321 passed。逐條＝線框 §10.7.3。（上一點「D1 停點」已解除；有意識的更新，不是漏刪；決策者 AI 總管） ⚠️ 單組產出。
- **P4-1 QA 第二輪修正（2026-10-31）**：DEC-118 送審題幹附錄、Gate §8 但書、Z fallback 擴大、`WATER_REPORT_DISCLOSURE` 位置詞、CSS 白名單加嚴、degraded 夾具；M31～M38 必紅；Fast 35748／slow 183 passed、0 failed；新登 P2 `P1R-P4-SPEED-HINT-HEADER-WORD`、`P1R-P4-RISK-TILE-FIRST-SCREEN`。⚠️ 單組產出。
- **Phase 4 P4-2（📊 市場頁圖區）實作完成、待獨立 QA（2026-10-31；分支 `ccr-c8ef17de-9tw7yt` 本地 commit，未 push、未開 PR；中間批，Visual Fidelity Gate 未判）**：動檔＝`src/ui/views/_market_blocks.py`（圖區重寫＋四段摺疊元件 `ChartFold`）、`src/ui/views/page_market.py`（圖區編排：Primary→國際小倍數→圖 D→圖 C）、`src/ui_v2/compact.py`（加性 `SmCell.missing_verbatim`）；`src/services|compute|data`、`shared/`、`app.py`、`page_today.py`、`requirements.txt`、`markup.py` 0 diff。守衛＝`tests/test_p4_2_market_charts.py`（新）＋既有四檔改寫（等強／加嚴，皆附 📌）＋P4 還原鏈同基底 `7484c57b` 重產；24 項 mutation 全轉紅。逐條＝線框 §10.8；PR 五段＝`docs/vnext/phase4_market/p4_2/PR_NOTES.md`。其他頁與 `?legacy=1` 與 P4-2 前基底逐字相同（實測 8 組）。**下一唯一安全接手點＝兩組獨立 QA → push／PR／CI → P4-3 正式 Gate。** ⚠️ 單組產出，未經第二組驗證。
- **Phase 4 P4-3（📊 市場頁正式 Visual Fidelity Gate）初判完成＝❌ FAIL（2026-10-31；docs＋量測腳本／截圖，`src/`、`tests/` 0 diff；基準 main `228b9fa9`，P4-1 #984、P4-2 #985 已合併）**：A5（桌機全頁高 3061／1517＝2.018×）、A6（手機 Primary 圖高 220 > Q3 ≤140）、A8（外露 >32 字非客戶原句 3 塊）❌；🟡 A4、A10、A11、V3 共 4 項觸發合計規則；PASS 14 項；Q7／DEC-118 例外條件實測成立。**Stage 維持未完成**。證據＝`docs/vnext/phase4_market/p4_3/GATE_REPORT.md`（含零資料語意證明 (a)～(g)、線框 §10 全表最終狀態、其他頁／`?legacy=1` 前後 8 組逐字相同、floor 1.56.0 量測結論相同）。**單組初判，獨立 QA／總管複驗未做**；未驗：真資料、手機實機、Cloud、1.57～1.58。待客戶 3 題＋內部 P4-4 小修批；BACKLOG 新登 `P1R-P4-GATE-A5-PAGE-HEIGHT`／`-A6-MOBILE-CHART-HEIGHT`／`-A8-LONG-TEXT` 等 9 列。（有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）
- **Phase 4 P4-4（📊 市場頁內部小修批）完成、待獨立 QA（2026-10-31；本地 commit，未 push、未開 PR；單組）**：A8 外露 >32 字 3 塊已修（原整句逐字下沉）、F3 守衛 `tests/test_p4_4_market_exposed_text.py` 已補（9 項 mutation 轉紅）、F1 手機圖例**未修**（須換圖元件，停點回報）；A5／A6／四項 🟡 未動、等客戶裁示；Gate 仍為初判 ❌。證據 `docs/vnext/phase4_market/p4_4/`＋`p4_3/GATE_REPORT.md` §14。
- **Phase 4 P4-5（客戶裁示落盤＋F1 修正＋Gate 重判）完成、待獨立 QA（2026-10-31；本地 commit，未 push、未開 PR；單組）**：客戶 DEC-119（題 1=A 手機 Primary 維持約 220px＋自訂圖表；題 2=A 桌機 2.02× 為已知輕微偏差）已落盤（DECISIONS DEC-119、Gate §8 兩項例外、GATE_REPORT §16、BACKLOG 5 列結案、PROJECT_RULES 第 24.2 節 📌）；**F1 已修**＝圖 A `st.line_chart`→`st.vega_lite_chart`（`src/ui/views/_market_blocks.py`；圖高 220、5 項圖例手機全可見、不遮圖、無水平捲動；L2／L3／`page_market.py`／`compact.py`／page_today／app／requirements 0 diff）；圖 A 守衛改寫為 vega spec 語意守衛、15 項 mutation 轉紅、floor 1.56.0 同結果。**Gate 重判仍 ❌（僅 🟡≥4：A2／A4／A10／A11；單項 ❌＝0）**；待客戶 1 題（四項輕微偏離是否接受，AI 總管推薦 A）、獨立 QA 複驗、CI 綠；Stage 仍未完成。證據 `docs/vnext/phase4_market/p4_5/`。（有意識的更新，不是漏刪；決策者 客戶（DEC-119）＋AI 總管〔事實更新〕）
- **Phase 4 P4-3 Gate 收尾：客戶 DEC-120「選 A」（2026-10-31；docs-only；已隨 PR #987 合併 `f42ce0e6`）**：📊 市場頁 A2／A4／A10／A11 四項 🟡 接受為已知合理偏離，不因「🟡≥4 視為 ❌」升格（⛔ 僅市場頁；他頁不繼承、仍照規則）。~~**Phase 4 狀態＝Gate PASS（DEC-120），待 CI 綠＋獨立 QA 複驗＋merge**；⛔ 尚未 merge、尚未結案。~~ **Phase 4 已結案：PR #987 squash 合併 `f42ce0e6`，Fast＋Slow CI 綠、獨立 QA 複驗通過、DEC-120 Gate PASS；BACKLOG `P1R-PHASE4-MARKET` 已關閉。**（2026-10-31 有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；依據：PR #987 squash 合併 `f42ce0e6`，Fast＋Slow CI 綠、獨立 QA 複驗通過）落點：DECISIONS DEC-120、Gate §8、`p4_3/GATE_REPORT.md` §17、BACKLOG。下一個接手點：Phase 5（🎯 標的頁）步驟 0（重測＋W3–W6 文字線框＋Customer Decision Gate；客戶核准前禁寫 UI code）。（有意識的更新，不是漏刪；決策者 客戶（DEC-120）＋AI 總管〔事實更新〕；上一條「Gate 重判仍 ❌、待客戶 1 題」已被取代，原文保留）
- **Phase 5 步驟 0：🎯 標的頁現況重測＋能力盤點＋文字線框＋Customer Decision Gate（2026-10-31；docs-only；分支 `ccr-c8ef17de-9tw7yt`；單組、未經第二組驗證）**：以 main `0369285b` 重測（夾具＋真本地板塊快取）：全頁高 5084／7149（夾具）、7240／14051（42 產業）＝blueprint 2.2～4.4×；產業矩陣 42 列全量外露、每列重複同一句 Missing；候選區標題在真資料下落在桌機第 4 屏、手機第 11 屏；第一屏 0 張 Primary 圖。產出：`docs/vnext/PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md`（能力盤點 T-01～T-52、桌機／手機／冷啟動線框、驗收條件草案 C／N、Visual Fidelity 預期上限）、`docs/vnext/phase5_target/p5_0/`（量測 JSON、截圖、`CUSTOMER_GATE_DRAFT.md`）。客戶決策 3 題（Q1 產業 Top 5 形式＋排序鍵〔現行矩陣順序＝象限→名稱、不依 `x_yi`；觸及排序規則，風險已提升〕、Q2＝W4 選股條件預設＋W5 候選提前、Q3＝W3 摺疊標籤＋W6 排序依據句），各附 AI 推薦；**待客戶裁示，無新 DEC；客戶核准前不得寫 Phase 5 UI code；DEC-117／118／119／120 的例外不繼承**。`src/`、`tests/`、`app.py`、`requirements.txt`、`shared/` 0 diff。未驗：真資料態、真冷啟動、手機實機、Streamlit Cloud、floor 1.56。（有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）

- **Phase 狀態（2026-10-31，live main `265040d9`）**：Phase 4（📊 市場頁）已結案（#987／#988）；Phase 5（🎯 標的頁）step 0 已合併（#989），客戶裁示 Q1=A／Q2=B／Q3=A 已落盤（DEC-121），~~**UI 尚未開始**~~ **UI PR1～PR3 已合併（#992 `6c69208`、#993 `f2a6a8a`、#994 `4e4aa5e`）；自評 Gate ❌0／🟡3 待獨立 QA，三項 🟡 由 Final UI Stage C 承接（總管內部，不送題）**（2026-11-02 過期狀態更正，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；依據 `git log`）；OneBrain OB-0 架構治理已在 main（#986）；quota-safe checkpoint 已合併（#990）。

- **Phase 5 PR3：🎯 標的頁第三區「單一股票」＋進階分析（2026-11-01；~~分支 `ccr-a0b4e085-ijdaio` 本地，未 commit／push~~ **已合併 PR #994 `4e4aa5e`**（2026-11-02 過期狀態更正，有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕）；單組、未經第二組驗證）**：判型結果卡→chip（原卡下沉「▸ 判型明細」；UNKNOWN／失敗灰紅卡維持外露）、3 張摘要卡（財報體檢／357 估值／近 20 日籌碼，值只取既有 builder 欄位）、計數 chip「命中 N 項」「未通過／缺漏 M 項」分開、誠實主圖槽、「▸ 完整分析」預設收合且原樣。0 diff：`app.py`、`requirements.txt`、`shared/`、`src/services|compute|data`；無新 DEC。追加（總管裁示）：A8＝選股／單檔 freshness 整句→`抓取`／`⚠ 可能已過期` chip、整句下沉查看依據，`PICK_NOTE` 縮句；A2＝手機元素間距 .5→.125rem。量測（夾具，第二輪）：桌機全頁高 3104／3404（3／50 候選，1.42／1.55×）、手機 2850／3105（0.89／0.97×）、cold 1827／1551；Primary 140px，手機整張圖 633–773＜導航 791（餘裕 18px）；QA P2（計數 chip 真項數、全未評估顯示 `⬜ 尚未評估`、部分未評估另加 `⬜ k 塊尚未評估`）與 P3（chip 列／cold 佔位框疊壓，本批加重處已修，v2 卡貼合既有已登記 `P5-V2CARD-BOTTOM-OVERLAP`）已修；無水平捲動。自評 Gate＝❌0／🟡3（A5 桌機、A4、A10；第一輪❌1＋🟡4）→ 待獨立 QA 與客戶／總管對三項 🟡 裁示；證據＝`docs/vnext/phase5_target/p5_3/GATE_REPORT.md`。測試：新增 `tests/test_p5_3_target_single.py` 36 項（含 mutation）；streamlit==1.56.0 venv 跑 p5／uit 相關 AppTest 全綠。Phase 5 **未結案**（Gate 未過）。

## 49. Final UI Contract Freeze（DEC-122，客戶 2026-11-02；append-only；~~**客戶指示 A 生效；Freeze 內容待客戶拍板（含 Q1～Q3）——不是 Approved**~~ **Freeze 已由客戶拍板（Q1=A／Q2=A／Q3=A，2026-11-02）；Stage A 待 Freeze 獨立驗收 PASS**（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔事實更新〕；原文刪除線保留））

- **main**：撰寫時 `origin/main`＝`ce8422d`（cron；最後非 cron 合併＝#994 `4e4aa5e`；撰寫組 2026-11-02 `git fetch` 實查）。cron 會推進 tip，**一律以當下 `git fetch origin` 為準**。
- **Phase 5 實況（更正）**：🎯 標的頁 PR1～PR3（#992～#994）**已合併**；自評 Visual Fidelity Gate ❌0／🟡3（A5 桌機、A4、A10；單組、夾具）待獨立 QA；三項 🟡 由 Final UI Stage C 承接（總管內部處理，不送題）；BACKLOG `P1R-PHASE5-TARGET` 仍 open。上方 §48 兩條「UI 尚未開始」「本地未 commit」已加刪除線更正。
- **客戶方向（DEC-122，逐字見 DECISIONS）**：主線＝四頁 Final UI 收斂 → UI 與 Decision Context 完全解耦 → Headless Decision Digest → Single Action Authority → OneBrain runtime 最後接入 → Real-data／Mobile acceptance → 舊 UI 最終替代確認後才移除。**三條 invariant**：UI 越簡潔，Decision Context 不能越少；Deterministic System 是唯一動作權威，OneBrain 只能推理、解釋與反證；Presentation Slice ≠ Decision Context ≠ AI Output。
- **本輪裁示＝A（生效）**：先做 **docs-only Final UI Contract Freeze**，⛔ Stage A production implementation。~~**Freeze 三份文件是送客戶拍板的草案，客戶尚未拍板**；~~ **Freeze 已由客戶拍板（2026-11-02）**；~~Freeze 合併＋客戶拍板＋裁示 Q1～Q3 後才能開始 Stage A。~~ 客戶已拍板並裁示 Q1～Q3（2026-11-02）；**Stage A 須待 Freeze 獨立驗收（含必要 QA）PASS 後才能開始**（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）。
- **正式文件位置**（正式契約層；位階見 `PROJECT_RULES.md` 第 25 節）：
  - 契約：`docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md`（四頁 Blueprint、雙模式＋Session 隔離＋加入觀察 CTA disabled、Semantic Chip、四態、Single Action Authority、No Uncalibrated Probability、Risk Cap Enforcement、Field-level Freshness、單檔 Valuation、大盤 EPS×PE 分離、Digest Viewer／唯讀 Rule Registry、Presentation Slice ≠ Decision Context、Headless Digest、OneBrain 邊界、Desktop／Mobile L1 線框、Stage A–J＋Model×Effort＋Stage A DoD、完成定義、Q1～Q3）
  - 能力對照：`docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md`（85 列；critical 7：M02、M03、T16、T21、H01、H02、E08；舊獨有 41 列；機械計數，量測日 2026-11-02）
  - 取代關係：`docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md`~~（S1～S20；S10／S11 條件式待 Q3；條件式清單；防誤讀清單）~~ （S1～S20；S10／S11 依 Q3=A 正式取代；§2 裁示結果；防誤讀清單）
- **重要現況知識（FACT，單組 grep／讀碼，非窮舉）**：
  - Risk Cap 規則存在；📊 市場頁數值隱藏（DEC-081 Q2-2／`RC-VISIBILITY`），💼 持股頁卡⑤依 DEC-051／PQ-C6-3（客戶 2026-10-16 核准）外露建議持股區間（已核准、非違規）；**沒有**「實際曝險 > 上限 → 禁止新增」規則；持股 Sheet 表頭無現金／總資產 →「目前曝險」算不出（→ Q1，含兩頁顯示是否統一）。
  - 正式動作來源只有 ETF `action_branch` 七分支＋個股 `swap_level` 四級；**沒有**「減碼 1/2」「全出」規則（→ Q2）。
  - 正式 rule id 只有 `RULE_ID_ALLOWLIST` 6 個；`R-VIX-02` 類 id 不存在；Rule Registry 只能顯示已存在 id。
  - Decision Digest builder 0 production caller；Headless 尚未成立（Stage F 前置）。
  - Forward EPS 資料源不存在 → Forward／Scenario 估值不可呈現；大盤 EPS×PE 維持 Research（`DEC092-EPSPE-HIGH-GATE`）。
  - 新四頁未見數值型未校準機率；`page_market`「信心度」實為資料齊備度（改名列 Stage B）；`recession_probability` 未校準 logit ⛔ 上新 UI。
  - `page_hold` ⑦ AI 戰情總結直呼 Gemini（非 Digest、無 grounding）＝違反 Final 契約，待 Stage G。
  - `guard_chip` 在 🎯 標的頁被用於判型／計數／估值口徑＝違反 Semantic Chip Contract，待 Stage A／C。
- **Stage 順序**：A 共用呈現基礎 → B 市場 → C 標的 → D 持股 → E 我的／Audit → F Headless Digest → G OneBrain → H 跨頁一致 → I 真資料／手機驗收 → J 舊 UI Removal Gate（取代 DEC-109 三十一 Phase 編號；Digest 凍結前不寫 prompt／glue 仍有效）。BACKLOG §5.1.17 `FUI-*`。
~~- **Decision Gate PENDING（Freeze 本身亦待拍板）**：~~ - **Decision Gate（已全數裁示 A，2026-11-02；本條為送題當時內容）**（2026-11-02 Freeze 獨立驗收修正；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔驗收修正〕；原文刪除線保留）：Q1（Risk Cap 曝險分母／數值啟用／兩頁區間顯示；總管推薦 A＝只定形狀、數值另開 RC Gate、兩頁維持現狀）、Q2（持股動作詞彙；推薦 A＝沿用既有分支原名、依「加／留／換／減」分組、無動作「今日無需調整」、減碼 1/2／全出待 DEC-053）、Q3（📊 市場頁手機第一屏；推薦 A＝照 §40「是否行動」進第一屏、改 DEC-117 Q1 手機排法與 DEC-118 問題 1；B＝維持 DEC-118）。裁示前一律採較嚴暫行讀法、既有裁示照舊。
- **限制**：Freeze 三份文件與 DEC-122 整理皆單組撰寫、未經第二組驗證（`FUI-FREEZE-SECOND-AUDIT`）；未跑 runtime、未在真資料／手機實機／Streamlit Cloud 驗。
- 📌 **客戶拍板（2026-11-02；DEC-122 裁示段逐字；DR-2026-11-02-2）**（2026-11-02 客戶裁示 Q1～Q3 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-122 裁示）＋AI 總管〔事實更新〕；原文刪除線保留）：
  - **main**：Freeze 草案已合併 PR #995（`origin/main`＝`c1e10a6`，撰寫組 `git fetch` 實查；以當下 fetch 為準）。裁示收斂批落盤於分支，待 PR。
  - **狀態**：Freeze＝**客戶拍板版**；~~**Stage A 須待 Freeze 獨立驗收（含必要 QA）PASS**（客戶原文「不得因本裁示直接跳過 Freeze 驗收」）。~~ **Freeze 獨立驗收兩輪已 PASS（第一輪 PASS with fixes F1～F6、第二輪 PASS；單組驗收，已揭露）；下一個唯一安全工作＝待客戶切換 Model×Effort（Opus 5.5＋High → Sonnet 5.5＋Medium）後開 Stage A-1（≤3 項）**（2026-11-02 Freeze 獨立驗收第二輪 PASS 後同步；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留）。
  - 📌 **上一句「下一個唯一安全工作＝待客戶切換 Model×Effort 後開 Stage A-1」自 2026-11-02 起失效**：客戶 New UI2 裁示（DEC-123）停止原 Stage A；現行狀態與下一步見 **§50** 與 `docs/HANDOFF.md`「Safe Handoff（2026-11-02 New UI2）」（有意識的政策變更，不是漏刪；決策者 客戶（DEC-123）；本節原文一字未改）。
  - **產品方向**：「簡化 UI，但不簡化 Decision Context」；前台只呈現真正需要決策的資訊，完整資料不得因 UI 精簡而裁掉。
  - **正式架構鏈**：Canonical Data → Deterministic Rules／Formulas → Risk Cap／Hard Constraints → System Action State → Decision Digest → OneBrain → UI。
  - **6 條永久 invariant**（契約 §0.1.3）：UI 越簡潔 Decision Context 不能越少；Presentation Slice ≠ Decision Context ≠ AI Output；System Action State 是唯一正式動作權威；OneBrain 只負責 reasoning／summary／explanation／counter-evidence／limitations；OneBrain 不得創造第二套 portfolio action、不得覆寫 deterministic action、不得繞過 Risk Cap；OneBrain 讀完整 Decision Digest，不只讀 UI Top-N／摘要。
  - **Q1=A**：Risk Cap 只凍結規則形狀；超限＝禁止新增曝險；曝險或有效上限任一不足 → `⬜ 無法判定`；unavailable／not evaluated ≠ safe、不得允許加碼；⛔ 發明分母／現金／總資產／替代值；數值啟用另開 Gate（`FUI-RC-NUMERIC-GATE`）；持股頁既有區間維持。
  - **Q2=A**：沿用既有分支原名；「加／留／換／減」僅呈現分組；只有無正式動作時才「今日無需調整」；資料不足／未評估不得算無需調整；「減碼 1/2」「全出」⛔ 映射或產生（`FUI-PROPORTIONAL-ACTION-RULES`）。
  - **Q3=A**：📊 市場頁 Mobile-first；手機第一屏＝市場目前狀態＋Risk Cap＋是否需要行動＋主 Update CTA；今日主要風險緊接其後、仍屬 L1；DEC-117 Q1 手機 2＋1、DEC-118 問題 1=A、DEC-120 A10／A11 **正式取代**（supersede map S10／S11）。
  - **工作模式**：Silent Autonomous Cruise、每批 ≤3 項；Model／Effort 不足 → 立即停下通知客戶、等客戶修改後才繼續，不得自行切換。
  - **限制**：裁示收斂批仍為單組撰寫；capability map critical 仍 7 列（Stage J 第 6 條不成立）。

## 50. New UI2 Greenfield Presentation Layer（DEC-123，客戶 2026-11-02；append-only；**客戶裁示生效**；~~Architecture Gate 草案待客戶裁示（G1、G3′、四頁線框、G2＋#996 合併確認）——不是 Approved 架構；目前只存在工作樹、尚未落盤 GitHub~~ **Architecture Gate 已由客戶裁示 Q1～Q4 核准；已落盤 #997；待 #997 獨立稽核＋合併後凍結（現況見 §51）**（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）＋AI 總管〔事實更新〕；原文刪除線保留））

- **main**：撰寫組 2026-11-02 `git fetch origin main` 實查 `origin/main`＝`c1e10a62`（#995）；工作樹＝PR #996 head `139e315b`（Freeze 收斂＋獨立驗收 PASS，**尚未合併**）。cron 會推進 tip，**一律以當下 `git fetch origin` 為準**。
- **客戶裁示（DEC-123，逐字見 DECISIONS）**：立即停止原 Stage A／現有 New UI 延續路線；**後續正式 UI 路線改為 New UI2 Greenfield Presentation Layer**——「全新的 Presentation Layer，但沿用成熟的底層資料與投資邏輯」，**不是整套系統重寫**。#996 維持現狀、定位不變（⛔ 擴大範圍、⛔ 丟棄）；⛔ 修改 production UI、⛔ 刪除現有 New UI／Old UI、⛔ 新增 Risk Cap runtime／OneBrain runtime、⛔ 重寫既有 data／services／rules。
- **三代 UI**：Old UI（`src/ui/tabs|etf|pages|render`＋`app.py` 內嵌；`?legacy=1`）＝只讀 Logic／Capability Reference、禁止修改；現有 New UI（`src/ui/views`＋`src/ui_v2`；預設四頁）＝**Legacy New UI／Reuse Candidate**，停止當主線 patch；**New UI2**＝未來唯一主要 Presentation Layer（尚無程式；提案目錄 `shared/ui2_contract`（L0）＋`src/services/ui2/{*_feed,*_vm}`（L3）＋`src/ui2/{shell,components,views}`（L5）＋`app_ui2.py`（L6））。⚠️ `src/ui2`（New UI2）≠ `src/ui_v2`（Legacy New UI 共用元件層）。
- **目標鏈（客戶原文）**：Canonical Data／Sources → Normalization／Validation → Deterministic Rules／Formulas → Risk Cap／Hard Constraints → System Action State → View Model／Presentation Contract → New UI2；未來 System Action State → Decision Digest → OneBrain；**New UI2 與 LINE 都是 consumer**；LINE ⛔ 形成第二套投資大腦。
- **Freeze（DEC-122）的位置**：**全部 semantic contracts 保留為 New UI2 的 input**（Q1=A／Q2=A／Q3=A、產品方向、6 條 invariant、四態、chip、Risk Cap boundary、Single Action Authority、freshness／provenance、Digest、OneBrain boundary、Mobile-first、四頁 IA）；**施工路線**：Stage A 暫停／被取代（語意項移作 UI2 components 需求）；B～E 改為 New UI2 四頁（Freeze 各頁語意內容仍是需求）；F～J 保留（F 與 UI2 先後依 G3；J 對象擴為 Old UI 與 Legacy New UI）（F 與 UI2 先後依 G3′；撰寫組讀法，客戶可推翻；DEC-123「與 DEC-122 的關係」）。
- **正式文件位置**（草案）：Architecture Gate `docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md`；Reuse Matrix `docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`（88 列：KEEP 26／WRAP 21／PORT 24／REIMPLEMENT 2／RETIRE LATER 5／DO NOT TOUCH 10）；四頁線框 `docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md`（手機 390×844 先、桌機 1440×900 後；W-1～W-9 送核准點）；待辦 BACKLOG §5.1.18 `NUI2-*`。
- **送客戶四題（PENDING）**：**G1** Preview（推薦 A：獨立入口＋獨立 Cloud 預覽 app，需客戶人工操作）；**G3′** System Action Aggregator（~~系統動作彙整層~~）（推薦 A′：先建單一 headless L3 彙整層——合併 ETF 七分支與個股四級、加／留／換／減計數、「沒事 vs 判不出」、加碼列 Risk Cap 標註、跨頁 ⚡ N；不新增規則、不新增寫入〔只觸發既有服務的既有副作用〕；UI2／LINE／Digest 共用、VM 不聚合；請客戶確認不算新增 runtime；B：等 Stage F 完整 Headless Digest）；**四頁線框核准**（W-4、W-5〔推薦 A：加／換／減＋暫停加碼計入，其餘「留」只做分布〕、W-9、W-10〔⚡ N 來源〕、W-11〔持股桌機對齊 Freeze〕）；**G2** Cutover（推薦 A：逐頁 preview 驗收、全過後一次切預設、`?ui=1`／`?legacy=1` 隱藏保留、回滾一行）＋**#996 可否現在合併**（推薦：可；合併後本 Gate 以新 PR 落盤）。LINE 維持現狀不送題（客戶已明說）。獨立稽核（2026-11-02，單組）判 PASS with fixes，已改寫。
- **重要現況知識（FACT，單組 grep／讀碼，非窮舉；invC／invD）**：
  - System Action State 層**不存在**；Decision Digest builder **0 production caller**；`st.session_state` 是事實上的狀態匯流排（L3 寫 session 者 9 檔）；主 Update CTA（`refresh_macro_now`）是 producer 鏈。
  - 風控／語意閘門住在顯示層：`src/ui/views/risk_cap_gate`（L5）、`src/ui/render/station_cards.cruise_or_gap`（L4，Old UI）→ UI2 前須 PORT（預設新建＋parity，Old UI 與 Legacy New UI 原處皆不改；`cruise_or_gap` 去向＝System Action Aggregator（~~系統動作彙整層~~），依 G3′）。
  - Legacy New UI 依賴 Old UI（`tab_today.Card` 等）；c3 guard **不擋 L5→L5**，且新目錄未登記時五條規則**靜默失效**（`src/ui_v2` 前例）→ UI2 首個實作 PR 須同 PR 登記＋meta 測試。
  - Old UI `section_mid` render 期登記 caps／conflicts（OLD-7）：`get_allocation` 以 `_derive_intrinsic_caps()` 重算並剔除同名登記 ⇒ **建議持股數字不受影響**，只有 `register_conflict` 揭露文字隨舊頁 render 而不同（稽核 F4 更正，P2）。
  - App 端另有不經天花板仲裁的持股比例輸出：`check_macro_veto().max_position`、`market_strategy.exposure_pct`、💼 ④ `posture_range`（未套天花板）——登記於 `NUI2-LINE-SECOND-BRAIN`，UI2 ⛔ 整包搬。
  - LINE：`market_alert_banner`「建議持股降至 10%／20%」＋「請以警語為準」＝第二套動作權威；週報自建定調；cron regime 來源與 App 不同；LINE 看不到 Risk Cap；持股頁 ⑦ Gemini 直呼——皆**登記**（`NUI2-LINE-SECOND-BRAIN`、`NUI2-LINE-REGIME-SOURCE`、`FUI-PUSH-ACTION-CONSISTENCY`、`FUI-HOLD-GEMINI-DIRECT`），本批不改。
  - `app.py` 被 82 個測試檔以原始碼字面讀取（改入口爆炸半徑大）；`tools/visual_fidelity/harness_app.py` 不支援 👤 我的。
- **完成條件（客戶 (5)-13）**：architecture frozen、reuse matrix frozen、four-page wireframe approved、migration boundary approved、preview strategy approved、cutover strategy approved、no unresolved architecture blocker——全部成立才發「🟡 Model / Effort Change Gate：New UI2 architecture 已凍結，後續 presentation implementation 可切 Claude Sonnet 5.5 + Medium。」並**立即停手**；⛔ 自行開始 production。
- **限制**：三份 Architecture Gate 文件與本段皆單組撰寫、未經第二組驗證（`NUI2-ARCH-SECOND-AUDIT`）；未跑 runtime、未在 Streamlit Cloud／手機實機／Python 3.14 驗；OAuth 轉跳後旗標遺失為讀碼推論。

## 51. New UI2 Architecture Gate 客戶裁示 Q1～Q4（DEC-123，客戶 2026-11-02；append-only；**客戶核准**；~~待 #997 獨立稽核＋合併後凍結——尚未凍結~~ **#997 獨立稽核兩輪完成（第一輪 PASS with fixes → 第二輪 PASS）；**#997 合併即凍結**（merge SHA 由下一位補記）**（2026-11-02 #997 獨立稽核第二輪 PASS 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留））

- **GitHub 狀態**：#996（Final UI Freeze 收斂）**已合併**，`main`＝`acd1648c`（總管實查；cron 會推進 tip，以當下 `git fetch` 為準）。New UI2 Architecture Gate 草案已落盤為 commit `6d30dcea`（分支 `ccr-a0b4e085-ijdaio`，對齊新 main），**Draft PR #997**；本裁示整合批亦在 #997。§50「只存在工作樹」與 HANDOFF「GitHub 舊接手點寫開 Stage A-1」兩則警語**已解除**。
- **Q1=A｜Preview**：獨立 Streamlit Cloud New UI2 Preview；正式網站不動。**成本控制四點**（客戶原文）：架構／UI 驗收優先 fake／snapshot／view-model scenario；真實外部資料只在 real-data acceptance 或必要人工驗收時使用；⛔ 為 Preview 建第二套 data／service／source pipeline；Preview 與 production 最終讀相同 canonical services／contracts。人工建 Preview App／Secrets／OAuth 網址 → **需要時**才以 🟡 Manual Action Gate 通知客戶，⛔ 提前要求。
- **Q2=A（修正分類）｜System Action Aggregator（共用 System Action Aggregation Layer）**：定位 Existing Formal Rules＋Risk Cap → System Action Aggregator → System Action State／action-facing canonical contract → Decision Digest／New UI2／LINE；**不是第二套規則引擎**。允許 7 項（收集正式結果、收集 Risk Cap state、四類區分、加留換減 grouping、統一計數、「今日無需調整 vs 無法判定」、共用 canonical action-facing view）；禁止 9 項（新規則、新門檻、新比例、AI action、改寫 deterministic result、覆寫 Risk Cap、自行決定減碼 1/2／全出、portfolio write、Sheet write）。**屬新的 runtime component**：本 Gate 只凍結 interface／ownership／I-O contract／tests／migration plan（Architecture Gate §4.6），**實作待 implementation Gate**（`NUI2-AGGREGATOR-IMPL`）；實作前 UI2 動作欄位 `⬜ 尚未提供`。總管原「不算新增 runtime」讀法被客戶推翻。
- **Q3｜四頁線框核准**（線框 §9）：W-4 限輕量 context row／chip（⛔ 搶過查一檔、基本面、valuation／company-first research；市場技術訊號 ⛔ 成為單股主要判斷）；**W-5=A**（加／換／減／暫停加碼計入「今日需處理」；🟡 留意無正式 action code ⛔ 升格）；W-9「可判定覆蓋度」；W-10 transitional contract（Aggregator 完成前舊警示標 source／scope、⛔ 冒充 System Action State、⛔ 第二套 Action Authority、與持股頁衝突並列揭露；完成後同一 canonical action source）；W-11 持股桌機依 Freeze，建議持股區間 ≠ 已啟用 Portfolio Risk Cap。
- **Q4=A｜Cutover**：New UI2 → 獨立 Preview → 四頁逐頁驗收 → mobile／desktop → missing／stale／source failure → real-data acceptance → cross-page consistency → 全部通過 → 一次切成正式 default；現有 New UI 與 Old UI 保留 rollback path；⛔ 先刪程式；正式切換後另進 Removal Gate（`docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`）。
- **永久收尾 Gate**（`PROJECT_RULES.md` 第 27 節）：每批完成前檢查新的 Rule／Decision／Audit finding／Limitation／Backlog／Migration debt，同步 GitHub 正式文件後才能宣告完成；「沒有寫進 GitHub的項目，不視為可靠專案狀態。」
- **正式文件（New UI2）**：Architecture Gate、Reuse Matrix、Wireframes、Migration／Cutover Contract、Audit／Acceptance Checklist（皆 `docs/vnext/NEWUI2_*_2026-11-02.md`）；決策 DEC-123；待辦 BACKLOG §5.1.18、§5.1.19（客戶點名 16 項＋衍生 W-10／W-4／W-5／W-11／收尾 Gate）。
- **下一步**：~~#997 獨立稽核（`NUI2-ARCH-SECOND-AUDIT`）＋合併 → Architecture 凍結 → 發「🟡 Model / Effort Change Gate」後**停手**；⛔ 自行開始 implementation；Architecture 凍結前**不得降模型**（客戶：維持 Opus 5.5＋High）。~~ #997 獨立稽核兩輪完成（第一輪 PASS with fixes → 第二輪 PASS）；**#997 合併即凍結**（merge SHA 由下一位補記）；凍結後**下一個唯一安全工作**＝發 🟡 Model／Effort Change Gate，**客戶切換 Model×Effort 至 Sonnet 5.5＋Medium** 後，經 **implementation Gate** 開第一個 New UI2 批次（建議先 `NUI2-GUARD-REGISTRATION`／View Model boundary（`NUI2-VM-BOUNDARY`）／Preview 入口骨架（`NUI2-PREVIEW`），≤3 項，fake／snapshot 資料）；**未經客戶切換與 Gate 不得開始 implementation**；System Action Aggregator 實作另需 implementation Gate（`NUI2-AGGREGATOR-IMPL`）；Architecture 凍結前不得降模型（2026-11-02 #997 獨立稽核第二輪 PASS 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔事實更新〕；原文刪除線保留）。
- **限制**：裁示整合批單組撰寫；Aggregator I／O 欄位名、Migration 判準、Audit 清單為 AI 總管暫定；未跑 runtime、未在 Streamlit Cloud／手機實機驗。

<!-- PROJECT_STATE_HISTORY_INDEX:BEGIN lines=885-901 archive=docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q2；只搬不改）**：原 L885–L901 已逐字搬至 `docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md`（分冊 L51–L67）。本處原為下列 1 節（標題逐字）：
  - 原 L885–L901 → [分冊 L51–L67](archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md#ps-hist-52)：## 52. New UI2 Batch 1：Guard 登記／VM boundary 骨架／Preview 入口骨架（2026-11-02；append-only；實作組單組、待總管複驗）
<!-- PROJECT_STATE_HISTORY_INDEX:END -->

## 53. New UI2 Semantic Correction Gate（DEC-124，客戶 2026-11-02 (8)；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (8)（逐字見 `docs/DECISIONS.md` DEC-124）；範圍限 (8)-5 三項。基準 `origin/main`＝`57b361ab`（含 #998 New UI2 Batch 1；分支 `ccr-a0b4e085-ijdaio`，實作組 `git status` 實查與 origin/main 一致）。~~**未 commit／push（由總管處理）**~~ **實作已 commit＝`64e6fe2c`（已 push）**；獨立稽核修正批 SHA 由總管補記（2026-11-02 DEC-124 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正／事實更新〕；原文刪除線保留）。#998 整體接受、未回退。
- **做了什麼（0 投資語意；未新增 Risk Cap 規則或數值）**：
  - **① FieldState／capability 語意邊界＝選項 A**：`FieldState` 恰五態（OK／Missing／Stale／Unavailable／Not Evaluated）；`⬜ 尚未提供` 改為 `CapabilityState.NOT_PROVIDED`（`FieldVM.capability`；該欄 `state` 必為 None、⛔ 帶值）；三張字樣表互斥。理由見 DEC-124「落地」（客戶 (8)-2 明言資料語意仍維持五個；影響面只在 New UI2 套件；第 2 項本就需新型別）。
  - **② Risk Cap `⬜ 無法判定`**＝`JudgementState.UNDETERMINABLE`（判定結果，非資料語意；依 Freeze §0.1.4 第 3 點、§8.2、Architecture Gate O4b）；⛔ NOT_EVALUATED、⛔ 綠、⛔ 「今日無需調整」等 safe 讀法。DEC-074／075 客戶逐字 `⬜ 未評估／資料不足` 依原始語境歸 Unable to Determine（字樣不改；單組判讀待覆核）。`⬜ 尚未核准／無法判定` 維持 Not Evaluated（混合字樣，登記待覆核）。canonical spec 未知 `state` 提示改為 raise（原會默默落成 OK／MISSING）。
  - **③ 守衛**：`tests/test_ui2_guards.py` 新增 DEC-124 段（資料語意恰五態、三軸型別互斥、UTD≠NE 不同值不同字樣、字樣跨軸禁用、客戶字樣逐字釘死、Risk Cap 無法判定 ⛔ safe 讀法／綠、capability marker Preview-only 允許清單、未知 state 提示 raise），各附 teeth。既有斷言改寫 6 處（皆標「DEC-124 語意修正」：`NOT_PROVIDED` 從資料態改到 capability 軸、Risk Cap 從 NOT_EVALUATED 改為 UNDETERMINABLE、字樣互斥掃描擴到三張表、查表改依語意軸），**未放寬**（每處斷言數不減、範圍不縮）。
  - **文件**：DEC-124（含客戶 (8) 逐字）＋DECISIONS §5 取代鏈一列；Freeze §0.1.4／§5.1／§5.3／§8.1／§22；Architecture Gate §4.6.5／§4.6.6（O1 增 `undeterminable`、`unjudged→undeterminable`、O2 增 `undeterminable_n`）／§9.2 G5／§14；Audit Checklist §2／§4／§5／§11／§15；Wireframes §0.2；Migration Contract §6（W-1 措辭）／§7；`PROJECT_RULES.md` §19.8 加註；BACKLOG §5.1.20 兩列更新＋§5.1.21；HANDOFF Safe Handoff。
- **驗證（實作組實測；單組）**：~~見 HANDOFF Safe Handoff（DEC-124）「tests」欄與 PR 描述。~~（HANDOFF 該段無「tests」欄，指標錯誤，改為就地記錄（2026-11-02 DEC-124 獨立稽核 PASS with fixes 後更新；有意識的更新，不是漏刪；決策者 AI 總管〔稽核修正／事實更新〕；原文刪除線保留））實作批：`tests/test_ui2_*.py`＋`test_c3_layering_guard`＋`test_zz_test_portability`＋`test_views_no_unverified_universal_claims` 361 passed；`streamlit==1.56.0` venv ui2 測試 313 passed；全 repo 序列 `-m "not slow"` 36261 passed／1 failed（`test_uim_market_page::test_loaded_hero_items_match_panel_rows`，main `57b361ab` 同樣失敗＝既有）。mutation：DEC-124 守衛 11 項＋Batch 1 既有 15 項全部轉紅後已還原。獨立稽核（第二組）：**PASS with fixes**（9 項 mutation 全紅；A／Risk Cap UNDETERMINABLE／DEC-074／075 歸類／O1 第五類皆同意）。修正批：見下一條。
- **稽核修正批（2026-11-02，同分支、test／docs＋UI2 契約一行）**：(a) 既有 CI 阻擋測試決定化——bisect（worktree 實跑）`6b814b0d` 過／`e5be97a6` 起敗、其間只動 `data_cache/` ⇒ 測試讀 live 快照的脆弱性；`tests/test_uim_market_page.py` 改以 `monkeypatch` 釘死 L3 方向歷史，L2 計算與頁面組裝照跑，原斷言保留並加嚴＋teeth（BACKLOG `TEST-UIM-MARKET-HERO-DIRECTION-PREEXISTING`）；(b) `⬜ 尚未核准／無法判定` 自 UI2 Not Evaluated 允許表移除＋守衛（`NUI2-NOT-APPROVED-LITERAL-REVIEW` 升 P2）；(c) Supersede Map／DEC-122 摘要加 DEC-124 指標、Freeze 措辭「不是資料語意態」、本節與 HANDOFF 過期句。驗證結果見 HANDOFF 現行 Safe Handoff「驗證」列。
- **限制（誠實揭露）**：(1) 守衛為原始碼／契約層級；capability marker 的 Preview-only 以**檔案允許清單**強制，**不是** runtime 斷言（cutover 前補：`NUI2-CAPABILITY-MARKER-CUTOVER-ZERO`）；(2) DEC-074／075 字樣與 `not_approved` 混合字樣歸類為單組判讀；(3) Aggregator O1 第五類 `undeterminable` 為 docs-only 契約修正，Aggregator 未實作；(4) Old UI／Legacy New UI 中 `⬜ 未評估／資料不足` 等字樣的語意歸類**未盤點、未修改**（範圍外）；(5) 全部 FAKE；未實機。
- **未碰（硬限制）**：`app.py`、`requirements.txt`、`src/ui/**`、`src/ui_v2/**`、`src/data`、`src/compute`、`shared` 既有非 ui2 檔；navigation 實作、real data wiring、Aggregator、Risk Cap runtime、Digest、OneBrain、LINE。
- **W-1**：頂部 navigation 維持 temporary implementation gap（**不是 W-1 amendment**；`NUI2-NAV-W1-FIDELITY`），下一個 presentation batch 修。

<!-- PROJECT_STATE_HISTORY_INDEX:BEGIN lines=916-928 archive=docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q2；只搬不改）**：原 L916–L928 已逐字搬至 `docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md`（分冊 L73–L85）。本處原為下列 1 節（標題逐字）：
  - 原 L916–L928 → [分冊 L73–L85](archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md#ps-hist-54)：## 54. New UI2 Batch 2（W-1 導覽保真／共用元件三軸呈現／Mobile-first 第一屏＋viewport 量測；2026-11-03；append-only；實作組單組、待總管複驗）
<!-- PROJECT_STATE_HISTORY_INDEX:END -->

## 55. 市場趨勢 Research Baseline 落盤＋中性命名永久規則（DEC-125，客戶 2026-11-03 (10) A 節；2026-11-03；append-only；文件組單組、待總管複驗）

- **依據**：客戶 (10) A1～A5（逐字見 `docs/DECISIONS.md` DEC-125）。基準 `origin/main`＝`e5f9a0d7`（=#1000 `a726b05e` 之後僅一個純資料 bot commit，`src/data/etf/etf_managers.json`；分支 `ccr-a0b4e085-ijdaio`）。
- **做了什麼（docs/governance only；0 production 變更）**：① 新增 `docs/vnext/MARKET_TREND_RESEARCH_BASELINE_2026-11-03.md`（台股 6 維度、國際 11 維度、定位、「不得自行」清單、Pending、現況盤點、與 Freeze §11 關係、A3 兩主軸規格）；② `PROJECT_RULES.md` 第 28 節（中性命名＋兩主軸＋Baseline 永久語意）；③ DEC-125（A 節逐字）；④ BACKLOG §5.1.23 `MKT-RB-*`；⑤ 本節與 HANDOFF Safe Handoff。
- **已存在且只 cross-reference（未建第二份）**：DEC-071、PROJECT_STATE §22、DEC-091(g)／092、Freeze §11、`DEC092-EPSPE-HIGH-GATE`、`VN1-MT-*`、`NSR-*`。
- **現況（FACT，單組）**：repo **沒有**任何已核准的台股趨勢／國際趨勢 validated deterministic contract（`tw_trend`／`intl_trend`＝`NOT_DEFINED`）；相鄰既有正式概念＝市場位階、指標危險度（16 燈）、Risk Cap、持股層 Rule ID 允許名單（皆非趨勢）。大盤 EPS／PE／forward EPS 資料源不存在。
- **A4 命名盤點（grep＋讀檔，未窮舉）**：使用者可見字串未發現老師／個人姓名；識別字層有 v19.174 去識別化遺留（22 個 `MJ_*` alias、`mj_*` 欄位、`*caisen*` 函式 alias、4 個 `tests/test_mj_*.py`、舊快取目錄常數）；**New UI2 範圍 0 命中**。皆只登記（`MKT-RB-NAMING-*`），未改 code。
- **未驗與限制**：文件組單組；盤點非窮舉；§1.1 三定位詞釋義、A3 與產業趨勢的關係、A4 適用範圍皆 INFERENCE，已列疑點待客戶確認（DEC-125 疑點；`MKT-RB-AXES-INDUSTRY-READING`／`MKT-RB-NAMING-SCOPE`／`MKT-RB-NAMING-EPONYM`）。
- **§27 檢查**：新 Rule＝`PROJECT_RULES.md` 第 28 節；新 Decision＝DEC-125；Audit finding／Backlog／Limitation＝BACKLOG §5.1.23 與上列；Migration debt＝無新增（命名債登記於 BACKLOG）；Acceptance item＝待總管複驗 A1～A4 對照。
- **未碰（硬限制）**：`src/`、`tests/`、`shared/`、`app.py`、`requirements.txt`、`tools/`、`scripts/`、`.github/`。

## 56. New UI2 Batch 3（📊 今日結論＋今日主要風險／🎯 雙模式＋搜尋＋查一檔 FAKE／👤 帳戶 skeleton；2026-11-03；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (10) B～F（2026-11-03；Sonnet 5.5＋Medium；最多 3 項；純 presentation）。基準 `origin/main`＝`e5f9a0d7`（#1000 `a726b05e` 之後僅純資料 bot commit；分支 `ccr-a0b4e085-ijdaio` 含 A 段 docs `f683e0d9`；cron 會推進 tip，以當下 `git fetch` 為準）。本批變更在工作樹，**commit／push／PR 由總管處理**（實作組未 commit）。**本批無新 DEC**（今日結論句型＝DEC-081 Q2-1 規則；主要風險退化句＝DEC-117 Q6 逐字；皆既有裁示）。
- **做了什麼（0 投資語意；未新增 Risk Cap 規則／數值／門檻／公式／probability；未動 Aggregator／Action Authority／Digest／OneBrain／LINE／real-data／production default）**：
  - **① 📊 市場**：`FirstScreenVM.conclusion`（今日結論，第一屏**首列**）與 `PageContext.main_risk`（今日主要風險，L1，**緊接第一屏四問之後**，同一個 `.ui2-m-l1` 容器內、⛔ 被卡片／L2／L3 插隊）。桌機（≥769px）以 CSS grid 把 ①市場目前狀態／Risk Cap／今日主要風險排成**三 tile**（Wireframes §2.2／DEC-117 Q1 桌機），手機同 DOM 順序堆疊。**今日結論**＝canonical 提供的 FAKE 示意句（`FAKE 示意結論：市場目前狀態 …；〈非 OK 指標逐一明寫〉；各項判斷並列、互不推導`）：各判斷獨立並列以「；」相接、缺值／Stale／Unavailable／未評估**明寫**、⛔「但／因此」、⛔ 方向與動作字樣；**VM 原樣帶出**，不由位階／指標推導（`market_vm`／`vm_common` 無任何結論生成碼）；冷啟動＝灰色 `⬜ 尚未載入`。**今日主要風險**：只放退化／護欄句（DEC-117 Q6 逐字，常數在 `shared/ui2_contract/text.py` `RISK_SENTENCE_*`／`RISK_NOTE_UNEVALUATED_NOT_SAFE`／`RISK_ERROR_FMT`，與 Legacy `_market_blocks.py` 原始碼逐字比對）：cold＝`⬜ 尚未載入，請按更新`（灰；不列風險項列）、missing＝`⬜ 無法判定（五桶資料皆不足）`（判定結果軸）、unavailable＝`🔴 來源目前不可用`＋`五桶風險摘要算不出來：…`（真錯誤才紅）、not_evaluated＝`⬜ 尚未評估`＋`未評估不等於安全`、loaded／stale＝capability `⬜ 尚未提供`（Preview：風險項尚未接線，**不產生任何風險項**）。
  - **② 🎯 標的**：`TargetVM`（`PageContext.target`）＋`PresentationSlice.active_mode`。**雙模式**（`市場精選｜即時查一檔`，`st.radio(key="ui2_target_mode")`＋`st.container(key="ui2_target_mode_box")`＋CSS 膠囊；只寫 `ui2_` 前綴 UI 狀態）：兩模式內容**都在 `context`**，切換只改 slice（`visible_card_ids`＝查一檔時 `()`、`active_mode`）→ 不同時完整展開（Presentation Slice ≠ Decision Context；測試證明 context 逐欄相等）。**搜尋框＋搜尋 CTA**＝disabled 示意（`role="searchbox" aria-disabled="true"`＋disabled CTA；⛔ `<input>`／`<form>`／real-data fetch；兩模式都外露；名稱搜尋＝capability `⬜ 尚未提供`＋「請輸入代碼」）。**fake ticker／fake result**：`FAKE-0001 FAKE 示意公司`＋Neutral chip；6 維 Snapshot（基本面／估值／籌碼＝`FAKE 占位`、趨勢／產業＝`⬜ 尚未定義`〔DEC-092 Q2 固定〕、市場環境排最後且 Neutral）；**加入觀察 CTA 恆 disabled**（`尚未提供：正式加入觀察流程僅舊 UI；Preview 不寫入…`，DEC-083）；session 隔離說明句。**W-4**：市場位階＋Risk Cap 為一行輕量 chip（置於查詢摘要之下、字級 .78rem＜摘要）；位階與市場頁同一份 FAKE market context（各場景同步）。**本頁不產生持股動作**（動作欄維持 capability，動作權威＝💼 持股）。
  - **③ 👤 我的**：`AccountVM`（`PageContext.account`）；`get_preview_page_vm(..., account=)`／`fake_canonical(..., account=)`（FAKE 連線事實維度；預設 `signed_in`＝Batch 2 內容不變）。**三態**：signed-out（Google 卡 `尚未登入`〔OK 事實值〕、Sheet／組合／觀察清單＝Missing `⬜ 資料未備`〔不適用〕、主 CTA `Google 登入`）、signed-in（主 CTA `切換 Sheet`；動作列 切換 Sheet／選組合／選觀察清單／Google 登出）、unavailable（Sheet＝Unavailable `🔴 來源目前不可用`＋「Sheet 讀取失敗（FAKE 示意）」、組合／觀察清單＝Missing `⬜ 資料未取得`、主 CTA `重新讀取`）。全部動作 CTA disabled；Preview 控制新增 selectbox `ui2_account`（僅 👤 我的頁有效）。**無** OAuth／Sheet／secrets／`src.data`（AST／import 守衛含 mutation）。
  - **量測腳本擴充**（`tests/ui2_viewport/measure_viewport.py`）：新增 6 條判定（`market_conclusion_in_first_screen`／`market_main_risk_follows_first_screen`／`target_mode_search_first_screen`／`target_mode_exclusive`／`target_w4_context_light`／`me_account_state_first_screen`），**門檻全部引用既有條文**（Freeze §0.1.6-3／-5、§16、Wireframes §2.1／§2.2／§3.1／§9／§1／§5.1，未自創 px）；🎯 每場景另量『即時查一檔』、👤 另量 signed-out／unavailable（每 viewport 32 態、共 64 態）。
- **量測結果（Chromium headless，390×844／1440×900；FAKE）**：Streamlit **1.59.2：64/64 通過**；Streamlit **1.56.0（`/tmp/v156` venv，floor）：64/64 通過**（`docs/vnext/newui2_batch3/viewport_measurements_streamlit156.json`；1.56 venv 的 `test_ui2_*`＋`test_c3_layering_guard` 615 passed）。手機底緣 y（px，跨全部場景範圍；可用高 791）：📊 市場 今日結論 268–293、① 322–365、Risk Cap 378–421、② 474–517、③ 543–588、④ 633–679、**今日主要風險 top 650–696／bottom 708–772**（皆在導覽上緣 791 之上、且緊接 ④ 之後）；🎯 標的 模式切換 bottom 223、搜尋列（＝④）bottom 284、① 398–423、W-4 context 434–464、② 505–536、③ 558–588；👤 我的 ① 248–272、② 300–339、③ 354–411、④ 444–502、帳戶動作列 bottom 566–654。桌機三 tile：①、Risk Cap、今日主要風險頂緣同為 y=238（差 0px）。
- **驗證（實作組實測；單組）**：新測試 `tests/test_ui2_batch3.py`（180 項；含 AppTest 整頁渲染順序／模式互斥／session 隔離、AST 守衛含注入、判定器 21 條 teeth）；既有 `tests/test_ui2_*.py`（guards／batch2／registration）仍綠（`_all_fields` 掃描範圍只增不減；batch2 slow 測試的預期態數隨覆蓋擴大改為 `2×(4×6＋6＋2)`）。**mutation 12 項實測轉紅後還原**：結論句改「，但」、今日主要風險被卡片插隊、兩模式同時展開、標的頁寫非 `ui2_` session key、我的頁 import `oauth_state`、signed-out Sheet 掛判定結果軸、加入觀察 CTA 變 enabled、冷啟動主要風險畫成紅色、退化句改寫、模式切換改變 context、VM 夾帶方向字樣、搜尋框變可互動。
- **限制（誠實揭露）**：(1) 量測全在 **FAKE 字串**，真資料長度未測（手機今日主要風險 bottom 最大 772 vs 導覽上緣 791，餘裕僅 19px；真資料只會更長 → `NUI2-VIEWPORT-FAKE-ONLY`）；(2) 只測 Chromium headless 兩個 viewport；Safari／Firefox／真機／螢幕閱讀器未測；(3) 搜尋＝disabled 示意，**W-3 送出即切換、名稱搜尋、真查詢全未做**；(4) 今日結論是 **FAKE 示意句，非逐字結論句**（DEC-081 Q2-1 只有句型規則；真結論句＝`NUI2-CONCLUSION-REAL-FEED`）；(5) 冷啟動「主要風險不出列」為單組解讀（`NUI2-COLD-MAIN-RISK-READING`）；(6) 「尚未登入」歸類與 W-4／紅色兩義交會為單組判讀（`NUI2-ME-SIGNEDOUT-CLASSIFICATION-REVIEW`、`NUI2-TARGET-W4-RED-ON-UNAVAILABLE`）；(7) 桌機三 tile 依賴 `display:contents`＋`grid-row` 明確放置（`NUI2-MARKET-DESKTOP-3TILE-CSS`）；(8) 截圖手機全部態＋桌機 cold／loaded；其餘桌機態以 JSON 為準；(9) 本 repo 無 `SESSION_LOG` 檔（grep／find 0 命中），session 紀錄以本節＋HANDOFF 為準。
- **未碰（硬限制；`git diff --name-only HEAD -- app.py requirements.txt tools scripts .github src/ui src/ui_v2 src/data src/compute` 與 `shared`（非 `ui2_contract`）實查為空）**：同 Batch 2；另 System Action Aggregator runtime／Action Authority／Decision Digest／OneBrain／LINE／real-data canonical wiring／新 source／新 threshold／新公式／新 probability。
- **§27 檢查**：新 Rule＝無（既有 DEC-124 三軸、DEC-117 Q6、DEC-081 Q2-1、PROJECT_RULES §28 原樣適用）；新 Decision＝無；Audit finding／Limitation／Backlog／Migration debt／Acceptance item 已寫入 BACKLOG §5.1.24、Audit Checklist §17、Migration Contract §9、Wireframes §10、HANDOFF Safe Handoff。

- **§56 補（獨立 QA 修正；append）**：F3 查一檔 cold 只畫搜尋框＋灰色說明（`LookupResultVM.queried`）；F2 W-4 context／『市場環境』改 Neutral＋文字狀態（只放寬此二處；`NUI2-TARGET-W4-RED-ON-UNAVAILABLE` 更新）；F4 預設道補「市場 L1 之前無 L2／L3」AppTest（mutation 轉紅）；F5 三個自證式 teeth 測試改真實 mutation／刪除；新登記 `NUI2-MARKET-REFRESH-CTA-ORDER`（Batch 2 起的未登記偏離）、`NUI2-ME-DUP-LOGIN-BUTTON`、`NUI2-Q21-RISKCAP-MISSING-WORDING`、`NUI2-MAIN-RISK-NAV-MARGIN`（BACKLOG §5.1.24 末）。證據 JSON／截圖已重量（1.59.2 與 1.56.0）。

- **索引（DEC-126／PROJECT_RULES 第 29 節；append）**：客戶 2026-11-03 新增「多元解法與最小成本決策規則」，逐字見 `docs/DECISIONS.md` DEC-126、規則本體 `PROJECT_RULES.md` 第 29 節（第 9 點為併用 `CLAUDE.md` v3 §03、第 11／12 點為 AI 總管增添，均非客戶原文，已於該處明註）。

## 57. New UI2 小型 presentation correction（DEC-127，客戶 2026-11-03「#1001 整體接受」；2026-11-03；append-only；實作組單組、待總管複驗）

- **依據**：客戶 2026-11-03 裁示三項（逐字 `docs/DECISIONS.md` DEC-127）。純 presentation；基準 `origin/main`＝`bd41ee11`（#1001）。
- **做了什麼（0 投資語意；未碰 System Action Aggregator／Risk Cap runtime／Action Authority／Decision Digest／OneBrain／real-data／OAuth／Sheet／LINE／production default／新公式／門檻／source）**：
  - **① 📊 市場更新 CTA 順序**：`NUI2-MARKET-REFRESH-CTA-ORDER` 依 frozen contract（Wireframes §2.1／§2.2、DEC-117 Q5）修正＝頁首→🚀 更新今日戰情 CTA→今日結論→核心狀態…；`first_screen_html(cta_first=True)`（僅市場頁）＋桌機 grid 列序。四問內容／VM 欄位／字樣未變（測試鎖定）；其他頁不動。客戶明示不開 Decision Gate、不改 Wireframes 條文。
  - **② W-4**：逐點對照客戶列 8 點，**現行實作符合**（輕量一行 chip／Neutral／字級 .78rem < 摘要 1rem 與 6 維格 .85rem／在搜尋與摘要之下／『市場環境』不排第一格／無方向與買賣字樣／與市場頁位階同源）；補 2 條測試（字級、整頁 DOM 順序），其餘引既有測試；`NUI2-TARGET-W4-RED-ON-UNAVAILABLE` 收斂為 accepted／implemented。valuation／基本面區塊落地後須重驗（`NUI2-W4-RECHECK-WHEN-RESEARCH-BLOCKS-LAND`）。
  - **③ 手機底部導覽餘裕**：比較 A／B／C（BACKLOG §5.1.24 DEC-127 補）→ 採 **B（主解：CTA 列原因與按鈕同列、不重複「④」標籤；不縮字、不刪資訊）＋A（保險層：`@supports` safe-area 內容保留量）**，不採 C。stale／unavailable 餘裕 2.5px→42px；壓力態（L1 文字 1.5×，頁內 DOM 注入）六場景可達。
  - **量測腳本**：新增 `market_cta_before_conclusion`／`market_main_risk_nav_margin`／`market_stress_reachable` 三條判定；修正頁底內容量測（`scroll_end_bottom`）。總態數 64→70。
- **量測結果（Chromium headless，390×844／1440×900；FAKE）**：Streamlit **1.59.2：70/70**；**1.56.0（`/tmp/v156` venv）：70/70**；證據 `docs/vnext/newui2_batch3b/`（JSON 兩份＋手機全部態與桌機 cold／loaded 截圖；手機六場景已逐張目視：CTA 在頁首下、結論之上，風險區塊與下一卡片頂緣皆在導覽之上）。
- **驗證（實作組實測；單組）**：新增測試於 `tests/test_ui2_batch3.py` §9（`tests/test_ui2_batch3.py` 222 passed（重跑確認；含讀證據 JSON 的測試））；**mutation 6 項實測轉紅後還原**：M1 CTA 移回最後（單元 12 紅；真瀏覽器 `market_cta_before_conclusion`／`market_main_risk_nav_margin`／`market_stress_reachable` 手機 12 態紅）、M2 桌機 grid 列序（1 紅）、M3 拿掉 safe-area 保留量（1 紅）、M4 原因句改回按鈕下方（1 紅）、M5 關掉餘裕判定（1 紅）、M6 頁底保留量 5rem→3rem（真瀏覽器 `content_not_covered_by_nav` 31 態＋`market_stress_reachable` 6 態紅）。全量序列結果見回報（⚠️ 以總管複驗為準）。
- **限制（誠實揭露）**：(1) iOS safe-area 未驗（Chromium env＝0；`NUI2-NAV-SAFEAREA-IOS-UNVERIFIED`）；(2) Safari／Firefox／真機／螢幕閱讀器未測（`NUI2-VIEWPORT-NON-CHROMIUM-UNVERIFIED`）；(3) 量測全在 FAKE 字串，壓力態＝1.5× 文字注入、非真資料（`NUI2-VIEWPORT-FAKE-ONLY`、`NUI2-NAV-MARGIN-CRITERION-INTERNAL`）；(4)『≥1 行行高』餘裕門檻為 AI 總管內部判準、客戶可推翻；(5) 桌機 CTA 與線框『頁首列右側』非逐像素等同（`NUI2-MARKET-CTA-DESKTOP-PLACEMENT`）。
- **未碰（硬限制；`git diff --name-only origin/main -- app.py requirements.txt tools scripts .github src/ui src/ui_v2 src/data src/compute` 與 `shared`（非 `ui2_contract`）實查為空）**：同 §54／§56。
- **§27 檢查**：新 Decision＝DEC-127（客戶原文逐字）；新 Rule＝無；Audit finding／Limitation／Backlog／Acceptance item 已寫入 BACKLOG §5.1.24 DEC-127 補、Audit Checklist §18、Wireframes §10 補註、HANDOFF。

## 58. New UI2 NUI2-REAL-FEED A 批（A1 Canonical Read Path Mapping／A2 最小 read-only real feed adapter／A3 real-data shadow acceptance；客戶 2026-11-03 (11)；2026-11-03；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (11)（Opus 5.5＋High；§29 比較後選 A；≤3 項）。基準 `origin/main`＝`ade8181e`（#1002）。**本批無新 DEC**；內部判準（可推翻）登記 BACKLOG §5.1.25。
- **一句話**：Real-data Preview（唯讀、非 production default、預設關）**只接 2 個事實**——台股加權指數（📊 卡）、市場位階（📊 現在狀態＋L2 位階說明、🎯 W-4、🎯 市場環境，同一次呼叫）；**其餘欄位一律 ⬜＋原因**。⛔ 描述為「真資料已接上」。
- **做了什麼（分層）**：
  - **L0** `shared/ui2_contract`：`REAL_PREVIEW_BANNER_TEXT`「Real-data Preview（非正式 production default）」＋`REAL_PREVIEW_BANNER_NOTE`；`SCENARIO_REAL="real"`（**不在** `SCENARIO_IDS`）、`FEED_FAKE／FEED_REAL／FEED_IDS`。
  - **L3** `src/services/ui2/real_feed.py`（**唯一 I/O 檔**；只呼叫 `market_twii_view_service.get_twii_trend_view(1)` 與 `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`；例外接住→錯誤字串；回 frozen `RealFeedSnapshot`）；`real_canonical.py`（純函式：snapshot→canonical dict→**既有** `build_market_page_vm／build_skeleton_page_vm`）；`vm_common.build_page_vm` 加 banner 分派（FAKE／real 兩軸混用即 raise）。
  - **L5** 殼 `src/ui2/shell/app.py`：Preview 控制加「資料來源（feed）」`ui2_feed`（預設 FAKE；Real 時場景／帳戶 widget disabled）；Real 模式每 rerun 讀一次、banner 換 Real 標示。views／components **未改**。
  - **測試／工具**：`tests/test_ui2_real_feed.py`（新）；`tests/test_ui2_guards.py`（G2F 新增、G9 補洞、capability allowlist 加 `real_canonical.py`、G2 掃描範圍扣具名 `FEED_FILES`）；`tests/ui2_viewport/measure_viewport.py`（`--feed real`、新判定 `real_feed_banner_on_top`）；`tests/test_batch_z66b.py`（`require_valid_risk_cap=True` 呼叫點清單加 `src/services/ui2/real_feed.py`，舊集合刪除線保留）。
  - **文件**：`docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md`（A1 正式 mapping）；Migration Contract §10；Audit Checklist §19；BACKLOG §5.1.25＋`NUI2-REAL-FEED` 列更新；HANDOFF Safe Handoff。
- **兩組盤點差異（裁定見 mapping §1）**：位階入口採組 A（`get_macro_regime`＝全站唯一橋樑、只 `.get`；組 B 的 `get_macro_state(warroom)` 需殼讀非 `ui2_` key 或 feed 端寫死 `warroom=None`）；A3 不採組 B 的 `run_headless_refresh`（需網路）；利差實查 DangerSpec 18 key 無 spread（採組 A ⬜＋SG）。
- **語意映射**：見 mapping §5（`is_stale=None`→Stale `⚠ 可能已過期`＝AI 總管內部判準、可推翻；位階 as_of＝`⬜ 資料日未提供`、⛔ `cl_ts`；source＝「規則分支 id：…（非資料來源）」；未知 source→raise）。手機第一屏放不下 L0 完整位階說明 → L1 短句＋L2「位階說明」逐字（Freeze §16.5 縮字句；`NUI2-REALFEED-REGIME-L1-BRIEF`）。
- **驗證（實作組實測；單組）**：
  - `tests/test_ui2_real_feed.py` 62 passed；UI2 相關組（`test_ui2_*`＋`test_c3_layering_guard`＋`test_batch_z66b`＋`test_zz_test_portability`）848 passed（1.59.2）；UI2 組於 Streamlit 1.56.0（`/tmp/v156`）776 passed。**全量序列** `python -m pytest tests -q -p no:cacheprovider -m "not slow"`：**36700 passed, 46 skipped, 0 failed**（第二次；第一次 2 failed 已修：`test_batch_z66b` 的 `require_valid_risk_cap=True` 呼叫點清單〔加 real_feed，刪除線保留〕、`test_zz_test_portability` 禁測試呼叫外部 `git`〔改純 Python 工作樹指紋〕）；slow 真瀏覽器 `tests/test_ui2_batch2.py::test_real_browser_viewport_acceptance`（FAKE 70 態）1 passed。
  - **mutation 13 項實測轉紅後還原**：M1 stale 當 OK、M2 `is_stale=None` 當 OK、M3a feed 讀位階兩次、M3b 🎯 位階不吃同一 snapshot、M4 feed 寫 session（G2F＋runtime 紀錄器）、M5 feed import `refresh_macro_now`（G2F）、M6 real source 加 FAKE 前綴、M7 Risk Cap 被接值、M8 非 strict（壞檔被吞成未評估）、M9 殼整包傳 `session_state`（G9）、M10 位階 L0 說明被改寫、M11 未知 source 默默落態、M12 feed 寫檔（`data_cache/` 探針；工作樹指紋測試轉紅）。
  - **no-write proof**：(1) AST G2F（24 注入）＋G9 補洞（5 注入）；(2) AppTest runtime `SessionStateProxy` 寫入紀錄器：Real 模式四頁＋查一檔期間 0 次寫入（首跑只寫明列 `ui2_page／ui2_scenario／ui2_account／ui2_feed`；紀錄器確實掛上由同測試斷言）；(3) 工作樹全檔（含 git 忽略檔；純 Python）mtime＋size，及 `data_cache/**`、`macro_state.json`、`risk_cap_state.json` sha256＋mtime 前後相同（另人工 `git status --porcelain` 前後比對相同）；(4) socket connect guard＝0 次連線且真讀本地 parquet 成功。
  - **viewport（Real 模式，Chromium headless）**：390×844／1440×900 × 四頁＋🎯 查一檔＋手機市場壓力態＝11 態；**Streamlit 1.59.2：11/11；1.56.0（`/tmp/v156`）：11/11**；證據 `docs/vnext/newui2_realfeed/`；手機五張已逐張目視（banner 在頁首、CTA 在今日結論之前、Risk Cap ⬜ 無法判定、動作欄待 Aggregator、💼／👤 無假帳戶狀態）。
- **限制（誠實揭露）**：(1) **shadow ≠ C5**（Migration Contract §10）；(2) Preview Cloud 的 CWD／狀態檔存在性未驗（`NUI2-PREVIEW-CLOUD-STATE-FILES`）；(3) 錯誤字串未經 `scrub_secrets`（UI2 守衛擋識別字 `secrets`；`NUI2-REALFEED-ERROR-SCRUB`）；(4) 手機市場頁主要風險後餘裕 27.8px（門檻 24px＝AI 總管內部判準）；(5) Real 模式 🎯 查一檔未查詢 ⇒ 6 維 Snapshot 不渲染（位階一致性於 VM 層驗）；(6) 真值為量測日快照（每日 cron 會變）；(7) iOS／Safari／Firefox／真機未測；(8) 兩份盤點與本整合皆單組、計數非 AST 窮舉。
- **未碰（硬限制）**：`git diff --name-only origin/main -- app.py requirements.txt tools scripts .github src/ui src/ui_v2 src/data src/compute` 實查為空；`shared` 只動 `ui2_contract`；`src/services` 只動 `ui2/`。未碰 Aggregator／Risk Cap 規則與數值／Action Authority／Digest／OneBrain／LINE／OAuth／Sheet／production default／新公式／門檻／source。
- **§27 檢查**：新 Decision＝無；新 Rule＝無（守衛擴充屬測試）；Audit finding／Limitation／Backlog／Migration debt／Acceptance item 已寫入 mapping、BACKLOG §5.1.25、Migration Contract §10、Audit Checklist §19、HANDOFF。
- 📌 **兩組獨立 QA 修正補記（2026-11-03；append；上文一字未改；原 commit `70c4969b` 已 push 至遠端分支、待 PR；兩組皆無 P0）**：
  - **必修**：① 白名單不變量測試（7 台股 × 6 位階注入組合＋sandbox；只有 5 個已接落點與明列契約固定欄可帶 value／source／as_of／資料態）＋VIX 捏造 mutation；② 錯誤字串不上畫面（只型別名＋固定句；upstream_error 固定句；原文只 log；`token=SECRET` 植入測試）——`NUI2-REALFEED-ERROR-SCRUB` closed；③ G2F 精確 import 白名單＋反射／pandas／json／open／時鐘禁令＋G2／G2F／G9 相對 import 違規；④ G9 `session_state` 用法白名單；⑤ mapping「零網路」更正為「feed 呼叫期 0 連線；import 期既有 eager 鏈可連 proxy（FAKE 亦同、本批前即存在）」。
  - **P3**：🎯 指引改「說明見 📊 市場頁『為什麼（L2）』」；L0 位階說明後接連接句（L0 原文未改）、移除二次抄寫；**契約違反改為讀取期隔離**（該欄紅色 Unavailable＋log、另一事實照常；純函式仍 raise；可推翻，理由 mapping §11-8）；Real 模式 expander「Preview 控制（資料來源）」、帳戶 widget 標籤無 fake 字樣；SG-02 補證據、SG-14 新公式／新 threshold；Reuse Matrix S6／S23 回填；BACKLOG 新增 `NUI2-TWII-CORRUPT-AS-MISSING`／`NUI2-REALFEED-FINGERPRINT-SCOPE`／`NUI2-REALFEED-WARROOM-CONTRACT-INTEGRATION`／`NUI2-REALFEED-CONTRACT-ISOLATION-RULE`。
  - **QA 修正批 mutation 13 項實測轉紅後還原**：N1 VIX 捏造 18.20＋as_of＋source、N2 VIX 補 0.00、N3 畫面放例外訊息原文、N4 upstream_error 原文上畫面、N5 契約違反不在讀取期驗（不隔離）、N6 🎯 指引改回本頁、N7 G2F 放寬回模組前綴、N8 G2F 不查相對 import、N9 G2F 拿掉反射禁令、N10 G9 拿掉 session_state 用法白名單、N11 G2 不查相對 import、N12 Real 模式 expander 顯示 fake、N13 拿掉 L0 後的連接句。（上一輪 M1～M12 於 `70c4969b` 實測；本批未重跑該組，部分 mutation 字串因程式改動已不適用。）
  - **viewport 重量（Real 模式）**：1.59.2 與 1.56.0 各 **11/11**；手機市場頁主要風險後餘裕仍 27.8px；手機截圖已重看（🎯／📊）。
  - **QA 修正批驗證（實作組實測；單組）**：`tests/test_ui2_real_feed.py`＋`test_ui2_guards.py`＋`test_ui2_batch2/3`＋`test_ui2_registration_and_boot`＋`test_c3_layering_guard`＋`test_batch_z66b` 937 passed（1.59.2）；UI2 組於 1.56.0 872 passed；**全量序列** `python -m pytest tests -q -p no:cacheprovider -m "not slow"`：**36796 passed, 46 skipped, 0 failed**；slow 真瀏覽器 `test_ui2_batch2::test_real_browser_viewport_acceptance` 1 passed；限制區域 `git diff --name-only origin/main -- app.py requirements.txt tools scripts .github src/ui src/ui_v2 src/data src/compute` 為空。
- 📌 **獨立複驗（`756ed846`，無 P0／P1）最後一輪補記（2026-11-03；append）**：P2-1（`is_stale` 身分比較；`ok`＋`failed` 矛盾＝契約違反）、P2-3（G2／G2F／G9 通用禁令：dunder 屬性、`importlib`／`__import__`／`exec`／`eval`；G2 時鐘與 pandas 讀寫屬性；G2F `real_canonical` 具名白名單；G9 禁 `streamlit.runtime*`；既有 UI2 檔 0 誤傷）、P3-2（白名單不變量改 VM 位置路徑＋原因句數字樣式）、P3-4（`RealFeedSnapshot.of()` 錯誤代碼降級；`_type_of_service_error` 正規式＋長度上限）。依 PROJECT_RULES §29 不再擴充靜態守衛：**AST 守衛＝defense-in-depth、非窮舉；主要 no-write 證明＝runtime session 紀錄器＋socket guard＋檔案指紋**；已知限制 `NUI2-GUARD-STATIC-LIMITS`。
  - **mutation 9 項實測轉紅後還原**：P1 `is_stale` 改回 `in` 比較、P2 拿掉 ok＋failed 檢查、P3 G2 拿掉通用禁令、P4 G2F `real_canonical` 改回任意名、P5 G9 不禁 `streamlit.runtime`、P6 白名單改回以 label 判斷、P7 拿掉原因句數字樣式、P8 feed 不經 `of()`、P9 service 錯誤型別不設上限。
  - **驗證（實作組；單組）**：UI2 組（`test_ui2_*`＋c3＋z66b）958 passed；**全量序列 not slow：36817 passed, 46 skipped, 0 failed**；slow 真瀏覽器 1 passed；Real 模式 viewport（1.59.2）11/11（沙箱真資料路徑畫面未變，證據檔未更新）；限制區域 diff 為空。

## 59. Presentation Compression ≠ Information Loss（DEC-128）落盤＋Active Rule Supersede Cleanup（客戶 2026-11-03 (13)；2026-11-03；append-only；實作組單組、待總管複驗）

- **依據**：客戶 2026-11-03 指示 (13)（Sonnet 5.5＋Medium；≤3 項；本批以 governance／contract cleanup 為主）。基準 `origin/main`＝`74435cab`（#1003）。逐字見 `docs/DECISIONS.md` DEC-128。
- **一句話**：New UI2 四頁 Human UI 不再顯示完整 L2／L3（為什麼、指標明細、原始資料、provenance、工程／provider 診斷、raw JSON、debug、大量 Missing 清單）；**從 UI 移除 ≠ 刪資料**；完整診斷集中 👤 我的·資料健康度（三層）；Human UI ViewModel ≠ Decision Digest（OneBrain）Context 雙 projection；**現行唯一有效 presentation contract＝`docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`**。
- **做了什麼（docs＋測試清理；0 行 `src/`／`shared/`／`app.py` 變更；DEC-129 後 5 處「保護已失效 presentation」的舊斷言已改寫，見 BACKLOG §5.1.26）**：
  - **新 DEC-128**（客戶原文逐字 fence；取代範圍表 S21～S35；不被取代清單；PROVISIONAL (a)～(d)〔📌 (a)(b)(c) 已由 DEC-130 升為正式 Active，見 §60〕）；DEC-072／076／081／091／105／109／111／112／117／122 條頭加 `📌 SUPERSEDED IN PART BY DEC-128`（原文不動）。
  - **`PROJECT_RULES.md` 新第 30 節**（8 點）；§24.2「第一屏三層答不出＝FAIL」加刪除線＋📌；§19.2、§24.1 加 📌。
  - **新 Active Contract 單一入口**`docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`（四頁優先順序、各頁應有／不應有、Chart-first＋SPEC、資料健康度三層與禁曝險清單、Preview 控制去向、OneBrain Outlook、projection 邊界與保留清單、取代對照表 §10）。
  - **Supersede Cleanup**：Freeze、Wireframes、Presentation Contract、Capability Map、Architecture Gate、Migration／Cutover、Audit Checklist、Reuse Matrix、Real Feed Mapping、Visual Fidelity Gate、ME Page Draft、Digest Contract、OneBrain Architecture 加 `⛔ SUPERSEDED / HISTORICAL — NOT ACTIVE（DEC-128…）`（部分）橫幅或 📌 補註；Supersede Map 續編 S21～S35；BACKLOG 舊 🩺 資料中心列加 📌。**舊文一字未刪。**
  - **測試**：新增 `tests/test_ui2_active_contract_docs.py`（docs-consistency：Active Contract／DEC-128／橫幅／舊 DEC 原句未被改／待更新測試登記常數；**mutation 11 項實測轉紅後還原**〔M1 Wireframes 橫幅字樣拿掉、M2 Freeze 橫幅不指向 Active Contract、M3 DEC-128 fence 關鍵句被改、M4 PROVISIONAL 標示拿掉、M5 舊 DEC-091 Level 3 原句被改、M6 DEC-117 條頭 📌 拿掉、M7 Active Contract 頂端宣告拿掉、M8 PROJECT_RULES §24.2 刪除線拿掉、M9 登記的待改測試被改名、M10 登記測試被 xfail、M11 Supersede Map S25 列拿掉〕）。
  - **後續**：BACKLOG §5.1.26（UI correction P1～P6、T-new-1～6、測試改動清單、資料健康度欄位表、PROVISIONAL 待確認、未驗）；HANDOFF 新 Safe Handoff；Audit Checklist §20（未自勾）。
- **現況（誠實揭露）**：📌 **2026-11-03 P1 已修其中三項（工程字樣、題號鷹架、Preview 控制 expander；見 §61）；舊 L2／L3 expander 仍在（P3）**。〔原文：**現行 Preview 仍有舊 L2／L3 expander、工程字樣、題號鷹架、Preview 控制 expander**〕——那是 implementation deviation，由 UI correction 批修；既有測試仍斷言舊 presentation（清單在測試檔 `PENDING_UI_CORRECTION_TESTS`），**不得用 xfail／skip 隱藏**。
- ~~**PROVISIONAL（AI 總管暫定、客戶可推翻）**：(a) 資料健康度 Level 1 符號 ✅◷◇⛔⬜ 為面內別名、不新增第 6 態、不改全站字樣；(b) 稽核面保留在 👤 等灰色地帶；(c) Preview 控制 `?ui2_dev=1`。~~ 📌 **已由客戶 2026-11-03 (15)／DEC-130 升為正式 Active**（見 §60）；(a) 為有條件同意（Data State 五態與 Capability 兩軸分離）。
- **限制**：取代範圍「只有 S21～S35」與 Active Contract 皆單組撰寫、**未經第二組獨立稽核**（`NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT`）；兩份 Gap Audit 皆單組、非窮舉；未驗 FAKE 非 loaded 場景、Safari／iOS／Cloud。
- **未碰（硬限制）**：Decision Digest schema、Risk Cap、System Action semantics、新資料 contract／source／公式／threshold、OneBrain／Digest runtime、real-data 擴大、production default、Old UI／Legacy New UI。`git diff --name-only origin/main` 只含 `docs/`、`PROJECT_RULES.md`、`tests/test_ui2_active_contract_docs.py`。
- **§27 檢查**：新 Decision＝DEC-128；新 Rule＝PROJECT_RULES 第 30 節；Audit finding／Limitation／Backlog／Migration debt／Acceptance item 已寫入 BACKLOG §5.1.26、Active Contract §9～§11、Audit Checklist §20、本節、HANDOFF。
- **📌 DEC-129 追加（客戶 (14)，同批；優先於 (13) 衝突處）**：①桌機左側 Navigation Rail 加 compact Account Area（Login／Auth Status；`⬜ 尚未登入`／`✅ 已登入`；不算第五頁；手機仍四格；狀態須來自正式 auth contract——目前**沒有**，`ui2_account` 只是開發面 FAKE）；②Active interpretation 11 點置於 Active Contract 開頭；③tests／guards 清理：5 個舊斷言改寫（不強制舊 presentation）、新增 `tests/test_ui2_contract_teeth_pending.py`（7 個 strict xfail teeth＋4 個現綠 teeth）；mutation：strict 翻紅 T_new_5／6／7 實測；docs 一致性測試另有 11＋項 mutation。「OneBrain 只能讀 UI slice」字面實查 0 命中（Freeze 現行寫法本就是「只讀完整 Digest」）。**未碰** auth 架構本體／Digest schema／Risk Cap／System Action／新資料 contract／source／公式／threshold。
- **📌 獨立稽核（`ca6209c8`，無 P0／P1）後增補（P2／P3 已修；仍 docs＋tests、src 零變更）**：Architecture Gate G3「context＝將來 Digest」更正（S38）；Visual Fidelity Gate A8／V11（S39）；Presentation Contract §12.2／§12.3／§9 判準 (a)（S40）；DEC-123 A-3／Gate §6.1／`NUI2-COMPONENT-GAP`「expander 層級」（S41）；DEC-092／108／101 「收合到查看依據」通則（S42，條頭 📌）；Wireframes W-1 桌機 4 項／W-6 下沉 L2、Freeze §5.1／§5.3「留 L2」（S43）；Legacy 時代再 5 份加橫幅（S44）；PROJECT_RULES §24.1 blueprint HTML 補註；HANDOFF REAL-FEED A 段標「歷史快照」；Active Contract 的 Level 預設展開／收合與「Level 3 只准遮罩後診斷代碼」標 PROVISIONAL；S32 與 PROVISIONAL (b)①〔📌 現已 Active，DEC-130〕的張力用語消除（📊🎯💼 整頁 0 個完整 evidence expander，👤 稽核面為明列例外）；`NUI2-COMMENT-DOCSTRING-SYNC` 登記 src 過時註解（待 UI 批改）；batch3 測試改名。**新牙**：strict xfail 逐 decorator AST 驗證（strict=True＋reason 含 DEC-128）、DEC-128／129 fence 整段 sha256 釘住、章節橫幅逐節配對；mutation 6 項＋既有 16 項實測轉紅。DEC-128 §七 為增補取代範圍（S38～S44）。


## 60. DEC-130：客戶覆核 PROVISIONAL (a)(b)(c) 升為正式 Active（客戶 2026-11-03 (15)；2026-11-03；append-only；實作組單組、待總管複驗）

- **做了什麼（docs＋tests；`src/`、`shared/`、`app.py` 零變更）**：新 **DEC-130**（客戶 (15) 逐字 fence、sha256 釘住）；DEC-128 §四 加 📌；Active Contract §5 改寫為**兩軸分離**（新 §5.1：Data State 五態 OK／Missing／Stale／Unavailable／Not Evaluated ↔ Capability／Implementation Availability；`✅→OK`、`◷→Stale`、`◇→Missing`、`⛔→Unavailable`；`⬜ 尚未接線` **不是 Data State**；Not Evaluated 另以既有字樣呈現、不併入 `⬜`；同列拆 `狀態(Data State)`／`接線(Capability)` 兩欄）；§3.2／§3.4／§6 補 (b)(c) 客戶新增限制（含「`ui2_dev` 不得與 auth state 混用、不能當登入證據」）；BACKLOG（批次表 P6 加「兩軸欄位分離」驗收條件、結案 `NUI2-DATA-HEALTH-SYMBOLS-CONFIRM`／`NUI2-AUDIT-SURFACE-CONFIRM`、T-new-8／9）／HANDOFF／Audit Checklist §21／PROJECT_RULES §30／Wireframes・Freeze・Architecture Gate・Supersede Map 橫幅同步（舊字加刪除線＋📌）。
- **新守衛**：`tests/test_ui2_guards.py` `check_axis_separation`（FieldState 恰五態且名稱釘住、CapabilityState 與 FieldState/JudgementState 無共用成員、AST 擋 `FieldState.<第六態>`／capability 標記進 Data State 欄／FieldState 進 capability 欄／Data State 欄含「尚未接線／尚未提供」字樣）、`check_ui2_dev_not_auth`（同函式共現＋簡單污染傳播＋模組層）——皆 defense-in-depth（AST 不窮舉）；`tests/test_ui2_active_contract_docs.py` DEC-130 docs 守衛與 fence sha256；`tests/test_ui2_contract_teeth_pending.py` 新 `T_new_8`（P6）／`T_new_9`（P1）strict xfail。**mutation 實測轉紅後還原**：docs 11 項（fence 被改、cap 列拿掉「不是 Data State」、◷ 改映 Missing、PROVISIONAL (a) 復活、ui2_dev 登入證據句拿掉、DEC-128 📌 拿掉、尚未接線填進 Data State 欄、P6 兩軸驗收條件拿掉、CONFIRM 項重開、§30 拆欄句拿掉、`_xfail130` 去 strict）；守衛 4 項真碼注入（FieldState 加第六員、`FieldVM(MISSING, TEXT_NOT_PROVIDED)`、`FieldState.NOT_PROVIDED`、capability 當 state、app_ui2／shell 注入 `ui2_dev→account`）＋5 項削弱檢查器（拿掉規則 4／第六態／讀取函式污染／函式陳述式／模組層檢查 → teeth 全轉紅；僅「同函式共現」被陳述式層冗餘涵蓋、移除它不轉紅）；`T_new_8`／`T_new_9` 以注入對應 UI 實作各實測 XPASS(strict) 轉紅。
- **殘留 PROVISIONAL**：(a)(b)(c)＝**0**。仍有「撰寫組暫定」（非 (a)(b)(c)、客戶 (15) 未涵蓋）：Level 1／2 預設展開或收合、Level 3 遮罩嚴於客戶原文、`⛔` 顏色、🎯 跨季趨勢是否保留（Active Contract §11）。
- **限制**：單組撰寫、未經第二組獨立驗證；`NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT` 仍 open（客戶：後續補、不阻擋）；T_new_8 DOM 標記名暫擬；`ui2_dev` AppTest 於 Streamlit 1.56 floor 未驗（1.59.2 已驗）；src 過時註解仍待 `NUI2-COMMENT-DOCSTRING-SYNC`。
- **未碰（硬限制）**：auth／OAuth 架構、Decision Digest schema、Risk Cap、System Action、新資料 contract／source／公式／threshold、production default、Old UI／Legacy New UI。
- **§27 檢查**：新 Decision＝DEC-130；新 Rule＝無（併入 §30 條文）；Audit finding／Limitation／Backlog／Acceptance item 已寫入 BACKLOG §5.1.26 補記、Active Contract §5.1／§11、Audit Checklist §21、本節、HANDOFF。

## 61. New UI2 UI Correction P1（Preview 控制 → `?ui2_dev=1`／去工程字樣與題號／標題與過時註解同步；客戶 2026-11-03 (16)；2026-11-03；append-only；實作組單組、待總管複驗）

- **做了什麼**：① Preview／FAKE／Real／帳戶場景控制只在 `?ui2_dev=1` 以虛線框「🧪 開發／測試工具（非產品內容）」獨立區塊顯示（頁內容之後、導覽之前；不是 expander／sidebar／導覽項；不佔桌機左導覽）；預設道 0 控制、預設值＝FAKE／cold（`DEFAULT_SCENARIO`）／帳戶 signed_in；`ui2_` 前綴不變；頂部標示單行（FAKE＝`示意資料（FAKE）`＋`非真實行情、持股或建議`；Real＝客戶要求的 `Real-data Preview（非正式 production default）`，手機不附說明以維持單行）；UI2 CSS 隱藏 Streamlit Deploy／⋮。② 四頁使用者畫面：工程術語（Preview／尚未接線／PORT／Gate／Stage／Aggregator／session／路徑 C／OAuth／nonce／契約／DEC-／macro_state／Legacy／規則分支 id…）改簡短人話；可見題號「①②③④」移除（保留 `data-ui2-q`、新增 `data-ui2-qname`）；重複標籤合併（OneBrain 標題＋列標籤）。③ 標題外顯「（L2）」「（L3）」拿掉、「指標明細（16 項）」逐字恢復（區塊仍在，P3 才移除）；`NUI2-COMMENT-DOCSTRING-SYNC` 列出的過時註解／docstring 同步（0 邏輯變更）。
- **ui2_dev 不是 auth 證據**：`dev_surface_enabled()` 只讀 `st.query_params['ui2_dev']=='1'`，結果只決定是否畫開發面；`check_ui2_dev_not_auth` 保持綠（含 mutation：`dev→signed_in_flag` 紅）；T_new_9 斷言四頁產品內容在 dev／非 dev 逐字相同。帳戶示意態（signed-out／in／unavailable）預設 signed_in，真實 auth contract 不在本批（`NUI2-AUTH-CONTRACT-GATE`）。
- **關鍵設計選擇（內部自決，CLAUDE.md v3 §03-1；無新客戶裁示、無新 DEC）**：(1) 文案改寫＝只動 canonical 的使用者可見字串，不動 VM 結構／欄位／語意；(2) L0 `regime_arbiter.*_EXPLAIN`（逐字、含 `DEC-074／075`、`macro_state.json`）不改，Human UI 以 render policy（`html.shown()`／`is_dev_only_text`）不畫含治理參照的 `detail`，VM 逐字保留，測試斷言「被略過者只能是這兩個 L0 常數」（`NUI2-P1-L0-EXPLAIN-WITHHELD`）；(3) 原 `html.freshness_html` 對「規則分支 id」來源的處理經查**原本就不渲染**（Real 四頁 DOM 無「規則分支」），故不新增死碼；(4) 紅色錯誤句保留例外型別名（`NUI2-P1-ERROR-TYPE-NAMES`）。
- **測試**：新 `tests/test_ui2_p1_human_text.py`（75 項）；`T_new_2`／`T_new_5`／`T_new_9` 畢業（移除 strict xfail，`GRADUATED_TEETH` 守衛）；`T_new_1` 加結構判準；T13／T5／T10 隨開發面改；`PENDING_UI_CORRECTION_TESTS` 移除 7 項已處理者。**strict xfail 由 15 降為 10 個 test 實例**（原 15＝T_new_1×3 頁、1b×3 頁、2×3 頁、3、5、6、7、8、9；移除 P1 負責的 T_new_2×3＋T_new_5＋T_new_9＝5 個；餘 T_new_1×3、1b×3、3、6、7、8＝10；T_new_2 同時擴為 4 頁〔加 🎯〕且為一般測試）。
- **實測**：見 BACKLOG §5.1.26「P1 完成補記」；證據 `docs/vnext/newui2_p1/`（`fake/`、`real/`、`real_states/`、`dev/`、`v156/`；各含 JSON，精選截圖）。目視過的截圖：FAKE 手機 `mobile_p4_market_{loaded,unavailable}`／`mobile_p4_target_{loaded,stale_lookup}`／`mobile_p4_me_loaded_signed_out`、桌機 `desktop_p4_market_loaded`；Real 手機 `mobile_p4_market_real`、桌機 `desktop_p4_me_real`／`desktop_p4_target_real_lookup`；Real 固定 snapshot 手機 `mobile_p4_market_{unavailable,stale}`；開發道 `mobile_dev_p4_market_devsurface`／`desktop_dev_p4_me_devsurface`、預設道 `desktop_default_p4_hold_first`。**其餘截圖僅經判定器（viewport 判定＋可見文字詞彙掃描）而未逐張目視**（70＋11＋56＋16 態；誠實揭露）。
- **限制**：Cloud 上 Deploy／⋮ 未驗；Safari／Firefox／iOS／真機未測；新文案措辭未經客戶看過；詞彙清單掃描非窮舉語意稽核；單組、未經獨立 QA。
- **未碰（硬限制）**：auth／OAuth 本體、Decision Digest schema、Risk Cap、System Action、新 canonical contract／source／公式／門檻、P2～P7 項、`app.py`／`src/ui`／`src/ui_v2`／`src/data`／`src/compute`／`.streamlit/config.toml`。
- **§27 檢查**：新 Decision＝無（P1 實作選擇屬內部自決）；新 Rule＝無；Audit finding／Limitation／Backlog／Acceptance item 已寫入 BACKLOG §5.1.26「P1 完成補記」（含 5 個新 ID）、Active Contract §6／§9 📌、Audit Checklist §22、本節、HANDOFF 最末 Safe Handoff。
- **全量驗證（實作組實測，單組）**：`python -m pytest tests -q -p no:cacheprovider -m "not slow"`（序列）＝**37047 passed、0 failed、46 skipped、186 deselected、10 xfailed**（21 分 05 秒；於 P1 commit `30e6a5f0` 內容上跑；其後 merge #1006 只帶入 3 個 docs 檔，merge 後另跑 docs 守衛）；slow 真瀏覽器 `test_ui2_batch2.py` 1 passed；Streamlit 1.56.0 venv 跑 `test_ui2_p1_human_text.py`＋`test_ui2_contract_teeth_pending.py`＝85 passed、10 xfailed。
- **#1006 合併記錄**：`de5f272e`（docs-only，新增 `docs/vnext/NEWUI2_UI_EXECUTION_SPEC_2026-11-04.md`，Active Contract 的人類可讀施工附件，非第二套 SSOT）已合併進 `origin/main`；本分支已 merge（無衝突）。CI 綠與獨立 QA 結論（P1-1 已以 S1 勘誤、S2～S11 已套用於 `aaa9ea30`）為總管轉達。P3 登記見 BACKLOG §5.1.26「#1006 施工附件合併記錄」（`NUI2-EXEC-SPEC-UNCOVERED-DETAILS`／`NUI2-ACTIVE-CONTRACT-VS-WIREFRAME-RISK-ORDER`／`NUI2-EXEC-SPEC-P7-ORDER-NOT-AUTHORITATIVE`）。四項撰寫組暫定維持 Pending。
- **P1 QA 修正（兩組獨立 QA 無 P0／P1；2026-11-03；實作組單組、待總管複驗）**：處置全表見 BACKLOG §5.1.26「P1 QA 修正補記」。要點：Capability 欄位原因句不再寫「尚無資料」（改「此項目尚未開放」）＋三軸文案守衛 `test_capability_and_missing_copy_never_cross_axes`；錯誤型別名不上畫面（`_error_text` 固定句，`NUI2-P1-ERROR-TYPE-NAMES` 結案）＋詞彙／渲染層加 `Error|Exception` 後綴規則；FAKE microtag 改「FAKE 示意資料／FAKE 示意」（FAKE 前綴與 banner 保留）、去「冷啟動」「占位」；expander 去文字「▸」；來源 chip 可換行；`REGIME_SEE_WHY` 前提註解＋測試鎖 `BREADTH_PROXY_SCORING_ENABLED=False`；`html.shown()` 對未知治理參照句 print 警告。P3-6（🎯 查詢摘要重複）查證為 P1 前既有，只登記。`NUI2-P1-L0-EXPLAIN-WITHHELD` 維持 P6 決定。
- **QA 修正後驗證**：`tests/test_ui2_*.py` 1106 passed、10 xfailed（1.59.2）；1.56.0 venv（`/tmp/v156`）`test_ui2_p1_human_text.py`＋`test_ui2_contract_teeth_pending.py`＝**95 passed、10 xfailed**（前述「85 passed」已被取代）；新守衛 mutation 11 項（`_R_EMPTY`／`_R_PORT`／`_R_NOT_IN_BATCH` 改回尚無資料、型別名放回、`FAKE·scenario`／`FAKE-ASOF`／`冷啟動`／`占位` 放回、`BREADTH_PROXY_SCORING_ENABLED` 改 True、`shown` 靜默、`▸` 前綴放回）皆轉紅後還原。viewport／全量序列結果見下條。環境：容器曾重啟，`/tmp/v156`（1.56.0）與 Playwright Chromium 實查仍可用。
- **QA 修正後 viewport 重量（重跑，證據已更新於 `docs/vnext/newui2_p1/`）**：1.59.2＝FAKE 70/70、Real 11/11、預設／開發道 16 態、Real 固定 snapshot 56 態；1.56.0（`/tmp/v156`）＝FAKE 70/70、Real 11/11、dev 道 16 態；皆全綠。逐張目視（QA 修正後）：手機 FAKE `market_loaded`／`target_stale_lookup`／`hold_loaded`／`me_loaded_unavailable`、手機 Real `market_real`、Real snapshot 手機 `market_unavailable`（共 6 張手機）；桌機 FAKE `market_loaded`／`target_loaded`、桌機 Real `me_real`（3 張）。其餘未逐張目視。
- **QA 修正後全量驗證（實作組實測，單組）**：`python -m pytest tests -q -p no:cacheprovider -m "not slow"`（序列）＝**37056 passed、0 failed、46 skipped、186 deselected、10 xfailed**（21 分 00 秒）；slow 真瀏覽器 `test_ui2_batch2.py` 1 passed（結果見本次回報）。
- **#1007 記錄與下一批候選（2026-11-04；docs-only；append；docs 組單組、待總管複驗）**：PR #1007（ChatGPT 撰寫，docs-only 1 檔 `NEWUI2_UI_DATA_EVIDENCE_MAPPING_PLAN_2026-11-04.md`）經總管獨立 QA（無 P0；1 個 P1 事實錯誤＝台股歷史主圖／MA 描述；9 項 P2）以 12 項最小文字勘誤（`c4b31a63`）修正，CI 綠，squash merge `6cb588d7`；**不是新客戶 Decision、不是 Real Feed 授權**；勘誤時發現舊 mapping 的 H3 是「目前曝險」非「建議持股水位」（新列編號寫「—」）。未驗限制：QA 未執行 service runtime 驗證、未窮舉 caller。QA 未處理項已登記（BACKLOG §5.1.26 末：`NUI2-PLAN1007-CAPMAP-UNCOVERED`、`NUI2-PLAN1007-METADATA-NO-L3`、`NUI2-PLAN1007-P3-T1B-TENSION`；`NUI2-TWII-TWO-PATHS` 與 `NUI2-ACTIVE-CONTRACT-VS-WIREFRAME-RISK-ORDER` 在 BACKLOG 已有條目，僅交叉參照）。新增「下一批候選（供客戶選擇；非授權）」A＝P3／B＝P2①②／C＝P7 殼；**不替客戶選定**。§27 檢查：新 Decision＝無；新 Rule＝無；Backlog＝3 個新 ID；未改 `src/`、`shared/`、`tests/`、`app.py`；Audit Checklist 無新自勾。

## 62. New UI2 UI Correction P3（Human UI 不渲染 L2／L3 evidence expander；T_new_1b 規格錯誤修正；客戶 2026-11-03 (17)／DEC-131；2026-11-03；append-only；實作組單組、待獨立 QA）

- **範圍（僅三項）**：(0) 修 T_new_1b 測試規格錯誤（A2）；(1) 四頁 Human UI 移除 L2／L3 evidence expander（保留 🎯 選股條件、👤 Decision Digest／Rule Registry 稽核入口）；(2) 更新測試與 strict xfail；(3) L0 位階完整說明過渡期限制記錄。不動資料層／公式／Action Authority／Risk Cap／System Action／Digest schema／OAuth；P2／P6／P7 未動。
- **實作**：`src/ui2/views/_page.py` render policy（L2／L3 預設不渲染、`SHOWN_FOLDS` 白名單 fail closed）；VM／canonical／scenarios 0 行變更。詳見 DEC-131、BACKLOG §5.1.26「P3 完成補記」。
- **L0 位階完整說明過渡期限制**：~~完整說明（`regime_arbiter.*_EXPLAIN`）留在 VM／Digest 可取得處~~ 📌 QA 更正（2026-11-04；過度宣稱已更正，有意識的更正，不是漏刪；決策者 AI 總管〔QA 修正〕）：**保留於 VM**（`regime_arbiter.*_EXPLAIN` 逐字常數與 VM `why` 等 sections）；**Decision Digest 是否涵蓋未驗**（實測 Digest builder 不含位階完整說明、指標明細、lookup 基本面／估值；`NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY`），未來 OneBrain 批須先核對 Digest 缺欄；Human UI 過渡期只見 L1 `REGIME_SEE_WHY`；由 P6 資料健康度承接。
- **測試**：新 `tests/test_ui2_p3_evidence_preservation.py`（baseline 指紋＋渲染層＋Digest import 閉包＋teeth）；`T_new_1`／`T_new_1b`（新驗收）畢業；strict xfail **10 → 4**。
- **實測（實作組單組）**：viewport FAKE 70／Real 11 態全綠（1.59.2 與 1.56.0 各一輪）；證據 `docs/vnext/newui2_p3/`。全量序列 `python -m pytest tests -q -p no:cacheprovider -m "not slow"`＝**37210 passed、0 failed、46 skipped、186 deselected、4 xfailed**（21 分 24 秒）；slow 真瀏覽器 `test_ui2_batch2.py` 1 passed。
- **§27 檢查**：新 Decision＝DEC-131（客戶 (17) 逐字）；新 Rule＝無；Audit finding／Limitation／Backlog＝5 個新 ID 已寫 BACKLOG；Audit Checklist §23 新節（未自勾）。
- **P3 QA 修正（2026-11-04；實作組單組、待複驗）**：兩組獨立 QA 無 P0／P1。已修：baseline 指紋擴大鎖定（內文雜湊）＋baseline sha256 釘值、RuleID 現況鎖定（VM 尚無 RuleID 欄位）、Digest 過度宣稱更正、`_evaluate_p3` 缺鍵判紅＋單元測試；登記 `NUI2-P3-CONDITIONS-TITLE-PAREN`、`NUI2-P3-DIGEST-DYNAMIC-IMPORT-BLIND`。細節見 BACKLOG「P3 QA 修正補記」、DEC-131 §六。全量 not slow＝37219 passed、0 failed、46 skipped、186 deselected、4 xfailed；slow 1 passed；viewport 1.59.2／1.56.0 各 FAKE 70＋Real 11 全綠。§27：新 Decision＝無；新 Rule＝無；Backlog＝2 新 ID；Audit §23 加第 9 項（未自勾）。


## 63. DEC-132：客戶覆核 (18)——#1009 兩灰區裁定落盤＋P2「文字線框先行」交付（客戶 2026-11-04；2026-11-04；docs-only；append-only；docs 組單組、待總管複驗）

- **範圍**：docs-only（`docs/DECISIONS.md` DEC-132、`docs/vnext/NEWUI2_P2_TEXT_WIREFRAME_2026-11-04.md`、BACKLOG／PROJECT_STATE／HANDOFF／Audit Checklist §24／Active Contract §11 與施工附件指標、`tests/test_ui2_active_contract_docs.py` 加性守衛）。**0 行 src／shared／app／既有 tests 行為變更**；不授權任何實作。
- **裁定**：(1) 👤 Data Freshness／System Information 維持不在四頁一般 Human UI，由 P6 資料健康度承接，不得刪 VM／資料來源／provenance／Evidence；(2) 🎯 跨季趨勢與完整分析暫不恢復舊 L3 expander，保留為設計候選（精簡圖卡優先；資料來源／EPS 口徑／版型另行驗證；**仍 Pending，不是核准功能**）；(3) VM 保存≠Digest 已有，`NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY` 維持 open，未證實前不得宣稱 OneBrain 可讀完整資料；(4) P2 採文字線框先行，本輪僅線框與資料欄位驗證。
- **P2 線框**（待客戶驗收；QA 勘誤已套用）：OneBrain 上移至今日主要風險之後／Primary 槽之前；台股 Primary 誠實空槽＋一行 SPEC（來源／資料日取 TWII 卡 freshness，**省略頻率欄**）；歷史序列／MA 不接。**披露**：手機指標卡會被推到第一屏之下（QA 原型：560→798px；餘裕 166.5→162.5px，須 ≥160px），待客戶確認 G-3。待客戶確認 3 點：G-1 空槽高度、G-2 SPEC 欄位、G-3 手機指標卡下移。排序核對結論：以 Wireframes／DEC-122 Q3=A／DEC-127 為準，不需客戶裁示。
- **§27 檢查**：新 Decision＝DEC-132；新 Rule＝文件措辭規則；Backlog＝既有 ID 狀態更新；Audit §24 新節未自勾。

## 64. New UI2 UI Correction P2（OneBrain 位置＋台股 Primary 空槽＋SPEC；客戶 2026-11-04 (19)／DEC-133；2026-11-04；append-only；施工組單組、待獨立 QA）

- **範圍（僅兩項）**：(1) 🤖 OneBrain Outlook 移至核准位置（手機＝今日主要風險之後、Primary 空槽之前、指標卡之前；桌機單行）、內容不變；(2) 🇹🇼 台股趨勢 Primary 誠實空槽（`⬜ 尚未提供`、灰底、0 圖形、依內容高度）＋一行 SPEC `SPEC｜最新收盤參考｜<來源>｜資料日 <as_of>｜缺值不補`（省略頻率欄；與 TWII 卡 freshness 逐字一致）。
- **客戶裁定**：G-1＝A、G-2＝B、G-3＝A；順序差異確認；Active Contract §3.1 最小文字勘誤已套用；SPEC 須標「最新收盤參考」（資料誠實性）。詳見 DEC-133。
- **實作**：`src/ui2/views/market.py`／`_page.py`（`section_l1_html`、`render_sections(skip=)`）、`components/html.py`（`spec_line_text`／`primary_slot_html`）、`shell/css.py`；**VM／canonical／`shared`／`src/services`／`app.py`／資料層 0 diff**。
- **測試**：新 `tests/test_ui2_p2_primary_slot.py`；`T_new_6` 畢業、strict xfail 4→3；viewport 判定器加 `p2_onebrain_primary_slot_order`／`p2_nav_margin_160`；每項新守衛附 mutation 實測轉紅後還原（見 BACKLOG 補記）。
- **實測**：viewport FAKE 70／Real 11 全綠（Streamlit 1.59.2 與 1.56.0 各一輪）＋Real 固定 snapshot 5 態各 11 態（loaded／stale／missing／unavailable／contract_error）（兩種口徑勿混：①**Real 固定 snapshot＝九態**〔loaded／unloaded／unevaluated／stale／stale_unknown／missing／upstream_error／unavailable／contract_error，`tests/test_ui2_p1_human_text.py::_snapshots`；AppTest 與渲染層測試用〕；②viewport 量測的「Real 11」＝**活 Real feed 的 11 個量測態**〔4 頁×2 viewport＋🎯 查一檔模式＋手機壓力態〕。本批 viewport 另以其中 5 個 snapshot〔loaded／stale／missing／unavailable／contract_error〕各跑 11 態＝55 態）；手機導覽餘裕 stale／unavailable＝181.6／162.5px（≥160）；證據 `docs/vnext/newui2_p2/`。
- **§27 檢查**：新 Decision＝DEC-133；新 Rule＝無；Backlog＝1 項結案＋限制記錄；Audit Checklist §25 新節（未自勾）。

## 65. New UI2 P6 資料健康度／手機抽屜 文字線框（2026-11-04；docs-only；append-only；單組撰寫＋一組獨立 QA）

- **已產出**：`docs/vnext/NEWUI2_P6_DATA_HEALTH_TEXT_WIREFRAME_2026-11-04.md`、`docs/vnext/NEWUI2_MOBILE_DRAWER_TEXT_WIREFRAME_2026-11-04.md`（零程式碼、零測試變更）。狀態＝已過獨立 QA，待 ChatGPT／客戶線框審查；**尚未取得客戶核准**。
- **P6／抽屜施工未授權**（客戶 (20)）；P7、auth 契約 Gate（`NUI2-AUTH-CONTRACT-GATE`，Opus 5.5＋High）未動。H-11（P6）與 J-6（抽屜）為同一題，措辭已對齊。
- **撰寫組推薦（非裁示）**：抽屜實作採 C（CSS-only checkbox），B 為備案。
- **未驗**：iOS／Android 真機、Streamlit Community Cloud（含 Manage app 浮層）、VoiceOver／TalkBack；僅 Chromium headless × Streamlit 1.56.0／1.59.2 實驗。欄位盤點以讀碼為準，未對各 service 實呼叫。
- **§27 檢查**：新 Decision＝無；新 Rule＝無；Backlog＝新增 `NUI2-P6-VOCAB-VS-CAPABILITY-TEXT`、`NUI2-P6-WIREFRAME-CUSTOMER-DECISIONS`；Audit Checklist §26 新節（未自勾）。

## 66. New UI2 手機抽屜施工前驗證（2026-11-04；docs-only；append-only；單組撰寫＋一組獨立複驗）

- **已入庫**：`docs/vnext/NEWUI2_MOBILE_DRAWER_PREIMPLEMENTATION_VERIFICATION_2026-11-04.md`＋證據 `docs/vnext/newui2_drawer_preimpl/`。環境 Chromium headless×Streamlit 1.56.0／1.59.2，非真機。
- **結論（非裁示）**：推薦 C+JS（需新 JS＋安全白名單 Gate），否則 C-pop（(5) 部分）；A 不可行；B 無優勢；Auth Gate 不需要。線框「☰ 8px＋44px」使 unavailable 餘裕 154.5<160，須改占既有 44px 保留帶（162.5）。
- **施工未授權**；前置：治理／客戶核准線框與新 JS Gate、J-6 字樣、施工 PR 同批改寫 4 個 CSS 測試與 harness。P7、`NUI2-AUTH-CONTRACT-GATE` 未動。
- **未驗**：iOS／Android 真機、Cloud Manage app、VoiceOver／TalkBack、Firefox／WebKit、Cloud CSP 對 `st.html` JS。
- **§27 檢查**：新 Decision＝無；新 Rule＝無；Backlog＝新增 `NUI2-DRAWER-PREIMPL-VERIFICATION`、`NUI2-DRAWER-NEW-JS-GATE`；Audit Checklist 未自勾。

## 67. New UI2 手機抽屜統一施工規格／JS 安全設計／測試與驗收規格（2026-11-04；docs-only；append-only；單組撰寫＋待獨立 QA）

- **已入庫**：`docs/vnext/NEWUI2_MOBILE_DRAWER_UNIFIED_BUILD_SPEC_2026-11-04.md`、`docs/vnext/NEWUI2_MOBILE_DRAWER_JS_SAFETY_DESIGN_2026-11-04.md`、`docs/vnext/NEWUI2_MOBILE_DRAWER_TEST_AND_ACCEPTANCE_SPEC_2026-11-04.md`（零程式碼、零測試、零 workflow 變更）。另在舊線框主檔、P6 線框檔頭、J 表處**只追加**指向註記。
- **本輪治理採用**：inert（精準範圍）、點當前頁收合、C+JS 首選候選（**正式 JS 未核准**）、J-6 採 B（Capability 軸）、☰ top:0/left:0/44px 占既有頂部保留帶（52px／8px 配置不可用）。來源＝治理方向（ChatGPT／客戶側經總管轉達），**非客戶視覺驗收**（使用者在 #1016 自述看不到圖片）、**DEC 尚未落盤**（落盤與否由 ChatGPT／客戶決定，本批未新增 DEC）。
- **未授權**：抽屜／P6 施工、JS、workflow 變更；P7、`NUI2-AUTH-CONTRACT-GATE`（Opus 5.5＋High）未動；DEC-128..134 與 Active Contract 一字未動。
- **未驗**：iOS／Android 真機、Streamlit Cloud／Manage app、CSP、VoiceOver／TalkBack、Firefox／WebKit、GitHub Actions runner 耗時；瀏覽器數字皆研究組單組 Chromium 結果，撰寫組未重跑。
- **§27 檢查**：新 Decision＝無（DEC 落盤由 ChatGPT／客戶決定）；新 Rule＝無；Backlog＝新增 `NUI2-DRAWER-UNIFIED-BUILD-SPEC`、`NUI2-DRAWER-JS-SAFETY-DESIGN`、`NUI2-DRAWER-TEST-ACCEPTANCE-SPEC`、`NUI2-DRAWER-CI-BROWSER-LANE`、`NUI2-DRAWER-CLOSED-A11Y-RESIDUAL`，並對 `NUI2-DRAWER-NEW-JS-GATE`／`NUI2-P6-WIREFRAME-CUSTOMER-DECISIONS` 補註；Audit Checklist §27 新節（未自勾）。


## 68. New UI2 手機抽屜施工（2026-11-04；DEC-137；實作組單組；獨立 QA 待做）

- **已做**：手機 ☰＋左側抽屜（預設收合）、桌機 176px rail 不變；JS_V4（固定常數、雜湊釘住）；帳戶摘要固定占位（Capability「⬜ 尚未提供」、disabled 登入鈕）；L-4 CSS 修法；viewport 判定器／既有守衛等價或更嚴改寫；Playwright `ui2_browser` lane（1.56.0／1.59.2 各 52 passed、skipped 0）；CI `ui2-browser`＋`ui2-browser-gate`；證據 JSON 加 meta 並重生（1.59.2／1.56.0；FAKE 70 態、Real 11 態全過；stale 181.6／unavailable 162.5 逐位相同）。
- **路徑比較**（見 PR 描述）：(a) JS_V3 原文照用＝Enter 不可用、不符使用者要求；(b) V3＋最小修補（Enter 兩行＋CSS L-4 修法）＝採用；(c) C-pop＝需重新裁示、不採。
- **未通過／限制（不標 PASS）**：L-1 `stMain` 焦點停靠；L-2 新節點約 1 frame 未 inert；L-3 不支援 inert 的瀏覽器；L-5 body 層 portal／Manage app 浮層不被 inert；L-6 ☰ 在 DOM 末端；L-8；`ui2-browser-gate` 尚未被設為 required；真機／SR／Cloud CSP 未驗。
- **未動**：P6、四頁視覺、OAuth／Sheet、OneBrain、Digest、Risk Cap／System Action、公式、資料來源、P7、`NUI2-AUTH-CONTRACT-GATE`；DEC-128..136 與 Active Contract 文字一字未動。
- **§27 檢查**：新 Decision＝DEC-137；新 Rule＝無；Backlog＝補註＋4 個新 open 項；**Audit Checklist 未自勾**（待獨立 QA）：□ 獨立 QA 複驗 □ Visual Fidelity（截圖 `docs/vnext/newui2_drawer_impl/`，需客戶確認）□ required check 設定 □ 真機。


<!-- PROJECT_STATE_HISTORY_INDEX:BEGIN lines=1110-1116 archive=docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q2；只搬不改）**：原 L1110–L1116 已逐字搬至 `docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md`（分冊 L91–L97）。本處原為下列 1 節（標題逐字）：
  - 原 L1110–L1116 → [分冊 L91–L97](archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md#ps-hist-69)：## 69. New UI2 視覺完善 Batch 1（2026-11-05；presentation-only；實作組單組；獨立 QA 待做）
<!-- PROJECT_STATE_HISTORY_INDEX:END -->

## 補註（2026-11-05｜#1020 視覺完善 Batch 1）
- 獨立 QA 通過（0 FAIL），待合併（draft）；DEC-138 維持 Dark-only，不新增 Light 支援。
- 局部修正、非整頁完成：W-11 Primary 圖／⑤ 建議持股區間／持股表未做（B 類，需草稿裁示）；限制保留於 BACKLOG／HANDOFF。
- 下一個安全工作：💼 完整 W-11 與 🎯 精選線框草稿（須先出草稿裁示）。

<!-- PROJECT_STATE_HISTORY_INDEX:BEGIN lines=1122-1124 archive=docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md -->
- 📦 **路徑索引（2026-11-12，DEC-173 Q2；只搬不改）**：原 L1122–L1124 已逐字搬至 `docs/archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md`（分冊 L103–L105）。本處原為下列 1 節（標題逐字）：
  - 原 L1122–L1124 → [分冊 L103–L105](archive/historical/PROJECT_STATE_HISTORY_2026-11-12.md#ps-hist-69-note2)：## 補註（2026-11-05｜💼 W-11 批 1 版面空槽）
<!-- PROJECT_STATE_HISTORY_INDEX:END -->

## 70. New UI2 有效專案知識與第一版資料資格（2026-11-07 checkpoint；GitHub 最新為準）

> 本節是**目前有效的專案知識索引**，不是逐字聊天、第二套 Decision，也不是授權直接施工；與未合併 Draft 不一致時先核對最新 GitHub。原始依據：使用者五頁與 OneBrain 方向（DEC-142，已為 main 正式 DEC；#1030 為原提案 PR，仍 open）；GitHub 記憶及資料資格（DEC-143，已為 main 正式 DEC；#1034 為原提案 PR，仍 open）；已入 main 的 #1031 研究提案、#1033 資料缺口及 supersession 稽核。DEC-141～145 的正式收斂 PR #1045 已合併（`848fd977`）；後續 DEC-146（#1050，`67a7cea5`）核准五頁頂部兩列導覽方向（工程未施工，見 `docs/vnext/NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md`）；#1051（`9ca5441e`）`docs/handoff/stock_github_checkpoint_2026-11-07.md` 為歷史量測時點快照，非第二套 SSOT。cron 資料發布路徑 #1035／#1036／#1037／#1042 已合併，真實發布端到端 NOT VERIFIED，與 #1038 PIT 阻塞（禁合併）獨立。DEC-147 分工更新已由 #1052（`d709d87b`）合併生效；#1030／#1027 的獨有文件已由 #1053（`71ac2889`）保存，#1030、#1027 可依 DEC-147 條件關閉；#1034 的 PROJECT_RULES §0.4／§32／§33 抽取與重編號**尚未做**；#1048 已被 DEC-146＋Gate 文件承接，可關閉。

### 70.1 對下一版仍有效的產品方向
- **五頁目標**：📊市場／🎯標的／💼持股／👤我的／🗂資料。手機與桌機**頂部五頁導覽**（手機可橫滑）、頂部 Active Sheet 選擇與右上帳號、Dark-only、Mobile-first；完整資料來源健康度集中🗂資料。四頁、桌機左 rail、手機 Drawer、健康度牆留👤我的屬**舊版面歷史**；現行已寫的 JS_V4／安全守衛不得無等價 Gate 擅刪。〔已更新（2026-11-07 晚，#1055 `5bd4a7ea`）：五頁頂部導覽已在 main，JS_V4 已以零 JS 守衛＋原生鍵盤測試等價取代而退役，見 §70.4。〕文件適用性註記 PR #1046 已合併（`08bf2b68`）。
- **OneBrain**：同一核准 canonical/Evidence 基礎→確定性 Domain／Risk Cap／Single Action Authority→Human ViewModel 精簡呈現與完整 Decision Digest 分離→按需協調六研究領域（市場、籌碼、財報、產業、持股、資料稽核）及全域正反證複核；白話短／中／長不固定月份。AI **不自行取數、不回寫、不繞過正式動作權威**；VM 存在不代表 Digest 已涵蓋，現階段仍不能宣稱 production OneBrain 完成。
- **研究候選（非正式行情／訊號）**：2026/10 教材中的大盤 EPS×PE 情境、疑似產業缺貨／大型訂單、AI/CSP CAPEX／OCF／FCF、外資融資與國際利率；需先審核來源、發布時點、EPS/PE 口徑、真實觀察與推論、反證及資格，才可設計研究 Sheet（另走 Schema/權限 Gate）。教材歷史指數區間不可當目前市場數值。
- **Old UI 能力重用 Gate**：財報體檢／跨期變化、月營收、法人與集保、總經與國際、ETF/持股曝險、疑似缺貨及資料診斷，逐項檢查「來源核准／可達性／資料日與發布日／Missing／公式與期間／新 UI2 feed 接線／Digest 覆蓋」。有舊程式≠可用、有 VM≠已接 AI、有來源缺口≠官方無資料。細節見 main `docs/vnext/NEWUI2_SUPERSESSION_AND_DATA_GAP_AUDIT_2026-11-06.md`。

### 70.2 稽核發現與完成限制
- `shortage_screener` 四種財務足跡僅是**疑似缺貨**，非官方確認大單；收入缺值曾見分項 0 及其他項仍 rankable。 `fin_trend_score` 月／季缺腿有 0→中性風險，`fin_health_diff` 與現金流單季／累計口徑仍須獨立負測試。這些是**待複驗稽核線索**，不是本批核准修改投資公式。
  📌 **2026-11-08 更新（DEC-149）**：客戶已核准方向——`fin_trend_score` 維持 65%／35% 原始權重不重配、必要資料不足不產正式綜合評級；缺貨排名採至少兩項有效獨立證據資格、四項全缺排除正式排名並保留「無法評估」診斷、證據不完整的強缺貨訊號先研究降級或封頂（具體封頂分數、有效／獨立定義細節、新權重等尚未裁定）；施工分批見 BACKLOG／HANDOFF，~~目前僅 docs、未施工~~（2026-11-08 已更新：三批已 squash 合併：#1067（D3 B2，main `fb37488`）、#1068（財報缺值資格，main `db82a20`）、#1069（缺貨 Phase 3B，main `234c5f4`），皆最新 head 原生 CI 全綠、各有非作者 QA，發布端到端仍 NOT VERIFIED；~~餘項待客戶裁示~~（部分已由 DEC-150 取代：財報缺腿、空快照、C4 缺月、無法評估檔數揭露、缺貨證據資格與研究分流的方向已核准；缺貨有效／獨立定義、固定封頂、揭露分母分類、歷史案例等其餘仍待驗證；有意識的更新，不是漏刪；決策者 客戶），見 BACKLOG `NUI2-FIN-CHANGE-QUALIFICATION`／`NUI2-SHORTAGE-VERIFIED-EVIDENCE`；有意識的更新，不是漏刪；決策者 AI 總管（事實更新））。 📌 **2026-11-08 追加（DEC-150，客戶第三直接裁示，~~僅 docs、尚未施工~~〔2026-11-08 已更新：Batch A 已合併 #1072，見下句；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）〕）**：財報缺任一必要腿不產正式綜合評級（65/35 不變）、接受空快照資格修正造成的排序變化、缺貨證據資格方向＝資料品質＋不同經濟機制＋日期／來源雙重驗證（具體准入條件先驗證）、強缺貨缺證據留研究清單不立即訂固定封頂、C4 缺月不得認連續加速、在既有相關畫面揭露無法評估檔數；有效／獨立定義、固定封頂、C4 月份日期契約、揭露分母與分類仍待驗證或裁示，施工分批 Batch A→B1→B2／B3→C，見 DECISIONS／BACKLOG／HANDOFF。 📌 **2026-11-08 追加（DEC-150 本批結果）**：Batch A 已合併 #1072（main `438dd7b`，缺任一必要腿不產正式綜合評級，65/35 與公式未動；`diff_failed` 保守判定與月腿有效門檻待客戶確認）；Batch B1（C4 缺月）調查結論＝停手進 Decision Gate、B2／B3 研究（單組讀碼＋合成枚舉，未經第二組複驗，歷史報酬 NOT VERIFIED）與 Batch C（分母與線框未定）均未施工，~~下一步等客戶裁示~~（已由 DEC-151 更新：客戶 2026-11-08 已核准 C4 方向，下一個唯一安全工作＝C4 Batch A 月份契約；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；DEC-151），詳見 BACKLOG『NUI2-DATA-D1D3C』段『DEC-150 本批結果』與 HANDOFF 最新接手點；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）。 📌 **2026-11-08 追加（DEC-151，客戶第四直接裁示，僅 docs）**：C4 採最近三個完整且已達可信公告時點的日曆月、可信月份鍵、保留缺值位置；不連續不得判逐月加速，可依既有部分達標規則評分但不得虛構證據；公告時點證據仍待驗證（無法驗證標『日期資格 NOT VERIFIED』）；施工分批 Batch A 月份契約→B C4 評分修復→C 整合驗收，見 DECISIONS DEC-151／BACKLOG／HANDOFF；有意識的更新，不是漏刪；決策者 客戶。
- 第一版到 UI2 的真實 API 成功率、資料流、source/as_of、授權與完整 Digest coverage **未實測完成**；勿把 `NOT_VERIFIED` 或 `N0~N4` 稽核分組升格為正式 Data State 第六態。
- 已落 main 的 #1041 帳本 Fail-Closed、#1042 Parquet 原子寫入與 #1043 孤兒暫存檔 ignore，是資料保存安全修復；**#1038 仍因 PIT（2026-11-05 資料列引用較晚的 as_of）不得合併**。pandas 舊版 object 浮點精確比對已由 #1049 合併（Issue #1044 closed）。讀到 BACKLOG/HANDOFF 舊段「非原子／孤兒 tmp 未 ignore」時，以 GitHub 真實合併證據為準。

### 70.3 使用方法
- 下一個 session **先重新 GitHub Verification Gate**（main、Open/Draft PR head/diff、CI/QA、branches），再參照 DECISIONS、BACKLOG、HANDOFF；舊文件原文保留歷史，不把歷史 next action 當今日工作。
- 新五頁 Layout、Auth/Sheet、JS 安全遷移、正式 Evidence Schema／OneBrain runtime、來源/金融公式/Risk Cap 均須各自 Gate；**本節不代表已核准施工**。

### 70.4 New UI2 現況更新｜五頁＋頂部兩列導覽已在 main（2026-11-07 晚；#1055 squash `5bd4a7ea`，head `da2dfb34`）

> 本小節只更新「現況」，不改 §70.1～70.3 歷史敘述；**FACT／INFERENCE／RECOMMENDATION** 分開寫。與 GitHub 最新不一致時以 GitHub 為準。

**FACT（來自 #1055 合併事實與獨立 QA／原生 CI 回報）**
- 五頁 Preview：📊市場／🎯標的／💼持股／👤我的／🗂資料，頂部兩列導覽；UI2 自有五頁登錄於 `shared/ui2_contract/pages.py`，`shared/ia_nav4` 未動。
- 第一列＝Active Sheet｜FAKE/Real 標示｜帳號；帳號固定為「⬜ 尚未提供」占位，**不是登入**，不代表 OAuth／Active Sheet 已接線。🗂資料頁僅 Capability「尚未提供」空殼。
- Drawer／rail／☰／`_WRAP_TAGS`／JS_V4（`src/ui2/shell/drawer_js.py`）已退役；改由 `src/ui2` 零 JS 守衛＋真 Chromium 原生 radiogroup 鍵盤測試守住。
- 量測（Chromium 153，390×844 最小首屏餘裕）：FAKE unavailable **169.4px**（舊 162.5px）、Real **175.8px**；Streamlit 1.56.0／1.59.2 同值。4 份 viewport JSON `source_hash` 6ab8f9cf… 已重生。
- 獨立 QA（非作者）＋原生 CI 五項（Fast、Slow、ui2-browser 1.56.0／1.59.2、ui2-browser-gate）於 head `da2dfb34` 全綠。
- 客戶可見差異：手機第一列為兩行（40px），線框為一行；手機 Real 補充說明（「僅台股與市場位階為真資料」）仍隱藏（沿用既有行為）。

**INFERENCE**
- 「FAKE/Real 標示併入第一列」是 **ChatGPT 對 DEC-146 的最小版面修正建議（方案 A），非使用者逐字裁示**；QA 判定在 DEC-146 授權內、未觸發 Gate STOP 條件。此為 QA 解讀，使用者可另行推翻。

**NOT VERIFIED**
- iOS／Android 真機、Safari／WebKit、VoiceOver／TalkBack、Streamlit Cloud CSP、safe-area 真實 inset。上列量測僅 Chromium headless，不得外推。

**RECOMMENDATION／後續**：QA SHOULD-FIX 與文件待辦見 BACKLOG `NUI2-TOPNAV-*`、`NUI2-DOCS-SUPERSEDE-DRAWER-SERIES`。下一個唯一安全動作見 HANDOFF 最末 Safe Handoff（#1034 治理段落抽取）。


### 70.5 C4 月營收月份契約現況（2026-11-08；DEC-151／DEC-152；以 GitHub 為準）

- **FACT**：C4 月份資料契約（#1075，`228e976`）與評分修復（#1076，`556b335`）已在 main，各有非作者 QA 與最新 head 原生 CI 全綠。缺月／不連續不再被壓縮成「連續加速」。
- **現況限制**：全市場批次路徑尚未傳遞可信月份鍵，故**全市場 STRONG 暫時為 0**——這是 fail-closed 過渡狀態（客戶 DEC-152 裁示 3），**不是長期正確排名結果**。合成 3000 檔（seed 20261108，不代表真實比例）顯示 STRONG 963→0、前 50 名換 10 檔（單股路徑換 1 檔）。半邊批次失敗標整池 FAIL_CLOSED 為既有行為，客戶裁示維持。
- **NOT VERIFIED**：FinMind `TaiwanStockMonthRevenue` 之 `revenue_year`／`revenue_month` 欄位語意與「`date` 可能不同於營收所屬月」僅為客戶轉述（ChatGPT 查閱官方文件），本 repo 沙箱無法連 FinMind、未獨立核實；公告時點資格未驗證；真實資料恢復情形未驗證。
- **RECOMMENDATION／後續**：C4-D（以既有欄位傳遞可信月份鍵、回溯相容）→ C4-D-real（需合法 token 環境，blocked）；Batch C 整合驗證進行中。詳見 BACKLOG `NUI2-C4`、HANDOFF 最新接手點、DECISIONS DEC-152。未授權新權重／門檻／封頂／新排名例外。

- **2026-11-08 補（Batch C／C4-D）**：Batch C 唯讀驗證（單組、無第二組、沙箱無 FinMind）未發現缺月被當連續加速的路徑；但下游 `fundamental_screener_service` 把缺貨缺值當 0 分入綜合排序／徽章~~（Decision Gate 候選，需客戶裁示，未修）~~（2026-11-08 已於 DEC-153 裁示（方向 B），見 NUI2-DEC153；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；DEC-153）（具體資格規則仍待 Gate）。C4-D（批次長表帶 revenue_year／month、`BATCH_SOURCE_MONTH_KEY_VERIFIED=False`）已實作於 `c4d-local`（`a958849`），~~**尚未 QA／合併**~~（2026-11-08 已更新：C4-D 非作者 QA 通過（無必修），待 PR／CI／merge；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；DEC-152）~~**非作者 QA 通過（無必修），待 PR／CI／merge，尚未合併**~~（2026-11-08 已更新：C4-D 已由 #1077 squash 合併（main `c5846b7`）；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；#1077）；另有 Decision Gate 候選：單股『date≠ym、ym 齊全』由 FAIL_CLOSED 變最高 STEADY／PARTIAL（連續性建立在未驗證 ym 上），須客戶裁示，AI 不自改；全市場 STRONG 仍恆 0，不得宣稱恢復。細節見 BACKLOG `NUI2-C4`。

- **2026-11-08 補（DEC-153 執行結果；AI 總管事實更新，非客戶裁示）**：GitHub 為準 ~~main `35c08d2`，#1075～#1078 已 merge，~~ ~~現行 main `b01db69`，#1075～#1079 已 merge，~~（已更新：main `476529d`，#1075～#1084 部分已合併，見本檔下一則；有意識的更新，不是漏刪）#1038 Draft NO MERGE，#1034 Draft 待核銷。**Batch A**：FinMind 真實取樣 **BLOCKED**（無 token、無真實／錄製樣本；欄位語意 NOT VERIFIED；全市場 STRONG 仍恆 0，不得宣稱恢復）。**Batch B**：C4 未驗證月份鍵上限~~實作完成＋非作者 QA 通過（commit `93904d0`＋`964f717`），**待 PR／CI／merge，尚未合併**~~（2026-11-08 已更新：Batch B（C4-E）已由 #1079 squash 合併，main `b01db69`，head `d02811d` 最新 head 原生 CI 全綠、非作者 QA 通過；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；#1079）**已合併 #1079**；~~待客戶確認詮釋點（5 分 vs 0 分）。~~（2026-11-08 已更新：已由 DEC-154 裁示（C4 保留 5 分，含全高值，missing 不保底）；有意識的更新，不是漏刪；決策者 AI 總管（事實更新）；DEC-154）**Batch C**：缺貨缺值唯讀研究（單組、合成資料），推薦 A 先行、資格規則進 Decision Gate、不建議數值門檻。詳見 BACKLOG `NUI2-DEC153`、HANDOFF 最新接手點、DECISIONS DEC-153 ③。

- **2026-11-08 補（DEC-154 執行結果；AI 總管事實更新，非客戶裁示）**：GitHub 為準 main `476529d`；#1082（`412d15b`）、#1083（G1，`b6a20b6`）、#1084（FinMind 唯讀探針，`476529d`）已合併，皆原生 CI 全綠、有非作者 QA；#1038 NO MERGE、#1034 待核銷。**G1**：缺貨 n_ok＜4 不再寫確定「缺貨弱」而顯示「部分證據 n/4」，排名／百分位／composite／權重逐位元不變。**探針合併≠執行，尚未執行**（`run_workflow` 403），FinMind 欄位語意與方案可取性仍 NOT VERIFIED，不得翻 `BATCH_SOURCE_MONTH_KEY_VERIFIED`，全市場 STRONG 仍恆 0、不得宣稱恢復。候選視窗研究與 `SHORTAGE_VERSION` 設計（皆未施工）見 DECISIONS DEC-154 ③。


### 70.6 Issue #1140／#1144 後的有效專案知識（2026-11-11；只追加；不改既有節；依據 DEC-164／DEC-165 轉錄，非客戶逐字、非 QA PASS）

> 依 `PROJECT_RULES.md` §0.3／§15／§32：只收「目前仍有效且會影響下一個 AI 判斷」的知識；待辦在 BACKLOG、current／next safe point 在 HANDOFF、正式裁示在 DECISIONS。本檔檔首「量測」行屬 2026-10-29 歷史值（cron 會推進 main）；本節以 GitHub 實況為準，**不在此寫最新 main SHA**。

**FACT（main，各 PR 已合併）**

- 新增兩支**唯讀 L3** service：`src/services/margin_fact_service.py`（融資）、`src/services/sector_flow_fact_service.py`（板塊資金；#1142，`1e5542a87cdc0006a6535b34457f8b59a85f6baa`）。實查：**目前除自身與測試外無 production caller、未接任何 UI**（本節撰寫時以 grep `margin_fact_service|sector_flow_fact_service` 對 `*.py` 檢視；窮舉性單組，NOT VERIFIED 第二組）。外資 L3 **不存在**（另案）。
- 新增 L1 純讀函式 `src/data/sector_flow/reader.py::read_sector_daily_net_latest`（讀 `daily_net.parquet`）與 `read_sector_flow_cron_coverage`；新常數檔 `shared/sector_flow_fact_thresholds.py`（舊常數檔被 `test_batch_z42` sha256 釘住，故另立新檔）。
- 安全修復（#1141，`907322aa0af9570fdcca9a496ffdc83e275bfdd3`）：價格≤0 於卡片與日 K 一致拒用；未來 `as_of` 不再顯示負過期天數（卡片層與日 K 處理**不對稱**，已登記 `I1140-FUTURE-ASOF-ASYM`）。
- 板塊口徑（G-10，DEC-164）：「三大法人合計（外資＋投信＋自營商），依個股張數×收盤價彙總至板塊」，**與「大盤外資淨買賣超（僅外資）」不同、不可直接比較**。#1142 實測 coverage：板塊 41、觀測 38、未觀測 3（**非全市場完整覆蓋**；最低 coverage 門檻**未裁示**）。
- Digest regime／light 缺口（研究文件 `docs/vnext/DIGEST_REGIME_LIGHT_COMPAT_GATE_2026-11-11.md`）：`decision_digest_builder.py::_market_section` 對 `market.regime`／`market.light` 無白名單，非空垃圾值可被當合法 `Fact`；`get_macro_state` 會把非 canonical regime 洗成 `neutral` 且 `is_loaded=True`；`market.health` 僅檢查有限數、無 0–100 範圍。

**授權狀態（Approved ≠ 已完成）**

| 項目 | 狀態 | 出處 |
|---|---|---|
| Digest builder A2（白名單驗證＋反例測試，不改凍結 Schema） | **已授權（客戶同意方案 A）、尚未實作** | DEC-165；Issue #1144 |
| UI2 runtime 接線**前置 Gate**（唯讀研究：coverage／PIT／授權／缺口） | **已授權、尚未施工**（docs-only） | DEC-165 |
| Digest A3 配對一致性、`market.health` 範圍驗證 | **未授權，獨立 Gate** | DEC-165 三 |
| UI2 市場頁「市場資金與籌碼」runtime 接線／上線 | **仍未授權**，需新 Gate（含 G-F2～G-F6、coverage 門檻） | DEC-164 G-9；DEC-165 |

**限制與 NOT VERIFIED**：TWSE／TPEX／FinMind 再散布授權原文、parquet 缺 `release_date` 的 PIT、Streamlit Cloud、iOS／Android 真機、Playwright／viewport、ETF Managers 2026-11-16 20:00 UTC 首次排程、#1126 PIT 皆**未驗**。#1119 維持 HOLD；#1124～#1126 未處置。

**出處**：`docs/DECISIONS.md` DEC-164、DEC-165；`docs/BACKLOG.md`『Issue #1140』『Issue #1144』；`docs/HANDOFF.md` Issue #1144 接手點。與出處不一致時**以出處為準**。


### 70.7 A2 已上線後的有效專案知識（2026-11-11；只追加；不改既有節；依據 DEC-166，非客戶逐字）

- **FACT**：Digest builder A2 已在 main（PR #1146，`d4f7b3f6a64d177b7ee0953dc22563adf59120e4`）：`_market_section` 對 `market.regime`／`market.light` 以由 `REGIME_LIGHT` 推導的白名單驗證，名單外非空值判 `INVALID`；凍結 Schema 未動。更正 §70.6 表中「A2 已授權、尚未實作」→ 已完成。
- **FACT**：UI2 runtime 接線前置 Gate 研究文件已產出（`docs/vnext/UI2_RUNTIME_PREGATE_RESEARCH_2026-11-11.md`），內含 DG-COV／DG-PIT／DG-LIC／DG-SCOPE／WIRING-GATE；AI 推薦方案 B 為 RECOMMENDATION，非裁示。
- **仍未授權**：UI2 runtime 接線、A3、`market.health` 範圍、外資 L3；最低 coverage 與 G-F2～G-F6 待客戶裁示。
- **NOT VERIFIED**：上游授權、PIT `release_date`、Cloud、真機、Playwright、真實 macro_state。
- **出處**：DEC-166；BACKLOG『Issue #1144 結果』；HANDOFF 最新接手點。不一致時以出處為準。


### 70.8 「同意 B」後的有效專案知識（2026-11-11；只追加；不改既有節；依據 DEC-167，非客戶逐字）

- **FACT**：客戶裁示「同意 B」＝UI2「市場資金與籌碼」先做唯讀證據補強、不進正式 runtime 接線；補充文件 `docs/vnext/UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md` 已產出（PR 號：#1148）。
- **FACT（抽查實跑）**：板塊 41／38／3 為窗口標籤聯集，未觀測 3 者為單檔偶發標籤；現有資料算不出個股覆蓋率；`n_dropped_missing_price` 僅最近一次 cron；三資料集無 `release_date`；融資 `fetched_at` 99.5% 為 bootstrap 批值。
- **仍未授權**：UI2 runtime 接線（停在 WIRING-GATE）、A3、health 範圍、外資 L3、方案 A／C 施工、任何 coverage 門檻值。
- **待裁示**：DG-COV、DG-PIT、DG-LIC、DG-SCOPE、WIRING-GATE。
- **NOT VERIFIED**：TWSE／TPEX 授權（全部）、FinMind 官網條款、OGDL 原文、PIT 發布日、休市表、Cloud／真機／Playwright。
- **出處**：DEC-167；BACKLOG『Issue #1144 後續』；補充文件。不一致時以出處為準。


### 70.9 B8「NAS 中繼站備援」後的有效專案知識（2026-11-11；只追加；不改既有節；依據 DEC-168，非客戶逐字）

- **FACT**：客戶新增 B8——官方網站直連不通時，參考舊 UI 的 NAS 中繼方式查證；不授權改網路架構／Secrets／NAS Server／端點／認證／排程，不得自建第二套 Proxy。
- **FACT（本批實測）**：Direct 失敗（沙箱 agent proxy 對官方網域 CONNECT 403）；本環境 NAS 連線資訊與 Squid 設定皆未配置，故 NAS 路徑未測試；官方 GitHub raw 成功（僅 FinMind README）。補充文件 §9 記錄契約與安全限制（`/proxy` 無主機白名單、僅 SSRF 私網封鎖、`X-API-Key` 認證、範例 scheme 為 HTTP）。
- **授權結論無變動**：TWSE／TPEX／OGDL 原文與 FinMind 官網條款仍 NOT VERIFIED；DG-LIC 維持 NOT VERIFIED。NAS 可達≠已授權≠PIT 合格。
- **仍未授權**：UI2 runtime 接線（停在 WIRING-GATE）、網路架構變更、第二套 Proxy。
- **出處**：DEC-168；補充文件 §9；BACKLOG『Issue #1144 後續｜B8』。PR 號：#1149。不一致時以出處為準。


### 70.10 Coverage 母體收斂與官方條款證據後的有效專案知識（2026-11-11；只追加；不改既有節；依據 DEC-169，非客戶逐字）

- **FACT**：客戶授權 docs-only 的 Coverage 母體收斂與 TWSE／TPEX／FinMind 官方條款證據補查；補充文件新增 §10～§12（PR 號：#1149）。其餘 Gate 保持 HOLD，**未關閉任何 Gate**。
- **FACT（抽查實跑）**：現行母體＝窗口標籤聯集 41；3 偶發標籤窗口內 7 股日（全 37 日 15 股日）；僅板塊標籤覆蓋可算，個股／金額／市值覆蓋 NOT VERIFIED；歷史列用回補當下的產業對映（非各日 PIT）。
- **RECOMMENDATION（非裁示）**：暫不改母體；日後揭露至少 COV-A 強制揭露；候選 COV-C「標註不剔除」；不選 COV-B。**未設任何 coverage 百分比。**
- **授權證據**：FinMind PARTIALLY VERIFIED（官方 GitHub Pages 原文，版本日期 2026-10-31；≠TWSE／TPEX 條款；Apache-2.0 只管 SDK）；TWSE／TPEX／data.gov.tw NOT VERIFIED；OGDL 僅 SPDX 轉錄本。repo 公開、`data_cache` 追蹤 29 檔（含 `industry_raw.json`）僅陳述事實，須客戶／法律專業判斷。
- **仍未授權**：UI2 runtime 接線（停在 WIRING-GATE）、新母體、門檻值、任何程式／資料／`data_cache` 變更、刪檔。
- **NOT VERIFIED**：TWSE／TPEX 授權原文、PIT 發布日、3 偶發標籤個股成因、UI 來源標示是否顯示、Cloud／真機／Playwright；證據單組、未經第二組獨立複驗。
- **出處**：DEC-169；補充文件 §10～§12；BACKLOG『Issue #1144 後續｜Coverage 母體收斂』。PR 號：#1149。不一致時以出處為準。


### 70.11 CI 環境最小修復後的有效專案知識（2026-11-11；只追加；不改既有節；依據 DEC-170，非客戶逐字）

- **FACT**：客戶裁示「同意優先採 A，失敗再評估 B」並授權獨立最小 CI workflow 安裝環境修復。#1149 的 `ui2-browser` 因 runner apt／DNS 無法裝 Chromium 依賴而失敗；方案 A 經 CI 實證失效（三個 Ubuntu 來源 host 皆 DNS 失敗）；方案 B＝`ui2-browser` job 改在固定 tag＋digest 的 `mcr.microsoft.com/playwright:v1.64.1-noble` 容器內執行，已由 PR #1150 合併（main `96cb7614`）。#1149 內容未改，Update branch 後原生 CI 五項全綠並合併（main `d8d74ccd`）。
- **FACT（守衛未降）**：matrix 兩版本、`UI2_BROWSER_LANE=required`、junit tests≥40／skipped=0、evidence artifact、`ui2-browser-gate` 全保留；無 `continue-on-error`／`|| true`／skip／降門檻／新 Secret；未改 tests／production；獨立 QA PASS。
- **維護**：升級 Playwright 時 image tag、digest、`playwright==` pin 一併更新；不得用 `latest`。
- **仍未授權／HOLD**：UI2 runtime 接線（停在 WIRING-GATE）、Coverage 母體新算法與最低門檻、PIT 正式語意、資料再散布最終授權、Digest A3／`market.health`／外資 L3。CI 修復不構成上述任何核准。
- **NOT VERIFIED**：僅證明當日 runner 可執行；runner Ubuntu 來源 DNS 故障根因未查明；Streamlit Cloud／真機未驗；`ui2-browser-gate` 是否為 branch protection required check（設定面，本工作階段無權限）。
- **出處**：DEC-170；BACKLOG『Issue #1144 後續｜CI 環境最小修復完成』。docs PR 號：#1151。不一致時以出處為準。


### 70.12 公開 Repository 資料曝露、來源授權與儲存架構唯讀稽核後的有效專案知識（2026-11-11；只追加；不改既有節；依據 DEC-171，非客戶逐字）

- **FACT**：客戶裁示「同意方案 B」並授權 docs-only 唯讀稽核（本 docs PR 號：#1152）。repo 公開；`data_cache` 追蹤 29 檔（約 2.30 MB），個股級 15 檔；Git 歷史 `data_cache` 1,036 個相異 blob（約 80.0 MB）散在各分支與 1,133 個 PR head，停止追蹤不減歷史；網站讀 repo checkout 內 `data_cache`。
- **授權證據**：條款原文僅 FinMind（官方 GitHub Pages，2026-10-31 版）PARTIALLY VERIFIED，其餘來源 NOT VERIFIED，repo 內無授權證據；A（原文）／B（適用）／C（已取得授權）分開；**未下法律定論**。
- **更正**：`industry_raw.json` 的 FinMind 列僅 `date`／`industry_category`／`type` 三欄、官方列僅四欄，非「全部原始列」。
- **安全**：無可確認 Secret／個人資料事件（regex 範圍；非專業掃描器；PR-only 物件未掃）。
- **RECOMMENDATION（非裁示）**：先取得授權書面答案；若降低曝露面，優先評估可逆的方案 C 第一階段；歷史改寫與改 repo 可見性不可逆，須客戶拍板。
- **仍未授權／HOLD**：遷移、刪檔、改歷史、改可見性、改 workflow／Secrets／儲存、UI2 runtime 接線（停在 WIRING-GATE）、Coverage 母體變更與門檻、PIT、`DG-LIC` 最終判斷、Digest A3／`market.health`／外資 L3／OneBrain runtime。
- **NOT VERIFIED**：其餘來源條款、FinMind 方案等級與是否商業、Streamlit Cloud 設定、UI 來源標示、歷史 Secret 掃描窮盡性、第二組獨立複驗。
- **出處**：DEC-171；研究文件 `docs/vnext/PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md`；BACKLOG『Issue #1144 後續｜公開 Repository 資料曝露…』。PR 號：#1152。不一致時以出處為準。


### 70.13 Batch 1～3 後的 UI2 與資料層有效知識（2026-11-12；只追加；不改既有節；依據 DEC-174／DEC-175／DEC-176，非客戶逐字；量測值標日期、會過期）

> 本節只記**目前有效的架構與資料層知識**，每條附出處（文件／DEC）與標籤（FACT＝本組讀碼／讀檔／GitHub 取回；INFERENCE＝推論）。**不是授權**；不解除任何 Gate；數字與狀態以 GitHub 最新為準（出處文件為稽核證據，單組產出，其全稱句只當待驗事項）。基準 main `76ed4b7b`（2026-11-12）。

- **UI2 實際接入真資料 2／8（FACT；量測日 2026-11-12；單組盤點）**：以「🗂 固定清單 8 項」（**為 #1173 文字線框的候選清單，未經客戶核准**）計，UI2 讀取路徑已接 **2 項**＝台股加權指數（📊 台股卡＋20 根日 K，同一份 `data_cache/twii_ohlcv.parquet`）與市場位階（讀取路徑已接，但 UI2 獨立 session 沙箱內恆為「⬜ 尚未載入」；**部署端 NOT VERIFIED**）。其餘 6 項（外資、融資、M1B／M2、台灣 PMI、板塊資金流、基本面季報）UI2 無讀取路徑。**預設路徑（無 `?ui2_dev=1`）只到 FAKE，0 個真值。** 出處：`docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md` §1.2；`NEWUI2_FIVE_PAGE_DATA_CONTRACT_AUDIT_2026-11-12.md` §0（結論 1～3）。位階恆未載入的因果鏈（讀碼）：`allocation_service.get_macro_regime` 讀 `st.session_state['warroom_summary']`，寫入點只在 Legacy，UI2 三目錄 0 寫入。
- **融資／板塊 L3（#1142）UI2 0 呼叫端（FACT；`git grep margin_fact_service|sector_flow_fact_service` 對 `src/ui2`、`src/services/ui2`、`shared/ui2_contract` ＝ 0 命中，2026-11-12）**；大盤外資**無** L3（`finmind_inst` 無專屬 L3）。「市場資金與籌碼」區塊不在 UI2 VM 契約內。接線仍停在 `I1144-WIRING-GATE`。出處：五頁稽核 §0-4；DEC-174 結果指標。
- **🗂 資料頁是固定空殼（FACT）**：`src/ui2/views/data.py::render` 的內容來自 `src/services/ui2/data_page.py::data_page_canonical`，FAKE 與 Real 兩軸共用同一份；`real_canonical._data` **不讀 snapshot**；`data_overview` 區塊只有三欄（來源健康度、資料日、Active Sheet 連線），全為 `⬜ 尚未提供`。畫面上沒有任何總覽新鮮度的位置。出處：資料新鮮度總覽文字線框 §1.1（#1173，待客戶拍板，**候選未核准**）。
- **資料層沒有 `published_at`（FACT）**：資料檔（parquet／JSON）只有觀測日（`date`）與抓取時間（`fetched_at`／`cached_at`／`updated_at`）；來源發布時間不存在，發布 PR 本文一律寫「n/a（來源未提供）」（`scripts/publish_data_pr.py`）。**`data_cache/metadata.json` 的頂層 `updated_at` 是 cron 執行時刻**（每次執行必變，發布腳本把它列為揮發欄），**不是資料觀測日**，不得頂替。`fetched_at` 是**列首次寫入時間**（後續「舊 null→新有值」補值不改該列 `fetched_at`，#1169 調查 §2.1 FACT），且是日 K「是否已收盤（台北 17:00 後）」判斷的輸入（`shared/twii_ohlc_contract.py` 契約註解自陳**不是**歷史 PIT 可得時間證據）。出處：`DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md`；`NEWUI2_DATA_FRESHNESS_OVERVIEW_TEXT_WIREFRAME_2026-11-12.md` §1.3。
- **三套新鮮度規則並存，尚未統一（FACT；稽核登記為 N-1／`DEC174-N1-STALE-THRESHOLD`）**：(1) `shared/freshness_policy.py::assess_daily`——客戶 2026-10-14 核准的引擎計分輸入規則，落後 > `DAILY_MAX_LAG_TRADING_DAYS`＝**3 個交易日**才過期；休市表取不到時依上界／下界判定（上界 ≤ 3 → FRESH、下界 > 3 → STALE、否則 UNDETERMINED），**`git grep assess_daily` 顯示尚未接到 UI2 的 stale 判定**；(2) `shared/staleness.py::STALE_DAYS_DAILY`＝**7 曆日**（顯示用，經 `macro_cache_reader.compute_cache_staleness`，套用於台股指數／外資／融資）；(3) `shared/sector_flow_thresholds.py::SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`＝**4 曆日**（板塊）；另有極端風險兩腿 `shared/signal_thresholds.py::EXTREME_STALE_MAX_CALENDAR_DAYS`＝**10 曆日**（現行唯一讀 `finmind_inst` 的 consumer）。同一資料日會在不同日子「翻面」；基準日也不一致（台股卡用主機 `date.today()`，板塊／融資用台北今日，`I1140-TODAY-TZ`）。是否統一屬客戶 Gate，**未裁示**。出處：資料新鮮度文字線框 §1.4；`shared/freshness_policy.py` 模組註解表。
- **每日資料發布鏈（FACT；讀 workflow／腳本）**：`update_macro_history`（cron 09:00 UTC）、`update_sector_flow`（09:30）、`update_macro_forward_test`（09:40 週一～五）、`update_etf_managers`（週一 20:00）→ `scripts/publish_data_pr.py` → 推 `auto/data-<job>` 分支並以 `GITHUB_TOKEN` 開／更新 PR；**不自動合併**。**INFERENCE（機制）**：`GITHUB_TOKEN` 建立的 push／PR 事件通常不觸發 `pull_request` workflow，所以這些資料 PR 的檢查不會自動跑。**FACT（轉述自 #1172 文件，本組未獨立驗證）**：#1124～#1126 每個 head 都只有結論為 `action_required` 的 pr-check run 紀錄，PR 的 check runs 為空（0）。main 分支保護要求 `ui2-browser-gate`，裸推 main 會 GH006（腳本註解自陳）。**仍以裸 `git push` 直推的 workflow**：`update_fundamentals`（下次排程 11/21，INFERENCE：直推會被同一保護擋下）、`update_forward_test`（每月 2 日）、`calibrate_health_weights`（1／4／7／10 月 1 日）；`update_health_history` 排程已停用（檔內 `schedule` 已註解）；`export_db` 以 `git push -f origin _pub:data` 推獨立 `data` 分支。**因此**主分支上的 `data_cache/` 僅在人工合併資料 PR 後前進：台股卡資料日停在 **2026-11-09**（量測日 2026-11-12）的**最可能**原因是 #1124～#1126 未合併（**INFERENCE，信心高**；排程自 11-09～11-11 皆成功，FACT 轉述 #1169 調查）；台股在分支上缺 11-11 的原因 **NOT VERIFIED**。出處：`DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md` §1；`DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`（#1172，證據缺口 G-01～G-17）。#1124～#1126 目前 HOLD（客戶 DEC-176(a) 方案 A）。
- **CI 結構（FACT；`.github/workflows/pr-check.yml`）**：`pr-check` 共 **5 項**原生檢查——`Fast checks`、`Slow tests`（`continue-on-error`，資訊性）、`ui2-browser (streamlit 1.56.0)`、`ui2-browser (streamlit 1.59.2)`、`ui2-browser-gate`。`ui2-browser` 在固定 tag＋digest 的 Playwright 容器（`mcr.microsoft.com/playwright:v1.64.1-noble`）內執行，junit tests ≥ 40 且 skipped = 0（`UI2_BROWSER_LANE=required`）；**#1171（`2a1623e8`）起該容器 job 一律用 `python -m pip`**（原因：預建 pip 26.3 下 bare `pip` 在容器內 exit 127；失敗 job 131230664848 日誌重讀為證）。**修正有效性仍 NOT VERIFIED**（偶發故障是否完全消失需後續樣本）；`Fast checks`／`Slow tests` 直接跑在 runner、仍有 bare `pip install`，在預建 pip 26.3 image 上無樣本。出處：DEC-170、DEC-176(b)；BACKLOG `DEC176-CI-1171-VALIDITY`。
- **DEC-175／DEC-176 權限邊界（FACT：客戶釐清已落盤）**：DEC-175 是已生效的工作優先序、資料架構與交接治理決策，**不是**無條件的 UI／資料施工授權，不解除 `CLAUDE.md` §-1、文字線框 Gate、資料接線 Gate、獨立 QA、CI 或其他既有治理；既有明確核准的工作可依已批准範圍繼續。出處：DEC-176(c)（經派工訊息轉錄，逐字一致性 NOT VERIFIED）。
- **仍未授權／HOLD／NOT VERIFIED**：`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、G-F2～G-F6、Digest A3、`market.health`、外資 L3、#1124～#1126、#1164、#1119、Old UI／預設 UI 切換；Cloud UI2／真機、部署端位階實況、Streamlit Cloud 追蹤分支、外部來源對帳。
- **出處**：DEC-174（含結果指標）、DEC-175、DEC-176；`docs/vnext/` 的 #1165／#1169／#1172／#1173 文件；BACKLOG 檔尾「DEC-176 結果同步」。PR 號：本同步 PR 見 HANDOFF 檔尾。不一致時以出處為準。


### 70.14 後續註記（2026-11-12；只追加；不改既有節；非授權；非 QA PASS；單組撰寫，未經非作者獨立 QA）

> 本節為 §70.13 的**勘誤與基準更新**。§70.13 上文一字未改；與本節衝突處，以本節「有效讀法」為準。依據：DECISIONS「DEC-174／DEC-176 後續註記：#1169 獨立複驗結論的有效讀法」；`docs/vnext/NEWUI2_INDEPENDENT_REVERIFICATION_2026-11-12.md`（單組複驗文件）。引用行號皆為撰寫時 main `85c65dfc` 的行號，僅供定位。

#### 70.14.1 #1169 複驗結論對 §70.13 的有效讀法

- **新鮮度規則：外資門檻的有效讀法（複驗 E-1；FACT，讀碼）**：§70.13「三套新鮮度規則並存」條（撰寫時第 1244 行）把 `shared/staleness.py::STALE_DAYS_DAILY`＝7 曆日描述為「套用於台股指數／外資／融資」，與同一條後段「極端風險兩腿 `EXTREME_STALE_MAX_CALENDAR_DAYS`＝10 曆日（現行唯一讀 `finmind_inst` 的 consumer）」**自相矛盾**。有效讀法：**外資 `finmind_inst` 的現行 consumer 走 10 日曆日門檻**（複驗文件自述，單組）（`macro_cache_reader.load_extreme_risk_legs`），不經 7 日規則；7 日對 `finmind_inst` 只被校準腳本使用；7 日對台股指數與融資的適用，沿 §70.13 原述（複驗僅就外資更正，台股指數／融資部分未重驗）。因此過期門檻共**三種**（板塊 4／日頻顯示 7／極端風險 10），另有客戶核准的交易日 SSOT `shared/freshness_policy.py`（`DAILY_MAX_LAG_TRADING_DAYS`＝3，**尚未接到 UI2 stale 判定**）；「若日後接 L3 外資會落在 7 日」屬假想，門檻另行決定。另（複驗 E-2）「無交易日曆」過度絕對：repo 有交易日曆服務與休市表抓取，只是這幾條 stale 判定未接。
- **N-1 部分推翻（複驗 E-7；FACT）**：§70.13 稱此不一致「登記為 N-1／`DEC174-N1-STALE-THRESHOLD`」——該登記仍成立，但 N-1 原論述漏引 `shared/freshness_policy.py`（兩份 #1165 文件對它的引用數為 0）；且複驗自身的反向勘誤 R-A 指出：紅隊原句「`assess_daily` 無行事曆會是 UNDETERMINED」錯誤，實測在 11-09／今日 11-12 情境為 FRESH（落後 3 個交易日）。§70.13 此條中對 `assess_daily` 休市表取不到的描述（上界 ≤ 3 → FRESH、下界 > 3 → STALE、否則 UNDETERMINED）與此一致，不需更正。是否統一各規則屬客戶 Gate，**未裁示**。
- **B1 有效讀法**：**未證明違反已核准契約，但不能說「無」**；紅隊找到 R1～R5 **候選**（只分類，不修、不授權 UI 施工；涉及畫面結構須先文字線框＋客戶拍板；R4 併入 VG1；R5 為環境依賴非缺陷）。§70.13 的「UI2 實際接入真資料 2／8」「🗂 資料頁固定空殼」等條，複驗未推翻（核心事實獨立重現，0 個被整體推翻（複驗文件自述，單組）；紅隊盤點非盲測、單組）。
- **仍須注意**：複驗文件是**單組產出**，不等於 `DEC174-B1-INDEP-QA` 結案；其內事實未被再次重驗；#1165 兩份文件仍含被修正措辭、本批不改（是否回寫勘誤附註另待總管／客戶決定）。出處：BACKLOG「#1169 獨立複驗結論的勘誤指標」。

#### 70.14.2 76ed4b7b push CI 紅燈（指標；不重複全文）

- **FACT**：main push `76ed4b7b` 的 PR Check run 43253404141 failure，9 個失敗全在 `tests/test_d6_diagnostic_no_secret_display.py`；同 head PR CI 與最新 main push `85c65dfc` 皆 success。**高度可能為測試偵測器的非決定性缺陷（元素 ID 隨機 hex 命中合成假秘密片段），但 CI 當次實例未被直接驗證 → 不記為「已證實的偶發誤報」。** 只記錄、不修；未經客戶新授權不改測試、不放寬 CI Gate。證據與口徑見 DECISIONS「後續註記：76ed4b7b push CI 紅燈證據」；追蹤 BACKLOG `DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`。與 §70.13 的 `ui2-browser` pip exit 127（#1171）是**不同事項**。

#### 70.14.3 §70.13 基準更新（2026-11-12；Open PR 清單為時點快照）

- **基準 main**：§70.13 檔頭寫「基準 main `76ed4b7b`」（撰寫時第 1238 行）已過期一個 commit——#1174（DEC-176 登錄與五檔同步）於 2026-11-12T17:02:54Z squash 合併為 main **`85c65dfc`**（head `e589be3b`；GitHub MCP 重讀，FACT）。#1174 為 docs-only，**未改 §70.13 所述 UI2／資料層事實**（§70.13 各條仍沿用，除 §70.14.1 所列勘誤）。main 以 `git fetch origin main` 實查為準，cron 與其他 PR 會推進，一律重查。
- **Open PR（各 PR 最後更新／fetched_at 約 2026-11-12 17:29–17:45Z 的時點快照，讀取時間以 HANDOFF 檔尾 checkpoint 為準；cron 會推進，一律重查）**：#1164（REORG3C 歸檔，Draft，base `7eb48d6c`，head `6fddc582`）；資料 PR #1124（head `3cd3f525`）、#1125（head `cf4739c5`）、#1126（head `1654ae60`）——皆 open、HOLD，base 皆為 main `85c65dfc`。§70.13 HOLD 清單（#1124～#1126、#1164 等）與實況一致，未變。#1124 的 commit 數已由「各 3 個提交」（`DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md` §1 第 1 點約第 21 行、資料 PR 現況表約第 37 行）增為 5（派工訊息所述，本組未重讀 commit 列表）——與資料 PR 隨 cron 持續推進一致（INFERENCE），不構成任何處置授權。
- **出處**：HANDOFF 檔尾「六處差異收尾後最新接手點」；BACKLOG 檔尾「六處差異收尾」段。本節單組撰寫，未經非作者獨立 QA。

### 70.15 DEC-177 後 🗂 資料頁現況與三組守衛連動（2026-11-13；只追加；不改既有節；依據 DEC-177 與其後續註記、`docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md`；非授權；非 QA PASS；單組撰寫，未經非作者獨立 QA）

> 只記**目前有效的事實**；基準 main `093b323d`（#1176 squash，2026-11-13；時點快照）。客戶已裁示「🗂 資料新鮮度總覽＝A 首屏＋B 展開明細」並允許最小 UI 第一版實作（DEC-177），但**不解除任何 Gate**；實作前調查發現須先裁示 7 題（決策單 Q1～Q7），故**尚未有任何 UI／測試變更**。以下 FACT＝作者 2026-11-13 讀碼／複本實測；全稱句只當待驗事項。

- **🗂 資料頁今日仍是固定空殼（FACT）**：`src/services/ui2/data_page.py::data_page_canonical` 為 FAKE／Real 兩軸共用的固定內容，只有 `data_overview` 一個 L1 區塊（3 欄皆 capability `⬜ 尚未提供`）；`src/services/ui2/real_canonical.py::_data()` 不吃 snapshot。第一屏四問與舊區塊文字明寫「資料健康度尚未開放；這裡不顯示任何來源狀態與資料日」。
- **八項固定清單的接入現況＝2／8（FACT；單組盤點，量測日 2026-11-12／13）**：台股加權指數（有資料日＋距今天數，唯一）、市場位階（`as_of=None`；UI2 獨立 session 沙箱恆為 `source=unloaded`，部署端 NOT VERIFIED）；其餘 6 項 UI2 無讀取路徑，接上屬「接線」，受 `I1144-WIRING-GATE`／`DG-SCOPE`／`DG-LIC`／`DG-PIT`（板塊另 `DG-COV`）約束，本批不碰。清單順序以線框 §1.2 為準（線框 §2.4 示意把位階排第 2，為內部不一致，INFERENCE）。
- **三組守衛與連動檔案（FACT；各守衛的放寬都需客戶裁示，見決策單）**：
  1. **帶值欄位白名單**：`tests/test_ui2_real_feed.py` `WIRED_PATHS`（2 頁 5 條路徑，🗂 不在內）；🗂 任何帶 value／source／as_of 的欄位使 19 個測試紅（複本實測）。
  2. **預設收合白名單**：`src/ui2/views/_page.py` `SHOWN_FOLDS`（3 項，🗂 無）；連動 `tests/test_ui2_p3_evidence_preservation.py` `EXPECTED_SHOWN_FOLDS`、`tests/ui2_viewport/measure_viewport.py` `P3_ALLOWED_EXPANDER_TITLES["p4_data"]`；新增 1 條＋1 個 L2 區塊使 21 個測試紅（含 5 個 viewport 證據過期）。
  3. **viewport 證據新鮮度**：`source_hash` 涵蓋 `src/ui2/**/*.py`＋`app_ui2.py`＋`measure_viewport.py`；4 份證據 JSON（`docs/vnext/newui2_realfeed/`、`newui2_batch3b/` 各 2 份）；只改 `src/services/ui2/*` 不觸發（複本實測）。重生需真瀏覽器，本沙箱無 Python Playwright（NOT VERIFIED）。
  4. **P3 證據基準**：`tests/fixtures/ui2_p3_evidence_baseline.json`＋雜湊釘 `tests/test_ui2_active_contract_docs.py` `_P3_BASELINE_SHA256`；改第一屏／舊區塊文案須重生基準（規則：只能擴大、不得縮小）。
  5. **詞彙守衛**：`tests/test_ui2_p1_human_text.py` `ENGINEERING_VOCAB` 含「接線」「尚未接線」；capability 欄位合法字樣僅 `⬜ 尚未提供`（`shared/ui2_contract/text.py`）。
- **五態符號 ✅ ◷ ◇ ⛔（FACT；2026-11-13 更正）**：這組符號**作為「狀態字樣」只存在於文件**（`tones.py` 的 `✅` 是色調晶片符號，另一回事），程式內無別名常數；**但**狀態欄位有守衛——`shared/ui2_contract/models.py` `FieldVM.__post_init__`＋`shared/ui2_contract/text.py` `ALLOWED_STATUS_PREFIXES`：OK 態不得外露狀態字樣（帶 `✅ 正常` 會 raise），STALE／MISSING／UNAVAILABLE 只接受現行全站字樣（`⚠ 過期`／`⬜ 資料未備`…／`🔴 來源目前不可用`），帶 `◷`／`◇`／`⛔` 版本全 raise（作者以 Python 重現）；符號放在純文字 `value_text` 可建立並渲染（複本實測，現有自動檢查全綠）。DEC-128 (a) 寫「僅用於 👤 我的·資料健康度面…不改 `text.py` 與其 guard」，已由 DEC-130 升為 Active，DEC-130 (a) 客戶原文未重述「僅 👤」；用於 🗂 的適用範圍待客戶裁示（決策單 Q4，總管推薦 B＝沿用現行全站字樣；RECOMMENDATION）。本節初稿曾寫「無守衛、不使測試紅」，已更正。
- **基準線（FACT；作者 2026-11-13 於 venv、Streamlit 1.59.2 實跑，會漂移）**：17 個 `tests/test_ui2_*.py` 檔 1705 passed、3 xfailed、41 deselected。
- **仍 HOLD／未授權**：同 DEC-177「仍 HOLD」與 HANDOFF 檔尾。出處：DECISIONS 檔尾「DEC-177 後續註記：實作前調查結果」；BACKLOG 檔尾「2026-11-13｜DEC-177 實作前調查與裁示單提交」；HANDOFF 檔尾最新接手點。本節單組撰寫，未經非作者獨立 QA。

### 70.16 專業 Agent 層現況與權限邊界（2026-11-13；只追加；不改既有節；依據 DEC-178 與 `PROJECT_RULES.md` 第 34 節；非授權；非 QA PASS；單組撰寫，未經非作者獨立 QA）

> 只記**目前有效的事實**；基準 main `63da9515`（#1177 squash，2026-11-13；時點快照）。以下 FACT＝作者本批讀檔／實跑；全稱句只當待驗事項。

- **三個按需專業 Agent 已入庫（本 PR 合併後才算進 main；FACT：檔案存在於本 PR 分支）**：`.claude/agents/stock-data-integrity.md`（資料真實性，唯讀）、`stock-ui-ux.md`（New UI2 五頁／Mobile-first，本定義唯讀；實作由總管另派一般實作 AI 並以其規則為約束）、`stock-independent-qa.md`（非作者獨立 QA，唯讀＋驗證）。角色與 Output 格式只維護於這三檔，**本節與 `PROJECT_RULES.md` 第 34 節不複製其內容**。
- **權限邊界（FACT；靜態）**：frontmatter 只用 `name`、`description`、`tools`、`disallowedTools`（`model` 等省略＝繼承）；三者 `tools` 皆不含 Write／Edit／NotebookEdit／Agent，並於 `disallowedTools` 明列；只有 QA 列 GitHub **讀取類** MCP 工具（pull_request_read、list_pull_requests、get_commit、list_commits、get_file_contents、actions_get、actions_list、get_job_logs、get_check_run、list_branches），不含 merge／update／review 寫入／留言／觸發 workflow 等寫入工具；不設 `permissionMode`。守衛：`tests/test_agent_definitions_guard.py`（欄位白名單、權限、七節標題、目錄只准三檔、突變測試）。
- **Bash 唯讀只是指示性約束（FACT＋限制）**：Claude Code 無法在 agent 層限制特定 Bash 指令，三檔內文以 Forbidden 明文禁止寫檔／git 寫入／`gh`·`curl` 寫入／重跑 workflow，**非機械強制**；settings 層是否強制 NOT VERIFIED（BACKLOG `DEC178-AGENT-BASH-READONLY-ENFORCEMENT`；本批未動 `.claude/settings*`）。
- **Agent 定義不是授權、不是第二份 SSOT**：不解除任何 Gate／HOLD；與 `CLAUDE.md`／`PROJECT_RULES.md` 衝突時以後者為準；「按需」＝挑哪個 Agent，**不改** `CLAUDE.md` §-2「每一次任務都派工」與多組獨立稽核要求。第二批候選（Investment Logic、OneBrain、GitHub Auditor）未建立、未授權。
- **NOT VERIFIED**：三檔在 Claude Code 的實際載入（`/agents`、`/doctor`；須新對話，BACKLOG `DEC178-AGENT-LOAD-VERIFY`）；frontmatter 格式依派工訊息轉述的官方文件（單組，作者未重新查官方文件）；路由規則的實際效果（Quality Batch 3 ⑦）。
- **後續**：品質補強分三批（BACKLOG `DEC178-QUALITY-BATCH-1`～`3`），順序與內容見 DEC-178。出處：`docs/DECISIONS.md` DEC-178；`docs/BACKLOG.md` 檔尾「2026-11-13｜DEC-178 登記」；`docs/HANDOFF.md` 檔尾最新接手點。
