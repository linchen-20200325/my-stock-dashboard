# 【CANDIDATE／NOT ENABLED／NO CODE／NOT A PRODUCTION CALLER／非施工授權】OneBrain「完整 eligible evidence」驗收準則候選（Full Eligible Evidence Acceptance Criteria）

> 2026-11-20｜基準 main `5ea2f5fc`｜授權 #1199 comment `7040939424`（總管裁示，決策 1、2）｜來源研究 #1199 comment `7040656318` 與 `7037529004`。
> **本文不是**：Stage F／G 授權、schema／validator／簽章／Digest v2 的凍結、OneBrain 可用的證明、截斷問題的修復。**綠燈（含 #1238 的測試）不得被引用為放行依據。**
> **現況一句話**：OneBrain＝**NOT READY**；正式市場廣度＝**NOT EVALUATED**。
> 標記：**〔F〕**事實（附 `檔案路徑::符號` 或 issue comment id，撰寫當日對 main `5ea2f5fc` 實檔查證）｜**〔I〕**推論｜**〔NV〕**NOT VERIFIED。本文不寫行號（`CLAUDE.md` §8.2.A.0 規則 1）。單組作者撰寫，未經第二組複驗。

## 0. 這份文件是什麼／不是什麼

- **是**：把「OneBrain 日後若要宣稱『Evidence 來自完整 eligible 母集』，至少要滿足哪些不變量、哪些現在有保障、哪些根本沒有」整理成**可討論的驗收準則候選**（I1–I7），並把兩個容易被誤讀的事實寫清楚：(a) 對稱截斷／預過濾會讓現有 `is_complete` 誤報 `True`（§2）；(b) 現行資料發布流程不保存逐次擷取的版本歷史，不能支持 PIT 聲明（附錄 A）。
- **不是**：實作、測試、schema、Gate 的批准。I3／I5／I6／I7 涉及 schema／validator／簽章／L0，本文只列為**未核准 Gate**。
- **關於 #1238（務必讀）**：〔F〕`tests/test_onebrain_evidence_unknown_contract.py` 是 **tests-only 契約護欄**。它證明「單一 Top-N 回灌會把 `is_complete` 變 `True`」這個危險事實，並 pin 住 `assemble_digest` 簽章與 `ProviderRequest` 欄位。〔F〕它**沒有**阻止未來 builder 從 UI Top-N 反推完整 Evidence，也沒有偵測截斷的能力（該檔 docstring 自述「`assemble_digest` **無法偵測**輸入是否已被截斷」「本 tests-only PR **不阻止**任何實際 production caller 截斷」）。**本文不得被讀成「截斷已修復」。**

## 1. 術語（決策 1，正式採用）

**「雙側／對稱截斷」**：同一個完整 eligible 母集所衍生的 `station_rows` 與 `holdings_rows` **同時**因 Top-N 或預先篩選被**一致縮減**，使現有互相對帳的計數相等（`holdings_without_station_row`＝0、`station_rows_unmatched`＝0），卻誤報 `is_complete=True`。

明示的邊界（避免詞彙被誤用）：
- 〔F〕此詞**不是** repo 既有正式詞彙：撰寫當日在 `docs/` 全文搜尋「雙側」「對稱截斷」，兩者**皆無既有定義**（0 命中，本檔新增前）。
- **不是**「支持／反對」正反證兩側。正反證概念僅見未核准草案 `docs/vnext/ONEBRAIN_EVIDENCE_COVERAGE_SCHEMA_CANDIDATE_2026-11-06.md`（候選欄位 `contradicts_evidence_ids`）。本文的「側」指的是**兩條輸入通道**（站內列與持有列）。
- 〔F〕`shared/decision_digest.py::ActionRef.evidence_refs` 的 docstring 規定它指向「本 Digest 內 status ∈ {ok, stale} 的 fact」（行動的判斷依據）；〔F〕在 `shared/`、`src/` 全文搜尋 `contradict` 為 **0 命中**。〔I〕故現行輸入／Digest 沒有任何通道可表達「反證」，正反證雙側目前**無輸入通道**（此推論基於上述兩項事實，請審查者對碼複核）。

## 2. 反例表：什麼擋得住、什麼擋不住

**輸入**：〔F〕`tests/onebrain_anon_demo.py::_kwargs(10)`（10 筆合格、固定合成輸入；`_action` 依序循環 add／pause_add／cut／take_profit_force／take_profit_partial／add／pause_add，故 T7 add、T8 pause_add、T9 cut）；上限 〔F〕`shared/decision_digest.py::MAX_ACTIONS`＝3。欄位名以實檔為準：`actions_total_eligible`、`actions_omitted_count`、`holdings_without_station_row`、`station_rows_unmatched`、`excluded_invalid_rows`（注意：實檔欄位名為 `excluded_invalid_rows`）、`is_complete`（`shared/decision_digest_coverage.py::DigestCoverage`）。

| 情境 | `actions_total_eligible`／`actions_omitted_count` | `holdings_without_station_row`／`station_rows_unmatched` | `digest.holdings.entries` 筆數 | `is_complete` |
|---|---|---|---|---|
| 完整輸入（10 筆） | 10／7 | 0／0 | 10 | False |
| 只截 station 為 3 筆 | 3／0 | 7／0 | 10 | False |
| 只截 holdings 為 3 筆 | 3／0 | 0／7 | 3 | False |
| station 3／holdings 5（巢狀） | 3／0 | 2／0 | 5 | False |
| station 3／holdings 3（不相交） | 0／0（total＝0） | 3／3 | 3 | False |
| **兩通道同取 builder 實際顯示的 Top3（對稱截斷）** | 3／0 | 0／0 | 3 | **True（錯判）** |
| **各側 Top1（聯集 2 筆）** | 2／0 | 0／0 | 2 | **True（錯判）** |
| 各側 Top2（聯集 4 筆） | 4／1 | 0／0 | 4 | False（但原因見下） |
| 各側 Top3（聯集 6 筆） | 6／3 | 0／0 | 6 | False（但原因見下） |

註：
- 「各側」＝以輸入的 `_action` 分兩側：加碼側（add／pause_add：T0、T1、T5、T6、T7、T8）與減碼側（cut／take_profit_force／take_profit_partial：T2、T3、T4、T9）；「Top-k」＝該側依輸入順序取前 k 列（**原型的取法，不是 production 排序**）。各側 Top1 時，減碼側與加碼側**各自單獨**組裝也各是 `True`，合起來（聯集 2 筆）才是被截斷的母集——即任何單側檢查都看不出問題。
- 各側 Top2／Top3 的 `is_complete=False` **不是**偵測到截斷：`total` 低報（真值 10，卻報 4、6），`False` 只因展示上限 `MAX_ACTIONS`＝3 造成 `omitted>0`。
- 對稱截斷時，〔F〕`digest.actions` 與完整輸入**逐項相同**（保留集＝builder 實際顯示的三筆時），僅 `digest.holdings` 筆數不同（3 對 10）。〔F〕#1238 的 `test_KNOWN_UNFIXED_RISK_top_n_feedback_makes_truncated_input_look_complete` 斷言 `fed.digest.actions == full.digest.actions` 與 `is_complete` 不同，**但沒有斷言 holdings 筆數差異**——這是本文補的觀察，不是 #1238 的內容。若保留集取輸入的前三列而非 builder 實際顯示的三筆，`digest.actions` 並不相同（原型實測），故「actions 相同」僅在「保留集＝顯示 Top3」時成立。
- 〔I〕由表推得（僅測 eligible 數 2、3、4、6）：保留集的 eligible 數 ≤ `MAX_ACTIONS` 時對稱截斷被判完整；更大時 `is_complete=False`，但屬展示上限造成，`total` 仍低報。

**預先濾掉 invalid 列**（需 eligible ≤ `MAX_ACTIONS`，否則 `omitted>0` 使 `is_complete` 仍為 False）：4 列輸入（3 筆 eligible＋1 筆帶非空 `_invalid_lights`）→ `excluded_invalid_rows`＝1、`is_complete`＝False；呼叫端把該列從 station 與 holdings 兩通道都預先濾掉 → `excluded_invalid_rows`＝0、`is_complete`＝**True（錯判）**。

**結論與限制（必須同時讀）**：
1. **僅單側截斷時，現有雙向對帳（`holdings_without_station_row`／`station_rows_unmatched`）能擋**；不可概稱「所有截斷都擋不住」。
2. 擋不住的是：**對稱截斷**與**預過濾**（含預先濾掉 invalid 列）。兩者共同點：被截掉的列從所有通道**同時**消失，coverage 沒有任何「應有多少」的獨立參照（見 I3）。
3. **證據強度聲明**：〔F〕本表來自 C 線以空命名空間（避開 streamlit import）載入 `src/services` 的**本機原型**；總管線獨立重跑一致；本文撰寫者另以同法在 repo 外暫存目錄重跑一次，數值一致（單組、非 QA）。**不是** native pytest、**不是** production integration QA。原型腳本**未入庫**（本文 NO CODE）；需重現者依 `tests/onebrain_anon_demo.py::_kwargs` 的固定合成輸入形狀自建。

## 3. 不變量 I1–I7（驗收準則候選）

**分級定義**：**G1**＝文件／測試等級候選（不動 runtime、契約、schema；屬總管內部自決層，**仍需另行指派才可寫 tests**）。**G2**＝涉及 schema／validator／簽章／Digest v2／L0 freshness／新 caller／持股，**須使用者獨立授權，本文不決定**。「日後驗收形態」欄皆為**候選描述，尚非測試**。

| ID | 不變量陳述 | 為何必要 | 現有保障 | 分級 | 日後驗收形態（候選，尚非測試） |
|---|---|---|---|---|---|
| **I1** 完整母集來源 | Evidence 輸入必須來自**上游完整 eligible 清單**，不得由 Digest、規則摘要或 UI Top-N 反推（含 `src/ui/views/page_find.py::DEFAULT_TOP_N`＝50〔UI 請求筆數預設，選項 20／50／100〕） | 反推會讓 §2 的對稱截斷成為常態；客戶原文已禁（見右欄） | 〔F〕客戶原文：One AI Brain 不得「從 UI Top-N 認為只有 Top-N 資料存在」（`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` §2，引 DEC-109 十七）；〔F〕`assemble_digest` 簽章無 `top_n` 類參數，且被 #1238 的 `test_assembler_has_no_input_channel_declaring_truncation` pin 住。**執行期無強制**（無 production caller 亦無偵測） | **G1** | 未來 evidence builder 的測試應能證明其輸入資料流不經 Digest／摘要／UI 排序結果（資料流斷言或型別層限制，形態未定） |
| **I2** 兩通道各自由母集導出 | `station_rows` 與 `holdings_rows` 各自由同一母集獨立導出，**不得互相過濾** | 互相過濾使對帳計數天然相等（§2 對稱截斷） | **部分**：單側截斷會被對帳計數擋；對稱不會 | **G1** | 對同一母集隨機抽子集，兩通道若被一致縮減，builder 層（而非 assembler）須能辨識或拒絕 |
| **I3** 獨立母集計數 | producer 在**任何篩選之前**記下 `expected_*`（母集應有筆數），並與 coverage 實得值比對 | 唯一能偵測對稱截斷與預過濾的結構：需要一個**不由被截斷的輸入推出**的參照數 | **無**：〔F〕`DigestCoverage` 無 expected 欄；〔F〕Digest v2 計畫 A6 只有概念 `{evaluated, expected}`（`DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` §6，未實作）；DEC-160 裁示 3 僅記為方向 | **G2**：未核准 Gate，**不得寫成已批准契約** | 若日後授權：`expected≠evaluated` 時 `is_complete` 不得為 True（欄位位置、命名、版本屬 schema Gate） |
| **I4** 禁止預過濾 | 不得預先剔除 invalid／non-held／unkeyed 列；一律交 builder 分類計數 | 預過濾使 `excluded_invalid_rows` 歸零（§2 末段） | **部分**：〔F〕builder 對**收到**的每一列分類計數（`DigestCoverage` docstring 鐵則 1）；對**沒收到**的列無能為力 | **G1** | 對含 invalid 列的母集，經 builder 組裝後 `excluded_invalid_rows` 須等於母集中的 invalid 數 |
| **I5** `is_complete` 只能證偽、不能證明 | `is_complete=True` 只代表「已收到的列沒有可見遺漏」；**不得**被當作「母集完整」的證明或對 Provider／使用者的完整性保證 | 見 §2：`True` 可由截斷輸入產生 | 〔F〕`src/services/decision_digest_assembly.py` 模組 docstring「已知限制」第 1 點與 `AssembledDigest` docstring 自述「不防惡意偽造」；〔F〕`DigestCoverage` docstring 自述 `is_complete` 只回答「有沒有東西沒被讀進來」 | **G2**（若要讓 Provider 看見完整性，須動 `ProviderRequest`〔F〕現恰為 `{digest, task}`，#1238 已 pin）；僅列未核准 Gate | 若日後授權：Provider 端是否收得到完整性資訊屬契約變更；在那之前，文件與 UI 不得用 `is_complete` 宣稱「完整」 |
| **I6** 列層級 as_of／代表 stamp | 每列（或每段）的資料日與代表 stamp 如何決定，目前**未定** | 整段共用一個 stamp，無法表達「母集中最舊的一列」 | 〔F〕`src/services/decision_digest_assembly.py::EvidenceInput` 只有整段一個 `stamp`（外加 `freshness`、`upstream_state`）；須重用 `shared/staleness`（〔F〕檔案存在）不另立常數 | **未決（G2 邊界）：本文不定義** | 新 L0 freshness key 需獨立授權；本文不提供取法 |
| **I7** 正反證雙側 | 反證（contradicting evidence）若要進入 OneBrain，需有獨立欄位且缺資料不得當反證為 0 | 只有支持方的輸入會系統性偏向確認 | 〔F〕無 `contradict*` 識別字（§1）；〔F〕未核准草案列有 `contradicts_evidence_ids` | **G2**：涉及 schema，僅列未核准 Gate | 無（草案未核准，不提供驗收形態） |

補充觀察（〔F〕+〔I〕，與 I1/I3 相關）：〔F〕`src/services/fundamental_screener_service.py::get_ranked_picks` 自身帶有 `top_n` 請求參數（函式預設 300），而 Digest 計畫 A3 寫「L3 請求參數＝既有預設（`DEFAULT_TOP_N=50`），與 UI Top-N 無關」（`DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` §6）。〔I〕因此對「選股候選」而言，**「完整 eligible 母集」的口徑（排名前 N，還是通過篩選的全集）本身尚未定義**——這屬於 `DG-COV`（最低 coverage，含母體口徑；DEC-166／DEC-167 登記為「仍待客戶裁示」）的範圍，本文**不決定**。〔NV〕本文只查證了站內列（station rows）通道的現行 coverage 欄位，未查證選股候選段是否有等價欄位。

## 4. 授權與不得越界清單

本文與其伴隨的 DEC／BACKLOG 補登**僅**授權三個 docs 檔案的新增或追加（見 DEC-213）。以下**全部不在授權內，本文與後續任何引用本文的工作均不得執行**：

- Stage F／Stage G；G-F2（私人持股）及一切讀取私人持股、帳戶、OAuth、Sheet、Secrets 的工作；
- Digest v2 / OB-1-D3 的任何實作、新欄位、版本升級；
- L0 新增 freshness key／新常數檔；
- 真 Provider、W8、Risk Cap；
- `ALLOWED_CALLERS`、`OFFLINE_SHADOW_MODULES`（及 `OFFLINE_SHADOW_CALLERS`）的任何增刪；c3 分層守衛的 `_WHITELIST`／`_KNOWN_VIOLATIONS` 的任何增刪；
- 新增任何 production caller；
- 定時擷取、版本歷史收集、發送任何官方詢問（官方詢問草稿 v2 維持 NO SEND／HOLD）。

**修改 #1238 已 pin 的斷言**：依該檔 docstring，斷言 1、2 屬「目前契約快照」、斷言 3 若 assembler 日後被修好「會轉紅 —— 屆時須同步更新」；該檔明示「本檔不得被引用來阻止合理演進，只要求『演進必須是被批准的、並顯式改測試』，而不是被悄悄洗掉」。故：**任何改動 `assemble_digest` 簽章、`ProviderRequest` 欄位或截斷反例行為的工作，須先有已批准的契約變更，並在同一變更內顯式改寫該測試**；不得為了讓新設計通過而悄悄放寬這些斷言。

## 5. 與既有項的關係（避免重複立案）

| 既有項 | 關係 |
|---|---|
| DEC-212（#1238 的登記） | 本文是其後續的**驗收準則候選**；不取代、不修改 DEC-212。DEC-212 已寫明「`assemble_digest` 無法偵測截斷」「不修復 Top-N」，本文補上對稱截斷／預過濾反例 |
| `OB-ASSEMBLER-FULL-INPUT-INVARIANT`（BACKLOG，OPEN／待 Gate） | **沿用同一 ID，不另立**。本文是它的驗收準則候選細化（I1–I7 分級）；狀態不變 |
| `P1R-DIGEST-HEADLESS-ASSEMBLY`（BACKLOG） | I1／I2／I4 日後隨它的設計一併考量；本文不推進它 |
| OB-1-D3／Digest v2 | I3／I5／I7 的 schema 面向歸此 Gate；本文不實作 |
| G-F1／G-F2（BACKLOG 客戶 Gate） | I1 的「完整母集」能否取得，取決於是否存在合法、PIT 合格、headless 的來源（DEC-161 方案 A 的缺口驗證）；私人持股（G-F2）預設 NO ACCESS，本文不碰 |
| `docs/vnext/ONEBRAIN_OB2_PROPERTY_SPEC_CANDIDATE_2026-11-19.md`（#1230） | 格式先例（CANDIDATE／NO CODE／〔F〕〔I〕〔NV〕）；兩者範圍不同（OB-2 管指紋／cache／trace／預算，本文管輸入完整性） |

## 6. 風險與「這份文件不能解決什麼」

- **不阻止截斷**。文件、反例表、候選不變量都不會讓任何 caller 無法傳入被截斷的輸入。
- `assemble_digest` **仍然偵測不到**輸入已被截斷（§2；I3 才是結構性解法，但屬 G2）。
- **不使 OneBrain 可用**，也不使正式市場廣度可評估；**不放行 Stage F**。
- Stage F 未開，**短期零使用者價值**（沒有 production caller，使用者看不到任何 runtime OneBrain 輸出）。
- **規格膨脹風險（Scope Inflation）**：I1–I7 與附錄 A 可能被誤讀為「已批准的待辦清單」。它們是候選；任何一項要變成工作，都須另行指派（G1）或另行授權（G2）。
- 〔I〕§2 的結論（單側擋得住、對稱擋不住）只涵蓋表中測過的形狀；其他輸入形狀（含非行動碼 premium／cruise 列、重複 ticker、無鍵持股）本文**未測**，〔NV〕不得推廣。

## 7. NOT VERIFIED 清單

- 反例表為**本機原型**結果，非 native pytest、非 production integration QA；原型未入庫。
- 兩組非作者 QA、PR exact-head 五項原生 CI、0 unresolved threads、merge＋main push CI：**均未完成**；本文單組撰寫，在完成前不得宣稱 QA 通過。
- 外部提供數值 **18409**、**11369** 與「OGDL v1 指定資源許可已核證」之說法：〔F〕僅存在於 #1199 留言，**尚未入 repo**（撰寫當日在 `docs/`、`shared/`、`src/`、`scripts/` 搜尋這兩個數值為 0 命中）；本文**不引用其內容作為結論**，標「外部提供」。DG-LIC 仍以 DEC-205 的 HOLD 為準。
- 官方詢問草稿 v2：NO SEND／HOLD。
- 歷史 PIT、`available_at`、來源修訂 vintage、母體映射：皆 NV（附錄 A）。
- 本文未查證：選股候選段是否有等價 coverage 欄位（§3 補充觀察）；各資料更新腳本自身對既有檔的合併語意（附錄 A 只查證了 `scripts/publish_data_pr.py` 的發布路徑）。

---

## 附錄 A：historical PIT（未驗證）vs forward-only 的比較（僅比較，不定義規格）

**本附錄不定義任何收集政策、主鍵、儲存格式、新欄位或排程。** 它回答的是：現況下，兩種取得資料的方式各**能聲明什麼、不能聲明什麼**。

### A.1 比較表

| 概念 | 歷史回補（historical backfill；PIT 未驗證） | forward-only（自開始保存起逐次擷取） |
|---|---|---|
| `data_date`（資料日／觀測日） | 來源序列通常自帶；但**不蘊含「該日當時已可得」** | 同左 |
| 首次可得 `available_at` | **無法重建**：來源發布時刻不存在於資料層（DEC-205：`fetched_at` 絕不作官方公布日） | repo **未定義**此欄（A.2 (a)）；至多可得「不晚於」的上界，且需滿足 A.2 (a) 的條件，**現行流程尚未保存** |
| `fetched_at` | 等於回補執行時刻，通常**遠晚於**當時；不可回填為 `available_at` | 可作上界（條件見 A.2 (a)）；不是發布時刻 |
| 來源修訂 vintage | 取得的是**回補當下的現行修訂版**，看不出當時值 | 只有逐次保存才可追溯；現行發布流程**不保存**（A.2 (b)） |
| 交易日 vs 休市 | 缺日可能是休市、缺檔或來源遺漏；〔F〕repo 無第三方交易日曆（`CLAUDE.md` §4.5） | 同左；另需區分「這次沒抓到」與「來源本無此日」 |
| coverage 缺列 | 缺列原因無從回溯 | 缺列可能是擷取失敗或無新資料，須顯式區分（A.2 (c)） |
| **可聲明什麼** | 只能聲明「在現行來源版本下，資料日 D 的值為 X（擷取於回補時刻）」；**不得**聲明「T 時已可得」或做歷史序列／回測／事後當時已知判斷（DEC-205 的 DG-PIT＝B＋X 射程） | 只能聲明「自開始保存之日起，首次成功擷取時刻不晚於…」且僅在 A.2 (a) 條件成立時；**不得追溯到開始保存之前** |

### A.2 現況事實與限制

**(a) `available_at`／`published_at` 在 repo 未定義。**〔F〕DEC-070 明記「未定 `published_at`／`available_at` 欄位契約」；〔F〕`docs/PROJECT_STATE.md` §10（已知資料時點、freshness、PIT 問題）與 §20（GitHub 無定義來源）寫「`published_at`／`available_at` 欄位契約：GitHub 無定義來源；不得推測」；〔F〕DEC-205：`fetched_at` 僅內部稽核證據、絕不作官方公布日。任何以 `fetched_at` 作的上界**不是發布時刻**，只是「不晚於」的上界，且僅在「該格**首次**成功擷取、UTC 且 tz-aware、非補抓／重跑／覆蓋後」才成立；cron 延遲只會讓上界變寬，不會變準。

**(b) 現行 `scripts/publish_data_pr.py::union_parquet_by_date` 不保存逐次擷取的版本歷史（無 vintage log），不能宣稱已滿足 PIT。**〔F〕對碼描述如下（僅描述被呼叫時的行為；〔F〕它**只在 `auto/data-<job>` 分支已存在於遠端時**才被呼叫，分支不存在時直接提交腳本輸出）：
- 兩邊皆有的 key：比對時**忽略揮發欄**（`VOLATILE_ROW_COLS`＝`VOLATILE_PARQUET_COLS`〔`fetched_at`、`captured_at`〕加 `updated_at`），其餘欄逐欄比對；合併時**舊列優先（含揮發欄）**。
- 非帳本模式：舊值為空、新值有值 → **採新值**（僅在有傳入 log 時記一行「舊 null→新有值，採新值 N 格」）。因此該格被補上後，〔F〕所在列的 `fetched_at` 在舊列該欄非空時仍是**舊列的值**，不是該格的取得時刻；列上也**看不出該格原為空**。
- 舊值非空而新值為空（或缺欄），或兩邊皆非空但不同 → `PublishError`（中止，不寫入、不 commit），**不記錄修訂前後兩版**。
- 帳本模式（`LEDGER_PATHS`，目前 `data_cache/macro_forward_test/signals.parquet`）：同 date 已存在則保留既有列，**任何差異（含舊空→新有值）皆 fail-closed**；保留的是第一列，**不保存修訂**。
- 另：〔F〕`parquet_substantive_change` 忽略揮發欄，故「僅 `fetched_at` 不同」不構成實質變更、不會觸發發布。
- **結論**：不能靠「舊 null→新值」的行為證明該格「首次已見」；不能以 `fetched_at` 回填歷史 `available_at`；現行流程不構成 PIT 聲明的證據。〔NV〕各資料更新腳本自身（上游）對既有檔的寫入語意未在本附錄查證。

**(c) 若日後（需 DG-PIT 裁示）要對「首次值」作 PIT 聲明，必須先能回答的問題**（以問句表達；**不是**規格、主鍵設計、收集政策、payload 儲存決策或新 L0 freshness key）：
1. 首次成功擷取的時刻，如何與**該格**（而非整列、整檔）綁定？
2. 後續來源修訂，如何不覆蓋首次值、且可追溯？
3. 擷取失敗（`FETCH_FAILED`）、無新資料（`NO_NEW_DATA`）、來源無該列（可能休市或缺檔）三者，如何區分而**不折算為 0／安全／正常**？〔F〕`shared/fetch_outcome.py::FetchOutcome` 已有三態詞彙 `NO_NEW_DATA`／`FETCH_FAILED`／`UNDETERMINED`；「來源無該列」是否另需第四種表達，本文**不決定**。
4. 來源授權對**保存原始內容**的限制為何？（OGDL 適用範圍 NV；DG-LIC 維持 HOLD。）

**(d) 缺值治理（不變）**：missing ≠ 0 ≠ neutral ≠ normal ≠ HOLD；proxy ≠ real。任何比較表中的「無法聲明」都以「未知」呈現，不以任何預設值填補（`CLAUDE.md` §1）。
