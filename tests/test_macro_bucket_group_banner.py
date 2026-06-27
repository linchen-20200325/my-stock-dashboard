"""v18.310 總經版面重設計 — bucket_group_banner_html 測試。

總經分頁載入後 deep section 視覺歸位成 5+1 桶群組(user 反饋「版面太散」)。
本 banner 為純字串 builder(L0,零 streamlit)。

涵蓋:
1. 5 桶 + AI 群組各產合法 banner
2. 含對應主色 + emoji + title
3. 桶 idx/total badge
4. Fail Loud:壞 key → KeyError
5. tab_macro 確實插入 5 個 banner
"""
from __future__ import annotations

import pytest

from shared.macro_buckets import (
    bucket_group_banner_html,
    BUCKET_GROUP_COLOR,
    BUCKET_META,
)


def test_all_buckets_render():
    for k in ("long", "mid", "short", "chips", "news"):
        h = bucket_group_banner_html(k, 1)
        assert "linear-gradient" in h
        assert BUCKET_GROUP_COLOR[k] in h
        assert BUCKET_META[k]["emoji"] in h
        assert BUCKET_META[k]["title"] in h


def test_ai_group_renders():
    h = bucket_group_banner_html("ai", 6)
    assert BUCKET_GROUP_COLOR["ai"] in h
    assert "🧠" in h
    assert "AI 綜合決策" in h
    assert "綜合" in h   # AI badge 用「綜合」非「桶 N」


def test_bucket_badge_shows_index():
    h = bucket_group_banner_html("long", 1, total=5)
    assert "桶 1/5" in h


def test_bad_key_fail_loud():
    with pytest.raises(KeyError):
        bucket_group_banner_html("nonexistent", 1)


def test_tab_macro_inserts_five_banners():
    """tab_macro.py 必須在 5 個桶叢集前插入 group banner。"""
    import tab_macro
    src = open(tab_macro.__file__, encoding="utf-8").read()
    for key in ("'long'", "'mid'", "'short'", "'chips'", "'ai'"):
        assert f"_bgb({key}" in src, f"tab_macro 缺 {key} 桶 banner"


def test_top_summary_dashboard_present():
    """五桶 bar 上方有『總經總結儀表板』醒目框(user 反饋『不夠顯眼』)。"""
    import tab_macro
    src = open(tab_macro.__file__, encoding="utf-8").read()
    assert "總經總結儀表板" in src
