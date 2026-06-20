"""
shared/constants.py — 全球常數定義（唯一事實來源）

所有 hardcode 常數均應統一在此模組。
任何模組 import 常數時，應用此模組而非自行定義 fallback。

v2.0 重構 — 2026-06-20
"""

# ============================================================================
# 技術指標 — RSI
# ============================================================================

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30


# ============================================================================
# 技術指標 — 均線
# ============================================================================

MA_SHORT = 20         # 短期均線（月線）
MA_MID = 60           # 中期均線
MA_LONG = 120         # 長期均線
MA_ANNUAL = 240       # 年線

# 集合體：推薦的所有均線週期
MA_PERIODS_STANDARD = [MA_SHORT, MA_MID, MA_LONG, MA_ANNUAL]
MA_PERIODS_EXTENDED = [5, 20, 60, 120, 240]  # 擴展集：含 5 日快線


# ============================================================================
# 技術指標 — MACD
# ============================================================================

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


# ============================================================================
# 技術指標 — 布林帶
# ============================================================================

BOLLINGER_PERIOD = 20
BOLLINGER_STD_DEV = 2


# ============================================================================
# 健康度評分
# ============================================================================

HEALTH_GRADE_A_MIN = 80          # A 級最低分
HEALTH_GRADE_B_MIN = 50          # B 級最低分
HEALTH_GRADE_C_MIN = 20          # C 級最低分
HEALTH_GRADE_D_MIN = 0           # D 級最低分

# 健康度防守閾值
HEALTH_DEFENSE_THRESHOLD = 35    # 低於此分數時進入防守模式


# ============================================================================
# 市場狀態與曝險配置
# ============================================================================

EXPOSURE_BULL = 0.80             # 多頭市場曝險
EXPOSURE_NEUTRAL = 0.50          # 盤整市場曝險
EXPOSURE_BEAR = 0.20             # 空頭市場曝險

# 市場狀態判定閾值
MARKET_STATE_POSITIVE_THRESHOLD = 0.6
MARKET_STATE_NEGATIVE_THRESHOLD = 0.4


# ============================================================================
# ETF 評分
# ============================================================================

ETF_HOLDINGS_CONCENTRATION_THRESHOLD = 30  # 成分股集中度警戒（%）
ETF_EXPENSE_RATIO_GOOD = 0.005             # 優秀費率（0.5%）
ETF_EXPENSE_RATIO_FAIR = 0.020             # 合理費率（2.0%）


# ============================================================================
# 籌碼指標
# ============================================================================

CHIP_TREND_PERIOD = 20           # 籌碼趨勢計算週期


# ============================================================================
# 成交量指標
# ============================================================================

VOLUME_MA_PERIOD = 20            # 成交量均線週期
VOLUME_SPIKE_MULTIPLIER = 1.5    # 成交量激增倍數（相對均線）


# ============================================================================
# 宏觀指標 — 台灣
# ============================================================================

# 機構投資人資金流向閾值（十億新台幣）
INSTITUTIONAL_INFLOW_SIGNIFICANT = 50
INSTITUTIONAL_OUTFLOW_SIGNIFICANT = -50

# 融資融券信用比閾值
MARGIN_RATIO_HIGH = 40           # 融資比 >40% 警戒
FINANCING_RATIO_HIGH = 35        # 融資比 >35% 警戒


# ============================================================================
# 股票篩選
# ============================================================================

# PB 倍數（本益比代理）
PB_CHEAP = 1.0                   # 便宜
PB_FAIR = 2.5                    # 合理
PB_EXPENSIVE = 4.0               # 昂貴

# ROE 閾值
ROE_EXCELLENT = 0.20             # 20% 以上優秀
ROE_GOOD = 0.15                  # 15% 以上良好
ROE_FAIR = 0.10                  # 10% 以上合理
ROE_POOR = 0.05                  # 低於 5% 欠佳

# 負債比
DEBT_RATIO_HIGH = 0.60           # 高槓桿警戒
DEBT_RATIO_FAIR = 0.40           # 合理負債


# ============================================================================
# UI 與色彩（另見 shared/colors.py）
# ============================================================================

EMOJI_PASS = '✅'
EMOJI_FAIL = '❌'
EMOJI_NEUTRAL = '⚪'
EMOJI_UP = '📈'
EMOJI_DOWN = '📉'
EMOJI_UNCHANGED = '➡️'


# ============================================================================
# 系統配置
# ============================================================================

MAX_RETRIES = 3                  # API 重試次數
DEFAULT_TIMEOUT = 30             # 網路請求逾時（秒）


# ============================================================================
# 回測參數
# ============================================================================

BACKTEST_INIT_CASH = 1_000_000           # 初始資金
BACKTEST_COMMISSION = 0.001425           # 台股手續費 0.1425%
BACKTEST_SLIPPAGE = 0.003                # 滑價 0.3%
WFT_TRAIN_YEARS = 3                      # Walk Forward Test 訓練年限
WFT_TEST_MONTHS = 12                     # Walk Forward Test 測試月數


__all__ = [
    # RSI
    'RSI_PERIOD', 'RSI_OVERBOUGHT', 'RSI_OVERSOLD',
    # MA
    'MA_SHORT', 'MA_MID', 'MA_LONG', 'MA_ANNUAL',
    'MA_PERIODS_STANDARD', 'MA_PERIODS_EXTENDED',
    # MACD
    'MACD_FAST', 'MACD_SLOW', 'MACD_SIGNAL',
    # Bollinger
    'BOLLINGER_PERIOD', 'BOLLINGER_STD_DEV',
    # Health
    'HEALTH_GRADE_A_MIN', 'HEALTH_GRADE_B_MIN', 'HEALTH_GRADE_C_MIN',
    'HEALTH_GRADE_D_MIN', 'HEALTH_DEFENSE_THRESHOLD',
    # Market
    'EXPOSURE_BULL', 'EXPOSURE_NEUTRAL', 'EXPOSURE_BEAR',
    'MARKET_STATE_POSITIVE_THRESHOLD', 'MARKET_STATE_NEGATIVE_THRESHOLD',
    # ETF
    'ETF_HOLDINGS_CONCENTRATION_THRESHOLD', 'ETF_EXPENSE_RATIO_GOOD',
    'ETF_EXPENSE_RATIO_FAIR',
    # Chip
    'CHIP_TREND_PERIOD',
    # Volume
    'VOLUME_MA_PERIOD', 'VOLUME_SPIKE_MULTIPLIER',
    # Macro TW
    'INSTITUTIONAL_INFLOW_SIGNIFICANT', 'INSTITUTIONAL_OUTFLOW_SIGNIFICANT',
    'MARGIN_RATIO_HIGH', 'FINANCING_RATIO_HIGH',
    # Stock
    'PB_CHEAP', 'PB_FAIR', 'PB_EXPENSIVE',
    'ROE_EXCELLENT', 'ROE_GOOD', 'ROE_FAIR', 'ROE_POOR',
    'DEBT_RATIO_HIGH', 'DEBT_RATIO_FAIR',
    # UI
    'EMOJI_PASS', 'EMOJI_FAIL', 'EMOJI_NEUTRAL', 'EMOJI_UP',
    'EMOJI_DOWN', 'EMOJI_UNCHANGED',
    # System
    'MAX_RETRIES', 'DEFAULT_TIMEOUT',
    # Backtest
    'BACKTEST_INIT_CASH', 'BACKTEST_COMMISSION', 'BACKTEST_SLIPPAGE',
    'WFT_TRAIN_YEARS', 'WFT_TEST_MONTHS',
]
