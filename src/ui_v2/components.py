"""戰情室 v2 元件規格 —— 純資料層（契約 B）。

唯一資料來源：`docs/v2/spec/UI_COMPONENTS.md`（每個值旁以 `# UI_COMPONENTS.md:NN` 標出處）。
⛔ 本檔不 import streamlit：元件規格是**框架無關的純資料**。

**SSOT 分工（UI_COMPONENTS.md:7-9）**：顏色／字級／間距／圓角的唯一真相源是
`UI_TOKENS.md`（＝ `src/ui_v2/tokens.py`）⇒ 本檔一律存 **token 名**（如 `"--rule-2"`），
⛔ 不把 hex 複製進來（那會製造第二個真相源，違 CLAUDE.md §2.1）。

**狀態常數 SSOT（UI_COMPONENTS.md:51-52）**：七態的唯一真相源是既有 L0
`shared/ui_state.py`；本檔的 `state_const` 只存**常數名字串**，
⛔ 不在 `src/ui_v2/` 重新宣告 `UI_LIVE`／`UI_IDLE`／… 任何一個。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


# ══════════════════════════════════════════════════════════════════
# 1. 卡片（四層密度）—— UI_COMPONENTS.md:35-47
# ══════════════════════════════════════════════════════════════════
#: `.blk` 基準（UI_COMPONENTS.md:35）。
CARD_BASE: Final[Mapping[str, object]] = _frozen({
    "background": "--panel",     # UI_COMPONENTS.md:35 `background:var(--panel)`
    "border_width_px": 1.0,      # UI_COMPONENTS.md:35 `border:1px solid var(--rule-2)`
    "border_style": "solid",     # UI_COMPONENTS.md:35
    "border_color": "--rule-2",  # UI_COMPONENTS.md:35
    "radius_px": 2.0,            # UI_COMPONENTS.md:35 `border-radius:2px`
})

#: 四層密度階梯。⚠️ `padding_px` 為 (上下, 左右)。
#: `title_color` 只有 t4 由規格指定（`--ink-2`）；t1~t3 規格未覆寫 → `None`＝承襲卡面主文字色。
CARD_TIERS: Final[Mapping[str, Mapping[str, object]]] = _frozen({
    # UI_COMPONENTS.md:40 t1 結論
    "t1": _frozen({
        "padding_px": (15.0, 17.0),
        "padding_mobile_px": (11.0, 12.0),   # ≤640；四階中只有 t1 有覆寫值
        "radius_px": 2.0,
        "border_width_px": 2.0,              # **2px** solid
        "border_style": "solid",
        "border_color": "--rule-2",
        "shadow": None,                      # UI_COMPONENTS.md:45 ⛔ 不得發明陰影
        "margin_top_px": 15.0,
        "title_px": 17.5,
        "title_weight": 700,
        "title_color": None,
        "badge_size": "b1",                  # UI_COMPONENTS.md:56 t1→b1
    }),
    # UI_COMPONENTS.md:41 t2 核心（`--sp-4` `--sp-5`）
    "t2": _frozen({
        "padding_px": (10.0, 12.0),
        "padding_mobile_px": None,
        "radius_px": 2.0,
        "border_width_px": 1.0,
        "border_style": "solid",
        "border_color": "--rule-2",
        "shadow": None,
        "margin_top_px": 10.0,               # `margin-top:10px`（`--sp-4`）
        "title_px": 14.5,
        "title_weight": 700,
        "title_color": None,
        "badge_size": "b2",
    }),
    # UI_COMPONENTS.md:42 t3 操作（`--sp-2` ＋ 9px）
    "t3": _frozen({
        "padding_px": (6.0, 9.0),
        "padding_mobile_px": None,
        "radius_px": 2.0,
        "border_width_px": 1.0,
        "border_style": "solid",
        "border_color": "--rule-2",
        "shadow": None,
        "margin_top_px": 6.0,                # `margin-top:6px`（`--sp-2`）
        "title_px": 13.0,
        "title_weight": 700,
        "title_color": None,
        "badge_size": "b3",
    }),
    # UI_COMPONENTS.md:43 t4 佐證
    "t4": _frozen({
        "padding_px": (5.0, 9.0),
        "padding_mobile_px": None,
        "radius_px": 2.0,
        "border_width_px": 1.0,
        "border_style": "dashed",            # 四階中唯一的 dashed
        "border_color": "--rule-2",
        "shadow": None,
        "margin_top_px": 5.0,
        "title_px": 12.5,
        "title_weight": 700,
        "title_color": "--ink-2",            # UI_COMPONENTS.md:43 唯一指定 title 色的一階
        "badge_size": "b4",
    }),
})

#: 面板 `.pan`（UI_COMPONENTS.md:46）—— 與卡片是兩種容器，⛔ 不共用階梯。
PANEL: Final[Mapping[str, object]] = _frozen({
    "padding_px": (12.0, 14.0),
    "radius_px": 3.0,
    "border_width_px": 1.0,
    "border_style": "solid",
    "border_color": "--rule",
    "background": "--panel",
})

#: 標記態 `.blk.flagged`（UI_COMPONENTS.md:47）：產品模式下改回 solid。
CARD_FLAGGED: Final[Mapping[str, object]] = _frozen({
    "border_color": "--ochre-line",
    "border_style": "dashed",
    "border_style_product_mode": "solid",
})

# 四層由層序自動掛（UI_COMPONENTS.md:36「⛔ 非逐塊手選」）。
# layer 0 ＝ 葉外 chrome（UI_PAGE_TODAY.md:14，據實列出、不計入四層）走 t3。
_LAYER_TIER: Final[Mapping[int, str]] = _frozen({
    0: "t3",   # UI_PAGE_TODAY.md:14
    1: "t1",   # UI_PAGE_TODAY.md:15
    2: "t2",   # UI_PAGE_TODAY.md:16
    3: "t3",   # UI_PAGE_TODAY.md:17
    4: "t4",   # UI_PAGE_TODAY.md:18
})


def tier_for_layer(layer: int) -> str:
    """層序 → 卡密度。**⛔ 刻意不提供任何覆寫參數** —— 這正是

    UI_COMPONENTS.md:36「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」的落地形式：
    只要簽名裡沒有 `tier=`／`density=`，手選在結構上就不可能發生。
    """
    try:
        return _LAYER_TIER[layer]
    except KeyError:
        raise ValueError(
            f"未知的層序 {layer!r}：只有 0（葉外 chrome）與 1~4 四層"
        ) from None


# ══════════════════════════════════════════════════════════════════
# 2. 徽章（10 種）—— UI_COMPONENTS.md:49-96
# ══════════════════════════════════════════════════════════════════
#: 10 種共用幾何（線框 `.bdg`，UI_COMPONENTS.md:53-54）。
BADGE_BASE: Final[Mapping[str, object]] = _frozen({
    "display": "inline-flex",
    "gap_px": 4.0,
    "radius_px": 3.0,
    "padding_px": (1.0, 7.0),
    "font_px": 11.5,
    "font_weight": 600,
    "white_space": "nowrap",
    "border_width_px": 1.0,
    "border_style": "solid",
})

#: 卡片主徽章 `.sbadge` 四尺寸（UI_COMPONENTS.md:55-56），依所在卡層 t1→b1 … t4→b4。
#: `radius_px`：規格只在 b3 明寫 3px，其餘三尺寸未覆寫 → 承 `BADGE_BASE` 的 3px。
SBADGE_SIZES: Final[Mapping[str, Mapping[str, object]]] = _frozen({
    "b1": _frozen({"font_px": 14.5, "padding_px": (10.0, 22.0),
                   "min_height_px": 46.0, "border_width_px": 2.0, "radius_px": 3.0}),
    "b2": _frozen({"font_px": 12.5, "padding_px": (5.0, 13.0),
                   "min_height_px": 36.0, "border_width_px": 1.0, "radius_px": 3.0}),
    "b3": _frozen({"font_px": 11.0, "padding_px": (2.0, 10.0),
                   "min_height_px": 28.0, "border_width_px": 1.0, "radius_px": 3.0}),
    # b4 `border:0` ⇒ 框線整條不存在 ⇒ 扛分辨的只剩圖示＋文字（UI_COMPONENTS.md:87）
    "b4": _frozen({"font_px": 10.5, "padding_px": (2.0, 5.0),
                   "min_height_px": 26.0, "border_width_px": 0.0, "radius_px": 3.0}),
})


def _badge(n, name, state_const, miss_reason, bg, fg,
           border_width_px, border_style, border_color, icon, text) -> Mapping[str, object]:
    # 硬規則（UI_COMPONENTS.md:94）：狀態色一律配圖示＋文字，⛔ 不得只靠顏色
    # —— 依據 UI_TOKENS.md:96 實測「綠/紅在 deuteranopia 下 ΔE 3.9 無解」。
    assert icon.strip() and text.strip(), f"#{n} 的圖示與文字皆為必填"
    return _frozen({
        "n": n, "name": name, "state_const": state_const, "miss_reason": miss_reason,
        "bg": bg, "fg": fg, "border_width_px": border_width_px,
        "border_style": border_style, "border_color": border_color,
        "icon": icon, "text": text,
    })


#: 徽章目錄，依 `n` 升冪。⛔ 恰 10 枚，不得新造第 11 種（UI_PAGE_TODAY.md:80）。
BADGES: Final[tuple[Mapping[str, object], ...]] = (
    # UI_COMPONENTS.md:60
    _badge(1, "正常", "UI_LIVE", None,
           "--sig-green-bg", "--sig-green", 1.0, "solid", "--sig-green", "🟢", "運作中"),
    # UI_COMPONENTS.md:61
    _badge(2, "載入中", "UI_LOADING", None,
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⏳", "載入中"),
    # UI_COMPONENTS.md:62
    _badge(3, "還沒載入", "UI_IDLE", None,
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⬜", "尚未載入"),
    # UI_COMPONENTS.md:63
    _badge(4, "門檻已失準", "UI_DEGRADED", None,
           "--sig-amber-bg", "--sig-amber", 1.0, "solid", "--sig-amber", "🟠", "門檻已失準"),
    # UI_COMPONENTS.md:64（四階中唯一 dashed 的灰系）
    _badge(5, "這項還沒做", "UI_UNWIRED", None,
           "--sig-grey-bg", "--sig-grey", 1.0, "dashed", "--rule-2", "⛔", "未接線"),
    # UI_COMPONENTS.md:65
    _badge(6, "出錯了", "UI_FAILED", None,
           "--sig-red-bg", "--sig-red", 1.0, "solid", "--sig-red", "🔴", "取得失敗"),
    # UI_COMPONENTS.md:66 —— 拆 UI_EMPTY 之一：該有卻沒拿到，重試有用
    _badge(7, "缺漏", "UI_EMPTY", "MISS_NO_INPUT",
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⚠︎ —", "缺漏 · 可重跑"),
    # UI_COMPONENTS.md:67 —— 拆 UI_EMPTY 之二：結構上不適用，重試無用
    _badge(8, "結構上不適用", "UI_EMPTY", "MISS_NOT_APPLICABLE",
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "N/A", "不適用 · 重跑無效"),
    # UI_COMPONENTS.md:68 —— 新訂（七態無 partial）；⛔ 與 #1 零共用色 token
    _badge(9, "資料不完整", None, None,
           "--sig-neutral-bg", "--sig-neutral", 1.0, "dashed", "--sig-blue", "◧", "N／M 計入"),
    # UI_COMPONENTS.md:69 —— 三旗標互相獨立（2026-08-26 裁示），⛔ 不得併進 #8
    _badge(10, "只描述不判等級", "emits_level=False", None,
           "--sig-blue-bg", "--sig-blue", 1.0, "solid", "--sig-blue", "◆", "只描述，不判等級"),
)

_BADGE_BY_N: Final[Mapping[int, Mapping[str, object]]] = _frozen({b["n"]: b for b in BADGES})


def badge(n: int) -> Mapping[str, object]:
    """取第 n 枚徽章；n 不在 1..10 → `KeyError`（⛔ 不回傳一個「差不多」的）。"""
    try:
        return _BADGE_BY_N[n]
    except KeyError:
        raise KeyError(f"徽章只有 #1~#10，收到 #{n}；⛔ 不得新造第 11 種") from None


# ══════════════════════════════════════════════════════════════════
# 3. 按鈕（五類）—— UI_COMPONENTS.md:102-110
# ⚠️ 規格的 hover 欄只列「會變的通道」；未列出的通道即**不變**。
#    因此：主 CTA 的 hover 明列「字 `--paper`」⇒ 非 hover 態的字色同為 `--paper`
#    （底色是 `--ink`，深色模式下為淺色，字必須是 `--paper` 才讀得到）；
#    而「次級（展開佐證）」與「文字按鈕」的 hover **明列字色會變成 `--ink`**
#    ⇒ 非 hover 態的字色必然**不是** `--ink`。規格沒有給那個值 ——
#    本檔取墨階的次一階 `--ink-2`，**此為實作組的決定，非規格值**（見交付報告）。
# ══════════════════════════════════════════════════════════════════
BUTTONS: Final[Mapping[str, Mapping[str, object]]] = _frozen({
    # UI_COMPONENTS.md:104 主 CTA（**全站唯一一顆**）
    "primary_cta": _frozen({
        "min_height_px": 40.0,
        "padding_px": (6.0, 16.0),
        "font_px": 13.5,
        "font_weight": 700,
        "radius_px": 3.0,
        "bg": "--ink",
        "border_width_px": 2.0,
        "border_style": "solid",
        "border_color": "--ink",
        "fg": "--paper",
        "hover": _frozen({"bg": "--ochre", "border_color": "--ochre", "fg": "--paper"}),
    }),
    # UI_COMPONENTS.md:105 次級（說明）
    "secondary_explain": _frozen({
        "min_height_px": 40.0,
        "padding_px": (6.0, 16.0),
        "font_px": 13.5,
        "font_weight": 700,
        "radius_px": 3.0,
        "bg": "transparent",
        "border_width_px": 1.0,
        "border_style": "solid",
        "border_color": "--ink",
        "fg": "--ink",  # hover 未列字色 ⇒ 不變
        "hover": _frozen({"bg": "--panel-2", "border_color": "--rule-2"}),
    }),
    # UI_COMPONENTS.md:106 次級（展開佐證）—— 44×44 觸控目標
    "secondary_evidence": _frozen({
        "min_height_px": 44.0,
        "min_width_px": 44.0,
        "padding_px": (7.0, 9.0),
        "font_px": 12.5,
        "font_weight": 600,
        "radius_px": 3.0,
        "bg": "transparent",
        "border_width_px": 1.0,
        "border_style": "solid",
        "border_color": "transparent",
        "fg": "--ink-2",  # ⚠️ 實作組決定（規格未給），理由見本節檔頭註
        "hover": _frozen({"bg": "--panel-2", "fg": "--ink", "border_color": "--rule"}),
    }),
    # UI_COMPONENTS.md:107 文字按鈕（表頭明細）
    "text": _frozen({
        "min_height_px": 28.0,
        "padding_px": (2.0, 11.0),
        "font_px": 11.0,
        "font_weight": 600,
        "radius_px": 999.0,
        "bg": "transparent",
        "border_width_px": 1.0,
        "border_style": "solid",
        "border_color": "--rule",
        "fg": "--ink-2",  # ⚠️ 實作組決定（規格未給），理由見本節檔頭註
        "hover": _frozen({"fg": "--ink", "border_color": "--rule-2"}),
    }),
    # UI_COMPONENTS.md:108 停用態（無主 CTA 時）—— hover 欄逐字為「無」
    "disabled": _frozen({
        "min_height_px": 40.0,
        "padding_px": (6.0, 16.0),
        "font_px": 13.5,
        "font_weight": 500,
        "radius_px": 3.0,
        "bg": "transparent",
        "border_width_px": 1.0,
        "border_style": "dashed",
        "border_color": "--rule-2",
        "fg": "--sig-grey",
        "hover": None,
    }),
})

#: 全站唯一一條焦點環（UI_COMPONENTS.md:110），⛔ 不准個別 `outline:none`。
FOCUS_RING: Final[Mapping[str, object]] = _frozen({
    "outline_width_px": 2.0,
    "outline_style": "solid",
    "outline_color": "--focus",
    "outline_offset_px": 2.0,
})


# ══════════════════════════════════════════════════════════════════
# 5. 斷點與欄數 —— UI_COMPONENTS.md:28 ＋ UI_PAGE_TODAY.md:47-48
# ⚠️ UI_COMPONENTS.md:28 同行記載 CSS 現況是 `640 / 940 / 560`、`880`／`881`
#    在 `@media` 零命中 → 那是**實作待修**，規格值就是下面這組。
# ══════════════════════════════════════════════════════════════════
BREAKPOINTS: Final[Mapping[str, int]] = _frozen({
    "mobile_max_px": 640,
    "tablet_min_px": 641,
    "tablet_max_px": 880,
    "desktop_min_px": 881,
})

#: 欄數硬夾上限：多於 3 格**換行排下一列，不是加欄**（UI_PAGE_TODAY.md:47-48）。
MAX_COLS: Final[int] = 3


def resolve_cols(cols: tuple[int, int, int], viewport_px: int) -> int:
    """線框 `cols` 記法 `(桌機, 平板, 手機)` → 該視窗寬下的欄數，並夾在 `MAX_COLS`。"""
    if len(cols) != 3:
        raise ValueError(f"cols 必須是 (桌機, 平板, 手機) 三元組，收到 {cols!r}")

    desktop, tablet, mobile = cols
    if viewport_px <= BREAKPOINTS["mobile_max_px"]:
        chosen = mobile
    elif viewport_px <= BREAKPOINTS["tablet_max_px"]:
        chosen = tablet
    else:
        chosen = desktop

    if chosen < 1:
        raise ValueError(f"欄數至少為 1，收到 {chosen!r}（cols={cols!r}）")
    return min(chosen, MAX_COLS)


__all__ = [
    "CARD_BASE", "CARD_TIERS", "PANEL", "CARD_FLAGGED", "tier_for_layer",
    "BADGE_BASE", "SBADGE_SIZES", "BADGES", "badge",
    "BUTTONS", "FOCUS_RING",
    "BREAKPOINTS", "MAX_COLS", "resolve_cols",
]
