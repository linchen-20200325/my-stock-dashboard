"""v18.307 Bug2 PR-C — shared/stock_buckets section SSOT 測試。

涵蓋:
1. 5 section 完整性 + anchor / 漸層 HTML 結構
2. TOC 5 錨點
3. color_override 路徑
4. Fail Loud:壞 key → KeyError
5. drift:_FUNDAMENTAL_GREEN 鏡像 == shared.colors.TRAFFIC_GREEN
"""
from __future__ import annotations

import pytest

from shared.stock_buckets import (
    STOCK_SECTION_ORDER,
    STOCK_SECTION_META,
    section_header_html,
    render_stock_toc_html,
    _FUNDAMENTAL_GREEN,
)


def test_section_order_complete():
    # v18.308 PR-D：chips 升級為一級可導航桶（介於 tech 與 fundamental）
    assert STOCK_SECTION_ORDER == ["entry", "tech", "chips", "fundamental", "financials", "ai"]
    for k in STOCK_SECTION_ORDER:
        assert k in STOCK_SECTION_META
        meta = STOCK_SECTION_META[k]
        for field in ("emoji", "title", "color", "sub", "anchor", "toc"):
            assert field in meta, f"{k} 缺 {field}"


def test_section_header_html_structure():
    for k in STOCK_SECTION_ORDER:
        h = section_header_html(k)
        meta = STOCK_SECTION_META[k]
        assert f'id="{meta["anchor"]}"' in h    # 錨點(TOC 跳轉用)
        assert "linear-gradient" in h
        assert meta["emoji"] in h
        assert meta["title"] in h


def test_toc_has_all_anchors():
    toc = render_stock_toc_html()
    for k in STOCK_SECTION_ORDER:
        assert f'#{STOCK_SECTION_META[k]["anchor"]}' in toc
    assert toc.count('<a href="#sec-') == len(STOCK_SECTION_ORDER)


def test_chips_is_navigable_bucket():
    """v18.308 PR-D：籌碼為一級桶，有獨立 anchor + TOC chip。"""
    assert "chips" in STOCK_SECTION_ORDER
    h = section_header_html("chips")
    assert 'id="sec-chips"' in h
    assert "籌碼定位" in h
    toc = render_stock_toc_html()
    assert "#sec-chips" in toc


def test_color_override():
    custom = "#abcdef"
    h = section_header_html("fundamental", color_override=custom)
    assert custom in h
    # 預設 meta 色不應出現(被 override)
    assert h.count(STOCK_SECTION_META["fundamental"]["color"]) == 0 \
        or STOCK_SECTION_META["fundamental"]["color"] == custom


def test_bad_key_fail_loud():
    with pytest.raises(KeyError):
        section_header_html("nonexistent_bucket")


def test_fundamental_green_mirror_no_drift():
    """_FUNDAMENTAL_GREEN 鏡像必須 == shared.colors.TRAFFIC_GREEN（防色票漂移）。"""
    from shared.colors import TRAFFIC_GREEN
    assert _FUNDAMENTAL_GREEN == TRAFFIC_GREEN, (
        f"stock_buckets 鏡像 {_FUNDAMENTAL_GREEN} != TRAFFIC_GREEN {TRAFFIC_GREEN}；"
        "請同步更新鏡像常數")


# ══════════════════════════════════════════════════════════════
# v18.337 — 個股每桶 Bar 結論 + 燈號（compute_stock_section_levels
#           + section_header_html(level=, headline=)）
# ══════════════════════════════════════════════════════════════
from shared import stock_buckets as _sb
from shared.stock_buckets import (
    compute_stock_section_levels as _csl,
    section_header_html as _shh,
)


def test_light_color_drift_matches_shared_colors():
    """_LIGHT_COLOR 鏡像 shared.colors.TRAFFIC_*（§3.3 防漂移）。"""
    from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
    assert _sb._LIGHT_COLOR["green"] == TRAFFIC_GREEN
    assert _sb._LIGHT_COLOR["yellow"] == TRAFFIC_YELLOW
    assert _sb._LIGHT_COLOR["red"] == TRAFFIC_RED


def test_header_backward_compat_no_level():
    """不傳 level → 行為與舊版相同（無結論行，§向下相容）。"""
    h = _shh("tech")
    assert "🟢" not in h and "🟡" not in h and "🔴" not in h
    assert "技術面分析" in h


def test_header_renders_conclusion_on_bar():
    """傳 level+headline → Bar 上出現燈號 emoji + 結論文字。"""
    h = _shh("tech", level="green", headline="健康度 85 分 體質強（A）")
    assert "🟢" in h and "健康度 85 分" in h


def test_header_illegal_level_is_gray_not_green():
    """非法 level → gray ⬜（§1 不偽綠）。"""
    h = _shh("chips", level="bogus", headline="x")
    assert "⬜" in h and "🟢" not in h


def test_levels_all_six_sections_present():
    out = _csl()
    assert set(out) == {"entry", "tech", "chips", "fundamental", "financials", "ai"}
    # 全空輸入 → 可算的 4 桶 gray、on-demand 2 桶 gray（§1 不偽綠）
    for k in out:
        assert out[k]["level"] in {"green", "yellow", "red", "gray"}


def test_levels_tech_grade_thresholds_ssot():
    from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
    assert _csl(health=HEALTH_GRADE_A_MIN)["tech"]["level"] == "green"
    assert _csl(health=HEALTH_GRADE_A_MIN - 1)["tech"]["level"] == "yellow"
    assert _csl(health=HEALTH_GRADE_B_MIN)["tech"]["level"] == "yellow"
    assert _csl(health=HEALTH_GRADE_B_MIN - 1)["tech"]["level"] == "red"


def test_levels_entry_rs_thresholds_ssot():
    from shared.signal_thresholds import STOCK_RS_NEUTRAL_MIN, STOCK_RS_STRONG_MIN
    assert _csl(rs_val=STOCK_RS_STRONG_MIN)["entry"]["level"] == "green"
    assert _csl(rs_val=STOCK_RS_NEUTRAL_MIN)["entry"]["level"] == "yellow"
    assert _csl(rs_val=STOCK_RS_NEUTRAL_MIN - 1)["entry"]["level"] == "red"


def test_levels_chips_signal_categorical():
    assert _csl(chips_sig="吸籌", chips_con=8)["chips"]["level"] == "green"
    assert _csl(chips_sig="倒貨")["chips"]["level"] == "red"
    assert _csl(chips_sig="中性")["chips"]["level"] == "yellow"
    assert _csl(chips_sig=None)["chips"]["level"] == "gray"


def test_levels_fundamental_worst_light_wins():
    # 有紅燈 → 紅（最差燈號聚合，對齊 macro aggregate_level）
    assert _csl(li_green=5, li_yellow=0, li_red=1)["fundamental"]["level"] == "red"
    assert _csl(li_green=5, li_yellow=1, li_red=0)["fundamental"]["level"] == "yellow"
    assert _csl(li_green=6, li_yellow=0, li_red=0)["fundamental"]["level"] == "green"
    assert _csl()["fundamental"]["level"] == "gray"


def test_levels_financials_ai_always_gray_on_demand():
    """on-demand 兩桶一律 gray + 提示展開（§1 不用 top 不存在值偽造）。"""
    out = _csl(health=90, rs_val=90)   # 即使其他桶有值
    assert out["financials"]["level"] == "gray"
    assert out["ai"]["level"] == "gray"
    assert "體檢表" in out["financials"]["headline"]
    assert "AI" in out["ai"]["headline"]
