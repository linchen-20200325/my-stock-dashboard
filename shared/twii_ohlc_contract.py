# -*- coding: utf-8 -*-
"""shared/twii_ohlc_contract.py — 加權指數（TWII）日 K OHLC 視窗的唯讀、fail-closed 資料契約（L0 純函式）。

來源：Issue #1099 PR-1；決策 DEC-156（`docs/DECISIONS.md`）＋規格
`docs/vnext/NEWUI2_MARKET_TWII_KBAR_ABA_DECISION_SPEC_2026-11-09.md` §二「資料契約候選」。

單一職責：給定呼叫端**已切好**的一段日 K 視窗（日期／開高低收／每列 `fetched_at`），判斷它能不能被當成
「已收盤、邏輯合法」的日 K 畫出來；**不合法就整段不合格**（first violation wins），⛔ 不修補、不剔除、不補值。

§1 Fail Loud／fail-closed：
- 判不出來（缺 fetched_at、naive 時間、日期無法解析）一律當**不合格**，⛔ 不假設合格。
- 本模組不讀檔、不連網、不讀時鐘：`today` 由呼叫端注入（L3 以 Asia/Taipei 今日帶入）。
- ⛔ 不 import pandas／streamlit／`src.*`（L0 不得依賴 L1+，CLAUDE.md §8.2）；只用標準函式庫。

⚠️ 本契約**只管 K 線圖的顯示資料有效性**：與 Risk Cap／VN1-PG-CUTOFF-VERIFY／DEC-070 無關，
不是投資門檻、不產生任何訊號。成交量、均線不在本契約範圍（DEC-156：不畫量、MA 未核准）。
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

#: 日 K「已收盤可信」的台北時間門檻（時）：抓取時間（台北）落在**該交易日 17:00 以後**才算完整收盤棒。
#: 出處：CLAUDE.md §2.3 PIT 表「TWSE / TPEX｜收盤行情／法人｜同日盤後 ~14:30 TW｜交易日 + 17:00 後可信」；
#: 寫入端 cron `.github/workflows/update_macro_history.yml` 排程 `0 9 * * *`（UTC 09:00 ＝ 台北 17:00）。
#: ⚠️ 這是 **K 線圖顯示資料的有效性守衛**，獨立於 VN1-PG-CUTOFF-VERIFY／DEC-070
#: （⛔ 不是 Risk Cap 規則、⛔ 不是投資門檻），兩者不得互相引用或連動。
TWII_BAR_TRUSTED_AFTER_TAIPEI_HOUR: int = 17

#: 台北時區名稱（IANA）。台灣自 1979 年起無日光節約，`zoneinfo` 不可用時退回固定 UTC+8 結果相同。
TAIPEI_TZ_NAME: str = "Asia/Taipei"

# ── 原因碼（first violation wins；`OHLC_OK` ＝ 合格）─────────────────────────────
OHLC_OK: str = ""
EMPTY: str = "EMPTY"                          # 視窗沒有任何一列
LENGTH_MISMATCH: str = "LENGTH_MISMATCH"      # 日期／開高低收／fetched_at 長度不一致
BAD_DATE: str = "BAD_DATE"                    # 日期不是 'YYYY-MM-DD'
NOT_FINITE: str = "NOT_FINITE"                # 開高低收有 NaN／inf／非數值
NON_POSITIVE: str = "NON_POSITIVE"            # 開高低收 ≤ 0
OHLC_RELATION: str = "OHLC_RELATION"          # 違反 low ≤ min(open,close) ≤ max(open,close) ≤ high
DUPLICATE_DATE: str = "DUPLICATE_DATE"        # 日期重複
NOT_ASCENDING: str = "NOT_ASCENDING"          # 日期未嚴格升序
FUTURE_DATE: str = "FUTURE_DATE"              # 日期晚於 today
FETCHED_AT_MISSING: str = "FETCHED_AT_MISSING"  # fetched_at 缺／無法解析／naive（判不出時區）
INCOMPLETE_BAR: str = "INCOMPLETE_BAR"        # 抓取時間早於該日 17:00（台北）→ 可能是盤中未完成棒
AS_OF_MISMATCH: str = "AS_OF_MISMATCH"        # 呼叫端給的 as_of ≠ 視窗最後一日（卡片與圖不同源）
# ── 以下兩碼**只給呼叫端（L3）用**，`validate_ohlc_window` 本身不會回傳 ─────────────────
READ_FAILED: str = "READ_FAILED"              # 讀取 OHLC 快取時丟例外（系統真出錯）
WINDOW_MISMATCH: str = "WINDOW_MISMATCH"      # OHLC 視窗與收盤卡序列不是同一批列（同快照自檢失敗）

#: 全部原因碼（測試與消費端判讀用）。
OHLC_REASON_CODES: frozenset = frozenset({
    EMPTY, LENGTH_MISMATCH, BAD_DATE, NOT_FINITE, NON_POSITIVE, OHLC_RELATION, DUPLICATE_DATE,
    NOT_ASCENDING, FUTURE_DATE, FETCHED_AT_MISSING, INCOMPLETE_BAR, AS_OF_MISMATCH,
    READ_FAILED, WINDOW_MISMATCH,
})


def taipei_tz():
    """Asia/Taipei tzinfo（供呼叫端換算台北時間；本模組自身不讀時鐘）。"""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(TAIPEI_TZ_NAME)
    except Exception:  # noqa: BLE001 — 系統缺 tzdata：台灣無 DST，固定 UTC+8 等價（CLAUDE.md §4.5 既有作法）
        return timezone(timedelta(hours=8))


def _parse_iso_date(v) -> Optional[date]:
    if not isinstance(v, str):
        return None
    try:
        return date.fromisoformat(v.strip())
    except ValueError:
        return None


def _parse_fetched_at_taipei(v) -> Optional[datetime]:
    """ISO datetime 字串 → 台北時間；缺／非字串／無法解析／naive → None（判不出來，fail-closed）。"""
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        _dt = datetime.fromisoformat(v.strip())
    except ValueError:
        return None
    if _dt.tzinfo is None or _dt.tzinfo.utcoffset(_dt) is None:
        return None                       # naive：不知道是 UTC 還是台北，⛔ 不猜
    return _dt.astimezone(taipei_tz())


def _as_float(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def validate_ohlc_window(
    dates: Sequence[str],
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    fetched_at: Sequence[Optional[str]],
    *,
    as_of: Optional[str],
    today: date,
) -> tuple[bool, str, str]:
    """驗證一段日 K 視窗（**視窗＝呼叫端傳入的全部列**，本函式不切、不剔除）。

    Args:
        dates: ISO 'YYYY-MM-DD'，應嚴格升序且唯一。
        opens／highs／lows／closes: 有限正值，且 low ≤ min(open,close) ≤ max(open,close) ≤ high。
        fetched_at: 每列抓取時間（ISO datetime，須帶時區）；用來判斷是否已收盤（台北 17:00 後）。
            ⚠️ `fetched_at` 是抓取時間，**不是**歷史 PIT 可得時間證據；本契約只拿它判「是否盤中未完成」。
        as_of: 卡片端的資料日（ISO）；非 None 時必須等於視窗最後一日（卡片與圖同源）。
        today: 基準日（呼叫端注入，台北今日）；任何日期晚於它 → FUTURE_DATE。

    Returns:
        `(ok, code, detail)`：合格 → `(True, OHLC_OK, "")`；否則 `(False, <原因碼>, <含日期的說明>)`。
        first violation wins：依列順序逐列檢查，每列依「日期 → 數值 → 關係 → 順序 → 未來日 → 抓取時間 → 完整性」，
        全列通過後再檢查 as_of。
    """
    _n = len(dates)
    if _n == 0:
        return False, EMPTY, "OHLC 視窗沒有任何一列"
    _lens = (len(opens), len(highs), len(lows), len(closes), len(fetched_at))
    if any(_l != _n for _l in _lens):
        return False, LENGTH_MISMATCH, (f"長度不一致：dates={_n}、open/high/low/close/fetched_at={_lens}")

    _prev: Optional[date] = None
    for _i in range(_n):
        _raw_d = dates[_i]
        _d = _parse_iso_date(_raw_d)
        if _d is None:
            return False, BAD_DATE, f"第 {_i + 1} 列日期無法解析：{_raw_d!r}"
        _ds = _d.isoformat()

        _vals = {}
        for _name, _seq in (("open", opens), ("high", highs), ("low", lows), ("close", closes)):
            _f = _as_float(_seq[_i])
            if _f is None or not math.isfinite(_f):
                return False, NOT_FINITE, f"{_ds} {_name}={_seq[_i]!r} 不是有限數值"
            _vals[_name] = _f
        for _name in ("open", "high", "low", "close"):
            if _vals[_name] <= 0:
                return False, NON_POSITIVE, f"{_ds} {_name}={_vals[_name]!r} 不是正值"

        _o, _h, _l, _c = _vals["open"], _vals["high"], _vals["low"], _vals["close"]
        if not (_l <= min(_o, _c) and max(_o, _c) <= _h):
            return False, OHLC_RELATION, (f"{_ds} 違反 low ≤ min(open,close) ≤ max(open,close) ≤ high："
                                          f"open={_o} high={_h} low={_l} close={_c}")

        if _prev is not None:
            if _d == _prev:
                return False, DUPLICATE_DATE, f"{_ds} 日期重複"
            if _d < _prev:
                return False, NOT_ASCENDING, f"{_ds} 排在 {_prev.isoformat()} 之後，日期未升序"
        _prev = _d

        if _d > today:
            return False, FUTURE_DATE, f"{_ds} 晚於今日 {today.isoformat()}"

        _fa = _parse_fetched_at_taipei(fetched_at[_i])
        if _fa is None:
            return False, FETCHED_AT_MISSING, (f"{_ds} 抓取時間缺、無法解析或未帶時區：{fetched_at[_i]!r}"
                                               f"（判不出是否已收盤，fail-closed）")
        _fd = _fa.date()
        if not (_fd > _d or (_fd == _d and _fa.hour >= TWII_BAR_TRUSTED_AFTER_TAIPEI_HOUR)):
            return False, INCOMPLETE_BAR, (f"{_ds} 抓取於台北 {_fa.isoformat()}，早於該日 "
                                           f"{TWII_BAR_TRUSTED_AFTER_TAIPEI_HOUR}:00，可能是盤中未完成棒")

    _last = _prev.isoformat() if _prev is not None else ""
    if as_of is not None and as_of != _last:
        return False, AS_OF_MISMATCH, f"卡片資料日 {as_of!r} ≠ 圖最後一日 {_last!r}"
    return True, OHLC_OK, ""
