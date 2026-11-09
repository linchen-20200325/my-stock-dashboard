# 資料血緣限定範圍取證（2026-11-05）

> **狀態：靜態取證／待獨立 QA 與本次 head 的 CI；不是完整血緣圖、不是死碼證明。**
> 依本次客戶授權，ChatGPT 處理資料重構與清碼；Claude Code 的 New UI2 工作優先。本批最多三項：#1025 工具修復、兩支資料鏈索引、交接 checkpoint。未刪碼、未搬移資料、未新增來源、未修改 production／Old UI／公式／Risk Cap／OneBrain／workflow。
> 原碼基準：main `481ae083f5276d003882d1e0954e501809aa3aa4`；#1025 原 head `a08def39ab8598ec15d1b88e44807beea0aa2806`；#1026 head `6f755d9962063e710189f7ee6b74f70cd26e01c0`。合併與 CI 現況必須重查 GitHub，這些 SHA 不代表之後的最新 main。

## 1. 三句 Plan 與選案

1. 先修 #1025 的 prefix 漏列，保留原 AST records schema，新增 CLI 回歸，不把靜態符號候選當已解析模組。
2. 以既有工具與限定範圍原碼搜尋，分別列出 runtime registry 與 UI2 Real feed 的入口、讀寫、欄位與未驗項；不把兩者誤接成同一 pipeline。
3. 將發現、限制與下一步保存於本專屬報告；共享交接三檔因 Claude 分支同檔差異退讓，未同步，完整 Stage 尚未完成。

| 方案 | 正確性／語意風險 | 速度 | Token／模型成本 | 修改／回歸範圍 | 可逆性 | 沿用 | 失敗降級 |
|---|---|---|---|---|---|---|---|
| **A：修既有 selector＋rg 補充＋限定索引（採用）** | 低；明示 static-only／符號歧義 | 最快 | 最低；一般工具／文件批 | 既有工具、測試與 docs | 高 | #1025 與現有契約 | 未解析項記 UNKNOWN，停在唯讀 |
| B：新增完整 graph resolver | 動態 import／re-export／session 仍易漏 | 慢 | 高 | 新工具架構、較大測試面 | 高但成本大 | 部分沿用 AST | 回到 A；目前不施工 |
| C：直接整併 registry 與 UI2 feed | 高；兩鏈責任與語意不同 | 回歸慢 | 返工高 | production／契約，超出本批 | 較低 | 不能直接共用 | 不採；先證實重複才提遷移 |

## 2. 兩支鏈，而非 registry → UI2 單鏈

### A. 靜態來源宣告與 runtime registry

| 角色 | 原碼位置（上述基準） | 實際責任／邊界 |
|---|---|---|
| 宣告 metadata | `src/data/core/data_registry.py:17`、`:23`、`:68` | `DATA_REGISTRY` 宣告 source／identifier／state_key 等；登記不代表 runtime 已取數。 |
| Re-export／動態 attribute | `src/data/core/__init__.py:2`、`:4`、`:7` | `_SUBMODULES`＋PEP562 `__getattr__` 即時轉發。AST 的零直接 import 不足以判定零 consumer。 |
| Scanner writer | `src/services/data_registry_scanner.py:85`、`:378` | 從已載入 DF／session 組 registry，寫 `session_state['data_registry']`；不是新增 fetcher。 |
| Scanner 呼叫入口 | `src/services/macro_refresh_service.py:181`、`:1112`；`src/ui/tabs/tab_macro.py:538` | refresh service 登記寫入 key 並呼叫 scanner；Old UI 也有呼叫，不得因 UI2 尚未使用就刪。 |
| Patch writer | `src/services/macro_registry_patch.py:31`、`:50`、`:231`；`src/ui/tabs/tab_macro.py:550` | 讀現有 registry，補建／替換部分 entries 再寫同 key；與 scanner 的執行時機不同。 |
| Pure summary | `src/services/data_registry_summary_service.py:34`、`:76`、`:106` | 讀 caller 注入 mapping；依分類回 count／missing／latest，不取數、不寫 session、不判 freshness。 |
| Legacy consumer | `src/ui/views/page_why.py:2065` | 呼叫 `summarize_data_registry(session)`。Old UI 視圖另有 `src/ui/pages/data_registry_panel.py`，不可因名稱相似直接整併。 |

這裡的 static `DATA_REGISTRY` 與 runtime `data_registry` 是不同資料物件；共同 category 名稱由 `shared/data_categories.py` 定義，不代表可把宣告、寫入、摘要與呈現揉成同一層。

### B. UI2 Real feed（既有兩個事實）

| 角色 | 原碼位置（上述基準） | 實際責任／邊界 |
|---|---|---|
| TWII canonical service | `src/services/market_twii_view_service.py:68`、`:93` | `get_twii_trend_view` 包裝既有 L1 讀取結果及 attrs；latest close 與 as_of／is_stale 原有語意不變。 |
| 市場位階 service | `src/services/allocation_service.py:342`、`:375`、`:378` | `get_macro_regime` 讀 `warroom_summary` 並轉既有 locker；feed 指定 strict 與 require_valid_risk_cap。 |
| Feed adapter | `src/services/ui2/real_feed.py:44`、`:65`、`:80` | `_read_twii`／`_read_regime`→`read_real_snapshot`；兩個事實隔離。此檔所列呼叫路徑未以 registry 作輸入。 |
| Snapshot／canonical | `src/services/ui2/real_canonical.py:93`、`:117`、`:133` | TwiiFact／RegimeFact／RealFeedSnapshot；再轉現有 canonical dict／VM，不新增正式事實。 |
| UI2 caller | `src/ui2/shell/app.py:25`、`:92` | Real 分支呼叫 `read_real_snapshot()` 後交 `get_real_page_vm`。 |

有效依據：`NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md`、`NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` 與 `NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md` 的未 superseded 部分。Real feed 只接既有兩事實，其他未接線能力不能因此判死碼；migration 的 Old UI 凍結／Removal Gate 不變。

## 3. 時間、來源與追溯欄位不是同義詞

| 節點 | source／provenance | as_of／日期 | retrieved_at | freshness |
|---|---|---|---|---|
| 靜態 DATA_REGISTRY | 宣告 source／identifier；不是執行證據 | 非逐次觀測值的統一契約 | 本批未追到逐次擷取契約 | 不能由登記推斷新鮮 |
| Runtime registry | scanner row 主要有 category／frequency／rows／missing；不等於完整來源追溯 | `last_updated` 混合來源；`_reg_add` 從 DF 日期取值（scanner `:35`）；patch scalar 有 proxy 日期（patch `:51`） | 本批未追到可等同此欄的契約 | summary 刻意不判定；`latest` 只選可解析日期前綴 |
| TwiiFact | `source` 原樣欄位；錯誤全文只進 log | `as_of`，不是抓取時間 | TwiiFact 欄位未提供；上游完整血緣尚未追完 | `is_stale`／`stale_reason`／`age_days`，未知不得當新鮮 |
| RegimeFact | `source` 為規則分支 id，**非資料來源**（canonical `:166`） | 契約沒有 as_of→None（canonical `:32`），禁止拿 cl_ts 頂替 | 欄位未提供；不得自行補造 | 保留既有未載入／無法判定等契約，不能從缺欄推 safe |

**限制**：這是欄位與路徑索引，不是新 schema。`last_updated`、資料所屬日、proxy 日期、抓取時間不能互換；缺失欄位不填 0、不建立新的正式狀態。不推論整個 repo 沒有 retrieved_at；本批只列上述節點與未完成追溯。

## 4. 可重跑取證

在完整工作樹、對照當前 main 後執行（命令只讀；輸出由呼叫端自行保存至 scratch）：

```bash
git rev-parse HEAD
python scripts/audit_data_layer_references.py --repo . --prefix src.data
python scripts/audit_data_layer_references.py --repo . --prefix src.services
rg -n 'scan_and_write_data_registry|patch_registry|summarize_data_registry|read_real_snapshot' src shared app.py app_ui2.py scripts tools mcp_server .github/workflows
rg -n 'data_registry|warroom_summary|_SUBMODULES|__getattr__|importlib|__import__' src/data/core src/services src/ui2 scripts tools mcp_server .github/workflows
rg -n 'source|as_of|retrieved_at|fetched_at|freshness|last_updated|is_stale' src/services/data_registry_scanner.py src/services/macro_registry_patch.py src/services/data_registry_summary_service.py src/services/ui2/real_feed.py src/services/ui2/real_canonical.py
pytest --noconftest -o addopts='' tests/test_audit_data_layer_references.py
```

總管已以本批修復版對 main `481ae083` 工作樹重跑預設 prefix：`import_count=18047`、`selected_count=1322`、`parse_errors=[]`；stdout 保存於 scratch，不提交巨大 JSON。這僅是工具掃描範圍內的靜態證據，不是完整依賴或資料血緣。
命令涵蓋明列的搜尋根；**零命中只代表該查詢未命中，不代表沒有 CLI／cron／動態 consumer**。工具 `SCAN_ROOTS` 限 src／shared／scripts／tests，加 app.py／app_ui2.py；infra／tools／mcp_server／workflow 未由本工具完整掃描，需另補取證。PEP562、反射、外部 caller、session 由變數組合的 key、import-time side effects、實際 runtime 頻次均尚未完整解析。不得以 selected_count 或零引用直接刪碼。

## 5. 驗證與合併 checkpoint（尚未完成）

- #1024 已關閉、未合併；Fast CI 曾被 Old UI 零異動守衛擋下，本批不重試該產品碼路徑、不改守衛。
- #1025 原工具會漏 `from src import data` 的 `--prefix src.data` 選取；本批只把 `imported.symbol` 納入靜態語法候選匹配，不宣稱該符號一定為模組。原 4 項隔離測試已經獨立 QA 重跑；修復後總管與獨立 QA 各重跑 7 項通過，拔掉修復的 mutation 為 3 failed／4 passed。兩個工具／測試檔的 pyflakes 與 mypy 通過（環境安裝，未改 requirements）；**新 head CI 待驗**。
- #1026 僅 append DEC-139／140 與 PROJECT_RULES §31；獨立 QA 已檢視文件內容，未改 DEC-138 Dark-only 原文；**CI／合併待最新 GitHub 查證**。本文件不把 PR 分支裁示紀錄冒稱已在 main。
- Branch-protection GET 回 403；rulesets GET 為空。**沒有驗證 required 設定清單，也沒有宣稱 ui2-browser-gate 已被設為 required。**既有 workflow 明記 AI 無權讀寫該設定；不得 bypass／更改保護。合併仍需逐條 checks、獨立 QA、review threads、最新 head／main／衝突 Gate，使用正常受保護 API；此限制不是放寬合併授權。
- **衝突／縮範圍**：main `481ae083` 與 `ccr-phase2-step1` 比較為 ahead 1／behind 65，Claude 分支仍對 `docs/BACKLOG.md`、`docs/HANDOFF.md`、`docs/PROJECT_STATE.md` 有未合併差異。不能假設舊分支 inactive；已撤回本批對共享三檔的追加，保留本專屬報告。**三檔未同步，完整 Stage 尚未完成。**
- **恢復 checkpoint／唯一下一步**：重查 main／Open-Draft PR／全部 branch diff；完成 #1025 新 head 與本索引的獨立 QA／checks。#1026／#1025 合併仍須既有 Gate；共享三檔須等可避開 Claude 同檔工作後同步及驗 main，未完成前不宣告 Stage complete。工具 prefix 修復／兩鏈索引／時間欄位缺口均保留在本報告，沒有新 production 清碼授權。

收尾 Gate：新 Rule／客戶 Decision 無；Audit findings／Limitations／下一步保存於本報告，**共享 BACKLOG／PROJECT_STATE／HANDOFF 因 Claude 同檔衝突退讓、未同步**。無刪碼、無資料遷移、無新 Migration debt；本批尚未驗收完成，不能將本報告視為共享三檔同步的替代品。

**QA 後補記（更新上方「待獨立 QA」狀態）**：本報告限定範圍與工具修復已經獨立 QA 通過；原碼 anchor 按 QA 更正並複核。新 head CI 待驗、共享三檔未同步，完整 Stage 仍未完成；不表示已可合併或已在 main。
