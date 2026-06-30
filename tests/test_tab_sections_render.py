"""tests/test_tab_sections_render.py — U2 v18.401 tab_sections render helper 單元測試。

對應 src/ui/render/tab_sections.py(從 tab_stock.py 散落的 inline HTML 抽出 SSOT)。
"""
from __future__ import annotations

import pytest

from src.ui.render.tab_sections import (
    alert_box,
    border_left_banner,
    box_wrapper_close,
    box_wrapper_open,
    section_header,
    traffic_light_card,
)


class TestBoxWrapper:
    def test_neutral_default(self):
        html = box_wrapper_open()
        assert html.startswith('<div')
        assert 'background:#0d1117' in html
        assert 'padding:10px' in html

    def test_primary_theme_with_custom_padding(self):
        html = box_wrapper_open('primary', padding=12)
        assert 'background:#0a1628' in html
        assert 'border:1px solid #1f6feb' in html
        assert 'padding:12px' in html

    def test_unknown_theme_falls_back_to_neutral(self):
        html = box_wrapper_open('mystery_theme')  # type: ignore[arg-type]
        assert 'background:#0d1117' in html

    def test_close_is_pure_close_div(self):
        assert box_wrapper_close() == '</div>'


class TestSectionHeader:
    def test_title_only(self):
        html = section_header('營收動能')
        assert '營收動能' in html
        assert 'font-weight:700' in html

    def test_title_with_emoji_and_subtitle(self):
        html = section_header('營收動能', subtitle='YoY 趨勢', emoji='📈')
        assert '📈' in html
        assert '營收動能' in html
        assert 'YoY 趨勢' in html
        # subtitle 應該是灰色小字
        assert 'color:#8b949e' in html


class TestAlertBox:
    def test_info_level_blue_border(self):
        html = alert_box('info', '提示', '請注意')
        assert 'border-left:4px solid #1f6feb' in html
        assert 'ℹ️' in html
        assert '提示' in html
        assert '請注意' in html

    def test_error_level_red_border_no_text(self):
        html = alert_box('error', '系統錯誤')
        assert 'border-left:4px solid #f85149' in html
        assert '🔴' in html
        # 無 text 時不應出現空的 body div
        assert '<div style="font-size:13px' not in html

    def test_warning_level_yellow(self):
        html = alert_box('warning', '注意', '門檻已達')
        assert 'border-left:4px solid #d29922' in html
        assert '⚠️' in html

    def test_success_level_green(self):
        html = alert_box('success', '完成')
        assert 'border-left:4px solid #2ea043' in html
        assert '✅' in html


class TestBorderLeftBanner:
    def test_default_3px_border_dark_bg(self):
        html = border_left_banner('#f85149', '⛔ 警示文字')
        assert 'border-left:3px solid #f85149' in html
        assert 'background:#0d1117' in html
        assert '⛔ 警示文字' in html
        assert 'color:#f85149' in html
        assert 'font-weight:700' not in html  # 預設 non-bold

    def test_custom_border_width_and_bold(self):
        html = border_left_banner('#2ea043', 'OK', border_width=4, bold=True)
        assert 'border-left:4px solid #2ea043' in html
        assert 'font-weight:700' in html

    def test_custom_bg_for_alert_style(self):
        html = border_left_banner('#f85149', 'X', bg='#2a0d0d', padding_y=7, margin_y=3)
        assert 'background:#2a0d0d' in html
        assert 'padding:7px' in html
        assert 'margin:3px 0' in html

    def test_html_subtags_allowed_in_text(self):
        html = border_left_banner('#58a6ff', '價格 <b>100.5</b>')
        assert '<b>100.5</b>' in html


class TestTrafficLightCard:
    def test_basic_render(self):
        html = traffic_light_card('短線', '#2ea043', value='強')
        assert '短線' in html
        assert '強' in html
        assert 'border:1px solid #2ea043' in html
        assert 'color:#2ea043' in html

    def test_no_value_no_value_div(self):
        html = traffic_light_card('短線', '#d29922')
        assert '短線' in html
        assert 'font-size:20px' not in html  # value div 不該出現


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
