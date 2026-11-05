# 死碼、資料分類與重複資料路徑｜GitHub 初步唯讀稽核（2026-11-05）

> **狀態：Initial Read-only Audit / Not Exhaustive / 不授權刪除、搬檔或修改投資規則**。
> **基準**：GitHub main `fb466d156e1003b0450053344934962007be07a4`（#1019）；撰寫時 #1020（UI code，head 另有更新）、#1021（分工）、#1022（New UI2 藍圖）仍 open。實查由 GitHub file/code search 與既有稽核文件交叉讀取，**未於完整 repository 工作樹執行 AST/import graph、pytest、runtime trace、動態註冊分析**。本稽核只能列候選，不宣稱掃描完全部死碼或目前 production 仍有歷史報告的每個缺陷。
> **治理**：`CLAUDE.md`、`PROCESS.md`、`PROJECT_RULES.md`、有效 DEC 優先；舊 UI 不因 New UI2 尚未切換正式入口而被當成 dead。OneBrain 完整 Evidence 以及 canonical/source/provenance/freshness 禁刪。

## 1. 本輪直接讀到的架構事實
| 位置 | 現有責任 | 注意事項 |
|---|---|---|
| `app.py`, `src/ui/` | Old UI；實際 `app.py` 仍引用 legacy rendering | **不是死碼**；切換正式入口前不刪、不搬 |
| `src/ui_v2/` | Legacy New UI | 不是 New UI2；需核對引用、測試、資料依賴及 cutover contract |
| `app_ui2.py`, `src/ui2/` | New UI2 Preview；四頁人類呈現 | 預設 FAKE Preview，不是真實 production 預設 |
| `src/services/ui2/real_feed.py` | New UI2 的唯一 I/O feed 適配器 | 目前只讀 TWII 與市場位階兩個事實；不能把其他未接線項目判定為不存在 |
| `src/services/ui2/real_canonical.py`, `*_vm.py` | snapshot→canonical→純 VM | 不可把 missing / unavailable / not evaluated 混用或直接轉成 0 |
| `src/data/core/data_registry.py` | 宣告式 metadata／資料源註冊表，含 EDU 指引 | **登記來源 ≠ production 已呼叫／已取得資料／有 as_of** |
| `src/services/data_registry_scanner.py` | 實際 session/DF 掃描，寫 `data_registry` | **執行時健康資料**，與靜態 registry 是不同事實；不能任意合併 |
| `src/services/data_registry_summary_service.py` | 執行時 registry 的唯讀摘要 | 應以同一份 metadata 身分映射，不能另外推導成新的狀態權威 |
| `src/data/` | L1 來源；現有核心、總經、個股、ETF、日資料、portfolio、proxy 等分類 | 不應只為目錄美觀搬動穩定模組；其他子類以當前 Git tree 與引用為準 |
| `src/compute/`／`src/services/`／`shared/` | 規則計算／業務接口／跨層常數契約 | 尤其 shared/ 有跨 repo 同步註記，禁止不查同步來源就改寫 |

## 2. 死碼候選（證據標準與處置）
| 候選 | 已有證據 | 本輪判定 | 下一步 |
|---|---|---|---|
| `MACRO_ALLOC`（`src/ui/render/etf_render.py`） | 原始碼註明 Deprecated；舊表與正式 allocation service 脫鉤，但保留給舊 caller 相容／fallback | **待 caller 逐一確認**，非已證明零讀者 | AST/動態引用/測試/外部入口檢查後才可移除 |
| `MACRO_DESC`（同上） | 原始碼註明 Deprecated、現有 repo 無實質讀者的**歷史自述**；`src/ui/etf/etf_dashboard.py` 仍 re-export | **高價值清理候選，但未達刪除門檻** | 查 imports / public API / downstream test，先做 thin shim 退場計畫 |
| `etf_backtest_data` 舊 session 讀者 | `etf_tab_ai.py` 留讀取與可選報告欄；原註解稱無寫入者、回測 UI 已移除 | **疑似過時相容路徑**；不可只因無寫入者就刪 | 查正式 session writer、外部測試、AI prompt 及安全語意 |
| `shared/ia_nav4.py` 的 `page_inspect` | 原始碼明示 Legacy `?legacy=1` 仍可派發 | **LIVE，不准判死碼** | cutover 後再盤點 |
| `src/ui2/` 未接 Real 的圖表和 placeholder | 現有 Active Contract 明定保留圖槽與 VM evidence；Real feed 僅接兩項事實 | **NOT DEAD**（未接線 / 尚未提供） | 依資料契約決定接線，不造假趨勢 |
| 舊 `src/ui_v2/` 與 Old UI | New UI2 尚非正式 app 入口 | **暫不清** | 必須先過 cutover + Old→New Interaction Coverage 與 E2E |
| `docs/DEAD_CODE_AUDIT.md` T2 二十五候選 | 歷史 AST-strict audit：20 test-live、3 false positives、2 source-string guard；**該時點** 0 項准自動刪 | **既有安全清單，不當作 2026-11-05 的即時引用圖** | 逐檔最新引用圖重新驗證；禁止批量刪 |
| `ARCHIVED_FEATURES.md` 的歷史恢復路徑 | 已明確更正：PR #623 將三個 backend 模組與測試一起刪除，原「磁碟仍有 backend」說法失效 | **文件已補歷史更正**，不能當現存死碼 | 需要復活才走歷史還原 Gate |

**刪除門檻：** 同時具備 (1) production/Preview/legacy/CLI/cron/side-effect/import-time/writer/reader 的最新引用證明；(2) public API/re-export/字串/反射/測試 guard 掃描；(3) 不是儲存 canonical/evidence/追溯責任；(4) 最小 mutation / regression 保全；(5) 不會觸及未核准功能縮減／刪資料。否則分類 `UNKNOWN`／`TEST_LIVE`／`COMPAT`／`FUTURE_DEPENDENCY` 而不是 DEAD。

## 3. 資料分類：建議改為「資料契約索引」而非立刻搬檔
現有 source metadata、session registry、UI2 adapter 既非同一層也非同一種來源，建議**先加一份只讀映射**，不建立第二套資料判定 SSOT：
| 分類維度 | 欄位（只記錄／來源明確，缺則記缺） |
|---|---|
| Domain | 台股大盤／國際總經／產業與籌碼／個股價格與基本面／ETF／持股與帳戶／事件與新聞 |
| Source identity | 原始供應商、識別碼、原始 frequency、endpoint 是否宣告、授權／可達性 |
| Pipeline role | registry metadata / actual fetcher / normalize / canonical / deterministic compute / service / UI2 feed / evidence / Digest |
| Runtime readiness | implemented?、wired to production?、wired to UI2?、actually read?、as_of、retrieved_at、freshness／source error（皆以證據為準） |
| Semantics | Data State 五態／Capability 兩軸分開，proxy/estimated 不當真值；讀數與規則判斷分層 |
| Consumer / owner | Old UI、Legacy New UI、New UI2、headless／cron、Risk Cap、System Action、OneBrain future；唯一 owner、所有 read/write/Side-effect |
| Governance | 正式 canonical SSOT、Risk Cap 規則、資料來源授權、缺值合約、最後實驗證據、問題 BACKLOG ID |

**建議路徑**：維持原始 fetcher 按 domain 既有結構；以**一份產生式／唯讀 inventory**跨層連結 metadata 與 consumers。只有已證實重複取數、同一事實兩套映射，才提 API 單一出口或 import shim；不要直接大批更名、移動 `src/data` 或複製 canonical。

## 4. 有資料可靠性疑慮的既有證據（必須重新驗證新狀態）
讀取 `docs/vnext/DATA_HEALTH_AUDIT_2026-10-23.md`，該報告指出以下當時缺陷：`^TWII` MA200 樣本不足可能假值；代理 ADL 被當真實廣度計分；BIAS240／PCR estimated 影響 Risk Cap；FinMind 備援 buy/sell 缺漏時 `fillna(0)`；台灣出口名稱與資料實義不同；VIX as_of／盤中未收盤；Registry 教學條目與實取來源可能不符。**這是 2026-10-23 的歷史報告，不是此輪重現的即時 bug**；須逐項重新驗現行 Git SHA 的 code、測試、相關 PR、可能已修狀況。
- **Risk Cap／市場位階**：只讀研究；不得把這些問題包在清碼 PR 修改正式公式或數值。
- **資料缺口不填 0**；缺資料不能變「不觸發」或「安全」。
- **資源優先**：先核對會改變正式投資動作的來源與新鮮度問題，再處理純文案或目錄美觀。

## 5. 三路徑比較
| 路線 | 風險 | 速度 / Token | 建議 |
|---|---|---|---|
| A. 立刻重分目錄並批量刪 dead | 動態入口與相容性極易漏；高 | 返工高 | 不採 |
| **B. 建立引用與資料血緣映射，再分三個安全施工批** | 低／可證明 | 最省重工 | **採用** |
| C. 保持原狀，只按缺陷零星補 | 低但 SSOT 漂移難追 | 長期高 | 不採 |

## 6. 後續施工任務（屬 Claude Code；文件分工仍由 ChatGPT 主責）
**Batch A — 唯讀二組獨立取證（建議 Sonnet 5.5 Medium）**：
1. 在當前 main 的完整 clone 以 AST + ripgrep + importlib entrypoint/registry/side-effect，先覆核 `MACRO_ALLOC`、`MACRO_DESC`、`etf_backtest_data`，每項輸出全 consumer／test/side-effect 和證據；不刪。
2. 用現有資料 registry/consumer 建一份**機器生成的只讀清單**，對應 data/core、scanner、real_feed、Risk Cap、Digest；先研究資料契約，不新加 production runtime。
3. 交叉對照 2026-10-23 Data Health Audit 影響正式 action 的高風險項，列 still-open／fixed／unable-to-reproduce 並對應 commit 與 test；不改公式。
**Batch B — 僅通過 Gate 的純相容退場（Sonnet 5.5 Medium）**：逐一對候選提供 caller=0、test 遷移、差異與 mutation 證據；只在上位授權與獨立 QA 完成後才動。
**Batch C — 來源與分類正規化（視影響 Medium／High）**：以 inventory 證明重複 fetch／canonical 失配才分批收斂，提供回滾路徑；觸及資料定義、Risk Cap、來源或時間對齊則 Opus 5.5 High 及客戶 Gate。

## 7. 執行與驗收
- 全面唯讀探針不受限於本文件列的候選三項；範圍先從 high-value 的實際動作風險開始，避免只依文檔 TODO 或 `DEPRECATED` 字眼机械掃。
- 真 dead 要能同時證明「production 0 + CLI/cron 0 + old UI 0 + test/safe-compat 已處理」。無依賴證據不能刪。避免動態 import／Streamlit widget key／UI session 讀寫遺失。
- 驗資料須列 `source, identifier, as_of, retrieved_at, freshness, is_proxy, is_estimated, consumer, risk_gate`（不存在欄位標 `missing`，不是 0）。
- 舊 UI 邏輯保留至正式 cutover，真資料與 AI 分離；Evidence 覆蓋與 UI 簡化分軌驗。
- 本文件是 ChatGPT 的初步唯讀稽核，尚未經獨立 code-level QA，也未執行完整 CI，**不得以此標 DEAD_CONFIRMED 或批准任何刪除**。
