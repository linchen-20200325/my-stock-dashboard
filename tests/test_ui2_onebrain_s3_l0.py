"""OneBrain S3-L0 可操作隔離原型（tests-only）的行為與守衛測試。

被測：`tests/ui2_viewport/onebrain_s3_l0_launcher.py`（獨立 streamlit 入口；只在「💼 持股／FAKE／cold」把既有 OneBrain L1 槽
換成示範內容並畫出四主題切換）。客戶 R16 核准範圍：四主題、預設持股健檢、行內證據文案、恰兩個 tests-only 檔案。

三層：
1. **fast（無 marker）**：夾具分桶、文案詞彙、靜態守衛（import／session key 前綴）、安裝還原、封網牙齒、各檢查器的牙齒（注入壞資料必紅）。
2. **slow（AppTest）**：渲染矩陣——示範頁、Real 正常／degraded、一般 FAKE 各場景、非持股頁皆「無示範內容、逐值同未安裝」；夾具出錯退回原槽；零非本機網路。
3. **ui2_browser（Playwright）**：390×844／1280×900 的鍵盤選取、選取狀態可辨識（AX tree＋標題文字，不只顏色）、無遮擋／水平溢出、
   OneBrain 槽恰出現一次、拒用原值不外洩、Real 無示範選擇器、server 封網零連外。

⛔ 本檔不 import 任何決策摘要／OneBrain／AI 模組，也不新增任何 production caller；不連網。
缺 playwright／Chromium：`UI2_BROWSER_LANE=required` → fail、本機 skip＋警示（`tests/ui2_browser.py`）。
"""
from __future__ import annotations

import ast
import html as _html
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

from shared.ui2_contract.pages import (
    P4_DATA, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE_IDS, SCENARIO_COLD, SCENARIO_IDS,
)
from tests.test_ui2_guards import _FORBIDDEN_ACTION_WORDS, _FORBIDDEN_TERMS
from tests.test_ui2_p1_human_text import ENGINEERING_VOCAB, hits_in
from tests.ui2_viewport import onebrain_s3_l0_launcher as L

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_PATH = ROOT / "tests" / "ui2_viewport" / "onebrain_s3_l0_launcher.py"
THIS_PATH = Path(__file__).resolve()
SLOT = 'data-ui2-l1="onebrain"'
SLOT_TAG_RX = re.compile(r'<div[^>]*data-ui2-l1="onebrain"')     # 元素（不含 <style> 內的 CSS 選擇器字串）
MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 900}

#: 買賣動作／方向字（槽內不得出現；「非投資建議」是必要的免責字樣，故不列「建議」）。
DIRECTION_AND_ACTION_WORDS = (
    "多頭", "空頭", "偏多", "偏空", "看多", "看空", "看漲", "看跌", "上漲", "下跌", "bull", "bear", "caution", "neutral",
    "買", "賣", "加碼", "減碼", "持有", "出場", "進場", "停損", "停利", "目標價", "推薦",
)
NO_COUNTER_TEXT = "⬜ 無法判定（無反證輸入）"


# ══════════════════════════════════════════════════════════════════════
# 共用工具
# ══════════════════════════════════════════════════════════════════════
_STYLE_RX = re.compile(r"<style.*?</style>", re.S)
_TAG_RX = re.compile(r"<[^>]+>")


def plain(html: str) -> str:
    """HTML → 使用者看到的文字（去 `<style>`、去標籤、反跳脫）。"""
    return _html.unescape(_TAG_RX.sub(" ", _STYLE_RX.sub("", html)))


def slot_html(markdowns) -> str:
    """從一串 markdown 值取出 OneBrain 槽的 HTML（`ui2-m-onebrain` 區塊到 Primary 空槽之前）。"""
    for v in markdowns:
        m = SLOT_TAG_RX.search(v)
        if m:
            j = v.find('data-ui2-l1="hold_primary_slot"', m.start())
            return v[m.start():j if j > 0 else len(v)]
    return ""


def slot_count(markdowns) -> int:
    return sum(len(SLOT_TAG_RX.findall(v)) for v in markdowns)


def forbidden_hits(text: str) -> list[str]:
    """工程詞彙（P1 守衛的 ENGINEERING_VOCAB＋型別名／層級／題號）＋買賣動作／方向字＋禁用字樣。"""
    out = list(hits_in(text))
    out += [w for w in _FORBIDDEN_ACTION_WORDS + _FORBIDDEN_TERMS + DIRECTION_AND_ACTION_WORDS if w in text]
    return out


def leak_hits(text: str) -> list[str]:
    """被拒用項目的原值（含夾具敘述片段）不得出現在任何輸出面。"""
    secrets = list(L.LEAKY_RAW_VALUES)
    secrets += [it.text for items in L.FIXTURES.values() for it in items if it.raw]
    return [s for s in secrets if s in text]


@contextmanager
def installed():
    L.install()
    try:
        yield
    finally:
        L.uninstall()


@contextmanager
def sealed():
    st = L.seal_network()
    try:
        yield st
    finally:
        L.unseal_network()


# ══════════════════════════════════════════════════════════════════════
# 1. fast：夾具分桶
# ══════════════════════════════════════════════════════════════════════
def test_topics_default_and_labels_are_the_approved_four():
    assert L.TOPICS == ("大盤", "產業前瞻", "持股健檢", "反方風險")
    assert L.DEFAULT_TOPIC == "持股健檢"
    assert L.ROW_LABELS == ("支持證據", "反面證據", "缺項", "拒用")
    assert set(L.FIXTURES) == set(L.TOPICS)


@pytest.mark.parametrize("topic", L.TOPICS)
def test_every_topic_builds_exactly_four_valid_fieldvm_rows(topic):
    fields = L.build_fields(topic)
    assert tuple(f.label for f in fields) == L.ROW_LABELS


def test_evidence_rows_show_only_items_with_source_and_date_and_mark_synthetic():
    for topic in L.TOPICS:
        b = L.classify(L.FIXTURES[topic])
        for it in (*b.support, *b.counter):
            assert it.source and L._parse_day(it.as_of) is not None
        fields = {f.label: f for f in L.build_fields(topic)}
        for lab in (L.LABEL_SUPPORT, L.LABEL_COUNTER):
            f = fields[lab]
            if f.value_text is not None:
                assert f.value_text.count(f"［{L.SYNTHETIC_MARK}］") == f.value_text.count("來源：")
                assert "資料日 20" in f.value_text


def test_citation_alone_never_counts_as_support():
    cite = L.Item(L.KIND_CITATION, "合成標的丙 於法說會被提及")
    b = L.classify((cite,))
    assert b.support == () and b.counter == ()
    assert b.missing == (L.REASON_NO_SOURCE,)
    # 帶 kind=support 但沒有來源／資料日：同樣不是支持（只能是缺項）
    for it in (L.Item(L.KIND_SUPPORT, "x", None, "2026-11-01"), L.Item(L.KIND_SUPPORT, "x", "合成來源", None),
               L.Item(L.KIND_SUPPORT, "x", "合成來源", "not-a-date")):
        b2 = L.classify((it,))
        assert b2.support == () and b2.missing == (L.REASON_NO_SOURCE,)
    f = {x.label: x for x in L.build_fields(L.TOPIC_HOLDINGS)}
    assert "法說會" not in (f[L.LABEL_SUPPORT].value_text or "")


def test_risk_cap_item_never_becomes_counter_evidence_or_support():
    rc = L.Item(L.KIND_RISK_CAP, "合成組合風險上限接近滿水位", "合成組合表", "2026-11-20")
    b = L.classify((rc,))
    assert b == L.Buckets()
    only_rc = L.classify((rc, rc))
    assert only_rc.counter == () and only_rc.support == ()
    # 持股健檢主題含一筆風險上限夾具：反面證據只來自 kind=counter 的夾具
    f = {x.label: x for x in L.build_fields(L.TOPIC_HOLDINGS)}
    assert "風險上限" not in " ".join((x.value_text or "") + (x.detail or "") for x in f.values())
    # 只有風險上限 ⇒ 反面證據＝無法判定
    row = L._undeterminable_row(L.LABEL_COUNTER, "反證")
    assert row.status_text == NO_COUNTER_TEXT


def test_no_counter_input_row_is_exactly_undeterminable_with_reason():
    for topic in (L.TOPIC_MARKET, L.TOPIC_INDUSTRY):
        f = {x.label: x for x in L.build_fields(topic)}
        c = f[L.LABEL_COUNTER]
        assert c.status_text == NO_COUNTER_TEXT and c.value_text is None
        assert c.state.value == "undeterminable"           # unknown ≠ safe；不是 OK、不是 0


def test_rejected_items_expose_only_fixed_public_reasons_and_never_the_raw_value():
    b = L.classify(L.FIXTURES[L.TOPIC_HOLDINGS])
    assert set(b.rejected) <= set(L.PUBLIC_REJECT_REASONS) and len(b.rejected) == 2
    stale = L.Item(L.KIND_SUPPORT, "含原值 7777.77", "合成來源", "2026-01-01", raw="7777.77")
    pit = L.Item(L.KIND_COUNTER, "含原值 原值哨兵甲", "合成來源", "2027-06-01", raw="原值哨兵甲")
    b = L.classify((stale, pit))
    assert b.rejected == (L.REASON_STALE, L.REASON_PIT) and b.support == () and b.counter == ()
    for topic in L.TOPICS:
        blob = repr(L.build_fields(topic)) + L.summary_text(topic)
        assert leak_hits(blob) == [], topic


def test_stale_and_future_dated_items_are_rejected_not_displayed():
    ref = L.REFERENCE_DATE
    ok = L.Item(L.KIND_SUPPORT, "a", "s", ref.isoformat())
    assert L.classify((ok,)).support == (ok,)
    assert L.classify((L.Item(L.KIND_SUPPORT, "a", "s", "2026-11-26"),)).rejected == (L.REASON_PIT,)
    old = ref.replace(year=ref.year - 1).isoformat()
    assert L.classify((L.Item(L.KIND_COUNTER, "a", "s", old),)).rejected == (L.REASON_STALE,)


def test_unknown_fixture_kind_fails_loud():
    with pytest.raises(ValueError):
        L.classify((L.Item("weird", "x", "s", "2026-11-01"),))
    with pytest.raises(KeyError):
        L.build_fields("不存在的主題")


def test_market_topic_commits_to_no_sentence_and_says_preview():
    assert "預覽" in L._section_title(L.TOPIC_MARKET)
    f = L.build_fields(L.TOPIC_MARKET)
    assert all(x.value_text is None for x in f)               # 不寫任何大盤句子（C3／D7 未裁）


def test_current_topic_falls_back_to_default_on_garbage():
    assert L.current_topic({}) == L.DEFAULT_TOPIC
    assert L.current_topic({L.TOPIC_KEY: "亂碼"}) == L.DEFAULT_TOPIC
    assert L.current_topic({L.TOPIC_KEY: L.TOPIC_COUNTER}) == L.TOPIC_COUNTER


# ══════════════════════════════════════════════════════════════════════
# 1b. fast：文案（工程詞彙／買賣動作／方向字）
# ══════════════════════════════════════════════════════════════════════
def _all_visible_strings(topic: str) -> list[str]:
    out = [L._section_title(topic), L.SELECTOR_LABEL, *L.TOPICS, *L.ROW_LABELS]
    for f in L.build_fields(topic):
        out += [x for x in (f.label, f.value_text, f.status_text, f.detail) if x]
    return out


@pytest.mark.parametrize("topic", L.TOPICS)
def test_visible_copy_has_no_engineering_vocab_no_action_or_direction_words(topic):
    blob = "\n".join(_all_visible_strings(topic))
    assert forbidden_hits(blob) == [], topic
    assert L.SYNTHETIC_MARK in blob or topic == L.TOPIC_MARKET
    assert "非即時" in blob and "非投資建議" in blob


def test_vocab_scan_has_teeth():
    for bad in ("Preview", "session", "接線", "Gate", "traceback", "twii_ohlcv", "L2 明細", "①", "OSError", "買進", "看多"):
        assert forbidden_hits("正常文字" + bad), bad
    assert any(w in ENGINEERING_VOCAB for w in ("Preview", "session", "Gate"))


# ══════════════════════════════════════════════════════════════════════
# 1c. fast：靜態守衛（import／session key 前綴／無 production Digest caller）
# ══════════════════════════════════════════════════════════════════════
BANNED_IMPORT_SUBSTRINGS = (
    "decision_digest", "onebrain", "ai_fetcher", "app_ai_service", "ai_qa_service", "ai_structured_summary",
    "requests", "httpx", "aiohttp", "urllib", "http.client", "openai", "anthropic", "google.generativeai",
    "google.genai", "vertexai", "langchain", "litellm", "src.services", "src.data", "src.compute", "proxy_helper",
)
#: 本檔對被測 launcher 的唯一合法 import（模組名含 onebrain 但它是 tests-only 入口，不是決策／OneBrain 模組）。
SELF_ALLOWED_MODULES = frozenset({
    "tests.ui2_viewport.onebrain_s3_l0_launcher", "tests.ui2_viewport", "tests",
    # 既有守衛／Real 取數入口的「只讀引用」（本檔只比對 Real VM 逐值不變、讀 ALLOWED_CALLERS；不新增 caller）
    "tests.test_decision_digest_invariants_guard", "tests.test_decision_digest_invariants_guard.ALLOWED_CALLERS",
    "src.services.ui2.real_feed", "src.services.ui2.real_feed.read_real_snapshot",
    "src.services.ui2.real_canonical", "src.services.ui2.real_canonical.get_real_page_vm",
    "urllib.request",                          # 只用於輪詢本機 127.0.0.1 的 streamlit health（封網下 loopback 不受影響）
    "urllib.request.urlopen",
})


def import_problems(source: str, *, allowed=frozenset()) -> list[str]:
    """AST：任何 import／動態 import 字串命中禁用片段（allowed 內的精確模組名除外）。"""
    out: list[str] = []
    for n in ast.walk(ast.parse(source)):
        mods: list[str] = []
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            mods = [base] + [f"{base}.{a.name}" for a in n.names]
        elif isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name)):
            fn = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
            if fn in ("import_module", "__import__") and n.args and isinstance(n.args[0], ast.Constant):
                mods = [str(n.args[0].value)]
        for m in mods:
            if m in allowed:
                continue
            if any(b in m for b in BANNED_IMPORT_SUBSTRINGS):
                out.append(m)
    return out


def test_launcher_and_test_import_no_digest_onebrain_ai_or_network_modules():
    # launcher 對 shell／hold 的動態 import 只用模組名常數（SHELL_MODULE／HOLD_MODULE），其值亦須乾淨
    assert not any(b in L.SHELL_MODULE + L.HOLD_MODULE for b in BANNED_IMPORT_SUBSTRINGS)
    assert import_problems(LAUNCHER_PATH.read_text(encoding="utf-8"), allowed=frozenset({"socket"})) == []
    assert import_problems(THIS_PATH.read_text(encoding="utf-8"), allowed=SELF_ALLOWED_MODULES | {"socket"}) == []


def test_import_guard_has_teeth():
    for bad in ("import shared.decision_digest_rules", "from src.services import decision_digest_summary",
                "from src.services.onebrain_shadow import run_shadow", "import requests",
                "import importlib\nimportlib.import_module('shared.onebrain_provider')",
                "from src.data.core import data_loader"):
        assert import_problems(bad), bad
    assert import_problems("import json\nfrom pathlib import Path") == []


def test_production_digest_gate_is_still_closed():
    from tests.test_decision_digest_invariants_guard import ALLOWED_CALLERS
    assert ALLOWED_CALLERS == frozenset()


def _const_strs(tree: ast.Module) -> dict[str, str]:
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = n.value.value
    return out


def key_prefix_problems(source: str) -> list[str]:
    """G9 紀律的 tests-only 版本：`key=` 與 `session_state` 取用的字串鍵一律 `ui2_` 前綴；無法解析成字串常數＝違規（不猜）。"""
    tree = ast.parse(source)
    consts = _const_strs(tree)

    def resolve(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return consts.get(node.id)
        return None

    def is_state(node) -> bool:
        return isinstance(node, ast.Attribute) and node.attr == "session_state"

    bad: list[str] = []
    for n in ast.walk(tree):
        cands = []
        if isinstance(n, ast.keyword) and n.arg == "key":
            cands.append(n.value)
        elif isinstance(n, ast.Subscript) and is_state(n.value):
            cands.append(n.slice)
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and is_state(n.func.value)
              and n.func.attr in ("get", "setdefault", "pop") and n.args):
            cands.append(n.args[0])
        elif isinstance(n, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in n.ops) \
                and any(is_state(c) for c in n.comparators):
            cands.append(n.left)
        for c in cands:
            k = resolve(c)
            if k is None:
                # `k` 這類迴圈變數取用（seed_session）：以 tuple 常數走訪驗證，見下一個測試
                if isinstance(c, ast.Name) and c.id == "k":
                    continue
                bad.append(f"line {getattr(c, 'lineno', '?')}: 非常數鍵")
            elif not k.startswith("ui2_"):
                bad.append(f"line {getattr(c, 'lineno', '?')}: {k!r}")
    return bad


def test_all_session_and_widget_keys_are_ui2_prefixed():
    src = LAUNCHER_PATH.read_text(encoding="utf-8")
    assert key_prefix_problems(src) == []
    assert all(k.startswith("ui2_") for k in L.SESSION_KEYS) and L.BOX_KEY.startswith("ui2_")
    # seed_session 的迴圈鍵（以 tuple 常數走訪）
    tree = ast.parse(src)
    seed = next(f for f in tree.body if isinstance(f, ast.FunctionDef) and f.name == "seed_session")
    keys = [e.elts[0].value for n in ast.walk(seed) if isinstance(n, ast.For) for e in n.iter.elts]
    assert keys == ["ui2_feed", "ui2_page", "ui2_scenario"]


def test_key_prefix_guard_has_teeth():
    for bad in ('st.radio("x", [1], key="topic")', 'st.session_state["topic"] = 1',
                'st.session_state.setdefault("topic", 1)', 'x = "topic" in st.session_state',
                'st.radio("x", [1], key=some_var)'):
        assert key_prefix_problems("import streamlit as st\n" + bad), bad
    assert key_prefix_problems('import streamlit as st\nst.radio("x",[1],key="ui2_ok")') == []


def test_launcher_never_writes_non_ui_state_or_touches_clock_and_files():
    src = LAUNCHER_PATH.read_text(encoding="utf-8")
    for bad in ("datetime.now", "date.today", "time.time(", "open(\"", "read_text", "write_text", "st.secrets", "environ["):
        assert bad not in src.replace("open(st[\"log_path\"]", ""), bad


# ══════════════════════════════════════════════════════════════════════
# 1d. fast：安裝／還原、封網牙齒
# ══════════════════════════════════════════════════════════════════════
def test_install_is_idempotent_and_uninstall_restores_everything():
    shell = L._shell()
    hold = __import__("importlib").import_module(L.HOLD_MODULE)
    views0, md0 = shell.VIEWS, hold._md
    try:
        L.install()
        L.install()
        assert L.is_installed() and L.get_state()["installs"] == 1
        assert shell.VIEWS is not views0 and shell.VIEWS[P4_HOLD] is not views0[P4_HOLD]
        for pid in PAGE_IDS:
            if pid != P4_HOLD:
                assert shell.VIEWS[pid] is views0[pid]            # 只包 💼
    finally:
        L.uninstall()
    assert shell.VIEWS is views0 and hold._md is md0 and not L.is_installed()
    L.uninstall()                                                  # 冪等


def _connect_closing(method: str):
    with socket.socket() as s:
        return getattr(s, method)(("93.184.216.34", 80))


def test_network_seal_has_teeth_and_allows_loopback():
    with sealed() as st:
        for call in (lambda: socket.create_connection(("93.184.216.34", 80), timeout=1),
                     lambda: socket.getaddrinfo("example.invalid", 80),
                     lambda: _connect_closing("connect"),
                     lambda: _connect_closing("connect_ex")):
            with pytest.raises(L.NetworkSealed):
                call()
        assert len(st["denied"]) == 4
        socket.getaddrinfo("127.0.0.1", 80)                         # loopback 不受影響
        with socket.socket() as s:
            s.settimeout(0.5)
            s.connect_ex(("127.0.0.1", 9))                          # 連不上也行（回 errno）；重點是不被封網攔截、不 raise
        assert len(st["denied"]) == 4
    assert getattr(socket, L.SEAL_ATTR, None) is None              # 離開後還原


# ══════════════════════════════════════════════════════════════════════
# 2. slow：AppTest 渲染矩陣
# ══════════════════════════════════════════════════════════════════════
def _apply(at, *, feed="fake", page=P4_HOLD, scenario=SCENARIO_COLD, topic=None):
    at.session_state["ui2_feed"] = feed
    at.session_state["ui2_page"] = page
    at.session_state["ui2_scenario"] = scenario
    if topic is not None:
        at.session_state[L.TOPIC_KEY] = topic


def run_app(*, feed="fake", page=P4_HOLD, scenario=SCENARIO_COLD, topic=None):
    """在封網下跑一次 app_ui2（AppTest）；回傳 AppTest。任何連外嘗試 ⇒ 測試失敗。"""
    from streamlit.testing.v1 import AppTest
    with sealed() as st:
        at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=90)
        _apply(at, feed=feed, page=page, scenario=scenario, topic=topic)
        at.run()
        assert st["denied"] == [], st["denied"]
    assert not at.exception, [e.value for e in at.exception]
    return at


def md_values(at) -> list[str]:
    return [m.value for m in at.markdown]


def has_box(at) -> bool:
    return any(r.key == L.TOPIC_KEY for r in at.radio)


def page_text(at) -> str:
    """AppTest 裡所有使用者可見文字：markdown（去 style／標籤）＋radio 標籤與選項＋caption／text。"""
    parts = [plain(v) for v in md_values(at)]
    for r in at.radio:
        parts += [r.label, *r.options]
    parts += [c.value for c in at.caption] + [t.value for t in at.text]
    return "\n".join(parts)


@pytest.fixture
def inst():
    with installed():
        yield


@pytest.mark.slow
def test_demo_page_default_topic_selector_and_single_slot(inst):
    at = run_app()
    r = at.radio(key=L.TOPIC_KEY)
    assert tuple(r.options) == L.TOPICS and r.value == "持股健檢" and r.label == L.SELECTOR_LABEL
    vals = md_values(at)
    assert slot_count(vals) == 1
    s = slot_html(vals)
    for lab in L.ROW_LABELS:
        assert f'<div class="ui2-row__label">{lab}</div>' in s
    assert "｜持股健檢｜" in plain(s)
    st = L.get_state()
    assert st["injected"] >= 1 and st["fallbacks"] == 0


@pytest.mark.slow
@pytest.mark.parametrize("topic", L.TOPICS)
def test_each_topic_renders_four_rows_once_and_never_leaks_rejected_values(inst, topic):
    at = run_app(topic=topic)
    vals = md_values(at)
    assert slot_count(vals) == 1
    s = slot_html(vals)
    assert [m for m in re.findall(r'class="ui2-row__label">([^<]+)<', s)] == list(L.ROW_LABELS)
    assert f"｜{topic}" in plain(s)
    blob = "\n".join(vals) + page_text(at) + repr(L.build_fields(topic)) + L.summary_text(topic)
    assert leak_hits(blob) == []
    assert forbidden_hits(plain(s) + " " + L.SELECTOR_LABEL + " ".join(L.TOPICS)) == []


@pytest.mark.slow
def test_no_counter_row_and_missing_row_and_rejected_row_are_each_covered_in_dom(inst):
    s_market = plain(slot_html(md_values(run_app(topic=L.TOPIC_MARKET))))
    assert NO_COUNTER_TEXT in s_market                      # 無反證 ⇒ 無法判定（無反證輸入）
    assert "⬜ 無法判定（無支持輸入）" in s_market and "⬜ 無法判定（無拒用輸入）" in s_market
    s_hold = plain(slot_html(md_values(run_app(topic=L.TOPIC_HOLDINGS))))
    assert "缺：" in s_hold and "只被引用，沒有可核對的來源與資料日" in s_hold          # 引用 ⇒ 缺項，不當支持
    assert "未採用：資料已過期；資料日晚於判讀時點（不顯示原值）" in s_hold             # 拒用：只有固定原因
    assert "法說會" not in s_hold.split("反面證據")[0]                               # 引用的敘述不在支持列
    s_counter = plain(slot_html(md_values(run_app(topic=L.TOPIC_COUNTER))))
    assert "風險上限" not in s_counter                       # Risk Cap 不推反證，也不出現在槽內
    assert "⬜ 無法判定（無支持輸入）" in s_counter


@pytest.mark.slow
def test_garbage_topic_in_session_falls_back_to_default(inst):
    at = run_app(topic="亂碼")
    assert at.radio(key=L.TOPIC_KEY).value == L.DEFAULT_TOPIC
    assert "｜持股健檢｜" in plain(slot_html(md_values(at)))


@pytest.mark.slow
def test_switching_topic_via_widget_rerenders_slot(inst):
    at = run_app()
    for topic in (L.TOPIC_COUNTER, L.TOPIC_INDUSTRY, L.TOPIC_MARKET, L.TOPIC_HOLDINGS):
        at.radio(key=L.TOPIC_KEY).set_value(topic).run()
        assert not at.exception
        s = slot_html(md_values(at))
        assert f"｜{topic}" in plain(s) and slot_count(md_values(at)) == 1


@pytest.mark.slow
def test_whole_page_adds_no_new_forbidden_words_versus_uninstalled(inst):
    on = page_text(run_app())
    L.uninstall()
    off = page_text(run_app())
    L.install()
    assert set(forbidden_hits(on)) <= set(forbidden_hits(off)), sorted(set(forbidden_hits(on)) - set(forbidden_hits(off)))
    assert leak_hits(on) == []


def _real_snapshot():
    from src.services.ui2.real_feed import read_real_snapshot
    return read_real_snapshot()


@pytest.fixture
def real_snapshot_patch(monkeypatch):
    """固定 Real snapshot（兩次渲染比較不受時間／檔案變動影響）；degraded 另測。"""
    snap = _real_snapshot()
    monkeypatch.setattr(L._shell(), "read_real_snapshot", lambda: snap)
    return snap


@pytest.mark.slow
def test_real_normal_has_no_demo_and_vm_and_markup_are_identical_to_uninstalled(real_snapshot_patch):
    from src.services.ui2.real_canonical import get_real_page_vm
    snap = real_snapshot_patch
    vm_before = get_real_page_vm(P4_HOLD, snap)
    L.uninstall()
    off = run_app(feed="real")
    with installed():
        vm_after = get_real_page_vm(P4_HOLD, snap)
        on = run_app(feed="real")
        injected = L.get_state()["injected"]
    assert vm_before == vm_after                                   # Real VM 逐值不變（本檔不經過 Real 的 VM 函式）
    assert md_values(on) == md_values(off)                          # 渲染逐字相同
    assert injected == 0 and not has_box(on)
    t = page_text(on)
    assert "OneBrain 示意" not in t and L.SELECTOR_LABEL not in t and "支持證據" not in t and "反面證據" not in t


@pytest.mark.slow
def test_real_degraded_has_no_demo_and_is_identical_to_uninstalled(monkeypatch):
    def boom():
        raise RuntimeError("secret-token")
    monkeypatch.setattr(L._shell(), "read_real_snapshot", boom)
    L.uninstall()
    off = run_app(feed="real")
    with installed():
        on = run_app(feed="real")
    assert md_values(on) == md_values(off) and not has_box(on)
    assert "secret-token" not in page_text(on)


@pytest.mark.slow
def test_real_on_every_page_never_gets_selector_or_demo_content(real_snapshot_patch):
    with installed():
        for pid in PAGE_IDS:
            at = run_app(feed="real", page=pid)
            t = page_text(at)
            assert not has_box(at), pid
            assert "OneBrain 示意" not in t and "支持證據" not in t, pid


@pytest.mark.slow
@pytest.mark.parametrize("scenario", [s for s in SCENARIO_IDS if s != SCENARIO_COLD])
def test_plain_fake_hold_in_non_cold_scenarios_has_no_demo_and_is_identical(scenario):
    off = run_app(scenario=scenario)
    with installed():
        on = run_app(scenario=scenario)
        assert not has_box(on) and L.get_state()["injected"] == 0
    assert md_values(on) == md_values(off)


@pytest.mark.slow
@pytest.mark.parametrize("page", [P4_MARKET, P4_TARGET, P4_ME, P4_DATA])
def test_fake_cold_on_non_hold_pages_has_no_demo_and_is_identical(page):
    off = run_app(page=page)
    with installed():
        on = run_app(page=page)
        assert not has_box(on) and L.get_state()["injected"] == 0
    assert md_values(on) == md_values(off)


@pytest.mark.slow
def test_fixture_failure_falls_back_to_original_slot_and_page_stays_operable(monkeypatch):
    L.uninstall()
    off = run_app()
    monkeypatch.setattr(L, "build_fields", lambda topic: (_ for _ in ()).throw(RuntimeError("secret-token 7777.77")))
    with installed():
        at = run_app()
        assert md_values(at) == md_values(off) and not has_box(at)       # 退回原本的「尚未提供」槽、無選擇器
        st = L.get_state()
        assert st["fallbacks"] >= 1 and st["injected"] == 0
        assert "secret-token" not in page_text(at) and "7777.77" not in page_text(at)
        # 既有頁面與導覽仍可操作（確定性規則照常）：切到 📊 再回 💼
        at.radio(key="ui2_page").set_value(P4_MARKET).run()
        assert not at.exception
        assert at.radio(key="ui2_page").value == P4_MARKET


@pytest.mark.slow
def test_ai_is_not_involved_and_demo_works_with_no_ai_configuration(inst, monkeypatch):
    for k in list(os.environ):
        if any(t in k.upper() for t in ("GEMINI", "OPENAI", "ANTHROPIC", "API_KEY", "LLM")):
            monkeypatch.delenv(k, raising=False)
    at = run_app()
    assert has_box(at) and "支持證據" in page_text(at)
    assert import_problems(LAUNCHER_PATH.read_text(encoding="utf-8"), allowed=frozenset({"socket"})) == []


# ══════════════════════════════════════════════════════════════════════
# 3. ui2_browser：真瀏覽器（390×844／1280×900）
# ══════════════════════════════════════════════════════════════════════
from tests.ui2_browser import launch_or_fail, require_browser  # noqa: E402
from tests.ui2_viewport import measure_viewport as MV  # noqa: E402

BOX = ".st-key-ui2_s3l0_topic_box"
VIEWPORTS = {"mobile390": MOBILE, "desktop1280": DESKTOP}


def _start_server(env_extra: dict) -> tuple[subprocess.Popen, str]:
    port = MV._free_port()
    env = {**os.environ, **env_extra}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(LAUNCHER_PATH), "--server.headless", "true",
         "--server.port", str(port), "--browser.gatherUsageStats", "false"],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            return proc, url
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("streamlit server 未在 40 秒內就緒")


@pytest.fixture(scope="module")
def pw():
    sp = require_browser()
    with sp() as p:
        yield p


@pytest.fixture(scope="module")
def browser(pw):
    b = launch_or_fail(pw)
    yield b
    b.close()


@pytest.fixture(scope="module")
def seal_log(tmp_path_factory):
    return tmp_path_factory.mktemp("s3l0") / "seal.jsonl"


@pytest.fixture(scope="module")
def demo_url(seal_log):
    proc, u = _start_server({L.ENV_SEAL_LOG: str(seal_log)})
    yield u
    proc.kill()


@pytest.fixture(scope="module")
def real_url(tmp_path_factory):
    log = tmp_path_factory.mktemp("s3l0real") / "seal.jsonl"
    proc, u = _start_server({L.ENV_SEED: "0", L.ENV_SEAL_LOG: str(log)})
    yield u, log
    proc.kill()


class Page:
    def __init__(self, browser, url, vp, wait_box=True):
        self.ctx = browser.new_context(viewport=vp)
        self.pg = self.ctx.new_page()
        self.errs: list[str] = []
        self.pg.on("pageerror", lambda e: self.errs.append(str(e)))
        self.pg.goto(url)
        self.pg.wait_for_selector(".ui2-pagetitle", timeout=40000)
        if wait_box:
            self.pg.wait_for_selector(BOX, timeout=40000)
        self.pg.wait_for_timeout(600)

    def close(self):
        self.ctx.close()

    def checked_topic(self) -> str:
        return self.pg.evaluate("""(b) => { const i = document.querySelector(b + ' input[type=radio]:checked');
          if (!i) return null; const l = i.closest('label'); return l ? l.innerText.trim() : null; }""", BOX)

    def slot_title(self) -> str:
        return self.pg.evaluate("""() => { const e = document.querySelector('[data-ui2-l1="onebrain"] .ui2-section-title');
          return e ? e.innerText : null; }""")

    def wait_topic(self, topic: str):
        self.pg.wait_for_function(
            "([b, t]) => { const i = document.querySelector(b + ' input[type=radio]:checked'); const l = i && i.closest('label');"
            " const e = document.querySelector('[data-ui2-l1=\"onebrain\"] .ui2-section-title');"
            " return !!l && l.innerText.trim() === t && !!e && e.innerText.indexOf('｜' + t) >= 0; }",
            arg=[BOX, topic], timeout=20000)
        self.pg.wait_for_timeout(250)

    def ax_radios(self):
        cdp = self.ctx.new_cdp_session(self.pg)
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        cdp.detach()
        out = []
        for n in nodes:
            if (n.get("role") or {}).get("value") != "radio" or n.get("ignored"):
                continue
            name = (n.get("name") or {}).get("value", "")
            if name in L.TOPICS:
                props = {p["name"]: (p.get("value") or {}).get("value") for p in n.get("properties", [])}
                out.append((name, props.get("checked")))
        return out

    def focus_checked(self):
        self.pg.focus(BOX + " input[type=radio]:checked")


@pytest.fixture(params=list(VIEWPORTS), ids=list(VIEWPORTS))
def ui(request, browser, demo_url):
    p = Page(browser, demo_url, VIEWPORTS[request.param])
    yield p
    p.close()


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_streamlit_version_matches_expectation():
    import streamlit
    from tests.ui2_browser import EXPECT_ENV, lane_required
    want = os.environ.get(EXPECT_ENV)
    if lane_required():
        assert want, f"browser lane required 時必須設定 {EXPECT_ENV}"
    if want:
        assert streamlit.__version__ == want


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_default_topic_and_one_slot_and_four_labels(ui):
    assert ui.checked_topic() == "持股健檢"
    assert ui.pg.locator('[data-ui2-l1="onebrain"]').count() == 1
    assert ui.pg.locator(BOX).count() == 1
    labels = ui.pg.locator(BOX + " [role=radiogroup] > label").all_inner_texts()
    assert [x.strip() for x in labels] == list(L.TOPICS)
    assert ui.slot_title().count("｜持股健檢｜") == 1


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_keyboard_reaches_and_selects_all_four_topics_with_visible_state(ui):
    ui.pg.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
    # Tab 可進入（不在鍵盤陷阱外：最多 40 次 Tab 內必能停在選擇器的 radio 上）
    reached = False
    for _ in range(40):
        ui.pg.keyboard.press("Tab")
        if ui.pg.evaluate("(b) => !!(document.activeElement && document.activeElement.closest(b))", BOX):
            reached = True
            break
    assert reached, "Tab 走不到四主題選擇器"
    order = ["持股健檢", "反方風險", "持股健檢", "產業前瞻", "大盤"]
    assert ui.checked_topic() == order[0]
    for want in order[1:]:
        key = "ArrowRight" if want in ("反方風險",) else "ArrowLeft"
        ui.pg.keyboard.press(key)
        ui.wait_topic(want)
        assert ui.checked_topic() == want
        assert ui.slot_title().count(f"｜{want}") == 1                       # 文字可辨識（不只靠顏色）
        ax = ui.ax_radios()
        assert sorted(n for n, _ in ax) == sorted(L.TOPICS), ax
        assert [n for n, c in ax if c in (True, "true")] == [want], ax       # AX tree 恰一個 checked＝所選主題
        ui.focus_checked()                                                   # rerun 後焦點可能回 body：重新聚焦再按
    assert ui.pg.locator('[data-ui2-l1="onebrain"]').count() == 1
    assert ui.errs == []


@pytest.mark.slow
@pytest.mark.ui2_browser
@pytest.mark.parametrize("topic", L.TOPICS)
def test_each_topic_no_occlusion_no_horizontal_overflow_single_slot_no_raw_leak(ui, topic):
    ui.pg.locator(BOX + " [role=radiogroup] > label", has_text=topic).click()
    ui.wait_topic(topic)
    assert ui.pg.locator('[data-ui2-l1="onebrain"]').count() == 1
    ov = ui.pg.evaluate("""(box) => { const de = document.documentElement; const w = innerWidth; const bad = [];
      for (const e of document.querySelectorAll('[data-ui2-l1="onebrain"], [data-ui2-l1="onebrain"] *, ' + box + ' *')) {
        const r = e.getBoundingClientRect(); if (r.width && (r.right > w + 1 || r.left < -1)) bad.push(e.className || e.tagName); }
      return {sw: de.scrollWidth, cw: de.clientWidth, bad}; }""", BOX)
    assert ov["sw"] <= ov["cw"] + 1 and ov["bad"] == [], ov
    occl = ui.pg.evaluate("""(box) => { const out = [];
      const targets = [...document.querySelectorAll('[data-ui2-l1="onebrain"] .ui2-section-title, [data-ui2-l1="onebrain"] .ui2-row'),
                       ...document.querySelectorAll(box + ' [role=radiogroup] > label')];
      for (const t of targets) { t.scrollIntoView({block: 'center'}); const r = t.getBoundingClientRect();
        const h = document.elementFromPoint(r.left + r.width / 2, r.top + Math.min(r.height / 2, 12));
        if (!h || !(t.contains(h) || h.contains(t))) out.push((t.className || t.tagName) + ' <- ' + (h ? (h.className || h.tagName) : 'null')); }
      return out; }""", BOX)
    assert occl == [], occl
    body = ui.pg.evaluate("() => document.body.innerText + document.documentElement.innerHTML")
    assert leak_hits(body) == []
    assert forbidden_hits(plain(ui.pg.inner_html('[data-ui2-l1="onebrain"]'))) == []
    shot_dir = os.environ.get("UI2_S3L0_SHOT_DIR")
    if shot_dir:
        Path(shot_dir).mkdir(parents=True, exist_ok=True)
        ui.pg.locator('[data-ui2-l1="onebrain"]').scroll_into_view_if_needed()
        ui.pg.screenshot(path=str(Path(shot_dir) / f"s3l0_{ui.pg.viewport_size['width']}_{topic}.png"))


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_real_default_entry_has_no_demo_selector_or_content(browser, real_url):
    url, _log = real_url
    for vp in VIEWPORTS.values():
        p = Page(browser, url, vp, wait_box=False)
        try:
            for label in ("📊 市場", "💼 持股"):
                loc = p.pg.locator(".st-key-ui2_nav [role='radiogroup'] > label", has_text=label)
                loc.scroll_into_view_if_needed()
                loc.click()
                p.pg.wait_for_timeout(1200)
                assert p.pg.locator(BOX).count() == 0
                txt = p.pg.evaluate("() => document.body.innerText")
                assert "OneBrain 示意" not in txt and "預覽主題" not in txt and "反面證據" not in txt
            assert p.pg.locator('[data-ui2-l1="onebrain"]').count() <= 1
        finally:
            p.close()


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_servers_made_zero_non_loopback_connections(browser, demo_url, real_url, seal_log):
    p = Page(browser, demo_url, MOBILE)
    for topic in L.TOPICS:
        p.pg.locator(BOX + " [role=radiogroup] > label", has_text=topic).click()
        p.wait_topic(topic)
    p.close()
    for log in (seal_log, real_url[1]):
        assert (not Path(log).exists()) or Path(log).read_text(encoding="utf-8").strip() == "", Path(log).read_text()
