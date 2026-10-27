# AB-1 Digest Builder 規格與調查結論（2026-10-27）

> **決策者：AI 總管內部（技術實作）；非客戶裁示；單組產出，未經第二組獨立驗證（CLAUDE.md §-2 規則 6）。**
> 本檔是交接用的**規格落盤**：新對話零記憶接手 AB-1 時，以本檔為設計依據。
> 下列「調查結論」是兩組獨立**唯讀**調查的產物，其中的全稱句（「沒有」「只有」「全部」）均為**單組窮舉、待驗**，不得當成已查證事實引用。
> 來源背景：AB-0 契約已合併（PR #949，main `894b2f49`，`shared/decision_digest.py`；DEC-092 Q3／Q4、DEC-093）。AB-1 = 在該契約上建 Builder，**不重新定義 Decision Digest 語意**。

## 0. 客戶指示（2026-10-27，Sonnet 5.5／Medium）

在已合併的 AB-0 契約上建 AB-1 Digest Builder，不重新定義 Decision Digest 語意。範圍：

- Builder；**正式 `rule_id` 允許名單**（取代 AB-0 盡力而為的拒收名單，成為**主要治理**）；落實 DEC-092 Q4 既有建議動作優先序。
- ⛔ 不新增投資規則、不做 AI 出口、不做 UI；不碰 `app.py`／`shared/ia_nav.py`；不定義 `portfolio_id` 來源；不寫 Sheet；缺值／availability 語意沿用 AB-0 不變。
- 完成後：獨立 QA → 依風險補測試 → CI → Auto-Ship → 同步 DECISIONS／BACKLOG／PROJECT_STATE／HANDOFF。Silent Autonomous Cruise。
- 之後客戶為交接停止本 session（察覺語言漂移／巡航規則漂移）：「請不要再繼續 AB-1 實作」。

## A. 調查結論（2026-10-27，兩組獨立唯讀調查；單組、全稱句待驗）

### A.1 既有「建議動作」產生者

- `src/compute/etf/dividend_station.py` 的 `suggest_action(a)` 與 `action_branch(a)`（約 L742–800）。分支碼 `ACTION_*`：`cut`（汰弱，tier1）／`take_profit_force`、`take_profit_partial`（停利，tier2）／`pause_add`（趨勢暫停，tier3）／`add`（加碼，tier4）／`premium`／`cruise`（**後兩者不在客戶的順序內**）。
- `action_branch` 的 if 鏈順序**就是**優先序；程式內**沒有**任何 rank／priority SSOT 常數。
- 客戶順序文字「汰弱＞停利＞趨勢暫停＞加碼」出現在：C §4（`NEWUI_D25_C_AI_BRAIN_DATA`，ActionRef 列）、C §11 第 16 列、程式 docstring。DEC-092 Q4 本身只寫「沿用既有已正式存在的建議動作與既有優先序」＋ AI「不得創造既有規則層沒有產出的買賣動作」。
- 列來源：`src/services/dividend_station_service.py` `row_from_assessment`（約 L66–77）：鍵 `"建議動作"`（逐字，常為動態 f-string，**必須原樣攜帶，不得重組**）與非顯示鍵 `"_action"`（分支碼）。`build_station_digest(rows, vix)`（約 L1219）是 `_action` 的既有消費者。
- **不攜帶（v1）**：個股路徑（`assess_stock` 換股字串，無分支碼、無 Q4 rank）與 `flag_take_profit`（衛星 ≥15%，`SATELLITE_TAKE_PROFIT_PCT`，另一個產生者、rank 未定義；C §9 HI-3 稱 cited-not-extended）。若客戶要，須客戶裁示（見 BACKLOG `AB1-STOCK-PATH-AND-TAKE-PROFIT-RANK`）。`unified_verdict` 是另一套三態引擎，不是建議動作。
- 動作規則版本：程式內**無**既有版本常數 → AB-1 內部標籤 `action_branch.v1`（內部命名決定，記入 DEC-094）。既有識別字：`RISK_CAP_RULESET_VERSION="risk_cap.v2"`（`shared/risk_cap_policy.py:30`；rule_id `risk_cap` 僅存在於文件）；`SHADOW_POLICY_VERSION="c2a-shadow-1"` **與 risk_cap 無關，不得使用**。
- AB-0 測試夾具用臨時 rule id（`rule_x`、`allocation`、`risk_cap` …）→ 允許名單**不得**接進 `validate()`／`RuleRef.__post_init__`；另設 `validate_rule_ids`、`validate_action_order`、`validate_strict`。

### A.2 日期／出處缺口

- `get_macro_state`、`get_allocation`、`build_station_digest`、`compute_industry_concentration`、`get_ranked_picks` **皆不回傳** `as_of`／`fetched_at`。唯一現存日期是 `risk_cap_disclosure.snapshot_ts`（台北 `%Y-%m-%d %H:%M:%S`，僅在 `require_valid_risk_cap=True` 且快照被接受時才有）。
- AB-0 要求 ok／stale 的 fact 必有 `as_of` → 無日期的輸出不可能是 `ok`。
- **決定**：Builder 從不自編日期；呼叫端對每個來源明確傳 `SourceStamp(source, as_of, fetched_at)`；沒有 stamp ⇒ MISSING／NO_INPUT（取捨已記錄：安全降級，不是值的謊言）。
- 從既有服務加回 `as_of`（加法式，依 PLAN §5 須獨立 QA）＋讀 session 的包裝層＝後續 `AB1B`（BACKLOG `AB1B-EXPOSE-AS-OF-AND-WRAPPER`）。

### A.3 Risk Cap 對映

- `cap_pct` ← `macro_state['exposure_limit_pct']`（**不是** `AllocationDecision.cap_pct`，那是多個上限的 min）。
- `exposure_lo/hi_pct` ← `allocation.final_lo/final_hi`，**僅當** `allocation.is_loaded`。
- `cap_valid` 是 **PROXY**（`exposure_limit_pct is not None` 且 disclosure 帶 `snapshot_ts`），因為沒有直接旗標可讀。
- `stale` 在沒有新讀取路徑前**不可達**；真正的 0 維持 ok／0，None 維持 missing；**不得**呼叫 `is_valid_risk_cap_snapshot` 或重讀檔案。

### A.4 持股

- `HoldingsResult.holdings` 的列（ticker, name, held, asset_kind, asset_class, lots, avg_price）**沒有** portfolio_id；`portfolio_name` 是顯示名，**絕不可當鍵**（鍵來源由 AB-4r 負責）。
- 因此在 AB-4r 之前，production 的所有持股列都無鍵 ⇒ holdings UNAVAILABLE ＋ `unkeyed_count=N`；而 AB-0 規則「actions AVAILABLE 須 holdings != UNAVAILABLE」⇒ actions 也必須 UNAVAILABLE ⇒ **Q4 排序已實作、已測，但 production 在 AB-4r 前不可達**。
- Builder 接受呼叫端可選的 `holding_keys: Mapping[symbol, HoldingKey]`（預設 None），讓排序可測而不必定義鍵來源。

### A.5 分層／可測性

- L3 service 只要 import 那五個函式，就會經 barrel 拉進 streamlit／pandas（import 時無網路）。故 Builder 是**純函式**，所有輸入皆注入（無 streamlit、無檔案、無 session）。
- `get_ranked_picks` 離線不安全，除非注入 `survivors_df`、`pe_map`、`name_map`、`shortage_rows=[]`、`rs_rows=[]`、`trend_map={}`、`auto_fetch=False`；`get_allocation` 讀 `st.session_state`。
- 產業集中度與 ranked picks 在 AB-0 契約**沒有對應段落**（C §11 第 4／14 列）→ **不攜帶**（補回＝BACKLOG `AB1-RESTORE-DROPPED-FIELDS`）。五桶危險摘要（`compute_five_bucket_summary`，`macro_helpers.py:1677`）與關鍵警示不在那五個函式內 → v1 不含。

## B. 已定案設計（照做；偏離 → 回報總管／走 Gate）

### B.1 新 L0 `shared/decision_digest_rules.py`

- 只能 import stdlib＋`shared.decision_digest`；須通過 `tests/test_c3_layering_guard.py`。
- `RULE_ID_ALLOWLIST`（rule_id → 允許的版本集合）：**只收程式裡已存在的識別字**——`risk_cap`→{`risk_cap.v2`}；五個動作分支碼 `cut`／`take_profit_force`／`take_profit_partial`／`pause_add`／`add`→{`action_branch.v1`}；`premium`／`cruise` **刻意排除**；不收任何推測性成員。市場事實僅在 `Fact.rule` 對非數值事實為可選時才不帶 rule；**不得發明 rule id**。
- `Q4_ACTION_PRIORITY`：汰弱:{cut} → 停利:{take_profit_force, take_profit_partial；force 先於 partial} → 趨勢暫停:{pause_add} → 加碼:{add}，附出處引註。
- `validate_rule_ids`／`assert_rule_ids_valid`；`validate_action_order`（依 tier 排序、`priority_rank` 嚴格遞增＝位置 1..n、長度 ≤ `MAX_ACTIONS=3`、動作 rule 在允許名單內）；`validate_strict`／`assert_strict` = AB-0 `validate` ＋ 以上兩者。
- **不改** AB-0 `validate()` 簽名與 `RuleRef`。Docstring 寫明：允許名單是**主要治理**；AB-0 拒收名單維持盡力而為的縱深防禦。

### B.2 新 L3 `src/services/decision_digest_builder.py`

純函式 `build_decision_digest(*, generated_at(UTC), macro_state, macro_stamp, allocation, station_rows, station_stamp, holdings_rows, holding_keys=None) -> DecisionDigest`：

- **市場事實**：`macro_state` 的 regime／light（文字逐字）與 health（有限數值）；僅在有 `macro_stamp` 時為 OK；unknown／⬜ 不得映射成值。
- **risk_cap**：依 A.3 對映；`snapshot_ts` 以台北日期解析（台北 D 日 23:30 ⇒ as_of=D）。
- `tw_trend`／`intl_trend`／`industry` 恆 NOT_DEFINED；`valuation` 恆 RESEARCH_ONLY。
- **holdings**：僅經 `holding_keys` 取鍵；strategy 恆「未分類」；無鍵者計入 `unkeyed_count`；`holdings_rows=None` ⇒ UNAVAILABLE／NO_INPUT 且 `unkeyed_count=0`（未知，不是零）。
- **actions**：只取 `_action` 屬五個允許分支碼、無 `_detail.error`、持股有鍵且有 `station_stamp` 的列；每筆動作 = 持股項 Fact（text＝`row["建議動作"]` 逐字、OK、as_of 來自 stamp、rule＝(分支碼, `action_branch.v1`)）＋ ActionRef（origin RULE_LAYER、同 text、target HoldingKey、evidence_refs 指向該 Fact）；依 Q4 tier 排序、rank＝位置、**截斷至 3**（已文件化；上游仍保留完整清單）。
- `ai_participation` = RULE_ONLY；結尾 `assert_strict`（fail loud）。

### B.3 必備測試

允許名單接受／拒收；跨 tier 排序；截斷；逐字文字對照**真實引擎**（真 `HoldingAssessment`／`row_from_assessment`／`action_branch`），含**釘住測試**：`Q4_ACTION_PRIORITY` 與 `action_branch` 解決競爭條件的方式一致；無鍵列計數而非捏造；`portfolio_name` 絕不當鍵；無 stamp ⇒ MISSING；Risk Cap 0 vs None；台北日界；allocation 未載入 ⇒ lo/hi missing；holdings UNAVAILABLE 時 actions UNAVAILABLE；輸出通過 `validate_strict` 且 `to_dict` 可 JSON 序列化；AST 鎖（Builder 不 import streamlit／`src.ui`；`app.py`／`shared/ia_nav.py` 不 import Builder——僅直接 import）；**每個守衛必做突變檢查，零倖存**。

### B.4 驗證指令與範圍

契約＋rules＋builder＋layering guard＋boot smoke，再 fast lane（`-m "not slow"`，deselect 那 1 個需 `markdown_it` 的測試）；與 main 的 diff **只能**碰 4 個新檔（外加 repo 守衛要求的最小登記，若有）。

## C. 狀態與下一步

- 4 個 WIP 檔（`shared/decision_digest_rules.py`、`src/services/decision_digest_builder.py`、`tests/test_decision_digest_rules.py`、`tests/test_decision_digest_builder.py`，合計 1,415 行）由實作組子代理寫成後被總管依客戶指示中止；**從未完整跑過測試、突變檢查或 QA，一律視為不可信草稿**。其位置見 `docs/HANDOFF.md` Resume Checkpoint（branch `ccr-fa5b6ded-9rhvoj`／`WIP(AB-1)` Draft PR，**以 GitHub 實況為準**）。
- 接手第一件事：對照 B 節**審查** WIP → 跑測試與突變檢查 → 兩組獨立 QA（對抗式＋語意）→ CI → merge；之後寫 DEC-094（內部決策：允許名單、`action_branch.v1` 標籤、SourceStamp 原則、premium／cruise 排除、截斷、無日期⇒missing）並同步 docs。
- 可能需要客戶 Gate 的未決事項（客戶若要才問）：個股路徑換股動作與 `flag_take_profit` 相對 Q4 順序的排位；停利 force vs partial 子序（目前以程式順序作實作細節）；無日期服務是否應暴露 `as_of`（AB1B）。
- 升級條件：若碰到 Risk Cap 讀取語意、新增來源、或需要規則語意 → **停手重判**，不得自行拍板。
