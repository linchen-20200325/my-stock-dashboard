"""SA2-f4（2026-09-28）：「📖 憑什麼」頁 L0 規格標記卡的「去哪補」⛔ 不得再指向「下方的門檻對照表」。

`build_spec_flag_card()` 建的卡**只畫在葉2「資料體檢」**（`_render_user_health_wall()`）；
「逐盞門檻對照表」畫在**葉1「教學」**（`_render_edu_leaf()`）—— 兩葉是 `render_page_why()` 裡
不同的 `st.tabs` 分頁，卡片所在那一葉的下方沒有對照表 ⇒ 那句指引把人帶去一個不存在的地方。
句尾「；下方的門檻對照表有這一盞的完整規格」已在子句界刪掉（只刪不改，K1；同 SA-r2-f2 #729）。

① 刪後的逐字值：舊值 ＝ 新值 ＋「；」＋ 被刪的那一句（其餘一字不差）。
② 實際建出來的卡（degraded ＝ 當下 L0；unwired ＝ conftest 合成）與 v2 卡面（含「▸ 詳細」摺疊區）。
③ 整頁實跑（AppTest）：葉2「資料體檢」那一分頁真的畫出規格標記卡，而且不再出現那句。
④ 前提守衛：對照表哪天搬進葉2（或規格標記卡搬去葉1），刪句的理由就不成立 → 紅燈，請重評。
⑤ 突變：把那一句加回去 → ①② 的判準必須轉紅。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
import textwrap
import types

import pytest

from shared.ui_state import UI_DEGRADED, UI_UNWIRED
from src.ui.tabs.tab_today import NO_EXIT_MARKER
from src.ui.views import page_why as P

#: 被刪的那一句（修前字面，逐字抄 —— ⛔ 不由現行常數組出來）。
_DELETED = "下方的門檻對照表有這一盞的完整規格"
#: 修前（baseline `e23ff2f`）的完整 `Note.where`（含 Markdown 記號）。
#: 只有開頭的「沒有出口」標記走 SSOT 常數（同 `test_v2_silent_fail_b5_vix` 用同一組原料重組舊值的作法），
#: 其餘逐字抄。
_OLD_WHERE = (f"{NO_EXIT_MARKER} —— 這是**規格層面**的已知限制，"
              "不是這一輪抓壞了，重按幾次都一樣；"
              "下方的門檻對照表有這一盞的完整規格")
#: 刪後應得的值 ＝ 舊值拿掉「；」＋ 那一句。
_NEW_WHERE = _OLD_WHERE.removesuffix("；" + _DELETED)


def _assert_trimmed(builts) -> None:
    """每一張規格標記卡的 where：⛔ 沒有那一句；其餘字元與修前逐字相同（只少「；」＋那一句）。"""
    assert builts, "一張規格標記卡都沒有 → 下面的判準會空轉"
    for built in builts:
        card = built[0]
        where = card.note.where
        assert _DELETED not in where and "門檻對照表" not in where, (
            f"{card.key} 的去哪補仍指向（葉2 下方不存在的）門檻對照表：{where!r}")
        assert _OLD_WHERE == where + "；" + _DELETED, (
            f"{card.key} 的 where 不是「修前原文只少『；』＋那一句」：{where!r}")
        assert not where.endswith(("；", "，", "、", "——", " ")), f"{card.key} 截斷處不在子句界：{where!r}"


def _flag_builts(mod: types.ModuleType = P):
    return mod.build_spec_flag_cards(mod.load_specs())


# ── ① ② 刪後的逐字值 ＋ 實際建出來的卡 ─────────────────────────────────────────
def test_new_where_is_the_old_one_minus_the_clause_and_its_separator():
    assert _NEW_WHERE != _OLD_WHERE and _OLD_WHERE == _NEW_WHERE + "；" + _DELETED
    assert _NEW_WHERE == f"{NO_EXIT_MARKER} —— 這是**規格層面**的已知限制，不是這一輪抓壞了，重按幾次都一樣"


def test_degraded_flag_cards_carry_the_trimmed_where():
    builts = _flag_builts()
    assert builts and all(b[0].state == UI_DEGRADED for b in builts), [
        (b[0].key, b[0].state) for b in builts]
    _assert_trimmed(builts)
    assert {b[0].note.where for b in builts} == {_NEW_WHERE}


@pytest.mark.usefixtures("synthetic_unwired_lamp")
def test_unwired_flag_cards_carry_the_same_trimmed_where():
    """where 與 `row.wired` 無關（兩態同一句）—— 未接線那一支也要一起驗，不只驗當下 L0 有的 degraded。"""
    scan = P.load_specs()
    assert scan.unwired, "合成的未接線燈沒被掃到 → 這條會空轉"
    builts = tuple(P.build_spec_flag_card(r) for r in scan.unwired)
    assert all(b[0].state == UI_UNWIRED for b in builts), [(b[0].key, b[0].state) for b in builts]
    _assert_trimmed(builts)


def test_v2_card_face_and_fold_no_longer_carry_the_pointer():
    for built in _flag_builts():
        html = P.v2_card_html(*built)            # 短句摘錄仍對得上（對不上會 KeyError）
        assert _DELETED not in html and "下方的門檻對照表" not in html, built[0].key
        _short, full = P.v2_short_rows(built[0])
        assert dict(full)[P.V2_GUIDE_FACT_KEY] == P.v2_plain(_NEW_WHERE), "摺疊區的去哪補不是刪後原文"


# ── ③ 整頁實跑：葉2「資料體檢」那一分頁 ────────────────────────────────────────
def _tab_text(tab) -> str:
    return ("\n".join(m.value for m in tab.markdown)
            + "\n" + "\n".join(c.value for c in tab.caption))


def test_the_data_health_leaf_as_drawn_no_longer_carries_the_pointer(tmp_path):
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_sa2f4_why.py"
    script.write_text(textwrap.dedent("""
        from src.ui.views.page_why import render_page_why
        render_page_why()
    """), encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    tabs = {t.label: t for t in at.tabs}
    health, edu = tabs[P.LEAF_DATA_HEALTH_TITLE], tabs[P.LEAF_EDU_TITLE]
    health_text, edu_text = _tab_text(health), _tab_text(edu)

    # 反證：規格標記卡**真的畫在這一葉**（否則下面「沒有那句」會空轉而假綠）。
    fold_ids = [P.v2_fold_id(b[0]) for b in _flag_builts()]
    assert fold_ids
    for fid in fold_ids:
        assert f'id="{fid}"' in health_text, f"{fid} 沒畫在「{P.LEAF_DATA_HEALTH_TITLE}」那一葉"
        assert f'id="{fid}"' not in edu_text
    assert _DELETED not in health_text and "下方的門檻對照表" not in health_text
    assert P.v2_plain(_NEW_WHERE) in health_text, "刪後的去哪補原文沒畫出來（摺疊區那一列）"

    # 前提（實跑版）：對照表只在葉1；葉2 冷啟動一張表都沒有。
    assert "逐盞門檻對照表" in edu_text and edu.dataframe
    assert "逐盞門檻對照表" not in health_text and not health.dataframe


# ── ④ 前提守衛（結構版）：誰畫卡、誰畫表、各掛在哪一個分頁 ─────────────────────
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


def test_premise_flag_cards_and_threshold_table_live_on_different_leaves():
    """刪句的理由是「卡在葉2、表在葉1」。哪天兩者同葉，這條紅 → 請重評是否補回指路
    （⛔ 不自己新寫一句，K1）。"""
    assert _callers_of("build_spec_flag_card") == {"build_spec_flag_cards"}
    assert _callers_of("build_spec_flag_cards") == {"_render_user_health_wall"}
    assert _callers_of("_spec_table_rows") == {"_render_edu_leaf"}
    tabs = _tab_of_each_render()
    edu_tabs = {t for t, calls in tabs.items() if "_render_edu_leaf" in calls}
    health_tabs = {t for t, calls in tabs.items() if "_render_user_health_wall" in calls}
    assert len(edu_tabs) == 1 and len(health_tabs) == 1 and edu_tabs != health_tabs, tabs


# ── ⑤ 突變：把那一句加回去 → 判準必須轉紅 ──────────────────────────────────────
def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 原始碼裡每一組 `old` **恰好一處**換成 `new`，載成獨立的新模組（同 `test_v2_find_inspect_p23`）。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_sa2f4_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def test_mutation_restoring_the_clause_is_caught():
    _anchor = '               "不是這一輪抓壞了，重按幾次都一樣"),\n'
    m = _mutant(P, (_anchor, '               "不是這一輪抓壞了，重按幾次都一樣；"\n'
                             '               "下方的門檻對照表有這一盞的完整規格"),\n'))
    builts = _flag_builts(m)
    assert builts and {b[0].note.where for b in builts} == {_OLD_WHERE}, "突變版應回到修前原文"
    with pytest.raises(AssertionError):
        _assert_trimmed(builts)
    _assert_trimmed(_flag_builts())             # 現行版照樣通過
