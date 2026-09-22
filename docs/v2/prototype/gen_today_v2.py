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
    ])

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
        '<header class="pv-head">',
        "<div>",
        '<div class="pv-title">🚦 今天 · 戰情室 v2 版面原型</div>',
        '<p class="pv-meta">'
        + esc(
            "整頁 CSS 與所有卡片標記都由 src/ui_v2/markup.py 的公開函式產生"
            "（page_css / card_html / grid_html / layer_html / badge_html）；"
            "本頁沒有任何手抄的色碼或 px。"
        )
        + "</p>",
        "</div>",
        '<div class="pv-toggle">',
        '<button type="button" class="pv-btn-secondary" id="pv-theme-toggle">'
        "◐ 切換深／淺色</button>",
        '<span class="pv-meta" id="pv-theme-now">目前：跟隨系統（預設深色）</span>',
        "</div>",
        "</header>",
        "<main>",
        build_body(),
        "</main>",
        f'<footer class="pv-meta">{esc(footer)}</footer>',
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
    print(f"wrote {OUT} ({len(written.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
