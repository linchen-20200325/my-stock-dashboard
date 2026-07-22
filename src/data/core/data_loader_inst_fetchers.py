"""data_loader_inst_fetchers.py — TWSE/TPEX 三大法人「單日 / 補抓 fallback」raw fetcher(L1)。

_get_t86_day / _get_tpex_day / _fetch_twse_inst_fallback / _fetch_tpex_inst_fallback /
_normalize_inst_pivot。B8-b v19.156 從 data_loader.py 原封拆出(降體積 + 職責單一化)。

完全自足(只依 config/proxy/shared + pandas/datetime,零耦合 data_loader 內部 helper 與
_FINMIND_META 共享狀態)→ data_loader import 回這 5 個供 StockDataLoader / 外部 caller 使用,
線性依賴無 cycle。FinMind raw fetcher(_fetch_finmind_*)因與 _FINMIND_META 共享狀態耦合,
刻意留在 data_loader。
"""
from __future__ import annotations

import datetime

import pandas as pd

from shared.roc_calendar import gregorian_to_roc_year
from shared.ttls import TTL_15MIN  # noqa: F401  (部分 fetcher inline 引用)
from src.data.proxy import fetch_url as _fetch_url_dl

# B8-b:進程級快取隨 _get_t86_day 一併搬入(原 data_loader.py:175/179,僅此函式使用)。
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
            df.attrs.setdefault('source', 'src.data.core.data_loader_inst_fetchers._fetch_twse_inst_fallback:TWSE T86')
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
            df.attrs.setdefault('source', 'src.data.core.data_loader_inst_fetchers._fetch_tpex_inst_fallback:TPEx 三大法人')
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
