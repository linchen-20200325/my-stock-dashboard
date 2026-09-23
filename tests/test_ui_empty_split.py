"""tests/test_ui_empty_split.py — `UI_EMPTY` 三態分辨的守衛（客戶 2026-09-23 裁示 D-3(a)）。

裁示逐字：「**D-3(a)：補 `#7`/`#8`/`#9` 三態分辨，改 `shared/ui_state.py` ＋五頁 `page_*.py`**」

═══ 這裡守的是什麼（先讀這段，它決定了每條測試為什麼長這樣）═══════════
客戶要解決的**不是美觀，是資訊損失**：三種缺值都畫成同一顆 `UI_EMPTY` 時，
使用者**分不出該不該重試** —— #7 是「等一下再按」，#8 是「按幾次都一樣」。
讓人對著一個永遠不會變的格子一直按重新載入，和給他一個錯的數字一樣是誤導
（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險，錯誤的**指引**亦然）。

⇒ 本檔的每一條都釘在**使用者看得到的差別**上，不是釘在「有沒有新常數」。
  常數多幾個而畫面仍然一模一樣，這件事就沒有做完。

═══ 突變測試（`CLAUDE.md §-1.5.E A7`：守衛要能證明自己有牙齒）═════════
把三態合一改回去，下列守衛**必須**轉紅。兩個突變都實跑驗證過：

  M1 `EMPTY_STATE_BY_REASON = {}`（分派表清空 → 全部退回 `UI_EMPTY`）
     ⇒ `TestReasonDispatchActuallySplits` 4 條紅
  M2 `UI_STATE_META` 三個變體改回 `UI_EMPTY` 的 `("無資料", "▨", …)`
     ⇒ `TestThreeEmptiesLookDifferent` 3 條紅

⚠️ **本檔不寫死任何符號字面量**：glyph 一律從 L0 `UI_STATE_META` 讀回來比對。
   寫死等於在測試裡開第二真相源 —— L0 改了符號，測試會用舊符號繼續判綠。
"""
from __future__ import annotations

import io
import pathlib

import pytest

from shared.colors import TRAFFIC_NEUTRAL
from shared.station_specs import (
    MISS_CONTRACT_DRIFT,
    MISS_FETCH_FAILED,
    MISS_NO_INPUT,
    MISS_NO_VARIATION,
    MISS_NOT_APPLICABLE,
    MISS_NOT_ENOUGH,
    STATE_MISSING,
)
from shared.ui_state import (
    EMPTY_STATE_BY_REASON,
    NO_VALUE_STATES,
    UI_EMPTY,
    UI_FAILED,
    UI_MISSING_RETRYABLE,
    UI_NOT_APPLICABLE,
    UI_PARTIAL,
    UI_STATES,
    UI_STATE_META,
    classify_ui_state,
    is_alarming,
    state_meta,
)

#: 本次裁示涉及的四個「缺值家族」狀態（#7 / #8 / #9 ＋ 保守退路）。
_FAMILY: tuple[str, ...] = (
    UI_EMPTY, UI_MISSING_RETRYABLE, UI_NOT_APPLICABLE, UI_PARTIAL)

#: 五頁的實體路徑。**由 glob 取得，不手抄檔名** —— 手抄的清單在有人新增
#: 第六頁時會靜靜地漏掉它（而且漏的方式是「測試還是綠的」）。
_PAGES: tuple[pathlib.Path, ...] = tuple(
    sorted(pathlib.Path("src/ui/views").glob("page_*.py")))


def _glyph(state: str) -> str:
    return state_meta(state)[1]


def _label(state: str) -> str:
    return state_meta(state)[0]


class TestThreeEmptiesLookDifferent:
    """#7 / #8 / #9 在**畫面上**必須是三個不同的東西（M2 突變的守門人）。"""

    def test_five_pages_are_actually_there(self):
        """五頁都在 —— 否則下面那條反向守衛會掃 0 個檔案然後「通過」。"""
        assert len(_PAGES) == 5, [p.name for p in _PAGES]

    @pytest.mark.parametrize("state", _FAMILY)
    def test_every_family_state_has_meta(self, state):
        assert state in UI_STATES
        _name, _g, _hex = state_meta(state)
        assert _name.strip() and _g.strip(), f"{state} 的名稱與 glyph 都是必填"

    def test_the_four_render_as_four_different_things(self):
        """**核心斷言**：四者的 glyph 兩兩不同、名稱兩兩不同。

        合一的失效模式長什麼樣：常數有四個，`UI_STATE_META` 卻讓它們回同一組
        `("無資料", "▨")` —— 程式看起來分開了，**使用者看到的還是同一顆**。
        """
        _glyphs = [_glyph(s) for s in _FAMILY]
        _names = [_label(s) for s in _FAMILY]
        assert len(set(_glyphs)) == len(_FAMILY), f"glyph 撞了：{_glyphs}"
        assert len(set(_names)) == len(_FAMILY), f"名稱撞了：{_names}"

    def test_retryability_is_written_on_the_face_of_it(self):
        """#7 與 #8 的**文案本身**要讓人看得出該不該再按一次。

        golden pin：這兩句是使用者唯一會讀到的「該怎麼辦」，
        改動它就是改動對使用者的指引 —— 要改，就要有人在 review 看到。
        取自 `docs/v2/spec/UI_COMPONENTS.md §2` 徽章表的「文字」欄，逐字。
        """
        assert _label(UI_MISSING_RETRYABLE) == "缺漏 · 可重跑"
        assert _label(UI_NOT_APPLICABLE) == "不適用 · 重跑無效"
        assert _label(UI_MISSING_RETRYABLE) != _label(UI_NOT_APPLICABLE)

    def test_the_distinction_does_not_rely_on_colour(self):
        """四者**同色**，分辨完全靠 glyph 與文案。

        `UI_COMPONENTS.md §2` 引 `INDICATOR_SPEC` R-3 明文：灰系**內部**的
        「不適用」與「缺漏」必須再以符號分辨，⛔ 不得只靠顏色 ——
        **只差顏色等於把兩態併回一態**，而色盲使用者連那個差別都看不到。
        這條同時擋住「偷偷用顏色矇混過去」的假分辨。
        """
        assert {state_meta(s)[2] for s in _FAMILY} == {TRAFFIC_NEUTRAL}

    @pytest.mark.parametrize("state", _FAMILY)
    def test_none_of_them_is_alarming(self, state):
        """缺值**不是故障**。標紅就是 v3 §02 要杜絕的假性錯誤。"""
        assert not is_alarming(state) and state != UI_FAILED


class TestReasonDispatchActuallySplits:
    """`classify_ui_state()` 真的**依原因**分出 #7 / #8（M1 突變的守門人）。"""

    def test_no_input_is_the_retryable_one(self):
        assert classify_ui_state(
            requested=True, has_value=False,
            reason=MISS_NO_INPUT) == UI_MISSING_RETRYABLE

    def test_not_applicable_is_the_futile_one(self):
        assert classify_ui_state(
            requested=True, has_value=False,
            reason=MISS_NOT_APPLICABLE) == UI_NOT_APPLICABLE

    def test_the_two_do_not_collapse_into_one(self):
        """**這條是整個裁示的一句話版本。**

        「上游這輪失敗」與「結構上不適用」必須走到不同的狀態，
        而那兩個狀態必須畫成不同的東西。兩件事缺一不可，故一起斷言。
        """
        _a = classify_ui_state(requested=True, has_value=False,
                               reason=MISS_NO_INPUT)
        _b = classify_ui_state(requested=True, has_value=False,
                               reason=MISS_NOT_APPLICABLE)
        assert _a != _b, "兩種缺值又被判成同一態了"
        assert _glyph(_a) != _glyph(_b), "兩態判開了，畫面卻還是同一顆"
        assert _a != UI_EMPTY and _b != UI_EMPTY

    def test_dispatch_table_is_exactly_these_two(self):
        """golden：分派表只有這兩條。**新增一條就要有人在 review 看到** ——
        多分一種出去，就是多對使用者做一次「該不該重試」的宣稱。"""
        assert EMPTY_STATE_BY_REASON == {
            MISS_NO_INPUT: UI_MISSING_RETRYABLE,
            MISS_NOT_APPLICABLE: UI_NOT_APPLICABLE,
        }


class TestAmbiguousReasonsAreNotGuessed:
    """§1 Fail Loud：**判不出是哪一種，就不准挑一個看起來合理的。**"""

    @pytest.mark.parametrize("reason", [MISS_NOT_ENOUGH, MISS_NO_VARIATION])
    def test_wait_it_out_reasons_stay_on_the_conservative_fallback(self, reason):
        """「等時間累積」「等它開始動」**刻意**留在 `UI_EMPTY`。

        兩者重試無用，但它們**也不是** #8 所稱的「結構上不適用」：
        一檔新上市股票**完全適用**這盞燈，只是還不夠長。判成「不適用」＝
        對使用者說一句**永久性的假話**（暗示等再久也不會有，事實是會有）。
        `UI_COMPONENTS.md §2` 的十枚徽章沒有一枚描述得了它們，而該表明文
        「⛔ 不得新造第 11 種」⇒ 留在不對重試做任何宣稱的 `UI_EMPTY`，
        **那是此刻唯一誠實的畫法**。

        ⚠️ 前例：`CLAUDE.md §-2` 記載的 `MISS_*` 選錯事故 —— 新上市標的收到
        「可以重跑一次」的錯誤指引，真正原因是歷史長度不足，重跑一百次也一樣。
        **這條測試就是不要再踩同一個坑。**
        """
        assert classify_ui_state(requested=True, has_value=False,
                                 reason=reason) == UI_EMPTY

    def test_an_unknown_reason_falls_back_instead_of_picking_one(self):
        assert classify_ui_state(requested=True, has_value=False,
                                 reason="something_nobody_registered") == UI_EMPTY

    def test_no_reason_at_all_is_still_plain_empty(self):
        assert classify_ui_state(requested=True, has_value=False) == UI_EMPTY

    @pytest.mark.parametrize("reason", [MISS_FETCH_FAILED, MISS_CONTRACT_DRIFT])
    def test_the_red_ones_are_untouched(self, reason):
        """#6 的行為**一格都沒有動**（本次裁示只碰缺值家族）。"""
        assert classify_ui_state(requested=True, has_value=False,
                                 reason=reason) == UI_FAILED


class TestBackwardCompatibility:
    """`UI_EMPTY` 是既有鍵，全 repo 都在用 —— **語意與鍵名都不准動**。"""

    def test_ui_empty_still_exists_and_still_means_the_same_thing(self):
        assert UI_EMPTY == "empty" and UI_EMPTY in UI_STATES
        assert state_meta(UI_EMPTY) == ("無資料", state_meta(UI_EMPTY)[1],
                                        TRAFFIC_NEUTRAL)

    def test_the_no_value_family_is_exactly_the_three(self):
        """`UI_PARTIAL` **不在**裡面：#9 是「有值、只是不完整」，不是「沒有值」。"""
        assert NO_VALUE_STATES == {
            UI_EMPTY, UI_MISSING_RETRYABLE, UI_NOT_APPLICABLE}
        assert UI_PARTIAL not in NO_VALUE_STATES

    def test_new_keys_do_not_collide_with_the_other_four_state_vocabulary(self):
        """⚠️ `station_specs` 是**另一套**四態語彙（`live/degraded/missing/unwired`）。

        若這裡的 #7 用了字面 `"missing"`，一個誤傳進來的 `classify_state()`
        回傳值會**悄悄畫成 #7**；現在它仍會在 `state_meta()` 當場 fail loud。
        **那道防線不為了鍵名好看而拆。**
        """
        assert UI_MISSING_RETRYABLE != STATE_MISSING
        with pytest.raises(ValueError):
            state_meta(STATE_MISSING)


class TestPagesNeverHardcodeAGlyph:
    """🔴 **反向守衛**：五頁**整檔**不得出現缺值家族的字面符號。

    為什麼是「整檔」而不是「只掃執行期字串」：這四個符號在本次改動前
    **五頁合計 0 次出現**（實測 HEAD `17998e9`），所以整檔掃是**做得到**的，
    而做得到就該用最嚴的那一種 —— 只掃執行期字串的話，一句
    `# 這一格畫 ▨` 的註解會在 L0 改符號之後變成**與程式相反的說明**，
    而註解正是下一個人唯一會讀的東西。

    ⚠️ 本檔連自己的 docstring 都寫不出那些符號（見檔頭），那是刻意的：
    符號的唯一真相源是 L0 `UI_STATE_META`，這裡只從它讀回來比對。
    """

    @pytest.mark.parametrize("page", _PAGES, ids=lambda p: p.name)
    def test_no_literal_family_glyph_anywhere_in_the_page(self, page):
        _src = io.open(page, encoding="utf-8").read()
        _bad = {s: _glyph(s) for s in _FAMILY if _glyph(s) in _src}
        assert not _bad, (
            f"{page.name} 裡寫死了狀態符號 {sorted(_bad.values())} —— "
            "符號只准由 `state_meta()` 從 L0 供給一次。"
            "頁面自己寫一個，L0 改了之後畫面與 L0 就會說兩件不同的事")

    @pytest.mark.parametrize("page", _PAGES, ids=lambda p: p.name)
    def test_no_page_builds_its_own_state_meta_table(self, page):
        """⛔ 不得在頁面裡長出第二張狀態對映表（`CLAUDE.md §2.1` SSOT）。"""
        _src = io.open(page, encoding="utf-8").read()
        for _forbidden in ("UI_STATE_META =", "STATE_META =", "UI_STATE_META["):
            assert _forbidden not in _src, (
                f"{page.name} 疑似自建狀態對映表（命中 {_forbidden!r}）")
