"""D6（Issue #1113，客戶授權的資安最小修補）：舊版 API 診斷頁與側欄「只顯示狀態，不顯示任何值」。

═══ 守什麼 ═══════════════════════════════════════════════════════════════
舊版畫面會把下列東西送上畫面（任何看得到畫面的人都看得到）：
  · 金鑰「前 4 碼…後 4 碼 (len=N)」的遮罩預覽、`os.environ 同步` 欄的同款預覽；
  · 「已偵測到的 secrets keys：…」＝**全部** secrets key 名稱 + 數量；
  · Proxy 警告的 URL 片段、側欄的 `🔒 host:port`；
  · 探測結果的 `HTTP <code> <回應本文前 80 字>`、`<例外型別>: <例外原文>`（可能夾帶 URL／金鑰）。
現行（本檔守的）：**只剩**固定核准的 Key 名稱 + 已設定／未設定／解析失敗 + 來源標籤（st.secrets／os.environ／none）；
探測結果 **只剩** 成功／失敗、整數 HTTP 狀態碼、固定列舉的錯誤類別。

═══ 怎麼測（全部合成假秘密；⛔ 不讀真實憑證檔／環境、不連網）═════════════════
· 用 Streamlit `AppTest` 真的把頁面跑起來，收集**畫面上所有元素**（markdown／caption／metric／table／
  alert／button label…的 proto + table 的 DataFrame），再併上被捕捉的 stdout／stderr／logging，
  斷言一個假秘密、秘密的任一 4 字元片段、`len=`、`user:pass`、host／port、假回應本文都不在其中。
· `requests.get` 以替身取代（記錄每次呼叫 → 同時證明「請求語意一字未動」）。
· 側欄：從 `app.py` 以 AST **取出現行的那一段原始碼**（不是貼一份副本）放進真的 AppTest 執行。
· 突變：把舊行為（遮罩預覽／回應本文／例外原文）重新注入頁面原始碼 → 本檔的洩漏偵測必須轉紅。
"""
from __future__ import annotations

import ast
import importlib
import logging
import pathlib
import re
import sys
import textwrap

import pytest
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
_PAGE_SRC = ROOT / "src" / "ui" / "pages" / "api_diagnostic.py"
_APP_SRC = ROOT / "app.py"

# ══════════════════════════════════════════════════════════════════
# 合成假秘密（全部是假的；形狀刻意避開頁面靜態文字，讓「4 字元片段」檢查有鑑別力）
# ══════════════════════════════════════════════════════════════════
LONG = "ZQ-d6long_k3y-0123456789abcdefXYZ-vq7"            # 長
SHORT = "qZ9"                                              # 短（< 4 字元：整串視為片段）
SPECIAL = "p@ss\"w'rd*_[]{}<>&%\\d6~"                      # 特殊字元
PROXY_USER, PROXY_PW = "usr_d6", "pw_d6x"
PROXY_HOST, PROXY_PORT = "zq-nas.d6qz.exmpl", "31280"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PW}@{PROXY_HOST}:{PROXY_PORT}"
#: 使用者原文舉的形狀；只能用整串／元件比對（"http"、"host" 這類太通用的 4 字元片段會撞到靜態文字）
CLIENT_EXAMPLE_URL = "http://user:pass@host.example:3128"
BODY_MARK = "BODYLEAK-d6-echoes-"                           # 假回應本文
OTHER_SECRET_KEY_NAME = "SOME_OTHER_SECRET_NAME_d6"        # secrets 裡的其他 key（舊版會被「全部列出」）
OTHER_SECRET_VAL = "OTHERVAL-d6-zz81"
PATH_USER = "alicesec3d6"                                  # 出現在 secrets 檔案路徑裡的使用者名

_APPROVED = ("GEMINI_API_KEY", "FINMIND_TOKEN", "FRED_API_KEY", "PROXY_URL", "PROXY_HOST", "PROXY_PORT")
_ENV_NAMES = _APPROVED + ("NAS_PROXY_URL", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy")


def _frags(secret: str) -> set[str]:
    """秘密的任一 4 字元片段（長度 < 4 → 整串）。"""
    if len(secret) <= 4:
        return {secret}
    return {secret[i:i + 4] for i in range(len(secret) - 3)}


#: 單一假秘密 → 不得出現的字串集合
_SECRET_SETS: dict[str, set[str]] = {
    "LONG": {LONG} | _frags(LONG),
    "SHORT": {SHORT},
    "SPECIAL": {SPECIAL} | _frags(SPECIAL),
    "PROXY_URL": {PROXY_URL, f"{PROXY_USER}:{PROXY_PW}", f"{PROXY_PW}@", PROXY_HOST, PROXY_PORT,
                  f"{PROXY_HOST}:{PROXY_PORT}"}
                 | _frags(f"{PROXY_USER}:{PROXY_PW}@{PROXY_HOST}:{PROXY_PORT}"),
    "OTHER": {OTHER_SECRET_KEY_NAME, OTHER_SECRET_VAL} | _frags(OTHER_SECRET_VAL),
    "BODY": {BODY_MARK},
    "PATH": {PATH_USER},
}
_FORBIDDEN_PATTERNS = (
    re.compile(r"len\s*=\s*\d+", re.I),   # 舊版「(len=N)」
    re.compile(r"\(空\)"),                 # 舊版空值遮罩
    re.compile(r"user:pass"),              # 使用者原文舉的 proxy 帳密
)


def leaks_in(blob: str, *, groups: tuple[str, ...] | None = None) -> list[str]:
    """回傳 blob 內出現的所有不得出現的字串（空 list ＝ 乾淨）。"""
    hits: list[str] = []
    for name, strs in _SECRET_SETS.items():
        if groups is not None and name not in groups:
            continue
        hits += [f"{name}:{s!r}" for s in sorted(strs) if s and s in blob]
    for pat in _FORBIDDEN_PATTERNS:
        m = pat.search(blob)
        if m:
            hits.append(f"pattern:{m.group(0)!r}")
    return hits


# ══════════════════════════════════════════════════════════════════
# 把「畫面上所有東西」收成一個字串
# ══════════════════════════════════════════════════════════════════
def _walk(node):
    for ch in node.children.values():
        if hasattr(ch, "children"):
            yield from _walk(ch)
        else:
            yield ch


def screen_text(at) -> str:
    """AppTest 畫面（主區 + 側欄）所有元素：proto 全文 + table／dataframe 的實際內容。"""
    parts: list[str] = []
    for root in (at.main, at.sidebar):
        for el in _walk(root):
            proto = getattr(el, "proto", None)
            if proto is not None:
                parts.append(str(proto))
            val = getattr(el, "value", None)
            if hasattr(val, "to_json"):          # table／dataframe
                parts.append(val.to_json(force_ascii=False))
            elif isinstance(val, (str, int, float)):
                parts.append(str(val))
    # 例外元素（頁面崩潰時畫面上的 traceback）也算畫面
    parts += [str(e.value) for e in at.exception]
    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════
# 替身：requests.get（記錄呼叫）
# ══════════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, code: int, body: str):
        self.status_code = code
        self.text = body
        self.content = body.encode("utf-8")
        self.headers = {"X-Echo": body, "Set-Cookie": body}
        self.url = f"https://echo.test/?leak={body}"
        self.reason = body

    def json(self):
        return {"echo": self.text}


_HOST_ORDER = ("finmindtrade", "generativelanguage", "stlouisfed", "finance.yahoo", "twse.com.tw")


def _which(url: str) -> str:
    for h in _HOST_ORDER:
        if h in url:
            return h
    raise AssertionError(f"診斷頁打了預期之外的端點：{url!r}")


def _install_requests(monkeypatch, plan) -> list[dict]:
    """plan(host_key, proxied) → _Resp 或 例外實例。回傳記錄每次呼叫的 list。"""
    calls: list[dict] = []

    def _get(url, params=None, **kw):
        calls.append({"url": url, "params": params, **kw})
        beh = plan(_which(url), kw.get("proxies") is not None)
        if isinstance(beh, BaseException):
            raise beh
        return beh

    monkeypatch.setattr(requests, "get", _get)
    return calls


def _clean_env(monkeypatch):
    for k in _ENV_NAMES:
        monkeypatch.delenv(k, raising=False)


def _stub_proxy(monkeypatch, cfg):
    import src.data.proxy.proxy_helper as ph
    monkeypatch.setattr(ph, "get_proxy_config", lambda: cfg)


_DRIVER = """
import os, sys
sys.path.insert(0, os.getcwd())
{pre}
from {mod} import render_api_diagnostic
render_api_diagnostic()
"""


def _run_page(monkeypatch, capsys, caplog, *, secrets=None, env=None, click=False,
              mod="src.ui.pages.api_diagnostic", pre="", keep_stdio=False):
    """跑一次診斷頁 → (AppTest, blob)。blob ＝ 畫面 + stdout + stderr + logging。"""
    from streamlit.testing.v1 import AppTest
    caplog.set_level(logging.DEBUG)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    at = AppTest.from_string(_DRIVER.format(pre=pre, mod=mod), default_timeout=60)
    if secrets is not None:
        for k, v in secrets.items():
            at.secrets[k] = v
    capsys.readouterr()  # 清掉前面的輸出
    at.run()
    if click:
        at.button(key="api_diag_run").click().run()
    assert not at.exception, [str(e.value)[:200] for e in at.exception]
    out = capsys.readouterr()
    blob = "\n".join([screen_text(at), out.out, out.err, caplog.text])
    return at, blob


def _table(at) -> dict[str, dict[str, str]]:
    rows = at.table[0].value.to_dict("records")
    return {r["Key"]: r for r in rows}


# ══════════════════════════════════════════════════════════════════
# 0. 偵測器本身要有鑑別力（前提）
# ══════════════════════════════════════════════════════════════════
def test_baseline_page_contains_none_of_the_forbidden_strings(monkeypatch, capsys, caplog):
    """沒有任何秘密時，頁面靜態文字不得含任何「不得出現的字串」——否則 4 字元片段檢查會誤判／失去意義。"""
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    _, blob = _run_page(monkeypatch, capsys, caplog, secrets={"UNRELATED_FLAG": "1"})
    assert leaks_in(blob) == []


def test_leak_detector_catches_each_old_style_leak():
    for sample in (f"{LONG[:4]}…{LONG[-4:]} (len={len(LONG)})", "(空)", f"🔒 {PROXY_HOST}:{PROXY_PORT}",
                   f"HTTP 200 {BODY_MARK}", f"ConnectionError: x {PROXY_URL}", "user:pass@h", SHORT,
                   f"已偵測到的 secrets keys：`{OTHER_SECRET_KEY_NAME}`"):
        assert leaks_in(sample), sample


# ══════════════════════════════════════════════════════════════════
# 1. 靜態呈現：長／短／特殊字元／proxy URL／其他 secrets key
# ══════════════════════════════════════════════════════════════════
_ALL_SET = {
    "GEMINI_API_KEY": LONG, "FINMIND_TOKEN": SHORT, "FRED_API_KEY": SPECIAL,
    "PROXY_URL": PROXY_URL, "PROXY_HOST": PROXY_HOST, "PROXY_PORT": PROXY_PORT,
    OTHER_SECRET_KEY_NAME: OTHER_SECRET_VAL,
}


def test_page_shows_only_names_state_source_never_values(monkeypatch, capsys, caplog):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, {"http": PROXY_URL, "https": PROXY_URL})
    at, blob = _run_page(monkeypatch, capsys, caplog, secrets=dict(_ALL_SET))
    assert leaks_in(blob) == [], leaks_in(blob)
    # 正向：固定名稱、狀態、來源標籤仍在
    tbl = _table(at)
    assert list(tbl) == list(_APPROVED), "表只列固定核准的 Key 名稱，且順序固定"
    for name in _APPROVED:
        assert tbl[name]["狀態"] == "已設定" and tbl[name]["使用來源"] == "st.secrets", tbl[name]
    assert set(tbl["GEMINI_API_KEY"]) == {"Key", "狀態", "使用來源"}, "不得再有遮罩預覽／os.environ 同步欄"
    assert "Proxy 已設定" in blob
    # 其他 secrets 的 key 名稱與數量都不再上畫面（舊版：「已偵測到的 secrets keys：…」＋「Secrets keys 數」）
    assert OTHER_SECRET_KEY_NAME not in blob
    assert "secrets keys" not in blob.lower()
    assert "Secrets keys 數" not in blob


def test_client_example_proxy_url_is_never_rendered(monkeypatch, capsys, caplog):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, {"http": CLIENT_EXAMPLE_URL, "https": CLIENT_EXAMPLE_URL})
    _, blob = _run_page(monkeypatch, capsys, caplog,
                        secrets={"PROXY_URL": CLIENT_EXAMPLE_URL})
    for piece in (CLIENT_EXAMPLE_URL, "user:pass", "pass@", "host.example", "3128", "host.example:3128"):
        assert piece not in blob, piece
    assert "Proxy 已設定" in blob


def test_empty_and_unset_values_show_unset_not_a_mask(monkeypatch, capsys, caplog):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    at, blob = _run_page(monkeypatch, capsys, caplog,
                         secrets={"GEMINI_API_KEY": "", "FRED_API_KEY": ""})
    tbl = _table(at)
    assert tbl["GEMINI_API_KEY"]["狀態"] == "未設定" and tbl["GEMINI_API_KEY"]["使用來源"] == "none"
    assert tbl["FINMIND_TOKEN"]["狀態"] == "未設定"
    assert "(空)" not in blob and "(未設定)" not in blob and "len=" not in blob
    assert "Proxy 未設定" in blob


def test_env_fallback_reports_source_without_value(monkeypatch, capsys, caplog):
    """秘密只在 os.environ：來源標 os.environ、狀態已設定，值（含片段）不上畫面。"""
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    at, blob = _run_page(monkeypatch, capsys, caplog,
                         secrets={"UNRELATED_FLAG": "1"},
                         env={"GEMINI_API_KEY": LONG, "FINMIND_TOKEN": SHORT, "FRED_API_KEY": SPECIAL})
    assert leaks_in(blob) == [], leaks_in(blob)
    tbl = _table(at)
    for name in ("GEMINI_API_KEY", "FINMIND_TOKEN", "FRED_API_KEY"):
        assert tbl[name]["狀態"] == "已設定" and tbl[name]["使用來源"] == "os.environ", tbl[name]
    assert tbl["PROXY_URL"]["狀態"] == "未設定" and tbl["PROXY_URL"]["使用來源"] == "none"


def test_no_secrets_file_at_all_unset_keys_say_unset_not_parse_failure(monkeypatch, capsys, caplog, tmp_path):
    """CI／本機常見：根本沒有 secrets 檔（真的 Secrets 物件，路徑指向不存在的檔）。
    env 有的 → 已設定(os.environ)；env 沒有的 → **未設定**（不是「解析失敗」）。精確斷言，不再接受兩種。"""
    import streamlit as st
    from streamlit import config as st_config
    from streamlit.runtime.secrets import Secrets
    orig = st_config.get_option("secrets.files")
    st_config.set_option("secrets.files", [str(tmp_path / "nope" / "secrets.toml")])
    try:
        secrets_obj = Secrets()
        with pytest.raises(Exception):                       # 前提：這個物件對任何 key 都會丟例外
            "GEMINI_API_KEY" in secrets_obj
        _clean_env(monkeypatch)
        monkeypatch.setattr(st, "secrets", secrets_obj)
        _stub_proxy(monkeypatch, None)
        at, blob = _run_page(monkeypatch, capsys, caplog, env={"FRED_API_KEY": LONG})
    finally:
        st_config.set_option("secrets.files", orig)
    assert leaks_in(blob) == [], leaks_in(blob)
    assert str(tmp_path) not in blob
    tbl = _table(at)
    assert tbl["FRED_API_KEY"]["狀態"] == "已設定" and tbl["FRED_API_KEY"]["使用來源"] == "os.environ"
    for name in ("GEMINI_API_KEY", "FINMIND_TOKEN", "PROXY_URL", "PROXY_HOST", "PROXY_PORT"):
        assert tbl[name]["狀態"] == "未設定" and tbl[name]["使用來源"] == "none", (name, tbl[name])
    assert "解析失敗" not in "".join(r["狀態"] for r in tbl.values())


def test_existing_but_broken_secrets_file_stays_parse_failure(monkeypatch, capsys, caplog, broken_secrets):
    """對照組：檔案存在但壞掉 → 沒有 env 的 key 仍是「解析失敗」（不得被上面的修正吃成「未設定」）。"""
    import streamlit as st
    monkeypatch.setattr(st, "secrets", broken_secrets[0])
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    at, _ = _run_page(monkeypatch, capsys, caplog)
    tbl = _table(at)
    assert all(r["狀態"] == "解析失敗" for r in tbl.values())


# ══════════════════════════════════════════════════════════════════
# 2. secrets TOML 解析失敗（真的壞檔）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def broken_secrets(tmp_path):
    from streamlit import config as st_config
    from streamlit.runtime.secrets import Secrets

    d = tmp_path / f"home_{PATH_USER}" / ".streamlit"
    d.mkdir(parents=True)
    path = d / "secrets.toml"
    # 失敗那一行之前放假金鑰；Streamlit 的解析錯誤會帶檔案完整路徑
    path.write_text(f'GEMINI_API_KEY = "{LONG}"\nbroken = "abc\n', encoding="utf-8")
    orig = st_config.get_option("secrets.files")
    st_config.set_option("secrets.files", [str(path)])
    yield Secrets(), path
    st_config.set_option("secrets.files", orig)


def test_secrets_parse_failure_shows_state_only(monkeypatch, capsys, caplog, broken_secrets):
    import streamlit as st
    secrets_obj, path = broken_secrets
    with pytest.raises(Exception) as ei:                     # 前提：真的會炸、且訊息帶路徑
        list(secrets_obj.keys())
    assert str(path) in str(ei.value), "前提變了：Streamlit 的解析錯誤不再帶路徑"
    _clean_env(monkeypatch)
    monkeypatch.setattr(st, "secrets", secrets_obj)
    # 用「真的」get_proxy_config（不替身）：它在 secrets 壞掉時會把例外原文印到 stderr —— 本頁不得讓它外露
    import src.data.proxy.proxy_helper as ph
    monkeypatch.setattr(ph, "_PROXY_CFG_CACHE", None)
    monkeypatch.setattr(ph, "_PROXY_CFG_TS", 0.0)
    at, blob = _run_page(monkeypatch, capsys, caplog,
                         env={"FINMIND_TOKEN": SPECIAL, "PROXY_URL": PROXY_URL})
    assert leaks_in(blob) == [], leaks_in(blob)
    assert str(path) not in blob and str(path.parent) not in blob
    for exc_word in ("StreamlitSecretNotFoundError", "TOMLDecodeError", "Unbalanced", "secrets.toml"):
        assert exc_word not in blob, exc_word
    tbl = _table(at)
    assert tbl["FINMIND_TOKEN"]["狀態"] == "已設定" and tbl["FINMIND_TOKEN"]["使用來源"] == "os.environ"
    assert tbl["GEMINI_API_KEY"]["狀態"] == "解析失敗" and tbl["GEMINI_API_KEY"]["使用來源"] == "none"
    assert "解析失敗" in blob and "Proxy 已設定" in blob
    assert at.metric[1].value == "❌"


def test_premise_proxy_helper_prints_exception_text_to_stderr(monkeypatch, capsys, broken_secrets):
    """前提（反證「不遮蔽就會外露」）：未包裝的 get_proxy_config 在壞 secrets 下確實把含路徑的例外原文印到 stderr。
    本頁用 stderr 導向丟棄擋住它；若上游日後自己修了，這條會先說（那時可移除導向）。"""
    import streamlit as st
    import src.data.proxy.proxy_helper as ph
    secrets_obj, _ = broken_secrets
    _clean_env(monkeypatch)
    monkeypatch.setattr(st, "secrets", secrets_obj)
    monkeypatch.setattr(ph, "_PROXY_CFG_CACHE", None)
    monkeypatch.setattr(ph, "_PROXY_CFG_TS", 0.0)
    capsys.readouterr()
    ph.get_proxy_config()
    assert PATH_USER in capsys.readouterr().err, "前提變了：get_proxy_config 不再把例外原文印到 stderr"


# ══════════════════════════════════════════════════════════════════
# 3. 探測結果：2xx／4xx／5xx 回應本文含假金鑰、例外訊息含金鑰與 URL
# ══════════════════════════════════════════════════════════════════
def _plan(host: str, proxied: bool):
    body = f"{BODY_MARK}{LONG} {SPECIAL} {PROXY_URL} {SHORT}"
    if proxied:
        return {
            "finmindtrade": _Resp(200, body),
            "generativelanguage": requests.exceptions.ConnectionError(
                f"HTTPSConnectionPool(host='x'): Max retries url: /v1beta/models?key={LONG} via {PROXY_URL}"),
            "stlouisfed": requests.exceptions.ReadTimeout(f"timed out GET api_key={SPECIAL} {PROXY_URL}"),
            "finance.yahoo": requests.exceptions.ProxyError(f"Cannot connect to proxy {PROXY_URL} key={LONG}"),
            "twse.com.tw": ValueError(f"weird {LONG} {BODY_MARK}"),
        }[host]
    return {
        "finmindtrade": _Resp(401, body),
        "generativelanguage": _Resp(503, body),
        "stlouisfed": _Resp(404, body),
        "finance.yahoo": _Resp(200, body),
        "twse.com.tw": _Resp(403, body),
    }[host]


def test_probe_results_are_status_and_category_only(monkeypatch, capsys, caplog):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, {"http": PROXY_URL, "https": PROXY_URL})
    calls = _install_requests(monkeypatch, _plan)
    at, blob = _run_page(monkeypatch, capsys, caplog, secrets=dict(_ALL_SET), click=True)
    assert leaks_in(blob) == [], leaks_in(blob)
    # 例外型別名／訊息片段也不得外露（只剩固定類別）
    for w in ("ReadTimeout", "ValueError", "HTTPSConnectionPool",
              "Max retries", "timed out", "Cannot connect", "weird", "api_key=", "?key="):
        assert w not in blob, w
    # 靜態說明文字本來就會提到 ConnectionError／ProxyError 這兩個詞；要擋的是「<型別>: <訊息>」的回顯格式
    assert not re.search(r"\b(ConnectionError|ProxyError|ReadTimeout|ValueError)\s*:", blob)
    # 正向：整數 HTTP 狀態碼 + 固定錯誤類別都在
    for want in ("HTTP 200", "HTTP 401", "HTTP 403", "HTTP 404", "HTTP 503",
                 "認證失敗(401/403)", "伺服器錯誤(5xx)", "其他", "連線失敗", "逾時", "代理錯誤"):
        assert want in blob, want
    # 請求語意一字未動：10 次（5 端點 × 走 proxy／直連）、verify=False、timeout=8、proxies 照傳
    assert len(calls) == 10
    assert all(c["verify"] is False and c["timeout"] == 8 for c in calls)
    assert sum(1 for c in calls if c.get("proxies") is not None) == 5
    # 順序：每個端點先走 proxy、再直連
    assert [c.get("proxies") is not None for c in calls] == [True, False] * 5
    by = {(_which(c["url"]), c.get("proxies") is not None): c for c in calls}
    fm = by[("finmindtrade", False)]
    assert fm["headers"]["Authorization"] == f"Bearer {SHORT}", "憑證仍只走 header（請求語意不變）"
    assert fm["params"] == {"dataset": "TaiwanStockInfo", "stock_id": "2330"}
    assert by[("generativelanguage", False)]["headers"]["x-goog-api-key"] == LONG
    assert by[("stlouisfed", False)]["params"]["api_key"] == SPECIAL, "FRED 仍用 api_key query（API 端限制）"
    assert by[("twse.com.tw", False)]["params"] is None


@pytest.mark.parametrize("code,want", [(200, None), (204, None), (301, None), (400, "其他"), (401, "認證失敗(401/403)"),
                                       (403, "認證失敗(401/403)"), (404, "其他"), (429, "其他"),
                                       (500, "伺服器錯誤(5xx)"), (502, "伺服器錯誤(5xx)"), (599, "伺服器錯誤(5xx)")])
def test_probe_status_codes_map_to_fixed_categories(monkeypatch, code, want):
    import src.ui.pages.api_diagnostic as AD
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp(code, f"{BODY_MARK}{LONG}"))
    ok, msg = AD._probe("t", "https://x.test", {"api_key": LONG}, headers={"Authorization": f"Bearer {LONG}"})
    assert ok is (want is None)
    assert msg == (f"HTTP {code}" if want is None else f"HTTP {code}（{want}）")
    assert leaks_in(msg) == []


@pytest.mark.parametrize("exc,want", [
    (requests.exceptions.ProxyError("x"), "代理錯誤"),
    (requests.exceptions.ConnectTimeout("x"), "逾時"),       # 同時是 ConnectionError 子類，要判為逾時
    (requests.exceptions.ReadTimeout("x"), "逾時"),
    (requests.exceptions.ConnectionError("x"), "連線失敗"),
    (requests.exceptions.SSLError("x"), "連線失敗"),
    (requests.exceptions.InvalidURL("x"), "其他"),
    (ValueError("x"), "其他"),
    (KeyError("x"), "其他"),
])
def test_probe_exceptions_map_to_fixed_categories_and_never_echo_text(monkeypatch, exc, want):
    import src.ui.pages.api_diagnostic as AD
    exc.args = (f"boom {LONG} {PROXY_URL} {BODY_MARK}",)

    def _boom(*a, **k):
        raise exc

    monkeypatch.setattr(requests, "get", _boom)
    ok, msg = AD._probe("t", "https://x.test", {"api_key": LONG})
    assert ok is False and msg == want
    assert msg in AD.ERROR_CATEGORIES


def test_probe_nonint_status_is_other_not_echoed(monkeypatch):
    import src.ui.pages.api_diagnostic as AD

    class _Weird:
        status_code = f"{BODY_MARK}{LONG}"
        text = "t"

    monkeypatch.setattr(requests, "get", lambda *a, **k: _Weird())
    assert AD._probe("t", "https://x.test") == (False, "其他")


def test_page_probe_without_proxy_shows_direct_only(monkeypatch, capsys, caplog):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    calls = _install_requests(monkeypatch, lambda host, proxied: _Resp(200, f"{BODY_MARK}{LONG}"))
    _, blob = _run_page(monkeypatch, capsys, caplog, secrets={"FRED_API_KEY": LONG}, click=True)
    assert leaks_in(blob) == []
    assert len(calls) == 5 and all(c.get("proxies") is None for c in calls), "未設 proxy → 只打直連 5 次"
    assert blob.count("HTTP 200") >= 5 and "略過" in blob


def test_page_never_prints_or_logs_anything_with_values(monkeypatch, capsys, caplog):
    """stdout／stderr／logging（DEBUG）三個管道單獨檢查（_run_page 的 blob 已含，這裡分開講清楚來源）。"""
    from streamlit.testing.v1 import AppTest
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, {"http": PROXY_URL, "https": PROXY_URL})
    _install_requests(monkeypatch, _plan)
    caplog.set_level(logging.DEBUG)
    at = AppTest.from_string(_DRIVER.format(pre="", mod="src.ui.pages.api_diagnostic"), default_timeout=60)
    for k, v in _ALL_SET.items():
        at.secrets[k] = v
    capsys.readouterr()
    at.run()
    at.button(key="api_diag_run").click().run()
    out = capsys.readouterr()
    assert leaks_in(out.out) == [] and leaks_in(out.err) == [] and leaks_in(caplog.text) == []


def test_page_source_has_no_print_logging_or_body_access():
    """靜態守衛：頁面原始碼不得 print／logging，也不得再碰回應本文／例外字串化（防未來回歸）。"""
    src = _PAGE_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            assert n.func.id != "print", "診斷頁不得 print"
        if isinstance(n, ast.Import):
            assert "logging" not in [a.name for a in n.names]
        if isinstance(n, ast.Attribute):
            assert n.attr not in ("text", "content", "json", "headers", "url"), f"不得讀回應欄位 {n.attr!r}"
    assert "_mask" not in src and "len=" not in src and "preview" not in src
    assert "scrub" not in src.split('"""', 2)[2], "訊息已無例外原文，不再依賴清洗當第一道防線"
    assert "verify=False" in src and "timeout=timeout" in src, "請求語意（verify/timeout）不得被動到"


# ══════════════════════════════════════════════════════════════════
# 4. 側欄：從 app.py 以 AST 取出現行的那一段原始碼，放進真的 AppTest 執行
# ══════════════════════════════════════════════════════════════════
def _sidebar_driver() -> str:
    tree = ast.parse(_APP_SRC.read_text(encoding="utf-8"))
    get_secret = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_get_secret")
    withs = [n for n in tree.body if isinstance(n, ast.With)
             and "st.sidebar" in ast.unparse(n.items[0].context_expr)
             and any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_fm_tok"
                                                         for t in s.targets) for s in n.body)]
    assert len(withs) == 1, "app.py 應恰有一個含 `_fm_tok =` 的側欄區塊"
    body = withs[0].body
    start = next(i for i, s in enumerate(body) if isinstance(s, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "_fm_tok" for t in s.targets))
    end = next(i for i, s in enumerate(body) if isinstance(s, ast.If) and "測試連線" in ast.unparse(s.test))
    block = textwrap.indent("\n".join(ast.unparse(s) for s in body[start:end]), "    ")
    return (
        "import os, sys\nsys.path.insert(0, os.getcwd())\nimport streamlit as st\n"
        "from src.services.app_ai_service import GEMINI_KEY_NAMES as _GEMINI_KEY_NAMES, "
        "gemini_keys as _gemini_keys\n"
        f"{ast.unparse(get_secret)}\n"
        f"with st.sidebar:\n{block}\n"
    )


def _run_sidebar(monkeypatch, *, secrets=None, env=None, broken=None):
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    _clean_env(monkeypatch)
    for n in ("GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        monkeypatch.delenv(n, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    if broken is not None:
        monkeypatch.setattr(st, "secrets", broken)
    at = AppTest.from_string(_sidebar_driver(), default_timeout=60)
    for k, v in (secrets or {}).items():
        at.secrets[k] = v
    at.run()
    assert not at.exception, [str(e.value)[:200] for e in at.exception]
    return at, screen_text(at)


def test_sidebar_driver_really_contains_the_proxy_block():
    drv = _sidebar_driver()
    assert "_px_set" in drv and "Proxy" in drv and "_get_secret('PROXY_HOST')" in drv


@pytest.mark.parametrize("secrets", [
    {"PROXY_URL": PROXY_URL},
    {"PROXY_HOST": PROXY_HOST, "PROXY_PORT": PROXY_PORT},
    {"PROXY_HOST": PROXY_HOST, "PROXY_PORT": PROXY_PORT, "PROXY_URL": PROXY_URL},
    {"PROXY_URL": CLIENT_EXAMPLE_URL},
], ids=["url_only", "host_port", "all_three", "client_example_url"])
def test_sidebar_proxy_set_shows_status_only(monkeypatch, secrets):
    at, text = _run_sidebar(monkeypatch, secrets=secrets)
    assert "Proxy ✅ 已設定" in text and "🔒 Proxy 已設定" in text
    assert [s.value for s in at.sidebar.success if "Proxy" in s.value] == ["Proxy ✅ 已設定"]
    assert leaks_in(text, groups=("PROXY_URL",)) == [], leaks_in(text, groups=("PROXY_URL",))
    for piece in (CLIENT_EXAMPLE_URL, "user:pass", "host.example", "3128", PROXY_HOST, PROXY_PORT):
        assert piece not in text, piece
    assert "未設定" not in text


def test_sidebar_proxy_unset_shows_unset(monkeypatch):
    at, text = _run_sidebar(monkeypatch)
    assert [w.value for w in at.sidebar.warning if "Proxy" in w.value] == ["Proxy — 未設定"]
    assert "🔒" not in text and "已設定" not in text.replace("Proxy ✅ 已設定", "")


def test_sidebar_proxy_env_fallback_shows_status_only(monkeypatch):
    at, text = _run_sidebar(monkeypatch, secrets={"UNRELATED_FLAG": "1"}, env={"PROXY_URL": PROXY_URL})
    assert "Proxy ✅ 已設定" in text
    assert leaks_in(text, groups=("PROXY_URL",)) == []


def test_sidebar_proxy_with_broken_secrets_is_clean(monkeypatch, broken_secrets):
    secrets_obj, path = broken_secrets
    at, text = _run_sidebar(monkeypatch, broken=secrets_obj, env={"PROXY_HOST": PROXY_HOST, "PROXY_PORT": PROXY_PORT})
    assert "Proxy ✅ 已設定" in text
    assert leaks_in(text) == [] and PATH_USER not in text


def test_sidebar_gemini_lamp_still_shows_names_not_values(monkeypatch):
    """鄰近燈號不得被連帶改壞：Gemini 仍只列『欄位名稱』；FinMind 燈照舊。"""
    at, text = _run_sidebar(monkeypatch, secrets={"GEMINI_API_KEY": LONG, "FINMIND_TOKEN": SHORT})
    assert "FinMind ✅" in text and "GEMINI_API_KEY" in text and "Gemini ✅" in text
    assert leaks_in(text, groups=("LONG", "SHORT")) == []


def test_app_sidebar_source_never_binds_proxy_values():
    """靜態守衛：app.py 不得再把 PROXY_* 的值存進變數或組字串（防回歸）。"""
    src = _APP_SRC.read_text(encoding="utf-8")
    assert "_px_host" not in src.replace("`_fm_tok / _gm_keys / _px_set`", "") and "_px_port" not in src
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.JoinedStr):
            seg = ast.unparse(n)
            assert "_px_" not in seg and "PROXY" not in seg, seg


# ══════════════════════════════════════════════════════════════════
# 5. 突變：把舊行為重新注入頁面原始碼 → 洩漏偵測必須轉紅（證明本檔真的守得住）
# ══════════════════════════════════════════════════════════════════
_MUTANT_MODNAME = "d6_mutant_api_diagnostic"

_MUTATIONS = {
    # 遮罩預覽（前 4 + 後 4 + 長度）重新出現在 Key 表
    "mask_preview": (
        "{'Key': r['name'], '狀態': r['state'], '使用來源': r['source']}",
        "{'Key': r['name'], '狀態': r['state'], '使用來源': r['source'], "
        "'實際值（遮罩）': (str(r['val'])[:4] + '…' + str(r['val'])[-4:] + f\" (len={len(str(r['val']))})\") "
        "if r['val'] else '(空)'}",
    ),
    # 回應本文片段重新上畫面
    "body_snippet": (
        "return True, f'HTTP {code}'",
        "return True, f'HTTP {code} ' + (r.text or '')[:80]",
    ),
    # 例外原文重新上畫面
    "exception_text": (
        "return False, _classify_exception(e)",
        "return False, f'{type(e).__name__}: {e}'",
    ),
    # 列出全部 secrets key 名稱
    "secrets_key_listing": (
        "list(sec_obj.keys())  # 只為測",
        "st.caption('已偵測到的 secrets keys：' + ', '.join(sec_obj.keys()))  # 只為測",
    ),
}


def _load_mutant(tmp_path, key: str):
    old, new = _MUTATIONS[key]
    src = _PAGE_SRC.read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變錨點應恰出現一次：{key}"
    (tmp_path / f"{_MUTANT_MODNAME}.py").write_text(src.replace(old, new), encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    sys.modules.pop(_MUTANT_MODNAME, None)
    importlib.invalidate_caches()
    return _MUTANT_MODNAME


@pytest.mark.parametrize("key", list(_MUTATIONS))
def test_mutation_reintroducing_old_display_is_caught(monkeypatch, capsys, caplog, tmp_path, key):
    mod = _load_mutant(tmp_path, key)
    try:
        _clean_env(monkeypatch)
        _stub_proxy(monkeypatch, {"http": PROXY_URL, "https": PROXY_URL})
        _install_requests(monkeypatch, _plan)
        # 讓突變碼 import 得到：頁面本身用 `from src.config import ...`，cwd=repo root 即可
        _, blob = _run_page(monkeypatch, capsys, caplog, secrets=dict(_ALL_SET), click=True,
                            mod=mod, pre=f"sys.path.insert(0, {str(tmp_path)!r})")
        assert leaks_in(blob), f"突變 {key} 沒被偵測到——本檔的守衛失效"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(_MUTANT_MODNAME, None)


def test_unmutated_page_passes_the_same_check(monkeypatch, capsys, caplog):
    """對照組：同一組輸入、同一個偵測器，未突變的真檔案是乾淨的（突變測試的紅不是偵測器過敏）。"""
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, {"http": PROXY_URL, "https": PROXY_URL})
    _install_requests(monkeypatch, _plan)
    _, blob = _run_page(monkeypatch, capsys, caplog, secrets=dict(_ALL_SET), click=True)
    assert leaks_in(blob) == []


# ══════════════════════════════════════════════════════════════════
# 6. QA M1：stderr 交換必須執行緒安全，且例外原文到不了 Streamlit 的紅色 traceback 框
# ══════════════════════════════════════════════════════════════════
import threading
import time


def _hammer_quiet(monkeypatch, AD, n=6, hold=0.15, stagger=0.02):
    """n 個執行緒（錯開 `stagger` 秒、每次呼叫在 get_proxy_config 內停 `hold` 秒）同時走 `_get_proxy_config_quiet`。
    回傳 (交換前的 sys.stderr, 交換後的 sys.stderr, 視窗內各執行緒看到的 sys.stderr 是否都是 StringIO)。"""
    import io
    import src.data.proxy.proxy_helper as ph
    seen: list[bool] = []

    def _slow():
        seen.append(isinstance(sys.stderr, io.StringIO))
        time.sleep(hold)
        return {"http": PROXY_URL, "https": PROXY_URL}

    monkeypatch.setattr(ph, "get_proxy_config", _slow)
    before = sys.stderr
    results: list = []

    def _worker(i):
        time.sleep(i * stagger)
        results.append(AD._get_proxy_config_quiet())

    ts = [threading.Thread(target=_worker, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in ts)
    assert len(results) == n
    return before, sys.stderr, seen, results


def test_concurrent_sessions_leave_sys_stderr_exactly_as_found(monkeypatch):
    import src.ui.pages.api_diagnostic as AD
    before, after, seen, results = _hammer_quiet(monkeypatch, AD)
    assert after is before, "多執行緒交錯後 sys.stderr 不是原本那個物件（M1）"
    assert all(seen), "視窗內 stderr 應被導向丟棄緩衝"
    assert all(r == ({"http": PROXY_URL, "https": PROXY_URL}, False) for r in results), "回傳值語意不變"


def test_mutation_without_the_lock_the_same_scenario_corrupts_stderr(monkeypatch):
    """突變：把鎖換成空操作（＝舊的 redirect_stderr 交錯行為）→ 同一情境必須留下被污染的 sys.stderr。
    證明上一條真的有鑑別力（鎖被拿掉它會紅），而不是情境太鬆。"""
    import contextlib
    import src.ui.pages.api_diagnostic as AD
    monkeypatch.setattr(AD, "_STDERR_LOCK", contextlib.nullcontext())
    before = sys.stderr
    try:
        _, after, _, _ = _hammer_quiet(monkeypatch, AD)
        assert after is not before, "無鎖版本沒有被污染——情境沒有鑑別力"
    finally:
        sys.stderr = before   # 把被突變污染的全域還原，免得拖累後面的測試


def test_old_redirect_stderr_implementation_would_also_fail_this_scenario(monkeypatch):
    """對照舊實作（contextlib.redirect_stderr 無鎖）本身：同一情境下同樣被污染（M1 的原始重現）。"""
    import contextlib
    import io
    import src.ui.pages.api_diagnostic as AD

    def _old_quiet():
        from src.data.proxy import get_proxy_config
        with contextlib.redirect_stderr(io.StringIO()):
            return get_proxy_config(), False

    monkeypatch.setattr(AD, "_get_proxy_config_quiet", _old_quiet)
    before = sys.stderr
    try:
        _, after, _, _ = _hammer_quiet(monkeypatch, AD)
        assert after is not before
    finally:
        sys.stderr = before


def test_stderr_restored_when_get_proxy_config_raises_and_text_never_escapes(monkeypatch):
    import src.data.proxy.proxy_helper as ph
    import src.ui.pages.api_diagnostic as AD

    def _boom():
        raise RuntimeError(f"boom {LONG} {PROXY_URL} {BODY_MARK}")

    monkeypatch.setattr(ph, "get_proxy_config", _boom)
    before = sys.stderr
    got = AD._get_proxy_config_quiet()          # 不得把例外拋出去（否則文字會進 Streamlit 的紅色 traceback 框）
    assert got == (None, True)
    assert sys.stderr is before
    assert not AD._STDERR_LOCK.locked(), "例外後鎖必須釋放"
    assert AD._get_proxy_config_quiet() == (None, True)   # 鎖沒卡死，可再進入


def test_stderr_restored_even_for_baseexception(monkeypatch):
    import src.data.proxy.proxy_helper as ph
    import src.ui.pages.api_diagnostic as AD

    def _kb():
        raise KeyboardInterrupt()

    monkeypatch.setattr(ph, "get_proxy_config", _kb)
    before = sys.stderr
    with pytest.raises(KeyboardInterrupt):
        AD._get_proxy_config_quiet()
    assert sys.stderr is before and not AD._STDERR_LOCK.locked()


def test_page_when_proxy_config_raises_shows_fixed_text_only(monkeypatch, capsys, caplog):
    import src.data.proxy.proxy_helper as ph
    _clean_env(monkeypatch)

    def _boom():
        raise RuntimeError(f"boom {LONG} {PROXY_URL} {BODY_MARK}")

    monkeypatch.setattr(ph, "get_proxy_config", _boom)
    calls = _install_requests(monkeypatch, lambda host, proxied: _Resp(200, f"{BODY_MARK}{LONG}"))
    at, blob = _run_page(monkeypatch, capsys, caplog, secrets={"FRED_API_KEY": LONG}, click=True)
    assert not at.exception                                   # 沒有紅色 traceback 框
    assert leaks_in(blob) == [], leaks_in(blob)
    assert "RuntimeError" not in blob and "boom" not in blob
    assert "Proxy 設定讀取失敗" in blob
    assert "Proxy 未設定" not in blob, "讀取失敗不得被說成『未設定』"
    assert len(calls) == 5 and all(c.get("proxies") is None for c in calls), "失敗時只做直連，不假裝有 proxy"
    assert "略過（proxy 設定讀取失敗）" in blob


def test_premise_still_holds_stderr_leak_vector_is_real_and_page_contains_it(monkeypatch, capsys, broken_secrets):
    """保留的前提測試（再確認一次）：未包裝時確實外洩；經 `_get_proxy_config_quiet` 後 stderr 乾淨且被還原。"""
    import streamlit as st
    import src.data.proxy.proxy_helper as ph
    import src.ui.pages.api_diagnostic as AD
    _clean_env(monkeypatch)
    monkeypatch.setattr(st, "secrets", broken_secrets[0])
    monkeypatch.setattr(ph, "_PROXY_CFG_CACHE", None)
    monkeypatch.setattr(ph, "_PROXY_CFG_TS", 0.0)
    capsys.readouterr()
    ph.get_proxy_config()
    assert PATH_USER in capsys.readouterr().err
    monkeypatch.setattr(ph, "_PROXY_CFG_CACHE", None)
    monkeypatch.setattr(ph, "_PROXY_CFG_TS", 0.0)
    before = sys.stderr
    AD._get_proxy_config_quiet()
    assert sys.stderr is before
    assert PATH_USER not in capsys.readouterr().err
