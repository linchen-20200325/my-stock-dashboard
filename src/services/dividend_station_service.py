"""L3 Service — 💰 存股戰情室編排（讀清單 → 抓數 → L2 評估 → 組表）。

§8.2 L3：編排 L1 抓取 + L2 純函式,不自算指標。純組表 `build_station_rows` /
`row_from_assessment` 與 I/O 分離（`metrics_fn` 依賴注入）,離線可單測；真正的
逐檔抓取 `fetch_metrics`（週K/折溢價/配息/夏普/3年報酬/同儕）需部署端網路。

§1：逐檔抓取失敗 → 該列標「資料不足/抓取失敗」,不炸整張表、不捏造數字。
"""
from __future__ import annotations

from typing import Callable

from shared import dividend_station_thresholds as T
from src.compute.etf import dividend_station as ds

_CLASS_ICON = {T.ASSET_CORE: "🛡️ 核心", T.ASSET_SATELLITE: "🚀 衛星"}


def row_from_assessment(a: ds.HoldingAssessment) -> dict:
    """HoldingAssessment → 表格一列（純函式）。"""
    _add = f"{a.light.deploy_pct:.0f}%" if a.light.deploy_pct else ""
    _is_stock = a.asset_kind == T.KIND_STOCK
    return {
        "代號": a.ticker,
        "名稱": a.name,
        "種類": "個股" if _is_stock else "ETF",
        "類別": _CLASS_ICON.get(a.asset_class, a.asset_class),
        "健檢": a.worst_health,
        "235 燈號": f"{a.light.icon} {a.light.label}",
        "加碼金": _add,
        "3-3-3": ("—" if _is_stock
                  else ("✅ 合格" if a.screen.passed
                        else ("❔ 待資料"
                              if None in (a.screen.inception_ok, a.screen.return_ok, a.screen.peer_ok)
                              else "❌ 未過"))),
        "建議動作": ds.suggest_action(a),
        # 展開明細（UI 下鑽用；不進主表）
        "_detail": {
            "健檢A": a.health_a.msg, "健檢B": a.health_b.msg,
            "健檢C": a.health_c.msg, "健檢D": a.health_d.msg,
            "235觸發": "、".join(a.light.reasons),
            "深水防守": a.light.deepwater_note or "—",
            "3-3-3明細": a.screen.detail,
        },
    }


def _error_row(ticker: str, name: str, asset_class: str, asset_kind: str, reason: str) -> dict:
    return {
        "代號": ticker, "名稱": name,
        "種類": "個股" if asset_kind == T.KIND_STOCK else "ETF",
        "類別": _CLASS_ICON.get(asset_class, asset_class),
        "健檢": "⚪", "235 燈號": "—", "加碼金": "", "3-3-3": "—",
        "建議動作": f"⚠️ 資料不足/抓取失敗：{reason}",
        "_detail": {"error": reason},
    }


def build_station_rows(holdings: list[dict], *, vix: float | None,
                       metrics_fn: Callable[[str, str], dict]) -> list[dict]:
    """逐檔評估 → 組表。metrics_fn(ticker) 回一 dict 指標（依賴注入,離線可測）。

    holdings: [{'ticker','name','asset_class'}, ...]
    metrics_fn 需回：weekly_close(必要) + premium_pct/sharpe/total_return_1y_pct/
      annual_yield_pct/inception_years/ann_return_3y_pct/cum_return_3y_pct/peer_ranks（可缺）。
    """
    rows: list[dict] = []
    for h in (holdings or []):
        tk = str(h.get("ticker", "") or "").strip()
        nm = str(h.get("name", "") or "")
        ac = h.get("asset_class", T.ASSET_CORE)
        ak = h.get("asset_kind", T.KIND_ETF)         # stock / etf（fetcher 分流 + 適用性）
        if not tk:
            continue
        try:
            m = metrics_fn(tk, ak)
            a = ds.assess_holding(
                ticker=tk, name=nm or str(m.get("name", "")), asset_class=ac,
                asset_kind=ak, weekly_close=m["weekly_close"], vix=vix,
                premium_pct=m.get("premium_pct"), sharpe=m.get("sharpe"),
                total_return_1y_pct=m.get("total_return_1y_pct"),
                annual_yield_pct=m.get("annual_yield_pct"),
                inception_years=m.get("inception_years"),
                ann_return_3y_pct=m.get("ann_return_3y_pct"),
                cum_return_3y_pct=m.get("cum_return_3y_pct"),
                peer_ranks=m.get("peer_ranks"))
            rows.append(row_from_assessment(a))
        except Exception as e:  # noqa: BLE001 — 單檔失敗不炸整表（§1 誠實標記）
            rows.append(_error_row(tk, nm, ac, ak, f"{type(e).__name__}: {e}"))
    return rows


# ── 真實抓取（部署端網路才跑得到；沙箱代理擋 TW/yfinance）────────────────
def fetch_vix() -> float | None:
    """最新 VIX（^VIX 收盤）。抓不到 → None（§1 不猜,235 該條件不觸發）。"""
    try:
        import yfinance as yf
        _df = yf.Ticker("^VIX").history(period="5d")
        if _df is not None and not _df.empty:
            return float(_df["Close"].dropna().iloc[-1])
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] VIX 抓取失敗: {type(_e).__name__}: {_e}")
    return None


def fetch_metrics(ticker: str, asset_kind: str = T.KIND_ETF) -> dict:
    """逐檔抓 L2 所需指標（best-effort;缺的回 None → 該項標資料不足）。

    日線走 L1 `fetch_etf_price`（proxy-aware、auto_adjust；**本質是 yfinance 歷史,個股
    2330.TW 亦適用**）→ 週K + 報酬 + 夏普 + 成立年；配息走 `fetch_etf_dividends`→ 年化
    配息率（個股亦可）。折溢價 `fetch_etf_nav_history` **僅 ETF**（個股無 iNAV,跳過）。
    ⚠️ 需部署端網路（沙箱代理擋）。日線為必要,無則 raise（該列標抓取失敗,§1 誠實不假裝）。
    同儕排名（3-3-3 ③）Phase 2 未接 → peer_ranks=None。
    """
    import pandas as pd
    from src.compute.etf import normalize_etf_ticker

    # ⚠️ 台股代碼須補 .TW(0056→0056.TW) 再抓,否則 fetch_etf_price/yfinance 抓空 →
    # 每檔 raise「無日線」= 整排 error(部署端實測回報)。既有 ETF 分頁都先做這步。
    _yf = normalize_etf_ticker(ticker) or ticker

    # 1) 日線（還原價）→ 週K（必要）。normalize 一律補 .TW（上市）;抓空 → 試 .TWO（上櫃,
    #    稽核 MED:上櫃存股 5314/8069 等 yfinance 用 .TWO,否則整檔 error）。
    try:
        from src.data.etf.etf_fetch import fetch_etf_price   # EX-PASSTHRU-1
        _px = fetch_etf_price(_yf, period="5y")
        if (_px is None or getattr(_px, "empty", True)) and _yf.endswith(".TW"):
            _alt = _yf[:-3] + ".TWO"
            _px2 = fetch_etf_price(_alt, period="5y")
            if _px2 is not None and not getattr(_px2, "empty", True):
                _px, _yf = _px2, _alt        # 上櫃命中 → 後續配息/折溢價亦改用 .TWO
    except Exception as _e:  # noqa: BLE001
        raise ValueError(f"{ticker} 日線抓取失敗: {type(_e).__name__}: {_e}") from _e
    if _px is None or getattr(_px, "empty", True):
        raise ValueError(f"{ticker} 無日線資料（.TW/.TWO 皆無;部署端網路或代碼確認）")
    _col = next((c for c in ("Close", "close") if c in _px.columns), None)
    if _col is None:
        raise ValueError(f"{ticker} 日線缺 Close 欄")
    _close = pd.Series(_px[_col]).dropna()
    if not isinstance(_close.index, pd.DatetimeIndex):
        _close.index = pd.to_datetime(_close.index)
    _close = _close.sort_index()
    weekly = ds.weekly_closes(_close)
    if weekly is None or len(weekly) == 0:
        raise ValueError(f"{ticker} 週K 為空")

    m: dict = {"weekly_close": weekly}
    _as_of = pd.Timestamp.today().normalize()
    _cur = float(_close.iloc[-1])

    def _close_before(days: int) -> float | None:
        _sub = _close.loc[:_as_of - pd.Timedelta(days=days)]
        return float(_sub.iloc[-1]) if len(_sub) else None

    # 成立年數（以 5y 資料窗估算,足以判定「≥3 年」門檻）
    m["inception_years"] = ds.inception_years(_close.index.min(), _as_of)
    # 報酬（還原價 → 已含息）
    m["total_return_1y_pct"] = ds.total_return_pct(_close_before(365), _cur)
    m["cum_return_3y_pct"] = ds.total_return_pct(_close_before(365 * 3), _cur)
    m["ann_return_3y_pct"] = ds.annualized_return_pct(_close_before(365 * 3), _cur, 3.0)
    # 夏普（週報酬,rf=0 簡化）
    m["sharpe"] = ds.sharpe_weekly(weekly)

    # 2) 年化配息率
    try:
        from src.data.etf.etf_fetch import fetch_etf_dividends
        _div = pd.Series(fetch_etf_dividends(_yf))
        if len(_div):
            _div.index = pd.to_datetime(_div.index)
            _ttm = float(_div[_div.index >= (_as_of - pd.Timedelta(days=365))].sum())
            m["annual_yield_pct"] = ds.annual_yield_pct(_ttm, _cur)
    except Exception as _e:  # noqa: BLE001 — 配息缺 → 健檢 A 標資料不足,不炸
        print(f"[dividend_station] {ticker} 配息缺: {type(_e).__name__}")

    # 3) 折溢價（TWSE MIS iNAV;欄位 g 已是「折溢價率(%)」,同單位比 1.5%）—— 僅 ETF
    if asset_kind == T.KIND_ETF:
        try:
            from src.data.etf.etf_fetch import fetch_etf_nav_history
            _nav = fetch_etf_nav_history(_yf)
            if _nav is not None and len(_nav):
                _pcol = next((c for c in _nav.columns if "折溢價" in str(c)), None)
                if _pcol:
                    m["premium_pct"] = float(
                        pd.to_numeric(_nav[_pcol], errors="coerce").dropna().iloc[-1])
        except Exception as _e:  # noqa: BLE001
            print(f"[dividend_station] {ticker} 折溢價缺: {type(_e).__name__}")

    # 同儕排名（3-3-3 ③）Phase 2 未接
    m["peer_ranks"] = None
    return m


def get_station_rows(holdings: list[dict]) -> tuple[list[dict], float | None]:
    """畫面入口：抓 VIX（一次）+ 逐檔 → 組表。回 (rows, vix)。"""
    vix = fetch_vix()
    rows = build_station_rows(holdings, vix=vix, metrics_fn=fetch_metrics)
    return rows, vix
