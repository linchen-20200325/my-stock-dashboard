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
import hashlib
import pathlib
import re
import subprocess
import sys
from html import escape
from typing import Mapping, Sequence

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

#: 其餘四頁的佔位逐字。
TODO_HEADLINE = "此頁待做"
TODO_BODY = (
    "本原型只做了「{today}」。這一頁還沒有任何實作，"
    "⛔ 不是壞掉、⛔ 也不是載入失敗 —— 畫這塊佔位，是為了不讓五頁切換假裝五頁都已完成"
    "（對照 CLAUDE.md §1：錯誤的數字比沒有數字更危險）。"
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
        "⚠️ ★-15（引導入口放哪裡）⛔ 不受本條影響 —— S2-UI_SPEC.md 7.2 逐字"
        "「★-08 已於 2026-09-22 單獨解除；★-15 仍未決 · 阻斷，等客戶裁示」。"
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
    3: "主 CTA 全站唯一一顆，標籤逐字取 page_today.MAIN_CTA['label']；"
       "可按性取 main_cta_state()。⚠️ 本頁是靜態原型，按下去不會有任何事發生。",
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
             "facts": (("主 CTA", "全站唯一一顆"),
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
    """其餘四頁的「此頁待做」佔位（預設 `hidden`，由側欄點擊切出來）。"""
    return "\n".join([
        '<section class="pv-todo" id="pv-page-todo" hidden>',
        '<div class="pv-todo-card">',
        '<div class="pv-todo-title">'
        f'<span id="pv-todo-name">{esc(PAGE_LABELS[PAGE_FIND])}</span>'
        f"　·　{esc(TODO_HEADLINE)}</div>",
        f'<p class="pv-meta">'
        f'{esc(TODO_BODY.format(today=PAGE_LABELS[PAGE_TODAY]))}</p>',
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

  function show(page, label) {
    var today = document.getElementById('pv-page-today');
    var todo = document.getElementById('pv-page-todo');
    var isToday = (page === TODAY);
    today.hidden = !isToday;
    todo.hidden = isToday;
    document.getElementById('pv-page-name').textContent = label;
    if (!isToday) { document.getElementById('pv-todo-name').textContent = label; }
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
    ])

    # 導覽 JS：頁 id 與斷點都從契約層帶進去，⛔ 不在 JS 裡手打第二份。
    nav_js = _NAV_JS_TEMPLATE % {
        "today": f'"{PAGE_TODAY}"',
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
        "<title>🚦 今天 · 戰情室 v2 靜態原型</title>",
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
        build_body(),
        "</main>",
        "</div>",
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
    for cls in (".lg-3-2-1", ".g-3-2-1"):
        found = re.findall(re.escape(cls) + r"\{grid-template-columns:repeat\((\d)", written)
        assert found == ["3", "2", "1"], f"{cls} 的三段欄數不是 3/2/1：{found}"
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
    assert "為什麼" not in written, (
        "全檔出現「為什麼」—— 客戶 2026-09-22 ④ 明示第五頁用 SSOT 的「📖 憑什麼」，"
        "⛔ 不改成「為什麼」；本檔連散文都避開這三個字，讓這道守衛可以是全檔級的。")
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
    assert len(CHROME_SPEC_GAPS) >= 4, len(CHROME_SPEC_GAPS)
    assert written.count(esc(GAP_CAVEAT)) == len(CHROME_SPEC_GAPS) + 1, (
        "缺口標記數不對（每條一次 ＋ 前言一次）")

    print(f"wrote {OUT} ({len(written.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
