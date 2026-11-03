"""New UI2 UI Correction P1 —— 使用者畫面「無工程字樣／無可見題號／無重複標籤／預設道無 Preview 控制」守衛。

出處：客戶 2026-11-03 (16) P1 第 2 項；Active Presentation Contract §6／§9／§11（題號與工程字樣 INFERENCE）、DEC-128／130；
`docs/BACKLOG.md` §5.1.26 `T-new-2`。T_new_2 / T_new_5 / T_new_9 的最小斷言在 `test_ui2_contract_teeth_pending.py`；
本檔是它們的完整版：**具名詞彙清單 × 四頁 × 各場景 × FAKE／Real**（排除開發面）。

掃描對象＝使用者實際看到的文字：
1. VM 層：`PageVM` 內全部會被 view 渲染成文字的字串（label／value／status／detail／title／CTA／freshness 的 as_of／來源）；
2. 渲染層：AppTest 整頁 markdown（去 `<style>`、去開發面標題區塊、去 HTML 標籤）。
兩層都掃，避免「VM 乾淨但 view 又加了字」或反過來。

⛔ 允許清單只有一項：客戶要求的 Real-data 單行標示 `REAL_PREVIEW_BANNER_TEXT`（含 `Preview`、`production default`）。
"""
from __future__ import annotations

import dataclasses
import re
from enum import Enum
from pathlib import Path

import pytest

from shared import regime_arbiter as RA
from shared.ui2_contract import text as T
from shared.ui2_contract.models import PageVM
from shared.ui2_contract.pages import ACCOUNT_IDS, P4_ME, PAGE_IDS, SCENARIO_IDS
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import (
    RealFeedSnapshot, RegimeFact, TwiiFact, get_real_page_vm,
)

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"

#: 具名工程詞彙清單（Active Contract §9／ui_gap_B G6／BACKLOG T-new-2）。比對方式：子字串（大小寫敏感者另註）。
ENGINEERING_VOCAB: tuple[str, ...] = (
    "Preview", "尚未接線", "接線", "PORT", "Gate", "Stage", "Aggregator", "Headless", "session", "Session",
    "路徑 C", "OAuth", "nonce", "契約", "canonical", "Legacy", "第二套規則", "workspace", "macro_state",
    "規則分支", "DEC-", "traceback", "Traceback", "Exception", "src.", ".py", "詳見 log", "fake data",
)
#: 層級標記（獨立字詞，避免誤傷 "L1" 以外的英數）：標題上外顯的「（L2）」「（L3）」「L2 明細」。
_LAYER_RX = re.compile(r"(?<![A-Za-z0-9])L[1-6](?![A-Za-z0-9])")
_NUMBERED_RX = re.compile(r"[①②③④⑤]")
#: 唯一允許：客戶要求的 Real-data 單行標示。
_ALLOWED_PHRASES = (T.REAL_PREVIEW_BANNER_TEXT,)

_SKIP_KEYS = {"section_id", "card_id", "page_id", "scenario_id", "mode_id", "default_mode", "account_state",
              "level", "mode", "active_mode", "visible_card_ids"}


#: 渲染層略過、只留 VM 的「治理參照句」（`T.is_dev_only_text`）——這裡逐一記帳，測試再斷言它們**只**可能是 L0 逐字常數。
DROPPED_DEV_ONLY: list[str] = []


def _walk_strings(obj, out: list[str], key: str = "") -> None:
    if isinstance(obj, Enum):
        return                                # 狀態列舉值（"ok"／"not_provided"…）是內部識別，不是畫面文字
    if isinstance(obj, str):
        if key not in _SKIP_KEYS:
            if key == "detail" and T.is_dev_only_text(obj):
                DROPPED_DEV_ONLY.append(obj)
                return
            out.append(obj)
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            v = getattr(obj, f.name)
            if f.name == "source" and isinstance(v, str) and v.startswith(T.RULE_BRANCH_SOURCE_PREFIX):
                continue                  # 規則分支 id＝provenance，只在 VM；現行 view 不渲染（Real 渲染層掃描另證）
            _walk_strings(v, out, f.name)
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            _walk_strings(x, out, key)


def vm_visible_text(vm: PageVM) -> str:
    out: list[str] = []
    _walk_strings(vm, out)
    return "\n".join(out)


def hits_in(text: str) -> list[str]:
    for ph in _ALLOWED_PHRASES:
        text = text.replace(ph, "")
    found = [w for w in ENGINEERING_VOCAB if w in text]
    found += sorted(set(_LAYER_RX.findall(text)))
    found += sorted(set(_NUMBERED_RX.findall(text)))
    return found


# ── Real 模式固定 snapshot（不讀本機檔，結果可重現）────────────────────────────
def _twii(**kw) -> TwiiFact:
    base = dict(ok=True, close=(23456.789,), as_of="2026-11-02", is_stale=False, stale_reason="", age_days=1,
                has_upstream_error=False, error_type="", failed=False, source="本地加權指數歷史快取")
    base.update(kw)
    return TwiiFact(**base)


def _snapshots() -> dict[str, RealFeedSnapshot]:
    unloaded = RegimeFact("unknown", "⬜", RA.SOURCE_UNLOADED, False)
    unevald = RegimeFact("unknown", "⬜", RA.SOURCE_UNEVALUATED_BREADTH, False)
    bull = RegimeFact("bull", "🟢", RA.SOURCE_BULL_SCORE, True)
    S = RealFeedSnapshot.of
    return {
        "loaded": S(_twii(), "", bull, ""),
        "unloaded": S(_twii(), "", unloaded, ""),
        "unevaluated": S(_twii(), "", unevald, ""),
        "stale": S(_twii(is_stale=True, age_days=5, stale_reason="已 5 天沒有新資料"), "", unloaded, ""),
        "stale_unknown": S(_twii(is_stale=None, age_days=None), "", unloaded, ""),
        "missing": S(_twii(ok=False, close=(), as_of=None), "", unloaded, ""),
        "upstream_error": S(_twii(has_upstream_error=True), "", unloaded, ""),
        "unavailable": S(None, "OSError", None, "RuntimeError"),
        "contract_error": S(None, "RealFeedContractError", None, "RealFeedContractError"),
    }


# ══════════════════════════════════════════════════════════════════ VM 層
@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_fake_vm_visible_text_has_no_engineering_vocabulary(page, scenario):
    accounts = ACCOUNT_IDS if page == P4_ME else (None,)
    for acct in accounts:
        vm = get_preview_page_vm(page, scenario, account=acct)
        assert hits_in(vm_visible_text(vm)) == [], f"{page}/{scenario}/{acct}"


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("name", list(_snapshots()))
def test_real_vm_visible_text_has_no_engineering_vocabulary(page, name):
    vm = get_real_page_vm(page, _snapshots()[name])
    assert hits_in(vm_visible_text(vm)) == [], f"{page}/{name}"


def test_only_the_verbatim_l0_explain_constants_are_withheld_from_the_human_ui():
    """被 render 略過（只留 VM）的句子，必須**僅是** L0 `regime_arbiter.*_EXPLAIN` 逐字常數（客戶裁示原文，含 DEC 編號／狀態檔名）。
    任何新的「含 DEC-／macro_state.json／backtick」的 detail 都不得靠這條路偷渡出現在 VM 又被默默隱藏。"""
    DROPPED_DEV_ONLY.clear()
    for name, snap in _snapshots().items():
        for page in PAGE_IDS:
            vm_visible_text(get_real_page_vm(page, snap))
    for page in PAGE_IDS:
        for sc in SCENARIO_IDS:
            vm_visible_text(get_preview_page_vm(page, sc))
    assert DROPPED_DEV_ONLY, "Real 模式 unloaded／unevaluated 應有 L0 說明被略過（否則本守衛沒在掃）"
    for d in set(DROPPED_DEV_ONLY):
        assert RA.NOT_LOADED_PENDING_BREADTH_EXPLAIN in d or RA.UNEVALUATED_BREADTH_EXPLAIN in d, d


def test_vocabulary_scanner_has_teeth():
    """mutation：把工程字樣塞進任何一個欄位 → 掃描器必須抓到（防掃描器本身壞掉而假綠）。"""
    vm = get_preview_page_vm("p4_market", "loaded")
    assert hits_in(vm_visible_text(vm)) == []
    f0 = vm.context.cards[0].field
    for bad in ("尚未接線：PORT 至 L3", "Stage G 前不提供", "待 System Action Aggregator", "路徑 C", "OAuth nonce",
                "詳見 log", "規則分支 id：x", "標題（L2）", "① 現在狀態", "DEC-074", "macro_state.json"):
        mutated = dataclasses.replace(vm, context=dataclasses.replace(
            vm.context, cards=(dataclasses.replace(vm.context.cards[0], field=dataclasses.replace(f0, value_text=bad)),)))
        assert hits_in(vm_visible_text(mutated)), bad
    # 允許清單不是萬用豁免：Real 單行標示本身放行，但同一句後面夾工程字樣仍要抓
    assert hits_in(T.REAL_PREVIEW_BANNER_TEXT) == []
    assert hits_in(T.REAL_PREVIEW_BANNER_TEXT + "（Gate）") == ["Gate"]


def test_banner_constants_are_one_liners_without_engineering_words():
    assert hits_in(T.PREVIEW_BANNER_TEXT + T.PREVIEW_BANNER_NOTE) == []
    assert hits_in(T.REAL_PREVIEW_BANNER_NOTE) == []
    assert "FAKE" in T.PREVIEW_BANNER_TEXT                   # FAKE 資料不得被誤認為真資料（示意資料標示保留）
    assert T.REAL_PREVIEW_BANNER_TEXT == "Real-data Preview（非正式 production default）"   # 客戶 (11) 要求逐字
    assert "\n" not in T.PREVIEW_BANNER_TEXT + T.PREVIEW_BANNER_NOTE + T.REAL_PREVIEW_BANNER_NOTE


# ══════════════════════════════════════════════════════════════════ 渲染層（AppTest 整頁）
def _at(dev: bool):
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    if dev:
        a.query_params["ui2_dev"] = "1"
    return a.run(timeout=60)


def rendered_human_text(at) -> str:
    parts = [m.value for m in at.markdown if 'data-ui2-dev="1"' not in m.value]
    html = re.sub(r"<style>.*?</style>", "", "\n".join(parts), flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def _rendered_html(at) -> str:
    parts = [m.value for m in at.markdown if 'data-ui2-dev="1"' not in m.value]
    return re.sub(r"<style>.*?</style>", "", "\n".join(parts), flags=re.S)


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_rendered_fake_pages_have_no_engineering_vocabulary_numbering_or_duplicate_labels(scenario):
    at = _at(dev=True)                                       # 要切場景才需要開發面；掃描時排除開發面區塊
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    for page in PAGE_IDS:
        at.radio(key="ui2_page").set_value(page).run(timeout=60)
        assert not at.exception, f"{page}/{scenario}"
        if page == "p4_target":
            for mode in ("curated", "lookup"):
                at.radio(key="ui2_target_mode").set_value(mode).run(timeout=60)
                assert hits_in(rendered_human_text(at)) == [], f"{page}/{scenario}/{mode}"
            at.radio(key="ui2_target_mode").set_value("curated").run(timeout=60)
        if page == P4_ME:
            for acct in ACCOUNT_IDS:
                at.selectbox(key="ui2_account").set_value(acct).run(timeout=60)
                assert hits_in(rendered_human_text(at)) == [], f"{page}/{scenario}/{acct}"
            at.selectbox(key="ui2_account").set_value("signed_in").run(timeout=60)
        text, html = rendered_human_text(at), _rendered_html(at)
        assert hits_in(text) == [], f"{page}/{scenario}"
        # 題號鷹架不可見，但量測／測試錨點與結構仍在
        assert 'data-ui2-q="q1"' in html and 'data-ui2-q="q2"' in html, page
        assert text.count("是否需要行動") <= 1, f"{page}/{scenario}: 『是否需要行動』重複 {text.count('是否需要行動')} 次"


def test_market_page_has_each_first_screen_label_once_and_keeps_anchors():
    at = _at(dev=False)
    html, text = _rendered_html(at), rendered_human_text(at)
    for qid in ("q1", "q2", "q3", "q4", "concl", "ctx"):
        assert f'data-ui2-q="{qid}"' in html, qid           # 錨點全數保留
    assert 'class="ui2-m-l1"' in html and "ui2-risk" in html
    assert text.count("OneBrain Outlook") == 1              # 標題與列標籤合併為一次
    for label in ("是否需要行動", "下一步", "今日結論", "市場目前狀態"):
        assert text.count(label) == 1, (label, text.count(label))


def test_target_and_me_first_screen_labels_are_not_numbered_but_anchors_remain():
    at = _at(dev=False)
    at.radio(key="ui2_page").set_value("p4_target").run(timeout=60)
    html = _rendered_html(at)
    assert not _NUMBERED_RX.search(rendered_human_text(at))
    assert all(f'data-ui2-q="{q}"' in html for q in ("q1", "ctx", "q2", "q3", "q4"))
    at.radio(key="ui2_page").set_value(P4_ME).run(timeout=60)
    html = _rendered_html(at)
    assert not _NUMBERED_RX.search(rendered_human_text(at))
    assert all(f'data-ui2-q="{q}"' in html for q in ("q1", "q2", "q3", "q4"))


def test_real_mode_rendered_pages_have_no_engineering_vocabulary_except_the_required_banner(monkeypatch):
    from src.ui2.shell import app as shell
    for name, snap in _snapshots().items():
        monkeypatch.setattr(shell, "read_real_snapshot", lambda s=snap: s)
        at = _at(dev=True)
        at.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
        for page in PAGE_IDS:
            at.radio(key="ui2_page").set_value(page).run(timeout=60)
            assert not at.exception, f"{page}/{name}"
            text = rendered_human_text(at)
            assert T.REAL_PREVIEW_BANNER_TEXT in text         # 客戶要求的單行標示仍在
            assert hits_in(text) == [], f"{page}/{name}"
            assert _rendered_html(at).count('class="ui2-banner"') == 1


def test_default_lane_never_shows_the_dev_surface_but_dev_lane_marks_it_non_product():
    plain, dev = _at(dev=False), _at(dev=True)
    assert 'data-ui2-dev="1"' not in "\n".join(m.value for m in plain.markdown)
    heads = [m.value for m in dev.markdown if 'data-ui2-dev="1"' in m.value]
    assert len(heads) == 1 and "🧪 開發／測試工具（非產品內容）" in heads[0]


def test_streamlit_toolbar_and_deploy_button_are_hidden_by_ui2_css_only():
    from src.ui2.shell.css import CSS
    assert 'stToolbar' in CSS and 'stAppDeployButton' in CSS and 'stMainMenu' in CSS
    # 只在 UI2 入口的 CSS 內；不動 .streamlit/config.toml（那會連帶影響 Legacy app）
    cfg = (ROOT / ".streamlit" / "config.toml")
    if cfg.exists():
        assert "toolbarMode" not in cfg.read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════ viewport 判定器（P1 兩條）teeth
def test_viewport_p1_evaluators_have_teeth():
    from tests.ui2_viewport import measure_viewport as MV
    ids = {t["id"] for t in MV.THRESHOLDS}
    assert {"p1_human_text_clean", "p1_banner_single_line"} <= ids
    out = lambda: {i: [] for i in ids}        # noqa: E731
    ok = out()
    MV._evaluate_p1({"product_text": "市場目前狀態 ⬜ 尚未載入", "banner_box": {"height": 26.0, "lineHeight": 18.0}}, ok)
    assert not any(ok.values())
    bad = out()
    MV._evaluate_p1({"product_text": "尚未接線：PORT 至 L3 ① 現在狀態", "banner_box": {"height": 46.0, "lineHeight": 18.0}}, bad)
    assert bad["p1_human_text_clean"] and bad["p1_banner_single_line"]
    legacy = out()                            # 舊版量測 dict（無這兩個鍵）→ 略過，不誤判
    MV._evaluate_p1({}, legacy)
    assert not any(legacy.values())
