# OneBrain AI Architecture vNext（AI Reasoning & Orchestration Layer）

- **狀態**：正式方向紀錄／Architecture & Governance only；本輪禁止大規模 runtime 實作。
- **日期**：2026-10-31
- **GitHub 基準**：開工前 `origin/main = 4c1546b5797e94c3fa8c5e91a6da7ded15e9e225`（PR #984 merge）；另有 Draft PR #985（P4-2）在 `ccr-c8ef17de-9tw7yt`，本文件分支不碰其 WIP。
- **上位**：`CLAUDE.md` > `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance/*` > 最新有效 DEC > 本檔。
- **既有配套 SSOT**：
  - `docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`
  - `docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`
  - `docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`
  - `shared/decision_digest*.py`
  - `src/services/decision_digest_builder.py`
  - `src/services/decision_digest_summary.py`
- **核心句**：**Data is evidence. Rules are constraints. OneBrain is reasoning.**

---

## 1. 定位

OneBrain 是本專案的 **AI 推理／協調層（AI Reasoning & Orchestration Layer）**。

它負責：
- 在已存在、可追溯的證據與正式規則結果之上做多來源訊號整合。
- 解讀基本面、總經、籌碼、事件、Regime、持股與候選之間的關係。
- 解析矛盾訊號與情境。
- 產出人類可讀、可追溯、受 deterministic safety logic 約束的解釋／決策理由。
- 協調 Provider、prompt/policy、structured output、cache、trace、budget、fallback。

OneBrain **不是**：
- 資料來源／crawler／ETL。
- 指標計算器或財務公式引擎。
- Risk Cap 規則本身。
- UI。
- DB／storage layer。
- 可自行搜尋市場資料的 agent。
- 可取代 deterministic rules 的自然語言規則引擎。

正式資料流：

```text
資料來源 / API / DB
  ↓ fetch / clean / normalize / validate / provenance
客觀資料層（Canonical Data）
  ↓ deterministic compute / rules / indicators / Risk Engine
Decision Digest（Decision Context）
  ↓
OneBrain AI（Reasoning & Orchestration）
  ↓
Structured AI Result + Grounding / Trace
  ↓
UI / Local Summary / 決策輸出
```

延續既有契約：**Data View ≠ Decision Context ≠ AI Output**。

---

## 2. 絕對邊界：資料層 ≠ AI 推理層

OneBrain 只可讀「已取得、已標準化、可追溯的現有資料」與正式 deterministic rule results。

禁止 OneBrain：
- 創造缺失資料。
- missing → 0。
- unavailable → neutral。
- not evaluated → safe。
- 因資料缺漏自行假設「無風險」。
- 回寫／修改 canonical data。
- 以 LLM 推論取代可由 Python／rule engine 明確公式化的計算。
- 無來源製造市場事實。
- 從 UI 文字、顏色、widget、Top-N、expander 狀態反推 canonical data。

資料不足時：

```text
必要 evidence 不足
→ Structured Result 明確列 missing_data / degradation_reason
→ 顯示「資料不足／無法判定」
→ 不產生假 HOLD / SAFE / neutral
```

現有 `Decision Digest` 與 `grounding.check_summary` 防線優先沿用，不建立第二套「AI 自己驗自己」的平行資料契約。

---

## 3. Deterministic-first 原則

**能確定性計算的，不使用 LLM。**

通常留在 Python / domain rules：
- EPS、成長率、報酬率。
- 技術指標、均線、排名、分數。
- 門檻與分類。
- Risk Cap。
- schema / provenance / data completeness validation。
- 日期、freshness、stale 判斷。
- deterministic classification。
- 可明確公式化的財務模型。

OneBrain 適合：
- 多來源訊號整合。
- 基本面變化解讀。
- 新聞事件與持股影響。
- 產業趨勢推理（只能基於既有 evidence，不自行產生產業事實）。
- Regime／基本面／籌碼／事件關聯說明。
- 矛盾訊號解析。
- 情境分析。
- 已存在規則結果的解釋。
- 人類可讀的決策理由。

LLM 不得覆蓋安全規則；若 AI 結論與 deterministic safety logic 衝突，以 deterministic safety logic 為準。

---

## 4. Provider-neutral 架構

OneBrain 不得與單一模型供應商耦合。

目標概念：

```text
OneBrain
├─ Provider Router
│  ├─ ClaudeProvider   ← current planned Primary
│  ├─ OpenAIProvider   ← future approved fallback
│  ├─ GeminiProvider   ← future approved fallback / legacy migration target
│  └─ OtherProvider    ← future only
├─ Prompt / Policy Registry
├─ Model Routing Policy
├─ Analysis Cache
├─ Trace / Audit
├─ Budget Control
└─ Graceful Degradation
```

### 4.1 Provider interface 最低契約

Provider adapter 至少需抽象：
- provider id
- model id（config/policy 管理，不寫死 domain logic）
- request
- response
- timeout
- retry policy
- rate-limit error
- provider unavailable
- token usage（若 provider 提供）
- estimated / actual cost（若可得）
- trace metadata（不得含 secrets）

### 4.2 最小依賴

本輪不安裝 Claude／OpenAI／Gemini SDK。

未來若進 Provider abstraction，優先：
1. Protocol / ABC。
2. FakeProvider。
3. Provider-neutral request/result schema。
4. 再於獨立 shadow 階段只接「已核准的單一真 Provider」。

不得為「未來可能會用」一次安裝全部 SDK。

---

## 5. Claude API Primary 策略（未啟用）

未來正式啟用的預設方向：

1. Claude API 可用且政策允許 → Claude。
2. Claude 發生 timeout / rate limit / provider unavailable / budget cap / policy-disabled → 才進入**已核准** fallback。
3. 全部 Provider 不可用 → 客觀資料頁面與 deterministic rules 必須繼續可用；AI 部分明確顯示「AI 分析暫不可用／無法判定」。

注意：
- Claude 是目前**規劃中的 Primary**，不是 domain dependency。
- 不把任何訂閱方案、贈送額度金額、促銷期限寫成架構前提。
- Claude 不得寫死在 UI、資料模組或投資規則。
- 未來換 Provider 不應要求重寫核心業務邏輯。
- 本輪**尚未接 Claude API**、未要求 key。

---

## 6. 現有 AI / LLM 架構盤點

### 6.1 已可沿用

| 現有資產 | 判定 | OneBrain 用法 |
|---|---|---|
| `shared/decision_digest.py` | ✅ 核心可沿用 | AI canonical input contract |
| `shared/decision_digest_rules.py` | ✅ | deterministic rule references / allowlist |
| `shared/decision_digest_validator.py` | ✅ | input validity / availability |
| `shared/decision_digest_grounding.py` | ✅ | output grounding / evidence refs |
| `src/services/decision_digest_builder.py` | ✅ 但需 headless 接線 | canonical Decision Context builder |
| `src/services/decision_digest_summary.py` | ✅ | AI unavailable 時 rule-only fallback |
| `ONE_AI_BRAIN_BOUNDARY...` | ✅ | Brain 邊界與 Local Summary slice 規則 |
| `DECISION_DIGEST_CONTRACT...` | ✅ | Data → Context 契約 |
| 既有 secrets/env 慣例 | ✅ | 未來 provider key 只走 secrets/env |

### 6.2 Legacy / 可重用但不得直接當 OneBrain

| 現況 | 問題 | 方向 |
|---|---|---|
| `src/services/app_ai_service.py::gemini_call` | Gemini hard-coded；key pool／model list／HTTP／persona 混在一起 | Legacy transport；未來拆成 provider adapter / credential config / routing policy |
| `src/services/ai_fetcher.py::post_gemini` | 單一 Gemini transport，API version/model retry 規則 provider-specific | 可參考 transport retry semantics，不直接當 Provider Router |
| `dividend_station_service.build_ai_summary/build_summary_prompt` | prompt 與 domain/service 綁定；無統一 OneBrain trace/cache/grounding | 輸入 building block 可盤點；prompt 出口未來 replace |
| App／LINE 同摘要不同 persona/temperature | 同資料可能產生不同 AI 結論 | 未來統一 Brain 結果，再切 Local/Channel view |
| `weekly_review_service` 自建大盤定調 | 平行 deterministic semantics | replace / 改吃正式 rules + Digest |
| `ai_qa_service.run_agent` | 工具型獨立功能；會自行做方向判斷 | 不併入 OneBrain decision path；只可借用明確 degradation pattern |
| `ai_structured_summary` | tab/UI 字串導向 | 不作 Brain canonical input |
| `exit_signals.judge_news_sentiment` | AI sentiment 介入訊號 | 不得併入新 OneBrain safety path，需另 Decision Gate |

### 6.3 目前主要缺口

- ❌ Provider-neutral abstraction / Router。
- ❌ ClaudeProvider。
- ❌ OneBrain-level analysis fingerprint / cache。
- ❌ 統一 trace / audit record。
- ❌ token/cost telemetry。
- ❌ monthly/provider/per-analysis budget control。
- ❌ prompt/policy 集中 registry 與 version lifecycle。
- ❌ provider-neutral structured output schema。
- ❌ approved fallback policy runtime。
- ❌ headless production Decision Digest assembly（既有 contract 已列為 Phase 7 前置）。

---

## 7. Analysis Fingerprint / Cache

**禁止 UI reload 直接觸發 AI。**

OneBrain 的正式分析以 normalized semantic input 建立 fingerprint：

```text
analysis_fingerprint = hash(
  normalized_decision_digest,
  source_data_refs + source_as_of / version,
  analysis_type,
  prompt_version,
  policy_version,
  output_schema_version,
  model_configuration_if_semantically_relevant
)
```

至少考慮：
- 主要輸入資料。
- source data reference / timestamp / version。
- Decision Digest schema version。
- prompt version。
- policy version。
- analysis type。
- output schema version。
- 必要時 model configuration。

不得把純 UI/session 噪音放入 fingerprint：
- page reload。
- expander 開關。
- navigation。
- widget display state。
- presentation-only Top-N。
- 非語意排序／格式欄位。

流程：

```text
normalized input
→ fingerprint
→ 查最近一次 valid analysis
→ fingerprint 相同：cache hit，不呼叫 Provider
→ fingerprint 改變：才允許新分析
```

失敗結果不得冒充 valid cache；failure caching / backoff 需與「成功分析 cache」分開定義。

---

## 8. Trace / Audit Contract

每一次正式 OneBrain 分析至少可追溯：
- `analysis_id`
- `provider`
- `model`
- `analysis_type`
- `prompt_version`
- `policy_version`
- `output_schema_version`
- source data references
- `data_hash` / `analysis_fingerprint`
- source data timestamp / as_of
- request timestamp
- token usage（若 Provider 提供）
- estimated / actual cost（若可得）
- cache hit / miss
- fallback 是否發生＋from/to
- error / degradation reason

不得只保存「一段 AI 文字」。

Trace 禁止：
- API key / secrets。
- Authorization header。
- provider credential identifier 的可逆敏感資訊。
- 原始 secrets environment 值。

---

## 9. Cost & Budget Governance

成本原則：
- UI reload 不重跑。
- 背景無實質資料變化不重跑。
- Python 先做篩選、聚合、標準化，再送 LLM。
- 不把大量 raw data 無差別塞入 LLM。
- 同 fingerprint 優先 cache。
- 模型依任務複雜度 routing。
- 簡單分類不得固定使用最高成本模型。

模型 tier 僅是 policy 概念：

```text
simple → low-cost tier
normal → standard tier
deep reasoning → high-capability tier
```

不得把特定型號／價格寫死在 domain logic。

### 9.1 Budget Control 保留介面

未來至少保留：
- provider monthly soft cap
- provider monthly hard cap
- per-analysis max tokens / cost
- per-feature budget
- usage telemetry

達 hard cap：
- 不得偷偷改用更昂貴模型。
- 依核准 policy fallback；或 AI unavailable。
- deterministic data / rules 照常提供。
- 「AI 未執行」不得解讀成「安全」。

---

## 10. Prompt / Policy Governance

Prompt 不得散落在 Streamlit 頁面／UI component。

未來 repo layout 概念（實際位置 Phase B 再依 repo 現況決定）：

```text
onebrain/
  providers/
  routing/
  prompts/
  policies/
  schemas/
  cache/
  trace/
```

這是**概念邊界，不是本輪搬檔要求**。

每個 prompt/policy 至少有：
- version
- analysis purpose
- required inputs
- expected structured output schema
- missing-data behavior
- safety/domain constraints

任何 prompt 變更若會改投資語意／新增 vocabulary／改 safety boundary → Decision Gate。

---

## 11. Structured Output

正式 OneBrain 不以自由文字作唯一正式結果。

概念 schema：

```json
{
  "status": "<existing approved vocabulary only>",
  "confidence": "<only if existing formal semantics exists>",
  "evidence": [],
  "risks": [],
  "contradictions": [],
  "reasoning_summary": "...",
  "action_context": "...",
  "missing_data": []
}
```

硬規則：
- 只可用本專案既有正式詞彙。
- 不得自行新增投資狀態、UI 詞、決策等級、confidence 語意。
- 若需新增 domain vocabulary → Customer Decision Gate。
- evidence 必須可回指 Decision Digest / provenance / RuleRef。
- provider raw text 不是 final domain result；必須經 schema validation + grounding + safety checks。

---

## 12. Domain Safety Boundary

既有 deterministic safety logic 包含但不限於：
- Risk Cap。
- hard gate / risk downgrade。
- action matrix。
- candidate admission rule。
- strategy classification。
- regime / risk rules。
- formal provenance / freshness / missing contract。

OneBrain 不得：
- 繞過。
- 降低。
- 自行重算成另一套。
- 以「AI 覺得可以」覆蓋 deterministic safety result。

正確：

```text
Evidence
→ deterministic rules / safety constraints
→ OneBrain interpretation
→ final output still bounded by deterministic constraints
```

---

## 13. Provider Failure / Graceful Degradation

Provider failure 類型至少區分：
- timeout
- rate limit
- provider unavailable
- invalid response/schema
- policy disabled
- budget exhausted

降級順序：
1. cache 中同 fingerprint 的有效正式分析（若 policy 允許且仍有效）。
2. 已核准 fallback provider。
3. `decision_digest_summary.build_rule_summary` / deterministic explanation。
4. UI 顯示 AI unavailable / 無法判定。

任何降級都不得生成假的 HOLD / SAFE / neutral。

---

## 14. Secrets

未來 Provider API key：
- 不進 Git。
- 文件只寫變數名，不放真值。
- 不印 log。
- 不放 trace。
- 不進 AI output。
- 不拼進 URL/query string。
- 沿用 secrets / environment configuration 慣例。

本輪不要求任何真實 Claude key，也不改 production secrets。

---

## 15. 跨專案方向（只定相容邊界）

長期可以相容：

```text
             OneBrain concept
                  │
      ┌───────────┼───────────┐
      ↓           ↓           ↓
  my-stock     my-Fund      mynews
      └───────────┼───────────┘
                  ↓
           Provider Router concept
```

本輪禁止：
- 建第四個 shared repo。
- 強迫三 repo 共用 runtime。
- premature package/service abstraction。

何時才考慮 shared service/package：
- 至少兩個 repo 出現穩定、重複、已驗證的 Provider / trace / cache contract。
- 有實際 maintenance pain。
- 另走 Decision Gate。

---

## 16. 實作階段映射（沿用現有 Phase 7，不另創衝突主制度）

以下是 **Phase 7 內的 OneBrain 子批次**，不是新的平行 Phase 制度：

| 子批 | 內容 | Runtime? | Gate |
|---|---|---|---|
| OB-0 | 本輪：inventory / architecture / governance / ADR / backlog | docs only | 無 production enablement |
| OB-1 | Provider protocol + FakeProvider + provider-neutral schemas | minimal | 不接真 API |
| OB-2 | fingerprint/cache/trace/budget interfaces + tests | minimal | 不接真 API |
| OB-3 | ClaudeProvider Shadow | shadow only | 需 key/secrets Decision + manual setup |
| OB-4 | 選 1 個低風險 feature controlled integration | limited | Customer Decision Gate |
| OB-5 | evaluation：correctness / consistency / cost / latency / fallback / missing | evaluation | 不等於 production |
| OB-6 | production enablement | production | **必須另行客戶裁示** |

禁止跳過 OB-3/OB-5 直接 production。

---

## 17. 本輪禁止事項確認

本輪不得：
- 大規模 runtime implementation。
- 改 UI。
- 改公式／Risk Cap／既有決策結果。
- 新增外部資料源。
- 新增付費服務。
- 安裝 Provider SDK。
- 建 shared service。
- 寫 API key / secret。
- 改 production secrets。
- 建付費 fallback 帳號。
- 因 OneBrain 重構整 repo。

任何需要上述動作的工作只登 backlog / gate。

---

## 18. 本輪結論

### 已符合／可沿用
- Data ≠ AI 原則已存在。
- Decision Digest 已建立結構化、可追溯輸入骨架。
- One AI Brain / Local Summary slice 邊界已存在。
- grounding + rule-summary fallback 已存在。
- secrets 不進 Git 的既有方向可沿用。

### 衝突／技術債
- legacy Gemini transport/provider hard-coding。
- prompt/persona 分散。
- 同摘要不同 channel 可能因 persona/temperature 分歧。
- legacy AI 可能做方向分類／情緒訊號，不能直接併入新 Brain。
- 缺 provider-neutral trace/cache/budget/structured result runtime。
- Digest production headless assembly 尚未完成。

### 正式方向
**Data is evidence. Rules are constraints. OneBrain is reasoning.**

OneBrain 的責任是「在已存在的證據與規則邊界內推理、整合、解釋」，不是製造資料，也不是取代安全規則。
