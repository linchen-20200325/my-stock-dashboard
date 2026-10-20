"""VN1-STORE「Sheet 權限驗證 Gate」批 — workflow 守衛、權限測試腳本（P1／P2／R1／R2／R3）、WIF 反向測試（R4／R5）。

規格：`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 5 節（P1／P2／R1～R5 語意的唯一依據）；客戶 2026-10-20 決策：
reader 測試用一次性例外 secret `RISK_CAP_READER_TEST_SA_JSON`（scope 恰好 readonly）；R1 對持股 Sheet 只發唯讀 GET；
P1 只寫一列明確標記的測試列、讀回、立刻刪除。

守：
1. `.github/workflows/risk_cap_history_poc.yml` 新增三個 mode／job（writer 用 WIF、reader 無 id-token 且只限 main、
   R4 無 auth action），全部 action 以 40 字元 SHA 釘版；dry-run／wif_auth_only 的既有逐字守衛照跑；全檔無排程；
   一次性 reader secret 只出現在 reader job。
2. `.github/workflows/risk_cap_wif_negative_r5.yml`：只 workflow_dispatch、無 secrets、無排程、無 auth action。
3. `scripts/risk_cap_permission_test.py`：判定分類、P1 流程（append／讀回／刪除／確認已刪；錯列不刪；append 後失敗
   仍經 finally 清理）、reader scope 恰好 readonly、R3 2xx ⇒ FAIL、持股 Sheet 只收到 GET、輸出不含 Sheet ID／token／金鑰。
4. `scripts/risk_cap_wif_negative.py`：R4／R5 前置條件、STS 判定（2xx ⇒ FAIL；attribute condition ⇒ PASS；5xx ⇒ INCONCLUSIVE）。
5. 突變自驗：守衛與判定被拔掉時必須轉紅。
不連網：所有 Google／GitHub／HTTP 依賴以假物件注入。⛔ 不依賴 PyYAML（沿用 `tests/test_vn1_wif_auth_only.py` 的受限解析器）。
"""
from __future__ import annotations

import base64
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest

from shared import risk_cap_history_policy as P
from tests.test_p01_macro_refresh import _mutated_module
from tests.test_vn1_wif_auth_only import (
    DRY_RUN_JOB_BEFORE,
    WIF_JOB_PINS,
    WIF_PROVIDER,
    WRITER_SA,
    _auth_step,
    _job_text,
    _parse,
    _yaml_lines,
    assert_workflow_guards,
)

REPO = Path(__file__).resolve().parents[1]
WORKFLOW_REL = ".github/workflows/risk_cap_history_poc.yml"
R5_WORKFLOW_REL = ".github/workflows/risk_cap_wif_negative_r5.yml"
PERM_SCRIPT_REL = "scripts/risk_cap_permission_test.py"
NEG_SCRIPT_REL = "scripts/risk_cap_wif_negative.py"
READER_SA = "risk-cap-reader@mystock20260823.iam.gserviceaccount.com"
READONLY = "https://www.googleapis.com/auth/spreadsheets.readonly"
READER_SECRET = "RISK_CAP_READER_TEST_SA_JSON"
PIP_LINE = 'pip install "google-auth>=2.0.0,<4.0" "requests>=2.31.0,<3.0.0"'
NEW_JOBS = ("permission_test_writer", "permission_test_reader", "wif_negative_r4", "permission_test_branch_guard")
BRANCH_GUARD_IF = ("${{ (inputs.mode == 'permission-test-writer' || inputs.mode == 'permission-test-reader') "
                   "&& github.ref != 'refs/heads/main' }}")


def _wf() -> str:
    return (REPO / WORKFLOW_REL).read_text(encoding="utf-8")


def _r5() -> str:
    return (REPO / R5_WORKFLOW_REL).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# 1. workflow 守衛
# ══════════════════════════════════════════════════════════════════════════
def _assert_pinned(job: dict, block: str, expected_actions: set[str]) -> None:
    uses = [s["uses"] for s in job["steps"] if "uses" in s]
    assert {u.split("@", 1)[0] for u in uses} == expected_actions, uses
    for u in uses:
        action, ref = u.split("@", 1)
        assert re.fullmatch(r"[0-9a-f]{40}", ref), f"必須以 40 字元 commit SHA 釘版：{u!r}"
        sha, ver = WIF_JOB_PINS[action]
        assert ref == sha, (u, sha)
        assert re.search(rf"^\s*uses:\s*{re.escape(u)}\s+#\s*{re.escape(ver)}\s*$", block, flags=re.MULTILINE), u
    assert len(re.findall(r"^\s*-?\s*uses:", block, flags=re.MULTILINE)) == len(uses)


def _common_prefix(job: dict) -> list[dict]:
    """checkout（persist-credentials false）→ setup-python 3.11 → pip（只兩個套件）。回傳其餘步驟。"""
    steps = job["steps"]
    assert steps[0]["uses"].startswith("actions/checkout@") and steps[0]["with"] == {"persist-credentials": False}
    assert steps[1]["uses"].startswith("actions/setup-python@") and steps[1]["with"] == {"python-version": "3.11"}
    assert steps[2]["run"] == PIP_LINE and "env" not in steps[2]
    assert "env" not in steps[0] and "env" not in steps[1]
    return steps[3:]


def assert_gate_guards(text: str) -> None:
    """新三個 job 的完整守衛 ＋ 既有 job 的 golden（呼叫既有 `assert_workflow_guards`）。"""
    assert_workflow_guards(text)                       # 既有：dry-run 逐字、wif_auth_only 逐字、頂層設定
    d = _parse(text)
    assert set(d["on"]) == {"workflow_dispatch"}
    assert d["permissions"] == {"contents": "read"}
    jobs = d["jobs"]
    assert {k: v for k, v in jobs["poc-dry-run"].items() if k != "if"} == DRY_RUN_JOB_BEFORE
    code_all = "\n".join(c for _, _, c in _yaml_lines(text))      # 不含註解
    for bad in ("schedule", "cron"):
        assert bad not in code_all, bad
    assert "schedule:" not in text and "cron:" not in text

    # ── writer（P1＋R1）──
    w, wt = jobs["permission_test_writer"], _job_text(text, "permission_test_writer")
    assert w["if"] == "${{ inputs.mode == 'permission-test-writer' && github.ref == 'refs/heads/main' }}"
    assert w["permissions"] == {"contents": "read", "id-token": "write"}
    assert set(w) == {"if", "runs-on", "timeout-minutes", "permissions", "steps"}, set(w)
    _assert_pinned(w, wt, {"actions/checkout", "actions/setup-python", "google-github-actions/auth"})
    rest = _common_prefix(w)
    assert len(rest) == 2
    auth = _auth_step(w)
    assert rest[0] is auth and "env" not in auth
    assert auth["with"] == {"workload_identity_provider": WIF_PROVIDER, "service_account": WRITER_SA,
                            "create_credentials_file": True, "export_environment_variables": True}, auth["with"]
    assert auth["with"] == _auth_step(jobs["wif_auth_only"])["with"]
    assert rest[1]["run"] == "python scripts/risk_cap_permission_test.py writer"
    assert rest[1]["env"] == {
        "RISK_CAP_HISTORY_SHEET_ID": "${{ secrets.RISK_CAP_HISTORY_SHEET_ID }}",
        "PORTFOLIO_SHEET_ID": "${{ secrets.PORTFOLIO_SHEET_ID }}",
        "STOCK_PORTFOLIO_SHEET_ID": "${{ secrets.STOCK_PORTFOLIO_SHEET_ID }}",
    }, rest[1]["env"]

    # ── reader（P2／R2／R3）：⛔ 沒有 id-token、⛔ 沒有 auth action、只限 main ──
    r, rt = jobs["permission_test_reader"], _job_text(text, "permission_test_reader")
    assert r["if"] == "${{ inputs.mode == 'permission-test-reader' && github.ref == 'refs/heads/main' }}"
    assert r["permissions"] == {"contents": "read"}, r["permissions"]
    assert set(r) == {"if", "runs-on", "timeout-minutes", "permissions", "steps"}, set(r)
    rt_code = "\n".join(c for _, _, c in _yaml_lines(rt))          # 不含註解（註解裡寫「沒有 id-token」）
    assert "id-token" not in rt_code and "google-github-actions" not in rt_code
    _assert_pinned(r, rt, {"actions/checkout", "actions/setup-python"})
    rest = _common_prefix(r)
    assert len(rest) == 1
    assert rest[0]["run"] == "python scripts/risk_cap_permission_test.py reader"
    assert rest[0]["env"] == {
        READER_SECRET: "${{ secrets.RISK_CAP_READER_TEST_SA_JSON }}",
        "RISK_CAP_HISTORY_SHEET_ID": "${{ secrets.RISK_CAP_HISTORY_SHEET_ID }}",
        "PORTFOLIO_SHEET_ID": "${{ secrets.PORTFOLIO_SHEET_ID }}",
        "STOCK_PORTFOLIO_SHEET_ID": "${{ secrets.STOCK_PORTFOLIO_SHEET_ID }}",
    }, rest[0]["env"]

    # ── R4：⛔ 沒有 auth action、⛔ 沒有 secrets；刻意**不**限 main ──
    n, nt = jobs["wif_negative_r4"], _job_text(text, "wif_negative_r4")
    assert n["if"] == "${{ inputs.mode == 'wif-negative-r4' }}"
    assert n["permissions"] == {"contents": "read", "id-token": "write"}
    assert set(n) == {"if", "runs-on", "timeout-minutes", "permissions", "steps"}, set(n)
    _assert_pinned(n, nt, {"actions/checkout", "actions/setup-python"})
    rest = _common_prefix(n)
    assert len(rest) == 1 and "env" not in rest[0]
    assert rest[0]["run"] == "python scripts/risk_cap_wif_negative.py --test R4"
    n_code = "\n".join(c for _, _, c in _yaml_lines(nt))
    assert "secrets." not in n_code and "google-github-actions" not in n_code

    # ── 非 main 觸發權限驗證 ⇒ 明確紅燈（稽核修正第 1 輪）：無 checkout、無 secrets、無 id-token ──
    g, gt = jobs["permission_test_branch_guard"], _job_text(text, "permission_test_branch_guard")
    assert g["if"] == BRANCH_GUARD_IF
    assert g["permissions"] == {"contents": "read"}
    assert set(g) == {"if", "runs-on", "timeout-minutes", "permissions", "steps"}, set(g)
    assert len(g["steps"]) == 1 and set(g["steps"][0]) == {"name", "run"}
    run = g["steps"][0]["run"]
    assert "permission tests must be dispatched on main; nothing was tested" in run and run.endswith("&& exit 1")
    g_code = "\n".join(c for _, _, c in _yaml_lines(gt))
    for bad in ("uses:", "secrets.", "id-token", "${{ github", "env:"):
        assert bad not in g_code.replace(BRANCH_GUARD_IF, ""), bad
    # 守衛條件必須恰好是 writer／reader 條件的補集（mode 相同、ref 相反）
    for job in ("permission_test_writer", "permission_test_reader"):
        assert jobs[job]["if"].endswith("&& github.ref == 'refs/heads/main' }}")

    # 一次性 reader secret：全檔只出現在 reader job（含註解都算）
    assert text.count(READER_SECRET) == rt.count(READER_SECRET) >= 2
    for job in NEW_JOBS:
        code = "\n".join(c for _, _, c in _yaml_lines(_job_text(text, job)))
        for bad in ("credentials_json", "token_format", "gspread", "GCP_SERVICE_ACCOUNT_JSON", "contents: write",
                    "git push", "git commit", "upload-artifact"):
            assert bad not in code, (job, bad)
        secrets = set(re.findall(r"secrets\.([A-Z0-9_]+)", code))
        assert secrets <= {"RISK_CAP_HISTORY_SHEET_ID", "PORTFOLIO_SHEET_ID", "STOCK_PORTFOLIO_SHEET_ID",
                           READER_SECRET}, (job, secrets)
        if job != "permission_test_reader":
            assert READER_SECRET not in code


def _parse_r5(text: str) -> dict:
    """受限解析器不支援「空值鍵」：唯一的 `workflow_dispatch:`（無 inputs）先換成哨兵再解析（恰好一次）。"""
    assert text.count("\n  workflow_dispatch:\n") == 1
    d = _parse(text.replace("\n  workflow_dispatch:\n", "\n  workflow_dispatch: __EMPTY__\n"))
    assert d["on"] == {"workflow_dispatch": "__EMPTY__"}, d["on"]
    return d


def assert_r5_guards(text: str) -> None:
    d = _parse_r5(text)
    assert set(d) == {"name", "on", "permissions", "jobs"}, set(d)
    assert d["permissions"] == {"contents": "read"}
    assert set(d["jobs"]) == {"wif_negative_r5"}
    j = d["jobs"]["wif_negative_r5"]
    assert set(j) == {"runs-on", "timeout-minutes", "permissions", "steps"}, set(j)
    assert j["permissions"] == {"contents": "read", "id-token": "write"}
    _assert_pinned(j, text, {"actions/checkout", "actions/setup-python"})
    rest = _common_prefix(j)
    assert len(rest) == 1 and "env" not in rest[0]
    assert rest[0]["run"] == "python scripts/risk_cap_wif_negative.py --test R5"
    code = "\n".join(c for _, _, c in _yaml_lines(text))
    for bad in ("secrets.", "schedule", "cron", "google-github-actions", "credentials_json", "token_format",
                "env:", "contents: write", "git push", "SHEET_ID", "SA_JSON", "risk_cap_permission_test"):
        assert bad not in code, bad
    assert "schedule:" not in text and "cron:" not in text and "secrets." not in text


class TestWorkflowGuards:
    def test_poc_workflow_path_unchanged(self):
        assert (REPO / WORKFLOW_REL).is_file()

    def test_gate_guards(self):
        assert_gate_guards(_wf())

    def test_r5_guards(self):
        assert_r5_guards(_r5())

    def test_r5_not_the_pinned_workflow_name(self):
        assert "risk_cap_history_poc.yml" not in R5_WORKFLOW_REL

    def test_no_schedule_in_any_vn1_workflow(self):
        for rel in (WORKFLOW_REL, R5_WORKFLOW_REL):
            t = (REPO / rel).read_text(encoding="utf-8")
            assert "schedule:" not in t and "cron:" not in t

    def test_reader_secret_only_in_poc_reader_job(self):
        for f in sorted((REPO / ".github/workflows").glob("*.y*ml")):
            t = f.read_text(encoding="utf-8")
            if f.name == Path(WORKFLOW_REL).name:
                assert t.count(READER_SECRET) == _job_text(t, "permission_test_reader").count(READER_SECRET)
            else:
                assert READER_SECRET not in t, f.name

    def test_new_scripts_only_invoked_by_gate_jobs(self):
        for f in sorted((REPO / ".github/workflows").glob("*.y*ml")):
            t = f.read_text(encoding="utf-8")
            if f.name not in (Path(WORKFLOW_REL).name, Path(R5_WORKFLOW_REL).name):
                assert "risk_cap_permission_test" not in t and "risk_cap_wif_negative" not in t, f.name


class TestWorkflowMutations:
    @staticmethod
    def _in_job(text: str, job: str, old: str, new: str) -> str:
        block = _job_text(text, job)
        assert block.count(old) == 1, (job, old)
        return text.replace(block, block.replace(old, new))

    @pytest.mark.parametrize("job,old,new", [
        # reader job 拿 id-token
        ("permission_test_reader", "    permissions:\n      contents: read\n",
         "    permissions:\n      contents: read\n      id-token: write\n"),
        # 拔掉 reader 的「只限 main」
        ("permission_test_reader", " && github.ref == 'refs/heads/main' }}", " }}"),
        # writer 改用 tag
        ("permission_test_writer", "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 # v3.0.0",
         "google-github-actions/auth@v3"),
        # writer 換 SA
        ("permission_test_writer", f"service_account: {WRITER_SA}",
         "service_account: fund-nav@other.iam.gserviceaccount.com"),
        # writer 換 provider
        ("permission_test_writer", "providers/github-actions\n", "providers/other\n"),
        # 一次性 reader secret 跑到 writer job
        ("permission_test_writer", "          STOCK_PORTFOLIO_SHEET_ID: ${{ secrets.STOCK_PORTFOLIO_SHEET_ID }}\n",
         "          STOCK_PORTFOLIO_SHEET_ID: ${{ secrets.STOCK_PORTFOLIO_SHEET_ID }}\n"
         "          RISK_CAP_READER_TEST_SA_JSON: ${{ secrets.RISK_CAP_READER_TEST_SA_JSON }}\n"),
        # R4 job 加上 secrets
        ("wif_negative_r4", "        run: python scripts/risk_cap_wif_negative.py --test R4\n",
         "        env:\n          X: ${{ secrets.FINMIND_TOKEN }}\n"
         "        run: python scripts/risk_cap_wif_negative.py --test R4\n"),
        # R4 job 限 main（反向測試就跑不起來）
        ("wif_negative_r4", "'wif-negative-r4' }}", "'wif-negative-r4' && github.ref == 'refs/heads/main' }}"),
        # reader checkout 改用 tag
        ("permission_test_reader", "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1",
         "actions/checkout@v4"),
        # writer 的 pip 多裝 gspread
        ("permission_test_writer", '"requests>=2.31.0,<3.0.0"\n', '"requests>=2.31.0,<3.0.0" gspread\n'),
    ])
    def test_gate_mutation_turns_red(self, job, old, new):
        with pytest.raises(AssertionError):
            assert_gate_guards(self._in_job(_wf(), job, old, new))

    @pytest.mark.parametrize("old,new", [
        ("  permission_test_branch_guard:\n", "  permission_test_branch_guard_disabled:\n"),
        ("&& exit 1\n", "\n"),
        ("github.ref != 'refs/heads/main' }}", "false }}"),
        ("inputs.mode == 'permission-test-writer' || inputs.mode == 'permission-test-reader'",
         "inputs.mode == 'permission-test-writer'"),
        ("      - name: Refuse non-main dispatch (nothing was tested)\n",
         "      - name: Refuse non-main dispatch (nothing was tested)\n"
         "        env:\n          X: ${{ secrets.RISK_CAP_HISTORY_SHEET_ID }}\n"),
    ])
    def test_branch_guard_mutation_turns_red(self, old, new):
        t = _wf()
        assert t.count(old) == 1, old
        with pytest.raises(AssertionError):
            assert_gate_guards(t.replace(old, new))

    def test_schedule_added_turns_red(self):
        t = _wf()
        assert t.count("on:\n  workflow_dispatch:\n") == 1
        with pytest.raises(AssertionError):
            assert_gate_guards(t.replace("on:\n  workflow_dispatch:\n",
                                         "on:\n  schedule:\n    - cron: '0 1 * * *'\n  workflow_dispatch:\n"))

    @pytest.mark.parametrize("old,new", [
        ("        run: python scripts/risk_cap_wif_negative.py --test R5\n",
         "        env:\n          X: ${{ secrets.RISK_CAP_HISTORY_SHEET_ID }}\n"
         "        run: python scripts/risk_cap_wif_negative.py --test R5\n"),
        ("on:\n  workflow_dispatch:\n", "on:\n  schedule:\n    - cron: '0 1 * * *'\n  workflow_dispatch:\n"),
        ("      id-token: write\n", ""),
        ("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0", "actions/setup-python@v5"),
    ])
    def test_r5_mutation_turns_red(self, old, new):
        t = _r5()
        assert t.count(old) == 1, old
        with pytest.raises(AssertionError):
            assert_r5_guards(t.replace(old, new))


# ══════════════════════════════════════════════════════════════════════════
# 2. 權限測試腳本
# ══════════════════════════════════════════════════════════════════════════
def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod             # @dataclass 需要
    spec.loader.exec_module(mod)
    return mod


S = _load(PERM_SCRIPT_REL, "_vn1_perm_test")
N = _load(NEG_SCRIPT_REL, "_vn1_wif_negative")

RC_ID = "RCSHEETID_SENTINEL_0123456789abcdef"
H1_ID = "HOLDINGS1_SENTINEL_aaaaaaaaaaaaaaaa"
H2_ID = "HOLDINGS2_SENTINEL_bbbbbbbbbbbbbbbb"
RUN_ID = "424242"
NOW = "2026-10-20T01:02:03+00:00"
TOKEN_SENTINEL = "ya29.SENTINEL-TOKEN-must-never-print-0123456789"
PK_SENTINEL = "-----BEGIN PRIVATE KEY-----PKSENTINELmustneverprint-----END PRIVATE KEY-----"
HEADER = list(P.HISTORY_COLUMNS)
OTHER_ROW = ["2026-10-19", "v1", "VALID"]
ID_SENTINELS = (RC_ID, H1_ID, H2_ID)


def _gerr(code: int, status: str, *reasons: str) -> dict:
    return {"error": {"code": code, "status": status, "message": f"secret detail {TOKEN_SENTINEL} {RC_ID}",
                      "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": r}
                                  for r in reasons]}}


DENIED = (403, _gerr(403, "PERMISSION_DENIED"))
NOT_FOUND = (404, _gerr(404, "NOT_FOUND"))
SCOPE = (403, _gerr(403, "PERMISSION_DENIED", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"))
DISABLED = (403, _gerr(403, "PERMISSION_DENIED", "SERVICE_DISABLED"))


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


_RANGE_RE = re.compile(r"^risk_cap_daily!([A-Z])(\d*):([A-Z])(\d*)$")


class FakeSheets:
    """System Risk Cap Sheet（`risk_cap_daily` 分頁 in-memory）＋ 持股 Sheet（固定回應）的假後端。"""

    def __init__(self, *, rows=None, holdings=(H1_ID, H2_ID), holdings_resp=DENIED, tab=True,
                 append_resp=None, report_offset=0, readback_exc=False, tamper_readback=False):
        self.rows = [list(r) for r in (rows if rows is not None else [HEADER, OTHER_ROW])]
        self.holdings = set(holdings)
        self.holdings_resp = holdings_resp
        self.tab = tab
        self.append_resp = append_resp
        self.report_offset = report_offset
        self.readback_exc = readback_exc
        self.tamper_readback = tamper_readback
        self.calls: list[tuple[str, str, dict, object]] = []

    # AuthorizedSession.request 介面
    def request(self, method, url, params=None, json=None, timeout=None, **kw):
        assert timeout and timeout > 0
        self.calls.append((method, url, dict(params or {}), json))
        sid = S.target_spreadsheet_id(url)
        if sid in self.holdings:
            return _Resp(*self.holdings_resp)
        assert sid == RC_ID, url
        rest = url[len(S.SHEETS_API) + 1 + len(sid):]
        if method == "GET" and rest == "":
            if (params or {}).get("fields") == "sheets.properties":
                sheets = [{"properties": {"sheetId": 7, "title": "risk_cap_daily", "index": 0}}] if self.tab else []
                sheets.append({"properties": {"sheetId": 9, "title": "other", "index": 1}})
                return _Resp(200, {"sheets": sheets})
            return _Resp(200, {"spreadsheetId": RC_ID})
        if method == "POST" and rest == ":batchUpdate":
            (req,) = json["requests"]
            rng = req["deleteDimension"]["range"]
            assert rng["sheetId"] == 7 and rng["dimension"] == "ROWS" and rng["endIndex"] - rng["startIndex"] == 1
            del self.rows[rng["startIndex"]:rng["endIndex"]]
            return _Resp(200, {"spreadsheetId": RC_ID, "replies": [{}]})
        assert rest.startswith("/values/"), url
        rng = unquote(rest[len("/values/"):])
        if method == "POST":
            assert rng == "risk_cap_daily!A1:append", rng
            if self.append_resp is not None:
                return _Resp(*self.append_resp)
            self.rows.append(list(json["values"][0]))
            r = len(self.rows) - self.report_offset
            return _Resp(200, {"spreadsheetId": RC_ID, "updates": {"updatedRange": f"risk_cap_daily!A{r}:D{r}"}})
        m = _RANGE_RE.fullmatch(rng)
        assert m, rng
        c1, r1, c2, r2 = m.group(1), m.group(2), m.group(3), m.group(4)
        cols = slice(ord(c1) - 65, ord(c2) - 64)
        if not r1:
            vals = [row[cols] for row in self.rows]
            return _Resp(200, {"range": f"risk_cap_daily!A1:B{max(len(self.rows), 1000)}", "values": vals})
        if c2 == "D" and self.readback_exc:
            raise ConnectionError(f"boom {TOKEN_SENTINEL}")
        vals = [row[cols] for row in self.rows[int(r1) - 1:int(r2)]]
        if c2 == "D" and self.tamper_readback and vals:
            vals = [vals[0][:2] + ["tampered"] + vals[0][3:]]
        body = {"range": rng}
        if any(vals):
            body["values"] = vals
        return _Resp(200, body)

    def methods_for(self, sid):
        return [m for m, u, _, _ in self.calls if S.target_spreadsheet_id(u) == sid]

    def posts(self):
        return [(u, j) for m, u, _, j in self.calls if m == "POST"]


class _AppendRaises(FakeSheets):
    """append 請求丟例外（`write_first=True` ＝ 伺服器其實已寫入、只是回應沒回來）。"""

    def __init__(self, *, write_first: bool, **kw):
        super().__init__(**kw)
        self.write_first = write_first

    def request(self, method, url, **kw):
        if method == "POST" and url.endswith(":append"):
            if self.write_first:
                super().request(method, url, **kw)
            else:
                self.calls.append((method, url, dict(kw.get("params") or {}), kw.get("json")))
            raise ConnectionError(f"reset {TOKEN_SENTINEL}")
        return super().request(method, url, **kw)


def assert_holdings_get_only(fake: FakeSheets) -> None:
    for method, url, params, body in fake.calls:
        if S.target_spreadsheet_id(url) in (H1_ID, H2_ID):
            assert method == "GET", (method, url)
            assert url == f"{S.SHEETS_API}/{S.target_spreadsheet_id(url)}" and params == {"fields": "spreadsheetId"}
            assert body is None


class _WriterCreds:
    service_account_email = WRITER_SA


def _wenv(**kw):
    env = {P.HISTORY_SHEET_ID_ENV_VAR: RC_ID, "PORTFOLIO_SHEET_ID": H1_ID, "STOCK_PORTFOLIO_SHEET_ID": H2_ID,
           "GITHUB_RUN_ID": RUN_ID}
    env.update(kw)
    return {k: v for k, v in env.items() if v is not None}


def _run_writer(fake, env=None, creds=None):
    return S.run_writer(_wenv() if env is None else env, creds_loader=lambda e: creds or _WriterCreds(),
                        session_factory=lambda c: fake, now_fn=lambda: NOW)


def _out(rep) -> str:
    return "\n".join(S.format_report(rep))


def assert_no_leak(text: str) -> None:
    for s in (*ID_SENTINELS, TOKEN_SENTINEL, PK_SENTINEL, "PKSENTINEL", "secret detail", "spreadsheetId\":"):
        assert s not in text, s


def _verdicts(rep) -> dict:
    return {r.test_id: r.verdict for r in rep.results}


class TestClassification:
    @pytest.mark.parametrize("http,body,verdict", [
        (*DENIED, "PASS"),
        (*NOT_FOUND, "PASS_NOT_FOUND"),
        (*DISABLED, "INCONCLUSIVE"),
        (*SCOPE, "INCONCLUSIVE"),
        # 稽核修正第 1 輪：允許清單 —— 帶任何 reason 的 403／404 一律 INCONCLUSIVE
        (403, _gerr(403, "PERMISSION_DENIED", "SECURITY_POLICY_VIOLATED"), "INCONCLUSIVE"),
        (403, _gerr(403, "PERMISSION_DENIED", "IAM_PERMISSION_DENIED"), "INCONCLUSIVE"),
        (403, _gerr(403, "PERMISSION_DENIED", "CONSUMER_SUSPENDED"), "INCONCLUSIVE"),
        (403, _gerr(403, "PERMISSION_DENIED", "SOME_FUTURE_REASON"), "INCONCLUSIVE"),
        (404, _gerr(404, "NOT_FOUND", "SOME_REASON"), "INCONCLUSIVE"),
        (403, {"error": {"code": 403, "status": "PERMISSION_DENIED", "details": []}}, "PASS"),
        (403, {"error": {"code": 403, "status": "PERMISSION_DENIED"}}, "PASS"),
        (403, _gerr(403, "PERMISSION_DENIED", "API_KEY_INVALID"), "INCONCLUSIVE"),
        (403, _gerr(403, "PERMISSION_DENIED", "weird reason with spaces"), "INCONCLUSIVE"),
        (403, None, "INCONCLUSIVE"),
        (404, None, "INCONCLUSIVE"),
        (403, _gerr(403, "FORBIDDEN"), "INCONCLUSIVE"),
        (401, _gerr(401, "UNAUTHENTICATED"), "INCONCLUSIVE"),
        (200, {"spreadsheetId": "x"}, "FAIL"),
        (204, None, "FAIL"),
        (500, _gerr(500, "INTERNAL"), "INCONCLUSIVE"),
        (429, _gerr(429, "RESOURCE_EXHAUSTED"), "INCONCLUSIVE"),
    ])
    def test_reverse_read(self, http, body, verdict):
        assert S.classify_reverse_read(http, body)[0] == verdict

    @pytest.mark.parametrize("http,body,verdict", [
        (*SCOPE, "PASS"),
        (*DENIED, "PASS"),
        (*DISABLED, "INCONCLUSIVE"),
        (403, _gerr(403, "PERMISSION_DENIED", "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "SERVICE_DISABLED"), "INCONCLUSIVE"),
        (*NOT_FOUND, "INCONCLUSIVE"),
        (400, _gerr(400, "INVALID_ARGUMENT"), "INCONCLUSIVE"),
        (200, {"updates": {}}, "FAIL"),
        (500, None, "INCONCLUSIVE"),
    ])
    def test_write_denied(self, http, body, verdict):
        assert S.classify_write_denied(http, body)[0] == verdict

    def test_reason_and_status_are_sanitized(self):
        status, reasons = S.google_error({"error": {"status": f"X {TOKEN_SENTINEL}",
                                                    "details": [{"reason": TOKEN_SENTINEL}]}})
        assert status == "?" and reasons == ("?",)

    @pytest.mark.parametrize("rng,row", [
        ("risk_cap_daily!A5:D5", 5), ("'risk_cap_daily'!A12:D12", 12),
        ("risk_cap_daily!A5:D6", None), ("risk_cap_daily!B5:E5", None), ("other!A5:D5", None),
        ("risk_cap_daily!A5", None), ("", None), (None, None), ("A5:D5", None),
    ])
    def test_parse_updated_row(self, rng, row):
        assert S.parse_updated_row(rng) == row


class TestGuardedSheets:
    def test_refuses_post_to_holdings_without_sending(self):
        fake = FakeSheets()
        api = S.GuardedSheets(fake, write_target=RC_ID, holdings_ids=[H1_ID, H2_ID])
        for sid in (H1_ID, H2_ID, "SOME_OTHER_SHEET_0000000"):
            with pytest.raises(S.HoldingsWriteRefused):
                api.post(f"{S.SHEETS_API}/{sid}:batchUpdate", {"requests": []})
            with pytest.raises(S.HoldingsWriteRefused):
                api.request("PUT", f"{S.SHEETS_API}/{sid}/values/A1", json_body={})
        with pytest.raises(S.HoldingsWriteRefused):
            api.get("https://www.googleapis.com/drive/v3/files")
        assert fake.calls == []

    def test_refuses_write_target_that_is_also_holdings(self):
        fake = FakeSheets(holdings=(RC_ID,))
        api = S.GuardedSheets(fake, write_target=RC_ID, holdings_ids=[RC_ID])
        with pytest.raises(S.HoldingsWriteRefused):
            api.post(f"{S.SHEETS_API}/{RC_ID}:batchUpdate", {"requests": []})
        assert fake.calls == []


class TestWriter:
    def test_happy_path(self):
        fake = FakeSheets()
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        out = _out(rep)
        assert rep.exit_code == 0, out
        assert _verdicts(rep) == {"R1[PORTFOLIO_SHEET_ID]": "PASS", "R1[STOCK_PORTFOLIO_SHEET_ID]": "PASS",
                                  "P1": "PASS"}
        assert fake.rows == before                                   # 測試列已刪，其他列一列都沒動
        assert_holdings_get_only(fake)
        # R1 先於任何對 System Risk Cap Sheet 的請求
        first_rc = next(i for i, c in enumerate(fake.calls) if S.target_spreadsheet_id(c[1]) == RC_ID)
        assert all(S.target_spreadsheet_id(c[1]) in (H1_ID, H2_ID) for c in fake.calls[:first_rc])
        posts = fake.posts()
        assert len(posts) == 2                                       # append ＋ 一次 deleteDimension
        (append_url, append_body), (del_url, del_body) = posts
        assert append_url.endswith(":append")
        assert append_body["values"] == [["PERMISSION_TEST", RUN_ID, NOW, S.P1_NOTE]]
        append_params = next(p for m, u, p, _ in fake.calls if u == append_url)
        assert append_params == {"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"}
        assert del_body == {"requests": [{"deleteDimension": {"range": {
            "sheetId": 7, "dimension": "ROWS", "startIndex": 2, "endIndex": 3}}}]}
        assert "clear" not in " ".join(c[1] for c in fake.calls).lower()
        assert f"identity={WRITER_SA}" in out and "P1 PASS" in out and "exit=0" in out
        assert_no_leak(out)

    def test_only_one_holdings_id_is_enough(self):
        fake = FakeSheets()
        rep = _run_writer(fake, env=_wenv(STOCK_PORTFOLIO_SHEET_ID=""))
        assert rep.exit_code == 0 and set(_verdicts(rep)) == {"R1[PORTFOLIO_SHEET_ID]", "P1"}

    def test_r1_403_permission_denied_passes(self):
        rep = _run_writer(FakeSheets(holdings_resp=DENIED))
        assert rep.exit_code == 0

    def test_r1_404_is_pass_not_found_with_note(self):
        fake = FakeSheets(holdings_resp=NOT_FOUND)
        rep = _run_writer(fake)
        out = _out(rep)
        assert rep.exit_code == 0, out
        assert _verdicts(rep) == {"R1[PORTFOLIO_SHEET_ID]": "PASS_NOT_FOUND",
                                  "R1[STOCK_PORTFOLIO_SHEET_ID]": "PASS_NOT_FOUND", "P1": "PASS"}
        assert ("ID not found or not visible — confirm the holdings Sheet ID secret is the live one "
                "(push_holdings_daily uses the same secret)") in out
        assert_no_leak(out)

    @pytest.mark.parametrize("resp", [
        DISABLED, SCOPE, (500, None),
        (403, _gerr(403, "PERMISSION_DENIED", "SECURITY_POLICY_VIOLATED")),
        (403, _gerr(403, "PERMISSION_DENIED", "IAM_PERMISSION_DENIED")),
        (403, _gerr(403, "PERMISSION_DENIED", "CONSUMER_SUSPENDED")),
    ])
    def test_r1_non_plain_errors_are_inconclusive_and_skip_p1(self, resp):
        """稽核修正第 1 輪：任何 R1 INCONCLUSIVE ⇒ P1 SKIPPED（不寫）。"""
        fake = FakeSheets(holdings_resp=resp)
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        assert rep.exit_code == 1
        assert _verdicts(rep)["R1[PORTFOLIO_SHEET_ID]"] == "INCONCLUSIVE"
        assert _verdicts(rep)["P1"] == "SKIPPED" and "未寫入任何列" in _out(rep)
        assert fake.posts() == [] and fake.methods_for(RC_ID) == [] and fake.rows == before

    def test_one_inconclusive_r1_among_passes_still_skips_p1(self):
        class _Mixed(FakeSheets):
            def request(self, method, url, **kw):
                if S.target_spreadsheet_id(url) == H2_ID:
                    self.calls.append((method, url, dict(kw.get("params") or {}), kw.get("json")))
                    return _Resp(*DISABLED)
                return super().request(method, url, **kw)
        fake = _Mixed()
        rep = _run_writer(fake)
        assert _verdicts(rep) == {"R1[PORTFOLIO_SHEET_ID]": "PASS", "R1[STOCK_PORTFOLIO_SHEET_ID]": "INCONCLUSIVE",
                                  "P1": "SKIPPED"}
        assert fake.posts() == []

    def test_r1_2xx_fails_and_stops_before_any_write(self):
        fake = FakeSheets(holdings_resp=(200, {"spreadsheetId": H1_ID}))
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        assert rep.exit_code == 1
        assert _verdicts(rep)["R1[PORTFOLIO_SHEET_ID]"] == "FAIL" and _verdicts(rep)["P1"] == "SKIPPED"
        assert fake.posts() == [] and fake.methods_for(RC_ID) == [] and fake.rows == before
        out = _out(rep)
        assert "立刻停下" in out
        assert_no_leak(out)

    def test_missing_tab_fails_without_append(self):
        fake = FakeSheets(tab=False)
        rep = _run_writer(fake)
        assert _verdicts(rep)["P1"] == "FAIL" and fake.posts() == [] and rep.exit_code == 1

    def test_append_rejected_no_delete(self):
        fake = FakeSheets(append_resp=DENIED)
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        p1 = rep.results[-1]
        assert (p1.verdict, p1.http, p1.status) == ("FAIL", 403, "PERMISSION_DENIED")
        assert [u for u, _ in fake.posts() if u.endswith(":batchUpdate")] == []
        assert fake.rows == before and rep.manual_cleanup == []

    def test_failure_after_append_still_deletes_via_finally(self):
        fake = FakeSheets(readback_exc=True)
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        out = _out(rep)
        assert _verdicts(rep)["P1"] == "FAIL" and rep.exit_code == 1
        assert fake.rows == before                                  # 讀回例外後仍刪掉了測試列
        assert "readback=NG" in out and "delete=ok" in out and "verify_gone=ok" in out
        assert "ConnectionError" in out
        assert_no_leak(out)

    @pytest.mark.parametrize("write_first", [False, True])
    def test_append_exception_always_prints_manual_check(self, write_first):
        """稽核修正第 1 輪：append 請求例外 ⇒ 結果不明 ⇒ P1 FAIL、一律印人工確認指引（即使搜尋沒找到）；
        若其實已寫入，搜尋到唯一標記列仍會刪掉。"""
        fake = _AppendRaises(write_first=write_first)
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        out = _out(rep)
        assert _verdicts(rep)["P1"] == "FAIL" and rep.exit_code == 1
        assert fake.rows == before
        assert len(rep.manual_cleanup) == 1
        text = rep.manual_cleanup[0]
        assert "PERMISSION_TEST" in text and RUN_ID in text and "risk_cap_daily" in text
        assert "整個分頁搜尋" in text and "A 欄" not in text
        assert "人工確認" in out and "ConnectionError" in out
        assert_no_leak(out)

    @pytest.mark.parametrize("updated", [None, "risk_cap_daily!B9:E9", "garbage"])
    def test_append_2xx_unparseable_range_prints_manual_check(self, updated):
        class _Odd(FakeSheets):
            def request(self, method, url, **kw):
                resp = super().request(method, url, **kw)
                if method == "POST" and url.endswith(":append"):
                    body = dict(resp._body)
                    body["updates"] = {} if updated is None else {"updatedRange": updated}
                    return _Resp(200, body)
                return resp
        fake = _Odd()
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        assert _verdicts(rep)["P1"] == "FAIL" and rep.manual_cleanup
        assert fake.rows == before                                   # 搜尋到唯一標記列 ⇒ 仍清掉

    @pytest.mark.parametrize("resp,unknown", [((503, None), True), ((500, _gerr(500, "INTERNAL")), True),
                                              ((429, _gerr(429, "RESOURCE_EXHAUSTED")), True),
                                              (DENIED, False), ((400, _gerr(400, "INVALID_ARGUMENT")), False)])
    def test_append_error_manual_check_only_when_outcome_unknown(self, resp, unknown):
        fake = FakeSheets(append_resp=resp)
        rep = _run_writer(fake)
        assert _verdicts(rep)["P1"] == "FAIL"
        assert bool(rep.manual_cleanup) is unknown

    def test_readback_mismatch_fails_but_cleans_up(self):
        fake = FakeSheets(tamper_readback=True)
        before = [list(r) for r in fake.rows]
        rep = _run_writer(fake)
        assert _verdicts(rep)["P1"] == "FAIL" and fake.rows == before

    def test_mismatched_row_is_not_deleted_marker_row_is(self):
        """append 回報的列號指到別人的列（OTHER_ROW）⇒ 再讀確認不符 ⇒ 不刪那一列；搜尋到唯一標記列才刪它。"""
        fake = FakeSheets(report_offset=1)
        rep = _run_writer(fake)
        assert _verdicts(rep)["P1"] == "FAIL"                      # 讀回對不上
        assert fake.rows == [HEADER, OTHER_ROW]                     # OTHER_ROW 還在、標記列已刪
        dels = [j for u, j in fake.posts() if u.endswith(":batchUpdate")]
        assert len(dels) == 1 and dels[0]["requests"][0]["deleteDimension"]["range"]["startIndex"] == 2

    def test_duplicate_markers_never_delete_and_ask_manual_cleanup(self):
        orphan = ["PERMISSION_TEST", RUN_ID, "earlier", "x"]
        fake = FakeSheets(rows=[HEADER, orphan, OTHER_ROW], report_offset=1)
        rep = _run_writer(fake)
        out = _out(rep)
        assert _verdicts(rep)["P1"] == "FAIL" and rep.exit_code == 1
        assert [u for u, _ in fake.posts() if u.endswith(":batchUpdate")] == []
        assert fake.rows[:3] == [HEADER, orphan, OTHER_ROW] and len(fake.rows) == 4
        assert rep.manual_cleanup and "PERMISSION_TEST" in out and RUN_ID in out and "人工確認／清理" in out
        assert_no_leak(out)

    def test_marker_with_other_run_id_is_untouched(self):
        other_run = ["PERMISSION_TEST", "999", "earlier", "x"]
        fake = FakeSheets(rows=[HEADER, other_run])
        rep = _run_writer(fake)
        assert rep.exit_code == 0 and fake.rows == [HEADER, other_run]

    @pytest.mark.parametrize("env,needle", [
        (_wenv(STOCK_PORTFOLIO_SHEET_ID=RC_ID), "完全隔離"),
        (_wenv(PORTFOLIO_SHEET_ID=RC_ID, STOCK_PORTFOLIO_SHEET_ID=None), "完全隔離"),
        (_wenv(PORTFOLIO_SHEET_ID=None, STOCK_PORTFOLIO_SHEET_ID=None), "一個都沒設"),
        (_wenv(**{P.HISTORY_SHEET_ID_ENV_VAR: None}), "未設定"),
        (_wenv(GITHUB_RUN_ID=None), "GITHUB_RUN_ID"),
        (_wenv(PORTFOLIO_SHEET_ID="bad id/with spaces"), "格式"),
    ])
    def test_preconditions_refuse_without_requests(self, env, needle):
        def _no_session(c):
            raise AssertionError("前置條件被拒時不得建立 session")
        rep = S.run_writer(env, creds_loader=lambda e: _WriterCreds(), session_factory=_no_session)
        out = _out(rep)
        assert rep.exit_code == 2 and needle in rep.refused and "REFUSED" in out
        assert_no_leak(out)

    def test_refuses_wrong_impersonation_target(self):
        class _Other:
            service_account_email = "fund-nav@other.iam.gserviceaccount.com"
        rep = S.run_writer(_wenv(), creds_loader=lambda e: _Other(),
                           session_factory=lambda c: pytest.fail("不得建立 session"))
        assert rep.exit_code == 2

    def test_default_loader_refuses_sa_key_file(self, tmp_path):
        key = tmp_path / "k.json"
        key.write_text(json.dumps({"type": "service_account", "private_key": PK_SENTINEL}), encoding="utf-8")
        rep = S.run_writer(_wenv(GOOGLE_APPLICATION_CREDENTIALS=str(key)),
                           session_factory=lambda c: pytest.fail("不得建立 session"))
        out = _out(rep)
        assert rep.exit_code == 2 and "external_account" in rep.refused
        assert_no_leak(out)
        rep = S.run_writer(_wenv(), session_factory=lambda c: pytest.fail("x"))
        assert rep.exit_code == 2                                      # 沒有 GAC

    def test_default_loader_with_real_google_auth_external_account(self, tmp_path, monkeypatch):
        """真的 google-auth 讀 WIF external_account 檔（auth action 產生的形狀）：身分＝writer、scope＝WRITER_SCOPES。"""
        pytest.importorskip("google.auth")
        cred = {"type": "external_account", "audience": "//iam.googleapis.com/" + WIF_PROVIDER,
                "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
                "token_url": "https://sts.googleapis.com/v1/token",
                "credential_source": {"url": "https://example.invalid/token",
                                      "headers": {"Authorization": f"Bearer {TOKEN_SENTINEL}"},
                                      "format": {"type": "json", "subject_token_field_name": "value"}},
                "service_account_impersonation_url": ("https://iamcredentials.googleapis.com/v1/projects/-/"
                                                      f"serviceAccounts/{WRITER_SA}:generateAccessToken")}
        path = tmp_path / "gha-creds-test.json"
        path.write_text(json.dumps(cred), encoding="utf-8")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "mystock20260823")
        seen = []
        fake = FakeSheets()

        def _factory(c):
            seen.append(c)
            return fake
        rep = S.run_writer(_wenv(GOOGLE_APPLICATION_CREDENTIALS=str(path)), session_factory=_factory,
                           now_fn=lambda: NOW)
        out = _out(rep)
        assert rep.exit_code == 0, out
        assert seen[0].service_account_email == WRITER_SA and tuple(seen[0].scopes) == P.WRITER_SCOPES
        assert_no_leak(out)

    def test_loader_exception_is_fail_without_message(self):
        def _boom(e):
            raise RuntimeError(f"leak {TOKEN_SENTINEL}")
        rep = S.run_writer(_wenv(), creds_loader=_boom, session_factory=lambda c: pytest.fail("x"))
        out = _out(rep)
        assert rep.exit_code == 1 and "RuntimeError" in out
        assert_no_leak(out)

    def test_session_exception_on_r1_is_inconclusive_no_leak(self):
        class _Boom(FakeSheets):
            def request(self, method, url, **kw):
                if S.target_spreadsheet_id(url) == H1_ID:
                    raise RuntimeError(f"RefreshError {TOKEN_SENTINEL}")
                return super().request(method, url, **kw)
        rep = _run_writer(_Boom())
        out = _out(rep)
        assert _verdicts(rep)["R1[PORTFOLIO_SHEET_ID]"] == "INCONCLUSIVE" and rep.exit_code == 1
        assert_no_leak(out)


def _reader_info(**kw):
    info = {"type": "service_account", "project_id": "mystock20260823", "private_key_id": "abc",
            "private_key": PK_SENTINEL, "client_email": READER_SA, "client_id": "1",
            "token_uri": "https://oauth2.googleapis.com/token"}
    info.update(kw)
    return info


class _ReaderCreds:
    def __init__(self, scopes, email=READER_SA):
        self.scopes = list(scopes)
        self.service_account_email = email


def _renv(info=None, **kw):
    env = _wenv(**kw)
    env[S.READER_TEST_SA_JSON_ENV] = json.dumps(_reader_info() if info is None else info)
    return env


def _run_reader(fake, env=None, seen=None, creds=None):
    def _factory(info, scopes):
        if seen is not None:
            seen.append((dict(info), tuple(scopes)))
        return creds or _ReaderCreds(scopes)
    return S.run_reader(_renv() if env is None else env, creds_factory=_factory, session_factory=lambda c: fake)


class TestReader:
    def test_happy_path(self):
        fake = FakeSheets(append_resp=SCOPE)
        before = [list(r) for r in fake.rows]
        seen = []
        rep = _run_reader(fake, seen=seen)
        out = _out(rep)
        assert rep.exit_code == 0, out
        assert _verdicts(rep) == {"P2": "PASS", "R2[PORTFOLIO_SHEET_ID]": "PASS",
                                  "R2[STOCK_PORTFOLIO_SHEET_ID]": "PASS", "R3": "PASS"}
        assert seen and seen[0][1] == (READONLY,)                   # scope 恰好 readonly
        assert fake.rows == before
        assert_holdings_get_only(fake)
        assert [u for u, _ in fake.posts()] == [S._values_url(RC_ID, "risk_cap_daily!A1", ":append")]
        assert fake.posts()[0][1]["values"][0][:2] == ["PERMISSION_TEST_R3_SHOULD_FAIL", RUN_ID]
        assert "rows=2" in out and "scope 層" in out and "ACL 層未被單獨驗到" in out
        assert f"identity={READER_SA}" in out
        assert_no_leak(out)

    def test_p2_empty_tab_still_passes(self):
        rep = _run_reader(FakeSheets(rows=[], append_resp=SCOPE))
        out = _out(rep)
        assert _verdicts(rep)["P2"] == "PASS" and "tab empty" in out
        assert "P2 proves read access + tab exists; tab empty → content not demonstrated" in out

    def test_r3_2xx_fails_loud_with_manual_cleanup(self):
        fake = FakeSheets()                                          # append 成功 ＝ reader 寫得進去
        rep = _run_reader(fake)
        out = _out(rep)
        assert _verdicts(rep)["R3"] == "FAIL" and rep.exit_code == 1
        assert "PERMISSION_TEST_R3_SHOULD_FAIL" in out and "人工確認／清理" in out
        assert [u for u, _ in fake.posts() if u.endswith(":batchUpdate")] == []   # reader 不嘗試刪除
        assert_no_leak(out)

    def test_r3_service_disabled_inconclusive(self):
        rep = _run_reader(FakeSheets(append_resp=DISABLED))
        assert _verdicts(rep)["R3"] == "INCONCLUSIVE" and rep.exit_code == 1

    def test_r2_2xx_fails(self):
        rep = _run_reader(FakeSheets(append_resp=SCOPE, holdings_resp=(200, {"spreadsheetId": H1_ID})))
        assert _verdicts(rep)["R2[PORTFOLIO_SHEET_ID]"] == "FAIL" and rep.exit_code == 1
        assert_no_leak(_out(rep))

    @pytest.mark.parametrize("info,needle", [
        (_reader_info(type="external_account"), "service_account"),
        (_reader_info(client_email=WRITER_SA), "client_email"),
        (_reader_info(client_email="fund-nav@x.iam.gserviceaccount.com"), "client_email"),
        ([1, 2], "service_account"),
    ])
    def test_refuses_bad_reader_json(self, info, needle):
        rep = S.run_reader(_renv(info), creds_factory=lambda i, s: pytest.fail("x"),
                           session_factory=lambda c: pytest.fail("x"))
        out = _out(rep)
        assert rep.exit_code == 2 and needle in rep.refused
        assert_no_leak(out)
        assert WRITER_SA not in out and "fund-nav" not in out

    def test_refuses_missing_or_invalid_json(self):
        env = _wenv()
        rep = S.run_reader(env, creds_factory=lambda i, s: pytest.fail("x"))
        assert rep.exit_code == 2
        env[S.READER_TEST_SA_JSON_ENV] = "{not json " + PK_SENTINEL
        rep = S.run_reader(env, creds_factory=lambda i, s: pytest.fail("x"))
        assert rep.exit_code == 2
        assert_no_leak(_out(rep))

    def test_refuses_creds_with_wider_scope(self):
        creds = _ReaderCreds([READONLY, "https://www.googleapis.com/auth/spreadsheets"])
        rep = _run_reader(FakeSheets(), creds=creds)
        assert rep.exit_code == 2 and "readonly" in rep.refused

    def test_refuses_creds_with_other_identity(self):
        rep = _run_reader(FakeSheets(), creds=_ReaderCreds([READONLY], email=WRITER_SA))
        assert rep.exit_code == 2

    def test_reader_preconditions_shared(self):
        rep = S.run_reader(_renv(STOCK_PORTFOLIO_SHEET_ID=RC_ID), creds_factory=lambda i, s: pytest.fail("x"))
        assert rep.exit_code == 2

    def test_real_google_auth_creds_scope_exactly_readonly(self):
        """用真的 google-auth（requirements.txt 版本）＋ 測試用 RSA key 建 creds：scope 必須恰好 readonly。"""
        pytest.importorskip("google.oauth2.service_account")
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
        info = _reader_info(private_key=pem)
        creds = S._default_reader_creds(info, P.READER_SCOPES)
        assert tuple(creds.scopes) == (READONLY,) and creds.service_account_email == READER_SA
        fake = FakeSheets(append_resp=SCOPE)
        rep = S.run_reader(_renv(info), session_factory=lambda c: fake)      # 預設 creds_factory
        out = _out(rep)
        assert rep.exit_code == 0, out
        assert pem.splitlines()[1] not in out and "PRIVATE KEY" not in out


class TestPermissionScriptStatic:
    def test_imports_and_strings(self):
        import ast
        src = (REPO / PERM_SCRIPT_REL).read_text(encoding="utf-8")
        tree = ast.parse(src)
        imps = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imps |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                imps.add(n.module)
        assert not [i for i in imps if i.split(".")[0] in ("gspread", "streamlit", "googleapiclient", "src")], imps
        assert {i for i in imps if i.startswith("shared")} == {"shared.risk_cap_history_policy"}
        for bad in ("GCP_SERVICE_ACCOUNT_JSON", "gcp_service_account", "drive.googleapis", "/auth/drive",
                    "values:clear", ":clear", "write_text", "write_bytes", "RISK_CAP_HISTORY_READER_SA_JSON"):
            assert bad not in src, bad
        # Sheet ID 只從環境變數來：原始碼不得出現任何像 Sheet ID 的長字串
        assert not re.search(r"['\"][A-Za-z0-9_\-]{40,}['\"]", src)

    def test_uses_l0_constants(self):
        assert S.WRITER_SCOPES == P.WRITER_SCOPES and S.READER_SCOPES == P.READER_SCOPES
        assert S.HISTORY_WORKSHEET_NAME == P.HISTORY_WORKSHEET_NAME == "risk_cap_daily"
        assert S.HISTORY_SHEET_ID_ENV_VAR == P.HISTORY_SHEET_ID_ENV_VAR
        assert P.PRODUCTION_WRITE_APPROVED is False

    def test_main_refuses_without_env(self, monkeypatch, capsys):
        for k in (P.HISTORY_SHEET_ID_ENV_VAR, "PORTFOLIO_SHEET_ID", "STOCK_PORTFOLIO_SHEET_ID"):
            monkeypatch.delenv(k, raising=False)
        assert S.main(["writer"]) == 2 and S.main(["reader"]) == 2
        assert "REFUSED" in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════════
# 3. WIF 反向測試腳本（R4／R5）
# ══════════════════════════════════════════════════════════════════════════
REPO_FULL = "linchen-20200325/my-stock-dashboard"
REQ_TOKEN = "GH-REQUEST-TOKEN-SENTINEL-0123456789"
STS_TOKEN = "ya29.STS-ACCESS-TOKEN-SENTINEL-abcdef0123456789"


def _jwt(**claims) -> str:
    base = {"ref": "refs/heads/test-r4", "repository_id": "1241930464", "repository_owner_id": "285537060",
            "workflow_ref": f"{REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/test-r4",
            "event_name": "workflow_dispatch", "sub": "repo:x:ref:refs/heads/test-r4", "aud": N.OIDC_AUDIENCE}
    base.update(claims)

    def seg(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{seg({'alg': 'RS256', 'typ': 'JWT'})}.{seg(base)}.SIGNATURESENTINELsignaturesentinel"


def _nenv(test="R4", **kw):
    if test == "R4":
        env = {"GITHUB_REF": "refs/heads/test-r4",
               "GITHUB_WORKFLOW_REF": f"{REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/test-r4"}
    else:
        env = {"GITHUB_REF": "refs/heads/main",
               "GITHUB_WORKFLOW_REF": f"{REPO_FULL}/.github/workflows/risk_cap_wif_negative_r5.yml@refs/heads/main"}
    env.update({"ACTIONS_ID_TOKEN_REQUEST_URL": "https://token.actions.example.invalid/idtoken?api-version=2.0",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN": REQ_TOKEN})
    env.update(kw)
    return {k: v for k, v in env.items() if v is not None}


def _r5_jwt(**kw):
    claims = {"ref": "refs/heads/main",
              "workflow_ref": f"{REPO_FULL}/.github/workflows/risk_cap_wif_negative_r5.yml@refs/heads/main"}
    claims.update(kw)
    return _jwt(**claims)


REJECT = (400, {"error": "unauthorized_client",
                "error_description": "The given credential is rejected by the attribute condition."})


class _Net:
    def __init__(self, jwt, sts=REJECT, sts_exc=None, oidc=None):
        self.jwt, self.sts, self.sts_exc, self.oidc = jwt, sts, sts_exc, oidc
        self.gets, self.posts = [], []

    def get(self, url, headers, timeout):
        self.gets.append((url, dict(headers), timeout))
        return self.oidc if self.oidc is not None else (200, {"count": 1, "value": self.jwt})

    def post(self, url, data, timeout):
        self.posts.append((url, dict(data), timeout))
        if self.sts_exc:
            raise self.sts_exc
        return self.sts


def _neg(test, net, env=None):
    return N.run_negative(test, environ=_nenv(test) if env is None else env,
                          http_get=net.get, http_post_form=net.post)


def _nout(r) -> str:
    return "\n".join(N.format_result(r))


def assert_neg_no_leak(text: str, jwt: str) -> None:
    for s in (jwt, jwt.split(".")[1], "SIGNATURESENTINEL", REQ_TOKEN, STS_TOKEN):
        assert s not in text, s


class TestWifNegative:
    def test_audience_matches_auth_action_default(self):
        # google-github-actions/auth v3.0.0 src/main.ts：`https://iam.googleapis.com/${workloadIdentityProvider}`
        assert N.OIDC_AUDIENCE == "https://iam.googleapis.com/" + WIF_PROVIDER
        # workload_identity_federation.ts：`//${iamHost}/${provider}`
        assert N.STS_AUDIENCE == "//iam.googleapis.com/" + WIF_PROVIDER
        assert N.WIF_PROVIDER == WIF_PROVIDER

    @pytest.mark.parametrize("test", ["R4", "R5"])
    def test_pass_on_attribute_condition_rejection(self, test):
        jwt = _jwt() if test == "R4" else _r5_jwt()
        net = _Net(jwt)
        r = _neg(test, net)
        out = _nout(r)
        assert (r.verdict, r.exit_code, r.http) == ("PASS", 0, 400), out
        # OIDC 請求：audience 正確、請求 token 只放 header
        (url, headers, _), = net.gets
        assert url == ("https://token.actions.example.invalid/idtoken?api-version=2.0&audience="
                       "https%3A%2F%2Fiam.googleapis.com%2Fprojects%2F847745640234%2Flocations%2Fglobal%2F"
                       "workloadIdentityPools%2Fstock-dashboard-github%2Fproviders%2Fgithub-actions")
        assert headers["Authorization"] == f"bearer {REQ_TOKEN}"
        # STS：與 auth action 相同的欄位
        (surl, form, _), = net.posts
        assert surl == "https://sts.googleapis.com/v1/token"
        assert form == {"grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                        "audience": "//iam.googleapis.com/" + WIF_PROVIDER,
                        "scope": "https://www.googleapis.com/auth/cloud-platform",
                        "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
                        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
                        "subject_token": jwt}
        assert "error=unauthorized_client" in out and "rejected by the attribute condition" in out
        assert "claim.workflow_ref=" + REPO_FULL in out and "claim.repository_id=1241930464" in out
        assert "claim.event_name=workflow_dispatch" in out
        assert_neg_no_leak(out, jwt)

    def test_sts_2xx_is_fail_and_token_never_printed(self, capsys, monkeypatch):
        jwt = _jwt()
        net = _Net(jwt, sts=(200, {"access_token": STS_TOKEN, "issued_token_type": "x", "token_type": "Bearer",
                                   "expires_in": 3599}))
        monkeypatch.setattr(N, "_http_get", net.get)
        monkeypatch.setattr(N, "_http_post_form", net.post)
        for k, v in _nenv("R4").items():
            monkeypatch.setenv(k, v)
        monkeypatch.setattr(N, "run_negative", lambda t, _rn=N.run_negative: _rn(
            t, http_get=N._http_get, http_post_form=N._http_post_form))
        assert N.main(["--test", "R4"]) == 1
        out = capsys.readouterr()
        text = out.out + out.err
        assert "FAIL" in text and "沒擋住" in text
        assert_neg_no_leak(text, jwt)

    @pytest.mark.parametrize("sts", [
        (500, {"error": "internal"}),
        (503, None),
        (400, {"error": "invalid_target", "error_description": "The target service indicated by the audience is invalid"}),
        (400, {"error": "invalid_grant", "error_description": "The audience in ID Token does not match"}),
        (400, {"error": "unauthorized_client", "error_description": "something else"}),
        # 稽核修正第 1 輪：設定錯誤 ≠ 被條件拒絕
        (400, {"error": "invalid_grant", "error_description": "Error evaluating the attribute condition"}),
        (400, {"error": "unauthorized_client", "error_description": "Invalid attribute condition expression"}),
        (400, {"error": "invalid_request", "error_description": "rejected by the attribute condition"}),
        (500, {"error": "unauthorized_client", "error_description": "rejected by the attribute condition"}),
        (403, {"error": {"code": 403, "status": "PERMISSION_DENIED"}}),
        (400, None),
        (302, None),
    ])
    def test_other_responses_are_inconclusive(self, sts):
        r = _neg("R4", _Net(_jwt(), sts=sts))
        assert (r.verdict, r.exit_code) == ("INCONCLUSIVE", 1)

    def test_invalid_grant_with_attribute_condition_passes(self):
        r = _neg("R4", _Net(_jwt(), sts=(400, {"error": "invalid_grant",
                                               "error_description": "Credential REJECTED BY THE ATTRIBUTE CONDITION"})))
        assert r.verdict == "PASS"

    def test_sts_exception_inconclusive_no_leak(self):
        jwt = _jwt()
        r = _neg("R4", _Net(jwt, sts_exc=ConnectionError(f"proxy {jwt} {REQ_TOKEN}")))
        out = _nout(r)
        assert (r.verdict, r.exit_code) == ("INCONCLUSIVE", 1) and "ConnectionError" in out
        assert_neg_no_leak(out, jwt)

    def test_oidc_failure_inconclusive(self):
        r = _neg("R4", _Net("", oidc=(403, {"message": "no"})))
        assert (r.verdict, r.exit_code) == ("INCONCLUSIVE", 1)
        r = _neg("R4", _Net("not-a-jwt"))
        assert r.verdict == "INCONCLUSIVE"

    def test_error_description_is_sanitized(self):
        jwt = _jwt()
        desc = f"rejected by the attribute condition {jwt} {STS_TOKEN} " + "A" * 60
        r = _neg("R4", _Net(jwt, sts=(400, {"error": "unauthorized_client", "error_description": desc})))
        out = _nout(r)
        assert r.verdict == "PASS" and "[REDACTED]" in out and "A" * 60 not in out
        assert_neg_no_leak(out, jwt)

    @pytest.mark.parametrize("test,env_kw", [
        ("R4", {"GITHUB_REF": "refs/heads/main"}),
        ("R4", {"GITHUB_REF": ""}),
        ("R4", {"GITHUB_WORKFLOW_REF": f"{REPO_FULL}/.github/workflows/risk_cap_wif_negative_r5.yml@refs/heads/x"}),
        ("R5", {"GITHUB_WORKFLOW_REF": f"{REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/main"}),
        ("R5", {"GITHUB_REF": "refs/heads/test"}),
        ("R5", {"GITHUB_WORKFLOW_REF": ""}),
        ("R4", {"ACTIONS_ID_TOKEN_REQUEST_URL": None}),
        ("R5", {"ACTIONS_ID_TOKEN_REQUEST_TOKEN": None}),
    ])
    def test_env_preconditions_refuse_without_requests(self, test, env_kw):
        net = _Net(_jwt())
        r = _neg(test, net, env=_nenv(test, **env_kw))
        assert (r.verdict, r.exit_code) == ("REFUSED", 2)
        assert net.gets == [] and net.posts == []

    @pytest.mark.parametrize("test,jwt", [
        ("R4", _jwt(ref="refs/heads/main")),                                          # claim 說是 main
        ("R5", _r5_jwt(workflow_ref=f"{REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/main")),
        ("R4", _jwt(repository_id="999")),                                            # 不是本 repo
        ("R4", _jwt(repository_owner_id="1")),
    ])
    def test_claim_preconditions_refuse_before_sts(self, test, jwt):
        net = _Net(jwt)
        r = _neg(test, net)
        assert (r.verdict, r.exit_code) == ("REFUSED", 2) and len(net.gets) == 1 and net.posts == []
        assert_neg_no_leak(_nout(r), jwt)

    def test_claim_sanitizer_keeps_workflow_ref(self):
        wr = f"{REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/test-r4"
        assert N.sanitize_claim(wr) == wr
        assert "[REDACTED]" in N.sanitize_claim(_jwt())

    def test_static(self):
        import ast
        src = (REPO / NEG_SCRIPT_REL).read_text(encoding="utf-8")
        tree = ast.parse(src)
        imps = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imps |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not [i for i in imps if i.split(".")[0] in ("gspread", "streamlit", "src", "shared", "google")], imps
        for bad in ("sheets.googleapis", "GCP_SERVICE_ACCOUNT_JSON", "write_text", "print(jwt", "print(token"):
            assert bad not in src, bad


# ══════════════════════════════════════════════════════════════════════════
# 4. 腳本突變自驗
# ══════════════════════════════════════════════════════════════════════════
class TestScriptMutations:
    @pytest.mark.parametrize("resp", [DISABLED, SCOPE,
                                      (403, _gerr(403, "PERMISSION_DENIED", "SECURITY_POLICY_VIOLATED"))])
    def test_r1_allow_list_dropped_is_caught(self, resp):
        """突變：R1 允許清單拿掉「沒有 reason」條件（退回 block-list 前的寬鬆）⇒ 帶 reason 的 403 被判 PASS。"""
        mut = _mutated_module(PERM_SCRIPT_REL, (
            '    if http == 403 and status == "PERMISSION_DENIED" and not reasons:\n        return PASS, status, reason\n',
            '    if http == 403 and status == "PERMISSION_DENIED":\n        return PASS, status, reason\n'))
        assert mut.classify_reverse_read(*resp)[0] == "PASS"                # 突變體誤判 PASS
        assert S.classify_reverse_read(*resp)[0] == "INCONCLUSIVE"          # 真模組：上方參數化測試守住

    def test_not_found_label_collapsed_is_caught(self):
        mut = _mutated_module(PERM_SCRIPT_REL, (
            '        return PASS_NOT_FOUND, status, reason\n', '        return PASS, status, reason\n'))
        assert mut.classify_reverse_read(*NOT_FOUND)[0] == "PASS"
        assert S.classify_reverse_read(*NOT_FOUND)[0] == "PASS_NOT_FOUND"

    def test_r3_accepting_service_disabled_is_caught(self):
        mut = _mutated_module(PERM_SCRIPT_REL, ('    "SERVICE_DISABLED", "ACCESS_TOKEN_SCOPE_INSUFFICIENT",',
                                                '    "ACCESS_TOKEN_SCOPE_INSUFFICIENT",'))
        assert mut.classify_write_denied(*DISABLED)[0] == "PASS"
        assert S.classify_write_denied(*DISABLED)[0] == "INCONCLUSIVE"

    def test_r1_inconclusive_still_writing_is_caught(self):
        mut = _mutated_module(PERM_SCRIPT_REL, (
            "    if any(r.verdict not in PASSING_VERDICTS for r in rep.results):\n",
            "    if any(r.verdict == FAIL for r in rep.results):\n"))
        fake = FakeSheets(holdings_resp=DISABLED)
        mut.run_writer(_wenv(), creds_loader=lambda e: _WriterCreds(), session_factory=lambda c: fake,
                       now_fn=lambda: NOW)
        assert fake.posts()                                                 # 突變體照樣寫入
        fake_ok = FakeSheets(holdings_resp=DISABLED)
        _run_writer(fake_ok)
        assert fake_ok.posts() == []

    def test_sts_loose_phrase_is_caught(self):
        mut = _mutated_module(NEG_SCRIPT_REL, ('ATTRIBUTE_CONDITION_TEXT = "rejected by the attribute condition"\n',
                                               'ATTRIBUTE_CONDITION_TEXT = "attribute condition"\n'))
        body = {"error": "invalid_grant", "error_description": "Error evaluating the attribute condition"}
        assert mut.classify_sts(400, body)[0] == "PASS"
        assert N.classify_sts(400, body)[0] == "INCONCLUSIVE"

    def test_unknown_append_without_manual_note_is_caught(self):
        mut = _mutated_module(PERM_SCRIPT_REL, (
            "    if not cleanup_ok or not gone_ok or append_unknown:\n", "    if not cleanup_ok or not gone_ok:\n"))
        fake = _AppendRaises(write_first=False)
        rep = mut.run_writer(_wenv(), creds_loader=lambda e: _WriterCreds(), session_factory=lambda c: fake,
                             now_fn=lambda: NOW)
        assert rep.manual_cleanup == []                                     # 突變體不提醒
        assert _run_writer(_AppendRaises(write_first=False)).manual_cleanup

    def test_holdings_post_is_caught_by_guard_and_by_test(self):
        swap = ('        http, body = api.get(_meta_url(sid), {"fields": "spreadsheetId"})\n',
                '        http, body = api.post(_meta_url(sid), {"fields": "spreadsheetId"})\n')
        # (a) 只把 R1 改成 POST：GuardedSheets 擋下（不送出）⇒ R1 不再 PASS ⇒ happy path 轉紅
        mut = _mutated_module(PERM_SCRIPT_REL, swap)
        fake = FakeSheets()
        rep = mut.run_writer(_wenv(), creds_loader=lambda e: _WriterCreds(), session_factory=lambda c: fake,
                             now_fn=lambda: NOW)
        assert rep.exit_code != 0 and fake.methods_for(H1_ID) == []
        # (b) 再拔掉 GuardedSheets 的守衛：POST 真的送到持股 Sheet ⇒ assert_holdings_get_only 抓得到
        mut2 = _mutated_module(PERM_SCRIPT_REL, swap, (
            '        if method != "GET" and (target != self._write_target or target in self._holdings):\n',
            '        if False:\n'))
        fake2 = FakeSheets()
        mut2.run_writer(_wenv(), creds_loader=lambda e: _WriterCreds(), session_factory=lambda c: fake2,
                        now_fn=lambda: NOW)
        assert "POST" in fake2.methods_for(H1_ID)
        with pytest.raises(AssertionError):
            assert_holdings_get_only(fake2)

    def test_delete_without_recheck_deletes_wrong_row(self):
        """突變：拿掉「刪除前再讀確認」⇒ 指錯列時會刪到別人的列（真模組保住 OTHER_ROW，見 TestWriter）。"""
        mut = _mutated_module(PERM_SCRIPT_REL, (
            "        if http == 200 and _values(body) == [[P1_MARKER, run_id]]:\n", "        if True:\n"))
        fake = FakeSheets(report_offset=1)
        mut.run_writer(_wenv(), creds_loader=lambda e: _WriterCreds(), session_factory=lambda c: fake,
                       now_fn=lambda: NOW)
        assert OTHER_ROW not in fake.rows                                  # 突變體刪錯列
        fake_ok = FakeSheets(report_offset=1)
        _run_writer(fake_ok)
        assert fake_ok.rows == [HEADER, OTHER_ROW]

    def test_cleanup_outside_finally_leaves_row(self):
        """突變：把清理從 finally 移走（讀回例外時直接往外拋）⇒ 測試列殘留。真模組見 test_failure_after_append…。"""
        mut = _mutated_module(PERM_SCRIPT_REL, (
            "    except Exception as e:  # noqa: BLE001\n        step_note = _exc_note(\"append／讀回\", e)\n"
            "    finally:\n",
            "    except ZeroDivisionError as e:  # noqa: BLE001\n        step_note = _exc_note(\"append／讀回\", e)\n"
            "    else:\n"))
        fake = FakeSheets(readback_exc=True)
        with pytest.raises(ConnectionError):
            mut.run_writer(_wenv(), creds_loader=lambda e: _WriterCreds(), session_factory=lambda c: fake,
                           now_fn=lambda: NOW)
        assert any(r[0] == "PERMISSION_TEST" for r in fake.rows)

    def test_reader_scope_check_removed_is_caught(self):
        mut = _mutated_module(PERM_SCRIPT_REL, (
            '        if tuple(getattr(creds, "scopes", None) or ()) != (READONLY_SCOPE,):\n', "        if False:\n"))
        creds = _ReaderCreds([READONLY, "https://www.googleapis.com/auth/spreadsheets"])
        rep = mut.run_reader(_renv(), creds_factory=lambda i, s: creds, session_factory=lambda c: FakeSheets(
            append_resp=SCOPE))
        assert rep.exit_code == 0                                           # 突變體放行寬 scope
        assert _run_reader(FakeSheets(), creds=creds).exit_code == 2

    def test_sts_any_4xx_pass_is_caught(self):
        mut = _mutated_module(NEG_SCRIPT_REL, (
            "            and ATTRIBUTE_CONDITION_TEXT in desc.lower()):\n", "            and True):\n"))
        body = {"error": "invalid_grant", "error_description": "The audience in ID Token does not match"}
        assert mut.classify_sts(400, body)[0] == "PASS"
        assert N.classify_sts(400, body)[0] == "INCONCLUSIVE"

    def test_sts_2xx_not_fail_is_caught(self):
        mut = _mutated_module(NEG_SCRIPT_REL, ("    if 200 <= http < 300:\n        return FAIL, \"\", \"\"\n",
                                               "    if False:\n        return FAIL, \"\", \"\"\n"))
        assert mut.classify_sts(200, {"access_token": STS_TOKEN})[0] != "FAIL"
        assert N.classify_sts(200, {"access_token": STS_TOKEN})[0] == "FAIL"

    def test_r4_main_precondition_removed_is_caught(self):
        mut = _mutated_module(NEG_SCRIPT_REL, ('        if ref == MAIN_REF or not ref:\n', '        if not ref:\n'))
        assert mut.precondition_violation("R4", "refs/heads/main",
                                          f"{REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/main") == ""
        assert N.precondition_violation("R4", "refs/heads/main",
                                        f"{REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/main")
