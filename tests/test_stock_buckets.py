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
    assert STOCK_SECTION_ORDER == ["entry", "tech", "fundamental", "financials", "ai"]
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
