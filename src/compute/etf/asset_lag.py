"""src/compute/etf/asset_lag.py — 資產分類 + 基準對映 + 落後燈號(L2 純函式)。

「組合體檢」的判定核心,零 I/O、零 streamlit,可單測。三支純函式:
  - classify_asset_kind(ticker)  : 代號 → 'etf' | 'stock' | 'unknown'(§4.6 不猜:非台股代號回 unknown)
  - pick_benchmark(kind)         : 資產類型 → 基準代號(ETF→0050.TW、個股→^TWII)
  - classify_lag_verdict(metrics): calc_weakness_metrics 的指標 → 燈號 + 動作建議

§3.3:門檻/基準全走 shared.signal_thresholds SSOT,不 inline。
§8.2:L2 純函式,只吃 dict/字串,取價與經理人抓取留在 L1/L3。

`classify_lag_verdict` 抽自 etf_calc.compute_etf_weakness_row 的燈號段(原 gate 在
`is_active_etf` → 個股/被動 ETF 拿不到燈號)。抽出後**不 gate on active**,ETF 與個股
共用同一份「落後燈號 SSOT」;經理人任期(tenure_days)僅 ETF 有,個股一律 None。
"""
from __future__ import annotations

from src.compute.etf.etf_helpers import bare_etf_code
from shared.signal_thresholds import (
    ETF_MANAGER_TENURE_NEW_DAYS,
    ETF_UP_DOWN_DAYS_THRESHOLD,
    LAG_ALERT_STREAK_QUARTERS,
    PORTFOLIO_BENCHMARK_TICKER,
    STOCK_BENCHMARK_TICKER,
)

ASSET_ETF = "etf"
ASSET_STOCK = "stock"
ASSET_UNKNOWN = "unknown"


def classify_asset_kind(ticker) -> str:
    """台股代號 → 'etf' | 'stock' | 'unknown'。

    台股慣例:ETF 代號一律 `00` 開頭(0050 / 00878 / 00980A);個股為 4 碼且首位 1-9
    (2330 / 6488)。非台股/指數代號(如 ^TWII、美股)→ 'unknown'(§4.6:不硬塞)。
    純前綴 heuristic,不臆造;誤判時使用者可於清單另標(MVP 不加 type 欄)。
    """
    code = bare_etf_code(ticker)
    if not code:
        return ASSET_UNKNOWN
    if code.startswith("00"):
        return ASSET_ETF
    if code[0].isdigit():
        return ASSET_STOCK
    return ASSET_UNKNOWN


def pick_benchmark(kind: str) -> str | None:
    """資產類型 → 基準代號。ETF→0050.TW、個股→^TWII、unknown→None(無法判定)。"""
    if kind == ASSET_ETF:
        return PORTFOLIO_BENCHMARK_TICKER
    if kind == ASSET_STOCK:
        return STOCK_BENCHMARK_TICKER
    return None


def classify_lag_verdict(metrics, *, is_etf: bool = False,
                         tenure_days=None) -> dict:
    """由 calc_weakness_metrics 指標裁定「落後燈號 + 動作建議」(純函式)。

    Args:
        metrics: calc_weakness_metrics 回傳的 dict(需含 down_ratio / up_ratio /
                 quarter_lose_streak)。含 '_err' 或缺鍵 → 回「⚪ 無法判定」(§1 不猜)。
        is_etf:  是否 ETF(僅 ETF 才判「新經理人再給時間」;個股無經理人)。
        tenure_days: ETF 現任經理人任期天數(個股/未知 → None)。

    Returns:
        {'燈號': str, '動作建議': str}。
    """
    if not isinstance(metrics, dict) or "_err" in metrics:
        return {"燈號": "⚪ 無法判定", "動作建議": "—"}
    if not all(k in metrics for k in ("down_ratio", "up_ratio", "quarter_lose_streak")):
        return {"燈號": "⚪ 無法判定", "動作建議": "—"}

    down = metrics.get("down_ratio") or 0
    up = metrics.get("up_ratio") or 0
    streak = metrics.get("quarter_lose_streak") or 0
    new_manager = (is_etf and isinstance(tenure_days, int)
                   and tenure_days < ETF_MANAGER_TENURE_NEW_DAYS)

    if streak >= LAG_ALERT_STREAK_QUARTERS:
        return {
            "燈號": f"🚨 連續{streak}季輸盤",
            "動作建議": ("⏳ 新經理人 <6 月，再給時間" if new_manager
                       else "考慮換到大盤被動式 ETF（如 0050）"),
        }
    if down > ETF_UP_DOWN_DAYS_THRESHOLD and up > ETF_UP_DOWN_DAYS_THRESHOLD:
        return {"燈號": "🔴 雙向弱勢", "動作建議": "近期表現雙向落後大盤；觀察 1-2 季"}
    if down > ETF_UP_DOWN_DAYS_THRESHOLD:
        return {"燈號": "🟡 大跌弱勢", "動作建議": "下跌防禦力不足，注意"}
    if up > ETF_UP_DOWN_DAYS_THRESHOLD:
        return {"燈號": "🟡 反彈無力", "動作建議": "反彈追不上大盤，績效落後"}
    return {"燈號": "🟢 體質正常", "動作建議": "續抱觀察"}
