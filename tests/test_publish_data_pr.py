"""scripts/publish_data_pr.py 測試：tmp git repo + 本機 bare origin + mock gh，不碰網路。"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

import os

_SPEC = importlib.util.spec_from_file_location(
    "publish_data_pr", os.environ.get("PDP_PATH") or Path(__file__).resolve().parents[1] / "scripts" / "publish_data_pr.py")
pdp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pdp)

BRANCH = "auto/data-t"


def _sh(cwd, *cmd):
    """本測試以 tmp git repo＋本機 bare origin 驗證真實 git 行為，無純 Python 替代；Windows 開發者需安裝 git。"""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)  # portability-ok
    assert r.returncode == 0, (cmd, r.stderr)
    return r.stdout.strip()


class Rec:
    """記錄所有呼叫；git 走真的 repo，gh 走腳本化回應。"""

    def __init__(self, pr_open=False, fail_create=False, fail_dispatch=False):
        self.calls: list[list[str]] = []
        self.pr_open, self.fail_create, self.fail_dispatch = pr_open, fail_create, fail_dispatch

    def __call__(self, cmd, cwd=None, input=None, binary=False):
        self.calls.append(list(cmd))
        if cmd[0] == "gh":
            if cmd[1:3] == ["pr", "list"]:
                return pdp.Result(0, json.dumps([{"number": 7}] if self.pr_open else []), "")
            if cmd[1:3] == ["pr", "create"]:
                return pdp.Result(1 if self.fail_create else 0, "", "boom" if self.fail_create else "")
            if cmd[1:3] == ["workflow", "run"]:
                return pdp.Result(1 if self.fail_dispatch else 0, "", "")
            raise AssertionError(cmd)
        return pdp.default_runner(cmd, cwd, input, binary)

    def has(self, *tokens):
        return [c for c in self.calls if all(t in c for t in tokens)]


def _df(dates, fetched="2026-01-01T00:00:00Z", extra=0.0):
    return pd.DataFrame({"date": dates, "v": [1.0 + extra + i for i in range(len(dates))],
                         "fetched_at": fetched})


def _write_pq(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


@pytest.fixture
def env(tmp_path):
    origin = tmp_path / "origin.git"
    _sh(tmp_path, "git", "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    _sh(tmp_path, "git", "clone", "-q", str(origin), str(work))
    _sh(work, "git", "config", "user.name", "t")
    _sh(work, "git", "config", "user.email", "t@t")
    d = work / "data_cache"
    d.mkdir()
    (d / "metadata.json").write_text(json.dumps(
        {"updated_at": "A", "datasets": {"x": {"last_error": None, "row_count": 2}}}), encoding="utf-8")
    _write_pq(d / "x.parquet", _df(["2026-01-01", "2026-01-02"]))
    _sh(work, "git", "add", "-A")
    _sh(work, "git", "commit", "-qm", "base")
    _sh(work, "git", "branch", "-M", "main")
    _sh(work, "git", "push", "-q", "-u", "origin", "main")
    return work, origin


def _args(**kw):
    base = dict(job="t", paths=["data_cache/"], commit_msg="msg", observation_date=None,
                force_add=False, dry_run=False)
    base.update(kw)
    return type("A", (), base)()


def _run(work, rec, **kw):
    return pdp.publish(_args(**kw), pdp.Publisher(rec, str(work), log=lambda *_: None))


def _meta(work, **over):
    p = work / "data_cache" / "metadata.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m.update({k: v for k, v in over.items() if k != "last_error"})
    if "last_error" in over:
        m["datasets"]["x"]["last_error"] = over["last_error"]
    p.write_text(json.dumps(m), encoding="utf-8")


def _no_forbidden(rec):
    for c in rec.calls:
        assert not any(t.startswith("--force") or t == "-f" and "push" in c for t in c), c
        if "push" in c:
            assert not any(t in ("main", "HEAD:main") or t.startswith("+") for t in c), c
            assert BRANCH in c
        assert "rebase" not in c


# ── 實質變更判定 ──
def test_only_updated_at_changes_is_noop(env):
    work, _ = env
    _meta(work, updated_at="B")
    rec = Rec()
    assert _run(work, rec) == 0
    assert not rec.has("gh") and not rec.has("push")
    assert _sh(work, "git", "status", "--porcelain") == ""  # 工作樹已還原


def test_last_error_change_is_substantive(env):
    work, _ = env
    _meta(work, updated_at="B", last_error="來源失敗")
    rec = Rec()
    assert _run(work, rec) == 0
    assert rec.has("git", "push")
    assert rec.has("gh", "create")


def test_parquet_same_content_different_bytes_is_noop(env):
    work, _ = env
    # 只改 fetched_at 欄 + 不同 row group 寫法 → 位元組不同、內容相同
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02"], fetched="2099-01-01"))
    rec = Rec()
    assert _run(work, rec) == 0
    assert not rec.has("push")


def test_parquet_new_row_is_substantive(env):
    work, _ = env
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    rec = Rec()
    assert _run(work, rec) == 0
    assert rec.has("push")


def test_unit_functions():
    a = json.dumps({"updated_at": 1, "k": 1}).encode()
    assert not pdp.json_substantive_change("z.json", a, json.dumps({"updated_at": 2, "k": 1}).encode())
    assert pdp.json_substantive_change("z.json", a, json.dumps({"updated_at": 2, "k": 2}).encode())
    assert pdp.json_substantive_change("z.json", a, json.dumps({"updated_at": 1, "k": 1, "new": 0}).encode())  # 未知鍵=實質
    assert pdp.is_substantive("f.bin", "M", b"1", b"2") and not pdp.is_substantive("f.bin", "M", b"1", b"1")
    assert pdp.is_substantive("f.bin", "A", None, b"1")


# ── 分支與 PR ──
def test_new_branch_pushes_normally_and_never_main_or_force(env):
    work, origin = env
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    rec = Rec()
    _run(work, rec)
    _no_forbidden(rec)
    assert BRANCH in _sh(origin, "git", "branch", "--list")
    assert _sh(origin, "git", "rev-parse", "main") == _sh(work, "git", "rev-parse", "origin/main")  # main 未動
    dispatch = rec.has("gh", "workflow", "run")[0]
    assert dispatch[-3:] == ["pr-check.yml", "--ref", BRANCH]


def test_existing_branch_takes_merge_path_without_force(env):
    work, origin = env
    # day1：開分支
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    _run(work, Rec())
    # main 前進（無衝突的別檔）
    _sh(work, "git", "checkout", "-q", "main")
    (work / "other.txt").write_text("x", encoding="utf-8")
    _sh(work, "git", "add", "other.txt")
    _sh(work, "git", "commit", "-qm", "main moves")
    _sh(work, "git", "push", "-q", "origin", "main")
    # day2：以 main 為基底只產出 01-04（不含分支上的 01-03）
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-04"]))
    rec = Rec(pr_open=True)
    assert _run(work, rec) == 0
    _no_forbidden(rec)
    assert rec.has("git", "merge", "origin/main")
    assert not rec.has("gh", "create")  # 已有開啟 PR 不重複建立
    assert rec.has("gh", "workflow", "run")  # 新 head 仍 dispatch
    got = pd.read_parquet(io.BytesIO(_sh_bytes(origin, f"{BRANCH}:data_cache/x.parquet")))
    assert sorted(got["date"].tolist()) == ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]  # 沒丟分支上的 01-03
    assert "other.txt" in _sh(origin, "git", "ls-tree", "-r", "--name-only", BRANCH)  # main 已併入


def _sh_bytes(cwd, spec):
    """本測試以 tmp git repo＋本機 bare origin 驗證真實 git 行為，無純 Python 替代；Windows 開發者需安裝 git。"""
    return subprocess.run(["git", "show", spec], cwd=cwd, capture_output=True, check=True).stdout  # portability-ok


def test_merge_conflict_fails_loud_and_does_not_push(env):
    work, origin = env
    _meta(work, updated_at="B", last_error="e1")
    _run(work, Rec())  # 分支上 metadata 改成 e1
    _sh(work, "git", "checkout", "-q", "main")
    (work / "data_cache" / "metadata.json").write_text(json.dumps({"conflict": "main"}), encoding="utf-8")
    _sh(work, "git", "commit", "-qam", "main edits meta")
    _sh(work, "git", "push", "-q", "origin", "main")
    before = _sh(origin, "git", "rev-parse", BRANCH)
    _meta_data = {"updated_at": "C", "datasets": {"x": {"last_error": "e2", "row_count": 2}}}
    (work / "data_cache" / "metadata.json").write_text(json.dumps(_meta_data), encoding="utf-8")
    rec = Rec()
    with pytest.raises(pdp.PublishError, match="合併衝突"):
        _run(work, rec)
    assert not rec.has("git", "push") and not rec.has("gh")
    assert _sh(origin, "git", "rev-parse", BRANCH) == before


def test_pr_not_duplicated_when_open(env):
    work, _ = env
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    rec = Rec(pr_open=True)
    _run(work, rec)
    assert not rec.has("gh", "create")


def test_pr_create_failure_exit_1_with_hint(env, capsys):
    work, _ = env
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    rec = Rec(fail_create=True)
    with pytest.raises(pdp.PublishError, match="Allow GitHub Actions to create and approve pull requests"):
        _run(work, rec)
    # CLI 層轉 exit 1 由 test_main_returns_1_on_publish_error 驗


def test_main_returns_1_on_publish_error(monkeypatch, capsys):
    def boom(*a, **k):
        raise pdp.PublishError("分支已推送、PR/check 未建立；x")
    monkeypatch.setattr(pdp, "publish", boom)
    assert pdp.main(["--job", "t", "--paths", "p", "--commit-msg", "m"]) == 1
    assert "PR/check 未建立" in capsys.readouterr().err


def test_dispatch_failure_exit_1(env):
    work, _ = env
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    with pytest.raises(pdp.PublishError, match="actions: write"):
        _run(work, Rec(fail_dispatch=True))


def test_dry_run_writes_nothing(env):
    work, origin = env
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    before_status = _sh(work, "git", "status", "--porcelain")
    before_head = _sh(work, "git", "rev-parse", "HEAD")
    rec = Rec()
    assert _run(work, rec, dry_run=True) == 0
    assert _sh(work, "git", "status", "--porcelain") == before_status
    assert _sh(work, "git", "rev-parse", "HEAD") == before_head
    assert _sh(work, "git", "branch", "--list") .count(BRANCH) == 0
    assert not rec.has("gh") and not rec.has("push") and not rec.has("commit") and not rec.has("add")
    assert BRANCH not in _sh(origin, "git", "branch", "--list")


def test_guard_blocks_force_main_rebase():
    p = pdp.Publisher(Rec(), None)
    for bad in (["git", "push", "--force", "origin", BRANCH], ["git", "push", "--force-with-lease", "origin", BRANCH],
                ["git", "push", "origin", "main"], ["git", "push", "origin", f"+{BRANCH}"],
                ["git", "push", "origin", "HEAD:main"], ["git", "rebase", "origin/main"]):
        with pytest.raises(pdp.PublishError):
            p.run(bad)


# ── 時間欄位不偽造 ──
def test_pr_body_times_not_fabricated():
    body = pdp.build_pr_body("t", ["a"], None, pdp.collect_fetched_at({"a.json": b"{}"}))
    assert "n/a（未帶入）" in body and "n/a（來源未提供）" in body and "n/a（資料檔內無 fetched_at）" in body
    assert "未經人工審閱不得合併" in body
    body2 = pdp.build_pr_body("t", ["a"], "2026-11-05", "2026-11-05T09:40:00+00:00")
    assert "2026-11-05" in body2 and "2026-11-05T09:40:00+00:00" in body2 and "n/a（來源未提供）" in body2


def test_collect_fetched_at_from_real_data():
    buf = io.BytesIO()
    _df(["2026-01-01"], fetched="2026-05-05T00:00:00Z").to_parquet(buf, index=False)
    assert pdp.collect_fetched_at({"x.parquet": buf.getvalue()}) == "2026-05-05T00:00:00Z"


# ───────────────── QA 缺陷修正（D1~D6）─────────────────
def _pq_bytes(df):
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


@pytest.mark.parametrize("bad", [
    ["git", "push", "-fu", "origin", BRANCH], ["git", "push", "-uf", "origin", BRANCH],
    ["git", "push", "origin", f"{BRANCH}:main"], ["git", "push", "--delete", "origin", BRANCH],
    ["git", "push", "--prune", "origin", BRANCH], ["git", "push", "origin", "HEAD:main"],
    ["git", "push", "-u", "origin", BRANCH, "extra"], ["git", "push"],
    ["git", "reset", "--hard", "HEAD"], ["git", "update-ref", "-d", "x"], ["git", "send-pack", "x"],
    ["git", "pull", "--rebase"], ["git", "-c", "a=b", "push", "origin", "main"],
    ["gh", "pr", "merge", "7"], ["gh", "api", "-X", "DELETE", "repos/o/r/branches/main/protection"],
])
def test_d1_guard_whitelist_rejects(bad):
    with pytest.raises(pdp.PublishError):
        pdp._guard(bad)


@pytest.mark.parametrize("good", [
    ["git", "push", "-u", "origin", BRANCH], ["git", "push", "origin", BRANCH],
    ["git", "commit", "-m", "push"], ["git", "commit", "-m", "rebase main push --force"],
    ["git", "-c", "user.name=x", "commit", "-m", "git push origin main"], ["git", "reset", "-q", "--", "p"],
    ["gh", "pr", "list", "--head", BRANCH], ["gh", "api", "repos/o/r/pulls"],
])
def test_d1_guard_allows_normal_and_no_false_positive(good):
    pdp._guard(good)


def test_d1_job_name_validated():
    for bad in ("Bad", "-x", "a/b", "a b", "a_b", ""):
        with pytest.raises(SystemExit):
            pdp.parse_args(["--job", bad, "--paths", "p", "--commit-msg", "m"])
    assert pdp.parse_args(["--job", "macro-history", "--paths", "p", "--commit-msg", "m"]).job == "macro-history"


def test_d2_same_day_nan_does_not_overwrite_old_value():
    base = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "v": [1.0, 2.0]})
    new = pd.DataFrame({"date": ["2026-01-02"], "v": [float("nan")]})
    logs = []
    out = pd.read_parquet(io.BytesIO(pdp.union_parquet_by_date(_pq_bytes(base), _pq_bytes(new), logs.append)))
    assert out.set_index("date")["v"].to_dict() == {"2026-01-01": 1.0, "2026-01-02": 2.0}
    assert any("2026-01-02" in l and "1 列" in l for l in logs)


def test_d2_same_day_new_value_wins():
    base = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "v": [1.0, 2.0]})
    new = pd.DataFrame({"date": ["2026-01-02"], "v": [3.0]})
    out = pd.read_parquet(io.BytesIO(pdp.union_parquet_by_date(_pq_bytes(base), _pq_bytes(new))))
    assert out.set_index("date")["v"].to_dict() == {"2026-01-01": 1.0, "2026-01-02": 3.0}


def test_d4_columns_only_in_branch_are_kept():
    base = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "v": [1.0, 2.0], "extra": ["a", "b"]})
    new = pd.DataFrame({"date": ["2026-01-02", "2026-01-03"], "v": [5.0, 6.0]})
    out = pd.read_parquet(io.BytesIO(pdp.union_parquet_by_date(_pq_bytes(base), _pq_bytes(new))))
    assert "extra" in out.columns
    r = out.set_index("date")["extra"].to_dict()
    assert r["2026-01-01"] == "a" and r["2026-01-02"] == "b" and pd.isna(r["2026-01-03"])  # 同日舊值回填


def test_d4_dtype_conflict_fails_loud():
    base = pd.DataFrame({"date": ["2026-01-01"], "v": ["text"]})
    new = pd.DataFrame({"date": ["2026-01-02"], "v": [1.0]})
    with pytest.raises(pdp.PublishError, match="型別衝突"):
        pdp.union_parquet_by_date(_pq_bytes(base), _pq_bytes(new))


def test_d5_json_strict_types_and_nested_keys():
    a = json.dumps({"k": True}).encode()
    assert pdp.json_substantive_change("z.json", a, json.dumps({"k": 1}).encode())  # bool != int
    assert pdp.json_substantive_change("z.json", json.dumps({"k": 1}).encode(), json.dumps({"k": 1.0}).encode())
    n1 = json.dumps({"a": {"updated_at": 1}}).encode()
    n2 = json.dumps({"a": {"updated_at": 2}}).encode()
    assert pdp.json_substantive_change("z.json", n1, n2)  # 未登記檔：巢狀視為實質
    assert not pdp.json_substantive_change("data_cache/metadata.json", n1, n2)  # 已登記檔：照舊任意深度
    assert not pdp.json_substantive_change("z.json", json.dumps({"updated_at": 1}).encode(),
                                           json.dumps({"updated_at": 2}).encode())  # 頂層仍忽略


def test_d3_ignored_directory_entries_do_not_crash_on_existing_branch_path(env):
    work, origin = env
    (work / ".gitignore").write_text("data_cache/ign/\n", encoding="utf-8")
    _sh(work, "git", "add", ".gitignore")
    _sh(work, "git", "commit", "-qm", "ignore")
    _sh(work, "git", "push", "-q", "origin", "main")
    # 先開分支，讓第二輪走 remote_has 路徑
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    _run(work, Rec(), force_add=True)
    _sh(work, "git", "checkout", "-q", "main")
    ign = work / "data_cache" / "ign"
    (ign / "__pycache__").mkdir(parents=True)
    (ign / "a.json").write_text("{}", encoding="utf-8")
    (ign / "__pycache__" / "m.pyc").write_bytes(b"x")
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-04"]))
    rec = Rec(pr_open=True)
    assert _run(work, rec, force_add=True) == 0
    tree = _sh(origin, "git", "ls-tree", "-r", "--name-only", BRANCH)
    assert "data_cache/ign/a.json" in tree and "__pycache__" not in tree
    # 不 force_add：目錄項被跳過，不當機
    _sh(work, "git", "checkout", "-q", "main")
    assert _run(work, Rec(pr_open=True), force_add=False) == 0


def test_d6_new_pr_dispatches_even_without_new_push(env):
    work, _ = env
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    with pytest.raises(pdp.PublishError):
        _run(work, Rec(fail_create=True))  # 分支已推送、PR 建立失敗
    _sh(work, "git", "checkout", "-q", "main")
    _write_pq(work / "data_cache" / "x.parquet", _df(["2026-01-01", "2026-01-02", "2026-01-03"]))
    rec = Rec(pr_open=False)  # 第二輪：內容與分支相同 → 無新 push，但 PR 為新建
    _run(work, rec)
    assert not rec.has("git", "push")
    assert rec.has("gh", "pr", "create") and rec.has("gh", "workflow", "run")
