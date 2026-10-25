"""👤 我的 P1（DEC-083）—— L0 `shared/sheet_id.py` 新增常數 / 純函式，以及 L1 `oauth_state` 的選定與共用登出。

客戶原文：
- Q4：「一般 UI 顯示：『Sheet 名稱＋ID 末 6 碼』。」
- Q5：「登出時同步清除：Google 登入 session、active Sheet binding、URL 上 "sheet" 參數、OAuth state／登入流程
  攜帶的舊 Sheet ID、會造成登出後重新自動綁回舊 Sheet 的 silent marker。不得登出後自動恢復上一個 Sheet。」
- Q7：「👤 我的提供新版全站共用：active portfolio／active watchlist。……不得再以『名稱排序第一本』作為不可見的業務決策。」
"""
from __future__ import annotations

import pytest

from shared import sheet_id as S

_ID = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"   # 44 字元，同 Google 實測長度


# ══ L0 ═════════════════════════════════════════════════════════════════════
class TestSheetIdTail:
    def test_tail_is_last_six_with_ellipsis(self):
        assert S.SHEET_ID_TAIL_LEN == 6
        assert S.sheet_id_tail(_ID) == "…" + _ID[-6:]
        assert _ID not in S.sheet_id_tail(_ID)

    @pytest.mark.parametrize("raw", ["", None, "   ", "e", "含 空白", "<b>x</b>", "a" * 121])
    def test_unusable_id_gives_empty(self, raw):
        assert S.sheet_id_tail(raw) == ""

    def test_short_id_is_not_padded(self):
        assert S.sheet_id_tail("abc") == "…abc"


class TestSelectionKeys:
    def test_kinds_map_to_distinct_keys(self):
        _keys = S.ACTIVE_SELECTION_SESSION_KEYS
        assert set(_keys) == {S.SELECTION_KIND_PORTFOLIO, S.SELECTION_KIND_WATCHLIST}
        assert len(set(_keys.values())) == 2
        assert S.ACTIVE_PORTFOLIO_SESSION_KEY in _keys.values()
        assert S.ACTIVE_WATCHLIST_SESSION_KEY in _keys.values()

    def test_selection_keys_do_not_collide_with_binding_keys(self):
        assert not set(S.ACTIVE_SELECTION_SESSION_KEYS.values()) & set(S.SHEET_BINDING_SESSION_KEYS)

    def test_logout_extra_keys_are_the_me_page_keys(self):
        assert set(S.LOGOUT_EXTRA_SESSION_KEYS) == {
            S.ME_DRIVE_FOLDERS_SESSION_KEY, S.ME_DRIVE_SHEETS_SESSION_KEY, S.ME_PASTE_INPUT_KEY}
        assert all(_k.startswith("p07me_") for _k in S.LOGOUT_EXTRA_SESSION_KEYS)
