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

from shared.http_diag import scrubbed_body_head
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
        # 批 Z38(治理規則 Level 1 欄名對映 bug):現行欄名「外陸資買賣超股數(不含外資自營商)」
        # 括號內含「自營」→ 舊條件「不含自營」把它排除 → f_idx=None → 每檔外資假 0。
        # 改先挑「含外陸資且含買賣超」(現行格式只命中此欄,與 BFI82U 外資口徑同:外資及陸資、
        # 不含外資自營商);舊格式「外資買賣超股數」保留原判斷作備援,「外資自營商買賣超股數」
        # 兩條件皆不命中。
        f_idx = next((v for k, v in fi.items() if '外陸資' in k and '買賣超' in k), None)
        if f_idx is None:
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
                # 批 Z38:找不到外資欄 → NaN(缺值),不回 _pn 的 0.0 假零;交下游既有缺值路徑
                day_data[code] = {'外資': _pn(row, f_idx) if f_idx is not None else float('nan'),
                                  '投信': _pn(row, t_idx), '自營商': _pn(row, d_idx)}
        _T86_DAY_CACHE[ds] = day_data
        print(f'[TWSE T86] {ds}: {len(day_data)} 支')
        return day_data
    except Exception as e:
        print(f'[TWSE T86] {ds} 失敗: {e}')
        import time as _t_t86e
        _T86_FAIL_TS[ds] = _t_t86e.time()   # N2c:暫時性 → 負快取,不永久釘
        return {}


def _fetch_twse_inst_fallback(stock_id: str, df: pd.DataFrame, *,
                              failed: dict | None = None) -> pd.DataFrame:
    """TWSE T86 備援：T86 一次抓全市場，多股共用同一份進程快取，不重複發請求。

    failed（2026-09-27 Q5-r2；預設 None ＝ 既有行為一字不變）：傳一個 dict →
    **確定抓取失敗**時寫 `failed['twse']`：本段拋例外，或查過的每一天都沒拿到
    TWSE 的回答（日資料沒進 `_T86_DAY_CACHE` ＝ 網路／例外／短 TTL 負快取；
    `stat != OK` 與「有資料但沒有這一檔」都是回答，不算失敗）。
    """
    _answered = False       # Q5-r2:有沒有任何一天拿到 TWSE 的回答
    _asked: list = []
    try:
        rows = []
        base = datetime.date.today()
        checked = 0
        for delta in range(20):
            if checked >= 10: break
            d = base - datetime.timedelta(days=delta)
            if d.weekday() >= 5: continue
            _ds_q = d.strftime('%Y%m%d')
            day = _get_t86_day(_ds_q)
            _asked.append(_ds_q)
            if _ds_q in _T86_DAY_CACHE:
                _answered = True
            checked += 1
            if stock_id in day:
                rows.append({'date': d, **day[stock_id]})
        if rows:
            _df_tw = pd.DataFrame(rows)
            _df_tw['主力合計'] = _df_tw['外資'] + _df_tw['投信'] + _df_tw['自營商']
            df = pd.merge(df, _df_tw, on='date', how='left')
            print(f'[TWSE T86] {stock_id} 補充 {len(rows)} 日')
        elif failed is not None and _asked and not _answered:
            failed['twse'] = f'[TWSE T86] {stock_id} 失敗: {",".join(_asked)}'
    except Exception as e:
        print(f'[TWSE T86] {stock_id} 失敗: {e}')
        if failed is not None:
            failed['twse'] = f'[TWSE T86] {stock_id} 失敗: {type(e).__name__}: {e}'
    # v18.356 PR-Q5b S-PROV-1 phase 19:DataFrame 走 attrs
    try:
        if hasattr(df, 'attrs'):
            df.attrs.setdefault('source', 'src.data.core.data_loader_inst_fetchers._fetch_twse_inst_fallback:TWSE T86')
            df.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
    except Exception:
        pass
    return df


_TPEX_DAY_CACHE: dict = {}  # {日期字串: {股票代碼: {外資,投信,自營商}}} TPEx 進程級快取
# P1 v19.159(團隊稽核 QA-Med):TPEX 暫時性失敗(網路 None/例外)原本把 {} 永久釘進
# _TPEX_DAY_CACHE(無 TTL)→ 來源恢復後同 process 不再重試,上櫃股法人欄位靜默 NaN。
# 對稱補上與 T86 相同的短 TTL 負快取(N2c v19.80 當時只補 T86,漏了 TPEX)。
# 「aaData 為空」(TPEX 明確回無資料,如假日)仍永久快取 — 該日資料永不出現,語意正確。
_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打
# 批 Z39(客戶 Q-z28 診斷;零行為變更):每次**實際打出請求**後記錄該日的結果狀態,
# 供 cron 區分「TPEx 假日回空」與「交易日 TPEx 失敗」。回傳值與快取語意一字不變。
#   ok             JSON 有 aaData 且欄位驗證(buy-sell≈net)通過
#   empty          JSON 正常但 aaData 空(假日或 TPEx 交易日回空,需由 caller 對照 TWSE 判定)
#   http_none      fetch_url 回 None(網路/proxy/非 2xx)
#   json_error     回應不是 JSON(例:改版或擋爬回 HTML)
#   col_unverified 欄位驗證 for/else 失敗(仍沿用預設索引回資料,但不得當成成功)
#   exception      其他例外
# 快取命中 / 負快取命中不重設狀態(沿用上一次實際請求的結果)。
_TPEX_DAY_DIAG: dict[str, str] = {}
TPEX_DAY_STATUS_OK: str = "ok"


def get_tpex_day_status(ds: str) -> str | None:
    """`_get_tpex_day(ds)` 最近一次實際請求的狀態(見 `_TPEX_DAY_DIAG`);從未請求 → None。"""
    return _TPEX_DAY_DIAG.get(ds)


def _log_tpex_body(ds: str, status: str, r) -> None:
    """批 Z39:失敗分支印 response body 前 500 字(先洗秘密;只印 body,不印 headers/proxy/token)。"""
    print(f'[TPEx] {ds} status={status} body[:500]={scrubbed_body_head(r)!r}')


def _get_tpex_day(ds: str) -> dict:
    """抓取 TPEx 特定日期的全市場法人資料（上櫃股），進程內快取。
    回傳 {股票代碼: {'外資':float, '投信':float, '自營商':float}}，單位：張"""
    if ds in _TPEX_DAY_CACHE:
        return _TPEX_DAY_CACHE[ds]
    import time as _t_tp
    _fts = _TPEX_FAIL_TS.get(ds)
    if _fts is not None and (_t_tp.time() - _fts) < TTL_15MIN:
        return {}   # 負快取生效中(短 TTL),不重打
    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*',
           'Referer': 'https://www.tpex.org.tw/'}
    r = None   # 批 Z39:例外分支印 body 用(請求前就炸 → 無 body 可印)
    try:
        dt = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
        roc_year = gregorian_to_roc_year(dt.year)
        roc_date = f'{roc_year}/{dt.month:02d}/{dt.day:02d}'
        r = _fetch_url_dl(
            'https://www.tpex.org.tw/web/stock/3insti/daily_report/3itrade_hedge_result.php',
            params={'l': 'zh-tw', 'se': 'EW', 't': 'D', 'd': roc_date, 'o': 'json'},
            headers=HDR, timeout=5)
        if r is None:
            _TPEX_DAY_DIAG[ds] = 'http_none'
            _TPEX_FAIL_TS[ds] = _t_tp.time()   # P1:暫時性 → 短 TTL 負快取,不永久釘
            return {}
        try:
            j = r.json()
        except ValueError as e:
            # 批 Z39:非 JSON(改版/擋爬 HTML)單獨記狀態 + 印 body;回傳與負快取同原 except 分支
            _TPEX_DAY_DIAG[ds] = 'json_error'
            _log_tpex_body(ds, 'json_error', r)
            print(f'[TPEx] {ds} 失敗: {e}')
            _TPEX_FAIL_TS[ds] = _t_tp.time()
            return {}
        rows_data = j.get('aaData', [])
        if not rows_data:
            _TPEX_DAY_DIAG[ds] = 'empty'
            _log_tpex_body(ds, 'empty', r)
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
        _status = TPEX_DAY_STATUS_OK   # 批 Z39:for/else 失敗 → col_unverified

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
            _status = 'col_unverified'
            _log_tpex_body(ds, _status, r)

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
        _TPEX_DAY_DIAG[ds] = _status
        print(f'[TPEx] {ds} ({roc_date}): {len(day_data)} 支 idx=({f_idx},{t_idx},{d_idx})')
        return day_data
    except Exception as e:
        print(f'[TPEx] {ds} 失敗: {e}')
        _TPEX_DAY_DIAG[ds] = 'exception'
        if r is not None:
            _log_tpex_body(ds, 'exception', r)
        _TPEX_FAIL_TS[ds] = _t_tp.time()   # P1:暫時性 → 短 TTL 負快取,不永久釘
        return {}


def _fetch_tpex_inst_fallback(stock_id: str, df: pd.DataFrame, *,
                              failed: dict | None = None) -> pd.DataFrame:
    """TPEx 上櫃股法人備援，邏輯同 TWSE T86，使用 TPEx 三大法人 API。

    failed：同 `_fetch_twse_inst_fallback`（鍵 `'tpex'`；回答 ＝ 日資料進了 `_TPEX_DAY_CACHE`）。
    """
    _answered = False       # Q5-r2:有沒有任何一天拿到 TPEx 的回答
    _asked: list = []
    try:
        rows = []
        base = datetime.date.today()
        checked = 0
        for delta in range(20):
            if checked >= 10: break
            d = base - datetime.timedelta(days=delta)
            if d.weekday() >= 5: continue
            _ds_q = d.strftime('%Y%m%d')
            day = _get_tpex_day(_ds_q)
            _asked.append(_ds_q)
            if _ds_q in _TPEX_DAY_CACHE:
                _answered = True
            checked += 1
            if stock_id in day:
                rows.append({'date': d, **day[stock_id]})
        if rows:
            _df_tp = pd.DataFrame(rows)
            _df_tp['主力合計'] = _df_tp['外資'] + _df_tp['投信'] + _df_tp['自營商']
            df = pd.merge(df, _df_tp, on='date', how='left')
            print(f'[TPEx] {stock_id} 補充 {len(rows)} 日')
        elif failed is not None and _asked and not _answered:
            failed['tpex'] = f'[TPEx] {stock_id} 失敗: {",".join(_asked)}'
    except Exception as e:
        print(f'[TPEx] {stock_id} 失敗: {e}')
        if failed is not None:
            failed['tpex'] = f'[TPEx] {stock_id} 失敗: {type(e).__name__}: {e}'
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
