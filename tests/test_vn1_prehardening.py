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
   ~~⛔ 任何 job 都沒有 `environment:`（引用不存在的 environment 會自動建一個沒有保護的 —— 那是客戶 Gate）。~~
   📌 2026-10-21（DEC-066 C Step 2；有意識的變更，不是漏刪）：客戶已在 GitHub UI 建立 Environment `production-risk-cap`
   （DEC-066 C Step 1 完成）⇒ 改為「**只有** `production_write` 掛 `environment: production-risk-cap`（job 層純字串）；
   其他 job、R5 檔、`.github/workflows/` 其他所有 workflow 一律沒有 `environment` 鍵、也不得出現該名稱（註解除外）」。
   舊句的理由（⛔ 先引用不存在的 environment）仍成立；被取代的只是「尚未建立」這個前提。完整守衛見 E 節。
E. DEC-066 C Step 2（2026-10-21）：environment 只在 `production_write`；該 job 鍵集合＝原集合＋`environment`、
   步驟名稱序列與 main `8995729d` 逐項相同；production 路徑（寫入腳本、L1、寫入 job steps）⛔ 沒有
   delete／clear／rollback／retry／continue-on-error（DEC-066 E FAIL-STOP）。
突變自驗（in-test）：缺 hash、寫入 job 改裝 requirements.txt、拿掉某個 job 的 group、group 改名、workflow group 撞名 ⇒ 轉紅；
（E 節）environment 加到其他 job／R5／其他 workflow、移除、改名、改 mapping／expression、步驟順序變動、
加入 continue-on-error／rollback ⇒ 轉紅。
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
from tests.test_vn1_wif_auth_only import _job_text, _parse, _yaml_lines

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
    # 📌 2026-10-21（DEC-066 C Step 2；有意識的變更，不是漏刪）：
    #   ~~assert "environment" not in j（任何 job 都不得加 environment；客戶 Gate）~~ 與
    #   ~~assert not re.search(r"^\s+environment:", text, flags=re.MULTILINE)~~
    #   —— 客戶已建立 Environment（Step 1）⇒ 改為「只有 production_write 掛 `production-risk-cap`」。
    #   完整守衛在 E 節 `assert_environment_guards`；此處照舊呼叫，讓本節的併發突變測試同時守住 environment。
    assert_environment_guards(text)


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

    # 📌 2026-10-21（DEC-066 C Step 2；有意識的變更，不是漏刪）：原 `test_environment_added_turns_red`
    #   （把 environment 加到 production_write ⇒ 紅）語意反轉 —— production_write 現在**必須**有。
    #   改為：加到別的 job ⇒ 紅、從 production_write 拿掉 ⇒ 紅（經由本節守衛；細項突變見 E 節）。
    @pytest.mark.parametrize("job", ["wif_auth_only", "permission_test_writer", "production_write_compute"])
    def test_environment_added_elsewhere_turns_red(self, job):
        with pytest.raises(AssertionError):
            assert_concurrency_guards(_add_env_to_job(_wf(), job))

    def test_environment_removed_turns_red(self):
        with pytest.raises(AssertionError):
            assert_concurrency_guards(_remove_env(_wf()))


# ══════════════════════════════════════════════════════════════════════════
# E. DEC-066 C Step 2（2026-10-21）：Environment wiring —— 只有 production_write 掛 environment
# ══════════════════════════════════════════════════════════════════════════
# 有意識地更新守衛（理由＝DEC-066 C Step 2）：客戶已在 GitHub UI 建立 Environment `production-risk-cap`
# （Step 1；總管轉述客戶畫面：Required reviewers＝客戶本人、Prevent self-review＝OFF、Wait timer＝OFF、
# Admin bypass＝OFF、Selected branches → main、tags 0、secrets 0、variables 0）。DEC-066 C ~~只准**真正有寫入能力**
# 的 job~~ 只准**正式寫入 job**（`production_write`：needs compute、有 id-token、執行 `--write`）引用；
# `permission_test_writer` 雖能以 writer 身分 append／刪測試列（P1），依 DEC-066 C 範圍不掛（回修第 1 輪 2026-10-21，
# 有意識的變更，不是漏刪）；compute／dry-run／wif_auth_only／其他權限驗證／R4 job 與 R5 檔一律不得掛
# （掛上會改變它們的 OIDC `sub`，且不在本批授權範圍）。⚠️ Step 3 前，Environment 只擋 production_write。
# ⛔ 本節不碰 WIF condition（Step 3）、不碰 `PRODUCTION_WRITE_APPROVED`（Step 4）。
ENV_NAME = "production-risk-cap"
ENV_JOB = "production_write"
ENV_LINE = f"    environment: {ENV_NAME}"
R5_NAME = "risk_cap_wif_negative_r5.yml"
_ENV_KEY_RE = re.compile(r"^[ \t]*(?:-[ \t]+)?environment[ \t]*:", flags=re.MULTILINE)

#: production_write 在本批之前（main `8995729d`）的 job 鍵集合；本批只多 `environment`。
PRODUCTION_WRITE_KEYS_BEFORE = {"if", "needs", "runs-on", "timeout-minutes", "permissions", "concurrency", "steps"}
#: production_write 的步驟名稱序列（main `8995729d` 逐字；本批 ⛔ 不得變動任何一步）。
PRODUCTION_WRITE_STEP_NAMES = [
    "Checkout Repository",
    "Production write gate (must pass before any auth)",
    "Set up Python",
    "Install writer deps (hash-locked)",
    "Download record JSON",
    "Verify record artifact sha256 (must match compute job)",
    "Authenticate to Google Cloud (WIF, no key)",
    "Write record (gate first, WIF writer only)",
]
#: DEC-066 E（FAIL-STOP）：production 路徑不得出現的自動補救字樣（小寫比對）。
#: ⛔ 只掃 production 路徑；權限驗證腳本 `scripts/risk_cap_permission_test.py` 的 P1 測試列刪除（deleteDimension）
#: 是既有、經 DEC-065／規格第 5 節核准的權限驗證清理，**刻意排除**、不在本守衛範圍。
PRODUCTION_PATH_FILES = ("scripts/risk_cap_history_poc.py", NEW_L1_REL)
FORBIDDEN_AUTO_RECOVERY = ("delete", "clear", "rollback", "retry", "continue-on-error")


def _full_line_code(text: str) -> str:
    """只去掉整行註解（行尾註解仍算 code —— 比 `_yaml_lines` 更嚴，寧可誤紅）。"""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def _other_workflows() -> dict[str, str]:
    files = sorted((REPO / ".github/workflows").glob("*.y*ml"))
    out = {f.name: f.read_text(encoding="utf-8") for f in files if f.name != Path(WORKFLOW_REL).name}
    assert R5_NAME in out and len(out) >= 10, sorted(out)
    return out


def _add_env_to_job(text: str, job: str, line: str = ENV_LINE) -> str:
    block = _job_text(text, job)
    old = "    runs-on: ubuntu-latest\n"
    assert block.count(old) == 1, job
    return text.replace(block, block.replace(old, f"{line}\n{old}"))


def _remove_env(text: str) -> str:
    assert text.count(ENV_LINE + "\n") == 1
    return text.replace(ENV_LINE + "\n", "")


def assert_environment_guards(text: str, others: dict[str, str] | None = None) -> None:
    d = _parse(text)
    assert "environment" not in d
    jobs = d["jobs"]
    env = jobs[ENV_JOB].get("environment")
    assert isinstance(env, str) and env == ENV_NAME, env          # 純字串；⛔ mapping／expression／別的名字
    for name, j in jobs.items():
        if name != ENV_JOB:
            assert "environment" not in j, f"{name}：⛔ 只有 {ENV_JOB} 可以掛 environment（DEC-066 C Step 2）"
        for s in j["steps"]:
            assert "environment" not in s, name
    code = _full_line_code(text)
    assert len(_ENV_KEY_RE.findall(code)) == 1, _ENV_KEY_RE.findall(code)
    wt = _job_text(text, ENV_JOB)
    assert [ln for ln in wt.splitlines() if ln == ENV_LINE] == [ENV_LINE]    # job 層（4 格縮排）恰好一行
    assert code.count(ENV_NAME) == 1 and _full_line_code(wt).count(ENV_NAME) == 1
    others = _other_workflows() if others is None else others
    for fname, t in others.items():
        c = _full_line_code(t)
        assert not _ENV_KEY_RE.search(c), f"{fname}：⛔ 不得有 environment（DEC-066 C Step 2 只准 {ENV_JOB}）"
        assert ENV_NAME not in c, fname


def assert_production_write_shape(text: str) -> None:
    w = _parse(text)["jobs"][ENV_JOB]
    assert set(w) == PRODUCTION_WRITE_KEYS_BEFORE | {"environment"}, set(w)
    assert [s.get("name") for s in w["steps"]] == PRODUCTION_WRITE_STEP_NAMES


def assert_no_auto_recovery(text: str, sources: dict[str, str] | None = None) -> None:
    sources = {rel: (REPO / rel).read_text(encoding="utf-8") for rel in PRODUCTION_PATH_FILES} \
        if sources is None else sources
    for rel, src in sources.items():
        low = src.lower()
        for bad in FORBIDDEN_AUTO_RECOVERY:
            assert bad not in low, (rel, bad)
    wcode = "\n".join(c for _, _, c in _yaml_lines(_job_text(text, ENV_JOB))).lower()
    for bad in FORBIDDEN_AUTO_RECOVERY:
        assert bad not in wcode, (ENV_JOB, bad)


def _plain_red(fn, *args) -> None:
    """突變必須被**守衛本身**擋下（純 AssertionError），不是被解析器的不支援語法擋下。"""
    with pytest.raises(AssertionError) as ei:
        fn(*args)
    assert type(ei.value) is AssertionError, repr(ei.value)


class TestEnvironmentWiring:
    def test_guards(self):
        assert_environment_guards(_wf())

    def test_shape_unchanged(self):
        assert_production_write_shape(_wf())

    def test_no_auto_recovery(self):
        assert_no_auto_recovery(_wf())

    def test_r5_and_others_scanned(self):
        others = _other_workflows()
        assert "risk_cap_wif_negative_r5.yml" in others and "pr-check.yml" in others

    @pytest.mark.parametrize("job", ["poc-dry-run", "wif_auth_only", "permission_test_branch_guard",
                                     "permission_test_writer", "permission_test_reader", "wif_negative_r4",
                                     "production_write_compute"])
    def test_env_on_other_job_turns_red(self, job):
        _plain_red(assert_environment_guards, _add_env_to_job(_wf(), job))

    def test_env_removed_turns_red(self):
        _plain_red(assert_environment_guards, _remove_env(_wf()))
        _plain_red(assert_production_write_shape, _remove_env(_wf()))

    @pytest.mark.parametrize("new", [
        "    environment: production-risk-cap-x",
        "    environment: production",
        "    environment: ${{ 'production-risk-cap' }}",
        "    environment:\n      name: production-risk-cap",
        "    environment:\n      name: production-risk-cap\n      url: https://example.invalid",
    ])
    def test_env_renamed_or_reshaped_turns_red(self, new):
        text = _wf()
        assert text.count(ENV_LINE + "\n") == 1
        _plain_red(assert_environment_guards, text.replace(ENV_LINE + "\n", new + "\n"))

    def test_env_on_r5_turns_red(self):
        others = _other_workflows()
        r5 = others[R5_NAME]
        old = "    runs-on: ubuntu-latest\n"
        assert r5.count(old) == 1
        others[R5_NAME] = r5.replace(old, ENV_LINE + "\n" + old)
        _plain_red(assert_environment_guards, _wf(), others)

    @pytest.mark.parametrize("extra", [
        "\n  other:\n    environment: production-risk-cap\n",
        "\n  other:\n    environment: staging\n",
        "\n# ok comment production-risk-cap\nenv:\n  X: production-risk-cap\n",
    ])
    def test_env_in_other_workflow_turns_red(self, extra):
        others = _other_workflows()
        others["update_macro_history.yml"] = others["update_macro_history.yml"] + extra
        _plain_red(assert_environment_guards, _wf(), others)

    def test_comment_mention_in_other_workflow_is_allowed(self):
        """對照組：註解提到名稱不算（只掃 code）。"""
        others = _other_workflows()
        others["update_macro_history.yml"] = others["update_macro_history.yml"] + "\n# production-risk-cap\n"
        assert_environment_guards(_wf(), others)

    def test_step_order_change_turns_red(self):
        text = _wf()
        a = "      - name: Set up Python\n"
        block = _job_text(text, ENV_JOB)
        assert block.count(a) == 1
        moved = block.replace(a, "      - name: Set up Python (moved)\n")
        _plain_red(assert_production_write_shape, text.replace(block, moved))

    def test_extra_job_key_turns_red(self):
        text = _wf()
        old = ENV_LINE + "\n"
        _plain_red(assert_production_write_shape, text.replace(old, old + "    continue-on-error: true\n"))

    def test_continue_on_error_in_write_step_turns_red(self):
        text = _wf()
        name = "      - name: Write record (gate first, WIF writer only)\n"
        assert text.count(name) == 1
        _plain_red(assert_no_auto_recovery, text.replace(name, name + "        continue-on-error: true\n"))

    @pytest.mark.parametrize("snippet", ["\ndef _rollback():\n    pass\n", "\nfor _retry in range(3):\n    pass\n",
                                         "\nws.batch_clear(['A2:T2'])\n", "\nws.delete_rows(2)\n"])
    def test_auto_recovery_in_sources_turns_red(self, snippet):
        sources = {rel: (REPO / rel).read_text(encoding="utf-8") for rel in PRODUCTION_PATH_FILES}
        sources[PRODUCTION_PATH_FILES[0]] += snippet
        _plain_red(assert_no_auto_recovery, _wf(), sources)

    # ~~`test_approval_flag_still_false`~~ —— 📌 2026-10-21（DEC-066 A，Step 4 子步驟 1；有意識的變更，不是漏刪）：
    #   客戶核准一次性旗標 PR ⇒ 改斷言 True；首次寫入嘗試後下一個 PR 改回 False，本測試同步改回。
    def test_approval_flag_approved_for_first_write(self):
        from shared import risk_cap_history_policy as P
        assert P.PRODUCTION_WRITE_APPROVED is True


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
