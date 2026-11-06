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
# 精確兩項：不得有 actions: write（本流程不 dispatch；dispatch 的 checks 不符合 required checks）
NEED_PERMS = {"contents": "write", "pull-requests": "write"}


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
    if perms != NEED_PERMS:
        out.append(f"job permissions 必須恰為 {NEED_PERMS}，實際 {perms}")
    nc = re.sub(r"[ \t]#.*$", "", code, flags=re.M)  # 去行內註解（權限行註解會提到 actions: write）
    if re.search(r"\bactions:\s*write\b", nc):
        out.append("含 actions: write")
    if re.search(r"\bgh\s+workflow\b|workflow_dispatch\s*\)|/dispatches", nc):
        out.append("含 gh workflow／dispatch 呼叫")
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
    """突變驗證：裸 push、actions: write、dispatch、concurrency/fetch-depth/helper 被拿掉，守衛必須轉紅。"""
    text = (WF / name).read_text(encoding="utf-8")
    assert violations(name, text + "\n      - run: git push\n")
    assert violations(name, text.replace("    permissions:\n", "    permissions:\n      actions: write\n", 1))
    assert violations(name, text + "\n      - run: gh workflow run pr-check.yml --ref x\n")
    assert violations(name, text.replace("cancel-in-progress: false", "cancel-in-progress: true", 1))
    assert violations(name, text.replace("fetch-depth: 0", "fetch-depth: 1", 1))
    assert violations(name, text.replace("scripts/publish_data_pr.py", "scripts/x.py"))


def _helper_paths(text: str) -> list[str]:
    code = _code_lines(text).replace("\\\n", " ")
    m = re.search(r"--paths\s+(.*?)\s+--commit-msg", code, re.S)
    return m.group(1).split() if m else []


def test_job_paths_do_not_overlap():
    """三個 job 的 --paths 互不重疊（不得互相吃掉對方檔案）。"""
    allp = {n: _helper_paths((WF / n).read_text(encoding="utf-8")) for n in CRONS}
    assert all(allp.values())
    items = [(n, p) for n, ps in allp.items() for p in ps]
    for i, (n1, a) in enumerate(items):
        for n2, b in items[i + 1:]:
            if n1 == n2:
                continue
            assert not (a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/")), (n1, a, n2, b)


def test_macro_history_paths_cover_all_fetchers_and_metadata():
    """macro-history 的明確 --paths 必須涵蓋 FETCHERS 各表 parquet + metadata.json（新增 dataset 漏列即紅）。"""
    src = (WF.parents[1] / "scripts" / "update_macro_history.py").read_text(encoding="utf-8")
    block = src[src.index("\nFETCHERS = {"):]
    block = block[:block.index("\n}\n")]
    names = re.findall(r'^    "(\w+)": \(', block, re.M)
    assert names
    paths = set(_helper_paths((WF / "update_macro_history.yml").read_text(encoding="utf-8")))
    assert {f"data_cache/{n}.parquet" for n in names} | {"data_cache/metadata.json", "data_cache/macro_last_good/"} == paths


# ── 腳本實際寫入位置 vs --paths（D1：腳本新增寫入位置而 workflow 沒列 → 紅）──
_LIT = re.compile(r"data_cache/[A-Za-z0-9_./-]+")
ROOT = WF.parents[1]


def _covers(paths: list[str], lit: str) -> bool:
    lit = lit.rstrip("/")
    return any(lit == p.rstrip("/") or lit.startswith(p.rstrip("/") + "/") for p in paths)


def _durable_dirs() -> list[str]:
    src = (ROOT / "src" / "data" / "macro" / "macro_core.py").read_text(encoding="utf-8")
    m = re.search(r'^_MACRO_DURABLE_DIR\s*=\s*_os\.path\.join\("data_cache",\s*"([^"]+)"\)', src, re.M)
    assert m, "macro_core._MACRO_DURABLE_DIR 定義改了，請同步此測試"
    return [f"data_cache/{m.group(1)}"]


def _forward_dirs() -> list[str]:
    src = (ROOT / "shared" / "macro_forward_test_schema.py").read_text(encoding="utf-8")
    m = re.search(r'^MACRO_FWD_TEST_RELPATH[^=]*=\s*\(([^)]*)\)', src, re.M)
    assert m
    parts = re.findall(r'"([^"]+)"', m.group(1))
    return ["/".join(parts[:-1])]  # 檔案所在目錄


def uncovered_writes(yml_text: str, script: str, extra: list[str]) -> list[str]:
    paths = _helper_paths(yml_text)
    lits = set(_LIT.findall((ROOT / "scripts" / script).read_text(encoding="utf-8"))) | set(extra)
    return sorted(l for l in lits if not _covers(paths, l))


def test_macro_history_paths_cover_all_script_written_locations():
    text = (WF / "update_macro_history.yml").read_text(encoding="utf-8")
    assert uncovered_writes(text, "update_macro_history.py", _durable_dirs()) == []
    assert "data_cache/macro_last_good" in _durable_dirs()[0]


def test_sector_flow_paths_cover_all_script_written_locations():
    text = (WF / "update_sector_flow.yml").read_text(encoding="utf-8")
    assert uncovered_writes(text, "update_sector_flow.py", []) == []


def test_forward_test_paths_cover_store_location():
    text = (WF / "update_macro_forward_test.yml").read_text(encoding="utf-8")
    paths = _helper_paths(text)
    assert all(_covers(paths, d) for d in _forward_dirs()), (paths, _forward_dirs())


def test_mutation_missing_durable_dir_turns_red():
    text = (WF / "update_macro_history.yml").read_text(encoding="utf-8")
    mutated = text.replace("            data_cache/macro_last_good/ \\\n", "")
    assert mutated != text
    assert uncovered_writes(mutated, "update_macro_history.py", _durable_dirs())
    # 腳本新增一個 workflow 沒列的寫入位置 → 紅
    assert uncovered_writes(text, "update_macro_history.py", _durable_dirs() + ["data_cache/new_dir"]) == ["data_cache/new_dir"]
