# OneBrain Evidence Coverage / Digest 正反證契約草案（2026-11-06）

> **CANDIDATE / DESIGN GATE / 未核准 schema 或 runtime 施工**。設計主責 ChatGPT；Claude Code 負責程式可行性、原始 schema 對照、測試與審查。依 DEC-128、DEC-136、#1030 DEC-142 草案及 DEC-143 客戶要求。相關實務證據：#1033 的《SUPERSESSION_AND_DATA_GAP_AUDIT》§G～I。這不是把來自基金專案的公式搬進台股。

## 一、責任邊界（不可互換）

`Canonical Source Data → Deterministic Validity/Calculation → Evidence Registry (候選持久化/索引層) → Decision Digest（完整可追溯語意） + Human UI ViewModel（精簡顯示） → 單一 OneBrain 六領域按需分析 → Global Reviewer → System Action Authority / Risk Cap`

- **Source Data**：來源只負責取用、清理、標準化、可追溯與時間同步；L0/L2 原有核准公式不改。
- **Evidence Registry**：此層在 repo 內尚無已確認 production 實作；不等於 `RULE_ID_ALLOWLIST`。可先做 immutable `EvidenceSnapshot`＋stable `evidence_id` 規格，不預設必須新建資料庫或跨 repo schema。
- **Decision Digest**：既有 builder/schema/validator 仍需 production caller；不可宣稱現有完整 Digest 已讀取正反證。新增欄位需獨立 versioning、migration、compatibility 和 security Gate。
- **OneBrain**：只讀核准 Evidence，不自連新來源、不改寫/發明事實、不決定風控豁免、不寫回。Global Reviewer 必須根據來源 evidence ID 比對反證，而非僅讓 LLM 對文字自我肯定。
- **Action**：Risk Cap、唯一動作權威仍由 deterministic 決策邏輯決定，AI 語言建議不可視為交易指令。

## 二、Evidence Registry 每一筆最小候選欄位

| 欄位 | 說明與限制 |
|---|---|
| `evidence_id`, `schema_version` | stable 唯一 ID、版本；防重、跨頁 trace |
| `domain`, `subject_type`, `subject_id` | market/chips/financial/industry/holdings/data_audit；市場／股票／產業／組合等 |
| `metric_id`, `value`, `unit`, `period_kind` | canonical 語意、數值含 true 0、單位及 point/quarter/TTM/forward 等 |
| `observation_date`, `period_start`, `period_end`, `fetched_at` | 完整分離資料日、期間與拉取時刻，避免錯期；timestamp 帶 timezone |
| `source_id`, `source_locator`, `source_tier`, `source_version` | 一手/第三方/推論；URL/文件/發布日期，不保存 secret |
| `data_status`, `reason_code`, `coverage`, `freshness` | 觀測成功 / missing / stale / unavailable / not_verified / proxy / not_applicable；`reason_code` 可追溯。不得用 missing→0/neutral/safe |
| `calc_rule_id`, `calc_version`, `assumptions`, `dependencies` | 取樣/衍生/公式版本、時間對齊和依賴證據 ID；保留受限性 |
| `claim_id`, `claim_status`, `supports_claim` | 已確認事實／有限代理／研究假設，並標對正反結論的證據支持方向 |
| `contradicts_evidence_ids`, `limitation_codes` | 反證／限制來源，不能以缺資料當反證為 0 |
| `lineage_hash`, `snapshot_as_of` | stable fingerprint，區分 cache/新鮮度和重跑；不包含憑證與隱私 |

**實作前必須以現有 model/schema 做欄位表對照**，避免 duplicate storage、超額 token、與已 frozen VM/Digest contract 衝突。

## 三、Coverage Manifest 與分包策略

- `required_evidence_manifest` 描述 **所需資料類別/最低時效/必要來源/計算資格**，不是一張 UI Top-N 清單；按頁 scoped domain 讀取。
- `read_manifest` 應逐筆列 `required`、`available`、`read`、`excluded`、`unavailable_reason`、`omitted_count`、`omitted_ids_or_pagination_cursor`、`coverage_status`。
- `coverage_status` 建議 `COMPLETE | PARTIAL | UNAVAILABLE | INVALID`；每個域也須帶完整性，**不能用 AI 自評的「我看完」代替 deterministic Gate**。
- **分包可回查**：Token budget 超限時依 evidence_id/頁面游標分批讀取、暫存 fingerprint，所有 required 全讀完才能 Complete；真的讀不完標 PARTIAL，明確列仍未讀的來源與風險，不得 silent truncate。
- 候選 `MAX_ACTIONS=3` 僅可視為**畫面/動作展示上限**的研究議題；現有 builder 若真的在 Digest 形成前截掉候選，則需要 `total_action_candidates`, `shown_action_candidates`, `omitted_count`, `omitted_reason`, `omitted_manifest_ref` 等揭露或另建完整 evidence ledger。**不要未核准就把 MAX_ACTIONS 由 3 調大**；要另外檢查其為安全限制還是 UI 呈現限制。
- 以最低 token 策略做 `Decision Digest` 索引及精簡聚合，異常可按 evidence_id 拉回，並以 deterministic coverage 驗證完整性。

## 四、資料有效性與模型降級（不是更改正式分數）

| 情境 | 候選資料狀態 | 可顯示／不可宣稱 |
|---|---|---|
| 月營收或季報未取到 | MISSING/INSUFFICIENT | 顯示缺資料與哪些腿；不能導出中性／穩定／無缺貨 |
| 缺貨四腿只部分可用 | PARTIAL/PROXY | 可保留**疑似供需足跡研究**，不能說已證實缺貨或大訂單、也不能有正式動作 |
| 財報單季/累計無法對齊 | INVALID_PERIOD | 暫停相關比率及跨期結論；先驗證 source period，無法判定 |
| ADL 指數估算當廣度 | PROXY | 顯示代理性，正式 Risk Cap 資格須已有核准條文 |
| Digest builder 的候選截斷 | PARTIAL + OMITTED | 不向 OneBrain 宣稱讀到完整證據；保留省略來源和再讀路徑 |
| 沒有 Evidence Registry 或 production caller | NOT_IMPLEMENTED | UI「尚未提供」、不得假冒空的 Complete Digest |

## 五、正反證與產業實例

- **「疑似缺貨」研究 claim**：財務足跡（合約負債、毛利率、存貨天數、營收）是間接 evidence；反證如產能擴張後庫存回升、毛利壓縮、訂單取消、公司否認等需官方/可核對來源。缺反證來源標 `NOT_EVALUATED`，不可視為「沒有反證」。
- **大單**：單獨標示 `official_disclosure / management_guidance / broker_forecast / rumor` 和 `verified / unverified / contradicted`；財報發生值與未來訂單不可混在同一 measurement。
- **財報跨期**：月/季有效期間、缺腿與財會差異須可追溯；混合比率不得憑空轉年化。
- **大盤 EPS×PE**：若無大盤 forward EPS 的正式來源，研究情境只能保留 `assumptions`、來源、期別、估值倍數和完整性狀態，不能提供正式價位。

## 六、Gate 與下一步

1. ChatGPT 完成 **Existing Registry/Digest mapping + schema diff**，先檢查 repo 是否已有可重用的 class/adapter，避免建新真相表。
2. Claude Code 只讀驗證 `MAX_ACTIONS` truncation 位置、缺值/反證/資料日 coverage 和 version migration 相容性，回傳可重現證據及 3 種實作比較（完整性/速度/Token）。
3. 需客戶授權新 schema/模型語意/production caller/資料來源/Token 成本後，另開 High effort 工程 PR，targeted + full QA + mutation + CI。任何正式 Risk Cap／唯一行動權威都不在本 Draft 施工範圍。

**仍未完成**：真實資料 API live probe、FinMind 現金流口徑核對、production Evidence Registry、Digest 接線、正反證校驗與全域 OneBrain 實際運行。
