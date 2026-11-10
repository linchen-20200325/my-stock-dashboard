"""Issue #1116：update_etf_managers.yml 改走「資料分支 + PR」（取代裸 `git push` main，GH006）。

涵蓋（全部合成資料、tmp git repo + 本機 bare origin + mock gh，零網路、零祕密值）：
  A. publish_data_pr 對 src/data/etf/etf_managers.json 的實質／揮發判定
  B. 冪等、既有未合併資料 PR、fail-closed、只 stage 白名單路徑、輸出 bytes 不被改寫
  C. workflow YAML 靜態守衛（無裸 push／force／origin main、permissions、triggers、祕密名單、fetch 步驟不變）
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "update_etf_managers.yml"
JSON_REL = "src/data/etf/etf_managers.json"
BRANCH = "auto/data-etf-managers"
SENTINEL = "SENTINEL-PROXY-VALUE-xyz"

_SPEC = importlib.util.spec_from_file_location("publish_data_pr", ROOT / "scripts" / "publish_data_pr.py")
pdp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pdp)


def _sh(cwd, *cmd):
    """tmp git repo＋本機 bare origin 驗證真實 git 行為，無純 Python 替代。"""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)  # portability-ok
    assert r.returncode == 0, (cmd, r.stderr)
    return r.stdout.strip()


class Rec:
    """記錄所有呼叫；git 走真的 repo，gh 走腳本化回應。fail 指定哪個 gh/git 子命令回非 0。"""

    def __init__(self, pr_open=False, fail=()):
        self.calls: list[list[str]] = []
        self.pr_open, self.fail = pr_open, set(fail)
        self.pr_body = "開頭\n人工補註：KEEP-ME\n"

    def __call__(self, cmd, cwd=None, input=None, binary=False):
        self.calls.append(list(cmd))
        if cmd[0] == "gh":
            key = cmd[2] if len(cmd) > 2 else ""
            if key in self.fail:
                return pdp.Result(1, "", "boom")
            if cmd[1:3] == ["pr", "list"]:
                return pdp.Result(0, json.dumps([{"number": 7}] if self.pr_open else []), "")
            if cmd[1:3] == ["pr", "view"]:
                return pdp.Result(0, json.dumps({"body": self.pr_body}), "")
            if cmd[1:3] in (["pr", "create"], ["pr", "edit"]):
                return pdp.Result(0, "", "")
            raise AssertionError(cmd)
        if cmd[0] == "git" and "push" in cmd and "push" in self.fail:
            return pdp.Result(1, "", "push rejected")
        return pdp.default_runner(cmd, cwd, input, binary)

    def has(self, *tokens):
        return [c for c in self.calls if all(t in c for t in tokens)]


def _db(mgrs: dict, updated_at="2026-11-03T02:05:13+00:00") -> dict:
    """合成資料（非真實經理人）：結構同 scripts/update_etf_managers.py 輸出。"""
    return {"note": "synthetic", "updated_at": updated_at, "managers": mgrs}


def _rec(name, since=None, tenure=None, last_seen="2026-11-03", first_seen="2026-06-02", history=None):
    return {"history": history or [], "first_seen": first_seen, "name": name,
            "since": since, "tenure_days": tenure, "last_seen": last_seen}


def _dump(db: dict) -> bytes:
    # 同腳本寫檔格式：ensure_ascii=False, indent=2, 結尾換行
    return (json.dumps(db, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


BASE = _db({"AAA.TW": _rec("甲"), "BBB.TW": _rec("乙", since="2025-01-01", tenure=100)})


@pytest.fixture
def env(tmp_path):
    origin = tmp_path / "origin.git"
    _sh(tmp_path, "git", "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    _sh(tmp_path, "git", "clone", "-q", str(origin), str(work))
    _sh(work, "git", "config", "user.name", "t")
    _sh(work, "git", "config", "user.email", "t@t")
    f = work / JSON_REL
    f.parent.mkdir(parents=True)
    f.write_bytes(_dump(BASE))
    (f.parent / "etf_manager_watchlist.json").write_text('{"tickers": ["AAA", "BBB"]}\n', encoding="utf-8")
    _sh(work, "git", "add", "-A")
    _sh(work, "git", "commit", "-qm", "base")
    _sh(work, "git", "branch", "-M", "main")
    _sh(work, "git", "push", "-q", "-u", "origin", "main")
    return work, origin


def _args(**kw):
    base = dict(job="etf-managers", paths=[JSON_REL], commit_msg="msg", observation_date=None,
                force_add=False, dry_run=False)
    base.update(kw)
    return type("A", (), base)()


def _run(work, rec, logs=None, **kw):
    log = (lambda *a: logs.append(" ".join(map(str, a)))) if logs is not None else (lambda *_: None)
    return pdp.publish(_args(**kw), pdp.Publisher(rec, str(work), log=log), today="2026-11-09")


def _write(work, db_or_bytes):
    data = db_or_bytes if isinstance(db_or_bytes, bytes) else _dump(db_or_bytes)
    (work / JSON_REL).write_bytes(data)
    return data


def _variant(**over):
    """以 BASE 為底複製出『下週腳本輸出』；over 以 ticker 覆寫該筆。"""
    d = json.loads(json.dumps(BASE))
    for k, v in over.items():
        d["managers"][k.replace("_TW", ".TW")] = v
    return d


def _volatile_only():
    d = _variant()
    d["updated_at"] = "2026-11-10T02:00:00+00:00"
    for r in d["managers"].values():
        r["last_seen"] = "2026-11-10"
        if r["tenure_days"] is not None:
            r["tenure_days"] += 7
    return d


# ───────────── A. 實質／揮發判定 ─────────────
def test_unit_manager_change_is_substantive_and_timestamps_are_not():
    old = _dump(BASE)
    assert pdp.json_substantive_change(JSON_REL, old, _dump(_volatile_only())) is False
    chg = _variant(AAA_TW=_rec("丙", last_seen="2026-11-10", first_seen="2026-11-10",
                               history=[{"from": "甲", "to": "丙", "detected_at": "2026-11-10", "since": None}]))
    assert pdp.json_substantive_change(JSON_REL, old, _dump(chg)) is True


@pytest.mark.parametrize("mutate", [
    lambda d: d["managers"]["AAA.TW"].update(name="丙"),                      # 換手（姓名）
    lambda d: d["managers"]["BBB.TW"].update(since="2025-06-01"),            # 到職日異動
    lambda d: d["managers"]["AAA.TW"].update(first_seen="2026-11-10"),       # 新任期起點
    lambda d: d["managers"]["AAA.TW"].update(history=[{"from": "甲", "to": "丙", "detected_at": "2026-11-10", "since": None}]),
    lambda d: d["managers"].update({"CCC.TW": _rec("丁")}),                   # 新增標的
    lambda d: d["managers"].pop("BBB.TW"),                                    # 標的消失
    lambda d: d.update(note="changed"),                                       # 未知頂層鍵一律實質
    lambda d: d["managers"]["BBB.TW"].update(turnover=0.5),                   # 未知巢狀鍵一律實質（例：未來加換手率欄）
    lambda d: d["managers"]["BBB.TW"].update(since=None),                     # 到職日由有值變 null
])
def test_unit_each_substantive_field_is_detected(mutate):
    d = json.loads(json.dumps(BASE))
    mutate(d)
    assert pdp.json_substantive_change(JSON_REL, _dump(BASE), _dump(d)) is True


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(updated_at="X"),
    lambda d: d["managers"]["AAA.TW"].update(last_seen="2099-01-01"),
    lambda d: d["managers"]["BBB.TW"].update(tenure_days=999),
])
def test_unit_each_volatile_field_alone_is_ignored(mutate):
    d = json.loads(json.dumps(BASE))
    mutate(d)
    assert pdp.json_substantive_change(JSON_REL, _dump(BASE), _dump(d)) is False


def test_volatile_registration_is_additive_only_for_this_path():
    """其他 job 的揮發設定不受影響（登記制新增一鍵，不改通用語意）。"""
    old = json.dumps({"updated_at": "A", "managers": {"x": {"last_seen": "1"}}}).encode()
    new = json.dumps({"updated_at": "B", "managers": {"x": {"last_seen": "2"}}}).encode()
    assert pdp.json_substantive_change("some/other.json", old, new) is True      # 預設：巢狀 last_seen 為實質
    assert pdp.json_substantive_change(JSON_REL, old, new) is False
    for k, v in pdp.VOLATILE_JSON_KEYS.items():
        if k != JSON_REL:
            assert "last_seen" not in v and "tenure_days" not in v, k


def test_substantive_change_creates_pr_on_data_branch_only(env):
    work, origin = env
    chg = _variant(AAA_TW=_rec("丙", last_seen="2026-11-10", first_seen="2026-11-10",
                               history=[{"from": "甲", "to": "丙", "detected_at": "2026-11-10", "since": None}]))
    out = _write(work, chg)
    rec = Rec()
    assert _run(work, rec) == 0
    assert BRANCH in _sh(origin, "git", "branch", "--list")
    assert _sh(origin, "git", "rev-parse", "main") == _sh(work, "git", "rev-parse", "origin/main")  # main 未動
    assert rec.has("gh", "pr", "create")
    create = rec.has("gh", "pr", "create")[0]
    assert create[create.index("--head") + 1] == BRANCH and create[create.index("--base") + 1] == "main"
    # 輸出 bytes 一字不改：分支上的檔 == 腳本輸出
    assert _sh(origin, "git", "show", f"{BRANCH}:{JSON_REL}") == out.decode("utf-8").rstrip("\n")
    show = subprocess.run(["git", "show", f"{BRANCH}:{JSON_REL}"], cwd=origin, capture_output=True)  # portability-ok
    assert show.stdout == out
    assert json.loads(show.stdout)["managers"]["AAA.TW"]["name"] == "丙"


def test_volatile_only_run_is_noop_no_pr_no_push(env):
    work, origin = env
    _write(work, _volatile_only())
    rec = Rec()
    logs: list[str] = []
    assert _run(work, rec, logs=logs) == 0
    assert not rec.has("gh") and not rec.has("push") and not rec.has("commit")
    assert _sh(work, "git", "status", "--porcelain") == ""        # 工作樹已還原
    assert BRANCH not in _sh(origin, "git", "branch", "--list")
    assert any("無實質變更" in l for l in logs)


def test_identical_output_noop(env):
    work, _ = env
    rec = Rec()
    assert _run(work, rec) == 0                                    # 腳本未改任何東西
    assert not rec.has("gh") and not rec.has("push")


# ───────────── B. 冪等／既有 PR／fail-closed／白名單 ─────────────
def _chg_a():
    return _variant(AAA_TW=_rec("丙", last_seen="2026-11-10", first_seen="2026-11-10",
                                history=[{"from": "甲", "to": "丙", "detected_at": "2026-11-10", "since": None}]))


def test_rerun_with_identical_bytes_is_idempotent(env):
    work, origin = env
    out = _write(work, _chg_a())
    assert _run(work, Rec()) == 0
    head1 = _sh(origin, "git", "rev-parse", BRANCH)
    n1 = _sh(origin, "git", "rev-list", "--count", f"main..{BRANCH}")
    _sh(work, "git", "checkout", "-q", "main")
    _write(work, out)                                              # 同資料再跑一次
    rec = Rec(pr_open=True)
    assert _run(work, rec) == 0
    assert _sh(origin, "git", "rev-parse", BRANCH) == head1        # 無新 commit
    assert _sh(origin, "git", "rev-list", "--count", f"main..{BRANCH}") == n1 == "1"
    assert not rec.has("push") and not rec.has("gh", "pr", "create") and not rec.has("gh", "pr", "edit")


def test_existing_unmerged_pr_updates_same_branch_keeps_earlier_change(env):
    work, origin = env
    _write(work, _chg_a())
    assert _run(work, Rec()) == 0
    first = _sh(origin, "git", "rev-parse", BRANCH)
    # 下週：PR 尚未合併，main 仍是 BASE；腳本以 main 為底，再次偵測到 A 換手並新偵測到 B 換手
    _sh(work, "git", "checkout", "-q", "main")
    d = _chg_a()
    d["managers"]["BBB.TW"] = _rec("戊", since="2025-01-01", tenure=107, last_seen="2026-11-17",
                                   first_seen="2026-11-17",
                                   history=[{"from": "乙", "to": "戊", "detected_at": "2026-11-17", "since": "2025-01-01"}])
    out2 = _write(work, d)
    rec = Rec(pr_open=True)
    assert _run(work, rec) == 0
    assert not rec.has("gh", "pr", "create")                       # 不重複開 PR
    assert rec.has("gh", "pr", "edit")                             # 只更新同一 PR 的 body
    assert rec.has("git", "push", "-u", "origin", BRANCH)
    assert _sh(origin, "git", "merge-base", "--is-ancestor", first, BRANCH) == ""   # 舊 commit 仍在歷史（非 force）
    final = json.loads(subprocess.run(["git", "show", f"{BRANCH}:{JSON_REL}"], cwd=origin,  # portability-ok
                                      capture_output=True).stdout)
    assert final["managers"]["AAA.TW"]["name"] == "丙" and final["managers"]["BBB.TW"]["name"] == "戊"
    assert final == json.loads(out2)
    for c in rec.calls:
        assert not any(t.startswith("--force") or t.startswith("+") for t in c), c
        assert "rebase" not in c


def test_pr_create_failure_fails_loud_with_hint_and_no_success_text(env):
    work, _ = env
    _write(work, _chg_a())
    rec = Rec(fail={"create"})
    logs: list[str] = []
    with pytest.raises(pdp.PublishError, match="Allow GitHub Actions to create and approve pull requests"):
        _run(work, rec, logs=logs)
    assert not any("已建立 PR" in l for l in logs)


def test_pr_list_failure_fails_loud(env):
    work, _ = env
    _write(work, _chg_a())
    logs: list[str] = []
    with pytest.raises(pdp.PublishError):
        _run(work, Rec(fail={"list"}), logs=logs)
    assert not any("已建立 PR" in l for l in logs)


def test_push_failure_fails_loud_no_pr(env):
    work, _ = env
    _write(work, _chg_a())
    rec = Rec(fail={"push"})
    with pytest.raises(pdp.PublishError):
        _run(work, rec)
    assert not rec.has("gh", "pr", "create")


def test_main_exit_code_1_and_no_success_message_on_failure(env, monkeypatch, capsys):
    work, _ = env
    _write(work, _chg_a())
    rec = Rec(fail={"create"})
    real = pdp.Publisher
    monkeypatch.setattr(pdp, "Publisher", lambda: real(rec, str(work), log=print))
    rc = pdp.main(["--job", "etf-managers", "--paths", JSON_REL, "--commit-msg", "m"])
    cap = capsys.readouterr()
    assert rc == 1
    assert "FAIL" in cap.err and "已建立 PR" not in cap.out


def test_only_allowlisted_path_is_staged_and_committed(env):
    work, origin = env
    _write(work, _chg_a())
    (work / "src/data/etf/etf_manager_watchlist.json").write_text('{"tickers": ["ZZZ"]}\n', encoding="utf-8")  # 範圍外已追蹤檔被改
    (work / "stray.txt").write_text("x", encoding="utf-8")                                                  # 範圍外未追蹤檔
    assert _run(work, Rec()) == 0
    files = _sh(origin, "git", "diff", "--name-only", f"main..{BRANCH}").splitlines()
    assert files == [JSON_REL]


@pytest.mark.parametrize("bad", [
    ["git", "push", "origin", "main"],
    ["git", "push", "origin", "HEAD:main"],
    ["git", "push", "--force", "origin", BRANCH],
    ["git", "push", "origin", "+" + BRANCH],
    ["git", "push", "--force-with-lease", "origin", BRANCH],
    ["git", "push", "origin", "auto/other"],
    ["git", "rebase", "origin/main"],
    ["gh", "pr", "merge", "7"],
    ["gh", "workflow", "run", "pr-check.yml"],
])
def test_guard_rejects_everything_outside_the_data_branch(bad):
    with pytest.raises(pdp.PublishError):
        pdp._guard(bad)


def test_guard_allows_data_branch_push():
    pdp._guard(["git", "push", "-u", "origin", BRANCH])
    pdp._guard(["git", "push", "origin", BRANCH])


def test_no_secret_or_url_in_commands_logs_or_pr_body(env, monkeypatch):
    work, _ = env
    monkeypatch.setenv("PROXY_URL", SENTINEL)
    monkeypatch.setenv("GH_TOKEN", SENTINEL)
    _write(work, _chg_a())
    rec = Rec()
    logs: list[str] = []
    assert _run(work, rec, logs=logs) == 0
    blob = "\n".join(logs) + "\n" + "\n".join(" ".join(c) for c in rec.calls)
    assert SENTINEL not in blob
    create = rec.has("gh", "pr", "create")[0]
    body = create[create.index("--body") + 1] + create[create.index("--title") + 1]
    assert SENTINEL not in body
    assert not re.search(r"https?://", body)
    # 沿用既有慣例的 PR body 警語（GITHUB_TOKEN 建立的 PR 不會自動觸發 required check）
    for must in ("CI 不一定自動觸發", "ui2-browser-gate", "Close→Reopen", "Update branch", "未啟用 auto-merge"):
        assert must in body, must


def test_dry_run_writes_nothing(env):
    work, origin = env
    _write(work, _chg_a())
    rec = Rec()
    assert _run(work, rec, dry_run=True) == 0
    assert not rec.has("push") and not rec.has("commit") and not rec.has("gh", "pr", "create")
    assert BRANCH not in _sh(origin, "git", "branch", "--list")


# ───────────── C. workflow YAML 靜態守衛 ─────────────
def _code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def _steps(code: str) -> list[str]:
    parts = re.split(r"(?m)^      - name: ", code)
    return ["      - name: " + p for p in parts[1:]]


def violations(text: str) -> list[str]:
    code = _code(text) + "\n"
    nc = re.sub(r"[ \t]#.*$", "", code, flags=re.M)
    out = []
    if re.search(r"\bgit\s+push\b", nc):
        out.append("含裸 git push")
    if re.search(r"--force|--force-with-lease|\borigin\s+main\b|HEAD:main|\+refs?/", nc):
        out.append("含 force／origin main")
    if "scripts/publish_data_pr.py --job etf-managers" not in nc:
        out.append("未以 --job etf-managers 呼叫 helper")
    if not re.search(r"--paths src/data/etf/etf_managers\.json\s*\\?\n", nc):
        out.append("--paths 不是恰為 etf_managers.json")
    m = re.search(r"^    permissions:[ \t]*\n((?:      [A-Za-z-]+:[ \t]*\S+.*\n)+)", nc, re.M)
    perms = dict(re.findall(r"^      ([A-Za-z-]+):[ \t]*(\S+)", m.group(1), re.M)) if m else {}
    if perms != {"contents": "write", "pull-requests": "write"}:
        out.append(f"job permissions 不符：{perms}")
    if re.search(r"^permissions:", nc, re.M):
        out.append("不應有 workflow 層 permissions")
    if re.search(r"\bactions:\s*write\b|write-all", nc):
        out.append("含 actions: write／write-all")
    if re.search(r"\bgh\s+workflow\b|/dispatches", nc):
        out.append("含 dispatch")
    if not re.search(r"uses: actions/checkout@\S+[ \t]*\n\s+with:[ \t]*\n\s+fetch-depth: 0\b", nc):
        out.append("checkout 缺 fetch-depth: 0")
    if not re.search(r"^concurrency:[ \t]*\n  group: data-publish-etf-managers[ \t]*\n  cancel-in-progress: false[ \t]*$",
                     nc, re.M):
        out.append("concurrency 不符")
    if not re.search(r"GH_TOKEN: \$\{\{ secrets\.GITHUB_TOKEN \}\}", nc):
        out.append("發布步驟缺 GH_TOKEN")
    return out


def test_workflow_has_no_violations():
    assert violations(WF.read_text(encoding="utf-8")) == []


def test_workflow_mutation_guard_turns_red():
    """突變驗證：還原裸 push／force／缺 helper／多餘權限，守衛必須轉紅。"""
    t = WF.read_text(encoding="utf-8")
    assert violations(t + "\n      - run: git push\n")
    assert violations(t + "\n      - run: git push origin main --force\n")
    assert violations(t.replace("scripts/publish_data_pr.py", "scripts/x.py"))
    assert violations(t.replace("    permissions:\n", "    permissions:\n      actions: write\n", 1))
    assert violations(t.replace("      pull-requests: write", "      issues: write", 1))
    assert violations(t.replace("fetch-depth: 0", "fetch-depth: 1", 1))
    assert violations(t.replace("cancel-in-progress: false", "cancel-in-progress: true", 1))
    assert violations(t.replace("--job etf-managers", "--job other", 1))


def test_workflow_triggers_secrets_and_fetch_step_unchanged():
    t = WF.read_text(encoding="utf-8")
    code = _code(t)
    on = code[code.index("\non:"):code.index("\nconcurrency:")]
    assert re.findall(r"^  (\w+):", on, re.M) == ["workflow_dispatch", "schedule"]
    assert "    - cron: '0 20 * * 1'" in on
    assert "workflow_dispatch:\n  # " in t or re.search(r"workflow_dispatch:\s*\n(?:\s*#.*\n)*  schedule:", t)  # 無 inputs
    # 祕密名單：恰為 PROXY_URL（取數）與 GITHUB_TOKEN（發布）
    assert sorted(set(re.findall(r"secrets\.([A-Za-z0-9_]+)", code))) == ["GITHUB_TOKEN", "PROXY_URL"]
    steps = _steps(code)
    names = [s.splitlines()[0].replace("      - name: ", "") for s in steps]
    assert names == ["Checkout Repository", "Set up Python", "Install Dependencies",
                     "Fetch ETF managers", "Publish via data PR (no direct push to main)"]
    fetch = steps[3]
    assert "PROXY_URL: ${{ secrets.PROXY_URL }}" in fetch
    assert "run: python scripts/update_etf_managers.py" in fetch
    assert "GITHUB_TOKEN" not in fetch and "GH_TOKEN" not in fetch    # 取數步驟不拿發布 token
    assert "run: pip install requests urllib3 pandas" in steps[2]
    assert "PROXY_URL" not in steps[4]                                  # 發布步驟不拿取數祕密


def test_workflow_publish_step_is_last_and_only_touches_the_json():
    code = _code(WF.read_text(encoding="utf-8"))
    pub = _steps(code)[-1]
    assert "git add" not in pub and "git commit" not in pub and "git push" not in pub
    assert "--force-add" not in pub
    assert pub.count("src/data/etf/etf_managers.json") == 1
