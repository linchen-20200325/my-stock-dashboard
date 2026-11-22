# OneBrain 持股讀取結果 → Digest 輸入：離線契約（C-OB-HOLDINGS-INPUT-CONTRACT-1；2026-11-21）

> **性質**：契約**設計**＋離線驗收案例的對照文件。**不是 adapter 實作、不是 schema、不是接線、不是授權。**
> **授權**：Issue #1199 comment 7060205009（契約設計＋離線驗收案例；最多一支 Draft PR；不合併）。
> **依據**：DEC-215、DEC-218（Q1=B 持有部位全集；Q2=(a) 選定單一本組合）、DEC-219（L1 tally）；
> `docs/vnext/ONEBRAIN_DUAL_UNIVERSE_TABLE_2026-11-21.md`、`docs/vnext/ONEBRAIN_UPSTREAM_EXCLUSION_POINTS_CONTRACT_EVIDENCE_2026-11-21.md`。
> **量測基準**：main `29594c5a`；以符號為準，不寫行號。
> **驗收測試**：`tests/test_onebrain_holdings_input_contract.py`（規範＝`test_norm_*`；現況≠契約＝`test_gap_*`，`xfail(strict=True)`；
> 現況快照＝名稱含 `current_behavior`；突變＝`test_mutation_*`）。
> **標記**：FACT＝原始碼或測試可直接核對；INFERENCE＝由 FACT 推得；NV＝NOT VERIFIED。
> **狀態**：L1 可用（dormant，0 production caller）；**Digest NOT READY**；OneBrain 正式廣度 NOT EVALUATED。單組撰寫，非 QA PASS。
> **版本／變更紀錄**：見 §F。最新一版 2026-11-22：依客戶正式裁示 #1199 comment 7071998333（分析 7071883974 方案 C），§A 第 9–11 列與第 12 列預設模式標為**目標態 list／過渡期 None**，新增「§A 註」（C-EX-CONTRACT-DOCS-IMPLEMENT-1；docs-only；非 adapter 實作）。

## 0. 兩側的現況（FACT）

- **L1**：`src/data/portfolio/gsheet_portfolio.py` 的 `load_portfolio_tallied(name, …)` 回 `PortfolioReadTally`；
  `tally_portfolio_records` 為其純函式核心。非 `ok`／`not_selected` 時全部計數為 `None`。`raw` 與 `rows` 來自**同一份快照**，
  **不是獨立應有母體**。`rows` 每列只有 `ticker`／`lots`／`avg_price`，**沒有 `held`**。`LoginRequiredError` 與權限／網路等例外**原樣上拋**。
- **Digest**：`src/services/decision_digest_builder.py` 的 `build_decision_digest`／`plan_action_selection`，
  `src/services/decision_digest_assembly.py` 的 `assemble_digest`，`shared/decision_digest_coverage.py` 的 `DigestCoverage.is_complete`，
  `src/services/decision_digest_summary.py` 的 `build_rule_summary`。builder 只讀持有列的 `ticker`／`代號` 與 `held`（**不讀 lots／avg_price**）；
  `held` 須為 `bool` 或缺／None（缺／None／False＝非持有），其他型別 `TypeError`。
- **兩側之間沒有 adapter**（0 production caller；本文件也不建）。

## §A 逐列對照表：L1 讀取狀態 → Digest 可用輸入 → coverage → 人可讀摘要

「Digest 輸入」欄即測試內契約規格表 `contract_expected_holdings_input` 的輸出類別（測試專用，非 production adapter，
有守衛確認 `src/`、`shared/`、`scripts/`、`app*.py` 未引用）。
⚠️ 2026-11-22 起，第 9–11 列與第 12 列（預設模式）此欄所載 list 為**目標態**；過渡期實際應給的輸入見下方「§A 註」。測試內 `contract_expected_holdings_input` 對 raw>0 的 ok 狀態一律輸出 list 類別（＝目標態；FACT），本次未改測試。

| # | L1 讀取狀態 | Digest 可用輸入（`holdings_rows`） | coverage（`assemble_digest`） | 人可讀摘要（`build_rule_summary`） | 驗收 |
|---|---|---|---|---|---|
| 1 | `not_selected`（name 空白；不讀 Sheet） | **None**（§B1） | `unkeyed_held_count`／`holdings_non_mapping_rows`＝None；`is_complete=False` | 持股兩段與行動段只有「⬜ …無法判定」；**不得**出現零持股字樣 | `test_norm_unknown_l1_states_map_to_none_not_empty_list`、`test_norm_none_input_digest_coverage_summary_all_unknown` |
| 2 | 讀取失敗狀態：`worksheet_missing`／`schema_mismatch`（及任何非 ok 的未知狀態） | **None**（§B1） | 同上 | 同上 | 同上 |
| 3 | `LoginRequiredError`（及權限／網路／配額等例外） | L1 **不產生 tally**（原樣上拋，不得轉成狀態或 0）；若 L3 仍要建 Digest，holdings 必為 **None** | 同上 | 同上 | `test_norm_l1_login_required_never_becomes_a_tally`；上拋 vs 降級見 §C-9 |
| 4 | 計數未知（status ok 但 `rows` 或任何計數為 None） | **None**（fail-closed；§B1） | 同上 | 同上 | `test_norm_unknown_l1_states_map_to_none_not_empty_list` |
| 5 | ok＋選定組合不存在（`raw==0`、`other_name_rows>0`） | **待決**（候選 None 或 []；§C-1） | 兩個候選皆 `is_complete=False` | 兩個候選皆不得宣稱零持股 | `test_norm_pending_raw_zero_both_candidates_never_claim_zero_holdings`、`test_current_behavior_c1_…` |
| 6 | ok＋空表／只有表頭（`raw==0`、`other_name_rows==0`） | **待決**（同 #5；L1 無法與 #5 在「選定組合是否存在」上區分） | 同 #5 | 同 #5 | 同 #5 |
| 7 | ok＋有持有列且可評估（有 `HoldingKey`） | **list**：依 §B3 手寫（只取屬持有全集的列、`held=True`；計數單位未裁示） | 有鍵列 → entries（輸入順序）；但缺獨立母體 → 依契約須 incomplete（**現況可能 True**，§C-6） | 行動句逐字展開 | `test_norm_no_row_lost_and_duplicates_not_silently_absorbed`、`test_gap_contract_fed_input_without_independent_universe_must_be_incomplete` |
| 8 | ok＋有持有列但無法評估（無 `HoldingKey`） | **list**（該列照樣一筆 `held=True`，不得丟） | `unkeyed_held_count=n`、`is_complete=False`；**只有計數，沒有部位與原因**（§C-5） | 「⬜ 另有 n 檔持股缺少投資組合鍵…」 | `test_norm_unevaluable_rows_retained_with_count`、`test_gap_unevaluable_row_identity_and_reason_preserved` |
| 9 | ok＋L1 丟列（`dropped>0`，含 `kept==0`） | ~~**list**，依 §B3：~~ **目標態 list**（**過渡期回 None**＋固定脫敏原因碼，見 §A 註；刪除線為有意識的變更，不是漏刪；決策者 客戶；#1199 7071998333；日期 2026-11-22；兩邊理由見 §A 註第 6 點），目標態依 §B3：EX 丟列（`blank_ticker`／`non_numeric`／`non_finite`／`non_positive`）不入；`blank_value` 丟列（DEC-219 第 3 點；依 DEC-218 §一 第 1 點屬 IN-U）**須以 IN-U 入**；kept 中 NaN／+inf 屬 EX 不入。⚠️ **不是**「kept 列＝Digest 輸入」。丟棄列的數量與原因必須往下游揭露（§C-2） | **現況無通道**：coverage 看不到 L1 dropped（§C-2、§C-6） | 現況不揭露 | `test_norm_ok_with_rows_maps_to_list_including_dropped_dup_nonfinite`、`test_gap_contract_fed_input_…[l1_dropped_2]` |
| 10 | ok＋重複列（`duplicate_tickers` 非空） | ~~**list**~~ **目標態 list**（**過渡期回 None**＋固定脫敏原因碼，見 §A 註；有鍵重複會使 Digest `duplicate_holding_key` fail-loud（`shared/decision_digest.py` 契約檢查），**§C-3 技術契約訂定前不得給 list**；刪除線為有意識的變更，不是漏刪；決策者 客戶；#1199 7071998333；日期 2026-11-22；兩邊理由見 §A 註第 6 點）（不得默默去重、不得重複灌水；計數單位列 vs 代號未裁示；§B3、§C-3） | 有鍵重複 → `ValueError(duplicate_holding_key)`；無鍵重複 → 計 2、無重複揭露（§C-3） | 無鍵重複寫成「另有 2 檔」 | `test_norm_no_row_lost_and_duplicates_not_silently_absorbed`（只要求重複可觀測）、`test_current_behavior_c3_…`／`c3b_…`（列單位快照）、`test_gap_duplicate_holding_rows_disclosed` |
| 11 | ok＋非有限值（NaN／+inf 保留在 rows；-inf 已歸 `non_finite` 丟棄） | ~~**list，不含 NaN／+inf 列**~~ **目標態 list，不含 NaN／+inf 列**（**過渡期回 None**＋固定脫敏原因碼，見 §A 註；L1 快照只有 `kept_non_finite` 計數、**無逐列旗標，目前無法逐列剔除**；刪除線為有意識的變更，不是漏刪；決策者 客戶；#1199 7071998333；日期 2026-11-22；兩邊理由見 §A 註第 6 點）（§B3；歸類已定 EX，DEC-218 §一 第 5 點、雙母體表 §2）；L1 現況仍保留於 rows（§C-4） | 現況與乾淨值逐字相同 | 現況與乾淨值逐字相同 | `test_current_behavior_c4_…`、`test_gap_non_finite_source_value_disclosed_downstream` |
| 12 | ok＋張數／均價空白（預設模式歸 `blank_value` 丟棄；`keep_blank=True` 保留為 None） | 「保留為 IN-U」**已裁示**（DEC-218 §一 第 1 點）⇒ 應在 list 內（**目標態**；限保留空白值模式讀取）；**預設模式已把 `blank_value` 列丟掉 ⇒ 過渡期回 None＋固定脫敏原因碼，且永不改 list**（列已丟、無從還原；正式接線須用保留空白值模式，§C-8(b)；見 §A 註；客戶 #1199 comment 7071998333，2026-11-22）；待決只剩 IN-U 標示方式與 L1 預設模式會丟的差距（§C-8） | 保留時與乾淨值逐字相同（無 IN-U 標記） | 同左 | `test_current_behavior_c8_…` |
| 13 | 任一 ok 狀態的來源時點 | tally 與 `holdings_rows` 都不帶 `fetched_at`／`as_of`（§C-10） | 持有側無時點；`SegmentEvidence` 的 holdings 段 as_of：段採用（used）時先取該段 OK 事實中最舊的 provenance as_of，無則退回站內證據戳；未採用時取站內證據戳（若有）（`decision_digest_assembly.assemble_digest`／`_seg`／`_oldest`）。兩者都不是持股讀取時點 | 無持股資料日 | 文件登記（本批無對應測試） |

### §A 註（過渡期；客戶 2026-11-22 正式裁示）

> **依據**：客戶正式裁示 #1199 comment 7071998333（issue 轉錄，原始對話不在 repo）：「OneBrain EX 契約口徑正式裁示：過渡期=有無效列就整段顯示無法判定；未來剔除提示=保留正式上線 Gate，全部條件通過後不必再問產品口徑。…」；差異分析與三方案比較見 7071883974（客戶選方案 C「目標態不變＋過渡期 fail-closed」）。
> **性質**：本註是**產品口徑（業務語意）**的落盤，**不是 adapter 實作、不是 schema、不是接線、不是上線授權**。

1. **適用範圍**：§A 第 9、10、11 列與第 12 列「預設模式」部分，表內所載 list 為**目標態**；過渡期一律依本註。
2. **過渡期規則（fail-closed）**：在剔除提示／原因／影響範圍及 coverage 不完整的正式揭露機制尚未具備、尚未通過其 Gate 之前，持股輸入只要有**任一無效列**——EX 丟列（`blank_ticker`／`non_numeric`／`non_finite`／`non_positive`）、重複代號、保留列含 NaN／+inf（非有限）、預設模式 `blank_value` 丟列等——⇒ **整段 `holdings_rows=None`**，持股與行動段摘要只能說「無法判定」。
   - ⛔ **不得**以其餘列顯示持股建議；**不得**宣稱完整（`is_complete` 不得為 True）、零持股、中性或安全。missing≠0；UNKNOWN≠0／中性／SAFE（DEC-215 §一 第 2 點「不得隱藏，不得視為 0／中性／SAFE」；§B1）。
   - **原因碼**：須保留**固定、脫敏**的原因碼——只表達類別，不含代號、張數、均價、組合名稱、sheet_id 等來源私值。參考：Draft #1258 dormant adapter 現用 `ex_dropped_*`／`non_finite_kept`／`duplicate_tickers`／`in_u_blank_dropped`（該 PR 未合併；本文件不定碼名）。
   - 未知／空列（§A 第 1–6 列、§B1）既有的 fail-closed 語意**維持不變**。
   - 保留空白值模式（`keep_blank=True`）下保留為 None 的 IN-U 列不是「無效列」，本註不改其口徑（仍依第 12 列與 §C-8(a)）。
   - **文案**：過渡期對使用者應準確表達「資料無法判定／有異常輸入」，**不得**說成「沒有持股」；現行摘要「…無法判定（尚無輸入）」的「尚無輸入」措辭不準（§C-2 已記）。具體 UI 文案待產品／畫面 Gate，本文件不定稿。
3. **逐型解除前置**（每型各自滿足才可對**該型**改回 list；未滿足即維持 None）：
   - **四類 L1 EX 丟列**（`blank_ticker`／`non_numeric`／`non_finite`／`non_positive`）⇒ §C-2 揭露通道（丟棄數量與原因進 coverage 或其後繼）放行。
   - **保留列 NaN／+inf** ⇒ 可逐列辨識：DEC-219 明列 HOLD 的「NaN／+inf 過濾修補」放行，或 L1 快照提供逐列旗標（現況只有 `kept_non_finite` 計數；§C-4）。
   - **重複代號** ⇒ §C-3 技術契約（聚合粒度、計數單位、有鍵重複處置；DEC-218 §一 第 5 點「若尚無既有核准契約，待明確技術契約」）訂定並放行；在此之前有鍵重複會使 Digest `duplicate_holding_key` fail-loud。
   - **預設模式 `blank_value` 丟列** ⇒ **永不改 list**：列已丟、無從還原，不得以預設空白丟列冒充「已復原」；正式接線須用保留空白值模式讀取（§C-8(b)）。
   - **共同**：coverage 須能承載「不完整」；§C-6（缺獨立母體 ⇒ 任何 L1 餵入都須 incomplete）照常適用。
4. **目標態**：逐類滿足「可準確剔除、保留其餘列、可追溯揭露剔除 N 列與原因、coverage 不完整可承載」，並通過正式技術／品質／來源／使用者可見 UI Gate 後，依**已核准產品口徑**顯示其餘有效持股＋明示「剔除 N 列」——客戶**免再確認產品口徑**。
   - ⚠️ 免再確認的**只有產品口徑**，**不等於**授權接線、真實資料／Sheet／OAuth、Schema、Stage F／G、Cloud／部署、切換／回退——各自仍需原 Gate；任何 Ready、merge、部署或啟用仍依原流程。
5. **狀態不變**：Digest NOT READY；OneBrain NOT READY；OneBrain 正式廣度 NOT EVALUATED。本註不建 adapter、不改測試、不改 schema。
6. **兩邊理由**（§A 第 9–11 列刪除線；有意識的變更，不是漏刪；決策者 客戶；#1199 7071998333；日期 2026-11-22）：
   - **舊表述（直接寫 list）的理由仍成立**：它描述的是正確的終態——EX 列剔除、其餘 IN／IN-U 列照常評估，最貼近 DEC-218「持有全集」，也不浪費有效列。故舊表述保留為「目標態」，不是被推翻。
   - **新口徑為何勝出**：揭露通道（§C-2／§C-3／§C-4）尚不存在時直接給剔除後 list，四段齊備會 `is_complete=True` 且不提剔除，違 DEC-215 §一 第 2 點「不得隱藏」（7071883974 合成案例實跑，單組）；且有鍵重複會 fail-loud、NaN／+inf 無逐列旗標、預設模式空白列已丟無從還原——list 在現況有一部分根本做不到。代價：過渡期一列異常即整段無法判定（客戶已知悉並裁示）。

## §B 三條規範

### §B1 未知不得映成空

未選定（`not_selected`）、讀取失敗（非 ok 狀態或例外）、計數未知 ⇒ **`holdings_rows=None`，不得映成 `[]`**。
- 理由（FACT）：`[]` 會讓 coverage `unkeyed_held_count` 由 None（未知）變成 0（已知），把「不知道」偽裝成「已知沒有」（`test_norm_none_and_empty_list_are_distinguishable_in_coverage`）。
- 摘要**不得**宣稱零持股（「0 檔／無持股／空倉」等）；持股兩段與行動段只能說「無法判定」。
- coverage 的持有側計數為 None、`is_complete=False`。
- **UNKNOWN 不得視為 0／中性／SAFE**（DEC-215 §一 第 2 點「不得隱藏，不得視為 0／中性／SAFE」）：持股與相關行動段（buy_and_hold／capital_gain／actions）不得以中性、正常、安全描述未知；市場段逐字引用的 regime（如 `neutral`）不在此限（`test_norm_none_input_digest_coverage_summary_all_unknown`；對照 `test_neutral_safe_check_*`）。零持股字樣則仍掃整份摘要。
- 現況：依契約餵 None 時以上全部成立（規範測試皆綠）。

### §B2 缺獨立母體 ⇒ incomplete；無法評估列保留部位與原因

1. **缺獨立應有母體**：獨立 `expected_*` 屬 DEC-213 I3（G2 未核准 Gate），DEC-215 §五「I3 expected」只列為後續候選 Gate，皆未落地；L1 `raw` 與 `rows` 同源，不能證明「讀到的就是組合的全部」。（DEC-219 所稱「Q2 延後」是施工包 #1199 comment 7055505068 的題號，**不是** DEC-218 的 Q2。）
   因此**任何**以 L1 rows 餵入的 Digest，coverage **必須** incomplete。
   - **現況≠契約（FACT）**：四段證據齊備、每個持有列都有鍵且有行動時，`is_complete=True`（含 L1 `dropped>0` 的情形）。見 §C-6。
2. **有持有列但無法評估**（目前可實測的只有「無 `HoldingKey`」）⇒ 部位與原因必須保留。
   - **現況保留到的（FACT）**：`HoldingsSection.unkeyed_count`、`DigestCoverage.unkeyed_held_count`（逐列計數、不去重）、
     `ActionSelectionPlan.unkeyed_held_count`；holdings 變 PARTIAL、`is_complete=False`；摘要以「缺少投資組合鍵」揭露數量。
   - **差距（FACT）**：只有**計數**；部位（代號）與原因不在 Digest／coverage／摘要（`excluded_invalid_rows` 只涵蓋站內 held 異常列，與此無關）。見 §C-5。
   - 其他「無法評估」原因（行情取數失敗、過期、空白張數等 IN-U）目前在 Digest 側**沒有可承載的欄位**（INFERENCE；見 §C-8）。

### §B3 `held` 的來源

`held` 只能來自**所選單一組合**（DEC-218 Q2=(a)）中**屬持有全集（IN／IN-U，DEC-218 §一）的列**的可追溯證據。
**L1 rows 的現況不是契約**——兩個已知例外：
- **NaN／+inf 列屬 EX**（DEC-218 §一 第 5 點；§C-4）：不屬持有全集，不得以 `held=True` 進 `holdings_rows`；但 L1 現況仍把它留在 `rows`。
- **張數／均價空白列須保留為 IN-U**（DEC-218 §一 第 1 點；§C-8）：屬持有全集，不得刪；但 L1 **預設模式**現況會把它歸 `blank_value` 丟掉。

規範：
- **不得遺失**（DEC-218 §一 第 1 點：不得默默刪除、取數或評估失敗不得讓部位自母體消失）；**不得默默去重、不得重複灌水**（DEC-218 §一 第 5 點）：每個屬持有全集的來源列都要能在 `holdings_rows` 找到對應；同代號多列不得被默默吸收成一筆，單列也不得被算成多筆。
  **計數單位（列 vs 代號）未裁示**（雙母體表 §4；§C-3），本契約與規範測試**不定單位**，只要求「重複可觀測」。
- `held=True` 必須是明確 `bool`；不得由字串／數字推成 bool（現況 builder 對非 bool 的 `held` Fail Loud，FACT）。
- **來源為該組合**：不跨組合、不混 SA headless 多 Sheet 母體、不含觀察清單。
- **不由 `holding_keys` 推得**：`holding_keys` 只是「有沒有鍵」的查表，多給的代號（例：別本組合）不得變成持股或行動（現況成立，FACT）。
- **不得由 AI 推測**。
- 測試的合成 `holdings_rows` 依本條**手寫**；本文件與測試都**不**提供 tally.rows → holdings_rows 的通用轉換。

## §C 待決案例表（現況 ≠ 契約；需裁示者另列）

| # | 案例 | 目前行為（證據） | 預期（候選） | 需誰裁示 |
|---|---|---|---|---|
| §C-1 | 選定組合 0 列：組合不存在／空表／只有表頭 | L1 `status=ok`、`raw=0`、`rows=()`，僅 `other_name_rows` 不同；無法分辨「名稱打錯／改名」與「真的 0 列」（`test_current_behavior_c1_…`；既有 #1251 `test_g3_current_behavior_…`） | 候選 (i) None（無法證明組合存在 ⇒ 未知；作者推薦，fail-closed）；(ii) `[]`（來源可讀即已知 0 列）。兩者都必須：不宣稱零持股、`is_complete=False`（已由規範測試守住） | **客戶**（業務語意：「選了但 0 列」算未知或已知空；DEC-218 Q1 延伸） |
| §C-2 | L1 丟列（`dropped>0`）往下游揭露 | L1 `dropped_by_reason` 五鍵可問到；Digest／coverage 無通道（既有 strict xfail `test_desired_excluded_coverage_includes_upstream_dropped_rows`）。⚠️ 五鍵中**只有 `blank_value` 以外**（`blank_ticker`／`non_numeric`／`non_finite`／`non_positive`）才是 EX；**`blank_value` 屬 IN-U**（DEC-218 §一 第 1 點），應入 `holdings_rows`、不是「丟棄後揭露」（見 §C-8）。**ok 且 `kept==0`、且丟列中沒有 `blank_value`（無 IN-U 丟列）、也沒有其他屬持有全集的列**時，依 §B3 才可能餵 `[]`；此時摘要與餵 None **一字不差**顯示「…無法判定（尚無輸入）」（#1251 `test_b_current_behavior_digest_and_summary_identical_for_none_and_empty`）：雖不宣稱零持股，但「尚無輸入」描述不準（實為「有列、全部被剔除」）＝待決 | 丟棄數量與原因揭露到 coverage（或其後繼）；有丟棄 ⇒ incomplete；`kept==0` 時摘要措辭應能區分「全部被剔除」與「尚無輸入」 | 揭露形態＝技術（內部）；但需改 coverage／Digest schema ⇒ **另需放行**（High Gate）；`kept==0` 的摘要措辭＝待決。⚠️ **過渡期**（§A 註；客戶 #1199 7071998333，2026-11-22）：有 EX 丟列即整段 None（含 `kept==0`，此時不給 `[]`；上述可餵 `[]` 情形屬目標態）；本列揭露通道放行＝四類 EX 丟列改回 list 的前置 |
| §C-3 | 重複代號列 | L1 揭露 `duplicate_tickers`、rows 不去重；Digest 有鍵重複 ⇒ `ValueError(duplicate_holding_key)`；無鍵重複 ⇒ 計 2、與兩個不同代號逐字相同、摘要寫「另有 2 檔」（`test_current_behavior_c3_…`；`test_decision_digest_assembly.py::test_duplicate_holding_keys_fail_loud`） | 揭露重複列數與代號；不得默默去重、不得重複灌水（DEC-218 第 5 點，已裁示）。**計數單位（列 vs 代號）未裁示**（雙母體表 §4）：現況「計 2」只是 current_behavior 快照，不是規範；有鍵重複是 Fail Loud 還是揭露後保留、列數 vs 檔數用語 | 聚合粒度與公式＝**待明確技術契約**（DEC-218 第 5 點：「若尚無既有核准契約，待明確技術契約」；本裁示不授權自選公式）；是否另需客戶裁示＝推論（作者認為「列 vs 部位」屬業務語意，可能需要），未驗；揭露形態需 schema 放行。⚠️ **過渡期**（§A 註；客戶 #1199 7071998333，2026-11-22）：重複代號 ⇒ 整段 None＋固定脫敏原因碼；本列技術契約訂定並放行＝重複代號改回 list 的前置 |
| §C-4 | 非有限值（NaN／+inf 保留；-inf 丟棄） | L1 `kept_non_finite` 揭露、rows 仍含該列（DEC-219 第 4 點：只揭露、不過濾）；builder 不讀 lots ⇒ Digest／coverage／摘要與乾淨值逐字相同（`test_current_behavior_c4_…`；#1251 `test_e2_current_behavior_…`） | **歸類已定：EX**（DEC-218 §一 第 5 點「來源無效值…不得作為有效評分值；剔除須可回報」；雙母體表 §2 同為 EX）。差距在 L1 現況仍把 NaN／+inf 保留於 rows | 不是歸類裁示；**NaN／+inf 過濾修補屬 DEC-219 明列 HOLD 項的放行問題**（放行者依 DEC-219 HOLD，該條未指明）；下游回報形態需 schema 放行。⚠️ **過渡期**（§A 註；客戶 #1199 7071998333，2026-11-22）：保留列含 NaN／+inf ⇒ 整段 None；可逐列辨識（本 HOLD 項放行或快照逐列旗標）＝改回 list 的前置 |
| §C-5 | 無法評估列的部位與原因 | 只有計數（`unkeyed_count`／`unkeyed_held_count`）；代號與原因不在輸出（`test_gap_unevaluable_row_identity_and_reason_preserved`） | 每個 IN-U 部位可追溯（身分＋原因），隱私呈現方式另定 | 欄位形態需 **schema 放行**；對使用者呈現另過 UI 線框 Gate |
| §C-6 | 缺獨立應有母體 | 四段齊備＋全部有鍵有行動 ⇒ `is_complete=True`（`test_gap_contract_fed_input_without_independent_universe_must_be_incomplete`） | `is_complete=False`，直到有獨立 expected（DEC-213 I3，G2 未核准 Gate；DEC-215 §五「I3 expected」） | 獨立 expected＝**DEC-213 I3 的 G2 Gate**（客戶獨立授權）；coverage 改法需 schema 放行 |
| §C-7 | `holdings_rows` 內 `held` 缺／None／False 的列 | 被當「非持有」，coverage 無欄位，`is_complete` 不受影響、代號不出現（`test_current_behavior_c7_…`） | 依 §B3 adapter 不應產生此類列；若出現，是否須揭露／Fail Loud | 技術（內部），但 coverage 加欄位需 schema 放行 |
| §C-8 | 張數／均價空白（IN-U） | 預設模式歸 `blank_value` 丟棄；`keep_blank=True` 保留為 None，但 Digest 無 IN-U 標記、與乾淨列逐字相同（`test_current_behavior_c8_…`） | 「保留為 IN-U、不得刪」**已裁示**（DEC-218 §一 第 1 點）。待決只剩：(a) IN-U 在 Digest／coverage 的標示方式；(b) L1 預設模式現況會丟空白列（與裁示的差距；`keep_blank=True` 才保留） | (a) IN-U 標示需 schema 放行；(b) adapter 用哪個模式＝技術（不得選會丟列的模式）。⚠️ **NOT VERIFIED**：真實 gspread 讀到的空白格可能被轉成 0 而落入 `non_positive`、不是 `blank_value`（#1242 P2；雙母體表 §2 末條），本批只以合成資料驗證，真實 Sheet 未讀。⚠️ **過渡期**（§A 註；客戶 #1199 7071998333，2026-11-22）：預設模式 `blank_value` 丟列 ⇒ 整段 None，且**永不改 list**（無從還原）；正式接線須用保留空白值模式（(b)） |
| §C-9 | 讀取例外（`LoginRequiredError` 等） | L1 原樣上拋，不入快取（#1251 `test_g4_…`；`test_norm_l1_login_required_never_becomes_a_tally`） | 上拋到呼叫端（不建 Digest），或 L3 捕捉後以 None＋原因降級；⛔ 不得映成 `[]` | 技術（L3 adapter Gate；adapter 本身未授權） |
| §C-10 | 時點／新鮮度 | `PortfolioReadTally` 與 `holdings_rows` 都不帶 `fetched_at`／`as_of`；L1 讀取有 `TTL_15MIN` 快取（`_load_portfolio_tallied_cached`），餵入時無法得知持股讀取的時點；Digest 持有側只有站內證據戳 | 持股讀取帶可追溯時點（至少 fetched_at）；過期須能標示且不自動算已評估 | 過期標示語意已由 DEC-218 §一 第 4 點裁示；列層級 as_of／代表 stamp＝DEC-213 I6「未決（G2 邊界）」⇒ **客戶 G2 Gate**；欄位需 schema 放行 |

**注意**：上表「目前行為」欄由 `current_behavior` 測試釘住，**不是**「這是對的」。轉紅時依各測試 docstring 處置：更新本表與快照、記錄裁示；
`test_gap_*` 若 XPASS，代表缺口被改掉，須升為正式斷言並同步本表。規範測試（`test_norm_*`）不依賴任何快照。

## §D 範圍與不授權事項

- 本文件**不是 adapter 實作**。正式 L3 adapter、Digest schema（含 coverage 新欄位）、任何 production caller、私人 Sheet／OAuth 讀取、真 Provider，**各自另需放行**。
- 本批只新增兩個檔（本文件與 `tests/test_onebrain_holdings_input_contract.py`）；`src/`、`shared/`、既有測試與 DECISIONS／HANDOFF／PROJECT_STATE／BACKLOG **0 改動**。
- 測試內的 `contract_expected_holdings_input` 只輸出「預期輸入類別」，是契約規格表，**不得**被 production 引用（有守衛）。
- **L1 可用、Digest NOT READY**；OneBrain 正式廣度 NOT EVALUATED。

## §E NOT VERIFIED

- 單組撰寫與自測；兩組非作者 QA、PR exact-head CI、0 unresolved threads 均未完成。
- §A／§C 的「目前行為」只以合成資料驗證；真實 Sheet 的 gspread 數值轉換、真實 `holding_keys` 來源（`portfolio_id` 仍無正式來源）未驗。
- §C-1 推薦 (i) 與 §C 各列「需誰裁示」為作者判斷，未經第二組驗證。
- 「其他無法評估原因在 Digest 側沒有可承載欄位」（§B2-2 末句）為 INFERENCE，未窮舉 Digest 所有欄位語意。
- 2026-11-22 修訂（§A 第 9–12 列標註、§A 註、§C-2／§C-3／§C-4／§C-8 交叉引用）為單組撰寫，未經第二組驗證；「§A 註」逐型解除前置是依 #1199 7071998333 與 7071883974 的轉述整理，非客戶逐字條文；Draft #1258 原因碼名稱僅供參考（未合併）；「四段齊備時剔除後 list 會 `is_complete=True`」引自 7071883974 合成案例實跑，本次未重跑。

## §F 版本／變更紀錄

| 日期 | 變更 | 依據 |
|---|---|---|
| 2026-11-21 | 初版：契約設計＋離線驗收案例對照（量測基準 main `29594c5a`） | #1199 comment 7060205009 |
| 2026-11-22 | §A 第 9–11 列 list 改標**目標態 list**（舊表述刪除線保留）、第 12 列補預設模式過渡期；新增「§A 註（過渡期）」：過渡期整段 None、固定脫敏原因碼、逐型解除前置、目標態與 Gate 邊界；§C-2／§C-3／§C-4／§C-8 加交叉引用；§E 補未驗事項。本檔以外 0 改動（測試、adapter、DECISIONS／BACKLOG／HANDOFF 未動）。量測基準 main `2c6d9081` | 客戶正式裁示 #1199 comment 7071998333；分析 7071883974（C-EX-CONTRACT-DOCS-IMPLEMENT-1；docs-only） |
