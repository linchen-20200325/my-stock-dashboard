"""
ETF 抓取層（fetch layer）
從 etf_dashboard.py 抽出的純 I/O 函式：價格 / 配息 / 基本資訊 / 費用率 / NAV / 類股漲跌
無內部依賴；可被 etf_calc、etf_render、tab_* 模組安全 import。

S-H3 v18.244(CLAUDE.md §8.2 修正):L1 不得用 `st.error/st.warning/st.session_state`
真 UI 呼叫。原 4 處 violation:
- L147 / L1581:`st.error/st.warning` → 改 `print()` log,caller 自行偵測 empty DataFrame
- L1024 / L1747:`st.session_state.setdefault('_etf_*_last_err', {})` 側通道錯誤儲存
  → 改 module-level `_ETF_MANAGER_LAST_ERR` / `_ETF_INDEX_LAST_ERR` dict +
    `get_etf_manager_last_err()` / `get_etf_index_last_err()` accessor,
    UI(`health_inspector.py`)讀取改用 accessor。
"""

# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
# 本檔僅用 @st.cache_data + getattr(st, 'secrets', {}) defensive read,
# 無 st.session_state / st.error / st.markdown 等真 UI 呼叫(S-H3 已下沉 module-level dict)。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa
import pandas as pd
import yfinance as yf

from shared.ttls import TTL_15MIN, TTL_30MIN, TTL_1HOUR, TTL_2HOUR, TTL_1DAY, TTL_7DAY
from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT


# v18.352 PR-Q2 — S-PROV-1 phase 19 helper
# 7 fetcher (sitca_expense / moneydj_expense / yahoo_tw_holdings /
# etf_holdings / sitca_manager / etf_zh_name / etf_underlying_index)
# 共用一個 stderr audit trail。介面 0 改:fetcher return 不動。
# P2-1 v18.380:_prov_log 統一收攏至 src/data/core/provenance.py(原 3 處同名異簽名)
from src.data.core.provenance import prov_log as _prov_log_unified


def _prov_log(fn_name: str, source: str, ticker: str, result_summary: str):
    """§2.2 provenance — backward-compat shim,thin wrapper to unified SSOT。"""
    try:
        _prov_log_unified(fn_name, source, result_summary, ticker=ticker)
    except Exception:
        pass


# S-H3 v18.244:diagnostic 錯誤儲存從 st.session_state 下移至 module-level dict
# UI 讀取走 get_etf_manager_last_err() / get_etf_index_last_err() accessor。
_ETF_MANAGER_LAST_ERR: dict = {}
_ETF_INDEX_LAST_ERR: dict = {}


def get_etf_manager_last_err() -> dict:
    """Diagnostic 面板 accessor:回最近一次 ETF manager fetch 失敗原因(by ticker)。"""
    return dict(_ETF_MANAGER_LAST_ERR)


def get_etf_index_last_err() -> dict:
    """Diagnostic 面板 accessor:回最近一次 ETF index fetch 失敗原因(by ticker)。"""
    return dict(_ETF_INDEX_LAST_ERR)


def _fetch_news_for(ticker: str, name: str = "", n: int = 4) -> str:
    """抓取個股/ETF 相關新聞，回傳格式化字串。失敗時回傳空字串。
    走 NAS 中繼站 → Squid proxy(帶 CONSENT cookie 繞 Google 同意頁) → 直連。"""
    try:
        import feedparser as _fp
        import html as _h
        from urllib.parse import quote as _uq
    except ImportError:
        return ""
    try:
        from src.data.proxy import fetch_url as _furl, nas_relay_fetch as _nasf
    except ImportError:
        _furl = _nasf = None
    _feeds = [
        f'https://news.google.com/rss/search?q={_uq(f"{ticker} {name}".strip())}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
        f'https://news.google.com/rss/search?q={_uq(f"Taiwan ETF {ticker}".strip())}&hl=en-US&gl=US&ceid=US:en',
    ]
    _hdr = {'Cookie': 'CONSENT=YES+cb; SOCS=CAI',
            'Accept': 'application/rss+xml, application/xml;q=0.9, */*;q=0.5'}
    _out = []
    for _url in _feeds:
        try:
            _fd = None
            if _nasf is not None:
                _rr = _nasf(_url, timeout=15)
                if _rr is not None:
                    _fd = _fp.parse(_rr.content)  # 餵 bytes（避免 str+encoding 宣告被拒解析）
            if (_fd is None or not getattr(_fd, 'entries', None)) and _furl is not None:
                _rs = _furl(_url, headers=_hdr, timeout=10)
                if _rs is not None:
                    _fd = _fp.parse(_rs.content)
            if _fd is None or not getattr(_fd, 'entries', None):
                _fd = _fp.parse(_url, request_headers=_hdr)
            for _e in _fd.entries:
                _t = _h.unescape(_e.get('title', '')).strip()
                _p = str(_e.get('published', ''))[:10]
                if _t:
                    _out.append(f'- {_t}（{_p}）')
                if len(_out) >= n:
                    break
        except Exception:
            pass
        if len(_out) >= n:
            break
    return '\n'.join(_out[:n]) if _out else '（暫無相關新聞）'


# ── MK 規格 條件 B：台灣 ETF 發行價對照表（用於破發檢測）──────
# 台灣常見 ETF 發行價（多為 10/15/20/30/40 元）；債券 ETF 多為 40 元
_TW_ETF_LAUNCH_PRICE = {
    '0050': 36.98, '0051': 25.57, '0052': 36.99, '0053': 22.20,
    '0055': 12.95, '0056': 25.20, '0057': 38.10,
    '006203': 25, '006204': 30, '006208': 30, '00646': 20,
    '00692': 20, '00701': 20, '00713': 20, '00730': 20,
    '00731': 20, '00733': 20, '00735': 20, '00850': 20,
    '00878': 15, '00881': 15, '00882': 15, '00891': 15,
    '00892': 15, '00893': 15, '00895': 15, '00896': 15,
    '00897': 15, '00898': 15, '00899': 15, '00900': 15,
    '00901': 15, '00902': 15, '00903': 15, '00904': 15,
    '00905': 15, '00907': 15, '00910': 15, '00911': 15,
    '00912': 15, '00913': 15, '00915': 15, '00916': 15,
    '00918': 15, '00919': 20, '00920': 15, '00921': 15,
    '00922': 15, '00923': 15, '00924': 15, '00925': 15,
    '00927': 15, '00929': 15, '00930': 15, '00932': 15,
    '00934': 10, '00935': 10, '00936': 10, '00939': 15,
    '00940': 10, '00941': 10, '00942B': 15, '00943': 15,
    '00944': 10, '00945B': 15, '00946': 10, '00947': 10,
    # 債券 ETF 多為 40 元起始
    '00679B': 40, '00687B': 40, '00696B': 40, '00697B': 40,
    '00710B': 40, '00711B': 40, '00712':  20, '00714':  30,
    '00718B': 40, '00719B': 40, '00720B': 40, '00721B': 40,
    '00722B': 40, '00723B': 40, '00724B': 40, '00725B': 40,
    '00726B': 40, '00727B': 40, '00772B': 40, '00773B': 40,
    '00777B': 40, '00778B': 40, '00779B': 40, '00780B': 40,
    '00781B': 40, '00782B': 40, '00783B': 40, '00784B': 40,
    '00785B': 40, '00786B': 40, '00787B': 40, '00788B': 40,
    '00795B': 40, '00834B': 40, '00836B': 40, '00837B': 40,
    '00840B': 40, '00845B': 40, '00846B': 40, '00847B': 40,
    '00848B': 40, '00849B': 40, '00853B': 40, '00857B': 40,
    '00859B': 40, '00860B': 40, '00862B': 40, '00863B': 40,
    '00864B': 40, '00865B': 40, '00867B': 40, '00870B': 40,
    '00883B': 40, '00890B': 40, '00937B': 40,
}


def _get_etf_launch_price(ticker: str, df: "pd.DataFrame|None" = None):
    """取得 ETF 發行價（用於 MK 規格條件 B 破發檢測）。

    優先序：
    1. 內建台灣 ETF 對照表（最精準）
    2. df 首個交易日收盤價（已還原權息，僅供 fallback 估算）

    Returns
    -------
    float | None
    """
    from shared.etf_codes import bare_etf_code as _bare
    _code = _bare(ticker)
    _v = _TW_ETF_LAUNCH_PRICE.get(_code)
    if _v is not None:
        return float(_v)
    # fallback：用 df 第一筆收盤估算（僅當美股 ETF / 未收錄者）
    try:
        if df is not None and len(df) > 0:
            return float(df['Close'].iloc[0])
    except Exception:
        pass
    return None


# v18.228 P1-S1：fetch_etf_price 跨 tab period 集中
# 原本 cache key = (ticker, period)，同檔 ETF 因 1y/5y/10y 不同 period 重抓 2~3 次。
# 改為單一 'max' fetch + 記憶體內切片，cache key 只剩 ticker。
_PERIOD_TO_DAYS = {
    '5d': 7, '1mo': 31, '3mo': 93, '6mo': 186,
    '1y': 365, '2y': 365 * 2, '3y': 365 * 3, '5y': 365 * 5,
    '10y': 365 * 10, 'ytd': 366, 'max': None,
}


@st.cache_data(ttl=TTL_1HOUR, max_entries=20)
def _fetch_etf_price_max(ticker: str) -> pd.DataFrame:
    """共用底層 — 一次抓 period='max'，供 fetch_etf_price 切片。

    v18.228 集中化：portfolio / single / grp_compare / backtest 跨 tab 同檔
    ETF 從 2~3 次 yfinance call → 1 次（cache key 只剩 ticker）。

    S-PROV-1 v18.251 phase 7:成功時 df.attrs 含 source/fetched_at(§2.2)。
    """
    try:
        df = yf.Ticker(ticker).history(period='max', auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        out = df.ffill()
        # S-PROV-1 v18.251:provenance via DataFrame.attrs(§2.2)
        out.attrs["source"] = f"Yahoo:{ticker}:history_max_adj"
        out.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return out
    except Exception as e:
        # S-H3 v18.244:L1 不可 st.error → 改 print log,caller 依 empty DataFrame 判斷
        print(f'[etf_fetch] ❌ 無法取得 {ticker} 價格:{type(e).__name__}: {e}')
        return pd.DataFrame()


def fetch_etf_price(ticker: str, period: str = '5y') -> pd.DataFrame:
    """取得 ETF 歷史價格（auto_adjust=True 還原權息）。

    v18.228 起改為共用 'max' 底層 + 記憶體切片。公開簽章不變，呼叫端 0 改動。
    S-PROV-1 v18.251:provenance attrs 從底層繼承(切片後顯式 copy 保留)。
    Phase 2 pandera Priority 1 v18.433:log-mode schema validation(yfinance 大寫,
    normalize_case=True);失敗只 stderr log,不擋 caller。
    """
    df = _fetch_etf_price_max(ticker)
    if df.empty:
        return df
    days = _PERIOD_TO_DAYS.get(period, 365 * 5)
    if days is None or len(df) == 0:
        result = df
    else:
        cutoff = df.index.max() - pd.Timedelta(days=days)
        result = df.loc[df.index >= cutoff]
        # v18.251 S-PROV-1:.loc 切片可能 lose attrs,顯式 copy 保留血緣
        result.attrs = dict(df.attrs)
    # Phase 2 pandera Priority 1 v18.433:log-mode schema validation
    try:
        from src.compute.risk.schemas import validate_in_log_mode, OHLCVSchema
        result = validate_in_log_mode(result, OHLCVSchema,
                                       label=f'fetch_etf_price:{ticker}:{period}',
                                       normalize_case=True)
    except Exception:
        pass
    return result


@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_etf_dividends(ticker: str) -> pd.Series:
    """取得 ETF 歷史配息。

    S-PROV-1 v18.251:成功時 s.attrs 含 source/fetched_at(§2.2)。
    """
    try:
        divs = yf.Ticker(ticker).dividends
        if divs.empty:
            return pd.Series(dtype=float)
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        # S-PROV-1 v18.251:provenance via Series.attrs
        divs.attrs["source"] = f"Yahoo:{ticker}:dividends"
        divs.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return divs
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=TTL_1HOUR, max_entries=300, show_spinner=False)
def fetch_etf_meta_moneydj(ticker: str) -> dict:
    """從 MoneyDJ Basic0004 一次取得台股 ETF metadata（走 NAS Squid + 中繼站）。

    為何需要：yfinance.info 在 Streamlit Cloud 經常被 Yahoo 海外 IP 封鎖
    或 rate limit；MoneyDJ Basic0004 走 NAS 中繼站（家用台灣 IP）可穩定取得
    台股 ETF 的 AUM / 費用率（經理費 + 保管費）/ 標的指數 / 中文名。

    Returns
    -------
    dict  欄位缺漏為 None；全失敗回 {}
        keys: zh_name / aum_twd / expense / manager_fee /
              custodian_fee / underlying_index
    """
    import re as _re_meta
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return {}
    if '.' not in _t:
        _t = f'{_t}.TW'

    _url = f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}'
    try:
        from src.data.proxy import fetch_url as _fu_meta
        _r = _fu_meta(_url, headers={'Referer': 'https://www.moneydj.com/'},
                      timeout=12, attempts=2)
        if _r is None or _r.status_code != 200:
            _code = _r.status_code if _r is not None else 'None'
            print(f'[MDJ/meta] {_t}: HTTP {_code}（含 NAS 中繼皆失敗）')
            return {}
        _r.encoding = 'utf-8'
        _txt = _r.text
    except Exception as _e:
        print(f'[MDJ/meta] {_t}: {type(_e).__name__}: {_e}')
        return {}

    _out: dict = {}

    # 1. 中文名（從 <title> 擷取首段）
    _m = _re_meta.search(
        r'<title>\s*([^<\-]{2,30}?)\s*-\s*[0-9]{4,5}[A-Z]?\.TW\s*-', _txt)
    if _m:
        _name = _m.group(1).strip()
        if any('一' <= _c <= '鿿' for _c in _name):
            _out['zh_name'] = _name

    # 2. 基金規模（億 → 元）
    _m = _re_meta.search(
        r'(?:基金規模|資產規模|淨資產)[^\d]{0,30}?'
        r'(\d{1,5}(?:,\d{3})*(?:\.\d+)?)\s*億', _txt)
    if _m:
        try:
            _out['aum_twd'] = float(_m.group(1).replace(',', '')) * 1e8
        except ValueError:
            pass

    # 3-4. 經理費 / 保管費（% → 比例）
    # MoneyDJ 標籤多為「經理費(%)」(值格無 %)，純 regex 會被標籤內 % 破壞，
    # 故以 _html_kv_pairs 儲存格配對為主（同經理人解析法）、regex 為輔。
    _kv_meta = _html_kv_pairs(_txt)

    def _pct_ratio(_raw):
        """字串取數字並轉比例（1.00 → 0.01）；無數字回 None。"""
        _mm = _re_meta.search(r'(\d+(?:\.\d+)?)', str(_raw).replace(',', ''))
        if not _mm:
            return None
        try:
            return float(_mm.group(1)) / 100.0
        except ValueError:
            return None

    for _labels, _key in ((('經理費', '管理費'), 'manager_fee'),
                          (('保管費',), 'custodian_fee')):
        _v = None
        for _k, _vv in _kv_meta.items():               # KV 主路徑
            if any(_lb in _k for _lb in _labels):
                _v = _pct_ratio(_vv)
                if _v is not None:
                    break
        if _v is None:                                  # regex 兜底
            for _lb in _labels:
                _m = _re_meta.search(rf'{_lb}[^\d%]{{0,30}}?(\d+(?:\.\d+)?)\s*%', _txt)
                if _m:
                    _v = _pct_ratio(_m.group(1))
                    break
        if _v is not None:
            _out[_key] = _v

    # 5. 合計總費用率（經理 + 保管）；若僅一項則退而求其次
    if 'manager_fee' in _out and 'custodian_fee' in _out:
        _out['expense'] = round(_out['manager_fee'] + _out['custodian_fee'], 6)
    elif 'manager_fee' in _out:
        _out['expense'] = _out['manager_fee']
    else:
        # 兜底：找「總費用率/內扣費用率」單一欄位（KV 優先 → regex）
        for _k, _vv in _kv_meta.items():
            if any(_lb in _k for _lb in ('總費用率', '內扣費用率', '內含費用率', '費用率')):
                _ev = _pct_ratio(_vv)
                if _ev is not None:
                    _out['expense'] = _ev
                    break
        if 'expense' not in _out:
            _m = _re_meta.search(
                r'(?:總費用率|內扣費用率|內含費用率|費用率)[^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%',
                _txt)
            if _m:
                _ev = _pct_ratio(_m.group(1))
                if _ev is not None:
                    _out['expense'] = _ev

    # 6. 追蹤指數（與 fetch_etf_underlying_index 同 regex 風格，HTML entity 預清洗）
    _txt_c = (_txt.replace('&nbsp;', ' ').replace('&#160;', ' ')
                  .replace('&amp;', '&').replace('　', ' '))
    _m = _re_meta.search(
        r'(?:追蹤|標的|對應)\s*指數[^一-鿿A-Za-z\d]{0,40}?'
        r'([一-鿿A-Za-z0-9 &\.\-／/（）()]{4,80})', _txt_c)
    if _m:
        _idx = _m.group(1).strip().rstrip('，,。.、 ')
        if 4 <= len(_idx) <= 80 and not any(b in _idx for b in (
                '追蹤誤差', '指數股票型', '指數型基金', 'nbsp', 'amp;')):
            _out['underlying_index'] = _idx

    if _out:
        print(f'[MDJ/meta] OK {_t} = {list(_out.keys())}')
        # S-PROV-1 phase 12 v18.258 — provenance(schema-additive)
        _out['source'] = 'MoneyDJ:Basic0004'
        _out['fetched_at'] = pd.Timestamp.now('UTC').isoformat()
    else:
        print(f'[MDJ/meta] {_t}: 200 但無欄位匹配')
    return _out


@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_etf_info(ticker: str) -> dict:
    """取得 ETF 基本資訊（費用率 / Beta / AUM）。

    yfinance.info 主源（含 Beta、海外 ETF 必要）→ MoneyDJ Basic0004 補齊
    AUM/expense（yfinance 海外 IP 經常被擋時自動補位，台股 ETF only）。

    S-PROV-1 v18.253:回傳 dict 含 source + fetched_at 兩個 key(§2.2)。
    """
    # S-PROV-1 v18.253:provenance
    _fetched_at = pd.Timestamp.now('UTC').isoformat()
    try:
        _info = yf.Ticker(ticker).info or {}
        _src = f"Yahoo:{ticker}:info"
    except Exception:
        _info = {}
        _src = f"Yahoo:{ticker}:info:failed"

    # 補齊：yfinance.info 空或缺 AUM/expense 時，從 MoneyDJ Basic0004 fetch
    _t = (ticker or '').upper()
    _is_tw = _t.endswith('.TW') or _t.endswith('.TWO')
    if _is_tw and (not _info.get('totalAssets') or not _info.get('expenseRatio')):
        _meta = fetch_etf_meta_moneydj(ticker)
        if _meta:
            if not _info.get('totalAssets') and _meta.get('aum_twd'):
                _info['totalAssets'] = _meta['aum_twd']
            if not _info.get('expenseRatio') and _meta.get('expense'):
                _info['expenseRatio'] = _meta['expense']
            if not _info.get('annualReportExpenseRatio') and _meta.get('expense'):
                _info['annualReportExpenseRatio'] = _meta['expense']
            # longName 補中文名（yfinance 多為英文）
            if _meta.get('zh_name') and not any(
                    '一' <= _c <= '鿿' for _c in str(_info.get('longName', ''))):
                _info['longName'] = _meta['zh_name']
            # 若靠 MoneyDJ 補了東西,更新 source 表示 hybrid
            if not _src.endswith(':failed') and (_meta.get('aum_twd') or _meta.get('expense')):
                _src = f"Yahoo:{ticker}:info+MoneyDJ:Basic0004"
    # S-PROV-1 v18.253:provenance
    _info['source'] = _src
    _info['fetched_at'] = _fetched_at
    return _info


def fetch_sitca_expense_ratio(ticker: str, *, attempts: int = 1):
    """從 SITCA 投信投顧公會抓台股 ETF 內扣費用率（Primary，海外 IP 走 NAS proxy）。

    URL: https://www.sitca.org.tw/ROC/Industry/IN2211.aspx?pid=IN2222_01

    Returns
    -------
    float | None  比例形式（0.0036 = 0.36%）；找不到 ticker 或抓取失敗回 None。
    """
    from src.data.proxy import fetch_url as _fu_sit
    import pandas as _pd_sit, re as _re_sit
    from shared.etf_codes import bare_etf_code as _bare
    _t = _bare(ticker)
    # 主動式 ETF 後綴字母（00982A、00980A、00406A）→ SITCA 表格僅收純數字代號，先剝
    _t_num = _re_sit.sub(r'[A-Za-z]+$', '', _t)
    if not _t_num or not _t_num.isdigit():
        return None  # SITCA 只收純台股 ETF 數字代號（0050、00878、剝 'A' 後的 00982）
    try:
        r = _fu_sit(
            'https://www.sitca.org.tw/ROC/Industry/IN2211.aspx?pid=IN2222_01',
            timeout=15, attempts=attempts,
        )
        if r is None or r.status_code != 200:
            return None
        r.encoding = 'utf-8'
        # ASP.NET 頁面通常一張總費用率表；多表都試找含「代號」+「費用率」欄位的那張
        tables = _pd_sit.read_html(r.text)
        # ticker 標準化：去掉 leading 0（治 pandas 把 "0050" parse 成 int 50 的場景）
        _tn = _t_num.lstrip('0') or '0'
        for tbl in tables:
            # 注意：column 可能是 MultiIndex tuple，比對用 str(c)，但取值用原物件 c
            code_col = next((c for c in tbl.columns
                             if any(k in str(c) for k in ('代號', 'ETF', 'Code'))), None)
            rate_col = next((c for c in tbl.columns
                             if '費用率' in str(c) or '費用比率' in str(c)), None)
            if code_col is None or rate_col is None:
                continue
            # 雙向 leading-zero 容忍：cell 也 strip leading 0 後比對
            _digits = tbl[code_col].astype(str).str.replace(r'\D', '', regex=True)
            row = tbl[_digits.where(_digits != '', '0').str.lstrip('0').replace('', '0') == _tn]
            if row.empty:
                continue
            raw = str(row[rate_col].iloc[0])
            m = _re_sit.search(r'(\d+(?:\.\d+)?)', raw)
            if not m:
                continue
            v = float(m.group(1))
            # SITCA 表格數字常見已是百分比（0.36 = 0.36%），標準化成「比例」回傳
            print(f'[SITCA/expense] ✅ {_t} = {v}% (col={rate_col})')
            _prov_log('fetch_sitca_expense_ratio', 'SITCA:IN2222_01', _t, f'{v/100.0:.6f}')
            return v / 100.0
        print(f'[SITCA/expense] ⚠️ {_t} 未找到符合 column 的表格 (tables={len(tables)})')
        _prov_log('fetch_sitca_expense_ratio', 'SITCA:IN2222_01', _t, 'None:no-match')
        return None
    except Exception as e:
        print(f'[SITCA/expense] ❌ {_t}: {type(e).__name__}: {e}')
        _prov_log('fetch_sitca_expense_ratio', 'SITCA:IN2222_01', _t, f'None:exc:{type(e).__name__}')
        return None


def fetch_moneydj_expense_ratio(ticker: str):
    """從 MoneyDJ ETF Basic0004 頁面抓「經理費 + 保管費」總費用率（私募/已下市 ETF 備援）。

    URL: https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid=XXXX.TW

    Returns
    -------
    float | None  比例形式（0.0036 = 0.36%）；找不到或抓取失敗回 None。
    """
    import re as _re_mdje
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    # MoneyDJ etfid 通常吃 '0050.TW' 格式；純數字補 .TW
    if _t.isdigit():
        _t = f'{_t}.TW'
    _url = f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}'
    try:
        # 走 fetch_url（NAS Squid → 直連 → NAS 中繼站 fallback，PR #100）
        from src.data.proxy import fetch_url as _fu_mdje
        _r = _fu_mdje(_url, headers={'Referer': 'https://www.moneydj.com/'},
                      timeout=12, attempts=2)
        if _r is None or _r.status_code != 200:
            _code = _r.status_code if _r is not None else 'None'
            print(f'[MoneyDJ/expense] {_t}: HTTP {_code}（含 NAS 中繼皆失敗）')
            return None
        _txt = _r.text
        # 直掃「經理費 X.XX%」與「保管費 X.XX%」合計；MoneyDJ Basic0004 表格常以 td 緊鄰呈現
        _mng = _re_mdje.search(r'經理費[^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%', _txt)
        _cus = _re_mdje.search(r'保管費[^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%', _txt)
        if _mng and _cus:
            _total = float(_mng.group(1)) + float(_cus.group(1))
            print(f'[MoneyDJ/expense] ✅ {_t} = {_total}% (mng={_mng.group(1)}+cus={_cus.group(1)})')
            _prov_log('fetch_moneydj_expense_ratio', 'MoneyDJ:Basic0004:mng+cus',
                      _t, f'{_total/100.0:.6f}')
            return _total / 100.0
        # Fallback：找「總費用率 / 內含費用率」單一欄位
        _tot = _re_mdje.search(r'(?:總費用率|內含費用率|費用率)[^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%', _txt)
        if _tot:
            _v = float(_tot.group(1))
            print(f'[MoneyDJ/expense] ✅ {_t} = {_v}% (總費用率欄位)')
            _prov_log('fetch_moneydj_expense_ratio', 'MoneyDJ:Basic0004:total',
                      _t, f'{_v/100.0:.6f}')
            return _v / 100.0
        print(f'[MoneyDJ/expense] ⚠️ {_t} 頁面無「經理費/保管費/總費用率」欄位')
        _prov_log('fetch_moneydj_expense_ratio', 'MoneyDJ:Basic0004', _t, 'None:no-match')
        return None
    except Exception as _e:
        print(f'[MoneyDJ/expense] ❌ {_t}: {type(_e).__name__}: {_e}')
        _prov_log('fetch_moneydj_expense_ratio', 'MoneyDJ:Basic0004',
                  _t, f'None:exc:{type(_e).__name__}')
        return None


def _fetch_holdings_yahoo_tw(symbol_yf: str):
    """台灣 Yahoo 股市 ETF 持股頁（國內版 Yahoo，海外 IP 可直連、繞過 MoneyDJ 403）。

    URL：https://tw.stock.yahoo.com/quote/{symbol}/holding
    symbol_yf：yfinance 格式代號（如 '00980A.TW' / '0050.TW'）。
    解析雙策略：① 頁面內嵌 JSON（名稱+權重鍵）② BeautifulSoup 表格列（中文名 + n.nn%）。
    回 {個股名稱: 權重%} 或 None（抓不到 / 解析不出）。
    """
    import re as _re_y
    try:
        from src.data.proxy import fetch_url as _fu_y
    except Exception:
        return None
    _url = f'https://tw.stock.yahoo.com/quote/{symbol_yf}/holding'
    try:
        _r = _fu_y(_url, timeout=15, attempts=2)
    except Exception as _e:
        print(f'[Holdings/YahooTW] fetch 異常 {symbol_yf}: {type(_e).__name__}: {_e}')
        return None
    if _r is None or getattr(_r, 'status_code', None) != 200:
        print(f'[Holdings/YahooTW] {symbol_yf} 無回應 / 非 200')
        return None
    try:
        _r.encoding = 'utf-8'
    except Exception:
        pass
    _html = _r.text or ''
    _out = {}
    # ── 策略 A：頁面內嵌 JSON（名稱鍵 + 權重鍵就近配對）──
    for _m in _re_y.finditer(
        r'"(?:name|symbolName|holdingName|stockName)"\s*:\s*"([^"]{1,40})"'
        r'[^{}]{0,200}?"(?:weighting|holdingPercent|percent|weight|ratio)"'
        r'\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',
        _html
    ):
        _nm = _m.group(1).strip()
        try:
            _w = float(_m.group(2))
        except ValueError:
            continue
        if _w <= 1.5:           # 小數表示（0.05）→ 轉百分比
            _w *= 100
        if _nm and not _nm.isdigit() and 0 < _w <= 100 and _nm not in _out:
            _out[_nm] = round(_w, 4)
        if len(_out) >= 60:
            break
    if _out:
        print(f'[Holdings/YahooTW] ✅(JSON) {symbol_yf} {len(_out)} 檔')
        return _out
    # ── 策略 B：表格純文字（中文股名 + n.nn% 同列）──
    try:
        from bs4 import BeautifulSoup as _BS_y
        _txt = _BS_y(_html, 'html.parser').get_text(' ', strip=True)
        for _m in _re_y.finditer(
            r'([一-鿿][一-鿿A-Za-z0-9&\.\-]{1,29})\s+'
            r'([0-9]{1,2}\.[0-9]{1,2})\s*%', _txt
        ):
            _nm = _m.group(1).strip()
            try:
                _w = float(_m.group(2))
            except ValueError:
                continue
            if (_nm and not _nm.isdigit() and 0 < _w <= 100
                    and _nm not in _out
                    and _nm not in ('持股權重', '權重', '比例', '持股比例')):
                _out[_nm] = _w
            if len(_out) >= 60:
                break
    except Exception as _eb:
        print(f'[Holdings/YahooTW] BS 解析異常 {symbol_yf}: {type(_eb).__name__}: {_eb}')
    if _out:
        print(f'[Holdings/YahooTW] ✅(HTML) {symbol_yf} {len(_out)} 檔')
        _prov_log('_fetch_holdings_yahoo_tw', 'Yahoo:tw.stock:quote/holding',
                  symbol_yf, f'dict:{len(_out)}items')
        return _out
    print(f'[Holdings/YahooTW] ⚪ {symbol_yf} 頁面無可解析持股')
    _prov_log('_fetch_holdings_yahoo_tw', 'Yahoo:tw.stock:quote/holding',
              symbol_yf, 'None:no-match')
    return None


def _enrich_tw_holding_name(raw_name: str, symbol) -> str:
    """持股顯示成「中文名 (代碼)」。

    - symbol 形如 '2330.TW'：台股代號（4-6 碼數字，末可帶字母）→ 以
      stock_names.get_stock_name 補中文；查無中文時退回「原名 (代碼)」至少帶出代碼。
    - 海外成分股（如美股 ETF 的 AAPL）或無法判別 → 原樣回傳，不畫蛇添足。
    """
    import re as _re_n
    from shared.etf_codes import bare_etf_code as _bare
    _code = _bare(symbol)
    if not _re_n.fullmatch(r'\d{4,6}[A-Z]?', _code):
        return raw_name
    _zh = ''
    try:
        from src.config import get_stock_name as _gsn
        _zh = _gsn(_code) or ''
    except Exception:
        _zh = ''
    if _zh and _re_n.search(r'[一-鿿]', _zh):
        return f'{_zh} ({_code})'
    return f'{raw_name} ({_code})'


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_etf_holdings(ticker: str):
    """抓 ETF 成份股清單（個股名稱 → 權重 %）。台股 ETF 為主，海外 ETF 走 yfinance 兜底。

    多段備援（按順序嘗試，任一成功即返回）：
      1. yfinance `.funds_data.top_holdings` — 海外 ETF 主源；台股通常 None
      1.5 台灣 Yahoo 股市 /quote/{sym}/holding — 台股 ETF 主源（海外 IP 可直連）
      2. MoneyDJ 三條 URL 並掃（備源，海外 IP 需 NAS proxy）：
         - Basic0007.xdjhtm（持股明細）
         - Basic0008.xdjhtm（投資配置）
         - RankA0001.xdjhtm（持股排名）
      3. 全失敗回 None（UI 端標 ⚪ N/A）

    Returns
    -------
    dict[str, float] | None
        key=個股名稱（中/英文），value=權重百分比（如 5.23 代表 5.23%）
        無資料 / 抓取失敗回 None。

    Cache
    -----
    TTL 86400 秒（1 日），因 ETF 成份股月度才更新。
    """
    import re as _re_h
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    _t_yf = _t if '.' in _t else (f'{_t}.TW' if _t.isdigit() else _t)
    _t_mdj = _t_yf  # MoneyDJ etfid 同 yfinance ticker

    # ── 1. yfinance funds_data（海外 ETF 主源）──────────────────
    try:
        _yt = yf.Ticker(_t_yf)
        _fd = getattr(_yt, 'funds_data', None)
        if _fd is not None:
            _th = getattr(_fd, 'top_holdings', None)
            if _th is not None and hasattr(_th, 'iterrows') and not _th.empty:
                _out = {}
                for _idx, _row in _th.iterrows():
                    _name = str(_row.get('Name', _idx) or _idx).strip()
                    _sym  = _row.get('Symbol', _idx)  # top_holdings index 多為代號
                    _w_raw = _row.get('Holding Percent', _row.get('% of Net Assets', None))
                    if _w_raw is None or _name == '':
                        continue
                    try:
                        _w = float(_w_raw)
                    except (TypeError, ValueError):
                        continue
                    # yfinance 多以小數表示（0.05 = 5%）；> 1 視為已是百分比
                    if _w <= 1.5:
                        _w = _w * 100
                    if _w > 0:
                        _out[_enrich_tw_holding_name(_name, _sym)] = round(_w, 4)
                if _out:
                    print(f'[Holdings/yf] ✅ {_t_yf} {len(_out)} 檔')
                    _prov_log('fetch_etf_holdings', 'yfinance:funds_data:top_holdings',
                              _t_yf, f'dict:{len(_out)}items')
                    return _out
    except Exception as _ey:
        print(f'[Holdings/yf] {_t_yf}: {type(_ey).__name__}: {_ey}')

    # ── 1.5 台灣 Yahoo 股市（國內版 Yahoo，台股 ETF 主源）────────
    # Yahoo CDN 海外 IP 可直連，繞過 MoneyDJ 對海外 IP 的 403 封鎖
    _yh = _fetch_holdings_yahoo_tw(_t_yf)
    if _yh:
        _prov_log('fetch_etf_holdings', 'Yahoo:tw:holding(via _fetch_holdings_yahoo_tw)',
                  _t_yf, f'dict:{len(_yh)}items')
        return _yh

    # ── 2. MoneyDJ 三條 URL 嘗試（台股 ETF 備源）────────────────
    # 走 proxy_helper（NAS Squid 台灣 IP）為主源 — MoneyDJ 反爬擋海外 IP 回 403；
    # curl_cffi 留作 fallback（本機開發或 proxy 掛掉時）
    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0007.xdjhtm?etfid={_t_mdj}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0008.xdjhtm?etfid={_t_mdj}',
        f'https://www.moneydj.com/ETF/X/Basic/RankA0001.xdjhtm?etfid={_t_mdj}',
    ]
    for _url in _urls:
        _txt = None
        # ── 2a. proxy_helper 主源 ───
        try:
            from src.data.proxy import fetch_url as _fu_h
            _r = _fu_h(_url, timeout=15, attempts=2)
            if _r is not None and _r.status_code == 200:
                _r.encoding = 'utf-8'
                _txt = _r.text
        except Exception as _eph:
            print(f'[Holdings/MDJ] proxy 異常 {_t_mdj}: {type(_eph).__name__}: {_eph}')
        # ── 2b. curl_cffi fallback ─
        if _txt is None:
            try:
                from curl_cffi import requests as _cffi_h
                _r2 = _cffi_h.get(_url, impersonate='chrome124', timeout=15)
                if _r2.status_code == 200:
                    _txt = _r2.text
                else:
                    print(f'[Holdings/MDJ] curl_cffi {_t_mdj} {_url[-30:]}: HTTP {_r2.status_code}')
            except Exception as _eh:
                print(f'[Holdings/MDJ] curl_cffi 異常 {_t_mdj} {_url[-30:]}: {type(_eh).__name__}: {_eh}')
        if _txt is None:
            continue
        # ── 寬鬆 regex 擷取：個股名（中文/英數）+ 後續百分比 ──
        try:
            _stocks = {}
            for _m in _re_h.finditer(
                r'>([一-鿿 A-Z0-9&\.\-]{2,30})</[^>]+>[^<]*<[^>]+>\s*(\d{1,2}\.\d{1,3})\s*%',
                _txt
            ):
                _nm = _m.group(1).strip()
                if (_nm and not _nm.isdigit() and not _nm.replace('.', '').isdigit()
                        and _nm not in ('持股比例', '比例', '持股比重', '權重', '個股名稱', '名稱')
                        and len(_nm) >= 2):
                    try:
                        _w = float(_m.group(2))
                        if 0 < _w <= 100 and _nm not in _stocks:
                            _stocks[_nm] = _w
                    except ValueError:
                        continue
                if len(_stocks) >= 50:
                    break
            if _stocks:
                print(f'[Holdings/MDJ] ✅ {_t_mdj} {len(_stocks)} 檔 ({_url[-30:]})')
                _prov_log('fetch_etf_holdings', f'MoneyDJ:{_url[-30:]}',
                          _t_mdj, f'dict:{len(_stocks)}items')
                return _stocks
        except Exception as _eh2:
            print(f'[Holdings/MDJ] regex 異常 {_t_mdj} {_url[-30:]}: {type(_eh2).__name__}: {_eh2}')
            continue

    print(f'[Holdings] ❌ {_t} — yf/MoneyDJ 三條 URL 全失敗')
    _prov_log('fetch_etf_holdings', 'all-sources-failed', _t, 'None:all-fail')
    return None


# ══════════════════════════════════════════════════════════════
# 主動式 ETF 判別 + 經理人查詢（PR — claude/etf-weakness-manager）
# ══════════════════════════════════════════════════════════════
# 主動式台股 ETF 白名單（代號末多帶字母 A/D/T；2024-2026 元大/復華/野村等募集）
# 補：純數字代號的主動式 ETF（如未來新版）需手動加進來
_ACTIVE_TW_ETF_WHITELIST = {
    # 元大主動式系列（2024 Q4 ~ 2026）
    '00980A', '00982A', '00984A', '00989A', '00992A',
    '00982T', '00980D',
    # 復華 / 國泰 / 中信 / 野村 主動式（補充清單，依公告陸續加入）
    '00981A', '00983A', '00985A', '00986A', '00987A',
    '00988A', '00990A', '00991A', '00993A', '00994A',
    '00995A', '00996A', '00997A',
}


def is_active_etf(ticker: str) -> bool:
    """判別 ETF 是主動式 (Active) 還是被動式 (Passive)。

    判別優先序：
      1. 白名單命中 → True
      2. 代號末位 ∈ {B 債券 / L 槓桿(正2) / R 反向(反1) / U,F 期貨} → False（皆被動追蹤，非主動經理式）
      3. 代號末位為其他字母（A 主動 / D / T 等）→ True（主動式）
      4. 純數字代號 → False（被動追蹤指數，如 0050/00878/00940）
    """
    if not ticker:
        return False
    from shared.etf_codes import bare_etf_code as _bare
    _code = _bare(ticker)
    if _code in _ACTIVE_TW_ETF_WHITELIST:
        return True
    if not _code:
        return False
    _last = _code[-1]
    # 台股後綴：L=槓桿(正2,如 00631L) / R=反向(反1,如 00632R) / B=債券 / U,F=期貨 → 皆被動追蹤,非主動。
    # (原本排除集寫 ('B','K') 有誤:台股無 'K' 後綴,且漏掉 L/R → 槓桿/反向 ETF 被誤判成主動式 → 跑錯弱勢判定)
    if _last in ('B', 'L', 'R', 'U', 'F'):
        return False
    if _last.isalpha():       # A(主動) / D / T 等 = 主動式
        return True
    return False              # 純數字 = 被動追蹤指數


def _fetch_yuanta_active_etf_meta(ticker: str) -> dict | None:
    """元大投信官網 fallback — 抓主動式 ETF 經理人 / 費用率 / NAV。

    為何需要：MoneyDJ Basic0001/0006/0011 / SITCA 對主動式 ETF（00980A 等）
    無經理人欄位，元大投信官網才是源頭。多 URL 嘗試，HTML regex 解析。

    Returns
    -------
    dict | None
        成功：{
            'manager':   str | None,    經理人姓名
            'expense':   float | None,  總費用率（小數，0.0085 = 0.85%）
            'nav_latest': float | None, 最近一日 NAV
            'nav_date':   str | None,   NAV 日期 YYYY-MM-DD
            'source':     'yuanta-official',
            'url':        str,
        }
        失敗：None
    """
    import re as _re_y
    from shared.etf_codes import bare_etf_code as _bare
    _code = _bare(ticker)
    if not _code or not is_active_etf(ticker):
        return None
    _urls = [
        f'https://www.yuantaetfs.com/product/detail/{_code}/profile',
        f'https://www.yuantaetfs.com/product/detail/{_code}',
        f'https://www.yuantaetfs.com/RtnPercent/Detail/{_code}',
    ]
    for _url in _urls:
        _txt = None
        try:
            from src.data.proxy import fetch_url as _fu_y
            _r = _fu_y(_url, timeout=12, attempts=2)
            if _r is not None and _r.status_code == 200 and len(_r.text or '') > 500:
                _r.encoding = 'utf-8'
                _txt = _r.text
        except Exception as _ey:
            print(f'[Yuanta/{_code}] proxy 異常 {_url}: {type(_ey).__name__}: {_ey}')
            continue
        if not _txt:
            continue
        _out: dict = {'manager': None, 'expense': None,
                      'nav_latest': None, 'nav_date': None,
                      'source': 'yuanta-official', 'url': _url}
        _m = _re_y.search(
            r'(?:基金)?經理人[\s\:：]*([一-鿿]{2,8}(?:\s*[\/、，]\s*[一-鿿]{2,8})*)',
            _txt,
        )
        if _m:
            _out['manager'] = _m.group(1).strip().replace(' ', '')
        _e = _re_y.search(
            r'(?:總費用率|經理費[\s\S]{0,80}?保管費[\s\S]{0,40}?)[\s\:：]{0,5}(\d+\.\d{1,3})\s*%',
            _txt,
        )
        if _e:
            try:
                _out['expense'] = float(_e.group(1)) / 100.0
            except ValueError:
                pass
        _n = _re_y.search(
            r'(?:淨值|單位淨值|NAV)[\s\:：]*(\d+\.\d{2,4})',
            _txt,
        )
        if _n:
            try:
                _out['nav_latest'] = float(_n.group(1))
            except ValueError:
                pass
        _nd = _re_y.search(r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', _txt)
        if _nd:
            try:
                from datetime import date as _date_y
                _y, _mo, _d = (int(_nd.group(i)) for i in (1, 2, 3))
                _out['nav_date'] = _date_y(_y, _mo, _d).isoformat()
            except (ValueError, OverflowError):
                pass
        if any(_out.get(k) for k in ('manager', 'expense', 'nav_latest')):
            print(f'[Yuanta/{_code}] ✅ via {_url[:60]}... '
                  f'manager={_out.get("manager")} '
                  f'expense={_out.get("expense")} '
                  f'nav={_out.get("nav_latest")}')
            # S-PROV-1 P0 v18.434:dict 已有 'source':'yuanta-official',補 fetched_at(§2.2)
            _out.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
            return _out
    return None


def _html_kv_pairs(html_text: str) -> dict:
    """把 HTML 表格 td/th 相鄰儲存格配成 {欄位名: 值}（沿用新聞專案解析法）。

    MoneyDJ 標籤(如「經理人」「經理費(%)」)的值在相鄰儲存格,純 regex 易被
    標籤內 % 或 HTML 干擾;改用儲存格配對更穩健。只在『前格像欄位名(含中文、
    ≤12字)』時配對,濾掉報價頁雜訊。
    """
    import re as _re_kv
    from html.parser import HTMLParser as _HP_kv

    class _Cells(_HP_kv):
        def __init__(self):
            super().__init__()
            self.cells, self._buf = [], None
        def handle_starttag(self, tag, attrs):
            if tag in ('td', 'th'):
                self._buf = []
        def handle_data(self, data):
            if self._buf is not None:
                self._buf.append(data)
        def handle_endtag(self, tag):
            if tag in ('td', 'th') and self._buf is not None:
                self.cells.append(_re_kv.sub(r'\s+', ' ', ''.join(self._buf)).strip())
                self._buf = None

    _p = _Cells()
    try:
        _p.feed(html_text or '')
    except Exception:
        return {}
    _cells = [c for c in _p.cells if c]
    _kv: dict = {}
    for _i in range(len(_cells) - 1):
        _key = _cells[_i].rstrip(':： ').strip()
        _val = _cells[_i + 1].strip()
        if _val and _key and _key not in _kv and len(_key) <= 12 and _re_kv.search(r'[一-鿿]', _key):
            _kv[_key] = _val
    return _kv


@st.cache_data(ttl=TTL_7DAY, show_spinner=False)
def fetch_etf_manager(ticker: str):
    """從 MoneyDJ ETF 抓「現任經理人 + 任期起始日」。

    抓取策略
    --------
    多 URL 嘗試（同 proxy，不同 endpoint）：
      1. Basic0001.xdjhtm — 基本資料（傳統入口）
      2. Basic0006.xdjhtm — 基金概觀（基金資訊類，新 ETF 可能在此）
      3. Basic0011.xdjhtm — 基金特色（少見但部分基金有）
    每 URL 內：proxy_helper 主源 → curl_cffi fallback。

    Regex 寬鬆策略
    --------------
    名字：「經理人」「基金經理人」「現任經理人」(中間可有 HTML/whitespace) 後接中文 2-8 字
    任期：「到職日」「上任日」「任期」「管理基金日」「派任日」其中之一 + 日期

    Returns
    -------
    dict | None
        成功：{'name': '張三', 'since': '2024-04-15', 'tenure_days': 400}
        失敗：None;失敗原因寫入 _ETF_MANAGER_LAST_ERR[ticker]
              (UI 透過 get_etf_manager_last_err() accessor 讀,S-H3 v18.244)
    """
    import re as _re_mg
    from datetime import date as _date_mg
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    if '.' not in _t:
        _t = f'{_t}.TW'

    # Basic0004(簡介頁)就有「經理人」欄(fetch_etf_meta_moneydj 抓的同一頁)，擺第一優先。
    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0006.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0011.xdjhtm?etfid={_t}',
    ]
    _err_trace: list[str] = []
    _best = None   # 名字已抓到但缺到職日時暫存；續查其他頁是否有任期再決定

    for _url in _urls:
        _txt = None
        _endpoint = _url.split('/')[-1].split('?')[0]
        # ── 1. proxy_helper（NAS Squid 台灣 IP）主源 ─────────────
        try:
            from src.data.proxy import fetch_url as _fu_mg
            _r = _fu_mg(_url, timeout=12, attempts=2)
            if _r is not None and _r.status_code == 200 and len(_r.text or '') > 500:
                _r.encoding = 'utf-8'
                _txt = _r.text
            else:
                _code = _r.status_code if _r is not None else 'None'
                _ln = len(_r.text or '') if _r is not None else 0
                _err_trace.append(f'proxy {_endpoint}: HTTP {_code} len={_ln}')
                print(f'[MDJ/manager] proxy {_t} {_endpoint}: HTTP {_code} len={_ln}')
        except Exception as _ep:
            _err_trace.append(f'proxy {_endpoint}: {type(_ep).__name__}')
            print(f'[MDJ/manager] proxy 異常 {_t} {_endpoint}: {type(_ep).__name__}: {_ep}')

        # ── 2. curl_cffi fallback ────────────────────────────────
        if _txt is None:
            try:
                from curl_cffi import requests as _cffi_mg
                _r2 = _cffi_mg.get(_url, impersonate='chrome124', timeout=12)
                if _r2.status_code == 200 and len(_r2.text or '') > 500:
                    _txt = _r2.text
                else:
                    _err_trace.append(f'cffi {_endpoint}: HTTP {_r2.status_code}')
                    print(f'[MDJ/manager] curl_cffi {_t} {_endpoint}: HTTP {_r2.status_code}')
            except Exception as _ec:
                _err_trace.append(f'cffi {_endpoint}: {type(_ec).__name__}')
                print(f'[MDJ/manager] curl_cffi 異常 {_t} {_endpoint}: {type(_ec).__name__}: {_ec}')

        if _txt is None:
            continue

        # ── 3a. KV 儲存格解析（穩健，優先 regex）：經理人/到職日常在表格相鄰格 ──
        try:
            _kv_mg = _html_kv_pairs(_txt)
            _nm_raw = ''
            for _k in ('基金經理人', '現任經理人', '經理人'):
                if _k in _kv_mg:
                    _nm_raw = _kv_mg[_k]
                    break
            if not _nm_raw:
                for _k, _v in _kv_mg.items():
                    if '經理' in _k:
                        _nm_raw = _v
                        break
            _nm_m2 = _re_mg.search(r'[一-鿿]{2,8}', _nm_raw)  # 取第一段中文（避開「、」多人）
            if _nm_m2:
                _name = _nm_m2.group(0)
                _since, _days = None, None
                _dt_raw = ''
                for _k in ('到職日', '上任日', '派任日', '起聘日', '管理基金日', '任期'):
                    if _k in _kv_mg:
                        _dt_raw = _kv_mg[_k]
                        break
                _dm2 = _re_mg.search(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', _dt_raw)
                if _dm2:
                    try:
                        _dtv = _date_mg(int(_dm2.group(1)), int(_dm2.group(2)), int(_dm2.group(3)))
                        _since = _dtv.strftime('%Y-%m-%d')
                        _days = (_date_mg.today() - _dtv).days
                    except ValueError:
                        pass
                if _since:
                    print(f'[MDJ/manager] ✅(KV) {_t} = {_name} via {_endpoint} (since={_since}, days={_days})')
                    # S-PROV-1 phase 11 v18.257 — provenance(schema-additive)
                    return {'name': _name, 'since': _since, 'tenure_days': _days,
                            'source': f'MoneyDJ:{_endpoint}:KV',
                            'fetched_at': pd.Timestamp.now('UTC').isoformat()}
                if _best is None:   # 名字有、到職日缺 → 暫存，續查其他頁
                    _best = {'name': _name, 'since': None, 'tenure_days': None,
                             'source': f'MoneyDJ:{_endpoint}:KV',
                             'fetched_at': pd.Timestamp.now('UTC').isoformat()}
                    print(f'[MDJ/manager] (KV) {_t} = {_name} via {_endpoint}，無到職日，續查其他頁')
        except Exception as _ekv:
            print(f'[MDJ/manager] KV parse 略過 {_endpoint}: {type(_ekv).__name__}')

        # ── 3. 寬鬆 regex 嘗試解析 ────────────────────────────────
        try:
            # 名字：經理人 / 基金經理人 / 現任經理人 ... 中文 2-8 字
            _name_m = _re_mg.search(
                r'(?:基金|現任)?\s*經理人[^<>]{0,50}?>\s*([一-鿿]{2,8})\s*[<\(]',
                _txt,
            )
            # 寬鬆 fallback：經理人後直接接中文（無 > 標籤）
            if not _name_m:
                _name_m = _re_mg.search(
                    r'(?:基金|現任)?\s*經理人[^一-鿿\d]{0,30}?([一-鿿]{2,8})',
                    _txt,
                )
            _date_m = _re_mg.search(
                r'(?:到職日|上任日|任期|管理基金日|派任日|起聘日)[^\d]{0,30}?(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})',
                _txt,
            )
            if not _name_m:
                _err_trace.append(f'{_endpoint}: 200 但 regex 無經理人')
                print(f'[MDJ/manager] ⚠️ {_t} {_endpoint}: 200 但 regex 無經理人')
                continue
            _name = _name_m.group(1).strip()
            _since, _days = None, None
            if _date_m:
                _y, _mo, _d = (int(_date_m.group(i)) for i in (1, 2, 3))
                try:
                    _dt = _date_mg(_y, _mo, _d)
                    _since = _dt.strftime('%Y-%m-%d')
                    _days = (_date_mg.today() - _dt).days
                except ValueError:
                    pass
            if _since:
                print(f'[MDJ/manager] ✅ {_t} = {_name} via {_endpoint} (since={_since}, days={_days})')
                # S-PROV-1 phase 11 v18.257 — provenance(schema-additive)
                return {'name': _name, 'since': _since, 'tenure_days': _days,
                        'source': f'MoneyDJ:{_endpoint}:regex',
                        'fetched_at': pd.Timestamp.now('UTC').isoformat()}
            if _best is None:
                _best = {'name': _name, 'since': None, 'tenure_days': None,
                         'source': f'MoneyDJ:{_endpoint}:regex',
                         'fetched_at': pd.Timestamp.now('UTC').isoformat()}
                print(f'[MDJ/manager] (regex) {_t} = {_name} via {_endpoint}，無到職日，續查其他頁')
        except Exception as _e:
            _err_trace.append(f'{_endpoint}: regex 例外 {type(_e).__name__}')
            print(f'[MDJ/manager] ❌ regex parse {_t} {_endpoint}: {type(_e).__name__}: {_e}')

    # MoneyDJ 各頁掃完：有名字但全無到職日 → 回名字（任期 UI 顯示「未揭露」屬實）
    if _best is not None:
        print(f'[MDJ/manager] ▶ {_t} = {_best["name"]}（MoneyDJ 各頁皆無到職日）')
        return _best

    # ── 4. SITCA fallback — 與費用率同 proxy 路徑（已證可走）────────
    from shared.etf_codes import bare_etf_code as _bare4
    if _bare4(_t).isdigit():
        _sitca = _fetch_sitca_manager(_t)
        if _sitca and _sitca.get('name'):
            print(f'[SITCA/manager] ✅ {_t} = {_sitca["name"]}')
            # S-PROV-1 phase 11 v18.257 — provenance(schema-additive)
            _sitca.setdefault('source', 'SITCA:fund-manager-table')
            _sitca.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
            return _sitca
        else:
            _err_trace.append('sitca: 多 URL/多 column 比對全失敗')

    # ── 5. Yuanta 官網 fallback — 主動式 ETF 專屬（v1.1）─────────────
    _yu = _fetch_yuanta_active_etf_meta(_t)
    if _yu and _yu.get('manager'):
        print(f'[Yuanta/manager] ✅ {_t} = {_yu["manager"]}')
        # S-PROV-1 phase 11 v18.257 — provenance(schema-additive,既有 'source' 保留)
        return {'name': _yu['manager'], 'since': None, 'tenure_days': None,
                'source': 'Yuanta:official',
                'fetched_at': pd.Timestamp.now('UTC').isoformat()}
    elif _yu is not None:
        _err_trace.append('yuanta: 200 但 regex 無經理人')
    else:
        if is_active_etf(_t):
            _err_trace.append('yuanta: 3 URL 全 fail')

    # S-H3 v18.244:全部失敗 — 寫 module-level dict 給診斷面板讀(原 st.session_state)
    _ETF_MANAGER_LAST_ERR[_t] = ' | '.join(_err_trace) if _err_trace else 'unknown'
    return None


import os as _os_mg
import json as _json_mg

_MGR_HISTORY_PATH = _os_mg.path.join('/tmp/st_cache', 'etf_manager_history.json')
# 持久檔：由 update_etf_managers.py（GitHub Actions 每週）維護並 commit 進 repo，
# 跨 Streamlit Cloud 容器重啟仍存活（解決 /tmp 清空導致紅框不跳的問題）。
_ETF_MANAGERS_REPO_PATH = _os_mg.path.join(
    _os_mg.path.dirname(_os_mg.path.abspath(__file__)), 'etf_managers.json')
_RECENT_CHANGE_DAYS = 180   # 換手偵測日後多久內仍在 UI 亮紅框


def track_etf_manager_change(ticker: str, manager: dict | None) -> dict:
    """比對 ETF 經理人異動（ETF 表現與經理人相關，換手須提醒）。

    換手基準與歷史的主來源 = `etf_managers.json`（Actions 維護、commit 進 repo，
    跨容器重啟存活）；`/tmp` 為次要（兩次 Actions 之間 app 自行即時偵測 + 雲端
    唯讀時的備援）。回傳 UI 用字典:
      {'changed': bool, 'prev': str|None, 'detected_at': 'YYYY-MM-DD'|None,
       'is_new': bool, 'tenure_days': int|None}
    changed：持久檔近 180 天有換手紀錄，或 live 名字與基準不同。
    is_new：到職日推算任期 < 180 天（半年內新任,表現待觀察）。
    """
    import datetime as _dt_mg
    _name = (manager or {}).get('name') or None
    _tenure = (manager or {}).get('tenure_days')
    _is_new = isinstance(_tenure, int) and _tenure < 180
    _out = {'changed': False, 'prev': None, 'detected_at': None,
            'is_new': _is_new, 'tenure_days': _tenure}
    if not _name:
        return _out
    _key = (ticker or '').replace('.tw', '.TW').strip()
    _today_d = _dt_mg.date.today()
    _today = _today_d.isoformat()

    # ── 1. 持久檔（repo）：跨容器存活的換手基準 + 歷史 ──────────────
    _repo_rec = {}
    try:
        if _os_mg.path.exists(_ETF_MANAGERS_REPO_PATH):
            with open(_ETF_MANAGERS_REPO_PATH, 'r', encoding='utf-8') as _f:
                _repo_db = _json_mg.load(_f) or {}
            _repo_rec = (_repo_db.get('managers') or {}).get(_key) or {}
    except Exception as _e_repo:
        print(f'[ETF Manager] 讀持久檔略過: {_e_repo}')

    # 1a. 持久 history 近 180 天的換手 → 即使容器重啟仍亮紅框
    for _h in reversed(_repo_rec.get('history') or []):
        _da = _h.get('detected_at')
        try:
            _dd = _dt_mg.date.fromisoformat(_da) if _da else None
        except ValueError:
            _dd = None
        if _dd and (_today_d - _dd).days <= _RECENT_CHANGE_DAYS:
            _out.update({'changed': True, 'prev': _h.get('from'), 'detected_at': _da})
            break

    # 1c. 任期 fallback：live tenure_days 缺 → 用持久檔 first_seen 推算近似值
    #     （MoneyDJ 不揭露到職日的 ETF 適用；標 'approx' 讓 UI 知道是估算）
    if _out['tenure_days'] is None and _repo_rec.get('first_seen'):
        try:
            _fs = _dt_mg.date.fromisoformat(_repo_rec['first_seen'])
            _approx_days = (_today_d - _fs).days
            if _approx_days >= 0:
                _out['tenure_days'] = _approx_days
                _out['tenure_approx'] = True   # UI 提示「至少 X 天」而非確切
                # 重新評估 is_new（用近似 tenure）
                _out['is_new'] = _approx_days < 180
        except ValueError:
            pass

    # 1b. live 名字 vs 持久基準不同 → 兩次 Actions 之間也能即時偵測
    _repo_name = _repo_rec.get('name')
    if not _out['changed'] and _repo_name and _repo_name != _name:
        _out.update({'changed': True, 'prev': _repo_name, 'detected_at': _today})

    # ── 2. /tmp 即時檔（次要：session 內 + 持久檔不可寫時備援）──────
    try:
        _os_mg.makedirs('/tmp/st_cache', exist_ok=True)
        _db = {}
        if _os_mg.path.exists(_MGR_HISTORY_PATH):
            with open(_MGR_HISTORY_PATH, 'r', encoding='utf-8') as _f:
                _db = _json_mg.load(_f) or {}
        _rec = _db.get(_key) or {}
        _prev = _rec.get('name')
        if _prev and _prev != _name and not _out['changed']:
            _out.update({'changed': True, 'prev': _prev, 'detected_at': _today})
            _hist = _rec.get('history') or []
            _hist.append({'from': _prev, 'to': _name, 'detected_at': _today,
                          'since': (manager or {}).get('since')})
            _rec['history'] = _hist[-10:]
            # 換手 → first_seen 重設為今天（新任期起點）
            _rec['first_seen'] = _today
        _rec.update({'name': _name, 'since': (manager or {}).get('since'),
                     'last_seen': _today})
        # 首次紀錄此 ticker 時設 first_seen：優先用持久檔的值，避免容器重啟後
        # tenure 歸零導致全部顯示「新任」；只有持久檔也沒有時才設為今天。
        _rec.setdefault('first_seen', _repo_rec.get('first_seen') or _today)
        _rec.setdefault('history', _rec.get('history', []))
        _db[_key] = _rec

        # 若持久檔沒 first_seen 但 /tmp 有 → 補回 out 推算 tenure
        if _out['tenure_days'] is None and _rec.get('first_seen'):
            try:
                _fs2 = _dt_mg.date.fromisoformat(_rec['first_seen'])
                _ad2 = (_today_d - _fs2).days
                if _ad2 >= 0:
                    _out['tenure_days'] = _ad2
                    _out['tenure_approx'] = True
                    _out['is_new'] = _ad2 < 180
            except ValueError:
                pass
        with open(_MGR_HISTORY_PATH, 'w', encoding='utf-8') as _f:
            _json_mg.dump(_db, _f, ensure_ascii=False, indent=2)
    except Exception as _e_mg:
        print(f'[ETF Manager] 異動追蹤略過（無法存檔）: {_e_mg}')
    return _out


@st.cache_data(ttl=TTL_7DAY, show_spinner=False)
def _fetch_sitca_manager(ticker: str):
    """SITCA fallback：投信投顧公會基金經理人查詢。

    跟 fetch_sitca_expense_ratio 同 proxy 路徑（已驗證可走）；pd.read_html 後動態
    掃描所有表格找「代號／基金代碼」+「經理人／基金經理人」雙欄。

    Returns
    -------
    dict | None  {'name': ..., 'since': None, 'tenure_days': None}（任期 SITCA 通常不揭露）
    """
    from src.data.proxy import fetch_url as _fu_sm
    import pandas as _pd_sm
    from shared.etf_codes import bare_etf_code as _bare
    _t = _bare(ticker)
    if not _t or not _t.isdigit():
        return None
    _tn = _t.lstrip('0') or '0'

    _urls = [
        'https://www.sitca.org.tw/ROC/Industry/IN2401.aspx?pid=IN2401_01',
        'https://www.sitca.org.tw/ROC/Industry/IN2421.aspx?pid=IN2421_01',
        'https://www.sitca.org.tw/ROC/Industry/IN2422.aspx?pid=IN2422_01',
        'https://www.sitca.org.tw/ROC/Industry/IN2411.aspx?pid=IN2411_01',
    ]
    for _url in _urls:
        try:
            r = _fu_sm(_url, timeout=15, attempts=2)
            if r is None or r.status_code != 200 or len(r.text or '') < 500:
                continue
            r.encoding = 'utf-8'
            try:
                tables = _pd_sm.read_html(r.text)
            except ValueError:
                continue
            for tbl in tables:
                code_col = next((c for c in tbl.columns
                                 if any(k in str(c) for k in
                                        ('代號', '代碼', '基金統編', '統一編號', 'Code'))), None)
                mgr_col = next((c for c in tbl.columns
                                if any(k in str(c) for k in
                                       ('經理人', '基金經理', '現任經理'))), None)
                if code_col is None or mgr_col is None:
                    continue
                _digits = tbl[code_col].astype(str).str.replace(r'\D', '', regex=True)
                row = tbl[_digits.where(_digits != '', '0').str.lstrip('0').replace('', '0') == _tn]
                if row.empty:
                    continue
                _raw = str(row[mgr_col].iloc[0]).strip()
                if not _raw or _raw.lower() == 'nan' or _raw.isdigit():
                    continue
                # 多人共同經理用「、」「,」分隔；可能附括號註記，取首位淨化
                _name = _raw.split('、')[0].split(',')[0].split('(')[0].split('（')[0].strip()
                if 2 <= len(_name) <= 8:
                    print(f'[SITCA/manager] ✅ {_t} = {_name} (url={_url[-30:]})')
                    _prov_log('_fetch_sitca_manager', f'SITCA:{_url[-30:]}',
                              _t, f'dict:name={_name}')
                    return {'name': _name, 'since': None, 'tenure_days': None}
        except Exception as e:
            print(f'[SITCA/manager] {_t} {_url[-30:]}: {type(e).__name__}: {e}')
            continue
    _prov_log('_fetch_sitca_manager', 'SITCA:4-urls-all-fail', _t, 'None:no-match')
    return None


def get_etf_expense_ratio_safe(ticker: str):
    """安全讀取 ETF 費用率：MoneyDJ Basic0004 → SITCA → Yuanta → yfinance 四段備援。

    順序變更（v2）：MoneyDJ 改為 primary（走 NAS 中繼站穩定，繞 SITCA/yfinance
    在 Streamlit Cloud 海外 IP 被封鎖時的單點失敗）。缺失回 None。
    """
    # Primary：MoneyDJ Basic0004 一次取 metadata（含 expense），與 fetch_etf_info 共用 cache
    _meta = fetch_etf_meta_moneydj(ticker)
    if _meta and _meta.get('expense') is not None:
        return _meta['expense']
    _sit = fetch_sitca_expense_ratio(ticker)
    if _sit is not None:
        return _sit
    _mdj = fetch_moneydj_expense_ratio(ticker)
    if _mdj is not None:
        return _mdj
    # v1.1：主動式 ETF 專屬，SITCA + MDJ 都失敗時補位
    if is_active_etf(ticker):
        _yu = _fetch_yuanta_active_etf_meta(ticker)
        if _yu and _yu.get('expense') is not None:
            return _yu['expense']
    try:
        info = fetch_etf_info(ticker)
        return (info.get('annualReportExpenseRatio')
                or info.get('totalExpenseRatio')
                or info.get('expenseRatio'))
    except Exception:
        return None


# ── NAV 合理範圍常數（用於 fetch_etf_nav_history 多源 sanity check）──
_NAV_MIN, _NAV_MAX = 0.5, 100000


def _safe_float(s, strip_chars: str = ',%') -> float | None:
    """安全 float 解析：失敗回 None。

    Replaces inline `try: float(...) except: pass` pattern；避免 bare except
    吞掉 KeyboardInterrupt / SystemExit。
    """
    try:
        _t = str(s).strip()
        for _c in strip_chars:
            _t = _t.replace(_c, '')
        return float(_t) if _t else None
    except (ValueError, TypeError):
        return None


def _fetch_all_etf_json(session, proxies, verify, timeout):
    """對 MIS all_etf.txt 做「暖身 + 正式請求」兩段式抓取，回傳 parsed JSON 或 None。

    v18.448:TWSE MIS 是舊式 Java/Tomcat 系統(`.jsp` 端點遍布),瀏覽器 DevTools 實測
    確認請求會帶 `JSESSIONID` cookie —— 這類系統常見設計是資料端點需要「先訪問過前台頁面
    建立 session」才會正常回應，裸 GET data 端點（無 cookie）容易被拒。故本函式先 GET
    揭露頁面（讓 session cookie 寫入同一個 `requests.Session()`），再用同一個 session
    取 `all_etf.txt`（沿用 cookie）。任何一步非 200 即視為失敗，回 None 讓呼叫端記錄原因。
    """
    _disclosure_url = ('https://mis.twse.com.tw/stock/various-areas/etf-price/'
                        'indicator-disclosure-etf?lang=zhHant')
    _data_url = 'https://mis.twse.com.tw/stock/data/all_etf.txt'
    _hdr = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'),
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    }
    _r_warmup = session.get(_disclosure_url, headers=_hdr, proxies=proxies,
                            verify=verify, timeout=timeout)
    if _r_warmup.status_code != 200:
        print(f'[ETF 折溢價/MIS] 暖身請求 HTTP {_r_warmup.status_code}'
              f'(揭露頁面本身連不上,建立 session 失敗)')
        return None, _r_warmup.status_code
    _r = session.get(_data_url,
                     headers={**_hdr, 'Referer': _disclosure_url,
                              'Accept': 'application/json, text/plain, */*'},
                     proxies=proxies, verify=verify, timeout=timeout)
    if _r.status_code != 200:
        print(f'[ETF 折溢價/MIS] all_etf.txt HTTP {_r.status_code}'
              f'(暖身 OK 但正式資料端點被拒,可能仍需其他驗證)')
        return None, _r.status_code
    return _r.json(), 200


@st.cache_data(ttl=TTL_15MIN, max_entries=100, show_spinner=False)
def fetch_etf_official_premium(ticker: str, ver: int = 6) -> dict | None:
    """抓 TWSE 官方「全體投信 ETF 即時預估淨值揭露」聚合 feed(繞 geo-block)。

    v18.446:改用 **經瀏覽器 DevTools Network 面板實測確認**的正確端點
    `https://mis.twse.com.tw/stock/data/all_etf.txt` —— 對應官方頁面「ETF發行單位變動及
    預估淨值揭露專區」(`mis.twse.com.tw/stock/various-areas/etf-price/
    indicator-disclosure-etf`)背後打的 API,每 15 秒輪詢一次。

    v18.443/444/445 均猜錯 endpoint(`openapi.twse.com.tw/v1/ETF/TaiwanStock*` 是
    FinMind dataset 名非 TWSE 真實路徑;`etf_nav.jsp` 是舊站改版前的猜測,新站已無此
    路徑),兩者從未真的抓到值,一路 fallback 到 yfinance 過時 navPrice → 假折溢價。

    v18.448:v18.446 上線後 endpoint 正確,但仍未抓到值。改用**自建 session 兩段式請求**
    (`_fetch_all_etf_json`):先 GET 揭露頁面(暖身,讓 MIS 這套舊式 Java/Tomcat 系統
    寫入 `JSESSIONID`——瀏覽器 DevTools 實測請求確實帶此 cookie,裸 GET data 端點無 cookie
    易被拒),再用同一 session 取 `all_etf.txt`。同時修正 `fetch_url(attempts=1)` 的既有
    bug:該函式的降級直連只在「連續 2 次 403」才觸發,`attempts=1` 時 1 次 403 就直接放棄,
    永遠不會嘗試直連 —— 改自建 session 後不再依賴 `fetch_url`,直接做「Squid 代理 → 直連」
    兩層 fallback。

    v18.450 hotfix:production log 證實 v18.448 連線已成功(HTTP 200 + json() 正常),
    但解析卡在「回應非預期陣列結構」——**回應頂層其實不是裸陣列,是 `{"a1": [...]}`**
    (一個物件,鍵名剛好叫 "a1")。先前對照瀏覽器 DevTools JSON 樹狀展開畫面時,誤把
    這個 "a1" 當成 devtools 內部的陣列索引標示,實際上它就是回應本體的 key。已改為
    dict/list 兩種頂層皆相容解析。

    回應結構:**頂層是物件,鍵 `a1` 對應陣列**(24 個「投信公司」區塊,各自帶
    `msgArray`——該投信旗下所有 ETF)。欄位(依實測):
      a=代號  b=簡稱  c=已發行受益權單位數  d=與前日差異數
      **e=成交價(市價)**  **f=投信預估淨值(iNAV)**  **g=折溢價率(%) = (e-f)/f×100**
      h=前一營業日單位淨值  i=日期(YYYYMMDD)  j=時間(HH:MM:SS)  k=flag

    需跨全部投信區塊找目標代號(0050 位於元大投信區塊)。僅台股 ETF(代號首碼數字)。
    **完全未設代理 → 回 None**(不空試 + 測試不觸網),呼叫端(`etf_calc.calc_premium_discount`)
    自動 fallback 既有 5 段 NAV 鏈。§8.2:L1 Data。

    Returns
    -------
    dict {'nav'(=投信預估淨值),'price'(=成交價),'premium_pct','source'[,'data_date']}
    或 None
    """
    from shared.etf_codes import bare_etf_code as _bare
    code = _bare(ticker)
    # 僅台股 ETF(海外 ETF 走 yfinance;TWSE 無資料)
    if not code or not code[:1].isdigit():
        return None
    from src.data.proxy.proxy_helper import get_proxy_config
    _proxy_cfg = get_proxy_config()
    if _proxy_cfg is None:
        print(f'[ETF 折溢價/MIS] {code}: 未設 PROXY_URL/NAS_PROXY_URL,'
              '略過 → 走既有 NAV 鏈')
        return None
    import requests as _requests
    _blocks = None
    # Squid 代理(家用台灣 IP)優先;失敗才降級直連(Streamlit Cloud 美國 IP 大概率仍被擋,
    # 但保留此路徑對齊 fetch_url 既有「代理→直連」慣例,不平白少一次機會)。
    for _label, _proxies, _verify in (('Squid代理', _proxy_cfg, False),
                                       ('直連', {}, True)):
        try:
            _sess = _requests.Session()
            _blocks, _status = _fetch_all_etf_json(_sess, _proxies, _verify, timeout=15)
            if _blocks is not None:
                print(f'[ETF 折溢價/MIS] {code}: 經{_label}成功取得 all_etf.txt')
                break
            print(f'[ETF 折溢價/MIS] {code}: 經{_label}失敗(HTTP {_status}),嘗試下一步')
        except Exception as _e_conn:
            print(f'[ETF 折溢價/MIS] {code}: 經{_label}例外 '
                  f'{type(_e_conn).__name__}: {_e_conn}')
    if _blocks is None:
        print(f'[ETF 折溢價/MIS] {code}: 代理+直連皆失敗,走既有 NAV 鏈')
        return None
    try:
        # v18.450 hotfix:production log 證實連線成功(HTTP 200 + json() 正常解析),
        # 但真實回應**不是**裸陣列 —— 是 `{"a1": [...24 個投信區塊...]}`,外層多包一層
        # 物件、鍵名剛好叫 "a1"(先前對照瀏覽器 DevTools JSON 樹狀展開時，把這個當成
        # devtools 的內部陣列索引標示，誤判成裸陣列 —— 實際上它就是回應本體的 key)。
        # 相容處理:list 直接用;dict 則優先取 "a1"，找不到就退而在所有 value 裡找第一個
        # list-of-dict(防止 key 名稱未來改變)。
        if isinstance(_blocks, dict):
            _candidate = _blocks.get('a1')
            if not isinstance(_candidate, list):
                _candidate = next((v for v in _blocks.values() if isinstance(v, list)), None)
            _blocks = _candidate
        if not isinstance(_blocks, list):
            print(f'[ETF 折溢價/MIS] {code}: all_etf.txt 回應非預期結構(非 list 也非'
                  f' {{"a1": [...]}})')
            return None
        _row = None
        for _blk in _blocks:
            if not isinstance(_blk, dict):
                continue
            for _m in (_blk.get('msgArray') or []):
                if str(_m.get('a', '')).strip() == code:
                    _row = _m
                    break
            if _row is not None:
                break
        if _row is None:
            print(f'[ETF 折溢價/MIS] {code}: 全 24 家投信區塊皆無此代號')
            return None
        _price = _safe_float(_row.get('e'))  # 成交價(市價)
        _nav = _safe_float(_row.get('f'))    # 投信/總代理人預估淨值(iNAV)
        _prem = _safe_float(_row.get('g'))   # 折溢價率(%)
        # g 缺 → 由 (成交價-淨值)/淨值 反推(fail loud 保底)
        if _prem is None and _nav and _price and _nav > 0:
            _prem = round((_price - _nav) / _nav * 100, 2)
        _date = str(_row.get('i', '')).strip()  # YYYYMMDD
        _time = str(_row.get('j', '')).strip()
        if _nav and _nav > 0 and _prem is not None:
            _dd = (f'{_date[:4]}/{_date[4:6]}/{_date[6:]}'
                   if len(_date) == 8 and _date.isdigit() else (_date or None))
            print(f'[ETF 折溢價/MIS] ✅ {code}: 淨值={_nav} 成交價={_price} '
                  f'折溢價={_prem}% ({_dd} {_time})')
            _prov_log('fetch_etf_official_premium', 'TWSE-MIS:all_etf',
                      code, f'prem={_prem}%')
            _out = {'nav': _nav, 'price': _price, 'premium_pct': _prem,
                    'source': 'TWSE-MIS:all_etf'}
            if _dd:
                _out['data_date'] = _dd
            return _out
    except Exception as _e:
        print(f'[ETF 折溢價/MIS] {code}: {type(_e).__name__}: {_e}')
    print(f'[ETF 折溢價/MIS] {code}: MIS all_etf 未回傳可用值'
          '(非交易時段可能無即時值)')
    return None


@st.cache_data(ttl=TTL_2HOUR, show_spinner=False, max_entries=10)
def fetch_etf_nav_history(ticker: str, days: int = 35, ver: int = 5) -> "pd.DataFrame":
    """ETF 歷史淨值及折溢價（最近 N 個交易日）

    資料來源優先順序（5 段備援 + 1 兜底）：
      1. FinMind TaiwanETFNetAssetValue（批次，有/無 token 皆可）
      2. goodinfo.tw StockDetail（不受 TWSE IP 封鎖）
      3. TWSE OpenAPI（僅 NAS Proxy 環境）
      4. MoneyDJ BeautifulSoup
      5. yfinance navPrice
      *. 兜底：FinMind 過舊資料（前述 5 段全失敗時）

    Args
    ----
    ticker : str  ETF 代號（含 .TW 後綴）
    days   : int  目標回溯交易日（含緩衝 +10 日）
    ver    : int  cache key bumper — 升版觸發 @st.cache_data 失效；不入函式邏輯。

    Returns
    -------
    pd.DataFrame  欄位：date / price / nav / premium / premium_pct
    """
    import os
    import datetime as _dt
    from shared.etf_codes import bare_etf_code as _bare
    code = _bare(ticker)
    # st.secrets 優先（Streamlit Cloud secrets 不自動匯出至 os.environ）
    token = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN')
             or os.environ.get('FINMIND_TOKEN', ''))
    start = (_dt.date.today() - _dt.timedelta(days=days + 10)).strftime('%Y-%m-%d')
    _df_stale = None       # 備援：FinMind 過舊資料
    _days_stale: int | None = None
    # S-PROV-1 phase 10 v18.256 — provenance helper(schema-additive,既有 caller 無感)
    _fetched_at_iso = pd.Timestamp.now('UTC').isoformat()

    def _attach_prov(_d, _src):
        """為返回 DataFrame 補 source / fetched_at 兩欄(若已存在則不覆蓋)。"""
        try:
            if _d is None or _d.empty:
                return _d
            if 'source' not in _d.columns:
                _d = _d.assign(source=_src)
            if 'fetched_at' not in _d.columns:
                _d = _d.assign(fetched_at=_fetched_at_iso)
            return _d
        except Exception:  # noqa: BLE001
            return _d

    # 即時報價類來源（goodinfo/TWSE/MoneyDJ/yfinance）回的是「最後一筆已公告淨值」，
    # 但若硬戳 today，遇週末/假日會與 yfinance 收盤日（上一交易日）對不上而 inner-join 落空。
    # 故統一戳「最近交易日」：今天是工作日用今天，否則往前推到最後一個工作日。
    def _last_business_day(_d):
        while _d.weekday() >= 5:   # 5=Sat, 6=Sun
            _d -= _dt.timedelta(days=1)
        return _d
    _last_bd = _last_business_day(_dt.date.today())

    # ── 1. FinMind ETF NAV（試兩個 dataset 名稱 + 多種欄位名稱）───────────
    from src.data.proxy import fetch_url as _fu_etfnav  # NAS 中繼 fallback
    for _ds1 in ['TaiwanETFNetAssetValue', 'TaiwanStockETFNAV']:
        try:
            _p = {'dataset': _ds1, 'data_id': code, 'start_date': start}
            if token: _p['token'] = token
            _r = _fu_etfnav(FINMIND_API_URL, params=_p,
                            timeout=15, attempts=2)  # v19.105: attempts=1 使 2×403 直連降級永不觸發(同 v18.455)
            if _r is None:
                print(f'[ETF NAV] FinMind {_ds1} {code}: fetch_url 回 None（含 NAS 中繼皆失敗）')
                continue
            _j = _r.json()
            _jstatus = _j.get('status')
            _jdata   = _j.get('data')
            # 接受 status=200 / status=None（部分 proxy 環境）；排除已知錯誤碼
            # v19.83(第六份 review Bug 3):排除清單補 '429'(FinMind 限流)— 原漏列,
            # 429 回應若帶非空 data 會被誤收進快取
            _status_ok = str(_jstatus) not in ('400', '401', '402', '403', '404', '429', '500')
            if _jdata and _status_ok:
                _df = pd.DataFrame(_jdata)
                # 自動偵測 NAV 欄位名稱（FinMind 兩個版本欄位名不同）
                _nav_field = next((f for f in ['nav', 'base_unit_net_value', 'NavPrice', 'netAssetValue']
                                   if f in _df.columns), None)
                if _nav_field is None:
                    print(f'[ETF NAV] {code} {_ds1}: 找不到 NAV 欄位，現有={list(_df.columns)}')
                    continue
                _df['date'] = pd.to_datetime(_df['date']).dt.date
                _df['nav']  = pd.to_numeric(_df[_nav_field], errors='coerce')
                _df = _df[_df['nav'].notna() & (_df['nav'] > 0)].sort_values('date')
                if _df.empty:
                    print(f'[ETF NAV] {code} {_ds1}: 所有 nav 欄位為空/NaN，跳過')
                    continue
                _latest_d   = _df['date'].iloc[-1]
                _days_stale = (_dt.date.today() - _latest_d).days
                _df_stale   = _df[['date', 'nav']]   # 保留，供 path 4 備援
                print(f'[ETF NAV] {code} {_ds1}(field={_nav_field}): {len(_df)} 筆, 最新={_latest_d}, 距今={_days_stale}d')
                if _days_stale <= 14:          # 14天內視為可用（含連假/公告延遲）
                    return _attach_prov(_df_stale, f'FinMind:{_ds1}')
                print(f'[ETF NAV] {_ds1} {code} 資料較舊({_days_stale}d)，嘗試其他來源')
                break   # 找到資料就不再嘗試第二個 dataset
            else:
                _msg = str(_j.get('msg', ''))[:80]
                print(f'[ETF NAV] FinMind {_ds1} {code}: status={_jstatus} data_len={len(_jdata) if _jdata else 0} msg={_msg}')
        except Exception as _e1:
            print(f'[ETF NAV] FinMind {_ds1} {code}: {_e1}')

    # ── 2. goodinfo.tw — 不受 TWSE IP 封鎖，抓取 ETF 淨值 ───────────────────
    try:
        from bs4 import BeautifulSoup as _BS4_gi
        import re as _re_gi
        _url_gi = f'https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={code}'
        # 走 fetch_url（自動 NAS Squid → 直連 → NAS 中繼站 fallback）
        _r_gi = _fu_etfnav(_url_gi, headers={'Referer': 'https://goodinfo.tw/tw/'},
                           timeout=12, attempts=2)
        if _r_gi is not None and _r_gi.status_code == 200:
            _soup_gi = _BS4_gi(_r_gi.text, 'lxml')
            _nav_gi, _prem_gi = None, None
            # 策略1：在 <td> 中找「淨值」標籤，取下一格數字
            for _td_gi in _soup_gi.find_all('td'):
                _txt_gi = _td_gi.get_text(strip=True)
                if _txt_gi in ('淨值', '每單位淨值', 'NAV'):
                    _sib_gi = _td_gi.find_next_sibling('td')
                    if _sib_gi:
                        _v = _safe_float(_sib_gi.get_text(strip=True))
                        if _v is not None and _NAV_MIN < _v < _NAV_MAX:
                            _nav_gi = _v
                    if _nav_gi:
                        break
            # 策略2：regex 掃全文
            if not _nav_gi:
                _m_gi = _re_gi.search(r'淨值[^\d<]{0,30}?(\d{1,5}\.\d{2,6})', _r_gi.text)
                if _m_gi:
                    _v = _safe_float(_m_gi.group(1))
                    if _v is not None and _NAV_MIN < _v < _NAV_MAX:
                        _nav_gi = _v
            # 嘗試抓折溢價率
            if _nav_gi:
                for _td_gi2 in _soup_gi.find_all('td'):
                    if '折溢價' in _td_gi2.get_text(strip=True):
                        _sib_gi2 = _td_gi2.find_next_sibling('td')
                        if _sib_gi2:
                            _m_p = _re_gi.search(r'([+-]?\d+\.?\d*)', _sib_gi2.get_text(strip=True))
                            if _m_p:
                                _prem_gi = _safe_float(_m_p.group(1))
                        if _prem_gi is not None:
                            break
                _row_gi = {'date': _last_bd, 'nav': _nav_gi}
                if _prem_gi is not None: _row_gi['premium_pct'] = _prem_gi
                print(f'[ETF NAV] {code} goodinfo: nav={_nav_gi} prem={_prem_gi}%')
                return _attach_prov(pd.DataFrame([_row_gi]), 'Goodinfo:StockDetail')
            else:
                print(f'[ETF NAV] {code} goodinfo: 找不到淨值欄位')
        else:
            print(f'[ETF NAV] {code} goodinfo: HTTP {_r_gi.status_code}')
    except Exception as _e_gi:
        print(f'[ETF NAV] goodinfo {code}: {_e_gi}')

    # ── 3. TWSE OpenAPI（走 fetch_url，含 NAS Squid + NAS 中繼站 fallback）─
    def _parse_twse_row(row_dict, ep_label):
        _nav2 = 0.0
        for _nk in ['單位淨值', '淨值', 'NetAssetValue', 'nav']:
            _v = _safe_float(row_dict.get(_nk, ''))
            if _v is not None:
                _nav2 = _v
                break
        _price2 = 0.0
        for _pk in ['收盤價', 'ClosingPrice', 'close']:
            _v = _safe_float(row_dict.get(_pk, ''))
            if _v is not None:
                _price2 = _v
                break
        _prem_key = next((k for k in row_dict if '折溢價' in str(k)), None)
        _prem2 = _safe_float(row_dict[_prem_key]) if _prem_key else None
        if _prem2 is None and _nav2 > 0 and _price2 > 0:
            _prem2 = round((_price2 - _nav2) / _nav2 * 100, 2)
        if _nav2 > 0:
            _r_out = {'date': _last_bd, 'nav': _nav2}
            if _price2 > 0:
                _r_out['price'] = _price2
            if _prem2 is not None:
                _r_out['premium_pct'] = _prem2
            print(f'[ETF NAV] {code} TWSE({ep_label}): nav={_nav2} price={_price2} prem={_prem2}%')
            return _r_out
        return None

    for _op_id2 in ['TaiwanStockPremiumDiscountRatio', 'TaiwanStockNetValue']:
        try:
            _ep2 = f'https://openapi.twse.com.tw/v1/ETF/{_op_id2}'
            _r2 = _fu_etfnav(_ep2, headers={'Accept': 'application/json'},
                             timeout=10, attempts=2)  # v19.105: 同上,允許 403 降級
            if _r2 is None:
                print(f'[ETF NAV] TWSE {_op_id2}: fetch_url 回 None'); continue
            _j2 = _r2.json()
            _df2 = pd.DataFrame(_j2 if isinstance(_j2, list) else [])
            if _df2.empty:
                print(f'[ETF NAV] TWSE {_op_id2}: 回傳空資料'); continue
            _code_col = next((c for c in _df2.columns if '證券代號' in str(c) or c == 'code'), None)
            if _code_col is None:
                print(f'[ETF NAV] TWSE {_op_id2}: 找不到 證券代號 欄位'); continue
            _match = _df2[_df2[_code_col].astype(str).str.strip() == code]
            if _match.empty:
                print(f'[ETF NAV] TWSE {_op_id2}: 找不到 {code}'); continue
            _out2 = _parse_twse_row(_match.iloc[0].to_dict(), _op_id2)
            if _out2:
                return _attach_prov(pd.DataFrame([_out2]), f'TWSE:OpenAPI:ETF:{_op_id2}')
        except Exception as _e2:
            print(f'[ETF NAV] TWSE {_op_id2} {code}: {_e2}')

    # ── 4. MoneyDJ Basic0003 淨值表格（每日 NAV 歷史）─────────────────────
    # 修正：原使用 Basic0004（基本資料頁，無 NAV 歷史）+ etfid 缺 .TW 後綴
    # Basic0003 是專門的淨值表格，主動式 ETF（00982A.TW）也支援
    try:
        import re as _re_mdj
        # etfid 需 .TW 後綴；主動式 ETF 'A' 保留（如 00982A.TW）
        _etfid_mdj = ticker.upper() if ticker.upper().endswith(('.TW', '.TWO')) else f'{code}.TW'

        # 4a. Basic0001 即時報價頁 — 直接含「淨值/市價/折溢價(%)」官方值，
        #     不必用 yfinance Close 反推（杜絕跨來源日期錯位）。KV 解析較 regex 穩。
        _url_q = f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_etfid_mdj}'
        _r_q = _fu_etfnav(_url_q, headers={'Referer': 'https://www.moneydj.com/'},
                          timeout=12, attempts=2)
        if _r_q is not None and _r_q.status_code == 200:
            _r_q.encoding = 'utf-8'
            _kv_q = _html_kv_pairs(_r_q.text)

            def _kv_num_q(_keys, _excl=()):
                for _k, _v in _kv_q.items():
                    if any(_kk in _k for _kk in _keys) and not any(_xx in _k for _xx in _excl):
                        _m = _re_mdj.search(r'[-+]?\d+\.?\d*', _v.replace(',', ''))
                        if _m:
                            return _safe_float(_m.group(0))
                return None

            _nav_q   = _kv_num_q(['淨值'])
            _price_q = _kv_num_q(['市價', '成交價'], _excl=['漲跌'])
            _prem_q  = _kv_num_q(['折溢價'])
            if _nav_q is not None and _NAV_MIN < _nav_q < _NAV_MAX:
                _row_q = {'date': _last_bd, 'nav': _nav_q}
                if _price_q is not None and _price_q > 0:
                    _row_q['price'] = _price_q
                if _prem_q is None and _price_q and _nav_q:
                    _prem_q = round((_price_q - _nav_q) / _nav_q * 100, 2)
                if _prem_q is not None:
                    _row_q['premium_pct'] = _prem_q
                print(f'[ETF NAV] MoneyDJ-Q(Basic0001) {_etfid_mdj}: '
                      f'nav={_nav_q} price={_price_q} prem={_prem_q}%')
                return _attach_prov(pd.DataFrame([_row_q]), 'MoneyDJ:Basic0001')
            print(f'[ETF NAV] MoneyDJ-Q {_etfid_mdj}: 200 但 KV 無淨值 '
                  f'(keys={list(_kv_q)[:8]})')
        else:
            _cq = _r_q.status_code if _r_q is not None else 'None'
            print(f'[ETF NAV] MoneyDJ-Q {_etfid_mdj}: HTTP {_cq}')

        # 4b. Basic0003 淨值表格 — 補 NAV 歷史（4a 拿不到時的備援）
        _url_mdj = f'https://www.moneydj.com/ETF/X/Basic/Basic0003.xdjhtm?etfid={_etfid_mdj}'
        _r_mdj = _fu_etfnav(_url_mdj, headers={'Referer': 'https://www.moneydj.com/'},
                            timeout=12, attempts=2)
        if _r_mdj is not None and _r_mdj.status_code == 200:
            _r_mdj.encoding = 'utf-8'
            # v18.451 hotfix:原 regex 假設「日期後 40 字內接著數字」，但 user 提供實測
            # HTML 證實這是**正規 <table>**(CSS class 分欄,如 <td class="col08">)，
            # 日期/淨值中間隔了市價/折溢價等其他 <td>(遠超過 40 字)→ regex 從未真的
            # 抓到過(production log「200 但 regex 無 date+nav pair」),一路 fallback 到
            # yfinance 過時 navPrice,導致「近期淨值及折溢價」表格顯示錯位假折溢價。
            #
            # 改用 BeautifulSoup 逐 <tr> 解析,不依賴 class 名稱(user 提供的實測 HTML
            # 顯示市價與折溢價欄位「共用」class="col09",class 名稱不可靠,故只依「同一列
            # 恰有 4 個 <td>、第一格是日期格式」定位,以此為錨點)：
            #   td[0]=日期 td[1]=淨值 td[2]=市價 td[3]=折溢價%(負值包 <span class="negative">,
            #   get_text() 會自動取出內層文字,不受影響)。
            # 同一列的 nav/price/premium_pct 同源同日,無跨欄位錯位風險 —— 比原本「NAV 走
            # MoneyDJ、市價走 yfinance 再事後 inner-join」更根本,直接消除這整類 bug。
            _records_mdj: list[dict] = []
            try:
                from bs4 import BeautifulSoup as _BS4_mdj
                _soup_mdj = _BS4_mdj(_r_mdj.text, 'lxml')
                _date_re_mdj = _re_mdj.compile(r'^\d{4}[/\-]\d{1,2}[/\-]\d{1,2}$')
                for _tr_mdj in _soup_mdj.find_all('tr'):
                    _tds_mdj = _tr_mdj.find_all('td')
                    if len(_tds_mdj) != 4:
                        continue
                    _txt0_mdj = _tds_mdj[0].get_text(strip=True)
                    if not _date_re_mdj.match(_txt0_mdj):
                        continue
                    _nav_v_mdj = _safe_float(_tds_mdj[1].get_text(strip=True))
                    if _nav_v_mdj is None or not (_NAV_MIN < _nav_v_mdj < _NAV_MAX):
                        continue
                    try:
                        _y_m, _m_m, _d_m = (int(x) for x in _txt0_mdj.replace('-', '/').split('/'))
                        _date_v_mdj = _dt.date(_y_m, _m_m, _d_m)
                    except (ValueError, IndexError):
                        continue
                    _rec_mdj = {'date': _date_v_mdj, 'nav': _nav_v_mdj}
                    _price_v_mdj = _safe_float(_tds_mdj[2].get_text(strip=True))
                    if _price_v_mdj is not None and _price_v_mdj > 0:
                        _rec_mdj['price'] = _price_v_mdj
                    _prem_v_mdj = _safe_float(_tds_mdj[3].get_text(strip=True))
                    if _prem_v_mdj is not None:
                        _rec_mdj['premium_pct'] = _prem_v_mdj
                    _records_mdj.append(_rec_mdj)
            except Exception as _e_bs_mdj:
                print(f'[ETF NAV] MoneyDJ {_etfid_mdj} BS4 解析例外: '
                      f'{type(_e_bs_mdj).__name__}: {_e_bs_mdj}')
            if _records_mdj:
                _records_mdj.sort(key=lambda r: r['date'])  # 升冪(對齊其他來源慣例)
                _df_mdj = pd.DataFrame(_records_mdj)
                _last_rec_mdj = _records_mdj[-1]
                print(f'[ETF NAV] MoneyDJ {_etfid_mdj}: {len(_df_mdj)} 筆(最新 '
                      f'{_last_rec_mdj["date"]} nav={_last_rec_mdj["nav"]} '
                      f'price={_last_rec_mdj.get("price")} '
                      f'prem={_last_rec_mdj.get("premium_pct")}%)')
                return _attach_prov(_df_mdj, 'MoneyDJ:Basic0003')
            print(f'[ETF NAV] MoneyDJ {_etfid_mdj}: 200 但表格解析無有效列(頁面結構可能已變)')
        else:
            _code_st = _r_mdj.status_code if _r_mdj is not None else 'None'
            print(f'[ETF NAV] MoneyDJ {_etfid_mdj}: HTTP {_code_st}')
    except Exception as _e_mdj:
        print(f'[ETF NAV] MoneyDJ {code}: {type(_e_mdj).__name__}: {_e_mdj}')

    # ── 5. yfinance ETF info.navPrice（加限速 retry）──────────────────────
    import time as _t3
    for _sfx3 in ('.TW', '.TWO'):
        for _retry3 in range(3):
            try:
                import yfinance as _yf3
                _tk3 = _yf3.Ticker(f'{code}{_sfx3}')
                _info3 = _tk3.info
                _nav3 = _info3.get('navPrice') or _info3.get('regularMarketNAV')
                if _nav3 and float(_nav3) > 0:
                    print(f'[ETF NAV] yfinance {code}{_sfx3}: navPrice={_nav3}')
                    return _attach_prov(pd.DataFrame([{'date': _last_bd, 'nav': float(_nav3)}]),
                                        f'Yahoo:navPrice:{code}{_sfx3}')
                break  # 沒資料，不 retry
            except Exception as _e3:
                _e3s = str(_e3)
                if ('Too Many Requests' in _e3s or 'Rate' in _e3s) and _retry3 < 2:
                    _t3.sleep(2 + _retry3 * 2)  # 2s, 4s
                    print(f'[ETF NAV] yfinance {code}{_sfx3}: 限速 retry {_retry3+1}/3')
                    continue
                print(f'[ETF NAV] yfinance {code}{_sfx3}: {_e3}')
                break

    # ── 最終兜底：FinMind 過舊資料（goodinfo/MoneyDJ/yfinance 全部失敗時）────
    if _df_stale is not None and not _df_stale.empty:
        print(f'[ETF NAV] {code} 最終兜底: FinMind過舊資料({_days_stale}d)，所有即時來源失敗')
        return _attach_prov(_df_stale, 'FinMind:fallback_stale')

    return pd.DataFrame()


@st.cache_data(ttl=TTL_30MIN, max_entries=10)
def _fetch_sector_returns(tickers: tuple, period: str) -> dict:
    """批次抓取類股漲跌幅，回傳 {ticker: pct_change}"""
    result = {}
    try:
        raw = yf.download(list(tickers), period=period,
                          auto_adjust=True, progress=False, threads=True)
        if raw.empty:
            return result
        # yf.download 多 ticker 時 Close 為 MultiIndex
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw['Close'] if 'Close' in raw.columns.get_level_values(0) else raw.xs('Close', axis=1, level=0)
        else:
            close = raw[['Close']] if 'Close' in raw.columns else raw
        close = close.ffill().dropna(how='all')
        for t in tickers:
            if t in close.columns:
                series = close[t].dropna()
                if len(series) >= 2:
                    pct = round((float(series.iloc[-1]) / float(series.iloc[0]) - 1) * 100, 2)
                    result[t] = pct
    except Exception as e:
        # S-H3 v18.244:L1 不可 st.warning → 改 print log
        print(f'[etf_fetch/sector] ⚠️ 類股資料抓取部分失敗:{type(e).__name__}: {e}')
    # S-PROV-1 P0 v18.434:批次 yf.download 結果 prov_log(§2.2)
    _prov_log('_fetch_sector_returns', f'yfinance:batch:period={period}',
              f'{len(tickers)}tickers', f'dict:{len(result)}items')
    return result


def _fetch_etf_zh_name_finmind(ticker: str) -> str | None:
    """v18.455:FinMind TaiwanStockInfo.stock_name 取 ETF 中文商品名（結構化，最可靠）。

    stock_id 不帶 .TW/.TWO 後綴;stock_name 即官方中文名(0050→元大台灣50)。
    同 dataset 的 industry_category 早已在 fetch_industry_category 穩定運作。
    失敗/非中文/查無 → None(呼叫端 fallback MoneyDJ)。
    """
    import os as _os_fn
    import re as _re_fn
    import requests as _rq_fn
    _bare = _re_fn.sub(r'\.(TW|TWO)$', '', (ticker or '').replace('.tw', '.TW').strip())
    if not _bare:
        return None
    # token 選填(FinMind 無 token 亦可 rate-limited 查詢);讀 secrets 失敗不可中斷
    _tok = _os_fn.environ.get('FINMIND_TOKEN', '')
    if not _tok:
        try:
            _tok = getattr(st, 'secrets', {}).get('FINMIND_TOKEN', '') or ''
        except Exception:
            _tok = ''
    try:
        _p = {'dataset': 'TaiwanStockInfo', 'data_id': _bare}
        if _tok:
            _p['token'] = _tok
        # S8 v19.78 UA 補漏(v19.82):token 維持走 params,headers 僅補 UA
        from src.data.core.data_loader import _fm_raw_headers as _fm_hdrs_fn
        _r = _rq_fn.get(FINMIND_API_URL, params=_p, headers=_fm_hdrs_fn(''), timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        for _row in _data:
            _nm = str(_row.get('stock_name', '') or '').strip()
            # 只取真中文名(含 CJK,非純數字/英數,2-30 字)
            if (2 <= len(_nm) <= 30 and not _nm.isdigit()
                    and any('一' <= _c <= '鿿' for _c in _nm)):
                return _nm
    except Exception as _e:
        print(f'[FinMind/zhname] {_bare}: {type(_e).__name__}: {_e}')
    return None


@st.cache_data(ttl=TTL_7DAY, max_entries=500, show_spinner=False)
def fetch_etf_zh_name(ticker: str):
    """取 ETF 中文名稱（yfinance 對台股 ETF 只有英文 longName/發行商名）。

    v18.455 來源優先序:
      1. FinMind TaiwanStockInfo.stock_name（官方結構化，最可靠）— PRIMARY
      2. MoneyDJ Basic 系列 <title> regex（MoneyDJ 疑改版格式，原為唯一來源
         但連 0050 都 FAIL，降為 fallback）

    MoneyDJ <title> 格式（fallback 用）:「{中文名}-{代號}.TW-ETF{頁面類型} - MoneyDJ理財網」

    Returns
    -------
    str | None  中文名（2-30 字）；全敗回 None（呼叫端應 fallback 至 yfinance）
    """
    import re as _re_zh
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    if '.' not in _t:
        _t = f'{_t}.TW'

    # ── PRIMARY:FinMind TaiwanStockInfo.stock_name(結構化中文名) ──
    _fm_name = _fetch_etf_zh_name_finmind(_t)
    if _fm_name:
        print(f'[FinMind/zhname] OK {_t} = {_fm_name}')
        _prov_log('fetch_etf_zh_name', 'FinMind:TaiwanStockInfo:stock_name',
                  _t, f'str:{_fm_name}')
        return _fm_name

    # ── fallback:MoneyDJ Basic0003（淨值表格）通常最快、最穩；再 fallback 0004/0001 ──
    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0003.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_t}',
    ]
    for _url in _urls:
        try:
            from src.data.proxy import fetch_url as _fu_zh
            _r = _fu_zh(_url, headers={'Referer': 'https://www.moneydj.com/'},
                        timeout=12, attempts=2)  # v18.455: attempts=1 bug fix — 403 需連續2次才觸發直連降級
            if _r is None or _r.status_code != 200:
                continue
            _r.encoding = 'utf-8'
            # Title pattern：「{中文名}-{代號}.TW-...」首段 capture
            _m = _re_zh.search(
                r'<title>\s*([^<\-]{2,30}?)\s*-\s*[0-9]{4,5}[A-Z]?\.TW\s*-',
                _r.text)
            if _m:
                _name = _m.group(1).strip()
                # 排除：純數字、純英數（yfinance 也會回的英文名）
                if (2 <= len(_name) <= 30 and not _name.isdigit()
                        and any('一' <= _c <= '鿿' for _c in _name)):
                    print(f'[MDJ/zhname] OK {_t} = {_name}')
                    _prov_log('fetch_etf_zh_name', f'MoneyDJ:{_url[-30:]}',
                              _t, f'str:{_name}')
                    return _name
        except Exception as _e:
            print(f'[MDJ/zhname] {_t} {_url[-30:]}: {type(_e).__name__}: {_e}')
    print(f'[zhname] FAIL {_t}（FinMind + MoneyDJ 皆無中文名）')
    _prov_log('fetch_etf_zh_name', 'FinMind+MoneyDJ:all-fail', _t, 'None:no-match')
    return None


@st.cache_data(ttl=TTL_7DAY, max_entries=200, show_spinner=False)
def fetch_etf_underlying_index(ticker: str):
    """從 MoneyDJ 抓 ETF 追蹤指數名稱（yfinance 沒有此欄）。

    抓取策略：複用 fetch_etf_manager 的 proxy 通路（NAS Squid 主源 + curl_cffi fallback）。
    優先順序：Basic0001（基本資料，最常見）→ Basic0006（基金概觀）→ Basic0007（持股明細，部分有）。

    Regex 三層寬鬆策略：
      1. 表頭 + 表格儲存格：>追蹤指數</…><td…>內容</td>
      2. 冒號形式：追蹤指數：內容 / 標的指數：內容
      3. 同義詞兜底：對應/標的/追蹤 指數 後接中英文/數字 4-80 字

    Returns
    -------
    str | None
        指數名稱（如 '臺灣加權股價報酬指數' / 'MSCI Taiwan ESG Index'），找不到回 None。
    """
    import re as _re_ui
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    if '.' not in _t:
        _t = f'{_t}.TW'

    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0006.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0007.xdjhtm?etfid={_t}',
    ]
    _err_trace: list[str] = []

    for _url in _urls:
        _txt = None
        _endpoint = _url.split('/')[-1].split('?')[0]
        try:
            from src.data.proxy import fetch_url as _fu_ui
            _r = _fu_ui(_url, timeout=12, attempts=2)
            if _r is not None and _r.status_code == 200 and len(_r.text or '') > 500:
                _r.encoding = 'utf-8'
                _txt = _r.text
            else:
                _code = _r.status_code if _r is not None else 'None'
                _err_trace.append(f'proxy {_endpoint}: HTTP {_code}')
        except Exception as _epu:
            _err_trace.append(f'proxy {_endpoint}: {type(_epu).__name__}')

        if _txt is None:
            try:
                from curl_cffi import requests as _cffi_ui
                _r2 = _cffi_ui.get(_url, impersonate='chrome124', timeout=12)
                if _r2.status_code == 200 and len(_r2.text or '') > 500:
                    _txt = _r2.text
                else:
                    _err_trace.append(f'cffi {_endpoint}: HTTP {_r2.status_code}')
            except Exception as _ecu:
                _err_trace.append(f'cffi {_endpoint}: {type(_ecu).__name__}')

        if _txt is None:
            continue

        # HTML entity 預清洗 — 避免 lazy regex 卡在 &nbsp;
        _txt = (_txt.replace('&nbsp;', ' ').replace('&#160;', ' ')
                    .replace('&amp;', '&').replace('　', ' '))

        # 排除「追蹤誤差」「指數型基金」等假陽性詞
        _idx = None
        try:
            # 1. 表頭 + 儲存格（最常見的 MoneyDJ 排版）
            _m = _re_ui.search(
                r'(?:追蹤|標的|對應)\s*指數\s*</[^>]+>\s*<[^>]+>\s*'
                r'([一-鿿A-Za-z0-9 &\.\-／/（）()]{4,80})\s*<',
                _txt,
            )
            if not _m:
                # 2. 冒號形式
                _m = _re_ui.search(
                    r'(?:追蹤|標的|對應)\s*指數\s*[：:]\s*'
                    r'([一-鿿A-Za-z0-9 &\.\-／/（）()]{4,80})',
                    _txt,
                )
            if not _m:
                # 3. 寬鬆兜底（含 HTML/whitespace 雜訊）
                _m = _re_ui.search(
                    r'(?:追蹤|標的|對應)\s*指數[^一-鿿A-Za-z\d]{0,40}?'
                    r'([一-鿿A-Za-z0-9 &\.\-／/（）()]{4,80})',
                    _txt,
                )
            if _m:
                _cand = _m.group(1)
                # HTML entity / 全形空白清洗 → 排除假陽性與長度不足
                _cand = (_cand.replace('&nbsp;', ' ').replace('　', ' ')
                              .replace('&amp;', '&').strip().rstrip('，,。.、 '))
                _bad = ('追蹤誤差', '指數股票型', '指數型基金', '基金經理',
                        '管理費', 'nbsp', 'amp;')
                if len(_cand) >= 4 and not any(_b in _cand for _b in _bad):
                    _idx = _cand
        except Exception as _ex:
            _err_trace.append(f'{_endpoint}: regex {type(_ex).__name__}')

        if _idx:
            print(f'[MDJ/index] OK {_t} = {_idx} via {_endpoint}')
            _prov_log('fetch_etf_underlying_index', f'MoneyDJ:{_endpoint}',
                      _t, f'str:{_idx}')
            return _idx
        _err_trace.append(f'{_endpoint}: 200 但 regex 無指數')

    # S-H3 v18.244:寫 module-level dict 給診斷面板讀(原 st.session_state)
    _ETF_INDEX_LAST_ERR[_t] = ' | '.join(_err_trace) if _err_trace else 'unknown'
    print(f'[MDJ/index] FAIL {_t} — {_err_trace[-1] if _err_trace else "no trace"}')
    _prov_log('fetch_etf_underlying_index', 'MoneyDJ:3-urls-all-fail',
              _t, 'None:no-match')
    return None


# ═══════════════════════════════════════════════════════════════════════
# v18.358 PR-R1 §8.2 A7:從 etf_calc.compute_etf_peer_ranking 抽出 yfinance I/O。
# L1 Data 層負責批次抓 close prices(可多 ticker 一次抓);L2 Compute(etf_calc)
# 負責 pure compute(percentile / median / period 切片)。caller (compute_etf_peer_ranking)
# 介面 0 改。
# ═══════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=TTL_1HOUR, max_entries=50, show_spinner=False)
def fetch_etf_peer_history(tickers: tuple, period: str = '2y') -> pd.DataFrame:
    """批次抓多檔 ETF 收盤價歷史(L1 Data,純 I/O)。

    Parameters
    ----------
    tickers : tuple[str, ...]
        ETF ticker 列表(self + peers),tuple 以利 @st.cache_data hash。
    period : str
        yfinance period 字串(預設 '2y')。

    Returns
    -------
    pd.DataFrame
        columns=tickers,index=date,values=Close。
        抓不到或全空回空 DataFrame(caller 用 .empty 判)。
    """
    _all = list(tickers)
    try:
        _hist = yf.download(_all, period=period, auto_adjust=True,
                            progress=False, threads=False)
        # yf.download 多 ticker 回 MultiIndex (column 0=field, 1=ticker);單一回扁平
        if isinstance(_hist.columns, pd.MultiIndex):
            _close = _hist['Close']
        else:
            _close = _hist[['Close']].rename(columns={'Close': _all[0]})
        if _close is None or _close.empty:
            _prov_log('fetch_etf_peer_history',
                      f'yfinance:batch:period={period}',
                      f'{_all[0]}+{len(_all)-1}peers', 'empty')
            return pd.DataFrame()
        _prov_log('fetch_etf_peer_history',
                  f'yfinance:batch:period={period}',
                  f'{_all[0]}+{len(_all)-1}peers', f'df:{_close.shape}')
        return _close
    except Exception as _e:
        import traceback as _tb_pr
        print(f'[fetch_etf_peer_history] {_all[0]} ❌ {type(_e).__name__}: {_e}')
        _tb_pr.print_exc()
        _prov_log('fetch_etf_peer_history',
                  f'yfinance:batch:period={period}',
                  f'{_all[0]}+{len(_all)-1}peers',
                  f'None:exc:{type(_e).__name__}')
        return pd.DataFrame()
