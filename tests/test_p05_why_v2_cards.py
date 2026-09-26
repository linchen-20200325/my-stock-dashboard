"""「📖 憑什麼」的卡改走 v2 卡面（同「🔬 查一檔」頁、「💼 我的持股」頁 `57b5993`、
「🔍 找標的」頁 `8f3f869`；客戶 2026-09-25 裁示 1~4 ＋ K1）的守衛。

一條測試對應一種說謊方式（同查一檔頁那一份）：
  · 某一張卡**沒登記**在 v2 契約（含兩個動態容器）→ 同頁長出兩種卡面；
  · 某一則可產生的 `Note` **沒有短句** → 渲染當下才炸；短句表有**死列**；
  · 短句**不是原文摘錄**（新造白話 ＝ K1 裁示的 §1 捏造）；
  · 長句被濃縮後**原文不見了**（摺疊區少字 / 只活在 hover）；
  · 「沒有出口」被短句改寫成一個看起來可以按的指路；
  · 兩張卡的摺疊開關 id 撞名 → 點一張開另一張（含動態卡的 fetcher 名）；
  · 卡化順手動到**表格**（本批 ⛔ 不動三個 `st.dataframe` 呼叫點、⛔ 不畫新表）；
  · 灰被畫成紅、紅被畫成灰（冷啟動 ⛔ 不得有紅）；
  · 本頁沒有登記任何「有效的空結果」⇒ #11 ⛔ 不得出現在本頁。

「可產生的 Note」以**窮舉建卡**取得（`_enumerate()`：把每一支 `build_*` 餵過一組
readout 組合，收集實際吐出來的 `(card.key, note.now)`），⛔ 不是手抄一份名單。
燈號規格類的卡一律用**當下的 L0 規格表**實跑 —— L0 改寫原因欄時這裡會紅（據實揭露見
`page_why.V2_SHORT_ROWS` 的註解）。
"""
from __future__ import annotations

import ast
import dataclasses
import html
import inspect
import pathlib
import re
import textwrap

import pytest

from shared.ui_state import (
    UI_DEGRADED,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_MISSING_RETRYABLE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import NO_EXIT_MARKER
from src.ui.views import page_why as P
from src.ui_v2 import blocks, components
from src.ui_v2 import markup as M
from src.ui_v2 import page_today as V2
from src.ui_v2 import page_why as V2W

_VIEW = pathlib.Path(P.__file__)
_E = "RuntimeError('boom')"


def _entry(status: str, **kw) -> dict:
    _e = {"category": "🇹🇼 台灣總經", "frequency": "monthly", "last_status": status,
          "last_error": None, "last_rows": None, "last_ms": None, "last_called_at": None}
    _e.update(kw)
    return _e


def _scan_of(registry: dict) -> P.SourceScan:
    """照 `load_sources()` 真的會組出來的形狀造（含「不是 Mapping」那一列的錯誤句）。"""
    _saved = P.get_monitor_registry
    P.get_monitor_registry = lambda: registry
    try:
        return P.load_sources()
    finally:
        P.get_monitor_registry = _saved


def _enumerate():
    """把每一支 `build_*` 餵過一組 readout 組合 → `{(key, now, why, where): built}` ＋ 全部 built。"""
    notes: dict[tuple[str, str, str, str], tuple] = {}
    builts: list[tuple] = []

    def add(b):
        builts.append(b)
        c = b[0]
        if c.note is not None:
            notes.setdefault((c.key, c.note.now, c.note.why, c.note.where), b)

    # ── 葉1 教學 ───────────────────────────────────────────────────
    specs = P.load_specs()
    scales = P.build_scale_disclosure()
    for b in P.build_edu_cards(specs, scales):
        add(b)
    add(P.build_lights_card(P.SpecScan(error=_E)))
    add(P.build_lights_card(P.SpecScan()))
    add(P.build_scale_card(P.ScaleDisclosure(error=_E)))
    add(P.build_scale_card(P.ScaleDisclosure()))
    add(P.build_scale_card(dataclasses.replace(scales, degraded_notes=())))   # 兩側都可讀 → live
    # ── 葉2 使用者版 ───────────────────────────────────────────────
    scan = _scan_of({
        "fetch_fred": _entry("ok", last_called_at="2026-09-26 09:00", last_rows=12, last_ms=34),
        "twse_volume": _entry("未執行"),
        "fetch_tw_pmi": _entry("failed", last_error=_E),
        "fetch_margin_balance": _entry("failed"),
        "fetch_share_capital": _entry("weird-status"),
        "fetch_chip_concentration": ["不是", "Mapping"],
        "外資現貨": _entry("未執行"),
        "外資期貨": _entry("未執行"),
    })
    for p in scan.probes:
        add(P.build_source_card(p))
    add(P.build_empty_registry_card())
    add(P.build_wall_registry_failed_card(P.SourceScan(error=_E)))   # 燈牆上的「登錄表讀不出來」
    for b in P.build_unmeasured_cards():
        add(b)
    for b in P.build_spec_flag_cards(specs):
        add(b)
    # ── 葉2 工程師版 ───────────────────────────────────────────────
    add(P.build_engineer_card(P.EngineerRequest(opened=False), P.SourceScan()))
    add(P.build_engineer_card(P.EngineerRequest(opened=True), P.SourceScan(error=_E)))
    add(P.build_engineer_card(P.EngineerRequest(opened=True), scan))
    for b in P.build_engineer_panel_cards():
        add(b)
    # ── 葉3 AI 問答 ────────────────────────────────────────────────
    for qa in (P.QaReadout(asked=False),
               P.QaReadout(asked=True, key_missing=True, error=P.NO_KEY_ERROR),
               P.QaReadout(asked=True, error=_E),
               P.QaReadout(asked=True, error=P.UNKNOWN_ERROR_TEXT, model="m"),
               P.QaReadout(asked=True),
               P.QaReadout(asked=True, answered=True, text="答", model="gemini",
                           tool_calls=("get_health", "get_macro"))):
        add(P.build_qa_card(qa))
    return notes, builts


_NOTES, _BUILTS = _enumerate()
#: 每一則可產生的 Note 一個代表 ＋ 每張卡每一態一個代表。
_CASES = list(_NOTES.values()) + list(
    {(b[0].key, b[0].state): b for b in _BUILTS}.values())
_IDS = [f"{b[0].key}:{b[0].state}:{i}" for i, b in enumerate(_CASES)]

_ROW_RE = r'<span class="blk-fact-k">(.*?)</span><span class="blk-fact-v"[^>]*>(.*?)</span>'


def _split(outer: str) -> tuple[str, str]:
    i = outer.find('<div class="blk-fold">')
    return (outer, "") if i < 0 else (outer[:i], outer[i:])


def _rows(fragment: str) -> list[tuple[str, str]]:
    return [(html.unescape(k), html.unescape(v)) for k, v in re.findall(_ROW_RE, fragment, re.S)]


def _face_rows(outer: str) -> list[tuple[str, str]]:
    return _rows(_split(outer)[0])


def _fold_rows(outer: str) -> list[tuple[str, str]]:
    return _rows(_split(outer)[1])


def _fold_id(outer: str) -> str | None:
    # 2026-09-26 a11y：input 另帶 `aria-labelledby` / `aria-controls` ⇒ id 之後允許其他屬性。
    m = re.search(r'<input type="checkbox" class="blk-fold-i" id="([^"]+)"[^>]*>', outer)
    return m.group(1) if m else None


def _html(built) -> str:
    card, facts, signal = built
    return P.v2_card_html(card, facts, signal)


def _badge_of(out: str) -> int:
    m = re.search(r'class="bdg bdg-(\d+) ', out)
    assert m, "卡面上找不到主徽章"
    return int(m.group(1))


# ── 1. 登記：固定卡 ＋ 兩個動態容器，層→密度照規格 ─────────────────────
#: UI_PAGE_WHY.md ② 表：n1 → t1、n3 → t3、n4 → t4、n5 → t2（沿用找標的頁）。**手寫**（第二把尺）。
_EXPECTED_TIER = {
    "why.edu.lights": "t1", "why.edu.health6": "t1", "why.edu.scales": "t1",
    "why.edu.legacy": "t1",                                                          # n1
    "why.source.wall": "t3", "why.source.none": "t3",
    "why.source.unmeasured.finmind_quota": "t3", "why.spec.flags": "t3",             # n3
    "why.engineer.gate": "t4", "why.engineer.registry": "t4",
    "why.engineer.reconcile": "t4", "why.engineer.api_root": "t4",
    "why.engineer.raw": "t4", "why.engineer.calibration": "t4",                      # n4
    "why.qa": "t2",                                                                  # n5
}


def test_every_card_the_page_builds_is_registered_and_nothing_else():
    built_blocks = {V2W.block_for_card(b[0].key) for b in _BUILTS}
    assert built_blocks == set(V2W.BLOCK_COLS) == set(_EXPECTED_TIER), sorted(built_blocks)
    dyn = {b[0].key for b in _BUILTS if V2W.block_for_card(b[0].key) != b[0].key}
    assert {k.split(".")[1] for k in dyn} == {"source", "spec"}, dyn
    assert len(dyn) >= 8 + 3, "動態卡（每支 fetcher、每盞被標記的燈）窮舉太少"


def test_dynamic_prefixes_do_not_swallow_fixed_cards_and_unknown_keys_raise():
    assert V2W.block_for_card("why.source.none") == "why.source.none"
    assert V2W.block_for_card("why.source.unmeasured.finmind_quota") == \
        "why.source.unmeasured.finmind_quota"
    assert V2W.block_for_card("why.source.fetch_fred") == "why.source.wall"
    assert V2W.block_for_card("why.spec.margin") == "why.spec.flags"
    for bad in ("why.source.", "why.spec.", "why.other", "inspect.kind", "why.v2_css.render_failed"):
        with pytest.raises(KeyError):
            V2W.block_for_card(bad)


def test_tiers_come_from_the_spec_layers():
    for key, tier in _EXPECTED_TIER.items():
        assert blocks.tier_for_block(key) == tier
        assert V2W.tier_for_block(key) == tier
        assert blocks.BLOCK_PAGE[key] == "why"
    for layer in V2W.LAYERS:
        assert layer["tier"] == components.tier_for_layer(layer["layer"])
    assert blocks.PAGES["why"] is V2W
    assert V2W.N5_DENSITY_LAYER == 2
    from src.ui_v2 import page_find
    assert V2W.N5_DENSITY_LAYER == page_find.N5_DENSITY_LAYER, "n5 沿用找標的頁的新訂"


def test_spec_block_mapping_and_cols_follow_the_spec_table():
    m = V2W.SPEC_BLOCK
    assert {k for k, v in m.items() if v == "why.engineer.panels"} == {
        "why.engineer.registry", "why.engineer.reconcile", "why.engineer.api_root",
        "why.engineer.raw", "why.engineer.calibration"}
    assert m["why.source.none"] == "why.source.wall"
    for k, cols in V2W.BLOCK_COLS.items():
        want = (1, 1, 1) if k in ("why.engineer.gate", "why.qa") else (3, 2, 1)
        assert cols == want, k


def test_no_override_and_badge_10_not_drawn():
    assert list(inspect.signature(V2W.tier_for_block).parameters) == ["block_key"]
    assert V2W.BADGES_NOT_ON_PAGE == frozenset({10})
    for key in V2W.BLOCK_COLS:
        with pytest.raises(ValueError):
            M.card_html(block=key, state="live", title="t", badge_n=10)


def test_page_css_did_not_grow():
    assert M._BLOCK_COLS_USED == tuple(sorted(set(V2.BLOCK_COLS.values())))


def test_no_block_key_collides_with_another_page():
    for page, mod in blocks.PAGES.items():
        if page == "why":
            continue
        for layer in mod.LAYERS:
            assert not (set(layer["blocks"]) & set(V2W.BLOCK_COLS)), page


# ── 2. 短句表：可產生的每一則 Note 都有、而且沒有死列 ──────────────────
def test_short_rows_cover_every_producible_note_and_have_no_dead_rows():
    used = {P.v2_short_rows_key(b[0]) for b in _NOTES.values()}
    registered = set(P.V2_SHORT_ROWS)
    assert registered - used == set(), f"短句表有死列：{registered - used}"
    for b in _NOTES.values():   # 每一則都查得到（`v2_short_rows_key` 查不到會 raise）
        P.v2_short_rows(b[0])
    assert len(used) == len(registered) >= 25, f"窮舉太少，建卡掃描壞了？{len(used)}"


def test_every_note_now_in_the_module_is_a_registered_constant():
    """靜態對帳：本檔**每一個** `Note(now=…)` / `L0CardSpec(now=…)` 都是常數／
    `*_NOW_TEMPLATE.format(…)`／`SOURCE_UNKNOWN_NOW_HEAD` 起頭的 f-string，
    且每一個被用到的 `*_NOW` 常數至少登記在一列短句表 —— 擋「日後新增一則 Note 而沒補表」。"""
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    names: set[str] = set()
    templates: set[str] = set()

    def collect(v):
        if isinstance(v, ast.IfExp):
            collect(v.body)
            collect(v.orelse)
        elif isinstance(v, ast.Name):
            names.add(v.id)
        elif isinstance(v, ast.Attribute) and ast.unparse(v) == "spec.now":
            pass   # `build_l0_card()` 轉交 `L0CardSpec.now`（下面另驗 `L0CardSpec(now=…)`）
        elif (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
              and v.func.attr == "format" and isinstance(v.func.value, ast.Name)
              and v.func.value.id.endswith("_NOW_TEMPLATE")):
            templates.add(v.func.value.id)
        elif isinstance(v, ast.JoinedStr):
            src = ast.unparse(v)
            # 只准兩種：v2 渲染失敗的補救紅卡（走舊卡面，不查表）／登記過的固定開頭。
            assert "這一格畫不出來" in src or src.startswith(
                "f'{SOURCE_UNKNOWN_NOW_HEAD}"), src
        else:
            pytest.fail(f"now 不是常數：{ast.unparse(v)}")

    for call in ast.walk(tree):
        if isinstance(call, ast.Call) and getattr(call.func, "id", None) in ("Note", "L0CardSpec"):
            for kw in call.keywords:
                if kw.arg == "now":
                    collect(kw.value)
    local = {n for n in names if n.startswith("_")}
    assert local == {"_now"}, local        # `build_spec_flag_card` 的區域變數（兩個常數二選一）
    names -= local
    names |= {"SPEC_FLAG_UNWIRED_NOW", "SPEC_FLAG_DEGRADED_NOW"}
    assert len(names) >= 20 and templates == {"L0_FAILED_NOW_TEMPLATE"}, (sorted(names), templates)
    registered = {now for (_k, now) in P.V2_SHORT_ROWS}
    for n in sorted(names):
        assert getattr(P, n) in registered, f"{n} 沒有登記短句"
    fn = ast.parse(textwrap.dedent(inspect.getsource(P.build_spec_flag_card)))
    assert "SPEC_FLAG_UNWIRED_NOW if not row.wired" in ast.unparse(fn)


# ── 3. K1：短句一律是原文摘錄 ─────────────────────────────────────────
@pytest.mark.parametrize("key", sorted(_NOTES),
                         ids=[f"{k[0]}|{k[1][:10]}|{i}" for i, k in enumerate(sorted(_NOTES))])
def test_every_short_cell_is_an_excerpt_of_its_own_note(key):
    card = _NOTES[key][0]
    short, full = P.v2_short_rows(card)
    for (lab_s, s), (lab_f, f) in zip(short, full):
        assert lab_s == lab_f
        pos = 0
        for piece in s.split(P.V2_EXCERPT_GAP):
            assert piece, f"{card.key}: 空的摘錄段"
            at = f.find(piece, pos)
            assert at >= 0, f"{card.key}「{lab_s}」：{piece!r} 不在原文裡（新造白話 ＝ K1 禁止）"
            pos = at + len(piece)
        assert len(s) <= M.FACT_VALUE_MAX_CHARS, f"{card.key}: 短句會被契約層截斷：{s}"
        assert "**" not in s and "`" not in s


def _idle_qa():
    return P.build_qa_card(P.QaReadout(asked=False))


def _capture(monkeypatch) -> list[str]:
    md: list[str] = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s, **_k: md.append(str(s))
    ns.caption = lambda s, **_k: md.append(str(s))
    monkeypatch.setattr(P, "st", ns)
    from src.ui.views import _ui_kit as K
    monkeypatch.setattr(K, "st", ns)
    return md


def test_a_non_excerpt_short_row_raises_and_renders_red(monkeypatch):
    built = _idle_qa()
    card = built[0]
    monkeypatch.setitem(P.V2_SHORT_ROWS, (card.key, card.note.now),
                        ("尚未提問", "這是一句新寫的白話", "按一下"))
    with pytest.raises(KeyError, match="K1"):
        P.v2_card_html(*built)
    md = _capture(monkeypatch)
    P._render_one(built)
    out = "\n".join(md)
    assert "這一格畫不出來" in out, "摘錄對不上原文 → 必須是看得見的紅卡"
    assert '<div class="blk blk-' not in out, "新造白話不得以 v2 卡面的短句畫出來"


def test_an_l0_reason_the_table_does_not_know_turns_red_not_invented(monkeypatch):
    """L0 改寫原因欄 → 短句對不上 → **紅卡**（⛔ 不靜默退回長句、⛔ 不新寫一句）。"""
    row = P.load_specs().degraded[0]
    built = P.build_spec_flag_card(dataclasses.replace(row, degraded_reason="一段 L0 新寫的原因"))
    with pytest.raises(KeyError, match="K1"):
        P.v2_card_html(*built)
    md = _capture(monkeypatch)
    P._render_one(built)
    assert "這一格畫不出來" in "\n".join(md)


def test_an_unregistered_note_raises():
    built = _idle_qa()
    saved = P.V2_SHORT_ROWS.pop((built[0].key, built[0].note.now))
    try:
        with pytest.raises(KeyError, match="V2_SHORT_ROWS"):
            P.v2_card_html(*built)
    finally:
        P.V2_SHORT_ROWS[(built[0].key, built[0].note.now)] = saved


def test_no_exit_stays_no_exit_and_keeps_its_next_step():
    seen = 0
    for card, _f, _s in _NOTES.values():
        where_s = P.v2_short_rows(card)[0][2][1]
        assert (NO_EXIT_MARKER in where_s) == (NO_EXIT_MARKER in card.note.where), card.key
        if NO_EXIT_MARKER in where_s:
            assert where_s != NO_EXIT_MARKER, f"{card.key}: 只剩標記，原文的下一步被吞掉了"
            seen += 1
    assert seen >= 10, "未接線五面板／額度／六因子／規格標記／契約漂移都該有「沒有出口」"


def test_unknown_status_head_matches_only_its_own_shape():
    probe = P.probe_from_entry("fetch_x", _entry("完全沒見過"))
    card = P.build_source_card(probe)[0]
    assert P.v2_short_rows_key(card) == ("why.source.wall", P.SOURCE_UNKNOWN_NOW_HEAD)
    assert P.v2_short_rows(card)[0][0][1] == P.v2_plain(P.SOURCE_UNKNOWN_NOW_HEAD)
    fake = dataclasses.replace(card, note=P.Note(now=P.SOURCE_UNKNOWN_NOW_HEAD + "別的尾巴",
                                                 why="w", where="x"))
    with pytest.raises(KeyError):
        P.v2_short_rows_key(fake)


# ── 4. 每張卡、每一態都走 v2 卡面；原文一字不少 ──────────────────────
@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_every_state_renders_through_the_v2_face(built):
    card, facts, signal = built
    out = _html(built)
    assert f'class="blk blk-{_EXPECTED_TIER[V2W.block_for_card(card.key)]}"' in out
    v2_state, reason = P.V2_STATE_VOCAB[card.state]
    assert _badge_of(out) == V2.resolve_badge(state=v2_state, miss_reason=reason)
    assert html.escape(P.v2_plain(card.label), quote=True) in out
    if card.state == UI_LIVE:
        assert html.escape(P.v2_plain(card.value), quote=True) in out
    else:
        assert '<div class="blk-val">' not in out
    assert signal == "" and '<div class="blk-lvl">' not in out, "本頁沒有訊號頻道"
    assert out.count("<div") == out.count("</div>")


def test_the_badges_mean_what_the_old_card_meant():
    """灰／紅／橘不得互換：live → #1、idle → #3、degraded → #4、unwired → #5、failed → #6、
    缺漏（再試一次有用）→ #7。"""
    want = {UI_LIVE: 1, UI_IDLE: 3, UI_DEGRADED: 4, UI_UNWIRED: 5, UI_FAILED: 6,
            UI_MISSING_RETRYABLE: 7}
    seen: set[str] = set()
    for b in _BUILTS:
        assert b[0].state in want, (b[0].key, b[0].state)
        assert _badge_of(_html(b)) == want[b[0].state], (b[0].key, b[0].state)
        seen.add(b[0].state)
    assert seen == set(want), f"窮舉沒打到：{set(want) - seen}"
    # 看不懂的狀態 ／ 不是 Mapping 的列 → 紅（⛔ 不當綠、⛔ 不當灰）
    odd = [b for b in _BUILTS if b[0].key in ("why.source.fetch_share_capital",
                                                 "why.source.fetch_chip_concentration")]
    assert len(odd) == 2 and all(_badge_of(_html(b)) == 6 for b in odd)


def test_badge_11_never_appears_on_this_page():
    from src.ui.views import page_today as PT

    assert not {p for p in PT.v2_valid_empty_pairs() if p[0].startswith("why.")}
    checked = 0
    for b in _BUILTS:
        card = b[0]
        if card.state == UI_LIVE:
            continue
        v2_state, reason = P.V2_STATE_VOCAB[card.state]
        assert _badge_of(_html(b)) == V2.resolve_badge(state=v2_state, miss_reason=reason) \
            != V2.VALID_EMPTY_BADGE, (card.key, card.note.now)
        checked += 1
    assert checked > 20


@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_existing_facts_all_stay_on_the_face_after_the_short_rows(built):
    card, facts, _s = built
    out = _html(built)
    rows = _face_rows(out)
    tail = rows[3:] if card.note is not None else rows
    assert len(tail) == len(facts)
    fold = _fold_rows(out)
    for (fk, fv), (k, v) in zip(tail, facts):
        k, v = P.v2_plain(k), P.v2_plain(v)
        assert fk == k, "卡面標籤必須是整句原文"
        shown = (fv[:-1] if fv.endswith(M.FACT_VALUE_ELLIPSIS)
                 and len(fv) > M.FACT_VALUE_MAX_CHARS else fv)
        pos = 0
        for piece in shown.split(P.V2_EXCERPT_GAP):
            if piece:
                at = v.find(piece, pos)
                assert at >= 0, f"{card.key}: 卡面值不是原值摘錄：{fv!r}"
                pos = at + len(piece)
        if (fk, fv) != (k, v):
            assert (k, v) in fold, f"{card.key}: 卡面被摘過的列，原文沒進摺疊區：{k}"


#: 三列短句裡**准許**出現的長識別字（逐一列名，⛔ 不是放寬規則）：QA F4 要求 AI 問答「未啟用」的
#: 「去哪補」必須留住金鑰的來處 —— 環境變數名本身就是那個來處，略成「…」就等於沒說。
#: `src/services/`（13 字，只超出上限 1 字）：QA nit 要求雙演算法對帳的「為什麼」留住
#: 「沒有任何一支把它包起來」的**主詞** —— 那個目錄名本身就是主詞，略成「…」句子就沒有主詞。
_SHORT_ROW_ASCII_ALLOWED: frozenset[str] = frozenset({"GEMINI_API_KEY", "src/services/"})


def test_face_has_no_long_unbroken_ascii_run():
    """卡面上不得有「長、含字母或底線、**且不含數字**」的 ASCII 連續段（含數字的永遠不略，見 F3）。"""
    for built in _CASES:
        rows = _face_rows(_html(built))
        n_short = 3 if built[0].note is not None else 0
        for i, (_k, v) in enumerate(rows):
            for run in re.findall(r"[\x21-\x7e]{%d,}" % (P.V2_FACE_TOKEN_MAX + 1), v):
                if i < n_short and run in _SHORT_ROW_ASCII_ALLOWED:
                    continue
                assert not (re.search(r"[A-Za-z_]", run) and not re.search(r"\d", run)), (
                    built[0].key, v)


def test_numbers_are_never_elided_on_the_face():
    assert P._v2_face_value("已載入 · 登錄表有 12345678901234 支") == "已載入 · 登錄表有 12345678901234 支"
    assert P._v2_face_value("x shared.fetch_monitor.get_monitor_registry y") == "x … y"


#: QA F3（同查一檔頁 F5）：黏著字母的數字 ⇒ 整段含數字 ⇒ ⛔ 不得被吃成「…」。
_MARGIN_SSOT = "SSOT:MARGIN_BALANCE_OVERHEAT(3400)+MARGIN_BALANCE_WARN(2500)"


@pytest.mark.parametrize("glued", [_MARGIN_SSOT, "NT$12,345,678", "TWD1,234,567.8",
                                   "2330.TW:600.00", "fetch_2330_daily_close"])
def test_a_token_with_a_digit_is_never_elided(glued):
    assert P._v2_face_value(glued) == glued
    assert P._v2_face_value(f"值 {glued} 元") == f"值 {glued} 元"
    # 同一格裡不含數字的識別字照舊略（⛔ 修法不是把略的規則整條拔掉）。
    assert P._v2_face_value(f"{glued} shared.fetch_monitor") == f"{glued} …"


def test_the_live_margin_threshold_source_keeps_its_numbers_on_the_face():
    """實跑當下的 L0：`why.spec.margin` 的「值從哪來」上卡面時 3400 與 2500 都還在。"""
    built = [b for b in _BUILTS if b[0].key == "why.spec.margin"]
    assert built, "L0 目前沒有標記融資那一盞 —— 這一條沒有東西可驗"
    raw = dict((P.v2_plain(k), P.v2_plain(v)) for k, v in built[0][1])
    assert raw.get("值從哪來") == _MARGIN_SSOT, raw.get("值從哪來")
    out = _html(built[0])
    face_v = [v for k, v in _face_rows(out) if k == "值從哪來"][0]
    # 本頁 ⛔ 不再把它吃成「…」；超過 `FACT_VALUE_MAX_CHARS` 的部分由**契約層**截顯示
    # （`markup._fact_value_cell`：截斷處補「…」、完整值掛 `title=`），完整值另進摺疊區。
    assert face_v != P.V2_EXCERPT_GAP and "3400" in face_v, face_v
    assert _MARGIN_SSOT.startswith(face_v.rstrip(M.FACT_VALUE_ELLIPSIS)), face_v
    assert ("值從哪來", _MARGIN_SSOT) in _fold_rows(out), "超過卡面寬度的完整值要在摺疊區"


@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_full_note_text_is_in_the_fold(built):
    card, _f, _s = built
    fold = _fold_rows(_html(built))
    if card.note is not None:
        assert fold[:3] == [(P.V2_NOW_FACT_KEY, P.v2_plain(card.note.now)),
                            (P.V2_WHY_FACT_KEY, P.v2_plain(card.note.why)),
                            (P.V2_GUIDE_FACT_KEY, P.v2_plain(card.note.where))]


@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_nothing_lives_only_in_a_title_attribute(built):
    out = _html(built)
    fold_text = "\n".join(v for _k, v in _fold_rows(out))
    for t in re.findall(r' title="([^"]*)"', out):
        pos = 0
        for piece in html.unescape(t).split(P.V2_EXCERPT_GAP):
            if not piece:
                continue
            at = fold_text.find(piece, pos)
            assert at >= 0, f"只活在 hover 的字：{piece[:40]}"
            pos = at + len(piece)


def test_red_cards_keep_the_exception_text_in_the_fold_only():
    seen = 0
    for card, facts, sig in _NOTES.values():
        if card.state != UI_FAILED or _E not in card.note.why:
            continue
        out = P.v2_card_html(card, facts, sig)
        assert _E in dict(_fold_rows(out))[P.V2_WHY_FACT_KEY]
        assert _E not in "".join(v for _k, v in _face_rows(out))
        seen += 1
    assert seen >= 5


# ── 5. 摺疊開關 id ／ 本頁樣式 ────────────────────────────────────────
def test_fold_ids_are_stable_per_card_and_scoped_to_this_page():
    """每張卡的 id 由 key 決定（跨態不變）、不同 key 的 id 不同。
    ⚠️ 這一條**看不到**「同一輪畫了兩張同 key 的卡」（QA F1）—— 那由下面的**單輪**守衛驗。"""
    ids: dict[str, set[str]] = {}
    for built in _CASES:
        fid = _fold_id(_html(built))
        if fid is None:
            continue
        assert re.fullmatch(r"fold-why-[a-z0-9-]+", fid), fid
        ids.setdefault(built[0].key, set()).add(fid)
    assert all(len(v) == 1 for v in ids.values()), "同一張卡不同態 id 不同 → rerun 展開狀態會掉"
    flat = [next(iter(v)) for v in ids.values()]
    assert len(flat) == len(set(flat)), "本頁卡之間 id 撞名"
    # 兩支中文名 fetcher：若直接洗會同洗成 `fold-why-source`，必須各自唯一
    zh = [next(iter(ids[k])) for k in ("why.source.外資現貨", "why.source.外資期貨")]
    assert len(set(zh)) == 2 and "fold-why-source" not in zh, zh


def test_why_card_css_is_scoped_stacked_and_invents_no_numbers():
    css = P.V2_WHY_CARD_CSS
    cls = P.V2_WHY_CARD_CLASS
    assert css.count(f".{cls} ") == 3 and ":has(" not in css
    assert not re.search(r"\d", css.replace(cls, "")), "不得寫死任何數字"
    assert cls not in M.page_css("dark") and cls not in M.page_css("light")
    from src.ui.views import page_hold as H
    from src.ui.views import page_inspect as I
    assert cls not in (H.V2_HOLD_CARD_CLASS, I.V2_INSPECT_CARD_CLASS)
    assert css == H.V2_HOLD_CARD_CSS.replace(H.V2_HOLD_CARD_CLASS, cls), (
        "與我的持股頁同三條規則、只換外層 class")


def test_blank_lines_in_l0_text_do_not_reach_st_markdown(monkeypatch):
    """L0 原因欄自帶段落空行 → 送去 `st.markdown` 的 HTML 不得有空白行（否則 HTML 區塊中途結束）；
    摺疊區的原文（`v2_card_html` 輸出）一個字都不動。"""
    flagged = [b for b in _BUILTS if b[0].key.startswith("why.spec.")
               and "\n\n" in b[0].note.why]
    assert flagged, "L0 目前沒有帶空行的原因欄 —— 這一條沒有東西可驗"
    sent = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    for b in flagged:
        assert re.search(r"\n[ \t]*\n", _html(b))
        P._render_one(b)
    assert sent and not any(re.search(r"\n[ \t]*\n", s_) for s_ in sent)
    for s_, b in zip(sent, flagged):
        assert re.sub(r"\s+", " ", s_) == re.sub(
            r"\s+", " ", f'<div class="{P.V2_WHY_CARD_CLASS}">{_html(b)}</div>')


def test_render_wraps_each_card_in_the_why_scope(monkeypatch):
    sent = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    built = _idle_qa()
    P._render_one(built)
    assert sent == [f'<div class="{P.V2_WHY_CARD_CLASS}">{P.v2_card_html(*built)}</div>']


# ── 6. 渲染接線（含突變檢查：拔掉 v2 路徑 → 本組守衛必須轉紅）──────────────
def _assert_every_card_routes_to_v2(monkeypatch):
    seen = []
    monkeypatch.setattr(P, "_render_one_v2", lambda c, f=(), s="": seen.append(c.key))
    monkeypatch.setattr(P, "render_card_isolated",
                        lambda *a, **k: pytest.fail("登記的卡不該走舊卡面"))
    for built in _CASES:
        P._render_one(built)
    assert {V2W.block_for_card(k) for k in seen} == set(V2W.BLOCK_COLS) == set(_EXPECTED_TIER)
    assert set(seen) == {b[0].key for b in _CASES}


def test_render_routes_every_card_to_the_v2_face(monkeypatch):
    _assert_every_card_routes_to_v2(monkeypatch)


def test_removing_the_card_path_turns_the_routing_guard_red(monkeypatch):
    """突變：把 v2 契約的登記與前綴清空（＝ 拔掉卡化路徑），上一條守衛必須失敗。"""
    monkeypatch.setattr(V2W, "_BLOCK_LAYER", {})
    monkeypatch.setattr(V2W, "DYNAMIC_PREFIXES", ())
    with pytest.raises((AssertionError, pytest.fail.Exception, KeyError)):
        _assert_every_card_routes_to_v2(monkeypatch)


def test_a_v2_render_failure_becomes_a_red_card(monkeypatch):
    md = _capture(monkeypatch)
    monkeypatch.setattr(P, "v2_card_html", lambda *_a, **_k: (_ for _ in ()).throw(
        RuntimeError("render exploded")))
    P._render_one(_idle_qa())
    out = "\n".join(md)
    assert "這一格畫不出來" in out and "render exploded" in out


def test_css_is_emitted_once_per_run(monkeypatch):
    sent = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    P._inject_v2_css()
    assert len(sent) == 1
    assert P.V2_WHY_CARD_CSS in sent[0] and M.page_css(P.V2_CSS_MODE) in sent[0]
    fn = ast.parse(textwrap.dedent(inspect.getsource(P.render_page_why)))
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)
             and getattr(c.func, "id", None) == "_inject_v2_css"]
    assert len(calls) == 1, "每輪恰吐一次樣式表"


def test_css_failure_becomes_a_red_card(monkeypatch):
    md = _capture(monkeypatch)
    monkeypatch.setattr(P.v2_markup, "page_css", lambda _m: (_ for _ in ()).throw(
        RuntimeError("css exploded")))
    P._inject_v2_css()
    out = "\n".join(md)
    assert "這一格畫不出來" in out and "css exploded" in out


# ── 7. 表格與版面：⛔ 不動 ────────────────────────────────────────────
def test_the_tables_are_untouched_and_no_new_table_is_drawn():
    """三個 `st.dataframe` 呼叫點（規格 ②「3 個呼叫點」），卡化沒有加表、沒有改表。"""
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    frames = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
              and isinstance(c.func, ast.Attribute) and c.func.attr in ("dataframe", "table")]
    assert len(frames) == 3 and all(f.func.attr == "dataframe" for f in frames)
    for built in _CASES:
        assert not any(t in _html(built) for t in ("<table", "<tr", "<td"))


def test_cold_page_mounts_with_v2_cards_no_red_and_three_tables(tmp_path):
    """整頁冷啟動：葉1 四張、葉2 燈牆＋量不到＋L0 標記＋工程師 idle、葉3 idle 全走 v2 卡面；
    ⛔ 沒有任何紅卡（冷啟動只准灰／橘／綠）；三張表照舊；樣式表恰一次。"""
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_p05_v2.py"
    script.write_text(textwrap.dedent("""
        from src.ui.views.page_why import render_page_why
        render_page_why()
    """), encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    md = [m.value for m in at.markdown]
    cards = [m for m in md
             if m.startswith(f'<div class="{P.V2_WHY_CARD_CLASS}"><div class="blk blk-')]
    n_flags = len(P.build_spec_flag_cards(P.load_specs()))
    assert len(cards) >= 4 + 1 + 1 + n_flags + 1 + 1, f"v2 卡面 {len(cards)} 張"
    # ⚠️ 燈牆上每支 fetcher 的那一格**不在**此斷言內：登錄表的內容取決於這個 process 裡
    #    別的測試有沒有真的呼叫過那些 fetcher（沙箱沒網路 → 真的 `failed` → 紅卡是**對的**）；
    #    同 `test_p05_why_view.py::test_page_mounts_clean` 刻意不斷言燈牆的理由。
    def _is_wall(c: str) -> bool:
        m = re.search(r'id="fold-why-source-([a-z0-9-]+)"', c)
        return bool(m) and not m.group(1).startswith(("none", "unmeasured"))
    assert not any(_badge_of(c) == 6 for c in cards if not _is_wall(c)), (
        "冷啟動不得有紅卡（假性錯誤）")
    edu = [c for c in cards if 'class="blk blk-t1"' in c]
    assert [_badge_of(c) for c in edu] == [1, 5, 4, 5], "葉1 四張的狀態（live/unwired/degraded/unwired）"
    assert sum(P.V2_WHY_CARD_CSS in m for m in md) == 1, "樣式表應恰吐一次"
    assert len(at.dataframe) == 3
    assert not any(t in "\n".join(md) for t in ("<table", "<tr", "<td")), "卡化不得畫新表格"
    ids = [m.group(1) for c in cards for m in [re.search(r'id="(fold-why-[a-z0-9-]+)"', c)] if m]
    assert len(ids) == len(set(ids))
    assert not [c for c in md if '<div class="blk ' in c and P.V2_WHY_CARD_CLASS not in c]


def test_the_lifted_constants_are_used_verbatim():
    """上提常數後文字一字未改（抽樣對照原本寫在函式體內的字面）。"""
    assert P.SOURCE_IDLE_NOW == "**未檢查**"
    assert P.L0_FAILED_NOW_TEMPLATE.format(label="X") == "**X讀不出來**"
    probe = P.probe_from_entry("f", _entry("zz"))
    assert P.build_source_card(probe)[0].note.now == "**這一盞的狀態本頁看不懂**（L0 回 'zz'）"
    assert P.build_engineer_card(P.EngineerRequest(opened=False), P.SourceScan())[0].note.now \
        == "**進階診斷未載入**"
    assert P.build_qa_card(P.QaReadout(asked=True))[0].note.now == "**這一輪沒有回答內容**"


# ── 8. QA F1／F2：摺疊開關 id 在**同一輪**裡唯一；燈牆上的「登錄表讀不出來」是 t3 ────────
_SCRIPT = """
from src.ui.views import page_why as P


def _boom():
    raise RuntimeError("registry exploded")


_saved = P.get_monitor_registry
if {raises!r}:
    P.get_monitor_registry = _boom
try:
    P.render_page_why()
finally:
    P.get_monitor_registry = _saved
"""


def _run_page(tmp_path, *, registry_raises: bool, engineer: bool) -> list[str]:
    """整頁實跑一輪 → 本頁 v2 卡的 HTML（依畫出來的順序；⛔ 不去重 —— 重複正是要抓的東西）。"""
    from streamlit.testing.v1 import AppTest

    script = tmp_path / f"_p05_run_{int(registry_raises)}{int(engineer)}.py"
    script.write_text(_SCRIPT.format(raises=registry_raises), encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.session_state[P.SS_ENGINEER_GATE] = engineer
    at.run()
    assert not at.exception, at.exception
    return [m.value for m in at.markdown
            if m.value.startswith(f'<div class="{P.V2_WHY_CARD_CLASS}"><div class="blk blk-')]


def _fold_ids_of_run(cards: list[str]) -> list[str]:
    return [m.group(1) for c in cards
            for m in [re.search(r'id="(fold-why-[a-z0-9-]+)"', c)] if m]


@pytest.mark.parametrize("registry_raises,engineer",
                         [(False, False), (False, True), (True, False), (True, True)])
def test_fold_ids_are_unique_within_a_single_run(tmp_path, registry_raises, engineer):
    """同一輪畫出來的每一張 v2 卡，摺疊 id 兩兩不同（否則點一張會開另一張 / 打不開）。"""
    ids = _fold_ids_of_run(_run_page(tmp_path, registry_raises=registry_raises,
                                     engineer=engineer))
    assert ids, "這一輪一張有摺疊的卡都沒有 —— 掃描壞了？"
    dup = sorted({i for i in ids if ids.count(i) > 1})
    assert not dup, f"同一輪裡摺疊 id 撞名：{dup}"


def test_registry_failure_with_engineer_ticked_draws_two_distinct_red_cards(tmp_path):
    """QA F1／F2：登錄表讀爆 ＋ 勾了工程師版 → 燈牆一張、工程師版一張，兩張都紅（#6），
    內容相同，但 id 不同；燈牆那張掛在燈牆那一層（n3 → t3），工程師版那張在 n4 → t4。"""
    cards = _run_page(tmp_path, registry_raises=True, engineer=True)
    wall_id = P.v2_markup.fold_dom_id(P.WALL_REGISTRY_FAILED_KEY)
    gate_id = P.v2_markup.fold_dom_id("why.engineer.gate")
    wall = [c for c in cards if f'id="{wall_id}"' in c]
    gate = [c for c in cards if f'id="{gate_id}"' in c]
    assert len(wall) == 1 and len(gate) == 1, (len(wall), len(gate))
    assert 'class="blk blk-t3"' in wall[0], "燈牆上的紅卡應是 t3（規格 ② 燈牆 n3）"
    assert 'class="blk blk-t4"' in gate[0]
    assert _badge_of(wall[0]) == _badge_of(gate[0]) == 6
    assert _face_rows(_split(wall[0])[0]) == _face_rows(_split(gate[0])[0]), "兩張的卡面應一字不差"
    assert "registry exploded" in "".join(v for _k, v in _fold_rows(wall[0]))
    assert wall_id != gate_id and wall_id.startswith("fold-why-source-")


def test_the_wall_failure_card_is_the_engineer_failure_card_with_another_key():
    scan = P.SourceScan(error=_E)
    wall = P.build_wall_registry_failed_card(scan)
    gate = P.build_engineer_card(P.EngineerRequest(opened=True), scan)
    assert wall[0].key == P.WALL_REGISTRY_FAILED_KEY != gate[0].key
    assert dataclasses.replace(wall[0], key=gate[0].key) == gate[0] and wall[1:] == gate[1:]
    assert V2W.block_for_card(wall[0].key) == "why.source.wall"
    assert V2W.tier_for_block(V2W.block_for_card(wall[0].key)) == "t3"
    # fetcher 名是 Python 識別字（不含 `.`）⇒ 不可能與任何一支 `why.source.<fetcher>` 同 key。
    assert not P.WALL_REGISTRY_FAILED_KEY[len("why.source."):].isidentifier()


# ── 9. QA F5：`*_NOW` 常數的字面釘死（手寫，抄自 origin/main `2a56483` 的函式體內字面）─────
#: ⛔ 不得改成 `getattr(P, name)` 自己對自己 —— 這一張表就是「第二把尺」。
_BASELINE_NOW_LITERALS: dict[str, str] = {
    # `build_l0_card` 的 f-string `f"**{spec.label}讀不出來**"`（`{label}` 由呼叫端帶）。
    "L0_FAILED_NOW_TEMPLATE": "**{label}讀不出來**",
    "SOURCE_IDLE_NOW": "**未檢查**",
    # `build_source_card` 的 f-string `f"**這一盞的狀態本頁看不懂**（L0 回 {…!r}）"` 的固定開頭。
    "SOURCE_UNKNOWN_NOW_HEAD": "**這一盞的狀態本頁看不懂**",
    "SOURCE_FAILED_NOW": "**最後一次真實抓取失敗了**",
    "EMPTY_REGISTRY_NOW": "**這個 session 還沒有任何 fetcher 登錄**",
    "FINMIND_QUOTA_NOW": "**額度這件事本頁看不到**",
    "SPEC_FLAG_UNWIRED_NOW": "**這一盞刻意沒有接**",
    "SPEC_FLAG_DEGRADED_NOW": "**這一盞會亮，但別照門檻讀**",
    "LIGHTS_EMPTY_NOW": "**門檻表讀不出來**",
    "HEALTH6_NOW": "**六個因子各佔幾分，本頁還說不出來**",
    "SCALES_DEGRADED_NOW": "**兩套刻度目前有一側已失準，本頁不提供跨頁比較**",
    "SCALES_EMPTY_NOW": "**兩套刻度的定義讀不出來**",
    "LEGACY_NOW": "**既有的完整教學內容還沒有搬到這一頁**",
    "ENGINEER_IDLE_NOW": "**進階診斷未載入**",
    "ENGINEER_FAILED_NOW": "**進階診斷本身讀不出來**",
    "ENGINEER_REGISTRY_NOW": "**全站來源清單本頁讀不到**",
    "ENGINEER_RECONCILE_NOW": "**雙演算法對帳本頁跑不了**",
    "ENGINEER_API_ROOT_NOW": "**API 根因診斷本頁不做**",
    "ENGINEER_RAW_NOW": "**原始資料表本頁看不到**",
    "ENGINEER_CALIBRATION_NOW": "**門檻校準本頁跑不了**",
    "QA_IDLE_NOW": "**尚未提問**",
    "QA_NO_KEY_NOW": "**AI 問答未啟用**",
    "QA_FAILED_NOW": "**這一輪問答失敗了**",
    "QA_EMPTY_NOW": "**這一輪沒有回答內容**",
}
_NOW_NAME_RE = r"[A-Z0-9_]+_NOW(_TEMPLATE|_HEAD)?"


@pytest.mark.parametrize("name", sorted(_BASELINE_NOW_LITERALS))
def test_now_constant_literal_is_pinned(name):
    assert getattr(P, name) == _BASELINE_NOW_LITERALS[name], f"{name} 的文字被改了"


def test_every_now_constant_in_the_module_is_pinned():
    """模組裡**每一個** `*_NOW` / `*_NOW_TEMPLATE` / `*_NOW_HEAD` 都在上表 —— 新增一則而沒釘 ⇒ 紅燈。"""
    names = {n for n in vars(P) if re.fullmatch(_NOW_NAME_RE, n)}
    assert names == set(_BASELINE_NOW_LITERALS), names ^ set(_BASELINE_NOW_LITERALS)
    assert len(names) == 24


# ── 10. QA F4：卡面短句的**忠實度** —— 原文拿來限定的條件／原因／去處／升級路徑，
#    卡面上⛔ 不得只剩一句沒被限定的話。每一格手寫「必須留在卡面」的片語（第二把尺）。──────
_WHY, _WHERE = P.V2_WHY_FACT_KEY, P.V2_GUIDE_FACT_KEY
_DH = "「📖 憑什麼 › 資料體檢」"
_SCALES = ("要看某一檔的實際數字", "到「🔬 查一檔」或「💼 我的持股」各看各的，不要把兩邊的數字放在一起比")
_UNWIRED = (NO_EXIT_MARKER, "這是待接線項，不是你操作的問題")
_SPEC_WHERE = (NO_EXIT_MARKER, "規格層面的已知限制", "重按幾次都一樣")
_REPORT = "回報給維護者"
_MUST_KEEP: dict[str, dict[str, tuple[str, ...]]] = {
    "L0_FAILED_NOW_TEMPLATE": {_WHY: ("拋出例外",), _WHERE: (NO_EXIT_MARKER, "規格表本身的問題", _REPORT)},
    "SOURCE_IDLE_NOW": {_WHY: ("還沒有真的對外抓過", "快取命中點不亮這一盞"),
                        _WHERE: ("到會用到它的那一頁", "讓它真的跑一次", "就會看到時間")},
    # 「為什麼」兩支原文（不認得的狀態 / 不是 Mapping）→ 逐支必留片語見 `_UNKNOWN_WHY_ANY`。
    "SOURCE_UNKNOWN_NOW_HEAD": {_WHERE: (NO_EXIT_MARKER, "契約漂移", _REPORT)},
    "SOURCE_FAILED_NOW": {_WHY: ("拋出例外",),
                          _WHERE: ("上游來源的問題", "不是你操作的問題", "到會用到它的那一頁",
                                   "重按一次更新", "若持續失敗請", _REPORT)},
    "EMPTY_REGISTRY_NOW": {_WHY: ("如果你是直接打開這一頁", "還沒去過任何會取數的分頁",
                                  "這是正常的，不是壞掉"),
                           _WHERE: ("會抓資料的分頁載入一次", _DH)},
    "FINMIND_QUOTA_NOW": {_WHY: ("FinMind 帳號層級", "不在任何一支 fetcher 的回傳裡"),
                          _WHERE: _UNWIRED},
    # 「為什麼」是 L0 原因欄（每盞不同）→ 逐盞必留片語見 `_SPEC_WHY`。
    "SPEC_FLAG_UNWIRED_NOW": {_WHERE: _SPEC_WHERE},
    "SPEC_FLAG_DEGRADED_NOW": {_WHERE: _SPEC_WHERE},
    "LIGHTS_EMPTY_NOW": {_WHY: ("沒有回傳任何一盞燈的定義",), _WHERE: (NO_EXIT_MARKER, _REPORT)},
    "HEALTH6_NOW": {_WHY: ("沒有任何一份是可讀的資料結構",), _WHERE: _UNWIRED},
    "SCALES_DEGRADED_NOW": {_WHY: ("別照門檻讀", "逐盞原因見上方的 facts 與下方對照表"),
                            _WHERE: _SCALES},
    "SCALES_EMPTY_NOW": {_WHY: ("沒有回傳可用的燈號定義",), _WHERE: _SCALES},
    "LEGACY_NOW": {_WHY: ("搬遷會動到既有分頁與 caller", "刻意不夾帶"),
                   _WHERE: ("這一項有出口", "沒有下架", "照舊使用")},
    "ENGINEER_IDLE_NOW": {_WHY: ("預設不跑",),
                          _WHERE: ("展開「🔧 進階診斷", "勾「載入進階診斷",
                                   "（較耗時，部分項目會實際打外部 API）")},
    "ENGINEER_FAILED_NOW": {_WHY: ("拋出例外",),
                            _WHERE: (NO_EXIT_MARKER, "L0 登錄表的問題", "不是某一個資料來源壞掉",
                                     _REPORT)},
    "ENGINEER_REGISTRY_NOW": {_WHY: ("SSOT 住在 L1", "不得直呼 L1", "也不想依賴「你得先去過另一頁」"), _WHERE: _UNWIRED},
    "ENGINEER_RECONCILE_NOW": {_WHY: ("純函式在 L2", "但 src/services/ 沒有任何一支把它包起來"), _WHERE: _UNWIRED},
    "ENGINEER_API_ROOT_NOW": {_WHY: ("會當場對外送出請求", "L5 直接打外部 API", "明文禁止"),
                              _WHERE: _UNWIRED},
    "ENGINEER_RAW_NOW": {_WHY: ("去翻別頁的 session key", "對方改一個 key，這裡就會靜默變空"),
                         _WHERE: _UNWIRED},
    "ENGINEER_CALIBRATION_NOW": {_WHY: ("不從 UI 觸發離線腳本", "可能改到門檻"), _WHERE: _UNWIRED},
    "QA_IDLE_NOW": {_WHY: ("只根據本站已經載入的資料作答", "不自行上網查"),
                    _WHERE: ("在下方輸入問題並送出",)},
    "QA_NO_KEY_NOW": {_WHY: ("未偵測到 Gemini API 金鑰", "部署端沒有設，或這個環境讀不到"),
                      _WHERE: ("金鑰目前由部署端提供", "環境變數的 GEMINI_API_KEY", NO_EXIT_MARKER)},
    "QA_FAILED_NOW": {_WHY: ("拋出例外",), _WHERE: ("換個問法再送一次", "若持續失敗", _REPORT)},
    "QA_EMPTY_NOW": {_WHY: ("沒有回報錯誤", "也沒有給任何文字", "不是故障"),
                     _WHERE: ("換一個更具體的問法",)},
}
#: 「看不懂的狀態」兩支原文各自的必留片語（原因 ＋ 結論）。
_UNKNOWN_WHY_ANY: tuple[tuple[str, ...], ...] = (
    ("不認得的狀態", "不把它畫成正常"), ("不是 Mapping", "讀不出它的狀態"))
#: L0 規格標記：逐盞的必留片語（**當下的 L0 規格表**；L0 新標一盞而沒補這裡 ⇒ 紅燈）。
_SPEC_WHY: dict[str, tuple[str, ...]] = {
    "why.spec.foreign_net": ("單位未確認",),
    # 原因：固定 3,400 億門檻 vs 已經長大的市場 —— ⛔ 不得只剩「天天紅但不危險」。
    # 「幾乎」⛔ 不得略：少了它卡面比原文更強（「每天都紅」）。
    "why.spec.margin": ("幾乎天天紅", "不代表天天危險", "固定金額", "3,400 億", "台股整體規模長大了不少"),
    # 去處：真要看趨勢該去的那一區。
    "why.spec.stock_trend": ("只比較最近兩季", "🏆 個股組合的「📊 財報趨勢×轉機」區塊"),
}


def _const_name_of(now: str) -> str:
    # 先比對固定字面，再比對模板（`**{label}讀不出來**` 會吞掉「**門檻表讀不出來**」這類固定句）。
    for name, lit in _BASELINE_NOW_LITERALS.items():
        if now == lit:
            return name
    for name, lit in _BASELINE_NOW_LITERALS.items():
        pat = re.escape(lit).replace(re.escape("{label}"), ".+")
        if name.endswith("_HEAD"):
            pat += "（L0 回 .*）"
        if re.fullmatch(pat, now, re.S):
            return name
    raise AssertionError(f"這則 now 不在釘死表裡：{now!r}")


def test_must_keep_table_covers_every_pinned_now():
    assert set(_MUST_KEEP) == set(_BASELINE_NOW_LITERALS)
    flagged = {b[0].key for b in _BUILTS if b[0].key.startswith("why.spec.")}
    assert flagged == set(_SPEC_WHY), flagged ^ set(_SPEC_WHY)


@pytest.mark.parametrize("key", sorted(_NOTES),
                         ids=[f"{k[0]}|{k[1][:10]}|{i}" for i, k in enumerate(sorted(_NOTES))])
def test_face_rows_keep_the_qualifiers_of_their_full_text(key):
    card = _NOTES[key][0]
    name = _const_name_of(card.note.now)
    face = dict(_face_rows(_html(_NOTES[key])))
    for label, phrases in _MUST_KEEP[name].items():
        for ph in phrases:
            assert ph in face[label], f"{card.key}「{label}」卡面少了「{ph}」：{face[label]!r}"
    if name == "SOURCE_UNKNOWN_NOW_HEAD":
        assert any(all(ph in face[_WHY] for ph in g) for g in _UNKNOWN_WHY_ANY), face[_WHY]
    if card.key.startswith("why.spec."):
        for ph in _SPEC_WHY[card.key]:
            assert ph in face[_WHY], f"{card.key}「為什麼」卡面少了「{ph}」：{face[_WHY]!r}"
