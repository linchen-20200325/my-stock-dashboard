"""L3 Service — 從「我的持股」自動穿透曝險。

編排：讀持股 → 判斷 ETF（台股 00 開頭）→ 逐檔抓現價算市值 + 抓 ETF 成分 →
丟給 L2 `compute_penetrated_exposure` 去重複計數。

price_fn / holdings_fn 以**依賴注入**（預設接真實 L1 repo）,離線測試可注入假函式。
§1 Fail Loud：無現價的標的**跳過並回報**（不 fabricate 市值）；ETF 成分抓不到 →
holdings=None 交由穿透引擎標「不完整」。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core import constants as C
from ..core.circuit_breaker import FailLoudError, require
from ..repositories import etf_repo, market_repo
from ..repositories.sheets_repo import PoolStore
from .etf_overlap_calc import ExposureReport, compute_penetrated_exposure


def _bare(code: str) -> str:
    """'2330.TW' → '2330'（統一與 ETF 成分 key 對齊）。"""
    return str(code).split(".")[0].strip().upper()


def is_tw_etf(code: str) -> bool:
    """台股 ETF 代碼慣例：00 開頭（0050/0056/00878/006208…）。"""
    return _bare(code).startswith(C.TW_ETF_CODE_PREFIX)


@dataclass(frozen=True)
class PortfolioExposureResult:
    report: ExposureReport
    priced: list[str]                       # 有現價、納入計算的標的
    etf_tickers: list[str]                  # 被判定為 ETF 並嘗試穿透的標的
    skipped_no_price: list[dict] = field(default_factory=list)   # {ticker, reason}


def build_portfolio_exposure(
    store: PoolStore,
    *,
    price_fn=market_repo.fetch_latest_close,
    holdings_fn=etf_repo.fetch_etf_holdings,
    alias_map: dict[str, str] | None = None,
) -> PortfolioExposureResult:
    """讀持股組合 → 穿透曝險。"""
    holdings = store.list_holdings()
    require(len(holdings) > 0, "持股組合為空,無從計算穿透曝險")

    direct: list[dict] = []
    etfs: list[dict] = []
    priced: list[str] = []
    etf_tickers: list[str] = []
    skipped: list[dict] = []

    for h in holdings:
        code = h.get("ticker", "")
        lots = float(h.get("lots", 0) or 0)
        try:
            price = float(price_fn(code))
            require(price > 0, f"{code} 現價 <= 0")
        except FailLoudError as e:
            skipped.append({"ticker": code, "reason": str(e)})
            continue                        # 無現價 → 跳過,不捏造市值（§1）
        mv = lots * price * C.SHARES_PER_LOT
        priced.append(_bare(code))

        if is_tw_etf(code):
            etf_tickers.append(_bare(code))
            try:
                hd = holdings_fn(code)
            except FailLoudError:
                hd = None                   # 成分抓不到 → 穿透引擎標 incomplete
            etfs.append({"ticker": _bare(code), "market_value": mv, "holdings": hd})
        else:
            direct.append({"ticker": _bare(code), "market_value": mv})

    require(len(direct) + len(etfs) > 0,
            "所有標的皆無現價,無法計算穿透（請檢查代碼或資料來源）")
    report = compute_penetrated_exposure(direct, etfs, alias_map=alias_map)
    return PortfolioExposureResult(
        report=report, priced=priced, etf_tickers=etf_tickers,
        skipped_no_price=skipped,
    )
