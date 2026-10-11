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
from shared.inst_labels import (  # 批 Z40 法人身分別判定 SSOT(L0)
    T86_DEALER_HEDGE_NET_COL, T86_DEALER_NET_COL, T86_DEALER_SELF_NET_COL,
    T86_FOREIGN_NET_COL, T86_FOREIGN_NET_COL_LEGACY, T86_TOTAL_NET_COL, T86_TRUST_NET_COL,
    is_foreign_dealer_label)
from shared.tpex_schema import (  # 批 Z41 TPEx 官方新網站 JSON 結構契約 SSOT(L0)
    TPEX_ALL_GROUPS, TPEX_G_DEALER, TPEX_G_DEALER_HEDGE, TPEX_G_DEALER_SELF,
    TPEX_G_FOREIGN_DEALER, TPEX_G_FOREIGN_EXCL_FD, TPEX_G_FOREIGN_INCL_FD, TPEX_G_TRUST,
    TPEX_IDX_OUT_DEALER, TPEX_IDX_OUT_FOREIGN, TPEX_IDX_OUT_TRUST, TPEX_IDX_TOTAL_NET,
    TPEX_INST_FIELDS, TPEX_INST_MAX_INVALID_ROW_RATIO, TPEX_INST_N_FIELDS, TPEX_INST_TITLE,
    check_tpex_envelope, parse_tpex_int, tpex_query_date, tpex_redirected_to_error, tpex_roc_date)
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
    回傳 {股票代碼: {'外資':float, '投信':float, '自營商':float}}，單位：張
    批 Z40 官方口徑：外資不含外資自營商、自營商＝自行＋避險；缺欄／髒值／守衛不過 → 該格 NaN（不補 0）。"""
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
        # T86 欄位名稱用「買賣超」而非「淨」，例如「外陸資買賣超股數」「投信買賣超股數」
        # 批 Z38(治理規則 Level 1 欄名對映 bug):現行欄名「外陸資買賣超股數(不含外資自營商)」
        # 括號內含「自營」→ 舊條件「不含自營」把它排除 → f_idx=None → 每檔外資假 0。
        # 批 Z40（客戶 Q-z24＝A' 官方口徑／Q-z25＝A）：欄名一律 strip 後**完全相等**比對（⛔ 子字串
        #   `next()` —— 「外資自營商買賣超股數」含「自營商買賣超股數」、「外陸資…(不含外資自營商)」含「自營」）：
        #   外資 ＝ `外陸資買賣超股數(不含外資自營商)`（2017-12-18 前舊格式備援 `外資買賣超股數`，當時官方口徑）；
        #   投信 ＝ `投信買賣超股數`；自營商 ＝ `自營商買賣超股數`（idx 11，＝自行＋避險；修前只取「自行買賣」子欄）。
        #   外資自營商欄不取（已含在自營商內）。任一類找不到欄 → 該類 NaN（Z38 只對外資，本批擴及投信／自營商）。
        fi = {n.strip(): i for i, n in enumerate(fields)}
        f_idx = fi.get(T86_FOREIGN_NET_COL)
        if f_idx is None:
            f_idx = fi.get(T86_FOREIGN_NET_COL_LEGACY)
        t_idx = fi.get(T86_TRUST_NET_COL)
        d_idx = fi.get(T86_DEALER_NET_COL)
        dself_idx = fi.get(T86_DEALER_SELF_NET_COL)
        dhedge_idx = fi.get(T86_DEALER_HEDGE_NET_COL)
        tot_idx = fi.get(T86_TOTAL_NET_COL)
        print(f'[T86] {ds} fields={fields[:5]} f_idx={f_idx} t_idx={t_idx} d_idx={d_idx} '
              f'd_self_idx={dself_idx} d_hedge_idx={dhedge_idx} total_idx={tot_idx}')

        def _iv(row, idx):
            """儲存格 → 股數 int。欄不存在／列太短／空白／'--'／非數字 → None（缺值）。
            批 Z40：修前 `_pn` 對髒儲存格回 0.0（假 0），改回缺值；真 0（'0'）仍是 0。"""
            if idx is None or idx >= len(row): return None
            try: return int(str(row[idx]).replace(',', '').replace('+', '').strip())
            except (ValueError, TypeError): return None

        def _lots(v):
            return float('nan') if v is None else round(v / 1000, 1)   # 股 → 張（單位不變）

        day_data = {}
        _n_d_mismatch = _n_d_unverified = _n_tot_mismatch = 0
        for row in j['data']:
            code = str(row[0]).strip()
            if code:
                _f, _t, _d = _iv(row, f_idx), _iv(row, t_idx), _iv(row, d_idx)
                # 批 Z40 守衛：自行、避險兩子欄都在 ⇒ 逐列驗 自行＋避險 == 自營商；不成立／子欄值不可解析
                #   ⇒ 該列自營商 NaN（不 raise 整日，避免單列髒資料毀整日）。缺合計欄但兩子欄都在 ⇒ 兩者相加；
                #   任一子欄缺 ⇒ NaN（⛔ 不得半套）。
                if dself_idx is not None and dhedge_idx is not None:
                    _ds_v, _dh_v = _iv(row, dself_idx), _iv(row, dhedge_idx)
                    if d_idx is None:
                        _d = None if (_ds_v is None or _dh_v is None) else _ds_v + _dh_v
                    elif _d is not None and (_ds_v is None or _dh_v is None):
                        _n_d_unverified += 1
                        _d = None
                    elif _d is not None and _ds_v + _dh_v != _d:
                        _n_d_mismatch += 1
                        _d = None
                # log 層級對帳：外資＋投信＋自營商 == 三大法人買賣超股數（不成立只計數）
                _tot = _iv(row, tot_idx)
                if None not in (_f, _t, _d, _tot) and _f + _t + _d != _tot:
                    _n_tot_mismatch += 1
                day_data[code] = {'外資': _lots(_f), '投信': _lots(_t), '自營商': _lots(_d)}
        if _n_d_mismatch or _n_d_unverified:
            print(f'[TWSE T86] ⚠️ {ds} 自營商守衛：自行＋避險≠自營商 {_n_d_mismatch} 列、'
                  f'子欄不可解析 {_n_d_unverified} 列 → 該列自營商為缺值(NaN)')
        if _n_tot_mismatch:
            print(f'[TWSE T86] ⚠️ {ds} 對帳：外資＋投信＋自營商≠三大法人買賣超股數 {_n_tot_mismatch} 列（僅記錄）')
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


_TPEX_DAY_CACHE: dict = {}  # {日期字串: {股票代碼: {外資,投信,自營商}}} TPEx 進程級快取（批 Z41：只收 status=ok 的日子）
# P1 v19.159(團隊稽核 QA-Med):TPEX 暫時性失敗(網路 None/例外)原本把 {} 永久釘進
# _TPEX_DAY_CACHE(無 TTL)→ 來源恢復後同 process 不再重試,上櫃股法人欄位靜默 NaN。
# 對稱補上與 T86 相同的短 TTL 負快取(N2c v19.80 當時只補 T86,漏了 TPEX)。
# ~~「aaData 為空」(TPEX 明確回無資料,如假日)仍永久快取 — 該日資料永不出現,語意正確。~~
# 批 Z41(客戶 Q-z27＝A 受控遷移)更正 —— 有意識的語意變更,不是漏刪:空表**不再永久快取**,
#   一律走短 TTL 負快取。舊理由(空表＝假日、資料永不出現)在舊端點成立,但探針實測舊收盤端點
#   **交易日也回空表**、新端點非交易日亦回 stat=ok 空表 ⇒ 空表無法區分「休市」與「來源故障」,
#   永久快取會把一次故障釘成整個進程的「沒有資料」(§1)。休市與否改由 caller 以 TWSE 同日判定。
_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打
# 批 Z39(客戶 Q-z28 診斷):每次**實際打出請求**後記錄該日的結果狀態,
# 供 cron 區分「TPEx 假日回空」與「交易日 TPEx 失敗」。
# 批 Z41(客戶 Q-z27＝A):改接官方新網站 `insti/dailyTrade` JSON,狀態值擴充(只有 ok 會回資料、進永久快取):
#   ok              外殼／欄位／逐列恆等式全部通過
#   empty           stat=ok、日期回聲正確,但 totalCount=0 且 data=[](休市或交易日故障,由 caller 對照 TWSE)
#   http_none       fetch_url 回 None 或非 200(網路/proxy/非 2xx)
#   redirect_error  被轉往官方 /errors 錯誤頁(舊端點下架的實際症狀:302 → HTML 404 頁、最終 200)
#   json_error      回應不是 JSON(改版或擋爬回 HTML)
#   schema_error    stat≠ok／日期回聲不符(含回退前一交易日)／title 不符／fields 非逐字 24 欄／列長≠24
#   identity_failed 任一列逐列恆等式不成立(7 組 買−賣＝超、G1＋G2＝G3、G5＋G6＝G7、T＝G1＋G4＋G7)
#   parse_error     不可解析列比例 > TPEX_INST_MAX_INVALID_ROW_RATIO
#   exception       其他例外
#   (Z39 的 `col_unverified`「欄位驗證失敗仍用預設索引回資料」語意已廢除 —— 新 parser 驗不過一律不回資料,
#    歸入 schema_error / identity_failed;舊狀態字串不再產生。)
# 快取命中 / 負快取命中不重設狀態(沿用上一次實際請求的結果)。
_TPEX_DAY_DIAG: dict[str, str] = {}
TPEX_DAY_STATUS_OK: str = "ok"
#: 批 Z41:`get_tpex_day_status` 可能回傳的全部狀態(只有 ok 代表有可用資料)。
TPEX_DAY_STATUSES: tuple[str, ...] = (
    "ok", "empty", "http_none", "redirect_error", "json_error", "schema_error",
    "identity_failed", "parse_error", "exception")
#: 批 Z41:櫃買中心官方新網站「三大法人買賣明細資訊」JSON(探針 run 38104351927 等驗證)。
TPEX_INST_URL: str = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"


def get_tpex_day_status(ds: str) -> str | None:
    """`_get_tpex_day(ds)` 最近一次實際請求的狀態(見 `_TPEX_DAY_DIAG`);從未請求 → None。"""
    return _TPEX_DAY_DIAG.get(ds)


def _log_tpex_body(ds: str, status: str, r) -> None:
    """批 Z39:失敗分支印 response body 前 500 字(先洗秘密;只印 body,不印 headers/proxy/token)。"""
    print(f'[TPEx] {ds} status={status} body[:500]={scrubbed_body_head(r)!r}')


def _tpex_day_fail(ds: str, status: str, r, reason: str) -> dict:
    """批 Z41:非 ok 統一出口 —— 記狀態 + 短 TTL 負快取(**不**進永久快取)+ log(含洗過的 body)。"""
    import time as _t_tpf
    _TPEX_DAY_DIAG[ds] = status
    _TPEX_FAIL_TS[ds] = _t_tpf.time()
    print(f'[TPEx] {ds} 非 ok（{status}）：{reason}')
    if r is not None:
        _log_tpex_body(ds, status, r)
    return {}


def _parse_tpex_inst_rows(ds: str, data: list) -> tuple[str, str, dict]:
    """批 Z41:`tables[0].data` 逐列驗證 → (status, reason, day_data)。純解析,無 I/O。

    - 列長 ≠ 24 → schema_error(整日)。
    - 代號 strip 後空 / 任一數值欄不可解析 / 代號重複 → 該列無效(⛔ 不當 0),該股不輸出(缺值);
      無效列 > 0 → warning;比例 > TPEX_INST_MAX_INVALID_ROW_RATIO → parse_error(整日)。
    - 有效列逐列恆等式(容差 0):7 組 買−賣＝超;G1＋G2＝G3(買/賣/超);G5＋G6＝G7(買/賣/超);
      T＝G1超＋G4超＋G7超。任一列不成立 → identity_failed(整日,不猜、不部分採用)。
    - G2(外資自營商)任一列非零 → warning(G1/G3 區分首次有數值證據,且已由 G1＋G2＝G3 逐列驗過)。
    - 輸出口徑(Q-z24 A'/Q-z25 A,同上市 T86):外資＝G1 超、投信＝G4 超、自營商＝G7 超;股 → 張(/1000,不捨入)。
    """
    n_cols = TPEX_INST_N_FIELDS
    bad_len = [i for i, row in enumerate(data)
               if not isinstance(row, (list, tuple)) or len(row) != n_cols]
    if bad_len:
        return ('schema_error',
                f'{len(bad_len)} 列長度≠{n_cols}(首例第 {bad_len[0]} 列)', {})
    parsed: dict = {}
    codes_seen: dict = {}
    invalid: list = []
    for row in data:
        code = str(row[0]).strip()
        vals = [None, None] + [parse_tpex_int(row[i]) for i in range(2, n_cols)]
        if not code or any(v is None for v in vals[2:]):
            invalid.append(code or '<空代號>')
            continue
        codes_seen[code] = codes_seen.get(code, 0) + 1
        parsed[code] = vals
    for c in [c for c, n in codes_seen.items() if n > 1]:
        parsed.pop(c, None)                         # 代號重複:無法判定取哪列 → 該股缺值
        invalid.extend([c] * codes_seen[c])
    if invalid:
        print(f'[TPEx] ⚠️ {ds} 不可解析/重複代號列 {len(invalid)}/{len(data)}'
              f'(該股缺值,不當 0):{invalid[:10]}')
        if len(invalid) / len(data) > TPEX_INST_MAX_INVALID_ROW_RATIO:
            return ('parse_error', f'不可解析列 {len(invalid)}/{len(data)} > '
                    f'{TPEX_INST_MAX_INVALID_ROW_RATIO:.0%}', {})
    fails: list = []
    n_g2_nonzero = 0
    g1, g2, g3 = TPEX_G_FOREIGN_EXCL_FD, TPEX_G_FOREIGN_DEALER, TPEX_G_FOREIGN_INCL_FD
    g4, g5, g6, g7 = TPEX_G_TRUST, TPEX_G_DEALER_SELF, TPEX_G_DEALER_HEDGE, TPEX_G_DEALER
    for code, v in parsed.items():
        for gi, (b, s, n) in enumerate(TPEX_ALL_GROUPS, start=1):
            if v[b] - v[s] != v[n]:
                fails.append(f'{code}:G{gi} 買−賣≠超')
        for k in range(3):
            if v[g1[k]] + v[g2[k]] != v[g3[k]]:
                fails.append(f'{code}:G1+G2≠G3[{k}]')
            if v[g5[k]] + v[g6[k]] != v[g7[k]]:
                fails.append(f'{code}:G5+G6≠G7[{k}]')
        if v[TPEX_IDX_TOTAL_NET] != v[g1[2]] + v[g4[2]] + v[g7[2]]:
            fails.append(f'{code}:T≠G1+G4+G7')
        if v[g2[0]] or v[g2[1]] or v[g2[2]]:
            n_g2_nonzero += 1
    if fails:
        return ('identity_failed', f'逐列恆等式不成立 {len(fails)} 處(首例 {fails[:5]})', {})
    if n_g2_nonzero:
        print(f'[TPEx] ⚠️ {ds} 外資自營商(G2)非零 {n_g2_nonzero} 列 —— G1(不含)/G3(含)首次有數值'
              '證據可區分,已逐列驗 G1+G2=G3 通過')
    day_data = {code: {'外資': v[TPEX_IDX_OUT_FOREIGN] / 1000,
                       '投信': v[TPEX_IDX_OUT_TRUST] / 1000,
                       '自營商': v[TPEX_IDX_OUT_DEALER] / 1000}
                for code, v in parsed.items()}
    return TPEX_DAY_STATUS_OK, '', day_data


def _get_tpex_day(ds: str) -> dict:
    """抓取 TPEx 特定日期的全市場法人資料（上櫃股），進程內快取。
    回傳 {股票代碼: {'外資':float, '投信':float, '自營商':float}}，單位：張

    批 Z41(客戶 Q-z27＝A 受控遷移):改接櫃買中心官方新網站 `insti/dailyTrade`(sect=EW、西元
    `YYYY/MM/DD`)。口徑同上市 `_get_t86_day`(Z40):外資＝外資及陸資(不含外資自營商)、投信、
    自營商＝自行＋避險;外資自營商不加到任何一類。守衛(任一不過 → 非 ok、回 {}、短 TTL 負快取):
    轉址 /errors、非 JSON、stat、日期回聲(頂層 YYYYMMDD + tables[0] 民國)、title、fields 逐字 24 欄、
    列長、數值可解析(無效列 ≤1%)、逐列恆等式。只有 ok 進 `_TPEX_DAY_CACHE`(永久)。
    """
    if ds in _TPEX_DAY_CACHE:
        return _TPEX_DAY_CACHE[ds]
    import time as _t_tp
    _fts = _TPEX_FAIL_TS.get(ds)
    if _fts is not None and (_t_tp.time() - _fts) < TTL_15MIN:
        return {}   # 負快取生效中(短 TTL),不重打
    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, */*',
           'Referer': 'https://www.tpex.org.tw/'}
    r = None   # 批 Z39:例外分支印 body 用(請求前就炸 → 無 body 可印)
    try:
        r = _fetch_url_dl(
            TPEX_INST_URL,
            params={'type': 'Daily', 'sect': 'EW', 'date': tpex_query_date(ds),
                    'id': '', 'response': 'json'},
            headers=HDR, timeout=5)
        if r is None:
            return _tpex_day_fail(ds, 'http_none', None, 'fetch_url 回 None')
        if getattr(r, 'status_code', 200) != 200:
            return _tpex_day_fail(ds, 'http_none', r, f'HTTP {getattr(r, "status_code", None)}')
        if tpex_redirected_to_error(r):
            return _tpex_day_fail(ds, 'redirect_error', r,
                                  f'被轉往官方錯誤頁 url={getattr(r, "url", None)!r}')
        try:
            j = r.json()
        except ValueError as e:
            # 批 Z39:非 JSON(改版/擋爬 HTML)單獨記狀態 + 印 body
            return _tpex_day_fail(ds, 'json_error', r, f'{type(e).__name__}: {e}')
        _st, _why, t0 = check_tpex_envelope(j, ds, title_exact=TPEX_INST_TITLE)
        if _st != TPEX_DAY_STATUS_OK:
            return _tpex_day_fail(ds, _st, r, _why)
        fields = tuple(str(f).strip() for f in (t0.get('fields') or []))
        if fields != TPEX_INST_FIELDS:
            return _tpex_day_fail(ds, 'schema_error', r,
                                  f'fields 非逐字 {TPEX_INST_N_FIELDS} 欄常數'
                                  f'(實得 {len(fields)} 欄:{list(fields)})')
        _st, _why, day_data = _parse_tpex_inst_rows(ds, t0['data'])
        if _st != TPEX_DAY_STATUS_OK:
            return _tpex_day_fail(ds, _st, r, _why)
        _TPEX_DAY_CACHE[ds] = day_data
        _TPEX_DAY_DIAG[ds] = TPEX_DAY_STATUS_OK
        print(f'[TPEx] {ds} ({tpex_roc_date(ds)}): {len(day_data)} 支(官方新網站 dailyTrade,守衛全過)')
        return day_data
    except Exception as e:
        return _tpex_day_fail(ds, 'exception', r, f'{type(e).__name__}: {e}')


def _fetch_tpex_inst_fallback(stock_id: str, df: pd.DataFrame, *,
                              failed: dict | None = None) -> pd.DataFrame:
    """TPEx 上櫃股法人備援，邏輯同 TWSE T86，使用 TPEx 三大法人 API。

    failed：同 `_fetch_twse_inst_fallback`（鍵 `'tpex'`；回答 ＝ 日資料進了 `_TPEX_DAY_CACHE`）。

    批 Z41（客戶 Q-z27＝A）語意更正：`_get_tpex_day` 只有 status=ok 的日子進 `_TPEX_DAY_CACHE`，
    空表（empty）／轉址／schema／恆等式失敗一律短 TTL 負快取 ⇒ 「回答」＝ 該日通過全部守衛。
    ~~空表（假日）算回答~~（舊端點把空表永久快取，因此被算成「有回答」）—— 有意識的語意變更，
    不是漏刪：交易日空表無法與故障區分，算「有回答」會把 TPEx 全面故障誤報成「這檔沒有上櫃法人資料」；
    10 個平日內必有交易日，真休市日夾在其中不會讓整段被判失敗。本函式程式碼不變。
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
    # 批 Z40（客戶 Q-z24＝A' 官方口徑／Q-z25＝A）：外資自營商（Foreign_Dealer_Self／「外資自營商…」欄）
    #   已含在自營商（自行＋避險）內 ⇒ 在 rename 之前明確 drop，不計入任何一類。
    #   （修前註解「外資自營商屬外資陣營，應歸入外資」→ 英文 Foreign_Dealer_Self 被 'foreign' 歸外資；
    #   若只改外資條件，它會掉進下方 'dealer' in cl 被加進自營商 —— 兩者都是重複計算。）
    _fd_cols = [c for c in pv.columns if c != 'date' and is_foreign_dealer_label(c)]
    if _fd_cols:
        print(f'[INST-RENAME] 略過外資自營商欄 {_fd_cols}（官方口徑：已含在自營商自行＋避險內，不另計）')
        pv = pv.drop(columns=_fd_cols)
    # 重命名：支援英文（Foreign_Investor）與中文（外陸資…）
    rn = {}
    for c in pv.columns:
        cs = str(c); cl = cs.lower()
        cb = _re_ni.split(r'[（(買賣]', cs)[0].strip()
        if ('外' in cs and '資' in cs) or cs in ('外資', '外陸資', '外資及陸資'):
            rn[c] = '外資'          # 外陸資(不含外資自營商)；外資自營商已於上方 drop（批 Z40）
        elif '投信' in cb:
            rn[c] = '投信'
        elif '自營' in cb and '外資' not in cs:  # 純國內自營商
            rn[c] = '自營商'
        elif 'foreign' in cl:
            rn[c] = '外資'          # 英文名稱（Foreign_Investor；Foreign_Dealer_Self 已於上方 drop，批 Z40）
        elif 'investment' in cl or 'trust' in cl:
            rn[c] = '投信'
        elif 'dealer' in cl:
            rn[c] = '自營商'        # Dealer_self ＋ Dealer_Hedging（自行＋避險，下方重複欄合併加總）
    print(f'[INST-RENAME] 欄位對應: {rn}')
    pv.rename(columns=rn, inplace=True)
    # 重複欄合併（pandas 3.0 相容）
    if pv.columns.duplicated().any():
        _dp = pv[['date']]
        _np = pv.drop(columns=['date'])
        # 批 Z40 跟進二（QA F4）：合併時**任一來源欄當日缺值 ⇒ 合併後該日缺值**（⛔ 修前 groupby.sum 預設
        #   min_count=0 ⇒ 全缺算成假 0（連單欄的外資／投信也被補 0，使下方主力合計的 NaN 傳遞失效）、
        #   自行／避險缺一邊算成半套 —— 同 T86 守衛「任一子欄缺 ⇒ NaN」與客戶 Q-z21「半套不當完整」）。
        _np_na = _np.isna().T.groupby(level=0).any().T
        _np = _np.T.groupby(level=0).sum().T.mask(_np_na)
        pv = pd.concat([_dp, _np], axis=1)
    main = [c for c in ['外資', '投信', '自營商'] if c in pv.columns]
    if main:
        # 批 Z40 跟進二（QA F4）：主力合計 ＝ 外資＋投信＋自營商，三類**任一缺值（NaN）或整欄不存在 ⇒ 該日主力合計 NaN**
        #   （同 Z38 `_fetch_twse_inst_fallback` 的 NaN 傳遞；⛔ 修前 `sum(axis=1)` 預設 skipna ⇒ 缺一類算成半套、
        #   三類全缺算成假 0）。下游 data_loader D2 `fillna(0)`（有 log）屬既有取捨，本處不動。
        _absent = [c for c in ['外資', '投信', '自營商'] if c not in main]
        if _absent:
            pv['主力合計'] = float('nan')
            print(f'[INST-RENAME] 主力合計缺值：缺 {_absent} 欄（不以其餘類別充當主力合計）')
        else:
            pv['主力合計'] = pv[main].sum(axis=1, skipna=False)
            _n_na = int(pv['主力合計'].isna().sum())
            if _n_na:
                print(f'[INST-RENAME] 主力合計缺值 {_n_na} 日（外資／投信／自營商任一類當日缺值）')
    return pv
