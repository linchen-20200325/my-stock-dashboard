"""戰情室 v2 設計 token —— 純資料層（契約 A）。

唯一資料來源：`docs/v2/spec/UI_TOKENS.md`
（每個值旁以 `# UI_TOKENS.md <章節名>` 標出處；⛔ 不寫行號 —— CLAUDE.md §8.2.A.0 規則 1）。
⛔ 本檔不 import streamlit：token 是**框架無關的純資料**，要能在沙箱單測。
⛔ 本檔不引用 `shared/colors.py`（該檔自陳 AUTO-SYNCED FROM my-fund-dashboard，
   改了會被 `scripts/sync_to_stock.sh` 蓋掉
   —— UI_TOKENS.md §0 落地位置表「token 落地」與「`shared/colors.py`」兩列）。

**深色為實際運行模式，dark 值為主要交付；light 值次要**（UI_TOKENS.md 檔頭基準段逐字）。

§1 Fail Loud 在本層的落點：客戶尚未指定的值一律存 `TBD` 哨兵，
取值時 `raise TokenNotSpecifiedError`，⛔ 不得回退到 dark 值、⛔ 不得填近似色。

⚠️ **`TBD` 機制目前沒有任何 token 在用**（`--sig-neutral` / `--sig-neutral-bg`
的 light 值已於 2026-09-21 補上，見 UI_TOKENS.md 附錄 A-2.2）。
⛔ **機制本身不得因此刪除** —— 它是通用的：下一個「客戶只給 dark」的 token
還要靠它 fail loud。守衛見 `tests/ui_v2/test_tokens.py::test_get_token_still_raises_for_a_tbd_value`
（以合成 token 走一遍 raise 路徑，⛔ 不讓它變成沒人測的死碼）。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping


class _TBD:
    """「客戶尚未指定」哨兵。⛔ 不是 `None`、⛔ 不是空字串、⛔ 不是近似色。"""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - 診斷用
        return "<TBD 客戶尚未指定>"

    def __bool__(self) -> bool:
        # 真值為假，讓 `if token:` 這種寫法不會誤把未指定當成有值。
        return False


TBD: Final = _TBD()


class TokenNotSpecifiedError(KeyError):
    """token 存在，但客戶尚未指定該模式的值 —— 寧可炸掉，不可造假（CLAUDE.md §1）。"""


# ══════════════════════════════════════════════════════════════════
# A-1 主色／輔色／面與墨 —— UI_TOKENS.md §A-1 表
# A-2 狀態色 —— UI_TOKENS.md §A-2 狀態色表
# ══════════════════════════════════════════════════════════════════
_DARK: Final[dict[str, str]] = {
    # ── A-1 ──────────────────────────────────────────────────────
    "--ochre":        "#d59a5e",   # UI_TOKENS.md §A-1 表「--ochre」列
    "--ochre-bg":     "#2a2013",   # UI_TOKENS.md §A-1 表「--ochre-bg／--ochre-line」列
    "--ochre-line":   "#8a6234",   # UI_TOKENS.md §A-1 表「--ochre-bg／--ochre-line」列
    "--focus":        "#8fc0ff",   # UI_TOKENS.md §A-1 表「--focus」列
    "--paper":        "#0e141b",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--panel":        "#151d26",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--panel-2":      "#1b242f",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--grid":         "#1a242e",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--rule":         "#2e3b48",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--rule-2":       "#46545f",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--ink":          "#dbe5ef",   # UI_TOKENS.md §A-1 表「--ink／--ink-2」列
    "--ink-2":        "#9fb0c1",   # UI_TOKENS.md §A-1 表「--ink／--ink-2」列
    "--ink-3":        "#7d8d99",   # UI_TOKENS.md §A-1 表「--ink-3」列（2026-09-16 自 #73838f 改；舊值在卡面 FAIL）
    "--review-bg":    "#1d1b28",   # UI_TOKENS.md §A-1 表「--review-*」列（僅審稿模式）
    "--review-line":  "#8b82b4",   # UI_TOKENS.md §A-1 表「--review-*」列
    "--review-ink":   "#c3bbe4",   # UI_TOKENS.md §A-1 表「--review-*」列
    # ── A-2 ──────────────────────────────────────────────────────
    "--sig-green":      "#57b985",  # UI_TOKENS.md §A-2 表「--sig-green」列
    "--sig-green-bg":   "#11241a",  # UI_TOKENS.md §A-2 表「--sig-green」列
    "--sig-amber":      "#d3a43c",  # UI_TOKENS.md §A-2 表「--sig-amber」列
    "--sig-amber-bg":   "#292110",  # UI_TOKENS.md §A-2 表「--sig-amber」列
    "--sig-red":        "#e8706b",  # UI_TOKENS.md §A-2 表「--sig-red」列
    "--sig-red-bg":     "#2b1615",  # UI_TOKENS.md §A-2 表「--sig-red」列
    "--sig-blue":       "#4b8efe",  # UI_TOKENS.md §A-2 表「--sig-blue」列
    "--sig-blue-bg":    "#141f2b",  # UI_TOKENS.md §A-2 表「--sig-blue」列
    "--sig-grey":       "#8b98a4",  # UI_TOKENS.md §A-2 表「--sig-grey」列
    "--sig-grey-bg":    "#1b232b",  # UI_TOKENS.md §A-2 表「--sig-grey」列
    # 以下兩筆同出 UI_TOKENS.md §A-2 表「--sig-neutral／--sig-neutral-bg」列。
    "--sig-neutral":    "#8fa3b8",  # 客戶 2026-09-21 裁示
    # bg 另見 §A-2.1「總管建議值…客戶已於 2026-09-21 採納：#26313d」條
    #（同日自 #1f2a36 改；⛔ 非評估過但未採用的 #2b3947）
    "--sig-neutral-bg": "#26313d",
}

_LIGHT: Final[dict[str, object]] = {
    # ── A-1 ──────────────────────────────────────────────────────
    "--ochre":        "#96591f",   # UI_TOKENS.md §A-1 表「--ochre」列
    "--ochre-bg":     "#f6ecdf",   # UI_TOKENS.md §A-1 表「--ochre-bg／--ochre-line」列
    "--ochre-line":   "#c08a4e",   # UI_TOKENS.md §A-1 表「--ochre-bg／--ochre-line」列
    "--focus":        "#14508f",   # UI_TOKENS.md §A-1 表「--focus」列
    "--paper":        "#f6f5f1",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--panel":        "#fffefc",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--panel-2":      "#edece7",   # UI_TOKENS.md §A-1 表「--paper／--panel／--panel-2」列
    "--grid":         "#e5e3dc",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--rule":         "#c6ccd2",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--rule-2":       "#9aa4af",   # UI_TOKENS.md §A-1 表「--grid／--rule／--rule-2」列
    "--ink":          "#15293f",   # UI_TOKENS.md §A-1 表「--ink／--ink-2」列
    "--ink-2":        "#4b5b6d",   # UI_TOKENS.md §A-1 表「--ink／--ink-2」列
    "--ink-3":        "#5f6c77",   # UI_TOKENS.md §A-1 表「--ink-3」列（前輪 #626f7a 已退場）
    "--review-bg":    "#eceaf2",   # UI_TOKENS.md §A-1 表「--review-*」列
    "--review-line":  "#6f6790",   # UI_TOKENS.md §A-1 表「--review-*」列
    "--review-ink":   "#4a4270",   # UI_TOKENS.md §A-1 表「--review-*」列
    # ── A-2 ──────────────────────────────────────────────────────
    "--sig-green":      "#1c6f43",  # UI_TOKENS.md §A-2 表「--sig-green」列
    "--sig-green-bg":   "#e3f0e9",  # UI_TOKENS.md §A-2 表「--sig-green」列
    "--sig-amber":      "#87600a",  # UI_TOKENS.md §A-2 表「--sig-amber」列
    "--sig-amber-bg":   "#f6efdb",  # UI_TOKENS.md §A-2 表「--sig-amber」列
    "--sig-red":        "#ae2f2b",  # UI_TOKENS.md §A-2 表「--sig-red」列
    "--sig-red-bg":     "#f8e7e5",  # UI_TOKENS.md §A-2 表「--sig-red」列
    "--sig-blue":       "#044cb6",  # UI_TOKENS.md §A-2 表「--sig-blue」列
    "--sig-blue-bg":    "#e4ecf3",  # UI_TOKENS.md §A-2 表「--sig-blue」列
    "--sig-grey":       "#586470",  # UI_TOKENS.md §A-2 表「--sig-grey」列（自線框 #6c7883 下修）
    "--sig-grey-bg":    "#eae9e4",  # UI_TOKENS.md §A-2 表「--sig-grey」列
    # UI_TOKENS.md 附錄 A-2.2（2026-09-21，B 組值）：TBD 已解除。
    # ⚠️ 決策者＝**AI 總管**，⛔ 不是客戶 —— 客戶只指派「補這個洞」、⛔ 未指定值；
    #    總管自兩組獨立量測中選 B 組。⛔ 不得寫成「客戶核准」。**可被客戶一句話推翻。**
    # ⛔ 非 dark 值回退（dark 是 #8fa3b8／#26313d）、⛔ 非未採用的 A 組 #3c5063／#d9dce0。
    "--sig-neutral":    "#1e3b4f",  # 附錄 A-2.2：on 自身 bg 8.482:1；對五個 light
                                    # 狀態色前景 OKLab×100 全 ≥15（最窄 grey 16.02）
    "--sig-neutral-bg": "#d7dce1",  # 附錄 A-2.2：vs --sig-blue-bg ΔE2000 3.669、
                                    # vs --panel 8.406，兩格皆在 2~10 可辨帶
}

assert set(_DARK) == set(_LIGHT), "dark／light 必須覆蓋同一組 token 名（缺的那邊用 TBD）"

DARK: Final[Mapping[str, str]] = MappingProxyType(_DARK)
LIGHT: Final[Mapping[str, object]] = MappingProxyType(_LIGHT)

#: A-2 狀態色 (ink, bg) 配對，依 UI_TOKENS.md §A-2 狀態色表順序。
STATUS_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("--sig-green", "--sig-green-bg"),      # UI_TOKENS.md §A-2 表「--sig-green」列
    ("--sig-amber", "--sig-amber-bg"),      # UI_TOKENS.md §A-2 表「--sig-amber」列
    ("--sig-red", "--sig-red-bg"),          # UI_TOKENS.md §A-2 表「--sig-red」列
    ("--sig-blue", "--sig-blue-bg"),        # UI_TOKENS.md §A-2 表「--sig-blue」列
    ("--sig-grey", "--sig-grey-bg"),        # UI_TOKENS.md §A-2 表「--sig-grey」列
    ("--sig-neutral", "--sig-neutral-bg"),  # UI_TOKENS.md §A-2 表「--sig-neutral／--sig-neutral-bg」列
)

# ══════════════════════════════════════════════════════════════════
# A-3 圖表序列識別色 —— 7 槽，固定順序、⛔ 不循環（UI_TOKENS.md §A-3 表）
# 第 8 條以上折成「其他」或分面；⛔ 狀態色是保留色，不得挪用為第 N 條線。
# 🔴 附帶條件（UI_TOKENS.md §A-3「🔴 有拘束力的附帶條件（必須實作；
#    客戶 2026-09-16 裁示，門檻自「第 6、7 槽」下修）」段）：
#    同時使用 ≥4 槽時一律強制直接標籤或紋理，
#    ⛔ 不得只靠顏色區分（light 連 3 槽都不免除）—— 由繪圖層落實，本層只供色。
# ══════════════════════════════════════════════════════════════════
SERIES_DARK: Final[tuple[str, ...]] = (
    "#2e64a6",  # UI_TOKENS.md §A-3 表 槽 1
    "#c7843c",  # UI_TOKENS.md §A-3 表 槽 2
    "#209993",  # UI_TOKENS.md §A-3 表 槽 3
    "#c15dde",  # UI_TOKENS.md §A-3 表 槽 4
    "#6f650d",  # UI_TOKENS.md §A-3 表 槽 5
    "#934d6b",  # UI_TOKENS.md §A-3 表 槽 6
    "#7a3ae2",  # UI_TOKENS.md §A-3 表 槽 7
)
SERIES_LIGHT: Final[tuple[str, ...]] = (
    "#2482eb",  # UI_TOKENS.md §A-3 表 槽 1
    "#b47227",  # UI_TOKENS.md §A-3 表 槽 2
    "#1b9690",  # UI_TOKENS.md §A-3 表 槽 3
    "#b118a5",  # UI_TOKENS.md §A-3 表 槽 4
    "#5b5e00",  # UI_TOKENS.md §A-3 表 槽 5
    "#ff3282",  # UI_TOKENS.md §A-3 表 槽 6
    "#7612e0",  # UI_TOKENS.md §A-3 表 槽 7
)

# ══════════════════════════════════════════════════════════════════
# C. 間距 token（UI_TOKENS.md §C 表 --sp-1~--sp-8 三列）—— 八級，與 dark/light 無關。
# ══════════════════════════════════════════════════════════════════
SPACING: Final[Mapping[str, str]] = MappingProxyType({
    "--sp-1": "4px",    # UI_TOKENS.md §C 表「--sp-1／--sp-2／--sp-3」列
    "--sp-2": "6px",    # UI_TOKENS.md §C 表「--sp-1／--sp-2／--sp-3」列
    "--sp-3": "8px",    # UI_TOKENS.md §C 表「--sp-1／--sp-2／--sp-3」列
    "--sp-4": "10px",   # UI_TOKENS.md §C 表「--sp-4／--sp-5／--sp-6」列
    "--sp-5": "12px",   # UI_TOKENS.md §C 表「--sp-4／--sp-5／--sp-6」列
    "--sp-6": "16px",   # UI_TOKENS.md §C 表「--sp-4／--sp-5／--sp-6」列
    "--sp-7": "22px",   # UI_TOKENS.md §C 表「--sp-7／--sp-8」列
    "--sp-8": "26px",   # UI_TOKENS.md §C 表「--sp-7／--sp-8」列
})

_MODES: Final[dict[str, Mapping[str, object]]] = {"dark": DARK, "light": LIGHT}


def get_token(name: str, *, mode: str) -> str:
    """取單一 token 值。

    - `mode` 不是 `"dark"`／`"light"` → `ValueError`
    - 未知 `name` → `KeyError`（⛔ 不回傳預設色，CLAUDE.md §1）
    - 值為 `TBD` → `TokenNotSpecifiedError`（⛔ 不偷偷回退到 dark 值）
    """
    try:
        table = _MODES[mode]
    except KeyError:
        raise ValueError(f"mode 只能是 'dark' 或 'light'，收到 {mode!r}") from None

    if name not in table:
        raise KeyError(f"未知的 token：{name!r}（token SSOT 在 docs/v2/spec/UI_TOKENS.md）")

    value = table[name]
    if value is TBD:
        raise TokenNotSpecifiedError(
            f"{name!r} 的 {mode} 值客戶尚未指定（SSOT：docs/v2/spec/UI_TOKENS.md）"
            "：⛔ 不得回退到另一模式、⛔ 不得自行發明近似色，落地前必須回頭補量。"
        )
    return value  # type: ignore[return-value]


__all__ = [
    "TBD",
    "TokenNotSpecifiedError",
    "DARK",
    "LIGHT",
    "SPACING",
    "SERIES_DARK",
    "SERIES_LIGHT",
    "STATUS_PAIRS",
    "get_token",
]
