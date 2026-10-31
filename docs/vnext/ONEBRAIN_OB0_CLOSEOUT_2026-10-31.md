# OneBrain OB-0 Closeout Checklist（2026-10-31）

## Scope

本批為 docs-only architecture/governance inventory，不做 runtime。

## Checks

- [x] OneBrain 定位為 AI Reasoning & Orchestration Layer。
- [x] 保留 Data → Rules → Digest → OneBrain → UI 架構。
- [x] Provider-neutral，Claude 只作 future Primary direction。
- [x] Deterministic-first / Risk Cap precedence。
- [x] Cache/fingerprint 原則。
- [x] Trace/audit/cost/budget 原則。
- [x] Prompt/policy/structured output 原則。
- [x] Secrets 安全邊界只寫規格，不要求客戶配置。
- [x] 跨 repo 只定相容方向，不建 shared runtime。
- [x] Staged backlog OB-1～OB-6。
- [x] 本分支 diff 僅 `docs/`。

## Explicit non-changes

- Claude API runtime：未接。
- 真實 Provider credential：未要求。
- UI：未改。
- Data layer：未改。
- Formula / threshold / Risk Cap：未改。
- Production decision logic：未改。
- Dependencies / SDK：未新增。
- External data source：未新增。

## Canonical-doc concurrency note

開工時存在 Draft PR #985（P4-2），其工作流正在更新 Phase 4 的 HANDOFF / PROJECT_STATE / BACKLOG 類接手資訊。為避免在平行 branch 對同一大型 canonical 文件製造 merge conflict，本 OB-0 分支採「新增正式 OneBrain docs＋專題 handoff/state snapshot」方式落盤，**沒有在這個平行分支直接改寫 `docs/HANDOFF.md`、`docs/PROJECT_STATE.md`、`docs/BACKLOG.md`、`docs/DECISIONS.md`**。

這不是宣稱中央 SSOT 已同步：合併 OB-0 前／後，專案總管應在沒有平行衝突的安全 checkpoint，把本批入口索引回中央 HANDOFF/STATE/BACKLOG/DECISIONS；不得因未索引就重做本批架構內容，也不得因此提前啟動 runtime。
