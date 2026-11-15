"""專業 Agent 定義結構守衛（DEC-178；pure Python，不新增依賴，手寫 frontmatter 解析）。

守什麼：`.claude/agents/` 底下只准有三個已登記的 Agent，且其 frontmatter 只用已知欄位、
權限不得擴張（不含 Write／Edit／NotebookEdit／Agent，QA 的 MCP 工具只准 GitHub 讀取類）、
內文含七個必備章節。Claude Code 對「無法辨識的 frontmatter 欄位」是靜默忽略（拼錯不會報錯），
所以這裡必須主動擋。

不守什麼（NOT VERIFIED）：Agent 是否真的被 Claude Code 載入（需新對話 `/agents`／`/doctor`
實測，列為 BACKLOG `DEC178-AGENT-LOAD-VERIFY`）；Bash 只讀（agent 層無法機械限制，只能靠內文指示）。

突變測試（TestMutationTeeth）：對「被竄改的定義」斷言驗證器必須回報錯誤，證明守衛有牙；
若有人把驗證器放寬，這些測試會轉紅。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".claude" / "agents"

#: 唯一准許存在的 Agent（第二批候選 Investment Logic／OneBrain／GitHub Auditor 未授權，不得悄悄加入）。
REGISTERED_AGENTS = (
    "stock-data-integrity",
    "stock-independent-qa",
    "stock-ui-ux",
)
QA_AGENT = "stock-independent-qa"

#: 嚴格白名單：本 repo 的 Agent frontmatter 只准這四個欄位（最小權限）。
#: 其餘官方欄位（hooks／mcpServers／omitClaudeMd／isolation／background／skills／memory／initialPrompt／
#: model／permissionMode／autoCompactWindow…）一律拒絕；拼錯的欄位名 Claude Code 會靜默忽略，同樣由此擋下。
ALLOWED_FIELDS = frozenset({"name", "description", "tools", "disallowedTools"})
UNREGISTERED_FIELD_MSG = "未登記欄位；新增須改守衛並經非作者 QA"
LIST_FIELDS = ("tools", "disallowedTools")

BASE_TOOLS = frozenset({"Read", "Grep", "Glob", "Bash"})
#: 這些絕不可出現在 tools，且必須出現在 disallowedTools（Agent 屬防遞迴派工／擴權）。
MUST_DENY = ("Write", "Edit", "NotebookEdit", "Agent")
NEVER_IN_TOOLS = frozenset(MUST_DENY) | {"Task", "WebFetch", "WebSearch"}

#: QA 唯一准許的 MCP 工具（GitHub 讀取類）。
QA_MCP_READ_WHITELIST = frozenset({
    "mcp__github__pull_request_read",
    "mcp__github__list_pull_requests",
    "mcp__github__get_commit",
    "mcp__github__list_commits",
    "mcp__github__get_file_contents",
    "mcp__github__actions_get",
    "mcp__github__actions_list",
    "mcp__github__get_job_logs",
    "mcp__github__get_check_run",
    "mcp__github__list_branches",
})
#: 寫入類（命中即以專用訊息拒絕；白名單之外本來就拒絕，這是為了讓錯誤訊息明確）。
MCP_WRITE_RE = re.compile(
    r"^mcp__.*(merge|update_|review_write|add_issue_comment|add_reply|add_comment|run_trigger|"
    r"create_|push_files|delete_|issue_write|sub_issue_write|enable_pr|disable_pr|fork_|"
    r"resolve_review|unresolve_review|request_copilot)"
)
FORBIDDEN_PERMISSION_MODES = frozenset({"bypassPermissions", "acceptEdits"})

REQUIRED_SECTIONS = ("Role", "Trigger", "Inputs", "Tools", "Forbidden", "Output", "Escalation")
DESCRIPTION_MAX = 300
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PROVISIONAL_ABC_RE = re.compile(r"PROVISIONAL[^\n]{0,6}\([abc]\)")
SECRET_RES = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
)


# --------------------------------------------------------------------------- 解析
def parse_agent(text: str):
    """回傳 (fields: dict, body: str, errors: list[str])。只支援本守衛需要的最小 YAML 子集。"""
    errors: list[str] = []
    if not text.startswith("---\n"):
        return {}, text, ["檔案必須以 `---` frontmatter 開頭"]
    end = text.find("\n---\n", 3)
    if end == -1:
        return {}, text, ["frontmatter 缺少結尾 `---`"]
    raw = text[4:end].split("\n")
    body = text[end + 5:]
    fields: dict = {}
    cur_list_key = None
    for ln in raw:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m_item = re.match(r"^\s+-\s+(.*\S)\s*$", ln)
        if m_item and cur_list_key is not None:
            fields[cur_list_key].append(m_item.group(1).strip("'\""))
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9_]*):(?:\s+(.*))?$", ln)
        if not m:
            errors.append(f"無法解析的 frontmatter 行：{ln!r}")
            cur_list_key = None
            continue
        key, val = m.group(1), m.group(2)
        if key in fields:
            errors.append(f"frontmatter 欄位重複：{key}")
        if val is None or not val.strip():
            fields[key] = []
            cur_list_key = key
        else:
            cur_list_key = None
            val = val.strip().strip("'\"")
            if key in LIST_FIELDS:
                if val.startswith("[") and val.endswith("]"):   # YAML flow list：tools: [Read, Grep]
                    val = val[1:-1]
                elif val.startswith("[") or val.endswith("]"):
                    errors.append(f"flow list 括號不成對：{key}")
                fields[key] = [v.strip().strip("'\"") for v in val.split(",") if v.strip()]
            else:
                fields[key] = val
    return fields, body, errors


# --------------------------------------------------------------------------- 驗證
def validate_agent(stem: str, text: str) -> list[str]:
    """回傳錯誤清單；空清單＝通過。stem 為檔名（不含 .md）。"""
    fields, body, errors = parse_agent(text)
    if errors and not fields:
        return errors

    unknown = sorted(set(fields) - ALLOWED_FIELDS)
    if unknown:
        errors.append(f"{UNREGISTERED_FIELD_MSG}：{unknown}（拼錯的欄位名會被 Claude Code 靜默忽略）")

    name = fields.get("name")
    if not name or isinstance(name, list):
        errors.append("缺少 name")
    else:
        if name != stem:
            errors.append(f"name 與檔名不一致：{name!r} vs {stem!r}")
        if not NAME_RE.match(name) or ":" in name or len(name) > 256:
            errors.append(f"name 格式不合法：{name!r}")

    desc = fields.get("description")
    if not desc or isinstance(desc, list):
        errors.append("缺少 description")
    elif len(desc) > DESCRIPTION_MAX:
        errors.append(f"description 過長（{len(desc)} > {DESCRIPTION_MAX}；常駐父層 context 的 Token 成本）")

    tools = fields.get("tools")
    if not tools:
        errors.append("缺少 tools（省略＝繼承全部工具含 MCP，不允許）")
        tools = []
    denied = fields.get("disallowedTools") or []
    for t in MUST_DENY:
        if t not in denied:
            errors.append(f"disallowedTools 必須包含 {t}")
    for t in tools:
        if t in NEVER_IN_TOOLS:
            errors.append(f"tools 不得包含 {t}（會使寫入／派工／網路能力可用）")
        elif t.startswith("mcp__"):
            if MCP_WRITE_RE.match(t):
                errors.append(f"tools 含寫入類 MCP 工具：{t}")
            elif stem != QA_AGENT:
                errors.append(f"只有 {QA_AGENT} 可列 MCP 工具：{t}")
            elif t not in QA_MCP_READ_WHITELIST:
                errors.append(f"MCP 工具不在讀取類白名單：{t}")
        elif t not in BASE_TOOLS:
            errors.append(f"tools 含未登記工具：{t}")

    pm = fields.get("permissionMode")
    if pm in FORBIDDEN_PERMISSION_MODES:   # 縱深：即使白名單被放寬，這兩個值仍必拒
        errors.append(f"permissionMode 不得為 {pm}")

    headings = set(re.findall(r"(?m)^## (\S+)", body))
    for sec in REQUIRED_SECTIONS:
        if sec not in headings:
            errors.append(f"缺少必備章節標題：## {sec}")

    if PROVISIONAL_ABC_RE.search(text):
        errors.append("含禁止字樣（PROVISIONAL (a)(b)(c)）")
    for rx in SECRET_RES:
        if rx.search(text):
            errors.append(f"疑似 secret 樣式：{rx.pattern}")

    errors.extend(_content_checks(stem, body))
    return errors


def _content_checks(stem: str, body: str) -> list[str]:
    errs: list[str] = []
    if "§-2" not in body:
        errs.append("內文須引用 CLAUDE.md §-2（每次任務都派工；按需不取代它）")
    if "不得擴權" not in body:
        errs.append("缺少『不得擴權』聲明")
    if "Bash" in body and "指示性約束" not in body:
        errs.append("使用 Bash 的 Agent 必須明載『Bash 唯讀為指示性約束』")
    if stem == "stock-data-integrity":
        for w in ("FACT", "INFERENCE", "NOT VERIFIED"):
            if w not in body:
                errs.append(f"資料 Agent 的 Output 須含 {w}")
    if stem == QA_AGENT:
        for w in ("PASS", "FAIL", "BLOCKED", "最新 head", "不是作者", "非作者", "不等於只派一組", "規則 4"):
            if w not in body:
                errs.append(f"QA Agent 內文須含 {w}")
        if "擅自 merge" not in body and "不得 merge" not in body:
            errs.append("QA Agent 內文須明載擅自 merge／不得 merge")
    return errs


def validate_directory(names: set[str]) -> list[str]:
    expected = {f"{a}.md" for a in REGISTERED_AGENTS}
    errs = []
    if names - expected:
        errs.append(f"目錄內有未登記檔案（第二批候選未授權）：{sorted(names - expected)}")
    if expected - names:
        errs.append(f"缺少已登記的 Agent 檔：{sorted(expected - names)}")
    return errs


def _read(stem: str) -> str:
    return (AGENTS_DIR / f"{stem}.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- 真實檔案
class TestRealAgentDefinitions:
    def test_directory_contains_exactly_the_registered_agents(self):
        names = {p.name for p in AGENTS_DIR.iterdir()}
        assert validate_directory(names) == []

    @pytest.mark.parametrize("stem", REGISTERED_AGENTS)
    def test_each_agent_passes_validator(self, stem):
        assert validate_agent(stem, _read(stem)) == []

    @pytest.mark.parametrize("stem", REGISTERED_AGENTS)
    def test_frontmatter_basics(self, stem):
        fields, body, errs = parse_agent(_read(stem))
        assert errs == []
        assert fields["name"] == stem
        assert 0 < len(fields["description"]) <= DESCRIPTION_MAX
        assert set(fields) <= ALLOWED_FIELDS

    def test_names_are_unique(self):
        names = [parse_agent(_read(s))[0]["name"] for s in REGISTERED_AGENTS]
        assert len(set(names)) == len(names) == 3

    def test_non_qa_agents_have_no_mcp_tools(self):
        for s in REGISTERED_AGENTS:
            tools = parse_agent(_read(s))[0]["tools"]
            mcp = [t for t in tools if t.startswith("mcp__")]
            assert (mcp != []) == (s == QA_AGENT), s

    def test_effective_tools_exclude_write_and_agent(self):
        for s in REGISTERED_AGENTS:
            f = parse_agent(_read(s))[0]
            eff = set(f["tools"]) - set(f["disallowedTools"])
            assert not (eff & set(MUST_DENY)), s

    def test_project_rules_section_34_registers_the_three_agents(self):
        pr = (ROOT / "PROJECT_RULES.md").read_text(encoding="utf-8")
        assert "## 第 34 節｜" in pr
        sec = pr[pr.index("## 第 34 節｜"):]
        for a in REGISTERED_AGENTS:
            assert a in sec, a
        assert "僅為候選" in sec


# --------------------------------------------------------------------------- 突變測試
class TestMutationTeeth:
    """竄改合格定義 → 驗證器必須回報錯誤。若有人放寬驗證器，這裡轉紅。"""

    def _must_fail(self, stem, mutate, needle):
        good = _read(stem)
        bad = mutate(good)
        assert bad != good, "突變未生效（測試本身壞了）"
        errs = validate_agent(stem, bad)
        assert errs, f"驗證器未攔下被竄改的定義：{needle}"
        assert any(needle in e for e in errs), (needle, errs)

    def test_baseline_is_clean(self):
        for s in REGISTERED_AGENTS:
            assert validate_agent(s, _read(s)) == []

    def test_adding_write_tool_is_rejected(self):
        self._must_fail("stock-data-integrity", lambda t: t.replace("  - Bash\n", "  - Bash\n  - Write\n", 1), "Write")

    def test_adding_agent_tool_is_rejected(self):
        self._must_fail("stock-ui-ux", lambda t: t.replace("  - Bash\n", "  - Bash\n  - Agent\n", 1), "Agent")

    def test_adding_merge_tool_to_qa_is_rejected(self):
        self._must_fail(QA_AGENT, lambda t: t.replace(
            "  - mcp__github__list_branches\n",
            "  - mcp__github__list_branches\n  - mcp__github__merge_pull_request\n", 1), "寫入類 MCP")

    def test_adding_unlisted_read_mcp_to_qa_is_rejected(self):
        self._must_fail(QA_AGENT, lambda t: t.replace(
            "  - mcp__github__list_branches\n",
            "  - mcp__github__list_branches\n  - mcp__github__get_me\n", 1), "白名單")

    def test_mcp_tool_on_non_qa_agent_is_rejected(self):
        self._must_fail("stock-data-integrity", lambda t: t.replace(
            "  - Bash\n", "  - Bash\n  - mcp__github__get_commit\n", 1), "只有")

    def test_typo_in_field_name_is_rejected(self):
        self._must_fail("stock-ui-ux", lambda t: t.replace("disallowedTools:", "disallowdTools:", 1), "未登記欄位")

    @pytest.mark.parametrize("line", [
        "hooks: x", "mcpServers: x", "omitClaudeMd: true", "isolation: worktree", "background: true",
        "skills: x", "memory: project", "initialPrompt: hi", "model: opus", "autoCompactWindow: 1",
    ])
    def test_unregistered_official_fields_are_rejected(self, line):
        self._must_fail("stock-data-integrity",
                        lambda t: t.replace("disallowedTools:", f"{line}\ndisallowedTools:", 1), "未登記欄位；新增須改守衛並經非作者 QA")

    def test_flow_list_is_supported_and_still_guarded(self):
        good = _read("stock-data-integrity")
        flow = good.replace("tools:\n  - Read\n  - Grep\n  - Glob\n  - Bash\n", "tools: [Read, Grep, Glob, Bash]\n", 1)
        assert flow != good
        assert validate_agent("stock-data-integrity", flow) == []
        bad = flow.replace("[Read, Grep, Glob, Bash]", "[Read, Grep, Glob, Bash, Write]", 1)
        assert any("Write" in e for e in validate_agent("stock-data-integrity", bad))
        unbalanced = flow.replace("Bash]", "Bash", 1)
        assert validate_agent("stock-data-integrity", unbalanced)

    @pytest.mark.parametrize("stem", REGISTERED_AGENTS)
    def test_removing_section_2_reference_is_rejected(self, stem):
        self._must_fail(stem, lambda t: t.replace("§-2", "§"), "§-2")

    def test_qa_missing_not_only_one_group_phrase_is_rejected(self):
        self._must_fail(QA_AGENT, lambda t: t.replace("不等於只派一組", "等於"), "不等於只派一組")

    def test_qa_missing_rule_4_is_rejected(self):
        self._must_fail(QA_AGENT, lambda t: t.replace("規則 4", "規則"), "規則 4")

    def test_qa_missing_no_merge_clause_is_rejected(self):
        self._must_fail(QA_AGENT, lambda t: t.replace("擅自 merge", "擅自 m"), "merge")

    def test_removing_name_is_rejected(self):
        self._must_fail("stock-ui-ux", lambda t: t.replace("name: stock-ui-ux\n", "", 1), "缺少 name")

    def test_name_mismatching_filename_is_rejected(self):
        self._must_fail("stock-ui-ux", lambda t: t.replace("name: stock-ui-ux", "name: stock-ui", 1), "不一致")

    def test_dropping_write_from_disallowed_is_rejected(self):
        self._must_fail("stock-independent-qa", lambda t: t.replace("  - Write\n", "", 1), "disallowedTools 必須包含 Write")

    def test_omitting_tools_means_inherit_all_and_is_rejected(self):
        def drop_tools(t):
            head, rest = t.split("disallowedTools:", 1)
            head = head[:head.index("tools:")]
            return head + "disallowedTools:" + rest
        self._must_fail("stock-ui-ux", drop_tools, "缺少 tools")

    @pytest.mark.parametrize("mode", ["bypassPermissions", "acceptEdits"])
    def test_dangerous_permission_mode_is_rejected(self, mode):
        self._must_fail("stock-data-integrity",
                        lambda t: t.replace("disallowedTools:", f"permissionMode: {mode}\ndisallowedTools:", 1),
                        "permissionMode")

    def test_missing_section_heading_is_rejected(self):
        self._must_fail("stock-independent-qa", lambda t: t.replace("## Escalation", "## Esc", 1), "## Escalation")

    def test_missing_frontmatter_is_rejected(self):
        errs = validate_agent("stock-ui-ux", _read("stock-ui-ux").split("---\n", 2)[2])
        assert any("frontmatter" in e for e in errs)

    def test_overlong_description_is_rejected(self):
        self._must_fail("stock-ui-ux", lambda t: t.replace("description: ", "description: " + "字" * 301 + " ", 1), "過長")

    def test_removing_bash_readonly_notice_is_rejected(self):
        self._must_fail("stock-data-integrity", lambda t: t.replace("指示性約束", "約束"), "指示性約束")

    def test_secret_like_text_is_rejected(self):
        self._must_fail("stock-ui-ux", lambda t: t + "\napi_key = abcdefghijklmnop1234\n", "secret")

    def test_extra_agent_file_is_rejected(self):
        names = {f"{a}.md" for a in REGISTERED_AGENTS} | {"investment-logic.md"}
        assert validate_directory(names)

    def test_missing_agent_file_is_rejected(self):
        names = {f"{a}.md" for a in REGISTERED_AGENTS[:2]}
        assert validate_directory(names)
