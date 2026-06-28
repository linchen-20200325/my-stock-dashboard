"""
tw_macro.py — 台灣金融資料抓取核心 v1.0

設計目標
========
1. 把 stock-dashboard 與 fund-dashboard 中所有「台灣資料源」的抓取邏輯
   集中到此模組,避免雙邊重複。資料源涵蓋:
   - TWSE OpenAPI(漲跌家數)
   - FinMind 免費 API(三大法人籌碼)
   - 中央銀行 ms1.json / SDMX EF15M01(M1B / M2)
2. **所有抓取統一透過 proxy_helper.fetch_url(),確保走家用 NAS 中繼站**,
   解決雲端境外 IP 被擋(TWSE 對境外 IP 有限制)、被限流的問題。

範圍邊界
========
✅ 收錄:台灣資料抓取(TWSE / FinMind / CBC)
✅ 收錄:Tier 3 ^TWII 動能代理(透過 macro_core.fetch_yf_close,亦走 NAS proxy)
❌ 不收錄:全球指標(放在 macro_core.py)
❌ 不收錄:下游決策(放在各 repo 自己的引擎)

依賴限制
========
- 不依賴 streamlit
- 不依賴 yfinance(統一打 REST API,經 NAS 中繼)
"""
from __future__ import annotations

import datetime as _dt
import functools as _ft
import re as _re
import time as _time
from typing import Optional

import pandas as pd

from src.data.proxy import fetch_url

__version__ = "1.1.0"


# ── v1.1 輕量 TTL cache（純 stdlib，不依賴 streamlit）──────────
# 雙 repo 共用設計約束：本模組嚴禁 import streamlit，故自帶 cache decorator。
def _ttl_cache(ttl_sec: int, maxsize: int = 32):
    """TTL+LRU cache。cache key=(args, sorted kwargs)；unhashable 引數 bypass。"""
    def decorator(fn):
        _cache: dict = {}

        @_ft.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                key = (args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
                return fn(*args, **kwargs)
            now = _time.time()
            hit = _cache.get(key)
            if hit and (now - hit[0]) < ttl_sec:
                return hit[1]
            result = fn(*args, **kwargs)
            _cache[key] = (now, result)
            if len(_cache) > maxsize:
                oldest = min(_cache.items(), key=lambda kv: kv[1][0])[0]
                _cache.pop(oldest, None)
            return result

        wrapper.cache_clear = lambda: _cache.clear()  # type: ignore[attr-defined]
        return wrapper

    return decorator

# ── 各端點 URL ────────────────────────────────────────────
TWSE_MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
FINMIND_BASE      = "https://api.finmindtrade.com/api/v4/data"
CBC_MS1_URLS      = [
    # v18.240 SSOT — CBC ms1.json 端點清單；tw_macro._try_cbc_ms1 與
    # update_macro_history.fetch_finmind_m1m2 共用，與 fetch_cbc_ms1_rows
    # kernel 形成完整 SSOT。新增端點 = 此清單 append 一個 URL 即可。
    # 註：歷史 /public/Attachment/ms1.json 路徑於 v18.231 確認 404，
    # 已移除（fetch_cbc_ms1_rows None-guard 已可覆蓋未來新增 dead URL）。
    "https://www.cbc.gov.tw/public/data/ms1.json",
    "https://www.cbc.gov.tw/tw/public/data/ms1.json",
]
CBC_EF15M01_URL   = "https://cpx.cbc.gov.tw/API/DataAPI/Get"


# ══════════════════════════════════════════════════════════════
# TWSE 市場寬度
# ══════════════════════════════════════════════════════════════

@_ttl_cache(ttl_sec=600, maxsize=4)
def fetch_twse_breadth() -> dict:
    """
    從 TWSE MI_INDEX 抓上漲/下跌家數,計算市場寬度。

    Returns
    -------
    dict
        {
            'adv':        int | None,    上漲家數
            'dec':        int | None,    下跌家數
            'breadth':    float | None,  (adv-dec)/(adv+dec) × 100
            'z_breadth':  float | None,  max(-3, min(3, breadth/20))
            'date':       str,
            'error':      str | None,
            'source':     str,           血緣標識 (S-PROV-1 v18.249)
            'fetched_at': str,           UTC ISO (S-PROV-1 v18.249)
        }
    """
    # S-PROV-1 v18.249 phase 5:provenance schema(§2.2)
    _now_iso = pd.Timestamp.now('UTC').isoformat()
    result = {'adv': None, 'dec': None, 'breadth': None,
              'z_breadth': None, 'date': '', 'error': None,
              'source': 'TWSE:MI_INDEX:MS', 'fetched_at': _now_iso}

    r = fetch_url(TWSE_MI_INDEX_URL,
                  params={'response': 'json', 'type': 'MS'}, timeout=12)
    if r is None:
        result['error'] = "TWSE 抓取失敗(NAS proxy + 直連都失敗)"
        return result
    try:
        d = r.json()
    except Exception as e:
        result['error'] = f"TWSE JSON 解析失敗: {e}"
        return result

    result['date'] = d.get('date', '')
    for tbl in (d.get('tables') or []):
        if not isinstance(tbl, dict):
            continue
        rows = tbl.get('data', [])
        if not any('上漲' in str(row) for row in rows):
            continue
        adv = dec = 0
        for row in rows:
            row_s = str(row[0]) if row else ""
            mkt_s = str(row[1]) if len(row) > 1 else ""
            nums  = _re.findall(r"[\d,]+", mkt_s)
            val   = int(nums[0].replace(",", "")) if nums else 0
            if "上漲" in row_s:
                adv = val
            elif "下跌" in row_s:
                dec = val
        if adv + dec > 0:
            result['adv']        = adv
            result['dec']        = dec
            result['breadth']    = round((adv - dec) / (adv + dec) * 100, 2)
            result['z_breadth']  = max(-3.0, min(3.0, result['breadth'] / 20.0))
        break
    return result


# ══════════════════════════════════════════════════════════════
# FinMind 三大法人籌碼
# ══════════════════════════════════════════════════════════════

@_ttl_cache(ttl_sec=600, maxsize=8)
def fetch_finmind_foreign_investor(days_back: int = 7) -> dict:
    """
    從 FinMind 抓最近 N 天的外資買賣超(免費 API,無需 token)。

    Parameters
    ----------
    days_back : int
        回看天數,預設 7 天。

    Returns
    -------
    dict
        {
            'fii_net':    int | None,    外資淨買超(元)
            'z_fii':      float | None,  max(-3, min(3, fii_net / 5e9))
            'date':       str,
            'error':      str | None,
            'source':     str,           血緣標識 (S-PROV-1 v18.248 新增)
            'fetched_at': str,           本次抓取 UTC ISO (S-PROV-1 v18.248 新增)
        }
    """
    # S-PROV-1 v18.248 phase 4:provenance schema(§2.2)— 全路徑(含 error)皆攜帶
    _now_iso = pd.Timestamp.now('UTC').isoformat()
    _src = 'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor'
    result = {'fii_net': None, 'z_fii': None, 'date': '', 'error': None,
              'source': _src, 'fetched_at': _now_iso}

    today    = _dt.date.today()
    end_dt   = today.strftime("%Y-%m-%d")
    start_dt = (today - _dt.timedelta(days=days_back)).strftime("%Y-%m-%d")

    r = fetch_url(FINMIND_BASE, params={
        'dataset':    'TaiwanStockTotalInstitutionalInvestors',
        'start_date': start_dt,
        'end_date':   end_dt,
    }, timeout=12)
    if r is None:
        result['error'] = "FinMind 抓取失敗"
        return result
    try:
        rows = r.json().get('data', [])
    except Exception as e:
        result['error'] = f"FinMind JSON 解析失敗: {e}"
        return result

    fi_rows = [r for r in rows if r.get('name') == 'Foreign_Investor']
    if not fi_rows:
        result['error'] = "FinMind 無 Foreign_Investor 資料"
        return result

    fi_rows.sort(key=lambda x: x.get('date', ''), reverse=True)
    latest = fi_rows[0]
    fii_net = int(latest.get('buy', 0)) - int(latest.get('sell', 0))
    result['fii_net'] = fii_net
    result['z_fii']   = max(-3.0, min(3.0, fii_net / 5_000_000_000))
    result['date']    = latest.get('date', '')
    return result


# ══════════════════════════════════════════════════════════════
# 中央銀行 M1B / M2(三層備援)
# ══════════════════════════════════════════════════════════════

def fetch_cbc_ms1_rows(url: str, *, min_rows: int = 1,
                       log_label: Optional[str] = None,
                       **fetch_kwargs) -> Optional[list]:
    """v18.238 SSOT — CBC ms1.json 端點抓取 + JSON list-shape 驗證共用 kernel.

    Consumers:
      - tw_macro._try_cbc_ms1（即時三層備援 Tier 1）
      - update_macro_history.fetch_finmind_m1m2（歷史 bootstrap ms1 分支）

    `**fetch_kwargs` 透傳 fetch_url（timeout / attempts 等），caller 控制 IO 參數。
    `log_label` 給時印詳細 debug log（update_macro_history 模式），否則 silent（tw_macro 模式）。
    """
    r = fetch_url(url, **fetch_kwargs)
    if r is None:
        if log_label:
            print(f"[{log_label}] {url[-40:]} → None")
        return None
    try:
        data = r.json()
    except Exception:
        if log_label:
            body = getattr(r, 'text', '')[:200]
            print(f"[{log_label}] {url[-40:]} JSON 解析失敗 body={body}")
        return None
    if not isinstance(data, list) or len(data) < min_rows:
        if log_label:
            print(f"[{log_label}] {url[-40:]} json 非 list 或不足 {min_rows} 行")
        return None
    if log_label:
        print(f"[{log_label}] ✅ {url[-40:]} 取到 {len(data)} 行")
    # v18.354 PR-Q4 S-PROV-1 phase 19:stderr audit trail(不破 caller list return)
    try:
        import sys as _sys_prov_cbc
        _now_cbc = pd.Timestamp.now('UTC').isoformat()
        print(f'[fetch_cbc_ms1_rows] source=CBC:ms1.json:{url[-40:]} '
              f'fetched_at={_now_cbc} result=list:{len(data)}rows',
              file=_sys_prov_cbc.stderr)
    except Exception:
        pass
    return data


def _try_cbc_ms1(url: str) -> Optional[tuple]:
    """嘗試抓 CBC ms1.json,回傳 (m1b_yoy, m2_yoy) 或 None。"""
    data = fetch_cbc_ms1_rows(url, min_rows=13, timeout=12)
    if data is None:
        return None
    df = pd.DataFrame(data)
    c1 = next((c for c in df.columns
               if 'M1B' in str(c).upper() or '貨幣供給額M1B' in str(c)), None)
    c2 = next((c for c in df.columns
               if str(c).strip().upper() == 'M2' or '貨幣供給額M2' in str(c)), None)
    if not (c1 and c2):
        return None
    s1 = pd.to_numeric(df[c1], errors='coerce').dropna()
    s2 = pd.to_numeric(df[c2], errors='coerce').dropna()
    if len(s1) < 13 or len(s2) < 13:
        return None
    return (
        round((s1.iloc[-1] / s1.iloc[-13] - 1) * 100, 2),
        round((s2.iloc[-1] / s2.iloc[-13] - 1) * 100, 2),
    )


def _try_cbc_ef15m01() -> Optional[tuple]:
    """嘗試抓 CBC SDMX EF15M01,回傳 (m1b_yoy, m2_yoy) 或 None。"""
    r = fetch_url(CBC_EF15M01_URL, params={'FileName': 'EF15M01'}, timeout=15)
    if r is None:
        return None
    try:
        data = r.json()
    except Exception:
        return None
    rows = data.get('DataSet', [])
    if not rows:
        return None
    dims = (data.get('Structure') or {}).get('Dimensions', [])
    cmap: dict = {}
    for dim in (dims if isinstance(dims, list) else []):
        if isinstance(dim, dict):
            cmap[str(dim.get('id', ''))] = str(dim.get('name', ''))
    if not cmap:
        cmap = {k: k for k in (rows[0] if isinstance(rows[0], dict) else {})}
    ck1 = next((k for k, v in cmap.items() if 'M1B' in v.upper()), None)
    ck2 = next((k for k, v in cmap.items()
                if v.strip().upper() in ('M2', 'M2 ')), None)
    if not ck1:
        ck1 = next((k for k in (rows[0] if isinstance(rows[0], dict) else {})
                    if 'M1B' in k.upper()), None)
    if not ck2:
        ck2 = next((k for k in (rows[0] if isinstance(rows[0], dict) else {})
                    if k.strip().upper() == 'M2'), None)
    if not (ck1 and ck2) or len(rows) < 13:
        return None
    sv1, sv2 = [], []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            sv1.append(float(str(row.get(ck1, '')).replace(',', '')))
            sv2.append(float(str(row.get(ck2, '')).replace(',', '')))
        except Exception:
            pass
    if len(sv1) < 13 or len(sv2) < 13:
        return None
    return (
        round((sv1[-1] / sv1[-13] - 1) * 100, 2),
        round((sv2[-1] / sv2[-13] - 1) * 100, 2),
    )


def _try_twii_proxy() -> Optional[tuple]:
    """Tier 3:^TWII 動能代理(走 macro_core 經 NAS proxy)。"""
    try:
        from src.data.macro import fetch_yf_close
    except ImportError:
        return None
    twii = fetch_yf_close("^TWII", range_="6mo")
    if len(twii) < 60:
        return None
    chg20 = round((twii.iloc[-1] / twii.iloc[-20] - 1) * 100, 2)
    chg60 = round((twii.iloc[-1] / twii.iloc[-60] - 1) * 100, 2)
    return (chg20, round(chg60 / 3, 2))


@_ttl_cache(ttl_sec=600, maxsize=4)
def fetch_cbc_m1b_m2() -> dict:
    """
    抓中央銀行 M1B / M2 月資料 YoY 變動率。三層備援:

    - Tier 1: CBC public/data/ms1.json(官方公開 JSON)
    - Tier 2: cpx.cbc.gov.tw SDMX EF15M01
    - Tier 3: ^TWII 動能代理(走 macro_core 經 NAS proxy)

    Returns
    -------
    dict
        {
            'm1b_yoy':        float | None,
            'm2_yoy':         float | None,
            'gap':            float | None,    m1b_yoy - m2_yoy
            'tier_used':      1 | 2 | 3 | None,
            'is_proxy_tier':  bool,            tier 3 才為 True
            'error':          str | None,
            'source':         str,             血緣標識,依 tier 動態 (v18.249)
            'fetched_at':     str,             UTC ISO (v18.249)
        }
    """
    # S-PROV-1 v18.249 phase 5:provenance schema(§2.2)
    _now_iso = pd.Timestamp.now('UTC').isoformat()
    result = {
        'm1b_yoy': None, 'm2_yoy': None, 'gap': None,
        'tier_used': None, 'is_proxy_tier': False, 'error': None,
        'source': 'CBC:M1B_M2:unknown', 'fetched_at': _now_iso,
    }

    # ── Tier 1 ──
    for url in CBC_MS1_URLS:
        out = _try_cbc_ms1(url)
        if out is not None:
            result['m1b_yoy'], result['m2_yoy'] = out
            result['gap']        = round(out[0] - out[1], 2)
            result['tier_used']  = 1
            result['source']     = 'CBC:ms1.json:tier1'
            return result

    # ── Tier 2 ──
    out = _try_cbc_ef15m01()
    if out is not None:
        result['m1b_yoy'], result['m2_yoy'] = out
        result['gap']       = round(out[0] - out[1], 2)
        result['tier_used'] = 2
        result['source']    = 'CBC:EF15M01:tier2'
        return result

    # ── Tier 3 ──
    out = _try_twii_proxy()
    if out is not None:
        result['m1b_yoy'], result['m2_yoy'] = out
        result['gap']            = round(out[0] - out[1], 2)
        result['tier_used']      = 3
        result['is_proxy_tier']  = True
        result['source']         = 'Yahoo:^TWII:proxy_tier3'
        return result

    result['error'] = "三層備援全部失敗"
    return result


# ══════════════════════════════════════════════════════════════
# v1.1 拐點偵測資料源（景氣對策信號 / 領先指標 / 外資連續日數）
# ══════════════════════════════════════════════════════════════

# FinMind TaiwanMacroEconomics 指標名（中央銀行/國發會公開資料）
# v18.177：FinMind v4 已把此 dataset 改 Sponsor 付費 tier，
# tw_macro 改走 data.gov.tw NDC OpenData（dgtw）為 PRIMARY，FinMind 為 FALLBACK
_NDC_SIGNAL_KEYS  = ('景氣對策信號(分)', '景氣對策信號')
_NDC_LI_KEYS      = ('領先指標綜合指數', '領先指標', '領先指標(綜合指數)')

# v18.177 dgtw NDC 配置
_DGTW_SEARCH_URLS = (
    'https://data.gov.tw/api/v2/rest/dataset/search',
    'https://data.gov.tw/api/v1/rest/dataset/search',
)
_DGTW_DATASET_META_URLS = (
    'https://data.gov.tw/api/v2/rest/dataset/{id}',
    'https://data.gov.tw/api/v1/rest/dataset/{id}',
)
# 候選 dataset ID（國發會景氣指標序列；以 PMI=6100 為錨點向周邊延伸）
_DGTW_NDC_SIGNAL_CANDIDATE_IDS = ('6097', '6098', '6099', '6101', '6102',
                                    '6103', '6104', '6105', '6106', '6107',
                                    '6108', '6109', '6053', '6054', '6055', '6056')
_DGTW_NDC_LEADING_CANDIDATE_IDS = _DGTW_NDC_SIGNAL_CANDIDATE_IDS
_DGTW_NDC_SIGNAL_KEYWORDS = ('景氣對策信號', '景氣信號', '對策信號')
_DGTW_NDC_LEADING_KEYWORDS = ('領先指標', '景氣領先', '綜合領先指標')
_DGTW_NDC_SIGNAL_VALUE_KEYWORDS = ('信號分數', '對策信號', '景氣對策', '分數', '燈號')
_DGTW_NDC_LEADING_VALUE_KEYWORDS = ('領先指標', '綜合領先', '不含趨勢', '指數')


def _dgtw_search_dataset_ids(keyword: str, label: str = "") -> list[str]:
    """v18.177：data.gov.tw search API 找關鍵字對應 dataset ID list。

    多 endpoint 變體 + 多 result shape parser；任一成功即回；全失敗回 []。
    """
    _ids: list[str] = []
    for _su in _DGTW_SEARCH_URLS:
        try:
            _r = fetch_url(_su, params={'q': keyword, 'limit': 20},
                            timeout=10, attempts=1,
                            headers={'Accept': 'application/json'})
            if _r is None or _r.status_code != 200:
                continue
            try:
                _j = _r.json()
            except Exception:
                continue
            _items = (_j.get('result', {}).get('results')
                      or _j.get('results') or _j.get('data', {}).get('results')
                      or _j.get('data') or [])
            for _it in _items:
                _did = str(_it.get('id') or _it.get('datasetId') or
                           _it.get('resourceId') or '').strip()
                if _did and _did.isdigit() and _did not in _ids:
                    _ids.append(_did)
            if _ids:
                if label:
                    print(f'[tw_macro/dgtw/{label}] search '
                          f'"{keyword}" → {len(_ids)} IDs')
                return _ids
        except Exception:
            continue
    return _ids


def _dgtw_fetch_dataset_csv(ds_id: str, value_keywords: tuple,
                             label: str = "") -> Optional[pd.DataFrame]:
    """v18.177：給 dataset ID，抓 metadata 找 CSV → 解析全表 [date, value]。

    Sanity：value ∈ [-1e6, 1e6]（避開字串、NaN）；月頻保留所有列。
    """
    import csv as _csv
    import io as _io
    for _mu_t in _DGTW_DATASET_META_URLS:
        _mu = _mu_t.format(id=ds_id)
        try:
            _r_meta = fetch_url(_mu, timeout=10, attempts=1,
                                 headers={'Accept': 'application/json'})
            if _r_meta is None or _r_meta.status_code != 200:
                continue
            try:
                _j_meta = _r_meta.json()
            except Exception:
                continue
            _res = (_j_meta.get('result', {}).get('resources')
                    or _j_meta.get('resources')
                    or _j_meta.get('data', {}).get('resources') or [])
            if not _res:
                continue
            # 找 CSV resource
            _csv_url = None
            for _it in _res:
                _fmt = str(_it.get('format', '')).upper()
                _url2 = _it.get('url') or _it.get('resourceDownloadUrl')
                if _fmt in ('CSV', 'JSON') and _url2:
                    _csv_url = _url2
                    break
            if not _csv_url:
                continue
            _r_csv = fetch_url(_csv_url, timeout=15, attempts=2)
            if _r_csv is None or _r_csv.status_code != 200:
                continue
            _txt = _r_csv.content.decode('utf-8-sig', errors='ignore')
            _rdr = list(_csv.DictReader(_io.StringIO(_txt)))
            if not _rdr:
                continue
            _rows: list[tuple[str, float]] = []
            for _row in _rdr:
                _v = None
                _d = None
                for _k, _vc in _row.items():
                    _kl = str(_k)
                    if _v is None and any(_x in _kl for _x in value_keywords):
                        try:
                            _vn = float(str(_vc).strip().replace(',', ''))
                            if -1e6 < _vn < 1e6:
                                _v = _vn
                        except (ValueError, TypeError):
                            pass
                    if _d is None:
                        _m = _re.search(r'(20\d{2}|19\d{2})[-/年]?(\d{1,2})',
                                         str(_vc))
                        if _m:
                            _d = f'{_m.group(1)}-{int(_m.group(2)):02d}-01'
                if _v is not None and _d:
                    _rows.append((_d, _v))
            if not _rows:
                continue
            _df = pd.DataFrame(_rows, columns=['date', 'value'])
            _df = _df.drop_duplicates(subset=['date'], keep='last').sort_values(
                'date').reset_index(drop=True)
            if label:
                print(f'[tw_macro/dgtw/{label}] dataset/{ds_id} '
                      f'→ {len(_df)} rows')
            return _df
        except Exception:
            continue
    return None


def _dgtw_ndc_indicator_series(keywords: tuple, value_keywords: tuple,
                                 candidate_ids: tuple,
                                 label: str = "") -> Optional[pd.DataFrame]:
    """v18.177：兩路徑彙整找 NDC 月頻指標 DataFrame。

    ① search API 找 dataset IDs → 試每個的 CSV
    ② 直接 probe 鄰近 candidate IDs
    任一命中且回 DataFrame[date, value] 即返；全失敗回 None。
    """
    # 路徑 1：search API
    for _kw in keywords:
        _ids = _dgtw_search_dataset_ids(_kw, label=label)
        for _did in _ids:
            _df = _dgtw_fetch_dataset_csv(_did, value_keywords, label=label)
            if _df is not None and not _df.empty:
                return _df
    # 路徑 2：probe candidate IDs
    for _did in candidate_ids:
        _df = _dgtw_fetch_dataset_csv(_did, value_keywords, label=label)
        if _df is not None and not _df.empty:
            return _df
    return None


def _finmind_macro_series(indicator_keys: tuple, months_back: int = 18,
                          token: str = "") -> Optional[pd.DataFrame]:
    """通用：抓 FinMind TaiwanMacroEconomics 指定指標的月頻歷史。
    回傳 DataFrame[date, value] 由舊到新；找不到回 None。"""
    today    = _dt.date.today()
    end_dt   = today.strftime("%Y-%m-%d")
    # months_back 月轉日（多抓一倍緩衝）
    start_dt = (today - _dt.timedelta(days=int(months_back * 31))).strftime("%Y-%m-%d")
    params: dict = {
        'dataset':    'TaiwanMacroEconomics',
        'start_date': start_dt,
        'end_date':   end_dt,
    }
    if token:
        params['token'] = token
    r = fetch_url(FINMIND_BASE, params=params, timeout=15)
    if r is None:
        return None
    try:
        rows = r.json().get('data', [])
    except Exception:
        return None
    if not rows:
        return None
    df = pd.DataFrame(rows)
    # FinMind 欄位名可能是 indicator / name / metric
    cand_col = next((c for c in ('indicator', 'name', 'metric')
                     if c in df.columns), None)
    val_col  = next((c for c in ('value', 'data') if c in df.columns), None)
    if cand_col is None or val_col is None or 'date' not in df.columns:
        return None
    mask = df[cand_col].astype(str).isin(indicator_keys)
    if not mask.any():
        # 用 contains 兜底
        mask = df[cand_col].astype(str).apply(
            lambda x: any(k in x for k in indicator_keys))
    if not mask.any():
        return None
    sub = df.loc[mask, ['date', val_col]].copy()
    sub.columns = ['date', 'value']
    sub['value'] = pd.to_numeric(sub['value'], errors='coerce')
    sub = sub.dropna().sort_values('date').reset_index(drop=True)
    if sub.empty:
        return None
    return sub


@_ttl_cache(ttl_sec=600, maxsize=8)
def fetch_ndc_signal_history(months_back: int = 12,
                             token: str = "") -> dict:
    """抓景氣對策信號分數歷史（月頻），偵測連 2 月反轉拐點。

    Returns
    -------
    dict
        {
          'score_latest': int | None,    最新月份分數（9~45）
          'score_prev':   int | None,    上月分數
          'score_prev2':  int | None,    上上月分數
          'trend':        list[int],     近 6 月分數
          'inflection':   str,           '🚀 連2月翻多' / '⚠️ 連2月翻空' /
                                          '🟢 持續上升' / '🔴 持續下降' / '📊 持平' /
                                          '⬜ 資料不足'
          'date_latest':  str,
          'source':       'FinMind' | None,
          'error':        str | None,
        }
    """
    result: dict = {
        'score_latest': None, 'score_prev': None, 'score_prev2': None,
        'trend': [], 'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
        # S-PROV-1 v18.249:provenance fetched_at(source 既有,無需改 schema)
        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
    }
    # v18.177 chain：dgtw PRIMARY（免費 NDC OpenData）→ FinMind FALLBACK（付費牆）
    sub = _dgtw_ndc_indicator_series(
        _DGTW_NDC_SIGNAL_KEYWORDS, _DGTW_NDC_SIGNAL_VALUE_KEYWORDS,
        _DGTW_NDC_SIGNAL_CANDIDATE_IDS, label='ndc_signal')
    _src = 'data.gov.tw' if sub is not None and not sub.empty else None
    if sub is None or sub.empty:
        sub = _finmind_macro_series(_NDC_SIGNAL_KEYS,
                                    months_back=months_back, token=token)
        if sub is not None and not sub.empty:
            _src = 'FinMind'
    if sub is None or len(sub) < 3:
        result['error'] = 'dgtw + FinMind 皆無景氣對策信號資料'
        return result
    # v18.177 sanity：信號分數 ∈ [9, 45]
    sub = sub[(sub['value'] >= 9) & (sub['value'] <= 45)].reset_index(drop=True)
    if len(sub) < 3:
        result['error'] = '景氣對策信號通過 sanity 後資料不足'
        return result
    vals = [int(round(v)) for v in sub['value'].tail(6).tolist()]
    cur, prev = vals[-1], vals[-2]
    prev2 = vals[-3] if len(vals) >= 3 else None
    result['score_latest'] = cur
    result['score_prev']   = prev
    result['score_prev2']  = prev2
    result['trend']        = vals
    result['date_latest']  = str(sub['date'].iloc[-1])[:10]
    result['source']       = _src or 'unknown'
    # 拐點判斷：連 2 月同向反轉
    if prev2 is not None:
        # 連 2 月由跌轉升（prev2 ≥ prev 且 prev < cur 且 cur > prev）
        if prev2 >= prev and cur > prev:
            result['inflection'] = '🚀 連2月翻多'
        elif prev2 <= prev and cur < prev:
            result['inflection'] = '⚠️ 連2月翻空'
        elif cur > prev > prev2:
            result['inflection'] = '🟢 連3月上升'
        elif cur < prev < prev2:
            result['inflection'] = '🔴 連3月下降'
        else:
            result['inflection'] = '📊 震盪持平'
    return result


def fetch_ndc_leading_index(months_back: int = 18,
                            token: str = "") -> dict:
    """抓領先指標綜合指數歷史，計算 6M smoothed 變化率與翻揚拐點。

    Returns
    -------
    dict
        {
          'latest':   float | None,
          'prev':     float | None,
          'mom':      float | None,    最新月 MoM%
          'smooth6m': float | None,    最新 6M smoothed change（%）
          'prev_s6m': float | None,    前期 6M smoothed change
          'inflection': str,           '🚀 6M 由負轉正' / '🟢 持續擴張' /
                                       '🔴 持續收縮' / '⚠️ 由正轉負' / '⬜ 資料不足'
          'trend':    list[float],     近 8 月 6M smoothed change
          'date_latest': str,
          'source':   'FinMind' | None,
          'error':    str | None,
        }
    """
    result: dict = {
        'latest': None, 'prev': None, 'mom': None,
        'smooth6m': None, 'prev_s6m': None,
        'inflection': '⬜ 資料不足', 'trend': [],
        'date_latest': '', 'source': None, 'error': None,
        # S-PROV-1 v18.249:provenance fetched_at(source 既有)
        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
    }
    # v18.177 chain：dgtw PRIMARY → FinMind FALLBACK
    sub = _dgtw_ndc_indicator_series(
        _DGTW_NDC_LEADING_KEYWORDS, _DGTW_NDC_LEADING_VALUE_KEYWORDS,
        _DGTW_NDC_LEADING_CANDIDATE_IDS, label='ndc_leading')
    _src_li = 'data.gov.tw' if sub is not None and not sub.empty else None
    if sub is None or sub.empty:
        sub = _finmind_macro_series(_NDC_LI_KEYS,
                                    months_back=months_back, token=token)
        if sub is not None and not sub.empty:
            _src_li = 'FinMind'
    if sub is None or len(sub) < 8:
        result['error'] = 'dgtw + FinMind 皆無領先指標歷史'
        return result
    s = sub.set_index('date')['value'].astype(float)
    cur = float(s.iloc[-1])
    prev = float(s.iloc[-2])
    # 6M smoothed change：用 6 月移動平均的月變化率
    ma6 = s.rolling(6).mean().dropna()
    if len(ma6) < 2:
        result['error'] = '6M MA 樣本不足'
        return result
    s6m = ma6.pct_change().dropna() * 100  # 月變化率 %
    if len(s6m) < 2:
        result['error'] = '6M smoothed change 樣本不足'
        return result
    cur_s, prev_s = float(s6m.iloc[-1]), float(s6m.iloc[-2])
    trend = [round(v, 2) for v in s6m.tail(8).tolist()]
    result.update({
        'latest':   round(cur, 2),
        'prev':     round(prev, 2),
        'mom':      round((cur - prev) / prev * 100, 2) if prev else None,
        'smooth6m': round(cur_s, 2),
        'prev_s6m': round(prev_s, 2),
        'trend':    trend,
        'date_latest': str(s.index[-1])[:10],
        'source':   _src_li or 'unknown',
    })
    if cur_s > 0 and prev_s <= 0:
        result['inflection'] = '🚀 6M 由負轉正'
    elif cur_s > 0:
        result['inflection'] = '🟢 持續擴張'
    elif cur_s < 0 and prev_s >= 0:
        result['inflection'] = '⚠️ 由正轉負'
    elif cur_s < 0:
        result['inflection'] = '🔴 持續收縮'
    else:
        result['inflection'] = '📊 持平'
    return result


@_ttl_cache(ttl_sec=600, maxsize=8)
def fetch_foreign_consecutive_days(days_back: int = 30,
                                   token: str = "") -> dict:
    """抓外資最近 N 日買賣超，計算連續同向日數與反轉拐點。

    Returns
    -------
    dict
        {
          'consec_days': int | None,    當前連續日數（+ 連買、- 連賣）
          'reversed':    bool,          昨日 vs 今日是否反轉
          'today_net':   int | None,    今日淨額（元）
          'prev_streak': int | None,    上一段連續日數（+ / -）
          'inflection':  str,           '🚀 連5賣→買' / '⚠️ 連5買→賣' /
                                        '🟢 連N買' / '🔴 連N賣' / '📊 震盪' /
                                        '⬜ 資料不足'
          'date_latest': str,
          'source':      'FinMind' | None,
          'error':       str | None,
        }
    """
    result: dict = {
        'consec_days': None, 'reversed': False, 'today_net': None,
        'prev_streak': None, 'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
        # S-PROV-1 v18.249:provenance fetched_at(source 既有)
        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
    }
    today    = _dt.date.today()
    end_dt   = today.strftime("%Y-%m-%d")
    start_dt = (today - _dt.timedelta(days=days_back)).strftime("%Y-%m-%d")
    params: dict = {
        'dataset':    'TaiwanStockTotalInstitutionalInvestors',
        'start_date': start_dt,
        'end_date':   end_dt,
    }
    if token:
        params['token'] = token
    r = fetch_url(FINMIND_BASE, params=params, timeout=15)
    if r is None:
        result['error'] = 'FinMind 抓取失敗'
        return result
    try:
        rows = r.json().get('data', [])
    except Exception as e:
        result['error'] = f'FinMind JSON 解析失敗: {e}'
        return result
    fi_rows = [x for x in rows if x.get('name') == 'Foreign_Investor']
    if not fi_rows:
        result['error'] = 'FinMind 無 Foreign_Investor 資料'
        return result
    df = pd.DataFrame(fi_rows)
    df['net'] = pd.to_numeric(df.get('buy', 0), errors='coerce').fillna(0) - \
                pd.to_numeric(df.get('sell', 0), errors='coerce').fillna(0)
    df = df.sort_values('date').reset_index(drop=True)
    if len(df) < 2:
        result['error'] = '外資資料筆數不足'
        return result
    nets = df['net'].astype(float).tolist()
    # 連續日數計算：從尾巴往前數同號
    last_sign = 1 if nets[-1] > 0 else (-1 if nets[-1] < 0 else 0)
    consec = 0
    for v in reversed(nets):
        sign = 1 if v > 0 else (-1 if v < 0 else 0)
        if sign == last_sign and sign != 0:
            consec += 1
        else:
            break
    # 上一段連續日數（同樣由反方向掃描）
    prev_streak = 0
    if consec < len(nets):
        before = nets[:len(nets) - consec]
        if before:
            prev_sign = 1 if before[-1] > 0 else (-1 if before[-1] < 0 else 0)
            for v in reversed(before):
                sign = 1 if v > 0 else (-1 if v < 0 else 0)
                if sign == prev_sign and sign != 0:
                    prev_streak += 1
                else:
                    break
            prev_streak = prev_streak * prev_sign  # 帶號（- 表連賣）
    result['consec_days'] = consec * last_sign
    result['today_net']   = int(nets[-1])
    result['prev_streak'] = prev_streak
    result['date_latest'] = str(df['date'].iloc[-1])[:10]
    result['source']      = 'FinMind'
    result['reversed']    = (consec == 1 and prev_streak * last_sign < -5)
    # 拐點判斷
    if consec == 1 and prev_streak <= -5:
        result['inflection'] = f'🚀 連{-prev_streak}賣→買（拐點）'
    elif consec == 1 and prev_streak >= 5:
        result['inflection'] = f'⚠️ 連{prev_streak}買→賣（拐點）'
    elif consec >= 5 and last_sign > 0:
        result['inflection'] = f'🟢 連{consec}日買超'
    elif consec >= 5 and last_sign < 0:
        result['inflection'] = f'🔴 連{consec}日賣超'
    else:
        result['inflection'] = '📊 震盪'
    return result


# ══════════════════════════════════════════════════════════════
# 整合 API — 一次抓回三大台股總經因子
# ══════════════════════════════════════════════════════════════

def fetch_tw_market_snapshot(days_back: int = 7) -> dict:
    """
    一次抓回三大台股總經因子(寬度 / 外資 / M1B-M2),供 TPI 計算使用。

    Returns
    -------
    dict
        {
            'breadth': fetch_twse_breadth() 回傳值,
            'fii':     fetch_finmind_foreign_investor() 回傳值,
            'm1b_m2':  fetch_cbc_m1b_m2() 回傳值,
        }
    """
    return {
        'breadth': fetch_twse_breadth(),
        'fii':     fetch_finmind_foreign_investor(days_back=days_back),
        'm1b_m2':  fetch_cbc_m1b_m2(),
    }


# ══════════════════════════════════════════════════════════════
# TW PMI 月度歷史 — FinMind TaiwanEconomicIndicator(merrill_clock 共用)
# S-H4 v18.243:從 `merrill_clock.py`(L2 Compute)下沉至 L1 Data,
# 修正 CLAUDE.md §8.2「L2 不得 import proxy_helper」違憲。caller(merrill_clock)
# 改 `from tw_macro import fetch_pmi_history` 並從 `config.FINMIND_TOKEN` 取 token。
# ══════════════════════════════════════════════════════════════
@_ttl_cache(ttl_sec=600, maxsize=4)
def fetch_pmi_history(months: int = 18, token: str = "") -> Optional[pd.DataFrame]:
    """從 FinMind 抓台灣 PMI 月度歷史(含當期),merrill 時鐘 YoY 算用。

    Parameters
    ----------
    months : int
        往回抓的月數(實際抓略多,容週末/假日 lag)。
    token : str
        FinMind API token。空 → 回 None(免費版有 dataset 限制)。

    Returns
    -------
    pd.DataFrame  欄位:
        - `date` (Timestamp):資料歸屬日(normalized 月底)
        - `value` (float):PMI 數值(已過濾合理範圍)
        - `source` (str):血緣標識,"FinMind:TaiwanEconomicIndicator:PMI"(S-PROV-1 v18.247)
        - `fetched_at` (str):本次抓取 UTC ISO(S-PROV-1 v18.247)

    失敗時回傳 None。
    """
    from shared.signal_thresholds import PMI_VALID_MAX, PMI_VALID_MIN
    if not token:
        return None
    _start = (_dt.date.today() - _dt.timedelta(days=months * 31)).strftime('%Y-%m-%d')
    _r = fetch_url(
        FINMIND_BASE,
        params={'dataset': 'TaiwanEconomicIndicator',
                'start_date': _start, 'token': token},
        timeout=15)
    if _r is None:
        print('[tw_macro/pmi-hist] fetch_url None(proxy 失敗)')
        return None
    if _r.status_code != 200:
        print(f'[tw_macro/pmi-hist] HTTP {_r.status_code}')
        return None
    try:
        _data = (_r.json() or {}).get('data') or []
    except Exception as _e:
        print(f'[tw_macro/pmi-hist] JSON 解析失敗:{type(_e).__name__}')
        return None
    _rows = [d for d in _data
             if 'PMI' in str(d.get('name', '')) or '製造業' in str(d.get('name', ''))]
    if not _rows:
        print('[tw_macro/pmi-hist] FinMind 無 PMI series')
        return None
    _df = pd.DataFrame(_rows)
    _df['date'] = pd.to_datetime(_df['date']).dt.normalize()
    _df['value'] = pd.to_numeric(_df['value'], errors='coerce')
    _df = _df.dropna(subset=['value']).sort_values('date').reset_index(drop=True)
    _df = _df[(_df['value'] >= PMI_VALID_MIN) & (_df['value'] <= PMI_VALID_MAX)].reset_index(drop=True)
    print(f'[tw_macro/pmi-hist] ✅ {len(_df)} months')
    out = _df[['date', 'value']].copy()
    # S-PROV-1 v18.247 phase 3:provenance schema(§2.2)
    out['source'] = 'FinMind:TaiwanEconomicIndicator:PMI'
    out['fetched_at'] = pd.Timestamp.now('UTC').isoformat()
    return out


# ════════════════════════════════════════════════════════════════════════════
# v18.270 — TW 央行政策階段判讀 4 大缺口補完
# (1) TW CPI YoY  (2) TW 失業率  (3) CBC 重貼現率  (4) USDTWD spot
# 對齊 §7 alignment / §8 architecture
# ════════════════════════════════════════════════════════════════════════════

# FinMind TaiwanMacroEconomics 指標關鍵字(含模糊比對 fallback)
_TW_CPI_YOY_KEYS = (
    '消費者物價指數(CPI)-總指數年增率(%)',
    '消費者物價基本分類指數(CPI)-總指數(原始值)年增率(%)',
    'CPI 年增率',
    '消費者物價指數',
    '物價指數年增率',
    'CPI',
)
_TW_UNEMP_KEYS = (
    '失業率(%)',
    '失業率',
)


@_ttl_cache(ttl_sec=900, maxsize=8)  # 15min;CPI 月後 5-7 天發布,無需更頻繁
def fetch_tw_cpi_yoy(months_back: int = 24, token: str = "") -> Optional[pd.DataFrame]:
    """抓 TW 消費者物價指數 CPI 年增率(% YoY)月頻歷史。

    來源:FinMind TaiwanMacroEconomics(主計總處原始)。
    Unit: % YoY(對齊 macro_core.MACRO_THRESHOLDS.CPI 範圍 [-5, 20])。
    發布延遲:月後 ~5-7 天;修正風險:低(主計總處權威)。

    Returns
    -------
    pd.DataFrame[date, value, source, fetched_at] | None
        由舊到新排序;找不到回 None(per §1 fail loud,不偽造)。
    """
    sub = _finmind_macro_series(_TW_CPI_YOY_KEYS, months_back=months_back, token=token)
    if sub is None or sub.empty:
        print(f'[tw_macro/cpi_yoy] FinMind 無 CPI YoY 資料(keys={_TW_CPI_YOY_KEYS[:2]}…)')
        return None
    # §3.2 sanity:CPI YoY ∈ [-5, 20]
    sub = sub[(sub['value'] >= -5) & (sub['value'] <= 20)].reset_index(drop=True)
    if sub.empty:
        print('[tw_macro/cpi_yoy] sanity 過濾後資料為空(疑似指標名比對誤觸非 YoY 欄)')
        return None
    out = sub.copy()
    out['source'] = 'FinMind:TaiwanMacroEconomics:CPI_YoY'
    out['fetched_at'] = pd.Timestamp.now('UTC').isoformat()
    print(f'[tw_macro/cpi_yoy] ✅ {len(out)} months, latest={out.iloc[-1]["value"]:+.2f}%')
    return out


@_ttl_cache(ttl_sec=900, maxsize=8)
def fetch_tw_unemployment(months_back: int = 24, token: str = "") -> Optional[pd.DataFrame]:
    """抓 TW 失業率(% level)月頻歷史。

    來源:FinMind TaiwanMacroEconomics(主計總處勞動力統計)。
    Unit: % level(歷史範圍 [3.6, 6.0])。
    發布延遲:月後 ~22 天(較慢);修正風險:極低。

    Returns
    -------
    pd.DataFrame[date, value, source, fetched_at] | None
    """
    sub = _finmind_macro_series(_TW_UNEMP_KEYS, months_back=months_back, token=token)
    if sub is None or sub.empty:
        print(f'[tw_macro/unemp] FinMind 無失業率資料(keys={_TW_UNEMP_KEYS})')
        return None
    # §3.2 sanity:失業率 ∈ [2, 8]
    sub = sub[(sub['value'] >= 2) & (sub['value'] <= 8)].reset_index(drop=True)
    if sub.empty:
        print('[tw_macro/unemp] sanity 過濾後資料為空')
        return None
    out = sub.copy()
    out['source'] = 'FinMind:TaiwanMacroEconomics:Unemployment'
    out['fetched_at'] = pd.Timestamp.now('UTC').isoformat()
    print(f'[tw_macro/unemp] ✅ {len(out)} months, latest={out.iloc[-1]["value"]:.2f}%')
    return out


@_ttl_cache(ttl_sec=3600, maxsize=4)  # 1hr;政策利率變動極少
def fetch_cbc_discount_rate(months_back: int = 24, fred_api_key: str = "") -> Optional[pd.DataFrame]:
    """抓 CBC 重貼現率(% level)月頻歷史。

    來源:FRED INTDSRTWM193N(IMF International Financial Statistics 月頻)。
    Unit: % level(歷史範圍 [1.125, 2.875])。
    發布延遲:央行理監事會公告即時,FRED 月後 1-2 月;修正風險:無(政策利率不修)。

    Returns
    -------
    pd.DataFrame[date, value, source, fetched_at] | None
    """
    if not fred_api_key:
        print('[tw_macro/cbc_rate] fred_api_key 空,跳過')
        return None
    # 避免迴圈 import:lazy import macro_core(macro_core.py 屬同層 L1,可互相 lazy import)
    from src.data.macro import fetch_fred  # noqa: PLC0415
    from shared.fred_series import FRED_TW_DISCOUNT_RATE  # noqa: PLC0415

    df = fetch_fred(FRED_TW_DISCOUNT_RATE, fred_api_key, n=max(months_back, 24))
    if df is None or df.empty:
        print(f'[tw_macro/cbc_rate] FRED {FRED_TW_DISCOUNT_RATE} 無資料')
        return None
    # §3.2 sanity:重貼現率 ∈ [0, 5]
    df = df[(df['value'] >= 0) & (df['value'] <= 5)].reset_index(drop=True)
    if df.empty:
        print('[tw_macro/cbc_rate] sanity 過濾後資料為空')
        return None
    # fetch_fred 已附 source/fetched_at(S-PROV-1 phase 1),改寫 source 標籤明確指出語意
    out = df.copy()
    out['source'] = f'FRED:{FRED_TW_DISCOUNT_RATE}:CBC_DiscountRate'
    print(f'[tw_macro/cbc_rate] ✅ {len(out)} months, latest={out.iloc[-1]["value"]:.3f}%')
    return out


@_ttl_cache(ttl_sec=3600, maxsize=4)
def fetch_usdtwd_close(days_back: int = 180) -> Optional[pd.DataFrame]:
    """抓 USD/TWD 日匯率收盤序列。

    來源:Yahoo Chart API `TWD=X`(走 NAS proxy)。
    Unit: TWD/USD(數字越大 = 台幣越貶,歷史 ~[28, 35])。
    發布延遲:EOD 翌日;修正風險:無。

    Returns
    -------
    pd.DataFrame[date, value, source, fetched_at] | None

    Notes
    -----
    `daily_checklist.py` 既有用 yfinance 直抓 TWD=X,此 fetcher 走 macro_core 的
    proxy 化 Chart API path,作 macro 模組統一入口。caller 兩種皆可用。
    """
    # lazy import 避免 import loop
    from src.data.macro import fetch_yf_close  # noqa: PLC0415

    # range_ 取較寬期(180d 約 6 月,足供 60D MA + 趨勢計算)
    s = fetch_yf_close('TWD=X', range_=f'{max(days_back, 60)}d')
    if s is None or s.empty:
        print('[tw_macro/usdtwd] Yahoo TWD=X 無資料')
        return None
    # §3.2 sanity:USDTWD ∈ [25, 40]
    s = s[(s >= 25) & (s <= 40)]
    if s.empty:
        print('[tw_macro/usdtwd] sanity 過濾後資料為空')
        return None
    out = pd.DataFrame({
        'date': pd.to_datetime(s.index).normalize(),
        'value': s.values,
        'source': 'Yahoo:TWD=X:Close',
        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
    }).reset_index(drop=True)
    print(f'[tw_macro/usdtwd] ✅ {len(out)} days, latest={out.iloc[-1]["value"]:.3f}')
    return out


# ════════════════════════════════════════════════════════════════════════════
# v18.271 — China macro 5 指標(方向 B,對稱 Fund v19.113)
# 服務:台積電/出口企業終端需求 + 全球流動性二把交椅判讀
# ════════════════════════════════════════════════════════════════════════════

# SSOT specs:對應 shared/fred_series 的 5 個 China 常數(避免重複定義 string literal)
# DEXCHUS 日頻 ~2y;其餘 4 條月頻 ~10y
def _china_fred_specs():
    """SSOT lookup 避免 import 順序 issue。"""
    from shared.fred_series import (  # noqa: PLC0415
        FRED_CHN_CPI,
        FRED_CHN_M2,
        FRED_CHN_OECD_CLI,
        FRED_CHN_PMI,
        FRED_USDCNY,
    )
    return [
        (FRED_USDCNY,         500),
        (FRED_CHN_OECD_CLI,   120),
        (FRED_CHN_CPI,        120),
        (FRED_CHN_M2,         120),
        (FRED_CHN_PMI,        120),
    ]


@_ttl_cache(ttl_sec=1800, maxsize=4)  # 30min;OECD 月頻發布
def fetch_china_macro(fred_api_key: str = "") -> dict:
    """並行抓 5 條 China macro FRED series。

    Returns
    -------
    dict[series_id, pd.DataFrame]
        key 為 FRED series ID,value 為 macro_core.fetch_fred 結果。
        失敗 series 對應空 DataFrame;api_key 空 → 空 dict。

    §1 fail loud:單條失敗回空 DataFrame + caller 自己判 .empty,
    不偽造數值。
    """
    if not fred_api_key:
        print('[tw_macro/china_macro] fred_api_key 空,跳過')
        return {}
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    from src.data.macro import fetch_fred  # noqa: PLC0415

    specs = _china_fred_specs()
    result: dict = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(fetch_fred, sid, fred_api_key, n): sid for sid, n in specs}
        for fut in futs:
            sid = futs[fut]
            try:
                df = fut.result()
                result[sid] = df
                if df is not None and not df.empty:
                    print(f'[tw_macro/china_macro/{sid}] ✅ {len(df)} pts')
                else:
                    print(f'[tw_macro/china_macro/{sid}] ⚠️ empty')
            except Exception as e:
                print(f'[tw_macro/china_macro/{sid}] 失敗: {type(e).__name__}: {e}')
                import pandas as _pd  # noqa: PLC0415
                result[sid] = _pd.DataFrame()
    # v18.354 PR-Q4 S-PROV-1 phase 19:aggregator 級 audit trail
    # (內部 5 條 fetch_fred 已各自 phase 1 寫 attrs;此處記彙整成果)
    try:
        import sys as _sys_prov_chn
        _now_chn = pd.Timestamp.now('UTC').isoformat()
        _ok = sum(1 for _df in result.values() if _df is not None and not _df.empty)
        print(f'[fetch_china_macro] source=FRED:china_macro(5-series-parallel) '
              f'fetched_at={_now_chn} result=dict:{_ok}/{len(result)}series',
              file=_sys_prov_chn.stderr)
    except Exception:
        pass
    return result
