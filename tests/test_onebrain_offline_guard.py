"""OneBrain OB-1（完全離線）守衛與行為測試（fast lane；DEC-195，Issue #1199 GPT §C）。

═══ 守什麼 ═══════════════════════════════════════════════════════════
1. **零 production import**：`shared.onebrain_provider`／`src.services.onebrain_shadow` 只准彼此與 tests/ 引用
   （含 app.py、app_ui2.py、src/ui*、src/ui2、src/services/ui2、scripts）。
2. **零網路／SDK**：兩個新模組不得 import LLM SDK、網路客戶端、專案 AI 模組，也不得含 LLM 端點字串
   （重用 `tests/test_ui2_no_second_ai_guard.py` 的禁用清單與掃描器，不另養一份）。
3. **凍結面不動**：`SCHEMA_VERSION == "decision_digest.v1"`、`DecisionDigest` 欄位集合不變；
   `ShadowOutcome` 沒有 action／Risk Cap／決策類欄位（反射）。
4. **行為**：9 種失敗／壞輸出模式 × 2 份 Digest，`effective` 一律等於 `build_rule_summary(digest)`、
   `shadow_accepted` 為 False、`error_kind` 非 None；偽造草稿（把缺值升格、丟掉 stale／缺值／Risk Cap 揭露、
   塞 safe 字樣）被 `check_summary` 拒收；Provider 全程沒有網路（socket 被封鎖仍能跑）。

⛔ 本檔不改任何 production 檔；不新增門檻。AST 守衛是 defense-in-depth，非窮舉。
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import socket

import pytest

from shared.decision_digest import SCHEMA_VERSION, AiParticipation, DecisionDigest
from shared.decision_digest_grounding import (
    Lit, SummaryDraft, SummarySection, SummarySentence, check_summary,
)
from shared.onebrain_provider import ProviderError, ProviderErrorKind, ProviderRequest, SummaryProvider
from src.services import onebrain_shadow
from src.services.decision_digest_summary import _expand_shape, build_rule_summary, compose_rule_draft
from src.services.onebrain_shadow import ShadowOutcome, run_shadow
from tests.decision_digest_factory import empty_digest, make_digest, missing, ok_text, stale_text
from tests.onebrain_fake_provider import ALL_MODES, ERROR_MODES, MODE_BOOM, MODE_PAYLOAD, FakeProvider
from tests.test_ui2_no_second_ai_guard import scan_no_second_ai

ROOT = pathlib.Path(__file__).resolve().parents[1]
NEW_MODULES = ("shared.onebrain_provider", "src.services.onebrain_shadow")
NEW_FILES = (ROOT / "shared" / "onebrain_provider.py", ROOT / "src" / "services" / "onebrain_shadow.py")
_ALLOWED_IMPORTERS = {"src/services/onebrain_shadow.py"}          # 唯一的 production importer（L3 影子層）


# ════════════════════════════════════════════════════════════════════
# 1. 零 production import
# ════════════════════════════════════════════════════════════════════
def _production_files() -> list[pathlib.Path]:
    out: list[pathlib.Path] = [ROOT / "app.py", ROOT / "app_ui2.py"]
    for top in ("shared", "src", "scripts"):
        out += [p for p in (ROOT / top).rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(p for p in out if p.exists())


def _imports_onebrain(source: str) -> list[str]:
    """回傳引用到新模組的 import（含 `from shared import onebrain_provider`、`import_module("…")` 字串）。"""
    hit: list[str] = []
    for n in ast.walk(ast.parse(source)):
        mods: list[str] = []
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            mods = [base] + [f"{base}.{a.name}" for a in n.names]
        elif isinstance(n, ast.Call):
            mods = [a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        for m in mods:
            if any(m == b or m.startswith(b + ".") for b in NEW_MODULES) or m.rsplit(".", 1)[-1] in {
                    "onebrain_provider", "onebrain_shadow"}:
                hit.append(f"L{n.lineno}: {m}")
    return hit


def test_scan_scope_covers_the_places_that_must_not_import():
    rel = {p.relative_to(ROOT).as_posix() for p in _production_files()}
    for must in ("app.py", "app_ui2.py", "src/ui2/__init__.py", "src/services/ui2/__init__.py"):
        assert must in rel, must
    assert any(r.startswith("src/ui/") for r in rel) and any(r.startswith("src/ui2/") for r in rel)
    assert any(r.startswith("src/services/ui2/") for r in rel) and any(r.startswith("shared/ui2_contract/") for r in rel)


def test_no_production_module_imports_onebrain_except_the_shadow_layer():
    offenders = {}
    for p in _production_files():
        rel = p.relative_to(ROOT).as_posix()
        if rel in _ALLOWED_IMPORTERS or rel in {"shared/onebrain_provider.py"}:
            continue
        hits = _imports_onebrain(p.read_text(encoding="utf-8"))
        if hits:
            offenders[rel] = hits
    assert offenders == {}


def test_import_scanner_has_teeth():
    for src in ("import shared.onebrain_provider", "from shared import onebrain_provider",
                "from shared.onebrain_provider import SummaryProvider", "import src.services.onebrain_shadow as x",
                "from src.services import onebrain_shadow", "importlib.import_module('src.services.onebrain_shadow')"):
        assert _imports_onebrain(src), src
    assert _imports_onebrain("import json\nfrom shared import decision_digest") == []


def test_shadow_layer_is_the_only_production_importer_and_imports_only_the_contract():
    src = (ROOT / "src/services/onebrain_shadow.py").read_text(encoding="utf-8")
    assert _imports_onebrain(src)                                     # 確實引用契約（白名單不是空殼）


# ════════════════════════════════════════════════════════════════════
# 2. 零網路／SDK／第二個 AI
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", NEW_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_new_modules_have_no_sdk_network_or_project_ai_import(path):
    assert scan_no_second_ai(path.read_text(encoding="utf-8")) == []


def test_new_modules_import_only_stdlib_and_layered_project_modules():
    allowed_roots = {"__future__", "dataclasses", "enum", "typing", "logging", "shared", "src"}
    for path in NEW_FILES:
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else (
                [n.module or ""] if isinstance(n, ast.ImportFrom) else [])
            for m in mods:
                assert m.split(".")[0] in allowed_roots, (path.name, m)
    # L0 不得依賴 L1+：provider 契約只准 import shared.*
    l0 = ast.parse(NEW_FILES[0].read_text(encoding="utf-8"))
    for n in ast.walk(l0):
        if isinstance(n, ast.ImportFrom) and n.module:
            assert n.module.split(".")[0] in {"__future__", "dataclasses", "enum", "typing", "shared"}, n.module


# ════════════════════════════════════════════════════════════════════
# 3. 凍結面不動
# ════════════════════════════════════════════════════════════════════
def test_digest_schema_version_and_field_set_unchanged():
    assert SCHEMA_VERSION == "decision_digest.v1"
    assert {f.name for f in dataclasses.fields(DecisionDigest)} == {
        "generated_at", "market", "tw_trend", "intl_trend", "valuation", "industry", "holdings", "risk_cap",
        "actions", "ai_participation", "ai_passed_checks", "ai_failed_checks", "schema_version"}


def test_shadow_outcome_has_no_action_or_risk_cap_fields():
    names = {f.name for f in dataclasses.fields(ShadowOutcome)}
    assert names == {"effective", "error_kind", "grounding", "shadow_accepted"}
    for n in names:
        assert not any(w in n.lower() for w in ("action", "risk", "cap", "safe", "decision", "regime"))
    assert dataclasses.is_dataclass(ShadowOutcome) and ShadowOutcome.__dataclass_params__.frozen


def test_provider_request_is_frozen_and_carries_only_the_digest():
    assert {f.name for f in dataclasses.fields(ProviderRequest)} == {"digest", "task"}
    r = ProviderRequest(make_digest())
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.task = "x"


def test_provider_error_requires_a_known_kind():
    with pytest.raises(TypeError):
        ProviderError("timeout")                                      # type: ignore[arg-type]
    assert {k.value for k in ProviderErrorKind} == {"timeout", "rate_limit", "unavailable", "invalid_response"}


# ════════════════════════════════════════════════════════════════════
# 4. 行為：失敗／壞輸出一律回到規則式摘要
# ════════════════════════════════════════════════════════════════════
def _safe_literal_draft():
    return SummaryDraft((SummarySection("market", (SummarySentence((Lit("safe"),)),)),))


BAD_CASES = [
    *[pytest.param(m, None, id=m) for m in ERROR_MODES],                       # 4 種 ProviderError
    pytest.param(MODE_BOOM, None, id="boom"),                                   # 非 ProviderError 例外
    pytest.param(MODE_PAYLOAD, None, id="payload-None"),
    pytest.param(MODE_PAYLOAD, "free text: 市場安全，維持中性", id="payload-free-text"),
    pytest.param(MODE_PAYLOAD, SummaryDraft(), id="payload-empty-draft"),
    pytest.param(MODE_PAYLOAD, _safe_literal_draft(), id="payload-safe-literal"),
]


def test_bad_case_matrix_covers_nine_modes():
    assert len(BAD_CASES) == 9


@pytest.mark.parametrize("mk", [make_digest, empty_digest], ids=["normal", "empty"])
@pytest.mark.parametrize("mode,payload", BAD_CASES)
def test_failure_and_bad_output_fall_back_to_rule_summary(mode, payload, mk):
    d = mk()
    p = FakeProvider(mode, payload)
    assert isinstance(p, SummaryProvider)
    o = run_shadow(d, p)
    assert p.calls == 1
    assert o.effective == build_rule_summary(d)
    assert o.shadow_accepted is False
    assert isinstance(o.error_kind, ProviderErrorKind)
    if mode in ERROR_MODES:
        assert o.error_kind.value == mode and o.grounding is None
    elif mode == MODE_BOOM:
        assert o.error_kind is ProviderErrorKind.INVALID_RESPONSE and o.grounding is None


@pytest.mark.parametrize("mk", [make_digest, empty_digest], ids=["normal", "empty"])
def test_echo_is_accepted_but_effective_is_still_the_rule_summary(mk):
    d = mk()
    o = run_shadow(d, FakeProvider())
    assert o.shadow_accepted is True and o.error_kind is None and o.grounding.clean
    assert o.effective == build_rule_summary(d)
    assert o.effective.sections == compose_rule_draft(d).sections


def test_effective_never_changes_with_the_provider():
    d = make_digest()
    outs = [run_shadow(d, FakeProvider(m, pl)).effective for m, pl in
            [("echo", None), ("timeout", None), ("boom", None), ("payload", "x")]]
    assert all(e == outs[0] for e in outs)


def test_provider_failure_is_logged_not_swallowed(caplog):
    with caplog.at_level("WARNING", logger=onebrain_shadow.__name__):
        run_shadow(make_digest(), FakeProvider("boom"))
        run_shadow(make_digest(), FakeProvider("timeout"))
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "RuntimeError" in msgs and "timeout" in msgs


def test_rule_layer_error_is_not_swallowed_by_the_shadow_layer():
    d = make_digest(ai_participation=AiParticipation.AI_EXPLAINED, ai_passed_checks=("G1",))
    with pytest.raises(ValueError):
        build_rule_summary(d)
    p = FakeProvider()
    with pytest.raises(ValueError):
        run_shadow(d, p)
    assert p.calls == 0                                                # 規則層先炸，不會去叫 Provider


# ── 偽造／未接地草稿必被 check_summary 拒收 ───────────────────────────
def _forgery_digest():
    return make_digest(market_facts=[ok_text("market.regime", "bull"), stale_text("market.light", "🟢"),
                                     missing("market.health")])


def _replace_market(base: SummaryDraft, mutate) -> SummaryDraft:
    sec = base.sections[0]
    sents = list(sec.sentences)
    mutate(sents)
    return SummaryDraft((dataclasses.replace(sec, sentences=tuple(sents)),) + base.sections[1:])


def _forgeries(d):
    base = compose_rule_draft(d)
    sents = base.sections[0].sentences

    def idx(fid):                                                     # market 段內該事實的句序
        return next(i for i, s in enumerate(sents) if any(getattr(g, "ref_id", None) == fid for g in s.segments))

    def raise_missing(s):                                              # 缺值 → 偽裝成有值
        s[idx("market.health")] = _expand_shape("fact_value_ok", "market.health")

    def stale_as_fresh(s):                                             # stale → 偽裝成新鮮
        s[idx("market.light")] = _expand_shape("fact_text_ok", "market.light")

    def drop_stale(s):
        del s[idx("market.light")]

    def drop_missing(s):
        del s[idx("market.health")]

    def drop_risk_cap(s):                                              # 丟掉 Risk Cap 揭露句
        del s[next(i for i, x in enumerate(s) if any(str(getattr(g, "ref_id", "")).endswith("risk_cap") for g in x.segments))]

    return {
        "missing-raised-to-ok": _replace_market(base, raise_missing),
        "stale-presented-as-fresh": _replace_market(base, stale_as_fresh),
        "stale-sentence-dropped": _replace_market(base, drop_stale),
        "missing-sentence-dropped": _replace_market(base, drop_missing),
        "risk-cap-disclosure-dropped": _replace_market(base, drop_risk_cap),
        "market-section-dropped": SummaryDraft(base.sections[1:]),
        "actions-section-dropped": SummaryDraft(base.sections[:-1]),
        "safe-literal": _safe_literal_draft(),
        "free-text": "市場安全、風險中性、可全數加碼",
    }


def test_forged_drafts_are_rejected_by_grounding_and_never_accepted_by_shadow():
    d = _forgery_digest()
    assert check_summary(d, compose_rule_draft(d)).clean                 # 對照組：誠實草稿乾淨
    forged = _forgeries(d)
    assert len(forged) == 9
    for name, draft in forged.items():
        rep = check_summary(d, draft)
        assert rep.clean is False, name
        o = run_shadow(d, FakeProvider(MODE_PAYLOAD, draft))
        assert o.shadow_accepted is False and o.error_kind is ProviderErrorKind.INVALID_RESPONSE, name
        assert o.effective == build_rule_summary(d), name


# ── 無網路 ───────────────────────────────────────────────────────────
def test_shadow_runs_with_network_blocked(monkeypatch):
    def _no_net(*a, **k):
        raise AssertionError("OB-1 離線：不得開 socket")
    monkeypatch.setattr(socket, "socket", _no_net)
    monkeypatch.setattr(socket, "create_connection", _no_net)
    monkeypatch.setattr(socket, "getaddrinfo", _no_net)
    for mode in ALL_MODES:
        o = run_shadow(make_digest(), FakeProvider(mode, None if mode != MODE_PAYLOAD else "x"))
        assert o.effective == build_rule_summary(make_digest())


def test_fake_provider_rejects_unknown_mode():
    with pytest.raises(ValueError):
        FakeProvider("nope")


# ── N2：畸形 ProviderError 子類也要被分類 ───────────────────────────────
class _NoInitError(ProviderError):
    def __init__(self):                                   # 刻意不呼叫 super().__init__
        pass


class _StrKindError(ProviderError):
    def __init__(self):
        super().__init__(ProviderErrorKind.TIMEOUT)
        self.kind = "timeout"                              # type: ignore[assignment]


@pytest.mark.parametrize("exc", [_NoInitError, _StrKindError])
def test_malformed_provider_error_is_classified_not_attribute_error(exc):
    class P:
        def propose_summary(self, request):
            raise exc()
    d = make_digest()
    o = run_shadow(d, P())
    assert o.error_kind is ProviderErrorKind.INVALID_RESPONSE and o.shadow_accepted is False
    assert o.effective == build_rule_summary(d)


# ── NOTE-1（#1216）：讀取 kind 本身不得讓例外逃出 handler ───────────────
class _PropRaisesRuntime(ProviderError):
    def __init__(self):
        pass

    @property
    def kind(self):                                        # type: ignore[override]
        raise RuntimeError("evil kind property")


class _PropRaisesValue(ProviderError):
    def __init__(self):
        pass

    @property
    def kind(self):                                        # type: ignore[override]
        raise ValueError("evil kind property")


class _GetattrRaises(ProviderError):
    def __init__(self):
        pass

    def __getattr__(self, name):
        raise RuntimeError("evil __getattr__")


@pytest.mark.parametrize("exc", [_PropRaisesRuntime, _PropRaisesValue, _GetattrRaises])
def test_kind_read_failure_is_contained_and_classified(exc):
    class P:
        def propose_summary(self, request):
            raise exc()
    d = make_digest()
    o = run_shadow(d, P())
    assert o.error_kind is ProviderErrorKind.INVALID_RESPONSE
    assert o.shadow_accepted is False and o.grounding is None
    assert o.effective == build_rule_summary(d)


@pytest.mark.parametrize("bad", [KeyboardInterrupt, SystemExit])
def test_kind_read_failure_does_not_swallow_baseexception(bad):
    class E(ProviderError):
        def __init__(self):
            pass

        @property
        def kind(self):                                    # type: ignore[override]
            raise bad()
    class P:
        def propose_summary(self, request):
            raise E()
    with pytest.raises(bad):
        run_shadow(make_digest(), P())


def test_rule_layer_error_still_propagates_with_kind_guard(monkeypatch):
    def boom(_d):
        raise ValueError("rule layer bug")
    monkeypatch.setattr(onebrain_shadow, "build_rule_summary", boom)
    class P:
        def propose_summary(self, request):
            raise AssertionError("must not reach provider")
    with pytest.raises(ValueError):
        run_shadow(make_digest(), P())


# ── N4：兩個新檔的 import 明確白名單（逐檔） ───────────────────────────
_IMPORT_ALLOWLIST = {
    "shared/onebrain_provider.py": {"__future__", "dataclasses", "enum", "typing", "shared.decision_digest",
                                    "shared.decision_digest_grounding"},
    "src/services/onebrain_shadow.py": {"__future__", "logging", "dataclasses", "typing", "shared.decision_digest",
                                        "shared.decision_digest_grounding", "shared.onebrain_provider",
                                        "src.services.decision_digest_summary"},
}


def _import_modules(source: str) -> set:
    out = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(n.module or "")
    return out


def test_new_files_import_exactly_within_the_explicit_allowlist():
    for rel, allowed in _IMPORT_ALLOWLIST.items():
        assert _import_modules((ROOT / rel).read_text(encoding="utf-8")) <= allowed, rel


@pytest.mark.parametrize("extra", ["src.services.decision_digest_assembly", "src.services.decision_digest_builder",
                                   "shared.decision_digest_validator", "shared.decision_digest_coverage",
                                   "shared.decision_digest_rules", "shared.decision_digest_terms", "json"])
@pytest.mark.parametrize("rel", sorted(_IMPORT_ALLOWLIST))
def test_allowlist_check_turns_red_when_an_extra_import_is_added(rel, extra):
    src = (ROOT / rel).read_text(encoding="utf-8") + f"\nimport {extra}\n"
    assert not (_import_modules(src) <= _IMPORT_ALLOWLIST[rel])
