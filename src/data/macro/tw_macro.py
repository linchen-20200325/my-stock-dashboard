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

from shared.fetch_monitor import monitored  # v19.96 批次4 Item1(純 stdlib,無 streamlit)
from shared.fail_cooldown import FailCooldown as _FailCooldown, NO_HIT as _FC_NO_HIT  # D2-f40
from shared.ttls import TTL_10MIN, TTL_15MIN, TTL_30MIN, TTL_1HOUR
from shared.staleness import monthly_periods_behind  # DL-f1-s13：資料月過期閘（L0 SSOT）
from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT
# DL-f1-s1:EF15M01 解析 SSOT(與排程 scripts/update_macro_history 共用同一份,§2.1)
from src.data.macro.cbc_ef15m01 import (
    EF15_FILE,
    ef15_fatal_from,
    ef15_latest_month,
    parse_cbc_ef15m01,
)
from src.data.proxy import fetch_url

__version__ = "1.1.0"


# ── v1.1 輕量 TTL cache（純 stdlib，不依賴 streamlit）──────────
# 雙 repo 共用設計約束：本模組嚴禁 import streamlit，故自帶 cache decorator。
def _ttl_cache(ttl_sec: int, maxsize: int = 32, cache_if=None, fail_cooldown: bool = False):
    """TTL+LRU cache。cache key=(args, sorted kwargs)；unhashable 引數 bypass。

    D2-f13(2026-09-29,§1.A-3(a)「只快取成功結果」):`cache_if` 為選用的 `callable(result) -> bool`,
    由被裝飾的函式自己給判定式(寫法同 `shared.fetch_monitor.monitored(success_check=...)`)。
    給了且這次結果判為 False → 結果**照常回傳、不入快取**(下次同參數呼叫重算)。
    預設 None ＝ 一律入快取(修前行為;沒給 `cache_if` 的函式行為不變)。
    ⚠️ 不入快取 ≠ 可以轟炸上游:給 `cache_if` 的函式須確認底層抓取已有退避(見各函式註解)。
    `fail_cooldown`(D2-f40,批 D2;預設 False ＝ 行為不變):底層沒有退避的函式設 True —— 判為失敗後
    同參數在 `shared.fail_cooldown.FAIL_COOLDOWN_SEC` 秒內不重算、回同一份失敗結果(§1.A-3(b));
    成功一次即解除。`cache_clear()` 同清退避紀錄。
    """
    def decorator(fn):
        _cache: dict = {}
        _cd = _FailCooldown() if (cache_if is not None and fail_cooldown) else None

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
            _gen = None
            if _cd is not None:   # D2-f40:失敗退避期內不重算
                _fhit, _gen = _cd.begin(key)
                if _fhit is not _FC_NO_HIT:
                    return _fhit
            result = fn(*args, **kwargs)
            if _cd is not None and not cache_if(result):
                return _cd.fail(key, _gen, result)   # D2-f40:不入快取,記退避
            if cache_if is not None and not cache_if(result):
                return result   # D2-f13:判為失敗／不完整 → 不入快取(回傳內容不變)
            if _cd is not None:
                _cd.success(key)
            _cache[key] = (now, result)
            if len(_cache) > maxsize:
                oldest = min(_cache.items(), key=lambda kv: kv[1][0])[0]
                _cache.pop(oldest, None)
            return result

        def _cache_clear() -> None:
            _cache.clear()
            if _cd is not None:
                _cd.clear()

        wrapper.cache_clear = _cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator

# ── 各端點 URL ────────────────────────────────────────────
TWSE_MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
FINMIND_BASE      = FINMIND_API_URL
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


# ── D2-f40(批 D2,§1.A-3(a)):下列 `_ttl_cache` 函式的入快取判準(失敗 → 不入快取 + 底層無退避 → 本層冷卻) ──
def _not_none(result) -> bool:
    """回 None ＝ 失敗(抓不到／解析失敗／空表)。"""
    return result is not None


def _no_error(result) -> bool:
    """dict 的 `error` 為 None ＝ 成功;有 error ＝ 失敗。"""
    return isinstance(result, dict) and result.get('error') is None


#: FinMind 外資那兩支「有回應但沒有外資列／筆數不足」的 error —— 與真的沒資料分不出來 → 照舊快取(不猜)。
_FII_NO_DATA_ERRORS = ('FinMind 無 Foreign_Investor 資料', '外資資料筆數不足')


def _fii_ok(result) -> bool:
    """外資兩支:只有「抓取失敗／JSON 解析失敗」算失敗;沒資料那一類照舊快取。"""
    return isinstance(result, dict) and (result.get('error') is None
                                         or result.get('error') in _FII_NO_DATA_ERRORS)


def _market_snapshot_ok(result) -> bool:
    """聚合快照:寬度或外資那一腿失敗 → 不入快取(M1B-M2 那一腿的快取政策另案,不在此判)。"""
    return (isinstance(result, dict) and _no_error(result.get('breadth'))
            and _fii_ok(result.get('fii')))


# ══════════════════════════════════════════════════════════════
# TWSE 市場寬度
# ══════════════════════════════════════════════════════════════

@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=4, cache_if=_no_error, fail_cooldown=True)  # D2-f40
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

@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=8, cache_if=_fii_ok, fail_cooldown=True)  # D2-f40
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

@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=8, cache_if=_not_none, fail_cooldown=True)  # D2-f40
def fetch_cbc_ms1_rows(url: str, *, min_rows: int = 1,
                       log_label: Optional[str] = None,
                       **fetch_kwargs) -> Optional[list]:
    """v18.238 SSOT — CBC ms1.json 端點抓取 + JSON list-shape 驗證共用 kernel.

    Consumers:
      - tw_macro._try_cbc_ms1（即時三層備援 Tier 1）
      - update_macro_history.fetch_finmind_m1m2（排程 ms1 分支；DL-f1-s40 起只做形狀／量級檢查、
        結果只進 log，**不寫進** finmind_m1m2.parquet —— 該表的列只收 EF15M01）

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


def parse_cbc_ms1_rows(data) -> tuple[Optional[pd.DataFrame], str]:
    """CBC ms1.json 的 list → (DataFrame[date, m1b, m2]（date＝資料月月初、升冪）, 說明) 或 (None, 原因)。

    DL-f1-s49（2026-10-02 批 D3）：線上 Tier 1 與排程 `update_macro_history._m1m2_ms1_candidate`
    **共用這一份**欄位辨識／日期正規化／去千分位（原本只寫在排程端；線上端不讀日期、兩欄各自
    `dropna` 後以 `iloc` 硬配）。內容逐字沿用排程端原 ms1 分支（§2.1 SSOT）。
    只做形狀與解析；列數與量級檢查留給呼叫端（兩端門檻不同）。
    """
    df = pd.DataFrame(data)
    c1 = next((c for c in df.columns
               if "M1B" in str(c).upper() or "貨幣供給額M1B" in str(c)), None)
    c2 = next((c for c in df.columns
               if str(c).strip().upper() == "M2" or "貨幣供給額M2" in str(c)), None)
    date_col = next((c for c in df.columns
                     if str(c).strip() in ("年月", "date", "yearMonth", "Date",
                                            "PERIOD", "TIME_PERIOD")), None)
    if not (c1 and c2 and date_col):
        return None, f"形狀不符：欄位對應失敗（欄位={list(df.columns)[:15]}）"
    out = df[[date_col, c1, c2]].copy()
    out.columns = ["date_raw", "m1b", "m2"]

    # 日期 normalize：支援 'YYYYMmm'（CBC PXWeb）/ 'YYYY-MM' / 'YYYY/MM' / 'YYYYMM'
    def _norm(s):
        s = str(s).strip()
        m = _re.search(r"(20\d{2})\s*M\s*(\d{1,2})", s, _re.IGNORECASE)
        if m:
            return _dt.date(int(m.group(1)), int(m.group(2)), 1)
        m = _re.search(r"(20\d{2})[-/年]?(\d{1,2})", s)
        if not m:
            return None
        return _dt.date(int(m.group(1)), int(m.group(2)), 1)
    out["date"] = out["date_raw"].apply(_norm)
    out = out.dropna(subset=["date"]).drop(columns=["date_raw"])
    # SDMX 數字可能含 thousand separator，先去掉再轉
    out["m1b"] = pd.to_numeric(
        out["m1b"].astype(str).str.replace(",", ""), errors="coerce")
    out["m2"] = pd.to_numeric(
        out["m2"].astype(str).str.replace(",", ""), errors="coerce")
    out = out.dropna().sort_values("date").reset_index(drop=True)
    if out.empty:
        return None, "日期或數值全數無法解析"
    return out, "ok"


def _try_cbc_ms1_dated(url: str) -> Optional[tuple]:
    """Tier 1:CBC ms1.json → `(m1b_yoy, m2_yoy, 資料月 date)` 或 None。

    DL-f1-s49:改以**資料月**對齊 —— 取最新資料月,再找**恰好 12 個月前**那一列當基期
    (舊碼兩欄各自 `dropna` 後 `iloc[-1]/iloc[-13]`,不讀日期、不排序,缺月即錯配)。
    同月重複 / 找不到 t−12 那一列 → 回 None(不猜,往下一層)。
    """
    tag = '[tw_macro/ms1]'
    data = fetch_cbc_ms1_rows(url, min_rows=13, timeout=12)
    if data is None:
        return None
    try:
        # D3 QA：壞月份（2026M13／M00／2026-0）會讓解析器的 `datetime.date` 拋 ValueError ——
        # 不得冒出 `fetch_cbc_m1b_m2`（否則 Tier 2 EF15M01 永遠沒機會試）。比照 EF15M01 的守法：拒用、往下。
        df, why = parse_cbc_ms1_rows(data)
    except (ValueError, TypeError, OverflowError) as e:
        print(f'{tag} ❌ {url[-40:]} 解析例外 {type(e).__name__}: {e} → 拒用,往下一層')
        return None
    if df is None:
        print(f'{tag} ❌ {url[-40:]} {why} → 往下一層')
        return None
    if df['date'].duplicated().any():
        print(f'{tag} ❌ {url[-40:]} 同一資料月出現多列 → 拒用,往下一層')
        return None
    last = df.iloc[-1]
    as_of = last['date']
    base_month = _dt.date(as_of.year - 1, as_of.month, 1)
    base = df[df['date'] == base_month]
    if base.empty:
        print(f'{tag} ❌ {url[-40:]} 最新月 {as_of:%Y-%m} 找不到 12 個月前 {base_month:%Y-%m}'
              f' 的基期 → 拒用,往下一層')
        return None
    b = base.iloc[0]
    return (
        round((float(last['m1b']) / float(b['m1b']) - 1) * 100, 2),
        round((float(last['m2']) / float(b['m2']) - 1) * 100, 2),
        as_of,
    )


def _try_cbc_ms1(url: str) -> Optional[tuple]:
    """嘗試抓 CBC ms1.json,回傳 (m1b_yoy, m2_yoy) 或 None。

    DL-f1-s49 起為 `_try_cbc_ms1_dated` 的相容外殼(拿掉資料月);`fetch_cbc_m1b_m2` 走 dated 版。
    """
    out = _try_cbc_ms1_dated(url)
    return None if out is None else out[:2]


def _try_cbc_ef15m01_dated() -> Optional[tuple]:
    """Tier 2:CBC PXWeb EF15M01(貨幣總計數-日平均數)→ (m1b_yoy, m2_yoy) 或 None。

    DL-f1-s1(2026-09-28)改寫。舊版讀頂層 `DataSet`／`Structure`(舊格式),CBC 現行回應是
    `{meta, data:{dataSets, structure}}` ⇒ 恆回 None,線上一直落到 Tier 3 `^TWII` 動能代理
    (探針 GitHub Actions run 36408641177:代理回 m1b 3.65／m2 0.91／gap +2.74,央行 EF15M01
    2026M07 實值 7.34／7.42／−0.08 —— 方向相反)。
    取數照舊(同網址、同參數、同 timeout);解析一律交給共用的
    `src.data.macro.cbc_ef15m01.parse_cbc_ef15m01`(與排程 `update_macro_history` 同一份,§2.1 SSOT),
    **本函式不自己解析任何一格**。

    回傳:「M1B、M2 官方年增率都有值」的最新資料月之 CBC **官方年增率**(%,T1 權威值;
    四捨五入到 2 位,與既有回傳一致)—— 不由餘額自算。最新月任一欄為 "-" → 往前退到兩者都有值
    的月份(餘額為 "-" 的月份解析器已整月剔除,同樣往前退)。

    對帳窗口(致命範圍)沿用排程路徑同一條規則 `ef15_fatal_from`:把「表內最新資料月」當作唯一的
    寫入月 ⇒ 最新月往前 12 個月(= 最新月官方年增率的 t−12 基期)起的每一列,自算年增率與官方
    年增率超出捨入容差 → 整表拒用;更早的列不符只印 ⚠️、不拒用(不影響本函式輸出,而每次都重解析
    全表,一筆舊歷史被修訂就會天天擋住)。對帳驗的是「標籤 → 欄位」配對;回傳月份若恰好無 t−12
    餘額可對帳,採用的仍是同一組已在窗口內驗過配對的欄位。

    任一步拒用(無回應、非 JSON、格式不符、序列名不唯一、單位／標題不符、對帳不符、可用月份早於
    對帳窗口)→ 回 None → caller 照舊往 Tier 3 走(Tier 3 帶 `is_proxy_tier=True`)。
    寧可降級,不可沉默給錯值(§1)。拒用原因由解析器或本函式印出。
    """
    tag = f'[tw_macro/{EF15_FILE}]'
    r = fetch_url(CBC_EF15M01_URL, params={'FileName': EF15_FILE}, timeout=15)
    if r is None:
        return None
    try:
        sdmx = r.json()
    except Exception as e:  # noqa: BLE001 — 非 JSON 即本層失敗;印出後回 None 交給下一層
        print(f'{tag} ❌ JSON 解析失敗 {type(e).__name__}: {e} → 往下一層')
        return None
    try:
        # 推對帳窗口也在 try 內(批 M QA):表內最新期間是 0001 年時 `ef15_fatal_from` 要回
        # 0000 年 → `datetime.date` 拋 ValueError,不得冒出 `fetch_cbc_m1b_m2`。
        latest = ef15_latest_month(sdmx)
        fatal_from = ef15_fatal_from(latest) if latest is not None else None
        df, _why = parse_cbc_ef15m01(sdmx, fatal_from, log_tag=tag)
    except (ValueError, TypeError, OverflowError) as e:
        # 期間／餘額的極端壞值(例:期間年份 0000／0001、超出 int64 的餘額)會讓推窗口或解析
        # 拋例外 → 視同拒用
        print(f'{tag} ❌ 解析例外 {type(e).__name__}: {e} → 拒用,往下一層')
        return None
    if df is None:
        return None                     # 拒用原因解析器已印出
    both = df[df['m1b_yoy'].notna() & df['m2_yoy'].notna()]
    if both.empty:
        print(f'{tag} ❌ 無任何月份同時有 M1B、M2 官方年增率 → 拒用,往下一層')
        return None
    last = both.iloc[-1]
    as_of = last['date']
    if fatal_from is not None and as_of < fatal_from:
        print(f'{tag} ❌ 可用的最新月份 {as_of:%Y-%m} 早於對帳窗口(≥ {fatal_from:%Y-%m})'
              f' → 拒用,往下一層')
        return None
    m1b_yoy = round(float(last['m1b_yoy']), 2)
    m2_yoy = round(float(last['m2_yoy']), 2)
    print(f'{tag} ✅ {as_of:%Y-%m} 官方年增率 M1B={m1b_yoy:.2f}% M2={m2_yoy:.2f}%')
    return (m1b_yoy, m2_yoy, as_of)


def _try_cbc_ef15m01() -> Optional[tuple]:
    """Tier 2 → `(m1b_yoy, m2_yoy)` 或 None。

    DL-f1-s13(2026-10-02 批 D3)起為 `_try_cbc_ef15m01_dated` 的相容外殼(拿掉資料月);
    `fetch_cbc_m1b_m2` 走 dated 版,把資料月帶進回傳並過資料月過期閘。
    """
    out = _try_cbc_ef15m01_dated()
    return None if out is None else out[:2]


def _today_tw() -> _dt.date:
    """台北時間今天(資料月過期閘的基準日;測試可 monkeypatch)。"""
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date()


def _official_month_ok(as_of, tag: str) -> bool:
    """DL-f1-s13:官方值的資料月是否仍算當期(落後 < 1 個發布期)。

    判準走 L0 SSOT `shared.staleness.monthly_periods_behind(indicator='m1b_m2')`
    (發布延遲 `MACRO_PUBLICATION_LAG_DAYS['m1b_m2']` + 既有緩衝)。落後 ≥ 1 期或判不出來
    → False:不把舊月當當期(§2.4),呼叫端照舊往下一層。
    """
    behind = monthly_periods_behind(as_of, indicator='m1b_m2', today=_today_tw())
    if behind is None or behind >= 1:
        print(f'{tag} ❌ 資料月 {as_of} 落後預期 {behind} 期(m1b_m2 發布延遲 SSOT)→ 拒用,往下一層')
        return False
    return True


def _try_twii_proxy() -> Optional[tuple]:
    """Tier 3:^TWII 動能代理(走 macro_core 經 NAS proxy)。

    回傳 `(chg20, chg60 / 3)`(單位 %,各取 2 位小數),資料不足 60 列回 None:
      - 第一個值 = ^TWII 20 日報酬 → caller 寫進 `m1b_yoy`;
      - 第二個值 = ^TWII **60 日報酬除以 3**(不是 60 日報酬本身)→ caller 寫進 `m2_yoy`。
    ⚠️ 兩者都是股價動能,不是貨幣供給年增率(代理值;見
    `shared/signal_thresholds.M1B_M2_LEG_ENABLED` docstring「線上路徑另有獨立問題」段)。
    (2026-10-01 DL-f1-s54 補述;只補 docstring,行為不變。)
    """
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


def fetch_twii_m1b_m2_proxy() -> Optional[tuple]:
    """Tier 3 `^TWII` 動能代理的公開入口 → `(m1b 代理值, m2 代理值)` 或 None。

    DL-f1-s12(2026-10-02 批 D3):`macro_snapshot.fetch_m1b_m2_block` 改成「央行 → FRED → IMF
    → 代理」的順序,代理排最後;直接委派 `_try_twii_proxy`(同一份實作,不另寫)。
    ⚠️ 回的是股價動能,不是貨幣供給年增率 —— 只顯示、不計分(客戶 2026-10-02 頁 1 ③)。
    """
    return _try_twii_proxy()


@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=4)
def fetch_cbc_m1b_m2(include_proxy: bool = True) -> dict:
    """
    抓中央銀行 M1B / M2 月資料 YoY 變動率。三層備援:

    - Tier 1: CBC public/data/ms1.json(官方公開 JSON)
    - Tier 2: cpx.cbc.gov.tw PXWeb EF15M01 —— DL-f1-s1 起由共用解析器
      `cbc_ef15m01.parse_cbc_ef15m01` 解析,回 CBC 官方年增率(見 `_try_cbc_ef15m01`)
    - Tier 3: ^TWII 動能代理(走 macro_core 經 NAS proxy)

    ⚠️ DL-f1-s1(2026-09-28)探針 run 36408641177 實測:Tier 1 未命中(`/public/data/ms1.json`
    回 HTTP 404;`/tw/public/data/ms1.json` 有回應但未通過 `fetch_cbc_ms1_rows` 檢查),Tier 2 在
    本次修正前恆回 None(讀舊格式)→ 線上實際落在 Tier 3(tier_used=3)。修正後 Tier 2 可用時,
    `m1b_yoy`／`m2_yoy` 是央行官方年增率(不是 ^TWII 報酬)。

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
            'data_month':     str | None,      'YYYY-MM' 資料月(Tier 1/2;Tier 3 代理 → None)
        }

    DL-f1-s13／s49(2026-10-02 批 D3):
      · 回傳多帶 `data_month`(schema-additive);
      · Tier 1/2 的資料月落後 ≥ 1 個發布期(`_official_month_ok`)→ 拒用、往下一層;
      · `include_proxy=False` → 不試 Tier 3(DL-f1-s12:讓 `macro_snapshot` 先試 FRED/IMF
        真值備援,代理排最後;代理值只顯示不計分,客戶 2026-10-02 頁 1 ③)。
    """
    # S-PROV-1 v18.249 phase 5:provenance schema(§2.2)
    _now_iso = pd.Timestamp.now('UTC').isoformat()
    result = {
        'm1b_yoy': None, 'm2_yoy': None, 'gap': None,
        'tier_used': None, 'is_proxy_tier': False, 'error': None,
        'source': 'CBC:M1B_M2:unknown', 'fetched_at': _now_iso,
        'data_month': None,
    }

    # ── Tier 1 ──
    for url in CBC_MS1_URLS:
        out = _try_cbc_ms1_dated(url)
        if out is not None and _official_month_ok(out[2], '[tw_macro/ms1]'):
            result['m1b_yoy'], result['m2_yoy'] = out[0], out[1]
            result['gap']        = round(out[0] - out[1], 2)
            result['tier_used']  = 1
            result['source']     = 'CBC:ms1.json:tier1'
            result['data_month'] = f'{out[2]:%Y-%m}'
            return result

    # ── Tier 2 ──
    out = _try_cbc_ef15m01_dated()
    if out is not None and _official_month_ok(out[2], f'[tw_macro/{EF15_FILE}]'):
        result['m1b_yoy'], result['m2_yoy'] = out[0], out[1]
        result['gap']        = round(out[0] - out[1], 2)
        result['tier_used']  = 2
        result['source']     = 'CBC:EF15M01:tier2'
        result['data_month'] = f'{out[2]:%Y-%m}'
        return result

    if not include_proxy:
        result['error'] = "央行兩層皆未取得"
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
# ⚠️ v19.85 更正:「TaiwanMacroEconomics」在 FinMind **不存在**(SDK 2.0.4 Dataset
#    枚舉 + 官方文件皆無此名;真名為 `TaiwanBusinessIndicator`,寬表含 monitoring
#    分數/燈號/leading)。v18.177「改付費 tier」為誤診 — 付費牆 dataset 仍會列在
#    文件,查無此名 = 名字打錯。NDC 兩 fetcher 已改走 fetch_business_indicator_series;
#    _finmind_macro_series(長表過濾)僅存 CPI/失業率 caller,同病待另源(見 STATE v19.85)。
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

# v19.x 致命03:景氣對策信號真源 = data.gov.tw dataset 6099「景氣指標及燈號」(國發會)。
# 關鍵:6099 的 resource format 是 **ZIP 打包 CSV**,非純 CSV → `_dgtw_fetch_dataset_csv`
# 的 `_fmt in ('CSV','JSON')` 判斷會跳過它 → 這就是 macro_tw_signal 在 production 恆空的根因
# (2026-07-21 export log 實錘:candidate IDs 掃到 6099 但格式判斷跳過 → 抓不到)。
# ZIP 內 `景氣指標與燈號.csv` 欄:Date(西元 YYYYMM 6 碼)/ 景氣對策信號綜合分數(9~45)/
# 景氣對策信號(官方燈號字串 藍/黃藍/綠/黃紅/紅)。走 NAS proxy(TW IP)取數。
_NDC_ZIP_DATASET_ID = '6099'
_NDC_ZIP_SCORE_KEYS = ('綜合分數', '景氣對策信號綜合分數', '景氣對策信號(分)')  # 具體優先,避免誤中燈號欄
_NDC_ZIP_COLOR_KEYS = ('景氣對策信號', '對策信號燈', '燈號')                    # 官方燈號字串欄
_NDC_ZIP_DATE_KEYS = ('date', '年月', '資料年月', '時間', '月份')             # lower() 後比對


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


def _parse_ndc_signal_zip(zip_bytes: bytes) -> Optional[pd.DataFrame]:
    """[純函式] data.gov.tw 6099 ZIP bytes → DataFrame[date, value, color]。

    抽出含「綜合分數」欄的 CSV(通常「景氣指標與燈號.csv」;以**欄位內容**判定,
    避開 ZIP 檔名編碼脆弱)。解 Date(西元 YYYYMM 6 碼,或值內藏日期)+ 分數(9~45)+
    官方燈號字串。offline 可單測。§1 Fail-Loud:ZIP/CSV 壞、缺分數欄、無有效列 → None。
    """
    import csv as _csv
    import io as _io
    import zipfile as _zip
    try:
        _zf = _zip.ZipFile(_io.BytesIO(zip_bytes))
    except Exception:
        return None
    _csv_names = [n for n in _zf.namelist() if n.lower().endswith('.csv')]
    for _nm in _csv_names:
        try:
            _raw = _zf.read(_nm)
        except Exception:
            continue
        _txt = None
        for _enc in ('utf-8-sig', 'big5', 'cp950', 'utf-8'):
            try:
                _txt = _raw.decode(_enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if not _txt:
            continue
        _rows_raw = list(_csv.DictReader(_io.StringIO(_txt)))
        if not _rows_raw:
            continue
        _cols = list(_rows_raw[0].keys())
        _score_col = next((c for c in _cols
                           if any(k in str(c) for k in _NDC_ZIP_SCORE_KEYS)), None)
        if _score_col is None:
            continue  # 這張 CSV 非「燈號」表 → 換下一張
        _date_col = next((c for c in _cols
                          if str(c).strip().lower() in _NDC_ZIP_DATE_KEYS), None)
        _color_col = next((c for c in _cols
                           if c != _score_col
                           and any(k in str(c) for k in _NDC_ZIP_COLOR_KEYS)), None)
        _rows: list[tuple] = []
        for _row in _rows_raw:
            _ym = str(_row.get(_date_col, '') if _date_col else '').strip()
            _dstr = None
            if len(_ym) == 6 and _ym.isdigit():          # Date 西元 YYYYMM
                _dstr = f'{_ym[:4]}-{_ym[4:]}-01'
            else:                                         # 兜底:任一欄藏 YYYY(-/年)MM
                for _cand in ([_ym] + [str(v) for v in _row.values()]):
                    _m = _re.search(r'(20\d{2}|19\d{2})[-/年]?(\d{1,2})', _cand)
                    if _m:
                        _dstr = f'{_m.group(1)}-{int(_m.group(2)):02d}-01'
                        break
            try:
                _sv = float(str(_row.get(_score_col, '')).strip().replace(',', ''))
            except (ValueError, TypeError):
                _sv = None
            if _dstr is None or _sv is None:
                continue
            _color = str(_row.get(_color_col, '') if _color_col else '').strip() or None
            _rows.append((_dstr, _sv, _color))
        if _rows:
            _df = pd.DataFrame(_rows, columns=['date', 'value', 'color'])
            return (_df.drop_duplicates(subset=['date'], keep='last')
                    .sort_values('date').reset_index(drop=True))
    return None


def _dgtw_ndc_signal_from_zip(label: str = 'ndc_signal') -> Optional[pd.DataFrame]:
    """[I/O] data.gov.tw 6099(景氣指標及燈號)metadata → ZIP resource → 下載 → 解析。

    走 NAS proxy(`fetch_url`)。§1 Fail-Loud:任一步失敗 → None(上游 chain 續走)。
    回 DataFrame[date, value(分數), color(官方燈號)]。
    """
    for _mu_t in _DGTW_DATASET_META_URLS:
        _mu = _mu_t.format(id=_NDC_ZIP_DATASET_ID)
        try:
            _r_meta = fetch_url(_mu, timeout=10, attempts=1,
                                headers={'Accept': 'application/json'})
            if _r_meta is None or _r_meta.status_code != 200:
                continue
            try:
                _j = _r_meta.json()
            except Exception:
                continue
            _res = (_j.get('result', {}).get('resources')
                    or _j.get('resources')
                    or _j.get('data', {}).get('resources') or [])
            _zip_url = None
            for _it in _res:
                _fmt = str(_it.get('format', '')).upper()
                _u = _it.get('url') or _it.get('resourceDownloadUrl')
                if _fmt == 'ZIP' and _u:
                    _zip_url = _u
                    break
            if not _zip_url:
                continue
            _r_zip = fetch_url(_zip_url, timeout=25, attempts=2)
            if _r_zip is None or _r_zip.status_code != 200:
                continue
            _df = _parse_ndc_signal_zip(_r_zip.content)
            if _df is not None and not _df.empty:
                print(f'[tw_macro/dgtw/{label}] 6099 ZIP → {len(_df)} rows(景氣對策信號)')
                return _df
        except Exception as _e:
            print(f'[tw_macro/dgtw/{label}] 6099 ZIP 失敗: {type(_e).__name__}: {_e}')
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
    # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
    _hdrs = {'Authorization': f'Bearer {token}'} if token else None
    r = fetch_url(FINMIND_BASE, params=params, headers=_hdrs, timeout=15)
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


def _finmind_token_from_env() -> str:
    """FINMIND_TOKEN 環境變數 bootstrap。

    production 由 app.py 啟動時把 st.secrets 同步進 os.environ(v18.x 既有機制);
    本模組鐵則不 import streamlit(檔頭「依賴限制」),故僅讀 env。無 token 時
    TaiwanBusinessIndicator 仍可匿名呼叫(免費 dataset,受較嚴 rate limit)。
    """
    import os as _os
    return _os.environ.get('FINMIND_TOKEN', '') or ''


@_ttl_cache(ttl_sec=TTL_15MIN, maxsize=4, cache_if=_not_none, fail_cooldown=True)  # D2-f40
@monitored('fetch_business_indicator_series', category='🇹🇼 台灣總經',
           frequency='monthly', registry_key='景氣先行指標（NDC）')  # v19.96(cache 內=只記真實抓)
def fetch_business_indicator_series(months_back: int = 18,
                                    token: str = "") -> Optional[pd.DataFrame]:
    """抓 FinMind `TaiwanBusinessIndicator`(國發會景氣指標官方鏡像,寬表)。

    v19.85 新增:取代誤植的 `TaiwanMacroEconomics`(不存在,見 §上方更正註)。
    欄位契約(FinMind SDK data_loader.taiwan_business_indicator 文件):
      date / leading(領先指標綜合指數) / coincident / lagging /
      monitoring(景氣對策信號綜合分數) / monitoring_color(景氣對策信號燈號)

    Returns
    -------
    pd.DataFrame[date, monitoring(, monitoring_color, leading)] 由舊到新;
    失敗回 None(§1 fail loud:print log + None,不捏造)。
    """
    today = _dt.date.today()
    params: dict = {
        'dataset':    'TaiwanBusinessIndicator',
        'start_date': (today - _dt.timedelta(days=int(months_back * 31))
                       ).strftime('%Y-%m-%d'),
        'end_date':   today.strftime('%Y-%m-%d'),
    }
    _tok = token or _finmind_token_from_env()
    # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
    _hdrs = {'Authorization': f'Bearer {_tok}'} if _tok else None
    r = fetch_url(FINMIND_BASE, params=params, headers=_hdrs, timeout=15)
    if r is None:
        print('[tw_macro/TBI] ❌ FinMind TaiwanBusinessIndicator 無回應')
        return None
    try:
        _j = r.json()
    except Exception as e:
        print(f'[tw_macro/TBI] ❌ JSON parse: {type(e).__name__}: {e}')
        return None
    rows = _j.get('data', [])
    if not rows:
        print(f"[tw_macro/TBI] ⚠️ 空 data(msg={str(_j.get('msg', ''))[:80]})")
        return None
    df = pd.DataFrame(rows)
    if 'date' not in df.columns or 'monitoring' not in df.columns:
        print(f'[tw_macro/TBI] ❌ 欄位不符: {list(df.columns)[:8]}')
        return None
    _keep = ['date'] + [c for c in ('monitoring', 'monitoring_color', 'leading')
                        if c in df.columns]
    out = df[_keep].copy()
    out['monitoring'] = pd.to_numeric(out['monitoring'], errors='coerce')
    if 'leading' in out.columns:
        out['leading'] = pd.to_numeric(out['leading'], errors='coerce')
    out = out.dropna(subset=['monitoring']).sort_values('date').reset_index(drop=True)
    if out.empty:
        print('[tw_macro/TBI] ⚠️ monitoring 全 NaN,回 None')
        return None
    return out


@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=8, cache_if=_no_error, fail_cooldown=True)  # D2-f40
@monitored('fetch_ndc_signal_history', category='🇹🇼 台灣總經',
           frequency='monthly', registry_key='景氣先行指標（NDC）')  # v19.96
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
          'source':       'FinMind:TaiwanBusinessIndicator' |
                          'data.gov.tw:6099(景氣指標及燈號)' | 'data.gov.tw' | None,
          'color_latest': str | None,   官方燈號字串(僅 TBI 源有,v19.85)
          'error':        str | None,
        }
    """
    result: dict = {
        'score_latest': None, 'score_prev': None, 'score_prev2': None,
        'trend': [], 'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
        # v19.85 additive:官方燈號字串(TaiwanBusinessIndicator monitoring_color;
        # 其他源無此欄 → None,caller 以分數自算燈號的既有邏輯不受影響)
        'color_latest': None,
        # S-PROV-1 v18.249:provenance fetched_at(source 既有,無需改 schema)
        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
    }
    # v19.85 chain:FinMind TaiwanBusinessIndicator PRIMARY(官方鏡像,含分數+燈號)
    # → dgtw 候選 ID 掃描 FALLBACK。原 _finmind_macro_series(TaiwanMacroEconomics)
    # 段拔除 — dataset 名不存在,從未命中(§3.3 反捏造,見 §上方 v19.85 更正註)。
    sub = None
    _src = None
    _tbi = fetch_business_indicator_series(months_back=max(months_back, 6),
                                           token=token)
    if _tbi is not None and not _tbi.empty:
        sub = _tbi[['date', 'monitoring']].rename(columns={'monitoring': 'value'})
        _src = 'FinMind:TaiwanBusinessIndicator'
        if 'monitoring_color' in _tbi.columns:
            _c = str(_tbi['monitoring_color'].iloc[-1] or '').strip()
            result['color_latest'] = _c or None
    # 致命03:FinMind TBI 失敗(帳號 tier / 無回應)→ data.gov.tw 6099「景氣指標及燈號」
    # ZIP 真源(官方 keyless,走 NAS proxy)。含官方燈號字串 → 補 color_latest。
    if sub is None or sub.empty:
        _zdf = _dgtw_ndc_signal_from_zip(label='ndc_signal')
        if _zdf is not None and not _zdf.empty:
            sub = _zdf[['date', 'value']]
            _src = 'data.gov.tw:6099(景氣指標及燈號)'
            _c_zip = str(_zdf['color'].iloc[-1] or '').strip()
            if _c_zip:
                result['color_latest'] = _c_zip
    # 末路 fallback:泛用 candidate-ID CSV 掃描(非 ZIP 資料集才可能命中)
    if sub is None or sub.empty:
        sub = _dgtw_ndc_indicator_series(
            _DGTW_NDC_SIGNAL_KEYWORDS, _DGTW_NDC_SIGNAL_VALUE_KEYWORDS,
            _DGTW_NDC_SIGNAL_CANDIDATE_IDS, label='ndc_signal')
        if sub is not None and not sub.empty:
            _src = 'data.gov.tw'
    if sub is None or len(sub) < 3:
        result['error'] = 'FinMind-TBI + dgtw 皆無景氣對策信號資料'
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


@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=4, cache_if=_no_error, fail_cooldown=True)  # D2-f40
@monitored('fetch_ndc_leading_index', category='🇹🇼 台灣總經',
           frequency='monthly', registry_key='景氣先行指標（NDC）')  # v19.96
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
    # v19.85 chain:FinMind TaiwanBusinessIndicator PRIMARY(leading 欄)
    # → dgtw FALLBACK。原 _finmind_macro_series(TaiwanMacroEconomics)段拔除 —
    # dataset 名不存在,從未命中(§3.3 反捏造,見 §上方 v19.85 更正註)。
    sub = None
    _src_li = None
    _tbi_li = fetch_business_indicator_series(months_back=months_back,
                                              token=token)
    if (_tbi_li is not None and 'leading' in _tbi_li.columns
            and _tbi_li['leading'].notna().sum() >= 8):
        sub = (_tbi_li.dropna(subset=['leading'])[['date', 'leading']]
               .rename(columns={'leading': 'value'}).reset_index(drop=True))
        _src_li = 'FinMind:TaiwanBusinessIndicator'
    if sub is None or sub.empty:
        sub = _dgtw_ndc_indicator_series(
            _DGTW_NDC_LEADING_KEYWORDS, _DGTW_NDC_LEADING_VALUE_KEYWORDS,
            _DGTW_NDC_LEADING_CANDIDATE_IDS, label='ndc_leading')
        if sub is not None and not sub.empty:
            _src_li = 'data.gov.tw'
    if sub is None or len(sub) < 8:
        result['error'] = 'FinMind-TBI + dgtw 皆無領先指標歷史'
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


@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=8, cache_if=_fii_ok, fail_cooldown=True)  # D2-f40
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
    # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
    _hdrs = {'Authorization': f'Bearer {token}'} if token else None
    r = fetch_url(FINMIND_BASE, params=params, headers=_hdrs, timeout=15)
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

@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=4, cache_if=_market_snapshot_ok, fail_cooldown=True)  # D2-f40
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
            'source':  'tw_macro:aggregate(breadth+fii+m1b_m2)',
            'fetched_at': UTC ISO timestamp,
        }
        各子鍵已自帶內部 prov;外層 wrapper prov 用於 audit trail 區分聚合呼叫。
    """
    return {
        'breadth': fetch_twse_breadth(),
        'fii':     fetch_finmind_foreign_investor(days_back=days_back),
        'm1b_m2':  fetch_cbc_m1b_m2(),
        # S-PROV-1 P0 v18.434:外層 aggregator prov(子鍵 prov pre-existing 保留)
        'source':     'tw_macro:fetch_tw_market_snapshot(aggregate)',
        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
    }


# ══════════════════════════════════════════════════════════════
# (v19.86 第八份 review E 死碼刪除)原 `fetch_pmi_history(months, token)`:
# 打 dataset `TaiwanEconomicIndicator`(v19.85 證實不存在於 FinMind — SDK 2.0.4
# 枚舉 + 官方文件皆無),恆回 None;且 **0 production caller**(僅 schemas.py
# docstring 提及、無任何 import/呼叫)。原為 S-H4 v18.243 自 merrill_clock 下沉,
# 但 merrill_clock 已於 v18.359 整檔刪除,此函式隨之成孤兒。
# 當期 TW PMI 由 `fetch_tw_pmi`(macro_core,8 源賽跑)供應,不需本死路徑。
# git history 可查回。§3.3 反捏造 + 死碼零殘留。
# ════════════════════════════════════════════════════════════════


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


@_ttl_cache(ttl_sec=TTL_15MIN, maxsize=8)  # CPI 月後 5-7 天發布,無需更頻繁
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
    # Phase 2 pandera P3 v18.436 #24:macro 時序 schema(date+value+source)log-mode
    try:
        from shared.schemas import validate_in_log_mode, MacroDFSchema
        validate_in_log_mode(out, MacroDFSchema, label='fetch_tw_cpi_yoy')
    except Exception:
        pass
    return out


@_ttl_cache(ttl_sec=TTL_15MIN, maxsize=8)
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
    # Phase 2 pandera P3 v18.436 #24
    try:
        from shared.schemas import validate_in_log_mode, MacroDFSchema
        validate_in_log_mode(out, MacroDFSchema, label='fetch_tw_unemployment')
    except Exception:
        pass
    return out


@_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=4)  # 1hr;政策利率變動極少
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
    # Phase 2 pandera P3 v18.436 #24
    try:
        from shared.schemas import validate_in_log_mode, MacroDFSchema
        validate_in_log_mode(out, MacroDFSchema, label='fetch_cbc_discount_rate')
    except Exception:
        pass
    return out


def _usdtwd_ok(result) -> bool:
    """D2-f13 `fetch_usdtwd_close` 的入快取判準:回 None(抓不到／sanity 過濾後為空)＝ 失敗 → 不入快取。"""
    return result is not None


@_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=4, cache_if=_usdtwd_ok)
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

    D2-f13(2026-09-29,§1.A-3(a)):回 None 時**不入** 1 小時快取(修前連 None 一起凍 1 小時,
    Yahoo 恢復後同參數仍回 None、上游 0 次呼叫);有資料的結果照舊快取 1 小時、回傳不變。
    退避(§1.A-3(b))由底層 `macro_core._fetch_yf_close_base` 承擔:抓取失敗三個出口記
    `FAIL_COOLDOWN_SEC` 秒退避;sanity 過濾後為空時,底層那份序列在它自己的 1 小時成功快取裡
    —— 兩種情形重算都不會重打上游。
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
    # Phase 2 pandera P3 v18.436 #24
    try:
        from shared.schemas import validate_in_log_mode, MacroDFSchema
        validate_in_log_mode(out, MacroDFSchema, label='fetch_usdtwd_close')
    except Exception:
        pass
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


def _china_macro_complete(result: dict) -> bool:
    """D2-f13 `fetch_china_macro` 的入快取判準:每條序列都有資料才算成功。

    任一條為空(`fetch_fred` 失敗出口／退避中回的空表、執行緒例外補的空表)＝ 結果不完整 →
    不入 30 分鐘快取、回傳內容照舊(同 D2-f23「半邊失敗不入快取」的判準)。
    api_key 空時回的 `{}` 沒有任何序列 → 照舊入快取(那是設定狀態、不是抓取失敗;修前同)。
    """
    return all(df is not None and not df.empty for df in result.values())


@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=4, cache_if=_china_macro_complete)  # OECD 月頻發布
def fetch_china_macro(fred_api_key: str = "") -> dict:
    """並行抓 5 條 China macro FRED series。

    Returns
    -------
    dict[series_id, pd.DataFrame]
        key 為 FRED series ID,value 為 macro_core.fetch_fred 結果。
        失敗 series 對應空 DataFrame;api_key 空 → 空 dict。

    §1 fail loud:單條失敗回空 DataFrame + caller 自己判 .empty,
    不偽造數值。

    D2-f13(2026-09-29,§1.A-3(a)):任一條序列為空 → 這一份**不入** 30 分鐘快取(修前整包照存:
    FRED 恢復後 30 分鐘內仍 0/5、上游 0 次請求);5 條全有資料才照舊快取、回傳不變。
    退避(§1.A-3(b))由底層 `macro_core.fetch_fred` 承擔:有資料(及 HTTP 200 但全為 '.')的序列在它的
    30 分鐘成功快取、三個失敗出口在它的 `FAIL_COOLDOWN_SEC` 秒退避 —— 期內重算都不重打上游。
    例外是 HTTP 200 之後才在 fetch_fred 內拋例外(缺欄的 KeyError、日期解析失敗、pandera SchemaError 等)
    的那條:不在退避裡、也不入成功快取,只靠 `fetch_url` 的 URL 快取擋 —— `proxy_helper._URL_CACHE`
    (TTL `_URL_CACHE_TTL` = 300 秒、上限 `_URL_CACHE_MAX` = 256 筆,全程序所有 `fetch_url` 呼叫共用;
    寫入時先清過期項、仍滿就逐出最早寫入的一筆,命中不續命;「強制重抓」會整包清空)。該筆還在時重算
    不打上游;過期、被其他取數擠出或被清空後,下一次重算就再打一次上游 —— 每次重算前都被擠出時,
    就是每次重算都重打上游。這是 `fetch_fred` 的既有缺口(`risk_radar` 的 HY OAS／10Y 兩燈直呼
    `fetch_fred`,同樣如此;本函式修前被 30 分鐘快取整包蓋住才沒露出),本次不修,已另登待辦（交接本 D2-f49）。
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
