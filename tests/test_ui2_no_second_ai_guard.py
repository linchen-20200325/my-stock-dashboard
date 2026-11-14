"""Issue #1138 B 線（tests-only）— New UI2 「不得有第二個 AI／自帶網路通道」守衛（fast lane）。

═══ 守什麼 ═══════════════════════════════════════════════════════════
New UI2 的四個範圍（L0 `shared/ui2_contract`、L3 `src/services/ui2`、L5 `src/ui2`、L6 `app_ui2.py`）
只能**呈現**既有 canonical 結果，不得自己叫 LLM、不得自己開網路連線、不得繞路呼叫專案既有的 AI 模組
（OneBrain：決策只有一個大腦；UI2 若偷接第二個 AI，畫面上的判讀就不再可追溯到 Digest／Evidence）。

AST 掃描（含 `importlib.import_module("…")`／`__import__("…")` 的字串形式）禁止：
- LLM SDK：google.generativeai、google.genai、google.ai、vertexai、openai、anthropic、langchain*、litellm；
- 網路客戶端：httpx、aiohttp、urllib*（含 urllib3）、http.client、socket、requests；
- 專案 AI 模組（以模組路徑**任一段**比對，含 `import ai_fetcher` 這類非 `src.` 前綴的繞路寫法）：
  ai_fetcher、app_ai_service、ai_qa_service、ai_structured_summary；
- LLM 端點字串：generativelanguage.googleapis.com、api.openai.com、api.anthropic.com 等。

═══ 與既有守衛的關係（2026-11-14 實查 `tests/test_ui2_guards.py`；本檔不改它一個字）═══
既有守衛**部分**涵蓋，但沒有一支涵蓋上述全部組合：
- G2（L0＋L3 純 VM 檔）：已禁 requests／socket／urllib／http，且專案內只准 `shared`／`src.services.ui2`
  ⇒ `src.services.ai_*` 已被擋；但**未**列 openai／anthropic／google.genai／vertexai／langchain／litellm／
  httpx／aiohttp／urllib3 等第三方套件，也不掃端點字串。
- G2F（`real_feed.py`）：精確 import 白名單，該檔已涵蓋上述全部 import（本檔對它是重疊的縱深防禦）；不掃端點字串。
- G4／G4b（L5＋L6）：只禁 Legacy UI／app 與非 `src.services.ui2` 的 `src.services.*`／`src.data`／`src.compute`；
  **未**禁任何第三方 LLM SDK 或網路客戶端，也不擋 `import ai_fetcher` 這種非 `src.` 路徑。
- G9（L5＋L6）：`_generic_bans` 已禁 `importlib`／`__import__` 名稱本身（故動態 import 已被擋；本檔的字串形式
  偵測與之重疊，保留是為了讓「禁哪些模組」在本檔自成一份完整清單）。
⇒ 本檔新增的實質涵蓋：**L5／L6 與純 VM 檔的第三方 LLM SDK、L5／L6 的網路客戶端、純 VM 檔的 httpx／aiohttp／urllib3、
所有範圍的 LLM 端點字串、以及非 `src.` 路徑的專案 AI 模組**。與既有守衛重疊的格子保留，屬縱深防禦（不放寬任何既有守衛）。

⚠️ AST 守衛是 defense-in-depth、**非窮舉**（例如經由允許的 canonical service 間接呼叫 AI 不在本檔範圍；
那由 G2F 精確白名單＋c3 分層守衛負責）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCAN_DIRS = (ROOT / "shared" / "ui2_contract", ROOT / "src" / "services" / "ui2", ROOT / "src" / "ui2")
L6_FILE = ROOT / "app_ui2.py"


def _py(d: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in d.rglob("*.py") if "__pycache__" not in p.parts)


SCAN_FILES = [p for d in SCAN_DIRS for p in _py(d)] + [L6_FILE]

#: 以「完整模組路徑」比對（等於或為其子模組）。
BANNED_MODULE_PREFIXES = (
    # LLM SDK
    "google.generativeai", "google.genai", "google.ai", "vertexai", "openai", "anthropic", "litellm",
    # 網路客戶端
    "httpx", "aiohttp", "http.client", "socket", "requests",
)
#: 以「頂層套件名開頭」比對（家族：langchain／langchain_openai／langchain_core…；urllib／urllib3）。
BANNED_TOPLEVEL_STARTSWITH = ("langchain", "urllib")
#: 專案 AI 模組：模組路徑**任一段**等於這些名稱即違規（`src.services.ai_fetcher`、`from src.services import
#: ai_fetcher`、`import ai_fetcher` 皆中）。
BANNED_PROJECT_AI_MODULES = ("ai_fetcher", "app_ai_service", "ai_qa_service", "ai_structured_summary")
#: LLM 端點字串（任何字串常數內出現即違規，含 f-string 的常數片段）。
BANNED_ENDPOINT_SUBSTRINGS = (
    "generativelanguage.googleapis.com", "aiplatform.googleapis.com", "api.openai.com", "api.anthropic.com",
)
_DYNAMIC_IMPORT_FUNCS = {"import_module", "__import__"}


def _module_banned(mod: str) -> bool:
    if any(mod == b or mod.startswith(b + ".") for b in BANNED_MODULE_PREFIXES):
        return True
    parts = mod.split(".")
    if any(parts[0].startswith(b) for b in BANNED_TOPLEVEL_STARTSWITH):
        return True
    return any(p in BANNED_PROJECT_AI_MODULES for p in parts)


def _imported_modules(n: ast.AST) -> list[str]:
    if isinstance(n, ast.Import):
        return [a.name for a in n.names]
    if isinstance(n, ast.ImportFrom):
        base = n.module or ""
        # 相對 import（level>0）也收：`from .ai_fetcher import x`／`from . import ai_fetcher`
        return ([base] if base else []) + [f"{base}.{a.name}" if base else a.name for a in n.names]
    if isinstance(n, ast.Call):
        f = n.func
        name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
        if name in _DYNAMIC_IMPORT_FUNCS:
            return [a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return []


def scan_no_second_ai(source: str) -> list[str]:
    """純函式：回傳違規清單（空＝合規）。同一支掃描器既掃真檔，也掃刻意注入違規的假原始碼（見 teeth 測試）。"""
    bad: list[str] = []
    for n in ast.walk(ast.parse(source)):
        for mod in _imported_modules(n):
            if _module_banned(mod):
                bad.append(f"L{n.lineno}: 禁止 import {mod}")
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            hit = [s for s in BANNED_ENDPOINT_SUBSTRINGS if s in n.value]
            if hit:
                bad.append(f"L{n.lineno}: 禁止 LLM 端點字串 {hit}")
    return bad


# ════════════════════════════════════════════════════════════════════
# 真檔：四個範圍必須 0 違規
# ════════════════════════════════════════════════════════════════════
def test_scan_scope_is_the_four_ui2_ranges_and_not_empty():
    assert L6_FILE.exists()
    for d in SCAN_DIRS:
        assert d.is_dir() and _py(d), f"範圍不存在或沒有 .py：{d}"
    assert len(SCAN_FILES) == len(set(SCAN_FILES))


@pytest.mark.parametrize("path", SCAN_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_ui2_has_no_second_ai_or_network_channel(path):
    assert scan_no_second_ai(path.read_text(encoding="utf-8")) == []


# ════════════════════════════════════════════════════════════════════
# 牙齒：注入違規的假原始碼必須被抓到（拔掉守衛邏輯 ⇒ 這裡轉紅）
# ════════════════════════════════════════════════════════════════════
_CLEAN_SAMPLE = ROOT / "src" / "ui2" / "views" / "market.py"


def _injections() -> list[str]:
    out: list[str] = []
    for b in BANNED_MODULE_PREFIXES:                           # 由清單推導，不寫死數量
        out.append(f"import {b}\n")
        head, _, tail = b.rpartition(".")
        if head:
            out.append(f"from {head} import {tail}\n")
        out.append(f"import importlib\nm = importlib.import_module({b!r})\n")
        out.append(f"m = __import__({b!r})\n")
    for name in BANNED_PROJECT_AI_MODULES:
        out += [f"import src.services.{name}\n", f"from src.services import {name}\n",
                f"from src.services.{name} import x\n", f"import {name}\n", f"from . import {name}\n",
                f"import importlib\nm = importlib.import_module('src.services.{name}')\n"]
    for host in BANNED_ENDPOINT_SUBSTRINGS:
        out += [f"u = 'https://{host}/v1/x'\n", f"u = f'https://{host}/v1/{{k}}'\n"]
    out += ["import langchain\n", "from langchain_openai import ChatOpenAI\n", "import langchain_core.messages\n",
            "import urllib.request\n", "import urllib3\n", "from urllib.parse import quote\n",
            "from openai import OpenAI\n", "from anthropic import Anthropic\n", "import google.generativeai as genai\n",
            "from google import genai\n", "from http import client\n", "from vertexai.generative_models import M\n"]
    return out


@pytest.mark.parametrize("injected", _injections())
def test_scanner_has_teeth(injected):
    clean = _CLEAN_SAMPLE.read_text(encoding="utf-8")
    assert scan_no_second_ai(clean) == []
    assert scan_no_second_ai(injected + clean), f"沒抓到：{injected!r}"


@pytest.mark.parametrize("benign", [
    "import google.protobuf\n", "import http.cookies\n", "import requests_like_name_but_not_requests\n",
    "from shared.ui2_contract import text\n", "import socketserver_helper_x\n", "x = 'ai_fetcher'\n",
    "u = 'https://example.com/openai'\n",
])
def test_scanner_does_not_flag_unrelated_names(benign):
    """比對以模組路徑分段為準，不做子字串比對（避免誤傷；誤傷會逼人放寬守衛）。"""
    assert scan_no_second_ai(benign) == []
