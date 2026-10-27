# AB-2a 規格：Decision Digest 的 Grounding／Validator（G1～G6）＋fail-safe 降級＋規則式摘要（無 AI）（2026-10-27）

> **決策者：AI 總管內部（技術實作，依 `CLAUDE.md` §-1.5 v3 §03-1 內部自決）；非客戶裁示。**
> 本檔由執行 AI 單組撰寫，**未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。
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
| `shared/decision_digest_terms.py` | L0 | 全部**具名常數**：五段鍵／標籤、引用 id 前綴、標示語、洗白／行動／方向／確定語氣字眼、代號／日期／數字樣式、閘門 id、顯示標籤。零邏輯。 |
| `shared/decision_digest_validator.py` | L0 | `assess_digest(digest) -> DigestAssessment`（Digest 自身檢查＋四態）、`SummaryState`、`DigestViolation`、`section_availability`、`derive_state`、`strategy_entries`。 |
| `shared/decision_digest_grounding.py` | L0 | 最小輸出格式 `SummaryDraft／SummarySection／SummarySentence`；`check_summary(digest, draft) -> GroundingReport`（G1～G6）；`SummaryResult`（統一摘要結果型別）；`build_ref_index`／`section_basis`／`number_literal`／`remove_quotes`。 |
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

**AB-2a 新增的三個檢查（只收緊，不放寬任何 AB-0／AB-1 語意）**：
1. `control_chars_in_text`（閘門 `AB2A_TEXT`）：`Fact.text`／`ActionRef.text`／`strategy_source` 含控制字元（Cc）或零寬／格式字元（Cf）。AB-0 沒禁；摘要要**逐字**引用這些文字，不可見字元會讓逐字比對與字眼檢查失真。
2. `ref_id_reserved`／`ref_id_collision`（閘門 `AB2A_REFS`）：fact_id／action_id 以保留前綴 `section:`／`holding:` 開頭，或 fact_id 與 action_id 相同 —— evidence 命名空間會含糊。
3. 輸入不是（恰好）`DecisionDigest` → INVALID，不 raise。

### 四態（`SummaryState`）

| 態 | 條件 | 輸出 |
|---|---|---|
| **INVALID**（contract drift） | 上列任一違規 | **不輸出任何投資結論**：`sections=()`、`retained_sections=()`；`notices` 指出**哪一段 invalid**（`invalid_sections`）、**哪個閘門失敗**（`failed_gates`）、違規代碼、並明說**其他段落未保留**。 |
| **UNAVAILABLE** | 合規，且五段依據皆 UNAVAILABLE | 五段都輸出，每項以「⬜ …資料不足，無法判定」明示。 |
| **PARTIAL** | 合規，部分可用 | 只輸出可證明部分；缺的明示；**整體不標 AVAILABLE**。 |
| **VALID** | 合規，五段依據皆 AVAILABLE | ⚠️ **現行契約下不可達**（INFERENCE→已測）：產業趨勢與策略分類的正式定義未核准，產業段恆 UNAVAILABLE、市場段恆含「尚未定義」的趨勢。這是誠實，不是 bug。 |

availability **只由資料推導**（沿用各段已推導的 `availability`；市場段＝market／risk_cap／tw／intl／valuation 合併、定義狀態段恆 UNAVAILABLE ⇒ 市場段至多 PARTIAL；存股／資本利得＝持股讀不到→UNAVAILABLE、無該策略 entry→UNAVAILABLE、有→至多 PARTIAL（基本面判定未接線）；行動＝actions 段自己的）。
`SummaryResult` 在**建構時**強制：`state` 必須等於由各段可得性推導的結果（不得升格／降格）、`mode` 必須是 AB-0 既有 `AiParticipation`、INVALID 不得帶任何段落。

**INVALID 的保留政策（內部決定）**：違規一旦涉及跨物件不變量（fact_id 唯一、evidence 指向可用事實、行動 vs 持股），代表 builder 違反契約、影響範圍未知；AB-0 的 `evidence_refs` 本身就是跨段依賴，無法證明段落彼此獨立 → **整份不採信**，`retained_sections` 恆為空。替代方案「保留未受影響的段落」需要先證明段間無依賴，不採。（單組判斷，待覆核。）

## 3. 最小輸出格式契約（AB-2b 不得因它被迫採用某種 prompt／傳輸）

```
SummaryDraft(sections=(SummarySection(key, sentences=(SummarySentence(text, evidence_refs=(id, ...)), ...)), ...))
```
- `key`：`market／industry／buy_and_hold／capital_gain／actions`（五段，固定順序）。
- `text`：單行非空 str，不得含控制／零寬字元；`evidence_refs`：tuple of 非空無空白 str、不重複。
- **無法解析的輸入（None／dict／str／子類別／型別錯）一律視為驗證失敗**（`structural_failure=True`，`accepted=False`，`surviving=None`）；永不 raise。

**引用 id 空間**（`evidence_refs` 只能指向這些；G1 引用封閉）：Digest 內任一 `fact_id`／`action_id`；`section:<digest 段名>`（讓「這段沒資料」也有依據，因 AB-0 的定義狀態段沒有 facts）；`holding:<portfolio_id>:<symbol>`。每個引用項帶：狀態（決定要求的標示語）、可逐字引用的文字、允許的數字字面、資料日、代號、受限旗標。

## 4. G1～G6 在「無 AI」版本的落地

核心設計：**逐字引用（quote）豁免** —— 句中與所引項目的 `Fact.text`／`ActionRef.text`／`strategy_source`／代號逐字相同的片段視為 Digest 自己的文字，**不做字眼檢查**；**其餘殘餘文字**才檢查。AI 要表達行動／狀態／數字，只能逐字搬運 Digest，不能改寫。引用邊界規則：引用首／尾若是 ASCII 英數字，其前後不得緊接英數字（尾端還不得緊接 `.數字`）；純數字引用在日期遮罩**之後**才移除 —— 防止「引用 `7`」把 `72.5` 吃掉。

| 閘門 | 檢查（違規 code） | 規則式摘要如何滿足（基準） | 已知限制 |
|---|---|---|---|
| **G1 引用封閉** | ① `ref_not_in_digest`；② `symbol_not_in_digest`（4–6 位數字代號須屬 Digest 持股／行動目標；英文大寫 2–5 字母代號須屬 Digest 或 `ETF／EPS／PE`）；③ `industry_not_in_digest`（官方 35 類產業名與其「去業」形一律拒收 —— Digest 的 industry 段恆「尚未定義」，**沒有允許名單**）；④ `state_word_not_in_digest`（燈號符號、regime 英文狀態詞只能逐字引用） | 只引用 Digest 內的 id；代號取自 Digest 鍵 | 產業名只涵蓋官方代碼表（`shared/industry_codes`），**不含** sector_flow 的 40 板塊名；英文以外語言、同義詞擋不住 |
| **G2 數字一致** | `number_not_literal`（數字須「字面」等於所引項目的值：`number_literal`＝整數 `str(int)`、浮點最短往返固定小數；**不補零、不截斷、不四捨五入、不換算**，`72.50`≠`72.5`、`60`≠`60.0`）；單位吻合（有 unit→緊接 unit；無 unit→後面不得緊接 `%`／文字）；`date_not_in_digest`（ISO 日期須等於所引項目的 as_of）；`restricted_value`（Risk Cap 區段與「僅供參考」觀測值的數字**一律不得出現**）；`non_finite_token`（nan／inf／∞）；`non_ascii_digit`（全形／其他書寫系統數字） | 數字只來自 Digest 的值字面、資料日、`unkeyed_count` | ⚠️ **只擋阿拉伯數字**：「七十二點五」「三成」這類中文數字、`百分之` 擋不住；千分位 `1,234` 會被拆成兩個 token 而失敗（fail closed） |
| **G3 狀態不可升級** | `washing_term`（中性／正常／維持／續抱／持有／觀望／不動作…、neutral／hold／normal…，殘餘文字內一律拒收）；`placeholder_segment`（沿用 AB-0 `PLACEHOLDER_TEXTS`，整段等於佔位字）；`missing_marker`（引用 missing／failed／invalid 須含「資料不足」或「無法判定」；stale 須含「資料已過期」；proxy 須含「代理估算」；未定義／未接線／研究框架／Risk Cap 須含各自標示語）；`assertive_tone`（引用非 ok 項目時不得出現「確定／肯定／必然／穩健／無虞…」） | 缺值一律「⬜ …資料不足，無法判定」；過期標資料日；代理標「非正式資料」 | 字眼清單是盡力而為；比對前做 NFKC＋去零寬＋去空白＋casefold，擋全形／拆字，但擋不住同義詞 |
| **G4 不新增結論類別** | `new_action_term`（買進／賣出／加碼／減碼／停利／換股／續抱…、buy／sell／hold 只能出現在逐字引用內）；`new_direction_term`（變強／轉弱／衰退／崛起／偏多／偏空…只能在逐字引用內）；`action_text_not_verbatim`（引用行動 id 的句子必須逐字含該 `ActionRef.text`） | 行動句＝`{symbol}：{ActionRef.text}`，逐字、依 Digest 順序、不重排 | Digest 沒有任何方向欄位（趨勢／產業＝尚未定義），故方向字眼一律只能引用；AI 要改寫行動就會被擋（刻意，fail closed） |
| **G5 段落完整** | `missing_section`／`duplicate_section`／`unknown_section`／`section_order`（五段齊全、唯一、固定順序）；`empty_section`；`missing_disclosure`（每段對 Digest 中**非 ok 的依據**都須有句子明示：缺資料的市場事實、台股／國際趨勢、大盤合理區間、Risk Cap 卡面措辭、產業、持股讀不到／未帶鍵持股／尚未設定策略分類／策略分類但判定未接線、行動不可得／規則層未產出行動）；`ref_out_of_scope`（句子只能引用屬於該段的項目，防止以無關事實填充） | 每個非 ok 依據都有對應句 | 「該段退回規則式」的**政策**由呼叫端（AB-2b／AB-5）決定；本檔只提供 `failed_gates`／違規的 `section` |
| **G6 依據可回溯** | `no_evidence_ref`：`evidence_refs` 為空的句子**丟棄**（不使整份失敗；不再檢查其他閘門）；丟棄後該段若失去依據，由 G5 抓出 | 每句都帶至少一個引用 | — |

`GroundingReport`：`accepted`（無任何 STRUCT／DIGEST／G1～G5 違規；G6 丟棄不影響）、`violations`、`dropped`、`failed_gates`（含 G6）、`passed_gates`（結構失敗／Digest 不合規時為空 —— 沒檢查完就不宣稱通過）、`surviving`（丟棄 G6 句後的摘要）。
G7（輸出過濾）**不在本批**。

## 5. 規則式摘要（`build_rule_summary`）

只**重新組織** Digest 已有內容：不新增數值／買賣判斷／門檻／權重／產業結論／趨勢結論／候選股／AI 信心機率。

| 段 | 內容（全部取自 Digest；缺資料處明示） |
|---|---|
| 市場 | 位階／燈號／健康度逐字（有資料日）；Risk Cap 只顯示客戶核准卡面措辭「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」（**不顯示 Risk Cap 區段任何數值**，DEC-081 Q2-2）；台股／國際趨勢「尚未定義，無法判定」；大盤合理區間「研究框架，未啟用，無法判定」（**不出區間、不出 EPS／PE**） |
| 產業 | 「產業趨勢：尚未定義，資料不足，無法判定」（不補多空、不列任何產業名） |
| 存股／資本利得 | 持股讀不到→「持股資料不足，無法判定（原因）」；未帶鍵持股→「另有 N 檔持股缺少投資組合鍵，未納入判讀」（N＝Digest 的 `unkeyed_count`）；無該策略 entry→「尚未設定投資策略分類，無法判定」；有→「{代號}：策略分類為…（來源：…）；基本面與配置判定尚未接線，無法判定」 |
| 本期行動 | 每項＝`{代號}：{ActionRef.text 逐字}`，沿用 Digest 順序（DEC-092 Q4／AB-1：汰弱＞停利＞趨勢暫停＞加碼，最多 3 項，**不重排**；Digest 若違反序 → INVALID，不修復）；stale 依據加「資料已過期，資料日」；無法判定→「⬜ 本期行動：資料不足，無法判定」；AB-0 允許的「available 且 0 筆」→「本期行動：規則層未產出行動」（不得寫成維持／持有） |

**自檢（基準對照）**：回傳前一律 `check_summary`，未通過即 `ValueError`（摘要或驗證器有 bug，Fail Loud）。行動句只引用行動 id＋屬於本段依據的持股事實；evidence 若指向市場／Risk Cap 事實，該事實不在本段引用（行動 id 本身可回溯）。
`portfolio_id` 無正式來源：holdings 依 AB-1 維持 UNAVAILABLE／PARTIAL，缺鍵持股只以計數呈現，**不以 symbol／Sheet 名稱代鍵**（以真實 builder 輸入實測）。

## 6. 與 AB-2b 的介面邊界

AB-2a **提供**：`check_summary`（唯一的 G1～G6 檢查器）、`SummaryDraft` 最小格式、`SummaryResult`（`mode`＝AB-0 既有 `AiParticipation`）、`build_rule_summary`（降級用的基準答案）、`GroundingReport.passed_gates／failed_gates`（可對映 Digest 的 `ai_passed_checks／ai_failed_checks`）。
AB-2b **負責**（本批不碰，亦不預先決定）：prompt、輸出解析（AI 文字→`SummaryDraft`；解析失敗＝`check_summary(digest, None)`）、傳輸／金鑰／退避／用量、何時呼叫（Decision Gate：新 AI 出口屬 substantive AI behavior）、驗證通過後 `mode=AI_EXPLAINED`／失敗後 `AI_REJECTED` 並退回 `build_rule_summary`。
⚠️ **需 AB-2b 自行決定的映射**：`structural_failure` 沒有對應的 G id；而 AB-0 的 `ai_rejected` 要求 `ai_failed_checks` 非空 —— 結構失敗要記成哪個（或哪些）G id，本檔不替它決定。
禁止的資料流：Data→LLM；AI 輸出寫回 Digest；AI 修 Digest。

## 7. 內部設計決定（**待登記 DEC；非客戶裁示**）與與正式文件的差異

1. **三個 L0 檔＋一個 L3 檔**（terms／validator／grounding／summary）；常數集中於 terms（`CLAUDE.md` §3.3）。
2. **INVALID 整份不採信**（§2）。
3. **逐字引用豁免＋殘餘文字檢查**（§4）：AI 不能改寫行動／狀態，只能逐字搬運。fail closed 的代價：合法的 AI 改寫也會被退回規則式 —— AB-2b 若覺得太嚴，須走 Gate 調整，不得在本檔偷放寬。
4. **引用 id 空間擴充**（`section:`／`holding:`）：因為 AB-0 契約沒有 C §4 草案的 `sources[]`，且定義狀態段／缺值段沒有 fact 可引。
5. **Risk Cap 顯示保守**：C §2.4／DEC-081 Q2-2 禁止顯示未核准的 Risk Cap 獨立數字。本批**連 `exposure_lo/hi_pct`（建議持股水位）也不顯示**（`final_hi` 已含 cap，顯示等於繞過）。⚠️ **需總管／客戶判斷**：「建議總持股水位」是 C §3.1 市場段的內容，是否核准顯示 lo/hi 屬 RC-VISIBILITY Gate，本批不替它決定。
6. **與 C §2.4 字面的差異（以正式文件為準；以下是無法照字面落地之處）**：
   - G1 的允許名單寫 `holdings[]`／`candidates[]`／`industry_trend[]`；AB-0 Digest **沒有** candidates／industry_trend，故允許名單＝持股／行動目標代號；產業名稱**無允許名單**（一律拒收）。
   - G3 的洗白字眼 C 列「中性／正常／維持／續抱」＋ `PROJECT_RULES.md` §16.1 的 HOLD，本批擴為較長清單（加「持有／觀望／不動作／照舊／如常／不變／無異常」與英文）；且**範圍**限定為殘餘文字（逐字引用豁免），否則規則層自己的文字（如「先觀望」）會被誤殺。
   - G5 C 寫「該段退回規則式」，G1～G4 寫「退回規則式摘要」（整份）：本檔只回報事實，不執行退回政策。
   - C §2.5 的「`ai_participation.validation`」在 AB-0 落地為 `ai_passed_checks／ai_failed_checks`（C §11 已記），本檔以 `passed_gates／failed_gates` 對映。
7. **VALID 態現行不可達**（§2）。
8. 單元測試的隨機 Digest 用標準庫 `random` 固定種子（repo 沒有 `hypothesis`；不為本批新增依賴）。

## 8. 測試與突變

見交付報告與 PR（數字隨最終驗證更新；本檔不寫會漂移的量測值，`CLAUDE.md` §8.2.A.0 規則 4）。
突變腳本：`/tmp/claude-0/-home-user-my-stock-dashboard/92636036-60ab-5183-a29d-e08e992434fc/scratchpad/ab2a_mutation.py`（沙箱 scratchpad，未入庫；要重跑請連同本節對照表一併搬進 repo 或重寫）（可重跑；複製 repo 後在副本突變，不動真實工作樹）；
指令：`/tmp/claude-0/venv/bin/python /tmp/claude-0/-home-user-my-stock-dashboard/92636036-60ab-5183-a29d-e08e992434fc/scratchpad/ab2a_mutation.py --jobs 4`（repo 根目錄執行）。
「守衛→殺死它的測試」對照表見報告；零倖存（等價突變須另列理由）。

### 8.1 守衛→殺死它的測試（突變對照表；最終一輪，單組自跑）

133 個突變：132 killed、1 個經論證的等價突變（G512）、0 倖存。每個突變＝對一個守衛恰好一處的拔除／反轉
（validator 沿用檢查與自有檢查、G1～G6 各子檢查、`SummaryResult` 不變量、規則式摘要各分支、字眼清單成員、正規式樣式）。
前一輪曾有 9 個倖存，皆已補測試並重跑全部：G210（受限項目的資料日）、G213（引用開頭邊界）、G303（缺值佔位字——原測試被
`missing_marker` 搶先擋下，改為標示語齊全只差佔位字）、G404（行動文字須是逐字引用）、G511（持股讀不到須引用 holdings 段）、
T13（Risk Cap 卡面措辭須逐字等於客戶核准字串）、V05（非 Digest 的精確閘門）、V24（持股讀不到時策略段不得升格）；G512 見下。
**G512（等價）**：G5 產業段的 basis 與 G3 標示語＋範圍檢查重疊——產業段只允許引用 `section:industry`（其他引用先被
`ref_out_of_scope` 擋），而引用它的句子必須含「尚未定義」（G3 `missing_marker`），故任何通過範圍＋G3 的句子必然已滿足 basis；
保留為縱深防禦（日後若放寬產業段引用範圍才會咬人）。

| 突變 | 被拔掉／反轉的守衛 | 殺死它的測試（首個紅燈；`validator`／`grounding`／`summary` ＝ `tests/test_decision_digest_*.py`） |
|---|---|---|
| G101 | G1 引用封閉：未知 ref 回報 | `grounding.py::test_g1_unknown_evidence_ref` |
| G102 | G5 段內引用範圍 | `grounding.py::test_g5_ref_out_of_scope_blocks_padding` |
| G103 | G1 英文代號 | `grounding.py::test_g1_latin_ticker` |
| G104 | G1 產業名稱 | `grounding.py::test_g1_industry_name_rejected_because_digest_has_no_industry_allowlist` |
| G105 | G1 燈號符號 | `grounding.py::test_g1_state_words_only_via_verbatim_quote` |
| G106 | G1 regime 英文狀態詞 | `grounding.py::test_g1_state_words_only_via_verbatim_quote` |
| G107 | G1 未知數字代號 | `grounding.py::test_g1_known_symbol_ok_unknown_symbol_rejected` |
| G108 | G1 代號白名單來自 Digest | `grounding.py::test_g1_known_symbol_ok_unknown_symbol_rejected` |
| G201 | G2 非 ASCII 數字 | `grounding.py::test_g2_non_ascii_digits_rejected` |
| G202 | G2 NaN／inf | `grounding.py::test_g2_non_finite_tokens_rejected` |
| G203 | G2 日期須等於資料日 | `grounding.py::test_g2_non_literal_numbers_rejected` |
| G204 | G2 字面（非數值）相等 | `grounding.py::test_g2_non_literal_numbers_rejected` |
| G205 | G2 單位須吻合 | `grounding.py::test_g2_non_literal_numbers_rejected` |
| G206 | G2 無單位時後面不得緊接 %／文字 | `grounding.py::test_g2_non_literal_numbers_rejected` |
| G207 | G2 無單位時後面不得緊接 %（僅禁 %） | `grounding.py::test_g2_non_literal_numbers_rejected` |
| G208 | G2 Risk Cap 數字受限（出現即 restricted_value） | `grounding.py::test_g2_risk_cap_numbers_are_restricted` |
| G209 | G2 受限項目不貢獻允許的數字 | `grounding.py::test_g2_risk_cap_numbers_are_restricted` |
| G210 | G2 受限項目的資料日也不貢獻 | `grounding.py::test_g2_restricted_fact_dates_are_not_citable_either` |
| G211 | G2 純數字引用延後到日期遮罩之後 | `summary.py::test_property_random_digests_never_raise_and_never_launder_missing` |
| G212 | 引用邊界：尾端 | `grounding.py::test_remove_quotes_boundaries` |
| G213 | 引用邊界：開頭 | `grounding.py::test_quote_removal_start_boundary_blocks_digit_laundering` |
| G214 | number_literal 固定小數（不用科學記號） | `grounding.py::test_number_literal_is_fixed_point_shortest_roundtrip` |
| G215 | number_literal 拒絕非有限 | `grounding.py::test_number_literal_rejects_non_finite_or_non_real` |
| G216 | number_literal 拒絕 bool | `grounding.py::test_number_literal_rejects_non_finite_or_non_real` |
| G217 | 觀測值為受限項目 | `grounding.py::test_trend_observations_are_reference_only_and_never_citable_as_numbers` |
| G218 | Risk Cap 事實為受限項目 | `grounding.py::test_g2_risk_cap_numbers_are_restricted` |
| G219 | unkeyed 計數是允許的數字字面 | `grounding.py::test_rule_summary_passes_over_many_digests` |
| G301 | G3 中文洗白字眼 | `grounding.py::test_g3_washing_terms_rejected_anywhere_outside_quotes` |
| G302 | G3 英文洗白字眼 | `grounding.py::test_g3_washing_terms_rejected_anywhere_outside_quotes` |
| G303 | G3 缺值佔位字單獨成段 | `grounding.py::test_g3_placeholder_segment_rejected` |
| G304 | G3 缺值／過期／代理須明示 | `grounding.py::test_g3_missing_fact_requires_insufficient_marker` |
| G305 | G3 非 ok 不得確定語氣 | `grounding.py::test_g3_assertive_tone_forbidden_for_non_ok_refs_only` |
| G306 | G3 事實狀態 → 標示語（stale） | `grounding.py::test_g3_stale_and_proxy_markers` |
| G307 | G3 事實狀態 → 標示語（proxy） | `grounding.py::test_g3_stale_and_proxy_markers` |
| G308 | G3 事實狀態 → 標示語（missing 類） | `grounding.py::test_g3_missing_fact_requires_insufficient_marker` |
| G309 | G3 定義狀態段標示語 | `ERROR tests/grounding.py::test_rule_summary_passes_all_gates` |
| G310 | G3 正規化去空白（洗白字眼拆字） | `grounding.py::test_g3_missing_fact_requires_insufficient_marker` |
| G311 | G3 正規化 NFKC（全形） | `grounding.py::test_g3_washing_terms_survive_whitespace_and_fullwidth_tricks` |
| G401 | G4 新行動字眼 | `grounding.py::test_g4_new_action_terms_rejected_outside_quotes` |
| G402 | G4 新方向字眼 | `grounding.py::test_g4_direction_terms_rejected` |
| G403 | G4 行動句必須逐字含行動文字 | `grounding.py::test_g4_actions_only_via_verbatim_digest_action` |
| G404 | G4 行動文字須納入逐字引用 | `grounding.py::test_action_text_is_a_verbatim_quote_even_without_the_evidence_fact` |
| G501 | G5 缺段 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G502 | G5 重複段 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G503 | G5 未知段 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G504 | G5 段序 | `grounding.py::test_g5_missing_duplicate_unknown_and_order_of_sections` |
| G505 | G5 空段 | `grounding.py::test_g5_empty_section_rejected` |
| G506 | G5 逐項明示 | `grounding.py::test_g5_every_basis_item_must_be_disclosed` |
| G507 | G5 basis：市場段 Risk Cap 卡面 | `grounding.py::test_g5_every_basis_item_must_be_disclosed` |
| G508 | G5 basis：市場段缺值事實 | `grounding.py::test_g5_missing_fact_must_be_disclosed` |
| G509 | G5 basis：未帶鍵持股 | `grounding.py::test_g5_unkeyed_holdings_must_be_disclosed` |
| G510 | G5 basis：策略分類未設定 | `grounding.py::test_g5_strategy_classified_entries_need_not_wired_disclosure` |
| G511 | G5 basis：持股讀不到 | `grounding.py::test_g5_holdings_unavailable_must_cite_the_holdings_section_itself` |
| G512 | G5 basis：產業段 | **等價（已論證，見上）** |
| G513 | G5 basis：無行動／行動不可得 | `grounding.py::test_g5_actions_disclosure_must_cite_the_actions_section_itself` |
| G514 | G5 basis：已分類持股須明示未接線 | `grounding.py::test_g5_strategy_classified_entries_need_not_wired_disclosure` |
| G601 | G6 無依據句丟棄 | `grounding.py::test_g6_sentence_without_refs_is_dropped_not_fatal` |
| G602 | G6 丟棄後不再檢查該句 | `grounding.py::test_g6_sentence_without_refs_is_dropped_not_fatal` |
| G603 | accepted 只看非 G6 違規 | `grounding.py::test_unparseable_input_is_validation_failure` |
| G604 | G6 不阻擋 accepted（只阻擋其他） | `grounding.py::test_g6_sentence_without_refs_is_dropped_not_fatal` |
| G605 | Digest 不合規即不比對 | `grounding.py::test_invalid_digest_means_no_grounding` |
| G606 | STRUCT：型別（SummaryDraft） | `grounding.py::test_unparseable_input_is_validation_failure` |
| G607 | STRUCT：sections tuple | `grounding.py::test_draft_subclass_and_wrong_container_types_rejected` |
| G608 | STRUCT：句子控制字元 | `grounding.py::test_bad_sentence_text_is_structural` |
| G609 | STRUCT：句子空白 | `grounding.py::test_bad_sentence_text_is_structural` |
| G610 | STRUCT：refs 重複 | `grounding.py::test_bad_refs_container_is_structural` |
| G611 | STRUCT：ref 空白 | `grounding.py::test_bad_refs_container_is_structural` |
| G612 | STRUCT：refs 為 tuple | `grounding.py::test_bad_refs_container_is_structural` |
| G613 | STRUCT：句子型別 | `grounding.py::test_draft_subclass_and_wrong_container_types_rejected` |
| G614 | STRUCT：段落型別 | `grounding.py::test_draft_subclass_and_wrong_container_types_rejected` |
| G615 | passed_gates 在結構失敗時為空 | `grounding.py::test_unparseable_input_is_validation_failure` |
| R01 | SummaryResult：狀態不得與可得性推導不符 | `grounding.py::test_summary_result_rejects_upgraded_state` |
| R02 | SummaryResult：mode 須為 AB-0 AiParticipation | `grounding.py::test_summary_result_mode_must_be_existing_ab0_value_and_five_sections` |
| R03 | SummaryResult：INVALID 不得帶段落 | `grounding.py::test_summary_result_invalid_cannot_carry_conclusions` |
| R04 | SummaryResult：INVALID 須指出無效段 | `grounding.py::test_summary_result_invalid_cannot_carry_conclusions` |
| R05 | SummaryResult：五段齊全且依序 | `grounding.py::test_summary_result_mode_must_be_existing_ab0_value_and_five_sections` |
| R06 | SummaryResult：state 型別 | `grounding.py::test_summary_result_mode_must_be_existing_ab0_value_and_five_sections` |
| R07 | SummaryResult：可得性涵蓋五段 | `grounding.py::test_summary_result_availability_must_cover_five_sections_in_order` |
| S01 | INVALID 時不輸出段落 | `summary.py::test_q4_order_is_never_repaired_by_the_summary` |
| S02 | 自檢：未通過即 raise | `summary.py::test_self_check_fails_loud_when_summary_would_violate_grounding` |
| S03 | 自檢：被丟棄的句子視為 bug | `summary.py::test_self_check_fails_loud_on_dropped_sentence` |
| S04 | 行動文字逐字 | `grounding.py::test_rule_summary_passes_all_gates` |
| S05 | 行動依 Digest 順序（不重排） | `summary.py::test_actions_are_verbatim_in_digest_order_and_one_to_three` |
| S06 | Risk Cap 卡面措辭 | `grounding.py::test_rule_summary_passes_all_gates` |
| S07 | 行動引用只含本段依據 | `summary.py::test_action_sentence_stale_evidence_is_disclosed_and_out_of_scope_evidence_not_cited` |
| S08 | stale 依據揭露 | `summary.py::test_action_sentence_stale_evidence_is_disclosed_and_out_of_scope_evidence_not_cited` |
| S09 | 缺值原因不猜 | `summary.py::test_stale_proxy_failed_invalid_are_marked_not_upgraded` |
| S10 | 未帶鍵持股揭露 | `grounding.py::test_rule_summary_passes_over_many_digests` |
| S11 | 策略來源揭露 | `summary.py::test_strategy_classified_holdings_show_source_and_unwired_judgement` |
| S12 | 無行動不得寫成持有 | `summary.py::test_actions_available_with_zero_items_says_rule_layer_produced_none` |
| S13 | mode=RULE_ONLY（有效路徑） | `summary.py::test_baseline_shape_state_and_mode` |
| S14 | INVALID 不保留任何段落 | `summary.py::test_q4_order_is_never_repaired_by_the_summary` |
| S15 | 市場事實 stale 標示 | `grounding.py::test_rule_summary_passes_over_many_digests` |
| S16 | proxy 標示 | `grounding.py::test_rule_summary_passes_over_many_digests` |
| S17 | INVALID 事實標示 | `summary.py::test_stale_proxy_failed_invalid_are_marked_not_upgraded` |
| S18 | 趨勢段使用定義狀態標示語 | `grounding.py::test_rule_summary_passes_all_gates` |
| S19 | 策略未設定標示語 | `grounding.py::test_rule_summary_passes_all_gates` |
| S20 | 已分類持股未接線揭露 | `grounding.py::test_rule_summary_passes_over_many_digests` |
| T01 | 洗白字眼含「中性」 | `grounding.py::test_g3_washing_terms_survive_whitespace_and_fullwidth_tricks` |
| T02 | 洗白字眼含「維持」 | `grounding.py::test_terms_cover_the_c_document_wording` |
| T03 | 英文洗白含 neutral | `grounding.py::test_g3_washing_terms_survive_whitespace_and_fullwidth_tricks` |
| T04 | 行動字眼含「減碼」 | `grounding.py::test_g4_new_action_terms_rejected_outside_quotes` |
| T05 | 方向字眼含「衰退」 | `grounding.py::test_g4_direction_terms_rejected` |
| T06 | 產業泛稱排除不得誤含半導體 | `grounding.py::test_g1_industry_name_rejected_because_digest_has_no_industry_allowlist` |
| T07 | 確定語氣含「確定」 | `grounding.py::test_g3_assertive_tone_forbidden_for_non_ok_refs_only` |
| T08 | 段落順序 | `grounding.py::test_rule_summary_passes_all_gates` |
| T09 | 數字樣式（小數） | `grounding.py::test_rule_summary_passes_all_gates` |
| T10 | 數字樣式（正負號） | `grounding.py::test_g2_non_literal_numbers_rejected` |
| T11 | 日期樣式 | `grounding.py::test_rule_summary_passes_all_gates` |
| T12 | PLACEHOLDER 沿用 AB-0 | `grounding.py::test_g3_placeholder_segment_rejected` |
| T13 | Risk Cap 卡面措辭為客戶核准字串 | `grounding.py::test_risk_cap_wording_is_the_customer_approved_string_verbatim` |
| V01 | 呼叫 AB-0 validate() | `validator.py::test_schema_version_drift_is_invalid` |
| V02 | 呼叫 AB-1 validate_rule_ids（allowlist／wrong location／版本） | `validator.py::test_rule_id_not_in_allowlist_fails_with_rule_gate` |
| V03 | 呼叫 AB-1 validate_action_order（Q4 序） | `validator.py::test_action_order_violation_fails_with_order_gate` |
| V04 | 前三者全過才跑自有檢查 | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V05 | 非 DecisionDigest → INVALID | `validator.py::test_non_digest_is_invalid_not_raise` |
| V10 | 控制／零寬字元檢查 | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V11 | has_forbidden_char 判斷 Cf | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V12 | 保留前綴檢查 | `validator.py::test_reserved_ref_prefix_fails` |
| V13 | fact／action id 碰撞 | `validator.py::test_fact_and_action_id_collision_fails` |
| V14 | strategy_source 文字檢查 | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V15 | 行動文字檢查 | `validator.py::test_control_or_zero_width_in_texts_fail` |
| V20 | 多依據合併：非全 AVAILABLE 不得 AVAILABLE（尾端 PARTIAL） | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V21 | 多依據合併：全 UNAVAILABLE | `validator.py::test_all_unavailable_is_unavailable_not_neutral` |
| V22 | 市場段納入定義狀態段（至多 PARTIAL） | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V23 | 策略段：有該策略 entry 至多 PARTIAL | `validator.py::test_strategy_section_availability_derivation` |
| V24 | 策略段：持股讀不到 → UNAVAILABLE | `validator.py::test_strategy_section_with_unreadable_holdings_stays_unavailable` |
| V25 | derive_state：全 AVAILABLE 才 VALID | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V26 | derive_state：全 UNAVAILABLE 才 UNAVAILABLE | `validator.py::test_valid_contract_digest_is_partial_never_valid` |
| V27 | assess 回傳 derive_state（非固定值） | `validator.py::test_all_unavailable_is_unavailable_not_neutral` |
| V28 | INVALID 時不給 section_availability | `validator.py::test_invalid_sections_mapping_and_order` |
| V29 | holdings 違規同時影響存股與資本利得 | `validator.py::test_invalid_sections_mapping_and_order` |
| V30 | 跨段違規標記為 * | `validator.py::test_schema_version_drift_is_invalid` |

## 9. 已知限制與未驗證項（誠實揭露）

- **單組撰寫、未經獨立 QA**；承重判斷（INVALID 不保留、逐字引用豁免、Risk Cap 保守顯示、VALID 不可達）請獨立覆核。
- 字眼清單（洗白／行動／方向／確定語氣／產業名）皆盡力而為；**中文數字、同義詞、非中英文語言擋不住**（結構性防線是引用封閉＋逐字引用＋數字字面一致，但那只對「有引用的句子」成立；若 AI 寫出完全不含上述任何字眼的新斷言，G1～G4 抓不到 —— 這是規則式驗證的本質限制，不是可以靠加字眼清單補完的事）。
- 本批**沒有 production caller、沒有 UI**；沙箱 Python 3.13，CI Python 3.11 未實跑；未做網路／AI／Sheet 相關的任何實測（本批本來就沒有）。
- `AB1-ACTION-TEXT-AI-WORDING`（行動文字可能含 "AI" 字樣）與本批無交互：行動文字走逐字引用豁免，不被檢查。
- G2 對 AI 偏嚴（`60.0`≠`60`）：fail closed 是刻意的；放寬須走 Gate。
