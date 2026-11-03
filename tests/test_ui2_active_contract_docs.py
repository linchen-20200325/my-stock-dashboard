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
    # T10：measure_viewport 以 Preview 控制 expander 為操作入口與頁底錨點
    ("tests/ui2_viewport/measure_viewport.py", "_select_box"),
    # 依賴 Preview 控制 selectbox（ui2_feed／ui2_scenario／ui2_account）的 AppTest（P1③ 移到開發面時須同步）
    ("tests/test_ui2_batch2.py", "test_full_rendered_page_has_no_global_update_time"),
    ("tests/test_ui2_batch3.py", "_market_dom_order"),
    ("tests/test_ui2_batch3.py", "_at_target"),
    ("tests/test_ui2_batch3.py", "test_cta_order_in_real_page_default_lane"),
    ("tests/test_ui2_batch3.py", "test_me_page_switches_account_in_the_real_app"),
    ("tests/test_ui2_registration_and_boot.py", "test_every_page_switches_and_renders_in_every_scenario"),
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
    # (b) 每個 test_T_new_* 都用 `_xfail("P#")`（或直接 pytest.mark.xfail 且同樣 strict+DEC-128）
    n = 0
    for fn in [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name.startswith("test_T_new_")]:
        ok = False
        for d in fn.decorator_list:
            if isinstance(d, ast.Call) and ast.unparse(d.func) == "_xfail":
                assert re.fullmatch(r"P\d", ast.literal_eval(d.args[0])), fn.name
                ok = True
            elif isinstance(d, ast.Call) and ast.unparse(d.func) == "pytest.mark.xfail":
                k = {x.arg: x.value for x in d.keywords}
                assert isinstance(k.get("strict"), ast.Constant) and k["strict"].value is True, fn.name
                assert "DEC-128" in ast.unparse(k["reason"]), fn.name
                ok = True
        assert ok, f"{fn.name} 沒有 strict xfail"
        n += 1
    assert n >= 7
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
