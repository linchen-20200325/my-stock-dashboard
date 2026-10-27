# D2.5 AB-4r：策略分類唯讀契約 —— 規格與決策紀錄（2026-10-27）

> 計畫出處：`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 序 5（AB-4r）。
> 規格由 AI 總管拍板，實作組依規格落地；本文件記錄決策、理由與已知限制。
> ⚠️ 本文件與程式由實作組單組產出；下列「已知限制」以外的全稱宣稱，在獨立複驗前屬待驗事項（CLAUDE.md §-2 規則 6）。

## 1. 範圍

**做**：策略分類的**唯讀**契約 —— `portfolio_id` 的來源、持股鍵的組法、`strategy_class` 分頁的解析規則、L1 唯讀 reader。

**不做**（硬邊界）：寫入、建分頁、UI、`app.py`、`shared/ia_nav.py`、接進 AB-1 builder、
改 AB-0／AB-1／AB-2a 任何檔（`shared/decision_digest*.py`、`src/services/decision_digest_*.py`）、
新增 streamlit import、新增 scope／credential。現有 `portfolios` 分頁 5 欄表頭完全不動（策略放獨立分頁）。

## 2. 檔案與公開 API

| 層 | 檔案 | 公開 API |
|---|---|---|
| L0 | `shared/strategy_class_schema.py` | 常數 `STRATEGY_WORKSHEET_NAME`、`STRATEGY_HEADERS`、`PORTFOLIO_ID_PREFIX`、`PORTFOLIO_ID_HEX_LEN`、`STRATEGY_SOURCE`、`STATUS_*`、`INVALID_*`；`derive_portfolio_id`、`build_holding_keys`→`HoldingKeysResult`、`parse_strategy_records`→`StrategyReadResult`、`lookup`、`empty_result`、`InvalidRow`、`StrategySchemaMismatchError` |
| L1 | `src/data/portfolio/gsheet_portfolio.py`（**加法**） | `read_worksheet_values(worksheet_name, *, sheet_id) -> list[list]` |
| L1 | `src/data/portfolio/strategy_class_reader.py` | `read_strategy_classes(*, sheet_id) -> StrategyReadResult` |

## 3. `portfolio_id`

`derive_portfolio_id(sheet_id, portfolio_name)` ＝ `"pfv1-"` ＋ `sha256((sid + "\x00" + name).encode("utf-8")).hexdigest()[:20]`

- `sid = sanitize_sheet_id(sheet_id)`（全 repo 唯一 Sheet ID parser）。
- `name = portfolio_name.strip()` —— **與 `gsheet_portfolio` 篩組合的方式逐條相同**（查證：
  `_list_portfolios_names` 用 `str(rec['name']).strip()`；`load_portfolio` 先 `name.strip()`，
  `_load_portfolio_rows` 再以 `str(r['name']).strip() == name` 逐字比對；`name` 欄屬 `_TEXT_COLS`，保留原字串）。
  ⛔ 不做 NFKC、不做大小寫折疊、不動中間空白 —— 否則兩個在 gsheet 看來不同的組合會被併成同一個 pid。
- 任一為空、非 str、或 sid 消毒不過 → `ValueError`（⛔ 不退回任何預設 Sheet）。
- NUL 分隔：sid 字母集 `[A-Za-z0-9_-]` 不含 NUL ⇒ (sid, name) 與雜湊輸入一一對應。
- 結果字元只有 `[a-z0-9-]` ⇒ 通過 AB-0 `_key_problem`（以 `HoldingKey` 建構驗證）與 AB-2a
  `has_forbidden_char`（測試覆蓋）。

### 3.1 候選比較

| 候選 | 寫入？ | 優點 | 缺點 | 判定 |
|---|---|---|---|---|
| A. sheet_id＋名稱原文直接拼接 | 否 | 可讀 | 鍵含使用者原文（含空白／全形／控制字元時 AB-0 `_key_problem` 直接拒收）；把 Sheet ID 全文帶進 Digest 與 AI 輸入面（違 Q4「只露末 6 碼」精神） | ✗ |
| **B. sha256(sid＋NUL＋name) 截 20 hex（加版本前綴）** | **否** | 決定性、字元集固定必過 AB-0／AB-2a、不外洩 ID 與名稱、不同 Sheet 同名自然分開 | 改名／換 Sheet → pid 變（見 §6） | **✓ 採用** |
| C. 只用名稱 | 否 | 換 Sheet 不變 | 不同 Sheet 同名組合互撞（雙通道／多本 Sheet 時錯配策略 ＝ 錯誤數字）；名稱原文同 A 的字元問題 | ✗ |
| D. 新增 ID 欄（`portfolios` 加欄或另存） | **是** | 改名不變 | 需寫入 Sheet ＝ HI-5 寫入面（AB-4w Gate）；且動 `portfolios` 表頭違反「現有 5 欄不得破壞」 | ✗（超出唯讀範圍） |
| E. Sheets developerMetadata | **是** | 對使用者不可見、改名不變 | 需寫入 API 與 scope 審查（HI-5），讀取也要額外 API 呼叫 | ✗（超出唯讀範圍） |

**選 B 的理由**：唯讀批次唯一同時滿足「零寫入、決定性、鍵字元必合法、不同 Sheet 不互撞、不外洩識別原文」者。
版本前綴 `pfv1-` 讓日後若改演算法（例如 AB-4w 改用 D/E）時新舊 id 不會互撞。

## 4. `build_holding_keys`

`build_holding_keys(*, sheet_id, portfolio_name, tickers) -> HoldingKeysResult(keys, rejected)`

- `keys`：ticker **原字串** → `HoldingKey(pid, ticker)`（`MappingProxyType`；對接 AB-1 builder 的
  `holding_keys: Mapping[str, HoldingKey]` —— builder 要求 `k.symbol == ticker`，故不得改寫 ticker）。
- `rejected`：`HoldingKey` 建構失敗的 ticker（保序去重；⛔ 不補鍵、不改寫）。
- ⛔ 不預先套 AB-2a 的 `SYMBOL_PATTERN`：那是 AB-2a validator 的 fail-closed 關卡；這裡先濾會把它遮住。
- ticker 非 str、或 `tickers` 是單一字串 → `TypeError`（規格未明示；Fail Loud，⛔ 不 `str()` 轉換 —— `50.0` 不是 `0050`）。

## 5. `strategy_class` 分頁解析

分頁 `strategy_class`，表頭 `name | ticker | strategy | updated_at`。

| 規則 | 行為 | 理由 |
|---|---|---|
| 沒有任何列 / 整張表空白 | `status="ok"`、0 entries | 分頁存在只是沒人填；與 `gsheet_portfolio._header_state` 對空表回 EMPTY 一致。日後寫入面建分頁時一次寫上表頭 |
| 第一列從 A 欄起逐字等於 `STRATEGY_HEADERS` | OK；右側自加欄允許 | 比照 `_header_state` |
| 表頭不符 / 本分頁欄名重複 / 第一列空白但下面有資料 | L0 拋 `StrategySchemaMismatchError`；L1 reader 轉成 `gsheet_portfolio.SheetSchemaMismatchError`（`__cause__` 保留） | L0 不得 import L1；轉型後 `classify_read_error` 能判成 `schema_mismatch`，與其他分頁讀取同一型別（「沿用現有錯誤型別」） |
| ⚠️ 窄表頭（只有前段欄位） | **判不符** | **刻意與 `_header_state` 不同**：`strategy` 是唯一資料欄，沒有它就沒有內容可讀；`updated_at` 缺也判不符以維持規格「等於 STRATEGY_HEADERS 才 OK」 |
| 全空白列 | 略過 | 同 gsheet |
| name／ticker／strategy 任一格非 str 且非 None（NaN、數字、bool） | `invalid_rows`：`non_text_cell` | ⛔ 不 `str()` 轉換；`updated_at` 不使用、不檢查 |
| name 空 / ticker 空 | `missing_name` / `missing_ticker` | |
| strategy：strip → NFKC → 必須**恰好**是「存股／資本利得／未分類」 | 否則 `bad_strategy`（含空、`ＢＵＹ`、`HOLD`、emoji） | ⛔ 不默默當未分類（那會把使用者的錯字講成「沒設定」） |
| ticker 只 strip | 與 `parse_portfolio_records` 的 `str(rec['ticker']).strip()` 一致 | |
| pid＝`derive_portfolio_id(sheet_id, name)`；`HoldingKey` 建不出 | `bad_key` | 例：全形「２３３０」、中間空白 |
| 同鍵多列同值 | 去重 | |
| 同鍵不同值（**含「未分類」vs 其他**） | 記入 `conflict_keys`，該鍵不入 entries（讀成未分類） | ⛔ 不擇一 |
| 「未分類」列 | 合法、不入 entries | AB-0：未分類時 `strategy_source` 必須 None |

`invalid_rows` 為 `InvalidRow(row, reason)`：row＝Sheet 列號（1-based，表頭＝1），reason＝代碼；⛔ 不回顯格子內容。

`StrategyReadResult(status, entries, invalid_rows, conflict_keys)`（frozen）：status ∈ {`ok`, `worksheet_missing`, `not_bound`}；
entries 為 `MappingProxyType`，只含 `存股／資本利得`；非 ok 時不得有任何內容（`__post_init__` 檢查）。
`lookup(result, key)`：查無 → `未分類`；key 非 `HoldingKey` 或 result 型別錯 → `TypeError`。
有分類時 `HoldingEntry.strategy_source` 用 `STRATEGY_SOURCE = "google_sheet:strategy_class"`（測試證明通過 AB-0 檢查）。

## 6. L1 reader 與讀取函式

`read_strategy_classes(*, sheet_id)`：
- `sanitize_sheet_id` 後為空（含 None）→ `not_bound`（不打 Google）；非 str 且非 None → `TypeError`。
- 經 `gsheet_portfolio.read_worksheet_values`（**新增、加法式**；只開不建 `_ws` → `get_all_values()`）：
  分頁不存在 → `worksheet_missing`（⛔ 不建）；未登入／權限／網路／找不到 Sheet 原樣上拋。
- `read_worksheet_values` 沿用既有本人 OAuth client（`_build_client`）、身分隔離快取（`_identity_scoped_read`，
  TTL_15MIN，鍵含身分指紋＋sheet_id＋worksheet_name＋B5 失效世代）與錯誤型別；sheet_id 必填（⛔ 不退回 session 那本）。
- `gsheet_portfolio.py` 只新增 46 行，既有函式一行未改。

## 7. 已知限制（據實）

1. **改名或複製 Sheet → pid 變 → 讀成未分類**（fail-safe：最壞是「沒分類」，不會錯配到別的組合）。
2. **AB-4r 沒有寫入面**：production 上沒有任何東西會建 `strategy_class` 分頁或寫值，故目前讀到的一律是
   `worksheet_missing`／空／未分類，直到 AB-4w（HI-5）落地。
3. **雙通道**：呼叫端必須固定傳**綁定的那本** sheet_id（`session_binding_snapshot()`），reader 不自行挑通道；
   若 ETF／個股兩通道指向不同 Sheet，同名組合會得到不同 pid（設計如此）。
4. **截短碰撞**：20 hex ＝ 80 bit；生日界約 n²／2⁸¹，10⁶ 個組合時碰撞機率約 4×10⁻¹³，視為可忽略；
   碰撞的後果是兩組合共用策略分類（不是錯誤數字），且換前綴即可升級。
5. **全域 `clear_read_cache()` 不清本快取**：改它＝改既有函式行為（規格禁止）。本快取由 B5 失效世代
   （`invalidate_my_read_cache`／`invalidate_sheet_read_cache`）或 TTL 失效；寫入後失效由 AB-4w 負責。
6. `read_worksheet_values` 未列入 `tests/test_sheet_safety_guards.py` 的 `_READ_ENTRIES`（未改既有測試檔）；
   其零寫入閉包檢查改寫在 `tests/test_strategy_class_reader.py`（沿用該檔的 AST 工具）。
7. 本批**不接 builder**：`build_holding_keys` 的結果如何傳進 `build_decision_digest(holding_keys=...)`、
   由誰在 L3 取得 binding sheet_id 與組合名，屬接線批次。
