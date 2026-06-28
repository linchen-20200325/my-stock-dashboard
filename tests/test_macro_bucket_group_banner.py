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


def test_global_group_renders():
    """v18.317 🌍 全球風險群組(10 燈雷達改桶)— 與 ai 同走特例 meta,badge=雷達。"""
    h = bucket_group_banner_html("global", 0)
    assert BUCKET_GROUP_COLOR["global"] in h
    assert "🌍" in h
    assert "全球風險" in h
    assert "雷達" in h   # global badge 用「雷達」非「桶 N/5」
    assert "桶 0/5" not in h


def test_pivot_and_cashflow_groups_render():
    """v18.321 🔮 拐點 / 💵 現金流向 群組 banner(分組化收尾)— 特例 meta + 自訂 badge。"""
    hp = bucket_group_banner_html("pivot", 0)
    assert BUCKET_GROUP_COLOR["pivot"] in hp
    assert "🔮" in hp and "拐點" in hp and "拐點" in hp
    assert "桶 0/5" not in hp
    hc = bucket_group_banner_html("cashflow", 0)
    assert BUCKET_GROUP_COLOR["cashflow"] in hc
    assert "💵" in hc and "現金流向" in hc and "金流" in hc
    assert "桶 0/5" not in hc


def test_tab_macro_inserts_pivot_cashflow_banners():
    """tab_macro 必須在拐點 + 現金流向區塊插入 group banner。
    F-7.1 B-S2:拐點 banner 搬至 macro/section_state.py;檢查合集。"""
    from src.ui.tabs import tab_macro
    from src.ui.tabs.macro import section_state
    src = (open(tab_macro.__file__, encoding="utf-8").read()
           + open(section_state.__file__, encoding="utf-8").read())
    assert "_bgb_pv('pivot'" in src, "tab_macro/section_state 缺 🔮 拐點 banner"
    assert "_bgb_cf('cashflow'" in src, "tab_macro/section_state 缺 💵 現金流向 banner"


def test_bad_key_fail_loud():
    with pytest.raises(KeyError):
        bucket_group_banner_html("nonexistent", 1)


def test_tab_macro_inserts_five_banners():
    """src/ui/tabs/tab_macro.py + 抽出的 section_*.py 必須在 5 個桶叢集前插入 group banner。
    F-7.1 B-2/B-3/B-5:short/ai/long 桶 _bgb call 搬到各 section_*.py;檢查合集。"""
    from src.ui.tabs import tab_macro
    from src.ui.tabs.macro import section_short, section_ai, section_long, section_chips
    src = (open(tab_macro.__file__, encoding="utf-8").read()
           + open(section_short.__file__, encoding="utf-8").read()
           + open(section_ai.__file__, encoding="utf-8").read()
           + open(section_long.__file__, encoding="utf-8").read()
           + open(section_chips.__file__, encoding="utf-8").read())
    for key in ("'long'", "'mid'", "'short'", "'chips'", "'ai'"):
        assert f"_bgb({key}" in src, f"tab_macro 缺 {key} 桶 banner"


def test_top_summary_dashboard_present():
    """五桶 bar 上方有『總經總結儀表板』醒目框(user 反饋『不夠顯眼』)。"""
    from src.ui.tabs import tab_macro
    src = open(tab_macro.__file__, encoding="utf-8").read()
    assert "總經總結儀表板" in src


# ════════════════════════════════════════════════════════════════
# v18.313 桶輕量總結 bar
# ════════════════════════════════════════════════════════════════

def test_bucket_summary_bar_with_data():
    from shared.macro_buckets import bucket_summary_bar_html
    s = {'color': '#3fb950', 'emoji': '🟢', 'label': '結構健康', 'details': [
        {'danger': 'green', 'label': 'M1B-M2', 'value_str': '5.2pt'},
        {'danger': 'yellow', 'label': '年線乖離', 'value_str': '+18%'},
        {'danger': 'red', 'label': 'X', 'value_str': '9'},
    ]}
    h = bucket_summary_bar_html('long', s)
    assert '整體狀態' in h and '結構健康' in h
    assert 'M1B-M2' in h and '5.2pt' in h
    assert 'SPEC §11' in h
    # 燈號計數
    assert '🔴 1' in h and '🟡 1' in h and '🟢 1' in h


def test_bucket_summary_bar_empty_fail_safe():
    """空 summary → 顯示『未載入』+ 引導,不 raise / 不偽造數字(§1)。"""
    from shared.macro_buckets import bucket_summary_bar_html
    h = bucket_summary_bar_html('long', {})
    assert '未載入' in h
    assert '尚未載入資料' in h


def test_tab_macro_buckets_have_summary_bar():
    """tab_macro 各資料桶(long/mid/short/news)接 render_macro_bucket_summary_bar；
    §三 籌碼(chips)保留原樣不加(user 2026-06-27 指定)。"""
    # F-7.1 a/B-2/B-3/B-5:bucket_summary_bar_html 在 macro/helpers.py;
    # short/news/long 桶 call 在 section_short.py / section_ai.py / section_long.py;
    # 其他 bucket call 仍在 tab_macro.py。檢查 5 處合集。
    from src.ui.tabs import tab_macro
    from src.ui.tabs.macro import helpers as _macro_helpers
    from src.ui.tabs.macro import section_short as _section_short
    from src.ui.tabs.macro import section_ai as _section_ai
    from src.ui.tabs.macro import section_long as _section_long
    src = (open(tab_macro.__file__, encoding='utf-8').read()
           + open(_macro_helpers.__file__, encoding='utf-8').read()
           + open(_section_short.__file__, encoding='utf-8').read()
           + open(_section_ai.__file__, encoding='utf-8').read()
           + open(_section_long.__file__, encoding='utf-8').read())
    assert 'bucket_summary_bar_html' in src
    # 用 prefix 比對（不含右括號）：long 自 v18.338 起帶 with_cards=True 選參，
    # 桶仍有接 summary bar，斷言放寬以容許額外 kwarg（intent 不變）。
    for key in ('long', 'mid', 'short', 'news'):
        assert f"render_macro_bucket_summary_bar('{key}'" in src, f"缺 {key} 桶總結 bar"
    # 籌碼桶不可有總結 bar(保留原樣)
    assert "render_macro_bucket_summary_bar('chips')" not in src, "籌碼桶不應加總結 bar(user 指定保留)"


def test_render_macro_bucket_summary_bar_callable():
    from src.ui.tabs import tab_macro
    assert callable(getattr(tab_macro, 'render_macro_bucket_summary_bar', None))
