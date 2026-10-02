"""src/data/stock/twse_holiday_fetcher.py — 台股「開（休）市日期」官方表 fetcher（L1）。

批 D5（2026-10-02，客戶裁示頁1⑤「接休市日曆」＝放行新源；HANDOFF B4 (a)）。

═══ 來源（§2.1 T1）═══════════════════════════════════════════════════
臺灣證券交易所 OpenAPI「有價證券集中交易市場開（休）市日期」::

    GET https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule

回傳 JSON **陣列**，每列四欄（官方欄名）::

    {"Name": "中華民國開國紀念日", "Date": "1150101",
     "Weekday": "四", "Description": "依規定放假1日。"}

- `Date`：**7 位民國年月日** `YYYMMDD`（與 `FMTQIK` 等 openapi 端點同格式，
  見 `src/data/macro/leading_indicators.py` 的同款解析註解）。
- 時區：日期是**台北日曆日**（Asia/Taipei，UTC+8），不含時刻。
- 發布時點：證交所於前一年年底公告次年全年表；**臨時休市（颱風等）不在表內**
  —— 那是當天才由主管機關宣布的，本表給不出來（見「已知限制」）。

⚠️ **本檔寫成時沙箱連不到 `openapi.twse.com.tw`**（agent proxy 回 403 tunnel，
2026-10-02 實測），上述格式取自證交所 OpenAPI 文件與本 repo 既有 openapi 端點的
日期慣例，**沒有拿到一份真實回應比對過**。所以解析一律**嚴格**：欄位缺、日期壞、
整份空 → 直接 raise，不猜（§1）。

═══ 表裡不是每一列都是「休市」═══════════════════════════════════════
證交所這張表同時列出「休市日」與「提示用的交易日」（例：「國曆新年開始交易日」
「農曆春節前最後交易日」）。把每一列都當休市 = 把交易日說成休市。故逐列分三類：

- `closed`：名稱或說明含 `CLOSED_MARKERS` 任一詞（放假／補假／休市／無交易…）
- `trading`：含 `TRADING_MARKERS` 任一詞（開始交易／最後交易／照常交易）
- `unclassified`：**兩類都沒中、或兩類都中**。⛔ 不猜它是哪一類 ——
  下游碰到這一天一律判「無法判定」（L2 `src/compute/trading_calendar.py`）。
- **同一天兩列分類互相衝突**（例：一列放假、一列開始交易）→ 該日只歸 `unclassified`。

═══ 完整性檢查（批 D5 QA 修 1）═════════════════════════════════════
某年要三個固定國曆日國定假日（`COMPLETENESS_ANCHORS`：1/1、2/28、10/10）都以 `closed`
出現才算涵蓋；沒有任何一年通過 → 整份 raise（不入快取）。只防明顯殘缺，⛔ 不證明完整。

═══ 只快取成功、失敗退避（§1.A-3）══════════════════════════════════
- 快取層 `_fetch_calendar_cached` 失敗一律 **raise**（`st.cache_data` 不快取例外）；
  成功結果快取 `TTL_1DAY`。快取鍵帶「台北當年」，跨年第一次呼叫必定重抓。
- 外層 `fetch_twse_holiday_calendar` 以 `shared.fail_cooldown.FailCooldown` 退避：
  失敗後冷卻期內**不重打上游**，直接再拋同一則失敗（訊息註明「冷卻中」）。

§8.2：L1 —— 只做 I/O＋解析；「今天是不是交易日」的判斷在 L2，編排在 L3
（`src/services/trading_calendar_service.py`）。streamlit 只為 `@st.cache_data`
（§8.2.A EX-CACHE-1；登錄於 `tests/test_c3_layering_guard.py` 白名單）。
⚠️ 未掛 `@monitored`：掛上會讓「📖 憑什麼 › 資料體檢」多出一列（畫面變更），
本批不動畫面。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from shared.fail_cooldown import NO_HIT as _FC_NO_HIT
from shared.fail_cooldown import FailCooldown as _FailCooldown
from shared.roc_calendar import roc_to_gregorian_year
from shared.ttls import TTL_1DAY

# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
# 本檔僅用 @st.cache_data,無真 UI 呼叫。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

#: 官方端點（§2.1 T1）。
TWSE_HOLIDAY_URL: str = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
#: provenance 的來源識別（§2.2）。
SOURCE_ID: str = "TWSE:openapi/holidaySchedule"

#: 判為「休市」的關鍵詞（名稱或說明任一含即中）。
CLOSED_MARKERS: tuple[str, ...] = ("放假", "補假", "休市", "無交易", "停止交易")
#: 判為「表內提示的交易日」的關鍵詞。
#: 「照常交易」（批 D5 QA A 組）：例「依規定僅勞工放假，市場照常交易」同時中「放假」→ 兩類都中
#: → `unclassified`（無法判定），⛔ 不再被誤判成休市。
TRADING_MARKERS: tuple[str, ...] = ("開始交易", "最後交易", "照常交易")

#: `Weekday` 欄的字 → `date.weekday()`（交叉核對用；格式漂移時 raise）。
_WEEKDAY_CHARS: dict[str, int] = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}

#: 「這一年的表是完整的」的錨點：三個**固定國曆日**的國定假日，每年必列（落在週末也照列）。
#: 某年三個都以 `closed` 出現，才算本表涵蓋該年；缺任一 → 該年一律無法判定（批 D5 QA 修 1：
#: 修前「該年有任一列就算涵蓋」⇒ 只回一列的殘表會把春節等平日休市全判成交易日）。
#: ⚠️ 只防「明顯殘缺」，⛔ 不證明完整（例：漏掉春節而三錨點都在的表仍會通過）。
COMPLETENESS_ANCHORS: tuple[tuple[int, int], ...] = ((1, 1), (2, 28), (10, 10))

_HDR_JSON = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


class HolidayCalendarUnavailable(RuntimeError):
    """休市表拿不到或格式不對 —— 呼叫端必須顯示「無法判定」，⛔ 不得當成交易日。"""


@dataclass(frozen=True)
class HolidayEntry:
    """表內一列（原文保留，供追溯）。"""

    day: date
    name: str
    description: str
    kind: str  # "closed" | "trading" | "unclassified"


@dataclass(frozen=True)
class HolidayCalendar:
    """解析後的休市表 ＋ provenance（§2.2）。"""

    entries: tuple[HolidayEntry, ...]
    #: 通過完整性檢查（`COMPLETENESS_ANCHORS`）的西元年；不在其中的年份一律無法判定。
    covered_years: frozenset[int]
    source: str
    #: 抓取當下（UTC）。
    fetched_at: datetime

    def conflicting_dates(self) -> frozenset[date]:
        """同一天出現兩種以上分類的日子（例：一列放假、一列開始交易）。"""
        kinds: dict[date, set[str]] = {}
        for e in self.entries:
            kinds.setdefault(e.day, set()).add(e.kind)
        return frozenset(d for d, k in kinds.items() if len(k) > 1)

    def dates_of(self, kind: str) -> frozenset[date]:
        """某一類的日子。**分類互相衝突的日子只歸 `unclassified`**（批 D5 QA 修 2）。"""
        conflict = self.conflicting_dates()
        if kind == "unclassified":
            return frozenset(e.day for e in self.entries if e.kind == kind) | conflict
        return frozenset(e.day for e in self.entries if e.kind == kind) - conflict


def parse_roc_date(raw: object) -> date:
    """7 位民國 `YYYMMDD` → `date`。格式不符一律 raise（⛔ 不猜）。"""
    s = str(raw).strip() if raw is not None else ""
    if len(s) != 7 or not s.isdigit():
        raise ValueError(f"Date 欄不是 7 位民國年月日：{raw!r}")
    if int(s[:3]) < 1:
        raise ValueError(f"Date 欄民國年小於 1（民國 0 年不存在）：{raw!r}")
    return date(roc_to_gregorian_year(int(s[:3])), int(s[3:5]), int(s[5:7]))


def classify_entry(name: str, description: str) -> str:
    """一列 → `closed` / `trading` / `unclassified`（見檔頭；兩類都中也算 unclassified）。"""
    text = f"{name}　{description}"
    is_closed = any(m in text for m in CLOSED_MARKERS)
    is_trading = any(m in text for m in TRADING_MARKERS)
    if is_closed and not is_trading:
        return "closed"
    if is_trading and not is_closed:
        return "trading"
    return "unclassified"


def parse_holiday_schedule(payload: object, *, fetched_at: datetime) -> HolidayCalendar:
    """官方 JSON（已 `json.loads`）→ `HolidayCalendar`。任何格式不符一律 raise。"""
    if not isinstance(payload, list):
        raise ValueError(f"回應不是 JSON 陣列：{type(payload).__name__}")
    if not payload:
        raise ValueError("回應是空陣列（休市表沒有任何一列）")
    entries: list[HolidayEntry] = []
    for i, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"第 {i} 列不是物件：{type(row).__name__}")
        missing = [k for k in ("Name", "Date") if k not in row]
        if missing:
            raise ValueError(f"第 {i} 列缺欄 {missing}：{row!r}")
        day = parse_roc_date(row["Date"])
        wd = str(row.get("Weekday") or "").strip()
        if wd and wd[-1] in _WEEKDAY_CHARS and _WEEKDAY_CHARS[wd[-1]] != day.weekday():
            raise ValueError(f"第 {i} 列星期對不上：Date={row['Date']!r} Weekday={wd!r}")
        name = str(row.get("Name") or "").strip()
        desc = str(row.get("Description") or "").strip()
        entries.append(HolidayEntry(day=day, name=name, description=desc,
                                    kind=classify_entry(name, desc)))
    entries.sort(key=lambda e: e.day)
    _unc = [e for e in entries if e.kind == "unclassified"]
    if _unc:
        # §1：不吞 —— 這些日子下游會判「無法判定」，這裡先講出來。
        print(f"[twse_holiday] {len(_unc)} 列無法分類（下游判無法判定）："
              + "；".join(f"{e.day} {e.name}" for e in _unc[:5]))
    _draft = HolidayCalendar(entries=tuple(entries), covered_years=frozenset(),
                             source=SOURCE_ID, fetched_at=fetched_at)
    _closed = _draft.dates_of("closed")
    _years = sorted({e.day.year for e in entries})
    complete = frozenset(y for y in _years
                         if all(date(y, m, d) in _closed for m, d in COMPLETENESS_ANCHORS))
    if not complete:
        # 殘表 ⇒ raise（快取層不快取例外），⛔ 不得當成功結果快取 TTL_1DAY。
        raise ValueError(f"休市表不完整：{_years} 年都缺固定國定假日錨點 {COMPLETENESS_ANCHORS}")
    if set(_years) - complete:
        print(f"[twse_holiday] 下列年份表不完整、判無法判定：{sorted(set(_years) - complete)}")
    return HolidayCalendar(
        entries=tuple(entries),
        covered_years=complete,
        source=SOURCE_ID,
        fetched_at=fetched_at,
    )


def _fetch_json() -> object:
    """打官方端點（NAS proxy → 直連降級 → NAS 中繼，見 `proxy_helper.fetch_url`）。"""
    from src.data.proxy import fetch_url as _furl
    r = _furl(TWSE_HOLIDAY_URL, headers=_HDR_JSON, timeout=20, attempts=2)
    if r is None:
        raise HolidayCalendarUnavailable(f"{SOURCE_ID} 無回應（proxy／直連／中繼皆失敗）")
    if getattr(r, "status_code", None) != 200:
        raise HolidayCalendarUnavailable(f"{SOURCE_ID} HTTP {getattr(r, 'status_code', None)}")
    try:
        return r.json()
    except ValueError as e:
        raise HolidayCalendarUnavailable(f"{SOURCE_ID} 回應不是 JSON：{e}") from e


@st.cache_data(ttl=TTL_1DAY, max_entries=4, show_spinner=False)
def _fetch_calendar_cached(taipei_year: int) -> HolidayCalendar:
    """快取層。**失敗一律 raise**（不入快取）。`taipei_year` 只當快取鍵（跨年即重抓）。"""
    payload = _fetch_json()
    try:
        return parse_holiday_schedule(payload, fetched_at=datetime.now(timezone.utc))
    except ValueError as e:
        raise HolidayCalendarUnavailable(f"{SOURCE_ID} 格式不符：{e}") from e


#: §1.A-3(b)：失敗退避 —— 冷卻期內不重打上游。
_calendar_fail_cooldown = _FailCooldown()


def fetch_twse_holiday_calendar(*, taipei_year: int) -> HolidayCalendar:
    """取休市表（只快取成功；失敗退避）。

    Raises:
        HolidayCalendarUnavailable: 拿不到或格式不對。冷卻期內再叫，**不打上游**，
            直接再拋同一則失敗（訊息加註「冷卻中」）。
    """
    _key = int(taipei_year)
    _hit, _gen = _calendar_fail_cooldown.begin(_key)
    if _hit is not _FC_NO_HIT:
        raise HolidayCalendarUnavailable(f"{_hit}（冷卻中，未重打上游）")
    try:
        cal = _fetch_calendar_cached(_key)
    except Exception as e:  # noqa: BLE001 — 記下後原樣轉成可辨識的失敗再拋（§1 不吞）
        msg = str(e) if isinstance(e, HolidayCalendarUnavailable) else f"{type(e).__name__}: {e}"
        print(f"[twse_holiday] 取休市表失敗：{msg}")
        _calendar_fail_cooldown.fail(_key, _gen, msg)
        raise HolidayCalendarUnavailable(msg) from e
    _calendar_fail_cooldown.success(_key)
    return cal


def _clear_calendar_cache() -> None:
    getattr(_fetch_calendar_cached, "clear", lambda: None)()
    _calendar_fail_cooldown.clear()


fetch_twse_holiday_calendar.clear = _clear_calendar_cache
