"""16 盞燈卡（`detail.*`）的「▸ 詳細」摺疊區（客戶 2026-09-25 核可線框）。

📌 2026-09-25 客戶選 (b)：~~原生 `<details>`~~（iPhone 點了沒反應）→ 純 CSS 開關：
   `<div class="blk-fold">` 內依序 ＝ 隱藏 `<input type="checkbox" class="blk-fold-i" id=…>`
   ＋ `<label class="blk-fold-s" for=…>▸ 詳細</label>` ＋ `<div class="blk-fold-b">`（摺起來的列）。

守的東西：
  1. live 卡：「命中來源」「門檻出處」「這條線在看什麼」三列**只**在 `.blk-fold-b` 內；
     「變化方向」「門檻帶」在外（卡面）。
  2. 非 live 卡：「現在」「為什麼」「去哪補」留卡面、⛔ 不摺；degraded 的「現值」也留卡面。
  3. 原本卡面上的每一段文字都還在（只換位置，⛔ 沒有刪字）。
  4. 非 `detail.*` 的卡、以及 `card_html` 不給 `folded_facts` 時，逐 byte 不變。
  5. 開關：label 文字「▸ 詳細」、⛔ 無 `checked`（預設收合）、`for` ＝ input `id`
     ＝ `fold_dom_id(卡 key)`（16 張互不相同）、input 排在 body 之前（`~` 才選得到）。
  6. `page_css()` 真的有「body 預設隱藏、`:checked ~` 才顯示」兩條規則。
  7. 2026-09-26 a11y（客戶核可）：開關可鍵盤聚焦（⛔ display:none／tabindex=-1／disabled）、
     可及名稱只引用畫面上既有的字（`aria-labelledby` ＝ 開關字 ＋ 卡標題）、
     `aria-controls` 指向 body、⛔ 無寫死的 `aria-expanded`；拿掉新增屬性後與改前逐 byte 相同。
"""
from __future__ import annotations

import re

import pytest

from shared.macro_buckets import BUCKET_DANGER_SPECS
from src.compute.macro.lamp_direction import compute_lamp_direction
from src.ui.views import page_today as P
from src.ui_v2 import markup as M

FOLD_KEYS = ("命中來源", "門檻出處", "這條線在看什麼")
_FOLD_OPEN = '<div class="blk-fold">'
#: body 開標籤的**前綴**（2026-09-26 a11y 起 body 帶 `id=` 供 `aria-controls` 引用 ⇒ 不再寫死 `>`）。
_BODY_OPEN = '<div class="blk-fold-b"'
_DIV_TOKEN = re.compile(r"<div\b[^>]*>|</div>")
_FOLD_HEAD_RE = re.compile(
    r'^<div class="blk-fold">'
    r'<input type="checkbox" class="blk-fold-i" id="(?P<id>[^"]*)"(?P<iattr>[^>]*)>'
    r'<label class="blk-fold-s" id="(?P<lid>[^"]*)" for="(?P<for>[^"]*)">(?P<label>.*?)</label>'
    r'<div class="blk-fold-b" id="(?P<bid>[^"]*)">', re.S)


def _span(key: str) -> str:
    return f'<span class="blk-fact-k">{key}</span>'


def _balanced(html: str, start: int) -> int:
    """`html[start:]` 以 `<div…>` 開頭 → 回傳與它配對的 `</div>` 之後的位置。"""
    depth = 0
    for m in _DIV_TOKEN.finditer(html, start):
        depth += -1 if m.group(0) == "</div>" else 1
        if depth == 0:
            return m.end()
    raise AssertionError("div 未閉合")


def _fold_parts(html: str) -> dict:
    """→ {outside, fold, body, id, for, label, iattr}。恰好一個摺疊區，否則炸。"""
    assert html.count(_FOLD_OPEN) == 1, f"應恰好一個摺疊區，實得 {html.count(_FOLD_OPEN)}"
    assert "<details" not in html and "<summary" not in html
    i = html.index(_FOLD_OPEN)
    j = _balanced(html, i)
    fold = html[i:j]
    head = _FOLD_HEAD_RE.match(fold)
    assert head, f"摺疊區結構不對：{fold[:200]!r}"
    b = fold.index(_BODY_OPEN)
    b_end = _balanced(fold, b)
    # body 是摺疊區**最後一個**子節點（後面只剩摺疊區自己的 `</div>`）
    assert fold[b_end:] == "</div>", fold[b_end:]
    body = fold[fold.index(">", b) + 1:b_end - len("</div>")]
    return dict(outside=html[:i] + html[j:], fold=fold, body=body,
                id=head["id"], **{"for": head["for"]},
                label=head["label"], iattr=head["iattr"],
                lid=head["lid"], bid=head["bid"])


def _split(html: str) -> tuple[str, str]:
    """→ (摺疊區外, 被開關控制的 body 內)。"""
    p = _fold_parts(html)
    return p["outside"], p["body"]


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
    # 2026-09-26：16 盞都有「變化方向」列（沒歷史的顯示無資料）
    dirs = {k: compute_lamp_direction(k, None) for k in P.LAMP_DIRECTION_KEYS}
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
        if (key.split(".", 1)[1] in P.LAMP_DIRECTION_KEYS
                and tile.card.state in (P.UI_LIVE, P.UI_DEGRADED)):
            assert _span(P.LAMP_DIRECTION_FACT_KEY) in outside
            assert _span(P.LAMP_DIRECTION_FACT_KEY) not in inside

    def test_toggle_collapsed_by_default(self):
        html = P.v2_card_html(_live_tiles()["detail.margin"])
        p = _fold_parts(html)
        assert "checked" not in p["iattr"] and "checked" not in p["fold"]
        assert p["label"] == "▸ 詳細" == M.FOLD_SUMMARY_TEXT
        # ⛔ 摺疊靠 CSS：無 script、無任何 on* 事件屬性
        assert "<script" not in html and not re.search(r"\bon[a-z]+=", html)

    @pytest.mark.parametrize(
        "key", sorted(k for k in P.V2_CARD_BLOCKS if k.startswith("detail.")))
    def test_label_for_matches_input_id(self, key):
        p = _fold_parts(P.v2_card_html(_live_tiles()[key]))
        assert p["id"] == p["for"] == M.fold_dom_id(key)
        assert re.fullmatch(r"[a-z0-9-]+", p["id"])

    def test_ids_unique_and_stable_across_16_cards(self):
        ids = [_fold_parts(P.v2_card_html(t))["id"] for t in _live_tiles().values()]
        assert len(ids) == 16 and len(set(ids)) == 16
        # 決定性：再建一次（模擬 rerun）逐字相同
        again = [_fold_parts(P.v2_card_html(t))["id"] for t in _live_tiles().values()]
        assert ids == again
        # 冷啟動等非 live 態也用同一個 id（狀態變了 DOM 仍對得上）
        cold = _non_live_sets()["cold"]
        assert sorted(_fold_parts(P.v2_card_html(t))["id"] for t in cold.values()) \
            == sorted(ids)

    def test_fold_dom_id_sanitizes(self):
        assert M.fold_dom_id("detail.bias_240") == "fold-detail-bias-240"
        assert M.fold_dom_id("Detail.<X>&y") == "fold-detail-x-y"
        with pytest.raises(ValueError):
            M.fold_dom_id("..__")


class TestToggleCss:
    """開關真正靠的兩條規則。拔掉任一條 ⇒ 永遠攤開或永遠打不開。"""

    @pytest.mark.parametrize("mode", ["dark", "light"])
    def test_body_hidden_until_checked(self, mode):
        try:
            css = M.page_css(mode)
        except Exception:  # noqa: BLE001 — 該模式仍有 TBD token 時 page_css 會炸，另有測試守
            pytest.skip(f"page_css({mode!r}) 不可產出")
        compact = re.sub(r"\s+", "", css)
        assert ".blk-fold-b{display:none}" in compact
        assert ".blk-fold-i:checked~.blk-fold-b{display:block}" in compact
        # input 視覺隱藏（⛔ 不能讓一個原生 checkbox 冒出來）
        assert re.search(r"\.blk-fold-i\{[^}]*opacity:0", compact)
        # label 是觸控區
        rule = re.search(r"\.blk-fold-s\{([^}]*)\}", compact).group(1)
        for decl in ("display:block", "cursor:pointer",
                     "-webkit-tap-highlight-color:transparent", "padding-top:"):
            assert decl in rule, decl

    def test_input_precedes_body_as_sibling(self):
        p = _fold_parts(P.v2_card_html(_live_tiles()["detail.vix"]))
        fold = p["fold"]
        assert fold.index('class="blk-fold-i"') < fold.index(_BODY_OPEN)


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
            assert inside.startswith('<div class="blk-facts">') and inside.endswith("</div>")
            rows = inside[len('<div class="blk-facts">'):-len("</div>")]
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
        assert "<details" not in base and "blk-fold" not in base and "<input" not in base

    def test_card_html_folded_requires_valid_id(self):
        kw = dict(block=P.V2_CARD_BLOCKS["detail.vix"], state="live", title="t",
                  value="1", level="L", badge_n=1, folded_facts=(("a", "b"),))
        for bad in (None, "", "Fold X", 'x"><script>'):
            with pytest.raises(ValueError):
                M.card_html(**kw, fold_id=bad)
        p = _fold_parts(M.card_html(**kw, fold_id="fold-x"))
        assert p["id"] == p["for"] == "fold-x"

    def test_non_detail_cards_have_no_fold(self):
        tiles = P.build_bucket_tiles(P.MacroReadout(requested=False))
        tiles += (P.build_key_alert_tile(None, requested=False,
                                         threshold_scanned=False, error=""),)
        assert tiles
        for t in tiles:
            assert not t.card.key.startswith("detail.")
            html = P.v2_card_html(t)
            assert "<details" not in html and "▸ 詳細" not in html
            assert "blk-fold" not in html and "<input" not in html and "<label" not in html

    def test_fold_label_rename_fails_loud(self, monkeypatch):
        monkeypatch.setattr(P, "V2_FOLDED_FACT_KEYS", frozenset({"不存在的標籤"}))
        with pytest.raises(KeyError):
            P.v2_card_html(_live_tiles()["detail.vix"])


_A11Y_ADDED_ATTR = re.compile(
    r' (?:aria-labelledby|aria-controls)="[^"]*"'
    r'|(?<=<span class="blk-title") id="[^"]*"'
    r'|(?<=<label class="blk-fold-s") id="[^"]*"'
    r'|(?<=<div class="blk-fold-b") id="[^"]*"')


class TestA11y:
    """2026-09-26 客戶核可：「▸ 詳細」鍵盤與螢幕朗讀可操作（⛔ 無 JS、⛔ 畫面不變、⛔ 無新文案）。"""

    @pytest.mark.parametrize("mode", ["dark", "light"])
    def test_input_focusable_not_removed_from_tab_order(self, mode):
        try:
            css = M.page_css(mode)
        except Exception:  # noqa: BLE001 — 同 TestToggleCss
            pytest.skip(f"page_css({mode!r}) 不可產出")
        compact = re.sub(r"\s+", "", css)
        rules = re.findall(r"\.blk-fold-i\{([^}]*)\}", compact)
        assert rules, "找不到 .blk-fold-i 規則"
        for rule in rules:
            # display:none / visibility:hidden 會把 input 移出 Tab 順序與無障礙樹
            assert "display:none" not in rule and "visibility:hidden" not in rule, rule
        # 鍵盤聚焦時 label 有可見框（只在 :focus-visible，滑鼠點按不觸發 ⇒ 畫面不變）
        m = re.search(r"\.blk-fold-i:focus-visible~\.blk-fold-s\{([^}]*)\}", compact)
        assert m and "outline:" in m.group(1) and "outline:none" not in m.group(1)
        # QA 2026-09-26：負的 outline-offset 會把框畫進 label 盒內、壓到「▸」字形 ⇒ ⛔ 不得為負
        off = re.search(r"outline-offset:(-?[\d.]+)px", m.group(1))
        assert off and float(off.group(1)) >= 0, m.group(1)

    @pytest.mark.parametrize(
        "key", sorted(k for k in P.V2_CARD_BLOCKS if k.startswith("detail.")))
    def test_accessible_name_reuses_visible_text_only(self, key):
        tile = _live_tiles()[key]
        html = P.v2_card_html(tile)
        p = _fold_parts(html)
        for bad in ("tabindex", "disabled", "aria-hidden", "aria-expanded", "aria-label="):
            assert bad not in p["iattr"], bad
        assert p["label"] == M.FOLD_SUMMARY_TEXT == "▸ 詳細"  # 開關字一字未改
        fid = p["id"]
        assert p["lid"] == M.fold_label_id(fid) and p["bid"] == M.fold_body_id(fid)
        m = re.search(r'aria-labelledby="([^"]*)"', p["iattr"])
        assert m and m.group(1).split() == [M.fold_label_id(fid), M.fold_title_id(fid)]
        assert f'aria-controls="{M.fold_body_id(fid)}"' in p["iattr"]
        # labelledby 引用的標題元素真的在同一張卡上，而且文字就是卡標題（⛔ 無新文案）
        t = re.search(rf'<span class="blk-title" id="{M.fold_title_id(fid)}">(.*?)</span>', html)
        assert t and t.group(1) == M._esc(P.v2_plain(tile.card.label))

    def test_all_ids_unique_and_stable_per_run(self):
        def ids():
            page = "".join(P.v2_card_html(t) for t in _live_tiles().values())
            return re.findall(r'\bid="([^"]*)"', page)
        got = ids()
        assert len(got) == 16 * 4 and len(set(got)) == len(got)   # input／label／title／body
        assert got == ids()                                        # rerun 逐字相同

    def test_sub_ids_cannot_collide_with_any_fold_id(self):
        for fid in ("fold-a", "fold-a-t", "fold-a-s", "fold-a-b"):
            for sub in (M.fold_label_id(fid), M.fold_title_id(fid), M.fold_body_id(fid)):
                assert not re.fullmatch(r"[a-z0-9-]+", sub), sub   # 合法 fold_id 不可能長這樣

    def test_markup_identical_to_before_once_a11y_attrs_removed(self):
        """拿掉本次新增的屬性 ⇒ 與改前的結構逐 byte 相同（展開內容、開關字、順序都沒動）。"""
        for tile in _live_tiles().values():
            html = P.v2_card_html(tile)
            fid = M.fold_dom_id(tile.card.key)
            legacy = _A11Y_ADDED_ATTR.sub("", html)
            assert "aria-labelledby" not in legacy and "aria-controls" not in legacy
            assert f"{fid}_" not in legacy
            assert (f'<div class="blk-fold"><input type="checkbox" class="blk-fold-i" id="{fid}">'
                    f'<label class="blk-fold-s" for="{fid}">▸ 詳細</label>'
                    '<div class="blk-fold-b"><div class="blk-facts">') in legacy
            assert legacy.count('<span class="blk-title">') == 1

    def test_unfolded_card_gets_no_a11y_ids(self):
        kw = dict(block=P.V2_CARD_BLOCKS["detail.vix"], state="live", title="t<",
                  value="1", level="L", badge_n=1, facts=(("a", "b&"),))
        base = M.card_html(**kw)
        assert not re.search(r'\bid="', base)          # 標題⛔ 掛 id
        assert "aria-labelledby" not in base and "aria-controls" not in base
