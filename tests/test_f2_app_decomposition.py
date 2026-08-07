"""F2(2026-08)— 解構 app.py:`gemini_call` / `_bps` 下沉,消掉 5 處 `from app import`。

對應 CLAUDE.md §8.2.A.2 的兩筆待修違憲(**同一根因**):
  V-APP-1    L6 App 兼任 L1(`_bps` 造 requests.Session)與 L3(`gemini_call` 直打
             Gemini HTTP、`_build_llm_context` 組 prompt)
  V-UP-APP-1 5 處 L5 → L6 上行 import,靠 `app.py` 頂部的 `_AppProxy` +
             `sys.modules['app']` 劫持才不會循環 import

搬遷落點
────────
  gemini_call / 金鑰池 / get_gemini_api_key / build_llm_context
        → L3  src/services/app_ai_service.py
  _tw_now / _tw_now_str  → L0  shared/macro_compute.py
  _get_fm_token          → L0  src/config/config.py::get_finmind_token
  parse_stocks           → L0  shared/parse_helpers.py(v18.302 就在了,只是 caller 沒改)
  _bps                   → L1  src/data/proxy/proxy_helper.py::build_unverified_proxy_session

測試設計原則(本 session 踩過的坑,勿回退)
──────────────────────────────────────
1. **行為斷言優先。** 金鑰池 / round-robin / 429 換 key / build_llm_context 全部
   真的呼叫函式驗行為,不靠讀原始碼猜。
2. **非寫不可的原始碼守衛一律走 AST**,不用字串比對:
   docstring 與註解裡大量出現 `from app import ...`、`def _bps`、`gemini_call`
   這些字樣(本檔自己就是),字串掃描 = 保證假紅燈。失敗訊息一律印出該行原文。
3. **patch 一定要斷言 mock 真的被呼叫過。** 否則 patch 目標打錯時,測試會照樣綠 ——
   而真正發生的是「去打真的 Gemini API」。本檔每個 fake HTTP 都記 call list 並斷言。
4. **金鑰一律用 monkeypatch 隔離。** 開發機若有 `.streamlit/secrets.toml`,
   真 key 會漏進測試 → 不確定性 + 真的送出請求。本檔把 module 的 `st` 換成
   空 secrets stub,並清掉 6 個 GEMINI_API_KEY* 環境變數。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# F2 之後不得再出現 `from app import ...` 的模組。
# V-UP-APP-1 原文寫「5 處」—— 那是 **import 陳述** 5 處,分佈在 **4 個檔案**
# (`tab_stock_grp.py` 有兩處:render_stock_grp 與三階段濾網區各一)。
_FORMER_APP_IMPORTERS = (
    "src/ui/tabs/tab_macro.py",
    "src/ui/tabs/tab_stock.py",
    "src/ui/tabs/tab_stock_grp.py",
    "src/ui/tabs/macro/section_news_ai.py",
)

_GEMINI_ENV_NAMES = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 7)]


# ════════════════════════════════════════════════════════════════════
# AST 工具
# ════════════════════════════════════════════════════════════════════
# 掃描全樹時遇到讀不了 / parse 不了的檔案 → 記下來,由 test_scanner_is_healthy 統一報。
# 直接吞掉會讓守衛靜默失效(掃不到 = 假綠燈);直接炸掉又會讓不相干的壞檔擋住本批。
_PARSE_FAILURES: list[str] = []


def _parse(relpath: str) -> tuple[ast.Module, list[str]]:
    try:
        src = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        _PARSE_FAILURES.append(f"{relpath}: 讀檔失敗 {type(e).__name__}: {e}")
        return ast.parse(""), []
    try:
        return ast.parse(src), src.splitlines()
    except SyntaxError as e:
        _PARSE_FAILURES.append(f"{relpath}:{e.lineno}: SyntaxError {e.msg}")
        return ast.parse(""), src.splitlines()


def _line(lines: list[str], lineno: int) -> str:
    return lines[lineno - 1].strip() if 0 < lineno <= len(lines) else "<?>"


def _iter_py(*roots: str) -> list[str]:
    out: list[str] = []
    skip = {"__pycache__", ".git", ".venv", "venv", "node_modules",
            "build", "dist", ".mypy_cache", ".pytest_cache"}
    for root in roots:
        base = REPO_ROOT / root
        if base.is_file():
            out.append(root)
            continue
        for p in base.rglob("*.py"):
            if skip & set(p.relative_to(REPO_ROOT).parts):
                continue
            out.append(p.relative_to(REPO_ROOT).as_posix())
    return sorted(out)


def _func_defs(tree: ast.Module) -> dict[str, ast.AST]:
    """所有(含巢狀)函式定義:name → node。"""
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _import_from_records(tree: ast.Module) -> list[ast.ImportFrom]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]


# ════════════════════════════════════════════════════════════════════
# 1. V-APP-1:app.py 不再定義 gemini_call / _bps / _build_llm_context
# ════════════════════════════════════════════════════════════════════
class TestAppPyNoLongerOwnsL1L3:

    @pytest.mark.parametrize("fn_name", ["gemini_call", "_bps", "_build_llm_context",
                                         "_gemini_keys", "_get_fm_token"])
    def test_app_py_does_not_define(self, fn_name):
        """app.py(L6)不得再**定義**這些 L1/L3 職責的函式。

        用 AST FunctionDef,不用字串 —— app.py 的註解裡刻意留了搬遷紀錄
        (「gemini_call 已下沉 L3」等),字串比對會直接假紅燈。
        """
        tree, lines = _parse("app.py")
        defs = _func_defs(tree)
        node = defs.get(fn_name)
        assert node is None, (
            f"app.py 仍定義 `def {fn_name}` @ line {getattr(node, 'lineno', '?')}:\n"
            f"    {_line(lines, getattr(node, 'lineno', 0))}\n"
            f"→ 這是 CLAUDE.md V-APP-1 點名的違憲(L6 兼任 L1/L3)。"
        )

    def test_app_py_still_exposes_gemini_call_as_orchestrator(self):
        """app.py 仍需**取得** gemini_call(注入各 render 的 gemini_fn)—— 但必須是 import 來的。"""
        tree, lines = _parse("app.py")
        hit = [n for n in _import_from_records(tree)
               if n.module == "src.services.app_ai_service"
               and any(a.name == "gemini_call" for a in n.names)]
        assert hit, (
            "app.py 應以 `from src.services.app_ai_service import gemini_call` 取得,"
            "否則 render_sector_heatmap / render_etf_* 的 gemini_fn 會 NameError。"
        )

    def test_app_py_does_not_build_requests_session(self):
        """app.py 不得再出現 `<x>.verify = False`(造 session = L1 職責)。"""
        tree, lines = _parse("app.py")
        bad = [n for n in ast.walk(tree)
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Attribute) and t.attr == "verify"
                       for t in n.targets)]
        assert not bad, (
            "app.py 仍在設定 session.verify:\n"
            + "\n".join(f"    app.py:{n.lineno}: {_line(lines, n.lineno)}" for n in bad)
        )


# ════════════════════════════════════════════════════════════════════
# 2. V-UP-APP-1:4 個 L5 模組(5 處 import 陳述)不再 `from app import`
# ════════════════════════════════════════════════════════════════════
class TestNoUpwardAppImports:

    @pytest.mark.parametrize("relpath", _FORMER_APP_IMPORTERS)
    def test_module_has_no_from_app_import(self, relpath):
        tree, lines = _parse(relpath)
        bad = [n for n in _import_from_records(tree)
               if n.level == 0 and (n.module or "").split(".")[0] == "app"]
        assert not bad, (
            f"{relpath} 仍有 L5→L6 上行 import(CLAUDE.md V-UP-APP-1):\n"
            + "\n".join(f"    {relpath}:{n.lineno}: {_line(lines, n.lineno)}"
                        for n in bad)
        )

    def test_whole_production_tree_has_no_from_app_import(self):
        """全 production 樹(src/ + shared/ + scripts/)0 處 `from app import`。

        比逐檔 parametrize 更強:防止「修好這 4 個檔、別的檔又新增一處」。
        tests/ 不掃 —— test_parse_helpers.py::test_app_reexport 刻意在 subprocess
        裡 `from app import parse_stocks` 驗 re-export 身分,那是合理用法。
        """
        offenders: list[str] = []
        for rel in _iter_py("src", "shared", "scripts"):
            tree, lines = _parse(rel)
            for n in _import_from_records(tree):
                if n.level == 0 and (n.module or "").split(".")[0] == "app":
                    offenders.append(f"    {rel}:{n.lineno}: {_line(lines, n.lineno)}")
            for n in ast.walk(tree):
                if isinstance(n, ast.Import) and any(a.name == "app" for a in n.names):
                    offenders.append(f"    {rel}:{n.lineno}: {_line(lines, n.lineno)}")
        assert not offenders, (
            "production code 出現 `import app` / `from app import ...`(L*→L6 上行):\n"
            + "\n".join(offenders)
            + "\n→ 需要 app.py 的東西,代表那東西不屬於 L6。請下沉 L0/L1/L3。"
        )

    @pytest.mark.parametrize("relpath", _FORMER_APP_IMPORTERS)
    def test_module_gets_gemini_call_from_l3(self, relpath):
        """反向:確認這 5 個檔是真的改吃 L3,而不是把呼叫整段刪掉了。"""
        tree, _ = _parse(relpath)
        hit = [n for n in _import_from_records(tree)
               if n.module == "src.services.app_ai_service"
               and any(a.name == "gemini_call" for a in n.names)]
        assert hit, f"{relpath} 應改為 `from src.services.app_ai_service import gemini_call`"


# ════════════════════════════════════════════════════════════════════
# 3. _AppProxy / sys.modules['app'] 劫持已移除
# ════════════════════════════════════════════════════════════════════
class TestAppProxyRemoved:

    def test_no_app_proxy_class(self):
        tree, lines = _parse("app.py")
        bad = [n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "_AppProxy"]
        assert not bad, (
            "app.py 仍定義 _AppProxy:\n"
            + "\n".join(f"    app.py:{n.lineno}: {_line(lines, n.lineno)}" for n in bad)
            + "\n→ 它唯一的存在理由是撐住 5 處 `from app import`;那些已消失。"
        )

    def test_no_sys_modules_app_assignment(self):
        """不得再有 `sys.modules['app'] = ...`(AST:Subscript 賦值)。"""
        tree, lines = _parse("app.py")
        bad = []
        for n in ast.walk(tree):
            if not isinstance(n, ast.Assign):
                continue
            for t in n.targets:
                if (isinstance(t, ast.Subscript)
                        and isinstance(t.value, ast.Attribute)
                        and t.value.attr == "modules"):
                    bad.append(n)
        assert not bad, (
            "app.py 仍在劫持 sys.modules:\n"
            + "\n".join(f"    app.py:{n.lineno}: {_line(lines, n.lineno)}" for n in bad)
        )


# ════════════════════════════════════════════════════════════════════
# 4. §2.1 SSOT:_bps 全 repo 只有一份實作
# ════════════════════════════════════════════════════════════════════
class TestBpsSingleSource:

    def test_no_module_defines_bps(self):
        """`def _bps` 在全 repo 應為 0 —— 4 份逐字複本已收斂成一個 L1 函式 + 別名。"""
        offenders: list[str] = []
        for rel in _iter_py("src", "shared", "scripts", "app.py"):
            tree, lines = _parse(rel)
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_bps":
                    offenders.append(f"    {rel}:{n.lineno}: {_line(lines, n.lineno)}")
        assert not offenders, (
            "仍有模組自己 `def _bps`(§2.1 SSOT:應 import "
            "src.data.proxy.proxy_helper.build_unverified_proxy_session):\n"
            + "\n".join(offenders)
        )

    @pytest.mark.parametrize("relpath", [
        "src/data/macro/leading_indicators.py",
        "src/data/daily/daily_data_fetchers.py",
        "src/services/daily_checklist.py",
    ])
    def test_bps_alias_points_at_ssot(self, relpath):
        """原本各自 def 的三個模組,現在必須是 `import ... as _bps` 別名。"""
        tree, _ = _parse(relpath)
        hit = [n for n in _import_from_records(tree)
               if n.module == "src.data.proxy.proxy_helper"
               and any(a.name == "build_unverified_proxy_session" and a.asname == "_bps"
                       for a in n.names)]
        assert hit, (
            f"{relpath} 的 `_bps` 應為 "
            f"`from src.data.proxy.proxy_helper import build_unverified_proxy_session as _bps`"
        )

    def test_verify_false_session_builders_are_registered(self):
        """守衛:新增「造 session 並關 TLS 驗證」的地方就會紅。

        `<x>.verify = False` 是 NAS Squid 自簽憑證的既有妥協(見 SSOT docstring)。
        它散得越多,將來要收掉(改裝 CA bundle)就越難盤點。這裡把現存位置凍結成
        清單:多一個就紅,提示「改用 SSOT,或在此登記並說明為什麼不能共用」。

        ⚠️ 清單裡除 SSOT 外的 4 筆是 **F2 之前就存在的技術債**,不在 F2 範圍:
        它們是 thread-local 單例 / 就地 session(S7 v19.78 的連線池複用優化),
        語意與 SSOT 不同,硬合併會動到批次抓取的連線行為。
        """
        expected = {
            # ── SSOT(F2 建立)──
            ("src/data/proxy/proxy_helper.py", "build_unverified_proxy_session"),
            # ── F2 前既有,thread-local / 就地 session,另案處理 ──
            ("src/data/core/data_loader.py", "_bps_dl"),
            ("src/data/stock/app_stock_fetchers.py", "_make_proxy_session"),
            ("src/data/stock/app_stock_fetchers.py", "fetch_financials"),
            ("src/data/macro/macro_snapshot.py", "_make_proxy_session"),
            ("src/data/macro/macro_snapshot.py", "fetch_export_block"),
        }
        found: set[tuple[str, str]] = set()
        evidence: dict[tuple[str, str], str] = {}
        for rel in _iter_py("src", "app.py"):
            tree, lines = _parse(rel)
            # node id → **最內層** enclosing function 名稱。
            # ast.walk 由外而內,後寫覆蓋前寫 → 最後留下的就是最內層(同 C3 守衛作法)。
            # 不做這步的話,巢狀 def 會讓外層函式一起被記進來 → 假紅燈。
            enclosing: dict[int, str] = {}
            for fn in ast.walk(tree):
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for sub in ast.walk(fn):
                        if isinstance(sub, ast.Assign):
                            enclosing[id(sub)] = fn.name
            for n in ast.walk(tree):
                if not isinstance(n, ast.Assign):
                    continue
                for t in n.targets:
                    if (isinstance(t, ast.Attribute) and t.attr == "verify"
                            and isinstance(n.value, ast.Constant)
                            and n.value.value is False):
                        key = (rel, enclosing.get(id(n), "<module-level>"))
                        found.add(key)
                        evidence.setdefault(key, f"{rel}:{n.lineno}: {_line(lines, n.lineno)}")
        new = sorted(found - expected)
        assert not new, (
            "新增了未登記的 `session.verify = False` 建構點:\n"
            + "\n".join(f"    {evidence[k]}" for k in new)
            + "\n→ 請改用 src.data.proxy.proxy_helper.build_unverified_proxy_session,"
              "\n  或在本測試的 expected 清單登記並在 PR 說明為什麼不能共用。"
        )
        gone = sorted(expected - found)
        assert not gone, (
            "以下登記點已不存在(修好了?)—— 請從本測試 expected 清單移除,"
            "否則清單會變成新的爛帳:\n" + "\n".join(f"    {g}" for g in gone)
        )

    def test_ssot_returns_session_with_verify_disabled(self):
        """行為斷言:SSOT 真的回傳關掉 TLS 驗證的 Session。"""
        import requests

        from src.data.proxy.proxy_helper import build_unverified_proxy_session
        s = build_unverified_proxy_session()
        assert isinstance(s, requests.Session)
        assert s.verify is False, "NAS Squid 自簽憑證路徑需要 verify=False(既有行為)"

    def test_ssot_falls_back_to_bare_session(self, monkeypatch):
        """build_proxy_session 取不到時顯式降級為裸 Session,而不是 raise 或回 None。"""
        import requests

        import src.data.stock as _stock_pkg
        from src.data.proxy import proxy_helper

        def _boom(*_a, **_k):
            raise RuntimeError("proxy 設定壞掉")

        monkeypatch.setattr(_stock_pkg, "build_proxy_session", _boom, raising=False)
        s = proxy_helper.build_unverified_proxy_session()
        assert isinstance(s, requests.Session)
        assert s.verify is False


# ════════════════════════════════════════════════════════════════════
# 5. LLM 呼叫路徑行為不變(行為斷言 + mock 必須真的被呼叫)
# ════════════════════════════════════════════════════════════════════
class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or "{}"

    def json(self):
        return self._payload


def _ok_payload(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class _FakePost:
    """記錄每一次呼叫;`calls` 空 = patch 目標打錯(E2 踩過的坑)。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)


@pytest.fixture()
def ai(monkeypatch):
    """乾淨的 app_ai_service:空 st.secrets + 清掉所有 GEMINI_API_KEY* 環境變數。"""
    from src.services import app_ai_service as mod

    class _StubST:
        secrets: dict = {}
        session_state: dict = {}

    monkeypatch.setattr(mod, "st", _StubST(), raising=True)
    for name in _GEMINI_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(mod, "_gemini_rr", [0], raising=True)
    return mod


class TestGeminiCallBehaviour:

    def test_no_key_returns_warning_and_makes_no_http_call(self, ai, monkeypatch):
        fake = _FakePost([_FakeResponse(200, _ok_payload("不該被呼叫"))])
        monkeypatch.setattr(ai.requests, "post", fake, raising=True)
        out = ai.gemini_call("hi")
        assert out.startswith("⚠️ 請設定 GEMINI_API_KEY")
        assert fake.calls == [], "沒有金鑰時不該送出任何 HTTP 請求"

    def test_happy_path_returns_text_and_mock_was_called(self, ai, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "K1")
        fake = _FakePost([_FakeResponse(200, _ok_payload("報告內容"))])
        monkeypatch.setattr(ai.requests, "post", fake, raising=True)

        out = ai.gemini_call("prompt-x", max_tokens=123)

        assert out == "報告內容"
        assert fake.calls, "mock 沒被呼叫過 —— patch 目標打錯,真實跑法會去打 Gemini API"
        call = fake.calls[0]
        # 憑證只走 header,不進 URL/query(v19.170 資安修正,搬家後必須保持)
        assert call["headers"] == {"x-goog-api-key": "K1"}
        assert "K1" not in call["url"], "金鑰不得出現在 URL"
        # endpoint / payload 形狀與搬家前一致
        assert call["url"].startswith(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite")
        assert call["json"]["contents"][0]["parts"][0]["text"] == "prompt-x"
        assert call["json"]["generationConfig"]["maxOutputTokens"] == 123
        assert call["json"]["generationConfig"]["temperature"] == 0.3
        # 2.5 系列關思考模式(否則 thinking token 吃掉輸出額度)
        assert call["json"]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
        assert "systemInstruction" in call["json"], "persona 應以 systemInstruction 帶入"
        assert call["timeout"] == 120

    def test_429_switches_to_next_key(self, ai, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "K1")
        monkeypatch.setenv("GEMINI_API_KEY_2", "K2")
        fake = _FakePost([
            _FakeResponse(429, {}, text="{}"),
            _FakeResponse(200, _ok_payload("第二把成功")),
        ])
        monkeypatch.setattr(ai.requests, "post", fake, raising=True)

        out = ai.gemini_call("p")

        assert out == "第二把成功"
        assert len(fake.calls) == 2, "429 應換下一把 key 重試(做法 B 核心)"
        assert fake.calls[0]["headers"]["x-goog-api-key"] == "K1"
        assert fake.calls[1]["headers"]["x-goog-api-key"] == "K2"

    def test_round_robin_starts_from_different_key(self, ai, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "K1")
        monkeypatch.setenv("GEMINI_API_KEY_2", "K2")
        fake = _FakePost([_FakeResponse(200, _ok_payload("ok"))])
        monkeypatch.setattr(ai.requests, "post", fake, raising=True)

        ai.gemini_call("a")
        ai.gemini_call("b")

        assert len(fake.calls) == 2
        firsts = [c["headers"]["x-goog-api-key"] for c in fake.calls]
        assert firsts == ["K1", "K2"], (
            f"round-robin 起手 key 應輪替以分散額度,實際 {firsts}")

    def test_all_models_and_keys_exhausted_returns_warning(self, ai, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "K1")
        fake = _FakePost([_FakeResponse(500, {}, text="boom")])
        monkeypatch.setattr(ai.requests, "post", fake, raising=True)

        out = ai.gemini_call("p")

        assert out.startswith("⚠️ AI 服務暫時無法使用")
        # 4 個 model × 1 key,全試過才放棄
        assert len(fake.calls) == 4, f"應把 4 個 model 都試過,實際 {len(fake.calls)}"

    def test_exception_does_not_propagate(self, ai, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "K1")

        def _boom(*_a, **_k):
            raise ConnectionError("網路斷了")

        calls: list[int] = []

        def _tracked(*a, **k):
            calls.append(1)
            return _boom(*a, **k)

        monkeypatch.setattr(ai.requests, "post", _tracked, raising=True)
        out = ai.gemini_call("p")
        assert calls, "mock 沒被呼叫過"
        assert out.startswith("⚠️ AI 服務暫時無法使用")

    def test_keys_deduped_and_ordered(self, ai, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "SAME")
        monkeypatch.setenv("GEMINI_API_KEY_2", "SAME")
        monkeypatch.setenv("GEMINI_API_KEY_3", "OTHER")
        assert ai.gemini_keys() == ["SAME", "OTHER"]

    def test_get_gemini_api_key_prefers_secrets(self, ai, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "FROM_ENV")
        assert ai.get_gemini_api_key() == "FROM_ENV"
        ai.st.secrets = {"GEMINI_API_KEY": "FROM_SECRETS"}
        assert ai.get_gemini_api_key() == "FROM_SECRETS"

    def test_secrets_raising_falls_back_to_env(self, ai, monkeypatch):
        """無 secrets.toml 時 st.secrets 會 raise —— 必須降級到 env,不得炸穿。"""
        class _Raising:
            def get(self, *_a, **_k):
                raise RuntimeError("StreamlitSecretNotFoundError")

        ai.st.secrets = _Raising()
        monkeypatch.setenv("GEMINI_API_KEY", "ENVKEY")
        assert ai.get_gemini_api_key() == "ENVKEY"
        assert ai.gemini_keys() == ["ENVKEY"]


# ════════════════════════════════════════════════════════════════════
# 6. 下沉到 L0 的三個 helper:行為與 app.py 舊版一致
# ════════════════════════════════════════════════════════════════════
class TestL0Helpers:

    def test_tw_now_str_format_and_timezone(self):
        import datetime as _dt

        from shared.macro_compute import tw_now, tw_now_str
        now = tw_now()
        assert now.tzinfo is not None, "應為 tz-aware"
        assert now.utcoffset() == _dt.timedelta(hours=8), "台灣時間 UTC+8(§4.5)"
        s = tw_now_str()
        # 格式與 app.py 舊版 '%Y-%m-%d %H:%M' 一致(畫面「現在 / 上次更新」直接顯示)
        _dt.datetime.strptime(s, "%Y-%m-%d %H:%M")

    def test_get_finmind_token_never_raises(self):
        """§1 的相反面:這是**降級**不是掩蓋。

        app.py 舊版 `_get_fm_token` 沒有 try/except —— 無 `secrets.toml` 的環境
        (本機裸跑 / CI)`st.secrets.get()` 會 raise StreamlitSecretNotFoundError,
        而唯一 caller(tab_macro)是裸呼叫 → 整頁炸。下沉 L0 時補上 env fallback。
        """
        from src.config import config as cfg
        v = cfg.get_finmind_token()
        assert isinstance(v, str)

    def test_get_finmind_token_env_fallback_when_secrets_absent(self, monkeypatch):
        """secrets 拿不到時,值必須來自 os.environ。"""
        from src.config import config as cfg
        try:
            import streamlit as _st
            _secret_has = bool((getattr(_st, "secrets", None) or {}).get("FINMIND_TOKEN", ""))
        except Exception:
            _secret_has = False
        if _secret_has:
            pytest.skip("本機 secrets.toml 內含 FINMIND_TOKEN → env fallback 分支不可測")
        monkeypatch.setenv("FINMIND_TOKEN", "FM_ENV_SENTINEL")
        assert cfg.get_finmind_token() == "FM_ENV_SENTINEL"

    def test_get_finmind_token_is_exported_from_package(self):
        """tab_macro 走 `from src.config import get_finmind_token`,star-export 必須通。"""
        from src.config import get_finmind_token
        assert callable(get_finmind_token)

    def test_parse_stocks_available_from_l0(self):
        """tab_stock_grp 改吃 L0(原本走 app.py 的 re-export shim)。"""
        from shared.parse_helpers import parse_stocks
        assert parse_stocks("2330, 2454") == ["2330", "2454"]


# ════════════════════════════════════════════════════════════════════
# 8. 守衛的守衛:掃描器本身沒壞
# ════════════════════════════════════════════════════════════════════
class TestScannerHealth:

    def test_scanner_reaches_expected_files(self):
        """路徑錯 / rglob 失效會讓上面所有 AST 守衛靜默通過(假綠燈)。"""
        files = _iter_py("src", "shared", "scripts", "app.py")
        assert "app.py" in files
        assert len(files) > 200, f"只掃到 {len(files)} 個 .py,掃描器可能壞了"
        for rel in _FORMER_APP_IMPORTERS:
            assert rel in files, f"{rel} 未被掃到"

    def test_no_parse_failures(self):
        """有檔案 parse 不了 = 那個檔的守衛結果不可信,必須顯式報出來(§1)。"""
        # 先跑一次全樹,填充 _PARSE_FAILURES(其他 test 可能已跑過,重複無妨)
        for rel in _iter_py("src", "shared", "scripts", "app.py"):
            _parse(rel)
        assert not _PARSE_FAILURES, (
            "以下檔案無法 parse,本檔所有 AST 守衛對它們形同失效:\n"
            + "\n".join(f"    {m}" for m in sorted(set(_PARSE_FAILURES)))
        )


# ════════════════════════════════════════════════════════════════════
# 7. macro_fetch_orchestrator:bps_session 不再由 L5 注入
# ════════════════════════════════════════════════════════════════════
class TestOrchestratorBuildsItsOwnSession:

    def test_bps_session_is_optional(self):
        import inspect

        from src.services.macro_fetch_orchestrator import fetch_macro_bundle
        sig = inspect.signature(fetch_macro_bundle)
        p = sig.parameters["bps_session"]
        assert p.default is None, (
            "bps_session 應可省略(預設 None → L3 自行向 L1 取),"
            "否則 tab_macro 還是得自己造 session")

    def test_tab_macro_no_longer_passes_bps_session(self):
        """AST:tab_macro 呼叫 fetch_macro_bundle 時不得再帶 bps_session。"""
        tree, lines = _parse("src/ui/tabs/tab_macro.py")
        bad = []
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            fname = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            if fname != "fetch_macro_bundle":
                continue
            for kw in n.keywords:
                if kw.arg == "bps_session":
                    bad.append(n)
        assert not bad, (
            "tab_macro 仍在注入 bps_session:\n"
            + "\n".join(f"    tab_macro.py:{n.lineno}: {_line(lines, n.lineno)}"
                        for n in bad))
