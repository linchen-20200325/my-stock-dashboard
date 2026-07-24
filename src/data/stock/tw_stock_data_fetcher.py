"""
tw_stock_data_fetcher.py — 台股財報抓取模組（Proxy-aware）

強制走 NAS Proxy 路由，支援 Goodinfo / MOPS 備援。
與 data_loader.fetch_fin_data() 回傳格式相容。

§8.2 例外:本檔為 L1 Data 但 import streamlit,屬 CLAUDE.md §8.2.A EX-CACHE-1 + EX-L0-1
複合例外:
  - L119 `st.secrets`: bootstrap 讀 FINMIND_TOKEN(同 config.py 模式)
  - L485/525/747 `@st.cache_data`: 部署架構核心 cache
無 `st.session_state` / `st.error` / `st.markdown` 等真 UI 呼叫,符合例外條件。
"""

from __future__ import annotations

import random
import re
import time
from typing import Any

import pandas as pd
import requests

from shared.roc_calendar import gregorian_to_roc_year  # B3 SSOT-H2:西元→民國
from shared.finmind_subject_aliases import FIELD_ALIASES  # B4 SSOT-H1:財報科目別名
# §8.2.A EX-CACHE-1 + EX-L0-1:條件 import streamlit + 無 UI 呼叫 fallback。
# 本檔僅用 @st.cache_data + st.secrets(同 config.py 模式),無真 UI 呼叫。
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
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from shared.ttls import TTL_3DAY, TTL_7DAY
from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT

# ─────────────────────────────────────────────
# §1 Constants
# ─────────────────────────────────────────────
CACHE_TTL_SEC = TTL_3DAY  # alias kept for back-compat
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 30
_RETRY_TOTAL = 3
_RETRY_BACKOFF = 1.5
_RETRY_STATUS = [429, 503, 504]

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# ─────────────────────────────────────────────
# §2 Field Aliases
# ─────────────────────────────────────────────
# FIELD_ALIASES 已於 B4(SSOT-H1)搬至 shared/finmind_subject_aliases.py,見檔頂 import。

# ─────────────────────────────────────────────
# §3 Proxy Config
# ─────────────────────────────────────────────
_proxy_health_tfw: dict = {}
_PROXY_TTL_TFW = 60

def _proxy_alive_tfw(url: str, timeout: float = 2.0) -> bool:
    """TCP 快測代理是否可達；結果快取 60s。"""
    import socket, time as _t
    from urllib.parse import urlparse
    now = _t.time()
    if url in _proxy_health_tfw:
        alive, ts = _proxy_health_tfw[url]
        if now - ts < _PROXY_TTL_TFW:
            return alive
    try:
        _p = urlparse(url)
        with socket.create_connection((_p.hostname or 'localhost', _p.port or 3128), timeout=timeout):
            alive = True
    except Exception:
        alive = False
    _proxy_health_tfw[url] = (alive, now)
    if not alive:
        print(f'[Proxy/tfw] ⚠️ {url} 無法連線，跳過代理')
    return alive

def _load_proxy_config() -> dict[str, str] | None:
    """Read proxy settings: PROXY_URL (single key) → PROXY_HOST/PORT → OS env vars.
    若代理 TCP 探測失敗，自動跳過（避免代理斷線拖垮所有連線）。"""
    import os as _os_proxy
    _purl = None
    try:
        secrets = st.secrets
        # 優先：單一 PROXY_URL（Streamlit Cloud 格式）
        _purl = secrets.get("PROXY_URL", "")
        if not _purl:
            # 次選：分開的 HOST/PORT/USER/PASS
            host = secrets.get("PROXY_HOST", "")
            port = secrets.get("PROXY_PORT", "")
            if host and port:
                user   = secrets.get("PROXY_USER", "")
                passwd = secrets.get("PROXY_PASS", "")
                auth   = f"{user}:{passwd}@" if user else ""
                _purl = f"http://{auth}{host}:{port}"
    except Exception:
        pass
    if not _purl:
        # OS 環境變數 fallback
        _hp  = _os_proxy.environ.get("HTTP_PROXY")  or _os_proxy.environ.get("http_proxy")
        _hsp = _os_proxy.environ.get("HTTPS_PROXY") or _os_proxy.environ.get("https_proxy")
        _purl = _hp or _hsp or ''
    if _purl and _proxy_alive_tfw(_purl):
        return {"http": _purl, "https": _purl}
    return None


# ─────────────────────────────────────────────
# §4 Session Builder
# ─────────────────────────────────────────────
def build_proxy_session() -> requests.Session:
    """Build a requests.Session with retry adapter and proxy (if configured)."""
    session = requests.Session()
    retry = Retry(
        total=_RETRY_TOTAL,
        backoff_factor=_RETRY_BACKOFF,
        status_forcelist=_RETRY_STATUS,
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    proxies = _load_proxy_config()
    if proxies:
        session.proxies.update(proxies)
    return session


def _random_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


# ─────────────────────────────────────────────
# §5 Proxy GET / POST with manual backoff
# ─────────────────────────────────────────────
def proxy_get(
    session: requests.Session,
    url: str,
    params: dict | None = None,
    **kwargs: Any,
) -> requests.Response | None:
    timeout = (_CONNECT_TIMEOUT, _READ_TIMEOUT)
    for attempt in range(_RETRY_TOTAL):
        try:
            resp = session.get(url, params=params, headers=_random_headers(),
                               timeout=timeout, **kwargs)
            if resp.status_code == 403:
                wait = _RETRY_BACKOFF ** attempt
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException:
            if attempt < _RETRY_TOTAL - 1:
                time.sleep(_RETRY_BACKOFF ** attempt)
    return None


def proxy_post(
    session: requests.Session,
    url: str,
    data: dict | None = None,
    **kwargs: Any,
) -> requests.Response | None:
    timeout = (_CONNECT_TIMEOUT, _READ_TIMEOUT)
    for attempt in range(_RETRY_TOTAL):
        try:
            resp = session.post(url, data=data, headers=_random_headers(),
                                timeout=timeout, **kwargs)
            if resp.status_code in (403, 503):
                wait = _RETRY_BACKOFF ** attempt
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException:
            if attempt < _RETRY_TOTAL - 1:
                time.sleep(_RETRY_BACKOFF ** attempt)
    return None


# ─────────────────────────────────────────────
# §6 Fuzzy Field Lookup
# ─────────────────────────────────────────────
# v18.398 P5-DEAD-RE-AUDIT:`fuzzy_get(dict 版)` 已刪 — 嚴格雙重條件 audit
# 確認 0 ref everywhere(prod / test / module-internal 全 0)。
# DataFrame 版 `fuzzy_get_from_df` 仍 live(被 calc_financial_metrics 用)。


def fuzzy_get_from_df(df: pd.DataFrame, field: str, default: float = 0.0) -> float:
    """Look up a field from a DataFrame column set using FIELD_ALIASES."""
    aliases = FIELD_ALIASES.get(field, [field])
    # Exact match
    for alias in aliases:
        if alias in df.columns:
            val = df[alias].dropna()
            if not val.empty:
                try:
                    return float(val.iloc[-1])
                except (TypeError, ValueError):
                    continue
    # Contains match (substring)
    # v19.74 review 修正:欄名可能非 str(MOPS read_html 常回整數欄)→ str(c)
    # 否則 `alias in c` 直接 TypeError 炸掉整個 calc_financial_metrics。
    for alias in aliases:
        matched = [c for c in df.columns if alias in str(c)]
        for col in matched:
            val = df[col].dropna()
            if not val.empty:
                try:
                    return float(val.iloc[-1])
                except (TypeError, ValueError):
                    continue
    return default


# ─────────────────────────────────────────────
# §7 HTML Table Parser (Goodinfo)
# ─────────────────────────────────────────────
def _detect_quarter_cols(headers: list[str]) -> list[int]:
    """Return column indices that look like quarterly periods (e.g. '2024Q1')."""
    import re
    pattern = re.compile(r"\d{4}Q[1-4]")
    return [i for i, h in enumerate(headers) if pattern.search(h)]


def parse_goodinfo_table(html: str, table_id: str = "") -> pd.DataFrame:
    """
    Parse a Goodinfo financial table HTML into a DataFrame.
    Rows = fields; Columns = quarters.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": table_id}) if table_id else soup.find("table")
    if table is None:
        return pd.DataFrame()
    rows = table.find_all("tr")
    if len(rows) < 2:
        return pd.DataFrame()

    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    quarter_idx = _detect_quarter_cols(headers)
    if not quarter_idx:
        return pd.DataFrame()

    records: dict[str, list] = {headers[i]: [] for i in quarter_idx}
    field_names: list[str] = []

    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
        if not cells:
            continue
        field_name = cells[0]
        field_names.append(field_name)
        for i in quarter_idx:
            raw = cells[i] if i < len(cells) else ""
            raw = raw.replace(",", "").replace("(", "-").replace(")", "")
            try:
                records[headers[i]].append(float(raw))
            except ValueError:
                records[headers[i]].append(None)

    df = pd.DataFrame(records, index=field_names)
    return df


# ─────────────────────────────────────────────
# §8 Goodinfo Fetcher
# ─────────────────────────────────────────────
_GOODINFO_BASE = "https://goodinfo.tw/tw"

def _goodinfo_url(stock_id: str, report: str) -> str:
    report_map = {
        "BS": "BALANCE_SHEET",
        "IS": "INCOME_STATEMENT",
        "CF": "CASH_FLOW",
    }
    code = report_map.get(report, report)
    return f"{_GOODINFO_BASE}/StockFinDetail.asp?STOCK_ID={stock_id}&REPORT_TYPE={code}&RPT_TIME=QS"


def fetch_goodinfo_financials(
    stock_id: str,
    session: requests.Session | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch BS/IS/CF quarterly DataFrames from Goodinfo.
    Returns dict with keys 'BS', 'IS', 'CF'; empty DataFrames on failure.
    """
    if session is None:
        session = build_proxy_session()

    result: dict[str, pd.DataFrame] = {"BS": pd.DataFrame(), "IS": pd.DataFrame(), "CF": pd.DataFrame()}
    # S-PROV-1 phase 16 v18.262 — provenance(對每張表 DataFrame 加 source/fetched_at columns)
    _fetched_at = pd.Timestamp.now('UTC').isoformat()
    for report_type in ("BS", "IS", "CF"):
        url = _goodinfo_url(stock_id, report_type)
        resp = proxy_get(session, url)
        if resp is None or resp.status_code != 200:
            continue
        try:
            df = parse_goodinfo_table(resp.text)
            if not df.empty:
                df["source"] = f"Goodinfo:{report_type}:StockBzPerformance"
                df["fetched_at"] = _fetched_at
                result[report_type] = df
        except Exception:
            continue
    return result


# ─────────────────────────────────────────────
# §9 MOPS Backup Fetcher
# ─────────────────────────────────────────────
_MOPS_URL = "https://mops.twse.com.tw/mops/web/ajax_t164sb03"

def fetch_mops_financials(
    stock_id: str,
    year: int,
    season: int,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """
    Fetch single-quarter financial statements from MOPS via POST.
    season: 1=Q1, 2=Q2, 3=Q3, 4=Q4.
    Returns raw DataFrame (all fields as rows); empty on failure.
    """
    if session is None:
        session = build_proxy_session()
    payload = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "keyword4": "",
        "code1": "",
        "TYPEK2": "",
        "checkbtn": "",
        "queryName": "co_id",
        "inpuType": "co_id",
        "TYPEK": "all",
        "isnew": "false",
        "co_id": stock_id,
        "year": str(gregorian_to_roc_year(year)),   # 民國年
        "season": f"{season:02d}",
    }
    resp = proxy_post(session, _MOPS_URL, data=payload)
    if resp is None or resp.status_code != 200:
        return pd.DataFrame()
    try:
        tables = pd.read_html(resp.text, flavor="lxml")
        if not tables:
            return pd.DataFrame()
        df = tables[0]
        # S-PROV-1 phase 16 v18.262 — provenance(schema-additive)
        if not df.empty:
            df["source"] = f"MOPS:t164sb03:Y{year}Q{season}"
            df["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return df
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────────
# §10 Metric Calculator
# ─────────────────────────────────────────────
def calc_financial_metrics(
    bs: pd.DataFrame,
    inc: pd.DataFrame,
    cf: pd.DataFrame,
    is_finance: bool = False,
) -> dict[str, Any]:
    """
    Compute standardised financial metrics compatible with
    data_loader.fetch_fin_data() return format.
    All monetary values are in thousands (千元).
    """
    def _g(df: pd.DataFrame, field: str) -> float:
        return fuzzy_get_from_df(df, field)

    rev = _g(inc, "營業收入")
    gross = _g(inc, "毛利")
    op_inc = _g(inc, "營業利益")
    net_inc = _g(inc, "淨利")
    eps = _g(inc, "EPS")

    total_assets = _g(bs, "總資產")
    cur_assets = _g(bs, "流動資產")
    non_cur_assets = _g(bs, "非流動資產")
    total_liab = _g(bs, "總負債")
    cur_liab = _g(bs, "流動負債")
    equity = _g(bs, "股東權益")
    cash = _g(bs, "現金及約當現金")
    inv = _g(bs, "存貨")
    ar = _g(bs, "應收帳款")
    retained = _g(bs, "保留盈餘")
    contract_liab = _g(bs, "合約負債")

    ocf = _g(cf, "營業現金流")
    capex = abs(_g(cf, "資本支出"))
    div = abs(_g(cf, "股利支付"))

    # Derived ratios
    # v19.81 review C:fuzzy_get 可經 float("nan") 字串路徑回 NaN,而 NaN 為 truthy
    # → `if rev` 擋不住,NaN/NaN 傳染下游(毛利率=NaN 汙染健康引擎)。
    # 分母須 notna 且非 0 才算比率;無效分母維持既有 0.0 語意(缺分母≠可算)。
    def _denom_ok(x: float) -> bool:
        return bool(pd.notna(x) and x)

    gross_margin = round(gross / rev * 100, 2) if _denom_ok(rev) else 0.0
    op_margin = round(op_inc / rev * 100, 2) if _denom_ok(rev) else 0.0
    net_margin = round(net_inc / rev * 100, 2) if _denom_ok(rev) else 0.0
    debt_ratio = round(total_liab / total_assets * 100, 2) if _denom_ok(total_assets) else 0.0
    current_ratio = round(cur_assets / cur_liab, 2) if _denom_ok(cur_liab) else 0.0
    roe = round(net_inc / equity * 100, 2) if _denom_ok(equity) else 0.0

    return {
        # Revenue & Profit (千元)
        "營業收入(千)": rev,
        "毛利(千)": gross,
        "營業利益(千)": op_inc,
        "稅後淨利(千)": net_inc,
        "EPS": eps,
        # Balance Sheet (千元)
        "總資產(千)": total_assets,
        "流動資產(千)": cur_assets,
        "非流動資產(千)": non_cur_assets,
        "總負債(千)": total_liab,
        "流動負債(千)": cur_liab,
        "股東權益(千)": equity,
        "現金(千)": cash,
        "存貨(千)": inv,
        "應收帳款(千)": ar,
        "保留盈餘(千)": retained,
        "合約負債(千)": contract_liab,
        # Cash Flow (千元)
        "營業現金流(千)": ocf,
        "資本支出(千)": capex,
        "股利支付(千)": div,
        # Ratios (%)
        "毛利率(%)": gross_margin,
        "營益率(%)": op_margin,
        "淨利率(%)": net_margin,
        "負債比率(%)": debt_ratio,
        "流動比率": current_ratio,
        "ROE(%)": roe,
        # Flags
        "is_finance": is_finance,
        "source": "tw_stock_data_fetcher",
    }


# ─────────────────────────────────────────────
# §11 Cached Fetcher Factory
# ─────────────────────────────────────────────
def _make_cached_fetcher():
    # v19.74 review:max_entries=64 — 以 stock_id 為鍵逐檔堆積,無上界時
    # Streamlit Cloud(~1GB)連續瀏覽數百檔會膨脹;LRU 回收控記憶體上界。
    @st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False, max_entries=64)
    def _fetch(stock_id: str, is_finance: bool = False) -> dict[str, Any]:
        """
        Fetch Taiwan stock financials via Goodinfo (proxy-aware).
        Falls back to MOPS for the most recent quarter if Goodinfo fails.
        Compatible with data_loader.fetch_fin_data() return format.
        """
        session = build_proxy_session()

        # Primary: Goodinfo
        dfs = fetch_goodinfo_financials(stock_id, session)
        bs, inc, cf = dfs["BS"], dfs["IS"], dfs["CF"]

        # Fallback: MOPS for current quarter (rough estimate)
        _mops_fallback_used = False
        if bs.empty and inc.empty:
            import datetime
            now = datetime.datetime.now()
            year = now.year
            season = (now.month - 1) // 3 + 1
            mops_df = fetch_mops_financials(stock_id, year, season, session)
            if not mops_df.empty:
                # MOPS returns raw rows; attempt minimal extraction
                inc = mops_df
                _mops_fallback_used = True
        if bs.empty and inc.empty and cf.empty:
            return {"error": "all_sources_failed", "is_finance": is_finance}

        _metrics = calc_financial_metrics(bs, inc, cf, is_finance=is_finance)
        # v19.74 review 修正:MOPS ajax_t164sb03 是未標準化長格式(會計項目/金額),
        # 非 Goodinfo 季度寬表 schema,fuzzy 欄位比對多半全落空回 default=0.0 →
        # 「表面拿到財報 dict、實際全指標 = 0」,下游健康度被餵零值誤判財務崩壞
        # (§1 錯值比缺值更危險)。核心科目全零 → 顯式 fail 回 parse_failed,
        # 讓上游走 insufficient_data 路徑(對齊同檔 fetch_5_years_cash_flow
        # 「OCF=0 改回 insufficient」防禦)。
        if _mops_fallback_used and not any(
                _metrics.get(_k) for _k in
                ("營業收入(千)", "總資產(千)", "稅後淨利(千)", "EPS")):
            print(f'[fetch_tw_financials] {stock_id} MOPS fallback 解析全零 '
                  f'→ mops_parse_failed(不回傳零值假財報)')
            return {"error": "mops_parse_failed", "is_finance": is_finance}
        return _metrics

    return _fetch


# ─────────────────────────────────────────────
# §12 Public API
# ─────────────────────────────────────────────
fetch_tw_financials = _make_cached_fetcher()


# ─────────────────────────────────────────────
# §12.5  5年期現金流量允當比率（B 項精確版）
# ─────────────────────────────────────────────
@st.cache_data(ttl=TTL_7DAY, show_spinner=False, max_entries=64)
def fetch_5_years_cash_flow(stock_code: str, token: str = "") -> dict:
    """
    抓取 5 年期現金流量允當比率（100/100/10 法則 B 項）
    資料源：FinMind TaiwanStockCashFlowsStatement 年度報表（12月）
    Proxy-aware；7 天快取。

    回傳 dict:
      ratio      : float  5年允當比率(%)；None 表示資料不足
      label      : str    顯示用文字
      status     : str    "ok" / "insufficient_data" / "error"
      years      : int    實際取得年份數
      ocf_5y     : float  5年 OCF 加總（千）
      capex_5y   : float  5年資本支出加總（千，絕對值）
      inv_inc_5y : float  5年存貨增加額加總（千，僅正值）
      div_5y     : float  5年現金股利加總（千，絕對值）
      denom_5y   : float  5年分母合計（千）
    """
    import datetime
    import os

    _tok = token or os.environ.get("FINMIND_TOKEN", "")
    _empty = {
        "status": "error", "ratio": None, "label": "資料不足",
        "years": 0, "ocf_5y": 0, "capex_5y": 0,
        "inv_inc_5y": 0, "div_5y": 0, "denom_5y": 0,
    }

    try:
        today  = datetime.date.today()
        start  = today.replace(year=today.year - 6).strftime("%Y-%m-%d")
        end    = today.strftime("%Y-%m-%d")
        params = {
            "dataset":    "TaiwanStockCashFlowsStatement",
            "data_id":    stock_code,
            "start_date": start,
            "end_date":   end,
        }
        if _tok:
            params["token"] = _tok

        session = build_proxy_session()
        r = session.get(
            FINMIND_API_URL,
            params=params,
            headers={"User-Agent": random.choice(_USER_AGENTS)},
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
        )
        j = r.json()
        if j.get("status") != 200 or not j.get("data"):
            return {**_empty, "label": f"FinMind status={j.get('status')}"}

        df = pd.DataFrame(j["data"])
        df["date"] = pd.to_datetime(df["date"])
        # 年度報表 = 每年 12 月（Q4 累計）
        df = df[df["date"].dt.month == 12].copy()
        df["year"] = df["date"].dt.year
        years_avail = sorted(df["year"].unique())[-5:]
        df = df[df["year"].isin(years_avail)]
        if len(years_avail) < 3:
            return {**_empty, "status": "insufficient_data",
                    "label": f"年份不足（僅{len(years_avail)}年）"}

        # ── 科目別名集合 ───────────────────────────────────────────
        # 注意：FinMind 行內 type=英文IFRS碼，origin_name=中文科目名。
        # _sum() 會同時比對兩個欄位，所以 alias 集合可混用英中文。
        # 對齊 data_loader.py:1612-1620（同一份 FinMind dataset）
        _OCF   = {"CashFlowsFromOperatingActivities",        # 複數！與 data_loader 對齊
                  "CashFlowFromOperatingActivities",          # 單數備援
                  "OperatingActivities",
                  "營業活動之淨現金流入（流出）",              # 全形括號（FinMind 主格式）
                  "營業活動之淨現金流入(流出)",                # 半形括號
                  "來自營業活動之現金流量",
                  "營業活動之淨現金流入",
                  "營業活動現金流量"}
        _CAPEX = {"AcquisitionOfPropertyPlantAndEquipment",
                  "取得不動產、廠房及設備", "購置不動產廠房及設備",
                  "取得不動產廠房及設備", "資本支出",
                  "取得不動產、廠房及設備及使用權資產",
                  "購置不動產、廠房及設備",
                  "取得固定資產", "購買固定資產", "取得有形固定資產",
                  "AcquisitionOfPropertyPlantEquipmentAndRightOfUseAssets",
                  # 擴充：涵蓋更多 IFRS 命名變體
                  "PaymentsToAcquirePropertyPlantAndEquipment",
                  "PurchaseOfPropertyPlantAndEquipment",
                  "CapitalExpenditures", "CapExpenditures",
                  "取得有形資產", "購置設備", "添購設備",
                  "支付購置不動產廠房及設備", "支付取得不動產廠房及設備",
                  "購建固定資產", "購置及建造不動產廠房設備",}
        _INV   = {"IncreaseDecreaseInInventories", "存貨增加",
                  "存貨(增加)減少", "存貨(增加)、減少",
                  "IncreaseInInventories", "存貨之增加",
                  "存貨增加（減少）", "存貨減少（增加）",
                  "存貨之增加（減少）", "存貨之減少（增加）",   # 變體
                  "存貨（增加）減少", "存貨（增加）、減少"}
        _DIV   = {"DividendsPaid", "CashDividendsPaid", "支付現金股利",
                  "發放現金股利", "支付股東現金股利",
                  "發放現金股利予非控制權益",
                  "發放股東現金股利", "普通股現金股利",
                  "支付給股東之股利",
                  "現金股利", "股利之支付", "支付之股利"}    # 補變體

        def _sum(aliases):
            """同時比對 type（英文 IFRS）與 origin_name（中文科目）兩欄。
            原版只比對 type，導致中文 alias 永遠白寫；此修法治本（治 6770 OCF=0）。"""
            mask_t = df["type"].isin(aliases)
            mask_o = df["origin_name"].isin(aliases) if "origin_name" in df.columns else False
            mask = mask_t | mask_o
            vals = pd.to_numeric(df.loc[mask, "value"], errors="coerce").dropna()
            return float(vals.sum()) if not vals.empty else 0.0

        ocf_5y     = _sum(_OCF)
        capex_5y   = abs(_sum(_CAPEX))          # CF 表通常為負值
        # 存貨變化兩個方向都需算進分母（MJ：擴張用的存貨累積與消耗都是現金需求）
        inv_inc_5y = abs(_sum(_INV))
        div_5y     = abs(_sum(_DIV))

        # OCF Fuzzy fallback：alias miss 時，從欄位中模糊搜尋「營業活動」或 Operating
        if ocf_5y == 0:
            _ocf_kw_zh = ['營業活動']
            _ocf_kw_en = ['operatingactivities', 'cashflowsfromoperating']
            _fuzzy_mask_ocf = df.apply(
                lambda r: (
                    any(k in str(r.get('origin_name', '')) for k in _ocf_kw_zh)
                    or any(k in str(r.get('type', '')).lower().replace(' ', '') for k in _ocf_kw_en)
                ) and r['type'] not in (_CAPEX | _INV | _DIV),
                axis=1,
            )
            _fuzzy_vals_ocf = pd.to_numeric(df.loc[_fuzzy_mask_ocf, 'value'], errors='coerce').dropna()
            ocf_5y = float(_fuzzy_vals_ocf.sum()) if not _fuzzy_vals_ocf.empty else 0.0
            if ocf_5y != 0:
                print(f'[5yr CF] {stock_code} OCF fuzzy match: {round(ocf_5y/1e3)}百萬')

        # Fuzzy fallback：若 capex=0，從全欄位中模糊搜尋不動產/廠房/設備/資本支出
        if capex_5y == 0:
            _kw = ['不動產', '廠房', '設備', '固定資產', 'Property', 'Plant', 'Equipment',
                   'CapEx', 'Capital', '資本支出', '工程款', '機器']
            _fuzzy_mask = df['type'].apply(
                lambda t: any(k.lower() in str(t).lower() for k in _kw)
                and t not in _OCF  # 排除 OCF 欄位
            )
            _fuzzy_vals = pd.to_numeric(df.loc[_fuzzy_mask, 'value'], errors='coerce').dropna()
            capex_5y = abs(float(_fuzzy_vals.sum())) if not _fuzzy_vals.empty else 0.0
            if capex_5y > 0:
                print(f'[5yr CF] {stock_code} CapEx fuzzy match: {round(capex_5y/1e3)}百萬')

        denom_5y   = capex_5y + inv_inc_5y + div_5y

        # OCF=0：分子缺失，不應輸出 0%（會誤導為「真零」），改為 insufficient_data
        if ocf_5y == 0:
            _types_sample = list(df['type'].unique())[:3] if len(df) else []
            print(f'[5yr CF] {stock_code} OCF=0 even after fuzzy；FinMind types 前3={_types_sample}')
            return {**_empty, "status": "insufficient_data",
                    "label": "分子缺失（FinMind 未提供 OCF 欄位）",
                    "denom_5y": round(denom_5y), "years": len(years_avail)}

        if denom_5y == 0:
            return {**_empty, "status": "insufficient_data",
                    "label": "分母為零（CapEx+存貨+股利均缺失）",
                    "ocf_5y": round(ocf_5y), "years": len(years_avail)}

        ratio = round(ocf_5y / denom_5y * 100, 1)
        # S-PROV-1 phase 17 v18.263 — provenance(schema-additive,僅 ok status)
        return {
            "status":     "ok",
            "ratio":      ratio,
            "label":      f"{ratio:.1f}%（{len(years_avail)}年實際）",
            "years":      len(years_avail),
            "ocf_5y":     round(ocf_5y),
            "capex_5y":   round(capex_5y),
            "inv_inc_5y": round(inv_inc_5y),
            "div_5y":     round(div_5y),
            "denom_5y":   round(denom_5y),
            "source":     "FinMind:TaiwanStockCashFlowsStatement:5y_annual",
            "fetched_at": pd.Timestamp.now('UTC').isoformat(),
        }

    except Exception as _e:
        return {**_empty, "label": f"例外:{type(_e).__name__}:{_e}"}


# ─────────────────────────────────────────────
# §12.6  Goodinfo 老師 財報指標直抓（資產/負債/應收/DSO）
# ─────────────────────────────────────────────
_GI_BS_URL = "https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=BS_M_QUAR&STOCK_ID={sid}"
_GI_IS_URL = "https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_M_QUAR&STOCK_ID={sid}"
_GI_QTR = re.compile(r"\d{3,4}Q[1-4]")   # 支援民國 (113Q4) 與西元 (2024Q4)


def _gi_latest(html: str, field: str) -> float | None:
    """
    從 Goodinfo 季報 HTML 取指定欄位最新一季數值。
    回傳 Goodinfo 原生單位（通常為百萬元）；ratio 計算時單位可相消。
    """
    import io
    try:
        tables = pd.read_html(io.StringIO(html), encoding="utf-8")
    except Exception as exc:
        print(f"[_gi_latest] read_html failed: {exc}")
        return None

    for tb in tables:
        cols = [str(c) for c in tb.columns]
        qtr_cols = sorted([c for c in cols if _GI_QTR.search(c)], reverse=True)
        if not qtr_cols:
            continue
        for _, row in tb.iterrows():
            label = str(row.iloc[0])
            if field not in label:
                continue
            for qcol in qtr_cols:
                raw = str(row.get(qcol, "")).replace(",", "").replace("--", "").strip()
                if raw in ("", "nan", "N/A", "－"):
                    continue
                try:
                    val = float(raw)
                    if val != 0.0:
                        return val
                except ValueError:
                    continue

    print(f"[_gi_latest] '{field}' 欄位在表格中未找到")
    return None


@st.cache_data(ttl=CACHE_TTL_SEC, show_spinner=False, max_entries=64)
def fetch_goodinfo_metrics(
    stock_code: str,
    _proxies: dict | None = None,
) -> dict:
    """
    從 Goodinfo BS_M_QUAR / IS_M_QUAR 直抓最新一季財報數值並計算 老師 指標。

    Args:
        stock_code: 股票代號（如 "2330"）
        _proxies:   自訂代理，格式 {"http": "http://host:port", "https": "..."}
                    傳入 None 時自動讀取 Streamlit Secrets 設定。
                    v19.74 review 修正:改名 `_proxies`(前置底線讓 @st.cache_data
                    略過雜湊)— dict 不可雜湊,原名 `proxies` 傳入非 None 值時
                    Streamlit 直接拋 UnhashableParamError。
                    ⚠️ 語意 trade-off:不同 proxies 共用同一 cache 條目(以
                    stock_code 為鍵);本函式 proxy 只影響取數路徑不影響數值,可接受。

    Returns dict:
        assets (float|None)   : 資產總額（Goodinfo 原生單位，通常百萬元）
        liab   (float|None)   : 負債總額
        ar     (float|None)   : 應收帳款及票據
        revenue (float|None)  : 營業收入（單季）
        debt_ratio (float|None): 負債 / 資產 × 100（%）
        dso    (float|None)   : 360 / (營收×4 / 應收帳款)（天）
        error  (str|None)     : 例外訊息；正常為 None
    """
    session = build_proxy_session()
    if _proxies:
        session.proxies.update(_proxies)

    result: dict[str, Any] = {
        "assets": None, "liab": None, "ar": None, "revenue": None,
        "debt_ratio": None, "dso": None, "error": None,
    }

    try:
        # ── 資產負債表 ─────────────────────────────────────────
        resp_bs = proxy_get(session, _GI_BS_URL.format(sid=stock_code))
        if resp_bs and resp_bs.status_code == 200 and len(resp_bs.text) > 500:
            resp_bs.encoding = "utf-8"
            result["assets"] = _gi_latest(resp_bs.text, "資產總額")
            result["liab"]   = _gi_latest(resp_bs.text, "負債總額")
            result["ar"]     = _gi_latest(resp_bs.text, "應收帳款及票據")
        else:
            print(f"[fetch_goodinfo_metrics] {stock_code} BS: HTTP {getattr(resp_bs,'status_code','None')}")

        # ── 損益表 ─────────────────────────────────────────────
        resp_is = proxy_get(session, _GI_IS_URL.format(sid=stock_code))
        if resp_is and resp_is.status_code == 200 and len(resp_is.text) > 500:
            resp_is.encoding = "utf-8"
            result["revenue"] = _gi_latest(resp_is.text, "營業收入")
        else:
            print(f"[fetch_goodinfo_metrics] {stock_code} IS: HTTP {getattr(resp_is,'status_code','None')}")

        # ── 老師 指標計算（units cancel in ratios）──────────────
        _a, _l, _ar, _rev = result["assets"], result["liab"], result["ar"], result["revenue"]

        if _l is not None and _a and _a > 0:
            result["debt_ratio"] = round(_l / _a * 100, 1)

        if _rev is not None and _ar and _ar > 0 and _rev > 0:
            result["dso"] = round(360 / (_rev * 4 / _ar), 1)

        # S-PROV-1 phase 17 v18.263 — provenance(僅在實際拿到資料時寫入)
        if any(result.get(k) is not None for k in ("assets", "liab", "ar", "revenue")):
            result["source"] = "Goodinfo:BS_M_QUAR+IS_M_QUAR"
            result["fetched_at"] = pd.Timestamp.now('UTC').isoformat()

    except Exception as exc:
        result["error"] = str(exc)
        print(f"[fetch_goodinfo_metrics] {stock_code}: {exc}")

    return result


# ─────────────────────────────────────────────
# §13 CLI Test
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    stock_id = sys.argv[1] if len(sys.argv) > 1 else "2330"
    print(f"Fetching financials for {stock_id} …")

    session = build_proxy_session()
    dfs = fetch_goodinfo_financials(stock_id, session)
    for k, df in dfs.items():
        print(f"\n[{k}] shape={df.shape}")
        if not df.empty:
            print(df.head(5).to_string())

    print("\n--- calc_financial_metrics ---")
    metrics = calc_financial_metrics(dfs["BS"], dfs["IS"], dfs["CF"])
    for key, val in metrics.items():
        print(f"  {key}: {val}")
