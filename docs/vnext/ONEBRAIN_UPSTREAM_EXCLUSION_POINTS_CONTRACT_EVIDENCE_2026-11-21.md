# OneBrain 上游剔除點契約證據表（G-X2；docs＋tests-only；2026-11-21）

> **性質**：缺口**證據**與待決問題清單。**不是規範、不是設計、不是授權。**
> **授權**：Issue #1199 總管裁示 G-X2（comment 7052927599，裁示一）。DEC-215 語意**原樣不動**；本文件不改寫它、不宣稱完整母體已有實作。
> **量測基準**：main `c7be5eb909cbeec19e84c5b35e99b13797d3957f`；行號量測日 2026-11-21（會漂移，以符號為準；漂移守衛見 `tests/test_onebrain_upstream_exclusion_gap_evidence.py`）。
> **標記**：FACT＝原始碼可直接核對；INFERENCE＝由 FACT 推得、含未驗條件；NV＝NOT VERIFIED。
> **不變**：OneBrain NOT READY（0 production caller）；正式廣度 NOT EVALUATED；G-X1 **未授權**；本文件不放行 Digest v2／Stage F／任何 Provider。

## 1. 剔除點表（持股原始資料 → 解析 → 持股 → 戰情列 → action rows）

| # | 位置（file:符號，行號） | 原因類別 | 是否回報計數 | 計數消失層 | 範圍 | 標記 |
|---|---|---|---|---|---|---|
| P0 | `src/data/portfolio/gsheet_portfolio.py:_load_portfolio_rows`（928–934） | 其他組合／`name` 空白或不符之列，不進解析 | 否 | 此層（L1） | 全 Sheet 其他組合；屬「選定組合」定義而非資料異常 | FACT |
| P1 | 同檔 `parse_portfolio_records`（803–834）：空代號 `continue`（820–821） | 空代號 | **否** | L1 | 選定組合內 | FACT |
| P2 | 同函式預設路徑：`float(x or 0)`、`lots<=0 or avg<=0`（829–834） | 空白格（讀成 0）、0、負數 | **否** | L1 | 選定組合內 | FACT |
| P3 | 同函式 `except (TypeError, ValueError): continue`（831–832） | 非數字（如 `'abc'`） | **否** | L1 | 選定組合內 | FACT |
| P4 | 同函式 `keep_blank=True` 分支（822–827） | 只放寬「空白格」（回 `None`＝缺值，非 0）；有填值但不可用者與空代號照丟 | **否** | L1 | 選定組合內；`keep_blank` 為加性參數，預設行為不變 | FACT |
| H1 | `src/services/holdings_service.py` 持有列組裝：`if not _tk: continue`（293–294） | 空代號（解析層已先擋，實務多為冗餘守衛） | 否 | L3 | 持有列 | FACT；「實務冗餘」為 INFERENCE |
| H2 | 同檔觀察清單：`if not _tk or _norm(_tk) in _seen: continue`（337–338） | 空代號／與持有或觀察清單重複（去重） | 否 | L3 | 僅影響 `held=False` 列 | FACT |
| S1 | `src/services/dividend_station_service.py:build_station_rows`（400；空代號 `continue` 437–438） | 空代號（含純空白） | 否（無列、無錯誤列） | L3 | holdings 清單內 | FACT |
| S2 | 同函式：非空代號單檔 `metrics_fn` 例外 | **不剔除**：產 `_error_row`（帶 `_detail.error`） | 由下行 D1 計入 | — | — | FACT（見測試 `..._nonblank_ticker_always_gets_a_row`） |
| D1 | `src/services/decision_digest_builder.py:_scan_action_rows`（335；異常旗標 365–367、`_detail.error` 368–371） → `plan_action_selection` → `DigestCoverage.excluded_invalid_rows`（`decision_digest_assembly.py` 358–362） | **held** 且 `_invalid_lights`／`_invalid_inputs`／`_detail.error` | **是（唯一）** | 回報至 coverage | 僅「已進 station_rows 的 held 異常列」 | FACT |
| D2 | 同函式其他分支 | 非 Mapping／非 held（`not_held`）／未知行動碼（`unrecognized`）／premium·cruise 非行動列（`non_action`）／對不上持股鍵（`unmatched`） | 是（各自互斥欄位，非 `excluded_invalid_rows`） | coverage | 已進 station_rows 的列 | FACT |

## 2. `excluded_invalid_rows` 實際覆蓋與不覆蓋

- **覆蓋（FACT）**：已進 `station_rows`、`held` 為真、且帶 `_invalid_lights`／`_invalid_inputs` 非空或 `_detail.error` 的列。
- **不覆蓋（FACT）**：P1–P4（L1 解析丟棄）、P0、H1／H2、S1（空代號）；非 held 異常列（歸 `station_not_held_rows`）；`unmatched`／`unrecognized`／`non_mapping`（互斥的其他分類）。
- 測試重現：`test_current_behavior_excluded_invalid_rows_counts_only_held_invalid_station_rows`、`..._rows_dropped_by_parse_are_invisible_...`。

## 3. 已知完整性缺口

1. **L1 預剔除無痕**（FACT）：同一份 7 筆合成列，預設路徑只剩 1 筆（`keep_blank=True` 剩 3 筆），回傳純 list，無 raw／dropped 計數。
2. **station 由 holdings 派生，對帳可能恆等**（INFERENCE）：`build_station_rows` 對非空代號一對一產列，故 holdings↔station 的 `holdings_without_station_row` 在 L1 丟失後仍可為 0（測試以合成資料佐證此現象）。**成立條件 NV**：各呼叫端是否傳同一份 holdings、ticker 大小寫／空白正規化是否一致，未逐一檢查。
3. **空代號 `continue` 三處**（P1／H1／S1）皆無痕（FACT）。
4. **名稱過濾**（P0）決定「哪些列算本組合」，其母體定義不由任何計數揭露（FACT）。
5. **觀察清單去重**（H2）靜默（FACT），僅影響 `held=False`。

## 4. 與 DEC-215 的對照（不改寫其語意）

- DEC-215 要求排除列「另行揭露數量與原因」且基準取在預剔除之前（依 #1199 comment 7052632346 之轉述；以 DEC-215 原文為準）。目前 `excluded_invalid_rows` 只涵蓋 D1 一小部分，且 `actions_total_eligible` 取在預剔除**之後**（FACT：`decision_digest_builder.py` 546 → `decision_digest_assembly.py` 358），**不滿足**該揭露要求；**完整母體尚無實作**。
- 本文件與測試只釘現況與不足；不主張現況為正確規範。

## 5. 「可評分」資格判準：**NOT VERIFIED**

- DEC-215 所指「既有、正式核准之可評分資格判準」的實作映射＝**NOT VERIFIED**。已知相近術語（`actions_total_eligible`、`scoring_eligible`、`_is_scorable`、`is_trend_scorable`）**皆不等同**全域「可評分持股全集」，不得擇一冒充（依 #1199 comment 7052632346）。
- 「統一資格判準」須由獨立 Decision Gate 決定；本文件**不**創造資格條件、**不**新增資格欄位、**不**指定函式。

## 6. 待決問題（僅列，不裁決）

1. DEC-215 指的既有判準是哪一份，或確認尚無統一定義？
2. 上游丟棄的揭露應落在哪一層、以何種形態（不在此指定）？
3. 完整性宣稱所需的**獨立** expected 來源是什麼（G-X1 的 L1 內部 raw→kept **不是**獨立 expected，且**未授權**）？
4. 對帳兩側同源問題（缺口 2）的條件核對由誰、用什麼證據完成？

## 7. 測試對照

`tests/test_onebrain_upstream_exclusion_gap_evidence.py`：`test_current_behavior_*` 釘現況（缺口證據，非規範）；`test_desired_*` 為 `xfail(strict=True)` 期望改善；另含剔除點存在性守衛，避免文件漂移。資料全為匿名合成與公開代號，不含任何私人持股或 Sheet 內容。

## 8. 狀態註記（C-OB-GX1-L1-ADDITIVE-TALLY-1；追加，上文不改）

- **L1 計數已實作（dormant）**：`gsheet_portfolio.tally_portfolio_records` / `load_portfolio_tallied` / `PortfolioReadTally`（見 DEC-219）。僅 L1 純加性、0 production caller、全合成資料測試；`parse_portfolio_records` / `load_portfolio` 判定未改；NaN／+inf 只揭露不改判；不去重。對應測試 `tests/test_onebrain_gx1_l1_tally.py`。第 1 節表中 `parse_portfolio_records` 列「是否回報計數＝否」對**該函式本身**仍成立（仍回純 list）；新 API 是並列的另一條讀取路徑。
- **L3 缺口未解**：`test_desired_excluded_coverage_includes_upstream_dropped_rows`（期望 `excluded_invalid_rows == 6`）**仍保留 `xfail(strict=True)`**——L3 / 戰情表 / Digest 沒有任何接線，缺口 2 與缺口 3 原樣存在。原 L1 層 xfail 已有意識改寫為正式測試 `test_l1_tally_reports_dropped_count_and_reasons`，不是刪除。
- 單組撰寫，未經獨立 QA；OneBrain 仍 NOT READY，廣度 NOT EVALUATED。
