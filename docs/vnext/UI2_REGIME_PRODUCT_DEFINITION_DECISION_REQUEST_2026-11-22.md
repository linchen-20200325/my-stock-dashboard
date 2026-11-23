# New UI2「市場位階（Regime）」產品定義：客戶決策請示稿（2026-11-22）

> **文件性質：REQUEST FOR DECISION（請示稿）／DOCS-ONLY／不是授權。**
> - **日期**：2026-11-22。**基準**：origin/main `e2068a68`（原撰寫基準）；**2026-11-23 差額修訂**：已併入 main `e6d21a7f`（worktree `ace11a7f`），並以 `git diff e2068a68 e6d21a7f -- shared/ui2_contract/text.py src/services/ui2/real_canonical.py` 核對，凡與 Real 橫幅、位階未載入／無法判定畫面有關的敘述均已改依現行原始碼（派工訊息稱該變更為 #1267，PR 編號作者未另行核對）。
> - **作者**：單組作者（AI 執行組）。**未經非作者 QA，不得升格為決策依據或已驗證事實**；本文所有「推薦」皆為 RECOMMENDATION，不是裁示。
> - **本文不做的事**：不改任何程式、測試、契約、BACKLOG、DECISIONS；不提案實作任何新文案、計數口徑、口徑鎖定測試；不放行任何 Gate。客戶若選了需要後續工作的選項，後續須另案、另走各自的 Gate（本文第 3 節逐項列出）。
> - **標籤**：**FACT**＝作者本次讀檔／grep 直接確認（附出處檔名＋章節或符號，不寫行號）；**INFERENCE**＝由事實推得、未實測；**NOT VERIFIED**＝未驗證，不得當前提。
> - **派工來源**：總管 #1199 comment 7079173656 第三優先（作者環境無網路，**該留言原文本次未讀**；三項待決策依派工訊息轉述，見第 7 節）。

---

## 1. 已決事項（不重問）

以下事項客戶／總管已有裁示，本文**不再詢問**。

### 1.1 DEC-202 的 O2（位階無資料日 ＝ 歸「資料未備」，非缺陷，維持現狀）

- **出處**：`docs/DECISIONS.md` `DEC-202`（New UI2 產品收斂；#1199 comment 6995747146 授權；2026-11-19）；`docs/BACKLOG.md` 章節「2026-11-19 UI2-PRODUCT-CLOSURE 結論」之 **O2** 條。
- **BACKLOG 原文**：「**O2｜regime 有值但無可驗證 as_of 時歸「資料未備」**：已重現。**判定：非缺陷，符合 DEC-177 口徑；維持現狀。** 「多頭」等顯示不構成已確認資料日期。使用者影響：低。」
- **DEC-202 原文（決定段）**：「O1／O2 已重現，判定非缺陷＝符合 DEC-177 口徑，維持現狀，僅以文件揭露（設計文件 §7 補註）。」
- **DEC-202 的限制（本文遵守）**：「**不新增契約**：未改程式、測試、JSON、Schema、UI 文案、統計口徑；……候選的新字句／改口徑／口徑鎖定測試均**未授權**。」BACKLOG 同章亦寫「**候選但未授權（不得自行施工）**：新增揭露字句、更改計數口徑、口徑鎖定測試。」
- **文件揭露落點**：`docs/vnext/NEWUI2_DATA_FRESHNESS_FIRST_SCREEN_DESIGN_2026-11-18.md` §7「口徑補註」(b)。
- **O2 的涵蓋範圍（務必分清）**：O2 只涵蓋「位階**有值**但無可驗證 as_of」的情形。**位階「沒有值」而長期顯示「⬜ 尚未載入」**不在 O2 範圍內，其使用者影響是**本次首次請示，尚無既有判定、也無先例**（見決策 1）。
- **本文如何處理**：O2 的**現狀判定（有值無日期）不重問**。本文只問 O2 判定**之後**的三件事（長期缺值容忍度、將來 as_of 規則、Cloud state 取得架構）；凡涉及「新增揭露字句／更改計數口徑／口徑鎖定測試」者，只列為「客戶若同意才進入的後續」，**不提案實作**。

### 1.2 「Q5」：派工訊息未寫明是哪一個 Q5 —— 指涉 NOT VERIFIED，以下如實列出作者找到的候選

作者搜尋範圍：`docs/DECISIONS.md` 全部 `Q5` 命中、`docs/BACKLOG.md` 全部 `Q5` 命中、`docs/vnext/NEWUI2_DATA_FRESHNESS_*` 文件、`src/services/ui2/*.py` 註解與測試中的 `Q5`。與「位階」直接相關者有兩個，**其餘同名者與本題無關**（DEC-092 Q5 產業趨勢、DEC-117 Q5 市場頁順序、DEC-173 Q5 `REORG3C-Q5-GATE`、DEC-083 Q5 登出清三件）。

**候選一（最可能；與 O2 同一脈絡）：DEC-177 資料新鮮度總覽「實作裁示單」Q5＝規格缺口（位階「無法判定」、位階無資料日）**
- **出處**：`docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md` §「Q5　規格缺口：兩種情況不在線框的『五態』之內」。
- **內容**：(a) 市場位階有時是「無法判定」（輸入不足），屬判定結果、不屬五態，DEC-124 明定不得併入「尚未評估」；(b) 位階「已載入」卻**沒有資料日**，與「正常＝資料日在規則內」矛盾。**總管推薦 A**：(a) 計數行外另加一句「另有 n 項判定結果為無法判定，不計入上列」；(b) 位階無資料日時顯示既有字樣 `⬜ 資料日未提供`，**計入「資料未備」**，不寫「正常」。
- **目前 repo 內的引用方式**（FACT）：`src/services/ui2/real_canonical.py::item_state_of_spec` 的 docstring 寫「DEC-177 Q4=B／Q5=A」；`src/services/ui2/data_page.py` 註解「項目狀態（Q5=A；互斥）」；`docs/BACKLOG.md` 的 `UI2-DATA-ITEMS-REGIME-LOADED-WORDING` 列寫「`item_state_of_spec`（DEC-177 Q5）之 `S_MISSING` 歸類」；`tests/test_ui2_data_freshness_overview.py` 有「六種輸入情境（Q5＋#1206）」。
- **客戶是否明示答過 Q5：repo 內查無逐題答覆原文（NOT VERIFIED）**。已讀到的相關紀錄：`DEC-179`（2026-11-13）第 6 項為「🗂 資料新鮮度總覽 Q1～Q7 暫不裁示」，其對照欄註記「DEC-177 裁示單 Q1～Q7 一題都未回答」；`DEC-190`（2026-11-18）只記錄客戶核准「方案 C、Q1=A、D-5」，並指「依 GPT 最終設計（#1199 comment 6964559744）」；該 GPT 定稿留言本次未讀（無網路）。**因此「Q5=A 已由客戶逐題明示裁定」不得當成已驗證事實**；可確認的是：**Q5 的總管推薦 A 已隨首屏方案 C 出貨，成為現行行為**，且 `DEC-190` 延後項明寫「位階契約無 `as_of`，若日後新增，載入→『資料未備』歸類須重審」。
- **本文如何處理**：不重問「位階無資料日是否計入資料未備」。決策 2 若選到「位階將來有資料日」的選項，依 `DEC-190` 該歸類須重審，**重審本身屬後續另案**，本文不預設結果。

**候選二：DEC-062 的 VN1-Q5＝A（客戶 2026-10-18 明示）**
- **出處**：`docs/DECISIONS.md` `DEC-062`；`docs/BACKLOG.md` DR-2026-10-18-3 列。
- **客戶原文**：「Q5：A，並確認代理值不計分、停用項明示停用、無資料來源不得宣稱通過。」
- **與位階的關係**（FACT）：現行 `shared/signal_thresholds.py::BREADTH_PROXY_SCORING_ENABLED=False`（DEC-074 B，客戶 2026-10-23）即此原則的落實之一；位階缺正式市場廣度來源時恆未載入／未評估。本文決策 3 的所有選項**不得**以翻旗標或代理值計分繞過它。

> **派工訊息若指的是其他 Q5，請總管更正；本文不猜。**

### 1.3 其他不重問的既有裁示（與本題直接相關者）

| 已決事項 | 出處 | 對本文的限制 |
|---|---|---|
| DG-PIT＝B＋X、DG-LIC＝A，**且不授權正式資料發布或 UI2 接線**（客戶原話：「不授權正式資料發布或 UI2 接線」） | `DEC-205`（#1199 comment 7007425153） | 將來任何 as_of 規則只能「顯示最新值的資料日」；`fetched_at` 僅內部稽核，**絕不**當官方公布日；DG-LIC 權利 Gate 仍 HOLD |
| 位階契約無 `as_of`，**⛔ 以 `cl_ts` 頂替**；擴契約＝改既有 service，須客戶 Gate（SG-10） | `docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` §6（SG-10）、§5 | 決策 2、3 任何帶日期的選項，皆須另案走 SG-10 |
| DEC-161 已裁 G-F1「方案 A」（既有 canonical 市場資料 headless 唯讀契約＋缺口驗證） | `DEC-161`；`docs/vnext/STAGE_F_GF1_HEADLESS_MARKET_CONTRACT_2026-11-11.md` | 不重問方案 A；G-F1「方向」題仍 `CUSTOMER_DIRECTION_GATE_PENDING`（BACKLOG 2026-11-20 `G-F1` 列），與本文決策 3 高度重疊，見 3.3 |
| DEC-137 viewport 存證、UI2 零 JS、G2F 守衛 | `DEC-137`、`DEC-146`、`tests/test_ui2_guards.py`（G2F 段） | 任何動 `src/ui2/**` 的後續需重生存證 |

---

## 2. 現況事實（FACT）

### 2.1 位階的資料路徑（唯讀）

- UI2 Real feed 對位階只做一次呼叫：`allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`，且**不收** Risk Cap 欄位。出處：`src/services/ui2/real_feed.py` 檔頭 docstring；`src/services/ui2/real_canonical.py::RegimeFact`（欄位僅 `regime／light／source／is_loaded／has_file_error`，**無 as_of**；`tests/test_ui2_real_feed.py::test_regime_fact_never_carries_risk_cap_fields` 釘住欄位集合）。
- `get_macro_regime` 的輸入是 **session 的 `warroom_summary`** ＋本地檔 `macro_state.json`／`risk_cap_state.json`。出處：`src/services/allocation_service.py::get_macro_regime`；`docs/vnext/STAGE_F_GF1_HEADLESS_MARKET_CONTRACT_2026-11-11.md` §1.3（「輸入來源 `mkt_info`／`jingqi_info`／`cl_data`／`li_latest` 只存在於 session。**無 headless 副本**」「輸出 9 鍵……**無 `as_of`**」）。
- **UI2 沒有 `warroom_summary` 寫入者**：對 `src/ui2`、`src/services/ui2`、`app_ui2.py`、`shared/ui2_contract` grep `warroom`，僅命中 `real_feed.py` 檔頭與 `real_canonical.py` 的註解／docstring（皆為「只讀」描述）；`tests/test_ui2_guards.py` 的 G2F `_G2F_BANNED_NAMES` 禁止 feed 出現 `compute_and_store_warroom_summary`、`refresh_macro_now` 等 producer。寫入者在 Legacy：`src/services/macro_refresh_service.py::STEP_WARROOM`（Legacy 新 UI「更新今日戰情」那一輪）。
- `macro_state.json`、`risk_cap_state.json` 被 `.gitignore` 排除、`git ls-files` 無此二檔。出處：`.gitignore`；`docs/BACKLOG.md` `DEC180-UI2-REGIME-STATE-FILES-PUBLISH`（「Cloud 上位階預期恆『⬜ 尚未載入』（INFERENCE，未實機驗）」）、`NUI2-PREVIEW-CLOUD-STATE-FILES`（open 未驗）。**Cloud 容器內是否真的不存在這兩檔：INFERENCE／NOT VERIFIED。**
- **即使這兩檔存在，位階仍不會載入**：`tests/test_batch_c21.py::TestRegimeMatrix::test_absent_cold_start_gate` 釘住「旗標 False（現行）：warroom 不存在 ⇒ 舊檔**有效**時位階未評估（`SOURCE_UNLOADED`）、不退舊檔」。
- **廣度旗標**：`shared/signal_thresholds.py::BREADTH_PROXY_SCORING_ENABLED = False`（DEC-074 B）。其 docstring 與 STAGE_F §1.5 記載：現行 `fetch_adl` 為由 `^TWII` 反推的估算（`is_proxy=True`）、`data_cache` 無逐日漲跌家數序列；**復活條件缺一不可**：(1) 正式漲跌家數來源接上並帶 `is_proxy=False` provenance，或另一套經客戶核准的計算方式；(2) 客戶裁示可計分。「『恢復』是否等於『新增來源』須客戶裁示」。
- 前進式驗證帳本 `data_cache/macro_forward_test/signals.parquet`：**FACT（出處為 repo 文件，作者未讀檔案值）**——`STAGE_F_GF1…` §1.6／`STAGE_F_HEADLESS_INPUT_AND_STALE_SEMANTICS_2026-11-11.md` 量測日 2026-11-11 記載：（原句，兩份文件分別記載）`STAGE_F_GF1…` §1.6：「47 列（date 2026-08-20～11-03，25 欄）；`effective_regime` bull 22／neutral 18／unknown 6／bear 1；`schema_version` 1:37／2:4／3:6；`date_source=backfill_from_captured_at` 37 列」；`STAGE_F_HEADLESS…` 同表：「6 列 unknown 的 `regime_source`＝`unevaluated:breadth_unavailable`」「v1／v2 列為旗標生效前，仍有 bull／neutral 歷史值」。**兩份來源都沒有直接寫「schema v3 的 6 列即是那 6 列 unknown」；把兩者對應起來是 INFERENCE**（數字相同、`regime_source` 與 v3 語意一致，但作者未讀 parquet 驗證）。另：PIT 被拒；「不得充當 live 市場判斷」；`src/ui`、`src/ui2`、`app.py`、`app_ui2.py`、`src/services/ui2` 皆無引用，**無「禁止讀取」測試，僅靠無 caller（INFERENCE）**。該帳本的 producer workflow `update_macro_forward_test.yml` 於 2026-11-14 被手動停用（`DEC-185`，`disabled_manually`）；**現在是否仍停用：NOT VERIFIED**。
- 帳本的每腿資料日欄位定義（只引既有 schema 註解，未讀 parquet 值）：`shared/macro_forward_test_schema.py` 的 `inputs_as_of`、`score_index_as_of`（大盤分用的 ^TWII 最後一根）、`inst_as_of`（外資現貨；失敗時回的是請求日，不是資料日，故為 None）、`adl_as_of`（廣度實際被用的末列）、`li_as_of`（先行指標末列）。**同檔註解明寫這四個 per-leg 欄位為「純觀測：⛔ 不得用這四欄做任何判斷（寫不寫列、改判 ⬜、新鮮度…皆禁止）」**（`MACRO_FWD_TEST_LEG_AS_OF_COLUMNS`）。`max_score` 註解亦指出「當日實際分母會隨選填腿在／不在浮動」——即**哪幾條腿實際參與當日位階結論，本身會變動**。
- **位階本身是內部衍生值，沒有官方發布日**；任何位階 as_of 都只能衍生自輸入腿，並**繼承各輸入腿的授權（DG-LIC）與 PIT（DG-PIT）狀態**，不會因為是「自己算的」而免除（INFERENCE，依 DEC-205 的限定射程推得）。

### 2.2 UI2 各路徑的位階結果

| 路徑／條件 | 位階結果（畫面） | 既有測試斷言（已用 grep 確認存在） |
|---|---|---|
| **Real（`app_ui2.py` 預設）**，無 warroom、無狀態檔（Cloud 預期） | `⬜ 尚未載入`（NOT_EVALUATED）＋`⬜ 資料日未提供`；第一屏短句＝「資料日未提供」＋原因句＋**新增末句「尚無可用的市場位階資料，暫不顯示判讀。」**（`real_canonical.REGIME_NO_DATA_NOTE`，現行 main）；L2 說明句＝L0「缺正式市場廣度」＋「這裡不提供更新，所以這一格維持尚未載入」 | `tests/test_ui2_real_feed.py::test_regime_unloaded_is_not_evaluated_with_the_l0_explanation`；`tests/test_batch_c21.py::TestRegimeMatrix::test_absent_cold_start_gate` |
| Real，無 warroom，**舊 `macro_state.json` 有效** | 仍 `⬜ 尚未載入`（不退舊檔） | `test_absent_cold_start_gate`（`old_only`／`both` 情境） |
| Real，warroom 存在但健康分缺（廣度只有代理值） | `⬜ 無法判定`（UNDETERMINABLE），非「尚未評估」；第一屏短句同樣以 `REGIME_NO_DATA_NOTE` 收尾（有真值與讀取失敗兩分支**不帶**此句） | `tests/test_ui2_real_feed.py::test_regime_breadth_unevaluated_is_unable_to_determine_not_not_evaluated`；`tests/test_batch_c21.py::TestRegimeMatrix::test_no_health_breadth_gate` |
| Real，位階讀取例外 | 🔴 來源目前不可用（不當成未評估） | `tests/test_ui2_real_feed.py::test_regime_read_failure_is_unavailable_not_unevaluated` |
| Real，位階「已載入」（目前**無已知的正常路徑**可達；僅為契約情境） | 顯示全站位階字（多頭等）＋`⬜ 資料日未提供`；🗂 計入「資料未備」 | `tests/test_ui2_real_feed.py::test_regime_loaded_uses_the_site_wide_label`；`tests/test_ui2_data_freshness_overview.py::test_all_missing` |
| FAKE 場景（開發面 `?ui2_dev=1`） | 示意值（標 FAKE）；與真資料無關 | 既有 FAKE 場景測試（不在本題範圍） |

**註（2026-11-23）**：`REGIME_NO_DATA_NOTE` 相關斷言在 `tests/test_ui2_real_feed.py`、`tests/test_ui2_v1u1_viewports_and_copy.py`（grep 命中）；本表第 1 欄原寫的測試名稱未變。

**結論（FACT 彙整）**：在 Real 軸，位階目前**沒有任何已知路徑能在 Cloud 上載入有值**；「尚未載入」是結構性結果，不是某次抓取失敗。**最強成因是客戶自己的裁示**：DEC-074 B（客戶 2026-10-23，代理廣度不得計分、`BREADTH_PROXY_SCORING_ENABLED=False`）與 DEC-075 D-1(a)（位階一併「⬜ 未評估／資料不足」）；架構成因（無 UI2 寫入者、狀態檔不在 git）次之——即使架構補齊，旗標不動位階仍不載入（見 `test_absent_cold_start_gate`、`test_no_health_breadth_gate`）。

### 2.3 可能造成誤讀之處（只陳述事實；DEC-202 O2 的「非缺陷、影響低」判定針對「有值無日期」，**不涵蓋**本節「長期無值」情形，故此處不引為先例）

- Real 頁首橫幅（`shared/ui2_contract/text.py::REAL_PREVIEW_BANNER_NOTE`，**現行 main**）寫「**目前僅部分台股資料已接入；各項指標請以卡片顯示的資料日與狀態為準。**」（舊字樣「僅台股與市場位階為真資料」已被取代，新橫幅**不再點名位階**；本稿初版曾引用舊字樣，已更正。）因此「橫幅宣稱位階為真資料」的矛盾**不再成立**。
- 位階卡未載入／無法判定時，第一屏短句末尾現有「尚無可用的市場位階資料，暫不顯示判讀。」（`REGIME_NO_DATA_NOTE`），位階一側已直接說明無資料。
- 🗂 資料頁第一屏（`src/services/ui2/data_page.py::freshness_rows`）寫「固定清單 8 項」「**已接入畫面 2 項**｜尚未提供 6 項」；位階屬「已接入」（此字樣與 `RegimeFact` 欄位、`REGIME_ASOF_NOTE`、`TEXT_NOT_LOADED`／`TEXT_ASOF_MISSING` 在現行 main 均未變），其狀態在計數中落「⬜ 尚未評估」（未載入時）或「⬜ 資料未備」（已載入但無資料日時）。
- 「已接入」在此指「畫面已接上該事實的讀取」，**不等於**「目前有值」；**目前剩餘的誤讀風險只在這一側**：資料頁把位階計為已接入、其狀態恆為尚未載入（橫幅與位階卡一側已有明示文字）。BACKLOG `UI2-DATA-ITEMS-REGIME-LOADED-WORDING`（「待評估，不施工」）已登記同族的措辭疑慮（已載入時顯示「資料未備」）。

---

## 3. 三項待決策

> 選項字母**只在各決策內有效**，回覆時請帶決策編號（見第 4 節）。所有推薦皆為 RECOMMENDATION，**不是裁示**，客戶可全部不採。

### 3.1 決策 1：長期缺值容忍度

**問題（白話）**：目前 Real Preview 的位階會長期、結構性地顯示「⬜ 尚未載入」（原因見 2.1／2.2）。這個狀態可以長期存在嗎？

**先說清楚成因**：位階長期無值，**最強的成因是客戶自己的 DEC-074 B／DEC-075 D-1(a)**（旗標 `BREADTH_PROXY_SCORING_ENABLED=False`、位階一併未評估），架構成因（UI2 無寫入者、狀態檔不在 git）次之。因此**決策 1 實質在問：是否接受 DEC-074 B 的長期後果**（在正式廣度來源與客戶計分裁示到位前，Real Preview 位階不會有值）。注意：DEC-202 的 O2 只判定「有值無日期」，**沒有**判定「長期無值」；後者是本次首次請示。

| 選項 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A 接受現狀** | 位階長期顯示「⬜ 尚未載入」；不改任何畫面字句、計數、測試；僅維持 DEC-202 的文件揭露 | 零改動、不碰任何 Gate；畫面本身誠實（不造值、不補 0，符合 `CLAUDE.md` §1） | 客戶在 Preview 永遠看不到位階值；資料頁「已接入畫面 2 項」把位階計為已接入、事實是位階目前沒有值，是否構成誤導，**由客戶判定**（現行橫幅已不點名位階，原橫幅矛盾不再成立） | 這是「**文字是否與事實相符**」的問題，現只剩資料頁計數一側：「已接入」＝畫面已接上讀取，但位階恆為尚未載入；位階卡另有「尚無可用的市場位階資料，暫不顯示判讀。」。是否仍易誤讀，需客戶看過資料頁計數（並對照位階卡新句與橫幅新字樣）後判斷（作者不替客戶下結論） |
| **B 接受長期未載入，另案調整揭露** | 同意位階長期未載入，**並同意後續另案**評估新增揭露字句、改橫幅／計數口徑、口徑鎖定測試（**本文不提案這些的內容**） | 消除 2.3 的誤讀；揭露與事實更貼合 | 屬 DEC-202 明列「候選但未授權」的新文案／口徑變更；需新文案 Gate；動 `src/ui2/**` 會使 DEC-137 存證 `source_hash` 失效、須重生四份存證；連動 P3 evidence 基準 | 一次改字牽動多處測試與存證；文案若與 DEC-177 口徑不一致會產生新矛盾 |
| **C 不接受** | 位階無值就不算 Real Preview 完成；把「位階有值」列為 Real Preview 驗收條件 | Real 軸名實相符 | 取決於決策 3 的資料來源（見 3.3），且受廣度旗標與來源授權雙重阻擋 | 卡住目前的 Offline Preview Ready 驗收；時程取決於外部授權（DG-LIC 等待條款原文／法務，時間不在 AI 手上） |

**AI 總管推薦：A，前提是「客戶看過三處現行文字——橫幅『目前僅部分台股資料已接入；各項指標請以卡片顯示的資料日與狀態為準。』、位階卡『尚無可用的市場位階資料，暫不顯示判讀。』、資料頁『已接入畫面 2 項』——後，仍接受位階長期無值」。若客戶認為資料頁計數（目前唯一剩下的疑點）與事實不符，請改選 B。**
**理由**：(1) **O2 不能當依據**：O2 只涵蓋「位階有值但無可驗證 as_of」，**未**涵蓋「長期無值」；後者的使用者影響是本次首次請示，**尚無既有判定**，客戶不應以為已有先例；(2) 位階缺值的最強成因是 DEC-074 B／DEC-075 D-1(a)（客戶既有裁示），其次是來源授權與無 UI2 寫入者，都是**資料來源／資料政策 Gate**，不是畫面問題，選 C 只是把畫面驗收綁到一個今天無法解的條件上；(3) B 的內容（新增揭露字句、改橫幅／計數口徑、口徑鎖定測試）屬 DEC-202 明列「候選但未授權」，本文不提案其內容，只請客戶表態要不要另案評估。
**請客戶同時明示（選 A 或 B 皆需回答）**：「橫幅／位階卡文字／資料頁計數口徑是否另案評估：〈另案／不另案〉」。選「另案」＝只同意 AI 總管另送新文案 Gate 請示，**不是**授權改字；選「不另案」＝該疑慮就此結案。（取代原先「有客戶抱怨才處理」的觸發式寫法。）
**後續所需 Gate**：A＝無；B＝新文案 Gate＋UI 變更草稿先行（若動版面）＋DEC-137 存證重生；C＝見決策 3。**是否動既有 Contract**：A 否；B 可能（`shared/ui2_contract/text.py` 文案常數屬契約檔，需另案）；C 是（見決策 3）。

### 3.2 決策 2：將來 as_of 日期規則（僅在位階日後真的有值時才適用）

**前提（FACT）**：位階契約目前無 as_of（`RegimeFact` 無此欄）；SG-10 禁止以 `cl_ts` 頂替；擴契約須客戶 Gate；DEC-205 的 DG-PIT＝B＋X 只允許「顯示最新值的資料日」。位階是**多條輸入腿的合成結論**，而「哪幾條腿實際參與當日結論」會浮動（2.1，`max_score` 註解），因此「位階的資料日」本身是一個**定義**問題，不是單純加一欄。

| 選項 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A 取輸入腿的最早日** | 位階資料日＝參與結論的各腿 as_of 的最小值；任一腿缺日則整體不顯示日期（fail-closed） | 保守：不會宣稱比任何一腿更新；與 `CLAUDE.md` §1 方向一致 | 單一舊腿會拖低整體；「資料日」可能被讀成整體日期；須先定義「哪幾腿參與」；**輸入腿頻率不一致時最早日可能長期過舊**：若有月頻腿參與（站內月頻來源如 M1B／M2、PMI，`CLAUDE.md` §2.3 發布延遲表：M1B／M2 約月後 27 天、月度 PMI 約月後 5–10 天），最早日幾乎恆為數週前（INFERENCE；現行 `M1B_M2_LEG_ENABLED=False`，**哪些腿屬月頻、是否參與 NOT VERIFIED**） | 腿定義不清時日期不可重現；需要各腿都有可信資料日（現無 headless 副本） |
| **B 取輸入腿的最晚日** | 資料日＝各腿 as_of 最大值 | 看起來最新 | **高估新鮮度**：舊腿被新腿掩蓋，等同為舊資料背書 | 違反寧可保守、不得造日期的原則；**不推薦** |
| **C 各腿並列** | 不合成單一日期，列出每條腿各自的資料日（大盤、外資、廣度、先行指標等） | 最誠實、可稽核；符合 DG-PIT「只顯示最新值的資料日」的精神 | 版面異動（需 UI 草稿先行）；新文案；與 🗂 第一屏「單一資料日」計數口徑如何對映待另定 | 畫面變重；各腿 as_of 來源與權利需逐腿確認（DG-LIC／DG-PIT） |
| **D 不顯示（維持 `⬜ 資料日未提供`）** | 即使將來位階有值，也不顯示資料日；🗂 仍計「資料未備」 | 不動契約、不新增文案、與現狀及 DEC-202 O2 一致 | 位階有值時使用者無從判斷新舊；「多頭」等顯示不構成已確認資料日期（DEC-202） | 使用者可能把無日期的值當成最新值 |

**共通限制（不論選哪個）**：不得造日期；不得拿 `cl_ts` 或 `fetched_at` 頂替（SG-10、DEC-205）；不得使用 `signals.parquet` 的四個 per-leg 純觀測欄做新鮮度判斷（其 schema 註解明文禁止）；任何帶日期的選項都須**擴既有 service 契約**，屬 SG-10；DEC-190 要求位階一旦有資料日，「載入→資料未備」歸類須重審。

**AI 總管推薦：D（現階段維持不顯示）。閘門：位階一旦有值，無日期顯示須重新請示客戶（與 DEC-190 延後項「位階契約新增 as_of／載入→資料未備歸類須重審」同向），不得因本次選了 D 而默認沿用。條件式後備：日後位階真有值且客戶要日期時，以 A（最早日，任一腿缺日則整體 fail-closed）為起點；但若屆時有月頻腿參與、最早日長期過舊，則 C（並列）可能更合適，須依當時實際輸入腿再議。**
**理由**：(1) 位階目前沒有值（決策 3 若選甲則長期如此），為尚不存在的資料預先鎖死日期口徑，無從驗證；(2) 腿的集合會浮動，口徑必須在知道「真正有哪些腿、各腿的授權與 PIT 狀態」之後才定得準；(3) 若將來要日期，最早日是唯一不會高估新鮮度的單一值；B 會製造「看起來新」的假象，不推薦。
**後續所需 Gate**：D＝無；A／B／C＝SG-10（擴契約）＋DG-PIT（B＋X 射程內）＋逐腿 DG-LIC＋`I1144-WIRING-GATE`（若涉及接線）；C 另需 UI 草稿先行。**是否動既有 Contract**：D 否；A／B／C 是（需另案）。

### 3.3 決策 3：Cloud state 取得架構

**問題（白話）**：UI2 若要在 Cloud 上有位階，位階的輸入要從哪來？

**重要前提（FACT，2.1）**：不論選哪個架構，位階有值的**共同條件**是廣度旗標 `BREADTH_PROXY_SCORING_ENABLED` 的復活條件被滿足。docstring 原意：(1) 正式漲跌家數來源接上並帶 `is_proxy=False`，**或另一套經客戶核准的計算方式**；(2) 客戶裁示可計分。**架構只決定「怎麼取輸入」，不會自己產生缺的正式廣度來源。**

| 選項 | 內容 | 優點 | 缺點 | 所需 Gate／是否動既有 Contract |
|---|---|---|---|---|
| **A 接受長期未載入** | 維持現狀（與決策 1 的 A 搭配） | 零改動；不碰授權與來源 | 位階在 UI2 永遠沒值 | **無新 Gate**；**不動** Contract |
| **B UI2 headless 自行計算** | UI2 自己從原始資料算位階（需 I/O 與輸入來源） | 不依賴 Legacy | 輸入（`mkt_info`／`jingqi_info`／`cl_data`／`li_latest`）**無 headless 副本**（STAGE_F §1.3）；需新取數／cron／Secrets；缺正式廣度來源；feed 對 L3 service 只准 `get_twii_trend_view`／`get_macro_regime` 兩個名稱（G2F 白名單，`tests/test_ui2_guards.py`）須放寬 | **DG-LIC**（來源授權，HOLD）、**DG-PIT**（B＋X）、**I1144-WIRING-GATE**（未授權）、**SG-10**（as_of）、**G2F**（放寬守衛）、廣度旗標復活條件；**動**既有 Contract（新增 as_of、可能新增 service） |
| **C 沿用 Legacy 流程** | UI2 讀 Legacy 更新後寫入的 session `warroom_summary` | 計算邏輯已存在、不重寫 | **UI2 與 Legacy 是否共用 session：NOT VERIFIED**。現況 `app_ui2.py` 與 `app.py` 是**兩個獨立入口檔**（FACT：`app_ui2.py` 自行呼叫 `st.set_page_config`，只 import `src.ui2` 與 `connection_diag_service`；`git grep -n app_ui2 -- app.py` 0 命中；repo 根無 `pages/` 目錄）；共用 session 需先改部署／導航形態（INFERENCE；Cloud 部署形態 NOT VERIFIED）。`NUI2-REALFEED-WARROOM-CONTRACT-INTEGRATION` 亦記載「同行程／同 session」才成立。另受 DEC-161 邊界限制（「不以 session 的 `macro_state.json` 或推播 SA 冒充 headless source」，同一不授權條款）；UI2「更新」CTA 目前 disabled，feed 被 G2F 禁止呼叫任何 producer；warroom 組合可能被 `validate_regime_fact` 判契約違反（同 BACKLOG 條目） | **I1144-WIRING-GATE**、**G2F**（解禁 producer 呼叫）、**SG-10**、廣度旗標復活條件；可能**動**既有 Contract（`validate_regime_fact` 擴充）；DG-LIC／DG-PIT 視輸入來源而定（NOT VERIFIED） |
| **D 改由已提交的快取產物提供** | 新 producer 把位階（或其輸入）發布成 git 追蹤的快取檔，UI2 讀檔 | 與台股日 K 既有「cron→PR→git 檔→feed 讀檔」模式一致；BACKLOG 已登記候選 `DEC180-UI2-REGIME-STATE-FILES-PUBLISH`（未授權） | 需**新 producer**與**新來源 Gate**；資料發布 workflow 現況（DEC-185：三支被手動停用，恢復條件未裁示）；**不可用 `signals.parquet` 當來源**——repo 既有記載：凍結帳本（同日已存在則保留既有、不覆寫）；`shared/macro_forward_test_schema.py` 檔頭：離線重建版與線上版在 `conf`（重建恆 60／線上可達 100）、`m1b_m2_prev` 兩處系統性不同；STAGE_F §1.6：v1／v2 的 bull／neutral 為旗標生效前的舊規則值（INFERENCE：這正是 DEC-075 D-1(a)「不得靜默沿用另一套規則」所要避免者）、PIT 被拒、「不得充當 live 市場判斷」；producer 已被停用（見 2.1）；且該帳本 per-leg 欄位禁止用於判斷。**即使只發布 state 檔，旗標不動位階仍不載入**（`test_absent_cold_start_gate`／`test_no_health_breadth_gate`）。DEC-161 邊界同樣適用（不以 session 的 `macro_state.json` 冒充 headless source） | **DG-LIC**、**DG-PIT**、**I1144-WIRING-GATE**、**SG-10**、新 cron／Secrets 授權、資料發布授權（DEC-205 明示不授權）、廣度旗標復活條件；**動**既有 Contract |

**AI 總管推薦：A（接受長期未載入）。**「是否希望位階有真值」屬既有未決的 G-F1 方向題，由總管另案單獨整理成客戶 Decision Gate 請示（BACKLOG `G-F1` 列：「由總管整理成客戶 Decision Gate」）；本稿的回覆**不視為已答 G-F1**，本題也不先挑 B／C／D。
**理由**：(1) B、C、D 都被**同一組尚未解的前置條件**阻擋：廣度正式來源與客戶計分裁示、DG-LIC／DG-PIT 逐資料集證據、I1144-WIRING-GATE；現在選架構，只是把一個今天無法開工的方案寫進計畫；(2) 架構選擇取決於**資料來源**答案——來源若是官方公開資料集，D（發布快取）最自然；若來源是 Legacy 運算，C 才有意義；這正是 BACKLOG `G-F1`（客戶方向 Gate：是否希望使用真正可信的市場位階／廣度資訊）要先問的，且須另案單獨請示；(3) 與決策 1＝A、決策 2＝D 構成**一組自洽的「維持現狀」組合**，不會留下半套契約。
**重要**：G-F1 若日後由客戶同意方向，**僅授權後續來源／PIT／授權可行性研究，不自動授權開 fetcher、cron、Secret 或正式接線**（沿用 BACKLOG `G-F1` 列的限定）。

---

## 4. 客戶可直接回覆的格式

一行即可（選項字母只在各決策內有效，請帶決策編號）：

```
決策1=〈A／B／C〉（橫幅／位階卡文字／計數口徑：〈另案／不另案〉）、決策2=〈A／B／C／D〉、決策3=〈A／B／C／D〉
```

- **AI 總管推薦組合**：`決策1=A（橫幅／位階卡文字／計數口徑：由客戶表態）、決策2=D、決策3=A`（＝維持現狀；位階長期顯示「⬜ 尚未載入」，不新增任何字句或契約）。推薦 A 的前提見 3.1（客戶看過橫幅、位階卡、資料頁計數三處現行文字後仍接受）。
- **互相矛盾的組合**（例如決策 1=C 要求位階有值、決策 3=A 接受永遠無值）由總管追問，**不視為有效回覆**。
- 本稿**不含** G-F1 的欄位；G-F1 另案單獨請示，本稿回覆不視為已答。
- 沒答的項目視為**維持現狀**（等同各決策的推薦選項 A／D／A 的「不動」效果，但**不是**客戶裁示）。
- 若選到需要後續工作的選項（決策 1 的 B／C、決策 2 的 A／B／C、決策 3 的 B／C／D），**回覆本身不構成施工授權**；AI 總管會另送對應 Gate 的請示（新文案 Gate、SG-10、DG-LIC／DG-PIT、I1144-WIRING-GATE、G2F 等），逐項取得授權後才進入實作。
- 想改為「不採推薦、另有想法」，直接寫自己的答案即可。

---

## 5. 本文件不是什麼

- **不是**授權：不授權任何程式、測試、契約、文案、資料來源、cron、Secrets、workflow、資料發布、接線或 UI 變更。
- **不是** QA PASS：單組作者、未經非作者 QA、無 exact-head CI、無 main CI。
- **不是** Cloud 驗證：Cloud 實際部署狀態（狀態檔是否存在、Cloud 上實際顯示的橫幅新字樣／位階卡新句／資料頁計數）NOT VERIFIED（上述現行字樣只依 main 原始碼）。
- **不是**對 DEC-202 O2 的重新裁決：O2 現狀判定原樣有效。
- **不是** Contract 變更提案：本文不提出修改 `shared/ui2_contract`、`RegimeFact` 或任何 service 的條文；若客戶選了需要契約變動的選項，須另案走 SG-10。
- **不是**「某項已可接上」的宣稱：本文所有選項均尚未取得所需 Gate。

---

## 6. 驗證用 grep 指令（從 repo 根目錄執行；皆唯讀）

```bash
# 1.1 O2 與 DEC-202
grep -n "^### DEC-202" docs/DECISIONS.md
grep -n "O2｜regime 有值但無可驗證 as_of" docs/BACKLOG.md
# 1.2 Q5 候選
grep -n "^### Q5" docs/vnext/NEWUI2_DATA_FRESHNESS_OVERVIEW_IMPLEMENTATION_DECISION_SHEET_2026-11-13.md
grep -n "Q5=A" src/services/ui2/real_canonical.py src/services/ui2/data_page.py
grep -n "UI2-DATA-ITEMS-REGIME-LOADED-WORDING" docs/BACKLOG.md
grep -n "Q5：A，並確認代理值不計分" docs/DECISIONS.md docs/BACKLOG.md
grep -n "一題都未回答" docs/DECISIONS.md          # DEC-179 的 Q1～Q7 未答紀錄
grep -n "^### DEC-190" docs/DECISIONS.md
# 2.1 資料路徑與缺口
grep -n "class RegimeFact" -A 12 src/services/ui2/real_canonical.py
grep -rn "warroom" src/ui2 src/services/ui2 app_ui2.py shared/ui2_contract
grep -n "macro_state.json\|risk_cap_state.json" .gitignore ; git ls-files | grep -c "macro_state.json\|risk_cap_state.json"
grep -n "BREADTH_PROXY_SCORING_ENABLED" shared/signal_thresholds.py
grep -n "inputs_as_of\|score_index_as_of\|inst_as_of\|adl_as_of\|li_as_of\|純觀測" shared/macro_forward_test_schema.py
grep -n "update_macro_forward_test.yml" docs/DECISIONS.md   # DEC-185 停用紀錄
grep -n "^### 1.6" -A 6 docs/vnext/STAGE_F_GF1_HEADLESS_MARKET_CONTRACT_2026-11-11.md
grep -n "SG-10" docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md
grep -n "DEC180-UI2-REGIME-STATE-FILES-PUBLISH\|NUI2-PREVIEW-CLOUD-STATE-FILES\|NUI2-REALFEED-WARROOM-CONTRACT-INTEGRATION" docs/BACKLOG.md
grep -n "G2F_IMPORT_ALLOWLIST\|compute_and_store_warroom_summary" tests/test_ui2_guards.py
# 2.2 路徑與測試
grep -n "def test_regime_" tests/test_ui2_real_feed.py
grep -n "def test_no_health_breadth_gate\|def test_absent_cold_start_gate" tests/test_batch_c21.py
grep -n "def test_all_missing" tests/test_ui2_data_freshness_overview.py
# 2.3 橫幅、位階卡新句與計數文字
grep -n "REGIME_NO_DATA_NOTE" src/services/ui2/real_canonical.py
grep -rln "REGIME_NO_DATA_NOTE" tests
grep -n "REAL_PREVIEW_BANNER_NOTE" shared/ui2_contract/text.py
grep -n "已接入畫面" src/services/ui2/data_page.py
# 3.3 G-F1
grep -n "\*\*G-F1\*\*" docs/BACKLOG.md
```

---

## 7. NOT VERIFIED

- **「Q5」的確切指涉**（1.2）：本文列出兩個與位階相關的候選，**不猜**；若派工訊息另有所指請更正。
- **DEC-177 Q5 是否由客戶逐題明示裁定**：repo 內僅見 `DEC-190`（方案 C、Q1=A、D-5）與 `DEC-179`（Q1～Q7 未答）；GPT 定稿留言（#1199 comment 6964559744）與客戶核准留言（6964576511）本次未讀（作者環境無網路）。
- **派工來源留言（#1199 comment 7079173656）原文未讀**：三項待決策依派工訊息轉述。
- **Cloud 實況**：Cloud 容器內 `macro_state.json`／`risk_cap_state.json` 是否存在；Cloud 部署版本；Cloud 上實際顯示的橫幅新字樣、位階卡新句與資料頁計數（本稿只依 main 原始碼）。
- **Legacy 與 UI2 是否共用 session**（決策 3 的 C）。
- **`update_macro_forward_test.yml` 現在是否仍停用**（DEC-185 記錄的是 2026-11-14 狀態）。
- **`signals.parquet` 的現況列數與值**：本文引用的 47／6 列等數字來自 repo 文件（量測日 2026-11-11），作者**未讀檔案值**，之後可能已變動。
- **「哪幾條輸入腿實際參與位階結論」**的精確集合與其各腿 as_of 的 headless 取得性（決策 2 的前提）。
- **DG-LIC／DG-PIT 對各腿來源的逐資料集結論**：均為 HOLD，未取得證據。
- **各選項的工時、成本與施工可行性**：本文只列 Gate 與契約影響，未估工時，也未試作任何原型。
- **非作者 QA、exact-head CI、main CI**：皆未做。
