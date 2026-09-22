"""產生器：由 `src/ui_v2/` 的公開 API 產出獨立 HTML 原型 `today_v2.html`。

⚠️ **這是開發工具，⛔ 不是 production code。**
   `src/` 底下**沒有任何模組 import 它**（它只 import `src.ui_v2`，方向是單向的），
   它也**不在 `CLAUDE.md §8.2` 的七層分層裡** —— `tests/test_c3_layering_guard.py`
   的 `_SCAN_ROOTS` 只走 `shared/` `src/` `scripts/` ＋ 根目錄 `app.py`，⛔ 不掃 `docs/`。
   ⛔ **刻意不放 `scripts/`**：那個目錄在該守衛裡被標為 **L1 Data**，
   而本檔 import `src.ui_v2`（**L5**）⇒ 放進去就是一條 L1→L5 的跨層上行違憲。

**為什麼它必須進 repo（本檔存在的唯一理由）**
   產物 `today_v2.html` 的檔頭自稱「由 `src/ui_v2/` 產生的靜態快照」並附了重建配方，
   但產生器若只活在某個 session 的暫存區，**那句宣稱就沒有人能複驗** ——
   那正是 `CLAUDE.md §-2` 點名的「**沒查證的宣稱比沒有宣稱更危險**」：
   下一個人（含未來的 AI）會建立在「這個檔是同源產生的」這個假前提上繼續蓋。
   把產生器放進來，那句宣稱就從**信我**變成**你自己跑一次**。

**怎麼跑**
   ```
   python docs/v2/prototype/gen_today_v2.py
   ```
   ⛔ 不吃參數、⛔ 不讀環境變數、⛔ 不連網；就地覆寫同目錄的 `today_v2.html`，
   並在尾端跑一輪自驗（見 `main()` 末段）。任何一項不過就 `AssertionError`，
   **⛔ 不會留下半套 HTML 的成功假象**（§1 Fail Loud）。

🔴 **同源，⛔ 不手抄**：CSS 與卡片標記一律由 `src/ui_v2/markup.py` 的公開函式產生；
   本檔**不寫任何色碼**、**不寫任何 px 字面值** —— 所有幾何數字都從
   `components.*` / `page_today.*` / `tokens.*` 取回來再格式化成 CSS 長度。
⛔ **不碰底線開頭的私有符號**（`markup._root_rule` / `markup._px` / `_resolve_palette` …）
   —— 本 repo 有一筆登記在案的違憲 `V-PICKER-PRIV-1` 就是跨層直取私有符號。

兩套色的併法：**選 (b)「只重新宣告 :root」**，理由見下方 `_theme_css()` 的註解。
"""
from __future__ import annotations

import datetime
import ast
import contextlib
import hashlib
import pathlib
import re
import subprocess
import sys
import types
from html import escape
from typing import Iterator, Mapping, Sequence

# 本檔位置 ＝ `<repo>/docs/v2/prototype/gen_today_v2.py` ⇒ 往上第 3 層是 repo 根。
# ⛔ **不寫死絕對路徑**：原版寫死 `/home/user/my-stock-dashboard`，換一台機器／換一個
#    checkout 就跑不動 —— 而「**真的跑得起來**」正是本檔進 repo 的唯一理由。
REPO = pathlib.Path(__file__).resolve().parents[3]
#: 產物與本檔**同目錄**（搬家時兩個一起搬，⛔ 不會各走各的）。
OUT = pathlib.Path(__file__).resolve().parent / "today_v2.html"

# §1 Fail Loud：路徑推導錯了**當場炸**，⛔ 不要等到 import 才丟一個看不懂的 ModuleNotFoundError。
assert (REPO / "src" / "ui_v2").is_dir(), (
    f"REPO 推導錯誤：{REPO} 底下沒有 src/ui_v2/。"
    "本檔是不是被搬離 docs/v2/prototype/ 了？（parents[3] 是依那個位置算的）"
)
sys.path.insert(0, str(REPO))

from src.ui_v2 import components, markup, page_today, tokens  # noqa: E402

# 五頁的顯示名 SSOT ＝ L0 `shared/ia_nav.py`（純字串、零 streamlit、零 L1+ 依賴）。
# 🔴 **一律 import，⛔ 不手抄那五個字串** —— 該檔檔頭逐字自陳「任何地方都不准手抄字串」，
#    `app.py` 自己也照辦（`from shared.ia_nav import PAGE_LABELS as _IA_PAGE_LABELS`）。
#    手抄 ＝ 製造第二份真相源（CLAUDE.md §2.1）。
# ⚠️ `ia_nav` 檔頭同時明文「**不做導覽**。它只回字串，不切分頁、不碰 session」
#    ⇒ 它是**標籤 SSOT，不是導覽元件**；導覽長什麼樣由本原型決定（見 CHROME_SPEC_GAPS G1）。
from shared.ia_nav import (  # noqa: E402
    PAGE_LABELS,
    PAGE_TODAY, PAGE_FIND, PAGE_INSPECT, PAGE_HOLD, PAGE_WHY,
)


# ══════════════════════════════════════════════════════════════════
# 0. 小工具（與 markup 同一種格式，但**不** import 它的私有函式）
# ══════════════════════════════════════════════════════════════════
def px(value: object) -> str:
    """契約層的 px 數 → CSS 長度。`2.0` → `2px`、`17.5` → `17.5px`。"""
    return f"{float(value):g}px"


def paint(token_or_keyword: object) -> str:
    """契約層的顏色欄位 → CSS 值。`"--ink"` → `var(--ink)`；`"transparent"` 原樣。"""
    text = str(token_or_keyword)
    return f"var({text})" if text.startswith("--") else text


def pad(padding_px: Sequence[float]) -> str:
    """`(上下, 左右)` → 四條 longhand（與 markup 的做法一致：longhand 兩種查法都對得上）。"""
    vertical, horizontal = padding_px
    return (
        f"padding-top:{px(vertical)};padding-bottom:{px(vertical)};"
        f"padding-left:{px(horizontal)};padding-right:{px(horizontal)}"
    )


def esc(text: object) -> str:
    return escape(str(text), quote=True)


def html_comment(text: str) -> str:
    """HTML 註解。⚠️ 內文**不得出現連續兩個半形減號**（會把註解提前關掉）。"""
    assert "--" not in text, "註解含連續兩個減號，會把 HTML 註解提前關掉"
    return "<!--\n" + text + "\n-->"


# ══════════════════════════════════════════════════════════════════
# 1. 兩套色怎麼併 —— 作法 (b)：只重新宣告 :root
# ══════════════════════════════════════════════════════════════════
def _root_rule_of(mode: str) -> str:
    """把 `page_css(mode)` 的 `:root{…}` 那一條**原樣取出來**（⛔ 不自己重組字串）。

    取法本身帶三道自驗，任何一道不過就炸（⛔ 不留半套 CSS）：
      ① 第一行必須是 `:root{…}`；
      ② `page_css('dark')` 與 `page_css('light')` 去掉第一行後**必須逐字相同**
         ⇒ 證明「第一行是唯一與模式相關的規則」，(b) 因此與 (a) 等價、零損失；
      ③ 與「用 `tokens.get_token(name, mode=…)` ＋ `tokens.SPACING` ＋
         `components.FONT_STACKS` 獨立組出來的字串」逐字比對 ⇒ 證明取到的
         真的是整組調色盤、沒有少任何一個 token。
    """
    dark_lines = markup.page_css("dark").split("\n")
    light_lines = markup.page_css("light").split("\n")
    for lines in (dark_lines, light_lines):
        assert lines[0].startswith(":root{") and lines[0].endswith("}"), lines[0][:80]
    assert "\n".join(dark_lines[1:]) == "\n".join(light_lines[1:]), (
        "page_css('dark') 與 page_css('light') 在 :root 以外出現差異 —— "
        "作法 (b) 的前提不成立，必須改走作法 (a)"
    )

    rule = {"dark": dark_lines, "light": light_lines}[mode][0]

    decls = [f"{n}:{tokens.get_token(n, mode=mode)};" for n in tokens.DARK]
    decls += [f"{n}:{v};" for n, v in tokens.SPACING.items()]
    decls += [f"{n}:{v};" for n, v in components.FONT_STACKS.items()]
    assert rule == ":root{" + "".join(decls) + "}", (
        f"{mode} 的 :root 與獨立組出來的調色盤不一致 —— 取到的不是整組 token"
    )
    return rule


def _reselect(root_rule: str, selector: str) -> str:
    """把 `:root{…}` 換一個選擇器，宣告內容**一個字都不動**。"""
    head = ":root{"
    assert root_rule.startswith(head)
    return selector + "{" + root_rule[len(head):]


def theme_css() -> str:
    """dark 是預設；light 走 media query；再加一組 `data-theme` 手動覆寫。

    🔴 **層疊順序是刻意的，四條規則缺一不可**（`:root` ＝ (0,1,0)，
       `:root[data-theme=…]` ＝ (0,2,0)，media query 本身不加權重）：
       R1 `:root{dark}`                                   ← 預設深色（位置最前、權重最低）
       R2 `@media (prefers-color-scheme: light){:root{light}}`
                                                          ← 同權重但在後 ⇒ 系統淺色時贏過 R1
       R3 `:root[data-theme="dark"]{dark}`                ← 權重較高 ⇒ **壓得過 R2**
                                                          （系統淺色下手動切深色才有反應）
       R4 `:root[data-theme="light"]{light}`              ← 權重較高 ⇒ 壓得過 R1
       ⛔ 少了 R3，使用者在 light 系統下按「切換深色」會沒反應 —— 那是最容易漏的一格。

    **為什麼選 (b) 不選 (a)**：`_root_rule_of()` 的自驗 ② 實測
    `page_css('dark')` 與 `page_css('light')` **只差第一行**（其餘 56 行逐字相同）
    ⇒ (a) 會把同一份幾何規則再貼 1~2 份，還得把 `@media (max-width:…)` 巢進
    `@media (prefers-color-scheme:…)` 裡；(b) 只多四條 `:root`，
    **拿到的畫面與 (a) 完全相同**。⛔ 兩者都不得改寫非 `:root` 的規則。
    """
    dark_root = _root_rule_of("dark")
    light_root = _root_rule_of("light")
    return "\n".join([
        "/* ── R2：系統為淺色時的調色盤（內容取自 page_css('light') 的 :root，一字未改）── */",
        "@media (prefers-color-scheme: light){" + light_root + "}",
        "/* ── R3／R4：手動切換（權重 0,2,0 ⇒ 兩個方向都壓得過 R1／R2）── */",
        _reselect(dark_root, ':root[data-theme="dark"]'),
        _reselect(light_root, ':root[data-theme="light"]'),
        "/* color-scheme 讓捲軸等瀏覽器 UI 跟著切；它不是色碼，是關鍵字 */",
        ":root{color-scheme:dark}",
        "@media (prefers-color-scheme: light){:root{color-scheme:light}}",
        ':root[data-theme="dark"]{color-scheme:dark}',
        ':root[data-theme="light"]{color-scheme:light}',
    ])


# ══════════════════════════════════════════════════════════════════
# 2. 原型外殼（chrome）的 CSS —— `page_css()` 不產這些，但每個值都有出處
# ══════════════════════════════════════════════════════════════════
def _button_rules(selector: str, spec: Mapping[str, object]) -> list[str]:
    decls = [
        "display:inline-flex", "align-items:center", "justify-content:center",
        f"min-height:{px(spec['min_height_px'])}",
        pad(spec["padding_px"]),                      # type: ignore[arg-type]
        f"font-size:{px(spec['font_px'])}",
        f"font-weight:{spec['font_weight']}",
        f"border-radius:{px(spec['radius_px'])}",
        f"background:{paint(spec['bg'])}",
        f"border-width:{px(spec['border_width_px'])}",
        f"border-style:{spec['border_style']}",
        f"border-color:{paint(spec['border_color'])}",
        f"color:{paint(spec['fg'])}",
        "cursor:pointer",
    ]
    if "min_width_px" in spec:
        decls.append(f"min-width:{px(spec['min_width_px'])}")
    out = [selector + "{" + ";".join(decls) + "}"]
    hover = spec.get("hover")
    if hover:
        hov = [f"{k.replace('_', '-').replace('fg', 'color').replace('bg', 'background')}"
               f":{paint(v)}" for k, v in hover.items()]
        out.append(selector + ":hover{" + ";".join(hov) + "}")
    return out


def chrome_css() -> str:
    """原型外殼樣式。

    ⚠️ **這一段不是 `page_css()` 產的**（`markup` 沒有頁殼／按鈕的規則），
    但**每一個數字仍取自契約層**，出處逐條寫在下面的 CSS 註解裡。
    ⛔ 唯一沒有出處的是 `body` 的 `font-family` 系統字堆疊 ——
    `UI_TOKENS.md §B` 的字型 token 還沒落地到 `tokens.py`
    （`components.FONT_STACKS` 只有 `--mono`，其註解自陳那是暫時落地點），
    故本頁**不設內文字級與行高**，讓它退回瀏覽器預設，
    ⛔ 不自己挑一個「看起來合理」的數字（CLAUDE.md §3.3 反捏造）。
    """
    t1 = components.CARD_TIERS["t1"]
    t3 = components.CARD_TIERS["t3"]
    base = components.CARD_BASE
    ring = components.FOCUS_RING
    disclosure = page_today.HOLDINGS_EQUAL_WEIGHT_DISCLOSURE
    value = components.CARD_VALUE

    rules = [
        "/* ── 版面骨架：只用 --sp-* 間距 token，⛔ 無限寬容器 ── */",
        "/*    ⛔ 刻意不加 max-width：多一個排版限寬會讓「斷點只有兩個」不成立， */",
        "/*    也會讓 1→2→3 欄的斷點對不上真正的視窗寬（markup._breakpoint_rules 同旨）*/",
        "*{box-sizing:border-box}",
        "body{margin:0;background:var(--paper);color:var(--ink);"
        "padding-left:var(--sp-6);padding-right:var(--sp-6);"
        f"padding-top:var(--sp-6);padding-bottom:var(--sp-8);"
        "font-family:system-ui,sans-serif}",
        "p{margin-top:var(--sp-2);margin-bottom:0}",

        "/* ── 焦點環：components.FOCUS_RING，全站唯一一條，⛔ 不准個別 outline:none ── */",
        f":focus-visible{{outline-width:{px(ring['outline_width_px'])};"
        f"outline-style:{ring['outline_style']};"
        f"outline-color:{paint(ring['outline_color'])};"
        f"outline-offset:{px(ring['outline_offset_px'])}}}",

        "/* ── 示意橫幅：色走 sig-amber 對（tokens A-2）、框寬取 CARD_TIERS['t1'] 的 2px、 */",
        "/*    圓角取 CARD_BASE、字級與字重取 t1 卡標 ⇒ 全頁最高視覺層級 ── */",
        f".pv-banner{{background:var(--sig-amber-bg);color:var(--sig-amber);"
        f"border-width:{px(t1['border_width_px'])};border-style:{t1['border_style']};"
        f"border-color:var(--sig-amber);border-radius:{px(base['radius_px'])};"
        f"{pad(t1['padding_px'])};"  # type: ignore[arg-type]
        f"font-size:{px(t1['title_px'])};font-weight:{t1['title_weight']}}}",

        "/* ── 頁首 ── */",
        ".pv-head{display:flex;justify-content:space-between;align-items:flex-end;"
        "gap:var(--sp-5);flex-wrap:wrap;margin-top:var(--sp-7)}",
        f".pv-title{{font-size:{px(value['font_px'])};font-weight:{value['font_weight']};"
        f"line-height:{float(value['line_height']):g}}}",
        ".pv-toggle{display:flex;align-items:center;gap:var(--sp-3);flex-wrap:wrap}",

        "/* ── 說明字：色與字級取自 page_today.HOLDINGS_EQUAL_WEIGHT_DISCLOSURE ── */",
        "/*    （該常數自陳出處為 UI_TOKENS.md §B 字型 token 表「說明」列）      ── */",
        f".pv-meta{{color:{paint(disclosure['color'])};font-size:{px(disclosure['font_px'])}}}",
        f".pv-disclosure{{color:{paint(disclosure['color'])};"
        f"font-size:{px(disclosure['font_px'])};margin-top:0;margin-bottom:0}}",
        ".pv-mono{font-family:var(--mono);font-variant-numeric:tabular-nums}",

        "/* ── 層標籤：字級／字重取 CARD_TIERS['t3'] 卡標 ── */",
        ".pv-layer{margin-top:var(--sp-8)}",
        f".pv-layer-label{{font-size:{px(t3['title_px'])};font-weight:{t3['title_weight']};"
        f"color:var(--ink-2);border-bottom-width:{px(base['border_width_px'])};"
        "border-bottom-style:solid;"
        "border-bottom-color:var(--grid);padding-bottom:var(--sp-2)}",
        ".pv-badges{display:flex;flex-wrap:wrap;align-items:center;gap:var(--sp-3);"
        "margin-top:var(--sp-3)}",
        ".pv-cta{margin-top:var(--sp-4);display:flex;align-items:center;"
        "gap:var(--sp-3);flex-wrap:wrap}",
    ]
    rules += ["/* ── 按鈕：components.BUTTONS 逐欄展開 ── */"]
    rules += _button_rules(".pv-btn-primary", components.BUTTONS["primary_cta"])
    rules += _button_rules(".pv-btn-secondary", components.BUTTONS["secondary_explain"])
    return "\n".join(rules)


# ══════════════════════════════════════════════════════════════════
# 2.5 跨頁 chrome（五頁共用殼）—— 逐字 SSOT 與它們的**產生時守衛**
#
# 客戶 2026-09-22 拍板三塊：① 五頁切換做側欄式　② 資料時點列做示意殼
# ③ 頁尾免責逐字用 SSOT　④ 第五頁用 SSOT 的「📖 憑什麼」。
# ══════════════════════════════════════════════════════════════════

#: 頁尾免責的逐字內容。**SSOT 在 `app.py` 的 `_render_footer()`。**
#:
#: 🔴 **這是一份「有守衛的複本」，⛔ 不是第二個真相源** —— 差別在於它會漂移就當場炸。
#:    `S1-6_COMPLIANCE_COPY_GUIDE.md §3.1` 逐字要求「一處常數，兩處引用」「⛔ 禁止在
#:    各頁手抄免責」，而**真正的解是把它抽成 L0 常數**。做不到的理由（實測，非推測）：
#:      (a) 它在 `app.py` 裡是**函式體內的 inline literal**，⛔ 沒有任何可 import 的名字；
#:      (b) `app.py` 是 L6 且 module-level `import streamlit` ⇒ 本產生器 import 它
#:          會在無 streamlit 的環境直接爆，而且那是一條 docs 工具 → L6 的反向依賴。
#:    ⇒ **本輪的作法**：放一份複本，並在產生時讀 `app.py` 的**原始文字**逐字比對；
#:      不符就 `AssertionError`、⛔ 不產出 HTML（§1 Fail Loud）。
#:    ⚠️ **待辦（⛔ 不在本輪授權範圍，本輪只准動本檔與 today_v2.html）**：
#:      把這個字串抽成 L0 常數（例如 `shared/compliance_copy.py`），讓 `app.py` 與本檔
#:      都改 import。那要動 `app.py` ⇒ 須另案授權。見 CHROME_SPEC_GAPS G2。
COMPLIANCE_FOOTER_TEXT = "⚠️ 台股AI戰情室 v3.0 · 僅供學術研究，非投資建議，盈虧自負"

#: 資料時點列的「尚未載入」態逐字（`S2-UI_SPEC.md §5.2` 表 ＋ `S1-4_STATE_MATRIX.md §3.8` 表）。
ASOF_IDLE_TEXT = "資料時點：尚未載入，本頁沒有任何本輪資料"

#: 六個**性質詞彙的格式**（`S2-UI_SPEC.md §5.1` 表第二欄逐字）。
#: 🔴 **本輪只列格式，⛔ 一個真值都不填** —— 見 `ASOF_SHELL_DISCLOSURE`。
ASOF_NATURE_FORMATS: tuple[tuple[str, str], ...] = (
    ("日頻收盤序列（股價／指數／匯率）", "MM-DD 收盤"),
    ("盤中／即時取得的純量", "MM-DD HH:MM 取得"),
    ("月頻總經（CPI／PMI／M1B／營收）", "YYYY-MM 資料"),
    ("季頻財報", "YYYY-Qn 財報"),
    ("盤後統計（三大法人／融資／PCR）", "MM-DD 盤後"),
    ("凍結快照（前進式驗證）", "YYYY-MM-DD 凍結"),
)

#: 時點列**就地揭露**：這一列是形狀示意，⛔ 不是真資料。
#: ⚠️ 本節以下常數會**直接渲染成畫面上的字**，故沿用本檔既有散文慣例：
#:    ⛔ 不寫 markdown（`**` / 反引號）—— 它們在 HTML 裡不會被渲染，只會露出原始符號。
#:    （既有 `_LAYER_NOTE` 同樣一個 markdown 記號都沒有；`**` 只出現在 HTML 註解裡。）
ASOF_SHELL_DISCLOSURE = (
    "⚠️ 這一列是形狀示意，⛔ 不是真資料。真實時間目前拿不到（實測，非推測）："
    "L3 canonical 總經契約 get_macro_state() 只有 9 個 key、沒有 as_of / timestamp，"
    "所以 src/ui_v2/page_today.py 把 chrome.asof 登記在 WITHDRAWN_BLOCKS（已撤回，不是待補），"
    "src/ui/views/page_today.py 的 AS_OF_NOT_IN_CONTRACT 逐字寫「寧可什麼都不寫，"
    "也不編一個時間出來」。⇒ 本頁畫出規格定義的那一列、用「尚未載入」態的逐字，"
    "⛔ 不填任何看起來像真的日期時間。下表只是可能的格式，⛔ 不是本頁的值。"
)

#: 時點列**摺疊器的 summary**。⭐ 誠實的那句話**留在收起狀態也看得見**，
#: ⛔ 被摺起來的只有「原因與可能的格式」這些細節 —— ⛔ 不是把「這是示意」藏起來。
ASOF_SHELL_SUMMARY = "▸ 這一列是形狀示意，⛔ 不是真資料（點開看原因與可能的格式）"

#: ★-05 定案逐字（`S2-UI_SPEC.md §5.4`）＋ §5.1 第 3 條書寫規則。
ASOF_NO_FRESHNESS_NOTE = (
    "S2-UI_SPEC.md 5.4 的 ★-05 定案逐字：「資料時點」只寫歸屬日 ＋ 性質，"
    "⛔ 不做「新不新鮮」的判斷；同檔 5.1 第 3 條另⛔ 禁用「今天／剛剛／最新」這類相對詞。"
)

#: 側欄式導覽的理由（客戶 2026-09-22 ①：做側欄式，⛔ 不做頂部分頁）。
NAV_WHY_SIDEBAR = (
    "⛔ 刻意不做頂部分頁列。app.py 逐字記載：2026-09-07 的 FE-7~FE-16 曾把這五頁"
    "掛成第 1~5 個頂層頁籤與舊的 7 個並排 ⇒ 手機上頁籤列 7 變 12，"
    "舊的 7 個被擠出可視範圍，客戶回報「很多 Tab 不見了」；"
    "2026-09-08 FE-35 客戶拍板方案 A 撤回該掛法，改由側欄 radio 導覽。"
    "客戶 2026-09-22 再次拍板「五頁切換：做側欄式，不做頂部分頁"
    "（走回三個月前否決過的做法）」。"
)

#: 側欄內那一行短註（⛔ 放長句會把側欄那一欄的 min-content 撐寬）。
NAV_WHY_SHORT = "⛔ 刻意不做頂部分頁列"

#: 其餘**兩**頁的佔位逐字。
#: ⚠️ **2026-09-22 更新（第一次）：原句寫「本原型只做了『🚦 今天』」，自本日起不成立** ——
#:    客戶同日拍板加做「📖 憑什麼」頁（六層 22 block），佔位頁因此從四頁減為三頁。
#: ⚠️ **2026-09-22 更新（第二次，同日）：「兩頁／三頁」自本輪起同樣不成立** ——
#:    客戶同日再拍板加做「🔍 找標的」頁（六層 14 block），佔位頁因此從三頁再減為**兩頁**
#:    （客戶逐字：「5. 其他兩頁（查一檔、我的持股）仍顯示「此頁待做」」）。
#: ⚠️ **2026-09-22 更新（第三次，同日）：佔位頁自本輪起只剩「💼 我的持股」一頁** ——
#:    客戶同日再拍板加做「🔬 查一檔」頁（五層 22 block），客戶逐字：
#:    「側欄切到「🔬 查一檔」可顯示；其他一頁（💼 我的持股）仍顯示「此頁待做」」。
#:    **有意識的更正、⛔ 不是漏刪**；⛔ 這三次都是**事實更正**，不是政策變更 ——
#:    「⛔ 不讓五頁切換假裝五頁都已完成」那句理由**一個字都沒有被弱化**。
#:    三次的舊句都加刪除線保留於下方 `TODO_BODY_SUPERSEDED`。
TODO_HEADLINE = "此頁待做"
TODO_BODY = (
    "本原型目前做了「{today}」、「{why}」、「{find}」與「{inspect}」四頁。這一頁還沒有任何實作，"
    "⛔ 不是壞掉、⛔ 也不是載入失敗 —— 畫這塊佔位，是為了不讓五頁切換假裝五頁都已完成"
    "（對照 CLAUDE.md §1：錯誤的數字比沒有數字更危險）。"
)
#: 歷代舊句，加刪除線保留 —— ⛔ 不是漏刪；決策者：客戶；日期 2026-09-22。
TODO_BODY_SUPERSEDED = (
    "~~本原型只做了「🚦 今天」。~~"
    "／／舊句在它寫下的當天是對的（那時確實只有一頁）；"
    "被權衡掉的⛔ 不是它的推理，是它的前提（「只有一頁」）。"
    "　~~本原型目前做了「🚦 今天」與「📖 憑什麼」兩頁。~~"
    "／／同理：同日再加了「🔍 找標的」，前提（「只有兩頁」）再次過期，推理仍然成立。"
    "　~~本原型目前做了「🚦 今天」、「📖 憑什麼」與「🔍 找標的」三頁。~~"
    "／／同理：同日再加了「🔬 查一檔」，前提（「只有三頁」）第三次過期，推理仍然成立 ——"
    "過期的一直是**頁數**，⛔ 從來不是「不讓切換假裝五頁都已完成」那個理由。"
)


def verbatim_sources() -> dict[str, str]:
    """把本檔所有**逐字複本**拿去跟它們的真實出處比對。任一條不符 ⇒ 當場炸。

    🔴 **這是「手抄」與「有守衛的複本」的唯一差別。** 沒有這一段，上面那些常數就是
       CLAUDE.md §2.1 禁止的第二份真相源：出處改了、複本不會跟著改，而且**沒有人會發現**。
       有了這一段，漂移會變成 `AssertionError` ⇒ fail loud（§1）。

    Returns:
        `{來源檔的相對路徑: 實際比對用的原始文字}`，供 `main()` 寫進交付紀錄。
    """
    app_py = (REPO / "app.py").read_text(encoding="utf-8")
    ui_spec = (REPO / "docs/v2/spec/S2-UI_SPEC.md").read_text(encoding="utf-8")
    state_matrix = (
        REPO / "docs/v2/spec/S1-4_STATE_MATRIX.md").read_text(encoding="utf-8")

    # ① 頁尾免責 —— 出處 `app.py::_render_footer`。
    hits = app_py.count(COMPLIANCE_FOOTER_TEXT)
    assert hits == 1, (
        f"免責逐字在 app.py 命中 {hits} 次（預期 1 次）。"
        "0 次 ＝ SSOT 改了而本檔的複本沒跟上（⛔ 不得逕自改本檔遷就，先確認是誰對）；"
        ">1 次 ＝ app.py 自己出現了第二份，違反 S1-6 §3.1「一處常數」。"
    )
    assert "_render_footer" in app_py, "app.py 找不到 _render_footer —— 出處函式被改名了？"

    # ② 時點列「尚未載入」態 —— 出處 S2 §5.2 表 ＋ S1-4 §3.8 表（兩份都要在）。
    for name, text in (("S2-UI_SPEC.md", ui_spec),
                       ("S1-4_STATE_MATRIX.md", state_matrix)):
        assert "尚未載入，本頁沒有任何本輪資料" in text, (
            f"{name} 找不到時點列「尚未載入」態的逐字 —— 規格改了，本檔的複本要跟著改")

    # ③ 六個性質詞彙格式 —— 出處 S2 §5.1 表。
    for label, fmt in ASOF_NATURE_FORMATS:
        assert fmt in ui_spec, f"S2-UI_SPEC.md 找不到性質格式 {fmt!r}（{label}）"

    # ④ 五頁標籤 —— ⛔ 沒有複本可比對（直接 import PAGE_LABELS），但順手釘住兩件事：
    #    (a) 第五頁是「📖 憑什麼」，⛔ 不是「為什麼」（客戶 2026-09-22 ④）；
    #    (b) dict 宣告序 ＝ 畫面序。
    assert PAGE_LABELS[PAGE_WHY] == "📖 憑什麼", PAGE_LABELS[PAGE_WHY]
    assert list(PAGE_LABELS) == [
        PAGE_TODAY, PAGE_FIND, PAGE_INSPECT, PAGE_HOLD, PAGE_WHY], list(PAGE_LABELS)

    # ⑤ 側欄導覽的理由 —— 出處 app.py 的 FE-35 註解。
    assert "很多 Tab 不見了" in app_py, (
        "app.py 找不到「很多 Tab 不見了」—— NAV_WHY_SIDEBAR 引述的客戶回報出處不見了")

    return {"app.py": app_py,
            "docs/v2/spec/S2-UI_SPEC.md": ui_spec,
            "docs/v2/spec/S1-4_STATE_MATRIX.md": state_matrix}


#: ⚠️ **本輪查到的規格缺口，逐條登記**（客戶指示「有洞就標」）。
#: 🔴 每一條都是 **⚠️ 單組／兩組調查結論，未經第三方驗**（CLAUDE.md §-2 規則 6）——
#:    ⛔ 不得被引用為「已查證的事實」去支撐下一步決策。
GAP_CAVEAT = "⚠️ 單組／兩組調查結論，未經第三方驗"

CHROME_SPEC_GAPS: tuple[tuple[str, str, str], ...] = (
    (
        "G1",
        "五頁導覽在規格裡沒有元件級定義 ⇒ 本原型的導覽長相是原型自創，⛔ 非規格。",
        "三條實測：(a) UI_COMPONENTS.md 只有六節元件（卡片／徽章／按鈕／表格／圖表容器／"
        "序列色），沒有 nav／側欄／分頁列；(b) 規格裡的「分頁列」一律指頁內葉列"
        "（UI_PAGE_HOLD.md：leaf:null ＝「畫在分頁列之上、兩葉共用」），⛔ 不是五頁切換；"
        "(c) 五頁切換機制規格寫的是側欄 radio（docs/v2/wireframe/wf_global.js 的 "
        "global.sidebar，逐字「側欄（五頁共用，預設收起）」；app.py 的 _IA_NAV_KEY radio "
        "是它的落地）。⇒ 本原型畫的側欄清單 ＋ 待做佔位在規格裡沒有對應元件，"
        "是為了把客戶 2026-09-22 ①「做側欄式」畫出來而自創的形狀。",
    ),
    (
        "G2",
        "頁尾免責不是可 import 的常數 ⇒ 本檔只能放一份「有守衛的複本」。",
        "實測：該字串是 app.py 的 _render_footer() 函式體內的 inline literal，"
        "⛔ 沒有任何可 import 的名字；而 app.py 是 L6 且 module-level import streamlit，"
        "本產生器（docs 工具）⛔ 不得 import 它。⇒ 本輪作法：複本 ＋ 產生時讀 app.py "
        "原始文字逐字比對，不符就炸、⛔ 不產出 HTML。"
        "真正的解是把它抽成 L0 常數（例如 shared/compliance_copy.py）讓兩邊都 import，"
        "但那要動 app.py ⇒ ⛔ 不在本輪授權範圍，登記為待辦。",
    ),
    (
        "G3",
        "資料時點列拿不到真時間 ⇒ 本頁只畫示意殼。",
        "實測：L3 canonical 契約 get_macro_state() 只有 9 個 key、沒有 as_of／timestamp；"
        "src/ui_v2/page_today.py 因此把 chrome.asof 放進 WITHDRAWN_BLOCKS"
        "（逐字「已撤回、不是待補」），src/ui/views/page_today.py 的 AS_OF_NOT_IN_CONTRACT "
        "逐字「寧可什麼都不寫，也不編一個時間出來」。"
        "⇒ 要顯示真實時點，得先擴充 L3 契約；在那之前本列只能是形狀示意。",
    ),
    (
        "G4",
        "chrome.footer 在新契約層 code 端 0 命中 ⇒ 頁尾免責由 L6 統一出，⛔ 不是頁面自己畫。",
        "實測：grep -rn chrome.footer src/ 為 0 命中（src/ui_v2/ 沒有頁尾這個 block，"
        "page_today.LAYERS 的 n0 只有 today.statusbar）；命中全落在 docs/。"
        "UI_PAGE_INSPECT.md 已由總管 2026-09-16 更正為「非缺陷」："
        "頁尾是 L6 app.py 統一出的跨頁 chrome（_render_footer() 於 st.stop() 前對每一個 "
        "IA 頁呼叫），頁面 0 命中是正確設計。⇒ 本靜態原型沒有 L6 可以依賴，只能自己畫一份 "
        "—— 這是原型與 Streamlit 實作的結構差異，⛔ 不得被讀成「頁面應該自己畫頁尾」"
        "（app.py 註解逐字已點名「複製第二份 ＝ 兩邊會漂移」）。",
    ),
    (
        "G5",
        "★-08（側欄預設展開還是收起）✅ 已決 —— 客戶 2026-09-22 拍板「側欄預設收起」；"
        "本原型現已對齊（三個斷點一律收起，只能手動展開）。",
        "現況：S2-UI_SPEC.md 7.2（★-08）已於 2026-09-22 由客戶拍板定為「側欄預設收起」，"
        "狀態自「未決／阻斷」改為「已決」（commit 6035262）。該節同時點名本原型的執行層"
        "不一致：JS 的 syncOpen()（nav.open = mq.matches、TABLET_MIN = 641）"
        "在 ≥641px 會自動展開 ⇒ 標記層收起、執行層在桌機不收起，並要求原型擁有組回頭對齊。"
        "客戶同日對本原型的裁示逐字：「【拍板：桌機自動展開，修掉】理由：規格說收起、"
        "畫面卻展開，就是規格與實作打架。」⇒ 本輪已移除產生器裡「依斷點把 nav.open 設為 true」"
        "的整段邏輯（syncOpen 的定義、載入時的呼叫、以及 matchMedia 的 change 監聽）；"
        "標記層本來就⛔ 不帶 open ⇒ 兩層自本日起給出同一個答案。"
        "⚠️ 唯一保留的斷點判斷是「選完頁之後在手機寬度把側欄收起（nav.open = false）」，"
        "它只關⛔ 不開。"
        "⚠️ ★-15（引導入口放哪裡）⛔ 不受本條影響，而且它自己也已經有答案了："
        "✅ 已決（客戶 2026-09-22 拍板）：(B) 側欄常駐一條入口、不自動展開；"
        "客戶理由逐字「與『側欄預設收起』一致」。"
        "⚠️ 已決的是「入口放哪裡」這道題，⛔ 不是「現在就去做那條入口」—— "
        "真的做那條側欄入口屬另案，本原型本輪⛔ 沒有新增任何引導入口。"
        "／／以下為 2026-09-22 稍早的舊句，有意識的政策變更、⛔ 不是漏刪，"
        "日期 2026-09-22、決策者：客戶，加刪除線保留："
        "~~S2-UI_SPEC.md 7.2 逐字「★-08 已於 2026-09-22 單獨解除；"
        "★-15 仍未決 · 阻斷，等客戶裁示」。~~"
        "／／兩邊理由並陳：舊句在它寫下的那一刻是對的（客戶當時只拍了 ★-08，"
        "★-08 與 ★-15 確實是分兩次問、客戶也確實分兩次答）；"
        "被權衡掉的⛔ 不是它的推理，是它的前提（「客戶尚未回答 ★-15」）。"
        "⚠️ 據實記錄、⛔ 不粉飾 —— 線框檔 docs/v2/wireframe/wf_global.js 的 ★-08／★-15 "
        "grade 由另一組負責，⛔ 不在本輪授權內，本輪⛔ 一個字都沒有動它。"
        "🔴 本檔因此**兩個方向都不宣稱**：⛔ 不寫「線框已同步」，⛔ 也不寫「線框尚未同步」"
        "—— 要知道它現在是什麼值，請**現場開那個檔查**，⛔ 不要引用本行"
        "（CLAUDE.md §8.2.A.0 規則 4：會漂移的量測值一律標日期或不寫；"
        "本行選擇不寫，因為它在本檔產生的同一天就被另一組動過，"
        "寫死任一個值都會在下一次重產時變成假話）。"
        "／／以下為 2026-09-22 之前的舊文字，有意識的政策變更、⛔ 不是漏刪，加刪除線保留："
        "~~側欄預設展開還是收起 ⇒ ★-08 規格上仍是未決，本原型的斷點行為是原型自創。"
        "實測：S2-UI_SPEC.md 7.2（★-08）於 2026-09-15 由來歷更正組把結論改標「未決」"
        "（原本引為「客戶已逐字回覆」的那句，實為 warroom_draft.html 決策卡上"
        "一顆未被按下的選項按鈕標籤）；wf_global.js 的 ★-08 grade 已同步改標「阻斷」，"
        "並與 ★-15 互指、要求一起問客戶。⇒ 本原型採「640 以下收起、641 以上展開」，"
        "是為了滿足客戶 2026-09-14「狀態列、時點列、分頁列不得吃掉首屏」而做的原型決定，"
        "⛔ 不是 ★-08 的答案，⛔ 不得被引用為已拍板。~~"
        "／／兩邊理由並陳：舊做法的理由在它寫下當天是合理的（桌機橫向空間大、展開較好用、"
        "少一次點擊，且手機那半確實滿足了首屏那條）；被權衡掉的原因是客戶原話"
        "「規格說收起、畫面卻展開，就是規格與實作打架」。",
    ),
)


def shell_css() -> str:
    """跨頁 chrome（側欄導覽／時點列／待做佔位／頁尾免責）的樣式。

    ⚠️ 與 `chrome_css()` 同一個紀律：**⛔ 不寫任何色碼、⛔ 不寫任何 px 字面值**，
       每一個數字都從 `components.*` / `page_today.*` 取回來（出處逐條寫在 CSS 註解裡）。
       class 一律 `.pv-` 前綴 —— `markup.page_css()` 產的 37 個 class
       （`blk*` / `grd*` / `lyr*` / `bdg*` / `sb-b*` / `g-*` / `lg-*`）**一個都不含 `pv-`**，
       ⇒ 零撞名（本檔 `main()` 末段另有機器比對，⛔ 不靠這句話）。
    """
    panel = components.PANEL
    base = components.CARD_BASE
    t1 = components.CARD_TIERS["t1"]
    t3 = components.CARD_TIERS["t3"]
    t4 = components.CARD_TIERS["t4"]
    nav_btn = components.BUTTONS["secondary_evidence"]
    tiny = components.BUTTONS["text"]
    disclosure = page_today.HOLDINGS_EQUAL_WEIGHT_DISCLOSURE
    tablet_min = components.BREAKPOINTS["tablet_min_px"]

    rules = [
        "/* ── hidden：分頁切換靠它，⛔ 兩個頁容器都不自訂 display，讓 UA 的 [hidden] 生效 ── */",
        "[hidden]{display:none}",

        "/* ══ 跨頁 chrome ①：五頁切換（側欄式）══════════════════════════════ */",
        "/*    ⛔ 刻意不做頂部分頁列：理由見本檔 NAV_WHY_SIDEBAR ＋ HTML 內的可見文案。 */",
        "/*    版面：≥tablet_min 兩欄（側欄 min-content ＋ 內容 1fr）；≤mobile_max 單欄。 */",
        "/*    ⭐ 側欄欄寬刻意用 min-content 而非固定寬：本檔⛔ 不寫 px 字面值，  */",
        "/*       寬度由最長的那個頁名（white-space:nowrap）自己撐出來。          */",
        ".pv-shell{margin-top:var(--sp-6)}",
        "/*    面板外觀取 components.PANEL 全欄 */",
        f".pv-nav{{background:{paint(panel['background'])};"
        f"border-width:{px(panel['border_width_px'])};"
        f"border-style:{panel['border_style']};"
        f"border-color:{paint(panel['border_color'])};"
        f"border-radius:{px(panel['radius_px'])};"
        f"{pad(panel['padding_px'])}}}",  # type: ignore[arg-type]
        "/*    summary ＝ 唯一的展開控制，**任何斷點都看得見**： */",
        "/*    ⛔ 不在桌機把它藏起來 —— 藏了之後若 JS 沒跑，側欄就永遠打不開。 */",
        "/*    ⚠️ 2026-09-22 桌機自動展開移除後，它是**唯一**能把側欄打開的東西 */",
        "/*       （★-08 已決：預設收起）⇒ 這條「任何斷點都看得見」更不能省。 */",
        f".pv-nav-summary{{cursor:pointer;color:var(--ink);white-space:nowrap;"
        f"font-size:{px(t3['title_px'])};font-weight:{t3['title_weight']};"
        f"min-height:{px(nav_btn['min_height_px'])};"
        "display:flex;align-items:center;gap:var(--sp-2)}",
        ".pv-nav-body{margin-top:var(--sp-3)}",
        ".pv-nav-list{list-style:none;margin:0;padding:0;"
        "display:flex;flex-direction:column;gap:var(--sp-2)}",
    ]
    rules += ["/*    項目：components.BUTTONS['secondary_evidence']（44x44 點擊區）逐欄展開 */"]
    rules += _button_rules(".pv-nav-item", nav_btn)
    rules += [
        ".pv-nav-item{width:100%;justify-content:flex-start;text-align:start;"
        "white-space:nowrap}",
        "/*    current：底色 + 框色 + 字重升到 t1 卡標，⛔ 不只靠顏色（另有 aria-current） */",
        f'.pv-nav-item[aria-current="page"]{{background:var(--panel-2);'
        f"border-color:var(--ochre-line);color:var(--ink);"
        f"font-weight:{t1['title_weight']}}}",
        f".pv-nav-why{{margin-top:var(--sp-3);color:var(--ink-3);"
        f"font-size:{px(tiny['font_px'])}}}",

        "/* ══ 跨頁 chrome ②：資料時點揭露列 ═══════════════════════════════ */",
        "/*    位置：S2-UI_SPEC.md 7.1 逐字「緊接其下，頁面標題下方第一行，葉外」。 */",
        "/*    左側 amber 虛線 ＝ 一眼看出「這是示意殼」（虛線樣式取 t4，全站唯一 dashed 的一階）*/",
        f".pv-asof{{margin-top:var(--sp-4);padding-inline-start:var(--sp-4);"
        f"border-inline-start-width:{px(t1['border_width_px'])};"
        f"border-inline-start-style:{t4['border_style']};"
        "border-inline-start-color:var(--sig-amber)}",
        f".pv-asof-line{{color:var(--ink);font-size:{px(t3['title_px'])};"
        f"font-weight:{t3['title_weight']}}}",
        "/*    摺疊器：收起時只佔一行 —— 客戶 2026-09-14「時點列不得吃掉首屏」 */",
        f".pv-asof-sum{{cursor:pointer;margin-top:var(--sp-2);"
        f"color:{paint(disclosure['color'])};font-size:{px(disclosure['font_px'])}}}",
        ".pv-fmt{list-style:none;margin-top:var(--sp-3);padding:0;"
        "display:flex;flex-direction:column;gap:var(--sp-1)}",
        f".pv-fmt li{{color:{paint(disclosure['color'])};"
        f"font-size:{px(disclosure['font_px'])}}}",

        "/* ══ 跨頁 chrome ③：其餘四頁的「此頁待做」佔位 ════════════════════ */",
        "/*    框線取 t4 的 dashed ＝ 與第四層同一種「這裡還不是實心內容」的語彙 */",
        ".pv-todo{margin-top:var(--sp-7)}",
        f".pv-todo-card{{background:{paint(base['background'])};"
        f"border-width:{px(t4['border_width_px'])};"
        f"border-style:{t4['border_style']};"
        f"border-color:{paint(t4['border_color'])};"
        f"border-radius:{px(base['radius_px'])};"
        f"{pad(panel['padding_px'])}}}",  # type: ignore[arg-type]
        f".pv-todo-title{{color:var(--ink);font-size:{px(t1['title_px'])};"
        f"font-weight:{t1['title_weight']}}}",
        ".pv-todo-back{margin-top:var(--sp-4)}",

        "/* ══ 跨頁 chrome ④：頁尾免責（逐字 SSOT ＝ app.py::_render_footer）════ */",
        f".pv-legal{{margin-top:var(--sp-6);padding-top:var(--sp-4);text-align:center;"
        f"border-top-width:{px(base['border_width_px'])};border-top-style:solid;"
        f"border-top-color:var(--grid);color:{paint(disclosure['color'])};"
        f"font-size:{px(disclosure['font_px'])}}}",

        "/* ══ 斷點：兩欄版面只在 >= BREAKPOINTS['tablet_min_px'] 生效 ═════════ */",
        "/*    ⚠️ 斷點只換**版面**（單欄／兩欄），⛔ 不換側欄的開合：      */",
        "/*    details 在**每一個斷點**都預設收起（★-08 已決，客戶 2026-09-22 拍板）， */",
        "/*    ⇒ 手機（<= mobile_max_px）是單欄 ＋ details 收起，桌機同樣收起， */",
        "/*      客戶 2026-09-14「狀態列、時點列、分頁列不得吃掉首屏」在所有斷點都成立。 */",
        f"@media (min-width:{px(tablet_min)}){{"
        ".pv-shell{display:grid;grid-template-columns:min-content minmax(0,1fr);"
        "gap:var(--sp-6);align-items:start}"
        ".pv-nav{position:sticky;top:var(--sp-5)}"
        "}",
    ]
    return "\n".join(rules)


# ══════════════════════════════════════════════════════════════════
# 3. 示意內容
#
# 🔴 客戶指定「示意數字，且必須標明示意」⇒ 每一張**畫得出數字**的卡都掛一列
#    `("資料來源", "⚠️ 示意值 · 未接線")`，頁面頂部另有橫幅。
# 🔴 卡標題規則：**規格給了名字的用規格的名字，沒給的直接用 block key**
#    （沿用 `render.unwired_view_model` 的做法：⛔ 不發明一組沒有出處的中文標題）。
# ══════════════════════════════════════════════════════════════════
DEMO = "⚠️ 示意值 · 未接線"

_LAYER_LABEL = {   # UI_PAGE_TODAY.md ① 四層結構表第一欄逐字
    0: "葉外 chrome",
    1: "第一層 結論燈",
    2: "第二層 核心卡",
    3: "第三層 操作列",
    4: "第四層 展開佐證",
}

_LAYER_NOTE = {
    0: "三張卡都確實傳了值進去；「總經」是 #4 門檻已失準 ⇒ 觀測照出、判決留白，"
       "「Sheet」是 #7 缺漏 ⇒ 值與判決都留白。畫面上看不到的那些值，"
       "是 page_today.card_value_text() / card_level_text() 依狀態擦掉的，不是漏畫。",
    1: "t1 是四階裡唯一 2px 框線、內距最大的一階（手機 ≤640 另有一組覆寫內距，"
       "四階中也只有 t1 有）。",
    2: "三個 block 由 layer_html(layer=2) 包在同一個 .lyr / .lg-3-2-1 裡 ⇒ "
       "≥881 三欄、641–880 兩欄、≤640 單欄（拉視窗可驗）。"
       "✅ today.summary 的 BLOCK_COLS 現為 1/1/1（客戶 2026-09-22 裁示 B：三張獨立卡、"
       "卡內⛔ 不巢狀網格）⇒ 卡內網格三段都只剩一欄（.g-1-1-1），三張卡各佔一列垂直堆疊；"
       "桌機上不再有「三欄摘要被壓在 1/3 寬內」這回事 —— 巢狀多欄網格已經不存在。"
       "U-1 已決，⛔ 不再是 UI_PAGE_TODAY.md ③ 登記的「未判定」矛盾"
       "（該段已結案搬入「U-1 已決」；⚠️ 裁示只及 today.summary，"
       "同一個 cols 語意問題在 today.statusbar 上的反例已拆為 U-2，仍未判定）。"
       "⚠️ 但 .g-3-2-1 還在用：today.detail（第四層）的 BLOCK_COLS 仍是 3/2/1。"
       "本原型照現行程式碼原樣渲染，⛔ 不代為裁決任何還沒被裁示的項目。",
    # ── 主 CTA 的範圍詞：2026-09-22 由「全站唯一」改為「每頁首屏唯一」──────────
    # ⚠️ **有意識的政策變更，⛔ 不是漏刪；日期 2026-09-22；決策者：客戶。**
    # 客戶拍板逐字：「【拍板 2：主 CTA】不是「全站唯一」，是「**每頁首屏唯一**」。」
    # **舊句加刪除線保留（⛔ 不是漏刪）**：
    #   ~~"主 CTA 全站唯一一顆，標籤逐字取 page_today.MAIN_CTA['label']；"~~
    # **兩邊理由並陳**：
    # ① **舊說法在它寫下的當天是對的（⛔ 不是寫錯）**：本原型當時只有「🚦 今天」一頁，
    #    「全站唯一」與「每頁首屏唯一」在**只有一頁**時**外延完全相同** ——
    #    那時兩種寫法指到同一顆鈕，看不出差別，選較強的那個寫法並不造成任何錯誤。
    # ② **被權衡掉的原因**：五頁逐頁落地之後，「🔍 找標的」有**自己的**主 CTA
    #    「🎯 開始選股」（線框 `mainCTA.label` 逐字）⇒「全站唯一」變成一句**可以被
    #    當場否證的假話**，而畫面上寫假話正是 CLAUDE.md §1 要防的那一型。
    #    範圍詞從「站」收到「頁的首屏」之後，**規則本身沒有被放寬** ——
    #    每一頁仍然只准有一顆、且必須在預設葉（S2-UI_SPEC.md 的 L0-3）。
    # ⚠️ **本輪只改得到產生器裡的這 2 處**（本處 ＋ today.actions 卡的 facts）。
    #    `src/ui_v2/page_today.py`（2 處）與 `docs/v2/spec/UI_COMPONENTS.md` §3
    #    **不在本組的檔案邊界內**，由另一組同步 ⇒ ⛔ 不得宣稱「已全部同步」。
    #    四個落點的完整登記見 `FIND_SPEC_GAPS` 的 F1。
    3: "主 CTA 每頁首屏唯一一顆，標籤逐字取 page_today.MAIN_CTA['label']；"
       "可按性取 main_cta_state()。⚠️ 本頁是靜態原型，按下去不會有任何事發生。"
       "⚠️ 範圍詞 2026-09-22 由「全站唯一」改為「每頁首屏唯一」（客戶拍板）——"
       "「🔍 找標的」頁有自己的主 CTA「🎯 開始選股」，"
       "「全站唯一」自那一頁落地起就是一句可被否證的假話。",
    4: "t4 是四階裡唯一 dashed 的一階。today.detail 放了 4 張卡、而它的網格是 3 欄 ⇒ "
       "第 4 張換行排下一列（cols ＝ 一列幾格，⛔ 不是加欄）。"
       "這 4 張卡的標題直接取自 components.BADGES 的 name —— "
       "規格沒有給 today.detail 的逐卡名稱，⛔ 不發明。",
}


def _fact_demo() -> tuple[tuple[str, str], ...]:
    return (("資料來源", DEMO),)


def build_cards() -> dict[str, list[dict]]:
    """每個 block 的卡片內容（state 與 badge_n 一律用 resolve_badge 對齊，⛔ 不各寫各的）。"""
    rb = page_today.resolve_badge

    holdings_demo = {
        "n_total": "12",
        "n_classified": "10",
        "n_unclassified": "2",
        "n_industries": "6",
        "coverage_pct": "83.3%",
        "top1_pct": "30.0%",
        "top3_pct": "70.0%",
        "hhi": "0.18",
        "n_eff": "5.6",
    }
    # 白名單自檢：⛔ 不得混進 pnl / position_pct 這類本卡算不出來的欄位。
    assert page_today.unknown_holdings_fields(holdings_demo) == ()
    holdings_facts = [
        (page_today.HOLDINGS_TOP1_LABEL if f == "top1_pct" else f, holdings_demo[f])
        for f in page_today.HOLDINGS_DISPLAY_FIELDS
    ]
    holdings_facts.append(("資料來源", DEMO))

    # 第二層摘要的**三張獨立卡**（客戶 2026-09-22 裁示 B；⛔ 不再是「卡內三欄」）：
    # 名稱／接線與否／徽章全部取自 page_today.SUMMARY_COLUMNS。
    summary_demo = {"位階": ("4 / 5", "🟢 擴張"), "風險": ("2 / 5", "🟡 偏高")}
    summary_cards = []
    for col in page_today.SUMMARY_COLUMNS:
        name = str(col["name"])
        if col["wired"]:
            value, level = summary_demo[name]
            summary_cards.append({
                "state": "live", "title": name, "value": value, "level": level,
                "badge_n": rb(state="live"), "facts": _fact_demo(),
            })
        else:
            # 未接線態依規格走 #5，⛔ 不得畫成 #1；此處順手驗證兩個來源一致。
            assert col["badge"] == rb(state="unwired"), col
            summary_cards.append({
                "state": "unwired", "title": name, "value": None, "level": None,
                "badge_n": rb(state="unwired"), "facts": (),
            })

    detail_cards = []
    for n, state, kwargs in (
        (2, "loading", {}),
        (6, "failed", {}),
        (8, "na", {"miss_reason": page_today.MISS_NOT_APPLICABLE}),
        (9, "partial", {"numerator": 7, "denominator": 9}),
    ):
        assert rb(state=state, **kwargs) == n, (state, kwargs, n)
        spec = components.badge(n)
        detail_cards.append({
            "state": state, "title": spec["name"],
            "value": "7 / 9" if state == "partial" else "99.9",
            "level": "🟡 部分計入" if state == "partial" else "🟢 正常",
            "badge_n": n,
            "facts": (("徽章", f"#{n} {spec['text']}"),
                      ("資料來源", DEMO)),
        })

    return {
        # UI_PAGE_TODAY.md ①：today.statusbar ＝ 3 張狀態卡（交易日／總經／Sheet）
        "today.statusbar": [
            {"state": "live", "title": "交易日", "value": None, "level": None,
             "badge_n": rb(state="live"),
             "facts": (("最近交易日", "2026-09-18"), ("資料來源", DEMO))},
            {"state": "degraded", "title": "總經", "value": "58.0", "level": "🟡 中性",
             "badge_n": rb(state="degraded"),
             "facts": (("門檻校準", "已過期"), ("行為", "觀測照出、判決留白"),
                       ("資料來源", DEMO))},
            {"state": "missing", "title": "Sheet", "value": "12", "level": "🟢 正常",
             "badge_n": rb(state="missing"),
             "facts": (("狀態", "讀取失敗"), ("重試", "有用 ⇒ #7 缺漏 · 可重跑"),
                       ("資料來源", DEMO))},
        ],
        # 線框 name 逐字「① 結論燈」（UI_PAGE_TODAY.md ③）
        "today.verdict": [
            {"state": "live", "title": "① 結論燈", "value": "62",
             "level": "🟢 偏多 · 可分批出手",
             "badge_n": rb(state="live"),
             "facts": (("觀測", "綜合 62 / 100"), ("信心", "中"), ("資料來源", DEMO))},
        ],
        "today.summary": summary_cards,
        # UI_PAGE_TODAY.md ①：today.key_banner ＝ 今日關鍵橫幅
        "today.key_banner": [
            {"state": "live", "title": "今日關鍵橫幅", "value": "-1.8%",
             "level": "🟠 外資連 3 賣", "badge_n": rb(state="live"),
             "facts": (("加權指數", "22,481"), ("資料來源", DEMO))},
        ],
        # UI_PAGE_TODAY.md ①：today.holdings ＝ 持倉健檢
        "today.holdings": [
            {"state": "live", "title": "持倉健檢", "value": "83.3%",
             "level": "🟢 已分類 10 / 12",
             "badge_n": page_today.holdings_badge(n_classified=10),
             "facts": tuple(holdings_facts)},
        ],
        "today.actions": [
            {"state": "live", "title": "today.actions", "value": None, "level": None,
             "badge_n": rb(state="live"),
             # ⚠️ 2026-09-22 客戶拍板：範圍詞由「全站唯一」→「每頁首屏唯一」。
             #    **有意識的政策變更，⛔ 不是漏刪**；舊值加刪除線保留：
             #    ~~("主 CTA", "全站唯一一顆")~~
             #    兩邊理由並陳與四個落點見 `_LAYER_NOTE[3]` 上方註解 ＋ `FIND_SPEC_GAPS` F1。
             "facts": (("主 CTA", "每頁首屏唯一一顆"),
                       ("停用條件", page_today.MISS_CONTRACT_DRIFT))},
        ],
        "today.warroom": [
            {"state": "idle", "title": "today.warroom", "value": "41", "level": "🟢 正常",
             "badge_n": rb(state="idle"),
             "facts": (("狀態", "尚未載入 ⇒ 值與判決一律留白"),)},
        ],
        "today.detail": detail_cards,
    }


# ══════════════════════════════════════════════════════════════════
# 4. 組頁
# ══════════════════════════════════════════════════════════════════
def _tier_caption(tier: str) -> str:
    spec = components.CARD_TIERS[tier]
    vertical, horizontal = spec["padding_px"]          # type: ignore[misc]
    mobile = spec["padding_mobile_px"]
    bits = [
        f"內距 {px(vertical)} {px(horizontal)}",
        f"框線 {px(spec['border_width_px'])} {spec['border_style']}",
        f"卡標 {px(spec['title_px'])}/{spec['title_weight']}",
        f"徽章 .sb-{spec['badge_size']}",
        f"卡距 {px(spec['margin_top_px'])}",
    ]
    if mobile is not None:
        bits.append(f"手機內距 {px(mobile[0])} {px(mobile[1])}")
    return "、".join(bits)


def build_body() -> str:
    cards_by_block = build_cards()
    cta = page_today.main_cta_state()
    parts: list[str] = []

    for layer_spec in page_today.LAYERS:
        layer = int(layer_spec["layer"])           # type: ignore[arg-type]
        tier = str(layer_spec["tier"])
        blocks = tuple(layer_spec["blocks"])       # type: ignore[arg-type]
        label = _LAYER_LABEL[layer]
        parts.append('<section class="pv-layer">')
        parts.append(
            f'<div class="pv-layer-label">{esc(label)} · 密度 {esc(tier)} · '
            f'block：{esc("、".join(blocks))}</div>'
        )
        parts.append(
            f'<p class="pv-meta">components.CARD_TIERS[<span class="pv-mono">'
            f'{esc(tier)}</span>]：{esc(_tier_caption(tier))}</p>'
        )
        if layer in _LAYER_NOTE:
            parts.append(f'<p class="pv-meta">{esc(_LAYER_NOTE[layer])}</p>')

        grids = [
            markup.grid_html(
                block=block,
                cards=[markup.card_html(block=block, **card)
                       for card in cards_by_block[block]]
                + ([f'<p class="pv-disclosure">'
                    f'{esc(page_today.HOLDINGS_EQUAL_WEIGHT_DISCLOSURE["text"])}</p>']
                   if block == "today.holdings" else []),
            )
            for block in blocks
        ]
        if layer in page_today.LAYER_GRID_COLS:
            parts.append(markup.layer_html(layer=layer, block_htmls=grids))
        else:
            parts.extend(grids)

        if layer_spec["has_main_cta"]:
            parts.append('<div class="pv-cta">')
            parts.append(
                f'<button type="button" class="pv-btn-primary"'
                f'{"" if cta["enabled"] else " disabled"}>'
                f'{esc(page_today.MAIN_CTA["label"])}</button>'
            )
            note = cta.get("note")
            parts.append(
                '<span class="pv-meta">'
                + esc(note if note else "靜態原型：這顆鈕不會觸發任何事。")
                + '</span>'
            )
            parts.append('</div>')
        parts.append('</section>')

    # 附錄：徽章總覽（元件展示，⛔ 不是「🚦 今天」頁的版面規格）
    parts.append('<section class="pv-layer">')
    parts.append('<div class="pv-layer-label">附錄 · 徽章總覽（元件展示，非本頁版面）</div>')
    parts.append(
        '<p class="pv-meta">'
        + esc(
            f"components.BADGES 共 {len(components.BADGES)} 種；本頁畫 "
            f"{sorted(page_today.BADGES_ON_PAGE)}，"
            f"#{sorted(page_today.BADGES_NOT_ON_PAGE)[0]} 依 page_today.BADGES_NOT_ON_PAGE "
            "刻意不畫（⛔ 但不得因此把它併進別的徽章）。"
            "四個尺寸依所在卡層 t1→b1 … t4→b4；每一顆都是圖示＋文字，⛔ 不只靠顏色。"
        )
        + '</p>'
    )
    for size in components.SBADGE_SIZES:
        parts.append(f'<p class="pv-meta">.sb-{esc(size)}</p>')
        parts.append('<div class="pv-badges">')
        parts.extend(markup.badge_html(n, size=size)
                     for n in sorted(page_today.BADGES_ON_PAGE))
        parts.append('</div>')
    parts.append('</section>')
    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════
# 4.6 「📖 憑什麼」頁 —— 版面定義寫在產生器（客戶 2026-09-22 拍板「選項 1」）
#
# 🔴 **本節就是「選項 1」的落地。** 客戶 2026-09-22 拍板逐字：
#    「1. 走選項 1：版面定義寫在產生器，畫面上就地揭露缺口」
#    「2.「憑什麼」頁照規格 **6 層**，⛔ 不是四層（客戶先前記的四層是簡化說法）」
#    「3. `badge_html(10)` 不報錯 → 登記為待修（**本輪不動**）」
#    ⇒ `WHY_LAYOUT` 是本頁版面的**唯一定義**；它**不在** `src/ui_v2/` 契約層、
#      **沒有** `tests/ui_v2/` 的測試守護。**這件事必須畫在畫面上**（`WHY_GAP_W1`）。
#
# 🔴 **⛔ 不發明 block、⛔ 不發明 cols。** 22 筆每一筆都在 `src` 欄標出處
#    （規格**章節名** ＋ 線框 **block key**；依 CLAUDE.md §8.2.A.0 規則 1 **⛔ 不寫行號**）。
#    規格查不到的一律**登記為洞**（`WHY_SPEC_GAPS`），⛔ 不填一個看起來合理的值（§1）。
#
# 📌 **兩個來源**（本組各自 import／node 實跑過，⛔ 非讀他組轉述）：
#    · 規格 `docs/v2/spec/UI_PAGE_WHY.md`
#    · 線框 `docs/v2/wireframe/wf_page_why.js` 的 `window.WF_PAGES[0]`（`id:"why"`）
#      —— block 巢在 `layers[].blocks[]`，本組 node 實測 **6 層 22 block 3 葉**，
#      `cols` 全集只有 `1/1/1`（14 塊）與 `3/2/1`（8 塊）兩種。
# ══════════════════════════════════════════════════════════════════

#: R4 就地揭露的**那一句**（客戶明示⛔ 不得省）。畫在「📖 憑什麼」頁的最上方。
WHY_LAYOUT_DISCLOSURE = (
    "⚠️ 此頁版面定義在產生器內，未進 src/ui_v2/ 契約層、無 tests/ui_v2/ 測試守護。"
)

#: 上面那句的**後果**（⛔ 不是免責套話，是可查證的差別）。
WHY_LAYOUT_DISCLOSURE_WHY = (
    "差別在哪：「🚦 今天」頁的版面（哪個 block 在第幾層、幾欄、哪一階密度）住在 "
    "src/ui_v2/page_today.py，改壞了 tests/ui_v2/ 會紅燈；本頁的同一組資料住在 "
    "docs/v2/prototype/gen_today_v2.py 的 WHY_LAYOUT，改壞了⛔ 沒有任何測試會攔。"
    "⇒ 本頁的版面只有「跟規格與線框對照」這一種查法，⛔ 沒有機器守衛。"
    "本產生器在結尾自己跑了一輪對照（22 個 block key／層／欄數 class／密度 class 逐一比對），"
    "但那是**同一組人寫的自驗**，⛔ 不等於獨立測試。"
)

#: 本頁的**形狀**（本組自己量的，⛔ 不引用他組轉述）。
WHY_PAGE_SHAPE_NOTE = (
    "本頁形狀（本組自行實測，⛔ 非引用轉述）：規格 docs/v2/spec/UI_PAGE_WHY.md ＋ 線框 "
    "docs/v2/wireframe/wf_page_why.js 的 window.WF_PAGES[0]（id 為 why）—— "
    "node 解析結果：6 層、22 block、3 葉（l1 教學／l2 資料體檢／l3 AI 問答，五頁唯一的三葉頁）；"
    "22 塊的 cols 全集只有兩種，1/1/1 共 14 塊、3/2/1 共 8 塊。"
    "線框 mainCTA 欄位存在且值為 null ⇒ 本頁是五頁唯一沒有主 CTA 的一頁，⛔ 不得為它發明一顆按鈕。"
)

#: 六層的層標 —— `UI_PAGE_WHY.md` ② 六層結構表**第一欄逐字**（⛔ 去掉 markdown 粗體記號）。
WHY_LAYER_LABEL: Mapping[int, str] = {
    0: "葉外 chrome",
    1: "第一層 四張說明卡",
    2: "第二層 逐盞門檻表",
    3: "第三層 資料體檢 · 使用者版",
    4: "第四層 資料體檢 · 工程師版",
    5: "葉3",
}

#: 每層所屬的葉 —— 線框 `layers[].blocks[].leaf`（本組 node 實測，同層內全同值）。
#: `None` ＝ 線框 `leaf: null`（畫在分頁列之上、三葉共用）。
WHY_LAYER_LEAF: Mapping[int, str | None] = {
    0: None, 1: "l1", 2: "l1", 3: "l2", 4: "l2", 5: "l3",
}

#: 三葉的名字 —— 線框 `leaves[].id`／`UI_PAGE_WHY.md` ① 逐字（`l1` 教學／`l2` 資料體檢／`l3` AI 問答）。
WHY_LEAF_NAME: Mapping[str, str] = {
    "l1": "教學", "l2": "資料體檢", "l3": "AI 問答",
}

#: `n5` 的卡密度。**⛔ 非本檔發明**：`UI_PAGE_WHY.md` ② 表 `葉3 / n5` 列逐字
#: 「t2（**沿用 `UI_PAGE_FIND` 對 `n5` 的新訂**：超出 `n1~n4` 自動對映時取「核心卡」，⛔ 非本組發明）」。
#: 🔴 契約層 `components.tier_for_layer()` 只認 0 與 1~4（實測 `tier_for_layer(5)` → `ValueError`）
#:    ⇒ 這一格是**規格有、契約層沒有**的地方，已登記為 `WHY_GAP_W2`。
WHY_N5_TIER = "t2"

#: 本頁**會畫**的徽章 —— `UI_PAGE_WHY.md` ④ 末句逐字：
#: 「⇒ **會出現在畫面上的是 6 態：#1／#3／#4／#5／#6／#7**；#2 未落地、#8／#9 待接線、
#:   **#10 有對象但尚未徽章化**。」
#: ⇒ 其餘四顆一律**不畫**，並由下面的代理物件把「不小心畫了」變成 `ValueError`（fail loud）。
WHY_BADGES_ON_PAGE: frozenset[int] = frozenset({1, 3, 4, 5, 6, 7})
WHY_BADGES_NOT_ON_PAGE: frozenset[int] = frozenset(
    int(b["n"]) for b in components.BADGES if int(b["n"]) not in WHY_BADGES_ON_PAGE
)

#: 本頁的**版面定義**（六層 22 block）。`cols` ＝ `(桌機, 平板, 手機)`。
#: 🔴 每一筆的 `src` 是**出處**，⛔ 不是註解：規格章節名 ＋ 線框 block key。
WHY_LAYOUT: tuple[Mapping[str, object], ...] = (
    # ── n0 葉外｜全域 chrome（線框 `leaf: null`，三塊全 1/1/1）────────────────
    {"block": "why.statusbar", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ① 差異 3 ＋ ② 六層結構表「葉外 chrome」列｜線框 why.statusbar"},
    {"block": "why.asof", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ① 差異 3 ＋ ② 六層結構表「葉外 chrome」列｜線框 why.asof"},
    {"block": "why.footer", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ① 差異 3 ＋ ② 六層結構表「葉外 chrome」列｜線框 why.footer"},
    # ── n1 葉1 教學 · 上半｜四張說明卡（② 表逐字「四塊全 3/2/1」）──────────────
    {"block": "why.edu.lights", "n": 1, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第一層 四張說明卡」列｜線框 why.edu.lights"},
    {"block": "why.edu.health6", "n": 1, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第一層 四張說明卡」列｜線框 why.edu.health6"},
    {"block": "why.edu.scales", "n": 1, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第一層 四張說明卡」列｜線框 why.edu.scales"},
    {"block": "why.edu.legacy", "n": 1, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第一層 四張說明卡」列｜線框 why.edu.legacy"},
    # ── n2 葉1 教學 · 下半｜逐盞門檻對照表（② 表逐字「全 1/1/1」；5 塊⛔ 不是 3 塊）──
    #    ⚠️ ① 差異 2 逐字：層標寫「三塊」指的是**三張表**，「5 塊」指的是**五個線框區塊**，
    #       兩個數字各自都對；⑤-d／⑤-e 是「表格**下方**逐列」的說明區，⛔ 不是第 4、5 張表。
    {"block": "why.edu.table.macro", "n": 2, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第二層 逐盞門檻表」列｜線框 why.edu.table.macro"},
    {"block": "why.edu.table.reference", "n": 2, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第二層 逐盞門檻表」列｜線框 why.edu.table.reference"},
    {"block": "why.edu.table.hold", "n": 2, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第二層 逐盞門檻表」列｜線框 why.edu.table.hold"},
    {"block": "why.edu.table.caveat", "n": 2, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第二層 逐盞門檻表」列｜線框 why.edu.table.caveat"},
    {"block": "why.edu.table.nolevel", "n": 2, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第二層 逐盞門檻表」列｜線框 why.edu.table.nolevel"},
    # ── n3 葉2 資料體檢 · 使用者版（⭐ 常駐，⛔ 不藏在 gate 後面）────────────────
    {"block": "why.source.wall", "n": 3, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第三層 …使用者版」列（該列逐字標 3/2/1）｜線框 why.source.wall"},
    {"block": "why.source.named", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第三層 …使用者版」列｜線框 why.source.named"},
    {"block": "why.source.cache_semantics", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第三層 …使用者版」列｜線框 why.source.cache_semantics"},
    {"block": "why.source.unmeasured.finmind_quota", "n": 3, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第三層 …使用者版」列（該列逐字標 3/2/1）"
            "｜線框 why.source.unmeasured.finmind_quota"},
    {"block": "why.spec.flags", "n": 3, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第三層 …使用者版」列（該列逐字標 3/2/1）｜線框 why.spec.flags"},
    {"block": "why.source.coverage", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第三層 …使用者版」列｜線框 why.source.coverage"},
    # ── n4 葉2 資料體檢 · 工程師版（維持現行單一 gate；t4 是四階唯一 dashed）────────
    {"block": "why.engineer.gate", "n": 4, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第四層 …工程師版」列｜線框 why.engineer.gate"},
    {"block": "why.engineer.monitor", "n": 4, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第四層 …工程師版」列｜線框 why.engineer.monitor"},
    {"block": "why.engineer.panels", "n": 4, "cols": (3, 2, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「第四層 …工程師版」列（該列逐字標 3/2/1）｜線框 why.engineer.panels"},
    # ── n5 葉3 AI 問答（送出就是啟動）────────────────────────────────────────
    {"block": "why.qa", "n": 5, "cols": (1, 1, 1),
     "src": "UI_PAGE_WHY ② 六層結構表「葉3」列｜線框 why.qa"},
)

#: 由 `WHY_LAYOUT` **推導**（⛔ 不另手寫一份，否則就是第二個真相源 —— CLAUDE.md §2.1）。
WHY_BLOCK_COLS: Mapping[str, tuple[int, int, int]] = {
    str(rec["block"]): tuple(rec["cols"]) for rec in WHY_LAYOUT   # type: ignore[misc]
}
_WHY_BLOCK_LAYER: Mapping[str, int] = {
    str(rec["block"]): int(rec["n"]) for rec in WHY_LAYOUT        # type: ignore[arg-type]
}
WHY_LAYER_BLOCKS: Mapping[int, tuple[str, ...]] = {
    n: tuple(str(rec["block"]) for rec in WHY_LAYOUT if int(rec["n"]) == n)  # type: ignore[arg-type]
    for n in sorted({int(rec["n"]) for rec in WHY_LAYOUT})                   # type: ignore[arg-type]
}


def why_tier_for_layer(n: int) -> str:
    """層序 → 卡密度。

    · `n0~n4`：**一律走契約層** `components.tier_for_layer()`，⛔ 不在本檔手抄一份
      —— 那正是 `UI_COMPONENTS.md` §1「四層由 `layers[].n` **自動掛**，⛔ 非逐塊手選」
      的落地形式（本檔照抄一份就等於把「手選」搬回來了）。
    · `n5`：超出契約層的 `1~4` 自動對映（實測 `components.tier_for_layer(5)` → `ValueError`），
      取規格 ② 表 `葉3` 列的 `t2`。**⛔ 非本檔發明**，見 `WHY_N5_TIER` 的出處註。
    · 其餘層序 → `ValueError`（⛔ 不猜一階）。
    """
    if n == 5:
        return WHY_N5_TIER
    return components.tier_for_layer(n)


def why_tier_for_block(block_key: str) -> str:
    """block → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**（同 `page_today.tier_for_block`）。"""
    try:
        n = _WHY_BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return why_tier_for_layer(n)


# ── 代理：把 `markup.page_today` **暫時**換成本頁的版面契約 ──────────────────
#
# 🔴 **何以要代理（R2：作法要寫清楚理由）**
#    `markup.py` 的五個公開函式**全部**把版面查表寫死在 `page_today` 上
#    （本組實測，⛔ 非讀轉述）：
#      · `card_html(block='why.…')` → `KeyError: 未知的 block`（卡在 `page_today.tier_for_block`）
#      · `grid_html(block='why.…')` → `KeyError`（卡在 `page_today.BLOCK_COLS[block]`）
#      · `layer_html(layer=5)`      → `KeyError: 第 5 層沒有登記層級網格`
#      · `components.tier_for_layer(5)` → `ValueError: 只有 0 與 1~4`
#      · `badge_html(10)`           → **不報錯**，但 `.bdg-10` 不在 `page_css()` 的輸出裡
#        ⇒ 會畫出一顆**無配色的徽章**（§1 最危險的那一型：看起來成功、實際是假的）
#    ⇒ 想把「📖 憑什麼」畫出來，只有三條路：
#      (a) 新增 `src/ui_v2/page_why.py`  —— 客戶本輪⛔ 沒有選這條（選項 1 明說版面寫在產生器）；
#      (b) 在本檔**手抄**一份 `<div class="blk blk-t1">…` 的標記 —— **那是第二個真相源**：
#          `markup.card_html` 之後改了，本檔不會跟著改，而且**沒有人會發現**（CLAUDE.md §2.1）；
#      (c) **代理**：版面查表換成本頁的，**標記仍由 `markup` 的公開函式產出**。
#    ⇒ 選 (c)。它的產物與「真的有 `page_why.py`」時**逐字相同** —— 因為標記完全是
#      `markup.card_html` / `grid_html` 自己吐的，本檔一個角括號都沒有手打。
#
# ⛔ **三條紀律（缺一不可）**
#    ① **只在產「📖 憑什麼」頁的期間替換，產完一定還原** —— 「🚦 今天」頁仍走真正的
#       `page_today`（離場時 assert `markup.page_today is page_today`）。
#    ② **⛔ 不碰 `markup` 的私有符號**（`_root_rule` / `_px` / `_resolve_palette` …）。
#       `markup.page_today` 是**公開名字**（無底線）—— 本 repo 登記在案的違憲
#       `V-PICKER-PRIV-1` 就是跨層直取底線開頭的私有符號，⛔ 不重蹈。
#    ③ **⛔ 不在代理生效期間呼叫 `markup.page_css()`** —— `markup` 有四個 module-level
#       常數（`_BLOCK_COLS_USED` / `_LAYER_COLS_USED` / `_TIERS_ON_PAGE` /
#       `_TIERS_WITH_LAYER_GRID`）是 **import 當下**就依 `page_today` 算好的，
#       代理換不動它們；CSS 一律在代理**之外**產（`main()` 的順序已保證，另有 assert）。
def _markup_page_today_names() -> frozenset[str]:
    """AST 掃 `markup.py`：它到底讀了 `page_today` 的哪幾個名字。

    🔴 **⛔ 不用 grep、⛔ 不憑記憶**：`markup` 日後多讀一個名字，代理就少一塊；
    少的那一塊會以 `AttributeError` 炸在產生時，⛔ 不會靜默畫出半套版面（§1 Fail Loud）。
    """
    tree = ast.parse(pathlib.Path(markup.__file__).read_text(encoding="utf-8"))
    return frozenset(
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "page_today"
    )


#: 代理物件。**只提供 `markup` 真的會讀的那幾個名字**（由上面的 AST 掃描把關）。
#: · `BLOCK_COLS` / `tier_for_block` / `BADGES_*`：本頁自己的（來自 `WHY_LAYOUT` 與規格 ④）。
#: · `card_value_text` / `card_level_text`：**直接沿用 `page_today` 的原函式** ——
#:   它們是「灰態紅態一律留白、`degraded` 觀測照出判決留白」這組 §1 規則的落地，
#:   **與哪一頁無關**，⛔ 不得在本檔另立第二把尺。
#: · `LAYER_GRID_COLS`：**刻意是空的**。線框只給 block 級 `cols`，**⛔ 沒有給任何層級網格欄數**
#:   ⇒ 本頁一旦有人呼叫 `markup.layer_html()` 就會炸（這是**要的**，見 `WHY_GAP_W3`）。
_WHY_CONTRACT = types.SimpleNamespace(
    BLOCK_COLS=WHY_BLOCK_COLS,
    LAYER_GRID_COLS={},
    BADGES_ON_PAGE=WHY_BADGES_ON_PAGE,
    BADGES_NOT_ON_PAGE=WHY_BADGES_NOT_ON_PAGE,
    tier_for_block=why_tier_for_block,
    card_value_text=page_today.card_value_text,
    card_level_text=page_today.card_level_text,
)


@contextlib.contextmanager
def why_page_contract() -> Iterator[None]:
    """`with` 期間 `markup` 走「📖 憑什麼」的版面查表；離開時**一定**還原。

    進場先驗兩件事、離場再驗一件，⛔ 不是「應該可以」：
      1. 代理**蓋得齊** `markup` 實際會讀的每一個 `page_today.*` 名字（AST 掃出來的）；
      2. 進場時 `markup.page_today` **本來就是**真的 `page_today`（⛔ 沒有人忘了還原）；
      3. 離場後 `markup.page_today` **是同一個物件**（`is` 比對，⛔ 不是 `==`）。
    """
    needed = _markup_page_today_names()
    missing = needed - set(vars(_WHY_CONTRACT))
    assert not missing, (
        f"代理少了 markup 會讀的名字：{sorted(missing)} —— "
        "markup.py 多讀了東西而本檔的代理沒跟上。"
        "⛔ 不得為了跑得動就隨便補一個值（那會畫出一個編出來的版面，違 CLAUDE.md §1）。"
    )
    original = markup.page_today
    assert original is page_today, (
        "進場時 markup.page_today 已經不是原物件 —— 上一次替換忘了還原")
    markup.page_today = _WHY_CONTRACT
    try:
        yield
    finally:
        markup.page_today = original
    assert markup.page_today is page_today, "還原失敗：markup.page_today 不是原物件"


# ── 本頁每一塊要畫成什麼狀態 ────────────────────────────────────────────
#
# 🔴 **狀態⛔ 不是挑好看的，是照規格與線框挑的。** 兩道各自獨立的把關：
#    ① 規格 `UI_PAGE_WHY.md` 有寫該塊是哪一態的，照規格；
#    ② 線框該塊的 `states` 十態格裡，**值為 `null` 的一律不准用**
#       —— `null` ＝「這塊在該情況下**結構上不存在**」（規格 ④ 逐字，⛔ 不得畫成空卡）。
#    兩道都是本組 node／grep 實測，見 `build_why_cards()` 逐塊註解。
#
# 🔴 **#4 與 #5 是規格點名「必須畫得出來」的兩顆**（④ 逐字：「畫版面時必須同時畫得出
#    `unwired`（#5）與 `degraded`（#4）」，⛔ 不得只畫 live 版）—— 本頁各出現兩處以上。
WHY_LAYER_NOTE: Mapping[int, str] = {
    0: "三塊的 leaf 在線框是 null ＝ 畫在分頁列之上、三葉共用。statusbar 與 asof 線框自標 "
       "unwired「本頁目前沒有這一條」；footer 是這三條裡唯一已經在畫面上的"
       "（由 L6 app.py 在 st.stop() 之前對每一個 IA 頁統一呼叫）。"
       "⚠️ 在這份 HTML 原型裡，statusbar／asof／footer 三塊的**實體**畫在五頁共用的外殼上"
       "（時點列在頁標題下方、頁尾免責在最底），本層畫的是它們的**版面登記**，"
       "⛔ 不是第二份 chrome。",
    1: "t1 是四階裡唯一 2px 框線、內距最大的一階。四張卡的狀態⛔ 不是挑的 —— "
       "規格 ③ 規則二 (b) 實跑結果逐字：lights ＝ live／health6 ＝ unwired／"
       "scales ＝ degraded／legacy ＝ unwired，也就是「這一葉沒有灰態」這句話在**線框文字**上"
       "成立、在**實作**上不成立（四張中了三張）。"
       "本組另以 node 實測線框同四塊的 states：health6 與 legacy 十態裡只有 unwired 非 null、"
       "scales 的 degraded 非 null、lights 的 live 非 null ⇒ **線框與實跑互相對得上**。",
    2: "五塊全 1/1/1。⚠️ 層標寫「切成三塊」指的是**三張表**（總經／參考走勢／持股），"
       "「5 塊」指的是**五個線框區塊** —— ⑤-d／⑤-e 是表格**下方**的逐列說明區，"
       "⛔ 不是第 4、5 張表；兩個數字各自都對（規格 ① 差異 2）。"
       "⚠️ ⑤-e 整塊**⛔ 沒有徽章**，理由見本頁缺口 W5。",
    3: "⭐ 這一層是**常駐**的，⛔ 不藏在 gate 後面 —— 另外四頁的「去哪補」指路句終點就在這裡；"
       "藏起來等於把四頁的指路句指到一個看不見的地方（規格 ① 差異 1）。"
       "六塊裡有三塊是 3/2/1（wall／finmind_quota／spec.flags），三塊是 1/1/1。",
    4: "t4 是四階裡唯一 dashed 的一階。整層在實作上鎖在單一 gate 後面"
       "（未勾選時一次 L0 登錄表都不讀）⇒ 本頁畫的是它的 idle 態。"
       "⚠️ 與 n3 的可見性**完全相反**，規格 ① 差異 1 逐字⛔ 不得把這兩層合併寫。",
    5: "五頁唯一的三葉頁，葉3 只有一塊。密度 t2 是規格 ② 表給的，"
       "⛔ 不是契約層算出來的（components.tier_for_layer 只認 0 與 1~4）—— 見缺口 W2。"
       "冷啟動是 #3 灰、⛔ 不是紅：線框逐字「第一次進來時是灰的，不是紅的 —— "
       "即使根本沒有金鑰」；規格 ⑤ (a) 另逐字「送出本身就是啟動」。",
}


def build_why_cards() -> dict[str, list[dict]]:
    """每個 block 要畫幾張卡、各是什麼狀態。

    🔴 **卡標題規則沿用「🚦 今天」頁的既有做法**：規格／線框給了名字的用它的名字，
       沒給逐卡名稱的用 `components.badge(n)["name"]`（⛔ 不發明一組沒有出處的中文標題
       —— 同 `_LAYER_NOTE[4]` 對 `today.detail` 的處置）。
    🔴 **每一張畫得出數字的卡都掛 `("資料來源", DEMO)`**（客戶：示意數字必須標明示意）。
    """
    rb = page_today.resolve_badge
    bn = lambda n: str(components.badge(n)["name"])   # noqa: E731

    def demo(*rows: tuple[str, str]) -> tuple[tuple[str, str], ...]:
        """帶數字的卡：事實列 ＋ 一條「⚠️ 示意值 · 未接線」。"""
        return (*rows, ("資料來源", DEMO))

    return {
        # ── n0（線框自標 unwired／footer 已在畫面上；規格 ① 差異 3）──────────────
        "why.statusbar": [
            {"state": "unwired", "title": "（跨頁）頂部狀態列",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": demo(("線框自標", "unwired ·「本頁目前沒有這一條」"),
                           ("出處", "UI_PAGE_WHY ① 差異 3"))},
        ],
        "why.asof": [
            {"state": "unwired", "title": "資料時點揭露列（頁標題下方第一行）",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": (("線框自標", "unwired ·「本頁目前沒有這一條」"),
                       ("這份原型", "外殼上畫了一條示意殼，⛔ 一個真時間都沒填"))},
        ],
        "why.footer": [
            {"state": "live", "title": "頁尾免責（每一頁都要有）",
             "value": None, "level": None, "badge_n": rb(state="live"),
             "facts": demo(("出處", "本頁 chrome 三條裡唯一已經在畫面上的"),
                           ("誰畫的", "L6 app.py 在 st.stop() 之前對每一個 IA 頁統一呼叫"))},
        ],
        # ── n1 四張說明卡：狀態 ＝ 規格 ③ 規則二 (b) 的**實跑結果**（⛔ 不是挑的）──────
        "why.edu.lights": [
            {"state": "live", "title": "① 紅綠燈怎麼判 · 各門檻的出處",
             "value": None, "level": "🟢 這一張是接上的", "badge_n": rb(state="live"),
             "facts": (("實跑狀態", "live（規格 ③ 規則二 (b)）"),
                       ("線框對照", "十態格裡 live 非 null"))},
        ],
        "why.edu.health6": [
            {"state": "unwired", "title": "② 健康評分六因子",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": (("實跑狀態", "unwired（規格 ③ 規則二 (b)）"),
                       ("線框對照", "十態格裡只有 unwired 非 null，其餘九格全 null"),
                       ("要接上需要什麼", "六因子配分 SSOT 真的接進來，"
                                          "⛔ 不得把 state 寫死成 live 假裝"))},
        ],
        "why.edu.scales": [
            {"state": "degraded", "title": "③ 同一個名詞，兩套刻度",
             # degraded ＝ 觀測照出、判決留白（page_today.card_level_text 負責擦掉）
             "value": "2", "level": "🟡 中性", "badge_n": rb(state="degraded"),
             "facts": demo(("實跑狀態", "degraded（規格 ③ 規則二 (b)）"),
                           ("畫面行為", "觀測照出、判決留白 ⇒ 上面那顆等級⛔ 不會畫出來"),
                           ("兩套刻度", "其中已失準的那一側"))},
        ],
        "why.edu.legacy": [
            {"state": "unwired", "title": "④ 完整策略邏輯說明書（既有 📚 教學）",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": (("實跑狀態", "unwired（規格 ③ 規則二 (b)）"),
                       ("線框旗標", "★待拍板"))},
        ],
        # ── n2 逐盞門檻表（三張表 ＋ 兩段表下說明）────────────────────────────
        "why.edu.table.macro": [
            {"state": "live", "title": "⑤-a 總經燈（16 盞）",
             "value": "16", "level": "🟢 盞數取自 L0 常數表", "badge_n": rb(state="live"),
             "facts": demo(("表格欄數", "7 欄"),
                           ("欄名逐字", "這一盞／分組／方向／門檻／值從哪來／在防什麼／已知限制"))},
        ],
        "why.edu.table.reference": [
            {"state": "live", "title": "⑤-b 參考走勢（2 條 · 不算燈）",
             "value": "2", "level": "🟢 不算燈，只是參考", "badge_n": rb(state="live"),
             "facts": demo(("表格欄數", "4 欄"),
                           ("欄名逐字", "這一條／單位／這條線在說什麼／值從哪來"))},
        ],
        "why.edu.table.hold": [
            {"state": "live", "title": "⑤-c 持股燈（12 盞）",
             "value": "12", "level": "🟢 與 ⑤-a 共用同一支表格", "badge_n": rb(state="live"),
             "facts": demo(("表格欄數", "7 欄（與 ⑤-a 同一支）"),
                           ("執行時", "4 張表、3 個呼叫點（⑤-a 與 ⑤-c 共用一個）"))},
        ],
        "why.edu.table.caveat": [
            {"state": "live", "title": "⑤-d 被降級的門檻 —— 為什麼現在不能用（表格下方逐列）",
             "value": None, "level": "🟢 這一段是表格下方的逐列說明",
             "badge_n": rb(state="live"),
             "facts": demo(("它不是第 4 張表", "是三張表下方的逐列說明區（規格 ① 差異 2）"),
                           ("卡標逐字", "本卡標題含「為…什麼」三字，是線框 name 的逐字複本，"
                                        "⛔ 不是頁名 —— 第五頁的頁名一律是「📖 憑什麼」"))},
        ],
        # ⑤-e：**整塊⛔ 不掛徽章**（正確答案是 #10，而 #10 本輪不畫）—— 見 W5。
        "why.edu.table.nolevel": [],
        # ── n3 資料體檢 · 使用者版（⭐ 常駐）──────────────────────────────────
        #    牆是「逐源獨立判態」⇒ 四張卡示範四種**線框十態格非 null** 的態。
        #    標題取 components.badge(n)["name"]（⛔ 不發明來源名 —— 來源是被用到才登記的）。
        "why.source.wall": [
            {"state": "idle", "title": bn(3),
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": (("線框逐字", "⬜ 未檢查 —— 還沒有真的對外抓過"),
                       ("規格 ④", "這是本頁最常見的一態"),
                       ("去哪補", "到會用到它的那一頁按更新／載入，讓它真的跑一次"))},
            {"state": "empty", "title": bn(7),
             "value": None, "level": None, "badge_n": rb(state="empty"),
             "facts": (("線框逐字", "名單讀得到、裡面一支都沒有 ——「這是正常的，不是壞掉」"),
                       ("⛔ 不得", "顯示成一片空白 —— 讀到了沒東西 ≠ 讀不到，兩件事"),
                       ("範圍", "這是整面牆的態，⛔ 不是某一源的態"))},
            {"state": "unwired", "title": bn(5),
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": (("線框逐字", "該源未接線（還沒做）＋ 就地寫明原因"),
                       ("這一態的特點", "沒有你可以做的事 —— 不是你操作的問題"))},
            {"state": "error", "title": bn(6),
             "value": None, "level": None, "badge_n": rb(state="error"),
             "facts": (("線框逐字", "一源紅不會把另外兩源一起染色"),
                       ("第四種紅", "這一盞的狀態本頁看不懂 → 看不懂一律當紅，絕不當綠"))},
        ],
        "why.source.named": [
            {"state": "live", "title": "⑦ 線框具名三源的狀態一覽（常駐 caption）",
             "value": "3", "level": "🟢 常駐，⛔ 不藏在 gate 後面",
             "badge_n": rb(state="live"), "facts": demo(("形式", "常駐 caption"))},
        ],
        "why.source.cache_semantics": [
            {"state": "live", "title": "⑧ 「這面牆上的時間是什麼」（常駐 caption · 誠實揭露）",
             "value": None, "level": "🟢 常駐", "badge_n": rb(state="live"),
             "facts": (("線框逐字", "吃快取不算 —— 拿快取回答的，那一盞仍停在「未檢查」"),)},
        ],
        "why.source.unmeasured.finmind_quota": [
            {"state": "unwired", "title": "⑨ 具名、但這面牆量不到的來源（FinMind API 額度）",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": (("線框對照", "十態格裡只有 unwired 非 null，其餘九格全 null"),
                       ("語意", "線框具名了它，但這面牆量不到 ⇒ 誠實寫「量不到」，"
                                "⛔ 不編一個數字"))},
        ],
        "why.spec.flags": [
            {"state": "degraded", "title": bn(4),
             "value": None, "level": None, "badge_n": rb(state="degraded"),
             "facts": (("線框實況指名", "融資餘額（總經燈）與 財報趨勢（持股燈）"),
                       ("為何在這一區", "「已失準」走燈號表自己的標記，⛔ 不走牆上的格子"))},
            {"state": "unwired", "title": bn(5),
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": (("線框實況指名", "外資現貨淨買賣"),)},
        ],
        "why.source.coverage": [
            {"state": "live", "title": "⑪ 涵蓋率揭露（常駐 caption · 本頁最重要的一段話）",
             "value": "9", "level": "🟢 常駐", "badge_n": rb(state="live"),
             "facts": demo(("這個 9 是什麼", "被監控的取數點個數；規格檔末「本組實查」段的實跑值，本組另以 grep 自行重測同為 9（量測日 2026-09-22）"),
                           ("⛔ 不寫成分數", "N／M 是 #9 的語意，而 #9 在本頁待接線 —— "
                                             "寫成分數等於假裝它已經接上"))},
        ],
        # ── n4 資料體檢 · 工程師版（單一 gate）──────────────────────────────
        "why.engineer.gate": [
            {"state": "idle", "title": "⑫ 進階診斷（要兩步才打得開）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(("規格 ④ (ii)", "未勾選時整區 idle —— 一次 L0 登錄表都不讀"),
                           ("與 n3 的差別", "n3 常駐、n4 在 gate 後面，可見性完全相反"))},
        ],
        "why.engineer.monitor": [
            {"state": "live", "title": "⑬ 🛰️ 取數監控（六個面板中唯一接得上的）",
             "value": None, "level": "🟢 六個面板裡唯一接得上的", "badge_n": rb(state="live"),
             "facts": demo(("表格欄數", "8 欄"),
                           ("欄名逐字", "fetcher／分類／更新頻率／最後一次真實抓取／回了幾列／"
                                        "耗時(ms)／錯誤／本頁看不懂的狀態"))},
        ],
        "why.engineer.panels": [
            {"state": "unwired", "title": "⑭ 其餘五個面板",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": (("五個面板逐字", "資料源清單／雙演算法對帳／API 根因／原始資料表／門檻校準"),
                       ("線框對照", "十態格裡 live 為 null ⇒ 結構上就不存在「接上了」這一格"))},
        ],
        # ── n5 葉3 AI 問答 ────────────────────────────────────────────────
        "why.qa": [
            {"state": "idle", "title": "⑮ AI 問答（對話區 ＋ 狀態卡）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": (("線框逐字", "第一次進來時是灰的，不是紅的 —— 即使根本沒有金鑰"),
                       ("規格 ⑤ (a)", "送出本身就是啟動（不需要再按別的鈕）"),
                       ("⛔ 不得", "在問之前先亮紅燈 —— 那是替一個還沒發生的失敗製造假警報"))},
        ],
    }


#: ⑤-e 整塊的**就地揭露**（它沒有卡、沒有徽章，只有這一段）。
WHY_NOLEVEL_DISCLOSURE = (
    "⑤-e 依規格就不出等級的燈（不是壞掉，是還沒有判燈規則）—— "
    "⚠️ 這一塊本輪⛔ 沒有卡、⛔ 沒有徽章，是刻意的。"
    "它的正確徽章是 #10 ◆「只描述，不判等級」（規格 ④ 指名本頁是前六份中第一個有適用對象的，"
    "實跑 1 項「KD 指標」），但 #10 在本頁**尚未徽章化**，"
    "而且 markup.page_css() 的輸出裡⛔ 沒有 .bdg-10 這條規則（本組實測 0 命中）"
    "⇒ 硬畫出來會是一顆**無配色的徽章**，那正是 CLAUDE.md §1 最危險的那一型：看起來成功、其實是假的。"
    "⛔ 更不得拿 #5／#4／#7 冒充 —— 規格 ④ 三句反面話逐字："
    "unwired 說它沒接（假的）、degraded 說它門檻失準（假的，它從來沒有門檻）、"
    "empty 說它沒資料（假的，K、D 都抓得到）。⇒ 三句都不是實情。"
    "本輪處置：畫出這一塊的版面位置（層／欄數／密度都在），但⛔ 不掛任何徽章。見缺口 W5。"
)

#: 「📖 憑什麼」頁**本輪查到的缺口**，逐條登記並**畫在畫面上**（客戶：就地揭露）。
#: 🔴 每一條同樣是 **⚠️ 單組／兩組調查結論，未經第三方驗**（CLAUDE.md §-2 規則 6）。
WHY_SPEC_GAPS: tuple[tuple[str, str, str], ...] = (
    (
        "W1",
        WHY_LAYOUT_DISCLOSURE,
        WHY_LAYOUT_DISCLOSURE_WHY
        + "／／來歷：客戶 2026-09-22 拍板逐字「1. 走選項 1：版面定義寫在產生器，"
          "畫面上就地揭露缺口」⇒ 這是**已拍板的作法**，⛔ 不是偷懶，"
          "但它的後果必須看得見，所以有這一條。",
    ),
    (
        "W2",
        "n5（葉3）超出契約層的層序對映 ⇒ 它的卡密度 t2 只能寫在本產生器裡。",
        "實測：components.tier_for_layer(5) 拋 ValueError「未知的層序 5：只有 0（葉外 chrome）"
        "與 1~4 四層」。而 UI_PAGE_WHY ② 表「葉3」列逐字給了 t2，並自陳"
        "「沿用 UI_PAGE_FIND 對 n5 的新訂：超出 n1~n4 自動對映時取「核心卡」，⛔ 非本組發明」。"
        "⇒ 規格有、契約層沒有。本檔把它寫成 WHY_N5_TIER 常數並標明出處，"
        "n0~n4 則一律走 components.tier_for_layer（⛔ 不在本檔手抄第二份對映表）。"
        "真正的解是契約層補上 n5 的對映，但那要動 src/ui_v2/components.py ⇒ ⛔ 不在本輪授權範圍。",
    ),
    (
        "W3",
        "本頁⛔ 沒有任何「層級網格」的來源 ⇒ 代理的 LAYER_GRID_COLS 是空的，"
        "markup.layer_html() 在本頁一律會炸（這是要的）。",
        "實測：線框 22 個 block 都只有 block 級的 cols（desktop／tablet／phone 三鍵），"
        "layers[] 上⛔ 沒有任何欄數欄位。對照「🚦 今天」頁：它的 LAYER_GRID_COLS 只有第二層，"
        "而那一格有明確來歷（客戶 2026-09-16「3 張並排卡」＋ 原型 .g3 實測）。"
        "⇒ 本頁沒有那樣的來歷，就⛔ 不給它一個猜的欄數；六層一律逐 block 全寬輸出。"
        "markup.layer_html 自己的 docstring 逐字要求同一件事："
        "「沒有登記層級網格的層 → 炸…⛔ 不得 try/except 吞掉改成預設 1 欄」。",
    ),
    (
        "W4",
        "cols 的語意本身未決（＝「🚦 今天」頁登記的 U-2）⇒ 本頁 8 塊 3/2/1 照契約層語意原樣渲染，"
        "⛔ 不代為裁決。",
        "現況：契約層把 cols 讀成「**卡內**網格一列幾格」（markup.grid_html 的 .g-* class）。"
        "但本頁 n1 的四塊各自是獨立 block、每塊只有 1 張卡，卻四塊都標 3/2/1 ⇒ "
        "「3/2/1」也可以被讀成「這四塊並排」。兩種讀法會畫出不一樣的版面。"
        "「🚦 今天」頁的同一個問題已拆為 U-2 並記為「仍未判定」（見本檔 _LAYER_NOTE[2]）⇒ "
        "本頁沿用同一處置：照現行契約層語意原樣渲染，⛔ 不裁決。"
        "／／另轉錄一條**不影響本原型**的：UI_PAGE_WHY ② 逐字記載 3/2/1 的 tablet=2 在 "
        "Streamlit 實作端未落地（641–880 仍恆 3 欄），並註明「沿用 UI_PAGE_FIND 的實作待修登記，"
        "⛔ 本頁不另開一筆」⇒ 本檔**也不另開一筆**。"
        "⚠️ 這份 HTML 原型的 CSS 本身是對的：.g-3-2-1 三段實測 ＝ 3/2/1（產生器結尾有守衛）。",
    ),
    (
        "W5",
        "#10 ◆ 有適用對象但尚未徽章化；且 markup.badge_html(10) **不報錯** ⇒ 會畫出一顆無配色的徽章。",
        "實測三件事：(a) UI_PAGE_WHY ④ 逐字「本頁是前六份中第一個有適用對象的」，"
        "實跑 no_level ＝ 1 項「KD 指標」；同段又逐字「現況以 st.caption 逐列呈現、◆ 0 命中 ⇒ "
        "徽章化為待補」。(b) markup.page_css('dark') 的輸出裡 .bdg-10 **0 命中**。"
        "(c) markup.badge_html(10) **不拋例外**，回傳 <span class=\"bdg bdg-10\">…</span> ⇒ "
        "一顆沒有任何配色規則的徽章。⇒ 客戶 2026-09-22 拍板逐字「3. badge_html(10) 不報錯 → "
        "登記為待修（**本輪不動**）」。本輪處置：本頁的代理把 10 放進 BADGES_NOT_ON_PAGE，"
        "任何一次誤畫都會在產生時變成 ValueError；⑤-e 整塊⛔ 不掛徽章"
        "（⛔ 不得拿 #5／#4／#7 冒充，規格 ④ 三句反面話）。"
        "真正的解有兩條：補 .bdg-10 的 CSS，或讓 badge_html 對未出現在該頁的徽章 fail loud；"
        "兩條都要動 src/ui_v2/ ⇒ ⛔ 不在本輪授權範圍。",
    ),
    (
        "W6",
        "#2（載入中）未落地、#8／#9 待接線 ⇒ 本頁⛔ 不畫這三顆。",
        "UI_PAGE_WHY ④ 表逐字：#2「Name 0、st.spinner 0 ⇒ 未落地，⛔ 不得拿 #3 冒充載入中」；"
        "#8「MISS_NOT_APPLICABLE 0 命中 ⇒ #8 未落地，⛔ 不得把 missing 畫成 #8"
        "（重跑無效，畫錯＝給錯指引）」；#9「◧ 0、「已檢查」0 ⇒ 未落地…分子分母拿不到 → "
        "一律降 #7，⛔ 不得退回 #1」。同節末句逐字「會出現在畫面上的是 6 態：#1／#3／#4／#5／#6／#7」。"
        "⇒ 本頁的 WHY_BADGES_ON_PAGE 就是那 6 顆，其餘四顆由代理擋成 ValueError。"
        "⚠️ 對照「🚦 今天」頁：它畫 #1~#9（只擋 #10）—— 兩頁的可畫集合不同是**規格不同**，"
        "⛔ 不是本檔挑的。",
    ),
    (
        "W7",
        "規格三條特殊規則裡的規則二「這頁沒有灰態」在**實作上不成立** ⇒ 版面必須畫得出 #4 與 #5。",
        "UI_PAGE_WHY ③ 規則二 (b) 的實跑結果逐字：四張教學卡 ＝ live／unwired／degraded／unwired "
        "⇒ 四張中了三張。同檔 ④ 逐字「畫版面時必須同時畫得出 unwired（#5）與 degraded（#4），"
        "⛔ 不得只畫 live 版」。本頁照辦：#5 出現在 statusbar／asof／edu.health6／edu.legacy／"
        "source.wall／finmind_quota／spec.flags／engineer.panels，#4 出現在 edu.scales／spec.flags。"
        "⛔ 明確不做的事：把那三張卡的 state 寫死成 live 讓畫面好看 —— 規格 ③ (c) 逐字"
        "「⛔ 不得用『把 state 寫死 live』來假裝 —— 那會把『這項還沒做』畫成『正常』，違 CLAUDE.md §1」。",
    ),
    (
        "W8",
        "線框對 subtitle 的白話指路句提案 ★待拍板 ⇒ 本頁⛔ 不畫那句。",
        "UI_PAGE_WHY ③ 規則三逐字：線框記載客戶回饋「有些頁面寫『本頁目前沒有主 CTA』，新手會迷失」，"
        "線框的做法是**不新增按鈕**、改在 subtitle 加一句白話指路，並自標 ★待拍板"
        "（flags 含「★待拍板／偏離核准線框／單組結論」）⇒ 規格同段逐字「登記為未決，⛔ 本份不代決、"
        "⛔ 不得寫成已生效」。本頁照辦：⛔ 不畫該句、⛔ 不發明主 CTA"
        "（規格 ③ 規則三逐字：線框 mainCTA 值為 null，本組 node 複驗命中）。",
    ),
    (
        "W9",
        "「無金鑰時要不要就地給設定入口」★待拍板 ⇒ 本頁⛔ 不畫設定入口。",
        "UI_PAGE_WHY ⑤ 逐字：S1-3B 規格要求「去哪補：本頁就地顯示設定入口與步驟」"
        "＋ ⛔「不得把使用者指去改 .streamlit/secrets.toml」；線框與實作則寫"
        "「要開這個入口必須先由客戶拍板『這一頁可以收金鑰』，本批不做」，理由是"
        "「那等於在畫面上收憑證」。規格判定逐字：兩者都沒有把使用者指去改 toml"
        "（規格的 ⛔ 沒有被違反），分歧只在要不要就地給入口 ⇒ **登記為未決**。本頁照辦：不畫。",
    ),
    (
        "W10",
        "線框十態格的有值格數**兩組數字不一致**（114 vs 112）⇒ 本頁畫面上⛔ 一個都不寫。",
        "UI_PAGE_WHY ④ 逐字：「220 格中 114 有值、106 為 null」，同句又註"
        "「與 INV-9B 轉述的『112 有值／108 null』差 2 格…**兩組數字不一致，本項待第三方裁定，"
        "⛔ 不得引用任一數字當前提**」。⇒ 本檔**兩個數字都沒有寫進畫面**，"
        "也⛔ 沒有拿它們去推導任何版面決定。"
        "⚠️ 本組確實用 node 自己數了一次（⛔ 不引用他組轉述），但依上引的 ⛔，"
        "本組的數字同樣**只是第三個單組結論**，⛔ 不足以裁定，故同樣不寫進畫面。"
        "本頁真正依賴的是**逐格 null / 非 null**（哪一態結構上存在），那是逐塊查的，⛔ 不依賴總數。",
    ),
    (
        "W11",
        "首屏可見範圍：三個斷點一律「需實機量測」⇒ ⛔ 不猜、⛔ 不寫推導值冒充量測。",
        "UI_PAGE_WHY ② 逐字：「首屏可見範圍：三個斷點一律『需實機量測』…"
        "⛔ **不猜、⛔ 不得寫推導值冒充量測**」，並指出實作端另有 st.tabs 頭高與 st.expander 邊框高"
        "兩個 repo 反解不出的高度來源。⇒ 本檔⛔ 沒有寫任何首屏高度數字。"
        "⚠️ 這份 HTML 原型的排版與 Streamlit 實作**不是同一套 CSS** ⇒ 即使量了這份，"
        "也⛔ 不能拿去當 Streamlit 端的答案。",
    ),
    (
        "W12",
        "線框裡的 ▨ 符號待同步（已自 #7／#8 撤掉）⇒ 本頁⛔ 不出現 ▨，一律用契約層的符號。",
        "UI_PAGE_WHY ④ 逐字：「▨ 在 wf_page_why.js **11 處**…但依 UI_COMPONENTS 撤銷紀錄，"
        "▨ 已自 #7／#8 撤掉、改 ⚠︎ — 與 N/A ⇒ 凡屬 #7／#8 語意者一律改用第 2 份符號」，"
        "同段另註「⛔ 本份不改線框」。⇒ 本頁的徽章符號**一律由 components.BADGES 產出**"
        "（本檔⛔ 沒有手打任何徽章符號），故不受 ▨ 影響；"
        "線框端的同步屬另案，⛔ 不在本輪授權範圍（線框檔本輪一個字都沒動）。",
    ),
)

#: **允許清單**：規格／線框**逐字**名稱裡本來就帶那三個字的地方（⛔ 不是頁名）。
#: 🔴 存在理由：`main()` 有一道**全檔級**守衛，禁止「為…什麼」三字出現
#:    （客戶 2026-09-22 ④ 明示第五頁用 SSOT 的「📖 憑什麼」）。本輪新增的「📖 憑什麼」頁
#:    帶進一個**線框 `name` 的逐字複本**含那三個字 ⇒ 兩者相撞。
#: ⛔ **⛔ 不削弱守衛，也⛔ 不竄改規格名**：沿用本檔既有的「先遮掉已知合法、再掃剩下的」
#:    同一招（HH:MM 那道守衛就是這樣做的），把**逐字出處**列進允許清單，其餘仍然一個都不准。
#: ⚠️ 每一條都必須是**線框／規格的逐字**，⛔ 不得拿本檔自己的散文往這裡塞。
WHY_VERBATIM_ALLOW_WEISHENME: tuple[str, ...] = (
    # 線框 `why.edu.table.caveat` 的 `name` 逐字（本組 node 實測，22 個 name 裡唯一命中）
    "⑤-d 被降級的門檻 —— 為什麼現在不能用（表格下方逐列）",
)


def build_why_body() -> str:
    """「📖 憑什麼」頁的整頁標記。**全程在 `why_page_contract()` 之內**。

    🔴 標記一個角括號都不手打卡片：`markup.card_html` / `markup.grid_html` 產。
    🔴 **⛔ 不呼叫 `markup.layer_html`**：本頁沒有層級網格的來源（見 `WHY_GAP` W3）——
       六層一律逐 block 全寬輸出，與 `build_body()` 對「沒登記層級網格的層」的處置相同。
    """
    cards_by_block = build_why_cards()
    parts: list[str] = [
        # ── R4 就地揭露：**收起狀態也看得見**，⛔ 不藏進摺疊器 ──
        '<section class="pv-layer" id="pv-why-disclosure">',
        '<div class="pv-layer-label">📖 憑什麼 · 六層 22 block（版面定義在產生器內）</div>',
        f'<p class="pv-disclosure">{esc(WHY_LAYOUT_DISCLOSURE)}</p>',
        f'<p class="pv-meta">{esc(WHY_LAYOUT_DISCLOSURE_WHY)}</p>',
        f'<p class="pv-meta">{esc(WHY_PAGE_SHAPE_NOTE)}</p>',
        "</section>",
    ]

    with why_page_contract():
        for n, blocks in WHY_LAYER_BLOCKS.items():
            tier = why_tier_for_layer(n)
            leaf = WHY_LAYER_LEAF[n]
            leaf_text = "葉外（三葉共用）" if leaf is None else f"{leaf} {WHY_LEAF_NAME[leaf]}"
            parts.append('<section class="pv-layer">')
            parts.append(
                f'<div class="pv-layer-label">{esc(WHY_LAYER_LABEL[n])} · n{n} · '
                f'{esc(leaf_text)} · 密度 {esc(tier)} · '
                f'block {len(blocks)} 塊：{esc("、".join(blocks))}</div>'
            )
            parts.append(
                f'<p class="pv-meta">components.CARD_TIERS[<span class="pv-mono">'
                f'{esc(tier)}</span>]：{esc(_tier_caption(tier))}</p>'
            )
            parts.append(f'<p class="pv-meta">{esc(WHY_LAYER_NOTE[n])}</p>')
            for block in blocks:
                cards = [markup.card_html(block=block, **card)
                         for card in cards_by_block[block]]
                if block == "why.edu.table.nolevel":
                    # ⑤-e：⛔ 沒有卡、⛔ 沒有徽章，只有就地揭露（見 W5）。
                    assert not cards, "⑤-e ⛔ 不得有卡：它的正確徽章 #10 本輪不畫"
                    cards = [f'<p class="pv-disclosure">'
                             f'{esc(WHY_NOLEVEL_DISCLOSURE)}</p>']
                parts.append(markup.grid_html(block=block, cards=cards))
            parts.append("</section>")

    # ── 本頁的缺口，逐條畫出來（⛔ 不只留在 .py 裡）──
    parts.append('<section class="pv-layer" id="pv-why-gaps">')
    parts.append('<div class="pv-layer-label">附錄 · 「📖 憑什麼」頁本輪查到的缺口（逐條登記）</div>')
    parts.append(
        f'<p class="pv-meta">{esc("每一條都是：" + GAP_CAVEAT + "。⛔ 不得被引用為「已查證的事實」去支撐下一步決策（CLAUDE.md §-2 規則 6）。")}</p>')
    for gap_id, title, detail in WHY_SPEC_GAPS:
        parts.append(
            f'<p class="pv-meta"><span class="pv-mono">{esc(gap_id)}</span>　'
            f"{esc(title)}　{esc(GAP_CAVEAT)}</p>"
        )
        parts.append(f'<p class="pv-meta">{esc(detail)}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def build_why_html() -> str:
    """把「📖 憑什麼」整頁包成一個可切換的容器（預設 `hidden`，由側欄點出來）。"""
    return "\n".join([
        html_comment(
            "「📖 憑什麼」頁 ＝ **六層 22 block**（⛔ 不是四層）。\n"
            "客戶 2026-09-22 拍板逐字：\n"
            "  「2.「憑什麼」頁照規格 6 層，⛔ 不是四層（客戶先前記的四層是簡化說法）」\n"
            "⛔ 本頁的版面定義住在產生器的 `WHY_LAYOUT`，**不在** `src/ui_v2/` 契約層、\n"
            "  **沒有** `tests/ui_v2/` 的測試守護 —— 這是客戶拍板的「選項 1」，\n"
            "  而它的後果已就地揭露在本頁最上方與附錄 W1。\n"
            "⭐ 標記怎麼來的：產生期間把 `markup.page_today` **暫時**換成本頁的版面契約，\n"
            "  卡片與網格仍由 `markup.card_html` / `grid_html` 產出 ⇒ 與「真的有 page_why.py」\n"
            "  的產物逐字相同；產完**立刻還原**，「🚦 今天」頁仍走真正的 `page_today`。\n"
            "⛔ 本頁⛔ 沒有畫任何 #10 徽章：`.bdg-10` 不在 `page_css()` 的輸出裡，\n"
            "  硬畫會是一顆無配色的徽章（客戶已裁示該項登記為待修、本輪不動）。"
        ),
        '<div id="pv-page-why" hidden>',
        "<main>",
        build_why_body(),
        "</main>",
        "</div>",
    ])


# ══════════════════════════════════════════════════════════════════
# 4.7 「🔍 找標的」頁 —— 版面定義寫在產生器（沿用 4.6 的「選項 1」作法）
#
# 🔴 **客戶 2026-09-22 拍板逐字（本節就是這三條的落地）**：
#    「【拍板 1：CSS 走 (甲)】在產生器補 `.g-3-3-1` 與 `.g-2-1-1` 兩條 rule。
#      值用 `components.resolve_cols()` ＋ `BREAKPOINTS` 算。就地揭露「規則形狀複製了一份」。」
#    「【拍板 2：主 CTA】不是「全站唯一」，是「每頁首屏唯一」。
#      FIND 的「🎯 開始選股」就是它的每頁唯一主 CTA。」
#    「2. 6 層 14 block　3. 元件全部從 `src/ui_v2/` 生成　4. 側欄切到「🔍 找標的」可顯示
#      5. 其他兩頁（查一檔、我的持股）仍顯示「此頁待做」
#      6. 遇到規格衝突 → 就地標明、寫進附錄、⛔ 不自行裁決」
#
# 🔴 **⛔ 不發明 block、⛔ 不發明 cols。** 14 筆每一筆都在 `src` 欄標出處
#    （規格**章節名** ＋ 線框 **block key**；依 CLAUDE.md §8.2.A.0 規則 1 **⛔ 不寫行號**）。
#
# 📌 **兩個來源**（本組各自 node／import 實跑過，⛔ 非讀他組轉述）：
#    · 規格 `docs/v2/spec/UI_PAGE_FIND.md`（六節 ①~⑥）
#    · 線框 `docs/v2/wireframe/wf_page_find.js` 的 `id:"find"`
#      —— block 巢在 `layers[].blocks[]`，本組 node 實測 **6 層 14 block 2 葉**，
#      `cols` 全集 **4 種**：`1/1/1` 10 塊、`3/2/1` 1 塊、`3/3/1` 1 塊、`2/1/1` 2 塊。
# ══════════════════════════════════════════════════════════════════

#: 就地揭露的**那一句**（同 `WHY_LAYOUT_DISCLOSURE`：版面不在契約層、無測試守護）。
FIND_LAYOUT_DISCLOSURE = (
    "⚠️ 此頁版面定義在產生器內，未進 src/ui_v2/ 契約層、無 tests/ui_v2/ 測試守護。"
)

#: 上面那句的**後果**（⛔ 不是免責套話，是可查證的差別）。
FIND_LAYOUT_DISCLOSURE_WHY = (
    "差別在哪：「🚦 今天」頁的版面（哪個 block 在第幾層、幾欄、哪一階密度）住在 "
    "src/ui_v2/page_today.py，改壞了 tests/ui_v2/ 會紅燈；本頁的同一組資料住在 "
    "docs/v2/prototype/gen_today_v2.py 的 FIND_LAYOUT，改壞了⛔ 沒有任何測試會攔。"
    "⇒ 本頁的版面只有「跟規格與線框對照」這一種查法，⛔ 沒有機器守衛。"
    "本產生器在結尾自己跑了一輪對照（14 個 block key／層／欄數 class／密度 class 逐一比對，"
    "另從 CSS 文字量三個斷點的實際欄數），但那是**同一組人寫的自驗**，⛔ 不等於獨立測試。"
)

#: ⭐ **本頁比「📖 憑什麼」頁多一個缺口**：它用到兩組契約層**沒有產 CSS** 的欄數。
FIND_GRID_CSS_DISCLOSURE = (
    "⚠️ 本頁有兩條欄數規則（.g-3-3-1 與 .g-2-1-1）是**產生器自己補的**，⛔ 不在 src/ui_v2/ 契約層。"
    "非補不可的理由（實測，⛔ 非推測）：markup.page_css() 只產「page_today.BLOCK_COLS 裡真的出現過」"
    "的欄數 class，而那份查表只有 1/1/1 與 3/2/1 兩種；markup._BLOCK_COLS_USED 是 module-level、"
    "import 當下就依 page_today 算好了，本頁的代理換不動它。"
    "而 markup.grid_html() 對「沒有對應 CSS 的欄數」**不報錯**，會照樣吐出 g-3-3-1 這個 class，"
    "偏偏 .grd 基準規則裡**沒有** grid-template-columns ⇒ 那 3 塊會**靜默塌成單欄**、三個斷點長得一樣。"
    "這與 .bdg-10「畫得出來但沒有配色」是**同一型的靜默失效**（CLAUDE.md §1 最危險的那一型："
    "看起來成功、其實是假的）。"
)

#: 🔴 客戶明示的「就地揭露」那一句 —— **規則的形狀被複製了一份 ⇒ 第二個真相源**。
FIND_GRID_CSS_DISCLOSURE_WHY = (
    "🔴 就地揭露（客戶 2026-09-22 拍板 1 明示⛔ 不得省）：**規則的「形狀」被複製了一份，"
    "這是第二個真相源。** 補的那兩條裡，**數字沒有第二份** —— 欄數一律用公開 API "
    "components.resolve_cols(cols, components.BREAKPOINTS[…]) 算、斷點值一律取 "
    "components.BREAKPOINTS，⛔ 沒有寫死 3／2／1／640／880 任何一個。"
    "被複製的是**形狀**三件事：class 怎麼命名（g-桌-平-手）、宣告怎麼寫"
    "（grid-template-columns:repeat(N,minmax(0,1fr))）、兩個 @media 的順序（先 880 後 640，"
    "因為 640 也命中 max-width:880px）。這三件事住在 markup._grid_rules() 與 "
    "markup._breakpoint_rules()，**是底線開頭的私有函式** ⇒ ⛔ 不得直接呼叫"
    "（本 repo 登記在案的違憲 V-PICKER-PRIV-1 就是跨層直取私有符號）。"
    "⇒ **後果**：markup 日後若改了 class 命名或宣告寫法，本檔**不會跟著改，而且沒有任何測試會攔**。"
    "**真正的解**是把這兩組 cols 放進契約層、讓 page_css() 自己產，那要動 src/ui_v2/ "
    "⇒ ⛔ 不在本輪授權範圍。本產生器結尾有一道守衛：從產出的 CSS 文字用 regex 量三個斷點的"
    "實際欄數，3/3/1 與 2/1/1 任一段不符就炸 —— 但那同樣是同一組人寫的自驗，⛔ 不等於獨立測試。"
)

#: 本頁的**形狀**（本組自己量的，⛔ 不引用他組轉述）。
FIND_PAGE_SHAPE_NOTE = (
    "本頁形狀（本組自行實測，⛔ 非引用轉述）：規格 docs/v2/spec/UI_PAGE_FIND.md ＋ 線框 "
    "docs/v2/wireframe/wf_page_find.js 的 id 為 find 那一頁 —— node 解析結果："
    "6 層、14 block、2 葉（l1 選股網／l2 板塊地圖，後者是產業熱力圖＋板塊資金潮汐兩個既有分頁併出來的）；"
    "14 塊的 cols 全集有 4 種，1/1/1 共 10 塊、3/2/1 共 1 塊、3/3/1 共 1 塊、2/1/1 共 2 塊。"
    "線框 mainCTA 欄位存在且非 null（label 逐字「🎯 開始選股」）⇒ 本頁**有**主 CTA，"
    "與「📖 憑什麼」頁（mainCTA 為 null）相反。"
)

#: 六層的層標 —— `UI_PAGE_FIND.md` ① 四層結構表**第一欄逐字**（⛔ 去掉 markdown 粗體記號）。
FIND_LAYER_LABEL: Mapping[int, str] = {
    0: "葉外",
    1: "第一層 條件表單",
    2: "第二層 總覽卡",
    3: "第三層 大表＋CSV",
    4: "第四層 展開佐證",
    5: "葉2",
}

#: 每層所屬的葉 —— 線框 `layers[].blocks[].leaf`（本組 node 實測，同層內全同值）。
#: `None` ＝ 線框 `leaf: null`（葉外 chrome，畫在分頁列之上、兩葉共用）。
FIND_LAYER_LEAF: Mapping[int, str | None] = {
    0: None, 1: "l1", 2: "l1", 3: "l1", 4: "l1", 5: "l2",
}

#: 兩葉的名字 —— 線框 `leaves[].name` 逐字（本組 node 實測）。
FIND_LEAF_NAME: Mapping[str, str] = {
    "l1": "選股網",
    "l2": "板塊地圖（＝產業熱力圖＋板塊資金潮汐）",
}

#: `n5` 的卡密度。**⭐ 出處就是 `UI_PAGE_FIND.md` ① 表自己那一列**：
#: 「t2（**WH 本組新訂**：`n5` 超出 `n1~n4` 自動對映，取「核心卡」）」。
#: 🔴 **⛔ 不得寫成「借「📖 憑什麼」頁的」** —— 方向剛好相反：`UI_PAGE_WHY.md` ② 表的
#:    `葉3 / n5` 列自己逐字寫「**沿用 `UI_PAGE_FIND` 對 `n5` 的新訂**」
#:    ⇒ **本頁（FIND）才是原創處**，那一頁是沿用者。
#: 🔴 契約層 `components.tier_for_layer()` 只認 0 與 1~4（實測 `tier_for_layer(5)` → `ValueError`）
#:    ⇒ 這一格是**規格有、契約層沒有**的地方，已登記為 `FIND_SPEC_GAPS` 的 F14。
FIND_N5_TIER = "t2"

#: 本頁**會畫**的徽章。
#: ⚠️ **⛔ 這不是規格的逐字，是本組自 `UI_PAGE_FIND.md` ② 表「實作」欄推導的**
#:    —— 該份**沒有**像 `UI_PAGE_WHY.md` ④ 那樣的「會出現在畫面上的是 N 態」總結句。
#:    推導方式（逐列，⛔ 不是挑的）：② 表「實作」欄 ✅ 的取用（#1 live／#3 idle／#6 error）、
#:    ⚠️ 的取用（#4 degraded「僅葉2 可達」、#7「實作只有單一 UI_EMPTY」）、
#:    ❌ 的一律不畫（#2 loading 未落地／#5 unwired 已撤回／#8 na 未拆二／#9 partial 未接線）、
#:    #10 該表逐字「本頁 emits_level 0 命中 ⇒ **不畫 #10**；⛔ 不得併進 #8」。
#:    ⇒ 這是**單組判定**，已登記為 `FIND_SPEC_GAPS` 的 F13（CLAUDE.md §-2 規則 6）。
FIND_BADGES_ON_PAGE: frozenset[int] = frozenset({1, 3, 4, 6, 7})
FIND_BADGES_NOT_ON_PAGE: frozenset[int] = frozenset(
    int(b["n"]) for b in components.BADGES if int(b["n"]) not in FIND_BADGES_ON_PAGE
)

#: 本頁的**版面定義**（六層 14 block）。`cols` ＝ `(桌機, 平板, 手機)`。
#: 🔴 每一筆的 `src` 是**出處**，⛔ 不是註解：規格章節名 ＋ 線框 block key。
FIND_LAYOUT: tuple[Mapping[str, object], ...] = (
    # ── n0 葉外｜全域 chrome（線框 `leaf: null`，兩塊全 1/1/1）─────────────────
    {"block": "find.statusbar", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「葉外」列 ＋ ⑤ 反例自檢 A 末條｜線框 find.statusbar"},
    {"block": "chrome.asof", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「葉外」列 ＋ ⑤ 反例自檢 A 末條｜線框 chrome.asof"},
    # ── n1 葉1 選股網｜條件表單（① 表該列 cols 逐字「3/2/1・3/3/1・1/1/1」）─────
    {"block": "find.screen_form", "n": 1, "cols": (3, 2, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第一層 條件表單」列（該列 cols 首項 3/2/1）"
            "｜線框 find.screen_form"},
    {"block": "find.scenario_quickpick", "n": 1, "cols": (3, 3, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第一層 條件表單」列（該列 cols 次項 3/3/1）"
            "｜線框 find.scenario_quickpick"},
    {"block": "find.wiring_disclosure", "n": 1, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第一層 條件表單」列（該列 cols 末項 1/1/1）"
            "｜線框 find.wiring_disclosure"},
    # ── n2 葉1｜選股結果總覽卡（① 表逐字 1/1/1）──────────────────────────────
    {"block": "find.screen_summary", "n": 2, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第二層 總覽卡」列｜線框 find.screen_summary"},
    # ── n3 葉1｜大表＋入選理由＋CSV（① 表逐字三塊全 1/1/1）────────────────────
    {"block": "find.screen_table", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第三層 大表＋CSV」列｜線框 find.screen_table"},
    {"block": "find.pick_reason", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第三層 大表＋CSV」列｜線框 find.pick_reason"},
    {"block": "find.csv", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第三層 大表＋CSV」列｜線框 find.csv"},
    # ── n4 葉1｜展開佐證（單獨成層；t4 是四階唯一 dashed）───────────────────────
    {"block": "find.pe_two_kinds", "n": 4, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「第四層 展開佐證」列 ＋ ④ 全節"
            "｜線框 find.pe_two_kinds"},
    # ── n5 葉2 板塊地圖（① 表逐字「1/1/1・2/1/1・2/1/1・1/1/1」）──────────────
    {"block": "find.map_cta", "n": 5, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「葉2」列（該列 cols 第 1 項 1/1/1）｜線框 find.map_cta"},
    {"block": "find.heatmap", "n": 5, "cols": (2, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「葉2」列（該列 cols 第 2 項 2/1/1）｜線框 find.heatmap"},
    {"block": "find.sector_flow", "n": 5, "cols": (2, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「葉2」列（該列 cols 第 3 項 2/1/1）｜線框 find.sector_flow"},
    {"block": "find.map_scale_disclosure", "n": 5, "cols": (1, 1, 1),
     "src": "UI_PAGE_FIND ① 四層結構表「葉2」列（該列 cols 第 4 項 1/1/1）"
            "｜線框 find.map_scale_disclosure"},
)

#: 由 `FIND_LAYOUT` **推導**（⛔ 不另手寫一份，否則就是第二個真相源 —— CLAUDE.md §2.1）。
FIND_BLOCK_COLS: Mapping[str, tuple[int, int, int]] = {
    str(rec["block"]): tuple(rec["cols"]) for rec in FIND_LAYOUT   # type: ignore[misc]
}
_FIND_BLOCK_LAYER: Mapping[str, int] = {
    str(rec["block"]): int(rec["n"]) for rec in FIND_LAYOUT        # type: ignore[arg-type]
}
FIND_LAYER_BLOCKS: Mapping[int, tuple[str, ...]] = {
    n: tuple(str(rec["block"]) for rec in FIND_LAYOUT if int(rec["n"]) == n)  # type: ignore[arg-type]
    for n in sorted({int(rec["n"]) for rec in FIND_LAYOUT})                   # type: ignore[arg-type]
}


def find_tier_for_layer(n: int) -> str:
    """層序 → 卡密度（作法與 `why_tier_for_layer` 完全相同，理由見該函式）。

    · `n0~n4`：**一律走契約層** `components.tier_for_layer()`，⛔ 不在本檔手抄一份。
    · `n5`：取 `FIND_N5_TIER`（**出處是 `UI_PAGE_FIND.md` ① 表自己那一列**，⛔ 非本檔發明、
      ⛔ 也不是「借「📖 憑什麼」頁的」—— 方向相反，那一頁才是沿用者）。
    · 其餘層序 → `ValueError`（⛔ 不猜一階）。
    """
    if n == 5:
        return FIND_N5_TIER
    return components.tier_for_layer(n)


def find_tier_for_block(block_key: str) -> str:
    """block → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**（同 `page_today.tier_for_block`）。"""
    try:
        n = _FIND_BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return find_tier_for_layer(n)


# ── 本頁欠缺的兩條欄數 CSS（客戶 2026-09-22【拍板 1：CSS 走 (甲)】）──────────
#
# 🔴 **就地揭露見 `FIND_GRID_CSS_DISCLOSURE` / `…_WHY`（兩句都畫在本頁最上方）。**
# ⛔ **不碰任何底線私有符號**：`markup._grid_rules` / `_breakpoint_rules` /
#    `_block_cols_class` / `_grid_template` 一個都不呼叫；欄數一律走公開 API
#    `components.resolve_cols()`，斷點一律走 `components.BREAKPOINTS`。
#: 本頁用到、但**契約層沒有產 CSS** 的欄數組合（**推導，⛔ 不手寫清單**）。
#: `page_today.BLOCK_COLS` 日後若自己補上 `(3,3,1)`，這裡就自動少一條，⛔ 不會重複宣告。
_FIND_COLS_NEEDING_CSS: tuple[tuple[int, int, int], ...] = tuple(sorted(
    set(FIND_BLOCK_COLS.values()) - set(page_today.BLOCK_COLS.values())
))


def _find_cols_class(cols: tuple[int, int, int]) -> str:
    """`(3,3,1)` → `g-3-3-1`。

    ⚠️ **這就是被複製的「形狀」之一** —— 命名規則與 `markup._block_cols_class` 相同，
    但那是私有函式（⛔ 不得呼叫）⇒ 這裡另寫一份。見 `FIND_GRID_CSS_DISCLOSURE_WHY`。
    """
    return "g-" + "-".join(str(int(c)) for c in cols)


def _find_grid_template(n_cols: int) -> str:
    """欄數 → `grid-template-columns` 宣告。⚠️ 同上，形狀複製自 `markup._grid_template`。"""
    return f"grid-template-columns:repeat({int(n_cols)},minmax(0,1fr))"


def find_grid_css() -> str:
    """補上 `.g-3-3-1` / `.g-2-1-1`（**只補契約層沒產的那幾條**）。

    三段欄數**全部顯式寫出來**（沿用 `markup._breakpoint_rules` 的紀律）：
    桌機走基準規則、平板與手機各走一個 `@media (max-width:…)`。
    ⚠️ 順序**先 880 後 640** —— 640 也命中 `max-width:880px`，後者必須寫在後面才蓋得過。
    ⚠️ **⛔ 不新增第三個斷點**：兩個 `max-width` 的值直接取自 `components.BREAKPOINTS`，
       與 `page_css()` 產的那兩個**是同兩個數**（本檔⛔ 沒有寫死 640／880）。
    """
    bp = components.BREAKPOINTS
    if not _FIND_COLS_NEEDING_CSS:
        # 契約層已經自己產齊了 ⇒ 本函式該退場（⛔ 不留一段沒有對應實體的死 CSS）。
        return ("/* ══ 5. 「🔍 找標的」頁的欄數 CSS：契約層已自行涵蓋，本輪⛔ 無需補 ══ */")
    rules = [
        "/* ══ 5. 「🔍 找標的」頁欠缺的欄數規則（客戶 2026-09-22 拍板 1，走作法(甲)）══ */",
        "/*    ⚠️ 規則的**形狀**在此被複製了一份 ⇒ 第二個真相源（就地揭露畫在該頁最上方）。 */",
        "/*    ⛔ 數字沒有第二份：欄數走 components.resolve_cols()、斷點走 components.BREAKPOINTS。 */",
        "/*    ⛔ 不呼叫 markup 的任何底線私有函式（V-PICKER-PRIV-1 是本 repo 登記在案的違憲）。 */",
    ]
    for cols in _FIND_COLS_NEEDING_CSS:
        n = components.resolve_cols(cols, bp["desktop_min_px"])
        rules.append(f".{_find_cols_class(cols)}{{{_find_grid_template(n)}}}")
    for max_px in (bp["tablet_max_px"], bp["mobile_max_px"]):
        inner = "".join(
            f".{_find_cols_class(cols)}{{{_find_grid_template(components.resolve_cols(cols, max_px))}}}"
            for cols in _FIND_COLS_NEEDING_CSS
        )
        rules.append(f"@media (max-width:{int(max_px)}px){{{inner}}}")
    return "\n".join(rules)


# ── 代理：把 `markup.page_today` **暫時**換成本頁的版面契約 ──────────────────
#: 作法、三條紀律與「為何非代理不可」**與 `_WHY_CONTRACT` 完全相同**（見該處長註，⛔ 不重抄）。
#: ⚠️ 名單由同一個 AST 掃描把關（`_markup_page_today_names()`）——
#:    本組實跑結果：`markup` 只讀 7 個名字，與「📖 憑什麼」頁**同一組，一個都不用加**。
_FIND_CONTRACT = types.SimpleNamespace(
    BLOCK_COLS=FIND_BLOCK_COLS,
    LAYER_GRID_COLS={},
    BADGES_ON_PAGE=FIND_BADGES_ON_PAGE,
    BADGES_NOT_ON_PAGE=FIND_BADGES_NOT_ON_PAGE,
    tier_for_block=find_tier_for_block,
    card_value_text=page_today.card_value_text,
    card_level_text=page_today.card_level_text,
)


@contextlib.contextmanager
def find_page_contract() -> Iterator[None]:
    """`with` 期間 `markup` 走「🔍 找標的」的版面查表；離開時**一定**還原。

    三道 assert 與 `why_page_contract()` 同構（⛔ 不是「應該可以」）。
    """
    needed = _markup_page_today_names()
    missing = needed - set(vars(_FIND_CONTRACT))
    assert not missing, (
        f"代理少了 markup 會讀的名字：{sorted(missing)} —— "
        "markup.py 多讀了東西而本檔的代理沒跟上。"
        "⛔ 不得為了跑得動就隨便補一個值（那會畫出一個編出來的版面，違 CLAUDE.md §1）。"
    )
    original = markup.page_today
    assert original is page_today, (
        "進場時 markup.page_today 已經不是原物件 —— 上一次替換忘了還原")
    markup.page_today = _FIND_CONTRACT
    try:
        yield
    finally:
        markup.page_today = original
    assert markup.page_today is page_today, "還原失敗：markup.page_today 不是原物件"


FIND_LAYER_NOTE: Mapping[int, str] = {
    0: "兩塊的 leaf 在線框是 null ＝ 葉外 chrome，畫在分頁列之上、兩葉共用。"
       "⚠️ 規格 ⑤ 反例自檢 A 末條逐字：find.statusbar 與 chrome.asof 兩塊**本頁皆無實作**"
       "⇒ 失敗時無可顯示；⛔ 不得用總覽卡的紅態冒充一條不存在的狀態列。"
       "⚠️ 在這份 HTML 原型裡，時點列的**實體**畫在五頁共用的外殼上（頁標題下方第一行），"
       "本層畫的是它的**版面登記**，⛔ 不是第二份 chrome；頂部狀態列的實體本原型**沒有做**。"
       "⚠️ 線框 find.statusbar 的 src 指到的那一行，規格 ⑤ 實測是 _load_regime（空頭濾網），"
       "⛔ 不是狀態列本身 —— 這是已登記的兩個 src 內容漂移之一（見缺口 F16）。",
    1: "t1 是四階裡唯一 2px 框線、內距最大的一階（手機 ≤640 另有一組覆寫內距，四階中也只有 t1 有）。"
       "⭐ **本頁的主 CTA「🎯 開始選股」就住在這一層**（線框 mainCTA.label 逐字）——"
       "客戶 2026-09-22 拍板逐字：主 CTA 不是「全站唯一」，是「**每頁首屏唯一**」，"
       "而 FIND 的這一顆就是它的每頁唯一主 CTA。規格 ① 另逐字：form 內只有這一顆、住預設葉 l1。"
       "⚠️ 三塊的 cols 是本頁四種欄數裡**最複雜的一組**：3/2/1、3/3/1、1/1/1 各一。"
       "其中 3/3/1 是契約層**沒有產 CSS** 的一條，由本產生器補（見本頁最上方的就地揭露）。"
       "⚠️ 中間那塊（情境快選）本輪**沒有卡、沒有徽章**，理由就地寫在該塊位置上。",
    2: "只有一塊，1/1/1。本層畫**兩張卡**：冷啟動 #3 與上游失敗 #6 ——"
       "⛔ 不是挑好看的，兩張都是規格 ⑤ 點名的：⑤B 逐字「冷啟動（還沒點「🎯 開始選股」）："
       "一律 #3 ⬜ 尚未載入 ＋ 灰色說明，⛔ 不得畫成紅色錯誤」；"
       "⑤A 逐字「n2 總覽卡：#6 🔴 取得失敗，大字區留白，⛔ 不得顯示 0 或上一輪殘值」。"
       "⚠️ 大字區留白**不是漏畫**：是 page_today.card_value_text() 依狀態擦掉的。",
    3: "三塊全 1/1/1。⚠️ 規格 ⑥ 逐字：結果表的欄位是**勾選決定的動態欄**、因子值是"
       "百分位 0–100 且 1 位小數，**無殖利率欄** —— 線框畫的固定 6 欄原始值模型"
       "已由總管判定為「設計變更（線框待改）」，且客戶 2026-09-16 裁示「結果表原始值欄：維持不要」。"
       "⚠️ 中間那塊（入選理由）本輪**沒有卡、沒有徽章**，理由就地寫在該塊位置上。"
       "⚠️ CSV 那塊畫的是 empty 態：規格 ⑤A 逐字「0 列也是一個結果」"
       "⇒ 鈕**停用但不隱藏**；現行實作早退會讓它一起消失，屬實作待修（缺口 F10）。",
    4: "t4 是四階裡唯一 dashed 的一階，且本層**只有一塊**、單獨成層 ——"
       "這一點是總管 2026-09-16 推翻「結果表要留原始值欄」的決定性依據："
       "三語彙的載體在 n4，與 n3 的結果表**不同層、不同 block**。"
       "⭐ 本塊畫的是 #7 缺漏，那是客戶 2026-09-16 裁示的**現行落地態**，逐字："
       "「本益比兩種「沒有」：UI 層先誠實顯示「本機分不出，需 L1 補旗標」。"
       "L1 修改列為獨立任務，等 UI 全部做完再評估解凍。不要假裝做得到。」"
       "⛔ 在 D-08 修完之前不得把 PE≤0 與 NaN 畫成兩種不同符號（見缺口 F8）。",
    5: "葉2 板塊地圖，四塊：1/1/1、2/1/1、2/1/1、1/1/1。兩個 2/1/1 同樣是契約層**沒有產 CSS** "
       "的一條，由本產生器補。密度 t2 是**規格 ① 表自己新訂的**（超出 n1~n4 自動對映時取「核心卡」），"
       "⛔ 不是契約層算出來的（components.tier_for_layer 只認 0 與 1~4）—— 見缺口 F14。"
       "⚠️ 本頁是 n5 新訂的**原創處**：「📖 憑什麼」頁 ② 表自己逐字寫「沿用 UI_PAGE_FIND 對 n5 的新訂」"
       "⇒ ⛔ 不得把本頁這一格寫成「借那一頁的」。"
       "⚠️ 規格 ① 另逐字：n5 的 2/1/1 在實作端**只落地一半**（兩張卡並列，兩張圖上下堆疊）。"
       "⚠️ 兩張圖**各自判態**（線框層標逐字），所以這裡一張畫 #3 idle、一張畫 #4 degraded ——"
       "#4 是規格 ② 處置 5 逐字「現僅葉2 可達」的那一顆，葉1 待補。",
}

#: 兩塊**本輪⛔ 不掛卡、⛔ 不掛徽章**的 block（規格 ② 處置 2(a)）。
#: 🔴 沿用「📖 憑什麼」頁 `why.edu.table.nolevel` 的同一招：**畫出版面位置，不畫徽章**。
#:
#: ⭐ **2026-09-22 客戶就這兩塊親自裁示（逐字，⛔ 不是本組判讀）**：
#:    「維持「畫框不畫卡」。理由：兩種讀法都成立，畫框保留位置才看得出規格要它們消失。
#:      加一行說明：「規格說此塊現階段不存在，線框有登記；等規格澄清後再決定填什麼」」
#:    ⇒ 上一輪登記的缺口 **F3**（「本組處置、⛔ 不自行裁決」）**這一半已由客戶拍板** ——
#:      **處置本身維持原樣、一個字都沒有改**，客戶要的**只有那一行說明**，
#:      下面兩塊各補在該塊揭露的**末尾**（逐字，⛔ 不改寫、⛔ 不「優化」）。
#:    ⚠️ F3 那一條**⛔ 不刪、⛔ 不標成已解決**：它記錄的是「當時本組無法自行排除兩種可能」
#:      這個**事實**，而那正是客戶得以拍板的前提（CLAUDE.md §8.2.A.3 第 3 點：
#:      曾判定的東西被推翻要登記，⛔ 不准靜默刪掉當沒發生過）。
#: ⚠️ **F3 的內文本輪⛔ 一個字都沒有動**：客戶本輪的指示逐字只到「在那兩個框內加一行說明」，
#:    ⛔ 沒有授權改附錄 —— 改了就是自行擴大範圍（CLAUDE.md §8.4 step 4：範圍問客戶）。
#:    ⇒ 現況是「兩塊的揭露已載明客戶裁示，F3 仍寫著當時未決」——
#:      **這個不一致是本組刻意留下的，已在交付回報中列為建議事項，⛔ 不自行處理。**

#: 客戶 2026-09-22 指定要加的那一行（**逐字**，⛔ 不得改寫）。
FIND_NO_CARD_CLARIFY_LINE = (
    "規格說此塊現階段不存在，線框有登記；等規格澄清後再決定填什麼"
)

FIND_NO_CARD_DISCLOSURE: Mapping[str, str] = {
    "find.scenario_quickpick": (
        "這一塊本輪⛔ 沒有卡、⛔ 沒有徽章，是刻意的。"
        "線框 src 為 null；線框 unwired 那一格自己逐字寫「這一格就是現在的真實狀態："
        "這三顆鈕在現行畫面上不存在。線框畫的是提案，還沒有做」。"
        "規格 ② 處置 2 逐字：「find.scenario_quickpick／find.pick_reason 線框 src:null、"
        "畫面上整塊不存在 ⇒ 不畫，⛔ 不得用 #5 冒充「有這塊但沒接線」」。"
        "⇒ 本輪畫出它的**版面位置**（層 n1／欄數 3/3/1／密度 t1 都在），但⛔ 不掛任何徽章。"
        "⚠️ 這與客戶本輪「6 層 14 block」的要求有交集，⛔ 本組不自行裁決 —— 見缺口 F3。"
        "／／⭐ 客戶 2026-09-22 就此塊親自裁示（逐字）：「維持「畫框不畫卡」。"
        "理由：兩種讀法都成立，畫框保留位置才看得出規格要它們消失。加一行說明：」"
        "⇒ " + FIND_NO_CARD_CLARIFY_LINE
    ),
    "find.pick_reason": (
        "這一塊本輪⛔ 沒有卡、⛔ 沒有徽章，是刻意的。"
        "線框 src 為 null；線框 live 那一格自己逐字開頭就寫「這一塊還是提案，現在還沒有 ——"
        "現行畫面點列不會展開」。規格 ② 處置 2 把它與上一塊列在同一條，處置相同。"
        "⇒ 本輪畫出它的**版面位置**（層 n3／欄數 1/1/1／密度 t3 都在），但⛔ 不掛任何徽章。"
        "⚠️ ⛔ 不得拿 #5 冒充，也⛔ 不得因為「客戶要 14 block」就給它一顆看起來正常的 #1 ——"
        "那會把「這塊還沒做」畫成「做好了」（CLAUDE.md §1）。見缺口 F3。"
        "／／⭐ 客戶 2026-09-22 就此塊親自裁示（逐字）：「維持「畫框不畫卡」。"
        "理由：兩種讀法都成立，畫框保留位置才看得出規格要它們消失。加一行說明：」"
        "⇒ " + FIND_NO_CARD_CLARIFY_LINE
    ),
}


def build_find_cards() -> dict[str, list[dict]]:
    """每個 block 要畫幾張卡、各是什麼狀態。

    🔴 **狀態⛔ 不是挑好看的**，每一塊都同時過兩道（兩道都是本組 node／grep 實測）：
       ① 線框該塊 `states` 十態格裡**值為 null 的一律不准用**（null ＝ 該情況下結構上不存在）；
       ② 該態對應的徽章必須在 `FIND_BADGES_ON_PAGE` 內（否則 `markup.card_html` 會 fail loud）。
       規格點名了該畫哪一態的（⑤A／⑤B／② 處置 5／④(d)），一律照規格。
    🔴 **每一張渲染得出阿拉伯數字的卡都掛 `("資料來源", DEMO)`**（客戶：示意數字必須標明示意）。
    """
    rb = page_today.resolve_badge

    def demo(*rows: tuple[str, str]) -> tuple[tuple[str, str], ...]:
        return (*rows, ("資料來源", DEMO))

    return {
        # ── n0 葉外 chrome（規格 ⑤A 末條：兩塊本頁皆無實作）────────────────────
        "find.statusbar": [
            {"state": "idle", "title": "（跨頁）頂部狀態列",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "09/13 週五 ✅ 交易日　|　⬜ 總經未評估　|　🔗 尚未綁定 Sheet"),
                 ("那個日期", "線框自註：live／idle 那一行的日期是規格示意值，非實測"),
                 ("本頁實作", "規格 ⑤ 逐字：本頁無實作 ⇒ 失敗時無可顯示"),
                 ("誰定義它", "五頁共用 chrome，狀態定義在頁1 的 today.statusbar，本頁不重新定義"))},
        ],
        "chrome.asof": [
            {"state": "idle", "title": "資料時點揭露列（頁標題下方第一行）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": (
                 ("線框 idle 逐字", "資料時點：尚未載入，本頁沒有任何本輪資料"),
                 ("這份原型", "外殼上那一條畫的正是這一態的逐字，⛔ 一個真時間都沒填"),
                 ("本頁的難處", "一頁之內有三種節奏的時點（收盤日／資料歸屬月／盤後凍結快照），"
                                "線框逐字⛔ 不可合併成一個日期 ⇒ 本頁常態是「最舊～最新」"))},
        ],
        # ── n1 條件表單（主 CTA 住這一層）────────────────────────────────────
        "find.screen_form": [
            {"state": "idle", "title": "葉1 條件表單（三格 ＋ 主 CTA 🎯 開始選股）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "表單永遠可見（它就是灰態的出口），三格顯預設值，submit 可按"),
                 ("規格 ① 逐字", "form 內只有這一顆、住預設葉 l1"),
                 ("主 CTA 範圍詞", "每頁首屏唯一一顆（客戶 2026-09-22 拍板；舊寫法「全站唯一」已改）"),
                 ("⛔ 不得", "用表單本身去表示有沒有選過 —— 還沒選過與已經選過，表單長得一樣"))},
        ],
        # find.scenario_quickpick：⛔ 沒有卡（見 FIND_NO_CARD_DISCLOSURE）
        "find.scenario_quickpick": [],
        "find.wiring_disclosure": [
            {"state": "live", "title": "取數接線揭露（表單下方常駐 caption）",
             "value": None, "level": "🟢 常駐，⛔ 不隨狀態消失", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框十態", "十格全部非 null，九格逐字都是「常駐」"),
                 ("live 那一格", "是 code 端 WIRING_DISCLOSURE 常數的逐字內容"),
                 ("⚠️ 但它是 code 自己的宣稱", "「五個因子都已接線」是一句全稱句，"
                                               "線框自陳沒有逐一驗證五條路徑（CLAUDE.md §-2 規則 6）"))},
        ],
        # ── n2 總覽卡：兩張卡，兩張都是規格點名的（⑤B 冷啟動 ＋ ⑤A 上游全敗）────
        "find.screen_summary": [
            {"state": "idle", "title": "葉1 選股結果 · 總覽卡（冷啟動）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("規格 ⑤B 逐字", "冷啟動一律 #3 ⬜ 尚未載入 ＋ 灰色說明，⛔ 不得畫成紅色錯誤"),
                 ("線框 idle 逐字", "在你送出之前，本頁一次 L3 取數都不會發（沒有人叫過它）"),
                 ("去哪補", "勾好條件後，按「🎯 開始選股」（在表單裡）"))},
            {"state": "error", "title": "葉1 選股結果 · 總覽卡（上游全敗）",
             "value": None, "level": None, "badge_n": rb(state="error"),
             "facts": demo(
                 ("規格 ⑤A 逐字", "#6 🔴 取得失敗，大字區留白，⛔ 不得顯示 0 或上一輪殘值"),
                 ("逐源列出", "aux_errors 逐源列出（存活池／估值／缺貨／RS／跨季／總經位階），"
                              "一源壞⛔ 不染色其餘"),
                 ("⛔ 不得", "對契約漂移給「可以重跑」指引 —— 重按不會好，給錯指引比不給更糟"))},
        ],
        # ── n3 大表＋入選理由＋CSV ─────────────────────────────────────────
        "find.screen_table": [
            {"state": "live", "title": "葉1 選股結果 · 大表（桌機表格／手機卡片流）",
             "value": None, "level": "🟢 這一塊是接上的", "badge_n": rb(state="live"),
             "facts": demo(
                 ("規格 ⑥ 現況", "欄位是勾選決定的動態欄；因子值是百分位 0–100、1 位小數；無殖利率欄"),
                 ("客戶 2026-09-16 裁示逐字", "結果表原始值欄：維持不要"),
                 ("線框待改", "線框畫的固定 6 欄原始值模型已判為設計變更"),
                 ("手機 ≤640", "規格 ③ 末段新訂卡片流；⛔ 本輪不得照現值落地，"
                               "該段自帶一條無障礙阻斷（見缺口 F17）"))},
        ],
        # find.pick_reason：⛔ 沒有卡（見 FIND_NO_CARD_DISCLOSURE）
        "find.pick_reason": [],
        "find.csv": [
            {"state": "empty", "title": "⬇ 下載結果 CSV（form 外）",
             "value": None, "level": None, "badge_n": rb(state="empty"),
             "facts": demo(
                 ("線框 empty 逐字", "停用但不隱藏 ——「我跑過、結果是 0」本身就是一個要留存的結果"),
                 ("實作待修", "現行早退會讓 CSV 跟著消失 ⇒ 0 列／錯誤時鈕應留在畫面上走停用態"),
                 ("⛔ 不得", "在匯出時把 ⚠︎ — 變成空白或 0（線框逐字）"),
                 ("兩處未決", "檔名不含資料歸屬日（實作待修）＋ 鈕字串兩份真相源（待客戶拍板），"
                              "見缺口 F10"))},
        ],
        # ── n4 展開佐證：本益比的兩種「沒有」（客戶 2026-09-16 已裁示現行態）────
        "find.pe_two_kinds": [
            {"state": "missing", "title": "🔴 為什麼有些本益比是空的（PE 兩種「沒有」的分辨）",
             "value": None, "level": None, "badge_n": rb(state="missing"),
             "facts": demo(
                 ("客戶 2026-09-16 裁示逐字", "UI 層先誠實顯示「本機分不出，需 L1 補旗標」。"
                                              "L1 修改列為獨立任務，等 UI 全部做完再評估解凍。"
                                              "不要假裝做得到"),
                 ("線框十態", "十格全部非 null，逐字都是「常駐」—— missing 那格另註「這一態正是它要解釋的」"),
                 ("上畫面的字面", "一律標 ⚠︎ —，並就地說明「這一欄目前分不出兩種「沒有」」"),
                 ("⛔ 使用者看到的字面不得出現", "L1／旗標／D-08 這類內部詞，也不得出現「虧損」"))},
        ],
        # ── n5 葉2 板塊地圖（兩張圖各自判態）──────────────────────────────
        "find.map_cta": [
            {"state": "idle", "title": "葉2 CTA：🗺️ 載入板塊地圖",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "鈕常駐可按；下方兩張圖各自顯示自己的灰態（兩張圖不共用同一段文字）"),
                 ("⛔ 它不是頁主 CTA", "線框自註：form 外、非預設葉 ⇒ 不是頁主 CTA；"
                                       "本頁的主 CTA 是葉1 的「🎯 開始選股」"))},
        ],
        "find.heatmap": [
            {"state": "idle", "title": "葉2 左｜產業漲跌熱力圖",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "⬜ 板塊資料尚未載入"),
                 ("線框給的原因（逐字）", "熱力圖要批次抓數十檔類股代表"),
                 ("去哪補", "點「🗺️ 載入板塊地圖」"),
                 ("線框 degraded 是 null", "本塊結構上就沒有「門檻失準」這一格 ⇒ ⛔ 不得畫 #4"))},
        ],
        "find.sector_flow": [
            {"state": "degraded", "title": "葉2 右｜三大法人資金流向泡泡圖",
             "value": None, "level": None, "badge_n": rb(state="degraded"),
             "facts": demo(
                 ("規格 ② 處置 5 逐字", "#4 degraded：葉1 待補，現僅葉2 可達"),
                 ("線框 degraded 逐字", "快照是舊的 → 就地寫出它為什麼是舊的"
                                        "（來源沒給原因時就寫「上游沒有給原因」）"),
                 ("⛔ 不得", "靜默拿舊快照當今天的值"),
                 ("畫面行為", "degraded ＝ 觀測照出、判決留白 ⇒ 上面那顆等級⛔ 不會畫出來"))},
        ],
        "find.map_scale_disclosure": [
            {"state": "live", "title": "⭐ 葉2 口徑揭露（常駐小字）",
             "value": None, "level": "🟢 常駐", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字", "X＝近 5 日累計淨流入（億）· Y＝動能變化 · 泡泡＝近 20 日淨額規模。"
                                    "面積不等於權重。"),
                 ("線框 idle 逐字", "常駐 —— 你在看圖之前就該知道這張圖在量什麼"),
                 ("線框十態", "十格全部非 null，九格逐字都是「常駐」"))},
        ],
    }


#: 「🔍 找標的」頁**本輪查到的衝突與洞**，逐條登記並**畫在畫面上**（客戶要求 6：就地標明、
#: 寫進附錄、⛔ 不自行裁決）。🔴 每一條同樣是 **⚠️ 單組／兩組調查結論，未經第三方驗**。
FIND_SPEC_GAPS: tuple[tuple[str, str, str], ...] = (
    (
        "F1",
        "🔴 主 CTA 的範圍詞「全站唯一」**不只四個落點** —— 本組實測至少 **8 處**，"
        "其中 **3 處到目前為止仍未同步**（且**全部不在本組的檔案邊界內**）"
        "⇒ ⛔ 不得宣稱「已全部同步」。",
        "客戶 2026-09-22 拍板逐字：「【拍板 2：主 CTA】不是「全站唯一」，是「每頁首屏唯一」。"
        "⇒ 產生器裡那 2 處文案改掉。FIND 的「🎯 開始選股」就是它的每頁唯一主 CTA」。"
        "／／**落點普查（本組 grep 實測，量測日 2026-09-22；⚠️ 單組、⛔ 未窮舉全 repo，只掃了 "
        "src/ui_v2/ ＋ docs/v2/spec/UI_COMPONENTS.md ＋ 本產生器）**："
        "已同步 5 處 —— (1) docs/v2/spec/UI_COMPONENTS.md §3 按鈕表該列標題；"
        "(2) src/ui_v2/page_today.py 第三層註解；(3) 同檔 MAIN_CTA 的鍵"
        "（unique_per_site → unique_per_first_screen）；(4)(5) 本產生器兩處"
        "（_LAYER_NOTE[3] ＋ today.actions 卡的 facts）。"
        "／／🔴 **仍未同步 3 處（本組本輪新發現，⛔ 不在本組檔案邊界內、本組一個字都沒動）**："
        "(6) src/ui_v2/render.py 的 _MAIN_CTA_LAYERS 註解「UI_PAGE_TODAY ①：全站唯一一顆，掛第三層」；"
        "(7) 同檔 _render_main_cta() 的 docstring「UI_COMPONENTS §3「主 CTA（全站唯一一顆）」」；"
        "(8) src/ui_v2/components.py 的 BUTTONS 上方註解「UI_COMPONENTS.md §3 按鈕表"
        "「主 CTA（全站唯一一顆）」列」。"
        "／／**本輪本組只動了 (4)(5)**。(1)(2)(3) 由另一組處理 —— 本組**只查證到"
        "「git log 有一筆訊息寫著鍵名同步改名、且 diff 觸及那三個檔」這件事**，"
        "**⛔ 沒有逐字複驗它們的內容** ⇒ 依 CLAUDE.md §-2 規則 6，"
        "⛔ 不得寫成「落點已全部同步」。"
        "／／**規格端早就有一條否證**：UI_PAGE_FIND ① 逐字「2026-09-16 修正（WJ）："
        "原寫「全站唯一一顆」主 CTA 不成立 —— 葉2 那顆同為 type=primary…"
        "可宣稱的是客戶指令原意 ——「選股主 CTA 只有一顆、且在預設葉 l1 可見」；⛔ 不得寫成全站唯一」。"
        "⇒ 客戶本輪的拍板與這條規格端修正**同向**。"
        "／／⚠️ 本產生器**不讀** MAIN_CTA 的那個鍵（只讀 MAIN_CTA['label']，本組 grep 實測）"
        "⇒ 鍵名改名⛔ 不影響本產生器；本檔也因此**沒有**跟著改任何鍵名。",
    ),
    (
        "F2",
        FIND_GRID_CSS_DISCLOSURE,
        FIND_GRID_CSS_DISCLOSURE_WHY
        + "／／來歷：客戶 2026-09-22 拍板逐字「【拍板 1：CSS 走 (甲)】在產生器補 .g-3-3-1 與 "
          ".g-2-1-1 兩條 rule。值用 components.resolve_cols() ＋ BREAKPOINTS 算。"
          "就地揭露「規則形狀複製了一份」」⇒ 這是**已拍板的作法**，⛔ 不是偷懶，"
          "但它的後果必須看得見，所以有這一條。",
    ),
    (
        "F3",
        "⭐ **本輪最主要的一處衝突**：規格 ② 處置 2(a) 要「不畫」的兩塊，"
        "與客戶本輪「6 層 14 block」的要求有交集 ⇒ 本組**處置後登記，⛔ 不自行裁決**。",
        "衝突長這樣：客戶本輪逐字「2. 6 層 14 block」；而 UI_PAGE_FIND ② 處置 2 逐字"
        "「(a) find.scenario_quickpick／find.pick_reason 線框 src:null、畫面上整塊不存在 ⇒ 不畫，"
        "⛔ 不得用 #5 冒充「有這塊但沒接線」」。"
        "／／**本組的處置（⛔ 這是處置，不是裁決）**：沿用「📖 憑什麼」頁 why.edu.table.nolevel "
        "的同一招 —— **畫出那兩塊的版面位置（層／欄數 class／密度 class 都在），"
        "但⛔ 不畫卡、⛔ 不畫任何徽章**，並在該位置就地寫明理由。"
        "／／**理由**：客戶要的「14 block」是**版面**（哪一塊在第幾層、幾欄、哪一階密度），"
        "規格禁的是**冒充狀態**（給一個它在現行畫面上沒有的徽章）—— 兩者的交集只在「要不要掛徽章」，"
        "所以只讓徽章退場，版面照畫。"
        "／／⚠️ **本組可能判錯的地方，據實寫出來**：若客戶本意是「14 block 每一塊都要有卡」，"
        "那本組的處置就不足；若客戶本意是「整塊連框都不要畫」，那本組畫了版面位置就是超過。"
        "**兩種可能本組都無法自行排除** ⇒ 依客戶要求 6，登記、⛔ 不裁決。",
    ),
    (
        "F4",
        "#2 載入中：**實作待補**（⛔ 不是規格待決）⇒ 本頁⛔ 不畫 #2。",
        "UI_PAGE_FIND ② 處置 1 逐字：「#2 loading：實作待補（不是規格待決）。"
        "分類器有能力產生（第 3 份已證），缺的是 caller —— 本頁 0 處傳 in_flight=。"
        "處置：取數段包 st.spinner，並把 in_flight=True 顯式傳進上列三個呼叫點。"
        "⛔ 在補上之前不得拿 #3「尚未載入」冒充載入中」。"
        "⇒ 本頁的代理把 2 放進 BADGES_NOT_ON_PAGE，任何一次誤畫都會在產生時變成 ValueError。"
        "⚠️ 線框十態格裡 loading 全部 14 塊都非 null ⇒ **線框有、實作沒有**，這是本頁"
        "「線框 states 非 null」與「實作畫得出來」兩道把關**結論不同**的一格。",
    ),
    (
        "F5",
        "#7／#8：**規格待接線**（該份自稱這是它的主體）⇒ 本頁只畫 #7，⛔ 不畫 #8。",
        "UI_PAGE_FIND ② 處置 3 逐字：「#7／#8：規格待接線（本份的主體）。"
        "實作只有單一 UI_EMPTY、glyph ▨「無資料」，未依 miss_reason 拆二。"
        "處置：依 ③ 的對照表拆 ⚠︎ —／N/A；⛔ 不得為了對齊線框鍵數新造第 11 種徽章；"
        "⛔ 不得把 missing 畫成 #8（#8 重跑無效，畫錯＝給錯指引）」。"
        "／／⇒ 本頁畫 #7（現行那顆單一空值就是它），⛔ 不畫 #8。"
        "⚠️ 本頁**也⛔ 沒有出現 ▨ 符號**：徽章符號一律由 components.BADGES 產出，本檔⛔ 沒有手打任何一顆。",
    ),
    (
        "F6",
        "🔴 #9 部分計入：**分母對不上表上的列數**，規格明文「擇一處置，⛔ 不得直接貼」"
        "⇒ 本頁⛔ 不畫 #9、⛔ 不寫任何 N／M。",
        "UI_PAGE_FIND ② 處置 4 逐字：「本頁 L3 已經算出分母 —— _cov_bits＝…（現只拼進 note 字串）"
        "⇒ 接到欄標題層即可畫 #9 ◧ N／M，這是接線工作、不是缺資料」，"
        "但同段 🔴 逐字：「分母對不上表上的列數…_cov_bits 的分母是 len(ids)，而 ids ＝存活池全體；"
        "表上只有 ranked[:top_n] ⇒ 直接把 N／M 貼到欄標題，使用者會讀成「這 20 列裡有 N 列算得出來」，"
        "實際講的是「存活池 M 檔裡有 N 檔算得出來」—— 兩個母體差一個數量級，"
        "⛔ 這正是 §1「錯誤的數字比沒有數字更危險」。處置（擇一，⛔ 不得直接貼）："
        "(a) 另算表上列的覆蓋數當 N／M，或 (b) 保留存活池分母但在 tooltip 寫死母體」。"
        "⇒ **擇一由誰決定，規格沒說，本組⛔ 不代決**；在決定之前本頁一個 N／M 都不寫。",
    ),
    (
        "F7",
        "#4 門檻已失準：**葉1 待補**，現僅葉2 可達 ⇒ 本頁的 #4 只畫在葉2。",
        "UI_PAGE_FIND ② 處置 5 逐字：「#4 degraded：葉1 待補。現僅葉2 可達（:1329／:1389）。"
        "線框 screen_table.degraded 要求 🟠 標在該欄標題旁（不是逐格）＋ 就地寫"
        "「請不要把它當入選理由讀」→ 待接」。"
        "⇒ 本頁把 #4 畫在 find.sector_flow（葉2）；"
        "⚠️ **⛔ 不畫在 find.heatmap**：該塊線框的 degraded 那一格是 null（結構上不存在），"
        "兩道把關任一不過就不畫。",
    ),
    (
        "F8",
        "🔴 `D-08` 待裁：`MISS_CONTRACT_DRIFT` 被升成 #6，與規格 ④(a)「逾 sanity → #7」對不上。",
        "UI_PAGE_FIND ④(c) 逐字：「MISS_CONTRACT_DRIFT 落在 FAILED_REASONS 內"
        "（shared/ui_state.py）⇒ classify_ui_state 會把它升成 #6 🔴（同 ② error 列），"
        "與 (a) 寫的「逾 sanity → ⚠︎ —」（#7）以及 INDICATOR_SPEC「逾界 → 缺漏」對不上。"
        "⛔ 不得就地改 FAILED_REASONS（那會動到全站每一盞燈）⇒ 列為 D-08 待裁」。"
        "／／同節 (d) 是**客戶 2026-09-16 已裁示的現行落地態**，逐字："
        "「本益比兩種「沒有」：UI 層先誠實顯示「本機分不出，需 L1 補旗標」。"
        "L1 修改列為獨立任務，等 UI 全部做完再評估解凍。不要假裝做得到」。"
        "⇒ 本頁 n4 照 (d) 畫成 #7 ＋ 就地誠實說明，⛔ 不畫成分得開的樣子。"
        "⚠️ (c) 另有一條承重警告（線框逐字）：L1 補旗標與 pe_low 排序端擋非正值**必須同一批落地**，"
        "否則虧損股會被排成全市場最便宜。⚠️ D-08 的排程狀態⛔ 不得寫成「已排程」或「已核准」。",
    ),
    (
        "F9",
        "殖利率欄：**2026-09-16 已降級為「待覆核的開放項」**，⇒ ⛔ 不得再寫成「線框待刪該欄」。",
        "UI_PAGE_FIND ⑥ 第一列逐字：「殖利率欄：⚠️ 2026-09-16 降級為「待覆核的開放項」，本份不下結論（WJ）"
        "—— 原寫「不加」的依據是「來源端『沒配息』與『還沒公告』分不開 ⇒ 畫不出三語彙」，"
        "但那正是 ④ 對本益比認定的同型缺陷，而 ④ 的處置是保留該塊 ＋ 誠實寫「目前分不出這兩種」…"
        "同一條依據不得在 ④ 判「保留」、在此判「刪欄」…依 §-2 規則 6 不硬掰，降為開放項」。"
        "／／⇒ 本頁**照實作現況畫（無殖利率欄）**，但⛔ 不宣稱「該欄已刪」或「線框待刪」。"
        "⚠️ 規格同列另註：支撐該判斷的來源端數字（410 檔中 99 檔為空 ≈24%）是**轉錄**，"
        "**無任何一組獨立查證過來源端** ⇒ ⛔ 不得引用為事實。",
    ),
    (
        "F10",
        "CSV：**檔名＝實作待修；鈕字串＝待客戶拍板（兩份真相源）** ⇒ 本頁⛔ 不代決字串。",
        "UI_PAGE_FIND ⑥ 第二列逐字：「檔名寫死 screener_result.csv，不含資料歸屬日 ⇒ 連兩天下載"
        "得到兩個同名檔；鈕字串 production／線框 states.live 為「💾 下載選股結果 CSV」…"
        "檔名＝實作待修；鈕字串＝待客戶拍板（兩份真相源）…鈕字串推薦取 production 那串、線框改齊"
        "（它已是使用者看過的字面）；⛔ 不得兩邊各留一份」。"
        "／／⇒ 本頁的卡標用**線框的 name 逐字**（⬇ 下載結果 CSV），facts 裡同時寫出兩份都存在這件事，"
        "⛔ 不替客戶挑一個。⚠️ 檔名規則編號 G-24 **不在** INDICATOR_SPEC §5／DECISION_RULES §8，"
        "出處是 DRAFT_GAP_AUDIT.md ＋ S1-3B Part 6.3（規格逐字，本組未再獨立查證）。",
    ),
    (
        "F11",
        "⑤C 兩個原先漏掉的情境：**(1) 改了勾選但沒按送出 (2) 軌 A 會連帶汙染 CSV** ——"
        "兩條都**未落地**，本頁只登記、⛔ 不畫成已完成。",
        "UI_PAGE_FIND ⑤C 逐字（兩項）："
        "(1)「「改了勾選但沒按 🎯 開始選股」在 ② 的十鍵裡沒有對應狀態格…"
        "使用者眼前是「條件 ≠ 表上結果」。它不是 idle（已經跑過）、不是 degraded、更不是 error。"
        "處置：⛔ 不得新造第 11 種徽章、⛔ 不得把表清掉（表上的數字仍是真的，只是舊的）⇒ 維持 #1，"
        "另在總覽卡就地加一行灰色 caption「條件已改，尚未套用 —— 請按 🎯 開始選股」。"
        "⚠️ 依 §1.A 第 4 點，該提示必須是灰色說明、⛔ 不得畫成紅色錯誤」；"
        "(2)「③ 軌 A 會連帶讓下載的 CSV 從數值退化成字串…CSV 必須另備一份 df：數值欄保留數值、"
        "缺值原因另立一欄承載；⛔ 不得直接 to_csv 那份已格式化的表。本項必須與軌 A 同一批落地，"
        "⛔ 不得延後（延後＝使用者拿到一份看起來正常、卻算不了的檔案）」。",
    ),
    (
        "F12",
        "#10 ◆：規格 ② 明文**本頁不畫** ⇒ 照辦，且⛔ 不得併進 #8。",
        "UI_PAGE_FIND ② 表末列逐字：「（線框無此鍵）／emits_level=False／#10／"
        "**不適用**：本頁 emits_level 0 命中 ⇒ **不畫 #10**；⛔ 不得併進 #8」。"
        "⇒ 本頁的代理把 10 放進 BADGES_NOT_ON_PAGE；另有一道全檔守衛"
        "（class 屬性裡的 token 掃描）確認產物裡⛔ 沒有任何 bdg-10。"
        "⚠️ 這與「📖 憑什麼」頁的 #10 是**兩件不同的事**：那一頁是「有適用對象但尚未徽章化」"
        "（W5），本頁是「**根本沒有適用對象**」—— ⛔ 不得混為一談。",
    ),
    (
        "F13",
        "⚠️ 本頁「會畫哪幾顆徽章」是**本組自規格 ② 表推導的單組判定**，"
        "規格**沒有**像「📖 憑什麼」頁那樣的總結句。",
        "對照：UI_PAGE_WHY ④ 末句有一句逐字「⇒ 會出現在畫面上的是 6 態：#1／#3／#4／#5／#6／#7」，"
        "那一頁的可畫集合是**照抄規格**。UI_PAGE_FIND ② **沒有**對應的句子"
        "（本組通讀六節，0 命中）⇒ 本組只能逐列從「實作」欄推導："
        "✅ 三列取（#1 live／#3 idle／#6 error）、⚠️ 兩列取（#4 僅葉2 可達／#7 現行單一 UI_EMPTY）、"
        "❌ 四列不取（#2／#5／#8／#9）、#10 該表明文不適用。"
        "⇒ FIND_BADGES_ON_PAGE ＝ {1,3,4,6,7}。"
        "⚠️ 依 CLAUDE.md §-2 規則 6，這是**單組判定、未經第二組複驗**，"
        "⛔ 不得被引用為「規格就是這樣寫的」。若第二組判讀不同（例如認為 #7 的 ⚠️ 也算未落地），"
        "本頁的徽章集合要跟著改。",
    ),
    (
        "F14",
        "n5（葉2）超出契約層的層序對映 ⇒ 它的卡密度 t2 只能寫在本產生器裡。"
        "⭐ **本頁是這條新訂的原創處，⛔ 不是沿用者。**",
        "實測：components.tier_for_layer(5) 拋 ValueError「未知的層序 5：只有 0（葉外 chrome）"
        "與 1~4 四層」。而 UI_PAGE_FIND ① 表「葉2／n5」列逐字給了 t2，並自陳"
        "「WH 本組新訂：n5 超出 n1~n4 自動對映，取「核心卡」」。"
        "／／⭐ **方向要講清楚**：UI_PAGE_WHY ② 表的「葉3／n5」列**自己逐字寫**"
        "「沿用 UI_PAGE_FIND 對 n5 的新訂…⛔ 非本組發明」"
        "⇒ **FIND 是原創處、WHY 是沿用者**；⛔ 不得把本頁這一格寫成「借「📖 憑什麼」頁的」。"
        "／／真正的解是契約層補上 n5 的對映，但那要動 src/ui_v2/components.py ⇒ ⛔ 不在本輪授權範圍。"
        "n0~n4 則一律走 components.tier_for_layer（本產生器結尾逐一 assert 相等），"
        "⛔ 不在本檔手抄第二份對映表。",
    ),
    (
        "F15",
        "cols 的語意本身未決（＝「🚦 今天」頁登記的 U-2）；另外 n1 的 3/2/1 在 Streamlit 端"
        "**tablet=2 未落地** ⇒ 兩條都照實登記，⛔ 不代為裁決。",
        "(1) cols 語意：契約層把 cols 讀成「卡內網格一列幾格」（markup.grid_html 的 .g-* class），"
        "但一個 block 只有一張卡時，「3/3/1」也可以被讀成「這三塊並排」。"
        "「🚦 今天」頁的同一個問題已拆為 U-2 並記為「仍未判定」⇒ 本頁沿用同一處置："
        "照現行契約層語意原樣渲染，⛔ 不裁決。"
        "(2) UI_PAGE_FIND ① 逐字：「n1 的 3/2/1 只有 tablet=2 未落地…"
        "Streamlit 自身帶一條寫死的 columns:640px 斷點…⇒ ≤640 本來就堆成 1 欄（phone=1 已落地），"
        "641–880 仍恆 3 欄（tablet=2 → 實作待修）。⛔ 該斷點值寫死在 bundle 內，"
        "本專案改不到、也不得假設它跨版本不變」；同節另逐字「n5 的 2/1/1 只落地一半："
        "實作兩張卡並列，兩張圖上下堆疊」。"
        "⚠️ **這份 HTML 原型的 CSS 本身是對的**：.g-3-2-1／.g-3-3-1／.g-2-1-1 三段實測分別為"
        "3/2/1、3/3/1、2/1/1（產生器結尾有守衛，從 CSS 文字用 regex 量）。"
        "⚠️ 但**這份原型與 Streamlit 實作不是同一套 CSS** ⇒ 量了這份也⛔ 不能拿去當 Streamlit 端的答案。",
    ),
    (
        "F16",
        "線框 `src` 有**兩例內容漂移**（已知），其餘 block 的 `src` 內容**無人逐一比對過**。",
        "UI_PAGE_FIND 檔尾「WH 本組實查」列逐字收窄：「查到的是「每個 block 的 src 字串是什麼」，"
        "不是「每個 src 指的那一行內容對不對」；已知內容漂移兩例"
        "（find.statusbar → :796 實為 _load_regime；find.screen_table → :1163 實為 _fmt_count），"
        "其餘 block 的 src 內容無人逐一比對 ⇒ ⛔ 不得讀成「每個 src 都對過」」。"
        "⇒ 本檔 FIND_LAYOUT 的 src 欄一律只寫**規格章節名 ＋ 線框 block key**，"
        "**⛔ 一個行號都沒寫**（CLAUDE.md §8.2.A.0 規則 1：行號是保證會過期的資訊）。",
    ),
    (
        "F17",
        "手機 ≤640 卡片流規格**自帶一條無障礙阻斷** ⇒ ⛔ 不得照現值落地。",
        "UI_PAGE_FIND ③ 末段逐字：「⛔ 無障礙阻斷…上句 key 用的 --ink-3 9.5px 在卡面上"
        "現行未達 WCAG AA 4.5:1 —— dark #73838f on --panel ＝ 4.35:1、on --panel-2 ＝ 4.01:1；"
        "light #626f7a on --panel ＝ 5.11:1（PASS）、on --panel-2 ＝ 4.36:1 ⇒ 四種組合三種不及格…"
        "⇒ ⛔ 本段不得照現值落地，須等 --ink-3 修正後才做」；同段另註「token 修正不在本檔範圍」。"
        "⇒ 本原型**⛔ 沒有實作手機卡片流**（本頁的手機版就是欄數塌成 1 欄），"
        "n3 那張卡的 facts 已就地標明這條相依。"
        "⚠️ 規格自註該組對比數字是**總管實算、WH 未重算、僅轉錄** ⇒ ⛔ 不得當成本組量過。",
    ),
)

#: **允許清單**：規格／線框**逐字**名稱裡本來就帶「為…什麼」三字的地方（⛔ 不是頁名）。
#: 🔴 存在理由與處置方式**完全沿用** `WHY_VERBATIM_ALLOW_WEISHENME`（見該處長註）。
#: ⚠️ 每一條都必須是**線框／規格的逐字**，⛔ 不得拿本檔自己的散文往這裡塞。
FIND_VERBATIM_ALLOW_WEISHENME: tuple[str, ...] = (
    # 線框 `find.pe_two_kinds` 的 `name` 逐字（本組 node 實測：14 個 name 裡唯一命中）
    "🔴 為什麼有些本益比是空的（PE 兩種「沒有」的分辨）",
    # 線框 `find.sector_flow` 的 `degraded` 格逐字片段（本檔在 n5 層註與該塊卡片各引一次）
    "就地寫出它為什麼是舊的",
)


def build_find_body() -> str:
    """「🔍 找標的」頁的整頁標記。**全程在 `find_page_contract()` 之內**。

    🔴 標記一個角括號都不手打卡片：`markup.card_html` / `markup.grid_html` 產。
    🔴 **⛔ 不呼叫 `markup.layer_html`**：線框 `layers[]` 上⛔ 沒有任何層級網格欄數
       （本組 node 實測）⇒ 六層一律逐 block 全寬輸出，同 `build_why_body()`。
    """
    cards_by_block = build_find_cards()
    parts: list[str] = [
        # ── 就地揭露：**收起狀態也看得見**，⛔ 不藏進摺疊器 ──
        '<section class="pv-layer" id="pv-find-disclosure">',
        '<div class="pv-layer-label">🔍 找標的 · 六層 14 block（版面定義在產生器內）</div>',
        f'<p class="pv-disclosure">{esc(FIND_LAYOUT_DISCLOSURE)}</p>',
        f'<p class="pv-meta">{esc(FIND_LAYOUT_DISCLOSURE_WHY)}</p>',
        # ⭐ 客戶 2026-09-22【拍板 1】明示的那一句 —— ⛔ 不得省
        f'<p class="pv-disclosure">{esc(FIND_GRID_CSS_DISCLOSURE)}</p>',
        f'<p class="pv-meta">{esc(FIND_GRID_CSS_DISCLOSURE_WHY)}</p>',
        f'<p class="pv-meta">{esc(FIND_PAGE_SHAPE_NOTE)}</p>',
        "</section>",
    ]

    with find_page_contract():
        for n, blocks in FIND_LAYER_BLOCKS.items():
            tier = find_tier_for_layer(n)
            leaf = FIND_LAYER_LEAF[n]
            leaf_text = "葉外（兩葉共用）" if leaf is None else f"{leaf} {FIND_LEAF_NAME[leaf]}"
            parts.append('<section class="pv-layer">')
            parts.append(
                f'<div class="pv-layer-label">{esc(FIND_LAYER_LABEL[n])} · n{n} · '
                f'{esc(leaf_text)} · 密度 {esc(tier)} · '
                f'block {len(blocks)} 塊：{esc("、".join(blocks))}</div>'
            )
            parts.append(
                f'<p class="pv-meta">components.CARD_TIERS[<span class="pv-mono">'
                f'{esc(tier)}</span>]：{esc(_tier_caption(tier))}</p>'
            )
            parts.append(f'<p class="pv-meta">{esc(FIND_LAYER_NOTE[n])}</p>')
            for block in blocks:
                cards = [markup.card_html(block=block, **card)
                         for card in cards_by_block[block]]
                if block in FIND_NO_CARD_DISCLOSURE:
                    # 規格 ② 處置 2(a)：整塊不存在 ⇒ ⛔ 沒有卡、⛔ 沒有徽章（見 F3）。
                    assert not cards, f"{block} ⛔ 不得有卡：規格 ② 處置 2(a)"
                    cards = [f'<p class="pv-disclosure">'
                             f'{esc(FIND_NO_CARD_DISCLOSURE[block])}</p>']
                parts.append(markup.grid_html(block=block, cards=cards))
            parts.append("</section>")

    # ── 本頁的衝突與洞，逐條畫出來（客戶要求 6：就地標明、寫進附錄、⛔ 不自行裁決）──
    parts.append('<section class="pv-layer" id="pv-find-gaps">')
    parts.append('<div class="pv-layer-label">'
                 '附錄 · 「🔍 找標的」頁本輪查到的規格衝突與未決項（逐條登記，⛔ 不代為裁決）</div>')
    parts.append(
        f'<p class="pv-meta">{esc("每一條都是：" + GAP_CAVEAT + "。⛔ 不得被引用為「已查證的事實」去支撐下一步決策（CLAUDE.md §-2 規則 6）。")}</p>')
    for gap_id, title, detail in FIND_SPEC_GAPS:
        parts.append(
            f'<p class="pv-meta"><span class="pv-mono">{esc(gap_id)}</span>　'
            f"{esc(title)}　{esc(GAP_CAVEAT)}</p>"
        )
        parts.append(f'<p class="pv-meta">{esc(detail)}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def build_find_html() -> str:
    """把「🔍 找標的」整頁包成一個可切換的容器（預設 `hidden`，由側欄點出來）。"""
    return "\n".join([
        html_comment(
            "「🔍 找標的」頁 ＝ **六層 14 block**（客戶 2026-09-22 拍板逐字「2. 6 層 14 block」）。\n"
            "⛔ 本頁的版面定義住在產生器的 `FIND_LAYOUT`，**不在** `src/ui_v2/` 契約層、\n"
            "  **沒有** `tests/ui_v2/` 的測試守護 —— 同「📖 憑什麼」頁的作法（客戶拍板的選項 1），\n"
            "  後果已就地揭露在本頁最上方與附錄 F1~F17。\n"
            "⭐ 標記怎麼來的：產生期間把 `markup.page_today` **暫時**換成本頁的版面契約，\n"
            "  卡片與網格仍由 `markup.card_html` / `grid_html` 產出；產完**立刻還原**。\n"
            "⭐ CSS：本頁用到兩組契約層**沒有產**的欄數（3/3/1 與 2/1/1）——\n"
            "  客戶【拍板 1】選作法 (甲)：由產生器補兩條 rule，值用 `components.resolve_cols()`\n"
            "  ＋ `components.BREAKPOINTS` 算（⛔ 不寫死數字、⛔ 不碰任何底線私有符號），\n"
            "  並**就地揭露「規則形狀複製了一份」** ＝ 第二個真相源。\n"
            "⛔ 本頁**沒有畫** #2 / #5 / #8 / #9 / #10 五顆徽章：規格 ② 逐列判它們未落地或不適用，\n"
            "  誤畫會在產生時變成 ValueError（代理的 BADGES_NOT_ON_PAGE 擋）。\n"
            "⛔ 兩塊（情境快選 / 入選理由）**沒有卡、沒有徽章**：規格 ② 處置 2(a) 逐字「整塊不存在\n"
            "  ⇒ 不畫，⛔ 不得用 #5 冒充」—— 本輪只畫它們的版面位置，衝突登記在附錄 F3。"
        ),
        '<div id="pv-page-find" hidden>',
        "<main>",
        build_find_body(),
        "</main>",
        "</div>",
    ])



# ══════════════════════════════════════════════════════════════════
# 4.8 「🔬 查一檔」頁 —— 版面定義寫在產生器（沿用 4.6／4.7 的「選項 1」作法）
#
# 🔴 **客戶本輪的硬約束（逐字，本節就是它們的落地）**：
#    「只動 docs/v2/prototype/gen_today_v2.py 與產出 HTML」
#    「不碰 src/ 真實作」「元件全部從 src/ui_v2/ 生成，⛔ 不手抄」
#    「規格衝突 → 就地標明、寫進附錄、⛔ 不自行裁決」「跑兩條 lane」
#    「側欄切到「🔬 查一檔」可顯示；其他一頁（💼 我的持股）仍顯示「此頁待做」」
#
# 🔴 **⛔ 不發明 block、⛔ 不發明 cols。** 22 筆每一筆都在 `src` 欄標出處
#    （規格**章節名** ＋ 線框 **block key**；依 CLAUDE.md §8.2.A.0 規則 1 **⛔ 不寫行號**）。
#
# 📌 **兩個來源（本組各自 node／import 實跑過，⛔ 非讀他組轉述）**：
#    · 規格 `docs/v2/spec/UI_PAGE_INSPECT.md`（五節 ①~⑤）
#    · 線框 `docs/v2/wireframe/wf_page_inspect.js` 的 `id:"inspect"`
#      —— block 巢在 `layers[].blocks[]`，本組 node 實測 **5 層 22 block 2 葉**
#      （`l1` 17 塊／`l2` 2 塊／葉外 `leaf:null` 3 塊），
#      `cols` 全集只有 `1/1/1`（14 塊）與 `3/2/1`（8 塊）兩種。
#
# ⭐ **本頁與前兩頁的三個結構差異（實測，⛔ 不是抄前例）**：
#    ① **沒有 n5** —— 五層恰為 `n0~n4`，全部落在 `components.tier_for_layer()` 的
#      定義域內 ⇒ 本頁**⛔ 不需要**「📖 憑什麼」／「🔍 找標的」兩頁那種 `*_N5_TIER` 繞法。
#    ② **`n3` 是唯一跨葉的一層**（`l1` 4 塊 ＋ `l2` 2 塊）—— 前兩頁每層單一葉，
#      故本頁的 `INSPECT_LAYER_LEAF` 回的是**一個 tuple**，⛔ 不是單一字串。
#    ③ **cols 全集只有兩種，且兩種契約層都已產 CSS** ⇒ 本頁**⛔ 不補任何一條欄數 rule**
#      （「🔍 找標的」頁補了兩條；本頁一條都不補，見 `_INSPECT_COLS_NEEDING_CSS`）。
# ══════════════════════════════════════════════════════════════════

#: 就地揭露的**那一句**（同 `WHY_LAYOUT_DISCLOSURE` / `FIND_LAYOUT_DISCLOSURE`）。
INSPECT_LAYOUT_DISCLOSURE = (
    "⚠️ 此頁版面定義在產生器內，未進 src/ui_v2/ 契約層、無 tests/ui_v2/ 測試守護。"
)

#: 上面那句的**後果**（⛔ 不是免責套話，是可查證的差別）。
INSPECT_LAYOUT_DISCLOSURE_WHY = (
    "差別在哪：「🚦 今天」頁的版面（哪個 block 在第幾層、幾欄、哪一階密度）住在 "
    "src/ui_v2/page_today.py，改壞了 tests/ui_v2/ 會紅燈；本頁的同一組資料住在 "
    "docs/v2/prototype/gen_today_v2.py 的 INSPECT_LAYOUT，改壞了⛔ 沒有任何測試會攔。"
    "⇒ 本頁的版面只有「跟規格與線框對照」這一種查法，⛔ 沒有機器守衛。"
    "本產生器在結尾自己跑了一輪對照（22 個 block key／層／欄數 class／密度 class 逐一比對），"
    "但那是**同一組人寫的自驗**，⛔ 不等於獨立測試。"
)

#: 本頁的**形狀**（本組自己 node 量的，⛔ 不引用他組轉述）。
INSPECT_PAGE_SHAPE_NOTE = (
    "本頁形狀（本組自行實測，⛔ 非引用轉述）：規格 docs/v2/spec/UI_PAGE_INSPECT.md ＋ 線框 "
    "docs/v2/wireframe/wf_page_inspect.js 的 id 為 inspect 那一頁 —— node 解析結果："
    "5 層（n0~n4，⛔ 沒有 n5）、22 block、2 葉（l1 單檔診斷 17 塊／l2 多檔比較 2 塊／"
    "葉外 leaf 為 null 3 塊）；22 塊的 cols 全集只有兩種，1/1/1 共 14 塊、3/2/1 共 8 塊；"
    "22 塊的 states 十鍵同名同序，220 格中 150 格有值、70 格為 null；"
    "22 塊的 asOf 欄**全部是 null**（⇒ 本頁一個時間都不准填）；src 為 null 的有 5 塊"
    "（chrome.asof、chrome.footer、inspect.evi.cards、inspect.evi.overlap、inspect.evi.cost）。"
    "線框 mainCTA 欄位存在且非 null（label 逐字「🔍 載入完整分析」）⇒ 本頁**有**主 CTA，"
    "住 n1 的 inspect.form；葉2 另有一顆「🚀 批次分析」，線框自己把它排除在 mainCTA 之外 "
    "⇒ 符合客戶「每頁首屏唯一」的範圍詞。"
)

#: 🔴 **總管拍板 1（表格）—— 理由逐字寫在畫面上，⛔ 不得省。**
#:    （散文常數會直接渲染成畫面上的字，故沿用本檔慣例**去掉 markdown 粗體與反引號**，
#:      ⛔ 用字一字未改；見 `ASOF_SHELL_DISCLOSURE` 上方的同一條慣例註記。）
INSPECT_TABLE_DISCLOSURE = (
    "⚠️ 本頁唯一用到表格的那一塊（inspect.batch 批次評分表）**⛔ 沒有畫成真的表格**："
    "它的四個欄（代碼｜型別｜狀態｜明細）是用 markup.card_html 的 facts 逐列描述掉的。"
)
INSPECT_TABLE_DISCLOSURE_WHY = (
    "總管拍板（理由逐字）：這不是三選一，是客戶既有約束逼出的唯一解："
    "(乙)「產生器自寫表格 CSS」會手打 px 字面值＋製造第二個真相源，"
    "違反本檔檔頭紀律與客戶「⛔ 不手抄」；"
    "(丙)「補進 components/markup」違反客戶「⛔ 不碰 src/ 真實作」。"
    "必須登記成缺口一條：「表格能力未落地」。"
    "／／本組實測（⛔ 非推測，量測日 2026-09-22）：src/ui_v2/markup.py 的公開函式**恰 5 個** ——"
    "page_css／badge_html／card_html／grid_html／layer_html（ast 掃 module 層 def，"
    "底線開頭的 15 個私有函式⛔ 不得呼叫）；"
    "以 ast 掃 src/ui_v2 全部模組的**字串常值**，"
    "⛔ 沒有任何 <table>／<thead>／<tbody>／<tr>／<th>／<td> 標記；"
    "本輪產出的 HTML 這六個標籤計數**為 0**（產生器結尾有一道守衛逐一掃它們）。⇒ 缺口編號 P1。"
)

#: 🔴 **總管拍板 2（主 CTA）—— 理由逐字寫在畫面上，⛔ 不得省。**
INSPECT_CTA_DISCLOSURE = (
    "⚠️ 本頁的主 CTA「🔍 載入完整分析」**⛔ 沒有畫成真的 pv-btn-primary 鈕**，"
    "沿「🔍 找標的」頁先例以文字呈現。"
)
INSPECT_CTA_DISCLOSURE_WHY = (
    "總管拍板（理由逐字）：全檔目前只有 TODAY 一顆 primary 鈕；"
    "只補 INSPECT 會造成三頁不一致。登記成缺口：註明「FIND 與 INSPECT 的主 CTA "
    "皆未渲成真鈕，若要補應兩頁一起補、屬另一輪，⛔ 本輪不單邊處理」。⇒ 缺口編號 P2。"
)

#: 五層的層標 —— `UI_PAGE_INSPECT.md` ① 四層結構表**第一欄逐字**（⛔ 去掉 markdown 粗體記號）。
#: ⚠️ `n0` 那一列規格逐字寫「葉外」並自註「**據實列出，不計入四層**」
#:    ⇒ 本頁是「四層 ＋ 一層葉外」，⛔ 不是五層內容層。
INSPECT_LAYER_LABEL: Mapping[int, str] = {
    0: "葉外",
    1: "第一層 輸入與判型",
    2: "第二層 三張判決卡",
    3: "第三層 明細",
    4: "第四層 展開佐證",
}

#: 每個 block 所屬的葉 —— 線框 `layers[].blocks[].leaf`（本組 node 實測，逐塊抄下來）。
#: 🔴 **⛔ 不能像前兩頁那樣每層一個值**：`n3` 的 6 塊裡有 4 塊在 `l1`、2 塊在 `l2`
#:    （`inspect.batch.form` / `inspect.batch`）—— 那是本頁與前兩頁的結構差異之一。
#: ⚠️ 本表與 `INSPECT_LAYOUT` 是兩張手寫表，故 `main()` 另有一道 assert 釘住兩者 key 集合相同
#:    （⛔ 不讓其中一張漏一塊而沒有人發現）。
_INSPECT_BLOCK_LEAF: Mapping[str, str | None] = {
    "inspect.statusbar": None,
    "chrome.asof": None,
    "chrome.footer": None,
    "inspect.form": "l1",
    "inspect.wiring_single": "l1",
    "inspect.kind": "l1",
    "inspect.unknown": "l1",
    "inspect.stock.health": "l1",
    "inspect.stock.valuation": "l1",
    "inspect.stock.chips": "l1",
    "inspect.etf.premium": "l1",
    "inspect.etf.dividend": "l1",
    "inspect.etf.peer": "l1",
    "inspect.profit": "l1",
    "inspect.pattern_measure": "l1",
    "inspect.stock.detail": "l1",
    "inspect.etf.detail": "l1",
    "inspect.batch.form": "l2",
    "inspect.batch": "l2",
    "inspect.evi.cards": "l1",
    "inspect.evi.overlap": "l1",
    "inspect.evi.cost": "l1",
}

#: 兩葉的名字 —— 線框 `leaves[].name` 逐字（本組 node 實測）。
INSPECT_LEAF_NAME: Mapping[str, str] = {
    "l1": "單檔診斷（個股／ETF/unknown 三分支）",
    "l2": "多檔比較（可混貼）",
}

#: 本頁**會畫**的徽章。
#: ⭐ **這一組⛔ 不是本組推導的，是規格 ② 的逐字總結句**（與「🔍 找標的」頁相反 —— 那一份
#:    沒有總結句、只能逐列推導，見 F13）：UI_PAGE_INSPECT ② 表下方逐字
#:    「⇒ **實際會出現在畫面上的是 5 態：#1／#3／#5／#6／#7。** #2／#4／#8／#9 皆未落地
#:      （#4 為刻意，其餘三者待補）」，同表末列另逐字「#10 **不適用**…⇒ **不畫 #10**；
#:      ⛔ 不得併進 #8」。
#: ⚠️ **#4 與其他三顆不同類，⛔ 不要混為一談**：#2／#8／#9 是「**待補**」，
#:    #4 是規格明寫的「**刻意不出現**」（實作檔頭逐字「本頁沒有任何一格會判 UI_DEGRADED，
#:    這是刻意的」，線框 inspect.profit.degraded 亦自陳「本頁目前不會出現這一態」）。
INSPECT_BADGES_ON_PAGE: frozenset[int] = frozenset({1, 3, 5, 6, 7})
INSPECT_BADGES_NOT_ON_PAGE: frozenset[int] = frozenset(
    int(b["n"]) for b in components.BADGES if int(b["n"]) not in INSPECT_BADGES_ON_PAGE
)

#: 本頁的**版面定義**（五層 22 block）。`cols` ＝ `(桌機, 平板, 手機)`。
#: 🔴 每一筆的 `src` 是**出處**，⛔ 不是註解：規格章節名 ＋ 線框 block key，全形｜分隔。
INSPECT_LAYOUT: tuple[Mapping[str, object], ...] = (
    # ── n0 葉外｜全域 chrome（線框 `leaf: null`，三塊全 1/1/1）──────────────────
    {"block": "inspect.statusbar", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「葉外」列 ＋ ④ 反例自檢 A 的 n0 那一條"
            "｜線框 inspect.statusbar"},
    {"block": "chrome.asof", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「葉外」列 ＋ ④ 反例自檢 A 的 n0 那一條"
            "｜線框 chrome.asof"},
    {"block": "chrome.footer", "n": 0, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「葉外」列 ＋ ④ 反例自檢 A 的 chrome.footer 那一條"
            "（總管 2026-09-16 更正為非缺陷）｜線框 chrome.footer"},
    # ── n1 葉1｜輸入與判型（主 CTA 住這一層；① 表該列 cols 逐字「3/2/1・其餘 1/1/1」）──
    {"block": "inspect.form", "n": 1, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第一層 輸入與判型」列（該列 cols 首項 3/2/1）"
            "＋ ① 按鈕段主 CTA 那一條｜線框 inspect.form"},
    {"block": "inspect.wiring_single", "n": 1, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第一層 輸入與判型」列（該列 cols 末項 1/1/1）"
            "｜線框 inspect.wiring_single"},
    {"block": "inspect.kind", "n": 1, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第一層 輸入與判型」列 ＋ ⑤ 判型三分支"
            "｜線框 inspect.kind"},
    {"block": "inspect.unknown", "n": 1, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第一層 輸入與判型」列 ＋ ⑤ 第 3 分支（unknown）"
            "｜線框 inspect.unknown"},
    # ── n2 葉1｜三張判決卡（① 表逐字「6 block 全 3/2/1」）──────────────────────
    {"block": "inspect.stock.health", "n": 2, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第二層 三張判決卡」列 個股 A ＋ ④ 反例自檢 A 的 n2 那一條"
            "｜線框 inspect.stock.health"},
    {"block": "inspect.stock.valuation", "n": 2, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第二層 三張判決卡」列 個股 A ＋ ① 的 357 算式段"
            "｜線框 inspect.stock.valuation"},
    {"block": "inspect.stock.chips", "n": 2, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第二層 三張判決卡」列 個股 A"
            "｜線框 inspect.stock.chips"},
    {"block": "inspect.etf.premium", "n": 2, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第二層 三張判決卡」列 ETF B ＋ ⑤ 第 2 分支"
            "｜線框 inspect.etf.premium"},
    {"block": "inspect.etf.dividend", "n": 2, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第二層 三張判決卡」列 ETF B ＋ ⑤ 第 2 分支"
            "｜線框 inspect.etf.dividend"},
    {"block": "inspect.etf.peer", "n": 2, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第二層 三張判決卡」列 ETF B ＋ ② 的 na 那一列"
            "｜線框 inspect.etf.peer"},
    # ── n3｜明細（l1 四塊）＋ 葉2 批次（l2 兩塊）；① 表逐字「3/2/1・其餘 1/1/1」──
    {"block": "inspect.profit", "n": 3, "cols": (3, 2, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第三層 明細」列（該列 cols 首項 3/2/1）"
            "＋ ③① 獲利能力 5 指標那一節｜線框 inspect.profit"},
    {"block": "inspect.pattern_measure", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第三層 明細」列（該列 cols 末項 1/1/1）"
            "｜線框 inspect.pattern_measure"},
    {"block": "inspect.stock.detail", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第三層 明細」列 ＋ ② 的 unwired 那一列"
            "（載體是兩支 detail 卡）｜線框 inspect.stock.detail"},
    {"block": "inspect.etf.detail", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第三層 明細」列 ＋ ② 的 unwired 那一列"
            "（載體是兩支 detail 卡）｜線框 inspect.etf.detail"},
    {"block": "inspect.batch.form", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第三層 明細」列 葉2 ＋ ① 按鈕段葉2 那一條"
            "｜線框 inspect.batch.form"},
    {"block": "inspect.batch", "n": 3, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第三層 明細」列 葉2 ＋ ① 表格三斷點那一段"
            "｜線框 inspect.batch"},
    # ── n4 葉1｜展開佐證（三塊全 1/1/1；t4 是四階裡唯一 dashed）────────────────
    {"block": "inspect.evi.cards", "n": 4, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第四層 展開佐證」列 ＋ ① 的 357 算式段"
            "（算式併在本塊第 2 條列項）｜線框 inspect.evi.cards"},
    {"block": "inspect.evi.overlap", "n": 4, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第四層 展開佐證」列 ＋ ③③ 個股與 ETF 重疊那一節"
            "｜線框 inspect.evi.overlap"},
    {"block": "inspect.evi.cost", "n": 4, "cols": (1, 1, 1),
     "src": "UI_PAGE_INSPECT ① 四層結構表「第四層 展開佐證」列 ＋ ③② 成本口徑那一節"
            "｜線框 inspect.evi.cost"},
)

#: 由 `INSPECT_LAYOUT` **推導**（⛔ 不另手寫一份，否則就是第二個真相源 —— CLAUDE.md §2.1）。
INSPECT_BLOCK_COLS: Mapping[str, tuple[int, int, int]] = {
    str(rec["block"]): tuple(rec["cols"]) for rec in INSPECT_LAYOUT   # type: ignore[misc]
}
_INSPECT_BLOCK_LAYER: Mapping[str, int] = {
    str(rec["block"]): int(rec["n"]) for rec in INSPECT_LAYOUT        # type: ignore[arg-type]
}
INSPECT_LAYER_BLOCKS: Mapping[int, tuple[str, ...]] = {
    n: tuple(str(rec["block"]) for rec in INSPECT_LAYOUT if int(rec["n"]) == n)  # type: ignore[arg-type]
    for n in sorted({int(rec["n"]) for rec in INSPECT_LAYOUT})                   # type: ignore[arg-type]
}
#: 每層有哪幾個葉 —— **由 `_INSPECT_BLOCK_LEAF` 推導**，⛔ 不手寫第二份。
#: ⚠️ 回的是 tuple：`n3` 會回 `("l1", "l2")`（本頁唯一跨葉的一層）。
INSPECT_LAYER_LEAF: Mapping[int, tuple[str | None, ...]] = {
    n: tuple(dict.fromkeys(_INSPECT_BLOCK_LEAF[b] for b in blocks))
    for n, blocks in INSPECT_LAYER_BLOCKS.items()
}


def inspect_tier_for_layer(n: int) -> str:
    """層序 → 卡密度。

    ⭐ **本頁⛔ 沒有任何一層需要繞過契約層** —— 五層恰為 `n0~n4`，
    `components.tier_for_layer()` 的定義域就是 `0` 與 `1~4`（本組實測）⇒ **整段直接委派**。
    ⛔ 刻意**不**抄「📖 憑什麼」／「🔍 找標的」兩頁的 `*_N5_TIER` 繞法：
    那兩頁有 `n5`（契約層沒有那一格），本頁沒有 —— **⛔ 不得為了「看起來一致」多留一個沒有
    對應實體的分支**（那是 §8.1 step 6「用不到的抽象」的反例）。
    """
    return components.tier_for_layer(n)


def inspect_tier_for_block(block_key: str) -> str:
    """block → 卡密度。**⛔ 刻意不提供 tier 覆寫參數**（同 `page_today.tier_for_block`）。"""
    try:
        n = _INSPECT_BLOCK_LAYER[block_key]
    except KeyError:
        raise KeyError(f"未知的 block：{block_key!r}") from None
    return inspect_tier_for_layer(n)


#: 本頁用到、但**契約層與前面各頁都還沒產 CSS** 的欄數組合（**推導，⛔ 不手寫清單**）。
#: 🔴 **公式必須同時減掉兩個來源**（⛔ 不是只減契約層）：
#:    契約層 `page_today.BLOCK_COLS` ＋「🔍 找標的」頁已補的 `FIND_BLOCK_COLS`。
#:    只減前者會讓本頁在用到 `(3,3,1)` / `(2,1,1)` 時**重複宣告同名 CSS rule** ——
#:    那正是「第二個真相源」本身（CLAUDE.md §2.1），而且**不會報錯**、只會靜默疊在一起。
#: ⚠️ 本頁實測結果是**空集合**（cols 全集只有 1/1/1 與 3/2/1，兩種契約層都已產）
#:    ⇒ 本頁**一條欄數 rule 都不補**。公式仍照寫 —— 版面日後若加了新欄數，這裡會自動長出來。
_INSPECT_COLS_NEEDING_CSS: tuple[tuple[int, int, int], ...] = tuple(sorted(
    set(INSPECT_BLOCK_COLS.values())
    - set(page_today.BLOCK_COLS.values())
    - set(FIND_BLOCK_COLS.values())
))


# ── 代理：把 `markup.page_today` **暫時**換成本頁的版面契約 ──────────────────
#: 作法、三條紀律與「為何非代理不可」**與 `_WHY_CONTRACT` 完全相同**（見該處長註，⛔ 不重抄）。
#: ⚠️ 名單由同一個 AST 掃描把關（`_markup_page_today_names()`）——
#:    本組實跑結果：`markup` 只讀 7 個名字，與前兩頁**同一組，一個都不用加**。
#: ⚠️ `LAYER_GRID_COLS` **刻意給空 dict**（同前兩頁）：`markup.layer_html()` 只有 `layer=2`
#:    能用，且它讀的 `markup._LAYER_COLS_USED` 是 **import 當下**就依 `page_today` 算好的、
#:    代理換不動 ⇒ 本頁⛔ 不呼叫 `layer_html()`，給空 dict 讓任何誤用**當場 KeyError**。
#: ⚠️ `card_value_text` / `card_level_text` **沿用 `page_today` 原函式** ——
#:    「灰態紅態留白」那把尺⛔ 不分頁，本檔⛔ 不另立第二把。
_INSPECT_CONTRACT = types.SimpleNamespace(
    BLOCK_COLS=INSPECT_BLOCK_COLS,
    LAYER_GRID_COLS={},
    BADGES_ON_PAGE=INSPECT_BADGES_ON_PAGE,
    BADGES_NOT_ON_PAGE=INSPECT_BADGES_NOT_ON_PAGE,
    tier_for_block=inspect_tier_for_block,
    card_value_text=page_today.card_value_text,
    card_level_text=page_today.card_level_text,
)


@contextlib.contextmanager
def inspect_page_contract() -> Iterator[None]:
    """`with` 期間 `markup` 走「🔬 查一檔」的版面查表；離開時**一定**還原。

    三道 assert 與 `why_page_contract()` / `find_page_contract()` 同構（⛔ 不是「應該可以」）。
    """
    needed = _markup_page_today_names()
    missing = needed - set(vars(_INSPECT_CONTRACT))
    assert not missing, (
        f"代理少了 markup 會讀的名字：{sorted(missing)} —— "
        "markup.py 多讀了東西而本檔的代理沒跟上。"
        "⛔ 不得為了跑得動就隨便補一個值（那會畫出一個編出來的版面，違 CLAUDE.md §1）。"
    )
    original = markup.page_today
    assert original is page_today, (
        "進場時 markup.page_today 已經不是原物件 —— 上一次替換忘了還原")
    markup.page_today = _INSPECT_CONTRACT
    try:
        yield
    finally:
        markup.page_today = original
    assert markup.page_today is page_today, "還原失敗：markup.page_today 不是原物件"


INSPECT_LAYER_NOTE: Mapping[int, str] = {
    0: "三塊的 leaf 在線框是 null ＝ 葉外 chrome，畫在分頁列之上、兩葉共用。"
       "⚠️ 規格 ④ 反例自檢 A 逐字：**這三塊在本頁的實作檔全部 0 命中** —— "
       "其中 inspect.statusbar 與 chrome.asof ⇒ 失敗時無可顯示；"
       "⛔ 不得用判決卡的紅態冒充一條不存在的狀態列。"
       "⭐ 但**同樣是 0 命中，chrome.footer 的結論剛好相反**：規格 ④ 有一條總管 2026-09-16 的更正 ——"
       "原登記「本頁沒有頁尾 ⇒ 實作待修」是誤判，因為頁尾是 L6 app.py 統一出的跨頁 chrome"
       "（對每一個 IA 頁都會呼叫，註解逐字「不分頁面」）⇒ **頁面自己 0 命中是正確設計，不是缺陷**；"
       "⛔ 不得據此在頁面檔內另畫一份頁尾（會變成兩邊各漂移一份）。"
       "⚠️ 在這份 HTML 原型裡，時點列與頁尾的**實體**畫在五頁共用的外殼上，"
       "本層畫的是它們的**版面登記**，⛔ 不是第二份 chrome；頂部狀態列的實體本原型**沒有做**。"
       "⚠️ 線框這三塊的 asOf 欄全是 null（22 塊都是）⇒ 本頁⛔ 一個真時間都不准填。",
    1: "t1 是四階裡唯一 2px 框線、內距最大的一階（手機 ≤640 另有一組覆寫內距，四階中也只有 t1 有）。"
       "⭐ **本頁的主 CTA「🔍 載入完整分析」就住在這一層**（線框 mainCTA.label 逐字）——"
       "規格 ① 另逐字：form 內只有這一顆、住預設葉 l1。"
       "葉2 的「🚀 批次分析」依規格 ① 轉述（WM 實查，本組未重跑）實作同為 primary 型別，"
       "但線框自己把它排除在 mainCTA 欄之外 "
       "⇒ 符合客戶「每頁首屏唯一」的範圍詞，⛔ 不得讀成「本頁有兩顆主 CTA」。"
       "⚠️ 四塊裡只有表單那塊是 3/2/1，其餘三塊 1/1/1。"
       "⭐ 判型結果那塊畫兩張卡（#3 冷啟動 ＋ #6 判型失敗）——⛔ 不是挑好看的："
       "規格 ④ 反例自檢 A 逐字要求判型失敗要標 #6 並附錯誤型別，且逐字「這種時候不會替你猜一個型別」。"
       "⚠️ 判不出型別那塊**只畫 #3 灰態**：規格 ⑤ 第 3 分支逐字「第三條路，不是紅態」、"
       "「這一格不會變紅 —— 判不出型別是一個結果，不是故障」⇒ ⛔ 不得給它 #6。",
    2: "六塊全 3/2/1：個股分支 A 三張（健康度／估值 357／籌碼）、ETF 分支 B 三張"
       "（折溢價／配息／追蹤同儕）。規格 ⑤ 逐字「骨架同、內容全換 —— 與 A 沒有一個欄位共用」。"
       "⭐ 六張卡**各自判態，⛔ 不共用一態**：規格 ④ 反例自檢 A 逐字「三張判決卡各自判態，"
       "一格紅不染另外兩格」⇒ 六張卡的徽章依序是 #6／#1／#7／#7／#1／#3 ——"
       "⛔ 不是同一態複製六份，讓「一紅不染其餘」這件事在畫面上看得出來。"
       "（⚠️ 六張卡**只落在四種狀態**上：錯誤／正常／缺漏／尚未載入 —— "
       "⛔ 不要讀成「六種不同狀態」；本頁可畫的狀態本來就只有 5 態，見附錄 P10。）"
       "⚠️ 大字區留白**不是漏畫**：是 page_today.card_value_text() 依狀態擦掉的"
       "（規格 ④ 逐字「大字區留白，⛔ 不得顯示 0 或上一輪殘值」）。"
       "⚠️ ETF 同儕那塊線框有 na 格（本益比對 ETF 天生不存在），但規格 ② 判 #8 未落地、"
       "且逐字「⛔ 不得把 missing 畫成 #8（#8 重跑無效，畫錯＝給錯指引）」⇒ 本頁⛔ 不畫 #8。",
    3: "⭐ **本層是本頁唯一跨葉的一層**：l1 四塊（獲利能力／型態等幅量測／個股明細／ETF 明細）"
       "＋ l2 兩塊（批次表單／批次評分表）。前兩頁每層單一葉，本頁⛔ 不是。"
       "⚠️ 線框 l2 自註逐字「st.tabs 這一輪會把兩葉的 body 都跑完，葉只是視覺分組、不是執行閘門」"
       "⇒ ⛔ 不得把「分在兩葉」讀成「另一葉不會跑」。"
       "⭐ 💰 獲利能力那塊**只畫三格**（毛利率／營業利益率／安全邊際）：總管本輪拍板逐字"
       "「照規格畫 3 格；⛔ 不得採納「先畫兩張 #5 unwired 卡」」——那兩張是某組的建議，"
       "非客戶裁示、非總管拍板，原型照規格畫、不發明。缺口 P3 記了這件事與那個建議的身分。"
       "⚠️ 但**缺口本身⛔ 不准藏起來**：那三張卡的 facts 已就地寫出「第 2 排兩格（稅後淨利率／ROE）"
       "本頁未接線」，理由是規格 ③① 逐字點名現況「畫面上只有一排三格 —— 你看不出自己少看了兩個指標」，"
       "那正是 CLAUDE.md §1 要防的「把缺口掩蓋成完整」。"
       "⭐ #5 這一顆（未接線）畫在三塊上：型態等幅量測、個股明細、ETF 明細 ——"
       "規格 ② 逐字「該態確實會出現…載體是兩支 detail 卡」。"
       "⚠️ 批次評分表那塊**⛔ 沒有畫成真表格**（總管拍板 1，理由見本頁最上方揭露與缺口 P1）。",
    4: "t4 是四階裡唯一 dashed 的一階。三塊全 1/1/1、全在 l1。"
       "⚠️ 三塊的線框 src 都是 null（22 塊裡有 5 塊是 null，這三塊佔其中三塊）"
       "⇒ 它們在現行實作裡**沒有對應的程式位置**。"
       "⭐ 357 算式**沒有自己的 block**：規格 ① 逐字「「357 算式」在線框沒有獨立 block ——"
       "它併在 inspect.evi.cards 的第 2 條列項」⇒ 本頁⛔ 不另立一塊，也⛔ 不另寫一份算式"
       "（規格同句逐字「⛔ 不得在本頁另寫一份算式」）。"
       "⚠️ 重疊那塊的 13／6 兩個數字，線框自標「紅隊的比對結果，本組未複驗」"
       "⇒ 引用時必須照此標明，⛔ 不得當成已查證的事實（缺口 P6）。"
       "⚠️ 成本那塊本輪畫的是**誠實擬稿版**（總管拍板 4）：畫面上⛔ 不得出現規格禁止的口徑宣稱，"
       "理由與被拿掉的那半個標題見缺口 P4 與 P5。",
}


def build_inspect_cards() -> dict[str, list[dict]]:
    """每個 block 要畫幾張卡、各是什麼狀態。

    🔴 **狀態⛔ 不是挑好看的**，每一塊都同時過兩道（兩道都是本組 node／grep 實測）：
       ① 線框該塊 `states` 十態格裡**值為 null 的一律不准用**（null ＝ 該情況下結構上不存在，
          規格 ② 逐字：「⛔ 不得畫成空卡」）；
       ② 該態對應的徽章必須在 `INSPECT_BADGES_ON_PAGE` 內
          （否則 `markup.card_html` 會 fail loud —— 代理的 `BADGES_NOT_ON_PAGE` 擋）。
       規格點名了該畫哪一態的（④A／④B／⑤／③①），一律照規格。
    🔴 **每一張卡都掛 `("資料來源", DEMO)`** —— 比客戶的字面要求（「帶數字的卡」）更嚴：
       本頁的卡標大量含「葉1-A」「判決卡①」「7 段」這類**含阿拉伯數字**的規格名字，
       分不清「資料的數字」與「出處的數字」時一律從嚴掛標記。
    🔴 **⛔ 一個時間都不填**：線框 22 塊的 `asOf` 欄**全是 null**（本組 node 實測）。
    ⚠️ **本頁的文字都是從線框／規格摘的片段，⛔ 不是本組編的**；但**刻意避開了
       線框大量使用的「為…什麼：」句式** —— 那三個字與本產生器的一道全檔守衛相撞
       （客戶 2026-09-22 ④：第五頁用 SSOT 的「📖 憑什麼」）。
       處置與理由見缺口 P8，⛔ 本輪不擴大允許清單、⛔ 不弱化守衛。
    """
    rb = page_today.resolve_badge

    def demo(*rows: tuple[str, str]) -> tuple[tuple[str, str], ...]:
        return (*rows, ("資料來源", DEMO))

    return {
        # ── n0 葉外 chrome（規格 ④A：前兩塊本頁實作 0 命中；頁尾另有總管更正）────
        "inspect.statusbar": [
            {"state": "idle", "title": "（跨頁）頂部狀態列",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "⬜ 總經未評估　|　🔗 尚未綁定 Sheet"),
                 ("去哪補（線框逐字）", "到「🚦 今天」按「🚀 更新今日戰情」"),
                 ("本頁實作", "規格 ④A 逐字：本頁 0 命中 ⇒ 失敗時無可顯示"),
                 ("⛔ 不得", "用判決卡的紅態冒充一條不存在的狀態列（規格 ④A 逐字）"))},
        ],
        "chrome.asof": [
            {"state": "idle", "title": "資料時點揭露列（頁標題下方第一行）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "資料時點：尚未載入，本頁沒有任何本輪資料"),
                 ("這份原型", "外殼上那一條畫的正是這一態的逐字，⛔ 一個真時間都沒填"),
                 ("線框 asOf 欄", "本頁 22 塊全部是 null（本組 node 實測）⇒ ⛔ 不得編造任何時間"))},
        ],
        "chrome.footer": [
            {"state": "live", "title": "頁尾免責（每一頁都要有）",
             "value": None, "level": "🟢 常駐，⛔ 不隨狀態消失", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 error 逐字", "同上（整頁出錯時仍然出現）"),
                 ("總管 2026-09-16 更正", "原登記「本頁沒有頁尾 ⇒ 實作待修」是誤判 ——"
                                          "頁尾是 L6 統一出的跨頁 chrome，頁面自己 0 命中是正確設計"),
                 ("⛔ 不得", "在頁面檔內另畫一份頁尾（複製第二份 ＝ 兩邊會漂移）"))},
        ],
        # ── n1 輸入與判型（主 CTA 住這一層）──────────────────────────────────
        "inspect.form": [
            {"state": "idle", "title": "葉1 輸入表單 ＋ 🔍 載入完整分析（主 CTA）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字（常駐那句）", "按下去才會開始取數。在你按之前，"
                                               "這一頁不會發出任何一次網路連線。"),
                 ("線框 live 逐字（三格）", "〔代碼〕〔期間 / K 線〕〔均線〕＋ ▌🔍 載入完整分析 ▐"),
                 ("規格 ① 逐字", "form 內只有這一顆、住預設葉 l1"),
                 ("主 CTA 範圍詞", "每頁首屏唯一一顆（客戶 2026-09-22 拍板）"),
                 ("⚠️ 本輪的限制", "這一顆⛔ 沒有渲成真鈕，沿 FIND 先例以文字呈現 —— 見缺口 P2"),
                 ("線框 loading 逐字", "submit 停用；三格維持已填值（不會清掉你剛打的代碼）"))},
        ],
        "inspect.wiring_single": [
            {"state": "live", "title": "取數接線揭露 caption（表單正下方，常駐）",
             "value": None, "level": "🟢 常駐，⛔ 不隨狀態消失", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字（已接線那半）", "判型、個股健康度、估值（357）、籌碼、"
                                                 "💰 獲利能力三格、ETF 折溢價／配息／同儕 —— 這幾項已接線"),
                 ("線框 live 逐字（沒接線那半）", "K 線與其餘明細在本頁還沒接線 —— 它們的卡會標"
                                                 "「未接線」並寫明要去哪看，不會拿空白冒充結果"),
                 ("線框 live 逐字（期間的效力）", "期間的選擇只決定籌碼那一格載入多長的日線；"
                                                 "改期間不會改變籌碼結論"),
                 ("線框十態", "四格非 null，其餘六格是 null；idle／loading／error 三格逐字都是「同上」"))},
        ],
        "inspect.kind": [
            {"state": "idle", "title": "判型結果（就地顯示 ＋ 可手動覆寫）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "⬜ 尚未判型"),
                 ("去哪補（線框逐字）", "在上方輸入代碼後按「🔍 載入完整分析」"),
                 ("線框 loading 逐字", "⏳ 判型中…（固定高骨架，不顯示上一輪的型別）"),
                 ("⛔ 本頁不畫 #2", "規格 ② 逐字：載入中在實作端 0 處、st.spinner 亦 0 ⇒ 實作待補；"
                                    "⛔ 在補上之前不得拿 #3 冒充載入中"))},
            {"state": "error", "title": "判型結果 · 上游失敗（判型失敗）",
             "value": None, "level": None, "badge_n": rb(state="error"),
             "facts": demo(
                 ("線框 error 逐字", "🔴 判型失敗（附錯誤型別）—— 這種時候不會替你猜一個型別"),
                 ("規格 ④A 逐字", "判型失敗 ⇒ 兩支分支的判決卡都不畫"),
                 ("⛔ 不得", "替使用者猜一邊（線框 ⑤ 逐字「本站不替你選一邊」）"))},
        ],
        "inspect.unknown": [
            {"state": "idle", "title": "葉1-C 判不出型別 —— 已停在這裡（第三條路，不是紅態）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "⬜ 無法判定這是個股還是 ETF —— 已停在這裡，沒有替你猜"),
                 ("線框 idle 逐字（本站的立場）", "本站不替你選一邊。"),
                 ("去哪補（線框逐字）", "確認代碼；若確定它是台股，可在上方表單手動指定型別後重新載入"),
                 ("線框 error 逐字", "這一格不會變紅 —— 判不出型別是一個結果，不是故障"),
                 ("⛔ 不得", "給它 #6 紅態（規格 ⑤ 逐字：徽章走 #3／#7 灰系）"))},
        ],
        # ── n2 三張判決卡：六塊六態，⛔ 不是挑好看的（規格 ④A「一格紅不染另外兩格」）──
        "inspect.stock.health": [
            {"state": "error", "title": "葉1-A 判決卡①「健康度」",
             "value": None, "level": None, "badge_n": rb(state="error"),
             "facts": demo(
                 ("線框 error 逐字", "🔴 健康度取得失敗（附錯誤型別）—— 估值與籌碼照常顯示"),
                 ("規格 ④A 逐字", "三張判決卡各自判態，一格紅不染另外兩格；"
                                  "大字區留白，⛔ 不得顯示 0 或上一輪殘值"),
                 ("大字區為何是空的", "那是 page_today.card_value_text() 依狀態擦掉的，⛔ 不是漏畫"))},
        ],
        "inspect.stock.valuation": [
            {"state": "live", "title": "葉1-A 判決卡②「估值（357 評價）」",
             "value": None, "level": "🟡 殖利率 5~7%", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字（五分支之一）", "殖利率 5.80%，落在 5~7% 區間（92.1~128.9）"),
                 ("三段門檻（線框 evi.cards 逐字）", "三段門檻（7% / 5% / 3%）與各自對應的價位"),
                 ("算式住哪裡", "規格 ① 逐字：357 算式在線框沒有獨立 block，併在展開佐證那一塊的"
                                "第 2 條列項；⛔ 不得在本頁另寫一份算式"),
                 ("⛔ 全頁禁止買賣建議", "規格 ⑤ 末段逐字：357 三段價位是門檻反推價，⛔ 不得標成進出場點"))},
        ],
        "inspect.stock.chips": [
            {"state": "empty", "title": "葉1-A 判決卡③「籌碼」（籌碼明細全部收在這張卡裡）",
             "value": None, "level": None, "badge_n": rb(state="empty"),
             "facts": demo(
                 ("線框 empty 逐字", "▨ 判不出來 ＋ 上游給的原因原文 —— ⚠️ 這不是故障，"
                                     "走灰態，不是紅態"),
                 ("線框 live 逐字（卡內補充列）", "連續性、集中度、單日爆量檢查"),
                 ("⛔ 不得", "把 missing 畫成 #8（規格 ② 逐字：#8 重跑無效，畫錯＝給錯指引）"))},
        ],
        "inspect.etf.premium": [
            {"state": "empty", "title": "葉1-B 判決卡①「折溢價」（ETF 分支）",
             "value": None, "level": None, "badge_n": rb(state="empty"),
             "facts": demo(
                 ("線框 empty 逐字", "▨ 這一檔沒有折溢價資料"),
                 ("線框 empty 逐字（關鍵區別）", "這是「沒有淨值」，不是「折溢價為 0」；"
                                                "本站不拿最後一次公告的淨值硬戳今天的價格算一個假溢價"),
                 ("去哪補（線框逐字）", "等當日官方 iNAV 公告；重按不會讓淨值提早出現"),
                 ("線框 error 逐字", "🔴 折溢價取不到（附錯誤型別）—— 配息照常顯示"))},
        ],
        "inspect.etf.dividend": [
            {"state": "live", "title": "葉1-B 判決卡②「配息」（ETF 分支）",
             "value": None, "level": "🟢 近 4 季未縮", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字", "標籤 配息／大數值 年化 5.8%／副標 年化配息率／時點 2026-Q2 配息"),
                 ("線框 empty 逐字（不可造假那句）", "本站不把兩者都寫成 0%，因為 0% 是"
                                                    "「不配息」這個結論"),
                 ("⛔ 不得", "把「查不到」與「真的沒配過」合併成同一個數字（對照 CLAUDE.md §1）"))},
        ],
        "inspect.etf.peer": [
            {"state": "idle", "title": "葉1-B 判決卡③「追蹤／同儕」（ETF 分支）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "⬜ 尚未載入"),
                 ("線框 live 逐字（facts 列）", "近 3／6／12 月分位、品質評等、成立年數"),
                 ("線框 na 逐字", "N/A —— 本益比那一欄對 ETF 天生不存在。不加 ⚠︎、不寫「壞掉」、"
                                  "也不會叫你去做什麼"),
                 ("⛔ 本頁不畫 #8", "規格 ② 逐字：實作只有單一 UI_EMPTY、未依 miss_reason 拆 #7／#8"),
                 ("線框 empty 逐字", "算不出就是算不出，不會拿一個中位數頂替"))},
        ],
        # ── n3 l1｜💰 獲利能力：**只畫三格**（總管拍板 3）───────────────────────
        "inspect.profit": [
            {"state": "live", "title": "💰 獲利能力① 毛利率",
             "value": None, "level": "🟢 好生意", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字（第 1 排）", "〔毛利率 58.2% 🟢 好生意〕"),
                 ("區塊標題下一句話（線框逐字）", "這家公司每賣 100 元，最後留下多少？"),
                 ("⚠️ 這一排不是全部", "第 2 排兩格（稅後淨利率／ROE）本頁未接線 ——"
                                       "規格 ③① 逐字：畫面上只有一排三格，你看不出自己少看了兩個指標"),
                 ("本輪為何只畫三格", "總管拍板 3：照規格畫 3 格；⛔ 不得採納「先畫兩張未接線卡」"
                                      "—— 那是某組的建議，非客戶裁示、非總管拍板。見缺口 P3"))},
            {"state": "live", "title": "💰 獲利能力② 營業利益率",
             "value": None, "level": "🟢 本業獲利", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字（第 1 排）", "〔營業利益率 42.1% 🟢 本業獲利〕"),
                 ("線框 empty 逐字", "⚪ 〈格名〉：資料缺漏 —— 不是紅的「辛苦生意」"
                                     "（一格缺不會把其餘各格一起染色）"),
                 ("線框 error 逐字", "⚠️ 出錯時是整排一起紅，不是單一格紅 ——"
                                     "上面「一格缺不影響其他格」只適用於缺資料，不適用於出錯"))},
            {"state": "live", "title": "💰 獲利能力③ 安全邊際",
             "value": None, "level": "🟢", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字（第 1 排）", "〔安全邊際 抗震極強 🟢〕"),
                 ("線框 unwired 逐字（第 2 排那兩格）", "稅後淨利率 · ROE —— 兩格未接線（還沒做）："
                                                       "大字區留空，那一列寫 N/A（不加 ⚠︎ —— 它不是壞掉）"),
                 ("線框 unwired 逐字（⛔ 別重按）", "這一態沒有你可以做的事 —— 按一百次也不會亮"),
                 ("線框 live 逐字（接線後的坑）", "這兩格接線之後，第三行會是空的 ——"
                                                 "它們目前沒有中文判讀語。本線框不編一個字填進去"))},
        ],
        "inspect.pattern_measure": [
            {"state": "unwired", "title": "🎯 型態等幅量測（改名提案）",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": demo(
                 ("線框 unwired 逐字", "未接線（還沒做）—— 這一段在本頁沒有在運作"),
                 ("去哪補（線框逐字）", "目前只在舊分頁「🔬 個股」與「🏆 個股組合」看得到；"
                                       "它不會在本頁自己亮起來"),
                 ("線框 live 逐字（改名提案的欄位）", "等幅量測位＝頸線 ＋ 型態高度；型態起算價位；"
                                                     "型態失效價位；量測位／失效位距離比"),
                 ("線框 flags", "★待拍板（合規改名）／★待拍板（本頁要不要收）／偏離核准線框／單組結論"),
                 ("線框 missing 逐字", "型態未明 —— 這種時候不會給任何可操作的數字，"
                                       "也不會補一個好看的值"))},
        ],
        "inspect.stock.detail": [
            {"state": "unwired", "title": "葉1-A 個股明細 7 段（依序 · 單欄堆疊）",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": demo(
                 ("線框 unwired 逐字", "本頁還沒有個股明細（還沒做）—— 一張卡，"
                                       "刻意把 7 段的名字全部列出來"),
                 ("線框 unwired 逐字（理由）", "只寫「明細未接線」你不會知道自己少看了什麼，"
                                              "列出來至少知道該去舊分頁找哪幾段。按幾次都一樣"),
                 ("線框 live 逐字（7 段名字）", "K 線＋均線 → 357 評價河流圖 → 財報領先指標 →"
                                               " VCP／布林 → 月營收 → 什麼時候買賣 → 心理檢查"),
                 ("圖表容器", "規格 ① 逐字：K 線與 357 河流圖只出現在兩支 detail 的 live 文字，"
                              "而那兩支現況未接線 ⇒ 目前無任何一塊需要掛圖表容器；"
                              "⛔ 不得預先把圖表容器畫成佔位"))},
        ],
        "inspect.etf.detail": [
            {"state": "unwired", "title": "葉1-B ETF 明細 7 段（骨架同 A、內容全換）",
             "value": None, "level": None, "badge_n": rb(state="unwired"),
             "facts": demo(
                 ("線框 unwired 逐字", "本頁還沒有 ETF 明細（還沒做）—— 同 A，卡上列出 7 段名稱。"
                                       "按幾次都一樣"),
                 ("線框 live 逐字（7 段名字）", "淨值 vs 市價走勢 → 折溢價帶 → 配息紀錄與以息養股試算"
                                               " → 成分股與集中度 → 同儕 7 維評分 → 標準差買賣帶 → 破發檢查"),
                 ("規格 ⑤ 逐字", "骨架同 A、內容全換 —— 與 A 沒有一個欄位共用"))},
        ],
        # ── n3 l2｜葉2 批次（表格走總管拍板 1：用 facts 描述掉，⛔ 不畫真表格）────
        "inspect.batch.form": [
            {"state": "idle", "title": "葉2 表單 ＋ 🚀 批次分析（貼一串代碼，可混貼）",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "空白 text_area ＋ placeholder"),
                 ("線框 live 逐字", "〔貼一串代碼（可混 個股／ETF；逗號、空白或換行分隔）〕"
                                    "＋〔型別篩選（只影響顯示，不影響取數）〕＋ ▌🚀 批次分析 ▐"),
                 ("⛔ 它不是頁主 CTA", "線框 mainCTA 欄只列葉1 那顆；規格 ① 逐字："
                                       "它與主 CTA 同款，但不是頁主 CTA"),
                 ("線框 empty 逐字", "▨ 你還沒貼任何代碼"))},
        ],
        "inspect.batch": [
            {"state": "idle", "title": "葉2 批次評分表 · 冷啟動",
             "value": None, "level": None, "badge_n": rb(state="idle"),
             "facts": demo(
                 ("線框 idle 逐字", "⬜ 尚未批次分析"),
                 ("去哪補（線框逐字）", "在表單貼上代碼後按「🚀 批次分析」"),
                 ("線框 loading 逐字", "⏳ 骨架表（保留表頭與列數，不會整片空白）"))},
            {"state": "live",
             "title": "葉2 批次評分表 ＋ 下鑽（點任一列就地展開該檔明細，依型別走 A 或 B）",
             "value": None, "level": "🟢 這一塊是接上的", "badge_n": rb(state="live"),
             "facts": demo(
                 ("⚠️ 表格⛔ 沒有畫成真表格", "總管拍板 1：用卡片的 facts 描述掉 —— 理由與"
                                              "「表格能力未落地」見缺口 P1"),
                 ("四個欄（規格 ① 逐字）", "代碼｜型別｜狀態｜明細"),
                 ("桌機／平板（規格 ① 逐字）", "表頭列高與列高固定、數值欄靠右 ＋ 等寬字 ＋"
                                              " tabular-nums ＋ 不換行"),
                 ("手機 ≤640（規格 ① 逐字）", "走卡片流：一列＝一張卡、每卡至多 4 對 key/value，"
                                              "其餘收進展開佐證"),
                 ("部分失敗（規格 ④B 逐字）", "整張卡維持正常態，⛔ 不轉紅 ——"
                                              "紅色留給「整批都算不出來」那一種"),
                 ("失敗列的處置（線框逐字）", "失敗的那一列不會從清單裡消失 —— 該列保留、列首標紅、"
                                              "各格 — ＋ ⚠︎"),
                 ("⚠️ 未落地（規格 ④B 新發現）", "線框要求「整列可點」，但實作的 on_select／"
                                                 "selection_mode 0 命中，現況是「選單挑一檔」；"
                                                 "分類待判 —— 見缺口 P7"))},
        ],
        # ── n4 展開佐證（三塊 src 全 null）────────────────────────────────────
        "inspect.evi.cards": [
            {"state": "live", "title": "〔展開佐證 ▸〕判決卡區塊級佐證（門檻與算式怎麼來的）",
             "value": None, "level": "🟢 常駐觸發器", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字（第 1 條）", "健康度 —— 六因子各自的分數與權重、"
                                              "哪幾項計入／未計入"),
                 ("線框 live 逐字（第 2 條 ＝ 357 算式住的地方）", "估值（357）—— 三段門檻"
                                                                  "（7% / 5% / 3%）與各自對應的價位；"
                                                                  "平均年現金股利、實際有配息的年數"),
                 ("線框 live 逐字（第 3 條）", "籌碼 —— 近 20 日窗口、集中度門檻、"
                                              "連續性與單日爆量的判定式"),
                 ("線框 live 逐字（第 4 條）", "每一項各自的資料時點與來源名"),
                 ("觸發器位置（線框逐字）", "位置在區塊標題列的最右側、與標題同一行右對齊，"
                                            "標題本身不可點"),
                 ("線框 degraded 逐字", "每一個各給一顆 —— 未接線／門檻失準／出錯三種情況的"
                                        "原因逐個不同，合起來一顆就看不出是哪一個"))},
        ],
        "inspect.evi.overlap": [
            {"state": "live",
             "title": "〔展開佐證 ▸〕個股與 ETF **重疊近零**（合併的是入口，不是內容）",
             "value": None, "level": "🟢 常駐，⛔ 不隨狀態消失", "badge_n": rb(state="live"),
             "facts": demo(
                 ("線框 live 逐字（前半）", "本頁把個股與 ETF 放在同一個入口，"
                                           "但兩邊看的東西幾乎完全不同"),
                 ("線框 live 逐字（後半）", "合併的是入口與骨架，不是內容 —— 所以你查 ETF 時"
                                           "看不到本益比、查個股時看不到折溢價，"
                                           "那不是漏了，是它本來就不存在"),
                 ("⚠️ 13／6 兩個數字", "線框自標「紅隊的比對結果，本組未複驗」⇒ 引用時照此打折，"
                                       "⛔ 不得寫成畫面上的權威統計（缺口 P6）"),
                 ("⛔ 它不是資料功能", "規格 ③③ 逐字：它是「兩種標的為何共用一頁」的設計理由揭露，"
                                       "⛔ 不得實作成「這檔股票被哪些 ETF 持有」"))},
        ],
        "inspect.evi.cost": [
            {"state": "live", "title": "〔展開佐證 ▸〕這裡的「成本」怎麼算的",
             "value": None, "level": "🟢 常駐，⛔ 不隨狀態消失", "badge_n": rb(state="live"),
             "facts": demo(
                 ("現行文案（規格 ③② 擬稿逐字 · now）", "這裡的成本是你自己填的均價"),
                 ("現行文案（規格 ③② 擬稿逐字 · why）", "這一頁沒有在替你算成本 ——"
                                                        "你在持股表填的那個均價，系統原樣拿來用、"
                                                        "不會替你重算；同一個代號填了兩列時，"
                                                        "只留第一列，另一列會被丟掉並列出來給你看"),
                 ("⚠️ 為何不照線框原文", "總管拍板 4：規格明文禁止把某一種成本口徑寫上畫面 ——"
                                         "系統根本沒在算成本，寫了就是宣稱一件它沒做的事。"
                                         "被禁的那一句與完整理由逐字記在缺口 P4"),
                 ("⚠️ 卡標也被截掉一半", "線框 name 的括號含規格點名禁上畫面的內部詞 ⇒ 本輪只取前半，"
                                         "被拿掉的那半逐字記在缺口 P5"),
                 ("⛔ 連引述都不行", "本輪的守衛是逐張卡掃的 —— 把那條禁令「引述」在卡面上，"
                                     "同樣會把被禁的字印出來。⇒ 那些字只出現在本頁附錄與層註"
                                     "（內部揭露），⛔ 不出現在任何一張卡上"),
                 ("★待拍板（落點）", "線框自標：規格既有的四個落點裡沒有本頁，本檔是依派工單加入 ——"
                                     "⛔ 本組不代為裁決（缺口 P4）"))},
        ],
    }


#: 「🔬 查一檔」頁**本輪查到的衝突與洞**，逐條登記並**畫在畫面上**（客戶要求：就地標明、
#: 寫進附錄、⛔ 不自行裁決）。🔴 每一條同樣是 **⚠️ 單組／兩組調查結論，未經第三方驗**。
#:
#: ⭐ **編號前綴為何是 `P`**：本產生器現用 `G`＝跨頁 chrome、`W`＝「📖 憑什麼」、
#:    `F`＝「🔍 找標的」；`P` 在本產生器內實測 0 命中（⛔ 不用 I／O —— 與 1／0 易混；
#:    ⛔ 不用 N —— 撞 CLAUDE.md §-1.2 的 N-1~N-3）。
#: ⚠️ **⛔ 不要把 `P1`~`P12` 與規格引用的 `P-1` 混為一談**：後者是
#:    S1-5_HOLDINGS_MODEL 的一個未判定項（成本口徑的權重定義），出現在 P4 的內文裡。
#:    本產生器的慣例是**自己的缺口編號⛔ 不帶連字號**（G1／W5／F17／P1），
#:    **引用外部編號一律帶連字號**（D-2／D-08／G-24／U-2／P-1）—— 兩者靠連字號區分。
INSPECT_SPEC_GAPS: tuple[tuple[str, str, str], ...] = (
    (
        "P1",
        "🔴 **表格能力未落地**：契約層 src/ui_v2/markup.py **⛔ 沒有任何產表格的公開函式** ⇒ "
        "本頁唯一用到表格的那一塊（批次評分表）只能用卡片的 facts 描述掉。",
        INSPECT_TABLE_DISCLOSURE + "／／" + INSPECT_TABLE_DISCLOSURE_WHY
        + "／／**規格端要求長這樣（UI_PAGE_INSPECT ① 表格三斷點段逐字）**："
          "「只有 inspect.batch 用到（實作 st.dataframe，AST 全檔恰 1 處；四欄＝代碼｜型別｜"
          "狀態｜明細）；桌機／平板走 UI_COMPONENTS §4 表格…手機 ≤640 走 §4 卡片流"
          "（一列＝一張卡、每卡至多 4 對 key/value）」。"
          "⇒ **本輪畫得出來的只有「四欄是哪四欄」與「三斷點各自長什麼樣」的文字描述**，"
          "⛔ 不是表格本身；**真正的解**是把表格能力補進 src/ui_v2/，那要動 src/ 真實作 "
          "⇒ ⛔ 不在本輪授權範圍。"
          "⚠️ **複驗程度，據實寫**：「markup 公開函式恰 5 個／字串常值 0 個表格標籤」"
          "由本組 ast 實測，派工規格另轉述有一組同向的實測結果 —— **但兩組用的是同一種方法**"
          "（ast 掃字串常值）⇒ ⛔ 不等於方法獨立的複驗，引用時照此打折（CLAUDE.md §-2 規則 6）。",
    ),
    (
        "P2",
        "🔴 **主 CTA「🔍 載入完整分析」⛔ 沒有渲成真的 pv-btn-primary 鈕**，"
        "與「🔍 找標的」頁的「🎯 開始選股」同樣只有文字 ⇒ **兩頁一起缺，⛔ 本輪不單邊補**。",
        INSPECT_CTA_DISCLOSURE + "／／" + INSPECT_CTA_DISCLOSURE_WHY
        + "／／**規格端的樣子（UI_PAGE_INSPECT ① 按鈕段逐字）**：主 CTA ＝ UI_COMPONENTS §3 "
          "主 CTA（最小高度 40、內距與字級固定、底與框走 ink、hover 轉 ochre、"
          "焦點環 2px solid focus 並外推 2px），在表單內、住預設葉 l1、form 內只有這一顆。"
          "／／⚠️ **要補就兩頁一起補**：只補本頁會讓 TODAY／FIND／INSPECT 三頁的同一種元件"
          "長出兩種樣子 —— 那是畫面自己在說謊（對照 CLAUDE.md §1）。"
          "⇒ **屬另一輪**，⛔ 本輪不動；⛔ 也不得把本條讀成「已排程」。",
    ),
    (
        "P3",
        "🔴 **💰 獲利能力「5 指標只有 3 格」**：本輪**照規格畫 3 格**，"
        "⛔ **不得**採納「先畫兩張未接線卡把第 2 排佔出來」的那個建議。",
        "總管拍板（理由逐字）：那是某組的建議，非客戶裁示、非總管拍板。原型照規格畫、不發明。"
        "登記成缺口並註明該建議的身分。"
        "／／**那個建議的身分（規格 ③① 自己標的，逐字）**："
        "「🔴 WM 本組建議（⛔ 非客戶裁示、⛔ 非總管拍板）：以「先畫兩張 unwired 卡」為現行落地態」"
        "—— 該份自己就標明了它**只是一組的建議**。"
        "／／**應然與現況的差距（規格 ③① (a)(b) 逐字）**：線框指定「3 欄 × 2 排，共 5 格"
        "（5 ÷ 3 → 第 2 排 2 格 ＋ 1 個空位）」，第 1 排三格已接線、第 2 排〔稅後淨利率〕〔ROE〕"
        "明標未接線；實作端 `_labels` 只有三個、`grid()`「天然不足一列的保持原欄數、不硬湊三欄」"
        "⇒ 畫面上只有一排三格，稅後淨利率與 ROE **無卡、無佔位、無未接線標示**。"
        "／／⚠️ **缺口⛔ 不准因此被藏起來**：本輪把「第 2 排兩格未接線」寫進那三張卡的 facts 與層註，"
        "理由是規格 ③① 逐字「現況「只有一排三格」會讓使用者看不出自己少看了兩個指標 —— "
        "那是 CLAUDE.md §1 要防的「把缺口掩蓋成完整」」。"
        "／／⚠️ **接線時另有兩個坑（規格 ③① 逐字，⛔ 本輪不動）**：實作裡寫死的「其餘兩格」"
        "在 5 格後就是錯的；ROE 那一格上游回的是槓桿警語而非好壞判決語，"
        "⛔ 不得照抄前三格的形狀、⛔ 不得替它編一句中文判讀語。"
        "／／⚠️ 規格另記：**核准線框在這一格自己前後不一致**（說明欄寫 2 排、格子清單只列 3 個），"
        "該不一致登記在線框的偏離表 DEV-20。",
    ),
    (
        "P4",
        "🔴 **成本口徑（D-2）：本輪畫誠實擬稿版；畫面上⛔ 不得出現規格禁止的口徑宣稱。** "
        "★待拍板（落點）—— 規格既有的四個落點裡**沒有本頁**。",
        "總管拍板（理由逐字）：規格明文「⛔ 畫面不得寫『本系統採加權移動平均法』」。"
        "畫面上⛔ 不得出現該句或任何等義宣稱；登記成缺口（★待拍板・落點）。"
        "／／**三個未解問題（規格 ③② (c) 逐字，⛔ 本組不代為決定）**："
        "(1) **落點偏離** —— D-2 的既有落點是「頁4 葉1／頁4 葉2／Part 5 再平衡區塊」"
        "＋一個已失去載體的落點，**四個裡沒有本頁**；線框自陳是依派工單加入，"
        "旗標「★待拍板（落點）／偏離核准線框／單組結論／未驗證」。"
        "(2) **權重未定義** —— S1-5_HOLDINGS_MODEL 的 **P-1** 指出母法只說「統一採加權移動平均法」，"
        "**沒說權重是什麼（金額 vs 單位數）**；P-1 本身是建議，決定權未行使。"
        "(3) **實作不存在** —— 規格 ③② (b) 實測：該口徑名詞在 src/ 與 shared/ 全 0 命中；"
        "均價是使用者自己填在試算表的欄位，系統不計算成本；"
        "同代號重複列的處置是「保留首見、丟棄其餘」；且本頁根本不碰成本"
        "（成本／均價相關欄名在本頁實作檔 0 命中）。"
        "／／⇒ **在 (3) 成立的前提下，畫面上寫那句話就是宣稱一件系統沒做的事**"
        "（違 CLAUDE.md §1，同客戶「不要假裝做得到」）。本輪畫的是規格 ③② (c) 給的**誠實擬稿**"
        "（規格自註：文案擬稿，⛔ 非客戶逐字）。"
        "／／📌 **落點若拍板為「放」**：線框自己的提案是綁在 ETF 明細第 3 段"
        "「配息紀錄與以息養股試算」的佐證裡（該段現況未接線），⛔ 不掛整頁 —— "
        "**此為線框單組提案，⛔ 本組轉錄、未背書。**",
    ),
    (
        "P5",
        "⭐ **本輪自己撞到的新衝突**：成本那一塊的**卡標被截掉後半**，"
        "因為線框給的 name 含規格點名**禁止上畫面**的內部詞。",
        "**衝突長這樣**：本產生器既有慣例（本檔 §3 註解逐字）是「規格給了名字的用規格的名字，"
        "沒給的直接用 block key…⛔ 不發明一組沒有出處的中文標題」；"
        "而線框該塊的 name 逐字是「〔展開佐證 ▸〕這裡的「成本」怎麼算的"
        "（D-2：加權移動平均 vs FIFO）」，括號那半**同時命中**規格 ③② 的禁令 —— "
        "規格逐字：「⛔ 使用者看到的字面不得出現「FIFO」「加權移動平均」「D-2」「L1」"
        "這類內部詞或系統做不到的口徑宣稱」。"
        "／／**本組的處置（⛔ 這是處置，不是裁決）**：**卡標只取前半**"
        "（〔展開佐證 ▸〕這裡的「成本」怎麼算的），被拿掉的後半**逐字記在本條**；"
        "**內部詞仍出現在本附錄與層註裡** —— 本組據此畫了一條線："
        "**卡面 ＝ 使用者看到的字面（受禁令拘束）／附錄與層註 ＝ 內部揭露（可寫內部詞）**，"
        "且本產生器既有的 FIND 附錄本來就寫了 L1／D-08 這類詞。"
        "／／⚠️ **本組可能判錯的地方，據實寫出來**：若認為整份原型（含附錄）都算"
        "「使用者看到的字面」，那本組在附錄裡寫內部詞就是超過；"
        "若認為線框 name 只是主題標籤、不構成口徑宣稱，那本組截掉卡標就是超過。"
        "**兩種可能本組都無法自行排除** ⇒ 登記、⛔ 不裁決。",
    ),
    (
        "P6",
        "⚠️ **「13 個個股概念／6 個 ETF 概念 0 命中」是轉錄，⛔ 不是任何一組實測的數字。**",
        "規格 ③③ (c) 逐字：「13／6 這兩個數字線框自標「紅隊比對結果、本組未複驗」"
        "⇒ 引用時必須照此標明，⛔ 不得當成已查證的事實，⛔ 不得把它寫成畫面上的權威統計。"
        "若要讓它成為可宣稱的數字，需另派一組逐項重做該比對」。"
        "／／⇒ 本頁該塊的 facts 已就地標明它是轉錄；**⛔ 本組也沒有重做那個比對**。"
        "／／⚠️ **另一個更容易讀錯的地方（規格 ③③ (a) 逐字）**：這一塊是"
        "「兩種標的為何共用一頁」的**設計理由揭露，⛔ 不是資料功能** —— "
        "⛔ 不得寫成、也⛔ 不得實作成「這檔股票被哪些 ETF 持有」。"
        "規格 (b) 實測：repo 內只有 ETF × ETF 的持股重疊函式（兩者都吃兩份 ETF 持股），"
        "個股反查**查無實作**（單次 grep，⛔ 非 AST、⛔ 不得當窮舉）。",
    ),
    (
        "P7",
        "🔴 **「整列可點」在本頁未落地**，且**分類待判**（實作待修 vs 線框待改）⇒ ⛔ 不代為裁決。",
        "規格 ④B 末項逐字（該份自標為「WM 本組新發現（須覆核）」）："
        "「線框 inspect.batch.live 逐字「點任一列就地展開該檔明細」＋「✅ 整列可點」，"
        "但實作 st.dataframe 的 on_select／selection_mode **0 命中（WM AST＋grep）**，"
        "下鑽走的是另一顆 st.selectbox。⇒ **「整列可點」在本頁未落地**，"
        "現況是「選單挑一檔」。⛔ 不得寫成已做到；**分類待判**（實作待修 vs 線框待改）」。"
        "／／⇒ 本頁該塊的 facts 已就地標明現況；**⛔ 本組不代為判它該往哪邊改**。"
        "⚠️ 線框該塊的 flags 另含「總管拍板（整列可點）」與「推翻 2026-09-14 規格」"
        "「已回到核准線框」「前提不乾淨」—— **「總管拍板」講的是線框該怎麼畫，"
        "⛔ 不等於實作已經做到**，這正是本條要分開的兩件事。"
        "／／⚠️ **同一塊還有第二個張力**：規格 ④B 逐字「葉2 部分失敗：整張卡維持正常態，⛔ 不轉紅」"
        "（紅色留給「整批都算不出來」），但線框的 error 格寫的是「🔴 3 檔中 1 檔失敗」。"
        "本組讀法是「那個紅講的是**列首**、不是卡的徽章」，"
        "**但那是本組的讀法、⛔ 不是規格明寫的** ⇒ 一併登記；"
        "本輪因此**只畫正常態與冷啟動兩張卡**，⛔ 不畫一張紅的批次卡。",
    ),
    (
        "P8",
        "⭐ **本輪自己撞到的第二個新衝突**：線框本頁大量使用「為…什麼：」句式，"
        "與本產生器一道**全檔守衛**相撞 ⇒ 本輪改引**不含那三字的逐字片段**，"
        "⛔ 不擴大允許清單、⛔ 不弱化守衛。",
        "**衝突長這樣**：客戶 2026-09-22 ④ 明示第五頁用 SSOT 的「📖 憑什麼」，"
        "本產生器因此有一道守衛 —— 產物全檔遮掉允許清單後**不得再出現那三個字**，"
        "而允許清單**只收線框／規格的逐字名稱**、⛔ 不收本檔自己的散文。"
        "／／而本頁線框的 states 文案**大量**用「為…什麼：〈原因〉／去哪補：〈做法〉」這組句式"
        "（它正是規格要求的誠實兩段式）⇒ 逐字照引就會命中守衛。"
        "／／**本組的處置（⛔ 這是處置，不是裁決）**：**⛔ 不動守衛、⛔ 不往允許清單塞東西**，"
        "改為**只引那組句式裡不含那三字的部分**（多半是「去哪補：」那一段與結論句），"
        "並在此登記。理由：允許清單每多一條，守衛就弱一分；"
        "而本頁 22 個線框 name **一個都沒有命中**那三字（本組 node 實測）"
        "⇒ **卡標完全不受影響**，受影響的只有 facts 裡的引文長度。"
        "／／⚠️ **本組可能判錯的地方**：若認為「逐字引線框 states」比「守衛維持最嚴」重要，"
        "那正解是把那些 states 逐字加進允許清單。**本組無法自行排除這個可能** ⇒ 登記、⛔ 不裁決。",
    ),
    (
        "P9",
        "⚠️ **線框 8 個 ★待拍板 旗標逐條登記**（本組 node 實測，⛔ 不是轉述）—— "
        "本輪**一條都沒有替客戶決定**。",
        "逐條（block ⇒ 旗標逐字）："
        "(1) chrome.asof ⇒ ★待拍板；"
        "(2) inspect.form ⇒ ★待拍板；"
        "(3) inspect.stock.health ⇒ ★待拍板（三格改名）；"
        "(4) inspect.stock.valuation ⇒ ★待拍板（合規改寫）；"
        "(5) inspect.pattern_measure ⇒ ★待拍板（合規改名）；"
        "(6) inspect.pattern_measure ⇒ ★待拍板（本頁要不要收）；"
        "(7) inspect.stock.detail ⇒ ★待拍板；"
        "(8) inspect.evi.cost ⇒ ★待拍板（落點）。"
        "／／⚠️ 其中 (6)「本頁要不要收」是**版面層級**的未決 —— 也就是"
        "**「🎯 型態等幅量測」這一塊該不該出現在本頁本身還沒拍板**；"
        "本輪照線框畫出它的版面位置與未接線態，⛔ 不代表本組認為它該留。"
        "／／⚠️ 線框同時另有一批非 ★ 的旗標（偏離核准線框／偏離現行 code 現況／偏離 UI-E／"
        "合規改寫／單組結論／未驗證／前提不乾淨／推翻 2026-09-14 規格／已回到核准線框），"
        "**⛔ 本條沒有窮舉它們** —— ⛔ 不得把本條讀成「未決項只有這 8 筆」。",
    ),
    (
        "P10",
        "🔴 **本頁⛔ 沒有畫 #2／#4／#8／#9 四顆徽章**，其中 **#4 與其餘三顆不同類** —— "
        "⛔ 不得混為一談；#9 另有一個**母體歧義**尚未解決。",
        "規格 ② 表逐字：#2 載入中「實作 0 處（連 import 都沒有）；st.spinner 亦 0 ⇒ 實作待補，"
        "⛔ 在補上之前不得拿 #3 冒充載入中」；#8 「實作只有單一 UI_EMPTY，未依 miss_reason 拆 #7／#8…"
        "⛔ 不得把 missing 畫成 #8（#8 重跑無效，畫錯＝給錯指引）」；#9 「0 處」；"
        "#10 「不適用…⇒ 不畫 #10；⛔ 不得併進 #8」。"
        "／／⭐ **#4 是「刻意不出現」，⛔ 不是「待補」** —— 規格 ② 逐字："
        "「這不是缺陷：實作檔頭逐字「本頁沒有任何一格會判 UI_DEGRADED，這是刻意的」，"
        "線框 inspect.profit.degraded 亦自陳「本頁目前不會出現這一態」」。"
        "⇒ 把 #4 跟 #2／#8／#9 一起寫成「待補」就是**把一個設計決定讀成缺陷**。"
        "／／🔴 **#9 的母體歧義（規格 ② 末段逐字，該份自標「WM 判定（須覆核）」）**："
        "「inspect.profit 的「3 / 5」講的是**接線度**，inspect.batch 的「N/M」講的是**資料涵蓋度** —— "
        "兩者**母體不同類**。⛔ 共用 #9 時**必須在 tooltip 寫明母體**…否則使用者會把"
        "「還沒做」讀成「這一輪沒拿到」」。"
        "⇒ **在母體寫法定案之前，本頁一個 N／M 都不寫**（同 FIND 缺口 F6 的處置）。"
        "／／⚠️ 規格 ② 另有一條 fail-safe 逐字：「分子分母拿不到 → 一律降 #7『缺漏 · 可重跑』，"
        "⛔ 不得退回 #1『正常』」—— 契約層的 resolve_badge 本來就是這樣寫的（本組實測），"
        "本檔⛔ 沒有另立第二把尺。",
    ),
    (
        "P11",
        "⚠️ **規格自己的複驗分級：本頁的實作面與線框面盤點**全部是**單組結論**，"
        "⛔ 不得當前提；**總管對本頁只下過一項實查結論**。",
        "規格檔尾「複驗分級」逐字："
        "「**總管實查**＝（本檔**無**此類項目 —— 總管未對本頁下過實查結論；"
        "⛔ 不得把派工單轉述當成總管實查）」；"
        "「**總管更正（2026-09-16）**＝**僅 chrome.footer 一項**」（原登記「缺頁尾免責」為誤判，"
        "已更正為非缺陷，理由見本頁 n0 層註）；"
        "「**INV-7A 單組（實作面，未複驗，⛔ 不得當前提）**＝本頁實作檔的全部盤點」；"
        "「**INV-7B 單組（線框面，未複驗，⛔ 不得當前提）**＝線框解析結果」。"
        "／／**轉錄（非任何一組實測）共三項**：13／6 個概念 0 命中（見 P6）；"
        "「上游 L3 五欄都有回」（線框單組讀、未跨檔窮舉、未實跑）；"
        "Streamlit bundle 自帶的 columns 斷點（另一份頁規格的實測，本份未重驗）。"
        "／／⚠️ **本產生器自己也一樣**：本頁的 22 筆版面、狀態挑選與上列各條，"
        "都是**本組單組**的 node／import 實測 ＋ 判讀，**⛔ 未經第二組複驗**"
        "（CLAUDE.md §-2 規則 6）。⛔ 不得寫進 commit message 或 PR 描述當成已完成的事實。",
    ),
    (
        "P12",
        "⚠️ **3/2/1 的 tablet=2 在 Streamlit 端未落地**；**首屏可見範圍三個斷點一律需實機量測** "
        "⇒ ⛔ 不猜、⛔ 不得寫推導值冒充量測。",
        "規格 ① 逐字：「3/2/1 的 tablet=2 未落地：grid(items, MAX_COLS) 三斷點恆 3 欄；"
        "≤640 堆成 1 欄是 Streamlit bundle 自帶的斷點（**此為另一份頁規格的實測，本份未重驗、"
        "照此打折**）⇒ 641–880 仍恆 3 欄，**登記為實作待修**」。"
        "／／同節另逐字：「**首屏可見範圍：三個斷點一律「需實機量測」**。"
        "本頁的 CSS 變數／style／media query／原始 HTML 開關**各 0 命中** ⇒ 排版全由 Streamlit "
        "自身 CSS 決定；另有兩個 repo 反解不出的高度來源 —— 分頁頭高與表單邊框高"
        "（由 Streamlit 版本決定，floor 見 requirements.txt）。⛔ 不猜、"
        "⛔ 不得寫推導值冒充量測」。"
        "／／⚠️ **這份 HTML 原型的 CSS 本身是對的**（.g-3-2-1 三段實測為 3/2/1，"
        "產生器結尾有守衛從 CSS 文字量），**但這份原型與 Streamlit 實作不是同一套 CSS** "
        "⇒ 量了這份也⛔ 不能拿去當 Streamlit 端的答案。"
        "／／⚠️ 規格**唯一可宣稱的是順序（不含高度）**：頁標題 → 說明 → 兩葉分頁頭 → 葉1 段標 → "
        "輸入表單 → 接線揭露 → 判型 →（三張判決卡｜判不出型別的卡）→ 💰 三格 → 明細卡。"
        "⚠️ 線框另逐字：**兩葉的 body 同一輪都會跑完**，葉只是視覺分組、不是執行閘門。",
    ),
)


def build_inspect_body() -> str:
    """「🔬 查一檔」頁的整頁標記。**全程在 `inspect_page_contract()` 之內**。

    🔴 標記一個角括號都不手打卡片：`markup.card_html` / `markup.grid_html` 產。
    🔴 **⛔ 不呼叫 `markup.layer_html`**：線框 `layers[]` 上⛔ 沒有任何層級網格欄數
       （本組 node 實測）⇒ 五層一律逐 block 全寬輸出，同前兩頁。
    """
    cards_by_block = build_inspect_cards()
    parts: list[str] = [
        # ── 就地揭露：**收起狀態也看得見**，⛔ 不藏進摺疊器 ──
        '<section class="pv-layer" id="pv-inspect-disclosure">',
        '<div class="pv-layer-label">'
        '🔬 查一檔 · 五層（葉外 ＋ 四層）22 block（版面定義在產生器內）</div>',
        f'<p class="pv-disclosure">{esc(INSPECT_LAYOUT_DISCLOSURE)}</p>',
        f'<p class="pv-meta">{esc(INSPECT_LAYOUT_DISCLOSURE_WHY)}</p>',
        # ⭐ 總管本輪拍板 1／2 的就地揭露 —— 理由逐字，⛔ 不得省
        f'<p class="pv-disclosure">{esc(INSPECT_TABLE_DISCLOSURE)}</p>',
        f'<p class="pv-meta">{esc(INSPECT_TABLE_DISCLOSURE_WHY)}</p>',
        f'<p class="pv-disclosure">{esc(INSPECT_CTA_DISCLOSURE)}</p>',
        f'<p class="pv-meta">{esc(INSPECT_CTA_DISCLOSURE_WHY)}</p>',
        f'<p class="pv-meta">{esc(INSPECT_PAGE_SHAPE_NOTE)}</p>',
        "</section>",
    ]

    with inspect_page_contract():
        for n, blocks in INSPECT_LAYER_BLOCKS.items():
            tier = inspect_tier_for_layer(n)
            leaves = INSPECT_LAYER_LEAF[n]
            leaf_text = "、".join(
                "葉外（兩葉共用）" if lf is None else f"{lf} {INSPECT_LEAF_NAME[lf]}"
                for lf in leaves
            )
            parts.append('<section class="pv-layer">')
            parts.append(
                f'<div class="pv-layer-label">{esc(INSPECT_LAYER_LABEL[n])} · n{n} · '
                f'{esc(leaf_text)} · 密度 {esc(tier)} · '
                f'block {len(blocks)} 塊：{esc("、".join(blocks))}</div>'
            )
            parts.append(
                f'<p class="pv-meta">components.CARD_TIERS[<span class="pv-mono">'
                f'{esc(tier)}</span>]：{esc(_tier_caption(tier))}</p>'
            )
            parts.append(f'<p class="pv-meta">{esc(INSPECT_LAYER_NOTE[n])}</p>')
            for block in blocks:
                cards = [markup.card_html(block=block, **card)
                         for card in cards_by_block[block]]
                assert cards, f"{block} ⛔ 沒有卡 —— 本頁 22 塊每一塊都要有至少一張"
                parts.append(markup.grid_html(block=block, cards=cards))
            parts.append("</section>")

    # ── 本頁的衝突與洞，逐條畫出來（客戶要求：就地標明、寫進附錄、⛔ 不自行裁決）──
    parts.append('<section class="pv-layer" id="pv-inspect-gaps">')
    parts.append('<div class="pv-layer-label">'
                 '附錄 · 「🔬 查一檔」頁本輪查到的規格衝突與未決項（逐條登記，⛔ 不代為裁決）</div>')
    parts.append(
        f'<p class="pv-meta">{esc("每一條都是：" + GAP_CAVEAT + "。⛔ 不得被引用為「已查證的事實」去支撐下一步決策（CLAUDE.md §-2 規則 6）。")}</p>')
    for gap_id, title, detail in INSPECT_SPEC_GAPS:
        parts.append(
            f'<p class="pv-meta"><span class="pv-mono">{esc(gap_id)}</span>　'
            f"{esc(title)}　{esc(GAP_CAVEAT)}</p>"
        )
        parts.append(f'<p class="pv-meta">{esc(detail)}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def build_inspect_html() -> str:
    """把「🔬 查一檔」整頁包成一個可切換的容器（預設 `hidden`，由側欄點出來）。"""
    return "\n".join([
        html_comment(
            "「🔬 查一檔」頁 ＝ **五層 22 block**（葉外 n0 ＋ 規格自己稱的「四層」n1~n4）。\n"
            "⛔ 本頁的版面定義住在產生器的 `INSPECT_LAYOUT`，**不在** `src/ui_v2/` 契約層、\n"
            "  **沒有** `tests/ui_v2/` 的測試守護 —— 同前兩頁的作法（客戶拍板的選項 1），\n"
            "  後果已就地揭露在本頁最上方與附錄 P1~P12。\n"
            "⭐ 標記怎麼來的：產生期間把 `markup.page_today` **暫時**換成本頁的版面契約，\n"
            "  卡片與網格仍由 `markup.card_html` / `grid_html` 產出；產完**立刻還原**。\n"
            "⭐ **本頁⛔ 沒有補任何一條欄數 CSS**：cols 全集只有 1/1/1 與 3/2/1，\n"
            "  兩種契約層都已經產了（與「🔍 找標的」頁相反，那一頁補了兩條）。\n"
            "⭐ **本頁⛔ 沒有 n5**，五層恰落在 `components.tier_for_layer()` 的定義域內\n"
            "  ⇒ ⛔ 刻意不抄前兩頁的 `*_N5_TIER` 繞法（那是「用不到的抽象」）。\n"
            "⛔ 本頁**沒有畫** #2 / #4 / #8 / #9 / #10 五顆徽章：規格 ② 的總結句逐字\n"
            "  「實際會出現在畫面上的是 5 態：#1／#3／#5／#6／#7」，\n"
            "  誤畫會在產生時變成 ValueError（代理的 BADGES_NOT_ON_PAGE 擋）。\n"
            "  ⚠️ #4 是規格明寫的**刻意不出現**，⛔ 與另外三顆「待補」不同類。\n"
            "⭐ **#5 這顆（未接線）本原型第一次畫得出來**：前兩頁一頁沒有適用對象、\n"
            "  一頁被規格撤回；本頁有三塊（型態等幅量測 / 個股明細 / ETF 明細）。\n"
            "⛔ 批次評分表**沒有畫成真表格**（總管拍板：contract 層無表格能力）——\n"
            "  登記在附錄 P1；主 CTA 也**沒有渲成真鈕**（兩頁一起缺）—— 登記在附錄 P2。"
        ),
        '<div id="pv-page-inspect" hidden>',
        "<main>",
        build_inspect_body(),
        "</main>",
        "</div>",
    ])


# ══════════════════════════════════════════════════════════════════
# 4.5 跨頁 chrome 的標記
# ══════════════════════════════════════════════════════════════════
def build_nav_html() -> str:
    """五頁切換（側欄式）。標籤**一律取自 `shared.ia_nav.PAGE_LABELS`，⛔ 不手抄**。

    - `today` ＝ current（`aria-current="page"`），其餘四個可點 → 顯示「此頁待做」佔位。
    - 五個都是 `<button>`，**⛔ 不是 `<a href>`** —— 那四頁沒有檔案，
      給一個連不到的 href 就是假裝它存在（§1）。
    - 收合用原生 `<details>`：**⛔ 不依賴 JS 才打得開**（JS 掛了仍是一顆可按的 summary）。
    - **預設收起**：`<details>` ⛔ 不帶 `open`，**三個斷點一律收起，只能手動展開**
      —— ★-08 已決（客戶 2026-09-22 拍板）。桌機自動展開已於同日移除，
      理由與被移除的三行見 `_NAV_JS_TEMPLATE` 上方的政策變更註記。
    """
    items = []
    for page_id, label in PAGE_LABELS.items():
        current = ' aria-current="page"' if page_id == PAGE_TODAY else ""
        items.append(
            f'<li><button type="button" class="pv-nav-item" '
            f'data-pv-page="{esc(page_id)}"{current}>{esc(label)}</button></li>'
        )
    return "\n".join([
        html_comment(
            "五頁切換：**側欄式**（客戶 2026-09-22 拍板 ①「做側欄式，不做頂部分頁」）。\n"
            "⛔ 這裡為何不是一列頂部分頁：\n"
            "  `app.py` 逐字記載 2026-09-07 的 FE-7~FE-16 曾把這五頁掛成第 1~5 個頂層頁籤，\n"
            "  與舊的 7 個並排 ⇒ 手機上頁籤列 7 變 12，舊的 7 個被擠出可視範圍，\n"
            "  客戶回報「很多 Tab 不見了」。2026-09-08 FE-35 客戶拍板方案 A 撤回該掛法。\n"
            "  ⇒ 本原型刻意不做頂部分頁列。\n"
            "⛔ 五個為何都是 button 而不是連結：另外四頁沒有檔案，\n"
            "  給一個連不到的 href 等於假裝它存在（CLAUDE.md 1 Fail Loud）。\n"
            "⭐ 預設收起：本 details ⛔ 不帶 open ⇒ **三個斷點一律收起，只能手動展開**。\n"
            "  ★-08 已決（客戶 2026-09-22 拍板：側欄預設收起，S2-UI_SPEC.md 7.2）。\n"
            "  同日客戶另拍板「桌機自動展開，修掉」，理由逐字：\n"
            "  「規格說收起、畫面卻展開，就是規格與實作打架」\n"
            "  ⇒ 產生器的導覽 JS 已⛔ 不含任何「依斷點把 nav.open 設為 true」的程式碼。"
        ),
        '<details class="pv-nav" id="pv-nav">',
        '<summary class="pv-nav-summary">☰ 五頁切換</summary>',
        '<nav class="pv-nav-body" aria-label="戰情室五頁切換（側欄式）">',
        '<ul class="pv-nav-list">',
        *items,
        "</ul>",
        f'<p class="pv-nav-why">{esc(NAV_WHY_SHORT)}</p>',
        "</nav>",
        "</details>",
    ])


def build_asof_html() -> str:
    """資料時點揭露列（**示意殼**）。

    位置：`S2-UI_SPEC.md §7.1` 逐字「緊接其下，**頁面標題下方第一行**，葉外」
    ⇒ 本檔把它放在 `.pv-head`（含 `.pv-title`）之後、`<main>` 之前。
    內容：**「尚未載入」態的逐字**（`§5.2` 表 ／ `S1-4 §3.8` 表）＋ 就地揭露它是形狀示意。
    🔴 **⛔ 一個真的日期時間都不填**（見 `ASOF_SHELL_DISCLOSURE`：L3 契約無 `as_of`）。
    """
    rows = "\n".join(
        f'<li><span class="pv-mono">{esc(fmt)}</span>　{esc(label)}</li>'
        for label, fmt in ASOF_NATURE_FORMATS
    )
    return "\n".join([
        html_comment(
            "資料時點揭露列 ＝ **示意殼**。\n"
            "⛔ 這一列沒有真時間，也**不准**填一個：\n"
            "  L3 canonical 契約 `get_macro_state()` 只有 9 個 key，沒有 `as_of` / `timestamp`；\n"
            "  `src/ui_v2/page_today.py` 已把 `chrome.asof` 登記為 WITHDRAWN_BLOCKS（已撤回）。\n"
            "  `src/ui/views/page_today.py::AS_OF_NOT_IN_CONTRACT` 逐字：\n"
            "  「寧可什麼都不寫，也不編一個時間出來」。\n"
            "下面那張表只是**可能的格式**（規格 5.1 第二欄逐字），⛔ 不是本頁的值。"
        ),
        '<section class="pv-asof" aria-label="資料時點揭露列（示意殼）">',
        f'<div class="pv-asof-line">{esc(ASOF_IDLE_TEXT)}</div>',
        # ⭐ 客戶 2026-09-14「狀態列、時點列、分頁列不得吃掉首屏」：
        #    線框自己的處置是「把主 CTA 的說明字與葉說明改成**點開才看**」——
        #    本檔沿用同一招。⛔ 被摺起來的只有**細節**；
        #    「這是示意、不是真資料」那句留在 summary 上，收起狀態也看得見。
        '<details class="pv-asof-more">',
        f'<summary class="pv-asof-sum">{esc(ASOF_SHELL_SUMMARY)}</summary>',
        f'<p class="pv-meta">{esc(ASOF_SHELL_DISCLOSURE)}</p>',
        f'<p class="pv-meta">{esc(ASOF_NO_FRESHNESS_NOTE)}</p>',
        '<ul class="pv-fmt">',
        rows,
        "</ul>",
        "</details>",
        "</section>",
    ])


def build_todo_html() -> str:
    """其餘**一**頁的「此頁待做」佔位（預設 `hidden`，由側欄點擊切出來）。

    ⚠️ 2026-09-22 起是**一**頁（「💼 我的持股」），⛔ 不是兩頁、三頁或四頁：
       「📖 憑什麼」「🔍 找標的」「🔬 查一檔」都已成為可切換的真頁
       （客戶本輪逐字：「側欄切到「🔬 查一檔」可顯示；
       其他一頁（💼 我的持股）仍顯示「此頁待做」」）。
    ⚠️ `pv-todo-name` 的**初始值**同步改為「💼 我的持股」——
       它原本是「🔬 查一檔」，而那一頁本輪已是真頁，留著會讓佔位卡的預設標題
       指到一個**不會再走到這裡**的頁（JS 每次切頁都會覆寫它，但初值仍應是真的）。
       ⚠️ 這是**事實更正**（上一版初值 `PAGE_LABELS[PAGE_INSPECT]`），⛔ 不是政策變更。
    """
    return "\n".join([
        '<section class="pv-todo" id="pv-page-todo" hidden>',
        '<div class="pv-todo-card">',
        '<div class="pv-todo-title">'
        f'<span id="pv-todo-name">{esc(PAGE_LABELS[PAGE_HOLD])}</span>'
        f"　·　{esc(TODO_HEADLINE)}</div>",
        f'<p class="pv-meta">'
        f'{esc(TODO_BODY.format(today=PAGE_LABELS[PAGE_TODAY], why=PAGE_LABELS[PAGE_WHY], find=PAGE_LABELS[PAGE_FIND], inspect=PAGE_LABELS[PAGE_INSPECT]))}</p>',
        f'<p class="pv-meta">{esc(TODO_BODY_SUPERSEDED)}</p>',
        f'<p class="pv-meta">{esc(NAV_WHY_SIDEBAR)}</p>',
        '<div class="pv-todo-back">',
        '<button type="button" class="pv-btn-secondary" '
        f'data-pv-page="{esc(PAGE_TODAY)}">← 回到 {esc(PAGE_LABELS[PAGE_TODAY])}</button>',
        "</div>",
        "</div>",
        "</section>",
    ])


def build_gaps_html() -> str:
    """把 `CHROME_SPEC_GAPS` 畫成可見的一段（**⛔ 不只留在 .py 裡**）。

    理由：登記在產生器裡只有讀 code 的人看得到；畫出來，看 HTML 的人也查得到
    —— 對照 CLAUDE.md §-2「沒查證的宣稱比沒有宣稱更危險」。
    """
    parts = ['<section class="pv-layer" id="pv-gaps">',
             '<div class="pv-layer-label">附錄 · 本輪查到的規格缺口（逐條登記）</div>',
             f'<p class="pv-meta">{esc("每一條都是：" + GAP_CAVEAT + "。⛔ 不得被引用為「已查證的事實」去支撐下一步決策（CLAUDE.md §-2 規則 6）。")}</p>']
    for gap_id, title, detail in CHROME_SPEC_GAPS:
        parts.append(
            f'<p class="pv-meta"><span class="pv-mono">{esc(gap_id)}</span>　'
            f"{esc(title)}　{esc(GAP_CAVEAT)}</p>"
        )
        parts.append(f'<p class="pv-meta">{esc(detail)}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def build_legal_html() -> str:
    """頁尾免責。**逐字 ＝ `app.py::_render_footer()` 的 SSOT**，由 `verbatim_sources()` 守衛。"""
    return "\n".join([
        html_comment(
            "頁尾免責：逐字 SSOT ＝ `app.py` 的 `_render_footer()`。\n"
            "本檔放的是一份**有守衛的複本** —— 產生時會讀 `app.py` 的原始文字逐字比對，\n"
            "不符就 AssertionError、⛔ 不產出 HTML。\n"
            "⚠️ 真正的解是把它抽成 L0 常數讓兩邊都 import，但那要動 `app.py`，\n"
            "  ⛔ 不在本輪授權範圍 ⇒ 已登記為 CHROME_SPEC_GAPS 的 G2。"
        ),
        f'<p class="pv-legal">{esc(COMPLIANCE_FOOTER_TEXT)}</p>',
    ])


#: ── 桌機自動展開：**已移除**（2026-09-22）──────────────────────────────
#: ⚠️ **有意識的政策變更，⛔ 不是漏刪；日期 2026-09-22；決策者：客戶。**
#: 客戶拍板逐字：「【拍板：桌機自動展開，修掉】理由：規格說收起、畫面卻展開，
#: 就是規格與實作打架。」⇒ ★-08 已決為「側欄預設收起」
#: （S2-UI_SPEC.md 7.2，commit 6035262；該節自己也點名本原型
#:   「執行層在桌機寬度不收起（不一致）」「須由原型擁有組依本裁示回頭對齊」）。
#:
#: **被移除的三行，保留加刪除線（⛔ 不是漏刪）**：
#:   ~~function syncOpen() { if (mq) { nav.open = mq.matches; } }~~
#:   ~~syncOpen();~~
#:   ~~if (mq && mq.addEventListener) { mq.addEventListener('change', syncOpen); }~~
#:
#: **兩邊理由並陳**：
#: ① **舊做法的理由（在它寫下當天是合理的，⛔ 不是寫錯）**：桌機橫向空間大，
#:    側欄展開著比較好用、少一次點擊；上輪 UH 組據此判斷「640 以下收起、
#:    641 以上展開」，並用它去滿足客戶 2026-09-14「狀態列、時點列、分頁列
#:    不得吃掉首屏」—— 在手機上那條確實被滿足了。
#: ② **被權衡掉的原因（客戶原話）**：「**規格說收起、畫面卻展開，就是規格與
#:    實作打架**」。★-08 已決為預設收起之後，舊做法讓標記層（`<details>`
#:    ⛔ 不帶 `open`）與執行層（JS 載入即 `nav.open = true`）給出兩個相反的
#:    答案 —— 好不好用是次要的，**規格與實作各說各話**才是要修的那件事。
#:
#: ⚠️ **`mq` 沒有一起拔掉，且⛔ 不得被讀成「自動展開還留著」**：它自本日起
#:    只剩一個用途 —— `show()` 裡判斷「現在是不是手機寬度」，用來在**選完頁
#:    之後**把側欄收起（`nav.open = false`）。⛔ 它不再、也⛔ 不得再把
#:    `nav.open` 設為 true。
#: ⚠️ **⛔ 刻意不改用 `window.innerWidth`**：CSS 的斷點是 `@media (min-width:…)`，
#:    沿用同一種 media query 才不會在 JS 裡長出第二份斷點定義（SSOT）。
_NAV_JS_TEMPLATE = """
(function () {
  var TODAY = %(today)s;
  var WHY = %(why)s;
  var FIND = %(find)s;
  var INSPECT = %(inspect)s;
  var TABLET_MIN = %(tablet_min)s;
  var nav = document.getElementById('pv-nav');
  var mq = window.matchMedia
         ? window.matchMedia('(min-width: ' + TABLET_MIN + 'px)')
         : null;

  // 側欄在**每個斷點都預設收起**（details 沒有 open 屬性），只能手動展開
  // —— ★-08 已決（客戶 2026-09-22 拍板：側欄預設收起）。
  // ⛔ 本段刻意沒有任何「依斷點把 nav.open 設為 true」的程式碼。
  // ⛔ 也刻意不在 CSS 裡把 summary 藏起來：JS 若沒跑，側欄仍要打得開。
  // ⇒ 不管 JS 有沒有跑，每個斷點都是收起 ＋ 一顆看得見的 summary，
  //    客戶 2026-09-14「分頁列不得吃掉首屏」在所有斷點都成立。
  // ⚠️ mq 只剩一個用途：下面 show() 判斷「是不是手機寬度」以便選完頁收起。

  // 五向切換（2026-09-22 第三次擴充）：🚦 今天 / 📖 憑什麼 / 🔍 找標的 / 🔬 查一檔 /
  //   其餘一頁（💼 我的持股）的「此頁待做」佔位。
  // ⛔ 刻意不用 if-else 串：五個容器各自只看自己那一個布林，
  //    少一個容器忘了關的機會（兩頁同時 visible 會讓畫面說謊）。
  function show(page, label) {
    var today = document.getElementById('pv-page-today');
    var why = document.getElementById('pv-page-why');
    var find = document.getElementById('pv-page-find');
    var inspect = document.getElementById('pv-page-inspect');
    var todo = document.getElementById('pv-page-todo');
    var isToday = (page === TODAY);
    var isWhy = (page === WHY);
    var isFind = (page === FIND);
    var isInspect = (page === INSPECT);
    today.hidden = !isToday;
    why.hidden = !isWhy;
    find.hidden = !isFind;
    inspect.hidden = !isInspect;
    todo.hidden = isToday || isWhy || isFind || isInspect;
    document.getElementById('pv-page-name').textContent = label;
    if (!isToday && !isWhy && !isFind && !isInspect) {
      document.getElementById('pv-todo-name').textContent = label;
    }
    var items = document.querySelectorAll('.pv-nav-item');
    for (var i = 0; i < items.length; i++) {
      if (items[i].getAttribute('data-pv-page') === page) {
        items[i].setAttribute('aria-current', 'page');
      } else {
        items[i].removeAttribute('aria-current');
      }
    }
    // 手機：選完就收起，⛔ 不讓分頁列繼續佔著首屏。
    // ⚠️ 這裡只會把側欄**關起來**（false），⛔ 永遠不會打開它。
    if (mq && !mq.matches) { nav.open = false; }
    window.scrollTo(0, 0);
  }

  var labels = {};
  var navItems = document.querySelectorAll('.pv-nav-item');
  for (var i = 0; i < navItems.length; i++) {
    labels[navItems[i].getAttribute('data-pv-page')] =
      navItems[i].textContent.trim();
  }
  var triggers = document.querySelectorAll('[data-pv-page]');
  for (var j = 0; j < triggers.length; j++) {
    triggers[j].addEventListener('click', function () {
      var page = this.getAttribute('data-pv-page');
      show(page, labels[page]);
    });
  }
})();
"""


def build_header_comment(meta: Mapping[str, str]) -> str:
    """HTML 檔頭註解。⚠️ 全段**不得出現連續兩個半形減號**（會提前關掉 HTML 註解）。"""
    lines = [
        "本檔是**機器產生**的靜態快照，⛔ 不要手改。",
        "",
        f"(a) 產生來源：{REPO.name} 分支 {meta['branch']}，"
        f"src/ui_v2/ 於 commit {meta['ui_v2_commit']}（{meta['ui_v2_commit_date']}）",
        f"    產生當下 HEAD ＝ {meta['head']}",
        f"    src/ui_v2/ 工作區{meta['worktree']}",
        f"    src/ui_v2 底下 {meta['src_count']} 個 .py 的內容 sha256 ＝ {meta['src_hash']}",
        "    （雜湊算法 ＝ 檔名 ＋ 位元組，依檔名排序後依序餵進 sha256；見產生器 main()）",
        f"(b) 產生日期：{meta['generated']}",
        "(c) ⚠️ **這是靜態快照：tokens.py / components.py 改了，這個檔不會自動跟著變。**",
        "    要它跟上，唯一的方法是重跑產生器（見 d）。",
        "    畫面上所有數字都是示意值，未接任何資料源。",
        "",
        "(d) 怎麼重建：跑 `python docs/v2/prototype/gen_today_v2.py`",
        "    （產生器**已進 repo**，就放在本檔旁邊 ⇒ 上面 (a) 那句「機器產生」**驗得到**；",
        "     它先前只活在某個 session 的暫存區，那時這句話沒有人能複驗）。",
        "    配方如下（六步，與產生器的實作一一對應）：",
        "    1. css ＝ markup.page_css('dark') 的輸出，**逐字**內嵌進 style 標籤（第一段）。",
        "    2. 取 markup.page_css('light') 的第一行（它就是 :root 那一條）。",
        "       先自驗：兩個模式的輸出去掉第一行後必須逐字相同；且該行必須等於用",
        "       tokens.get_token(name, mode) ＋ tokens.SPACING ＋ components.FONT_STACKS",
        "       獨立組出來的字串。兩道都過，才證明「只重新宣告 :root」與「整份重貼」等價。",
        "    3. 依序補四條規則：",
        "       R1 dark 的 :root（已在第 1 步內含，為預設）；",
        "       R2 @media (prefers-color-scheme: light) 內包 light 的 :root；",
        "       R3 :root[data-theme=\"dark\"] 換選擇器後的 dark 宣告；",
        "       R4 :root[data-theme=\"light\"] 換選擇器後的 light 宣告。",
        "       R3 不可省：屬性選擇器權重 (0,2,0) 高於 R2 的 (0,1,0)，",
        "       少了它，系統淺色下按「切換深色」會沒有反應。",
        "    4. 外殼樣式（橫幅／頁首／層標籤／按鈕／說明字）另外產：",
        "       數值全部取自 components.CARD_TIERS / CARD_BASE / CARD_VALUE / BUTTONS /",
        "       FOCUS_RING 與 page_today.HOLDINGS_EQUAL_WEIGHT_DISCLOSURE，",
        "       顏色與間距一律 var(…) token。⛔ 本檔不手打色碼、不手打 px。",
        "    5. 內容依 page_today.LAYERS 逐層產：",
        "       每個 block 走 markup.card_html() ＋ markup.grid_html()；",
        "       有登記層網格的層（實測只有第二層）整層走 markup.layer_html()。",
        "    6. 徽章總覽走 markup.badge_html(n, size=…)。",
        "    7. 跨頁 chrome 三塊（客戶 2026-09-22 拍板）另外產：",
        "       ① 五頁切換：**側欄式**（⛔ 不是頂部分頁）。五個頁名 import 自 L0 SSOT",
        "          shared/ia_nav.PAGE_LABELS，**⛔ 一個字都沒有手抄**；dict 宣告序 ＝ 畫面序。",
        "          🚦 今天 ＝ current，其餘四個點下去顯示「此頁待做」佔位。",
        "          **預設收起**：details ⛔ 不帶 open，且 JS ⛔ 不依斷點自動展開",
        "          ⇒ 三個斷點一律收起，只能手動點 summary 展開",
        "          （★-08 已決，客戶 2026-09-22 拍板；同日並拍板移除桌機自動展開）。",
        "       ② 資料時點列：**示意殼**。位置照 S2-UI_SPEC.md 7.1「頁面標題下方第一行、葉外」，",
        "          內容用「尚未載入」態的逐字。⛔ 一個真的日期時間都沒有填，",
        "          因為 L3 契約 get_macro_state() 只有 9 個 key、沒有 as_of",
        "          （src/ui_v2/page_today.py 已把 chrome.asof 登記為已撤回）。",
        "       ③ 頁尾免責：逐字 SSOT ＝ app.py 的 _render_footer()。",
        "          本檔放的是**有守衛的複本** —— 產生時讀 app.py 原始文字逐字比對，",
        "          不符就 AssertionError、⛔ 不產出 HTML（見 verbatim_sources()）。",
        "    8. 本輪查到的**規格缺口**畫成附錄一段（見產生器的 CHROME_SPEC_GAPS），",
        "       每條都標「單組／兩組調查結論，未經第三方驗」。",
        "    9. 「📖 憑什麼」頁（2026-09-22 新增，客戶拍板走「選項 1」）：",
        "       · **六層 22 block**（⛔ 不是四層；客戶逐字「客戶先前記的四層是簡化說法」）。",
        "         版面定義 ＝ 產生器裡的 WHY_LAYOUT，22 筆逐筆標出處",
        "         （規格 docs/v2/spec/UI_PAGE_WHY.md 的章節名 ＋ 線框",
        "          docs/v2/wireframe/wf_page_why.js 的 block key；⛔ 不寫行號）。",
        "       · ⭐ **它不在 src/ui_v2/ 契約層、沒有 tests/ui_v2/ 的測試守護** ——",
        "         這是客戶拍板的作法，而它的後果已**就地揭露在該頁畫面上**（該頁最上方 ＋ 附錄 W1）。",
        "       · 標記怎麼產的：產該頁期間把 markup.page_today **暫時**換成該頁的版面契約，",
        "         卡片與網格仍由 markup.card_html() / grid_html() 產出 ⇒ 與「真的有 page_why.py」",
        "         的產物逐字相同；產完**立刻還原**，「🚦 今天」頁仍走真正的 page_today。",
        "         產生器另有一道守衛：今天頁在代理前後各產一次，兩次逐字相同才算過。",
        "       · ⛔ 該頁**沒有畫任何 #10 徽章**：.bdg-10 不在 page_css() 的輸出裡，",
        "         硬畫出來會是一顆無配色的徽章（客戶已裁示該項登記為待修、本輪不動）。",
        "    10. 「🔍 找標的」頁（2026-09-22 同日新增，沿用同一套作法）：",
        "       · **六層 14 block**（客戶逐字「2. 6 層 14 block」）。版面定義 ＝ 產生器裡的",
        "         FIND_LAYOUT，14 筆逐筆標出處（規格 docs/v2/spec/UI_PAGE_FIND.md 的章節名 ＋",
        "         線框 docs/v2/wireframe/wf_page_find.js 的 block key；⛔ 不寫行號）。",
        "       · ⭐ **CSS 補了兩條**：本頁用到 3/3/1 與 2/1/1 兩組欄數，而 markup.page_css()",
        "         只產 page_today.BLOCK_COLS 裡出現過的（1/1/1 與 3/2/1）；grid_html() 對缺 CSS",
        "         的欄數**不報錯**，會讓那 3 塊**靜默塌成單欄**。客戶【拍板 1】選作法 (甲)：",
        "         由產生器補兩條 rule，欄數走 components.resolve_cols()、斷點走",
        "         components.BREAKPOINTS（⛔ 不寫死數字、⛔ 不碰底線私有符號），",
        "         並**就地揭露「規則形狀複製了一份」＝ 第二個真相源**（該頁最上方 ＋ 附錄 F2）。",
        "       · ⛔ 該頁**沒有畫** #2 / #5 / #8 / #9 / #10 五顆徽章（規格 ② 逐列判它們未落地",
        "         或不適用）；**兩塊沒有卡、沒有徽章**（情境快選 / 入選理由 —— 規格 ② 處置 2(a)",
        "         逐字「整塊不存在 ⇒ 不畫，⛔ 不得用 #5 冒充」），只畫它們的版面位置。",
        "       · 本輪查到的規格衝突與未決項共 17 條，逐條畫在該頁附錄（F1~F17），",
        "         客戶要求 6 逐字：「遇到規格衝突 → 就地標明、寫進附錄、⛔ 不自行裁決」。",
        "       · 五頁切換：🚦 今天 / 📖 憑什麼 / 🔍 找標的 是可切換的真頁，",
        "         其餘**兩頁**（🔬 查一檔 · 💼 我的持股）仍顯示「此頁待做」；",
        "         時點列與頁尾免責**五頁共用**（畫在外殼上，⛔ 不是每頁各一份）。",
        "",
        "⚠️ 例外揭露（依 CLAUDE.md §3.3 反捏造，據實記錄）：",
        "    body 的 font-family 用的是通用系統字堆疊，**沒有契約出處** ——",
        "    UI_TOKENS.md §B 的字型 token 尚未落地到 tokens.py",
        "    （components.FONT_STACKS 只有 mono 一條，且自陳是暫時落地點）。",
        "    因此本頁也**不設**內文字級與行高，讓它退回瀏覽器預設，",
        "    ⛔ 不自己挑一個看起來合理的數字。",
    ]
    text = "\n".join(lines)
    assert "--" not in text, "註解含連續兩個減號，會把 HTML 註解提前關掉"
    return "<!--\n" + text + "\n-->"


_TOGGLE_JS = """
(function () {
  var root = document.documentElement;
  var btn = document.getElementById('pv-theme-toggle');
  var now = document.getElementById('pv-theme-now');
  function current() {
    var manual = root.getAttribute('data-theme');
    if (manual) { return manual; }
    return (window.matchMedia &&
            window.matchMedia('(prefers-color-scheme: light)').matches)
           ? 'light' : 'dark';
  }
  function label() {
    var manual = root.getAttribute('data-theme');
    now.textContent = manual
      ? ('目前：' + (manual === 'dark' ? '深色' : '淺色') + '（手動）')
      : '目前：跟隨系統（預設深色）';
  }
  btn.addEventListener('click', function () {
    root.setAttribute('data-theme', current() === 'dark' ? 'light' : 'dark');
    label();
  });
  label();
})();
"""


def main() -> None:
    # ── 出門前的第 0 道：所有逐字複本先跟出處對過，⛔ 不符就不產 HTML（§1）──
    verbatim_sources()

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(REPO), *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    src_files = sorted((REPO / "src/ui_v2").glob("*.py"))
    digest = hashlib.sha256()
    for path in src_files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())

    dirty = git("status", "--porcelain", "--", "src/ui_v2")
    meta = {
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": git("rev-parse", "HEAD"),
        "ui_v2_commit": git("log", "-1", "--format=%H", "--", "src/ui_v2"),
        "ui_v2_commit_date": git("log", "-1", "--format=%ad", "--date=short",
                                 "--", "src/ui_v2"),
        "worktree": "乾淨（無未提交變更）" if not dirty else f"有未提交變更：{dirty}",
        # ⛔ 不寫死檔數:原版檔頭寫死「六檔」,而 src/ui_v2/*.py 早在舊 HTML 自己的
        #    產生點(ui_v2 commit b4cb83e)就已經是 7 個 ⇒ 那句話當時就是假的。
        #    CLAUDE.md §8.2.A.0 規則 2/4:會漂移的量測值一律現場量測或標日期。
        "src_count": str(len(src_files)),
        "src_hash": digest.hexdigest(),
        "generated": datetime.date.today().isoformat(),
    }

    dark_css = markup.page_css("dark")
    style = "\n".join([
        "/* ══ 1. markup.page_css('dark') 的輸出，逐字內嵌 —— dark 是預設模式 ══ */",
        dark_css,
        "/* ══ 2. 淺色：只重新宣告 :root（非 :root 的規則一律沿用上面那份）══ */",
        theme_css(),
        "/* ══ 3. 原型外殼（page_css 不產這些；數值出處見各條註解）══ */",
        chrome_css(),
        "/* ══ 4. 跨頁 chrome（側欄導覽／時點列／待做佔位／頁尾免責）══ */",
        shell_css(),
        # ⭐ 客戶 2026-09-22【拍板 1：CSS 走 (甲)】—— 「🔍 找標的」頁用到兩組契約層
        #   沒有產 CSS 的欄數（3/3/1 與 2/1/1）。⚠️ **必須排在 page_css 之後**：
        #   雖然 class 名不撞（markup 根本沒產這兩條），但同名情形下後寫的才蓋得過。
        #   ⚠️ **也必須在代理之外產** —— `_BLOCK_COLS_USED` 是 import 當下算好的，
        #   代理換不動它，所以這裡用的是 `components.*` 公開 API，與代理無關。
        find_grid_css(),
    ])

    # ── 兩頁的內容：順序**刻意**寫死，⛔ 不得交錯 ───────────────────────
    # 🔴 `build_why_body()` 會在自己的 `with` 區塊內把 `markup.page_today` 暫時換成
    #    「📖 憑什麼」頁的版面契約。CSS（上面的 `page_css`）與「🚦 今天」頁的內容
    #    **一律先產完**，代理才上場 ⇒ 代理期間**⛔ 沒有任何東西讀得到它**。
    # ⭐ **污染自驗（⛔ 不是「應該可以」）**：今天頁**產兩次** —— 一次在代理之前、
    #    一次在代理還原之後 —— 兩次**逐字相同**才算數。
    #    ⛔ 不用「看起來沒事」交差：`build_body()` 的輸出是純函式的結果，
    #    若代理漏還原或漏蓋某個名字，第二次就會不同（或直接炸）。
    today_body = build_body()
    why_html = build_why_html()          # ← 代理在這一行之內上場、之內還原
    assert markup.page_today is page_today, (
        "產完「📖 憑什麼」頁後 markup.page_today 不是原物件 —— 代理漏還原")
    find_html = build_find_html()        # ← 另一個代理，同樣之內上場、之內還原
    assert markup.page_today is page_today, (
        "產完「🔍 找標的」頁後 markup.page_today 不是原物件 —— 代理漏還原")
    inspect_html = build_inspect_html()  # ← 第三個代理，同樣之內上場、之內還原
    assert markup.page_today is page_today, (
        "產完「🔬 查一檔」頁後 markup.page_today 不是原物件 —— 代理漏還原")
    today_body_after = build_body()
    assert today_body_after == today_body, (
        "今天頁的輸出在產另外三頁前後不一致 —— 代理污染了今天頁")
    # ⭐ 三頁互不污染也要驗：前面兩頁在後面的代理跑完之後**各再產一次**，
    #    逐字相同才算數（⛔ 不用「看起來沒事」交差）。
    why_html_after = build_why_html()
    assert why_html_after == why_html, (
        "「📖 憑什麼」頁的輸出在產後面兩頁前後不一致 —— 代理互相污染")
    find_html_after = build_find_html()
    assert find_html_after == find_html, (
        "「🔍 找標的」頁的輸出在產「🔬 查一檔」頁前後不一致 —— 兩個代理互相污染")
    assert markup.page_today is page_today, "重產後 markup.page_today 不是原物件"

    # 導覽 JS：頁 id 與斷點都從契約層帶進去，⛔ 不在 JS 裡手打第二份。
    nav_js = _NAV_JS_TEMPLATE % {
        "today": f'"{PAGE_TODAY}"',
        "why": f'"{PAGE_WHY}"',
        "find": f'"{PAGE_FIND}"',
        "inspect": f'"{PAGE_INSPECT}"',
        "tablet_min": int(components.BREAKPOINTS["tablet_min_px"]),
    }

    banner = "⚠️ 靜態示意原型：所有數字皆為示意，未接任何資料源"
    footer = (
        f"由 src/ui_v2/（commit {meta['ui_v2_commit'][:7]}、"
        f"sha256 {meta['src_hash'][:12]}）於 {meta['generated']} 產生的靜態快照。"
        "CSS 由 markup.page_css() 產出並逐字內嵌，卡片由 markup.card_html() / "
        "grid_html() / layer_html() / badge_html() 產出。"
        "⚠️ tokens 之後改了，這個檔不會自動跟著變，"
        "必須重跑產生器 docs/v2/prototype/gen_today_v2.py（與本檔同目錄）。"
    )

    html = "\n".join([
        "<!DOCTYPE html>",
        '<html lang="zh-Hant">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        # ⚠️ 2026-09-22：原標題只寫「🚦 今天」，自本日起不成立（本原型已有兩頁）。
        #    **事實更正，⛔ 不是政策變更**；舊值 `🚦 今天 · 戰情室 v2 靜態原型`。
        # ⚠️ 2026-09-22 第二次：同日再加「🔍 找標的」⇒ 三頁。
        #    **同樣是事實更正**；上一版值 `戰情室 v2 靜態原型 · 🚦 今天 ＋ 📖 憑什麼`。
        # ⚠️ 2026-09-22 第三次：同日再加「🔬 查一檔」⇒ 四頁。
        #    **同樣是事實更正、⛔ 不是政策變更**；
        #    上一版值 `戰情室 v2 靜態原型 · 🚦 今天 ＋ 📖 憑什麼 ＋ 🔍 找標的`。
        "<title>戰情室 v2 靜態原型 · 🚦 今天 ＋ 📖 憑什麼 ＋ 🔍 找標的 ＋ 🔬 查一檔</title>",
        build_header_comment(meta),
        "<style>",
        style,
        "</style>",
        "</head>",
        "<body>",
        f'<div class="pv-banner">{esc(banner)}</div>',
        '<div class="pv-shell">',
        # ① 五頁切換（側欄式）—— 葉外、五頁共用
        build_nav_html(),
        "<script>" + nav_js + "</script>",
        '<div class="pv-main">',
        '<header class="pv-head">',
        "<div>",
        '<div class="pv-title">'
        f'<span id="pv-page-name">{esc(PAGE_LABELS[PAGE_TODAY])}</span>'
        " · 戰情室 v2 版面原型</div>",
        '<p class="pv-meta">'
        + esc(
            "整頁 CSS 與所有卡片標記都由 src/ui_v2/markup.py 的公開函式產生"
            "（page_css / card_html / grid_html / layer_html / badge_html）；"
            "本頁沒有任何手抄的色碼或 px。"
            "五頁的頁名取自 L0 SSOT shared/ia_nav.PAGE_LABELS，同樣沒有手抄。"
        )
        + "</p>",
        "</div>",
        '<div class="pv-toggle">',
        '<button type="button" class="pv-btn-secondary" id="pv-theme-toggle">'
        "◐ 切換深／淺色</button>",
        '<span class="pv-meta" id="pv-theme-now">目前：跟隨系統（預設深色）</span>',
        "</div>",
        "</header>",
        # ② 資料時點列 —— 頁面標題下方第一行、葉外（S2-UI_SPEC.md §7.1 逐字）
        build_asof_html(),
        '<div id="pv-page-today">',
        "<main>",
        today_body,
        "</main>",
        "</div>",
        # 🔴 「📖 憑什麼」「🔍 找標的」「🔬 查一檔」三頁在**這裡**擺 —— 三者都會暫時替換
        #    markup.page_today，所以它們的**產生**必須排在 `today_body` 與
        #    `style`（page_css）之後，⛔ 不得交錯（上方 main() 已按序產好）。
        why_html,
        find_html,
        inspect_html,
        build_todo_html(),
        build_gaps_html(),
        f'<footer class="pv-meta">{esc(footer)}</footer>',
        # ③ 頁尾免責 —— 逐字 SSOT
        build_legal_html(),
        "</div>",
        "</div>",
        "<script>" + _TOGGLE_JS + "</script>",
        "</body>",
        "</html>",
        "",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")

    # ── 出門前的自驗（⛔ 不是「應該可以」）──────────────────────────
    written = OUT.read_text(encoding="utf-8")
    assert dark_css in written, "page_css('dark') 的輸出沒有逐字出現在檔案裡"
    for forbidden in ("http://", "https://", "@import", "url(", "<script src", "<link "):
        assert forbidden not in written, f"出現外部資源引用：{forbidden}"
    # 🔴 **三個斷點的實際欄數：從 CSS 文字量，⛔ 不是看 class 名字有沒有印出來。**
    #    ⚠️ 兩條新的（.g-3-3-1 / .g-2-1-1）是產生器補的 —— 這一道就是它們唯一的守衛
    #    （契約層的那兩條另有 tests/ui_v2/ 守著，新的這兩條⛔ 沒有，見 FIND 缺口 F2）。
    #    量法：三次命中依 CSS 出現序 ＝ 基準（桌機）→ max-width:880（平板）→ max-width:640（手機）。
    for cls, want in ((".lg-3-2-1", ["3", "2", "1"]),
                      (".g-3-2-1", ["3", "2", "1"]),
                      (".g-1-1-1", ["1", "1", "1"]),
                      (".g-3-3-1", ["3", "3", "1"]),
                      (".g-2-1-1", ["2", "1", "1"])):
        found = re.findall(re.escape(cls) + r"\{grid-template-columns:repeat\((\d)", written)
        assert found == want, f"{cls} 的三段欄數不是 {'/'.join(want)}：{found}"
    for block in page_today.blocks_of_layer(2):
        assert f'class="grd grd-t2 ' in written and block in build_cards()

    # ── 跨頁 chrome 三塊的自驗（⛔ 不是「應該可以」）─────────────────
    # ① 五頁標籤：**程式比對，⛔ 非目視** —— 逐字取自 shared.ia_nav.PAGE_LABELS。
    for page_id, label in PAGE_LABELS.items():
        assert f'data-pv-page="{page_id}"' in written, f"側欄少了 {page_id}"
        assert esc(label) in written, f"側欄標籤 {label!r} 沒有逐字出現"
    #    ⚠️ 只數**標記裡**的（結尾是 `>`）—— CSS 選擇器裡也有一個 `aria-current="page"]`。
    assert written.count('aria-current="page">') == 1, (
        "current 頁不是恰好一個 —— 側欄的初始狀態壞了")
    assert f'data-pv-page="{PAGE_TODAY}" aria-current="page"' in written, (
        "current 不是 today")
    # ② 第五頁必須是「📖 憑什麼」，⛔ 全檔不得出現「為什麼」（客戶 2026-09-22 ④）。
    assert esc(PAGE_LABELS[PAGE_WHY]) in written and PAGE_LABELS[PAGE_WHY] == "📖 憑什麼"
    #    ⚠️ **2026-09-22 這道守衛被「縮範圍」，⛔ 沒有被弱化，⛔ 也不是漏改。**
    #    舊寫法：`assert "為…什麼" not in written`（**全檔級**，連散文都避開那三個字）。
    #    新增的「📖 憑什麼」頁帶進一個**線框 `name` 的逐字複本**，該名字本身含那三個字
    #    （`why.edu.table.caveat`，本組 node 實測：22 個 name 裡**唯一**命中）⇒ 兩者相撞。
    #    **兩條路都不走**：改守衛＝弱化；改規格名＝竄改逐字出處（比弱化更糟）。
    #    ⇒ 沿用本檔既有的「**先遮掉已知合法、再掃剩下的**」同一招
    #      （下面 HH:MM 那道守衛就是這樣做的）：允許清單只放**逐字出處**，其餘一個都不准。
    #    · 舊規則的理由**仍然成立**：全檔級最簡單，沒有人能偷渡；
    #    · 被權衡掉的原因：它會逼本檔去改一個**規格給的名字**，那是更嚴重的造假（§1）。
    #    ⚠️ 2026-09-22 第二次擴充：新增的「🔍 找標的」頁又帶進**線框 name 的逐字複本**
    #       （find.pe_two_kinds）與**線框 states 的逐字片段**（find.sector_flow.degraded）
    #       ⇒ 允許清單改成**兩份相加**，⛔ 仍然只收逐字出處、⛔ 不收本檔的散文。
    _masked_page_name = written
    for _verbatim in WHY_VERBATIM_ALLOW_WEISHENME + FIND_VERBATIM_ALLOW_WEISHENME:
        hits = _masked_page_name.count(esc(_verbatim))
        assert hits >= 1, (
            f"允許清單裡的逐字 {_verbatim!r} 在產物裡 0 命中 —— "
            "清單過期了（線框改名了？）。⛔ 不得留一條沒有對應實體的豁免。")
        _masked_page_name = _masked_page_name.replace(esc(_verbatim), "")
    assert "為什麼" not in _masked_page_name, (
        "遮掉允許清單後仍出現「為…什麼」—— 客戶 2026-09-22 ④ 明示第五頁用 SSOT 的"
        "「📖 憑什麼」，⛔ 不改成那三個字；允許清單只收**線框／規格的逐字名稱**，"
        "⛔ 不得拿本檔自己的散文往清單裡塞。")
    # ③ 頁尾免責逐字（出處比對已在 main() 開頭的 verbatim_sources() 跑過）。
    assert esc(COMPLIANCE_FOOTER_TEXT) in written, "頁尾免責沒有逐字出現"
    # ④ 時點列「尚未載入」逐字 ＋ **全檔⛔ 不得有任何 HH:MM 形狀的假時間**。
    assert esc(ASOF_IDLE_TEXT) in written, "時點列的「尚未載入」逐字沒出現"
    #    已知且合法的 `數字:數字` 只有一種：CSS 間距 token 的宣告（例 `--sp-4:10px`）。
    #    先把它們遮掉，再掃剩下的 —— 有剩就是有人填了一個時間進來。
    masked = re.sub(r"--sp-\d+:\d+px", "", written)
    leftover_times = re.findall(r"\d{1,2}:\d{2}", masked)
    assert not leftover_times, (
        f"出現 HH:MM 形狀的時間：{sorted(set(leftover_times))} —— "
        "時點列是示意殼，⛔ 不得填任何真時間（L3 契約無 as_of）")
    # ⑤ `.pv-` 命名空間⛔ 不得與 markup.page_css() 產出的 class 撞名（機器比對）。
    page_classes = set(re.findall(r"\.([A-Za-z][\w-]*)", markup.page_css("dark")))
    pv_classes = set(re.findall(r"\.(pv-[\w-]*)", shell_css() + chrome_css()))
    assert not (page_classes & pv_classes), page_classes & pv_classes
    assert not any(c.startswith("pv-") for c in page_classes), sorted(page_classes)
    # ⑥ 規格缺口至少四條，且每一條都掛了「未經第三方驗」的標記。
    #    ⚠️ 2026-09-22 起共**四組**缺口：chrome 的（五頁共用）＋「📖 憑什麼」頁
    #       ＋「🔍 找標的」頁 ＋「🔬 查一檔」頁自己的。
    #       每組都是「每條一次 ＋ 該組前言一次」。
    assert len(CHROME_SPEC_GAPS) >= 4, len(CHROME_SPEC_GAPS)
    assert len(WHY_SPEC_GAPS) >= 4, len(WHY_SPEC_GAPS)
    assert len(FIND_SPEC_GAPS) >= 4, len(FIND_SPEC_GAPS)
    assert len(INSPECT_SPEC_GAPS) >= 4, len(INSPECT_SPEC_GAPS)
    expected_caveats = ((len(CHROME_SPEC_GAPS) + 1) + (len(WHY_SPEC_GAPS) + 1)
                        + (len(FIND_SPEC_GAPS) + 1) + (len(INSPECT_SPEC_GAPS) + 1))
    assert written.count(esc(GAP_CAVEAT)) == expected_caveats, (
        f"缺口標記數不對：{written.count(esc(GAP_CAVEAT))} ≠ {expected_caveats}"
        "（每組各為：每條一次 ＋ 前言一次）")

    # ══ 「📖 憑什麼」頁的自驗（⛔ 不是「應該可以」；量到什麼就寫什麼）══════════
    # ⑦ 22 個 block **全部**出現，且**逐一**比對層／欄數 class／密度 class。
    #    ⛔ 不是「數一數有 22 個」——那只證明數量對。這裡比對的是每一塊的**長相**。
    assert len(WHY_LAYOUT) == 22, len(WHY_LAYOUT)
    assert len(WHY_BLOCK_COLS) == 22, "WHY_LAYOUT 有重複的 block key"
    assert sorted(WHY_LAYER_BLOCKS) == [0, 1, 2, 3, 4, 5], sorted(WHY_LAYER_BLOCKS)
    for _rec in WHY_LAYOUT:
        _block = str(_rec["block"])
        _cols = tuple(_rec["cols"])                       # type: ignore[arg-type]
        _tier = why_tier_for_block(_block)
        # `grid_html` 產的就是這一串（本檔⛔ 不手打，這裡只是把它算出來比對）
        _grid_cls = f'class="grd grd-{_tier} g-{_cols[0]}-{_cols[1]}-{_cols[2]}"'
        assert _grid_cls in written, f"{_block} 的網格 class 不對，預期 {_grid_cls}"
        assert esc(_block) in written, f"{_block} 這個 block key 沒有出現在畫面上"
        assert str(_rec["src"]).strip(), f"{_block} ⛔ 沒有標出處"
    #    ⑦-b cols 全集只有兩種（本組 node 實測線框：1/1/1 共 14、3/2/1 共 8）
    _cols_count = {c: sum(1 for v in WHY_BLOCK_COLS.values() if v == c)
                   for c in sorted(set(WHY_BLOCK_COLS.values()))}
    assert _cols_count == {(1, 1, 1): 14, (3, 2, 1): 8}, _cols_count
    #    ⑦-c 密度：n0~n4 必須與**契約層**的自動對映一致（⛔ 本檔不得偷偷手選一階）；
    #         n5 是規格 ② 表給的 t2（契約層沒有這一格，見缺口 W2）。
    for _n in (0, 1, 2, 3, 4):
        assert why_tier_for_layer(_n) == components.tier_for_layer(_n), _n
    assert why_tier_for_layer(5) == "t2"
    #    ⑦-d 密度與徽章尺寸必須對上規格 ② 表逐字（t3/t1/t2/t3/t4/t2 與 b3/b1/b2/b3/b4/b2）
    _spec_tiers = {0: "t3", 1: "t1", 2: "t2", 3: "t3", 4: "t4", 5: "t2"}
    _spec_badge_sizes = {0: "b3", 1: "b1", 2: "b2", 3: "b3", 4: "b4", 5: "b2"}
    for _n, _want in _spec_tiers.items():
        assert why_tier_for_layer(_n) == _want, (_n, why_tier_for_layer(_n), _want)
        _got = str(components.CARD_TIERS[_want]["badge_size"])
        assert _got == _spec_badge_sizes[_n], (_n, _got, _spec_badge_sizes[_n])

    # ⑧ #10：`.bdg-10` **仍然不在 CSS**，且新頁**⛔ 沒有畫任何一顆 #10**。
    #    （客戶 2026-09-22 拍板：`badge_html(10)` 不報錯 → 登記為待修，**本輪不動**。）
    assert ".bdg-10" not in dark_css, (
        ".bdg-10 竟然在 CSS 裡了 —— 有人動了契約層；本輪的前提（#10 無配色）已改變")
    #    ⚠️ **比對的是 class 屬性裡的 token，⛔ 不是全文搜字串**：
    #       本頁**刻意**用散文提到 `.bdg-10` 與 `#10`（就地揭露⛔ 不得省，W5）——
    #       「畫出一顆 #10」與「解釋何以不畫 #10」是兩件事，守衛必須分得出來。
    _class_tokens: set[str] = set()
    for _attr in re.findall(r'class="([^"]*)"', written):
        _class_tokens.update(_attr.split())
    assert "bdg-10" not in _class_tokens, (
        "產物的 class 屬性裡出現 bdg-10 —— ⛔ 那會是一顆無配色的徽章")
    _drawn_badges = {int(t[4:]) for t in _class_tokens if re.fullmatch(r"bdg-\d+", t)}
    assert _drawn_badges <= page_today.BADGES_ON_PAGE, (
        f"畫出了不該畫的徽章：{sorted(_drawn_badges - page_today.BADGES_ON_PAGE)}")
    assert WHY_BADGES_ON_PAGE <= _drawn_badges, (
        f"「📖 憑什麼」頁該畫的 6 態沒畫齊：少了 "
        f"{sorted(WHY_BADGES_ON_PAGE - _drawn_badges)}")
    assert FIND_BADGES_ON_PAGE <= _drawn_badges, (
        f"「🔍 找標的」頁該畫的 5 態沒畫齊：少了 "
        f"{sorted(FIND_BADGES_ON_PAGE - _drawn_badges)}")
    assert INSPECT_BADGES_ON_PAGE <= _drawn_badges, (
        f"「🔬 查一檔」頁該畫的 5 態沒畫齊：少了 "
        f"{sorted(INSPECT_BADGES_ON_PAGE - _drawn_badges)}")
    assert 10 in WHY_BADGES_NOT_ON_PAGE and 10 in page_today.BADGES_NOT_ON_PAGE
    assert sorted(WHY_BADGES_NOT_ON_PAGE) == [2, 8, 9, 10], sorted(WHY_BADGES_NOT_ON_PAGE)
    #    ⚠️ 「🔍 找標的」頁**多擋一顆 #5**（規格 ② 處置 2：unwired 已撤回、⛔ 不得回填）
    #       ⇒ 兩頁的可畫集合不同是**規格不同**，⛔ 不是本檔挑的（見 FIND 缺口 F13）。
    assert sorted(FIND_BADGES_NOT_ON_PAGE) == [2, 5, 8, 9, 10], sorted(FIND_BADGES_NOT_ON_PAGE)
    #    ⚠️ 「🔬 查一檔」頁**擋的是 #4，⛔ 不是 #5** —— 三頁的可畫集合各不相同，
    #       那是**規格不同**，⛔ 不是本檔挑的：
    #       規格 ② 的總結句逐字「實際會出現在畫面上的是 5 態：#1／#3／#5／#6／#7」
    #       （⇒ #5 **會**畫，#4 不畫）；同表另逐字說明 **#4 是刻意不出現、⛔ 不是待補**
    #       （實作檔頭「本頁沒有任何一格會判 UI_DEGRADED，這是刻意的」）。見缺口 P10。
    assert sorted(INSPECT_BADGES_NOT_ON_PAGE) == [2, 4, 8, 9, 10], \
        sorted(INSPECT_BADGES_NOT_ON_PAGE)
    #    ⭐ #5（未接線）在本原型**到本輪才第一次真的被畫出來**：
    #       「📖 憑什麼」頁沒有適用對象、「🔍 找標的」頁被規格撤回（F13）。
    assert 5 in _drawn_badges and 5 in INSPECT_BADGES_ON_PAGE
    #    ⑧-b 順手把「待修」釘住：一旦 badge_html(10) 改成會炸，這行會紅
    #        ⇒ 提醒把 W5 從缺口清單移掉（⛔ 不讓已修好的東西繼續掛在缺口表上）。
    try:
        markup.badge_html(10)
    except Exception:  # noqa: BLE001
        raise AssertionError(
            "markup.badge_html(10) 現在會炸了 —— 待修項已被修掉，"
            "請把 WHY_SPEC_GAPS 的 W5 改標為已解決（⛔ 不得留一條過期的缺口）") from None

    # ⑨ 五頁切換：**四頁是真頁、一頁是佔位**；`aria-current` 恰 1（標記裡的）。
    #    ⚠️ 2026-09-22 第三次擴充：`PAGE_INSPECT` 自本輪起是**真頁**，
    #       已從下方「⛔ 不得有頁容器」那一組**移出**
    #       （客戶逐字：「側欄切到「🔬 查一檔」可顯示；
    #        其他一頁（💼 我的持股）仍顯示「此頁待做」」）。
    #    ⚠️ 這是**事實更正**（真頁多了一頁），⛔ 不是把守衛放寬 ——
    #       剩下那一頁仍然一個字都不准有頁容器，下面那一圈照跑。
    for _pid in (PAGE_TODAY, PAGE_WHY, PAGE_FIND, PAGE_INSPECT):
        assert f'id="pv-page-{_pid}"' in written, f"少了 {_pid} 的頁容器"
    assert 'id="pv-page-why" hidden' in written, "「📖 憑什麼」頁預設⛔ 不是收起的"
    assert 'id="pv-page-find" hidden' in written, "「🔍 找標的」頁預設⛔ 不是收起的"
    assert 'id="pv-page-inspect" hidden' in written, "「🔬 查一檔」頁預設⛔ 不是收起的"
    assert 'id="pv-page-todo" hidden' in written, "待做佔位預設⛔ 不是收起的"
    assert written.count(esc(TODO_HEADLINE)) >= 1, "「此頁待做」佔位不見了"
    for _pid in (PAGE_HOLD,):
        assert f'id="pv-page-{_pid}"' not in written, (
            f"{_pid} 竟然有自己的頁容器 —— 那一頁本輪仍是「此頁待做」")
    #    ⚠️ 佔位卡的**初值**必須是那一頁（JS 每次切頁都會覆寫，但初值仍應是真的）。
    assert f'<span id="pv-todo-name">{esc(PAGE_LABELS[PAGE_HOLD])}</span>' in written, (
        "佔位卡的初始標題不是「💼 我的持股」—— 它指到一個不會再走到這裡的頁")
    #    ⚠️ 導覽 JS 必須真的認得第四頁（⛔ 不是「應該可以」：少一個布林 ＝ 兩頁同時可見）。
    for _needle in ("var INSPECT =", "isInspect", "inspect.hidden = !isInspect"):
        assert _needle in written, f"導覽 JS 少了 {_needle} —— 第四頁切不出來"

    # ⑩ 側欄行為**⛔ 未改動**：仍無 `open`、仍無任何把 `nav.open` 設 true 的路徑。
    #    ⚠️ **只掃 `<script>` 裡的內容，⛔ 不掃全文**：G5 缺口的散文**刻意**引述了被移除的
    #       那三行（`syncOpen` / `nav.open = mq.matches`），那是**加刪除線保留的紀錄**，
    #       ⛔ 不是活的程式碼 —— 守衛必須分得出「留著紀錄」與「留著行為」。
    assert "<details class=\"pv-nav\" id=\"pv-nav\">" in written, "側欄的 details 被動過了"
    _scripts = "\n".join(re.findall(r"<script>(.*?)</script>", written, flags=re.S))
    assert _scripts.strip(), "產物裡一段 <script> 都沒有 —— 抽取方式壞了，這道守衛等於沒跑"
    #       ⚠️ 再剝一層：JS 的 `//` 註解也**刻意**寫了「⛔ 本段沒有任何把 nav.open 設為
    #       true 的程式碼」—— 那是**說明**，⛔ 不是行為。⇒ 先去註解，再數。
    #       （去註解用 `//` 切行是安全的：全檔已另有一道守衛禁止任何 `http://` 之類的外部資源。）
    _js_code = "\n".join(re.sub(r"//.*", "", line) for line in _scripts.splitlines())
    assert "syncOpen" not in _js_code, "桌機自動展開的 syncOpen 又回來了（★-08 已決為收起）"
    _opens = re.findall(r"nav\.open\s*=\s*(\w+)", _js_code)
    assert _opens == ["false"], (
        f"JS 對 nav.open 的寫入是 {_opens}（預期恰一次，且值為 false）"
        " —— 側欄行為被改動了；★-08 已決為「預設收起、⛔ 無桌機自動展開」")

    # ⑪ 就地揭露（R4 客戶明示⛔ 不得省）：那句話**必須在畫面上**。
    assert esc(WHY_LAYOUT_DISCLOSURE) in written, "R4 的就地揭露沒有畫在畫面上"
    for _needle in ("src/ui_v2/", "tests/ui_v2/"):
        assert esc(_needle) in written or _needle in written, _needle

    # ⑫ 示意值：「📖 憑什麼」頁**凡是渲染得出阿拉伯數字的卡，一律掛示意標記**。
    #    ⚠️ 這比客戶的字面要求（「帶數字的卡」）**更嚴**：連「規格 ① 差異 3」這種
    #       **章節編號**也算數字 —— 分不清「資料的數字」與「出處的數字」時，一律從嚴掛標記。
    #    ⛔ 不用目視：逐張卡把標籤剝掉再掃，缺一張就炸。
    _unmarked: list[str] = []
    with why_page_contract():
        for _block, _cards in build_why_cards().items():
            for _card in _cards:
                _one = markup.card_html(block=_block, **_card)
                _text = re.sub(r"<[^>]+>", " ", _one)
                if re.search(r"\d", _text) and esc(DEMO) not in _one:
                    _unmarked.append(f"{_block} / {_card['title']}")
    assert not _unmarked, (
        f"這些卡渲染得出數字卻⛔ 沒有掛「{DEMO}」：{_unmarked}")

    # ══ 「🔍 找標的」頁的自驗（⛔ 不是「應該可以」；量到什麼就寫什麼）══════════
    # ⑬ 14 個 block **全部**出現，且**逐一**比對層／欄數 class／密度 class。
    #    ⛔ 不是「數一數有 14 個」——那只證明數量對。這裡比對的是每一塊的**長相**。
    assert len(FIND_LAYOUT) == 14, len(FIND_LAYOUT)
    assert len(FIND_BLOCK_COLS) == 14, "FIND_LAYOUT 有重複的 block key"
    assert sorted(FIND_LAYER_BLOCKS) == [0, 1, 2, 3, 4, 5], sorted(FIND_LAYER_BLOCKS)
    for _rec in FIND_LAYOUT:
        _block = str(_rec["block"])
        _cols = tuple(_rec["cols"])                       # type: ignore[arg-type]
        _tier = find_tier_for_block(_block)
        # `grid_html` 產的就是這一串（本檔⛔ 不手打，這裡只是把它算出來比對）
        _grid_cls = f'class="grd grd-{_tier} g-{_cols[0]}-{_cols[1]}-{_cols[2]}"'
        assert _grid_cls in written, f"{_block} 的網格 class 不對，預期 {_grid_cls}"
        assert esc(_block) in written, f"{_block} 這個 block key 沒有出現在畫面上"
        assert str(_rec["src"]).strip(), f"{_block} ⛔ 沒有標出處"
        assert ".py:" not in str(_rec["src"]), (
            f"{_block} 的 src 寫了行號 —— CLAUDE.md §8.2.A.0 規則 1：⛔ 不寫行號")
    #    ⑬-b cols 全集四種（本組 node 實測線框：1/1/1 共 10、3/2/1 共 1、3/3/1 共 1、2/1/1 共 2）
    _find_cols_count = {c: sum(1 for v in FIND_BLOCK_COLS.values() if v == c)
                        for c in sorted(set(FIND_BLOCK_COLS.values()))}
    assert _find_cols_count == {(1, 1, 1): 10, (2, 1, 1): 2,
                                (3, 2, 1): 1, (3, 3, 1): 1}, _find_cols_count
    #    ⑬-c 密度：n0~n4 必須與**契約層**的自動對映一致（⛔ 本檔不得偷偷手選一階）；
    #         n5 是規格 ① 表自己新訂的 t2（契約層沒有這一格，見缺口 F14）。
    for _n in (0, 1, 2, 3, 4):
        assert find_tier_for_layer(_n) == components.tier_for_layer(_n), _n
    assert find_tier_for_layer(5) == "t2"
    try:
        components.tier_for_layer(5)
    except ValueError:
        pass
    else:  # pragma: no cover - 契約層補上 n5 時才會走到
        raise AssertionError(
            "components.tier_for_layer(5) 不再拋 ValueError —— 契約層補上 n5 了，"
            "請把 FIND_N5_TIER 改成直接走契約層，並把缺口 F14 標為已解決")
    #    ⑬-d 密度與徽章尺寸必須對上規格 ① 表逐字（t3/t1/t2/t3/t4/t2 與 b3/b1/b2/b3/b4/b2）
    _find_spec_tiers = {0: "t3", 1: "t1", 2: "t2", 3: "t3", 4: "t4", 5: "t2"}
    _find_spec_badge_sizes = {0: "b3", 1: "b1", 2: "b2", 3: "b3", 4: "b4", 5: "b2"}
    for _n, _want in _find_spec_tiers.items():
        assert find_tier_for_layer(_n) == _want, (_n, find_tier_for_layer(_n), _want)
        _got = str(components.CARD_TIERS[_want]["badge_size"])
        assert _got == _find_spec_badge_sizes[_n], (_n, _got, _find_spec_badge_sizes[_n])
    #    ⑬-e 兩塊**⛔ 沒有卡、⛔ 沒有徽章**（規格 ② 處置 2(a)），且就地揭露有畫出來。
    _find_cards_snapshot = build_find_cards()
    assert sorted(FIND_NO_CARD_DISCLOSURE) == ["find.pick_reason",
                                               "find.scenario_quickpick"], \
        sorted(FIND_NO_CARD_DISCLOSURE)
    for _block, _text in FIND_NO_CARD_DISCLOSURE.items():
        assert not _find_cards_snapshot[_block], f"{_block} ⛔ 不得有卡"
        assert esc(_text) in written, f"{_block} 的就地揭露沒有畫在畫面上"
    #    ⑬-f ⭐ 客戶【拍板 1】明示的就地揭露**必須在畫面上**（⛔ 不得只留在 .py 裡）。
    for _needle in (FIND_LAYOUT_DISCLOSURE, FIND_GRID_CSS_DISCLOSURE,
                    FIND_GRID_CSS_DISCLOSURE_WHY):
        assert esc(_needle) in written, "「🔍 找標的」頁的就地揭露沒有畫在畫面上"
    #    ⑬-g ⭐ 本檔補的欄數 CSS：**只補契約層沒產的**，且⛔ 沒有新增第三個斷點。
    assert set(_FIND_COLS_NEEDING_CSS).isdisjoint(set(page_today.BLOCK_COLS.values())), (
        "本檔補的欄數與契約層重複了 —— 會有兩條同名規則（第二個真相源）")
    assert set(_FIND_COLS_NEEDING_CSS) == {(2, 1, 1), (3, 3, 1)}, _FIND_COLS_NEEDING_CSS
    _max_widths = sorted(set(int(m) for m in re.findall(r"max-width:(\d+)px", written)))
    assert _max_widths == sorted({int(components.BREAKPOINTS["mobile_max_px"]),
                                  int(components.BREAKPOINTS["tablet_max_px"])}), (
        f"全檔的 max-width 斷點不是那兩個：{_max_widths} —— "
        "補的那兩條 rule⛔ 不得引進第三個斷點")
    #    ⑬-h 示意值：同 ⑫，**凡是渲染得出阿拉伯數字的卡，一律掛示意標記**。
    _find_unmarked: list[str] = []
    with find_page_contract():
        for _block, _cards in _find_cards_snapshot.items():
            for _card in _cards:
                _one = markup.card_html(block=_block, **_card)
                _text = re.sub(r"<[^>]+>", " ", _one)
                if re.search(r"\d", _text) and esc(DEMO) not in _one:
                    _find_unmarked.append(f"{_block} / {_card['title']}")
    assert not _find_unmarked, (
        f"這些卡渲染得出數字卻⛔ 沒有掛「{DEMO}」：{_find_unmarked}")

    # ══ 「🔬 查一檔」頁的自驗（⛔ 不是「應該可以」；量到什麼就寫什麼）══════════
    # ⑭ 22 個 block **全部**出現，且**逐一**比對層／欄數 class／密度 class。
    #    ⛔ 不是「數一數有 22 個」——那只證明數量對。這裡比對的是每一塊的**長相**。
    assert len(INSPECT_LAYOUT) == 22, len(INSPECT_LAYOUT)
    assert len(INSPECT_BLOCK_COLS) == 22, "INSPECT_LAYOUT 有重複的 block key"
    assert sorted(INSPECT_LAYER_BLOCKS) == [0, 1, 2, 3, 4], sorted(INSPECT_LAYER_BLOCKS)
    #    ⚠️ **本頁⛔ 沒有 n5**（前兩頁都有）—— 這一行就是那件事的守衛。
    assert 5 not in INSPECT_LAYER_BLOCKS, "本頁竟然長出 n5 —— 線框實測是 5 層 n0~n4"
    #    ⚠️ 兩張手寫表（版面／葉）的 key 集合必須一致，⛔ 不讓其中一張漏一塊而沒人發現。
    assert set(_INSPECT_BLOCK_LEAF) == set(INSPECT_BLOCK_COLS), (
        "_INSPECT_BLOCK_LEAF 與 INSPECT_LAYOUT 的 block 不一致："
        f"{sorted(set(_INSPECT_BLOCK_LEAF) ^ set(INSPECT_BLOCK_COLS))}")
    for _rec in INSPECT_LAYOUT:
        _block = str(_rec["block"])
        _cols = tuple(_rec["cols"])                       # type: ignore[arg-type]
        _tier = inspect_tier_for_block(_block)
        # `grid_html` 產的就是這一串（本檔⛔ 不手打，這裡只是把它算出來比對）
        _grid_cls = f'class="grd grd-{_tier} g-{_cols[0]}-{_cols[1]}-{_cols[2]}"'
        assert _grid_cls in written, f"{_block} 的網格 class 不對，預期 {_grid_cls}"
        assert esc(_block) in written, f"{_block} 這個 block key 沒有出現在畫面上"
        assert str(_rec["src"]).strip(), f"{_block} ⛔ 沒有標出處"
        assert ".py:" not in str(_rec["src"]), (
            f"{_block} 的 src 寫了行號 —— CLAUDE.md §8.2.A.0 規則 1：⛔ 不寫行號")
        assert "｜線框 " in str(_rec["src"]), (
            f"{_block} 的 src ⛔ 沒有標線框 block key（格式：規格章節名｜線框 block key）")
    #    ⑭-b cols 全集**只有兩種**（本組 node 實測線框：1/1/1 共 14、3/2/1 共 8）
    _ins_cols_count = {c: sum(1 for v in INSPECT_BLOCK_COLS.values() if v == c)
                       for c in sorted(set(INSPECT_BLOCK_COLS.values()))}
    assert _ins_cols_count == {(1, 1, 1): 14, (3, 2, 1): 8}, _ins_cols_count
    #    ⑭-c 密度：五層**全部**必須與契約層的自動對映一致 ——
    #         本頁⛔ 沒有任何一層需要繞過契約層（與前兩頁的 n5 不同，見本節開頭長註）。
    for _n in sorted(INSPECT_LAYER_BLOCKS):
        assert inspect_tier_for_layer(_n) == components.tier_for_layer(_n), _n
    #    ⑭-d 密度與徽章尺寸必須對上規格 ① 表逐字（t3/t1/t2/t3/t4 與 b3/b1/b2/b3/b4）
    _ins_spec_tiers = {0: "t3", 1: "t1", 2: "t2", 3: "t3", 4: "t4"}
    _ins_spec_badge_sizes = {0: "b3", 1: "b1", 2: "b2", 3: "b3", 4: "b4"}
    for _n, _want in _ins_spec_tiers.items():
        assert inspect_tier_for_layer(_n) == _want, (_n, inspect_tier_for_layer(_n), _want)
        _got = str(components.CARD_TIERS[_want]["badge_size"])
        assert _got == _ins_spec_badge_sizes[_n], (_n, _got, _ins_spec_badge_sizes[_n])
    #    ⑭-e ⭐ 本頁**⛔ 沒有補任何一條欄數 CSS**，且公式**同時減掉兩個來源**
    #         （契約層 ＋「🔍 找標的」頁已補的）—— ⛔ 只減契約層會重複宣告同名 rule。
    assert _INSPECT_COLS_NEEDING_CSS == (), (
        f"本頁竟然需要補欄數 CSS：{_INSPECT_COLS_NEEDING_CSS} —— "
        "版面加了新欄數；補之前請先確認⛔ 沒有與 find_grid_css() 重複宣告")
    assert set(INSPECT_BLOCK_COLS.values()) <= (
        set(page_today.BLOCK_COLS.values()) | set(FIND_BLOCK_COLS.values())), (
        "本頁用到的欄數不在「契約層 ∪ FIND 已補」之內")
    #    ⑭-f ⭐ 總管本輪四項拍板的**就地揭露必須在畫面上**（⛔ 不得只留在 .py 裡）。
    for _needle in (INSPECT_LAYOUT_DISCLOSURE, INSPECT_TABLE_DISCLOSURE,
                    INSPECT_TABLE_DISCLOSURE_WHY, INSPECT_CTA_DISCLOSURE,
                    INSPECT_CTA_DISCLOSURE_WHY, INSPECT_PAGE_SHAPE_NOTE):
        assert esc(_needle) in written, "「🔬 查一檔」頁的就地揭露沒有畫在畫面上"
    #    ⑭-g ⭐ 總管拍板 1：本頁**⛔ 沒有畫任何一個表格標籤**（全檔級，⛔ 不是只看本頁）。
    #         量法：直接掃標記裡的標籤名，⛔ 不是看有沒有寫「表格」兩個字。
    for _tag in ("<table", "<thead", "<tbody", "<tr", "<th", "<td"):
        assert _tag not in written, (
            f"產物裡出現 {_tag} —— 契約層 markup 沒有表格能力，"
            "本輪⛔ 不得自寫表格標記（總管拍板 1，缺口 P1）")
    #    ⑭-h/i 逐張卡的兩道守衛 —— **卡片逐張重算，⛔ 不用會吃到附錄的全文 regex**：
    #      (h) ⭐ 總管拍板 4：規格點名**禁上畫面**的口徑用詞，**卡面**上一個都不准有。
    #          ⚠️ **只掃卡面，⛔ 不掃全檔**：附錄與層註是**內部揭露**，本來就要寫出
    #             「被拿掉的是哪半句」「規格禁的是哪一句」（缺口 P4／P5 就地說明了這條界線）。
    #          ⚠️ 這是**縮範圍、⛔ 不是弱化**：卡面那一側一個字都沒有放寬 ——
    #             連「引述那條禁令」本身都不准出現在卡面上（引述也會把那幾個字印上去）。
    #      (i) 示意值：同 ⑫／⑬-h，**凡是渲染得出阿拉伯數字的卡，一律掛示意標記**。
    #      另順手釘住：每一張重算出來的卡**逐字出現在產物裡**（⛔ 不是「應該有」）。
    _ins_cards_snapshot = build_inspect_cards()
    _ins_unmarked: list[str] = []
    _ins_banned_hits: list[str] = []
    with inspect_page_contract():
        for _block, _cards in _ins_cards_snapshot.items():
            assert _cards, f"{_block} ⛔ 沒有卡 —— 本頁 22 塊每一塊都要有至少一張"
            for _card in _cards:
                _one = markup.card_html(block=_block, **_card)
                assert _one in written, f"{_block} 的卡沒有逐字出現在產物裡：{_card['title']}"
                _text = re.sub(r"<[^>]+>", " ", _one)
                if re.search(r"\d", _text) and esc(DEMO) not in _one:
                    _ins_unmarked.append(f"{_block} / {_card['title']}")
                for _banned in ("加權移動平均", "FIFO", "先進先出"):
                    if esc(_banned) in _one:
                        _ins_banned_hits.append(
                            f"{_block} / {_card['title']} ⇒ {_banned}")
    assert not _ins_banned_hits, (
        f"卡面出現規格禁止的口徑用詞：{_ins_banned_hits} —— 規格 ③② 逐字："
        "⛔ 使用者看到的字面不得出現這類內部詞或系統做不到的口徑宣稱（缺口 P4／P5）")
    assert not _ins_unmarked, (
        f"這些卡渲染得出數字卻⛔ 沒有掛「{DEMO}」：{_ins_unmarked}")
    #    ⑭-j 22 塊**每一塊都有卡**（本頁⛔ 沒有「畫框不畫卡」那種塊 —— 那是 FIND 的處置）。
    assert sorted(_ins_cards_snapshot) == sorted(INSPECT_BLOCK_COLS), (
        "build_inspect_cards() 的 block 與 INSPECT_LAYOUT 不一致："
        f"{sorted(set(_ins_cards_snapshot) ^ set(INSPECT_BLOCK_COLS))}")

    print(f"wrote {OUT} ({len(written.encode('utf-8'))} bytes)")
    print(f"  · 「📖 憑什麼」頁：{len(WHY_LAYOUT)} block / "
          f"{len(WHY_LAYER_BLOCKS)} 層 / 缺口 {len(WHY_SPEC_GAPS)} 條")
    print(f"    畫的徽章：{sorted(WHY_BADGES_ON_PAGE)}；"
          f"⛔ 不畫：{sorted(WHY_BADGES_NOT_ON_PAGE)}")
    print(f"  · 「🔍 找標的」頁：{len(FIND_LAYOUT)} block / "
          f"{len(FIND_LAYER_BLOCKS)} 層 / 缺口 {len(FIND_SPEC_GAPS)} 條")
    print(f"    畫的徽章：{sorted(FIND_BADGES_ON_PAGE)}；"
          f"⛔ 不畫：{sorted(FIND_BADGES_NOT_ON_PAGE)}；"
          f"⛔ 無卡無徽章的 block：{sorted(FIND_NO_CARD_DISCLOSURE)}")
    print(f"  · 「🔬 查一檔」頁：{len(INSPECT_LAYOUT)} block / "
          f"{len(INSPECT_LAYER_BLOCKS)} 層（n0~n4，⛔ 無 n5）/ 缺口 {len(INSPECT_SPEC_GAPS)} 條")
    print(f"    畫的徽章：{sorted(INSPECT_BADGES_ON_PAGE)}；"
          f"⛔ 不畫：{sorted(INSPECT_BADGES_NOT_ON_PAGE)}"
          f"（其中 #4 是規格明寫的**刻意不出現**，⛔ 與另外三顆「待補」不同類）")
    print(f"    本頁補的欄數 CSS：{list(_INSPECT_COLS_NEEDING_CSS) or '（無，cols 全集契約層都已產）'}；"
          f"表格標籤：0（總管拍板 1 —— 契約層無表格能力，見缺口 P1）")
    print(f"  · 本檔補的欄數 CSS：{[f'g-{a}-{b}-{c}' for a, b, c in _FIND_COLS_NEEDING_CSS]}"
          f"（⚠️ 規則形狀複製了一份 ＝ 第二個真相源，見缺口 F2）")


if __name__ == "__main__":
    main()
