"""
daily_checklist.py v6.0 — Squid Proxy 模式
🔄 三大法人：TWSE BFI82U via Squid Proxy（5天回溯，row[3] 買賣超，元÷1e8=億）
🔄 融資餘額：5 段備援 — rwd MI_MARGN → HiStock → Goodinfo → Yahoo → 鉅亨網（仟元÷100,000=億）
🔄 ADL / yfinance / FinMind：不受 geo-block 影響，直連
"""
import logging as _cl_log
import requests, os
import urllib3

_logger = _cl_log.getLogger(__name__)
# v18.325 PR-C: 融資餘額紅線改用既有 SSOT（原 inline 3400，§3.3 反捏造）
# 融資紅/黃線門檻屬本服務的 SSOT 消費契約(consumed_ssot guard 釘),
# 即使主邏輯已下沉 daily_data_fetchers,仍保留 import 作消費標記(F401 豁免)。
from shared.signal_thresholds import (  # noqa: F401
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,  # v18.326 PR-D: 融資黃線
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _bps():
    try:
        from src.data.stock import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s

import streamlit as st

DISABLE_TWSE: bool = True  # 🚫 TWSE 已永久停用


# ── 快取基礎設施 (v18.344 PR-N1 抽至 shared/cache_layer.py)─────────────
# 原 v4.5 SSOT cache 邏輯遷出,保留 re-export 維持向後相容(caller 不必改)。
from src.config import TTL_CONFIG as _TTL_CFG, PKL_DIR as _PKL_DIR  # noqa: F401
from shared.cache_layer import (
    _CACHE_SENTINEL,  # noqa: F401
    _pkl_get,         # noqa: F401
    _pkl_put,         # noqa: F401
    _pkl_clear_all,   # noqa: F401
)


# v18.344 PR-N1:`st.secrets.get(...)` 即使無 secrets.toml 也會觸發 StreamlitSecretNotFoundError
# (st.secrets 物件 lazy parse),原 getattr 防護不夠;改 try/except 包,僅在 secrets.toml
# 存在時走 st.secrets,否則 fallback 到 os.environ(headless / CLI test 場景無 secrets)。
try:
    FINMIND_TOKEN = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN', '')
                     or os.environ.get('FINMIND_TOKEN', ''))
except Exception:
    FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN', '')
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}
# v18.344 PR-N1:COLORS_7 抽至 macro_ui_components.py(L4 Render),re-export 維持相容
from src.ui.render.macro_ui_components import COLORS_7  # noqa: F401  # v18.361 F-6.5:直打 submod 避 __init__ 順序 circular
INTL_MAP = {"道瓊工業 DJI":"^DJI","納斯達克 IXIC":"^IXIC","費城半導體 SOX":"^SOX","10Y公債殖利率":"^TNX","美元指數 DXY":"DX-Y.NYB"}
INTL_UNIT = {k:("%" if "殖利率" in k else "指數") for k in INTL_MAP}
TW_MAP   = {"台股加權指數":"^TWII","新台幣匯率":"TWD=X"}
TW_UNIT  = {"台股加權指數":"pts","新台幣匯率":"TWD/USD"}
TECH_MAP = {"台積電 ADR":"TSM","微軟 MSFT":"MSFT","蘋果 AAPL":"AAPL","谷歌 GOOGL":"GOOGL","輝達 NVDA":"NVDA","AMD":"AMD","博通 AVGO":"AVGO"}

# v18.344 PR-N1:_num / _TW_TZ_DL / _tw_today_dl / _recent_date 抽至 shared/macro_compute.py
# (L2 純函式),re-export 維持向後相容(無 caller 直引但保險起見)
from shared.macro_compute import (
    _num,           # noqa: F401
    _TW_TZ_DL,      # noqa: F401
    _tw_today_dl,   # noqa: F401
    _recent_date,   # noqa: F401
)

# ═══════════════════════════════════════════════
# 三大法人 (v18.346 PR-N3 抽至 daily_data_fetchers.py)
# ═══════════════════════════════════════════════
from src.data.daily import fetch_institutional  # noqa: F401


# ═══════════════════════════════════════════════
# 融資餘額 — v18.348 PR-N5 抽至 daily_data_fetchers.py
# ═══════════════════════════════════════════════
from src.data.daily import fetch_margin_balance  # noqa: F401


# v18.344 PR-N1:evaluate_market_status_v4_final 抽至 shared/macro_compute.py(L2 純函式)
from shared.macro_compute import evaluate_market_status_v4_final  # noqa: F401


# ═══════════════════════════════════════════════
# yfinance (v18.345 PR-N2 抽至 daily_data_fetchers.py)
# ═══════════════════════════════════════════════
# caller 用 `from daily_checklist import fetch_single` 形式,re-export 維持 0 改動
from src.data.daily import (  # noqa: F401
    fetch_single,
    fetch_flow_snapshot,
)

# v18.346 PR-N3:_fetch_otc_via_finmind 抽至 daily_data_fetchers.py
from src.data.daily import _fetch_otc_via_finmind  # noqa: F401


# ═════════════════════════════════════════════════════
# 騰落指標（ADL）— v18.347 PR-N4 抽至 daily_data_fetchers.py
# ═════════════════════════════════════════════════════
from src.data.daily import fetch_adl, _adl_selftest  # noqa: F401


# v18.344 PR-N1:UI 渲染元件抽至 macro_ui_components.py(L4 Render),re-export 維持相容。
# 8 個函式:_hex2rgba / _base_layout / sparkline / multi_chart /
# bar_chart_institutional / stat_card / margin_card / section_header
from src.ui.render.macro_ui_components import (  # noqa: F401  # v18.361 F-6.5:直打 submod 避 circular
    _hex2rgba,
    _base_layout,
    sparkline,
    multi_chart,
    bar_chart_institutional,
    stat_card,
    margin_card,
    section_header,
)


# v18.344 PR-N1:analyze_20d_chips_from_df 抽至 shared/macro_compute.py(L2 純函式)。
# 三個 caller (tab_macro / tab_stock x2 / tab_stock_grp) 用 `from daily_checklist
# import analyze_20d_chips_from_df` 形式,re-export 維持 0 caller 改動。
from shared.macro_compute import analyze_20d_chips_from_df  # noqa: F401


# v18.301 §8.3 拆檔:calc_stats 已提取至 shared/stats_helpers.py(L0 純函式)。
# 此處保 re-export 維持向後相容(tab_macro.py:358 等 caller 0 改)。
from shared.stats_helpers import calc_stats  # noqa: F401


# ═══════════════════════════════════════════════════════════
# v5.0 Wrapper 函數 — NAS 優先，快取裝飾，統一 N/A 邏輯
# ═══════════════════════════════════════════════════════════

