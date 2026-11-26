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
    assert b.missing == (L.REASON_CITED_ONLY,)
    # 帶 kind=support 但沒有來源／資料日：同樣不是支持（只能是缺項，且原因分別是固定常數）
    for it, reason in ((L.Item(L.KIND_SUPPORT, "x", None, "2026-11-01"), L.REASON_NO_SOURCE),
                       (L.Item(L.KIND_SUPPORT, "x", "合成來源", None), L.REASON_NO_DATE),
                       (L.Item(L.KIND_SUPPORT, "x", "合成來源", "not-a-date"), L.REASON_NO_DATE)):
        b2 = L.classify((it,))
        assert b2.support == () and b2.missing == (reason,)
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
    f = {x.label: x for x in L.build_fields(L.TOPIC_INDUSTRY)}
    c = f[L.LABEL_COUNTER]
    assert c.status_text == NO_COUNTER_TEXT and c.value_text is None
    assert c.state.value == "undeterminable"               # unknown ≠ safe；不是 OK、不是 0


def split_reasons(text: str) -> list[str]:
    """「缺：a；b（2 項）」／「未採用：a；b（不顯示原值）」→ 原因清單（去掉前綴、去掉『（N 項）』與尾註）。"""
    body = re.sub(r"^(缺：|未採用：)", "", text)
    body = body.replace("（不顯示原值）", "")
    return [re.sub(r"（\d+ 項）$", "", x) for x in body.split("；") if x]


@pytest.mark.parametrize("topic", L.TOPICS)
def test_missing_and_rejected_rows_use_only_the_fixed_public_reason_table(topic):
    f = {x.label: x for x in L.build_fields(topic)}
    for lab, table in ((L.LABEL_MISSING, L.PUBLIC_MISSING_REASONS), (L.LABEL_REJECTED, L.PUBLIC_REJECT_REASONS)):
        row = f[lab]
        if row.value_text:
            reasons = split_reasons(row.value_text)
            assert reasons and all(r in table for r in reasons), (topic, lab, reasons)
        else:
            assert row.status_text and ("無法判定" in row.status_text or "尚未提供" in row.status_text)
    assert len(set(L.PUBLIC_REASONS)) == len(L.PUBLIC_REASONS)


def test_fixture_with_free_text_missing_reason_fails_loud():
    with pytest.raises(ValueError):
        L.classify((L.Item(L.KIND_MISSING, "合成標的乙 缺少最新一季財報"),))
    for it in (i for items in L.FIXTURES.values() for i in items if i.kind == L.KIND_MISSING):
        assert it.text in L.PUBLIC_MISSING_REASONS


@pytest.mark.parametrize("topic", L.TOPICS)
def test_missing_row_never_wears_a_data_missing_chip_and_states_are_not_mixed(topic):
    """三種缺值字樣不混用：尚未提供＝功能未開放；無法判定＝有流程但無輸入；資料未取得只給真的缺資料（本原型的列都不用）。"""
    from shared.ui2_contract import text as T
    for f in L.build_fields(topic):
        st = f.status_text or ""
        assert not st.startswith(T.TEXT_MISSING_NOT_FETCHED), (topic, f.label)
        if f.capability.value == "not_provided":
            assert st.startswith(T.TEXT_NOT_PROVIDED) and f.state is None
        elif st:
            assert st.startswith(T.TEXT_RISK_CAP_UNDETERMINABLE) and f.state.value == "undeterminable"

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


def test_market_topic_commits_to_no_sentence_and_says_preview_in_plain_words():
    title = L._section_title(L.TOPIC_MARKET)
    assert "預覽" in title and "裁示" not in title and "客戶" not in title        # 不把內部決策流程帶給使用者
    f = L.build_fields(L.TOPIC_MARKET)
    assert all(x.value_text is None and x.detail is None for x in f)            # 不寫任何大盤句子（C3／D7 未裁）
    assert all(x.capability.value == "not_provided" and "本主題尚未開放" in x.status_text for x in f)
    blob = "\n".join(_all_visible_strings(L.TOPIC_MARKET))
    for bad in ("裁示", "句型待", "尚未裁", "客戶", "資料未取得"):
        assert bad not in blob, bad


def test_current_topic_falls_back_to_default_on_garbage():
    assert L.current_topic({}) == L.DEFAULT_TOPIC
    assert L.current_topic({L.TOPIC_KEY: "亂碼"}) == L.DEFAULT_TOPIC
    assert L.current_topic({L.TOPIC_KEY: L.TOPIC_COUNTER}) == L.TOPIC_COUNTER
    # 單選可被點掉成 None：還原成最近一次有效主題（不落在「無主題」）
    assert L.current_topic({L.TOPIC_KEY: None, L.LAST_TOPIC_KEY: L.TOPIC_INDUSTRY}) == L.TOPIC_INDUSTRY
    assert L.current_topic({L.TOPIC_KEY: None, L.LAST_TOPIC_KEY: "亂碼"}) == L.DEFAULT_TOPIC


# ══════════════════════════════════════════════════════════════════════
# 1b. fast：文案（工程詞彙／買賣動作／方向字）
# ══════════════════════════════════════════════════════════════════════
def _all_visible_strings(topic: str) -> list[str]:
    out = [L._section_title(topic), L.SELECTOR_LABEL, L.status_text(topic), *L.TOPICS, *L.ROW_LABELS]
    for f in L.build_fields(topic):
        out += [x for x in (f.label, f.value_text, f.status_text, f.detail) if x]
    return out


@pytest.mark.parametrize("topic", L.TOPICS)
def test_visible_copy_has_no_engineering_vocab_no_action_or_direction_words(topic):
    blob = "\n".join(_all_visible_strings(topic))
    assert forbidden_hits(blob) == [], topic
    assert L.SYNTHETIC_MARK in blob or topic in L.NOT_OPEN_TOPICS
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
    "subprocess", "ctypes", "ftplib", "smtplib", "ssl", "telnetlib", "xmlrpc", "webbrowser", "multiprocessing",
    "_socket", "pty", "posix", "popen2", "commands",          # 繞過封網的低階入口（`socket` 本身被 launcher 用來封網，故精確放行）
)
#: 本檔對被測 launcher 的唯一合法 import（模組名含 onebrain 但它是 tests-only 入口，不是決策／OneBrain 模組）。
SELF_ALLOWED_MODULES = frozenset({
    "tests.ui2_viewport.onebrain_s3_l0_launcher", "tests.ui2_viewport", "tests",
    # 既有守衛／Real 取數入口的「只讀引用」（本檔只比對 Real VM 逐值不變、讀 ALLOWED_CALLERS；不新增 caller）
    "tests.test_decision_digest_invariants_guard", "tests.test_decision_digest_invariants_guard.ALLOWED_CALLERS",
    "src.services.ui2.real_feed", "src.services.ui2.real_feed.read_real_snapshot",
    "src.services.ui2.real_canonical", "src.services.ui2.real_canonical.get_real_page_vm",
    "subprocess",                              # 只用於啟動本機 streamlit server 子行程（browser lane）
    "urllib.request",                          # 只用於輪詢本機 127.0.0.1 的 streamlit health（封網下 loopback 不受影響）
    "urllib.request.urlopen",
    "urllib.parse", "urllib.parse.urlsplit",    # 純字串解析（判斷請求是否同源 loopback），不連網
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
    for bad in ("import _socket\n_socket.socket().connect(('93.184.216.34', 80))", "import pty", "import posix\nposix.system('x')",
                "from _socket import socket", "import shared.decision_digest_rules", "from src.services import decision_digest_summary",
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


#: 時鐘存取（含別名）：模組只准 `from datetime import date`（`date.fromisoformat`／建構子），其餘時間模組一律禁止；
#: 任何名為 now／today／time／monotonic… 的屬性取用都算違規（別名 `from datetime import datetime as d; d.now()` 因 import 即違規而擋下）。
CLOCK_MODULES = frozenset({"time", "datetime", "calendar", "zoneinfo", "pytz", "freezegun", "arrow", "pendulum", "sched"})
CLOCK_ATTRS = frozenset({"now", "today", "utcnow", "fromtimestamp", "utcfromtimestamp", "time", "time_ns", "monotonic",
                         "monotonic_ns", "perf_counter", "perf_counter_ns", "process_time", "localtime", "gmtime",
                         "strftime", "sleep", "clock"})


def clock_problems(source: str) -> list[str]:
    bad: list[str] = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Import):
            bad += [f"import {a.name}" for a in n.names if a.name.split(".")[0] in CLOCK_MODULES]
        elif isinstance(n, ast.ImportFrom):
            root = (n.module or "").split(".")[0]
            if root in CLOCK_MODULES:
                names = {a.name for a in n.names}
                if not (root == "datetime" and names <= {"date"}):
                    bad.append(f"from {n.module} import {sorted(names)}")
        elif isinstance(n, ast.Attribute) and n.attr in CLOCK_ATTRS:
            bad.append(f"attr .{n.attr} (line {n.lineno})")
        elif (isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name))
              and (n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id) in ("import_module", "__import__")
              and n.args and isinstance(n.args[0], ast.Constant) and str(n.args[0].value).split(".")[0] in CLOCK_MODULES):
            bad.append("dynamic import of a clock module")
    return bad


#: 外部資源／腳本守衛（S1；與 tests/test_ui2_drawer_js_guard.py 的 SCAN_PATTERNS 同型，另加外連偵測）。掃對象＝launcher 原始碼，
#: 以及它在頁面上實際組出的 HTML／CSS 字串（AppTest 的 markdown 值，見 `test_rendered_html_adds_no_external_resource…`）。
#: 只准 127.0.0.1／localhost／[::1] 的 http(s)／ws(s)；其餘任何 http(s) URL、`url(`／`@import`／`src=`／`href=` 指向外部者一律違規。
_LOOPBACK_URL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
_URL_RX = re.compile(r"(?i)\b(?:https?|wss?|ftp)://([^/\s\"'<>)\\]+)")
_RES_PATTERNS = {
    "<script": r"(?i)<script",
    "on*= attr": r"(?i)\bon[a-z]{3,}\s*=\s*[\"'\\]",
    "javascript:": r"(?i)javascript:",
    "<iframe": r"(?i)<iframe|srcdoc",
    "@import": r"(?i)@import",
    "css url(external)": r"(?i)url\(\s*[\"']?\s*(?:https?:)?//",
    "src/href=external": r"(?i)\b(?:src|href|srcset|action|poster|data|formaction)\s*=\s*[\"']?\s*(?:https?:)?//",
}


def external_resource_problems(text: str) -> list[str]:
    bad = [k for k, p in _RES_PATTERNS.items() if re.search(p, text)]
    for m in _URL_RX.finditer(text):
        host = m.group(1).split("@")[-1]
        if not any(host == h or host.startswith(h + ":") for h in _LOOPBACK_URL_HOSTS):
            bad.append(f"external url host {host}")
    return bad


_EVIL_RESOURCES = (
    '<img src="http://93.184.216.34/x.png" onerror="alert(1)">', "<img src='//evil.example/x'>", "<script>fetch('http://93.184.216.34')</script>",
    "<style>.a{background:url(http://93.184.216.34/a.png)}</style>", "<style>.a{background:url('//evil.example/a')}</style>",
    "<style>@import 'x.css';</style>", '<a href="javascript:void(0)">x</a>', '<div onclick="x()">', '<iframe src="x"></iframe>',
    'X = "https://evil.example/path"', "ws://93.184.216.34/sock",
)


def test_launcher_source_has_no_script_inline_handler_or_external_resource():
    assert external_resource_problems(LAUNCHER_PATH.read_text(encoding="utf-8")) == []


def test_external_resource_guard_has_teeth_and_allows_loopback():
    for bad in _EVIL_RESOURCES:
        assert external_resource_problems(bad), bad
    for ok in ("http://127.0.0.1:8501/_stcore/health", "ws://localhost:8501/_stcore/stream", "<style>.a{color:red}</style>",
               '<div role="status" data-ui2-s3l0-status="1">目前主題：持股健檢</div>'):
        assert external_resource_problems(ok) == [], ok


#: 動態程式碼／動態 import 守衛（SF1）。launcher 唯一需要動態 import 的是 shell／hold 兩個 UI2 模組（為了不改 src 而換掉它們的屬性）：
#: 只准 `importlib.import_module(<模組層字串常數 Name>)`，且該常數的值必須在下列極小白名單內；其餘一切動態手段一律違規。
ALLOWED_DYNAMIC_MODULES = frozenset({"src.ui2.shell.app", "src.ui2.views.hold"})
DYNAMIC_BANNED_NAMES = frozenset({"__import__", "exec", "eval", "compile", "globals", "locals", "vars", "breakpoint", "__builtins__"})
#: `getattr(x, <常數>)` 的屬性名若落在時鐘／網路／動態載入集合 ⇒ 違規（常數表達的是「要取什麼」，必須可審查）。
RISKY_ATTR_NAMES = CLOCK_ATTRS | frozenset({"connect", "connect_ex", "create_connection", "getaddrinfo", "urlopen", "system", "popen",
                                            "import_module", "__import__", "modules", "run", "Popen", "check_output"})


#: 程序／低階系統呼叫入口（`os.system('curl …')` 之類）：任何屬性取用都算違規。
PROCESS_ATTRS = frozenset({"system", "popen", "fork", "forkpty", "startfile", "posix_spawn", "posix_spawnp",
                           "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
                           "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe"})


# ⚠ AST 守衛非窮舉：operator.attrgetter／type().__getattribute__／importlib.util／pkgutil.resolve_name／runpy／別名 sys／
# 把常數改成變數／os.environ 切換等繞法 AST 抓不全，本檔不宣稱窮盡；時鐘／網路類的繞法由行為測試（時鐘函式換成會 raise 的版本）
# 與封網（`seal_network`，含 AppTest／server 兩條路徑的驗證）兜底。
def dynamic_code_problems(source: str) -> list[str]:
    tree = ast.parse(source)
    consts = _const_strs(tree)
    bad: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in DYNAMIC_BANNED_NAMES:
            bad.append(f"name {n.id} (line {n.lineno})")
        elif isinstance(n, ast.Attribute):
            if n.attr in PROCESS_ATTRS:
                bad.append(f"process/system call .{n.attr} (line {n.lineno})")
            if n.attr in DYNAMIC_BANNED_NAMES or n.attr in ("__builtins__", "__dict__", "__globals__", "__subclasses__"):
                bad.append(f"attr .{n.attr} (line {n.lineno})")
            if n.attr == "modules" and isinstance(n.value, ast.Name) and n.value.id == "sys":
                bad.append(f"sys.modules (line {n.lineno})")
        elif isinstance(n, ast.Call):
            fn = n.func.attr if isinstance(n.func, ast.Attribute) else (n.func.id if isinstance(n.func, ast.Name) else None)
            if fn == "import_module":
                a0 = n.args[0] if n.args else None
                ok = (isinstance(n.func, ast.Attribute) and isinstance(a0, ast.Name)       # 只准 `importlib.import_module(<常數>)`；裸呼叫（別名）一律違規
                      and consts.get(a0.id) in ALLOWED_DYNAMIC_MODULES)
                if not ok:
                    bad.append(f"import_module with non-whitelisted target (line {n.lineno})")
            elif fn in ("getattr", "setattr", "delattr", "hasattr") and isinstance(n.func, ast.Name):
                a1 = n.args[1] if len(n.args) > 1 else None
                val = (a1.value if isinstance(a1, ast.Constant) and isinstance(a1.value, str)
                       else consts.get(a1.id) if isinstance(a1, ast.Name) else None)
                if val is None:
                    bad.append(f"{fn} with non-constant attribute name (line {n.lineno})")
                elif val in RISKY_ATTR_NAMES:
                    bad.append(f"{fn} of risky attribute {val!r} (line {n.lineno})")
        elif isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "importlib":
            bad.append("from importlib import … (只准 `import importlib` 後以屬性呼叫)")
    return bad


def test_launcher_has_no_unreviewable_dynamic_code_or_dynamic_imports():
    assert dynamic_code_problems(LAUNCHER_PATH.read_text(encoding="utf-8")) == []
    # 白名單極小且與 launcher 實際使用一致（不多不少）
    assert {L.SHELL_MODULE, L.HOLD_MODULE} == ALLOWED_DYNAMIC_MODULES


_EVIL_DYNAMIC = (
    "import importlib\nimportlib.import_module('date' + 'time')",
    "import importlib\nx = 'time'\nimportlib.import_module(x)",
    "import importlib\nSHELL_MODULE = 'time'\nimportlib.import_module(SHELL_MODULE)",
    "from importlib import import_module as im\nim('os')",
    "__import__('os')",
    "import builtins\nbuiltins.__import__('os')",
    "exec('import time')",
    "eval('1+1')",
    "compile('1', 'x', 'eval')",
    "g = globals()['time']",
    "import sys\nsys.modules['time']",
    "n = 'no' + 'w'\ngetattr(obj, n)",
    "getattr(obj, 'now')",
    "getattr(getattr(m, 'datetime'), 'now')",
    "getattr(sock, 'connect')",
    "vars(m)",
    "import os\nos.system('curl http://93.184.216.34')", "import os\nos.popen('curl x')", "import os\nos.execv('/bin/sh', [])",
    "import os\nos.spawnl(0, 'x')", "import os\nos.posix_spawn('x', [], {})", "import os\nos.fork()",
)


def test_dynamic_code_guard_has_teeth_for_every_bypass():
    for bad in _EVIL_DYNAMIC:
        assert dynamic_code_problems(bad), bad
    ok = ("import importlib\nSHELL_MODULE = 'src.ui2.shell.app'\nimportlib.import_module(SHELL_MODULE)\n"
          "STATE = '_s3l0_state'\ngetattr(obj, STATE, None)\ngetattr(obj, 'after_first', None)")
    assert dynamic_code_problems(ok) == []


def test_launcher_never_touches_the_clock_even_through_aliases():
    assert clock_problems(LAUNCHER_PATH.read_text(encoding="utf-8")) == []


def test_clock_guard_has_teeth_including_alias_bypass():
    for bad in ("from datetime import datetime as d\nx = d.now()", "import datetime\nx = datetime.datetime.now()",
                "from datetime import date as d\nx = d.today()", "import time\nx = time.time()",
                "from time import monotonic as m\nx = m()", "import importlib\nimportlib.import_module('datetime')",
                "import time as t\nt.sleep(1)", "from datetime import datetime, date"):
        assert clock_problems(bad), bad
    assert clock_problems("from datetime import date\nx = date.fromisoformat('2026-11-25')\ny = date(2026, 1, 1)") == []


def test_launcher_output_is_independent_of_the_real_clock(monkeypatch):
    """行為版：把常見的時鐘函式全換成會 raise 的版本，整條夾具→分桶→四列→摘要→規劃路徑仍須照常運作且輸出不變。"""
    import time as _t
    before = {t: (repr(L.build_fields(t)), L.summary_text(t)) for t in L.TOPICS}

    def boom(*a, **k):
        raise AssertionError("launcher 讀了真實時鐘")
    for name in ("time", "monotonic", "perf_counter", "time_ns", "localtime", "gmtime", "strftime"):
        monkeypatch.setattr(_t, name, boom)
    after = {t: (repr(L.build_fields(t)), L.summary_text(t)) for t in L.TOPICS}
    assert after == before


def test_launcher_has_no_filesystem_or_secrets_access_other_than_the_seal_log():
    src = LAUNCHER_PATH.read_text(encoding="utf-8")
    for bad in ("read_text", "write_text", "st.secrets", "environ["):
        assert bad not in src, bad
    opens = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"]
    assert len(opens) == 1                                       # 只有封網記錄檔一處（append）


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
# 2. AppTest 渲染矩陣（每筆 <1s；刻意不標 slow，讓 CI fast lane 就能擋住隔離／外洩／文案的退化）
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


def selector(at):
    return at.button_group(key=L.TOPIC_KEY)


def has_box(at) -> bool:
    return any(b.key == L.TOPIC_KEY for b in at.button_group)


def option_labels(bg) -> tuple:
    return tuple(o.content for o in bg.proto.options)


def page_text(at) -> str:
    """AppTest 裡所有使用者可見文字：markdown（去 style／標籤）＋選擇器標籤與選項＋nav radio＋caption／text。"""
    parts = [plain(v) for v in md_values(at)]
    for r in at.radio:
        parts += [r.label, *r.options]
    for b in at.button_group:
        parts += [b.label, *option_labels(b)]
    parts += [c.value for c in at.caption] + [t.value for t in at.text]
    return "\n".join(parts)


def _walk(block):
    for c in block.children.values():
        if hasattr(c, "children"):
            yield from _walk(c)
        else:
            yield c


def all_widget_proto_text(at) -> str:
    """整頁**所有**元素的 proto（含 widget 的 help／label／placeholder／options／default／tooltip…任何欄位）攤成一個字串。"""
    import json
    from google.protobuf.json_format import MessageToDict
    out = []
    for el in _walk(at.main):
        pr = getattr(el, "proto", None)
        out.append(json.dumps(MessageToDict(pr), ensure_ascii=False) if pr is not None else repr(el))
    return "\n".join(out)


def session_state_text(at) -> str:
    """整個 session_state（所有 key 與 value 的 repr）。"""
    st = at.session_state.filtered_state
    return "\n".join(f"{k!r}: {v!r}" for k, v in st.items())


@pytest.fixture
def inst():
    with installed():
        yield


def test_demo_page_default_topic_selector_and_single_slot(inst):
    at = run_app()
    b = selector(at)
    assert option_labels(b) == L.TOPICS and b.value == "持股健檢" and b.label == L.SELECTOR_LABEL
    vals = md_values(at)
    assert slot_count(vals) == 1
    s = slot_html(vals)
    for lab in L.ROW_LABELS:
        assert f'<div class="ui2-row__label">{lab}</div>' in s
    assert "｜持股健檢｜" in plain(s)
    st = L.get_state()
    assert st["injected"] >= 1 and st["fallbacks"] == 0


@pytest.mark.parametrize("topic", L.TOPICS)
def test_each_topic_renders_four_rows_once_and_never_leaks_rejected_values_anywhere(inst, topic):
    at = run_app(topic=topic)
    vals = md_values(at)
    assert slot_count(vals) == 1
    s = slot_html(vals)
    assert re.findall(r'class="ui2-row__label">([^<]+)<', s) == list(L.ROW_LABELS)
    assert f"｜{topic}" in plain(s)
    assert forbidden_hits(plain(s) + " " + L.SELECTOR_LABEL + " ".join(L.TOPICS)) == []
    # 所有輸出面：markdown／文字、**所有元素 proto（help／label／placeholder／options…）**、**整個 session_state**、VM／摘要
    surfaces = {"markdown": "\n".join(vals), "text": page_text(at), "proto": all_widget_proto_text(at),
                "session_state": session_state_text(at), "vm": repr(L.build_fields(topic)) + L.summary_text(topic)}
    for name, blob in surfaces.items():
        assert leak_hits(blob) == [], (topic, name)
    assert all(k.startswith("ui2_") for k in at.session_state.filtered_state), list(at.session_state.filtered_state)


STATUS_RX = re.compile(r'<div role="status" data-ui2-s3l0-status="1">([^<]*)</div>')


def status_texts(at) -> list[str]:
    return [_html.unescape(t) for v in md_values(at) for t in STATUS_RX.findall(v)]


@pytest.mark.parametrize("topic", L.TOPICS)
def test_status_text_names_the_current_topic_and_is_clean(inst, topic):
    """MF1 補償：1.56 的選擇器控件沒有 aria 選取，改以一行文字（live region）傳達目前主題；恰一條、與選取同步、文字乾淨。"""
    at = run_app(topic=topic)
    assert status_texts(at) == [f"目前主題：{topic}"]
    blob = status_texts(at)[0] + " " + all_widget_proto_text(at) + session_state_text(at)
    assert forbidden_hits(status_texts(at)[0]) == [] and leak_hits(blob) == []


def test_status_text_follows_every_switch_and_each_deselect(inst):
    at = run_app()
    for topic in (L.TOPIC_COUNTER, L.TOPIC_INDUSTRY, L.TOPIC_MARKET, L.TOPIC_HOLDINGS):
        selector(at).set_value(topic).run()
        assert status_texts(at) == [f"目前主題：{topic}"], topic
    at.session_state[L.TOPIC_KEY] = None                       # 點掉 ⇒ 還原最近一次有效主題，狀態文字也不落成「無主題」
    at.run()
    assert status_texts(at) == [f"目前主題：{L.TOPIC_HOLDINGS}"]


def test_status_text_absent_wherever_the_selector_is_absent(real_snapshot_patch):
    with installed():
        for kw in ({"feed": "real"}, {"scenario": "loaded"}, {"page": P4_MARKET}):
            at = run_app(**kw)
            assert status_texts(at) == [] and not any("data-ui2-s3l0-status" in v for v in md_values(at)), kw


@pytest.mark.parametrize("topic", L.TOPICS)
def test_rendered_html_adds_no_external_resource_or_script_versus_uninstalled(inst, topic):
    """launcher 在頁面上實際組出的 HTML／CSS（含狀態列、SLOT_CSS）不得多出任何腳本／行內事件／外部資源（與未安裝版差集）。"""
    on = "\n".join(md_values(run_app(topic=topic)))
    L.uninstall()
    off = "\n".join(md_values(run_app(topic=topic)))
    L.install()
    new_problems = set(external_resource_problems(on)) - set(external_resource_problems(off))
    assert new_problems == set(), new_problems


def test_widget_proto_and_session_state_scanners_have_teeth():
    """掃描器本身：help／label／placeholder／任意 session key 夾帶哨兵必被抓到（突變證明另見回報）。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(f'''
import streamlit as st
st.radio("x", ["a"], help="{L.LEAKY_RAW_VALUES[1]}")
st.text_input("y", placeholder="{L.LEAKY_RAW_VALUES[2]}", help="{L.LEAKY_RAW_VALUES[0]}")
st.segmented_control("z{L.LEAKY_RAW_VALUES[1]}", ["q"], key="ui2_zz")
st.session_state["ui2_anything"] = "{L.LEAKY_RAW_VALUES[0]}"
''').run()
    assert not at.exception
    blob = all_widget_proto_text(at)
    assert all(v in blob for v in L.LEAKY_RAW_VALUES), blob[:400]
    assert L.LEAKY_RAW_VALUES[0] in session_state_text(at)
    assert leak_hits(blob) and leak_hits(session_state_text(at))


def test_no_counter_row_and_missing_row_and_rejected_row_are_each_covered_in_dom(inst):
    s_ind = plain(slot_html(md_values(run_app(topic=L.TOPIC_INDUSTRY))))
    assert NO_COUNTER_TEXT in s_ind                          # 無反證 ⇒ 無法判定（無反證輸入）
    assert "⬜ 無法判定（無拒用輸入）" in s_ind
    assert f"缺：{L.REASON_NO_PEER}" in s_ind
    s_hold = plain(slot_html(md_values(run_app(topic=L.TOPIC_HOLDINGS))))
    assert f"缺：{L.REASON_CITED_ONLY}；{L.REASON_NO_FINANCIALS}" in s_hold                 # 引用 ⇒ 缺項，不當支持；原因＝固定常數
    assert f"未採用：{L.REASON_STALE}；{L.REASON_PIT}（不顯示原值）" in s_hold                  # 拒用：只有固定原因
    assert "法說會" not in s_hold and "資料未取得" not in s_hold
    s_counter = plain(slot_html(md_values(run_app(topic=L.TOPIC_COUNTER))))
    assert "風險上限" not in s_counter                       # Risk Cap 不推反證，也不出現在槽內
    assert "⬜ 無法判定（無支持輸入）" in s_counter
    s_market = plain(slot_html(md_values(run_app(topic=L.TOPIC_MARKET))))
    assert s_market.count("⬜ 尚未提供（本主題尚未開放）") == 4 and "無法判定" not in s_market and "資料未取得" not in s_market
    assert "預覽" in s_market and "裁示" not in s_market


def test_garbage_topic_in_session_falls_back_to_default(inst):
    at = run_app(topic="亂碼")
    assert selector(at).value == L.DEFAULT_TOPIC
    assert "｜持股健檢｜" in plain(slot_html(md_values(at)))


def test_switching_topic_rerenders_slot_and_deselect_restores_last_topic(inst):
    at = run_app()
    for topic in (L.TOPIC_COUNTER, L.TOPIC_INDUSTRY, L.TOPIC_MARKET, L.TOPIC_HOLDINGS):
        selector(at).set_value(topic).run()
        assert not at.exception
        assert f"｜{topic}" in plain(slot_html(md_values(at))) and slot_count(md_values(at)) == 1
    selector(at).set_value(L.TOPIC_COUNTER).run()
    at.session_state[L.TOPIC_KEY] = None                      # 使用者在單選按鈕組上把已選項點掉
    at.run()
    assert not at.exception and selector(at).value == L.TOPIC_COUNTER
    assert f"｜{L.TOPIC_COUNTER}" in plain(slot_html(md_values(at)))


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
    assert all_widget_proto_text(on) == all_widget_proto_text(off) and session_state_text(on) == session_state_text(off)


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


def test_real_on_every_page_never_gets_selector_or_demo_content(real_snapshot_patch):
    with installed():
        for pid in PAGE_IDS:
            at = run_app(feed="real", page=pid)
            t = page_text(at)
            assert not has_box(at), pid
            assert "OneBrain 示意" not in t and "支持證據" not in t, pid
            assert L.TOPIC_KEY not in session_state_text(at) and L.LAST_TOPIC_KEY not in session_state_text(at)


@pytest.mark.parametrize("scenario", [s for s in SCENARIO_IDS if s != SCENARIO_COLD])
def test_plain_fake_hold_in_non_cold_scenarios_has_no_demo_and_is_identical(scenario):
    off = run_app(scenario=scenario)
    with installed():
        on = run_app(scenario=scenario)
        assert not has_box(on) and L.get_state()["injected"] == 0
    assert md_values(on) == md_values(off)


@pytest.mark.parametrize("page", [P4_MARKET, P4_TARGET, P4_ME, P4_DATA])
def test_fake_cold_on_non_hold_pages_has_no_demo_and_is_identical(page):
    off = run_app(page=page)
    with installed():
        on = run_app(page=page)
        assert not has_box(on) and L.get_state()["injected"] == 0
    assert md_values(on) == md_values(off)


def test_fixture_failure_falls_back_to_original_slot_and_page_stays_operable(monkeypatch, caplog):
    L.uninstall()
    off = run_app()
    monkeypatch.setattr(L, "build_fields", lambda topic: (_ for _ in ()).throw(RuntimeError("secret-token 7777.77")))
    with installed():
        with caplog.at_level("DEBUG"):
            at = run_app()
        assert md_values(at) == md_values(off) and not has_box(at)       # 退回原本的「尚未提供」槽、無選擇器
        st = L.get_state()
        assert st["fallbacks"] >= 1 and st["injected"] == 0
        assert "secret-token" not in page_text(at) and "7777.77" not in page_text(at)
        # 既有頁面與導覽仍可操作（確定性規則照常）：切到 📊 再回 💼
        at.radio(key="ui2_page").set_value(P4_MARKET).run()
        assert not at.exception
        assert at.radio(key="ui2_page").value == P4_MARKET
    # log：必須有 fail-closed 的記錄（非空洞），且只含例外「型別名」，不含例外訊息、夾具原值，也沒有 exc_info／traceback
    mine = [r for r in caplog.records if r.name == L.__name__]
    assert mine and any("RuntimeError" in r.getMessage() for r in mine)
    for r in caplog.records:
        text = r.getMessage() + " " + str(r.args) + " " + (r.exc_text or "")
        assert "secret-token" not in text and "7777.77" not in text, text
        if r.name == L.__name__:
            assert r.exc_info is None
    assert "secret-token" not in caplog.text and "7777.77" not in caplog.text


def test_ai_is_not_involved_and_demo_works_with_no_ai_configuration(inst, monkeypatch):
    for k in list(os.environ):
        if any(t in k.upper() for t in ("GEMINI", "OPENAI", "ANTHROPIC", "API_KEY", "LLM")):
            monkeypatch.delenv(k, raising=False)
    at = run_app()
    assert has_box(at) and "支持證據" in page_text(at)
    assert import_problems(LAUNCHER_PATH.read_text(encoding="utf-8"), allowed=frozenset({"socket"})) == []


def test_launcher_main_really_seals_the_network_and_logs_a_start_marker(tmp_path, monkeypatch):
    """走真入口（`main()`，AppTest 以 `__main__` 執行 launcher 檔）：必須①封網確實啟動（socket 被換）②seal log 存在且第一行＝啟動標記
    ③頁面落在 💼 FAKE cold 並有選擇器④封網下零拒絕。拿掉 main 的 `seal_network` 呼叫 ⇒ 本測試必紅（空洞通過已堵）。"""
    import json
    from streamlit.testing.v1 import AppTest
    log = tmp_path / "seal.jsonl"
    monkeypatch.setenv(L.ENV_SEAL_LOG, str(log))
    L.unseal_network()
    L.uninstall()
    try:
        assert getattr(socket, L.SEAL_ATTR, None) is None
        at = AppTest.from_file(str(LAUNCHER_PATH), default_timeout=90)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
        assert getattr(socket, L.SEAL_ATTR, None) is not None, "main() 沒有啟用封網"
        lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert lines and lines[0]["kind"] == L.SEAL_MARKER_KIND and lines[0]["pid"] == os.getpid()
        assert lines[1:] == []                                   # 只有啟動標記，沒有被拒絕的連線
        assert has_box(at) and selector(at).value == L.DEFAULT_TOPIC
        with pytest.raises(OSError, match="network sealed"):     # 此時對外連線真的會被拒（`__main__` 版的例外類別與 L 不同，故比對訊息）
            socket.create_connection(("93.184.216.34", 80), timeout=1)
        denied = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()][1:]
        assert [d["kind"] for d in denied] == ["create_connection"]
    finally:
        L.unseal_network()
        L.uninstall()


def test_main_seals_the_network_even_without_the_seal_log_env_var(monkeypatch):
    """封網不依賴環境變數：未設 `UI2_S3_L0_SEAL_LOG` 時 `main()` 仍必須封網（只是不留記錄）。"""
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv(L.ENV_SEAL_LOG, raising=False)
    L.unseal_network()
    L.uninstall()
    try:
        assert getattr(socket, L.SEAL_ATTR, None) is None
        at = AppTest.from_file(str(LAUNCHER_PATH), default_timeout=90)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
        st = getattr(socket, L.SEAL_ATTR, None)
        assert st is not None and st["log_path"] is None, "沒有 env 時 main() 沒有封網"
        with pytest.raises(OSError, match="network sealed"):
            socket.create_connection(("93.184.216.34", 80), timeout=1)
        assert has_box(at)
    finally:
        L.unseal_network()
        L.uninstall()


def test_selector_draw_failure_logs_only_the_exception_type_and_keeps_the_page_up(monkeypatch, caplog):
    """選擇器畫不出來：不得拖垮頁面（槽仍在）；log 只記例外型別名，不含例外訊息／夾具原值，也沒有 traceback。"""
    def boom():
        raise RuntimeError("secret-token 7777.77 原值哨兵甲")
    monkeypatch.setattr(L, "_draw_selector", boom)
    with installed():
        with caplog.at_level("DEBUG"):
            at = run_app()
        vals = md_values(at)
        assert slot_count(vals) == 1 and not has_box(at)                 # 槽照常（已規劃的 VM），只是沒有選擇器
    mine = [r for r in caplog.records if r.name == L.__name__ and "selector failed" in r.getMessage()]
    assert mine and all("RuntimeError" in r.getMessage() and r.exc_info is None for r in mine)
    for r in caplog.records:
        text = r.getMessage() + " " + str(r.args) + " " + (r.exc_text or "")
        assert "secret-token" not in text and "7777.77" not in text and "原值哨兵" not in text, text
    assert "secret-token" not in caplog.text and "7777.77" not in caplog.text
    assert "secret-token" not in page_text(at)


# ══════════════════════════════════════════════════════════════════════
# 3. ui2_browser：真瀏覽器（390×844／1280×900）
# ══════════════════════════════════════════════════════════════════════
# ── Streamlit 1.56 鍵盤調查（成因＋緩解；本檔 `test_known_limitation_*` 以可觀察斷言記錄）────────────────────────
# 現象（QA-2）：選擇器若用 `st.radio`，在 1.56.0 於最後一項按 → 或第一項按 ←，焦點會跳進上方頁面導覽並直接切換頁籤；1.59.2 正常。
# 成因（DOM 實測）：1.56（BaseWeb）渲染的每個 `<input type=radio>` 的 `name` 都是空字串，且無 `<form>`／`fieldset` 分組。
#   Chromium 把整份文件所有「name 為空」的 radio 視為同一個方向鍵群組 ⇒ 頁面導覽 radio（同為 name=""）與選擇器 radio 同組，
#   選擇器最後一項再往後＝回繞到文件中第一個 name="" 的 radio＝導覽第一項（📊），選取即切頁。1.59.2（react-aria）每組各自 role=radiogroup。
#   導覽是既有檔（src/ui2）⇒ 不能在範圍內改它的分組。
# 緩解（只改 launcher）：選擇器改用原生 `st.segmented_control`（按鈕組，不是 radio ⇒ 不與導覽共組）。兩版實測：
#   1.56＝四顆按鈕各一個 Tab 停點，方向鍵不作用，Space／Enter 選取；1.59.2＝roving，Tab 進出一個停點，方向鍵在群組內移動且停在邊界，Space／Enter 選取。
#   兩版皆不會因邊界方向鍵切走頁籤。代價（已知限制，如實記錄）：1.56 的 segmented_control 沒有 ARIA 選取狀態（AX tree 無 checked／selected），
#   選取只靠視覺樣式（`stBaseButton-segmented_controlActive`）＋槽標題的文字（「｜持股健檢｜」）；1.59.2 有 role=radio＋aria-checked。
from tests.ui2_browser import launch_or_fail, require_browser  # noqa: E402
from tests.ui2_viewport import measure_viewport as MV  # noqa: E402

BOX = ".st-key-ui2_s3l0_topic_box"
VIEWPORTS = {"mobile390": MOBILE, "desktop1280": DESKTOP}


def streamlit_minor() -> tuple:
    import streamlit
    return tuple(int(x) for x in streamlit.__version__.split(".")[:2])


def start_streamlit(script: Path, env_extra: dict | None = None) -> tuple[subprocess.Popen, str]:
    port = MV._free_port()
    env = {**os.environ, **(env_extra or {})}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(script), "--server.headless", "true",
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


class Server:
    def __init__(self, env_extra: dict, log: Path):
        self.log = log
        self.proc, self.url = start_streamlit(LAUNCHER_PATH, {L.ENV_SEAL_LOG: str(log), **env_extra})

    def seal_lines(self) -> list[dict]:
        import json
        if not self.log.exists():
            return []
        return [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines() if x.strip()]


def assert_server_sealed(srv: Server) -> None:
    """封網**確實啟動**：log 必須存在、第一行是啟動標記且 pid＝該 server 進程；其後沒有任何被拒絕的連線。
    （舊版把「log 不存在」當通過＝空洞：launcher 根本沒封網也會綠。）"""
    lines = srv.seal_lines()
    assert lines, f"seal log 不存在或為空：封網沒有啟動（{srv.log}）"
    assert lines[0]["kind"] == L.SEAL_MARKER_KIND and lines[0]["pid"] == srv.proc.pid, lines[0]
    assert lines[1:] == [], lines[1:]


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
def demo(tmp_path_factory):
    srv = Server({}, tmp_path_factory.mktemp("s3l0") / "seal.jsonl")
    yield srv
    srv.proc.kill()


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    srv = Server({L.ENV_SEED: "0"}, tmp_path_factory.mktemp("s3l0real") / "seal.jsonl")
    yield srv
    srv.proc.kill()


_SELECTED_JS = """(box) => { const bs = [...document.querySelectorAll(box + ' button')];
  const on = bs.filter(b => b.getAttribute('aria-checked') === 'true' || b.getAttribute('data-selected') === 'true'
                            || (b.getAttribute('data-testid') || '').endsWith('Active'));
  return on.map(b => b.innerText.trim()); }"""


def _allowed_origin(url: str, origin: str) -> bool:
    """同源 loopback（server 自身 host:port；含 ws://同源）或無網路的內嵌 scheme（data:／blob:／about:）。"""
    from urllib.parse import urlsplit
    u, o = urlsplit(url), urlsplit(origin)
    if u.scheme in ("data", "blob", "about"):
        return True
    return u.hostname == o.hostname and (u.port or {"http": 80, "ws": 80, "https": 443, "wss": 443}.get(u.scheme)) == o.port \
        and u.scheme in ("http", "https", "ws", "wss")


class Page:
    def __init__(self, browser, url, vp, wait_box=True):
        self.ctx = browser.new_context(viewport=vp)
        self.pg = self.ctx.new_page()
        self.errs: list[str] = []
        self.requests: list[str] = []          # 所有請求（含被擋的）；`external` 為其中非同源 loopback 者
        self.external: list[str] = []
        self.origin = url
        self.pg.on("pageerror", lambda e: self.errs.append(str(e)))

        def _route(route):                      # 外連一律中止並記錄（⛔ 不放行）；同源 loopback 照常放行
            u = route.request.url
            self.requests.append(u)
            if _allowed_origin(u, self.origin):
                route.continue_()
            else:
                self.external.append(u)
                route.abort()
        self.ctx.route("**/*", _route)
        # 雙保險：request 事件（含 route 以外的 ws／子資源）＋ WebSocket 目的地
        self.pg.on("request", lambda r: None if _allowed_origin(r.url, self.origin) or r.url in self.external
                   else self.external.append(r.url))
        self.pg.on("websocket", lambda w: None if _allowed_origin(w.url, self.origin) else self.external.append(w.url))
        self.ws: list[str] = []
        self.pg.on("websocket", lambda w: self.ws.append(w.url))
        self.pg.goto(url)
        self.pg.wait_for_selector(".ui2-pagetitle", timeout=40000)
        if wait_box:
            self.pg.wait_for_selector(BOX, timeout=40000)
        self.pg.wait_for_timeout(600)

    def close(self):
        self.ctx.close()

    def assert_no_external_requests(self):
        """零外連：除同源 loopback（含 ws）外沒有任何請求；且不是空洞（確實攔到同源請求、也看到 websocket）。"""
        assert self.requests and any("_stcore" in u or u.rstrip("/") == self.origin.rstrip("/") for u in self.requests), self.requests[:5]
        assert self.external == [], self.external

    def selected(self) -> list[str]:
        return self.pg.evaluate(_SELECTED_JS, BOX)

    def slot_title(self) -> str | None:
        return self.pg.evaluate("""() => { const e = document.querySelector('[data-ui2-l1="onebrain"] .ui2-section-title');
          return e ? e.innerText : null; }""")

    def wait_topic(self, topic: str):
        self.pg.wait_for_function(
            "([b, t]) => { const bs = [...document.querySelectorAll(b + ' button')]; const on = bs.filter(x => x.getAttribute('aria-checked') === 'true'"
            " || x.getAttribute('data-selected') === 'true' || (x.getAttribute('data-testid') || '').endsWith('Active'));"
            " const e = document.querySelector('[data-ui2-l1=\"onebrain\"] .ui2-section-title');"
            " return on.length === 1 && on[0].innerText.trim() === t && !!e && e.innerText.indexOf('｜' + t) >= 0; }",
            arg=[BOX, topic], timeout=20000)
        self.pg.wait_for_timeout(250)

    def active_desc(self) -> dict:
        return self.pg.evaluate("""(box) => { const a = document.activeElement;
          return {tag: a.tagName, text: (a.innerText || '').trim(), where: a.closest(box) ? 'topic' : (a.closest('.st-key-ui2_nav') ? 'nav' : 'other'),
                  page: document.querySelector('.ui2-pagetitle').dataset.ui2Page,
                  navChecked: (() => { const i = document.querySelector('.st-key-ui2_nav input[type=radio]:checked'); const l = i && i.closest('label'); return l ? l.innerText.trim() : null; })()}; }""", BOX)

    def page_id(self) -> str:
        return self.pg.evaluate("() => document.querySelector('.ui2-pagetitle').dataset.ui2Page")

    def ax_selected_topics(self):
        """AX tree 裡「已選取」的主題（role=radio 且 checked）；沒有暴露選取狀態 ⇒ 空清單。"""
        cdp = self.ctx.new_cdp_session(self.pg)
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        cdp.detach()
        out, seen = [], []
        for n in nodes:
            if (n.get("role") or {}).get("value") != "radio" or n.get("ignored"):
                continue
            name = (n.get("name") or {}).get("value", "")
            if name in L.TOPICS:
                seen.append(name)
                props = {p["name"]: (p.get("value") or {}).get("value") for p in n.get("properties", [])}
                if props.get("checked") in (True, "true"):
                    out.append(name)
        return seen, out

    def focus_start(self):
        self.pg.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")

    def tab_into_box(self, limit=40):
        for _ in range(limit):
            self.pg.keyboard.press("Tab")
            if self.active_desc()["where"] == "topic":
                return
        raise AssertionError("Tab 走不到四主題選擇器")

    def focus_topic(self, topic: str):
        """純鍵盤走到指定主題的按鈕：先 Tab 進群組，再依版本用 Tab（1.56：每顆各一停點，只能往後）或方向鍵（1.59：群組內 roving，
        進入點可能是上次離開的那一顆，故依目前位置決定左右）移動。"""
        self.focus_start()
        self.tab_into_box()
        roving = streamlit_minor() >= (1, 59)
        want = L.TOPICS.index(topic)
        for _ in range(8):
            cur = self.active_desc()["text"]
            if cur == topic:
                return
            if roving:
                self.pg.keyboard.press("ArrowRight" if L.TOPICS.index(cur) < want else "ArrowLeft")
            else:
                self.pg.keyboard.press("Tab")
        raise AssertionError(f"鍵盤走不到 {topic}")


@pytest.fixture(params=list(VIEWPORTS), ids=list(VIEWPORTS))
def ui(request, browser, demo):
    p = Page(browser, demo.url, VIEWPORTS[request.param])
    yield p
    try:
        p.assert_no_external_requests()          # 每個 browser 測試結束時都核一次：零外連
    finally:
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
    assert ui.selected() == ["持股健檢"]
    assert ui.pg.locator('[data-ui2-l1="onebrain"]').count() == 1
    assert ui.pg.locator(BOX).count() == 1
    labels = [x.strip() for x in ui.pg.locator(BOX + " button").all_inner_texts()]
    assert labels == list(L.TOPICS)
    assert ui.slot_title().count("｜持股健檢｜") == 1


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_selector_is_adjacent_to_the_slot_and_both_are_on_the_first_screen(ui):
    """QA-2：選擇器緊貼在 OneBrain 槽正上方（中間不夾「建議持股水位」等其他區塊），且選擇器與槽標題在首屏同時可見（不需捲動）。"""
    g = ui.pg.evaluate("""(box) => { const b = document.querySelector(box).getBoundingClientRect();
      const t = document.querySelector('[data-ui2-l1="onebrain"] .ui2-section-title').getBoundingClientRect();
      const between = [...document.querySelectorAll('[data-ui2-l1]')].filter(e => e.dataset.ui2L1 !== 'onebrain')
        .filter(e => { const r = e.getBoundingClientRect(); return r.height > 0 && r.top >= b.bottom - 1 && r.top < t.top; })
        .map(e => e.dataset.ui2L1);
      return {boxTop: b.top, boxBottom: b.bottom, titleTop: t.top, titleBottom: t.bottom, vh: innerHeight, scrollY, between}; }""", BOX)
    assert g["scrollY"] == 0 and g["between"] == [], g
    assert g["boxBottom"] <= g["titleTop"] and g["titleTop"] - g["boxBottom"] <= 80, g          # 相鄰（只隔一個元素間距）
    assert g["titleBottom"] < g["vh"] and g["boxTop"] >= 0, g                                    # 同屏可見（未捲動）
    ui.pg.locator(BOX + " button", has_text="反方風險").click()
    ui.wait_topic("反方風險")
    g2 = ui.pg.evaluate("""() => { const t = document.querySelector('[data-ui2-l1="onebrain"] .ui2-section-title').getBoundingClientRect();
      return {titleBottom: t.bottom, vh: innerHeight, scrollY}; }""")
    assert g2["scrollY"] == 0 and g2["titleBottom"] < g2["vh"], g2          # 切換後變化仍在首屏內


@pytest.mark.slow
@pytest.mark.ui2_browser
@pytest.mark.parametrize("topic", L.TOPICS)
def test_keyboard_only_selects_every_topic_and_selection_is_visible(ui, topic):
    ui.focus_topic(topic)
    assert ui.active_desc()["where"] == "topic" and ui.active_desc()["page"] == "p4_hold"
    ui.pg.keyboard.press("Space")
    ui.wait_topic(topic)
    assert ui.selected() == [topic]                                      # 視覺選取（DOM 狀態）恰一個
    assert ui.slot_title().count(f"｜{topic}") == 1                      # 文字可辨識（不只靠顏色）
    seen, checked = ui.ax_selected_topics()
    if streamlit_minor() >= (1, 59):
        assert sorted(seen) == sorted(L.TOPICS) and checked == [topic], (seen, checked)   # AX tree 恰一個 checked
    else:
        # 已知限制（1.56.0）：segmented_control 沒有 ARIA 選取狀態 ⇒ AX tree 沒有任何 radio／checked。
        # 若 Streamlit 升版修好，本斷言會變紅，提醒回頭更新這段調查註解。
        assert seen == [] and checked == []
    assert ui.pg.locator('[data-ui2-l1="onebrain"]').count() == 1 and ui.errs == []


def ax_static_texts(page: Page) -> list[str]:
    cdp = page.ctx.new_cdp_session(page.pg)
    nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
    cdp.detach()
    return [(n.get("name") or {}).get("value", "") for n in nodes
            if not n.get("ignored") and (n.get("role") or {}).get("value") == "StaticText"]


@pytest.mark.slow
@pytest.mark.ui2_browser
@pytest.mark.parametrize("topic", L.TOPICS)
def test_ax_tree_exposes_the_current_topic_in_both_streamlit_versions(ui, topic):
    """MF1：輔助科技要能得知目前主題。補償（不是真正的 ARIA 選取）：以文字傳達——AX tree 恰有一條「目前主題：X」。
    1.59.2 另有 role=radio＋checked＝所選主題；1.56.0 的控件本身仍無 aria 選取（已知限制，見 test_keyboard_only… 的斷言）。"""
    ui.pg.locator(BOX + " button", has_text=topic).click()
    ui.wait_topic(topic)
    texts = [t for t in ax_static_texts(ui) if t.startswith(L.STATUS_PREFIX)]
    assert texts == [L.status_text(topic)], texts
    assert ui.pg.locator('[role="status"][data-ui2-s3l0-status]').count() == 1
    seen, checked = ui.ax_selected_topics()
    if streamlit_minor() >= (1, 59):
        assert checked == [topic], (seen, checked)
    else:
        assert checked == []                                              # 1.56：控件本身仍無 aria 選取（補償只是文字）
    assert forbidden_hits(texts[0]) == [] and leak_hits("\n".join(ax_static_texts(ui))) == []


@pytest.mark.slow
@pytest.mark.ui2_browser
@pytest.mark.parametrize("vp", list(VIEWPORTS))
def test_no_external_requests_or_websockets_across_all_topics_and_switching(browser, demo, vp):
    """S1：以 `context.route('**/*')`＋request／websocket 事件攔截並記錄所有請求；除同源 loopback 外零外連。
    涵蓋載入、四主題各切換一次、再切回預設；且確實看到同源 websocket（非空洞）。"""
    p = Page(browser, demo.url, VIEWPORTS[vp])
    try:
        for topic in (*L.TOPICS, L.DEFAULT_TOPIC):
            p.pg.locator(BOX + " button", has_text=topic).click()
            p.wait_topic(topic)
        p.pg.wait_for_timeout(500)
        p.assert_no_external_requests()
        assert p.ws and all(_allowed_origin(w, demo.url) for w in p.ws), p.ws
        assert all(_allowed_origin(u, demo.url) for u in p.requests), [u for u in p.requests if not _allowed_origin(u, demo.url)]
    finally:
        p.close()


def test_allowed_origin_helper_has_teeth():
    o = "http://127.0.0.1:8501"
    assert _allowed_origin("http://127.0.0.1:8501/_stcore/health", o) and _allowed_origin("ws://127.0.0.1:8501/_stcore/stream", o)
    assert _allowed_origin("data:image/png;base64,AAAA", o)
    for bad in ("http://93.184.216.34/x.png", "http://127.0.0.1:9999/x", "http://localhost:8501/x", "https://fonts.googleapis.com/css",
                "ws://93.184.216.34/s", "http://127.0.0.1/x"):
        assert not _allowed_origin(bad, o), bad


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_keyboard_edges_never_leave_the_selector_or_switch_the_page(ui):
    """QA-2 Should-Fix-1：最後一項按 →、第一項按 ←、Shift+Tab 離開群組，都不得切走頁籤（頁面 id 與導覽選取不變）。"""
    base = ui.active_desc()
    assert base["page"] == "p4_hold" and base["navChecked"] == "💼 持股"
    ui.focus_topic(L.TOPICS[-1])
    for _ in range(3):
        ui.pg.keyboard.press("ArrowRight")
        ui.pg.wait_for_timeout(700)
    d = ui.active_desc()
    assert d["page"] == "p4_hold" and d["navChecked"] == "💼 持股" and d["where"] in ("topic", "other"), d
    ui.focus_topic(L.TOPICS[0])
    for _ in range(3):
        ui.pg.keyboard.press("ArrowLeft")
        ui.pg.wait_for_timeout(700)
    d = ui.active_desc()
    assert d["page"] == "p4_hold" and d["navChecked"] == "💼 持股" and d["where"] in ("topic", "other"), d
    ui.pg.keyboard.press("Shift+Tab")
    d = ui.active_desc()
    assert d["page"] == "p4_hold" and d["navChecked"] == "💼 持股", d
    assert ui.selected() == ["持股健檢"]                                  # 方向鍵／Shift+Tab 沒有悄悄改選主題
    assert ui.pg.locator('[data-ui2-l1="onebrain"]').count() == 1 and ui.errs == []


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_tab_order_nav_then_selector_then_leaves_without_trap(ui):
    ui.focus_start()
    seq = []
    for _ in range(12):
        ui.pg.keyboard.press("Tab")
        d = ui.active_desc()
        seq.append((d["where"], d["text"][:12]))
        assert d["page"] == "p4_hold"
    where = [w for w, _ in seq]
    first_nav, first_topic = where.index("nav"), where.index("topic")
    assert first_nav < first_topic, seq                                  # 導覽在前、選擇器在後
    topic_stops = [t for w, t in seq[:first_topic + 4] if w == "topic"]
    assert topic_stops and topic_stops == list(L.TOPICS)[:len(topic_stops)], seq   # 群組內依 DOM 順序（1.56：四顆；1.59：roving 一個）
    after_group = where[first_topic:]
    leave = next((i for i, w in enumerate(after_group) if w == "other"), None)       # 第一次走出選擇器（Tab 不被困）
    assert leave is not None and "topic" in after_group[:leave], f"Tab 被困在選擇器內：{seq}"


@pytest.mark.slow
@pytest.mark.ui2_browser
@pytest.mark.parametrize("topic", L.TOPICS)
def test_each_topic_no_occlusion_no_horizontal_overflow_single_slot_no_raw_leak(ui, topic):
    ui.pg.locator(BOX + " button", has_text=topic).click()
    ui.wait_topic(topic)
    assert ui.pg.locator('[data-ui2-l1="onebrain"]').count() == 1
    ov = ui.pg.evaluate("""(box) => { const de = document.documentElement; const w = innerWidth; const bad = [];
      for (const e of document.querySelectorAll('[data-ui2-l1="onebrain"], [data-ui2-l1="onebrain"] *, ' + box + ' *')) {
        const r = e.getBoundingClientRect(); if (r.width && (r.right > w + 1 || r.left < -1)) bad.push(e.className || e.tagName); }
      return {sw: de.scrollWidth, cw: de.clientWidth, bad}; }""", BOX)
    assert ov["sw"] <= ov["cw"] + 1 and ov["bad"] == [], ov
    occl = ui.pg.evaluate("""(box) => { const out = [];
      const targets = [...document.querySelectorAll('[data-ui2-l1="onebrain"] .ui2-section-title, [data-ui2-l1="onebrain"] .ui2-row'),
                       ...document.querySelectorAll(box + ' button, ' + box + ' [data-ui2-s3l0-status]')];
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
        ui.pg.evaluate("() => window.scrollTo(0, 0)")
        ui.pg.screenshot(path=str(Path(shot_dir) / f"s3l0_{ui.pg.viewport_size['width']}_{topic}.png"))


_ATTRS_JS = """() => { const out = []; for (const e of document.querySelectorAll('*')) for (const a of e.attributes) out.push(a.name + '=' + a.value);
  return out.join('\\n'); }"""


@pytest.mark.slow
@pytest.mark.ui2_browser
@pytest.mark.parametrize("topic", L.TOPICS)
def test_no_raw_value_in_any_element_attribute_title_aria_data_or_tooltip(ui, topic):
    """所有元素的**全部屬性**（title／aria-*／data-*／placeholder／alt…）與所有 widget 的 help tooltip 都不得含拒用原值；
    選擇器沒有 help／tooltip（掃描對象明確列舉，不靠多一個 Tab 停點之類的巧合）。"""
    ui.pg.locator(BOX + " button", has_text=topic).click()
    ui.wait_topic(topic)
    attrs = ui.pg.evaluate(_ATTRS_JS)
    assert attrs and leak_hits(attrs) == []
    assert ui.pg.locator(BOX + ' [data-testid="stTooltipIcon"], ' + BOX + " [aria-describedby]").count() == 0
    tips = ui.pg.locator('[data-testid="stTooltipIcon"], [data-testid="stTooltipHoverTarget"]')
    texts = []
    for i in range(tips.count()):
        tips.nth(i).hover()
        ui.pg.wait_for_timeout(250)
        texts.append(ui.pg.evaluate("() => [...document.querySelectorAll('[data-testid=\"stTooltipContent\"], [role=tooltip]')].map(e => e.innerText).join('|')"))
    assert leak_hits("\n".join(texts)) == []


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_real_default_entry_has_no_demo_selector_or_content(browser, real):
    for vp in VIEWPORTS.values():
        p = Page(browser, real.url, vp, wait_box=False)
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
            p.assert_no_external_requests()
        finally:
            p.close()


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_servers_really_sealed_and_made_zero_non_loopback_connections(browser, demo, real):
    p = Page(browser, demo.url, MOBILE)
    for topic in L.TOPICS:
        p.pg.locator(BOX + " button", has_text=topic).click()
        p.wait_topic(topic)
    p.close()
    q = Page(browser, real.url, MOBILE, wait_box=False)
    q.close()
    assert_server_sealed(demo)
    assert_server_sealed(real)


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_known_limitation_streamlit_1_56_radios_share_one_unnamed_group(browser, tmp_path):
    """成因證據（見本節檔頭調查）：兩個獨立 `st.radio`（模擬頁面導覽＋選擇器）。
    1.56.0：所有 radio input 的 name 皆為空字串，第二組最後一項按 → 會回繞並選到第一組第一項（跨組跳動）。
    1.59.2：分組正確，不跳動。其他版本不下斷言（調查只針對 floor 與目前 resolver 版本）。"""
    app = tmp_path / "two_radios.py"
    app.write_text('import streamlit as st\nst.radio("nav", ["n1", "n2"], key="ui2_nav_x", horizontal=True)\n'
                   'st.radio("topic", ["t1", "t2"], key="ui2_topic_x", horizontal=True)\n', encoding="utf-8")
    proc, url = start_streamlit(app)
    try:
        ctx = browser.new_context(viewport=DESKTOP)
        pg = ctx.new_page()
        pg.goto(url)
        pg.wait_for_selector(".st-key-ui2_topic_x input[type=radio]", state="attached", timeout=40000)
        pg.wait_for_timeout(600)
        names = pg.evaluate("() => [...document.querySelectorAll('input[type=radio]')].map(i => i.name)")
        for box in (".st-key-ui2_nav_x", ".st-key-ui2_topic_x"):                # 各組以方向鍵選到第 2 項（1.56／1.59 都支援；label 點擊在 1.59 無效）
            pg.focus(box + " input[type=radio]:checked")
            pg.keyboard.press("ArrowRight")
            pg.wait_for_timeout(800)
        pg.focus(".st-key-ui2_topic_x input[type=radio]:checked")               # 此時選擇器在最後一項；導覽在第 2 項（值 "1"）
        pg.keyboard.press("ArrowRight")                                        # 最後一項再按 →
        pg.wait_for_timeout(1000)
        nav_checked = pg.evaluate("() => { const i = document.querySelector('.st-key-ui2_nav_x input[type=radio]:checked'); return i ? i.value : null; }")
        ctx.close()
    finally:
        proc.kill()
    minor = streamlit_minor()
    if minor == (1, 56):
        assert set(names) == {""}, names                       # 成因：name 全為空
        assert nav_checked == "0", nav_checked                  # 跨組跳動：回繞到導覽第一項並選取（導覽原本選第 2 項＝"1"）
    elif minor == (1, 59):
        assert all(names), names
        assert nav_checked == "1", nav_checked                  # 不跳動：導覽仍停在第 2 項


