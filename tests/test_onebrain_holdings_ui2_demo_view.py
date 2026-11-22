"""C-OB-HOLD-DEMO-STAGE2-A1（tests-only）— OneBrain 持股 FAKE 示範 → New UI2 `onebrain` L1 槽：mapper／launcher／證據判定器的測試與負控。

被測：`tests/onebrain_holdings_ui2_demo_vm.py`（mapper）、`tests/ui2_viewport/onebrain_hold_demo_launcher.py`、
`tests/ui2_viewport/onebrain_hold_demo_evidence.py`（runner＋純函式判定器）。⛔ 不測、不改 `src/**`、`app_ui2.py`、`shared/**`。

分層（pytest.ini addopts＝`-m "not slow and not ui2_browser"`）：
  · 快測（預設）：mapper／逐字／導出列矩陣／禁字／launcher 行為／AST 守衛／判定器 teeth／mutation 負控。
  · `@pytest.mark.slow`：真 `app_ui2.py` 經 launcher 的 AppTest（案例化斷言，不只驗 `at.exception==[]`）。
  · `@pytest.mark.ui2_browser`：真瀏覽器（Playwright 於函式內才 import；缺則依 `tests/ui2_browser.py` 慣例 skip／required 時 fail）。
    ⚠️ 本檔的 browser 測試**不在** `pr-check.yml` 的 ui2-browser lane 清單內（總管 Q9：不改 workflow）⇒ 原生 CI 覆蓋 NOT VERIFIED，只有本地封網驗證。

Oracle 獨立性：Digest 原句由本檔**自行**跑 `adapt_holdings_read → assemble → build_rule_summary` 取得；列規格、逐字文案、列數、禁字表皆為
本檔**本地常數**（不讀 mapper 的同名常數），所以改 mapper／demo 的常數或列邏輯會被抓到。
⚠️ DOM `data-state="ok"` 只是文字載體：本檔任何斷言都不以它推導持股／安全（`test_ok_state_is_text_carrier_only`）。
"""
from __future__ import annotations

import ast
import dataclasses
import html as htmllib
import inspect
import os
import pathlib
import re
import socket
import sys

import pytest

import src.services.decision_digest_assembly as ASM
import src.services.decision_digest_summary as S
import src.services.onebrain_holdings_adapter as A
import src.services.onebrain_shadow as SH
import tests.onebrain_holdings_ui2_demo as demo
import tests.onebrain_holdings_ui2_demo_vm as VM
import tests.test_ui2_p1_human_text as P1
import tests.ui2_viewport.onebrain_hold_demo_evidence as EV
import tests.ui2_viewport.onebrain_hold_demo_launcher as L
from shared.decision_digest import Availability
from shared.ui2_contract.models import FieldState, JudgementState
from shared.ui2_contract.pages import P4_HOLD, PAGE_IDS, SCENARIO_COLD, SCENARIO_IDS
from shared.ui2_contract.text import TEXT_ASOF_MISSING, TEXT_RISK_CAP_UNDETERMINABLE
from src.ui2.views._page import section_l1_html
from tests.ui2_viewport import measure_viewport as MV

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "tests" / "ui2_viewport" / "onebrain_hold_demo_launcher.py"
MAPPER_PATH = ROOT / "tests" / "onebrain_holdings_ui2_demo_vm.py"
EVIDENCE_PATH = ROOT / "tests" / "ui2_viewport" / "onebrain_hold_demo_evidence.py"

# ══════════════════════════════════════════════════════════════════════
# 本地 oracle 常數（刻意不讀 mapper 的同名常數）
# ══════════════════════════════════════════════════════════════════════
CASE_IDS = ("R1", "R2", "R3", "L1", "L2", "L3")
ROW_COUNTS = {"R1": 7, "R2": 7, "R3": 7, "L1": 9, "L2": 8, "L3": 5}
FAILCLOSED_ROWS = 5
SECTION_ID, LEVEL, TITLE = "onebrain", "L1", "🤖 OneBrain 持股摘要"
DISCLOSURE = "示意：合成持股快照（FAKE）；非真實持股；非即時 OneBrain；非投資建議"
DERIVED_FOOTNOTE = "此列由畫面依持股狀態推導，非系統摘要原句"
FAILCLOSED_FOOTNOTE = "此列為固定顯示，非系統摘要原句"
FAILCLOSED_NOTE = "示意內容未能產生，未顯示任何摘要句"
SOURCE = "FAKE 合成持股快照（非真實持股）"
ASOF = "無（FAKE 示意，沒有持股讀取時點）"
UNDETERMINABLE = "⬜ 無法判定"
NOTE_TRIGGER = "（尚無輸入）"
NOTE_D3 = "註：『尚無輸入』是現行摘要措辭，也可能代表讀取失敗、輸入異常或缺少組合鍵；請勿解讀為零持股。"
TESTINFO_PREFIX = "測試輸入說明（非系統輸出）："
LABEL_OF = {"buy_and_hold": "存股", "capital_gain": "資本利得"}
ORACLE_SECTIONS = ("buy_and_hold", "capital_gain")
LABEL_WHITELIST = ("示意", "持股判讀", "存股", "資本利得", "說明", "來源", "時點")
#: 任何狀態、任何位置（槽與整頁）都不得出現
NEVER_ANYWHERE = ("顯示＝規則式摘要", "FakeProvider", "§C", "示範鏈", "與本頁其他 FAKE 數字無關")
#: 槽內（rows 全文字）禁字；「零持股」僅核定註記列逐字許可
BANNED = ("市場位階", "Risk Cap", "風險上限", "本期行動", "shadow_accepted", "grounding", "is_complete", "完整", "正常",
          "安全", "中性", "空倉", "0 檔", "零持股", "bull", "🟢", "72.5", "txt-", "未評估", "草稿", *A.ALL_REASONS)
DEFAULT_SLOT_TEXT = "🤖 OneBrain 持股摘要 ⬜ 尚未提供 此功能尚未開放"

_ROW_RX = re.compile(
    r'<div class="ui2-row" data-axis="(\w+)" data-state="(\w+)">(?:<div class="ui2-row__label">(.*?)</div>)?'
    r'<div class="ui2-row__body"><span class="ui2-row__value">(.*?)</span>(.*?)</div>'
    r'(?:<div class="ui2-row__detail">(.*?)</div>)?</div>', re.S)


@pytest.fixture(autouse=True)
def _always_uninstall(monkeypatch):
    """每個測試前後都還原 launcher（函式、哨兵、shell.CSS、封網）；結束時斷言沒有洩漏。
    ⚠️ 必須**依賴 monkeypatch**：fixture 反向拆除 ⇒ 本 fixture 的 `uninstall()` 先於 monkeypatch 復原。
    否則被測試 monkeypatch 過的 `shell.get_preview_page_vm`（記錄器／lambda）會被 `uninstall()` 當成「原函式」寫回、洩漏給後面的測試檔。"""
    L.uninstall()
    cwd = os.getcwd()
    yield
    L.uninstall()
    shell = L._shell()
    assert not any(hasattr(shell, a) for a in (L.ORIG_ATTR, L.CSS_ATTR, L.STATE_ATTR)), "launcher 哨兵洩漏"
    assert getattr(shell.get_preview_page_vm, "__obdemo_wrapper__", False) is False, "shell.get_preview_page_vm 仍被包"
    assert "PREVIEW-ONLY" not in shell.CSS, "shell.CSS 洩漏預覽 CSS"
    assert not hasattr(socket, L.SEAL_ATTR), "封網洩漏"
    assert os.getcwd() == cwd, "cwd 洩漏"


# ══════════════════════════════════════════════════════════════════════
# 獨立 oracle 與共用檢查
# ══════════════════════════════════════════════════════════════════════
def _oracle(cid):
    case = demo.CASES[cid]
    res = A.adapt_holdings_read(case.snapshot)
    a = demo.assemble(case, res.rows_for_digest())
    summary = S.build_rule_summary(a.digest)
    secs = dict(summary.lines)
    return a.digest.holdings.availability, tuple((k, x) for k in ORACLE_SECTIONS for x in secs[k])


def _expected_rows(cid):
    av, sents = _oracle(cid)
    rows = [("示意", "D", DISCLOSURE)]
    if av is not Availability.AVAILABLE:
        rows.append(("持股判讀", "J", DERIVED_FOOTNOTE))
    rows += [(LABEL_OF[k], "D", t) for k, t in sents]
    if any(NOTE_TRIGGER in t for _k, t in sents):
        rows.append(("說明", "D", NOTE_D3))
    rows += [("來源", "D", SOURCE), ("時點", "D", ASOF)]
    return rows


def _expected_failclosed_rows():
    return [("示意", "D", DISCLOSURE), ("持股判讀", "J", FAILCLOSED_FOOTNOTE), ("說明", "D", FAILCLOSED_NOTE),
            ("來源", "D", SOURCE), ("時點", "D", ASOF)]


def _got_rows(section):
    out = []
    for f in section.fields:
        if isinstance(f.state, JudgementState):
            out.append((f.label, "J", f.detail))
        else:
            out.append((f.label, "D", f.value_text))
    return out


def _html_rows(section):
    """SectionVM → 實際 HTML → 逐列解析（確認 `FieldVM` 真的被畫成預期的 DOM）。"""
    text = htmllib.unescape(section_l1_html(section))
    rows = []
    for axis, state, label, value, chip, detail in _ROW_RX.findall(text):
        rows.append({"axis": axis, "state": state, "label": label, "value": value,
                     "chip": re.sub(r"<[^>]+>", "", chip), "detail": detail})
    return text, rows


def _all_texts(section):
    return [t for f in section.fields for t in (f.label, f.value_text, f.status_text, f.detail) if t]


def _banned_hits(section) -> list[str]:
    """禁字掃描。例外只有一個：**核定註記列**（label=說明 且 value 逐字＝NOTE_D3）可含「零持股」；其餘一切照掃。"""
    hits = []
    for f in section.fields:
        is_core_note = f.label == "說明" and f.value_text == NOTE_D3
        for t in (f.label, f.value_text, f.status_text, f.detail):
            if not t:
                continue
            scan = t.replace("零持股", "") if (is_core_note and t == NOTE_D3) else t
            hits += [f"{f.label}:{w}" for w in BANNED if w in scan]
    return hits


def _visible_text(section) -> str:
    text, _ = _html_rows(section)
    return re.sub(r"<[^>]+>", " ", text)


def _check_scans(section):
    assert _banned_hits(section) == [], f"禁字 {_banned_hits(section)}"
    joined = "\n".join(_all_texts(section))
    for w in NEVER_ANYWHERE:
        assert w not in joined, f"UI 槽不得出現 {w}"
    assert P1.hits_in(joined) == [], f"工程詞彙（mapper 輸出）{P1.hits_in(joined)}"
    vis = _visible_text(section)
    assert P1.hits_in(vis) == [], f"工程詞彙（渲染 HTML 可見字）{P1.hits_in(vis)}"
    for w in NEVER_ANYWHERE:
        assert w not in vis


def _check_normal(cid):
    sec = VM.build_section(demo.build_case_block(cid))
    assert (sec.section_id, sec.level, sec.title) == (SECTION_ID, LEVEL, TITLE)
    got, want = _got_rows(sec), _expected_rows(cid)
    assert got == want, f"{cid} 列不符\n got={got}\nwant={want}"
    assert len(sec.fields) == ROW_COUNTS[cid]
    assert [f.label for f in sec.fields] == [r[0] for r in want] and set(f.label for f in sec.fields) <= set(LABEL_WHITELIST)
    for f in sec.fields:
        if isinstance(f.state, JudgementState):
            assert f.state is JudgementState.UNDETERMINABLE and f.status_text == UNDETERMINABLE and f.value_text is None
        else:
            assert f.state is FieldState.OK and f.status_text is None and f.detail is None and f.value_text
    _text, rows = _html_rows(sec)
    assert [(r["label"], r["axis"], r["state"]) for r in rows] == [
        (lb, "judgement" if k == "J" else "data", "undeterminable" if k == "J" else "ok") for lb, k, _t in want]
    _check_scans(sec)
    return sec


def _failclosed_section(cid="R1"):
    sec, fc = L.build_demo_section(cid, True)
    assert fc is True
    return sec


def _check_failclosed(sec):
    assert (sec.section_id, sec.level, sec.title) == (SECTION_ID, LEVEL, TITLE)
    assert _got_rows(sec) == _expected_failclosed_rows(), f"fail-closed 列不符：{_got_rows(sec)}"
    assert len(sec.fields) == FAILCLOSED_ROWS, "fail-closed 列數"
    joined = "\n".join(_all_texts(sec))
    assert NOTE_D3 not in joined and "尚無輸入" not in joined and TESTINFO_PREFIX not in joined, "fail-closed 不得有 D3／測試輸入"
    assert not any(f.label in ("存股", "資本利得") for f in sec.fields), "fail-closed 不得猜 Digest 句"
    _check_scans(sec)


def _check_all():
    for cid in CASE_IDS:
        _check_normal(cid)
        _check_failclosed(_failclosed_section(cid))


# ══════════════════════════════════════════════════════════════════════
# A. mapper 正向
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("cid", CASE_IDS)
def test_row_counts_labels_and_fields_per_case(cid):
    _check_normal(cid)


def test_row_count_table_is_exactly_the_approved_one():
    assert {cid: len(VM.build_section(demo.build_case_block(cid)).fields) for cid in CASE_IDS} == ROW_COUNTS
    assert len(_failclosed_section().fields) == FAILCLOSED_ROWS


@pytest.mark.parametrize("cid", CASE_IDS)
def test_source_and_asof_rows_exact(cid):
    sec = VM.build_section(demo.build_case_block(cid))
    f = sec.fields
    assert (f[-2].label, f[-2].value_text, f[-1].label, f[-1].value_text) == ("來源", SOURCE, "時點", ASOF)
    assert f[-1].value_text != TEXT_ASOF_MISSING and TEXT_ASOF_MISSING not in "\n".join(_all_texts(sec)), "時點不用 TEXT_ASOF_MISSING"


@pytest.mark.parametrize("cid", CASE_IDS)
def test_disclosure_row_first(cid):
    f = VM.build_section(demo.build_case_block(cid)).fields
    assert (f[0].label, f[0].value_text) == ("示意", DISCLOSURE)
    assert f[0].value_text == demo.DISCLOSURE_LINES[0]
    first_digest = next(i for i, x in enumerate(f) if x.label in ("存股", "資本利得"))
    assert first_digest <= 2, "示意首列與首個 Digest 句最多相距 2 列"


@pytest.mark.parametrize("cid", CASE_IDS)
def test_mapper_verbatim_sentences_equal_digest(cid):
    _av, sents = _oracle(cid)
    got = [(f.label, f.value_text) for f in VM.build_section(demo.build_case_block(cid)).fields if f.label in ("存股", "資本利得")]
    assert got == [(LABEL_OF[k], t) for k, t in sents]            # 原句逐字、原順序、重複 label 保留；未 strip
    assert all(t == t.strip() for _l, t in got)
    assert all("⬜" in t for _l, t in got), "Digest 原句帶 ⬜ 者不得被改寫成 0"


def test_l1_pair_in_digest_order():
    f = VM.build_section(demo.build_case_block("L1")).fields
    labels = [x.label for x in f]
    assert labels == ["示意", "持股判讀", "存股", "存股", "資本利得", "資本利得", "說明", "來源", "時點"]
    _av, sents = _oracle("L1")
    assert [x.value_text for x in f if x.label in ("存股", "資本利得")] == [t for _k, t in sents]


def test_l2_order_is_not_resorted():
    f = [x for x in VM.build_section(demo.build_case_block("L2")).fields if x.label == "存股"]
    assert "另有 1 檔持股缺少投資組合鍵" in f[0].value_text and "尚未設定投資策略分類" in f[1].value_text


def test_none_cases_are_word_for_word_identical():
    """R1／R2／R3（adapter 回 None）原句與整個區塊逐字相同（原因不傳遞）。"""
    a, b, c = (VM.build_section(demo.build_case_block(x)) for x in ("R1", "R2", "R3"))
    assert a == b == c


@pytest.mark.parametrize("cid", CASE_IDS)
def test_note_iff_trigger_verbatim(cid):
    _av, sents = _oracle(cid)
    f = VM.build_section(demo.build_case_block(cid)).fields
    notes = [x for x in f if x.label == "說明"]
    has_trigger = any(NOTE_TRIGGER in t for _k, t in sents)
    assert bool(notes) is has_trigger
    if notes:
        assert len(notes) == 1 and notes[0].value_text == NOTE_D3
        i = f.index(notes[0])
        assert f[i - 1].label in ("存股", "資本利得") and f[i + 1].label == "來源"
    assert {cid: bool(notes)} == {cid: {"R1": True, "R2": True, "R3": True, "L1": True, "L2": False, "L3": False}[cid]}


@pytest.mark.parametrize("cid", CASE_IDS)
def test_derived_row_matrix(cid):
    av, _s = _oracle(cid)
    rows = [x for x in VM.build_section(demo.build_case_block(cid)).fields if x.label == "持股判讀"]
    if av is Availability.AVAILABLE:
        assert rows == [] and cid == "L3"
    else:
        assert len(rows) == 1
        r = rows[0]
        assert (r.state, r.status_text, r.value_text, r.detail) == (JudgementState.UNDETERMINABLE, UNDETERMINABLE, None, DERIVED_FOOTNOTE)
        assert r.status_text == TEXT_RISK_CAP_UNDETERMINABLE


def test_l3_has_no_completeness_claim():
    sec = VM.build_section(demo.build_case_block("L3"))
    text = "\n".join(_all_texts(sec))
    assert not any(w in text for w in ("完整", "正常", "安全", "OK", "✅", "🟢", "已通過"))
    assert [x.label for x in sec.fields] == ["示意", "存股", "資本利得", "來源", "時點"]


def test_provider_draft_never_displayed():
    """FakeProvider 全模式＋偽造草稿：顯示列恆等於規則式摘要，且與 provider 無關（草稿不採用）。"""
    for cid in CASE_IDS:
        _av, _s = _oracle(cid)
        res = A.adapt_holdings_read(demo.CASES[cid].snapshot)
        digest = demo.assemble(demo.CASES[cid], res.rows_for_digest()).digest
        summary = S.build_rule_summary(digest)
        provs = demo.providers(digest)
        assert {"forged_safe_literal", "forged_drop_holdings", "clean_reordered"} <= set(provs)
        for mode, p in provs.items():
            assert SH.run_shadow(digest, p).effective == summary, mode
        text = "\n".join(_all_texts(VM.build_section(demo.build_case_block(cid))))
        assert "草稿" not in text and "FakeProvider" not in text and "safe" not in text.lower()


_REAL_PROVIDERS = demo.providers


def test_provider_draft_cannot_change_mapper_output(monkeypatch):
    """只留偽造／乾淨重排草稿的 provider：示範鏈照常通過，顯示列與原本逐字相同（草稿不採用）。"""
    base = {cid: VM.build_section(demo.build_case_block(cid)) for cid in CASE_IDS}
    monkeypatch.setattr(demo, "providers", lambda d: {k: v for k, v in _REAL_PROVIDERS(d).items()
                                                      if k.startswith(("forged", "clean"))})
    got = {cid: demo.build_case_block(cid) for cid in CASE_IDS}
    assert all(b.fail_closed is False for b in got.values())
    assert {cid: VM.build_section(b) for cid, b in got.items()} == base


def test_ui_slot_never_contains_display_footer():
    for cid in CASE_IDS:
        sec = VM.build_section(demo.build_case_block(cid))
        blob = "\n".join(_all_texts(sec)) + _visible_text(sec)
        assert "顯示＝規則式摘要" not in blob and "FakeProvider 草稿不採用" not in blob
    fc = _failclosed_section()
    assert "顯示＝規則式摘要" not in "\n".join(_all_texts(fc)) + _visible_text(fc)


def test_mapper_independent_of_footer_structure(monkeypatch):
    """mapper 以 `block.fail_closed`／區域判定，不讀 footer：把 demo 的 footer 常數改壞，輸出不變（#1265 footer 怎麼改都不影響）。"""
    base = {cid: VM.build_section(demo.build_case_block(cid)) for cid in CASE_IDS}
    base_fc = _failclosed_section()
    for name in ("FOOTER_DISPLAY", "FOOTER_SOURCE", "FOOTER_ASOF", "TEST_INPUT_PREFIX", "FAILCLOSED_NOTE"):
        monkeypatch.setattr(demo, name, "XXX 被改壞 XXX")
    monkeypatch.setattr(demo, "FOOTER_LINES", ("a", "b", "c"))
    monkeypatch.setattr(demo, "FAILCLOSED_FOOTER_LINES", ("x",))
    assert {cid: VM.build_section(demo.build_case_block(cid)) for cid in CASE_IDS} == base
    assert _failclosed_section() == base_fc


def test_ok_state_is_text_carrier_only():
    """Q4：D 列在 DOM 上全是 data-state=ok（連 ⬜ 資料不足、來源、時點也是）⇒ ok 不代表持股正常；判定器不得以它推導安全。"""
    assert VM.OK_STATE_IS_TEXT_CARRIER_ONLY is True
    sec = VM.build_section(demo.build_case_block("R1"))             # UNAVAILABLE：資料不足
    _t, rows = _html_rows(sec)
    d_rows = [r for r in rows if r["axis"] == "data"]
    assert d_rows and all(r["state"] == "ok" for r in d_rows)
    assert any("資料不足" in r["value"] for r in d_rows), "⬜ 資料不足句也是 data-state=ok"
    judge = [r for r in rows if r["axis"] == "judgement"]
    assert [r["state"] for r in judge] == ["undeterminable"]

    def infer_safe_from_dom(rs):                                   # 假想的錯誤推導：全 ok ⇒ 安全
        return all(r["state"] == "ok" for r in rs if r["axis"] == "data")
    assert infer_safe_from_dom(rows) is True                        # 這個推導對 UNAVAILABLE 案例也成立 ⇒ 證明它不可用
    assert "ok" in {r["state"] for r in rows} and any(r["axis"] == "judgement" for r in rows)


def test_testinfo_outside_slot_not_in_slot_html():
    for cid in CASE_IDS:
        info = VM.test_info_text(cid)
        assert info == TESTINFO_PREFIX + demo.CASES[cid].test_input and info.startswith(TESTINFO_PREFIX)
        assert "§C" not in info and P1.hits_in(info) == []
        sec = VM.build_section(demo.build_case_block(cid))
        text, _rows = _html_rows(sec)
        assert info not in text and TESTINFO_PREFIX not in text and demo.CASES[cid].test_input not in text
        assert not any(demo.CASES[cid].test_input in t for t in _all_texts(sec))
    with pytest.raises(KeyError):
        VM.test_info_text("ZZ")


def test_three_blank_square_meanings_are_not_conflated():
    """Q3-9：「⬜ 尚未提供」＝正式功能尚未開啟（預設槽）；「持股判讀 ⬜ 無法判定」＝FAKE 輸入不足／部分可用但不能判斷；
    首屏「Risk Cap ⬜ 無法判定」＝獨立風險資料不足。示範槽只用第二種，不得混入第一種，L3 AVAILABLE 也不寫成完整／安全。"""
    for sec in [VM.build_section(demo.build_case_block(c)) for c in CASE_IDS] + [_failclosed_section()]:
        joined = "\n".join(_all_texts(sec))
        assert "⬜ 尚未提供" not in joined and "此功能尚未開放" not in joined and "Risk Cap" not in joined
        judges = [f for f in sec.fields if f.label == "持股判讀"]
        assert all(f.status_text == UNDETERMINABLE for f in judges)
    l3 = "\n".join(_all_texts(VM.build_section(demo.build_case_block("L3"))))
    assert UNDETERMINABLE not in l3 or "持股判讀" not in l3, "L3 AVAILABLE 不得帶『無法判定』判讀列"


def test_testinfo_wanted_only_for_injected_non_failclosed():
    assert L.testinfo_wanted({"injected": True, "failclosed": False}) is True
    assert L.testinfo_wanted({"injected": True, "failclosed": True}) is False
    assert L.testinfo_wanted({"injected": False, "failclosed": False}) is False
    assert L.testinfo_wanted({}) is False


def test_no_cross_page_claim_and_no_engineering_codes():
    secs = [VM.build_section(demo.build_case_block(c)) for c in CASE_IDS] + [_failclosed_section()]
    for sec in secs:
        blob = "\n".join(_all_texts(sec)) + _visible_text(sec)
        for w in ("與本頁其他 FAKE 數字無關", "§C", "示範鏈", "is_complete"):
            assert w not in blob
        assert not re.search(r"§C-\d+|C-\d+", blob)


# ══════════════════════════════════════════════════════════════════════
# B. fail-closed
# ══════════════════════════════════════════════════════════════════════
def test_failclosed_fixed_wording():
    _check_failclosed(_failclosed_section())
    assert VM.FAILCLOSED_NOTE == FAILCLOSED_NOTE and VM.FAILCLOSED_FOOTNOTE == FAILCLOSED_FOOTNOTE
    assert "暫時" not in FAILCLOSED_NOTE and "重試" not in FAILCLOSED_NOTE, "不得暗示可重試"
    assert VM.DERIVED_FOOTNOTE != VM.FAILCLOSED_FOOTNOTE, "fail-closed 不得假裝已推導可用性"
    ti = [x for x in _failclosed_section().fields]
    assert not any(TESTINFO_PREFIX in (x.value_text or "") for x in ti)


def _step_snapshot(mp):
    mp.setitem(demo.CASES, "L1", dataclasses.replace(demo.CASES["L1"], snapshot=None))


def _step_adapter_raise(mp):
    mp.setattr(A, "adapt_holdings_read", lambda s: (_ for _ in ()).throw(TypeError("x")))


def _step_adapter_path(mp):
    mp.setitem(demo.CASES, "L1", dataclasses.replace(demo.CASES["L1"], expect_none=True))


def _step_assemble(mp):
    mp.setattr(ASM, "assemble_digest", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))


def _step_summary(mp):
    mp.setattr(S, "build_rule_summary", lambda d: (_ for _ in ()).throw(ValueError("x")))


def _step_shadow_mismatch(mp):
    other = S.build_rule_summary(_oracle_digest("L3"))
    real = SH.run_shadow
    mp.setattr(SH, "run_shadow", lambda d, p: dataclasses.replace(real(d, p), effective=other))


def _step_availability(mp):
    mp.setitem(demo.CASES, "L1", dataclasses.replace(demo.CASES["L1"], expect_availability=Availability.AVAILABLE))


def _step_banned(mp):
    mp.setattr(demo, "RUNTIME_BANNED", (*demo.RUNTIME_BANNED, "存股"))


def _step_vm_build(mp):
    real = VM.build_fields

    def fields(block):
        if block.fail_closed is False:
            raise VM.MapperError("注入：正常區塊 mapper 失敗")
        return real(block)
    mp.setattr(VM, "build_fields", fields)


def _oracle_digest(cid):
    res = A.adapt_holdings_read(demo.CASES[cid].snapshot)
    return demo.assemble(demo.CASES[cid], res.rows_for_digest()).digest


FAILCLOSED_STEPS = {"snapshot": _step_snapshot, "adapter_raise": _step_adapter_raise, "adapter_path": _step_adapter_path,
                    "assemble": _step_assemble, "summary": _step_summary, "shadow_mismatch": _step_shadow_mismatch,
                    "availability": _step_availability, "banned": _step_banned, "vm_build": _step_vm_build}


@pytest.mark.parametrize("step", list(FAILCLOSED_STEPS))
def test_failclosed_each_step(monkeypatch, step):
    FAILCLOSED_STEPS[step](monkeypatch)
    real_assemble = ASM.assemble_digest
    sec, fc = L.build_demo_section("L1", False)
    assert fc is True, f"{step}：未 fail-closed"
    _check_failclosed(sec)
    assert ASM.assemble_digest is real_assemble


def test_failclosed_injection_restores_assemble_even_on_error(monkeypatch):
    real = ASM.assemble_digest
    monkeypatch.setattr(demo, "build_case_block", lambda cid: (_ for _ in ()).throw(KeyError("boom")))
    with pytest.raises(KeyError):
        L.build_demo_section("R1", True)
    assert ASM.assemble_digest is real


def test_failclosed_drift_in_mapper_raises_not_silent(monkeypatch):
    """mapper 常數漂移（示意首列與 demo 不一致）⇒ launcher 失敗（raise），不是靜默顯示壞畫面。"""
    monkeypatch.setattr(VM, "DISCLOSURE_FIRST", "示意：被改過的首列")
    with pytest.raises(VM.MapperError):
        L.build_demo_section("R1", False)
    with pytest.raises(VM.MapperError):
        L.build_demo_section("R1", True)


# ══════════════════════════════════════════════════════════════════════
# C. 禁字掃描（含核定註記例外的窄化）
# ══════════════════════════════════════════════════════════════════════
def _sec(*rows):
    from shared.ui2_contract.models import FieldVM, SectionVM
    return SectionVM("onebrain", TITLE, "L1", tuple(FieldVM(lb, FieldState.OK, value_text=t) for lb, t in rows))


def test_banned_scan_exempts_only_core_note_row():
    assert _banned_hits(_sec(("說明", NOTE_D3))) == []                                  # 逐字核定註記：許可
    assert _banned_hits(_sec(("說明", NOTE_D3 + "。"))) != []                           # 多一字：不再例外
    assert _banned_hits(_sec(("說明", NOTE_D3.replace("請勿", "請別")))) != []           # 改一字
    assert _banned_hits(_sec(("存股", NOTE_D3))) != []                                  # 換 label
    assert _banned_hits(_sec(("存股", "存股：零持股"))) != []                           # 其他列的「零持股」
    assert _banned_hits(_sec(("來源", "FAKE 合成持股快照（非真實持股）；零持股"))) != []


@pytest.mark.parametrize("word", [w for w in BANNED if w not in A.ALL_REASONS] + [A.ALL_REASONS[0], A.ALL_REASONS[-1]])
def test_banned_scan_flags_every_word(word):
    assert _banned_hits(_sec(("存股", f"x {word} y"))) != []


def test_banned_scan_clean_on_all_real_output():
    for cid in CASE_IDS:
        assert _banned_hits(VM.build_section(demo.build_case_block(cid))) == []
    assert _banned_hits(_failclosed_section()) == []


def test_hits_in_engineering_vocab_on_mapper_and_html():
    for sec in [VM.build_section(demo.build_case_block(c)) for c in CASE_IDS] + [_failclosed_section()]:
        joined = "\n".join(_all_texts(sec))
        assert P1.hits_in(joined) == [] and P1.hits_in(_visible_text(sec)) == []
    for cid in CASE_IDS:
        assert P1.hits_in(VM.test_info_text(cid)) == []
    assert P1.hits_in("需要 Gate 與 canonical") != [], "hits_in 本身須有牙（抓得到工程詞）"


# ══════════════════════════════════════════════════════════════════════
# D. 負控／突變：每一項改壞即須紅（_check_all 或對應檢查必須 raise）
# ══════════════════════════════════════════════════════════════════════
_RED = (AssertionError, VM.MapperError)


def _wrap_fields(mp, fn):
    real = VM.build_fields
    mp.setattr(VM, "build_fields", lambda block: fn(tuple(real(block)), block))


def _row(label, text):
    from shared.ui2_contract.models import FieldVM
    return FieldVM(label, FieldState.OK, value_text=text)


def _drop(label):
    return lambda mp: _wrap_fields(mp, lambda rows, b: tuple(f for f in rows if f.label != label))


def _append(label, text):
    return lambda mp: _wrap_fields(mp, lambda rows, b: rows[:-2] + (_row(label, text),) + rows[-2:])


def _edit(label, fn, nth=0):
    def apply(mp):
        def go(rows, b):
            out, seen = [], 0
            for f in rows:
                if f.label == label and f.value_text is not None:
                    if seen == nth:
                        f = dataclasses.replace(f, value_text=fn(f.value_text))
                    seen += 1
                out.append(f)
            return tuple(out)
        _wrap_fields(mp, go)
    return apply


def _swap_l2(mp):
    def go(rows, b):
        idx = [i for i, f in enumerate(rows) if f.label == "存股"]
        if len(idx) == 2:
            rows = list(rows)
            rows[idx[0]], rows[idx[1]] = rows[idx[1]], rows[idx[0]]
        return tuple(rows)
    _wrap_fields(mp, go)


def _derive_patch(fn):
    def apply(mp):
        real = demo.derive_holdings_judgement
        mp.setattr(demo, "derive_holdings_judgement", lambda av: fn(av, real))
    return apply


def _failclosed_with_sentence(mp):
    _wrap_fields(mp, lambda rows, b: rows[:2] + (_row("存股", "⬜ 存股：猜的一句"),) + rows[2:] if b.fail_closed else rows)


MUTATIONS = {
    # 來源／時點／示意首列
    "drop_source": _drop("來源"), "drop_asof": _drop("時點"), "drop_disclosure": _drop("示意"),
    "asof_uses_missing_text": lambda mp: mp.setattr(VM, "ASOF_VALUE", TEXT_ASOF_MISSING),
    "source_text_changed": lambda mp: mp.setattr(VM, "SOURCE_VALUE", "FAKE 合成持股快照"),
    "disclosure_text_changed": lambda mp: mp.setattr(VM, "DISCLOSURE_FIRST", "示意：合成持股快照"),
    "disclosure_not_first": lambda mp: _wrap_fields(mp, lambda r, b: r[1:2] + r[:1] + r[2:]),
    # D3 註記
    "note_one_char_changed": lambda mp: mp.setattr(VM, "NOTE_D3", NOTE_D3.replace("請勿", "請別")),
    "note_never_shown": lambda mp: mp.setattr(VM, "NOTE_TRIGGER", "（絕不會出現的字串）"),
    "note_shown_without_trigger": lambda mp: mp.setattr(VM, "NOTE_TRIGGER", ""),
    "note_label_changed": lambda mp: mp.setattr(VM, "LABEL_NOTE", "註"),
    "note_row_dropped": _drop("說明"),
    # D9 持股判讀
    "derived_text_changed": _derive_patch(lambda av, real: "⬜ 未評估／資料不足" if real(av) else None),
    "derived_missing_for_unavailable": _derive_patch(lambda av, real: None if av is Availability.UNAVAILABLE else real(av)),
    "derived_missing_for_partial": _derive_patch(lambda av, real: None if av is Availability.PARTIAL else real(av)),
    "l3_gets_derived_row": _derive_patch(lambda av, real: UNDETERMINABLE),
    "derived_row_dropped": _drop("持股判讀"),
    # 逐字句
    "sentence_one_char_changed": _edit("存股", lambda t: t.replace("⬜", "0")),
    "sentence_stripped_prefix": _edit("資本利得", lambda t: " " + t),
    "sentence_rewritten": _edit("存股", lambda t: t.replace("無法判定", "尚可")),
    "l2_order_swapped": _swap_l2,
    # 草稿／FOOTER／跨頁／工程碼
    "forged_draft_sentence": _append("存股", "safe"),
    "footer_display_in_slot": _append("說明", demo.FOOTER_DISPLAY),
    "footer_fakeprovider_in_slot": _append("說明", "FakeProvider 草稿不採用"),
    "cross_page_claim": _append("說明", "與本頁其他 FAKE 數字無關"),
    "engineering_code": _append("說明", "§C-2"),
    "demo_chain_word": _append("說明", "示範鏈未通過檢查"),
    "testinfo_inside_slot": _append("說明", "測試輸入說明（非系統輸出）：合成讀取結局為網路例外；無列資訊"),
    "banned_market_word": _append("說明", "市場位階 72.5"),
    "banned_zero_holding": _append("說明", "零持股"),
    # fail-closed
    "failclosed_with_digest_sentence": _failclosed_with_sentence,
    "failclosed_note_changed": lambda mp: mp.setattr(VM, "FAILCLOSED_NOTE", "示範鏈未通過檢查，未顯示任何系統句"),
    "failclosed_note_has_tentative": lambda mp: mp.setattr(VM, "FAILCLOSED_NOTE", "示意內容暫時無法產生，未顯示任何摘要句"),
    "failclosed_footnote_swapped": lambda mp: mp.setattr(VM, "FAILCLOSED_FOOTNOTE", VM.DERIVED_FOOTNOTE),
    "failclosed_drops_source": lambda mp: _wrap_fields(mp, lambda r, b: tuple(f for f in r if not (b.fail_closed and f.label == "來源"))),
}


def test_check_all_is_green_on_the_unmutated_tree():
    _check_all()


@pytest.mark.parametrize("name", list(MUTATIONS))
def test_mutation_turns_red(monkeypatch, name):
    MUTATIONS[name](monkeypatch)
    with pytest.raises(_RED):
        _check_all()


#: 掃描類控制必須**不靠整列相等**也能抓到（獨立證明禁字／FOOTER／跨頁／工程碼／測試輸入掃描本身有牙）
SCAN_ONLY_MUTATIONS = ("footer_display_in_slot", "footer_fakeprovider_in_slot", "cross_page_claim", "engineering_code",
                       "demo_chain_word", "banned_market_word", "banned_zero_holding")


@pytest.mark.parametrize("name", SCAN_ONLY_MUTATIONS)
def test_scan_alone_catches_mutation(monkeypatch, name):
    MUTATIONS[name](monkeypatch)
    with pytest.raises(AssertionError):
        _check_scans(VM.build_section(demo.build_case_block("R1")))


def _check_testinfo_not_in_slot(cid):
    sec = VM.build_section(demo.build_case_block(cid))
    text, _rows = _html_rows(sec)
    assert TESTINFO_PREFIX not in text and demo.CASES[cid].test_input not in text, "測試輸入說明不得在槽內"
    assert not any(TESTINFO_PREFIX in t or demo.CASES[cid].test_input in t for t in _all_texts(sec))


def test_testinfo_scan_alone_catches_mutation(monkeypatch):
    _check_testinfo_not_in_slot("R1")
    MUTATIONS["testinfo_inside_slot"](monkeypatch)
    with pytest.raises(AssertionError):
        _check_testinfo_not_in_slot("R1")


def test_mutation_catalog_covers_each_control_in_the_spec_table():
    """規格 §4 負控表的每個控制都至少有一個突變（防止有人靜默刪掉某個負控）。"""
    need = ("drop_source", "drop_disclosure", "asof_uses_missing_text", "note_one_char_changed", "note_never_shown",
            "note_shown_without_trigger", "note_label_changed", "derived_text_changed", "derived_missing_for_unavailable",
            "l3_gets_derived_row", "forged_draft_sentence", "footer_display_in_slot", "cross_page_claim", "engineering_code",
            "testinfo_inside_slot", "failclosed_with_digest_sentence", "failclosed_note_changed", "failclosed_footnote_swapped",
            "sentence_one_char_changed", "l2_order_swapped", "sentence_stripped_prefix", "banned_zero_holding")
    assert set(need) <= set(MUTATIONS)


def test_mutation_testinfo_prefix_changed_turns_red(monkeypatch):
    monkeypatch.setattr(VM, "TEST_INFO_PREFIX", "說明：")
    with pytest.raises(AssertionError):
        assert VM.test_info_text("R1").startswith(TESTINFO_PREFIX)


def test_mutation_failclosed_still_draws_testinfo_turns_red(monkeypatch):
    monkeypatch.setattr(L, "testinfo_wanted", lambda state: True)
    with pytest.raises(AssertionError):
        assert L.testinfo_wanted({"injected": True, "failclosed": True}) is False


# ══════════════════════════════════════════════════════════════════════
# E. launcher
# ══════════════════════════════════════════════════════════════════════
def _wrap_depth(fn) -> int:
    d = 0
    while getattr(fn, "__obdemo_wrapper__", False):
        d += 1
        fn = fn.__wrapped__
    return d


def _default_vm(page=P4_HOLD, scenario=SCENARIO_COLD, **kw):
    import src.services.ui2.preview_feed as PF
    return PF.get_preview_page_vm(page, scenario, **kw)


def _check_wraps_once(shell, original, installs=3):
    for _ in range(installs):
        L.install()
    cur = shell.get_preview_page_vm
    assert _wrap_depth(cur) == 1, f"包了 {_wrap_depth(cur)} 層"
    assert cur.__wrapped__ is original and getattr(shell, L.ORIG_ATTR) is original
    assert getattr(original, "__obdemo_wrapper__", False) is False


def test_launcher_wraps_once_across_reruns():
    shell = L._shell()
    _check_wraps_once(shell, shell.get_preview_page_vm)


def test_launcher_call_counter_counts_each_run_once(monkeypatch):
    shell = L._shell()
    L.install()
    L.install()
    shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD)
    assert L.get_state(shell)["calls"] == 1, "巢狀包會讓一次呼叫計兩次"


def _check_forwards(shell, monkeypatch):
    seen = []
    real = _default_vm

    def rec(page_id, scenario_id, *a, **kw):
        seen.append((page_id, scenario_id, a, kw))
        return real(page_id, scenario_id, **kw)
    monkeypatch.setattr(shell, "get_preview_page_vm", rec)
    monkeypatch.setenv(L.ENV_CASE, "R1")
    L.install()
    shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD, mode="curated", account="signed_out", top_n=3)
    assert seen == [(P4_HOLD, SCENARIO_COLD, (), {"mode": "curated", "account": "signed_out", "top_n": 3})]


def test_launcher_forwards_mode_and_account(monkeypatch):
    _check_forwards(L._shell(), monkeypatch)


def test_uninstall_restores():
    shell = L._shell()
    orig, css = shell.get_preview_page_vm, shell.CSS
    L.install()
    assert shell.get_preview_page_vm is not orig
    L.uninstall()
    assert shell.get_preview_page_vm is orig and shell.CSS is css
    assert not any(hasattr(shell, a) for a in (L.ORIG_ATTR, L.CSS_ATTR, L.STATE_ATTR))
    L.uninstall()                                                   # 可重複呼叫


def test_mutation_nested_wrapping_turns_red(monkeypatch):
    shell = L._shell()
    orig = shell.get_preview_page_vm

    def nested_install():
        shell.get_preview_page_vm = L._make_wrapper(shell.get_preview_page_vm, shell)
    monkeypatch.setattr(L, "install", nested_install)
    with pytest.raises(AssertionError):
        _check_wraps_once(shell, orig)
    shell.get_preview_page_vm = orig                                # 還原（autouse 另會 uninstall）


def test_mutation_not_forwarding_mode_account_turns_red(monkeypatch):
    def bad_make(orig, shell):
        def w(page_id, scenario_id, *a, **kw):
            return orig(page_id, scenario_id)                       # 丟掉 mode／account／top_n
        w.__obdemo_wrapper__ = True
        return w
    monkeypatch.setattr(L, "_make_wrapper", bad_make)
    with pytest.raises(AssertionError):
        _check_forwards(L._shell(), monkeypatch)


def test_mutation_uninstall_noop_turns_red(monkeypatch):
    shell = L._shell()
    orig = shell.get_preview_page_vm
    L.install()
    real_uninstall = L.uninstall
    monkeypatch.setattr(L, "uninstall", lambda: None)
    L.uninstall()
    assert shell.get_preview_page_vm is not orig, "no-op uninstall 後仍被包（此為突變；正式 uninstall 必須還原）"
    real_uninstall()
    assert shell.get_preview_page_vm is orig


def test_wrapper_injects_only_for_hold_cold_fake_with_case(monkeypatch):
    shell = L._shell()
    L.install()
    for page in PAGE_IDS:                                           # 無 env：一律不注入
        for sc in SCENARIO_IDS:
            assert shell.get_preview_page_vm(page, sc) == _default_vm(page, sc)
    monkeypatch.setenv(L.ENV_CASE, "L1")
    for page in PAGE_IDS:
        for sc in SCENARIO_IDS:
            got, default = shell.get_preview_page_vm(page, sc), _default_vm(page, sc)
            if page == P4_HOLD and sc == SCENARIO_COLD:
                assert got != default
                restored = dataclasses.replace(got, context=dataclasses.replace(got.context, sections=default.context.sections))
                assert restored == default, "只能換 onebrain 區塊，其餘 VM 不得變"
                ob = [s for s in got.context.sections if s.section_id == "onebrain" and s.level == "L1"]
                assert len(ob) == 1 and len(ob[0].fields) == ROW_COUNTS["L1"]
            else:
                assert got == default, f"{page}/{sc} 不應被注入"


def test_real_feed_function_is_never_wrapped():
    shell = L._shell()
    real_fn = shell.get_real_page_vm
    L.install()
    assert shell.get_real_page_vm is real_fn and getattr(real_fn, "__obdemo_wrapper__", False) is False


def test_unknown_case_env_raises(monkeypatch):
    monkeypatch.setenv(L.ENV_CASE, "ZZ")
    with pytest.raises(ValueError):
        L.selected_case()
    shell = L._shell()
    L.install()
    with pytest.raises(ValueError):
        shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD)
    monkeypatch.setenv(L.ENV_CASE, "")
    assert L.selected_case() is None
    monkeypatch.delenv(L.ENV_CASE)
    assert L.selected_case() is None


def test_failclosed_env_without_case_does_not_inject(monkeypatch):
    shell = L._shell()
    L.install()
    monkeypatch.setenv(L.ENV_FAILCLOSED, "1")
    assert shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD) == _default_vm()


def test_failclosed_env_injects_fixed_rows(monkeypatch):
    shell = L._shell()
    L.install()
    monkeypatch.setenv(L.ENV_CASE, "L3")
    monkeypatch.setenv(L.ENV_FAILCLOSED, "1")
    vm = shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD)
    ob = next(s for s in vm.context.sections if s.section_id == "onebrain")
    _check_failclosed(ob)
    assert L.get_state(shell)["failclosed"] is True and L.get_state(shell)["injected"] is True


def _vm_with_sections(sections):
    d = _default_vm()
    return dataclasses.replace(d, context=dataclasses.replace(d.context, sections=tuple(sections)))


def test_injection_point_missing_raises(monkeypatch):
    default = _default_vm()
    secs = default.context.sections
    assert len([s for s in secs if s.section_id == "onebrain" and s.level == "L1"]) == 1
    sec = VM.build_section(demo.build_case_block("R1"))
    ob = next(s for s in secs if s.section_id == "onebrain")
    bad = {
        "missing": tuple(s for s in secs if s.section_id != "onebrain"),
        "duplicate": secs + (ob,),
        "wrong_level": tuple(dataclasses.replace(s, level="L2") if s.section_id == "onebrain" else s for s in secs),
    }
    for name, sections in bad.items():
        with pytest.raises(L.InjectionPointMissing, match="onebrain"):
            L.inject_section(_vm_with_sections(sections), sec)
    # 經 wrapper：同樣 raise，不被吞掉
    shell = L._shell()
    monkeypatch.setattr(shell, "get_preview_page_vm", lambda *a, **k: _vm_with_sections(bad["missing"]))
    monkeypatch.setenv(L.ENV_CASE, "R1")
    L.install()
    with pytest.raises(L.InjectionPointMissing):
        shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD)


def test_preview_css_only_with_env_and_restored(monkeypatch):
    shell = L._shell()
    base = shell.CSS
    assert "PREVIEW-ONLY" not in base
    L.install()
    assert shell.CSS == base
    monkeypatch.setenv(L.ENV_PREVIEW_CSS, "1")
    L.install()
    L.install()
    assert shell.CSS == L.with_preview_css(base) and shell.CSS.count("PREVIEW-ONLY") == 1
    assert shell.CSS.count("<style>") == shell.CSS.count("</style>") == base.count("<style>")
    assert shell.CSS.rstrip().endswith("</style>"), "預覽規則必須在 <style> 之內（附加在其後會變成可見文字）"
    assert L.PREVIEW_CSS in shell.CSS[:shell.CSS.rfind("</style>")]
    assert "非現況、非 baseline、非 DEC-137" in L.PREVIEW_CSS and "display:block" in L.PREVIEW_CSS
    monkeypatch.delenv(L.ENV_PREVIEW_CSS)
    L.install()
    assert shell.CSS == base
    monkeypatch.setenv(L.ENV_PREVIEW_CSS, "1")
    L.install()
    L.uninstall()
    assert shell.CSS is base


def test_with_preview_css_requires_style_block():
    with pytest.raises(RuntimeError):
        L.with_preview_css("body{}")
    out = L.with_preview_css("<style>a{}</style>\n")
    assert out == "<style>a{}" + L.PREVIEW_CSS + "</style>\n"


def test_seal_network_rejects_non_loopback_and_counts(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(socket.socket, "connect", lambda self, a: calls.append(("connect", a)))
    monkeypatch.setattr(socket.socket, "connect_ex", lambda self, a: calls.append(("ex", a)) or 0)
    monkeypatch.setattr(socket, "create_connection", lambda addr, *a, **k: calls.append(("cc", addr)))
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: calls.append(("gai", host)) or [])
    log = tmp_path / "seal.jsonl"
    state = L.seal_network(str(log))
    try:
        assert L.seal_network(str(log)) is state, "冪等"
        with socket.socket() as s:
            with pytest.raises(ConnectionRefusedError):
                s.connect(("example.com", 443))
            assert s.connect_ex(("203.0.113.7", 80)) == 111
            s.connect(("127.0.0.1", 8501))
        with pytest.raises(ConnectionRefusedError):
            socket.create_connection(("example.com", 443))
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("example.com", 443)
        socket.create_connection(("localhost", 8501))
        socket.getaddrinfo("127.0.0.1", 8501)
        assert calls == [("connect", ("127.0.0.1", 8501)), ("cc", ("localhost", 8501)), ("gai", "127.0.0.1")]
        assert L.seal_rejected_count() == 4
        lines = log.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 4 and "example.com" in lines[0]
    finally:
        L.unseal_network()
    assert L.seal_rejected_count() == 0 and not hasattr(socket, L.SEAL_ATTR)


# ── AST 守衛（launcher／mapper：無網路／時鐘／chdir）─────────────────────
_FORBIDDEN_IMPORTS = {"requests", "urllib", "urllib3", "http", "httpx", "aiohttp", "subprocess", "ssl", "ftplib", "smtplib",
                      "websocket", "websockets"}
_FORBIDDEN_CALLS = {"os.chdir", "chdir", "time.time", "time.sleep", "time.monotonic", "time.perf_counter", "datetime.now",
                    "datetime.utcnow", "datetime.today", "date.today", "datetime.datetime.now", "datetime.datetime.utcnow",
                    "os.system", "os.popen"}
_FORBIDDEN_ATTR_CALLS = {"connect", "connect_ex", "create_connection", "getaddrinfo", "getnameinfo", "gethostbyname", "urlopen", "sendto"}


def _dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _ast_violations(source: str) -> list[str]:
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            out += [f"import {a.name}" for a in n.names if a.name.split(".")[0] in _FORBIDDEN_IMPORTS]
        elif isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in _FORBIDDEN_IMPORTS:
            out.append(f"from {n.module} import …")
        elif isinstance(n, ast.Call):
            name = _dotted(n.func)
            if name in _FORBIDDEN_CALLS:
                out.append(f"call {name}")
            if isinstance(n.func, ast.Attribute) and n.func.attr in _FORBIDDEN_ATTR_CALLS:
                out.append(f"call .{n.func.attr}()")
    return out


def test_launcher_ast_guard():
    assert _ast_violations(LAUNCHER_PATH.read_text(encoding="utf-8")) == []
    assert _ast_violations(MAPPER_PATH.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("bad", ["import os\nos.chdir('/')", "import requests", "from urllib.request import urlopen",
                                 "import time\ntime.sleep(1)", "import datetime\ndatetime.datetime.now()",
                                 "import socket\ns=socket.socket()\ns.connect(('x',1))",
                                 "import socket\nsocket.getaddrinfo('x',1)", "import subprocess"])
def test_ast_guard_has_teeth(bad):
    assert _ast_violations(bad) != []


def test_no_production_file_imports_mapper_or_launcher(tmp_path):
    names = ("onebrain_holdings_ui2_demo", "onebrain_hold_demo")

    def scan(roots, files=()):
        hits = []
        paths = [p for r in roots for p in pathlib.Path(r).rglob("*.py")] + list(files)
        for p in paths:
            text = p.read_text(encoding="utf-8")
            hits += [f"{p.name}:{n}" for n in names if n in text]
        return hits
    assert scan([ROOT / "src", ROOT / "shared", ROOT / "scripts"], sorted(ROOT.glob("app*.py"))) == []
    bad = tmp_path / "prod.py"
    bad.write_text("from tests.onebrain_holdings_ui2_demo_vm import build_section\n", encoding="utf-8")
    assert scan([tmp_path]) != []                                   # 掃描本身有牙


def test_a1_adds_no_production_import_of_new_modules_via_ast():
    """src／shared／app*.py 沒有任何 `import tests…`（A1 檔都在 tests/ 下，生產程式不得依賴 tests）。"""
    for p in [*(ROOT / "src").rglob("*.py"), *(ROOT / "shared").rglob("*.py"), *ROOT.glob("app*.py")]:
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            mod = (n.module if isinstance(n, ast.ImportFrom) else "") or ""
            names = [a.name for a in n.names] if isinstance(n, (ast.Import, ast.ImportFrom)) else []
            assert not (mod.split(".")[0] == "tests" or any(x.split(".")[0] == "tests" for x in names)), f"{p} import tests"


# ══════════════════════════════════════════════════════════════════════
# F. 證據判定器（純函式）teeth
# ══════════════════════════════════════════════════════════════════════
def _good_measure(case="R1", failclosed=False, vw=390, variant="baseline"):
    sec = _failclosed_section(case) if failclosed else VM.build_section(demo.build_case_block(case))
    rows = []
    for i, f in enumerate(sec.fields):
        j = isinstance(f.state, JudgementState)
        rows.append({"label": f.label, "value": f.value_text or "", "chip": f.status_text or "", "detail": f.detail or "",
                     "axis": "judgement" if j else "data", "state": "undeterminable" if j else "ok",
                     "top": 640.0 + 50 * i, "bottom": 680.0 + 50 * i, "left": 14.0, "right": 370.0, "width": 356.0, "height": 40.0})
    desktop = vw > 768
    text = " ".join(r["label"] + " " + r["value"] + " " + r["chip"] + " " + r["detail"] for r in rows)
    ti = None if failclosed else {"text": VM.test_info_text(case), "inside_slot": False, "top": 1700.0}
    return {"case": case, "failclosed": failclosed, "css_variant": variant, "viewport": {"name": "x", "w": vw, "h": 844},
            "slot": {"top": 611.0, "bottom": 611.0 + 50 * len(rows), "display": ("flex" if variant == "baseline" else "block") if desktop else "block",
                     "scroll_w": 360, "client_w": 360},
            "rows": rows, "slot_text": text, "page_text": text + (" " + ti["text"] if ti else ""),
            "hscroll": {"doc_sw": vw, "doc_cw": vw, "main_sw": vw, "main_cw": vw}, "truncated": [], "testinfo": ti,
            "elements": [{"q": q, "text": q + " t", "top": 100.0 + i * 40, "bottom": 130.0 + i * 40, "left": 14.0, "right": 370.0,
                          "width": 356.0, "height": 30.0} for i, q in enumerate(("q1", "q2", "q4"))],
            "title": {"top": 620.0}}


def _baseline_of(m):
    return [dict(e) for e in m["elements"]]


@pytest.mark.parametrize("case,fc,vw,variant", [(c, False, 390, "baseline") for c in CASE_IDS]
                         + [("R1", True, 390, "baseline"), ("L1", False, 1280, "baseline"), ("R1", False, 1440, "baseline"),
                            ("L2", False, 1280, "preview"), ("R1", True, 1440, "baseline")])
def test_viewport_evaluator_accepts_a_good_measurement(case, fc, vw, variant):
    m = _good_measure(case, fc, vw, variant)
    assert EV.failures(EV.evaluate_demo(m, _baseline_of(m))) == {}


def _mut(fn):
    def apply(m):
        fn(m)
        return m
    return apply


TEETH = {
    "slot_missing": (_mut(lambda m: m.update(slot=None)), "slot_rows"),
    "row_count_off": (_mut(lambda m: m["rows"].pop()), "slot_rows"),
    "doc_overflow": (_mut(lambda m: m["hscroll"].update(doc_sw=m["hscroll"]["doc_cw"] + 5)), "no_horizontal_overflow"),
    "main_overflow": (_mut(lambda m: m["hscroll"].update(main_sw=999)), "no_horizontal_overflow"),
    "slot_overflow": (_mut(lambda m: m["slot"].update(scroll_w=m["slot"]["client_w"] + 9)), "no_horizontal_overflow"),
    "truncated_text": (_mut(lambda m: m["truncated"].append({"why": "ellipsis 截斷", "text": "x"})), "no_truncated_text"),
    "disclosure_not_first": (_mut(lambda m: m["rows"].insert(0, m["rows"].pop(1))), "disclosure_first"),
    "disclosure_altered": (_mut(lambda m: m["rows"][0].update(value="示意")), "disclosure_first"),
    "digest_too_far": (_mut(lambda m: [m["rows"].insert(1, dict(m["rows"][1], label="說明")) for _ in range(3)]), "disclosure_first"),
    "testinfo_inside_slot": (_mut(lambda m: m["testinfo"].update(inside_slot=True)), "testinfo_outside_slot"),
    "testinfo_missing": (_mut(lambda m: m.update(testinfo=None)), "testinfo_outside_slot"),
    "testinfo_prefix": (_mut(lambda m: m["testinfo"].update(text="說明：x")), "testinfo_outside_slot"),
    "forbidden_footer_page": (_mut(lambda m: m.update(page_text=m["page_text"] + " 顯示＝規則式摘要；FakeProvider 草稿不採用")), "no_forbidden_text"),
    "forbidden_cross_page": (_mut(lambda m: m.update(slot_text=m["slot_text"] + " 與本頁其他 FAKE 數字無關")), "no_forbidden_text"),
    "ok_attr_on_judgement": (_mut(lambda m: [r.update(state="ok", axis="data") for r in m["rows"] if r["label"] == "持股判讀"]), "row_state_attrs"),
    "carrier_not_ok": (_mut(lambda m: m["rows"][-1].update(state="unavailable")), "row_state_attrs"),
    "label_off_whitelist": (_mut(lambda m: m["rows"][2].update(label="備註")), "row_state_attrs"),
    "source_altered": (_mut(lambda m: m["rows"][-2].update(value="FAKE 合成持股快照")), "source_asof_rows"),
    "asof_missing_text": (_mut(lambda m: m["rows"][-1].update(value=TEXT_ASOF_MISSING)), "source_asof_rows"),
    "first_screen_shifted": (_mut(lambda m: m["elements"][1].update(top=m["elements"][1]["top"] + 0.6)), "first_screen_equals_nodemo"),
    "first_screen_text": (_mut(lambda m: m["elements"][0].update(text="changed")), "first_screen_equals_nodemo"),
    "first_screen_dropped": (_mut(lambda m: m["elements"].pop()), "first_screen_equals_nodemo"),
}


@pytest.mark.parametrize("name", list(TEETH))
def test_viewport_evaluator_has_teeth(name):
    mutate, check = TEETH[name]
    m = _good_measure("R1", False, 390, "baseline")
    base = _baseline_of(m)
    mutate(m)
    f = EV.failures(EV.evaluate_demo(m, base))
    assert check in f, f"{name}：應紅在 {check}，實得 {list(f)}"


def test_first_screen_tolerance_boundary():
    m = _good_measure()
    base = _baseline_of(m)
    m["elements"][0]["top"] += 0.4
    assert EV.evaluate_demo(m, base)["first_screen_equals_nodemo"] == []
    m["elements"][0]["top"] += 0.2
    assert EV.evaluate_demo(m, base)["first_screen_equals_nodemo"] != []
    assert EV.evaluate_demo(m, None)["first_screen_equals_nodemo"] != [], "缺無注入對照也判紅"


def test_disclosure_first_check_teeth():
    m = _good_measure("L1")
    assert EV.evaluate_demo(m, _baseline_of(m))["disclosure_first"] == []
    for mut in (lambda x: x["rows"].insert(0, x["rows"].pop(2)),                       # 首列不是示意
                lambda x: x["rows"][0].update(label="持股判讀"),
                lambda x: x["rows"][0].update(value=DISCLOSURE + "。")):
        m = _good_measure("L1")
        mut(m)
        assert EV.evaluate_demo(m, _baseline_of(m))["disclosure_first"] != []
    m = _good_measure("R1", True)                                                      # fail-closed 不得有 Digest 句
    m["rows"].insert(2, dict(m["rows"][0], label="存股", value="x"))
    assert EV.evaluate_demo(m, _baseline_of(m))["disclosure_first"] != []


def test_l3_completeness_check_teeth():
    m = _good_measure("L3")
    assert EV.evaluate_demo(m, _baseline_of(m))["l3_no_completeness"] == []
    for word in ("完整", "正常", "安全", "OK", "🟢"):
        m = _good_measure("L3")
        m["slot_text"] += " " + word
        assert EV.evaluate_demo(m, _baseline_of(m))["l3_no_completeness"] != [], word
    m = _good_measure("L2")                                                            # 只對 L3 套用
    m["slot_text"] += " 完整"
    assert EV.evaluate_demo(m, _baseline_of(m))["l3_no_completeness"] == []


@pytest.mark.parametrize("vw,variant,display,ok", [(1280, "baseline", "flex", True), (1440, "baseline", "block", False),
                                                    (1280, "preview", "block", True), (1440, "preview", "flex", False),
                                                    (390, "baseline", "block", True), (390, "baseline", "flex", False)])
def test_layout_mode_check_teeth(vw, variant, display, ok):
    m = _good_measure("R1", False, vw, variant)
    m["slot"]["display"] = display
    assert (EV.evaluate_demo(m, _baseline_of(m))["layout_mode"] == []) is ok


def test_failclosed_shape_check_teeth():
    m = _good_measure("R1", True)
    assert EV.evaluate_demo(m, _baseline_of(m))["failclosed_shape"] == []
    m["rows"][2]["value"] = "示範鏈未通過檢查，未顯示任何系統句"
    assert EV.evaluate_demo(m, _baseline_of(m))["failclosed_shape"] != []
    m = _good_measure("R1", True)
    m["testinfo"] = {"text": TESTINFO_PREFIX + "x", "inside_slot": False}
    assert EV.evaluate_demo(m, _baseline_of(m))["testinfo_outside_slot"] != []


def test_fold_report_and_row_layout_are_measurements_not_gates():
    m = _good_measure("R1")
    fr = EV.fold_report(m)
    assert fr["fold"] == 844 - MV.NAV_MOBILE_H == 791 and isinstance(fr["slot_crosses_fold"], bool)
    assert EV.fold_report(_good_measure("R1", False, 1280)) is None
    m = _good_measure("R1", False, 1440)
    m["rows"][1]["top"] = m["rows"][0]["top"]
    lay = EV.row_layout(m)
    assert lay["rows_sharing_a_line"] >= 1 and lay["visual_lines"][0][:2] == ["示意", "持股判讀"]


def test_contrast_math_and_not_verified():
    assert abs(EV.contrast_ratio((255, 255, 255), (0, 0, 0)) - 21.0) < 1e-6
    assert EV.contrast_ratio((10, 20, 30), (10, 20, 30)) == pytest.approx(1.0)
    ok = {"fg": {"r": 255, "g": 255, "b": 255, "a": 1}, "opacity": 0.75, "bg": {"r": 14, "g": 17, "b": 23, "a": 1}, "bg_partial": False}
    assert EV.effective_contrast(ok) > EV.CONTRAST_MIN
    assert EV.effective_contrast({**ok, "bg": None}) is None, "量不到背景 ⇒ NOT VERIFIED"
    assert EV.effective_contrast({**ok, "bg_partial": True}) is None
    assert EV.effective_contrast(None) is None
    faint = {**ok, "opacity": 0.2}
    assert EV.effective_contrast(faint) < EV.CONTRAST_MIN, "對比判定有牙（低不透明度會紅）"


def _good_meta():
    return {"label": EV.LABEL, "tool": EV.TOOL, "git_sha": "a" * 40, "source_hash": "b" * 64,
            "a1_file_hashes": {f: "c" * 64 for f in EV.A1_FILES}, "generated_at": "2026-11-22T00:00:00+00:00",
            "streamlit_version": "1.59.2", "playwright_version": "1.65.2", "chromium_version": "157.0",
            "viewports": {"mobile_390": [390, 844]},
            "network_sealed": {"server_sealed": True, "server_rejected": 0, "context_aborted": 0, "context_sealed": True},
            "css_variant": "baseline", "case": "R1"}


def test_check_meta_requires_every_field():
    assert EV.check_meta(_good_meta()) == []
    for k in EV.META_REQUIRED:
        m = _good_meta()
        m.pop(k)
        assert EV.check_meta(m) != [], f"缺 {k} 必須判紅"
    for mut in (lambda m: m.update(label="DEC-137 正式"), lambda m: m.update(git_sha="abc123"), lambda m: m.update(css_variant="x"),
                lambda m: m["network_sealed"].pop("server_rejected"), lambda m: m["a1_file_hashes"].pop(EV.A1_FILES[0]),
                lambda m: m.update(git_sha=None)):
        m = _good_meta()
        mut(m)
        assert EV.check_meta(m) != []


def test_variant_dir_isolation():
    assert EV.variant_dir_ok({"css_variant": "baseline"}, "baseline_unmodified_css")
    assert not EV.variant_dir_ok({"css_variant": "preview"}, "baseline_unmodified_css")
    assert not EV.variant_dir_ok({"css_variant": "baseline"}, "supplementary_preview_css")
    assert EV.variant_dir_ok({"css_variant": "preview"}, "supplementary_preview_css")


def test_build_meta_has_real_values_without_a_browser():
    meta = EV.build_meta(ROOT, variant="baseline", case="R1", streamlit_version="x", chromium_version="y",
                         network={"server_rejected": 0, "context_aborted": 0, "server_rejected_hosts": [], "context_aborted_urls": []})
    # git_sha（無 .git 的環境）與 playwright_version（Fast lane 不裝 Playwright）可能合法為 None；其餘必填欄位都必須在
    assert [e for e in EV.check_meta(meta) if "git_sha" not in e and "playwright_version" not in e] == []
    assert sorted(meta["a1_file_hashes"]) == sorted(EV.A1_FILES) and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in meta["a1_file_hashes"].values())
    assert re.fullmatch(r"[0-9a-f]{64}", meta["source_hash"]) and meta["label"] == "tests-only／非 DEC-137 正式"
    assert meta["git_sha"] is None or re.fullmatch(r"[0-9a-f]{40}", meta["git_sha"])


def test_evidence_viewports_are_local_and_not_measure_viewport_VIEWPORTS():
    assert EV.VIEWPORTS == {"mobile_390": (390, 844), "desktop_1280": (1280, 900), "desktop_1440": (1440, 900)}
    assert EV.VIEWPORTS is not MV.VIEWPORTS
    tree = ast.parse(EVIDENCE_PATH.read_text(encoding="utf-8"))            # 只看程式碼（docstring／註解提到不算）
    refs = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "VIEWPORTS"]
    assert refs == [], "runner 不得引用 measure_viewport.VIEWPORTS（DEC-137 V1 會改它）"


def test_evidence_imports_playwright_lazily_only():
    tree = ast.parse(EVIDENCE_PATH.read_text(encoding="utf-8"))
    for n in tree.body:                                             # 只看模組頂層
        if isinstance(n, ast.Import):
            assert not any(a.name.split(".")[0] == "playwright" for a in n.names)
        if isinstance(n, ast.ImportFrom):
            assert (n.module or "").split(".")[0] != "playwright"
    assert "playwright" in EVIDENCE_PATH.read_text(encoding="utf-8")     # 函式內確有 import


def test_measure_viewport_api_surface():
    """DEC-137 V1（B 線）可能改 measure_viewport：本 runner 重用的介面若消失／改簽名，這裡先紅（而不是靜默壞掉）。"""
    sig = lambda fn: list(inspect.signature(fn).parameters)
    assert sig(MV.measure_state) == ["page", "vw", "vh"]
    assert sig(MV.evidence_meta) == ["repo", "chromium_version"]
    assert sig(MV._select_box) == ["page", "name", "option_label", "anchor"]
    assert sig(MV.click_nav) == ["page", "label"] and sig(MV._screenshot) == ["page", "path"]
    assert sig(MV._dev_url) == ["url"] and sig(MV.launch_chromium) == ["p"] and sig(MV._free_port) == []
    assert sig(MV.source_hash) == ["repo"] and sig(MV._git_head) == ["repo"] and sig(MV._streamlit_version) == ["python"]
    assert isinstance(MV.NAV_MOBILE_H, int) and callable(MV.evaluate)
    assert "elements" in inspect.getsource(MV.measure_state) or "_JS" in inspect.getsource(MV.measure_state)


# ══════════════════════════════════════════════════════════════════════
# G. 真 app_ui2.py 經 launcher 的 AppTest（slow）
# ══════════════════════════════════════════════════════════════════════
def _page_blob(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [t.value for t in at.text]
    parts += [e.value for e in (*at.error, *at.warning, *at.info, *at.success)]
    return htmllib.unescape("\n".join(parts))


def _visible(blob: str) -> str:
    """整頁 markdown 去 <style>／標籤後的可見字（供 hits_in）。"""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<style.*?</style>", " ", blob, flags=re.S))


def _slot(blob: str) -> str:
    i = blob.index('data-ui2-l1="onebrain"')
    return blob[i:blob.index('data-ui2-l1="hold_primary_slot"', i)]


def _slot_rows(blob: str):
    return [{"axis": a, "state": s, "label": lb, "value": v, "detail": d} for a, s, lb, v, _c, d in _ROW_RX.findall(_slot(blob))]


def _run_app(monkeypatch, *, case=None, failclosed=False, feed="fake", page=P4_HOLD, scenario=SCENARIO_COLD, dev=False):
    from streamlit.testing.v1 import AppTest
    for k in (L.ENV_CASE, L.ENV_FAILCLOSED, L.ENV_PREVIEW_CSS, L.ENV_SEAL):
        monkeypatch.delenv(k, raising=False)
    if case:
        monkeypatch.setenv(L.ENV_CASE, case)
    if failclosed:
        monkeypatch.setenv(L.ENV_FAILCLOSED, "1")
    at = AppTest.from_file(str(LAUNCHER_PATH), default_timeout=60)
    if dev:
        at.query_params["ui2_dev"] = "1"
    at.session_state["ui2_feed"], at.session_state["ui2_page"], at.session_state["ui2_scenario"] = feed, page, scenario
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _first_screen(at):
    return [m.value for m in at.markdown if "data-ui2-q=" in m.value]


@pytest.mark.slow
@pytest.mark.parametrize("cid", CASE_IDS)
def test_apptest_normal_case(monkeypatch, cid):
    at = _run_app(monkeypatch, case=cid)
    blob = _page_blob(at)
    rows = _slot_rows(blob)
    want = _expected_rows(cid)
    assert [(r["label"], r["value"] if r["axis"] == "data" else r["detail"]) for r in rows] == [(lb, t) for lb, _k, t in want]
    assert len(rows) == ROW_COUNTS[cid]
    assert [(r["axis"], r["state"]) for r in rows] == [("judgement", "undeterminable") if k == "J" else ("data", "ok") for _l, k, _t in want]
    for _k, t in _oracle(cid)[1]:
        assert t in blob, "Digest 原句須逐字在頁面"
    assert any(r["label"] == "說明" for r in rows) is (cid in ("R1", "R2", "R3", "L1"))
    assert any(r["label"] == "持股判讀" for r in rows) is (cid != "L3")
    assert FAILCLOSED_NOTE not in blob and "未顯示任何摘要句" not in blob, "正常案例不得出現 fail-closed 固定句"
    for w in NEVER_ANYWHERE:
        assert w not in blob, f"{cid}：整頁出現 {w}"
    assert P1.hits_in(_visible(blob)) == [], f"整頁工程詞彙 {P1.hits_in(_visible(blob))}"
    captions = [c.value for c in at.caption]
    assert captions.count(VM.test_info_text(cid)) == 1 and VM.test_info_text(cid) not in _slot(blob)
    assert set(at.session_state.filtered_state) <= {"ui2_account", "ui2_feed", "ui2_page", "ui2_scenario", "ui2_target_mode"}
    assert all(k.startswith("ui2_") for k in at.session_state.filtered_state)


@pytest.mark.slow
@pytest.mark.parametrize("cid", ("R1", "L2", "L3"))
def test_apptest_failclosed_case(monkeypatch, cid):
    at = _run_app(monkeypatch, case=cid, failclosed=True)
    blob = _page_blob(at)
    rows = _slot_rows(blob)
    assert [(r["label"], r["value"] if r["axis"] == "data" else r["detail"]) for r in rows] == [(lb, t) for lb, _k, t in _expected_failclosed_rows()]
    assert len(rows) == FAILCLOSED_ROWS
    for _k, t in _oracle(cid)[1]:
        assert t not in blob, "fail-closed 不得顯示任何 Digest 句"
    assert NOTE_D3 not in blob and FAILCLOSED_NOTE in blob and FAILCLOSED_FOOTNOTE in blob
    assert [c.value for c in at.caption if "測試輸入說明" in c.value] == [], "fail-closed 無槽外區塊"
    for w in NEVER_ANYWHERE:
        assert w not in blob
    assert demo.ASM.assemble_digest is ASM.assemble_digest and ASM.assemble_digest.__name__ != "_raise_assemble"


@pytest.mark.slow
def test_apptest_real_feed_never_gets_demo(monkeypatch):
    from tests.test_ui2_real_feed import _feed
    _feed(monkeypatch)
    at = _run_app(monkeypatch, case="R1", feed="real")
    blob = _page_blob(at)
    assert "示意：合成持股快照" not in blob and [c.value for c in at.caption if "測試輸入說明" in c.value] == []
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _slot(blob))).strip()
    assert DEFAULT_SLOT_TEXT in text and "持股判讀" not in text and "示意" not in text


@pytest.mark.slow
@pytest.mark.parametrize("scenario", [s for s in SCENARIO_IDS if s != SCENARIO_COLD])
def test_apptest_fake_non_cold_scenarios_unchanged(monkeypatch, scenario):
    with_env = _run_app(monkeypatch, case="R1", scenario=scenario)
    without = _run_app(monkeypatch, scenario=scenario)
    assert _slot(_page_blob(with_env)) == _slot(_page_blob(without))
    assert "示意：合成持股快照" not in _page_blob(with_env) and not [c for c in with_env.caption if "測試輸入說明" in c.value]


@pytest.mark.slow
def test_apptest_default_hold_slot_unchanged(monkeypatch):
    expected = htmllib.unescape(section_l1_html(next(s for s in _default_vm().context.sections if s.section_id == "onebrain")))
    for feed in ("fake",):
        at = _run_app(monkeypatch, feed=feed)
        slot = _slot(_page_blob(at))
        assert expected in slot and "示意：合成持股快照" not in slot
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", slot)).strip()
        assert DEFAULT_SLOT_TEXT in text
    from tests.test_ui2_real_feed import _feed
    _feed(monkeypatch)
    at = _run_app(monkeypatch, feed="real")
    assert "示意：合成持股快照" not in _page_blob(at)


@pytest.mark.slow
@pytest.mark.parametrize("cid", ("R1", "L1", "L3"))
def test_apptest_hold_cold_first_screen_equals_no_demo(monkeypatch, cid):
    base = _first_screen(_run_app(monkeypatch))
    assert base, "對照組必須有第一屏 data-ui2-q 區塊"
    assert _first_screen(_run_app(monkeypatch, case=cid)) == base
    assert _first_screen(_run_app(monkeypatch, case=cid, failclosed=True)) == base


@pytest.mark.slow
def test_apptest_wraps_once_across_streamlit_reruns(monkeypatch):
    from streamlit.testing.v1 import AppTest
    at = _run_app(monkeypatch, case="R1")
    shell = L._shell()
    assert _wrap_depth(shell.get_preview_page_vm) == 1 and L.get_state(shell)["calls"] == 1
    at.run(timeout=60)
    at.run(timeout=60)
    assert not at.exception and _wrap_depth(shell.get_preview_page_vm) == 1
    assert L.get_state(shell)["calls"] == 3, "每次 rerun 恰好呼叫一次（巢狀包會變 2×）"
    assert isinstance(at, AppTest)


@pytest.mark.slow
def test_no_wrapper_leak_after_apptest(monkeypatch):
    cwd = os.getcwd()
    _run_app(monkeypatch, case="L2")
    shell = L._shell()
    assert getattr(shell.get_preview_page_vm, "__obdemo_wrapper__", False) is True      # 執行期間確實有包
    assert os.getcwd() == cwd, "launcher 不得 chdir"
    L.uninstall()
    assert not getattr(shell.get_preview_page_vm, "__obdemo_wrapper__", False)
    assert not hasattr(shell, L.ORIG_ATTR)


@pytest.mark.slow
def test_apptest_default_blob_has_no_demo_words_without_env(monkeypatch):
    blob = _page_blob(_run_app(monkeypatch))
    for w in (*NEVER_ANYWHERE, "示意：合成持股快照", "測試輸入說明"):
        assert w not in blob


# ══════════════════════════════════════════════════════════════════════
# H. 真瀏覽器（ui2_browser；Playwright 於函式內 import；不在 CI browser lane 清單內）
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def _browser_ctx():
    from tests.ui2_browser import launch_or_fail, require_browser
    sp = require_browser()
    with sp() as p:
        b = launch_or_fail(p)
        yield p, b
        b.close()


@pytest.fixture(scope="module")
def _nodemo(_browser_ctx, tmp_path_factory):
    p, b = _browser_ctx
    out = tmp_path_factory.mktemp("obdemo_nodemo")
    return EV.run_server_case(p, b, ROOT, out, tag="NODEMO", env_extra={}, case="NODEMO", failclosed=False,
                              variant="baseline", python=sys.executable)


def _assert_browser_case(res, nodemo, case, failclosed, variant):
    base = {vp: m["elements"] for vp, m in nodemo["measures"].items()}
    for vp, m in res["measures"].items():
        fails = EV.failures(EV.evaluate_demo(m, base[vp]))
        assert fails == {}, f"{case}/{vp}：{fails}"
    net = res["network"]
    assert net["server_rejected"] == 0 and net["context_aborted"] == 0, net


@pytest.mark.ui2_browser
@pytest.mark.parametrize("case,failclosed", [("R1", False), ("L3", False), ("R1", True)])
def test_browser_baseline_css_evidence(_browser_ctx, _nodemo, tmp_path, case, failclosed):
    p, b = _browser_ctx
    env = {"UI2_OBDEMO_CASE": case, **({"UI2_OBDEMO_FAILCLOSED": "1"} if failclosed else {})}
    res = EV.run_server_case(p, b, ROOT, tmp_path, tag=f"{case}{'_FC' if failclosed else ''}", env_extra=env, case=case,
                             failclosed=failclosed, variant="baseline", python=sys.executable, real_control=(case == "R1" and not failclosed))
    _assert_browser_case(res, _nodemo, case, failclosed, "baseline")
    for vp in ("desktop_1280", "desktop_1440"):
        assert res["measures"][vp]["slot"]["display"] == "flex", "baseline 桌機 .ui2-m-onebrain 必須是 flex（未改 CSS）"
    if case == "R1" and not failclosed:
        assert all(v["no_demo_text"] for v in res["real_control"].values()), "Real 不得被注入"


@pytest.mark.ui2_browser
def test_browser_preview_css_variant_is_block_and_labelled(_browser_ctx, _nodemo, tmp_path):
    p, b = _browser_ctx
    res = EV.run_server_case(p, b, ROOT, tmp_path, tag="R1_preview", env_extra={"UI2_OBDEMO_CASE": "R1", "UI2_OBDEMO_PREVIEW_CSS": "1"},
                             case="R1", failclosed=False, variant="preview", python=sys.executable)
    _assert_browser_case(res, _nodemo, "R1", False, "preview")
    for vp in ("desktop_1280", "desktop_1440"):
        assert res["measures"][vp]["slot"]["display"] == "block"


def test_zz_shell_attributes_are_pristine_after_this_module():
    """本檔最後一個非 browser 測試：launcher／mutation 測試跑完後，shell 的三個被動過的名字必須是原物（防污染其他測試檔）。"""
    import src.services.ui2.preview_feed as PF
    import src.services.ui2.real_canonical as RC
    import src.ui2.shell.css as CSSM
    shell = L._shell()
    assert shell.get_preview_page_vm is PF.get_preview_page_vm
    assert shell.get_real_page_vm is RC.get_real_page_vm
    assert shell.CSS is CSSM.CSS
    assert not hasattr(socket, L.SEAL_ATTR)
