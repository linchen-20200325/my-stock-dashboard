"""`src/ui_v2/blocks.py` —— 「依 block 查密度階」登記處（客戶 2026-09-25 裁示 1）。

守的是三件事：
  1. **同一套機制**：每個 block 的階仍由「它所在的層」經 `components.tier_for_layer()` 推出；
     登記處只做分派，⛔ 沒有自己的 tier 值、⛔ 沒有覆寫參數。
  2. **「🚦 今天」逐 byte 不變**：`markup.card_html()` 改經登記處查階後，
     today 每個 block × 每個狀態 × 每顆徽章的輸出，與「直接問 `page_today.tier_for_block`」
     （改動前的路徑）完全相同；`page_css()` 也不因登記了找標的頁而多產任何一條規則。
  3. **未知 block 照炸**（⛔ 不猜一階）。
"""
from __future__ import annotations

import inspect
import itertools
from types import MappingProxyType, SimpleNamespace

import pytest

from src.ui_v2 import blocks, components, markup, page_find, page_today

TODAY_BLOCKS = tuple(b for L in page_today.LAYERS for b in L["blocks"])
FIND_BLOCKS = tuple(b for L in page_find.LAYERS for b in L["blocks"])
V2_STATES = ("live", "loading", "idle", "degraded", "unwired", "failed", "error",
             "missing", "empty", "na", "partial")


# ── 1. 查表 ───────────────────────────────────────────────────────
@pytest.mark.parametrize("block", TODAY_BLOCKS)
def test_today_blocks_answer_exactly_as_page_today(block):
    assert blocks.tier_for_block(block) == page_today.tier_for_block(block)
    assert blocks.BLOCK_PAGE[block] == "today"


def test_find_blocks_are_registered_with_spec_tiers():
    """UI_PAGE_FIND.md ① 表：n1 → t1；n2 → t2；葉2 n5 → t2（取核心卡層）。"""
    expected = {
        "find.screen_form": "t1",
        "find.screen_result": "t2",   # 規格 key 為 find.screen_summary（據實登記，未改名）
        "find.heatmap": "t2",
        "find.sector_flow": "t2",
    }
    assert set(FIND_BLOCKS) == set(expected)
    for block, tier in expected.items():
        assert blocks.tier_for_block(block) == tier
        assert page_find.tier_for_block(block) == tier
        assert blocks.BLOCK_PAGE[block] == "find"


def test_find_tiers_are_derived_from_layers_not_hand_picked():
    for layer in page_find.LAYERS:
        assert layer["tier"] == components.tier_for_layer(layer["layer"])
        for block in layer["blocks"]:
            assert page_find.tier_for_block(block) == components.tier_for_layer(layer["layer"])


def test_n5_borrows_the_core_card_layer_and_layer_5_still_raises():
    n5 = [L for L in page_find.LAYERS if L["wireframe_n"] == "n5"]
    assert len(n5) == 1 and n5[0]["layer"] == page_find.N5_DENSITY_LAYER == 2
    with pytest.raises(ValueError):
        components.tier_for_layer(5)   # ⛔ 不得為了本頁放寬契約層


def test_find_cols_are_the_spec_values():
    assert dict(page_find.BLOCK_COLS) == {
        "find.screen_form": (3, 2, 1),
        "find.screen_result": (1, 1, 1),
        "find.heatmap": (2, 1, 1),
        "find.sector_flow": (2, 1, 1),
    }


def test_find_does_not_draw_badge_10():
    assert page_find.BADGES_NOT_ON_PAGE == frozenset({10})
    for block in FIND_BLOCKS:
        with pytest.raises(ValueError):
            markup.card_html(block=block, state="live", title="t", badge_n=10)


@pytest.mark.parametrize("fn", [blocks.tier_for_block, page_find.tier_for_block])
def test_no_override_parameter(fn):
    assert list(inspect.signature(fn).parameters) == ["block_key"]


# ── 3. 未知 block 照炸 ─────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["today.not_a_block", "find.not_a_block", "find.screen_summary", ""])
def test_unknown_block_still_raises(bad):
    with pytest.raises(KeyError):
        blocks.tier_for_block(bad)
    with pytest.raises(KeyError):
        markup.card_html(block=bad, state="live", title="t", badge_n=1)


def test_pages_stay_separate():
    """today 的查表不因登記處而認得 find 的 block（反之亦然）。"""
    for block in FIND_BLOCKS:
        with pytest.raises(KeyError):
            page_today.tier_for_block(block)
    for block in TODAY_BLOCKS:
        with pytest.raises(KeyError):
            page_find.tier_for_block(block)


def test_a_block_registered_twice_is_a_hard_error(monkeypatch):
    dup = SimpleNamespace(LAYERS=({"blocks": ("today.verdict",)},),
                          BADGES_NOT_ON_PAGE=frozenset(),
                          tier_for_block=lambda b: "t1")
    monkeypatch.setattr(blocks, "PAGES", MappingProxyType({**blocks.PAGES, "dup": dup}))
    with pytest.raises(RuntimeError, match="today.verdict"):
        blocks._build_owner()


# ── 2. 「🚦 今天」逐 byte 不變 ───────────────────────────────────
def _today_cases():
    for block, state, n in itertools.product(
            TODAY_BLOCKS, V2_STATES, sorted(page_today.BADGES_ON_PAGE)):
        yield dict(block=block, state=state, title='T<&>"\'', value="1,234 <b>",
                   level="L&", badge_n=n, facts=[("k<", "v" * 60), ("a", "b")],
                   folded_facts=[("f", "x")] if n == 1 else (),
                   fold_id="fold-x" if n == 1 else None)


def test_today_cards_are_byte_identical_to_the_direct_page_today_lookup(monkeypatch):
    """登記處路徑 vs 改動前路徑（直接問 `page_today`）—— today 全部組合逐 byte 相同。"""
    cases = list(_today_cases())
    assert len(cases) > 500
    via_registry = [markup.card_html(**kw) for kw in cases]
    monkeypatch.setattr(markup.blocks, "tier_for_block", page_today.tier_for_block)
    monkeypatch.setattr(markup.blocks, "badges_not_on_page",
                        lambda b: page_today.BADGES_NOT_ON_PAGE)
    direct = [markup.card_html(**kw) for kw in cases]
    assert via_registry == direct


def test_page_css_is_still_derived_from_today_only():
    """登記 find 的 block ⛔ 不得讓 `page_css()` 多產任何 class（today 的樣式表輸出不變）。"""
    assert markup._BLOCK_COLS_USED == tuple(sorted(set(page_today.BLOCK_COLS.values())))
    assert markup._TIERS_ON_PAGE == tuple(
        t for t in components.CARD_TIERS
        if any(page_today.tier_for_block(b) == t for b in page_today.BLOCK_COLS))
    css = markup.page_css("dark")
    assert ".g-2-1-1" not in css, "找標的頁的 2/1/1 不該跑進 today 的樣式表"


def test_every_registered_tier_has_card_css():
    css = markup.page_css("dark")
    for block in blocks.BLOCK_PAGE:
        assert f".blk-{blocks.tier_for_block(block)}" in css


def test_find_card_uses_the_registry_tier():
    html = markup.card_html(block="find.screen_form", state="failed", title="t", badge_n=6)
    assert 'class="blk blk-t1"' in html
    html = markup.card_html(block="find.heatmap", state="idle", title="t", badge_n=3)
    assert 'class="blk blk-t2"' in html


def test_fold_truncate_false_shows_full_text_and_default_is_unchanged():
    long = "長" * (markup.FACT_VALUE_MAX_CHARS + 10)
    kw = dict(block="find.heatmap", state="idle", title="t", badge_n=3,
              folded_facts=[("k", long)], fold_id="fold-find-x")
    full = markup.card_html(**kw, fold_truncate=False)
    assert f">{long}</span>" in full and markup.FACT_VALUE_ELLIPSIS not in full
    default = markup.card_html(**kw)
    assert markup.FACT_VALUE_ELLIPSIS in default and default == markup.card_html(**kw, fold_truncate=True)
