"""葉1 ③ 三欄摘要「風險」格接上指標危險度（2026-09-26）。

客戶 2026-09-16 裁示（`UI_PAGE_TODAY.md` ③「3 卡歸位」已決段，逐字）：
「位階 ← summary.regime（既有）／動能 ← 未接線（exposure 不是動能，不搬）
／風險 ← danger（對得上，直接對映）」。契約 `src/ui_v2/page_today.py::SUMMARY_COLUMNS`
「風險」列 `source="verdict.danger", wired=True`。

本檔守的五件事：
1. 「風險」格與卡② `verdict.danger` **同一份讀數、同一段文案**（只差 key 與標題）——
   ⛔ 沒有第二份文案；
2. 四態徽章：idle #3（灰）／live #1／failed #6（紅）／算過但全灰 → 與卡② 同一顆；
3. **冷啟動是灰，⛔ 不是紅**；
4. **逐格獨立判態**（④A「一格壞不染色另兩格」）：危險度壞掉不碰位階／動能，
   位階壞掉也不碰風險；「動能」維持未接線；
5. 畫面端真的走 `build_summary_tiles()`（拔掉接線 ⇒ 本檔轉紅；fast lane 見 5b 行為版）。
"""
from __future__ import annotations

import dataclasses
import itertools

import pytest

from shared.regime_arbiter import SOURCE_UNLOADED
from shared.ui_state import (
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import build_today_blocks
from src.ui.views import page_today as P
from src.ui_v2 import page_today as v2_page

#: L4 `macro_v2_cards.BAND_META` 的形狀（同 `tests/test_p01_today_view.py` 的替身）。
BANDS = {"green": ("綠", "#0ca30c"), "yellow": ("黃", "#fab219"),
         "red": ("紅", "#d03b3b"), "gray": ("無資料", "#8a8e96")}

LIVE_REGIME = {"regime": "bull", "light": "🟢", "source": "warroom",
               "is_loaded": True}
COLD_REGIME = {"regime": "unknown", "light": "⬜", "source": SOURCE_UNLOADED,
               "is_loaded": False}

#: 危險度的四種讀數（`_load_danger()` 的三個回傳 ＋ 五桶 gate 旗標）。
DANGER_SCENARIOS: dict[str, dict] = {
    "idle":   dict(danger=None, danger_error="", danger_requested=False),
    "live":   dict(danger=("yellow", "5 桶黃　·　最差是「長期」黃"),
                   danger_error="", danger_requested=True),
    "failed": dict(danger=None, danger_error="RuntimeError('boom')",
                   danger_requested=True, danger_source=P.SRC_DANGER),
    "failed_upstream": dict(danger=None, danger_error="RuntimeError('five')",
                            danger_requested=True,
                            danger_source=P.SRC_FIVE_BUCKET),
    "empty":  dict(danger=("gray", "0 桶有資料"), danger_error="",
                   danger_requested=True),
}

REGIME_SCENARIOS: dict[str, dict] = {
    "cold": dict(macro_state=COLD_REGIME, macro_error=None),
    "live": dict(macro_state=LIVE_REGIME, macro_error=None),
    "failed": dict(macro_state=None, macro_error="RuntimeError('regime')"),
}


def _summary_cards(**regime_kw):
    _blocks = {_b.key: _b for _b in build_today_blocks(**regime_kw)}
    return _blocks["today.summary"].cards


def _summary(regime="cold", danger="idle", **extra):
    _kw = dict(DANGER_SCENARIOS[danger])
    _kw.setdefault("danger_source", P.SRC_DANGER)
    _kw.update(extra)
    return {_t.card.key: _t for _t in P.build_summary_tiles(
        _summary_cards(**REGIME_SCENARIOS[regime]),
        band_zh_color=BANDS, l4_error="", **_kw)}


def _verdict_danger(danger="idle"):
    _kw = dict(DANGER_SCENARIOS[danger])
    _kw.setdefault("danger_source", P.SRC_DANGER)
    _tiles = P.build_verdict_tiles(
        alloc=None, alloc_error="", regime=COLD_REGIME, regime_error="",
        band_zh_color=BANDS, l4_error="", **_kw)
    return next(_t for _t in _tiles if _t.card.key == "verdict.danger")


# ══════════════════════════════════════════════════════════════════
# 1. 同一份讀數、同一段文案（⛔ 沒有第二份）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("danger", sorted(DANGER_SCENARIOS))
def test_risk_cell_is_verdict_danger_with_only_key_and_label_swapped(danger):
    """「風險」格 ＝ 卡② 換 key 與標題；state / value / note / 燈號 / facts 逐欄相同。"""
    _risk = _summary(danger=danger)[P.SUMMARY_RISK_KEY]
    _card2 = _verdict_danger(danger)
    _expected = dataclasses.replace(
        _card2, card=dataclasses.replace(
            _card2.card, key=_risk.card.key, label=_risk.card.label))
    assert _risk == _expected


def test_risk_cell_keeps_the_tab_today_key_and_label():
    """⛔ 不新造標題字串：key / label 就是 `tab_today` 那一格自己的。"""
    _card = next(_c for _c in _summary_cards(**REGIME_SCENARIOS["cold"])
                 if _c.key == P.SUMMARY_RISK_KEY)
    _risk = _summary()[P.SUMMARY_RISK_KEY]
    assert (_risk.card.key, _risk.card.label) == (_card.key, _card.label) == (
        "summary.risk", "風險")


def test_contract_column_points_at_verdict_danger():
    """契約層「風險」列宣稱接 `verdict.danger` —— 本頁接的就是它（見上一組）。"""
    _risk_col = next(_c for _c in v2_page.SUMMARY_COLUMNS if _c["name"] == "風險")
    assert _risk_col["source"] == "verdict.danger" and _risk_col["wired"] is True
    assert _summary()[P.SUMMARY_RISK_KEY].card.label == _risk_col["name"]


# ══════════════════════════════════════════════════════════════════
# 2. 四態徽章 ＆ 3. 冷啟動是灰
# ══════════════════════════════════════════════════════════════════
def test_idle_is_grey_badge_3_not_red():
    _t = _summary(danger="idle")[P.SUMMARY_RISK_KEY]
    assert _t.card.state == UI_IDLE
    assert P.v2_card_badge_n(_t.card) == 3
    assert "未評估" not in (_t.card.note.now or "")  # 不把「還沒叫」講成判決


def test_live_is_badge_1_with_the_danger_readout():
    _t = _summary(danger="live")[P.SUMMARY_RISK_KEY]
    assert _t.card.state == UI_LIVE
    assert P.v2_card_badge_n(_t.card) == 1
    assert _t.card.value == DANGER_SCENARIOS["live"]["danger"][1]
    assert _t.signal_text == "黃"


@pytest.mark.parametrize("danger", ["failed", "failed_upstream"])
def test_failed_is_badge_6_and_points_at_code(danger):
    _t = _summary(danger=danger)[P.SUMMARY_RISK_KEY]
    assert _t.card.state == UI_FAILED
    assert P.v2_card_badge_n(_t.card) == 6
    assert _t.card.note.where is P.EXIT_FIX_CODE


def test_computed_but_all_grey_matches_card_two_badge():
    _risk = _summary(danger="empty")[P.SUMMARY_RISK_KEY]
    _card2 = _verdict_danger("empty")
    assert _risk.card.state == _card2.card.state
    assert P.v2_card_badge_n(_risk.card) == P.v2_card_badge_n(_card2.card)
    assert P.v2_card_badge_n(_risk.card) != 6, "算過但全灰 ⛔ 不是故障"


def test_risk_cell_is_no_longer_unwired():
    for _d in DANGER_SCENARIOS:
        assert _summary(danger=_d)[P.SUMMARY_RISK_KEY].card.state != UI_UNWIRED


@pytest.mark.parametrize("regime,danger", list(itertools.product(
    sorted(REGIME_SCENARIOS), sorted(DANGER_SCENARIOS))))
def test_every_summary_card_renders_on_the_v2_face(regime, danger):
    """每一個 `where` 都登記在 `V2_EXIT_PHRASES`（漏登 ⇒ KeyError ⇒ 紅卡）。"""
    for _t in _summary(regime=regime, danger=danger).values():
        assert _t.card.key in P.V2_CARD_KEYS
        _html = P.v2_card_html(_t)
        assert _t.card.label in _html


# ══════════════════════════════════════════════════════════════════
# 4. 逐格獨立判態
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("regime", sorted(REGIME_SCENARIOS))
def test_danger_outcome_never_touches_regime_or_momentum(regime):
    _cards = {_c.key: _c for _c in _summary_cards(**REGIME_SCENARIOS[regime])}
    for _d in DANGER_SCENARIOS:
        _tiles = _summary(regime=regime, danger=_d)
        for _k in ("summary.regime", "summary.momentum"):
            assert _tiles[_k] == P.Tile(_cards[_k]), (
                f"危險度 {_d} 染到了 {_k}")


@pytest.mark.parametrize("danger", sorted(DANGER_SCENARIOS))
def test_regime_outcome_never_touches_risk(danger):
    _risks = {_r: _summary(regime=_r, danger=danger)[P.SUMMARY_RISK_KEY]
              for _r in REGIME_SCENARIOS}
    assert len(set(map(repr, _risks.values()))) == 1


def test_momentum_stays_unwired():
    """客戶裁示「動能 ← 未接線（exposure 不是動能，不搬）」。"""
    for _d in DANGER_SCENARIOS:
        assert _summary(danger=_d)["summary.momentum"].card.state == UI_UNWIRED


def test_card_order_and_count_unchanged():
    _keys = tuple(_summary())
    assert _keys == tuple(_c.key for _c in _summary_cards(
        **REGIME_SCENARIOS["cold"])) == (
        "summary.regime", "summary.momentum", "summary.risk")


def test_summary_block_cols_unchanged():
    assert v2_page.BLOCK_COLS["today.summary"] == (1, 1, 1)


# ══════════════════════════════════════════════════════════════════
# 5. 畫面端真的接上（拔掉接線 ⇒ 轉紅）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
@pytest.mark.parametrize("mode", ["cold", "live"])
def test_page_renders_the_wired_risk_cell(tmp_path, mode):
    """整頁 mount：「風險」格畫的是危險度，⛔ 不再是「風險尚未接線」。"""
    import textwrap

    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_risk_view.py"
    _script.write_text(textwrap.dedent(f"""
        from shared.macro_buckets import BUCKET_DANGER_SPECS
        from src.ui.views import page_today as P
        # ⚠️ AppTest 與 pytest 同一個行程、同一份 `sys.modules` ⇒ 換掉的 loader
        #    一定要還原，否則會漏到後面的測試（實測：漏到 test_page_mounts_clean）。
        _orig = P.load_macro_readout
        if {mode!r} == "live":
            _rd = {{s.key: {{"wired": True, "discriminative": True, "state": "ok",
                            "value": float(s.yellow), "reason": None,
                            "hit_source": "T"}} for s in BUCKET_DANGER_SPECS}}
            P.load_macro_readout = lambda _s: P.MacroReadout(
                requested=True, readiness=_rd)
        try:
            P.render_page_today()
        finally:
            P.load_macro_readout = _orig
    """), encoding="utf-8")
    _at = AppTest.from_file(str(_script), default_timeout=120)
    _at.run()
    assert not _at.exception, _at.exception
    _cards = [_m.value for _m in _at.markdown if 'class="blk' in _m.value]
    _risk = [_h for _h in _cards if ">風險<" in _h]
    assert len(_risk) == 1, "「風險」格沒畫出來或畫了兩張"
    assert "風險尚未接線" not in "\n".join(_m.value for _m in _at.markdown)
    if mode == "cold":
        assert "指標危險度：尚未載入" in _risk[0]
        assert "取得失敗" not in _risk[0], "冷啟動 ⛔ 不得是紅卡"
        # QA 突變 M2b（畫面端把 `danger_requested` 寫死成 True）會把冷啟動畫成
        # #7「缺漏 · 可重跑」—— 冷啟動只准是 #3 灰（還沒叫 ≠ 叫了沒資料）。
        assert "bdg bdg-3" in _risk[0], "冷啟動的風險格必須是 #3 尚未載入"
        assert "bdg-7" not in _risk[0], "冷啟動 ⛔ 不得畫成 #7 缺漏"
    else:
        assert "bdg bdg-1" in _risk[0] and "運作中" in _risk[0]
        # QA 突變 M6（畫面端漏傳 `band_zh_color`）會讓燈號頻道無聲消失。
        # 中文取 L4 SSOT 本身（⛔ 不手抄「黃」）；harness 的 16 盞燈全落在黃線上。
        from src.ui.render.macro_v2_cards import BAND_META
        _zh = BAND_META["yellow"][0]
        assert _zh and f'<div class="blk-lvl">{_zh}</div>' in _risk[0], (
            "live 風險格的燈號頻道（L4 BAND_META 中文）沒畫出來")


# ══════════════════════════════════════════════════════════════════
# 5b. 畫面端真的接上 —— **行為版**快速守衛（fast lane）
#
# 📌 2026-09-26 QA 補洞：**取代**原本的 `test_render_path_uses_the_wired_builder`
# （比對 `inspect.getsource` 的字串，含換行與縮排）。取代理由（實測，非推論）：
#   · 把 `build_summary_tiles(\n            _summary.cards,` 收成一行（無害重排）⇒ 它轉紅；
#   · 把 `danger_requested` 寫死 True、漏傳 `band_zh_color`、吞掉 `danger_error`
#     （真回歸）⇒ 它全綠 —— 它唯一抓得到的「退回 `_tiles_of_cards`」，本組也抓得到。
# 本組實際跑一次 `render_page_today()`：所有 loader 注入、`st` 換成假物件、
# `_render_tiles` 換成錄影機，逐態比對「畫面收到的風險格」＝ 純 builder 的產出。
# ══════════════════════════════════════════════════════════════════
def _drive_page(monkeypatch, danger: str) -> dict:
    """跑一次整頁 render（無 Streamlit runtime），回 `{card.key: Tile}`（畫面實際收到的）。"""
    from unittest import mock

    _sc = DANGER_SCENARIOS[danger]
    _requested = _sc["danger_requested"]
    _src = _sc.get("danger_source", "") if _sc["danger_error"] else ""
    _drawn: list = []

    _fake_st = mock.MagicMock(name="st")
    _fake_st.session_state = {}
    _fake_st.tabs.side_effect = lambda labels: [mock.MagicMock() for _ in labels]
    monkeypatch.setattr(P, "st", _fake_st)
    monkeypatch.setattr(P, "_inject_v2_css", lambda: None)
    monkeypatch.setattr(P, "_render_update_form", lambda _s: None)
    monkeypatch.setattr(P, "section_header", lambda *a, **k: None)
    monkeypatch.setattr(P, "render_note", lambda *a, **k: None)
    monkeypatch.setattr(P, "load_macro_readout",
                        lambda _s: P.MacroReadout(requested=_requested))
    monkeypatch.setattr(P, "_load_l4_labels", lambda: (None, None, BANDS, ""))
    monkeypatch.setattr(P, "_load_allocation", lambda: (None, ""))
    monkeypatch.setattr(P, "_load_regime", lambda: (COLD_REGIME, ""))
    monkeypatch.setattr(P, "_load_danger",
                        lambda _r: (_sc["danger"], _sc["danger_error"], _src))
    monkeypatch.setattr(P, "_load_key_alerts", lambda _s: (None, False, ""))
    monkeypatch.setattr(P, "_load_lamp_directions", lambda _s=None: {})
    monkeypatch.setattr(P, "_render_tiles",
                        lambda tiles, cols=None: _drawn.extend(tiles))
    P.render_page_today()
    _risk_n = sum(_t.card.key == P.SUMMARY_RISK_KEY for _t in _drawn)
    assert _risk_n == 1, f"「風險」格應恰畫一次，實際 {_risk_n} 次"
    return {_t.card.key: _t for _t in _drawn}


def _expected_risk(danger: str):
    _sc = DANGER_SCENARIOS[danger]
    _src = _sc.get("danger_source", "") if _sc["danger_error"] else ""
    return {_t.card.key: _t for _t in P.build_summary_tiles(
        _summary_cards(**REGIME_SCENARIOS["cold"]),
        danger=_sc["danger"], danger_error=_sc["danger_error"],
        danger_requested=_sc["danger_requested"], danger_source=_src,
        band_zh_color=BANDS, l4_error="")}[P.SUMMARY_RISK_KEY]


@pytest.mark.parametrize("danger", sorted(DANGER_SCENARIOS))
def test_render_path_draws_the_wired_risk_tile(monkeypatch, danger):
    _risk = _drive_page(monkeypatch, danger)[P.SUMMARY_RISK_KEY]
    assert _risk == _expected_risk(danger)
    assert _risk.card.state != UI_UNWIRED


@pytest.mark.parametrize("danger,state,badge", [
    ("idle", UI_IDLE, 3), ("live", UI_LIVE, 1),
    ("failed", UI_FAILED, 6), ("failed_upstream", UI_FAILED, 6),
])
def test_render_path_risk_tile_state_and_badge(monkeypatch, danger, state, badge):
    """直接釘「畫面收到的」狀態與徽章（⛔ 只靠 builder 等式的話，兩邊一起錯看不出來）。"""
    _risk = _drive_page(monkeypatch, danger)[P.SUMMARY_RISK_KEY]
    assert _risk.card.state == state
    assert P.v2_card_badge_n(_risk.card) == badge
    if danger == "live":
        assert _risk.signal_text == "黃"


def test_render_path_risk_equals_card_two_on_the_same_page(monkeypatch):
    """同一輪畫面上，「風險」格與卡② 是同一份讀數（只差 key / 標題）。"""
    _tiles = _drive_page(monkeypatch, "live")
    _risk, _card2 = _tiles[P.SUMMARY_RISK_KEY], _tiles["verdict.danger"]
    assert _risk == dataclasses.replace(_card2, card=dataclasses.replace(
        _card2.card, key=_risk.card.key, label=_risk.card.label))
