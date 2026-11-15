# Quality Batch 1 ①：六項品質補強「現有覆蓋與真正缺口」稽核 — 2026-11-13

> 📌 **這份文件是什麼、不是什麼（請先讀）**
> - **是稽核紀錄**：DEC-178 Quality Batch 1 工作項 ①（`docs/BACKLOG.md` 的 `DEC178-QUALITY-BATCH-1`），逐項盤點九個工作項（Batch 1～3 的 ①～⑨）是否已有機制，輸出 REUSE／PARTIAL／GAP／BLOCKED／NOT VERIFIED 與證據。
> - **不是授權**：不解除任何 Gate／HOLD（`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`DEC177` Q1～Q7、#1124～#1126、#1164、#1119 全部維持原狀）；不新增資料欄位、來源、接線、API、cron、Secrets；不建議降低任何 CI／QA／Merge Gate。
> - **不是 QA PASS**：本文件為單組撰寫（執行 AI），輸入為五份單組唯讀調查報告，已由撰寫者抽查複驗承重引用（結果見 §4），**尚未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 3／4／6）。§3 的優先序是 **RECOMMENDATION，不是客戶裁示**。
> - **標註規則**：**FACT**＝撰寫者本次讀檔／grep／`gh api` 直接確認；**INFERENCE**＝由事實推論；**INHERITED**＝轉述調查報告、撰寫者未重核（只能當待驗事項）；**NOT VERIFIED**＝未驗證，不得當前提。
> - **基準**：`origin/main` ＝ `5b180ea`（`gh api` 實查仍為此 SHA）；撰寫日 2026-11-13；沙箱未安裝 pytest、未跑任何測試／瀏覽器，**所有「測試 PASS」皆 NOT VERIFIED**，只確認測試檔／符號存在。行號會漂移，本文件一律以可 grep 字串為證。
> - **時點說明（E3／E4）**：以下缺口描述為本 PR ② 落地前（基準 `5b180ea`）；② 已在 PR 範本與 `PROJECT_RULES.md` 第 7 節補入 DoR／Producer→Consumer 入口（②：`.github/PULL_REQUEST_TEMPLATE.md`「需求 ID／核准／Gate／Impact」小節含 Producer→Consumer 與不可變更事項的最小欄位）；⑤ 的完整 PR Impact Check（含重跑測試對應、文件同步）仍屬 Batch 2。各節「GAP／PARTIAL」為落地前基準，不代表 ② 之後的現況。
> - **分類定義**：REUSE＝已有機制可直接引用；PARTIAL＝有機制但不完整或範圍受限；GAP＝repo 內查無對應機制；BLOCKED＝被客戶 Gate／HOLD 擋住，不是技術缺口；NOT VERIFIED＝需實際環境才能判定。

## 1. 九個工作項總表

| # | 工作項（DEC-178） | 分類 | 一句話現況 | 主要證據（路徑＋可 grep 字串） | 後續批次與最小補強候選 |
|---|---|---|---|---|---|
| ① | 現有覆蓋與缺口稽核 | —（本文件） | 本文件即產出 | `docs/vnext/QUALITY_BATCH1_COVERAGE_GAP_AUDIT_2026-11-13.md` | Batch 1；產出後須非作者獨立 QA |
| ② | DoR／DoD 最小補強 | PARTIAL（DoD REUSE／DoR GAP） | DoD 已有（§7）；**repo 沒有任何 DoR 規則**；Preview 完成 vs Production 完成未成為兩層 DoD | `PROJECT_RULES.md` `## 第 7 節｜Definition of Done`；`git grep "Definition of Ready"` 僅命中 `docs/DECISIONS.md`（DEC-178 fence）、`docs/BACKLOG.md`（`DEC178-QUALITY-BATCH-1`）、`docs/HANDOFF.md`（待辦敘述） | **Batch 1 後續產出**：(a) `.github/PULL_REQUEST_TEMPLATE.md` 新增「需求 ID／核准／Gate」小節（緊接 `## Summary` 後）；(b) `PROJECT_RULES.md` §7 末尾 append-only 補註：DoR 與 Preview／Production 兩層完成定義（引用既有 Cutover 合約與 §16.7，不重新定義）；(c) `docs/BACKLOG.md` §0.3 新增更新規則（第 7 條） |
| ③ | New UI2 五頁資料／功能／驗收矩陣 | PARTIAL | 欄位級、功能級、Gate 級 SSOT 已存在且完整度高；矩陣要求的 fetched_at／PIT／currency／Canonical-Shadow 四欄在 UI2 VM 契約中**不存在**，只能標 NOT AVAILABLE | `docs/vnext/NEWUI2_FIVE_PAGE_DATA_CONTRACT_AUDIT_2026-11-12.md`（AUD）、`NEWUI2_CAPMAP_3COL_2026-11-10.md`（`## 2. 三欄對照表（共 100 列）`）、`NEWUI2_MARKET_DATA_CONTRACT_VALIDATION_2026-11-12.md`；`shared/ui2_contract/models.py` `class FreshnessInfo`（僅 `as_of`／`source`） | **Batch 1 後續產出**：`docs/vnext/` 下一份**五頁矩陣索引文件**，只連結 AUD／CAPMAP／MKT／LIC／決策單，**不複製內容、不新增欄位**；缺欄一律 NOT AVAILABLE／NOT VERIFIED |
| ④ | E2E／Golden／Mutation Tests | PARTIAL；Digest 段 BLOCKED | 六段鏈上每段有單元／守衛／部分 golden 與突變測試；**無「來源→LINE／UI」整鏈 E2E**；Digest 在 production 為 0 caller，只能驗契約／離線 | `tests/test_five_bucket_golden.py`、`tests/_fina_mutants.py`（`load_mutant`）、`tests/test_ui2_guards.py`、`tests/test_decision_digest_invariants_guard.py`（`ALLOWED_CALLERS: frozenset = frozenset()`） | Batch 2（見 §2.1） |
| ⑤ | 最小 PR Impact Check | PARTIAL | 五問中 1 問 REUSE、1 問 PARTIAL、3 問 GAP；純文件慣例，**無任何測試／CI 強制 PR 內文** | `.github/PULL_REQUEST_TEMPLATE.md` 七個 `##` 小節；`pr-check.yml` job 名：`Fast checks (pytest unit, ~30s)`、`Slow tests (AppTest, informational)`、`ui2-browser (streamlit …)`、`ui2-browser-gate` | Batch 2（見 §2.2）；注意與 ② 的 PR 範本修改合併規劃，避免兩次改同一檔的小節順序（INFERENCE） |
| ⑥ | Production 健康度五軸 | PARTIAL；軸 4 GAP；部署面 NOT VERIFIED | 五軸各有零散機制，**無單一彙整輸出**；正式部署證據一律 NOT VERIFIED | `shared/staleness.py`、`shared/freshness_policy.py`、`shared/fetch_monitor.py`、`scripts/verify_data_branch.py`、`.github/workflows/*.yml`（19 檔） | Batch 2（見 §2.3）；只讀既有證據，不新增 API／cron／Secrets |
| ⑦ | Agent 路由整合 | PARTIAL；行為 NOT VERIFIED | 靜態規範（三定義＋§34 路由表＋守衛測試）齊備；自動選擇、實際載入、獨立性稽核紀錄皆未驗證 | `.claude/agents/stock-{data-integrity,ui-ux,independent-qa}.md`；`PROJECT_RULES.md` `## 第 34 節｜專業 Agent 路由`；`tests/test_agent_definitions_guard.py`（`TestMutationTeeth`、`REGISTERED_AGENTS`） | Batch 3（見 §2.4） |
| ⑧ | Token 與返工基準 | GAP | repo 內**無 LLM Token 量測機制**（無腳本／workflow／結構化紀錄）；僅有一份總管轉述的單次樣本（`docs/HANDOFF.md`「量測結果」小節），方法與數值可見但未獨立複驗，不得當基準；另有自標估算 | `docs/HANDOFF.md` 內 `Q5 相關 Token 量測為單次樣本，不得當統計結論`；`docs/BACKLOG.md` `REORG3C-Q5-GATE`（blocked-on-customer） | Batch 3；Claude Code 能否取得 Token 本身 NOT VERIFIED，須先在實際環境確認（見 §2.4） |
| ⑨ | 零記憶接手測試 | PARTIAL（機制 REUSE／實測 GAP） | 接手提示語、預防性交接、零聊天恢復驗收定義都已寫成規則；**從未執行過一次零記憶實測** | `PROJECT_RULES.md` `### 22.4 接手提示語的定位與建議骨架`、`## 第 33 節｜預防性交接制度`；`docs/HANDOFF.md` `### 新對話接手提示語` | Batch 3；併入 `DEC178-AGENT-LOAD-VERIFY` |

## 2. 逐項細表

### 2.0 ② DoR／DoD 九項需求比對

> 本表為 ② 落地**前**（基準 `5b180ea`）的比對；② 已在 PR 範本新增「需求 ID／核准／Gate／Impact」小節（含 Producer→Consumer、不可變更事項、適用 Gate 的最小欄位）並在 `PROJECT_RULES.md` 第 7 節 2026-11-13 補註定義 DoR 與 Preview／Production 兩層完成。下表「缺口」欄為落地前描述。

| 需求項 | 分類 | 現有機制（可 grep 字串） | 缺口 |
|---|---|---|---|
| 需求／規格 ID | PARTIAL | DEC-NNN、BACKLOG `ID` 欄（`docs/BACKLOG.md` §0.1 表頭 `ID｜標題｜sev／pri｜status｜evidence｜affected area｜dependency｜customer decision｜source／PR｜next action｜驗證組數`） | PR 範本不要求填；六問的 `Which contract?` 只限 UI2 主線（`NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` `## §1 每批 PR 驗收六問`） |
| 正式核准狀態 | PARTIAL | DEC `狀態` 欄；BACKLOG `status`＋`customer decision` 欄；`PROJECT_RULES.md` §15 第 5 點「尚未核准的構想一律進 BACKLOG 的 Candidate／Decision Gate，⛔ 禁止升格成 Approved」 | PR 描述無「核准依據」欄 |
| 影響範圍 | PARTIAL | BACKLOG `affected area` 欄 | PR 範本僅 `## 風險評估`（LOW／MED／HIGH），無影響範圍 |
| 資料依賴 | PARTIAL | BACKLOG `dependency` 欄；`docs/governance/OLD_UI_FIRST_ADAPTATION_GATE_2026-11-08.md` 的 `最小 Evidence Matrix`（欄位・單位・日期・PIT・freshness） | 僅新頁面／重大功能啟動時用，一般 PR 無 |
| Producer／Consumer | GAP | `git grep "Producer" PROJECT_RULES.md` ＝ 0 命中；Consumer 僅出現在 `.claude/agents/stock-data-integrity.md`（Consumer 追溯）與 §34 路由表任務特徵 | 無「PR 須列」要求；⑤ 的 Producer·Consumer 問題同源 |
| 不可變更事項 | PARTIAL | `PROJECT_RULES.md` `## 第 4 節｜Stop／Decision Gate`；六問 `What did NOT change?`（僅 UI2） | PR 範本無對應欄 |
| 必要 Gate | PARTIAL | Stop Gate；PR 範本 `## Visual Fidelity Gate`（僅 UI PR）；`PROJECT_RULES.md` `### 16.7 Production 安全狀態` | 範本無「適用 Gate」欄；DG-*／I1144-WIRING-GATE 只在 BACKLOG／DEC |
| 可驗證驗收案例 | PARTIAL | PR 範本 `## Test plan`（僅「pytest 全綠」類 checkbox）；六問 `What tests?` | 無「驗收案例對應規格 ID」要求 |
| Preview 完成 vs Production 完成 | PARTIAL | `NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`「capability marker 是 Preview-only」；`shared/risk_cap_history_policy.py` `PRODUCTION_WRITE_APPROVED: bool = False`；`NEWUI2_CUTOVER_GAP_MATRIX_2026-11-10.md` §1.1（C1～C7 無一「已滿足」，INHERITED） | §7 DoD 沒有兩層定義；風險＝把 FAKE／REAL shadow Preview 完成說成正式完成 |

可直接 REUSE（不重做）：DoD §7、Old UI First §1／§4、六問、Cutover 合約、BACKLOG §0.1／§0.3、DEC 格式、§4 Stop Gate、§23 優先級。
**CI 不會擋 PR 範本／BACKLOG 欄位變更（FACT）**：`git grep PULL_REQUEST_TEMPLATE -- '*.py' '*.yml'` ＝ 0；`.github/workflows` 無 `pull_request.body` 檢查。→ 欄位純屬文件慣例，改範本不會令測試紅，**同時也代表加了欄位不會被機械強制**（INFERENCE）。
**治理文件改動須走 PR 與獨立稽核**：`PROCESS.md` §4 `取代註記 D1`（2026-11-12：一律走 PR）；`CLAUDE.md` §-2 規則 4。

### 2.1 ④ 鏈上六段測試（均 FACT：測試檔存在；PASS 一律 NOT VERIFIED）

| 段 | 既有測試（類型） | 固定 fixture | 缺口候選 | 分類 |
|---|---|---|---|---|
| 資料來源／fetch | `tests/test_pr_n2_data_fetchers.py`、`test_pr_n3_*`、`test_d3_fetch_outcome.py`、`test_fetch_monitor.py`（單元＋突變殺手） | monkeypatch／假 requests | 無「真實來源回應快照」golden；來源改版（欄位／單位）只靠個別守衛 | PARTIAL |
| 正規化／schema | `tests/test_schemas.py`、`test_b3_margin_schema.py`、`test_twii_ohlc_revert_chain.py`（拔修正轉紅）、`tests/_fina_mutants.py` | 內嵌合成；`tests/fixtures/` 僅 `twse_holiday_schedule_115_synthetic.json`、`z43_label_official_codes.json`、`ui2_p3_evidence_baseline.json`、`secret_scrub_*.py` | 跨來源單位／幣別統一 golden | PARTIAL |
| 選股／決策 | `tests/test_five_bucket_golden.py`（16 燈 golden）、`test_push_action_consistency.py`、`test_fina_both_legs_required.py`（突變） | 合成；golden 自帶 | 對固定輸入的整體 Top-N 排序 golden 未見（INHERITED） | PARTIAL |
| Digest | `tests/test_decision_digest_*`（契約／建構／驗證／不變性） | factory 合成 | `decision_digest_builder` 在 `src` 內無 production caller（僅 `src/services/decision_digest_assembly.py` 等 digest 家族自身 import）；測試端除 digest 家族測試外，另有 `tests/test_strategy_class_schema.py`、`tests/test_ui2_p3_evidence_preservation.py` import；`ALLOWED_CALLERS` 為空（FACT，親驗 grep）→ 只能驗契約／離線，**不得稱正式 E2E** | PARTIAL；E2E BLOCKED（Stage F Gate） |
| UI2 | `tests/test_ui2_guards.py`、`test_ui2_real_feed.py`（`WIRED_PATHS`）、`test_ui2_contract_teeth_pending.py`、`test_ui2_registration_and_boot.py`、瀏覽器 lane `test_ui2_drawer_browser.py`＋`test_ui2_batch2.py`（CI 強制 0 skip、≥40 tests） | real_feed 用 git 追蹤 parquet | 瀏覽器 lane 僅兩檔；REAL 軸只有三個 reader；🗂 資料頁為空殼；有 `tests/test_ui2_drawer_browser.py::test_data_page_is_honest_not_wired_shell`（`ui2_browser` marker，預設 pytest 不跑），僅驗誠實空殼，無新鮮度內容驗收（FACT；詳 §4.2-7） | PARTIAL |
| LINE push | `tests/test_daily_signal_push.py`、`test_push_holdings_daily.py`、`test_push_weekly_report.py`、`test_holdings_digest_message.py` | 合成 | `scripts/push_*.py` orchestrator 無端到端離線測試（`test_daily_signal_push.py` 自宣告 orchestrator 為薄 glue 不重測，INHERITED）；推播不經 Digest | PARTIAL |

測試規模（FACT，grep 計數）：`tests/*.py` ＝ 711 檔。**已知非決定性紅燈**：`tests/test_d6_diagnostic_no_secret_display.py`，已登記 `DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`（BACKLOG 載有兩組調查的機制推論：元素 ID 每行程隨機、片段偶然命中禁字；本文件**未重跑、未驗證該機制**，根因 NOT VERIFIED；修復為另批提案，客戶未授權前不動，見 BACKLOG `DEC178-QUALITY-BATCH-2` 行末）。

### 2.2 ⑤ PR Impact Check 五問比對

> 本表為 ② 落地**前**（基準 `5b180ea`）的比對。② 已含 Producer→Consumer 與不可變更事項的最小欄位（PR 範本新小節）；**⑤ 完整 Impact Check 與「哪些測試應重跑」對應、正式文件同步仍屬 Batch 2**，下表第 2、4 列的 GAP 為落地前描述。

| 五問 | 現況（FACT） | 分類 |
|---|---|---|
| 改了什麼 | `## Summary`、`## §-1 工作準則對齊` | REUSE |
| 影響哪些 Producer·Consumer | 無此問；`## SSOT / §8.2 / §3.3 影響` 只問新增 SSOT 常數／例外／magic number | GAP |
| 哪些測試應重跑 | `## Test plan` 問「跑了什麼」；CI 無依影響範圍的路徑對應（pr-check 無 paths 過濾邏輯＝INFERENCE，未逐行讀） | PARTIAL |
| 哪些契約不可變更 | 無此問（契約散在 CLAUDE.md／PROJECT_RULES／tests） | GAP |
| 哪些正式文件引用需同步 | 無此問；`PROJECT_RULES.md` §27 永久收尾 Gate 管批次收尾，非 PR 欄位 | GAP |

**branch protection／required checks：NOT VERIFIED**。`pr-check.yml` 註解自陳：`ui2-browser-gate` 才是建議的 required check，「未設定前 required 不生效（本 repo AI 工作階段無權限讀寫該設定）」。

### 2.3 ⑥ Production 健康度五軸

| 軸 | 既有機制 | 可複驗證據來源 | 分類／NOT VERIFIED |
|---|---|---|---|
| (1) CI | `pr-check.yml` 四個 job；同 head SHA 的 check runs | GitHub Actions（唯讀 API） | REUSE；required 設定 NOT VERIFIED |
| (2) 資料是否更新 | 排程 workflow 19 檔（例：`update_macro_history.yml` `cron: '0 9 * * *'`、`update_sector_flow.yml` `'30 9 * * *'`、`export_db.yml` `"0 21 * * *"`）；`scripts/verify_data_branch.py`；`data_cache/metadata.json` | 見下方資料日表 | PARTIAL；各 cron 近期是否成功 NOT VERIFIED |
| (3) 資料是否有效 | `shared/{staleness,freshness_policy,data_freshness,fetch_monitor,fetch_outcome,vix_validity,twii_ohlc_contract,margin_schema,schemas}.py` | 純函式＋測試 | PARTIAL（分散，無單一彙總） |
| (4) 正式 UI 是否接線 | 正式預設仍是 `app.py`（`git grep -c ui2 app.py` ＝ 0；`test_production_app_does_not_reference_ui2`）；UI2 為 `app_ui2.py` Preview；🗂 頁 `R_DATA_NOT_WIRED`＝「資料健康度尚未開放…」；`git grep freshness_overview -- src shared app_ui2.py` ＝ 0 | 文件＋測試可複驗「未接線」 | GAP（UI2）；Streamlit Cloud 部署實況 NOT VERIFIED |
| (5) 決策與通知可用 | `src/data/notify/{line_notify,dispatch}.py`；`push_holdings_daily.yml`（`30 22 * * 0-4`）、`push_weekly_report.yml`（`0 21 * * 0`）、`push_watchlist_signals.yml`（`--health-check`＝`format_quiet_health_check`，本組已確認的推播存活心跳（未窮舉））；`push_daily_signals.yml` 已**停自動推**（僅 `workflow_dispatch`） | 程式／測試可驗契約 | PARTIAL；Digest 路徑 BLOCKED；實際送達、Secrets 有效性 NOT VERIFIED |

`data_cache/metadata.json` 實值（FACT，main `5b180ea`）：`twii_ohlcv` 2026-11-09（4913 列）、`finmind_inst` 2026-11-09、`finmind_margin` 2026-11-09、`finmind_m1m2` 2026-09-01（`NO_NEW_DATA`）、`tw_pmi` 2026-10-01（`UNDETERMINED`）。**跨軸缺口（FACT）**：repo 內無把五軸分開、逐軸附證據的 production health 文件或腳本。

### 2.4 ⑦⑧⑨

| 項 | 面向 | 分類 | 證據／現況 |
|---|---|---|---|
| ⑦ | 三 Agent 定義與路由表 | REUSE | `.claude/agents/` 恰三檔；`.claude/settings*` 不存在；§34 路由表 5 列（資料／UI／QA／不派 Agent 的 Stop Gate 類／跨類由總管拆分） |
| ⑦ | 跨領域邊界、QA 獨立性 | PARTIAL | 僅文字規範（§34 第 3、4 點；QA 定義 Forbidden）；無機械強制、無「誰是作者／QA」稽核紀錄；跨類任務僅寫「總管拆分」無準則；UI 實作用的一般實作 AI 無定義檔 |
| ⑦ | 守衛測試 | PARTIAL | `tests/test_agent_definitions_guard.py` 守結構與 frontmatter 白名單（`ALLOWED_FIELDS`）；不守 Forbidden 內文被刪、實際載入、路由行為（INHERITED，BACKLOG E3） |
| ⑦ | 實際載入／自動路由／`/agents`／`/doctor` | NOT VERIFIED | BACKLOG `DEC178-AGENT-LOAD-VERIFY`：僅「單次觀察」（harness 列出三 Agent），**不等於載入驗證完成** |
| ⑦ | Bash 唯讀 | GAP | §34 第 7 點 (a)；BACKLOG `DEC178-AGENT-BASH-READONLY-ENFORCEMENT`（需客戶裁示）；僅指示性約束 |
| ⑧ | Token 量測機制 | GAP | `git grep -E "input_tokens\|total_tokens\|cost_usd"` 無 LLM 用量命中（`cache_read` 子字串僅命中 `macro_cache_reader`／`upstream_state` 的無關文字，非用量）；workflow／scripts 皆無量測 |
| ⑧ | 已實測／估算／返工紀錄 | GAP／PARTIAL | `docs/HANDOFF.md`「量測結果（總管轉述；harness `subagent_tokens` 單次樣本…）」小節有一份總管轉述的單次樣本（方法與數值可見；限制自述「單次樣本、無對照重複、讀取策略不同」），**未獨立複驗，不得當基準**（FACT：親讀該小節；數值正確性 NOT VERIFIED）；各 wireframe／契約文件中的 Token 為自標估算（INHERITED）；PR 返工次數、QA 輪次、重複讀取次數無結構化紀錄 |
| ⑧ | Claude Code 能否取得 Token | NOT VERIFIED | repo 內無依據；`PROJECT_RULES.md` §33 第 5 點明文「不承諾能準確讀取剩餘上下文 Token」；須實際環境實測 |
| ⑧ | 與 Q5 的關係 | BLOCKED | `REORG3C-Q5-GATE`（P2、blocked-on-customer）；⑧ 是證據來源候選，**不構成 Q5 重議**；單次樣本不可當基準 |
| ⑨ | 接手機制與驗收定義 | REUSE／PARTIAL | §22.4、§32 第 6／8 點、§33；HANDOFF 提示語；驗收標準是文字規則，不是實測紀錄 |
| ⑨ | 零記憶實測紀錄 | GAP | `零記憶` 僅出現於規劃與提示語；五個檢查點全未實測 |
| ⑨ | HANDOFF 時點快照風險 | PARTIAL（已知瑕疵） | HANDOFF 為多段追加，需以最末段為準（`### 📌 狀態更新（2026-11-13…` 與 `### 📌 存檔完整性補註`）；二者自述單組、未經非作者 QA；更早段落含過期描述未改 |
| ⑨ | 獨立 QA 結案 | BLOCKED | `DEC174-B1-INDEP-QA`（需客戶指派）；#1169 複驗為單組產出，新對話易誤當獨立 QA 已完成 |

### 2.5 ③ 矩陣欄位對既有 SSOT 的覆蓋

| 矩陣要求欄 | 既有 SSOT | 分類 |
|---|---|---|
| source／schema／unit | AUD §2.1～2.5（M-／T-／H-／U-／D- 逐欄）、MKT | REUSE |
| as_of／freshness／missing reason | AUD、`FreshnessInfo.as_of`、`shared/upstream_state.py`；市場位階無 as_of（畫面 `⬜ 資料日未提供`，INHERITED） | PARTIAL |
| fetched_at | UI2 VM 契約無此欄；儲存層有（`finmind_inst`／`tw_pmi`，INHERITED）；`twii_ohlc_contract` 消費 fetched_at 判日 K 是否收盤（`real_canonical` 內 `FETCHED_AT_MISSING`） | NOT AVAILABLE（VM 契約層） |
| PIT | AUD §4／§6、`DG-PIT`（HOLD）；VM 契約無此欄 | NOT AVAILABLE（契約層）；BLOCKED（Gate） |
| currency | `git grep -iE "currency\|幣別" -- src/services/ui2 shared/ui2_contract src/ui2` ＝ 0 命中 | NOT AVAILABLE |
| Canonical／Shadow | 無「每 Dataset」屬性；唯一用語為 `pages.py` 的 `Real＝唯讀 real-data shadow（非 production default）` | NOT AVAILABLE（屬性層）；feed 層可由 `real_feed` 三 reader 判定 |
| Consumer | AUD、CAPMAP；UI2 實際消費僅 `_read_twii`／`_read_twii_kbar`／`_read_regime`（FACT） | REUSE |
| 授權狀態 | `PUBLIC_DATA_EXPOSURE_LICENSE_ARCH_AUDIT_2026-11-11.md` §2；全部非 license-verified（INHERITED） | BLOCKED（`DG-LIC`） |

若客戶要把 fetched_at／PIT／currency／Canonical-Shadow 變成**正式契約欄位**，屬新設計決策，需 Data Contract Gate（INFERENCE：撰寫者不建議由矩陣代為新增）。

## 3. 缺口優先序建議（RECOMMENDATION，非裁示；不改變任何 Gate）

| 優先 | 缺口 | 歸屬 | 說明 |
|---|---|---|---|
| 1 | DoR 缺失、PR 範本缺「需求 ID／核准／Gate」 | Batch 1 ②（本批後續） | 純文件、一次一檔；PR 範本→PROJECT_RULES §7→BACKLOG §0.3 依序 |
| 2 | 五頁矩陣索引 | Batch 1 ③（本批後續） | 只連結 SSOT；四欄 NOT AVAILABLE 如實標明 |
| 3 | PR Impact Check 三個 GAP（Producer·Consumer／契約不可變更／文件同步） | Batch 2 ⑤ | 在 ② 的範本小節基礎上延伸，不另建報告。（② 落地後：Producer→Consumer 與不可變更事項已有最小欄位；Batch 2 補完整 Impact Check、重跑測試對應與文件同步） |
| 4 | 鏈上整鏈與 golden 缺口（真實來源快照、Top-N 排序、push orchestrator 離線測試） | Batch 2 ④ | 只補離線 fixture／契約；Digest 段不稱正式 E2E；不放寬 PIT、Risk Cap、門檻 |
| 5 | 五軸彙整（逐軸附證據的唯讀彙總） | Batch 2 ⑥ | 軸 4 對 UI2 的結論是「未接線」，非缺陷；部署端 NOT VERIFIED |
| 6 | Agent 行為實測、零記憶實測、Token 可取得性確認 | Batch 3 ⑦⑧⑨ | 前置為 Batch 2 合併；須新對話與實際環境 |
| BLOCKED | 外資 L3、融資／板塊接線（D6～D8）、🗂 新鮮度總覽、Digest 正式 E2E、Q5 重議、#1124～#1126 處置、`DEC174-B1-INDEP-QA`、Bash 唯讀強制 | 客戶 Gate | 只引 ID：`I1144-WIRING-GATE`、`DG-SCOPE`／`DG-COV`／`DG-PIT`／`DG-LIC`、DEC-177 Q1～Q7（`DEC177-FRESHNESS-IMPL-DECISION-SHEET`）、`REORG3C-Q5-GATE`、`DEC174-B1-INDEP-QA`、`DEC178-AGENT-BASH-READONLY-ENFORCEMENT`；本批不解除 |
| 不在六項內 | D6 非決定性紅燈修復 | 另批提案 | `DEC176-CI-D6-NOSECRET-ID-NONDETERMINISM`；客戶未授權修測試前不動 |

## 4. 報告與親驗不一致、已知矛盾

### 4.1 撰寫者親驗摘要（FACT）

共親驗 **約 40 項**，要點：PR 範本七個 `##` 小節；`PROJECT_RULES.md` §4／7／15／16.7／22.4／23／24／27／32／33／34 位置；BACKLOG §0.1 表頭與 §0.3 規則 6；`pr-check.yml` 四 job 名、`ui2-browser-gate`、「AI 無權限」註解、瀏覽器 lane 兩檔與 `tests < 40`／`skipped > 0` 強制；`pytest.ini` 的 `ui2_browser` marker 與 `addopts`；`.claude/agents/` 三檔且無 `settings*`；17 個關鍵測試檔存在；`tests/*.py` 711；`real_feed.py` 三 reader；`_FEED_LABELS`、`REAL_PREVIEW_BANNER_NOTE`；`app.py` 的 ui2 引用 0；`R_DATA_NOT_WIRED`；`freshness_overview` 於 src／shared 0 命中；Active Contract `## §2 四頁正式 Human UI` 與守衛斷言；`test_only_five_pages`、`test_nav_has_exactly_the_five_pages`；`G2F_IMPORT_ALLOWLIST`、`WIRED_PATHS`、`SHOWN_FOLDS`；`margin_fact_service`／`sector_flow_fact_service` 無 UI2 consumer；`metadata.json` 五個 dataset 值；`ALLOWED_CALLERS` 為空且 `decision_digest_builder` 在 `src` 內無 production caller（測試端另有 `test_strategy_class_schema.py`、`test_ui2_p3_evidence_preservation.py` import）；Token 關鍵字 grep；HANDOFF 單次樣本字句；`REORG3C-Q5-GATE`、`DEC178-AGENT-*`、`DEC174-B1-INDEP-QA`、D6 BACKLOG 列；15 份被引用的 vnext／governance 文件皆存在；多個 cron 字串；`PRODUCTION_WRITE_APPROVED`＝False；`PROCESS.md` §4 `取代註記 D1`；`gh api` 取得 #1124～#1126 與 main SHA；`git diff --stat 7eb48d6c HEAD`。

### 4.2 報告與親驗不一致（以親驗為準）

| # | 報告說法 | 親驗結果 | 影響 |
|---|---|---|---|
| 1 | R1：`PULL_REQUEST_TEMPLATE\|pull_request.body\|pr_body` 於 `*.py`／`*.yml` 全 repo 0 命中 | `PULL_REQUEST_TEMPLATE` 單獨 0 命中；但 `pr_body` 命中 `scripts/publish_data_pr.py`（`build_pr_body`）與三個測試檔——那是**資料發布 PR 的內文產生器**，不是檢查 PR 範本 | 結論（無任何機制強制 PR 範本欄位）不變；字面 grep 描述不精確 |
| 2 | R3：`cache_read` 等 Token 關鍵字「零命中」 | `cache_read` 為子字串，命中 `macro_cache_reader`／`upstream_state` 的無關文字；LLM 用量類關鍵字確為 0 | 結論不變 |
| 3 | R2：「`PROJECT_STATE.md` 寫 Digest builder 0 production caller」 | 路徑是 `docs/PROJECT_STATE.md`（根目錄無此檔）；另有守衛測試 `ALLOWED_CALLERS` 為空可獨立佐證 | 路徑更正 |
| 4 | R2／R3：把 `push_daily_signals.yml` 列為排程推播之一 | 該 workflow 已停自動推，僅 `workflow_dispatch`（檔內註解「停自動推，保留 workflow_dispatch」） | ⑥ 軸 5 的排程推播應不含它 |
| 5 | R4：「UI2 VM 契約沒有 fetched_at」 | VM 契約 `FreshnessInfo` 確只有 `as_of`／`source`；但 `real_canonical` 內有 `FETCHED_AT_MISSING`（日 K 收盤完成判定消費 fetched_at） | 精確說法：**VM 契約欄位不存在，但日 K 契約檢查會用到儲存層 fetched_at** |
| 6 | R1：PROCESS.md 的取代註記為 D1 | `PROCESS.md` 有 D1（§4，直推例外取代）與 D2（§1，開頭附近）兩則；R1 所指「一律走 PR」的是 D1，無誤 | 無影響（備註） |
| 7 | 稽核初稿（INHERITED 調查）：🗂 資料頁「無專屬測試」 | 存在 `tests/test_ui2_drawer_browser.py::test_data_page_is_honest_not_wired_shell`（`ui2_browser` marker，預設 pytest 不跑）；僅驗誠實空殼，無新鮮度內容驗收 | 更正為「無預設 pytest 道的專屬測試；瀏覽器道有一支誠實空殼測試」，與矩陣 F17 一致 |
| 8 | 稽核初稿：repo 內無任何 Token 量測樣本 | `docs/HANDOFF.md`「量測結果」小節有總管轉述的單次樣本（親讀） | §1／§2.4／§5#11 已更正：有轉述樣本、未獨立複驗、不得當基準 |

### 4.3 已知矛盾（只記錄，不建議放寬任何守衛）

| # | 矛盾 | 證據 | 標註 |
|---|---|---|---|
| K1 | **UI2 Active Contract 正文「四頁，不得新增第五頁」vs 現行五頁**（DEC-135 頂部註記只鬆綁頁數上限；DEC-142／146 實際五頁） | `NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` `## §2 四頁正式 Human UI 與每頁優先順序`；`tests/test_ui2_guards.py::test_only_five_pages` | FACT |
| K2 | **守衛測試釘住舊標題**：`tests/test_ui2_active_contract_docs.py` 斷言 `"## §2 四頁正式 Human UI"`、`"## §5 👤 我的 → 資料健康度"` | 同檔 | FACT；INFERENCE：改 Active Contract 標題會令該守衛轉紅，任何「修正文」須同步調整測試，屬守衛調整、需客戶裁示。**本文件不建議放寬守衛，也不動這兩份檔** |
| K3 | 資料健康度落點：DEC-128／Active §5＝👤 我的；DEC-142／146＝🗂 資料 | `NEWUI2_CUTOVER_GAP_MATRIX_2026-11-10.md` 「資料健康度的最終落點」（該檔自述不裁決） | FACT。**DEC-177 fence 已表態**：完整資料健康度仍保留在 👤 我的既有契約位置；🗂 本批只處理新鮮度摘要，不搬移入口（`docs/DECISIONS.md` DEC-177 fence；客戶訊息轉錄，逐字一致性 NOT VERIFIED）；`DEC176-HEALTH-ESCALATION-1` 是否結案由總管判定，本文件不裁決 |
| K4 | Real feed 事實數文案漂移：`_FEED_LABELS`「只接 2 項真資料」、`REAL_PREVIEW_BANNER_NOTE`「僅台股與市場位階為真資料」vs 實際 3 reader（位階恆未載入，INHERITED） | `src/ui2/shell/app.py`、`shared/ui2_contract/text.py` | FACT（文案）；AUD §7.3 已登記，未改 |
| K5 | AUD 的 PR 證據已過期：#1124～#1126 於 `gh api` 實查仍為 `open`、`merged=false`；head 已前進為 `3cd3f525`／`cf4739c5`／`1654ae60`，base `85c65dfc`；AUD 記載 head `fc447def`、base `043a4d21` | `gh api repos/…/pulls/{1124,1125,1126}`（唯讀）；AUD 內 `fc447def`、`043a4d21` 字樣仍存在 | FACT。分支上實際資料日（INHERITED：finmind 到 2026-11-12、`twii_ohlcv` 到 11-11）本文件未重核；main 上 `metadata.json` 仍為 2026-11-09 與 AUD 一致（FACT）。**只記錄，不碰這三個 PR** |
| K6 | 程式與資料自 AUD 基準 `7eb48d6c` 以來未變（僅 `pr-check.yml`、`tests/test_agent_definitions_guard.py` 有 diff） | `git diff --stat 7eb48d6c HEAD -- src shared app.py app_ui2.py data_cache tests scripts .github` | FACT：AUD 對 src／shared／data_cache 的斷言在 `5b180ea` 仍適用 |
| K7 | 台股卡固定字樣「每日更新」與資料停在 2026-11-09 並存 | `market_twii_view_service.TWII_SOURCE_TEXT`（INHERITED）＋ `metadata.json`（FACT） | INFERENCE：因果推論為每日資料 PR 未併入（非 cron 失敗）；未驗證 |
| K8 | AUD 引用的「1705 passed、82／82 viewport」為調查者自報、非本次執行，不可當 Production 驗收證據 | AUD §0 | INHERITED |

## 5. NOT VERIFIED 清單

| # | 項目 | 為何未驗 |
|---|---|---|
| 1 | `/agents`、`/doctor` 輸出、三 Agent 是否被實際載入、自動委派是否選對專家、Write／Edit 是否實際不可用 | 需 Claude Code 實際環境；`DEC178-AGENT-LOAD-VERIFY` |
| 2 | description 常駐 Token 成本；Claude Code 是否可匯出每任務 Token | 無量測、repo 無依據 |
| 3 | Streamlit Cloud 部署實況（正式 UI 是否真正接線、位階實值、`macro_state.json` 是否存在） | 沙箱無法存取 |
| 4 | GitHub branch protection／required checks（`ui2-browser-gate` 是否 required） | `pr-check.yml` 自陳 AI 無權限讀寫 |
| 5 | 各 cron 近期執行成功與否、LINE／Telegram 實際送達、Secrets 有效性 | 未查 Actions 紀錄、無收訊證據 |
| 6 | D6 非決定性紅燈根因（BACKLOG 的元素 ID 隨機機制僅為轉述） | 未重跑該測試檔 |
| 7 | 所有 pytest／AppTest／Playwright／viewport 的 PASS | 本沙箱未安裝 pytest，未執行 |
| 8 | AUD／CAPMAP／MKT／LIC 內部各列的正確性（本文件僅確認檔案存在與少數引用） | 單組稽核文件，需非作者複核（`DEC174-B1-INDEP-QA`） |
| 9 | 授權狀態（FinMind／TWSE／TPEX／Yahoo／FRED／MOPS／data.gov.tw／CBC；其中 FRED **不在** LIC §2 來源授權矩陣表內，無任何授權判定可引）、parquet 內容（沙箱無 pyarrow，AUD 的來源斷點、volume 稀疏度為轉述） | 外部條款原文、無法讀 parquet |
| 10 | #1124～#1126 分支上的實際資料日與 PIT | 本文件僅讀 PR 狀態，未讀分支內容 |
| 11 | HANDOFF 內「Q5 相關 Token 量測」單次樣本的正確性 | repo 內有一份總管轉述的單次樣本（HANDOFF「量測結果」小節；方法與數值可見），但未獨立複驗、無原始 harness 輸出，不得當基準 |
| 12 | 客戶 2026-11-13 原始訊息與 DEC-178 fence 的逐字一致性 | 原始對話不在 repo |

## 6. Batch 2 更正（2026-11-13 追加；原文 §0～§5 不改，以本節為準）

> 兩點更正均為單組（執行 AI）重取後的結論，尚未經非作者 QA；不解除任何 Gate／HOLD。證據：`tests/test_push_holdings_daily.py`（`grep -n "P.main(" ` 命中 10 處）、`tests/test_push_weekly_report_main.py`、`origin/main:.github/workflows/push_*.yml` 的 `on:` 區塊、`docs/vnext/PRODUCTION_HEALTH_FIVE_AXIS_SNAPSHOT_2026-11-13.md`。

| # | 原文位置 | 原說法 | 更正 |
|---|---|---|---|
| 1 | §2.1 LINE push 列 | 「`scripts/push_*` orchestrator 無端到端離線測試」 | **不精確**：`tests/test_push_holdings_daily.py` 已有多支 `P.main([...])` 離線測試。**缺口之一（weekly 已補）**：`push_weekly_report.main`（當時 `tests/test_push_weekly_report.py` 無 `main(` 呼叫），已由 `tests/test_push_weekly_report_main.py` 補上（Batch 2 ④；為離線契約測試，非 Production E2E，不證明 LINE 送達）。該檔位於 Batch 2 分支，是否已併入 main 以該 PR 為準。**另：`push_daily_signals`／`push_watchlist_signals` 的 `main()` 亦無離線測試**（`git grep` 親驗：`tests/` 內僅 `tests/test_daily_signal_push.py` 測 `push_daily_signals` 的 `_maybe_ai_judgment` 等輔助函式、無任何 `main(` 呼叫；`push_watchlist_signals` 在 `tests/` 僅出現於 workflow 檔名檢查與分層守衛）；目前僅 workflow_dispatch 手動觸發，風險較低，登記為備選，不在本批。 |
| 2 | §2.3 軸 5 列 | 「`push_watchlist_signals.yml`（`--health-check`）為存活心跳」 | **與 workflow 現況不符**：`push_watchlist_signals.yml`、`push_daily_signals.yml` 的 `on:` 只剩 `workflow_dispatch`（排程已停，註解 user 2026-08-23）；**仍排程者為 `push_weekly_report`（`0 21 * * 0`）與 `push_holdings_daily`（`30 22 * * 0-4`）**。`--health-check` 參數仍在腳本中，但目前無排程中的心跳。 |
