"""shared/sector_heatmap.py — 產業熱力圖「區間口徑 / 缺值呈現」單一權威(L0 SSOT,B4-b)。

本檔為 B4-b 稽核(H-1 / H-3 / H-4 / H-9)的 SSOT 落點。原實作把三件事混在
`src/ui/render/etf_render.py` 的 inline magic number 裡,造成三類違憲:

1. **H-1 §4.1 量綱違反**:原 `_PERIOD_MAP = {'1日':'5d','5日':'1mo','1月':'3mo','3月':'6mo'}`
   只是 **yfinance 下載窗**,而 `_fetch_sector_returns` 用「整個下載窗的第一根」當基期
   (`series.iloc[0]`)。於是使用者選「1日」實際看到的是 ≈4 個交易日的累積報酬,
   全部標籤少算 4~6 倍(畫面出現「1日 NVDA +13.3%」這種不可能的數字)。
   → 修法:**下載窗**與**計算區間**徹底拆開。下載窗刻意放大(含假期緩衝),
   計算區間固定以 `SECTOR_LOOKBACK_TRADING_DAYS` 的 **bar 根數**回看。

2. **H-3 §1 造假**:缺資料的格子原本把顏色填 `0`,hover 顯示「+0.00%」——
   與真實「持平」無法區分。→ 本檔提供 `hover_value_text()` 讓缺值一律吐
   `HEATMAP_MISSING_TEXT`,顏色端由呼叫者傳 `None` 給 Plotly 留白。

3. **H-9 ValueError**:原 `max(abs(c) for c in colors if c != 0) or 5` 在「全部為 0」
   時炸 `max() arg is an empty sequence`。→ `color_span_pct()` 顯式處理空序列。

## §4.1 口徑定義(必讀)— 交易日,不是日曆日

本檔所有區間一律以 **交易日(trading day / K 棒根數)** 計,**不是日曆日**:

| UI 標籤 | 交易日(bars) | 依據 |
|---|---|---|
| `1日` | 1  | 最新收盤 vs 前一個交易日收盤 |
| `5日` | 5  | ≈ 1 週(TW/US 皆為週 5 個交易日) |
| `1月` | 21 | 月均交易日數(252 / 12) |
| `3月` | 63 | 季均交易日數(252 / 4) |

**為什麼用交易日而不是日曆日**:
- 資料本體(yfinance 日線)就是 bar 序列,`iloc[-1-n]` 天然是交易日位移;改用日曆日
  就得做 as-of 日期查找,而 US / TW 假日表不同(§4.6「多市場休市」),同一張圖裡
  兩個市場會取到不同 bar 數 → 又是一次量綱不一致。
- 與本專案既有慣例一致:`config.ANNUAL_MA = 240 trading days`、
  `signal_thresholds` 的 252、`macro_signal_lookback_tw.pct_change(20)` 皆為交易日。

**下載窗為何比計算區間大很多**:TW 有農曆年 9 天連假、US 有感恩節/耶誕連假,
`period='5d'` 在連假後可能只回 1~2 根 bar,連「1日」都算不出來。放大下載窗只是
多拿幾根 bar(同一次 batch request,成本近似不變),基期仍嚴格取第 `n` 根前。

## §1 Fail Loud

- 未知的 period label → `lookback_trading_days()` / `yf_download_window()` 直接
  `raise ValueError`,**不猜預設值**。
- bar 數不足 → `pct_change_over_bars()` 回 `None`(呼叫端必須顯示「無資料」),
  **不回 0、不 ffill**。
"""
from __future__ import annotations

import math
import re
from typing import Iterable, Sequence

# ══════════════════════════════════════════════════════════════
# §4.1 區間口徑 — 交易日(bars),非日曆日
# ══════════════════════════════════════════════════════════════
SECTOR_LOOKBACK_TRADING_DAYS: dict[str, int] = {
    '1日': 1,
    '5日': 5,
    '1月': 21,
    '3月': 63,
}

#: yfinance `period=` 下載窗。刻意 >= 對應 bar 數 × 2 + 連假緩衝(見 module docstring)。
#: **這不是計算區間** —— 計算區間一律讀 `SECTOR_LOOKBACK_TRADING_DAYS`。
SECTOR_YF_DOWNLOAD_WINDOW: dict[str, str] = {
    '1日': '1mo',   # ≈21 bars,需 2 根;涵蓋農曆年連假
    '5日': '2mo',   # ≈42 bars,需 6 根
    '1月': '6mo',   # ≈126 bars,需 22 根
    '3月': '1y',    # ≈252 bars,需 64 根
}

#: UI selectbox 的顯示順序 SSOT(dict 於 py3.7+ 保序)。
SECTOR_PERIOD_LABELS: tuple[str, ...] = tuple(SECTOR_LOOKBACK_TRADING_DAYS)

# ══════════════════════════════════════════════════════════════
# 熱力圖呈現常數(§3.3 反捏造:原為 etf_render inline magic number)
# ══════════════════════════════════════════════════════════════
#: 有資料節點的最小面積 —— 避免 ±0.0x% 的類股完全看不見。
HEATMAP_AREA_FLOOR_PARENT: float = 0.5
HEATMAP_AREA_FLOOR_SUB: float = 0.3
#: 缺資料節點的面積。**必須嚴格小於**對應的 floor —— 原實作給缺值 1.0(parent)/
#: 0.5(sub),比一檔真實 ±0.5% 的類股還大,等於讓「沒資料」霸佔版面。
HEATMAP_AREA_MISSING_PARENT: float = 0.25
HEATMAP_AREA_MISSING_SUB: float = 0.15
#: 全部節點皆缺值 / 皆為 0 時的色階跨度(%),供 cmin/cmax 對稱用。
HEATMAP_DEFAULT_COLOR_SPAN_PCT: float = 5.0
#: 缺值統一文案 —— 禁止用「+0.00%」冒充(§1)。
HEATMAP_MISSING_TEXT: str = '無資料'

_TICKER_SUFFIX_RE = re.compile(r'\.(TW|TWO)$', re.IGNORECASE)


# ══════════════════════════════════════════════════════════════
# 區間查表(§1:未知 label 一律 raise)
# ══════════════════════════════════════════════════════════════
def lookback_trading_days(period_label: str) -> int:
    """UI 區間標籤 → 回看的**交易日根數**。

    Raises:
        ValueError: label 不在 SSOT(§1 Fail Loud,不猜預設值)。
    """
    try:
        return SECTOR_LOOKBACK_TRADING_DAYS[period_label]
    except KeyError:
        raise ValueError(
            f'未知的產業熱力圖區間標籤 {period_label!r};'
            f'合法值(shared/sector_heatmap.SECTOR_LOOKBACK_TRADING_DAYS)='
            f'{list(SECTOR_LOOKBACK_TRADING_DAYS)}'
        ) from None


def yf_download_window(period_label: str) -> str:
    """UI 區間標籤 → yfinance `period=` 下載窗字串(**不是計算區間**)。

    Raises:
        ValueError: label 不在 SSOT(§1 Fail Loud)。
    """
    try:
        return SECTOR_YF_DOWNLOAD_WINDOW[period_label]
    except KeyError:
        raise ValueError(
            f'未知的產業熱力圖區間標籤 {period_label!r};'
            f'合法值(shared/sector_heatmap.SECTOR_YF_DOWNLOAD_WINDOW)='
            f'{list(SECTOR_YF_DOWNLOAD_WINDOW)}'
        ) from None


# ══════════════════════════════════════════════════════════════
# 報酬計算(純函式,無 I/O)
# ══════════════════════════════════════════════════════════════
def pct_change_over_bars(
    closes: Sequence[float] | Iterable[float],
    n_bars: int,
    *,
    ndigits: int = 2,
) -> float | None:
    """以「最後一根 vs 往前第 `n_bars` 根」計算區間報酬(%)。

    Args:
        closes: 已 **dropna** 的收盤價序列(時間遞增)。呼叫端不可先 ffill ——
            ffill 會把停牌日複製成同一個價,基期取到複製值後報酬恆為 0.00%
            (§4.6「停牌股票不可 ffill」)。
        n_bars: 回看的交易日根數(見 `SECTOR_LOOKBACK_TRADING_DAYS`)。
        ndigits: 四捨五入位數。

    Returns:
        報酬百分比(`rate_pct`,例:+1.23 表 +1.23%);
        **樣本不足 / 值非有限 / 基期 <= 0 一律回 `None`**(§1:留缺不填 0)。

    Raises:
        ValueError: `n_bars < 1`(呼叫端傳錯,屬 bug 不是資料問題)。
    """
    if n_bars < 1:
        raise ValueError(f'n_bars 必須 >= 1,收到 {n_bars}')
    vals = list(closes)
    if len(vals) < n_bars + 1:
        return None
    try:
        last = float(vals[-1])
        base = float(vals[-1 - n_bars])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(last) or not math.isfinite(base) or base <= 0:
        return None
    return round((last / base - 1.0) * 100.0, ndigits)


# ══════════════════════════════════════════════════════════════
# 呈現層純函式(缺值一律與真實 0% 區分)
# ══════════════════════════════════════════════════════════════
def node_area(ret_pct: float | None, *, is_parent: bool) -> float:
    """treemap 區塊面積。缺值面積**嚴格小於**任何有資料節點(H-3)。"""
    if ret_pct is None or not math.isfinite(float(ret_pct)):
        return HEATMAP_AREA_MISSING_PARENT if is_parent else HEATMAP_AREA_MISSING_SUB
    floor = HEATMAP_AREA_FLOOR_PARENT if is_parent else HEATMAP_AREA_FLOOR_SUB
    return max(abs(float(ret_pct)), floor)


def color_span_pct(colors: Iterable[float | None]) -> float:
    """色階對稱跨度 = max(|非零有限值|);全缺 / 全 0 時回預設(H-9 防空序列 ValueError)。"""
    vals = [
        abs(float(c)) for c in colors
        if c is not None and math.isfinite(float(c)) and float(c) != 0.0
    ]
    return max(vals) if vals else HEATMAP_DEFAULT_COLOR_SPAN_PCT


def direction_label(ret_pct: float | None) -> str:
    """排行表「方向」欄。缺值必須是「無資料」,**不可**落到「持平」(H-4)。"""
    if ret_pct is None or not math.isfinite(float(ret_pct)):
        return f'❓ {HEATMAP_MISSING_TEXT}'
    if float(ret_pct) > 0:
        return '📈 上漲'
    if float(ret_pct) < 0:
        return '📉 下跌'
    return '➡️ 持平'


def hover_value_text(ret_pct: float | None) -> str:
    """treemap hover 顯示字串。缺值吐「無資料」而非「+0.00%」(H-3)。"""
    if ret_pct is None or not math.isfinite(float(ret_pct)):
        return HEATMAP_MISSING_TEXT
    return f'{float(ret_pct):+.2f}%'


def sort_key_desc(ret_pct: float | None) -> float:
    """排行表排序鍵(搭配 `reverse=True`)。缺值排最後,**不可**當成 0.00% 插進真實報酬中間(H-4)。"""
    if ret_pct is None or not math.isfinite(float(ret_pct)):
        return float('-inf')
    return float(ret_pct)


# ══════════════════════════════════════════════════════════════
# 揭露(H-2):台股側的「類股」實為單一代表股
# ══════════════════════════════════════════════════════════════
def bare_code(ticker: str) -> str:
    """'2330.TW' → '2330';'XLK' → 'XLK'。"""
    return _TICKER_SUFFIX_RE.sub('', (ticker or '').strip())


def sector_display_name(name: str, ticker: str, *, single_stock_proxy: bool) -> str:
    """類股顯示名。

    `single_stock_proxy=True`(台股側)時**必須**把代表股代號寫進標籤 ——
    否則使用者會把「台積電的報酬」讀成「半導體類股平均」(§1 不可讓使用者誤以為
    那是類股平均)。美股側走真 GICS 類股 ETF(XLK/XLF...),不加註。
    """
    if not single_stock_proxy:
        return name
    return f'{name}（代表股 {bare_code(ticker)}）'


#: 台股側揭露文案 SSOT(熱力圖警示框 / AI prompt 兩處同源)。
#: **刻意寫成純文字**(無 markdown `**`、無 HTML tag)—— 因為它同時要進
#: `_colored_box`(走 `unsafe_allow_html`,markdown 不會被解析)與 AI prompt
#: (不該混入標記)。需要強調時由呼叫端自行包 `<b>`。
TW_SINGLE_STOCK_PROXY_DISCLOSURE: str = (
    '台股側沒有可用的類股指數日線資料源，此處每個「類股」是用該產業的'
    '單一代表權值股近似（例如「半導體」＝台積電 2330 這一檔的報酬），'
    '不是類股指數、也不是成分股平均。只能當「龍頭股強弱」看，'
    '不可解讀為整個產業的漲跌。美股側走真正的 GICS 類股 ETF（XLK／XLF…），無此限制。'
)
