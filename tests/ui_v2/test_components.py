"""WT 測試組｜test-first 契約 B：元件（`src/ui_v2/components.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/` 尚不存在，
   本檔因此**應該是紅燈（ModuleNotFoundError）** —— 紅燈即正確結果。

唯一資料來源：`docs/v2/spec/UI_COMPONENTS.md`（每條 assert 旁標 `# UI_COMPONENTS.md:NN`）。
顏色／字級／間距的 SSOT 在 `UI_TOKENS.md`（UI_COMPONENTS.md:7）⇒ 本層一律存**token 名**
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
    七態 SSOT 是既有 L0 `shared/ui_state.py`（UI_COMPONENTS.md:51-52），
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
    四層密度**由層序自動掛**，⛔ 非逐塊手選（UI_COMPONENTS.md:36）。
    `0`（葉外 chrome）→ `"t3"`；`1..4` → `"t1".."t4"`；其餘 → `raise ValueError`。

`resolve_cols(cols: tuple[int, int, int], viewport_px: int) -> int`
    `cols` 依線框記法 `(桌機, 平板, 手機)`；回傳該視窗寬下的欄數，並夾在 `MAX_COLS`。
"""
from __future__ import annotations

import inspect

import pytest

from src.ui_v2 import components


TIER_KEYS = ("t1", "t2", "t3", "t4")


# ══════════════════════════════════════════════════════════════════
# B-1 卡片四階密度（UI_COMPONENTS.md:38-43）
# ══════════════════════════════════════════════════════════════════
def test_card_tiers_are_exactly_four():
    assert tuple(components.CARD_TIERS) == TIER_KEYS  # UI_COMPONENTS.md:38-43


@pytest.mark.parametrize(
    "tier, padding, border_width, border_style, margin_top, title_px",
    [
        ("t1", (15.0, 17.0), 2.0, "solid", 15.0, 17.5),   # UI_COMPONENTS.md:40
        ("t2", (10.0, 12.0), 1.0, "solid", 10.0, 14.5),   # UI_COMPONENTS.md:41
        ("t3", (6.0, 9.0), 1.0, "solid", 6.0, 13.0),      # UI_COMPONENTS.md:42
        ("t4", (5.0, 9.0), 1.0, "dashed", 5.0, 12.5),     # UI_COMPONENTS.md:43
    ],
)
def test_card_tier_geometry(tier, padding, border_width, border_style, margin_top, title_px):
    spec = components.CARD_TIERS[tier]
    assert tuple(spec["padding_px"]) == padding
    assert spec["border_width_px"] == border_width
    assert spec["border_style"] == border_style
    assert spec["margin_top_px"] == margin_top
    assert spec["title_px"] == title_px
    assert spec["title_weight"] == 700          # UI_COMPONENTS.md:40-43 「/700」
    assert spec["radius_px"] == 2.0             # UI_COMPONENTS.md:35 全卡 radius 2px
    assert spec["border_color"] == "--rule-2"   # UI_COMPONENTS.md:35／:40-43


def test_t1_has_the_only_mobile_padding_override():
    # UI_COMPONENTS.md:40 t1 ≤640 → `11px 12px`（其餘三階規格未給覆寫值）
    assert tuple(components.CARD_TIERS["t1"]["padding_mobile_px"]) == (11.0, 12.0)


def test_t4_title_uses_ink_2():
    # UI_COMPONENTS.md:43 t4 卡標 `12.5px/700` `--ink-2`
    assert components.CARD_TIERS["t4"]["title_color"] == "--ink-2"


@pytest.mark.parametrize("tier", TIER_KEYS)
def test_no_tier_invents_a_shadow(tier):
    """UI_COMPONENTS.md:45「層級只靠 border-width／dashed／padding 三個通道區分，
    ⛔ 不得發明陰影」；:40-43 四階陰影欄皆為「無（線框 0 命中）」。"""
    assert components.CARD_TIERS[tier]["shadow"] is None


def test_density_ladder_is_monotonic():
    """密度階梯：越往下層越緊。UI_COMPONENTS.md:38-43 四階實際值。

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
# B-2 四層自動掛（UI_COMPONENTS.md:36）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "layer, tier",
    [(0, "t3"),   # UI_PAGE_TODAY.md:14 葉外 chrome 走 t3（據實列出、不計入四層）
     (1, "t1"),   # UI_PAGE_TODAY.md:15
     (2, "t2"),   # UI_PAGE_TODAY.md:16
     (3, "t3"),   # UI_PAGE_TODAY.md:17
     (4, "t4")],  # UI_PAGE_TODAY.md:18
)
def test_tier_is_auto_mounted_from_layer(layer, tier):
    """UI_COMPONENTS.md:36「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」。"""
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
    """UI_COMPONENTS.md:51-52「基底＝既有 L0 `shared/ui_state.py` 七態 SSOT…
    `_ui_kit.py` 明寫『不定義狀態，唯一真相源是它』」。

    ⇒ `src/ui_v2/` ⛔ 不得再長出第二份狀態常數（§2.1 SSOT）。
    """
    for const_name in ("UI_LIVE", "UI_LOADING", "UI_IDLE", "UI_DEGRADED",
                       "UI_UNWIRED", "UI_FAILED", "UI_EMPTY"):
        assert not hasattr(components, const_name), (
            f"{const_name} 不得在 src/ui_v2/ 重新宣告，唯一真相源是 shared/ui_state.py"
        )


# ══════════════════════════════════════════════════════════════════
# B-3 徽章 10 種（UI_COMPONENTS.md:58-69）
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
    # UI_COMPONENTS.md:49「徽章（10 種）」＋ :58-69 表
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
    """UI_COMPONENTS.md:94 硬規則「狀態色一律配圖示＋文字，⛔ 不得只靠顏色」
    —— 依據是 UI_TOKENS.md:96 實測「綠/紅在 deuteranopia 下 ΔE 3.9 無解」。"""
    got = components.badge(n)
    assert isinstance(got["icon"], str) and got["icon"].strip(), f"#{n} 圖示為必填"
    assert isinstance(got["text"], str) and got["text"].strip(), f"#{n} 文字為必填"


def test_badge_7_and_8_are_separable_without_colour():
    """UI_COMPONENTS.md:73-74「灰系內部的『不適用』與『缺漏』必須再以符號與 tooltip 分辨，
    ⛔ 不得只靠顏色 —— 只差顏色等於把兩態併回一態」。"""
    seven, eight = components.badge(7), components.badge(8)
    assert seven["bg"] == eight["bg"] and seven["fg"] == eight["fg"], "兩者同屬灰系（前提）"
    assert seven["icon"] != eight["icon"], "⛔ 缺漏與不適用不得共用圖示"
    assert seven["text"] != eight["text"], "⛔ 文字不得省略或縮寫成同一句"
    assert seven["miss_reason"] != eight["miss_reason"]


def test_badge_9_shares_no_colour_token_with_badge_1():
    """UI_COMPONENTS.md:75「#9『資料不完整』⛔ 不得長得像 #1『正常』…與 #1 不共用任何一個色 token」。"""
    nine, one = components.badge(9), components.badge(1)
    nine_colours = {nine["bg"], nine["fg"], nine["border_color"]}
    one_colours = {one["bg"], one["fg"], one["border_color"]}
    assert nine_colours.isdisjoint(one_colours)
    assert nine["icon"] != one["icon"]  # UI_COMPONENTS.md:77 圖示 🟢→`◧`


def test_badge_9_and_10_do_not_rely_on_the_border_alone():
    """UI_COMPONENTS.md:80／:87「其中圖示與文字在 `.sbadge b4`（`border:0`）下仍存在，
    ⛔ 不得把虛線當唯一分辨通道」—— b4 框線整條不存在，扛分辨的是圖示＋文字。"""
    nine, ten = components.badge(9), components.badge(10)
    assert components.SBADGE_SIZES["b4"]["border_width_px"] == 0  # UI_COMPONENTS.md:56
    assert nine["icon"] != ten["icon"]
    assert nine["text"] != ten["text"]
    assert nine["fg"] != ten["fg"]  # 2026-09-21 換色後前景已不同（UI_COMPONENTS.md:85）


def test_badge_base_geometry():
    # UI_COMPONENTS.md:53-54（線框 `.bdg`，10 種共用）
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
        ("b1", 14.5, (10.0, 22.0), 46.0, 2.0),   # UI_COMPONENTS.md:55
        ("b2", 12.5, (5.0, 13.0), 36.0, 1.0),    # UI_COMPONENTS.md:55（框寬未覆寫→承 :54 基底 1px）
        ("b3", 11.0, (2.0, 10.0), 28.0, 1.0),    # UI_COMPONENTS.md:56（同上）
        ("b4", 10.5, (2.0, 5.0), 26.0, 0.0),     # UI_COMPONENTS.md:56 border 0
    ],
)
def test_sbadge_four_sizes(size, font_px, padding, min_height, border_width):
    spec = components.SBADGE_SIZES[size]
    assert spec["font_px"] == font_px
    assert tuple(spec["padding_px"]) == padding
    assert spec["min_height_px"] == min_height
    assert spec["border_width_px"] == border_width


def test_sbadge_b3_radius():
    assert components.SBADGE_SIZES["b3"]["radius_px"] == 3.0  # UI_COMPONENTS.md:56


@pytest.mark.parametrize("tier, size", list(zip(TIER_KEYS, ("b1", "b2", "b3", "b4"))))
def test_card_tier_picks_its_badge_size(tier, size):
    # UI_COMPONENTS.md:56「依所在卡層 t1→b1 … t4→b4」
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
# B-4 按鈕五類（UI_COMPONENTS.md:102-108）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "key, min_height, padding, font_px, font_weight, radius",
    [
        ("primary_cta", 40.0, (6.0, 16.0), 13.5, 700, 3.0),        # UI_COMPONENTS.md:104
        ("secondary_explain", 40.0, (6.0, 16.0), 13.5, 700, 3.0),  # UI_COMPONENTS.md:105
        ("secondary_evidence", 44.0, (7.0, 9.0), 12.5, 600, 3.0),  # UI_COMPONENTS.md:106
        ("text", 28.0, (2.0, 11.0), 11.0, 600, 999.0),             # UI_COMPONENTS.md:107
        ("disabled", 40.0, (6.0, 16.0), 13.5, 500, 3.0),           # UI_COMPONENTS.md:108
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
    }  # UI_COMPONENTS.md:102-108


def test_evidence_button_meets_the_44px_touch_target():
    # UI_COMPONENTS.md:106「`min-height:44px`／`min-width:44px`」
    spec = components.BUTTONS["secondary_evidence"]
    assert spec["min_height_px"] == 44.0 and spec["min_width_px"] == 44.0


def test_primary_cta_paints_with_ink_and_hovers_to_ochre():
    # UI_COMPONENTS.md:104 底 `--ink`／框 2px solid `--ink`／hover → `--ochre`、字 `--paper`
    spec = components.BUTTONS["primary_cta"]
    assert spec["bg"] == "--ink"
    assert spec["border_width_px"] == 2.0 and spec["border_style"] == "solid"
    assert spec["border_color"] == "--ink"
    assert spec["hover"]["bg"] == "--ochre"
    assert spec["hover"]["border_color"] == "--ochre"
    assert spec["hover"]["fg"] == "--paper"


def test_disabled_button_is_dashed_and_grey():
    # UI_COMPONENTS.md:108 `1px dashed --rule-2`，字 `--sig-grey`，hover 無
    spec = components.BUTTONS["disabled"]
    assert spec["border_style"] == "dashed"
    assert spec["border_color"] == "--rule-2"
    assert spec["fg"] == "--sig-grey"
    assert spec.get("hover") is None


def test_focus_ring_is_a_single_global_rule():
    """UI_COMPONENTS.md:110「全站唯一一條 `:focus-visible{outline:2px solid var(--focus);
    outline-offset:2px}`，⛔ 不准個別 `outline:none`」。"""
    ring = components.FOCUS_RING
    assert ring["outline_width_px"] == 2.0
    assert ring["outline_style"] == "solid"
    assert ring["outline_color"] == "--focus"
    assert ring["outline_offset_px"] == 2.0
    for key, spec in components.BUTTONS.items():
        assert spec.get("outline") != "none", f"{key} ⛔ 不得個別關掉焦點環"


# ══════════════════════════════════════════════════════════════════
# B-5 斷點三段（UI_COMPONENTS.md:28）
# ══════════════════════════════════════════════════════════════════
def test_three_breakpoints():
    """UI_COMPONENTS.md:28「斷點＝`≤640 手機 / 641–880 平板 / ≥881 桌機`（線框 JS `BP` 宣告版）」。

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
    # 線框 cols 記法為 (桌機, 平板, 手機)；此處用 `.g3` 的 3/2/1（UI_PAGE_TODAY.md:28）
    assert components.resolve_cols((3, 2, 1), viewport) == expected


def test_resolve_cols_is_clamped_at_max_cols():
    """UI_PAGE_TODAY.md:47-48「硬夾在 `tab_today.MAX_COLS＝3` —— 多於 3 格換行排下一列，
    不是加欄（`_ui_kit.py:145 min(cols, MAX_COLS)`）」。"""
    assert components.MAX_COLS == 3
    assert components.resolve_cols((5, 4, 1), 1440) == 3
    assert components.resolve_cols((5, 4, 1), 800) == 3
