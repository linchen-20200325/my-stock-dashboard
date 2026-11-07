> **歷史／適用性引言（2026-11-07 抽出）**：本檔自 Draft PR #1030（head 1e5afee1） 原內容抽出保存（來源分支 `docs/newui2-data-page-trend-onebrain-pdf-20261106`），抽出日期 2026-11-07。
> 此為歷史草案／研究材料，**不是現行施工依據**；現行方向以 DEC-142／DEC-146 與 `NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md` 為準。

# OneBrain 證據覆蓋與 Token 預算治理｜短／中／長（2026-11-06）

> 使用者最新裁示方向：**前瞻分析名稱為「短期／中期／長期」，取消「3／6／9 個月」固定顯示**。完整語意 evidence 不因單頁或 context-window 限制遺失；OneBrain 僅使用資料層提供／核准的來源。此文件為 docs-only 架構增補，須依既有 GitHub Decision Gate 登記正式裁示；不得自行修改既有 Runtime／Risk Cap／Digest schema。
>
> **衝突處理**：同 PR 早先 `ONEBRAIN_INPUT_ISOLATION_AND_3_6_9_HORIZON_2026-11-06.md` 及其他 `…CHIPS_OVERNIGHT…` 文件的「3／6／9 個月」均屬**已被本次客戶新方向取代的歷史草稿**；保留歷史來源以供稽核，未來施工以本新文件的「短／中／長」為準。短／中／長的精確日數、公式、信號門檻**尚待獨立定義與核准**。

## 1. 需要防止的兩種失真
1. **Human UI visibility ≠ OneBrain data visibility**：市場/標的/持股/我的/資料五頁各只是讀取共用 canonical/VM 的呈現，不能拿每頁卡片文字、Top 10、目前畫面 DOM 或頁面專屬 session 當 OneBrain 全部輸入。
2. **完整證據 ≠ 全部原始 blob 一次餵模型**：輸入 token 限制不應靠砍掉反證、完整來源或風險欄位來解決。完整保存結構化 facts、evidence IDs、來源與時間、證據關聯、缺失矩陣；每次推理只送經權限控制的必要投影與可按需檢索的內部證據。

## 2. 三方案
| 方案 | 問題 | 評估 |
|---|---|---|
| 一次送全庫到一個 Prompt | context overflow、成本、遺漏/中途截斷、時效混淆 | 不採 |
| 每頁獨立 AI 摘要並做平均/拼貼 | UI truncation、跨頁反證遺漏、無總證據覆蓋 Gate | 不採 |
| **一份 headless Complete Evidence Ledger + 分域 evidence packs + 分層分析 + 全域整合 + coverage check** | 需多一層可驗證的 orchestration，但可分批、cache、按需檢索 | **推薦** |

## 3. 建議管線（設計，未授權施工）
```text
Approved data adapters (external data access only here)
  -> validation/normalization + timestamps + provenance + safe scraping constraints
  -> canonical facts + approved event facts
  -> deterministic domain / existing Risk Cap / System Action authority
  -> immutable/versioned headless Complete Evidence Ledger / Digest
     |-- ledger: every required evidence_id, source/as_of, status, links, positive & negative
     |-- availability matrix: required/available/missing/stale/not_evaluated/blocked
     |-- market & chips pack
     |-- fundamentals & valuation pack
     |-- industry / approved news / orders pack
     |-- holdings & risk pack
           |
           v
    constrained analysts (optional per domain, no external fetch)
           |
    typed, evidence-cited summaries with unresolved facts and counter-evidence
           |
           v
    single integrator -> short / medium / long research narrative and limitations
           |
    deterministic coverage checker -> only then release complete / partial / unavailable
```

- **不能只靠模型口述「全部讀完」**：Required Evidence manifest 必須獨立於 LLM 建立；包含 source、producer、domain、as_of、freshness、claim/evidence_id、contextual relevance、negative evidence、status，以及版本/hash。模型輸出 reference ID 必須可反向驗證存在且確實供給模型。
- **層級檢索**：先送摘要 + 全域索引；遇到風險分歧、未解矛盾、關鍵催化劑，從**已批准且已落在資料層**的 Evidence Store 按 ID 取原文/必要明細。不能用 Browser、web search、LLM 外部 API、未核准的新資料源補洞。
- **分域預算**：按來源重要性/風險與量選取 evidence chunks；硬 token 上限保護；若溢出，分批重試或改回部分分析，**不可 silent truncation**。必要反證、缺資料、Risk Cap 不可壓縮消失。
- **成本策略**：正常情況優先 rule-based/typed deterministic summaries；增量 snapshot/hash cache；只有資料變化或指名必要時呼叫分域 LLM，多模型呼叫不是強制設計。
- **執行安全**：OneBrain runtime 預設無任意網路能力/搜尋工具/檔案寫入權限；唯一 approved internal evidence reader scoped read-only。不得直接呼叫 data fetchers、改 canonical / Rule IDs / Risk Cap / System Action。
- **投資語意**：LLM 只分析解釋、呈現可核實研究假設，不授權新的預測公式、數值信心/概率、買賣動作；不將「資料未見」變「安全」或「持有」。

## 4. 短、中、長三種研究視角（不是固定 3／6／9 個月）
- **短期**：隔夜美股、外資買賣超、籌碼轉折、近期事件與突發風險。可自用短窗時間框架，但精確起訖尚未核准。
- **中期**：月營收、季度 EPS 與估值、訂單轉營收、資金與景氣方向、公司營運變化。
- **長期**：產業供需、缺貨/大單落地、AI/CSP CAPEX、產能/良率、技術世代、FCF/競爭反證。
- 各視角必須標 claim、支持與反對證據、資料時點、missing/blocked、需要驗證的事件，**允許短弱中強長正同時出現**；不得自動映射成三套 System Action。

## 5. 驗收與停手條件
1. 建立 **Required Evidence Coverage Matrix**：source/domain/required/available/processed/referenced/omitted_reason；missing、unavailable、not evaluated 各自計數，zero ≠ N/A。
2. 至少驗證：UI 故意只畫 Top-N 時，Digest/OneBrain 仍可讀完整 required evidence；壞消息加入後不能因 token cutoff 消失。
3. 資料量超出模型上限時，**必須分批或回報 partial**；記錄 input_manifest_version、token budget、產生時間、使用 model/effort、失敗缺口及完整反證索引。
4. 每個研究結論都要指回可追溯 ID，驗證 claim 是否來自已批准且已提供的 evidence；缺少的公司訂單不准讓 AI 自己搜尋。
5. 若已有正式投資決策／風險引擎須由 Single Action Authority 決定，AI 不可另行產生越權 trade recommendation。
6. 進行真正 runtime adapter、Evidence schema、權限封鎖或跨模組修改前，需另案 **High Gate + 完整 QA**；本文件不提供施工授權。

## 6. 預覽稿
獨立 HTML（未入 GitHub）更新為 v0.7「短／中／長期」；不代表真正的 OneBrain runtime 已分域運作或已通過 coverage 驗收。
