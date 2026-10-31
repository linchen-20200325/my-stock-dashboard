# OneBrain Architecture Decision — 2026-10-31

- **ID**：ADR-OB-001（架構決策編號；不是 `docs/DECISIONS.md` 的 DEC 序號，避免與平行工作產生編號碰撞）
- **狀態**：Approved direction by customer instruction；docs-only；production enablement 未核准。
- **範圍**：my-stock-dashboard only。

## Decision

1. OneBrain 正式定位為 **AI Reasoning & Orchestration Layer**。
2. 正式資料鏈維持：Canonical Data → Deterministic Rules / Risk Engine → Decision Digest → OneBrain → Structured AI Result / UI。
3. **Claude API 為未來規劃 Primary Provider**；架構必須 Provider-neutral，Claude 不得寫死在 domain logic、UI 或 data module。
4. OneBrain 不做 deterministic computation，不得覆蓋 Risk Cap、hard gate、action matrix、candidate admission、provenance/missing safety rule。
5. UI reload 不得直接觸發 AI；正式分析需以 semantic fingerprint / cache 控制。
6. 正式 AI result 必須可追溯 provider/model/prompt-policy/schema/source/fingerprint/usage/cost/fallback/degradation。
7. Prompt / policy 必須集中治理，正式輸出優先 structured schema；不得自行創造新投資 vocabulary 或 confidence 語意。
8. Provider budget exhaustion / unavailable 時，deterministic data/rules 必須繼續工作；AI unavailable 不得等同 SAFE / HOLD / neutral。
9. Provider runtime 導入採 staged path：interface/fake → cache/trace/budget interfaces → Claude shadow → controlled integration → evaluation → separate production decision。
10. 本輪不建立跨 repo shared service；等至少兩個 repo 有穩定重複 contract 與實際 maintenance pain 再另行裁示。

## Existing assets to reuse

- `DecisionDigest` contract / builder / validator / grounding。
- `decision_digest_summary.build_rule_summary` 作為無 AI 的 deterministic fallback。
- `ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md` 的 single Brain + local slice 邊界。
- 現有 secrets/environment 慣例與「credential 不進 Git」方向。

## Existing assets explicitly NOT promoted to OneBrain core

- `app_ai_service.gemini_call`：legacy Gemini-specific transport / key-pool policy。
- `ai_fetcher.post_gemini`：legacy Gemini transport，可借 retry semantics 但不是 Router。
- `dividend_station_service` 現有 prompt/output：legacy building block，不能直接宣稱 OneBrain。
- `ai_qa_service` 工具型 agent：獨立功能，不是 OneBrain canonical decision path。
- `ai_structured_summary` 的 UI/tab 字串輸入：不得成為 canonical Decision Context。
- `exit_signals.judge_news_sentiment`：AI sentiment 介入訊號，需另行 domain Decision Gate。

## Consequences

### Positive
- Provider 可替換，不綁單一供應商。
- AI 成本與頁面 refresh 解耦。
- Analysis 可 audit / replay / compare。
- Data facts、rules、AI explanation 三層責任清楚。
- Provider outage 不破壞客觀資料頁面。

### Costs / technical debt exposed
- 既有 Gemini transport 與 prompt 分散需逐步收斂。
- 需新增 provider-neutral schema、fingerprint/cache、trace、budget interfaces。
- Decision Digest headless production assembly 仍是 OneBrain runtime 前置。
- App/LINE 同資料不同 persona/temperature 的 legacy 分歧需消除。

## Explicit non-decisions

本 ADR **沒有**決定：
- Claude 的具體 model 名稱。
- Claude / OpenAI / Gemini 價格。
- monthly budget 數字。
- fallback provider 順序與付費帳號。
- 新投資狀態詞。
- Risk Cap 公式／門檻。
- 台股／國際趨勢正式定義。
- production enablement。

以上需要 future config/policy 或 Customer Decision Gate。
