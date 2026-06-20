"""
data_config.py — 資料來源優先順序與快取 TTL 設定 (v4.1 — v2.0重構)

集中管理所有資料抓取策略與快取策略，避免散落各處的魔術數字。

【v2.0 重構】 所有 TTL 定義已統一在此檔案。各模組禁止硬編碼 ttl 值。
"""

# 各資料類型的來源優先順序（由高到低）
PRIORITY = {
    "institutional":   ["TWSE", "FinMind", "Cache"],
    "margin_balance":  ["FinMind", "Wearn", "TWSE", "Cache"],
    "futures":         ["TAIFEX", "FinMind", "Cache"],
    "volume":          ["TWSE_OpenAPI", "YFinance", "Cache"],
    "index":           ["YFinance", "TWSE"],
    "adl":             ["Cache", "YFinance"],
}

# 【新增】細粒度快取存活時間（秒）— 統一 Streamlit cache_data decorator 使用
# 
# 快取策略說明：
#   短(600秒以下)：  當日高頻更新的交易數據、法人資金流
#   中(1800秒)：     日頻更新的金融指標、融資融券
#   長(3600+秒)：    每小時以上的穩定數據
#   極長(86400+秒)： 日線歷史數據、基本資料
#
CACHE_TTL = {
    # ── 短期快取 ─────────────────────────────────────────
    'institutional_flows':  900,        # 15 分鐘 — 法人買賣（日內監控）
    'margin_realtime':      600,        # 10 分鐘 — 融資融券實時
    'futures_price':        600,        # 10 分鐘 — 期貨選擇權
    'volume_intraday':      600,        # 10 分鐘 — 當日成交量
    
    # ── 中期快取 ─────────────────────────────────────────
    'financial_data':       1800,       # 30 分鐘 — 機構資金/融資融券（日收盤後更新）
    'margin_balance':       1800,       # 30 分鐘 — 融資融券餘額
    'tech_indicators':      1800,       # 30 分鐘 — 技術指標（RSI、MA 等）
    'price_data':           3600,       # 1 小時 — 股價、配息
    
    # ── 長期快取 ──────────────────────────────────────────
    'daily_snapshot':       86400,      # 1 天 — 財報、基本資料、EPS
    'fundamentals':         86400,      # 1 天 — 基本面數據（月度更新）
    'etf_nav':              86400,      # 1 天 — ETF 淨值
    
    # ── 極長期快取 ────────────────────────────────────────
    'etf_holdings':         604800,     # 7 天 — ETF 成分股（季度變動）
    'industry_bands':       604800,     # 7 天 — 產業 PB 分位數
    'macro_snapshot':       90*86400,   # 90 天 — 宏觀指標 fallback
    
    # ── 代理相關快取 ──────────────────────────────────────
    'proxy_config':         300,        # 5 分鐘 — 代理配置測活
    'proxy_fallback':       60,         # 1 分鐘 — 快速重試
}

# ── 舊版 TTL_CONFIG（向後兼容）────────────────────────────────────
# 【已廢止】建議改用上方 CACHE_TTL，粒度更細
TTL_CONFIG = {
    "institutional":   1800,   # 30 分鐘 — 法人買賣（收盤後更新，日頻）
    "margin_balance":  1800,   # 30 分鐘 — 融資融券餘額（日頻）
    "futures":         900,    # 15 分鐘 — 期貨選擇權法人
    "volume":          600,    # 10 分鐘 — 成交量
    "historical":      86400,  # 24 小時 — 歷史/不常變的資料
}

# pickle 快取根目錄（Streamlit Cloud /tmp 重啟後自動清除）
PKL_DIR = "/tmp/stock_cache"


__all__ = [
    'PRIORITY',
    'CACHE_TTL',
    'TTL_CONFIG',
    'PKL_DIR',
]

