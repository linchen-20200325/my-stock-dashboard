"""💼 持股 W-11 批 1 守衛（DEC-141；客戶 2026-11-05 Q1~Q8）——僅版面／欄位結構／空槽，⛔ 資料接線。

涵蓋：組合狀態行（資料日固定 `⬜ 資料日未提供`、判得出不計算）、今日需處理單行、Primary 空槽（桌機預定高度／手機一行）、
建議持股水位（市場端）空槽（不暗示上限）、持股表（桌機八欄／手機四欄＋展開、無假列）、DOM 順序、人類字樣守衛。
每條幾何／內容守衛都配負向突變（mutation）：拔掉被守的結構，檢查器必須轉紅。
"""
from __future__ import annotations

import re

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.pages import P4_HOLD
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import get_real_page_vm
from src.ui2.components import html as H
from src.ui2.shell.css import CSS
from src.ui2.views import _page, hold
from tests.test_ui2_p1_human_text import _snapshots, hits_in

SCENARIOS = ("cold", "loaded", "missing", "stale", "unavailable", "not_evaluated")
EIGHT = ["代碼", "名稱", "持股比例", "成本", "現價", "報酬", "策略", "System Action"]
FOUR = ["代碼", "名稱", "報酬", "System Action"]


def _chunks(monkeypatch, vm) -> list[str]:
    out: list[str] = []
    monkeypatch.setattr(_page.st, "markdown", lambda html, **kw: out.append(html))
    monkeypatch.setattr(_page.st, "expander", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no expander on hold")), raising=False)
    hold.render(vm)
    return out


def _all_vms():
    for sc in SCENARIOS:
        yield f"fake/{sc}", get_preview_page_vm(P4_HOLD, sc)
    for name, snap in _snapshots().items():
        yield f"real/{name}", get_real_page_vm(P4_HOLD, snap)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"<style.*?</style>", "", html, flags=re.S))


# ── 檢查器（純函式；mutation 測試重用）──────────────────────────────────────────
def check_status(first: str) -> list[str]:
    bad = []
    m = re.search(r'<div class="ui2-h-status".*?</div>', first, re.S)
    if not m:
        return ["缺組合狀態行"]
    s = _text(m.group(0))
    if T.TEXT_ASOF_MISSING not in s:
        bad.append("資料日不是 `⬜ 資料日未提供`")
    if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}", s):
        bad.append("狀態行出現日期（⛔ 今日／最舊一檔／抓取時間頂替）")
    if re.search(r"判得出\s*\d|\d\s*[／/]\s*\d", s):
        bad.append("判得出被計算成 M／N")
    if f"{T.HOLD_STATUS_JUDGED_LABEL} {T.TEXT_NOT_PROVIDED}" not in re.sub(r"\s+", " ", s):
        bad.append("判得出不是 `⬜ 尚未提供`")
    return bad


def check_action_row(first: str) -> list[str]:
    bad = []
    rows = re.findall(r'<div class="ui2-qrow" data-ui2-q="q2".*?</div>', first, re.S)
    if len(rows) != 1:
        return [f"今日需處理不是單行（q2 列數 {len(rows)}）"]
    if 'data-ui2-q="q3"' in first:
        bad.append("仍有『下一步』獨立列")
    r = rows[0]
    if T.HOLD_ACTION_LABEL not in r or 'data-axis="capability"' not in r or T.TEXT_NOT_PROVIDED not in r:
        bad.append("今日需處理不是 `⬜ 尚未提供` Capability 空槽")
    for w in ("今日無需調整", "無需調整", "加碼", "減碼", "換股", "續抱"):
        if w in r:
            bad.append(f"今日需處理含動作字樣 {w}")
    return bad


def check_body(body: str) -> list[str]:
    bad = []
    order = [m for m in re.findall(r'data-ui2-l1="(hold_cap_slot|onebrain|hold_primary_slot|hold_table)"', body)]
    if order != ["hold_cap_slot", "onebrain", "hold_primary_slot", "hold_table"]:
        bad.append(f"DOM 順序不是 建議持股水位→OneBrain→Primary→持股表：{order}")
    prim = re.search(r'<div class="ui2-primary-slot ui2-h-primary".*?</div></div>', body, re.S)
    cap = re.search(r'<div class="ui2-primary-slot ui2-h-cap".*?</div></div>', body, re.S)
    if not prim or T.HOLD_PRIMARY_TITLE not in prim.group(0) or T.TEXT_NOT_PROVIDED not in prim.group(0):
        bad.append("Primary 空槽缺標題或 `⬜ 尚未提供`")
    if prim and re.search(r"<(svg|polyline|canvas|img|rect|path)\b|ui2-chip--danger", prim.group(0), re.I):
        bad.append("Primary 空槽含圖形元素或紅色")
    if not cap or T.HOLD_CAP_TITLE not in cap.group(0) or T.TEXT_NOT_PROVIDED not in cap.group(0):
        bad.append("建議持股水位空槽缺標題或 `⬜ 尚未提供`")
    if cap:
        c = _text(cap.group(0))
        if re.search(r"\d|%|％|Risk Cap", c):
            bad.append("建議持股水位含數字／百分比／Risk Cap（⛔ 讀 Risk Cap、⛔ 暗示已有上限）")
    tb = re.search(r'<div class="ui2-h-table".*', body, re.S)
    if not tb:
        return bad + ["缺持股表"]
    ths = re.findall(r"<th([^>]*)>([^<]*)</th>", tb.group(0))
    if [n for _, n in ths] != EIGHT:
        bad.append(f"桌機欄名不是八欄：{[n for _, n in ths]}")
    if [n for a, n in ths if "ui2-ht__x" not in a] != FOUR:
        bad.append("手機四欄不是 代碼／名稱／報酬／System Action")
    if re.search(r"<(td|tbody|tr)\b", re.sub(r"<thead>.*?</thead>", "", tb.group(0), flags=re.S)) or "<td" in tb.group(0):
        bad.append("持股表出現資料列（⛔ 假列／假成本／假報酬）")
    t = _text(tb.group(0))
    if T.HOLD_TABLE_REASON not in t or T.TEXT_NOT_PROVIDED not in t:
        bad.append("持股表缺原因句或 `⬜ 尚未提供`")
    if re.search(r"0\s*檔|沒有持股|無持股|空倉", t):
        bad.append("持股表把未登入寫成持股 0 檔")
    return bad


_MEDIA = re.compile(r"@media \(min-width:769px\)\{\n  \.ui2-h-status.*?\n\}\n", re.S)


def check_css(css: str) -> list[str]:
    bad = []
    m = _MEDIA.search(css)
    if not m:
        return ["缺 💼 W-11 批 1 桌機 media 區塊"]
    desk = m.group(0)
    outside = _MEDIA.sub("", css)
    if not re.search(r"\.ui2-h-primary\{[^}]*min-height:240px", desk):
        bad.append("桌機 Primary 未維持預定高度 240px")
    if re.search(r"\.ui2-h-primary\{[^}]*min-height", outside):
        bad.append("Primary 預定高度漏到手機（手機必須一行）")
    if not re.search(r"\.ui2-h-primary\s+\.ui2-primary-slot__reason,\.ui2-h-primary\s+\.ui2-primary-slot__spec\{display:none\}", outside):
        bad.append("手機 Primary 未收成一行（原因／SPEC 未隱藏）")
    if not re.search(r"\.ui2-ht__x\{display:none\}", outside):
        bad.append("手機未隱藏後四欄")
    if not re.search(r"\.ui2-ht__x\{display:table-cell\}", desk):
        bad.append("桌機未顯示八欄")
    if not re.search(r'grid-template-areas:"ob ob" "pr cap" "tb tb"', desk):
        bad.append("桌機排版不是 OneBrain／〔Primary｜建議持股水位〕／持股表")
    return bad


# ── 正向 ────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,vm", list(_all_vms()))
def test_hold_layout_contract_all_states(monkeypatch, name, vm):
    first, body = _chunks(monkeypatch, vm)[:2]
    assert check_status(first) == [] and check_action_row(first) == [] and check_body(body) == []


@pytest.mark.parametrize("name,vm", list(_all_vms()))
def test_new_visible_text_passes_human_text_guard(monkeypatch, name, vm):
    assert hits_in(_text("".join(_chunks(monkeypatch, vm)))) == []


def test_css_geometry_contract():
    assert check_css(CSS) == []


def test_vm_still_carries_next_step_and_holdings_card():
    """Presentation Compression ≠ Information Loss：畫面合併／改版，VM 的『下一步』與 holdings_table 卡不得消失。"""
    vm = get_preview_page_vm(P4_HOLD, "loaded")
    assert vm.context.first_screen.next_step is not None
    assert any(c.card_id == "holdings_table" for c in vm.context.cards)


def test_no_new_data_source_in_view_and_components():
    """⛔ 資料接線：view／元件不得 import src.data、streamlit session、services（本批 presentation-only）。"""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for rel in ("src/ui2/views/hold.py",):
        src = (root / rel).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+(src\.data|src\.services|src\.ui\b|app\b)", src, re.M)
        assert "session_state" not in src


# ── 負向突變：拔掉被守的結構，檢查器必須轉紅 ─────────────────────────────────────────
def _good(monkeypatch):
    vm = get_preview_page_vm(P4_HOLD, "loaded")
    first, body = _chunks(monkeypatch, vm)[:2]
    return first, body


def test_mutations_status(monkeypatch):
    first, _ = _good(monkeypatch)
    assert check_status(first) == []
    assert check_status(first.replace(T.TEXT_ASOF_MISSING, "2026-11-05", 1))                      # 今日冒充
    assert check_status(first.replace(f"{T.HOLD_STATUS_JUDGED_LABEL} {T.TEXT_NOT_PROVIDED}", "判得出 10／12", 1))
    assert check_status(re.sub(r'<div class="ui2-h-status".*?</div>', "", first, flags=re.S))      # 整行拿掉


def test_mutations_action_row(monkeypatch):
    first, _ = _good(monkeypatch)
    assert check_action_row(first.replace(T.TEXT_NOT_PROVIDED_AGGREGATOR, "今日無需調整", 1))
    assert check_action_row(first.replace('data-ui2-q="q4"', 'data-ui2-q="q3" data-x="q4"', 1))   # 『下一步』獨立列回來
    assert check_action_row(first + '<div class="ui2-qrow" data-ui2-q="q2"></div>')                # 兩列


def test_mutations_body(monkeypatch):
    _, body = _good(monkeypatch)
    assert check_body(body) == []
    swapped = body.replace('data-ui2-l1="hold_table"', 'data-ui2-l1="TMP"').replace('data-ui2-l1="hold_cap_slot"', 'data-ui2-l1="hold_table"')
    assert check_body(swapped)                                                                      # 順序被破壞
    assert check_body(body.replace(">報酬</th>", "></th>", 1).replace("<th scope=\"col\"></th>", "<th scope=\"col\">收益</th>", 1))  # 欄名改
    assert check_body(body.replace("<th scope=\"col\" class=\"ui2-ht__x\">策略</th>", "", 1))      # 少一欄
    assert check_body(body.replace("</thead>", "</thead><tbody><tr><td>0050</td></tr></tbody>", 1))  # 假列
    assert check_body(body.replace(T.HOLD_TABLE_REASON, "目前 0 檔", 1))                            # 未登入寫成 0 檔
    assert check_body(body.replace(T.HOLD_CAP_REASON, "建議 40～60%", 1))                           # 建議區間數字
    assert check_body(body.replace(T.HOLD_PRIMARY_REASON, T.HOLD_PRIMARY_REASON + "<svg></svg>", 1))  # 假圖


def test_mutations_css():
    assert check_css(CSS) == []
    assert check_css(CSS.replace("min-height:240px", "min-height:0", 1))                            # 桌機高度拿掉
    assert check_css(CSS.replace(".ui2-ht__x{display:none}", "", 1))                                # 手機八欄
    assert check_css(CSS.replace(".ui2-h-primary .ui2-primary-slot__reason,.ui2-h-primary .ui2-primary-slot__spec{display:none}", "", 1))  # 手機非一行
    assert check_css(CSS.replace('"ob ob" "pr cap" "tb tb"', '"ob ob" "tb tb" "pr cap"', 1))        # 表跑到 Primary 之上


# ── 真瀏覽器判定器（measure_viewport._evaluate_h1）單元測試：對合成量測必綠，拔掉任一幾何必紅 ──────────────
import copy

from tests.ui2_viewport import measure_viewport as MV


def _box(top, bottom, left, right, **kw):
    return {"top": float(top), "bottom": float(bottom), "left": float(left), "right": float(right),
            "height": float(bottom - top), "width": float(right - left), **kw}


def _h1(mobile: bool) -> dict:
    segs = [{"seg": "portfolio", "text": "組合：⬜ 尚未提供", "left": 14, "right": 120, "clipped": False},
            {"seg": "asof", "text": "資料日 ⬜ 資料日未提供", "left": 130, "right": 280, "clipped": False},
            {"seg": "judged", "text": "判得出 ⬜ 尚未提供", "left": 14, "right": 150, "clipped": False}]
    if mobile:
        th = [{"text": n, "left": 14 + i * 80, "right": 90 + i * 80, "clipped": False} for i, n in enumerate(MV.H1_COLS_MOBILE)]
        return {"vw": 390, "status": {**_box(130, 170, 14, 376), "segs": segs},
                "cap": {**_box(400, 460, 14, 376), "danger": 0, "text": "建議持股水位（市場端） ⬜ 尚未提供"},
                "onebrain": _box(470, 510, 14, 376),
                "primary": {**_box(520, 562, 14, 376), "graphics": 0, "danger": 0, "text": "產業曝險／集中度 ⬜ 尚未提供",
                            "title_cy": 541.0, "chip_cy": 541.0},
                "table": {**_box(572, 700, 14, 376), "data_rows": 0, "more_visible": True, "th": th}}
    th = [{"text": n, "left": 220 + i * 120, "right": 330 + i * 120, "clipped": False} for i, n in enumerate(MV.H1_COLS_DESKTOP)]
    return {"vw": 1440, "status": {**_box(70, 90, 200, 1400), "segs": segs},
            "cap": {**_box(400, 650, 1000, 1400), "danger": 0, "text": "建議持股水位（市場端） ⬜ 尚未提供"},
            "onebrain": _box(330, 370, 200, 1400),
            "primary": {**_box(400, 650, 200, 980), "graphics": 0, "danger": 0, "text": "產業曝險／集中度 ⬜ 尚未提供",
                        "title_cy": 420.0, "chip_cy": 450.0},
            "table": {**_box(660, 760, 200, 1400), "data_rows": 0, "more_visible": False, "th": th}}


def _h1_eval(mobile: bool, mut=None) -> list[str]:
    m = {"page": "p4_hold", "viewport": {"w": 390 if mobile else 1440, "h": 844 if mobile else 900}, "h1": _h1(mobile)}
    if mut:
        mut(m["h1"])
    out = {t["id"]: [] for t in MV.THRESHOLDS}
    MV._evaluate_h1(m, out)
    return out["w11_hold_layout"]


def test_h1_evaluator_accepts_good_and_registered():
    assert _h1_eval(True) == [] and _h1_eval(False) == []
    assert "w11_hold_layout" in {t["id"] for t in MV.THRESHOLDS}
    assert MV.H1_PRIMARY_DESKTOP_MIN_PX == 240


def test_h1_evaluator_skips_other_pages_and_fails_missing_key():
    out = {t["id"]: [] for t in MV.THRESHOLDS}
    MV._evaluate_h1({"page": "p4_market", "viewport": {"w": 390, "h": 844}}, out)
    assert out["w11_hold_layout"] == []
    MV._evaluate_h1({"page": "p4_hold", "viewport": {"w": 390, "h": 844}}, out)
    assert out["w11_hold_layout"]                                           # hold 缺 h1＝紅


def test_hold_requires_q1_q2_q4_but_other_pages_still_need_q3():
    assert MV.HOLD_FIRST_SCREEN_QS == ("q1", "q2", "q4") and "q3" in MV.FIRST_SCREEN_QS
    from tests.test_ui2_batch2 import _good_mobile
    m = copy.deepcopy(_good_mobile())
    m["elements"] = [e for e in m["elements"] if e["q"] != "q3"]
    fail = lambda page: bool(MV.evaluate({**m, "page": page})["first_screen_within_usable_height"])
    assert fail("p4_market") and not fail("p4_hold")                         # 只有 hold 豁免 q3
    m["elements"] = [e for e in m["elements"] if e["q"] != "q2"]
    assert fail("p4_hold")                                                   # hold 缺 q2 仍紅


@pytest.mark.parametrize("mobile,label,mut", [
    (False, "桌機 Primary 高度拿掉", lambda h: h["primary"].update(**_box(400, 450, 200, 980), graphics=0)),
    (False, "桌機 Primary 與建議持股水位不並排", lambda h: h["cap"].update(**_box(660, 900, 1000, 1400))),
    (False, "桌機持股表跑到 Primary 之上", lambda h: h["table"].update(**_box(300, 390, 200, 1400))),
    (False, "桌機只剩四欄", lambda h: h["table"].update(th=h["table"]["th"][:4])),
    (False, "桌機欄名改名", lambda h: h["table"]["th"][2].update(text="比例")),
    (True, "手機 Primary 沒收成一行", lambda h: h["primary"].update(**_box(520, 640, 14, 376))),
    (True, "手機 Primary 標題與 chip 不同列", lambda h: h["primary"].update(title_cy=530.0, chip_cy=560.0)),
    (True, "手機八欄", lambda h: h["table"].update(th=[{"text": n, "left": 14 + i * 40, "right": 50 + i * 40, "clipped": False} for i, n in enumerate(MV.H1_COLS_DESKTOP)])),
    (True, "手機缺展開提示", lambda h: h["table"].update(more_visible=False)),
    (True, "手機順序：Primary 跑到 OneBrain 之上", lambda h: h["primary"].update(**_box(400, 442, 14, 376))),
    (True, "手機欄名被裁切", lambda h: h["table"]["th"][0].update(clipped=True)),
    (False, "出現假資料列", lambda h: h["table"].update(data_rows=3)),
    (False, "Primary 含假圖", lambda h: h["primary"].update(graphics=1)),
    (False, "空槽紅色", lambda h: h["cap"].update(danger=1)),
    (True, "資料日被改成日期", lambda h: h["status"]["segs"][1].update(text="資料日 2026-11-05")),
    (True, "資料日段超出視窗", lambda h: h["status"]["segs"][1].update(right=500)),
    (True, "缺狀態行", lambda h: h.update(status=None)),
])
def test_h1_evaluator_mutations_go_red(mobile, label, mut):
    assert _h1_eval(mobile, mut), f"突變『{label}』未被判定器抓到"
