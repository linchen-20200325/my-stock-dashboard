"""C3 — CLAUDE.md §8.2 五條分層硬規則的機器化守衛。

為什麼需要這個檔
────────────────
§8.2 定了 7 層架構 + 5 條硬規則,但 `tests/` 過去一條 layering guard 都沒有,
全靠人工盤點 → 文件必然漂移。實測(v19.180 C3):
  * §8.2.A EX-PASSTHRU-1 prose 說「25+ 處」,實際 58 處,行號 100% 過期
  * EX-CACHE-1 prose 說「9 處」,實際 22 處
本檔把例外清單改成**機器可讀 SSOT**;CLAUDE.md prose 只負責解釋「為什麼」,
「有哪些」以本檔 `_WHITELIST` 為準。

設計要點(踩過的坑,勿回退)
──────────────────────────
1. **用 AST,不用字串比對。** docstring / 註解裡大量出現 `from src.data...`
   (shared/** 幾乎每個檔都在註解裡寫來源出處),字串掃描會產生假紅燈。
   `ast` 只會看到真的 import 節點。
2. **走訪巢狀 import。** 本專案大量用 late import(button click / 避循環 import),
   例如 `src/ui/tabs/tab_macro.py` 的 `from app import ...` 藏在 render 函式裡。
   所以用 `ast.walk()` 掃全樹,不是只看 `tree.body`。
3. **展開 PEP 562 barrel 轉發。** `src/data/proxy/__init__.py` 用 `__getattr__`
   把 `proxy_helper` 的符號轉出來,所以
       from src.data.proxy import fetch_url     # ← 這其實就是 proxy_helper
   天真 grep `import proxy_helper` 掃不到。本檔先建「符號 → 定義模組」映射表
   (`_barrel_exports`),規則 2 才判得出 `src/compute/risk/risk_radar.py` 的違憲。
4. **白名單不用行號。** 行號一定會過期(CLAUDE.md 已經全錯)。
   key = (規則, 檔案路徑, 被 import 的模組)。
5. **反向守衛。** 白名單/待修清單裡「現在已經不違憲」的項目會讓測試紅,
   提示移出。否則清單只會越長 —— 這正是目前 CLAUDE.md 的病。

用法
────
    pytest tests/test_c3_layering_guard.py -v

基線漂移時(改了 import 結構之後),直接產生可貼上的新基線:

    python tests/test_c3_layering_guard.py

會把目前實際掃到的 `_WHITELIST` / `_KNOWN_VIOLATIONS` 條目印出來。
**注意**:貼上前先確認每一條是「合法例外」還是「真違憲」,不要無腦覆蓋。
"""

from __future__ import annotations

import ast
import os
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# ── 層級定義 ────────────────────────────────────────────────────────
L0, L1, L2, L3, L4, L5, L6 = 0, 1, 2, 3, 4, 5, 6

LAYER_NAMES = {
    L0: "L0 Infra", L1: "L1 Data", L2: "L2 Compute", L3: "L3 Service",
    L4: "L4 Render", L5: "L5 UI Tabs", L6: "L6 App",
}

# 檔案路徑 → 層(most-specific-first;順序有意義)
_PATH_LAYERS: tuple[tuple[str, int], ...] = (
    ("shared/", L0),
    ("src/config/", L0),
    ("src/data/", L1),
    ("scripts/", L1),
    ("src/compute/", L2),
    ("src/services/", L3),
    ("src/ui/render/", L4),
    ("src/ui/tabs/", L5),
    ("src/ui/etf/", L5),
    ("src/ui/pages/", L5),
)

# 被 import 的模組路徑 → 層(most-specific-first;順序有意義)
_MODULE_LAYERS: tuple[tuple[str, int], ...] = (
    ("shared", L0),
    ("src.config", L0),
    ("src.data", L1),
    ("scripts", L1),
    ("src.compute", L2),
    ("src.services", L3),
    ("src.ui.render", L4),
    ("src.ui.tabs", L5),
    ("src.ui.etf", L5),
    ("src.ui.pages", L5),
    ("src.ui", L5),          # 兜底:未知的 src.ui.* 視為 L5
    ("app", L6),
)

# 只掃這幾個 root — 其餘(infra/、mcp_server/、tests/)未納入 §8.2 分層
_SCAN_ROOTS = ("shared", "src", "scripts")
_SCAN_FILES = ("app.py",)
_SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules",
              "build", "dist", ".mypy_cache", ".pytest_cache"}

# 規則 2 字面點名禁止的模組
_BANNED_IN_L2 = ("requests", "yfinance", "FinMind", "proxy_helper")


# ── AST 掃描 ────────────────────────────────────────────────────────
class ImportRecord:
    """一筆 import。`target` 是解析後的絕對模組路徑。"""

    __slots__ = ("relpath", "lineno", "source", "target", "names", "func")

    def __init__(self, relpath: str, lineno: int, source: str,
                 target: str, names: tuple[str, ...], func: str | None):
        self.relpath = relpath
        self.lineno = lineno
        self.source = source
        self.target = target
        self.names = names
        self.func = func

    @property
    def key(self) -> tuple[str, str]:
        return (self.relpath, self.target)

    def evidence(self) -> str:
        where = f" (在函式 {self.func} 內)" if self.func else ""
        return f"    {self.relpath}:{self.lineno}: {self.source}{where}"


def _iter_py_files() -> list[Path]:
    out: list[Path] = []
    for root_name in _SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".py"):
                    out.append(Path(dirpath) / fn)
    for fn in _SCAN_FILES:
        p = REPO_ROOT / fn
        if p.is_file():
            out.append(p)
    return sorted(out)


def _relpath(p: Path) -> str:
    return p.relative_to(REPO_ROOT).as_posix()


def _module_of_file(relpath: str) -> str:
    """`src/data/proxy/proxy_helper.py` → `src.data.proxy.proxy_helper`"""
    parts = relpath[:-3].split("/")          # 去掉 .py
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package_of_file(relpath: str) -> str:
    """相對 import 的 anchor package。"""
    parts = relpath[:-3].split("/")
    return ".".join(parts[:-1])              # __init__.py 與一般檔案同解


def _layer_of_file(relpath: str) -> int | None:
    if relpath == "app.py":
        return L6
    for prefix, layer in _PATH_LAYERS:
        if relpath.startswith(prefix):
            return layer
    return None


def _layer_of_module(module: str) -> int | None:
    if not module:
        return None
    for prefix, layer in _MODULE_LAYERS:
        if module == prefix or module.startswith(prefix + "."):
            return layer
    return None


def _resolve_relative(relpath: str, node: ast.ImportFrom) -> str:
    """把 `from .x import y` / `from ..x import y` 解析成絕對模組路徑。"""
    pkg_parts = _package_of_file(relpath).split(".") if _package_of_file(relpath) else []
    if node.level > 1:
        pkg_parts = pkg_parts[: len(pkg_parts) - (node.level - 1)]
    if node.module:
        pkg_parts = pkg_parts + node.module.split(".")
    return ".".join(pkg_parts)


def _scan_file(path: Path) -> list[ImportRecord]:
    relpath = _relpath(path)
    try:
        src = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    lines = src.splitlines()

    # node → 最近的 enclosing function 名稱(用來標示 late import)
    enclosing: dict[int, str] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(fn):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    # 取最內層(後蓋前;ast.walk 由外而內,故內層最後寫入)
                    enclosing[id(sub)] = fn.name

    out: list[ImportRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(ImportRecord(
                    relpath, node.lineno,
                    lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                    alias.name, (alias.asname or alias.name,),
                    enclosing.get(id(node)),
                ))
        elif isinstance(node, ast.ImportFrom):
            target = (_resolve_relative(relpath, node) if node.level
                      else (node.module or ""))
            out.append(ImportRecord(
                relpath, node.lineno,
                lines[node.lineno - 1].strip() if node.lineno <= len(lines) else "",
                target, tuple(a.name for a in node.names),
                enclosing.get(id(node)),
            ))
    return out


# ── PEP 562 barrel 展開 ─────────────────────────────────────────────
def _module_file(module: str) -> Path | None:
    base = REPO_ROOT / Path(*module.split("."))
    for cand in (base / "__init__.py", base.with_suffix(".py")):
        if cand.is_file():
            return cand
    return None


def _toplevel_names(module: str) -> list[str]:
    """近似 `vars(mod)`:top-level def / class / 賦值 / import 進來的名字。

    有 `__all__` 時以 `__all__` 為準(star import 語意)。
    """
    f = _module_file(module)
    if f is None:
        return []
    try:
        tree = ast.parse(f.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    dunder_all: list[str] | None = None
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.append(tgt.id)
                    if tgt.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                        dunder_all = [e.value for e in node.value.elts
                                      if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, ast.Import):
            names.extend(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.extend(a.asname or a.name for a in node.names if a.name != "*")
    return dunder_all if dunder_all is not None else names


def _barrel_exports(pkg: str) -> dict[str, str]:
    """package 的「符號 → 定義它的 submodule」映射。

    處理本專案實際存在的三種 barrel 寫法:
      (a) PEP 562:`from . import a, b` + `_SUBMODULES = (a, b)` + `__getattr__`
          → a、b 的 top-level 名字全部轉發,依 `_SUBMODULES` 順序 first-match-wins
            (與 runtime `for sub in _SUBMODULES: if name in vars(sub)` 一致)
      (b) 顯式 re-export:`from .sub import x`
      (c) star:`from .sub import *`
    """
    f = _module_file(pkg)
    if f is None or f.name != "__init__.py":
        return {}
    try:
        tree = ast.parse(f.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {}

    exports: dict[str, str] = {}
    plain_submods: list[str] = []       # `from . import a, b` 的順序
    declared_order: list[str] | None = None
    has_getattr = False

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__":
            has_getattr = True
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Name) and tgt.id == "_SUBMODULES"
                        and isinstance(node.value, (ast.Tuple, ast.List))):
                    declared_order = [e.id for e in node.value.elts
                                      if isinstance(e, ast.Name)]
        elif isinstance(node, ast.ImportFrom) and node.level == 1:
            if node.module is None:
                # `from . import a, b` — submodule 本身也是 package 的公開名字
                for a in node.names:
                    plain_submods.append(a.name)
                    exports.setdefault(a.asname or a.name, f"{pkg}.{a.name}")
            else:
                sub = f"{pkg}.{node.module}"
                for a in node.names:
                    if a.name == "*":
                        for n in _toplevel_names(sub):
                            exports.setdefault(n, sub)
                    else:
                        exports.setdefault(a.asname or a.name, sub)

    if has_getattr:
        order = declared_order or plain_submods
        for sub_name in order:
            sub = f"{pkg}.{sub_name}"
            for n in _toplevel_names(sub):
                exports.setdefault(n, sub)      # first-match-wins,同 runtime
    return exports


_BARREL_CACHE: dict[str, dict[str, str]] = {}


def _resolve_symbol(module: str, symbol: str) -> str:
    """`from <module> import <symbol>` 實際命中的模組。

    非 barrel / 找不到 → 回傳 module 本身。
    """
    if module not in _BARREL_CACHE:
        _BARREL_CACHE[module] = _barrel_exports(module)
    return _BARREL_CACHE[module].get(symbol, module)


def _touches_banned_module(rec: ImportRecord) -> str | None:
    """規則 2:這筆 import 有沒有碰到被點名禁止的模組?回傳命中的模組名。"""
    segs = rec.target.split(".")
    for banned in _BANNED_IN_L2:
        if banned in segs:
            return banned
    # barrel 轉發:`from src.data.proxy import fetch_url` → proxy_helper
    if rec.target.startswith("src."):
        for name in rec.names:
            resolved = _resolve_symbol(rec.target, name)
            for banned in _BANNED_IN_L2:
                if banned in resolved.split("."):
                    return banned
    return None


# ── 掃描結果(module-level,只算一次)──────────────────────────────
def _scan_all() -> list[ImportRecord]:
    out: list[ImportRecord] = []
    for p in _iter_py_files():
        out.extend(_scan_file(p))
    return out


_ALL_IMPORTS = _scan_all()


def _by_key(records: list[ImportRecord]) -> dict[tuple[str, str], list[ImportRecord]]:
    grouped: dict[tuple[str, str], list[ImportRecord]] = defaultdict(list)
    for r in records:
        grouped[r.key].append(r)
    return grouped


# ════════════════════════════════════════════════════════════════════
# 例外白名單 —— 對應 CLAUDE.md §8.2.A 的四個 EX-ID
#
# key   = (規則 id, 檔案相對路徑, 被 import 的模組)      ← 刻意不含行號
# value = (EX-ID, 理由)
#
# ⚠️ 新增條目必須同時:(1) 加在這裡並寫理由、(2) 在 CLAUDE.md §8.2.A 對應
#    EX-ID 底下說明、(3) PR 描述附理由。
# ⚠️ 已經不違憲的條目會被 `test_*_whitelist_not_stale` 抓出來,請移除。
# ════════════════════════════════════════════════════════════════════
EX_L0_1 = "EX-L0-1"
EX_CACHE_1 = "EX-CACHE-1"
EX_OAUTH_1 = "EX-OAUTH-1"
EX_PASSTHRU_1 = "EX-PASSTHRU-1"

_R_CACHE = ("條件 import streamlit,只用 @st.cache_data / @st.cache_resource / "
            "st.secrets,無 st.session_state / st.error 等真 UI 呼叫。"
            "Streamlit Cloud cache 是部署架構核心,functools.lru_cache 不等價。")

_WHITELIST: dict[tuple[str, str, str], tuple[str, str]] = {}

# ── EX-L0-1:L0 條件 import streamlit ───────────────────────────────
_WHITELIST[("R1-L0", "src/config/config.py", "streamlit")] = (
    EX_L0_1,
    "限於 st.secrets bootstrap 讀 FINMIND_TOKEN;try/except 已護純 .py 環境,"
    "無 UI lifecycle 依賴。改走 L3 會打破所有 caller 介面,ROI 低。",
)

# ── EX-CACHE-1:L1 條件 import streamlit(cache / secrets only)──────
for _f in (
    "src/data/core/data_loader.py",
    "src/data/core/financial_statements_fetcher.py",
    "src/data/daily/daily_data_fetchers.py",
    "src/data/etf/etf_fetch.py",
    "src/data/macro/foreign_flow_fetcher.py",
    "src/data/macro/leading_indicators.py",
    "src/data/macro/macro_snapshot.py",
    "src/data/news/news_fetcher.py",
    "src/data/proxy/yf_proxy.py",
    "src/data/stock/app_stock_fetchers.py",
    "src/data/stock/chip_concentration_fetcher.py",
    "src/data/stock/dividend_fetcher.py",
    "src/data/stock/fundamentals_snapshot_loader.py",
    "src/data/stock/monthly_revenue_fetcher.py",
    "src/data/stock/quarterly_financials_fetcher.py",
    "src/data/stock/share_capital_fetcher.py",
    "src/data/stock/tw_stock_data_fetcher.py",
):
    _WHITELIST[("R1", _f, "streamlit")] = (EX_CACHE_1, _R_CACHE)

# 同 EX-CACHE-1,但 except 子句用 `Exception` 而非 `ImportError`(語意等價)
_WHITELIST[("R1", "src/data/macro/macro_alert.py", "streamlit")] = (
    EX_CACHE_1, _R_CACHE + " 本檔用 _safe_cache() inline 函式內 late import。")
_WHITELIST[("R1", "src/data/proxy/proxy_helper.py", "streamlit")] = (
    EX_CACHE_1, _R_CACHE + " 本檔僅在 get_proxy_config/get_nas_relay 內讀 st.secrets。")
_WHITELIST[("R1", "src/data/macro/leading_indicators.py", "streamlit.runtime.scriptrunner")] = (
    EX_CACHE_1,
    "get_script_run_ctx 是 cache 機制的 runtime-context 偵測(判斷是否在 "
    "script run 內),非 UI 呼叫;包在 try/except 內。同 EX-CACHE-1 精神。",
)

# ── EX-OAUTH-1:L1 含 OAuth callback 的真 UI 呼叫 ───────────────────
_WHITELIST[("R1", "src/data/portfolio/oauth_state.py", "streamlit")] = (
    EX_OAUTH_1,
    "OAuth callback middleware 本質(?code= exchange → token → flash → rerun),"
    "類比 web framework session lifecycle。用 st.session_state/query_params/"
    "success/error/rerun。拆 L5+L1 會打破現有 OAuth 流程,ROI 低。",
)
_WHITELIST[("R1", "src/data/portfolio/gsheet_portfolio.py", "streamlit")] = (
    EX_OAUTH_1,
    "讀 st.session_state 取 gsheet_tokens / portfolio_sheet_id,同屬 OAuth "
    "session lifecycle(token 取用)。caller 注入 token 會打破現有 OAuth flow。"
    "註:fallback 是 `st = None` 而非 _NoOpST,故不適用 EX-CACHE-1。",
)

# ── EX-PASSTHRU-1:L4/L5/L6 直呼 L1 fetcher(pass-through,無 L3 業務值)──
_R_PASSTHRU = (
    "pass-through 直呼 L1 fetcher。§8.2「cache 才能集中」的理由在此失效:"
    "L1 模組內已用 @st.cache_data(EX-CACHE-1)集中緩存,加 L3 wrapper 只是 "
    "pure pass-through = §8.1 step 6「用不到的抽象」。多數為 button click / "
    "on-demand 的 lazy import,延遲 import 避免 module load 時跑全 dependency chain。"
    "升級觸發:若需跨多 fetcher 統一 TTL / 多源 fallback chain / 結果後處理 → 升 L3。"
)
for _f, _m in (
    # ── L6 App ──
    ("app.py", "src.data.stock"),
    ("app.py", "src.data.stock.app_stock_fetchers"),
    ("app.py", "src.data.portfolio.oauth_state"),
    # ── L5 UI Tabs ──
    ("src/ui/tabs/chip_radar.py", "src.data.stock.chip_concentration_fetcher"),
    ("src/ui/tabs/hot_money.py", "src.data.macro.foreign_flow_fetcher"),
    ("src/ui/tabs/macro/handlers.py", "src.data.proxy"),
    ("src/ui/tabs/macro/section_chips.py", "src.data.macro"),
    ("src/ui/tabs/macro/section_mid.py", "src.data.macro"),
    ("src/ui/tabs/macro/section_news_ai.py", "src.data.news"),
    ("src/ui/tabs/macro/section_short.py", "src.data.macro"),
    ("src/ui/tabs/macro/section_state.py", "src.data.macro"),
    ("src/ui/tabs/pattern_targets_ui.py", "src.data.stock.picker_fetcher"),
    ("src/ui/tabs/stock_grp_sections/section_batch_fetcher.py", "src.data.core"),
    ("src/ui/tabs/stock_grp_sections/section_batch_fetcher.py", "src.data.stock.app_stock_fetchers"),
    ("src/ui/tabs/stock_grp_sections/section_portfolio_summary.py", "src.data.news"),
    ("src/ui/tabs/stock_grp_sections/section_portfolio_summary.py", "src.data.stock.app_stock_fetchers"),
    ("src/ui/tabs/stock_sections/section_357_valuation.py", "src.data.core"),
    ("src/ui/tabs/stock_sections/section_357_valuation.py", "src.data.core.provenance"),
    ("src/ui/tabs/stock_sections/section_when_buy_sell.py", "src.data.news"),
    ("src/ui/tabs/tab_edu.py", "src.data.core"),
    ("src/ui/tabs/tab_edu.py", "src.data.macro.macro_core"),
    ("src/ui/tabs/tab_edu.py", "src.data.proxy"),
    ("src/ui/tabs/tab_macro.py", "src.data.macro"),
    ("src/ui/tabs/tab_macro.py", "src.data.news"),
    ("src/ui/tabs/tab_stock.py", "src.data.core"),
    ("src/ui/tabs/tab_stock.py", "src.data.news"),
    ("src/ui/tabs/tab_stock.py", "src.data.stock"),
    ("src/ui/tabs/tab_stock.py", "src.data.stock.app_stock_fetchers"),
    ("src/ui/tabs/tab_stock.py", "src.data.stock.share_capital_fetcher"),
    ("src/ui/tabs/tab_stock_grp.py", "src.data.portfolio"),
    ("src/ui/tabs/tab_stock_grp.py", "src.data.portfolio.oauth_state"),
    ("src/ui/tabs/tab_stock_grp.py", "src.data.stock.picker_fetcher"),
    ("src/ui/tabs/tab_stock_picker.py", "src.data.core"),
    ("src/ui/tabs/tab_stock_picker.py", "src.data.core.data_loader"),
    ("src/ui/tabs/tab_stock_picker.py", "src.data.core.provenance"),
    ("src/ui/tabs/tab_stock_picker.py", "src.data.etf"),
    ("src/ui/tabs/tab_stock_picker.py", "src.data.proxy"),
    ("src/ui/tabs/tab_stock_picker.py", "src.data.stock.picker_fetcher"),
    # ── L5 UI ETF ──
    ("src/ui/etf/etf_dashboard.py", "src.data.etf"),
    ("src/ui/etf/etf_tab_grp_compare.py", "src.data.core.provenance"),
    ("src/ui/etf/etf_tab_grp_compare.py", "src.data.etf"),
    ("src/ui/etf/etf_tab_portfolio.py", "src.data.etf.etf_fetch"),
    ("src/ui/etf/etf_tab_portfolio.py", "src.data.macro"),
    ("src/ui/etf/etf_tab_portfolio.py", "src.data.portfolio"),
    ("src/ui/etf/etf_tab_portfolio.py", "src.data.portfolio.oauth_state"),
    ("src/ui/etf/etf_tab_single.py", "src.data.etf"),
    ("src/ui/etf/etf_tab_single.py", "src.data.etf.etf_fetch"),
    ("src/ui/etf/etf_tab_smart.py", "src.data.etf"),
    ("src/ui/etf/etf_tab_smart.py", "src.data.etf.etf_fetch"),
    # ── L5 UI Pages ──
    ("src/ui/pages/api_diagnostic.py", "src.data.proxy"),
    ("src/ui/pages/health_inspector.py", "src.data.etf"),
    ("src/ui/pages/health_inspector.py", "src.data.etf.etf_fetch"),
    ("src/ui/pages/health_inspector.py", "src.data.macro"),
    ("src/ui/pages/health_inspector.py", "src.data.proxy"),
    # ── L4 Render lazy fallback ──
    # §8.2 硬規則只點名 L5/L6,但 §8.2.A 已登記 L4 Render 的 lazy fallback,
    # 故規則 4 的掃描範圍含 L4(否則此白名單條目會被反向守衛誤判為過期)。
    ("src/ui/render/app_render.py", "src.data.macro"),
    ("src/ui/render/etf_render.py", "src.data.etf"),
    ("src/ui/render/macro_ui_components.py", "src.data.macro.macro_alert"),
):
    _WHITELIST[("R4", _f, _m)] = (EX_PASSTHRU_1, _R_PASSTHRU)


# ════════════════════════════════════════════════════════════════════
# 待修清單 —— 真違憲,尚未收斂
#
# 這些**不是**合法例外,是已知技術債。列在這裡是為了讓守衛可以先 merge,
# 違憲再逐條收斂。每條都標 TODO + 為什麼還沒修。
# ⚠️ 修好之後 `test_*_known_violations_not_stale` 會紅,提示移出本清單。
# ════════════════════════════════════════════════════════════════════
_TODO_SCRIPTS_LAYER = (
    "TODO(C3-a):`scripts/**` 在 §8.2 被歸為 L1 Data,但這些檔其實是 cron / CLI "
    "entrypoint(orchestrator),職責等同 L6 App,呼叫 L2/L3 是設計本意而非違憲。"
    "未修原因:正解可能是**改 CLAUDE.md 的分層標籤**(把 CLI entrypoint 獨立成一層 / "
    "歸 L6),而不是改這些 script。屬 C2 文件修訂範圍,需 user 裁示,不自行決定。"
)

_KNOWN_VIOLATIONS: dict[tuple[str, str, str], str] = {}

# ── 規則 2:L2 Compute 經 barrel 轉發碰到 proxy_helper ───────────────
_KNOWN_VIOLATIONS[("R2", "src/compute/risk/risk_radar.py", "src.data.proxy")] = (
    "TODO(C3-b):`from src.data.proxy import fetch_url` 經 PEP 562 barrel 轉發,"
    "實際命中 proxy_helper → 規則 2 字面禁止。L2 純函式層不該有 HTTP I/O。"
    "未修原因:_fetch_cboe_csv 是 risk_radar 的多源 fallback,要修得把 CBOE CSV "
    "抓取下沉到 L1(如 src/data/macro/),屬跨層重構,需 §8.1 架構先行提案。"
)

# ── 規則 5:cron 腳本從 L5 UI Tab 取數 ──────────────────────────────
# ⚠️ 這兩條**不適用**「scripts 是 entrypoint,往下呼叫任何層都是設計本意」的判斷。
# 就算 scripts/** 等同 L6 orchestrator,去 **UI 層**取數仍然是錯的方向。
_C3_YIELD_SCREENER_TODO = (
    "TODO(C3-d):cron 從 L5 UI Tab import L1 fetcher。根因不在 scripts —— 是 "
    "`fetch_pe_name_maps` / `fetch_twse_yield_pe` / `fetch_tpex_yield_pe` 這三個 "
    "L1 fetcher 住在 `src/ui/tabs/yield_screener.py`(該檔 :14 module-level "
    "`import streamlit as st`)。實務風險:headless cron 走這條 import 會把整個 "
    "streamlit UI 鏈拉進來;`update_forward_test_freeze.py` 正是每月凍結前進式驗證的"
    "那支,import 鏈一斷紀錄就靜默停止更新,而那是本專案唯一的誠實績效量測。"
    "另兩個同源 caller:`app.py`(L6)、`mcp_server/server.py`。"
    "正解:三個 fetcher 下沉 L1(如 `src/data/stock/yield_pe_fetcher.py`,走 "
    "EX-CACHE-1 條件 import),`yield_screener.py` 保留 re-export 供 UI 與既有測試。"
    "⚠️ 搬遷會動到 `tests/test_b6b_screener_audit.py` 的 "
    "`patch.object(ys, 'fetch_tpex_yield_pe')` —— patch 目標要跟著改到 L1 模組,"
    "否則 `fetch_pe_name_maps` 內部呼叫的是 L1 的真函式、patch 打不到。"
    "未修原因:動到凍結路徑,需單獨一批 + 完整跑測試驗證,不與本批混做。"
)
_KNOWN_VIOLATIONS[("R5", "scripts/push_daily_signals.py", "src.ui.tabs.yield_screener")] = (
    _C3_YIELD_SCREENER_TODO)
_KNOWN_VIOLATIONS[("R5", "scripts/update_forward_test_freeze.py", "src.ui.tabs.yield_screener")] = (
    _C3_YIELD_SCREENER_TODO)

# ── 規則 3:L0 Infra 依賴 L1 ────────────────────────────────────────
_KNOWN_VIOLATIONS[("R3", "src/config/stock_names.py", "src.data.core.stock_names_fetcher")] = (
    "TODO(C3-c):L0 的 get_stock_name / refresh_name_cache 內 lazy import L1 fetcher "
    "(2 處:函式內 late import,避免 L0 啟動時就拉 requests)。"
    "未修原因:L0 被全層 import,要修得把 get_stock_name 整個上移到 L1/L3,"
    "會打破所有 caller 介面。需 §8.1 架構先行提案決定搬遷範圍。"
)

# ── 規則 4:L5 UI 直呼 scripts/(CLI entrypoint)─────────────────────
_KNOWN_VIOLATIONS[("R4", "src/ui/pages/calibration_ui.py", "scripts.calibrate_macro_traffic")] = (
    "TODO(C3-a2):L5 校準頁直接 import cron CLI 腳本的內部函式。"
    "不列入 EX-PASSTHRU-1 —— 那條例外的前提是「L1 fetcher 且 L1 內已有 cache」,"
    "本例 import 的是 CLI 腳本邏輯,不是 fetcher。正解是把校準演算法下沉 L2,"
    "UI 與 CLI 共用。與 " + _TODO_SCRIPTS_LAYER
)

# ── 規則 5:跨層上行 import ─────────────────────────────────────────
_KNOWN_VIOLATIONS[("R5", "src/data/portfolio/forward_test_store.py", "src.compute.screener.forward_test")] = (
    "TODO(C3-d):L1 → L2。module-level import,為了拿 PICK_SNAPSHOT_HEADERS 這個 "
    "schema 常數。諷刺的是本檔 docstring 還寫著「§8.2 L1:純檔案 I/O」。"
    "未修原因:正解是把 PICK_SNAPSHOT_HEADERS 下沉到 L0(shared/,如 "
    "shared/schemas.py 或新開 shared/forward_test_schema.py),兩層都 import L0。"
    "屬 SSOT 搬遷,低風險但要動 L2 caller,留給獨立 PR。"
)
_KNOWN_VIOLATIONS[("R5", "src/services/daily_checklist.py", "src.ui.render.macro_ui_components")] = (
    "TODO(C3-e):L3 → L4。module-level,為了 re-export 8 個渲染函式維持 v18.344 "
    "拆檔前的相容介面(_hex2rgba / sparkline / stat_card ...)。"
    "未修原因:要修得找出所有 `from src.services.daily_checklist import <render fn>` "
    "的 caller 改直打 L4,再刪 re-export shim。純機械改動但影響面要先盤點。"
)
for _f in (
    "src/ui/tabs/tab_macro.py",
    "src/ui/tabs/tab_stock.py",
    "src/ui/tabs/tab_stock_grp.py",
    "src/ui/tabs/macro/section_news_ai.py",
):
    _KNOWN_VIOLATIONS[("R5", _f, "app")] = (
        "TODO(C3-f):L5 → L6。late import `from app import gemini_call / api_key / "
        "parse_stocks / _bps / _get_fm_token / _tw_now_str`,寫在 render 函式內避免"
        "循環 import —— 循環 import 本身就是分層倒置的症狀。"
        "未修原因:正解是把 gemini_call 等 helper 下沉到 L3(src/services/ai_fetcher.py "
        "已有 post_gemini,可能直接改用),app.py 只留 orchestration。"
        "需先確認 app.py 版的 gemini_call 與 L3 版行為是否等價。"
    )

# L1 scripts/** → L2/L3(20 條,同一根因:scripts 分層標籤)
for _f, _m in (
    ("scripts/analyze_ring1_gate.py", "src.services.allocation_service"),
    ("scripts/calibrate_health_weights.py", "src.compute.macro.health_calibration"),
    ("scripts/calibrate_health_weights.py", "src.services.market_strategy"),
    ("scripts/calibrate_macro_traffic.py", "src.compute.macro"),
    ("scripts/calibrate_macro_traffic.py", "src.services"),
    ("scripts/export_stock_db.py", "src.compute.scoring.scoring_engine"),
    ("scripts/export_stock_db.py", "src.compute.strategy.tech_indicators"),
    ("scripts/push_daily_signals.py", "src.compute.notify.ai_judgment"),
    ("scripts/push_daily_signals.py", "src.compute.notify.signal_message"),
    ("scripts/push_daily_signals.py", "src.compute.notify.technical_snapshot"),
    ("scripts/push_daily_signals.py", "src.services.ai_fetcher"),
    ("scripts/push_daily_signals.py", "src.services.fundamental_screener_service"),
    ("scripts/push_daily_signals.py", "src.services.shortage_screener_service"),
    ("scripts/shortage_cli.py", "src.compute.health.monthly_revenue_calc"),
    ("scripts/shortage_cli.py", "src.compute.screener.shortage_screener"),
    ("scripts/update_forward_test_freeze.py", "src.services.forward_test_service"),
    ("scripts/update_forward_test_freeze.py", "src.services.fundamental_screener_service"),
    ("scripts/update_health_history.py", "src.compute.scoring"),
    ("scripts/update_health_history.py", "src.compute.strategy"),
    ("scripts/update_health_history.py", "src.services.health_history_service"),
):
    _KNOWN_VIOLATIONS[("R5", _f, _m)] = _TODO_SCRIPTS_LAYER


# ════════════════════════════════════════════════════════════════════
# 規則掃描
# ════════════════════════════════════════════════════════════════════
def _rule1_l1_streamlit() -> dict[tuple[str, str], list[ImportRecord]]:
    hits = [r for r in _ALL_IMPORTS
            if _layer_of_file(r.relpath) == L1
            and (r.target == "streamlit" or r.target.startswith("streamlit."))]
    return _by_key(hits)


def _rule1_l0_streamlit() -> dict[tuple[str, str], list[ImportRecord]]:
    hits = [r for r in _ALL_IMPORTS
            if _layer_of_file(r.relpath) == L0
            and (r.target == "streamlit" or r.target.startswith("streamlit."))]
    return _by_key(hits)


def _rule2_l2_banned() -> dict[tuple[str, str], list[ImportRecord]]:
    hits = [r for r in _ALL_IMPORTS
            if _layer_of_file(r.relpath) == L2 and _touches_banned_module(r)]
    return _by_key(hits)


def _rule3_l0_upward() -> dict[tuple[str, str], list[ImportRecord]]:
    hits = []
    for r in _ALL_IMPORTS:
        if _layer_of_file(r.relpath) != L0:
            continue
        tgt = _layer_of_module(r.target)
        if tgt is not None and tgt > L0:
            hits.append(r)
    return _by_key(hits)


def _rule4_ui_calls_l1() -> dict[tuple[str, str], list[ImportRecord]]:
    hits = []
    for r in _ALL_IMPORTS:
        # §8.2 硬規則點名 L5/L6;L4 併入掃描,因 §8.2.A 已登記 L4 lazy fallback
        if _layer_of_file(r.relpath) not in (L4, L5, L6):
            continue
        if _layer_of_module(r.target) == L1:
            hits.append(r)
    return _by_key(hits)


def _rule5_upward() -> dict[tuple[str, str], list[ImportRecord]]:
    """L1↛L2/L3、L2↛L3、L3↛L4/L5、L4/L5↛L6。L0 由規則 3 管,不重複。"""
    hits = []
    for r in _ALL_IMPORTS:
        src_layer = _layer_of_file(r.relpath)
        if src_layer is None or src_layer == L0:
            continue
        tgt_layer = _layer_of_module(r.target)
        if tgt_layer is None:
            continue
        if tgt_layer > src_layer:
            hits.append(r)
    return _by_key(hits)


_RULES = {
    "R1": ("L1 Data 不得 import streamlit", _rule1_l1_streamlit),
    "R1-L0": ("L0 Infra 不得 import streamlit(EX-L0-1 專用)", _rule1_l0_streamlit),
    "R2": ("L2 Compute 不得 import requests / proxy_helper / FinMind / yfinance",
           _rule2_l2_banned),
    "R3": ("L0 Infra 不得依賴任何 L1+", _rule3_l0_upward),
    "R4": ("L5 UI / L6 App(+L4 Render)不得直呼 L1 fetcher", _rule4_ui_calls_l1),
    "R5": ("跨層上行 import:L1↛L2/L3、L2↛L3、L3↛L4/L5、L4/L5↛L6", _rule5_upward),
}


def _baseline(rule_id: str) -> set[tuple[str, str]]:
    wl = {(f, m) for (r, f, m) in _WHITELIST if r == rule_id}
    kv = {(f, m) for (r, f, m) in _KNOWN_VIOLATIONS if r == rule_id}
    return wl | kv


def _assert_no_new(rule_id: str) -> None:
    desc, scan = _RULES[rule_id]
    found = scan()
    new = sorted(set(found) - _baseline(rule_id))
    if not new:
        return
    lines = [
        "",
        f"❌ 違反 CLAUDE.md §8.2 規則 {rule_id}:{desc}",
        f"   新增 {len(new)} 筆未登記的違憲 import:",
        "",
    ]
    for key in new:
        f, m = key
        lines.append(f"  ── {f}  →  {m}"
                     f"  [{LAYER_NAMES.get(_layer_of_file(f), '?')}"
                     f" → {LAYER_NAMES.get(_layer_of_module(m), m)}]")
        for rec in found[key]:
            lines.append(rec.evidence())
        lines.append("")
    lines += [
        "怎麼處理(二選一):",
        "  (A) 這是真違憲 → 修 production code,讓 import 走正確方向。",
        "  (B) 這是合法例外 → 加到本檔 _WHITELIST,key 寫成",
        f"        (\"{rule_id}\", \"<檔案路徑>\", \"<模組>\"): (EX-xxx, \"理由\")",
        "      並在 CLAUDE.md §8.2.A 對應 EX-ID 底下登記(禁止未登錄的軟例外)。",
        "  (C) 真違憲但這次不修 → 加到 _KNOWN_VIOLATIONS 並寫 TODO + 未修原因。",
        "",
        "  產生可貼上的基線:python tests/test_c3_layering_guard.py",
    ]
    pytest.fail("\n".join(lines), pytrace=False)


def _assert_not_stale(rule_id: str, registry: dict, label: str, hint: str) -> None:
    desc, scan = _RULES[rule_id]
    found = set(scan())
    listed = {(f, m) for (r, f, m) in registry if r == rule_id}
    stale = sorted(listed - found)
    if not stale:
        return
    lines = [
        "",
        f"❌ {label} 有 {len(stale)} 筆已經過期(規則 {rule_id}:{desc})",
        "   這些條目登記在案,但現在的程式碼已經不再違反該規則:",
        "",
    ]
    for f, m in stale:
        lines.append(f"  ── {f}  →  {m}")
    lines += ["", f"  {hint}", ""]
    pytest.fail("\n".join(lines), pytrace=False)


_STALE_WL_HINT = ("請從本檔 _WHITELIST 移除,並同步刪掉 CLAUDE.md §8.2.A 的對應登記。"
                  "例外清單只增不減,就會變成現在 CLAUDE.md 那樣的爛帳。")
_STALE_KV_HINT = ("違憲已修好 —— 請從本檔 _KNOWN_VIOLATIONS 移除(順手在 PR 描述記一筆)。"
                  "移除後這條規則就對該檔案永久生效了。")


# ════════════════════════════════════════════════════════════════════
# 規則 1 — L1 Data 不得 import streamlit
# ════════════════════════════════════════════════════════════════════
def test_rule1_l1_no_streamlit():
    _assert_no_new("R1")


def test_rule1_whitelist_not_stale():
    _assert_not_stale("R1", _WHITELIST, "EX-CACHE-1 / EX-OAUTH-1 白名單", _STALE_WL_HINT)


def test_rule1_known_violations_not_stale():
    _assert_not_stale("R1", _KNOWN_VIOLATIONS, "規則 1 待修清單", _STALE_KV_HINT)


def test_rule1_l0_no_streamlit():
    """不在 §8.2 五條硬規則內,但 EX-L0-1 存在就代表 L0 import streamlit 需被管制。"""
    _assert_no_new("R1-L0")


def test_rule1_l0_whitelist_not_stale():
    _assert_not_stale("R1-L0", _WHITELIST, "EX-L0-1 白名單", _STALE_WL_HINT)


# ════════════════════════════════════════════════════════════════════
# 規則 2 — L2 Compute 不得 import requests / proxy_helper / FinMind / yfinance
# ════════════════════════════════════════════════════════════════════
def test_rule2_l2_no_io_libs():
    _assert_no_new("R2")


def test_rule2_whitelist_not_stale():
    _assert_not_stale("R2", _WHITELIST, "規則 2 白名單", _STALE_WL_HINT)


def test_rule2_known_violations_not_stale():
    _assert_not_stale("R2", _KNOWN_VIOLATIONS, "規則 2 待修清單", _STALE_KV_HINT)


def test_rule2_barrel_forwarding_is_expanded():
    """守衛的守衛:確認 barrel 展開真的有效。

    `src/data/proxy/__init__.py` 用 PEP 562 `__getattr__` 把 proxy_helper 的符號
    轉發出來。如果哪天有人把 barrel 改成別的寫法而 _barrel_exports 沒跟上,
    規則 2 會靜默失效(掃不到任何東西 = 假綠燈)。這條測試釘住這個能力。
    """
    exports = _barrel_exports("src.data.proxy")
    assert exports, "src.data.proxy barrel 展開結果為空 — _barrel_exports 可能已失效"
    assert exports.get("fetch_url") == "src.data.proxy.proxy_helper", (
        "fetch_url 應解析到 proxy_helper(規則 2 點名禁止的模組),"
        f"實際得到 {exports.get('fetch_url')!r}。barrel 展開邏輯需要修。"
    )
    # 端到端:偽造一筆 L2 import,確認 _touches_banned_module 判得出來
    fake = ImportRecord("src/compute/x.py", 1, "from src.data.proxy import fetch_url",
                        "src.data.proxy", ("fetch_url",), None)
    assert _touches_banned_module(fake) == "proxy_helper"


# ════════════════════════════════════════════════════════════════════
# 規則 3 — L0 Infra 不得依賴任何 L1+
# ════════════════════════════════════════════════════════════════════
def test_rule3_l0_no_upward_deps():
    _assert_no_new("R3")


def test_rule3_whitelist_not_stale():
    _assert_not_stale("R3", _WHITELIST, "規則 3 白名單", _STALE_WL_HINT)


def test_rule3_known_violations_not_stale():
    _assert_not_stale("R3", _KNOWN_VIOLATIONS, "規則 3 待修清單", _STALE_KV_HINT)


# ════════════════════════════════════════════════════════════════════
# 規則 4 — L5 UI / L6 App 不得直呼 L1 fetcher
# ════════════════════════════════════════════════════════════════════
def test_rule4_ui_does_not_call_l1():
    _assert_no_new("R4")


def test_rule4_whitelist_not_stale():
    _assert_not_stale("R4", _WHITELIST, "EX-PASSTHRU-1 白名單", _STALE_WL_HINT)


def test_rule4_known_violations_not_stale():
    _assert_not_stale("R4", _KNOWN_VIOLATIONS, "規則 4 待修清單", _STALE_KV_HINT)


# ════════════════════════════════════════════════════════════════════
# 規則 5 — 跨層上行 import
# ════════════════════════════════════════════════════════════════════
def test_rule5_no_upward_imports():
    _assert_no_new("R5")


def test_rule5_whitelist_not_stale():
    _assert_not_stale("R5", _WHITELIST, "規則 5 白名單", _STALE_WL_HINT)


def test_rule5_known_violations_not_stale():
    _assert_not_stale("R5", _KNOWN_VIOLATIONS, "規則 5 待修清單", _STALE_KV_HINT)


def test_rule5_late_imports_are_detected():
    """守衛的守衛:確認巢狀(函式內)的 late import 有被掃到。

    §8.2 最常見的違憲就藏在函式內(避循環 import 的 `from app import ...`)。
    如果哪天有人把掃描改成只看 tree.body,這些會全部漏掉 = 假綠燈。
    """
    src = (
        "import os\n"
        "def f():\n"
        "    from app import gemini_call\n"
        "    if True:\n"
        "        try:\n"
        "            import yfinance as yf\n"
        "        except ImportError:\n"
        "            pass\n"
    )
    tree = ast.parse(src)
    targets = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    targets |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names}
    assert {"app", "yfinance", "os"} <= targets, (
        "ast.walk 應該掃到函式內 / try 內 / if 內的 import"
    )
    # 真實資料上的證據:專案內確實存在被掃到的 late import
    late = [r for r in _ALL_IMPORTS if r.func and r.target == "app"]
    assert late, "應至少掃到一筆函式內 `from app import ...`(L5→L6 違憲)"


# ════════════════════════════════════════════════════════════════════
# 結構自檢
# ════════════════════════════════════════════════════════════════════
def test_scan_found_files():
    """掃描器本身沒壞(路徑錯 / 全部 SyntaxError 會讓所有規則假綠燈)。"""
    assert len(_ALL_IMPORTS) > 300, (
        f"只掃到 {len(_ALL_IMPORTS)} 筆 import,掃描器可能壞了或路徑不對"
    )
    files = {r.relpath for r in _ALL_IMPORTS}
    assert "app.py" in files, "app.py(L6)未被掃到"
    assert any(f.startswith("src/data/") for f in files), "src/data/(L1)未被掃到"
    assert any(f.startswith("src/ui/tabs/") for f in files), "src/ui/tabs/(L5)未被掃到"


def test_whitelist_and_known_violations_are_disjoint():
    """同一條不能既是「合法例外」又是「待修違憲」—— 語意互斥。"""
    overlap = set(_WHITELIST) & set(_KNOWN_VIOLATIONS)
    assert not overlap, (
        "以下條目同時出現在 _WHITELIST 和 _KNOWN_VIOLATIONS,語意矛盾:\n"
        + "\n".join(f"  {k}" for k in sorted(overlap))
    )


def test_every_entry_has_a_reason():
    """例外/待修都必須寫理由 —— 沒理由的登記等於沒登記。"""
    bad_wl = [k for k, (ex, why) in _WHITELIST.items()
              if not ex or not why or len(why.strip()) < 20]
    assert not bad_wl, f"_WHITELIST 這些條目理由不足:\n" + "\n".join(map(str, bad_wl))

    bad_kv = [k for k, why in _KNOWN_VIOLATIONS.items()
              if "TODO" not in why or len(why.strip()) < 40]
    assert not bad_kv, (
        "_KNOWN_VIOLATIONS 這些條目缺 TODO 標記或未說明「為什麼還沒修」:\n"
        + "\n".join(map(str, bad_kv))
    )


def test_known_ex_ids_match_claude_md():
    """白名單只能用 §8.2.A 登記過的 EX-ID。"""
    allowed = {EX_L0_1, EX_CACHE_1, EX_OAUTH_1, EX_PASSTHRU_1}
    used = {ex for ex, _ in _WHITELIST.values()}
    assert used <= allowed, (
        f"出現未在 CLAUDE.md §8.2.A 登記的 EX-ID:{sorted(used - allowed)}"
    )


def test_all_registry_rule_ids_are_known():
    """打錯規則 id 會讓條目永遠不生效(且反向守衛也抓不到)。"""
    for name, reg in (("_WHITELIST", _WHITELIST), ("_KNOWN_VIOLATIONS", _KNOWN_VIOLATIONS)):
        bad = {r for (r, _, _) in reg} - set(_RULES)
        assert not bad, f"{name} 有未知的規則 id:{sorted(bad)}(合法:{sorted(_RULES)})"


def test_registry_paths_exist():
    """路徑打錯 / 檔案被刪但條目沒清,會讓條目變成幽靈。"""
    missing = sorted({f for (_, f, _) in {**_WHITELIST, **_KNOWN_VIOLATIONS}
                      if not (REPO_ROOT / f).is_file()})
    assert not missing, (
        "以下登記的檔案不存在(改名或已刪?請同步更新 _WHITELIST / _KNOWN_VIOLATIONS):\n"
        + "\n".join(f"  {m}" for m in missing)
    )


# ════════════════════════════════════════════════════════════════════
# 基線產生器:python tests/test_c3_layering_guard.py
# ════════════════════════════════════════════════════════════════════
def _dump() -> None:
    print(f"# C3 layering guard — 目前實際掃描結果(共 {len(_ALL_IMPORTS)} 筆 import)")
    for rule_id, (desc, scan) in _RULES.items():
        found = scan()
        base = _baseline(rule_id)
        print(f"\n{'=' * 70}\n# {rule_id}: {desc}")
        print(f"# 實際命中 {len(found)} 組 (檔案, 模組);已登記基線 {len(base)} 組")
        new = sorted(set(found) - base)
        stale = sorted(base - set(found))
        if new:
            print(f"\n#  ▼ 未登記({len(new)} 組)— 判斷是例外還是違憲後貼進對應清單:")
            for f, m in new:
                print(f'    ("{rule_id}", "{f}", "{m}"),')
                for rec in found[(f, m)]:
                    print(f"    #   {rec.relpath}:{rec.lineno}: {rec.source}")
        if stale:
            print(f"\n#  ▼ 已過期({len(stale)} 組)— 從清單移除:")
            for f, m in stale:
                print(f'    ("{rule_id}", "{f}", "{m}"),')
        if not new and not stale:
            print("#  ✅ 基線與實際一致")


if __name__ == "__main__":
    _dump()
