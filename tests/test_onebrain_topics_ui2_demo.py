"""C-OB-TOPICS-DEMO（tests-only，延續 #1268）— OneBrain 持股槽「可操作四主題」FAKE 預覽的測試與負控。

被測：`tests/onebrain_holdings_ui2_demo_topics.py`（主題內容＋SectionVM）、
`tests/ui2_viewport/onebrain_hold_demo_launcher.py`（四主題選擇器＋wrapper 依選擇換內容）。
⛔ 不測、不改 `src/**`、`app_ui2.py`、`shared/**`；零網路、零 Provider、零快取寫入。

分層（pytest.ini addopts＝`-m "not slow and not ui2_browser"`）：
  · 快測：主題×案例的列結構／逐字／上限檢查／證據可追溯／缺值降級／AST 守衛／mutation 負控。
  · `@pytest.mark.slow`：真 `app_ui2.py` 經 launcher 的 AppTest（點選四主題、內容真的換、Real 不受汙染、AI 未啟用仍可運作）。
  · `@pytest.mark.ui2_browser`：真瀏覽器 390／1280／1440（Playwright 於函式內才 import）。
    ⚠️ 不在 `pr-check.yml` 的 ui2-browser lane 清單內（不改 workflow）⇒ 原生 CI 覆蓋 NOT VERIFIED，只有本地封網驗證。

D7（字數口徑／徽章是否計入／作用域）**未裁**：本檔把「核心觀察 ≤3 句且各 <100 字、觀察重點每點 <25 字（Unicode 字元數；徽章另列不計入；
超限不截斷不丟句，改列該主題無法判定）」當作**預覽暫行口徑**測試，不是正式規則。
Oracle 獨立性：Digest 原句與引用 id 由本檔自行跑 `adapt_holdings_read → assemble → build_rule_summary` 取得；列規格與逐字文案為本檔本地常數。
"""
from __future__ import annotations

import ast
import dataclasses
import html as htmllib
import pathlib
import re
import socket
import sys

import pytest

import src.services.decision_digest_summary as S
import src.services.onebrain_holdings_adapter as A
import tests.onebrain_holdings_ui2_demo as demo
import tests.onebrain_holdings_ui2_demo_topics as T
import tests.onebrain_holdings_ui2_demo_vm as VM
import tests.test_onebrain_holdings_ui2_demo_view as LT
import tests.ui2_viewport.onebrain_hold_demo_evidence as EV
import tests.ui2_viewport.onebrain_hold_demo_launcher as L
from shared.decision_digest import Availability, DataStatus
from shared.decision_digest_grounding import Ref, build_ref_index
from shared.ui2_contract.models import FieldState, JudgementState
from shared.ui2_contract.pages import P4_DATA, P4_HOLD, SCENARIO_COLD, SCENARIO_LOADED
from src.ui2.views._page import section_l1_html

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════
# 本地 oracle 常數（刻意不讀 T 的同名常數）
# ══════════════════════════════════════════════════════════════════════
TOPICS = ("大盤", "產業前瞻", "持股健檢", "反方風險")
DEFAULT_TOPIC = "持股健檢"
CASE_IDS = ("R1", "R2", "R3", "L1", "L2", "L3")
KEY_TOPIC = "ui2_obdemo_topic"
KEY_CTRL = "ui2_obdemo_ctrl"
TITLE_PREFIX = "🤖 OneBrain 持股摘要｜"
DISCLOSURE = "示意：合成持股快照（FAKE）；非真實持股；非即時 OneBrain；非投資建議"
UNDET = "⬜ 無法判定"
D7_MARK = "預覽暫行口徑（D7 未裁，非正式）"
LENS = "LENS_MARKET_SURFACE_PENDING"
INDUSTRY_SENTENCE = "⬜ 產業趨勢：尚未定義，無法判定"
NOTE_D3 = "註：『尚無輸入』是現行摘要措辭，也可能代表讀取失敗、輸入異常或缺少組合鍵；請勿解讀為零持股。"
NOTE_TRIGGER = "（尚無輸入）"
CITED_CLAIM = "Digest 原句所引用的欄位"
HOLD_SOURCE = "來源 FAKE 合成持股快照（非真實持股）｜時點 無（FAKE 示意，沒有持股讀取時點）"
NONE_SOURCE = "來源 無（本主題沒有顯示任何來源資料）｜時點 無"
INDUSTRY_SOURCE = "來源 無（該句本身沒有來源、時點、狀態）｜時點 無"
RISK_FIXTURE_SOURCE = "來源 FAKE-SYN 合成反證（非 Digest 欄位）｜時點 見各列（FAKE 示意日）"
FIXTURE_CASES = ("L2",)
CORE_MAX_SENTENCES, CORE_LT_CODEPOINTS, POINT_LT_CODEPOINTS = 3, 100, 25
L_CORE, L_POINTS, L_SUP, L_CTR, L_GAP, L_SRC = "核心觀察", "觀察重點", "支持證據", "反面證據", "缺項", "來源時點"
LABELS = {"示意", "核心觀察", "持股判讀", "存股", "資本利得", "觀察重點", "支持證據", "反面證據", "缺項", "來源時點"}
#: 任何主題、任何案例、任何位置都不得出現
NEVER_ANYWHERE = ("顯示＝規則式摘要", "FakeProvider", "§C", "示範鏈", "與本頁其他 FAKE 數字無關", "is_complete")
#: 槽內禁字（「零持股」僅核定註記逐字許可）
BANNED = ("市場位階", "市場燈號", "市場健康度", "Risk Cap", "風險上限", "本期行動", "shadow_accepted", "grounding", "bull", "🟢",
          "72.5", "txt-", "完整", "正常", "安全", "中性", "空倉", "0 檔", "零持股", "續抱", "草稿", *A.ALL_REASONS)
MARKET_CONTENT_WORDS = ("bull", "🟢", "72.5", "市場位階", "市場燈號", "市場健康度")


@pytest.fixture(autouse=True)
def _always_uninstall(monkeypatch):
    monkeypatch.delenv(L.ENV_TOPICS, raising=False)             # 四主題為預設行為
    L.uninstall()
    yield
    L.uninstall()
    shell = L._shell()
    assert not any(hasattr(shell, a) for a in (L.ORIG_ATTR, L.CSS_ATTR, L.STATE_ATTR)), "launcher 哨兵洩漏"
    assert not hasattr(socket, L.SEAL_ATTR), "封網洩漏"


# ══════════════════════════════════════════════════════════════════════
# 獨立 oracle
# ══════════════════════════════════════════════════════════════════════
def _chain(cid):
    case = demo.CASES[cid]
    res = A.adapt_holdings_read(case.snapshot)
    a = demo.assemble(case, res.rows_for_digest())
    return a.digest, S.build_rule_summary(a.digest)


def _sentences(cid, *keys):
    _d, s = _chain(cid)
    lines = dict(s.lines)
    return tuple(x for k in keys for x in lines[k])


def _cited_refs(cid, *keys):
    _d, s = _chain(cid)
    out = []
    for sec in s.sections:
        if sec.key in keys:
            for sent in sec.sentences:
                for seg in sent.segments:
                    if isinstance(seg, Ref) and seg.ref_id not in out:
                        out.append(seg.ref_id)
    return out


def _holdings_sentences(cid):
    return _sentences(cid, "buy_and_hold", "capital_gain")


def _holdings_is_over_limit(cid):
    ss = _holdings_sentences(cid)
    return len(ss) > CORE_MAX_SENTENCES or any(len(x) >= CORE_LT_CODEPOINTS for x in ss)


def _ev_text(claim, ev_id, source, as_of, status):
    return f"{claim}｜證據編號 {ev_id}｜來源 {source}｜時點 {as_of}｜狀態 {status}"


def _sec(topic, cid, fc=False):
    return T.build_topic_section(topic, cid, fail_closed=fc)


def _labels(sec):
    return [f.label for f in sec.fields]


def _text(f):
    return "\n".join(x for x in (f.value_text, f.status_text, f.detail) if x)


def _all_text(sec):
    return "\n".join([sec.title, *(_text(f) for f in sec.fields)])


def _rows(sec, label):
    return [f for f in sec.fields if f.label == label]


def _gap_oracle(cid):
    d, _s = _chain(cid)
    h = d.holdings
    gaps = []
    if h.missing_reason is not None:
        gaps.append("持股資料：" + {"no_input": "尚無輸入"}[h.missing_reason.value])
    if h.unkeyed_count > 0:
        gaps.append(f"缺少投資組合鍵 {h.unkeyed_count} 檔")
    n_unset = sum(1 for e in h.entries if e.strategy.value == "未分類")
    if n_unset > 0:
        gaps.append(f"尚未設定投資策略分類 {n_unset} 檔")
    return "；".join(gaps)


def _expected_labels(topic, cid, fc=False):
    base = ["示意", L_CORE, L_POINTS, L_GAP, L_SRC]
    if fc or topic == "大盤":
        return base
    if topic == "產業前瞻":
        return ["示意", L_CORE, L_POINTS, L_SUP, L_GAP, L_SRC]
    if topic == "持股健檢":
        if _holdings_is_over_limit(cid):
            return base
        d, _s = _chain(cid)
        mid = ["持股判讀"] if d.holdings.availability is not Availability.AVAILABLE else []
        n_sup = len(_cited_refs(cid, "buy_and_hold", "capital_gain"))
        return ["示意", *mid, *("存股" for _ in dict(_chain(cid)[1].lines)["buy_and_hold"]),
                *("資本利得" for _ in dict(_chain(cid)[1].lines)["capital_gain"]), L_POINTS, *([L_SUP] * n_sup), L_GAP, L_SRC]
    if cid in FIXTURE_CASES:
        return ["示意", L_CORE, L_POINTS, L_CTR, L_CTR, L_GAP, L_SRC]
    return base


def _core_sentences(sec):
    """槽內「核心觀察」句：核心觀察列（D 型）的文字，或持股健檢的 存股／資本利得 句。"""
    out = []
    for f in sec.fields:
        if f.label in ("存股", "資本利得") or (f.label == L_CORE and not isinstance(f.state, JudgementState)):
            out.append(f.value_text)
    return out


def _check_section_invariants(topic, cid, fc, sec):
    """所有主題×案例共同的不變量（也是 mutation 負控的偵測器）。"""
    assert sec.section_id == "onebrain" and sec.level == "L1" and sec.title == TITLE_PREFIX + topic
    assert _labels(sec) == _expected_labels(topic, cid, fc), f"{topic}/{cid}/fc={fc} 列序不符：{_labels(sec)}"
    assert set(_labels(sec)) <= LABELS
    assert sec.fields[0].label == "示意" and sec.fields[0].value_text == DISCLOSURE, "首列必須是逐字的示意揭露"
    text = _all_text(sec)
    for w in NEVER_ANYWHERE:
        assert w not in text, f"出現 {w}"
    scan = text.replace(NOTE_D3, "")
    for w in BANNED:
        assert w not in scan, f"{topic}/{cid} 出現禁字 {w}"
    core = _core_sentences(sec)
    assert len(core) <= CORE_MAX_SENTENCES, "核心觀察超過 3 句"
    assert all(len(x) < CORE_LT_CODEPOINTS for x in core), "核心觀察某句 ≥100 字元"
    pts = _rows(sec, L_POINTS)
    assert len(pts) == 1 and pts[0].value_text and D7_MARK in (pts[0].detail or ""), "觀察重點列必須單列且標示預覽暫行口徑"
    listed = re.findall(r"[①②③]([^｜①②③]*)", pts[0].value_text)
    assert len(listed) <= 3 and all(len(x.strip()) < POINT_LT_CODEPOINTS for x in listed), "觀察重點超過 3 點或某點 ≥25 字元"
    for f in sec.fields:
        if isinstance(f.state, JudgementState):
            assert f.state is JudgementState.UNDETERMINABLE and f.status_text == UNDET and f.value_text is None
    # 缺值不補 0：任何列都不得出現單獨的 0／0%／N/A 之類
    assert not re.search(r"(?<![\d.])0(?:\.0+)?%?(?![\d.])", text), f"疑似補 0：{text}"
    # 支持／反面證據列：每列都有證據編號／來源／時點／狀態
    for f in (*_rows(sec, L_SUP), *_rows(sec, L_CTR)):
        for k in ("證據編號 ", "｜來源 ", "｜時點 ", "｜狀態 "):
            assert k in f.value_text, f"證據列缺 {k}：{f.value_text}"
    # 單一來源時點列
    assert len(_rows(sec, L_SRC)) == 1 and not any(f.label in ("來源", "時點") for f in sec.fields)
    # 行內：不得用 expander；DOM 以 section_l1_html 檢查
    html = section_l1_html(sec)
    assert "<details" not in html and "stExpander" not in html


def _check_all_topics():
    for topic in TOPICS:
        for cid in CASE_IDS:
            _check_section_invariants(topic, cid, False, _sec(topic, cid))
            _check_section_invariants(topic, cid, True, _sec(topic, cid, True))
    for cid in CASE_IDS:                                           # 四主題內容兩兩不同
        bodies = [tuple(_text(f) for f in _sec(t, cid).fields[1:]) for t in TOPICS]
        assert len(set(bodies)) == 4, f"{cid}：四主題內容必須兩兩不同"
    _check_counter_rules()


def _check_counter_rules():
    for cid in CASE_IDS:
        sec = _sec("反方風險", cid)
        ctr = _rows(sec, L_CTR)
        if cid in FIXTURE_CASES:
            assert len(ctr) == 2
            assert all("fake-syn:" in f.value_text and "FAKE-SYN 合成反證" in f.value_text and "非 Digest 欄位" in f.value_text for f in ctr)
            assert [f.state for f in ctr] == [FieldState.OK, FieldState.STALE]
            assert "資料已過期" in ctr[1].value_text and ctr[1].status_text.startswith("⚠")
            assert "資料已過期" not in ctr[0].value_text and ctr[0].status_text is None
            assert all(re.search(r"時點 FAKE", f.value_text) for f in ctr)
        else:
            assert ctr == [], f"{cid}：沒有反證輸入時反方風險不得有反面證據列"
            core = _rows(sec, L_CORE)[0]
            assert core.state is JudgementState.UNDETERMINABLE and "無反證輸入" in core.detail
        for other in ("大盤", "產業前瞻", "持股健檢"):
            assert _rows(_sec(other, cid), L_CTR) == [], f"{other}/{cid} 不得有反面證據列"


# ══════════════════════════════════════════════════════════════════════
# A. 主題與案例矩陣（快測）
# ══════════════════════════════════════════════════════════════════════
def test_topics_order_default_and_key():
    assert T.TOPICS == TOPICS and T.DEFAULT_TOPIC == DEFAULT_TOPIC and T.KEY_TOPIC == KEY_TOPIC
    assert KEY_TOPIC.startswith("ui2_obdemo_") and len(set(TOPICS)) == 4


@pytest.mark.parametrize("topic", TOPICS)
@pytest.mark.parametrize("cid", CASE_IDS)
def test_matrix_invariants_normal_and_failclosed(topic, cid):
    _check_section_invariants(topic, cid, False, _sec(topic, cid))
    _check_section_invariants(topic, cid, True, _sec(topic, cid, True))


def test_check_all_is_green_on_the_unmutated_tree():
    _check_all_topics()


@pytest.mark.parametrize("cid", CASE_IDS)
def test_four_topics_have_pairwise_different_content(cid):
    bodies = {t: tuple(_text(f) for f in _sec(t, cid).fields[1:]) for t in TOPICS}
    assert len(set(bodies.values())) == 4
    assert len({_sec(t, cid).title for t in TOPICS}) == 4


@pytest.mark.parametrize("cid", CASE_IDS)
def test_market_is_always_unavailable_with_no_content_sentence(cid):
    sec = _sec("大盤", cid)
    core = _rows(sec, L_CORE)
    assert len(core) == 1 and core[0].state is JudgementState.UNDETERMINABLE
    assert LENS in core[0].detail and "暫定名稱" in core[0].detail and "Copy Gate" in core[0].detail
    assert _core_sentences(sec) == []
    text = _all_text(sec)
    assert not any(w in text for w in MARKET_CONTENT_WORDS)
    assert _rows(sec, L_GAP)[0].value_text == "大盤對外句型尚未裁示；支持證據：無｜反面證據：無"
    assert _rows(sec, L_SRC)[0].value_text == NONE_SOURCE


@pytest.mark.parametrize("cid", CASE_IDS)
def test_industry_shows_only_the_existing_undefined_sentence_with_no_provenance(cid):
    assert _sentences(cid, "industry") == (INDUSTRY_SENTENCE,)
    sec = _sec("產業前瞻", cid)
    core = _rows(sec, L_CORE)
    assert [f.value_text for f in core] == [INDUSTRY_SENTENCE]
    assert [f.value_text for f in _rows(sec, L_SUP)] == [_ev_text(CITED_CLAIM, "section:industry", "無", "無", "無")]
    assert _cited_refs(cid, "industry") == ["section:industry"]
    assert _rows(sec, L_SRC)[0].value_text == INDUSTRY_SOURCE
    assert _rows(sec, L_GAP)[0].value_text == "產業趨勢尚未定義；反面證據：無"


@pytest.mark.parametrize("cid", [c for c in CASE_IDS if c not in ("L1", "L2")])
def test_holdings_verbatim_sentences_and_cited_evidence(cid):
    sec = _sec("持股健檢", cid)
    want = [("存股" if k == "buy_and_hold" else "資本利得", t) for k in ("buy_and_hold", "capital_gain") for t in _sentences(cid, k)]
    got = [(f.label, f.value_text) for f in sec.fields if f.label in ("存股", "資本利得")]
    assert got == want, "Digest 原句必須逐字、依原順序"
    sup = [f.value_text for f in _rows(sec, L_SUP)]
    assert sup == [_ev_text(CITED_CLAIM, rid, "無", "無", "無") for rid in _cited_refs(cid, "buy_and_hold", "capital_gain")]
    d, _s = _chain(cid)
    idx = build_ref_index(d)
    for rid in _cited_refs(cid, "buy_and_hold", "capital_gain"):
        assert rid in idx, "證據編號必須能追到 Digest 原欄位"
    assert _rows(sec, L_SRC)[0].value_text == HOLD_SOURCE
    gap = _rows(sec, L_GAP)[0]
    assert gap.value_text == _gap_oracle(cid)
    assert (gap.detail == NOTE_D3) is any(NOTE_TRIGGER in t for _l, t in want)
    assert ("持股判讀" in _labels(sec)) is (d.holdings.availability is not Availability.AVAILABLE)
    judge = _rows(sec, "持股判讀")
    assert all(f.detail == "此列由畫面依持股狀態推導，非系統摘要原句" for f in judge)


@pytest.mark.parametrize("cid", ("L1", "L2"))
def test_holdings_over_limit_degrades_to_undeterminable_with_badge_and_no_dropped_sentence(cid):
    assert len(_holdings_sentences(cid)) == 4
    sec = _sec("持股健檢", cid)
    assert _labels(sec) == ["示意", L_CORE, L_POINTS, L_GAP, L_SRC]
    core = sec.fields[1]
    assert core.state is JudgementState.UNDETERMINABLE and D7_MARK in core.detail and "不截斷" in core.detail
    assert not any(f.label in ("存股", "資本利得") for f in sec.fields), "超限不得顯示被截斷的句子"
    assert _rows(sec, L_SUP) == []
    assert _rows(sec, L_GAP)[0].value_text == _gap_oracle(cid)


def test_counter_fixture_only_in_declared_cases_and_not_derived_from_digest():
    assert tuple(T.COUNTER_FIXTURE) == FIXTURE_CASES
    for cid in CASE_IDS:
        d, _s = _chain(cid)
        idx = build_ref_index(d)
        for ev in T.counter_fixture(cid):
            assert ev.ev_id.startswith("fake-syn:") and ev.ev_id not in idx, "合成反證不得冒充 Digest 欄位"
            assert ev.source.startswith("FAKE") and ev.as_of.startswith("FAKE")
            assert ev.fixture is True
    assert T.counter_fixture("R1") == () and T.counter_fixture("L3") == ()


def test_risk_never_derives_counter_from_risk_cap_or_digest_fields(monkeypatch):
    monkeypatch.setattr(T, "COUNTER_FIXTURE", {})
    for cid in CASE_IDS:
        sec = _sec("反方風險", cid)
        assert _rows(sec, L_CTR) == []
        assert sec.fields[1].state is JudgementState.UNDETERMINABLE
        text = _all_text(sec)
        assert "action_fact" not in text and "risk_cap" not in text and "section:" not in text


# ══════════════════════════════════════════════════════════════════════
# B. 預覽暫行口徑與證據列的單元行為
# ══════════════════════════════════════════════════════════════════════
def test_check_core_boundaries():
    assert T.check_core(["字" * 99] * 3) is None
    assert "100" in (T.check_core(["字" * 100]) or "")
    assert "3" in (T.check_core(["字"] * 4) or "")
    assert T.check_core([]) is None
    assert T.check_core(["字" * 99, "字" * 100]) is not None


def test_points_boundary_and_exclusion_is_declared_not_truncated():
    pts = T.select_points(["a" * 24, "b" * 25, "c" * 10, "d" * 5, "e" * 5])
    assert pts.listed == ("a" * 24, "c" * 10, "d" * 5) and pts.excluded == 2
    pts2 = T.select_points(["x" * 30])
    assert pts2.listed == () and pts2.excluded == 1
    assert T.select_points([]).listed == () and T.select_points([]).excluded == 0


def _ev(status, **kw):
    base = dict(kind="support", ev_id="fake-syn:x:1", claim="示意證據", source="FAKE 來源", as_of="FAKE 示意日 2026-10-26",
                status=status, fixture=True)
    base.update(kw)
    return T.Evidence(**base)


@pytest.mark.parametrize("status,state,mark", [(DataStatus.OK, FieldState.OK, "有資料"), (DataStatus.STALE, FieldState.STALE, "資料已過期"),
                                               (DataStatus.PROXY, FieldState.OK, "代理估算")])
def test_evidence_field_status_texts(status, state, mark):
    f = T.evidence_field(_ev(status))
    assert f.state is state and f.label == L_SUP
    assert f.value_text == _ev_text("示意證據", "fake-syn:x:1", "FAKE 來源", "FAKE 示意日 2026-10-26", mark)
    assert (f.status_text or "").startswith("⚠") is (status is DataStatus.STALE)


def test_evidence_field_missing_values_are_stated_as_none_not_zero():
    f = T.evidence_field(_ev(None, source=None, as_of=None))
    assert f.value_text == _ev_text("示意證據", "fake-syn:x:1", "無", "無", "無")
    m = T.evidence_field(_ev(DataStatus.MISSING, source=None, as_of=None))
    assert m.state is FieldState.MISSING and m.value_text is None and m.status_text.startswith("⬜ 資料")
    assert "無" in m.detail and not re.search(r"(?<![\d.])0(?![\d.])", m.detail)
    with pytest.raises(ValueError):
        T.evidence_field(_ev("ok"))                     # 不認得的狀態一律 raise，不猜


def test_unknown_topic_or_case_raises_not_silently_defaulted():
    with pytest.raises(ValueError):
        T.build_topic_section("不存在的主題", "R1", fail_closed=False)
    with pytest.raises(KeyError):
        T.build_topic_section("大盤", "ZZ", fail_closed=False)


def test_chain_failure_inside_topic_builder_degrades_and_logs(monkeypatch, caplog):
    def boom(*_a, **_k):
        raise RuntimeError("secret detail must not be logged")
    monkeypatch.setattr(T.demo.ASM, "assemble_digest", boom)
    with caplog.at_level("WARNING"):
        sec = _sec("持股健檢", "R1")
    _check_section_invariants("持股健檢", "R1", True, sec)
    assert any("RuntimeError" in r.getMessage() for r in caplog.records)
    assert not any("secret detail" in r.getMessage() for r in caplog.records)


def test_failclosed_all_four_topics_degrade_honestly():
    for topic in TOPICS:
        sec = _sec(topic, "L3", True)
        assert _labels(sec) == ["示意", L_CORE, L_POINTS, L_GAP, L_SRC]
        assert sec.fields[1].state is JudgementState.UNDETERMINABLE
        assert not any(f.label in ("存股", "資本利得", L_SUP, L_CTR) for f in sec.fields)
        if topic != "大盤":
            assert "示意內容未能產生" in _all_text(sec)


def test_test_info_text_is_the_existing_caption():
    for cid in CASE_IDS:
        assert T.test_info_text(cid) == VM.test_info_text(cid)


# ══════════════════════════════════════════════════════════════════════
# C. launcher（快測）
# ══════════════════════════════════════════════════════════════════════
def test_selected_topic_default_valid_and_unknown_raises():
    assert L.selected_topic({}) == DEFAULT_TOPIC
    assert L.selected_topic({KEY_TOPIC: "大盤"}) == "大盤"
    with pytest.raises(ValueError):
        L.selected_topic({KEY_TOPIC: "亂填"})


def test_topics_enabled_flag(monkeypatch):
    assert L.topics_enabled() is True
    for off in ("0", "false", "OFF"):
        monkeypatch.setenv(L.ENV_TOPICS, off)
        assert L.topics_enabled() is False
    monkeypatch.setenv(L.ENV_TOPICS, "1")
    assert L.topics_enabled() is True


def test_wrapper_injects_selected_topic_section_only_for_hold_cold_fake_with_case(monkeypatch):
    shell = L._shell()
    L.install()
    monkeypatch.setenv(L.ENV_CASE, "R1")
    monkeypatch.setattr(L, "selected_topic", lambda *a, **k: "反方風險")
    vm = shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD)
    ob = [s for s in vm.context.sections if s.section_id == "onebrain" and s.level == "L1"]
    assert len(ob) == 1 and ob[0].title == TITLE_PREFIX + "反方風險"
    assert L.get_state(shell)["topic"] == "反方風險" and L.get_state(shell)["injected"] is True
    other = shell.get_preview_page_vm(P4_HOLD, SCENARIO_LOADED)
    assert next(s for s in other.context.sections if s.section_id == "onebrain").title == "🤖 OneBrain 持股摘要"


def test_legacy_mode_env_zero_keeps_the_original_single_slot(monkeypatch):
    shell = L._shell()
    L.install()
    monkeypatch.setenv(L.ENV_CASE, "R1")
    monkeypatch.setenv(L.ENV_TOPICS, "0")
    vm = shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD)
    ob = next(s for s in vm.context.sections if s.section_id == "onebrain")
    assert ob == VM.build_section(demo.build_case_block("R1"))


def test_failclosed_env_injects_degraded_topic_section(monkeypatch):
    shell = L._shell()
    L.install()
    monkeypatch.setenv(L.ENV_CASE, "L3")
    monkeypatch.setenv(L.ENV_FAILCLOSED, "1")
    for topic in TOPICS:
        monkeypatch.setattr(L, "selected_topic", lambda *a, _t=topic, **k: _t)
        ob = next(s for s in shell.get_preview_page_vm(P4_HOLD, SCENARIO_COLD).context.sections if s.section_id == "onebrain")
        _check_section_invariants(topic, "L3", True, ob)
        assert L.get_state(shell)["failclosed"] is True


# ══════════════════════════════════════════════════════════════════════
# D. 零正式 LLM／零網路／Real 隔離（AST 守衛）
# ══════════════════════════════════════════════════════════════════════
_FORBIDDEN_IMPORTS = ("anthropic", "openai", "requests", "httpx", "aiohttp", "urllib.request", "http.client", "google.generativeai",
                      "shared.onebrain_provider", "src.services.onebrain_shadow", "src.services.onebrain_provider")
_TOPICS_PATH = ROOT / "tests" / "onebrain_holdings_ui2_demo_topics.py"


def _imports(source: str) -> set[str]:
    out = set()
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
            out |= {f"{n.module}.{a.name}" for a in n.names}
    return out


def _forbidden_hits(source: str) -> list[str]:
    hits = []
    for mod in _imports(source):
        if any(mod == f or mod.startswith(f + ".") for f in _FORBIDDEN_IMPORTS):
            hits.append(mod)
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Attribute) and n.attr in ("run_shadow", "post_gemini", "messages") and isinstance(n.ctx, ast.Load):
            hits.append("attr:" + n.attr)
    return hits


@pytest.mark.parametrize("path", [_TOPICS_PATH, ROOT / "tests" / "ui2_viewport" / "onebrain_hold_demo_launcher.py"])
def test_new_code_imports_no_provider_or_network_client(path):
    # launcher 經 demo 間接 import 既有 onebrain_shadow（#1268 既有、離線 FakeProvider），本守衛只看「新增程式碼自己」的直接 import：
    src = path.read_text(encoding="utf-8")
    hits = [h for h in _forbidden_hits(src) if h not in ("src.services.onebrain_shadow",) or path is _TOPICS_PATH]
    assert hits == [], f"{path.name} 直接 import 了禁用模組／呼叫：{hits}"


def test_forbidden_hits_has_teeth():
    assert _forbidden_hits("import anthropic")
    assert _forbidden_hits("from shared.onebrain_provider import X")
    assert _forbidden_hits("from src.services.onebrain_shadow import run_shadow")
    assert _forbidden_hits("import requests as r")
    assert _forbidden_hits("x.run_shadow(1)")
    assert _forbidden_hits("import json") == []


def test_topics_module_source_has_no_clock_network_or_secret_reads():
    src = _TOPICS_PATH.read_text(encoding="utf-8")
    for bad in ("os.environ", "st.secrets", "datetime.now", "time.time", "socket", "open(", "write_text", "to_parquet", "st.cache"):
        assert bad not in src, f"新模組不得含 {bad}（零時鐘／零 Secrets／零快取寫入）"


def test_no_production_file_imports_topics_module():
    needles = ("onebrain_holdings_ui2_demo_topics", "onebrain_topics_evidence")
    offenders = []
    for base in ("src", "shared", "scripts"):
        for p in (ROOT / base).rglob("*.py"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            if any(n in t for n in needles):
                offenders.append(str(p.relative_to(ROOT)))
    for p in ROOT.glob("app*.py"):
        if any(n in p.read_text(encoding="utf-8", errors="ignore") for n in needles):
            offenders.append(p.name)
    assert offenders == []


def test_repo_diff_scope_is_tests_only():
    import subprocess
    out = subprocess.run(["git", "diff", "--name-only", "origin/main...HEAD"], cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        pytest.skip("無 origin/main 可比對")
    files = [x for x in out.stdout.splitlines() if x]
    assert all(f.startswith("tests/") for f in files), f"出現 tests/ 以外的變更：{[f for f in files if not f.startswith('tests/')]}"


# ══════════════════════════════════════════════════════════════════════
# E. mutation 負控（monkeypatch；repo 內不留突變）
# ══════════════════════════════════════════════════════════════════════
def test_mutation_counter_fixture_for_every_case_turns_red(monkeypatch):
    fixture = T.COUNTER_FIXTURE["L2"]
    monkeypatch.setattr(T, "COUNTER_FIXTURE", {c: fixture for c in CASE_IDS})
    with pytest.raises(AssertionError):
        _check_all_topics()


def test_mutation_market_emits_content_sentence_turns_red(monkeypatch):
    real = T.build_topic_view

    def mutant(topic, case_id, *, fail_closed):
        v = real("產業前瞻" if topic == "大盤" else topic, case_id, fail_closed=fail_closed)
        return dataclasses.replace(v, topic=topic) if topic == "大盤" else v
    monkeypatch.setattr(T, "build_topic_view", mutant)
    with pytest.raises(AssertionError):
        _check_all_topics()


def test_mutation_core_limit_disabled_turns_red(monkeypatch):
    monkeypatch.setattr(T, "check_core", lambda _s: None)
    with pytest.raises(AssertionError):
        _check_all_topics()


def test_mutation_missing_value_filled_with_zero_turns_red(monkeypatch):
    real = T.evidence_field

    def mutant(ev):
        f = real(ev)
        return dataclasses.replace(f, value_text=f.value_text.replace("狀態 無", "狀態 0")) if f.value_text else f
    monkeypatch.setattr(T, "evidence_field", mutant)
    with pytest.raises(AssertionError):
        _check_all_topics()


def test_mutation_topic_content_identical_turns_red(monkeypatch):
    real = T.build_topic_section
    monkeypatch.setattr(T, "build_topic_section",
                        lambda topic, cid, *, fail_closed: dataclasses.replace(real("持股健檢", cid, fail_closed=fail_closed),
                                                                            title=TITLE_PREFIX + topic))
    with pytest.raises(AssertionError):
        _check_all_topics()


def test_mutation_expander_in_html_turns_red(monkeypatch):
    import tests.test_onebrain_topics_ui2_demo as me
    monkeypatch.setattr(me, "section_l1_html", lambda sec: "<details>" + section_l1_html(sec) + "</details>")
    with pytest.raises(AssertionError):
        _check_section_invariants("大盤", "R1", False, _sec("大盤", "R1"))


# ══════════════════════════════════════════════════════════════════════
# F. AppTest（slow）：真 app_ui2.py 經 launcher、點選四主題
# ══════════════════════════════════════════════════════════════════════
def _run_app(monkeypatch, *, case="R1", failclosed=False, feed="fake", page=P4_HOLD, scenario=SCENARIO_COLD, source=None):
    from streamlit.testing.v1 import AppTest
    for k in (L.ENV_CASE, L.ENV_FAILCLOSED, L.ENV_PREVIEW_CSS, L.ENV_SEAL, L.ENV_TOPICS):
        monkeypatch.delenv(k, raising=False)
    if case:
        monkeypatch.setenv(L.ENV_CASE, case)
    if failclosed:
        monkeypatch.setenv(L.ENV_FAILCLOSED, "1")
    path = str(ROOT / "tests" / "ui2_viewport" / "onebrain_hold_demo_launcher.py")
    at = AppTest.from_string(source, default_timeout=60) if source is not None else AppTest.from_file(path, default_timeout=60)
    at.session_state["ui2_feed"], at.session_state["ui2_page"], at.session_state["ui2_scenario"] = feed, page, scenario
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _pick(at, topic):
    at.radio(key=KEY_TOPIC).set_value(topic).run(timeout=60)
    assert not at.exception, at.exception
    return LT._page_blob(at)


def _slot_labels(blob):
    return [r["label"] for r in LT._slot_rows(blob)]


def _slot_title(blob):
    m = re.search(r'class="ui2-section-title">(.*?)</div>', LT._slot(blob))
    return htmllib.unescape(m.group(1)) if m else None


@pytest.mark.slow
def test_apptest_selector_defaults_and_each_topic_changes_the_slot(monkeypatch):
    at = _run_app(monkeypatch, case="R1")
    radio = at.radio(key=KEY_TOPIC)
    assert list(radio.options) == list(TOPICS) and radio.value == DEFAULT_TOPIC
    blob0 = LT._page_blob(at)
    assert _slot_title(blob0) == TITLE_PREFIX + DEFAULT_TOPIC and _slot_labels(blob0) == _expected_labels(DEFAULT_TOPIC, "R1")
    seen = {}
    for topic in (*TOPICS, DEFAULT_TOPIC):
        blob = _pick(at, topic)
        assert at.radio(key=KEY_TOPIC).value == topic
        assert _slot_title(blob) == TITLE_PREFIX + topic
        rows = LT._slot_rows(blob)
        assert [r["label"] for r in rows] == _expected_labels(topic, "R1")
        seen[topic] = tuple((r["label"], r["value"], r["detail"]) for r in rows)
        assert set(at.session_state.filtered_state) <= {"ui2_account", "ui2_feed", "ui2_page", "ui2_scenario", "ui2_target_mode", KEY_TOPIC}
    assert len(set(seen.values())) == 4 or len({v for k, v in seen.items()}) == 4, "四主題的實際 DOM 內容必須兩兩不同"
    at.run(timeout=60)                                          # 重跑：選擇保持
    assert at.radio(key=KEY_TOPIC).value == DEFAULT_TOPIC
    blob = _pick(at, "大盤")
    at.run(timeout=60)
    assert at.radio(key=KEY_TOPIC).value == "大盤" and _slot_title(LT._page_blob(at)) == TITLE_PREFIX + "大盤"


@pytest.mark.slow
@pytest.mark.parametrize("cid", CASE_IDS)
def test_apptest_every_case_every_topic_renders_the_expected_rows(monkeypatch, cid):
    at = _run_app(monkeypatch, case=cid)
    for topic in TOPICS:
        blob = _pick(at, topic)
        sec = _sec(topic, cid)
        rows = LT._slot_rows(blob)
        assert [r["label"] for r in rows] == _labels(sec)
        assert [(r["value"] if r["axis"] == "data" else r["detail"]) for r in rows] == [
            (f.value_text if not isinstance(f.state, JudgementState) else f.detail) for f in sec.fields]
        slot_text = re.sub(r"<[^>]+>", " ", LT._slot(blob))
        for w in NEVER_ANYWHERE:
            assert w not in blob
        assert not at.expander, "不得新增 expander（客戶第 4 點：證據行內呈現）"
        assert "stExpander" not in blob and "<details" not in LT._slot(blob)
        assert DISCLOSURE in slot_text
    assert len([c for c in at.caption if "測試輸入說明" in c.value]) == 1


@pytest.mark.slow
def test_apptest_l2_risk_topic_shows_inline_counter_evidence_and_stale_badge(monkeypatch):
    at = _run_app(monkeypatch, case="L2")
    blob = _pick(at, "反方風險")
    slot = htmllib.unescape(LT._slot(blob))
    assert slot.count("反面證據") == 2 and "fake-syn:counter:L2" in slot and "資料已過期" in slot and "⚠" in slot
    assert "FAKE-SYN 合成反證" in slot and "非 Digest 欄位" in slot
    other = _pick(_run_app(monkeypatch, case="L3"), "反方風險")
    assert "反面證據" not in LT._slot(other) and "無反證輸入" in htmllib.unescape(LT._slot(other))


@pytest.mark.slow
@pytest.mark.parametrize("topic", TOPICS)
def test_apptest_failclosed_every_topic_degrades(monkeypatch, topic):
    at = _run_app(monkeypatch, case="L3", failclosed=True)
    blob = _pick(at, topic)
    sec = _sec(topic, "L3", True)
    assert _slot_labels(blob) == _labels(sec) == ["示意", L_CORE, L_POINTS, L_GAP, L_SRC]
    for t in _holdings_sentences("L3"):
        assert t not in blob, "fail-closed 不得顯示任何 Digest 句"
    assert [c for c in at.caption if "測試輸入說明" in c.value] == [], "fail-closed 沒有槽外測試輸入說明"
    assert at.radio(key=KEY_TOPIC).value == topic, "fail-closed 仍可切換主題（每個主題都誠實降級）"


@pytest.mark.slow
def test_apptest_real_feed_has_no_selector_and_no_demo(monkeypatch):
    from tests.test_ui2_real_feed import _feed
    _feed(monkeypatch)
    at = _run_app(monkeypatch, case="R1", feed="real")
    blob = LT._page_blob(at)
    assert len(at.radio(key=KEY_TOPIC)) == 0 if hasattr(at.radio(key=KEY_TOPIC), "__len__") else True
    assert not [r for r in at.radio if r.key == KEY_TOPIC]
    assert "示意：合成持股快照" not in blob and "OneBrain 持股摘要｜" not in blob and "fake-syn" not in blob
    assert [c.value for c in at.caption if "測試輸入說明" in c.value] == []
    assert LT.DEFAULT_SLOT_TEXT in re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", LT._slot(blob))).strip()


@pytest.mark.slow
def test_apptest_selector_only_on_injected_hold_cold_fake(monkeypatch):
    assert not [r for r in _run_app(monkeypatch, case=None).radio if r.key == KEY_TOPIC], "沒有案例 env ⇒ 沒有選擇器"
    assert not [r for r in _run_app(monkeypatch, case="R1", page=P4_DATA).radio if r.key == KEY_TOPIC]
    assert not [r for r in _run_app(monkeypatch, case="R1", scenario=SCENARIO_LOADED).radio if r.key == KEY_TOPIC]


@pytest.mark.slow
def test_apptest_ai_disabled_no_network_still_works(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    L.seal_network(None)
    before = L.seal_rejected_count()
    at = _run_app(monkeypatch, case="L3")
    for topic in TOPICS:
        _pick(at, topic)
    assert L.seal_rejected_count() == before, "四主題操作期間不得有任何非 loopback 連線嘗試"
    L.unseal_network()


@pytest.mark.slow
def test_mutation_selector_that_only_swaps_the_label_turns_red(monkeypatch):
    """選擇器只換標籤、不換內容：wrapper 不讀選擇（永遠用預設主題）⇒ 點到「大盤」時槽內容不變 ⇒ 偵測必須紅。"""
    src = (ROOT / "tests" / "ui2_viewport" / "onebrain_hold_demo_launcher.py").read_text(encoding="utf-8")
    old_root, old_sel = "Path(__file__).resolve().parents[2]", "topic = selected_topic()"
    assert src.count(old_root) == 1 and src.count(old_sel) == 1, "launcher 的 wrapper 取主題那行變了：突變失去對象，請同步本測試"
    mutated = src.replace(old_root, f"Path({str(ROOT)!r})").replace(old_sel, "topic = DEFAULT_TOPIC")
    at = _run_app(monkeypatch, case="R1", source=mutated)
    blob = _pick(at, "大盤")
    assert at.radio(key=KEY_TOPIC).value == "大盤", "選擇器本身有換（標籤換了）"
    with pytest.raises(AssertionError):
        assert _slot_title(blob) == TITLE_PREFIX + "大盤" and _slot_labels(blob) == _expected_labels("大盤", "R1")


# ══════════════════════════════════════════════════════════════════════
# G. 真瀏覽器 390／1280／1440（ui2_browser）
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def _browser_ctx():
    from tests.ui2_browser import launch_or_fail, require_browser
    sp = require_browser()
    with sp() as p:
        b = launch_or_fail(p)
        yield p, b
        b.close()


_JS_SLOT = r"""
() => {
  const slot = document.querySelector('[data-ui2-l1="onebrain"]');
  const ctrl = document.querySelector('.st-key-ui2_obdemo_ctrl');
  const R = e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right}; };
  return {title: slot ? (slot.querySelector('.ui2-section-title') || {}).innerText : null,
          rows: slot ? [...slot.querySelectorAll('.ui2-row')].map(r => ({label: ((r.querySelector('.ui2-row__label') || {}).innerText || '').trim(),
                value: ((r.querySelector('.ui2-row__value') || {}).innerText || '').trim(),
                detail: ((r.querySelector('.ui2-row__detail') || {}).innerText || '').trim()})) : [],
          details: document.querySelectorAll('details, [data-testid="stExpander"]').length,
          ctrl: ctrl ? {...R(ctrl), text: ctrl.innerText.replace(/\s+/g, ' ').trim(), radios: ctrl.querySelectorAll('input[type=radio]').length} : null,
          hscroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          vh: innerHeight};
}
"""


def _click_topic(page, topic):
    page.locator(".st-key-ui2_obdemo_ctrl label", has_text=topic).first.click()
    page.wait_for_function("(t) => { const s = document.querySelector('[data-ui2-l1=\"onebrain\"] .ui2-section-title'); return s && s.innerText.includes(t); }",
                           arg=topic, timeout=20000)
    page.wait_for_timeout(300)


@pytest.mark.ui2_browser
@pytest.mark.parametrize("case,failclosed", [("R1", False), ("L2", False), ("L3", True)])
def test_browser_four_topics_clickable_at_three_widths(_browser_ctx, case, failclosed):
    p, b = _browser_ctx
    env = {"UI2_OBDEMO_CASE": case, **({"UI2_OBDEMO_FAILCLOSED": "1"} if failclosed else {})}
    seen_per_vp = {}
    proc, url, log = EV.start_server(ROOT, {**env, "UI2_OBDEMO_SEAL": "1"}, sys.executable)
    aborted: list[str] = []
    try:
        for vp, (vw, vh) in EV.VIEWPORTS.items():
            ctx = EV._new_context(b, vw, vh, aborted)
            page = ctx.new_page()
            EV._open_hold_fake(page, url)
            first = page.evaluate(_JS_SLOT)
            assert first["ctrl"] and first["ctrl"]["radios"] == 4 and "FAKE" in first["ctrl"]["text"], "控制群組必須有 FAKE 標示與四個選項"
            assert first["title"].endswith(DEFAULT_TOPIC)
            bodies = {}
            for topic in TOPICS:
                _click_topic(page, topic)
                m = page.evaluate(_JS_SLOT)
                assert m["title"].endswith(topic), (vp, topic, m["title"])
                assert [r["label"] for r in m["rows"]] == _expected_labels(topic, case, failclosed), (vp, topic)
                assert m["details"] == 0, "不得有 expander／details"
                assert m["hscroll"] <= 1, "不得橫向溢出"
                bodies[topic] = tuple((r["label"], r["value"], r["detail"]) for r in m["rows"])
            assert len(set(bodies.values())) == 4, f"{vp}：四主題 DOM 內容必須兩兩不同"
            seen_per_vp[vp] = bodies
            ctx.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)
    assert aborted == [], f"瀏覽器端出現非本機請求：{aborted}"
    assert len({tuple(b.values()) for b in seen_per_vp.values()}) == 1, "三個寬度的文字內容必須一致（只有版面不同）"


@pytest.mark.ui2_browser
def test_browser_real_feed_has_no_selector_or_demo(_browser_ctx):
    p, b = _browser_ctx
    from shared.ui2_contract.pages import FEED_REAL, P4_HOLD as HOLD, PAGE_LABELS, SCENARIO_REAL
    from src.ui2.shell.app import _FEED_LABELS
    from tests.ui2_viewport import measure_viewport as MV
    proc, url, log = EV.start_server(ROOT, {"UI2_OBDEMO_CASE": "R1"}, sys.executable)
    aborted: list[str] = []
    try:
        ctx = EV._new_context(b, 390, 844, aborted)
        page = ctx.new_page()
        EV._open_hold_fake(page, url)
        MV._select_box(page, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
        MV.click_nav(page, PAGE_LABELS[HOLD])
        page.wait_for_selector(f'[data-ui2-page="{HOLD}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
        page.wait_for_timeout(500)
        m = page.evaluate(_JS_SLOT)
        assert m["ctrl"] is None and "OneBrain 持股摘要｜" not in (m["title"] or "")
        assert not any("fake-syn" in r["value"] or "示意：合成" in r["value"] for r in m["rows"])
        ctx.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)
