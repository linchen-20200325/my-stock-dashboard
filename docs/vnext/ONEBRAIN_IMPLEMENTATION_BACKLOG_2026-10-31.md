# OneBrain Implementation Backlog（2026-10-31）

- **性質**：OneBrain 專題 backlog / phase plan；不取代 `docs/BACKLOG.md` 的專案總主清單。
- **執行權限**：本檔列出未來工作，不代表已授權 runtime implementation。
- **依賴**：`ONEBRAIN_ARCHITECTURE_2026-10-31.md`、ADR-OB-001、Decision Digest Contract、One AI Brain Boundary。

## OB-0｜Architecture / Governance（本輪）

- [x] 盤點既有 AI / LLM / prompt / Provider / Decision Digest。
- [x] 定義 Provider-neutral OneBrain 邊界。
- [x] 定義 cache/fingerprint、trace、budget、prompt、structured output 原則。
- [x] 記錄 Claude Primary direction，但不接 runtime。
- [x] 記錄跨 repo 相容方向，但不建 shared service。

## OB-1｜Provider abstraction（未授權實作）

- [ ] 定義 `Provider` Protocol / ABC。
- [ ] 定義 provider-neutral Request / Response / Error taxonomy。
- [ ] 建 `FakeProvider`；CI 不呼叫外部 LLM。
- [ ] config/policy 決定 provider/model，不得 domain hard-code。
- [ ] 不安裝未使用 Provider SDK。

**DoD**：純 fake 測試可驗 timeout/rate-limit/unavailable/invalid-response；0 真 API call。

## OB-2｜Fingerprint / Cache / Trace / Budget interfaces（未授權實作）

- [ ] 定義 normalized semantic input serialization。
- [ ] analysis fingerprint（Digest/source refs/as_of/prompt-policy/schema/analysis type）。
- [ ] 明確排除 UI/session noise。
- [ ] 成功 cache vs failure/backoff 分離。
- [ ] `analysis_id` / trace schema。
- [ ] token / cost telemetry nullable fields。
- [ ] soft/hard cap policy interface。

**DoD**：同 semantic input 不觸發 Provider；UI-only change fingerprint 不變；資料/policy/prompt 改變 fingerprint 必變。

## OB-3｜Claude Provider Shadow（Decision Gate + manual configuration required）

- [ ] 先完成 secrets/config 規格審核。
- [ ] ClaudeProvider 只在 shadow path 啟用。
- [ ] 不接正式投資決策、不改 UI 的正式結論。
- [ ] 記錄 trace/cache/cost/latency/degradation。
- [ ] Provider unavailable 時 rule-only output 照常。

**Gate**：開始前需客戶明確核准真 Provider shadow 與必要設定；本輪不要求任何真實 credential。

## OB-4｜Controlled low-risk integration（Decision Gate）

候選功能必須符合：
- 只解釋既有 deterministic result。
- 不新增 action / Risk Cap / trend definition。
- 有 clear baseline 可比對。
- AI unavailable 時 deterministic output 完整。

- [ ] 選唯一 pilot feature。
- [ ] 定義 evaluation dataset / acceptance metrics。
- [ ] Structured output + grounding。
- [ ] cache/fallback/budget 全接通。

## OB-5｜Evaluation

- [ ] correctness / evidence grounding。
- [ ] consistency（同 fingerprint 重跑）。
- [ ] missing-data behavior。
- [ ] deterministic safety conflict test。
- [ ] provider timeout/rate-limit/unavailable。
- [ ] fallback behavior。
- [ ] cost / token usage。
- [ ] latency。
- [ ] cache hit rate。
- [ ] App / LINE channel consistency（若納入）。

## OB-6｜Production enablement（blocked on customer）

- [ ] 客戶另行裁示 production enablement。
- [ ] 明確 provider/model policy。
- [ ] 明確 budget caps。
- [ ] 明確 fallback provider policy。
- [ ] secrets deployment / rollback plan。
- [ ] production observability / audit retention。

## Existing technical debt / migration candidates

| ID | 優先 | 項目 | 處置 |
|---|---|---|---|
| OB-TD-01 | P1 | Decision Digest headless production assembly 尚未完成 | runtime 前置；沿用既有 `P1R-DIGEST-HEADLESS-ASSEMBLY` |
| OB-TD-02 | P1 | `app_ai_service.gemini_call` 與 `ai_fetcher.post_gemini` 雙 transport | Provider abstraction 後再收斂；不得本輪硬合併 |
| OB-TD-03 | P1 | prompt/persona 分散於 service / script / UI-adjacent code | Prompt Registry 階段盤點遷移 |
| OB-TD-04 | P1 | App/LINE 同摘要不同 persona/temperature 可能分歧 | 改吃同一 Brain result slice |
| OB-TD-05 | P1 | 無正式 OneBrain cache/fingerprint | OB-2 |
| OB-TD-06 | P1 | 無統一 trace/cost/budget | OB-2 |
| OB-TD-07 | P1 | provider-specific model names hard-coded in legacy Gemini paths | Legacy 保留；新 Router 禁止延續 |
| OB-TD-08 | P1 | `exit_signals.judge_news_sentiment` AI 參與訊號 | Domain Decision Gate；不得默默接入 Brain |
| OB-TD-09 | P2 | `ai_qa_service` / `ai_structured_summary` 與 OneBrain 名詞容易混淆 | 文件標界線；不急著重構 |
| OB-TD-10 | P2 | 未來跨 repo 可能重複 Provider/cache/trace | 先觀察；禁止 premature shared repo |

## Stop Gates

遇到以下任一項必停手：
- 要啟用真 Claude API。
- 要求真實 credential / production secret change。
- 要新增 fallback paid provider/account。
- 要新增投資 vocabulary / confidence semantics。
- 要改 Risk Cap / formula / deterministic action semantics。
- 要把 AI output 接正式 action path。
- 要建立跨 repo shared service/package。
- 要增加新外部資料來源。
