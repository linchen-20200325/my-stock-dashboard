"""L0 Infra — SSOT for every threshold / magic number in the dashboard.

資料憲法 §3.3 反捏造：任何判斷用到的數值一律從這裡引入,禁止 inline 腦補。
命名編碼單位（§4.1）：`_PCT` 百分比、`_PCTL` 百分位(0~1)、`_RATIO` 小數、
`_DAYS` 日數、`_TWD` 元。改門檻只改這一處。
"""
from __future__ import annotations

# ── 估值河流圖 (PE / PB river) ──────────────────────────────────────────
# 以「當前值在歷史分布的百分位」判位階。<=20% 便宜、>=80% 昂貴、其間合理。
VALUATION_CHEAP_PCTL: float = 0.20
VALUATION_EXPENSIVE_PCTL: float = 0.80
# 河流圖分帶（畫圖用）：20/40/60/80 百分位五分帶
RIVER_BAND_PCTLS: tuple[float, ...] = (0.20, 0.40, 0.60, 0.80)
# 河流圖至少需要的歷史樣本數,不足 → 位階不可信（confidence 扣分）
VALUATION_MIN_SAMPLES: int = 60

# ── 技術面 (均線 / MACD) ────────────────────────────────────────────────
MA_SHORT_DAYS: int = 20          # 月線
MA_MID_DAYS: int = 60            # 季線
MACD_FAST_DAYS: int = 12
MACD_SLOW_DAYS: int = 26
MACD_SIGNAL_DAYS: int = 9

# ── 籌碼面 (三大法人) ───────────────────────────────────────────────────
# 「外資 + 投信 同步買超」看近 N 個交易日的淨買賣超加總是否同為正。
CHIP_SYNC_LOOKBACK_DAYS: int = 5

# ── 綜合評分權重 (加總=1.0；§4.2 權重和不變量) ──────────────────────────
SCORE_WEIGHT_VALUATION: float = 0.35
SCORE_WEIGHT_TREND: float = 0.35
SCORE_WEIGHT_CHIP: float = 0.30

# ── ETF 成分穿透 / 重疊曝險 ─────────────────────────────────────────────
# 單一底層標的（穿透後）曝險超過此百分比 → 觸發集中度警戒。
SINGLE_NAME_EXPOSURE_ALERT_PCT: float = 30.0
# 成分穿透覆蓋率低於此值 → UI 明示「曝險為下限、非完整」。
OVERLAP_MIN_COVERAGE_PCT: float = 95.0

# ── 資料置信度 (Confidence 0~100) ───────────────────────────────────────
# < 70 鎖定建議（不給買賣結論,只顯示原始數據 + 警告）。
CONFIDENCE_LOCK_THRESHOLD: float = 70.0
# 置信度子項權重（加總=1.0）
CONF_WEIGHT_COMPLETENESS: float = 0.40   # 欄位/樣本齊全度
CONF_WEIGHT_FRESHNESS: float = 0.35      # 資料新鮮度
CONF_WEIGHT_SOURCE: float = 0.25         # 來源可靠度（是否代理/備援）
# 資料多舊算「不新鮮」：交易日級資料超過這天數線性衰減到 0 分。
FRESHNESS_FULL_DAYS: int = 1             # <=1 個日曆日 → 滿分
FRESHNESS_ZERO_DAYS: int = 7             # >=7 個日曆日 → 0 分

# ── 除權息防呆 ──────────────────────────────────────────────────────────
# 開盤相對前收跌幅超過此比例、且當日有配息/配股事件 → 判定為除權息跳空,
# 用還原參考價比對停損,避免誤觸。
EX_DIVIDEND_GAP_PCT: float = 3.0

# ── 停損 / 停利 (持股組合) ──────────────────────────────────────────────
DEFAULT_TRAILING_STOP_PCT: float = 8.0   # 移動停損：距波段高點回落 %
DEFAULT_TAKE_PROFIT_PCT: float = 20.0    # 停利目標 %

# ── 浮點比較容差 (§4.3 禁止 ==) ─────────────────────────────────────────
FLOAT_REL_TOL: float = 1e-9
FLOAT_ABS_TOL: float = 1e-12

# ── 單位換算 (§4.1) ─────────────────────────────────────────────────────
SHARES_PER_LOT: float = 1000.0           # 台股 1 張 = 1000 股

# ── 資產類別判斷（台股 ETF 代碼慣例：00 開頭，如 0050/0056/00878）────────
TW_ETF_CODE_PREFIX: str = "00"

# ── 資料合理範圍 (§3.2 range check) ─────────────────────────────────────
PE_VALID_RANGE: tuple[float, float] = (0.0, 500.0)
PB_VALID_RANGE: tuple[float, float] = (0.0, 100.0)

# ── 池狀態機 (§4.1 pool state) ──────────────────────────────────────────
STATE_WATCHLIST: str = "WATCHLIST"       # 觀察池
STATE_PORTFOLIO: str = "PORTFOLIO"       # 持股組合
STATE_EXITED: str = "EXITED"             # 已出場
LEDGER_ACTION_BUY: str = "BUY"
LEDGER_ACTION_SELL: str = "SELL"

# ── Google Sheets 實體隔離 worksheet 名 ─────────────────────────────────
WS_WATCHLIST: str = "stock_watchlist"
WS_PORTFOLIO: str = "stock_portfolio"
WS_LEDGERS: str = "stock_ledgers"

WS_HEADERS: dict[str, tuple[str, ...]] = {
    WS_WATCHLIST: ("ticker", "name", "note", "updated_at"),
    WS_PORTFOLIO: ("ticker", "name", "lots", "avg_price",
                   "trailing_stop_pct", "take_profit_pct", "updated_at"),
    WS_LEDGERS: ("ts", "ticker", "action", "lots", "price", "reason"),
}
