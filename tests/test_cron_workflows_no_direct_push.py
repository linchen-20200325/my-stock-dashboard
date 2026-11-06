"""靜態守衛：三支每日資料 cron 不得直接 push main，須經 scripts/publish_data_pr.py。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

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


def _job_permissions(code: str) -> dict[str, str]:
    """取 job 層（4 空白縮排）`permissions:` 區塊的 key: value（不依賴 yaml）。"""
    m = re.search(r"^    permissions:[ \t]*\n((?:      [A-Za-z-]+:[ \t]*\S+.*\n)+)", code, re.M)
    if not m:
        return {}
    return {k: v for k, v in re.findall(r"^      ([A-Za-z-]+):[ \t]*(\S+)", m.group(1), re.M)}


def violations(name: str, text: str) -> list[str]:
    code = _code_lines(text) + "\n"
    out = []
    if re.search(r"\bgit\s+push\b", code):
        out.append("含裸 git push")
    if "scripts/publish_data_pr.py" not in code:
        out.append("未呼叫 publish helper")
    job = CRONS[name]
    if not re.search(rf"^concurrency:[ \t]*\n  group: data-publish-{re.escape(job)}[ \t]*\n"
                     r"  cancel-in-progress: false[ \t]*$", code, re.M):
        out.append("concurrency 不符")
    perms = _job_permissions(code)
    if any(perms.get(k) != v for k, v in NEED_PERMS.items()):
        out.append("job permissions 不全")
    if "write-all" in code:
        out.append("write-all")
    if re.search(r"^permissions:", code, re.M):
        out.append("不應有 workflow 層 permissions（改 job 層最小授權）")
    if not re.search(r"uses: actions/checkout@\S+[ \t]*\n\s+with:[ \t]*\n\s+fetch-depth: 0\b", code):
        out.append("checkout 缺 fetch-depth: 0")
    if not re.search(r"GH_TOKEN: \$\{\{ secrets\.GITHUB_TOKEN \}\}", code):
        out.append("發布步驟缺 GH_TOKEN")
    if not re.search(r"^      (publish_)?dry_run:", code, re.M):
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
