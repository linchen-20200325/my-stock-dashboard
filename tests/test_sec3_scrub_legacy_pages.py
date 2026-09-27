"""SEC-3（2026-09-26）：v2 五頁以外把例外原文送上畫面的出口，一律先過 L0 `scrub_secrets`。

實證（#709）：secrets.toml 壞掉時例外會帶出 secrets 原文／檔案路徑。v2 五頁已於 #709/#710 清洗；
本檔守的是**舊頁**（`app.py`、`src/ui/etf/**`、`src/ui/pages/**`、`src/ui/tabs/**`、`src/ui/render/app_render.py`）。

測法（每個出口一條，全部是**行為**測試，不是字串比對原始碼）：
- 能直接呼叫的 render 函式 → 換掉模組的 `st`，真的呼叫，收集畫面上所有字串；
- 埋在巨型 render 函式／`app.py` 腳本裡的出口 → 用 AST 從**現行原始檔**取出那個 `st.*(...)` 呼叫
  （或那一個 except 區塊），綁上一個帶秘密的例外後真的執行。取的是檔案裡的**那一段程式碼本身**，
  拔掉清洗（突變）→ 這裡轉紅。
每條同時斷言：一般訊息（不含秘密）逐字出現在畫面上（清洗不改一般訊息）。
"""
from __future__ import annotations

import ast
import builtins
import pathlib
import textwrap

import pandas as pd
import pytest

from shared.secret_md import scrub_md, scrub_md_mask
from shared.secret_scrub import scrub_secrets

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ══════════════════════════════════════════════════════════════════
# 秘密樣本：每一段都是 `scrub_secrets` 會遮的形狀；斷言用的是各段**獨特的值**。
# ══════════════════════════════════════════════════════════════════
_SECRET_VAL = "S3CR3T_sec3_Zq9"
_TOKEN = "ya29.a0AfH6SMBsec3tokenXYZ"
_SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789sec3"
_USER = "alicesec3"
_API_KEY = "AIzaSyA1234567890sec3abcdefg"
_SECRET_MSG = (
    f'client_secret = "{_SECRET_VAL}" at /home/{_USER}/app/.streamlit/secrets.toml '
    f"token {_TOKEN} https://docs.google.com/spreadsheets/d/{_SHEET_ID}/edit "
    f"url=https://x.test/v1?key={_API_KEY}"
)
_LEAKS = (_SECRET_VAL, _TOKEN, _SHEET_ID, _USER, _API_KEY)
#: 一般訊息：不含任何可遮的東西 → 清洗後必須逐字不變。
_PLAIN_MSG = "連線逾時 timeout after 8s (HTTP 502)"


def _assert_no_leak(text: str) -> None:
    for _s in _LEAKS:
        assert _s not in text, f"秘密 {_s!r} 上了畫面：{text[:400]!r}"


# ══════════════════════════════════════════════════════════════════
# 假 streamlit：收集所有傳給 st.* 的字串
# ══════════════════════════════════════════════════════════════════
class _Ctx:
    def __init__(self, st):
        self._st = st

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):
        return getattr(self._st, name)


class FakeSt:
    def __init__(self, *, button=False, secrets=None):
        self.out: list[str] = []
        self.session_state: dict = {}
        self._button = button
        self.secrets = secrets if secrets is not None else {}

    def _rec(self, *a, **k):
        self.out.extend(str(x) for x in list(a) + list(k.values()))
        return _Ctx(self)

    def columns(self, spec, *a, **k):
        _n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx(self) for _ in range(_n)]

    def button(self, *a, **k):
        self._rec(*a)
        return self._button

    def rerun(self):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self._rec

    @property
    def text(self) -> str:
        return "\n".join(self.out)


# ══════════════════════════════════════════════════════════════════
# 從現行原始檔取出出口程式碼
# ══════════════════════════════════════════════════════════════════
class _NS(dict):
    """未提供的區域名 → 一個無害的佔位字串（內建名照常走 builtins）。

    ⚠️ `scrub*` 開頭的名字**不給佔位**：清洗函式一律從該檔**真正的 import** 取（見 `_mod_ns`），
    檔案漏 import → 這裡 NameError → 測試紅（M17：刪掉 `app.py` 的 import 曾經測不出來）。
    """

    def __missing__(self, key):
        if hasattr(builtins, key) or key.startswith("scrub"):
            raise KeyError(key)
        return f"<{key}>"


def _mod_ns(rel: str, **bind) -> "_NS":
    """命名空間：只放該檔**模組層真的有寫**的 `from shared.secret_* import …`（照原檔執行）＋ `bind`。"""
    _ns = _NS()
    _imps = [n for n in _tree(rel).body if isinstance(n, ast.ImportFrom)
             and (n.module or "").startswith("shared.secret_")]
    exec(compile(ast.Module(_imps, []), rel, "exec"), _ns)  # noqa: S102
    _ns.update(bind)
    return _ns


def _tree(rel: str) -> ast.AST:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _find_call(rel: str, anchor: str) -> ast.Call:
    """找出**恰好一個** `st.<x>(...)` 呼叫，其原始碼含 `anchor`。"""
    _hits = [n for n in ast.walk(_tree(rel))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "st"
             and anchor in ast.unparse(n)]
    assert len(_hits) == 1, f"{rel}：含 {anchor!r} 的 st 呼叫應恰一個，實得 {len(_hits)}"
    return _hits[0]


def _run_call(rel: str, anchor: str, **bind) -> FakeSt:
    """在假 st 下執行那一個出口呼叫；`bind` 綁定它用到的區域變數（例外物件等）。"""
    _st = FakeSt()
    _ns = _mod_ns(rel, st=_st, **bind)
    eval(compile(ast.Expression(_find_call(rel, anchor)), rel, "eval"), _ns)  # noqa: S307
    return _st


def _run_handler(rel: str, anchor: str, exc: BaseException, **bind):
    """執行含 `anchor` 的那一個 `except ... as <name>:` 區塊（包成函式，`return` 值帶回）。"""
    _hits = [h for h in ast.walk(_tree(rel))
             if isinstance(h, ast.ExceptHandler) and h.name
             and any(anchor in ast.unparse(s) for s in h.body)]
    assert len(_hits) == 1, f"{rel}：含 {anchor!r} 的 except 區塊應恰一個，實得 {len(_hits)}"
    _h = _hits[0]
    _st = FakeSt()
    _ns = _mod_ns(rel, st=_st, **bind)
    _ns[_h.name] = exc
    if not any(isinstance(n, ast.Return) for s in _h.body for n in ast.walk(s)):
        # 沒有 return → 直接在命名空間裡執行，賦值（`_r['error'] = …`）留在 `_ns` 供斷言
        exec(compile(ast.Module(_h.body, []), rel, "exec"), _ns)  # noqa: S102
        return None, _st, _ns
    _body = textwrap.indent("\n".join(ast.unparse(s) for s in _h.body), "    ")
    exec(compile("def __handler__():\n" + _body + "\n", rel, "exec"), _ns)  # noqa: S102
    return _ns["__handler__"](), _st, _ns


# ══════════════════════════════════════════════════════════════════
# 1. 直接把例外印上畫面的出口（`st.error/warning/caption(f'…{e}')`）
#    (檔案, 錨點, 例外變數名, 額外綁定)
# ══════════════════════════════════════════════════════════════════
_DIRECT = [
    ("app.py", "分頁渲染異常", "_e_tab", {"_label": "個股"}),
    ("app.py", "加入失敗", "_e_add", {}),
    ("app.py", "凍結失敗", "_e_fz", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "換股建議暫略", "_se", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "戰情室運算失敗", "_e", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "組合深度分析載入失敗", "_e_pf", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "葡萄串領息法載入失敗", "_e_gl", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "AI 摘要失敗", "_e", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "投資組合 Portfolio Sheet 判定略過", "_e", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "投資組合 Portfolio讀取失敗", "_e", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "觀察清單 Watchlist Sheet 判定略過", "_e", {}),
    ("src/ui/etf/etf_tab_dividend_station.py", "觀察清單 Watchlist讀取失敗", "_e", {}),
    ("src/ui/etf/etf_tab_smart.py", "批次價格資料載入失敗", "_e", {}),
    ("src/ui/etf/etf_tab_smart.py", "同儕資料載入失敗", "_e2", {}),
    ("src/ui/pages/calibration_ui.py", "匯入校準模組失敗", "_e", {}),
    ("src/ui/pages/calibration_ui.py", "抓 ^TWII 異常", "_e", {}),
    ("src/ui/pages/calibration_ui.py", "回測異常", "_e", {}),
    ("src/ui/pages/health_inspector.py", "proxy_helper 例外", "_ep_d", {}),
    ("src/ui/pages/health_inspector.py", "curl_cffi 例外", "_ec_d", {}),
    ("src/ui/tabs/macro/helpers.py", "風險雷達模組載入失敗", "_e_imp", {}),
    ("src/ui/tabs/macro/helpers.py", "風險雷達抓取失敗", "_e_rd", {}),
    ("src/ui/tabs/macro/helpers.py", "中國拖累 China Drag:⚠️ 取數失敗", "_e", {}),
    ("src/ui/tabs/macro/section_state.py", "熱錢監測渲染失敗", "_hme", {}),
    ("src/ui/tabs/portfolio_binder.py", "建立新 Sheet 失敗", "_e", {}),
    ("src/ui/tabs/portfolio_manager.py", "讀取投資組合清單失敗", "_e", {}),
    ("src/ui/tabs/portfolio_manager.py", "讀取觀察清單失敗", "_e", {}),
    ("src/ui/tabs/stock_grp_sections/section_industry_concentration.py", "產業集中度計算失敗", "_e", {}),
    ("src/ui/tabs/stock_sections/section_when_buy_sell.py", "出場點綜合提示暫不可用", "_ex_err", {}),
    ("src/ui/tabs/stock_sections/section_when_buy_sell.py", "K 線繪製失敗", "_kl_err", {}),
    ("src/ui/tabs/tab_edu.py", "無法載入 data_registry", "_ie", {}),
]
# 同一錨點在檔內出現多次的（兩處「價格資料載入失敗」「圖表渲染失敗」「儲存失敗」）另外測。
_DIRECT_IDS = [f"{r[0].rsplit('/', 1)[-1]}::{r[1][:18]}" for r in _DIRECT]


@pytest.mark.parametrize("rel,anchor,var,extra", _DIRECT, ids=_DIRECT_IDS)
def test_direct_exit_scrubs_secrets(rel, anchor, var, extra):
    _st = _run_call(rel, anchor, **{var: RuntimeError(_SECRET_MSG)}, **extra)
    assert _st.out, "出口沒有畫出任何東西"
    _assert_no_leak(_st.text)
    assert "***" in _st.text.replace("\\*", "*"), "應留下遮罩（看得到有東西被遮）"


@pytest.mark.parametrize("rel,anchor,var,extra", _DIRECT, ids=_DIRECT_IDS)
def test_direct_exit_plain_message_unchanged(rel, anchor, var, extra):
    _st = _run_call(rel, anchor, **{var: RuntimeError(_PLAIN_MSG)}, **extra)
    assert _PLAIN_MSG in _st.text


def _all_calls(rel: str, anchor: str) -> list[ast.Call]:
    return [n for n in ast.walk(_tree(rel))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "st"
            and anchor in ast.unparse(n)]


@pytest.mark.parametrize("rel,anchor,count", [
    ("src/ui/etf/etf_tab_smart.py", "價格資料載入失敗：", 2),
    ("src/ui/etf/etf_tab_smart.py", "圖表渲染失敗", 2),
    ("src/ui/tabs/portfolio_manager.py", "儲存失敗", 2),
])
def test_repeated_direct_exits_all_scrub(rel, anchor, count):
    """同一段文案在檔內出現多次 → **每一處**都要洗（少洗一處就紅）。"""
    _calls = [c for c in _all_calls(rel, anchor) if "批次" not in ast.unparse(c)]
    assert len(_calls) == count
    for _c in _calls:
        _var = next(n.id for n in ast.walk(_c) if isinstance(n, ast.Name)
                    and n.id not in {"st", "scrub_md", "type"})
        _st = FakeSt()
        _ns = _mod_ns(rel, st=_st, **{_var: RuntimeError(_SECRET_MSG)})
        eval(compile(ast.Expression(_c), rel, "eval"), _ns)  # noqa: S307
        _assert_no_leak(_st.text)


def test_app_tab_shell_truncates_after_scrubbing():
    """分頁外殼截 300 字：秘密在第 290 字附近也不能被截成「半截露出」。"""
    _pad = "x" * 270 + " "
    _st = _run_call("app.py", "分頁渲染異常", _e_tab=RuntimeError(_pad + _SECRET_MSG), _label="個股")
    _assert_no_leak(_st.text)
    # 半截秘密也不行：token 前 8 字元就夠辨識
    assert _TOKEN[:12] not in _st.text and _SECRET_VAL[:8] not in _st.text
    assert not _st.text.endswith("\\"), "截斷不可截出落單的跳脫字元"


def test_markdown_asterisks_in_exception_are_escaped():
    """清洗後的例外原文走 Markdown：`*` 必須跳脫（遮罩 `***` 不可被吃成粗體）。"""
    _st = _run_call("app.py", "加入失敗", _e_add=RuntimeError(_SECRET_MSG))
    assert "***" not in _st.text.replace("\\*", "")
    assert "\\*\\*\\*" in _st.text


# ══════════════════════════════════════════════════════════════════
# 2. ⭐ api_diagnostic：真的壞 secrets 檔（比照 b11）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def broken_secrets(tmp_path):
    from streamlit import config as st_config
    from streamlit.runtime.secrets import Secrets

    _dir = tmp_path / f"home_{_USER}" / ".streamlit"
    _dir.mkdir(parents=True)
    _path = _dir / "secrets.toml"
    # 解析失敗（Unbalanced quotes）——失敗那一行之前放一個假金鑰；
    # Streamlit 的訊息會帶出檔案完整路徑。
    _path.write_text(f'client_secret = "{_SECRET_VAL}"\nportfolio_sheet_id = "abc\n', encoding="utf-8")
    _orig = st_config.get_option("secrets.files")
    st_config.set_option("secrets.files", [str(_path)])
    yield Secrets(), _path
    st_config.set_option("secrets.files", _orig)


def _api_diag(monkeypatch, secrets, *, button=False):
    import src.ui.pages.api_diagnostic as AD
    _st = FakeSt(button=button, secrets=secrets)
    monkeypatch.setattr(AD, "st", _st)
    monkeypatch.setattr("src.data.proxy.proxy_helper.get_proxy_config", lambda: {})
    for _k in ("GEMINI_API_KEY", "FINMIND_TOKEN", "FRED_API_KEY", "PROXY_URL",
               "PROXY_HOST", "PROXY_PORT"):
        monkeypatch.delenv(_k, raising=False)
    return AD, _st


def test_api_diagnostic_secrets_parse_error_is_scrubbed(monkeypatch, broken_secrets):
    _secrets, _path = broken_secrets
    # 前提：真的 Streamlit 在這個檔上會丟出帶路徑的解析錯誤（它變了 → 這裡先說）
    with pytest.raises(Exception) as _ei:
        list(_secrets.keys())
    assert str(_path) in str(_ei.value), "前提變了：Streamlit 的解析錯誤不再帶路徑"
    AD, _st = _api_diag(monkeypatch, _secrets)
    AD.render_api_diagnostic()
    assert "st.secrets 解析失敗" in _st.text
    _assert_no_leak(_st.text)
    assert str(_path.parent) not in _st.text
    assert "StreamlitSecretNotFoundError" in _st.text  # 型別名照留


def test_api_diagnostic_probe_error_is_scrubbed(monkeypatch, broken_secrets):
    """端對端實測：requests 例外帶出含 `api_key=` 的完整 URL（FRED 只收 query 金鑰）。"""
    import requests
    _secrets, _ = broken_secrets
    AD, _st = _api_diag(monkeypatch, _secrets, button=True)
    monkeypatch.setenv("FRED_API_KEY", _API_KEY)

    def _boom(url, params=None, **k):
        _q = "&".join(f"{a}={b}" for a, b in (params or {}).items())
        raise requests.exceptions.ConnectionError(f"Max retries exceeded with url: {url}?{_q} " + _SECRET_MSG)

    monkeypatch.setattr(requests, "get", _boom)
    AD.render_api_diagnostic()
    assert "ConnectionError" in _st.text
    _assert_no_leak(_st.text)


@pytest.mark.parametrize("ok", [False, True], ids=["error_branch", "success_branch"])
def test_api_diagnostic_probe_via_proxy_both_columns_scrubbed(monkeypatch, broken_secrets, ok):
    """有設 proxy → 「走 Proxy」與「直連」兩欄、成功與失敗兩種分支，每一欄都要洗。

    成功分支印的是 `HTTP <code> <回應開頭 80 字>` —— 回應本文也可能夾帶金鑰（例：錯誤頁回顯 token）。
    """
    import requests
    _secrets, _ = broken_secrets
    AD, _st = _api_diag(monkeypatch, _secrets, button=True)
    monkeypatch.setattr("src.data.proxy.proxy_helper.get_proxy_config",
                        lambda: {"http": "http://nas.test:3128", "https": "http://nas.test:3128"})
    _body = f'Bearer {_TOKEN} client_secret = "{_SECRET_VAL}"'

    class _Resp:
        status_code = 200
        text = _body

    def _get(*a, **k):
        if ok:
            return _Resp()
        raise requests.exceptions.ProxyError(_body)

    monkeypatch.setattr(requests, "get", _get)
    AD.render_api_diagnostic()
    assert ("HTTP 200" if ok else "ProxyError") in _st.text
    assert _st.text.count("走 Proxy") >= 1
    _assert_no_leak(_st.text)


def test_api_diagnostic_probe_truncates_after_scrubbing(monkeypatch):
    """`_probe` 截 120 字：秘密跨在截斷點上也不能留下半截（必須先洗再截）。"""
    import requests
    import src.ui.pages.api_diagnostic as AD
    _msg = "x" * 95 + f" Bearer {_TOKEN}"  # token 開頭落在第 ~104 字，先截會留下半截

    def _boom(*a, **k):
        raise requests.exceptions.ConnectionError(_msg)

    monkeypatch.setattr(requests, "get", _boom)
    _ok, _m = AD._probe("t", "https://x.test")
    assert _ok is False
    assert _TOKEN[:8] not in _m, _m


def test_api_diagnostic_probe_plain_message_unchanged(monkeypatch, broken_secrets):
    import requests
    _secrets, _ = broken_secrets
    AD, _st = _api_diag(monkeypatch, _secrets, button=True)

    def _boom(*a, **k):
        raise requests.exceptions.ConnectionError(_PLAIN_MSG)

    monkeypatch.setattr(requests, "get", _boom)
    AD.render_api_diagnostic()
    assert f"ConnectionError: {_PLAIN_MSG}" in _st.text


# ══════════════════════════════════════════════════════════════════
# 3. 經回傳值／變數才上畫面的出口
# ══════════════════════════════════════════════════════════════════
def test_chip_radar_err_is_scrubbed(monkeypatch):
    import src.ui.tabs.chip_radar as CR
    for _msg, _leak in ((_SECRET_MSG, True), (_PLAIN_MSG, False)):
        _st = FakeSt()
        monkeypatch.setattr(CR, "st", _st)
        _fake = lambda _t, _m=_msg: {"df": pd.DataFrame(), "err": _m}  # noqa: E731
        _fake.clear = lambda: None
        monkeypatch.setattr(CR, "fetch_chip_concentration", _fake)
        CR.render_chip_radar("2330")
        if _leak:
            _assert_no_leak(_st.text)
        else:
            assert f"診斷訊息：{_PLAIN_MSG}" in _st.text


def test_macro_compass_err_is_scrubbed(monkeypatch):
    import src.ui.render.app_render as AR
    for _msg in (_SECRET_MSG, _PLAIN_MSG):
        _st = FakeSt()
        _st.session_state["_macro_compass_cache"] = {"_ts": None, "data": {}, "_err": f"RuntimeError: {_msg}"}
        monkeypatch.setattr(AR, "st", _st)
        AR.render_macro_compass()
        assert "抓取失敗" in _st.text
        if _msg is _SECRET_MSG:
            _assert_no_leak(_st.text)
        else:
            assert f"抓取失敗：RuntimeError: {_PLAIN_MSG}，請稍後重試" in _st.text


def test_macro_compass_fetch_path_end_to_end(monkeypatch):
    """按鈕 callback 真的抓失敗 → 存進 session → 畫出來，全程不外露。"""
    import src.ui.render.app_render as AR
    _st = FakeSt()
    monkeypatch.setattr(AR, "st", _st)

    def _boom():
        raise RuntimeError(_SECRET_MSG)

    monkeypatch.setattr("src.data.macro.fetch_macro_compass", _boom)
    _cb = {}

    def _button(*a, on_click=None, **k):
        _cb["f"] = on_click
        return False

    _st.button = _button
    AR.render_macro_compass()
    _cb["f"]()
    AR.render_macro_compass()
    assert "抓取失敗" in _st.text
    _assert_no_leak(_st.text)


def test_hot_money_fx_error_is_scrubbed(monkeypatch):
    import src.ui.tabs.hot_money as HM
    for _msg in (_SECRET_MSG, _PLAIN_MSG):
        _st = FakeSt()
        monkeypatch.setattr(HM, "st", _st)
        HM.render_hot_money_section(None, "", requested=True, fx_error=_msg)
        assert "取得失敗" in _st.text
        if _msg is _SECRET_MSG:
            _assert_no_leak(_st.text)
            assert "**重按更新對這個原因不一定有效**" in _st.text  # 原句刻意的粗體不動
        else:
            assert f"取得失敗：{_PLAIN_MSG}" in _st.text


def test_financial_leading_errors_are_scrubbed(monkeypatch):
    import src.ui.tabs.stock_sections.section_financial_leading as FL
    for _msg in (_SECRET_MSG, _PLAIN_MSG):
        _st = FakeSt()
        monkeypatch.setattr(FL, "st", _st)
        FL.render_financial_leading_section("2330", None, None, "FinMind", "", [_msg])
        assert "財報資料抓取失敗" in _st.text
        if _msg is _SECRET_MSG:
            _assert_no_leak(_st.text)
        else:
            assert f"錯誤:{_PLAIN_MSG}" in _st.text


def test_tab_stock_financial_health_error_is_scrubbed():
    _anchor = "財報體檢失敗，請確認 FINMIND_TOKEN 已設定。"
    _st = _run_call("src/ui/tabs/tab_stock.py", _anchor,
                    _fh={"error": True, "ai_insight": f"財報體檢發生例外：{_SECRET_MSG}"})
    _assert_no_leak(_st.text)
    _st = _run_call("src/ui/tabs/tab_stock.py", _anchor,
                    _fh={"error": True, "ai_insight": f"**財報體檢**發生例外：{_PLAIN_MSG}"})
    assert f"**財報體檢**發生例外：{_PLAIN_MSG}" in _st.text  # 刻意粗體與一般訊息都不動


def test_tab_stock_picker_ai_report_error_is_scrubbed():
    _ret, _, _ = _run_handler("src/ui/tabs/tab_stock_picker.py", "AI 生成失敗",
                              RuntimeError(_SECRET_MSG))
    assert _ret.startswith("❌ AI 生成失敗：RuntimeError")
    _assert_no_leak(_ret)
    _ret, _, _ = _run_handler("src/ui/tabs/tab_stock_picker.py", "AI 生成失敗",
                              RuntimeError(_PLAIN_MSG))
    assert _ret == f"❌ AI 生成失敗：RuntimeError: {_PLAIN_MSG}"


def test_etf_grp_compare_row_error_is_scrubbed_before_truncation():
    """備註欄截 50 字：必須先洗再截（先截會把秘密截成半截、對不上清洗規則）。"""
    _rel = "src/ui/etf/etf_tab_grp_compare.py"
    _msg = f"Bearer {_TOKEN}"  # 放最前面：先截 50 字的話 token 會整段留在截斷範圍內
    _, _, _ns = _run_handler(_rel, "_r['error'] =", RuntimeError(_msg),
                             build_etf_score_row=lambda *a: {})
    assert _TOKEN not in _ns["_r"]["error"] and _TOKEN[:12] not in _ns["_r"]["error"]
    _rows: list = []
    _run_handler(_rel, "rows.append({'ticker'", RuntimeError(_msg),
                 rows=_rows, _futs={"f": "0050"}, _fut="f")
    assert _rows and _TOKEN[:12] not in _rows[0]["error"]
    _, _, _ns = _run_handler(_rel, "_r['error'] =", RuntimeError(_PLAIN_MSG),
                             build_etf_score_row=lambda *a: {})
    assert _ns["_r"]["error"] == f"RuntimeError: {_PLAIN_MSG}"[:len("RuntimeError: ") + 50]


# ── health_inspector：診斷表 error_msg 欄（`_row`）＋ 兩個 session 訊息 ─────────
def _health_row_fn():
    _fn = next(n for n in ast.walk(_tree("src/ui/pages/health_inspector.py"))
               if isinstance(n, ast.FunctionDef) and n.name == "_row")
    _ns = _mod_ns("src/ui/pages/health_inspector.py", _FREQ_LBL={"daily": "日頻"},
              _light=lambda *a: ("🟢", "ok"))
    exec(compile(ast.Module([_fn], []), "health_inspector._row", "exec"), _ns)  # noqa: S102
    return _ns["_row"]


@pytest.mark.parametrize("kw", [{"probe_status": "fail"}, {"probe_status": "na"}, {}])
def test_health_inspector_row_error_msg_is_scrubbed(kw):
    _row = _health_row_fn()
    # 秘密放前面 —— 截斷在 50/55 字，先截會留下半截
    _r = _row("x", None, "daily", error_msg=f"Bearer {_TOKEN} {_SECRET_MSG}", **kw)
    _txt = repr(_r)
    assert _TOKEN[:12] not in _txt
    _r = _row("x", None, "daily", error_msg=_PLAIN_MSG, **kw)
    assert _PLAIN_MSG in repr(_r)


def _run_if(rel: str, test_src: str, **bind) -> FakeSt:
    _node = next(n for n in ast.walk(_tree(rel))
                 if isinstance(n, ast.If) and ast.unparse(n.test) == test_src)
    _st = FakeSt()
    _ns = _mod_ns(rel, st=_st, **bind)
    exec(compile(ast.Module([_node], []), rel, "exec"), _ns)  # noqa: S102
    return _st


def test_health_inspector_margin_diag_msg_is_scrubbed():
    _rel = "src/ui/pages/health_inspector.py"
    _, _st0, _ = _run_handler(_rel, "_diag_margin_msg", RuntimeError(_SECRET_MSG))
    _stored = _st0.session_state["_diag_margin_msg"]
    _st = _run_if(_rel, "_diag_msg", _diag_msg=_stored)
    _assert_no_leak(_st.text)
    _st = _run_if(_rel, "_diag_msg", _diag_msg=f"❌ 測試異常：RuntimeError: {_PLAIN_MSG}")
    assert f"❌ 測試異常：RuntimeError: {_PLAIN_MSG}" in _st.text


def test_health_inspector_proxy_diag_msg_is_scrubbed():
    _rel = "src/ui/pages/health_inspector.py"
    _pm = "❌ **0050.TW 成分股仍抓不到**\n\n" + f"❌ 測試異常：RuntimeError: {_SECRET_MSG}"
    _st = _run_if(_rel, "_pm", _pm=_pm)
    _assert_no_leak(_st.text)
    assert "**0050.TW 成分股仍抓不到**" in _st.text  # 刻意的粗體不動
    _st = _run_if(_rel, "_pm", _pm=f"❌ 測試異常：RuntimeError: {_PLAIN_MSG}")
    assert f"❌ 測試異常：RuntimeError: {_PLAIN_MSG}" in _st.text


# ══════════════════════════════════════════════════════════════════
# 4. L0 包裝本身
# ══════════════════════════════════════════════════════════════════
def test_secret_md_helpers():
    assert scrub_md(None) == "" and scrub_md_mask(None) == ""
    assert scrub_md(_PLAIN_MSG) == _PLAIN_MSG
    assert scrub_md("a*b") == "a\\*b"
    assert scrub_md_mask("**粗** a*b") == "**粗** a*b"
    _m = scrub_md_mask(_SECRET_MSG)
    _assert_no_leak(_m)
    assert "\\*\\*\\*" in _m
    # 截斷夾在清洗與跳脫之間
    _t = scrub_md("*" * 10, limit=3)
    assert _t == "\\*\\*\\*"


# ══════════════════════════════════════════════════════════════════
# 5. 截斷順序：秘密**跨在截斷點上**的反例（QA 追加，2026-09-26）
#    先截再洗 → 留下的半截對不上清洗規則而外露：
#    · `AIza…` 截在第 9 字（`AIzaSyA12`，規則要 AIza 後 ≥10 字才認）；
#    · `https://u:pw@host` 截在 `@` 前（userinfo 規則要看到 `@`）。
# ══════════════════════════════════════════════════════════════════
_EDGE_USERINFO = "https://bob:hunter2pwSEC3@db.test/x"
_EDGE_KINDS = {
    "aiza_cut_at_9": (_API_KEY, _API_KEY[:9], _API_KEY[:9]),
    "userinfo_cut_before_at": (_EDGE_USERINFO, _EDGE_USERINFO.split("@")[0], "hunter2pwSEC3"),
}


def _edge(limit: int, kind: str) -> tuple[str, str]:
    """回 (例外字串, 不得出現的外露片段)：`字串[:limit]` 恰好停在 kind 描述的位置。"""
    _full, _cut, _leak = _EDGE_KINDS[kind]
    _pad = "y" * (limit - len(_cut) - 1) + " "
    _s = _pad + _full
    assert _s[:limit].endswith(_cut)
    # 前提：先截再洗真的會外露（清洗規則若日後擴充到認得半截，這條會提醒更新反例）
    assert _leak in scrub_secrets(_s[:limit]), "反例失效：半截秘密已能被清洗"
    assert _leak not in scrub_secrets(_s)
    return _s, _leak


_KINDS = list(_EDGE_KINDS)


@pytest.mark.parametrize("kind", _KINDS)
def test_edge_app_tab_shell_300(kind):
    _msg, _leak = _edge(300, kind)
    _st = _run_call("app.py", "分頁渲染異常", _e_tab=RuntimeError(_msg), _label="個股")
    assert _leak not in _st.text.replace("\\*", "*")


@pytest.mark.parametrize("kind", _KINDS)
def test_edge_api_probe_120(kind, monkeypatch):
    import requests
    import src.ui.pages.api_diagnostic as AD
    _msg, _leak = _edge(120, kind)

    def _boom(*a, **k):
        raise requests.exceptions.ConnectionError(_msg)

    monkeypatch.setattr(requests, "get", _boom)
    _ok, _m = AD._probe("t", "https://x.test")
    assert _ok is False and _leak not in _m


@pytest.mark.parametrize("kind", _KINDS)
def test_edge_grp_compare_50(kind):
    _rel = "src/ui/etf/etf_tab_grp_compare.py"
    _msg, _leak = _edge(50, kind)
    _, _, _ns = _run_handler(_rel, "_r['error'] =", RuntimeError(_msg),
                             build_etf_score_row=lambda *a: {})
    assert _leak not in _ns["_r"]["error"]
    _rows: list = []
    _run_handler(_rel, "rows.append({'ticker'", RuntimeError(_msg),
                 rows=_rows, _futs={"f": "0050"}, _fut="f")
    assert _leak not in _rows[0]["error"]


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("kw,limit", [({"probe_status": "fail"}, 50),
                                      ({"probe_status": "na"}, 55), ({}, 55)])
def test_edge_health_row(kind, kw, limit):
    _msg, _leak = _edge(limit, kind)
    _r = _health_row_fn()("x", None, "daily", error_msg=_msg, **kw)
    assert _leak not in repr(_r)


def _coverage_rows(state):
    import datetime as _dtm
    from src.ui.pages.data_coverage import compute_tab_coverage
    return compute_tab_coverage(state=state, today=_dtm.date(2026, 9, 26))


@pytest.mark.parametrize("kind", _KINDS)
def test_edge_data_coverage_price_err_70(kind):
    _msg, _leak = _edge(70, kind)
    _txt = repr(_coverage_rows({"t2_data": {"sid": "2330", "err": _msg}}))
    assert "價格抓取失敗" in _txt and _leak not in _txt


@pytest.mark.parametrize("kind", _KINDS)
def test_edge_data_coverage_nav_err_50(kind):
    _msg, _leak = _edge(50, kind)
    _txt = repr(_coverage_rows({"etf_single_data": {"ticker": "0050", "_err_nav": _msg}}))
    assert "NAV 缺" in _txt and _leak not in _txt


def test_data_coverage_messages_scrubbed_and_plain_unchanged():
    _txt = repr(_coverage_rows({"t2_data": {"sid": "2330", "err": _SECRET_MSG},
                                "etf_single_data": {"ticker": "0050", "_err_nav": _SECRET_MSG}}))
    _assert_no_leak(_txt)
    _rows = _coverage_rows({"t2_data": {"sid": "2330", "err": "HTTP 502 *x*"},
                            "etf_single_data": {"ticker": "0050", "_err_nav": "HTTP 404 *y*"}})
    _details = " ".join(r["detail"] for r in _rows)
    # HTML 欄位：不做 Markdown 跳脫，一般訊息逐字不變
    assert "價格抓取失敗：HTTP 502 *x*" in _details and "NAV 缺:HTTP 404 *y*" in _details


# ══════════════════════════════════════════════════════════════════
# 6. QA 追加的 7 處漏網出口（2026-09-26）
# ══════════════════════════════════════════════════════════════════
_MORE = [
    # (檔案, 錨點, 綁定名, 綁定值的包裝, 畫面上一般訊息應出現的樣子)
    ("src/ui/tabs/stock_sections/section_kline_chart.py", "t2d['err']", "t2d",
     lambda m: {"err": f"系統錯誤: {m}"}, lambda m: f"❌ 系統錯誤: {m}"),
    ("src/ui/tabs/hot_money.py", "ferr", "ferr", lambda m: f"FinMind 抓取失敗:{m}",
     lambda m: f"FinMind 抓取失敗:{m}"),
    ("src/ui/tabs/stock_sections/section_chips_20d.py", "籌碼集中度取得失敗", "_chip20",
     lambda m: {"error": m}, lambda m: f"籌碼集中度取得失敗：{m}"),
    ("src/ui/tabs/tab_stock.py", "_diag", "_diag",
     lambda m: ["proxy HTTP 403 entries=0", f"直連 錯誤 {m}"], lambda m: f"直連 錯誤 {m}"),
]


@pytest.mark.parametrize("rel,anchor,name,wrap,shown", _MORE,
                         ids=[m[0].rsplit("/", 1)[-1] for m in _MORE])
def test_more_exits_scrub_secrets(rel, anchor, name, wrap, shown):
    _st = _run_call(rel, anchor, **{name: wrap(_SECRET_MSG)})
    assert _st.out
    _assert_no_leak(_st.text)
    _st = _run_call(rel, anchor, **{name: wrap(_PLAIN_MSG)})
    assert shown(_PLAIN_MSG) in _st.text


def test_st_code_diag_is_not_markdown_escaped():
    """`st.code` 不走 Markdown：遮罩原樣 `***`，⛔ 不跳脫。"""
    _st = _run_call("src/ui/tabs/tab_stock.py", "_diag", _diag=[f"x {_SECRET_MSG}"])
    assert "***" in _st.text and "\\*" not in _st.text


def test_section_mid_macro_errors_both_listings_scrubbed():
    """`_err_*` 兩處清單（展開／不展開）都在反引號內 → 用 `scrub_secrets`，不跳脫。"""
    _rel = "src/ui/tabs/macro/section_mid.py"
    _calls = [c for c in _all_calls(_rel, "_ev")]
    assert len(_calls) == 2
    for _c in _calls:
        for _msg, _leak in ((_SECRET_MSG, True), (_PLAIN_MSG, False)):
            _st = FakeSt()
            _ns = _mod_ns(_rel, st=_st, _ek="_err_vix", _ev=f"RuntimeError: {_msg}",
                          _err_label_map={"_err_vix": "VIX 恐慌指數"})
            eval(compile(ast.Expression(_c), _rel, "eval"), _ns)  # noqa: S307
            if _leak:
                _assert_no_leak(_st.text)
            else:
                assert f"`RuntimeError: {_PLAIN_MSG}`" in _st.text


def test_ai_chat_render_bundle_and_panel_errors_scrubbed(monkeypatch):
    import types
    import src.ui.tabs.tab_ai_chat as AC
    for _msg, _leak in ((f"import 失敗:{_SECRET_MSG}", True), (_PLAIN_MSG, False)):
        _st = FakeSt()
        monkeypatch.setattr(AC, "st", _st)
        AC._render_bundle({"get_quote": {"ok": False, "error": _msg}})
        AC._render_panel(types.SimpleNamespace(ok=False, error=_msg, data_bundle={}))
        if _leak:
            _assert_no_leak(_st.text)
        else:
            assert _st.text.count(_PLAIN_MSG) == 2


def _run_assign(rel: str, anchor: str, **bind) -> "_NS":
    _hits = [n for n in ast.walk(_tree(rel))
             if isinstance(n, ast.Assign) and anchor in ast.unparse(n)]
    assert len(_hits) == 1, f"{rel}：含 {anchor!r} 的賦值應恰一個，實得 {len(_hits)}"
    _ns = _mod_ns(rel, **bind)
    exec(compile(ast.Module(_hits, []), rel, "exec"), _ns)  # noqa: S102
    return _ns


def test_ai_chat_answer_body_error_scrubbed():
    """聊天回覆失敗 → `body` 既上畫面又存進 `ai_qa_history`（下一輪重畫）：洗在 body 本身。"""
    import types
    _rel = "src/ui/tabs/tab_ai_chat.py"
    _ns = _run_assign(_rel, "body = f'⚠️", res=types.SimpleNamespace(error=_SECRET_MSG))
    _assert_no_leak(_ns["body"])
    _ns = _run_assign(_rel, "body = f'⚠️", res=types.SimpleNamespace(error=_PLAIN_MSG))
    assert _ns["body"] == f"⚠️ {_PLAIN_MSG}"


def test_app_py_scrub_import_is_real():
    """M17：`app.py` 必須真的 import 它用到的清洗函式（測試不再代為注入）。"""
    _ns = _mod_ns("app.py")
    assert _ns.get("scrub_md") is scrub_md


def test_ai_chat_regime_blocked_error_keeps_bold_and_masks_secrets(monkeypatch):
    """L3 `_regime_blocked_error` 的錯誤字串**本身含刻意 `**粗體**`**：
    `_render_bundle`／`_render_panel`／回覆 body 都只跳脫遮罩（`scrub_md_mask`），
    ⛔ 不可全跳脫（使用者會看到字面 `\\*\\*`）；秘密仍要遮。"""
    import types
    import src.ui.tabs.tab_ai_chat as AC
    from shared.scoring_regime_gate import ScoringRegimeDecision
    from src.services.ai_qa_service import _regime_blocked_error
    _err = _regime_blocked_error(ScoringRegimeDecision(regime=None, reason=(
        # ⚠️ 不放 `client_secret = …`：TOML 賦值規則會遮到行尾，把後面的粗體一起吃掉，測不到跳脫
        f"讀取失敗 /home/{_USER}/app/.streamlit/secrets.toml token {_TOKEN} "
        f"https://docs.google.com/spreadsheets/d/{_SHEET_ID}/edit url=https://x.test/v1?key={_API_KEY}")))
    assert "**" in _err  # 前提：L3 字串真的帶刻意粗體
    _bold = [s for s in _err.split("**")[1::2]]
    _st = FakeSt()
    monkeypatch.setattr(AC, "st", _st)
    AC._render_bundle({"get_stock_score": {"ok": False, "error": _err}})
    AC._render_panel(types.SimpleNamespace(ok=False, error=_err, data_bundle={}))
    _ns = _run_assign("src/ui/tabs/tab_ai_chat.py", "body = f'⚠️",
                      res=types.SimpleNamespace(error=_err))
    _shown = [o for o in _st.out if "無法計算多因子評分" in o]
    assert len(_shown) == 2  # bundle 一次 + panel 一次
    for _txt in (*_shown, _ns["body"]):
        _assert_no_leak(_txt)
        assert "\\*\\*\\*" in _txt  # 遮罩被跳脫
        for _b in _bold:
            assert f"**{_b}**" in _txt, f"刻意粗體被跳脫：{_b!r}"
