"""WT 測試組｜test-first 契約 A：設計 token（`src/ui_v2/tokens.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/` 尚不存在，
   本檔因此**應該是紅燈（ModuleNotFoundError）** —— 紅燈即正確結果。
   實作組的任務＝把下面這份 API 做出來、讓它轉綠，⛔ 不是改本檔讓它變綠。

唯一資料來源：`docs/v2/spec/UI_TOKENS.md`（每條 assert 旁以 `# UI_TOKENS.md:NN` 標出處）。
⛔ 本檔未引用 `src/ui/` 任何既有檔案、未引用舊原型 `ui_prototype_today.html`。
⛔ 本檔不 import streamlit —— 這一層測的是**純資料契約**（token 值），不是渲染。

────────────────────────────────────────────────────────────────────
實作組必須提供：`src/ui_v2/tokens.py`
────────────────────────────────────────────────────────────────────
`TBD` : object
    哨兵值，意思是「**客戶尚未指定**」。
    ⛔ 不得用 `None`／空字串／自己挑一個近似色頂替
    （UI_TOKENS.md:53「客戶 2026-09-21 只指定 dark 兩碼，⛔ 本檔不得自行發明 light 值」
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


#: WCAG AA 小字門檻。UI_TOKENS.md:32／:58 明文 ⛔ 不得套大字 3:1 寬鬆標準
#: （落點字級 9.5px／11px／11.5px，遠低於 18.66px bold／24px 大字門檻）。
AA_SMALL_TEXT = 4.5


# ══════════════════════════════════════════════════════════════════
# A-0 先驗證「量尺」本身有牙齒：拿 UI_TOKENS.md 自己記載的**舊缺陷值**
#     回算，必須算得出 FAIL。這條擋的是「有人把對比函式寫成恆過」。
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "fg, bg, expected, label",
    [
        # UI_TOKENS.md:33 舊 dark --ink-3 `#73838f`：對 --paper 4.73 PASS，
        # 但對 --panel 4.35、--panel-2 4.01 兩格 FAIL（＝該缺陷本體）。
        ("#73838f", "#0e141b", 4.73, "舊 dark ink-3 on --paper"),
        ("#73838f", "#151d26", 4.35, "舊 dark ink-3 on --panel（FAIL）"),
        ("#73838f", "#1b242f", 4.01, "舊 dark ink-3 on --panel-2（FAIL）"),
        # UI_TOKENS.md:33 舊 light --ink-3 `#626f7a`：對 --panel-2 4.36 FAIL。
        ("#626f7a", "#edece7", 4.36, "舊 light ink-3 on --panel-2（FAIL）"),
        # UI_TOKENS.md:48 line --sig-grey 舊值 `#6c7883` 對自身 bg 僅 3.71。
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
# A-1 面與墨 token（dark 為主要交付；UI_TOKENS.md:4）
# ══════════════════════════════════════════════════════════════════
DARK_SURFACE_AND_INK = {
    "--ochre":   "#d59a5e",   # UI_TOKENS.md:23
    "--focus":   "#8fc0ff",   # UI_TOKENS.md:25
    "--paper":   "#0e141b",   # UI_TOKENS.md:26
    "--panel":   "#151d26",   # UI_TOKENS.md:26
    "--panel-2": "#1b242f",   # UI_TOKENS.md:26
    "--rule":    "#2e3b48",   # UI_TOKENS.md:27
    "--rule-2":  "#46545f",   # UI_TOKENS.md:27
    "--ink":     "#dbe5ef",   # UI_TOKENS.md:28
    "--ink-2":   "#9fb0c1",   # UI_TOKENS.md:28
    "--ink-3":   "#7d8d99",   # UI_TOKENS.md:29（2026-09-16 自 #73838f 改）
}


@pytest.mark.parametrize("name, value", sorted(DARK_SURFACE_AND_INK.items()))
def test_dark_surface_and_ink_tokens(name, value):
    assert tokens.DARK[name] == value
    assert tokens.get_token(name, mode="dark") == value


def test_light_ink_3_is_the_post_fix_value():
    # UI_TOKENS.md:29 light --ink-3 `#5f6c77`（前輪 `#626f7a` 已退場）
    assert tokens.LIGHT["--ink-3"] == "#5f6c77"


def test_dark_and_light_cover_the_same_token_names():
    # 兩模式必須同一組鍵；缺的那邊用 TBD 表示，⛔ 不是整個鍵消失。
    assert set(tokens.DARK) == set(tokens.LIGHT)


def test_ink_ramp_is_strictly_monotonic_in_both_modes():
    """UI_TOKENS.md:33「--ink→--ink-2→--ink-3 的 L* 兩模式皆嚴格單調」。

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
    "--sig-green":      "#57b985",   # UI_TOKENS.md:39
    "--sig-green-bg":   "#11241a",   # UI_TOKENS.md:39
    "--sig-amber":      "#d3a43c",   # UI_TOKENS.md:40
    "--sig-amber-bg":   "#292110",   # UI_TOKENS.md:40
    "--sig-red":        "#e8706b",   # UI_TOKENS.md:41
    "--sig-red-bg":     "#2b1615",   # UI_TOKENS.md:41
    "--sig-blue":       "#4b8efe",   # UI_TOKENS.md:42
    "--sig-blue-bg":    "#141f2b",   # UI_TOKENS.md:42
    "--sig-grey":       "#8b98a4",   # UI_TOKENS.md:43
    "--sig-grey-bg":    "#1b232b",   # UI_TOKENS.md:43
    "--sig-neutral":    "#8fa3b8",   # UI_TOKENS.md:44（2026-09-21 客戶裁示）
    "--sig-neutral-bg": "#26313d",   # UI_TOKENS.md:44／:62（同日自 #1f2a36 改）
}


@pytest.mark.parametrize("name, value", sorted(DARK_STATUS.items()))
def test_dark_status_tokens(name, value):
    assert tokens.DARK[name] == value


def test_sig_neutral_bg_is_the_new_value_not_the_retired_one():
    # UI_TOKENS.md:54／:62 舊值 `#1f2a36` 已退場（ΔE 只改善 0.09、底在卡上看不見）
    assert tokens.DARK["--sig-neutral-bg"] != "#1f2a36"
    # UI_TOKENS.md:63 `#2b3947` 評估過但**未採用**（文字對比掉到 4.55、餘裕太薄）
    assert tokens.DARK["--sig-neutral-bg"] != "#2b3947"


@pytest.mark.parametrize("name", ["--sig-neutral", "--sig-neutral-bg"])
def test_sig_neutral_light_is_tbd_and_must_not_be_invented(name):
    """UI_TOKENS.md:53「⛔ 本檔不得自行發明 light 值；light 模式落地前必須回頭補量」。

    ⇒ 實作必須讓它**炸開**，⛔ 不得回退 dark 值、⛔ 不得填一個近似色。
    """
    assert tokens.LIGHT[name] is tokens.TBD
    with pytest.raises(tokens.TokenNotSpecifiedError):
        tokens.get_token(name, mode="light")


def test_status_pairs_cover_six_ink_bg_couples():
    # UI_TOKENS.md:39-44 五枚狀態色 ＋ :44 新增 neutral
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
    # UI_TOKENS.md:32 本輪六格實算：dark 5.41／4.97／4.58；light 4.94／5.34／4.55
    ("dark", "--paper", 5.41),
    ("dark", "--panel", 4.97),
    ("dark", "--panel-2", 4.58),
    ("light", "--paper", 4.94),
    ("light", "--panel", 5.34),
    ("light", "--panel-2", 4.55),
]


@pytest.mark.parametrize("mode, surface, expected", INK3_SIX_CELLS)
def test_ink_3_passes_aa_on_all_three_surfaces(mode, surface, expected):
    """UI_TOKENS.md:32「--ink-3 一律對 --paper／--panel／--panel-2 三個背景都量，
    ⛔ 不得只對 --paper 定錨」→ 六格全 ≥ 4.5。"""
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    got = contrast_ratio(table["--ink-3"], table[surface])
    assert got == pytest.approx(expected, abs=0.005)
    assert got >= AA_SMALL_TEXT, f"{mode} --ink-3 on {surface} = {got:.2f} < {AA_SMALL_TEXT}"


def test_sig_neutral_on_its_own_bg_passes_aa():
    # UI_TOKENS.md:58「#8fa3b8 on #26313d ＝ 5.10:1」，徽章字級 11px／10.5px
    got = contrast_ratio(tokens.DARK["--sig-neutral"], tokens.DARK["--sig-neutral-bg"])
    assert got == pytest.approx(5.10, abs=0.005)
    assert got >= AA_SMALL_TEXT


@pytest.mark.parametrize(
    "surface, expected",
    [("--panel", 6.55), ("--paper", 7.14), ("--panel-2", 6.04)],  # UI_TOKENS.md:74
)
def test_sig_neutral_on_three_dark_surfaces(surface, expected):
    """UI_TOKENS.md:74「比照 A-1 --ink-3 三背景定錨慣例，三格皆 ≥ 4.5 PASS」。"""
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
    """UI_TOKENS.md:90「狀態色五枚 ink-on-own-bg WCAG AA 4.5:1 dark 5/5、light 5/5 PASS」。"""
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    got = contrast_ratio(table[ink], table[bg])
    assert got >= AA_SMALL_TEXT, f"{mode} {ink} on {bg} = {got:.2f}"


# ══════════════════════════════════════════════════════════════════
# A-4 序列識別色 7 槽
# ══════════════════════════════════════════════════════════════════
SERIES_DARK = ("#2e64a6", "#c7843c", "#209993", "#c15dde",
               "#6f650d", "#934d6b", "#7a3ae2")          # UI_TOKENS.md:80-86
SERIES_LIGHT = ("#2482eb", "#b47227", "#1b9690", "#b118a5",
                "#5b5e00", "#ff3282", "#7612e0")         # UI_TOKENS.md:80-86


@pytest.mark.parametrize("slot_index, value", list(enumerate(SERIES_DARK)))
def test_series_dark_seven_slots_fixed_order(slot_index, value):
    assert tokens.SERIES_DARK[slot_index] == value


@pytest.mark.parametrize("slot_index, value", list(enumerate(SERIES_LIGHT)))
def test_series_light_seven_slots_fixed_order(slot_index, value):
    assert tokens.SERIES_LIGHT[slot_index] == value


@pytest.mark.parametrize("palette_name", ["SERIES_DARK", "SERIES_LIGHT"])
def test_series_palette_has_exactly_seven_distinct_slots(palette_name):
    # UI_TOKENS.md:76「7 槽，固定順序、⛔ 不循環；第 8 條以上折成『其他』或分面」
    palette = getattr(tokens, palette_name)
    assert len(palette) == 7
    assert len(set(palette)) == 7


@pytest.mark.parametrize("mode, palette_name", [("dark", "SERIES_DARK"), ("light", "SERIES_LIGHT")])
def test_status_colors_are_reserved_and_never_reused_as_series(mode, palette_name):
    """UI_TOKENS.md:35／:76「狀態色是保留色：⛔ 不得挪用為圖表第 N 條線」。"""
    table = tokens.DARK if mode == "dark" else tokens.LIGHT
    status_inks = {table[ink] for ink, _bg in tokens.STATUS_PAIRS
                   if table[ink] is not tokens.TBD}
    assert status_inks.isdisjoint(set(getattr(tokens, palette_name)))


# ══════════════════════════════════════════════════════════════════
# A-5 間距八級
# ══════════════════════════════════════════════════════════════════
SPACING_SCALE = {
    "--sp-1": "4px",    # UI_TOKENS.md:117
    "--sp-2": "6px",    # UI_TOKENS.md:117
    "--sp-3": "8px",    # UI_TOKENS.md:117
    "--sp-4": "10px",   # UI_TOKENS.md:118
    "--sp-5": "12px",   # UI_TOKENS.md:118
    "--sp-6": "16px",   # UI_TOKENS.md:118
    "--sp-7": "22px",   # UI_TOKENS.md:119
    "--sp-8": "26px",   # UI_TOKENS.md:119
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
