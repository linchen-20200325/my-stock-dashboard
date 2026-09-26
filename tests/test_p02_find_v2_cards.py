"""「🔍 找標的」4 張卡改走 v2 卡面（客戶 2026-09-25 裁示 1~4）的守衛。

一條測試對應一種說謊方式：
  · 某一態的卡**沒走** v2 卡面（同頁長出兩種卡面）；
  · 某一則 `Note` **沒有短句** → 渲染當下才炸（或被偷偷退回長句）；
  · 短句表有**死列**（對不上任何一則 `Note`）→ 表與程式漂開；
  · 長句被濃縮後**原文不見了**（hover 裡少字）；
  · 「沒有出口」被短句改寫成一個看起來可以按的指路；
  · 使用者文字 / 上游例外**沒被 escape**。
"""
from __future__ import annotations

import ast
import html
import pathlib
import re

import pytest

from shared.ui_state import UI_DEGRADED, UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE
from src.ui.tabs.tab_today import NO_EXIT_MARKER
from src.ui.views import page_find as P
from src.ui_v2 import markup as M
from src.ui_v2 import page_today as V2

_VIEW = pathlib.Path(P.__file__)


class _Frame:
    def __init__(self, n: int) -> None:
        self._n = n

    def __len__(self) -> int:
        return self._n


def _screen(submitted=True, factors=(), **kw):
    req = P.ScreenRequest(submitted=submitted, factors=tuple(factors))
    return P.build_screen_result_card(P.ScreenResult(requested=submitted, **kw), req)


_SECTORS = ({"sector": "半導體", "quadrant": "漲潮"},)

#: (名稱, 產卡函式, 預期狀態)。**每一則 `Note` 至少一個情境**（第 2 條測試會對帳）。
SCENARIOS = [
    # 選股結果
    ("screen.idle", lambda: _screen(submitted=False), UI_IDLE),
    ("screen.empty", lambda: _screen(df=_Frame(0), rows=0, survivors_n=274), UI_EMPTY),
    ("screen.failed", lambda: _screen(error='RuntimeError("finmind quota")'), UI_FAILED),
    ("screen.drift", lambda: _screen(rows=None), UI_FAILED),
    ("screen.live", lambda: _screen(df=_Frame(3), rows=3, survivors_n=10), UI_LIVE),
    ("screen.live_pe_failed", lambda: _screen(
        factors=(P.PE_FACTOR_KEY,), df=_Frame(3), rows=3, pe_n=None), UI_LIVE),
    ("screen.live_pe_empty", lambda: _screen(
        factors=(P.PE_FACTOR_KEY,), df=_Frame(3), rows=3, pe_n=0), UI_LIVE),
    # 產業熱力圖
    ("heat.idle", lambda: P.build_heatmap_card(P.HeatmapReadout(requested=False)), UI_IDLE),
    ("heat.error", lambda: P.build_heatmap_card(
        P.HeatmapReadout(requested=True, error="ValueError('boom')")), UI_FAILED),
    ("heat.all_failed", lambda: P.build_heatmap_card(P.HeatmapReadout(
        requested=True, sectors_n=5, fetched_n=0, any_data=False)), UI_FAILED),
    ("heat.degraded", lambda: P.build_heatmap_card(P.HeatmapReadout(
        requested=True, sectors_n=5, fetched_n=3, any_data=True, complete=False)), UI_DEGRADED),
    ("heat.live", lambda: P.build_heatmap_card(P.HeatmapReadout(
        requested=True, sectors_n=5, fetched_n=5, any_data=True, complete=True)), UI_LIVE),
    # 三大法人資金流向泡泡圖
    ("flow.idle", lambda: P.build_sector_flow_card(P.SectorFlowReadout(requested=False)), UI_IDLE),
    ("flow.failed", lambda: P.build_sector_flow_card(
        P.SectorFlowReadout(requested=True, error="OSError('x')")), UI_FAILED),
    ("flow.degraded", lambda: P.build_sector_flow_card(P.SectorFlowReadout(
        requested=True, ok=True, stale=True, sectors=_SECTORS)), UI_DEGRADED),
    ("flow.empty", lambda: P.build_sector_flow_card(
        P.SectorFlowReadout(requested=True, ok=False, reason="快照未產生")), UI_EMPTY),
    ("flow.live", lambda: P.build_sector_flow_card(P.SectorFlowReadout(
        requested=True, ok=True, sectors=_SECTORS)), UI_LIVE),
    # 條件表單（只有這一種會畫成卡）
    ("form.failed", lambda: (P.build_form_unavailable_card("ImportError('x')"), ()), UI_FAILED),
]
_IDS = [s[0] for s in SCENARIOS]

_EXPECTED_TIER = {"find.screen_form": "t1", "find.screen_result": "t2",
                  "find.heatmap": "t2", "find.sector_flow": "t2"}


_ROW_RE = r'<span class="blk-fact-k">(.*?)</span><span class="blk-fact-v"[^>]*>(.*?)</span>'


def _split(outer: str) -> tuple[str, str]:
    """（卡面, 摺疊區 body）。沒有摺疊區 → body 為空字串。"""
    i = outer.find('<div class="blk-fold">')
    return (outer, "") if i < 0 else (outer[:i], outer[i:])


def _rows(fragment: str) -> list[tuple[str, str]]:
    return [(html.unescape(k), html.unescape(v)) for k, v in re.findall(_ROW_RE, fragment)]


def _face_rows(outer: str) -> list[tuple[str, str]]:
    return _rows(_split(outer)[0])


def _fold_rows(outer: str) -> list[tuple[str, str]]:
    return _rows(_split(outer)[1])


def _fold_id(outer: str) -> str | None:
    m = re.search(r'<input type="checkbox" class="blk-fold-i" id="([^"]+)">', outer)
    return m.group(1) if m else None


# ── 每張卡、每一態都走 v2 卡面 ────────────────────────────────────
@pytest.mark.parametrize("name,build,state", SCENARIOS, ids=_IDS)
def test_every_card_renders_through_the_v2_face_in_every_state(name, build, state):
    card, facts = build()
    assert card.state == state, f"{name}: 情境沒有打到預期狀態"
    assert card.key in P.v2_find.BLOCK_COLS, "這張卡沒有登記在 v2 契約"
    out = P.v2_card_html(card, facts)
    assert f'class="blk blk-{_EXPECTED_TIER[card.key]}"' in out
    v2_state, reason = P.V2_STATE_VOCAB[card.state]
    n = V2.resolve_badge(state=v2_state, miss_reason=reason)
    assert f"bdg bdg-{n} " in out
    assert html.escape(P.v2_plain(card.label), quote=True) in out
    if card.state == UI_LIVE:
        assert html.escape(P.v2_plain(card.value), quote=True) in out, "live 的大字不見了"
    else:
        assert '<div class="blk-val">' not in out, "非 live 大字區必須留白（契約層規則）"


@pytest.mark.parametrize("name,build,state", SCENARIOS, ids=_IDS)
def test_existing_facts_are_all_still_on_the_card(name, build, state):
    """既有 facts 一列不少、順序不變，排在三列短句之後（語意不變，裁示 4）。"""
    card, facts = build()
    rows = _face_rows(P.v2_card_html(card, facts))
    tail = rows[3:] if card.note is not None else rows   # 卡面（摺疊區之前）
    assert [k for k, _ in tail] == [P.v2_plain(k) for k, _ in facts]


# ── 短句表 ─────────────────────────────────────────────────────────
def test_short_phrase_table_covers_every_note_and_has_no_dead_rows():
    hit = set()
    for _name, build, _state in SCENARIOS:
        card, _ = build()
        if card.note is not None:
            key = (card.key, card.note.now)
            assert key in P.V2_SHORT_ROWS, f"{_name}: 這則 Note 沒有短句"
            hit.add(key)
    assert hit == set(P.V2_SHORT_ROWS), (
        f"短句表有對不上任何情境的死列：{set(P.V2_SHORT_ROWS) - hit}")


def _note_now_names_in_builders() -> list[tuple[str, str]]:
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and fn.name.startswith("build_")):
            continue
        for call in ast.walk(fn):
            if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "Note":
                kw = {k.arg: k.value for k in call.keywords}
                now = kw.get("now")
                out.append((fn.name, now.id if isinstance(now, ast.Name) else ast.dump(now)))
    return out


def test_every_note_written_in_a_builder_has_a_short_phrase_row():
    """靜態對帳：`build_*` 裡**每一個** `Note(now=…)` 都要是登記在短句表的常數。

    情境窮舉只證明「我想得到的那幾態」；這條擋的是**日後新增一則 Note 而沒補表**。
    """
    calls = _note_now_names_in_builders()
    assert len(calls) >= 14, f"掃到的 Note 太少，掃描壞了？{calls}"
    registered = {now for (_k, now) in P.V2_SHORT_ROWS}
    for fn, name in calls:
        assert name.isidentifier(), f"{fn}: Note.now 不是常數（{name}）—— 短句表查不到它"
        assert getattr(P, name) in registered, f"{fn}: {name} 沒有登記短句"


def test_an_unregistered_note_raises_and_renders_as_a_red_card(monkeypatch):
    card, facts = _screen(submitted=False)
    monkeypatch.delitem(P.V2_SHORT_ROWS, (card.key, card.note.now))
    with pytest.raises(KeyError, match="V2_SHORT_ROWS"):
        P.v2_card_html(card, facts)


def test_short_rows_are_short_and_never_truncated():
    for (key, now), rows in P.V2_SHORT_ROWS.items():
        assert len(rows) == 3
        for s in rows:
            assert s.strip(), f"{key}: 空短句"
            assert len(s) <= M.FACT_VALUE_MAX_CHARS, f"{key}: 短句會被契約層截斷：{s}"
            assert "**" not in s and "`" not in s


@pytest.mark.parametrize("name,build,state", SCENARIOS, ids=_IDS)
def test_short_rows_are_first_and_come_from_the_table(name, build, state):
    card, facts = build()
    rows = _face_rows(P.v2_card_html(card, facts))
    if card.note is None:
        assert P.V2_NOW_FACT_KEY not in [k for k, _ in rows]
        return
    now_s, why_s, where_s = P.V2_SHORT_ROWS[(card.key, card.note.now)]
    assert rows[:3] == [(P.V2_NOW_FACT_KEY, now_s), (P.V2_WHY_FACT_KEY, why_s),
                        (P.V2_GUIDE_FACT_KEY, where_s)]


def test_no_exit_stays_no_exit():
    """原文「沒有出口」的，短句⛔ 不得改寫成一個看起來可以按的指路（反之亦然）。"""
    for _name, build, _state in SCENARIOS:
        card, _ = build()
        if card.note is None:
            continue
        where_s = P.V2_SHORT_ROWS[(card.key, card.note.now)][2]
        assert (where_s == NO_EXIT_MARKER) == (NO_EXIT_MARKER in card.note.where), _name


# ── ⛔ 一個字都沒刪：完整原文在「▸ 詳細」摺疊區（客戶 2026-09-25 最終裁示）──
@pytest.mark.parametrize("name,build,state", SCENARIOS, ids=_IDS)
def test_full_original_text_is_inside_the_fold_not_only_hover(name, build, state):
    card, facts = build()
    out = P.v2_card_html(card, facts)
    fold = _fold_rows(out)
    if card.note is not None:
        assert fold[:3] == [(P.V2_NOW_FACT_KEY, P.v2_plain(card.note.now)),
                            (P.V2_WHY_FACT_KEY, P.v2_plain(card.note.why)),
                            (P.V2_GUIDE_FACT_KEY, P.v2_plain(card.note.where))], (
            f"{name}: Note 三段完整原文沒有逐字進摺疊區")


@pytest.mark.parametrize("name,build,state", SCENARIOS, ids=_IDS)
def test_nothing_lives_only_in_a_title_attribute(name, build, state):
    """卡上每一個 `title=` 的字，都必須在摺疊區裡**看得到**（手機沒有 hover）。"""
    card, facts = build()
    out = P.v2_card_html(card, facts)
    assert not out.startswith("<div title="), "外層 hover 包裝不該再出現"
    fold_text = "\n".join(v for _k, v in _fold_rows(out))
    for t in re.findall(r' title="([^"]*)"', out):
        assert html.unescape(t) in fold_text, f"{name}: 只活在 hover 的字：{html.unescape(t)[:40]}"


@pytest.mark.parametrize("name,build,state", SCENARIOS, ids=_IDS)
def test_fold_values_are_never_truncated(name, build, state):
    card, facts = build()
    for _k, v in _fold_rows(P.v2_card_html(card, facts)):
        assert not v.endswith(M.FACT_VALUE_ELLIPSIS) or len(v) <= M.FACT_VALUE_MAX_CHARS


def test_red_cards_error_text_is_in_the_fold():
    for build, err in [
        (lambda: _screen(error='RuntimeError("finmind quota")'), 'RuntimeError("finmind quota")'),
        (lambda: P.build_heatmap_card(P.HeatmapReadout(
            requested=True, error="ValueError('heat boom')")), "ValueError('heat boom')"),
        (lambda: P.build_sector_flow_card(P.SectorFlowReadout(
            requested=True, error="OSError('flow boom')")), "OSError('flow boom')"),
        (lambda: (P.build_form_unavailable_card("ImportError('form boom')"), ()),
         "ImportError('form boom')"),
    ]:
        card, facts = build()
        assert card.state == UI_FAILED
        out = P.v2_card_html(card, facts)
        assert err in dict(_fold_rows(out))[P.V2_WHY_FACT_KEY], f"紅卡的例外原文不在摺疊區：{err}"
        assert err not in "".join(v for _k, v in _face_rows(out)), "卡面應只放短句"


def test_fold_ids_unique_stable_and_do_not_collide_with_today():
    ids = {}
    for name, build, _state in SCENARIOS:
        card, facts = build()
        fid = _fold_id(P.v2_card_html(card, facts))
        if fid is None:
            continue
        assert re.fullmatch(r"fold-find-[a-z0-9-]+", fid), fid
        assert not fid.startswith("fold-detail-")
        assert fid == _fold_id(P.v2_card_html(*build())), "同一張卡兩次渲染 id 不同"
        ids.setdefault(card.key, set()).add(fid)
    assert all(len(v) == 1 for v in ids.values()), "同一張卡在不同態 id 不同 → rerun 展開狀態會掉"
    flat = [next(iter(v)) for v in ids.values()]
    assert len(flat) == len(set(flat)) == len(P.v2_find.BLOCK_COLS), "本頁卡之間 id 撞名"


def test_fold_is_collapsed_by_default_and_label_is_the_existing_one():
    out = P.v2_card_html(*_screen(submitted=False))
    assert " checked" not in out
    assert html.escape(M.FOLD_SUMMARY_TEXT) in out


def test_live_card_without_note_or_long_facts_has_no_fold():
    card, facts = P.build_heatmap_card(P.HeatmapReadout(
        requested=True, sectors_n=5, fetched_n=5, any_data=True, complete=True))
    facts = tuple((k, v) for k, v in facts if len(P.v2_plain(v)) <= M.FACT_VALUE_MAX_CHARS)
    assert '<div class="blk-fold">' not in P.v2_card_html(card, facts)


# ── escape ──────────────────────────────────────────────────────────
def test_everything_is_escaped():
    evil = '"><script>alert(1)</script>' + "x" * 50
    card, facts = P.build_heatmap_card(
        P.HeatmapReadout(requested=True, error=f"ValueError('{evil}')"))
    facts = tuple(facts) + ((evil, evil),)
    out = P.v2_card_html(card, facts)
    assert "<script>" not in out
    assert out.count("<div") == out.count("</div>")
    fold = _fold_rows(out)
    assert any(evil in v for _k, v in fold)
    assert (evil, evil) in fold


# ── 渲染接線 ───────────────────────────────────────────────────────
def test_render_routes_registered_cards_to_v2(monkeypatch):
    seen = []
    monkeypatch.setattr(P, "_render_one_v2", lambda c, f=(): seen.append(c.key))
    monkeypatch.setattr(P, "render_card_isolated",
                        lambda *a, **k: pytest.fail("登記的卡不該走舊卡面"))
    for _name, build, _state in SCENARIOS:
        card, facts = build()
        P._render_one(card, facts)
    assert set(seen) == set(P.v2_find.BLOCK_COLS)


def test_css_flag_is_reset_every_run():
    src = _VIEW.read_text(encoding="utf-8")
    body = src.split("def render_page_find() -> None:", 1)[1]
    assert "st.session_state[SS_V2_CSS_DONE] = False" in body
    assert P.SS_V2_CSS_DONE != __import__(
        "src.ui.views.page_today", fromlist=["x"]).SS_V2_CSS_DONE, (
        "與「🚦 今天」頁共用旗標 → 切頁後樣式表不會再吐")


def test_fold_wrap_css_is_scoped_to_this_page_and_invents_no_numbers():
    css = P.V2_FOLD_WRAP_CSS
    assert '[id^="fold-find-"]' in css and "overflow-wrap:anywhere" in css
    assert not re.search(r"\d", css.replace("fold-find-", "")), "不得寫死任何數字"
    out = P.v2_card_html(*_screen(error='RuntimeError("x")'))
    assert re.search(r'class="blk-fold-i" id="fold-find-', out), "選擇器對不上本頁的摺疊 id"


def test_fold_wrap_css_is_emitted_with_the_contract_sheet(monkeypatch):
    sent = []
    ns = type("NS", (), {})()
    ns.session_state = {}
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    P._inject_v2_css()
    assert len(sent) == 1 and P.V2_FOLD_WRAP_CSS in sent[0] and M.page_css(P.V2_CSS_MODE) in sent[0]


def test_aborted_short_phrase_keeps_the_original_reset_wording():
    """短句⛔ 不得改寫原文的事實（原文「額度每日 00:00 重置」，曾被寫成「隔日重置」）。"""
    card, _ = _screen(error='RuntimeError("x")')
    assert "每日 00:00 重置" in card.note.where
    assert "每日 00:00 重置" in P.V2_SHORT_ROWS[(card.key, card.note.now)][2]


# ── #11「▨ 無資料」（客戶 2026-09-26）：本頁**目前沒有任何一張卡登記** ────────────
def test_no_find_card_draws_badge_11():
    """⚠️ `find.screen_result` 的「選股已完成…0 檔」**未登記** —— 同一對 `(key, now)` 也會在
    「存活池讀取失敗」（`_load_survivors()` 回錯 → L3 回空表）與「季快照未就緒」時出現，
    登記它＝把 #11 擴散到真缺漏上（客戶裁示明文禁止）。理由全文見 `HANDOFF.md §6.4`。
    ⇒ 本頁每一種情境的徽章與改動前逐一相同（`screen.empty` 仍是 #7）。"""
    for _name, build, _state in SCENARIOS:
        card, facts = build()
        out = P.v2_card_html(card, facts)
        assert f"bdg bdg-{V2.VALID_EMPTY_BADGE} " not in out, _name
    card, facts = dict((s[0], s[1]) for s in SCENARIOS)["screen.empty"]()
    assert card.note.now == P.SCREEN_EMPTY_NOW
    assert "bdg bdg-7 " in P.v2_card_html(card, facts)
