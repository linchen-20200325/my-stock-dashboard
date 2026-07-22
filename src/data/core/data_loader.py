# v19.84(第七份 review C2):移除 nest_* 事件迴圈補丁死 import — 全 repo 無任何
# 非同步程式碼消費此 patch(唯一效果是 import 期 monkey-patch event loop,0 使用者),
# 且原本就包 try/except pass(套件缺席時本來就 no-op),移除零行為差。
# (回歸網 test_review_fixes_v19_84 掃 src/ 守恆:未來引入非同步碼會被提醒重評)

import sys  # v18.241 D2: sys.stderr for imputation count logging
import yfinance as yf
import pandas as pd
import datetime
# v19.79:FinMind SDK 已自 requirements.txt 移除 — 其 1.x 全系列宣告
# pandas<2.0 / numpy<2.0 / lxml<5.0,與本 repo 核心 pin(pandas>=2 / lxml>=5.3)
# 硬衝突,雲端/CI 實際從未安裝成功(殭屍依賴)。try-import 保留:
# DataLoader=None 分支即長期實際運行路徑(raw HTTP + finmind_get);
# 若未來 FinMind 2.x 解除衝突可無痛復活。
try:
    from FinMind.data import DataLoader        # finmind < 1.x
except ImportError as _e_fm_cap:
    _fm_err_cap = str(_e_fm_cap)   # v19.79:保留第一段錯誤(原被第二段覆蓋,誤導診斷)
    try:
        from finmind.data import DataLoader    # finmind >= 1.x (小寫)
    except ImportError as _e:
        DataLoader = None
        import warnings
        warnings.warn(f"FinMind DataLoader 無法載入（raw HTTP API 仍可用）："
                      f"FinMind={_fm_err_cap} / finmind={_e}")
# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
# 本檔僅用 @st.cache_data / @st.cache_resource(S-H1 已刪 st.session_state 違憲)。
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
import threading as _th_dl
import requests as _req_dl
import urllib3 as _urllib3_dl
_urllib3_dl.disable_warnings(_urllib3_dl.exceptions.InsecureRequestWarning)
from src.data.proxy import fetch_url as _fetch_url_dl
from shared.roc_calendar import gregorian_to_roc_year  # B3 SSOT-H2:西元→民國
from src.data.core.finmind_client import _UA as _FM_UA  # S8 v19.78:raw REST UA 對齊 SSOT client
from shared.ttls import TTL_15MIN, TTL_1DAY, TTL_1HOUR, TTL_3DAY  # v19.105 補 TTL_3DAY(get_quarterly_data 快取)

# v18.201 D2：FinMind dataset 後台 update 時間追蹤
# raw fetcher 從 response top-level 取 `last_update`，SDK 路徑無此欄位故留空
# caller 在 attrs assign block 統一寫進 df.attrs，給 chip hover tooltip 用
_FINMIND_META: dict = {}   # key: 'price'/'inst'/'margin', value: {last_update, fetched_at}


def _capture_finmind_meta(src_key: str, j_response: dict) -> None:
    """v18.201 D2：把 FinMind response top-level last_update + 抓取 wallclock 存進 module dict。"""
    try:
        _FINMIND_META[src_key] = {
            "last_update": str(j_response.get("last_update", "") if isinstance(j_response, dict) else ""),
            "fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception:
        _FINMIND_META[src_key] = {"last_update": "", "fetched_at": ""}


def _stamp_finreport_attrs(df, src_key: str, src_val: str):
    """v18.202 E2：把財報資料源 + 抓取時戳寫進 df.attrs。

    鏡像 v18.200 B1（K線/籌碼/融資 src chip）+ v18.201 D2（hover tooltip）。
    財報三段 fetcher 回傳 (df, err) tuple 且過 @st.cache_data，但 pandas
    DataFrame.attrs 直接 pickle 可保留（app.py wrapper 未做 df 轉換），
    故在 data_loader 寫入即可，無需 app.py attrs.update（與 fetch_price_data
    走 .tail().reset_index() 掉 attrs 的情況不同）。
    """
    try:
        df.attrs[f"{src_key}_src"] = src_val
        df.attrs[f"{src_key}_fetched_at"] = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return df


# S7 v19.78:原 _bps_dl 每呼叫 new Session → TCP/TLS 連線池零複用(單股抓取
# price/inst/margin/月營收/BS-CF 連打多請求,每個都重建連線)。改 thread-local
# 單例:同執行緒共用連線池(urllib3 pool thread-safe;Retry adapter 隨
# build_proxy_session 掛好,status_forcelist 含 429);批次 ThreadPoolExecutor
# 各 worker 自持一份,不跨執行緒共享 Session 物件。
_TLS_BPS = _th_dl.local()


def _bps_dl():
    s = getattr(_TLS_BPS, 'session', None)
    if s is None:
        try:
            from src.data.stock import build_proxy_session as _b
            s = _b()
        except Exception:
            s = _req_dl.Session()
        s.verify = False
        _TLS_BPS.session = s
    return s


def _fm_raw_headers(token: str) -> dict:
    """FinMind raw REST 共用標頭(S8 v19.78)。

    原 7 處手刻呼叫只帶 Authorization、無 User-Agent(requests 預設
    `python-requests/x.x` 易被上游辨識限流);UA 對齊 finmind_client SSOT。
    """
    h = {'User-Agent': _FM_UA, 'Accept': 'application/json'}
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h

# N3 v19.80(第三份 review):_yf_dl 改寫「全域」os.environ — v19.77 批次
# ThreadPool(3) 並行進入後為真競態:worker A 的 finally 還原會在 worker B
# 下載進行中拔掉/覆寫 proxy env,晚進的 worker 備份到「已被同儕設定的值」
# 導致還原後 env 外洩。yfinance 1.5.1 無 proxy kwarg、set_config 亦為全域
# → 改「引用計數 + 鎖」:第一個進入者備份+設定、最後一個離開者還原,
# 期間 env 恆穩定(所有 worker 用同一 proxy 設定,下載本身仍並行)。
_YF_ENV_LOCK = _th_dl.Lock()
_YF_ENV_DEPTH = 0
_YF_ENV_BAK: dict = {}


def _yf_dl(symbol, **kwargs):
    """yfinance download，透過 os.environ 注入 proxy（相容新舊版 yfinance）。"""
    import os as _os_yfd
    global _YF_ENV_DEPTH, _YF_ENV_BAK
    try:
        from src.data.stock import _load_proxy_config as _lpc_yfd
        _px_url = ((_lpc_yfd() or {}).get('https') or (_lpc_yfd() or {}).get('http') or None)
    except Exception:
        _px_url = None
    _ek = ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy')
    if _px_url:
        with _YF_ENV_LOCK:
            _YF_ENV_DEPTH += 1
            if _YF_ENV_DEPTH == 1:   # 第一個進入者才備份+設定
                _YF_ENV_BAK = {k: _os_yfd.environ.get(k) for k in _ek}
                for k in _ek:
                    _os_yfd.environ[k] = _px_url
    kwargs.setdefault('timeout', HTTP_TIMEOUT_YF_SEC)  # S6 v19.78:顯式逾時(SSOT)
    try:
        return yf.download(symbol, **kwargs)
    finally:
        if _px_url:
            with _YF_ENV_LOCK:
                _YF_ENV_DEPTH -= 1
                if _YF_ENV_DEPTH == 0:   # 最後一個離開者才還原(N3 v19.80)
                    for k, v in _YF_ENV_BAK.items():
                        if v is None:
                            _os_yfd.environ.pop(k, None)
                        else:
                            _os_yfd.environ[k] = v
                    _YF_ENV_BAK = {}

# S7 v19.78:刪死碼 `_TWSE_DL = _bps_dl()`(全檔 0 使用,且會在 import 期建立
# 從未被複用的 session)。
from src.config import (  # Batch 10 v18.412; _FINMIND_TOKEN_CFG reads st.secrets at import time
    FINMIND_API_URL,
    FINMIND_TOKEN as _FINMIND_TOKEN_CFG,
    HTTP_TIMEOUT_FINMIND_SDK_SEC,
    HTTP_TIMEOUT_YF_SEC,
    get_stock_name,
)

# S-H1 v18.244:`safe_fetch_strict` 為死碼(grep 全 repo 唯一引用為定義本身),
# 已刪除以同時修復 §8.2「L1 不得用 st.session_state」違憲(原使用
# `st.session_state['success_cache']` 作為 session-level 緩存)。
# 若日後需要嚴格安全抓取框架,應在 L3 service 層實作,不再放 L1 fetcher。


_T86_DAY_CACHE: dict = {}  # {日期字串: {股票代碼: {外資,投信,自營商}}} 進程級快取，多股共用
# N2c v19.80(第三份 review):暫時性失敗(網路 None/例外)原本把 {} 永久釘進
# _T86_DAY_CACHE(無 TTL,進程不重啟不重試)→ 改短 TTL 負快取,來源恢復後可重試。
# 「stat != OK」(TWSE 明確回無資料,如假日)仍永久快取 — 該日資料永遠不會出現,語意正確。
_T86_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打


def _get_t86_day(ds: str) -> dict:
    """抓取 T86 特定日期的全市場法人資料，進程內快取避免重複請求。
    回傳 {股票代碼: {'外資':float, '投信':float, '自營商':float}}，單位：張"""
    if ds in _T86_DAY_CACHE:
        return _T86_DAY_CACHE[ds]
    import time as _t_t86
    _fts = _T86_FAIL_TS.get(ds)
    if _fts is not None and (_t_t86.time() - _fts) < TTL_15MIN:
        return {}   # 負快取生效中(短 TTL),不重打
    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    try:
        r = _fetch_url_dl('https://www.twse.com.tw/fund/T86',
                          params={'response': 'json', 'date': ds, 'selectType': 'ALL'},
                          headers=HDR, timeout=5)
        if r is None:
            _T86_FAIL_TS[ds] = _t_t86.time()   # N2c:暫時性 → 負快取,不永久釘
            return {}
        j = r.json()
        if j.get('stat') != 'OK' or not j.get('data'):
            _T86_DAY_CACHE[ds] = {}
            return {}
        fields = [str(f) for f in j.get('fields', [])]
        fi = {n: i for i, n in enumerate(fields)}
        # T86 欄位名稱用「買賣超」而非「淨」，例如「外陸資買賣超股數」「投信買賣超股數」
        f_idx = next((v for k, v in fi.items() if '外' in k and '買賣超' in k and '自營' not in k), None)
        t_idx = next((v for k, v in fi.items() if '投信' in k and '買賣超' in k), None)
        d_idx = next((v for k, v in fi.items() if '自營' in k and '買賣超' in k and '自行' in k), None)
        print(f'[T86] {ds} fields={fields[:5]} f_idx={f_idx} t_idx={t_idx} d_idx={d_idx}')

        def _pn(row, idx):
            if idx is None or idx >= len(row): return 0.0
            try: return round(int(str(row[idx]).replace(',', '').replace('+', '') or 0) / 1000, 1)
            # v19.82:裸 except 收窄(§3.3);髒儲存格 → 0.0 為既有 fail-token 語意
            except (ValueError, TypeError): return 0.0

        day_data = {}
        for row in j['data']:
            code = str(row[0]).strip()
            if code:
                day_data[code] = {'外資': _pn(row, f_idx), '投信': _pn(row, t_idx), '自營商': _pn(row, d_idx)}
        _T86_DAY_CACHE[ds] = day_data
        print(f'[TWSE T86] {ds}: {len(day_data)} 支')
        return day_data
    except Exception as e:
        print(f'[TWSE T86] {ds} 失敗: {e}')
        import time as _t_t86e
        _T86_FAIL_TS[ds] = _t_t86e.time()   # N2c:暫時性 → 負快取,不永久釘
        return {}


def _fetch_twse_inst_fallback(stock_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """TWSE T86 備援：T86 一次抓全市場，多股共用同一份進程快取，不重複發請求。"""
    try:
        rows = []
        base = datetime.date.today()
        checked = 0
        for delta in range(20):
            if checked >= 10: break
            d = base - datetime.timedelta(days=delta)
            if d.weekday() >= 5: continue
            day = _get_t86_day(d.strftime('%Y%m%d'))
            checked += 1
            if stock_id in day:
                rows.append({'date': d, **day[stock_id]})
        if rows:
            _df_tw = pd.DataFrame(rows)
            _df_tw['主力合計'] = _df_tw['外資'] + _df_tw['投信'] + _df_tw['自營商']
            df = pd.merge(df, _df_tw, on='date', how='left')
            print(f'[TWSE T86] {stock_id} 補充 {len(rows)} 日')
    except Exception as e:
        print(f'[TWSE T86] {stock_id} 失敗: {e}')
    # v18.356 PR-Q5b S-PROV-1 phase 19:DataFrame 走 attrs
    try:
        if hasattr(df, 'attrs'):
            df.attrs.setdefault('source', 'src.data.core.data_loader._fetch_twse_inst_fallback:TWSE T86')
            df.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
    except Exception:
        pass
    return df


_TPEX_DAY_CACHE: dict = {}  # {日期字串: {股票代碼: {外資,投信,自營商}}} TPEx 進程級快取


def _get_tpex_day(ds: str) -> dict:
    """抓取 TPEx 特定日期的全市場法人資料（上櫃股），進程內快取。
    回傳 {股票代碼: {'外資':float, '投信':float, '自營商':float}}，單位：張"""
    if ds in _TPEX_DAY_CACHE:
        return _TPEX_DAY_CACHE[ds]
    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*',
           'Referer': 'https://www.tpex.org.tw/'}
    try:
        dt = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
        roc_year = gregorian_to_roc_year(dt.year)
        roc_date = f'{roc_year}/{dt.month:02d}/{dt.day:02d}'
        r = _fetch_url_dl(
            'https://www.tpex.org.tw/web/stock/3insti/daily_report/3itrade_hedge_result.php',
            params={'l': 'zh-tw', 'se': 'EW', 't': 'D', 'd': roc_date, 'o': 'json'},
            headers=HDR, timeout=5)
        if r is None:
            _TPEX_DAY_CACHE[ds] = {}
            return {}
        j = r.json()
        rows_data = j.get('aaData', [])
        if not rows_data:
            _TPEX_DAY_CACHE[ds] = {}
            return {}

        def _pn_tp(row, idx):
            if idx is None or idx >= len(row): return 0.0
            try: return round(int(str(row[idx]).replace(',', '').replace('+', '') or 0) / 1000, 1)
            # v19.82:裸 except 收窄(§3.3);髒儲存格 → 0.0 為既有 fail-token 語意
            except (ValueError, TypeError): return 0.0

        def _int_tp(row, idx):
            try: return int(str(row[idx]).replace(',', '').replace('+', '') or 0)
            # v19.82:裸 except 收窄(§3.3);此 helper 無 idx 前置守衛,補 IndexError
            except (ValueError, TypeError, IndexError): return 0

        # ── 動態偵測欄位索引（sColumns 或 buy-sell-net 驗證）──────────
        # TPEx 標準格式：[0]代號 [1]名稱
        # 外資 [2]買 [3]賣 [4]淨  投信 [5]買 [6]賣 [7]淨
        # 自營(自行) [8]買 [9]賣 [10]淨  [11..13]避險  [14]合計
        f_idx, t_idx, d_idx = 4, 7, 10  # 預設索引

        # 用第一筆有效資料驗證 buy - sell ≈ net（容許 1 張以內誤差）
        for _sample in rows_data[:5]:
            if len(_sample) < 11: continue
            _f_buy = _int_tp(_sample, 2); _f_sell = _int_tp(_sample, 3); _f_net = _int_tp(_sample, 4)
            _t_buy = _int_tp(_sample, 5); _t_sell = _int_tp(_sample, 6); _t_net = _int_tp(_sample, 7)
            if abs(_f_net - (_f_buy - _f_sell)) <= 1000 and abs(_t_net - (_t_buy - _t_sell)) <= 1000:
                break  # 驗證通過，使用預設索引
        else:
            # 若驗證全失敗，嘗試欄位較少的格式（部分 TPEx API 版本省略避險欄）
            # [0]代號 [1]名稱 [2]外買 [3]外賣 [4]外淨 [5]投買 [6]投賣 [7]投淨 [8]自買 [9]自賣 [10]自淨
            print(f'[TPEx] {ds} 欄位驗證失敗，row長度={len(rows_data[0]) if rows_data else 0}，使用預設索引')

        day_data = {}
        for row in rows_data:
            code = str(row[0]).strip()
            if not code or len(row) < 11: continue
            day_data[code] = {
                '外資': _pn_tp(row, f_idx),
                '投信': _pn_tp(row, t_idx),
                '自營商': _pn_tp(row, d_idx),
            }
        _TPEX_DAY_CACHE[ds] = day_data
        print(f'[TPEx] {ds} ({roc_date}): {len(day_data)} 支 idx=({f_idx},{t_idx},{d_idx})')
        return day_data
    except Exception as e:
        print(f'[TPEx] {ds} 失敗: {e}')
        _TPEX_DAY_CACHE[ds] = {}
        return {}


def _fetch_tpex_inst_fallback(stock_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """TPEx 上櫃股法人備援，邏輯同 TWSE T86，使用 TPEx 三大法人 API。"""
    try:
        rows = []
        base = datetime.date.today()
        checked = 0
        for delta in range(20):
            if checked >= 10: break
            d = base - datetime.timedelta(days=delta)
            if d.weekday() >= 5: continue
            day = _get_tpex_day(d.strftime('%Y%m%d'))
            checked += 1
            if stock_id in day:
                rows.append({'date': d, **day[stock_id]})
        if rows:
            _df_tp = pd.DataFrame(rows)
            _df_tp['主力合計'] = _df_tp['外資'] + _df_tp['投信'] + _df_tp['自營商']
            df = pd.merge(df, _df_tp, on='date', how='left')
            print(f'[TPEx] {stock_id} 補充 {len(rows)} 日')
    except Exception as e:
        print(f'[TPEx] {stock_id} 失敗: {e}')
    # v18.356 PR-Q5b S-PROV-1 phase 19:DataFrame 走 attrs
    try:
        if hasattr(df, 'attrs'):
            df.attrs.setdefault('source', 'src.data.core.data_loader._fetch_tpex_inst_fallback:TPEx 三大法人')
            df.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
    except Exception:
        pass
    return df


def _normalize_inst_pivot(df_raw: pd.DataFrame) -> pd.DataFrame:
    """把 FinMind/T86 原始法人 DataFrame 轉成含 外資/投信/自營商/主力合計 欄位的 pivot。
    df_raw 必須有 date / name / buy / sell 欄位，單位為股。"""
    import re as _re_ni
    df_raw = df_raw.copy()
    # v18.241 D1 (CLAUDE.md §1 Fail Loud) 刻意取捨註記：
    # fillna(0) before subtract = 「缺值 buy / sell 視為 0 股」，與 FinMind T86 在無交易日的語意一致
    # (T86 不含週末/休市日，剩餘缺值多為個別法人未提交)。直接 raise 會中斷整 pivot，
    # ROI 不如未來改 contract: 回傳含 `is_imputed` 旗標 DataFrame，由 caller 選擇是否容忍。
    # 受影響筆數通常 < 1%，當前風險可接受；列入 §8.2.A future enhancement。
    df_raw['net_buy'] = (pd.to_numeric(df_raw['buy'],  errors='coerce').fillna(0) -
                         pd.to_numeric(df_raw['sell'], errors='coerce').fillna(0))
    df_raw['date'] = pd.to_datetime(df_raw['date']).dt.date
    pv = df_raw.pivot_table(index='date', columns='name', values='net_buy',
                             aggfunc='sum').reset_index()
    # 股→張
    for c in pv.columns:
        if c != 'date':
            pv[c] = pv[c] / 1000
    # 重命名：支援英文（Foreign_Investor）與中文（外陸資…）
    # 注意：外資自營商 屬外資陣營，應歸入「外資」而非「自營商」
    rn = {}
    for c in pv.columns:
        cs = str(c); cl = cs.lower()
        cb = _re_ni.split(r'[（(買賣]', cs)[0].strip()
        if ('外' in cs and '資' in cs) or cs in ('外資', '外陸資', '外資及陸資'):
            rn[c] = '外資'          # 外陸資(不含外資自營商) + 外資自營商 → 均歸外資
        elif '投信' in cb:
            rn[c] = '投信'
        elif '自營' in cb and '外資' not in cs:  # 純國內自營商
            rn[c] = '自營商'
        elif 'foreign' in cl:
            rn[c] = '外資'          # 英文名稱（含 dealer）
        elif 'investment' in cl or 'trust' in cl:
            rn[c] = '投信'
        elif 'dealer' in cl:
            rn[c] = '自營商'
    print(f'[INST-RENAME] 欄位對應: {rn}')
    pv.rename(columns=rn, inplace=True)
    # 重複欄合併（pandas 3.0 相容）
    if pv.columns.duplicated().any():
        _dp = pv[['date']]
        _np = pv.drop(columns=['date'])
        _np = _np.T.groupby(level=0).sum().T
        pv = pd.concat([_dp, _np], axis=1)
    main = [c for c in ['外資', '投信', '自營商'] if c in pv.columns]
    if main:
        pv['主力合計'] = pv[main].sum(axis=1)
    return pv


def _fetch_finmind_margin_raw(stock_id: str, df: pd.DataFrame, start_str: str) -> tuple:
    """FinMind 原始 API 備援 — 個股融資融券（TaiwanStockMarginPurchaseShortSale）。

    SDK 失敗時的 fallback，邏輯對齊 _fetch_finmind_inst_raw。
    回傳 (df, src_label)：df 已 merge 融資/融券欄位；src_label='finmind_raw' 或 'missing'。
    """
    import os
    # _FINMIND_TOKEN_CFG 在 module load 時從 st.secrets 讀取；os.environ 作為 fallback
    # （Streamlit Cloud 的 secrets 不會自動寫入 os.environ，必須明確讀取）
    _token = _FINMIND_TOKEN_CFG or os.environ.get('FINMIND_TOKEN', '')
    _end_str = datetime.date.today().strftime('%Y-%m-%d')
    try:
        _params = {
            'dataset': 'TaiwanStockMarginPurchaseShortSale',
            'data_id': stock_id,
            'start_date': start_str,
            'end_date': _end_str,
        }
        if _token:
            _params['token'] = _token
        _r = _bps_dl().get(
            FINMIND_API_URL,
            params=_params,
            headers=_fm_raw_headers(_token),   # S8 v19.78:補 UA
            timeout=20,
        )
        _j = _r.json()
        _capture_finmind_meta('margin', _j)
        if _j.get('status') == 200 and _j.get('data'):
            _df_m = pd.DataFrame(_j['data'])
            _df_m['date'] = pd.to_datetime(_df_m['date']).dt.date
            if 'MarginPurchaseTodayBalance' in _df_m.columns:
                _df_m = _df_m[['date', 'MarginPurchaseTodayBalance', 'ShortSaleTodayBalance']].copy()
                _df_m.rename(columns={
                    'MarginPurchaseTodayBalance': '融資餘額',
                    'ShortSaleTodayBalance': '融券餘額',
                }, inplace=True)
                _df_m['融資餘額'] = pd.to_numeric(_df_m['融資餘額'], errors='coerce')
                _df_m['融券餘額'] = pd.to_numeric(_df_m['融券餘額'], errors='coerce')
                df['date'] = pd.to_datetime(df['date']).dt.date
                df = pd.merge(df, _df_m, on='date', how='left')
                _nz = (df.get('融資餘額', pd.Series(dtype=float)) != 0).sum()
                print(f'[FM-Raw margin] {stock_id}: ✅ {len(_j["data"])} 筆 融資非零={_nz}')
                return df, 'finmind_raw'
            print(f'[FM-Raw margin] {stock_id}: 找不到 MarginPurchaseTodayBalance, '
                  f'cols={list(_df_m.columns)[:8]}')
        else:
            print(f'[FM-Raw margin] {stock_id}: status={_j.get("status")} msg={_j.get("msg", "")}')
    except Exception as _e:
        print(f'[FM-Raw margin] {stock_id}: ❌ {_e}')
    return df, 'missing'


def _fetch_finmind_inst_raw(stock_id: str, df: pd.DataFrame, start_str: str) -> pd.DataFrame:
    """FinMind 原始 API 備援（不依賴 Python SDK）
    - 有 FINMIND_TOKEN: 使用 token 提高速率限制
    - 無 token: 匿名請求（FinMind 公開資料，限速 3 req/min，仍可取得）
    """
    import os
    _token = _FINMIND_TOKEN_CFG or os.environ.get('FINMIND_TOKEN', '')
    _end_str = datetime.date.today().strftime('%Y-%m-%d')
    try:
        _params = {'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
                   'data_id': stock_id, 'start_date': start_str, 'end_date': _end_str}
        if _token:
            _params['token'] = _token
        _r = _bps_dl().get(
            FINMIND_API_URL,
            params=_params,
            headers=_fm_raw_headers(_token),   # S8 v19.78:補 UA
            timeout=20)
        _j = _r.json()
        _capture_finmind_meta('inst', _j)   # v18.201 D2：紀錄 last_update + fetched_at
        if _j.get('data'):
            _first = _j['data'][0]
            _names = list(set(r.get('name','') for r in _j['data'][:20]))
        if _j.get('status') == 200 and _j.get('data'):
            _pv = _normalize_inst_pivot(pd.DataFrame(_j['data']))
            # 確保兩側 date 型別一致再 merge
            _pv['date'] = pd.to_datetime(_pv['date']).dt.date
            df['date']  = pd.to_datetime(df['date']).dt.date
            _df_dates   = set(df['date'])
            _pv_dates   = set(_pv['date'])
            _overlap    = len(_df_dates & _pv_dates)
            df = pd.merge(df, _pv, on='date', how='left')
            _nz = (df.get('外資', pd.Series(dtype=float)) != 0).sum()
            print(f'[FM-Raw] {stock_id}: ✅ {len(_j["data"])} 筆 → {len(_pv)} 日  外資非零={_nz}')
        else:
            print(f'[FM-Raw] {stock_id}: status={_j.get("status")} msg={_j.get("msg","")}')
    except Exception as _e:
        print(f'[FM-Raw] {stock_id}: ❌ {_e}')
    return df


def _fetch_finmind_price_raw(stock_id: str, start_str: str, end_str: str) -> pd.DataFrame:
    """FinMind 原始 API 取個股日K（不依賴 Python SDK），供 DataLoader=None 時備援。

    回傳與 dl.taiwan_stock_daily 相同的原生欄位（date/open/max/min/close/Trading_Volume…），
    呼叫端沿用既有 rename 與單位處理；失敗回空 DataFrame。
    """
    import os
    _token = _FINMIND_TOKEN_CFG or os.environ.get('FINMIND_TOKEN', '')
    try:
        _params = {'dataset': 'TaiwanStockPrice', 'data_id': stock_id,
                   'start_date': start_str, 'end_date': end_str}
        if _token:
            _params['token'] = _token
        _r = _bps_dl().get(
            FINMIND_API_URL,
            params=_params,
            headers=_fm_raw_headers(_token),   # S8 v19.78:補 UA
            timeout=20)
        _j = _r.json()
        _capture_finmind_meta('price', _j)   # v18.201 D2：紀錄 last_update + fetched_at
        if _j.get('status') == 200 and _j.get('data'):
            print(f'[FM-Raw price] {stock_id}: ✅ {len(_j["data"])} 筆（SDK 未載入，走 HTTP 備援）')
            _df_out = pd.DataFrame(_j['data'])
            # S-PROV-1 phase 15 v18.261 — provenance(schema-additive)
            if not _df_out.empty:
                _df_out['source'] = 'FinMind:TaiwanStockPrice:raw_http'
                _df_out['fetched_at'] = pd.Timestamp.now('UTC').isoformat()
            return _df_out
        print(f'[FM-Raw price] {stock_id}: status={_j.get("status")} msg={_j.get("msg","")}')
    except Exception as _e:
        print(f'[FM-Raw price] {stock_id}: ❌ {_e}')
    return pd.DataFrame()


# 版本鍵：改動 StockDataLoader 邏輯時 bump 此字串，供 app._get_loader 作為
# @st.cache_resource 的 cache key。避免線上 hot-reload 後仍用到舊實例的舊方法碼
# （PR #44 修了 NoneType 但 cache_resource 舊實例殘留 → 仍崩，即此故）。
_LOADER_VERSION = 'v3-no-negative-cache'  # N2a v19.80:bump 讓 @st.cache_resource loader 換新


class _CombinedDataError(Exception):
    """get_combined_data 暫時性失敗訊號(N2a v19.80)。

    st.cache_data 只快取「回傳值」、對 raise 不快取 — 原本 except 分支
    `return None, err, None` 會被快取整整 TTL_1HOUR:一次 FinMind 限速/網路
    抖動 → 該股接下來 1 小時持續回 None(即使來源已恢復)。改為 cached 內層
    raise、public wrapper 攔截還原成 (None, err, None) 3-tuple — caller 介面
    0 改變,但失敗結果不再進快取。「查無資料」類的確定性負結果仍走 return
    (快取合理:重打也不會變出資料)。
    """


class StockDataLoader:
    """台股數據引擎 - FinMind 優先，Yahoo 備援"""

    def __init__(self):
        import os
        self.dl = DataLoader() if DataLoader is not None else None  # [Fixed] DataLoader 未安裝時不崩潰
        # _FINMIND_TOKEN_CFG: st.secrets 優先（Streamlit Cloud secrets ≠ os.environ）
        _fm_token    = _FINMIND_TOKEN_CFG or os.environ.get('FINMIND_TOKEN', '')
        _fm_user     = os.environ.get('FINMIND_USER', '')
        _fm_password = os.environ.get('FINMIND_PASSWORD', '')
        try:
            if self.dl is None:
                print('[FinMind] ⚠️  SDK 未載入（DataLoader=None），改用 raw HTTP API 備援')
                self._token = _fm_token
            elif _fm_token:
                self.dl.login_by_token(api_token=_fm_token)
                # v19.83(第六份 review P2-17):不再印 token 前綴片段 — 憑證材料
                # 不入 log(Cloud console log 可見);只印長度供診斷「有沒有讀到」。
                print(f'[FinMind] ✅ Token 登入成功（len={len(_fm_token)}）')
                self._token = _fm_token
            elif _fm_user and _fm_password:
                self.dl.login(user_id=_fm_user, password=_fm_password)
                print('[FinMind] ✅ 帳號登入成功')
                self._token = ''
            else:
                print('[FinMind] ℹ️  匿名模式（每小時600次）')
                self._token = ''
        except Exception as e:
            print(f'[FinMind] ⚠️  登入失敗：{e}')
            self._token = _fm_token  # 保留 token 供 raw HTTP 備援使用

    # v19.74 review:max_entries=64 — 以 stock_id 為鍵逐檔堆積,LRU 回收控記憶體上界
    # (Streamlit Cloud ~1GB,連續瀏覽數百檔無上界會膨脹到 OOM 重啟)。
    def get_combined_data(self, stock_id, days, use_adjusted=True):
        """完整數據載入流程(public wrapper,N2a v19.80)。

        暫時性失敗(內層 raise _CombinedDataError)在此還原為 (None, err, None),
        **不進 st.cache_data** — 修「一次暫時性失敗被快取 1 小時」。
        成功與確定性負結果(查無資料)仍由內層快取。
        """
        try:
            return self._get_combined_data_cached(stock_id, days, use_adjusted)
        except _CombinedDataError as _e_gcd:
            return None, str(_e_gcd), None

    @st.cache_data(ttl=TTL_1HOUR, max_entries=64)
    def _get_combined_data_cached(_self, stock_id, days, use_adjusted=True):
        """完整數據載入流程

        Args:
            stock_id: 股票代碼
            days: 載入天數
            use_adjusted: True=還原K線(復權,預設), False=一般K線
        """
        try:
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=days + 150)
            start_str = start_date.strftime('%Y-%m-%d')

            # ========== 1. 股價數據 ==========

            df = None
            _price_src = 'unknown'
            _inst_src = 'unknown'
            _margin_src = 'unknown'

            # 還原K線(復權)：優先直接用 Yahoo auto_adjust=True 生成「已復權 OHLC」
            if use_adjusted:
                try:
                    yf_symbol = f"{stock_id}.TW"
                    df_yf_adj = _yf_dl(
                        yf_symbol,
                        start=start_date,
                        end=end_date + datetime.timedelta(days=1),
                        auto_adjust=True,
                        progress=False
                    )
                    # 若 .TW 查無資料，嘗試 .TWO（上櫃股票）
                    if df_yf_adj.empty:
                        yf_symbol = f"{stock_id}.TWO"
                        df_yf_adj = _yf_dl(
                            yf_symbol,
                            start=start_date,
                            end=end_date + datetime.timedelta(days=1),
                            auto_adjust=True,
                            progress=False
                        )
                    if not df_yf_adj.empty:
                        df_yf_adj = df_yf_adj.reset_index()

                        # 處理 MultiIndex
                        if isinstance(df_yf_adj.columns, pd.MultiIndex):
                            df_yf_adj.columns = df_yf_adj.columns.get_level_values(0)

                        df_yf_adj.columns = [str(c).lower() for c in df_yf_adj.columns]

                        # reset_index 後通常是 date 欄位
                        if 'date' not in df_yf_adj.columns and 'datetime' in df_yf_adj.columns:
                            df_yf_adj = df_yf_adj.rename(columns={'datetime': 'date'})

                        df_yf_adj['date'] = pd.to_datetime(df_yf_adj['date']).dt.date

                        # 成交量：股 -> 張
                        if 'volume' in df_yf_adj.columns:
                            # v19.81 review A:Yahoo 停牌/無量日 volume 可為 NaN,
                            # astype(int) 直接 IntCastingNaNError 炸整條 K 線。
                            # §1 顯式填補 + log:NaN→0(§4.6 跌停 0 vol=有效報價語意)
                            _vol_na = int(df_yf_adj['volume'].isna().sum())
                            if _vol_na:
                                print(f"[K線] {stock_id} Yahoo(adj) volume NaN {_vol_na} 筆 → 填 0(§4.6 無量日)")
                            df_yf_adj['volume'] = (df_yf_adj['volume'].fillna(0) / 1000).round().astype(int)
                        else:
                            df_yf_adj['volume'] = 0

                        df = df_yf_adj[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
                        _price_src = 'yahoo_adj'
                        print("✅ 還原K線：Yahoo auto_adjust=True（直接生成還原 OHLC）")
                except Exception as e:
                    print(f"⚠️ 還原K線：Yahoo auto_adjust 失敗，改用 FinMind 原始價：{e}")
                    df = None

            # 若未使用還原K線或 Yahoo 失敗，則走 FinMind（一般K線 / 備援）
            if df is None:
                if _self.dl is not None:
                    df_price = _self.dl.taiwan_stock_daily(
                        stock_id=stock_id,
                        start_date=start_str,
                        end_date=end_date.strftime('%Y-%m-%d'),
                        timeout=HTTP_TIMEOUT_FINMIND_SDK_SEC,  # S6 v19.78:SDK 預設 None=無限等待
                    )
                    _fm_path = 'finmind_sdk'
                    _capture_finmind_meta('price', {})   # v18.201 D2：SDK 無 response → 只記 fetched_at
                else:
                    # FinMind SDK 未載入（DataLoader=None）→ raw HTTP 備援，避免 NoneType 崩潰
                    df_price = _fetch_finmind_price_raw(
                        stock_id, start_str, end_date.strftime('%Y-%m-%d'))
                    _fm_path = 'finmind_raw'

                if df_price.empty:
                    # Yahoo 備援（先 .TW，再試 .TWO 上櫃）
                    yf_symbol = f"{stock_id}.TW"
                    df_yf = _yf_dl(yf_symbol, start=start_date, progress=False)
                    if df_yf.empty:
                        yf_symbol = f"{stock_id}.TWO"
                        df_yf = _yf_dl(yf_symbol, start=start_date, progress=False)
                    if df_yf.empty:
                        return None, "❌ 查無資料", None

                    df_yf = df_yf.reset_index()

                    # ========== 先處理復權（在轉小寫之前）==========
                    has_adj = False
                    adj_ratio_values = None
                    if isinstance(df_yf.columns, pd.MultiIndex):
                        df_yf.columns = df_yf.columns.get_level_values(0)

                    # 檢查並計算復權比例（先儲存起來）
                    if 'Adj Close' in df_yf.columns and 'Close' in df_yf.columns and use_adjusted:
                        adj_ratio_values = (df_yf['Adj Close'] / df_yf['Close']).values
                        adj_close_values = df_yf['Adj Close'].values
                        has_adj = True
                        print("✅ Yahoo 備援：使用復權資料")

                    # 轉小寫
                    df_yf.columns = [str(c).lower() for c in df_yf.columns]
                    df_yf['date'] = pd.to_datetime(df_yf['date']).dt.date

                    # 應用復權
                    if has_adj and use_adjusted and adj_ratio_values is not None:
                        df_yf['open'] = df_yf['open'] * adj_ratio_values
                        df_yf['high'] = df_yf['high'] * adj_ratio_values
                        df_yf['low'] = df_yf['low'] * adj_ratio_values
                        df_yf['close'] = adj_close_values

                    # v19.81 review A:同上,Yahoo 備援路徑 NaN volume 防炸(§1 顯式填補 + log)
                    _vol_na = int(df_yf['volume'].isna().sum())
                    if _vol_na:
                        print(f"[K線] {stock_id} Yahoo(備援) volume NaN {_vol_na} 筆 → 填 0(§4.6 無量日)")
                    df_yf['volume'] = (df_yf['volume'].fillna(0) / 1000).round().astype(int)
                    df = df_yf[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
                    _price_src = 'yahoo_fallback'
                else:
                    # FinMind 數據
                    _price_src = _fm_path
                    df = df_price.rename(columns={
                        'Trading_Volume': 'volume',
                        'max': 'high',
                        'min': 'low'
                    })[['date', 'open', 'high', 'low', 'close', 'volume']].copy()

                    df['date'] = pd.to_datetime(df['date']).dt.date
                    # v19.81 review A:FinMind 路徑同樣 NaN volume 防炸(§1 顯式填補 + log)。
                    # 保留原 astype(int) 截斷語意(不補 .round(),避免既有值位移)。
                    _vol_na = int(df['volume'].isna().sum())
                    if _vol_na:
                        print(f"[K線] {stock_id} FinMind volume NaN {_vol_na} 筆 → 填 0(§4.6 無量日)")
                    df['volume'] = (df['volume'].fillna(0) / 1000).astype(int)

                    # ========== 復權處理（從 Yahoo 獲取）==========
                    if use_adjusted:
                        try:
                            yf_symbol = f"{stock_id}.TW"
                            df_adj = _yf_dl(yf_symbol, start=start_date, progress=False)

                            if not df_adj.empty:
                                df_adj = df_adj.reset_index()

                                # 處理 MultiIndex
                                if isinstance(df_adj.columns, pd.MultiIndex):
                                    df_adj.columns = df_adj.columns.get_level_values(0)

                                # 計算復權比例
                                if 'Adj Close' in df_adj.columns and 'Close' in df_adj.columns:
                                    df_adj['date_key'] = pd.to_datetime(df_adj['Date']).dt.date
                                    df_adj['adj_ratio'] = df_adj['Adj Close'] / df_adj['Close']

                                    # 合併復權比例
                                    df = df.merge(df_adj[['date_key', 'adj_ratio']],
                                                  left_on='date', right_on='date_key', how='left')

                                    # 填補缺失值為 1.0（不調整）
                                    df['adj_ratio'] = df['adj_ratio'].fillna(1.0)

                                    # 應用復權到所有價格
                                    df['open'] = df['open'] * df['adj_ratio']
                                    df['high'] = df['high'] * df['adj_ratio']
                                    df['low'] = df['low'] * df['adj_ratio']
                                    df['close'] = df['close'] * df['adj_ratio']

                                    # 清理欄位
                                    df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
                                    print("✅ FinMind：復權成功")
                                else:
                                    print("⚠️ Yahoo 無 Adj Close，使用原始價格")
                            else:
                                print("⚠️ Yahoo 無資料，使用原始價格")
                        except Exception as e:
                            print(f"⚠️ 復權失敗: {e}")
                            # 失敗時確保 df 只有基本欄位
                            df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()

            # ========== 2. 股票名稱 ==========

            stock_name = stock_id
            try:
                stock_info = _self.dl.taiwan_stock_info()
                if not stock_info.empty:
                    match = stock_info[stock_info['stock_id'] == stock_id]
                    if not match.empty:
                        stock_name = match.iloc[0]['stock_name']
            except Exception as _e_si:
                # v18.343 PR-M1 S-MED:bare except → typed + stderr。FinMind SDK
                # taiwan_stock_info 偶爾 quota/timeout/empty,原 silent pass 下游 fallback
                # 到 get_stock_name(L621),功能不變,僅補軌跡讓 quota 問題立刻可見。
                print(f'[_fetch_stock_name_inner] swallow ({stock_id}): '
                      f'{type(_e_si).__name__}: {_e_si}', file=sys.stderr)

            if stock_name == stock_id:
                stock_name = get_stock_name(stock_id)

            # ========== 3. 均線 ==========
            for period in [5, 10, 20, 60, 100, 120, 240]:
                df[f'MA{period}'] = df['close'].rolling(window=period).mean()

            # ========== 4. 三大法人 ==========
            if _self.dl is not None:
                try:
                    df_inst = _self.dl.taiwan_stock_institutional_investors(
                        stock_id=stock_id,
                        start_date=start_str,
                        timeout=HTTP_TIMEOUT_FINMIND_SDK_SEC,  # S6 v19.78
                    )
                    _sdk_ok = (df_inst is not None and
                               hasattr(df_inst, 'empty') and
                               not df_inst.empty)
                    if _sdk_ok:
                        df_pivot = _normalize_inst_pivot(df_inst)
                        df_pivot['date'] = pd.to_datetime(df_pivot['date']).dt.date
                        df['date']       = pd.to_datetime(df['date']).dt.date
                        _overlap = len(set(df['date']) & set(df_pivot['date']))
                        df = pd.merge(df, df_pivot, on='date', how='left')
                        _nz = (df.get('外資', pd.Series(dtype=float)) != 0).sum()
                        print(f'[籌碼] {stock_id}: SDK ✅ 外資非零={_nz}', flush=True)
                        _sdk_used = True
                        _inst_src = 'finmind_sdk'
                        _capture_finmind_meta('inst', {})   # v18.201 D2
                    else:
                        _sdk_used = False
                except Exception as _e_sdk:
                    # v19.105 §3.3:原靜默吞 → 補 log(仍走 raw fallback,行為不變)
                    print(f'[法人] FinMind SDK 路徑失敗,改走 raw:{type(_e_sdk).__name__}: {_e_sdk}')
                    _sdk_used = False
            else:
                _sdk_used = False

            if not _sdk_used:
                # SDK 不可用 → FinMind Raw HTTP API（不依賴 SDK）
                df = _fetch_finmind_inst_raw(stock_id, df, start_str)
                if '外資' in df.columns:
                    _inst_src = 'finmind_raw'
                if '外資' not in df.columns:
                    df = _fetch_twse_inst_fallback(stock_id, df)
                    if '外資' in df.columns:
                        _inst_src = 'twse'
                if '外資' not in df.columns:
                    df = _fetch_tpex_inst_fallback(stock_id, df)
                    if '外資' in df.columns:
                        _inst_src = 'tpex'
                if _inst_src == 'unknown':
                    _inst_src = 'missing'

            # ========== 5. 融資融券 ==========
            _margin_sdk_ok = False
            if _self.dl is not None:
                try:
                    df_margin = _self.dl.taiwan_stock_margin_purchase_short_sale(
                        stock_id=stock_id,
                        start_date=start_str,
                        timeout=HTTP_TIMEOUT_FINMIND_SDK_SEC,  # S6 v19.78
                    )
                    if not df_margin.empty:
                        df_margin['date'] = pd.to_datetime(df_margin['date']).dt.date
                        margin_data = df_margin[['date', 'MarginPurchaseTodayBalance',
                                                 'ShortSaleTodayBalance']].copy()
                        margin_data.rename(columns={
                            'MarginPurchaseTodayBalance': '融資餘額',
                            'ShortSaleTodayBalance': '融券餘額'
                        }, inplace=True)
                        margin_data['融資餘額'] = pd.to_numeric(margin_data['融資餘額'], errors='coerce')
                        margin_data['融券餘額'] = pd.to_numeric(margin_data['融券餘額'], errors='coerce')
                        df = pd.merge(df, margin_data, on='date', how='left')
                        _margin_src = 'finmind_sdk'
                        _capture_finmind_meta('margin', {})
                        _margin_sdk_ok = True
                except Exception as e:
                    print(f"融資數據 SDK 錯誤: {e}")
            if not _margin_sdk_ok:
                # SDK 不可用 / 無資料 → FinMind Raw HTTP API 備援（對齊 inst 降級邏輯）
                df, _margin_src = _fetch_finmind_margin_raw(stock_id, df, start_str)

            # ========== 6. 數據清洗 ==========
            # v18.241 D2 (CLAUDE.md §1 Fail Loud) 刻意取捨 + 可視化：
            # fillna(0) 保留以維持下游 scoring/strategy 數值穩定，但統計受影響筆數寫 stderr
            # 讓「靜默填補」變成「可觀測填補」。未來理想做法：caller 取 is_imputed DataFrame
            # 旗標 → 由策略層自決是否容忍缺值（見 §8.2.A future enhancement）
            #
            # v18.349 PR-O1 SSOT 對齊註記:
            # - 外資 / 投信 / 自營商 / 主力合計 單位 = **張**(SSOT: _normalize_inst_pivot L286 `/1000` 轉換)
            #   * 與診斷 tab 顯示的 BFI82U 全市場「億元」單位**不同**:本 df 是個股 net 買賣超(張)
            #   * caller 若要 億元 = (張 × 1000 × 收盤價) / 1e8
            # - volume 單位 = **張**(yfinance / FinMind TaiwanStockPrice Trading_Volume)
            # - 融資餘額 / 融券餘額 單位 = **張**(FinMind TaiwanStockMarginPurchaseShortSale)
            fill_cols = ['volume', '外資', '投信', '自營商', '主力合計']
            _d2_imputed = sum(int(df[c].isna().sum()) for c in fill_cols if c in df.columns)
            if _d2_imputed > 0:
                print(f"[data_loader] {stock_id} {stock_name} imputed {_d2_imputed} NaN→0 across {fill_cols}", file=sys.stderr)
            for col in fill_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(0)

            # ✅ 防呆：若合併後仍有重複欄名，先處理掉（避免 pd.to_numeric 收到 DataFrame）
            if df.columns.duplicated().any():
                # 同名欄位以加總合併（pandas 3.0 移除 axis=1，改用 T.groupby.T）
                df = df.T.groupby(level=0).sum().T

            # 強制轉數值
            # v18.241 D2 第二層 fillna：catches pd.to_numeric 強制 coerce 後的 NaN
            # （非法字串轉數值失敗會變 NaN，再 fillna(0)）。保留同上理由。
            numeric_cols = ['open', 'high', 'low', 'close', 'volume',
                          '外資', '投信', '自營商', '主力合計', '融資餘額', '融券餘額']
            _d2_coerce = sum(int(pd.to_numeric(df[c], errors='coerce').isna().sum()
                                 - df[c].isna().sum()) for c in numeric_cols if c in df.columns)
            if _d2_coerce > 0:
                print(f"[data_loader] {stock_id} {stock_name} coerce-NaN {_d2_coerce} 個非法字串 → 0", file=sys.stderr)
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # ========== 7. 最終輸出 ==========
            # 過濾掉收盤價為0或NaN的列（避免快取到無效資料）
            df = df[pd.to_numeric(df['close'], errors='coerce').fillna(0) > 0].copy()
            df = df.sort_values('date').tail(days).reset_index(drop=True)

            # 除錯
            k_type = "還原K線(復權)" if use_adjusted else "一般K線(未復權)"
            print(f"\n【數據載入成功】{stock_id} {stock_name} - {k_type}")
            print(f"資料筆數: {len(df)}")
            if '外資' in df.columns:
                print(f"外資欄位類型: {df['外資'].dtype}")
                print(f"最後3筆外資數據: {df['外資'].tail(3).tolist()}")

            try:
                df.attrs['price_src'] = _price_src
                df.attrs['inst_src'] = _inst_src
                df.attrs['margin_src'] = _margin_src
                # v18.201 D2：FinMind dataset 後台 update 時間 + 客戶端抓取 wallclock
                for _k in ('price', 'inst', 'margin'):
                    _meta = _FINMIND_META.get(_k, {}) or {}
                    df.attrs[f'{_k}_last_update'] = _meta.get('last_update', '')
                    df.attrs[f'{_k}_fetched_at'] = _meta.get('fetched_at', '')
            except Exception:
                pass

            return df, None, stock_name

        except Exception as e:
            import traceback
            traceback.print_exc()
            # N2a v19.80:raise(st.cache_data 不快取)取代 return None tuple(會被快取 1hr)
            raise _CombinedDataError(f"系統錯誤: {str(e)}")

    @st.cache_data(ttl=TTL_1HOUR, max_entries=64)  # v19.74 review:LRU 上界防 OOM
    def get_monthly_revenue(_self, stock_id):
        """月營收優先順序：MOPS(官方) → FinMind"""
        import os as _os_rv, datetime as _dt_rv
        import pandas as _pd_rv
        _tok = (_os_rv.environ.get('FINMIND_TOKEN','') or
                _os_rv.environ.get('FM_TOKEN',''))
        end_date   = _dt_rv.date.today()
        start_date = end_date - _dt_rv.timedelta(days=1095)
        start_str  = start_date.strftime('%Y-%m-%d')
        df_revenue = None
        _rev_src = 'unknown'   # v18.202 E2：月營收資料源（finmind / mops / missing）

        # ── 方案0: FinMind TaiwanStockMonthRevenue（優先，MOPS year-file全部404）
        if _tok and df_revenue is None:
            try:
                _r_fm0 = _bps_dl().get(
                    FINMIND_API_URL,
                    params={'dataset':'TaiwanStockMonthRevenue',
                            'data_id':stock_id, 'start_date':start_str,
                            'token':_tok},
                    headers=_fm_raw_headers(_tok), timeout=20)  # S8 v19.78:補 UA
                _j0r = _r_fm0.json()
                print(f'[FM-Rev0] {stock_id}: status={_j0r.get("status")} rows={len(_j0r.get("data",[]))}')
                if _j0r.get('status')==200 and _j0r.get('data'):
                    _df0r = _pd_rv.DataFrame(_j0r['data'])
                    if 'revenue' in _df0r.columns:
                        if 'date' not in _df0r.columns:
                            _df0r['date'] = (_df0r['revenue_year'].astype(str)+'-'+
                                             _df0r['revenue_month'].astype(str).str.zfill(2)+'-01')
                        _df0r['date'] = _pd_rv.to_datetime(_df0r['date'])
                        df_revenue = _df0r.sort_values('date').reset_index(drop=True)
                        _rev_src = 'finmind'   # v18.202 E2
                        print(f'[FM-Rev0] {stock_id}: ✅ {len(df_revenue)}筆')
            except Exception as _e0r:
                print(f'[FM-Rev0] {stock_id}: ❌ {type(_e0r).__name__}: {_e0r}')


        # S11 v19.78(第二份 review):原此處有第二段「方案0」— dataset/data_id/
        # start_date/token/headers/時間窗與上段逐字相同的複製貼上冗餘(gate
        # `df_revenue is None` 使其只在上段失敗時跑,參數相同故必然同敗)。
        # 已刪;暫態網路錯誤的重試改由 _bps_dl session 的 Retry adapter
        # (含 429/503/504)原則性承接,非靠意外的重複程式碼。

        # ── 方案A: MOPS 月營收（官方來源，無需 Token）──────────
        # v19.85(第八份 review 屬實項):原本無 `df_revenue is None` 閘門 — 連
        # 方案0(FinMind)成功的快樂路徑都會白打最多 4 支 year-file URL(自承全部
        # 404,見方案0 註解;t21sc03_{西元年}_0.html 亦非 MOPS 實際檔名模式)。
        # 補閘門止血(range 條件化,零重排);整段移除/改正確檔名列待核准,不擅動。
        try:
            import pandas as _pd_mops
            _today_rv = _dt_rv.date.today()
            for _y_offset_rv in range(0 if df_revenue is not None else 3):
                _yr = _today_rv.year - _y_offset_rv
                for _mops_url_rv in [
                    f'https://mops.twse.com.tw/nas/t21/sii/t21sc03_{_yr}_0.html',
                    f'https://mops.twse.com.tw/nas/t21/otc/t21sc03_{_yr}_0.html',
                    f'https://mops.twse.com.tw/nas/t21/sii/t21sc03_{_yr-1}_0.html',
                    f'https://mops.twse.com.tw/nas/t21/otc/t21sc03_{_yr-1}_0.html',
                ]:
                    try:
                        _rm2 = _fetch_url_dl(_mops_url_rv,
                                             headers={'User-Agent': 'Mozilla/5.0'},
                                             timeout=12)
                        if _rm2 is None: continue
                        _dfs_m2 = _pd_mops.read_html(_rm2.text)
                        _mops_rows2 = []
                        for _dm2 in _dfs_m2:
                            _dm2.columns = [str(c) for c in _dm2.columns]
                            _id_c = next((c for c in _dm2.columns if
                                any(k in c for k in ['代號','股票代碼','公司代號'])), None)
                            _rv_c = next((c for c in _dm2.columns if
                                '當月' in c and ('收' in c or '營收' in c)), None)
                            _yoy_c = next((c for c in _dm2.columns if
                                'YoY' in c or '年增' in c), None)
                            if not _id_c or not _rv_c: continue
                            _row2 = _dm2[_dm2[_id_c].astype(str).str.strip()==str(stock_id)]
                            if _row2.empty: continue
                            for _, _r2 in _row2.iterrows():
                                try:
                                    _rv2 = float(str(_r2[_rv_c]).replace(',',''))
                                    _yoy2 = float(str(_r2.get(_yoy_c,0)).replace(',','').replace('%','')) if _yoy_c else None
                                    if _rv2 > 0:
                                        _mops_rows2.append({
                                            'revenue': _rv2 * 1000,
                                            'date': f'{_yr}-{_today_rv.month:02d}-01',
                                            'yoy': _yoy2})
                                except (ValueError, TypeError, KeyError) as _e_mops_r2:
                                    # W5-1 §1: bare except → narrow + log (per-row parse fail in MOPS revenue fallback 2)
                                    print(f'[MOPS-Rev2] {stock_id} {_yr}-{_today_rv.month:02d} row parse skip: {_e_mops_r2}')
                        if _mops_rows2:
                            df_revenue = _pd_mops.DataFrame(_mops_rows2)
                            df_revenue['date'] = _pd_mops.to_datetime(df_revenue['date'])
                            _rev_src = 'mops'   # v18.202 E2
                            print(f'[MOPS-Rev] {stock_id}: ✅ {len(df_revenue)} 筆')
                            break
                    except Exception as _e_mops_url:  # S-MED v18.304: narrow + log
                        print(f'[MOPS-Rev] {stock_id} {_mops_url_rv} 抓取失敗: {type(_e_mops_url).__name__}: {_e_mops_url}')
                        continue
                if df_revenue is not None: break
        except Exception as _eM_rv:
            print(f'[MOPS-Rev] {stock_id}: {_eM_rv}')

        # ── 方案B: FinMind TaiwanStockMonthRevenue（API，需Token）──
        if df_revenue is None and _tok:
            try:
                from src.data.core.finmind_client import finmind_get  # D5 step2 v18.437 SSOT client
                _df = finmind_get('TaiwanStockMonthRevenue', data_id=stock_id,
                                  start_date=start_str, token=_tok, timeout=20)
                print(f'[FM-Rev] {stock_id}: rows={len(_df)}')
                if not _df.empty:
                    # 欄位：date, revenue, revenue_year, revenue_month
                    # 統一欄位名
                    _rename = {}
                    for _c in _df.columns:
                        if 'revenue' == _c.lower(): _rename[_c] = 'revenue'
                        elif 'year'  in _c.lower(): _rename[_c] = 'revenue_year'
                        elif 'month' in _c.lower(): _rename[_c] = 'revenue_month'
                    _df = _df.rename(columns=_rename)
                    if 'date' not in _df.columns and 'revenue_year' in _df.columns:
                        _df['date'] = _df['revenue_year'].astype(str) + '-' + _df['revenue_month'].astype(str).str.zfill(2) + '-01'
                    if 'revenue' in _df.columns:
                        _df['date'] = _pd_rv.to_datetime(_df['date'])
                        _df = _df.sort_values('date')
                        df_revenue = _df
                        _rev_src = 'finmind'   # v18.202 E2
                        print(f'[FM-Rev] {stock_id}: ✅ {len(df_revenue)} 筆')
            except Exception as _eF:
                print(f'[FM-Rev] {stock_id}: {_eF}')

        # ── 方案B2: MOPS 每年月份統計表（備援方式）───────────────
        if df_revenue is None:
            try:
                _mops_rows = []
                _today = _dt_rv.date.today()
                for _y_offset in range(3):
                    _y = _today.year - _y_offset
                    _url_mops = ('https://mops.twse.com.tw/nas/t21/sii/'
                                 f't21sc03_{_y}_0.html')
                    _rm = _fetch_url_dl(_url_mops,
                                        headers={'User-Agent': 'Mozilla/5.0'},
                                        timeout=15)
                    if _rm is None: continue
                    _dfs_m = _pd_rv.read_html(_rm.text)
                    for _dm in _dfs_m:
                        _dm.columns = [str(c) for c in _dm.columns]
                        # 找代碼欄
                        _id_col = next((c for c in _dm.columns
                                        if any(k in c for k in ['代號','股票代碼','公司代號'])), None)
                        _rv_col = next((c for c in _dm.columns
                                        if '當月' in c and ('收' in c or '營收' in c)), None)
                        if not _id_col or not _rv_col: continue
                        _row = _dm[_dm[_id_col].astype(str).str.strip() == str(stock_id)]
                        if _row.empty: continue
                        for _, _r in _row.iterrows():
                            try:
                                _rv = float(str(_r[_rv_col]).replace(',',''))
                                if _rv > 0:
                                    _mops_rows.append({'revenue': _rv * 1000,
                                                       'date': f'{_y}-{_today.month:02d}-01'})
                            except (ValueError, TypeError, KeyError) as _e_mops_r:
                                # W5-1 §1: bare except → narrow + log (per-row parse fail in MOPS revenue fallback 1)
                                print(f'[MOPS-Rev] {stock_id} {_y}-{_today.month:02d} row parse skip: {_e_mops_r}')
                if _mops_rows:
                    df_revenue = _pd_rv.DataFrame(_mops_rows)
                    df_revenue['date'] = _pd_rv.to_datetime(df_revenue['date'])
                    _rev_src = 'mops'   # v18.202 E2
                    print(f'[MOPS-Rev] {stock_id}: ✅ {len(df_revenue)} 筆')
            except Exception as _eM:
                print(f'[MOPS-Rev] {stock_id}: {_eM}')

        if df_revenue is not None and not df_revenue.empty:
            # 計算 YoY
            if 'revenue' in df_revenue.columns:
                df_revenue['yoy'] = df_revenue['revenue'].pct_change(12) * 100
            _stamp_finreport_attrs(df_revenue, 'rev', _rev_src)   # v18.202 E2
            return df_revenue, None
        return None, '月營收：所有來源均失敗（MOPS/FinMind）'

    # v19.105(第九份 2-A④):原完全未快取,每次切個股重抓全部季報(FinMind 3 段)。
    # 季報季更,TTL_3DAY(既有 SSOT)綽綽有餘;同 get_combined_data 的 _self 慣例。
    @st.cache_data(ttl=TTL_3DAY, max_entries=64, show_spinner=False)
    def get_quarterly_data(_self, stock_id):
        """載入近3年季度財務數據（季營收、季毛利率）

        為了避免不同資料源的「type」欄位格式不一致（例如：Q1/Q2、季報、Quarter 等），
        這裡採用「先寬鬆取回 → 再用規則辨識季度」的方式，提高成功率。
        """
        try:
            import re
            # 取回近 3 年資料（約 12 季 + buffer）
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=1200)
            start_str = start_date.strftime('%Y-%m-%d')

            # 先試 FinMind REST API
            df_fin = None
            _qtr_src = 'unknown'   # v18.202 E2：季財報資料源（finmind_rest / finmind_sdk / yfinance / missing）
            try:
                import os as _os_q
                from src.data.core.finmind_client import finmind_get  # D5 step2 v18.437 SSOT client
                _tok_q = _os_q.environ.get('FINMIND_TOKEN', '')
                # 免費版：TaiwanStockFinancialStatement（無s）；付費版：有s；兩個都試
                _df_q_tmp = None
                for _ds_q in ['TaiwanStockFinancialStatement', 'TaiwanStockFinancialStatements']:
                    try:
                        _df_resp_q = finmind_get(_ds_q, data_id=stock_id,
                                                 start_date=start_str, token=_tok_q, timeout=25)
                        print(f'[季財報REST/{_ds_q}] {stock_id} rows={len(_df_resp_q)}')
                        if not _df_resp_q.empty:
                            _df_q_tmp = _df_resp_q
                            break
                    except Exception as _eq2:
                        print(f'[季財報REST/{_ds_q}] {_eq2}')
                if _df_q_tmp is not None and not _df_q_tmp.empty:
                    df_fin = _df_q_tmp
                    _qtr_src = 'finmind_rest'   # v18.202 E2
            except Exception as _eq:
                print(f'[季財報REST] {_eq}')

            # 備援: FinMind Library
            if df_fin is None or df_fin.empty:
                try:
                    df_fin = _self.dl.taiwan_stock_financial_statement(
                        stock_id=stock_id, start_date=start_str,
                        timeout=HTTP_TIMEOUT_FINMIND_SDK_SEC)  # S6 v19.78
                    if df_fin is not None and not df_fin.empty:
                        _qtr_src = 'finmind_sdk'   # v18.202 E2
                except Exception as _e_fin_sdk:
                    # W5-1 §1: bare except → log (FinMind SDK 季財報 fallback 失敗)
                    print(f'[FinMind-SDK 季報] {stock_id}: {_e_fin_sdk}')

            if df_fin is None or df_fin.empty:
                # ── 備援: yfinance 季度 ──
                try:
                    import yfinance as _yf_q
                    for _sfx_q in ('.TW', '.TWO'):
                        _tk_q = _yf_q.Ticker(f"{stock_id}{_sfx_q}")
                        _qf_q = (getattr(_tk_q, 'quarterly_income_stmt', None)
                                 or getattr(_tk_q, 'quarterly_financials', None))
                        if _qf_q is not None and not _qf_q.empty:
                            break
                    if _qf_q is not None and not _qf_q.empty:
                        _rows_yf = []
                        # 找出 Revenue 和 Gross Profit 的 index label
                        _rev_row = next((idx for idx in _qf_q.index if any(k in str(idx) for k in ['Revenue','Total Revenue','revenue'])), None)
                        _gp_row  = next((idx for idx in _qf_q.index if 'Gross Profit' in str(idx) or 'GrossProfit' in str(idx)), None)
                        for _col_q in _qf_q.columns:
                            _dt_q = pd.Timestamp(_col_q)
                            _qt_num = ((_dt_q.month - 1) // 3) + 1
                            _rev_val = float(_qf_q.loc[_rev_row, _col_q]) if _rev_row is not None else float('nan')
                            _gp_val  = float(_qf_q.loc[_gp_row,  _col_q]) if _gp_row  is not None else float('nan')
                            _rows_yf.append({'date': _dt_q.strftime('%Y-%m-%d'),
                                              'type': f'Q{_qt_num}', 'value': _rev_val,
                                              'origin_name': '營業收入合計', 'stock_id': stock_id})
                            if not pd.isna(_gp_val):
                                _rows_yf.append({'date': _dt_q.strftime('%Y-%m-%d'),
                                                  'type': f'Q{_qt_num}', 'value': _gp_val,
                                                  'origin_name': '毛利', 'stock_id': stock_id})
                        if _rows_yf:
                            df_fin = pd.DataFrame(_rows_yf)
                            _qtr_src = 'yfinance'   # v18.202 E2
                            print(f"[yfinance QTR] {stock_id}: ✅ {len(df_fin)}筆 (含毛利:{_gp_row is not None})")
                except Exception as _eYF_q:
                    print(f"[yfinance QTR] {stock_id}: {_eYF_q}")

            if df_fin is None or df_fin.empty:
                return None, f"{stock_id} 季財報：所有來源（FinMind/yfinance）均無資料"

            # ===== 0) 判斷是否金融股（避免把一般公司邏輯套到金融股）=====
            def _is_financial_stock(_sid: str) -> bool:
                try:
                    info = _self.dl.taiwan_stock_info()
                    if info is not None and not info.empty and 'stock_id' in info.columns:
                        m2 = info[info['stock_id'] == _sid]
                        if not m2.empty:
                            row = m2.iloc[0].to_dict()
                            # 嘗試從可能的產業欄位判斷
                            for k in ['industry_category', 'industry', 'category', 'type', '產業別', '產業類別', '產業分類', 'industry_category_zh']:
                                if k in row and row[k] is not None:
                                    s = str(row[k])
                                    if any(w in s for w in ['金融', '保險', '金控', '銀行', '證券']):
                                        return True
                except Exception as _e_isfin:
                    # §1 v19.80(N5):原靜默吞 — 補 log。退回前綴啟發式(28/58)為既有
                    # 保底行為,非 28/58 開頭的金融股(如純網銀)會誤判為一般股,log 留跡可診斷
                    print(f'[季財報] {_sid} 產業別查詢失敗(退前綴啟發式): '
                          f'{type(_e_isfin).__name__}: {_e_isfin}')
                # 保底：台股金融族群常見代碼前綴
                return str(_sid).startswith(('28', '58'))

            is_finance = _is_financial_stock(stock_id)

            # ===== 金融股：季營收改用「月營收加總」；毛利率不計算 =====
            if is_finance:
                try:
                    df_m, err_m = _self.get_monthly_revenue(stock_id)
                    if err_m is None and df_m is not None and not df_m.empty:
                        df_m = df_m.copy()
                        col_date = '日期' if '日期' in df_m.columns else ('date' if 'date' in df_m.columns else None)
                        col_rev  = '營收' if '營收' in df_m.columns else ('revenue' if 'revenue' in df_m.columns else None)
                        if col_date is not None and col_rev is not None:
                            df_m[col_date] = pd.to_datetime(df_m[col_date], errors='coerce')
                            df_m = df_m.dropna(subset=[col_date]).sort_values(col_date)
                            df_m['_y'] = df_m[col_date].dt.year.astype('int64')
                            df_m['_q'] = (((df_m[col_date].dt.month - 1) // 3) + 1).astype('int64')
                            df_m[col_rev] = pd.to_numeric(df_m[col_rev], errors='coerce')
                            qsum = df_m.groupby(['_y', '_q'])[col_rev].sum().reset_index()
                            qsum = qsum.rename(columns={'_y': '年度', '_q': '季度', col_rev: '營收'})
                            qsum['季度標籤'] = qsum['年度'].astype(str) + 'Q' + qsum['季度'].astype(str)
                            qsum['毛利率'] = pd.NA
                            qsum['毛利率名稱'] = '毛利率'
                            qsum['是否金融股'] = True
                            return qsum, None
                except Exception:
                    # 若月營收加總也失敗，才繼續走下面的原本邏輯（避免整段中斷）
                    pass


            # ===== 除錯資訊（保留，用來判斷 API 欄位格式）=====
            print(f"欄位: {df_fin.columns.tolist()}")
            print(f"總筆數: {len(df_fin)}")

            # ===== 1) 先嘗試辨識「季度」資料 =====
            df_work = df_fin.copy()

            # 有些資料會用 type 表示季度/年度；先把 type 轉成字串便於判斷
            if 'type' in df_work.columns:
                df_work['type'] = df_work['type'].astype(str)
                # 常見季度型態：Q1/Q2/Q3/Q4、1Q/2Q...、季報、Quarter、季
                q_mask = df_work['type'].str.contains(r"(?:^Q[1-4]$|^[1-4]Q$|季|季報|quarter)", case=False, na=False)
                df_q = df_work[q_mask].copy()

                # 若過濾後反而全空，代表 type 不是這種格式（例如根本沒有區分），就退回用全量資料
                if not df_q.empty:
                    df_work = df_q
                # else: type欄位格式不符，繼續使用全量資料

            # ===== 2) Pivot：date x 科目 =====
            need_cols = {'date', 'origin_name', 'value'}
            if not need_cols.issubset(set(df_work.columns)):
                # 缺欄位就直接回報，並附上目前欄位，方便定位
                return None, f"季度財報欄位不足（需要 date/origin_name/value），目前只有: {', '.join(df_work.columns.astype(str).tolist()[:20])}"

            df_pivot = df_work.pivot_table(
                index=['date'],
                columns='origin_name',
                values='value',
                aggfunc='first'
            ).reset_index()

            # date 轉時間
            df_pivot['date'] = pd.to_datetime(df_pivot['date'], errors='coerce')
            df_pivot = df_pivot[df_pivot['date'].notna()].copy()
            if df_pivot.empty:
                return None, "季度財報日期欄位無法解析"

            # ===== 3) 建立季度標籤 =====
            df_quarterly = pd.DataFrame()
            df_quarterly['年度'] = df_pivot['date'].dt.year
            df_quarterly['季度'] = ((df_pivot['date'].dt.month - 1) // 3) + 1
            df_quarterly['季度標籤'] = df_quarterly['年度'].astype(int).astype(str) + 'Q' + df_quarterly['季度'].astype(int).astype(str)

            # ===== 4) 找「營收」欄位（一般公司優先；金融股/金控用月營收加總作為季度營收）=====
            is_finance = False
            revenue_candidates = []
            for col in df_pivot.columns:
                c = str(col)
                if any(k in c for k in ['營業收入', '收入合計', '營收']) or re.search(r"\brevenue\b", c, re.I):
                    revenue_candidates.append(col)

            # 金融/保險常見的「營收代理」欄位（不一定等於營收，但可用來判斷是否為金融股）
            finance_candidates = []
            for col in df_pivot.columns:
                c = str(col)
                if any(k in c for k in ['淨收益', '利息淨收益', '利息以外淨收益', '保險負債準備淨變動']) or re.search(r"interest\s*net\s*income|net\s*interest|net\s*revenue", c, re.I):
                    finance_candidates.append(col)

            if revenue_candidates:
                rev_col = revenue_candidates[0]
                df_quarterly['營收'] = pd.to_numeric(df_pivot[rev_col], errors='coerce')
            else:
                # 找不到一般營收欄位：很可能是金融股/金控
                # v19.83(第六份 review Bug 1):原三元式兩分支皆 True(恆真)—
                # 無金融代理欄位的一般股(如特殊報表格式)也被當金融股走月加總路徑。
                is_finance = bool(finance_candidates)
                # 先用財報中的代理欄位墊底（避免空值），後續會用「月營收加總」覆蓋季度營收
                if finance_candidates:
                    rev_col = finance_candidates[0]
                    df_quarterly['營收'] = pd.to_numeric(df_pivot[rev_col], errors='coerce')
                else:
                    # v19.83:pd.NA(object) 會讓下方 L1576 `(營收<0).any()` 拋
                    # TypeError(NA 布林不明確);改 float nan,比較/運算行為皆安全
                    df_quarterly['營收'] = float('nan')

            # 金融股：季度營收一律以「月營收 3 個月加總」為準（對齊看盤軟體的季營收）
            if is_finance:
                df_month, _merr = _self.get_monthly_revenue(stock_id)
                if df_month is not None and not df_month.empty:
                    # v19.83(第六份 review Bug 1):get_monthly_revenue 契約欄位是
                    # date/revenue(v18.202 起),原 df_month[['年','月','營收']] 一執行
                    # 就 KeyError → 被本函式外層 except 變成「載入錯誤」,整檔季報全滅。
                    # 改用實際契約欄位(雙名容錯,對齊上方早退路徑 L1264 既有寫法)。
                    _mr_date = '日期' if '日期' in df_month.columns else (
                        'date' if 'date' in df_month.columns else None)
                    _mr_rev = '營收' if '營收' in df_month.columns else (
                        'revenue' if 'revenue' in df_month.columns else None)
                    if _mr_date is None or _mr_rev is None:
                        print(f'[季財報] {stock_id} 月營收欄位不符契約'
                              f'(需 date/revenue),實際: {list(df_month.columns)[:8]}')
                        dfm = None
                    else:
                        dfm = df_month[[_mr_date, _mr_rev]].copy()
                        dfm.columns = ['日期', '營收']
                        dfm['日期'] = pd.to_datetime(dfm['日期'], errors='coerce')
                        dfm = dfm[dfm['日期'].notna()].copy()
                        dfm['營收'] = pd.to_numeric(dfm['營收'], errors='coerce')
                if (df_month is not None and not df_month.empty
                        and dfm is not None and not dfm.empty):
                    dfm['年度'] = dfm['日期'].dt.year.astype(int)
                    dfm['季度'] = (((dfm['日期'].dt.month - 1) // 3) + 1).astype(int)
                    qsum = dfm.groupby(['年度', '季度'], as_index=False)['營收'].sum()
                    # 用字串鍵合併，避免 pandas 在不同平台發生 int/int64 factorize mismatch
                    df_quarterly['yq_key'] = df_quarterly['年度'].astype(int).astype(str) + 'Q' + df_quarterly['季度'].astype(int).astype(str)
                    qsum['yq_key'] = qsum['年度'].astype(int).astype(str) + 'Q' + qsum['季度'].astype(int).astype(str)
                    df_quarterly = df_quarterly.merge(qsum[['yq_key', '營收']].rename(columns={'營收': '營收_月加總'}), on='yq_key', how='left')
                    df_quarterly['營收'] = pd.to_numeric(df_quarterly['營收_月加總'], errors='coerce').fillna(pd.to_numeric(df_quarterly['營收'], errors='coerce'))
                    df_quarterly = df_quarterly.drop(columns=['營收_月加總'])
                else:
                    pass  # 月營收加總失敗，繼續用財報原始值

            # 預設指標名稱
            df_quarterly['毛利率名稱'] = '毛利率'
            # ===== 5) 毛利率：優先用毛利，沒有就用(營收-成本) =====
            # 金融股：不計算毛利率，改用稅後純益率(%) 取代；若算不出則留空
            if is_finance:
                net_col = None
                for col in df_pivot.columns:
                    c = str(col)
                    if any(k in c for k in ['本期稅後淨利', '稅後淨利', '淨利（淨損）', '繼續營業單位本期淨利']) or re.search(r"income\s*after\s*tax|net\s*income", c, re.I):
                        net_col = col
                        break
                if net_col is not None:
                    net_income = pd.to_numeric(df_pivot[net_col], errors='coerce')
                    # N1 v19.80:分母補 0→NaN 防呆(對齊營益率/淨利率 L1448 既有 pattern;
                    # 金融股不走「營收>0」過濾,inf 會流進圖表)
                    df_quarterly['毛利率'] = (net_income / pd.to_numeric(df_quarterly['營收'], errors='coerce').replace(0, float('nan')) * 100).round(2)
                    df_quarterly['毛利率名稱'] = '稅後純益率'
                else:
                    df_quarterly['毛利率'] = float('nan')
                    df_quarterly['毛利率名稱'] = '稅後純益率'

            # 一般公司：照舊計算毛利率（金融股已在上方 if is_finance 區塊處理，此處略過）
            if not is_finance:
                # 優先：直接毛利率(%)欄位（部分資料源直接給百分比）
                _gm_pct_col = next((col for col in df_pivot.columns if '毛利率' in str(col)), None)
                if _gm_pct_col is not None:
                    _gm_vals = pd.to_numeric(df_pivot[_gm_pct_col], errors='coerce')
                    if _gm_vals.notna().any():
                        df_quarterly['毛利率'] = _gm_vals.values
                        print(f'[毛利率] 直接欄位 {_gm_pct_col}: ✅')
                    else:
                        _gm_pct_col = None  # 欄位全NaN，繼續用下面的計算

                if _gm_pct_col is None:
                    gp_col = None
                    for col in df_pivot.columns:
                        c = str(col)
                        if any(k in c for k in ['毛利', '營業毛利']) or re.search(r"gross\s*profit", c, re.I):
                            gp_col = col
                            break

                    if gp_col is not None:
                        gp = pd.to_numeric(df_pivot[gp_col], errors='coerce')
                        # N1 v19.80:分母補 0→NaN(對齊 L1448 pattern,防 inf)
                        df_quarterly['毛利率'] = (gp / pd.to_numeric(df_quarterly['營收'], errors='coerce').replace(0, float('nan')) * 100).round(2)
                    else:
                        cost_col = None
                        for col in df_pivot.columns:
                            c = str(col)
                            if any(k in c for k in ['營業成本', '成本合計']) or re.search(r"cost\s+of\s+revenue|cost\s+of\s+goods", c, re.I):
                                cost_col = col
                                break

                        if cost_col is not None:
                            cost = pd.to_numeric(df_pivot[cost_col], errors='coerce')
                            # N1 v19.80:分母補 0→NaN(對齊 L1448 pattern,防 inf)
                            _rev_gm = pd.to_numeric(df_quarterly['營收'], errors='coerce').replace(0, float('nan'))
                            df_quarterly['毛利率'] = ((df_quarterly['營收'] - cost) / _rev_gm * 100).round(2)
                        else:
                            df_quarterly['毛利率'] = float('nan')
                            print(f"⚠️ 無法找到毛利/成本欄位，可用欄位: {[str(c) for c in df_pivot.columns[:15]]}")
                            # ── Fix C: 補充 yfinance 毛利率 ──────────────────────
                            try:
                                import yfinance as _yf_gps
                                for _sfx_g in ('.TW', '.TWO'):
                                    _tk_g = _yf_gps.Ticker(f'{stock_id}{_sfx_g}')
                                    _qi_g = (getattr(_tk_g, 'quarterly_income_stmt', None)
                                             or getattr(_tk_g, 'quarterly_financials', None))
                                    if _qi_g is not None and not _qi_g.empty:
                                        _gp_r = next((i for i in _qi_g.index if 'Gross Profit' in str(i)), None)
                                        _rv_r = next((i for i in _qi_g.index if 'Total Revenue' in str(i) or str(i)=='Revenue'), None)
                                        if _gp_r and _rv_r:
                                            for _qc in _qi_g.columns:
                                                _qts = f"{_qc.year}Q{((_qc.month-1)//3)+1}"
                                                _mk = df_quarterly['季度標籤'] == _qts
                                                if _mk.any():
                                                    _gv = float(_qi_g.loc[_gp_r, _qc])
                                                    _rv = float(_qi_g.loc[_rv_r, _qc])
                                                    if _rv > 0 and not pd.isna(_gv):
                                                        df_quarterly.loc[_mk, '毛利率'] = round(_gv / _rv * 100, 2)
                                            _non_nan = df_quarterly['毛利率'].notna().sum()
                                            print(f'[毛利率] yfinance補充 {stock_id}{_sfx_g}: 非NaN={_non_nan}')
                                            if _non_nan > 0:
                                                break
                            except Exception as _egp:
                                print(f'[毛利率] yfinance補充失敗: {_egp}')

            # ===== 5b) EPS：每股盈餘 =====
            eps_col = None
            for col in df_pivot.columns:
                c = str(col)
                if any(k in c for k in ['每股盈餘', '基本每股', 'EPS']) or re.search(r"basic\s*eps|earnings\s*per\s*share", c, re.I):
                    eps_col = col
                    break
            if eps_col is not None:
                df_quarterly['EPS'] = pd.to_numeric(df_pivot[eps_col], errors='coerce')
            else:
                df_quarterly['EPS'] = float('nan')

            # ===== 5d) 毛利率備援：yfinance quarterly_income_stmt（含舊名稱相容） =====
            if not is_finance and df_quarterly['毛利率'].isna().all():
                try:
                    import yfinance as _yf_gp
                    for _yf_sfx in ('.TW', '.TWO'):
                        _tk_gp = _yf_gp.Ticker(f"{stock_id}{_yf_sfx}")
                        # yfinance ≥0.2.36: quarterly_income_stmt; 舊版用 quarterly_financials
                        _qfin = (getattr(_tk_gp, 'quarterly_income_stmt', None)
                                 or getattr(_tk_gp, 'quarterly_financials', None))
                        if _qfin is not None and not _qfin.empty:
                            break
                    if _qfin is not None and not _qfin.empty:
                        # 取 GrossProfit 與 Revenue（多種欄位名相容）
                        _gp_row = next((r for r in _qfin.index if 'Gross' in str(r) and 'Profit' in str(r)), None)
                        if _gp_row is None:
                            _gp_row = next((r for r in _qfin.index if 'GrossProfit' in str(r).replace(' ', '')), None)
                        _rv_row = next((r for r in _qfin.index if 'Total' in str(r) and 'Revenue' in str(r)), None)
                        if _rv_row is None:   # 備援：OperatingRevenue / 任意 Revenue
                            _rv_row = next((r for r in _qfin.index if 'Revenue' in str(r)), None)
                        print(f'[yfinance 毛利率] {stock_id}: gp={_gp_row}, rv={_rv_row}, cols={list(_qfin.index)[:6]}')
                        if _gp_row and _rv_row:
                            _yf_updated = 0
                            for _col in _qfin.columns:
                                try:
                                    _ts = pd.Timestamp(_col)
                                    _yr_q = _ts.year; _mo_q = _ts.month
                                    _q_q  = ((_mo_q - 1) // 3) + 1
                                    _lbl  = f"{_yr_q}Q{_q_q}"
                                    _mk   = df_quarterly.index[df_quarterly['季度標籤'] == _lbl]
                                    if len(_mk) and pd.isna(df_quarterly.loc[_mk[0], '毛利率']):
                                        _gp_v = float(_qfin.loc[_gp_row, _col])
                                        _rv_v = float(_qfin.loc[_rv_row, _col])
                                        if (not pd.isna(_gp_v) and not pd.isna(_rv_v)
                                                and abs(_rv_v) > 0):
                                            df_quarterly.loc[_mk[0], '毛利率'] = round(_gp_v / _rv_v * 100, 2)
                                            _yf_updated += 1
                                except (ValueError, TypeError, KeyError) as _e_yfq:
                                    # W5-1 §1: bare except → narrow + log (yfinance 毛利率單季 parse 失敗)
                                    print(f'[yfinance 毛利率] {stock_id} col={_col} skip: {_e_yfq}')
                            if _yf_updated > 0:
                                print(f'[yfinance 毛利率] {stock_id}: ✅ {_yf_updated} 季')
                except Exception as _e_yf_gp:
                    print(f'[yfinance 毛利率] {stock_id}: {_e_yf_gp}')

            # ===== 5e) 三率：營業利益率 + 淨利率（從同一份 income statement pivot 提取）=====
            if not is_finance:
                # 營業利益 (Operating Income)
                _oi_col = None
                for col in df_pivot.columns:
                    c = str(col)
                    if any(k in c for k in ['營業利益', '業務利益', '營業損益']) or \
                       re.search(r"operating.*(income|profit|loss)", c, re.I):
                        _oi_col = col; break
                if _oi_col is not None:
                    _oi = pd.to_numeric(df_pivot[_oi_col], errors='coerce')
                    _rev_denom = pd.to_numeric(df_quarterly['營收'], errors='coerce').replace(0, float('nan'))
                    df_quarterly['營業利益率'] = (_oi.values / _rev_denom.values * 100).round(2)
                    print(f'[三率] {stock_id}: 營業利益率={_oi_col}')
                else:
                    df_quarterly['營業利益率'] = float('nan')

                # 稅後純益 / 本期淨利 (Net Income)
                _ni_col = None
                for col in df_pivot.columns:
                    c = str(col)
                    if any(k in c for k in ['稅後純益', '本期淨利', '本期損益', '稅後淨利',
                                             '淨利（淨損）', '淨損益', '繼續營業單位本期淨利']) or \
                       re.search(r"net.*(income|profit|loss)|profit.*after.*tax", c, re.I):
                        _ni_col = col; break
                if _ni_col is not None:
                    _ni = pd.to_numeric(df_pivot[_ni_col], errors='coerce')
                    _rev_denom = pd.to_numeric(df_quarterly['營收'], errors='coerce').replace(0, float('nan'))
                    df_quarterly['淨利率'] = (_ni.values / _rev_denom.values * 100).round(2)
                    print(f'[三率] {stock_id}: 淨利率={_ni_col}')
                else:
                    df_quarterly['淨利率'] = float('nan')
            else:
                # 金融股：不計算三率（毛利率名稱已改為稅後純益率）
                df_quarterly['營業利益率'] = float('nan')
                df_quarterly['淨利率']     = float('nan')

            # ===== 6) 清洗與排序 =====
            df_quarterly = df_quarterly.dropna(subset=['營收']).copy()
            # ✅ 金融股：允許負數營收（投資損失等）；一般公司：過濾負數
            if not is_finance:
                df_quarterly = df_quarterly[df_quarterly['營收'] > 0].copy()
            df_quarterly = df_quarterly.drop_duplicates(subset=['季度標籤'], keep='last')
            df_quarterly = df_quarterly.sort_values(['年度', '季度']).tail(12).reset_index(drop=True)

            if df_quarterly.empty:
                return None, "查無有效季度資料（可能該公司/資料源未提供近年季報）"

            # ── 加入季末標準 date 欄位，供資料診斷儀表板讀取 ──────────────
            _QTR_END = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}
            df_quarterly['date'] = (
                df_quarterly['年度'].astype(int).astype(str) + '-'
                + df_quarterly['季度'].astype(int).map(_QTR_END)
            )

            print(f"✓ 成功載入 {len(df_quarterly)} 筆季度資料")
            df_quarterly['是否金融股'] = is_finance

            # ✅ 除錯：檢查是否有負數營收
            if (df_quarterly['營收'] < 0).any():
                print(f"⚠️ 發現負數營收（金融股={is_finance}）:")
                neg_data = df_quarterly[df_quarterly['營收'] < 0][['季度標籤', '營收']]
                print(neg_data.to_string(index=False))

            _stamp_finreport_attrs(df_quarterly, 'qtr', _qtr_src)   # v18.202 E2
            return df_quarterly, None

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, f"載入錯誤: {str(e)}"

    def get_quarterly_bs_cf(_self, stock_id):
        """
        取得近 12 季的「資產負債表 + 現金流量」時序資料，用於前瞻動能計算。
        回傳欄位：季度標籤, 合約負債, 存貨, 資本支出（皆為原始金額，單位：千元或元）
        資料來源：FinMind TaiwanStockBalanceSheet + TaiwanStockCashFlowsStatement
        """
        try:
            import os as _os_bscf, datetime as _dt_bscf
            _qtr_extra_src = 'unknown'   # v18.202 E2：季財報-extra 資料源（finmind / finmind_mops / missing）
            _tok = _os_bscf.environ.get('FINMIND_TOKEN', '')
            _start = (_dt_bscf.date.today() - _dt_bscf.timedelta(days=365 * 3)).strftime('%Y-%m-%d')
            _hdrs = _fm_raw_headers(_tok)   # S8 v19.78:補 UA

            def _fm_fetch(dataset):
                _p = {'dataset': dataset, 'data_id': stock_id, 'start_date': _start}
                if _tok: _p['token'] = _tok
                _r = _bps_dl().get(FINMIND_API_URL,
                                    params=_p, headers=_hdrs, timeout=20)
                _j = _r.json()
                print(f'[BS/CF] {stock_id} {dataset}: status={_j.get("status")} rows={len(_j.get("data",[]))}')
                return _j.get('data', []) if _j.get('status') == 200 else []

            # ── Balance Sheet ────────────────────────────────────────
            _bs_rows = _fm_fetch('TaiwanStockBalanceSheet')
            _bs_map = {}   # {date → {type → value}}
            for _row in _bs_rows:
                _d = _row.get('date', '')
                _bs_map.setdefault(_d, {})[_row.get('type', '')] = _row
                _bs_map[_d][_row.get('origin_name', '')] = _row

            # ── Cash Flow ────────────────────────────────────────────
            _cf_rows = _fm_fetch('TaiwanStockCashFlowsStatement')
            _cf_map = {}   # {date → {type → value}}
            for _row in _cf_rows:
                _d = _row.get('date', '')
                _cf_map.setdefault(_d, {})[_row.get('type', '')] = _row
                _cf_map[_d][_row.get('origin_name', '')] = _row

            if not _bs_rows and not _cf_rows:
                return None, f"{stock_id} BS+CF：FinMind 無資料"
            _qtr_extra_src = 'finmind'   # v18.202 E2：BS/CF 主源命中

            # ── 彙整所有出現的季度日期 ──────────────────────────────
            _all_dates = sorted(set(list(_bs_map.keys()) + list(_cf_map.keys())))

            def _val(d_map, d, keys):
                """從 d_map[d] 裡按優先順序取第一個非零值

                W5-1 §1 註明:回傳 NaN 即為「無此欄位/無效值」的顯式旗標(caller 需 isna 檢查),
                每 key 每季 parse fail 全量 log 會 noise 過大(BS/CF 跨多 key×多季);
                此處將 bare except 收窄為 (ValueError, TypeError, AttributeError) 但維持 silent skip,
                NaN 出口為下游可偵測信號(§1 三條件:顯式 + 旗標達成)。
                """
                slot = d_map.get(d, {})
                for k in keys:
                    r = slot.get(k)
                    if r is not None:
                        try:
                            v = float(str(r.get('value', 0)).replace(',', '') or 0)
                            if v != 0: return abs(v)
                        except (ValueError, TypeError, AttributeError):
                            pass
                return float('nan')

            _CL_KEYS = ['CurrentContractLiabilities', 'NonCurrentContractLiabilities',
                        'ContractLiabilities', 'ContractLiabilitiesCurrent',
                        'ContractLiabilitiesNonCurrent',
                        '合約負債', '合約負債-流動', '合約負債－流動',
                        '合約負債-非流動', '合約負債－非流動',
                        '契約負債', '預收款項']
            _INV_KEYS = ['Inventories', 'InventoriesNet', 'Inventories_Net',
                         '存貨', '存貨淨額', '商品存貨']
            _CX_KEYS  = ['AcquisitionOfPropertyPlantAndEquipment',
                         'PropertyAndPlantAndEquipment',
                         '取得不動產、廠房及設備', '購置不動產、廠房及設備', '資本支出']
            # 處分PP&E現金流入（偵測賣廠等重大資產處分）
            _DISP_KEYS = ['ProceedsFromDisposalOfPropertyPlantAndEquipment',
                          'SaleOfPropertyPlantAndEquipment',
                          'DisposalOfPropertyPlantAndEquipment',
                          '處分不動產、廠房及設備之現金流入',
                          '出售不動產、廠房及設備收入',
                          '處分固定資產收入']

            # 建立 DataFrame 供合約負債模糊比對（str.contains 最可靠）
            _bs_df_raw = pd.DataFrame(_bs_rows) if _bs_rows else pd.DataFrame()
            _has_bs_df = (not _bs_df_raw.empty and
                          'type' in _bs_df_raw.columns and
                          'date' in _bs_df_raw.columns and
                          'value' in _bs_df_raw.columns)
            if _has_bs_df:
                _bs_df_raw = _bs_df_raw.sort_values('date', ascending=False)

            _records = []
            for _d in _all_dates:
                try:
                    _ts = pd.Timestamp(_d)
                    _yr = _ts.year; _qt = ((_ts.month - 1) // 3) + 1
                    _lbl = f'{_yr}Q{_qt}'
                except Exception as _e_qtr_parse:  # S-MED v18.304: narrow + log
                    print(f'[QtrExtra] date parse skip {_d}: {type(_e_qtr_parse).__name__}: {_e_qtr_parse}')
                    continue

                # ── 合約負債：DataFrame str.contains（最可靠，涵蓋所有 dash 變體）──
                _cl = float('nan')
                if _has_bs_df:
                    _cl_rows = _bs_df_raw[(_bs_df_raw['date'] == _d) &
                                          _bs_df_raw['type'].str.contains('合約負債', na=False)]
                    if len(_cl_rows) > 0:
                        _cl_vals = pd.to_numeric(
                            _cl_rows['value'].astype(str).str.replace(',', '', regex=False),
                            errors='coerce').abs()
                        _cl_vals = _cl_vals[_cl_vals > 0]
                        if len(_cl_vals) > 0:
                            _cl = float(_cl_vals.sum())
                            print(f'[BS/CF] {stock_id} {_d} CL={_cl:.0f} ({len(_cl_rows)} rows via contains)')
                # 備援：精確 key 查找 + dict fuzzy
                if isinstance(_cl, float) and _cl != _cl:  # isnan
                    _cl = _val(_bs_map, _d, _CL_KEYS)
                    if isinstance(_cl, float) and _cl != _cl:
                        _slot = _bs_map.get(_d, {})
                        _parts = [abs(float(str(_v.get('value', 0)).replace(',', '') or 0))
                                  for _k, _v in _slot.items()
                                  if '合約負債' in str(_k) and isinstance(_v, dict)]
                        _parts = [p for p in _parts if p > 0]
                        if _parts: _cl = sum(_parts)

                _inv  = _val(_bs_map, _d, _INV_KEYS)
                _cx   = _val(_cf_map, _d, _CX_KEYS)
                _disp = _val(_cf_map, _d, _DISP_KEYS)
                _records.append({'季度標籤': _lbl, '合約負債': _cl, '存貨': _inv,
                                  '資本支出': _cx, '處分資產現金流入': _disp})

            if not _records:
                return None, f"{stock_id} BS+CF：日期解析失敗"

            df_extra = pd.DataFrame(_records)
            df_extra = df_extra.drop_duplicates(subset=['季度標籤'], keep='last')
            df_extra = df_extra.sort_values('季度標籤').tail(12).reset_index(drop=True)
            # ── 加入季末標準 date 欄位，供資料診斷儀表板讀取 ──────────────
            _QME = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}
            def _qe2date(lbl):
                try: return f'{lbl[:4]}-{_QME[int(lbl[5])]}'
                # v19.82:裸 except 收窄(§3.3);非法季標籤 → None 為既有語意
                except (ValueError, TypeError, IndexError, KeyError): return None
            df_extra['date'] = df_extra['季度標籤'].apply(_qe2date)

            # ── MOPS 備援：FinMind 抓不到合約負債時，補抓最後 1 季 ──────────
            # 來源：mops.twse.com.tw/mops/web/ajax_t164sb03 (合併資產負債表)
            # 觸發條件：最後 1 季 _cl 為 NaN（避免 N×4 慢爆）
            try:
                _last_cl_nan = (len(df_extra) > 0 and
                                pd.isna(df_extra['合約負債'].iloc[-1]))
                if _last_cl_nan:
                    from src.data.stock import (fetch_mops_financials as _fmf,
                                                       build_proxy_session as _bps_mops)
                    _last_lbl = df_extra['季度標籤'].iloc[-1]
                    _yr_m = int(_last_lbl[:4]); _q_m = int(_last_lbl[5])
                    _sess_m = _bps_mops()
                    _mops_df = _fmf(stock_id, _yr_m, _q_m, _sess_m)
                    _cl_mops = float('nan')
                    if _mops_df is not None and not _mops_df.empty:
                        # MOPS 表格通常為 [會計項目, 金額] 兩欄 flat 格式
                        _flat = _mops_df.astype(str)
                        _mask = _flat.apply(
                            lambda row: row.str.contains('合約負債', na=False).any(),
                            axis=1)
                        _hit = _flat[_mask]
                        _vals = []
                        for _, _r_m in _hit.iterrows():
                            for _cell in _r_m.tolist():
                                _cs = str(_cell).replace(',', '').strip()
                                try:
                                    _vv = float(_cs)
                                    if _vv > 0:
                                        _vals.append(_vv)
                                except Exception:
                                    pass
                        if _vals:
                            _cl_mops = float(sum(_vals))
                    if _cl_mops == _cl_mops and _cl_mops > 0:
                        df_extra.loc[df_extra.index[-1], '合約負債'] = _cl_mops
                        _qtr_extra_src = 'finmind_mops'   # v18.202 E2：MOPS 補合約負債
                        print(f'[BS/CF/MOPS] {stock_id} {_last_lbl}: ✅ CL={_cl_mops:.0f} (備援命中)')
                    else:
                        print(f'[BS/CF/MOPS] {stock_id} {_last_lbl}: ⚠️ MOPS 亦無合約負債科目（可能此股無此項）')
            except Exception as _e_mops:
                print(f'[BS/CF/MOPS] ⚠️ {type(_e_mops).__name__}: {_e_mops}')

            print(f'[BS/CF] {stock_id}: ✅ {len(df_extra)} 季 CL={df_extra["合約負債"].notna().sum()} INV={df_extra["存貨"].notna().sum()} CX={df_extra["資本支出"].notna().sum()} DISP={df_extra["處分資產現金流入"].notna().sum()}')
            _stamp_finreport_attrs(df_extra, 'qtr_extra', _qtr_extra_src)   # v18.202 E2
            return df_extra, None

        except Exception as _e_bscf:
            import traceback; traceback.print_exc()
            return None, f"BS+CF 載入錯誤: {_e_bscf}"


# ── 模組級函式：MJ 財報體檢所需原始數據 ─────────────────────
@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_financial_statements(stock_id: str, token: str = "") -> dict:
    """
    從 FinMind 抓取最新一季資產負債表、現金流量表、損益表，
    計算 MJ 體系所需指標。
    回傳 dict；失敗時回傳 {"error": "..."}。
    """
    import os as _os_ffs, requests as _rq_ffs, datetime as _dt_ffs

    _tok = token or _os_ffs.environ.get("FINMIND_TOKEN", "")
    _start = (_dt_ffs.date.today() - _dt_ffs.timedelta(days=730)).strftime("%Y-%m-%d")
    _hdrs = {"Authorization": f"Bearer {_tok}"} if _tok else {}

    def _fm(dataset):
        _p = {"dataset": dataset, "data_id": stock_id, "start_date": _start}
        if _tok:
            _p["token"] = _tok
        try:
            _r = _rq_ffs.get(
                FINMIND_API_URL,
                params=_p, headers=_hdrs, timeout=20,
            )
            _j = _r.json()
            _st = _j.get("status")
            if _st != 200:
                print(f"[fetch_fin/{dataset}] 非200回應: status={_st} msg={_j.get('msg','')}")
            return _j.get("data", []) if _st == 200 else [], _st
        except Exception as _e:
            print(f"[fetch_fin/{dataset}] {_e}")
            return [], None

    # 3 個 dataset 彼此獨立 → 並行抓（_fm 純獨立 requests、無共享可變狀態，線程安全）。
    # map 保序，故下方解包順序與 _ds_ffs 一致；總請求數不變（FinMind 限額為每小時制）。
    from concurrent.futures import ThreadPoolExecutor as _TPE_ffs
    _ds_ffs = ("TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement",
               "TaiwanStockFinancialStatements")
    with _TPE_ffs(max_workers=3) as _ex_ffs:
        _fm_res = list(_ex_ffs.map(_fm, _ds_ffs))
    (_bs_rows, _bs_st), (_cf_rows, _cf_st), (_is_rows, _is_st) = _fm_res

    if not _bs_rows and not _cf_rows:
        # 區分 Token 問題 vs 股票本身無資料
        _statuses = [s for s in [_bs_st, _cf_st] if s is not None]
        if not _tok:
            _err = f"{stock_id}：未設定 FINMIND_TOKEN，無法查詢財報"
        elif any(s in (401, 403) for s in _statuses):
            _err = f"{stock_id}：FINMIND_TOKEN 無效或已過期（HTTP {_statuses[0]}）"
        else:
            _err = (f"{stock_id}：FinMind 無此股票財報資料"
                    f"（可能為新掛牌、未上市、或 FinMind 資料源尚未收錄）")
        return {"error": _err}

    def _build(rows):
        """同一 (date,key) 多筆值衝突時取最大絕對值。
        FinMind 對某些股票（例如 6770）會回傳多筆 type=Revenue 但 origin_name 不同
        （合計行 + 子科目行）；若用 last-wins 子科目會覆蓋合計，導致 rev 被低估、
        om/nm 出現 >100% 的荒謬比率。改取 max(|val|) 以保證合計優於子科目。"""
        m: dict = {}
        for r in rows:
            d = r.get("date", "")
            try:
                v = float(str(r.get("value", 0) or 0).replace(",", ""))
            except Exception:
                v = 0.0
            slot = m.setdefault(d, {})
            for _key in (r.get("type", ""), r.get("origin_name", "")):
                if not _key:
                    continue
                _prev = slot.get(_key)
                if _prev is None or abs(v) > abs(float(_prev) if _prev else 0):
                    slot[_key] = v
        return m

    _bs = _build(_bs_rows)
    _cf = _build(_cf_rows)
    _is = _build(_is_rows)

    _dates = sorted(set(list(_bs.keys()) + list(_cf.keys())))
    if not _dates:
        return {"error": f"{stock_id}：財報日期解析失敗"}

    _lat = _dates[-1]
    _prv = _dates[-2] if len(_dates) >= 2 else _lat

    def _v(m, d, keys):
        slot = m.get(d, {})
        for k in keys:
            v = slot.get(k)
            if v is not None:
                try:
                    fv = float(str(v).replace(",", "") or 0)
                    if fv != 0:
                        return fv
                except Exception:
                    pass
        return 0.0

    def _vsum(m, d, keys):
        """加總 keys 中所有非零欄位（用於應收票據+帳款需分開列示的報表）"""
        slot = m.get(d, {})
        total = 0.0
        for k in keys:
            v = slot.get(k)
            if v is not None:
                try:
                    fv = float(str(v).replace(",", "") or 0)
                    if fv > 0:
                        total += fv
                except Exception:
                    pass
        return total

    cash   = _v(_bs, _lat, ["CashAndCashEquivalents", "現金及約當現金", "Cash",
                              "現金及銀行存款", "庫存現金及約當現金"])
    assets = _v(_bs, _lat, ["TotalAssets", "資產總計", "資產合計", "資產總額",
                              "資產總計（千元）", "Assets"])
    liab   = _v(_bs, _lat, ["TotalLiabilities", "負債總計", "負債合計", "負債總額",
                             "Liabilities", "負債合計（千元）", "負債總額（千元）",
                             "負債總計（千元）"])
    cur_assets = _v(_bs, _lat, ["CurrentAssets", "流動資產合計", "流動資產總計",
                                  "流動資產", "流動資產總額"])
    cur_liab = _v(_bs, _lat, ["CurrentLiabilities", "流動負債合計", "流動負債總計",
                                "流動負債", "流動負債總額"])
    # FinMind 不一定提供「負債合計」彙總行，直接用 流動+非流動 相加
    _non_cur_liab = _v(_bs, _lat, ["NoncurrentLiabilities", "非流動負債合計",
                                    "非流動負債總計", "非流動負債"])
    if liab == 0 and (cur_liab > 0 or _non_cur_liab > 0):
        liab = cur_liab + _non_cur_liab
        print(f"[fetch_fin] {stock_id} 負債合計查無，改用 流動({cur_liab:.0f})+非流動({_non_cur_liab:.0f})={liab:.0f}千")
    # FinMind 不一定提供「資產合計」彙總行，直接用 流動+非流動 相加
    _non_cur_assets = _v(_bs, _lat, ["NoncurrentAssets", "非流動資產合計",
                                      "非流動資產總計", "非流動資產"])
    if assets == 0 and (cur_assets > 0 or _non_cur_assets > 0):
        assets = cur_assets + _non_cur_assets
        print(f"[fetch_fin] {stock_id} 資產合計查無，改用 流動({cur_assets:.0f})+非流動({_non_cur_assets:.0f})={assets:.0f}千")
    # AR：L1 先加總分開列示的票據+帳款+關係人（避免與合計行重疊）
    # 涵蓋：舊格式（淨額/關係人）+ IFRS 括號格式（非關係人）/（關係人）+ 含稅格式
    # + em-dash（－）半形連字號（-）波折號（—）三種變體 + 全形括號（）+ 半形括號()
    ar = _vsum(_bs, _lat, [
        "應收票據淨額", "應收帳款淨額", "應收帳款－關係人淨額", "應收款項",
        "應收帳款（非關係人）", "應收帳款（關係人）",
        "應收帳款（非關係人）淨額", "應收帳款（關係人）淨額",
        "應收帳款－非關係人淨額",          # em-dash 非關係人淨額
        "應收票據（非關係人）", "應收票據（關係人）",
        "應收帳款-非關係人", "應收帳款-關係人",
        "應收帳款—非關係人", "應收帳款—關係人",          # 全形破折號
        "應收帳款 - 非關係人", "應收帳款 - 關係人",      # 帶空白
        "應收票據－非關係人淨額", "應收票據－關係人淨額",  # 票據 em-dash
        "應收帳款-非關係人淨額", "應收帳款-關係人淨額",   # 半形 + 淨額
        "應收帳款(非關係人)", "應收帳款(關係人)",         # 半形括號
    ])
    # L2 若 L1 = 0，改抓合併列示的合計行（不與 L1 混加，避免重複計算）
    if ar == 0:
        ar = _vsum(_bs, _lat, ["應收帳款及票據", "應收帳款及票據淨額",
                                "應收票據及帳款淨額",                    # 新增
                                "應收票據及應收帳款", "應收帳款",
                                "應收帳款（含稅）", "應收帳款淨額（含稅）"])
    if ar == 0:
        ar = _v(_bs, _lat, ["AccountsReceivable", "應收帳款淨額", "應收帳款",
                             "NoteAndAccountsReceivable", "應收帳款及票據應收款",
                             "應收票據及帳款", "應收帳款（淨額）", "貿易應收款及其他應收款",
                             "貿易及其他應收款",                          # 新增：外資掛牌台企
                             "應收帳款，淨額", "貿易應收款",
                             "應收款項", "應收款項合計", "應收帳款及其他應收款",
                             "ReceivablesNet", "NetReceivables",
                             "合約資產", "工程應收款", "應收帳款及合約資產",
                             "應收票據及應收帳款",
                             "應收帳款（非關係人）", "應收帳款（關係人）"])
    ap     = _v(_bs, _lat, ["AccountsPayable", "應付帳款",
                             "NoteAndAccountsPayable", "應付帳款及票據應付款",
                             "應付票據及帳款", "貿易應付款"])
    inv    = _v(_bs, _lat, ["Inventories", "存貨", "存貨淨額"])
    inv_p  = _v(_bs, _prv, ["Inventories", "存貨", "存貨淨額"])
    ppe    = _v(_bs, _lat, ["PropertyPlantAndEquipmentNet", "不動產、廠房及設備淨額",
                             "固定資產淨額", "不動產廠房及設備",
                             "PropertyPlantAndEquipment", "不動產廠房及設備淨額",
                             "不動產、廠房及設備"])
    lt_inv = _v(_bs, _lat, ["LongTermInvestments", "長期投資", "採權益法之投資"])
    # ── v10.57.0 新增：MJ 體檢補充原料（速動比率 / 現金再投資比率 / EPS）──
    prepaid = _v(_bs, _lat, ["Prepayments", "預付款項", "預付費用", "預付貨款",
                              "預付投資款", "其他預付款項"])
    other_nca = _v(_bs, _lat, ["OtherNoncurrentAssets", "其他非流動資產",
                                "其他非流動資產合計"])
    # 基本 EPS（IS）
    eps_v = _v(_is, _lat, ["BasicEarningsPerShare", "基本每股盈餘", "每股盈餘",
                            "EPS", "Earnings Per Share", "稀釋每股盈餘"])

    ocf    = _v(_cf, _lat, ["CashFlowsFromOperatingActivities",
                             "營業活動之淨現金流入（流出）", "來自營業活動之現金流量"])
    icf    = _v(_cf, _lat, ["CashFlowsFromInvestingActivities",
                             "投資活動之淨現金流入（流出）", "來自投資活動之現金流量"])
    fncf   = _v(_cf, _lat, ["CashFlowsFromFinancingActivities",
                             "籌資活動之淨現金流入（流出）", "來自籌資活動之現金流量"])
    capex  = abs(_v(_cf, _lat, ["AcquisitionOfPropertyPlantAndEquipment",
                                 "取得不動產、廠房及設備", "購置不動產、廠房及設備", "資本支出"]))
    div_paid = abs(_v(_cf, _lat, ["CashDividendsPaid", "發放現金股利", "現金股利"]))

    rev    = _v(_is, _lat, ["Revenue", "營業收入合計", "營業收入", "NetRevenue",
                              "OperatingRevenue", "營業總收入", "營業淨收入",
                              "銷貨收入淨額", "銷貨收入"])
    cogs   = abs(_v(_is, _lat, ["CostOfGoodsSold", "營業成本", "銷售成本",
                                 "OperatingCosts", "營業總成本"]))
    oper_income = _v(_is, _lat, ["OperatingIncome", "營業利益（損失）", "營業利益",
                                  "Operating Income", "OperatingProfit",
                                  "營業淨利", "營業損益"])
    net_ni = _v(_is, _lat, ["NetIncome", "本期淨利（淨損）", "淨利", "稅後淨利",
                              "ProfitLoss", "本期綜合損益總額",
                              "歸屬於母公司業主之淨利（淨損）"])
    # ── Sanity: oi/ni 不應大於 rev × 1.2（單位錯亂或子科目誤抓）──────
    if rev > 0:
        if abs(oper_income) > rev * 1.2:
            print(f"[fetch_fin] {stock_id} ⚠️ oper_income={oper_income:.0f} > rev={rev:.0f}×1.2，疑似誤抓子科目，重置為 0")
            oper_income = 0
        if abs(net_ni) > rev * 1.2:
            print(f"[fetch_fin] {stock_id} ⚠️ net_ni={net_ni:.0f} > rev={rev:.0f}×1.2，疑似誤抓子科目，重置為 0")
            net_ni = 0

    rev_p  = _v(_is, _prv, ["Revenue", "營業收入合計", "營業收入"])
    ar_p   = _v(_bs, _prv, [
        "AccountsReceivable", "應收帳款淨額", "應收帳款",
        "應收帳款（非關係人）", "應收帳款（關係人）",
        "應收帳款（非關係人）淨額", "應收帳款及票據", "應收票據及應收帳款",
        "應收帳款（含稅）",
    ])
    equity = _v(_bs, _lat, ["TotalEquity", "權益總額", "股東權益合計",
                             "TotalStockholdersEquity", "股東權益總額",
                             "EquityAttributableToOwnersOfParent",
                             "歸屬於母公司業主之權益合計",
                             "權益合計"])
    # 理智校驗：equity < 0.1% of assets → 可能抓到子項目而非合計，改用 assets−liab 重算
    if 0 < equity < assets * 0.001 and liab > 0:
        recalc = max(assets - liab, 0)
        print(f"[fetch_fin] {stock_id} equity={equity:.0f}千 疑似欄位誤配（{equity/assets:.6%}），改用 assets-liab={recalc:.0f}千")
        equity = recalc
    # Fallback: Assets = Liabilities + Equity（IFRS 恆等式，雙向兜底）
    if liab == 0 and assets > 0 and equity > 0:
        liab = max(assets - equity, 0)
        print(f"[fetch_fin] {stock_id} 負債欄位查無資料，改用 資產-權益 計算: {round(liab/1e3)}千")
    if assets == 0 and equity > 0 and liab > 0:
        assets = equity + liab
        print(f"[fetch_fin] {stock_id} 資產欄位查無資料，改用 權益+負債 計算: {round(assets/1e3)}千")

    # 模糊比對兜底：從 BS 所有欄位取最大值（合計行通常是最大的）
    # 正規化 key：去除全形/半形空白，確保「負 債 總 計」等全形空白格式能匹配
    _bs_slot = _bs.get(_lat, {})
    def _fuzzy_bs(_inc, _exc=()):
        _best = 0.0
        for _fk, _fvv in _bs_slot.items():
            _fks = str(_fk).replace(' ', '').replace('　', '')
            if all(_i in _fks for _i in _inc) and not any(_e in _fks for _e in _exc):
                try:
                    _ffv = float(str(_fvv).replace(",", "") or 0)
                    if _ffv > _best:
                        _best = _ffv
                except Exception:
                    pass
        return _best
    if assets == 0:
        assets = _fuzzy_bs(["資產"], ["負債", "資本", "遞延"])
        if assets > 0:
            print(f"[fetch_fin] {stock_id} assets 模糊比對: {assets:.0f}千")
    if liab == 0:
        liab = _fuzzy_bs(["負債"], ["資產", "準備", "權益"])
        if liab == 0:
            # 放寬：移除「準備」排除（避免「負債準備」類科目被錯排）
            liab = _fuzzy_bs(["負債"], ["資產", "權益"])
        if liab > 0:
            print(f"[fetch_fin] {stock_id} liab 模糊比對: {liab:.0f}千")
        else:
            # 完全失敗：印出 BS 所有欄位名稱供診斷
            _all_bs_keys = sorted(_bs_slot.keys())
            print(f"[fetch_fin] {stock_id} liab 模糊全失敗 "
                  f"bs_keys={_all_bs_keys[:30]}")
    if ar == 0:
        ar = _fuzzy_bs(["應收"], ["利息", "所得稅", "員工", "遞延", "退稅"])
        if ar == 0:
            ar = _fuzzy_bs(["合約資產"])  # IFRS 15 合約資產
        if ar > 0:
            print(f"[fetch_fin] {stock_id} ar 模糊比對: {ar:.0f}千")

    # ── Pandas regex 終極兜底：正規化所有空白後做 str.contains，抓全形空白科目 ──
    if (ar == 0 or liab == 0) and _bs_slot:
        try:
            import pandas as _pd_regex
            _bsdf = _pd_regex.DataFrame(
                list(_bs_slot.items()), columns=['type', 'value']
            )
            _bsdf['type_n'] = _bsdf['type'].str.replace(r'\s+|　', '', regex=True)
            _bsdf['val_n'] = _pd_regex.to_numeric(
                _bsdf['value'].astype(str).str.replace(',', '', regex=False),
                errors='coerce'
            )
            _bsdf = _bsdf[_bsdf['val_n'].notna() & (_bsdf['val_n'] > 0)]
            if ar == 0:
                _ar_mask = (_bsdf['type_n'].str.contains('應收帳款|應收票據', regex=True, na=False) &
                            ~_bsdf['type_n'].str.contains('利息|所得稅|員工|遞延|退稅', regex=True, na=False))
                if _ar_mask.any():
                    ar = float(_bsdf.loc[_ar_mask, 'val_n'].max())
                    print(f"[fetch_fin] {stock_id} ar pandas-regex兜底: {ar:.0f}千 "
                          f"type={_bsdf.loc[_ar_mask, 'type'].iloc[0]!r}")
            if liab == 0:
                _lb_mask = (_bsdf['type_n'].str.contains('負債總計|負債合計|負債總額', regex=True, na=False) &
                            ~_bsdf['type_n'].str.contains('非流動|流動負債', regex=True, na=False))
                if _lb_mask.any():
                    liab = float(_bsdf.loc[_lb_mask, 'val_n'].max())
                    print(f"[fetch_fin] {stock_id} liab pandas-regex兜底: {liab:.0f}千 "
                          f"type={_bsdf.loc[_lb_mask, 'type'].iloc[0]!r}")
        except Exception as _e_regex:
            print(f"[fetch_fin] {stock_id} pandas-regex兜底異常: {_e_regex}")

    # ── FinMind 原始列 str.contains 兜底（非標準科目命名，如力積電等）──
    if ar == 0 and _bs_rows:
        try:
            import pandas as _pd_ar_sc
            _bs_df_sc = _pd_ar_sc.DataFrame(_bs_rows)
            if not _bs_df_sc.empty and 'date' in _bs_df_sc.columns and 'type' in _bs_df_sc.columns:
                _lat_sc = _bs_df_sc[_bs_df_sc['date'] == _lat].copy()
                _excl_kw = '利息|所得稅|員工|遞延|退稅'
                _on_col = (_lat_sc['origin_name'] if 'origin_name' in _lat_sc.columns
                           else _pd_ar_sc.Series([''] * len(_lat_sc), index=_lat_sc.index))
                _ar_mask = (
                    (_lat_sc['type'].str.contains('應收帳款', na=False) |
                     _on_col.str.contains('應收帳款', na=False)) &
                    ~_lat_sc['type'].str.contains(_excl_kw, na=False)
                )
                _ar_match_sc = _lat_sc[_ar_mask]
                if not _ar_match_sc.empty:
                    ar = float(_ar_match_sc['value'].max() or 0)
                    if ar > 0:
                        print(f"[fetch_fin] {stock_id} ar str.contains兜底: {ar:.0f}千 "
                              f"types={list(_ar_match_sc['type'].values)[:3]}")
        except Exception as _e_ar_sc:
            print(f"[fetch_fin] {stock_id} ar str.contains兜底異常: {_e_ar_sc}")

    # ── yfinance 備援：對仍為零的關鍵欄位嘗試補值 ────────────────────────
    if ar == 0 or liab == 0 or assets == 0:
        try:
            import yfinance as _yf_ffs, pandas as _pd_yf_ffs
            _yf_bs_df = None
            for _sfx_yf in (".TW", ".TWO"):
                _tk_yf = _yf_ffs.Ticker(f"{stock_id}{_sfx_yf}")
                _qbs_yf = getattr(_tk_yf, "quarterly_balance_sheet", None)
                if _qbs_yf is not None and not _qbs_yf.empty:
                    _yf_bs_df = _qbs_yf
                    break
            if _yf_bs_df is not None and not _yf_bs_df.empty:
                _yfc = _yf_bs_df.columns[0]
                def _yf_v(*_keys_yf):
                    for _k in _keys_yf:
                        for _idx in _yf_bs_df.index:
                            if _k.lower() in str(_idx).lower():
                                try:
                                    _v = float(_yf_bs_df.loc[_idx, _yfc])
                                    if _pd_yf_ffs.notna(_v) and _v != 0:
                                        return _v
                                except Exception:
                                    pass
                    return 0.0
                _filled_yf = []
                if assets == 0:
                    _va = _yf_v("total assets")
                    if _va > 0:
                        assets = _va; _filled_yf.append("assets")
                if liab == 0:
                    _vl = _yf_v("total liab", "total liabilities")
                    if _vl > 0:
                        liab = _vl; _filled_yf.append("liab")
                if ar == 0:
                    _var = _yf_v("net receivables", "accounts receivable", "receivables")
                    if _var > 0:
                        ar = _var; _filled_yf.append("ar")
                if _filled_yf:
                    print(f"[fetch_fin] {stock_id} yfinance備援補值 {_filled_yf}: "
                          f"assets={assets:.0f} liab={liab:.0f} ar={ar:.0f} 千")
                    # 若 yfinance 補了 assets/equity，再試一次 IFRS identity
                    if liab == 0 and assets > 0 and equity > 0:
                        liab = max(assets - equity, 0)
                    if assets == 0 and equity > 0 and liab > 0:
                        assets = equity + liab
        except Exception as _e_yf:
            print(f"[fetch_fin] {stock_id} yfinance備援異常: {_e_yf}")

    _zero_fields = [f for f, v in [("ar", ar), ("ppe", ppe), ("liab", liab), ("equity", equity)] if v == 0]
    if _zero_fields:
        _all_bs_keys = list((_bs.get(_lat) or {}).keys())
        print(f"[fetch_fin] {stock_id} 零值欄位={_zero_fields} 全部BS欄位({len(_all_bs_keys)})={_all_bs_keys}")
        # AR 全部失敗時額外嘗試：合約資產（IFRS 15）/ 貿易應收款 / 應收款項（不含利息）
        if ar == 0 and _all_bs_keys:
            for _extra_ar in ["合約資產", "流動合約資產", "貿易及其他應收款項",
                               "應收款項（不含關係人）", "短期應收款"]:
                _ev = _bs_slot.get(_extra_ar)
                if _ev:
                    try:
                        _ef = float(str(_ev).replace(',', ''))
                        if _ef > 0:
                            ar = _ef
                            print(f"[fetch_fin] {stock_id} ar 補充別名 '{_extra_ar}': {ar:.0f}千")
                            break
                    except Exception:
                        pass

    # 最終 sanity check：liab/assets < 1% → 疑似子科目誤配（非零但近零的 cur+noncur）
    # 印出所有含「負債」的欄位供診斷；嘗試 IFRS identity（equity 在此已被修正過）
    if 0 < liab < assets * 0.01 and assets > 0:
        _liab_keys = [(k, _bs_slot.get(k)) for k in sorted(_bs_slot.keys())
                      if '負債' in str(k) and '資產' not in str(k)]
        print(f"[fetch_fin] {stock_id} ⚠️ liab={liab:.0f} 僅 {liab/assets:.4%} of assets={assets:.0f}，"
              f"cur_liab={cur_liab:.0f} ncl={_non_cur_liab:.0f}，"
              f"負債欄位={_liab_keys[:10]}")
        # 用 IFRS identity 嘗試修正（equity 已在 1700-1703 處被修正為 assets-old_liab ≈ assets）
        # 此時 equity ≈ assets，故用 assets - equity 不可行；改用 fuzzy 強制再跑一次
        _liab_fuzzy2 = _fuzzy_bs(["負債"], ["資產", "權益"])
        if _liab_fuzzy2 > liab * 5:
            liab = _liab_fuzzy2
            print(f"[fetch_fin] {stock_id} liab sanity 修正 via fuzzy: {liab:.0f}千")

    # AR sanity：ar/季收入 < 0.5% → 疑似子科目誤配（如關係人應收幾千元）
    if 0 < ar < (rev * 0.005) and rev > 0:
        _ar_keys = [(k, _bs_slot.get(k)) for k in sorted(_bs_slot.keys())
                    if '應收' in str(k) and '利息' not in str(k) and '所得稅' not in str(k)]
        print(f"[fetch_fin] {stock_id} ⚠️ ar={ar:.0f}千 僅 {ar/(rev*4)*360:.1f}天，"
              f"應收欄位={_ar_keys[:10]}")
        _ar_fuzzy2 = _fuzzy_bs(["應收"], ["利息", "所得稅", "員工", "遞延", "退稅"])
        if _ar_fuzzy2 > ar * 5:
            ar = _ar_fuzzy2
            print(f"[fetch_fin] {stock_id} ar sanity 修正 via fuzzy: {ar:.0f}千")

    cash_ratio = round(cash / assets * 100, 1) if assets > 0 else 0
    debt_ratio = round(liab / assets * 100, 1) if assets > 0 else 0
    gp         = rev - cogs
    gm         = round(gp / rev * 100, 1) if rev > 0 else 0
    # 年化：單季數字 × 4，以免 DSO/DPO 被低估 4 倍；天數基準統一 360 天
    ar_days = round(ar / (rev * 4) * 360, 1) if rev > 0 and ar > 0 else 0
    ap_days = round(ap / (cogs * 4) * 360, 1) if cogs > 0 and ap > 0 else 0
    fcf        = round(ocf - capex)
    ar_chg     = round((ar - ar_p) / abs(ar_p) * 100, 1) if ar_p != 0 else None
    rev_chg    = round((rev - rev_p) / abs(rev_p) * 100, 1) if rev_p != 0 else None

    print(f"[fetch_fin] {stock_id} {_lat}: cash={cash_ratio}% debt={debt_ratio}% "
          f"OCF={round(ocf/1e6,1)}百萬 AR_days={ar_days} AP_days={ap_days}")

    # ── prev_period_data：供 MJ trend 季際比較 bootstrap（v18.456）─────────────────
    # 用已抓到的 730 天 FinMind 資料再計算上一季指標，避免 Streamlit Cloud 重啟後
    # 快照清空導致 mj_trend 恆為 0。不做模糊比對/yfinance 兜底（零值時 analyze 給 N/A 即可）。
    _prev_period_data: dict = {}
    if len(_dates) >= 2:
        _pp = _prv                                          # 上一季日期
        _pp_prv = _dates[-3] if len(_dates) >= 3 else _prv  # 上上季（for 存貨前期）
        _pp_cash   = _v(_bs, _pp, ["CashAndCashEquivalents", "現金及約當現金", "Cash", "現金及銀行存款"])
        _pp_assets = _v(_bs, _pp, ["TotalAssets", "資產總計", "資產合計", "資產總額"])
        _pp_cur_a  = _v(_bs, _pp, ["CurrentAssets", "流動資產合計", "流動資產總計", "流動資產"])
        _pp_cur_l  = _v(_bs, _pp, ["CurrentLiabilities", "流動負債合計", "流動負債總計", "流動負債"])
        _pp_ncl    = _v(_bs, _pp, ["NoncurrentLiabilities", "非流動負債合計", "非流動負債總計", "非流動負債"])
        _pp_liab   = _v(_bs, _pp, ["TotalLiabilities", "負債總計", "負債合計", "負債總額"])
        if _pp_liab == 0 and (_pp_cur_l > 0 or _pp_ncl > 0):
            _pp_liab = _pp_cur_l + _pp_ncl
        if _pp_assets == 0 and _pp_cur_a > 0:
            _pp_nca = _v(_bs, _pp, ["NoncurrentAssets", "非流動資產合計", "非流動資產"])
            _pp_assets = _pp_cur_a + _pp_nca
        _pp_equity = _v(_bs, _pp, ["TotalEquity", "權益總額", "股東權益合計", "股東權益總額", "權益合計"])
        if _pp_liab == 0 and _pp_assets > 0 and _pp_equity > 0:
            _pp_liab = max(_pp_assets - _pp_equity, 0)
        if _pp_assets == 0 and _pp_equity > 0 and _pp_liab > 0:
            _pp_assets = _pp_equity + _pp_liab
        _pp_inv    = _v(_bs, _pp, ["Inventories", "存貨", "存貨淨額"])
        _pp_inv_p  = _v(_bs, _pp_prv, ["Inventories", "存貨", "存貨淨額"])
        _pp_ppe    = _v(_bs, _pp, ["PropertyPlantAndEquipmentNet", "不動產、廠房及設備淨額",
                                    "固定資產淨額", "不動產廠房及設備淨額"])
        _pp_lt_inv = _v(_bs, _pp, ["LongTermInvestments", "長期投資", "採權益法之投資"])
        _pp_ar     = _v(_bs, _pp, ["AccountsReceivable", "應收帳款淨額", "應收帳款",
                                    "應收帳款（非關係人）淨額", "應收帳款及票據",
                                    "應收票據及應收帳款", "應收帳款（含稅）"])
        _pp_ap     = _v(_bs, _pp, ["AccountsPayable", "應付帳款",
                                    "應付帳款及票據應付款", "應付票據及帳款"])
        _pp_rev    = _v(_is, _pp, ["Revenue", "營業收入合計", "營業收入", "NetRevenue", "OperatingRevenue"])
        _pp_cogs   = abs(_v(_is, _pp, ["CostOfGoodsSold", "營業成本", "銷售成本", "OperatingCosts"]))
        _pp_gp     = _pp_rev - _pp_cogs
        _pp_oi     = _v(_is, _pp, ["OperatingIncome", "營業利益（損失）", "營業利益", "OperatingProfit"])
        _pp_ni     = _v(_is, _pp, ["NetIncome", "本期淨利（淨損）", "淨利", "稅後淨利", "ProfitLoss"])
        _pp_ocf    = _v(_cf, _pp, ["CashFlowsFromOperatingActivities",
                                    "營業活動之淨現金流入（流出）", "來自營業活動之現金流量"])
        _pp_capex  = abs(_v(_cf, _pp, ["AcquisitionOfPropertyPlantAndEquipment",
                                        "取得不動產、廠房及設備", "資本支出"]))
        _pp_div    = abs(_v(_cf, _pp, ["CashDividendsPaid", "發放現金股利", "現金股利"]))

        _pp_cash_ratio = round(_pp_cash / _pp_assets * 100, 1) if _pp_assets > 0 else 0
        _pp_debt_ratio = round(_pp_liab / _pp_assets * 100, 1) if _pp_assets > 0 else 0
        _pp_gm         = round(_pp_gp / _pp_rev * 100, 1) if _pp_rev > 0 else 0
        _pp_ar_days    = round(_pp_ar / (_pp_rev * 4) * 360, 1) if _pp_rev > 0 and _pp_ar > 0 else 0
        _pp_ap_days    = round(_pp_ap / (_pp_cogs * 4) * 360, 1) if _pp_cogs > 0 and _pp_ap > 0 else 0

        _prev_period_data = {
            "stock_id":           stock_id,
            "period":             _pp,
            "現金佔總資產(%)":    _pp_cash_ratio,
            "負債比率(%)":        _pp_debt_ratio,
            "OCF(千)":            round(_pp_ocf),
            "ICF(千)":            0,
            "籌資CF(千)":         0,
            "自由現金流(千)":     round(_pp_ocf - _pp_capex),
            "資本支出(千)":       round(_pp_capex),
            "應收帳款天數":       _pp_ar_days,
            "應付帳款天數":       _pp_ap_days,
            "毛利率(%)":          _pp_gm,
            "營業收入(千)":       round(_pp_rev),
            "毛利(千)":           round(_pp_gp),
            "營業利益(千)":       round(_pp_oi),
            "稅後淨利(千)":       round(_pp_ni),
            "股東權益(千)":       round(_pp_equity),
            "流動資產(千)":       round(_pp_cur_a),
            "非流動負債(千)":     round(max(_pp_liab - _pp_cur_l, 0)),
            "營業成本(千)":       round(_pp_cogs),
            "OCF符號":            "正" if _pp_ocf > 0 else "負",
            "ICF符號":            "負",
            "籌資CF符號":         "負",
            "應收帳款季增率(%)":  None,
            "營收季增率(%)":      None,
            "總資產(千)":         round(_pp_assets),
            "總負債(千)":         round(_pp_liab),
            "流動負債(千)":       round(_pp_cur_l),
            "存貨(千)":           round(_pp_inv),
            "存貨前期(千)":       round(_pp_inv_p),
            "現金股利(千)":       round(_pp_div),
            "固定資產(千)":       round(_pp_ppe),
            "長期投資(千)":       round(_pp_lt_inv),
            "現金及約當現金(千)": round(_pp_cash),
            "應收帳款(千)":       round(_pp_ar),
            "EPS":                0,
            "預付款項(千)":       0,
            "其他非流動資產(千)": 0,
            "is_finance":         stock_id.startswith(('28', '58')),
        }

    return {
        "stock_id":         stock_id,
        "period":           _lat,
        "現金佔總資產(%)":  cash_ratio,
        "負債比率(%)":      debt_ratio,
        "OCF(千)":          round(ocf),
        "ICF(千)":          round(icf),
        "籌資CF(千)":       round(fncf),
        "自由現金流(千)":   fcf,
        "資本支出(千)":     round(capex),
        "應收帳款天數":     ar_days,
        "應付帳款天數":     ap_days,
        "毛利率(%)":        gm,
        "營業收入(千)":      round(rev),
        "毛利(千)":          round(gp),
        "營業利益(千)":      round(oper_income),
        "稅後淨利(千)":      round(net_ni),
        "股東權益(千)":      round(equity),
        "流動資產(千)":      round(cur_assets),
        "非流動負債(千)":    round(max(liab - cur_liab, 0)),
        "營業成本(千)":      round(cogs),
        "OCF符號":          "正" if ocf > 0 else "負",
        "ICF符號":          "正" if icf > 0 else "負",
        "籌資CF符號":       "正" if fncf > 0 else "負",
        "應收帳款季增率(%)": ar_chg,
        "營收季增率(%)":     rev_chg,
        "總資產(千)":        round(assets),
        "總負債(千)":        round(liab),
        "流動負債(千)":      round(cur_liab),
        "存貨(千)":          round(inv),
        "存貨前期(千)":      round(inv_p),
        "現金股利(千)":      round(div_paid),
        "固定資產(千)":      round(ppe),
        "長期投資(千)":      round(lt_inv),
        # ── v10.57.0 新增：MJ 體檢原料（5 個）──
        "現金及約當現金(千)": round(cash),
        "應收帳款(千)":      round(ar),
        "EPS":               round(eps_v, 2) if eps_v else 0,
        "預付款項(千)":      round(prepaid),
        "其他非流動資產(千)": round(other_nca),
        "is_finance":        stock_id.startswith(('28', '58')),
        # ── 原始 slot 暴露：供診斷頁分辨「API 真失敗 / 此股無此科目 / 該股本季為 0」──
        "_bs_slot_latest":   dict(_bs_slot),
        "_cf_slot_latest":   dict(_cf.get(_lat, {})),
        "_is_slot_latest":   dict(_is.get(_lat, {})),
        "_period_latest":    _lat,
        # S-PROV-1 v18.250 phase 6:provenance(§2.2)
        "source":            "FinMind:FinancialStatements",
        "fetched_at":        pd.Timestamp.now('UTC').isoformat(),
        # v18.456: 上季關鍵指標，供 mj_trend bootstrap（ephemeral 重啟後仍可計算 2 季對比）
        "prev_period_data":  _prev_period_data,
    }


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_industry_category(sid: str) -> str:
    """v18.326 SSOT(原 tab_stock.py 私有 _fetch_industry_category 抽出)。

    從 FinMind TaiwanStockInfo 抓個股產業類別字串。失敗回 ''。
    用於 P/B 河流圖閾值動態調整(金融 / 成長科技 / 製造)。1 日快取。
    """
    import os as _os_ic
    import requests as _rq_ic
    try:
        _tok = _os_ic.environ.get('FINMIND_TOKEN', '')
        _p = {'dataset': 'TaiwanStockInfo', 'data_id': sid}
        if _tok:
            _p['token'] = _tok
        # S8 v19.78 UA 補漏(v19.82):token 維持走 params,headers 僅補 UA
        _r = _rq_ic.get(FINMIND_API_URL,
                        params=_p, headers=_fm_raw_headers(''), timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            try:
                from src.data.core.provenance import prov_log
                prov_log('fetch_industry_category',
                         'FinMind:TaiwanStockInfo', 'empty', ticker=sid)
            except Exception:
                pass
            return ''
        for _row in _data:
            _ind = _row.get('industry_category', '')
            if _ind:
                try:
                    from src.data.core.provenance import prov_log
                    prov_log('fetch_industry_category',
                             'FinMind:TaiwanStockInfo',
                             f'str:{_ind}', ticker=sid)
                except Exception:
                    pass
                return str(_ind)
        return ''
    except Exception:
        return ''


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_bps_from_finmind(sid: str) -> float:
    """v18.326 SSOT(原 tab_stock.py 私有 _fetch_bps_from_finmind 抽出)。

    FinMind TaiwanStockBalanceSheet 計算最新季度每股淨值(BPS)。
    公式:BPS = 股東權益總額 / 流通在外普通股股數
          流通股數 = 普通股股本 / 面額 10 元(台股慣例)
    Sanity 守門:BPS ∈ (0.1, 5000)。範圍外回 0.0。
    """
    import os as _os_bf
    import datetime as _dt_bf
    import requests as _rq_bf
    try:
        _tok = _os_bf.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_bf.date.today() - _dt_bf.timedelta(days=540)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockBalanceSheet', 'data_id': sid, 'start_date': _start}
        if _tok:
            _p['token'] = _tok
        # S8 v19.78 UA 補漏(v19.82):token 維持走 params,headers 僅補 UA
        _r = _rq_bf.get(FINMIND_API_URL,
                        params=_p, headers=_fm_raw_headers(''), timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return 0.0
        _dates = sorted({_row.get('date', '') for _row in _data}, reverse=True)
        _latest = _dates[0] if _dates else ''
        _equity = 0.0
        _common_stock = 0.0
        for _row in _data:
            if _row.get('date') != _latest:
                continue
            _t = str(_row.get('type', ''))
            _nm = str(_row.get('origin_name', ''))
            try:
                _v = float(str(_row.get('value', 0) or 0).replace(',', ''))
            except (TypeError, ValueError):
                continue
            if _v <= 0:
                continue
            if (not _equity and (_t in ('Equity', 'TotalEquity', 'StockholdersEquity')
                                  or '股東權益總額' in _nm or '權益總額' in _nm
                                  or '股東權益合計' in _nm or '權益合計' in _nm)):
                _equity = _v
            elif (not _common_stock and (_t in ('CommonStock', 'OrdinaryShare', 'ShareCapital')
                                          or '普通股股本' in _nm
                                          or ('股本' in _nm and '特別股' not in _nm))):
                _common_stock = _v
        if _equity <= 0 or _common_stock <= 0:
            return 0.0
        _shares_outstanding = _common_stock / 10.0
        _bps = _equity / _shares_outstanding
        if not (0.1 < _bps < 5000):
            return 0.0
        try:
            from src.data.core.provenance import prov_log
            prov_log('fetch_bps_from_finmind',
                     'FinMind:TaiwanStockBalanceSheet',
                     f'float:{_bps:.2f}:as_of={_latest}', ticker=sid)
        except Exception:
            pass
        return float(_bps)
    except Exception:
        return 0.0


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_bps(sid: str) -> float:
    """v18.326 SSOT(原 tab_stock.py 私有 _fetch_bps 抽出)。

    每股淨值(BPS)。PRIMARY:FinMind BS;FALLBACK:yfinance bookValue。
    """
    _bps_fm = fetch_bps_from_finmind(sid)
    if _bps_fm > 0:
        # fetch_bps_from_finmind 內已 prov_log,fetch_bps 不重複
        return _bps_fm
    try:
        import yfinance as _yf_pb
        for _sfx_pb in ('.TW', '.TWO'):
            try:
                _info_pb = _yf_pb.Ticker(f'{sid}{_sfx_pb}').info or {}
                _bps_v = _info_pb.get('bookValue')
                if _bps_v and float(_bps_v) > 0:
                    try:
                        from src.data.core.provenance import prov_log
                        prov_log('fetch_bps',
                                 f'yfinance:Ticker({sid}{_sfx_pb}).info.bookValue',
                                 f'float:{_bps_v}:fallback_from=FinMind_BS',
                                 ticker=sid)
                    except Exception:
                        pass
                    return float(_bps_v)
            except Exception:
                continue
    except Exception:
        pass
    return 0.0

