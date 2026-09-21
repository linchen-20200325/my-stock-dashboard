"""WT 測試組｜test-first 契約 C：「🚦 今天」頁（`src/ui_v2/page_today.py`）

⚠️ **本檔是規格書，不是現況描述。** 撰寫當下 `src/ui_v2/` 尚不存在，
   本檔因此**應該是紅燈（ModuleNotFoundError）** —— 紅燈即正確結果。
   實作組的任務＝把下面這份 API 做出來、讓它轉綠，⛔ 不是改本檔讓它變綠。

唯一資料來源：`docs/v2/spec/UI_PAGE_TODAY.md`（＋ 它引用的第 1、2 份）。
每條 assert 旁標 `# UI_PAGE_TODAY.md:NN`。
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
    線框 `cols` 記法 `(桌機, 平板, 手機)`。
    ⚠️ `today.holdings` 是新訂 block、線框 `n2` **未定義**其 cols
    ⇒ **⛔ 不得自行發明一組塞進來**（規格的洞，見本檔 test 與交付報告）。

`BLOCK_BADGES : Mapping[str, tuple[int, ...]]`
    各 block 依線框 `states` 會用到的徽章號（UI_PAGE_TODAY.md:22／:28／:45）。

`WITHDRAWN_BLOCKS : frozenset[str]`
    **已撤回、不是待補**的 block（UI_PAGE_TODAY.md:97 `chrome.asof`）。
    ⛔ 不得從 `LAYERS` 悄悄消失而不留紀錄。

`OPEN_ITEMS : frozenset[str]`
    **客戶未裁、去向開放**的卡（UI_PAGE_TODAY.md:115 `verdict.exposure`／`verdict.regime`）。
    ⛔ 不得自行判定刪除、⛔ 不得自行安排到第二層其他 block —— 但也⛔ 不得默默消失。

`SUMMARY_COLUMNS : tuple[Mapping, ...]`
    第二層 `today.summary` 三欄（位階／動能／風險），每欄：
      `name` / `source`(str|None) / `wired`(bool) / `badge`(int|None)

`BADGES_ON_PAGE / BADGES_NOT_ON_PAGE : frozenset[int]`

`MAIN_CTA : Mapping`  `label` / `button` / `unique_per_site`(True)
`MAIN_CTA_RETRY_NOTE : str`
`MAIN_CTA_CONTRACT_DRIFT_NOTE : str`
`G3_COLS : tuple[int, int, int]`  ＝ (3, 2, 1)

`HOLDINGS_DISPLAY_FIELDS : tuple[str, ...]`
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
# C-1 四層結構（UI_PAGE_TODAY.md:7-18）
# ══════════════════════════════════════════════════════════════════
def test_page_has_exactly_four_layers_plus_an_uncounted_chrome():
    """UI_PAGE_TODAY.md:10「線框 `n0` 為葉外 chrome（五頁共用，不屬任何葉）
    → **據實列出，不計入四層**」。"""
    numbered = [layer["layer"] for layer in page_today.LAYERS]
    assert sorted(n for n in numbered if n != 0) == [1, 2, 3, 4]
    assert numbered.count(0) == 1, "葉外 chrome 要據實列出（但不計入四層）"


def test_first_layer_is_one_verdict_light_not_three_cards():
    """UI_PAGE_TODAY.md:23-24「第一層＝**單一結論燈** ＋ 一句話結論…
    ⛔ 第一層**不再是 3 張並排卡**」（user 2026-09-16 裁示）。"""
    assert page_today.blocks_of_layer(1) == ("today.verdict",)
    assert len(page_today.blocks_of_layer(1)) == 1
    assert _layer(1)["tier"] == "t1"            # UI_PAGE_TODAY.md:15
    assert _layer(1)["badge_size"] == "b1"      # UI_PAGE_TODAY.md:15
    assert page_today.BLOCK_COLS["today.verdict"] == (1, 1, 1)  # UI_PAGE_TODAY.md:22 一格滿版


def test_second_layer_is_exactly_three_side_by_side_cards():
    """UI_PAGE_TODAY.md:27「第二層＝下列 3 張並排卡 —— `today.summary`／
    `today.key_banner`／🆕`today.holdings`」。"""
    assert page_today.blocks_of_layer(2) == (
        "today.summary", "today.key_banner", "today.holdings",
    )
    assert _layer(2)["tier"] == "t2"        # UI_PAGE_TODAY.md:16
    assert _layer(2)["badge_size"] == "b2"  # UI_PAGE_TODAY.md:16


def test_third_layer_is_the_action_row():
    assert page_today.blocks_of_layer(3) == ("today.actions",)  # UI_PAGE_TODAY.md:17
    assert _layer(3)["tier"] == "t3"
    assert page_today.BLOCK_COLS["today.actions"] == (1, 1, 1)  # UI_PAGE_TODAY.md:39


def test_fourth_layer_is_the_evidence_drawer():
    assert page_today.blocks_of_layer(4) == ("today.warroom", "today.detail")  # UI_PAGE_TODAY.md:18／:45
    assert _layer(4)["tier"] == "t4"        # t4 ＝ 1px **dashed**
    assert _layer(4)["badge_size"] == "b4"
    assert components.CARD_TIERS[_layer(4)["tier"]]["border_style"] == "dashed"


def test_chrome_layer_carries_the_status_bar():
    # UI_PAGE_TODAY.md:20「葉外 chrome（`cols 1/1/1` 三斷點皆滿版）：`today.statusbar` ＝ 3 張狀態卡」
    assert page_today.blocks_of_layer(0) == ("today.statusbar",)
    assert _layer(0)["tier"] == "t3"        # UI_PAGE_TODAY.md:14
    assert page_today.BLOCK_COLS["today.statusbar"] == (1, 1, 1)


def test_chrome_asof_is_withdrawn_not_pending():
    """UI_PAGE_TODAY.md:97「`chrome.asof`…**已撤回，不是待補**」
    （`get_macro_state()` 只有 9 key、無 `as_of`）。

    ⇒ 不得出現在版面，但要**留下紀錄**，⛔ 不是默默消失（§-2 規則 6 的同一紀律）。
    """
    all_blocks = {b for layer in page_today.LAYERS for b in layer["blocks"]}
    assert "chrome.asof" not in all_blocks
    assert "chrome.asof" in page_today.WITHDRAWN_BLOCKS


def test_holdings_columns_are_not_invented():
    """UI_PAGE_TODAY.md:30「🆕 `today.holdings` 持倉健檢 —— 新訂（線框 `n2` **未定義**此 block）」。

    ⇒ 它沒有線框 `cols`。⛔ 不得隨手發明一組欄數（§1 反捏造）。
    """
    assert "today.holdings" not in page_today.BLOCK_COLS


# ══════════════════════════════════════════════════════════════════
# C-2 四層「自動掛」（UI_COMPONENTS.md:36）
# ══════════════════════════════════════════════════════════════════
def test_every_block_inherits_its_layer_tier_automatically():
    """UI_COMPONENTS.md:36「四層由 `layers[].n` 自動掛，⛔ 非逐塊手選」。

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
# C-3 三卡歸位（user 2026-09-16 裁示，UI_PAGE_TODAY.md:111-115）
# ══════════════════════════════════════════════════════════════════
def test_summary_has_three_columns_named_by_the_wireframe():
    # UI_PAGE_TODAY.md:112 線框 `today.summary` 的 name 逐字＝「③ 三欄摘要（位階／動能／風險）」
    assert tuple(col["name"] for col in page_today.SUMMARY_COLUMNS) == ("位階", "動能", "風險")
    assert page_today.BLOCK_COLS["today.summary"] == (3, 2, 1)  # UI_PAGE_TODAY.md:28


def test_regime_column_keeps_its_existing_wiring():
    """UI_PAGE_TODAY.md:114(a)「『位階』＝ `summary.regime` **既有、維持現接線**，
    ⛔ 不得把 `verdict.regime` 搬過去」（客戶明示「位階 ← summary.regime（既有）」）。"""
    regime = page_today.SUMMARY_COLUMNS[0]
    assert regime["source"] == "summary.regime"
    assert regime["wired"] is True
    assert regime["source"] != "verdict.regime", "⛔ 同源重複，搬過去是撞欄不是填空"


def test_momentum_column_stays_unwired_and_is_drawn_as_badge_5():
    """UI_PAGE_TODAY.md:114(b)「『動能』**維持未接線**，⛔ 不得拿 `verdict.exposure` 頂替」
    （客戶明示「**exposure 不是動能，不搬**」）；未接線態依 ② 走 **#5**，⛔ 不得畫成 #1。"""
    momentum = page_today.SUMMARY_COLUMNS[1]
    assert momentum["wired"] is False
    assert momentum["source"] is None
    assert momentum["badge"] == 5            # UI_PAGE_TODAY.md:66／:114
    assert momentum["badge"] != 1, "⛔ 未接線不得畫成『正常』"


def test_risk_column_maps_directly_from_verdict_danger():
    # UI_PAGE_TODAY.md:114(c)「『風險』← `verdict.danger` **直接對映**」
    risk = page_today.SUMMARY_COLUMNS[2]
    assert risk["source"] == "verdict.danger"
    assert risk["wired"] is True


@pytest.mark.parametrize("orphan", ["verdict.exposure", "verdict.regime"])
def test_exposure_and_regime_are_not_reassigned_anywhere_in_layer_two(orphan):
    """UI_PAGE_TODAY.md:115「兩卡的最終去向＝**開放項**（⛔ 客戶未裁、⛔ 非本組判定）…
    ⛔ 不得自行判定刪除、⛔ 不得自行安排到第二層其他 block」。"""
    assert orphan not in {col["source"] for col in page_today.SUMMARY_COLUMNS}
    assert orphan in page_today.OPEN_ITEMS, "⛔ 不得默默消失：開放項要留在紀錄裡"


# ══════════════════════════════════════════════════════════════════
# C-4 主 CTA（UI_PAGE_TODAY.md:39-43／:127-129）
# ══════════════════════════════════════════════════════════════════
def test_main_cta_label_is_the_ssot_string():
    # UI_PAGE_TODAY.md:39-40 字串 SSOT `shared/ia_nav.py:83 ACTION_LABELS[ACTION_UPDATE_TODAY]`，
    # 與線框 `mainCTA.label` 逐字相同
    assert page_today.MAIN_CTA["label"] == "🚀 更新今日戰情"


def test_main_cta_uses_the_primary_button_class():
    # UI_PAGE_TODAY.md:41 按鈕規格取 UI_COMPONENTS §3 主 CTA
    assert page_today.MAIN_CTA["button"] == "primary_cta"
    assert components.BUTTONS["primary_cta"]["min_height_px"] == 40.0


def test_exactly_one_main_cta_on_the_whole_page():
    """UI_COMPONENTS.md:104「主 CTA（**全站唯一一顆**）」；
    UI_PAGE_TODAY.md:42「全頁 `st.button` 0 命中 ⇒ 全站唯一一顆主 CTA 的規定在本頁成立」。"""
    assert page_today.MAIN_CTA["unique_per_site"] is True
    owners = [layer["layer"] for layer in page_today.LAYERS if layer["has_main_cta"]]
    assert owners == [3], f"主 CTA 只能掛在第三層操作列，實際：{owners}"


def test_second_layer_is_not_clickable():
    """UI_PAGE_TODAY.md:26「（⛔ 卡片本身不可點，線框 n2 層標籤逐字）：
    ⛔ 本層不得放任何按鈕、連結、`st.popover`」；:32 持倉健檢「⛔ 無按鈕（不可點）」。"""
    assert _layer(2)["allows_interaction"] is False
    assert _layer(2)["has_main_cta"] is False


@pytest.mark.parametrize("failure_reason", [None, "MISS_NO_INPUT", "MISS_NOT_ENOUGH"])
def test_main_cta_stays_pressable_for_retryable_failures(failure_reason):
    """UI_PAGE_TODAY.md:127「主 CTA **可按**，說明字『**可以重試** —— 上游這輪失敗，
    不是程式錯誤。』」"""
    state = page_today.main_cta_state(failure_reason=failure_reason)
    assert state["enabled"] is True
    if failure_reason is not None:
        assert state["note"] == page_today.MAIN_CTA_RETRY_NOTE
        assert page_today.MAIN_CTA_RETRY_NOTE == "可以重試 —— 上游這輪失敗，不是程式錯誤。"


def test_contract_drift_disables_the_cta_and_never_says_retry():
    """UI_PAGE_TODAY.md:128-129「`MISS_CONTRACT_DRIFT`（契約漂移…）⇒ 按鈕**停用**＋
    『🔴 重按不會好，程式要修，請回報。』⛔ 不得對契約漂移給『可重跑』指引」。"""
    state = page_today.main_cta_state(failure_reason="MISS_CONTRACT_DRIFT")
    assert state["enabled"] is False
    assert state["note"] == "🔴 重按不會好，程式要修，請回報。"
    assert page_today.MAIN_CTA_CONTRACT_DRIFT_NOTE == state["note"]
    assert "可重跑" not in state["note"]
    assert "可以重試" not in state["note"]


def test_disabled_cta_falls_back_to_the_disabled_button_class():
    # UI_PAGE_TODAY.md:43「停用態…走 §3『停用態』：`13.5px/500`＋`1px dashed --rule-2`＋字 `--sig-grey`」
    disabled = components.BUTTONS["disabled"]
    assert disabled["font_px"] == 13.5 and disabled["font_weight"] == 500
    assert disabled["border_style"] == "dashed" and disabled["fg"] == "--sig-grey"


# ══════════════════════════════════════════════════════════════════
# C-5 狀態覆蓋（UI_PAGE_TODAY.md:58-90）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "state, miss_reason, badge",
    [
        ("live", None, 1),                              # UI_PAGE_TODAY.md:62
        ("loading", None, 2),                           # UI_PAGE_TODAY.md:63
        ("idle", None, 3),                              # UI_PAGE_TODAY.md:64
        ("degraded", None, 4),                          # UI_PAGE_TODAY.md:65
        ("unwired", None, 5),                           # UI_PAGE_TODAY.md:66
        ("failed", None, 6),                            # UI_PAGE_TODAY.md:67（常數值）
        ("error", None, 6),                             # UI_PAGE_TODAY.md:89-90 線框鍵視為同義
        ("empty", "MISS_NO_INPUT", 7),                  # UI_PAGE_TODAY.md:68
        ("empty", "MISS_NOT_ENOUGH", 7),                # UI_PAGE_TODAY.md:68
        ("empty", "MISS_NO_VARIATION", 7),              # UI_PAGE_TODAY.md:68
        ("missing", None, 7),                           # UI_PAGE_TODAY.md:69／:80
        ("na", "MISS_NOT_APPLICABLE", 8),               # UI_PAGE_TODAY.md:70
        ("empty", "MISS_NOT_APPLICABLE", 8),            # UI_PAGE_TODAY.md:70「靠 miss_reason 分辨」
    ],
)
def test_state_to_badge_mapping(state, miss_reason, badge):
    assert page_today.resolve_badge(state=state, miss_reason=miss_reason) == badge


def test_missing_is_drawn_as_7_not_8():
    """UI_PAGE_TODAY.md:80-81「兩鍵**都畫 #7**，⛔ 不得為了對齊線框鍵數而新造第 11 種徽章；
    ⛔ 也不得把 `missing` 畫成 #8（#8 專屬 `MISS_NOT_APPLICABLE`，重跑無效，畫錯等於給錯指引）」。"""
    assert page_today.resolve_badge(state="missing") == 7
    assert page_today.resolve_badge(state="missing") != 8
    assert len(components.BADGES) == 10, "⛔ 不得新造第 11 種徽章"


def test_idle_must_not_be_used_to_fake_loading():
    """UI_PAGE_TODAY.md:77「⛔ 在補上之前，**不得**拿 #3『尚未載入』冒充載入中」。"""
    assert page_today.resolve_badge(state="idle") == 3
    assert page_today.resolve_badge(state="loading") == 2
    assert page_today.resolve_badge(state="idle") != page_today.resolve_badge(state="loading")


def test_cold_start_is_grey_never_red():
    """UI_PAGE_TODAY.md:139-140「冷啟動（`requested=False`）：一律 **#3 ⬜ 尚未載入** ＋ 灰色說明，
    ⛔ **不得畫成紅色錯誤**（`CLAUDE.md §1.A` 第 4 點）」。"""
    badge = components.badge(page_today.resolve_badge(state="idle"))
    assert badge["fg"] == "--sig-grey" and badge["bg"] == "--sig-grey-bg"
    assert "red" not in badge["fg"] and "red" not in badge["bg"]
    assert badge["border_color"] != "--sig-red"


def test_partial_fails_safe_to_7_when_numerator_or_denominator_is_missing():
    """UI_PAGE_TODAY.md:83-84／:134 ＋ UI_COMPONENTS.md:78 硬規則（fail-safe）：
    「『N／M』的分子分母若拿不到 → 一律降級顯示為 #7『缺漏 · 可重跑』，
      ⛔ 不得退回 #1『正常』」—— 缺資訊時往保守側退。"""
    for numerator, denominator in [(None, None), (12, None), (None, 18)]:
        got = page_today.resolve_badge(
            state="partial", numerator=numerator, denominator=denominator)
        assert got == 7, f"({numerator}, {denominator}) 應 fail-safe 為 #7，實得 #{got}"
        assert got != 1, "⛔ 不得退回『正常』（假綠燈）"


def test_partial_reconnects_to_9_once_l3_supplies_n_over_m():
    """UI_PAGE_TODAY.md:84-85「L3 補齊分子分母欄位後，這三處要接回 #9，**不是永久降級**」。"""
    assert page_today.resolve_badge(state="partial", numerator=12, denominator=18) == 9
    assert components.badge(9)["text"] == "N／M 計入"  # UI_COMPONENTS.md:68


def test_badge_10_is_not_drawn_here_but_is_not_merged_into_8():
    """UI_PAGE_TODAY.md:86-87「本頁**不畫 #10**；⛔ 但不得因此把 #10 併進 #8
    （2026-08-26 裁示三旗標互相獨立）」。"""
    assert page_today.BADGES_NOT_ON_PAGE == frozenset({10})
    assert 10 not in page_today.BADGES_ON_PAGE
    assert components.badge(10)["state_const"] != components.badge(8)["state_const"]
    assert components.badge(10)["icon"] != components.badge(8)["icon"]


@pytest.mark.parametrize(
    "block, badges",
    [
        ("today.verdict", (1, 3, 4, 5, 6, 7)),              # UI_PAGE_TODAY.md:22
        ("today.summary", (1, 3, 4, 5, 6, 7, 8, 9)),        # UI_PAGE_TODAY.md:28
        ("today.warroom", (1, 3, 5, 6, 7)),                 # UI_PAGE_TODAY.md:45
        ("today.detail", (1, 3, 4, 5, 6, 7, 8, 9)),         # UI_PAGE_TODAY.md:45
    ],
)
def test_block_badge_inventory(block, badges):
    assert page_today.BLOCK_BADGES[block] == badges
    assert 10 not in badges  # UI_PAGE_TODAY.md:86 本頁不畫 #10


# ══════════════════════════════════════════════════════════════════
# C-6 缺值時的畫面行為（UI_PAGE_TODAY.md:122-141）—— §1 Fail Loud 的 UI 面
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("state", ["failed", "idle", "loading", "unwired", "empty", "missing", "na"])
@pytest.mark.parametrize("stale_value", [0, 0.0, 18.4, "—", None])
def test_grey_and_red_states_leave_the_value_blank(state, stale_value):
    """UI_PAGE_TODAY.md:122-123「大字區**留白**（`render_card` 灰態與紅態一律留白），
    ⛔ 不得顯示 `0` 或上一輪殘值」；:141「⛔ 全域：缺值一律不顯示為 `0`」。"""
    got = page_today.card_value_text(state=state, value=stale_value)
    assert got is None, f"state={state} value={stale_value!r} 應留白，實得 {got!r}"


def test_live_state_prints_the_value():
    assert page_today.card_value_text(state="live", value=18.4) == "18.4"  # UI_PAGE_TODAY.md:62


def test_degraded_prints_the_observation_but_blanks_the_verdict():
    """UI_PAGE_TODAY.md:137-138「`degraded` 的格子：**觀測照出、判決留白** ——
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
    """UI_PAGE_TODAY.md:141「`(None, None)` 與 `(值, MISS_*)` 為**非法二元組**，
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
# C-7 持倉健檢（UI_PAGE_TODAY.md:30-37）—— 拿不到部位大小就⛔不准裝作拿得到
# ══════════════════════════════════════════════════════════════════
def test_holdings_shows_only_the_nine_count_derived_fields():
    """UI_PAGE_TODAY.md:34「**可顯示**（皆由檔數推得）」九項；
    :35「⛔ **不得顯示**：損益、部位佔比、金額、張數、均價，
        或任何需要張數／均價才算得出來的量」。"""
    assert page_today.HOLDINGS_DISPLAY_FIELDS == (
        "n_total", "n_classified", "n_unclassified", "n_industries",
        "coverage_pct", "top1_pct", "top3_pct", "hhi", "n_eff",
    )


@pytest.mark.parametrize(
    "banned", ["pnl", "profit", "loss", "amount", "twd", "cost", "price",
               "shares", "lots", "qty", "position", "market_value"],
)
def test_holdings_never_leaks_a_position_sized_field(banned):
    """持股來源 `stock_watchlist` 只有 `name`／`ticker`／`updated_at` 三欄
    （UI_PAGE_TODAY.md:33）⇒ 這張卡**拿不到部位大小**，⛔ 不得出現任何需要張數／均價的量。"""
    for field in page_today.HOLDINGS_DISPLAY_FIELDS:
        assert banned not in field.lower(), f"⛔ 欄位 {field} 洩漏了部位大小語意（{banned}）"


def test_holdings_declares_the_equal_weight_assumption():
    """UI_PAGE_TODAY.md:33-34「`concentration.py` 因此一律 `basis='equal_weight'`
    並要求 UI 揭露該假設…**＋ 等權假設揭露句一行（必填，`--ink-3` `11.5px` 說明字級）**」。"""
    assert page_today.HOLDINGS_BASIS == "equal_weight"
    disclosure = page_today.HOLDINGS_EQUAL_WEIGHT_DISCLOSURE
    assert isinstance(disclosure["text"], str) and disclosure["text"].strip(), "揭露句必填"
    assert disclosure["color"] == "--ink-3"
    assert disclosure["font_px"] == 11.5


def test_top1_label_is_verbatim_and_never_called_position_share():
    # UI_PAGE_TODAY.md:36「`top1_pct` 標籤逐字為「最大單一產業（檔數等權）」，⛔ 不得標成「部位佔比」」
    assert page_today.HOLDINGS_TOP1_LABEL == "最大單一產業（檔數等權）"
    assert "部位佔比" not in page_today.HOLDINGS_TOP1_LABEL


def test_holdings_with_nothing_classified_is_a_gap_not_perfect_diversification():
    """UI_PAGE_TODAY.md:37「`is_computable=False`（`n_classified==0`）→ 徽章 **#7 缺漏 · 可重跑**，
    ⛔ 不得顯示 `0` 或「完美分散」」；:125-126 同。"""
    got = page_today.holdings_badge(n_classified=0)
    assert got == 7
    assert got != 1, "⛔ 不得退回『正常』"
    assert components.badge(got)["text"] == "缺漏 · 可重跑"


# ══════════════════════════════════════════════════════════════════
# C-8 三斷點下的 `.g3` 欄數（UI_PAGE_TODAY.md:28／:45／:47-48）
# ══════════════════════════════════════════════════════════════════
def test_g3_cols_declaration():
    # 線框 `cols 3/2/1` ＝ (桌機, 平板, 手機)
    assert page_today.G3_COLS == (3, 2, 1)
    assert page_today.BLOCK_COLS["today.summary"] == page_today.G3_COLS
    assert page_today.BLOCK_COLS["today.detail"] == page_today.G3_COLS


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
    # UI_PAGE_TODAY.md:20／:22／:29／:39／:45 這些 block 線框皆為 `cols 1/1/1`
    assert page_today.BLOCK_COLS[block] == (1, 1, 1)
    assert components.resolve_cols(page_today.BLOCK_COLS[block], viewport) == 1
