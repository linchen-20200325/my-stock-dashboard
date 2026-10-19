"""VN1-STORE「WIF auth-only」批（DEC-064 G1）— workflow 權限／釘版守衛、writer key 名稱退役守衛、驗證腳本行為。

守：
1. `.github/workflows/risk_cap_history_poc.yml`（⛔ 不得改名／搬移：WIF attribute condition 釘了 workflow_ref）：
   只 `workflow_dispatch`；頂層 permissions 恰好 `contents: read`；`id-token: write` **只在** `wif_auth_only` job；
   dry-run job 與加 mode 前逐步相同、沒有 id-token；auth action 以 40 字元 commit SHA 釘版；WIF provider／SA 逐字；
   ⛔ credentials_json／token_format／secrets／schedule／contents: write／--write／git push／Sheet ID／舊 SA 金鑰。
   wif job 內每個 `uses:` 都以 40 字元 commit SHA 釘版並附 `# vX.Y.Z`（checkout／setup-python／auth）。
2. 全 repo（git 追蹤的 .py／.yml，tests 除外）不得再出現退役的 writer JSON key 名稱。
3. `scripts/risk_cap_wif_auth_check.py`：缺 GAC／`service_account` 型別一律拒絕（exit 2、不發請求）；
   假物件走 PASS；email 不符 → FAIL；refresh 例外 → FAIL 且 token／例外訊息不外洩；tokeninfo 用 POST body。
4. 寫入閘門照樣拒絕、`PRODUCTION_WRITE_APPROVED` 仍為 False。
5. 突變自驗（in-test）：拔掉 wif job 的 id-token、改 SA 字串、拔掉型別檢查 ⇒ 對應守衛必須轉紅。
不連網：所有 Google／HTTP 依賴以假物件注入。
⛔ 不依賴 PyYAML（PR Check 不裝）：workflow 以本檔內只用標準函式庫的受限 YAML 子集解析器讀（稽核修正第 1 輪 M1）。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from shared import risk_cap_history_policy as P
from src.data.macro import risk_cap_history as L1H
from tests._git_tracked import REPO_MIN_TRACKED, only_tracked
from tests.test_p01_macro_refresh import _mutated_module

REPO = Path(__file__).resolve().parents[1]
WORKFLOW_REL = ".github/workflows/risk_cap_history_poc.yml"
SCRIPT_REL = "scripts/risk_cap_wif_auth_check.py"

#: 客戶設定的固定值（DEC-064 G1；BACKLOG `VN1-STORE` 2026-10-19 客戶回報）—— ⛔ 不是 secret，也不得改。
WIF_PROVIDER = ("projects/847745640234/locations/global/workloadIdentityPools/"
                "stock-dashboard-github/providers/github-actions")
WRITER_SA = "risk-cap-writer@mystock20260823.iam.gserviceaccount.com"
#: 退役的 writer JSON key 環境變數名（與其 L0 常數名）—— 只准以「禁止字面」出現在 tests/ 與文件。
RETIRED_LITERALS = ("RISK_CAP_HISTORY_WRITER_SA_JSON", "WRITER_SA_ENV_VAR")

#: dry-run job 加 mode 前的內容（origin/main `601c53eb`；只多了 `if:` 一行）—— 行為必須逐步相同。
DRY_RUN_JOB_BEFORE = {
    "runs-on": "ubuntu-latest",
    "timeout-minutes": 25,
    "steps": [
        {"name": "Checkout Repository", "uses": "actions/checkout@v4"},
        {"name": "Set up Python", "uses": "actions/setup-python@v5", "with": {"python-version": "3.11"}},
        {"name": "Install deps", "run": "pip install -r requirements.txt"},
        {"name": "Run PoC (dry-run + simulated same-day rerun)",
         "env": {"FINMIND_TOKEN": "${{ secrets.FINMIND_TOKEN }}", "PROXY_URL": "${{ secrets.PROXY_URL }}",
                 "NAS_BASE_URL": "${{ secrets.NAS_BASE_URL }}", "NAS_API_KEY": "${{ secrets.NAS_API_KEY }}"},
         "run": "python scripts/risk_cap_history_poc.py --simulate-rerun --out risk_cap_history_poc_record.json"},
        {"name": "Upload record JSON", "if": "always()", "uses": "actions/upload-artifact@v4",
         "with": {"name": "risk-cap-history-poc-record", "path": "risk_cap_history_poc_record.json",
                  "if-no-files-found": "warn", "retention-days": 14}},
    ],
}


# ══════════════════════════════════════════════════════════════════════════
# 1. workflow 守衛（以文字為輸入，突變測試可重用）
# ══════════════════════════════════════════════════════════════════════════
# 稽核修正第 1 輪（2026-10-19，M1）：原本用 PyYAML 解析 —— 但 PyYAML 不在 requirements.txt、
# PR Check 也不裝它 ⇒ 乾淨環境收集期 ModuleNotFoundError、整條 fast lane 紅。⛔ 不用 importorskip
# （會讓守衛靜默 skip）、⛔ 不改 requirements／pr-check.yml；改為下方只用標準函式庫的**受限 YAML 子集**
# 解析器：只認本檔用到的語法（縮排區塊 mapping、`- ` 序列、純量），其餘一律大聲失敗（⛔ 不猜）。


def _wf_text() -> str:
    return (REPO / WORKFLOW_REL).read_text(encoding="utf-8")


class UnsupportedWorkflowYaml(AssertionError):
    """workflow 用了本解析器不支援的 YAML 語法 —— 守衛不猜，直接紅（請擴充解析器或改寫 workflow）。"""


_KEY_RE = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*):(?:\s+(.*))?$")


def _strip_trailing_comment(line: str) -> str:
    """去掉引號外、前面有空白的 `#` 起始註解。"""
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    if quote:
        raise UnsupportedWorkflowYaml(f"引號未閉合：{line!r}")
    return line.rstrip()


def _yaml_lines(text: str) -> list[tuple[int, int, str]]:
    out = []
    for no, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise UnsupportedWorkflowYaml(f"第 {no} 行以 tab 縮排")
        body = raw.strip()
        if not body or body.startswith("#"):
            continue
        content = _strip_trailing_comment(raw.lstrip(" "))
        out.append((no, len(raw) - len(raw.lstrip(" ")), content))
    return out


def _yaml_scalar(no: int, s: str):
    if s[:1] in "[{&*!|>%@`":
        raise UnsupportedWorkflowYaml(f"第 {no} 行：不支援的 YAML 語法 {s!r}")
    if len(s) >= 2 and s[0] == s[-1] == '"':
        if "\\" in s:
            raise UnsupportedWorkflowYaml(f"第 {no} 行：雙引號字串含跳脫字元")
        return s[1:-1]
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1].replace("''", "'")
    if s[:1] in "\"'":
        raise UnsupportedWorkflowYaml(f"第 {no} 行：引號用法不支援 {s!r}")
    if s in ("true", "false"):
        return s == "true"
    if s in ("null", "~", "yes", "no", "on", "off", "True", "False", "Yes", "No"):
        raise UnsupportedWorkflowYaml(f"第 {no} 行：有歧義的純量 {s!r}（請加引號）")
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _yaml_block(lines: list, i: int, indent: int):
    if lines[i][2] == "-" or lines[i][2].startswith("- "):
        return _yaml_seq(lines, i, indent)
    return _yaml_map(lines, i, indent)


def _yaml_map(lines: list, i: int, indent: int):
    out: dict = {}
    while i < len(lines) and lines[i][1] >= indent:
        no, ind, content = lines[i]
        if ind != indent:
            raise UnsupportedWorkflowYaml(f"第 {no} 行：縮排不一致（預期 {indent}，實際 {ind}）")
        if content == "-" or content.startswith("- "):
            raise UnsupportedWorkflowYaml(f"第 {no} 行：mapping 中出現序列項")
        m = _KEY_RE.match(content)
        if not m:
            raise UnsupportedWorkflowYaml(f"第 {no} 行：不是 `key: value`：{content!r}")
        key, rest = m.group(1), m.group(2)
        if key in out:
            raise UnsupportedWorkflowYaml(f"第 {no} 行：重複的鍵 {key!r}")
        i += 1
        if rest:
            out[key] = _yaml_scalar(no, rest)
        elif i < len(lines) and lines[i][1] > indent:
            out[key], i = _yaml_block(lines, i, lines[i][1])
        else:
            raise UnsupportedWorkflowYaml(f"第 {no} 行：鍵 {key!r} 沒有值（或用了同層序列寫法）")
    return out, i


def _yaml_seq(lines: list, i: int, indent: int):
    out: list = []
    while i < len(lines) and lines[i][1] >= indent:
        no, ind, content = lines[i]
        if ind != indent or not (content == "-" or content.startswith("- ")):
            raise UnsupportedWorkflowYaml(f"第 {no} 行：序列縮排／格式不一致")
        body = content[1:].lstrip(" ")
        if not body:
            raise UnsupportedWorkflowYaml(f"第 {no} 行：空的序列項")
        if _KEY_RE.match(body):
            # `- key: v` ＝ 一個 mapping，第一個鍵在 indent + 2 + 額外空白
            item_indent = ind + (len(content) - len(body))
            lines = lines[:i] + [(no, item_indent, body)] + lines[i + 1:]
            item, i = _yaml_map(lines, i, item_indent)
            out.append(item)
        else:
            out.append(_yaml_scalar(no, body))
            i += 1
    return out, i


def _parse(text: str) -> dict:
    """受限 YAML 子集 → dict。整份文件必須被完整吃掉（剩下任何一行 ⇒ 失敗）。"""
    lines = _yaml_lines(text)
    assert lines and lines[0][1] == 0, "workflow 第一個有效行必須頂格"
    d, i = _yaml_map(lines, 0, 0)
    if i != len(lines):
        raise UnsupportedWorkflowYaml(f"第 {lines[i][0]} 行之後未被解析")
    return d


def _job_text(text: str, job: str) -> str:
    """取出某個 job 的原始文字區塊（`  <job>:` 起、到下一個同層 job 或檔尾）—— 給字串層守衛用。"""
    m = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  \S|\Z)", text, flags=re.MULTILINE | re.DOTALL)
    assert m, f"找不到 job {job!r}"
    return m.group(0)


def _auth_step(job: dict) -> dict:
    hits = [s for s in job["steps"] if str(s.get("uses", "")).startswith("google-github-actions/auth@")]
    assert len(hits) == 1, hits
    return hits[0]


#: wif job 內每一個 action 的預期 commit SHA（2026-10-19 `git ls-remote --tags` 實查；輕量 tag ⇒ 即 commit）。
WIF_JOB_PINS = {
    "actions/checkout": ("34e114876b0b11c390a56381ad16ebd13914f8d5", "v4.3.1"),       # commit 2025-11-13
    "actions/setup-python": ("a26af69be951a213d495a4c3e4e4022e16d87065", "v5.6.0"),   # commit 2025-04-23
    "google-github-actions/auth": ("7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", "v3.0.0"),  # commit 2025-08-28
}


def assert_workflow_guards(text: str) -> None:
    """全部 workflow 守衛；任何一條不成立就 AssertionError（突變測試據此確認守衛會轉紅）。"""
    d = _parse(text)
    assert set(d) == {"name", "on", "permissions", "concurrency", "jobs"}, set(d)
    # 觸發：只有 workflow_dispatch，mode 選單兩個選項、預設 dry-run
    assert set(d["on"]) == {"workflow_dispatch"}, d["on"]
    assert set(d["on"]["workflow_dispatch"]) == {"inputs"}
    assert set(d["on"]["workflow_dispatch"]["inputs"]) == {"mode"}
    mode = d["on"]["workflow_dispatch"]["inputs"]["mode"]
    assert mode["type"] == "choice" and mode["default"] == "dry-run"
    assert mode["options"] == ["dry-run", "wif-auth-only"]
    # 頂層權限恰好 contents: read
    assert d["permissions"] == {"contents": "read"}, d["permissions"]
    assert d["concurrency"] == {"group": "risk-cap-history-poc", "cancel-in-progress": False}
    jobs = d["jobs"]
    assert set(jobs) == {"poc-dry-run", "wif_auth_only"}, set(jobs)

    dry = dict(jobs["poc-dry-run"])
    assert dry.pop("if") == "${{ inputs.mode == 'dry-run' }}"
    assert dry == DRY_RUN_JOB_BEFORE, dry          # 行為與加 mode 前相同；⛔ 沒有 permissions／id-token
    assert "id-token" not in _job_text(text, "poc-dry-run")

    wif = jobs["wif_auth_only"]
    assert wif["if"] == "${{ inputs.mode == 'wif-auth-only' }}"
    assert wif["permissions"] == {"contents": "read", "id-token": "write"}, wif.get("permissions")
    # id-token 全檔（YAML 鍵；註解不算）只出現一次，且在 wif job 區塊內
    assert len(re.findall(r"^\s*id-token\s*:", text, flags=re.MULTILINE)) == 1
    wif_text = _job_text(text, "wif_auth_only")
    assert re.search(r"^      id-token: write$", wif_text, flags=re.MULTILINE)

    steps = wif["steps"]
    # 每一個 uses 都必須是 40 字元 commit SHA，且是預期版本、行尾附 `# vX.Y.Z`
    uses = [s["uses"] for s in steps if "uses" in s]
    assert {u.split("@", 1)[0] for u in uses} == set(WIF_JOB_PINS), uses
    for u in uses:
        action, ref = u.split("@", 1)
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"wif job 的 action 必須以 40 字元 commit SHA 釘版：{u!r}"
        sha, ver = WIF_JOB_PINS[action]
        assert ref == sha, (u, sha)
        assert re.search(rf"^\s*uses:\s*{re.escape(u)}\s+#\s*{re.escape(ver)}\s*$", wif_text, flags=re.MULTILINE), u
    raw_uses = re.findall(r"^\s*-?\s*uses:", wif_text, flags=re.MULTILINE)
    assert len(raw_uses) == len(uses)

    i_checkout = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/checkout@"))
    assert steps[i_checkout]["with"] == {"persist-credentials": False}
    auth = _auth_step(wif)
    i_auth = steps.index(auth)
    assert auth["with"] == {"workload_identity_provider": WIF_PROVIDER, "service_account": WRITER_SA,
                            "create_credentials_file": True, "export_environment_variables": True}, auth["with"]
    runs = [(i, s["run"]) for i, s in enumerate(steps) if "run" in s]
    check = [(i, r) for i, r in runs if "scripts/risk_cap_wif_auth_check.py" in r]
    assert len(check) == 1 and check[0][1] == f"python scripts/risk_cap_wif_auth_check.py --expect-sa {WRITER_SA}"
    assert i_checkout < i_auth < check[0][0]
    pip = [r for _, r in runs if r.startswith("pip install")]
    assert pip == ['pip install "google-auth>=2.0.0,<4.0" "requests>=2.31.0,<3.0.0"'], pip
    assert all("env" not in s for s in steps) and "env" not in wif

    wif_code = "\n".join(c for _, _, c in _yaml_lines(wif_text))     # 不含註解
    for bad in ("secrets.", "credentials_json", "token_format", "gspread", "env:"):
        assert bad not in wif_code, bad
    for bad in ("credentials_json", "token_format", "schedule:", "cron:", "contents: write", "--write",
                "git push", "git commit", "RISK_CAP_HISTORY_SHEET_ID", "GCP_SERVICE_ACCOUNT_JSON",
                *RETIRED_LITERALS):
        assert bad not in text, bad


class TestWorkflow:
    def test_path_unchanged(self):
        # WIF attribute condition 釘 `…/.github/workflows/risk_cap_history_poc.yml@refs/heads/main`
        assert (REPO / WORKFLOW_REL).is_file()

    def test_guards(self):
        assert_workflow_guards(_wf_text())

    def test_auth_sha_is_v3_0_0(self):
        """2026-10-19 實查：`git ls-remote --tags` v3.0.0 ＝ 7c6bc770…（輕量 tag ⇒ 即 commit），commit 日 2025-08-28。"""
        assert _auth_step(_parse(_wf_text())["jobs"]["wif_auth_only"])["uses"] == (
            "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093")

    def test_gitignore_blocks_gha_creds(self):
        gi = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert "gha-creds-*.json" in gi

    def test_guard_module_does_not_need_pyyaml(self):
        """M1 回歸守衛：本檔不得 import yaml（PR Check 不裝 PyYAML）。"""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert "yaml" not in mods


class TestMiniYamlParser:
    """受限解析器自測：支援的語法解得對、不支援的一律失敗（⛔ 不猜）。"""

    def test_parses_subset(self):
        doc = ("name: x  # c\non:\n  a:\n    inputs:\n      m:\n        type: choice\n        options:\n"
               "          - p\n          - q\n# full comment\njobs:\n  j:\n    steps:\n      - name: s1\n"
               "        uses: o/r@abc # v1\n        with:\n          k: 'v # not comment'\n          n: 14\n"
               "          b: false\n      - run: echo \"hi\"\n")
        assert _parse(doc) == {"name": "x", "on": {"a": {"inputs": {"m": {"type": "choice", "options": ["p", "q"]}}}},
                               "jobs": {"j": {"steps": [
                                   {"name": "s1", "uses": "o/r@abc", "with": {"k": "v # not comment", "n": 14,
                                                                               "b": False}},
                                   {"run": 'echo "hi"'}]}}}

    @pytest.mark.parametrize("doc", [
        "a: |\n  multi\n", "a: [1, 2]\n", "a: {b: 1}\n", "a: &x 1\n", "a: 1\na: 2\n", "a:\n- b\n",
        "a:\n  b: 1\n c: 2\n", "a: yes\n", "a:\n", "a: \"x\\n\"\n", "\ta: 1\n", "a: 'x\n",
    ])
    def test_rejects_unsupported(self, doc):
        with pytest.raises(AssertionError):
            _parse(doc)

    def test_real_workflow_fully_consumed(self):
        d = _parse(_wf_text())
        assert d["jobs"]["poc-dry-run"]["steps"][-1]["with"]["retention-days"] == 14


# ══════════════════════════════════════════════════════════════════════════
# 2. 退役名稱：全 repo 守衛
# ══════════════════════════════════════════════════════════════════════════
class TestRetiredWriterKeyName:
    def test_not_in_any_tracked_py_or_yml_outside_tests(self):
        files = only_tracked(REPO, [*REPO.rglob("*.py"), *REPO.rglob("*.yml"), *REPO.rglob("*.yaml")],
                             min_tracked=REPO_MIN_TRACKED, min_kept=200)
        hits = {}
        for f in files:
            rel = f.relative_to(REPO).as_posix()
            if rel.startswith("tests/"):
                continue
            t = f.read_text(encoding="utf-8")
            found = [n for n in RETIRED_LITERALS if n in t]
            if found:
                hits[rel] = found
        assert not hits, hits

    def test_policy_has_no_writer_key_constant(self):
        assert not hasattr(P, "WRITER_SA_ENV_VAR")
        assert P.WRITER_SCOPES == ("https://www.googleapis.com/auth/spreadsheets",)


class TestWriteGateStillRefuses:
    def test_gate_refuses_with_everything_set(self):
        with pytest.raises(L1H.ProductionWriteNotApproved):
            L1H.load_writer_credentials_or_refuse({P.WRITE_ENABLE_ENV_VAR: "1", P.HISTORY_SHEET_ID_ENV_VAR: "x",
                                                   "GOOGLE_APPLICATION_CREDENTIALS": "/x.json"})
        assert P.PRODUCTION_WRITE_APPROVED is False

    def test_gate_final_raise_even_if_approved(self, monkeypatch):
        """稽核修正第 1 輪（NIT）：就算核准旗標被改成 True、總開關與 Sheet ID 都設了，最後那道
        「未實作」仍必須拒絕 —— 守住「把最後的 raise 改成 return」這種突變。"""
        monkeypatch.setattr(L1H, "PRODUCTION_WRITE_APPROVED", True)
        with pytest.raises(L1H.ProductionWriteNotApproved, match="未實作"):
            L1H.load_writer_credentials_or_refuse({P.WRITE_ENABLE_ENV_VAR: "1", P.HISTORY_SHEET_ID_ENV_VAR: "x"})
        # 旗標 True 但 Sheet ID 沒設 ⇒ 卡在目標未設定（不是「未實作」）
        with pytest.raises(L1H.ProductionWriteNotApproved, match="寫入目標未設定"):
            L1H.load_writer_credentials_or_refuse({P.WRITE_ENABLE_ENV_VAR: "1"})

    def test_gate_refuses_with_nothing_set(self):
        with pytest.raises(L1H.ProductionWriteNotApproved, match="尚未核准"):
            L1H.load_writer_credentials_or_refuse({})


# ══════════════════════════════════════════════════════════════════════════
# 3. 驗證腳本
# ══════════════════════════════════════════════════════════════════════════
def _load_script():
    spec = importlib.util.spec_from_file_location("_wif_check", REPO / SCRIPT_REL)
    mod = importlib.util.module_from_spec(spec)
    # 腳本有 @dataclass：須先掛進 sys.modules（dataclasses 以 `sys.modules[cls.__module__]` 解註解）。
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


S = _load_script()
#: 假 token 哨兵：任何輸出出現它就是外洩。
TOKEN_SENTINEL = "ya29.SENTINEL-TOKEN-must-never-print-0123456789"
#: 假憑證檔裡的 GitHub OIDC 請求 token 哨兵（檔案內容也不得外洩）。
FILE_SENTINEL = "GH-OIDC-REQUEST-TOKEN-SENTINEL-abcdef"


def _ext_file(tmp_path, *, cred_type="external_account") -> str:
    p = tmp_path / "gha-creds-test.json"
    p.write_text(json.dumps({
        "type": cred_type, "audience": "//iam.googleapis.com/" + WIF_PROVIDER,
        "credential_source": {"url": "https://example.invalid/token",
                              "headers": {"Authorization": f"Bearer {FILE_SENTINEL}"}},
        "service_account_impersonation_url": ("https://iamcredentials.googleapis.com/v1/projects/-/"
                                              f"serviceAccounts/{WRITER_SA}:generateAccessToken"),
    }), encoding="utf-8")
    return str(p)


class _FakeCreds:
    def __init__(self, *, sa=WRITER_SA, exc=None, token=TOKEN_SENTINEL):
        self.service_account_email = sa
        self._exc = exc
        self._token_after = token
        self.token = None
        self.refresh_calls = 0

    def refresh(self, request):
        self.refresh_calls += 1
        if self._exc is not None:
            raise self._exc
        self.token = self._token_after


def _default_returning(creds, project="mystock20260823", seen=None):
    def _fn(scopes):
        if seen is not None:
            seen.append(tuple(scopes))
        return creds, project
    return _fn


def _post_returning(body, status=200, calls=None):
    def _fn(url, data, timeout):
        if calls is not None:
            calls.append((url, dict(data), timeout))
        return status, body
    return _fn


_GOOD_INFO = {"email": WRITER_SA, "email_verified": "true", "expires_in": "3599",
              "scope": "https://www.googleapis.com/auth/userinfo.email", "aud": "123"}


def _no_call(*a, **k):
    pytest.fail("設定被拒時不得進行任何認證／網路動作")


class TestScriptRefusals:
    def test_refuses_missing_gac(self):
        r = S.run_check(WRITER_SA, environ={}, default_fn=_no_call, request_factory=_no_call, post_fn=_no_call)
        assert r.exit_code == S.EXIT_REFUSED_CONFIG == 2

    def test_refuses_unreadable_or_not_json(self, tmp_path):
        assert S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: str(tmp_path / "nope.json")},
                           default_fn=_no_call, post_fn=_no_call).exit_code == 2
        bad = tmp_path / "bad.json"
        bad.write_text("{not json " + FILE_SENTINEL, encoding="utf-8")
        r = S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: str(bad)}, default_fn=_no_call, post_fn=_no_call)
        assert r.exit_code == 2 and FILE_SENTINEL not in r.message

    def test_refuses_service_account_key(self, tmp_path, capsys):
        path = _ext_file(tmp_path, cred_type="service_account")
        r = S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: path}, default_fn=_no_call,
                        request_factory=_no_call, post_fn=_no_call)
        assert r.exit_code == 2 and "DEC-064 G1" in r.message
        for line in S.format_result(r):
            print(line)
        out = capsys.readouterr()
        assert FILE_SENTINEL not in out.out + out.err

    def test_refuses_other_types(self, tmp_path):
        for t in ("authorized_user", "impersonated_service_account", ""):
            path = _ext_file(tmp_path, cred_type=t)
            assert S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: path}, default_fn=_no_call).exit_code == 2

    def test_refuses_impersonation_target_mismatch(self, tmp_path):
        creds = _FakeCreds(sa="someone-else@x.iam.gserviceaccount.com")
        r = S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: _ext_file(tmp_path)},
                        default_fn=_default_returning(creds), request_factory=_no_call, post_fn=_no_call)
        assert r.exit_code == 2 and creds.refresh_calls == 0

    def test_refuses_no_impersonation(self, tmp_path):
        creds = _FakeCreds(sa=None)
        r = S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: _ext_file(tmp_path)},
                        default_fn=_default_returning(creds), request_factory=_no_call, post_fn=_no_call)
        assert r.exit_code == 2

    def test_main_missing_gac_exit_2(self, monkeypatch, capsys):
        monkeypatch.delenv(S.GAC_ENV_VAR, raising=False)
        assert S.main(["--expect-sa", WRITER_SA]) == 2
        assert "REFUSED" in capsys.readouterr().out


class TestScriptAuthPaths:
    def _run(self, tmp_path, creds, post, seen=None):
        return S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: _ext_file(tmp_path)},
                           default_fn=_default_returning(creds, seen=seen),
                           request_factory=lambda: object(), post_fn=post)

    def test_pass(self, tmp_path, capsys):
        calls, seen = [], []
        creds = _FakeCreds()
        r = self._run(tmp_path, creds, _post_returning(dict(_GOOD_INFO), calls=calls), seen=seen)
        assert r.exit_code == S.EXIT_PASS == 0
        assert (r.email, r.project_id, r.lifetime_s) == (WRITER_SA, "mystock20260823", 3599)
        assert creds.refresh_calls == 1
        # 最小權限：只要 userinfo.email，⛔ 不要 spreadsheets
        assert seen == [("https://www.googleapis.com/auth/userinfo.email",)]
        assert not any("spreadsheets" in s or "drive" in s for s in S.VERIFY_SCOPES)
        # tokeninfo：POST body 帶 token，URL 不含 token
        assert len(calls) == 1
        url, data, timeout = calls[0]
        assert url == "https://oauth2.googleapis.com/tokeninfo" and "?" not in url
        assert data == {"access_token": TOKEN_SENTINEL} and timeout > 0
        for line in S.format_result(r):
            print(line)
        out = capsys.readouterr().out
        assert "PASS" in out and WRITER_SA in out and "~3599s" in out and "mystock20260823" in out
        assert TOKEN_SENTINEL not in out and FILE_SENTINEL not in out

    def test_fail_email_mismatch(self, tmp_path):
        info = dict(_GOOD_INFO, email="fund-nav@other.iam.gserviceaccount.com")
        r = self._run(tmp_path, _FakeCreds(), _post_returning(info))
        assert r.exit_code == S.EXIT_FAIL_AUTH == 1 and r.stage == S.STAGE_TOKENINFO

    @pytest.mark.parametrize("patch", [{"email_verified": "false"}, {"email_verified": None},
                                       {"expires_in": "0"}, {"expires_in": "-5"}, {"expires_in": None},
                                       {"scope": "https://www.googleapis.com/auth/spreadsheets"}])
    def test_fail_tokeninfo_checks(self, tmp_path, patch):
        r = self._run(tmp_path, _FakeCreds(), _post_returning(dict(_GOOD_INFO, **patch)))
        assert r.exit_code == 1 and r.stage == S.STAGE_TOKENINFO

    def test_fail_tokeninfo_http_error(self, tmp_path):
        r = self._run(tmp_path, _FakeCreds(), _post_returning({"error": "invalid_token"}, status=400))
        assert r.exit_code == 1 and r.stage == S.STAGE_TOKENINFO

    def test_fail_tokeninfo_request_exception_no_leak(self, tmp_path, capsys):
        def _boom(url, data, timeout):
            raise ConnectionError(f"proxy said no for {data['access_token']}")
        r = self._run(tmp_path, _FakeCreds(), _boom)
        assert r.exit_code == 1 and r.error_class == "ConnectionError"
        for line in S.format_result(r):
            print(line)
        out = capsys.readouterr()
        assert TOKEN_SENTINEL not in out.out + out.err and "proxy said no" not in out.out

    def test_fail_refresh_exception_no_leak(self, tmp_path, capsys, monkeypatch):
        exc = RuntimeError(f"Error code invalid_grant: token {TOKEN_SENTINEL} / {FILE_SENTINEL}")
        creds = _FakeCreds(exc=exc)
        monkeypatch.setenv(S.GAC_ENV_VAR, _ext_file(tmp_path))
        monkeypatch.setattr(S, "_default_fn", _default_returning(creds))
        monkeypatch.setattr(S, "_request_factory", lambda: object())
        monkeypatch.setattr(S, "_http_post", _no_call)
        # main() 走預設依賴（已被替換）—— 驗證真正的輸出路徑
        monkeypatch.setattr(S, "run_check", lambda sa, _rc=S.run_check: _rc(
            sa, default_fn=S._default_fn, request_factory=S._request_factory, post_fn=S._http_post))
        assert S.main(["--expect-sa", WRITER_SA]) == 1
        out = capsys.readouterr()
        text = out.out + out.err
        assert "FAIL" in text and "error_class=RuntimeError" in text
        assert TOKEN_SENTINEL not in text and FILE_SENTINEL not in text and "invalid_grant" not in text

    def test_fail_default_exception(self, tmp_path):
        def _boom(scopes):
            raise ValueError(f"bad file {FILE_SENTINEL}")
        r = S.run_check(WRITER_SA, environ={S.GAC_ENV_VAR: _ext_file(tmp_path)}, default_fn=_boom,
                        post_fn=_no_call)
        assert r.exit_code == 1 and r.stage == S.STAGE_LOAD and FILE_SENTINEL not in r.message

    def test_fail_no_token_after_refresh(self, tmp_path):
        r = self._run(tmp_path, _FakeCreds(token=None), _no_call)
        assert r.exit_code == 1


def _raise_from(filename: str, func: str):
    """在指定「檔名／函式名」的 frame 裡丟例外 —— 模擬 google-auth 各段的 traceback。"""
    ns: dict = {}
    exec(compile(f"def {func}():\n    raise RuntimeError('x')\n", filename, "exec"), ns)
    try:
        ns[func]()
    except RuntimeError as e:
        return e
    raise AssertionError("unreachable")


class TestStageClassification:
    def test_sts(self):
        e = _raise_from("/site-packages/google/oauth2/sts.py", "_make_request")
        assert S.classify_refresh_failure(e, S.STAGE_REFRESH) == S.STAGE_STS
        e = _raise_from("/site-packages/google/auth/identity_pool.py", "retrieve_subject_token")
        assert S.classify_refresh_failure(e, S.STAGE_REFRESH) == S.STAGE_STS

    def test_impersonation(self):
        e = _raise_from("/site-packages/google/auth/impersonated_credentials.py", "_make_iam_token_request")
        assert S.classify_refresh_failure(e, S.STAGE_REFRESH) == S.STAGE_IMPERSONATION

    def test_identity_pool_refresh_frame_alone_is_not_sts(self):
        """url 型 external_account 的 refresh 定義在 identity_pool.py —— 單憑檔名不得判成 STS。"""
        e = _raise_from("/site-packages/google/auth/identity_pool.py", "refresh")
        assert S.classify_refresh_failure(e, S.STAGE_REFRESH) == S.STAGE_REFRESH

    def test_unknown_falls_back(self):
        e = _raise_from("/somewhere/else.py", "f")
        assert S.classify_refresh_failure(e, S.STAGE_REFRESH) == S.STAGE_REFRESH


class _FakeResp:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self.headers = {"content-type": "application/json"}
        self.data = json.dumps(payload).encode("utf-8")


class _FakeTransport:
    """google-auth `transport.Request` 介面的假物件：依 URL 回 GitHub OIDC／STS／IAM Credentials 的假回應。"""

    def __init__(self, *, sts_status=200, iam_status=200):
        self.sts_status, self.iam_status = sts_status, iam_status
        self.urls: list[str] = []

    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kw):
        self.urls.append(url)
        if url.startswith("https://example.invalid/token"):
            return _FakeResp(200, {"value": "header.payload.sig"})
        if url.startswith("https://sts.googleapis.com/"):
            if self.sts_status != 200:
                return _FakeResp(self.sts_status, {"error": "invalid_grant",
                                                   "error_description": f"rejected {FILE_SENTINEL}"})
            return _FakeResp(200, {"access_token": "federated-" + TOKEN_SENTINEL, "expires_in": 3600,
                                   "token_type": "Bearer",
                                   "issued_token_type": "urn:ietf:params:oauth:token-type:access_token"})
        if url.startswith("https://iamcredentials.googleapis.com/"):
            if self.iam_status != 200:
                return _FakeResp(self.iam_status, {"error": {"code": self.iam_status,
                                                             "message": f"denied {TOKEN_SENTINEL}"}})
            return _FakeResp(200, {"accessToken": TOKEN_SENTINEL, "expireTime": "2099-01-01T00:00:00Z"})
        raise AssertionError(f"非預期的 URL：{url}")


class TestScriptWithRealGoogleAuth:
    """用**真的** google-auth（requirements.txt 版本範圍）＋假傳輸層，驗證 stage 判定與不外洩。"""

    @pytest.fixture(autouse=True)
    def _env(self, tmp_path, monkeypatch):
        pytest.importorskip("google.auth")
        info = json.loads(Path(_ext_file(tmp_path)).read_text(encoding="utf-8"))
        info.update({"subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
                     "token_url": "https://sts.googleapis.com/v1/token",
                     "audience": "//iam.googleapis.com/" + WIF_PROVIDER})
        info["credential_source"]["format"] = {"type": "json", "subject_token_field_name": "value"}
        path = tmp_path / "gha-creds-real.json"
        path.write_text(json.dumps(info), encoding="utf-8")
        monkeypatch.setenv(S.GAC_ENV_VAR, str(path))
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "mystock20260823")   # auth action 會匯出；免查 CRM

    def _run(self, transport, post):
        return S.run_check(WRITER_SA, request_factory=lambda: transport, post_fn=post)

    def test_pass_goes_through_sts_then_impersonation(self):
        t = _FakeTransport()
        calls = []
        r = self._run(t, _post_returning(dict(_GOOD_INFO), calls=calls))
        assert r.exit_code == 0, r
        hosts = [u.split("/")[2] for u in t.urls]
        assert hosts == ["example.invalid", "sts.googleapis.com", "iamcredentials.googleapis.com"], hosts
        assert calls[0][1] == {"access_token": TOKEN_SENTINEL}

    def test_sts_rejection_stage(self, capsys):
        r = self._run(_FakeTransport(sts_status=400), _no_call)
        assert (r.exit_code, r.stage) == (1, S.STAGE_STS), r
        for line in S.format_result(r):
            print(line)
        out = capsys.readouterr()
        assert TOKEN_SENTINEL not in out.out + out.err and FILE_SENTINEL not in out.out + out.err

    def test_impersonation_rejection_stage(self, capsys):
        r = self._run(_FakeTransport(iam_status=403), _no_call)
        assert (r.exit_code, r.stage) == (1, S.STAGE_IMPERSONATION), r
        for line in S.format_result(r):
            print(line)
        out = capsys.readouterr()
        assert TOKEN_SENTINEL not in out.out + out.err and "denied" not in out.out


class TestScriptStatic:
    def test_no_sheet_or_key_paths(self):
        """以 AST 判（docstring 寫「不 import gspread」不算違規）：import 與程式字串都不得碰 Sheet／舊金鑰。"""
        tree = ast.parse((REPO / SCRIPT_REL).read_text(encoding="utf-8"))
        imps = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imps |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                imps.add(n.module)
        assert not [i for i in imps if i.split(".")[0] in ("gspread", "streamlit", "googleapiclient", "src")], imps
        doc = ast.get_docstring(tree)
        strs = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value != doc]
        for bad in ("auth/spreadsheets", "sheets.googleapis", "drive.googleapis", "GCP_SERVICE_ACCOUNT_JSON",
                    "token_format", *RETIRED_LITERALS):
            assert not [v for v in strs if bad in v], bad
        # 不寫任何檔：沒有寫入模式的 open、沒有 write_text／write_bytes
        src = (REPO / SCRIPT_REL).read_text(encoding="utf-8")
        assert "write_text" not in src and "write_bytes" not in src
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open":
                modes = [a.value for a in n.args[1:2] if isinstance(a, ast.Constant)]
                assert not [m for m in modes if any(c in m for c in "wax+")], modes


# ══════════════════════════════════════════════════════════════════════════
# 5. 突變自驗（守衛必須抓得到）
# ══════════════════════════════════════════════════════════════════════════
class TestMutations:
    def _mutate(self, old: str, new: str) -> str:
        text = _wf_text()
        assert text.count(old) == 1, old
        return text.replace(old, new)

    def test_removing_id_token_from_wif_job_turns_red(self):
        mut = self._mutate("      contents: read\n      id-token: write\n", "      contents: read\n")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_id_token_on_top_level_turns_red(self):
        mut = self._mutate("permissions:\n  contents: read\n\nconcurrency:",
                           "permissions:\n  contents: read\n  id-token: write\n\nconcurrency:")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_changing_sa_string_turns_red(self):
        mut = self._mutate(f"          service_account: {WRITER_SA}\n",
                           "          service_account: fund-nav@other.iam.gserviceaccount.com\n")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_tag_instead_of_sha_turns_red(self):
        mut = self._mutate("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093",
                           "google-github-actions/auth@v3")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_checkout_tag_in_wif_job_turns_red(self):
        mut = self._mutate("actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1",
                           "actions/checkout@v4")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_setup_python_wrong_sha_turns_red(self):
        mut = self._mutate("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0",
                           "actions/setup-python@" + "0" * 40 + " # v5.6.0")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_missing_version_comment_turns_red(self):
        mut = self._mutate("auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 # v3.0.0",
                           "auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_secret_env_in_wif_job_turns_red(self):
        mut = self._mutate("          export_environment_variables: true\n",
                           "          export_environment_variables: true\n"
                           "        env:\n          X: ${{ secrets.FINMIND_TOKEN }}\n")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_dry_run_job_change_turns_red(self):
        mut = self._mutate("        run: pip install -r requirements.txt\n",
                           "        run: pip install -r requirements.txt gspread\n")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_schedule_trigger_turns_red(self):
        mut = self._mutate("on:\n  workflow_dispatch:\n",
                           "on:\n  schedule:\n    - cron: '0 9 * * *'\n  workflow_dispatch:\n")
        with pytest.raises(AssertionError):
            assert_workflow_guards(mut)

    def test_gate_final_raise_to_return_is_caught(self, monkeypatch):
        """NIT 突變：最後的「未實作」raise 改成 return ⇒ 旗標被打開時就會放行；真實模組必須照樣拒絕。"""
        mut = _mutated_module("src/data/macro/risk_cap_history.py", (
            '    raise ProductionWriteNotApproved("本 PoC 未實作建立寫入 client',
            '    return None\n    raise ProductionWriteNotApproved("本 PoC 未實作建立寫入 client'))
        mut.PRODUCTION_WRITE_APPROVED = True
        env = {P.WRITE_ENABLE_ENV_VAR: "1", P.HISTORY_SHEET_ID_ENV_VAR: "x"}
        assert mut.load_writer_credentials_or_refuse(env) is None       # 突變體放行
        monkeypatch.setattr(L1H, "PRODUCTION_WRITE_APPROVED", True)
        with pytest.raises(L1H.ProductionWriteNotApproved, match="未實作"):
            L1H.load_writer_credentials_or_refuse(env)

    def test_script_without_type_check_accepts_sa_key(self, tmp_path):
        mut = _mutated_module(SCRIPT_REL, ('    if cred_type == "service_account":\n',
                                           '    if False:\n'),
                              ("    if cred_type != ALLOWED_CREDENTIAL_TYPE:\n", "    if False:\n"))
        path = _ext_file(tmp_path, cred_type="service_account")
        assert mut.check_credentials_file({mut.GAC_ENV_VAR: path}) == path       # 突變體放行 SA key
        with pytest.raises(S.ConfigRefused):
            S.check_credentials_file({S.GAC_ENV_VAR: path})
