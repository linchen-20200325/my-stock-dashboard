"""Issue #1138 工作 A — Decision Digest v1 不變性回歸守衛（tests-only；不改 Digest v1 契約、不新增欄位、不建 caller）。

被測行為「已正確」，本檔補的是**缺少的回歸測試**。三組：

C1  UI 狀態不變性（契約 §9.3／Brain §8.3）：站內列／持股列／macro_state 上夾帶 UI 汙染鍵
    （`_top_n`／`expanded`／`visible`…）不得改變 `assemble_digest(...).to_dict()` 與 `build_rule_summary(...).lines`；
    builder／summary／assembly 在「執行期陷阱」（網路／subprocess／寫檔／改 env／讀 session_state 一碰就 raise）下仍可跑；
    輸入不被 mutate。

C2  repo 全域「0 production caller」守衛：AST 掃描 repo 內所有 .py（排除 tests/、docs、digest 家族檔自身），
    沒有任何檔 import 8 個 digest 側車／規則模組（含 `from x import y`、`import x`、相對 import、
    `importlib.import_module('…')`／`__import__('…')` 字串形式）。
    ⚠️ 此守衛**編碼 Stage F production caller Gate**：Gate 開啟（第一個 production caller 被核准）時，
    必須**同步更新本守衛**（把該 caller 加進 `ALLOWED_CALLERS` 並附核准依據），否則 CI 紅燈 —— 這是設計。
    依據：Issue #1138、DEC-159／DEC-160。
    白名單說明：`shared/strategy_class_schema.py` 只 import **L0 根契約** `shared.decision_digest`
    （取 `HoldingKey`／`StrategyType` 兩個純型別），不在上述 8 個目標內，亦不碰任何側車／規則模組；
    本檔另有測試鎖死「它對 digest 家族只 import 那一個模組」。

C3  L0 動態 import 閉包：以 `python -I` 子行程匯入 shared 的 digest 家族與其 L0 依賴，
    用**匯入前後 sys.modules 差集**斷言新增模組不含 streamlit／requests／pandas／numpy／src／app 等。
    （`google` 在直譯器啟動時即被預載，故一律用差集而非絕對檢查。）
    ⚠️ `python -I` 會**忽略 PYTHONPATH**，所以 repo 根以 `sys.path.insert` 在子行程腳本內注入；
    同時仍設 PYTHONPATH／cwd = repo 根（無害，與其他工具一致）。
"""
from __future__ import annotations

import ast
import builtins
import copy
import json
import os
import socket
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import HoldingKey
from shared.fetch_outcome import FetchOutcome  # noqa: F401  （確認 L0 依賴存在；C3 也會匯入）
from shared.freshness_policy import FreshnessStatus as F
from shared.risk_cap_policy import RiskCapDisclosure
from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp, build_decision_digest
from src.services.decision_digest_summary import build_rule_summary

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
D = date(2026, 10, 26)
MACRO_STAMP = SourceStamp("macro_state.json", D)
STATION_STAMP = SourceStamp("dividend_station_service", D)


# ── 夾具（自包含，不跨測試檔 import）──────────────────────────────────────
def _macro():
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5, "exposure_limit_pct": 60,
            "defense": False,
            "risk_cap_disclosure": RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(),
                                                     disabled=(), sahm_status=None)}


_CODES = ("add", "pause_add", "cut", "take_profit_force", "take_profit_partial", "add", "pause_add")


def _rows(n, codes=_CODES):
    return [{"代號": f"T{i}", "held": True, "_action": codes[i % len(codes)],
             "建議動作": f"txt-{codes[i % len(codes)]}-T{i}", "_detail": {}} for i in range(n)]


def _kwargs(n=6, codes=_CODES):
    rows = _rows(n, codes)
    tickers = [r["代號"] for r in rows]
    return dict(generated_at=NOW, macro_state=_macro(),
                macro_evidence=EvidenceInput(stamp=MACRO_STAMP, freshness=F.FRESH),
                allocation=build_allocation_decision(_macro()),
                station_rows=rows, station_evidence=EvidenceInput(stamp=STATION_STAMP, freshness=F.FRESH),
                holdings_rows=[{"ticker": t, "name": f"n-{t}", "held": True} for t in tickers],
                holding_keys={t: HoldingKey("pf-A", t) for t in tickers})


_UI_POLLUTION = {"_top_n": 3, "expanded": False, "visible": False, "_ui_selected": True, "page": 2}


def _polluted(kw):
    """副本 B：每一列加 UI 汙染鍵、macro_state 加 top_n／expanded。"""
    b = copy.deepcopy(kw)
    for key in ("station_rows", "holdings_rows"):
        for r in b[key]:
            r.update(_UI_POLLUTION)
    b["macro_state"].update({"top_n": 3, "expanded": False, "visible": False})
    return b


def _dump(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=repr)


# ════════════════════════════════════════════════════════════════════════
# C1 UI 狀態不變性
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("n", [5, 6, 8])
def test_c1_ui_pollution_keys_do_not_change_assembled_dict(n):
    a_kw = _kwargs(n)
    b_kw = _polluted(a_kw)
    assert b_kw["station_rows"] != a_kw["station_rows"]                 # 前提：B 真的被汙染
    a, b = assemble_digest(**a_kw), assemble_digest(**b_kw)
    assert a.to_dict() == b.to_dict()                                   # digest ＋ coverage 皆相同
    assert a.coverage.to_dict() == b.coverage.to_dict()
    assert a.coverage.actions_total_eligible == n                        # 5+ 檔候選：確實有被 MAX_ACTIONS 截斷
    assert a.coverage.actions_omitted_count == max(0, n - a.coverage.actions_max)


@pytest.mark.parametrize("codes", [("add",), ("pause_add",), ("add", "pause_add")])
def test_c1_ui_pollution_cannot_reshuffle_when_chosen_actions_are_low_priority_codes(codes):
    """候選全是低優先碼（被選中的就是這些列）→ 若有人讓 builder 讀 UI 鍵，輸出必變。"""
    a_kw = _kwargs(6, codes)
    a, b = assemble_digest(**a_kw), assemble_digest(**_polluted(a_kw))
    assert len(a.digest.actions.items) == 3
    assert a.to_dict() == b.to_dict()
    assert build_rule_summary(a.digest).lines == build_rule_summary(b.digest).lines


def test_c1_ui_pollution_keys_do_not_change_rule_summary_lines():
    a = assemble_digest(**_kwargs(6))
    b = assemble_digest(**_polluted(_kwargs(6)))
    la, lb = build_rule_summary(a.digest).lines, build_rule_summary(b.digest).lines
    assert la and la == lb


def test_c1_top_n_value_does_not_leak_into_action_count():
    """`_top_n` 不論設多少（1／3／99），Digest 的行動數都只由契約 MAX_ACTIONS 決定。"""
    base = assemble_digest(**_kwargs(7)).to_dict()
    for top_n in (1, 3, 99):
        kw = _kwargs(7)
        for r in kw["station_rows"]:
            r["_top_n"] = top_n
        assert assemble_digest(**kw).to_dict() == base


def test_c1_builder_alone_ignores_ui_pollution():
    kw = _kwargs(6)
    bkw = _polluted(kw)
    common = ("generated_at", "macro_state", "allocation", "station_rows", "holdings_rows", "holding_keys")
    da = build_decision_digest(**{k: kw[k] for k in common}, macro_stamp=MACRO_STAMP, station_stamp=STATION_STAMP)
    db = build_decision_digest(**{k: bkw[k] for k in common}, macro_stamp=MACRO_STAMP, station_stamp=STATION_STAMP)
    assert da.to_dict() == db.to_dict()


def test_c1_inputs_not_mutated_by_builder_summary_assembly():
    kw = _polluted(_kwargs(6))
    before = copy.deepcopy(kw)
    snapshot = _dump(before)
    a = assemble_digest(**kw)
    build_rule_summary(a.digest)
    build_decision_digest(generated_at=kw["generated_at"], macro_state=kw["macro_state"],
                          macro_stamp=MACRO_STAMP, allocation=kw["allocation"], station_rows=kw["station_rows"],
                          station_stamp=STATION_STAMP, holdings_rows=kw["holdings_rows"],
                          holding_keys=kw["holding_keys"])
    assert _dump(kw) == snapshot
    assert kw["station_rows"] == before["station_rows"] and kw["holdings_rows"] == before["holdings_rows"]
    assert kw["macro_state"] == before["macro_state"]
    assert kw["holding_keys"] == before["holding_keys"]


class _RaisingEnv(dict):
    """armed 期間任何寫入都 raise；解除（armed=False）後恢復正常，讓 pytest 自己的 teardown 能改 env。"""
    armed = True

    def __setitem__(self, k, v):
        if self.armed:
            raise AssertionError("digest 路徑不得改 os.environ")
        dict.__setitem__(self, k, v)

    def __delitem__(self, k):
        if self.armed:
            raise AssertionError("digest 路徑不得改 os.environ")
        dict.__delitem__(self, k)

    def setdefault(self, *a, **k):
        if self.armed:
            raise AssertionError("digest 路徑不得改 os.environ")
        return dict.setdefault(self, *a, **k)

    def update(self, *a, **k):
        if self.armed:
            raise AssertionError("digest 路徑不得改 os.environ")
        dict.update(self, *a, **k)

    def pop(self, *a, **k):
        if self.armed:
            raise AssertionError("digest 路徑不得改 os.environ")
        return dict.pop(self, *a, **k)


def test_c1_runs_under_runtime_traps(monkeypatch, tmp_path):
    real_open = builtins.open

    def guarded_open(file, mode="r", *a, **k):
        if any(ch in str(mode) for ch in "wax+"):
            raise AssertionError(f"digest 路徑不得寫檔：open({file!r}, {mode!r})")
        return real_open(file, mode, *a, **k)

    def boom(*a, **k):
        raise AssertionError("digest 路徑不得碰網路／subprocess")

    kw = _polluted(_kwargs(6))                       # 先備好輸入（fixture 建構本身不在受測範圍）
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    env_guard = _RaisingEnv(os.environ)
    monkeypatch.setattr(os, "environ", env_guard)
    try:
        import streamlit as st

        class NoSession:
            def __getattr__(self, name):
                raise AssertionError("digest 路徑不得讀 st.session_state")

            def __getitem__(self, k):
                raise AssertionError("digest 路徑不得讀 st.session_state")

            def __setitem__(self, k, v):
                raise AssertionError("digest 路徑不得寫 st.session_state")

            def get(self, *a, **k):
                raise AssertionError("digest 路徑不得讀 st.session_state")
        monkeypatch.setattr(st, "session_state", NoSession(), raising=False)
    except ImportError:
        pass
    before = sorted(p.name for p in tmp_path.iterdir())
    try:
        a = assemble_digest(**kw)
        summary = build_rule_summary(a.digest)
        digest = build_decision_digest(generated_at=NOW, macro_state=kw["macro_state"], macro_stamp=MACRO_STAMP,
                                       allocation=kw["allocation"], station_rows=kw["station_rows"],
                                       station_stamp=STATION_STAMP, holdings_rows=kw["holdings_rows"],
                                       holding_keys=kw["holding_keys"])
    finally:
        env_guard.armed = False                       # 解除，讓 pytest teardown 能正常寫 PYTEST_CURRENT_TEST
    assert a.coverage.actions_total_eligible == 6 and summary.lines and digest.to_dict()
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_c1_traps_actually_trip(monkeypatch):
    """陷阱本身有牙：確認上面的 trap 真的會 raise（避免陷阱失效導致測試永遠綠）。"""
    env_guard = _RaisingEnv(os.environ)
    monkeypatch.setattr(os, "environ", env_guard)
    try:
        with pytest.raises(AssertionError):
            os.environ["X_DIGEST_TRAP"] = "1"
        with pytest.raises(AssertionError):
            os.environ.setdefault("X_DIGEST_TRAP", "1")
    finally:
        env_guard.armed = False
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("net")))
    with pytest.raises(AssertionError):
        socket.socket()


# ════════════════════════════════════════════════════════════════════════
# C2 repo 全域 0 production caller 守衛（編碼 Stage F Gate；Issue #1138、DEC-159／DEC-160）
# ════════════════════════════════════════════════════════════════════════
TARGET_MODULES = frozenset({
    "src.services.decision_digest_builder",
    "src.services.decision_digest_assembly",
    "src.services.decision_digest_summary",
    "shared.decision_digest_coverage",
    "shared.decision_digest_grounding",
    "shared.decision_digest_validator",
    "shared.decision_digest_terms",
    "shared.decision_digest_rules",
})
# Stage F Gate 開啟時，核准的 production caller 加在這裡（repo 相對路徑，附核准依據）。現況：空。
ALLOWED_CALLERS: frozenset = frozenset()
# 僅 import L0 根契約 shared.decision_digest 的既有檔（不在 TARGET_MODULES 內，另由專屬測試鎖死）。
L0_ROOT_IMPORTERS = frozenset({"shared/strategy_class_schema.py"})

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "env", ".tox", ".mypy_cache",
              ".pytest_cache", "site-packages", "scratchpad", "docs", "tests"}


def _is_family_file(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return ((rel.startswith("shared/") and rel.count("/") == 1 and name.startswith("decision_digest"))
            or (rel.startswith("src/services/") and rel.count("/") == 2 and name.startswith("decision_digest_")))


def _iter_py(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def _package_of(rel: str) -> list:
    parts = rel[:-3].split("/")
    return parts[:-1] if parts[-1] != "__init__" else parts[:-1]


def _imported_modules(tree: ast.AST, rel: str) -> set:
    """回傳此檔以任何形式觸及的『絕對模組名』集合（含 from-import 的 module.name 組合與 importlib 字串形式）。"""
    found: set = set()
    pkg = _package_of(rel)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            found |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = pkg[: len(pkg) - (n.level - 1)] if n.level - 1 <= len(pkg) else []
                mod = ".".join(base + ([n.module] if n.module else []))
            else:
                mod = n.module or ""
            if mod:
                found.add(mod)
                found |= {f"{mod}.{a.name}" for a in n.names}
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if name in ("import_module", "__import__") and n.args:
                a0 = n.args[0]
                if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                    found.add(a0.value)
    return found


def scan_digest_callers(root: Path, *, allowed: frozenset = frozenset()) -> list:
    """掃 root 下所有 .py（排除 tests/docs/digest 家族檔自身），回傳 [(相對路徑, 命中的模組)]。"""
    hits = []
    for path in _iter_py(root):
        rel = path.relative_to(root).as_posix()
        if _is_family_file(rel) or rel in allowed:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:                  # 掃不動 ＝ 不能宣稱沒 caller → fail loud
            hits.append((rel, f"UNPARSEABLE:{type(exc).__name__}"))
            continue
        for m in sorted(_imported_modules(tree, rel) & TARGET_MODULES):
            hits.append((rel, m))
    return hits


def test_c2_repo_has_zero_production_callers_of_digest_family():
    hits = scan_digest_callers(REPO, allowed=ALLOWED_CALLERS)
    assert hits == [], (
        "發現 digest 側車／規則模組的 production caller。這是 Stage F production caller Gate"
        "（Issue #1138、DEC-159／DEC-160）：Gate 未開啟前不得有 caller；"
        "若 Gate 已核准開啟，請同步更新本守衛的 ALLOWED_CALLERS 並附核准依據。命中：" + repr(hits))


def test_c2_scanner_has_teeth_on_fake_callers(tmp_path):
    (tmp_path / "pkg").mkdir()
    cases = {
        "a_from.py": "from src.services.decision_digest_builder import build_decision_digest\n",
        "b_import.py": "import shared.decision_digest_rules\n",
        "c_from_pkg.py": "from src.services import decision_digest_summary\n",
        "d_importlib.py": "import importlib\nimportlib.import_module('shared.decision_digest_coverage')\n",
        "e_dunder.py": "__import__('src.services.decision_digest_assembly')\n",
        "pkg/f_rel.py": "from ..shared import decision_digest_terms\n",
        "pkg/g_alias.py": "import shared.decision_digest_validator as v\n",
    }
    for rel, src in cases.items():
        p = tmp_path / rel
        p.write_text(src, encoding="utf-8")
    hits = scan_digest_callers(tmp_path)
    assert {r for r, _ in hits} == set(cases)                       # 每種 import 形式都被抓到


def test_c2_scanner_catches_relative_import_and_respects_exclusions(tmp_path):
    (tmp_path / "shared").mkdir()
    (tmp_path / "src" / "services").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    # 相對 import：shared/foo.py 中 `from . import decision_digest_rules`
    (tmp_path / "shared" / "foo.py").write_text("from . import decision_digest_rules\n", encoding="utf-8")
    (tmp_path / "shared" / "bar.py").write_text("from .decision_digest_terms import X\n", encoding="utf-8")
    # 家族自身與 tests/ 不算 caller
    (tmp_path / "shared" / "decision_digest_validator.py").write_text(
        "from shared.decision_digest_rules import y\n", encoding="utf-8")
    (tmp_path / "src" / "services" / "decision_digest_summary.py").write_text(
        "from src.services.decision_digest_builder import z\n", encoding="utf-8")
    (tmp_path / "tests" / "test_x.py").write_text(
        "from src.services.decision_digest_builder import z\n", encoding="utf-8")
    hits = scan_digest_callers(tmp_path)
    assert sorted(hits) == [("shared/bar.py", "shared.decision_digest_terms"),
                            ("shared/foo.py", "shared.decision_digest_rules")]
    # allowed 白名單可放行
    assert scan_digest_callers(tmp_path, allowed=frozenset({"shared/foo.py", "shared/bar.py"})) == []
    # 掃不動的檔 fail loud，不靜默略過
    (tmp_path / "broken.py").write_text("def (:\n", encoding="utf-8")
    assert any(m.startswith("UNPARSEABLE") for _, m in scan_digest_callers(tmp_path))


def test_c2_l0_root_importers_are_exactly_the_whitelist():
    """`shared.decision_digest`（L0 根契約）在家族外的 importer 恰為白名單；且它們不碰任何側車／規則模組。"""
    importers = set()
    for path in _iter_py(REPO):
        rel = path.relative_to(REPO).as_posix()
        if _is_family_file(rel):
            continue
        mods = _imported_modules(ast.parse(path.read_text(encoding="utf-8")), rel)
        if any(m == "shared.decision_digest" or m.startswith("shared.decision_digest.") for m in mods):
            importers.add(rel)
        digest_family = {m for m in mods if "decision_digest" in m and m != "shared.decision_digest"
                         and not m.startswith("shared.decision_digest.")}
        # 家族外任何檔不得碰 root 以外的 digest 模組（含 `shared.decision_digest.<name>` 形式的 from-import 展開）
        assert not (digest_family & TARGET_MODULES), rel
    assert importers == set(L0_ROOT_IMPORTERS) | (importers & set(ALLOWED_CALLERS)), importers


def test_c2_strategy_class_schema_imports_only_l0_root_of_digest_family():
    rel = "shared/strategy_class_schema.py"
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    digest_mods = {m for m in _imported_modules(tree, rel) if "decision_digest" in m}
    # from shared.decision_digest import HoldingKey, StrategyType → {'shared.decision_digest', '….HoldingKey', '….StrategyType'}
    assert {m for m in digest_mods if m.count(".") == 1} == {"shared.decision_digest"}
    assert not (digest_mods & TARGET_MODULES)


# ════════════════════════════════════════════════════════════════════════
# C3 L0 動態 import 閉包（python -I 子行程；sys.modules 差集）
# ════════════════════════════════════════════════════════════════════════
DIGEST_FAMILY_MODULES = ("shared.decision_digest", "shared.decision_digest_rules", "shared.decision_digest_terms",
                         "shared.decision_digest_grounding", "shared.decision_digest_validator",
                         "shared.decision_digest_coverage")
L0_DEP_CANDIDATES = ("shared.regime_arbiter", "shared.risk_cap_policy", "shared.station_specs",
                     "shared.fetch_outcome", "shared.freshness_policy")
BANNED_TOP = ("streamlit", "requests", "urllib3", "http", "urllib", "socket", "ssl", "pandas", "numpy",
              "yfinance", "anthropic", "openai", "src", "app")
BANNED_DOTTED = ("google.generativeai",)

_CHILD = r"""
import importlib, json, sys
sys.path.insert(0, sys.argv[1])
before = set(sys.modules)
imported = []
for name in sys.argv[2:]:
    importlib.import_module(name)
    imported.append(name)
after = set(sys.modules)
print(json.dumps({"before": sorted(before), "new": sorted(after - before), "imported": imported}))
"""


def _run_child(mods):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    p = subprocess.run([sys.executable, "-I", "-c", _CHILD, str(REPO), *mods], cwd=REPO, env=env,
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def _existing_l0_deps():
    return [m for m in L0_DEP_CANDIDATES if (REPO / (m.replace(".", "/") + ".py")).exists()
            or (REPO / m.replace(".", "/") / "__init__.py").exists()]


def _violations(new_mods):
    bad = []
    for m in new_mods:
        top = m.split(".")[0]
        if top in BANNED_TOP or any(m == d or m.startswith(d + ".") for d in BANNED_DOTTED):
            bad.append(m)
    return bad


def test_c3_digest_family_and_l0_deps_exist_and_import_cleanly():
    deps = _existing_l0_deps()
    assert {"shared.risk_cap_policy", "shared.fetch_outcome", "shared.freshness_policy"} <= set(deps)
    out = _run_child(list(DIGEST_FAMILY_MODULES) + deps)
    assert out["imported"] == list(DIGEST_FAMILY_MODULES) + deps
    for m in DIGEST_FAMILY_MODULES:
        assert m in out["new"] or m in out["before"], m


def test_c3_digest_family_closure_has_no_forbidden_modules():
    out = _run_child(list(DIGEST_FAMILY_MODULES) + _existing_l0_deps())
    new = out["new"]
    assert any(m.startswith("shared.") for m in new)                       # 差集不是空的（測試有在量東西）
    assert _violations(new) == [], _violations(new)


@pytest.mark.parametrize("mod", DIGEST_FAMILY_MODULES + tuple(L0_DEP_CANDIDATES))
def test_c3_each_module_individually_has_clean_closure(mod):
    if not (REPO / (mod.replace(".", "/") + ".py")).exists():
        pytest.skip(f"{mod} 不存在")
    out = _run_child([mod])
    assert _violations(out["new"]) == [], (mod, _violations(out["new"]))


def test_c3_baseline_preloads_are_handled_by_diff_not_absolute():
    """直譯器啟動時已存在的模組（如 google）不可列為違規 —— 以差集判斷；差集檢查本身對『新載入』有牙。"""
    out = _run_child(list(DIGEST_FAMILY_MODULES))
    assert not (set(out["new"]) & set(out["before"]))
    # 牙：若匯入了 pandas（不在家族閉包內），差集檢查必須回報
    probe = _run_child(["pandas"]) if _has("pandas") else None
    if probe is not None:
        assert "pandas" in _violations(probe["new"])


def _has(name):
    import importlib.util
    return importlib.util.find_spec(name) is not None
