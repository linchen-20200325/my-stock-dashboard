"""WT 測試組｜test-first 契約 B：元件（`src/ui_v2/components.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/` 尚不存在，
   本檔因此**應該是紅燈（ModuleNotFoundError）** —— 紅燈即正確結果。

唯一資料來源：`docs/v2/spec/UI_COMPONENTS.md`
（每條 assert 旁標 `# UI_COMPONENTS.md <章節名>`；⛔ 不寫行號 —— CLAUDE.md §8.2.A.0 規則 1）。
顏色／字級／間距的 SSOT 在 `UI_TOKENS.md`（UI_COMPONENTS.md §0 SSOT 宣告 ①）⇒ 本層一律存**token 名**
（如 `"--rule-2"`），⛔ 不得把 hex 複製進元件表（那會製造第二個真相源）。
⛔ 未引用 `src/ui/` 既有檔案、未引用舊原型。⛔ 不 import streamlit。

────────────────────────────────────────────────────────────────────
實作組必須提供：`src/ui_v2/components.py`
────────────────────────────────────────────────────────────────────
`CARD_BASE : Mapping[str, str]`
    `.blk` 基準：`background` / `border_width_px` / `border_style` / `border_color` / `radius_px`。

`CARD_TIERS : Mapping[str, Mapping]`
    四階密度，鍵恰為 `"t1" "t2" "t3" "t4"`。每階欄位：
      `padding_px`        : tuple[float, float]   # (上下, 左右)
      `padding_mobile_px` : tuple[float, float] | None  # ≤640 覆寫；規格只定義 t1
      `radius_px`         : float
      `border_width_px`   : float
      `border_style`      : "solid" | "dashed"
      `border_color`      : token 名
      `shadow`            : None                  # ⛔ 四階一律 None，不得發明陰影
      `margin_top_px`     : float
      `title_px`          : float
      `title_weight`      : int
      `title_color`       : token 名 | None
      `badge_size`        : "b1".."b4"

`SBADGE_SIZES : Mapping[str, Mapping]`
    卡片主徽章四尺寸 `b1`~`b4`：`font_px` / `padding_px` / `min_height_px`
    / `border_width_px` / `radius_px`。

`BADGE_BASE : Mapping`
    10 種徽章共用幾何：`gap_px` / `radius_px` / `padding_px` / `font_px`
    / `font_weight` / `white_space` / `border_width_px` / `border_style`。

`BADGES : tuple[Mapping, ...]`
    **恰 10 枚**，依 `n` 升冪。每枚欄位：
      `n`(1..10) / `name` / `state_const` / `miss_reason`(str|None)
      / `bg` / `fg` / `border_width_px` / `border_style` / `border_color`
      / `icon`(必填非空) / `text`(必填非空)
    ⚠️ `state_const` 存的是**常數名字串**（`"UI_LIVE"`…），⛔ 不是重新定義它的值 ——
    七態 SSOT 是既有 L0 `shared/ui_state.py`
    （UI_COMPONENTS.md §2「基底＝既有 L0 `shared/ui_state.py` 七態 SSOT」），
    `src/ui_v2/` ⛔ 不得再宣告一份 `UI_LIVE`/`UI_IDLE`/… 常數。

`badge(n: int) -> Mapping`  取第 n 枚；n 不在 1..10 → `raise KeyError`。

`BUTTONS : Mapping[str, Mapping]`
    五類，鍵：`primary_cta` / `secondary_explain` / `secondary_evidence`
    / `text` / `disabled`。欄位：`min_height_px` / `min_width_px`(僅展開佐證)
    / `padding_px` / `font_px` / `font_weight` / `radius_px` / `bg`
    / `border_width_px` / `border_style` / `border_color` / `fg`。

`FOCUS_RING : Mapping`
    `outline_width_px` / `outline_style` / `outline_color` / `outline_offset_px`。

`BREAKPOINTS : Mapping[str, int]`
    `mobile_max_px` / `tablet_min_px` / `tablet_max_px` / `desktop_min_px`。

`MAX_COLS : int`  ＝ 3（硬夾）。

`tier_for_layer(layer: int) -> str`
    四層密度**由層序自動掛**，⛔ 非逐塊手選
    （UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」）。
    `0`（葉外 chrome）→ `"t3"`；`1..4` → `"t1".."t4"`；其餘 → `raise ValueError`。

`resolve_cols(cols: tuple[int, int, int], viewport_px: int) -> int`
    `cols` 依線框記法 `(桌機, 平板, 手機)`；回傳該視窗寬下的欄數，並夾在 `MAX_COLS`。
"""
from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from src.ui_v2 import components


TIER_KEYS = ("t1", "t2", "t3", "t4")


# ══════════════════════════════════════════════════════════════════
# B-1 卡片四階密度（UI_COMPONENTS.md §1 四層密度表）
# ══════════════════════════════════════════════════════════════════
def test_card_tiers_are_exactly_four():
    assert tuple(components.CARD_TIERS) == TIER_KEYS  # UI_COMPONENTS.md §1 四層密度表


@pytest.mark.parametrize(
    "tier, padding, border_width, border_style, margin_top, title_px",
    [
        ("t1", (15.0, 17.0), 2.0, "solid", 15.0, 17.5),   # §1 四層密度表「t1 結論」列
        ("t2", (10.0, 12.0), 1.0, "solid", 10.0, 14.5),   # §1 四層密度表「t2 核心」列
        ("t3", (6.0, 9.0), 1.0, "solid", 6.0, 13.0),      # §1 四層密度表「t3 操作」列
        ("t4", (5.0, 9.0), 1.0, "dashed", 5.0, 12.5),     # §1 四層密度表「t4 佐證」列
    ],
)
def test_card_tier_geometry(tier, padding, border_width, border_style, margin_top, title_px):
    spec = components.CARD_TIERS[tier]
    assert tuple(spec["padding_px"]) == padding
    assert spec["border_width_px"] == border_width
    assert spec["border_style"] == border_style
    assert spec["margin_top_px"] == margin_top
    assert spec["title_px"] == title_px
    assert spec["title_weight"] == 700          # §1 四層密度表四列的「/700」
    assert spec["radius_px"] == 2.0             # §1「`.blk` 基準」行：全卡 radius 2px
    assert spec["border_color"] == "--rule-2"   # §1「`.blk` 基準」行＋四層密度表


def test_t1_has_the_only_mobile_padding_override():
    # UI_COMPONENTS.md §1 四層密度表「t1 結論」列：≤640 → `11px 12px`（其餘三階規格未給覆寫值）
    assert tuple(components.CARD_TIERS["t1"]["padding_mobile_px"]) == (11.0, 12.0)


def test_t4_title_uses_ink_2():
    # UI_COMPONENTS.md §1 四層密度表「t4 佐證」列：卡標 `12.5px/700` `--ink-2`
    assert components.CARD_TIERS["t4"]["title_color"] == "--ink-2"


@pytest.mark.parametrize("tier", TIER_KEYS)
def test_no_tier_invents_a_shadow(tier):
    """UI_COMPONENTS.md §1「層級只靠 border-width／dashed／padding 三個通道區分，
    ⛔ 不得發明陰影」；§1 四層密度表四階的陰影欄皆為「無（線框 0 命中）」。"""
    assert components.CARD_TIERS[tier]["shadow"] is None


def test_density_ladder_is_monotonic():
    """密度階梯：越往下層越緊。UI_COMPONENTS.md §1 四層密度表的四階實際值。

    ⚠️ 左右內距（17/12/9/9）與框寬（2/1/1/1）只到「**非遞增**」，
       上下內距／卡間距／卡標字級才是「**嚴格遞減**」—— 依規格實際值，⛔ 不硬拗成全嚴格。
    """
    block = [components.CARD_TIERS[t]["padding_px"][0] for t in TIER_KEYS]
    inline = [components.CARD_TIERS[t]["padding_px"][1] for t in TIER_KEYS]
    gaps = [components.CARD_TIERS[t]["margin_top_px"] for t in TIER_KEYS]
    titles = [components.CARD_TIERS[t]["title_px"] for t in TIER_KEYS]
    borders = [components.CARD_TIERS[t]["border_width_px"] for t in TIER_KEYS]

    assert all(a > b for a, b in zip(block, block[1:])), f"上下內距未嚴格遞減：{block}"
    assert all(a > b for a, b in zip(gaps, gaps[1:])), f"卡間距未嚴格遞減：{gaps}"
    assert all(a > b for a, b in zip(titles, titles[1:])), f"卡標字級未嚴格遞減：{titles}"
    assert all(a >= b for a, b in zip(inline, inline[1:])), f"左右內距不得反增：{inline}"
    assert all(a >= b for a, b in zip(borders, borders[1:])), f"框寬不得反增：{borders}"


# ══════════════════════════════════════════════════════════════════
# B-2 四層自動掛（UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛」）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "layer, tier",
    # 層 → 密度的對映出自 UI_PAGE_TODAY.md ① 四層結構表逐列
    [(0, "t3"),   # ① 四層結構表「葉外」列：走 t3（據實列出、不計入四層）
     (1, "t1"),   # ① 四層結構表「第一層 結論燈」列
     (2, "t2"),   # ① 四層結構表「第二層 核心卡」列
     (3, "t3"),   # ① 四層結構表「第三層 操作列」列
     (4, "t4")],  # ① 四層結構表「第四層 展開佐證」列
)
def test_tier_is_auto_mounted_from_layer(layer, tier):
    """UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」。"""
    assert components.tier_for_layer(layer) == tier


def test_tier_for_layer_takes_only_the_layer_and_has_no_manual_override():
    """⛔ 非逐塊手選 ⇒ 這個函式不得有 `tier=` / `density=` 之類的覆寫參數。"""
    params = inspect.signature(components.tier_for_layer).parameters
    assert list(params) == ["layer"]
    assert not {"tier", "density", "override"} & set(params)


def test_unknown_layer_raises():
    with pytest.raises(ValueError):
        components.tier_for_layer(5)


def test_components_does_not_redeclare_the_seven_state_constants():
    """UI_COMPONENTS.md §2「基底＝既有 L0 `shared/ui_state.py` 七態 SSOT…
    `_ui_kit.py` 明寫『不定義狀態，唯一真相源是它』」。

    ⇒ `src/ui_v2/` ⛔ 不得再長出第二份狀態常數（§2.1 SSOT）。
    """
    for const_name in ("UI_LIVE", "UI_LOADING", "UI_IDLE", "UI_DEGRADED",
                       "UI_UNWIRED", "UI_FAILED", "UI_EMPTY"):
        assert not hasattr(components, const_name), (
            f"{const_name} 不得在 src/ui_v2/ 重新宣告，唯一真相源是 shared/ui_state.py"
        )


# ══════════════════════════════════════════════════════════════════
# B-3 徽章 10 種（UI_COMPONENTS.md §2 徽章表 #1~#10）
# ══════════════════════════════════════════════════════════════════
BADGE_TABLE = [
    # n, name,            state_const,  miss_reason,            bg,                  fg,               bw,  style,    border_color,   icon,      text
    (1, "正常", "UI_LIVE", None, "--sig-green-bg", "--sig-green", 1.0, "solid", "--sig-green", "🟢", "運作中"),
    (2, "載入中", "UI_LOADING", None, "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⏳", "載入中"),
    (3, "還沒載入", "UI_IDLE", None, "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⬜", "尚未載入"),
    (4, "門檻已失準", "UI_DEGRADED", None, "--sig-amber-bg", "--sig-amber", 1.0, "solid", "--sig-amber", "🟠", "門檻已失準"),
    (5, "這項還沒做", "UI_UNWIRED", None, "--sig-grey-bg", "--sig-grey", 1.0, "dashed", "--rule-2", "⛔", "未接線"),
    (6, "出錯了", "UI_FAILED", None, "--sig-red-bg", "--sig-red", 1.0, "solid", "--sig-red", "🔴", "取得失敗"),
    (7, "缺漏", "UI_EMPTY", "MISS_NO_INPUT", "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⚠︎ —", "缺漏 · 可重跑"),
    (8, "結構上不適用", "UI_EMPTY", "MISS_NOT_APPLICABLE", "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "N/A", "不適用 · 重跑無效"),
    (9, "資料不完整", None, None, "--sig-neutral-bg", "--sig-neutral", 1.0, "dashed", "--sig-blue", "◧", "N／M 計入"),
    (10, "只描述不判等級", "emits_level=False", None, "--sig-blue-bg", "--sig-blue", 1.0, "solid", "--sig-blue", "◆", "只描述，不判等級"),
]


def test_badge_catalog_has_exactly_ten_entries_in_order():
    # UI_COMPONENTS.md §2 標題「徽章（10 種）」＋ §2 徽章表 #1~#10
    assert len(components.BADGES) == 10
    assert [b["n"] for b in components.BADGES] == list(range(1, 11))


@pytest.mark.parametrize("row", BADGE_TABLE, ids=[f"badge{r[0]}" for r in BADGE_TABLE])
def test_badge_row_matches_spec(row):
    n, name, state_const, miss_reason, bg, fg, bw, style, border_color, icon, text = row
    got = components.badge(n)
    assert got["name"] == name
    assert got["state_const"] == state_const
    assert got["miss_reason"] == miss_reason
    assert got["bg"] == bg
    assert got["fg"] == fg
    assert got["border_width_px"] == bw
    assert got["border_style"] == style
    assert got["border_color"] == border_color
    assert got["icon"] == icon
    assert got["text"] == text


@pytest.mark.parametrize("n", list(range(1, 11)))
def test_every_badge_carries_both_icon_and_text(n):
    """UI_COMPONENTS.md §2 硬規則「狀態色**一律配圖示＋文字，⛔ 不得只靠顏色**」
    —— 依據是 UI_TOKENS.md §A-3 實測「綠/紅在 deuteranopia 下 ΔE 3.9 無法靠色相分辨」。"""
    got = components.badge(n)
    assert isinstance(got["icon"], str) and got["icon"].strip(), f"#{n} 圖示為必填"
    assert isinstance(got["text"], str) and got["text"].strip(), f"#{n} 文字為必填"


def test_badge_7_and_8_are_separable_without_colour():
    """UI_COMPONENTS.md §2「拆 `UI_EMPTY` 的依據（#7／#8）」段引 `INDICATOR_SPEC` R-3：
    「灰系內部的『不適用』與『缺漏』必須再以符號與 tooltip 分辨，
    ⛔ 不得只靠顏色 —— 只差顏色等於把兩態併回一態」。"""
    seven, eight = components.badge(7), components.badge(8)
    assert seven["bg"] == eight["bg"] and seven["fg"] == eight["fg"], "兩者同屬灰系（前提）"
    assert seven["icon"] != eight["icon"], "⛔ 缺漏與不適用不得共用圖示"
    assert seven["text"] != eight["text"], "⛔ 文字不得省略或縮寫成同一句"
    assert seven["miss_reason"] != eight["miss_reason"]


def test_badge_9_shares_no_colour_token_with_badge_1():
    """UI_COMPONENTS.md §2「**#9『資料不完整』⛔ 不得長得像 #1『正常』**」段：
    「…與 #1 **不共用任何一個色 token**」。"""
    nine, one = components.badge(9), components.badge(1)
    nine_colours = {nine["bg"], nine["fg"], nine["border_color"]}
    one_colours = {one["bg"], one["fg"], one["border_color"]}
    assert nine_colours.isdisjoint(one_colours)
    assert nine["icon"] != one["icon"]  # §2 同段：圖示 🟢→`◧`


def test_badge_9_and_10_do_not_rely_on_the_border_alone():
    """UI_COMPONENTS.md §2「其中**圖示與文字在 `.sbadge b4`（`border:0`）下仍存在**，
    ⛔ 不得把虛線當唯一分辨通道」＋同節「`.sbadge b4` 是 `border:0`…真正扛分辨的仍是
    **圖示＋文字**」—— b4 框線整條不存在，扛分辨的是圖示＋文字。"""
    nine, ten = components.badge(9), components.badge(10)
    assert components.SBADGE_SIZES["b4"]["border_width_px"] == 0  # §2「`.sbadge` 四尺寸」b4
    assert nine["icon"] != ten["icon"]
    assert nine["text"] != ten["text"]
    # 2026-09-21 換色後前景已不同（UI_COMPONENTS.md §2「📌 #9 改引用 `--sig-neutral-bg`…
    # 可分辨性複查」段的「**據實**」行）
    assert nine["fg"] != ten["fg"]


def test_badge_base_geometry():
    # UI_COMPONENTS.md §2「幾何（線框 `.bdg`，10 種共用）」
    base = components.BADGE_BASE
    assert base["gap_px"] == 4.0
    assert base["radius_px"] == 3.0
    assert tuple(base["padding_px"]) == (1.0, 7.0)
    assert base["font_px"] == 11.5
    assert base["font_weight"] == 600
    assert base["white_space"] == "nowrap"
    assert base["border_width_px"] == 1.0
    assert base["border_style"] == "solid"


@pytest.mark.parametrize(
    "size, font_px, padding, min_height, border_width",
    [
        # 四尺寸出自 UI_COMPONENTS.md §2「卡片主徽章用 `.sbadge` 四尺寸」
        ("b1", 14.5, (10.0, 22.0), 46.0, 2.0),   # §2「`.sbadge` 四尺寸」b1
        ("b2", 12.5, (5.0, 13.0), 36.0, 1.0),    # §2 b2（框寬未覆寫→承 §2「幾何」基底 1px）
        ("b3", 11.0, (2.0, 10.0), 28.0, 1.0),    # §2 b3（同上）
        ("b4", 10.5, (2.0, 5.0), 26.0, 0.0),     # §2 b4：border 0
    ],
)
def test_sbadge_four_sizes(size, font_px, padding, min_height, border_width):
    spec = components.SBADGE_SIZES[size]
    assert spec["font_px"] == font_px
    assert tuple(spec["padding_px"]) == padding
    assert spec["min_height_px"] == min_height
    assert spec["border_width_px"] == border_width


def test_sbadge_b3_radius():
    assert components.SBADGE_SIZES["b3"]["radius_px"] == 3.0  # §2「`.sbadge` 四尺寸」b3 radius 3px


@pytest.mark.parametrize("tier, size", list(zip(TIER_KEYS, ("b1", "b2", "b3", "b4"))))
def test_card_tier_picks_its_badge_size(tier, size):
    # UI_COMPONENTS.md §2「依所在卡層 t1→b1 … t4→b4」
    assert components.CARD_TIERS[tier]["badge_size"] == size


def test_sbadge_sizes_form_a_descending_ladder():
    fonts = [components.SBADGE_SIZES[s]["font_px"] for s in ("b1", "b2", "b3", "b4")]
    heights = [components.SBADGE_SIZES[s]["min_height_px"] for s in ("b1", "b2", "b3", "b4")]
    assert all(a > b for a, b in zip(fonts, fonts[1:])), f"徽章字級未遞減：{fonts}"
    assert all(a > b for a, b in zip(heights, heights[1:])), f"徽章高度未遞減：{heights}"


def test_unknown_badge_number_raises():
    with pytest.raises(KeyError):
        components.badge(11)


# ══════════════════════════════════════════════════════════════════
# B-4 按鈕五類（UI_COMPONENTS.md §3 按鈕表）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "key, min_height, padding, font_px, font_weight, radius",
    [
        ("primary_cta", 40.0, (6.0, 16.0), 13.5, 700, 3.0),        # §3 按鈕表「主 CTA」列
        ("secondary_explain", 40.0, (6.0, 16.0), 13.5, 700, 3.0),  # §3 按鈕表「次級（說明）」列
        ("secondary_evidence", 44.0, (7.0, 9.0), 12.5, 600, 3.0),  # §3 按鈕表「次級（展開佐證）」列
        ("text", 28.0, (2.0, 11.0), 11.0, 600, 999.0),             # §3 按鈕表「文字按鈕（表頭明細）」列
        ("disabled", 40.0, (6.0, 16.0), 13.5, 500, 3.0),           # §3 按鈕表「停用態」列
    ],
)
def test_button_class_geometry(key, min_height, padding, font_px, font_weight, radius):
    spec = components.BUTTONS[key]
    assert spec["min_height_px"] == min_height
    assert tuple(spec["padding_px"]) == padding
    assert spec["font_px"] == font_px
    assert spec["font_weight"] == font_weight
    assert spec["radius_px"] == radius


def test_buttons_are_exactly_five_classes():
    assert set(components.BUTTONS) == {
        "primary_cta", "secondary_explain", "secondary_evidence", "text", "disabled",
    }  # UI_COMPONENTS.md §3 按鈕表（恰五列）


def test_evidence_button_meets_the_44px_touch_target():
    # UI_COMPONENTS.md §3 按鈕表「次級（展開佐證）」列「`min-height:44px`／`min-width:44px`」
    spec = components.BUTTONS["secondary_evidence"]
    assert spec["min_height_px"] == 44.0 and spec["min_width_px"] == 44.0


def test_primary_cta_paints_with_ink_and_hovers_to_ochre():
    # UI_COMPONENTS.md §3 按鈕表「主 CTA」列：
    # 底 `--ink`／框 2px solid `--ink`／hover → `--ochre`、字 `--paper`
    spec = components.BUTTONS["primary_cta"]
    assert spec["bg"] == "--ink"
    assert spec["border_width_px"] == 2.0 and spec["border_style"] == "solid"
    assert spec["border_color"] == "--ink"
    assert spec["hover"]["bg"] == "--ochre"
    assert spec["hover"]["border_color"] == "--ochre"
    assert spec["hover"]["fg"] == "--paper"


def test_disabled_button_is_dashed_and_grey():
    # UI_COMPONENTS.md §3 按鈕表「停用態」列：`1px dashed --rule-2`，字 `--sig-grey`，hover 無
    spec = components.BUTTONS["disabled"]
    assert spec["border_style"] == "dashed"
    assert spec["border_color"] == "--rule-2"
    assert spec["fg"] == "--sig-grey"
    assert spec.get("hover") is None


def test_focus_ring_is_a_single_global_rule():
    """UI_COMPONENTS.md §3「焦點環」行「全站唯一一條 `:focus-visible{outline:2px solid var(--focus);
    outline-offset:2px}`，⛔ 不准個別 `outline:none`」。"""
    ring = components.FOCUS_RING
    assert ring["outline_width_px"] == 2.0
    assert ring["outline_style"] == "solid"
    assert ring["outline_color"] == "--focus"
    assert ring["outline_offset_px"] == 2.0
    for key, spec in components.BUTTONS.items():
        assert spec.get("outline") != "none", f"{key} ⛔ 不得個別關掉焦點環"


# ══════════════════════════════════════════════════════════════════
# B-5 斷點三段（UI_COMPONENTS.md 前言「斷點＝`≤640 手機 / 641–880 平板 / ≥881 桌機`」）
# ══════════════════════════════════════════════════════════════════
def test_three_breakpoints():
    """UI_COMPONENTS.md 前言
    「斷點＝`≤640 手機 / 641–880 平板 / ≥881 桌機`（線框 JS `BP` 宣告版）」。

    ⚠️ 同行記載 CSS 現況是 `640 / 940 / 560`、`880`／`881` 在 `@media` 零命中
       → 那是**實作待修**，規格值就是這裡釘的這一組。
    """
    bp = components.BREAKPOINTS
    assert bp["mobile_max_px"] == 640
    assert bp["tablet_min_px"] == 641
    assert bp["tablet_max_px"] == 880
    assert bp["desktop_min_px"] == 881
    assert bp["mobile_max_px"] + 1 == bp["tablet_min_px"], "斷點之間⛔不得有空隙"
    assert bp["tablet_max_px"] + 1 == bp["desktop_min_px"], "斷點之間⛔不得有空隙"


@pytest.mark.parametrize(
    "viewport, expected",
    [(320, 1), (640, 1),      # ≤640 手機 → 取 cols 的手機欄
     (641, 2), (800, 2), (880, 2),   # 641–880 平板
     (881, 3), (1440, 3)],    # ≥881 桌機
)
def test_resolve_cols_picks_by_breakpoint(viewport, expected):
    # 線框 cols 記法為 (桌機, 平板, 手機)；此處用 `.g3` 的 3/2/1 ——
    # 現行出處＝`today.detail` 的 block cols（UI_PAGE_TODAY.md ①「第四層」段）
    # ／第二層層級網格 `LAYER_GRID_COLS[2]`（UI_PAGE_TODAY.md ①「第二層」層級網格段）。
    # ⚠️ ~~（UI_PAGE_TODAY.md ①「第二層」today.summary 條）~~ —— 2026-09-22 客戶裁示 B
    # 已把 `today.summary` 的 block cols 覆寫為 1/1/1，該處不再是 3/2/1 的出處。
    assert components.resolve_cols((3, 2, 1), viewport) == expected


def test_resolve_cols_is_clamped_at_max_cols():
    """UI_PAGE_TODAY.md ①「排列（三斷點）」段「硬夾在 `tab_today.MAX_COLS＝3` ——
    多於 3 格換行排下一列，不是加欄（`_ui_kit.py` `grid()` 的 `min(cols, MAX_COLS)`）」。"""
    assert components.MAX_COLS == 3
    assert components.resolve_cols((5, 4, 1), 1440) == 3
    assert components.resolve_cols((5, 4, 1), 800) == 3


# ═════════════════════════════════════════════════════════════════
# B-6 引用守衛 —— 指向規格的引用一律寫**章節名**，⛔ 不寫行號
# ═════════════════════════════════════════════════════════════════
#: 掃描範圍：`src/ui_v2/` 與 `tests/ui_v2/` 底下全部 `.py`。
#: ⛔ **刻意不列任何例外**（見下方 test 的 docstring）。
_UI_V2_SCAN_DIRS: tuple[str, ...] = ("src/ui_v2", "tests/ui_v2")

#: 「檔名 ＋ 冒號 ＋ 數字」—— 即行號引用。
#:
#: **副檔名範圍＝規格與原型會用到的四種**：`.md`（規格）／`.html`（原型、線框）／
#: `.js`（線框腳本，如 `wf_page_today` 那一支）／`.py`（repo 內程式碼）。
#: ⛔ **刻意不寫成「任何檔名 ＋ 冒號 ＋ 數字」** —— 那會誤傷 `localhost:8080`、
#:   時間戳、比例（`4.5:1`）這類正常寫法。
#:
#: 🆕 **2026-09-21 放寬到 `.html` / `.js` / `.py`（總管裁示，引用修復組 WX2 落地）**：
#:   - `.html` / `.js`：原型與線框**被改一樣會漂**，而舊 regex 只認 `.md` ⇒ 同一顆
#:     炸彈的另一種型號。
#:   - `.py`：依據是 `CLAUDE.md §8.2.A.0` **規則 1 的第一句**「**禁止寫行號。**」
#:     ＋ 其理由「**行號在任何一次重構後就失效**，而重構**不會**觸發本清單更新
#:     → 行號是『**保證會過期的資訊**』」，以及**規則 4**（會漂移的量測值一律標日期
#:     或不寫）。這三句**沒有限定副檔名** ⇒ `.py` 的行號引用同樣落在射程內。
#:     只守 `.md` 而放掉 `.py`，就是「留但書等於留引用點」（`CLAUDE.md §-2` 規則 6）。
#:     ⚠️ **據實記錄（2026-09-21 同日更正）**：本條原先引的是規則 1 的**第二句**
#:     「例外一律以『檔案路徑 ＋ 符號名 ＋ 模式描述』登記」，並稱其「逐字就是」
#:     `.py` 引用的通則 —— **那是 AI 總管的過度宣稱**：該句在 `CLAUDE.md` 的脈絡裡
#:     是寫給 **§8.2.A 例外清單的登記格式**，⛔ 不是寫給所有 `.py` 交叉引用。
#:     由 WX2 提出、總管採納並於同日更正為上面的第一句 ＋ 規則 4。
#:     ⚠️ **結論（`.py` 要收進來）不變，只是依據換成站得住的那一句。**
#:     📌 **為什麼這件小事非改不可**：本守衛的整個價值就是「**引用要對得起被引用的
#:     原文**」。它自己的註解若誤引憲法，它就是在示範它要防的事。
#:     （⚠️ 那第二句仍是 `.py` 的**正確寫法範本** —— `_ui_kit.py::grid()` ＋ 逐字引文
#:     就是它的形狀；⛔ 只是不得被當成「本守衛為何涵蓋 `.py`」的依據。）
#:   ⚠️ **誤傷實測（量測日 2026-09-21，WX2 單組，⛔ 未經第二組複驗）**：放寬當下，
#:     掃描範圍內只多抓到 **1 筆**，且那筆是**真的行號引用**（`test_today_page`
#:     檔頭對 `_ui_kit` 的 `:<行號>` 引用，同日已由 WX3 改為 `::grid()` ＋ 逐字引文）
#:     ⇒ **0 筆誤傷**。突變測試（四種副檔名各注入一筆）四筆全抓、
#:     對照組 `localhost:8080`／`4.5:1`／`_ui_kit.py::grid()` 三種**全未命中**。
#:   ⚠️ **可預見的誤傷形狀（⛔ 現在沒有、日後可能有）**：若有人把一段 pytest traceback
#:     （形如 `某檔.py:<行號>: AssertionError`）貼進 docstring 當說明，本條會抓它 ——
#:     **屆時請回報總管改裁示**（可能的收法：只認 repo 內實際存在的檔），
#:     ⛔ 不得自行加白名單、⛔ 不得自行縮副檔名範圍（見下方 test 的 docstring）。
#:
#: ⚠️ 本常數自身的原始字串不會命中自己：`\\.(?:md|html|js|py):\\d` 的冒號後面是
#:   `\\d` 不是數字；`py` 後面接的是 `)` 不是冒號。所以本檔不會把自己判成違規。
#:   同理，任何想舉例的地方請寫 `UI_PAGE_TODAY.md:<行號>` 這種不帶數字的寫法。
#: ⚠️ **必須是 non-capturing group `(?:...)`** —— 改成 capturing group 會讓
#:   `findall()` 只回傳副檔名、報告變成一串 `md` / `py`，守衛看起來還是綠的**假象**。
_SPEC_LINE_REF = re.compile(r"[A-Za-z0-9_.\-]+\.(?:md|html|js|py):\d+")


def _ui_v2_python_files() -> list[pathlib.Path]:
    root = pathlib.Path(__file__).resolve().parents[2]
    files: list[pathlib.Path] = []
    for rel in _UI_V2_SCAN_DIRS:
        files.extend(sorted((root / rel).glob("*.py")))
    return files


def test_no_spec_reference_is_written_as_a_line_number():
    """指向規格／原型／程式碼的引用一律寫**章節名或符號名**，⛔ 不得寫行號。

    **依據：`CLAUDE.md` §8.2.A.0 規則 1**（逐字）——
    「**禁止寫行號。** 例外一律以「**檔案路徑 ＋ 符號名 ＋ 模式描述**」登記。
      行號在任何一次重構後就失效，而重構**不會**觸發本清單更新
      → **行號是「保證會過期的資訊」**」。

    **為什麼是現在立這條（2026-09-21 的實證，⛔ 不是儀式性規定）**：
    本輪規格組在 `docs/v2/spec/UI_PAGE_TODAY.md` 的 ① 與 ③ 插入內容，
    整檔行號整體下移（實測：151 行 → 200 行）——
    `src/ui_v2/`＋`tests/ui_v2/` 裡**一次就漂掉 400 筆以上**的行號引用
    （量測日 2026-09-21：WX 轉掉四個檔共 **259** 筆、WX2 轉掉
      `tokens` 與 `test_tokens` 兩個檔共 **146** 筆，
      其餘 `.html`／`.py` 型號由 WX3 收尾）。
    ⚠️ 上列筆數是**會過期的量測值**（`CLAUDE.md §8.2.A.0` 規則 4），
      **⛔ 不要拿它當現況** —— 現況一律以本測試**當場跑出來的結果**為準。
    更陰險的是：它們**不會報錯**—— 每一筆都還是一個合法的行號，
    只是指到別的句子去了。沒有守衛就沒有人會發現。

    **⛔ 本條沒有白名單，也不得加（總管 2026-09-21 裁示）**：
    留一條「特殊情況可以寫行號」的路，等於留下一個**會被引用來合理化的正當條文**
    （同 `CLAUDE.md` §-2 規則 6「留但書等於留引用點」）。
    若真的遇到非寫行號不可的情形 → **回報總管**，⛔ 不得自行開例外；
    同理，⛔ 不得為了讓本條轉綠而把某個檔排除在 `_UI_V2_SCAN_DIRS` 之外
    —— 那是把守衛本身開了一個洞。

    **正確的寫法（規格 `.md`）**：`UI_PAGE_TODAY.md ①「第二層」today.holdings 條`、
    `UI_COMPONENTS.md §2 徽章表 #9`、`UI_TOKENS.md §B 字型 token 表「說明」列`。
    章節沒有名字時 → 用「章節名 ＋ 該處逐字的一小段引文」，讓人搜尋得到。

    **正確的寫法（程式碼 `.py`）**：`CLAUDE.md §8.2.A.0 規則 1` 逐字要求的
    「**檔案路徑 ＋ 符號名 ＋ 模式描述**」—— 例如
    `src/ui/views/_ui_kit.py::grid()` 的 `min(cols, MAX_COLS)`。
    **正確的寫法（原型 `.html` ／ 線框 `.js`）**：檔名 ＋ **選擇器或區塊名**
    （＋ 必要時該處逐字），例如 `ui_prototype_today.html` 的 `.g3` 三斷點 CSS。

    ⚠️ **放寬到 `.html` / `.js` / `.py` 是 2026-09-21 總管裁示**（理由見上方常數註）。
    若日後發現它誤傷了**不是行號引用**的東西（pytest traceback 片語、
    錯誤訊息樣板等）→ **回報總管改裁示**，⛔ 不得自行加白名單、⛔ 不得縮副檔名範圍。
    """
    offenders: dict[str, list[str]] = {}
    for path in _ui_v2_python_files():
        hits = []
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for found in _SPEC_LINE_REF.findall(line):
                hits.append(f"    L{lineno}: {found}")
        if hits:
            offenders[path.name] = hits

    if offenders:
        total = sum(len(h) for h in offenders.values())
        report = [
            f"行號引用尚未清完，共 {total} 筆"
            "（.md／.html／.js／.py 四種副檔名；"
            "行號是「保證會過期的資訊」，CLAUDE.md §8.2.A.0 規則 1）：",
        ]
        for name, hits in sorted(offenders.items()):
            report.append(f"  {name}（{len(hits)} 筆）")
            report.extend(hits[:5])
            if len(hits) > 5:
                report.append(f"    …還有 {len(hits) - 5} 筆")
        report.append(
            "→ .md/.html/.js 改成章節名或區塊名引用（必要時 ＋ 逐字引文）；"
            ".py 改成「檔案路徑 ＋ 符號名」（CLAUDE.md §8.2.A.0 規則 1 逐字）；"
            "⛔ 不得重編行號、⛔ 不得加白名單、"
            "⛔ 不得縮掃描範圍、⛔ 不得縮副檔名範圍。"
        )
        raise AssertionError("\n".join(report))
