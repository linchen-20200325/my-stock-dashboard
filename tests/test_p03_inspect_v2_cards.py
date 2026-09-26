"""「🔬 查一檔」14 張卡改走 v2 卡面（同「💼 我的持股」頁 `57b5993`、「🔍 找標的」頁 `8f3f869`；
客戶 2026-09-25 裁示 1~4 ＋ K1）的守衛。

一條測試對應一種說謊方式（同我的持股頁那一份）：
  · 某一張卡**沒登記**在 v2 契約 → 同頁長出兩種卡面；
  · 某一則可產生的 `Note` **沒有短句** → 渲染當下才炸；短句表有**死列**；
  · 短句**不是原文摘錄**（新造白話 ＝ K1 裁示的 §1 捏造）；
  · 長句被濃縮後**原文不見了**（摺疊區少字 / 只活在 hover）；
  · 「沒有出口」被短句改寫成一個看起來可以按的指路；
  · 兩張卡的摺疊開關 id 撞名 → 點一張開另一張；
  · 卡化順手動到**表格**（本批 ⛔ 不動葉2 那張 `st.dataframe`、⛔ 不畫新表）；
  · 「判不出型別」被畫成紅或畫成可重跑（它是 #8「不適用 · 重跑無效」）；
  · 本頁沒有登記任何「有效的空結果」⇒ #11 ⛔ 不得出現在本頁。

「可產生的 Note」以**窮舉建卡**取得（`_enumerate()`：把每一支 `build_*` 餵過一組
readout 組合，收集實際吐出來的 `(card.key, note.now)`），⛔ 不是手抄一份名單。
"""
from __future__ import annotations

import ast
import html
import inspect
import itertools
import pathlib
import re
import textwrap

import pytest

from shared.ui_state import (
    NO_VALUE_STATES,
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_NOT_APPLICABLE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import NO_EXIT_MARKER
from src.ui.views import page_inspect as P
from src.ui_v2 import blocks, components
from src.ui_v2 import markup as M
from src.ui_v2 import page_inspect as V2I
from src.ui_v2 import page_today as V2

_VIEW = pathlib.Path(P.__file__)
_E = "RuntimeError('boom')"

_STOCK_ENTRY = "🔬 個股分頁（本頁不重複掛載，避免撞 DuplicateWidgetID）"
_ETF_ENTRY = "🏦 ETF 分頁（本頁不重複掛載，避免撞 DuplicateWidgetID）"


def _enumerate():
    """把每一支 `build_*` 餵過一組 readout 組合 → `{(key, now, why, where): built}` ＋ 全部 built。

    上游錯誤字串一律照 loader 真的會組出來的形狀造（`_error_why(SRC_*, …)`），
    ⛔ 不自己編一句 —— 那樣短句驗的就不是畫面上真的會出現的原文。
    不合法的組合（例：`requested=False` 卻帶 `error`）由 L0 當場拒收 —— 本來就產不出來，略過。
    """
    notes: dict[tuple[str, str, str, str], tuple] = {}
    builts: list[tuple] = []

    def add(b):
        builts.append(b)
        c = b[0]
        if c.note is not None:
            notes.setdefault((c.key, c.note.now, c.note.why, c.note.where), b)

    def tryadd(fn, *a, **k):
        try:
            b = fn(*a, **k)
        except (ValueError, TypeError):
            return
        if b and isinstance(b[0], tuple):
            for x in b:
                add(x)
        else:
            add(b)

    reqs = (P.InspectRequest(submitted=False), P.InspectRequest(submitted=True, ticker=""),
            P.InspectRequest(submitted=True, ticker="2330"),
            P.InspectRequest(submitted=True, ticker="00878", kind_choice=P.KIND_CHOICE_STOCK))
    verdicts = (
        P.KindVerdict(requested=False),
        P.KindVerdict(requested=True, code=""),
        P.KindVerdict(requested=True, code="AAPL", auto_kind="unknown", kind="unknown",
                      kind_label=P.KIND_LABEL_FALLBACK,
                      auto_kind_label=P.KIND_LABEL_FALLBACK, is_unknown=True),
        P.KindVerdict(requested=True, code="2330", error=_E),
        P.KindVerdict(requested=True, code="2330", auto_kind="stock", kind="stock",
                      kind_label="個股", auto_kind_label="個股", is_stock=True,
                      benchmark="0050"),
        P.KindVerdict(requested=True, code="00878", auto_kind="etf", kind="stock",
                      kind_label="個股", auto_kind_label="ETF", overridden=True,
                      is_stock=True))
    for v, r in itertools.product(verdicts, reqs):
        tryadd(P.build_kind_card, v, r)
    for v in verdicts:
        tryadd(P.build_unknown_card, v)
    for rq, err, sc in itertools.product((False, True), ("", _E), (None, 72.0)):
        try:
            s = P.StockReadout(requested=rq, error=err, score_pct=sc,
                               grade="A" if sc else "", name="台積電", price=600.0,
                               headline="h", fail_items=("x",),
                               trend_verdict={"verdict": "v"})
        except (ValueError, TypeError):
            continue
        tryadd(P.build_health_card, s)
    val_errs = ("", P._error_why(P.SRC_DIVIDENDS, _E), P._error_why(P.SRC_357, _E))
    for rq, err, zone, src, msg in itertools.product(
            (False, True), val_errs, (None, "cheap", "na"), ("", "FinMind"),
            ("", "無股價，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）", "上游改了字 🔴")):
        try:
            v = P.ValuationReadout(
                requested=rq, error=err, est_yield_pct=(6.0 if zone == "cheap" else None),
                zone_code=(zone or ""), signal="🟢 便宜", msg=msg,
                avg_div_twd=(3.0 if src else None), paying_years=(5 if src else None),
                source=src, years_n=(5 if src else 0), price=600.0)
        except (ValueError, TypeError):
            continue
        tryadd(P.build_valuation_card, v)
    chip_errs = ("", P._error_why(P.SRC_CHIPS, _E),
                 P._error_why(P.SRC_CHIPS, "E", verb="回報失敗"))
    for rq, err, sig, miss, ov in itertools.product(
            (False, True), chip_errs, ("", "🔥 大戶吸籌"), ("", "df缺法人/量欄"),
            ("", "anomaly", "normal", "unknown")):
        try:
            c = P.ChipsView(requested=rq, error=err, signal=sig,
                            concentration=(3.2 if sig else None), continuity=55.0, days=20,
                            pos_days=11, rows=250, days_loaded=250, miss_reason=miss,
                            outlier_verdict=ov, outlier_ratio=6.0, outlier_threshold=5.0,
                            outlier_window=30,
                            outlier_reason=("vol_unavailable" if ov == "unknown" else ""))
        except (ValueError, TypeError):
            continue
        tryadd(P.build_chips_card, c)
    prof_errs = ("", P._error_why(P.SRC_STATEMENTS, _E), P._error_why(P.SRC_HEALTH, _E))
    cells = (P.ProfitCell(key="gross_margin", label="毛利率", value_text="50%",
                          label_text="好生意"),
             P.ProfitCell(key="operating_margin", label="營業利益率", value_text="40%",
                          label_text="本業獲利"),
             P.ProfitCell(key="safety_margin", label="安全邊際", value_text="70%",
                          label_text="抗震"))
    for rq, err, cs, ism, gap, up in itertools.product(
            (False, True), prof_errs, ((), cells, cells[:1]), (False, True),
            ("", "欄位缺"), ("", "查無此代碼")):
        try:
            pr = P.ProfitabilityReadout(requested=rq, error=err, cells=cs,
                                        income_statement_missing=ism, gap_why=gap,
                                        upstream_note=up)
        except (ValueError, TypeError):
            continue
        tryadd(P.build_profit_cards, pr)
    for rq, err, full in itertools.product((False, True), ("", _E), (False, True)):
        try:
            e = P.EtfReadout(requested=rq, error=err,
                             premium_pct=(0.5 if full else None),
                             annual_yield_pct=(6.0 if full else None),
                             peer_ranks=({3: 0.1, 6: 0.2, 12: 0.3} if full else None),
                             quality=({"stars": "★★★"} if full else None),
                             inception_years=5.0)
        except (ValueError, TypeError):
            continue
        for fn in (P.build_premium_card, P.build_dividend_card, P.build_peer_card):
            tryadd(fn, e)
    for rq in (False, True):
        tryadd(P.build_detail_card, rq, key="inspect.stock.detail", label="個股明細",
               sections=P.STOCK_DETAIL_SECTIONS, entry=_STOCK_ENTRY)
        tryadd(P.build_detail_card, rq, key="inspect.etf.detail", label="ETF 明細",
               sections=P.ETF_DETAIL_SECTIONS, entry=_ETF_ENTRY)
    breqs = (P.BatchRequest(submitted=False), P.BatchRequest(submitted=True),
             P.BatchRequest(submitted=True, tickers=("2330", "00878"), truncated=3))
    rows = (P.BatchRow(code="2330", kind="stock", kind_label="個股", is_stock=True,
                       metrics=(("a", "b"),)),
            P.BatchRow(code="9999", error=_E))
    for rq, err, rs, br in itertools.product((False, True), ("", _E), ((), rows), breqs):
        try:
            bro = P.BatchReadout(requested=rq, error=err, rows=rs)
        except (ValueError, TypeError):
            continue
        tryadd(P.build_batch_card, bro, br)
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
    return [(html.unescape(k), html.unescape(v)) for k, v in re.findall(_ROW_RE, fragment)]


def _face_rows(outer: str) -> list[tuple[str, str]]:
    return _rows(_split(outer)[0])


def _fold_rows(outer: str) -> list[tuple[str, str]]:
    return _rows(_split(outer)[1])


def _fold_id(outer: str) -> str | None:
    m = re.search(r'<input type="checkbox" class="blk-fold-i" id="([^"]+)">', outer)
    return m.group(1) if m else None


def _html(built) -> str:
    card, facts, signal = built
    return P.v2_card_html(card, facts, signal)


def _badge_of(out: str) -> int:
    m = re.search(r'class="bdg bdg-(\d+) ', out)
    assert m, "卡面上找不到主徽章"
    return int(m.group(1))


# ── 1. 登記：14 張程式卡全部登記、層→密度照規格 ─────────────────────────
#: UI_PAGE_INSPECT.md ① 表：第一層 n1 → t1、第二層 n2 → t2、第三層 n3 → t3。**手寫**（第二把尺）。
_EXPECTED_TIER = {
    "inspect.kind": "t1", "inspect.unknown": "t1",                              # n1
    "inspect.stock.health": "t2", "inspect.stock.valuation": "t2",
    "inspect.stock.chips": "t2", "inspect.etf.premium": "t2",
    "inspect.etf.dividend": "t2", "inspect.etf.peer": "t2",                     # n2
    "inspect.profit.gross_margin": "t3", "inspect.profit.operating_margin": "t3",
    "inspect.profit.safety_margin": "t3", "inspect.stock.detail": "t3",
    "inspect.etf.detail": "t3", "inspect.batch": "t3",                          # n3
}


def test_every_card_the_page_builds_is_registered_and_nothing_else():
    built_keys = {b[0].key for b in _BUILTS}
    assert len(built_keys) == 14, sorted(built_keys)
    assert built_keys == set(V2I.BLOCK_COLS) == set(_EXPECTED_TIER)


def test_tiers_come_from_the_spec_layers():
    for key, tier in _EXPECTED_TIER.items():
        assert blocks.tier_for_block(key) == tier
        assert V2I.tier_for_block(key) == tier
        assert blocks.BLOCK_PAGE[key] == "inspect"
    for layer in V2I.LAYERS:
        assert layer["tier"] == components.tier_for_layer(layer["layer"])
    assert blocks.PAGES["inspect"] is V2I


def test_spec_block_mapping_and_cols_follow_the_spec_table():
    """`inspect.profit` 是規格的**容器**，程式畫成三張卡；cols 取 ① 表「3/2/1・其餘 1/1/1」。"""
    m = V2I.SPEC_BLOCK
    assert {k for k, v in m.items() if v == "inspect.profit"} == {
        "inspect.profit.gross_margin", "inspect.profit.operating_margin",
        "inspect.profit.safety_margin"}
    assert all(m[k] == k for k in m if not k.startswith("inspect.profit."))
    for k, cols in V2I.BLOCK_COLS.items():
        want = (3, 2, 1) if _EXPECTED_TIER[k] == "t2" or k.startswith("inspect.profit.") \
            else (1, 1, 1)
        assert cols == want, k


def test_no_override_and_badge_10_not_drawn():
    assert list(inspect.signature(V2I.tier_for_block).parameters) == ["block_key"]
    assert V2I.BADGES_NOT_ON_PAGE == frozenset({10})
    for key in V2I.BLOCK_COLS:
        with pytest.raises(ValueError):
            M.card_html(block=key, state="live", title="t", badge_n=10)


def test_page_css_did_not_grow():
    """登記本頁的卡 ⛔ 不得讓 `page_css()` 多產任何 class（其他頁的樣式表輸出不變）。"""
    assert M._BLOCK_COLS_USED == tuple(sorted(set(V2.BLOCK_COLS.values())))


def test_no_block_key_collides_with_another_page():
    for page, mod in blocks.PAGES.items():
        if page == "inspect":
            continue
        for layer in mod.LAYERS:
            assert not (set(layer["blocks"]) & set(V2I.BLOCK_COLS)), page


# ── 2. 短句表：可產生的每一則 Note 都有、而且沒有死列 ──────────────────
def test_short_rows_cover_every_producible_note_and_have_no_dead_rows():
    produced = {(k, now) for (k, now, _w, _x) in _NOTES}
    registered = set(P.V2_SHORT_ROWS)
    assert produced - registered == set(), f"這幾則 Note 沒有短句：{produced - registered}"
    assert registered - produced == set(), f"短句表有死列：{registered - produced}"
    assert len(produced) >= 35, f"窮舉太少，建卡掃描壞了？{len(produced)}"


def test_every_note_now_in_the_module_is_a_registered_constant():
    """靜態對帳：本檔**每一個** `Note(now=…)` 都是常數／`*_NOW_TEMPLATE.format(…)`／參數，
    且每一個被用到的 `*_NOW` 常數至少登記在一列短句表 —— 擋「日後新增一則 Note 而沒補表」。"""
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    names: set[str] = set()
    templates: set[str] = set()
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and getattr(call.func, "id", None) == "Note"):
            continue
        for kw in call.keywords:
            if kw.arg != "now":
                continue
            v = kw.value
            if isinstance(v, ast.Name):
                names.add(v.id)
            elif (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                  and v.func.attr == "format" and isinstance(v.func.value, ast.Name)
                  and v.func.value.id.endswith("_NOW_TEMPLATE")):
                templates.add(v.func.value.id)
            elif isinstance(v, ast.JoinedStr):
                # 只准 v2 渲染失敗的補救紅卡（走舊卡面，不查表）。
                assert "這一格畫不出來" in ast.unparse(v), ast.unparse(v)
            else:
                pytest.fail(f"Note.now 不是常數：{ast.unparse(v)}")
    names -= {"empty_now"}   # `_etf_card()` 的參數名（值由呼叫端傳常數）
    assert len(names) >= 10 and len(templates) == 4, (sorted(names), sorted(templates))
    registered = {now for (_k, now) in P.V2_SHORT_ROWS}
    for n in sorted(names):
        assert getattr(P, n) in registered, f"{n} 沒有登記短句"
    for t in sorted(templates):
        tpl = getattr(P, t)
        assert any(re.fullmatch(re.escape(tpl).replace(re.escape("{label}"), ".+"), r)
                   for r in registered), f"{t} 沒有登記短句"
    # `_etf_card(empty_now=…)` 的呼叫端一律傳常數。
    for call in ast.walk(tree):
        if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "_etf_card":
            for kw in call.keywords:
                if kw.arg == "empty_now":
                    assert isinstance(kw.value, ast.Name), ast.unparse(kw.value)
                    assert getattr(P, kw.value.id) in registered


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


def _idle_chips():
    return P.build_chips_card(P.ChipsView(requested=False))


def test_a_non_excerpt_short_row_raises_and_renders_red(monkeypatch):
    built = _idle_chips()
    card = built[0]
    monkeypatch.setitem(P.V2_SHORT_ROWS, (card.key, card.note.now),
                        ("尚未載入任何分析", "這是一句新寫的白話", "按一下"))
    with pytest.raises(KeyError, match="K1"):
        P.v2_card_html(*built)
    md: list[str] = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s, **_k: md.append(str(s))
    ns.caption = lambda s, **_k: md.append(str(s))
    monkeypatch.setattr(P, "st", ns)
    from src.ui.views import _ui_kit as K
    monkeypatch.setattr(K, "st", ns)
    P._render_one(built)
    out = "\n".join(md)
    assert "這一格畫不出來" in out, "摘錄對不上原文 → 必須是看得見的紅卡"
    assert '<div class="blk blk-' not in out, "新造白話不得以 v2 卡面的短句畫出來"


def test_an_unregistered_note_raises():
    built = _idle_chips()
    saved = P.V2_SHORT_ROWS.pop((built[0].key, built[0].note.now))
    try:
        with pytest.raises(KeyError, match="V2_SHORT_ROWS"):
            P.v2_card_html(*built)
    finally:
        P.V2_SHORT_ROWS[(built[0].key, built[0].note.now)] = saved


def test_no_exit_stays_no_exit_and_keeps_its_next_step():
    """原文「沒有出口」的，短句必須保留這個標記（⛔ 改寫成一個看起來可以按的指路），
    反之亦然；而且⛔ 只剩標記 —— 原文接著說的下一步（回報／待接線）要一起摘上來。"""
    seen = 0
    for card, _f, _s in _NOTES.values():
        where_s = P.v2_short_rows(card)[0][2][1]
        assert (NO_EXIT_MARKER in where_s) == (NO_EXIT_MARKER in card.note.where), card.key
        if NO_EXIT_MARKER in where_s:
            assert where_s != NO_EXIT_MARKER, f"{card.key}: 只剩標記，原文的下一步被吞掉了"
            seen += 1
    assert seen >= 4, "判型失敗／整批失敗／兩支明細都該有「沒有出口」"


def test_valuation_why_follows_the_branch_it_came_from():
    """估值「為什麼」有四種原文 → 各自摘到**自己那一句**（⛔ 一律退回同一句處置語）。"""
    def why_of(**kw):
        b = P.build_valuation_card(P.ValuationReadout(requested=True, price=600.0, **kw))
        return P.v2_short_rows(b[0])[0][1][1]

    # 三段備援都沒給：**兩種可能一起上卡面**（QA F2）。
    w = why_of()
    assert w.startswith("配息備援鏈")
    assert "近 5 年真的沒有配息" in w and "也可能是三段這一輪都沒拿到" in w, w
    # L2 的兩種 `msg`（`v5_modules.calc_dividend_yield_357` 的 `_why` 兩支）：**原因在句首，⛔ 不得略**。
    for cause in ("無股價", "無配息記錄"):
        msg = f"{cause}，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）"
        assert why_of(source="FinMind", years_n=5, zone_code="na", msg=msg) == msg
    assert why_of(source="FinMind", years_n=5, zone_code="na") == "357 殖利率法則在這一檔上不適用"
    # 上游改了字：照樣摘 L2 自己那一句（⛔ 不再退回只剩處置句「本站不以 0% 殖利率頂替」）。
    assert why_of(source="FinMind", years_n=5, zone_code="na", msg="新原因，不適用") == "新原因，不適用"
    for msg in ("無股價，357 殖利率法則不適用", "新原因，不適用", ""):
        assert why_of(source="FinMind", years_n=5, zone_code="na", msg=msg) != "本站不以 0% 殖利率頂替"


def test_valuation_why_too_long_for_the_face_keeps_the_cause_and_stays_grey():
    """QA F7：上游的 `msg` 整句放不下卡面、但第一個子句（＝原因）放得下 → **仍是灰卡**，
    卡面「為什麼」＝ 那個原因（原文開頭逐字）；⛔ 不得翻成紅卡（灰／紅分離）。"""
    msg = "無配息記錄，" + "上游補充說明" * 12
    b = P.build_valuation_card(P.ValuationReadout(
        requested=True, price=600.0, source="FinMind", years_n=5, zone_code="na", msg=msg))
    assert len(msg) > M.FACT_VALUE_MAX_CHARS
    assert b[0].state == UI_EMPTY
    out = P.v2_card_html(*b)
    assert _badge_of(out) != 6, "不適用的灰卡被畫成紅卡"
    assert dict(_face_rows(out))[P.V2_WHY_FACT_KEY] == "無配息記錄"


def test_valuation_why_with_nothing_that_fits_turns_red_not_causeless():
    """連第一個子句都放不下（或根本沒有子句）→ ⛔ 不退回一句沒有原因的處置語，改走看得見的紅卡。"""
    for msg in ("上游" * 40, "上游" * 30 + "，不適用"):
        b = P.build_valuation_card(P.ValuationReadout(
            requested=True, price=600.0, source="FinMind", years_n=5, zone_code="na", msg=msg))
        with pytest.raises(KeyError, match="K1"):
            P.v2_card_html(*b)


def test_chips_why_keeps_the_upstream_reason_on_the_face():
    def why_of(miss):
        b = P.build_chips_card(P.ChipsView(requested=True, rows=250, days_loaded=250,
                                           miss_reason=miss))
        return P.v2_short_rows(b[0])[0][1][1]

    for miss in ("df缺法人/量欄", "df資料不足", "df法人欄全為0", "成交量為0"):
        assert f"（上游給的原因：{miss}）" in why_of(miss), why_of(miss)
    assert "（上游給的原因：上游沒有說）" in why_of("")
    # 原因長到放不下 → 括號與「上游給的原因」仍在（原因本身在「上游說明」那一列與摺疊區）。
    long_w = why_of("x" * 60)
    assert long_w.startswith("判不出籌碼（上游給的原因：…）") and len(long_w) <= M.FACT_VALUE_MAX_CHARS


# ── 4. 每張卡、每一態都走 v2 卡面；原文一字不少 ──────────────────────
@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_every_state_renders_through_the_v2_face(built):
    card, facts, signal = built
    out = _html(built)
    assert f'class="blk blk-{_EXPECTED_TIER[card.key]}"' in out
    v2_state, reason = P.V2_STATE_VOCAB[card.state]
    assert _badge_of(out) == V2.resolve_badge(state=v2_state, miss_reason=reason)
    assert html.escape(P.v2_plain(card.label), quote=True) in out
    if card.state == UI_LIVE:
        assert html.escape(P.v2_plain(card.value), quote=True) in out
        if signal:
            assert f'<div class="blk-lvl">{html.escape(P.v2_plain(signal))}</div>' in out, (
                "舊卡面的訊號頻道不見了")
    else:
        assert '<div class="blk-val">' not in out
        assert '<div class="blk-lvl">' not in out
    assert out.count("<div") == out.count("</div>")


def test_the_badges_mean_what_the_old_card_meant():
    """灰／紅不得互換：idle → #3、unwired → #5、failed → #6、判不出型別 → #8（重跑無效）。"""
    want = {UI_IDLE: 3, UI_UNWIRED: 5, UI_FAILED: 6, UI_NOT_APPLICABLE: 8, UI_LIVE: 1}
    seen: set[str] = set()
    for b in _BUILTS:
        if b[0].state in want:
            assert _badge_of(_html(b)) == want[b[0].state], (b[0].key, b[0].state)
            seen.add(b[0].state)
    assert seen == set(want), f"窮舉沒打到：{set(want) - seen}"
    unknown = [b for b in _BUILTS if b[0].key == "inspect.unknown" and b[0].state != UI_IDLE]
    assert unknown and all(_badge_of(_html(b)) == 8 for b in unknown), "判不出型別必須是 #8"


def test_badge_11_never_appears_on_this_page():
    """本頁在 `V2_VALID_EMPTY_SPEC` **0 筆登記** ⇒ #11「▨ 無資料」⛔ 不得出現；
    每一張「沒有值」的卡徽章與不帶旗標的 `resolve_badge` 逐一相同。"""
    from src.ui.views import page_today as PT

    assert not {p for p in PT.v2_valid_empty_pairs() if p[0].startswith("inspect.")}
    checked = 0
    for b in _BUILTS:
        card = b[0]
        if card.state not in NO_VALUE_STATES:
            continue
        v2_state, reason = P.V2_STATE_VOCAB[card.state]
        assert _badge_of(_html(b)) == V2.resolve_badge(state=v2_state, miss_reason=reason) \
            != V2.VALID_EMPTY_BADGE, (card.key, card.note.now)
        checked += 1
    assert checked > 20


@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_existing_facts_all_stay_on_the_face_after_the_short_rows(built):
    """既有 facts 一列不少、順序不變、標籤整句原文；被摘過的值，**整列原文**一定在摺疊區。"""
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


def test_face_has_no_long_unbroken_ascii_run():
    """窄卡溢出的元兇：值裡一段沒有斷點的識別字。卡面（短句 ＋ fact 值）一律不得出現。"""
    for built in _CASES:
        for _k, v in _face_rows(_html(built)):
            for run in re.findall(r"[\x21-\x7e]{%d,}" % (P.V2_FACE_TOKEN_MAX + 1), v):
                # 含數字的一段一律不略（QA F5），故只擋「有字母、沒有數字」的識別字。
                assert not (re.search(r"[A-Za-z_]", run) and not re.search(r"\d", run)), (
                    built[0].key, v)


def test_long_numbers_are_never_elided_on_the_face():
    assert P._v2_face_value("NT$ 12,345,678,901.5 −3.25%") == "NT$ 12,345,678,901.5 −3.25%"
    assert P._v2_face_value("x compute.etf.asset_lag.classify_asset_kind y") == "x … y"


@pytest.mark.parametrize("glued", ["NT$12,345,678", "TWD1,234,567.8", "2330.TW:600.00"])
def test_numbers_glued_to_letters_are_never_elided(glued):
    """QA F5：黏著幣別／代碼的數字也含字母 —— ⛔ 不得因此整段被吃成「…」。"""
    assert P._v2_face_value(glued) == glued
    assert P._v2_face_value(f"現價 {glued} 元") == f"現價 {glued} 元"
    # 旁邊的純識別字照略，數字那一段照留。
    assert P._v2_face_value(f"{glued} services.valuation_service") == f"{glued} …"


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
    assert seen >= 8


# ── 5. 摺疊開關 id ／ 本頁樣式 ────────────────────────────────────────
def test_fold_ids_are_unique_stable_and_scoped_to_this_page():
    ids: dict[str, set[str]] = {}
    for built in _CASES:
        fid = _fold_id(_html(built))
        if fid is None:
            continue
        assert re.fullmatch(r"fold-inspect-[a-z0-9-]+", fid), fid
        ids.setdefault(built[0].key, set()).add(fid)
    assert all(len(v) == 1 for v in ids.values()), "同一張卡不同態 id 不同 → rerun 展開狀態會掉"
    flat = [next(iter(v)) for v in ids.values()]
    assert len(flat) == len(set(flat)) == 14, "本頁卡之間 id 撞名（或有卡從沒摺疊過）"


def test_inspect_card_css_is_scoped_stacked_and_invents_no_numbers():
    css = P.V2_INSPECT_CARD_CSS
    cls = P.V2_INSPECT_CARD_CLASS
    assert css.count(f".{cls} ") == 3 and ":has(" not in css
    assert f".{cls} .blk-fact{{display:block}}" in css
    assert "white-space:normal" in css and "overflow-wrap:anywhere" in css
    assert not re.search(r"\d", css.replace(cls, "")), "不得寫死任何數字"
    assert cls not in M.page_css("dark") and cls not in M.page_css("light")
    from src.ui.views import page_hold as H
    assert cls != H.V2_HOLD_CARD_CLASS
    assert css == H.V2_HOLD_CARD_CSS.replace(H.V2_HOLD_CARD_CLASS, cls), (
        "與我的持股頁同三條規則、只換外層 class")


def test_render_wraps_each_card_in_the_inspect_scope(monkeypatch):
    sent = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    built = _idle_chips()
    P._render_one(built)
    assert sent == [f'<div class="{P.V2_INSPECT_CARD_CLASS}">{P.v2_card_html(*built)}</div>']


# ── 6. 渲染接線（含突變檢查：拔掉 v2 路徑 → 本組守衛必須轉紅）──────────────
def _assert_every_card_routes_to_v2(monkeypatch):
    seen = []
    monkeypatch.setattr(P, "_render_one_v2", lambda c, f=(), s="": seen.append(c.key))
    monkeypatch.setattr(P, "render_card_isolated",
                        lambda *a, **k: pytest.fail("登記的卡不該走舊卡面"))
    for built in _CASES:
        P._render_one(built)
    assert set(seen) == set(V2I.BLOCK_COLS) == set(_EXPECTED_TIER)


def test_render_routes_every_card_to_the_v2_face(monkeypatch):
    _assert_every_card_routes_to_v2(monkeypatch)


def test_removing_the_card_path_turns_the_routing_guard_red(monkeypatch):
    """突變：把 v2 契約的登記清空（＝ 拔掉卡化路徑），上一條守衛必須失敗 —— 證明它守得到東西。"""
    monkeypatch.setattr(V2I, "BLOCK_COLS", {})
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        _assert_every_card_routes_to_v2(monkeypatch)


def test_css_is_emitted_once_per_run(monkeypatch):
    sent = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    P._inject_v2_css()
    assert len(sent) == 1
    assert P.V2_INSPECT_CARD_CSS in sent[0] and M.page_css(P.V2_CSS_MODE) in sent[0]
    fn = ast.parse(textwrap.dedent(inspect.getsource(P.render_page_inspect)))
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)
             and getattr(c.func, "id", None) == "_inject_v2_css"]
    assert len(calls) == 1, "每輪恰吐一次樣式表"


def test_css_failure_becomes_a_red_card(monkeypatch):
    md = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s, **_k: md.append(str(s))
    ns.caption = lambda s, **_k: md.append(str(s))
    monkeypatch.setattr(P, "st", ns)
    from src.ui.views import _ui_kit as K
    monkeypatch.setattr(K, "st", ns)
    monkeypatch.setattr(P.v2_markup, "page_css", lambda _m: (_ for _ in ()).throw(
        RuntimeError("css exploded")))
    P._inject_v2_css()
    out = "\n".join(md)
    assert "這一格畫不出來" in out and "css exploded" in out


# ── 7. 表格與版面：⛔ 不動 ────────────────────────────────────────────
def test_the_batch_table_is_untouched_and_no_new_table_is_drawn():
    """葉2 的 `st.dataframe` 恰 1 處（規格 ① 表格三斷點「AST 全檔恰 1 處」），卡化沒有加表。"""
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    frames = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
              and isinstance(c.func, ast.Attribute) and c.func.attr in ("dataframe", "table")]
    assert len(frames) == 1 and frames[0].func.attr == "dataframe"
    for built in _CASES:
        assert not any(t in _html(built) for t in ("<table", "<tr", "<td"))


def test_cold_page_mounts_with_v2_cards_and_no_table(tmp_path):
    """整頁冷啟動：判型 ＋ 三格預覽 ＋ 批次總覽 ＝ 5 張 v2 卡、全部灰（#3），沒有表格。"""
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_p03_v2.py"
    script.write_text(textwrap.dedent("""
        from src.ui.views.page_inspect import render_page_inspect
        render_page_inspect()
    """), encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    md = [m.value for m in at.markdown]
    cards = [m for m in md
             if m.startswith(f'<div class="{P.V2_INSPECT_CARD_CLASS}"><div class="blk blk-')]
    assert len(cards) == 5, f"v2 卡面 {len(cards)} 張"
    assert all(_badge_of(c) == 3 for c in cards), "冷啟動一律 #3 灰（⛔ 不得畫成紅）"
    assert sum(P.V2_INSPECT_CARD_CSS in m for m in md) == 1, "樣式表應恰吐一次"
    assert len(at.dataframe) == 0
    assert not any(t in "\n".join(md) for t in ("<table", "<tr", "<td")), "卡化不得畫新表格"
    ids = [m.group(1) for c in cards
           for m in [re.search(r'id="(fold-inspect-[a-z0-9-]+)"', c)] if m]
    assert len(ids) == len(set(ids)) == 5


def test_the_empty_state_constants_are_used_verbatim():
    """上提常數後文字一字未改（抽樣對照原本寫在函式體內的字面）。"""
    assert P.KIND_FAILED_NOW == "**判型判不動了**"
    assert P.PROFIT_EMPTY_NOW_TEMPLATE.format(label="毛利率") == "**毛利率：資料缺漏**"
    assert P.ETF_FAILED_NOW_TEMPLATE.format(label="配息") == "**配息取不到**"
    assert P.DETAIL_UNWIRED_NOW_TEMPLATE.format(label="個股明細") == "**本頁還沒有個股明細**"
    b = P.build_premium_card(P.EtfReadout(requested=True))
    assert b[0].state == UI_EMPTY and b[0].note.now == P.PREMIUM_EMPTY_NOW


# ── 5. QA F4：`*_NOW` 常數的字面釘死（手寫，抄自 origin/main `2a56483` 的函式體內字面）─────
#: ⛔ 不得改成 `getattr(P, name)` 自己對自己 —— 這一張表就是「第二把尺」。
#: 改動任何一則的文字 ⇒ 這裡紅燈 ⇒ 必須同時決定 `V2_SHORT_ROWS` 那一列要不要跟著改。
_BASELINE_NOW_LITERALS: dict[str, str] = {
    "SINGLE_IDLE_NOW": "**尚未載入任何分析**",
    "BLANK_TICKER_NOW": "**你按了載入，但代碼欄是空的**",
    "UNKNOWN_NOW": "**無法判定這是個股還是 ETF** —— 已停在這裡，沒有替你猜",
    "BATCH_IDLE_NOW": "**尚未批次分析**",
    "BATCH_EMPTY_NOW": "**你按了批次分析，但沒有解析出任何代碼**",
    "KIND_FAILED_NOW": "**判型判不動了**",
    "HEALTH_FAILED_NOW": "**健康度算不出來**",
    "HEALTH_EMPTY_NOW": "**這一檔的財報體檢分數算不出來**",
    "VALUATION_FAILED_NOW": "**357 估值算不出來**",
    "VALUATION_EMPTY_NOW": "**這一檔算不出 357 位階**",
    "CHIPS_FAILED_NOW": "**籌碼算不出來**",
    "CHIPS_EMPTY_NOW": "**這一檔判不出近 20 日籌碼**",
    "PREMIUM_EMPTY_NOW": "**這一檔沒有折溢價資料**",
    "DIVIDEND_EMPTY_NOW": "**這一檔查不到近一年的配息紀錄**",
    "PEER_EMPTY_NOW": "**同儕排名算不出來**",
    "BATCH_FAILED_NOW": "**整批都算不出來**",
    # 原本的 f-string：`f"**{_label}算不出來**"` 等（`{label}` 由呼叫端帶）。
    "PROFIT_FAILED_NOW_TEMPLATE": "**{label}算不出來**",
    "PROFIT_EMPTY_NOW_TEMPLATE": "**{label}：資料缺漏**",
    "ETF_FAILED_NOW_TEMPLATE": "**{label}取不到**",
    "DETAIL_UNWIRED_NOW_TEMPLATE": "**本頁還沒有{label}**",
}


@pytest.mark.parametrize("name", sorted(_BASELINE_NOW_LITERALS))
def test_now_constant_literal_is_pinned(name):
    assert getattr(P, name) == _BASELINE_NOW_LITERALS[name], f"{name} 的文字被改了"


def test_every_now_constant_in_the_module_is_pinned():
    """模組裡**每一個** `*_NOW` / `*_NOW_TEMPLATE` 常數都在上表 —— 新增一則而沒釘 ⇒ 紅燈。"""
    names = {n for n in vars(P) if re.fullmatch(r"[A-Z0-9_]+_NOW(_TEMPLATE)?", n)}
    assert names == set(_BASELINE_NOW_LITERALS), names ^ set(_BASELINE_NOW_LITERALS)


# ── 6. QA F2/F3/F4：卡面短句的**忠實度** —— 原文拿來限定的條件／另一種可能／原因／去處／數字，
#    卡面上⛔ 不得只剩一句沒被限定的話。每一格手寫「必須留在卡面」的片語（第二把尺）。──────
_WHY, _WHERE = P.V2_WHY_FACT_KEY, P.V2_GUIDE_FACT_KEY
_DH = "「📖 憑什麼 › 資料體檢」"
_LOAD = "按「🔍 載入完整分析」"
_MUST_KEEP: dict[str, dict[str, tuple[str, ...]]] = {
    "SINGLE_IDLE_NOW": {_WHY: ("在你送出之前", "一次 L3 取數都不會發"),
                        _WHERE: ("輸入代碼", "2330 或 00878", _LOAD)},
    "BLANK_TICKER_NOW": {_WHY: ("不會替你猜一個代碼", "也不會拿上一次查過的那一檔頂替"),
                         _WHERE: ("台股代號", _LOAD)},
    "UNKNOWN_NOW": {_WHY: ("美股／指數／興櫃／輸入錯誤", "這不是故障，重按一百次也是同一個答案"),
                    _WHERE: ("若確定它是台股", "「強制當個股」", "「強制當 ETF」", "後重新載入")},
    "KIND_FAILED_NOW": {_WHY: ("拋出例外",),
                        _WHERE: ("手動覆寫也救不回來", NO_EXIT_MARKER, "回報給維護者")},
    "HEALTH_FAILED_NOW": {_WHY: ("拋出例外",), _WHERE: ("代碼與網路／proxy", _DH)},
    "HEALTH_EMPTY_NOW": {_WHY: ("多半是", "季報還沒進 FinMind", "或該季欄位缺得太多"),
                         _WHERE: ("新上市或剛換季", "若持續如此", _DH, "備援鏈是否可用")},
    "VALUATION_FAILED_NOW": {_WHY: ("拋出例外",), _WHERE: ("代碼與網路／proxy", _DH)},
    # 「為什麼」隨分支不同（L2 的 msg）→ 逐分支由 `test_valuation_why_follows_the_branch_it_came_from` 驗。
    "VALUATION_EMPTY_NOW": {_WHERE: ("若是暫時抓不到", _LOAD, "重跑一次",
                                     "若這一檔近 5 年", "沒有配息", "重按幾次都一樣")},
    "CHIPS_FAILED_NOW": {_WHY: ("L3 近 20 日籌碼",), _WHERE: ("代碼與網路／proxy", _DH)},
    "CHIPS_EMPTY_NOW": {_WHY: ("判不出籌碼", "（上游給的原因：", "這是資料缺漏，不是這一檔籌碼不好"),
                        _WHERE: (_LOAD, "重跑一次",
                                 "新上市或長期停牌的標的也可能整段沒有法人資料")},
    "PREMIUM_EMPTY_NOW": {_WHY: ("同日的官方 iNAV", "（或三道守門員判定它不可信）",
                                 "不是「折溢價為 0」"),
                          _WHERE: ("等當日官方 iNAV 公告", "規模小或剛掛牌的 ETF 常態如此",
                                   "重按不會讓淨值提早出現")},
    "DIVIDEND_EMPTY_NOW": {_WHY: ("可能它真的沒配過息", "也可能上游這一輪沒回配息序列"),
                           _WHERE: ("公開資訊觀測站或發行商網站",)},
    "PEER_EMPTY_NOW": {_WHY: ("檔數不足以排名", "或同儕那一腿這一輪抓取失敗"),
                       _WHERE: ("常態如此", "重按通常不會改變", _DH)},
    "PROFIT_FAILED_NOW_TEMPLATE": {_WHY: ("拋出例外",), _WHERE: ("FinMind 額度", _DH)},
    # 「為什麼」有兩支原文（損益表整張沒回來 / 單一欄位缺）→ 逐支必留片語見 `_PROFIT_EMPTY_WHY_ANY`。
    "PROFIT_EMPTY_NOW_TEMPLATE": {_WHERE: ("其餘兩格若有值就照常顯示", "不必重按",
                                           "季報補齊後這一格會自己回來")},
    "ETF_FAILED_NOW_TEMPLATE": {_WHY: ("拋出例外",), _WHERE: ("代碼與網路／proxy", _DH)},
    "DETAIL_UNWIRED_NOW_TEMPLATE": {_WHY: ("在本頁再掛一次會撞",
                                           "而把取數抄一份到本頁則會變成第二個真相源"),
                                    _WHERE: (NO_EXIT_MARKER, "這是待接線項，不是你操作的問題")},
    "BATCH_IDLE_NOW": {_WHY: ("在你送出之前", "一次 L3 取數都不會發"), _WHERE: ("批次分析",)},
    "BATCH_EMPTY_NOW": {_WHY: ("沒有任何看起來像代碼的字串",),
                        _WHERE: ("用逗號、空白或換行分隔", "批次分析")},
    "BATCH_FAILED_NOW": {_WHY: ("拋出例外",),
                         _WHERE: ("這不是某一檔的問題", NO_EXIT_MARKER, "回報給維護者")},
}
#: 兩支原文各自的必留片語（損益表整張沒回來 vs 單一欄位缺 / 單位異常 —— ⛔ 兩個「或」都要在）。
_PROFIT_EMPTY_WHY_ANY: tuple[tuple[str, ...], ...] = (
    ("損益表這一輪沒有回來",), ("這一季沒抓到", "或上游判定單位異常標了 N/A"))


def _const_name_of(now: str) -> str:
    for name, lit in _BASELINE_NOW_LITERALS.items():
        pat = re.escape(lit).replace(re.escape("{label}"), ".+")
        if re.fullmatch(pat, now):
            return name
    raise AssertionError(f"這則 now 不在釘死表裡：{now!r}")


def test_must_keep_table_covers_every_pinned_now():
    assert set(_MUST_KEEP) == set(_BASELINE_NOW_LITERALS)


@pytest.mark.parametrize("key", sorted(_NOTES),
                         ids=[f"{k[0]}|{k[1][:10]}|{i}" for i, k in enumerate(sorted(_NOTES))])
def test_face_rows_keep_the_qualifiers_of_their_full_text(key):
    card = _NOTES[key][0]
    name = _const_name_of(card.note.now)
    face = dict(_face_rows(_html(_NOTES[key])))
    for label, phrases in _MUST_KEEP[name].items():
        for ph in phrases:
            assert ph in face[label], f"{card.key}「{label}」卡面少了「{ph}」：{face[label]!r}"
    if name == "PROFIT_EMPTY_NOW_TEMPLATE":
        assert any(all(ph in face[_WHY] for ph in grp) for grp in _PROFIT_EMPTY_WHY_ANY), face[_WHY]
