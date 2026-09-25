"""16 盞燈卡（`detail.*`）的「▸ 詳細」摺疊區（客戶 2026-09-25 核可線框）。

守的東西：
  1. live 卡：「命中來源」「門檻出處」「這條線在看什麼」三列**只**在 `<details>` 內；
     「變化方向」「門檻帶」在外（卡面）。
  2. 非 live 卡：「現在」「為什麼」「去哪補」留卡面、⛔ 不摺；degraded 的「現值」也留卡面。
  3. 原本卡面上的每一段文字都還在（只換位置，⛔ 沒有刪字）。
  4. 非 `detail.*` 的卡、以及 `card_html` 不給 `folded_facts` 時，逐 byte 不變。
  5. `<details>` 內有 `<summary>▸ 詳細</summary>`、⛔ 無 `open`（預設收合）。
"""
from __future__ import annotations

import re

import pytest

from shared.macro_buckets import BUCKET_DANGER_SPECS
from src.compute.macro.lamp_direction import compute_lamp_direction
from src.ui.views import page_today as P
from src.ui_v2 import markup as M

FOLD_KEYS = ("命中來源", "門檻出處", "這條線在看什麼")
_DETAILS_RE = re.compile(r"<details\b[^>]*>(.*?)</details>", re.S)


def _span(key: str) -> str:
    return f'<span class="blk-fact-k">{key}</span>'


def _split(html: str) -> tuple[str, str]:
    """→ (摺疊區外, 摺疊區內)。恰好一個 `<details>`，否則炸。"""
    found = _DETAILS_RE.findall(html)
    assert len(found) == 1, f"應恰好一個 <details>，實得 {len(found)}"
    return _DETAILS_RE.sub("", html), found[0]


def _flat(tiles_by_bucket):
    return {t.card.key: t for ts in tiles_by_bucket.values() for t in ts}


def _kw():
    band_label, thr_text, _, l4_err = P._load_l4_labels()
    return dict(band_label=band_label, thr_text=thr_text, l4_error=l4_err)


def _readout(state: str = "ok", value_of=lambda s: float(s.yellow)):
    rd = {s.key: {"wired": True, "discriminative": True, "state": state,
                  "value": value_of(s), "reason": None, "hit_source": "TEST<&>"}
          for s in BUCKET_DANGER_SPECS}
    return P.MacroReadout(requested=True, readiness=rd)


def _live_tiles():
    dirs = {"margin": compute_lamp_direction("margin", None),
            "bias_240": compute_lamp_direction("bias_240", None),
            "ism_pmi": compute_lamp_direction("ism_pmi", None),
            "m1b_m2_gap": compute_lamp_direction("m1b_m2_gap", None)}
    return _flat(P.build_indicator_tiles(_readout(), directions=dirs, **_kw()))


def _non_live_sets():
    """冷啟動 / 失敗 / 缺值 三組非 live。"""
    cold = _flat(P.build_indicator_tiles(P.MacroReadout(requested=False), **_kw()))
    failed = _flat(P.build_indicator_tiles(
        P.MacroReadout(requested=True, error="ImportError('x')"), **_kw()))
    missing = _flat(P.build_indicator_tiles(
        _readout(state="missing", value_of=lambda s: None), **_kw()))
    return {"cold": cold, "failed": failed, "missing": missing}


def _face_labels(tile) -> set[str]:
    return {P.v2_plain(k) for k, _ in tile.facts}


class TestLiveFold:
    def test_sixteen_live_cards(self):
        tiles = _live_tiles()
        assert len(tiles) == 16
        # margin 在 SSOT 是 degraded、foreign_net 是 unwired；其餘 14 盞 live
        live = {k for k, t in tiles.items() if t.card.state == P.UI_LIVE}
        assert len(live) >= 14
        assert {"detail.bias_240", "detail.ism_pmi", "detail.vix"} <= live

    @pytest.mark.parametrize(
        "key", sorted(k for k in P.V2_CARD_BLOCKS if k.startswith("detail.")))
    def test_source_rows_only_inside_fold(self, key):
        tile = _live_tiles()[key]
        outside, inside = _split(P.v2_card_html(tile))
        present = [k for k in FOLD_KEYS if k in _face_labels(tile)]
        assert "命中來源" in present
        for k in present:
            assert _span(k) in inside, k
            assert _span(k) not in outside, k
        # 卡面保留：門檻帶（＋有方向的四盞：變化方向）
        assert _span("門檻帶") in outside and _span("門檻帶") not in inside
        if key.split(".", 1)[1] in P.LAMP_DIRECTION_KEYS:
            assert _span(P.LAMP_DIRECTION_FACT_KEY) in outside
            assert _span(P.LAMP_DIRECTION_FACT_KEY) not in inside

    def test_summary_collapsed_by_default(self):
        html = P.v2_card_html(_live_tiles()["detail.margin"])
        m = re.search(r"<details\b([^>]*)>", html)
        assert m and "open" not in m.group(1)
        assert re.search(r"<summary\b[^>]*>▸ 詳細</summary>", html)
        assert M.FOLD_SUMMARY_TEXT == "▸ 詳細"
        # ⛔ 摺疊靠原生元素：無 script、無 onclick
        assert "<script" not in html and "onclick" not in html


class TestNonLive:
    @pytest.mark.parametrize("which", ["cold", "failed", "missing"])
    def test_guide_rows_stay_on_face(self, which):
        tiles = _non_live_sets()[which]
        assert len(tiles) == 16
        for key, tile in tiles.items():
            assert tile.card.state != P.UI_LIVE
            outside, inside = _split(P.v2_card_html(tile))
            for k in (P.V2_NOW_FACT_KEY, P.V2_WHY_FACT_KEY, P.V2_GUIDE_FACT_KEY):
                assert _span(k) in outside, (key, k)
                assert _span(k) not in inside, (key, k)
            assert _span("命中來源") in inside and _span("命中來源") not in outside

    def test_degraded_keeps_value_on_face(self):
        rd = {s.key: {"wired": True, "discriminative": s.key != "margin",
                      "state": "ok", "value": float(s.yellow), "reason": None,
                      "hit_source": "TEST"} for s in BUCKET_DANGER_SPECS}
        tiles = _flat(P.build_indicator_tiles(
            P.MacroReadout(requested=True, readiness=rd),
            directions={"margin": compute_lamp_direction("margin", None)}, **_kw()))
        tile = tiles["detail.margin"]
        assert tile.card.state == P.UI_DEGRADED
        outside, inside = _split(P.v2_card_html(tile))
        for k in ("現值", P.LAMP_DIRECTION_FACT_KEY, "門檻帶",
                  P.V2_NOW_FACT_KEY, P.V2_WHY_FACT_KEY, P.V2_GUIDE_FACT_KEY):
            assert _span(k) in outside, k
        for k in FOLD_KEYS:
            if k in _face_labels(tile):
                assert _span(k) in inside and _span(k) not in outside, k


class TestNothingLost:
    def _all_tiles(self):
        yield from _live_tiles().values()
        for s in _non_live_sets().values():
            yield from s.values()

    def test_same_rows_same_order_just_relocated(self, monkeypatch):
        """摺疊版把 `<details>…</details>` 換回它的列 ⇒ 與「全攤平」版逐 byte 相同。"""
        for tile in self._all_tiles():
            folded = P.v2_card_html(tile)
            monkeypatch.setattr(P, "V2_FOLD_CARD_PREFIX", "\0never")
            flat = P.v2_card_html(tile)
            monkeypatch.undo()
            outside, inside = _split(folded)
            rows = re.sub(r"^<summary\b[^>]*>.*?</summary>"
                          r'<div class="blk-facts">(.*)</div>$', r"\1", inside, flags=re.S)
            # 所有列（含 escape 後的內容）一列不少、字一個不差
            flat_rows = re.findall(r'<div class="blk-fact">.*?</div>', flat)
            new_rows = re.findall(r'<div class="blk-fact">.*?</div>', outside + rows)
            assert sorted(flat_rows) == sorted(new_rows), tile.card.key

    def test_escaped(self):
        html = P.v2_card_html(_live_tiles()["detail.vix"])
        _, inside = _split(html)
        assert "TEST&lt;&amp;&gt;" in inside and "TEST<&>" not in html


class TestUntouched:
    def test_card_html_default_has_no_fold(self):
        kw = dict(block=P.V2_CARD_BLOCKS["detail.vix"], state="live", title="t<",
                  value="1", level="L", badge_n=1, facts=(("a", "b&"),))
        base = M.card_html(**kw)
        assert base == M.card_html(**kw, folded_facts=())
        assert "<details" not in base

    def test_non_detail_cards_have_no_fold(self):
        tiles = P.build_bucket_tiles(P.MacroReadout(requested=False))
        tiles += (P.build_key_alert_tile(None, requested=False,
                                         threshold_scanned=False, error=""),)
        assert tiles
        for t in tiles:
            assert not t.card.key.startswith("detail.")
            html = P.v2_card_html(t)
            assert "<details" not in html and "▸ 詳細" not in html

    def test_fold_label_rename_fails_loud(self, monkeypatch):
        monkeypatch.setattr(P, "V2_FOLDED_FACT_KEYS", frozenset({"不存在的標籤"}))
        with pytest.raises(KeyError):
            P.v2_card_html(_live_tiles()["detail.vix"])
