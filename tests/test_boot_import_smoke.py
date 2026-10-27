"""tests/test_boot_import_smoke.py — production boot/import smoke（NEWUI-STAGE-D2-BOOT-INCIDENT）。

═══ 為什麼有這支 ═══════════════════════════════════════════════════════
D2 (#944) 合併後客戶回報 Streamlit Cloud 啟動 app.py 即 ImportError（指向 app.py
`from shared.ia_nav import (...)`），但 CI 全綠。既有測試都在 **pytest 行程內**
跑，`sys.modules` 早被別的測試填滿 —— 那會遮蔽「乾淨行程冷啟動」才會出的問題。

⚠️ 根因**尚未確認**（缺 Cloud 完整 traceback）。本檔**不宣稱**任何根因，只做：
  (a) 乾淨行程冷啟動 app.py（`python -I` subprocess，不是 pytest 行程內）；
  (b) 靜態契約：app.py 所 import 的名稱 / `_ia_nav.<attr>` 在對應模組真的存在；
  (c) 「偵測能力驗證」：把舊版 shared/ia_nav 塞進 sys.modules，確認守衛的檢查方式
      真的會炸 —— 這是證明守衛有牙，**不是**產品行為，也**不是**根因結論。

(a) 冷啟動 AppTest 實測耗時見測試 docstring 之外的 PR/報告；timeout 取寬鬆值，
慢但通過不算失敗。本檔刻意不標 slow（fast lane）。
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"
#: 舊版（D2 之前）ia_nav 的 commit；用來做偵測能力驗證，內容缺 D2 新增的名稱。
_OLD_IA_NAV_COMMIT = "ad0a3c2"
_COLD_BOOT_TIMEOUT_S = 180


def _run_clean(code: str, timeout: int, *args: str) -> subprocess.CompletedProcess:
    """`python -I`：忽略 PYTHON* 環境變數與 cwd/user site —— 全新、乾淨的 sys.modules。
    -I 連 cwd 都不放進 sys.path，故 repo 根由腳本自己顯式插入（等同 Cloud 的 repo-root 啟動）。"""
    prelude = f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    return subprocess.run(
        [sys.executable, "-I", "-c", prelude + code, *args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
    )


# ── (a) 乾淨行程冷啟動 ──────────────────────────────────────────────
def test_cold_boot_app_in_fresh_process_has_no_exception():
    code = textwrap.dedent(f"""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file({str(APP)!r}, default_timeout={_COLD_BOOT_TIMEOUT_S - 20}).run(timeout={_COLD_BOOT_TIMEOUT_S - 20})
        exc = [str(e.value)[:500] for e in at.exception]
        if exc:
            print("APP_EXCEPTIONS:", exc); raise SystemExit(3)
        print("COLD_BOOT_OK")
    """)
    r = _run_clean(code, _COLD_BOOT_TIMEOUT_S)
    assert r.returncode == 0 and "COLD_BOOT_OK" in r.stdout, (
        f"rc={r.returncode}\nSTDOUT:\n{r.stdout[-2000:]}\nSTDERR:\n{r.stderr[-3000:]}")
    assert "Traceback" not in r.stderr, r.stderr[-3000:]


# ── (b) 靜態契約 ────────────────────────────────────────────────────
def _app_module_level_imports() -> list[tuple[str, list[str]]]:
    """app.py **全部** `from shared.* / src.* import ...`（含縮排內者；late import 也要存在）。"""
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and (
                n.module.split(".")[0] in ("shared", "src")):
            out.append((n.module, [a.name for a in n.names]))
    return out


def _ia_nav_attrs_used() -> set[str]:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    return {n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            and n.value.id == "_ia_nav"}


_CHECK_IMPORTS = textwrap.dedent("""
    import importlib, json, sys
    specs = json.loads(sys.argv[1]); attrs = json.loads(sys.argv[2])
    missing = []
    for mod, names in specs:
        try:
            m = importlib.import_module(mod)
        except Exception as e:                      # 模組本身 import 失敗也是違約
            missing.append(f"{mod}: import failed {type(e).__name__}: {e}"); continue
        for nm in names:
            if nm == "*":
                continue
            if not hasattr(m, nm):
                try:                                 # `from pkg import submodule`
                    importlib.import_module(f"{mod}.{nm}")
                except Exception:
                    missing.append(f"{mod}.{nm}")
    ia = importlib.import_module("shared.ia_nav")
    missing += [f"shared.ia_nav.{a}" for a in attrs if not hasattr(ia, a)]
    print("MISSING:" + json.dumps(missing))
    raise SystemExit(1 if missing else 0)
""")


def _static_contract(extra_drop: str | None = None):
    import json
    specs = _app_module_level_imports()
    attrs = sorted(_ia_nav_attrs_used())
    return _run_clean(_CHECK_IMPORTS, 120, json.dumps(specs), json.dumps(attrs))


def test_app_imports_resolve_in_clean_process():
    specs = _app_module_level_imports()
    assert any(m == "shared.ia_nav" for m, _ in specs), "掃描器壞了：找不到 shared.ia_nav import"
    assert _ia_nav_attrs_used(), "掃描器壞了：找不到 _ia_nav.<attr>"
    r = _static_contract()
    assert r.returncode == 0, f"{r.stdout[-2500:]}\n{r.stderr[-2500:]}"


# ── (c) 偵測能力驗證（殘留舊模組模擬）— 不是產品行為，也不是根因結論 ──────────
def test_detection_capability_stale_ia_nav_in_sys_modules_is_caught(tmp_path):
    old = subprocess.run(["git", "show", f"{_OLD_IA_NAV_COMMIT}:shared/ia_nav.py"],
                         cwd=str(ROOT), capture_output=True, text=True)
    if old.returncode != 0:
        import pytest
        pytest.skip(f"git 歷史不含 {_OLD_IA_NAV_COMMIT}（shallow clone）：偵測能力驗證略過")
    stale = tmp_path / "stale_ia_nav.py"
    stale.write_text(old.stdout, encoding="utf-8")
    code = textwrap.dedent(f"""
        import ast, importlib.util, sys
        spec = importlib.util.spec_from_file_location("shared.ia_nav", {str(stale)!r})
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        sys.modules["shared.ia_nav"] = mod            # 模擬行程內殘留舊模組
        tree = ast.parse(open({str(APP)!r}, encoding="utf-8").read())
        body = []
        for n in tree.body:                            # 只跑 app 的 ia_nav import 區 + 其後第一個用到 _ia_nav 的賦值
            if isinstance(n, ast.ImportFrom) and n.module in ("shared.ia_nav",):
                body.append(n)
            elif isinstance(n, ast.ImportFrom) and n.module == "shared" and any(a.name == "ia_nav" for a in n.names):
                body.append(n)
            elif isinstance(n, ast.Assign) and ("_ia_nav" in ast.dump(n) or "_IA_NAV_OFF" in ast.dump(n)):
                body.append(n)
                if "_ia_nav" in ast.dump(n): break
        exec(compile(ast.Module(body=body, type_ignores=[]), "app_import_region", "exec"), {{}})
        print("NOT_CAUGHT")
    """)
    r = _run_clean(code, 120)
    assert "NOT_CAUGHT" not in r.stdout, "舊模組竟通過 app import 區：守衛無牙"
    assert ("ImportError" in r.stderr or "AttributeError" in r.stderr), r.stderr[-1500:]
