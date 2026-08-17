"""L0 Infra — 血緣追蹤 (資料憲法 §2.2).

每個關鍵數值都應能回答：哪來的、何時抓的、資料歸屬哪一天。
DataFrame 走 `df.attrs` 攜帶 provenance；純量走 DataPoint。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone


def utc_now_iso() -> str:
    """UTC ISO-8601（帶 'T' 與 'Z'），供 fetched_at 使用。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class DataPoint:
    """帶血緣的純量。value 之外一律不可變。"""
    value: float
    source: str                 # e.g. "yfinance:2330.TW", "TWSE:BFI82U"
    fetched_at: str             # UTC ISO-8601
    as_of: date | None = None   # 資料歸屬日（≠ 抓取日；PIT）
    is_proxy: bool = False      # 是否為備援/估計值
    meta: dict = field(default_factory=dict)


def stamp_df(df, *, source: str, as_of: date | None = None,
             is_proxy: bool = False):
    """把 provenance 蓋進 DataFrame.attrs，回傳同一個 df（就地）。"""
    df.attrs["source"] = source
    df.attrs["fetched_at"] = utc_now_iso()
    if as_of is not None:
        df.attrs["as_of"] = as_of.isoformat()
    df.attrs["is_proxy"] = bool(is_proxy)
    return df


def prov_log(fn_name: str, *, source: str, summary: str, ticker: str = "") -> None:
    """側寫審計 log（stderr），不影響回傳值。"""
    print(
        f"[prov] {fn_name} ticker={ticker or '-'} source={source} "
        f"fetched_at={utc_now_iso()} :: {summary}",
        file=sys.stderr,
    )
