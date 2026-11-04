"""New UI2 Active Presentation Contract — docs-consistency 守衛（DEC-128，客戶 2026-11-03 (13)）。

為什麼有這個檔
    客戶 (13) 第 10 點：「只允許一套 Active SSOT … 不得要求新 session 自己猜『哪一段比較新』」。
    這個檔把「單一現行有效讀法」機械化——
      (i)   Active Contract 單一入口文件存在，頂端宣告「現行唯一有效、衝突時以本文件與 DEC-128 為準」；
      (ii)  DEC-128 存在、客戶原文 15 點完整在 fence 內、取代範圍 S21～S35 與 PROVISIONAL 標示在；
      (iii) 被取代的主要文件含 `SUPERSEDED / HISTORICAL — NOT ACTIVE` 橫幅並指向 DEC-128 與 Active Contract；
      (iv)  append-only：舊 DEC／舊條文的關鍵原句仍在（沒有人偷改歷史），且 10 個被部分取代的 DEC 條頭都有 📌；
      (v)   仍斷言舊 presentation 的測試登記在 `PENDING_UI_CORRECTION_TESTS`（後續 UI correction 批的待改清單；
            這些測試**照常執行、不得 xfail／skip**）。

⛔ 本檔不碰任何 `src/`、不改任何既有測試的斷言；純讀 docs。
⛔ 本檔不是「UI 已改好」的證明——現行 Preview 仍有舊 L2／L3（implementation deviation，BACKLOG §5.1.26）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_REL = "docs/vnext/NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md"
ACTIVE_NAME = "NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md"
BANNER = "SUPERSEDED / HISTORICAL — NOT ACTIVE"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _dec128() -> str:
    t = _read("docs/DECISIONS.md")
    i = t.index("### DEC-128｜")
    return t[i:]


def _dec128_fence() -> str:
    d = _dec128()
    a = d.index("```\n") + 4
    b = d.index("\n```", a)
    return d[a:b]


# ---------------------------------------------------------------- (i) Active Contract
def test_active_contract_exists_and_declares_single_source_of_truth():
    t = _read(ACTIVE_REL)
    head = t[:2500]
    assert "現行唯一有效" in head
    assert "DEC-128" in head
    assert "以本文件與" in head and "為準" in head
    assert "不得依舊 Wireframes" in head or "不得依舊" in head   # 禁止依舊 L2／L3 expander 施工
    # 內容骨架：四頁優先順序、Chart SPEC、資料健康度三層、禁曝險、Preview 去向、OneBrain、projection、取代對照
    for must in ("## §2 四頁正式 Human UI", "## §4 Chart-first", "## §5 👤 我的 → 資料健康度",
                 "## §6 Preview 控制", "## §7 `🤖 OneBrain Outlook`", "## §8 Projection",
                 "## §10 取代對照表", "Level 1", "Level 2", "Level 3", "raw exception", "traceback",
                 "SPEC｜日頻｜TWSE｜資料日 11/03｜缺值不補"):
        assert must in t, must
    for status in ("KEEP", "SUPERSEDE", "REMOVE", "MIGRATE"):
        assert status in t, status
    # PROVISIONAL 必須被標出（不得偽裝成客戶裁示）
    assert "PROVISIONAL" in t


def test_active_contract_does_not_supersede_the_kept_layout_rules():
    """DEC-127 的 CTA 順序／W-4 與資料語意三軸、Single Action Authority 必須明列為仍有效。"""
    t = _read(ACTIVE_REL)
    d = _dec128()
    for must in ("DEC-127", "W-4"):
        assert must in t and must in d
    for must in ("DEC-124", "Single Action Authority", "Presentation Slice ≠ Decision Context"):
        assert must in d, must


# ---------------------------------------------------------------- (ii) DEC-128
_CUSTOMER_HEADINGS = (
    "1. 最新最高 Presentation 原則", "2. 四頁正式 Human UI", "3. 一般四頁不得再顯示完整 L2 / L3 資料",
    "4. Chart-first + Chart SPEC", "5. 👤 我的 → 資料健康度", "6. 資料健康度分層",
    "7. UI ViewModel 與 OneBrain Context 必須分離", "8. OneBrain 不是 UI Summary Bot",
    "9. Active Rule Cleanup — 本次新增強制要求", "10. 只允許一套 Active SSOT",
    "11. DECISIONS 歷史不得破壞", "12. Tests / Guards 也要清理", "13. 本批最多三項",
    "14. Model Gate", "15. Durable Persistence Gate",
)


def test_dec128_exists_with_verbatim_customer_text_in_order():
    d = _dec128()
    assert d.startswith("### DEC-128｜")
    fence = _dec128_fence()
    pos = -1
    for h in _CUSTOMER_HEADINGS:           # 15 點標題都在 fence 內，且依序
        i = fence.find(h, pos + 1)
        assert i > pos, h
        pos = i
    for must in ("Presentation Compression ≠ Information Loss",
                 "UI 沒顯示的資料，不代表 OneBrain 不得讀。OneBrain 能讀的資料，也不代表 UI 必須全部呈現。",
                 "✅ 正常、◷ 可能過期、◇ 資料未備、⛔ 來源不可用、⬜ 尚未接線",
                 "不得一般曝光：API key、secret、env var 名、raw exception、traceback、module path、credential detail、internal stack",
                 "SPEC｜日頻｜TWSE｜資料日 11/03｜缺值不補",
                 "SUPERSEDED / HISTORICAL — NOT ACTIVE",
                 "不得要求新 session 自己猜「哪一段比較新」。",
                 "KEEP：仍與最新裁示一致。", "REMOVE FROM ACTIVE CONTRACT", "MIGRATE：內容仍需要"):
        assert must in fence, must


def test_dec128_lists_supersede_scope_unsuperseded_and_marks_provisional():
    d = _dec128()
    for i in range(21, 36):
        assert f"**S{i}**" in d, i
    assert "不被取代" in d
    for must in ("DEC-124", "DEC-127", "Single Action Authority", "Presentation Slice ≠ Decision Context",
                 "PROVISIONAL", "(a)", "(b)", "(c)", "Decision Re-open Proposal"):
        assert must in d, must
    # PROVISIONAL 區必須明講「不是客戶裁示」
    assert "不是客戶裁示" in d
    # 不新增第 6 個資料語意態
    assert "不新增第 6 個資料語意態" in d


def test_supersede_map_and_project_rules_section_30_are_wired():
    sm = _read("docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md")
    for i in range(21, 36):
        assert f"| **S{i}** |" in sm, i
    pr = _read("PROJECT_RULES.md")
    assert "## 第 30 節｜Presentation Compression ≠ Information Loss" in pr
    sec = pr[pr.index("## 第 30 節｜"):]
    for n in range(1, 10):
        assert f"\n{n}. **" in sec, n
    assert ACTIVE_NAME in sec and "PROVISIONAL" in sec
    # §24.2 舊判準：原文保留 + 刪除線 + 指向 DEC-128
    assert "~~第一屏三層答不出＝FAIL（客戶原文）~~" in pr
    i = pr.index("~~第一屏三層答不出＝FAIL（客戶原文）~~")
    assert "DEC-128" in pr[i:i + 400]


# ---------------------------------------------------------------- (iii) 橫幅
BANNERED = (
    "docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md",
    "docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md",
    "docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md",
    "docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md",
    "docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md",
    "docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md",
    "docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md",
    "docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md",
    "docs/governance/UI_VISUAL_FIDELITY_GATE.md",
    "docs/vnext/ME_PAGE_DRAFT_2026-10-25.md",
)


@pytest.mark.parametrize("rel", BANNERED)
def test_superseded_documents_carry_banner_pointing_to_dec128_and_active_contract(rel):
    t = _read(rel)
    head = t[:6000]
    assert BANNER in head, rel
    line = next(ln for ln in head.split("\n") if BANNER in ln)       # 橫幅是單一行：同一行內必須指向 DEC-128 與 Active Contract
    assert "DEC-128" in line and ACTIVE_NAME in line, rel
    assert "仍有效" in line or "整份為 HISTORICAL" in line, rel         # 部分取代必須講清楚「其餘仍有效」（或整份歷史）


LEGACY_ERA = (
    "docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md",
    "docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md",
    "docs/vnext/PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md",
    "docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md",
    "docs/vnext/NEWUI_D25_A_FOUR_PAGE_SPEC_2026-10-27.md",
    "docs/vnext/NEWUI_D25_UIT_WIREFRAME_2026-10-29.md",
)


@pytest.mark.parametrize("rel", LEGACY_ERA)
def test_legacy_era_documents_say_they_are_not_active_for_new_ui2(rel):
    head = _read(rel)[:4000]
    line = next(ln for ln in head.split("\n") if BANNER in ln)
    assert "DEC-128" in line and ACTIVE_NAME in line and "Legacy" in line, rel


def test_section_level_banners_exist_in_wireframes_and_freeze():
    wf = _read("docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md")
    fz = _read("docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md")
    assert wf.count(BANNER) >= 8       # 頂端＋§0.1＋§2.1／§2.2／§3.1～§3.3／§4.1／§4.2／§5.1／§5.2
    assert fz.count(BANNER) >= 8       # 頂端＋§2.0～§2.4＋§10＋§12.2＋§16.1～§16.5
    # 原 ▸ 行仍在（歷史證據保留，沒有被刪）
    assert "▸ 為什麼（L2）" in wf and "▸ 指標明細（16 項）（L3）" in wf


def test_non_superseded_notes_do_not_claim_supersede():
    """Reuse Matrix／Digest Contract／OneBrain Architecture 只加補註，不得被標成 NOT ACTIVE。"""
    for rel in ("docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md",
                "docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md",
                "docs/vnext/ONEBRAIN_ARCHITECTURE_2026-10-31.md"):
        head = _read(rel)[:3000]
        assert "DEC-128" in head, rel
        assert BANNER not in head, rel


# ---------------------------------------------------------------- (iv) append-only
_OLD_ORIGINAL_SENTENCES = (
    # DEC-091 §一 Level 3（被部分取代；原文必須仍在）
    "- Level 3：「查看依據」展開後才看：原始數字、計算邏輯、資料來源、freshness、missing reason、門檻、工程診斷。不得預設展開 Level 3。",
    # DEC-105 第 4 點
    "3. **指標危險度卡＝A**：降階到「指標明細（16 項）」展開區最上方。",
    # DEC-122 客戶 §9／§22／§25（fence 內）
    "L3：raw table、full macro detail、engineering diagnostics",
    "詳細：fundamental、risk、chip、evidence、rule IDs 放 L2。",
    "新增正式入口：Decision Digest、Rule Registry、Data Freshness、System Information",
    # DEC-081 第 7 點
    "**📊 大盤**：更新／重新整理、資料中心入口、展開理由、問 AI／查看依據；⛔ 不得塞 Sheet CRUD。",
    # 不被取代的：DEC-124／DEC-127
    "正式資料語意只有 OK／Missing／Stale／Unavailable／Not Evaluated 五個",
    "目前 CTA 放在第一屏四問最後屬 implementation deviation，不是規格衝突。",
)


@pytest.mark.parametrize("sentence", _OLD_ORIGINAL_SENTENCES)
def test_old_decisions_original_text_still_present(sentence):
    assert sentence in _read("docs/DECISIONS.md"), sentence


def test_ten_partially_superseded_decisions_have_pointer_line_right_after_heading():
    t = _read("docs/DECISIONS.md")
    for dec in ("072", "076", "081", "091", "105", "109", "111", "112", "117", "122"):
        m = re.search(rf"^###? DEC-{dec}｜.*$", t, re.M)
        assert m, dec
        near = t[m.end():m.end() + 1500]
        assert "SUPERSEDED IN PART BY DEC-128" in near, dec
        assert "原文一字未改" in near, dec


def test_project_rules_old_text_not_deleted():
    pr = _read("PROJECT_RULES.md")
    assert "明顯偏離＝Visual Fidelity FAIL" in pr
    assert "- 🩺 資料中心：資料來源、資料健康、freshness、缺值與可用性。" in pr


# ---------------------------------------------------------------- (v) 待更新測試登記
# DEC-129：真正「強制舊 presentation」的斷言（pointer 指向 L2、Preview 控制 expander 標題、①～④ 題號可見、
# 緊接 L1 必為卡片）**已在本批移除／改寫**（見 docs/BACKLOG.md §5.1.26「已改／移除的舊測試」）。
# 下列是**仍存活、但綁定目前 UI 位置／操作方式**的測試或 helper（資料／語意斷言仍有效；UI 批移動內容或控制時須同步改）：
#   位階說明目前在 📊 VM 的 `why` section（location-bound）、以及經 Preview 控制 selectbox 切場景／帳戶的 AppTest。
#   * 待 UI 批更新；更新後須同步移除登記（本檔的存在斷言會在改名／刪除時提醒）。
#   * ⛔ 不得用 xfail／skip 隱藏（下方有 AST 守衛）；⛔ 不得為了讓它們通過而保留錯誤 UI。
#   * 真正的資料／語意安全守衛（DEC-124 三軸、G2／G2F／G4／G9、白名單 teeth、no-write proof）**不在此列、不得降低**。
PENDING_UI_CORRECTION_TESTS: tuple[tuple[str, str], ...] = (
    # location-bound：位階完整說明目前在 📊 VM `why` section（P3／P6 把落點改資料健康度時同步）
    ("tests/test_ui2_real_feed.py", "_why_regime"),
    ("tests/test_ui2_real_feed.py", "test_regime_unloaded_is_not_evaluated_with_the_l0_explanation"),
    ("tests/test_ui2_real_feed.py", "check_cross_page_regime"),
    # 📌 P3（2026-11-03）複查：以上三項是 VM 層（`why` section 位置）測試；P3 只改渲染、VM 位置不變 → 仍成立，維持登記至 P6 搬位階說明。
    # ✅ P1（2026-11-03）已處理並自本登記移除：T10 `measure_viewport._select_box`、T13 依賴 Preview 控制 selectbox 的 6 個 AppTest
    # （test_full_rendered_page_has_no_global_update_time／_market_dom_order／_at_target／test_cta_order_in_real_page_default_lane／
    # test_me_page_switches_account_in_the_real_app／test_every_page_switches_and_renders_in_every_scenario）——
    # 已改以 `?ui2_dev=1`（AppTest `at.query_params["ui2_dev"]="1"`）開啟開發面驅動，斷言語意不變。
)


def _function_nodes(rel: str) -> dict[str, ast.AST]:
    tree = ast.parse(_read(rel))
    return {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


@pytest.mark.parametrize("rel,name", PENDING_UI_CORRECTION_TESTS)
def test_pending_ui_correction_registry_entries_exist_and_are_not_hidden(rel, name):
    fns = _function_nodes(rel)
    assert name in fns, (
        f"{rel}::{name} 不存在——若已隨 UI correction 批更新／改名，請同步移除 PENDING_UI_CORRECTION_TESTS 登記"
        f"與 docs/BACKLOG.md §5.1.26「測試改動清單」")
    # ⛔ 不得用 xfail／skip 隱藏
    for dec in fns[name].decorator_list:
        src = ast.unparse(dec)
        assert "xfail" not in src and "skip" not in src, f"{rel}::{name} 被 {src} 隱藏"


def test_pending_registry_matches_backlog_test_change_list():
    b = _read("docs/BACKLOG.md")
    sec = b[b.index("### 5.1.26 "):]
    for rel, name in PENDING_UI_CORRECTION_TESTS:
        assert name in sec or Path(rel).name in sec, (rel, name)


def test_no_pending_test_is_hidden_by_module_level_skip_or_xfail():
    for rel in sorted({r for r, _ in PENDING_UI_CORRECTION_TESTS if r.endswith(".py") and "/test_" in r}):
        t = _read(rel)
        assert "pytestmark = pytest.mark.skip" not in t and "pytestmark = pytest.mark.xfail" not in t, rel


def test_legacy_tests_are_not_in_the_pending_registry():
    """Legacy New UI／Old UI 測試鎖 Legacy 行為（凍結不刪，DEC-019／020）——不是 New UI2 active contract 的待改清單。"""
    for rel, _ in PENDING_UI_CORRECTION_TESTS:
        base = Path(rel).name
        assert base.startswith("test_ui2_") or base == "measure_viewport.py", rel


# ---------------------------------------------------------------- (vi) 防復活 teeth 檔（DEC-129）
TEETH_REL = "tests/test_ui2_contract_teeth_pending.py"


#: 已隨 UI correction 批修好、**移除 xfail** 的 teeth（永久守衛；值＝畢業批）。新畢業者在此登記，docs 測試會要求它們不得再掛 xfail。
GRADUATED_TEETH: dict[str, str] = {
    "test_T_new_2_human_text_has_no_engineering_tokens": "P1",
    "test_T_new_5_preview_controls_are_dev_surface_only": "P1",
    "test_T_new_9_ui2_dev_shows_preview_controls_and_never_changes_account_area": "P1",
    "test_T_new_1_human_pages_have_no_full_evidence_expander": "P3",
    # 取代舊 T_new_1b（規格錯誤，DEC-131／客戶 (17) A2）：驗收對象＝渲染層無 evidence expander ＋ VM 仍完整保留
    "test_T_new_1b_vm_keeps_evidence_while_human_ui_hides_it": "P3",
}


def test_graduated_teeth_exist_and_are_plain_tests():
    fns = _function_nodes(TEETH_REL)
    for name in GRADUATED_TEETH:
        assert name in fns, name
        assert not any("xfail" in ast.unparse(d) or "skip" in ast.unparse(d) for d in fns[name].decorator_list), name


def test_pending_teeth_are_strict_xfail_with_dec128_reason_and_never_hide_safety_tests():
    """逐一驗證每個 xfail：必須是 strict=True 且 reason 含 DEC-128（AST，不是 substring 計數）；
    xfail 只准出現在這個 teeth 檔——其餘 tests/ 不得新增指向 DEC-128 的 xfail（防止拿它隱藏現有守衛）。"""
    src = _read(TEETH_REL)
    tree = ast.parse(src)
    # (a) `_xfail(p)` 工廠本身：pytest.mark.xfail(strict=True, reason=<含 DEC-128 的字串>)
    fac = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_xfail")
    calls = [c for c in ast.walk(fac) if isinstance(c, ast.Call) and ast.unparse(c.func) == "pytest.mark.xfail"]
    assert len(calls) == 1
    kw = {k.arg: k.value for k in calls[0].keywords}
    assert isinstance(kw.get("strict"), ast.Constant) and kw["strict"].value is True
    assert "DEC-128" in ast.unparse(kw["reason"]) and "待 UI correction 批" in ast.unparse(kw["reason"])
    # DEC-130：`_xfail130` 工廠同樣 strict=True，reason 同時含 DEC-128 與 DEC-130
    fac130 = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_xfail130")
    calls130 = [c for c in ast.walk(fac130) if isinstance(c, ast.Call) and ast.unparse(c.func) == "pytest.mark.xfail"]
    assert len(calls130) == 1
    kw130 = {k.arg: k.value for k in calls130[0].keywords}
    assert isinstance(kw130.get("strict"), ast.Constant) and kw130["strict"].value is True
    assert "DEC-130" in ast.unparse(kw130["reason"]) and "待 UI correction 批" in ast.unparse(kw130["reason"])
    # (b) 每個 test_T_new_* 都用 `_xfail("P#")`（或直接 pytest.mark.xfail 且同樣 strict+DEC-128）
    n = 0
    for fn in [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name.startswith("test_T_new_")]:
        if fn.name in GRADUATED_TEETH:       # P1 修好後移除 xfail 的永久守衛：必須真的沒有 xfail／skip（不得又被偷偷掛回去）
            assert not any("xfail" in ast.unparse(d) or "skip" in ast.unparse(d) for d in fn.decorator_list), fn.name
            continue
        ok = False
        for d in fn.decorator_list:
            if isinstance(d, ast.Call) and ast.unparse(d.func) in ("_xfail", "_xfail130"):
                assert re.fullmatch(r"P\d", ast.literal_eval(d.args[0])), fn.name
                ok = True
            elif isinstance(d, ast.Call) and ast.unparse(d.func) == "pytest.mark.xfail":
                k = {x.arg: x.value for x in d.keywords}
                assert isinstance(k.get("strict"), ast.Constant) and k["strict"].value is True, fn.name
                assert "DEC-128" in ast.unparse(k["reason"]), fn.name
                ok = True
        assert ok, f"{fn.name} 沒有 strict xfail"
        n += 1
    assert n == 4      # P3 後仍待後續批的 teeth：3（P6）、6（P2）、7（P7）、8（P6）；2／5／9（P1）、1／1b（P3）已畢業（GRADUATED_TEETH）
    # (c) 此檔內除 test_T_new_* 外，不得有任何 xfail／skip（現綠 teeth 不得被偷偷隱藏）
    for fn in [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and not x.name.startswith("test_T_new_")]:
        for d in fn.decorator_list:
            assert "xfail" not in ast.unparse(d) and "skip" not in ast.unparse(d), fn.name
    for f in sorted((ROOT / "tests").glob("test_*.py")):
        if f.name in (Path(TEETH_REL).name, "test_ui2_active_contract_docs.py"):
            continue
        assert "待 UI correction 批" not in f.read_text(encoding="utf-8"), f.name


def test_old_presentation_enforcing_assertions_are_gone():
    """被移除的舊斷言不得復活（DEC-129 §四）。"""
    rf = _read("tests/test_ui2_real_feed.py")
    assert 'ctrl == ["Preview 控制（資料來源）"]' not in rf
    assert "assert RC.REGIME_SEE_WHY in m_.detail" not in rf
    b2 = _read("tests/test_ui2_batch2.py")
    assert 'h.index("① 現在狀態")' not in b2
    b3 = _read("tests/test_ui2_batch3.py")
    assert 'first_after[0] == "ui2-grid"' not in b3
    # 真正的資料／語意安全守衛仍在（未被順手拿掉）
    assert "def check_cross_page_regime" in rf and "test_cross_page_checker_has_teeth" in rf


# ---------------------------------------------------------------- (vii) DEC-129（客戶 (14)）
def _dec129() -> str:
    d = _read("docs/DECISIONS.md")
    return d[d.index("### DEC-129｜"):]


def test_dec129_has_verbatim_customer_text_and_account_area_rules():
    d = _dec129()
    a = d.index("```\n") + 4
    fence = d[a:d.index("\n```", a)]
    for must in ("Desktop 左側加入登入與狀態", "未登入：\n- \"登入\"\n- \"⬜ 尚未登入\"", "不得從 URL/query parameter 猜登入狀態",
                 "手機仍固定四格導航", "10. Desktop 左側有 Login + Auth Status", "11. Mobile 仍只有四格導航",
                 "強制移除不再適用的 Active Rules", "加 teeth test 防止舊行為復活"):
        assert must in fence, must
    for must in ("ui2_account", "不是 auth contract", "NUI2-AUTH-CONTRACT-GATE", "Opus 5.5＋High", "優先於 (13)", "S36", "S37"):
        assert must in d, must


def test_active_contract_lists_the_eleven_points_and_account_area_and_no_old_must_display_wording():
    t = _read(ACTIVE_REL)
    head = t[:4000]
    assert "Active interpretation（11 點" in head
    for n in ("10. **桌機左側有 Login", "11. **手機仍只有四格導航"):
        assert n.replace("10. ", "").replace("11. ", "")[:6] in head
    assert "### §2.5 桌機左側 Navigation Rail" in t and "不是 auth contract" in t and "從 URL／query parameter 猜登入狀態" in t
    # grep 證明：Active Contract 內不得有「L2／L3 必須顯示於四主頁」類有效措辭
    for bad in ("必須顯示於四", "L2／L3 必須顯示", "expander 必須存在", "OneBrain 只能讀 UI slice 的讀法是"):
        assert bad not in t, bad
    sm = _read("docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md")
    i = sm.index("### §0.4 導覽")
    assert BANNER in sm[i:i + 1500] and "DEC-129" in sm[i:i + 1500]
    pr = _read("PROJECT_RULES.md")
    assert "桌機 Account Area 與導覽" in pr and "舊 presentation 假設退出 Active" in pr


# ---------------------------------------------------------------- (viii) 客戶原文 fence 整段 sha256 釘住
# 值＝客戶 (13)／(14) 原文（總管轉交之全文，scratchpad customer_directive）的 sha256；fence 內任何一字被改都會紅。
_FENCE_SHA256 = {
    "### DEC-128｜": "ed26051734a3dc1df2aee6321ac218cda0b2439872006bf2f94090eff6272a87",
    "### DEC-129｜": "210c1c2d55e2f37f7a5e0fcb809f3c43539609b72ede829bcc195ea707fdcf79",
    "### DEC-130｜": "dc28ea44aab00f12d3a0eb4977c517550385a60616ae8dd5c7a51b9e7398899c",   # 客戶 (15) 覆核 PROVISIONAL (a)(b)(c)
    "### DEC-131｜": "4f7f8ee15add8b9dc54c57ddae11fba6320dbed1c917a27c1e8e5abddc692de9",   # 客戶 (17) 選 A 開始 P3（A2）
    "### DEC-132｜": "088c01425621fa7d46163813e304a23be872cb630aa863dfc6f89e3b4208c086",   # 客戶 (18) 覆核 #1009 兩灰區＋P2 文字線框先行
}


@pytest.mark.parametrize("head", list(_FENCE_SHA256))
def test_customer_fences_are_pinned_by_sha256(head):
    import hashlib
    d = _read("docs/DECISIONS.md")
    b = d[d.index(head):]
    a = b.index("```\n") + 4
    fence = b[a:b.index("\n```", a)]
    assert hashlib.sha256(fence.encode("utf-8")).hexdigest() == _FENCE_SHA256[head]


# ---------------------------------------------------------------- (ix) 章節橫幅逐節配對
_L23_LINE = re.compile(r"▸ *(為什麼|指標明細|原始資料表|完整分析|完整 6 欄表|L2|L3)|（L[23]）|↓ *L2|L2／L3 摺疊|▸ L[23]")


def _unbannered_sections(rel: str, text: str | None = None) -> list[str]:
    """每個『在 code fence 內含 ▸ L2／L3 行』的章節：從該章節標題到該行之間必須出現橫幅。回傳違規 `行號:標題`。"""
    lines = (text if text is not None else _read(rel)).split("\n")
    bad, head_idx, in_fence, fence_start = [], None, False, None
    for i, ln in enumerate(lines):
        if ln.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and re.match(r"^#{2,3} ", ln):
            head_idx = i
            continue
        if in_fence and _L23_LINE.search(ln) and ("▸" in ln or "↓" in ln):
            seg = lines[head_idx:i] if head_idx is not None else lines[:i]
            if not any(BANNER in x for x in seg):
                bad.append(f"{i + 1}:{lines[head_idx] if head_idx is not None else '(top)'}")
    return sorted(set(bad))


@pytest.mark.parametrize("rel", ("docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md", "docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md"))
def test_every_section_with_l2_l3_expander_lines_is_bannered_before_the_block(rel):
    assert _unbannered_sections(rel) == [], rel


def test_section_banner_pairing_has_teeth():
    """mutation：把 Wireframes §3.2 的章節橫幅拿掉 → 逐節配對必紅；且確實偵測得到有 ▸ L2／L3 行的章節。"""
    rel = "docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md"
    real = _read(rel)
    j = real.index(BANNER, real.index("### §3.2 "))
    mutated = real[:j] + "XX" + real[j + len(BANNER):]
    assert any("§3.2" in x for x in _unbannered_sections(rel, mutated))
    assert _unbannered_sections(rel, real) == []


LEGACY_ERA_2 = (
    "docs/vnext/INTERACTION_COVERAGE_MATRIX_2026-10-25.md",
    "docs/vnext/NEWUI_STAGE_B_DRAFT_2026-10-26.md",
    "docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md",
    "docs/vnext/NEWUI_D25_B_COVERAGE_2026-10-27.md",
    "docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md",
)


@pytest.mark.parametrize("rel", LEGACY_ERA_2)
def test_second_batch_of_legacy_era_documents_are_bannered(rel):
    head = _read(rel)[:4000]
    line = next(ln for ln in head.split("\n") if BANNER in ln)
    assert "DEC-128" in line and ACTIVE_NAME in line and "Legacy" in line, rel


@pytest.mark.parametrize("rel,needle", (
    ("docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md", "DEC-128 S38"),
    ("docs/governance/UI_VISUAL_FIDELITY_GATE.md", "DEC-128 S39"),
    ("docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md", "DEC-128 S26/S40"),
    ("docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md", "DEC-128 S43"),
    ("docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md", "DEC-128 S43"),
))
def test_audit_p2_sections_are_bannered(rel, needle):
    assert needle in _read(rel), (rel, needle)


# ---------------------------------------------------------------- (x) DEC-130（客戶 (15)：PROVISIONAL (a)(b)(c) 升 Active）
def _dec130() -> str:
    d = _read("docs/DECISIONS.md")
    return d[d.index("### DEC-130｜"):]


def _dec130_fence() -> str:
    d = _dec130()
    a = d.index("```\n") + 4
    return d[a:d.index("\n```", a)]


def _strip_struck(text: str) -> str:
    """刪除線 `~~…~~` 內是「保留的舊字」，不算現行用法。"""
    return re.sub(r"~~.*?~~", "", text, flags=re.S)


_PROV_ABC = re.compile(r"PROVISIONAL[^\n]{0,6}\([abc]\)")


def test_dec130_fence_has_customer_text_and_effect_is_recorded():
    f = _dec130_fence()
    for must in ("(a) 有條件同意，需修正語意邊界", "Data State 仍只有五態", "不得新增第六態",
                 "⬜ 尚未接線不是 Data State。", "Capability / Implementation Availability",
                 "不得映射成 Not Evaluated、Missing、Unavailable 或任何第六態",
                 "必須拆成不同欄位／不同軸，不得混成單一 status", "\"Not Evaluated\" 仍保留原有正式語意",
                 "(b) 同意", "預設收合，不得搶主 UI", "不得讓這些功能把 🎯 主頁重新做成資料牆",
                 "(c) 同意", "\"?ui2_dev=1\"", "不放 sidebar", "不增加正式導航",
                 "不得將 \"ui2_dev\" query parameter 與正式 auth state 混用", "不能被當成登入證據",
                 "請從 PROVISIONAL 升為正式 Active interpretation", "NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT"):
        assert must in f, must
    d = _dec130()
    for must in ("升為正式 Active", "有條件同意", "兩軸", "⬜ 尚未接線", "Capability／Implementation Availability",
                 "ui2_dev", "不能被當成登入證據", "NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT",
                 "0 行 `src/`"):
        assert must in d, must


def test_dec128_provisional_block_is_marked_promoted_and_original_text_kept():
    d = _dec128()
    i = d.index("#### 四、⚠️ PROVISIONAL 判讀")
    near = d[i:i + 900]
    assert "已由 DEC-130 升為正式 Active" in near and "(a) 為「有條件同意」" in near
    # 原文一字未改
    assert "**(a) 資料健康度 Level 1 符號 ✅ ◷ ◇ ⛔ ⬜ 是「僅用於 👤 我的·資料健康度面」的別名**" in d
    assert "不得被引用為「客戶已核准」" in d and "不是客戶裁示" in d


def test_active_contract_no_longer_uses_provisional_abc_as_current_status():
    t = _read(ACTIVE_REL)
    live = _strip_struck(t)
    assert _PROV_ABC.findall(live) == [], _PROV_ABC.findall(live)
    assert "DEC-130" in t and "升為正式 Active" in t
    # 殘留的「撰寫組暫定」必須誠實標明、不得被寫成客戶已核准
    assert "撰寫組暫定" in t and "未經客戶覆核" in t


@pytest.mark.parametrize("rel", (
    "docs/vnext/NEWUI2_WIREFRAMES_2026-11-02.md", "docs/vnext/FINAL_UI_CONTRACT_FREEZE_2026-11-02.md",
    "docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md", "docs/vnext/FINAL_UI_SUPERSEDE_MAP_2026-11-02.md"))
def test_other_vnext_docs_do_not_keep_abc_as_provisional(rel):
    assert _PROV_ABC.findall(_strip_struck(_read(rel))) == [], rel


def test_project_rules_section_30_and_backlog_batch_table_treat_abc_as_active():
    pr = _read("PROJECT_RULES.md")
    sec = pr[pr.index("## 第 30 節｜"):]
    assert _PROV_ABC.findall(_strip_struck(sec)) == []
    for must in ("DEC-130", "`⬜ 尚未接線` 不是 Data State", "同一列同時需要兩者時**必須拆成不同欄位**",
                 "不能被當成登入證據", "預設收合、不搶主 UI"):
        assert must in sec, must
    b = _read("docs/BACKLOG.md")
    sec = b[b.index("### 5.1.26 "):b.index("#### 📌 DEC-130（客戶 2026-11-03 (15)）落盤補記")]
    assert _PROV_ABC.findall(_strip_struck(sec)) == [], _PROV_ABC.findall(_strip_struck(sec))
    p6 = next(ln for ln in sec.split("\n") if ln.startswith("| **P6**"))
    assert "兩軸欄位分離" in p6 and "狀態(Data State)" in p6 and "接線(Capability)" in p6
    # 資料健康度欄位表：Data State 與 Capability 分欄
    assert "`狀態(Data State)`（Level 1）" in sec and "`接線(Capability)`（Level 1；**獨立欄位，DEC-130**）" in sec
    # 結案的 CONFIRM 項不得再是 open
    for item in ("NUI2-DATA-HEALTH-SYMBOLS-CONFIRM", "NUI2-AUDIT-SURFACE-CONFIRM"):
        row = next(ln for ln in sec.split("\n") if item in ln and ln.startswith("|"))
        assert "closed by DEC-130" in row or "closed（DEC-130）" in row, item


def test_independent_audit_item_is_kept_and_not_claimed_done():
    b = _read("docs/BACKLOG.md")
    row = next(ln for ln in b.split("\n") if ln.startswith("| **NUI2-ACTIVE-CONTRACT-INDEPENDENT-AUDIT**"))
    assert "| open |" in row and "closed" not in row


_MAPPING_ROWS = (
    ("`✅ 正常`", "OK"), ("`◷ 可能過期`", "Stale"), ("`◇ 資料未備`", "Missing"), ("`⛔ 來源不可用`", "Unavailable"),
)


def _health_section(text: str) -> str:
    i = text.index("## §5 👤 我的 → 資料健康度")
    return text[i:text.index("## §6 Preview 控制")]


def test_active_contract_data_health_is_two_axis_separated():
    s = _health_section(_read(ACTIVE_REL))
    assert "### §5.1 Level 1 兩軸分離" in s
    # 四對映：符號 → Data State 軸 → 既有五態成員
    for sym, state in _MAPPING_ROWS:
        row = next((ln for ln in s.split("\n") if ln.startswith(f"| {sym} | Data State |")), None)
        assert row is not None and f"**{state}**" in row, (sym, state)
    # ⬜ 尚未接線 屬 Capability 軸、不對映任何 Data State
    cap = next(ln for ln in s.split("\n") if ln.startswith("| `⬜ 尚未接線` |"))
    assert "Capability／Implementation Availability" in cap and "不是 Data State" in cap and "無對映" in cap
    for st in ("**OK**", "**Stale**", "**Missing**", "**Unavailable**", "**Not Evaluated**"):
        assert st not in cap, st
    # 條文：不新增第六態、Not Evaluated 保留原義且不併入 ⬜、同列拆欄
    for must in ("**只有五態**：OK／Missing／Stale／Unavailable／Not Evaluated", "**不得新增第六態**",
                 "`Not Evaluated` **保留原有正式語意**", "**`⬜ 尚未接線` 不是 Data State**",
                 "⛔ 映射成 Not Evaluated、Missing、Unavailable 或任何第六態",
                 "Level 1 符號集**不含 Not Evaluated 的專用符號**", "Not Evaluated 另以**既有字樣**", "不併入 `⬜`（尚未接線）",
                 "必須拆成不同欄位", "`狀態(Data State)` 欄與 `接線(Capability)` 欄", "⛔ 單一 status 欄混用",
                 "只准出現在 `接線(Capability)` 欄"):
        assert must in s, must
    # Level 1 表格列本身也是兩欄（不是單一 status）
    l1 = next(ln for ln in s.split("\n") if ln.startswith("| **Level 1 使用者可讀摘要**"))
    assert "`狀態(Data State)`" in l1 and "`接線(Capability)`" in l1


def test_active_contract_health_example_rows_never_put_wiring_in_data_state_column():
    s = _health_section(_read(ACTIVE_REL))
    i = s.index("| 項目 | 狀態(Data State) | 接線(Capability) |")
    rows = [ln for ln in s[i:].split("\n")[2:] if ln.startswith("|")]
    assert rows
    for ln in rows:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        assert "尚未接線" not in cells[1], ln            # Data State 欄
        assert cells[1] in ("✅ 正常", "◷ 可能過期", "◇ 資料未備", "⛔ 來源不可用", "（不適用）"), ln


def test_active_contract_dev_surface_clauses_and_ui2_dev_is_not_login_evidence():
    s = _read(ACTIVE_REL)
    i = s.index("## §6 Preview 控制")
    sec = s[i:s.index("## §7 ")]
    for must in ("`?ui2_dev=1`", "developer-only surface", "不放 sidebar", "不增加正式導航", "production presentation 不依賴它",
                 "不曝光 secret／credential／raw developer diagnostics",
                 "`ui2_dev` query parameter 只能控制 developer preview surface", "不得與正式 auth state 混用",
                 "不能被當成登入證據"):
        assert must in sec, must
    # (b)：稽核面預設收合、🎯 不做成資料牆
    assert "預設收合、不搶主 UI" in s
    for must in ("選股條件只顯示精簡、人類可讀版本", "完整 rule detail／engineering detail 不上主頁",
                 "全部候選／CSV 為次層操作", "不得讓這些功能把 🎯 主頁做成資料牆"):
        assert must in s, must


# ---------------------------------------------------------------- (xi) DEC-131（客戶 (17)：P3／A2／T_new_1b 規格錯誤）
def _dec131() -> str:
    d = _read("docs/DECISIONS.md")
    return d[d.index("### DEC-131｜"):]


def test_dec131_records_a2_t_new_1b_error_and_transition_limit():
    d = _dec131()
    f = d[d.index("```\n") + 4:d.index("\n```", d.index("```\n") + 4)]
    for must in ("採用方案 A2", "完整 VM / Evidence 保留，只禁止 Human UI 渲染 L2/L3 evidence expander",
                 "修正測試不代表放寬驗收", "OneBrain 未來仍可從正式 headless Digest 取得完整 evidence"):
        assert must in f, must
    for must in ("T_new_1b 規格錯誤", "錯誤依據", "修正依據", "影響", "test_T_new_1b_vm_keeps_evidence_while_human_ui_hides_it",
                 "SHOWN_FOLDS", "過渡期使用者看不到完整說明", "REGIME_SEE_WHY", "P6 資料健康度承接",
                 "NUI2-P3-FRESH-SYSINFO-HIDDEN"):
        assert must in d, must


def test_p3_closure_is_recorded_in_backlog_and_active_contract():
    b = _read("docs/BACKLOG.md")
    assert "NUI2-PLAN1007-P3-T1B-TENSION" in b and "closed（DEC-131）" in b
    assert "#### 📌 P3 完成補記" in b
    c = _read(ACTIVE_REL)
    assert "T_new_1b 驗收對象" in c and "過渡期限制（P3）" in c


# ---------------------------------------------------------------- (xii) P3 evidence baseline 檔 sha256 釘住（防無聲洗白）
#: `tests/fixtures/ui2_p3_evidence_baseline.json` 的 sha256。⚠ 重新產生 baseline 的流程（有意識的 evidence 變更才可做）：
#: ① `python -m tests.test_ui2_p3_evidence_preservation --regen` ② `sha256sum tests/fixtures/ui2_p3_evidence_baseline.json`
#: ③ 把新值填到下面 ④ PR 描述與 BACKLOG 說明為何 evidence 變了（不得是縮小）。
_P3_BASELINE_SHA256 = "a8ab54b0d31f78db976ed75cd8a7909562033ce28ce38f9e37f532a200e8ad53"


def test_p3_evidence_baseline_file_is_pinned_by_sha256():
    import hashlib
    got = hashlib.sha256((ROOT / "tests" / "fixtures" / "ui2_p3_evidence_baseline.json").read_bytes()).hexdigest()
    assert got == _P3_BASELINE_SHA256, (
        "evidence baseline 被改動。若是有意識的 evidence 變更：照本檔註解的四步驟重新產生並更新釘值；"
        "若不是，請還原——不得為了讓 evidence-preservation 測試通過而改 baseline。")


# ---------------------------------------------------------------- (xiii) DEC-132（客戶 (18)：兩灰區裁定＋Digest 缺口維持＋P2 文字線框先行）
P2_WIREFRAME_REL = "docs/vnext/NEWUI2_P2_TEXT_WIREFRAME_2026-11-04.md"


def _dec132() -> str:
    d = _read("docs/DECISIONS.md")
    return d[d.index("### DEC-132｜"):]


def test_dec132_fence_has_customer_text_and_records_both_rulings():
    d = _dec132()
    a = d.index("```\n") + 4
    f = d[a:d.index("\n```", a)]
    for must in ("維持不在四頁一般 Human UI 顯示", "未來由 P6「資料健康度」承接", "不得刪 VM、資料來源、provenance 或其他 Evidence",
                 "暫不恢復舊 L3 expander", "保留為後續使用者分析能力的設計候選", "不自行開工或新增公式",
                 "VM 保存不等於 Digest 已有", "未證實之前不得宣稱 OneBrain 可讀完整資料",
                 "本輪只授權提出線框與驗證資料欄位，不授權直接實作新版面", "TWII 最新收盤值不等於歷史圖表資料"):
        assert must in f, must
    # 落盤段（fence 之外）：兩項裁定、Digest 缺口維持、P2 不授權實作、文件措辭規則
    rest = d[d.index("\n```", a) + 4:]
    for must in ("裁定 1", "裁定 2", "仍 Pending／設計候選", "不是核准功能", "NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY",
                 "維持 open", "P2 線框待客戶驗收", "不授權任何實作", "NEWUI2_P2_TEXT_WIREFRAME_2026-11-04.md"):
        assert must in rest or must in d, must


def test_fresh_sysinfo_is_recorded_as_customer_ruling_not_overridable_reading():
    b = _read("docs/BACKLOG.md")
    row = next(l for l in b.splitlines() if l.startswith("| **NUI2-P3-FRESH-SYSINFO-HIDDEN**"))
    assert "DEC-132" in row and "客戶裁示" in row and "維持不在四頁一般 Human UI" in row
    assert "~~**實作組讀法，可由總管／客戶推翻**~~" in row          # 原文刪除線保留，不刪
    full = next(l for l in b.splitlines() if l.startswith("| **NUI2-P3-FULL-TABLE-HIDDEN**"))
    assert "DEC-132" in full and "設計候選" in full and "不是核准功能" in full
    c = _read(ACTIVE_REL)
    assert "DEC-132" in c and "設計候選" in c and "不是核准功能" in c
    assert "~~🎯 跨季趨勢／完整分析是否保留為使用者功能~~" in c      # 原文刪除線保留
    # 舊 DEC 原文不改（DEC-131 §三 第 3 點仍在）
    assert "是**總管可推翻的讀法**" in _read("docs/DECISIONS.md")


def test_p2_text_wireframe_exists_declares_pending_acceptance_and_has_sections_a_to_g():
    w = _read(P2_WIREFRAME_REL)
    head = w[:1200]
    assert "待客戶驗收" in head and "不授權實作" in head
    for sec in ("## A. 現況首屏", "## B. ", "## C. P2 最小差異", "## D. 保留清單核對", "## E. 資料位置對照",
                "## F. 驗收準則與施工邊界", "## G. 待客戶確認項"):
        assert sec in w, sec
    for must in ("以 Wireframes §2.1", "DEC-122 Q3=A", "DEC-127", "TWII 最新收盤值≠歷史圖表資料",
                 "⛔ 不繪製假走勢線".replace("⛔ ", ""), "TWII_SOURCE_TEXT", "get_twii_trend_view(n)", "T_new_6"):
        assert must in w, must


def test_dec132_is_wired_into_backlog_state_handoff_and_checklist():
    assert "DEC-132 落盤與 P2" in _read("docs/BACKLOG.md")
    assert "## 63. DEC-132" in _read("docs/PROJECT_STATE.md")
    h = _read("docs/HANDOFF.md")
    tail = h[h.rindex("Safe Handoff（2026-11-04 DEC-132"):]
    assert "客戶驗收 P2 文字線框" in tail and "驗收通過前不得實作" in tail and "設計候選" in tail
    assert "## §24 DEC-132" in _read("docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md")
    b = _read("docs/BACKLOG.md")
    row = next(l for l in b.splitlines() if l.startswith("| **NUI2-ACTIVE-CONTRACT-VS-WIREFRAME-RISK-ORDER**"))
    assert "已判定" in row and "~~open~~" in row
    # Digest 缺口維持 open（不得被本批結案）
    dg = next(l for l in b.splitlines() if l.startswith("| **NUI2-P3-DIGEST-CLOSURE-STATIC-ONLY**"))
    assert "open（未驗）" in dg


def test_no_document_claims_onebrain_can_read_complete_data():
    """DEC-132 §三 文件措辭規則：不得宣稱 OneBrain 可讀完整資料／evidence 已在 Digest（反向守衛，僅掃本批新增文件）。"""
    for rel in (P2_WIREFRAME_REL,):
        w = _read(rel)
        for bad in ("OneBrain 可讀完整資料已", "evidence 已在 Digest", "Digest 已涵蓋"):
            assert bad not in w, (rel, bad)


def test_audit_checklist_section_24_is_not_self_checked_and_wireframe_discloses_g3():
    c = _read("docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md")
    sec = c[c.index("## §24 DEC-132"):]
    assert "[ ]" in sec and not re.search(r"\[[xX]\]", sec), "§24 不得自勾"
    w = _read(P2_WIREFRAME_REL)
    assert "G-3" in w and "≥160px" in w and "第一屏不增不減」不實" in w
    # G-2：頻率欄預設省略，「日頻」須明示同意（自相矛盾已修）
    assert "推薦 B**" in w and "沉默不等於同意" in w
