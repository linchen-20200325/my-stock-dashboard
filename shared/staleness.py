# -*- coding: utf-8 -*-
"""shared/staleness.py — 資料時效 SSOT（L0 純函式，A~E backlog 批次2）。

第八份 review §3.1:時效驗證應發生在**資料回應層**(拿到資料當下),而非只在
cache 層或事後診斷燈號。核心 = 算「預期最新交易日」(扣週末 + 可選休市日),
與資料實際最新日期比對得 `staleness_days`,讓下游「即時多空判斷」強制過閘 ——
**過期資料可顯示,但必須標記,且不得餵給當下決策**(對應 STATE 記錄的 v18.442
ETF 假折溢價事故:過時 NAV 被硬戳今日 → 假 🔴 嚴禁追高)。

設計原則(§8.1 自評過度設計):
- **不硬編全年台股休市日曆**(維護負擔);只扣週末 + 呼叫端可選傳入 holidays set。
  真需要精確休市日(春節長假等)再由 caller 注入,本模組不預設。
- 純函式,無 I/O,無 streamlit 依賴 → 可單測、可被全層 import。
- 既有散落實作(app_stock_fetchers._expected_latest_trading_date)委派至此,消重複。
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional


def expected_latest_trading_day(
    today: Optional[_dt.date] = None,
    holidays: Optional[set] = None,
) -> _dt.date:
    """預期最新交易日:自 today 起,往前退到最近一個非週末、非休市日。

    Parameters
    ----------
    today : date | None
        基準日;None → `date.today()`(呼叫端可注入以利測試/時區控制)。
    holidays : set[date] | None
        休市日集合(選填)。台股春節長假等由 caller 注入;None → 只扣週末。

    Returns
    -------
    date
        最近的預期交易日(weekday 0-4 且不在 holidays)。
    """
    d = today or _dt.date.today()
    _hol = holidays or set()
    # 上限 400 次防禦(holidays 若被誤傳整年會停;正常 1-4 次即命中)
    for _ in range(400):
        if d.weekday() < 5 and d not in _hol:
            return d
        d -= _dt.timedelta(days=1)
    return d


def staleness_days(
    data,
    *,
    date_col: str = "date",
    today: Optional[_dt.date] = None,
    holidays: Optional[set] = None,
) -> Optional[int]:
    """資料最新日期距「預期最新交易日」幾個日曆天。

    Parameters
    ----------
    data : pd.DataFrame | date | datetime | str | pd.Timestamp | None
        - DataFrame:取 `data[date_col]` 的 max 為最新日
        - date/datetime/str/Timestamp:直接視為最新日
    date_col : str
        DataFrame 的日期欄名(預設 "date")。
    today / holidays : 同 expected_latest_trading_day。

    Returns
    -------
    int | None
        `(預期最新交易日 - 資料最新日).days`;無法判定(空/缺欄/無法解析)回 None。
        正數 = 落後;0 = 當期;負數(資料比預期新,罕見)= 亦回實際差值。
    """
    latest = _extract_latest_date(data, date_col=date_col)
    if latest is None:
        return None
    exp = expected_latest_trading_day(today=today, holidays=holidays)
    return (exp - latest).days


def gate_for_realtime(
    days: Optional[int],
    *,
    max_days: int = 1,
) -> tuple[bool, str]:
    """時效閘:回 (可否用於即時多空判斷, 使用者提示字串)。

    - days is None      → (False, 無法確認日期,暫不納入即時判斷)
    - days > max_days   → (False, N 交易日前資料,僅供歷史參考,未納入即時燈號)
    - 否則               → (True, "")

    §1 Fail-Loud:無法確認新鮮度時 fail-safe 排除(不假裝新鮮餵決策)。
    """
    if days is None:
        return False, "⚠️ 無法確認資料日期，暫不納入即時多空判斷。"
    if days > max_days:
        return False, (f"⚠️ 此數據為 {days} 天前的資料，僅供歷史參考，"
                       "未納入即時燈號。")
    return True, ""


def stale_tag(days: Optional[int], *, threshold: int = 40) -> str:
    """AI prompt 用的時效標籤:days > threshold → "[STALE:Nd] ",否則空字串。

    對齊 Fund 端既有「月度指標 >40 天注入 [STALE] 防 AI 當當期講」慣例,SSOT 化。
    """
    if days is not None and days > threshold:
        return f"[STALE:{days}d] "
    return ""


# ── 頻率感知「合理最舊」門檻(日曆天)──────────────────────────────────────
# 不同發布頻率的資料,其「自然發布延遲」差異極大;拿日頻標準套季頻會把「當期最新一筆」
# 誤標過期。門檻 = 該頻率下一筆資料「合理仍是最新」的最大 as_of 年齡,超過才算真過期。
STALE_DAYS_DAILY = 7          # 日頻(報價/三大法人/大盤 regime):扣週末+短假仍應 ≤7d
STALE_DAYS_MONTHLY = 45       # 月頻(月營收/CPI 級):月後~10-13d 公布 + 一個月週期 → ~45d
STALE_DAYS_QUARTERLY = 150    # 季頻(台股季報):as_of=季末,季後~45d 才公告,下一季相隔~91d →
                              #   最新一季在下季公告前 as_of 年齡可達~136d;+FinMind 鏡像寬限~14d
                              #   = 91+45+14 = 150d。(例:力積電 Q1 as_of 3/31,7/15 為 106d < 150d
                              #   → 仍是最新一季,不該標過期;若 9 月還停在 Q1 → >150d 正確標過期)

_STALE_DAYS_BY_CADENCE = {
    "daily": STALE_DAYS_DAILY,
    "monthly": STALE_DAYS_MONTHLY,
    "quarterly": STALE_DAYS_QUARTERLY,
}


def stale_days_threshold(cadence: str = "daily") -> int:
    """依資料發布頻率回「合理最舊」門檻(日曆天)。

    未知 / 未指定 cadence → 退 daily(最嚴門檻;§1 Fail-Loud 寧可保守標過期也不放水)。
    """
    return _STALE_DAYS_BY_CADENCE.get(cadence, STALE_DAYS_DAILY)


# ── 內部:多型別日期萃取 ────────────────────────────────────────────────
def _extract_latest_date(data, *, date_col: str) -> Optional[_dt.date]:
    if data is None:
        return None
    # DataFrame(或有 columns 屬性者)
    _cols = getattr(data, "columns", None)
    if _cols is not None:
        try:
            if getattr(data, "empty", False) or date_col not in _cols:
                return None
            import pandas as _pd
            _s = _pd.to_datetime(data[date_col], errors="coerce").dropna()
            if _s.empty:
                return None
            return _s.max().date()
        except Exception:
            return None
    # date / datetime
    if isinstance(data, _dt.datetime):
        return data.date()
    if isinstance(data, _dt.date):
        return data
    # str / Timestamp 等 → 交給 pandas 寬鬆解析
    try:
        import pandas as _pd
        _ts = _pd.to_datetime(data, errors="coerce")
        if _ts is None or _pd.isna(_ts):
            return None
        return _ts.date()
    except Exception:
        return None
