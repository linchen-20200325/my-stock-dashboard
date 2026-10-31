# Safe Handoff / Quota Checkpoint — 2026-10-31

> Purpose: durable recovery point created because the customer reported only ~8% Claude usage remaining. This file is a recovery checkpoint, not a replacement for canonical governance files. On next session, GitHub is SSOT; verify live main/PR/CI first, then reconcile any still-unindexed items into `docs/DECISIONS.md`, `docs/BACKLOG.md`, `docs/PROJECT_STATE.md`, and `docs/HANDOFF.md` before runtime work.

## 1. Verified repository state at checkpoint

- Repository: `linchen-20200325/my-stock-dashboard`
- Live main immediately before this checkpoint branch: `2e034a6939376077ba9d488e2d6bbbd90e59075e`.
- PR #989 is merged; Phase 5 step 0 docs/wireframe is in main (`9a58bd8f...` in history).
- PR #986 OneBrain OB-0 was verified mergeable with successful PR Check and was squash-merged into main as `2e034a6939376077ba9d488e2d6bbbd90e59075e`.
- Phase 4 (📊 市場) is complete; Visual Fidelity PASS and governance sync were already merged via #987/#988.
- No Phase 5 UI implementation is authorized to begin until the customer decisions below are canonically persisted and the next session re-runs GitHub Verification Gate.

## 2. Phase 5 step 0 — customer decisions already made, not yet canonically indexed

Customer decision for `docs/vnext/PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md` Q1–Q3:

- **Q1 = A**
  - Industry Top 5 presentation uses a horizontal bar chart.
  - Display ordering uses the existing field **5-day cumulative institutional net inflow**, descending.
  - This decision is ONLY the presentation/display ranking of the Industry Top 5.
  - It MUST NOT change candidate admission, fundamental initial filters, stock ranking/score, Risk Cap, formal industry-trend definition, or any deterministic investment rule.
  - Missing values MUST NOT be converted to zero or treated as strongest/weakest; existing Missing Contract applies.

- **Q2 = B**
  - Keep the already-approved overall page order.
  - Stock-selection conditions are collapsed by default with one exposed summary line.
  - Candidate list shows Top 10 first.
  - Full candidates remain available through expansion/details.
  - Existing request parameters such as `DEFAULT_TOP_N=50` remain unchanged; Top 10 is a presentation slice only.
  - Collapsing UI MUST NOT be interpreted as reducing data fetch/computation.

- **Q3 = A**
  - Ranking basis remains an explanatory sentence, not a new chip.
  - Main visual uses `為什麼／來源／限制／去哪補`.
  - Other existing tile/block labels remain unchanged.
  - Do not rename the whole page merely for visual uniformity.

## 3. Next safe action

1. Re-run GitHub Verification Gate against current live main and open PRs.
2. Persist the Phase 5 Q1=A / Q2=B / Q3=A decision into canonical `docs/DECISIONS.md` with clear scope and supersede/relationship notes where necessary.
3. Synchronize `docs/BACKLOG.md`, `docs/PROJECT_STATE.md`, `docs/HANDOFF.md`, and the Phase 5 wireframe status.
4. Only after canonical persistence, begin Phase 5 UI implementation under the existing wireframe/Visual Fidelity rules.
5. Q1 crosses a ranking/investment-semantics boundary only to the extent described above; the approved scope is display ordering only. If implementation requires changing domain semantics, stop at Decision Gate instead of broadening Q1.

## 4. OneBrain durable status

OneBrain OB-0 architecture/governance docs are now merged to main. The durable direction is:

- OneBrain = **AI Reasoning & Orchestration Layer**.
- **Data is evidence. Rules are constraints. OneBrain is reasoning.**
- Data layer and AI reasoning layer remain separated.
- Deterministic compute/rules/Risk Engine precede OneBrain.
- Claude API is a future Primary Provider direction, but architecture is provider-neutral.
- No production Claude API/runtime/key/provider SDK was enabled by OB-0.
- Cache/fingerprint, trace/audit, budget, prompt/policy registry, structured output, fallback and graceful degradation are architecture requirements.
- No OneBrain production enablement without a future customer Decision Gate.

## 5. Do NOT lose these current governance rules

Existing `PROJECT_RULES.md` remains authoritative. At minimum the next session must preserve and enforce:

- GitHub is SSOT; HANDOFF/STATE/chat memory are secondary.
- Before project judgment, re-check live main SHA, PRs, relevant diffs, CI/QA, branches when relevant.
- Data layer != AI reasoning layer; missing != 0; unavailable != neutral; not evaluated != safe.
- Hard Output Gate / Silent Autonomous Cruise: do not expose CI-running, QA-running, agent/WIP, push/commit/PR-ready/merge-ready/waiting statuses.
- Customer Decision Gate output must be minimal; do not use `🟢 不需要你回覆` to wrap process chatter.
- UI Stage complete only after CI green + Visual Fidelity PASS + governance sync.
- New UI simplified presentation must not silently delete decision context/capability.
- Model×Effort uses minimum sufficient effort; if current actual setting already matches, continue without asking the customer to reconfirm.

## 6. Explicit pause instruction for quota exhaustion

This checkpoint was requested specifically to prevent loss of progress when model usage is nearly exhausted.

Until the customer explicitly resumes work:

- Prefer durable documentation over starting a new implementation batch.
- Do not start Phase 5 UI code merely because the previous Stage normally auto-continues.
- If a session ends here, the next session starts from Section 3 after fresh GitHub verification.

## 7. Suggested model / effort on resume

- Canonical docs reconciliation: **Sonnet 5.5 + Medium**.
- Phase 5 Q1 semantic guard review, only if domain semantics are actually touched: **Opus 5.5 + High**.
- Pure UI assembly/tests after the Q1 boundary is proven unchanged: **Sonnet 5.5 + Medium**.
