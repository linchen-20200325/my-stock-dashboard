"""C1（DEC-191）：TWII_SOURCE_TEXT 拿掉「，每日更新」——逐字鎖定＋反向守衛。

~~"本地加權指數歷史快取（來源 Yahoo，每日更新）"~~（舊值；有意識的文案變更，不是漏刪）。
只動文案常數；source／as_of／新鮮度判定／數值不在本檔改動範圍。
"""
from __future__ import annotations

from src.services import market_twii_view_service as S

NEW_TEXT = "本地加權指數歷史快取（來源 Yahoo）"


def test_twii_source_text_literal_pin():
    assert S.TWII_SOURCE_TEXT == NEW_TEXT


def test_twii_source_text_has_no_daily_update_claim():
    assert "每日更新" not in S.TWII_SOURCE_TEXT
    assert "每日" not in S.TWII_SOURCE_TEXT


def test_twii_view_default_source_follows_constant():
    import dataclasses
    f = {x.name: x for x in dataclasses.fields(S.TwiiTrendView)}["source"]
    assert f.default == NEW_TEXT
