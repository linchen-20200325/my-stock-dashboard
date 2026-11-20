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
    # QA 追加（P3）：FAKE microtag／內部場景用語
    "scenario", "ASOF", "冷啟動", "占位", "placeholder", "FAKE·",
    # B-UI2-STALE-COPY-1（DEC-213）：L1 `compute_cache_staleness` 過期說明句的工程字樣（資料集檔名／門檻）不得上畫面。
    # 假陽性量測（改動前）：FAKE 五頁×全場景、Real 九組 snapshot×五頁、AppTest 渲染皆 0 命中。
    "twii_ohlcv", "門檻", "parquet",
)
#: 例外型別名（`OSError`、`RuntimeError`、`RealFeedContractError`…）不得上畫面：型別名只留 log／snapshot。
_ERROR_SUFFIX_RX = re.compile(r"\b\w+(?:Error|Exception)\b")
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
    found += sorted(set(m.group(0) for m in _ERROR_SUFFIX_RX.finditer(text)))
    found += sorted(set(_LAYER_RX.findall(text)))
    found += sorted(set(_NUMBERED_RX.findall(text)))
    return found


# ── Real 模式固定 snapshot（不讀本機檔，結果可重現）────────────────────────────
def _twii(**kw) -> TwiiFact:
    base = dict(ok=True, close=(23456.789,), as_of="2026-11-02", is_stale=False, stale_reason="", age_days=1,
                has_upstream_error=False, error_type="", failed=False, source="本地加權指數歷史快取")
    base.update(kw)
    return TwiiFact(**base)


# ── 真 L1 過期原因字串（B-UI2-STALE-COPY-1）──────────────────────────────────────
# 不再手寫「人話版」fixture（那正是舊守衛漏接的原因）：逐字取自 L1 `macro_cache_reader.compute_cache_staleness`
# 對 `twii_ohlcv` 的真實輸出（合成 df＋注入 today；無 I/O、無時鐘）。
def _real_l1_stale_reasons() -> dict[str, str]:
    import datetime as dt
    import tempfile

    import pandas as pd

    from src.data.macro.macro_cache_reader import compute_cache_staleness
    today = dt.date(2026, 11, 20)
    out: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:                 # 空目錄＝無 metadata（L1 讀不到即視為無）
        cache_dir = Path(tmp)
        for name, dates in (("over_threshold", ["2026-11-06", "2026-11-09"]),       # 距今 11 天 > daily 門檻
                            ("future", ["2026-11-25"])):                              # 資料日晚於今日
            df = pd.DataFrame({"date": pd.to_datetime(dates), "close": [1.0] * len(dates)})
            out[name] = compute_cache_staleness("twii_ohlcv", cache_dir=cache_dir, df=df, today=today)["reason"]
        out["no_date"] = compute_cache_staleness(
            "twii_ohlcv", cache_dir=cache_dir, df=pd.DataFrame({"close": [1.0]}), today=today)["reason"]
    return out


REAL_L1_STALE_REASONS: dict[str, str] = _real_l1_stale_reasons()
REAL_L1_OVER_THRESHOLD: str = REAL_L1_STALE_REASONS["over_threshold"]


def _snapshots() -> dict[str, RealFeedSnapshot]:
    unloaded = RegimeFact("unknown", "⬜", RA.SOURCE_UNLOADED, False)
    unevald = RegimeFact("unknown", "⬜", RA.SOURCE_UNEVALUATED_BREADTH, False)
    bull = RegimeFact("bull", "🟢", RA.SOURCE_BULL_SCORE, True)
    S = RealFeedSnapshot.of
    return {
        "loaded": S(_twii(), "", bull, ""),
        "unloaded": S(_twii(), "", unloaded, ""),
        "unevaluated": S(_twii(), "", unevald, ""),
        "stale": S(_twii(is_stale=True, age_days=5, stale_reason=REAL_L1_OVER_THRESHOLD), "", unloaded, ""),
        "stale_unknown": S(_twii(is_stale=None, age_days=None, stale_reason=REAL_L1_STALE_REASONS["no_date"]),
                           "", unloaded, ""),
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


# ── 三軸文案：Capability 欄位的原因句不得讀成 Missing（資料缺）；Missing 欄位不得讀成「尚未開放」──────────
#: Missing 軸字樣（資料缺）／Capability 軸字樣（功能未開放）。各自只准出現在自己那一軸的欄位 detail。
MISSING_AXIS_WORDS = ("資料未備", "資料未取得", "尚無資料", "無資料")
CAPABILITY_AXIS_WORDS = ("尚未開放", "尚未提供")


def _all_fields(vm) -> list:
    from shared.ui2_contract.models import FieldVM
    out: list = []

    def walk(o):
        if isinstance(o, FieldVM):
            out.append(o)
        elif dataclasses.is_dataclass(o) and not isinstance(o, type):
            for f in dataclasses.fields(o):
                walk(getattr(o, f.name))
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x)
    walk(vm)
    return out


def _axis_violations(vm) -> list[str]:
    from shared.ui2_contract.models import CapabilityState, FieldState
    bad = []
    for f in _all_fields(vm):
        d = f.detail or ""
        if f.capability is CapabilityState.NOT_PROVIDED:
            bad += [f"capability『{f.label}』的原因含 Missing 軸字樣 {w!r}：{d}" for w in MISSING_AXIS_WORDS if w in d]
        elif f.state is FieldState.MISSING:
            bad += [f"Missing『{f.label}』的原因含 Capability 軸字樣 {w!r}：{d}" for w in CAPABILITY_AXIS_WORDS if w in d]
    return bad


@pytest.mark.parametrize("page", PAGE_IDS)
def test_capability_and_missing_copy_never_cross_axes(page):
    for scenario in SCENARIO_IDS:
        accounts = ACCOUNT_IDS if page == P4_ME else (None,)
        for acct in accounts:
            assert _axis_violations(get_preview_page_vm(page, scenario, account=acct)) == [], f"{page}/{scenario}/{acct}"
    for name, snap in _snapshots().items():
        assert _axis_violations(get_real_page_vm(page, snap)) == [], f"{page}/{name}"


def test_axis_copy_guard_has_teeth():
    vm = get_real_page_vm("p4_market", _snapshots()["loaded"])
    assert _axis_violations(vm) == []
    f0 = next(f for f in _all_fields(vm) if f.label == "VIX")
    bad_cap = dataclasses.replace(f0, detail="此項目前尚無資料")
    assert _axis_violations(dataclasses.replace(vm, context=dataclasses.replace(
        vm.context, cards=(dataclasses.replace(vm.context.cards[1], field=bad_cap),)))), "capability 讀成缺資料 → 要被抓"
    from shared.ui2_contract.models import FieldState
    miss = dataclasses.replace(f0, capability=type(f0.capability).PROVIDED, state=FieldState.MISSING,
                               status_text=T.TEXT_MISSING_NOT_READY, detail="此功能尚未開放")
    assert _axis_violations(dataclasses.replace(vm, context=dataclasses.replace(
        vm.context, cards=(dataclasses.replace(vm.context.cards[1], field=miss),)))), "Missing 讀成尚未開放 → 要被抓"


def test_error_type_names_never_reach_the_screen():
    snap = _snapshots()["unavailable"]
    for page in ("p4_market", "p4_target"):
        text = vm_visible_text(get_real_page_vm(page, snap))
        assert "OSError" not in text and "RuntimeError" not in text and "暫時無法讀取" in text
    assert snap.twii_error == "OSError" and snap.regime_error == "RuntimeError"      # 型別名仍在 snapshot（內部／log）
    assert hits_in("台股加權指數讀取失敗（OSError）") == ["OSError"]
    assert hits_in("RealFeedContractError") == ["RealFeedContractError"]


def test_regime_see_why_premise_breadth_proxy_scoring_is_off():
    """`REGIME_SEE_WHY`「尚缺正式的市場廣度」的前提＝廣度代理值不計分（DEC-074）。改 True 時須重審文案與 L0 說明。"""
    from shared import signal_thresholds as ST
    assert ST.BREADTH_PROXY_SCORING_ENABLED is False, "BREADTH_PROXY_SCORING_ENABLED 變了：重審 REGIME_SEE_WHY 與 L0 *_EXPLAIN 文案"


def test_shown_warns_instead_of_silently_hiding_unknown_governance_text(capsys):
    from src.ui2.components import html as H
    assert H.shown("普通原因句") is True
    assert H.shown(RA.NOT_LOADED_PENDING_BREADTH_EXPLAIN + "。x") is False
    assert capsys.readouterr().out == ""                          # 已知 L0 常數：安靜略過
    assert H.shown("工程句（DEC-999）") is False
    assert "WARNING" in capsys.readouterr().out                   # 未知治理參照句：略過但不沉默


def test_vocabulary_scanner_has_teeth():
    """mutation：把工程字樣塞進任何一個欄位 → 掃描器必須抓到（防掃描器本身壞掉而假綠）。"""
    vm = get_preview_page_vm("p4_market", "loaded")
    assert hits_in(vm_visible_text(vm)) == []
    f0 = vm.context.cards[0].field
    for bad in ("尚未接線：PORT 至 L3", "Stage G 前不提供", "待 System Action Aggregator", "路徑 C", "OAuth nonce",
                "詳見 log", "規則分支 id：x", "標題（L2）", "① 現在狀態", "DEC-074", "macro_state.json",
                "FAKE·scenario", "FAKE-ASOF", "FAKE 冷啟動", "Holdings（占位）", "OSError"):
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


def test_expander_labels_have_no_text_arrow_prefix_streamlit_draws_its_own():
    """QA P3-7：摺疊列已有 Streamlit 自帶箭頭，標題不再加文字「▸」（雙箭頭）。區塊本身仍在（P3 才移除），故只驗前綴。"""
    at = _at(dev=False)
    for page in PAGE_IDS:
        at.radio(key="ui2_page").set_value(page).run(timeout=60)
        labels = [e.label for e in at.expander]
        assert all(not lb.lstrip().startswith("▸") for lb in labels), (page, labels)


# ══════════════════════════════════════════════════════════════════ B-UI2-STALE-COPY-1（DEC-213）
# 台股卡與日 K 的 Real 詳情不得原樣輸出 L1 `stale_reason`（資料集檔名／門檻字樣）。
# 守衛用**真 L1 字串**（`REAL_L1_STALE_REASONS`，逐字取自 `compute_cache_staleness`），不是手寫人話版。
_L1_JARGON = ("twii_ohlcv", "門檻", "daily", "parquet")


def test_real_l1_stale_reason_premise_still_holds():
    """前提釘住：真 L1 過期句確實含工程字樣。L1 改寫成人話時此測試轉紅 → 重審本批的「不外露」做法是否仍必要。"""
    r = REAL_L1_OVER_THRESHOLD
    assert "twii_ohlcv" in r and "門檻" in r and "daily" in r and "2026-11-09" in r and "11 天" in r, r
    assert "twii_ohlcv" in REAL_L1_STALE_REASONS["no_date"] and "twii_ohlcv" in REAL_L1_STALE_REASONS["future"]


def _stale_card_kbar_snapshot(reason: str, *, is_stale=True, age_days: int | None = 11, as_of="2026-11-09",
                              upstream_state: str = "") -> RealFeedSnapshot:
    """經真 feed（`read_real_snapshot`）跑：只把 L3 service 換成回傳「帶真 L1 過期句」的 `TwiiTrendView`。"""
    from src.services import allocation_service, market_twii_view_service as TWS
    from src.services.ui2 import real_feed as RF
    xs = tuple(f"2026-10-{d:02d}" for d in range(12, 31)) + (as_of,)
    xs = tuple(sorted(set(xs)))[-20:]
    n = len(xs)
    c = tuple(23000.0 + i * 10 for i in range(n))
    o = tuple(v - 5 for v in c)
    h = tuple(v + 20 for v in c)
    lo = tuple(v - 30 for v in c)
    base = dict(ok=True, xs=xs, close=c, n_available=100, as_of=as_of, is_stale=is_stale, stale_reason=reason,
                age_days=age_days, upstream_error="", upstream_state=upstream_state, error="", failed=False)
    kbar = TWS.TwiiTrendView(**base, ohlc_requested=True, ohlc_ok=True, ohlc_error="", ohlc_detail="",
                             open=o, high=h, low=lo, n_ohlc=n)
    card = TWS.TwiiTrendView(**{**base, "xs": (xs[-1],), "close": (c[-1],)})
    regime = {"regime": "bull", "light": "🟢", "source": RA.SOURCE_BULL_SCORE, "trend_regime": None, "health": None,
              "defense": False, "exposure_limit_pct": None, "traffic_light": None, "is_loaded": True,
              "risk_cap_disclosure": None}
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(TWS, "get_twii_trend_view", lambda n_, **kw: kbar if kw.get("with_ohlc") else card)
        mp.setattr(allocation_service, "get_macro_regime", lambda **kw: regime)
        return RF.read_real_snapshot()
    finally:
        mp.undo()


def test_stale_real_l1_text_never_reaches_card_or_kbar_visible_text():
    from shared.ui2_contract.models import FieldState
    from src.ui2.components import html as H
    snap = _stale_card_kbar_snapshot(REAL_L1_OVER_THRESHOLD)
    # 內部事實仍保留原句（稽核用）：不是把資料模型洗掉
    assert snap.twii.stale_reason == REAL_L1_OVER_THRESHOLD and snap.kbar.stale_reason == REAL_L1_OVER_THRESHOLD
    vm = get_real_page_vm("p4_market", snap)
    card, kbar = vm.context.cards[0], vm.context.kbar
    assert kbar is not None and len(kbar.candles) == 20
    # VM 可見文本（detail／狀態字樣／資料日／來源）＋ 實際 HTML 都不含 L1 工程字樣
    html_card, html_kbar = H.metric_card_html(card), H.kbar_chart_html(kbar)
    visible = vm_visible_text(vm) + "\n" + html_card + "\n" + html_kbar
    for w in _L1_JARGON:
        assert w not in visible, (w, "出現在台股卡／日 K 可見文本")
    assert hits_in(visible) == []
    # 既有可顯示資訊仍在：⚠ 過期 N 天 chip、資料日、來源
    for fld in (card.field, kbar.field):
        assert fld.state is FieldState.STALE and fld.status_text == T.stale_text(11) == "⚠ 過期 11 天"
        assert fld.freshness.as_of == "2026-11-09" and fld.freshness.source
        assert not fld.detail                                           # 沒有其他已核准字樣時＝空，不是工程句
    for h_ in (html_card, html_kbar):
        assert "⚠ 過期 11 天" in h_ and "2026-11-09" in h_
        assert card.field.freshness.source in h_
    # 其餘四頁（含 🗂 各項明細的台股列）也不外洩
    for page in PAGE_IDS:
        txt = vm_visible_text(get_real_page_vm(page, snap))
        assert not [w for w in _L1_JARGON if w in txt], page


@pytest.mark.parametrize("name", ["over_threshold", "no_date", "future"])
def test_every_real_l1_reason_variant_stays_hidden_in_every_stale_branch(name):
    from shared.ui2_contract.models import FieldState
    reason = REAL_L1_STALE_REASONS[name]
    for kw in (dict(is_stale=True, age_days=11), dict(is_stale=True, age_days=None), dict(is_stale=None, age_days=None)):
        snap = _stale_card_kbar_snapshot(reason, **kw)
        vm = get_real_page_vm("p4_market", snap)
        card_f, kbar_f = vm.context.cards[0].field, vm.context.kbar.field
        for f in (card_f, kbar_f):
            assert f.state is FieldState.STALE
            assert reason not in (f.detail or "") and not [w for w in _L1_JARGON if w in (f.detail or "")]
        # 新鮮度未判定（is_stale=None）：既有已核准字樣仍在，不被一併洗掉
        if kw["is_stale"] is None:
            assert card_f.detail == kbar_f.detail == "新鮮度未判定"
            assert card_f.status_text == T.TEXT_STALE_UNKNOWN
        elif kw["age_days"] is None:
            assert card_f.status_text == T.TEXT_STALE_UNKNOWN and not card_f.detail


def test_boundaries_empty_non_stale_and_upstream_reason_do_not_break_card_or_kbar():
    """stale_reason 為空／非 stale／帶上游狀態：有上游句就只剩上游句；沒有就 detail 為空。"""
    from shared.ui2_contract.models import FieldState
    from shared.upstream_state import UPSTREAM_TEXT_FETCH_FAILED
    fresh = get_real_page_vm("p4_market", _stale_card_kbar_snapshot("", is_stale=False, age_days=1, as_of="2026-11-19"))
    for f in (fresh.context.cards[0].field, fresh.context.kbar.field):
        assert f.state is FieldState.OK and not f.detail and f.status_text is None
    # 非 stale 但 L1 仍帶說明句：同樣不外露
    odd = get_real_page_vm("p4_market", _stale_card_kbar_snapshot(REAL_L1_OVER_THRESHOLD, is_stale=False, age_days=1,
                                                                  as_of="2026-11-19"))
    for f in (odd.context.cards[0].field, odd.context.kbar.field):
        assert f.state is FieldState.OK and not f.detail
    # 過期＋上游抓取失敗：只保留既有已核准的上游句
    up = get_real_page_vm("p4_market", _stale_card_kbar_snapshot(REAL_L1_OVER_THRESHOLD, upstream_state="FETCH_FAILED"))
    for f in (up.context.cards[0].field, up.context.kbar.field):
        assert f.state is FieldState.STALE and f.detail == UPSTREAM_TEXT_FETCH_FAILED


def test_stale_copy_guard_has_teeth_when_the_l1_sentence_is_shown_again():
    """負例：若有人把 L1 原句塞回台股卡 detail，詞彙守衛必須抓到（掃描器本身的牙）。"""
    snap = _stale_card_kbar_snapshot(REAL_L1_OVER_THRESHOLD)
    vm = get_real_page_vm("p4_market", snap)
    card = vm.context.cards[0]
    leaked = dataclasses.replace(card, field=dataclasses.replace(card.field, detail=snap.twii.stale_reason))
    leaked_vm = dataclasses.replace(vm, context=dataclasses.replace(vm.context, cards=(leaked, *vm.context.cards[1:])))
    assert {"twii_ohlcv", "門檻"} <= set(hits_in(vm_visible_text(leaked_vm)))
    assert hits_in(vm_visible_text(vm)) == []
