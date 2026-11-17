"""tests/test_issue1208_moneydj_zero_requests.py — Issue #1208 第二個 PR：MoneyDJ 全入口「零真實出站請求」守衛。

GPT 2026-11-17 裁示（#1208）：首要驗收＝所有可達入口對 `www.moneydj.com` 的真實出站請求數 **嚴格 = 0**，
須在 transport／mock 層驗證（直接 requests、curl_cffi、helper／NAS relay 都要涵蓋），**不能只查函式字串消失**。

做法（兩層）
──────────
A. Transport 錄音機（runtime）：同時攔下列每一層，**任何**出站一律不放行（離線），URL／params 含 "moneydj"
   的另外記成 hit：
   - `requests.Session.request`（涵蓋 `requests.get`、proxy_helper 的 thread-local Session、NAS 中繼
     `requests.get(f'{base}/proxy', params={'url': 真目標})` —— 所以連 params 一起比）
     → 一律回假 403（讓 `fetch_url` 依序走完「proxy → 降級直連 → NAS 中繼」三段，三段都被錄到）；
   - `curl_cffi.requests.Session.request`／`curl_cffi.requests.get`／`.request`（模擬 chrome 的繞路）→ 記錄後拋例外；
   - `urllib.request.OpenerDirector.open` → 記錄後拋 URLError；
   - `socket.getaddrinfo`（最底層兜底：上面漏攔的 Python 層出站在 DNS 解析就被擋，且 host 含 moneydj 也記）；
   - helper 層 spy：`proxy_helper.fetch_url`／`nas_relay_fetch` 與 `macro_core.fetch_url`（模組載入時綁定的名字）
     —— helper 層有 300 秒 Storm Shield 快取，命中時根本不會到 transport，所以 helper 層也錄、快取也清。
   另：`yfinance.Ticker`／`download` 換成空殼（不連網）、`time.sleep` 改 no-op（fetch_url 403 退避會睡 2.5–6 秒）、
   `st.cache_data` 全清（否則前一次的 None 被快取，第二次呼叫根本不會發請求 ⇒ 假綠）。
B. 靜態掃描：`src/`、`scripts/`、`shared/`、`app.py`、`app_ui2.py`、`.github/workflows/` 不得出現
   `moneydj.com` 或 MoneyDJ 頁面副檔名（`.xdjhtm`／`.djhtm`）字面值。

⚠️ 正向對照（`TestRecorderSelfCheck`）證明錄音機每一層真的錄得到 —— 否則「0 次」可能只是錄音機壞了。
⚠️ 本檔對 PR2 實作**之前**的 main（b06a7eca）實跑：17 FAIL／7 PASS（PMI 首源命中仍打 5 筆、
   持股 21 筆含 3 次 curl_cffi、戰情室 fetch_metrics 24 筆…），證明守衛抓得到當時的 MoneyDJ 呼叫；
   PR2 實作後全綠。`TestEntryLevelPositiveControl` 另以「把 MoneyDJ 段塞回 registry」證明入口層也錄得到。
"""
from __future__ import annotations

import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd
import pytest
import requests

REPO = Path(__file__).resolve().parents[1]
_NEEDLE = "moneydj"


# ════════════════════════════════════════════════════════════════════════
# 錄音機
# ════════════════════════════════════════════════════════════════════════
class _Recorder:
    def __init__(self) -> None:
        self.hits: list[str] = []      # 對 MoneyDJ 的出站（任何一層）
        self.other: list[str] = []     # 其他出站（僅供除錯，不 assert）

    def note(self, layer: str, url, extra=None) -> None:
        _blob = f"{url} {extra!r}".lower()
        _line = f"[{layer}] {url}" + (f" params={extra!r}" if extra else "")
        (self.hits if _NEEDLE in _blob else self.other).append(_line)

    def report(self) -> str:
        _by_layer: dict[str, int] = {}
        for _h in self.hits:
            _k = _h.split("]")[0].lstrip("[")
            _by_layer[_k] = _by_layer.get(_k, 0) + 1
        return (f"MoneyDJ 出站請求（應為 0）：共 {len(self.hits)} 筆 by_layer={_by_layer}\n  "
                + "\n  ".join(self.hits))


def _fake_403(url: str) -> requests.Response:
    _r = requests.models.Response()
    _r.status_code = 403
    _r._content = b""
    _r.encoding = "utf-8"
    _r.url = str(url)
    return _r


class _FakeSecrets(dict):
    """沙盒沒有 secrets.toml，真 st.secrets 會 raise。"""
    def get(self, key, default=None):  # noqa: D401
        return default


class _FakeTicker:
    """yfinance.Ticker 空殼：不連網、全部回「沒有」。"""
    def __init__(self, *a, **k):
        self.info = {}
        self.dividends = pd.Series(dtype=float)
        self.funds_data = None

    def history(self, *a, **k):
        return pd.DataFrame()


@pytest.fixture
def mdj(monkeypatch, tmp_path):
    rec = _Recorder()

    # ── 1) requests（含 requests.get／thread-local Session／NAS 中繼）──
    def _req(self, method, url, *args, **kwargs):
        _params = kwargs.get("params", args[0] if args else None)
        rec.note("requests", url, _params)
        return _fake_403(url)
    monkeypatch.setattr(requests.Session, "request", _req)

    # ── 2) curl_cffi（模擬 chrome 繞路）──
    try:
        import curl_cffi.requests as _cr

        def _cffi_req(self, method, url, *a, **k):
            rec.note("curl_cffi.Session", url, k.get("params"))
            raise RuntimeError("offline test: curl_cffi blocked")

        def _cffi_mod(*a, **k):
            _url = k.get("url", a[1] if len(a) > 1 else (a[0] if a else None))
            rec.note("curl_cffi.module", _url, k.get("params"))
            raise RuntimeError("offline test: curl_cffi blocked")
        monkeypatch.setattr(_cr.Session, "request", _cffi_req)
        monkeypatch.setattr(_cr, "get", lambda url, **k: _cffi_mod(url=url, **k))
        monkeypatch.setattr(_cr, "request", lambda method, url, **k: _cffi_mod(url=url, **k))
    except ImportError:  # 沒裝 curl_cffi → production 那段 import 會失敗、本來就打不出去
        pass

    # ── 3) urllib ──
    def _urlopen(self, fullurl, *a, **k):
        _u = fullurl if isinstance(fullurl, str) else getattr(fullurl, "full_url", fullurl)
        rec.note("urllib", _u)
        raise urllib.error.URLError("offline test: urllib blocked")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _urlopen)

    # ── 4) socket 兜底（DNS 解析即擋）──
    def _gai(host, *a, **k):
        rec.note("socket.getaddrinfo", host)
        raise socket.gaierror("offline test: DNS blocked")
    monkeypatch.setattr(socket, "getaddrinfo", _gai)

    # ── 5) helper 層 spy（Storm Shield 快取命中時不到 transport）──
    from src.data.proxy import proxy_helper as _ph
    _orig_fu, _orig_relay = _ph.fetch_url, _ph.nas_relay_fetch

    def _spy_fu(url, *a, **k):
        rec.note("helper.fetch_url", url, k.get("params"))
        return _orig_fu(url, *a, **k)

    def _spy_relay(url, *a, **k):
        rec.note("helper.nas_relay_fetch", url)
        return _orig_relay(url, *a, **k)
    monkeypatch.setattr(_ph, "fetch_url", _spy_fu)          # ⚠️ patch 持有者，不 patch barrel（見 test_etf_moneydj_nav_parse 註）
    monkeypatch.setattr(_ph, "nas_relay_fetch", _spy_relay)
    from src.data.macro import macro_core as _mc
    monkeypatch.setattr(_mc, "fetch_url", _spy_fu)          # macro_core 在 import 時就綁了名字
    with _ph._URL_CACHE_LOCK:
        _ph._URL_CACHE.clear()

    # ── 6) 讓 fetch_url 三段（proxy／直連／中繼）都會發生 ──
    monkeypatch.setenv("PROXY_URL", "http://offline-proxy.invalid:3128")
    monkeypatch.setenv("NAS_BASE_URL", "http://offline-nas.invalid")
    monkeypatch.setenv("NAS_API_KEY", "dummy")
    _ph.reset_proxy_cache()
    import streamlit as _st
    monkeypatch.setattr(_st, "secrets", _FakeSecrets(), raising=False)

    # ── 7) yfinance 空殼 + 不睡 ──
    import yfinance as _yf
    monkeypatch.setattr(_yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(_yf, "download", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)

    # ── 8) 快取全清（前後都清：本檔造出的 None 不得污染其他測試）──
    _st.cache_data.clear()
    yield rec
    _st.cache_data.clear()
    _ph.reset_proxy_cache()
    with _ph._URL_CACHE_LOCK:
        _ph._URL_CACHE.clear()


# ════════════════════════════════════════════════════════════════════════
# 0. 正向對照：錄音機每一層都錄得到（否則「0 次」沒有意義）
# ════════════════════════════════════════════════════════════════════════
class TestRecorderSelfCheck:
    def test_requests_get_recorded(self, mdj):
        requests.get("https://www.moneydj.com/x")
        assert any("[requests]" in h for h in mdj.hits)

    def test_fetch_url_three_legs_recorded(self, mdj):
        from src.data.proxy import proxy_helper as _ph
        assert _ph.fetch_url("https://www.moneydj.com/probe", attempts=2) is None
        _layers = {h.split("]")[0] + "]" for h in mdj.hits}
        assert "[helper.fetch_url]" in _layers and "[helper.nas_relay_fetch]" in _layers
        # proxy 兩次 + 降級直連一次 + NAS 中繼（目標放在 params）一次 = 4 次 transport
        assert sum(1 for h in mdj.hits if h.startswith("[requests]")) == 4, mdj.report()
        assert any("offline-nas.invalid" in h and "moneydj" in h for h in mdj.hits)

    def test_curl_cffi_recorded(self, mdj):
        cr = pytest.importorskip("curl_cffi.requests")
        with pytest.raises(RuntimeError):
            cr.get("https://www.moneydj.com/y", impersonate="chrome124")
        with pytest.raises(RuntimeError):
            cr.Session().request("GET", "https://www.moneydj.com/z")
        assert len([h for h in mdj.hits if "curl_cffi" in h]) == 2

    def test_urllib_recorded(self, mdj):
        with pytest.raises(urllib.error.URLError):
            urllib.request.urlopen("https://www.moneydj.com/u")
        assert any("[urllib]" in h for h in mdj.hits)

    def test_socket_backstop_recorded(self, mdj):
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("www.moneydj.com", 443)
        assert any("socket" in h for h in mdj.hits)


# ════════════════════════════════════════════════════════════════════════
# 1. 各入口：MoneyDJ 出站 == 0
# ════════════════════════════════════════════════════════════════════════
class TestPmiEntries:
    """P1：`macro_core.fetch_tw_pmi` 平行競速 —— 前面的源命中，後面的源照樣送出請求。"""

    def test_fetch_tw_pmi_all_sources_fail(self, mdj, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)        # cache/ 與 data_cache/ 是相對路徑：不讀不寫真 repo
        from src.data.macro import macro_core as MC
        _r = MC.fetch_tw_pmi()
        assert _r.get("value") is None     # 全離線 → 誠實缺值（不得補 0／猜值）
        assert mdj.hits == [], mdj.report()

    def test_fetch_tw_pmi_top_source_hits(self, mdj, monkeypatch, tmp_path):
        """首源命中也不得對 MoneyDJ 發請求（GPT 指出：單看優先序不夠，race 會全送）。"""
        monkeypatch.chdir(tmp_path)
        from src.data.macro import macro_core as MC

        def _hit(today, max_age_days, errs):
            return {"value": 50.0, "date": f"{today:%Y-%m}-01", "label": "fake",
                    "source": "CIER-EN", "is_proxy": False, "series_id": "fake"}
        _reg = [(n, (_hit if n == "CIER-EN" else f)) for n, f in MC.PMI_SOURCE_REGISTRY]
        monkeypatch.setattr(MC, "PMI_SOURCE_REGISTRY", _reg)
        _r = MC.fetch_tw_pmi()
        assert _r.get("source") == "CIER-EN"
        assert mdj.hits == [], mdj.report()

    def test_update_macro_history_main_pmi_step(self, mdj, monkeypatch, tmp_path):
        """cron `update_macro_history.yml` 主路徑：`main()` 末段跑 runtime `fetch_tw_pmi()`。"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["update_macro_history.py", "--only", "__none__"])
        import scripts.update_macro_history as UMH
        assert UMH.main() == 0
        assert mdj.hits == [], mdj.report()


class TestEtfEntries:
    """P2–P7：ETF metadata／費用率／持股／淨值／中文名／追蹤指數。台股 0050 為代表。"""

    def test_get_etf_expense_ratio_safe(self, mdj):
        from src.data.etf import etf_fetch as EF
        _v = EF.get_etf_expense_ratio_safe("0050.TW")
        assert _v is None                  # 全源離線 → None（不得 0）
        assert mdj.hits == [], mdj.report()

    def test_get_etf_expense_ratio_safe_active(self, mdj):
        """主動式走 Yuanta 補位那條也不得碰 MoneyDJ。"""
        from src.data.etf import etf_fetch as EF
        EF.get_etf_expense_ratio_safe("00980A.TW")
        assert mdj.hits == [], mdj.report()

    def test_fetch_etf_info(self, mdj):
        from src.data.etf import etf_fetch as EF
        _info = EF.fetch_etf_info("0050.TW")
        assert _info.get("totalAssets") is None   # AUM 誠實缺（None），不補 0
        assert _info.get("expenseRatio") is None
        assert "MoneyDJ" not in str(_info.get("source", ""))
        assert mdj.hits == [], mdj.report()

    def test_fetch_etf_holdings(self, mdj):
        from src.data.etf import etf_fetch as EF
        assert EF.fetch_etf_holdings("0050.TW") is None
        assert mdj.hits == [], mdj.report()

    def test_fetch_etf_nav_history(self, mdj):
        from src.data.etf import etf_fetch as EF
        _df = EF.fetch_etf_nav_history("0050.TW", days=10)
        assert _df.empty
        assert mdj.hits == [], mdj.report()

    def test_fetch_etf_zh_name(self, mdj):
        from src.data.etf import etf_fetch as EF
        assert EF.fetch_etf_zh_name("0050.TW") is None
        assert mdj.hits == [], mdj.report()

    def test_fetch_etf_underlying_index_removed_or_silent(self, mdj):
        """P7 死碼：PR2 後應整個刪除；若仍存在，呼叫也不得碰 MoneyDJ。"""
        from src.data.etf import etf_fetch as EF
        _fn = getattr(EF, "fetch_etf_underlying_index", None)
        if _fn is not None:
            _fn("0050.TW")
        assert mdj.hits == [], mdj.report()

    def test_moneydj_only_symbols_gone(self):
        """MoneyDJ 專屬函式不得再存在（不需錄音機；純符號檢查）。"""
        from src.data.etf import etf_fetch as EF
        from src.data.macro import macro_core as MC
        _left = [n for n in ("fetch_etf_meta_moneydj", "fetch_moneydj_expense_ratio",
                             "fetch_etf_underlying_index") if hasattr(EF, n)]
        _left += [n for n in ("_pmi_src_moneydj",) if hasattr(MC, n)]
        assert _left == [], f"仍存在：{_left}"

    def test_pmi_registry_has_no_moneydj(self):
        from src.data.macro import macro_core as MC
        _names = [n for n, _ in MC.PMI_SOURCE_REGISTRY]
        assert "MoneyDJ" not in _names, _names


class TestDownstreamEntries:
    """AI 問答、ETF 品質評等、持股戰情室（cron push_holdings_daily 的逐檔引擎）。"""

    def test_compute_etf_quality(self, mdj):
        from src.compute.etf.etf_quality import compute_etf_quality
        _q = compute_etf_quality("0050.TW")
        # 全離線：AUM／費用率／Beta 皆缺 → 不得用 0 或猜值補出星等
        assert _q.get("stars") is None or _q.get("coverage", 1) < 1
        assert mdj.hits == [], mdj.report()

    def test_ai_qa_tool_get_etf_quality(self, mdj):
        from src.services import ai_qa_service as AQ
        _out = AQ._tool_get_etf_quality("0050")
        assert _out.get("ok") is False or _out.get("data")
        assert mdj.hits == [], mdj.report()

    def test_ai_qa_provenance_matches_actual_chain(self, monkeypatch):
        """給 LLM 看的來源字樣須逐字等於實際 caller 鏈（不得漏寫、不得寫成另一源）。

        原字樣「yfinance+SITCA」連「MoneyDJ 是費用率第一順位」都沒寫 —— 只查「不含 MoneyDJ」
        抓不到這種錯，故改逐字比對。
        """
        from src.services import ai_qa_service as AQ
        # patch 持有者（etf_quality），不 patch PEP 562 barrel（teardown 會把真函式釘成 package 屬性）
        from src.compute.etf import etf_quality as _EQ
        monkeypatch.setattr(_EQ, "compute_etf_quality",
                            lambda t: {"stars": 3, "score": 60, "coverage": 1.0, "factors": {}})
        _out = AQ._tool_get_etf_quality("0050")
        assert _out["ok"] is True
        assert _out["provenance"]["source"] == (
            "ETF 品質(AUM規模/費用率/配息穩定度/beta;"
            "AUM、Beta、配息＝yfinance；費用率＝SITCA→元大(主動式)→yfinance)")

    def test_station_fetch_metrics_etf(self, mdj, monkeypatch):
        """`push_holdings_daily.yml` → `get_station_rows` → `fetch_metrics`（ETF 腿）。

        日線是必要腿（無日線直接 raise，到不了後面的折溢價／品質腿）→ 以合成日線替身，
        讓折溢價（`fetch_etf_nav_history`）、品質（`compute_etf_quality`）、同儕三條腿真的跑到。
        """
        from shared import dividend_station_thresholds as T
        from src.data.etf import etf_fetch as EF
        _idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=1300)
        _px = pd.DataFrame({"Close": [100.0 + i * 0.01 for i in range(len(_idx))]}, index=_idx)
        monkeypatch.setattr(EF, "fetch_etf_price", lambda *a, **k: _px.copy())
        from src.services import dividend_station_service as DSS
        _failed: dict = {}
        DSS.fetch_metrics("0050", T.KIND_ETF, failed=_failed)
        assert mdj.hits == [], mdj.report()

    def test_station_resolve_holding_names(self, mdj):
        from src.services import dividend_station_service as DSS
        _h = [{"ticker": "0050", "name": "", "asset_kind": "etf"}]
        DSS.resolve_holding_names(_h)
        assert _h[0]["name"] == ""          # 抓不到留空（§1 不捏造）
        assert mdj.hits == [], mdj.report()


# ════════════════════════════════════════════════════════════════════════
# 2. 靜態守衛：production 原始碼不得出現 MoneyDJ 主機／頁面字面值
# ════════════════════════════════════════════════════════════════════════
_SCAN_DIRS = ("src", "scripts", "shared", ".github/workflows")
_SCAN_FILES = ("app.py", "app_ui2.py")
_SCAN_SUFFIX = {".py", ".yml", ".yaml", ".json", ".toml"}
_PAT = re.compile(r"moneydj\.com|\.x?djhtm\b", re.IGNORECASE)
#: 允許清單（檔案相對路徑 → 理由）。PR2 實作時預期為**空**；新增須寫明「純文件、無請求」的理由。
_ALLOW: dict[str, str] = {}


def _iter_scan_targets():
    for _d in _SCAN_DIRS:
        _p = REPO / _d
        if _p.is_dir():
            for _f in _p.rglob("*"):
                if _f.is_file() and _f.suffix in _SCAN_SUFFIX and "__pycache__" not in _f.parts:
                    yield _f
    for _n in _SCAN_FILES:
        if (REPO / _n).is_file():
            yield REPO / _n


def test_no_moneydj_host_literal_in_production_code():
    _bad = []
    for _f in _iter_scan_targets():
        _rel = _f.relative_to(REPO).as_posix()
        if _rel in _ALLOW:
            continue
        for _i, _line in enumerate(_f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _PAT.search(_line):
                _bad.append(f"{_rel}:{_i}: {_line.strip()[:120]}")
    assert _bad == [], "production 原始碼仍有 MoneyDJ 主機／頁面字面值：\n  " + "\n  ".join(_bad)


class TestEntryLevelPositiveControl:
    """入口層正向對照：把 MoneyDJ 段塞回 PMI registry，錄音機必須抓到（守衛不是恆綠）。"""

    def test_reinjected_moneydj_pmi_source_is_caught(self, mdj, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        from src.data.macro import macro_core as MC

        def _fake_moneydj(today, max_age_days, errs):
            MC.fetch_url("https://www.moneydj.com/KMDJ/Search/SearchListNew.aspx", timeout=1, attempts=1)
            return None
        monkeypatch.setattr(MC, "PMI_SOURCE_REGISTRY",
                            list(MC.PMI_SOURCE_REGISTRY) + [("MoneyDJ", _fake_moneydj)])
        MC.fetch_tw_pmi()
        assert mdj.hits, "錄音機沒錄到塞回去的 MoneyDJ 源 —— 入口層守衛失效"


def test_scan_targets_nonempty():
    """守衛自身：掃描範圍不得是空的（路徑寫錯會讓上一條恆綠）。"""
    _n = sum(1 for _ in _iter_scan_targets())
    assert _n > 100, _n
