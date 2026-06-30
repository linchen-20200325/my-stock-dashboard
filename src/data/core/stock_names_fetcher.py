"""src/data/core/stock_names_fetcher.py — TWSE/TPEx OpenAPI 動態股名快取(L1 Data)。

P0-1 v18.371 深層拔毒:從 src/config/stock_names.py(L0)抽出 I/O 邏輯。
L0 config 不該動態 HTTP fetch(雖原有 EX-L0-1 例外但限 st.secrets,不該擴及外部 API)。

職責:
- TWSE openapi STOCK_DAY_AVG_ALL / t187ap03_L 上市股名 fetch
- TPEx openapi tpex_mainboard_daily_close_quotes 上櫃股名 fetch
- pickle disk cache(24hr TTL)
- yfinance fast_info 個股 fallback

caller(thin shim in stock_names.py):
- `_ensure_cache()`:回傳當前 cache dict(stale 自動 refresh)
- `_build_dynamic_name_cache()`:強制重抓
- `lookup_via_yfinance(stock_id)`:單檔 yfinance fallback
"""
from __future__ import annotations

import os
import pickle
import datetime
import requests


_CACHE_DIR = '/tmp/st_cache'
os.makedirs(_CACHE_DIR, exist_ok=True)

_DYNAMIC_CACHE_PATH = os.path.join(_CACHE_DIR, 'tw_stock_names_v1.pkl')
_DYNAMIC_CACHE_TTL = 24  # 小時


def _load_dynamic_cache() -> dict:
    """從磁碟讀取動態名稱快取(無論是否過期皆載入)"""
    if os.path.exists(_DYNAMIC_CACHE_PATH):
        try:
            with open(_DYNAMIC_CACHE_PATH, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    return {}


def _is_cache_stale() -> bool:
    """回傳 True 若快取檔不存在或已超過 TTL。"""
    if not os.path.exists(_DYNAMIC_CACHE_PATH):
        return True
    age_h = (datetime.datetime.now().timestamp()
             - os.path.getmtime(_DYNAMIC_CACHE_PATH)) / 3600
    return age_h >= _DYNAMIC_CACHE_TTL


def _save_dynamic_cache(name_dict: dict) -> None:
    try:
        with open(_DYNAMIC_CACHE_PATH, 'wb') as f:
            pickle.dump(name_dict, f)
    except Exception:
        pass


def _build_dynamic_name_cache(static_fallback: dict | None = None) -> dict:
    """從 TWSE + TPEx 免費 OpenAPI 抓取全市場股票名稱。回傳 {股票代碼: 中文名稱} dict。

    static_fallback:可選,合併進結果(不覆蓋動態抓到的)— 由 caller 傳 _STATIC_NAMES dict。
    """
    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    result: dict = {}
    try:
        from src.data.proxy import fetch_url as _furl_sn  # 強制走 NAS proxy
    except ImportError:
        _furl_sn = None

    # 1. TWSE 上市(含ETF)
    _twse_urls = [
        'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL',
        'https://openapi.twse.com.tw/v1/opendata/t187ap03_L',
    ]
    for _url in _twse_urls:
        try:
            r = _furl_sn(_url, headers=HDR, timeout=12) if _furl_sn else requests.get(_url, headers=HDR, timeout=12)
            if r is not None and r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    for item in data:
                        code = str(item.get('Code', item.get('公司代號', ''))).strip()
                        name = str(item.get('Name', item.get('公司簡稱', ''))).strip()
                        if code and name and code not in result:
                            result[code] = name
                    print(f'[股名快取] TWSE {_url.split("/")[-1]}: {len(result)} 筆')
                    if len(result) > 100:
                        break
        except Exception as e:
            print(f'[股名快取] TWSE 抓取失敗: {e}')

    # 2. TPEx 上櫃
    try:
        _tpex_url = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'
        r2 = _furl_sn(_tpex_url, headers=HDR, timeout=12) if _furl_sn else requests.get(_tpex_url, headers=HDR, timeout=12)
        if r2 is not None and r2.status_code == 200:
            data2 = r2.json()
            if isinstance(data2, list):
                before = len(result)
                for item in data2:
                    code = str(item.get('SecuritiesCompanyCode', '')).strip()
                    name = str(item.get('CompanyName', '')).strip()
                    if code and name and code not in result:
                        result[code] = name
                print(f'[股名快取] TPEx: +{len(result)-before} 筆')
    except Exception as e:
        print(f'[股名快取] TPEx 抓取失敗: {e}')

    # 3. 合併靜態備援(不覆蓋動態結果)
    if static_fallback:
        for k, v in static_fallback.items():
            if k not in result:
                result[k] = v

    return result


# module-level cache(thin shim in L0 stock_names.py 透過 import 共享)
_dynamic_cache: dict = _load_dynamic_cache()


def _replace_dynamic_cache(new_cache: dict) -> None:
    """v18.435 WONTFIX-翻案 Bug #4:in-place 更新 _dynamic_cache,不 rebind 全域名。

    原作 `_dynamic_cache = new_cache` rebind 全域,會與 lookup_via_yfinance 內
    `_dynamic_cache[stock_id] = _n` 競爭 — 若刷新與 lookup 併發,lookup 的 setitem
    可能落在已被棄置的舊 dict 上(reference 已被新 rebind 取代)→ 寫入永久遺失。

    改 .clear() + .update():全域變數始終指向同一 dict 物件,所有 setitem 一致命中。
    CPython 下 dict.clear()/update() 各自於單一 C-level 操作完成(GIL 保護),不需鎖。
    """
    _dynamic_cache.clear()
    _dynamic_cache.update(new_cache)


def _ensure_cache(static_fallback: dict | None = None) -> dict:
    """確保動態快取存在;若空白或過期則嘗試重新抓取。
    只有在新快取筆數多於舊快取時才取代,避免 API 失敗時以少量靜態資料覆蓋大快取。"""
    if not _dynamic_cache or _is_cache_stale():
        new_cache = _build_dynamic_name_cache(static_fallback=static_fallback)
        if len(new_cache) > len(_dynamic_cache):
            _replace_dynamic_cache(new_cache)
            _save_dynamic_cache(_dynamic_cache)
    return _dynamic_cache


def refresh_name_cache(static_fallback: dict | None = None) -> int:
    """強制重新抓取並更新快取。回傳新快取大小。"""
    new_cache = _build_dynamic_name_cache(static_fallback=static_fallback)
    _replace_dynamic_cache(new_cache)
    _save_dynamic_cache(_dynamic_cache)
    return len(_dynamic_cache)


def lookup_via_yfinance(stock_id: str) -> str | None:
    """yfinance fast_info 個股 fallback(慢,只在 cache + static 都缺時用)。"""
    try:
        import yfinance as yf
        for suffix in ['.TW', '.TWO']:
            _info = yf.Ticker(f'{stock_id}{suffix}').fast_info
            _n = getattr(_info, 'company_name', None)
            if _n and _n not in (f'{stock_id}{suffix}', stock_id, ''):
                # 同時寫回 cache 供下次使用(in-place setitem,不 rebind)
                _dynamic_cache[stock_id] = _n
                return _n
    except Exception:
        pass
    return None
