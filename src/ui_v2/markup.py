"""戰情室 v2 標記層 —— 純字串（契約 D）：CSS 文字 ＋ HTML 文字。

⛔ **本檔不 import streamlit**：它只產字串，要能在沒有 Streamlit runtime 的沙箱單測
（沿用 `tokens.py` / `components.py` / `page_today.py` 的既有紀律）。
把字串交給 `st.markdown(..., unsafe_allow_html=True)` 是 `render.py` 的事。

公開介面（規格：`tests/ui_v2/test_markup.py`）
────────────────────────────────────────────
  `page_css(mode)`      整頁樣式表（不含 `<style>` 標籤 —— 由 `render.py` 包）
  `badge_html(n)`       一顆狀態徽章
  `card_html(...)`      一張卡
  `grid_html(...)`      一個 block 的**卡內**網格容器 ＋ 內含的卡
  `layer_html(...)`     一**層**的層級網格容器 ＋ 內含的各 block

🔴 **兩個網格是兩件事，⛔ 不得混用**（`page_today` 已用 🔴 標出）：
  · **block 網格**（`page_today.BLOCK_COLS`，class `.g-<桌>-<平>-<手>`）
    ＝ **單一 block 內部**一列放幾格；
  · **層級網格**（`page_today.LAYER_GRID_COLS`，class `.lg-<桌>-<平>-<手>`）
    ＝ 同一層的**幾個 block 彼此**怎麼並排。
  兩組 class **前綴不同、零交集**（同 `.bdg-{n}` 編號 vs `.sb-{key}` 尺寸的紀律）。

§1 Fail Loud 在本層的三個落點
────────────────────────────
1. **`page_css()` 先把 token 全部解析完，才開始產任何 CSS。** 任何一個 token 拿不到
   （`TBD` 或未知名）→ 整張 sheet 不存在。⛔ 不得「把拿不到的那幾個跳過不輸出」——
   那會留下 `:root` 少一個宣告、但 `var(--x)` 還在的半套 CSS；CSS 規範下
   `var()` 指向未定義的自訂屬性是 *invalid at computed-value time*，會**退回繼承值**
   ⇒ 畫面上出現一個看起來正常、實際上是錯的顏色。那比整頁炸掉危險得多。
2. **每一個 token 都走 `tokens.get_token(name, mode=mode)`。** ⛔ 不得
   `for k, v in tokens.DARK.items()` 直接讀 dict —— 直接讀 dict 繞過 `TBD` 檢查。
3. **大字區／判決區一律以 `page_today.card_value_text` / `card_level_text` 為準。**
   灰態紅態留白、`degraded` 觀測照出判決留白，⛔ 本檔不另立第二把尺。

⛔ **本檔不發明任何數字**（CLAUDE.md §3.3 反捏造）
────────────────────────────────────────────
CSS 裡所有 px / 顏色一律來自契約層：
`tokens.get_token()`（顏色）、`tokens.SPACING`（間距）、`components.CARD_BASE` /
`CARD_TIERS` / `BADGE_BASE` / `SBADGE_SIZES` / `BREAKPOINTS` / `resolve_cols()`（幾何）、
`page_today.BLOCK_COLS` / `LAYER_GRID_COLS`（欄數）。

~~⚠️ **已知的規格洞，據實揭露（⛔ 沒有自己補一個值）**：卡片「大字區（觀測值）」的~~
~~**字級沒有 SSOT** —— `components.CARD_TIERS` 只給 `title_px`，`tokens` 沒有型階表。~~
~~故 `.blk-val` **不設 `font-size`**（承襲卡面字級），⛔ 不自行挑一個看起來合理的數字。~~
~~要補請先補契約層，⛔ 不要在本檔寫死。~~

⚠️ **2026-09-21 事實更正，不是漏刪；決策者：AI 總管。** 上段畫掉的是**前提**，
**⛔ 不是紀律** —— 「要補請先補契約層」那句照辦了：`components.CARD_VALUE` 已落地。
- **舊句在它寫下的當天是對的**：當時 `components` 只有 `title_px`，本檔若自己挑一個
  「看起來夠大」的數字，就是 CLAUDE.md §3.3 反捏造。**⛔ 不寫死** 這條紀律**一個字都沒放寬**。
- **為什麼它必須被補掉**：`.blk-val` 不設 `font-size` ⇒ 承襲卡面字級 ⇒ 觀測值**跟卡標一樣大**，
  而 `UI_PRINCIPLES.md` 第 6 條「KPI ≥ 20px」正是靠這個值判 ✅ ——
  不補等於**文件宣稱 ✅、畫面沒做到**（對照 CLAUDE.md §-2「沒查證的宣稱比沒有宣稱更危險」）。
- **值的出處**（⛔ 非本檔發明）：`UI_COMPONENTS.md §4` 逐字「主數值欄一欄 → 卡內
  `24px/700` `--mono` tabular-nums」，由 `UI_PRINCIPLES.md` 第 6 條明文指定為 KPI 的出處
  （§B 無 KPI 專屬字級列）；行高 1.25 出自同條括號內的 `_ui_kit.render_card()` 大字 `24px/1.25`。
  完整引文與判讀見 `components.CARD_VALUE` 的區塊註解。
"""
from __future__ import annotations

import re
from html import escape
from typing import Final, Iterable, Mapping, Sequence

from src.ui_v2 import components, page_today, tokens

# ══════════════════════════════════════════════════════════════════
# 0. 取自契約層的清單（⛔ 一律不手抄、⛔ 不寫死）
# ══════════════════════════════════════════════════════════════════
#: token 名的正典清單。`tokens.py` 自己 assert 過 dark／light 覆蓋同一組名字，
#: 故任取一邊即為全集。
_TOKEN_NAMES: Final[tuple[str, ...]] = tuple(tokens.DARK)

#: **真的出現過**的 block 網格欄數組合（實測 2 種）。
#: ⛔ 不產 3×3×3 ＝ 27 種組合 —— 用不到的 class 是死 CSS（CLAUDE.md §8.1 step 6）。
_BLOCK_COLS_USED: Final[tuple[tuple[int, int, int], ...]] = tuple(
    sorted(set(page_today.BLOCK_COLS.values()))
)

#: **真的出現過**的層級網格欄數組合（實測只有第二層有登記 → 1 種）。
_LAYER_COLS_USED: Final[tuple[tuple[int, int, int], ...]] = tuple(
    sorted(set(page_today.LAYER_GRID_COLS.values()))
)

#: 真的有 block 掛在上面的密度階（決定要產哪幾條 `.grd-t*` / `.blk-t*`）。
_TIERS_ON_PAGE: Final[tuple[str, ...]] = tuple(
    t for t in components.CARD_TIERS
    if any(page_today.tier_for_block(b) == t for b in page_today.BLOCK_COLS)
)

#: 真的有層級網格的那幾階（只產這些 `.lyr-t*`，同上不產用不到的）。
_TIERS_WITH_LAYER_GRID: Final[tuple[str, ...]] = tuple(
    t for t in components.CARD_TIERS
    if any(components.tier_for_layer(L) == t for L in page_today.LAYER_GRID_COLS)
)


# ══════════════════════════════════════════════════════════════════
# 1. 小工具
# ══════════════════════════════════════════════════════════════════
def _px(value: float) -> str:
    """契約層的 px 數 → CSS 長度。`15.0` → `15px`、`17.5` → `17.5px`、`0.0` → `0px`。"""
    return f"{value:g}px"


def _var(token_name: str) -> str:
    return f"var({token_name})"


def _esc(text: object) -> str:
    """一律 escape —— 標題／值／判決都可能來自使用者資料（Google Sheet 的股名等）。

    不 escape 的後果不是資安問題，是**版面會壞掉**（名稱含 `<` 或 `&` 時）——
    repo 先例：`src/ui/render/station_cards.py` 的 `_esc`。
    """
    return escape(str(text), quote=True)


def _pad(padding_px: tuple[float, float]) -> str:
    """契約層的 `(上下, 左右)` → 四條 longhand。

    ⚠️ 刻意用 longhand 而非 `padding:` 簡寫：簡寫只對得上「查 `padding`」的讀者，
    longhand 對「查 `padding`」與「查 `padding-top`」**兩種都對得上**。
    """
    vertical, horizontal = padding_px
    return (
        f"padding-top:{_px(vertical)};padding-bottom:{_px(vertical)};"
        f"padding-left:{_px(horizontal)};padding-right:{_px(horizontal)}"
    )


def _border(width_px: float, style: str, color_token: str | None = None) -> str:
    """同 `_pad`：一律 longhand（`border:` 簡寫查不到 `border-width`）。"""
    out = f"border-width:{_px(width_px)};border-style:{style}"
    if color_token is not None:
        out += f";border-color:{_var(color_token)}"
    return out


def _grid_template(n_cols: int) -> str:
    return f"grid-template-columns:repeat({n_cols},minmax(0,1fr))"


def _cols_class(prefix: str, cols: tuple[int, int, int]) -> str:
    """欄數組合 → class 名。`("g", (3,2,1))` → `g-3-2-1`。

    ⚠️ 以**線框原值**命名（⛔ 不是 `resolve_cols` 夾過的值）：不同的 `cols` 必須拿到
    不同的 class，否則兩種設定會被悄悄併成同一條 CSS。
    """
    return prefix + "-" + "-".join(str(c) for c in cols)


def _block_cols_class(cols: tuple[int, int, int]) -> str:
    return _cols_class("g", cols)


def _layer_cols_class(cols: tuple[int, int, int]) -> str:
    return _cols_class("lg", cols)


# ══════════════════════════════════════════════════════════════════
# 2. page_css —— 整頁樣式表
# ══════════════════════════════════════════════════════════════════
def _resolve_palette(mode: str) -> dict[str, str]:
    """把**所有** token 解析成實值。

    🔴 這一步刻意獨立成函式，而且在**產生任何 CSS 之前**跑完：
    任何一個 token 拿不到就在這裡炸，⛔ 不會留下半套 sheet（見檔頭 §1 落點 1）。
    ⚠️ 走 `tokens.get_token(name, mode=mode)`，⛔ 不直接讀 `tokens.DARK` dict
    —— 直接讀 dict 會繞過 `TBD` 檢查（檔頭 §1 落點 2）。
    """
    return {name: tokens.get_token(name, mode=mode) for name in _TOKEN_NAMES}


def _root_rule(palette: Mapping[str, str]) -> str:
    """`:root` —— 本頁引用的每一個自訂屬性都必須在這裡宣告過。

    顏色走 `palette`（已解析）；間距走 `tokens.SPACING`、字族走 `components.FONT_STACKS`
    （兩者都與 dark/light 無關，故不經 `get_token` —— 它們本來就不是模式相依的 token）。

    ⚠️ **字族為什麼來自 `components` 而不是 `tokens`**（2026-09-21，據實揭露）：
    `UI_TOKENS.md §B` 的字型 token 目前**還沒落地到 `tokens.py`**，而該檔在本批的檔案
    邊界之外。`components.FONT_STACKS` 是**暫時落地點**，該節一落地就要改回引 `tokens`
    並刪掉那個常數（理由與引文寫在 `components.FONT_STACKS` 的註解裡）。
    ⛔ **不得**因為「反正 `--mono` 沒宣告也只是退回繼承字體」就跳過這一步 ——
    那正是本檔 §1 落點 1 講的失效模式（`var()` 指向未宣告的屬性 ⇒ 退回繼承值 ⇒
    畫面看起來正常、實際上是錯的）。
    """
    decls = [f"{name}:{value};" for name, value in palette.items()]
    decls += [f"{name}:{value};" for name, value in tokens.SPACING.items()]
    decls += [f"{name}:{value};" for name, value in components.FONT_STACKS.items()]
    return ":root{" + "".join(decls) + "}"


def _grid_rules() -> list[str]:
    """兩種網格的基準規則。

    · `.grd`  block 網格容器（卡內一列幾格）
    · `.lyr`  層級網格容器（同層的 block 彼此怎麼並排）
    欄數本身掛在 `.g-*` / `.lg-*`，容器基準與欄數分開 ⇒ 換欄數不必動容器樣式。
    """
    out = [
        "/* ── block 網格（卡內一列幾格）── */",
        ".grd{display:grid;gap:" + _var("--sp-5") + "}",
        ".grd>*{min-width:0}",
        # 卡在網格裡靠 gap 分隔，⛔ 不再疊自己的 margin-top（否則第一列被推下去）。
        # 用 `.grd>.blk`（兩個 class）壓過 `.blk-t*`（一個 class），與 CSS 順序無關。
        ".grd>.blk{margin-top:0px}",
    ]
    for tier in _TIERS_ON_PAGE:
        spec = components.CARD_TIERS[tier]
        out.append(f".grd-{tier}{{margin-top:{_px(spec['margin_top_px'])}}}")
    for cols in _BLOCK_COLS_USED:
        n = components.resolve_cols(cols, components.BREAKPOINTS["desktop_min_px"])
        out.append(f".{_block_cols_class(cols)}{{{_grid_template(n)}}}")

    out += [
        "/* ── 層級網格（同一層的 block 彼此怎麼並排）── */",
        ".lyr{display:grid;gap:" + _var("--sp-5") + "}",
        ".lyr>*{min-width:0}",
        ".lyr>.grd{margin-top:0px}",
    ]
    for tier in _TIERS_WITH_LAYER_GRID:
        spec = components.CARD_TIERS[tier]
        out.append(f".lyr-{tier}{{margin-top:{_px(spec['margin_top_px'])}}}")
    for cols in _LAYER_COLS_USED:
        n = components.resolve_cols(cols, components.BREAKPOINTS["desktop_min_px"])
        out.append(f".{_layer_cols_class(cols)}{{{_grid_template(n)}}}")
    return out


def _card_rules() -> list[str]:
    """卡片：`.blk` 基準 ＋ 四階密度階梯。

    🔴 四階**逐階各自一條規則**，⛔ 不寫 `.blk-t1,.blk-t2,…{padding:…}` 這種通規則
    —— 通規則會讓「資訊密度遞減」（`UI_PRINCIPLES.md` 第 3 條）在畫面上被壓平，
    而四階的值全都還在 CSS 裡，看起來像有做。
    """
    base = components.CARD_BASE
    out = [
        "/* ── 卡片基準 ── */",
        ".blk{box-sizing:border-box;background:" + _var(str(base["background"])) + ";"
        + _border(float(base["border_width_px"]), str(base["border_style"]),
                  str(base["border_color"]))
        + f";border-radius:{_px(float(base['radius_px']))}}}",
        ".blk *{box-sizing:border-box}",
        "/* ── 四階密度階梯（UI_COMPONENTS §1）── */",
    ]
    for tier in _TIERS_ON_PAGE:
        spec = components.CARD_TIERS[tier]
        out.append(
            f".blk-{tier}{{margin-top:{_px(spec['margin_top_px'])};"
            f"{_pad(spec['padding_px'])};"
            f"{_border(float(spec['border_width_px']), str(spec['border_style']), str(spec['border_color']))};"
            f"border-radius:{_px(float(spec['radius_px']))}}}"
        )

    # ── ~~t1 三張等高（客戶 2026-09-24 裁示 ②）：`.blk-t1{min-height:190px}`~~ ──
    # 🔴 **2026-09-24（同日稍晚）整頁卡化：該條已移除。**
    #    **有意識的移除，⛔ 不是漏刪；執行 AI 總管。⚠️ 決策者未定 —— 見末段。**
    #
    # · **舊規則的理由完全成立，⛔ 不是寫錯**：實機是 `st.columns` 三個**獨立欄**、
    #   ⛔ 不是一個 grid ⇒ `align-items` 摸不到跨欄的兄弟，**只有下限能讓三張對齊**。
    #   那句話**現在仍然是對的**。190 也是**實測**挑的（138／140／187px，380px 欄寬、idle）。
    #
    # · **被權衡掉的是它的前提** —— 它量的那個卡型**已經不存在了**：
    #   同日客戶再裁示「三要素壓成 2~3 行 fact」⇒ 卡內從「1 行指路」變成「3 列 fact」。
    #
    # 🔴 **移除的依據是實測，⛔ 不是嫌它舊**（量測日 2026-09-24，本機真跑
    #    `streamlit run app.py` ＋ Playwright，冷啟動 idle、側欄展開）：
    #    ① **它現在一點作用都沒有** —— 同一頁注入 `.blk-t1{min-height:0}` 前後
    #       逐張比對**三個視窗寬全部逐像素相同**：
    #         1920 → 192／218／192（有 190 與無 190 **完全一樣**）
    #         1440 → 201／252／226（同上）
    #         1280 → 254／280／280（同上）
    #       ⇒ 三張卡的自然高度**每一張都已經超過 190**，下限碰不到它們。
    #       **留著它＝留一個看起來在做事、實際上是死的數字**（⛔ 正是本輪要清的東西）。
    #    ② **⛔ 不換一個更大的數字頂上**：要真的等高，下限必須**大於當下最高的那一張**，
    #       而那個值**隨視窗寬劇烈漂移** —— 實測 218（1920）／252（1440）／280（1280）／
    #       443（1152）／688（1024，`st.columns` 在窄視窗**不會**收成一欄）。
    #       挑 280 ⇒ 1920 上憑空多出 88px 空白、1024 上照樣不等高；挑 688 ⇒ 寬螢幕慘不忍睹。
    #       **沒有任何單一數字同時成立** —— 再挑一個只是把 190 的下場重演一次
    #       （§-2：⛔ 不做沒驗過的宣稱；§3.3：⛔ 不發明數字）。
    #
    # ⚠️ **據實揭露，⛔ 不吞（§-2 規則 6）**：
    #    (a) **「三張等高」自本輪起⛔ 沒有被任何機制保證。** 上面第 ① 點證明的是
    #        「**移除它不會讓畫面動一個像素**」，⛔ 不是「等高還在」。
    #        等高**是被同日那個 3 列 fact 的裁示弄掉的**，⛔ 不是被這次移除弄掉的。
    #    (b) **真要等高得換機制**（讓卡片撐滿 `st.columns` 的欄高），而那要寫
    #        Streamlit DOM 的選擇器（`[data-testid="stColumn"]` …）—— 那是**版面機制變更**，
    #        依 `CLAUDE.md §-1.5.D §03-2 ①` **必須先出線框草稿送客戶拍板**，
    #        ⛔ 不由本組逕行決定。**本輪只移除死碼，⛔ 不動版面機制。**
    #    (c) **未量到的一種情形**：三張卡**同時 live**（有大字、無 fact 列）時自然高度可能
    #        低於 190，那時舊下限**仍會有作用**。冷啟動量不到那個狀態，本組**沒有量**
    #        ⇒ 這是**待驗事項**，⛔ 不得當成「移除在所有狀態下都是 no-op」。
    out += [
        "/* ── 卡內結構 ── */",
        ".blk-head{display:flex;justify-content:space-between;align-items:center;"
        "gap:" + _var("--sp-3") + ";flex-wrap:wrap}",
        # ── 卡頭防換行（客戶 2026-09-24 裁示 ③）──────────────────────
        # 症狀：`.blk-head` 是 `flex-wrap:wrap`，兩個子項預設 `min-width:auto`
        # （＝ min-content）⇒ 長標題「指標危險度（不含多空方向）」的 min-content 寬
        # ＋ gap ＋ 徽章寬 > 卡寬時，**徽章整顆被擠到第二行**。
        # 🔴 **關鍵是 `flex-basis:0`，⛔ 不是 `min-width:0`（本輪實測踩過）**：
        # `flex-wrap` 先用**內容寬**把子項分行，分完才在行內壓縮 ⇒ 只給 `min-width:0`
        # 徽章**照樣換行**（量到 `badgeWrapped: true`）。把標題的 flex 基準設成 0，
        # 分行階段它就佔 0 寬 ⇒ 兩者永遠同一行，剩餘空間再回頭給標題。
        # 徽章 `flex-shrink:0` 擋的是另一半：⛔ 不准被壓扁（它 `white-space:nowrap`）。
        # ⛔ **⛔ 不給標題 `text-overflow:ellipsis`**：縮窄之後標題會**折行**，
        # 一個字都不會被吃掉；加省略號才是真的把字刪掉（CLAUDE.md §1）。
        # ⚠️ 與 `.blk-fact-k` 的 `flex-shrink:0` 同族（flex 溢位控制**關鍵字**，⛔ 不是
        # 設計數字）⇒ 就地寫、⛔ 不進 `components.py`，理由見下方 `.blk-fact-k` 那段。
        ".blk-head>.bdg{flex-shrink:0}",
        ".blk-title{flex:1 1 0;min-width:0}",
    ]
    for tier in _TIERS_ON_PAGE:
        spec = components.CARD_TIERS[tier]
        decls = [f"font-size:{_px(float(spec['title_px']))}",
                 f"font-weight:{spec['title_weight']}"]
        # `title_color` 只有 t4 由規格指定；其餘三階規格未覆寫 ⇒ 承襲卡面主文字色，
        # ⛔ 不自己挑一個（那就是發明規格值）。
        if spec["title_color"] is not None:
            decls.append(f"color:{_var(str(spec['title_color']))}")
        out.append(f".blk-{tier} .blk-title{{{';'.join(decls)}}}")

    # ── 大字區（卡內主數值 ＝ KPI）──
    # 🔴 **四個通道全部來自 `components.CARD_VALUE`，⛔ 本檔不挑任何一個數字。**
    #    少掉 `font-size` 的後果不是「沒設定」而是「承襲卡面字級」⇒ 觀測值跟卡標一樣大，
    #    `UI_PRINCIPLES.md` 第 6 條「KPI ≥ 20px」在畫面上就不成立（見檔頭 2026-09-21 更正）。
    # ⚠️ `font-family` 走 `var(--mono)`：等寬 ＋ `tabular-nums` 是**一組的** ——
    #    只留 `tabular-nums` 而讓字族退回比例字體，數字仍然不會對齊。
    val = components.CARD_VALUE
    out.append(
        f".blk-val{{font-size:{_px(float(val['font_px']))};"
        f"font-weight:{val['font_weight']};"
        f"font-family:{_var(str(val['font_family']))};"
        f"line-height:{float(val['line_height']):g};"
        f"font-variant-numeric:{val['font_variant_numeric']}}}"
    )

    # ── t4（佐證階）的大字區覆寫 ──────────────────────────────────
    # 客戶 2026-09-23 指令逐字：「新增 `.blk-t4 .blk-val` 22px」。
    # 🔴 **基準 `.blk-val` 的 24px 一字未動**（同輪客戶拍板「B」：主數字維持 24px）——
    #    本條只把**最密的那一階**的大字降一級，⛔ 不改 KPI 的契約值。
    #
    # ⚠️ **這個 22 是本檔唯一沒有契約層出處的字級，據實揭露（CLAUDE.md §3.3）**：
    #    `components.CARD_VALUE` 只有單一 `font_px`，沒有「逐階大字」這張表，
    #    而客戶同輪明文約束 ⛔ 不碰 `components.py` / `tokens.py` ⇒ 本輪無法把它放進契約層。
    #    **值的出處是客戶指令本身**（⛔ 不是本檔挑的），但它**沒有** `CARD_VALUE` 那樣的
    #    規格條文背書 ⇒ 要調整請先補契約層（`CARD_TIERS[*]` 增一個 `value_px` 欄），
    #    ⛔ 不要在本檔長出第二張字級表。
    # ⛔ **不掛到 `components.BADGE_BASE['font_px']` 之類「剛好也是 11.5／22」的既有常數**
    #    —— 同數字不同義的耦合正是 `signal_thresholds` 前綴分名要防的事。
    #
    # 🔴 **選擇器的兩個前提，缺一這條就是死 CSS**：
    #    ① `t4` 真的有 block 掛在上面（否則 `.blk-t4` 從不出現在 HTML 上）——
    #       故與全檔其餘 `.blk-t*` 規則一樣，以 `_TIERS_ON_PAGE` 把關，⛔ 不無條件輸出；
    #    ② `.blk-val` 是 `.blk-t4` 的**後代**（`card_html` 把大字畫在卡 div 內）。
    #    特異性 (0,2,0) > 基準 `.blk-val` (0,1,0) ⇒ 與 CSS 出現順序無關，⛔ 不靠排序取勝。
    if "t4" in _TIERS_ON_PAGE:
        out.append(".blk-t4 .blk-val{font-size:22px}")

    # ── 明細列（`.blk-fact-*`）的主從對比 ──────────────────────────
    # 客戶 2026-09-23 指令逐字：key 改 `--ink-3` ＋ `font-size:11.5px`；value 加 `color:var(--ink)`。
    # 目的是把「鍵弱／值強」的階差做出來（改之前 key 是 `--ink-2`、value 沒有 color ⇒
    # value 承襲卡面主文字色，兩者對比只剩一階）。
    # ⚠️ `--ink-3` 的可讀性有守衛：`test_tokens.py` 釘住它對 `--paper`／`--panel`／`--panel-2`
    #    三個背景都 ≥ WCAG AA 4.5 ⇒ 降一階**不會**把明細鍵降到讀不到。
    # ⚠️ 11.5px 與 `UI_PRINCIPLES.md` 第 6 條「明細 ≤ 13px」相容；同頁 `page_today`
    #    的等權揭露句（`--ink-3` ＋ 11.5px）是同一組說明字級的既有先例。
    out += [
        ".blk-lvl{color:" + _var("--ink-2") + "}",
        ".blk-facts{margin-top:" + _var("--sp-3") + "}",
        ".blk-fact{display:flex;justify-content:space-between;align-items:center;"
        "gap:" + _var("--sp-3") + ";"
        "padding-top:" + _var("--sp-1") + ";padding-bottom:" + _var("--sp-1") + ";"
        "border-top-width:1px;border-top-style:solid;border-top-color:" + _var("--grid") + "}",
        ".blk-fact:first-child{border-top-width:0px}",
        # ── 明細列 key 的防擠壓（客戶 2026-09-23 裁示 (a)）──────────
        # 症狀：`.blk-fact` 是 `display:flex` ＋ `justify-content:space-between`，
        # 兩個子項的 `flex-shrink` 都是預設 1 ⇒ value 一長就把 key 壓成一條窄欄，
        # 文字逐字換行成**直排**（實機三張並排、卡寬 ≤400px 的每一個量到的寬度都中招）。
        # `flex-shrink:0` 讓 key 不被壓到內容寬以下、`white-space:nowrap` 讓它即使
        # 被壓也不換行 —— 🔴 **兩個要一起下**，只下一個在極窄卡上仍會直排。
        #
        # ⚠️ **為什麼這兩項就地寫、⛔ 不進 `components.py`**（據實揭露判斷依據）：
        #    本檔的分工是「**設計值**走契約層（顏色→token、間距→`SPACING`、幾何數字
        #    →`components.*`），**版面結構關鍵字**就地寫」。這兩項與同檔既有的
        #    `.grd>*{min-width:0}`、`.blk-fact{display:flex;…}`、`.blk-head{…;flex-wrap:wrap}`
        #    同族 —— 都是 flex/grid 的**溢位控制關鍵字**，⛔ 不是可調的設計數字。
        #    ⛔ **不為它新開一張 `components` 規格表**：`.blk-fact-*` 在契約層**本來就
        #    沒有**規格 dict（同列的 `--ink-3` 與 11.5px 也是就地寫，出處是客戶指令），
        #    新開一張表就得把那兩個值一併搬過去，否則同一條規則會長出第二個真相源
        #    （CLAUDE.md §2.1）—— 那超出本輪「修直排」的範圍。要補請整條一起補，⛔ 不要半套。
        ".blk-fact-k{color:" + _var("--ink-3") + ";font-size:11.5px;"
        "flex-shrink:0;white-space:nowrap}",
        ".blk-fact-v{color:" + _var("--ink") + ";font-variant-numeric:tabular-nums}",
    ]
    return out


def _fold_rules() -> list[str]:
    """「▸ 詳細」純 CSS 開關（客戶 2026-09-25 選 (b)，取代原生 `<details>`）。

    🔴 **只新增 `.blk-fold*` 選擇器**，⛔ 不改任何既有規則 ⇒ 非燈卡的卡逐 byte 不受影響
    （它們的 HTML 裡根本沒有這些 class）。
    · input 以「視覺隱藏」而非 `display:none` 藏起來：仍可被 label 切換、可鍵盤聚焦；
      `.blk-fold{position:relative}` 讓它定位在開關旁 ⇒ 聚焦時⛔ 不會把頁面捲走。
    · body 預設 `display:none`，`:checked ~` 才 `display:block`（⛔ 無 JS）。
    · label `display:block` ＋ 上下 `--sp-2` 內距 ⇒ 整條卡寬都是觸控區；
      `-webkit-tap-highlight-color:transparent` 拿掉 iOS 點按的灰框。
    """
    return [
        "/* ── 燈卡「▸ 詳細」純 CSS 開關 ── */",
        ".blk-fold{position:relative}",
        ".blk-fold-i{position:absolute;top:0;left:0;width:1px;height:1px;"
        "margin:0;padding:0;opacity:0;pointer-events:none}",
        ".blk-fold-s{display:block;cursor:pointer;"
        "padding-top:" + _var("--sp-2") + ";padding-bottom:" + _var("--sp-2") + ";"
        "-webkit-tap-highlight-color:transparent;-webkit-user-select:none;user-select:none}",
        ".blk-fold-i:focus-visible~.blk-fold-s{outline:1px dotted currentColor}",
        ".blk-fold-b{display:none}",
        ".blk-fold-i:checked~.blk-fold-b{display:block}",
    ]


def _badge_rules() -> list[str]:
    """徽章：`.bdg` 共用幾何 ＋ `.bdg-{n}` 編號配色 ＋ `.sb-{key}` 尺寸。

    🔴 **兩個命名空間零交集**：`.bdg-{n}` 是**編號**（1~9），`.sb-{key}` 是**尺寸**
    （`b1`~`b4`，依卡層 t1→b1…t4→b4）。⛔ 編號不得寫成 `.b1`——
    那會讓「第 1 號徽章」與「最大尺寸」變成同一個 class，CSS 互相蓋掉，
    而蓋出來的畫面看起來完全正常（錯的尺寸配對的顏色）。

    🔴 **顏色一律住 `<style>`，⛔ 不進 inline style** —— inline 顏色繞過 `:root` 的
    dark/light 切換，換模式就變成一片對不上的顏色。
    """
    geo = components.BADGE_BASE
    out = [
        "/* ── 徽章共用幾何 ── */",
        ".bdg{display:" + str(geo["display"]) + ";align-items:center;"
        f"gap:{_px(float(geo['gap_px']))};"
        f"border-radius:{_px(float(geo['radius_px']))};"
        f"{_pad(geo['padding_px'])};"
        f"font-size:{_px(float(geo['font_px']))};font-weight:{geo['font_weight']};"
        f"white-space:{geo['white_space']};"
        f"{_border(float(geo['border_width_px']), str(geo['border_style']))}}}",
        "/* ── 徽章編號配色（⛔ #9 與 #1 零共用色 token）── */",
    ]
    for n in sorted(page_today.BADGES_ON_PAGE):
        spec = components.badge(n)
        out.append(
            f".bdg-{n}{{background:{_var(str(spec['bg']))};color:{_var(str(spec['fg']))};"
            f"{_border(float(spec['border_width_px']), str(spec['border_style']), str(spec['border_color']))}}}"
        )

    out.append("/* ── 徽章尺寸（依所在卡層 t1→b1 … t4→b4）── */")
    for key, size in components.SBADGE_SIZES.items():
        out.append(
            f".bdg.sb-{key}{{font-size:{_px(float(size['font_px']))};"
            f"{_pad(size['padding_px'])};"
            f"min-height:{_px(float(size['min_height_px']))};"
            f"border-width:{_px(float(size['border_width_px']))};"
            f"border-radius:{_px(float(size['radius_px']))}}}"
        )
    return out


def _breakpoint_rules() -> list[str]:
    """兩個 `@media` 斷點 —— 斷點數字取 `components.BREAKPOINTS`，⛔ 不寫死 640／880。

    🔴 **三段欄數全部顯式寫出來，即使三個值相同**（如 `(1,1,1)`）：
    顯式寫出來，下一個人才看得到「這是刻意的」而不是「漏寫」。
    ⚠️ 順序：先 880 後 640 —— 640 也命中 `max-width:880px`，後者必須寫在後面才蓋得過。
    ⚠️ 全檔**只准出現這兩個 `max-width`**：多一個 `max-width:1100px` 之類的排版限寬，
    就會讓「斷點只有兩個」這件事在文字上不成立（也真的會排錯）。
    """
    bp = components.BREAKPOINTS
    out: list[str] = []
    for max_px in (bp["tablet_max_px"], bp["mobile_max_px"]):
        inner: list[str] = []
        for cols in _BLOCK_COLS_USED:
            n = components.resolve_cols(cols, max_px)
            inner.append(f".{_block_cols_class(cols)}{{{_grid_template(n)}}}")
        for cols in _LAYER_COLS_USED:
            n = components.resolve_cols(cols, max_px)
            inner.append(f".{_layer_cols_class(cols)}{{{_grid_template(n)}}}")
        if max_px == bp["mobile_max_px"]:
            # 四階中只有 t1 在契約裡有手機內距覆寫值；其餘三階規格未給 ⇒ ⛔ 不發明。
            for tier in _TIERS_ON_PAGE:
                mobile = components.CARD_TIERS[tier]["padding_mobile_px"]
                if mobile is not None:
                    inner.append(f".blk-{tier}{{{_pad(mobile)}}}")
        out.append(f"@media (max-width:{max_px}px){{{''.join(inner)}}}")
    return out


def page_css(mode: str) -> str:
    """整頁樣式表的內容（**不含** `<style>` 標籤 —— 怎麼注入是 `render.py` 的事）。

    `mode` 只能是 `"dark"` / `"light"`（由 `tokens.get_token` 把關）。
    任何一個 token 拿不到 → `TokenNotSpecifiedError` / `KeyError`，**整張 sheet 不產出**。
    """
    palette = _resolve_palette(mode)   # 🔴 先全部解析完；炸在產生任何 CSS 之前
    blocks: list[str] = [_root_rule(palette)]
    blocks += _grid_rules()
    blocks += _card_rules()
    blocks += _badge_rules()
    blocks += _fold_rules()
    blocks += _breakpoint_rules()
    return "\n".join(blocks)


# ══════════════════════════════════════════════════════════════════
# 3. HTML 片段
# ══════════════════════════════════════════════════════════════════
def badge_html(n: int, *, size: str | None = None) -> str:
    """一顆狀態徽章。

    `size` 為 `components.SBADGE_SIZES` 的鍵（`b1`~`b4`），由 `card_html` 依卡層帶入；
    單獨使用時省略即為 `.bdg` 基準尺寸。

    🔴 **圖示＋文字兩者都畫**（`UI_COMPONENTS` §2 硬規則）：⛔ 不得只靠顏色。
    圖示掛 `aria-hidden` —— 扛語意的是文字，圖示只是視覺輔助。
    """
    spec = components.badge(n)   # n 不在 1~10 → KeyError（⛔ 不回一個「差不多」的）
    classes = ["bdg", f"bdg-{n}"]
    if size is not None:
        if size not in components.SBADGE_SIZES:
            raise KeyError(
                f"未知的徽章尺寸 {size!r}：只有 {sorted(components.SBADGE_SIZES)}"
            )
        classes.append(f"sb-{size}")
    return (
        f'<span class="{" ".join(classes)}">'
        f'<span aria-hidden="true">{_esc(spec["icon"])}</span>'
        f'<span>{_esc(spec["text"])}</span>'
        f'</span>'
    )


#: 明細列**值**那一格的**顯示**字數上限。超過就截斷，
#: **完整原文一字不少地掛在該格的 `title=`（hover 看得到）**。
#:
#: 🔴 **截斷的是「顯示」，⛔ 不是內容**（CLAUDE.md §1）：⛔ 不得改成「只印前 N 字、
#: 其餘丟掉」—— 那是無聲丟棄，畫面看起來正常，而使用者永遠不知道後面還有兩百個字。
#:
#: ⚠️ **據實揭露（CLAUDE.md §3.3 反捏造）：這個數字沒有契約層出處，是實作層挑的。**
#: `components.py` 只有幾何與字級，v2 契約層**沒有**「一列幾個字」這張表。
#: 就地標明它是實作層挑的，⛔ 不假裝它有出處。
#:
#: ~~處置照 `src/ui/views/page_today.py::V2_LEVEL_MAX_CHARS` 的**既有先例**辦：~~
#: ~~⛔ **兩者⛔不是同一個真相源**：那一個管整行判決區、這一個管明細列右欄…~~
#: 📌 **2026-09-24 事實更正 —— 有意識的更正，⛔ 不是漏刪；決策者：AI 總管。**
#: 那個「另一個 46」（`page_today.V2_LEVEL_MAX_CHARS`）**已經不存在了**
#: —— 頁1 整頁卡化後它 0 caller，同批刪除（理由寫在它的原址）。
#: **現行：全頁只剩本常數一個 46**；`page_today.V2_WHY_MAX_CHARS` **直接讀本常數**
#: （`V2_WHY_MAX_CHARS = v2_markup.FACT_VALUE_MAX_CHARS`）。
#: ✅ **方向仍然合法，⛔ 不是反向依賴**：是**下游的 L5 view 讀本檔**，
#: ⛔ 不是本檔讀它 —— 本檔 `import` 清單一個字未動（仍只有 `components` /
#: `page_today`〔＝ `src/ui_v2/page_today.py` 契約層〕/ `tokens`）。
#: ⚠️ **舊註「兩者不是同一個真相源」的理由在它寫下的當天成立**（判決區與明細列右欄
#: 寬度本來就不同）；**被權衡掉的是它的前提** —— 判決區那一條夾子本身已經退場，
#: 「兩者」只剩一者。哪天契約層長出「一列幾個字」的表，**搬的是本常數**。
#: ⚠️ 它**保證不了**「恰好一行」—— 實折幾行取決於欄寬。本常數做到的是
#: 「把 200+ 字壓到這個量級」，⛔ 不是「保證一行」（§-2：⛔ 不做沒驗過的宣稱）。
FACT_VALUE_MAX_CHARS: Final[int] = 46

#: 截斷記號。純排版符號，⛔ 不屬於任何狀態 glyph 家族。
FACT_VALUE_ELLIPSIS: Final[str] = "…"

#: 摺疊區的開關字。客戶 2026-09-25 核可線框逐字「▸ 詳細」。
#: 📌 **2026-09-25 更正 —— 有意識的更正，⛔ 不是漏刪；決策者 user（客戶選 (b)）。**
#: ~~原生 `<details><summary>`：⛔ 無 JS、⛔ 無 hover —— 手機點按與桌機點擊同一條路。~~
#: 舊做法的理由（無 JS、無 hover）**仍然成立**；被推翻的是「手機點按與桌機同一條路」
#: 這個前提 —— 客戶實機回報 iPhone（iOS WebKit）點了沒反應。
#: **現行**：純 CSS 開關 —— 隱藏的 `<input type="checkbox" id=…>` ＋ `<label for=…>`
#: ＋ 兄弟選擇器 `.blk-fold-i:checked ~ .blk-fold-b{display:block}`（樣式見 `_fold_rules`）。
#: 仍然 ⛔ 無 JS、⛔ 無 hover。
FOLD_SUMMARY_TEXT: Final[str] = "▸ 詳細"

#: 摺疊開關 `id` 的前綴；`id` 由卡 key 決定（`fold_dom_id`），**同一張卡每一輪 rerun 都相同**
#: ⇒ React 比對得到同一個 DOM，展開狀態不會因 rerun 被換掉。
FOLD_ID_PREFIX: Final[str] = "fold-"
_FOLD_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9-]+$")


def fold_dom_id(key: str) -> str:
    """卡 key → 摺疊開關的 DOM `id`（決定性、只含 `[a-z0-9-]`）。

    例：`detail.bias_240` → `fold-detail-bias-240`。
    ⚠️ 不同 key 理論上可能洗成同一個 id（`a.b` 與 `a_b`）—— 本頁 16 張的唯一性由
    `tests/ui_v2/test_lamp_card_fold.py` 釘住，⛔ 不在這裡假設。
    """
    slug = re.sub(r"[^a-z0-9]+", "-", str(key).lower()).strip("-")
    if not slug:
        raise ValueError(f"卡 key {key!r} 洗完是空字串，產不出摺疊開關 id")
    return FOLD_ID_PREFIX + slug


def _fact_value_cell(value: object) -> str:
    """明細列**值**那一格：長值截斷顯示，完整原文進 `title=`。

    ⚠️ `title` 走 `_esc`（`quote=True`）⇒ 引號也會被轉義，⛔ 不會把屬性提前收掉。
    ⚠️ 短值**一個字都不動、也不多掛 `title`** —— 沒有被截斷的東西掛 hover
    只會讓「有 hover ＝ 還有沒顯示完的字」這個訊號失效。
    """
    text = str(value)
    if len(text) <= FACT_VALUE_MAX_CHARS:
        return f'<span class="blk-fact-v">{_esc(text)}</span>'
    shown = text[:FACT_VALUE_MAX_CHARS] + FACT_VALUE_ELLIPSIS
    return (f'<span class="blk-fact-v" title="{_esc(text)}">'
            f'{_esc(shown)}</span>')


def _facts_block(rows: Sequence[tuple[object, object]]) -> str:
    """`.blk-facts` 一段（卡面與摺疊區共用同一支 ⇒ 兩邊的列逐 byte 同構）。"""
    out = ['<div class="blk-facts">']
    for key, val in rows:
        out.append(
            '<div class="blk-fact">'
            f'<span class="blk-fact-k">{_esc(key)}</span>'
            + _fact_value_cell(val)
            + '</div>'
        )
    out.append('</div>')
    return "".join(out)


def card_html(
    *,
    block: str,
    state: str,
    title: object,
    value: object = None,
    level: object = None,
    badge_n: int,
    facts: Iterable[tuple[object, object]] = (),
    folded_facts: Iterable[tuple[object, object]] = (),
    fold_id: str | None = None,
) -> str:
    """一張卡。

    · 密度階由**它所在的層**決定（`page_today.tier_for_block`），⛔ 沒有手選的入口。
    · 大字區（觀測值）與判決區（燈號等級）一律以 `page_today.card_value_text` /
      `card_level_text` 為準 ⇒ 灰態紅態**留白**（⛔ 無 `0`、⛔ 無上一輪殘值）、
      `degraded` **觀測照出、判決留白**。⛔ 本檔不另立第二把尺。
    · `facts` 為 `(標籤, 值)` 序列，渲染成卡內 key-value 列。**值**超過
      `FACT_VALUE_MAX_CHARS` 時**只截顯示**，完整原文掛在該格 `title=`（⛔ 一個字都沒刪）。
    · `folded_facts`（2026-09-25）：與 `facts` 同型的列，渲染進卡底一個**預設收合**的
      純 CSS 開關（隱藏 checkbox ＋ `<label>` ＝ `FOLD_SUMMARY_TEXT`，⛔ 無 `checked`）。
      列的畫法與 `facts` **同一支**（同 class、同 escape、同截斷規則）⇒ 展開後長得一樣。
      **空（預設）⇒ 整段不渲染**，輸出與加這個參數之前逐 byte 相同。
    · `fold_id`：給了 `folded_facts` 就**必填**（通常是 `fold_dom_id(card.key)`），
      只准 `[a-z0-9-]`。⛔ 不自己亂生 —— 亂數 id 每輪 rerun 都變，展開狀態會被重設。
    """
    tier = page_today.tier_for_block(block)   # 未知 block → KeyError（⛔ 不猜一階）
    if badge_n in page_today.BADGES_NOT_ON_PAGE:
        raise ValueError(
            f"#{badge_n} 不畫在這一頁（page_today.BADGES_NOT_ON_PAGE）："
            "⛔ 不得為了畫得出來就把它併進別的徽章 —— 要畫請先改規格。"
        )
    badge = badge_html(badge_n, size=str(components.CARD_TIERS[tier]["badge_size"]))
    value_text = page_today.card_value_text(state=state, value=value)
    level_text = page_today.card_level_text(state=state, level=level)

    parts = [
        f'<div class="blk blk-{tier}">',
        '<div class="blk-head">',
        f'<span class="blk-title">{_esc(title)}</span>',
        badge,
        '</div>',
    ]
    # ⚠️ 留白＝**整段不渲染**，⛔ 不畫一個 `0`、⛔ 不畫「--」以外的任何代打值。
    if value_text is not None:
        parts.append(f'<div class="blk-val">{_esc(value_text)}</div>')
    if level_text is not None:
        parts.append(f'<div class="blk-lvl">{_esc(level_text)}</div>')
    rows = tuple(facts)
    if rows:
        parts.append(_facts_block(rows))
    folded = tuple(folded_facts)
    if folded:
        # 🔴 2026-09-25 客戶選 (b)：原生 `<details>` 在 iPhone 點了沒反應 ⇒ 改純 CSS 開關。
        #    input 必須排在 body **之前**（`~` 只往後找兄弟）；label 靠 `for` 綁 input，
        #    樣式全在 `page_css()` 的 `_fold_rules()`（只新增 `.blk-fold*` 選擇器）。
        if fold_id is None or not _FOLD_ID_RE.match(fold_id):
            raise ValueError(
                f"有摺疊列就必須給合法的 fold_id（[a-z0-9-]+），實得 {fold_id!r}")
        parts.append(
            '<div class="blk-fold">'
            f'<input type="checkbox" class="blk-fold-i" id="{fold_id}">'
            f'<label class="blk-fold-s" for="{fold_id}">{_esc(FOLD_SUMMARY_TEXT)}</label>'
            '<div class="blk-fold-b">'
            + _facts_block(folded)
            + '</div></div>'
        )
    parts.append('</div>')
    return "".join(parts)


def grid_html(*, block: str, cards: Sequence[str]) -> str:
    """一個 block 的**卡內**網格容器 ＋ 內含的卡。

    🔴 **整段自閉合**：`<div>` 開閉數相等，因為這一整塊要在**一次**
    `st.markdown(..., unsafe_allow_html=True)` 裡吐完 —— 未閉合的 `<div>`
    **不會**跨 `st.markdown` 呼叫包住下一次的產出（Streamlit 每次呼叫各自是獨立的
    DOM 節點），結果是版面靜默走樣：不會報錯、不會變紅。
    repo 先例：`src/ui/render/station_cards.py` docstring 逐字
    「整面牆是一次 `st.markdown` 的純 HTML」。

    `cards` 是**已渲染好的 HTML 片段**（通常來自 `card_html`），⛔ 不再 escape。
    """
    cols = page_today.BLOCK_COLS[block]        # 未知 block → KeyError（⛔ 不猜欄數）
    tier = page_today.tier_for_block(block)
    classes = f"grd grd-{tier} {_block_cols_class(cols)}"
    return f'<div class="{classes}">' + "".join(cards) + "</div>"


def layer_html(*, layer: int, block_htmls: Sequence[str]) -> str:
    """一**層**的層級網格容器 ＋ 內含的各 block。

    🔴 與 `grid_html` 是**兩個不同的網格**（見檔頭）：這裡排的是「同一層的幾個 block
    彼此怎麼並排」，欄數取 `page_today.LAYER_GRID_COLS`，class 前綴 `lg-`，
    **⛔ 不與 block 網格的 `g-` 撞名**。

    🔴 **沒有登記層級網格的層 → 炸**（沿用 `page_today.blocks_per_row` 的行為）。
    ⛔ 不得 try/except 吞掉改成預設 1 欄：那是 §1 的靜默造假 ——
    畫面看起來正常，實際上那個版面是編出來的。沒有層級網格的層，
    由 caller 逐 block 全寬輸出即可。

    `block_htmls` 是**已渲染好的 HTML 片段**（通常來自 `grid_html`），⛔ 不再 escape。
    """
    if layer not in page_today.LAYER_GRID_COLS:
        raise KeyError(
            f"第 {layer!r} 層沒有登記層級網格：只有第二層有來源"
            "（客戶 2026-09-16「3 張並排卡」＋ 原型 `.g3` 實測）。"
            "⛔ 不得為了畫得出來就給它一個猜的欄數 —— 要填請先補規格與來歷。"
        )
    cols = page_today.LAYER_GRID_COLS[layer]
    tier = components.tier_for_layer(layer)
    classes = f"lyr lyr-{tier} {_layer_cols_class(cols)}"
    return f'<div class="{classes}">' + "".join(block_htmls) + "</div>"


__all__ = ["page_css", "badge_html", "card_html", "grid_html", "layer_html"]
