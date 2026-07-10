"""src/data/stock/app_stock_fetchers.py — app.py 個股 L1 fetcher 集中地(v18.405 U5 B3-δ).

從 app.py:251-643 抽出 7 個 helper + fetcher,對齊 APP_PY_AUDIT.md B3-δ phase。

§8.2 layer:L1 Data — yfinance / FinMind / TWSE HTTP fetch + cache。
§8.2.A EX-CACHE-1 letter-compliant(try/except + `_NoOpST` fallback + secrets dict)。
§2.2 / S-PROV-1 phase 19 provenance(source + fetched_at)注入 DataFrame.attrs。

對外 API:
- `_get_loader(_v)`:cache_resource StockDataLoader 單例
- `_expected_latest_trading_date()`:預期最新交易日(週末退到週五)
- `fetch_price_data(sid, days) -> tuple`:股價 DataFrame + name + err
- `fetch_dividend_data(sid) -> tuple`:5 年配息(FinMind → yfinance → TWSE 3-fallback)
- `fetch_financials(sid, industry) -> tuple`:合約負債 + 固定資產 + 資本支出(FinMind BS/CF)
- `fetch_revenue(sid) -> tuple`:月營收(via StockDataLoader)
- `fetch_quarterly(sid, _ver) -> tuple`:季財報(via StockDataLoader)
- `fetch_quarterly_extra(sid, _ver) -> tuple`:近 12 季 BS/CF 時序(via StockDataLoader)
"""
from __future__ import annotations

import datetime
import os

import pandas as pd

from src.config import FINMIND_API_URL  # Batch 10 v18.412 SSOT

try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f

        @staticmethod
        def cache_resource(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f

        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.app_cache import _load_cache, _save_cache
from shared.signal_thresholds import PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS
from shared.ttls import TTL_30MIN, TTL_1HOUR
from src.data.core import StockDataLoader, _LOADER_VERSION


def _get_finmind_token() -> str:
    """每次動態讀取最新 Token:st.secrets > os.environ。
    對齊 app.py:_get_fm_token 行為(避免循環 import)。"""
    try:
        _tok = st.secrets.get('FINMIND_TOKEN', '') if hasattr(st, 'secrets') else ''
    except Exception:
        _tok = ''
    return _tok or os.environ.get('FINMIND_TOKEN', '')


def _make_proxy_session():
    """NAS proxy session,fallback 純 requests.Session。
    對齊 app.py:_bps 行為。"""
    import requests
    try:
        from src.data.stock import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s


@st.cache_resource
def _get_loader(_v: str = _LOADER_VERSION):
    """快取單一 StockDataLoader 實例,避免每次 cache miss 都重新 login。

    `_v` 綁定 `data_loader._LOADER_VERSION`:改動 loader 邏輯並 bump 版本後,
    cache key 隨之改變 → 自動建立新實例,避免 Streamlit hot-reload 後仍用到
    舊實例的舊方法碼(stale @st.cache_resource,PR #44 NoneType 殘留即此故)。
    """
    return StockDataLoader()


def _expected_latest_trading_date():
    """預期最新交易日(週末退到週五)。"""
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


@st.cache_data(ttl=TTL_30MIN, max_entries=10)
def fetch_price_data(sid, days):
    """股價歷史(本地 pkl cache → StockDataLoader.get_combined_data)。"""
    _c = _load_cache('price', sid, str(days), ttl_hours=0.5)
    if _c is not None:
        df_c, name_c = _c
        if df_c is not None and not df_c.empty and float(df_c['close'].max()) > 0:
            try:
                _latest = df_c['date'].iloc[-1]
                if hasattr(_latest, 'date'):
                    _latest = _latest.date()
                elif isinstance(_latest, str):
                    _latest = datetime.datetime.strptime(str(_latest)[:10], '%Y-%m-%d').date()
                # v19.74:容忍窗 5 → 14 日曆日(SSOT)。原 5 天在春節封關(最長 13 日曆日)
                # 期間把「休市無新資料」誤判 stale → 每次冷啟動全檔強制重抓 → 撞
                # FinMind/yfinance 限流(重抓也只拿到同樣的舊資料,純燒配額)。
                # 真新鮮度仍由 pkl TTL(0.5h) + @st.cache_data TTL(30min) 把關。
                _gap_days = (_expected_latest_trading_date() - _latest).days
                if _gap_days <= PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS:
                    if _gap_days > 5:  # §5 可觀測性:連假容忍範圍留跡,便於診斷
                        print(f'[fetch_price_data] {sid} 序列最新日落後 {_gap_days} 天'
                              f'(≤{PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS} 連假容忍),沿用快取')
                    return df_c, name_c, None
            except Exception:
                return df_c, name_c, None
    loader = _get_loader()
    df, err, name = loader.get_combined_data(sid, days + 60, True)
    if err or df is None:
        return None, None, err
    result = df.tail(days).reset_index(drop=True)
    try:
        result.attrs.update(df.attrs)
        # v18.351 PR-Q1 S-PROV-1 phase 19:確保 source/fetched_at 存在(§2.2)。
        # data_loader.get_combined_data 內部 fetchers (phase 15/16) 已寫 attrs;
        # 若上游缺(備援路徑),setdefault 補通用標籤 — 不覆蓋既有值
        result.attrs.setdefault('source', 'app:fetch_price_data:data_loader.get_combined_data')
        result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
    except Exception:
        pass
    _save_cache('price', sid, (result, name), str(days))
    return result, name, None


@st.cache_data(ttl=TTL_30MIN, max_entries=10)
def fetch_dividend_data(sid):
    """5 年配息(FinMind REST → SDK → yfinance → TWSE 4-fallback)。"""
    avg_div, yearly, source = 0.0, [], ''
    try:
        try:
            from FinMind.data import DataLoader as FM
        except ImportError:
            from finmind.data import DataLoader as FM
        dl = FM()
        _fm_tok_div = _get_finmind_token()
        if _fm_tok_div:
            try:
                dl.login_by_token(api_token=_fm_tok_div)
            except Exception:
                pass
        end = datetime.date.today()
        # First try REST API with proper auth
        _div_resp = _make_proxy_session().get(
            FINMIND_API_URL,
            params={'dataset': 'TaiwanStockDividend', 'data_id': sid,
                    'start_date': (end - datetime.timedelta(days=365 * 6)).strftime('%Y-%m-%d')},
            headers={'Authorization': f'Bearer {_get_finmind_token()}'}, timeout=20)
        _div_jd = _div_resp.json()
        print(f'[股利REST] {sid} status={_div_jd.get("status")}')
        ddf = pd.DataFrame(_div_jd['data']) if _div_jd.get('status') == 200 and _div_jd.get('data') else None
        if ddf is None or ddf.empty:
            ddf = dl.taiwan_stock_dividend(
                stock_id=sid,
                start_date=(end - datetime.timedelta(days=365 * 6)).strftime('%Y-%m-%d'))
        if ddf is not None and not ddf.empty:
            cash_col = next((c for c in ['CashDividend', 'cash_dividend', 'StockEarningsDistribution']
                             if c in ddf.columns), None)
            if cash_col is None:
                nums = ddf.select_dtypes(include='number').columns.tolist()
                if nums:
                    cash_col = nums[0]
            if cash_col:
                ddf['date'] = pd.to_datetime(ddf['date'], errors='coerce')
                ddf['year'] = ddf['date'].dt.year
                ddf['cash'] = pd.to_numeric(ddf[cash_col], errors='coerce').fillna(0)
                yr = ddf.groupby('year')['cash'].sum().reset_index().tail(5)
                avg_div = float(yr['cash'].mean()) if len(yr) > 0 else 0
                yearly = yr.to_dict('records')
                source = 'FinMind'
    except Exception:
        pass
    # ── 備援2: yfinance(v18.209 K5:改走 yf_proxy.cached_dividends,proxy+cache 統一)──
    if avg_div == 0:
        try:
            from src.data.proxy import cached_dividends as _yp_div
            divs = _yp_div(f'{sid}.TW')
            if divs is not None and len(divs) > 0:
                divs.index = pd.DatetimeIndex(divs.index).tz_localize(None)
                rec = divs[divs.index >= pd.Timestamp.now() - pd.DateOffset(years=5)]
                if len(rec) > 0:
                    ann = rec.resample('YE').sum().reset_index()
                    ann.columns = ['date', 'cash']
                    ann['year'] = pd.to_datetime(ann['date']).dt.year
                    yr = ann[['year', 'cash']].tail(5)
                    avg_div = float(yr['cash'].mean())
                    yearly = yr.to_dict('records')
                    source = 'yfinance'
        except Exception:
            pass

    # ── 備援3: TWSE 除權息資料(官方,免Token)──
    if avg_div == 0:
        try:
            _tw_div_url = 'https://www.twse.com.tw/rwd/zh/exRight/TWT49U'
            _start_dt_div = (datetime.date.today() - datetime.timedelta(days=365 * 6)).strftime('%Y%m%d')
            _end_dt_div = datetime.date.today().strftime('%Y%m%d')
            _tw_div_r = _make_proxy_session().get(
                _tw_div_url,
                params={'response': 'json', 'strDate': _start_dt_div,
                        'endDate': _end_dt_div, 'stockNo': sid},
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                         'Referer': 'https://www.twse.com.tw/',
                         'Accept': 'application/json, text/javascript, */*; q=0.01',
                         'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
                         'X-Requested-With': 'XMLHttpRequest'},
                timeout=15)
            _tw_div_j = _tw_div_r.json()
            if _tw_div_j.get('stat') == 'OK' and _tw_div_j.get('data'):
                _tw_div_rows = []
                for _dr in _tw_div_j['data']:
                    # 欄位:[日期, 股票代號, 名稱, 除權息前收盤, 開始交易基準價, 現金股利, 股票股利, ...]
                    try:
                        _yr_div = int(str(_dr[0]).split('/')[0])
                        if _yr_div < 1000:
                            _yr_div += 1911
                        _cash_d = float(str(_dr[5]).replace(',', '')) if len(_dr) > 5 else 0
                        if _cash_d > 0:
                            _tw_div_rows.append({'year': _yr_div, 'cash': _cash_d})
                    except Exception:
                        pass
                if _tw_div_rows:
                    _tw_div_df = pd.DataFrame(_tw_div_rows)
                    yr = _tw_div_df.groupby('year')['cash'].sum().reset_index().tail(5)
                    avg_div = float(yr['cash'].mean())
                    yearly = yr.to_dict('records')
                    source = 'TWSE'
        except Exception:
            pass

    # v18.351 PR-Q1 S-PROV-1 phase 19:stderr 記 provenance(§2.2 audit trail)。
    # 介面 0 改:return 仍是 (avg_div, yearly, source) 3-tuple,caller 由 source 欄已可追溯;
    # fetched_at 走 stderr log(tuple 增欄會破 caller)
    try:
        import sys as _sys_prov
        _now = pd.Timestamp.now('UTC').isoformat()
        print(f'[fetch_dividend_data] sid={sid} source={source or "FAIL"} '
              f'fetched_at={_now} avg_div={avg_div:.4f} years={len(yearly)}',
              file=_sys_prov.stderr)
    except Exception:
        pass
    return avg_div, yearly, source


@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_financials(sid, industry: str = ""):
    """合約負債 + 固定資產 + 資本支出 — v3.35 簡化版。

    100% FinMind(免費版已確認 status=200)。
    type 欄位為主鍵,比 origin_name 更可靠。
    """
    try:
        from src.data.stock import build_proxy_session as _bps_fin
        _rq_f = _bps_fin()
    except Exception:
        import requests as _rq_f_fallback
        _rq_f = _rq_f_fallback.Session()
    _rq_f.verify = False

    cl = cx = _capex = None
    cl_src = cx_src = cx_src_capex = ""
    fetch_errors = []
    _tok = _get_finmind_token()
    _start = (datetime.date.today() - datetime.timedelta(days=365 * 3)).strftime('%Y-%m-%d')

    # ── Step 1: BalanceSheet → 合約負債 + 固定資產 ──────────────
    try:
        _params = {"dataset": "TaiwanStockBalanceSheet", "data_id": sid, "start_date": _start}
        if _tok:
            _params["token"] = _tok
        _hdrs = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        if _tok:
            _hdrs["Authorization"] = f"Bearer {_tok}"
        _r = _rq_f.get(FINMIND_API_URL,
                       params=_params, headers=_hdrs, timeout=20)
        _j = _r.json()
        _rows = _j.get("data", [])
        _fm_status = _j.get("status")
        _fm_msg = _j.get("msg", "")
        print(f"[FM-BS] {sid} HTTP {_r.status_code} status={_fm_status} rows={len(_rows)}")
        if _fm_status != 200:
            fetch_errors.append(f"FinMind-BS:HTTP{_r.status_code}:{_fm_msg or _fm_status}")
        if _fm_status == 200 and _rows:
            # 取最新一季
            _dates = sorted(set(r.get("date", "") for r in _rows), reverse=True)
            _latest_dt = _dates[0] if _dates else None
            _latest = [r for r in _rows if r.get("date") == _latest_dt]
            print(f"[FM-BS] Latest={_latest_dt} rows={len(_latest)}")

            # 合約負債
            _CL_TYPES = ["CurrentContractLiabilities", "ContractLiabilities"]
            _CL_NAMES = ["合約負債", "契約負債", "預收款項"]
            _cl_total = 0.0
            for _row in _latest:
                _t = str(_row.get("type", ""))
                if any(_t == _ct or _t.startswith(_ct) for _ct in _CL_TYPES):
                    _v = float(str(_row.get("value", 0)).replace(",", "") or 0)
                    if _v > 0:
                        _cl_total += _v
            if _cl_total == 0:  # fallback: origin_name
                for _row in _latest:
                    _n = str(_row.get("origin_name", ""))
                    if any(_k in _n for _k in _CL_NAMES):
                        _v = float(str(_row.get("value", 0)).replace(",", "") or 0)
                        if _v > 0:
                            _cl_total += _v
            if _cl_total > 0:
                cl = _cl_total
                cl_src = "FinMind"
                print(f"[FM-BS] ✅ 合約負債={cl / 1e8:.2f}億")

            # 固定資產
            _FA_TYPE = "PropertyPlantAndEquipment"
            for _row in _latest:
                _t = str(_row.get("type", ""))
                if _t == _FA_TYPE or (_FA_TYPE in _t and "_per" not in _t):
                    _v = float(str(_row.get("value", 0)).replace(",", "") or 0)
                    if _v > 0:
                        cx = _v
                        cx_src = "FinMind"
                        break
            if cx is None:
                for _row in _latest:
                    _n = str(_row.get("origin_name", ""))
                    if any(_k in _n for _k in ["不動產、廠房及設備", "固定資產"]):
                        _v = float(str(_row.get("value", 0)).replace(",", "") or 0)
                        if _v > 0:
                            cx = _v
                            cx_src = "FinMind-name"
                            break
            if cx:
                print(f"[FM-BS] ✅ 固定資產={cx / 1e8:.2f}億")
    except Exception as _e_bs:
        err_msg = f"FinMind-BS:{type(_e_bs).__name__}:{_e_bs}"
        fetch_errors.append(err_msg)
        print(f"[FM-BS] ❌ {err_msg}")

    # ── Step 2: CashFlowsStatement → 資本支出 ────────────────────
    try:
        _params2 = {"dataset": "TaiwanStockCashFlowsStatement", "data_id": sid, "start_date": _start}
        if _tok:
            _params2["token"] = _tok
        _hdrs2 = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        if _tok:
            _hdrs2["Authorization"] = f"Bearer {_tok}"
        _r2 = _rq_f.get(FINMIND_API_URL,
                        params=_params2, headers=_hdrs2, timeout=20)
        _j2 = _r2.json()
        _rows2 = _j2.get("data", [])
        _fm2_status = _j2.get("status")
        _fm2_msg = _j2.get("msg", "")
        print(f"[FM-CF] {sid} HTTP {_r2.status_code} status={_fm2_status} rows={len(_rows2)}")
        if _fm2_status != 200:
            fetch_errors.append(f"FinMind-CF:HTTP{_r2.status_code}:{_fm2_msg or _fm2_status}")
        if _fm2_status == 200 and _rows2:
            _dates2 = sorted(set(r.get("date", "") for r in _rows2), reverse=True)
            _latest2 = [r for r in _rows2 if r.get("date") == (_dates2[0] if _dates2 else None)]
            _CX_TYPES = ["PropertyAndPlantAndEquipment", "AcquisitionOfPropertyPlantAndEquipment"]
            _CX_NAMES = ["取得不動產、廠房及設備", "購置不動產、廠房及設備", "資本支出"]
            _cx2 = None
            for _row in _latest2:
                _t = str(_row.get("type", ""))
                if any(_ct in _t for _ct in _CX_TYPES):
                    _v = float(str(_row.get("value", 0)).replace(",", "") or 0)
                    if _v != 0:
                        _cx2 = abs(_v)
                        break
            if _cx2 is None:
                for _row in _latest2:
                    _n = str(_row.get("origin_name", ""))
                    if any(_k in _n for _k in _CX_NAMES):
                        _v = float(str(_row.get("value", 0)).replace(",", "") or 0)
                        if _v != 0:
                            _cx2 = abs(_v)
                            break
            if _cx2 and _cx2 > 0:
                _capex = _cx2
                cx_src_capex = "FinMind-CF"
                if cx is None:
                    cx = _capex
                    cx_src = "FinMind-CF"
                print(f"[FM-CF] ✅ 資本支出={_capex / 1e8:.2f}億")
    except Exception as _e_cf:
        fetch_errors.append(f"FinMind-CF:{type(_e_cf).__name__}:{_e_cf}")
        print(f"[FM-CF] ❌ {_e_cf}")

    def _fmt(v): return f"{v / 1e8:.1f}" if v else "-"
    print(f"[FIN] {sid}: cl={_fmt(cl)}億  cx={_fmt(cx)}億  capex={_fmt(_capex)}億")
    # v18.351 PR-Q1 S-PROV-1 phase 19:stderr 記 provenance(§2.2)。
    try:
        import sys as _sys_prov_fin
        _now_f = pd.Timestamp.now('UTC').isoformat()
        print(f'[fetch_financials] sid={sid} cl_src={cl_src or "-"} cx_src={cx_src or "-"} '
              f'capex_src={cx_src_capex or "-"} fetched_at={_now_f} '
              f'errors={len(fetch_errors)}',
              file=_sys_prov_fin.stderr)
    except Exception:
        pass
    return cl, cx, _capex, cl_src, cx_src, cx_src_capex, fetch_errors


@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_revenue(sid):
    """月營收(via StockDataLoader.get_monthly_revenue)。"""
    try:
        loader = _get_loader()
        result = loader.get_monthly_revenue(sid)
        if result is None:
            return None, '月營收:內部回傳None'
        # v18.351 PR-Q1 S-PROV-1 phase 19:DataFrame 走 attrs(schema-additive)
        _df_attr = result[0] if isinstance(result, tuple) else result
        try:
            if hasattr(_df_attr, 'attrs'):
                _df_attr.attrs.setdefault('source',
                    'app:fetch_revenue:data_loader.get_monthly_revenue')
                _df_attr.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        if isinstance(result, tuple):
            return result
        return result, None  # single value
    except Exception as e:
        print(f"[fetch_revenue] {e}")
        return None, str(e)


@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_quarterly(sid, _ver=4):  # _ver 改變即清除舊快取
    """季財報(via StockDataLoader.get_quarterly_data)。"""
    try:
        loader = _get_loader()
        result = loader.get_quarterly_data(sid)
        if result is None:
            return None, '季財報:內部回傳None'
        # v18.351 PR-Q1 S-PROV-1 phase 19:DataFrame 走 attrs(schema-additive)
        _df_attr_q = result[0] if isinstance(result, tuple) else result
        try:
            if hasattr(_df_attr_q, 'attrs'):
                _df_attr_q.attrs.setdefault('source',
                    'app:fetch_quarterly:data_loader.get_quarterly_data')
                _df_attr_q.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        print(f"[fetch_quarterly] {e}")
        return None, str(e)


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False, max_entries=10)
def fetch_quarterly_extra(sid, _ver=2):  # _ver 改變即清除舊快取
    """取得近 12 季資產負債表 + 現金流量時序(合約負債、存貨、資本支出),用於前瞻動能分數。"""
    try:
        loader = _get_loader()
        result = loader.get_quarterly_bs_cf(sid)
        if result is None:
            return None, 'BS/CF:內部回傳None'
        # v18.354 PR-Q4 S-PROV-1 phase 19:DataFrame 走 attrs(對齊 fetch_quarterly 模式)
        _df_attr_qe = result[0] if isinstance(result, tuple) else result
        try:
            if hasattr(_df_attr_qe, 'attrs'):
                _df_attr_qe.attrs.setdefault('source',
                    'app:fetch_quarterly_extra:data_loader.get_quarterly_bs_cf')
                _df_attr_qe.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        print(f"[fetch_quarterly_extra] {e}")
        return None, str(e)
