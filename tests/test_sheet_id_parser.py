"""Sheet Safety 批 B3（DEC-083）：單一 Sheet ID parser `shared/sheet_id.py` 的表格測試。

客戶原文：「`/spreadsheets/d/e/...` 發布網址：不得解析成 "e"。若發布網址不能安全轉成可操作
spreadsheet ID：明確拒絕並顯示白話錯誤。不得猜測。」
"""
from __future__ import annotations

import pytest

from shared import sheet_id as S

_ID = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"   # 44 字元，同 Google 實測長度


@pytest.mark.parametrize("raw, expected", [
    # 正常編輯網址 → 真正的 spreadsheet ID
    (f"https://docs.google.com/spreadsheets/d/{_ID}/edit", _ID),
    (f"https://docs.google.com/spreadsheets/d/{_ID}/edit#gid=0", _ID),
    (f"https://docs.google.com/spreadsheets/d/{_ID}/edit?usp=sharing", _ID),
    (f"https://docs.google.com/spreadsheets/d/{_ID}", _ID),
    (f"https://docs.google.com/spreadsheets/d/{_ID}?usp=sharing", _ID),
    (f"https://docs.google.com/spreadsheets/u/0/d/{_ID}/edit", _ID),
    (f"https://docs.google.com/spreadsheets/u/12/d/{_ID}/htmlview", _ID),
    (f"  https://docs.google.com/spreadsheets/d/{_ID}/edit  ", _ID),
    # 真 ID 以 e 開頭：不可被當成發布連結
    ("https://docs.google.com/spreadsheets/d/eAbc123_-x/edit", "eAbc123_-x"),
    # 純 ID（去頭尾空白）
    (_ID, _ID),
    (f"  {_ID}\n", _ID),
    ("a" * S.SHEET_ID_MAX_LEN, "a" * S.SHEET_ID_MAX_LEN),
])
def test_parse_ok(raw, expected):
    r = S.parse_sheet_input(raw)
    assert r.sheet_id == expected and r.error == "" and r.ok
    assert r.message == ""


@pytest.mark.parametrize("raw", [
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pub?output=csv",
    "https://docs.google.com/spreadsheets/u/0/d/e/2PACX-1vQabc/pubhtml",
    "https://docs.google.com/spreadsheets/d/e",
    "https://docs.google.com/spreadsheets/d/e?x=1",
    "https://docs.google.com/spreadsheets/d/e#frag",
])
def test_published_link_rejected_never_e(raw):
    r = S.parse_sheet_input(raw)
    assert r.sheet_id == "" and r.error == S.SHEET_INPUT_PUBLISHED_LINK and not r.ok
    assert "發布到網路" in r.message and "edit" in r.message


@pytest.mark.parametrize("raw", [
    f"https://drive.google.com/file/d/{_ID}/view",
    f"https://docs.google.com/spreadsheet/ccc?key={_ID}",
    f"key={_ID}",
    "abc def",
    "<script>alert(1)</script>",
    "ＡＢＣ１２３",                                   # 全形字
    "a" * (S.SHEET_ID_MAX_LEN + 1),                  # 超過長度上限
    "https://docs.google.com/spreadsheets/d/",       # 片段為空
    "https://docs.google.com/spreadsheets/d/ab%20cd/edit",
    "https://docs.google.com/spreadsheets/d/ＡＢＣ/edit",
])
def test_invalid_rejected(raw):
    r = S.parse_sheet_input(raw)
    assert r.sheet_id == "" and r.error == S.SHEET_INPUT_INVALID
    assert r.message == S.SHEET_INPUT_ERROR_MESSAGES[S.SHEET_INPUT_INVALID]


@pytest.mark.parametrize("raw", [None, "", "   ", "\n\t"])
def test_empty(raw):
    r = S.parse_sheet_input(raw)
    assert r.sheet_id == "" and r.error == S.SHEET_INPUT_EMPTY


@pytest.mark.parametrize("raw", [
    "<script>x</script>", "ＡＢＣ", "a" * 121, "abc def",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml"])
def test_messages_do_not_echo_user_input(raw):
    """白話錯誤訊息⛔ 不回顯使用者貼上的內容（避免把怪字元／HTML 搬上畫面）。"""
    msg = S.parse_sheet_input(raw).message
    assert msg and raw.strip() not in msg


@pytest.mark.parametrize("raw, expected", [
    (_ID, _ID), (f" {_ID} ", _ID), ("", ""), (None, ""), ("e", "e"),
    ("a/b", ""), ("a" * 121, ""), ("ab.cd", ""), (123, "123"),
])
def test_sanitize(raw, expected):
    assert S.sanitize_sheet_id(raw) == expected


def test_sanitize_regex_identical_to_pre_move_oauth_state_rule():
    """`SHEET_ID_RE` 自 `oauth_state._SHEET_ID_RE` 原樣搬來（字母集、長度界一字未改）。"""
    assert S.SHEET_ID_RE.pattern == r"[A-Za-z0-9_-]{1,120}"


def test_key_constants_match_legacy_literals():
    """session / URL key 值與修前各處字面值逐字相同（只是集中，不改值）。"""
    assert S.PORTFOLIO_SHEET_SESSION_KEY == "portfolio_sheet_id"
    assert S.STOCK_PORTFOLIO_SHEET_SESSION_KEY == "stock_portfolio_sheet_id"
    assert S.SHEET_BINDING_SESSION_KEYS == ("portfolio_sheet_id", "stock_portfolio_sheet_id")
    assert S.SHEET_QUERY_PARAM == "sheet"


def test_every_error_code_has_a_message():
    for code in (S.SHEET_INPUT_EMPTY, S.SHEET_INPUT_PUBLISHED_LINK, S.SHEET_INPUT_INVALID):
        assert S.SHEET_INPUT_ERROR_MESSAGES[code]
