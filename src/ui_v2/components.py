"""戰情室 v2 元件規格 —— 純資料層（契約 B）。

唯一資料來源：`docs/v2/spec/UI_COMPONENTS.md`
（每個值旁以 `# UI_COMPONENTS.md <章節名>` 標出處；⛔ 不寫行號 —— CLAUDE.md §8.2.A.0 規則 1）。
⛔ 本檔不 import streamlit：元件規格是**框架無關的純資料**。

**SSOT 分工（UI_COMPONENTS.md §0 SSOT 宣告 ①／②）**：顏色／字級／間距／圓角的唯一真相源是
`UI_TOKENS.md`（＝ `src/ui_v2/tokens.py`）⇒ 本檔一律存 **token 名**（如 `"--rule-2"`），
⛔ 不把 hex 複製進來（那會製造第二個真相源，違 CLAUDE.md §2.1）。

**狀態常數 SSOT**（UI_COMPONENTS.md §2「基底＝既有 L0 `shared/ui_state.py` 七態 SSOT」）：
七態的唯一真相源是既有 L0 `shared/ui_state.py`；本檔的 `state_const` 只存**常數名字串**，
⛔ 不在 `src/ui_v2/` 重新宣告 `UI_LIVE`／`UI_IDLE`／… 任何一個。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

# ⚠️ 只 import **模組**、⛔ 不 import 常數名：`test_components` 守的是「`UI_EMPTY` 等常數
#    ⛔ 不得在 `src/ui_v2/` 重新宣告」（`hasattr(components, "UI_EMPTY")` 必須為 False）。
#    #11 的圖示與文字**直接讀** `UI_STATE_META[UI_EMPTY]`（見下方 #11 列），⛔ 不抄一份。
from shared import ui_state as _ui_state


def _frozen(mapping: dict) -> Mapping:
    return MappingProxyType(mapping)


# ══════════════════════════════════════════════════════════════════
# 1. 卡片（四層密度）—— UI_COMPONENTS.md §1 卡片（四層密度）
# ══════════════════════════════════════════════════════════════════
#: `.blk` 基準（UI_COMPONENTS.md §1「`.blk` 基準」行）。
CARD_BASE: Final[Mapping[str, object]] = _frozen({
    "background": "--panel",     # §1「`.blk` 基準」行 `background:var(--panel)`
    "border_width_px": 1.0,      # §1「`.blk` 基準」行 `border:1px solid var(--rule-2)`
    "border_style": "solid",     # §1「`.blk` 基準」行
    "border_color": "--rule-2",  # §1「`.blk` 基準」行
    "radius_px": 2.0,            # §1「`.blk` 基準」行 `border-radius:2px`
})

#: 四層密度階梯。⚠️ `padding_px` 為 (上下, 左右)。
#: `title_color` 只有 t4 由規格指定（`--ink-2`）；t1~t3 規格未覆寫 → `None`＝承襲卡面主文字色。
CARD_TIERS: Final[Mapping[str, Mapping[str, object]]] = _frozen({
    # UI_COMPONENTS.md §1 四層密度表「t1 結論」列
    "t1": _frozen({
        "padding_px": (15.0, 17.0),
        "padding_mobile_px": (11.0, 12.0),   # ≤640；四階中只有 t1 有覆寫值
        "radius_px": 2.0,
        "border_width_px": 2.0,              # **2px** solid
        "border_style": "solid",
        "border_color": "--rule-2",
        # §1「層級只靠 border-width／dashed／padding 三個通道區分，⛔ 不得發明陰影」
        "shadow": None,
        "margin_top_px": 15.0,
        "title_px": 17.5,
        "title_weight": 700,
        "title_color": None,
        "badge_size": "b1",                  # §2「依所在卡層 t1→b1 … t4→b4」
    }),
    # UI_COMPONENTS.md §1 四層密度表「t2 核心」列（`--sp-4` `--sp-5`）
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
    # UI_COMPONENTS.md §1 四層密度表「t3 操作」列（`--sp-2` ＋ 9px）
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
    # UI_COMPONENTS.md §1 四層密度表「t4 佐證」列
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
        # §1 四層密度表「t4 佐證」列 —— 四階中唯一指定 title 色的一階
        "title_color": "--ink-2",
        "badge_size": "b4",
    }),
})

#: 面板 `.pan`（UI_COMPONENTS.md §1「面板 `.pan`」行）—— 與卡片是兩種容器，⛔ 不共用階梯。
PANEL: Final[Mapping[str, object]] = _frozen({
    "padding_px": (12.0, 14.0),
    "radius_px": 3.0,
    "border_width_px": 1.0,
    "border_style": "solid",
    "border_color": "--rule",
    "background": "--panel",
})

#: 標記態 `.blk.flagged`（UI_COMPONENTS.md §1「標記態 `.blk.flagged`」行）：產品模式下改回 solid。
CARD_FLAGGED: Final[Mapping[str, object]] = _frozen({
    "border_color": "--ochre-line",
    "border_style": "dashed",
    "border_style_product_mode": "solid",
})

# 四層由層序自動掛（UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」）。
# layer 0 ＝ 葉外 chrome（UI_PAGE_TODAY.md ① 四層結構表「葉外」列，據實列出、不計入四層）走 t3。
_LAYER_TIER: Final[Mapping[int, str]] = _frozen({
    0: "t3",   # UI_PAGE_TODAY.md ① 四層結構表「葉外」列
    1: "t1",   # UI_PAGE_TODAY.md ① 四層結構表「第一層 結論燈」列
    2: "t2",   # UI_PAGE_TODAY.md ① 四層結構表「第二層 核心卡」列
    3: "t3",   # UI_PAGE_TODAY.md ① 四層結構表「第三層 操作列」列
    4: "t4",   # UI_PAGE_TODAY.md ① 四層結構表「第四層 展開佐證」列
})


def tier_for_layer(layer: int) -> str:
    """層序 → 卡密度。**⛔ 刻意不提供任何覆寫參數** —— 這正是

    UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」的落地形式：
    只要簽名裡沒有 `tier=`／`density=`，手選在結構上就不可能發生。
    """
    try:
        return _LAYER_TIER[layer]
    except KeyError:
        raise ValueError(
            f"未知的層序 {layer!r}：只有 0（葉外 chrome）與 1~4 四層"
        ) from None


# ══════════════════════════════════════════════════════════════════
# 2. 徽章（~~10 種~~ → 11 種）—— UI_COMPONENTS.md §2 徽章
#    📌 **2026-09-26 有意識的規格變更，⛔ 不是漏刪；決策者：客戶。**
#       舊標題「徽章（10 種）」保留在刪除線內供追溯；現行＝11 種（新增 #11「▨ 無資料」）。
#       理由兩邊並陳見下方 `BADGES` 的註解與 UI_COMPONENTS.md §2 #11 列。
# ══════════════════════════════════════════════════════════════════
#: 共用幾何（線框 `.bdg`，UI_COMPONENTS.md §2「幾何（線框 `.bdg`，~~10 種~~ 全部共用）」）。
#: #11 同樣沿用本幾何，⛔ 未新增任何幾何值。
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

#: 卡片主徽章 `.sbadge` 四尺寸（UI_COMPONENTS.md §2「卡片主徽章用 `.sbadge` 四尺寸」），
#: 依所在卡層 t1→b1 … t4→b4。
#: `radius_px`：規格只在 b3 明寫 3px，其餘三尺寸未覆寫 → 承 `BADGE_BASE` 的 3px。
SBADGE_SIZES: Final[Mapping[str, Mapping[str, object]]] = _frozen({
    "b1": _frozen({"font_px": 14.5, "padding_px": (10.0, 22.0),
                   "min_height_px": 46.0, "border_width_px": 2.0, "radius_px": 3.0}),
    "b2": _frozen({"font_px": 12.5, "padding_px": (5.0, 13.0),
                   "min_height_px": 36.0, "border_width_px": 1.0, "radius_px": 3.0}),
    "b3": _frozen({"font_px": 11.0, "padding_px": (2.0, 10.0),
                   "min_height_px": 28.0, "border_width_px": 1.0, "radius_px": 3.0}),
    # b4 `border:0` ⇒ 框線整條不存在 ⇒ 扛分辨的只剩圖示＋文字
    # （UI_COMPONENTS.md §2「`.sbadge b4` 是 `border:0`…真正扛分辨的仍是**圖示＋文字**」）
    "b4": _frozen({"font_px": 10.5, "padding_px": (2.0, 5.0),
                   "min_height_px": 26.0, "border_width_px": 0.0, "radius_px": 3.0}),
})


def _badge(n, name, state_const, miss_reason, bg, fg,
           border_width_px, border_style, border_color, icon, text) -> Mapping[str, object]:
    # 硬規則（UI_COMPONENTS.md §2「狀態色**一律配圖示＋文字，⛔ 不得只靠顏色**」）
    # —— 依據 UI_TOKENS.md §A-3 實測「綠/紅在 deuteranopia 下 ΔE 3.9 無法靠色相分辨」。
    assert icon.strip() and text.strip(), f"#{n} 的圖示與文字皆為必填"
    return _frozen({
        "n": n, "name": name, "state_const": state_const, "miss_reason": miss_reason,
        "bg": bg, "fg": fg, "border_width_px": border_width_px,
        "border_style": border_style, "border_color": border_color,
        "icon": icon, "text": text,
    })


#: 徽章目錄，依 `n` 升冪。
#: ~~⛔ 恰 10 枚，不得新造第 11 種~~
#: ~~（UI_PAGE_TODAY.md ② 落差 2「⛔ 不得為了對齊線框鍵數而新造第 11 種徽章」）。~~
#: 📌 **2026-09-26 有意識的規格變更，⛔ 不是漏刪；決策者：客戶。現行：恰 11 枚。**
#:   · **舊規則的理由仍然成立，⛔ 不是寫錯**：它防的是「為了對齊線框的**鍵數**就多造一顆」——
#:     多一顆徽章＝多一種使用者要學的語彙，且很容易被拿來替一個說不清楚的狀態找地方放。
#:   · **為什麼這次例外**（客戶 2026-09-26 裁示）：卡面文字寫「**這是一個有效的結果**」、
#:     徽章卻印 #7「缺漏 · 可重跑」—— **同一張卡同時說兩件相反的話**；10 顆裡**沒有一顆**
#:     能表示「算完了、結果真的是空的」（#8「不適用 · 重跑無效」語意也不對）。
#:     ⇒ 這不是對齊鍵數，是**現有語彙說不出一句真話**。
#:   · **#11 的射程（⛔ 不得擴張）**：**只**給「上游這一輪**成功算完**、結果**真的是 0／空**」的卡，
#:     且**登記制** —— 只有 `src/ui/views/page_today.py::V2_VALID_EMPTY_SPEC` 列出的
#:     `(card.key, note.now)` 才畫 #11。真缺漏／還沒載入／未評估／未綁定／這輪沒讀／
#:     契約漂移／可重試 —— **一律維持原徽章**。
#:   · **⛔ 仍然不得再新造第 12 種**；舊規則的精神（不為對齊鍵數造徽章）照舊有效。
BADGES: Final[tuple[Mapping[str, object], ...]] = (
    # UI_COMPONENTS.md §2 徽章表 #1 正常
    _badge(1, "正常", "UI_LIVE", None,
           "--sig-green-bg", "--sig-green", 1.0, "solid", "--sig-green", "🟢", "運作中"),
    # UI_COMPONENTS.md §2 徽章表 #2 載入中
    _badge(2, "載入中", "UI_LOADING", None,
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⏳", "載入中"),
    # UI_COMPONENTS.md §2 徽章表 #3 還沒載入
    _badge(3, "還沒載入", "UI_IDLE", None,
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⬜", "尚未載入"),
    # UI_COMPONENTS.md §2 徽章表 #4 門檻已失準
    _badge(4, "門檻已失準", "UI_DEGRADED", None,
           "--sig-amber-bg", "--sig-amber", 1.0, "solid", "--sig-amber", "🟠", "門檻已失準"),
    # UI_COMPONENTS.md §2 徽章表 #5 這項還沒做（四階中唯一 dashed 的灰系）
    _badge(5, "這項還沒做", "UI_UNWIRED", None,
           "--sig-grey-bg", "--sig-grey", 1.0, "dashed", "--rule-2", "⛔", "未接線"),
    # UI_COMPONENTS.md §2 徽章表 #6 出錯了
    _badge(6, "出錯了", "UI_FAILED", None,
           "--sig-red-bg", "--sig-red", 1.0, "solid", "--sig-red", "🔴", "取得失敗"),
    # UI_COMPONENTS.md §2 徽章表 #7 缺漏 —— 拆 UI_EMPTY 之一：該有卻沒拿到，重試有用
    _badge(7, "缺漏", "UI_EMPTY", "MISS_NO_INPUT",
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "⚠︎ —", "缺漏 · 可重跑"),
    # UI_COMPONENTS.md §2 徽章表 #8 結構上不適用 —— 拆 UI_EMPTY 之二：重試無用
    _badge(8, "結構上不適用", "UI_EMPTY", "MISS_NOT_APPLICABLE",
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2", "N/A", "不適用 · 重跑無效"),
    # UI_COMPONENTS.md §2 徽章表 #9 資料不完整 —— 新訂（七態無 partial）；⛔ 與 #1 零共用色 token
    _badge(9, "資料不完整", None, None,
           "--sig-neutral-bg", "--sig-neutral", 1.0, "dashed", "--sig-blue", "◧", "N／M 計入"),
    # UI_COMPONENTS.md §2 徽章表 #10 只描述不判等級 —— 三旗標互相獨立
    #（2026-08-26 裁示），⛔ 不得併進 #8
    _badge(10, "只描述不判等級", "emits_level=False", None,
           "--sig-blue-bg", "--sig-blue", 1.0, "solid", "--sig-blue", "◆", "只描述，不判等級"),
    # UI_COMPONENTS.md §2 徽章表 #11 有效的空結果（客戶 2026-09-26 新增）
    # 🔴 **圖示與文字⛔ 不在這裡寫字面** —— 直接讀 L0 `UI_STATE_META[UI_EMPTY]`
    #    （`("無資料", "▨", …)`），客戶裁示逐字「沿用既有 L0 chip」＝**同一個真相源，⛔ 不是抄一份**。
    #    L0 哪天改字，這顆徽章跟著變；`tests/ui_v2/test_components.py` 釘兩邊相等。
    # 灰系、1px solid `--rule-2`：與 #7／#8 同色系（三者都是「沒有值」），
    #    **靠圖示＋文字分辨**（`▨ 無資料` vs `⚠︎ — 缺漏 · 可重跑` vs `N/A 不適用 · 重跑無效`），
    #    ⛔ 不新增任何色 token（§2 硬規則「⛔ 不得只靠顏色」照舊）。
    _badge(11, "有效的空結果", "UI_EMPTY", None,
           "--sig-grey-bg", "--sig-grey", 1.0, "solid", "--rule-2",
           _ui_state.UI_STATE_META[_ui_state.UI_EMPTY][1],
           _ui_state.UI_STATE_META[_ui_state.UI_EMPTY][0]),
)

_BADGE_BY_N: Final[Mapping[int, Mapping[str, object]]] = _frozen({b["n"]: b for b in BADGES})


def badge(n: int) -> Mapping[str, object]:
    """取第 n 枚徽章；n 不在 1..11 → `KeyError`（⛔ 不回傳一個「差不多」的）。

    ~~n 不在 1..10~~ → 2026-09-26 客戶新增 #11（有意識的規格變更，⛔ 不是漏刪）。
    """
    try:
        return _BADGE_BY_N[n]
    except KeyError:
        # ~~「徽章只有 #1~#10…⛔ 不得新造第 11 種」~~（2026-09-26 客戶新增 #11 後改寫）
        raise KeyError(
            f"徽章只有 #1~#{len(BADGES)}，收到 #{n}；"
            f"⛔ 不得新造第 {len(BADGES) + 1} 種") from None


# ══════════════════════════════════════════════════════════════════
# 3. 按鈕（五類）—— UI_COMPONENTS.md §3 按鈕
# ⚠️ 規格的 hover 欄只列「會變的通道」；未列出的通道即**不變**。
#    ~~因此：主 CTA 的 hover 明列「字 `--paper`」⇒ 非 hover 態的字色同為 `--paper`
#      （底色是 `--ink`，深色模式下為淺色，字必須是 `--paper` 才讀得到）；~~
#    ← **2026-09-22 起不成立（有意識的政策變更，⛔ 不是漏刪；決策者客戶）**：
#      主 CTA 的底色已改為 `--cta-primary-bg`、**非 hover 態字色由規格直接指定**為
#      `--cta-primary-fg`（＝ 客戶裁示逐字「config 藍底／白字」）⇒ 該欄**不再靠
#      hover 欄反推**，上面那句推導的前提（底色是 `--ink`）已經不存在。
#      ⚠️ 推導**規則本身**（未列出的通道即不變）**未被推翻**，下面兩類仍照此讀。
#    🔴 **hover 的字色必須維持 `--paper`，⛔ 不得跟著改成 `--cta-primary-fg`** ——
#      實測 `#ffffff` on dark `--ochre` `#d59a5e` ＝ **2.438 FAIL**（WCAG AA 小字 4.5），
#      而 `--paper` on `--ochre` ＝ **7.592 PASS**。**這是硬約束，⛔ 不是風格選擇。**
#      守衛：`tests/ui_v2/test_components.py::test_primary_cta_hover_fg_must_stay_paper_because_white_on_ochre_fails_aa`
#    而「次級（展開佐證）」與「文字按鈕」的 hover **明列字色會變成 `--ink`**
#    ⇒ 非 hover 態的字色必然**不是** `--ink`。規格沒有給那個值 ——
#    本檔取墨階的次一階 `--ink-2`，**此為實作組的決定，非規格值**（見交付報告）。
# ══════════════════════════════════════════════════════════════════
BUTTONS: Final[Mapping[str, Mapping[str, object]]] = _frozen({
    # UI_COMPONENTS.md §3 按鈕表「主 CTA（~~**全站唯一一顆**~~ **每頁首屏唯一一顆**）」列
    # ⚠️ **2026-09-22 列標題改文案**（有意識的政策變更，⛔ 不是漏刪；決策者**客戶**）。
    #    - **舊文案的理由（仍然成立，⛔ 不是寫錯）**：在只有「🚦 今天」一頁時，
    #      「全站唯一」與「每頁首屏唯一」**外延相同** —— 兩句話挑不出差別。
    #    - **被權衡掉的原因**：五頁 IA 落地後，🔎 選股頁有自己的主 CTA `🎯 開始選股`
    #      ⇒「全站唯一」變成**可實測為假**的全稱句（`UI_PAGE_FIND.md` ① 已逐字否證）。
    #    ⚠️ 出處列標題已於 `7f14f68` 同步改名 ⇒ 此處**跟著改才對得上出處**，⛔ 不是改寫引文。
    #    ⛔ **本檔下方 `FOCUS_RING` 的「全站唯一一條焦點環」⛔ 不在本次射程內** ——
    #       那是**另一個**宣稱（一條 `:focus-visible` 規則，⛔ 不是主 CTA 顆數），
    #       且其出處 `UI_COMPONENTS.md §3「焦點環」行` **原文未改**（仍寫「全站唯一一條」）
    #       ⇒ 改它反而會讓引用與出處對不上。⛔ 不得順手一起改。
    #    ⚠️ 本次**只動這段文案**：下方 `primary_cta` 的**每一個值一字未動**。
    # 🔴 **2026-09-22 底色／框色／字色改值**（有意識的政策變更，⛔ 不是漏刪；決策者**客戶**）。
    #    舊值（保留備查）：~~`"bg": "--ink"` / `"border_color": "--ink"` / `"fg": "--paper"`~~
    #    - **舊契約的理由（仍然成立，⛔ 不是寫錯）**：`--paper` on `--ink` 對比
    #      dark **14.513**／light **13.548**，**遠優於**新契約的 **4.634**／**7.736**。
    #    - **被權衡掉的原因**：Streamlit 端主 CTA 是真 `st.button(type="primary")`、
    #      吃 `.streamlit/config.toml` 的 `primaryColor` ⇒ `--ink` 這個契約值
    #      **根本畫不出來**（`docs/v2/prototype/STREAMLIT_VS_HTML.md` §2 第 1 點實測）。
    #      留著等於讓契約與實際渲染**永久打架**。
    #    ⚠️ 代價已揭露於 `UI_TOKENS.md` §A-4 第 3 段：**dark 側只贏 AA 門檻 0.134**
    #      ⇒ ⛔ 不得把本次改動描述成「對比改善」，也⛔ 不得再往下調任何一碼。
    #    ⚠️ 幾何值（高度／內距／字級／字重／圓角）與 `border_width_px`／`border_style`
    #      **一字未動**；**`hover` 整個 dict 亦一字未動**（見上方 🔴 硬約束）。
    "primary_cta": _frozen({
        "min_height_px": 40.0,
        "padding_px": (6.0, 16.0),
        "font_px": 13.5,
        "font_weight": 700,
        "radius_px": 3.0,
        "bg": "--cta-primary-bg",            # §3 按鈕表「主 CTA」列 底色欄（2026-09-22 改）
        "border_width_px": 2.0,
        "border_style": "solid",
        # 客戶【拍板 2】「border_color 跟隨新 token」⇒ 維持「2px **同色**框」語意。
        "border_color": "--cta-primary-bg",  # §3 按鈕表「主 CTA」列 框色欄（2026-09-22 改）
        "fg": "--cta-primary-fg",            # §3 按鈕表 主 CTA 註「非 hover 字色＝--cta-primary-fg」
        "hover": _frozen({"bg": "--ochre", "border_color": "--ochre", "fg": "--paper"}),
    }),
    # UI_COMPONENTS.md §3 按鈕表「次級（說明）」列
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
    # UI_COMPONENTS.md §3 按鈕表「次級（展開佐證）」列 —— 44×44 觸控目標
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
    # UI_COMPONENTS.md §3 按鈕表「文字按鈕（表頭明細）」列
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
    # UI_COMPONENTS.md §3 按鈕表「停用態（無主 CTA 時）」列 —— hover 欄逐字為「無」
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

#: 全站唯一一條焦點環（UI_COMPONENTS.md §3「焦點環」行），⛔ 不准個別 `outline:none`。
FOCUS_RING: Final[Mapping[str, object]] = _frozen({
    "outline_width_px": 2.0,
    "outline_style": "solid",
    "outline_color": "--focus",
    "outline_offset_px": 2.0,
})


# ══════════════════════════════════════════════════════════════════
# 4. 卡內主數值（大字區 ＝ KPI）—— UI_COMPONENTS.md §4 表格
#
# 出處逐字（UI_COMPONENTS.md §4「手機卡片流（新訂）」段）：
#   「**升為標題**：① 識別欄（代號／名稱）→ `.bt .t` `13px/700`；
#     ② 主數值欄一欄 → 卡內 `24px/700` `--mono` tabular-nums。」
#
# ⚠️ **為什麼 KPI 字級的出處會是「表格」那一節** —— 這不是抄錯章節：
#    `UI_TOKENS.md §B` 字型 token 表**沒有 KPI 專屬字級列**，
#    `UI_PRINCIPLES.md` 第 6 條自己逐字揭露了這件事並指定替代出處：
#      「KPI ≥ 20px，明細 ≤ 13px｜KPI＝`UI_COMPONENTS` §4 主數值 `24px/700 --mono`
#        （原型 `.big` 24px、`_ui_kit.render_card()` 大字 `24px/1.25`）；
#        … ⚠️ §B **無 KPI 專屬字級列**」
#    ⇒ 本契約是**照規格指定的出處抄回來的**，⛔ 不是實作組挑一個「看起來夠大」的數字。
#
# ⚠️ **⛔ 不含 `text-align:end` 與 `white-space:nowrap`**：那兩項出自 §4 的
#    「對齊規則（三斷點共通）」，管的是**表格的數值欄**，不是卡內大字區。
#    把表格欄規則整包搬來，會讓大字右靠 —— 那是規格沒要求的版面改動。
# ══════════════════════════════════════════════════════════════════
CARD_VALUE: Final[Mapping[str, object]] = _frozen({
    # §4「升為標題」②「卡內 `24px/700`」的 24
    "font_px": 24.0,
    # §4「升為標題」②「卡內 `24px/700`」的 700
    "font_weight": 700,
    # §4「升為標題」②「`--mono`」。存 **token 名**，與本檔其餘欄位同一紀律。
    "font_family": "--mono",
    # UI_PRINCIPLES.md 第 6 條 KPI 列括號內「`_ui_kit.render_card()` 大字 `24px/1.25`」的
    # 1.25（該行的另一個佐證「原型 `.big`」只給了 24px，沒給行高）。
    # 實測佐證：`src/ui/views/_ui_kit.py` 該處逐字
    # `font-size:24px;font-weight:700;line-height:1.25;` —— 三個值全部對得上。
    "line_height": 1.25,
    # §4「升為標題」②「tabular-nums」
    "font_variant_numeric": "tabular-nums",
})

#: 字族 token 的**實值**。⚠️ **暫時落地點，⛔ 不是這個值最終該住的地方。**
#:
#: 正確的家是 `tokens.py`（＝ `UI_TOKENS.md §B` 字型 token 表的落地），與顏色／間距同層；
#: 本檔其餘欄位一律只存 token 名、⛔ 不複製值，正是為了不製造第二個真相源（CLAUDE.md §2.1）。
#: 之所以破例落在這裡，只有一個理由：**`tokens.py` 目前沒有字型 token 節，而該檔在本批的
#: 檔案邊界之外**（2026-09-21 由另一組承包），⛔ 不是因為這裡比較適合。
#:
#: ⚠️ 為什麼不能乾脆不宣告、直接寫 `font-family:var(--mono)`：CSS 規範下 `var()` 指向
#: **未宣告**的自訂屬性是 *invalid at computed-value time* ⇒ 退回繼承值 ⇒ 大字改用繼承來的
#: 非等寬字體，`tabular-nums` 形同虛設，而畫面**看起來完全正常**。
#: （`tests/ui_v2/test_markup.py::_check_var_referential_integrity` 也會當場轉紅。）
#:
#: ⛔ **`tokens.py` 一長出字型 token 節，本常數即刻刪除**，`markup._root_rule` 改引 `tokens`。
#: 值逐字取 `UI_TOKENS.md §B` 末段：
#:   「`--mono` = `"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace`
#:     （線框 30 處，**數值一律走這條**）」
FONT_STACKS: Final[Mapping[str, str]] = _frozen({
    "--mono": '"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace',
})


# ══════════════════════════════════════════════════════════════════
# 5. 斷點與欄數 —— UI_COMPONENTS.md 前言「斷點＝`≤640 手機 / 641–880 平板 / ≥881 桌機`」
#                ＋ UI_PAGE_TODAY.md ①「排列（三斷點）」段
# ⚠️ UI_COMPONENTS.md 該行同時記載 CSS 現況是 `640 / 940 / 560`、`880`／`881`
#    在 `@media` 零命中 → 那是**實作待修**，規格值就是下面這組。
# ══════════════════════════════════════════════════════════════════
BREAKPOINTS: Final[Mapping[str, int]] = _frozen({
    "mobile_max_px": 640,
    "tablet_min_px": 641,
    "tablet_max_px": 880,
    "desktop_min_px": 881,
})

#: 欄數硬夾上限：多於 3 格**換行排下一列，不是加欄**
#: （UI_PAGE_TODAY.md ①「排列（三斷點）」段）。
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
    "CARD_VALUE", "FONT_STACKS",
    "BREAKPOINTS", "MAX_COLS", "resolve_cols",
]
