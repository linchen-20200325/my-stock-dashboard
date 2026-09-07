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

## 本檔的類股表**涵蓋到哪裡**(2026-09-07 加,讀之前先看這段)

`US_SECTORS` / `TW_SECTORS` 是**熱力圖這一張圖**的類股宇宙。它們原本 inline 在
`src/ui/render/etf_render.py`(私有名 `_US_SECTORS` / `_TW_SECTORS`),2026-09-07
IA v2 頁2「🔍 找標的 › 板塊地圖」要用同一份宇宙時上移到 L0 ——
**兩個畫面讀同一份表**,舊分頁端改為別名轉發(`_US_SECTORS = US_SECTORS`)。

⛔ **本表不涵蓋下面這三處,它們各自維護、語意也不同 ——**
   **不可以拿本表去「統一」它們,那是行為變更**:

| 另外三處 | 位置 | 它在做什麼 | 為什麼併不得 |
|---|---|---|---|
| `_ETF_SECTOR_MAP` | `src/ui/render/etf_render.py` | ETF 代號 → GICS 類股**中文名**,給組合曝險集中度檢查用 | 對映方向與粒度都不同(它含 QQQ / SPY / 0050 / 債券 / 高股息這些**非類股** ETF),且**中文譯名刻意不同**:同一支 `XLK` 在那裡是「資訊科技」、在本表是「科技」;`XLV` 是「醫療保健」vs「醫療」;`XLB` 是「原材料」vs「原物料」。改任一邊的字串都會動到 `tests/test_sector_exposure_gate.py` 守著的曝險判定 |
| 攻守類股子集 | `src/compute/risk/risk_radar.py::_signal_sector_rotation` | 寫死 `("XLP","XLU","XLV")` vs `("XLK","XLY","XLF")` 兩組,算 30 日動能差 | 它要的是**攻擊 / 防禦兩個子集**,不是 11 大類股全集;本表沒有攻守屬性欄 |
| `ticker_sector.json` | `data_cache/sector_flow/`(由 cron 產,`src/data/sector_flow/reader.py` 讀) | **裸股號 → 產業別**,給三大法人資金泡泡圖標記持股板塊 | 那是**台股個股**的全市場對映(cron 產出的資料檔),不是「10 個代表股 + 子成分」這種手選清單;它會隨排程更新,本表是人工維護的常數 |

→ 也就是說:本檔對「熱力圖的類股宇宙」是單一來源,
**但「這個 repo 裡的類股分類」不是只有這一份**。
（`tests/test_sector_heatmap_universe_single_source.py` 只釘前者,不宣稱後者。）
"""
from __future__ import annotations

import math
import re
from typing import Iterable, NamedTuple, Sequence

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


# ══════════════════════════════════════════════════════════════
# 熱力圖的類股宇宙(2026-09-07 自 `src/ui/render/etf_render.py` 上移至 L0)
# ══════════════════════════════════════════════════════════════
# 上移的理由:IA v2 頁2「🔍 找標的 › 板塊地圖」與既有 🌍 市場環境 ›「🗺️ 產業
# 熱力圖」分頁要畫**同一份宇宙**。留在 L4 私有名的話,新頁只有兩條路 ——
# 跨檔直取底線私有符號(`CLAUDE.md §8.2.A.2` V-PICKER-PRIV-1 的前車之鑑),
# 或自己抄一份(第二個真相源,而且會無聲漂移)。上移到 L0 後兩邊讀同一份。
# ⚠️ 涵蓋範圍見 module docstring 最後一段:**本表不涵蓋**另外三處類股分類。

# ── 美股 11 大 GICS 類股 ETF ─────────────────────────────────
US_SECTORS: dict[str, dict] = {
    'XLK':  {'name': '科技',        'sub': ['AAPL','MSFT','NVDA','AVGO','AMD']},
    'XLF':  {'name': '金融',        'sub': ['JPM','BAC','WFC','GS','MS']},
    'XLE':  {'name': '能源',        'sub': ['XOM','CVX','COP','SLB','MPC']},
    'XLV':  {'name': '醫療',        'sub': ['LLY','UNH','JNJ','ABBV','MRK']},
    'XLI':  {'name': '工業',        'sub': ['GE','CAT','HON','UPS','BA']},
    'XLP':  {'name': '必需消費',    'sub': ['PG','KO','PEP','COST','WMT']},
    'XLU':  {'name': '公用事業',    'sub': ['NEE','SO','DUK','AEP','D']},
    'XLB':  {'name': '原物料',      'sub': ['LIN','APD','ECL','NEM','FCX']},
    'XLRE': {'name': '房地產',      'sub': ['PLD','AMT','EQIX','CCI','SPG']},
    'XLY':  {'name': '非必需消費',  'sub': ['AMZN','TSLA','HD','MCD','NKE']},
    'XLC':  {'name': '通訊服務',    'sub': ['META','GOOGL','NFLX','DIS','T']},
}

# ── 台股「類股」代表股 ────────────────────────────────────────
# ⚠️ B4-b H-2 揭露:以下 key **全部是個股**,不是類股指數、也不是成分股平均。
# 台股側沒有可用的類股指數日線資料源(查證結果見下),因此走「單一代表權值股近似」,
# 並在 UI 標籤 / caption / AI prompt 三處**明確揭露**(§1 寧可誠實標示,
# 不可讓使用者以為那是類股平均)。渲染時一律經
# `sector_display_name(..., single_stock_proxy=True)` 產生「半導體（代表股 2330）」
# 這種標籤。
#
# 【資料源查證】為什麼不改用真類股指數:
# - yfinance:無 TWSE 類股指數 ticker(僅 ^TWII 大盤 / ^TWOII 櫃買),拿不到日線序列。
# - TWSE `MI_INDEX`:確實含 29 檔類股指數,但**一次只回一個交易日**;要湊 63 根
#   bar 需 63 次 request,且本專案已在 `daily_data_fetchers.py` 標記
#   「🚫 TWSE MI_INDEX 已永久停用」(穩定性不足)。
# - FinMind:無類股指數 dataset(`TaiwanStockInfo.industry_category` 只有分類欄位,
#   要自行對數百檔成分股加權 → 屬新 L1 模組 + 新資料流,依 §8.1 需先送架構審。
# - 台股類股 ETF:僅科技(0052)/ 金融(0055)/ 電子(0053)等 3~4 個產業有,
#   塑化 / 鋼鐵 / 食品 / 航運 / 觀光 / 光電**沒有**對應 ETF,無法覆蓋整張圖。
# → 結論:走揭露路線。升級觸發條件:若日後接上可用的類股指數日線源,
#   把本表換成指數代號並將 `TW_SECTOR_SINGLE_STOCK_PROXY` 改 False 即可。
#
# 【B4-b 一併修掉的重複計數 / 錯分類 / 已下市】
# - `3008.TW`(大立光)原同時是「光電」母層 + 「電子製造」子成分 → 自電子製造移除。
# - `2409.TW`(友達,面板廠)原同時掛「電信」與「光電」→ 自電信移除(本就非電信股)。
# - `2475.TW`(華映)2019 已下市,永遠抓不到 → 移除(不猜替代標的)。
# - `9910.TW`(豐泰)是製鞋廠卻掛在「觀光」→ 母層改 `2707.TW`(晶華酒店)。
TW_SECTORS: dict[str, dict] = {
    '2330.TW': {'name': '半導體',    'sub': ['2303.TW','2308.TW','2454.TW','3711.TW','2379.TW']},
    '2317.TW': {'name': '電子製造',  'sub': ['2354.TW','2356.TW','2382.TW','3034.TW']},
    '2412.TW': {'name': '電信',      'sub': ['3045.TW','4904.TW']},
    '2882.TW': {'name': '金融',      'sub': ['2881.TW','2883.TW','2884.TW','2886.TW','2891.TW']},
    '1301.TW': {'name': '塑化',      'sub': ['1303.TW','1326.TW','1402.TW']},
    '2002.TW': {'name': '鋼鐵',      'sub': ['2006.TW','2007.TW','2010.TW']},
    '1216.TW': {'name': '食品',      'sub': ['1201.TW','1210.TW','1225.TW']},
    '2603.TW': {'name': '航運',      'sub': ['2609.TW','2615.TW','2617.TW']},
    '2707.TW': {'name': '觀光',      'sub': ['2731.TW','2727.TW']},
    '3008.TW': {'name': '光電',      'sub': ['2409.TW','3481.TW']},
}

#: 該市場的「類股」是否為單一代表股近似(H-2 揭露開關)。
#: 美股走真 GICS 類股 ETF(XLK/XLF…)→ False;台股走代表股 → True。
US_SECTOR_SINGLE_STOCK_PROXY: bool = False
TW_SECTOR_SINGLE_STOCK_PROXY: bool = True


def sector_universe(is_us: bool) -> tuple[dict[str, dict], bool]:
    """市場 → (類股宇宙, 該市場是否為單一代表股近似)。

    **兩個值一次回**是刻意的:呼叫端若分兩次查(一次拿表、一次拿旗標),
    就有可能拿到「美股的表 + 台股的旗標」——那會讓 XLK 被標成
    「科技（代表股 XLK）」,是一句假揭露(§1)。

    Args:
        is_us: True → 美股 GICS 11 大類股 ETF;False → 台股代表股。

    Returns:
        `(sectors, single_stock_proxy)`。`sectors` 是**本模組的 dict 物件本身**
        (不複製):呼叫端**不得就地修改**,要改請自己 `dict(...)`。
    """
    if is_us:
        return US_SECTORS, US_SECTOR_SINGLE_STOCK_PROXY
    return TW_SECTORS, TW_SECTOR_SINGLE_STOCK_PROXY


def flatten_tickers(sectors: dict[str, dict]) -> tuple[str, ...]:
    """類股宇宙 → 一次要抓的全部 ticker(母層 ＋ 子成分,去重)。

    **順序是穩定的**(母層依表序、每個母層後面接它的子成分,重複者只留第一次
    出現的位置)。⚠️ 這一點與 `etf_render.render_sector_heatmap()` 內那段
    等價的 inline 寫法**有一個差異**:那裡是 `tuple(set(...))`,而 `set` 的走訪
    順序受 `PYTHONHASHSEED` 影響 → 同一組標的在不同 process 會產生**不同的
    tuple**,而那個 tuple 正是 `@st.cache_data` 的 key,於是快取可能白白 miss。
    此處改成穩定去重,**只影響本函式的呼叫端**(舊分頁那段一個字都沒動)。

    Args:
        sectors: `{ticker: {'name': str, 'sub': [ticker, ...]}}`。

    Returns:
        去重後的 ticker tuple(hashable,可直接當 cache key)。
    """
    _out: list[str] = []
    _seen: set[str] = set()
    for _parent, _meta in (sectors or {}).items():
        for _t in (_parent, *( (_meta or {}).get('sub') or () )):
            _t = str(_t)
            if _t and _t not in _seen:
                _seen.add(_t)
                _out.append(_t)
    return tuple(_out)


class SectorCoverage(NamedTuple):
    """母層 / 子成分各自「抓到幾個 / 共幾個」。**純計數,不做任何判定。**"""

    parent_fetched: int
    parent_total: int
    sub_fetched: int
    sub_total: int

    @property
    def complete(self) -> bool:
        """是不是**全部**都抓到了。缺一個就是 False(§1:不四捨五入成「都有」)。"""
        return (self.parent_fetched == self.parent_total
                and self.sub_fetched == self.sub_total)


def coverage_counts(sectors: dict[str, dict],
                    returns: dict[str, float | None]) -> SectorCoverage:
    """覆蓋率計數(H-7:母層 ＋ 子成分**都要算**,原實作只數母層)。

    「抓到」的定義:該 ticker 在 `returns` 裡而且值**不是 `None`** ——
    `None` 是 `pct_change_over_bars()` 對「樣本不足」的回覆,把它算成抓到
    等於把「沒有數字」講成「有數字」(§1)。

    Args:
        sectors: 類股宇宙。
        returns: `{ticker: rate_pct}`;抓不到的 ticker 可以不在 dict 內。
    """
    _subs = [_s for _m in (sectors or {}).values()
             for _s in ((_m or {}).get('sub') or ())]
    _ret = returns or {}

    def _got(_t: str) -> bool:
        return _ret.get(_t) is not None

    return SectorCoverage(
        parent_fetched=sum(1 for _t in (sectors or {}) if _got(_t)),
        parent_total=len(sectors or {}),
        sub_fetched=sum(1 for _t in _subs if _got(_t)),
        sub_total=len(_subs),
    )
