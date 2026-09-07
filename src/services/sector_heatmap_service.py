"""src/services/sector_heatmap_service.py — 產業熱力圖的 L3 編排(2026-09-07)。

IA v2 頁2「🔍 找標的 › 板塊地圖」左半要畫熱力圖。本檔把「**要抓哪些標的、
抓回來之後覆蓋率是多少**」這段編排從 L5 拉出來,讓 UI 端只剩「畫」。

## 它做什麼 / 不做什麼

- **做**:查 L0 的類股宇宙 → 展平成一次 batch 的 ticker 清單 → 呼叫**既有**的
  L3 `services.etf_sector_service.get_sector_returns()` → 算覆蓋率 → 回**純 dict**。
- **不做**:不自己抓資料(取數在 L1,本檔只經既有 L3 wrapper 轉一手)、
  不畫圖(treemap 組裝在 L4 `ui.render.sector_heatmap_render`)、
  不決定顯示什麼顏色什麼文案(那是 UI 的事)。

## 為什麼**不是**再開一支 L1 直呼

`get_sector_returns()` 已經封裝了 `refresh` 時的 cache invalidation
(L4 直接 `.clear()` L1 cache 那個 anti-pattern 就是被它收掉的)。
本檔再繞過它直呼 L1,等於把那個 anti-pattern 從 L4 搬到 L3。

## §1 Fail Loud —— 三種「沒有數字」在本檔的處置

1. **區間標籤不合法** → L0 `lookback_trading_days()` 直接 `raise ValueError`,
   本檔**不接**(呼叫端傳錯屬 bug,不是資料問題)。
2. **上游取數拋例外** → **原樣往上拋**,本檔不吞、不回一份空 dict 冒充
   「今天大家都沒漲跌」。UI 端負責轉成看得見的紅態。
3. **抓回來是空的 / 只抓到一部分** → 這**不是**例外(L1 對網路失敗是
   fail-soft:印 log + 缺的 ticker 不入 dict)。本檔照實回報:
   `returns` 只含真的抓到的、`coverage` 講清楚母層與子成分各抓到幾個。
   ⚠️ **缺的 ticker 一律不出現在 `returns` 裡,絕不填 0** ——
   0 在熱力圖上會被畫成「持平」,與「沒有資料」長得一模一樣(§1 造假)。

零 streamlit、零 plotly、零 pandas —— 本檔只搬 dict。
"""
from __future__ import annotations

from typing import Any

from shared.sector_heatmap import (
    TW_SINGLE_STOCK_PROXY_DISCLOSURE,
    coverage_counts,
    flatten_tickers,
    lookback_trading_days,
    sector_universe,
)

#: 市場的顯示名。
#: ⚠️ **這兩個字串在 repo 內不只一份**:`ui/render/etf_render.render_sector_heatmap()`
#: 內另有一份 inline 的 `'美股 GICS' if is_us else '台股類股'`。**刻意不去合併** ——
#: 那支函式被 `tests/test_etf_render_heatmap_gate.py` 以 `inspect.getsource` 當
#: golden 釘住(防「進頁即冷抓」回退),改它的函式體會讓那道守衛失去比對基準。
#: 兩邊字面相同是**目前的事實**,不是被機制保證的;要改字的人請兩邊一起改。
MARKET_LABEL_US: str = '美股 GICS'
MARKET_LABEL_TW: str = '台股類股'


def get_sector_heatmap_view(is_us: bool, period_label: str, *,
                            refresh: bool = False) -> dict[str, Any]:
    """產業熱力圖要畫的一整份東西(純 dict,呼叫端不必再回頭問任何人)。

    Args:
        is_us: True → 美股 GICS 11 大類股 ETF;False → 台股代表股。
        period_label: UI 區間標籤(`shared.sector_heatmap.SECTOR_PERIOD_LABELS`,
            即 `'1日' / '5日' / '1月' / '3月'`)。**不是** yfinance 的下載窗字串。
        refresh: True → 要求上游清 cache 重抓。

    Returns:
        ```
        {
          'is_us': bool,
          'market_label': str,          # 給 treemap root 節點用
          'period_label': str,
          'n_bars': int,                # 這個標籤等於幾個交易日(口徑揭露用)
          'single_stock_proxy': bool,   # 台股 True:每個「類股」其實是一檔代表股
          'disclosure': str,            # 上一項為 True 時要印給使用者看的那段話
          'sectors': dict,              # L0 的類股宇宙(母層 → name / sub)
          'returns': dict,              # {ticker: rate_pct};抓不到的**不在裡面**
          'requested_n': int,           # 這一輪送出去抓幾檔
          'coverage': SectorCoverage,   # 母層 / 子成分 各抓到幾個、共幾個
        }
        ```

    Raises:
        ValueError: `period_label` 不在 L0 SSOT(§1:不猜預設值)。
        Exception: 上游取數拋什麼就往上拋什麼(§1:不吞、不回假空)。
    """
    _n_bars = lookback_trading_days(period_label)      # 先炸掉不合法的標籤
    _sectors, _proxy = sector_universe(is_us)
    _tickers = flatten_tickers(_sectors)

    from src.services.etf_sector_service import get_sector_returns
    _returns = get_sector_returns(_tickers, period_label, refresh=refresh)
    _returns = dict(_returns) if isinstance(_returns, dict) else {}

    return {
        'is_us': bool(is_us),
        'market_label': MARKET_LABEL_US if is_us else MARKET_LABEL_TW,
        'period_label': period_label,
        'n_bars': _n_bars,
        'single_stock_proxy': _proxy,
        'disclosure': TW_SINGLE_STOCK_PROXY_DISCLOSURE if _proxy else '',
        'sectors': _sectors,
        'returns': _returns,
        'requested_n': len(_tickers),
        'coverage': coverage_counts(_sectors, _returns),
    }
