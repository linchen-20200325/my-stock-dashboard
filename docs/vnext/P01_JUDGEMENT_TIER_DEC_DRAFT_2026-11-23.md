# 判定等級（正式／無法判定）DEC 草案（無編號；未生效）

## 0. 狀態
- **DRAFT，不生效**。須客戶於 #1199 正式裁示後才成為 DEC；本檔**不是** `docs/DECISIONS.md` 條目，未編 DEC 號。
- **不授權**：程式、Enum、schema、UI 文字、新來源、workflow、caller、Gate 解除、Ready／merge。
- **參考（非 DEC）**：總管裁示 #1199 comment 7101496340、7102624975；A 決策包 7101878581、7102518086；Work 非作者 QA 7101082181。
- 標記：FACT＝已在 origin/main `913dd759` 實讀；PROPOSED＝擬定條文；HOLD＝維持不變；NOT VERIFIED＝未驗證。
- 原則：missing≠0；unknown≠safe；not evaluated≠safe（DEC-054 第 3 點，docs/DECISIONS.md:1588-1598）。

## 1. 已裁示方向（FACT，非 DEC）
D-a=A（詞表）、D-b=A（僅 FORMAL／UNDETERMINABLE）、D-c=A（先 docs）：#1199 comment 7101496340。O-1=A、O-2=有條件 A、O-3=A，並允許 docs-only Draft PR：comment 7102624975。

## 2. 擬定條文（PROPOSED）
**第 1 條 詞表**：「正式／研究參考／無法判定」僅為概念詞表，避開 L0/L1/L2；不批准任何 Enum、文案或實作。
**第 2 條 兩級**：首版正式判定軸僅 FORMAL（正式）與 UNDETERMINABLE（無法判定）。**研究參考不是判定級別**。FORMAL＝§3 該功能前提全數成立；**任一該功能的必要條件未滿足**（缺、過期逾限、為代理值、as_of 不明、持有為 None）→ 該功能為 UNDETERMINABLE，顯示既有「⬜ 無法判定」，不得為 0／中性／安全／預設。**只影響該功能**：不受影響的其他功能、以及已依既有 DEC 授權的事實顯示（§4）維持不變，不因某一功能的必要條件未滿足而一併降級或隱藏。
**第 3 條 推導**：等級由既有狀態推導，不是輸入、不入庫；不新增第六個資料態（DEC-124，:6254）、不新增公式／分數／信心數字。`UNDETERMINABLE` 已存在於 `shared/ui2_contract/models.py`：`models.py:42` 起（`JudgementState`；`UNDETERMINABLE` 成員在 :45）；UNDETERMINABLE≠NOT_EVALUATED（:3170 對映列，記錄 DEC-124 的取代語意）。
**第 4 條 AI**：AI 不得提升等級；AI 不可用≠SAFE／HOLD／中性（`docs/vnext/ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md:16` 第 8 點）。
**第 5 條 比較與日期**：What Changed 是獨立於 Digest 單期判定的功能；比較須有同來源、同口徑的當期＋前次有效快照，缺任一時只能標「不可比較」，⛔「今日無重大訊號變更」（Work QA 7101082181；READ_FIRST 第 4 點）；`fetched_at` 不得替代資料日（DEC-205，:10809 起）。
**第 6 條 文案**：本草案不授權任何字樣變更；新字樣另走文案 Gate 與線框先行。

## 3. 逐功能 FORMAL 前提（PROPOSED；**非單一總門檻**，各列只依自己的原 DEC；任一該功能的必要條件未滿足只影響該功能）
本表只列「正式判定」的前提；**已授權的事實顯示（含 TWII 日 K）不在本表，見 §4**；「是否已部署可交付」不在本表，見 §5(b)。
| 功能 | 原依據 | 必要條件（判定面） | 現況 |
|---|---|---|---|
| 市場位階 | DEC-074 B（:2173）、DEC-075 D-1(a)（:2198）、DEC-161（:8078） | 代理廣度不可計分（DEC-074 B）；受 breadth 影響而無法依既有正式規則可靠計算的元件 →「⬜ 未評估／資料不足」，位階一併未評估（DEC-075 D-1(a)），失效只影響實際依賴它的元件，不重設權重。「位階須有 as_of」＝**INFERENCE／待裁示**：DEC-161 只是 G-F1 唯讀契約授權，不是該條件的出處 | 否：`RegimeFact` 無 as_of（`src/services/ui2/real_canonical.py:160`） |
| Risk Cap | DEC-054 第 3、4 點（:1588）、`shared/risk_cap_policy.py:55-116`、`src/services/macro_state_locker.py:666-694` | **(i) Required Core 5 輸入**（`REQUIRED_CORE_INPUTS`：VIX、台灣 PMI 當月、台灣 PMI 前月、外資期貨淨空單、加權指數跌破 MA5）**各依自己的新鮮度**：新鮮度非 FRESH 或計分值為 None ⇒ 無法評估，本輪不產生新上限。**(ii) 有效輸出快照**（與 (i) 是不同層次，不得混為一談）：專用 `risk_cap_state.json`（`RISK_CAP_STATE_FILE`）；`required_core_ok` 為布林 `True`（`is True`，不收 1／"true"）；`risk_cap_ruleset_version` 等於現行規則版本 `risk_cap.v2`（`RISK_CAP_RULESET_VERSION`）；`market_regime` 非 None／「系統異常」；**快照期限 7 曆日**（`MACRO_VERDICT_MAX_AGE_DAYS`，由 `macro_state_is_expired` 判；這是快照期限，不是 Core 輸入的新鮮度）；`exposure_limit_pct` 為 0~100 的整數值（`_valid_new_cap`），上限值為 null 或缺 ⇒ 沒有上限，格式不合法 ⇒ 沒有上限＋錯誤。讀端只取自本檔，不退回 `macro_state.json`。**Optional 輸入**（`OPTIONAL_INPUTS`：M1B／M2、BIAS240、PCR）缺項 ⇒ 依原規則續算、不計分，但須揭露為未評估（`not_evaluated`）；M1B／M2 在 `risk_cap.v2` 為依定義停用，不算未評估。**判定**：無有效快照（缺檔、ruleset 不符、`required_core_ok` 非 True、逾 7 曆日、上限值不合法）→ 無法判定；Core 輸入缺項只影響「是否產生新快照」（本輪不寫檔、不產生新上限），讀端仍可沿用 7 曆日內的有效快照（出處：`docs/vnext/VNEXT_1_0_DECISION_GATES.md` §7.1 第 2 列〔:200；該文自標為研究結論，非裁示〕、`src/services/risk_cap_apply.py` `REASON_CORE_MISSING`、`macro_state_locker.py:666-694`） | 否（UI2 數值 Gate 前恆 ⬜ 無法判定）；兩層各自是否成立 NOT VERIFIED |
| TWII 日 K | （事實顯示，不是正式趨勢判定） | 不在本表：屬 §4 第 1~3 項已授權事實顯示，條件見 §4 第 1 項；正式趨勢維持「尚未定義」 | 見 §4 |
| 個股 | DEC-215（:10967）、DEC-213（:10932） | 母體＝可評分全集，排除列另行揭露 | 無接線；各前提逐項 NOT VERIFIED |
| 持股 | DEC-215 §一第 2 點、DEC-218 §一（:11085）、Holdings 契約 §A 註（:47-55，過渡期規則 :53）、§C-6（:119） | 範圍＝「👤 我的」選定的**單一本組合**（DEC-218 Q2=(a)）；**持有全集**（Q1=B）含個股**與 ETF**、觀察清單不計入，**與 DEC-215 可評分全集分開計數、各有各的分母**（不得把所有 held 直接叫可評分，分母不得由輸出截斷倒推）；IN-U（張數／均價空白的合法持有列）保留不得刪；總量未知＝UNKNOWN／None，不得為 0／中性／SAFE；**過期值可留在持有全集並標 STALE／資料日，但不因有過期數值就自動算已評估**；重複代號須揭露、不得默默去重。**過渡期**（Holdings 契約 §A 註，客戶 #1199 7071998333）：任一無效列 ⇒ **整段 `holdings_rows=None`**（不是 `[]`，也不是剔除後的部分列），只能說「無法判定」。**§C-6 的「獨立 expected 母體」只是契約候選（`is_complete=False` 直到有獨立 expected），屬 DEC-213 I3 的 G2 Gate（客戶獨立授權）——不是已解的 G2，不得讀成已具備獨立完整性分母** | 無接線；各前提逐項 NOT VERIFIED |
| Digest／OneBrain（單期） | ADR-OB-001（`docs/vnext/ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md:7-18`，本文僅讀第 2、4、8 點）、DEC-054 第 2、3 點、DEC-160 裁示 2（:8067） | **單期**正式前提：正式上游輸入（Canonical Data → Deterministic Rules／Risk Engine）成立；所用規則可追溯（來源／as_of）；缺值或 PIT／過期不合格者依 DEC-160 裁示 2 與 DEC-054 第 3 點降級——不當 fresh、不補 0／中性／SAFE，並揭露缺口。OneBrain 僅解釋，不改寫 Risk Cap、規則或公式（ADR-OB-001 第 4 點）。**不含**「前次快照」（那是 What Changed，見下列） | 各前提逐項 NOT VERIFIED |
| What Changed（比較；獨立於 Digest 單期判定） | READ_FIRST 第 4 點、Work QA 7101082181 | 須有**同來源、同口徑、時間有效、可回查**的前次有效快照＋當期快照，且指定訊號完整檢查後，才可顯示「今日無重大訊號變更」；否則一律顯示「不可比較」。不可比較不使 Digest 單期判定失效 | 當期＋前次有效快照是否可得 NOT VERIFIED（Work QA 7104683540 §5 之說：目前不可比較；本文未複驗） |
| ETF 動作 | DEC-054 第 2~4 點、DEC-222 §二第 1 點（:11222；該節屬 AI 總管內部決定，非客戶裁示） | 沿用既有、可追溯的原規則（`action_branch.v1` 七分支碼）；Risk Cap 等護欄不得繞過；資料不足走原有「資料不足」分支、不硬給方向 | 無接線；NOT VERIFIED |
| System Action | DEC-222 §二（:11214；客戶核准的是 M-A1） | 沿用既有規則（ETF 分支碼、個股 `swap_level` 四級、`RULE_ID_ALLOWLIST`）；`unjudged` 列為 undeterminable、不計入今日需處理；觀察清單不計入 | 各前提逐項 NOT VERIFIED；是否可交付見 §5(b) |

## 3A. 呈現層 Level 0～2 與正式判定軸（FORMAL／UNDETERMINABLE）對照（PROPOSED；docs-only 差額，不改規則、不新增狀態）
**來源（FACT；#1276 為 Draft，未合併）**：PR #1276 分支（Draft，未合併；DEC-224 尚未入庫；head 4f1ac1f1）：`UI2_ONEBRAIN_FULL_PRODUCT_SPEC_V1_0_2026-11-23.md:63-70`（Level 2＝所有原正式必要條件成立才照既有規則得正式結論；Level 1＝有可信可追溯價格／觀察事實但輔助條件不足，僅「研究參考」並揭露缺項，不得新增正式市場位階、正式第三狀態、動作或放寬 Risk Cap；Level 0＝核心證據不足／過期／不可用，禁止投資結論；均非信心分數／公式／擇時／買賣權限）、`…PRODUCT_GOAL_V1_0_APPROVED…:13`（既有正式軸 FORMAL／UNDETERMINABLE 不新增第三值）、`…PRESENTATION_CONTRACT_DELTA_2026-11-24.md:3,8,10`（DIFF／NOT A CONTRACT OVERRIDE）、DEC-224 第 2 點（核准的是產品目標，不是施工／合併／部署 Gate；#1275 Must-Fix 與 DEC-124／081／092 仍走原 Gate）。以上在 #1276 合併前**都不是現行有效文件**。
| 呈現層（#1276／DEC-224 用語） | 對照正式判定軸 | 限制 |
|---|---|---|
| Level 2 | FORMAL：§3 該功能的必要條件全部成立（只對該功能） | 照既有規則得結論，揭露資料日與來源 |
| Level 0 | UNDETERMINABLE：顯示既有「⬜ 無法判定」 | 無投資結論；不得為 0／中性／安全 |
| Level 1 | **沒有對應的正式判定值**（INFERENCE） | 僅呈現層「研究參考」：新鮮、合格、可追溯的觀察事實＋來源＋as_of＋揭露缺口。**不是**第三個正式結果；不新增 Enum／DataStatus／FieldState（DEC-124）；不產生位階／System Action／Risk Cap／信心。stale、PIT 不合格、未來日、歧義日的值**不得**成為 Level 1 內容（DEC-160／201／207；§4 第 9a、9b） |
**粒度（INFERENCE，請正式 DEC Gate 確認）**：#1276 的「所有原正式必要條件／核心證據」依 §2／§3 與 Work Must-Fix 4 讀作**逐功能**，不是全站單一門檻。
**用語**：本草案不使用 L0/L1/L2（與 CLAUDE.md §8.2 分層、S1-6 文案分級相撞）；「Level 0～2」是 #1276／DEC-224 的呈現用語，其字樣仍須文案 Gate。#1276 把 FORMAL／UNDETERMINABLE 當「既有」軸，**但本草案尚未生效**——兩者目前互相引用，須由正式 DEC 先定軸。
| DEC／守衛 | 觸及條款 | 判定 |
|---|---|---|
| DEC-081 Q3=A（:2709） | 趨勢卡只顯示「尚未定義」，不自挑均線／漲跌幅／外資／國際指數代趨勢；原始資料可放第 3 層 | 第 3 層原始資料**已有許可**；Level 1 研究參考放進趨勢卡＝**衝突，需新裁示** |
| DEC-092 Q2（:1088-1105；固定句 :1095） | 參考線須標「均線為參考，不等於正式台股趨勢判斷。」 | 帶固定句的參考線**已有許可**；其他形式的 Level 1 **需新呈現裁示** |
| DEC-124（:6254；本文僅讀 :6313-6365 關鍵段） | 五態、無第六態；「無法判定」≠「未評估」；「尚未提供」＝capability | Level 當**狀態值**＝**衝突**；僅作呈現分組、不入 FieldState＝不衝突，但**需文案 Gate** |
| DEC-160（:8067）、DEC-201／207 | stale 不當 fresh；未來日／歧義日拒用 | Level 1 不得引用上述值；**同向** |
| DEC-054（:1588）第 4 點 | 不得繞過 Risk Cap | **同向**（Level 1 不放寬 Risk Cap） |
| DEC-022（:1570） | 禁用語含「目標價」 | 研究參考文案**需審**（**需新呈現裁示**） |
| `tests/test_ui2_guards.py:823` `_FORBIDDEN_TERMS` | 含「訊號可信度」「信心度」 | 「可信研究參考」字面不在清單內，但近似信心語意；是否被其他守衛擋 NOT VERIFIED，措辭**需文案審** |
**與 #1276／READ_FIRST（FACT，模擬）**：`git merge-tree` 模擬 #1275（13fae4d4）與 #1276（4f1ac1f1）兩者合併無衝突、與順序無關；合併結果的 READ_FIRST 採 #1275 的新句，舊「L0/L1/L2 僅候選顯示分級」句不再出現。**NOT VERIFIED 一致性**：#1276 分支自己的 READ_FIRST 第 27 行仍是舊句；若 #1276 先單獨入主幹而 #1275 未合，主幹會暫時出現「核准橫幅＋舊 L0/L1/L2 句」。合併順序由總管定（建議 #1276 先、#1275 後，或同批處理；本文不改 #1276）。

## 4. 事實不升格清單（O-1=A；PROPOSED）
下列事實**不得**升格為正式趨勢／Regime／Risk Cap／System Action／交易訊號／隱含信心。**本清單不是全面禁顯資料，也不是任何新取數許可**；各項只在其原 DEC 範圍內成立。
| # | 事實項 | 許可依據與範圍 | 狀態 |
|---|---|---|---|
| 1 | TWII 日 K 序列（K 色以開收比） | DEC-156（:7955-7960；下列資料契約條件在其「施工前 Gate」:7962）。DEC-156 載明的資料契約條件：OHLC 邏輯成立、有限正值、日期升序且唯一、無未來日、無未完成棒、stale／failed 區分、卡片與圖同源 as_of、legacy 資料有疑義時誠實降級；資料不足 20 根不補 0、不補假棒。同源對帳的現行守衛：`src/services/ui2/real_canonical.py` `kbar_same_source_problem`（:502-515 一帶；比對 as_of／最新收盤／is_stale／age_days／upstream_state／來源，不一致不得假裝一致）。這些是顯示的前提，不是正式趨勢判定 | 照原 DEC 顯示；各條件是否逐項成立 NOT VERIFIED |
| 2 | TWII 資料日、來源、is_stale 揭露 | DEC-156「來源／唯讀」 | 照原 DEC 顯示 |
| 3 | TWII 最新收盤值 | DEC-081 Q3=A「原始客觀資料可放第 3 層」（:2709） | 第 3 層已許可；首屏 NOT VERIFIED |
| 4 | 既有指數／均線參考線，須帶固定句「均線為參考，不等於正式台股趨勢判斷。」 | DEC-092 Q2（:1250；句 :1095） | 照原 DEC 顯示 |
| 5 | 國際既有可追溯資料系列 | DEC-092 Q2 圖 B | 照原 DEC 顯示 |
| 6 | 與前收比較的日漲跌幅 | DEC-156 稱須另取合法前收與獨立語意；DEC-081 Q3=A 禁以漲跌幅代趨勢 | NOT PERMITTED／NOT VERIFIED |
| 7 | 外資或其他單一指標當趨勢 | DEC-081 Q3=A 明禁 | NOT PERMITTED |
| 8 | 三大法人／融資／板塊於 **UI2** 顯示（範圍僅 UI2；舊 UI 既有顯示不受本案影響） | DEC-162 僅唯讀盤點；DEC-163（:8094）僅文字線框草案；DEC-164 僅授權唯讀 L3 service 與單元測試、不接 UI | UI2 顯示 NOT PERMITTED／NOT VERIFIED |
| 9a | **stale** 的值 | DEC-160 裁示 2（:8067）：可在隔離的 Evidence／audit／coverage 保留 source／as_of 與拒用原因，**不得當 fresh** 進決策／Risk Cap／排序／摘要；DEC-214（:10948）：現行契約的降級顯示＝「⚠ 過期 N 天」＋資料日＋來源 | 僅限上列 DEC 已定的降級呈現；不得當 fresh、不得升格 |
| 9b | **未來日／歧義日／最新日重複**的值 | **拒用路徑**，不是降級顯示：DEC-201（:10777）未來資料日 ⇒ 不印出不可信日期（日 K meta 改顯示缺日期字樣）；DEC-207（:10832）最新日重複 ⇒ 卡片 fail-closed 為 ⬜ 無法判定、日 K 同樣拒畫 | 拒用：不顯示該值、不顯示不可信日期、不得升格；**與 9a 的 stale 降級顯示不是同一種許可** |

## 5. 正式輸出可用性（O-2=有條件 A；**PROPOSED 新增治理條件，非既有核准條文**）
區分兩件事：
- **(a) 上游規則與輸入證據已具正式判定條件**：即 §3 該功能前提成立。
- **(b) 經核准的 production caller／consumer 真正部署且可交付**。
(b) 缺失 ⇒ **不得對使用者宣稱「正式生產輸出可用」**（現況：System Action Aggregator〔DEC-222〕沒有任何 production caller；Decision Digest 的 `ALLOWED_CALLERS` 為空集合）；但**不得**反過來說 (a) 因無 consumer 而不成立。本條**不授權** Stage F 或任何新 caller；`ALLOWED_CALLERS = frozenset()`（`tests/test_decision_digest_invariants_guard.py:286`，:422 斷言）維持不變。

## 6. READ_FIRST 第 24 行修訂提案（O-3=A；與本草案同批、非作者 QA，不直接改主幹）
現行（`docs/vnext/READ_FIRST_UI2_ONEBRAIN_VERSION_AND_DEC_DRAFT_2026-11-23.md` 第 24 行整行）：
> 3. **L0/L1/L2 僅候選顯示分級**：L2 必要正式條件全部滿足；L1 部分輔助證據缺失時只顯示可信研究參考及缺口，不得形成簡化正式位階/動作；L0 核心證據不可用時無法判定。不是新演算法/風險分數的授權。

擬替換（單行）：
> 3. **正式判定首版僅 FORMAL／UNDETERMINABLE 兩級**（提案，未生效）：該功能必要條件全部成立才為 FORMAL；任一該功能的必要條件未滿足 → 該功能 UNDETERMINABLE（無法判定），只影響該功能，不影響其他功能與已授權的事實顯示；研究事實可依既有 DEC 展示，但不得升格為正式位階/動作/趨勢。不是新演算法/風險分數的授權。

理由：舊句 L1「可信研究參考」與 D-b=A 衝突，且 L0/L1/L2 與 CLAUDE.md §8.2、`docs/v2/spec/S1-6_COMPLIANCE_COPY_GUIDE.md` 用語相撞；新句另以「任一該功能的必要條件未滿足」取代「全部成立／核心證據不可用」的整體式寫法，並明載不影響其他功能與已授權事實顯示（Work QA 7104683540 §1 Must-Fix 4）。

## 7. HOLD 不變
DEC-081／092／124／160；DG-LIC／PIT／COV／SCOPE／I1144（DEC-205 已裁 PIT＝B＋X、LIC＝A，DEC-215 已定 COV 母體口徑，皆「已裁示但未接線」，非解除）；Stage F／正式 caller；v1.1（Catalyst Radar／Signal Log）；NAS #1237；Cloud、Secrets、正式 OneBrain Provider 與 production LLM caller；DEC-185／187 三支資料發布 workflow 維持停用；真實持股與 Auth／Sheet／Secrets；LINE 真推播；Digest v2（DEC-160）。**本草案仍為 DRAFT、未生效，仍待正式 DEC Gate**；#1276／DEC-224 只批准產品目標，不解除上列任何 HOLD。

## 8. 開放項／NOT VERIFIED
DG-LIC 現況；TWII 資料日與 Risk Cap／Real VM 狀態（Work QA 之說）；DEC-092／156／215／218 內文逐字、DEC-161 逐字；Risk Cap 行號；Cloud 實況；ADR-OB-001 僅讀第 2、8 點；Holdings 契約 :54／:80；舊 UI 是否已顯示三大法人／融資／板塊；§3 各列「現況」非逐項實測；§3 Risk Cap 兩層、§4 第 1 項 DEC-156 各條件是否逐項成立；What Changed 當期＋前次快照是否可得；DEC-218 第 5 點重複代號的計數單位（列 vs 代號）未裁示。§3A：#1276 CI；#1199 comment 7110182570／7109632982 原文未重讀（僅讀 #1276 分支所轉錄之 DEC-224 與規格）；DEC-124 內文僅讀 :6313-6365 關鍵段；DEC-081／092／022 僅讀所引行；Level 1 文案是否被其他守衛擋。本文未經新一輪非作者 QA。

## 9. 唯一下一步
非作者 QA（本文含 §3A＋READ_FIRST 第 24 行替換）→ 客戶於 #1199 正式 DEC 裁示（§3A 的 Level／軸對映與粒度也一併請裁示）。裁示前不動程式、文案、來源、workflow、caller 或 Gate。

**待客戶裁示的問題**：請客戶於 #1199 裁示是否採納本草案為正式 DEC（編號由總管依治理流程指派）：採納／修改後採納／不採納。
**A 線推薦**：採納——它只收斂判定語意、不授權任何實作、不解除任何 Gate、不改現行畫面。（此為推薦，非已核准；客戶裁示前本草案維持 DRAFT、不生效。）
