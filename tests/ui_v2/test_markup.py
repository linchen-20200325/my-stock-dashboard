"""WRT 渲染層測試組｜test-first 契約 D：純字串標記層（`src/ui_v2/markup.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/markup.py` **尚不存在**，
   本檔因此**應該是紅燈**（`ImportError: cannot import name 'markup'`）——
   紅燈即本輪的正確產出。實作由 WRI 組補上，⛔ 本組不寫實作。

⛔ **本檔不 import streamlit**：`markup.py` 是純字串層，要能在沒有 Streamlit
   runtime 的沙箱裡單測（沿用 `tests/ui_v2/test_tokens.py` /
   `test_components.py` / `test_today_page.py` 的既有紀律）。
   有 `st.*` 的那一半由 `tests/ui_v2/test_render.py` 以 `AppTest` 冒煙。

────────────────────────────────────────────────────────────────────
實作組（WRI）必須提供：`src/ui_v2/markup.py`
────────────────────────────────────────────────────────────────────
`page_css(mode: str) -> str`
    整頁的 `<style>` 內容（含或不含 `<style>` 標籤皆可，本檔兩種都吃）。
    ⚠️ **每一個 token 都必須走 `tokens.get_token(name, mode=mode)`**，
       ⛔ 不得 `for k, v in tokens.LIGHT.items()` 直接讀 dict。
       理由見本檔「§1 Fail Loud」段的 `test_page_css_never_references_a_var_it_did_not_declare`。

`badge_html(n: int) -> str`
    一顆狀態徽章。class 用 `.bdg-{n}`（**編號**命名空間），
    ⛔ 不得用 `b1`~`b4` —— 那是 `components.SBADGE_SIZES` 的**尺寸**鍵，會撞名。

`card_html(*, block, state, title, value=None, level=None, badge_n, facts=()) -> str`
    一張卡。大字區（觀測值）與判決區（燈號等級）**一律以
    `page_today.card_value_text` / `card_level_text` 為準**。

`grid_html(*, block, cards: Sequence[str]) -> str`
    一個 block 的 grid 容器 ＋ 內含的卡。**整段必須是自閉合的一塊**
    （`<div>` 開閉數相等）—— 未閉合的 `<div>` 不會跨 `st.markdown` 呼叫
    包住下一次的產出（repo 先例：`src/ui/render/station_cards.py` docstring
    逐字「整面牆是一次 `st.markdown` 的純 HTML」）。
    ⚠️ 欄數取 `page_today.BLOCK_COLS`，語意是**卡內**一列幾格
    （`page_today.cols_scope()` 逐字回 `"inside_block"`）。

`layer_html(*, layer: int, block_htmls: Sequence[str]) -> str`
    （總管 2026-09-21 補的**第五支**）把某一層的各 block（已由 `grid_html` 產好）
    包進**層級網格** —— 同一層的幾個 block 彼此怎麼並排。
    欄數取 `page_today.LAYER_GRID_COLS[layer]`，三斷點、夾 `components.MAX_COLS`。
    🔴 **只有第二層有來源**；其餘層 `page_today.blocks_per_row()` 會 **raise**，
    本層必須把那個 raise 傳出來 —— ⛔ 不得回一個猜的值、⛔ 不得預設 1 欄蒙混。
    ⚠️ 它的 class ⛔ 不得與 `grid_html` 的網格 class 撞名（兩個不同語意的網格）。

⚠️ **四階密度幾何**：`page_css()` 還必須把 `components.CARD_TIERS` 的內距、卡標字級、
    框線樣式與 `SBADGE_SIZES` 的字級、min-height 吐進 CSS，而且**每一階掛在它自己的
    class 上**（見「C-1b」節）。格式完全自由：`17.5px` / `17.50px` / shorthand /
    longhand / `padding:var(--sp-4) var(--sp-5)` 一律等價。

────────────────────────────────────────────────────────────────────
本檔守的四件事（客戶點名三項 ＋ 總管加的 §1 守衛）
────────────────────────────────────────────────────────────────────
  · **C-1 每個元件渲染成什麼** —— grid 容器的 class 對得上
    `page_today.tier_for_block(block)`；每顆徽章帶得出
    `components.badge(n)` 的 `icon` 與 `text`；兩個徽章命名空間不撞名。
  · **C-1b 四階密度幾何** —— 內距／卡標字級／徽章 min-height 的**階梯活著走進 CSS**，
    而且每一階的值是**該階獨佔**（擋掉一條大通規則把四階壓平）。
  · **C-2 四層結構 ＋ 三斷點** —— 四層：每層的 block 都掛該層的 tier。
    三斷點：**降級成 CSS 文字斷言**（理由見下方「這些測試證明了什麼」）。
  · **C-2b 層級網格** —— `layer_html` 的三斷點欄數、**桌機第二層恰好 1 列**
    （「`today.holdings` ⛔ 不是疊在最下面的全寬卡」）、與 block 網格 class 不撞名、
    未登記的層要炸。
  · **C-3 九種狀態** —— 九顆徽章的顏色**住在 `<style>` 裡**、⛔ 不在 inline style；
    `#9` 與 `#1` 零共用色 token（`UI_COMPONENTS.md §2 徽章表 #9「資料不完整」列`）。
  · **§1 Fail Loud** —— **凡是還帶 `TBD` 的模式，`page_css()` 一律炸**
    （2026-09-21 當下＝`light`），而且**炸在產生 CSS 之前**；
    灰／紅態大字區一律留白、`degraded` 觀測照出判決留白。
    ⚠️ 這一條**讀 `tokens` 的現況、不釘死 `light`** —— 客戶補完 light 值之後
    自動翻面要求 `light` 產得出一張合格 sheet，⛔ 不會變成逼 WRI 改測試的假紅燈。

────────────────────────────────────────────────────────────────────
⚠️ 這些測試**證明了什麼、沒證明什麼**（誠實揭露，CLAUDE.md §-2 規則 6）
────────────────────────────────────────────────────────────────────
**「三個斷點」這一項，本檔沒有真的測到。** 這裡測的是
「`page_css()` 這個**字串**裡，`@media (max-width:…)` 段內宣告的欄數，
等於 `components.resolve_cols(cols, 該寬度)`」——
它證明的是 **CSS 文字與 `BLOCK_COLS` 一致**，
**不證明**瀏覽器在 640px / 880px / 1440px 真的排成 1 / 2 / 3 欄
（沒有真瀏覽器、沒有 layout engine、`AppTest` 也沒有 viewport 參數）。
版面在真裝置上的行為**不在本檔射程內**，要靠人眼或 E2E。

**⛔ 不寫死任何 magic number**（CLAUDE.md §3.3 反捏造在測試裡同樣適用）：
斷點取 `components.BREAKPOINTS`、欄數取 `components.resolve_cols`、
block 清單取 `page_today.BLOCK_COLS` / `LAYERS`、徽章號取
`page_today.BADGES_ON_PAGE`、token 名取 `tokens.DARK`。
—— 另一組正在動 `BLOCK_COLS`（`today.holdings` 已於 2026-09-21 加入），
本檔**全部動態讀**，不手抄清單。
"""
from __future__ import annotations

import re
from contextlib import contextmanager

import pytest

from src.ui_v2 import components, page_today, tokens
from src.ui_v2 import markup   # ← 本輪不存在 → ImportError。**紅燈即正確產出。**


# ══════════════════════════════════════════════════════════════════
# 0. 取自契約層的動態清單（⛔ 一律不手抄）
# ══════════════════════════════════════════════════════════════════
#: 有登記 `cols` 的 block —— grid / CSS 欄數相關的測試用這一份。
COLS_BLOCKS: tuple[str, ...] = tuple(page_today.BLOCK_COLS)

#: 版面上真的存在的 block（含 `cols` 未登記者）—— 卡片 / 分層測試用這一份。
ALL_BLOCKS: tuple[str, ...] = tuple(
    b for layer in page_today.LAYERS for b in layer["blocks"]
)

#: 本頁會畫到的徽章號（實測 `{1..9}`，#10 不畫）。⛔ 不寫死 1~9。
ON_PAGE_BADGES: tuple[int, ...] = tuple(sorted(page_today.BADGES_ON_PAGE))

#: 層序清單（0 葉外 chrome ＋ 1~4 四層）。
LAYER_IDS: tuple[int, ...] = tuple(layer["layer"] for layer in page_today.LAYERS)

#: **有登記層級網格**的層。實測只有第二層（客戶 2026-09-16「3 張並排卡」＋ 原型 `.g3`）。
GRID_LAYERS: tuple[int, ...] = tuple(sorted(page_today.LAYER_GRID_COLS))

#: **沒有**登記層級網格的層 —— 問到要炸，⛔ 不得回一個猜的值。
UNGRIDDED_LAYERS: tuple[int, ...] = tuple(
    L for L in LAYER_IDS if L not in page_today.LAYER_GRID_COLS
)

#: 四階密度的階序（由密到疏）。⛔ 不寫死 `("t1","t2","t3","t4")` —— 從 SSOT 取。
TIER_ORDER: tuple[str, ...] = tuple(sorted(components.CARD_TIERS))

#: 徽章尺寸的階序（由大到小），`b1`~`b4` 對應 t1~t4。
SBADGE_ORDER: tuple[str, ...] = tuple(sorted(components.SBADGE_SIZES))

#: 灰態／紅態 —— 大字區一律留白（`UI_PAGE_TODAY.md ④ 反例自檢`）。
#: ⚠️ 這份清單**不是憑空抄的**：下方
#: `test_grey_and_red_states_leave_the_value_blank` 每一條都先拿
#: `page_today.card_value_text` 當 oracle 驗過「它確實是留白態」才往下測。
BLANK_VALUE_STATES: tuple[str, ...] = (
    "failed", "error",                                        # 紅態
    "idle", "loading", "unwired", "empty", "missing", "na",   # 灰態
)

#: 兩個顯示模式（`tokens._MODES` 的公開面）。
MODES: tuple[str, ...] = ("dark", "light")

#: mode → token 表。`get_token()` 只認這兩個 mode 名（其餘 `ValueError`）。
_TABLES: dict[str, object] = {"dark": tokens.DARK, "light": tokens.LIGHT}


def _tbd_names(mode: str) -> set[str]:
    """該模式下「客戶尚未指定」的 token 名。

    ⚠️ **動態讀，⛔ 不寫死 `light` 有兩個 TBD** —— 2026-09-21 當下
    `--sig-neutral` / `--sig-neutral-bg` 的 light 值仍是 `TBD`，
    但另一組正在補客戶剛裁的值。補完之後本檔的 §1 守衛必須**自動換邊**
    （從「light 要炸」變成「light 要產出一張合格的 sheet」），
    ⛔ 不該因為 token 被補上就變成一條要 WRI 去改掉的假紅燈。
    """
    return {name for name, value in _TABLES[mode].items() if value is tokens.TBD}


#: 放進卡片、用來證明「它沒有被印出來」的哨兵。
#: ⚠️ 刻意**不含數字以外的意義**也**不與任何規格字串重疊**，避免假綠燈。
SENTINEL_VALUE = "8887.6"
SENTINEL_LEVEL = "WRTSENTINELLEVEL"
SENTINEL_CARD = "<span>WRT-CARD-SENTINEL</span>"

#: 餵給 `layer_html()` 的假 block（刻意**不帶 class、不帶 `<div>`**：
#: 不帶 class 才不會污染容器的 class 判讀，不帶 `<div>` 才能乾淨地數容器自己的開閉。
def _sentinel_blocks(n: int) -> tuple[str, ...]:
    return tuple(f"<i>WRT-BLOCK-SENTINEL-{i}</i>" for i in range(n))


# ══════════════════════════════════════════════════════════════════
# 1. 小工具 —— HTML / CSS 文字剖析（⛔ 不引入第三方 parser，保持沙箱可跑）
# ══════════════════════════════════════════════════════════════════
_TAG_RE = re.compile(r"<[^>]*>")
_FIRST_TAG_RE = re.compile(r"<\s*[A-Za-z][^>]*>")
_CLASS_ATTR_RE = re.compile(r'class\s*=\s*"([^"]*)"')
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_STYLE_TAG_RE = re.compile(r"</?\s*style[^>]*>", re.I)


def _strip_style_tags(css: str) -> str:
    """`page_css()` 回傳含 `<style>` 或不含都吃 —— 契約沒釘，本檔不強加。"""
    return _STYLE_TAG_RE.sub("", css)


def _first_tag_classes(html: str) -> set[str]:
    """最外層那個標籤的 class token 集合（＝容器自己的 class）。"""
    m = _FIRST_TAG_RE.search(html)
    assert m, f"沒有產出任何 HTML 標籤：{html[:120]!r}"
    cm = _CLASS_ATTR_RE.search(m.group(0))
    return set(cm.group(1).split()) if cm else set()


def _all_classes(html: str) -> set[str]:
    out: set[str] = set()
    for m in _CLASS_ATTR_RE.finditer(html):
        out.update(m.group(1).split())
    return out


def _text_of(html: str) -> str:
    """去掉所有標籤後剩下的文字（含屬性一併剝掉）。"""
    return _TAG_RE.sub(" ", html)


_RULE_CACHE: dict[str, list[tuple[str | None, str, str]]] = {}


def _iter_rules(css: str) -> list[tuple[str | None, str, str]]:
    """把 CSS 拆成 `(media_prelude | None, selector, body)`，支援一層 `@media` 巢狀。

    ⚠️ 這是**夠用就好**的剖析器，不是完整 CSS parser：
       `@keyframes` / `@supports` / `@font-face` 一律略過（本頁用不到）。
    """
    key = css
    if key in _RULE_CACHE:
        return _RULE_CACHE[key]
    _RULE_CACHE[key] = out = _parse(_CSS_COMMENT_RE.sub("", _strip_style_tags(css)), None)
    return out


def _parse(css: str, media: str | None) -> list[tuple[str | None, str, str]]:
    out: list[tuple[str | None, str, str]] = []
    i, n = 0, len(css)
    while i < n:
        brace = css.find("{", i)
        if brace == -1:
            break
        prelude = css[i:brace].strip()
        depth, j = 1, brace + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[brace + 1: j - 1]
        if prelude.startswith("@"):
            if prelude.lower().startswith("@media"):
                out.extend(_parse(body, prelude))
        else:
            out.append((media, prelude, body))
        i = j
    return out


def _media_max_px(prelude: str | None) -> int | None:
    """`None` ＝ 基準規則（不在任何 `@media` 裡）；`-1` ＝ 在 `@media` 裡但不是 max-width。"""
    if prelude is None:
        return None
    m = re.search(r"max-width\s*:\s*(\d+)\s*px", prelude)
    return int(m.group(1)) if m else -1


def _selector_targets(selector: str, cls: str) -> bool:
    pat = re.compile(r"\." + re.escape(cls) + r"(?![\w-])")
    return any(pat.search(part) for part in selector.split(","))


def _grid_cols_value(body: str) -> str | None:
    m = re.search(r"grid-template-columns\s*:\s*([^;}]+)", body)
    return m.group(1).strip() if m else None


def _col_count(value: str) -> int:
    """`repeat(3, …)` → 3；`1fr 1fr` → 2。"""
    compact = re.sub(
        r"\(\s*([^()]*?)\s*\)",
        lambda m: "(" + m.group(1).replace(" ", "") + ")",
        value,
    )
    m = re.search(r"repeat\(\s*(\d+)", compact)
    if m:
        return int(m.group(1))
    return len(compact.split())


def _declared_cols(css: str, cls: str, *, max_px: int | None) -> list[int]:
    """在指定的 media 脈絡下，`.cls` 被宣告了哪些欄數（依 CSS 出現順序）。"""
    out = []
    for media, sel, body in _iter_rules(css):
        if _media_max_px(media) != max_px:
            continue
        if not _selector_targets(sel, cls):
            continue
        v = _grid_cols_value(body)
        if v is not None:
            out.append(_col_count(v))
    return out


def _class_names_in_css(css: str) -> set[str]:
    out: set[str] = set()
    for _media, sel, _body in _iter_rules(css):
        out.update(re.findall(r"\.([A-Za-z_][\w-]*)", sel))
    return out


def _cols_class_of(html: str, css: str, label: str) -> str:
    """一個網格容器上，**負責欄數**的那一個 class。

    block 網格（`grid_html`）與層級網格（`layer_html`）共用這支 —— 兩者是
    **兩個不同的網格**，但「怎麼從容器找出管欄數的 class」是同一件事。
    """
    classes = _first_tag_classes(html)
    cols_classes = sorted(c for c in classes if _declared_cols(css, c, max_px=None))
    assert cols_classes, (
        f"{label}：網格容器的 class {sorted(classes)} 裡，"
        "沒有任何一個在 CSS 基準規則中宣告 grid-template-columns"
    )
    if len(cols_classes) == 1:
        return cols_classes[0]
    # 容器同時帶「基準 grid」與「欄數」兩個 class 時，取有 RWD 覆寫的那一個。
    responsive = [
        c for c in cols_classes
        if _declared_cols(css, c, max_px=components.BREAKPOINTS["mobile_max_px"])
    ]
    assert len(responsive) == 1, (
        f"{label}：分不出哪個 class 管欄數（候選 {cols_classes}，有 RWD 覆寫者 {responsive}）"
    )
    return responsive[0]


def _grid_class_of(block: str, css: str) -> str:
    return _cols_class_of(_grid(block), css, f"block {block}")


def _layer_class_of(layer: int, css: str) -> str:
    n = len(page_today.blocks_of_layer(layer))
    return _cols_class_of(_layer(layer, n), css, f"第 {layer} 層")


def _grid(block: str) -> str:
    return markup.grid_html(block=block, cards=(SENTINEL_CARD,))


def _layer(layer: int, n_blocks: int | None = None) -> str:
    if n_blocks is None:
        n_blocks = len(page_today.blocks_of_layer(layer))
    return markup.layer_html(layer=layer, block_htmls=_sentinel_blocks(n_blocks))


# ── 幾何（四階密度階梯）用的取值工具 ────────────────────────────────
def _resolve_spacing(value: str) -> str:
    """把 `var(--sp-N)` 換成 `tokens.SPACING` 的實值。

    ⚠️ **必須有這一步**：`UI_COMPONENTS.md §1 四層密度表 t2「核心」列` 的 t2 內距逐字就是用 `--sp-4 --sp-5`
    表示的，實作寫成 `padding:var(--sp-4) var(--sp-5)` 是**完全合規**的。
    不先解一次 token，這裡會量到 0 個 px 而誤判成「沒寫內距」。
    """
    return re.sub(
        r"var\(\s*(--[\w-]+)\s*\)",
        lambda m: str(tokens.SPACING.get(m.group(1), m.group(0))),
        value,
    )


def _px_values_under(
    css: str,
    classes: set[str] | tuple[str, ...],
    props: tuple[str, ...],
    *,
    max_px: int | None = None,
    exclude: set[str] | tuple[str, ...] = (),
) -> set[float]:
    """在指定 media 脈絡下，`.classes` 的規則裡、指定屬性宣告的所有 px 值。

    **格式無關**（總管指定的約束）：`17.5px` / `17.50px` / 空白多寡 / 屬性順序
    / shorthand vs longhand / `var(--sp-N)` 一律等價，⛔ 不做逐字字串比對。
    `exclude` 用來排掉「選擇器同時點到另一族 class」的規則
    （例：`.blk-t1 .sb-b1{font-size:…}` 不該算進 t1 的卡標字級）。
    """
    vals: set[float] = set()
    for media, sel, body in _iter_rules(css):
        if _media_max_px(media) != max_px:
            continue
        if not any(_selector_targets(sel, c) for c in classes):
            continue
        if any(_selector_targets(sel, c) for c in exclude):
            continue
        for decl in body.split(";"):
            prop, sep, value = decl.partition(":")
            if not sep:
                continue
            prop = prop.strip().lower()
            if not any(prop == p or prop.startswith(p + "-") for p in props):
                continue
            for num in re.findall(r"(-?\d+(?:\.\d+)?)\s*px", _resolve_spacing(value)):
                vals.add(float(num))
    return vals


def _keywords_under(css: str, classes, props: tuple[str, ...]) -> set[str]:
    """同上，但取關鍵字（如 `solid` / `dashed`）而非 px 數。"""
    out: set[str] = set()
    for media, sel, body in _iter_rules(css):
        if media is not None or not any(_selector_targets(sel, c) for c in classes):
            continue
        for decl in body.split(";"):
            prop, sep, value = decl.partition(":")
            if not sep:
                continue
            if not any(prop.strip().lower() == p or prop.strip().lower().startswith(p + "-")
                       for p in props):
                continue
            out.update(re.findall(r"[A-Za-z]+", value))
    return out


def _tier_classes(tier: str) -> set[str]:
    """該密度階在卡片上用的 class（＝含該階名的那些 class token）。

    ⚠️ 這裡沒有新增命名約束：「卡的 class 裡恰好出現一個階名」本來就已經被
    `test_card_container_class_carries_the_block_tier` 釘住了，本函式只是拿來定位。
    """
    block = next(b for b in ALL_BLOCKS if page_today.tier_for_block(b) == tier)
    classes = _first_tag_classes(_card(block, "live", value="1.0", level="中性"))
    hits = {c for c in classes if tier in c}
    assert hits, f"{tier}：卡片 class {sorted(classes)} 裡找不到帶階名的 class"
    return hits


def _sbadge_classes(key: str) -> set[str]:
    """徽章尺寸的 class（總管拍板：尺寸用 `.sb-{key}`）。"""
    return {f"sb-{key}"}


def _all_tier_classes() -> set[str]:
    return set().union(*(_tier_classes(t) for t in TIER_ORDER))


def _all_sbadge_classes() -> set[str]:
    return set().union(*(_sbadge_classes(k) for k in SBADGE_ORDER))


def _exclusive_to(groups: dict[str, set[float]], key: str) -> set[float]:
    """只屬於這一階、其他階都沒有的值。

    🔴 **為什麼要「獨佔」而不只是「有出現」**：如果實作寫一條
    `.blk-t1,.blk-t2,.blk-t3,.blk-t4{padding:10px 12px}` 的大通規則，
    「有出現」對四階**全部都會通過**（每一階的規則群都包含同一組值），
    四階密度已經被壓平了，測試卻全綠。獨佔性把這條路堵死。
    """
    others = set().union(*(v for k, v in groups.items() if k != key)) if len(groups) > 1 else set()
    return groups[key] - others


# ══════════════════════════════════════════════════════════════════
# 1b. 三個**可被突變測試的檢查器**
#
# 🔴 為什麼要把檢查邏輯抽成函式：v3 §03-1 要求「突變測試（拔掉修復邏輯必須轉為
#    紅燈）」。本檔下方「突變守衛」那一節會拿**真實實作的輸出**做定點破壞，
#    再要求這三支當場 `AssertionError` —— 把守衛本身也守起來。
#    （對照 `CLAUDE.md §-1.5.E` A7：規則 3 管「有沒有測試」，突變測試管
#     「**那個測試有沒有真的守到東西**」。）
# ══════════════════════════════════════════════════════════════════
def _check_var_referential_integrity(css: str) -> None:
    flat = _strip_style_tags(_CSS_COMMENT_RE.sub("", css))
    declared = set(re.findall(r"(--[\w-]+)\s*:", flat))
    referenced = set(re.findall(r"var\(\s*(--[\w-]+)", flat))
    assert referenced, "CSS 一個 `var()` 都沒用 —— token 層等於沒接上"
    orphan = referenced - declared
    assert not orphan, (
        f"引用了沒宣告的自訂屬性：{sorted(orphan)}；"
        "CSS 規範下這會退回繼承值，畫出一個看起來正常、實際上錯的顏色"
    )


def _check_badge_number_namespace(n: int, html: str) -> None:
    classes = _all_classes(html)
    assert f"bdg-{n}" in classes, f"#{n} 的 class {sorted(classes)} 裡沒有 bdg-{n}"
    collided = classes & set(components.SBADGE_SIZES)
    assert not collided, (
        f"#{n} 的 class 用到了尺寸鍵 {sorted(collided)}；"
        f"編號請用 bdg-{n}、尺寸請用 sb-<key>"
    )


def _check_no_orphan_responsive_grid_classes(css: str, minted: set[str]) -> None:
    bp = components.BREAKPOINTS
    responsive = {
        cls for cls in _class_names_in_css(css)
        if _declared_cols(css, cls, max_px=bp["mobile_max_px"])
        or _declared_cols(css, cls, max_px=bp["tablet_max_px"])
    }
    assert responsive == minted, (
        f"多餘的 RWD grid class：{sorted(responsive - minted)}；"
        f"缺少的：{sorted(minted - responsive)}"
    )


def _minted_grid_classes(css: str) -> set[str]:
    """本頁**應該**存在的 RWD 網格 class ＝ block 網格 ∪ 層級網格。"""
    return ({_grid_class_of(b, css) for b in COLS_BLOCKS}
            | {_layer_class_of(L, css) for L in GRID_LAYERS})


def _card(block: str, state: str, **kw) -> str:
    kw.setdefault("title", f"{block} 標題")
    kw.setdefault("badge_n", page_today.resolve_badge(state=state))
    kw.setdefault("facts", ())
    return markup.card_html(block=block, state=state, **kw)


def _clear_markup_caches() -> None:
    """`page_css` 若被 `lru_cache` 包住，spy 測試必須先清掉，否則量到的是快取。

    ⚠️ 這是對實作選擇的**容錯**，不是放寬守衛：清完之後該有的斷言一條都沒少。
    """
    for name in dir(markup):
        fn = getattr(markup, name, None)
        clear = getattr(fn, "cache_clear", None)
        if callable(clear):
            clear()
    _RULE_CACHE.clear()


@contextmanager
def _spy_get_token():
    """側錄 `page_css` 到底跟 `tokens.get_token` 要了哪些 token。

    `markup` 寫 `from src.ui_v2 import tokens` 或
    `from src.ui_v2.tokens import get_token` 兩種寫法都攔得到。
    """
    calls: list[tuple[str, str]] = []
    real = tokens.get_token

    def spy(name, *, mode):
        calls.append((name, mode))
        return real(name, mode=mode)

    targets = [(tokens, "get_token")]
    if getattr(markup, "get_token", None) is not None:
        targets.append((markup, "get_token"))
    saved = [(obj, attr, getattr(obj, attr)) for obj, attr in targets]
    for obj, attr in targets:
        setattr(obj, attr, spy)
    _clear_markup_caches()
    try:
        yield calls
    finally:
        for obj, attr, old in saved:
            setattr(obj, attr, old)
        _clear_markup_caches()


@contextmanager
def _poison_token(poisoned: str):
    """讓指定 token 變成「拿不到」，其餘照常 —— 驗「任何一個拿不到就整頁不出」。"""
    real = tokens.get_token

    def spy(name, *, mode):
        if name == poisoned:
            raise tokens.TokenNotSpecifiedError(f"WRT 下毒：{name!r} 故意拿不到")
        return real(name, mode=mode)

    targets = [(tokens, "get_token")]
    if getattr(markup, "get_token", None) is not None:
        targets.append((markup, "get_token"))
    saved = [(obj, attr, getattr(obj, attr)) for obj, attr in targets]
    for obj, attr in targets:
        setattr(obj, attr, spy)
    _clear_markup_caches()
    try:
        yield
    finally:
        for obj, attr, old in saved:
            setattr(obj, attr, old)
        _clear_markup_caches()


# ══════════════════════════════════════════════════════════════════
# C-1 每個元件渲染成什麼
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("block", COLS_BLOCKS)
def test_grid_container_class_carries_the_block_tier(block):
    """grid 容器的 class 對得上 `page_today.tier_for_block(block)`，且**只有**那一階。

    四階密度是**由層序自動掛**的（`UI_COMPONENTS.md §1`「⛔ 非逐塊手選」）——
    容器上同時出現兩階 class ＝ 手選從渲染層漏回來了。
    """
    expected = page_today.tier_for_block(block)
    classes = _first_tag_classes(_grid(block))
    tiers = set(components.CARD_TIERS)
    hit = {t for t in tiers if any(t in c for c in classes)}
    assert hit == {expected}, (
        f"{block}：容器 class {sorted(classes)} 對應到 {sorted(hit)}，應為 {expected!r}"
    )


@pytest.mark.parametrize("block", ALL_BLOCKS)
def test_card_container_class_carries_the_block_tier(block):
    """卡片本身也掛該 block 的密度階 —— 密度只能由它所在的層決定。"""
    expected = page_today.tier_for_block(block)
    classes = _first_tag_classes(_card(block, "live", value="1.0", level="中性"))
    hit = {t for t in components.CARD_TIERS if any(t in c for c in classes)}
    assert hit == {expected}, (
        f"{block}：卡片 class {sorted(classes)} 對應到 {sorted(hit)}，應為 {expected!r}"
    )


@pytest.mark.parametrize("block", COLS_BLOCKS)
def test_grid_html_is_one_self_contained_chunk(block):
    """一個 grid 必須是**自閉合的一整塊**，且把傳進去的卡整個吞進容器裡。

    🔴 這條守的是總管拍板的實作約束 2：**一個 grid 要在一次 `st.markdown`
    裡整段吐完**。未閉合的 `<div>` 不會跨呼叫包住下一次的產出
    —— 開閉數不等就代表這段在指望下一次呼叫幫它收尾。
    （repo 先例：`src/ui/render/station_cards.py` docstring 逐字
     「整面牆是一次 `st.markdown` 的純 HTML」。）
    """
    html = _grid(block)
    assert html.count("<div") == html.count("</div>"), (
        f"{block}：`<div>` 開 {html.count('<div')} 閉 {html.count('</div>')} —— "
        "未閉合的標籤不會跨 `st.markdown` 呼叫生效"
    )
    assert SENTINEL_CARD in html, f"{block}：傳進去的卡沒有出現在 grid 裡"
    head, _, tail = html.partition(SENTINEL_CARD)
    assert head.strip().startswith("<"), f"{block}：卡沒有被容器包住（前面不是標籤）"
    assert tail.strip().endswith(">"), f"{block}：容器沒有在卡之後收尾"


@pytest.mark.parametrize("n", ON_PAGE_BADGES)
def test_badge_html_carries_both_icon_and_text(n):
    """`UI_COMPONENTS.md §2` 硬規則：狀態色一律配**圖示＋文字**，⛔ 不得只靠顏色。

    ⚠️ 色盲不是唯一理由 —— `components._badge()` 的 assert 已經擋住「規格裡沒填」，
    但**規格填了、渲染時掉了**是另一回事，只有渲染層測得到。
    """
    spec = components.badge(n)
    html = markup.badge_html(n)
    assert spec["icon"] in html, f"#{n} 的圖示 {spec['icon']!r} 沒有被渲染出來"
    assert spec["text"] in html, f"#{n} 的文字 {spec['text']!r} 沒有被渲染出來"


@pytest.mark.parametrize("n", ON_PAGE_BADGES)
def test_badge_html_uses_the_bdg_number_namespace(n):
    """徽章**編號**的 class 是 `.bdg-{n}`（總管拍板的實作約束 4）。"""
    classes = _all_classes(markup.badge_html(n))
    assert f"bdg-{n}" in classes, f"#{n} 的 class {sorted(classes)} 裡沒有 bdg-{n}"


@pytest.mark.parametrize("n", ON_PAGE_BADGES)
def test_badge_number_class_never_collides_with_a_badge_size_class(n):
    """🔴 **編號**命名空間與**尺寸**命名空間不得撞名。

    `components.SBADGE_SIZES` 的鍵是 `b1`~`b4`（那是**尺寸**，依卡層 t1→b1…t4→b4）。
    徽章編號有 1~9，若編號也寫成 `b1`~`b9`，`b1`~`b4` 這四個就同時是
    「第 1~4 號徽章」和「四種尺寸」—— **一個 class 兩個意思，CSS 會互相蓋掉**，
    而且蓋出來的畫面看起來完全正常（錯的尺寸配對的顏色），沒有人會發現。
    """
    _check_badge_number_namespace(n, markup.badge_html(n))


@pytest.mark.parametrize("n", ON_PAGE_BADGES)
def test_card_html_actually_embeds_the_badge_it_was_handed(n):
    """卡片必須把 `badge_n` 那顆徽章**真的畫進去**。

    🔴 沒有這一條，`card_html` 可以整個忽略 `badge_n` 參數：
    上面那些徽章測試全綠（它們測的是 `badge_html` 自己），
    卡面卻一顆徽章都沒有 —— 而「狀態」正是這一頁的全部重點。
    """
    spec = components.badge(n)
    html = _card("today.summary", "live", value="1.0", level="中性", badge_n=n)
    assert f"bdg-{n}" in _all_classes(html), f"卡面沒有帶上 #{n} 的徽章 class"
    assert spec["icon"] in html and spec["text"] in html, (
        f"卡面有 #{n} 的 class，卻沒有它的圖示／文字"
    )


def test_css_keeps_the_two_badge_namespaces_apart():
    """CSS 這一側同樣要分得開：`.bdg-{n}` 與 `.sb-{key}` 兩組選擇器零交集。"""
    css = markup.page_css("dark")
    names = _class_names_in_css(css)
    number_classes = {f"bdg-{n}" for n in ON_PAGE_BADGES}
    size_classes = {f"sb-{k}" for k in components.SBADGE_SIZES}

    assert number_classes <= names, f"CSS 缺少編號選擇器：{sorted(number_classes - names)}"
    assert size_classes <= names, f"CSS 缺少尺寸選擇器：{sorted(size_classes - names)}"
    assert not (number_classes & size_classes), "兩個命名空間撞名"
    bare = names & set(components.SBADGE_SIZES)
    assert not bare, f"CSS 出現裸尺寸 class {sorted(bare)}；尺寸一律 `.sb-<key>`"


# ══════════════════════════════════════════════════════════════════
# C-2 四層結構 ＋ 三斷點
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("layer", LAYER_IDS)
def test_every_block_in_a_layer_renders_that_layers_tier(layer):
    """**四層結構**：一層裡的每個 block，密度都等於 `components.tier_for_layer(layer)`。

    契約層（`page_today`）與渲染層（`markup`）兩邊都要對得上 ——
    契約對、渲染掉，畫面照樣是錯的。
    """
    expected = components.tier_for_layer(layer)
    blocks = page_today.blocks_of_layer(layer)
    assert blocks, f"第 {layer} 層沒有任何 block"
    for block in blocks:
        assert page_today.tier_for_block(block) == expected, (
            f"{block} 在第 {layer} 層，密度應為 {expected!r}"
        )
        classes = _first_tag_classes(_card(block, "live", value="1.0", level="中性"))
        hit = {t for t in components.CARD_TIERS if any(t in c for c in classes)}
        assert hit == {expected}, (
            f"{block}：渲染出來的 class {sorted(classes)} 不是第 {layer} 層的 {expected!r}"
        )


@pytest.mark.parametrize("block", COLS_BLOCKS)
def test_page_css_declares_all_three_breakpoint_column_counts(block):
    """⭐ **三斷點**（降級成 CSS 文字斷言 —— 這是「三個斷點」在本檔的替身）。

    對每個 block，`page_css("dark")` 必須**同時**含三段欄數宣告：
      · 基準規則        欄數 == `resolve_cols(cols, 桌機寬)`
      · `@media (max-width:<平板斷點>)` 段內 == `resolve_cols(cols, 平板寬)`
      · `@media (max-width:<手機斷點>)` 段內 == `resolve_cols(cols, 手機寬)`

    ⚠️ 斷點數字一律取自 `components.BREAKPOINTS`，⛔ 不寫死 640 / 880。
    ⚠️ 三段**都要有**，即使三個欄數相同（如 `(1,1,1)`）——
       顯式寫出來，下一個人才看得到「這是刻意的」而不是「漏寫」。
    ⚠️ **本條不證明瀏覽器真的這樣排**（見檔頭「證明了什麼、沒證明什麼」）。

    🔴 為什麼走 CSS grid 而不是 `st.columns`（總管複驗的實證）：
       `st.context` 只有 `cookies/headers/ip_address/is_embedded/locale/theme/
       timezone/timezone_offset/url`，**沒有任何寬度**；`st.*` 無 viewport API；
       `AppTest` 簽章無 viewport 參數 ⇒ `st.columns(n)` 的 `n` 是伺服器端常數，
       **兩個斷點無處可掛**。
    """
    css = markup.page_css("dark")
    bp = components.BREAKPOINTS
    cols = page_today.BLOCK_COLS[block]
    cls = _grid_class_of(block, css)

    wanted = (
        (None, bp["desktop_min_px"], "基準規則（桌機）"),
        (bp["tablet_max_px"], bp["tablet_max_px"], f"@media max-width:{bp['tablet_max_px']}px（平板）"),
        (bp["mobile_max_px"], bp["mobile_max_px"], f"@media max-width:{bp['mobile_max_px']}px（手機）"),
    )
    for max_px, viewport, where in wanted:
        want = components.resolve_cols(cols, viewport)
        got = _declared_cols(css, cls, max_px=max_px)
        assert got, f"{block}（.{cls}）：{where} 完全沒有宣告 grid-template-columns"
        assert all(c == want for c in got), (
            f"{block}（.{cls}）：{where} 宣告成 {got} 欄，"
            f"應為 {want}（cols={cols}，viewport={viewport}px）"
        )


def test_media_queries_use_exactly_the_two_breakpoints_from_components():
    """CSS 裡的 `max-width` 斷點只准是 `components.BREAKPOINTS` 那兩個。

    寫成 `879px`／`940px` 會讓上一條**整條失效**（它照 SSOT 的數字去找段落，
    找不到就當成「沒宣告」）—— 但更糟的是畫面在 880px 那一格真的會排錯。
    """
    css = markup.page_css("dark")
    bp = components.BREAKPOINTS
    allowed = {bp["mobile_max_px"], bp["tablet_max_px"]}
    found = {
        int(m) for m in re.findall(
            r"max-width\s*:\s*(\d+)\s*px",
            _strip_style_tags(_CSS_COMMENT_RE.sub("", css)),
        )
    }
    assert found, "CSS 裡一個 `max-width` 斷點都沒有 —— RWD 整個不存在"
    assert found <= allowed, (
        f"出現不在 SSOT 裡的斷點 {sorted(found - allowed)}；"
        f"斷點 SSOT 是 components.BREAKPOINTS {dict(bp)}"
    )


def test_blocks_with_the_same_cols_share_exactly_one_grid_class():
    """🔴 總管拍板的實作約束 5：**只產 `BLOCK_COLS` 真的出現過的 grid class**。

    實測 `BLOCK_COLS` 只有兩種 `cols`（`(1,1,1)` 與 `(3,2,1)`）——
    同一種 `cols` 的 block 共用同一個 class、不同 `cols` 用不同 class
    ⇒ **class 數恰等於 cols 種類數**，⛔ 不是 3×3×3 ＝ 27 個組合。
    """
    css = markup.page_css("dark")
    by_cols: dict[tuple[int, int, int], set[str]] = {}
    for block, cols in page_today.BLOCK_COLS.items():
        by_cols.setdefault(cols, set()).add(_grid_class_of(block, css))

    for cols, classes in sorted(by_cols.items()):
        assert len(classes) == 1, (
            f"cols={cols} 的 block 分到了 {sorted(classes)} 兩個以上的 class"
        )
    minted = {next(iter(c)) for c in by_cols.values()}
    assert len(minted) == len(by_cols), (
        f"{len(by_cols)} 種 cols 卻只有 {len(minted)} 個 class —— 不同 cols 被併成同一個"
    )


def test_no_responsive_grid_class_is_minted_for_a_cols_combo_that_never_occurs():
    """CSS 裡有 RWD 欄數覆寫的 class，只准是 **block 網格 ∪ 層級網格** 那幾個。

    多出來的就是「先把 27 種組合都產一遍」——
    死 CSS 不會報錯、不會變紅，只會讓下一個人以為那些 class 有人在用。
    """
    css = markup.page_css("dark")
    _check_no_orphan_responsive_grid_classes(css, _minted_grid_classes(css))


def test_the_block_grid_is_the_inside_block_grid_not_the_layer_grid():
    """🔴 `BLOCK_COLS` 是**卡內**一列幾格，⛔ 不是「這個 block 在層裡佔幾欄」。

    `page_today.cols_scope()` 逐字回 `"inside_block"`；同一層的 block 彼此
    怎麼並排另有 `LAYER_GRID_COLS`／`blocks_per_row()`。
    兩者混用會畫出一個看起來很正常、但版面結構完全錯掉的頁面
    —— 例如 `today.holdings`（卡內 `(1,1,1)`）被當成「獨佔一列」堆在第二層底部，
    正面違反客戶 2026-09-16「第二層＝3 張並排卡」的裁示。

    ⚠️ 本條**只驗 `markup` 沒有把層級網格的數字搬進 block 網格**；
       層級網格本身怎麼畫**不在 `markup` 的公開介面裡**，⛔ 本組不發明契約。
    """
    css = markup.page_css("dark")
    bp = components.BREAKPOINTS
    checked = 0
    for block in COLS_BLOCKS:
        assert page_today.cols_scope(block) == "inside_block"
        for entry in page_today.LAYERS:
            if block not in entry["blocks"]:
                continue
            try:
                layer_cols = page_today.LAYER_GRID_COLS[entry["layer"]]
            except KeyError:
                continue   # 該層沒登記層級網格 → 沒有可混淆的對象
            if layer_cols == page_today.BLOCK_COLS[block]:
                continue   # 兩個網格剛好同值 → 這個 block 分辨不出來，跳過
            cls = _grid_class_of(block, css)
            want = components.resolve_cols(page_today.BLOCK_COLS[block], bp["desktop_min_px"])
            leak = components.resolve_cols(layer_cols, bp["desktop_min_px"])
            got = _declared_cols(css, cls, max_px=None)
            assert all(c == want for c in got), (
                f"{block}：block 網格被畫成 {got} 欄，卡內應為 {want} 欄；"
                f"{leak} 是第 {entry['layer']} 層的**層級**網格欄數，兩者不是同一件事"
            )
            checked += 1
    assert checked, (
        "沒有任何 block 能分辨兩種網格（兩者恰好同值）——"
        "本條這一輪沒有鑑別力，請在 BLOCK_COLS 有分歧值時重看"
    )


# ══════════════════════════════════════════════════════════════════
# C-2b 層級網格（`layer_html`）—— 總管 2026-09-21 補的第五支契約
#
# 🔴 **這一層原本表達不出來。** 前一輪的四支介面（`page_css` / `badge_html` /
#    `card_html` / `grid_html`）沒有「同一層的幾個 block 怎麼並排」的位置 ⇒
#    八個 block 只會直向堆疊 ⇒ 正面違反客戶 2026-09-16「第二層＝**3 張並排卡**」。
#    ⚠️ 與 `BLOCK_COLS` 是**兩個不同的網格**：`BLOCK_COLS` 是**卡內**一列幾格
#    （`page_today.cols_scope()` 逐字回 `"inside_block"`），本節是**層級**網格。
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("layer", GRID_LAYERS)
def test_layer_html_declares_all_three_breakpoint_column_counts(layer):
    """層級網格同樣要**三段都顯式寫出**（與 block 網格那條同一把尺）。

    欄數取 `page_today.LAYER_GRID_COLS[layer]`，語意與 `BLOCK_COLS` 相同
    （三斷點、夾 `components.MAX_COLS`）。
    ⚠️ 斷點與欄數一律從 SSOT 算，⛔ 不寫死 640 / 880 / 3 / 2 / 1。
    ⚠️ 同 block 網格那條：本條證明的是 **CSS 文字**一致，
       **不證明**瀏覽器真的排成那樣。
    """
    css = markup.page_css("dark")
    bp = components.BREAKPOINTS
    cols = page_today.LAYER_GRID_COLS[layer]
    cls = _layer_class_of(layer, css)

    for max_px, viewport, where in (
        (None, bp["desktop_min_px"], "基準規則（桌機）"),
        (bp["tablet_max_px"], bp["tablet_max_px"], f"@media max-width:{bp['tablet_max_px']}px（平板）"),
        (bp["mobile_max_px"], bp["mobile_max_px"], f"@media max-width:{bp['mobile_max_px']}px（手機）"),
    ):
        want = components.resolve_cols(cols, viewport)
        got = _declared_cols(css, cls, max_px=max_px)
        assert got, f"第 {layer} 層（.{cls}）：{where} 完全沒有宣告 grid-template-columns"
        assert all(c == want for c in got), (
            f"第 {layer} 層（.{cls}）：{where} 宣告成 {got} 欄，"
            f"應為 {want}（LAYER_GRID_COLS={cols}，viewport={viewport}px）"
        )


@pytest.mark.parametrize("layer", GRID_LAYERS)
def test_a_gridded_layer_fits_on_exactly_one_row_on_desktop(layer):
    """🔴 **桌機第二層恰好 1 列** —— 三張卡並排，⛔ 沒有任何一張被擠到下一列。

    這是「`today.holdings` ⛔ 不是疊在最下面的全寬卡」在**渲染層**的守衛。
    `BLOCK_COLS["today.holdings"] == (1,1,1)` 講的是**卡內**一列一格；
    誰要是把它讀成「它獨佔一列」，畫出來就是第二層變成
    「兩張並排 ＋ 一張全寬墊底」，正面違反客戶 2026-09-16 的裁示。

    oracle 是 `page_today.rows_of_layer` / `blocks_per_row`（⛔ 不另立第二把尺）。
    ⚠️ 桌機寬取 `BREAKPOINTS["desktop_min_px"]`（⛔ 不寫死 1440）——
       `resolve_cols` 對任何 > 平板斷點的寬度給同一個答案。
    """
    css = markup.page_css("dark")
    bp = components.BREAKPOINTS
    desktop = bp["desktop_min_px"]
    blocks = page_today.blocks_of_layer(layer)

    assert page_today.rows_of_layer(layer, desktop) == 1, (
        f"第 {layer} 層在桌機要排成 1 列，`rows_of_layer` 卻說 "
        f"{page_today.rows_of_layer(layer, desktop)} 列"
    )
    per_row = page_today.blocks_per_row(layer, desktop)
    assert per_row >= len(blocks), (
        f"第 {layer} 層有 {len(blocks)} 個 block，一列卻只排得下 {per_row} 個"
    )

    cls = _layer_class_of(layer, css)
    got = _declared_cols(css, cls, max_px=None)
    assert all(c == per_row for c in got), (
        f"第 {layer} 層的層級網格在桌機宣告成 {got} 欄，應為 {per_row} 欄 —— "
        f"少一欄就會把第 {len(blocks)} 個 block 擠到下一列"
    )


@pytest.mark.parametrize("layer", GRID_LAYERS)
def test_layer_html_is_one_self_contained_chunk_holding_every_block(layer):
    """層級網格同樣是**自閉合的一整塊**，且**一個 block 都不准掉**。

    掉一個 block 的後果跟排版錯一樣嚴重，而且更難發現 ——
    畫面上只是「少一張卡」，不會有任何錯誤。
    """
    blocks = _sentinel_blocks(len(page_today.blocks_of_layer(layer)))
    html = markup.layer_html(layer=layer, block_htmls=blocks)
    assert html.count("<div") == html.count("</div>"), (
        f"第 {layer} 層：`<div>` 開 {html.count('<div')} 閉 {html.count('</div>')}"
    )
    for b in blocks:
        assert b in html, f"第 {layer} 層：block {b!r} 沒有被放進層級網格"
    positions = [html.index(b) for b in blocks]
    assert positions == sorted(positions), f"第 {layer} 層：block 的順序被打亂了"


def test_layer_grid_classes_never_collide_with_block_grid_classes():
    """🔴 層級網格 class ⛔ 不得與 block 網格 class 撞名。

    ⚠️ ~~第二層的層級網格 `(3,2,1)` 與 `today.summary` 的**卡內**網格 `(3,2,1)`~~
    ~~**數字剛好一樣** —— 於是「共用同一個 class」會是很自然的省事寫法。~~
    🔵 **2026-09-22 事實更正（⛔ 不是漏刪；決策者：客戶，裁示 B）**：
    `today.summary` 的卡內網格**已被客戶覆寫成 `(1,1,1)`**，⇒ 上面那個「剛好一樣」的
    舉例**不再成立**。⚠️ **本條的理由一個字都沒有變弱，斷言也⛔ 未動** ——
    「數字剛好一樣」的情形**現在由 `today.detail` 承接**（它的卡內網格仍是 `(3,2,1)`，
    與第二層層級網格同值）。⇒ 舉例換了主角，風險一模一樣。
    **⛔ 不行（理由原文）**：兩者是不同語意的兩個網格（一個管 block 之間、一個管卡之間），
    哪天客戶把第二層改成 4 欄、或把某個 block 的卡內網格改成 2 欄，
    共用的那個 class 會讓**另一個也跟著動**，而且沒有人會預期到。
    （同本檔既有的 `.bdg-{n}` vs `.sb-{key}` 命名空間紀律。）

    🔴 **⚠️ 這不是假設，它 2026-09-22 真的發生了一次**：客戶把 `today.summary`
    的卡內網格從 `3/2/1` 改成 `1/1/1`，而**第二層的層級網格必須維持 `3/2/1`**
    （客戶同一次裁示逐字「layer_html 的 3 欄不變」）。
    若當初兩者共用了同一個 class，這次改動會**連帶把三張卡疊成直條** ——
    正面違反客戶 2026-09-16「第二層＝3 張並排卡」的裁示，而且畫面上不會有任何錯誤。
    """
    css = markup.page_css("dark")
    block_cls = {_grid_class_of(b, css) for b in COLS_BLOCKS}
    layer_cls = {_layer_class_of(L, css) for L in GRID_LAYERS}
    assert layer_cls, "一個層級網格 class 都沒有"
    collided = block_cls & layer_cls
    assert not collided, (
        f"層級網格與 block 網格共用了 class {sorted(collided)} —— "
        "兩者語意不同，⛔ 不得共用（數字目前剛好相同，不代表以後也會）"
    )


@pytest.mark.parametrize("layer", UNGRIDDED_LAYERS)
def test_layer_html_raises_for_a_layer_with_no_registered_layer_grid(layer):
    """🔴 沒登記層級網格的層 → **炸**，⛔ 不得回一個猜的值。

    `page_today.LAYER_GRID_COLS` 只登記第二層（客戶 2026-09-16「3 張並排卡」
    ＋ 原型 `.g3` 實測）；其餘各層**無來源**，`blocks_per_row()` 逐字寫
    「⛔ 不回一個猜的值：『猜一個看起來合理的排法』正是 §1 禁止的
    『自己估一個合理值』」。渲染層必須把那個 raise 傳出來 ——
    ⛔ **不得預設 1 欄蒙混過去**（預設 1 欄看起來完全正常，
    而它正是「沒有來源」被悄悄變成「有一個答案」的那一步）。
    """
    produced = []
    with pytest.raises(KeyError):
        produced.append(_layer(layer, 2))
    assert not produced, (
        f"第 {layer} 層沒有登記層級網格，layer_html 卻還是吐出了 HTML"
    )


# ══════════════════════════════════════════════════════════════════
# C-3 九種狀態
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("n", ON_PAGE_BADGES)
def test_every_on_page_badge_paints_its_colours_from_the_stylesheet(n):
    """九種狀態各自的顏色 token 出現在 `.bdg-{n}` 的 CSS 規則裡。

    顏色**住 `<style>`**，⛔ 不在 inline style（見下一條）——
    inline 顏色會繞過 `:root` 的 dark/light 切換，
    模式一換就變成一片對不上的顏色。
    """
    css = markup.page_css("dark")
    spec = components.badge(n)
    bodies = "\n".join(
        body for media, sel, body in _iter_rules(css)
        if _selector_targets(sel, f"bdg-{n}")
    )
    assert bodies.strip(), f"CSS 裡沒有任何 `.bdg-{n}` 規則"
    for key in ("fg", "bg", "border_color"):
        token = spec[key]
        assert isinstance(token, str) and token.startswith("--"), (
            f"#{n} 的 {key} 不是 token 名：{token!r}"
        )
        assert re.search(rf"var\(\s*{re.escape(token)}\s*\)", bodies), (
            f"`.bdg-{n}` 的規則裡沒有引用 {key} 的 token {token}"
        )


@pytest.mark.parametrize("n", ON_PAGE_BADGES)
def test_badge_html_carries_no_inline_colour(n):
    """徽章 HTML 的 `style=` 裡⛔ 不得出現顏色 —— 顏色一律走 `<style>`。"""
    html = markup.badge_html(n)
    for m in re.finditer(r'style\s*=\s*"([^"]*)"', html):
        decl = m.group(1).lower()
        assert "color" not in decl and "background" not in decl, (
            f"#{n} 把顏色寫進 inline style：{m.group(1)!r}"
        )


def test_badge_9_shares_no_colour_token_with_badge_1_in_the_css():
    """`UI_COMPONENTS.md §2 徽章表 #9「資料不完整」列`「#9 ⛔ 與 #1 零共用色 token」—— 在**渲染出來的 CSS** 上驗。

    #1「正常」是綠燈、#9「資料不完整」是「這個數字只算到一半」。
    共用任何一個色 token，使用者就會把「半套資料」讀成「一切正常」。
    ⚠️ `tests/ui_v2/test_components.py` 已經在**規格資料**上驗過同一件事；
       本條驗的是**規格對了、CSS 有沒有照做**，兩條不互相取代。
    """
    css = markup.page_css("dark")
    keys = ("bg", "fg", "border_color")
    t1 = {components.badge(1)[k] for k in keys}
    t9 = {components.badge(9)[k] for k in keys}
    assert not (t1 & t9), f"規格層就已經共用：{sorted(t1 & t9)}"

    def _vars_of(n: int) -> set[str]:
        bodies = "\n".join(
            body for media, sel, body in _iter_rules(css)
            if _selector_targets(sel, f"bdg-{n}")
        )
        return set(re.findall(r"var\(\s*(--[\w-]+)", bodies))

    v1, v9 = _vars_of(1), _vars_of(9)
    assert v1 and v9, f"CSS 找不到 .bdg-1 / .bdg-9 的規則（{sorted(v1)} / {sorted(v9)}）"
    assert not (v1 & v9), f"CSS 裡 #1 與 #9 共用了色 token：{sorted(v1 & v9)}"


# ══════════════════════════════════════════════════════════════════
# C-1b 四階密度幾何 —— 總管 2026-09-21 裁示補的洞
#
# 🔴 **為什麼非守不可**：`UI_PRINCIPLES.md` 第 3 條「資訊密度遞減」判 ✅
#    **正是靠**這個四階階梯（內距 15/17→10/12→6/9→5/9、卡標
#    17.5→14.5→13→12.5px、徽章 min-h 46→36→28→26）。
#    `test_components.py` 釘的是「**規格資料**對不對」；在此之前
#    **沒有任何測試要求 `markup` 把它吐進 CSS** ⇒ 實作可以整組忽略幾何、
#    畫面密度全平，而測試全綠 ⇒ 就是「文件宣稱 ✅、code 沒做到」。
#
# ⛔ **本節不替實作定 CSS 長相**（總管明示的約束）：
#    · 斷言的是「**值有沒有出現、對不對得上 SSOT**」，⛔ 不是「CSS 要怎麼寫」；
#    · **格式無關**：`17.5px` / `17.50px` / 空白 / 屬性順序 / shorthand vs
#      longhand / `padding:var(--sp-4) var(--sp-5)` 一律等價（見 `_px_values_under`）；
#    · 值一律動態讀 `components.CARD_TIERS` / `SBADGE_SIZES`，⛔ 不寫死數字。
#
# ⚠️ **本節確實加了一條實作要求**（誠實揭露，非規格明文）：
#    四階的內距／卡標字級與四尺寸的字級／min-height，**必須各自掛在自己那一階的
#    class 上** —— ⛔ 不要把其中一階藏進 `.blk` 之類的基準規則再覆寫其餘三階。
#    理由：那樣階梯就只剩三階「量得到」，第四階變成「靠繼承」，
#    機器無從分辨它是刻意的還是被壓平的。實作仍可自由決定怎麼寫規則。
# ══════════════════════════════════════════════════════════════════
def _tier_groups(props: tuple[str, ...], *, max_px: int | None = None) -> dict[str, set[float]]:
    css = markup.page_css("dark")
    return {
        t: _px_values_under(css, _tier_classes(t), props,
                            max_px=max_px, exclude=_all_sbadge_classes())
        for t in TIER_ORDER
    }


def _sbadge_groups(props: tuple[str, ...]) -> dict[str, set[float]]:
    css = markup.page_css("dark")
    return {
        k: _px_values_under(css, _sbadge_classes(k), props,
                            exclude=_all_tier_classes())
        for k in SBADGE_ORDER
    }


@pytest.mark.parametrize("tier", TIER_ORDER)
def test_each_card_tier_emits_its_own_padding(tier):
    """每一階的內距要出現在**它自己那一階**的規則裡，且**垂直內距為該階獨佔**。

    獨佔性擋的是「一條 `.blk-t1,.blk-t2,.blk-t3,.blk-t4{padding:…}` 大通規則」——
    那種寫法下「有出現」對四階全部通過，密度卻已經被壓平（見 `_exclusive_to`）。
    ⚠️ 水平內距只驗「有出現」不驗獨佔：`CARD_TIERS` 裡 t3／t4 的水平內距
       本來就同值（規格如此），要求獨佔會是一條假紅燈。
    """
    groups = _tier_groups(("padding",))
    vertical, horizontal = components.CARD_TIERS[tier]["padding_px"]

    assert groups[tier], f"{tier}：CSS 裡它自己那一階完全沒有內距宣告"
    assert vertical in _exclusive_to(groups, tier), (
        f"{tier}：垂直內距 {vertical}px 不是該階獨佔"
        f"（該階量到 {sorted(groups[tier])}）—— 四階密度可能被壓平了"
    )
    assert horizontal in groups[tier], (
        f"{tier}：水平內距 {horizontal}px 沒有出現（量到 {sorted(groups[tier])}）"
    )


@pytest.mark.parametrize("tier", TIER_ORDER)
def test_each_card_tier_emits_its_own_title_font_size(tier):
    """卡標字級同理：四階字級互不相同，所以一律要求**獨佔**。"""
    groups = _tier_groups(("font-size",))
    want = components.CARD_TIERS[tier]["title_px"]
    assert want in _exclusive_to(groups, tier), (
        f"{tier}：卡標字級 {want}px 不是該階獨佔（該階量到 {sorted(groups[tier])}）"
    )


@pytest.mark.parametrize("size", SBADGE_ORDER)
def test_each_badge_size_emits_its_own_font_size_and_min_height(size):
    """四種徽章尺寸的字級與 min-height 同樣要各自落在自己的 `.sb-{key}` 上。

    徽章 min-height 是**觸控目標**：`b1` 46px、`b4` 26px。
    壓平它不只是「看起來一樣」，是把 t1 那顆主結論燈的可點區縮掉快一半。
    """
    font_groups = _sbadge_groups(("font-size",))
    height_groups = _sbadge_groups(("min-height",))
    spec = components.SBADGE_SIZES[size]

    assert spec["font_px"] in _exclusive_to(font_groups, size), (
        f"{size}：字級 {spec['font_px']}px 不是該尺寸獨佔"
        f"（量到 {sorted(font_groups[size])}）"
    )
    assert spec["min_height_px"] in _exclusive_to(height_groups, size), (
        f"{size}：min-height {spec['min_height_px']}px 不是該尺寸獨佔"
        f"（量到 {sorted(height_groups[size])}）"
    )


def test_t1_mobile_padding_override_lands_inside_the_mobile_media_query():
    """t1 是四階中**唯一**有 ≤640 內距覆寫的一階（`padding_mobile_px`）。

    ⛔ 其餘三階 `padding_mobile_px` 為 `None` ⇒ **不得發明**一組手機內距
    （`CLAUDE.md §1` 反捏造：規格沒給的值，⛔ 不准自己估一個合理的）。
    """
    bp = components.BREAKPOINTS
    groups = _tier_groups(("padding",), max_px=bp["mobile_max_px"])
    with_override = {t for t in TIER_ORDER
                     if components.CARD_TIERS[t]["padding_mobile_px"] is not None}
    assert with_override, "CARD_TIERS 已經沒有任何一階有手機內距覆寫 —— 本條要重寫"

    for tier in TIER_ORDER:
        override = components.CARD_TIERS[tier]["padding_mobile_px"]
        if override is None:
            assert not groups[tier], (
                f"{tier} 的 padding_mobile_px 是 None，CSS 卻在手機斷點內"
                f"宣告了內距 {sorted(groups[tier])} —— ⛔ 規格沒給的值不得自行發明"
            )
        else:
            for want in override:
                assert want in groups[tier], (
                    f"{tier}：手機內距 {want}px 沒有出現在 "
                    f"@media max-width:{bp['mobile_max_px']}px 內（量到 {sorted(groups[tier])}）"
                )


@pytest.mark.parametrize(
    "what, props, spec_key, picker",
    [
        ("卡片垂直內距", ("padding",), "padding_px", lambda v: v[0]),
        ("卡標字級", ("font-size",), "title_px", lambda v: v),
    ],
)
def test_the_card_density_ladder_survives_into_the_css(what, props, spec_key, picker):
    """⭐ **階梯的單調性**：四階在 CSS 裡必須是**嚴格遞減**的。

    這條比「值對不對」更抓得到「有人把四階壓平」——
    每一階的值都先證明是**該階獨佔**（所以真的是從 CSS 量出來的，
    不是靠規格資料背書），再檢查它們由 t1 到 t4 嚴格遞減。
    ⚠️ 純資料面的單調性另有 `test_components.py::test_density_ladder_is_monotonic`
       在守；本條守的是「**那個階梯有沒有活著走進 CSS**」，兩條不互相取代。
    """
    groups = _tier_groups(props)
    ladder = []
    for tier in TIER_ORDER:
        want = picker(components.CARD_TIERS[tier][spec_key])
        assert want in _exclusive_to(groups, tier), (
            f"{what}：{tier} 的 {want}px 不是該階獨佔，階梯量不出來"
            f"（該階量到 {sorted(groups[tier])}）"
        )
        ladder.append(want)
    assert all(a > b for a, b in zip(ladder, ladder[1:])), (
        f"{what}的階梯不是嚴格遞減：{dict(zip(TIER_ORDER, ladder))} —— "
        "「資訊密度遞減」這條設計原則在 CSS 裡沒有落地"
    )


def test_the_badge_min_height_ladder_survives_into_the_css():
    """同上，守徽章尺寸的 min-height 階梯（觸控目標一路縮小）。"""
    groups = _sbadge_groups(("min-height",))
    ladder = []
    for size in SBADGE_ORDER:
        want = components.SBADGE_SIZES[size]["min_height_px"]
        assert want in _exclusive_to(groups, size), (
            f"{size} 的 min-height {want}px 不是該尺寸獨佔（量到 {sorted(groups[size])}）"
        )
        ladder.append(want)
    assert all(a > b for a, b in zip(ladder, ladder[1:])), (
        f"徽章 min-height 階梯不是嚴格遞減：{dict(zip(SBADGE_ORDER, ladder))}"
    )


def test_only_the_tiers_that_spec_says_are_dashed_are_dashed_in_the_css():
    """四階的框線樣式：`CARD_TIERS` 說哪一階 dashed，CSS 就只有那一階 dashed。

    t4「佐證」是四階中唯一的 dashed —— 那是「這是佐證、不是結論」的視覺訊號。
    ⛔ 全部改成 solid（或全部 dashed）＝ 把那個訊號抹掉。
    ⚠️ 值一律從 `CARD_TIERS` 動態讀，⛔ 不寫死「只有 t4」。
    """
    css = markup.page_css("dark")
    for tier in TIER_ORDER:
        want = components.CARD_TIERS[tier]["border_style"]
        got = _keywords_under(css, _tier_classes(tier), ("border",))
        got = {k for k in got if k in {"solid", "dashed", "dotted", "double", "none"}}
        assert got, f"{tier}：CSS 裡它自己那一階沒有任何框線樣式宣告"
        assert got == {want}, (
            f"{tier}：框線樣式應為 {want!r}，CSS 量到 {sorted(got)}"
        )


# ══════════════════════════════════════════════════════════════════
# §1 Fail Loud（CLAUDE.md §1）—— 總管加的守衛，⛔ 不可省
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("mode", MODES)
def test_page_css_raises_exactly_when_that_mode_still_has_a_tbd_token(mode):
    """帶 `TBD` 的模式必須**炸**；不帶的必須**產得出東西**。

    2026-09-21 當下：`light` 的 `--sig-neutral` / `--sig-neutral-bg` 仍是 `TBD`
    （`tokens.py` 檔頭逐字引 `UI_TOKENS.md §A-2`「客戶只指定 dark 兩碼，
    ⛔ 本檔不得自行發明 light 值」）⇒ 這一輪 `light` 應該炸。
    ⚠️ **但本條讀的是 `tokens` 的現況，不是那個日期** —— 客戶補完 light 值之後，
    本條自動翻面要求 `light` 產得出一張合格 sheet，⛔ 不會變成一條假紅燈。
    """
    tbd = _tbd_names(mode)
    produced: list[str] = []
    if tbd:
        with pytest.raises(tokens.TokenNotSpecifiedError):
            produced.append(markup.page_css(mode))
        assert not produced, (
            f"page_css({mode!r}) 竟然回傳了字串 —— {sorted(tbd)} 還是 TBD，應該 raise"
        )
    else:
        produced.append(markup.page_css(mode))
        assert produced[0].strip(), f"{mode} 的 token 都齊了，page_css 卻回空字串"


def test_page_css_really_asks_for_the_tbd_token_rather_than_skipping_it():
    """🔴 它必須是**問了才炸**，⛔ 不是「把 TBD 的那幾個跳過不輸出」。

    跳過的後果（CSS 規範）：`:root` 少了 `--sig-neutral`，但
    `.bdg-9{color:var(--sig-neutral)}` 還在 ⇒ `var()` 指向未定義的自訂屬性
    ⇒ invalid at computed-value time ⇒ 退回繼承值
    ⇒ **畫面上出現一個看起來正常、實際上是錯的顏色**。
    那比整頁炸掉危險得多（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ⛔⛔ **看到它 SKIPPED 請不要順手刪掉 —— 它沒壞，是目前沒有施力點。**
    2026-09-21 客戶補訂了 `--sig-neutral` / `--sig-neutral-bg` 的 light 值之後，
    兩個模式已經**一個 `TBD` 都不剩**，本條因此會 skip。
    **skip ⛔ 不等於通過。** 下一個「客戶只給 dark」的 token 一出現，
    它馬上又有牙齒（`tokens.py` 檔頭也寫了同一件事：
    「`TBD` 機制目前沒有任何 token 在用…⛔ 機制本身不得因此刪除」）。

    ⚠️ **空窗期的紀律由誰承接**：`test_any_unavailable_token_kills_the_whole_sheet`
    —— 它**自己對每一個 token 下毒**，不靠 `TBD` 存在，
    所以「拿不到的 token 不得被跳過」這條紀律全程沒掉。
    （實測：`skip_tbd` 突變在 TBD 全補齊的世界裡仍被它抓到 28 條紅。）
    """
    pairs = [(m, _tbd_names(m)) for m in MODES if _tbd_names(m)]
    if not pairs:
        pytest.skip("目前沒有任何模式帶 TBD token —— 本守衛暫時沒有施力點（⛔ 不是通過）")

    for mode, tbd in pairs:
        with _spy_get_token() as calls:
            with pytest.raises(tokens.TokenNotSpecifiedError):
                markup.page_css(mode)
        asked = {name for name, _mode in calls}
        assert asked & tbd, (
            f"page_css({mode!r}) 從頭到尾沒有問過 {sorted(tbd)} —— "
            "它是被跳過的，不是被擋下來的"
        )


def test_page_css_resolves_every_token_through_get_token():
    """🔴 總管拍板的實作約束 6：**每一個 token 都要走 `tokens.get_token(name, mode=mode)`**。

    ⛔ 不可 `for k, v in tokens.DARK.items()` 直接讀 dict ——
    直接讀 dict 的那條路**繞過了 `TBD` 檢查**，
    `light` 模式就會安安靜靜地把 `<TBD 客戶尚未指定>` 印進 CSS
    （或把那兩行漏掉），兩種都是 §1 禁止的造假。
    """
    with _spy_get_token() as calls:
        css = markup.page_css("dark")
    assert css, "page_css('dark') 回傳空字串"
    asked = {name for name, _mode in calls}
    missing = set(tokens.DARK) - asked
    assert not missing, (
        f"有 {len(missing)} 個 token 沒走 get_token：{sorted(missing)[:8]}…"
    )
    modes = {mode for _name, mode in calls}
    assert modes <= {"dark"}, f"page_css('dark') 竟然跟別的模式要值：{sorted(modes)}"


@pytest.mark.parametrize("poisoned", sorted(tokens.DARK))
def test_any_unavailable_token_kills_the_whole_sheet(poisoned):
    """🔴 **「炸在產生 CSS 之前」的可測形式**：任何一個 token 拿不到 → 整頁不出。

    逐一對每個 token 下毒（其餘照常），`page_css("dark")` 都必須 raise 且
    **不得回傳任何字串**。這條連同上一條把「產生一半」的路堵死：
      · 上一條保證**每個 token 都被問過**；
      · 本條保證**任何一個問不到就整張 sheet 不存在**。
    兩條合起來 ⇒ 不可能出現「少了一個 `--x` 宣告、但 `var(--x)` 還在」的半套 CSS。
    """
    produced = []
    with _poison_token(poisoned):
        with pytest.raises(tokens.TokenNotSpecifiedError):
            produced.append(markup.page_css("dark"))
    assert not produced, f"{poisoned} 拿不到，page_css 卻還是吐出了 CSS"


@pytest.mark.parametrize("mode", MODES)
def test_page_css_never_references_a_var_it_did_not_declare(mode):
    """🔴 **參照完整性**：CSS 裡 `var(--x)` 用到的每個自訂屬性，都必須有人宣告過。

    這就是「跳過 TBD」那個 bug 的直接量測面 ——
    少一個宣告、留著一個 `var()`，畫面不會報錯，只會悄悄換一個顏色。
    """
    if _tbd_names(mode):
        pytest.skip(f"{mode} 還有 TBD token，整張 sheet 依 §1 不該產出（由上面那條守）")
    _check_var_referential_integrity(markup.page_css(mode))


@pytest.mark.parametrize("state", BLANK_VALUE_STATES)
def test_grey_and_red_states_leave_the_value_blank(state):
    """灰態／紅態的大字區**一律留白** —— ⛔ 無 `0`、⛔ 無上一輪殘值。

    `UI_PAGE_TODAY.md ④ 反例自檢` ＋ `CLAUDE.md §1`。
    oracle 是 `page_today.card_value_text`（⛔ 不另立第二把尺）。
    """
    # oracle：先確認它真的是留白態，本條才有意義（⛔ 不盲抄清單）
    assert page_today.card_value_text(state=state, value=SENTINEL_VALUE) is None, (
        f"{state!r} 並不是留白態 —— 本條的前提不成立，清單要重對"
    )
    html = _card(state=state, block="today.summary",
                 value=SENTINEL_VALUE, level=SENTINEL_LEVEL)
    assert SENTINEL_VALUE not in html, f"{state}：上一輪殘值被印出來了"
    text = _text_of(html)
    assert not re.search(r"(?<![\w.])0(?![\w.])", text), (
        f"{state}：大字區出現了孤零零的 `0` —— 缺值⛔不得顯示為 0。渲染文字：{text!r}"
    )


def test_degraded_shows_the_observation_but_withholds_the_verdict():
    """`degraded` ＝ 門檻已失準：**觀測照出、判決留白**，兩件事同時成立。

    ⛔ 不因為門檻失效就把值藏起來（`UI_PAGE_TODAY.md ④ 反例自檢` B 段），
    也⛔ 不照失效的門檻判燈 —— 後者是拿一把壞掉的尺量完還宣布結論。
    """
    assert page_today.card_value_text(state="degraded", value=SENTINEL_VALUE) == SENTINEL_VALUE
    assert page_today.card_level_text(state="degraded", level=SENTINEL_LEVEL) is None

    html = _card(state="degraded", block="today.summary",
                 value=SENTINEL_VALUE, level=SENTINEL_LEVEL)
    assert SENTINEL_VALUE in html, "degraded 應該照出觀測值，不該連值一起藏掉"
    assert SENTINEL_LEVEL not in html, "degraded ⛔ 不得用失效門檻判出等級"


def test_live_shows_both_the_observation_and_the_verdict():
    """🔴 **反證**：`live` 時值與判決都要畫得出來。

    沒有這一條，上面兩組留白測試可以被「`card_html` 根本不渲染 value / level」
    整組騙過去 —— 那會全綠，而畫面上什麼數字都沒有。
    """
    assert page_today.card_value_text(state="live", value=SENTINEL_VALUE) == SENTINEL_VALUE
    assert page_today.card_level_text(state="live", level=SENTINEL_LEVEL) == SENTINEL_LEVEL

    html = _card(state="live", block="today.summary",
                 value=SENTINEL_VALUE, level=SENTINEL_LEVEL)
    assert SENTINEL_VALUE in html, "live 態的觀測值沒有被渲染出來"
    assert SENTINEL_LEVEL in html, "live 態的判決沒有被渲染出來"


# ══════════════════════════════════════════════════════════════════
# 突變守衛（v3 §03-1「突變測試：拔掉修復邏輯必須轉為紅燈」）
#
# 🔴 **這一節守的是守衛本身。** 上面那些 `assert` 只證明「真實輸出通過了檢查」，
#    **不證明那個檢查真的抓得到東西** —— 一條 `assert True` 也會全綠。
#    做法：拿**真實實作的輸出**做定點破壞，再要求對應的檢查器當場 `AssertionError`。
#
# ⚠️ **它證明什麼、不證明什麼**（誠實揭露）：
#    證明「檢查器對這一種破壞有鑑別力」，而且因為破壞的是**真輸出**，
#    也連帶證明「真輸出裡真的有那個可被破壞的結構」（突變若沒改到東西就當場紅）。
#    ⛔ **不證明**檢查器抓得到**所有**寫錯的方式 —— 突變測試只能否證，不能窮舉。
#
# 📌 這三條是本組在 scratchpad 跑過的 9 組突變裡，**搬得進 repo 的那幾組**。
#    另外幾組（`unclosed` / `zero` / `novalue` / `inline_colour` / `nobadge` / `bad_bp`）
#    需要**替換整支實作**才做得出來，搬進來就得在 repo 裡長期養一份假 `markup`
#    ——那會變成第二個真相源（`CLAUDE.md §2.1`），且有 import 汙染風險，故**不搬**。
#    理由與取捨已寫進交付報告。
# ══════════════════════════════════════════════════════════════════
def test_mutation_dropping_a_root_declaration_turns_the_var_guard_red():
    """突變：從 `:root` 拿掉一個**有被 `var()` 引用**的宣告 → 參照完整性必須轉紅。

    這正是「把 TBD 的那幾個跳過不輸出」留下的痕跡
    （`:root` 少一行、`var()` 還在），也是本輪最想擋住的那個失效模式。
    """
    css = markup.page_css("dark")
    flat = _strip_style_tags(_CSS_COMMENT_RE.sub("", css))
    referenced = set(re.findall(r"var\(\s*(--[\w-]+)", flat))
    assert referenced, "真實 CSS 一個 `var()` 都沒用 —— 沒有東西可以突變"

    victim = sorted(referenced)[0]
    mutated, n = re.subn(rf"{re.escape(victim)}\s*:[^;}}]*;?", "", flat, count=1)
    assert n == 1 and mutated != flat, f"突變沒有生效（{victim} 的宣告沒被拿掉）"

    with pytest.raises(AssertionError):
        _check_var_referential_integrity(mutated)


@pytest.mark.parametrize("n", ON_PAGE_BADGES[:1])
def test_mutation_renaming_a_badge_class_into_the_size_namespace_turns_that_guard_red(n):
    """突變：把 `bdg-{n}` 改名成 `b{n}`（撞進尺寸命名空間）→ 命名空間守衛必須轉紅。

    ⚠️ 只取第一顆徽章跑：這條驗的是**檢查器的鑑別力**，
       逐顆跑 9 次不會多證明任何事（每顆的真實斷言由上面那條參數化測試負責）。
    """
    html = markup.badge_html(n)
    _check_badge_number_namespace(n, html)   # 先確認真輸出是乾淨的

    size_keys = sorted(components.SBADGE_SIZES)
    mutated = re.sub(rf"(?<![\w-])bdg-{n}(?![\w-])", size_keys[0], html)
    assert mutated != html, f"突變沒有生效（找不到 bdg-{n}）"

    with pytest.raises(AssertionError):
        _check_badge_number_namespace(n, mutated)


def test_mutation_adding_unused_responsive_grid_classes_turns_that_guard_red():
    """突變：塞進幾個沒人用的 RWD 網格 class → 「27 種組合」守衛必須轉紅。

    對應 scratchpad 的 `combo27`：先把 3×3×3 種欄數組合都產一遍，
    再只用其中兩種。死 CSS 不會報錯、不會變紅。
    """
    css = markup.page_css("dark")
    minted = _minted_grid_classes(css)
    _check_no_orphan_responsive_grid_classes(css, minted)   # 先確認真輸出是乾淨的

    bp = components.BREAKPOINTS
    junk = "".join(
        f"@media (max-width:{bp['mobile_max_px']}px)"
        f"{{.wrt-junk-{i}{{grid-template-columns:repeat({i},1fr);}}}}"
        for i in range(1, components.MAX_COLS + 1)
    )
    mutated = _strip_style_tags(css) + junk
    assert mutated != css, "突變沒有生效"

    with pytest.raises(AssertionError):
        _check_no_orphan_responsive_grid_classes(mutated, minted)


# ══════════════════════════════════════════════════════════════════
# C-1c 大字區（卡內主數值 ＝ KPI）—— WRI2 補洞組 2026-09-21 **新增**
#
# 🔴 **這一節在補一個「文件宣稱 ✅、畫面沒做到」的洞。**
#    補之前：`.blk-val` 完全沒設 `font-size` ⇒ 承襲卡面字級 ⇒ 觀測值**跟卡標一樣大**。
#    而 `docs/v2/spec/UI_PRINCIPLES.md` 第 6 條「KPI ≥ 20px，明細 ≤ 13px」判 ✅，
#    靠的就是這個值 —— 它當時只活在規格文件裡，CSS 裡一個字都沒有。
#
# ⛔ **不寫死任何字級數字**（沿用本檔既有紀律）：值一律讀 `components.CARD_VALUE`。
#    **唯一**寫死的數字是門檻 `20` —— 它是 `UI_PRINCIPLES.md` 第 6 條的**門檻本身**
#    （「KPI ≥ 20px」），不是被測的值；契約值改成 22 或 28 本節都該綠，改成 16 才該紅。
# ══════════════════════════════════════════════════════════════════
#: `UI_PRINCIPLES.md` 第 6 條逐字：「KPI ≥ 20px，明細 ≤ 13px」。
#: ⚠️ 這是**原則的門檻**，⛔ 不是 KPI 的字級 —— KPI 字級在 `components.CARD_VALUE`。
KPI_MIN_PX_PER_PRINCIPLE_6 = 20.0

_VALUE_HOST_RE = re.compile(
    r'<[A-Za-z][^>]*\bclass="([^"]*)"[^>]*>\s*' + re.escape(SENTINEL_VALUE)
)


def _value_classes() -> set[str]:
    """大字區那個元素自己的 class —— **從真輸出反推**，⛔ 不手抄 `.blk-val`。

    手抄 class 名的後果：實作把 class 改名之後，本節會安安靜靜地量不到任何規則，
    然後因為「沒量到」而不是「量錯」全部綠燈 —— 那正是這個洞第一次發生的方式。
    """
    html = _card(ALL_BLOCKS[0], "live", value=SENTINEL_VALUE, level="中性")
    m = _VALUE_HOST_RE.search(html)
    assert m, (
        f"找不到裝大字（{SENTINEL_VALUE}）的元素；"
        f"`card_html` 是不是沒把觀測值畫出來？HTML={html[:200]!r}"
    )
    classes = {c for c in m.group(1).split() if c}
    assert classes, "大字區元素沒有任何 class —— CSS 掛不上去"
    return classes


def _decl_values_under(css: str, classes: set[str], prop: str) -> set[str]:
    """基準規則（非 `@media`）裡，`.classes` 對 `prop` 宣告的**原始字串**值。

    與 `_px_values_under` 的差別：本函式不解析成 px 數，因為 `font-family` /
    `font-variant-numeric` 這類通道根本不是數字。
    """
    out: set[str] = set()
    for media, sel, body in _iter_rules(css):
        if media is not None or not any(_selector_targets(sel, c) for c in classes):
            continue
        for decl in body.split(";"):
            name, sep, value = decl.partition(":")
            if sep and name.strip().lower() == prop:
                out.add(value.strip())
    return out


def test_the_big_value_declares_the_font_size_from_the_contract():
    """⭐ 洞 1 的正面守衛：大字區的 `font-size` ＝ `components.CARD_VALUE['font_px']`。

    ⛔ 「有宣告就好」不夠 —— 要**等於契約值**。契約值的出處是
    `UI_COMPONENTS.md §4`「主數值欄一欄 → 卡內 `24px/700` `--mono` tabular-nums」，
    由 `UI_PRINCIPLES.md` 第 6 條明文指定為 KPI 的字級來源（§B 無 KPI 專屬字級列）。
    """
    css = markup.page_css("dark")
    want = float(components.CARD_VALUE["font_px"])
    got = _px_values_under(css, _value_classes(), ("font-size",))
    assert got, (
        "大字區在 CSS 裡**沒有** `font-size` 宣告 —— 它會承襲卡面字級，"
        "畫面上跟卡標一樣大，而 `UI_PRINCIPLES.md` 第 6 條「KPI ≥ 20px」靠的就是這個值"
    )
    assert got == {want}, f"大字區字級應為 {want}px（契約值），CSS 量到 {sorted(got)}"


def test_the_big_value_meets_the_kpi_floor_in_principle_6():
    """⭐ 釘住 `UI_PRINCIPLES.md` 第 6 條的門檻：KPI **≥ 20px**。

    上一條守「等於契約」，本條守「**契約本身沒有掉到門檻以下**」——
    兩條不互相取代：有人把 `CARD_VALUE['font_px']` 改成 `13.0`，上一條仍然全綠
    （CSS 確實等於契約），只有本條會紅。
    """
    css = markup.page_css("dark")
    want = float(components.CARD_VALUE["font_px"])
    assert want >= KPI_MIN_PX_PER_PRINCIPLE_6, (
        f"契約層的 KPI 字級 {want}px 低於 `UI_PRINCIPLES.md` 第 6 條的門檻 "
        f"{KPI_MIN_PX_PER_PRINCIPLE_6}px —— 該條的 ✅ 判定會就此不成立"
    )
    got = _px_values_under(css, _value_classes(), ("font-size",))
    assert got and min(got) >= KPI_MIN_PX_PER_PRINCIPLE_6, (
        f"CSS 裡大字區量到 {sorted(got)}，未達第 6 條門檻 {KPI_MIN_PX_PER_PRINCIPLE_6}px"
    )


def test_the_big_value_declares_the_font_weight_from_the_contract():
    """大字區字重 ＝ `CARD_VALUE['font_weight']`（§4 逐字 `24px/700` 的 700）。"""
    css = markup.page_css("dark")
    want = str(components.CARD_VALUE["font_weight"])
    got = _decl_values_under(css, _value_classes(), "font-weight")
    assert got == {want}, f"大字區字重應為 {want}，CSS 量到 {sorted(got)}"


def test_the_big_value_runs_on_the_mono_font_token():
    """⭐ 大字區字族走 `var(--mono)`，而且 `--mono` **真的宣告過**。

    🔴 **兩件事要一起守，⛔ 不能只守一半**：
      · 只檢查 `font-family` 有 `var(--mono)` → `--mono` 沒宣告時照樣綠，
        但 CSS 規範下 `var()` 指向未宣告的自訂屬性是 *invalid at computed-value time*
        ⇒ 退回繼承值 ⇒ 大字用的是繼承來的**比例字體**，
        同一條規則裡的 `tabular-nums` 形同虛設，而畫面**看起來完全正常**。
      · 只檢查 `:root` 有 `--mono` → 沒人用它也綠（死 token）。
    ⚠️ token 名一律讀 `CARD_VALUE['font_family']`，⛔ 不寫死 `--mono` 字串。
    """
    css = markup.page_css("dark")
    token = str(components.CARD_VALUE["font_family"])
    assert token.startswith("--"), (
        f"`CARD_VALUE['font_family']` 應存 token 名（`--` 開頭），收到 {token!r} —— "
        "存實值會在 tokens 層之外開出第二個真相源（CLAUDE.md §2.1）"
    )

    got = _decl_values_under(css, _value_classes(), "font-family")
    assert got, "大字區沒有 `font-family` 宣告 —— 等寬與 tabular-nums 是一組的，缺一不可"
    assert all(f"var({token})" in v.replace(" ", "") for v in got), (
        f"大字區的 font-family 應引用 `var({token})`，CSS 量到 {sorted(got)}"
    )

    flat = _CSS_COMMENT_RE.sub("", _strip_style_tags(css))
    assert re.search(re.escape(token) + r"\s*:", flat), (
        f"`{token}` 被 `var()` 引用了卻**沒有在 CSS 裡宣告** —— "
        "CSS 會退回繼承字體，畫出一個看起來正常、實際上不是等寬的大字"
    )


def test_the_big_value_keeps_tabular_numerals():
    """大字區保留 `font-variant-numeric`（§4 逐字「tabular-nums」）。

    ⚠️ 這條在補洞**之前就已經是對的**（舊實作唯一有的那一行就是它）——
    寫下來是為了擋住「加字級時順手把它改掉／蓋掉」：數字不等寬，
    大字每次 rerun 都會左右跳動。
    """
    css = markup.page_css("dark")
    want = str(components.CARD_VALUE["font_variant_numeric"])
    got = _decl_values_under(css, _value_classes(), "font-variant-numeric")
    assert got == {want}, f"大字區的 font-variant-numeric 應為 {want!r}，量到 {sorted(got)}"


def test_the_big_value_is_actually_bigger_than_every_card_title():
    """⭐ 「大字區」這個名字要對得上畫面：它必須**大於每一階的卡標**。

    🔴 這是洞 1 的**症狀**測試，與上面的「等於契約值」不同角度：
    補洞前 `.blk-val` 沒有 `font-size` ⇒ 承襲卡面字級 ⇒ 大字與卡標**一樣大**，
    「每頁只有一個視覺焦點」（`UI_PRINCIPLES.md` 第 1 條）在畫面上直接不成立。
    ⚠️ 兩邊的值都動態讀（`CARD_VALUE` vs `CARD_TIERS[*]['title_px']`），⛔ 不寫死 24／17.5。
    """
    kpi = float(components.CARD_VALUE["font_px"])
    titles = {t: float(components.CARD_TIERS[t]["title_px"]) for t in TIER_ORDER}
    biggest = max(titles.values())
    assert kpi > biggest, (
        f"大字區 {kpi}px 並沒有比最大的卡標大（卡標 {titles}）—— "
        "「大字區」這個名字在畫面上不成立，視覺焦點被壓平"
    )


def test_mutation_dropping_the_big_value_font_size_turns_the_kpi_guard_red():
    """突變：把大字區的 `font-size` 整條拿掉 → 本節必須轉紅（v3 §03-1 突變測試）。

    ⚠️ 這條驗的是**守衛本身有沒有牙齒**。洞 1 的原始狀態就是「那一行不存在」，
    如果拿掉它測試照樣綠，本節等於白寫。
    """
    css = markup.page_css("dark")
    classes = _value_classes()
    want = float(components.CARD_VALUE["font_px"])
    assert _px_values_under(css, classes, ("font-size",)) == {want}, "真輸出先要是乾淨的"

    mutated = re.sub(r"font-size\s*:\s*" + f"{want:g}" + r"px\s*;", "", _strip_style_tags(css))
    assert mutated != css, "突變沒有生效（找不到大字區的 font-size）"
    assert not _px_values_under(mutated, classes, ("font-size",)), (
        "突變後大字區竟然還量得到 font-size —— 本節的定位方式有問題"
    )
