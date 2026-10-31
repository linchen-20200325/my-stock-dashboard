# Session Continuity / Quota-Safe Rules — 2026-10-31

Status: governance addendum. This file supplements, but does not replace, `PROJECT_RULES.md`.

## C1. Durable-first on quota/context risk

When remaining model quota/context is low enough to risk losing continuity, the project AI must prioritize a durable checkpoint before starting another implementation batch.

Durable checkpoint means recording, at minimum:
- live GitHub state as verified at that moment;
- current Stage/Phase and exact safe stopping point;
- customer decisions not yet canonically indexed;
- open PRs/branches that matter;
- known limitations/blockers;
- one next safe action;
- required Model×Effort for resume.

Conversation memory is not the checkpoint. GitHub is.

## C2. Auto-continue versus explicit pause

Normal rule: if the next step is already authorized, does not require a new customer decision/manual action/model switch, and remains inside the approved Stage/mainline, the project AI should continue silently rather than waiting for a ceremonial “start”.

Exception: an explicit customer instruction to save, hand off, pause, stop, or protect progress because of quota/context exhaustion overrides auto-continue. In that case, create/sync the durable checkpoint first and do not begin the next implementation batch until the customer resumes.

## C3. Hard Output Gate still applies during handoff

A quota-safe checkpoint does not authorize process chatter. Visible output is still limited to the existing Hard Output Gate cases. CI-running, QA-running, agent activity, commit/push/PR-ready/merge-ready, waiting/retry, and “I will continue” remain silent.

## C4. Model×Effort on resume

At resume, re-evaluate Minimum Sufficient Effort from the actual next action. Do not keep a high-cost model merely because the prior Stage used one, and do not ask the customer to reconfirm if the actual current Model×Effort already matches the recommendation.
