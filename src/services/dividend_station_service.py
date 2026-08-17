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
    return {
        "代號": a.ticker,
        "名稱": a.name,
        "類別": _CLASS_ICON.get(a.asset_class, a.asset_class),
        "健檢": a.worst_health,
        "235 燈號": f"{a.light.icon} {a.light.label}",
        "加碼金": _add,
        "3-3-3": "✅ 合格" if a.screen.passed else "❌ 未過",
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


def _error_row(ticker: str, name: str, asset_class: str, reason: str) -> dict:
    return {
        "代號": ticker, "名稱": name,
        "類別": _CLASS_ICON.get(asset_class, asset_class),
        "健檢": "⚪", "235 燈號": "—", "加碼金": "", "3-3-3": "—",
        "建議動作": f"⚠️ 資料不足/抓取失敗：{reason}",
        "_detail": {"error": reason},
    }


def build_station_rows(holdings: list[dict], *, vix: float | None,
                       metrics_fn: Callable[[str], dict]) -> list[dict]:
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
        if not tk:
            continue
        try:
            m = metrics_fn(tk)
            a = ds.assess_holding(
                ticker=tk, name=nm or str(m.get("name", "")), asset_class=ac,
                weekly_close=m["weekly_close"], vix=vix,
                premium_pct=m.get("premium_pct"), sharpe=m.get("sharpe"),
                total_return_1y_pct=m.get("total_return_1y_pct"),
                annual_yield_pct=m.get("annual_yield_pct"),
                inception_years=m.get("inception_years"),
                ann_return_3y_pct=m.get("ann_return_3y_pct"),
                cum_return_3y_pct=m.get("cum_return_3y_pct"),
                peer_ranks=m.get("peer_ranks"))
            rows.append(row_from_assessment(a))
        except Exception as e:  # noqa: BLE001 — 單檔失敗不炸整表（§1 誠實標記）
            rows.append(_error_row(tk, nm, ac, f"{type(e).__name__}: {e}"))
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


def fetch_metrics(ticker: str) -> dict:
    """逐檔抓 L2 所需指標（best-effort;缺的回 None → 該項標資料不足）。

    週K 為必要（無則 raise 讓上層標該列失敗）；其餘缺失以 None 誠實降級。
    ⚠️ 需部署端網路：折溢價走 TWSE MIS（proxy）、價量走 FinMind/yfinance。
    """
    import pandas as pd

    weekly = None
    # 日收盤 → 週K（優先用 ETF 收盤歷史；退 yfinance）
    try:
        from src.data.etf.etf_fetch import fetch_etf_close_history  # EX-PASSTHRU-1
        _daily = fetch_etf_close_history(ticker)
        if _daily is not None and len(_daily):
            _s = _daily["close"] if "close" in getattr(_daily, "columns", []) else _daily
            _s = pd.Series(_s)
            if not isinstance(_s.index, pd.DatetimeIndex) and "date" in getattr(_daily, "columns", []):
                _s.index = pd.to_datetime(_daily["date"])
            weekly = ds.weekly_closes(_s)
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] {ticker} 週K 主源失敗: {type(_e).__name__}")
    if weekly is None or len(weekly) == 0:
        raise ValueError(f"{ticker} 無週K 資料（部署端網路/代碼確認）")

    m: dict = {"weekly_close": weekly}
    # 折溢價（TWSE MIS iNAV）
    try:
        from src.data.etf.etf_fetch import fetch_etf_nav_history
        _nav = fetch_etf_nav_history(ticker)
        if _nav is not None and len(_nav):
            _prem_col = next((c for c in _nav.columns if "折溢價" in str(c)), None)
            if _prem_col:
                m["premium_pct"] = float(pd.to_numeric(_nav[_prem_col], errors="coerce").dropna().iloc[-1])
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] {ticker} 折溢價缺: {type(_e).__name__}")
    # 其餘指標（配息率/報酬/夏普/成立年/3年報酬/同儕）留待部署端逐步接；
    # 缺失以 None 誠實降級（健檢/3-3-3 對應項標「資料不足」而非捏造）。
    return m


def get_station_rows(holdings: list[dict]) -> tuple[list[dict], float | None]:
    """畫面入口：抓 VIX（一次）+ 逐檔 → 組表。回 (rows, vix)。"""
    vix = fetch_vix()
    rows = build_station_rows(holdings, vix=vix, metrics_fn=fetch_metrics)
    return rows, vix
