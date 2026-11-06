"""靜態守衛：三支每日資料 cron 不得直接 push main，須經 scripts/publish_data_pr.py。"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"
CRONS = {
    "update_macro_history.yml": "macro-history",
    "update_sector_flow.yml": "sector-flow",
    "update_macro_forward_test.yml": "macro-forward-test",
}
NEED_PERMS = {"contents": "write", "pull-requests": "write", "actions": "write"}


def _code_lines(text: str) -> str:
    """去掉 YAML 註解行（歷史註解可提 git push 字樣）。"""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def violations(name: str, text: str) -> list[str]:
    out = []
    if re.search(r"\bgit\s+push\b", _code_lines(text)):
        out.append("含裸 git push")
    doc = yaml.safe_load(text)
    if "scripts/publish_data_pr.py" not in text:
        out.append("未呼叫 publish helper")
    job = CRONS[name]
    conc = doc.get("concurrency") or {}
    jobs = doc["jobs"]
    if conc.get("group") != f"data-publish-{job}" or conc.get("cancel-in-progress") is not False:
        out.append("concurrency 不符")
    for jn, j in jobs.items():
        perms = j.get("permissions")
        if not isinstance(perms, dict) or any(perms.get(k) != v for k, v in NEED_PERMS.items()):
            out.append(f"{jn} permissions 不全")
        if "write-all" in str(perms) or "write-all" in str(doc.get("permissions")):
            out.append("write-all")
        co = [s for s in j["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
        if not co or co[0].get("with", {}).get("fetch-depth") != 0:
            out.append("checkout 缺 fetch-depth: 0")
        pub = [s for s in j["steps"] if "publish_data_pr.py" in s.get("run", "")]
        if not pub or "GH_TOKEN" not in (pub[0].get("env") or {}):
            out.append("發布步驟缺 GH_TOKEN")
    if doc.get("permissions"):
        out.append("不應有 workflow 層 permissions（改 job 層最小授權）")
    if "dry_run" not in str(doc[True]["workflow_dispatch"]["inputs"]):  # yaml 把 on 解析為 True
        out.append("缺 dry_run input")
    return out


@pytest.mark.parametrize("name", sorted(CRONS))
def test_workflow_ok(name):
    assert violations(name, (WF / name).read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("name", sorted(CRONS))
def test_mutation_guard_turns_red(name):
    """突變驗證：把裸 git push 加回、或拿掉權限 / concurrency，守衛必須轉紅。"""
    text = (WF / name).read_text(encoding="utf-8")
    assert violations(name, text + "\n      - run: git push\n")
    assert violations(name, text.replace("actions: write", "actions: read", 1))
    assert violations(name, text.replace("cancel-in-progress: false", "cancel-in-progress: true", 1))
    assert violations(name, text.replace("fetch-depth: 0", "fetch-depth: 1", 1))
    assert violations(name, text.replace("scripts/publish_data_pr.py", "scripts/x.py"))


@pytest.mark.skipif(shutil.which("actionlint") is None, reason="actionlint 不可用")
def test_actionlint():
    r = subprocess.run(["actionlint", *[str(WF / n) for n in CRONS]], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
