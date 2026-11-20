"""`tests/onebrain_anon_demo.py`（OneBrain／Digest 匿名離線示意）的行為與邊界測試（fast lane；C-OB-USABLE）。

守什麼：
1. 各情境（A～F）關鍵輸出存在，且每一頁頁首都有「示意：匿名合成輸入，非真實持股、非投資建議」；
2. 缺口如實呈現、不美化：C 情境摘要仍寫「尚無輸入」、coverage 記 stale、並有限制說明；E 情境（OB-1-D3）有限制說明；
3. 不捏造：輸出不含買賣動作用詞、不含 Risk Cap 數值；
4. F 情境：Provider 逾時／垃圾輸出／回聲，effective 恆為規則式摘要、Provider 輸出從不被採用；
5. 邊界：零網路（socket 被封鎖仍能跑）、demo 不 import streamlit／網路客戶端／LLM SDK、不被任何 src／app／scripts／shared import、
   檔名不是 `test_` 開頭（不被收集）。

⛔ 本檔不修改任何 src／shared／UI2／守衛常數。
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import re
import socket

import pytest

from shared.onebrain_provider import ProviderErrorKind
from src.services.decision_digest_summary import build_rule_summary
from src.services.onebrain_shadow import run_shadow
from tests import onebrain_anon_demo as demo
from tests.onebrain_fake_provider import FakeProvider

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_FILE = ROOT / "tests" / "onebrain_anon_demo.py"
BANNER = "示意：匿名合成輸入，非真實持股、非投資建議"
KEYS = ("A", "B", "C", "D", "E", "F")


def _text(key: str) -> str:
    return demo.run(key, "text")


def _report(key: str) -> dict:
    return demo.run_scenario(key)


# ════════════════════════════════════════════════════════════════════
# 1. 結構：頁首標示、四區、JSON
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("key", KEYS)
def test_every_page_starts_with_anonymous_banner_and_has_four_zones(key):
    t = _text(key)
    head = t.split("\n", 3)[1]                                  # 分隔線之後第一行
    assert BANNER in head
    for zone in ("① 來源", "② 缺值", "③ 規則判斷", "④ fallback"):
        assert zone in t, (key, zone)
    assert "UI2" in t and "空殼" in t and "看不到" in t          # 誠實聲明：這不是 UI
    assert "mode=rule_only" in t


def test_all_scenarios_render_one_page_each_in_order():
    t = demo.run("all", "text")
    assert t.count(BANNER) == len(KEYS)
    idx = [t.index(f"情境 {k}：") for k in KEYS]
    assert idx == sorted(idx)


def test_json_format_is_valid_and_mirrors_report():
    data = json.loads(demo.run("all", "json"))
    assert [d["scenario"] for d in data] == list(KEYS)
    for d in data:
        assert d["banner"] == BANNER
        assert {"sources", "missing", "rule_judgment", "notes", "fallback"} <= set(d)
        assert [s["segment"] for s in d["sources"]["segments"]] == ["market", "risk_cap", "holdings", "actions"]
    assert data[1]["sources"]["actions"]["total"] is None       # 未知是 None，不是 0


def test_deterministic_no_clock_no_randomness():
    assert demo.run("all", "text") == demo.run("all", "text")
    assert demo.run("all", "json") == demo.run("all", "json")


def test_main_cli_text_json_and_bad_scenario(capsys):
    assert demo.main(["--scenario", "B"]) == 0
    assert "情境 B" in capsys.readouterr().out
    assert demo.main(["--scenario", "c", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["scenario"] == "C"
    assert demo.main(["--scenario", "Z"]) == 2
    assert "未知情境" in capsys.readouterr().err


# ════════════════════════════════════════════════════════════════════
# 2. 各情境關鍵輸出
# ════════════════════════════════════════════════════════════════════
def test_A_complete_evidence_has_source_and_as_of_for_every_segment():
    r = _report("A")
    assert all(s["used"] and s["source"] and s["as_of"] == "2000-01-03" for s in r["sources"]["segments"])
    assert r["sources"]["is_complete"] is True and r["missing"]["withheld"] == []
    t = _text("A")
    assert "source=macro_state.json（合成）" in t and "資料日=2000-01-03（合成）" in t
    assert "四段證據皆採用" in t and r["notes"] == []


def test_B_zero_evidence_all_sections_insufficient_and_incomplete():
    r = _report("B")
    assert [w["reason"] for w in r["missing"]["withheld"]] == ["no_stamp"] * 4
    assert r["sources"]["is_complete"] is False
    t = _text("B")
    assert "資料不足，無法判定（尚無輸入）" in t
    assert t.count("資料不足，無法判定（尚無輸入）") + t.count("持股資料不足，無法判定（尚無輸入）") >= 4
    assert "no_stamp" in t and "is_complete=False" in t
    assert "未知（None，不是 0）" in t
    assert r["rule_judgment"]["state"] == "unavailable"


def test_C_stale_is_recorded_in_coverage_and_the_summary_gap_is_disclosed_not_hidden():
    r = _report("C")
    assert {w["segment"]: w["reason"] for w in r["missing"]["withheld"]} == {"market": "stale", "risk_cap": "stale"}
    t = _text("C")
    assert "stale" in t
    assert "摘要字面未區分「過期」與「尚無輸入」" in t          # 限制說明
    # 如實呈現現況：摘要仍寫「尚無輸入」（不美化成「過期」）
    market = next(b for b in r["rule_judgment"]["sections"] if b["section"] == "market")
    assert any("資料不足，無法判定（尚無輸入）" in s for s in market["sentences"])
    assert not any("過期" in s for b in r["rule_judgment"]["sections"] for s in b["sentences"])
    assert len(r["notes"]) == 1


def test_D_station_fetch_failed_is_named_in_coverage_and_in_notes():
    r = _report("D")
    assert {w["segment"]: w["reason"] for w in r["missing"]["withheld"]} == {
        "holdings": "fetch_failed", "actions": "fetch_failed"}
    t = _text("D")
    assert "fetch_failed" in t and "規則層未產出可引用依據，無法判定" in t
    assert "未點出「抓取失敗」" in t
    assert r["sources"]["actions"]["total"] is None


def test_E_more_than_top_n_actions_discloses_known_gap_OB_1_D3():
    r = _report("E")
    assert r["sources"]["actions"] == {"total": 7, "shown": 3, "omitted": 4, "max": 3}
    assert r["sources"]["is_complete"] is False
    actions = next(b for b in r["rule_judgment"]["sections"] if b["section"] == "actions")
    assert len(actions["sentences"]) == 3                        # 摘要只列 Top-N
    t = _text("E")
    assert "OB-1-D3" in t and "其餘 4 筆" in t and "total=7／shown=3／omitted=4" in t
    # 摘要本身沒有揭露省略（這是缺口，不是被修掉的項目）
    assert not any(w in s for s in actions["sentences"] for w in ("其餘", "省略", "未顯示"))


@pytest.mark.parametrize("key,expect_note", [("A", False), ("B", False), ("E", True), ("C", True), ("D", True)])
def test_limit_notes_only_when_the_phenomenon_is_present(key, expect_note):
    assert bool(_report(key)["notes"]) is expect_note


# ════════════════════════════════════════════════════════════════════
# 3. F：Provider 失敗不影響使用者看到的結果
# ════════════════════════════════════════════════════════════════════
def test_F_shadow_runs_effective_is_always_the_rule_summary():
    r = _report("F")
    runs = r["fallback"]["shadow_runs"]
    assert [x["error_kind"] for x in runs] == ["timeout", "invalid_response", None]
    assert [x["shadow_accepted"] for x in runs] == [False, False, True]
    assert all(x["effective_equals_rule_summary"] is True for x in runs)
    assert all(x["provider_output_adopted"] is False and x["effective_mode"] == "rule_only" for x in runs)
    assert r["fallback"]["provider_used"] is False
    t = _text("F")
    assert "error_kind=timeout" in t and "shadow_accepted=True" in t and "採用 Provider 輸出：否" in t
    assert "採用 Provider 輸出：是" not in t and "Provider 輸出是否被採用：是" not in t


def test_F_independent_recomputation_matches_the_demo_claim():
    a = demo._assemble("F")
    rule = build_rule_summary(a.digest).lines
    assert run_shadow(a.digest, FakeProvider("timeout")).effective.lines == rule
    out = run_shadow(a.digest, FakeProvider("timeout"))
    assert out.error_kind is ProviderErrorKind.TIMEOUT and out.shadow_accepted is False


def test_F_demo_reports_divergence_instead_of_hardcoding_equality(monkeypatch):
    """若影子層的 effective 與規則式摘要不同，demo 必須如實報 False（不得寫死 True）。"""
    real = demo.run_shadow
    other = build_rule_summary(demo._assemble("B").digest)       # 與 A digest 不同的合法摘要

    def diverging(digest, provider):
        return dataclasses.replace(real(digest, provider), effective=other)

    monkeypatch.setattr(demo, "run_shadow", diverging)
    runs = demo.run_scenario("F")["fallback"]["shadow_runs"]
    assert all(x["effective_equals_rule_summary"] is False for x in runs)
    assert "effective==規則式摘要：否" in demo.run("F", "text")


# ════════════════════════════════════════════════════════════════════
# 3b. QA 回修（N1～N3）：來源為合成值、Provider 標示、is_complete 如實
# ════════════════════════════════════════════════════════════════════
def test_N1_sources_are_marked_synthetic_in_text_and_json_and_not_a_real_date():
    for key in ("A", "C", "D", "E"):
        t, r = _text(key), _report(key)
        assert "① 來源（coverage：source／資料日）— 合成值（非真實 macro 資料日／非真實檔案；僅示意格式）" in t
        assert r["sources"]["provenance"] == "合成值（非真實 macro 資料日／非真實檔案；僅示意格式）"
        assert all(s["synthetic"] is True for s in r["sources"]["segments"])
        used = [s for s in r["sources"]["segments"] if s["source"]]
        assert used and all(s["as_of"] == "2000-01-03" for s in used)
        for s in used:                                            # 每個 source／資料日旁都有「合成」
            assert f"source={s['source']}（合成）　資料日={s['as_of']}（合成）" in t
    assert "2026-" not in demo.run("all", "text") and "2026-" not in demo.run("all", "json")   # 不與真實資料日撞同


def test_N2_fake_provider_is_labelled_and_acceptance_and_adopted_are_qualified():
    t = _text("F")
    assert "FakeProvider＝測試替身，不是真實模型" in t
    assert "shadow_accepted=True（僅表示規則草稿回聲通過檢查，不代表 AI 輸出被採用或品質認可）" in t
    assert t.count("採用 Provider 輸出：否（設計恆定宣告，非量測值；實質證據是 effective==規則式摘要）") == 3
    runs = _report("F")["fallback"]["shadow_runs"]
    assert runs[2]["shadow_accepted_note"] and runs[0]["shadow_accepted_note"] is None
    assert all(r["provider_output_adopted_note"] for r in runs)
    assert _report("F")["fallback"]["fake_provider_note"] == "FakeProvider＝測試替身，不是真實模型"


@pytest.mark.parametrize("key", KEYS)
def test_N3_is_complete_definition_shown_on_every_page(key):
    assert "is_complete 只指四段證據齊備且無未讀入計數，不代表摘要完整" in _text(key)
    assert "is_complete_note" in _report(key)["sources"]


def test_N3_scenario_C_title_says_stale_is_injected_not_derived_from_dates():
    assert "stale 以注入狀態示意，非由日期推算" in _text("C")
    assert "stale 以注入狀態示意，非由日期推算" in _report("C")["title"]


@pytest.mark.parametrize("key", ["B", "D"])
def test_N3_unknown_counts_render_as_None_and_is_complete_is_a_real_False(key):
    r, t = _report(key), _text(key)
    assert r["sources"]["actions"]["total"] is None and r["sources"]["actions"]["omitted"] is None
    assert r["sources"]["is_complete"] is False and r["sources"]["counts_unknown"] is True   # 布林 False，不是 None
    assert ("行動候選：total=未知（None，不是 0）／shown=0／omitted=未知（None，不是 0）（上限 3）；is_complete=False"
            in t)
    assert "is_complete 本身是 False（布林），不是 None" in t
    j = json.loads(demo.run(key, "json"))[0]["sources"]
    assert j["is_complete"] is False and j["actions"]["total"] is None and j["actions"]["omitted"] is None


def test_N3_known_counts_do_not_carry_the_unknown_note():
    for key in ("A", "C", "E"):
        assert _report(key)["sources"]["counts_unknown"] is False
        assert "行動計數為未知" not in _text(key)


# ── QA 存活突變補強：①區行動候選整行必須逐字出現（防 omitted／total 被寫死成 0）──
def test_B_text_has_the_full_actions_line_with_unknown_not_zero():
    t = _text("B")
    assert "行動候選：total=未知（None，不是 0）／shown=0／omitted=未知（None，不是 0）" in t
    assert "total=0" not in t and "omitted=0" not in t


def test_E_text_has_the_full_actions_line():
    assert "total=7／shown=3／omitted=4（上限 3）" in _text("E")


def test_A_text_actions_line_matches_coverage_exactly():
    assert "行動候選：total=2／shown=2／omitted=0（上限 3）；is_complete=True" in _text("A")


# ════════════════════════════════════════════════════════════════════
# 4. 不捏造：無買賣動作用詞、無 Risk Cap 數值
# ════════════════════════════════════════════════════════════════════
_BANNED = ("買進", "賣出", "加碼", "減碼", "停損", "停利", "目標價", "勝率", "信心")


def _strip_allowed(t: str) -> str:
    t = re.sub(r"txt-\S+", "", t)                               # Digest 既有示意識別字（已於頁首標示為合成示意）
    return t.replace("非投資建議", "").replace("不是建議", "")


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_no_trading_advice_wording_and_no_risk_cap_numbers(fmt):
    t = _strip_allowed(demo.run("all", fmt))
    for w in _BANNED:
        assert w not in t, w
    assert "建議" not in t
    assert not re.search(r"60\s*%", t) and "cap_pct" not in t and "exposure" not in t
    assert "風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate" in t   # Risk Cap 只顯示核准的卡面措辭


def test_action_texts_are_the_marked_synthetic_identifiers():
    t = demo.run("all", "text")
    acts = set(re.findall(r"txt-[^\s…]+", t))
    assert acts and all(re.fullmatch(r"txt-[a-z_]+-T\d", a) for a in acts), acts
    assert "合成示意識別字" in t


# ════════════════════════════════════════════════════════════════════
# 5. 邊界：零網路／不 import streamlit／不被 production import／不被收集
# ════════════════════════════════════════════════════════════════════
def test_runs_with_network_blocked(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("demo 不得觸網")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    assert BANNER in demo.run("all", "text")


_FORBIDDEN_IMPORTS = ("streamlit", "requests", "urllib", "http", "httpx", "aiohttp", "socket", "openai", "anthropic",
                      "google", "yfinance", "FinMind", "gspread", "src.data", "src.ui", "src.ui2", "app", "app_ui2",
                      "shared.onebrain_provider.real", "scripts")


def _imports(path: pathlib.Path) -> list[str]:
    out: list[str] = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            out.append(n.module or "")
    return out


def test_demo_imports_no_streamlit_network_sdk_or_ui_modules():
    bad = [m for m in _imports(DEMO_FILE) for f in _FORBIDDEN_IMPORTS if m == f or m.startswith(f + ".")]
    assert bad == [], bad
    src = DEMO_FILE.read_text(encoding="utf-8")
    for needle in ("st.session_state", "os.environ", "getenv", "open(", "time.time", "datetime.now", "date.today",
                   "random", "gsheet", "oauth", "api_key", "http://", "https://"):
        assert needle not in src, needle


def test_demo_is_not_a_test_module_and_lives_in_tests():
    assert DEMO_FILE.parent.name == "tests" and not DEMO_FILE.name.startswith("test_")


def test_no_production_file_imports_the_demo():
    hits: list[str] = []
    files = [ROOT / "app.py", ROOT / "app_ui2.py"]
    for top in ("shared", "src", "scripts"):
        files += [p for p in (ROOT / top).rglob("*.py") if "__pycache__" not in p.parts]
    for p in files:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        if "onebrain_anon_demo" in text:                         # 含字串／註解引用：一律視為耦合
            hits.append(p.relative_to(ROOT).as_posix())
    assert hits == [], "demo 只准被 tests/ 與人（python -m）使用：" + repr(hits)
