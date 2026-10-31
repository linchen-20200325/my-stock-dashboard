# OneBrain Repo Inventory（2026-10-31）

## Verification snapshot

- `origin/main`：`4c1546b5797e94c3fa8c5e91a6da7ded15e9e225`（PR #984 merge，開工時實查）。
- Open/Draft PR：#985，Draft，Phase 4 P4-2，head `6a5b43e22f01be48b8a77f3a21105b25296e4e92`。
- #985 PR Check：開工盤點時 in progress；本 OneBrain docs 分支不碰其 runtime WIP。
- 相關 branches：`main`、`ccr-c8ef17de-9tw7yt`（#985）、`auto/recalibrate-20261001`、`data`、`v2`、歷史 `ccr-*`／handoff branches。

## Existing AI / Decision Context assets

| 類型 | 現有檔／符號 | 現況判定 |
|---|---|---|
| Decision Context schema | `shared/decision_digest.py` | 可沿用，OneBrain canonical input 核心 |
| Rule references | `shared/decision_digest_rules.py` | 可沿用 |
| Validation | `shared/decision_digest_validator.py` | 可沿用 |
| Grounding | `shared/decision_digest_grounding.py` | 可沿用 |
| Digest builder | `src/services/decision_digest_builder.py` | 可沿用；production headless assembly 尚缺 |
| Rule-only summary | `src/services/decision_digest_summary.py` | 可作 AI unavailable fallback |
| Brain boundary | `docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md` | 正式既有邊界，需被本輪 Provider/cost/cache 規格擴充而非取代 |
| Digest contract | `docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` | 正式既有輸入契約 |
| Legacy Gemini multi-key | `src/services/app_ai_service.py::gemini_call` | Provider-specific legacy transport；含 key pool、model list、persona、HTTP |
| Legacy Gemini transport | `src/services/ai_fetcher.py::post_gemini` | Provider-specific transport；可借 retry/error semantics |
| Legacy holding summary | `dividend_station_service.build_ai_summary/build_summary_prompt` | prompt/domain 混合；未來 replace prompt出口 |
| App/LINE AI | app + `scripts/push_holdings_daily.py` | 同資料可能因 persona/temperature 不同產生分歧 |
| Weekly AI | `weekly_review_service` | 有自建市場定調，需改吃正式 rules/Digest |
| AI QA | `ai_qa_service.run_agent` | 獨立工具型功能，不是 canonical Brain |
| Structured tab summary | `ai_structured_summary` | UI/tab 字串導向，禁止當 canonical Brain input |
| AI sentiment exit signal | `exit_signals.judge_news_sentiment` | Domain safety conflict candidate，需另 Gate |

## Alignment

### 已符合
- Data ≠ AI 原則。
- Digest 不從 UI scrape 的正式方向。
- One Brain + local slice。
- Missing 不得冒充 neutral/safe。
- Grounding / evidence refs。
- Rule-only fallback 雛形。

### 可沿用
- DecisionDigest schema / builder / validator / grounding。
- formal RuleRef / provenance concepts。
- existing secrets/env convention。
- legacy transport 的 timeout/retry/rate-limit handling 經驗。

### 有衝突
- Gemini provider/model hard-code。
- legacy persona/prompt 分散。
- legacy AI 可參與方向判斷／情緒訊號。
- App/LINE 同一分析不是同一 Brain result。
- 部分 legacy context 仍從 session/UI-adjacent state 組裝。

### 尚缺
- Provider protocol/router。
- ClaudeProvider shadow path。
- analysis fingerprint/cache。
- unified trace/audit。
- token/cost telemetry。
- budget caps。
- centralized prompt/policy registry。
- provider-neutral structured result schema。
- approved fallback policy runtime。

## Scope note

本盤點不宣稱逐檔窮舉；它以既有 One AI Brain Boundary 的 AI 出口盤點、Decision Digest Contract、`app_ai_service.py`、`ai_fetcher.py` 與 main 上可定位的正式治理文件為基準。Phase 7 runtime 開工前仍需重新 GitHub Verification Gate 與獨立 inventory recheck。
