"""L1 Repository — 盤後三大法人買賣超 (TWSE T86 / TPEx)。

TWSE 回傳單位為「股」,出口轉「張」(/1000)。純解析 `_parse_t86_day` 與 I/O 分離,
可離線單測。缺料 Fail Loud,不 fillna(0)（§1）。
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..core.circuit_breaker import require
from ..core.provenance import prov_log, stamp_df
from ..core.schemas import ChipSchema, validate_or_reject

_T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
_SHARES_PER_LOT = 1000.0


def _num(x) -> float:
    """把 '1,234' / '--' / '' 轉 float；無法解析回 NaN（不腦補 0）。"""
    if x is None:
        return float("nan")
    s = str(x).replace(",", "").strip()
    if s in ("", "--", "---", "N/A"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def _find_col(fields: list[str], *needles: str) -> int | None:
    """回傳第一個「同時包含所有 needle 子字串」的欄位索引。"""
    for i, f in enumerate(fields):
        if all(n in f for n in needles):
            return i
    return None


def _parse_t86_day(payload: dict, ticker_code: str) -> dict | None:
    """從一日 T86 JSON 取出某代號的三大法人淨買賣超（張）。

    找不到該股 → None（當日無交易/非該市場）。單位股→張。
    """
    fields = payload.get("fields") or []
    data = payload.get("data") or []
    if not fields or not data:
        return None
    i_code = _find_col(fields, "證券代號")
    i_foreign = (_find_col(fields, "外陸資買賣超股數")
                 or _find_col(fields, "外資買賣超股數"))
    i_trust = _find_col(fields, "投信買賣超股數")
    i_dealer = _find_col(fields, "自營商買賣超股數")
    require(i_code is not None, "T86 缺『證券代號』欄")
    for row in data:
        if str(row[i_code]).strip() == ticker_code:
            def lots(idx):
                return (_num(row[idx]) / _SHARES_PER_LOT) if idx is not None else float("nan")
            return {
                "foreign_net": lots(i_foreign),
                "trust_net": lots(i_trust),
                "dealer_net": lots(i_dealer),
            }
    return None


def _bare_code(ticker: str) -> str:
    """'2330.TW' → '2330'。"""
    return ticker.split(".")[0].strip()


def fetch_chip_history(ticker: str, *, days: int = 20,
                       session=None) -> pd.DataFrame:
    """近 N 個日曆日的三大法人淨買賣超（張）。

    逐日打 TWSE T86；假日/無資料日自然略過。全期無資料 → Fail Loud。
    """
    import requests

    require(days > 0, "days 必須 > 0")
    code = _bare_code(ticker)
    sess = session or requests.Session()
    rows: list[dict] = []
    today = date.today()
    for d in range(days):
        day = today - timedelta(days=d)
        if day.weekday() >= 5:  # 週末跳過
            continue
        try:
            resp = sess.get(_T86_URL,
                            params={"date": day.strftime("%Y%m%d"),
                                    "selectType": "ALL", "response": "json"},
                            timeout=10)
            if resp.status_code != 200:
                continue
            parsed = _parse_t86_day(resp.json(), code)
        except Exception:  # noqa: BLE001 - 單日失敗不致命,續抓其他日
            continue
        if parsed is not None:
            parsed["date"] = pd.Timestamp(day)
            rows.append(parsed)

    require(len(rows) > 0,
            f"{ticker} 近 {days} 日查無三大法人資料（來源封鎖或代碼非上市）")
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df = df[["date", "foreign_net", "trust_net", "dealer_net"]]
    df = validate_or_reject(df, ChipSchema, name="Chip")
    stamp_df(df, source=f"TWSE:T86:{code}")
    prov_log("fetch_chip_history", source=f"TWSE:T86:{code}",
             summary=f"{len(df)} days", ticker=ticker)
    return df
