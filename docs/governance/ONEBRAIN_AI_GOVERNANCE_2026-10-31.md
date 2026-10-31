# OneBrain AI Governance（2026-10-31）

- **性質**：治理規則補充；不取代 `PROJECT_RULES.md`、既有 DEC、Decision Digest Contract 或 One AI Brain Boundary。
- **適用**：未來所有 OneBrain / Provider / prompt / AI analysis runtime。
- **本輪**：docs-only；不得因此啟用任何真 Provider。

## G1｜核心原則

**Data is evidence. Rules are constraints. OneBrain is reasoning.**

Data layer 只負責取得、清理、標準化、驗證、provenance；deterministic layer 負責公式、指標、門檻、Risk Cap、分類與安全規則；OneBrain 只在 evidence＋constraints 內推理、整合、解釋。

## G2｜Missing / unavailable

OneBrain 不得把 missing 當 0、unavailable 當 neutral、not evaluated 當 safe，也不得因資料不足推論「無風險」。必要 evidence 不足時必須回既有正式 Missing／「資料不足／無法判定」語意。

## G3｜Deterministic-first

凡可由 Python / formal rule 確定性計算者，不使用 LLM 重算或取代，包括 EPS、報酬率、技術指標、排名、門檻、Risk Cap、日期/freshness、schema validation 與可公式化財務模型。

## G4｜Provider-neutral

- Domain logic、UI、data module 不得依賴特定 Provider 類別或模型名稱。
- Provider 由 Router + configuration/policy 管理。
- Claude API 是目前規劃 Primary，不是永久 domain dependency。
- Fallback 必須先有核准 policy；不得自行轉用更昂貴 Provider/model。
- 本輪不得為 future providers 一次加入全部相依套件。

## G5｜Cache / Fingerprint

- UI reload/session refresh 不得觸發新 AI call。
- 同 semantic input＋prompt/policy/schema 版本優先 cache。
- fingerprint 必須忽略純 presentation state（導航、expander、UI Top-N、session refresh）。
- failure/backoff 與 successful analysis cache 分開處理。

## G6｜Trace / Audit

正式分析至少記錄 analysis id、provider/model、analysis type、prompt/policy/schema version、source refs/as_of、fingerprint、request timestamp、usage/cost（若可得）、cache/fallback/error/degradation metadata。敏感憑證資訊不得進入 trace、log 或 AI output。

## G7｜Budget

未來須保留 soft cap / hard cap / per-analysis cap / per-feature budget / usage telemetry。達 hard cap 時只可依核准 fallback policy，或降級為 AI unavailable；deterministic data/rules 必須仍可用；不得偷偷升級更高成本模型。

## G8｜Prompt / Structured Output

- Prompt/policy 集中管理；不得散落 Streamlit page/component。
- Prompt 至少有 version、purpose、required inputs、missing behavior、domain/safety constraints、output schema。
- 正式輸出優先 schema-based，不以自由文字作唯一 domain result。
- 不得自行創造新投資狀態、confidence、UI vocabulary、決策等級；需要新詞 → Customer Decision Gate。

## G9｜Safety precedence

若 OneBrain output 與 deterministic Risk Cap / hard gate / action matrix / admission rule / formal provenance rule 衝突：**deterministic safety logic 永遠勝出。**

## G10｜Production enablement

Provider abstraction、Shadow、controlled integration、evaluation、production enablement 必須分階段；任何 production enablement 都要另行客戶裁示。本治理檔不構成正式 Provider 啟用、正式憑證配置、付費 fallback、投資語意或 Risk Cap 變更授權。
