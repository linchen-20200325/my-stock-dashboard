"""SA2-f7／SA2-f8（2026-09-29）：「📖 憑什麼」頁 `_clean_reason()` 洗掉狀態符號後的揭露句 ⛔ 不得再指向「下方對照表」。

`_clean_reason()` 只有兩個呼叫端 —— `build_spec_flag_card()`，以及 `build_source_card()` 的 unknown-status 分支
（why ＝ `_clean_reason(probe.error)`）；兩者建的卡**只畫在葉2「資料體檢」**（`_render_user_health_wall()`），
「逐盞門檻對照表」畫在**葉1「教學」**（`_render_edu_leaf()`）—— 兩葉是 `render_page_why()` 裡不同的 `st.tabs`
分頁，卡片所在那一葉的下方沒有對照表 ⇒ 那句只要出現就是把人帶去一個不存在的地方（同 SA2-f4 #742 的病）。
括號內句尾「；完整原文見下方對照表」已在子句界刪掉（只刪不改，K1；同 SA2-f4 #742、SA-r2-f2 #729）。
SA2-f8：同函式 docstring「完整原文仍可在下方的門檻對照表看到」是同一個不成立的前提 —— 加刪除線保留並補事實更正。
SA2-f8 續：同一段 docstring 拿 `stock_kd.no_level_reason` 當「為什麼要洗」的例子，但那一欄從來不經過本函式
（葉1 以 `st.caption` 原文印出）—— 同樣加刪除線保留並補事實更正（洗 glyph 是防禦）。

⚠️ 目前潛伏：當下 L0 兩盞被標記的燈（`margin`、`stock_trend`）的原因欄都沒有狀態符號，來源卡那一支
只在 L0 登錄表回了本頁不認得的狀態、或某一列不是 Mapping 時才走到（以當下 L0 兩種都走不到）——
所以下面凡是要走「洗過 glyph」那條路的，都是**合成輸入**。

(a) 含狀態 glyph → 揭露句在（「原文裡的燈號符號已移除」）、⛔ 沒有「對照表」；逐字 ＝ 修前只少「；」＋那一句。
(b) 不含 glyph → 原文原樣（含當下 L0 被標記的燈的原因原文）。
(c) 空值（空字串／全空白；以及洗完才變空的「只有 glyph」）→ `UNKNOWN_ERROR_TEXT`（⛔ 不接揭露句）。
(d) 兩個呼叫端各實跑一次（含 glyph 的原因）→ why ⛔ 沒有「對照表」；v2 卡面與「▸ 詳細」摺疊區也沒有；
    另以整頁實跑（AppTest，合成注入 glyph）驗葉2 畫出來的樣子。
(e) 突變：把刪掉的那段加回去 → (a)(d) 的判準必須轉紅。
(f) 前提守衛（結構版）：呼叫端與各自所在的分頁 —— 哪天卡與表同葉，刪句的理由就不成立 → 紅燈，請重評
    （⛔ 不自己新寫一句指路，K1）。
(g) SA2-f8（含 SA2-f8 續）：docstring 的兩處舊前提只准留在刪除線裡（病史保留的標準寫法）；
    另以結構版前提守衛釘住「`no_level_reason` 不是本函式的輸入」。
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import pathlib
import re
import sys
import textwrap
import types

import pytest

from shared.ui_state import UI_DEGRADED, UI_FAILED, UI_STATE_META, UI_UNWIRED
from src.ui.tabs.tab_today import Note, scrub_state_glyphs
from src.ui.views import page_why as P

#: 被刪的那一句（修前字面，逐字抄 —— ⛔ 不由現行常數組出來）。
_DELETED = "完整原文見下方對照表"
#: 修前（baseline `da4eb94`）接在洗過的原因後面的整段揭露（逐字抄）。
_OLD_SUFFIX = ("（原文裡的燈號符號已移除，以免和這張卡自己的狀態燈"
               "變成兩個互相矛盾的說法；完整原文見下方對照表）")
#: 刪後應得的揭露（手寫，第二把尺）。
_NEW_SUFFIX = "（原文裡的燈號符號已移除，以免和這張卡自己的狀態燈變成兩個互相矛盾的說法）"
_DISCLOSURE = "原文裡的燈號符號已移除"
#: 全部狀態 glyph（L0 SSOT；`Note` 拒收的就是這一組）。
_GLYPHS: tuple[str, ...] = tuple(_g for _n, _g, _h in UI_STATE_META.values())


def _assert_trimmed(why: str, *, cleaned: str) -> None:
    """洗過 glyph 的 why：⛔ 沒有那一句；揭露句還在；逐字 ＝ 洗過的原文 ＋ 刪後的揭露。"""
    assert _DELETED not in why, f"why 仍指向（葉2 下方不存在的）對照表：{why!r}"
    assert _DISCLOSURE in why, f"洗過就要說（§1）—— 揭露句不見了：{why!r}"
    assert why == cleaned + _NEW_SUFFIX, f"why 不是「洗過的原文 ＋ 刪後的揭露」：{why!r}"


# ── 刪後的逐字值 ───────────────────────────────────────────────────────────
def test_new_suffix_is_the_old_one_minus_the_clause_and_its_separator():
    """只刪不改（K1）：修前 ＝ 刪後在右括號前補回「；」＋那一句，其餘一字不差；截在子句界。"""
    assert _OLD_SUFFIX == _NEW_SUFFIX[:-1] + "；" + _DELETED + _NEW_SUFFIX[-1]
    assert _NEW_SUFFIX.startswith("（") and _NEW_SUFFIX.endswith("說法）")


# ── (a) 含狀態 glyph ───────────────────────────────────────────────────────
@pytest.mark.parametrize("glyph", _GLYPHS)
def test_a_reason_with_a_state_glyph_keeps_the_disclosure_but_not_the_pointer(glyph):
    why = P._clean_reason(f"L0 寫的原因{glyph}後半句")
    assert glyph not in why
    assert "對照表" not in why, why
    _assert_trimmed(why, cleaned="L0 寫的原因後半句")
    Note(now="x", why=why, where="y")                 # 洗過的字放得進三要素（不得 raise）


def test_a_several_glyphs_and_the_spaces_they_leave_behind():
    """實測寫法（同 `test_p05_why_view` 那條）：兩個 glyph、各帶前後空白 → 空白收成一格。"""
    why = P._clean_reason("抓不到 🔴 而且 🟢 也不對")
    assert "對照表" not in why, why
    _assert_trimmed(why, cleaned="抓不到 而且 也不對")


# ── (b) 不含 glyph ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", ["L0 寫的原因，沒有任何狀態符號。", "第一段\n\n**第二段**（含 Markdown）"])
def test_b_reason_without_glyphs_passes_through_verbatim(raw):
    assert P._clean_reason(raw) == raw


def test_b_the_current_l0_reasons_reach_the_card_verbatim():
    """當下 L0 被標記的燈：原因欄沒有 glyph ⇒ why 就是原文（⛔ 沒有揭露句，也沒有指路）。"""
    scan = P.load_specs()
    flagged = scan.unwired + scan.degraded
    assert flagged, "L0 一盞被標記的燈都沒有 → 這條會空轉"
    for row in flagged:
        reason = row.unwired_reason if not row.wired else row.degraded_reason
        why = P.build_spec_flag_card(row)[0].note.why
        if any(_g in reason for _g in _GLYPHS):     # L0 日後寫進 glyph：走 (a) 的判準
            _assert_trimmed(why, cleaned=scrub_state_glyphs(reason)[0])
        else:
            assert why == reason, f"{row.key} 的原因被改寫了：{why!r}"


# ── (c) 空值 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_c_empty_reason_is_the_unknown_text(raw):
    assert P._clean_reason(raw) == P.UNKNOWN_ERROR_TEXT


@pytest.mark.parametrize("raw", ["🔴", " 🟠 ⛔ "])
def test_c_a_reason_that_is_only_glyphs_is_also_the_unknown_text(raw):
    """洗完才變空 → 同一句 `UNKNOWN_ERROR_TEXT`（修前修後同樣⛔ 不接揭露句，自然也沒有指路）。"""
    assert P._clean_reason(raw) == P.UNKNOWN_ERROR_TEXT


# ── (d) 兩個呼叫端各實跑一次 ───────────────────────────────────────────────
def _glyph_rows(rows):
    """每一盞被標記的燈，原因欄前面補一個 🔴（合成；當下 L0 兩盞都沒有 glyph）。"""
    out = []
    for row in rows:
        if not row.wired:
            out.append((dataclasses.replace(row, unwired_reason="🔴" + row.unwired_reason),
                        row.unwired_reason))
        else:
            out.append((dataclasses.replace(row, degraded_reason="🔴" + row.degraded_reason),
                        row.degraded_reason))
    return out


def _assert_v2_face_and_fold(built, *, cleaned: str) -> None:
    """v2 卡面（短句）與「▸ 詳細」摺疊區：⛔ 沒有那一句；摺疊區的「為什麼」＝ 刪後的完整原文。"""
    html = P.v2_card_html(*built)               # 短句摘錄仍對得上（對不上會 KeyError）
    assert _DELETED not in html and "下方對照表" not in html, built[0].key
    _short, full = P.v2_short_rows(built[0])
    assert dict(full)[P.V2_WHY_FACT_KEY] == P.v2_plain(cleaned + _NEW_SUFFIX)
    assert _DELETED not in dict(_short)[P.V2_WHY_FACT_KEY]


def _d1_spec_flag_builts(module: types.ModuleType = P):
    scan = P.load_specs()
    pairs = _glyph_rows(scan.degraded)
    assert pairs, "L0 一盞 degraded 的燈都沒有 → 這條會空轉"
    return [(module.build_spec_flag_card(row), original) for row, original in pairs]


def test_d1_spec_flag_card_with_a_glyph_in_the_l0_reason():
    for built, original in _d1_spec_flag_builts():
        card = built[0]
        assert card.state == UI_DEGRADED, (card.key, card.state)
        assert "對照表" not in card.note.why, card.note.why
        _assert_trimmed(card.note.why, cleaned=original)
        _assert_v2_face_and_fold(built, cleaned=original)


@pytest.mark.usefixtures("synthetic_unwired_lamp")
def test_d1_the_unwired_branch_of_the_same_caller():
    """`build_spec_flag_card()` 未接線那一支（`unwired_reason`）同一條判準；合成燈見 conftest。"""
    scan = P.load_specs()
    assert scan.unwired, "合成的未接線燈沒被掃到 → 這條會空轉"
    for row, original in _glyph_rows(scan.unwired):
        card = P.build_spec_flag_card(row)[0]
        assert card.state == UI_UNWIRED, (card.key, card.state)
        assert "對照表" not in card.note.why, card.note.why
        _assert_trimmed(card.note.why, cleaned=original)


def _entry(status: str) -> dict:
    return {"category": "🇹🇼 台灣總經", "frequency": "monthly", "last_status": status,
            "last_error": None, "last_rows": None, "last_ms": None, "last_called_at": None}


def _d2_source_probe(module: types.ModuleType = P):
    """unknown-status 分支；glyph 放在 `probe.error` 的子句界（⛔ 不放進 status —— status 會原樣進 `now`）。"""
    base = module.probe_from_entry("fetch_x", _entry("weird-status"))
    assert base.unknown_status == "weird-status" and "—— 在確認" in base.error, base
    return dataclasses.replace(base, error=base.error.replace("—— 在確認", "—— 🔴在確認", 1)), base.error


def test_d2_source_card_unknown_status_branch_with_a_glyph_in_probe_error():
    probe, original = _d2_source_probe()
    built = P.build_source_card(probe)
    card = built[0]
    assert card.state == UI_FAILED and card.note.now.startswith(P.SOURCE_UNKNOWN_NOW_HEAD), card
    assert "對照表" not in card.note.why, card.note.why
    _assert_trimmed(card.note.why, cleaned=original)
    _assert_v2_face_and_fold(built, cleaned=original)


def test_d2_the_natural_path_a_non_mapping_row_whose_name_carries_a_glyph(monkeypatch):
    """同一分支的另一種原文（「這一列不是 Mapping」）走真的 `load_sources()` —— 名字裡的 glyph 進了 `probe.error`。"""
    monkeypatch.setattr(P, "get_monitor_registry", lambda: {"🔴壞名": ["不是", "Mapping"]})
    scan = P.load_sources()
    assert scan.readable and len(scan.probes) == 1
    probe = scan.probes[0]
    assert probe.unknown_status and "🔴" in probe.error, probe
    built = P.build_source_card(probe)
    card = built[0]
    assert card.state == UI_FAILED, card
    assert "對照表" not in card.note.why, card.note.why
    cleaned = scrub_state_glyphs(probe.error)[0]
    _assert_trimmed(card.note.why, cleaned=cleaned)
    _assert_v2_face_and_fold(built, cleaned=cleaned)


# ── (d) 整頁實跑：葉2「資料體檢」（合成注入 glyph；當下 L0 走不到這條路）───────────────
_PAGE_SCRIPT = """
    import dataclasses
    from src.ui.views import page_why as P

    _orig_registry, _orig_specs = P.get_monitor_registry, P.load_specs

    def _specs_with_glyphs():
        _s = _orig_specs()
        return dataclasses.replace(_s, rows=tuple(
            dataclasses.replace(_r, degraded_reason="🔴" + _r.degraded_reason)
            if (_r.wired and not _r.discriminative) else _r for _r in _s.rows))

    P.get_monitor_registry = lambda: {"🔴壞名": ["不是", "Mapping"]}
    P.load_specs = _specs_with_glyphs
    try:
        P.render_page_why()
    finally:
        P.get_monitor_registry, P.load_specs = _orig_registry, _orig_specs
"""


def _tab_text(tab) -> str:
    return ("\n".join(m.value for m in tab.markdown)
            + "\n" + "\n".join(c.value for c in tab.caption))


def test_d_the_data_health_leaf_as_drawn_keeps_the_disclosure_without_the_pointer(tmp_path):
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_sa2f7_why.py"
    script.write_text(textwrap.dedent(_PAGE_SCRIPT), encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    _before = (P.get_monitor_registry, P.load_specs)
    at.run()
    assert not at.exception, at.exception
    assert (P.get_monitor_registry, P.load_specs) == _before, "腳本裡的注入沒有還原"
    tabs = {t.label: t for t in at.tabs}
    health, edu = tabs[P.LEAF_DATA_HEALTH_TITLE], tabs[P.LEAF_EDU_TITLE]
    health_text, edu_text = _tab_text(health), _tab_text(edu)

    # 反證：兩個呼叫端的卡都真的帶著揭露句畫在這一葉（否則下面「沒有那句」會空轉而假綠）。
    degraded = P.load_specs().degraded
    assert degraded
    assert health_text.count(_DISCLOSURE) >= len(degraded) + 1, health_text.count(_DISCLOSURE)
    assert _DELETED not in health_text and "下方對照表" not in health_text

    # 前提（實跑版）：對照表只在葉1；葉2 冷啟動一張表都沒有。
    assert "逐盞門檻對照表" in edu_text and edu.dataframe
    assert "逐盞門檻對照表" not in health_text and not health.dataframe
    # SA2-f8 docstring 寫的「原文在畫面別處另有出處」之一：葉1 對照表下方的說明列（原文，含 glyph）。
    for row in degraded:
        assert "🔴" + row.degraded_reason.split("\n", 1)[0] in edu_text, row.key


# ── (e) 突變：把那一段加回去 → 判準必須轉紅 ────────────────────────────────
def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 原始碼裡每一組 `old` **恰好一處**換成 `new`，載成獨立的新模組（同 `test_v2_sa2f4_spec_flag_where`）。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_sa2f7_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


_ANCHOR = '                   "變成兩個互相矛盾的說法）")\n'
_RESTORED = '                   "變成兩個互相矛盾的說法；完整原文見下方對照表）")\n'


def test_e_mutation_restoring_the_clause_is_caught():
    m = _mutant(P, (_ANCHOR, _RESTORED))
    # 突變版回到修前原文 ⇒ 判準對它必須轉紅。
    assert m._clean_reason("抓不到 🔴 而且 🟢 也不對") == "抓不到 而且 也不對" + _OLD_SUFFIX
    with pytest.raises(AssertionError):
        _assert_trimmed(m._clean_reason("L0 寫的原因🔴後半句"), cleaned="L0 寫的原因後半句")
    for built, original in _d1_spec_flag_builts(m):
        assert built[0].note.why == original + _OLD_SUFFIX
        with pytest.raises(AssertionError):
            _assert_trimmed(built[0].note.why, cleaned=original)
        with pytest.raises(AssertionError):
            _assert_v2_face_and_fold(built, cleaned=original)
    probe, original = _d2_source_probe(m)
    built = m.build_source_card(probe)
    assert built[0].note.why == original + _OLD_SUFFIX
    with pytest.raises(AssertionError):
        _assert_trimmed(built[0].note.why, cleaned=original)
    # 現行版照樣通過（同一組輸入）。
    _assert_trimmed(P._clean_reason("L0 寫的原因🔴後半句"), cleaned="L0 寫的原因後半句")


# ── (f) 前提守衛（結構版）：誰呼叫、畫在哪一個分頁 ─────────────────────────
def _module_tree() -> ast.Module:
    return ast.parse(pathlib.Path(P.__file__).read_text(encoding="utf-8"))


def _callers_of(name: str) -> set[str]:
    """本模組裡「函式體內呼叫了 `name`」的頂層函式名（AST，不數字樣）。"""
    out: set[str] = set()
    for fn in _module_tree().body:
        if isinstance(fn, ast.FunctionDef) and any(
                isinstance(n, ast.Call) and getattr(n.func, "id", None) == name
                for n in ast.walk(fn)):
            out.add(fn.name)
    return out


def _tab_of_each_render() -> dict[str, set[str]]:
    """`render_page_why()` 裡每一個 `with _leafN:` 區塊 → 區塊內呼叫的函式名。"""
    fn = next(n for n in _module_tree().body
              if isinstance(n, ast.FunctionDef) and n.name == "render_page_why")
    out: dict[str, set[str]] = {}
    for w in ast.walk(fn):
        if isinstance(w, ast.With):
            for item in w.items:
                if isinstance(item.context_expr, ast.Name):
                    out.setdefault(item.context_expr.id, set()).update(
                        n.func.id for n in ast.walk(w)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name))
    return out


def test_f_premise_both_callers_are_drawn_on_another_leaf_than_the_table():
    """刪句的理由是「兩個呼叫端的卡都在葉2、對照表在葉1」。哪天同葉 → 紅，請重評是否補回指路
    （⛔ 不自己新寫一句，K1）。"""
    assert _callers_of("_clean_reason") == {"build_spec_flag_card", "build_source_card"}
    assert _callers_of("build_spec_flag_card") == {"build_spec_flag_cards"}
    assert _callers_of("build_spec_flag_cards") == {"_render_user_health_wall"}
    assert _callers_of("build_source_card") == {"_render_user_health_wall"}
    assert _callers_of("_spec_table_rows") == {"_render_edu_leaf"}
    tabs = _tab_of_each_render()
    edu_tabs = {t for t, calls in tabs.items() if "_render_edu_leaf" in calls}
    health_tabs = {t for t, calls in tabs.items() if "_render_user_health_wall" in calls}
    assert len(edu_tabs) == 1 and len(health_tabs) == 1 and edu_tabs != health_tabs, tabs


def test_f_the_table_cells_never_held_the_reason_text():
    """SA2-f8 docstring：「那幾張表（`st.dataframe`）的儲存格裡本來就沒有原因原文」。"""
    scan = P.load_specs()
    flagged = [r for r in scan.rows if r.threshold_caveat]
    assert flagged
    for row in flagged:
        cells = P._spec_table_rows([row])[0].values()
        assert not any(row.threshold_caveat in str(v) for v in cells), row.key


# ── (g) SA2-f8：docstring 的舊前提只准留在刪除線裡 ─────────────────────────
#: `(舊句的穩定片段（逐字抄）, 為什麼不成立)`。
_STALE_PREMISES: tuple[tuple[str, str], ...] = (
    ("完整原文仍可在下方的門檻對照表看到",
     "SA2-f8：兩個呼叫端都在葉2、對照表在葉1"),
    # SA2-f8 續（2026-09-29）：拿來當「為什麼要洗」例子的 `stock_kd.no_level_reason` 從來不經過本函式。
    ("整段規格揭露消失",
     "SA2-f8 續：那個例子（`stock_kd.no_level_reason`）只在葉1 以 `st.caption` 原文印出，不是本函式的輸入"),
)


@pytest.mark.parametrize(("stale", "reason"), _STALE_PREMISES, ids=["SA2-f8", "SA2-f8-cont"])
def test_g_the_stale_premise_survives_only_inside_a_strikethrough(stale, reason):
    doc = P._clean_reason.__doc__ or ""
    assert "SA2-f8" in doc, "事實更正不見了"
    assert stale not in re.sub(r"~~.*?~~", "", doc, flags=re.S), (
        f"`_clean_reason` 的 docstring 又在主張「{stale}」—— {reason}；"
        "要留舊句當病史 → 包進刪除線")


def test_g_the_no_level_reason_never_reaches_this_function():
    """SA2-f8 續的前提（結構版）：兩個呼叫端的函式體裡都沒有碰 `no_level_reason`。
    哪天有人把它接進來 → 紅燈，docstring 那段更正要重評（劃掉的例子會變成真的）。"""
    callers = _callers_of("_clean_reason")
    assert callers == {"build_spec_flag_card", "build_source_card"}, callers
    for fn in _module_tree().body:
        if isinstance(fn, ast.FunctionDef) and fn.name in callers:
            touched = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
            assert "no_level_reason" not in touched, fn.name
