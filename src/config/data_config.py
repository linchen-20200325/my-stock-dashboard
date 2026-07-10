"""
data_config.py — 資料來源優先順序與快取 TTL 設定 (v4.2)
集中管理所有資料抓取策略，避免散落各處的魔術數字。
TTL 值改 import shared.ttls SSOT。
"""
from shared.ttls import TTL_15MIN, TTL_30MIN, TTL_1DAY

# 各資料類型的來源優先順序（由高到低）
PRIORITY = {
    "institutional":   ["TWSE", "FinMind", "Cache"],
    "margin_balance":  ["FinMind", "Wearn", "TWSE", "Cache"],
    "futures":         ["TAIFEX", "FinMind", "Cache"],
    "volume":          ["TWSE_OpenAPI", "YFinance", "Cache"],
    "index":           ["YFinance", "TWSE"],
    "adl":             ["Cache", "YFinance"],
}

# HTTP 請求逾時（秒）— S6/S14 v19.78(第二份 review):
# FinMind SDK dataset 方法簽名 `timeout: int = None`,None 會一路傳到
# `session.get(timeout=None)` = 無限等待(還包在 SDK max_retry_times=10 迴圈),
# proxy 慢/掛時單一請求即卡死整站 → 呼叫端必須顯式帶 timeout。
# 語意為「單次 HTTP 等待上限」,與 shared/ttls.py 的「快取存活時長」不同源,不混放。
HTTP_TIMEOUT_FINMIND_SDK_SEC: int = 30   # SDK 呼叫(daily/inst/margin/季報 fallback)
HTTP_TIMEOUT_YF_SEC: int = 15            # yfinance download(其內部預設 10,顯式化+放寬跨國 RTT)

# 快取存活時間（秒）— 短=當日關鍵數據，長=歷史數據
TTL_CONFIG = {
    "institutional":   TTL_30MIN,   # 30 分鐘 — 法人買賣（收盤後更新，日頻）
    "margin_balance":  TTL_30MIN,   # 30 分鐘 — 融資融券餘額（日頻）
    "futures":         TTL_15MIN,   # 15 分鐘 — 期貨選擇權法人
    "volume":          600,         # 10 分鐘 — 成交量（唯一 10min 使用點，不入 SSOT）
    "historical":      TTL_1DAY,    # 24 小時 — 歷史/不常變的資料
}

# pickle 快取根目錄(Streamlit Cloud /tmp 重啟後自動清除)
# A2 v18.383:env 注入(`STK_PKL_DIR`)解 shared/cache_layer.py 反向 import L0(L0↔L0 hardcode 設計味道)
import os as _os_cfg
import tempfile as _tf_cfg
# D14b v19.75(review):預設改 tempfile.gettempdir() 可攜寫法(Linux 結果不變;Windows 不炸)
PKL_DIR = _os_cfg.environ.get('STK_PKL_DIR') or _os_cfg.path.join(_tf_cfg.gettempdir(), 'stock_cache')
