"""
daily_checklist.py v6.0 — Squid Proxy 模式
🔄 三大法人：TWSE BFI82U via Squid Proxy（5天回溯，row[3] 買賣超，元÷1e8=億）
🔄 融資餘額：5 段備援 — rwd MI_MARGN → HiStock → Goodinfo → Yahoo → 鉅亨網（仟元÷100,000=億）
🔄 ADL / yfinance / FinMind：不受 geo-block 影響，直連
"""
import requests, pandas as pd, datetime, os, time, re
import urllib3
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.ttls import TTL_1HOUR
# v18.325 PR-C: 融資餘額紅線改用既有 SSOT（原 inline 3400，§3.3 反捏造）
from shared.signal_thresholds import (
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


import plotly.graph_objects as go

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

def analyze_20d_chips(stock_id: str) -> dict:
    """
    近 20 日個股籌碼集中度分析（外資 + 投信 vs 總成交量）

    指標 A 集中度 = (外資+投信) 20日淨買總和 / 20日總成交量  × 100%
    指標 B 延續性 = 20日中 (外資+投信) 淨買 > 0 的天數佔比 (%)

    買賣超單位：張 (FinMind TaiwanStockTotalInstitutionalInvestors)
    成交量單位：張 (FinMind TaiwanStockPrice Trading_Volume)
    → 兩者單位相同，集中度為無因次百分比
    """
    import datetime as _dt20
    try:
        import pandas as _pd20
        _start = (_dt20.date.today() - _dt20.timedelta(days=50)).strftime('%Y-%m-%d')
        _base  = 'https://api.finmindtrade.com/api/v4/data'
        _hdrs  = {'Authorization': f'Bearer {FINMIND_TOKEN}'} if FINMIND_TOKEN else {}
        _common = {'token': FINMIND_TOKEN} if FINMIND_TOKEN else {}

        # ── 1. 個股三大法人每日買賣超（單位：張）────────────────────
        _p_inst = {**_common, 'dataset': 'TaiwanStockTotalInstitutionalInvestors',
                   'stock_id': stock_id, 'start_date': _start}
        _r_inst = _bps().get(_base, params=_p_inst, headers=_hdrs, timeout=20, verify=False)
        _j_inst = _r_inst.json()
        _inst_ok = (not (isinstance(_j_inst.get('status'), int)
                         and _j_inst['status'] >= 400)) and bool(_j_inst.get('data'))
        if not _inst_ok:
            return {'error': f'法人資料失敗 status={_j_inst.get("status")}',
                    'signal': '⚫ 資料不足'}

        _df_i = _pd20.DataFrame(_j_inst['data'])
        _df_i.columns = [str(c).lower() for c in _df_i.columns]
        _df_i['buy']  = _pd20.to_numeric(_df_i.get('buy',  0), errors='coerce').fillna(0)
        _df_i['sell'] = _pd20.to_numeric(_df_i.get('sell', 0), errors='coerce').fillna(0)
        _df_i['net']  = _df_i['buy'] - _df_i['sell']
        # 辨識外資 / 投信（相容 FinMind 英文或中文 name 欄位）
        _is_fi = _df_i['name'].apply(
            lambda n: str(n) == 'Foreign_Investor' or ('外資' in str(n) and '自營' not in str(n)))
        _is_tr = _df_i['name'].apply(
            lambda n: str(n) == 'Investment_Trust' or '投信' in str(n))
        _df_fi = _df_i[_is_fi][['date','net']].rename(columns={'net':'foreign_net'})
        _df_tr = _df_i[_is_tr][['date','net']].rename(columns={'net':'trust_net'})
        _df_m  = _pd20.merge(_df_fi, _df_tr, on='date', how='outer').fillna(0)
        _df_m['combined'] = _df_m['foreign_net'] + _df_m['trust_net']
        _df_m  = _df_m.sort_values('date').tail(20)

        # ── 2. 每日成交量（單位：張，來自 TaiwanStockPrice）─────────
        _p_vol = {**_common, 'dataset': 'TaiwanStockPrice',
                  'stock_id': stock_id, 'start_date': _start}
        _r_vol = _bps().get(_base, params=_p_vol, headers=_hdrs, timeout=20, verify=False)
        _j_vol = _r_vol.json()
        _vol_ok = (not (isinstance(_j_vol.get('status'), int)
                        and _j_vol['status'] >= 400)) and bool(_j_vol.get('data'))
        if not _vol_ok:
            return {'error': '價量資料失敗', 'signal': '⚫ 資料不足'}

        _df_v  = _pd20.DataFrame(_j_vol['data'])
        _df_v.columns = [str(c).lower() for c in _df_v.columns]
        # 相容 trading_volume / volume 欄名
        _vcol  = next((c for c in _df_v.columns if 'trading_volume' in c or c == 'volume'), None)
        if _vcol is None:
            return {'error': '找不到成交量欄位', 'signal': '⚫ 資料不足'}
        _df_v[_vcol] = _pd20.to_numeric(_df_v[_vcol], errors='coerce').fillna(0)
        _df_v  = _df_v[['date', _vcol]].rename(columns={_vcol: 'volume'})
        _df_v  = _df_v.sort_values('date').tail(20)

        # ── 3. 合併：只取法人與成交量均有資料的交易日 ──────────────
        _df    = _pd20.merge(_df_m, _df_v, on='date', how='inner').tail(20)
        if len(_df) < 5:
            return {'error': f'有效天數不足（{len(_df)}天）', 'signal': '⚫ 資料不足'}

        # ── 4. 計算兩大指標 ──────────────────────────────────────────
        _tot_net = float(_df['combined'].sum())          # 外+投 累計淨買（張）
        _tot_vol = float(_df['volume'].sum())            # 總成交量（張）
        _concentration = (_tot_net / _tot_vol * 100) if _tot_vol > 0 else 0.0   # %
        _pos_days  = int((_df['combined'] > 0).sum())
        _continuity = _pos_days / len(_df) * 100                                  # %

        # ── 5. 判定訊號 ──────────────────────────────────────────────
        if _concentration > 5 and _continuity > 50:
            _signal = '🔥 大戶吸籌'
        elif _concentration < -5:
            _signal = '🔴 大戶倒貨'
        else:
            _signal = '🟡 籌碼發散'

        print(f'[20d_chips/{stock_id}] 集中度={_concentration:.2f}% 延續性={_continuity:.0f}% '
              f'days={len(_df)} signal={_signal}')
        return {
            'concentration': round(_concentration, 2),   # %（可正可負）
            'continuity':    round(_continuity, 1),       # 0~100%
            'signal':        _signal,
            'days':          len(_df),
            'pos_days':      _pos_days,
            'total_net_k':   round(_tot_net / 1e3, 1),   # 千張
            'total_vol_k':   round(_tot_vol / 1e3, 1),   # 千張
            'error':         None,
        }
    except Exception as _e20:
        print(f'[20d_chips/{stock_id}] ❌ {type(_e20).__name__}: {_e20}')
        return {'error': str(_e20), 'signal': '⚫ 計算失敗'}


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

@st.cache_data(ttl=TTL_1HOUR, show_spinner=False, max_entries=10)
def get_export_yoy() -> dict | None:
    return None


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False, max_entries=10)
def get_business_indicator() -> dict | None:
    return None
