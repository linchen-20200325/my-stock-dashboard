# AB-2a 規格：Decision Digest 的 Grounding／Validator（G1～G6）＋fail-safe 降級＋規則式摘要（無 AI）（2026-10-27；QA 回修版：句型白名單）

> **決策者：AI 總管內部（技術實作，依 `CLAUDE.md` §-1.5 v3 §03-1 內部自決）；非客戶裁示。**
> 本檔由執行 AI 單組撰寫；初版經兩組獨立 QA（語意治理＋紅隊）後，總管拍板**把主防線從「黑名單字眼＋quote 豁免」改為「句型白名單」**
> （本版即回修版）。回修版尚未經第二組獨立複驗（`CLAUDE.md` §-2 規則 6）。
> FACT＝已用程式／測試實測；INFERENCE＝設計推論，後續批次不得當成已查證事實引用。
> 上位依據：AB-0 契約（`shared/decision_digest.py`，**本批一字未改**）、AB-1 Builder／rules、
> C 設計草案 §2.4（G1～G7）／§2.5（降級）／§3.1（五段）、DEC-092 Q4、`PROJECT_RULES.md` §16.1。
> 與 C §2.4 正式定義的差異一律列在 §7（以正式文件為準；無法照字面落地之處據實標明）。

## 0. 一句話

資料流：`Digest → AB-2a Validator／Grounding → 規則式摘要 →（未來 AB-2b 才交給 AI）`。
**不得 Data→LLM；Digest 有問題由規則層判 INVALID，不由 AI 修。** 本批沒有任何 LLM 呼叫、傳輸、金鑰、用量。

## 1. 檔案與公開介面

| 檔 | 層 | 內容 |
|---|---|---|
| `shared/decision_digest_terms.py` | L0 | 全部**具名常數**：五段鍵／標籤、引用 id 前綴、標示語、**固定模板片段 `TEMPLATES`**、欄位名、閘門 id、顯示標籤；以及降級為建置期 lint 的字眼清單。零邏輯。 |
| `shared/decision_digest_validator.py` | L0 | `assess_digest(digest) -> DigestAssessment`（Digest 自身檢查＋四態）、`SummaryState`、`DigestViolation`、`section_availability`、`derive_state`、`strategy_entries`。 |
| `shared/decision_digest_grounding.py` | L0 | 最小輸出格式 `SummaryDraft／SummarySection／SummarySentence(segments)`、`Lit`／`Ref`；句型白名單 `SHAPES`；`check_summary(digest, draft) -> GroundingReport`（G1～G6）；`SummaryResult`（統一摘要結果型別）；`build_ref_index`／`section_basis`／`number_literal`／`remove_quotes`。 |
| `src/services/decision_digest_summary.py` | L3 | `build_rule_summary(digest) -> SummaryResult`（規則式摘要，`mode=RULE_ONLY`）、`compose_rule_draft`。 |
| `tests/test_decision_digest_{validator,grounding,summary}.py`、`tests/decision_digest_factory.py` | 測試 | 見 §8。 |

分層（`CLAUDE.md` §8.2）：L0 只 import 標準函式庫與 `shared.*`；L3 只 import L0。皆**不 import** streamlit／requests／LLM SDK／`src.*`（L0）；
`app.py`／`shared/ia_nav.py` 不 import 本批任何檔（AST 測試鎖死）。**production 無 caller**（AB-4r 前 `portfolio_id` 無來源，行動／持股本就不可達）。

## 2. Digest 層驗證與四態降級

`assess_digest` 逐一呼叫並**原樣沿用**（不弱化、不改語意）：AB-0 `validate()`（閘門 `AB0_CONTRACT`）、AB-1 `validate_rule_ids`（`AB1_RULE_ID`：allowlist／版本／`rule_wrong_location`）、`validate_action_order`（`AB1_ACTION_ORDER`：Q4 序）。
三者的違規集合＝AB-1 `validate_strict`（測試以集合相等鎖死）。任務清單中的檢查對映：

| 要求 | 由誰擋 | 代碼 |
|---|---|---|
| 契約漂移（schema_version 等） | AB-0 | `schema_version_mismatch` |
| invalid／NaN／inf 值 | AB-0 | `bad_number`、`value_with_missing_status`… |
| allowlist／rule_wrong_location／rule 版本 | AB-1 | `rule_not_allowlisted`／`rule_wrong_location`／`rule_version_not_allowed` |
| action origin 必為規則層 | AB-0 | `non_rule_origin` |
| evidence 指向 missing fact | AB-0 | `evidence_on_unusable_fact`／`dangling_evidence_ref` |
| unavailable holdings 不可有 available actions | AB-0 | `actions_available_without_holdings` |
| 重複 id | AB-0 | `duplicate_fact_id`／`duplicate_action_id`／`duplicate_holding_key` |

**AB-2a 新增的檢查（只收緊，不放寬任何 AB-0／AB-1 語意）**：
1. `control_chars_in_text`（閘門 `AB2A_TEXT`）：`Fact.text`／`ActionRef.text`／`strategy_source` 含控制（Cc）／零寬／格式（Cf）／代理／私用區／未指派字元、行段分隔（Zl／Zp）、**非普通空格的空白**（NBSP、全形空白 U+3000…）、或**孤立組合記號**（在字串開頭或緊接空白）。AB-0 沒禁；摘要要逐字轉述這些文字，不可見／不規範字元會讓逐字比對失真。
2. `ref_id_reserved`／`ref_id_collision`（閘門 `AB2A_REFS`）：fact_id／action_id 以保留前綴 `section:`／`holding:` 開頭，或 fact_id 與 action_id 相同 —— evidence 命名空間會含糊。
3. 輸入不是（恰好）`DecisionDigest` → INVALID，不 raise。
4. `unsupported_unit`（閘門 `AB2A_TEXT`）：市場事實的 unit 不是 `%` 也不是 None（摘要的單位由模板決定，不展開 Digest 的 unit 字串）。

### 四態（`SummaryState`）

| 態 | 條件 | 輸出 |
|---|---|---|
| **INVALID**（contract drift） | 上列任一違規 | **不輸出任何投資結論**：`sections=()`、`retained_sections=()`；`notices` 指出**哪一段 invalid**（`invalid_sections`）、**哪個閘門失敗**（`failed_gates`）、違規代碼、並明說**其他段落未保留**。 |
| **UNAVAILABLE** | 合規，且五段依據皆 UNAVAILABLE | 五段都輸出，每項以「⬜ …資料不足，無法判定」明示。 |
| **PARTIAL** | 合規，部分可用 | 只輸出可證明部分；缺的明示；**整體不標 AVAILABLE**。 |
| **VALID** | 合規，五段依據皆 AVAILABLE | ⚠️ **現行契約下不可達**（INFERENCE→已測）：產業趨勢與策略分類的正式定義未核准，產業段恆 UNAVAILABLE、市場段恆含「尚未定義」的趨勢。這是誠實，不是 bug。 |

availability **只由資料推導**（沿用各段已推導的 `availability`；市場段＝market／risk_cap／tw／intl／valuation 合併、定義狀態段恆 UNAVAILABLE ⇒ 市場段至多 PARTIAL；存股／資本利得＝持股讀不到→UNAVAILABLE、無該策略 entry→UNAVAILABLE、有→至多 PARTIAL（基本面判定未接線）；行動＝actions 段自己的）。
`SummaryResult` 的 `state` 等欄位**由 Digest 在建構時推導**，無法手造或升格（§4.5）。

**INVALID 的保留政策（內部決定）**：違規一旦涉及跨物件不變量（fact_id 唯一、evidence 指向可用事實、行動 vs 持股），代表 builder 違反契約、影響範圍未知；AB-0 的 `evidence_refs` 本身就是跨段依賴，無法證明段落彼此獨立 → **整份不採信**，`retained_sections` 恆為空。替代方案「保留未受影響的段落」需要先證明段間無依賴，不採。（單組判斷，待覆核。）

## 3. 最小輸出格式契約：segment 序列（AB-2b 不得因它被迫採用某種 prompt／傳輸）

```
SummaryDraft(sections=(SummarySection(key, sentences=(SummarySentence(segments=(Lit(template_id) | Ref(ref_id, field), ...)), ...)), ...))
```
- `key`：`market／industry／buy_and_hold／capital_gain／actions`（五段，固定順序）。
- `Lit(template_id)`：`terms.TEMPLATES` 的固定模板片段，**以 id 引用**（不是任意字串）；`Ref(ref_id, field)`：對某個 Digest 項目的**欄位展開**
  （`label／text／value／as_of／reason／symbol／strategy／count／marker／wording／bind`），內容由 checker 從 Digest 取出。
- **沒有任何型別能承載任意文字**：`segments` 裡放字串、dict、子類別一律 `structural_failure`；`Lit` 的 id 不在白名單（包括「把模板字串本身當 id」）→ G4。
- 文字只在 `SummaryResult.lines`／`render_draft(digest, draft)` 由「Digest＋模板」展開產生。
- **無法解析的輸入一律驗證失敗**（`structural_failure=True`，`accepted=False`，`surviving=None`）；永不 raise。

**引用 id 空間**：Digest 內的 `fact_id`／`action_id`；`section:<digest 段名>`；`holding:<portfolio_id>:<symbol>`。
**欄位展開的限制**：Risk Cap 區段與趨勢「僅供參考」觀測值**整個受限**（值／文字／資料日都不能展開，`restricted_value`）；
持股事實只開放資料日（行動 stale 揭露用）；**`strategy_source`（使用者自由文字）沒有任何欄位可展開**（A1：結構上不進摘要）。

## 4. 句型白名單與 G1～G6

### 4.1 為什麼改（QA 根因）
初版 G3／G4 靠「黑名單字眼＋quote 豁免」：自由文字可夾帶結論；同形異字／簡體／同義詞／中文數字繞過；標示語只做子字串檢查（否定／矛盾放行）；
行動句只需「含」`ActionRef.text`（可加字、換代號、換順序、漏項、重複）；多 ref 句池化 quotes／literals；掛一個 section ref 就能搭便車夾帶任意結論。
黑名單永遠擋不完；修法不是補名單，而是**讓壞句子沒有地方可以寫**。

### 4.2 句型（`grounding.SHAPES`）
一句話必須吻合**唯一一個**句型骨架（模板與欄位的排列、每個 slot 的項目種類），再通過該句型的**前置條件**（綁 Digest 狀態）。
同一 slot 的所有 `Ref` 必須指向同一項目（不池化）；沒有任何 `Ref` 的句子丟棄（G6）。句型清單（`·` 表示 `Lit` 模板）：

| 句型 | 段 | 前置條件（Digest 必須為真） |
|---|---|---|
| `fact_{text,value,value_pct}_{ok,stale,proxy}` | 市場 | 市場事實 status 吻合；`value_pct` 的 unit 必須是 `%`，`value`／`text` 必須無 unit（**單位由模板決定**，`unit_mismatch`）；ok／stale 標資料日，proxy 標「代理估算值，非正式資料」 |
| `fact_missing` | 市場 | status ∈ {missing, failed}；顯示固定模板＋缺值原因標籤 |
| `fact_invalid` | 市場 | status＝invalid |
| `risk_wording` | 市場 | 引用 `section:risk_cap`；展開為客戶核准卡面措辭（**不展開任何 Risk Cap 數值**） |
| `section_undefined` | 市場／產業 | 引用 tw／intl／valuation（市場）或 industry（產業）；標示語（尚未定義／尚未接線／研究框架，未啟用）由 Digest 的定義狀態決定 |
| `holdings_unavailable:<段>`／`strategy_unset:<段>` | 存股／資本利得 | 持股 UNAVAILABLE／非 UNAVAILABLE 且無該策略 entry |
| `holdings_unkeyed` | 存股／資本利得 | `unkeyed_count > 0`（N 取自 Digest） |
| `strategy_entry` | 存股／資本利得 | 持股非 UNAVAILABLE，且該 entry 的策略屬於此段；只展開代號與策略名，**不展開來源** |
| `actions_unavailable`／`actions_none` | 本期行動 | actions UNAVAILABLE／AVAILABLE 且 0 筆 |
| `action_item[_nt][_stale]` | 本期行動 | 行動在 Digest `actions[]` 內；代號只取自 `ActionRef.target`（無 target 用 `_nt`）；證據有 stale 事實時**必須**用 `_stale`（第二個 slot＝最舊資料日的 stale 證據），反之不得用 |

### 4.3 G1～G6 如何落地
| 閘門 | 結構性做法 | code |
|---|---|---|
| **G1 引用封閉** | `Ref` 的 id 必須在 Digest；欄位必須是該項目可展開的；slot 一致 | `ref_not_in_digest`／`field_not_quotable`／`slot_ref_mismatch` |
| **G2 數字一致** | 數字只能來自 `value`（`number_literal`：不補零、不四捨五入、不科學記號）、`as_of`、`count` 的展開；模板無任何阿拉伯數字（測試鎖死）；單位由模板決定；Risk Cap／觀測值受限 | `unit_mismatch`／`restricted_value` |
| **G3 狀態不可升級** | 句型前置條件綁項目狀態；ok／stale／proxy／missing／failed／invalid 各有固定句型；標示語由模板產生，不再做子字串判斷 | `status_mismatch`／`precondition_failed`／`stale_evidence_mismatch` |
| **G4 不新增結論類別** | 骨架不在白名單即拒；行動段與 Digest `actions[]` **一對一、同順序、無重複、無遺漏**；行動句＝代號＋`ActionRef.text` 展開，不得加前後字 | `template_not_whitelisted`／`shape_not_whitelisted`／`action_list_mismatch`／`wrong_strategy`／`target_mismatch` |
| **G5 段落完整** | 五段齊全、唯一、固定順序；每段非空；對 Digest 中非 ok 的依據（`section_basis`）都須有對應句型（且綁定該 ref）；句型須屬該段；段內不得有重複句 | `missing_section`／`duplicate_section`／`unknown_section`／`section_order`／`empty_section`／`missing_disclosure`／`shape_out_of_section`／`duplicate_sentence` |
| **G6 依據可回溯** | 沒有任何 `Ref` segment 的句子丟棄（不使整份失敗；丟棄的句子不再被檢查） | `no_evidence_ref` |
G7（輸出過濾）**不在本批**。

### 4.4 accepted／usable／clean／surviving（寫死）
- `accepted`：無 STRUCT／DIGEST／G1～G5 違規（G6 丟棄不算）。
- `surviving`：丟棄 G6 句子後的摘要。**消費端只能用 `surviving`，不得用原始 draft**（A7）。
- `usable`＝`accepted` 且 `surviving` 非 None；`clean`＝`usable` 且無丟棄。
- `SummaryResult` 只收 `clean` 的內容；`passed_gates`／`failed_gates` 為固定閘門順序。

### 4.5 `SummaryResult`（A8：不可手造、不可改裝）
只接受 `digest`、`mode`、`sections` 三個欄位；`state`、`section_availability`、`notices`、`invalid_sections`、`failed_gates`、`violations`、
`retained_sections` 全部在 `__post_init__` 由 Digest 推導（`init=False`，`dataclasses.replace` 會重跑檢查，指定這些欄位直接 TypeError）。
建構時：`mode` 必須是 AB-0 既有 `AiParticipation`；Digest INVALID ⇒ `sections` 必須為空；否則 `sections` 必須 `clean` 通過 `check_summary`（與該 Digest 綁定）。
`lines` 是唯一的文字來源（由 Digest＋模板展開）。

### 4.6 降級為「建置期 lint」的黑名單
洗白／確定語氣／行動／方向／狀態詞／產業名清單（`terms.WASHING_*` 等）不再參與執行期判斷；測試對**每個模板、標籤、標示語**做 lint，保證 L0 常數裡沒有人偷渡這些字眼。
它們仍是盡力而為（同義詞擋不住），但現在擋的是「我們自己寫的固定字串」，不是「對方給的自由文字」，所以風險面小很多。

## 5. 規則式摘要（`build_rule_summary`）

只**重新組織** Digest 已有內容：不新增數值／買賣判斷／門檻／權重／產業結論／趨勢結論／候選股／AI 信心機率。builder 不寫任何字串 —— 它只依
`SHAPES` 的骨架組 segment；文字由 `SummaryResult.lines` 展開。
市場：事實逐字＋資料日（缺值／過期／代理用各自句型）；Risk Cap 只顯示客戶核准卡面措辭；台股／國際趨勢「尚未定義，無法判定」；大盤合理區間「研究框架，未啟用，無法判定」（不出區間、不出 EPS／PE）。
產業：「產業趨勢：尚未定義，無法判定」。存股／資本利得：持股讀不到／未帶鍵持股／尚未設定策略分類／已分類持股（只顯示代號與策略名，判定「尚未接線」；**來源不顯示**）。
本期行動：`{代號}：{ActionRef.text}` 逐字、Digest 順序、不重排（Digest 違反 Q4 序 → INVALID）；證據 stale 時加「（依據資料已過期，資料日 …）」。
`portfolio_id` 無正式來源：holdings 依 AB-1 維持 UNAVAILABLE／PARTIAL，缺鍵持股只以計數呈現，不以 symbol／Sheet 名稱代鍵。

## 6. 與 AB-2b 的介面邊界

AB-2a **提供**：`check_summary`（唯一的 G1～G6 檢查器）、`SummaryDraft`（segment 格式）、`SummaryResult`、`render_draft`、`build_rule_summary`（降級用的基準答案）、
`GroundingReport.passed_gates／failed_gates`（可對映 Digest 的 `ai_passed_checks／ai_failed_checks`）。
AB-2b **負責**（本批不碰，亦不預先決定）：prompt、輸出解析、傳輸／金鑰／退避／用量、何時呼叫（Decision Gate）、通過後 `mode=AI_EXPLAINED`／失敗後 `AI_REJECTED` 並退回 `build_rule_summary`。
⚠️ **AB-2b 要上線，AI 必須以「選句型＋填 slot（`Ref`）」的受限格式輸出（例如函式呼叫／結構化輸出）；自由文字的 AI 輸出不可能通過本檢查器。** 這是設計，不是缺陷 ——
它意味著 AB-2b 的 AI 只能「挑選與排列」Digest 已有的句型，無法潤飾措辭；若客戶要的是自然語言潤飾，必須另走 Gate 重新決定（本批不替它決定）。
⚠️ `structural_failure` 沒有對應的 G id，而 AB-0 的 `ai_rejected` 要求 `ai_failed_checks` 非空，AB-2b 須自行決定映射。
禁止的資料流：Data→LLM；AI 輸出寫回 Digest；AI 修 Digest。

## 7. 內部設計決定（**待登記 DEC；非客戶裁示**）與與正式文件的差異

1. 三個 L0 檔＋一個 L3 檔（terms／validator／grounding／summary）；常數集中於 terms（`CLAUDE.md` §3.3）。
2. **INVALID 整份不採信**：Digest 的跨物件不變量一旦被破壞，代表 builder 違反契約、影響範圍未知；AB-0 的 `evidence_refs` 本身就是跨段依賴，無法證明段落彼此獨立；
   替代方案「保留未受影響的段落」需要先證明段間無依賴，不採。`SummaryResult` 的 `retained_sections` 恆為空（INVALID 時）。（單組判斷，待覆核。）
3. **主防線＝句型白名單**（§4）；fail closed 的代價：合法的 AI 改寫也無法通過，只能挑句型（見 §6）。
4. **引用 id 空間擴充**（`section:`／`holding:`）：因為 AB-0 契約沒有 C §4 草案的 `sources[]`，且定義狀態段／缺值段沒有 fact 可引。
5. **Risk Cap 顯示保守**：連 `exposure_lo/hi_pct` 也不顯示（`final_hi` 已含 cap，顯示等於繞過 DEC-081 Q2-2）。⚠️ 需總管／客戶判斷：「建議總持股水位」是 C §3.1 市場段內容，是否核准顯示屬 RC-VISIBILITY Gate。
6. **Digest 文字更嚴**（只收緊）：`Fact.text`／`ActionRef.text`／`strategy_source` 不得含控制／零寬／格式／私用區字元、行段分隔、非普通空格的空白（全形空白 U+3000 的決定：**拒收**）、孤立組合記號；市場事實的 unit 必須是 `%` 或無。
7. 與 C §2.4 字面的差異（以正式文件為準）：
   - G1 的允許名單寫 `holdings[]`／`candidates[]`／`industry_trend[]`；AB-0 Digest 沒有 candidates／industry_trend，故代號只能來自持股／行動目標，產業名稱**無允許名單**（句型根本沒有能放產業名的位置）。
   - G3 的洗白字眼不再是執行期黑名單，而是「標示語由模板產生、句型綁狀態」；C 列的字眼（中性／正常／維持／續抱／HOLD）由 lint 保證不在任何模板內。
   - G5 C 寫「該段退回規則式」，G1～G4 寫「退回規則式摘要」（整份）：本檔只回報事實，不執行退回政策。
   - C §2.5 的 `ai_participation.validation` 在 AB-0 落地為 `ai_passed_checks／ai_failed_checks`（C §11 已記），本檔以 `passed_gates／failed_gates` 對映。
8. VALID 態現行不可達（產業與策略分類未定義，產業段恆 UNAVAILABLE、市場段恆含「尚未定義」的趨勢）。
9. 隨機測試用標準庫 `random` 固定種子（repo 沒有 `hypothesis`；不為本批新增依賴）。

## 8. 測試與突變

見交付報告與 PR（數字隨最終驗證更新；本檔不寫會漂移的量測值，`CLAUDE.md` §8.2.A.0 規則 4）。
突變腳本：`/tmp/claude-0/-home-user-my-stock-dashboard/92636036-60ab-5183-a29d-e08e992434fc/scratchpad/ab2a_mutation.py`（沙箱 scratchpad，未入庫；在 repo 副本上突變，不動真實工作樹）。
指令：repo 根目錄執行 `/tmp/claude-0/venv/bin/python <腳本路徑> --jobs 4`。
QA 紅隊探針（`scratchpad/qa/probe*.py`、`mut2.py`）的最小重現已全部轉成回歸測試（`tests/test_decision_digest_*`，測試名含 `a1`…`a10`／`qa`）。

### 8.1 QA 發現的處置分類（結構性消失／靠測試擋／仍殘留）
QA 紅隊的 35 個突變（`mut2.py` N01～N35）逐一對映：守衛仍存在者已適配到新結構並殺死；守衛隨結構一起消失者，列為「結構性消失」，並以測試證明對應攻擊在新格式下無法表達。

| 類別 | QA 發現 | 處置 |
|---|---|---|
| **結構性消失** | A1 使用者自由文字（`strategy_source`）可作為 quote 進摘要 | 沒有任何欄位可展開 `strategy_source`（`expand` 矩陣測試＋哨兵字串測試）；另外 Digest 層擋該欄位的不可見字元 |
| **結構性消失** | A2 否定／矛盾／加形容詞／標示語子字串偽造；A3 同形異字、簡體、同義詞；A4 中文／全形數字；夾帶結論；搭便車 section ref；多 ref 池化 quotes／literals | `segments` 只能是 `Lit(模板 id)`／`Ref(欄位展開)`，沒有任意字串的位置；骨架固定、標示語由模板產生；slot 綁定單一項目 |
| **結構性消失＋測試擋** | A5 數字後空白／單位放行 | 單位由模板決定（`unit_mismatch`）；數字只由 `number_literal` 展開；模板無任何阿拉伯數字（測試鎖死） |
| **結構性消失＋測試擋** | A6 行動句加字／換代號／換順序／漏項／重複 | 行動句型＝代號＋`ActionRef.text` 展開；行動段與 Digest `actions[]` 一對一同順序（`action_list_mismatch`）；slot 一致擋換代號 |
| **靠測試擋** | A7 G6 丟棄時 `accepted` 被誤用 | `usable`／`clean`／`surviving` 語意寫死（§4.4）；`SummaryResult` 只收 `clean` |
| **靠測試擋** | A8 `SummaryResult` 可用 `dataclasses.replace`／手造繞過 | 只收 `digest`／`mode`／`sections`，其餘由 Digest 推導（`init=False`）；建構時重跑 `check_summary` 並與 Digest 綁定 |
| **靠測試擋** | Digest 文字的 Zl／Zp／Co／Cn／非普通空白／孤立組合記號 | `has_forbidden_char` 擴充（全形空白＝拒收），逐類別測試；市場事實 unit 限 `%`／無 |
| **仍殘留** | A10 `ActionRef.text` 與 `rule`（分支碼）未綁定（AB-1 缺口，非本批引入） | **不改 AB-1**；測試 `test_known_gap_a10_…` 釘住現況；BACKLOG 備註 `AB1-ACTION-TEXT-RULE-BINDING`（總管登記） |
| **仍殘留** | 規則層輸出本身（`Fact.text`／`ActionRef.text`）若有誤導性，摘要忠實轉述；句型選擇權（可省略 ok 事實）；受限證據的過期無法揭露 | 見 §9 |

N01～N35 對映：N01→W04；N02→W11；N03／N04／N05／N16／N17／N18／N21／N23／N24／N33／N34／N35→**結構性消失**（沒有字串比對／quote 豁免／代號與產業名偵測）；
N06→G11；N07→W16、G32；N08→V16；N09→V35；N10→V34；N11→R05；N12→R10；N13→M03；N14→M07；N15→S12；N19→T21；N20→T20；N22→T01；
N25→V33；N26→G03；N27→G18；N28→G19；N29→G13；N30→X01、X02；N31→V32；N32→V31、G23。

### 8.2 守衛→殺死它的測試（突變對照表）
170 個突變（每個＝對一個守衛恰好一處的拔除／反轉）：**170 killed、0 倖存、0 等價**。
回修過程中第一輪曾有 22 個倖存，處置：補測試（欄位展開矩陣、前置條件各自的精確閘門、行動證據的順序與受限事實、未帶鍵＋持股讀不到、`lines` 對垃圾 Digest 不 raise、lint 清單成員釘死）；或**刪掉重複／死碼**而非保留等價突變（行動段的 basis 與前置條件＋非空段重疊→移除；`expand` 的未知欄位檢查與數值例外 fallback 是死碼→移除；骨架簽名唯一的 `assert` 改為測試鎖死；builder 內重複的『最舊 stale 證據』選法改為共用 `grounding.oldest_stale_evidence`）。

| 突變 | 被拔掉／反轉的守衛 | 殺死它的測試（首個紅燈；`validator`／`grounding`／`summary` ＝ `tests/test_decision_digest_*.py`） |
|---|---|---|
| G01 | G6 無 Ref 句丟棄 | `grounding.py::test_g6_sentence_without_any_ref_is_dropped_not_fatal` |
| G02 | G6 丟棄後 surviving 不含該句 | `grounding.py::test_g6_sentence_without_any_ref_is_dropped_not_fatal` |
| G03 | surviving 不丟句（N26） | `grounding.py::test_g6_sentence_without_any_ref_is_dropped_not_fatal` |
| G04 | 缺段 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G05 | 重複段 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G06 | 未知段 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G07 | 段序 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G08 | 空段 | `grounding.py::test_g5_empty_section_rejected` |
| G09 | 段內重複句 | `grounding.py::test_g5_duplicate_sentence_rejected` |
| G10 | 必須明示（basis） | `grounding.py::test_g5_every_basis_item_must_be_disclosed` |
| G11 | basis 須綁定該 ref（N06） | `grounding.py::test_g5_every_basis_item_must_be_disclosed` |
| G12 | basis 須用對應句型 | `grounding.py::test_g5_unkeyed_holdings_must_be_disclosed` |
| G13 | 行動一對一 | `grounding.py::test_g4_action_list_must_match_digest_one_to_one_in_order` |
| G14 | 行動 id 清單取自 Digest 順序 | `summary.py::test_actions_keep_digest_order_even_when_ids_are_not_sorted` |
| G15 | accepted 只看非 G6 違規 | `grounding.py::test_g6_sentence_without_any_ref_is_dropped_not_fatal` |
| G16 | accepted 旗標 | `grounding.py::test_unparseable_input_is_validation_failure` |
| G17 | Digest 不合規即不比對 | `grounding.py::test_invalid_digest_means_no_grounding` |
| G18 | digest_invalid 旗標（N27） | `grounding.py::test_invalid_digest_means_no_grounding` |
| G19 | 結構失敗旗標（N28） | `grounding.py::test_unparseable_input_is_validation_failure` |
| G20 | usable 需 accepted | `grounding.py::test_g6_dropping_the_only_disclosure_triggers_g5` |
| G21 | clean 需無丟棄 | `grounding.py::test_g6_sentence_without_any_ref_is_dropped_not_fatal` |
| G22 | passed_gates 在結構失敗時為空 | `grounding.py::test_unparseable_input_is_validation_failure` |
| G23 | failed_gates 固定順序 | `grounding.py::test_failed_gates_are_in_fixed_gate_order` |
| G26 | basis：Risk Cap 卡面 | `grounding.py::test_g5_every_basis_item_must_be_disclosed` |
| G27 | basis：市場非 ok 事實 | `grounding.py::test_g5_missing_fact_must_be_disclosed` |
| G28 | basis：趨勢／合理區間 | `grounding.py::test_g5_every_basis_item_must_be_disclosed` |
| G29 | basis：產業 | `grounding.py::test_section_basis_for_baseline` |
| G30 | basis：持股讀不到 | `grounding.py::test_g5_unavailable_holdings_with_unkeyed_needs_both_disclosures` |
| G31 | basis：未帶鍵持股 | `grounding.py::test_g5_unkeyed_holdings_must_be_disclosed` |
| G32 | basis：已分類持股 | `grounding.py::test_g5_strategy_classified_entries_need_their_own_sentence` |
| G33 | basis：尚未設定策略分類 | `grounding.py::test_g5_strategy_classified_entries_need_their_own_sentence` |
| G34 | stale 事實對應句型 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M01 | INVALID 時不輸出段落 | `summary.py::test_q4_order_is_never_repaired_by_the_summary` |
| M02 | mode=RULE_ONLY | `summary.py::test_baseline_shape_state_and_mode` |
| M03 | 市場段含國際趨勢（N13） | `grounding.py::test_rule_draft_is_clean` |
| M04 | 市場段含 Risk Cap 卡面 | `grounding.py::test_rule_draft_is_clean` |
| M05 | 策略段：持股讀不到 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M06 | 策略段：未帶鍵持股 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M07 | 策略段：永遠展開 entries（N14） | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M08 | 策略段：個別持股 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M09 | 策略段：未設定策略 | `grounding.py::test_rule_draft_is_clean` |
| M10 | 行動段：不可得 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M11 | 行動段：規則層未產出 | `grounding.py::test_g4_actions_unavailable_and_none_shapes_are_state_bound` |
| M12 | 行動依 Digest 順序 | `grounding.py::test_rule_draft_is_clean` |
| M13 | 行動 stale 句型 | `grounding.py::test_g4_stale_evidence_must_be_disclosed_with_the_oldest_stale_fact` |
| M14 | 行動無 target 句型 | `grounding.py::test_g4_action_symbol_comes_only_from_target` |
| M15 | 事實：文字／值／百分比句型選擇 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M16 | 事實：INVALID 句型 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M17 | 事實：ok／stale／proxy 各自句型 | `grounding.py::test_rule_draft_clean_over_many_digests` |
| M18 | 產業段 | `grounding.py::test_rule_draft_is_clean` |
| R01 | mode 型別 | `grounding.py::test_summary_result_mode_must_be_existing_ab0_value` |
| R02 | INVALID 不得帶段落 | `grounding.py::test_summary_result_invalid_digest_cannot_carry_sections` |
| R03 | 摘要須乾淨（與 Digest 綁定） | `grounding.py::test_a7_consumers_must_use_surviving_not_the_original_draft` |
| R04 | 只要 accepted 不要 clean | `grounding.py::test_a7_consumers_must_use_surviving_not_the_original_draft` |
| R05 | retained_sections 推導（N11） | `grounding.py::test_summary_result_derives_everything_from_the_digest` |
| R06 | INVALID 的 retained_sections | `grounding.py::test_summary_result_invalid_digest_cannot_carry_sections` |
| R07 | state 取自 assess | `grounding.py::test_a7_consumers_must_use_surviving_not_the_original_draft` |
| R08 | section_availability 取自 assess | `grounding.py::test_summary_result_derives_everything_from_the_digest` |
| R10 | INVALID 通知：其他段落不保留（N12） | `grounding.py::test_summary_result_invalid_digest_cannot_carry_sections` |
| R11 | INVALID 通知：不輸出投資結論 | `grounding.py::test_summary_result_invalid_digest_cannot_carry_sections` |
| R12 | INVALID 通知：失敗閘門 | `grounding.py::test_summary_result_invalid_digest_cannot_carry_sections` |
| R13 | INVALID 通知：無效段落 | `summary.py::test_invalid_digest_outputs_no_investment_conclusion` |
| R14 | 渲染拒絕不可展開內容 | `grounding.py::test_render_sentence_refuses_unchecked_content` |
| R15 | lines 在 INVALID 時為空 | `grounding.py::test_summary_result_lines_on_garbage_digest_do_not_raise` |
| S01 | 型別：SummaryDraft | `grounding.py::test_unparseable_input_is_validation_failure` |
| S02 | 型別：sections tuple | `grounding.py::test_container_and_subclass_attacks_rejected` |
| S03 | 型別：SummarySection | `grounding.py::test_container_and_subclass_attacks_rejected` |
| S04 | 型別：sentences tuple | `grounding.py::test_container_and_subclass_attacks_rejected` |
| S05 | 型別：SummarySentence | `grounding.py::test_container_and_subclass_attacks_rejected` |
| S06 | 型別：segments tuple | `grounding.py::test_container_and_subclass_attacks_rejected` |
| S07 | segment 只能是 Lit／Ref（無任意字串） | `grounding.py::test_free_text_segment_is_structurally_impossible` |
| S08 | template_id 型別 | `grounding.py::test_non_str_template_id_or_field_is_structural` |
| S09 | field 型別 | `grounding.py::test_non_str_template_id_or_field_is_structural` |
| S10 | ref_id 問題 | `grounding.py::test_bad_ref_ids_are_structural` |
| S11 | ref_id 空白 | `grounding.py::test_bad_ref_ids_are_structural` |
| S12 | ref_id 控制字元 | `grounding.py::test_bad_ref_ids_are_structural` |
| S13 | ref_id 非空 str | `grounding.py::test_bad_ref_ids_are_structural` |
| T01 | 禁字元類別含 Cf | `validator.py::test_control_or_zero_width_in_texts_fail` |
| T02 | 禁字元類別含 Zl／Zp | `validator.py::test_exotic_whitespace_and_categories_in_texts_fail` |
| T03 | 禁字元類別含 Co | `validator.py::test_exotic_whitespace_and_categories_in_texts_fail` |
| T04 | 禁字元類別含 Cn | `validator.py::test_exotic_whitespace_and_categories_in_texts_fail` |
| T05 | 支援單位 | `validator.py::test_unsupported_market_unit_is_contract_drift` |
| T06 | 唯一允許的空白 | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| T07 | 段落順序 | `grounding.py::test_rule_draft_is_clean` |
| T08 | Risk Cap 卡面措辭 | `grounding.py::test_rendered_text_golden` |
| T09 | 模板：無法判定尾巴 | `grounding.py::test_rendered_text_golden` |
| T10 | 模板：過期日期前綴 | `summary.py::test_stale_proxy_failed_invalid_are_marked_not_upgraded` |
| T11 | 模板：代理尾巴 | `summary.py::test_stale_proxy_failed_invalid_are_marked_not_upgraded` |
| T12 | 模板：缺值開頭 | `summary.py::test_missing_never_becomes_neutral_or_zero` |
| T13 | 模板：行動不可得 | `summary.py::test_missing_never_becomes_neutral_or_zero` |
| T14 | 模板：行動 stale 前綴 | `grounding.py::test_g4_stale_evidence_must_be_disclosed_with_the_oldest_stale_fact` |
| T15 | 模板：策略項目尾巴 | `grounding.py::test_g5_strategy_classified_entries_need_their_own_sentence` |
| T16 | 模板：未設定策略 | `grounding.py::test_rendered_text_golden` |
| T17 | 模板：未帶鍵尾巴 | `grounding.py::test_g5_unkeyed_holdings_must_be_disclosed` |
| T18 | 模板：無行動 | `grounding.py::test_g4_actions_unavailable_and_none_shapes_are_state_bound` |
| T19 | 洗白字眼含「中性」（lint 清單） | `grounding.py::test_lint_actually_detects_forbidden_words` |
| T20 | 確定語氣含「穩健」（lint 清單） | `grounding.py::test_lint_term_lists_pinned_members` |
| T21 | 燈號符號含紅燈（lint 清單） | `grounding.py::test_lint_actually_detects_forbidden_words` |
| T22 | 缺值原因標籤：抓取失敗 | `summary.py::test_stale_proxy_failed_invalid_are_marked_not_upgraded` |
| T23 | 市場位階標籤 | `grounding.py::test_rendered_text_golden` |
| V01 | 呼叫 AB-0 validate() | `validator.py::test_schema_version_drift_is_invalid` |
| V02 | 呼叫 AB-1 validate_rule_ids | `validator.py::test_rule_id_not_in_allowlist_fails_with_rule_gate` |
| V03 | 呼叫 AB-1 validate_action_order | `validator.py::test_action_order_violation_fails_with_order_gate` |
| V04 | 前三者全過才跑自有檢查 | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V05 | 非 DecisionDigest → INVALID | `validator.py::test_non_digest_is_invalid_not_raise` |
| V10 | 控制／零寬／格式／私用區等類別 | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V11 | 非普通空格的空白（NBSP／全形空白） | `validator.py::test_exotic_whitespace_and_categories_in_texts_fail` |
| V12 | 孤立組合記號 | `validator.py::test_isolated_combining_marks_fail` |
| V13 | 孤立組合記號：空白之後 | `validator.py::test_isolated_combining_marks_fail` |
| V14 | 控制字元檢查（action 文字） | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V15 | 控制字元檢查（strategy_source） | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V16 | 控制字元檢查（市場事實文字） | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V17 | 市場事實單位須在支援範圍 | `validator.py::test_unsupported_market_unit_is_contract_drift` |
| V18 | 保留前綴檢查 | `validator.py::test_risk_cap_fact_id_with_reserved_prefix_fails` |
| V19 | fact／action id 碰撞 | `validator.py::test_fact_and_action_id_collision_fails` |
| V20 | 多依據合併不得升格 | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V21 | 多依據合併：全 UNAVAILABLE | `validator.py::test_all_unavailable_is_unavailable_not_neutral` |
| V22 | 市場段納入定義狀態段 | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V23 | 策略段至多 PARTIAL | `validator.py::test_strategy_section_availability_derivation` |
| V24 | 策略段：持股讀不到 → UNAVAILABLE | `validator.py::test_strategy_section_with_unreadable_holdings_stays_unavailable` |
| V25 | derive_state：全 AVAILABLE 才 VALID | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V26 | derive_state：全 UNAVAILABLE | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V27 | assess 回傳推導狀態 | `validator.py::test_all_unavailable_is_unavailable_not_neutral` |
| V28 | INVALID 不給 section_availability | `validator.py::test_invalid_sections_mapping_and_order` |
| V29 | holdings 違規影響兩個策略段 | `validator.py::test_invalid_sections_mapping_and_order` |
| V30 | 跨段違規標記為 * | `validator.py::test_schema_version_drift_is_invalid` |
| V31 | failed_gates 固定順序 | `validator.py::test_failed_gates_are_in_canonical_order_not_set_order` |
| V32 | 非 Digest 只回報 AB0 閘門 | `validator.py::test_non_digest_is_invalid_not_raise` |
| V33 | 行動段可得性取自 actions 段 | `validator.py::test_all_unavailable_is_unavailable_not_neutral` |
| V34 | risk_cap id 納入保留前綴檢查 | `validator.py::test_risk_cap_fact_id_with_reserved_prefix_fails` |
| V35 | 觀測值 id 納入碰撞檢查 | `validator.py::test_observation_fact_id_is_part_of_the_id_namespace` |
| W01 | 模板白名單 | `grounding.py::test_g1_unknown_template_id_is_not_a_loophole` |
| W02 | ref 必須在 Digest | `grounding.py::test_g1_unknown_ref` |
| W03 | 骨架必須吻合白名單句型 | `grounding.py::test_g1_unknown_field_name` |
| W04 | 骨架查表不得 fallback 到任意句型 | `grounding.py::test_a5_unit_or_whitespace_suffix_cannot_be_appended` |
| W05 | 同 slot 必須同一項目 | `grounding.py::test_rule_draft_is_clean` |
| W06 | 欄位須可展開 | `grounding.py::test_g2_risk_cap_values_and_dates_are_restricted` |
| W07 | 句型須屬該段 | `grounding.py::test_a_free_ride_section_ref_cannot_carry_extra_claims` |
| W08 | 前置條件 | `grounding.py::test_g2_unit_is_decided_by_template` |
| W09 | 前置條件：市場事實群組 | `grounding.py::test_pre_wrong_group_when_market_shape_is_applied_to_other_groups` |
| W10 | 前置條件：狀態須吻合 | `grounding.py::test_g3_status_cannot_be_upgraded_or_downgraded_by_picking_another_shape` |
| W11 | 前置條件：單位由模板決定 | `grounding.py::test_g2_unit_is_decided_by_template` |
| W12 | 前置條件：段名 | `grounding.py::test_g5_industry_and_trend_wording_belongs_to_its_own_section` |
| W13 | 前置條件：section 名稱 | `grounding.py::test_pre_section_shape_must_cite_its_own_section_ref` |
| W14 | 前置條件：Digest 狀態 | `grounding.py::test_g4_actions_unavailable_and_none_shapes_are_state_bound` |
| W15 | 前置條件：持股讀不到不得列個別持股 | `grounding.py::test_g5_strategy_entry_shape_cannot_be_used_when_holdings_unavailable` |
| W16 | 前置條件：策略分類屬於該段 | `grounding.py::test_g5_strategy_classified_entries_need_their_own_sentence` |
| W17 | 前置條件：行動 target 一致 | `grounding.py::test_pre_action_target_consistency` |
| W18 | 前置條件：stale 句型須指向最舊證據 | `grounding.py::test_g4_stale_evidence_must_be_disclosed_with_the_oldest_stale_fact` |
| W19 | 前置條件：有 stale 證據不得用一般句型 | `grounding.py::test_g4_stale_evidence_must_be_disclosed_with_the_oldest_stale_fact` |
| W20 | 最舊 stale 證據（as_of 排序） | `summary.py::test_stale_evidence_discloses_the_oldest_date_regardless_of_evidence_order` |
| W21 | 受限群組不當 stale 證據 | `summary.py::test_restricted_stale_evidence_does_not_break_or_leak` |
| W22 | missing 句型含 FAILED | `grounding.py::test_rule_draft_clean_over_many_digests` |
| X01 | 受限群組：不得展開值／文字／日期 | `grounding.py::test_g2_risk_cap_values_and_dates_are_restricted` |
| X02 | 受限群組判斷 | `grounding.py::test_g2_risk_cap_values_and_dates_are_restricted` |
| X03 | 持股事實只開放資料日 | `grounding.py::test_expand_field_matrix_is_pinned` |
| X04 | strategy_source 不可展開 | `grounding.py::test_user_free_text_strategy_source_never_expands` |
| X06 | 行動代號只取自 target | `grounding.py::test_g4_action_symbol_comes_only_from_target` |
| X08 | 文字欄位需有值 | `grounding.py::test_expand_field_matrix_is_pinned` |
| X09 | 值欄位需有值 | `grounding.py::test_user_free_text_strategy_source_never_expands` |
| X10 | section 標籤僅四段 | `grounding.py::test_expand_field_matrix_is_pinned` |
| X11 | 措辭僅 risk_cap | `grounding.py::test_expand_field_matrix_is_pinned` |
| X12 | count 僅 holdings | `grounding.py::test_expand_field_matrix_is_pinned` |
| X13 | NOT_WIRED 標示語 | `grounding.py::test_expand_not_wired_marker_follows_digest_definition_state` |
| X14 | valuation 標示語 | `grounding.py::test_rule_draft_is_clean` |
| X15 | number_literal 固定小數 | `grounding.py::test_number_literal_is_fixed_point_shortest_roundtrip` |
| X16 | number_literal 拒絕非有限 | `grounding.py::test_number_literal_rejects_non_finite_or_non_real` |
| X17 | number_literal 拒絕 bool | `grounding.py::test_number_literal_rejects_non_finite_or_non_real` |
| X18 | 觀測值受限 | `grounding.py::test_g2_trend_observations_are_restricted` |
| X19 | Risk Cap 事實受限 | `grounding.py::test_g2_risk_cap_values_and_dates_are_restricted` |

## 9. 已知限制與未驗證項（誠實揭露）

- **單組撰寫、回修版未經第二組獨立複驗**；承重判斷是 INVALID 不保留、句型白名單的完備性（是否漏了該有的句型／多了不該有的）、Risk Cap 保守顯示、VALID 不可達。
- **結構性限制（規則式驗證抓不到的剩餘風險）**：
  1. 白名單只保證「摘要說的話都是我們預先寫好的句型＋Digest 的原文」；**Digest 原文本身**（`Fact.text`／`ActionRef.text`）是規則層輸出，摘要逐字轉述，不再檢查其內容。若規則層輸出了誤導性文字，摘要會忠實轉述。
  2. **A10（AB-1 缺口，非本批引入，本批不改 AB-1）**：`ActionRef.text` 與其 `rule`（分支碼）、與 `Fact.text` 之間**沒有綁定**，Digest 層放行「行動文字與規則不對應」。測試 `test_known_gap_a10_...` 釘住現況。BACKLOG 備註：`AB1-ACTION-TEXT-RULE-BINDING`（由總管登記）。
  3. 句型選擇權仍在呼叫端：AI 可以省略 ok 的事實、調整同段內句子順序（行動段除外），也可以只挑對自己有利的 ok 事實 —— 但**不能**省略非 ok 的依據、不能改寫、不能加字。
  4. 行動證據若指向 Risk Cap／觀測值這類受限事實，其過期狀態無法揭露（資料日受限）；AB-1 現不產生這種證據。
  5. Digest 的 `generated_at`／時間一致性等仍只信 AB-0 的檢查。
- 本批**沒有 production caller、沒有 UI**；沙箱 Python 3.13，CI 3.11 未實跑；未做網路／AI／Sheet 相關的任何實測（本批本來就沒有）。
- `AB1-ACTION-TEXT-AI-WORDING`（行動文字可能含 "AI" 字樣）與本批無交互：行動文字走逐字展開，不被檢查。
- G2 對 AI 偏嚴是刻意 fail-closed；放寬須走 Gate。
