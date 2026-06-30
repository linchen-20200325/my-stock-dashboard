"""
台股 AI 戰情室 v3.0 集中設定檔 (§11) — 優化版
整合分析建議：ATR停損、Sharpe動能、時間停損、滑價修正
"""

# ── 市場判斷閾值 ──────────────────────────────────────────────
MARKET_SCORE_BULL    = 3     # 總分 >= 3 判定為多頭
MARKET_SCORE_NEUTRAL = 2     # 總分 == 2 判定為中性

# ── 均線參數 ──────────────────────────────────────────────────
MA_SHORT  = 20
MA_MID    = 60
MA_LONG   = 120
MA_ANNUAL = 240   # 年線

# ── 風控參數（優化版）────────────────────────────────────────
MAX_POSITION_PER_STOCK  = 0.10   # 單股最大持倉比重 10%
MAX_PORTFOLIO_DRAWDOWN  = 0.15   # 最大回撤 15%，超過暫停交易
STOP_LOSS_PCT           = 0.08   # 固定停損 -8%（ATR模式下為備援）
TRAILING_STOP_PCT       = 0.07   # 移動停利回撤 7%
MIN_CASH_RATIO          = 0.10   # 現金部位下限 10%
MAX_POSITIONS           = 10     # 最大持股檔數

# ── ATR 動態停損參數（§優化1）────────────────────────────────
ATR_PERIOD     = 14      # ATR 計算週期（天）
ATR_MULTIPLIER = 1.5     # 停損距離 = Entry - (N × ATR14)，N=1.5~2.0

# ── 時間停損參數（§優化5：防止資金被套）────────────────────
TIME_STOP_DAYS      = 15    # 買進後超過 15 天
TIME_STOP_MIN_GAIN  = 0.02  # 若報酬未達 +2% → 強制換股

# ── 動態因子權重表（依市場狀態自動切換，6 因子 SSOT）──────
# 唯一權重來源；scoring_engine.stock_score 由此讀取。
# bull：趨勢/動能加重，進攻型；bear：風險/基本面加重，防禦型
WEIGHT_TABLES = {
    'bull': {
        'trend': 0.30, 'momentum': 0.25, 'chip': 0.20,
        'volume': 0.15, 'risk': 0.05, 'fundamental': 0.05,
    },
    'neutral': {
        'trend': 0.25, 'momentum': 0.20, 'chip': 0.20,
        'volume': 0.15, 'risk': 0.10, 'fundamental': 0.10,
    },
    'bear': {
        'trend': 0.15, 'momentum': 0.10, 'chip': 0.15,
        'volume': 0.15, 'risk': 0.25, 'fundamental': 0.20,
    },
}

# ── 選股篩選條件 ──────────────────────────────────────────────
TOP_N_STOCKS    = 10
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30
MIN_LIQUIDITY   = 500

# ── 市場曝險比例（依 market_regime）────────────────────────
EXPOSURE_BULL    = 0.80   # 多頭：80% 持股
EXPOSURE_NEUTRAL = 0.50   # 中性：50% 持股
EXPOSURE_BEAR    = 0.20   # 空頭：20% 持股

# ── 韭菜指數警戒門檻 ─────────────────────────────────────────
LEEK_HIGH_THRESHOLD  = 35.0   # 超過此值 = 散戶過熱，警戒
LEEK_LOW_THRESHOLD   = 10.0   # 低於此值 = 散戶淨空，潛在機會

# ── 瘋牛濾網（量能過濾韭菜指數）────────────────────────────
BULLRUN_VOL_THRESHOLD = 1.3   # 大盤成交量 > 月均量 x 1.3 = 資金派對模式

# ── 總經警示規則（macro_alert.py 使用）──────────────────────
# 欄位說明：
#   red_above    → 值 > 此門檻觸發 🔴
#   yellow_above → 值 > 此門檻觸發 🟡（優先級低於 red_above）
#   red_below    → 值 < 此門檻觸發 🔴（雙向指標適用）
#   yellow_below → 值 < 此門檻觸發 🟡（雙向指標適用）
MACRO_ALERT_RULES: list = [
    {
        'key':          'vix',
        'label':        'VIX 恐慌指數',
        'unit':         '',
        'red_above':    30.0,   # > 30 市場恐慌
        'yellow_above': 20.0,   # 20–30 警戒
    },
    {
        'key':          'cpi',
        'label':        'CPI YoY（美）',
        'unit':         '%',
        'red_above':    3.5,    # > 3.5% 通膨加速，Fed 升息壓力
        'yellow_above': 2.5,    # 2.5–3.5% 溫和通膨
    },
    {
        'key':          'us10y',
        'label':        '美債 10Y 殖利率',
        'unit':         '%',
        'red_above':    4.8,    # > 4.8% 融資成本壓力，股市估值承壓
        'yellow_above': 4.2,    # 4.2–4.8% 觀察區
    },
    {
        'key':          'dxy',
        'label':        'DXY 美元指數',
        'unit':         '',
        'red_above':    107.0,  # > 107 強美元，外資撤離新興市場壓力
        'yellow_above': 103.0,  # 103–107 中性偏強
    },
    {
        'key':          'pcr',
        'label':        'PCR 選擇權比值',
        'unit':         '',
        'red_above':    1.5,    # > 1.5 市場極度恐慌
        'yellow_above': 1.2,    # 1.2–1.5 偏空情緒
        'red_below':    0.5,    # < 0.5 過度樂觀（頂部訊號）
        'yellow_below': 0.7,    # 0.5–0.7 樂觀偏高，注意反轉
    },
]


# ── Secrets / API Tokens ─────────────────────────────────────
# FINMIND_TOKEN：優先讀 Streamlit secrets，否則 fallback 到環境變數。
# 由 tab_stock.py / tab_stock_grp.py 等模組統一從這裡 import，
# 避免各檔重複貼 secrets+env 的 fallback 樣板。
#
# v18.241 A1：CLAUDE.md §8.2 例外 — L0 條件 import streamlit 限於 secrets bootstrap
# 理由：
#   1. try/except ImportError 已護 streamlit 缺席（純 .py 環境仍可運行）
#   2. 用途僅限讀 st.secrets，無 UI lifecycle 依賴（不用 cache_data / session_state）
#   3. 替代方案（移到 L3 + FINMIND_TOKEN 改函式）會打破所有 caller 介面，ROI 低
# 將此模式列為 CLAUDE.md §8.2 已知例外（見「8.2 已知例外清單」）。
import os as _os  # noqa: E402
try:
    import streamlit as _st  # noqa: E402  -- 例外:見上方 v18.241 A1 註解
    try:
        _t = (getattr(_st, 'secrets', None) or {}).get('FINMIND_TOKEN', '')
    except Exception:
        _t = ''
    FINMIND_TOKEN = _t or _os.environ.get('FINMIND_TOKEN', '')
except ImportError:
    FINMIND_TOKEN = _os.environ.get('FINMIND_TOKEN', '')

# Batch 10 v18.412 R-FETCH「附帶」:FinMind API endpoint SSOT
# 原 22 檔散落 hardcoded URL(37 occurrences),改 import 收 SSOT
FINMIND_API_URL = 'https://api.finmindtrade.com/api/v4/data'

