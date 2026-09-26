"""「💼 我的持股」23 張卡改走 v2 卡面（同找標的頁 `8f3f869`；客戶 2026-09-25 裁示 1~4 ＋ K1）的守衛。

一條測試對應一種說謊方式：
  · 某一張卡**沒登記**在 v2 契約 → 同頁長出兩種卡面；
  · 某一則可產生的 `Note` **沒有短句** → 渲染當下才炸；短句表有**死列**；
  · 短句**不是原文摘錄**（新造白話 ＝ K1 裁示的 §1 捏造）；
  · 長句被濃縮後**原文不見了**（摺疊區少字 / 只活在 hover）；
  · 「沒有出口」被短句改寫成一個看起來可以按的指路；
  · 兩張卡的摺疊開關 id 撞名 → 點一張開另一張；
  · 卡化順手動到**表格**（本批 ⛔ 不畫新表、⛔ 不動那 2 張 `st.dataframe`）。

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

from shared.ui_state import NO_VALUE_STATES, UI_DEGRADED, UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.tabs.tab_today import NO_EXIT_MARKER
from src.ui.views import page_hold as P
from src.ui_v2 import blocks, components
from src.ui_v2 import markup as M
from src.ui_v2 import page_hold as V2H
from src.ui_v2 import page_today as V2

_VIEW = pathlib.Path(P.__file__)
_E = "RuntimeError('boom')"


# ── 假 readout（用真的 dataclass；同 `test_p04_hold_view.py` 的理由）──────────
def _stress_res(**kw):
    from src.services.portfolio_deep_service import StressResult

    base = dict(computed=True, drop_pct=-20.0, loss_twd=-224000.0, loss_pct=20.4,
                warn_pct=20.0, total_value_twd=1_100_000.0, valued_n=2, held_n=2)
    base.update(kw)
    return StressResult(**base)


def _var_res(**kw):
    from src.services.portfolio_deep_service import VarResult

    base = dict(computed=True, hist_95_twd=16817.0, hist_99_twd=25000.0,
                param_95_twd=16000.0, param_99_twd=24000.0, monthly_99_twd=95000.0,
                monthly_99_pct=8.63, warn_pct=10.0, total_value_twd=1_100_000.0,
                n_common=119, n_union=120, first_day="2025-01-02",
                last_day="2025-06-17", valued_n=2, held_n=2)
    base.update(kw)
    return VarResult(**base)


def _cash_res(**kw):
    from src.services.portfolio_deep_service import DividendCashResult

    base = dict(computed=True, coverage_pct=100.0, gross_twd=30000.0, nhi_twd=0.0,
                net_after_nhi_twd=30000.0, payouts_n=8, tw_n=2, lots_n=2, held_n=2,
                shares_total=3000.0)
    base.update(kw)
    return DividendCashResult(**base)


def _rows_with_lights() -> tuple[dict, ...]:
    from shared.station_specs import KEY_HEALTH_A
    from src.compute.etf.dividend_station import LightCell

    return ({"代號": "0056", "名稱": "高股息", "種類": "ETF", "健檢": "🟢",
             "_lights": (LightCell(key=KEY_HEALTH_A, level="🟢", state="live"),),
             "_detail": {}},)


def _enumerate():
    """把每一支 `build_*` 餵過一組 readout 組合 → `{(key, now, why, where): built}` ＋ 全部 built。

    不合法的組合（例：`requested=False` 卻帶 `error`）由 L0 當場拒收 —— 那些本來就產不出來，略過。
    """
    notes: dict[tuple[str, str, str, str], tuple] = {}
    builts: list[tuple] = []

    def add(fn, *a):
        try:
            b = fn(*a)
        except (ValueError, TypeError):
            return
        builts.append(b)
        c = b[0]
        if c.note is not None:
            notes.setdefault((c.key, c.note.now, c.note.why, c.note.where), b)

    rows_l, rows_n = _rows_with_lights(), ({"代號": "0056", "名稱": "x"},)
    split = {"core_pct": 70.0, "sat_pct": 30.0, "core_dev": -10.0, "total_value": 1.0,
             "partial": False, "held_n": 2, "valued_n": 2}
    for rq, sb, er, hn, bd, rows, sp, tp in itertools.product(
            (False, True), (False, True), ("", _E), (0, 2), (False, True),
            ((), rows_l, rows_n), (None, split), ((), ({"代號": "2330", "損益%": 22.0},))):
        try:
            st_ = P.StationReadout(requested=rq, submitted=sb, error=er, holdings_n=hn,
                                   bound=bd, rows=rows, split=sp, take_profit=tp,
                                   total_lights=1 if rows is rows_l else 0,
                                   judged=1 if rows is rows_l else 0, add_n=1, cut_n=1)
        except (ValueError, TypeError):
            continue
        for fn in (P.build_action_card, P.build_confidence_card, P.build_todo_card,
                   P.build_lightwall_card, P.build_allocation_split_card,
                   P.build_take_profit_card, P.build_core_satellite_card):
            add(fn, st_)
        for srq, ssb, ser, adv in itertools.product(
                (False, True), (False, True), ("", _E), (False, True)):
            try:
                sw = P.SwitchReadout(requested=srq, submitted=ssb, error=ser,
                                     switch_out=(({"代號": "1", "建議動作": "汰弱"},)
                                                 if adv else ()))
            except (ValueError, TypeError):
                continue
            add(P.build_switch_card, sw, st_)
        for arq, aer, kind, txt in (
                (False, "", "", ""), (True, "", "", ""), (True, "", "", "推播文字"),
                (True, _E, P.AI_ERR_UPSTREAM, ""),
                (True, "⚠️ AI 服務暫時無法使用", P.AI_ERR_UNAVAILABLE, ""),
                (True, "tuple", P.AI_ERR_DRIFT, ""),
                (True, P.AI_EMPTY_ERROR, P.AI_ERR_EMPTY, ""),
                (True, _E, P.AI_ERR_EXCEPTION, "")):
            add(P.build_ai_summary_card,
                P.AiSummaryReadout(requested=arq, error=aer, error_kind=kind, text=txt), st_)
    # 只在特定條件才長出來的 fact 列（部分涵蓋、抓取失敗、估算 Beta、樣本壓縮…）——
    # 窄卡標籤摘錄表要涵蓋它們，所以窮舉也要走到它們。
    rich = P.StationReadout(
        requested=True, submitted=True, bound=True, holdings_n=3, rows=rows_l,
        split=dict(split, partial=True, valued_n=1), err_n=1, unjudged_rows=1,
        tally={"運作中": 1}, total_lights=1, judged=1, add_n=1, cut_n=1,
        take_profit=({"代號": "2330", "損益%": 22.0},),
        totals={"pnl_twd": 1.0, "pnl_pct": 1.0, "value_twd": 2.0,
                "held_n": 3, "valued_n": 2, "partial": True})
    for fn in (P.build_action_card, P.build_confidence_card, P.build_todo_card,
               P.build_lightwall_card, P.build_allocation_split_card,
               P.build_take_profit_card, P.build_core_satellite_card):
        add(fn, rich)
    for src in ("watchlist", "pool"):
        add(P.build_switch_card, P.SwitchReadout(
            requested=True, submitted=True, stance="defensive", excluded_n=1,
            switch_out=({"代號": "2330", "建議動作": "汰弱"},),
            switch_in=({"代號": "0056", "名稱": "高股息"},), switch_in_src=src), rich)
    add(P.build_macro_stage_card, P.MacroReadout(
        requested=True, loaded=True, regime="bull", health=60.0, posture_label="積極",
        posture_range="30-50%", defense=False))
    add(P.build_position_cap_card, P.AllocationReadout(
        requested=True, is_loaded=True, range_text="30-50%", posture="中性",
        cap_name="VIX", drivers=("a",), conflicts=("b",)))
    add(P.build_holdings_preview_card, P.HoldingsReadout(
        requested=True, submitted=True, bound=True, portfolio_name="p", watchlist_name="w",
        more_portfolios=True, watchlist_error="E",
        holdings=({"ticker": "0056", "held": True, "lots": 3, "avg_price": 35.0},)))
    _rich_deep = P.DeepReadout(
        requested=True, submitted=True, bound=True, holdings_n=2, has_station_rows=True,
        stress=_stress_res(beta_imputed=("2330",), valued_n=1),
        var=_var_res(dropped=3, limiter="2330", limiter_start="2025-03-01",
                     no_price=("9999",)),
        cash=_cash_res(overseas=("AAPL",), no_payout_tickers=("0050",), lots_n=1))
    add(P.build_stress_card, _rich_deep)
    add(P.build_var_card, _rich_deep)
    add(P.build_dividend_cash_card, _rich_deep)
    _sd = P.build_scale_disclosure()
    for sd in (_sd, P.ScaleDisclosure(error=_E), P.ScaleDisclosure(),
               P.ScaleDisclosure(hold_rows=_sd.hold_rows, inspect_rows=_sd.inspect_rows)):
        add(P.build_scale_card, sd)
    for rq, er, v in itertools.product((False, True), ("", _E), (None, 18.0)):
        add(P.build_vix_card, P.VixReadout(requested=rq, error=er, vix=v))
    for rq, er, ld in itertools.product((False, True), ("", _E), (False, True)):
        add(P.build_macro_stage_card,
            P.MacroReadout(requested=rq, error=er, loaded=ld, regime="bull"))
        add(P.build_position_cap_card,
            P.AllocationReadout(requested=rq, error=er, is_loaded=ld, range_text="30-50%"))
    for rq, sb, er, sbd, cr, pc, mr in itertools.product(
            (False, True), (False, True), ("", _E), (False, True), (False, True),
            (None, 0, 2), ("", P.MISS_FETCH_FAILED, P.MISS_NO_INPUT)):
        try:
            b = P.BindingReadout(requested=rq, submitted=sb, error=er, sheet_bound=sbd,
                                 logged_in=sbd, count_requested=cr, portfolio_count=pc,
                                 count_missing_reason=mr)
        except (ValueError, TypeError):
            continue
        add(P.build_binding_card, b)
        add(P.build_portfolio_count_card, b)
    for rq, sb, er, bd, h in itertools.product(
            (False, True), (False, True), ("", _E), (False, True),
            ((), ({"ticker": "0056", "held": True, "lots": 3, "avg_price": 35.0},))):
        try:
            hr = P.HoldingsReadout(requested=rq, submitted=sb, error=er, bound=bd, holdings=h)
        except (ValueError, TypeError):
            continue
        add(P.build_holdings_preview_card, hr)
    for rq in (False, True):
        for b in P.build_setup_unwired_cards(rq):
            add(lambda x: x, b)
        for s in P.DEEP_SPECS:
            add(P.build_unwired_card, rq, s)
    stress = (None, _stress_res(), _stress_res(computed=False, reason="r"),
              _stress_res(reconciled=False, reference_value_twd=1.0))
    var = (None, _var_res(), _var_res(computed=False), _var_res(no_price=("2330",)),
           _var_res(reconciled=False, reference_value_twd=1.0),
           _var_res(reconciled=False, reference_value_twd=1.0, no_price=("2330",)),
           _var_res(fetch_errors=("2330: E",), tickers_used=()))
    cash = (None, _cash_res(), _cash_res(gross_twd=0.0, payouts_n=0), _cash_res(computed=False),
            _cash_res(coverage_pct=50.0, excluded_tickers=("x",)),
            _cash_res(coverage_pct=50.0, excluded_tickers=("x",), overseas=("x",)),
            _cash_res(coverage_pct=50.0))
    for rq, sb, er, hn, bd, hs in itertools.product(
            (False, True), (False, True), ("", _E), (0, 2), (False, True), (False, True)):
        for s, v, c, errs in itertools.product(stress, var, cash, (("", "", ""), (_E, _E, _E))):
            try:
                d = P.DeepReadout(requested=rq, submitted=sb, error=er, holdings_n=hn,
                                  bound=bd, has_station_rows=hs, stress=s, var=v, cash=c,
                                  stress_error=errs[0], var_error=errs[1], cash_error=errs[2])
            except (ValueError, TypeError):
                continue
            add(P.build_stress_card, d)
            add(P.build_var_card, d)
            add(P.build_dividend_cash_card, d)
    # 批次 1（2026-09-26）：持有的衛星有整批抓取失敗列 → 停利卡的第二種紅（無例外）。
    add(P.build_take_profit_card, P.StationReadout(
        requested=True, submitted=True, bound=True, holdings_n=2,
        rows=({"代號": "2330", "種類": "個股", "held": True, "_detail": {}},
              {"代號": "2454", "種類": "個股", "held": True, "_detail": {"error": "E"}})))
    return notes, builts


_NOTES, _BUILTS = _enumerate()
#: 每一則可產生的 Note 一個代表 ＋ 每張卡的 live 一個代表。
_CASES = list(_NOTES.values()) + list(
    {b[0].key: b for b in _BUILTS if b[0].state == UI_LIVE}.values())
_IDS = [f"{b[0].key}:{b[0].state}:{i}" for i, b in enumerate(_CASES)]

_ROW_RE = r'<span class="blk-fact-k">(.*?)</span><span class="blk-fact-v"[^>]*>(.*?)</span>'

#: 本頁**有效的空結果**（#11「▨ 無資料」，客戶 2026-09-26）。**手寫、⛔ 不讀實作的登記表**。
#: 逐張審查理由見 `HANDOFF.md §6.4`；⛔ 未列者（含 `hold.switch`／`hold.take_profit`／
#: `hold.deep.dividend_cash` 的空態）一律維持原徽章。
_VALID_EMPTY_EXPECTED: frozenset[tuple[str, str]] = frozenset({
    ("hold.portfolio_count", P.COUNT_EMPTY_NOW),
})


def _is_expected_valid_empty(card) -> bool:
    return (card.state == UI_EMPTY and card.note is not None
            and (card.key, card.note.now) in _VALID_EMPTY_EXPECTED)


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


# ── 1. 登記：23 張程式卡全部登記、層→密度照規格 ─────────────────────────
_EXPECTED_TIER = {
    "hold.scales": "t3",                                     # n0
    "hold.conclusion.action": "t2", "hold.conclusion.confidence": "t2",
    "hold.conclusion.todo": "t2",                             # n2 conclusion_cards
    "hold.alloc_split": "t2", "hold.take_profit": "t2",
    "hold.position_cap": "t2",                                # n2 alloc_deviation
    "hold.lightwall": "t3", "hold.vix": "t3", "hold.switch": "t3",
    "hold.macro_stage": "t3", "hold.deep.rebalance": "t3",
    "hold.deep.core_satellite": "t3", "hold.deep.stress": "t3", "hold.deep.var": "t3",
    "hold.deep.dividend_cash": "t3", "hold.deep.grape": "t3", "hold.ai_summary": "t3",
    "hold.binding": "t3", "hold.portfolio_count": "t3", "hold.setup.preview": "t3",
    "hold.setup.pick_sheet": "t3", "hold.setup.watchlist": "t3",   # n3
}


def test_every_card_the_page_builds_is_registered_and_nothing_else():
    built_keys = {b[0].key for b in _BUILTS}
    assert len(built_keys) == 23, sorted(built_keys)
    assert built_keys == set(V2H.BLOCK_COLS) == set(_EXPECTED_TIER)


def test_tiers_come_from_the_spec_layers():
    for key, tier in _EXPECTED_TIER.items():
        assert blocks.tier_for_block(key) == tier
        assert V2H.tier_for_block(key) == tier
        assert blocks.BLOCK_PAGE[key] == "hold"
    for layer in V2H.LAYERS:
        assert layer["tier"] == components.tier_for_layer(layer["layer"])


def test_spec_block_mapping_is_the_data_map_one():
    """`DATA_MAP_HOLD.md`「block key ≠ 實作 key」逐字對映。"""
    m = V2H.SPEC_BLOCK
    assert m["hold.scales"] == "hold.scale_disclosure"
    assert {k for k, v in m.items() if v == "hold.conclusion_cards"} == {
        "hold.conclusion.action", "hold.conclusion.confidence", "hold.conclusion.todo"}
    assert {k for k, v in m.items() if v == "hold.alloc_deviation"} == {
        "hold.alloc_split", "hold.take_profit", "hold.position_cap"}
    assert {k for k, v in m.items() if v == "hold.war_table"} == {"hold.lightwall", "hold.vix"}
    assert {k for k, v in m.items() if v == "hold.swap_compare"} == {
        "hold.switch", "hold.macro_stage"}
    assert {k for k, v in m.items() if v == "hold.deep_analysis"} == {
        k for k in m if k.startswith("hold.deep.")}


def test_no_override_and_badge_10_not_drawn():
    assert list(inspect.signature(V2H.tier_for_block).parameters) == ["block_key"]
    assert V2H.BADGES_NOT_ON_PAGE == frozenset({10})
    for key in V2H.BLOCK_COLS:
        with pytest.raises(ValueError):
            M.card_html(block=key, state="live", title="t", badge_n=10)


def test_page_css_did_not_grow():
    """登記本頁的卡 ⛔ 不得讓 `page_css()` 多產任何 class（today 的樣式表輸出不變）。"""
    assert M._BLOCK_COLS_USED == tuple(sorted(set(V2.BLOCK_COLS.values())))


# ── 2. 短句表：可產生的每一則 Note 都有、而且沒有死列 ──────────────────
def test_short_rows_cover_every_producible_note_and_have_no_dead_rows():
    produced = {(k, now) for (k, now, _w, _x) in _NOTES}
    registered = set(P.V2_SHORT_ROWS)
    assert produced - registered == set(), f"這幾則 Note 沒有短句：{produced - registered}"
    assert registered - produced == set(), f"短句表有死列：{registered - produced}"
    assert len(produced) >= 100, f"窮舉太少，建卡掃描壞了？{len(produced)}"


def test_every_note_now_in_the_module_is_a_registered_constant():
    """靜態對帳：本檔**每一個** `Note(now=…)` 都是常數／參數／`DEGRADED_NOW_TEMPLATE`，
    且每一個 `*_NOW` 常數至少登記在一列短句表 —— 擋「日後新增一則 Note 而沒補表」。"""
    tree = ast.parse(_VIEW.read_text(encoding="utf-8"))
    names: set[str] = set()
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and getattr(call.func, "id", None)
                in ("Note", "UnwiredSpec", "_station_note", "_deep_note")):
            continue
        for kw in call.keywords:
            if kw.arg != "now":
                continue
            v = kw.value
            if isinstance(v, ast.Name):
                names.add(v.id)
            elif isinstance(v, ast.IfExp):
                names.update(n.id for n in (v.body, v.orelse) if isinstance(n, ast.Name))
            elif isinstance(v, ast.Attribute) and v.attr == "now":
                continue            # spec.now（UnwiredSpec）
            elif (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                  and getattr(v.func.value, "id", "") == "DEGRADED_NOW_TEMPLATE"):
                continue
            elif isinstance(v, ast.JoinedStr):
                # 只准兩處：v2 渲染失敗的補救紅卡（走舊卡面，不查表）。
                assert "這一格畫不出來" in ast.unparse(v), ast.unparse(v)
            else:
                pytest.fail(f"Note.now 不是常數：{ast.unparse(v)}")
    names -= {"now"}   # `_station_note` / `_deep_note` 的參數名
    assert len(names) >= 45, sorted(names)
    registered = {now for (_k, now) in P.V2_SHORT_ROWS}
    produced = {now for (_k, now, _w, _x) in _NOTES}
    for n in sorted(names):
        if n in _UNREACHABLE_NOW:
            # 反證：它真的產不出來（哪天變得產得出來，這裡紅燈 → 去補一列短句）。
            assert getattr(P, n) not in produced, f"{n} 現在產得出來了，要補短句"
            continue
        assert getattr(P, n) in registered, f"{n} 沒有登記短句"


#: 傳給 `_station_note()` / `_deep_note()` 當 `now=`、但**結構上到不了**的常數：
#: 那兩支只在 `error` 分支用呼叫端的 `now`，而這幾個呼叫點之前，同一張卡已先以
#: `UI_FAILED` 分支接走了 error ⇒ 這一句從來不會上畫面（既有現況，本批⛔ 不改）。
#: ⛔ 不為它們登記短句（那會是短句表的死列）。
_UNREACHABLE_NOW = frozenset({
    "SPLIT_NO_HOLDINGS_NOW", "TP_NO_HOLDINGS_NOW", "STRESS_NO_HOLDINGS_NOW",
    "VAR_NO_HOLDINGS_NOW", "CASH_NO_HOLDINGS_NOW",
})


# ── 3. K1：短句一律是原文摘錄 ─────────────────────────────────────────
@pytest.mark.parametrize("key", sorted(_NOTES), ids=[f"{k[0]}|{k[1][:10]}" for k in sorted(_NOTES)])
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


def test_a_non_excerpt_short_row_raises_and_renders_red(monkeypatch):
    built = P.build_vix_card(P.VixReadout(requested=False))
    card = built[0]
    k = (card.key, card.note.now)
    monkeypatch.setitem(P.V2_SHORT_ROWS, k, ("尚未執行", "這是一句新寫的白話", "按一下"))
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


def test_an_unregistered_note_raises(monkeypatch):
    built = P.build_vix_card(P.VixReadout(requested=False))
    monkeypatch.delitem(P.V2_SHORT_ROWS, (built[0].key, built[0].note.now))
    with pytest.raises(KeyError, match="V2_SHORT_ROWS"):
        P.v2_card_html(*built)


def test_no_exit_stays_no_exit_and_keeps_its_next_step():
    """原文「沒有出口」的，短句必須保留這個標記（⛔ 改寫成一個看起來可以按的指路），
    反之亦然；而且⛔ 只剩標記 —— 原文接著說的下一步（回報／現行入口／待接線）要一起摘上來。"""
    for card, _f, _s in _NOTES.values():
        where_s = P.v2_short_rows(card)[0][2][1]
        assert (NO_EXIT_MARKER in where_s) == (NO_EXIT_MARKER in card.note.where), card.key
        if NO_EXIT_MARKER in where_s:
            assert where_s != NO_EXIT_MARKER, f"{card.key}: 只剩標記，原文的下一步被吞掉了"


def test_qa_flagged_qualifiers_are_kept():
    rows = P.V2_SHORT_ROWS
    assert rows[("hold.switch", P.SWITCH_EMPTY_NOW)][2].startswith("若你預期應該要有：")
    assert rows[("hold.take_profit", P.TP_EMPTY_NOW)][2].startswith("若你預期應該要有：")
    for k, n in (("hold.setup.pick_sheet", P.PICK_SHEET_UNWIRED_NOW),
                 ("hold.setup.watchlist", P.WATCHLIST_UNWIRED_NOW)):
        assert "📁 組合管理" in rows[(k, n)][2]
    assert rows[("hold.scales", P.SCALE_DEGRADED_NOW)][1][0].startswith("其中一側")


# ── 4. 每張卡、每一態都走 v2 卡面；原文一字不少 ──────────────────────
@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_every_state_renders_through_the_v2_face(built):
    card, facts, signal = built
    out = _html(built)
    assert f'class="blk blk-{_EXPECTED_TIER[card.key]}"' in out
    v2_state, reason = P.V2_STATE_VOCAB[card.state]
    # 📌 2026-09-26：登記過的有效空結果畫 #11，其餘照舊（期望值用本檔**手寫**的
    #    `_VALID_EMPTY_EXPECTED`，⛔ 不讀實作的登記表 —— 測試是第二把尺）。
    _want = (V2.VALID_EMPTY_BADGE if _is_expected_valid_empty(card)
             else V2.resolve_badge(state=v2_state, miss_reason=reason))
    assert f"bdg bdg-{_want} " in out
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


@pytest.mark.parametrize("built", _CASES, ids=_IDS)
def test_existing_facts_all_stay_on_the_face_after_the_short_rows(built):
    """既有 facts 一列不少、順序不變；窄卡上標籤可能是摘錄，但**整列原文**一定在摺疊區。"""
    card, facts, _s = built
    out = _html(built)
    rows = _face_rows(out)
    tail = rows[3:] if card.note is not None else rows
    assert len(tail) == len(facts)
    fold = _fold_rows(out)
    for (fk, fv), (k, v) in zip(tail, facts):
        k, v = P.v2_plain(k), P.v2_plain(v)
        assert fk == k, "卡面標籤必須是整句原文（第 4 輪：標籤疊在值上方，⛔ 不再摘錄）"
        shown = fv[:-1] if fv.endswith(M.FACT_VALUE_ELLIPSIS) and len(fv) > M.FACT_VALUE_MAX_CHARS else fv
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
                assert not re.search(r"[A-Za-z_]", run), (built[0].key, v)


def test_long_numbers_are_never_elided_on_the_face():
    """QA 第 2 輪：10 位數以上的金額與長百分比⛔ 不得被「略過識別字」規則吃成「…」。"""
    big = 1_234_567_890.0
    deep = P.DeepReadout(
        requested=True, submitted=True, bound=True, holdings_n=2, has_station_rows=True,
        stress=_stress_res(total_value_twd=big, reconciled=False, reference_value_twd=1.0),
        var=None, cash=None)
    card, facts, sig = P.build_stress_card(deep)
    face = dict(_face_rows(P.v2_card_html(card, facts, sig)))
    assert face["納入計算的組合總市值（元）"] == "1,234,567,890"
    long_pct = next(v for _k, v in facts if "差 " in v and "%" in v)
    pct = re.search(r"差 [\d.]+%", long_pct).group(0)
    assert len(pct) >= 13
    assert P._v2_face_value(long_pct).count(pct) == 1, "長百分比被略掉了"
    assert P._v2_face_value("NT$ 12,345,678,901.5 −3.25%") == "NT$ 12,345,678,901.5 −3.25%"


def test_face_labels_are_the_full_original_labels():
    """QA 第 4 輪：標籤疊在值上方 ⇒ 卡面標籤一律整句原文（第 2~3 輪的摘錄丟過限定詞）。"""
    assert not hasattr(P, "V2_FACE_LABELS")
    for built in _CASES:
        card, facts, _s = built
        rows = _face_rows(_html(built))
        tail = rows[3:] if card.note is not None else rows
        assert [k for k, _ in tail] == [P.v2_plain(k) for k, _ in facts]


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
        # hover 裡的字可能是「略過識別字」後的卡面值 ⇒ 逐段在摺疊區依序找得到即可。
        pos = 0
        for piece in html.unescape(t).split(P.V2_EXCERPT_GAP):
            if not piece:
                continue
            at = fold_text.find(piece, pos)
            assert at >= 0, f"只活在 hover 的字：{piece[:40]}"
            pos = at + len(piece)


def test_red_cards_keep_the_exception_text_in_the_fold_only():
    for card, facts, sig in _NOTES.values():
        if card.state != UI_FAILED or _E not in card.note.why:
            continue
        out = P.v2_card_html(card, facts, sig)
        assert _E in dict(_fold_rows(out))[P.V2_WHY_FACT_KEY]
        assert _E not in "".join(v for _k, v in _face_rows(out))


def test_degraded_cards_keep_the_current_value_on_the_face():
    seen = 0
    for card, facts, sig in _NOTES.values():
        if card.state == UI_DEGRADED and card.key.startswith("hold.deep."):
            face = dict(_face_rows(P.v2_card_html(card, facts, sig)))
            assert any(k.startswith("現值") for k in face), card.key
            seen += 1
    assert seen >= 3


# ── 5. 摺疊開關 id ────────────────────────────────────────────────
def test_fold_ids_are_unique_stable_and_scoped_to_this_page():
    ids: dict[str, set[str]] = {}
    for built in _CASES:
        fid = _fold_id(_html(built))
        if fid is None:
            continue
        assert re.fullmatch(r"fold-hold-[a-z0-9-]+", fid), fid
        ids.setdefault(built[0].key, set()).add(fid)
    assert all(len(v) == 1 for v in ids.values()), "同一張卡不同態 id 不同 → rerun 展開狀態會掉"
    flat = [next(iter(v)) for v in ids.values()]
    assert len(flat) == len(set(flat)) == 23, "本頁卡之間 id 撞名（或有卡從沒摺疊過）"


def test_hold_card_css_is_scoped_stacked_and_invents_no_numbers():
    css = P.V2_HOLD_CARD_CSS
    cls = P.V2_HOLD_CARD_CLASS
    assert css.count(f".{cls} ") == 3 and ":has(" not in css
    assert f".{cls} .blk-fact{{display:block}}" in css
    assert "white-space:normal" in css and "overflow-wrap:anywhere" in css
    assert not re.search(r"\d", css.replace(cls, "")), "不得寫死任何數字"
    assert cls not in M.page_css("dark") and cls not in M.page_css("light")


def test_render_wraps_each_card_in_the_hold_scope(monkeypatch):
    sent = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    built = P.build_vix_card(P.VixReadout(requested=False))
    P._render_one(built)
    assert sent == [f'<div class="{P.V2_HOLD_CARD_CLASS}">{P.v2_card_html(*built)}</div>']


# ── 6. 渲染接線 ───────────────────────────────────────────────────
def test_render_routes_every_card_to_the_v2_face(monkeypatch):
    seen = []
    monkeypatch.setattr(P, "_render_one_v2", lambda c, f=(), s="": seen.append(c.key))
    monkeypatch.setattr(P, "render_card_isolated",
                        lambda *a, **k: pytest.fail("登記的卡不該走舊卡面"))
    for built in _CASES:
        P._render_one(built)
    assert set(seen) == set(V2H.BLOCK_COLS)


def test_css_is_emitted_once_per_run_without_a_session_write(monkeypatch):
    sent = []
    ns = type("NS", (), {})()
    ns.markdown = lambda s_, **k: sent.append(s_)
    monkeypatch.setattr(P, "st", ns)
    P._inject_v2_css()
    assert len(sent) == 1
    assert P.V2_HOLD_CARD_CSS in sent[0] and M.page_css(P.V2_CSS_MODE) in sent[0]
    fn = ast.parse(textwrap.dedent(inspect.getsource(P.render_page_hold)))
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


def test_cold_page_mounts_with_23_v2_cards_and_still_two_tables(tmp_path):
    """整頁冷啟動：23 張全是 v2 卡面、那 2 張 `st.dataframe` 原封不動、沒有新表格。"""
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_p04_v2.py"
    script.write_text(textwrap.dedent("""
        from src.ui.views.page_hold import render_page_hold
        render_page_hold()
    """), encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    md = [m.value for m in at.markdown]
    cards = [m for m in md if m.startswith(f'<div class="{P.V2_HOLD_CARD_CLASS}"><div class="blk blk-')]
    assert len(cards) == 23, f"v2 卡面 {len(cards)} 張"
    assert sum(P.V2_HOLD_CARD_CSS in m for m in md) == 1, "樣式表應恰吐一次"
    assert len(at.dataframe) == 2, "表格數量變了（本批 ⛔ 不動那 2 張 st.dataframe）"
    assert not any(t in "\n".join(md) for t in ("<table", "<tr", "<td")), "卡化不得畫新表格"
    ids = [m.group(1) for c in cards
           for m in [re.search(r'id="(fold-hold-[a-z0-9-]+)"', c)] if m]
    assert len(ids) == len(set(ids)) == 23


# ── #11「▨ 無資料」—— 有效的空結果（客戶 2026-09-26 新增；**只給登記的卡**）────────
def _badge_of(out: str) -> int:
    _m = re.search(r'class="bdg bdg-(\d+) ', out)
    assert _m, "卡面上找不到主徽章"
    return int(_m.group(1))


def test_badge_11_appears_exactly_on_the_registered_valid_empty_pairs():
    """窮舉本頁每一支 builder × 每一組 readout：畫出 #11 的 `(key, now)` 集合 **＝** 登記表，一個不多、一個不少。"""
    _eleven = {(b[0].key, b[0].note.now) for b in _BUILTS
               if _badge_of(_html(b)) == V2.VALID_EMPTY_BADGE}
    assert _eleven == set(_VALID_EMPTY_EXPECTED)
    # 實作端登記表（本頁那一半）也必須與手寫期望相等 —— 兩把尺對得上。
    from src.ui.views import page_today as PT
    assert {p for p in PT.v2_valid_empty_pairs() if p[0].startswith("hold.")} == set(
        _VALID_EMPTY_EXPECTED)


def test_every_other_no_value_card_keeps_its_old_badge():
    """#11 ⛔ 不得擴散：沒登記的「沒有值」卡（真缺漏／未綁定／這輪沒讀／未評估／算不出來／漂移）
    徽章與改動前**逐一相同**（＝ `resolve_badge` 不帶旗標的結果；`UI_EMPTY` ⇒ #7）。"""
    _checked = 0
    for b in _BUILTS:
        card = b[0]
        if card.state not in NO_VALUE_STATES or _is_expected_valid_empty(card):
            continue
        v2_state, reason = P.V2_STATE_VOCAB[card.state]
        _old = V2.resolve_badge(state=v2_state, miss_reason=reason)
        assert _badge_of(_html(b)) == _old != V2.VALID_EMPTY_BADGE, (card.key, card.note.now)
        _checked += 1
    assert _checked > 50, "窮舉沒有打到足夠的空態卡 —— 列舉器壞了？"


def test_count_empty_now_under_a_non_empty_state_does_not_get_11():
    """同一句 `COUNT_EMPTY_NOW` 若出現在 `UI_EMPTY` 以外的態（例：帶 `MISS_NO_INPUT` → #7），⛔ 不畫 #11。"""
    _hits = [b for b in _BUILTS
             if b[0].key == "hold.portfolio_count" and b[0].note is not None
             and b[0].note.now == P.COUNT_EMPTY_NOW and b[0].state != UI_EMPTY]
    assert _hits, "列舉器沒有打到這個組合（前提）"
    for b in _hits:
        assert _badge_of(_html(b)) != V2.VALID_EMPTY_BADGE
