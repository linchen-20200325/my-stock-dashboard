"""WT 測試組｜test-first 契約 C：「🚦 今天」頁（`src/ui_v2/page_today.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/` 尚不存在，
   本檔因此**應該是紅燈（ModuleNotFoundError）** —— 紅燈即正確結果。
   實作組的任務＝把下面這份 API 做出來、讓它轉綠，⛔ 不是改本檔讓它變綠。

唯一資料來源：`docs/v2/spec/UI_PAGE_TODAY.md`（＋ 它引用的第 1、2 份）。
每條 assert 旁標 `# UI_PAGE_TODAY.md <章節名>`（⛔ 不寫行號 —— CLAUDE.md §8.2.A.0 規則 1）。
⛔ 未引用 `src/ui/` 既有檔案（含 `views/page_today.py`）、⛔ 未引用舊原型。
⛔ 不 import streamlit —— 這一層測的是**結構與狀態契約**，不是 `st.*` 渲染。

════════════════════════════════════════════════════════════════════
本輪三個模組的 API 契約總覽（實作組請照這份做）
════════════════════════════════════════════════════════════════════
  src/ui_v2/tokens.py      → 見 tests/ui_v2/test_tokens.py 檔頭
  src/ui_v2/components.py  → 見 tests/ui_v2/test_components.py 檔頭
  src/ui_v2/page_today.py  → 本檔頭（以下）

────────────────────────────────────────────────────────────────────
實作組必須提供：`src/ui_v2/page_today.py`
────────────────────────────────────────────────────────────────────
`LAYERS : tuple[Mapping, ...]`
    由上而下的版面層。每層欄位：
      `layer`        : int          # 0＝葉外 chrome（據實列出、⛔ 不計入四層）；1..4＝四層
      `wireframe_n`  : str          # "n0".."n3"
      `blocks`       : tuple[str, ...]   # ⛔ 必須是**純字串**，不得是可夾帶 tier 的 dict
      `tier`         : str          # "t1".."t4"，必須等於 components.tier_for_layer(layer)
      `badge_size`   : str          # "b1".."b4"
      `title_px`     : float
      `has_main_cta` : bool         # 全頁恰有一層為 True
      `allows_interaction` : bool   # 第二層為 False（⛔ 不得放按鈕／連結／popover）

`BLOCK_COLS : Mapping[str, tuple[int, int, int]]`
    **block 內部**一列幾格，記法 `(桌機, 平板, 手機)`；多的**換行排下一列，不是加欄**
    （`src/ui/views/_ui_kit.py::grid()` 逐字 `_n = min(cols, MAX_COLS)` 夾上限，
    再以 `_n` 為步進逐塊 `st.columns(len(_chunk))` ⇒ 開新的一列、不是更多欄）。
    ⚠️ ~~`today.holdings` 是新訂 block、線框 `n2` **未定義**其 cols~~
    ~~⇒ **⛔ 不得自行發明一組塞進來**（規格的洞，見本檔 test 與交付報告）。~~
    **2026-09-21 更新（有意識的政策變更，⛔ 不是漏刪；決策者 AI 總管）**：
    規格洞已補 —— `today.holdings` ＝ `(1, 1, 1)`，但它是**總管推導值、⛔ 不是線框值**，
    故**必須**同時登記在 `COLS_PROVENANCE`／`DERIVED_COLS`／`COLS_DERIVATION`。
    「線框沒定義就不准填」仍然成立於**沒有來歷**的情形。
    🔵 **2026-09-22 更新（有意識的政策變更，⛔ 不是漏刪；決策者：客戶，裁示 B）**：
    `today.summary` ＝ `(1, 1, 1)`（原線框值 3/2/1 被客戶**覆寫**）——
    客戶逐字「把 today.summary 從「卡內三欄」改成「三張獨立卡」」。
    它是**客戶裁示值、⛔ 不是線框值**，同樣必須登記三處。
    ⚠️ **這與 holdings 那筆不是同一件事**：holdings 是**填線框沒寫的洞**，
    summary 是**推翻線框寫過的值** —— 後者**只有客戶做得到**
    （CLAUDE.md §-1.5.D §03-2 ①：版面異動必須客戶拍板）。

`COLS_PROVENANCE : Mapping[str, str]`   # 每個 `BLOCK_COLS` key → 來歷
                                        # （~~兩~~ **三**個字面常數之一，2026-09-22 起）
`COLS_FROM_WIREFRAME / COLS_DERIVED_BY_LEAD / COLS_RULED_BY_CLIENT : str`
    🔵 **第三種（`COLS_RULED_BY_CLIENT`）2026-09-22 新增**：線框**有**定義此 block 的
    `cols`，但客戶**明示裁示覆寫**。⚠️ 與 `COLS_DERIVED_BY_LEAD` 的關鍵差異 ——
    推導＝**填線框沒寫的洞**（`wireframe_defines_cols=False`／`wireframe_value=None`）；
    裁示＝**推翻線框寫過的值**（`wireframe_defines_cols=True`／`wireframe_value` 是舊值）。
`DERIVED_COLS : frozenset[str]`         # 來歷不是線框的 block（推導填洞／客戶裁示覆寫），
                                        # ⛔ 不得漏登
`COLS_DERIVATION : Mapping[str, Mapping]`  # `basis`(tuple) / `decided_by` / `decided_on`
                                           # / `is_wireframe_value` / `wireframe_defines_cols`
                                           # / 🆕 `wireframe_value`（被覆寫掉的線框值；
                                           #      填洞那筆為 `None`）/ `spec_section`
                                           # ⚠️ 兩筆**鍵集合必須一致**，⛔ 不得一筆有一筆沒有
`cols_scope(block_key) -> str`          # 一律 "inside_block"（⛔ 不是層網格）

`LAYER_GRID_COLS : Mapping[int, tuple[int, int, int]]`
    **同一層的幾個 block 彼此怎麼並排**（⛔ 與 `BLOCK_COLS` 是兩個不同的網格）。
    只登記第二層 ＝ `(3, 2, 1)`（客戶 2026-09-16「3 張並排卡」＋ 原型 `.g3` 實測）。
    🔵 **2026-09-22 裁示 B 之下本值⛔ 不變**：客戶逐字「layer_html 的 3 欄不變，
    block 內部不再巢狀網格」—— 改的是 `BLOCK_COLS["today.summary"]`（block 內部），
    ⛔ 不是本常數（層級網格）。**兩個網格仍是兩件事。**
`blocks_per_row(layer, viewport_px) -> int`
`rows_of_layer(layer, viewport_px) -> int`

`BLOCK_BADGES : Mapping[str, tuple[int, ...]]`
    各 block 依線框 `states` 會用到的徽章號（UI_PAGE_TODAY.md ①「第一層 `today.verdict`」段
    ／「第二層」today.summary 條／「第四層」段）。

`WITHDRAWN_BLOCKS : frozenset[str]`
    **已撤回、不是待補**的 block
    （UI_PAGE_TODAY.md ③「線框有、實作無」表 `chrome.asof` 列）。
    ⛔ 不得從 `LAYERS` 悄悄消失而不留紀錄。

`OPEN_ITEMS : frozenset[str]`
    **客戶未裁、去向開放**的卡（UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段
    「兩卡最終去向＝開放項」：`verdict.exposure`／`verdict.regime`）。
    ⛔ 不得自行判定刪除、⛔ 不得自行安排到第二層其他 block —— 但也⛔ 不得默默消失。

`SUMMARY_COLUMNS : tuple[Mapping, ...]`
    第二層 `today.summary` 三欄（位階／動能／風險），每欄：
      `name` / `source`(str|None) / `wired`(bool) / `badge`(int|None)
    🔵 **2026-09-22 裁示 B 只改「怎麼排」，⛔ 沒有改「有哪幾個」**：三個仍在、名字仍是
    線框逐字的位階／動能／風險；變的是它們從**一張卡內的三欄**變成**三張獨立卡**
    （`BLOCK_COLS["today.summary"]` 3/2/1 → 1/1/1）。
    ⚠️ 線框 `name` 字串「③ 三欄摘要（位階／動能／風險）」是**客戶審過的逐字**，⛔ 不動。

`BADGES_ON_PAGE / BADGES_NOT_ON_PAGE : frozenset[int]`

`MAIN_CTA : Mapping`  `label` / `button` / ~~`unique_per_site`~~ **`unique_per_first_screen`**(True)
    🔵 **2026-09-22 鍵名改（有意識的政策變更，⛔ 不是漏刪；決策者：客戶）**：
    客戶裁示逐字「**不是「全站唯一」，是「每頁首屏唯一」。**」
    **舊名的理由仍然成立**：只有「🚦 今天」一頁時兩者**外延相同**，寫哪個都對；
    **被權衡掉的原因**：五頁 IA 落地後 🔎 選股頁有自己的主 CTA `🎯 開始選股`
    ⇒「全站唯一」是**假的**，而**鍵名本身在說謊** ——
    留著它，下一個讀 code 的人會以為契約保證全站只有一顆。
`MAIN_CTA_RETRY_NOTE : str`
`MAIN_CTA_CONTRACT_DRIFT_NOTE : str`
`G3_COLS : tuple[int, int, int]`  ＝ (3, 2, 1)
    🔵 **2026-09-22 起 `today.summary` ⛔ 不再等於它**（裁示 B）；
    本常數**沒有退役** —— `today.detail` 的 block cols 與第二層 `LAYER_GRID_COLS[2]`
    仍是這個線框值。

`HOLDINGS_DISPLAY_FIELDS : tuple[str, ...]`
    **白名單（准許清單），⛔ 不是必填清單** —— UI_PAGE_TODAY.md ①「第二層」today.holdings 條
    「**可顯示**（皆由檔數推得）」那行的九項是「**可顯示**」，該行只有後半
    「＋ 等權假設揭露句一行」標了**必填**。渲染端**可以只畫子集**。
`unknown_holdings_fields(fields) -> tuple[str, ...]`  # 回傳白名單外的欄位（空 tuple ＝ 全合法）
`HOLDINGS_BASIS : str`  ＝ "equal_weight"
`HOLDINGS_TOP1_LABEL : str`
`HOLDINGS_EQUAL_WEIGHT_DISCLOSURE : Mapping`  `text`(非空) / `color`("--ink-3") / `font_px`(11.5)

`tier_for_block(block_key: str) -> str`
    ⛔ 只吃 block key，不得有 tier 覆寫參數（四層由層序自動掛）。
`blocks_of_layer(layer: int) -> tuple[str, ...]`
`resolve_badge(*, state, miss_reason=None, numerator=None, denominator=None) -> int`
`card_value_text(*, state, value) -> str | None`      # 觀測值；灰態／紅態一律 None（留白）
`card_level_text(*, state, level) -> str | None`      # 判決；degraded 一律 None（判決留白）
`observation_miss_reason(value, miss_reason) -> str | None`
    非法二元組 `(None, None)` 與 `(值, MISS_*)` → 回 `"MISS_CONTRACT_DRIFT"`。
`main_cta_state(*, failure_reason=None) -> Mapping`   # `enabled` / `note`
`holdings_badge(*, n_classified: int) -> int`
"""
from __future__ import annotations

import inspect

import pytest

from src.ui_v2 import components, page_today


def _layer(n: int):
    return next(layer for layer in page_today.LAYERS if layer["layer"] == n)


# ══════════════════════════════════════════════════════════════════
# C-1 四層結構（UI_PAGE_TODAY.md ① 四層結構）
# ══════════════════════════════════════════════════════════════════
def test_page_has_exactly_four_layers_plus_an_uncounted_chrome():
    """UI_PAGE_TODAY.md ① 四層結構起手句「線框 `n0` 為葉外 chrome（五頁共用，不屬任何葉）
    → **據實列出，不計入四層**」。"""
    numbered = [layer["layer"] for layer in page_today.LAYERS]
    assert sorted(n for n in numbered if n != 0) == [1, 2, 3, 4]
    assert numbered.count(0) == 1, "葉外 chrome 要據實列出（但不計入四層）"


def test_first_layer_is_one_verdict_light_not_three_cards():
    """UI_PAGE_TODAY.md ①「第一層 `today.verdict`」段「第一層＝**單一結論燈** ＋ 一句話結論…
    ⛔ 第一層**不再是 3 張並排卡**」（user 2026-09-16 裁示）。"""
    assert page_today.blocks_of_layer(1) == ("today.verdict",)
    assert len(page_today.blocks_of_layer(1)) == 1
    assert _layer(1)["tier"] == "t1"            # ① 四層結構表「第一層 結論燈」列
    assert _layer(1)["badge_size"] == "b1"      # ① 四層結構表「第一層 結論燈」列
    # ①「第一層 `today.verdict`」段：線框 `cols 1/1/1`，一格滿版
    assert page_today.BLOCK_COLS["today.verdict"] == (1, 1, 1)


def test_second_layer_is_exactly_three_side_by_side_cards():
    """UI_PAGE_TODAY.md ①「第二層」段「第二層＝下列 3 張並排卡 —— `today.summary`／
    `today.key_banner`／🆕`today.holdings`」。"""
    assert page_today.blocks_of_layer(2) == (
        "today.summary", "today.key_banner", "today.holdings",
    )
    assert _layer(2)["tier"] == "t2"        # ① 四層結構表「第二層 核心卡」列
    assert _layer(2)["badge_size"] == "b2"  # ① 四層結構表「第二層 核心卡」列


def test_third_layer_is_the_action_row():
    # ① 四層結構表「第三層 操作列」列
    assert page_today.blocks_of_layer(3) == ("today.actions",)
    assert _layer(3)["tier"] == "t3"
    # ①「第三層 `today.actions`」段：線框 `cols 1/1/1`
    assert page_today.BLOCK_COLS["today.actions"] == (1, 1, 1)


def test_fourth_layer_is_the_evidence_drawer():
    # ① 四層結構表「第四層 展開佐證」列 ＋ ①「第四層」段
    assert page_today.blocks_of_layer(4) == ("today.warroom", "today.detail")
    assert _layer(4)["tier"] == "t4"        # t4 ＝ 1px **dashed**
    assert _layer(4)["badge_size"] == "b4"
    assert components.CARD_TIERS[_layer(4)["tier"]]["border_style"] == "dashed"


def test_chrome_layer_carries_the_status_bar():
    # UI_PAGE_TODAY.md ①「葉外 chrome」段：
    #「葉外 chrome（`cols 1/1/1` 三斷點皆滿版）：`today.statusbar` ＝ 3 張狀態卡」
    assert page_today.blocks_of_layer(0) == ("today.statusbar",)
    assert _layer(0)["tier"] == "t3"        # ① 四層結構表「葉外」列
    assert page_today.BLOCK_COLS["today.statusbar"] == (1, 1, 1)


def test_chrome_asof_is_withdrawn_not_pending():
    """UI_PAGE_TODAY.md ③「線框有、實作無」表 `chrome.asof` 列「**已撤回，不是待補**」
    （`get_macro_state()` 只有 9 key、無 `as_of`）。

    ⇒ 不得出現在版面，但要**留下紀錄**，⛔ 不是默默消失（§-2 規則 6 的同一紀律）。
    """
    all_blocks = {b for layer in page_today.LAYERS for b in layer["blocks"]}
    assert "chrome.asof" not in all_blocks
    assert "chrome.asof" in page_today.WITHDRAWN_BLOCKS


def test_holdings_cols_is_filled_but_must_declare_a_non_wireframe_provenance():
    """⚠️ **2026-09-21 有意識的政策變更，⛔ 不是漏刪。決策者＝ AI 總管。**

    ~~舊守衛：`assert "today.holdings" not in page_today.BLOCK_COLS`~~
    ~~理由：UI_PAGE_TODAY.md ①「第二層」today.holdings 條「線框 `n2` **未定義**此 block」~~
    ~~⇒ 它沒有線框 `cols`，~~
    ~~⛔ 不得隨手發明一組欄數（§1 反捏造）。~~

    **舊理由仍然成立、不是寫錯**：在有人真的把來歷寫出來之前，填一組值就是捏造，
    而「不准有值」是當時唯一驗得到的形式。

    **新規則為何勝出**：規格洞**已由總管補上** —— `(1, 1, 1)`，來歷是
    「§① 排列段的 `cols` 語意 ＋ 原型形狀佐證」，且**已寫明⛔ 不是線框值**
    （UI_PAGE_TODAY.md §① 「🆕 `today.holdings` 的 `cols`」段）。
    ⇒ 守衛從「**不准有值**」改成「**有值，但必須標明它的來歷不是線框**」。
    反捏造的實質（⛔ 不得把推導值**偽裝成**線框值）**一條未減**，換的只是可驗的形式：
    ⛔ 靠註解不算 —— 來歷必須是**機器讀得到**的結構（`COLS_PROVENANCE`／`DERIVED_COLS`）。
    """
    assert page_today.BLOCK_COLS["today.holdings"] == (1, 1, 1)
    # 🔴 本條的核心：它⛔ 不得被登記成線框值
    assert "today.holdings" in page_today.DERIVED_COLS
    assert page_today.COLS_PROVENANCE["today.holdings"] == page_today.COLS_DERIVED_BY_LEAD
    assert page_today.COLS_PROVENANCE["today.holdings"] != page_today.COLS_FROM_WIREFRAME


def test_the_three_provenance_literals_are_distinct_and_exhaustive():
    """🔵 **2026-09-22 新增（客戶裁示 B 生出第三種來歷）**：三個來歷字面值
    **互不相等**，且 `COLS_PROVENANCE` 只會用這三個之一。

    為什麼要釘「互不相等」：三者是**靠字串比對**在分辨的
    （`DERIVED_COLS` ＝ `src != COLS_FROM_WIREFRAME`）。只要有人把其中兩個寫成同一個
    字串，分類就會**靜默失效** —— 客戶裁示值會被當成線框值、或反之，
    而**沒有任何測試會紅**（這正是 `CLAUDE.md §-2` 規則 6 那個死碼實證的同一族失效）。
    """
    literals = (page_today.COLS_FROM_WIREFRAME,
                page_today.COLS_DERIVED_BY_LEAD,
                page_today.COLS_RULED_BY_CLIENT)
    assert len(set(literals)) == 3, f"來歷字面值撞名：{literals}"
    assert all(isinstance(x, str) and x.strip() for x in literals)
    assert set(page_today.COLS_PROVENANCE.values()) <= set(literals), (
        "出現了三種之外的來歷 —— 新增一種就必須同步 `COLS_DERIVATION` 與本檔守衛"
    )


def test_every_declared_cols_says_where_it_came_from():
    """⛔ 不得有「來歷不明」的 `cols`：`BLOCK_COLS` 的每一個 key 都要有一筆來歷登記，
    且 `DERIVED_COLS` **恰好**等於那些來歷不是線框的 block（⛔ 不得漏登、⛔ 不得多登）。"""
    assert set(page_today.COLS_PROVENANCE) == set(page_today.BLOCK_COLS)
    derived = {k for k, v in page_today.COLS_PROVENANCE.items()
               if v != page_today.COLS_FROM_WIREFRAME}
    assert page_today.DERIVED_COLS == frozenset(derived)
    # ⚠️ ~~線框值恰為原有七筆（…含 today.summary…），推導值恰為 `today.holdings` 一筆。~~
    #    ~~assert 集合含 "today.summary"；assert DERIVED_COLS == {"today.holdings"}~~
    # 🔵 **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶（裁示 B）。**
    # **舊斷言的理由仍然成立**：在裁示之前，`today.summary` 的值確實逐字來自線框。
    # **被權衡掉的是那個前提** —— 客戶已覆寫該值，再把它登記成線框值就是造假（§1）。
    # 現行：線框值**六筆**（UI_PAGE_TODAY.md ①「葉外 chrome」／「第一層 `today.verdict`」／
    # 「第二層」today.key_banner 條／「第三層 `today.actions`」／「第四層」各段），
    # 非線框值**兩筆**：`today.holdings`（總管推導填洞）＋ `today.summary`（客戶裁示覆寫）。
    assert set(page_today.BLOCK_COLS) - page_today.DERIVED_COLS == {
        "today.statusbar", "today.verdict",
        "today.key_banner", "today.actions", "today.warroom", "today.detail",
    }
    assert page_today.DERIVED_COLS == frozenset({"today.holdings", "today.summary"})


def test_derived_cols_carry_a_written_derivation_chain():
    """非線框值⛔ 不得只有一句「總管說的」／「客戶說的」：要寫得出**推導鏈或裁示逐字**，
    這樣下一個人才驗得到它是怎麼來的（§-2 規則 6：來歷要留得住）。

    ⚠️ **本條只驗兩種來歷的「共通部分」。** `decided_by`／`decided_on`／
    `wireframe_defines_cols`／`wireframe_value` 兩者**本來就不同**，
    ⛔ 不得用一個 loop 對兩種來歷套同一組斷言 —— 那會讓較寬鬆的那一組**掩護**另一組。
    逐來歷的斷言見下面兩條；逐 block 的明示值見
    `test_each_non_wireframe_block_is_pinned_to_its_own_provenance`。
    """
    keysets = []
    for block in page_today.DERIVED_COLS:
        note = page_today.COLS_DERIVATION[block]
        keysets.append(frozenset(note))
        assert note["is_wireframe_value"] is False
        # 登記的值必須就是實際在用的值 —— 兩邊漂開＝來歷指向一個沒人在用的數字
        assert note["value"] == page_today.BLOCK_COLS[block], (
            f"{block}：`COLS_DERIVATION` 登記 {note['value']}，"
            f"`BLOCK_COLS` 卻是 {page_today.BLOCK_COLS[block]}"
        )
        assert isinstance(note["basis"], tuple) and len(note["basis"]) >= 3
        assert all(isinstance(line, str) and line.strip() for line in note["basis"])
        assert isinstance(note["decided_on"], str) and note["decided_on"].strip()
        assert isinstance(note["spec_section"], str) and note["spec_section"].strip()
    # 鍵集合必須一致：鍵不齊的那一筆會**悄悄跳過**下面兩條的部分斷言（守衛看起來還是綠的）
    assert len(set(keysets)) == 1, f"兩筆的鍵集合不一致：{[sorted(k) for k in keysets]}"


def test_the_lead_may_only_fill_a_hole_never_override_the_wireframe():
    """⭐ **總管只能填洞、⛔ 不能覆寫線框** —— `CLAUDE.md §-1.5.D §03-2 ①` 的機器版。

    §03-2 ①：**任何版面佈局（Layout）、欄位增減或分頁動線異動，必須先出線框草稿
    送客戶拍板** ⇒ 改一個線框**已經寫過**的 `cols`＝版面異動＝**只有客戶能拍板**。
    總管能做的只有一件事：線框**沒寫**的地方，把洞補起來並寫明來歷。

    ⇒ 可觀測形式：來歷是 `COLS_DERIVED_BY_LEAD` 的那幾筆，
    `wireframe_defines_cols` 必為 `False`、`wireframe_value` 必為 `None`
    （線框沒寫 ⇒ **沒有**被覆寫掉的舊值這種東西）。
    ⛔ 若有人把總管的一筆寫成 `wireframe_defines_cols=True`，那就是總管在覆寫線框。
    """
    checked = 0
    for block, src in page_today.COLS_PROVENANCE.items():
        if src != page_today.COLS_DERIVED_BY_LEAD:
            continue
        note = page_today.COLS_DERIVATION[block]
        assert note["decided_by"] == "AI 總管", f"{block}：推導值的決策者只能是 AI 總管"
        assert note["wireframe_defines_cols"] is False, (
            f"{block}：總管⛔ 不得覆寫線框已定義的 cols（§-1.5.D §03-2 ①，只有客戶能拍板）"
        )
        assert note["wireframe_value"] is None, (
            f"{block}：線框沒定義 ⇒ ⛔ 不得填一個「被覆寫掉的線框值」"
        )
        checked += 1
    assert checked, "一筆總管推導值都沒有 —— 本條這一輪沒有鑑別力，請重看"


def test_a_client_ruling_is_always_an_override_of_an_existing_wireframe_value():
    """⭐ **客戶裁示值＝對「線框已經寫過的值」的覆寫** —— 與上一條互為鏡像。

    這個方向也要釘死，否則 `COLS_RULED_BY_CLIENT` 會變成一個**萬用脫身門**：
    任何人想繞過「線框沒寫就不准填」，只要把來歷標成「客戶裁示」就通關了。
    ⇒ 釘住：客戶裁示必須**指得出它覆寫掉的那個線框值**（三元組），
    而且那個舊值**必須真的不同於**現行值 —— 相同就代表沒有覆寫任何東西，
    那筆根本不該叫裁示（它就是線框值）。
    """
    checked = 0
    for block, src in page_today.COLS_PROVENANCE.items():
        if src != page_today.COLS_RULED_BY_CLIENT:
            continue
        note = page_today.COLS_DERIVATION[block]
        assert note["decided_by"] == "客戶", f"{block}：裁示值的決策者只能是客戶"
        assert note["wireframe_defines_cols"] is True, (
            f"{block}：線框沒寫的地方⛔ 沒有東西可以「覆寫」——"
            "那是填洞（`COLS_DERIVED_BY_LEAD`），不是裁示"
        )
        wf = note["wireframe_value"]
        assert isinstance(wf, tuple) and len(wf) == 3 and all(isinstance(n, int) for n in wf), (
            f"{block}：`wireframe_value` 必須是被覆寫掉的那個線框三元組，收到 {wf!r}"
        )
        assert wf != note["value"], (
            f"{block}：`wireframe_value` 與現行值相同（{wf}）—— 那就沒有覆寫任何東西"
        )
        checked += 1
    assert checked, "一筆客戶裁示值都沒有 —— 本條這一輪沒有鑑別力，請重看"


def test_each_non_wireframe_block_is_pinned_to_its_own_provenance():
    """逐 block 明示（⛔ 不用 loop 套同一組斷言）—— 兩筆的來歷、決策者、日期都不一樣。

    為什麼要逐 block 寫死：上面兩條是**依來歷分派**的，若有人把某一筆的來歷改掉，
    它就會整筆跳到另一組斷言去、而**兩組都會通過**。本條是那個漏洞的補丁：
    **哪個 block 該是哪一種來歷**，在這裡釘死。
    """
    # ① `today.holdings` ＝ 總管推導填洞（UI_PAGE_TODAY.md §① holdings cols 段）
    holdings = page_today.COLS_DERIVATION["today.holdings"]
    assert page_today.COLS_PROVENANCE["today.holdings"] == page_today.COLS_DERIVED_BY_LEAD
    assert holdings["decided_by"] == "AI 總管"
    assert holdings["decided_on"] == "2026-09-21"
    assert holdings["wireframe_defines_cols"] is False
    assert holdings["wireframe_value"] is None
    assert holdings["value"] == (1, 1, 1) == page_today.BLOCK_COLS["today.holdings"]

    # ② 🔵 `today.summary` ＝ 客戶 2026-09-22 裁示 B 覆寫（UI_PAGE_TODAY.md ③「U-1 已決」段）
    summary = page_today.COLS_DERIVATION["today.summary"]
    assert page_today.COLS_PROVENANCE["today.summary"] == page_today.COLS_RULED_BY_CLIENT
    assert page_today.COLS_PROVENANCE["today.summary"] != page_today.COLS_FROM_WIREFRAME
    assert summary["decided_by"] == "客戶"
    assert summary["decided_on"] == "2026-09-22"
    assert summary["wireframe_defines_cols"] is True
    assert summary["wireframe_value"] == (3, 2, 1)     # 線框 `wf_page_today.js` 的舊值
    assert summary["value"] == (1, 1, 1) == page_today.BLOCK_COLS["today.summary"]


def test_the_client_ruling_text_is_not_quietly_rewritten():
    """🔴 **文字守衛：防裁示被改寫。** 客戶裁示 B 的兩個承重字眼必須留在 `basis` 裡。

    客戶原話：「三張獨立卡，不卡內三欄」＋「layer_html 的 3 欄不變，
    block 內部**不再巢狀網格**」。這兩句就是「為什麼是 1/1/1」的**全部理由** ——
    一旦被改寫成「為了版面一致」「為了效能」之類的話，這筆就從**客戶裁示**
    退化成**某個人的主張**，而值還在（`CLAUDE.md §-2` 規則 6：來歷錯比沒有來歷更危險）。
    """
    basis = page_today.COLS_DERIVATION["today.summary"]["basis"]
    assert any("三張獨立卡" in line for line in basis), (
        "裁示逐字「三張獨立卡」不見了 —— ⛔ 不得改寫客戶原話"
    )
    assert any("巢狀網格" in line for line in basis), (
        "裁示逐字「block 內部不再巢狀網格」不見了 —— ⛔ 不得改寫客戶原話"
    )


def test_the_client_ruling_changed_the_block_grid_not_the_layer_grid():
    """🔴 客戶逐字「**layer_html 的 3 欄不變**」—— 裁示只動 block 內部網格。

    ⇒ 兩件事同時成立才算做對：
      · `BLOCK_COLS["today.summary"]` ＝ `(1, 1, 1)`（卡內各佔一列、⛔ 不互相壓縮）；
      · `LAYER_GRID_COLS[2]` 仍 ＝ `(3, 2, 1)`（三張卡在第二層仍並排）。
    只做前者而順手把層網格也改成 1/1/1 ＝ 把三張卡疊成直條，
    **正面違反客戶 2026-09-16「第二層＝3 張並排卡」的裁示**（兩次裁示要一起成立）。
    """
    assert page_today.BLOCK_COLS["today.summary"] == (1, 1, 1)
    assert page_today.LAYER_GRID_COLS[2] == (3, 2, 1)
    assert page_today.BLOCK_COLS["today.summary"] != page_today.LAYER_GRID_COLS[2], (
        "block 網格與層級網格撞成同一個值 —— 兩個網格會分辨不出來"
    )
    assert page_today.cols_scope("today.summary") == "inside_block"


def test_rejected_singular_noun_argument_is_not_in_the_derivation_chain():
    """🔴 推導鏈裡**被打掉的那一條**：「規格『組成只用既有元件：卡 `.blk.t2` …』
    那句的『卡』是**單數**，所以只有一張卡」。

    中文不標複數 ⇒ 這條推不出來（對抗查證組已推翻；UI_PAGE_TODAY.md ① 四層表的
    「第二層 核心卡」列就是拿 `t2` 當**型別**用）。⛔ 不得日後被人當成第四條理由補回去。
    """
    for block in page_today.DERIVED_COLS:
        for line in page_today.COLS_DERIVATION[block]["basis"]:
            assert "單數" not in line and "複數" not in line, (
                f"{block} 的推導鏈混進了被推翻的『單複數』論證：{line!r}")


# ══════════════════════════════════════════════════════════════════
# C-2 四層「自動掛」（UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛」）
# ══════════════════════════════════════════════════════════════════
def test_every_block_inherits_its_layer_tier_automatically():
    """UI_COMPONENTS.md §1「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」。

    可觀測形式：同層的每個 block 拿到的密度**必須**是該層的密度，
    而該層密度又必須等於 `components.tier_for_layer(層序)` —— 中間沒有手選的餘地。
    """
    for layer in page_today.LAYERS:
        expected = components.tier_for_layer(layer["layer"])
        assert layer["tier"] == expected, f"layer {layer['layer']} 的密度不是自動掛的"
        for block in layer["blocks"]:
            assert page_today.tier_for_block(block) == expected


def test_blocks_are_plain_keys_with_no_per_block_tier_slot():
    """⛔ 非逐塊手選 ⇒ block 只能是字串 key，結構上就沒有地方塞 per-block tier。"""
    for layer in page_today.LAYERS:
        for block in layer["blocks"]:
            assert isinstance(block, str)


def test_tier_for_block_has_no_override_parameter():
    params = inspect.signature(page_today.tier_for_block).parameters
    assert list(params) == ["block_key"]
    assert not {"tier", "density", "override"} & set(params)


def test_unknown_block_raises():
    with pytest.raises(KeyError):
        page_today.tier_for_block("today.not_a_block")


# ══════════════════════════════════════════════════════════════════
# C-3 三卡歸位（user 2026-09-16 裁示，
#     UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段「3 卡歸位」已決段）
# ══════════════════════════════════════════════════════════════════
def test_summary_has_three_columns_named_by_the_wireframe():
    # UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段：線框 `today.summary` 的 name 逐字
    # ＝「③ 三欄摘要（位階／動能／風險）」
    assert tuple(col["name"] for col in page_today.SUMMARY_COLUMNS) == ("位階", "動能", "風險")
    # ⚠️ ~~①「第二層」today.summary 條：線框 `cols 3/2/1`~~
    #    ~~assert page_today.BLOCK_COLS["today.summary"] == (3, 2, 1)~~
    # 🔵 **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶（裁示 B）。**
    # **舊斷言的理由仍然成立**：它釘的是線框值，而線框 `wf_page_today.js` 的
    # `today.summary` block 確實逐字寫 `cols: { desktop: 3, tablet: 2, phone: 1 }`。
    # **被權衡掉的是「線框值＝現行值」這個前提** —— 客戶裁示 B 已覆寫它。
    # ⚠️ **三欄的「名字」與「有幾個」都沒有變**：客戶改的是它們**怎麼排**
    #    （一張卡內三欄 → 三張獨立卡），⛔ 不是改名字、⛔ 不是刪欄。
    assert page_today.BLOCK_COLS["today.summary"] == (1, 1, 1)   # ③「U-1 已決」段


def test_regime_column_keeps_its_existing_wiring():
    """UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段「逐欄落地（依裁示逐字）」(a)：
    「『位階』＝ `summary.regime` **既有、維持現接線**，
    ⛔ 不得把 `verdict.regime` 搬過去」（客戶明示「位階 ← summary.regime（既有）」）。"""
    regime = page_today.SUMMARY_COLUMNS[0]
    assert regime["source"] == "summary.regime"
    assert regime["wired"] is True
    assert regime["source"] != "verdict.regime", "⛔ 同源重複，搬過去是撞欄不是填空"


def test_momentum_column_stays_unwired_and_is_drawn_as_badge_5():
    """UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段「逐欄落地（依裁示逐字）」(b)：
    「『動能』**維持未接線**，⛔ 不得拿 `verdict.exposure` 頂替」
    （客戶明示「**exposure 不是動能，不搬**」）；未接線態依 ② 走 **#5**，⛔ 不得畫成 #1。"""
    momentum = page_today.SUMMARY_COLUMNS[1]
    assert momentum["wired"] is False
    assert momentum["source"] is None
    # ② 狀態覆蓋表 `unwired` 列（#5）＋ ③「逐欄落地」(b)
    assert momentum["badge"] == 5
    assert momentum["badge"] != 1, "⛔ 未接線不得畫成『正常』"


def test_risk_column_maps_directly_from_verdict_danger():
    # UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段「逐欄落地（依裁示逐字）」(c)：
    #「『風險』← `verdict.danger` **直接對映**」
    risk = page_today.SUMMARY_COLUMNS[2]
    assert risk["source"] == "verdict.danger"
    assert risk["wired"] is True


@pytest.mark.parametrize("orphan", ["verdict.exposure", "verdict.regime"])
def test_exposure_and_regime_are_not_reassigned_anywhere_in_layer_two(orphan):
    """UI_PAGE_TODAY.md ③「`today.verdict` 形狀」段「兩卡最終去向＝開放項」：
    「兩卡的最終去向＝**開放項**（⛔ 客戶未裁、⛔ 非本組判定）…
    ⛔ 不得自行判定刪除、⛔ 不得自行安排到第二層其他 block」。"""
    assert orphan not in {col["source"] for col in page_today.SUMMARY_COLUMNS}
    assert orphan in page_today.OPEN_ITEMS, "⛔ 不得默默消失：開放項要留在紀錄裡"


# ══════════════════════════════════════════════════════════════════
# C-4 主 CTA（UI_PAGE_TODAY.md ①「第三層 `today.actions`」段
#      ／④ 反例自檢 A「第三層 `today.actions`」條）
# ══════════════════════════════════════════════════════════════════
def test_main_cta_label_is_the_ssot_string():
    # UI_PAGE_TODAY.md ①「第三層 `today.actions`」段：
    # 字串 SSOT `shared/ia_nav.py ACTION_LABELS[ACTION_UPDATE_TODAY]`，
    # 與線框 `mainCTA.label` 逐字相同
    assert page_today.MAIN_CTA["label"] == "🚀 更新今日戰情"


def test_main_cta_uses_the_primary_button_class():
    # UI_PAGE_TODAY.md ①「第三層 `today.actions`」段：按鈕規格取 UI_COMPONENTS §3 主 CTA
    assert page_today.MAIN_CTA["button"] == "primary_cta"
    assert components.BUTTONS["primary_cta"]["min_height_px"] == 40.0


def test_exactly_one_main_cta_on_the_whole_page():
    """~~UI_COMPONENTS.md §3 按鈕表「主 CTA（**全站唯一一顆**）」列~~

    **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶。**
    **現行：UI_COMPONENTS.md §3 按鈕表「主 CTA（**每頁首屏唯一一顆**）」列。**
    客戶裁示逐字：「**不是「全站唯一」，是「每頁首屏唯一」。** 理由：客戶原話是
    『首屏僅允許一顆主 CTA』——是『每屏一顆』。」
    **舊說法的理由仍然成立，⛔ 不是寫錯**：在只有「🚦 今天」一頁時，「全站唯一」與
    「每頁首屏唯一」**外延相同**，寫哪個都對。
    **被權衡掉的原因**：五頁 IA 落地後，🔎 選股頁有自己的主 CTA `🎯 開始選股`
    ⇒「全站唯一」變成**假的**（`docs/v2/spec/UI_PAGE_FIND.md` ① 2026-09-16 已逐字否證）。
    ⚠️ **鍵名一併改**（~~`unique_per_site`~~ → **`unique_per_first_screen`**）——
    **鍵名本身在說謊**：留著它，下一個讀 code 的人會以為契約保證全站只有一顆。
    ⛔ **本條斷言的意圖一字未改**：仍斷言為 `True`、仍斷言主 CTA 只掛第三層。

    ⚠️ **下面這句逐字引用刻意保留舊措辭、⛔ 未改**：`UI_PAGE_TODAY.md` ①「第三層
    `today.actions`」段原文為「全頁 `st.button` 0 命中 ⇒ 全站唯一一顆主 CTA 的規定
    在本頁成立」。改它會讓**引用與被引用的原文對不上**（＝ 捏造出處），而該規格檔
    **不在本輪檔案邊界內** ⇒ 已列入交總管的「邊界外待同步落點」清單。"""
    assert page_today.MAIN_CTA["unique_per_first_screen"] is True
    owners = [layer["layer"] for layer in page_today.LAYERS if layer["has_main_cta"]]
    assert owners == [3], f"主 CTA 只能掛在第三層操作列，實際：{owners}"


def test_second_layer_is_not_clickable():
    """UI_PAGE_TODAY.md ①「第二層」段起手句「（⛔ 卡片本身不可點，線框 n2 層標籤逐字）：
    ⛔ 本層不得放任何按鈕、連結、`st.popover`」；同節 today.holdings 條
    「組成**只用既有元件**…⛔ 無按鈕（不可點）」。"""
    assert _layer(2)["allows_interaction"] is False
    assert _layer(2)["has_main_cta"] is False


@pytest.mark.parametrize("failure_reason", [None, "MISS_NO_INPUT", "MISS_NOT_ENOUGH"])
def test_main_cta_stays_pressable_for_retryable_failures(failure_reason):
    """UI_PAGE_TODAY.md ④ 反例自檢 A「第三層 `today.actions`」條
    「主 CTA **可按**，說明字『**可以重試** —— 上游這輪失敗，
    不是程式錯誤。』」"""
    state = page_today.main_cta_state(failure_reason=failure_reason)
    assert state["enabled"] is True
    if failure_reason is not None:
        assert state["note"] == page_today.MAIN_CTA_RETRY_NOTE
        assert page_today.MAIN_CTA_RETRY_NOTE == "可以重試 —— 上游這輪失敗，不是程式錯誤。"


def test_contract_drift_disables_the_cta_and_never_says_retry():
    """UI_PAGE_TODAY.md ④ 反例自檢 A「第三層 `today.actions`」條的例外
    「`MISS_CONTRACT_DRIFT`（契約漂移…）⇒ 按鈕**停用**＋
    『🔴 重按不會好，程式要修，請回報。』⛔ 不得對契約漂移給『可重跑』指引」。"""
    state = page_today.main_cta_state(failure_reason="MISS_CONTRACT_DRIFT")
    assert state["enabled"] is False
    assert state["note"] == "🔴 重按不會好，程式要修，請回報。"
    assert page_today.MAIN_CTA_CONTRACT_DRIFT_NOTE == state["note"]
    assert "可重跑" not in state["note"]
    assert "可以重試" not in state["note"]


def test_disabled_cta_falls_back_to_the_disabled_button_class():
    # UI_PAGE_TODAY.md ①「第三層 `today.actions`」段末
    #「停用態…走 §3『停用態』：`13.5px/500`＋`1px dashed --rule-2`＋字 `--sig-grey`」
    disabled = components.BUTTONS["disabled"]
    assert disabled["font_px"] == 13.5 and disabled["font_weight"] == 500
    assert disabled["border_style"] == "dashed" and disabled["fg"] == "--sig-grey"


# ══════════════════════════════════════════════════════════════════
# C-5 狀態覆蓋（UI_PAGE_TODAY.md ② 狀態覆蓋）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "state, miss_reason, badge",
    [
        ("live", None, 1),                              # ② 狀態覆蓋表 `live` 列
        ("loading", None, 2),                           # ② 狀態覆蓋表 `loading` 列
        ("idle", None, 3),                              # ② 狀態覆蓋表 `idle` 列
        ("degraded", None, 4),                          # ② 狀態覆蓋表 `degraded` 列
        ("unwired", None, 5),                           # ② 狀態覆蓋表 `unwired` 列
        ("failed", None, 6),                            # ② 狀態覆蓋表 `error` 列的常數值
        ("error", None, 6),                             # ② 落差 5「#6 字面不一致」線框鍵同義
        ("empty", "MISS_NO_INPUT", 7),                  # ② 狀態覆蓋表 `empty` 列
        ("empty", "MISS_NOT_ENOUGH", 7),                # ② 狀態覆蓋表 `empty` 列
        ("empty", "MISS_NO_VARIATION", 7),              # ② 狀態覆蓋表 `empty` 列
        ("missing", None, 7),                           # ② 狀態覆蓋表 `missing` 列＋落差 2
        ("na", "MISS_NOT_APPLICABLE", 8),               # ② 狀態覆蓋表 `na` 列
        ("empty", "MISS_NOT_APPLICABLE", 8),            # ② 狀態覆蓋表 `na` 列「靠 miss_reason 分辨」
    ],
)
def test_state_to_badge_mapping(state, miss_reason, badge):
    assert page_today.resolve_badge(state=state, miss_reason=miss_reason) == badge


def test_missing_is_drawn_as_7_not_8():
    """UI_PAGE_TODAY.md ② 落差 2「#7 被 `empty`＋`missing` 兩鍵共用」的處置：
    「兩鍵**都畫 #7**，⛔ 不得為了對齊線框鍵數而新造第 11 種徽章；
    ⛔ 也不得把 `missing` 畫成 #8（#8 專屬 `MISS_NOT_APPLICABLE`，重跑無效，畫錯等於給錯指引）」。"""
    assert page_today.resolve_badge(state="missing") == 7
    assert page_today.resolve_badge(state="missing") != 8
    # ~~`assert len(components.BADGES) == 10, "⛔ 不得新造第 11 種徽章"`~~
    # 📌 2026-09-26 客戶新增 #11「▨ 無資料」（有意識的規格變更，⛔ 不是漏刪）。
    #    **本條守衛的意圖不變**：`missing`／`empty` **不因為多了一顆徽章就改畫別的** ——
    #    裸 `missing`／`empty` 仍然是 #7，⛔ 不是 #11（#11 只給登記過的有效空結果）。
    assert len(components.BADGES) == 11, "⛔ 不得再新造第 12 種徽章"
    assert page_today.resolve_badge(state="missing") != 11
    assert page_today.resolve_badge(state="empty") == 7
    assert page_today.resolve_badge(state="empty") != 11


@pytest.mark.parametrize("state, miss_reason", [
    ("missing", None), ("na", "MISS_NOT_APPLICABLE"), ("empty", "MISS_NOT_APPLICABLE"),
    ("empty", "MISS_NO_INPUT"), ("idle", None), ("loading", None), ("failed", None),
    ("error", None), ("unwired", None), ("degraded", None), ("live", None),
    ("partial", None),
])
def test_valid_empty_flag_is_refused_outside_plain_empty(state, miss_reason):
    """客戶 2026-09-26：#11 ⛔ 不得擴散到任何別的態 —— 契約層直接拒收，⛔ 不是默默忽略旗標。"""
    with pytest.raises(ValueError):
        page_today.resolve_badge(state=state, miss_reason=miss_reason, valid_empty=True)


def test_valid_empty_flag_on_plain_empty_draws_11():
    assert page_today.resolve_badge(state="empty", valid_empty=True) == 11
    assert page_today.VALID_EMPTY_BADGE == 11
    assert components.badge(page_today.VALID_EMPTY_BADGE)["text"] == "無資料"


def test_idle_must_not_be_used_to_fake_loading():
    """UI_PAGE_TODAY.md ② 落差 1「#2 `loading`」的處置：
    「⛔ 在補上之前，**不得**拿 #3『尚未載入』冒充載入中」。"""
    assert page_today.resolve_badge(state="idle") == 3
    assert page_today.resolve_badge(state="loading") == 2
    assert page_today.resolve_badge(state="idle") != page_today.resolve_badge(state="loading")


def test_cold_start_is_grey_never_red():
    """UI_PAGE_TODAY.md ④ 反例自檢 B「冷啟動」條
    「冷啟動（`requested=False`）：一律 **#3 ⬜ 尚未載入** ＋ 灰色說明，
    ⛔ **不得畫成紅色錯誤**（`CLAUDE.md §1.A` 第 4 點）」。"""
    badge = components.badge(page_today.resolve_badge(state="idle"))
    assert badge["fg"] == "--sig-grey" and badge["bg"] == "--sig-grey-bg"
    assert "red" not in badge["fg"] and "red" not in badge["bg"]
    assert badge["border_color"] != "--sig-red"


def test_partial_fails_safe_to_7_when_numerator_or_denominator_is_missing():
    """UI_PAGE_TODAY.md ② 落差 3「#9 `partial`」／④ 反例自檢 B 首條
    ＋ UI_COMPONENTS.md §2 硬規則（fail-safe）：
    「『N／M』的分子分母若拿不到 → 一律降級顯示為 #7『缺漏 · 可重跑』，
      ⛔ 不得退回 #1『正常』」—— 缺資訊時往保守側退。"""
    for numerator, denominator in [(None, None), (12, None), (None, 18)]:
        got = page_today.resolve_badge(
            state="partial", numerator=numerator, denominator=denominator)
        assert got == 7, f"({numerator}, {denominator}) 應 fail-safe 為 #7，實得 #{got}"
        assert got != 1, "⛔ 不得退回『正常』（假綠燈）"


def test_partial_reconnects_to_9_once_l3_supplies_n_over_m():
    """UI_PAGE_TODAY.md ② 落差 3「#9 `partial`」末句
    「L3 補齊分子分母欄位後，這三處要接回 #9，**不是永久降級**」。"""
    assert page_today.resolve_badge(state="partial", numerator=12, denominator=18) == 9
    assert components.badge(9)["text"] == "N／M 計入"  # UI_COMPONENTS.md §2 徽章表 #9


def test_badge_10_is_not_drawn_here_but_is_not_merged_into_8():
    """UI_PAGE_TODAY.md ② 落差 4「#10 `emits_level=False`」
    「本頁**不畫 #10**；⛔ 但不得因此把 #10 併進 #8
    （2026-08-26 裁示三旗標互相獨立）」。"""
    assert page_today.BADGES_NOT_ON_PAGE == frozenset({10})
    assert 10 not in page_today.BADGES_ON_PAGE
    assert components.badge(10)["state_const"] != components.badge(8)["state_const"]
    assert components.badge(10)["icon"] != components.badge(8)["icon"]


@pytest.mark.parametrize(
    "block, badges",
    [
        ("today.verdict", (1, 3, 4, 5, 6, 7)),              # ①「第一層 today.verdict」段
        ("today.summary", (1, 3, 4, 5, 6, 7, 8, 9)),        # ①「第二層」today.summary 條
        ("today.warroom", (1, 3, 5, 6, 7)),                 # ①「第四層」段
        ("today.detail", (1, 3, 4, 5, 6, 7, 8, 9)),         # ①「第四層」段
    ],
)
def test_block_badge_inventory(block, badges):
    assert page_today.BLOCK_BADGES[block] == badges
    assert 10 not in badges  # ② 落差 4：本頁不畫 #10


# ══════════════════════════════════════════════════════════════════
# C-6 缺值時的畫面行為（UI_PAGE_TODAY.md ④ 反例自檢）—— §1 Fail Loud 的 UI 面
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("state", ["failed", "idle", "loading", "unwired", "empty", "missing", "na"])
@pytest.mark.parametrize("stale_value", [0, 0.0, 18.4, "—", None])
def test_grey_and_red_states_leave_the_value_blank(state, stale_value):
    """UI_PAGE_TODAY.md ④ 反例自檢 A「第一層 `today.verdict`」條
    「大字區**留白**（`render_card` 灰態與紅態一律留白），⛔ 不得顯示 `0` 或上一輪殘值」；
    同 ④ B「⛔ 全域」條「缺值一律不顯示為 `0`」。"""
    got = page_today.card_value_text(state=state, value=stale_value)
    assert got is None, f"state={state} value={stale_value!r} 應留白，實得 {got!r}"


def test_live_state_prints_the_value():
    # ② 狀態覆蓋表 `live` 列
    assert page_today.card_value_text(state="live", value=18.4) == "18.4"


def test_degraded_prints_the_observation_but_blanks_the_verdict():
    """UI_PAGE_TODAY.md ④ 反例自檢 B「`degraded` 的格子」條
    「`degraded` 的格子：**觀測照出、判決留白** ——
    有值就印值 ＋ #4 🟠『門檻已失準』，⛔ 不因為門檻失效就把值藏起來，
    也⛔ 不照失效門檻判燈」。"""
    assert page_today.card_value_text(state="degraded", value=18.4) == "18.4"
    assert page_today.card_level_text(state="degraded", level="綠") is None
    assert page_today.resolve_badge(state="degraded") == 4


@pytest.mark.parametrize(
    "value, miss_reason",
    [(None, None),                    # 非法：沒有值也沒有原因
     (18.4, "MISS_NO_INPUT"),         # 非法：有值卻同時宣告缺漏
     (0, "MISS_NOT_APPLICABLE")],
)
def test_illegal_observation_pairs_become_contract_drift(value, miss_reason):
    """UI_PAGE_TODAY.md ④ 反例自檢 B「⛔ 全域」條
    「`(None, None)` 與 `(值, MISS_*)` 為**非法二元組**，
    收到當 `MISS_CONTRACT_DRIFT`」。"""
    assert page_today.observation_miss_reason(value, miss_reason) == "MISS_CONTRACT_DRIFT"


@pytest.mark.parametrize(
    "value, miss_reason, expected",
    [(18.4, None, None),                        # 合法：有值、無缺漏原因
     (None, "MISS_NO_INPUT", "MISS_NO_INPUT"),  # 合法：沒值、有原因
     (None, "MISS_NOT_APPLICABLE", "MISS_NOT_APPLICABLE")],
)
def test_legal_observation_pairs_pass_through(value, miss_reason, expected):
    assert page_today.observation_miss_reason(value, miss_reason) == expected


# ══════════════════════════════════════════════════════════════════
# C-7 持倉健檢（UI_PAGE_TODAY.md ①「第二層」today.holdings 條）
#     —— 拿不到部位大小就⛔不准裝作拿得到
# ══════════════════════════════════════════════════════════════════
def test_holdings_field_whitelist_is_exactly_the_nine_count_derived_fields():
    """UI_PAGE_TODAY.md ①「第二層」today.holdings 條
    「**可顯示**（皆由檔數推得）」那行的九項；同條「⛔ **不得顯示**：損益、部位佔比、
    金額、張數、均價，或任何需要張數／均價才算得出來的量」。

    ⚠️ 「可顯示」＝ **白名單／准許清單**，⛔ **不是必填清單** —— 「可顯示」該行只有後半
    「＋ 等權假設揭露句一行」標了**必填**。本條測的是**白名單的內容**，
    ⛔ 不是「九項一定要全部畫出來」（那一點由下一條測）。
    """
    assert page_today.HOLDINGS_DISPLAY_FIELDS == (
        "n_total", "n_classified", "n_unclassified", "n_industries",
        "coverage_pct", "top1_pct", "top3_pct", "hhi", "n_eff",
    )


@pytest.mark.parametrize(
    "rendered",
    [(),                                                     # 退化：一項都不畫
     ("n_total", "n_classified", "n_industries", "top1_pct"),  # 原型實際只畫這 4 項
     ("n_total", "n_classified", "n_unclassified", "n_industries",
      "coverage_pct", "top1_pct", "top3_pct", "hhi", "n_eff")],  # 全九項
)
def test_any_subset_of_the_whitelist_is_legal(rendered):
    """白名單＝**至多**這九項，⛔ 不是**至少**這九項。
    渲染端只畫子集是合法的（`docs/v2/prototype/ui_prototype_today.html`「C. 持倉健檢」段
    ── `section.blk.t2`，標題 `id` 為 `h-t` ── 這張卡實際只畫 4 條 key-value：
    持股檔數／已分類檔數／產業數／最大單一產業（檔數等權））。"""
    assert page_today.unknown_holdings_fields(rendered) == ()


@pytest.mark.parametrize(
    "rendered, offender",
    [(("n_total", "pnl"), "pnl"),
     (("position_pct",), "position_pct"),
     (("n_total", "avg_cost"), "avg_cost")],
)
def test_fields_outside_the_whitelist_are_reported_not_silently_accepted(rendered, offender):
    """§1 Fail Loud：白名單外的欄位要**被指名回報**，⛔ 不得靜默放行。"""
    assert page_today.unknown_holdings_fields(rendered) == (offender,)


@pytest.mark.parametrize(
    "banned", ["pnl", "profit", "loss", "amount", "twd", "cost", "price",
               "shares", "lots", "qty", "position", "market_value"],
)
def test_holdings_never_leaks_a_position_sized_field(banned):
    """持股來源 `stock_watchlist` 只有 `name`／`ticker`／`updated_at` 三欄
    （UI_PAGE_TODAY.md ①「第二層」today.holdings 條「🔴 **資料限制（硬規則）**」行）
    ⇒ 這張卡**拿不到部位大小**，⛔ 不得出現任何需要張數／均價的量。"""
    for field in page_today.HOLDINGS_DISPLAY_FIELDS:
        assert banned not in field.lower(), f"⛔ 欄位 {field} 洩漏了部位大小語意（{banned}）"


def test_holdings_declares_the_equal_weight_assumption():
    """UI_PAGE_TODAY.md ①「第二層」today.holdings 條「🔴 **資料限制（硬規則）**」與
    「**可顯示**（皆由檔數推得）」兩行：「`concentration.py` 因此一律 `basis='equal_weight'`
    並要求 UI 揭露該假設…**＋ 等權假設揭露句一行（必填，`--ink-3` `11.5px` 說明字級）**」。"""
    assert page_today.HOLDINGS_BASIS == "equal_weight"
    disclosure = page_today.HOLDINGS_EQUAL_WEIGHT_DISCLOSURE
    assert isinstance(disclosure["text"], str) and disclosure["text"].strip(), "揭露句必填"
    assert disclosure["color"] == "--ink-3"
    assert disclosure["font_px"] == 11.5


def test_top1_label_is_verbatim_and_never_called_position_share():
    # UI_PAGE_TODAY.md ①「第二層」today.holdings 條「`top1_pct` 標籤逐字」行：
    #「`top1_pct` 標籤逐字為「最大單一產業（檔數等權）」，⛔ 不得標成「部位佔比」」
    assert page_today.HOLDINGS_TOP1_LABEL == "最大單一產業（檔數等權）"
    assert "部位佔比" not in page_today.HOLDINGS_TOP1_LABEL


def test_holdings_with_nothing_classified_is_a_gap_not_perfect_diversification():
    """UI_PAGE_TODAY.md ①「第二層」today.holdings 條「`is_computable=False`」行
    「`is_computable=False`（`n_classified==0`）→ 徽章 **#7 缺漏 · 可重跑**，
    ⛔ 不得顯示 `0` 或「完美分散」」；④ 反例自檢 A「第二層」條同。"""
    got = page_today.holdings_badge(n_classified=0)
    assert got == 7
    assert got != 1, "⛔ 不得退回『正常』"
    assert components.badge(got)["text"] == "缺漏 · 可重跑"


# ══════════════════════════════════════════════════════════════════
# C-8 三斷點下的 `.g3` 欄數
#     ⚠️ ~~（UI_PAGE_TODAY.md ①「第二層」today.summary 條／①「第四層」段／~~
#         ~~①「排列（三斷點）」段）~~
#     🔵 **2026-09-22 有意識的政策變更，⛔ 不是漏刪；決策者：客戶（裁示 B）。**
#     `today.summary` 的 block cols 已被客戶覆寫成 1/1/1 ⇒ 本段 3/2/1 的**來源**改指：
#       · **UI_PAGE_TODAY.md ①「第四層」段**（`today.detail` 的 block cols），與
#       · **UI_PAGE_TODAY.md ①「第二層」層級網格段**（`LAYER_GRID_COLS[2]`），
#       ＋ ①「排列（三斷點）」段（斷點語意）。
#     **舊出處的理由仍然成立**（當時 summary 確實寫 3/2/1，是最貼近的出處），
#     只是那個前提已被客戶裁示覆寫。⚠️ **`G3_COLS` 這個常數本身⛔ 沒有退役。**
# ══════════════════════════════════════════════════════════════════
def test_g3_cols_declaration():
    # 線框 `cols 3/2/1` ＝ (桌機, 平板, 手機)
    assert page_today.G3_COLS == (3, 2, 1)
    # ⚠️ ~~assert page_today.BLOCK_COLS["today.summary"] == page_today.G3_COLS~~
    #    🔵 2026-09-22 客戶裁示 B 覆寫後**改為反向釘住**：summary ⛔ 不再等於 `G3_COLS`。
    #    ⛔ 不是刪掉這一行了事 —— 直接刪會讓「summary 曾經是 3/2/1」這件事沒人擋得住
    #    回頭被改回去；反向斷言才會在有人改回去時**變紅**。
    assert page_today.BLOCK_COLS["today.summary"] != page_today.G3_COLS
    assert page_today.BLOCK_COLS["today.summary"] == (1, 1, 1)
    # `G3_COLS` 仍有兩個使用者（⇒ ⛔ 不得因為 summary 不用了就把它拔掉）
    assert page_today.BLOCK_COLS["today.detail"] == page_today.G3_COLS
    assert page_today.LAYER_GRID_COLS[2] == page_today.G3_COLS


@pytest.mark.parametrize(
    "viewport, expected",
    [(390, 1), (640, 1),            # ≤640 手機 → 1 欄
     (641, 2), (880, 2),            # 641–880 平板 → 2 欄
     (881, 3), (1440, 3)],          # ≥881 桌機 → 3 欄
)
def test_g3_columns_at_the_three_breakpoints(viewport, expected):
    assert components.resolve_cols(page_today.G3_COLS, viewport) == expected


@pytest.mark.parametrize("block", ["today.verdict", "today.key_banner", "today.actions",
                                   "today.warroom", "today.statusbar"])
@pytest.mark.parametrize("viewport", [390, 700, 1440])
def test_full_width_blocks_stay_one_column_at_every_breakpoint(block, viewport):
    # UI_PAGE_TODAY.md ①「葉外 chrome」／「第一層 `today.verdict`」／
    # 「第二層」today.key_banner 條／「第三層 `today.actions`」／「第四層」各段：
    # 這些 block 線框皆為 `cols 1/1/1`
    assert page_today.BLOCK_COLS[block] == (1, 1, 1)
    assert components.resolve_cols(page_today.BLOCK_COLS[block], viewport) == 1


# ══════════════════════════════════════════════════════════════════
# C-9 **層級網格** —— 三張並排卡在三斷點怎麼排（UI_PAGE_TODAY.md §① 第二層段）
#
# 🔴 本段防的是一個**不會被其他任何測試抓到**的誤讀：
#    `BLOCK_COLS["today.holdings"] == (1, 1, 1)` 講的是「**卡內**一列放一格」，
#    ⛔ **不是**「它獨佔一列、堆在最下面」。兩者是**兩個不同的網格**：
#      · `BLOCK_COLS`      ＝ block **內部**一列幾格（`_ui_kit.grid(items, cols)` 吃的那個）
#      · `LAYER_GRID_COLS` ＝ 同一層的幾個 block **彼此**怎麼並排
#    把 holdings 畫成第三張全寬卡疊在底部，會**正面違反客戶 2026-09-16
#    「第二層＝3 張並排卡」的裁示**（UI_PAGE_TODAY.md ①「第二層」段已決句
#    ／③「`today.verdict` 形狀」段裁決逐字）。
# ══════════════════════════════════════════════════════════════════
def test_layer_two_grid_is_three_two_one():
    """客戶 2026-09-16 裁示「第二層＝**3 張並排卡**」（UI_PAGE_TODAY.md ①「第二層」段已決句
    ／③「`today.verdict` 形狀」段裁決逐字）；
    缺的只是「那三張卡在三個斷點怎麼排」⇒ 原型 `.g3` CSS 實測補上：
    基準 `1fr`／641–880 `repeat(2,…)`／≥881 `repeat(3,…)` ＝ **3/2/1**。"""
    assert page_today.LAYER_GRID_COLS[2] == (3, 2, 1)
    assert page_today.LAYER_GRID_COLS[2] == page_today.G3_COLS
    assert len(page_today.blocks_of_layer(2)) == 3


@pytest.mark.parametrize(
    "viewport, per_row",
    [(390, 1), (640, 1),      # ≤640 手機 → 單欄
     (641, 2), (880, 2),      # 641–880 平板 → 兩欄
     (881, 3), (1440, 3)],    # ≥881 桌機 → 三欄
)
def test_layer_two_cards_per_row_at_the_three_breakpoints(viewport, per_row):
    assert page_today.blocks_per_row(2, viewport) == per_row


def test_holdings_sits_beside_the_other_two_on_desktop_not_stacked_below():
    """🔴 **本輪最重要的防呆**：桌機三張卡**同一列**，holdings ⛔ 不是疊在最下面的全寬卡。

    可觀測形式：第二層在桌機只佔 **1 列**（3 個 block ÷ 每列 3 格）。
    """
    assert page_today.rows_of_layer(2, 1440) == 1
    assert page_today.blocks_per_row(2, 1440) == len(page_today.blocks_of_layer(2))
    assert "today.holdings" in page_today.blocks_of_layer(2)
    # ⛔ 層網格不是 1/1/1 —— 若有人把它改成 1/1/1，三張卡就變成直向堆疊
    assert page_today.LAYER_GRID_COLS[2] != (1, 1, 1)


def test_block_cols_of_holdings_is_inside_the_card_not_the_layer_grid():
    """`today.holdings` 的 `(1, 1, 1)` ＝ **卡內**一列一格；
    它⛔ 不該被拿來當第二層的層網格（那是 `LAYER_GRID_COLS[2]`）。"""
    assert page_today.BLOCK_COLS["today.holdings"] == (1, 1, 1)
    assert page_today.BLOCK_COLS["today.holdings"] != page_today.LAYER_GRID_COLS[2]
    assert page_today.cols_scope("today.holdings") == "inside_block"


def test_layer_grid_is_only_declared_where_it_has_a_source():
    """⛔ 不得替其他層發明一組層網格（§1 反捏造）—— 只有第二層有來源
    （客戶裁示 3 張並排卡 ＋ 原型 `.g3` 實測）。問到未登記的層要**炸**，不是回一個猜的值。"""
    assert set(page_today.LAYER_GRID_COLS) == {2}
    with pytest.raises(KeyError):
        page_today.blocks_per_row(4, 1440)
