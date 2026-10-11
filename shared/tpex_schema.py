"""shared/tpex_schema.py — 櫃買中心（TPEx）官方新網站 JSON 結構契約 SSOT（L0，批 Z41，2026-10-11）。

客戶裁示 Q-z27＝A（受控遷移）：上櫃三大法人與收盤改接櫃買中心官方新網站 JSON。
本檔只放「結構契約 + 驗證門檻」常數，**不做 I/O**；抓取與逐列驗證在 L1
（`src/data/core/data_loader_inst_fetchers._get_tpex_day`、
`src/data/stock/market_close_fetcher.fetch_tpex_close_day`）。

探針證據（runner 實測 run 38104351927／38105028779／38105352894，2026-10-08；派工規格轉述）
=====================================================================================
法人 `https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=YYYY/MM/DD&id=&response=json`
- 頂層 `stat=='ok'`、`date`＝請求日 `YYYYMMDD`（非交易日也是回聲，不回退前一交易日）、
  `columnNum`（＝25，與實際 24 欄不符 ⇒ **不得使用**）、`tables`。
- `tables[0]`：`title=='三大法人買賣明細資訊'`、`date`＝民國 `YYY/MM/DD`、`totalCount`、`fields`（24）、`data`。
- fields 原文只有「買進股數／賣出股數／買賣超股數」×7，**群組語意只能靠官方明細頁表頭（colspan=3）**：
    G1 外資及陸資(不含外資自營商) [2-4]   G2 外資自營商 [5-7]   G3 外資及陸資 [8-10]
    G4 投信 [11-13]   G5 自營商(自行買賣) [14-16]   G6 自營商(避險) [17-19]   G7 自營商 [20-22]
    T  三大法人買賣超股數合計 [23]
  官方註腳：T ＝ 外資及陸資(不含外資自營商) ＋ 投信 ＋ 自營商；外資自營商已計入自營商，不納入合計。
- ⚠️ 外資自營商 G2 在 2018~2026 抽查皆 0 ⇒ G1 與 G3 數值相同、只靠表頭區分 ⇒ L1 **逐列**驗
  G1＋G2＝G3（買／賣／超三欄）；一旦 G2 非零即有數值證據可偵測 G1／G3 對調。
- 單位：股。代號為字串（含 `00411A`、`00687C`），只 strip、不得轉 int。

收盤 `https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?date=YYYY/MM/DD&type=EW&id=&response=json`
- `tables[0].title=='上櫃股票每日收盤行情(不含定價)'`；fields 17 欄（原文含 `<br>`、前後與內部多餘空白）。
- 收盤／最高／最低 元/股（千分位）；無成交為 `'----'`；成交股數（股）、成交金額（元）。
- notes：ETF 證券代號第六碼為 K、C 者以外幣交易（幣別混用防護見 `shared.sector_flow_thresholds`）。

常數 + 純函式（只讀已拿到的 response 物件屬性 / dict，零 I/O、不 import streamlit），只依賴 L0
`shared.roc_calendar`（可被全層 import）。
"""
from __future__ import annotations

import re

from shared.roc_calendar import gregorian_to_roc_year

# ══════════════════════════════════════════════════════════════════════
# 1. 三大法人買賣明細（insti/dailyTrade）
# ══════════════════════════════════════════════════════════════════════
#: 官方回應 `stat` 成功值（小寫，與 TWSE 的 'OK' 不同）。
TPEX_STAT_OK: str = "ok"
#: `tables[0].title` 逐字。
TPEX_INST_TITLE: str = "三大法人買賣明細資訊"
#: 每組「買進／賣出／買賣超」三欄（股）。
_BSN: tuple[str, str, str] = ("買進股數", "賣出股數", "買賣超股數")
#: `tables[0].fields` strip 後**逐字**等於本常數（24 欄）；不得用 `columnNum`。
TPEX_INST_FIELDS: tuple[str, ...] = ("代號", "名稱") + _BSN * 7 + ("三大法人買賣超股數合計",)
TPEX_INST_N_FIELDS: int = len(TPEX_INST_FIELDS)   # 24

#: 7 組（買, 賣, 超）欄位索引（官方明細頁表頭 colspan=3 順序；見模組 docstring）。
TPEX_G_FOREIGN_EXCL_FD: tuple[int, int, int] = (2, 3, 4)    # G1 外資及陸資(不含外資自營商)
TPEX_G_FOREIGN_DEALER: tuple[int, int, int] = (5, 6, 7)     # G2 外資自營商
TPEX_G_FOREIGN_INCL_FD: tuple[int, int, int] = (8, 9, 10)   # G3 外資及陸資（含外資自營商）
TPEX_G_TRUST: tuple[int, int, int] = (11, 12, 13)           # G4 投信
TPEX_G_DEALER_SELF: tuple[int, int, int] = (14, 15, 16)     # G5 自營商(自行買賣)
TPEX_G_DEALER_HEDGE: tuple[int, int, int] = (17, 18, 19)    # G6 自營商(避險)
TPEX_G_DEALER: tuple[int, int, int] = (20, 21, 22)          # G7 自營商（＝自行＋避險）
TPEX_IDX_TOTAL_NET: int = 23                                # T 三大法人買賣超股數合計
TPEX_ALL_GROUPS: tuple[tuple[int, int, int], ...] = (
    TPEX_G_FOREIGN_EXCL_FD, TPEX_G_FOREIGN_DEALER, TPEX_G_FOREIGN_INCL_FD, TPEX_G_TRUST,
    TPEX_G_DEALER_SELF, TPEX_G_DEALER_HEDGE, TPEX_G_DEALER)

#: 輸出口徑（客戶 Q-z24 A'／Q-z25 A，與上市 T86 一致）：外資＝G1 超、投信＝G4 超、自營商＝G7 超。
TPEX_IDX_OUT_FOREIGN: int = TPEX_G_FOREIGN_EXCL_FD[2]   # 4
TPEX_IDX_OUT_TRUST: int = TPEX_G_TRUST[2]               # 13
TPEX_IDX_OUT_DEALER: int = TPEX_G_DEALER[2]             # 22

#: 不可解析列（任一數值欄不可解析 / 代號空 / 代號重複）佔比 > 本值 ⇒ 整日 `parse_error`（非 ok）。
#: ≤ 本值時該代號輸出三分項 NaN（批 Z41 修正 QA M1：缺值不省略、不當 0）。
TPEX_INST_MAX_INVALID_ROW_RATIO: float = 0.01
#: 批 Z41 修正（QA M2）：**資料守衛**（7 組 買−賣＝超、G5＋G6＝G7、T＝G1＋G4＋G7）不成立列佔比 > 本值
#: ⇒ 整日 `identity_failed`；≤ 本值時該代號三分項 NaN。**語意守衛** G1＋G2＝G3 不受本門檻寬限：
#: 任一列不成立即整日 `identity_failed`（G1/G3 欄位對調的唯一偵測）。
TPEX_INST_MAX_IDENTITY_FAIL_ROW_RATIO: float = 0.01

# ══════════════════════════════════════════════════════════════════════
# 2. 上櫃股票每日收盤行情（afterTrading/otc）
# ══════════════════════════════════════════════════════════════════════
#: `tables[0].title` 開頭（完整原文「上櫃股票每日收盤行情(不含定價)」）。
TPEX_CLOSE_TITLE_PREFIX: str = "上櫃股票每日收盤行情"
#: fields 欄數（清洗後）。
TPEX_CLOSE_N_FIELDS: int = 17
#: 清洗（去 HTML 標籤、strip、內部連續空白去除）後**完全相等**比對的必要欄名。
TPEX_CLOSE_COL_CODE: str = "代號"
TPEX_CLOSE_COL_CLOSE: str = "收盤"
TPEX_CLOSE_COL_HIGH: str = "最高"
TPEX_CLOSE_COL_LOW: str = "最低"
TPEX_CLOSE_COL_VOLUME: str = "成交股數"
TPEX_CLOSE_COL_AMOUNT: str = "成交金額(元)"
TPEX_CLOSE_REQUIRED_COLS: tuple[str, ...] = (
    TPEX_CLOSE_COL_CODE, TPEX_CLOSE_COL_CLOSE, TPEX_CLOSE_COL_HIGH,
    TPEX_CLOSE_COL_LOW, TPEX_CLOSE_COL_VOLUME, TPEX_CLOSE_COL_AMOUNT)
#: 整表單位守衛：有成交列的「成交金額 ÷ 成交股數」須落在 [最低, 最高]（相對容差 ±0.1%）。
TPEX_CLOSE_VWAP_REL_TOL: float = 0.001
#: 上述單位守衛的成立率下限（有成交列中）；不足 ⇒ 整日非 ok（`unit_error`）。
TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO: float = 0.95

# ══════════════════════════════════════════════════════════════════════
# 3. 回應守衛
# ══════════════════════════════════════════════════════════════════════
#: 批 Z41 修正：外殼守衛的「表內日期」是否必填（集中於此，runner 實測若不同時單點修正）。
#: 法人表 `tables[0].date` 探針實測存在 → 必填；收盤表探針未記錄 → 有出現才比對。
TPEX_INST_REQUIRE_TABLE_DATE: bool = True
TPEX_CLOSE_REQUIRE_TABLE_DATE: bool = False

#: 舊端點下架後 302 轉往的錯誤頁路徑片段（最終 HTTP 200 的 HTML 404 頁）。
TPEX_ERROR_PATH_FRAGMENT: str = "/errors"


# ══════════════════════════════════════════════════════════════════════
# 4. 純函式守衛（L1 兩個 fetcher 共用；回傳狀態字串，由 L1 決定快取 / log）
# ══════════════════════════════════════════════════════════════════════
_INT_RE = re.compile(r"^-?\d+$")
_DEC_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def parse_tpex_int(v) -> int | None:
    """股數儲存格 → int；去千分位與 `+`、strip。空白／'--'／小數／亂字 → None（缺值，⛔ 不當 0）。"""
    s = str(v).replace(",", "").replace("+", "").strip()
    return int(s) if _INT_RE.match(s) else None


def parse_tpex_price(v) -> float | None:
    """價格／金額儲存格 → float；去千分位、strip。`'----'`／`'除息'`／空白／亂字 → None（缺值）。"""
    s = str(v).replace(",", "").strip()
    return float(s) if _DEC_RE.match(s) else None


def clean_tpex_field_name(name) -> str:
    """收盤表 fields 清洗：去 HTML 標籤（`<br>`）→ 去所有空白（含內部）。

    例：`'最後買量<br>(張數)'` → `'最後買量(張數)'`、`' 成交金額(元)'` → `'成交金額(元)'`、`'收盤 '` → `'收盤'`。
    """
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", str(name)))


def tpex_redirected_to_error(resp) -> bool:
    """回應是否被轉往官方錯誤頁（`r.url` 或 `r.history` 任一跳含 `/errors`）。

    舊端點下架後 302 → `/errors`（HTML 404 頁、最終 HTTP 200），`fetch_url` 視為成功 ——
    本守衛把它攔成 `redirect_error`。⚠️ `fetch_url` Storm Shield 快取命中回的 mock Response
    無 url／history；錯誤頁內容不是 JSON，仍會被下一關 `json_error` 擋下。
    """
    if TPEX_ERROR_PATH_FRAGMENT in str(getattr(resp, "url", "") or ""):
        return True
    for h in (getattr(resp, "history", None) or ()):
        loc = ""
        try:
            loc = str((getattr(h, "headers", None) or {}).get("Location", "") or "")
        except Exception:  # noqa: BLE001 — 診斷用 header 讀取失敗不擋主判定
            loc = ""
        if TPEX_ERROR_PATH_FRAGMENT in str(getattr(h, "url", "") or "") \
                or TPEX_ERROR_PATH_FRAGMENT in loc:
            return True
    return False


def tpex_roc_date(ds: str) -> str:
    """請求日 `YYYYMMDD` → 民國 `YYY/MM/DD`（`tables[0].date` 回聲格式）。"""
    return f"{gregorian_to_roc_year(int(ds[:4]))}/{ds[4:6]}/{ds[6:8]}"


def tpex_query_date(ds: str) -> str:
    """請求日 `YYYYMMDD` → 新網站查詢參數 `YYYY/MM/DD`（西元）。"""
    return f"{ds[:4]}/{ds[4:6]}/{ds[6:8]}"


def check_tpex_envelope(j, ds: str, *, title_exact: str | None = None,
                        title_prefix: str | None = None,
                        require_table_date: bool = True) -> tuple[str, str, dict | None]:
    """官方新網站 JSON 外殼守衛 → `(status, reason, table0)`。

    status：
    - `'schema_error'`：非 dict／`stat != 'ok'`／頂層 `date` ≠ 請求日（含回退前一交易日）／
      無 `tables[0]`／`data` 非 list／`totalCount` 可轉整數但 ≠ `len(data)`（批 Z41 修正 QA L2：
      防分頁／截斷靜默只收部分市場）／title 不符／
      `tables[0].date` ≠ 民國請求日。
    - `'empty'`：`data == []`（且 `totalCount` 缺或為 0）—— **非 ok**；空表不能等同休市
      （舊收盤端點在交易日也回空），由 caller 以 TWSE 同日是否有資料判定。
    - `'ok'`：外殼通過；欄位／逐列守衛由 caller 續做。
    `columnNum` 一律不讀（官方值 25 與實際 24 欄不符）。

    `require_table_date`：法人表探針實測 `tables[0].date`＝民國請求日 ⇒ 預設必須存在且相符；
    收盤表探針只回報頂層 `date` 回聲（未記錄 `tables[0].date` 是否存在）⇒ caller 傳 False：
    頂層回聲仍強制，`tables[0].date` **有出現就必須相符**、沒出現不臆測（避免把未驗證的假設寫成守衛）。
    """
    if not isinstance(j, dict):
        return "schema_error", f"頂層非 dict（{type(j).__name__}）", None
    if j.get("stat") != TPEX_STAT_OK:
        return "schema_error", f"stat={j.get('stat')!r}", None
    if str(j.get("date", "")).strip() != ds:
        return "schema_error", f"頂層 date 回聲 {j.get('date')!r} ≠ 請求日 {ds}", None
    tables = j.get("tables")
    if not isinstance(tables, list) or not tables or not isinstance(tables[0], dict):
        return "schema_error", "缺 tables[0]", None
    t0 = tables[0]
    data = t0.get("data")
    if not isinstance(data, list):
        return "schema_error", f"tables[0].data 非 list（{type(data).__name__}）", None
    tc = t0.get("totalCount")
    try:
        tc_i = None if tc is None else int(tc)
    except (TypeError, ValueError):
        return "schema_error", f"totalCount 不可解析 {tc!r}", None
    if tc_i is not None and tc_i != len(data):
        return "schema_error", f"totalCount={tc_i} ≠ data 列數 {len(data)}(分頁/截斷?)", None
    if not data:
        return "empty", "totalCount=0 且 data=[]", t0
    title = str(t0.get("title", "")).strip()
    if title_exact is not None and title != title_exact:
        return "schema_error", f"title {title!r} ≠ {title_exact!r}", None
    if title_prefix is not None and not title.startswith(title_prefix):
        return "schema_error", f"title {title!r} 不以 {title_prefix!r} 開頭", None
    if (require_table_date or "date" in t0) and \
            str(t0.get("date", "")).strip() != tpex_roc_date(ds):
        return "schema_error", (f"tables[0].date {t0.get('date')!r} ≠ 民國請求日 "
                                f"{tpex_roc_date(ds)}"), None
    return "ok", "", t0
