"""VN1-STORE Pre-Hardening 批（2026-10-20；production 寫入**仍未核准**）— 寫入依賴與併發守衛。

守：
A. 寫入依賴
   1. L1 儲存端已搬到 `src/data/risk_cap/history.py`（`src.data.macro` 是 eager barrel，會連帶載入 pandas）；
      新套件 `__init__` 只有 docstring（⛔ barrel／re-export shim）；全 repo 沒有任何程式再 import 舊路徑。
   2. `requirements-risk-cap-writer.txt`：每個套件都 `==` 釘版且帶 `--hash=sha256:`；直接依賴＝gspread／google-auth／
      requests 且版本落在 requirements.txt 同名行的範圍內；⛔ 沒有 pandas／numpy／streamlit；檔頭有重產指令與日期。
   3. workflow 寫入 job：`pip install --require-hashes --no-deps -r requirements-risk-cap-writer.txt`、⛔ 不裝
      requirements.txt；compute job 照舊裝完整 requirements.txt。
   4. 寫入路徑（`--write`／`--precheck`／`--verify-written` 走到閘門 exit 2）在子行程內 ⛔ 不載入 pandas／numpy／streamlit。
C. 併發：拿得到 writer 身分（auth action）或跑權限驗證腳本／`--write` 的 job，一律掛**同一個字面** job 層 group
   `risk-cap-history-sheet-write`（cancel-in-progress: false）；workflow 層 group 是另一個字面名稱且不變；
   ⛔ 任何 job 都沒有 `environment:`（引用不存在的 environment 會自動建一個沒有保護的 —— 那是客戶 Gate）。
突變自驗（in-test）：缺 hash、寫入 job 改裝 requirements.txt、拿掉某個 job 的 group、group 改名、workflow group 撞名 ⇒ 轉紅。
⛔ 不連網、⛔ 不碰 `PRODUCTION_WRITE_APPROVED`。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests._git_tracked import REPO_MIN_TRACKED, only_tracked
from tests.test_vn1_wif_auth_only import _job_text, _parse

REPO = Path(__file__).resolve().parents[1]
WORKFLOW_REL = ".github/workflows/risk_cap_history_poc.yml"
LOCK_REL = "requirements-risk-cap-writer.txt"
LOCK_IN_REL = "requirements-risk-cap-writer.in"
NEW_L1_REL = "src/data/risk_cap/history.py"
OLD_L1_REL = "src/data/macro/risk_cap_history.py"
SHEET_GROUP = "risk-cap-history-sheet-write"
WORKFLOW_GROUP = "risk-cap-history-poc"
WRITER_PIP_RUN = "pip install --require-hashes --no-deps -r requirements-risk-cap-writer.txt"
DIRECT_DEPS = ("gspread", "google-auth", "requests")
FORBIDDEN_PKGS = ("pandas", "numpy", "streamlit", "pyarrow", "altair")


def _wf() -> str:
    return (REPO / WORKFLOW_REL).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# A1. 搬移
# ══════════════════════════════════════════════════════════════════════════
class TestMove:
    def test_new_package_no_barrel(self):
        assert (REPO / NEW_L1_REL).is_file() and not (REPO / OLD_L1_REL).exists()
        init = (REPO / "src/data/risk_cap/__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(init)
        assert len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr) \
            and isinstance(tree.body[0].value, ast.Constant), "只准 docstring（⛔ barrel／re-export）"

    def test_nothing_imports_old_path(self):
        files = only_tracked(REPO, [*REPO.rglob("*.py")], min_tracked=REPO_MIN_TRACKED, min_kept=200)
        hits = []
        for f in files:
            if f.relative_to(REPO).as_posix() == "tests/test_vn1_prehardening.py":
                continue
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(n, ast.ImportFrom) and n.module:
                    if n.module == "src.data.macro.risk_cap_history" or (
                            n.module == "src.data.macro" and any(a.name == "risk_cap_history" for a in n.names)):
                        hits.append(f.relative_to(REPO).as_posix())
                if isinstance(n, ast.Import) and any(a.name == "src.data.macro.risk_cap_history" for a in n.names):
                    hits.append(f.relative_to(REPO).as_posix())
        assert not hits, hits

    def test_old_path_string_gone_from_code(self):
        """程式與 workflow 不再以字串引用舊路徑（文件的歷史註記不算 —— 只掃 .py／.yml，且略過本檔）。"""
        files = only_tracked(REPO, [*REPO.rglob("*.py"), *REPO.rglob("*.yml")],
                             min_tracked=REPO_MIN_TRACKED, min_kept=200)
        hits = [f.relative_to(REPO).as_posix() for f in files
                if f.relative_to(REPO).as_posix() not in ("tests/test_vn1_prehardening.py", NEW_L1_REL)
                and (OLD_L1_REL in f.read_text(encoding="utf-8")
                     or "src.data.macro.risk_cap_history" in f.read_text(encoding="utf-8"))]
        assert not hits, hits


# ══════════════════════════════════════════════════════════════════════════
# A2. hash 鎖定檔
# ══════════════════════════════════════════════════════════════════════════
_REQ_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][0-9A-Za-z.+-]*) \\$")
_HASH_RE = re.compile(r"^    --hash=sha256:[0-9a-f]{64}( \\)?$")


def parse_lock(text: str) -> dict[str, tuple[str, int]]:
    """鎖定檔 → {套件名(小寫): (版本, hash 數)}。任何不是「註解／空行／`name==ver \\`／hash 行」的行 ⇒ AssertionError。"""
    out: dict[str, tuple[str, int]] = {}
    cur: str | None = None
    expect_hash = False
    for ln in text.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            assert not expect_hash, f"{cur} 的 hash 行中斷"
            cur = None if not ln.startswith("    #") else cur
            continue
        m = _REQ_RE.match(ln)
        if m:
            assert not expect_hash, f"{cur} 沒有 hash 就換下一個套件"
            cur = m.group(1).lower()
            assert cur not in out, cur
            out[cur] = (m.group(2), 0)
            expect_hash = True
            continue
        h = _HASH_RE.match(ln)
        assert h and cur is not None, f"不是釘版或 hash 行：{ln!r}"
        out[cur] = (out[cur][0], out[cur][1] + 1)
        expect_hash = ln.endswith("\\")
    assert not expect_hash
    return out


def _vt(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _range_from_requirements(name: str) -> tuple[str, str]:
    req = (REPO / "requirements.txt").read_text(encoding="utf-8")
    m = re.search(rf"^{re.escape(name)}>=([0-9.]+),<([0-9.]+)\s*$", req, flags=re.MULTILINE)
    assert m, name
    return m.group(1), m.group(2)


class TestLockFile:
    def test_every_package_pinned_and_hashed(self):
        pkgs = parse_lock((REPO / LOCK_REL).read_text(encoding="utf-8"))
        assert pkgs and all(n >= 1 for _, n in pkgs.values()), pkgs
        for bad in FORBIDDEN_PKGS:
            assert bad not in pkgs, bad

    def test_direct_deps_within_requirements_ranges(self):
        pkgs = parse_lock((REPO / LOCK_REL).read_text(encoding="utf-8"))
        in_lines = [ln for ln in (REPO / LOCK_IN_REL).read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.startswith("#")]
        req = (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()
        assert sorted(re.split(r"[><=]", ln)[0] for ln in in_lines) == sorted(DIRECT_DEPS)
        assert all(ln in req for ln in in_lines), "compile 輸入必須逐字等於 requirements.txt 同名行"
        for name in DIRECT_DEPS:
            lo, hi = _range_from_requirements(name)
            assert _vt(lo) <= _vt(pkgs[name][0]) < _vt(hi), (name, pkgs[name][0])

    def test_header_reproducible(self):
        text = (REPO / LOCK_REL).read_text(encoding="utf-8")
        for need in ("uv pip compile requirements-risk-cap-writer.in --generate-hashes --python-version 3.11",
                     "--python-platform x86_64-unknown-linux-gnu --exclude-newer 2026-10-06",
                     "2026-10-20", WRITER_PIP_RUN):
            assert need in text, need

    @pytest.mark.parametrize("swap", [
        (r"(\n[a-z0-9-]+==[^\n]+ \\\n)    --hash=sha256:[0-9a-f]{64} \\\n", r"\1"),       # 少一個 hash（仍合法）
        (r"\n(gspread)==([0-9.]+) \\\n", r"\n\1>=\2 \\\n"),                                     # 不是 ==
        (r"\n    --hash=sha256:[0-9a-f]{64}\n", "\n"),                                         # 某套件最後一個 hash 拿掉
    ])
    def test_mutations(self, swap):
        text = (REPO / LOCK_REL).read_text(encoding="utf-8")
        mut = re.sub(swap[0], swap[1], text, count=1)
        assert mut != text
        if swap[0].startswith(r"(\n[a-z0-9-]+==[^\n]+ \\\n)"):
            parse_lock(mut)                             # 只少一個 hash ⇒ 仍是合法鎖檔（對照組）
            return
        with pytest.raises(AssertionError):
            parse_lock(mut)

    def test_mutation_unhashed_package_red(self):
        text = (REPO / LOCK_REL).read_text(encoding="utf-8") + "pandas==2.2.0\n"
        with pytest.raises(AssertionError):
            parse_lock(text)


# ══════════════════════════════════════════════════════════════════════════
# A3. workflow 安裝方式
# ══════════════════════════════════════════════════════════════════════════
def assert_install_guards(text: str) -> None:
    jobs = _parse(text)["jobs"]
    w = jobs["production_write"]
    pips = [s["run"] for s in w["steps"] if "pip install" in s.get("run", "")]
    assert pips == [WRITER_PIP_RUN], pips
    code = "\n".join(ln for ln in _job_text(text, "production_write").splitlines() if not ln.lstrip().startswith("#"))
    assert "requirements.txt" not in code.replace(LOCK_REL, "")
    c = jobs["production_write_compute"]
    assert [s["run"] for s in c["steps"] if "pip install" in s.get("run", "")] == ["pip install -r requirements.txt"]


class TestWorkflowInstall:
    def test_guards(self):
        assert_install_guards(_wf())

    @pytest.mark.parametrize("old,new", [
        (WRITER_PIP_RUN, "pip install -r requirements.txt"),
        (WRITER_PIP_RUN, "pip install --no-deps -r requirements-risk-cap-writer.txt"),
        (WRITER_PIP_RUN, WRITER_PIP_RUN + " -r requirements.txt"),
    ])
    def test_mutation_turns_red(self, old, new):
        text = _wf()
        block = _job_text(text, "production_write")
        assert block.count(old) == 1
        with pytest.raises(AssertionError):
            assert_install_guards(text.replace(block, block.replace(old, new)))


# ══════════════════════════════════════════════════════════════════════════
# A4. 寫入路徑不載入 pandas／streamlit（子行程；閘門 exit 2）
# ══════════════════════════════════════════════════════════════════════════
def _clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("RISK_CAP_", "GOOGLE_APPLICATION_CREDENTIALS", "GITHUB_RUN_ID"))}
    env["PYTHONPATH"] = str(REPO)
    return env


class TestWritePathImports:
    @pytest.mark.parametrize("flag", ["--write", "--precheck", "--verify-written"])
    def test_script_flow_loads_no_heavy_modules(self, flag, tmp_path):
        rec = tmp_path / "rec.json"
        rec.write_text(json.dumps({"record": {}}), encoding="utf-8")
        r = subprocess.run([sys.executable, "-X", "importtime", str(REPO / "scripts/risk_cap_history_poc.py"),
                            flag, "--record", str(rec)], capture_output=True, text=True, timeout=120,
                           cwd=str(tmp_path), env=_clean_env())
        assert r.returncode == 2, (r.stdout[-500:], r.stderr[-500:])
        mods = {ln.split("|")[-1].strip() for ln in r.stderr.splitlines() if ln.startswith("import time:")}
        assert mods, "importtime 沒有輸出"
        heavy = sorted(m for m in mods if m.split(".")[0] in FORBIDDEN_PKGS)
        assert not heavy, heavy
        assert "src.data.risk_cap.history" in mods and "src.data.macro" not in mods

    def test_l1_import_sys_modules(self):
        code = ("import sys, src.data.risk_cap.history as h; "
                "print(sorted(m for m in sys.modules if m.split('.')[0] in "
                f"{FORBIDDEN_PKGS!r} or m.startswith('src.data.macro') or m.startswith('src.services')))")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
                           cwd=str(REPO), env=_clean_env())
        assert r.returncode == 0 and r.stdout.strip() == "[]", (r.stdout, r.stderr[-500:])


# ══════════════════════════════════════════════════════════════════════════
# C. 併發 group
# ══════════════════════════════════════════════════════════════════════════
def _touches_sheet_or_writer(job: dict) -> bool:
    for s in job["steps"]:
        if str(s.get("uses", "")).startswith("google-github-actions/auth@"):
            return True
        run = s.get("run", "")
        if "risk_cap_permission_test.py" in run or "--write" in run:
            return True
    return False


def assert_concurrency_guards(text: str) -> None:
    d = _parse(text)
    assert d["concurrency"] == {"group": WORKFLOW_GROUP, "cancel-in-progress": False}
    assert WORKFLOW_GROUP != SHEET_GROUP
    touching = [name for name, j in d["jobs"].items() if _touches_sheet_or_writer(j)]
    assert {"permission_test_writer", "permission_test_reader", "production_write"} <= set(touching), touching
    for name in touching:
        assert d["jobs"][name].get("concurrency") == {"group": SHEET_GROUP, "cancel-in-progress": False}, name
    for name, j in d["jobs"].items():
        if "concurrency" in j:
            assert j["concurrency"]["group"] == SHEET_GROUP and "${{" not in j["concurrency"]["group"], name
        assert "environment" not in j, f"{name}：⛔ 不得加 environment（客戶 Gate）"
    assert not re.search(r"^\s+environment:", text, flags=re.MULTILINE)


class TestConcurrency:
    def test_guards(self):
        assert_concurrency_guards(_wf())

    @pytest.mark.parametrize("job", ["permission_test_writer", "permission_test_reader", "production_write",
                                     "wif_auth_only"])
    def test_remove_group_turns_red(self, job):
        text = _wf()
        block = _job_text(text, job)
        old = f"    concurrency:\n      group: {SHEET_GROUP}\n      cancel-in-progress: false\n"
        assert block.count(old) == 1
        with pytest.raises(AssertionError):
            assert_concurrency_guards(text.replace(block, block.replace(old, "")))
        with pytest.raises(AssertionError):
            assert_concurrency_guards(text.replace(block, block.replace(SHEET_GROUP, "risk-cap-other")))

    def test_workflow_group_collision_turns_red(self):
        text = _wf()
        old = f"concurrency:\n  group: {WORKFLOW_GROUP}\n"
        assert text.count(old) == 1
        with pytest.raises(AssertionError):
            assert_concurrency_guards(text.replace(old, f"concurrency:\n  group: {SHEET_GROUP}\n"))

    def test_environment_added_turns_red(self):
        text = _wf()
        block = _job_text(text, "production_write")
        old = "    needs: production_write_compute\n"
        with pytest.raises(AssertionError):
            assert_concurrency_guards(text.replace(block, block.replace(
                old, old + "    environment: production-risk-cap\n")))


# ══════════════════════════════════════════════════════════════════════════
# 回修第 1 輪（2026-10-20）：Google API 請求逾時
# ══════════════════════════════════════════════════════════════════════════
class TestSheetsTimeout:
    def test_l0_constant_shape(self):
        import math

        from shared import risk_cap_history_policy as P
        t = P.SHEETS_HTTP_TIMEOUT_S
        assert isinstance(t, tuple) and len(t) == 2
        assert all(isinstance(x, float) and math.isfinite(x) and x > 0 for x in t)

    def test_authorized_client_sets_l0_timeout(self, monkeypatch):
        import gspread

        from shared import risk_cap_history_policy as P
        from src.data.risk_cap import history as L1H
        seen = []

        class _C:
            def set_timeout(self, timeout):
                seen.append(timeout)
        monkeypatch.setattr(gspread, "authorize", lambda creds: _C())
        assert isinstance(L1H._authorized_client(object()), _C)
        assert seen == [P.SHEETS_HTTP_TIMEOUT_S]

    def test_real_gspread_client_carries_timeout(self):
        """真的 `gspread.authorize`＋真的 google-auth 憑證物件（假 token、不發任何請求）：逾時落到 http_client，
        而 gspread 6.x 的 `HTTPClient.request` 以 `timeout=self.timeout` 傳給 requests。"""
        import inspect

        from google.oauth2.credentials import Credentials
        from gspread.http_client import HTTPClient

        from shared import risk_cap_history_policy as P
        from src.data.risk_cap import history as L1H
        client = L1H._authorized_client(Credentials(token="not-a-token"))
        assert client.http_client.timeout == P.SHEETS_HTTP_TIMEOUT_S
        assert "timeout=self.timeout" in inspect.getsource(HTTPClient.request).replace(" ", "")

    def test_reader_and_writer_both_use_helper(self):
        tree = ast.parse((REPO / NEW_L1_REL).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name in ("build_reader_client", "build_writer_client"):
            calls = {ast.unparse(n.func) for n in ast.walk(fns[name]) if isinstance(n, ast.Call)}
            assert "_authorized_client" in calls and "gspread.authorize" not in calls, name
        helper = ast.unparse(fns["_authorized_client"])
        assert "client.set_timeout(SHEETS_HTTP_TIMEOUT_S)" in helper
        # 全檔只有 helper 呼叫 gspread.authorize
        auth_calls = [f for f, fn in fns.items()
                      if any(isinstance(n, ast.Call) and ast.unparse(n.func) == "gspread.authorize" for n in ast.walk(fn))]
        assert auth_calls == ["_authorized_client"]

    def test_mutation_without_timeout_turns_red(self, monkeypatch):
        import gspread

        from tests.test_p01_macro_refresh import _mutated_module
        mut = _mutated_module(NEW_L1_REL, ("    client.set_timeout(SHEETS_HTTP_TIMEOUT_S)\n", ""))
        seen = []

        class _C:
            def set_timeout(self, timeout):
                seen.append(timeout)
        monkeypatch.setattr(gspread, "authorize", lambda creds: _C())
        mut._authorized_client(object())
        assert seen == []                       # 突變體沒設逾時 ⇒ 上面的正向測試會紅

    @pytest.mark.parametrize("exc_name", ["ReadTimeout", "ConnectTimeout", "Timeout"])
    def test_timeout_classified_as_api_error(self, exc_name):
        import requests.exceptions as rqe

        from shared import risk_cap_history_policy as P
        from src.data.risk_cap import history as L1H
        from src.services import risk_cap_history_reader_service as R
        from tests.test_vn1_production_wiring import _factory_for, _FakeWS, _secrets
        exc = getattr(rqe, exc_name)("sheet-id-leak")
        with pytest.raises(L1H.HistoryApiError) as ei:
            L1H.read_history_values(_FakeWS([], exc=exc))
        assert ei.value.error_type == exc_name and "leak" not in str(ei.value)
        R.clear_read_cache()
        res = R.read_history(expected_date="2026-10-14", now=__import__("tests.test_batch_z64", fromlist=["NOW"]).NOW,
                             secrets=_secrets(), client_factory=_factory_for(_FakeWS([], exc=exc)))
        R.clear_read_cache()
        assert res.status == P.READ_STATUS_API_ERROR and exc_name in res.detail
