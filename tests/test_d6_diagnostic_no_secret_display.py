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
· R23.22（widget id 的隨機 md5 與假金鑰純 hex 片段偶發碰撞）：**不遮蔽、不正規化任何被掃描文字**——掃描一律是
  完整 `str(proto)`／table 內容／stdout／stderr／log 的全量比對（與修補前等效，連 `$$ID-<32hex>-` 的雜湊槽位也掃）。
  碰撞改由「確定性環境」根治：AppTest 把腳本寫在 `streamlit.testing.v1.app_test.TMP_DIR`（每個 pytest 行程隨機）下，
  widget id 的 md5 取決於腳本路徑 → 本檔把 TMP_DIR 換成固定可重現的候選目錄序列，並用「乾淨探針」（無秘密、無洩漏）
  選出使該腳本畫面完全不含任何禁止片段的第一個候選（見第 7 節與 `_select_dir`）。
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib
import inspect
import logging
import os
import pathlib
import re
import stat
import sys
import tempfile
import textwrap
import types

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


def _screen_text_with(at, proto_text) -> str:
    """畫面全文；`proto_text` 只是給第 7 節「遮蔽型突變」用的接縫——正式路徑（`screen_text`）恆為逐字 `str`。"""
    parts: list[str] = []
    for root in (at.main, at.sidebar):
        for el in _walk(root):
            proto = getattr(el, "proto", None)
            if proto is not None:
                parts.append(proto_text(proto))
            val = getattr(el, "value", None)
            if hasattr(val, "to_json"):          # table／dataframe
                parts.append(val.to_json(force_ascii=False))
            elif isinstance(val, (str, int, float)):
                parts.append(str(val))
    # 例外元素（頁面崩潰時畫面上的 traceback）也算畫面
    parts += [str(e.value) for e in at.exception]
    return "\n".join(parts)


def screen_text(at) -> str:
    """AppTest 畫面（主區 + 側欄）所有元素：proto 全文（逐字 `str(proto)`，含 widget id 的 32 位 hex 雜湊槽位，
    **不遮蔽、不正規化**）+ table／dataframe 的實際內容。"""
    return _screen_text_with(at, str)


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


# ══════════════════════════════════════════════════════════════════
# R23.22：確定性 widget-id 環境（根治「隨機 md5 剛好含假金鑰的純 hex 片段」，且**不遮蔽任何被掃描文字**）
# ──────────────────────────────────────────────────────────────────
# 根因：Button 等元件 proto 帶 `id: "$$ID-<32 位 hex md5>-<user key>"`；md5 含 `active_script_hash`＝AppTest 腳本路徑的 hash，
# 而腳本被寫在 `app_test.TMP_DIR`（模組層 TemporaryDirectory，每個 pytest 行程隨機）→ 每個行程 id 不同，約 0.04～0.6% 機率
# 剛好含 `LONG` 的純十六進位 4 字元片段（0123…cdef、789a…）→ 偵測器把「元件 id 的雜湊」誤判成洩漏。
# 做法：本檔所有「斷言乾淨」的 AppTest 都改用固定、可重現的候選目錄序列（系統暫存下 `stock_d6_fixture_<uid>/k0000…`）；
# 對每個**不同腳本內容**，先在乾淨情境（無秘密、無環境、無洩漏）探針：依序試候選目錄，第一個使該腳本畫面全文「完全不含任何
# 禁止片段」者即為其固定目錄。widget id 只取決於型別／key／腳本路徑，與秘密無關 → 乾淨探針的結論可套用到同腳本的所有情境。
# 掃描函式因此**完全不需遮蔽**：hash 槽位的秘密（含 32 位 hex 秘密）與修補前等效、一律命中。
#   · 選擇只看乾淨探針；真洩漏在任何目錄都存在 → 不會被「換目錄重試」洗掉（第 7 節有測試證明）。
#   · 候選全數碰撞 → 硬失敗並具名（代表頁面本身有靜態洩漏、或 Streamlit 的 id 行為變了），不放行。
#   · 真實執行時畫面中出現的任何 32 位以上 hex 串都必須是探針看過的（`_assert_hex_runs_probed`）→ 沒有「探針沒涵蓋的元件」。
# ══════════════════════════════════════════════════════════════════
_N_CANDIDATES = 64
_PROBE_CLICK_KEY = "api_diag_run"
_HEX_RUN_RE = re.compile(r"[0-9a-f]{32,}")


def _fixture_root() -> pathlib.Path:
    """系統暫存下、由測試自己建立的固定根目錄（含 uid，避免多使用者互踩；拒絕符號連結）。"""
    uid = os.getuid() if hasattr(os, "getuid") else 0
    root = pathlib.Path(tempfile.gettempdir()) / f"stock_d6_fixture_{uid}"
    root.mkdir(mode=0o700, exist_ok=True)
    _assert_own_real_dir(root)
    return root


def _assert_own_real_dir(path) -> None:
    """拒絕符號連結／非本人擁有的目錄（共用 /tmp 下，避免腳本被寫到別人預先佈置的位置）。"""
    st_ = os.lstat(path)
    assert stat.S_ISDIR(st_.st_mode), f"fixture 目錄不是真目錄（可能是符號連結）：{path}"
    if hasattr(os, "getuid"):
        assert st_.st_uid == os.getuid(), f"fixture 目錄不是本人擁有：{path}"


def _candidate_dirs():
    root = _fixture_root()
    for i in range(_N_CANDIDATES):
        yield str(root / f"k{i:04d}")


@contextlib.contextmanager
def _tmpdir_pinned(dirname: str):
    """把 AppTest 寫腳本的目錄暫時固定成 `dirname`（`from_string` 於呼叫當下才讀 `app_test.TMP_DIR.name`，
    1.56.0／1.59.2 皆然；腳本路徑建立後存在 AppTest 內，之後 `.run()` 不再讀它）。"""
    from streamlit.testing.v1 import app_test
    assert hasattr(app_test, "TMP_DIR"), "前提變了：app_test 不再有 TMP_DIR——widget id 確定性環境需要重新設計"
    os.makedirs(dirname, exist_ok=True)
    _assert_own_real_dir(dirname)
    orig = app_test.TMP_DIR
    app_test.TMP_DIR = types.SimpleNamespace(name=dirname)
    try:
        yield
    finally:
        app_test.TMP_DIR = orig


def _probe_screen(script: str, dirname: str) -> str:
    """乾淨探針：在 `dirname` 下把 `script` 以「無秘密、無環境變數、benign 回應」的情境跑一次，回傳畫面全文。
    刻意**沒有** secrets／env 參數：探針不可能帶入秘密。stdout／stderr／log 不含 widget id、與目錄無關，不在探針範圍。"""
    from streamlit.testing.v1 import AppTest
    with pytest.MonkeyPatch.context() as mp:
        _clean_env(mp)
        for n in ("GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
            mp.delenv(n, raising=False)
        if "render_api_diagnostic" in script:
            _stub_proxy(mp, None)
            _install_requests(mp, lambda host, proxied: _Resp(200, "ok"))
        with _tmpdir_pinned(dirname):
            at = AppTest.from_string(script, default_timeout=60)
        at.secrets["UNRELATED_FLAG"] = "1"          # 讓 AppTest 用自己的 secrets（不受外層測試對 st.secrets 的替換影響）
        at.run()
        for b in [b for b in at.button if b.key == _PROBE_CLICK_KEY]:
            b.click().run()
        assert not at.exception, ("D6 fixture：乾淨探針本身就崩潰", dirname, [str(e.value)[:200] for e in at.exception])
        return screen_text(at)


def _select_dir(script: str, candidates, probe, *, check=None) -> tuple[str, str]:
    """依序試候選目錄，回傳第一個「乾淨探針畫面全文完全不含任何禁止片段」的 (目錄, 探針畫面全文)。
    全部候選都不乾淨 → 硬失敗（具名）。`check` 只供突變測試替換（正式路徑一律 `leaks_in`）。"""
    check = check or leaks_in
    rejected: list[tuple[str, list[str]]] = []
    for d in candidates:
        text = probe(script, d)
        hits = check(text)
        if not hits:
            return d, text
        rejected.append((d, hits[:3]))
    raise AssertionError(
        f"D6 fixture：{len(rejected)} 個候選目錄的乾淨探針畫面全都含禁止片段——頁面本身有靜態洩漏，"
        f"或 Streamlit 的 widget id 行為變了（例如不再取決於腳本路徑）。不得放行。前幾個被拒的候選：{rejected[:3]}")


_PINNED: dict[str, tuple[str, frozenset[str]]] = {}      # sha256(script) → (固定目錄, 探針畫面中的 32+ 位 hex 串)


def _script_key(script: str) -> str:
    return hashlib.sha256(script.encode("utf-8")).hexdigest()


def _pin_script(script: str) -> str:
    key = _script_key(script)
    if key not in _PINNED:
        dirname, text = _select_dir(script, _candidate_dirs(), _probe_screen)
        _PINNED[key] = (dirname, frozenset(_HEX_RUN_RE.findall(text)))
    return _PINNED[key][0]


def _app_from_string(script: str, *, pin: bool = True, tmpdir: str | None = None):
    """`AppTest.from_string` 的確定性版本。pin=False 只給「腳本本身含洩漏、無法做乾淨探針」的測試
    （那些測試只斷言『有命中』，碰撞只會多一個命中、不會造成漏報）。"""
    from streamlit.testing.v1 import AppTest
    if tmpdir is not None:
        with _tmpdir_pinned(tmpdir):
            return AppTest.from_string(script, default_timeout=60)
    if not pin:
        return AppTest.from_string(script, default_timeout=60)
    with _tmpdir_pinned(_pin_script(script)):
        return AppTest.from_string(script, default_timeout=60)


def _assert_hex_runs_probed(script: str, at) -> None:
    """真實執行的畫面中，每個 32 位以上 hex 串（widget id 雜湊）都必須是乾淨探針看過且已確認乾淨的。"""
    probed = _PINNED[_script_key(script)][1]
    stray = set(_HEX_RUN_RE.findall(screen_text(at))) - probed
    assert not stray, f"D6 fixture：畫面出現乾淨探針沒涵蓋的 hex 串（未探針的元件？）：{sorted(stray)}"


_DRIVER = """
import os, sys
sys.path.insert(0, os.getcwd())
{pre}
from {mod} import render_api_diagnostic
render_api_diagnostic()
"""


def _driver_script(pre: str = "", mod: str = "src.ui.pages.api_diagnostic") -> str:
    return _DRIVER.format(pre=pre, mod=mod)


def _run_page(monkeypatch, capsys, caplog, *, secrets=None, env=None, click=False,
              mod="src.ui.pages.api_diagnostic", pre="", keep_stdio=False, pin=True, tmpdir=None):
    """跑一次診斷頁 → (AppTest, blob)。blob ＝ 畫面 + stdout + stderr + logging（全量、不遮蔽）。
    pin=True：腳本寫進確定性目錄（見上）；pin=False／tmpdir=...：只給突變測試與第 7 節的目錄對照實驗。"""
    caplog.set_level(logging.DEBUG)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    script = _driver_script(pre, mod)
    at = _app_from_string(script, pin=pin, tmpdir=tmpdir)
    if secrets is not None:
        for k, v in secrets.items():
            at.secrets[k] = v
    capsys.readouterr()  # 清掉前面的輸出（含乾淨探針的輸出）
    caplog.clear()
    at.run()
    if click:
        at.button(key="api_diag_run").click().run()
    assert not at.exception, [str(e.value)[:200] for e in at.exception]
    out = capsys.readouterr()
    blob = "\n".join([screen_text(at), out.out, out.err, caplog.text])
    if pin and tmpdir is None:
        _assert_hex_runs_probed(script, at)
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
    import streamlit as st
    _clean_env(monkeypatch)
    for n in ("GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        monkeypatch.delenv(n, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    if broken is not None:
        monkeypatch.setattr(st, "secrets", broken)
    script = _sidebar_driver()
    at = _app_from_string(script)
    for k, v in (secrets or {}).items():
        at.secrets[k] = v
    at.run()
    assert not at.exception, [str(e.value)[:200] for e in at.exception]
    _assert_hex_runs_probed(script, at)
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
                            mod=mod, pre=f"sys.path.insert(0, {str(tmp_path)!r})", pin=False)
        assert leaks_in(blob), f"突變 {key} 沒被偵測到——本檔的守衛失效"   # 只斷言「有命中」→ 不需確定性目錄
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


# ══════════════════════════════════════════════════════════════════
# 7. R23.22：widget id 隨機 md5 與假金鑰純 hex 片段碰撞（偶發紅燈）——以「確定性環境」根治，掃描完全不遮蔽
#    設計見上方 `_select_dir` 前的註解。本節證明：
#      (a) 碰撞真實存在：已知會撞的 TMP 目錄下，完整掃描確實報紅；選擇器拒絕碰撞候選並換下一個，選出的目錄為綠；
#          （該已知目錄在當前 Streamlit／暫存目錄不再碰撞時，改以構造的 proto 驗證同一套選擇器邏輯，仍有必紅負控）
#      (b) 只出現在 `$$ID-<32hex>-` 雜湊槽位的秘密（含恰為 32 位小寫 hex 的秘密）一律命中；
#      (c) 「疑似 ID 格式的使用者可見文字」仍命中；(d) id 後綴夾帶秘密／整串 id 為秘密／不符形狀的 id 仍命中；
#      (e) 真洩漏（各種元素、stdout／stderr／log）仍命中，且在任何候選目錄下都存在（不會被「換目錄」洗掉）；
#      (f) 突變：選擇器不探針／接受含禁止片段的候選／重新引入對 id 欄位或雜湊槽位的任何遮蔽 → 守門轉紅。
# ══════════════════════════════════════════════════════════════════
import itertools
from types import SimpleNamespace

#: 32 位小寫 hex、含 `789a`（LONG 的純十六進位片段之一）——模擬「隨機 md5 剛好碰撞」
_COLL = "5e7789a3c41b0d9f2a6e8b17c3d405f9"
#: 32 位小寫 hex、不含 LONG 的任何純十六進位片段（對照組：這種 ID 本來就不會誤判）
_SAFE_HASH = "e1f2a3b4c5d6e7f8e1f2a3b4c5d6e7f8"
_HEX_FRAGS_OF_LONG = sorted(f for f in _frags(LONG) if re.fullmatch(r"[0-9a-f]{4}", f))
#: 「恰為 32 位小寫 hex」的合成秘密（R23.22 盲點：只出現在 hash 槽位時舊掃描命中、遮蔽式掃描漏報）
HEX32_SECRET = "c0ffee5ec2e7a9b1d4f60837ab12cd34"
#: 盲點的原始重現（QA 實測）：整段都是 LONG 的純 hex 片段
_O_EXAMPLE_HASH = "0123456789abcdef0123456789abcdef"
_HEX32_STRS = {HEX32_SECRET} | _frags(HEX32_SECRET)

#: 對「預設 driver」腳本已知會讓 Button id 含 LONG 純 hex 片段的 TMP 目錄名（系統暫存目錄下）。
#: ⚠️ 只對特定 Streamlit id 演算法＋腳本文字＋暫存目錄為 `/tmp` 成立；不成立時回歸測試自動改走構造版（見 (a)），不是 skip。
_KNOWN_COLLIDING_DIRNAMES = ("tmp00003099", "tmp00000270", "tmp00000013")


def _hits(text: str) -> list[str]:
    """`leaks_in` ＋ 專屬的 32hex 秘密集合（不改 `leaks_in`／`_SECRET_SETS` 既有語意）。"""
    return leaks_in(text) + [f"HEX32:{s!r}" for s in sorted(_HEX32_STRS) if s in text]


def _widget_id(hash_: str, key: str = "api_diag_run") -> str:
    return f"$$ID-{hash_}-{key}"


def _button(id_: str, label: str = "btn", help_: str = ""):
    from streamlit.proto.Button_pb2 import Button
    return Button(id=id_, label=label, help=help_)


def _markdown(body: str):
    from streamlit.proto.Markdown_pb2 import Markdown
    return Markdown(body=body)


def _fake_at(*protos):
    """走『真的 screen_text』的最小畫面替身：main 底下一排只帶 proto 的元素。"""
    node = SimpleNamespace(children={i: SimpleNamespace(proto=p, value=None) for i, p in enumerate(protos)})
    return SimpleNamespace(main=node, sidebar=SimpleNamespace(children={}), exception=[])


def _run_snippet(code: str, *, pin: bool = True):
    """跑一小段真的 Streamlit 腳本 → AppTest。pin=False 只給「腳本本身含秘密、無法乾淨探針」且只斷言『有命中』的測試。"""
    at = _app_from_string(code, pin=pin).run()
    assert not at.exception, [str(e.value)[:200] for e in at.exception]
    if pin:
        _assert_hex_runs_probed(code, at)
    return at


def test_fixture_constants_are_what_the_regressions_assume():
    assert len(_COLL) == 32 and re.fullmatch(r"[0-9a-f]{32}", _COLL) and "789a" in _COLL
    assert len(_SAFE_HASH) == 32 and re.fullmatch(r"[0-9a-f]{32}", _SAFE_HASH)
    assert not any(f in _SAFE_HASH for f in _HEX_FRAGS_OF_LONG)
    assert leaks_in(_SAFE_HASH) == [] and _hits(_SAFE_HASH) == []
    assert len(_HEX_FRAGS_OF_LONG) == 13, _HEX_FRAGS_OF_LONG           # 0123…cdef（含 789a）
    assert "789a" in _HEX_FRAGS_OF_LONG
    assert len(HEX32_SECRET) == 32 and re.fullmatch(r"[0-9a-f]{32}", HEX32_SECRET)
    assert len(_O_EXAMPLE_HASH) == 32 and re.fullmatch(r"[0-9a-f]{32}", _O_EXAMPLE_HASH)
    # 32hex 秘密不是 `leaks_in` 既有集合的成員（證明 (b) 需要專屬集合、而非碰巧被 LONG 片段蓋到）
    assert leaks_in(HEX32_SECRET) == [], leaks_in(HEX32_SECRET)
    assert _hits(HEX32_SECRET)


# ── 確定性環境本身的前提與行為 ───────────────────────────────────────
def test_premise_script_dir_determines_widget_id_and_pinned_dir_makes_it_deterministic():
    """前提：widget id 取決於腳本路徑（TMP_DIR 目錄）；固定目錄 → 同 id；換目錄 → 不同 id。
    若 Streamlit 日後讓 id 與路徑無關，這條會先說（那時選擇器會對碰撞硬失敗，不會放行）。"""
    script = "import streamlit as st\nst.button('x', key='d6_premise')\n"
    root = _fixture_root()
    ids: dict[str, list[str]] = {}
    for tag in ("premise_a", "premise_b", "premise_a"):
        at = _app_from_string(script, tmpdir=str(root / tag)).run()
        assert at._script_path.startswith(str(root / tag)), at._script_path
        ids.setdefault(tag, []).append(at.button[0].proto.id)
    assert ids["premise_a"][0] == ids["premise_a"][1], "同目錄同腳本 id 必須相同（確定性）"
    assert ids["premise_a"][0] != ids["premise_b"][0], "前提變了：widget id 不再取決於腳本路徑"


def test_pinned_page_runs_have_identical_widget_ids_every_time(monkeypatch, capsys, caplog):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    first, _ = _run_page(monkeypatch, capsys, caplog, secrets={"UNRELATED_FLAG": "1"})
    second, _ = _run_page(monkeypatch, capsys, caplog, secrets={"UNRELATED_FLAG": "1"})
    id1, id2 = first.button(key="api_diag_run").proto.id, second.button(key="api_diag_run").proto.id
    assert re.fullmatch(r"\$\$ID-[0-9a-f]{32}-api_diag_run", id1) and id1 == id2
    assert leaks_in(id1) == [], "選出的固定目錄下，id 本身不含任何禁止片段"


def test_stray_unprobed_hex_run_in_real_screen_is_a_hard_failure():
    """探針沒看過的 32+ 位 hex 串（＝沒被確認乾淨的元件 id）出現在真實畫面 → 硬失敗，不默默放行。"""
    script = _driver_script()
    _pin_script(script)
    with pytest.raises(AssertionError, match="未探針"):
        _assert_hex_runs_probed(script, _fake_at(_button(_widget_id(_SAFE_HASH, "never_probed"))))


def test_probe_has_no_way_to_carry_secrets_or_environment():
    """探針只收 (script, dirname)：不可能帶入秘密／環境；只塞中性旗標 UNRELATED_FLAG。
    （若探針改用帶秘密的情境，真洩漏會在每個目錄都命中 → 只會讓選擇器硬失敗，不會放行；見下方 never_launders 測試。）"""
    assert list(inspect.signature(_probe_screen).parameters) == ["script", "dirname"]
    src = inspect.getsource(_probe_screen)
    assert re.findall(r"secrets\[(.*?)\]", src) == ['"UNRELATED_FLAG"']
    assert ".setenv(" not in src and "_ALL_SET" not in src and "LONG" not in src


# ── (a) 碰撞回歸：選擇器拒絕碰撞候選並換下一個；全掃描在碰撞目錄下確實報紅 ─────────────────
def _mutant_select_always_first(script, candidates, probe, *, check=None):
    """突變：不探針、恆回第一個候選。"""
    return next(iter(candidates)), ""


def _mutant_select_accepts_forbidden(script, candidates, probe):
    """突變：探針了，但驗收條件放寬到會放過含禁止片段（LONG 片段）的候選。"""
    return _select_dir(script, candidates, probe, check=lambda t: leaks_in(t, groups=("SHORT",)))


def _assert_selector_world(*, cands, colliding, probe, scan):
    """選擇器行為的完整斷言。cands() 每次回傳新的候選迭代器（前面是 `colliding`）；
    probe(script, d) 為乾淨探針；scan(d) 為「在目錄 d 下做完整掃描」的文字。"""
    script = _driver_script()
    chosen, _ = _select_dir(script, cands(), probe)
    assert chosen not in colliding, ("選擇器選了碰撞候選", chosen)
    assert leaks_in(scan(chosen)) == [], "選出的目錄下完整掃描必須是綠的"
    for d in colliding:
        assert leaks_in(scan(d)), ("前提：碰撞目錄下完整掃描必須是紅的（碰撞是真的）", d)
    for name, mutant in (("always_first", _mutant_select_always_first),
                         ("accepts_forbidden", _mutant_select_accepts_forbidden)):
        picked, _ = mutant(script, cands(), probe)
        assert picked in colliding and leaks_in(scan(picked)), f"突變 {name} 沒有讓碰撞回歸轉紅——守門失效"
    with pytest.raises(AssertionError, match="D6 fixture"):               # 全數碰撞 → 硬失敗、具名，不放行
        _select_dir(script, iter(colliding), probe)


def _constructed_world():
    """不依賴 Streamlit id 演算法的構造世界：前兩個候選的 id 雜湊含 LONG 的純 hex 片段，第三個乾淨。"""
    hashes = {"c0": _COLL, "c1": ("0123" + _SAFE_HASH)[:32], "c2": _SAFE_HASH}

    def probe(script, d):
        return screen_text(_fake_at(_button(_widget_id(hashes[d]))))

    return dict(cands=lambda: iter(["c0", "c1", "c2", "c3"]), colliding=["c0", "c1"], probe=probe,
                scan=lambda d: probe(None, d))


def test_a_constructed_collision_selector_rejects_collisions_and_mutants_turn_red():
    """永遠執行（不依賴任何 Streamlit 版本／暫存目錄）：構造的碰撞世界。"""
    _assert_selector_world(**_constructed_world())


def test_a_real_known_colliding_tmpdir_full_scan_is_red_and_selector_picks_another(monkeypatch, capsys, caplog):
    """真實 AppTest：已知碰撞目錄下完整掃描報紅；選擇器拒絕它、選出的目錄綠。
    該已知目錄在當前環境不再碰撞 → 降級為構造版（仍有必紅負控；不是 skip，也不放行整體檢測）。"""
    script = _driver_script()
    base = pathlib.Path(tempfile.gettempdir())
    live = [str(base / n) for n in _KNOWN_COLLIDING_DIRNAMES if leaks_in(_probe_screen(script, str(base / n)))]
    if not live:
        _assert_selector_world(**_constructed_world())
        return

    def scan(d):
        _clean_env(monkeypatch)
        _stub_proxy(monkeypatch, None)
        _, blob = _run_page(monkeypatch, capsys, caplog, secrets={"UNRELATED_FLAG": "1"}, tmpdir=d)
        return blob

    _assert_selector_world(cands=lambda: itertools.chain(live, _candidate_dirs()), colliding=live,
                           probe=_probe_screen, scan=scan)
    # 碰撞命中的確實是 LONG 的純 hex 片段（不是別的原因）
    hit_words = " ".join(leaks_in(scan(live[0])))
    assert any(f"LONG:{f!r}" in hit_words for f in _HEX_FRAGS_OF_LONG), hit_words


@pytest.mark.parametrize("frag", _HEX_FRAGS_OF_LONG)
def test_a_colliding_hash_in_id_slot_is_reported_by_the_full_scan_not_hidden(frag):
    hash_ = (frag + _SAFE_HASH)[:32]
    txt = screen_text(_fake_at(_button(_widget_id(hash_))))
    assert f"LONG:{frag!r}" in leaks_in(txt), "完整掃描必須把碰撞報出來（碰撞由確定性環境避開，不是由掃描吞掉）"
    assert hash_ in txt, "雜湊槽位原樣保留、未被遮蔽"


def test_a_forced_colliding_and_secret_ids_in_the_real_element_tree_are_reported(monkeypatch, capsys, caplog):
    """真頁面、真元素樹；把真 Button 的 id 就地換成含 `789a`／32hex 秘密的 ID → 全掃描必須命中。"""
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    at, _ = _run_page(monkeypatch, capsys, caplog, secrets={"UNRELATED_FLAG": "1"})
    real_id = at.button(key="api_diag_run").proto.id
    assert re.fullmatch(r"\$\$ID-[0-9a-f]{32}-api_diag_run", real_id), real_id
    assert _hits(screen_text(at)) == [], "前提：選出的固定目錄下畫面本來是乾淨的"

    def _clone_tree(root, new_id):               # 真元素的 proto 複本（Button.value 以 id 回查 session，故不就地改）
        kids = {}
        for i, el in enumerate(_walk(root)):
            proto = getattr(el, "proto", None)
            if proto is not None and hasattr(proto, "CopyFrom"):
                c = type(proto)()
                c.CopyFrom(proto)
                if getattr(c, "id", None) == real_id:
                    c.id = new_id
                proto = c
            kids[i] = SimpleNamespace(proto=proto, value=getattr(el, "value", None))
        return SimpleNamespace(children=kids)

    for new_id, expected in ((_widget_id(_COLL), "LONG:'789a'"),
                             (_widget_id(HEX32_SECRET), f"HEX32:{HEX32_SECRET!r}")):
        forced = SimpleNamespace(main=_clone_tree(at.main, new_id), sidebar=_clone_tree(at.sidebar, new_id),
                                 exception=[])
        assert new_id in screen_text(forced), "強制替換沒有進到畫面文字"
        assert expected in _hits(screen_text(forced)), (new_id, _hits(screen_text(forced)))


# ── (e)＋不被洗掉：真洩漏在任何候選目錄下都存在；選擇器遇到靜態洩漏只會硬失敗 ─────────────────
@pytest.mark.parametrize("key", ["mask_preview", "body_snippet"])
def test_real_leak_is_reported_under_every_candidate_dir(monkeypatch, capsys, caplog, tmp_path, key):
    mod = _load_mutant(tmp_path, key)
    try:
        dirs = [str(pathlib.Path(tempfile.gettempdir()) / _KNOWN_COLLIDING_DIRNAMES[0])]
        dirs += list(itertools.islice(_candidate_dirs(), 3))
        for d in dirs:
            _clean_env(monkeypatch)
            _stub_proxy(monkeypatch, {"http": PROXY_URL, "https": PROXY_URL})
            _install_requests(monkeypatch, _plan)
            _, blob = _run_page(monkeypatch, capsys, caplog, secrets=dict(_ALL_SET), click=True, mod=mod,
                                pre=f"sys.path.insert(0, {str(tmp_path)!r})", pin=False, tmpdir=d)
            assert leaks_in(blob), f"真洩漏（突變 {key}）在目錄 {d} 下沒被偵測到"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(_MUTANT_MODNAME, None)


def test_selector_never_launders_a_static_leak_it_hard_fails(tmp_path):
    """頁面本身有靜態洩漏（突變：遮罩預覽，連無秘密也會印『(空)』）→ 乾淨探針在每個候選都命中 → 硬失敗，不放行。"""
    mod = _load_mutant(tmp_path, "mask_preview")
    try:
        script = _driver_script(f"sys.path.insert(0, {str(tmp_path)!r})", mod)
        with pytest.raises(AssertionError, match="D6 fixture.*都含禁止片段"):
            _select_dir(script, itertools.islice(_candidate_dirs(), 3), _probe_screen)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(_MUTANT_MODNAME, None)


# ── (b) 只出現在 hash 槽位的秘密必命中（含恰為 32 位小寫 hex 的秘密） ─────────────────────
def test_b_o_example_hash_slot_made_of_long_hex_fragments_is_caught():
    txt = screen_text(_fake_at(_button(_widget_id(_O_EXAMPLE_HASH, "k"))))
    assert _O_EXAMPLE_HASH in txt
    hits = leaks_in(txt)
    assert "LONG:'0123'" in hits and "LONG:'cdef'" in hits, hits


def test_b_32hex_secret_that_appears_only_in_the_hash_slot_is_caught():
    txt = screen_text(_fake_at(_button(_widget_id(HEX32_SECRET, "k"))))
    assert HEX32_SECRET in txt, "掃描不得吃掉雜湊槽位"
    assert f"HEX32:{HEX32_SECRET!r}" in _hits(txt)
    assert leaks_in(txt) == [], "（對照：它不在 LONG 等既有集合內——命中只能來自 32hex 專屬集合的全量比對）"


def _b_all_detected(proto_text) -> bool:
    ok = True
    for h, expected in ((_O_EXAMPLE_HASH, "LONG:'0123'"), (HEX32_SECRET, f"HEX32:{HEX32_SECRET!r}")):
        text = _screen_text_with(_fake_at(_button(_widget_id(h, "k"))), proto_text)
        ok = ok and expected in _hits(text)
    return ok


def test_b_the_real_scan_detects_all_hash_slot_secrets():
    assert _b_all_detected(str)


# ── (c)(e) 真洩漏／疑似 ID 格式的使用者可見文字：每種元素都要攔截 ─────────────────
_ELEMENT_KINDS = {
    "markdown": "st.markdown(P)",
    "caption": "st.caption(P)",
    "text": "st.text(P)",
    "code": "st.code(P)",
    "table": "st.table(pd.DataFrame({'c': [P]}))",
    "dataframe": "st.dataframe(pd.DataFrame({'c': [P]}))",
    "error": "st.error(P)",
    "warning": "st.warning(P)",
    "success": "st.success(P)",
    "metric_label": "st.metric(P, '1')",
    "button_label": "st.button(P, key='d6_lbl')",
    "button_help": "st.button('b', key='d6_hlp', help=P)",
    "sidebar_markdown": "st.sidebar.markdown(P)",
}
_PAYLOADS = {
    "long_secret": (LONG, f"LONG:{LONG!r}"),
    "hex_fragment": ("789a", "LONG:'789a'"),
    "hex32_secret": (HEX32_SECRET, f"HEX32:{HEX32_SECRET!r}"),
    "id_lookalike_user_text": (_widget_id(_COLL, "x"), "LONG:'789a'"),
    "id_lookalike_prefix_text": (f"請看 {_widget_id(_COLL, 'x')} 這串", "LONG:'789a'"),
    "id_lookalike_hex32_secret": (_widget_id(HEX32_SECRET, "x"), f"HEX32:{HEX32_SECRET!r}"),
}


def _kind_script(kind: str, payload: str) -> str:
    return f"import streamlit as st\nimport pandas as pd\nP = {payload!r}\n{_ELEMENT_KINDS[kind]}\n"


@pytest.mark.parametrize("payload_name", list(_PAYLOADS))
@pytest.mark.parametrize("kind", list(_ELEMENT_KINDS))
def test_bc_secret_or_id_lookalike_text_in_any_element_is_still_caught(kind, payload_name):
    payload, expected_hit = _PAYLOADS[payload_name]
    # 腳本本身含秘密 → 無法乾淨探針（pin=False）；只斷言「有命中」，碰撞只會多一個命中、不會造成漏報
    txt = screen_text(_run_snippet(_kind_script(kind, payload), pin=False))
    assert expected_hit in _hits(txt), (kind, payload_name)


@pytest.mark.parametrize("kind", list(_ELEMENT_KINDS))
def test_bc_control_benign_text_in_the_same_elements_is_clean(kind):
    """對照組：同樣的元素、不含秘密／ID 形狀的內容 → 乾淨（上一條的紅不是偵測器過敏）；
    此處是**完整未遮蔽掃描**，元件自己的 id 能綠，靠的是確定性目錄（而不是遮蔽）。"""
    txt = screen_text(_run_snippet(_kind_script(kind, "benign text")))
    assert _hits(txt) == [], _hits(txt)
    assert re.search(r"\$\$ID-[0-9a-f]{32}-", txt) or kind not in ("button_label", "button_help"), "id 槽位必須原樣在文字內"


# ── (d) id 欄位本身被夾帶秘密／不符 widget id 形狀／lookalike 出現在其他欄位 ────────────
_ID_CASES = {
    # name: (proto, 必須出現的 hit)
    "hash_slot_o_example": (_button(_widget_id(_O_EXAMPLE_HASH, "k")), "LONG:'0123'"),
    "hash_slot_hex32_secret": (_button(_widget_id(HEX32_SECRET, "k")), f"HEX32:{HEX32_SECRET!r}"),
    "hash_slot_colliding_789a": (_button(_widget_id(_COLL, "k")), "LONG:'789a'"),
    "id_suffix_has_long_secret": (_button(_widget_id(_COLL, LONG)), f"LONG:{LONG!r}"),
    "id_suffix_has_long_secret_safe_hash": (_button(_widget_id(_SAFE_HASH, LONG)), f"LONG:{LONG!r}"),
    "id_suffix_has_fragment": (_button(_widget_id(_SAFE_HASH, "k_ZQ-d")), "LONG:'ZQ-d'"),
    "id_suffix_has_hex_fragment": (_button(_widget_id(_SAFE_HASH, "k_789a")), "LONG:'789a'"),
    "id_is_whole_secret": (_button(LONG), f"LONG:{LONG!r}"),
    "id_is_secret_fragment": (_button("cdef"), "LONG:'cdef'"),
    "id_hash_31_hex": (_button(f"$$ID-{_COLL[:31]}-k"), "LONG:'789a'"),
    "id_hash_33_hex": (_button(f"$$ID-{_COLL}f-k"), "LONG:'789a'"),
    "id_no_trailing_dash": (_button(f"$$ID-{_COLL}"), "LONG:'789a'"),
    "id_leading_space": (_button(" " + _widget_id(_COLL, "k")), "LONG:'789a'"),
    "id_prefix_text_before": (_button("x" + _widget_id(_COLL, "k")), "LONG:'789a'"),
    "id_lowercase_prefix": (_button(f"$$id-{_COLL}-k"), "LONG:'789a'"),
    # 非 `id` 欄位裡的 widget id 形狀文字
    "lookalike_in_button_label": (_button(_widget_id(_SAFE_HASH), label=_widget_id(_COLL, "x")), "LONG:'789a'"),
    "lookalike_in_button_help": (_button(_widget_id(_SAFE_HASH), help_=_widget_id(_COLL, "x")), "LONG:'789a'"),
    "lookalike_in_markdown_body": (_markdown(_widget_id(_COLL, "x")), "LONG:'789a'"),
    "hex32_secret_in_markdown_body": (_markdown(HEX32_SECRET), f"HEX32:{HEX32_SECRET!r}"),
}


def _assert_case_detected(name: str, proto_text) -> None:
    proto, expected = _ID_CASES[name]
    hits = _hits(_screen_text_with(_fake_at(proto), proto_text))
    assert expected in hits, (name, hits)


@pytest.mark.parametrize("name", list(_ID_CASES))
def test_cd_id_field_smuggling_hash_slots_and_non_widget_id_shapes_are_still_caught(name):
    _assert_case_detected(name, str)


def test_cd_clean_widget_ids_are_clean_under_the_unmasked_scan():
    for key in ("api_diag_run", "None", "k-with-dashes_1", ""):
        txt = screen_text(_fake_at(_button(_widget_id(_SAFE_HASH, key))))
        assert _hits(txt) == [], (key, _hits(txt))


# ── (e) stdout／stderr／log：全量掃描 ─────────────────────────────────────────
_CHANNEL_PRE = {
    "stdout": "print({msg!r})",
    "stderr": "print({msg!r}, file=sys.stderr)",
    "log": "import logging\nlogging.getLogger('d6chan').warning({msg!r})",
}


@pytest.mark.parametrize("msg,expected", [
    ("d6-chan 789a", "LONG:'789a'"),
    (_widget_id(_COLL, "x"), "LONG:'789a'"),                 # ID 形狀的輸出也照樣命中
    (_widget_id(HEX32_SECRET, "x"), f"HEX32:{HEX32_SECRET!r}"),
    (f"d6-chan {LONG}", f"LONG:{LONG!r}"),
])
@pytest.mark.parametrize("channel", list(_CHANNEL_PRE))
def test_e_hex_fragments_in_stdout_stderr_log_are_still_caught(monkeypatch, capsys, caplog, channel, msg, expected):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    pre = _CHANNEL_PRE[channel].replace("{msg!r}", repr(msg))     # 不用 str.format：_DRIVER 本身用 format，pre 內不得有大括號
    at, blob = _run_page(monkeypatch, capsys, caplog, secrets={"UNRELATED_FLAG": "1"}, pre=pre)
    assert _hits(screen_text(at)) == [], "畫面本身是乾淨的——紅色只能來自該輸出管道"
    assert expected in _hits(blob), (channel, msg)


def test_e_control_without_injection_the_same_run_is_clean(monkeypatch, capsys, caplog):
    _clean_env(monkeypatch)
    _stub_proxy(monkeypatch, None)
    _, blob = _run_page(monkeypatch, capsys, caplog, secrets={"UNRELATED_FLAG": "1"}, pre="print('d6-chan ok')")
    assert leaks_in(blob) == []


# ── (f) 遮蔽型突變：任何「對 id 欄位／hash 槽位／整段文字」的遮蔽都必須被 (b)(d) 的守門抓到 ────────
def _is_repeated(fd) -> bool:
    return bool(fd.is_repeated) if hasattr(type(fd), "is_repeated") else fd.label == fd.LABEL_REPEATED


def _mutant_rewrite_id_fields(proto, value_fn):
    """⛔ 僅供突變測試：這就是 R23.21 曾經的「欄位層正規化」（改寫名為 id 的 string 欄位）。正式掃描不得使用。"""
    clone = type(proto)()
    clone.CopyFrom(proto)

    def _walk_msg(msg):
        for fd, val in msg.ListFields():
            if fd.type == fd.TYPE_MESSAGE:
                if fd.message_type.GetOptions().map_entry:
                    continue
                for child in (list(val) if _is_repeated(fd) else [val]):
                    _walk_msg(child)
            elif fd.name == "id" and fd.type == fd.TYPE_STRING and not _is_repeated(fd):
                setattr(msg, "id", value_fn(val))

    _walk_msg(clone)
    return str(clone)


_HASH_SLOT_RE = re.compile(r"(?<=\$\$ID-)[0-9a-f]{32}(?=-)")


def _mut_reintroduce_field_level_hash_normalization(p):          # R23.21 的正規化（盲點本身）
    return _mutant_rewrite_id_fields(p, lambda v: _HASH_SLOT_RE.sub("<WIDGET-ID-HASH>", v) if v.startswith("$$ID-") else v)


def _mut_global_regex_mask_hash_slot(p):                        # 對整段文字遮蔽 hash 槽位
    return re.sub(r"\$\$ID-[0-9a-f]{32}-", "$$ID-<H>-", str(p))


def _mut_mask_whole_id_field(p):
    return _mutant_rewrite_id_fields(p, lambda v: "<MASKED>")


def _mut_mask_any_32hex_in_id_field(p):                         # 不檢查 widget id 形狀
    return _mutant_rewrite_id_fields(p, lambda v: re.sub(r"[0-9a-f]{32}", "<H>", v))


def _mut_drop_all_hex_fragments_globally(p):                    # 對整段文字吃掉所有 4 位 hex 片段
    return re.sub(r"[0-9a-f]{4}", "", str(p))


_HASH_SLOT_CASES = {"hash_slot_o_example", "hash_slot_hex32_secret", "hash_slot_colliding_789a"}

#: 突變 → 它**必須**讓哪些 case 轉為「沒偵測到」（＝守門轉紅）
_MUTANT_MUST_TURN_RED = {
    _mut_reintroduce_field_level_hash_normalization: set(_HASH_SLOT_CASES),
    _mut_global_regex_mask_hash_slot: set(_HASH_SLOT_CASES) | {
        "lookalike_in_button_label", "lookalike_in_button_help", "lookalike_in_markdown_body"},
    _mut_mask_whole_id_field: set(_HASH_SLOT_CASES) | {
        "id_suffix_has_long_secret", "id_suffix_has_long_secret_safe_hash", "id_suffix_has_fragment",
        "id_suffix_has_hex_fragment", "id_is_whole_secret", "id_is_secret_fragment", "id_hash_31_hex",
        "id_hash_33_hex", "id_no_trailing_dash", "id_leading_space", "id_prefix_text_before",
        "id_lowercase_prefix"},
    _mut_mask_any_32hex_in_id_field: set(_HASH_SLOT_CASES) | {
        "id_hash_33_hex", "id_no_trailing_dash", "id_leading_space", "id_prefix_text_before",
        "id_lowercase_prefix"},
    _mut_drop_all_hex_fragments_globally: set(_HASH_SLOT_CASES) | {
        "id_suffix_has_hex_fragment", "id_hash_31_hex", "id_hash_33_hex", "id_no_trailing_dash",
        "id_leading_space", "id_prefix_text_before", "id_lowercase_prefix", "lookalike_in_button_label",
        "lookalike_in_button_help", "lookalike_in_markdown_body", "id_is_secret_fragment"},
}


@pytest.mark.parametrize("mutant", list(_MUTANT_MUST_TURN_RED), ids=lambda f: f.__name__)
def test_f_masking_mutants_turn_the_bd_guards_red(mutant):
    red = set()
    for name in _ID_CASES:
        try:
            _assert_case_detected(name, mutant)
        except AssertionError:
            red.add(name)
    assert _MUTANT_MUST_TURN_RED[mutant] <= red, sorted(_MUTANT_MUST_TURN_RED[mutant] - red)
    assert not _b_all_detected(mutant), "(b) 的守門沒有對這個遮蔽型突變轉紅"


def test_f_the_real_scan_turns_none_of_the_guards_red():
    for name in _ID_CASES:
        _assert_case_detected(name, str)
    assert _b_all_detected(str)


def test_f_reintroduced_hash_normalization_hides_the_blind_spot_exactly_as_qa_reproduced():
    """QA 實測的盲點（R23.22）：`$$ID-0123456789abcdef0123456789abcdef-k`——舊（完整）掃描命中，遮蔽式掃描漏報。"""
    at = _fake_at(_button(_widget_id(_O_EXAMPLE_HASH, "k")))
    assert leaks_in(_screen_text_with(at, str)), "完整掃描必須命中"
    assert leaks_in(_screen_text_with(at, _mut_reintroduce_field_level_hash_normalization)) == [], \
        "前提變了：遮蔽式掃描不再漏報——突變失去鑑別力"
