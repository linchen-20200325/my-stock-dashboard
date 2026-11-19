# 【CANDIDATE／NOT ENABLED／NO CODE／非施工授權】OneBrain OB-2 性質規格與可失敗負例（未來 tests oracle 候選）

> 2026-11-19｜基準 main `f86e62e7`｜授權 #1199 comment `7011701691` 裁示 3（選 C；**OB-2 code／B′ HOLD**）。本文是**規格候選**：不是 OB-2 授權、不是 schema／演算法凍結、不是 OneBrain 功能完成。零 code、零 SDK／網路／Secrets／費用；Digest v1、`ProviderRequest`、`ShadowOutcome`、`run_shadow` 簽名不動。
> 標記：**〔F〕**事實（`file:符號` 或 comment id）｜**〔I〕**推論｜**〔NV〕**NOT VERIFIED。`c7011701691`＝#1199 comment 7011701691；`c7011572090`＝同 issue comment 7011572090（OB-2 Gate 候選；**其「四項離線可行性表」「6 護欄」「假安全風險」不在此重抄，視為前置閱讀**）。取值註記：**〔預設〕**＝規格預設（可被推翻、不凍結）｜**〔待裁〕**＝待使用者／總管裁示（未裁前以〔預設〕的 fail-safe 方向執行）。單組作者撰寫，未經第二組複驗。

## 0. 本文新增的規範（相對 c7011572090 的差額）
c7011572090 回答「離線可不可行、紅哪些守衛」；本文補它**沒有**的：(a) 可直接轉測試的**性質＋可失敗負例**（§2–§6）；(b) `fetched_at` 納入／排除**決策表**（§2 P-FP-4）；(c) 數值正規化規則（P-FP-5）；(d) 離線可證／需 runtime 對照（§7）；(e) 守衛逐項紅燈點與白名單同步清單（§8）；(f) 下一個最小 code gate（§9）。
**總原則 P-0（fail-safe 方向）**〔預設〕：**指紋／cache 寧可「多不同」（多一次 miss＝多一次 Provider 呼叫＝僅成本）**，不可「少不同」（誤命中＝把舊解釋當新資料＝§1 造假）。凡規格有歧義，取「更易 miss」的一邊。

## 1. 格式
**命名聲明**：本文中的 `CacheStatus`、`AnalysisTrace`、`BUDGET_DENIED`、`BUDGET_POLICY_ERROR`、`FingerprintError`、`AnalysisCache` 等列舉／類別／檔名皆為**候選名稱，非 schema 或 API 凍結**。
每條：**ID｜性質｜可失敗負例（輸入→預期）｜驗證面**（**〔離線〕**＝純 pytest 可證；**〔RT〕**＝需真 Provider／runtime，見 §7）。「指紋函式」＝未來 `f(digest, analysis_type, policy_id, prompt_version, provider_tag, algo_version)→str`，僅為敘述，**名稱與簽章不凍結**。Digest 先經 `assert_valid`〔F〕；無效 → 不產生指紋（P-FP-8）。

## 2. P-FP｜指紋（**指紋層**：純函式性質，是 §9 fingerprint-only gate 的驗收範圍；涉及 cache／Provider 呼叫的**編排層**性質已移至 §3、§6，屬後續 gate）
| ID | 性質 | 可失敗負例（輸入→預期） | 面 |
|---|---|---|---|
| P-FP-1 | 決定性：同 semantic input（含 deepcopy／重建／跨進程／不同 `PYTHONHASHSEED`）→ 同指紋；實作不得用內建 `hash()`、`set` 迭代序、`repr` of dict | `make_digest()` 與其 deepcopy→相等；兩個 `PYTHONHASHSEED`（0、1）子進程→相等；實作改用 `hash()`→紅 | 離線 |
| P-FP-2 | **欄位完備（反射）**：對 `dataclasses.fields` 遞迴枚舉 Digest 全部葉欄位，每個欄位必須在「納入／排除」表中**顯式分類**，無預設分支；新增 Digest 欄位未分類→測試紅（不得被靜默忽略） | 測試內以 stub 加一個未分類的假欄位→紅；從納入表刪 `rule_version`→突變測試紅 | 離線 |
| P-FP-3 | **逐欄突變必變**（納入欄位，c7011572090 已列）：source、as_of、status、missing_reason、value、text、unit、rule_id、rule_version、cap_valid、holdings 鍵／strategy／strategy_source、actions 全欄、schema_version、各段 availability／missing_reason；另含 `analysis_type`、`policy_id`、`prompt_version`、`provider_tag`、`algo_version`、output schema 識別 | 逐欄突變一格→指紋≠原值；`status` ok→missing（value→None）→變；只改 `missing_reason` NO_INPUT→FETCH_FAILED→變；缺值 vs 0：value=None(missing) vs value=0.0(ok)→不同 | 離線 |
| P-FP-3b | 排除欄位（**僅**這些）：`generated_at`、`ai_participation`、`ai_passed_checks`、`ai_failed_checks`（回寫狀態，納入會循環）；`fetched_at` 依 P-FP-4。UI／session／widget／導覽狀態**不得是函式輸入**（型別層即不可能） | 改 `generated_at`→不變；改 `ai_participation` RULE_ONLY→AI_REJECTED（並補 failed_checks）→不變；函式簽章含 `**kwargs`／`session_state`→紅 | 離線 |
| P-FP-4 | **`fetched_at` 決策表**（見下）；`generated_at` 不得被當歷史 `published_at`，指紋與 cache 皆不得用它推「發布日」 | 見下表負例 | 離線（規則）／RT（真來源行為） |
| P-FP-5 | **數值規則**〔預設，不凍結演算法〕：(i) **精確 deterministic 正規化，不四捨五入**（如 `float.hex()` 或 shortest-repr；兩個不同 float 必不同）；(ii) NaN／±inf→**raise，不 hash**；(iii) `-0.0`≡`0.0`（正規化 `+0.0`）。⚠️ 〔F〕`DecisionDigest.to_dict()` 對 `-0.0`／`0.0` 輸出不同（`float(-0.0)` 序列化為 `-0.0`；QA 實測），故指紋**不可**直接 `json.dumps(to_dict())`，須先自行正規化數值再序列化；(iv) `None`≠`0`≠`0.0`≠`""`，缺值與零不同 hash；(v) `Fact.value` 的 `int` 與等值 `float`（5 與 5.0）〔預設：同 hash，因 Digest `to_dict` 對二者輸出不同 JSON（`5` vs `5.0`，〔F〕`_to_jsonable`），屬來源型別噪音〕；`|int|>2^53`→raise〔待裁〕；(vi) numpy `float32(0.1)` 與 `float64(0.1)` 是**不同值**→不同 hash（不擅自折併；後果僅 miss） | `-0.0` vs `0.0`→相等；`0.1+0.2` vs `0.3`→**不等**（不四捨五入）；`nan`／`inf`（以 `object.__setattr__` 繞過 frozen 注入）→raise 且不回傳字串；`None` vs `0`→不等；5 vs 5.0→相等；`float32(0.1)` vs `0.1`→不等；`True` 當數值→raise（⚠️ Digest 建構階段 `Fact(value=True)` 已 `ValueError`，測指紋層須先以 `object.__setattr__` 繞過 frozen 才測得到指紋本身的拒收，而非建構期拒收） | 離線 |
| P-FP-6 | **結構與順序**〔預設：保序〕：actions／facts／holdings entries 的**順序是語意**，順序對調→不同 hash；`()`≠`None`；序列化須**無歧義**（結構化、長度／型別標記，不可僅字串串接）；序列欄位非 tuple（如 list）→**拒收／raise**（Digest `assert_valid` 以 `not_tuple` 拒收〔F〕`_check_str_tuple` 等），故「list 與 tuple 等價」**不可達**，不作為性質 | actions [A,B] vs [B,A]→不等；fact_id `("a","bc")` vs `("ab","c")`→不等；將 tuple 欄位換成 list→raise（不是「同 hash」）；holdings 重排→不等（〔待裁〕：是否正規化排序以降低 miss；未裁前保序） | 離線 |
| P-FP-7 | **前綴／標籤**：`algo_version`、`analysis_type`、`policy_id`、`prompt_version`、`provider_tag` 入 hash；`provider_tag` 為**不透明字串**（本文不選型號；格式沿用 Digest 鍵規則：非空、無空白／控制字元、NFKC）；`provider_tag=None`（未明）→指紋可算且與任何字串 tag 不同 hash（其 cache 層「恆 miss、不得共享輸出」屬編排層，見 P-CACHE-3）；tag 間**不推斷相容**（不做前綴／子字串比對） | tag `"x1"` vs `"x2"`→不等；`None` vs `""`→後者 raise（非空）；`None` vs 任一字串 tag→不等；實作含任何模型名清單（`claude`／`gpt`／`gemini` 等）→紅 | 離線 |
| P-FP-8 | **Fail-closed**：Digest 無效／子類別節點／未知型別／`bool` 數值／非 str tag／NaN-inf→raise 具名例外，**不回退空字串、不回 hash 部分欄位、不吞例外**（「指紋不可算⇒不得呼叫 Provider」屬編排層，見 P-EFFECTIVE-2） | `assert_valid` 違規的 Digest→raise；子類別 `Fact` 夾帶 `ai_verdict`→raise；raise 後不回傳任何字串 | 離線 |
| P-FP-9 | **輸出不外洩內容**：指紋為不可逆摘要；**但無鹽 sha256 非隱私邊界**（低熵輸入可被窮舉猜測）〔I〕→指紋只進 trace／cache key，不當匿名化 ID 對外輸出；錯誤訊息不含 Digest 內容 | raise 訊息 grep 不含持股鍵／value 字面 | 離線 |

**P-FP-4 `fetched_at` 決策表**（裁示明文：僅證明為非語意抓取噪音才可排除；**預設 fail-safe＝納入**）〔F〕Digest v1 `Provenance` 只有 `source／as_of／fetched_at` 三欄，**無獨立 snapshot／vintage 版本欄**，故 `fetched_at` 是 v1 唯一的「所引用哪一次抓取」標記。
| # | 條件 | 處置 | 判定者 |
|---|---|---|---|
| D1 | 預設／無法證明／來源不在 D2 清單 | **納入**（fail-safe） | 規格預設 |
| D2 | 該來源**逐來源**被證明：同 as_of 重抓**不會**改值（§2.3 修正風險「無」；例：TAIFEX 收盤、CIER 發布日），**且** `fetched_at` 不參與任何 PIT／eligibility 判斷（〔F〕組裝層 `src/services/decision_digest_assembly._pit_ok` 依 `fetched_at` 決定證據是否 `WITHHELD_PIT_VIOLATION`〔`shared/decision_digest_coverage.WITHHELD_PIT_VIOLATION`〕，即 `fetched_at` 在組裝層**確實影響 eligibility**；Digest 層只有 `lookahead`／`fetched_after_generated` 違規檢查〔`shared/decision_digest.py` `_check_provenance`／`validate`〕，僅反映組裝層結果） | 可排除；寫入**具名白名單**（來源 id＋證據＋日期），**初始為空** | 總管裁示＋證據；每筆新增＝一次政策變更，不得由呼叫端臨場宣稱 |
| D3 | 來源有回溯修正風險（§2.3「是」：FRED CPI／NFP、季財報、MOF 進出口） | **納入**（它標示引用哪個 vintage） | 規格預設 |
| D4 | `fetched_at` 改變 PIT／eligibility（〔F〕`_pit_ok` 組裝層即是：`fetched_at` 早於 as_of 日或晚於 generated_at ⇒ 證據被 withheld）或「實際引用的 snapshot 版本」 | **納入** | 規格預設 |
| D5 | `fetched_at is None` | 納入為「缺」，與有值不同 hash（None≠任何時間） | 規格預設 |
負例：(a) 同 source／as_of／value，僅 `fetched_at` 差 1 小時、來源在 D3→指紋**必變**；(b) 同上、來源在 D2 白名單→不變；(c) 白名單為空時任何 fetched_at 差異→變；(d) **D3 來源（有回溯修正風險，如 FRED／季財報／MOF）即使帶證據欄也不可進 D2 排除白名單**：加入→審查測試紅；證據欄缺→亦紅。〔NV〕各來源「重抓是否改值」本文**未逐源實測**，故 D2 初始為空。
**成本張力（一行）**：D1 預設＋空白名單 ⇒ 資料內容完全相同、僅重抓時間不同也 miss，會多呼叫 Provider；與 ADR-OB-001 Decision 5「UI reload 不得直接觸發 AI」的相容性取決於**重抓是否發生在 reload 路徑**（本文〔NV〕未查證）——此為保守取向的已知成本，非 bug。
**〔待裁〕`fetched_at` 正規化**：同一瞬間不同時區的 `isoformat()` 不同、微秒位數亦可不同；預設＝**不折併**（保守，更易 miss）；是否統一為 UTC／截斷至秒需裁示（截斷＝可能把真的不同抓取視為相同，與 D3／D4 衝突，須先證明）。

## 3. P-CACHE｜快取（性質對象為未來 `AnalysisCache` Protocol＋test fake；**不是**第二套 production cache）
| ID | 性質 | 可失敗負例 | 面 |
|---|---|---|---|
| P-CACHE-1 | 成功／失敗隔離：失敗（Provider 例外、grounding 不乾淨）**不入**成功 store；退避狀態另立物件／命名空間，且不可被成功路徑讀成命中 | Provider 回 `ProviderError`→store 條目數不變；INVALID_RESPONSE（grounding 不乾淨）→不入；退避計數器與成功 store 為不同物件（反射） | 離線 |
| P-CACHE-2 | **舊 as_of 不偽裝新資料**：命中必帶**原** `as_of`（輸入最大 as_of）、**原**計算時間、`is_stale`；時間由注入的 clock 比對，不得取代為「現在」；stale 判斷**獨立於**指紋一致性（指紋相等≠新鮮） | 條目 10 天前算出、指紋相等→hit 回傳 `computed_at=10 天前`、`is_stale` 依注入 TTL 為真；實作在命中時改寫為當前時間→紅；移除 is_stale 欄→反射紅 | 離線 |
| P-CACHE-3 | 版本相符才可命中：條目的 `algo_version／schema_version／policy_id／prompt_version／provider_tag` 任一≠當前→`VERSION_MISMATCH`→視同 miss；`provider_tag=None` 條目永不供應 | 條目 tag `"x1"`、當前 `"x2"`→miss 且不回傳舊輸出；當前 tag `None`→恆 miss | 離線 |
| P-CACHE-4 | **cache failure ≠ Provider failure**：`get`／`put` 例外、損毀、版本不符→`CacheStatus`（HIT／MISS／CACHE_ERROR／VERSION_MISMATCH／CORRUPT），**不得**映射成 `ProviderErrorKind`（封閉四類成員集合以測試鎖死）；`get` 失敗→當 miss 繼續（受 P-BUDGET 約束）；`put` 失敗→結果照回 | `get` raise `OSError`→`status==CACHE_ERROR`、`ProviderErrorKind` 成員仍為 `{timeout,rate_limit,unavailable,invalid_response}`；`put` raise→outcome 仍回；損毀條目（欄位缺／型別錯）→CORRUPT 非 HIT | 離線 |
| P-CACHE-5 | 命中**不改** `effective`（恆 `build_rule_summary(digest)`）；命中內容只是影子草稿，不餵下游 | 注入命中條目（含「safe」字樣草稿）→`effective` 與無 cache 時逐欄相等 | 離線 |
| P-CACHE-6 | **不得有第二套 Provider cache**（〔F〕BACKLOG OB-2 差額列：須重用既有 cache 層）：新模組**不得**寫檔、不用 `st.cache_*`／`session_state`／module-level 可變 dict 當 store；TTL 重用 `shared/ttls.py` 屬後續 Gate | AST：新模組含 `open(`／`streamlit`／`pickle`／`sqlite3`／模組層 `dict()` store→紅 | 離線 |

## 4. P-TRACE｜追蹤欄位
| ID | 性質 | 可失敗負例 | 面 |
|---|---|---|---|
| P-TRACE-1 | **欄位白名單**：`AnalysisTrace` 欄位名稱集合以反射鎖死——白名單（內嵌，取自 c7011572090，作 oracle 自足）＝`{fingerprint, analysis_type, policy_id, prompt_version, provider_tag, schema_version, cache_status, skip_reason, error_kind, grounding_clean, failed_check_ids, usage_units(Optional[int]), fallback_used}`；〔候選名稱，非 schema 凍結〕；新增欄位須同步改測試 | `dataclasses.fields` 集合≠白名單→紅；加 `raw_response`／`prompt`／`detail`／`cost`／`action`／`risk_cap`／`holdings`→紅 | 離線 |
| P-TRACE-2 | **值域受限**：除 `fingerprint`（固定長度 hex）與受格式約束的版本／tag 字串外，欄位只能是 Enum／bool／`Optional[int]`；**無自由文字欄**；`failed_check_ids ⊆ {G1..G6}`；`error_kind` 為 `ProviderErrorKind` 值 | 塞任意字串進 `skip_reason`→建構 raise；`error_kind="boom"`→raise | 離線 |
| P-TRACE-3 | **不洩漏**：`ProviderError.detail` 全文、金鑰樣式、原始 prompt、原始回應、Digest 內容（含持股鍵 `portfolio_id／symbol`）、cost／action／risk_cap 不得出現在 trace 的 `repr`／`asdict`／`json`／log（`caplog`）任一輸出 | `ProviderError(INVALID_RESPONSE, "sk-ant-FAKE…")`、Digest 持股鍵 `T1234`、prompt 標記字串→三者在 trace 全輸出 grep 皆無；實作把 `str(exc)` 放進 trace→紅 | 離線 |
| P-TRACE-4 | trace 寫入失敗（sink raise）不影響 `effective`、不吞成「已記錄」 | sink raise→outcome 仍回、`effective` 不變、warn 留型別名 | 離線 |

## 5. P-BUDGET｜預算（抽象單位）
| ID | 性質 | 可失敗負例 | 面 |
|---|---|---|---|
| P-BUDGET-1 | 決策只有 `ALLOW／SOFT_LIMIT／HARD_DENY`（封閉）；`HARD_DENY`→**Provider 不被呼叫**、`effective` 不變、trace 標 `BUDGET_DENIED`；不新增 `ProviderErrorKind` | fake provider `calls==0`；`effective==build_rule_summary(d)`；`ProviderErrorKind` 成員不變 | 離線 |
| P-BUDGET-2 | 單位為非負整數（非 `bool`）；負數／`bool`／`float`／`NaN`／`None` 作 units→raise；`used` 只在**實際 Provider 嘗試**時遞增（cache hit、deny 皆 0） | `requested_units=-1`／`True`／`1.5`→raise；cache 命中後 `used` 不增 | 離線 |
| P-BUDGET-3 | 策略本身 raise→**fail-closed 視同 HARD_DENY**（不呼叫 Provider；trace 標 `BUDGET_POLICY_ERROR`〔預設〕）；不映射 `ProviderErrorKind` | policy raise→`calls==0`、`effective` 不變 | 離線 |
| P-BUDGET-4 | **無貨幣／模型名／單價／預設上限數值**出現在模組（§3.3）；上限只能由呼叫端注入；SOFT_LIMIT 是否降級行為〔待裁，預設：照常執行但 trace 標記〕 | 掃描模組文字含 `USD`／`$`／`token_price`／`claude`／`gpt`／`gemini`／裸數字上限常數→紅 | 離線 |
| P-BUDGET-5 | `usage_units`／token／cost 欄位**預設 `None`，不是 0**；聚合時 `None` 計為「未知」不得當 0 相加；**未接真 SDK／Token usage 前，文件／PR／trace 不得宣稱「已實測成本控制」** | 預設建構→`usage_units is None`；`sum` 含 None 的聚合函式回傳「未知」旗標而非數值 0；模組 docstring 缺「未驗證真成本」→紅〔預設〕 | 離線（宣稱面）／RT（真成本） |

## 6. P-EFFECTIVE｜規則式結果不變
**P-EFFECTIVE-1**：任何失敗、預算拒絕、cache 異常、指紋失敗、trace 失敗下，`outcome.effective == build_rule_summary(digest)` 逐欄相等，`shadow_accepted` 僅在 Provider 草稿通過 `check_summary` 時為真且**不被任何下游讀取**；AI 未執行**不得**被呈現為 SAFE／HOLD／neutral。
負例（**沿用** OB-1 的 9 失敗模式×2 份 Digest〔F〕`tests/test_onebrain_offline_guard.py`，**不重做**；僅疊加 OB-2 注入面）：{cache get raise、put raise、CORRUPT、VERSION_MISMATCH、HARD_DENY、policy raise、指紋 raise、trace sink raise}×{既有 2 份 Digest}→`effective` 全等於 `build_rule_summary`；變異「effective 改採 Provider 草稿」→全紅。規則層自身錯誤（非 rule_only Digest 的 `ValueError`）仍 fail loud 上傳（OB-1 DEC-195 規則 4）。
**P-EFFECTIVE-2（編排層，自 P-FP-8 移入）**：指紋不可算（raise）⇒ **不得呼叫 Provider**（無法去重＝成本失控風險）且 `effective==build_rule_summary(d)`。負例：注入無效 Digest→編排層 `provider.calls==0`、`effective` 不變。屬後續編排 gate，非 fingerprint-only 驗收。

## 7. 離線可證 vs 只能 runtime 驗證
| 項目 | 離線可證 | 需 runtime（**NOT VERIFIED**） |
|---|---|---|
| 指紋決定性／欄位完備／逐欄突變／數值規則／fail-closed | ✔（P-FP-1～3、5、6、8） | — |
| 跨進程穩定（`PYTHONHASHSEED`） | ✔（子進程） | **跨版本／跨平台 Python 的 float repr 一致性** 〔NV〕（CPython 契約上 shortest-repr 穩定，本文未跨版本實測） |
| 來源重抓是否改值（D2 白名單依據） | ✘ | **〔NV〕逐來源**須取證；初始白名單為空 |
| cache 版本／損毀／失敗隔離（fake） | ✔（P-CACHE-1～5） | **跨進程 TTL、並發競態、真 store 一致性、退避實效** |
| trace 白名單與 fake secret 不洩漏 | ✔ | **真 Provider 錯誤訊息是否夾帶機密**；真 log 管線 |
| 預算決策／deny 不呼叫 | ✔（抽象單位） | **真 Token 用量、真成本、延遲、Provider 端 rate limit**——離線不得宣稱「成本控制已實測」 |
| `effective` 恆為規則式 | ✔ | — |
| rerun 下指紋穩定（同日不同 run 之 Digest 重組） | 部分：僅「同一 Digest 物件」 | **headless Digest 組裝的非決定性**（`P1R-DIGEST-HEADLESS-ASSEMBLY` 未完成，〔F〕BACKLOG OB-TD-01）〔NV〕 |

## 8. 與現有守衛的關係（新模組將打紅／漏掉什麼；**這些白名單改動本身屬未來施工 Gate**，本文不改）
以下 〔F〕為本次逐檔閱讀，**未實跑「新增檔後」的紅燈**〔NV〕；c7011572090 的結論為單組靜態閱讀，本表補其逐項：
1. `tests/test_decision_digest_invariants_guard.py`：`OFFLINE_SHADOW_MODULES`（逐檔×逐模組）；`test_c2_stage_f_gate_still_closed_and_offline_shadow_set_is_exactly_two_files` 以**字面**斷言 `OFFLINE_SHADOW_CALLERS == {兩檔}`→新增第三檔**必紅**；`test_c2_l0_root_importers_are_exactly_the_whitelist` 要求家族外 importer 的 `shared.decision_digest` ⊆ `L0_ROOT_IMPORTERS ∪ OFFLINE_SHADOW_CALLERS`→新檔若 import 根契約而未登記**必紅**；若新檔命名 `decision_digest_*`→`test_c2_family_whitelist_files_exist…` 紅；`ALLOWED_CALLERS=∅` 不動且仍被斷言。**替代路徑（交 Gate 擁有者選擇）**：新檔若只 import 根契約 `shared.decision_digest`，亦可**僅加入 `L0_ROOT_IMPORTERS`（一行）**——QA 實測此路 113 例全綠〔F，QA 於副本驗證，作者未獨立重跑〕。取捨：`L0_ROOT_IMPORTERS` 較省事，但該路徑**沒有**逐模組反向測試、也不需改「恰兩檔」斷言（亦不會把新檔納入影子層語意）；`OFFLINE_SHADOW_*` 路徑較嚴（逐模組反向測試），代價是須改「恰兩檔」斷言並附核准依據。本文不替 Gate 擁有者選。`test_c2_offline_shadow_exemption_is_per_module` 為依 dict key 參數化，新 key 自動納入反向測。
2. `tests/test_onebrain_offline_guard.py`：`NEW_MODULES`／`NEW_FILES`／`_imports_onebrain` 的名稱集合（寫死 `{"onebrain_provider","onebrain_shadow"}`）／`_ALLOWED_IMPORTERS`／`_IMPORT_ALLOWLIST`（逐檔 import 白名單）。**新檔不加入時不會紅，而是假陰性**（production 誤 import 新檔不被抓）；加入時 `allowed_roots` 需含 `hashlib`／`json`／`math`（現為 `{__future__,dataclasses,enum,typing,logging,shared,src}`）；既有「`json` 為多餘 import 即紅」的反向測試針對**既有兩檔**，須保留。
3. `tests/test_ui2_no_second_ai_guard.py`：只掃 UI2 四範圍，**不涵蓋** `shared/onebrain_*`；OB-1 以 `scan_no_second_ai` 對 `NEW_FILES` 重用，新檔須加入才受同一份 SDK／網路／端點掃描。**守衛綠不是無越界證據**（非窮舉）。
4. L0 分層（`tests/test_c3_layering_guard.py`）：新 `shared/` 檔受 L0↛L1+ 約束；〔F〕QA 已在副本新增 `hashlib`／`json`／`math` 的 L0 檔實測 c3 綠（作者未獨立重跑）。每個新增白名單項須有「多一個 import／production caller→紅」的反向測試（與 OB-1 同級）。

## 9. 下一個須使用者批准的最小 code gate：`OB-2-FINGERPRINT-ONLY-CODE`
- **前置（缺一不可）**：(1) **使用者明確批准**（DEC-195 仍列 OB-2 未授權；c7011701691：OB-2 code HOLD）；(2) 總管採納本規格並裁示 §2 的〔待裁〕項：holdings／facts 是否正規化排序、`|int|>2^53` 處置、`fetched_at` D2 白名單初始內容（預設空）、output schema 識別（〔NV〕`shared/decision_digest_grounding.SummaryDraft` **無版本欄**，須定義以何代位）。
- **範圍**：**單檔** L0 純函式 `shared/onebrain_fingerprint.py`（名稱為候選，**勿**用 `decision_digest_*`）；僅 stdlib（`hashlib`／`json`／`math`／`dataclasses`）＋ `shared.decision_digest`；性質範圍**僅 P-FP 指紋層**（P-CACHE／P-TRACE／P-BUDGET／P-EFFECTIVE-2 屬後續編排 gate）；具名例外 `FingerprintError`。
- **將新增的 tests**：`tests/test_onebrain_fingerprint.py`（僅 P-FP-1～9 指紋層，含反射欄位完備、逐欄突變矩陣、D1～D5 負例、數值負例、`PYTHONHASHSEED` 子進程、AST 零 production import／零 SDK／零網路／無模型名清單）。**不釘死 golden hash 字面值**（避免提前凍結演算法；〔待裁〕）。
- **將同步的守衛**（屬本 gate；二選一，見 §8-1）：`test_decision_digest_invariants_guard.py`（路徑 A：`OFFLINE_SHADOW_*` 登記＋「恰兩檔」字面斷言改為三檔並附核准依據；路徑 B：僅加入 `L0_ROOT_IMPORTERS`）；`test_onebrain_offline_guard.py`（`NEW_MODULES`／`NEW_FILES`／名稱集合／`_IMPORT_ALLOWLIST`／`allowed_roots`＋反向測試）。`ALLOWED_CALLERS=∅` 不動。
- **驗收**：非作者 QA；exact-head CI；對每條性質至少一個**突變**（刪納入欄、`-0.0` 不正規化、`generated_at` 誤納入、NaN 不 raise）使測試轉紅，附於 PR；PR／docstring 明寫「離線、無 caller、未驗證真成本與真洩漏」，**不得**寫「已具備 AI 基礎建設／預算管控」。
- **不做**：cache／trace／budget 任何實作（Protocol 型別是否同批留〔待裁〕，預設不含）、`run_shadow_with_controls`、改 `run_shadow`／`ProviderRequest`／`ShadowOutcome`／Digest v1、真 Provider／SDK／網路／Secrets／model／費用、任何 production caller（UI／LINE／決策）、改 `shared/ttls.py`、動 workflow／config。

## 10. 設計預留與聲明
- **opaque tag**：`provider_tag`／`policy_id` 為外部注入的不透明字串，Digest v1 不加欄位、`generated_at` 不當 `published_at`；未明 tag 不共享輸出（P-FP-7、P-CACHE-3）；未來 model 是否入指紋＝tag 的內容問題，不在本文選型號。
- **聲明**：本文**不是** OB-2 授權；真 runtime、指紋／cache／trace／budget 程式、Provider／SDK／Secret／預算上限均**未授權、未實作、未驗證**。引用：c7011701691；c7011572090；ADR-OB-001 §Decision 5/6/9；`ONEBRAIN_IMPLEMENTATION_BACKLOG` OB-2；DEC-195／DEC-199；`shared/decision_digest.py`（`Provenance`／`Fact`／`_to_jsonable`）、`shared/onebrain_provider.py`（`ProviderErrorKind`）、`src/services/onebrain_shadow.py`（`run_shadow`）。
