"""probe_finmind_monthrev(DEC-154)守衛:workflow 結構 + 腳本行為。全程不連網(假 HTTP)。

token 一律用明顯假值;驗證它絕不出現在任何輸出(含例外路徑)。
"""
from __future__ import annotations

import importlib.util
import re
import sys
import types
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WF_PATH = ROOT / ".github" / "workflows" / "probe_finmind_monthrev.yml"
SCRIPT_PATH = ROOT / "scripts" / "probe_finmind_monthrev.py"
FAKE_TOKEN = "FAKE-TOKEN-do-not-use-0123456789"
TODAY = date(2026, 11, 8)


# ───────────────────────── workflow 結構(不依賴 yaml)─────────────────────────
def _code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def _block(code: str, key: str) -> list[str]:
    """頂層 `key:` 之下縮排的行。"""
    lines = code.splitlines()
    for i, l in enumerate(lines):
        if re.match(rf"^{key}:\s*$", l):
            out = []
            for j in lines[i + 1:]:
                if j.strip() and not j.startswith(" "):
                    break
                out.append(j)
            return out
    return []


def wf_violations(text: str) -> list[str]:
    code = _code(text)
    v: list[str] = []
    on_keys = re.findall(r"^  ([A-Za-z_]+):", "\n".join(_block(code, "on")), re.M)
    if on_keys != ["workflow_dispatch"]:
        v.append(f"on 觸發必須恰為 workflow_dispatch,實際 {on_keys}")
    if re.search(r"^on:[ \t]*\S", code, re.M):
        v.append("on 不得為行內寫法")
    if re.search(r"\b(schedule|push|pull_request\w*|workflow_run|cron)\b\s*:", code):
        v.append("含 schedule/push/pull_request/workflow_run/cron")
    perms = dict(re.findall(r"^  ([A-Za-z-]+):\s*(\S+)", "\n".join(_block(code, "permissions")), re.M))
    if perms != {"contents": "read"}:
        v.append(f"permissions 必須恰為 contents: read,實際 {perms}")
    if len(re.findall(r"^\s*permissions:", code, re.M)) != 1:
        v.append("permissions 只能在頂層出現一次(不得 job 層加權)")
    if not re.search(r"^concurrency:\s*\n\s+group:\s*\S+", code, re.M):
        v.append("缺 concurrency")
    m = re.search(r"timeout-minutes:\s*(\d+)", code)
    if not m or int(m.group(1)) > 10:
        v.append("timeout-minutes 缺或 > 10")
    if len(re.findall(r"^  [A-Za-z_-]+:\s*$", "\n".join(_block(code, "jobs")), re.M)) != 1:
        v.append("必須恰一個 job")
    if re.search(r"upload-artifact|download-artifact|actions/cache", code):
        v.append("含 artifact/cache")
    if re.search(r"\bgit\s+(push|commit|add|tag)\b|\bgh\s+(pr|workflow|api)\b|/dispatches", code):
        v.append("含 git 寫入 / gh 呼叫")
    if re.search(r"set\s+-[a-z]*x|\bprintenv\b|^\s*(run:\s*)?env\s*$|echo\s+.*(TOKEN|secrets)|\$FINMIND_TOKEN|\$\{FINMIND_TOKEN\}",
                 code, re.M):
        v.append("含可能洩漏 token 的指令")
    # secrets 暴露面:僅 FINMIND_TOKEN,且僅一處,且在執行腳本的步驟 env
    secs = re.findall(r"secrets\.([A-Za-z0-9_]+)", code)
    if secs != ["FINMIND_TOKEN"]:
        v.append(f"secrets 只能恰好引用 FINMIND_TOKEN 一次,實際 {secs}")
    steps = re.split(r"(?m)^      - ", code)[1:]
    holder = [s for s in steps if "secrets.FINMIND_TOKEN" in s]
    if len(holder) != 1 or "scripts/probe_finmind_monthrev.py" not in holder[0] or "env:" not in holder[0]:
        v.append("FINMIND_TOKEN 必須僅在執行腳本步驟的 env")
    runs = re.findall(r"^\s+run:\s*(.+)$", code, re.M)
    allowed = {"pip install -r requirements.txt", "python scripts/probe_finmind_monthrev.py"}
    if set(runs) - allowed:
        v.append(f"出現未允許的 run 指令 {sorted(set(runs) - allowed)}")
    if "${{ inputs." in "\n".join(l for l in code.splitlines() if re.match(r"^\s+run:", l)):
        v.append("inputs 不得直接內插進 run(注入風險)")
    mm = re.search(r"months:[\s\S]*?default:\s*'?(\d+)'?", code)
    if not mm or not (1 <= int(mm.group(1)) <= 12):
        v.append("months 預設缺或超出 1~12")
    ms = re.search(r"stock_ids:[\s\S]*?default:\s*'([^']*)'", code)
    if not ms or len([x for x in ms.group(1).split(",") if x.strip()]) > 5:
        v.append("stock_ids 預設缺或 > 5 檔")
    return v


def test_workflow_structure_clean():
    assert wf_violations(WF_PATH.read_text(encoding="utf-8")) == []


_WF_MUTS = {
    "加 schedule": lambda t: t.replace("on:\n  workflow_dispatch:", "on:\n  schedule:\n    - cron: '0 0 * * *'\n  workflow_dispatch:"),
    "加 push": lambda t: t.replace("on:\n  workflow_dispatch:", "on:\n  push:\n  workflow_dispatch:"),
    "加權限": lambda t: t.replace("  contents: read", "  contents: read\n  pull-requests: write"),
    "加 artifact": lambda t: t + "\n      - uses: actions/upload-artifact@v4\n",
    "加 git push": lambda t: t.replace("run: pip install -r requirements.txt", "run: git push origin HEAD"),
    "echo token": lambda t: t.replace("run: pip install -r requirements.txt", "run: echo $FINMIND_TOKEN"),
    "secret 外溢到 install 步驟": lambda t: t.replace(
        "      - name: Install deps\n", "      - name: Install deps\n        env:\n          X: ${{ secrets.FINMIND_TOKEN }}\n"),
    "加 set -x": lambda t: t.replace("run: pip install -r requirements.txt", "run: set -x"),
    "months 預設 99": lambda t: t.replace("default: '6'", "default: '99'"),
    "timeout 60": lambda t: t.replace("timeout-minutes: 10", "timeout-minutes: 60"),
}


@pytest.mark.parametrize("name", sorted(_WF_MUTS))
def test_workflow_mutation_goes_red(name):
    base = WF_PATH.read_text(encoding="utf-8")
    mutated = _WF_MUTS[name](base)
    assert mutated != base, "突變未生效"
    assert wf_violations(mutated), f"突變『{name}』未被守衛抓到"


# ───────────────────────── 腳本行為 ─────────────────────────
def _load(src: str | None = None):
    src = SCRIPT_PATH.read_text(encoding="utf-8") if src is None else src
    mod = types.ModuleType("probe_mut")
    mod.__file__ = str(SCRIPT_PATH)
    sys.path.insert(0, str(ROOT))
    exec(compile(src, str(SCRIPT_PATH), "exec"), mod.__dict__)
    return mod


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        if isinstance(self._p, Exception):
            raise self._p
        return self._p


def _fake(payload_by_stock, status=200, record=None):
    def _get(url, params=None, headers=None, timeout=None):
        if record is not None:
            record.append({"url": url, "params": dict(params or {}), "headers": dict(headers or {})})
        p = payload_by_stock(params["data_id"]) if callable(payload_by_stock) else payload_by_stock
        if isinstance(p, Exception):
            raise p
        return _Resp(p, status)
    return _get


def _ok(rows):
    return {"status": 200, "msg": "success", "data": rows}


def _row(d, y, m, rev=1000):
    return {"date": d, "stock_id": "2330", "country": "Taiwan", "revenue": rev,
            "revenue_month": m, "revenue_year": y}


def _run(mod, http_get, env=None, **kw):
    lines: list[str] = []
    e = {"FINMIND_TOKEN": FAKE_TOKEN, "PROBE_STOCK_IDS": "2330", "PROBE_MONTHS": "6"}
    e.update(env or {})
    rc = mod.run(env=e, http_get=http_get, out=lines.append, today=TODAY, **kw)
    return rc, "\n".join(lines)


def test_date_is_next_month_first():
    rows = [_row("2026-06-01", 2026, 5), _row("2026-07-01", 2026, 6), _row("2026-08-01", 2026, 7)]
    rc, out = _run(_load(), _fake(_ok(rows)))
    assert rc == 0 and "'date=次月1日': 3" in out and "缺月(觀察區間內)=[]" in out
    assert "NOT VERIFIED" in out and "不改 verified 旗標" in out


def test_date_is_revenue_month():
    rows = [_row("2026-05-01", 2026, 5), _row("2026-06-01", 2026, 6)]
    rc, out = _run(_load(), _fake(_ok(rows)))
    assert rc == 0 and "'同月(date年月=營收年月)': 2" in out


def test_other_relation_dup_missing_nonmonotonic():
    rows = [_row("2026-07-15", 2026, 5), _row("2026-06-01", 2026, 5), _row("2026-09-01", 2026, 8)]
    rc, out = _run(_load(), _fake(_ok(rows)))
    assert "'其他': 1" in out
    assert "重複(year,month)=[(2026, 5)]" in out
    assert "(2026, 6), (2026, 7)" in out          # 缺月
    assert "date 遞增=False" in out


def test_year_boundary_missing():
    rows = [_row("2025-12-01", 2025, 11), _row("2026-02-01", 2026, 1)]
    a = _load().analyze(rows)
    assert a["missing"] == [(2025, 12)] and a["rel"]["date=次月1日"] == 2


def test_missing_ym_columns():
    rows = [{"date": "2026-06-01", "revenue": 1}]
    rc, out = _run(_load(), _fake(_ok(rows)))
    assert "欄位缺失" in out and rc == 0


def test_empty_rows_ok():
    rc, out = _run(_load(), _fake(_ok([])))
    assert rc == 0 and "列數=0" in out


def test_http_error_and_api_status():
    rc, out = _run(_load(), _fake({"status": 402, "msg": "Requests reach limit"}, status=402))
    assert rc == 1 and "API status != 200" in out
    rc, out = _run(_load(), _fake({"status": 400, "msg": "bad"}))
    assert rc == 1


def test_no_token_exit_nonzero_no_network():
    calls: list = []
    rc, out = _run(_load(), _fake(_ok([]), record=calls), env={"FINMIND_TOKEN": ""})
    assert rc != 0 and calls == []
    assert "NOT VERIFIED：無 FINMIND_TOKEN，未取樣" in out
    rc, out = _run(_load(), _fake(_ok([]), record=calls), env={"FINMIND_TOKEN": "   "})
    assert rc != 0 and calls == []


def test_token_only_in_bearer_header_never_in_output():
    calls: list = []
    rows = [_row("2026-06-01", 2026, 5)]
    rc, out = _run(_load(), _fake(_ok(rows), record=calls))
    assert calls and calls[0]["headers"]["Authorization"] == f"Bearer {FAKE_TOKEN}"
    assert FAKE_TOKEN not in str(calls[0]["params"]) and FAKE_TOKEN not in calls[0]["url"]
    assert FAKE_TOKEN not in out and "Authorization" not in out


def test_token_echoed_by_api_msg_is_redacted():
    echo = {"status": 401, "msg": f"bad token {FAKE_TOKEN} Bearer {FAKE_TOKEN}"}
    rc, out = _run(_load(), _fake(echo))
    assert FAKE_TOKEN not in out and "***" in out


def test_exception_path_redacted():
    rc, out = _run(_load(), _fake(RuntimeError(f"conn failed Authorization: Bearer {FAKE_TOKEN} url?t={FAKE_TOKEN}")))
    assert rc == 1 and FAKE_TOKEN not in out and "RuntimeError" in out
    rc, out = _run(_load(), _fake(_Resp.__new__(_Resp) and ValueError(FAKE_TOKEN)))
    assert FAKE_TOKEN not in out


def test_input_truncation_and_validation():
    mod = _load()
    ids, months, notes = mod.parse_inputs("1,2,3,4,5,6,7,bad id!,../x", "99")
    assert len(ids) == 5 and months == 12 and notes
    ids, months, _ = mod.parse_inputs("", "abc")
    assert ids == ["2330", "2317", "2454"] and months == 6
    assert mod.parse_inputs("2330", "0")[1] == 1
    calls: list = []
    _run(_load(), _fake(_ok([]), record=calls), env={"PROBE_STOCK_IDS": "1,2,3,4,5,6,7,8", "PROBE_MONTHS": "500"})
    assert len(calls) == 5


def test_script_is_readonly_static():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert not re.search(r"open\(|\.write_text|\.to_csv|\.to_parquet|subprocess|os\.system|shutil|git ", code)
    assert "BATCH_SOURCE_MONTH_KEY_VERIFIED" in src and "monthly_revenue_month_key" not in src
    assert "os.environ" not in code.replace("env = os.environ if env is None else env", "")


# ───────────────────────── 腳本突變(拔掉防線必紅)─────────────────────────
def _mutate(old: str, new: str) -> str:
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert old in src, f"突變錨點不存在: {old}"
    return src.replace(old, new, 1)


def test_mutation_no_token_continues():
    mod = _load(_mutate("        return 2\n", "        pass\n"))
    calls: list = []
    try:
        rc, out = _run(mod, _fake(_ok([]), record=calls), env={"FINMIND_TOKEN": ""})
    except Exception:
        return
    assert calls or rc == 0   # 突變版:無 token 仍繼續 → 守衛(上方 test_no_token_*)會紅
    with pytest.raises(AssertionError):
        assert rc != 0 and calls == []


def test_mutation_redaction_removed_leaks():
    mod = _load(_mutate("        return _BEARER_RE.sub(\"Bearer ***\", s)", "        return s"))
    mod2 = _load(_mutate("            s = s.replace(sec, \"***\")", "            pass"))
    rc, out = _run(mod2, _fake({"status": 401, "msg": f"x {FAKE_TOKEN}"}))
    assert FAKE_TOKEN in out   # 突變版洩漏 → 真實版的 test_token_echoed_* 會紅
    assert mod is not None


def test_mutation_header_dumped():
    mod = _load(_mutate('    emit(f"== FinMind {DATASET}', '    emit(f"{os.environ}")\n    emit(f"== FinMind {DATASET}'))
    import os
    os.environ["FINMIND_TOKEN"] = FAKE_TOKEN
    try:
        lines: list[str] = []
        # 突變版直接印環境變數:遮蔽函式雖遮 token,但「輸出含環境變數」本身即違規 → 靜態守衛抓
        mod.run(env={"FINMIND_TOKEN": FAKE_TOKEN}, http_get=_fake(_ok([])), out=lines.append, today=TODAY)
    finally:
        del os.environ["FINMIND_TOKEN"]
    assert "PATH" in "\n".join(lines)   # 突變確實輸出了環境變數
    src = _mutate('    emit(f"== FinMind {DATASET}', '    emit(f"{os.environ}")\n    emit(f"== FinMind {DATASET}')
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "os.environ" in code.replace("env = os.environ if env is None else env", "")  # 守衛條件成立 → 真實版 static 測試會紅


def test_mutation_truncation_removed():
    mod = _load(_mutate("        ids = ids[:MAX_STOCKS]", "        pass"))
    ids, _, _ = mod.parse_inputs("1,2,3,4,5,6,7", "6")
    assert len(ids) > 5   # 突變版超量 → 真實版 test_input_truncation 會紅
