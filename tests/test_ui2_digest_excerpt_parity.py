"""C-OB-UI-FAKE-A1：👤「Audit：Decision Digest」的 FAKE 靜態規則摘要節錄 —— parity／邊界／牙齒守衛。

授權：客戶設計確認 #1199 comment 7030418754；總管裁示 #1199 comment 7032645702 §2。
⚠️ 這**不是** OneBrain runtime：節錄是 `src/services/ui2/scenarios.py` 內的**固定字面常數**（匿名合成、只讀）。
本檔（tests/，不在 C2 掃描範圍）以 #1233 `tests/onebrain_anon_demo.py` 的**同一份合成 evidence** 現算 `build_rule_summary`，
逐字比對 UI 字面；改 UI 一字即紅。Stage F／G 仍關閉、`ALLOWED_CALLERS=∅`、不新增任何 production Digest import／caller。

節錄的選法（定義明確且最小）：取「證據齊全（A）」情境規則式摘要中**以缺值符號 ⬜ 起頭**的句子（市場／產業／存股／資本利得段），
排除「本期行動」整段與 Risk Cap 句（`RISK_CAP_HIDDEN_WORDING`，本就不以 ⬜ 起頭）。結果＝6 句「尚未定義／研究框架，未啟用／
尚未設定投資策略分類」：不含市場位階／燈號／健康度（含 `bull` 英文 token 與方向字，且會與 📊 的 FAKE 位階矛盾）、
不含資料日（故下方「合成資料日替換規則」為空集合並被鎖定）。
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from shared.decision_digest_terms import MISSING_GLYPH, RISK_CAP_HIDDEN_WORDING, SECTION_LABELS
from shared.ui2_contract.models import CapabilityState, PageVM
from shared.ui2_contract.pages import ACCOUNT_IDS, P4_ME, PAGE_IDS, SCENARIO_IDS
from src.services.decision_digest_summary import build_rule_summary
from src.services.ui2 import scenarios as SC
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import get_real_page_vm
from tests import onebrain_anon_demo as demo
from tests.test_ui2_p3_evidence_preservation import BASELINE, _snapshots, fingerprint

ROOT = Path(__file__).resolve().parents[1]

#: 總管裁示的示意聲明（必要新字串；逐字）與節錄聲明（總管指定「註明」的字面）。
NOTICE = "示意：合成資料／固定規則摘要節錄；非即時 OneBrain；非投資建議"
PARTIAL = "節錄，並非完整摘要"
#: 「合成資料日」顯示替換規則（明列並鎖定）：本節錄選法不含任何資料日 ⇒ 替換表為空；
#: 若日後節錄含資料日，必須在此新增 (舊, 新) 並同步重審，不得默默放行。
SYNTHETIC_DATE_REPLACEMENTS: tuple = ()
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|資料日")
_DIRECTION_OR_REGIME = ("多頭", "空頭", "偏多", "偏空", "看多", "看空", "bull", "bear", "caution", "neutral")
_WASHING = ("中性", "正常", "維持", "續抱", "持有", "觀望", "不動作", "照舊", "如常", "不變", "無異常")
_ACTION_TOKENS = ("txt-", "本期行動", "Risk Cap", "風險上限", "加碼", "減碼", "買進", "賣出", "建議")


# ── 預期值：由 demo 的同一份合成 evidence 現算 ───────────────────────────
def _lines(key: str) -> list[tuple[str, str]]:
    res = build_rule_summary(demo._assemble(key).digest)
    return [(sec, s) for sec, sentences in res.lines for s in sentences]


def expected_excerpt() -> list[tuple[str, str]]:
    out = []
    for sec, s in _lines("A"):
        if sec == "actions" or s == RISK_CAP_HIDDEN_WORDING or not s.startswith(MISSING_GLYPH):
            continue
        for old, new in SYNTHETIC_DATE_REPLACEMENTS:
            s = s.replace(old, new)
        out.append((SECTION_LABELS[sec], s))
    return out


# ── 從 PageVM 取出 digest 區塊 ────────────────────────────────────────────
def digest_rows(vm: PageVM) -> list[tuple[str, str]]:
    secs = [s for s in vm.context.sections if s.section_id == "digest"]
    assert len(secs) == 1 and secs[0].level == "L2" and secs[0].title == "Audit：Decision Digest"
    return [(f.label, f.value_text) for f in secs[0].fields]


# ── 檢查器（可被突變測試餵入壞資料；回傳違規描述）──────────────────────────
def check_parity(rows: list[tuple[str, str]]) -> list[str]:
    bad = []
    if len(rows) < 2 or rows[0][1] != NOTICE:
        bad.append("首列不是示意聲明（逐字）")
    if len(rows) < 2 or rows[1][1] != PARTIAL:
        bad.append("缺「節錄，並非完整摘要」")
    if rows[2:] != expected_excerpt():
        bad.append(f"節錄句與現算 build_rule_summary 不逐字一致：{rows[2:]!r}")
    return bad


def check_content_rules(rows: list[tuple[str, str]]) -> list[str]:
    # 示意聲明本身含「非投資建議」（否定句，總管裁示字串）→ 內容規則只掃聲明以外的列；聲明由 check_parity 逐字鎖定
    text = "\n".join(f"{a} {b}" for a, b in rows if b != NOTICE)
    bad = [f"含 {w!r}" for w in (*_ACTION_TOKENS, *_DIRECTION_OR_REGIME, *_WASHING) if w in text]
    if _DATE_RE.search(text):
        bad.append("顯示了資料日（節錄不得顯示真實或任何資料日）")
    for _, v in rows[2:]:
        if not v.startswith("⬜"):                      # 缺值句一律以 ⬜ 起頭（missing ≠ 0／中性）
            bad.append(f"節錄句未以 ⬜ 標示缺值：{v!r}")
    return bad


# ═══════════════════════════ 1. parity ═══════════════════════════
def test_expected_excerpt_is_the_six_missing_sentences_of_complete_evidence_scenario():
    exp = expected_excerpt()
    assert exp == [
        ("市場", "⬜ 台股趨勢：尚未定義，無法判定"),
        ("市場", "⬜ 國際趨勢：尚未定義，無法判定"),
        ("市場", "⬜ 大盤合理區間：研究框架，未啟用，無法判定"),
        ("產業", "⬜ 產業趨勢：尚未定義，無法判定"),
        ("存股", "⬜ 存股：尚未設定投資策略分類，無法判定"),
        ("資本利得", "⬜ 資本利得：尚未設定投資策略分類，無法判定"),
    ]
    assert SYNTHETIC_DATE_REPLACEMENTS == ()


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
@pytest.mark.parametrize("account", ACCOUNT_IDS)
def test_fake_me_digest_matches_rule_summary_verbatim(scenario, account):
    rows = digest_rows(get_preview_page_vm(P4_ME, scenario, account=account))
    assert check_parity(rows) == []
    assert check_content_rules(rows) == []


def test_ui_literals_equal_scenarios_constants():
    assert SC._DIGEST_EXCERPT_NOTICE == NOTICE and SC._DIGEST_EXCERPT_PARTIAL == PARTIAL


# ═══════════════════════════ 2. FAKE only／Real 不外洩 ═══════════════════════════
def test_real_digest_is_the_original_empty_slot():
    for name, snap in _snapshots().items():
        vm = get_real_page_vm(P4_ME, snap)
        sec = next(s for s in vm.context.sections if s.section_id == "digest")
        assert len(sec.fields) == 1, name
        f = sec.fields[0]
        assert (f.label, f.capability, f.value_text, f.status_text) == (
            "Decision Digest", CapabilityState.NOT_PROVIDED, None, "⬜ 尚未提供"), name
        assert f.detail == "此功能尚未開放"
        assert NOTICE not in repr(vm) and "台股趨勢：尚未定義" not in repr(vm)


def test_real_fingerprints_and_non_digest_fake_fingerprints_equal_committed_baseline():
    """Real 五頁（含 👤 digest／registry）指紋與 base 逐值相同；FAKE 除 p4_me 的 digest 區塊外亦同。"""
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    for name, snap in _snapshots().items():
        for page in PAGE_IDS:
            assert fingerprint(get_real_page_vm(page, snap)) == base[f"real/{page}/{name}"], (page, name)
    for page in PAGE_IDS:
        for sc in SCENARIO_IDS:
            for acct in (ACCOUNT_IDS if page == P4_ME else (None,)):
                cur = fingerprint(get_preview_page_vm(page, sc, account=acct))
                old = base[f"fake/{page}/{sc}/{acct}"]
                if page == P4_ME:
                    cur["sections"].pop("digest")
                    old["sections"].pop("digest")
                assert cur == old, (page, sc, acct)


def test_no_new_expander_and_gates_unchanged():
    from src.ui2.views import _page
    assert _page.SHOWN_FOLDS == frozenset({("p4_target", "conditions"), ("p4_me", "digest"),
                                           ("p4_me", "registry"), ("p4_data", "data_freshness_items")})
    from tests.test_decision_digest_invariants_guard import ALLOWED_CALLERS
    assert ALLOWED_CALLERS == frozenset()
    # 節錄只掛在既有 digest 區塊：👤 的 section id 集合不變
    ids = [s.section_id for s in get_preview_page_vm(P4_ME, "loaded").context.sections]
    assert ids == ["settings", "digest", "registry", "fresh", "sysinfo"]


# ═══════════════════════════ 3. 不新增 production Digest import／caller ═══════════════════════════
def _digest_imports(src: str) -> list[str]:
    hits = []
    for n in ast.walk(ast.parse(src)):
        mods = ([a.name for a in n.names] if isinstance(n, ast.Import)
                else [n.module or ""] + [a.name for a in n.names] if isinstance(n, ast.ImportFrom) else [])
        hits += [m for m in mods if "decision_digest" in m or "onebrain" in m]
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and re.fullmatch(r"(src|shared|tests)\.[\w.]*(decision_digest|onebrain)\w*", n.value)):
            hits.append(n.value)                        # importlib／__import__ 字串
    return hits


def _ui2_files():
    return [*sorted((ROOT / "src" / "services" / "ui2").rglob("*.py")),
            *sorted((ROOT / "src" / "ui2").rglob("*.py")), ROOT / "app_ui2.py"]


def test_ui2_has_no_digest_or_onebrain_import():
    for p in _ui2_files():
        assert _digest_imports(p.read_text(encoding="utf-8")) == [], p


# ═══════════════════════════ 4. 突變（檢查器必須轉紅）═══════════════════════════
def _good_rows() -> list[tuple[str, str]]:
    return digest_rows(get_preview_page_vm(P4_ME, "loaded"))


def test_teeth_parity_detects_one_char_change():
    rows = _good_rows()
    rows[3] = (rows[3][0], rows[3][1].replace("尚未定義", "尚未訂義"))
    assert check_parity(rows)


def test_teeth_parity_detects_missing_notice_or_partial_note():
    rows = _good_rows()
    assert check_parity(rows[1:])
    assert check_parity([rows[0], *rows[2:]])
    assert check_parity([("Decision Digest", "示意：合成資料／固定規則摘要節錄"), *rows[1:]])


def test_teeth_action_section_or_risk_cap_detected():
    rows = _good_rows() + [("本期行動", "T0：txt-add-T0")]
    assert check_content_rules(rows) and check_parity(rows)
    rows = _good_rows() + [("市場", RISK_CAP_HIDDEN_WORDING)]
    assert check_content_rules(rows) and check_parity(rows)


def test_teeth_real_data_date_detected():
    rows = _good_rows()
    rows[2] = (rows[2][0], rows[2][1] + "（資料日 2026-11-19）")
    assert check_content_rules(rows) and check_parity(rows)


def test_teeth_regime_token_direction_and_washing_detected():
    for bad in ("⬜ 市場位階：caution", "⬜ 市場位階：bull（資料日 2000-01-03）", "市場位階 中性", "⬜ 存股：維持"):
        assert check_content_rules(_good_rows() + [("市場", bad)]), bad


def test_teeth_missing_glyph_required():
    rows = _good_rows()
    rows[2] = (rows[2][0], "台股趨勢：尚未定義，無法判定")
    assert check_content_rules(rows)


def test_teeth_real_leak_detected(monkeypatch):
    """讓 Real 軸洩漏摘要（把 FAKE 區塊搬進 Real 的 👤 digest）→ Real 空槽斷言轉紅。"""
    from src.services.ui2 import real_canonical as RC
    orig = RC._me

    def leaky():
        c = orig()
        for s in c["sections"]:
            if s["key"] == "digest":
                s["fields"] = SC._digest_excerpt_fields()
        return c
    monkeypatch.setattr(RC, "_me", leaky)
    with pytest.raises(AssertionError):
        test_real_digest_is_the_original_empty_slot()


def test_teeth_production_import_detected():
    assert _digest_imports("from src.services.decision_digest_summary import build_rule_summary\n")
    assert _digest_imports("import shared.onebrain_provider as p\n")
    assert _digest_imports("import importlib\nimportlib.import_module('src.services.decision_digest_assembly')\n")
    assert _digest_imports("import os\n") == []


def test_teeth_allowed_callers_open_detected(monkeypatch):
    import tests.test_decision_digest_invariants_guard as G
    monkeypatch.setattr(G, "ALLOWED_CALLERS", frozenset({"src/ui2/views/me.py"}))
    with pytest.raises(AssertionError):
        test_no_new_expander_and_gates_unchanged()


def test_teeth_new_expander_detected(monkeypatch):
    from src.ui2.views import _page
    monkeypatch.setattr(_page, "SHOWN_FOLDS", _page.SHOWN_FOLDS | {("p4_me", "fresh")})
    with pytest.raises(AssertionError):
        test_no_new_expander_and_gates_unchanged()
