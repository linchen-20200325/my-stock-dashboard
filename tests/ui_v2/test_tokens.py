"""WT 測試組｜test-first 契約 A：設計 token（`src/ui_v2/tokens.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/` 尚不存在，
   本檔因此**應該是紅燈（ModuleNotFoundError）** —— 紅燈即正確結果。
   實作組的任務＝把下面這份 API 做出來、讓它轉綠，⛔ 不是改本檔讓它變綠。

唯一資料來源：`docs/v2/spec/UI_TOKENS.md`
（每條 assert 旁以 `# UI_TOKENS.md <章節名>` 標出處；⛔ 不寫行號 —— CLAUDE.md §8.2.A.0 規則 1）。
⛔ 本檔未引用 `src/ui/` 任何既有檔案、未引用舊原型 `ui_prototype_today.html`。
⛔ 本檔不 import streamlit —— 這一層測的是**純資料契約**（token 值），不是渲染。

────────────────────────────────────────────────────────────────────
實作組必須提供：`src/ui_v2/tokens.py`
────────────────────────────────────────────────────────────────────
`TBD` : object
    哨兵值，意思是「**客戶尚未指定**」。
    ⛔ 不得用 `None`／空字串／自己挑一個近似色頂替
    （UI_TOKENS.md §A-2.1 已加刪除線的「light 值＝待訂」條逐字：
      「客戶 2026-09-21 只指定 dark 兩碼，⛔ 本檔不得自行發明 light 值」
     ＋ `CLAUDE.md` §1 Fail Loud：寧可炸掉，不可造假）。

`class TokenNotSpecifiedError(KeyError)`
    `get_token()` 取到 `TBD` 時拋出。

`DARK : Mapping[str, str]`
    dark 模式 token 表。鍵＝CSS 自訂屬性**全名（含前導 `--`）**；值＝**小寫 7 字元 hex**（`#rrggbb`）。

`LIGHT : Mapping[str, str | TBD]`
    light 模式 token 表。**鍵集合必須與 `DARK` 完全相同**；客戶未指定者，值＝`TBD`。

`SPACING : Mapping[str, str]`
    `--sp-1` ~ `--sp-8` 八級，值為**含單位字串**（`"4px"`）。與 dark/light 無關。

`SERIES_DARK` / `SERIES_LIGHT` : `tuple[str, ...]`
    圖表序列識別色 **7 槽**，index 0 ＝ 槽 1。**固定順序、⛔ 不循環**。

`STATUS_PAIRS : tuple[tuple[str, str], ...]`
    狀態色 `(ink_token, bg_token)` 配對，依 A-2 表順序：
    green / amber / red / blue / grey / neutral（共 6 對）。

`get_token(name: str, *, mode: str) -> str`
    取 token 值。`mode` ∈ `{"dark", "light"}`。
    - 未知 `name` → `raise KeyError`
    - 值為 `TBD`  → `raise TokenNotSpecifiedError`（⛔ 不得偷偷回退到 dark 值）
"""
from __future__ import annotations

import pytest

from src.ui_v2 import tokens


# ══════════════════════════════════════════════════════════════════
# WCAG 相對亮度／對比 —— **測試自己算**，⛔ 不向實作要這個函式，
# 也⛔ 不用字串比對代替（改了 token 值就要立刻被抓到）。
# 公式：WCAG 2.x relative luminance + contrast ratio。
# ══════════════════════════════════════════════════════════════════
def _srgb_to_linear(channel_0_to_1: float) -> float:
    if channel_0_to_1 <= 0.03928:
        return channel_0_to_1 / 12.92
    return ((channel_0_to_1 + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    assert len(raw) == 6, f"token 值必須是 #rrggbb 六碼：{hex_color!r}"
    r, g, b = (int(raw[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (0.2126 * _srgb_to_linear(r)
            + 0.7152 * _srgb_to_linear(g)
            + 0.0722 * _srgb_to_linear(b))


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    lum_a, lum_b = relative_luminance(fg_hex), relative_luminance(bg_hex)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


#: WCAG AA 小字門檻。UI_TOKENS.md §A-1 表下註「--ink-3 一律對三個背景都量」
#: 與 §A-2.1「✅ 新值仍達標」條均明文 ⛔ 不得套大字 3:1 寬鬆標準
#: （落點字級 9.5px／11px／11.5px，遠低於 18.66px bold／24px 大字門檻）。
AA_SMALL_TEXT = 4.5


# ══════════════════════════════════════════════════════════════════
# A-0 先驗證「量尺」本身有牙齒：拿 UI_TOKENS.md 自己記載的**舊缺陷值**
#     回算，必須算得出 FAIL。這條擋的是「有人把對比函式寫成恆過」。
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "fg, bg, expected, label",
    [
        # UI_TOKENS.md §A-1 表下註「📌 舊值實測（缺陷本體，2026-09-16 修）」——
        # 舊 dark --ink-3 `#73838f`：對 --paper 4.73 PASS，
        # 但對 --panel 4.35、--panel-2 4.01 兩格 FAIL（＝該缺陷本體）。
        ("#73838f", "#0e141b", 4.73, "舊 dark ink-3 on --paper"),
        ("#73838f", "#151d26", 4.35, "舊 dark ink-3 on --panel（FAIL）"),
        ("#73838f", "#1b242f", 4.01, "舊 dark ink-3 on --panel-2（FAIL）"),
        # 同註：舊 light --ink-3 `#626f7a`：對 --panel-2 4.36 FAIL。
        ("#626f7a", "#edece7", 4.36, "舊 light ink-3 on --panel-2（FAIL）"),
        # UI_TOKENS.md §A-2 表下註「light --sig-grey 自線框 #6c7883 下修
        #（原對自身 bg 僅 3.71:1）」。
        ("#6c7883", "#eae9e4", 3.71, "舊 light sig-grey on own bg（FAIL）"),
    ],
)
def test_wcag_helper_reproduces_the_documented_failures(fg, bg, expected, label):
    """對比函式必須算得出 UI_TOKENS.md 記載的**舊值 FAIL**，否則量尺是壞的。"""
    got = contrast_ratio(fg, bg)
    assert got == pytest.approx(expected, abs=0.005), label
    if expected < AA_SMALL_TEXT:
        assert got < AA_SMALL_TEXT, f"{label}：規格記載為 FAIL，量尺卻算成 PASS"


# ══════════════════════════════════════════════════════════════════
# A-1 面與墨 token（dark 為主要交付 —— UI_TOKENS.md 檔頭基準段逐字）
# ══════════════════════════════════════════════════════════════════
DARK_SURFACE_AND_INK = {
    "--ochre":   "#d59a5e",   # UI_TOKENS.md §A-1 表「--ochre」列
    "--focus":   "#8fc0ff",   # UI_TOKENS.md §A-1 表「--focus」列
    "--paper":   "#0e141b",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--panel":   "#151d26",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--panel-2": "#1b242f",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--rule":    "#2e3b48",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--rule-2":  "#46545f",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--ink":     "#dbe5ef",   # UI_TOKENS.md §A-1 表「--ink／--ink-2」列
    "--ink-2":   "#9fb0c1",   # UI_TOKENS.md §A-1 表「--ink／--ink-2」列
    "--ink-3":   "#7d8d99",   # UI_TOKENS.md §A-1 表「--ink-3」列（2026-09-16 自 #73838f 改）
}


@pytest.mark.parametrize("name, value", sorted(DARK_SURFACE_AND_INK.items()))
def test_dark_surface_and_ink_tokens(name, value):
    assert tokens.DARK[name] == value
    assert tokens.get_token(name, mode="dark") == value


def test_light_ink_3_is_the_post_fix_value():
    # UI_TOKENS.md §A-1 表「--ink-3」列 light 欄 `#5f6c77`（前輪 `#626f7a` 已退場）
    assert tokens.LIGHT["--ink-3"] == "#5f6c77"


def test_dark_and_light_cover_the_same_token_names():
    # 兩模式必須同一組鍵；缺的那邊用 TBD 表示，⛔ 不是整個鍵消失。
    assert set(tokens.DARK) == set(tokens.LIGHT)


def test_ink_ramp_is_strictly_monotonic_in_both_modes():
    """UI_TOKENS.md §A-1 表下註「📌 舊值實測（缺陷本體，2026-09-16 修）」逐字：
    「--ink→--ink-2→--ink-3 的 L* 兩模式皆嚴格單調」。

    L* 是相對亮度 Y 的**單調遞增**函數 ⇒ 驗 Y 嚴格單調 ⟺ 驗 L* 嚴格單調。
    dark 模式墨色越深階越暗、light 模式越深階越亮（往背景靠）。
    """
    dark = [relative_luminance(tokens.DARK[k]) for k in ("--ink", "--ink-2", "--ink-3")]
    assert dark[0] > dark[1] > dark[2], f"dark 墨階未嚴格單調：{dark}"

    light = [relative_luminance(tokens.LIGHT[k]) for k in ("--ink", "--ink-2", "--ink-3")]
    assert light[0] < light[1] < light[2], f"light 墨階未嚴格單調：{light}"


# ══════════════════════════════════════════════════════════════════
# A-2 狀態色（五枚 ink/bg ＋ 本輪新增的 neutral）
# ══════════════════════════════════════════════════════════════════
DARK_STATUS = {
    "--sig-green":      "#57b985",   # UI_TOKENS.md §A-2 表「--sig-green」列
    "--sig-green-bg":   "#11241a",   # UI_TOKENS.md §A-2 表「--sig-green」列
    "--sig-amber":      "#d3a43c",   # UI_TOKENS.md §A-2 表「--sig-amber」列
    "--sig-amber-bg":   "#292110",   # UI_TOKENS.md §A-2 表「--sig-amber」列
    "--sig-red":        "#e8706b",   # UI_TOKENS.md §A-2 表「--sig-red」列
    "--sig-red-bg":     "#2b1615",   # UI_TOKENS.md §A-2 表「--sig-red」列
    "--sig-blue":       "#4b8efe",   # UI_TOKENS.md §A-2 表「--sig-blue」列
    "--sig-blue-bg":    "#141f2b",   # UI_TOKENS.md §A-2 表「--sig-blue」列
    "--sig-grey":       "#8b98a4",   # UI_TOKENS.md §A-2 表「--sig-grey」列
    "--sig-grey-bg":    "#1b232b",   # UI_TOKENS.md §A-2 表「--sig-grey」列
    # 以下兩筆同出 UI_TOKENS.md §A-2 表「--sig-neutral／--sig-neutral-bg」列。
    "--sig-neutral":    "#8fa3b8",   # 2026-09-21 客戶裁示
    # bg 另見 §A-2.1「總管建議值…客戶已於 2026-09-21 採納：#26313d」條
    "--sig-neutral-bg": "#26313d",   # 同日自 #1f2a36 改
}


@pytest.mark.parametrize("name, value", sorted(DARK_STATUS.items()))
def test_dark_status_tokens(name, value):
    assert tokens.DARK[name] == value


def test_sig_neutral_bg_is_the_new_value_not_the_retired_one():
    # UI_TOKENS.md §A-2.1「📌 2026-09-21 換色（決策者 user，客戶裁示採用
    # 總管建議值）」條：舊值 `#1f2a36` 已退場（ΔE 只改善 0.09、底在卡上看不見）
    assert tokens.DARK["--sig-neutral-bg"] != "#1f2a36"
    # UI_TOKENS.md §A-2.1「另評估過 #2b3947…⛔ 未採用」括號句：
    # `#2b3947` 評估過但**未採用**（文字對比掉到 4.55、餘裕太薄）
    assert tokens.DARK["--sig-neutral-bg"] != "#2b3947"


#: UI_TOKENS.md 附錄 A-2.2：2026-09-21 補上的 light 兩碼（B 組值）。
#: ⚠️ 決策者＝**AI 總管**，⛔ 不是客戶（客戶只指派補洞、⛔ 未指定值）。
#: ⭐ **可被客戶一句話改採 A 組 `#3c5063`／`#d9dce0`** —— 屆時本組常數要跟著改。
LIGHT_NEUTRAL = {
    "--sig-neutral":    "#1e3b4f",
    "--sig-neutral-bg": "#d7dce1",
}


@pytest.mark.parametrize("name, value", sorted(LIGHT_NEUTRAL.items()))
def test_sig_neutral_light_is_now_specified_with_the_b_group_value(name, value):
    """附錄 A-2.2：light 兩碼已補量落地，⛔ 不再是 TBD。

    ⚠️ 這條同時擋「回退 dark 值」——  dark 是 `#8fa3b8`／`#26313d`，與本對不同。
    ⚠️ ⛔ 也不得換成 A 組的 `#3c5063`／`#d9dce0`（前景過不了 ≥15 門檻，見下方測試）。
    """
    assert tokens.LIGHT[name] == value
    assert tokens.LIGHT[name] is not tokens.TBD
    assert tokens.get_token(name, mode="light") == value
    assert tokens.LIGHT[name] != tokens.DARK[name], "⛔ light 不得回退成 dark 值"


@pytest.mark.parametrize("name, rejected", [("--sig-neutral", "#3c5063"),
                                            ("--sig-neutral-bg", "#d9dce0")])
def test_light_sig_neutral_is_not_the_unadopted_a_group_value(name, rejected):
    # 附錄 A-2.2：A 組值經量測**未採用**（前景 vs light --sig-grey 僅 OKLab×100 7.66）。
    assert tokens.LIGHT[name] != rejected


def test_status_pairs_cover_six_ink_bg_couples():
    # UI_TOKENS.md §A-2 狀態色表：五枚狀態色
    # ＋ 同表「--sig-neutral／--sig-neutral-bg」列新增的 neutral
    assert tokens.STATUS_PAIRS == (
        ("--sig-green", "--sig-green-bg"),
        ("--sig-amber", "--sig-amber-bg"),
        ("--sig-red", "--sig-red-bg"),
        ("--sig-blue", "--sig-blue-bg"),
        ("--sig-grey", "--sig-grey-bg"),
        ("--sig-neutral", "--sig-neutral-bg"),
    )


# ══════════════════════════════════════════════════════════════════
# A-3 WCAG 實算（⛔ 不是字串比對）
# ══════════════════════════════════════════════════════════════════
INK3_SIX_CELLS = [
    # UI_TOKENS.md §A-1 表下註「--ink-3 一律對 --paper／--panel／--panel-2 三個背景
    # 都量」本輪六格實算：dark 5.41／4.97／4.58；light 4.94／5.34／4.55
    ("dark", "--paper", 5.41),
    ("dark", "--panel", 4.97),
    ("dark", "--panel-2", 4.58),
    ("light", "--paper", 4.94),
    ("light", "--panel", 5.34),
    ("light", "--panel-2", 4.55),
]


@pytest.mark.parametrize("mode, surface, expected", INK3_SIX_CELLS)
def test_ink_3_passes_aa_on_all_three_surfaces(mode, surface, expected):
    """UI_TOKENS.md §A-1 表下註逐字：「--ink-3 一律對 --paper／--panel／--panel-2
    三個背景都量，⛔ 不得只對 --paper 定錨」→ 六格全 ≥ 4.5。"""
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    got = contrast_ratio(table["--ink-3"], table[surface])
    assert got == pytest.approx(expected, abs=0.005)
    assert got >= AA_SMALL_TEXT, f"{mode} --ink-3 on {surface} = {got:.2f} < {AA_SMALL_TEXT}"


def test_sig_neutral_on_its_own_bg_passes_aa():
    # UI_TOKENS.md §A-2.1「✅ 新值仍達標」條逐字「#8fa3b8 on #26313d ＝ 5.10:1」，
    # 徽章字級 11px／10.5px
    got = contrast_ratio(tokens.DARK["--sig-neutral"], tokens.DARK["--sig-neutral-bg"])
    assert got == pytest.approx(5.10, abs=0.005)
    assert got >= AA_SMALL_TEXT


@pytest.mark.parametrize(
    "surface, expected",
    # 出處：UI_TOKENS.md §A-2.1「--sig-neutral 對三背景的文字對比」條
    [("--panel", 6.55), ("--paper", 7.14), ("--panel-2", 6.04)],
)
def test_sig_neutral_on_three_dark_surfaces(surface, expected):
    """UI_TOKENS.md §A-2.1「--sig-neutral 對三背景的文字對比」條逐字：
    「比照 A-1 --ink-3 三背景定錨慣例，三格皆 ≥ 4.5 PASS」。"""
    got = contrast_ratio(tokens.DARK["--sig-neutral"], tokens.DARK[surface])
    assert got == pytest.approx(expected, abs=0.005)
    assert got >= AA_SMALL_TEXT


@pytest.mark.parametrize("mode", ["dark", "light"])
@pytest.mark.parametrize(
    "ink, bg",
    [("--sig-green", "--sig-green-bg"), ("--sig-amber", "--sig-amber-bg"),
     ("--sig-red", "--sig-red-bg"), ("--sig-blue", "--sig-blue-bg"),
     ("--sig-grey", "--sig-grey-bg")],
)
def test_five_status_colors_ink_on_own_bg_pass_aa(mode, ink, bg):
    """UI_TOKENS.md §A-3「驗證器實跑」段逐字：
    「狀態色五枚 ink-on-own-bg WCAG AA 4.5:1 dark 5/5、light 5/5 PASS」。"""
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    got = contrast_ratio(table[ink], table[bg])
    assert got >= AA_SMALL_TEXT, f"{mode} {ink} on {bg} = {got:.2f}"


# ══════════════════════════════════════════════════════════════════
# A-4 序列識別色 7 槽
# ══════════════════════════════════════════════════════════════════
SERIES_DARK = ("#2e64a6", "#c7843c", "#209993", "#c15dde",
               "#6f650d", "#934d6b", "#7a3ae2")          # UI_TOKENS.md §A-3 表 槽 1~7
SERIES_LIGHT = ("#2482eb", "#b47227", "#1b9690", "#b118a5",
                "#5b5e00", "#ff3282", "#7612e0")         # UI_TOKENS.md §A-3 表 槽 1~7


@pytest.mark.parametrize("slot_index, value", list(enumerate(SERIES_DARK)))
def test_series_dark_seven_slots_fixed_order(slot_index, value):
    assert tokens.SERIES_DARK[slot_index] == value


@pytest.mark.parametrize("slot_index, value", list(enumerate(SERIES_LIGHT)))
def test_series_light_seven_slots_fixed_order(slot_index, value):
    assert tokens.SERIES_LIGHT[slot_index] == value


@pytest.mark.parametrize("palette_name", ["SERIES_DARK", "SERIES_LIGHT"])
def test_series_palette_has_exactly_seven_distinct_slots(palette_name):
    # UI_TOKENS.md §A-3 標題逐字「7 槽，固定順序、⛔ 不循環；
    # 第 8 條以上折成『其他』或分面」
    palette = getattr(tokens, palette_name)
    assert len(palette) == 7
    assert len(set(palette)) == 7


@pytest.mark.parametrize("mode, palette_name", [("dark", "SERIES_DARK"), ("light", "SERIES_LIGHT")])
def test_status_colors_are_reserved_and_never_reused_as_series(mode, palette_name):
    """UI_TOKENS.md §A-2 標題逐字「保留色：⛔ 不得挪用為圖表第 N 條線」
    —— 被保留的那一組色即 §A-3 圖表序列識別色表的七槽。"""
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    status_inks = {table[ink] for ink, _bg in tokens.STATUS_PAIRS
                   if table[ink] is not tokens.TBD}
    assert status_inks.isdisjoint(set(getattr(tokens, palette_name)))


# ══════════════════════════════════════════════════════════════════
# A-5 間距八級
# ══════════════════════════════════════════════════════════════════
SPACING_SCALE = {
    "--sp-1": "4px",    # UI_TOKENS.md §C 表「--sp-1／--sp-2／--sp-3」列
    "--sp-2": "6px",    # UI_TOKENS.md §C 表「--sp-1／--sp-2／--sp-3」列
    "--sp-3": "8px",    # UI_TOKENS.md §C 表「--sp-1／--sp-2／--sp-3」列
    "--sp-4": "10px",   # UI_TOKENS.md §C 表「--sp-4／--sp-5／--sp-6」列
    "--sp-5": "12px",   # UI_TOKENS.md §C 表「--sp-4／--sp-5／--sp-6」列
    "--sp-6": "16px",   # UI_TOKENS.md §C 表「--sp-4／--sp-5／--sp-6」列
    "--sp-7": "22px",   # UI_TOKENS.md §C 表「--sp-7／--sp-8」列
    "--sp-8": "26px",   # UI_TOKENS.md §C 表「--sp-7／--sp-8」列
}


@pytest.mark.parametrize("name, value", sorted(SPACING_SCALE.items()))
def test_spacing_scale_values(name, value):
    assert tokens.SPACING[name] == value


def test_spacing_scale_has_eight_strictly_increasing_steps():
    ordered = [tokens.SPACING[f"--sp-{i}"] for i in range(1, 9)]
    assert len(tokens.SPACING) == 8, "間距只有八級，⛔ 不得私自加階"
    as_px = [float(v.removesuffix("px")) for v in ordered]
    assert all(a < b for a, b in zip(as_px, as_px[1:])), f"間距階梯未嚴格遞增：{as_px}"


# ══════════════════════════════════════════════════════════════════
# A-6 取值介面：未知 token 要炸，⛔ 不得回一個預設色（§1 Fail Loud）
# ══════════════════════════════════════════════════════════════════
def test_unknown_token_raises_instead_of_returning_a_default():
    with pytest.raises(KeyError):
        tokens.get_token("--totally-made-up", mode="dark")


# ══════════════════════════════════════════════════════════════════
# A-7 色差量尺 —— ⚠️ **本檔有兩把尺，⛔ 不得互比**
#
#   ① OKLab ΔE×100 ＝ A-2「≥15 可辨門檻」的**原生度量**。
#      出處：`dataviz` skill 的 `validate_palette.js`，檔內逐字
#      `Delta E is Euclidean distance in OKLab ×100` ＋ `const NORMAL_FLOOR = 15.0;`
#   ② CIEDE2000 ＝ A-2.1「2~10 一眼可辨帶」用的尺（底色比較）。
#
# 「拿 CIEDE2000 的數字去比 15 門檻」是 UI_TOKENS.md 附錄 A-2.2 記載的
# **既有缺陷本體**；下方 `test_the_15_floor_metric_is_oklab_x100_not_ciede2000`
# 就是為了讓任何人再犯時**當場紅燈**。
# ══════════════════════════════════════════════════════════════════
import math  # noqa: E402  （量尺區段自包含，與上方 WCAG 區分開）


def _srgb_to_linear_colorimetric(channel_0_to_1: float) -> float:
    """⚠️ 門檻值 0.04045，**與 WCAG 的 0.03928 不同** —— 前者是比色學用的
    sRGB EOTF（OKLab／CIELab 走這條，`validate_palette.js` 亦同），
    後者是 WCAG 2.x 對比公式的歷史定義。⛔ 不得把兩者混成一個函式。"""
    if channel_0_to_1 <= 0.04045:
        return channel_0_to_1 / 12.92
    return ((channel_0_to_1 + 0.055) / 1.055) ** 2.4


def _linear_rgb(hex_color: str) -> tuple[float, float, float]:
    raw = hex_color.lstrip("#")
    assert len(raw) == 6, f"token 值必須是 #rrggbb 六碼：{hex_color!r}"
    return tuple(_srgb_to_linear_colorimetric(int(raw[i:i + 2], 16) / 255.0)
                 for i in (0, 2, 4))  # type: ignore[return-value]


def oklab(hex_color: str) -> tuple[float, float, float]:
    """Ottosson OKLab。係數逐字取自 `validate_palette.js::oklabFromLin`。"""
    r, g, b = _linear_rgb(hex_color)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def delta_e_oklab100(a_hex: str, b_hex: str) -> float:
    """A-2 ≥15 門檻的**原生度量**：OKLab 歐氏距離 ×100。"""
    return 100.0 * math.dist(oklab(a_hex), oklab(b_hex))


def cielab(hex_color: str) -> tuple[float, float, float]:
    """CIELab，D65 觀察者（sRGB 的原生白點）。"""
    r, g, b = _linear_rgb(hex_color)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.00000
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def ciede2000_lab(lab1: tuple[float, float, float],
                  lab2: tuple[float, float, float]) -> float:
    """CIEDE2000（Sharma / Wu / Dalal 2005 式）。kL=kC=kH=1。

    ⚠️ 直接吃 Lab，⛔ 不吃 hex —— 這樣下面的 Sharma 標準向量才驗得到本函式本身。
    """
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = 0.0 if (a1p == 0 and b1 == 0) else math.degrees(math.atan2(b1, a1p)) % 360
    h2p = 0.0 if (a2p == 0 and b2 == 0) else math.degrees(math.atan2(b2, a2p)) % 360

    d_lp = l2 - l1
    d_cp = c2p - c1p
    if c1p * c2p == 0:
        d_hp = 0.0
    elif abs(h2p - h1p) <= 180:
        d_hp = h2p - h1p
    elif h2p - h1p > 180:
        d_hp = h2p - h1p - 360
    else:
        d_hp = h2p - h1p + 360
    d_capital_hp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(d_hp) / 2)

    l_bar_p = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar_p = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar_p = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar_p = (h1p + h2p + 360) / 2
    else:
        h_bar_p = (h1p + h2p - 360) / 2

    t = (1 - 0.17 * math.cos(math.radians(h_bar_p - 30))
         + 0.24 * math.cos(math.radians(2 * h_bar_p))
         + 0.32 * math.cos(math.radians(3 * h_bar_p + 6))
         - 0.20 * math.cos(math.radians(4 * h_bar_p - 63)))
    d_theta = 30 * math.exp(-(((h_bar_p - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(c_bar_p ** 7 / (c_bar_p ** 7 + 25 ** 7))
    s_l = 1 + (0.015 * (l_bar_p - 50) ** 2) / math.sqrt(20 + (l_bar_p - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c
    return math.sqrt((d_lp / s_l) ** 2 + (d_cp / s_c) ** 2 + (d_capital_hp / s_h) ** 2
                     + r_t * (d_cp / s_c) * (d_capital_hp / s_h))


def delta_e_2000(a_hex: str, b_hex: str) -> float:
    return ciede2000_lab(cielab(a_hex), cielab(b_hex))


#: A-2 可辨門檻。**度量＝OKLab ΔE×100**（`validate_palette.js::NORMAL_FLOOR`）。
#: ⛔ 不得拿 CIEDE2000 的數字來比這個常數 —— 見附錄 A-2.2「度量單位更正」。
NORMAL_FLOOR_OKLAB100 = 15.0

#: A-2.1「一眼可辨」帶，度量＝CIEDE2000（底色之間用）。
DISTINCT_BAND_CIEDE2000 = (2.0, 10.0)


# ── Sharma 標準向量：⚠️ 沒驗過的 ΔE 實作⛔ 不准拿來給數字 ──────────
#: Sharma, Wu & Dalal (2005) "The CIEDE2000 Color-Difference Formula" 附表
#: 34 組標準測試向量：(Lab1, Lab2, 期望 ΔE00)。
SHARMA_CIEDE2000_VECTORS = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -1.1848, -84.8006), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -0.9009, -85.5211), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, -1.0000, 2.0000), (50.0000, 0.0000, 0.0000), 2.3669),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0010), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0011), 7.2195),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0012), 7.2195),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0009, -2.4900), 4.8045),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0010, -2.4900), 4.8045),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0011, -2.4900), 4.7461),
    ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
    ((50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
    ((50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


@pytest.mark.parametrize("lab1, lab2, expected",
                         SHARMA_CIEDE2000_VECTORS,
                         ids=[f"sharma{i:02d}" for i in
                              range(1, len(SHARMA_CIEDE2000_VECTORS) + 1)])
def test_ciede2000_matches_the_sharma_reference_vectors(lab1, lab2, expected):
    """⚠️ 這條先跑：ΔE2000 實作沒過 Sharma 向量，下面所有 ΔE 數字都不算數。

    Sharma 向量刻意挑在公式的**不連續處**（色相跨 0°、近中性灰、藍色區
    `R_T` 旋轉項），一個實作若漏掉 `G` 修正或 `R_T` 項，正好會在這裡爆掉。
    """
    assert ciede2000_lab(lab1, lab2) == pytest.approx(expected, abs=0.0001)


# ══════════════════════════════════════════════════════════════════
# ⭐ A-8 度量守衛 —— 本輪最重要的一條測試
#
# UI_TOKENS.md A-2 逐字寫的 15.8／16.3，是用 **OKLab×100** 算出來的。
# 這條測試同時斷言：
#   (a) OKLab×100 **重現**得了那兩個數字（⇒ 門檻 15 是這把尺）；
#   (b) CIEDE2000 **重現不了**（⇒ 那不是文件用的尺）。
# (b) 是關鍵：只寫 (a) 的話，有人把量尺換成 CIEDE2000 仍會矇混過關。
# ══════════════════════════════════════════════════════════════════
#: UI_TOKENS.md §A-2 表下註（「`--sig-blue` 與 `--sig-grey` 在 dark 的未模擬
#: ΔE 15.8、light 16.3」）逐字記載的兩個數字。
DOCUMENTED_BLUE_VS_GREY = [
    ("dark", "#4b8efe", "#8b98a4", 15.8),    # 同註「dark 的未模擬 ΔE 15.8」
    ("light", "#044cb6", "#586470", 16.3),   # 同註「light 16.3」
]


@pytest.mark.parametrize("mode, blue, grey, documented", DOCUMENTED_BLUE_VS_GREY)
def test_the_15_floor_metric_is_oklab_x100_not_ciede2000(mode, blue, grey, documented):
    """⭐ 釘住 A-2「≥15 可辨門檻」的**度量單位**。

    依據（三項，缺一不可）：
    1. `validate_palette.js` 檔內逐字 `Delta E is Euclidean distance in OKLab ×100`
       ＋ `const NORMAL_FLOOR = 15.0;`；
    2. 該檔 FAIL 訊息逐字 `below 15, hard to tell apart even with full color vision`
       ＝ UI_TOKENS.md §A-3「框架：這不是『3 槽擴 7 槽』」段引用的
       「低於 15，連全色覺的人都分不出來」；
    3. 下面的實算：**只有 OKLab×100 重現得了文件寫的 15.8／16.3。**

    ⚠️ 若日後有人把 A-2 的門檻改用 CIEDE2000 計算，本測試會**當場紅燈**
    —— 這正是它存在的唯一理由（附錄 A-2.2 記載的缺陷是拿 CIEDE2000 的
    4.85 去比 OKLab×100 的 15，兩把不同的尺互比）。
    """
    # 兩個 token 值必須真的還是這兩碼，否則下面比的是別的顏色。
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    assert table["--sig-blue"] == blue
    assert table["--sig-grey"] == grey

    oklab_100 = delta_e_oklab100(blue, grey)
    ciede = delta_e_2000(blue, grey)

    # (a) 門檻自己的尺 —— 必須重現文件數字。
    assert oklab_100 == pytest.approx(documented, abs=0.05), (
        f"{mode}: OKLab×100 ＝ {oklab_100:.4f}，對不上 UI_TOKENS.md 寫的 {documented}"
    )
    assert oklab_100 >= NORMAL_FLOOR_OKLAB100

    # (b) 另一把尺 —— **必須對不上**，否則這條守衛沒有鑑別力。
    assert abs(ciede - documented) > 0.05, (
        f"{mode}: CIEDE2000 ＝ {ciede:.4f} 竟然也重現了 {documented}，"
        "本守衛失去鑑別力 —— 請先確認量尺實作是否寫錯"
    )


def test_the_two_metrics_really_are_different_rulers():
    """把「兩把尺不一樣」本身釘成一條獨立事實，⛔ 不依賴上面任何 token 值。

    取 UI_TOKENS.md 附錄 A-2.2 記載的缺陷本體那一對（dark neutral ↔ grey）：
    CIEDE2000 ＝ 4.85，OKLab×100 ＝ 3.70 —— **同一對顏色、兩個數字**。
    """
    a, b = "#8fa3b8", "#8b98a4"
    assert delta_e_2000(a, b) == pytest.approx(4.85, abs=0.005)
    assert delta_e_oklab100(a, b) == pytest.approx(3.70, abs=0.005)
    assert delta_e_2000(a, b) != pytest.approx(delta_e_oklab100(a, b), abs=0.05)


# ══════════════════════════════════════════════════════════════════
# A-9 light `--sig-neutral` 兩碼的驗收條件 C1~C3（附錄 A-2.2）
# ══════════════════════════════════════════════════════════════════
def test_c1_light_sig_neutral_text_contrast_on_its_own_bg():
    """C1：`#1e3b4f` on `#d7dce1` ＝ 8.482:1（AA 小字 4.5，餘裕 +3.98）。"""
    got = contrast_ratio(tokens.LIGHT["--sig-neutral"], tokens.LIGHT["--sig-neutral-bg"])
    assert got == pytest.approx(8.482, abs=0.005)
    assert got >= AA_SMALL_TEXT


@pytest.mark.parametrize(
    "other_token, expected",
    [("--sig-blue-bg", 3.669),   # 徽章 #9 與 #10 的底色必須分得開
     ("--panel", 8.406)],        # 底色在卡面上必須看得見
)
def test_c2_light_sig_neutral_bg_sits_in_the_distinct_band(other_token, expected):
    """C2：底色 ΔE2000 落在「一眼可辨」帶 2~10（⛔ 此處用 CIEDE2000，非 OKLab）。"""
    got = delta_e_2000(tokens.LIGHT["--sig-neutral-bg"], tokens.LIGHT[other_token])
    assert got == pytest.approx(expected, abs=0.005)
    low, high = DISTINCT_BAND_CIEDE2000
    assert low <= got <= high, f"ΔE2000 {got:.2f} 不在 {low}~{high} 帶內"


@pytest.mark.parametrize(
    "surface, expected",
    [("--panel", 11.615), ("--paper", 10.732), ("--panel-2", 9.897)],
)
def test_c3_light_sig_neutral_fg_on_three_surfaces(surface, expected):
    """C3：比照 A-1 `--ink-3` 三背景定錨慣例，⛔ 不得只對自身 bg 定錨。"""
    got = contrast_ratio(tokens.LIGHT["--sig-neutral"], tokens.LIGHT[surface])
    assert got == pytest.approx(expected, abs=0.005)
    assert got >= AA_SMALL_TEXT


# ══════════════════════════════════════════════════════════════════
# A-10 ≥15 可辨門檻：light 前景對**全部五個** light 狀態色前景
#      （這是採 B 組 `#1e3b4f`、⛔ 不採 A 組 `#3c5063` 的整個理由）
# ══════════════════════════════════════════════════════════════════
LIGHT_STATUS_INKS = [
    ("--sig-green", 18.14),
    ("--sig-amber", 23.34),
    ("--sig-red", 26.36),
    ("--sig-blue", 17.32),
    ("--sig-grey", 16.02),   # ← 最窄的一格，也是 A 組過不了的那一格
]


@pytest.mark.parametrize("ink_token, expected", LIGHT_STATUS_INKS)
def test_light_sig_neutral_clears_the_floor_against_every_status_ink(ink_token, expected):
    """附錄 A-2.2：B 組前景對五個 light 狀態色前景**全部** ≥15（度量 OKLab×100）。"""
    got = delta_e_oklab100(tokens.LIGHT["--sig-neutral"], tokens.LIGHT[ink_token])
    assert got == pytest.approx(expected, abs=0.005)
    assert got >= NORMAL_FLOOR_OKLAB100, (
        f"light --sig-neutral ↔ {ink_token} ＝ {got:.2f} < {NORMAL_FLOOR_OKLAB100}"
    )


def test_the_unadopted_a_group_foreground_would_have_failed_the_floor():
    """反向守衛：A 組 `#3c5063` 對 light `--sig-grey` 只有 OKLab×100 7.66 ＜ 15。

    ⚠️ 這條的作用是**保住「為什麼不選 A 組」這個理由本身** ——
    若日後有人想把前景換回 `#3c5063`，這裡就是證據。
    """
    got = delta_e_oklab100("#3c5063", tokens.LIGHT["--sig-grey"])
    assert got == pytest.approx(7.66, abs=0.005)
    assert got < NORMAL_FLOOR_OKLAB100
    # 兩組**底色**其實幾乎同一個顏色，分歧完全在前景（ΔE2000 僅 0.92）。
    assert delta_e_2000("#d9dce0", tokens.LIGHT["--sig-neutral-bg"]) == pytest.approx(
        0.92, abs=0.005)


def test_light_sig_neutral_foreground_is_the_darkest_status_ink():
    """⚠️ 據實釘住**取捨的代價**：`#1e3b4f` L\\* ＝ 23.57，比其餘五個 light
    狀態色前景深約 12 個 L\\* 單位 ⇒ **這顆徽章的字會比同儕明顯重**。

    ⛔ 本測試**不是**在主張這樣比較好 —— 它是在防止這個代價被悄悄遺忘：
    若日後有人換掉這碼，這條會紅燈並把取捨重新攤開。
    """
    peers = {k: cielab(tokens.LIGHT[k])[0]
             for k, _ in LIGHT_STATUS_INKS}
    mine = cielab(tokens.LIGHT["--sig-neutral"])[0]
    assert mine == pytest.approx(23.57, abs=0.005)
    assert mine < min(peers.values()), f"不再是最深的一枚：{peers}"
    assert min(peers.values()) - mine == pytest.approx(11.57, abs=0.05)


# ══════════════════════════════════════════════════════════════════
# A-11 dark 側：⚠️ **防呆** —— 用錯尺會憑空生出一個「幽靈缺陷」
# ══════════════════════════════════════════════════════════════════
def test_dark_sig_neutral_vs_sig_blue_passes_the_floor_but_only_just():
    """⚠️ 這一對是「單位用錯會怎樣」的活例子，⛔ 不是一個缺陷：

    - CIEDE2000 ＝ **13.19** → 看起來像「第二個未登記的違規」
    - OKLab×100 ＝ **15.06** → **用門檻自己的尺是 PASS**

    ⚠️ 但餘裕只有 **0.06**，極薄 —— 動到 `--sig-neutral` 或 `--sig-blue`
    任一碼都可能掉到門檻下，本測試即為此而設。
    """
    neutral, blue = tokens.DARK["--sig-neutral"], tokens.DARK["--sig-blue"]
    oklab_100 = delta_e_oklab100(neutral, blue)
    assert oklab_100 == pytest.approx(15.06, abs=0.005)
    assert oklab_100 >= NORMAL_FLOOR_OKLAB100
    assert oklab_100 - NORMAL_FLOOR_OKLAB100 < 0.1, "餘裕極薄，⛔ 不得當成安全邊際"
    # 用錯尺會得到 13.19 —— ⛔ 不得據此登記成新缺陷。
    assert delta_e_2000(neutral, blue) == pytest.approx(13.19, abs=0.005)


def test_dark_sig_neutral_vs_sig_grey_is_still_below_the_floor():
    """🔴 **既有未解決缺陷**（dark 前景），本輪未動 —— 據實釘住，⛔ 不得當成已修。

    ⚠️ 用**門檻自己的度量**：OKLab×100 ＝ 3.70（文件原記 CIEDE2000 4.85，
    單位用錯，見附錄 A-2.2）。**結論 FAIL 不變，只是引用的數字單位錯了。**
    ✅ 對照：light 那一對已於本輪清過門檻（16.02，見上方 A-10）。
    """
    got = delta_e_oklab100(tokens.DARK["--sig-neutral"], tokens.DARK["--sig-grey"])
    assert got == pytest.approx(3.70, abs=0.005)
    assert got < NORMAL_FLOOR_OKLAB100


@pytest.mark.parametrize(
    "other_token, expected, retired_value_expected, retired_was_in_band",
    [("--sig-grey-bg", 4.77, 2.98, True),   # 舊值 2.98 ＝ 勉強在帶內（底線 2.0 之上 0.98）
     ("--panel-2", 4.10, 1.98, False)],     # 舊值 1.98 ＝ **在帶外**（低於底線）
)
def test_dark_sig_neutral_bg_clears_the_band_on_both_neighbouring_greys(
        other_token, expected, retired_value_expected, retired_was_in_band):
    """補掉 UI_TOKENS.md §A-2.1「--sig-neutral-bg 對 --sig-grey-bg／--panel-2
    本輪未重算」條自陳的缺口（三方獨立複算相符）。

    `#26313d` 對這兩個背景都**穩穩**進了 2~10 帶 ⇒ 該次換色**連帶**把這個缺口
    也修好了，只是當時沒人算。

    ⚠️ **⛔ 不得把舊值一概說成「在帶外」** —— 據實區分：
    - vs `--sig-grey-bg`：舊 **2.98**，其實**勉強在帶內**，只是貼著 2.0 底線；
    - vs `--panel-2`：舊 **1.98**，**才是真的在帶外**。
    兩格的共同點是「離底線很近」，⛔ 不是「都出界」。
    """
    now = delta_e_2000(tokens.DARK["--sig-neutral-bg"], tokens.DARK[other_token])
    assert now == pytest.approx(expected, abs=0.005)
    low, high = DISTINCT_BAND_CIEDE2000
    assert low <= now <= high

    was = delta_e_2000("#1f2a36", tokens.DARK[other_token])
    assert was == pytest.approx(retired_value_expected, abs=0.005)
    assert (low <= was <= high) is retired_was_in_band
    assert was < now, "換色後必須離得更遠，否則這個缺口沒有被補上"
    assert was - low < 1.0, "舊值貼著 2.0 底線（或在底線下）—— 這是它被換掉的原因之一"


# ══════════════════════════════════════════════════════════════════
# A-12 六對狀態色（含 neutral）ink-on-own-bg，兩模式
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("mode", ["dark", "light"])
def test_every_status_pair_passes_aa_in_both_modes(mode):
    """⚠️ neutral 的 light 值補上後，**六對都有值了** —— 這條要六對全過。

    ⛔ 不得再靠 TBD 略過任何一對（那是「還沒訂」的免死金牌，不是「訂了但沒量」的）。
    """
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    for ink, bg in tokens.STATUS_PAIRS:
        assert table[ink] is not tokens.TBD, f"{mode} {ink} 仍是 TBD"
        assert table[bg] is not tokens.TBD, f"{mode} {bg} 仍是 TBD"
        got = contrast_ratio(table[ink], table[bg])
        assert got >= AA_SMALL_TEXT, f"{mode} {ink} on {bg} = {got:.2f}"


# ══════════════════════════════════════════════════════════════════
# A-13 ⚠️ `TBD` 哨兵機制**本身**仍要有測試守著
#
# 本輪把 `--sig-neutral` / `--sig-neutral-bg` 的 light 值補掉之後，
# 表裡已經**沒有任何一個 TBD**。若不補這一段，`get_token()` 的
# `raise TokenNotSpecifiedError` 路徑就會變成**沒人測的死碼** ——
# 而它是通用機制（下一個「客戶只給 dark」的 token 還要靠它 fail loud）。
# ⇒ 改用**合成 token** 測機制，⛔ 不動 `tokens.py` 的機制本身。
# ══════════════════════════════════════════════════════════════════
def test_tbd_sentinel_is_not_a_falsy_lookalike():
    """`TBD` ⛔ 不是 None／空字串／近似色 —— 且真值為假，讓 `if token:` 不會誤用。"""
    assert tokens.TBD is not None
    assert not isinstance(tokens.TBD, str)
    assert bool(tokens.TBD) is False
    assert issubclass(tokens.TokenNotSpecifiedError, KeyError)


def test_no_token_is_silently_left_as_tbd_today():
    """現況快照：兩張表目前**都不該**還有 TBD（light 兩碼已補）。

    ⚠️ 這條紅了不代表機制壞了，代表**有人新增了未指定的 token 卻沒登記**。
    """
    left = [(mode, k) for mode, t in (("dark", tokens.DARK), ("light", tokens.LIGHT))
            for k, v in t.items() if v is tokens.TBD]
    assert left == [], f"仍有未指定的 token：{left}"


def test_get_token_still_raises_for_a_tbd_value(monkeypatch):
    """⭐ 機制守衛：用**合成 token** 走一遍 `TokenNotSpecifiedError` 路徑。

    ⚠️ 這裡刻意碰私有的 `_MODES` —— 因為要測的就是「表裡出現 TBD 時會不會炸」，
    而現實的表裡已經沒有 TBD 了。先斷言 `_MODES` 還在，避免它被改名後
    本測試**靜默失效**（變成測不到東西卻還是綠的）。
    """
    assert hasattr(tokens, "_MODES"), "get_token 的查表結構換了 —— 本機制守衛需同步更新"
    assert set(tokens._MODES) == {"dark", "light"}

    synthetic = "--synthetic-token-that-the-client-has-not-specified"
    assert synthetic not in tokens.DARK, "合成 token 名撞到真 token 了"
    monkeypatch.setattr(
        tokens, "_MODES",
        {mode: {**dict(table), synthetic: tokens.TBD}
         for mode, table in tokens._MODES.items()},
    )

    for mode in ("dark", "light"):
        with pytest.raises(tokens.TokenNotSpecifiedError):
            tokens.get_token(synthetic, mode=mode)
        # ⛔ 不得回退到另一模式、⛔ 不得回傳近似色 —— 真 token 仍正常。
        assert tokens.get_token("--paper", mode=mode) == (
            "#0e141b" if mode == "dark" else "#f6f5f1")


def test_get_token_rejects_an_unknown_mode():
    with pytest.raises(ValueError):
        tokens.get_token("--paper", mode="sepia")
