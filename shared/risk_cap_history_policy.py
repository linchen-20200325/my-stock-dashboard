"""shared/risk_cap_history_policy.py — 每日系統風險上限「系統歷史紀錄」的 schema／狀態詞彙 SSOT（L0）。

═══ 為什麼有這個檔（VN1-STORE 最小 PoC，客戶 2026-10-19 裁示 A）═══════════════════════
客戶裁示：採用「系統專用 Google Sheet」作為每日 System Risk Cap 歷史紀錄的持久化位置，
**但先做最小 PoC、尚未核准正式 production 排程寫入**。本檔只定「一列紀錄長什麼樣、狀態叫什麼」，
⛔ 不含任何門檻、⛔ 不新增投資語意：

- 欄位**只**取自既有快照欄位（`risk_cap_apply` 寫進 `risk_cap_state.json` 的鍵）與 provenance
  （何時寫、哪一次 run、哪個 commit）；
- 狀態詞彙**只**對映既有判定（`risk_cap_apply.REASON_*`、`get_macro_state(require_valid_risk_cap=True)`
  的收件條件、`macro_refresh_service` 的抓取步驟成敗）；
- ⛔ 沒有「變動多大才算變」的門檻（DEC-062：不得自行新增變動大小門檻）；
- 有效期沿用既有 `shared.staleness.MACRO_VERDICT_MAX_AGE_DAYS`（判定函式在 L3
  `macro_state_locker.macro_state_is_expired`，本檔不重寫）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫，被 L1（`src/data/macro/risk_cap_history.py`）
與 L3（`src/services/risk_cap_history_service.py`）import。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

#: 紀錄 schema 版本（欄位增刪 ⇒ 升版；⛔ 只增不改，舊列不改寫）。
HISTORY_SCHEMA_VERSION: str = "risk_cap_history.v1"
# （稽核修正 2026-10-19 加 `core_input_provenance` 一欄仍標 v1：v1 尚未有任何一列落地到真實 Sheet。）

#: 系統歷史 Sheet 內的工作表名稱。
#: ⚠️ 這本 Sheet 與個人持股 Sheet **完全分離**（客戶裁示第 4 點）：⛔ 不得把本工作表開在使用者的持股 Sheet 裡。
HISTORY_WORKSHEET_NAME: str = "risk_cap_daily"

# ══════════════════════════════════════════════════════════════════════
# 欄位（順序即 Sheet 欄序；第一列為表頭，讀端逐字比對）
# ══════════════════════════════════════════════════════════════════════
COL_RECORD_DATE = "record_date"            # 本輪計算的台北日期（`bundle_summary.today`）＝ 冪等鍵之一
COL_RULESET_VERSION = "risk_cap_ruleset_version"   # 冪等鍵之二；比較只比同版本
COL_STATUS = "status"                      # 下方 STATUS_*
COL_REASON_CODE = "reason_code"            # 下方 REASON_CODE_*（機器讀）
COL_REASON_DETAIL = "reason_detail"        # 既有 `RiskCapApplyResult.reason` 原文（⛔ 不放例外訊息，防外洩）
COL_EXPOSURE_LIMIT_PCT = "exposure_limit_pct"      # **只有 VALID 才有值**；其餘一律空白（⛔ 不補 0）
COL_REQUIRED_CORE_OK = "required_core_ok"  # 快照欄位原值（VALID ⇒ TRUE；未寫檔 ⇒ 空白）
COL_MISSING_CORE = "missing_core"          # `RiskCapApplyResult.missing_core`（逗號分隔鍵名）
COL_NOT_EVALUATED = "not_evaluated"        # 未評估（缺項不計分）的輸入鍵（逗號分隔）
COL_DISABLED_INPUTS = "disabled_inputs"    # 規則停用、不計分的輸入鍵（≠ 未評估）
COL_INPUT_ASOF = "input_asof"              # 各輸入的資料日（JSON，鍵排序）—— 判斷「是不是同一份資料」用它
COL_ENGINE_SOURCE = "engine_source"        # `risk_cap_apply.ENGINE_SOURCE`
COL_SNAPSHOT_TIMESTAMP = "snapshot_timestamp"      # 快照自己的 timestamp（台北時間；有效期 7 天由它判）
#: 稽核修正（2026-10-19）：Required Core 各輸入的 provenance（JSON）——
#: `{鍵名: {"source": 既有 L2 `DatedValue.source` 原文, "upstream_is_stale": True/False/"unknown"}}`。
#: `upstream_is_stale` **只**取上游 dict 自帶的 `is_stale` 布林；
#: 2026-10-19 複稽核更正（有意識的變更，不是漏刪）：舊註「L1 `macro_core` 的 stale-cache 退路會蓋 True」只對
#: **台灣 PMI 當月**成立（多源全失敗 → 讀上次已知值快照時才設 True；即時命中時不帶此欄）；
#: **VIX 上游（`macro_snapshot.fetch_vix_block`）從不帶 `is_stale`** ⇒ VIX 此欄恆為 "unknown"。
#: 上游沒有這個欄位 ⇒ "unknown"（⛔ 不以缺欄推定 False、⛔ 不另判新鮮度）。有效性判定與此欄無關。
COL_CORE_INPUT_PROVENANCE = "core_input_provenance"
COL_REFRESH_OK = "refresh_ok"              # 這一輪整條更新鏈是否全部成功（`MacroRefreshReport.ok`）
COL_REFRESH_FAILED = "refresh_failed"      # 失敗的來源／步驟**內部鍵名**（逗號分隔；⛔ 不放 detail 原文）
COL_WRITTEN_AT_UTC = "written_at_utc"      # 本列產生時刻（UTC ISO8601）—— provenance，⛔ 不當資料日
COL_RUN_ID = "run_id"                      # GitHub Actions run id；本機為 "local"
COL_GIT_SHA = "git_sha"                    # 產生本列的程式版本（取不到留空，⛔ 不編造）
COL_SCHEMA_VERSION = "schema_version"      # = HISTORY_SCHEMA_VERSION

HISTORY_COLUMNS: tuple[str, ...] = (
    COL_RECORD_DATE, COL_RULESET_VERSION, COL_STATUS, COL_REASON_CODE, COL_REASON_DETAIL,
    COL_EXPOSURE_LIMIT_PCT, COL_REQUIRED_CORE_OK, COL_MISSING_CORE, COL_NOT_EVALUATED,
    COL_DISABLED_INPUTS, COL_INPUT_ASOF, COL_ENGINE_SOURCE, COL_SNAPSHOT_TIMESTAMP,
    COL_CORE_INPUT_PROVENANCE, COL_REFRESH_OK, COL_REFRESH_FAILED, COL_WRITTEN_AT_UTC, COL_RUN_ID, COL_GIT_SHA,
    COL_SCHEMA_VERSION,
)

#: 冪等鍵：同一個台北日期 × 同一個規則版本。
IDEMPOTENCY_KEY_COLUMNS: tuple[str, ...] = (COL_RECORD_DATE, COL_RULESET_VERSION)

#: 「內容」欄位：同鍵重跑時拿來判斷「是不是同一份結果」。
#: ⛔ 不含 provenance（寫入時刻、run id、commit、快照 timestamp、整輪成敗、來源標籤）——
#: 同一份資料在不同時刻重跑，provenance 必然不同，若算進來就永遠判成「內容不同」。
#: 稽核修正（2026-10-19，有意識的變更）：加入 `reason_detail` —— 「核心輸入已過期」與「核心輸入未取得」
#: 同屬 REQUIRED_CORE_INCOMPLETE，只有原因原文分得出來；不比它會把兩個不同的事實當成重跑而吞掉。
CONTENT_COLUMNS: tuple[str, ...] = (
    COL_STATUS, COL_REASON_CODE, COL_REASON_DETAIL, COL_EXPOSURE_LIMIT_PCT, COL_REQUIRED_CORE_OK,
    COL_MISSING_CORE, COL_NOT_EVALUATED, COL_DISABLED_INPUTS, COL_INPUT_ASOF, COL_ENGINE_SOURCE,
)

# ══════════════════════════════════════════════════════════════════════
# 紀錄狀態（一列的「資料狀態」）—— 全部對映既有判定，⛔ 不新增投資語意
# ══════════════════════════════════════════════════════════════════════
#: 這一輪寫出快照，且官方讀端 `get_macro_state(require_valid_risk_cap=True)` 收得下它的上限。
STATUS_VALID = "VALID"
#: `risk_cap_apply.REASON_CORE_MISSING`：Required Core 任一無法評估（含「已過期」——既有規則把
#: 非 FRESH 的核心輸入一律當無法評估；是過期還是未取得，見 `reason_detail` 原文）。
STATUS_REQUIRED_CORE_INCOMPLETE = "REQUIRED_CORE_INCOMPLETE"
#: `risk_cap_apply.REASON_FAIL_SAFE`：啟用中的數值輸入全部無法計分 → 引擎 fail-safe。
STATUS_ENGINE_FAILSAFE = "ENGINE_FAILSAFE"
#: `risk_cap_apply.REASON_NOT_FINITE`：引擎回的上限不是有限數。
STATUS_ENGINE_NOT_FINITE = "ENGINE_NOT_FINITE"
#: `macro_refresh_service.STEP_FETCH` 整條失敗（抓取鏈拋例外，後續步驟全部沒跑）。
STATUS_FETCH_FAILED = "FETCH_FAILED"
#: `STEP_RISK_CAP` 本身拋例外（取值／引擎／JSON 檢查／寫檔）。
STATUS_COMPUTE_ERROR = "COMPUTE_ERROR"
#: 寫出了快照，但官方讀端不收（理論上不該發生；發生即代表寫端與讀端契約不一致）。
STATUS_SNAPSHOT_REJECTED = "SNAPSHOT_REJECTED"
#: 稽核修正（2026-10-19）：同日已有 VALID、本輪又算出內容不同的 VALID ⇒ 首筆不動，本輪結果以這個狀態
#: **另記一列**（`exposure_limit_pct` 空白、差異寫在 `reason_detail`）。⛔ 不是有效紀錄、讀端不拿它比較。
STATUS_SAME_DAY_CONFLICT = "SAME_DAY_CONFLICT"

RECORD_STATUSES: tuple[str, ...] = (
    STATUS_VALID, STATUS_REQUIRED_CORE_INCOMPLETE, STATUS_ENGINE_FAILSAFE, STATUS_ENGINE_NOT_FINITE,
    STATUS_FETCH_FAILED, STATUS_COMPUTE_ERROR, STATUS_SNAPSHOT_REJECTED, STATUS_SAME_DAY_CONFLICT,
)

#: 機器讀的原因碼（與 status 一對一或更細；VALID 時為空字串）。
REASON_CODE_NONE = ""
REASON_CODE_CORE_MISSING = "core_missing"
REASON_CODE_FAIL_SAFE = "engine_fail_safe"
REASON_CODE_NOT_FINITE = "engine_not_finite"
REASON_CODE_FETCH_EXCEPTION = "fetch_exception"
REASON_CODE_COMPUTE_EXCEPTION = "compute_exception"
REASON_CODE_READER_REJECTED = "reader_rejected"
REASON_CODE_SAME_DAY_CONFLICT = "same_day_valid_conflict"

STATUS_REASON_CODE: Mapping[str, str] = MappingProxyType({
    STATUS_VALID: REASON_CODE_NONE,
    STATUS_REQUIRED_CORE_INCOMPLETE: REASON_CODE_CORE_MISSING,
    STATUS_ENGINE_FAILSAFE: REASON_CODE_FAIL_SAFE,
    STATUS_ENGINE_NOT_FINITE: REASON_CODE_NOT_FINITE,
    STATUS_FETCH_FAILED: REASON_CODE_FETCH_EXCEPTION,
    STATUS_COMPUTE_ERROR: REASON_CODE_COMPUTE_EXCEPTION,
    STATUS_SNAPSHOT_REJECTED: REASON_CODE_READER_REJECTED,
    STATUS_SAME_DAY_CONFLICT: REASON_CODE_SAME_DAY_CONFLICT,
})

# ══════════════════════════════════════════════════════════════════════
# 冪等寫入的結果碼（`upsert_record` 回傳；排程 log 用）
# ══════════════════════════════════════════════════════════════════════
UPSERT_APPENDED = "APPENDED"
#: 同鍵、內容完全相同 → 不寫（重跑）。
UPSERT_NOOP_DUPLICATE = "NOOP_DUPLICATE"
#: ~~`UPSERT_NOOP_VALID_EXISTS`（同鍵已有 VALID、本輪非 VALID → 不寫）~~ —— 📌 稽核修正（2026-10-19，有意識的變更，
#:   不是漏刪）：後來的失敗也是當天的真實事實，改為**另記一列**（`UPSERT_APPENDED`）；首筆 VALID 照樣不動，
#:   讀端只拿 VALID 比較，失敗列不會蓋掉或稀釋它。舊規則的理由（不讓失敗蓋掉有效紀錄）由「既有列永不修改」守住。
#: 同鍵已有 VALID，本輪也是 VALID 但內容不同 → ⛔ 不覆寫首筆；本輪結果以 `STATUS_SAME_DAY_CONFLICT` 另記一列
#: （同內容的衝突列不重複記），呼叫端（腳本）據此以非 0 結束 —— 衝突必須被人看見，⛔ 不能只留在 Actions log。
UPSERT_CONFLICT_KEPT_EXISTING = "CONFLICT_KEPT_EXISTING"

UPSERT_OUTCOMES: tuple[str, ...] = (
    UPSERT_APPENDED, UPSERT_NOOP_DUPLICATE, UPSERT_CONFLICT_KEPT_EXISTING,
)

# ══════════════════════════════════════════════════════════════════════
# 讀端比較狀態（「和上次比」能不能說）—— ⛔ 沒有變動大小門檻
# ══════════════════════════════════════════════════════════════════════
#: 沒有任何同版本 VALID 歷史 ⇒ 畫面「從今天開始記錄」（DEC-062 Q4 過渡 B）。
COMPARE_START_RECORDING = "START_RECORDING"
#: 預期日期沒有紀錄（排程沒跑／失敗），或最新有效紀錄已超過既有 7 天有效期 ⇒ ⛔ 不比較。
COMPARE_STALE = "STALE"
#: 預期日期有紀錄，但不是 VALID（核心不齊／取數失敗…）⇒ ⛔ 不比較，照實顯示該列狀態。
COMPARE_CURRENT_NOT_VALID = "CURRENT_NOT_VALID"
#: 今天與上一筆有效紀錄的 `input_asof` 完全相同（沿用期、同一份資料）⇒ 不算變化、不比較。
COMPARE_NO_NEW_DATA = "NO_NEW_DATA"
#: 今天 VALID、有上一筆同版本 VALID、且資料日不同 ⇒ 可以並列「上次 vs 這次」。
COMPARE_COMPARABLE = "COMPARABLE"

COMPARE_STATUSES: tuple[str, ...] = (
    COMPARE_START_RECORDING, COMPARE_STALE, COMPARE_CURRENT_NOT_VALID,
    COMPARE_NO_NEW_DATA, COMPARE_COMPARABLE,
)

#: `COMPARE_STALE` 的細分原因。
STALE_TODAY_RUN_MISSING = "expected_date_record_missing"
STALE_LATEST_VALID_EXPIRED = "latest_valid_expired"

# ══════════════════════════════════════════════════════════════════════
# 寫入憑證（**未來**的排程寫入帳號；本 PoC 不建立、不讀取任何 secret）
# ══════════════════════════════════════════════════════════════════════
#: 📌 2026-10-19（VN1-STORE WIF auth-only 批；有意識的變更，不是漏刪）：原本這裡定義的「writer
#:   service account JSON key 所放的環境變數名」常數**已退役刪除**（DEC-064 G1：writer 採 GitHub OIDC＋
#:   Workload Identity Federation impersonate `risk-cap-writer`，⛔ 禁止建立 writer JSON key ⇒ 那個
#:   環境變數不會有任何合法內容；`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 6 節第 4 點）。
#:   舊名稱的理由（不沿用個人持股 Sheet 既有 SA 金鑰名稱，避免重開 SEC-3 同類風險）仍成立，
#:   由「writer 根本沒有 key」更嚴格地守住。writer 憑證日後**只**經 WIF 取得的短效 ADC
#:   （`google-github-actions/auth` 產生的 `external_account` 憑證檔）—— 由未來正式寫入批次接線；
#:   本批只驗證能換到身分（`scripts/risk_cap_wif_auth_check.py`），不碰任何 Sheet。
#:   舊名稱的字面只留在文件與測試的「禁止字面」守衛裡（`tests/test_vn1_wif_auth_only.py`）。
#: 寫入端 OAuth scope（只開試算表；⛔ 不含 Drive）。
WRITER_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/spreadsheets",)
#: ~~稽核修正（2026-10-19）：**保留**未來網站讀取端的名稱與 scope（放 Streamlit secrets）。
#: 本 PoC **沒有**任何讀取端程式碼路徑；先定名只為讓寫入／讀取兩支帳號從一開始就分開。~~
#: ~~`READER_SA_ENV_VAR`（環境變數式的讀取端 key 名稱）~~
#: 📌 2026-10-20（VN1-STORE Production Wiring 批；有意識的變更，不是漏刪）：上面那個**環境變數式**的讀取端名稱
#:   **已退役刪除** —— reader key 依規格 `docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 步驟 8 **只放 Streamlit secrets**
#:   的獨立 TOML 表格（下方 `READER_SECRETS_TABLE`），⛔ 不走環境變數；留著它等於留一條「把 reader key 放進
#:   環境變數也行」的引用點。舊名稱的理由（讀取／寫入兩支帳號從一開始就分開）由 `READER_SECRETS_TABLE`
#:   與 writer「只走 WIF、沒有 key」更嚴格地守住。舊字面只留在測試的「禁止字面」守衛裡。
#: 讀取端 OAuth scope：唯讀（`spreadsheets.readonly`）。
READER_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/spreadsheets.readonly",)
#: 未來系統歷史 Sheet 的 ID 所放的環境變數名（新名稱）。
HISTORY_SHEET_ID_ENV_VAR: str = "RISK_CAP_HISTORY_SHEET_ID"
#: 寫入總開關（新名稱）。本 PoC 階段**即使設了也拒絕**（production 寫入尚未核准）。
WRITE_ENABLE_ENV_VAR: str = "RISK_CAP_HISTORY_WRITE_ENABLED"
#: production 寫入是否已獲客戶核准。⚠️ 改成 True 需要客戶另一次裁示（DEC-009），⛔ 不得自行改。
PRODUCTION_WRITE_APPROVED: bool = False

# ══════════════════════════════════════════════════════════════════════
# 身分與憑證來源（VN1-STORE Production Wiring 批，2026-10-20；規格 `docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md`）
# ══════════════════════════════════════════════════════════════════════
#: 客戶設定的固定身分（DEC-064 G1／G2；⛔ 不是 secret —— 規格第 4 節、第 5.4 節實跑紀錄皆已公開記載）。
#: ⚠️ `scripts/risk_cap_permission_test.py` 另有同值字面（該腳本本批不動）；兩者一致由
#:   `tests/test_vn1_production_wiring.py` 守衛。
WRITER_SA_EMAIL: str = "risk-cap-writer@mystock20260823.iam.gserviceaccount.com"
READER_SA_EMAIL: str = "risk-cap-reader@mystock20260823.iam.gserviceaccount.com"
#: writer 憑證檔唯一接受的型別：WIF 產生的短效 federation 設定檔（`google-github-actions/auth`）。
#: ⛔ `service_account`（任何 JSON key）一律拒絕（DEC-064 G1 禁止 writer JSON key）。
WRITER_CREDENTIAL_TYPE: str = "external_account"
#: reader 憑證唯一接受的型別：`risk-cap-reader` 的唯讀 JSON key（DEC-064 G2）。
READER_CREDENTIAL_TYPE: str = "service_account"
#: writer ADC 憑證檔路徑的環境變數（auth action 以 `create_credentials_file` 匯出）。
GAC_ENV_VAR: str = "GOOGLE_APPLICATION_CREDENTIALS"
#: Streamlit secrets 內 reader key 的 TOML 表格名（規格步驟 8：`[risk_cap_history_reader]`）。
#: ⚠️ 必須與既有 `[gcp_service_account]` 不同名（SEC-3 同類風險）；讀取端 ⛔ 只讀這張表。
READER_SECRETS_TABLE: str = "risk_cap_history_reader"
#: Streamlit secrets 內系統歷史 Sheet ID 的頂層鍵（規格步驟 8：`risk_cap_history_sheet_id`）。
#: ⚠️ 與 GitHub secret `RISK_CAP_HISTORY_SHEET_ID`（寫入端環境變數，上方 `HISTORY_SHEET_ID_ENV_VAR`）同值不同名。
READER_SHEET_ID_SECRET_KEY: str = "risk_cap_history_sheet_id"

# ══════════════════════════════════════════════════════════════════════
# 讀取結果狀態（L3 `risk_cap_history_reader_service.read_history` 回傳；「讀得到嗎」，≠ 上面的比較狀態）
# ══════════════════════════════════════════════════════════════════════
#: 讀到表頭正確、至少一列資料（是否「能和上次比」另看 `compare`）。
READ_STATUS_OK = "OK"
#: 讀到了，但表是空的（沒有任何資料列；含連表頭都還沒有）⇒ `compare` 為 START_RECORDING（⛔ 不是 0、不是中性）。
READ_STATUS_EMPTY = "EMPTY"
#: Streamlit secrets 沒有 `[risk_cap_history_reader]` 表格（或空表、secrets 不可讀、key 內容無法載入）。
READ_STATUS_NO_CREDENTIAL = "NO_CREDENTIAL"
#: 沒有 `risk_cap_history_sheet_id`（或格式不是純 Sheet ID —— ⛔ 不接受網址、不解析）。
READ_STATUS_NO_SHEET_ID = "NO_SHEET_ID"
#: 試算表裡沒有 `risk_cap_daily` 分頁。
READ_STATUS_TAB_MISSING = "TAB_MISSING"
#: 表頭與 `HISTORY_COLUMNS` 不一致（缺欄／多欄／順序不同）或資料列欄數超過表頭 ⇒ ⛔ 不猜欄位對應。
READ_STATUS_SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
#: Google API／傳輸／權杖錯誤（403、404、5xx、逾時…）。只記例外類別名，⛔ 不記訊息原文。
READ_STATUS_API_ERROR = "API_ERROR"
#: 憑證身分不是 `risk-cap-reader`（含 writer、fund-nav、external_account、其他 SA），或開到的 Sheet／分頁核對不符。
READ_STATUS_IDENTITY_MISMATCH = "IDENTITY_MISMATCH"

READ_STATUSES: tuple[str, ...] = (
    READ_STATUS_OK, READ_STATUS_EMPTY, READ_STATUS_NO_CREDENTIAL, READ_STATUS_NO_SHEET_ID,
    READ_STATUS_TAB_MISSING, READ_STATUS_SCHEMA_MISMATCH, READ_STATUS_API_ERROR, READ_STATUS_IDENTITY_MISMATCH,
)
#: 只有這兩種讀取結果會進快取（失敗 ⛔ 不快取 —— v3 §02「只快取成功結果」）。
READ_STATUSES_CACHEABLE: tuple[str, ...] = (READ_STATUS_OK, READ_STATUS_EMPTY)
