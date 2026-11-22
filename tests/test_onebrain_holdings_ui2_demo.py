"""OFFLINE-WIRING-SCRATCH-1（原型，可拋棄）— `tests/onebrain_holdings_ui2_demo.py` 的 parity／分區禁字／fail-closed／突變測試。

基準：main（#1258＋#1261 已合併）；移植自 scratch/onebrain-holdings-ui2-demo-20261122@61619ad6；
設計＝#1199 v2 ＋ 總管 D1–D9（comment 7075101372）、D8（comment 7076099172）。QA 狀態不寫進程式檔（由 PR／#1199 記錄）。
⛔ tests-only；不改 src／shared／app*／scripts／守衛；全離線（socket 封鎖）、無時鐘。

Oracle 獨立性：Digest 原句由本檔**自行**跑 `adapt_holdings_read → assemble → build_rule_summary` 取得，
顯示段、預期原因碼、預期可用性、D9 規則、註記觸發條件均為本檔**本地常數**（不讀 demo 的同名常數），
故改 demo 的 SHOWN_SECTIONS／derive／觸發字等會被抓到。合成輸入（`demo.CASES`／`demo.assemble`）共用。
"""
from __future__ import annotations

import ast
import pathlib
import socket

import pytest

import src.services.decision_digest_assembly as ASM
import src.services.decision_digest_summary as S
import src.services.onebrain_holdings_adapter as A
import src.services.onebrain_shadow as SH
import tests.onebrain_holdings_ui2_demo as demo
from shared.decision_digest import Availability
from shared.ui2_contract.text import (
    JUDGEMENT_STATUS_PREFIXES,
    TEXT_NOT_EVALUATED_DATA_SHORT,
    TEXT_RISK_CAP_UNDETERMINABLE,
)
from tests.onebrain_fake_provider import ALL_MODES
from tests.test_onebrain_holdings_shadow_chain_offline import NEUTRAL_SAFE_CLAIMS, ZERO_HOLDING_CLAIMS

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_FILE = ROOT / "tests" / "onebrain_holdings_ui2_demo.py"

# ── 本地 oracle 常數（刻意不讀 demo 同名常數）──────────────────────────
EXPECTED_CASE_IDS = ("R1", "R2", "R3", "L1", "L2", "L3")
ORACLE_SECTIONS = ("buy_and_hold", "capital_gain")
EXPECTED_REASONS = {
    "R1": (A.REASON_READ_EXCEPTION_NETWORK,),
    "R2": (A.REASON_NOT_SELECTED,),
    "R3": (A.REASON_EX_DROPPED_NON_NUMERIC,),
    "L1": (A.REASON_UNIVERSE_NOT_INDEPENDENT,),
    "L2": (A.REASON_UNIVERSE_NOT_INDEPENDENT,),
    "L3": (A.REASON_UNIVERSE_NOT_INDEPENDENT,),
}
EXPECTED_AVAILABILITY = {"R1": Availability.UNAVAILABLE, "R2": Availability.UNAVAILABLE,
                         "R3": Availability.UNAVAILABLE, "L1": Availability.UNAVAILABLE,
                         "L2": Availability.PARTIAL, "L3": Availability.AVAILABLE}
DISCLOSURE_FIRST = "示意：合成持股快照（FAKE）；非真實持股；非即時 OneBrain；非投資建議"
DISCLOSURE_SECOND = "與本頁其他 FAKE 數字無關"
UNDETERMINABLE = "⬜ 無法判定"
DERIVED_ROW = "持股判讀 ⬜ 無法判定（UI 依持股可用性推導；非 Digest 原句）"
NOTE_TRIGGER = "（尚無輸入）"
APPROVED_NOTE = "註：『尚無輸入』是現行摘要措辭，也可能代表讀取失敗、輸入異常或缺少組合鍵；請勿解讀為零持股。"
EXPECTED_FOOTER = ("顯示＝規則式摘要；FakeProvider 草稿不採用", "來源：FAKE 合成持股快照",
                   "時點：FAKE 示意（無持股讀取時點，§C-10）")
TEST_INPUT_PREFIX = "測試輸入說明（非系統輸出；系統不傳遞此資訊，§C-2）："
UI_NOTE_WHITELIST = (APPROVED_NOTE, "示範鏈未通過檢查，未顯示任何系統句")
AREA_ORDER = ("disclosure", "derived", "system_output", "ui_note", "footer", "test_input")
BLOCK_BANNED = ("bull", "🟢", "72.5", "市場位階", "txt-", "本期行動", "is_complete", "shadow_accepted",
                "Risk Cap", "風險上限", "grounding", "市場燈號", "市場健康度", "產業")
SYSTEM_DERIVED_BANNED = (*ZERO_HOLDING_CLAIMS, *NEUTRAL_SAFE_CLAIMS, "完整", *A.ALL_REASONS)


def _expected_derived(av):
    """D9（本地規則）：UNAVAILABLE／PARTIAL → 列；AVAILABLE → 無列。"""
    return () if av is Availability.AVAILABLE else (DERIVED_ROW,)


@pytest.fixture(autouse=True)
def _socket_blocked(monkeypatch):
    def _no_net(*_a, **_k):
        raise AssertionError("示範不得連網")
    monkeypatch.setattr(socket.socket, "connect", _no_net)
    monkeypatch.setattr(socket.socket, "connect_ex", _no_net)
    monkeypatch.setattr(socket, "create_connection", _no_net)
    monkeypatch.setattr(socket, "getaddrinfo", _no_net)


# ══════════════════════════════════════════════════════════════════════
# 獨立 oracle
# ══════════════════════════════════════════════════════════════════════
def _oracle(cid):
    case = demo.CASES[cid]
    res = A.adapt_holdings_read(case.snapshot)
    a = demo.assemble(case, res.rows_for_digest())
    summary = S.build_rule_summary(a.digest)
    secs = dict(summary.lines)
    sents = tuple((k, x) for k in ORACLE_SECTIONS for x in secs[k])
    return res, a, summary, sents


# ══════════════════════════════════════════════════════════════════════
# 檢查（突變測試重用；失敗一律 AssertionError）
# ══════════════════════════════════════════════════════════════════════
def _build(cid):
    """build_case_block 不得往上拋（fail-closed 契約）；拋出 ⇒ AssertionError。"""
    try:
        return demo.build_case_block(cid)
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"{cid} build_case_block 不得往上拋：{type(e).__name__}") from e


def _check_case(cid):
    res, a, _summary, sents = _oracle(cid)
    assert res.reasons == EXPECTED_REASONS[cid], f"{cid} adapter 原因碼"
    assert (res.holdings_rows is None) is cid.startswith("R"), f"{cid} adapter 路徑"
    av = a.digest.holdings.availability
    assert av is EXPECTED_AVAILABILITY[cid], f"{cid} availability"
    b = _build(cid)
    assert b.fail_closed is False, f"{cid} 不應 fail-closed（{b.error_type}）"
    # 示意聲明在最前
    assert b.lines[0].area == "disclosure" and b.lines[0].text == DISCLOSURE_FIRST, f"{cid} 首行須為示意聲明"
    assert b.lines[1].area == "disclosure" and b.lines[1].text == DISCLOSURE_SECOND, f"{cid} 第二行"
    assert b.area("disclosure") == (DISCLOSURE_FIRST, DISCLOSURE_SECOND)
    assert demo.render_text(b).splitlines()[0].endswith(DISCLOSURE_FIRST), f"{cid} 呈現首行"
    # 區域順序
    idx = [AREA_ORDER.index(ln.area) for ln in b.lines]
    assert idx == sorted(idx), f"{cid} 區域順序"
    # 逐字 parity（含段鍵與順序）
    shown = tuple((ln.section, ln.text) for ln in b.lines if ln.area == "system_output")
    assert shown == sents, f"{cid} 系統輸出區須與 Digest 存股／資本利得逐字相同"
    # D9 衍生列
    assert b.area("derived") == _expected_derived(av), f"{cid} D9 衍生列"
    # 註記 iff 觸發
    has_trigger = any(NOTE_TRIGGER in x for _k, x in sents)
    assert (APPROVED_NOTE in b.area("ui_note")) is has_trigger, f"{cid} 註記須與（尚無輸入）同進退"
    assert set(b.area("ui_note")) <= set(UI_NOTE_WHITELIST), f"{cid} ui_note 只准白名單"
    assert not any("註" in x for x in b.area("system_output")), f"{cid} 註記不得混入系統輸出區"
    # 頁尾、測試輸入
    assert b.area("footer") == EXPECTED_FOOTER, f"{cid} 頁尾"
    ti = b.area("test_input")
    assert len(ti) == 1 and ti[0].startswith(TEST_INPUT_PREFIX) and b.lines[-1].area == "test_input", f"{cid} 測試輸入區"
    _check_banned(b, cid)


def _check_banned(b, cid):
    for area in ("system_output", "derived", "test_input"):
        for x in b.area(area):
            hit = [w for w in SYSTEM_DERIVED_BANNED if w in x]
            assert not hit, f"{cid}/{area} 禁字 {hit}：{x}"
    whole = "\n".join([ln.text for ln in b.lines] + [demo.render_text(b)])
    hit = [w for w in BLOCK_BANNED if w in whole]
    assert not hit, f"{cid} 全區塊禁字 {hit}"
    assert TEXT_NOT_EVALUATED_DATA_SHORT not in whole and "未評估" not in whole, f"{cid} 不得重用『未評估／資料不足』"


_INJECTED_MSG = "injected-secret-value-7f3a"  # 注入例外的訊息值；fail-closed log 只可記型別名，不得含此值


def _check_failclosed():
    with pytest.MonkeyPatch.context() as mp:
        def boom(*_a, **_k):
            raise RuntimeError(_INJECTED_MSG)
        mp.setattr(ASM, "assemble_digest", boom)
        for cid in EXPECTED_CASE_IDS:
            b = _build(cid)
            assert b.fail_closed is True and b.error_type == "RuntimeError", f"{cid} 須 fail-closed"
            assert b.area("system_output") == (), f"{cid} fail-closed 不得有系統句"
            assert b.area("disclosure") == (DISCLOSURE_FIRST, DISCLOSURE_SECOND) and b.lines[0].text == DISCLOSURE_FIRST
            assert b.area("derived") == (DERIVED_ROW,), f"{cid} fail-closed 須顯示無法判定"
            assert b.area("ui_note") == (UI_NOTE_WHITELIST[1],), f"{cid} fail-closed 說明"
            assert b.area("footer") == EXPECTED_FOOTER and b.area("test_input") == ()
            _check_banned(b, cid)


def _check_all():
    assert demo.CASE_IDS == EXPECTED_CASE_IDS
    for cid in EXPECTED_CASE_IDS:
        _check_case(cid)
    _check_failclosed()


# ══════════════════════════════════════════════════════════════════════
# 正向測試
# ══════════════════════════════════════════════════════════════════════
def test_cases_are_exactly_d6_and_exclude_zero_rows_and_status_empty():
    assert demo.CASE_IDS == EXPECTED_CASE_IDS
    for cid in EXPECTED_CASE_IDS:
        reasons = A.adapt_holdings_read(demo.CASES[cid].snapshot).reasons
        assert A.REASON_ZERO_ROWS not in reasons and A.REASON_READ_STATUS_EMPTY not in reasons
        assert demo.CASES[cid].snapshot.outcome != A.OUTCOME_STATUS_EMPTY


@pytest.mark.parametrize("cid", EXPECTED_CASE_IDS)
def test_case_block_parity_derived_note_banned(cid):
    _check_case(cid)


def test_expected_note_and_derived_presence_table():
    note = {cid: APPROVED_NOTE in demo.build_case_block(cid).area("ui_note") for cid in EXPECTED_CASE_IDS}
    assert note == {"R1": True, "R2": True, "R3": True, "L1": True, "L2": False, "L3": False}
    derived = {cid: demo.build_case_block(cid).area("derived") for cid in EXPECTED_CASE_IDS}
    assert derived["L2"] == (DERIVED_ROW,) and derived["L3"] == ()     # PARTIAL→無法判定；AVAILABLE→無列


def test_none_cases_are_word_for_word_identical_g3():
    """G3 照實呈現：三種 None 原因的系統輸出區逐字相同（原因不傳遞）。"""
    outs = {cid: demo.build_case_block(cid).area("system_output") for cid in ("R1", "R2", "R3")}
    assert outs["R1"] == outs["R2"] == outs["R3"]


def test_derive_rule_unit_and_allowlist():
    assert demo.derive_holdings_judgement(Availability.UNAVAILABLE) == UNDETERMINABLE
    assert demo.derive_holdings_judgement(Availability.PARTIAL) == UNDETERMINABLE
    assert demo.derive_holdings_judgement(Availability.AVAILABLE) is None
    for other in [m for m in Availability if m not in (Availability.UNAVAILABLE, Availability.PARTIAL,
                                                       Availability.AVAILABLE)] + ["partial", None, 1]:
        with pytest.raises(demo.DemoChainError):
            demo.derive_holdings_judgement(other)
    assert UNDETERMINABLE == TEXT_RISK_CAP_UNDETERMINABLE
    assert UNDETERMINABLE in JUDGEMENT_STATUS_PREFIXES["undeterminable"]
    assert UNDETERMINABLE != TEXT_NOT_EVALUATED_DATA_SHORT


@pytest.mark.parametrize("cid", EXPECTED_CASE_IDS)
def test_effective_equals_rule_summary_for_every_provider_mode(cid):
    _res, a, summary, _s = _oracle(cid)
    provs = demo.providers(a.digest)
    assert set(ALL_MODES) <= set(provs)
    for mode, p in provs.items():
        o = SH.run_shadow(a.digest, p)
        assert p.calls == 1, mode
        assert o.effective == summary == S.build_rule_summary(a.digest), mode
    # 示範區塊不受 provider 結果影響（已內建於 build_case_block；此處再確認決定性）
    assert demo.build_case_block(cid) == demo.build_case_block(cid)


def test_failclosed_on_assemble_exception(caplog):
    with caplog.at_level("WARNING"):
        _check_failclosed()
    assert "fail-closed" in caplog.text
    msgs = [r.getMessage() for r in caplog.records if r.name == demo.__name__]
    # demo 以 `_log.warning("... %s fail-closed: %s", case_id, type(err).__name__)` 記錄：只含型別名、不含例外訊息值
    assert msgs == [f"onebrain holdings demo {cid} fail-closed: {RuntimeError.__name__}" for cid in EXPECTED_CASE_IDS]
    assert _INJECTED_MSG not in caplog.text


@pytest.mark.parametrize("inject", ["rule_summary_raises", "adapter_raises", "effective_mismatch",
                                    "unexpected_availability", "missing_section", "runtime_banned_market"])
def test_failclosed_variants(monkeypatch, inject):
    cid = "L1"
    if inject == "rule_summary_raises":
        monkeypatch.setattr(S, "build_rule_summary", lambda d: (_ for _ in ()).throw(ValueError("x")))
    elif inject == "adapter_raises":
        monkeypatch.setattr(A, "adapt_holdings_read", lambda s: (_ for _ in ()).throw(TypeError("x")))
    elif inject == "effective_mismatch":
        other = S.build_rule_summary(_oracle("L3")[1].digest)
        import dataclasses
        real = SH.run_shadow
        monkeypatch.setattr(SH, "run_shadow", lambda d, p: dataclasses.replace(real(d, p), effective=other))
    elif inject == "unexpected_availability":
        import dataclasses
        monkeypatch.setitem(demo.CASES, cid, dataclasses.replace(demo.CASES[cid],
                                                                 expect_availability=Availability.AVAILABLE))
    elif inject == "missing_section":
        real_lines = S.build_rule_summary

        class _Fake:
            def __init__(self, r):
                self._r = r
                self.lines = tuple((k, v) for k, v in r.lines if k != "capital_gain")

            def __eq__(self, o):
                return self._r == o
        monkeypatch.setattr(S, "build_rule_summary", lambda d: _Fake(real_lines(d)))
    elif inject == "runtime_banned_market":       # 執行期禁字守衛：市場段混入 ⇒ fail-closed（不是只靠測試掃描）
        monkeypatch.setattr(demo, "SHOWN_SECTIONS", ("market", "buy_and_hold", "capital_gain"))
    b = demo.build_case_block(cid)
    assert b.fail_closed is True
    assert b.area("system_output") == () and b.area("derived") == (DERIVED_ROW,)
    assert b.lines[0].text == DISCLOSURE_FIRST
    _check_banned(b, cid)


_TEETH = [("system_output", w) for w in (*ZERO_HOLDING_CLAIMS, *NEUTRAL_SAFE_CLAIMS, "完整", *A.ALL_REASONS)] + \
    [("derived", w) for w in ("無持股", "中性", "完整", A.REASON_UNIVERSE_NOT_INDEPENDENT)] + \
    [("footer", w) for w in BLOCK_BANNED] + [("ui_note", "⬜ 未評估／資料不足")]


@pytest.mark.parametrize("area, word", _TEETH, ids=[f"{a}:{w}" for a, w in _TEETH])
def test_banned_scan_has_teeth(area, word):
    """分區禁字掃描本身有牙齒：在 L2 區塊插入一行含禁字 ⇒ _check_banned 轉紅（與 parity 獨立）。"""
    b = demo.build_case_block("L2")
    _check_banned(b, "L2")
    bad = demo.DemoBlock("L2", b.lines + (demo.Line(area, f"x{word}x", "buy_and_hold"),), False)
    with pytest.raises(AssertionError):
        _check_banned(bad, "L2")


def test_unknown_case_id_raises_not_failclosed():
    with pytest.raises(KeyError):
        demo.build_case_block("ZZ")


def test_cli_text_runs_offline(capsys):
    assert demo.main(["all"]) == 0
    out = capsys.readouterr().out
    assert out.count(DISCLOSURE_FIRST) == 6


# ══════════════════════════════════════════════════════════════════════
# 邊界守衛
# ══════════════════════════════════════════════════════════════════════
_FORBIDDEN_IMPORTS = ("streamlit", "requests", "urllib", "http", "httpx", "aiohttp", "socket", "time", "random",
                      "os", "openai", "anthropic", "google", "gspread", "yfinance", "FinMind", "src.data", "src.ui",
                      "src.ui2", "app", "app_ui2", "scripts", "shared.onebrain_provider.real")
_FORBIDDEN_ATTRS = {"now", "today", "utcnow", "time", "perf_counter", "monotonic", "secrets", "environ", "getenv"}


def test_demo_ast_no_network_clock_secrets():
    tree = ast.parse(DEMO_FILE.read_text(encoding="utf-8"))
    mods = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods.append(n.module or "")
    bad = [m for m in mods for f in _FORBIDDEN_IMPORTS if m == f or m.startswith(f + ".")]
    assert bad == [], bad
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not (attrs & _FORBIDDEN_ATTRS), attrs & _FORBIDDEN_ATTRS
    assert not (names & (_FORBIDDEN_ATTRS | {"open"})), names & (_FORBIDDEN_ATTRS | {"open"})


def test_no_production_file_imports_the_demo():
    hits = []
    files = [ROOT / "app.py", ROOT / "app_ui2.py"]
    for top in ("shared", "src", "scripts"):
        files += [p for p in (ROOT / top).rglob("*.py") if "__pycache__" not in p.parts]
    for p in files:
        if p.exists() and "onebrain_holdings_ui2_demo" in p.read_text(encoding="utf-8"):
            hits.append(p.relative_to(ROOT).as_posix())
    assert hits == [], "demo 只准被 tests/ 使用：" + repr(hits)


def test_demo_is_not_collected_and_lives_in_tests():
    assert DEMO_FILE.parent.name == "tests" and not DEMO_FILE.name.startswith("test_")


def test_full_check_suite_green():
    _check_all()


# ══════════════════════════════════════════════════════════════════════
# 突變：每個突變都必須讓 _check_all 轉紅（AssertionError）
# ══════════════════════════════════════════════════════════════════════
def _wrap_section_lines(monkeypatch, fn):
    real = demo._section_lines
    monkeypatch.setattr(demo, "_section_lines", lambda summary: fn(real(summary)))


def _m_adapter_ex_returns_list(mp):
    mp.setattr(A, "_ex_evidence_reasons", lambda s: ())


def _m_adapter_ex_returns_list_and_demo_trusts_it(mp):
    import dataclasses
    mp.setattr(A, "_ex_evidence_reasons", lambda s: ())
    mp.setitem(demo.CASES, "R3", dataclasses.replace(demo.CASES["R3"], expect_none=False,
                                                     expect_availability=Availability.AVAILABLE))


def _m_change_one_char(mp):
    _wrap_section_lines(mp, lambda xs: [(k, x.replace("存股", "存货", 1)) for k, x in xs])


def _m_inject_reason_code(mp):
    _wrap_section_lines(mp, lambda xs: xs + [("buy_and_hold", A.REASON_READ_EXCEPTION_NETWORK)])


def _m_inject_reason_code_guard_off(mp):
    mp.setattr(demo, "_guard_displayed", lambda lines: None)
    _m_inject_reason_code(mp)


def _m_include_market(mp):
    mp.setattr(demo, "SHOWN_SECTIONS", ("market", "buy_and_hold", "capital_gain"))


def _m_include_market_guard_off(mp):
    mp.setattr(demo, "_guard_displayed", lambda lines: None)
    mp.setitem(demo.SECTION_LABELS, "market", "市場")
    _m_include_market(mp)


def _m_include_actions_guard_off(mp):
    mp.setattr(demo, "_guard_displayed", lambda lines: None)
    mp.setitem(demo.SECTION_LABELS, "actions", "行動")
    mp.setattr(demo, "SHOWN_SECTIONS", ("buy_and_hold", "capital_gain", "actions"))


def _m_partial_to_ok(mp):
    real = demo.derive_holdings_judgement
    mp.setattr(demo, "derive_holdings_judgement",
               lambda av: None if av is Availability.PARTIAL else real(av))


def _m_partial_reuses_data_short(mp):
    real = demo.derive_holdings_judgement
    mp.setattr(demo, "derive_holdings_judgement",
               lambda av: TEXT_NOT_EVALUATED_DATA_SHORT if av is Availability.PARTIAL else real(av))


def _m_available_shows_row(mp):
    real = demo.derive_holdings_judgement
    mp.setattr(demo, "derive_holdings_judgement",
               lambda av: UNDETERMINABLE if av is Availability.AVAILABLE else real(av))


def _m_remove_disclosure(mp):
    mp.setattr(demo, "DISCLOSURE_LINES", ())


def _m_disclosure_not_first(mp):
    mp.setattr(demo, "DISCLOSURE_LINES", tuple(reversed(demo.DISCLOSURE_LINES)))


def _m_note_never(mp):
    mp.setattr(demo, "NOTE_NO_INPUT_TRIGGER", "（不存在的觸發字）")


def _m_note_always(mp):
    mp.setattr(demo, "NOTE_NO_INPUT_TRIGGER", "無法判定")


def _m_note_text_changed(mp):
    mp.setattr(demo, "NOTE_NO_INPUT", "註：尚無輸入代表沒有持股。")


def _m_show_is_complete_guard_off(mp):
    mp.setattr(demo, "_guard_displayed", lambda lines: None)
    mp.setattr(demo, "FOOTER_LINES", demo.FOOTER_LINES + ("is_complete=True",))


def _m_show_completeness_word_guard_off(mp):
    mp.setattr(demo, "_guard_displayed", lambda lines: None)
    mp.setattr(demo, "DERIVED_MARK", "（持股資料完整）")


def _m_effective_not_rule_summary_unchecked(mp):
    """provider 草稿被『採用』：系統輸出改用 forged_drop_holdings 草稿展開（繞過 demo 的 effective 檢查）。"""
    from shared.decision_digest_grounding import render_draft
    real_chain = demo._run_chain

    def chain(case):
        av, _ = real_chain(case)
        res = A.adapt_holdings_read(case.snapshot)
        a = demo.assemble(case, res.rows_for_digest())
        draft = demo.providers(a.digest)["forged_drop_holdings"].payload
        secs = dict(render_draft(a.digest, draft))
        return av, [(k, x) for k in demo.SHOWN_SECTIONS for x in secs.get(k, ())]
    mp.setattr(demo, "_run_chain", chain)


def _m_failclosed_guesses_sentence(mp):
    real = demo._failclosed_block

    def fb(cid, err):
        b = real(cid, err)
        return demo.DemoBlock(cid, b.lines + (demo.Line("system_output", "⬜ 存股：持股資料不足，無法判定（尚無輸入）",
                                                        "buy_and_hold"),), True, b.error_type)
    mp.setattr(demo, "_failclosed_block", fb)


def _m_failclosed_reraises(mp):
    def fb(cid, err):
        raise err
    mp.setattr(demo, "_failclosed_block", fb)


MUTATIONS = {name[3:]: fn for name, fn in dict(globals()).items() if name.startswith("_m_")}


def test_mutation_inventory():
    assert len(MUTATIONS) >= 20, sorted(MUTATIONS)


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_mutation_turns_red(monkeypatch, name):
    MUTATIONS[name](monkeypatch)
    with pytest.raises(AssertionError):
        _check_all()
