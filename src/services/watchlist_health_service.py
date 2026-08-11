"""src/services/watchlist_health_service.py — 組合體檢逐檔落後判定(L3 service)。

編排:L1 取價(fetch_etf_price)+ L2 純判定(asset_lag / calc_weakness_metrics /
compute_portfolio_vs_benchmark)→ UI-ready 逐檔 rows。§8.2 L3:合法組合 L1 fetcher + L2
純函式(對齊 forward_test_service / sector_flow_service pattern);L5 UI 只呼叫本層。

職責:給一組使用者持股/清單代號,逐檔判「vs 基準(個股→^TWII、ETF→0050)是否落後」:
連續輸盤季數、相對基準累積報酬%、大跌/反彈弱勢率、燈號 + 動作建議。

§1 Fail Loud, Never Fake(全走既有誠實範式):
- 非台股代號(pick_benchmark 回 None)→ ⚪ 無法判定,不硬選基準。
- 抓不到價 / 基準抓不到 → ⚪ 價格資料不足,不補值不畫假。
- 新上市 <30 天(calc_weakness_metrics insufficient)→ ⚪ 樣本不足,不外推。
- 單檔抓取例外 → 該列標 ⚪ 抓取失敗,不中斷整張表(逐檔隔離)。
"""
from __future__ import annotations

from src.data.etf import fetch_etf_price
from src.compute.etf.etf_calc import (
    calc_weakness_metrics,
    compute_portfolio_vs_benchmark,
)
from src.compute.etf.etf_helpers import normalize_etf_ticker
from src.compute.etf.asset_lag import (
    ASSET_ETF,
    classify_asset_kind,
    classify_lag_verdict,
    pick_benchmark,
)

_KIND_LABEL = {"etf": "ETF", "stock": "個股", "unknown": "未知"}


def _base_row(ticker: str, kind: str, bench: str | None) -> dict:
    """一列的預設骨架(未判定前的欄位;§1 指標一律 None 不填 0)。"""
    return {
        "代號": ticker,
        "類型": _KIND_LABEL.get(kind, "未知"),
        "基準": bench or "—",
        "連敗季數": None,
        "相對基準%": None,       # (個股/ETF 累積報酬 − 基準累積報酬)×100;負=落後
        "大跌弱勢率%": None,
        "反彈弱勢率%": None,
        "樣本日": 0,
        "燈號": "⚪ 未檢測",
        "動作建議": "—",
    }


def _relative_pct(returns, bench_returns, ticker: str):
    """(該檔累積報酬 − 基準累積報酬)×100;基準對不上(§1)→ None,不畫假。"""
    vb = compute_portfolio_vs_benchmark({ticker: returns}, {ticker: 1.0}, bench_returns)
    if not vb.get("benchmark_ok"):
        return None
    _port = vb["final"].get("portfolio")
    _bench = vb["final"].get("benchmark")
    if _port is None or _bench is None:
        return None
    return round((_port - _bench) * 100, 1)


def evaluate_one(ticker: str, *, period: str = "1y") -> dict:
    """單檔體檢(純編排,可單測):代號 → 逐檔落後判定列。§1 全程誠實降級。"""
    kind = classify_asset_kind(ticker)
    bench = pick_benchmark(kind)

    if bench is None:                          # 非台股代號 → 不硬選基準(§4.6),不抓價
        row = _base_row(str(ticker).strip().upper(), kind, bench)
        row["燈號"] = "⚪ 無法判定（非台股代號）"
        return row

    # 清單多為裸碼(如 '2330'/'00980A');fetch_etf_price 走 yfinance 需 .TW/.TWO 後綴。
    # ⚠️ normalize 一律補 .TW → 上櫃(.TWO)股票會抓不到而落「價格資料不足」(§1 誠實降級,不亂猜)。
    _yf = normalize_etf_ticker(ticker)
    row = _base_row(_yf, kind, bench)

    try:
        _etf_df = fetch_etf_price(_yf, period=period)
        _bench_df = fetch_etf_price(bench, period=period)
        if _etf_df is None or _etf_df.empty or _bench_df is None or _bench_df.empty:
            row["燈號"] = "⚪ 價格資料不足"
            return row

        _er = _etf_df["Close"].pct_change()
        _br = _bench_df["Close"].pct_change()
        _m = calc_weakness_metrics(_er, _br)
        row["相對基準%"] = _relative_pct(_er, _br, _yf)   # 與燈號獨立,盡量算得出就給

        if "_err" in _m:                        # 新上市/樣本不足 → 誠實標,不外推
            row["燈號"] = f"⚪ 樣本不足 (n={_m.get('sample', 0)})"
            return row

        row["連敗季數"] = _m["quarter_lose_streak"]
        row["大跌弱勢率%"] = _m["down_ratio"]
        row["反彈弱勢率%"] = _m["up_ratio"]
        row["樣本日"] = _m["sample"]
    except Exception as _e:                     # 逐檔隔離:單檔炸不拖垮整表(§1 loud log)
        print(f"[watchlist_health/{ticker}] {type(_e).__name__}: {_e}")
        row["燈號"] = f"⚪ 抓取失敗：{type(_e).__name__}"
        return row

    # MVP:tenure_days=None(不抓經理人;新經理人特例僅影響 ETF streak 動作文案,之後可補)
    _verdict = classify_lag_verdict(_m, is_etf=(kind == ASSET_ETF), tenure_days=None)
    row["燈號"] = _verdict["燈號"]
    row["動作建議"] = _verdict["動作建議"]
    return row


def get_watchlist_health_rows(tickers, *, period: str = "1y") -> list[dict]:
    """一組清單代號 → 逐檔體檢 rows(去重保序)。空清單 → []。"""
    _seen: set[str] = set()
    out: list[dict] = []
    for _raw in (tickers or []):
        _t = str(_raw).strip().upper()
        if not _t or _t in _seen:
            continue
        _seen.add(_t)
        out.append(evaluate_one(_t, period=period))
    return out


def summarize_laggards(rows) -> list[dict]:
    """從體檢 rows 篩出「亮警示(🚨/🔴)」的落後標的(供摘要/未來推播)。"""
    return [r for r in (rows or [])
            if str(r.get("燈號", "")).startswith(("🚨", "🔴"))]
