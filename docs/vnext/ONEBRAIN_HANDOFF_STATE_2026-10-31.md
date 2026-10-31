# OneBrain Handoff / State Snapshot（2026-10-31）

- **目的**：讓下一個沒有聊天記憶的 AI 能接續 OneBrain 規劃；本檔是 OneBrain 專題接手快照，不取代 `docs/HANDOFF.md` / `docs/PROJECT_STATE.md` 的全專案角色。
- **GitHub 開工基準**：`origin/main = 4c1546b5797e94c3fa8c5e91a6da7ded15e9e225`（PR #984 merge）。
- **平行 WIP**：Draft PR #985（Phase 4 P4-2，head `6a5b43e22f01be48b8a77f3a21105b25296e4e92`）在既有分支 `ccr-c8ef17de-9tw7yt`；本 OneBrain docs 分支不得混入 P4-2 runtime diff。
- **本 OneBrain 分支**：`docs/onebrain-architecture-20261031`。

## Current truth

1. 本 repo 已有正式：
   - Decision Digest Contract。
   - One AI Brain Boundary。
   - deterministic grounding / rule-only summary infrastructure。
2. 目前 legacy AI 主要仍是 Gemini-specific transport/prompt；不能宣稱 Provider-neutral OneBrain runtime 已完成。
3. 2026-10-31 客戶新增正式方向：Claude API 作 future Primary，但 OneBrain 必須 Provider-neutral，且內建 cache/fingerprint、trace/audit、budget、structured output、graceful degradation。
4. 本輪只做 architecture/governance/backlog；禁止大規模 runtime。

## Files created in this batch

- `docs/vnext/ONEBRAIN_ARCHITECTURE_2026-10-31.md`
- `docs/governance/ONEBRAIN_AI_GOVERNANCE_2026-10-31.md`
- `docs/vnext/ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md`
- `docs/vnext/ONEBRAIN_IMPLEMENTATION_BACKLOG_2026-10-31.md`
- `docs/vnext/ONEBRAIN_HANDOFF_STATE_2026-10-31.md`

## Next unique handoff point

**OB-0 docs PR review / merge only.**

合併前只驗證：
- 文件互相引用正確。
- 不與既有 Decision Digest / One AI Brain Boundary / PROJECT_RULES 衝突。
- diff 只有 docs。
- 無敏感憑證內容。
- 不混入 P4-2 runtime WIP。

合併後仍不得自動進 OB-1 runtime。下一個 runtime 起點必須重新 GitHub Verification Gate，並依 canonical `docs/BACKLOG.md` / 最新 DEC 判斷是否已有授權。

## Explicit confirmations

- 尚未接正式 Claude API。
- 尚未要求客戶提供真實 API credential。
- 尚未新增 Provider SDK。
- 尚未改正式投資決策邏輯。
- 尚未改資料層邏輯。
- 尚未改 Risk Cap。
- 尚未改 UI。
- 尚未建立跨 repo shared runtime。
