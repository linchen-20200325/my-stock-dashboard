LI_VERSION = "v8-finmind-20260323"
"""
📊 法人買賣 + 先行指標系統 v8
=================================================
資料來源策略：
  外資大小 → FinMind API  TaiwanFuturesInstitutionalInvestors (TX)
  外(選)   → FinMind API  TaiwanOptionInstitutionalInvestors  (TXO)
  前五大/前十大/未平倉 → TAIFEX largeTraderFutQryTbl (GET) + POST
  選PCR    → TAIFEX pcRatio (POST, 已穩定)
  三大法人現貨 → TWSE BFI82U (JSON GET, 已穩定)
  成交量   → TWSE FMTQIK  (JSON GET, 已穩定)
=================================================
v5 修正：
  1. FinMind JSON API 取代 TAIFEX rowspan HTML 解析
  2. find_data_table(html, kw) 依關鍵字找正確資料表，不再依大小
  3. largeTraderFutQryTbl GET 解析 "43,469 (37,392)" 格式
"""
import os, re, sys, time  # v18.241 D3: sys.stderr for fail-loud logging
# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
# 本檔僅用 @st.cache_data + _safe_cache wrapper(ThreadPool-safe);無真 UI 呼叫。
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
import requests
import urllib3
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.config import FINMIND_API_URL, TWSE_BFI82U_URL  # Batch 10b v18.412 + Batch 8.1 v18.420 SSOT
from shared.ttls import TTL_30MIN
from shared.roc_calendar import roc_to_gregorian_year  # B3 SSOT-H2:民國→西元
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _bps():
    try:
        from src.data.stock import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s

_TWSE_S = _bps()
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN', '')

# st.set_page_config removed (module-level, causes error when imported)


# ── _safe_cache: st.cache_data の安全ラッパー ──────────────────────────
# 背景スレッド（ThreadPoolExecutor）から呼ばれても ScriptRunContext
# エラーを発生させないよう、セッションコンテキストの有無を実行時に判定する。
import functools as _fc
def _safe_cache(**kw):
    """
    st.cache_data を安全に使用するデコレータ。
    ・Streamlit のメインスレッド → キャッシュ有効
    ・バックグラウンドスレッド / 素の Python → キャッシュなしで直接実行
    """
    def decorator(fn):
        try:
            _cached = st.cache_data(**kw)(fn)
        except Exception:
            return fn
        @_fc.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                from streamlit.runtime.scriptrunner import get_script_run_ctx as _gctx
                if _gctx() is not None:
                    return _cached(*args, **kwargs)
            except Exception:
                pass
            return fn(*args, **kwargs)
        return wrapper
    return decorator
# ────────────────────────────────────────────────────────────────────────

TWSE_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json, */*",
    "Referer": "https://www.twse.com.tw/",
}
TAIFEX_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Referer": "https://www.taifex.com.tw/cht/3/futContractsDate",
    "Origin": "https://www.taifex.com.tw",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}
FINMIND_URL = FINMIND_API_URL

# build_leading_fast §6.5 TAIFEX「補強」段(前五大/前十大/精確韭菜)為逐日序列爬,
# 最多 14 天 × 每天十幾秒 timeout = 整段可達 ~100s,會超過外層併發池對 li job 的
# 80s/100s 預算 → 整張表(連已抓到的 FinMind 三大法人/期貨/PCR/融資)一起被砍成空。
# 對策:給整段 TAIFEX 補強一個總時間預算,超過就 break、用已收到的部分 + FinMind 主
# 資料組表。25s ≪ 80s li 額度,確保 build_leading_fast 在被砍前先回傳。
# (此值為效能預算非資料門檻;named const 供 SSOT/測試引用,避免 inline magic。)
_TAIFEX_ENRICH_BUDGET_S = 25

# ── 工具 ─────────────────────────────────────────────────
def roc_to_ymd(s):
    s = str(s).strip()
    # 已是 YYYYMMDD（8位西元，OpenAPI 直接回傳）
    if re.match(r"^\d{8}$", s):
        return s
    # 7位民國 YYYMMDD（openapi.twse.com.tw 回傳格式，如 '1150401' = 2026-04-01）
    if re.match(r"^\d{7}$", s):
        return f"{roc_to_gregorian_year(int(s[:3]))}{s[3:5]}{s[5:7]}"
    # ROC 格式: YYY/MM/DD 或 YY/MM/DD
    m = re.match(r"(\d{2,3})[/年](\d{1,2})[/月](\d{1,2})", s)
    return f"{roc_to_gregorian_year(int(m.group(1)))}{m.group(2).zfill(2)}{m.group(3).zfill(2)}" if m else ""

def ymd_to_slash(s): return f"{s[:4]}/{s[4:6]}/{s[6:]}"
def ymd_to_dash(s):  return f"{s[:4]}-{s[4:6]}-{s[6:]}"
def d2ymd(d): return d.strftime("%Y%m%d")
def ymd_display(s):
    dt = datetime.strptime(s, "%Y%m%d"); return f"{dt.month}月{dt.day}日"

def to_num(v, as_int=False):
    try:
        s = str(v).replace(",","").replace("+","").strip()
        # 去掉括號內容 "(37,392)" → ""
        s = re.sub(r"\(.*?\)", "", s).strip()
        if s in ("","-","nan","NaN","None","—","--","N/A"): return None
        f = float(s)
        return int(round(f)) if as_int else f
    except Exception: return None

def first_num(cell, as_int=True):
    """從 '43,469  (37,392)' 或 '45.5%  (39.2%)' 取第一個數字"""
    m = re.search(r"[\d,]+", str(cell).replace(",",""))
    if not m: return None
    # 重新抓帶逗號版本
    m2 = re.search(r"[\d,]+", str(cell))
    if not m2: return None
    try:
        f = float(m2.group(0).replace(",",""))
        return int(round(f)) if as_int else f
    except Exception: return None

def months_in_range(s, e):
    r, y, m = [], s.year, s.month
    while (y,m) <= (e.year, e.month):
        r.append(f"{y}{m:02d}"); m+=1
        if m>12: m,y=1,y+1
    return r

def extract_date(s):
    m = re.search(r"(20\d{2})[/\-](\d{1,2})[/\-](\d{1,2})", str(s))
    if m: return f"{m.group(1)}{m.group(2).zfill(2)}{m.group(3).zfill(2)}"
    m = re.search(r"(\d{3})[/\-](\d{1,2})[/\-](\d{1,2})", str(s))
    if m: return f"{roc_to_gregorian_year(int(m.group(1)))}{m.group(2).zfill(2)}{m.group(3).zfill(2)}"
    return None

# ────────────────────────────────────────────────────────
# ✅ 核心改進：依關鍵字找正確資料表（不再依大小）
# ────────────────────────────────────────────────────────
def find_data_table(html, keywords):
    """
    在 HTML 中找包含 keywords 的 <table>
    keywords: list of str，至少一個匹配即選中
    回傳 BeautifulSoup table element 或 None
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for tbl in soup.find_all("table"):
        txt = tbl.get_text()
        score = sum(1 for kw in keywords if kw in txt)
        if score > 0:
            rows = tbl.find_all("tr")
            cells = sum(len(r.find_all(["td","th"])) for r in rows)
            candidates.append((score, cells, tbl))
    if not candidates: return None
    # 優先 score 高，其次 cell 數
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]

def expand_table_elem(tbl_elem):
    """手動展開 rowspan/colspan，回傳 list of list"""
    if tbl_elem is None: return []
    matrix = {}; max_col = 0
    for ri, tr in enumerate(tbl_elem.find_all("tr")):
        ci = 0
        for cell in tr.find_all(["td","th"]):
            while (ri, ci) in matrix: ci += 1
            txt = cell.get_text(separator=" ", strip=True)
            rs  = int(cell.get("rowspan", 1))
            cs  = int(cell.get("colspan", 1))
            for r in range(rs):
                for c in range(cs):
                    matrix[(ri+r, ci+c)] = txt
            ci += cs
            if ci > max_col: max_col = ci
    max_row = max(k[0] for k in matrix)+1 if matrix else 0
    return [[matrix.get((ri,ci),"") for ci in range(max_col)] for ri in range(max_row)]

# ── TAIFEX POST ──────────────────────────────────────────
def taifex_post(url, form, _timeout_get=2, _timeout_post=5, _max_retry=1):
    """
    POST 到 TAIFEX 並回傳 HTML。
    [BUG FIX] 縮短逾時：GET 4s + POST 8s × 2 retry = 最差 24s（舊版 105s）
    避免 ThreadPoolExecutor shutdown(wait=True) 長時間阻塞。
    """
    for attempt in range(_max_retry):
        try:
            sess = requests.Session()
            hdrs = dict(TAIFEX_HDR)
            hdrs["Referer"] = url
            sess.headers.update(hdrs)
            sess.get(url, timeout=_timeout_get)
            r = sess.post(url, data=form, timeout=_timeout_post)
            r.encoding = "utf-8"
            # N4b v19.80(第三份 review):原只用 len(text)>200 判成功 — TAIFEX
            # 維護頁/錯誤頁常 >200 字會誤判。補 HTTP status,非 200 視為失敗重試。
            if r.status_code == 200 and len(r.text) > 200:
                return r.text
        except Exception:
            if attempt == _max_retry - 1:
                return ""
            time.sleep(0.3)
    return ""

# ════════════════════════════════════════════════════════
# FinMind API
# ════════════════════════════════════════════════════════
def finmind_get(dataset, data_id, start_ymd, end_ymd, token=""):
    """FinMind API v4 查詢 → DataFrame(data_id 空字串不送出避免 422;自動重試 2 次)。

    D5 v18.437:實作下沉 `src/data/core/finmind_client.py`(L1 SSOT,收斂全專案
    ~12 處手寫 FinMind GET 樣板)。本處保留原 positional 介面 + 行為
    (start/end 皆送、timeout=25、retries=2),thin re-export 不影響既有 caller。
    """
    from src.data.core.finmind_client import finmind_get as _fm_client
    return _fm_client(dataset, data_id=data_id, start_date=start_ymd,
                      end_date=end_ymd, token=token, timeout=25, retries=2)

@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def finmind_fut_oi(start_ymd, end_ymd, token=""):
    """
    外資大小 = 外資大台淨多空口 + 外資小台淨多空口 × 0.25
    主要來源: FinMind TaiwanFuturesInstitutionalInvestors
    備援來源: TAIFEX 三大法人期貨留倉（官方，免Token）
    """
    result = {}

    # ── 主要: FinMind ──
    # N4a v19.80(第三份 review):原主源段無 try/except — FinMind schema 改欄名時
    # `df["institutional_investors"]` KeyError 直接冒泡,**繞過下方 TAIFEX 備援**。
    # 包 try 讓 schema 變動降級為「主源失敗 → 走備援」(§1:log 不吞)。
    if token:
        try:
            df_tx  = finmind_get("TaiwanFuturesInstitutionalInvestors","TX", start_ymd,end_ymd,token)
            df_mtx = finmind_get("TaiwanFuturesInstitutionalInvestors","MTX",start_ymd,end_ymd,token)
            for df, factor in [(df_tx, 1.0), (df_mtx, 0.25)]:
                if df.empty: continue
                df_fi = df[df["institutional_investors"].str.contains("外資", na=False)]
                for _, row in df_fi.iterrows():
                    dk = str(row["date"]).replace("-","")
                    long_  = int(row.get("long_open_interest_balance_volume",  0) or 0)
                    short_ = int(row.get("short_open_interest_balance_volume", 0) or 0)
                    result[dk] = result.get(dk, 0) + (long_ - short_) * factor
        except Exception as _e_fmoi:
            print(f"[fut_oi] FinMind 主源失敗(走 TAIFEX 備援): "
                  f"{type(_e_fmoi).__name__}: {_e_fmoi}")
            result = {}

    # ── 備援: TAIFEX 官方三大法人留倉（免Token）──
    if not result:
        try:
            _start_dt = datetime.strptime(start_ymd, "%Y%m%d")
            _end_dt   = datetime.strptime(end_ymd,   "%Y%m%d")
            _curr = _start_dt
            while _curr <= _end_dt:
                if _curr.weekday() < 5:  # 只查交易日
                    _d_ymd = _curr.strftime("%Y%m%d")
                    _taifex_inst = taifex_post(
                        "https://www.taifex.com.tw/cht/3/futContractsDate",
                        {"queryDate": ymd_to_slash(_d_ymd), "commodityId": "TX"}
                    )
                    if _taifex_inst:
                        _tbl_inst = find_data_table(_taifex_inst, ["外資", "留倉", "口數"])
                        _matrix_inst = expand_table_elem(_tbl_inst)
                        for _row_i in _matrix_inst:
                            if len(_row_i) < 5: continue
                            if "外資" not in " ".join(_row_i[:3]): continue
                            _net_i = first_num(_row_i[3]) if len(_row_i) > 3 else None
                            if _net_i is not None:
                                result[_d_ymd] = result.get(_d_ymd, 0) + _net_i
                                break
                _curr += timedelta(days=1)
        except Exception as _eTA:
            # §1 v19.80:備援失敗不可靜默(原 except: pass) — log 後回空由 caller 判斷
            print(f"[fut_oi] TAIFEX 備援失敗: {type(_eTA).__name__}: {_eTA}")

    return {k: round(v) for k, v in result.items()}


_FUT_NIGHT_COLS = ["date", "night_close", "day_close", "chg_pts", "chg_pct"]


def _fut_night_rows(df):
    """TaiwanFuturesDaily(TX) → DataFrame(date, night_close, day_close, chg_pts, chg_pct)（純轉換,可單測）。

    每日各時段取「成交量最大」的契約（近月主力）;日盤=position、夜盤=after_market。
    夜盤漲跌 = 夜盤收 − 同日日盤收（日盤缺 → 漲跌 None,不臆造;§1 Fail-Loud）。
    夜盤時段 15:00–05:00 為台灣時間（涵蓋歐美盤 → 對隔日開盤有領先性）。
    """
    need = {"date", "trading_session", "close", "volume"}
    if df is None or getattr(df, "empty", True) or not need.issubset(df.columns):
        return pd.DataFrame(columns=_FUT_NIGHT_COLS)
    d = df.copy()
    d["close"] = pd.to_numeric(d["close"], errors="coerce")
    d["volume"] = pd.to_numeric(d["volume"], errors="coerce")
    d = d[d["close"].notna() & d["volume"].notna()]
    if d.empty:
        return pd.DataFrame(columns=_FUT_NIGHT_COLS)
    # 每 (date, session) 取成交量最大的契約 → 近月主力。
    idx = d.groupby(["date", "trading_session"])["volume"].idxmax()
    piv = d.loc[idx].pivot(index="date", columns="trading_session", values="close")
    rows = []
    for d_str, r in piv.iterrows():
        night_c = r.get("after_market")
        if pd.isna(night_c):                       # 無夜盤資料 → 跳過該日
            continue
        day_c = r.get("position")
        row = {"date": str(d_str), "night_close": float(night_c),
               "day_close": None, "chg_pts": None, "chg_pct": None}
        if not pd.isna(day_c) and float(day_c) > 0:
            row["day_close"] = float(day_c)
            row["chg_pts"] = float(night_c) - float(day_c)
            row["chg_pct"] = (float(night_c) / float(day_c) - 1.0) * 100.0
        rows.append(row)
    return pd.DataFrame(rows, columns=_FUT_NIGHT_COLS)


# ── 致命03:夜盤去 FinMind 單點 — TAIFEX futDataDown 官方備援(免token, Big5 CSV) ──
# TAIFEX 每日期貨行情下載,含「交易時段」欄(一般=日盤 / 盤後=夜盤),轉成 FinMind
# TaiwanFuturesDaily 同 schema(date/trading_session/close/volume)→ 復用 _fut_night_rows
# (挑近月主力 + 算夜盤漲跌,不重寫)。§4.1:收盤價為指數點數(無單位換算);交易日期西元
# YYYY/MM/DD。taifex_post 硬寫 utf-8 不適用(此為 Big5),故自寫 POST + big5 解碼。
_TAIFEX_FUT_DOWN_URL = "https://www.taifex.com.tw/cht/3/futDataDown"
_TAIFEX_SESSION_MAP = {"一般": "position", "盤後": "after_market"}


def _taifex_fut_daily_csv(start_ymd: str, end_ymd: str) -> str:
    """POST TAIFEX futDataDown → Big5 CSV 文字(TX 日盤+盤後)。失敗回 ''(§1)。"""
    _form = {
        "down_type": "1",
        "queryStartDate": f"{start_ymd[:4]}/{start_ymd[4:6]}/{start_ymd[6:8]}",
        "queryEndDate": f"{end_ymd[:4]}/{end_ymd[4:6]}/{end_ymd[6:8]}",
        "commodity_id": "TX",
    }
    try:
        _sess = requests.Session()
        _hdrs = dict(TAIFEX_HDR)
        _hdrs["Referer"] = "https://www.taifex.com.tw/cht/3/futDailyMarketReport"
        _sess.headers.update(_hdrs)
        _sess.get(_TAIFEX_FUT_DOWN_URL, timeout=3)
        _r = _sess.post(_TAIFEX_FUT_DOWN_URL, data=_form, timeout=12)
        if _r.status_code == 200 and len(_r.content) > 200:
            return _r.content.decode("big5", errors="ignore")
        print(f"[fut_night] TAIFEX futDataDown 非200/空: status={_r.status_code}")
    except Exception as _e:
        print(f"[fut_night] TAIFEX futDataDown 失敗: {type(_e).__name__}: {_e}")
    return ""


def _parse_taifex_fut_night_csv(csv_text: str) -> pd.DataFrame:
    """[純函式] TAIFEX futDataDown CSV → DataFrame(date, trading_session, close, volume)。

    FinMind TaiwanFuturesDaily 相容 shape → 直接餵 _fut_night_rows。§4.1 西元 YYYY/MM/DD
    → YYYY-MM-DD;交易時段 一般→position / 盤後→after_market;僅收契約 TX。offline 可單測。
    §1 Fail-Loud:欄不齊 / 壞列 / 收盤≤0 → 略過,無有效列回空(不臆造)。
    """
    import csv as _csv
    import io as _io
    _cols = ["date", "trading_session", "close", "volume"]
    if not csv_text or not csv_text.strip():
        return pd.DataFrame(columns=_cols)
    _reader = _csv.reader(_io.StringIO(csv_text))
    try:
        _hdr = [str(h).strip() for h in next(_reader)]
    except StopIteration:
        return pd.DataFrame(columns=_cols)

    def _idx(*subs):
        for _i, _h in enumerate(_hdr):
            if any(_s in _h for _s in subs):
                return _i
        return None
    _i_date, _i_con = _idx("交易日期"), _idx("契約")
    _i_ses, _i_cls, _i_vol = _idx("交易時段"), _idx("收盤價"), _idx("成交量")
    if None in (_i_date, _i_con, _i_ses, _i_cls, _i_vol):
        return pd.DataFrame(columns=_cols)          # 欄不齊 → 空(§1)
    _rows = []
    _maxi = max(_i_date, _i_con, _i_ses, _i_cls, _i_vol)
    for _rec in _reader:
        if len(_rec) <= _maxi:
            continue
        if _rec[_i_con].strip() != "TX":            # 僅大台(排除 MTX/電子/金融等)
            continue
        _session = _TAIFEX_SESSION_MAP.get(_rec[_i_ses].strip())
        if _session is None:
            continue
        _m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", _rec[_i_date].strip())
        if not _m:
            continue
        _date = f"{_m.group(1)}-{int(_m.group(2)):02d}-{int(_m.group(3)):02d}"
        try:
            _close = float(_rec[_i_cls].replace(",", "").strip())
            _volume = float(_rec[_i_vol].replace(",", "").strip())
        except (ValueError, TypeError):
            continue
        if _close <= 0:
            continue
        _rows.append({"date": _date, "trading_session": _session,
                      "close": _close, "volume": _volume})
    return pd.DataFrame(_rows, columns=_cols)


@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def finmind_fut_night(start_ymd, end_ymd, token=""):
    """台指期(TX)日盤+夜盤收盤 → 夜盤漲跌。FinMind 主 → TAIFEX 官方 futDataDown 備援。

    致命03 去 FinMind 單點:FinMind(需 token)全敗/回空 → 免 token TAIFEX 官方備援。
    盤前「隔日開盤方向」領先訊號。全源無資料 → 回空 DataFrame(§1 Fail-Loud,不造假)。
    """
    # 主源 FinMind TaiwanFuturesDaily(需 token)
    if token:
        try:
            df = finmind_get("TaiwanFuturesDaily", "TX", start_ymd, end_ymd, token)
            _fm = _fut_night_rows(df)
            if _fm is not None and not _fm.empty:
                return _fm
        except Exception as _e:  # noqa: BLE001 — log 不吞(§1),降級 TAIFEX
            print(f"[fut_night] FinMind 失敗(走 TAIFEX 備援): {type(_e).__name__}: {_e}")
    # 備援 TAIFEX 官方 futDataDown(免 token)— 復用同一 _fut_night_rows 純轉換
    print("[fut_night] 走 TAIFEX futDataDown 備援(免 token 官方日盤+夜盤)")
    return _fut_night_rows(
        _parse_taifex_fut_night_csv(_taifex_fut_daily_csv(start_ymd, end_ymd)))


@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def taifex_calls_puts_day(date_ymd):
    """
    外(選) = (BC金額 - SC金額 - BP金額 + SP金額) / 10

    ✅ 瀏覽器 + expand_table_elem 雙重驗證（rowspan 展開後全部 16 欄）：
      col[2]  = 權別（買權 / 賣權）
      col[3]  = 身份別（外資）
      col[11] = 未平倉買方金額 ← OI Buy Amount
      col[13] = 未平倉賣方金額 ← OI Sell Amount

    3/3 驗證：BC=1,245,010  SC=891,558  BP=527,883  SP=410,474
    Net=236,043 → /10 = 23,604 ✅
    """
    url  = "https://www.taifex.com.tw/cht/3/callsAndPutsDate"
    form = {
        "queryType":   "1",
        "goDay":       "",
        "doQuery":     "1",
        "dateaddcnt":  "",
        "queryDate":   ymd_to_slash(date_ymd),
        "commodityId": "TXO",
    }
    try:
        html = taifex_post(url, form)
        if not html: return None
        tbl = find_data_table(html, ["買權", "賣權", "外資", "身份別"])
        matrix = expand_table_elem(tbl)  # rowspan 展開後：全部 16 欄
        call_buy_amt = call_sell_amt = put_buy_amt = put_sell_amt = None
        for row in matrix:
            if len(row) < 14: continue
            right_type = str(row[2]).strip()   # col[2] = 買權 / 賣權
            identity   = str(row[3]).strip()   # col[3] = 身份別
            if right_type not in ("買權", "賣權"): continue
            if "外資" not in identity or "自營商" in identity: continue
            buy_amt  = to_num(row[11], as_int=False)  # ✅ col[11] OI買方金額
            sell_amt = to_num(row[13], as_int=False)  # ✅ col[13] OI賣方金額
            if buy_amt is None or sell_amt is None: continue
            if right_type == "買權":
                call_buy_amt, call_sell_amt = buy_amt, sell_amt
            else:
                put_buy_amt, put_sell_amt = buy_amt, sell_amt
        if all(v is not None for v in [call_buy_amt, call_sell_amt, put_buy_amt, put_sell_amt]):
            net = call_buy_amt - call_sell_amt - put_buy_amt + put_sell_amt
            return round(net / 10)   # 金額÷10，與參考系統一致
    except Exception as _e:  # v18.241 D3 (§1 Fail Loud)
        print(f"[taifex_calls_puts_day] swallow: {type(_e).__name__}: {_e}", file=sys.stderr)
    return None


@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def taifex_mtx_data(date_ymd):
    """
    韭菜指數 = (三大法人空方MTX OI - 三大法人多方MTX OI) / 小台全體OI × 100
    正值 = 散戶淨多（危險）；負值 = 散戶淨空（機會）

    ① futContractsDate（queryDate 單日）→ 三大法人 MTX 多/空 OI
       13欄行：col[0]=身份別  col[7]=未平倉多方口  col[9]=未平倉空方口
       15欄行：col[2]=身份別  col[9]=未平倉多方口  col[11]=未平倉空方口
    ② futDailyMarketReport（queryDate）→ MTX 各月未沖銷契約量加總（全體OI）
    """
    inst_long = inst_short = total_oi = None
    try:
        # ① futContractsDate - 正確參數（瀏覽器確認）
        url1 = "https://www.taifex.com.tw/cht/3/futContractsDate"
        html1 = taifex_post(url1, {
            "queryType":   "1",
            "goDay":       "",
            "doQuery":     "1",
            "dateaddcnt":  "",
            "queryDate":   ymd_to_slash(date_ymd),
            "commodityId": "",
        })
        if html1:
            tbl = find_data_table(html1, ["小型臺指期貨", "外資", "投信", "自營"])
            matrix = expand_table_elem(tbl)
            long_sum = short_sum = 0
            in_mtx = False
            for row in matrix:
                n = len(row)
                if n < 3: continue
                if n == 15 and "小型臺指期貨" in str(row[1]):
                    in_mtx = True
                if in_mtx and n == 15 and "小型臺指期貨" not in str(row[1]) and str(row[0]).strip().isdigit():
                    break  # 離開 MTX 區段
                if not in_mtx: continue
                if n == 15:
                    identity = str(row[2]).strip()
                    lo = to_num(row[9],  as_int=True) or 0
                    so = to_num(row[11], as_int=True) or 0
                elif n == 13:
                    identity = str(row[0]).strip()
                    lo = to_num(row[7],  as_int=True) or 0
                    so = to_num(row[9],  as_int=True) or 0
                else:
                    continue
                if identity in ("自營商","投信","外資","外資及陸資"):
                    long_sum  += lo
                    short_sum += so
            if long_sum + short_sum > 0:
                inst_long, inst_short = long_sum, short_sum
    except Exception as _e:  # v18.241 D3 (§1 Fail Loud)
        print(f"[taifex_mtx_data:legacy] swallow: {type(_e).__name__}: {_e}", file=sys.stderr)

    try:
        # ② MTX 全體OI：futDailyMarketReport 各月 未沖銷契約量 加總
        url2 = "https://www.taifex.com.tw/cht/3/futDailyMarketReport"
        html2 = taifex_post(url2, {
            "queryDate":    ymd_to_slash(date_ymd),
            "commodity_id": "MTX",
            "MarketCode":   "0",
        })
        if html2:
            tbl = find_data_table(html2, ["MTX", "未沖銷"])
            matrix = expand_table_elem(tbl)
            total = 0
            for row in matrix:
                if len(row) < 13: continue
                if str(row[0]).strip() != "MTX": continue
                oi = to_num(row[12], as_int=True)
                if oi is not None: total += oi
            if total > 0: total_oi = total
    except Exception as _e:  # v18.241 D3 (§1 Fail Loud)
        print(f"[taifex_mtx_data:oi] swallow: {type(_e).__name__}: {_e}", file=sys.stderr)

    if inst_long is None or inst_short is None or total_oi is None:
        return None
    leek_val = round((inst_short - inst_long) / total_oi * 1000) / 10
    return (leek_val, total_oi)  # 同時回傳韭菜指數和全體MTX OI

# ════════════════════════════════════════════════════════
# TWSE 成交量
# ════════════════════════════════════════════════════════
@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def twse_volume(yyyymm):
    """
    成交量（億元）from TWSE FMTQIK，多 URL 備援。
    欄位: row[0]=日期(ROC), row[2]=成交金額(元) → /1e8 = 億元
    """
    def _parse_fmtqik(d):
        result = {}
        if d.get("stat") != "OK": return result
        for row in d.get("data", []):
            dk = roc_to_ymd(row[0])
            if not dk or len(row) < 3: continue
            # 嘗試 row[2]（成交金額）；若值不合理再試 row[1]
            for idx in [2, 1]:
                try:
                    v = round(float(str(row[idx]).replace(",", "")) / 1e8, 1)
                    if 100 < v < 20000:
                        result[dk] = v
                        break
                except (ValueError, TypeError, KeyError):
                    # W5-2 §1: twse_volume 月度資料 row 解析失敗,silent skip(NaN/keep prior 為顯式旗標)
                    continue
        return result

    print(f"[VOL] twse_volume({yyyymm}) 開始")
    for _url in [
        "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK",
        "https://www.twse.com.tw/zh/afterTrading/FMTQIK",
        "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK",
    ]:
        try:
            # OpenAPI 不需要 response 參數，但仍需 date
            if "openapi" in _url:
                _p = {"date": yyyymm + "01"}
            else:
                _p = {"response": "json", "date": yyyymm + "01"}
            r = _TWSE_S.get(_url, params=_p, headers=TWSE_HDR, timeout=15)
            j = r.json()
            # OpenAPI 回傳 list 格式（欄位名稱大小寫相容）
            if isinstance(j, list):
                def _tv(item):
                    for k in ['TradeValue', 'tradeValue', 'trade_value', 'TradeAmount']:
                        if k in item and item[k]: return item[k]
                    return ''
                j = {"stat": "OK", "data": [[
                    item.get("Date", item.get("date", "")),
                    item.get("TradeVolume", item.get("tradeVolume", "")),
                    _tv(item), "", "", ""] for item in j]}
            result = _parse_fmtqik(j)
            if result:
                in_month = sum(1 for dk in result if dk.startswith(yyyymm))
                if in_month > 0:
                    print(f"[VOL] FMTQIK {yyyymm}: {len(result)} 天 ({_url.split('/')[2]})")
                    return result
                # OpenAPI returns most-recent days regardless of month param — wrong month
                print(f"[VOL] FMTQIK {yyyymm}: {len(result)} 天但非本月，改用備援")
        except Exception as _e:
            print(f"[VOL] FMTQIK {yyyymm} {_url.split('/')[-1]}: {type(_e).__name__}")
    print(f"[VOL] FMTQIK {yyyymm} 改用 macro_core ^TWII Volume 備援")
    # ── [Step 4] 備援：macro_core.fetch_yf_ohlcv（走 NAS proxy 直打 Yahoo Chart API）
    try:
        from src.data.macro import fetch_yf_ohlcv as _mc_ohlcv
        _df_yf = _mc_ohlcv("^TWII", range_="9mo", interval="1d")
        if not _df_yf.empty and "Volume" in _df_yf.columns:
            _res_yf = {}
            _df_m = _df_yf[_df_yf.index.strftime("%Y%m") == yyyymm]
            for _idx, _row in _df_m.iterrows():
                _dk = _idx.strftime("%Y%m%d")
                try:
                    _raw = float(_row["Volume"])
                    for _div in [1e8, 1e4, 1e3]:
                        _v = round(_raw / _div, 1)
                        if 5 < _v < 20000:
                            _res_yf[_dk] = _v
                            break
                except Exception:
                    pass
            if _res_yf:
                print(f"[VOL] macro_core ^TWII {yyyymm}: {len(_res_yf)} 天")
                return _res_yf
    except Exception as _yfe:
        print(f"[VOL] macro_core ^TWII {yyyymm}: {type(_yfe).__name__}")

    print(f"[VOL] {yyyymm} 所有備援均失敗，成交量無資料")
    return {}


@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def twse_volume_daily(ymd8):
    """
    單日成交量 from TWSE MI_INDEX（搜尋所有 tables，row[2]=成交金額備援 row[1]）
    ymd8: YYYYMMDD (e.g., '20260320')
    """
    try:
        r = _TWSE_S.get("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
                        params={"response":"json","date":ymd8},
                        headers=TWSE_HDR, timeout=12)
        d = r.json()
        if d.get("stat") != "OK": return None
        tables = d.get("tables", [])
        # 搜尋所有 tables，找「總計」列；row[2]=成交金額，row[1] 備援
        for tbl in tables:
            for row in tbl.get("data", []):
                if not row or "總計" not in str(row[0]): continue
                for idx in [2, 1]:
                    if idx >= len(row): continue
                    try:
                        amt = round(float(str(row[idx]).replace(",","")) / 1e8, 1)
                        if 100 < amt < 20000: return amt
                    except (ValueError, TypeError, IndexError):
                        # W5-2 §1: twse_volume_daily row 解析失敗 silent skip(下游 None 為顯式旗標)
                        continue
        return None
    except Exception as _e:  # v18.241 D3 (§1 Fail Loud)
        print(f"[twse_volume_daily] swallow: {type(_e).__name__}: {_e}", file=sys.stderr)
        return None

# ════════════════════════════════════════════════════════
# TWSE 三大法人 BFI82U
# ════════════════════════════════════════════════════════
@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def twse_institutional_day(date_ymd):
    try:
        r = _TWSE_S.get(TWSE_BFI82U_URL,
                        params={"response":"json","dayDate":date_ymd},
                        headers=TWSE_HDR, timeout=15)
        d = r.json()
        if d.get("stat") != "OK": return {}
        result = {}; self_diff = None; hedge_diff = None
        for row in d.get("data", [])[:-1]:
            if len(row) < 4: continue
            name = str(row[0]).strip()
            diff = to_num(row[3])
            if diff is None: continue
            diff_bn = round(diff / 1e8, 1)
            if "自行買賣" in name:   self_diff = diff_bn
            elif "避險" in name:     hedge_diff = diff_bn
            elif name == "投信":     result["投信"] = diff_bn
            elif "外資及陸資" in name and name != "外資自營商":
                result["外資"] = diff_bn
        if self_diff is not None and hedge_diff is not None:
            result["自營"] = round(self_diff + hedge_diff, 1)
        elif self_diff is not None:
            result["自營"] = self_diff
        return result
    except Exception as _e:  # v18.241 D3 (§1 Fail Loud)
        print(f"[twse_institutional_day] swallow: {type(_e).__name__}: {_e}", file=sys.stderr)
        return {}

# ════════════════════════════════════════════════════════
# TWSE 融資融券 MI_MARGN（單日）
# ════════════════════════════════════════════════════════
def _twse_margin_day(ymd8: str) -> dict:
    """
    TWSE MI_MARGN 單日全市場合計 → {'融資餘額': 億元, '融券餘額': 億元}
    邏輯完全對齊 daily_checklist.fetch_margin_balance（已驗證有效）
    失敗回傳 {}
    """
    for _sel in ["MS", "ALL"]:
        try:
            r = _TWSE_S.get(
                "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN",
                params={"date": ymd8, "selectType": _sel, "response": "json"},
                headers={**TWSE_HDR, "Referer": "https://www.twse.com.tw/zh/trading/margin/mi-margn.html"},
                timeout=15)
            j = r.json()
            if j.get("stat") != "OK":
                continue
            data   = j.get("data", [])
            if not data:
                continue
            fields = [str(f) for f in j.get("fields", [])]
            print(f"[TWSE_MARGN/{_sel}/{ymd8}] fields={fields[:10]}")
            # 對齊 fetch_margin_balance 的欄位偵測
            fa_col = next((i for i, f in enumerate(fields)
                           if "融資" in f and "餘額" in f and "限" not in f), None)
            if fa_col is None:
                fa_col = 6
            fv_col = next((i for i, f in enumerate(fields)
                           if "融券" in f and "餘額" in f and "限" not in f), None)
            if fv_col is None:
                fv_col = 13
            entry = {}
            for row in reversed(data):
                if len(row) <= max(fa_col, fv_col):
                    continue
                try:
                    fa_raw = float(str(row[fa_col]).replace(",", "").replace(" ", ""))
                    # 對齊 fetch_margin_balance 的閾值
                    if fa_raw > 100_000_000:   # 太大，跳過
                        continue
                    if fa_raw > 10_000_000:    # 合理範圍
                        entry["融資餘額"] = round(fa_raw / 100_000, 0)
                    elif fa_raw > 1_000_000:   # 備用範圍（萬元單位）
                        r2 = round(fa_raw / 10_000, 0)
                        if 500 < r2 < 10000:
                            entry["融資餘額"] = r2
                    # 融券餘額（使用同欄位檢測策略）
                    if len(row) > fv_col:
                        fv_raw = float(str(row[fv_col]).replace(",", "").replace(" ", ""))
                        if fv_raw > 100_000_000:
                            pass  # 跳過
                        elif fv_raw > 100_000:    # >10億千元
                            entry["融券餘額"] = round(fv_raw / 100_000, 0)
                        elif fv_raw > 10_000:
                            r3 = round(fv_raw / 10_000, 0)
                            if 1 < r3 < 1000:
                                entry["融券餘額"] = r3
                    if entry.get("融資餘額"):
                        print(f"[TWSE_MARGN/{_sel}/{ymd8}] ✅ 融資={entry.get('融資餘額')}億 融券={entry.get('融券餘額')}億")
                        return entry
                except Exception:
                    continue
        except Exception as _e:
            print(f"[TWSE_MARGN/{_sel}/{ymd8}] {_e}")
    return {}

# ════════════════════════════════════════════════════════
# TAIFEX 選擇權 PCR（批量）
# ✅ 已穩定，保持不變
# ════════════════════════════════════════════════════════
@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def taifex_pcr(start_ymd, end_ymd):
    url  = "https://www.taifex.com.tw/cht/3/pcRatio"
    form = {"queryStartDate":ymd_to_slash(start_ymd),"queryEndDate":ymd_to_slash(end_ymd)}
    result = {}
    try:
        html = taifex_post(url, form)
        if not html: return result
        # 找含「比率」的資料表
        tbl = find_data_table(html, ["比率", "Put", "Call"])
        matrix = expand_table_elem(tbl)
        for row in matrix:
            if len(row) < 3: continue
            d = extract_date(row[0])
            if not d: continue
            val = to_num(row[-1])
            if val is None: continue
            if 0.1 < val < 10: val = round(val * 100, 1)
            if 20 < val < 500 and d not in result:
                result[d] = round(val, 1)
    except Exception as _e:  # v18.241 D3 (§1 Fail Loud)
        print(f"[taifex_pcr] swallow: {type(_e).__name__}: {_e}", file=sys.stderr)
    return result

# ════════════════════════════════════════════════════════
# TAIFEX 大額交易人（逐日）
# ✅ 修正：largeTraderFutQryTbl GET（今日）+ POST（歷史）
#    解析格式 "43,469  (37,392)" → 取 43,469
#    找「臺股期貨」+ 「所有」列
# ════════════════════════════════════════════════════════
@_safe_cache(ttl=TTL_30MIN, show_spinner=False)
def taifex_large_trader(date_ymd):
    # 嘗試 GET（今日）或 POST（歷史）
    html = ""
    today_ymd = date.today().strftime("%Y%m%d")
    if date_ymd == today_ymd:
        try:
            r = _bps().get("https://www.taifex.com.tw/cht/3/largeTraderFutQryTbl",
                           headers=TAIFEX_HDR, timeout=15)
            r.encoding = "utf-8"
            if len(r.text) > 200: html = r.text
        except (requests.RequestException, requests.Timeout) as _e_tx:
            # W5-2 §1: TAIFEX 直連失敗(走 POST fallback),補 log
            print(f"[leading_indicators TAIFEX] 直連失敗,改 POST:{_e_tx}")
    if not html:
        html = taifex_post(
            "https://www.taifex.com.tw/cht/3/largeTraderFutQry",
            {
                "queryDate":   ymd_to_slash(date_ymd),
                "contractId":  "TX",    # ✅ 真實參數名：contractId（不是 commodityId）
                "contractId2": "",      # ✅ hidden field（必填，空字串）
                "datecount":   "",      # ✅ hidden field（必填，空字串）
            }
        )
    if not html: return {}
    try:
        # 找含「臺股期貨」+「前五大」+「全市場」的資料表
        # ✅ 加入「臺股期貨」確保不選到頁面導覽表格
        tbl = find_data_table(html, ["臺股期貨", "前五大交易人", "前十大交易人", "全市場未沖銷"])
        matrix = expand_table_elem(tbl)

        # 表格展開後欄位結構（rowspan 已展開，每列固定 11 欄）：
        # col[0] = 契約名稱  col[1] = 到期月份
        # col[2] = 前五大買方口數  col[3] = 前五大買方%
        # col[4] = 前十大買方口數  col[5] = 前十大買方%
        # col[6] = 前五大賣方口數  col[7] = 前五大賣方%
        # col[8] = 前十大賣方口數  col[9] = 前十大賣方%
        # col[10] = 全市場未沖銷部位數（未平倉）
        #
        # 計算：
        #   前五大  = col[2] - col[6]   (買方所有契約 - 賣方所有契約)
        #   前十大  = col[4] - col[8]
        #   未平倉  = col[10] 直接取

        for row in matrix:
            if len(row) < 11: continue
            row_str = " ".join(row)
            # 找「臺股期貨」且「所有契約」列
            if not re.search(r"臺股期貨|TX\+MTX", row_str): continue
            if not re.search(r"所有", row_str): continue

            # 使用固定欄位索引提取數值（格式如 "43,469  (37,392)"，取第一個數）
            top5_buy  = first_num(row[2])
            top10_buy = first_num(row[4])
            top5_sell = first_num(row[6])
            top10_sell= first_num(row[8])
            oi_total  = first_num(row[10])  # 全市場未沖銷（直接取，無需計算）

            if any(v is None for v in [top5_buy, top10_buy, top5_sell, top10_sell]):
                continue

            return {
                "前五大": top5_buy  - top5_sell,   # 買方所有契約 - 賣方所有契約
                "前十大": top10_buy - top10_sell,
                "未平倉": oi_total,                 # 直接取「全市場未沖銷部位數」
            }
    except Exception as _e:  # v18.241 D3 (§1 Fail Loud)
        print(f"[taifex_large_trader] swallow: {type(_e).__name__}: {_e}", file=sys.stderr)
    return {}

# ════════════════════════════════════════════════════════
# 數據組合
# ════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════
# 輔助函式（供台股AI戰情室使用）
# ════════════════════════════════════════════════════════
def build_leading_indicators(start, end, token="", progress_cb=None):
    """
    主函式：抓取所有先行指標數據，回傳 DataFrame
    progress_cb(i, total, msg): 可選的進度回調
    """
    s_ymd, e_ymd = d2ymd(start), d2ymd(end)
    vol = {}
    for m in months_in_range(start, end): vol.update(twse_volume(m))
    fut_dict = finmind_fut_oi(s_ymd, e_ymd, token)
    pcr_dict = taifex_pcr(s_ymd, e_ymd)
    all_dates = sorted(d for d in vol if s_ymd <= d <= e_ymd)
    inst_data = {}; lt_data = {}; opt_data = {}; mtx_data = {}
    for i, d in enumerate(all_dates):
        if progress_cb: progress_cb(i, len(all_dates), f"逐日查詢 {i+1}/{len(all_dates)} （{ymd_display(d)}）")
        inst_data[d] = twse_institutional_day(d)
        lt_data[d]   = taifex_large_trader(d)
        opt_data[d]  = taifex_calls_puts_day(d)
        mtx_data[d]  = taifex_mtx_data(d)
        time.sleep(0.3)
    rows = []
    for d in all_dates:
        inst = inst_data.get(d, {}); lt = lt_data.get(d, {})
        rows.append({
            "_date":d, "日期":ymd_display(d), "成交量":f"{vol[d]:.1f}億",
            "外資":inst.get("外資"), "投信":inst.get("投信"), "自營":inst.get("自營"),
            "外資大小":fut_dict.get(d),
            "前五大留倉":lt.get("前五大"), "前十大留倉":lt.get("前十大"),
            "選PCR":pcr_dict.get(d), "外(選)":opt_data.get(d),
            "未平倉口數":lt.get("未平倉"), "韭菜指數":mtx_data.get(d),
        })
    df = pd.DataFrame(rows)
    # S-PROV-1 phase 18 v18.264 — provenance(多源 aggregator,記錄完整鏈)
    if not df.empty:
        df["source"] = "TWSE+FinMind+TAIFEX:leading_indicators:full"
        df["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    return df



# ════════════════════════════════════════════════════════════════
# v18.342 PR-L2:stale cache fallback helper(L0 純函式,易於 unit test)
# user 2026-06-28「如果遇假日則抓前一次的」+ §2.4「過期 cache 須帶 is_stale 旗標,
# 禁靜默」。週末/假日 FinMind 自然無新資料,build_leading_fast 返回 None 會讓 UI
# 整段空白;改:當次抓空 → 改返回最近一次成功的 pickle + is_stale=True attrs。
# ════════════════════════════════════════════════════════════════
def _load_stale_pickle(cache_path):
    """嘗試載入指定 pickle 路徑(忽略 TTL),回傳 (df, age_minutes) 或 (None, None)。"""
    import os as _os_sp, pickle as _pk_sp, time as _tm_sp, sys as _sys_sp
    if not _os_sp.path.exists(cache_path):
        return (None, None)
    try:
        _age_sec = _tm_sp.time() - _os_sp.path.getmtime(cache_path)
        _age_min = round(_age_sec / 60, 1)
        with open(cache_path, 'rb') as _f:
            _df = _pk_sp.load(_f)
        print(f'[LI-v8] 預載過期 pickle age={_age_min}min,當次失敗時用')
        return (_df, _age_min)
    except Exception as _e:
        print(f'[LI-v8] stale cache preload fail: {type(_e).__name__}: {_e}',
              file=_sys_sp.stderr)
        return (None, None)


def _mark_stale(df, age_min):
    """在 df.attrs 標記 is_stale=True + stale_age_min(下游 UI chip 用)。"""
    if df is None:
        return df
    try:
        df.attrs['is_stale'] = True
        if age_min is not None:
            df.attrs['stale_age_min'] = age_min
    except Exception:
        pass
    return df


# ════════════════════════════════════════════════════════════════
# 快速版先行指標（只用 FinMind 批次 API，無逐日爬蟲）
# 資料源：
#  ① 外資期貨留倉 → FinMind TaiwanFuturesInstitutionalInvestors (TX+MTX)
#  ② 選擇權 PCR  → TAIFEX pcRatio POST (批次，單次呼叫)
#  ③ 三大法人現貨 → TWSE BFI82U 逐日（最多抓5天，快速）
#  ④ 韭菜指數    → FinMind TaiwanFuturesInstitutionalInvestors 小台散戶淨多
#  備援：TAIFEX futContractsDate 外資留倉（免token，GET）
# ════════════════════════════════════════════════════════════════
def build_leading_fast(days=7, token=""):
    """
    先行指標 v8 — 純 FinMind，完全無 TAIFEX，零多線程
    所有資料從 FinMind 4 個 API 批次取得，不依賴任何爬蟲。
    """
    import os as _os_li
    import pickle as _pk_li
    import hashlib as _hs_li
    import time as _tm_li
    # 跨 session pickle 快取（沿用 fetch_single 模式：回傳新物件、線程安全，避開
    # @st.cache_data 的 DataFrame mutation 陷阱）。先行指標日頻（收盤後更新）→ 30 分鐘 TTL。
    # 只在 FinMind 主來源真的有回資料時才寫快取（見函式尾 _fm_ok），避免暫時性故障被黏住。
    from shared.cache_layer import _PKL_DIR as _pkl_dir_li  # D14b v19.75:可攜 cache dir SSOT
    _ck_li = _os_li.path.join(_pkl_dir_li, _hs_li.md5(f'lead_fast_{days}_{token}'.encode()).hexdigest() + '.pkl')
    _os_li.makedirs(_pkl_dir_li, exist_ok=True)
    if _os_li.path.exists(_ck_li) and (_tm_li.time() - _os_li.path.getmtime(_ck_li)) / 60 < 30:
        try:
            with open(_ck_li, 'rb') as _f_li:
                _df_fresh = _pk_li.load(_f_li)
                # 新鮮 cache → 確保無 is_stale 旗標(同源寫入後直接返回)
                if hasattr(_df_fresh, 'attrs'):
                    _df_fresh.attrs.pop('is_stale', None)
                    _df_fresh.attrs.pop('stale_age_min', None)
                return _df_fresh
        except Exception as _e_cf:
            print(f'[LI-v8] fresh cache load fail: {type(_e_cf).__name__}: {_e_cf}',
                  file=__import__('sys').stderr)

    # v18.342 PR-L2:預載過期 pickle 供 stale fallback(若當次抓不到再用)。
    _stale_fallback_df, _stale_age_min = _load_stale_pickle(_ck_li)
    import datetime as _dt
    today  = _dt.date.today()
    s_date = today - _dt.timedelta(days=days + 14)
    s_ymd  = s_date.strftime("%Y%m%d")
    e_ymd  = today.strftime("%Y%m%d")
    print(f"[LI-v8] ===== 開始 {s_ymd}~{e_ymd} token={bool(token)} days={days} =====")
    import sys; sys.stdout.flush()

    # ═══ 1. FinMind 4 API 並行呼叫（彼此獨立 → 省 ~3-4x 關鍵路徑時間）═══
    # finmind_get 每次自建 requests.Session、無共享狀態、回傳新 DataFrame → 線程安全。
    from concurrent.futures import ThreadPoolExecutor as _TPE_li
    _li_specs = [
        ("TaiwanFuturesInstitutionalInvestors",    "TX"),
        ("TaiwanFuturesInstitutionalInvestors",    "MTX"),
        ("TaiwanOptionInstitutionalInvestors",     "TXO"),
        ("TaiwanStockTotalInstitutionalInvestors", ""),
    ]
    with _TPE_li(max_workers=4) as _ex_li:
        _li_futs = [_ex_li.submit(finmind_get, _ds, _id, s_ymd, e_ymd, token)
                    for _ds, _id in _li_specs]
        df_tx, df_mtx, df_txo, df_inst = [_f.result() for _f in _li_futs]
    print(f"[LI-v8] FinMind TX={len(df_tx)} MTX={len(df_mtx)} TXO={len(df_txo)} inst={len(df_inst)}")
    import sys; sys.stdout.flush()
    # FinMind 主來源是否有回資料 → 決定函式尾是否寫快取（避免暫時性失敗被快取黏住）
    _fm_ok = (len(df_tx) + len(df_mtx) + len(df_txo) + len(df_inst)) > 0
    if not _fm_ok:
        print("[LI-v8] ❌ 所有 FinMind API 均返回空 → 可能速率限制或網路問題")

    # ═══ 2. 外資期貨留倉 ════════════════════════════════════════
    fut_net = {}
    for df, factor in [(df_tx, 1.0), (df_mtx, 0.25)]:
        if df.empty: continue
        for _, row in df[df["institutional_investors"].str.contains("外資", na=False)].iterrows():
            dk = str(row["date"]).replace("-", "")
            lo = int(pd.to_numeric(row.get("long_open_interest_balance_volume",  0), errors="coerce") or 0)
            sh = int(pd.to_numeric(row.get("short_open_interest_balance_volume", 0), errors="coerce") or 0)
            fut_net[dk] = fut_net.get(dk, 0) + round((lo - sh) * factor)
    print(f"[LI-v8] 外資期貨 {len(fut_net)} 天")

    # ═══ 3. PCR + 外(選) 從 TXO 計算（FinMind 法人估算，無需 TAIFEX）
    pcr_dict = {}
    opt_dict = {}
    if not df_txo.empty:
        agg = {}
        for _, row in df_txo.iterrows():
            dk = str(row["date"]).replace("-", "")
            if dk not in agg:
                agg[dk] = dict(callV=0, putV=0, extBC=0.0, extSC=0.0, extBP=0.0, extSP=0.0)
            b   = agg[dk]
            cp  = str(row.get("call_put", ""))
            ii  = str(row.get("institutional_investors", ""))
            loV = int(pd.to_numeric(row.get("long_open_interest_balance_volume",  0), errors="coerce") or 0)
            shV = int(pd.to_numeric(row.get("short_open_interest_balance_volume", 0), errors="coerce") or 0)
            loA = float(pd.to_numeric(row.get("long_open_interest_balance_amount",  0), errors="coerce") or 0)
            shA = float(pd.to_numeric(row.get("short_open_interest_balance_amount", 0), errors="coerce") or 0)
            ext = ("外資" in ii) and ("自營" not in ii)
            if "買權" in cp:
                b["callV"] += loV + shV
                if ext: b["extBC"] += loA; b["extSC"] += shA
            elif "賣權" in cp:
                b["putV"]  += loV + shV
                if ext: b["extBP"] += loA; b["extSP"] += shA
        for dk, b in agg.items():
            if b["callV"] > 0:
                pcr_dict[dk] = round(b["putV"] / b["callV"] * 100, 1)
            opt_dict[dk] = round((b["extBC"] - b["extSC"] - b["extBP"] + b["extSP"]) / 10)
        print(f"[LI-v8] PCR(FinMind估算)={len(pcr_dict)} 天  外(選)={len(opt_dict)} 天")

    # ═══ 4. 三大法人現貨 ════════════════════════════════════════
    inst_dict = {}
    if not df_inst.empty:
        df_i = df_inst.copy()
        df_i["_ymd"] = df_i["date"].astype(str).str.replace("-", "")
        for dk, grp in df_i.groupby("_ymd"):
            if not (s_ymd <= dk <= e_ymd): continue
            rd = {}
            for _, r in grp.iterrows():
                nm  = str(r.get("name", ""))
                net = round((float(r.get("buy",  0) or 0) - float(r.get("sell", 0) or 0)) / 1e8, 1)
                if   nm == "Foreign_Investor":                rd["外資"] = round(rd.get("外資", 0) + net, 1)
                elif nm == "Investment_Trust":                 rd["投信"] = round(rd.get("投信", 0) + net, 1)
                elif nm in ("Dealer_self", "Dealer_Hedging"): rd["自營"] = round(rd.get("自營", 0) + net, 1)
            if rd: inst_dict[dk] = rd
        print(f"[LI-v8] 三大法人 {len(inst_dict)} 天")

    # ═══ 4.5 融資融券日序列（FinMind 主 → TWSE 備援）══════════════
    margin_dict = {}   # {ymd: {'融資餘額': float, '融券餘額': float}}

    def _to_yi_mg(v):
        """智能單位轉換 → 億元，自動偵測千元/萬元/元"""
        try:
            v = float(v)
        except Exception as _e_to_yi:
            import sys as _sys_to_yi
            print(f'[_to_yi_mg] cast fail: {type(_e_to_yi).__name__}: {_e_to_yi} (val={v!r})',
                  file=_sys_to_yi.stderr)
            return None
        if pd.isna(v) or v <= 0:
            return None
        if 100 <= v <= 20000:   return round(v, 0)          # 已是億元
        if v > 1e9:             return round(v / 1e8, 0)    # 元 → 億元
        if v > 1e6:             return round(v / 1e5, 0)    # 千元 → 億元
        if v > 1e4:             return round(v / 1e4, 0)    # 萬元 → 億元
        return None

    # ── 來源 A：FinMind TaiwanStockTotalMarginPurchaseShortSale ──
    try:
        _df_mg = finmind_get("TaiwanStockTotalMarginPurchaseShortSale", "", s_ymd, e_ymd, token)
        if not _df_mg.empty:
            _mg_cols = list(_df_mg.columns)
            print(f"[LI-v8] FM融資融券欄位: {_mg_cols}")
            if not _df_mg.empty:
                print(f"[LI-v8] FM融資融券sample:\n{_df_mg.head(4).to_string()}")
            _df_mg['_ymd'] = _df_mg['date'].astype(str).str.replace('-', '')
            _df_mg = _df_mg[_df_mg['_ymd'].between(s_ymd, e_ymd)]
            # 自動找 balance 欄位（任何含 alance / 餘額 / Amount 的欄）
            _bal_cols = [c for c in _mg_cols if any(k in c for k in
                         ['alance', '餘額', 'amount', 'Amount'])]
            print(f"[LI-v8] FM候選balance欄: {_bal_cols}")
            if 'name' in _mg_cols and _bal_cols:
                for _bc in _bal_cols:
                    _tmp = {}
                    for _dk, _grp in _df_mg.groupby('_ymd'):
                        _e = {}
                        for _, _mr in _grp.iterrows():
                            _nm = str(_mr.get('name', '')).lower()
                            _v_yi = _to_yi_mg(_mr.get(_bc))
                            if _v_yi is None:
                                continue
                            if '融資' in _nm or 'margin' in _nm or 'purchase' in _nm:
                                if 100 < _v_yi < 20000:
                                    _e['融資餘額'] = _v_yi
                            elif '融券' in _nm or 'short' in _nm:
                                if 10 < _v_yi < 5000:
                                    _e['融券餘額'] = _v_yi
                        if _e:
                            _tmp[_dk] = _e
                    if _tmp:
                        margin_dict = _tmp
                        print(f"[LI-v8] FM融資融券欄={_bc} 找到 {len(margin_dict)} 天")
                        break
                if not margin_dict:
                    _name_samples = list(_df_mg['name'].unique()[:8]) if 'name' in _df_mg.columns else []
                    print(f"[LI-v8] FM融資融券所有欄均無法解析，name樣本={_name_samples}")
            elif 'MarginPurchaseTodayBalance' in _mg_cols:
                # 寬格式（個股樣式）
                for _dk, _grp in _df_mg.groupby('_ymd'):
                    _e = {}
                    _fa = _to_yi_mg(_grp['MarginPurchaseTodayBalance'].iloc[-1])
                    if _fa and 100 < _fa < 20000:
                        _e['融資餘額'] = _fa
                    if 'ShortSaleTodayBalance' in _grp.columns:
                        _fv = _to_yi_mg(_grp['ShortSaleTodayBalance'].iloc[-1])
                        if _fv and 10 < _fv < 5000:
                            _e['融券餘額'] = _fv
                    if _e:
                        margin_dict[_dk] = _e
                print(f"[LI-v8] FM融資融券（寬格式）{len(margin_dict)} 天")
        else:
            print("[LI-v8] FM融資融券回傳空 DataFrame")
    except Exception as _fm_mge:
        print(f"[LI-v8] FM融資融券略過: {_fm_mge}")

    # ── 來源 B：TWSE MI_MARGN（若 FinMind 無資料則備援）────────
    if not margin_dict:
        print("[LI-v8] 嘗試 TWSE MI_MARGN 備援")
        try:
            import datetime as _dt45
            _mg_c = _dt45.datetime.strptime(e_ymd, '%Y%m%d').date()
            _mg_s = _dt45.datetime.strptime(s_ymd, '%Y%m%d').date()
            _mg_dates = []
            while _mg_c >= _mg_s and len(_mg_dates) < days + 5:
                if _mg_c.weekday() < 5:
                    _mg_dates.append(_mg_c.strftime('%Y%m%d'))
                _mg_c -= _dt45.timedelta(days=1)
            for _mgd in _mg_dates:
                _r = _twse_margin_day(_mgd)
                if _r:
                    margin_dict[_mgd] = _r
                time.sleep(0.12)
            print(f"[LI-v8] TWSE融資融券序列 {len(margin_dict)} 天")
        except Exception as _tw_mge:
            print(f"[LI-v8] TWSE融資融券略過: {_tw_mge}")

    # ═══ 5. 成交量（選用）══════════════════════════════════════
    vol_dict = {}
    try:
        for m in months_in_range(s_date, today):
            vol_dict.update(twse_volume(m))
        print(f"[LI-v8] 成交量（FMTQIK）{len(vol_dict)} 天")
    except Exception as _ve:
        print(f"[LI-v8] 成交量FMTQIK略過: {_ve}")
    # 永遠補充近14天（MI_INDEX，盤後才有資料）
    import time as _vt2
    _mi_dates = []
    _ck = today
    while len(_mi_dates) < 14:
        if _ck.weekday() < 5:
            _mi_dates.append(_ck.strftime("%Y%m%d"))
        _ck -= _dt.timedelta(days=1)
    for _vd in _mi_dates:
        if _vd not in vol_dict:
            _v = twse_volume_daily(_vd)
            if _v: vol_dict[_vd] = _v
            _vt2.sleep(0.15)  # 只在實際發出 request 後才 sleep
    print(f"[LI-v8] 成交量（最終）{len(vol_dict)} 天")

    # ═══ 6. 確定日期範圍 ════════════════════════════════════════
    known = set(fut_net) | set(pcr_dict) | set(inst_dict) | set(opt_dict) | set(margin_dict)
    known = {d for d in known if s_ymd <= d <= e_ymd}
    if not known:
        import datetime as _dt2
        c = s_date
        while c <= today:
            if c.weekday() < 5: known.add(c.strftime("%Y%m%d"))
            c += _dt2.timedelta(days=1)
    target = sorted(known)[-days:]
    print(f"[LI-v8] known={len(known)} 天, target(last {days})={target}")
    if not target:
        print("[LI-v8] ❌ target 為空！known={known} → 請確認 FinMind API 可達")
        return pd.DataFrame()

    # ═══ 6.5 快速嘗試 TAIFEX（前五大/前十大/未平倉/韭菜精確值）══════
    # 每個日期超時 12s，Colab 若 IP 被封鎖則快速跳過
    taifex_lt   = {}   # {ymd: {前五大, 前十大}}
    taifex_mtx_oi = {} # {ymd: total MTX OI}
    taifex_leek = {}   # {ymd: float}
    # ── TAIFEX 可達性探測（最先執行，1秒超時，失敗則跳過所有 TAIFEX）
    _taifex_reachable = False
    try:
        _probe = _bps().get("https://www.taifex.com.tw",
                             headers=TAIFEX_HDR, timeout=2)
        _taifex_reachable = (_probe.status_code == 200)
        print(f"[TAIFEX] 連線測試 {'✅ 可達' if _taifex_reachable else '❌ 不通'}")
    except Exception as _probe_err:
        print(f"[TAIFEX] 連線測試 ❌ {type(_probe_err).__name__}（跳過所有 TAIFEX）")

    # ── TAIFEX PCR 精確值（全市場，只在 TAIFEX 可達時執行）────
    if _taifex_reachable:
        try:
            pcr_taifex = taifex_pcr(s_ymd, e_ymd)
            pcr_dict.update(pcr_taifex)
            print(f"[LI-v8] PCR(TAIFEX精確) {len(pcr_taifex)} 天 → 覆蓋 FinMind 估算")
        except Exception as _pe:
            print(f"[LI-v8] PCR(TAIFEX)略過: {_pe}")

    # TAIFEX: 嘗試 target 所有日期（最多14天），每天超時7s
    # 整段限時 _TAIFEX_ENRICH_BUDGET_S：逐日序列爬若拖過預算 → break，用已收到的
    # 部分 + FinMind 主資料組表(§1 不靜默：明確 log 切點與已收天數)。
    _tfx_deadline = _tm_li.monotonic() + _TAIFEX_ENRICH_BUDGET_S
    _tfx_budget_hit = False
    for _td in target:   # 全部 target 日期
        if _taifex_reachable and _tm_li.monotonic() > _tfx_deadline:
            _tfx_budget_hit = True
            print(f"[TAIFEX] ⏱️ 補強預算 {_TAIFEX_ENRICH_BUDGET_S}s 用罄，"
                  f"已收 LT={len(taifex_lt)}天 MTX={len(taifex_leek)}天，"
                  f"其餘日改用 FinMind 估算組表(三大法人/期貨/PCR/融資不受影響)")
            break
        if _taifex_reachable:
            try:
                _lt_res = taifex_large_trader(_td)
                if _lt_res and isinstance(_lt_res, dict):
                    taifex_lt[_td] = _lt_res
                    print(f"[TAIFEX-LT] {_td} ✅ {_lt_res}")
            except Exception as _te:
                print(f"[TAIFEX-LT] {_td} ❌ {type(_te).__name__}: {_te}")
        if _taifex_reachable:
          try:
            # taifex_mtx_data returns (leek, total_oi) or just leek
            _mtx_result = taifex_mtx_data(_td)
            if isinstance(_mtx_result, tuple) and len(_mtx_result) == 2:
                _leek_val, _oi_val = _mtx_result
                if _oi_val: taifex_mtx_oi[_td] = _oi_val
            else:
                _leek_val = _mtx_result
            if _leek_val is not None:
                taifex_leek[_td] = _leek_val
                print(f"[TAIFEX-MTX] {_td} ✅ 韭菜={_leek_val}% OI={taifex_mtx_oi.get(_td,'-')}")
          except Exception as _me:
            print(f"[TAIFEX-MTX] {_td} ❌ {type(_me).__name__}: {_me}")

    # ═══ 7. 組合 DataFrame ══════════════════════════════════════
    rows = []
    for d in target:
        inst = inst_dict.get(d, {})
        _lt  = taifex_lt.get(d, {})
        # ── 法人空多比（估算韭菜方向）──────────────────────────
        # 精確韭菜指數需 TAIFEX 全體 OI，在 Colab 無法取得
        # 改用「法人淨空比 = (法人空 - 法人多) / (法人空 + 法人多) × 100」
        # 正值=法人淨空（散戶被迫多方，反向警戒）；負值=法人淨多（散戶悲觀）
        _leek = None
        if df_mtx is not None and not df_mtx.empty:
            _mtx_d = df_mtx[df_mtx["date"].astype(str).str.replace("-","") == d]
            if not _mtx_d.empty:
                _inst_l = _inst_s = 0
                for _, _mr in _mtx_d.iterrows():
                    if any(k in str(_mr.get("institutional_investors","")) for k in ["外資","投信","自營"]):
                        _inst_l += int(pd.to_numeric(_mr.get("long_open_interest_balance_volume",0), errors="coerce") or 0)
                        _inst_s += int(pd.to_numeric(_mr.get("short_open_interest_balance_volume",0), errors="coerce") or 0)
                _inst_total = _inst_l + _inst_s
                if _inst_total > 0:
                    # 法人淨空比（方向指標，非精確韭菜指數）
                    _leek = round((_inst_s - _inst_l) / _inst_total * 100, 1)
                    _leek = max(-99, min(99, _leek))
        rows.append({
            "_date":     d,
            "日期":       ymd_display(d),
            "成交量":     f"{vol_dict[d]:.1f}億" if vol_dict.get(d) else "-",
            "外資":       inst.get("外資"),
            "投信":       inst.get("投信"),
            "自營":       inst.get("自營"),
            "外資大小":   fut_net.get(d),
            "前五大留倉": _lt.get("前五大"),   # FinMind 免費版無此資料
            "前十大留倉": _lt.get("前十大"),
            "選PCR":      pcr_dict.get(d),
            "外(選)":     opt_dict.get(d),
            "未平倉口數": taifex_mtx_oi.get(d) or _lt.get("未平倉"),
            "韭菜指數":   taifex_leek.get(d) if taifex_leek.get(d) is not None else _leek,
            "融資餘額":   margin_dict.get(d, {}).get('融資餘額'),
            "融券餘額":   margin_dict.get(d, {}).get('融券餘額'),
        })
    if not rows:
        print("[LI-v8] ⚠️ 無資料")
        # v18.342 PR-L2:無新資料 → 改用過期 pickle(若有),不返回 None。
        # user「假日抓前一次的」+ §2.4「過期 cache 須帶 is_stale,禁靜默」。
        if _stale_fallback_df is not None and not getattr(_stale_fallback_df, 'empty', True):
            print(f'[LI-v8] 📦 fallback to stale pickle (age={_stale_age_min}min)')
            return _mark_stale(_stale_fallback_df, _stale_age_min)
        return None
    df = pd.DataFrame(rows)
    filled = sum(1 for _, r in df.iterrows()
                 if any(r.get(c) is not None for c in ["外資大小","選PCR","外(選)","外資"]))
    print(f"[LI-v8] ✅ {len(df)} 筆 ({filled} 筆有數據)")
    # v18.342 PR-L2:當次 FinMind 全空 + 有過期 pickle → 用 pickle + is_stale 旗標
    # (rows 雖非空但全 None placeholder = 跟 user 視角的「沒抓到」等價,假日場景)
    if not _fm_ok and filled == 0 and _stale_fallback_df is not None \
            and not getattr(_stale_fallback_df, 'empty', True):
        print(f'[LI-v8] 📦 FinMind 全空 + filled=0 → fallback to stale pickle '
              f'(age={_stale_age_min}min)')
        return _mark_stale(_stale_fallback_df, _stale_age_min)
    # 只在 FinMind 主來源有回資料時快取；暫時性失敗（_fm_ok=False）不快取，保留下次刷新重試
    if _fm_ok:
        try:
            with open(_ck_li, 'wb') as _f_li:
                _pk_li.dump(df, _f_li)
        except Exception:
            pass
    # S-PROV-1 phase 18 v18.264 — provenance(schema-additive)
    # TAIFEX 補強逾預算被截斷時,source 標 :taifex-partial,讓 UI/稽核知道前五大/
    # 精確韭菜可能不全(主資料仍為 FinMind,§2.2 血緣可追)。
    if not df.empty:
        df["source"] = ("FinMind+TAIFEX:leading_indicators:fast:taifex-partial"
                        if _tfx_budget_hit else
                        "FinMind+TAIFEX:leading_indicators:fast")
        df["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    return df



def render_leading_table(df):
    """渲染先行指標 HTML 表格（含融資融券日序列）"""
    BRACKET = {"外資大小","前五大留倉","前十大留倉","外(選)"}
    SPOT    = {"外資","投信","自營"}
    MARGIN  = {"融資餘額","融券餘額"}
    COLS    = ["外資","投信","自營","外資大小","融資餘額","融券餘額",
               "前五大留倉","前十大留倉","選PCR","外(選)","未平倉口數","韭菜指數"]
    def fmt(v, col):
        if v is None or (isinstance(v, float) and pd.isna(v)): return "-"
        if col in BRACKET:
            n = int(v)
            if n > 0: return f"▲ {n:,}"
            if n < 0: return f"▼ ({abs(n):,})"
            return f"{n:,}"
        if col in SPOT:
            n = float(v)
            if n > 0: return f"▲ {n:.1f}"
            if n < 0: return f"▼ {abs(n):.1f}"
            return f"{n:.1f}"
        if col in MARGIN: return f"{float(v):,.0f}億"
        if col == "選PCR": return f"{float(v):.1f}"
        if col == "未平倉口數": return f"{int(v):,}"
        if col == "韭菜指數":
            n = float(v)
            if n > 0: return f"▲ {n:.1f}%"
            if n < 0: return f"▼ {abs(n):.1f}%"
            return f"{n:.1f}%"
        return str(v)
    def sty(v, col):
        if v is None: return ""
        try:
            if pd.isna(v): return ""
        except (TypeError, ValueError):
            pass
        try: n = float(v)
        except Exception: return ""
        # 台股紅漲綠跌：正數 = 紅 (TRAFFIC_RED) / 負數 = 綠 (TRAFFIC_GREEN)
        if col in BRACKET:
            if n > 0: return f"color:{TRAFFIC_RED};font-weight:bold;"
            if n < 0: return f"color:{TRAFFIC_GREEN};font-weight:bold;"
        if col in SPOT:
            if n > 0: return f"color:{TRAFFIC_RED};"
            if n < 0: return f"color:{TRAFFIC_GREEN};"
        if col == "融資餘額":
            # 水位指標（紅=過熱警示 / 綠=寬鬆），不受紅漲綠跌影響
            if n >= 3400: return f"color:{TRAFFIC_RED};font-weight:bold;"
            if n >= 2800: return f"color:{TRAFFIC_YELLOW};"
            return f"color:{TRAFFIC_GREEN};"
        if col == "融券餘額":
            if n >= 100:  return f"color:{TRAFFIC_RED};"
            return "color:#8b949e;"
        if col == "選PCR":
            # PCR 反向：高 PCR = 看空 (跌) = 綠 / 低 PCR = 看多 (漲) = 紅
            if n < 80:  return f"color:{TRAFFIC_RED};"
            if n > 120: return f"color:{TRAFFIC_GREEN};"
        if col == "未平倉口數":
            if n > 0: return f"color:{TRAFFIC_RED};"
            if n < 0: return f"color:{TRAFFIC_GREEN};"
        if col == "韭菜指數":
            # 直接視角：散戶淨多正數 = 紅；散戶淨空負數 = 綠（反向解讀由 user 自行）
            if n > 10:  return f"color:{TRAFFIC_RED};font-weight:bold;"
            elif n > 0: return f"color:{TRAFFIC_RED};"
            elif n < -10: return f"color:{TRAFFIC_GREEN};font-weight:bold;"
            elif n < 0: return f"color:{TRAFFIC_GREEN};"
        return ""
    # 判斷是否有融資融券資料（避免顯示全空欄位）
    _has_margin = any(df[c].notna().any() for c in ["融資餘額","融券餘額"] if c in df.columns)
    _margin_span = 2 if _has_margin else 0
    _margin_hdr = ('<th colspan="2" class="li-mg">💸 信用交易</th>\n' if _has_margin else '')
    _margin_th  = ('<th class="li-hb">融資餘額<br><small>億元</small></th>\n'
                   '  <th class="li-hb">融券餘額<br><small>億元</small></th>\n' if _has_margin else '')
    h = (
        "<style>\n"
        ".li-tbl{width:100%;border-collapse:collapse;font-size:14px;font-family:Arial,sans-serif;}\n"
        ".li-tbl th,.li-tbl td{border:1px solid #333;padding:6px 12px;text-align:center;white-space:nowrap;}\n"
        ".li-tbl tr:nth-child(even) td{background:rgba(255,255,255,0.04);}\n"
        ".li-tbl tr:hover td{background:rgba(255,215,0,0.08);}\n"
        ".li-hd{background:#1a3a5c;color:#fff;font-weight:bold;}\n"
        ".li-fa{background:#4a2060;color:#FFD700;font-weight:bold;}\n"
        ".li-mg{background:#3a2a10;color:#ffa040;font-weight:bold;}\n"
        ".li-li{background:#1a4a2a;color:#90EE90;font-weight:bold;}\n"
        ".li-hb{background:#1a1a2e;color:#ccc;font-weight:bold;}\n"
        ".li-dl{font-weight:bold;text-align:left;padding-left:12px;color:#9CDCFE;}\n"
        "</style>\n"
        "<table class=\"li-tbl\"><thead>\n"
        "<tr>\n"
        "  <th rowspan=\"2\" class=\"li-hd\">日期</th><th rowspan=\"2\" class=\"li-hd\">成交量</th>\n"
        "  <th colspan=\"4\" class=\"li-fa\">🏦 法人買賣</th>\n"
        f"  {_margin_hdr}"
        "  <th colspan=\"6\" class=\"li-li\">📡 先行指標</th>\n"
        "</tr>\n"
        "<tr>\n"
        "  <th class=\"li-hb\">外資<br><small>億元</small></th>\n"
        "  <th class=\"li-hb\">投信<br><small>億元</small></th>\n"
        "  <th class=\"li-hb\">自營<br><small>億元</small></th>\n"
        "  <th class=\"li-hb\">外資大小<br><small>口</small></th>\n"
        f"  {_margin_th}"
        "  <th class=\"li-hb\">前五大留倉<br><small>口</small></th>\n"
        "  <th class=\"li-hb\">前十大留倉<br><small>口</small></th>\n"
        "  <th class=\"li-hb\">選PCR</th>\n"
        "  <th class=\"li-hb\">外(選)<br><small>千元</small></th>\n"
        "  <th class=\"li-hb\">未平倉口數<br><small>口</small></th>\n"
        "  <th class=\"li-hb\">韭菜指數<br><small>%</small></th>\n"
        "</tr>\n"
        "</thead><tbody>"
    )
    _render_cols = COLS if _has_margin else [c for c in COLS if c not in MARGIN]
    for _, row in df.iterrows():
        h += "<tr>"
        h += f'<td class="li-dl">{row.get("日期","-")}</td><td><span style="color:#9CDCFE;">{row.get("成交量","-")}</span></td>'
        for col in _render_cols:
            v = row.get(col)
            _s = sty(v, col)
            _f = fmt(v, col)
            h += f'<td><span style="{_s}">{_f}</span></td>' if _s else f'<td>{_f}</td>'
        h += "</tr>\n"
    return h + "</tbody></table>"
